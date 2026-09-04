#!/usr/bin/env python3
"""Buyable equipment, its stats, and where to get it.

    equipment.py --kind guns --top 10
    equipment.py --kind shields --top 10
    equipment.py --where "Adv. Ripper"

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flvisits as fl  # noqa: E402
import trade as td  # noqa: E402
import weapons as wp  # noqa: E402
import wrecks as wr  # noqa: E402

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
        ("mount", "mount class", "pick", ""),
        ("price", "price", "num", "cr"),
        ("rank", "rank needed", "num", ""),
    ],
    "shields": [
        ("capacity", "capacity", "num", ""),
        ("regen", "regeneration", "num", "/s"),
        ("drain", "constant drain", "num", ""),
        ("rebuild", "rebuild time", "num", "s"),
        ("shield_type", "type", "pick", ""),
        ("mount", "mount class", "pick", ""),
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
    dockable, where, label, sysname = td.base_index(game_dir, data_dir, strings)
    market = load_market(game_dir, data_dir)
    loot = wreck_loot(game_dir)

    def sold_at(nick):
        seen, out = set(), []
        for base in market.get(nick, {}).get("bases", []):
            if base in seen or base not in dockable:
                continue
            seen.add(base)
            system = where.get(base, "")
            out.append({"base": base, "base_name": label.get(base, base),
                        "system": sysname.get(system, system)})
        out.sort(key=lambda b: (b["system"], b["base_name"]))
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


def search(rows, filters, order, descending=True):
    """Rows passing every filter, in the order asked for.

    `filters` is [(key, kind, value)]. A "num" filter is a minimum, a "pick" is
    an exact match. **Sorting is separate from filtering** and stays that way:
    adding a threshold narrows the list without reshuffling what you were
    reading, and the column headers are what change the order.
    """
    out = []
    for row in rows:
        keep = True
        for key, kind, value in filters:
            got = row.get(key)
            if kind == "num":
                if got is None or got < value:
                    keep = False
                    break
            elif str(got or "") != str(value):
                keep = False
                break
        if keep:
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
                    print(f"   {base['base_name']:<30}{base['system']}")
                for wreck in row["wrecks"]:
                    print(f"   wreck: {wreck['name']:<23}{wreck['system']}")
                if not row["bases"] and not row["wrecks"]:
                    print("   sold nowhere and in no wreck")
        return

    rows = cat[args.kind]
    order = ORDER[args.kind]
    sold = sum(1 for r in rows if r["bases"])
    print(f"{len(rows)} {args.kind}, {sold} sold somewhere\n")
    for row in search(rows, [], order)[:args.top]:
        price = f"{int(row['price']):>7}" if row["price"] else "      ?"
        print(f"{row['name'][:32]:<33}{row[order] or 0:>9.1f}{price} cr"
              f"   {len(row['bases'])} bases")


if __name__ == "__main__":
    main()
