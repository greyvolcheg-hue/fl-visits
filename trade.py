#!/usr/bin/env python3
"""Where a commodity is bought and sold, and for how much.

    trade.py --find gold
    trade.py --list

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
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docking as dk  # noqa: E402
import flvisits as fl  # noqa: E402
import wrecks as wr  # noqa: E402

SELLS_TO_YOU = 0  # the base has stock: this is where you buy


def _first(entry, key):
    """The first value of a key, already unwrapped. Do not index it again."""
    got = entry.get(key)
    return got[0] if got else None


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

    dockable = dk.dockable_bases(game_dir, data_dir, fl.system_files, fl.ipath)
    bases, systems = fl.load_universe(data_dir)
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
            system = where.get(key, "")
            rows.append({
                "base": key,
                "base_name": label.get(key, key),
                "system": sysname.get(system, system),
                "good": good,
                "good_name": names.get(good, good),
                "price": round(price[good] * mult),
                "buy": flag == SELLS_TO_YOU,
            })
    return names, rows


def find(rows, good, visited=None, only_visited=False):
    """Every base trading `good`, dearest first.

    Descending price puts the best place to sell at the top and the cheapest
    place to buy at the bottom, which is the same list read from either end.
    """
    out = [r for r in rows if r["good"] == good]
    if only_visited and visited is not None:
        out = [r for r in out if r["base"] in visited]
    if visited is not None:
        for row in out:
            row["visited"] = row["base"] in visited
    out.sort(key=lambda r: (-r["price"], r["base_name"]))
    return out


def sells(rows, base):
    """What `base` has on the shelf, dearest first.

    Only the flag-0 rows: a base with none of something cannot sell it to you,
    however much it is willing to pay.
    """
    out = [r for r in rows if r["base"] == base and r["buy"]]
    out.sort(key=lambda r: (-r["price"], r["good_name"]))
    return out


def deltas(rows, good, source, only=None):
    """Every other base trading `good`, by margin over `source`, biggest first.

    `source` is the row you would buy at, so `delta` is profit a unit. `only`
    narrows the destinations to a set of base nicknames when the player wants
    to stay on bases already docked at.

    Bases holding stock are not dropped. Freelancer lets you sell a commodity
    at any base whose market lists it, and one that also stocks it is a real
    destination, just usually a cheap one. Which end is which stays readable
    because the caller keeps the same colour rule as the Data view.
    """
    out = []
    for row in rows:
        if row["good"] != good or row["base"] == source["base"]:
            continue
        if only is not None and row["base"] not in only:
            continue
        out.append(dict(row, delta=row["price"] - source["price"]))
    out.sort(key=lambda r: (-r["delta"], r["base_name"]))
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
        found = deltas(by_good[src["good"]], src["good"], src, only)
        out.append({**src, "best": found[0] if found else None})
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
        found = find(rows, key)
        print(f"\n{names[key]} ({len(found)} bases)")
        for row in found:
            way = "buy " if row["buy"] else "sell"
            print(f"   {row['price']:>6} cr  {way}  {row['base_name'][:28]:<29} "
                  f"{row['system']}")


if __name__ == "__main__":
    main()
