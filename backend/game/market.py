"""Where a commodity is bought and sold, and for how much.

    fl.py market --find gold
    fl.py market --list

`DATA/EQUIPMENT/market_commodities.ini` holds 178 `[BaseGood]` sections, one per
base with a market, each carrying a run of:

    MarketGood = commodity_gold, 0, -1, 150, 500, 0, 1.08
                 ^ good          ^rank ^rep ^min ^max ^flag ^multiplier

The price is the commodity's own price from `goods.ini` times that multiplier:
gold is 425 a unit and the multipliers run from 0.001 to 100, which is how the
same cargo is worth 1 credit at one base and 1530 at another.

**The flag says which way the trade goes, and the data is unanimous about it.**
Of the 1994 commodity rows, 844 read flag 0 with a real stock range and 1150
read flag 1 with a stock of exactly zero. No row breaks the pattern, so:

    flag 0  the base has stock and sells it     -> you buy here
    flag 1  the base holds none and wants it    -> you sell here

Bases the player cannot dock at are dropped, the same 164 the rest of the tool
counts. 18 of the 178 markets belong to those: the mining platforms, Tohoku and
Alaska, and the cutscene copies. A price you can never reach is not information.
"""

import argparse
import os
import re
import sys

from . import bases as bs
from . import flvisits as fl
from . import infocards as ic
from . import wrecks as wr

SELLS_TO_YOU = 0  # the base has stock: this is where you buy


def _first(entry, key):
    """The first value of a key, already unwrapped. Do not index it again."""
    got = entry.get(key)
    return got[0] if got else None


def base_index(game_dir, data_dir=None, strings=None):
    """(dockable set, base -> the shared base shape, system nick -> label).

    Every market in the game is keyed by a base nickname and has to be turned
    into somewhere a player can find, so this is shared rather than rebuilt.
    `equipment.py` uses the same `ref` and must not grow its own copy: that is
    how `flvisits.py` and `serve.py` drifted apart in August.

    `sysname` comes back too because a wreck sits in a system without being a
    base, and that is genuinely a different thing.
    """
    data_dir = data_dir or fl.ipath(game_dir, "DATA")
    strings = strings if strings is not None else fl.load_names(game_dir)
    dockable = bs.dockable_bases(game_dir, data_dir, fl.system_files, fl.ipath)
    sectors = bs.base_sectors(
        data_dir, fl.system_files,
        bs.load_scales(data_dir, fl.read_ini, fl.ipath))
    _bases, systems = fl.load_universe(data_dir)
    objects = fl.load_objects(data_dir, systems)
    where, label = {}, {}
    for _nick, (system, base, ids) in objects.items():
        key = base.lower()
        where.setdefault(key, system)
        try:
            label.setdefault(key, strings.get(int(ids), key))
        except (TypeError, ValueError):
            label.setdefault(key, key)
    sysname = {}
    for nick, ids in systems.items():
        try:
            sysname[nick.lower()] = strings.get(int(ids), nick)
        except (TypeError, ValueError):
            sysname[nick.lower()] = nick
    def ref(key):
        """The one shape a base takes anywhere in this tool.

        `id` is the identity and `sys` is the system's, because display names
        collide: "Omicron Beta" is two systems, "Omicron Major" four. The rest
        is what gets printed. Every page that shows a base shows these fields
        under these names.
        """
        system = where.get(key, "")
        return {"id": key, "name": label.get(key, key),
                "system": sysname.get(system, system), "sys": system,
                "at": sectors.get(key, "")}

    return dockable, ref, sysname


# The banner the game writes into the item's own infocard. `plain` leaves the
# angle brackets as entities, and a hand-edited card could carry them raw, so
# both spellings are matched rather than one being assumed.
PERISHABLE = re.compile(
    r"(?:>|&gt;){2,}\s*(HIGHLY\s+PERISHABLE|PERISHABLE)\s*(?:<|&lt;){2,}", re.I)


def perishable(game_dir, cards=None):
    """Commodity -> the game's own word for how badly it spoils, or nothing.

    Exactly three of the 105 commodities on a stock install:

        Alien Organisms   decay_per_second 1.0   hit_pts 100   HIGHLY PERISHABLE
        Luxury Food       decay_per_second 1.0   hit_pts 100   HIGHLY PERISHABLE
        MOX               decay_per_second 1.0   hit_pts 200   PERISHABLE

    Every other commodity reads `decay_per_second = 0` and `hit_pts = 250`, and
    carries no banner in its card. All three are traded.

    **The two halves of the rule are independent and they agree.** *Which*
    commodities spoil is a number, `decay_per_second`; *how badly* is the
    `>>>PERISHABLE<<<` banner the game prints at the top of the item's own
    infocard. The set the field picks out and the set the text picks out are
    the same three, which is why this is derived rather than kept as a list of
    three nicknames somebody typed.

    **What none of it says is what spoiling costs you on a run.**
    `decay_per_second` sits among `pod_appearance`, `loot_appearance` and
    `hit_pts`, which are all properties of the container once it is floating in
    space, so the files do not prove that a hold loses cargo in flight. Show
    the game's own label and leave the arithmetic alone: do not invent a decay
    model here, and do not let one in later.
    """
    cards = cards if cards is not None else ic.load_cards(game_dir)
    equip_dir = fl.ipath(fl.ipath(game_dir, "DATA"), "EQUIPMENT")
    out = {}
    for section, pairs in wr.read_multi(fl.ipath(equip_dir, "select_equip.ini")):
        if section.lower() != "commodity":
            continue
        entry = {}
        for key, values in pairs:
            entry.setdefault(key.lower(), values)
        nick = _first(entry, "nickname")
        try:
            decays = float(_first(entry, "decay_per_second") or 0)
        except (TypeError, ValueError):
            decays = 0
        if not nick or not decays:
            continue
        found = PERISHABLE.search(cards.get(_int(_first(entry, "ids_info")), ""))
        # The grade comes from the card; the field is what says there is one to
        # look for. A card that has lost its banner still leaves a marked
        # commodity rather than an unmarked one.
        grade = " ".join(found.group(1).upper().split()) if found else "PERISHABLE"
        out[str(nick).lower()] = grade
    return out


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def load_market(game_dir=None):
    """(commodities, rows).

    `commodities` is nickname -> display name. Each row is a dict with the
    base, the commodity, the price, and which way the trade runs.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    data_dir = fl.ipath(game_dir, "DATA")
    equip_dir = fl.ipath(data_dir, "EQUIPMENT")
    strings = fl.load_names(game_dir)

    # Base price per unit. Only `category = commodity` counts; the same file
    # also prices every gun and ship in the game.
    price = {}
    for section, pairs in wr.read_multi(fl.ipath(equip_dir, "goods.ini")):
        if section.lower() != "good":
            continue
        entry = {}
        for key, values in pairs:
            entry.setdefault(key.lower(), values)
        cat = _first(entry, "category")
        nick = _first(entry, "nickname")
        cost = _first(entry, "price")
        if not nick or not cat or not cost:
            continue
        if str(cat).lower() != "commodity":
            continue
        try:
            price[str(nick).lower()] = float(cost)
        except (TypeError, ValueError):
            continue

    # Display names live in select_equip.ini, not in goods.ini.
    names = {}
    for section, pairs in wr.read_multi(fl.ipath(equip_dir, "select_equip.ini")):
        entry = {}
        for key, values in pairs:
            entry.setdefault(key.lower(), values)
        nick, ids = _first(entry, "nickname"), _first(entry, "ids_name")
        if not nick or not ids:
            continue
        key = str(nick).lower()
        if key in price:
            try:
                names[key] = strings.get(int(ids), key)
            except (TypeError, ValueError):
                names[key] = key
    for key in price:
        names.setdefault(key, key)

    # On the row rather than in a table the pages have to look things up in:
    # `trades`, `sells`, `best_runs` and `routes` then all carry it without any
    # of them learning what perishable means.
    spoils = perishable(game_dir)

    dockable, ref, _sysname = base_index(game_dir, data_dir, strings)

    rows = []
    market = fl.ipath(equip_dir, "market_commodities.ini")
    for section, pairs in wr.read_multi(market):
        if section.lower() != "basegood":
            continue
        entry = {}
        for key, values in pairs:
            entry.setdefault(key.lower(), []).append(values)
        base = entry.get("base")
        if not base:
            continue
        key = str(base[0][0]).lower()
        if key not in dockable:
            continue
        for values in entry.get("marketgood", []):
            good = str(values[0]).lower()
            if good not in price or len(values) < 7:
                continue
            try:
                flag, mult = float(values[5]), float(values[6])
            except (TypeError, ValueError):
                continue
            rows.append({
                "base": ref(key),
                "good": good,
                "good_name": names.get(good, good),
                "price": round(price[good] * mult),
                "buy": flag == SELLS_TO_YOU,
                "perishable": spoils.get(good, ""),
            })
    return names, rows


def trades(rows, good, source=None, visited=None, only=None, only_visited=False):
    """Every base trading `good`, dearest first.

    Descending price puts the best place to sell at the top and the cheapest
    place to buy at the bottom, which is the same list read from either end.

    **`source` is the only difference between the two questions this tab used
    to ask from two separate pages.** Given a row you would buy at, each result
    gains `delta`, the profit a unit, and the source base itself drops out
    because you cannot run a cargo to where it already is.

    The order does not change and cannot: `delta` is `price` minus a constant,
    so sorting by margin and sorting by price are the same sort. That is why
    these were one function all along and were written as two.

    Bases holding stock are not dropped. Freelancer lets you sell a commodity
    at any base whose market lists it, and one that also stocks it is a real
    destination, just usually a cheap one. Which end is which stays readable
    from the colour rule the page keeps.
    """
    out = []
    for row in rows:
        if row["good"] != good:
            continue
        if source is not None and row["base"]["id"] == source["base"]["id"]:
            continue
        if only is not None and row["base"]["id"] not in only:
            continue
        if only_visited and visited is not None and row["base"]["id"] not in visited:
            continue
        if source is not None:
            row = dict(row, delta=row["price"] - source["price"])
        if visited is not None:
            row = dict(row, visited=row["base"]["id"] in visited)
        out.append(row)
    out.sort(key=lambda r: (-r["price"], r["base"]["name"]))
    return out


def sells(rows, base):
    """What `base` has on the shelf, dearest first.

    Only the flag-0 rows: a base with none of something cannot sell it to you,
    however much it is willing to pay.
    """
    out = [r for r in rows if r["base"]["id"] == base and r["buy"]]
    out.sort(key=lambda r: (-r["price"], r["good_name"]))
    return out


def best_runs(rows, base, only=None):
    """Everything `base` sells, each with where it is worth most.

    One pass over the rows per commodity rather than a request per line: the
    figure is the whole point of the list, so it cannot wait for a click.
    A good with nowhere to take it carries `best` as None.
    """
    by_good = {}
    for row in rows:
        by_good.setdefault(row["good"], []).append(row)
    out = []
    for src in sells(rows, base):
        found = trades(by_good[src["good"]], src["good"], src, only=only)
        out.append({**src, "best": found[0] if found else None})
    return out


CARGO = re.compile(r"^cargo\s*=\s*([^,\s]+)\s*,\s*(\d+)", re.I | re.M)


def hold(saved, goods):
    """What is in the hold, {commodity: units}.

    **A real save names cargo by `FLHash` of the nickname, not by the
    nickname**, the same one-way hash the visit flags use, so every commodity
    is hashed once here and the line is looked up by number. The tutorial's
    `Restart.fl` is the one exception and writes plain nicknames; both are
    read, because testing against the tutorial save alone would prove the
    wrong half works.

    Only commodities. The same `cargo` lines carry countermeasures, nanobots,
    batteries and damaged guns, which are equipment a player fits or consumes,
    not freight any base will buy.

    Takes the decoded save text, not a path. The hold is exactly as fresh as
    the last time the game wrote a save, which is the whole caveat and the
    page states it rather than hiding it: a hold read five minutes ago is
    still worth planning against. Whose read it is matters too, so the caller
    passes the text in and one request sees one save throughout.

    Lives here rather than beside `parse_visits` because `flvisits.py` is
    frozen and the hold is a trade question, not a visit one.
    """
    by_hash = {fl.fl_hash(nick): nick for nick in goods}
    out = {}
    for token, count in CARGO.findall(saved):
        # `isdecimal`, not `isdigit`: '\xb2' is a digit to `isdigit` and a
        # ValueError to `int`, and latin-1 save text can carry one.
        key = by_hash.get(int(token)) if token.isdecimal() else token.lower()
        if key in goods:
            out[key] = out.get(key, 0) + int(count)
    return out


def hold_runs(rows, held, only=None, names=None):
    """Every system that will buy the hold, by what the whole load fetches.

    A system, not a base, because the question is where to fly once rather
    than which single counter pays best. `bases` says how many stops that
    costs inside the system and `one` is the best base that takes the whole
    load by itself, so a couple of thousand credits can be traded against not
    undocking again.

    Ranked on money, never on price a unit: 45 tonnes at 720 beats 5 at 2400,
    and the hold is what there actually is to sell.

    Systems taking only part of the load are kept, with `missing` naming the
    rest. When nothing takes all of it, which system takes the most of it is
    the next question, and dropping those rows would throw away the answer.

    `names` is the market's commodity -> display name table. Without it a
    commodity that no dockable base trades has no row to learn its name from,
    and `missing` prints the raw nickname next to properly named neighbours.
    """
    label = dict(names or {})
    best, per_base = {}, {}
    for row in rows:
        good = row["good"]
        if good not in held:
            continue
        label.setdefault(good, row["good_name"])
        if only is not None and row["base"]["id"] not in only:
            continue
        system = row["base"]["sys"]
        top = best.setdefault(system, {}).get(good)
        if top is None or row["price"] > top["price"]:
            best[system][good] = row
        per_base.setdefault(system, {}).setdefault(row["base"]["id"], {})[good] = row

    out = []
    for system, picks in best.items():
        goods = sorted(
            ({"good": good, "name": row["good_name"], "units": held[good],
              "price": row["price"], "value": row["price"] * held[good],
              "base": row["base"]}
             for good, row in picks.items()),
            key=lambda g: -g["value"])
        # A base that takes everything the system takes. Fewer than that and it
        # is not a single stop, whatever it pays.
        one = None
        for stocked in per_base[system].values():
            if len(stocked) < len(picks):
                continue
            total = sum(r["price"] * held[g] for g, r in stocked.items())
            if one is None or total > one["total"]:
                one = {"total": total, "base": next(iter(stocked.values()))["base"]}
        out.append({
            "sys": system,
            "system": goods[0]["base"]["system"],
            "total": sum(g["value"] for g in goods),
            "bases": len({g["base"]["id"] for g in goods}),
            "goods": goods,
            # `label` is seeded from `names` and topped up from the rows, so
            # the nickname fallback is a crash guard rather than something the
            # page is expected to show.
            "missing": sorted(label.get(g, g) for g in held if g not in picks),
            "one": one,
        })
    # Most of the load first, then money. A system that takes two of three is
    # never the answer while one takes all three, however much it pays.
    out.sort(key=lambda r: (len(r["missing"]), -r["total"]))
    return out


def routes(rows, src, dst, only=None):
    """What to buy in system `src` and sell in system `dst`, best margin first.

    Systems by nickname, never by display name: see `sys` on the base.

    One row per commodity rather than one per pair of bases. New York alone has
    12 market bases, so the uncollapsed cross product is mostly noise, and the
    cheapest place to buy against the dearest place to sell is by definition the
    pair with the widest margin.

    Losing and break-even rows are kept. The caller drops them, because how many
    there were is worth saying and cannot be recovered afterwards.
    """
    buy, sell = {}, {}
    for row in rows:
        if only is not None and row["base"]["id"] not in only:
            continue
        if row["base"]["sys"] == src and row["buy"]:
            cheap = buy.get(row["good"])
            if cheap is None or row["price"] < cheap["price"]:
                buy[row["good"]] = row
        if row["base"]["sys"] == dst:
            dear = sell.get(row["good"])
            if dear is None or row["price"] > dear["price"]:
                sell[row["good"]] = row
    out = []
    for good, source in buy.items():
        target = sell.get(good)
        if target is None or target["base"]["id"] == source["base"]["id"]:
            continue
        out.append({
            "good": good,
            "name": source["good_name"],
            # The commodity's, not the route's, so it rides along from the row
            # the good was bought at rather than being looked up again.
            "perishable": source.get("perishable", ""),
            "buy": source["price"],
            "sell": target["price"],
            "gain": target["price"] - source["price"],
            "from": source["base"],
            "to": target["base"],
        })
    out.sort(key=lambda r: (-r["gain"], r["name"]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--find", help="commodity name or part of one")
    ap.add_argument("--list", action="store_true", help="show every commodity")
    args = ap.parse_args()

    names, rows = load_market(args.game)
    if args.list or not args.find:
        for key in sorted(names, key=lambda k: names[k]):
            n = sum(1 for r in rows if r["good"] == key)
            print(f"  {names[key]:<26} {n:>3} bases")
        return

    want = args.find.strip().lower()
    hits = [k for k, v in names.items() if want in v.lower() or want in k]
    if not hits:
        sys.exit(f"no commodity matching {args.find!r}")
    for key in sorted(hits, key=lambda k: names[k]):
        found = trades(rows, key)
        print(f"\n{names[key]} ({len(found)} bases)")
        for row in found:
            way = "buy " if row["buy"] else "sell"
            print(f"   {row['price']:>6} cr  {way}  {row['base']['name'][:28]:<29} "
                  f"{row['base']['system']}")

