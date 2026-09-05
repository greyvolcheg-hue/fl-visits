#!/usr/bin/env python3
"""How close you get to a dock before the game cuts your cruise engine.

    dockdist.py             # what the running game is using
    dockdist.py 8000        # set it
    dockdist.py --vanilla   # back to 1750

**This is a proof of concept, not a settled setting.** Read the last section
before writing it up as a fix.

## Why this file exists

The symptom was overshooting trade lanes at a raised cruise speed. The obvious
suspect was `[TradeLane] basic_trade_lane_eq` in `DATA/EQUIPMENT/select_equip.ini`,
whose `activation_start` / `activation_end` are the only two distances anywhere
in the game's data with a trade lane's name on them. They were changed from
750/500 to 100/50 by hand on 2026-09-04 and nothing happened in flight.

Nothing happened because those two belong to the ring, not to the ship. They are
the ring's own equipment and govern its spin-up window. No value of them reaches
the player's engine state, so no value of them could have worked.

The distance that does is not in the game's data at all. A sweep of all 1252 INI
files under `DATA/` for any key containing `dock` finds `docking_sphere`,
`dock_with`, the mission scripts' `act_lockdock`, and no global distance of any
kind. `Trade_Lane_Ring` in `solararch.ini` carries no `docking_sphere` at all,
where a jump gate carries 225 and a jump hole 150.

It is a float inside `common.dll`:

    0x62fe16d  d9 44 24 1c      fld    dword [esp+1c]     ; distance to the dock
    0x62fe171  d8 1d c0223a06   fcomp  dword [0x63a22c0]  ; against 1750.0
    0x62fe177  df e0            fnstsw ax
    0x62fe179  f6 c4 41         test   ah, 41

Verified on 2026-09-05 both in the shipped file and in the running game: v1.0
loaded at its preferred base, and `0x63a22c0` reading exactly 1750.0.

The addresses come from **flhack** (Jason Hood, 2014), which has this as the
"Cruise to dock from" setting, and its own default table calls the constant
"activate cruise for docking from this". Its help adds that the proximity radius
default of 495 "is that used by Trade Lanes", which is what ties a lane entry to
this same dock approach path.

## The arithmetic that matches the symptom

1750 m is 5.8 seconds of approach at the vanilla cruise speed of 300. At 2500 it
is 0.7 seconds. The threshold never moved; the speed crossing it went up eight
times over.

## Two things this does not claim

**The direction is a hypothesis.** flhack documents this float as the threshold
separating "thrust to the dock" from "cruise to the dock", so raising it should
cut cruise further out and leave room to slow down. Whether that is what a lane
approach actually does has to be flown to be known. Do not record it as a fix
until it has been.

**The constant is used four times, not once.** Besides the `fcomp` above, three
`fmul dword [0x63a22c0]` sites sit 1250 bytes earlier in the same function.
Changing it may move more than the cut point, and the way to find out is to fly
it and watch, not to reason about it here.

Memory only, like `tradelane.py`, which already writes to this same read-only
section of this same DLL through `/proc/<pid>/mem`. No file is touched and the
game goes back to 1750 on its next launch, which is what makes this cheap to
experiment with.
"""

import argparse
import struct
import sys

import speed as sp
import tradelane as tl
from speed import NotRunning

# flhack's ADDR_DOCK_DIST, relative to the same `common.dll` base tradelane.py
# uses. Which of the two builds is running is decided by tradelane.locate, so
# there is one copy of that check rather than two that can disagree.
DIST = {10: 0x63A22C0, 11: 0x63A22F0}

VANILLA = 1750.0
# Below 100 the approach has no room at any speed; above 20000 the cut would
# happen most of a sector away. Both ends are judgement, not measurement, and
# the point of the range is to catch a wrong address rather than a bold value.
SANE = (100.0, 20000.0)

VANILLA_CRUISE = 300.0  # what constants.ini ships, for the seconds comparison


def locate(pid):
    """(address of the dock cruise distance, common.dll version).

    The version comes from tradelane.locate, which follows a pointer at a
    fixed check site and so works for either build. Reading the float here is
    the second half of the same self-validation: in this build the v1.1 address
    holds 1.5e-13, so picking the wrong one is caught rather than written to.
    """
    _speed_addr, version = tl.locate(pid)
    addr = DIST[version] - tl.COMMON_BASE + tl._base(pid, "common.dll")
    with open(f"/proc/{pid}/mem", "rb") as fh:
        fh.seek(addr)
        value = struct.unpack("<f", fh.read(4))[0]
    low, high = SANE
    if not low <= value <= high:
        raise NotRunning(
            f"common.dll v{version} found, but the value at {addr:#x} is "
            f"{value!r}, not a distance; refusing to guess")
    return addr, version


def read(pid=None):
    """(distance, version) for the running game."""
    pid = pid or sp.find_pid()
    addr, version = locate(pid)
    with open(f"/proc/{pid}/mem", "rb") as fh:
        fh.seek(addr)
        return struct.unpack("<f", fh.read(4))[0], version


def set_dist(value, pid=None):
    """Set the distance, read it back, and confirm."""
    low, high = SANE
    if not low <= value <= high:
        raise ValueError(f"{value:g} is outside {low:g} to {high:g}")
    pid = pid or sp.find_pid()
    addr, _version = locate(pid)
    with open(f"/proc/{pid}/mem", "r+b") as fh:
        fh.seek(addr)
        fh.write(struct.pack("<f", float(value)))
        fh.seek(addr)
        got = struct.unpack("<f", fh.read(4))[0]
    if abs(got - value) > 0.5:
        raise NotRunning(f"wrote {value:g} but read back {got:g}")
    return got


def cruise_speed(pid):
    """The live cruise speed, or None if it cannot be read.

    None rather than the vanilla 300: the whole point of the seconds figure is
    that the speed has been raised, so guessing it would print exactly the
    reassurance the reader came to check.
    """
    try:
        return sp.read(pid, sp.locate(pid))
    except (NotRunning, OSError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("distance", nargs="?", type=float,
                    help="new dock cruise distance, in metres")
    ap.add_argument("--vanilla", action="store_true",
                    help=f"back to {VANILLA:g}")
    args = ap.parse_args()

    try:
        pid = sp.find_pid()
        if args.vanilla:
            args.distance = VANILLA
        if args.distance is not None:
            print(f"dock cruise distance now {set_dist(args.distance, pid):g}")

        value, version = read(pid)
        print(f"common.dll v{version}, dock cruise distance {value:g} "
              f"(vanilla {VANILLA:g})")

        cruise = cruise_speed(pid)
        if cruise is None:
            print("cruise speed unreadable, so no timing to show")
            return
        # What the number buys you, which is the figure the setting is really
        # about: metres are meaningless without the speed crossing them.
        print(f"cruise speed {cruise:g}, so that is "
              f"{value / cruise:.2f}s of approach before the cut")
        print(f"vanilla gave {VANILLA / VANILLA_CRUISE:.2f}s at cruise "
              f"{VANILLA_CRUISE:g}; the same at {cruise:g} would need "
              f"{VANILLA / VANILLA_CRUISE * cruise:.0f}")
    except (NotRunning, ValueError, OSError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
