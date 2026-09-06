#!/usr/bin/env python3
"""What a new game starts you with: the ship and what is bolted to it.

    newgame.py              # what a new game currently gives you
    newgame.py --apply      # write the loadout below
    newgame.py --restore    # back to the .vanilla copies

**`EXE/newplayer.fl` is not where the starting ship comes from**, however much
it looks like it. The file says so itself, in its own comment:

    ; Debug Ship - gets replaced if missions active

Single player always starts M01, so the ship comes from one trigger in
`DATA/MISSIONS/M01A/m01a.ini`:

    Act_SetShipAndLoadout = ge_fighter, msn_playerloadout

and `msn_playerloadout` is a `[Loadout]` in `DATA/SHIPS/loadouts.ini`. Those
two files are what this module writes; `newplayer.fl` is deliberately left
alone, because writing a file the game overwrites is noise that later reads as
a second, disagreeing source of truth.

`msn_playerloadout` is safe to edit in place: that trigger is its only user in
the game. The near-identical `msn_playerloadout_faux` belongs to the `fauxplayer`
NPC and is a separate section.

**The gun placement is forced by the data, not chosen.** A Sabre takes class 10
on `HpWeapon01` to `04` and caps at class 9 on `05` and `06`. Nomad guns are
class 10 and the Salamanca Mk II is class 9, so four Nomads forward and two
Salamancas outboard is the only arrangement that mounts at all.
"""

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import bini  # noqa: E402
import flvisits as fl  # noqa: E402

LOADOUT = "msn_playerloadout"
TRIGGER = "act_setshipandloadout"
SHIP = "bw_elite2"  # Sabre

# The Sabre's own hull kit, taken from its `bwe2_package` in goods.ini. The
# ge_fighter parts a new game ships with do not fit it.
EQUIP = [
    ("ge_bwe2_engine_01",),
    ("bw_elite2_power01",),
    ("shield01_mark07_hf", "HpShield01"),
    ("ge_s_scanner_01",),
    ("ge_s_tractor_01",),
    ("ge_s_thruster_01", "HpThruster01"),
] + [("special_nomad_gun01", f"HpWeapon0{n}") for n in (1, 2, 3, 4)] \
  + [("fc_c_gun01_mark05", f"HpWeapon0{n}") for n in (5, 6)] \
  + [("LargeWhiteSpecial", "HpHeadlight")] \
  + [("SlowSmallWhite", f"HpRunningLight0{n}") for n in range(1, 9)] \
  + [("contrail01", f"HpContrail0{n}") for n in range(1, 5)] \
  + [("DockingLightRedSmall", f"HpDockLight0{n}") for n in (1, 2)]

CARGO = [("ge_s_battery_01", 3), ("ge_s_repair_01", 3)]


class WriteFailed(Exception):
    pass


def _paths(game_dir=None):
    data = fl.ipath(game_dir or fl.DEFAULT_GAME, "DATA")
    return (fl.ipath(data, "SHIPS", "loadouts.ini"),
            fl.ipath(data, "MISSIONS", "M01A", "m01a.ini"))


def _read(path):
    """Sections from the pristine copy if one was kept, else from the file."""
    keep = path + ".vanilla"
    return bini.decode(open(keep if os.path.exists(keep) else path, "rb").read())


def _write(path, sections):
    """Keep a pristine copy the first time, then write. Same shape as drawdist."""
    keep = path + ".vanilla"
    if not os.path.exists(keep):
        shutil.copy2(path, keep)
    blob = bini.encode(sections)
    if bini.decode(blob) != sections:
        raise WriteFailed(f"{os.path.basename(path)} would not round-trip")
    open(path, "wb").write(blob)


def _loadout(sections):
    """The [Loadout] entries for msn_playerloadout, or None."""
    for name, entries in sections:
        if name.lower() != "loadout":
            continue
        for key, values in entries:
            if key.lower() == "nickname" and str(values[0]).lower() == LOADOUT:
                return entries
    return None


def _triggers(sections):
    """Every (entries, index) where the mission sets the player's ship."""
    out = []
    for _name, entries in sections:
        for i, (key, values) in enumerate(entries):
            if key.lower() == TRIGGER and str(values[0]).lower() != "none":
                out.append((entries, i))
    return out


def state(game_dir=None):
    """(ship archetype, [(item, hardpoint)]) a new game currently gives you."""
    loadouts, mission = _paths(game_dir)
    ship = None
    for entries, i in _triggers(bini.decode(open(mission, "rb").read())):
        ship = str(entries[i][1][0])
    entries = _loadout(bini.decode(open(loadouts, "rb").read())) or []
    gear = [(str(v[0]), str(v[1]) if len(v) > 1 else "")
            for k, v in entries if k.lower() == "equip"]
    return ship, gear


def apply(game_dir=None):
    """Put SHIP and EQUIP into the mission trigger and the loadout."""
    loadouts, mission = _paths(game_dir)

    sections = _read(loadouts)
    entries = _loadout(sections)
    if entries is None:
        raise WriteFailed(f"no [Loadout] named {LOADOUT} in loadouts.ini")
    # Rebuilt rather than patched: the vanilla list is a different ship's, so
    # every line in it is either replaced or wrong.
    entries[:] = ([("nickname", [LOADOUT]), ("archetype", [SHIP])]
                  + [("equip", list(e)) for e in EQUIP]
                  + [("cargo", [n, c]) for n, c in CARGO])
    _write(loadouts, sections)

    sections = _read(mission)
    found = _triggers(sections)
    if not found:
        raise WriteFailed(f"no {TRIGGER} in m01a.ini")
    for entries, i in found:
        key, values = entries[i]
        entries[i] = (key, [SHIP] + list(values[1:]))
    _write(mission, sections)
    return len(found)


def restore(game_dir=None):
    """Put both files back from their .vanilla copies."""
    back = 0
    for path in _paths(game_dir):
        keep = path + ".vanilla"
        if os.path.exists(keep):
            shutil.copy2(keep, path)
            back += 1
    return back


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--apply", action="store_true", help="write the loadout")
    ap.add_argument("--restore", action="store_true", help="undo, from .vanilla")
    args = ap.parse_args()

    if args.restore:
        print(f"restored {restore(args.game)} file(s)")
    elif args.apply:
        print(f"patched {apply(args.game)} trigger(s) and the loadout")

    ship, gear = state(args.game)
    print(f"\na new game starts you in: {ship}")
    for item, hp in gear:
        print(f"   {item:<24} {hp}")


if __name__ == "__main__":
    main()
