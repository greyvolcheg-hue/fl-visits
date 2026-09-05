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

## The takeover distance, which is the other half and a different mechanism

`DOCK_DIST` answers "does the autopilot use cruise for this run". It does not
answer "when does the run end", and no number in memory does. **A global at
0x639f44c was tried and disproved**: it initialises a field that looked like the
same 1000.0, and the owner flew it at 100, 1000, 5000 and 10000 with no
difference to a lane approach at all. The knob for it was removed on 2026-09-05.
Do not go looking for it again.

The distance at which automatic docking takes over is loaded here:

    62fe758  d9 45 50   fld dword [ebp+0x50]     ; 1000.0 stock
    62fe75b  8d 73 2c   lea esi, [ebx+0x2c]

`[ebp+0x50]` is a field of a descriptor, so the only place to change it is the
instruction that reads it. That is exactly what flhack's "Closer docking" does,
and its help calls it *"reduces the distance where automatic docking takes
over"*. Its stub substitutes 200.0 for a non-station dock (trade lane, jump
gate) and 600.0 for a station, but only when the loaded value is exactly 1000.0,
so anything with its own figure is left alone.

This module ports that stub, with the non-station value configurable and
defaulting to **100**, which is what the owner asked for. `inject.py` supplies
the cave and the call, and carries why no allocation is needed.

## Which of these does what, so the next person does not re-test both

    step 3, cruise engines light        DOCK_DIST      a number     `dockdist.py 595`
    step 5, docking takes over          [ebp+0x50]     a code patch `--takeover 100`

Memory only, both of them. `tradelane.py` has written to this same read-only
section of this same DLL since 2026-09-02, no file is touched, and the next
launch puts everything back.
"""

import argparse
import struct
import sys

import inject as ij
import speed as sp
import tradelane as tl
from speed import NotRunning

# flhack's ADDR_DOCK_DIST, relative to the same `common.dll` base tradelane.py
# uses. Which of the two builds is running is decided by tradelane.locate, so
# there is one copy of that check rather than two that can disagree.
DIST = {10: 0x63A22C0, 11: 0x63A22F0}

# flhack's ADDR_DOCKa / ADDR_DOCKb, the two sites "Closer docking" patches.
# `inject.patch` checks the bytes it is about to cover against the shipped DLL,
# so picking the wrong build's pair is caught rather than written through: on a
# v1.0 install the v1.1 sites hold unrelated code and the write is refused.
TYPE_SITE = {10: 0x62C3DA4, 11: 0x62C3E04}
DOCK_SITE = {10: 0x62FE758, 11: 0x62FE808}
TYPE_LEN = 7  # test byte [esi+0x32c], 0xC0
DOCK_LEN = 6  # fld dword [ebp+0x50] ; lea esi, [ebx+0x2c]

# What the game loads when a dock point has no figure of its own, and the only
# value the stub is willing to replace.
SENTINEL = 1000.0
STATION = 600.0        # flhack's f600: stations and planets
# 200 is where the owner settled on 2026-09-05, after flying 100, 200, 400 and
# 600, and it is the number flhack picked independently. Below it the approach
# is unplayable; above it the gain shrinks, because the distance is really a
# time budget and the owner arrives at cruise speed about 40% of the time and
# brakes by hand for those.
NON_STATION = 200.0
TAKEOVER_SANE = (20.0, 5000.0)

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


# --- the takeover patch -----------------------------------------------------
#
# Two stubs, both ported from `flhack.nsm`. The cave holds the read-only half:
#
#     +0   sentinel    1000.0, the only value the second stub will replace
#     +4   station     600.0
#     +8   other       100.0, the one the owner tunes
#     +16  dock_type       12 bytes
#     +32  closer_docking  43 bytes
#
# **`dockwith` is not in there.** The first stub writes it while the game runs,
# and the cave is `.text` padding on a read-only page, so a store into it is an
# access violation and the game dies on the spot. It lives in `inject`'s
# writable scratch instead. The constants stay in the cave because only this
# tool ever writes them, from outside, where page protection does not apply.

DATA_OFF, TYPE_OFF, DOCK_OFF = 0, 16, 32
STUB_BYTES = 32 + 43


def _stubs(cave, scratch):
    """(dock_type, closer_docking), assembled against these two addresses."""
    dockwith = struct.pack("<I", scratch)
    sentinel = struct.pack("<I", cave + DATA_OFF)
    station = struct.pack("<I", cave + DATA_OFF + 4)
    other = struct.pack("<I", cave + DATA_OFF + 8)

    # mov eax,[esi+0x32c] ; mov [dockwith],eax ; ret
    # Saves the dock's type flags where the second stub can see them; the
    # displaced `test byte [esi+0x32c],0xC0` becomes `test al,0xC0` at the
    # call site, which sets the same flags from the same byte.
    dock_type = b"\x8b\x86\x2c\x03\x00\x00" + b"\xa3" + dockwith + b"\xc3"
    assert len(dock_type) == 12

    closer = (
        b"\xd9\x45\x50"                  # 0  fld dword [ebp+0x50]
        + b"\xd8\x15" + sentinel         # 3  fcom dword [sentinel]
        + b"\xdf\xe0"                    # 9  fnstsw ax
        + b"\xf6\xc4\x40"                # 11 test ah, 0x40   (C3 = equal)
        + b"\x74\x17"                    # 14 jz .ret  -> 39, not 1000, keep it
        + b"\xdd\xd8"                    # 16 fstp st0        (drop the 1000)
        + b"\xf6\x05" + struct.pack("<I", scratch + 1) + b"\x01"
        #                                # 18 test byte [dockwith+1], 1
        + b"\xbe" + other                # 25 mov esi, other  (flags untouched)
        + b"\x74\x05"                    # 30 jz .1 -> 37, not a station
        + b"\xbe" + station              # 32 mov esi, station
        + b"\xd9\x06"                    # 37 .1: fld dword [esi]
        + b"\x8d\x73\x2c"                # 39 .ret: lea esi,[ebx+0x2c]
        + b"\xc3"                        # 42 ret
    )
    assert len(closer) == 43
    return dock_type, closer


def _sites(version):
    if version not in TYPE_SITE:
        raise NotRunning(f"no takeover sites known for common.dll v{version}")
    return TYPE_SITE[version], DOCK_SITE[version]


def takeover_on(distance, pid=None, station=STATION):
    """Install the patch so docking takes over at `distance` metres.

    Order matters and is the whole safety story: fill the cave first, read it
    back, and only then write the calls. A call that lands on an empty cave
    executes zeros; a stub nobody calls is inert.
    """
    low, high = TAKEOVER_SANE
    if not low <= distance <= high:
        raise ValueError(f"{distance:g} is outside {low:g} to {high:g}")
    pid = pid or sp.find_pid()
    _addr, version = tl.locate(pid)
    type_site, dock_site = _sites(version)

    if ij.patched(pid, dock_site, DOCK_LEN):
        raise NotRunning(
            "the takeover patch is already installed; use --takeover-off "
            "first, or set the distance alone, which needs no re-patch")

    cave, room = ij.find_cave(pid, STUB_BYTES + 64)
    scratch, _run = ij.find_scratch(pid, 4)
    dock_type, closer = _stubs(cave, scratch)

    payload = (
        struct.pack("<fff", SENTINEL, station, float(distance))
        + bytes(TYPE_OFF - 12) + dock_type
        + bytes(DOCK_OFF - TYPE_OFF - len(dock_type)) + closer
    )
    ij.write_bytes(pid, cave, payload)

    ij.patch(pid, type_site,
             ij.call_to(type_site, cave + TYPE_OFF, 5) + b"\xa8\xc0")
    ij.patch(pid, dock_site,
             ij.call_to(dock_site, cave + DOCK_OFF, DOCK_LEN))
    return cave, room, version


def takeover_off(pid=None):
    """Put the shipped bytes back at both sites, and blank the cave."""
    pid = pid or sp.find_pid()
    _addr, version = tl.locate(pid)
    type_site, dock_site = _sites(version)
    # Calls first. Blanking the cave while a call still points at it would
    # leave the game executing zeros for however long the two writes take.
    ij.restore(pid, dock_site, DOCK_LEN)
    ij.restore(pid, type_site, TYPE_LEN)
    return version


def takeover_state(pid=None):
    """(installed?, distance or None, version)."""
    pid = pid or sp.find_pid()
    _addr, version = tl.locate(pid)
    type_site, dock_site = _sites(version)
    if not ij.patched(pid, dock_site, DOCK_LEN):
        return False, None, version
    # The call's own target says where the cave is, so the distance is read
    # from wherever the running game actually points rather than from a fresh
    # search that might pick somewhere else.
    call = ij.live_bytes(pid, dock_site, 5)
    rel = struct.unpack("<i", call[1:5])[0]
    cave = dock_site + 5 + rel - DOCK_OFF
    blob = ij.live_bytes(pid, cave + DATA_OFF, 12)
    _sentinel, _station, other = struct.unpack("<fff", blob)
    return True, other, version


def set_takeover(distance, pid=None):
    """Change the distance without re-patching, once it is installed."""
    low, high = TAKEOVER_SANE
    if not low <= distance <= high:
        raise ValueError(f"{distance:g} is outside {low:g} to {high:g}")
    pid = pid or sp.find_pid()
    installed, _now, version = takeover_state(pid)
    if not installed:
        raise NotRunning("the takeover patch is not installed")
    _type_site, dock_site = _sites(version)
    call = ij.live_bytes(pid, dock_site, 5)
    rel = struct.unpack("<i", call[1:5])[0]
    cave = dock_site + 5 + rel - DOCK_OFF
    ij.write_bytes(pid, cave + DATA_OFF + 8, struct.pack("<f", float(distance)))
    return distance


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
    ap.add_argument("--takeover", type=float, metavar="M",
                    help="distance at which automatic docking takes over, "
                         f"for lanes and gates (stock {SENTINEL:g}); installs "
                         "the code patch if it is not in yet")
    ap.add_argument("--takeover-off", action="store_true",
                    help="remove the takeover patch, leaving the game running")
    ap.add_argument("--vanilla", action="store_true",
                    help=f"everything back to stock: {VANILLA:g} and no patch")
    args = ap.parse_args()

    try:
        pid = sp.find_pid()
        if args.vanilla:
            args.distance = VANILLA
            args.takeover_off = True
        if args.distance is not None:
            print(f"dock cruise distance now {set_dist(args.distance, pid):g}")
        if args.takeover_off:
            installed, _now, _v = takeover_state(pid)
            if installed:
                takeover_off(pid)
                print("takeover patch removed, back to the stock 1000")
            else:
                print("takeover patch was not installed")
        elif args.takeover is not None:
            installed, _now, _v = takeover_state(pid)
            if installed:
                print(f"takeover distance now {set_takeover(args.takeover, pid):g}")
            else:
                cave, room, _v = takeover_on(args.takeover, pid)
                print(f"takeover patch installed, stub in {room} bytes of "
                      f".text padding at {cave:#x}")
                print(f"takeover distance now {args.takeover:g}")

        value, version = read(pid)
        # The HUD figure, because that is the one the player can act on. The
        # raw number is measured from the object's centre and reads as wrong
        # against everything the game shows.
        print(f"common.dll v{version}, dock cruise distance {value:g} "
              f"(vanilla {VANILLA:g})")
        print(f"  cruise cuts at {value - PROXIMITY:.0f} m on the HUD for a "
              f"trade lane, and engages for anything beyond it")
        installed, distance, _v = takeover_state(pid)
        if installed:
            print(f"takeover patch IN, docking takes over at {distance:g} m "
                  f"for lanes and gates (stock {SENTINEL:g})")
        else:
            print(f"takeover patch not installed, so docking takes over at "
                  f"the stock {SENTINEL:g}")

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
