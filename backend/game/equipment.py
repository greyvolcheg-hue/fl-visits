"""Buyable equipment, its stats, and where to get it.

    fl.py equipment --kind guns --top 10
    fl.py equipment --kind shields --top 10
    fl.py equipment --where "Adv. Ripper"

`DATA/EQUIPMENT/market_misc.ini` is the equipment counterpart of
`market_commodities.ini`: 176 bases, 10871 rows, each naming a `[Good]` that in
turn names a piece of equipment. Row shape is the same seven fields:

    MarketGood = br_gun01_mark01, 6, -1, 10, 10, 0, 1
                 ^ good           ^rank ^rep ^min ^max ^flag ^multiplier

**Three facts about that file drive the whole design, and all three were checked
against the shipped data rather than assumed.**

*Equipment costs the same everywhere.* The multiplier is exactly 1.0 on all
10871 rows and no good's multiplier differs between bases, so the price is a
property of the item, not of where you buy it. There is nothing to shop around
for and the price belongs on the item's own line. Do not copy the Trade tab's
cheapest-versus-dearest logic over here; it has nothing to work on.

*The rank and reputation gates are properties of the item too.* Rank runs
0, 2, 6, 10, 16, 22, 26, 30 and the rep requirement -1 (none) to +0.8, and
across the 366 goods sold at more than one base neither ever differs between
them.

*27 of the 247 mountable guns are sold nowhere.* They are the codenamed ones,
ARCHANGEL, BLOODSTONE, CERBERUS, Death's Hand. Those are wreck loot, so for
them `where` names the wreck instead of a dealer, which is the actual answer
rather than an empty list.

Guns come from `weapons.load_weapons`, which already reads both the `[Gun]` and
its `[Munition]`. Shields are parsed here because nothing else needed them yet.
"""

import argparse
import os
import sys

from . import flvisits as fl
from . import market as mk
from . import weapons as wp
from . import wrecks as wr

# What the page offers, and what each kind is ordered by when nothing else is
# asked for. A parameter is `(key, label, kind, unit)`; `kind` is "num" for
# anything with a threshold and "pick" for one chosen from a list.
PARAMETERS = {
    "guns": [
        ("hull_dps", "hull DPS", "num", ""),
        ("shield_dps", "shield DPS", "num", ""),
        # A pick, not a threshold: there are only 14 muzzle velocities in the
        # game and the question people ask is "which guns do exactly 600",
        # which no minimum can express.
        ("speed_group", "projectile speed", "pick", "m/s"),
        ("range", "range", "num", "m"),
        ("rate", "refire rate", "num", "/s"),
        ("power", "power per shot", "num", ""),
        # Two parameters, because a hardpoint is two facts. `hp_gun_special_6`
        # and `hp_turret_special_6` are different sockets on the ship and were
        # both labelled "6" until 2026-09-04, which merged 32 guns with 19
        # turrets under one filter value.
        ("kind", "gun or turret", "pick", ""),
        ("mount", "mount class", "class", ""),
        ("price", "price", "num", "cr"),
        ("rank", "rank needed", "num", ""),
    ],
    "shields": [
        ("capacity", "capacity", "num", ""),
        ("regen", "regeneration", "num", "/s"),
        ("drain", "constant drain", "num", ""),
        ("rebuild", "rebuild time", "num", "s"),
        ("shield_type", "type", "pick", ""),
        ("mount", "mount class", "class", ""),
        ("price", "price", "num", "cr"),
        ("rank", "rank needed", "num", ""),
    ],
}
ORDER = {"guns": "hull_dps", "shields": "capacity"}


def _entries(pairs):
    out = {}
    for key, values in pairs:
        out.setdefault(key.lower(), []).append(values)
    return out


def _first(entry, key):
    got = entry.get(key)
    return got[0][0] if got else None


def _num(entry, key):
    try:
        return float(_first(entry, key))
    except (TypeError, ValueError):
        return None


def _mount_label(raw):
    """`hp_fighter_shield_special_2` -> `fighter 2`, `hp_gun_special_7` -> `7`.

    The class number is what decides whether your ship can carry the thing, and
    the prefix is noise on a gun (they are all `hp_gun` or `hp_turret`, which
    the turret flag already says) but load-bearing on a shield, where fighter,
    freighter and elite mounts are three different sockets.
    """
    if not raw:
        return ""
    parts = raw.replace("hp_", "", 1).split("_")
    number = parts[-1] if parts and parts[-1].isdigit() else ""
    words = [p for p in parts[:-1] if p not in ("special", "shield", "gun", "turret")]
    return " ".join(words + [number]).strip() or raw


def load_goods(game_dir, data_dir):
    """good nickname -> {equipment, price}, over every declared goods file."""
    out = {}
    for path in wr.declared_files(game_dir, data_dir, "goods"):
        for _section, pairs in wr.read_multi(path):
            entry = _entries(pairs)
            nick, gear = _first(entry, "nickname"), _first(entry, "equipment")
            if not nick or not gear:
                continue
            out[str(nick).lower()] = {
                "equipment": str(gear).lower(),
                "price": _num(entry, "price"),
            }
    return out


def load_market(game_dir, data_dir):
    """equipment nickname -> {price, rank, rep, bases: [base nickname]}.

    Rank and rep are taken from the first row seen and not merged, because they
    never differ between bases; see the module docstring.
    """
    goods = load_goods(game_dir, data_dir)
    market = fl.ipath(fl.ipath(data_dir, "EQUIPMENT"), "market_misc.ini")
    out = {}
    for section, pairs in wr.read_multi(market):
        if section.lower() != "basegood":
            continue
        entry = _entries(pairs)
        base = _first(entry, "base")
        if not base:
            continue
        base = str(base).lower()
        for values in entry.get("marketgood", []):
            good = goods.get(str(values[0]).lower())
            if not good or len(values) < 7:
                continue
            row = out.setdefault(good["equipment"], {
                "price": good["price"], "rank": None, "rep": None, "bases": []})
            row["bases"].append(base)
            if row["rank"] is None:
                try:
                    row["rank"] = int(float(values[1]))
                    row["rep"] = float(values[2])
                except (TypeError, ValueError):
                    pass
    return out


def load_shields(game_dir, data_dir, fittable_only=True):
    """Shield generators a ship can actually carry, with the stats a buyer compares.

    Two are dropped for want of an `hp_type` and three more for want of a
    `shield_type`, which is the same honest line `load_weapons` draws with
    `hp_gun_type`: a mount is what makes a thing something you can fit, and one
    of the three damage types is what makes it a shield rather than a fixture.

    Without it the list is led by two station shields called "Object Unknown"
    with a capacity of 1000000000 and a pair of million-point "Uber Shields",
    none of which is sold, mounts anywhere, or means anything to a player. All
    79 shields that are sold carry both fields, so nothing real is lost.
    """
    names = fl.load_names(game_dir)
    out = []
    for path in wr.declared_files(game_dir, data_dir, "equipment"):
        for section, pairs in wr.read_multi(path):
            if section.lower() != "shieldgenerator":
                continue
            entry = _entries(pairs)
            nick = _first(entry, "nickname")
            if not nick:
                continue
            if fittable_only and not (_first(entry, "hp_type")
                                      and _first(entry, "shield_type")):
                continue
            ids = _first(entry, "ids_name")
            try:
                label = names.get(int(ids), str(nick))
            except (TypeError, ValueError):
                label = str(nick)
            kind = str(_first(entry, "shield_type") or "")
            out.append({
                "nickname": str(nick),
                "name": label,
                "capacity": _num(entry, "max_capacity"),
                "regen": _num(entry, "regeneration_rate"),
                "drain": _num(entry, "constant_power_draw"),
                "rebuild": _num(entry, "offline_rebuild_time"),
                # `S_Graviton01` -> `Graviton`. The number is a data-file
                # suffix, not something the game ever shows a player.
                "shield_type": kind.replace("S_", "").rstrip("0123456789") or "",
                "mount": _mount_label(str(_first(entry, "hp_type") or "").lower()),
            })
    return out


def wreck_loot(game_dir):
    """item display name -> [(wreck name, system nickname)].

    The fallback for the 27 guns no dealer stocks. `wrecks.load_wrecks` already
    resolves a loadout to display names, so this is a regrouping, not a parse.
    """
    out = {}
    for wreck in wr.load_wrecks(game_dir):
        for item, _count in wreck["loot"]:
            out.setdefault(item, []).append((wreck["name"], wreck["system"]))
    return out


def load_catalogue(game_dir=None, obtainable_only=True):
    """{"guns": [...], "shields": [...]} with prices and places to buy.

    Every row carries its own stats, its price, its rank and reputation gates,
    and the bases selling it. A row with no bases and a `wrecks` list is one of
    the codenamed guns.

    **Only what a player can actually get.** An item qualifies by being sold at
    a dockable base or by sitting in a wreck, and that leaves 235 guns of 247
    and 79 shields of 121. Same argument the Trade tab settles with: a price you
    can never reach is not information.

    What it drops, checked rather than assumed. Of the 42 shields, 30 have an
    `npc_` nickname and **no `npc_` item is sold anywhere, ever**, guns included;
    the other 12 have no `[Good]` at all, so they carry no price and no dealer
    can stock them. Left in, they lead the list by capacity: the top four are
    `npc_shield01_mark10` and friends at 10127 points, while the best shield a
    player can buy is the Adv. Brigandine at 289150 credits. The 12 guns dropped
    are Death's Hand, Adv. Dissolver and Adv. Sunrail, which are mission and NPC
    weapons.

    The 17 codenamed guns, ARCHANGEL through SILVER FIRE, are kept precisely
    because they are in wrecks, and for them `wrecks` is the answer to "where".
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    data_dir = fl.ipath(game_dir, "DATA")
    strings = fl.load_names(game_dir)
    dockable, ref, sysname = mk.base_index(game_dir, data_dir, strings)
    market = load_market(game_dir, data_dir)
    loot = wreck_loot(game_dir)

    def sold_at(nick):
        seen, out = set(), []
        for base in market.get(nick, {}).get("bases", []):
            if base in seen or base not in dockable:
                continue
            seen.add(base)
            out.append(ref(base))
        out.sort(key=lambda b: (b["system"], b["name"]))
        return out

    def finish(row):
        nick = row["nickname"].lower()
        deal = market.get(nick, {})
        row["price"] = deal.get("price")
        row["rank"] = deal.get("rank") or 0
        row["rep"] = deal.get("rep")
        row["bases"] = sold_at(nick)
        # Only worth looking up when no dealer has it: a gun you can buy is not
        # made more findable by listing the wrecks that also hold one.
        row["wrecks"] = [] if row["bases"] else [
            {"name": w, "system": sysname.get(s, s)} for w, s in loot.get(row["name"], [])]
        return row

    def reachable(row):
        return bool(row["bases"] or row["wrecks"]) or not obtainable_only

    guns = []
    for gun in wp.load_weapons(game_dir):
        gun["rate"] = 1 / gun["refire"] if gun["refire"] else None
        gun["mount"] = _mount_label(gun["mount"])
        gun["kind"] = "turret" if gun["turret"] else "gun"
        # Rounded to the whole number the game itself shows, at the owner's
        # call: 600.0, 600.3 and 600.4 are three values in the files and one
        # answer to "which guns do 600". The column keeps the exact figure.
        gun["speed_group"] = round(gun["speed"]) if gun["speed"] else None
        if reachable(finish(gun)):
            guns.append(gun)

    shields = [s for s in (finish(s) for s in load_shields(game_dir, data_dir))
               if reachable(s)]
    return {"guns": guns, "shields": shields}


def choices(rows, key):
    """The values a `pick` parameter actually takes, in a sensible order."""
    seen = {str(r.get(key) or "") for r in rows} - {""}
    # "fighter 2" before "fighter 10": the trailing number is a class, and
    # sorting it as text puts 10 between 1 and 2.
    def order(value):
        head, _, tail = value.rpartition(" ")
        return (head, int(tail)) if tail.isdigit() else (value, 0)
    return sorted(seen, key=order)


def mount_class(value):
    """A mount label as `(family, class number)`. `("", 0)` if it says neither.

    A gun's mount is a bare class, `"6"`. A shield's carries the socket it fits,
    `"fighter 6"`, and **the socket is not decoration**: fighter, freighter and
    elite are three different mounts on the ship, so a class number only means
    something next to another number from the same family. That is why `<` and
    `>` compare within a family and never across one.
    """
    text = str(value or "").strip()
    if not text:
        return "", 0
    head, _, tail = text.rpartition(" ")
    if tail.isdigit():
        return head, int(tail)
    return text, 0


def systems(rows):
    """Every system with a dealer for one of these rows: nickname and label.

    **Keyed on the nickname, and the label is only printed.** Five display
    names in this game are worn by more than one system, so a selector keyed on
    what it shows would quietly pick the wrong one. `bases.ref` supplies both
    halves already, which is why nothing here has to look a system up.
    """
    seen = {}
    for row in rows:
        for base in row.get("bases") or ():
            # One base resolves to nothing at all: `st01_01_base`, in a story
            # system, with no display name and no system name. It carries 15
            # items, so skipping it here costs a blank entry in the picker and
            # nothing else. It is left in each row's own "where" list, which is
            # the place that can say the base exists but has no name.
            if base.get("sys") and base.get("system"):
                seen.setdefault(base["sys"], base["system"])
    return [{"key": nick, "label": label}
            for nick, label in sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))]


def search(rows, filters, order, descending=True, keep=None):
    """Rows passing every filter, in the order asked for.

    `filters` is [(key, kind, value)] and the kind says how to read it:

        num     a minimum
        pick    an exact match
        text    a case-insensitive substring of the item's name
        system  sold at a base in that system, by system nickname
        docked  sold at one of the bases in `value`, a set of base ids
        lt, gt  a mount class below or above the one named, within its family

    **Sorting is separate from filtering** and stays that way: adding a
    threshold narrows the list without reshuffling what you were reading, and
    the column headers are what change the order.

    `system` and `docked` are the two that reach into `bases` rather than
    reading a column, and both **drop** a row rather than emptying it. `docked`
    used to be the exception, applied in `backend/search.py` afterwards and
    written up at length here as the opposite of `system`: it rewrote `bases`
    and kept the row so the page could say "nowhere you have docked sells it".
    **That was reversed on 2026-09-10 at the owner's request**, because a
    filter that drops nothing is not a filter: it left 187 of the 235 guns on
    screen with no dealer under them, wreck loot included. It is one of the
    filters now, and it goes here so that one function still decides what is
    kept. `backend/search.py` still narrows each surviving row's `bases` to the
    docked ones, which is a different job and can no longer empty a row.

    `keep` is the set of nicknames that **bypass every filter**: the Equipment
    tab's favourites. It is checked before the filters rather than merged in
    afterwards so the sort below places them, which is what makes a favourite
    land in the ranking rather than in a pile on top of it.
    """
    keep = keep or ()
    out = []
    for row in rows:
        if row.get("nickname") in keep:
            out.append(row)
            continue
        keep_row = True
        for key, kind, value in filters:
            got = row.get(key)
            if kind == "num":
                if got is None or got < value:
                    keep_row = False
                    break
            elif kind == "text":
                if str(value).lower() not in str(got or "").lower():
                    keep_row = False
                    break
            elif kind == "system":
                if not any(b.get("sys") == value for b in row.get("bases") or ()):
                    keep_row = False
                    break
            elif kind == "docked":
                # A gun sold nowhere at all has no `bases`, so wreck loot goes
                # with this one. That is the second half of what was asked for.
                if not any(b.get("id") in value for b in row.get("bases") or ()):
                    keep_row = False
                    break
            elif kind in ("lt", "gt"):
                # Same family or nothing: "under fighter 6" has no opinion about
                # an elite mount, and answering as though it did would offer
                # shields the ship cannot take.
                family, want = mount_class(value)
                mine, have = mount_class(got)
                if mine != family or not want or not have:
                    keep_row = False
                    break
                if not (have < want if kind == "lt" else have > want):
                    keep_row = False
                    break
            elif str(got or "") != str(value):
                keep_row = False
                break
        if keep_row:
            out.append(row)

    def key(row):
        """None for a row with nothing in that column, else a number or text.

        `mount` holds "6" and "10" as text, so a numeric reading is tried
        first: sorted as words, class 10 lands between 1 and 2.
        """
        got = row.get(order)
        if got is None or got == "":
            return None
        try:
            return float(got)
        except (TypeError, ValueError):
            return str(got).lower()

    have = [r for r in out if key(r) is not None]
    # A gun with no price is not the cheapest gun. Missing values sit at the
    # end whichever way round the column is turned, never at the top.
    missing = [r for r in out if key(r) is None]
    have.sort(key=lambda r: r["name"])
    have.sort(key=key, reverse=descending)
    missing.sort(key=lambda r: r["name"])
    return have + missing


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--kind", default="guns", choices=sorted(PARAMETERS))
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--where", help="say where one item by name is sold")
    ap.add_argument("--system", help="only what is sold in this system, "
                                     "by nickname (li01) or by name (New York)")
    ap.add_argument("--name", help="only items whose name contains this")
    args = ap.parse_args()

    cat = load_catalogue(args.game)
    if args.where:
        want = args.where.strip().lower()
        for rows in cat.values():
            for row in rows:
                if want not in row["name"].lower():
                    continue
                price = int(row["price"]) if row["price"] else "?"
                rank = f", rank {row['rank']}" if row["rank"] else ""
                print(f"\n{row['name']}  {price} cr{rank}")
                for base in row["bases"]:
                    print(f"   {base['name']:<30}{base['at']:<8}{base['system']}")
                for wreck in row["wrecks"]:
                    print(f"   wreck: {wreck['name']:<23}{wreck['system']}")
                if not row["bases"] and not row["wrecks"]:
                    print("   sold nowhere and in no wreck")
        return

    rows = cat[args.kind]
    order = ORDER[args.kind]
    sold = sum(1 for r in rows if r["bases"])

    # The same filters the page sends, so this is a second opinion on the same
    # rule rather than a second implementation of it.
    picks = []
    if args.name:
        picks.append(("name", "text", args.name))
    if args.system:
        known = {s["key"]: s["label"] for s in systems(rows)}
        want = args.system.lower()
        if want not in known:
            # A name is what a person has to hand; the nickname is what the
            # filter needs. Ambiguous names are refused rather than guessed:
            # five labels in this game belong to more than one system.
            hits = [k for k, label in known.items() if label.lower() == want]
            if len(hits) != 1:
                found = ", ".join(sorted(known)) if not hits else ", ".join(hits)
                raise SystemExit(
                    f"no single system called {args.system!r}. Try one of: {found}")
            want = hits[0]
        picks.append(("system", "system", want))
        print(f"sold in {known[want]} ({want})")

    found = search(rows, picks, order)
    print(f"{len(found)} of {len(rows)} {args.kind}, {sold} sold somewhere\n")
    for row in found[:args.top]:
        price = f"{int(row['price']):>7}" if row["price"] else "      ?"
        print(f"{row['name'][:32]:<33}{row[order] or 0:>9.1f}{price} cr"
              f"   {len(row['bases'])} bases")

