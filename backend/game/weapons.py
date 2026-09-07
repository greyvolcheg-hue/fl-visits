"""DPS of every gun in the game, worked out from its own stats.

    fl.py weapons [--top N] [--game DIR]

A gun's rate of fire is on the gun and its damage is on the munition that its
`projectile_archetype` names, so DPS needs both halves:

    hull DPS   = hull_damage / refire_delay
    shield DPS = (hull_damage * HULL_DAMAGE_FACTOR + energy_damage) / refire_delay

`HULL_DAMAGE_FACTOR` lives in `[ShieldEquipConsts]` of `constants.ini` and is
0.5 in vanilla. It is read from the file rather than written in here, because
this install already carries a modified `constants.ini` and a hardcoded 0.5
would drift away from the game the next time it is touched.

**Checked against the game's own dealer screens on 2026-09-02**, and both
halves of the sum are needed to fit. The game truncates for display:

    weapon           hull  energy  ->  computed   game says
    Adv. Starbeam    18.4     0        9.2        9
    Heavy Starbeam   22.4     0       11.2       11
    Stunpulse         4.6   153      155.3      155
    Adv. Stunpulse    5.6   186.8    189.6      189
    Adv. Skyrail    121.2     0       60.6       60

Two earlier readings are refuted by that table and must not come back. Shield
damage is not `energy_damage` alone: that gives 153 and 186 for the two
Stunpulses, against the 155 and 189 the game prints. Nor is it hull alone,
which gives 2.3 for a Stunpulse, a weapon sold as an anti-shield gun.

`energy_damage` is therefore part of shield damage and is not reported as a
column of its own. Note that the "Energy Usage" line on the dealer screen is a
different field again, `power_usage` on the gun, which is what a shot draws
from the ship: 9.18 for the Stunpulse, shown as 9. Confusing those two is what
produced the first wrong model here.

`weaponmoddb.ini` also carries a weapon-type against shield-type matrix, 21
types over Graviton, Molecular and Positron shields with multipliers of 0.8,
1.0 and 1.2. **It is deliberately not used.** A figure taken through it would
depend on what the target is flying, and the owner asked for the number that
follows from the weapon's own stats. Do not add it back.
"""

import argparse
import os
import sys

from . import flvisits as fl
from . import wrecks as wr

VANILLA_SHIELD_FACTOR = 0.5  # only the fallback; the file is the authority


def shield_factor(data_dir):
    """`HULL_DAMAGE_FACTOR`, the share of hull damage a shield takes."""
    try:
        for section, entries in wr.read_multi(fl.ipath(data_dir, "constants.ini")):
            if section.lower() != "shieldequipconsts":
                continue
            for key, values in entries:
                if key.upper() == "HULL_DAMAGE_FACTOR" and values:
                    return float(values[0])
    except (OSError, TypeError, ValueError):
        pass
    return VANILLA_SHIELD_FACTOR


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
    factor = shield_factor(data_dir)

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
        shield = hull * factor + energy

        # The Equipment search needs these; the DPS tab ignores them. They come
        # out of entries this loop has already built, which is why they are read
        # here rather than by a second gun parser somewhere else.
        def num(source, key):
            try:
                return float(_first(source, key))
            except (TypeError, ValueError):
                return None

        speed, life = num(entry, "muzzle_velocity"), num(shot, "lifetime")
        out.append({
            "nickname": str(nick),
            "name": label,
            "turret": str(mount or "").lower().startswith("hp_turret"),
            "hull": hull,
            "shield": shield,
            "refire": refire,
            "hull_dps": hull / refire,
            "shield_dps": shield / refire,
            "speed": speed,
            # Range is what a player actually compares, and neither field is it
            # on its own: the shot lives for `lifetime` seconds and covers
            # `muzzle_velocity` metres in each of them.
            "range": speed * life if speed and life else None,
            "power": num(entry, "power_usage"),
            "mount": str(mount or "").lower(),
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
    print(f"{len(weapons)} guns, shield factor {shield_factor(fl.ipath(args.game, 'DATA'))}\n")
    print(f"{'weapon':<34}{'hull':>9}{'shield':>9}{'refire':>9}")
    for w in rows:
        print(f"{w['name'][:33]:<34}{w['hull_dps']:>9.1f}{w['shield_dps']:>9.1f}"
              f"{w['refire']:>9.2f}")

