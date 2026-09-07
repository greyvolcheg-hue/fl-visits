"""Freelancer wreck ("secret") data and how much of it a save has found.

    fl.py wrecks <save.fl> [--game DIR] [--loot]

A wreck is a space object the game marks with `visit = 16` and gives a
`SECRET_*` loadout. Finding one writes a `visit` record against that object,
the same mechanism the base tracker already uses, so "found" is simply
"the object's hash is in the save".

Kept separate from flvisits.py, which is frozen (see CLAUDE.md). It also needs
something that module cannot give it: a loadout lists its contents as repeated
`equip` and `cargo` keys, and `flvisits.read_ini` collapses repeats into one
value. `read_multi` below keeps them.
"""

import argparse
import os
import sys
from collections import Counter, defaultdict

import bini

from . import bases
from . import flvisits as fl

SECRET_VISIT = 16  # the game's own marker for "this is a discoverable secret"
LOOTED = 8  # set once the loot is taken; a found but untouched wreck reads 17


def read_multi(path):
    """[(section, [(key, values), ...])] with repeated keys preserved."""
    blob = open(path, "rb").read()
    if blob[:4] == b"BINI":
        return bini.decode(blob)
    out, section, pairs = [], None, []
    for raw in blob.decode("latin-1").splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if section is not None:
                out.append((section, pairs))
            section, pairs = line[1:-1], []
        elif "=" in line and section is not None:
            key, value = line.split("=", 1)
            pairs.append((key.strip(), [p.strip() for p in value.split(",")]))
    if section is not None:
        out.append((section, pairs))
    return out


def declared_files(game_dir, data_dir, key):
    """Paths freelancer.ini lists under a repeated key such as `equipment`."""
    ini = fl.ipath(fl.ipath(game_dir, "EXE"), "freelancer.ini")
    out = []
    for raw in open(ini, encoding="latin-1"):
        line = raw.split(";", 1)[0].strip()
        if "=" not in line:
            continue
        name, value = (p.strip() for p in line.split("=", 1))
        if name.lower() != key:
            continue
        path = data_dir
        for part in value.replace("\\", "/").split("/"):
            path = fl.ipath(path, part)
        if os.path.exists(path):
            out.append(path)
    return out


def load_item_names(game_dir, data_dir, names):
    """equipment nickname (lower) -> display name, for loot lists."""
    out = {}
    for path in declared_files(game_dir, data_dir, "equipment"):
        for _, pairs in read_multi(path):
            entry = dict(pairs)
            nick, ids = entry.get("nickname"), entry.get("ids_name")
            if not nick:
                continue
            key = str(nick[0]).lower()
            try:
                # None on purpose when the item has no display name: those are
                # fittings like cargopod_red that the game never shows anyone,
                # so they are not loot and get dropped from the lists.
                out[key] = names.get(int(ids[0])) if ids else None
            except (TypeError, ValueError):
                out[key] = None
    return out


def load_loadouts(game_dir, data_dir, item_names):
    """loadout nickname (lower) -> [(display name, count)], commonest first."""
    out = {}
    for path in declared_files(game_dir, data_dir, "loadouts"):
        for section, pairs in read_multi(path):
            if section.lower() != "loadout":
                continue
            entry = dict(pairs)
            nick = entry.get("nickname")
            if not nick:
                continue
            tally = Counter()
            for key, values in pairs:
                if not values:
                    continue
                label = item_names.get(str(values[0]).lower())
                if not label:
                    continue
                if key.lower() == "equip":
                    tally[label] += 1
                elif key.lower() == "cargo":
                    try:
                        qty = int(values[1]) if len(values) > 1 else 1
                    except (TypeError, ValueError):
                        qty = 1
                    tally[label] += qty
            out[str(nick[0]).lower()] = tally.most_common()
    return out


def load_wrecks(game_dir):
    """Every secret object in a declared system, with its loot resolved."""
    data_dir = fl.ipath(game_dir, "DATA")
    names = fl.load_names(game_dir)
    item_names = load_item_names(game_dir, data_dir, names)
    loadouts = load_loadouts(game_dir, data_dir, item_names)
    scales = bases.load_scales(data_dir, fl.read_ini, fl.ipath)

    out = []
    for path, system in fl.system_files(data_dir):
        for section, pairs in read_multi(path):
            if section.lower() != "object":
                continue
            entry = dict(pairs)
            visit = entry.get("visit", [None])[0]
            loadout = str(entry.get("loadout", [""])[0])
            if str(visit) != str(SECRET_VISIT) and not loadout.upper().startswith("SECRET"):
                continue
            nick = str(entry.get("nickname", [""])[0])
            ids = entry.get("ids_name", [0])[0]
            try:
                label = names.get(int(ids), nick)
            except (TypeError, ValueError):
                label = nick
            pos = entry.get("pos")
            cell = spot = None
            if pos and len(pos) >= 3:
                try:
                    x, z = float(pos[0]), float(pos[2])
                except (TypeError, ValueError):
                    x = z = None
                if x is not None:
                    scale = scales.get(system, 1.0)
                    cell = bases.sector(x, z, scale)
                    spot = bases.subcell(x, z, scale)
            out.append({
                "system": system,
                "nickname": nick,
                "name": label,
                "sector": cell,
                "spot": spot,
                "loot": [[item, n] for item, n in loadouts.get(loadout.lower(), [])],
            })
    return out


def group_by_system(wrecks, visits, system_label):
    """Split every wreck into found / missing, grouped and sorted like bases.

    Three objects can share a display name (New York's Patrol 27 is three
    separate hulls), and they are counted separately on purpose: each is its
    own find.
    """
    rows = defaultdict(lambda: {"found": [], "missing": []})
    for wreck in wrecks:
        hid = fl.fl_hash(wreck["nickname"])
        flag = visits.get(hid)
        entry = {"name": wreck["name"], "sector": wreck["sector"],
                 "spot": wreck["spot"], "loot": wreck["loot"],
                 # Bit 8 is the game's own record of the loot having been taken.
                 #
                 # 54 of the 157 wrecks carry nothing, which is the game's own
                 # design and not a gap in the reader. The game never sets bit 8
                 # on those, because there was never anything to take, so they
                 # sat in the report forever as found-but-not-stripped and the
                 # count could not reach 157 however thoroughly they were
                 # searched. Finding an empty wreck *is* emptying it: there is
                 # no second visit that would ever change anything.
                 "emptied": bool(flag is not None
                                 and (flag & LOOTED or not wreck["loot"]))}
        rows[wreck["system"]]["found" if flag is not None else "missing"].append(entry)

    out = []
    for system, row in rows.items():
        for bucket in ("found", "missing"):
            row[bucket].sort(key=lambda e: (e["sector"] or "", e["name"]))
        # The raw nickname survives beside the label: the house a system belongs
        # to is its nickname's prefix, and "New York" does not carry it.
        row["nickname"] = system
        row["system"] = system_label(system)
        row["total"] = len(row["found"]) + len(row["missing"])
        # Only an emptied wreck counts towards progress, the same way only a
        # base you docked at counts on the Visits tab. A wreck you found and
        # left loaded is the wreck equivalent of a base the story revealed:
        # on the map, not yet done.
        row["stripped"] = sum(1 for e in row["found"] if e["emptied"])
        row["found_open"] = len(row["found"]) - row["stripped"]
        row["percent"] = round(100 * row["stripped"] / row["total"]) if row["total"] else 0
        out.append(row)
    # Deliberately not the Visits order. That tab is a to-do list and sorts by
    # how few bases are left; this one is a record of what has been found, so
    # the fullest systems lead and the empty ones trail. Asked for explicitly.
    out.sort(key=lambda r: (-r["percent"], -r["stripped"], r["system"]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--loot", action="store_true", help="list what each wreck holds")
    ap.add_argument("--all", action="store_true", help="include systems with nothing found")
    args = ap.parse_args()

    data_dir = fl.ipath(args.game, "DATA")
    _, systems = fl.load_universe(data_dir)
    names = fl.load_names(args.game)
    system_ids = {nick.lower(): ids for nick, ids in systems.items()}

    def label(system):
        try:
            return names.get(int(system_ids.get(system, 0)), system)
        except (TypeError, ValueError):
            return system

    wrecks = load_wrecks(args.game)
    visits = fl.parse_visits(fl.decode_save(args.save))
    rows = group_by_system(wrecks, visits, label)

    stripped = sum(r["stripped"] for r in rows)
    still_open = sum(r["found_open"] for r in rows)
    print(f"Stripped {stripped} of {len(wrecks)} wrecks "
          f"across {len([r for r in rows if r['stripped']])} of {len(rows)} systems")
    if still_open:
        print(f"{still_open} more found but still loaded (marked *), not counted above")
    print()
    for row in rows:
        if not row["found"] and not args.all:
            continue
        print(f"{row['system']:<22} {row['stripped']}/{row['total']}")
        for bucket in ("found", "missing"):
            if bucket == "missing" and not args.all:
                continue
            for entry in row[bucket]:
                if bucket == "missing":
                    mark = "-"
                else:
                    mark = "+" if entry["emptied"] else "*"
                loot = ""
                if args.loot and entry["loot"]:
                    loot = "   " + ", ".join(f"{n}x {i}" for i, n in entry["loot"])
                where = f"{entry['sector'] or '??'} {entry['spot'] or '':<2}"
                print(f"  {mark} {where}  {entry['name']}{loot}")

