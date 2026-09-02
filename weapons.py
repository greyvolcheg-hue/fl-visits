#!/usr/bin/env python3
"""DPS of every gun in the game, worked out from its own stats.

    weapons.py [--top N] [--game DIR]

A gun's rate of fire is on the gun and its damage is on the munition that its
`projectile_archetype` names, so DPS needs both halves:

    hull DPS   = hull_damage   / refire_delay
    shield DPS = energy_damage / refire_delay

Those two are not a redundant pair, they are the split the game itself makes. A
laser reads hull 19.6 and energy 0; a pulse gun reads hull 10.1 and energy 303,
which is what makes pulse weapons the anti-shield ones.

`weaponmoddb.ini` also carries a weapon-type against shield-type matrix, 21
types over Graviton, Molecular and Positron shields with multipliers of 0.8,
1.0 and 1.2. **It is deliberately not used.** A figure taken through it would
depend on what the target is flying, and the owner asked for the number that
follows from the weapon's own stats. Do not add it back.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flvisits as fl  # noqa: E402
import wrecks as wr  # noqa: E402


def _entries(pairs):
    """Lower-cased key -> list of value-lists, keeping repeats."""
    out = {}
    for key, values in pairs:
        out.setdefault(key.lower(), []).append(values)
    return out


def _first(entry, key):
    got = entry.get(key)
    return got[0][0] if got else None


def load_weapons(game_dir, mountable_only=True):
    """Every gun that fires a damaging projectile, with its DPS worked out.

    Two things are filtered out, both for the same reason: including them would
    put a number on the page that means nothing to a player.

    Guns whose munition carries a `seeker` are dropped. Missiles, torpedoes and
    mines do their damage through an explosion archetype rather than through
    `hull_damage`, so a DPS taken from the munition would read as zero and
    quietly understate them. Better absent than wrong.

    Guns with no `hp_gun_type` are dropped too, which is 190 of the 437. Those
    are the fixtures bolted to stations and capital ships, and they are also
    where the confusing name collisions live: five different guns are called
    "Battleship Defense Turret", from 81.6 to 1060 hull DPS. A hardpoint type is
    what makes a gun something a ship can carry, so it is the honest line
    between "a weapon you might fit" and "scenery that shoots back".
    """
    data_dir = fl.ipath(game_dir, "DATA")
    names = fl.load_names(game_dir)

    munitions, guns = {}, []
    for path in wr.declared_files(game_dir, data_dir, "equipment"):
        for section, pairs in wr.read_multi(path):
            name = section.lower()
            if name == "munition":
                entry = _entries(pairs)
                nick = _first(entry, "nickname")
                if nick:
                    munitions[str(nick).lower()] = entry
            elif name == "gun":
                guns.append(_entries(pairs))

    out = []
    for entry in guns:
        nick = _first(entry, "nickname")
        arch = _first(entry, "projectile_archetype")
        if not nick or not arch:
            continue
        shot = munitions.get(str(arch).lower())
        if not shot or "hull_damage" not in shot or "seeker" in shot:
            continue
        mount = _first(entry, "hp_gun_type")
        if mountable_only and not mount:
            continue
        try:
            refire = float(_first(entry, "refire_delay"))
            hull = float(_first(shot, "hull_damage"))
            energy = float(_first(shot, "energy_damage"))
        except (TypeError, ValueError):
            continue
        if refire <= 0:
            continue
        ids = _first(entry, "ids_name")
        try:
            label = names.get(int(ids), str(nick))
        except (TypeError, ValueError):
            label = str(nick)
        out.append({
            "nickname": str(nick),
            "name": label,
            "turret": str(mount or "").lower().startswith("hp_turret"),
            "hull": hull,
            "energy": energy,
            "refire": refire,
            "hull_dps": hull / refire,
            "shield_dps": energy / refire,
        })
    out.sort(key=lambda w: w["name"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--top", type=int, help="show the N hardest hitting instead of all")
    args = ap.parse_args()

    weapons = load_weapons(args.game)
    rows = weapons
    if args.top:
        rows = sorted(weapons, key=lambda w: -w["hull_dps"])[:args.top]
    print(f"{len(weapons)} guns\n")
    print(f"{'weapon':<34}{'hull':>9}{'shield':>9}{'refire':>9}")
    for w in rows:
        print(f"{w['name'][:33]:<34}{w['hull_dps']:>9.1f}{w['shield_dps']:>9.1f}"
              f"{w['refire']:>9.2f}")


if __name__ == "__main__":
    main()
