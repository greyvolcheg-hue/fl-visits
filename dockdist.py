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

## It is measured from the object's centre, not from where the HUD counts

**This is the part that made three hours of testing read as noise.** flhack says
it outright and it is easy to skim past:

    It is the "physical" distance, different to what is displayed. The
    "Proximity" setting controls the difference between the physical and
    displayed distances - the default value is that used by Trade Lanes.

Its calculator dialog fills that Proximity field in with **495**, so for a trade
lane:

    physical = displayed + 495

Which decodes every result we got. Vanilla 1750 physical is 1255 on the HUD, so
that is where stock Freelancer drops cruise, and at cruise 2500 you cross it in
half a second and sail past the ring. A test value of 6000 means the flag says
"do not cruise" for anything closer than 5505 displayed, which is why pressing
dock at 4000 refused to light the cruise engines at all. And 100 is below the
~495 physical you have at the ring itself, so the flag can never flip and cruise
would never cut.

**To pick a value: take the distance you want on the HUD and add 495.** 100 m
displayed is 595. A jump gate has its own radius, so the same number lands
somewhere else there.

## What the compare actually is

    [esi+0x364] = (distance > DOCK_DIST)     ; 1 = use cruise

That direction is the whole thing, and getting it backwards is what sent the
early testing into the weeds. Larger DOCK_DIST does **not** mean "cruise for
longer", it means "refuse to cruise until you are further away".

The surrounding code, which is still worth knowing:

    62fe163  mov  al, [esi+0x365]
    62fe169  test al, al
    62fe16b  je   0x62fe194          ; flag clear -> skip the compare entirely
    62fe16d  fld  dword [esp+0x1c]
    62fe171  fcomp dword [0x63a22c0] ; 1750.0
    62fe177  df e0  fnstsw ax
    ...
    62fe187  mov  [esi+0x364], al    ; cache the answer
    62fe18d  mov  byte [esi+0x365], 0 ; clear the trigger

`[esi+0x365]` gates the compare and is cleared right after it, so the answer is
latched rather than recomputed every frame. Whether the game re-arms that
trigger as you close in is the one thing still open, and it decides whether this
single number gives both halves of what a player wants (cruise on from far away,
cruise off at 100 m) or only the first half. The observable difference: if
cruise cuts at your chosen distance, it re-arms; if it cuts somewhere else, it
does not, and the cut belongs to flhack's `_cruise_on` instead -- which it
installs at 0x62fe177, adding `cmp byte [esi+0x368], 0 / jnz .cruise`, "cruise
already active? leave it on", bypassing the test rather than moving it. That is
a code injection and out of reach of a four-byte write.

## APPROACH, the candidate that replaces it

The arrival threshold is a different value in the same function, at 0x62fe758:

    62fe758  d9 45 50   fld dword [ebp+0x50]
    62fe75b  8d 73 2c   lea esi, [ebx+0x2c]
    62fe766  d9 9b 58 03 00 00   fstp dword [ebx+0x358]

flhack's "Closer docking" replaces those six bytes with a stub that tests the
loaded value for 1000.0 and swaps in 200.0 for a non-station dock or 600.0 for a
station, described in its own help as "initiates docking from a much closer
distance, **allowing you to cruise or thrust for longer**". That sentence is the
whole lead: this is the distance at which the docking manoeuvre begins, so it is
the distance at which the cruise engine stops mattering.

flhack had to patch code because `[ebp+0x50]` is a descriptor field, not a
global. `APPROACH` above is the global that field is initialised from, which is a
four-byte write instead of a code injection.

**The link between `[esi+0x46c]` and `[ebp+0x50]` is inferred, not proven.** They
are different structures at different offsets and the only evidence tying them
together is that 1000.0 is the value at both ends and there is exactly one
referenced 1000.0 in the file. Flying it is the test.

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

# The second constant, and the one that is probably the interesting one. See
# "What DIST actually does" below. **Not from flhack**, which patches code here
# instead of naming an address, so only the v1.0 address is known and v1.1 must
# refuse rather than guess. Found by taking the 1000.0 that flhack's
# `_closer_docking` intercepts and looking for where it comes from: exactly one
# referenced 1000.0 in `.rdata`, loaded by three sites that all do
#
#     mov ecx, ds:0x639f44c
#     mov [esi+0x46c], ecx
#
# and it sits in the same constant block as the trade lane speed.
APPROACH = {10: 0x639F44C}
APPROACH_VANILLA = 1000.0
# The floor is deliberately far below anything sensible. This constant is being
# probed rather than configured, and a bound that refuses the experiment is a
# bound that hides the answer; 10 is low enough to be obviously absurd in play,
# which is the point of trying it.
APPROACH_SANE = (10.0, 30000.0)

VANILLA = 1750.0
# flhack's "Proximity": the gap between the physical distance this constant is
# measured in and the distance the HUD counts down. Its own dialog defaults the
# field to 495 and says that default is the trade lane's. So a value here of
# `x` cuts cruise at `x - 495` on the HUD, and a jump gate, with its own radius,
# lands somewhere else.
PROXIMITY = 495.0
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


def locate_approach(pid):
    """(address of the docking approach distance, common.dll version).

    Refuses on v1.1 rather than guessing: this address did not come from
    flhack, which patches code here instead of naming a constant, so there is
    no second build to fall back on and a guessed address would be a write into
    whatever happens to sit there.
    """
    _speed_addr, version = tl.locate(pid)
    if version not in APPROACH:
        raise NotRunning(
            f"the approach distance is only known for common.dll v1.0, and "
            f"this is v{version}; refusing to guess an address")
    addr = APPROACH[version] - tl.COMMON_BASE + tl._base(pid, "common.dll")
    with open(f"/proc/{pid}/mem", "rb") as fh:
        fh.seek(addr)
        value = struct.unpack("<f", fh.read(4))[0]
    low, high = APPROACH_SANE
    if not low <= value <= high:
        raise NotRunning(
            f"the value at {addr:#x} is {value!r}, not a distance; "
            f"refusing to guess")
    return addr, version


def read_approach(pid=None):
    """(approach distance, version) for the running game."""
    pid = pid or sp.find_pid()
    addr, version = locate_approach(pid)
    with open(f"/proc/{pid}/mem", "rb") as fh:
        fh.seek(addr)
        return struct.unpack("<f", fh.read(4))[0], version


def set_approach(value, pid=None):
    """Set the docking approach distance, read it back, and confirm."""
    low, high = APPROACH_SANE
    if not low <= value <= high:
        raise ValueError(f"{value:g} is outside {low:g} to {high:g}")
    pid = pid or sp.find_pid()
    addr, _version = locate_approach(pid)
    with open(f"/proc/{pid}/mem", "r+b") as fh:
        fh.seek(addr)
        fh.write(struct.pack("<f", float(value)))
        fh.seek(addr)
        got = struct.unpack("<f", fh.read(4))[0]
    if abs(got - value) > 0.5:
        raise NotRunning(f"wrote {value:g} but read back {got:g}")
    return got


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
    ap.add_argument("--approach", type=float, metavar="M",
                    help="set the docking approach distance instead "
                         f"(vanilla {APPROACH_VANILLA:g}); this is the one "
                         "worth experimenting with")
    ap.add_argument("--vanilla", action="store_true",
                    help=f"both back to stock, {VANILLA:g} and "
                         f"{APPROACH_VANILLA:g}")
    args = ap.parse_args()

    try:
        pid = sp.find_pid()
        if args.vanilla:
            args.distance = VANILLA
            args.approach = APPROACH_VANILLA
        if args.distance is not None:
            print(f"dock cruise distance now {set_dist(args.distance, pid):g}")
        if args.approach is not None:
            print(f"docking approach distance now "
                  f"{set_approach(args.approach, pid):g}")

        value, version = read(pid)
        # The HUD figure, because that is the one the player can act on. The
        # raw number is measured from the object's centre and reads as wrong
        # against everything the game shows.
        print(f"common.dll v{version}, dock cruise distance {value:g} "
              f"(vanilla {VANILLA:g})")
        print(f"  cruise cuts at {value - PROXIMITY:.0f} m on the HUD for a "
              f"trade lane, and engages for anything beyond it")
        try:
            approach, _ = read_approach(pid)
            print(f"docking approach distance {approach:g} "
                  f"(vanilla {APPROACH_VANILLA:g})")
        except NotRunning as exc:
            print(f"docking approach distance unavailable: {exc}")

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
