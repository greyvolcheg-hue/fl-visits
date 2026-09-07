"""Docking: when the autopilot uses cruise, and when it stops flying you.

    fl.py dockdist                 # both settings, and what they buy
    fl.py dockdist 595             # cruise-to-dock threshold
    fl.py dockdist --takeover 200  # where automatic docking takes over
    fl.py dockdist --takeover-off
    fl.py dockdist --vanilla

**Two knobs, two mechanisms.** Re-testing one for the other cost an evening.

    cruise engines light     DOCK_DIST      a number      `dockdist.py 595`
    docking takes over       [ebp+0x50]     a code patch  `--takeover 200`

Memory only. Nothing on disk is touched and a relaunch restores both.

## DOCK_DIST, at 0x63a22c0, 1750.0 stock

    62fe163  mov  al, [esi+0x365]      ; gate
    62fe16b  je   0x62fe194            ; clear -> skip the compare entirely
    62fe16d  fld  dword [esp+0x1c]     ; distance to the dock
    62fe171  fcomp dword [0x63a22c0]   ; 1750.0
    62fe187  mov  [esi+0x364], al      ; cache the answer
    62fe18d  mov  byte [esi+0x365], 0  ; clear the gate

`[esi+0x364] = (distance > DOCK_DIST)`, 1 meaning use cruise. So a **larger**
value means "refuse to cruise until you are further away", not "cruise for
longer"; that direction backwards is what sent the early testing into the weeds.

**It is a one-shot latch.** The gate is cleared right after the compare, so the
answer is taken once when the dock is ordered and never revisited. Moving it
from 1750 to 300 changed nothing anyone could feel, because at any real lane
range both answer "use cruise".

**It is measured from the object's centre.** flhack: *"the 'physical' distance,
different to what is displayed"*, with the proximity radius defaulting to 495,
the figure trade lanes use. So `physical = displayed + 495`: for 100 m on the
HUD, set 595. A jump gate has its own radius and lands elsewhere.

## The takeover distance, at 0x62fe758

    62fe758  d9 45 50   fld dword [ebp+0x50]   ; 1000.0 stock
    62fe75b  8d 73 2c   lea esi, [ebx+0x2c]

A descriptor field, so the only place to change it is the instruction that
reads it. This ports flhack's "Closer docking", which substitutes 200 for a
non-station dock and 600 for a station, and only when the loaded value is
exactly 1000.0 so anything carrying its own figure is left alone. `inject.py`
supplies the cave and the call.

## Two dead ends, written down so nobody walks them again

**`activation_start` / `activation_end` in `select_equip.ini` are the ring's
spin-up window, not the ship's.** No value of them reaches the engine state.
Changed 750/500 to 100/50 by hand, no effect, restored.

**The global at 0x639f44c is not the takeover distance.** It initialises a
field holding the same 1000.0, and was flown at 100, 1000, 5000 and 10000 with
no difference to a lane approach. Its knob was removed. Do not look again.
"""

import argparse
import struct
import sys

from . import inject as ij
from . import speed as sp
from . import tradelane as tl
from .speed import NotRunning

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
    addr = DIST[version]
    value = struct.unpack("<f", ij.live_bytes(pid, addr, 4))[0]
    low, high = SANE
    if not low <= value <= high:
        raise NotRunning(
            f"common.dll v{version} found, but the value at {addr:#x} is "
            f"{value!r}, not a distance; refusing to guess")
    return addr, version


# --- the takeover patch -----------------------------------------------------
#
# Two stubs from `flhack.nsm`. The cave holds the read-only half:
#
#     +0 sentinel  +4 station  +8 other (tuned)  +12 scratch pointer
#     +16 dock_type (12 bytes)   +32 closer_docking (43 bytes)
#
# **`dockwith` is not in the cave.** The first stub writes it while the game
# runs, and the cave is `.text` padding on a read-only page: a store there is
# an access violation and the game dies on the spot. It goes in `inject`'s
# writable scratch. The constants stay, because only this tool writes them,
# from outside, where page protection does not apply.

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


def _calls(type_site, dock_site, cave):
    """The two call sites, as the list `inject.install`/`revert` work from."""
    return [
        ("common.dll", type_site,
         ij.call_to(type_site, cave + TYPE_OFF, 5) + b"\xa8\xc0"),
        ("common.dll", dock_site,
         ij.call_to(dock_site, cave + DOCK_OFF, DOCK_LEN)),
    ]


def takeover_on(distance, pid=None, version=None):
    """Install the patch so docking takes over at `distance` metres.

    Order matters and is the whole safety story: fill the cave first, read it
    back, and only then write the calls. A call that lands on an empty cave
    executes zeros; a stub nobody calls is inert.
    """
    distance = _sane(distance, TAKEOVER_SANE)
    pid = pid or sp.find_pid()
    if version is None:
        _addr, version = tl.locate(pid)
    type_site, dock_site = _sites(version)

    if ij.patched(pid, dock_site, DOCK_LEN):
        raise NotRunning(
            "the takeover patch is already installed; use --takeover-off "
            "first, or set the distance alone, which needs no re-patch")

    cave, room = ij.find_cave(pid, STUB_BYTES + 64)
    scratch, _run = ij.find_scratch(pid, 4)
    dock_type, closer = _stubs(cave, scratch)

    # Built by slotting each piece at its own offset rather than by counting
    # the gaps between them. The old form spelled the gaps as arithmetic on
    # four numbers that nothing checked against each other, so the layout
    # comment above and the code below could drift apart silently.
    payload = bytearray(STUB_BYTES)
    payload[DATA_OFF:DATA_OFF + 16] = struct.pack(
        "<fffI", SENTINEL, STATION, distance, scratch)
    payload[TYPE_OFF:TYPE_OFF + len(dock_type)] = dock_type
    payload[DOCK_OFF:DOCK_OFF + len(closer)] = closer
    ij.write_bytes(pid, cave, bytes(payload))

    ij.install(pid, _calls(type_site, dock_site, cave))
    return cave, room, version


def takeover_off(pid=None, version=None):
    """Put the shipped bytes back at both sites, and blank the cave.

    **Blanking is not tidiness, it is what makes this reversible.**
    `inject.find_cave` refuses a cave that is not all zeros, so a stub left
    behind means the patch can never be reinstalled without a relaunch. Found
    on 2026-09-06 by toggling the button off and on: the guard did its job and
    the second install was refused.
    """
    pid = pid or sp.find_pid()
    if version is None:
        _addr, version = tl.locate(pid)
    type_site, dock_site = _sites(version)

    cave = scratch = None
    if ij.patched(pid, dock_site, DOCK_LEN):
        cave = _cave_of(pid, dock_site)
        # Read out of the cave's own data block, where `takeover_on` put it.
        # It used to be recovered by checking for opcode 0xA3 at byte 6 of the
        # stub and unpacking the operand, which would have stopped working,
        # silently, the moment the stub's first instruction changed.
        scratch = struct.unpack(
            "<I", ij.live_bytes(pid, cave + DATA_OFF + 12, 4))[0]

    # Calls first. Blanking the cave while a call still points at it would
    # leave the game executing zeros for however long the two writes take.
    ij.revert(pid, _calls(type_site, dock_site, cave or 0))
    if cave is not None:
        ij.write_bytes(pid, cave, bytes(STUB_BYTES))
        ij.write_bytes(pid, scratch, bytes(4))
    return version


def _cave_of(pid, dock_site):
    """Where the installed stub lives, from the call that reaches it.

    Read from the running game rather than searched for again: a fresh search
    can legitimately pick somewhere else, and then the cleanup would blank an
    innocent region and leave the real stub in place.
    """
    call = ij.live_bytes(pid, dock_site, 5)
    rel = struct.unpack("<i", call[1:5])[0]
    return dock_site + 5 + rel - DOCK_OFF


def takeover_state(pid=None, version=None):
    """(installed?, distance or None, version).

    `version` is threaded in the way `tradelane.read_accel` takes one: the
    caller that just located the build should not make this locate it again,
    and on the Speed tab this runs every five seconds.
    """
    pid = pid or sp.find_pid()
    if version is None:
        _addr, version = tl.locate(pid)
    dock_site = _sites(version)[1]
    if not ij.patched(pid, dock_site, DOCK_LEN):
        return False, None, version
    blob = ij.live_bytes(pid, _cave_of(pid, dock_site) + DATA_OFF, 12)
    _sentinel, _station, other = struct.unpack("<fff", blob)
    return True, other, version


def set_takeover(distance, pid=None, version=None):
    """Change the distance without re-patching, once it is installed."""
    distance = _sane(distance, TAKEOVER_SANE)
    pid = pid or sp.find_pid()
    installed, _now, version = takeover_state(pid, version)
    if not installed:
        raise NotRunning("the takeover patch is not installed")
    cave = _cave_of(pid, _sites(version)[1])
    ij.write_bytes(pid, cave + DATA_OFF + 8, struct.pack("<f", distance))
    return distance


def read(pid=None):
    """(distance, version) for the running game."""
    pid = pid or sp.find_pid()
    addr, version = locate(pid)
    return struct.unpack("<f", ij.live_bytes(pid, addr, 4))[0], version


def set_dist(value, pid=None):
    """Set the distance, read it back, and confirm."""
    value = _sane(value, SANE)
    pid = pid or sp.find_pid()
    addr, _version = locate(pid)
    # `write_bytes` reads back and compares the bytes exactly. The old code
    # here had its own tolerance of half a metre, which was a second and
    # weaker rule for the same question.
    ij.write_bytes(pid, addr, struct.pack("<f", value))
    return value


def _sane(value, bounds):
    """Bounds-check and coerce, in the one place both callers can share."""
    low, high = bounds
    if not low <= value <= high:
        raise ValueError(f"{value:g} is outside {low:g} to {high:g}")
    return float(value)


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

