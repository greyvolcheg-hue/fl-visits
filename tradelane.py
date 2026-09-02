#!/usr/bin/env python3
"""Trade lane speed, and the 999 cap on the speed readout, in the live game.

    tradelane.py                # what the running game is using
    tradelane.py 8000           # set the trade lane speed
    tradelane.py --uncap        # let the HUD show speeds above 999

Trade lane speed is not in the game's data at all. `constants.ini` has no key
for it, the `Trade_Lane_Ring` archetype in `solararch.ini` has none, and
`[TradeLane] basic_trade_lane_eq` in `select_equip.ini` carries only timings,
ring spin and activation distances. It is a constant inside `common.dll`, so
the only way to change it is to write to the process, the same as cruise speed.

The addresses come from **flhack** (Jason Hood, 2014), a long-standing
Freelancer patcher whose C source the owner supplied. They are used here rather
than found by scanning, because a scan cannot tell the real constant from a
coincidence: an earlier attempt here found a lone 2500.0 in the mapping that
holds the cruise constant and it was the wrong one, sitting in the loaded copy
of `constants.ini` among the CommConsts values.

**The constant's address is read, not hardcoded.** flhack knows two builds of
`common.dll` and picks between them by reading a pointer out of the code at a
fixed check site. That pointer *is* the address of the trade lane speed, so
following it works for either build and validates itself on the way: if the
float it names is not a plausible speed, something is wrong and this refuses.

    v1.0   check 0x62c1485 -> 0x639f39c
    v1.1   check 0x62c14e5 -> 0x639f3cc

Both are given relative to a `common.dll` base of 0x6260000, which is where it
actually loads. Verified on this machine 2026-09-02: the v1.0 site matched and
the float it points at read exactly 2500.0, the vanilla trade lane speed and
flhack's own default.

The HUD cap is two writes into `Freelancer.exe` instead:

    0x4d5936   `0f 85` (jnz) -> `90 e9` (nop; jmp), dropping the 300 limit
    0x4d597a   the DWORD 999 -> 9999, the readout's own maximum

Writing to a code page is fine through `/proc/<pid>/mem`, which bypasses page
protection, so no `mprotect` dance is needed the way flhack needs one on
Windows.

Everything here is memory only. No file is touched and the game reverts to its
own numbers on the next launch.
"""

import argparse
import struct
import sys

from speed import NotRunning, find_pid  # noqa: F401  (re-exported deliberately)

COMMON_BASE = 0x6260000  # what the flhack addresses are relative to
CHECKS = ((10, 0x62C1485, 0x639F39C), (11, 0x62C14E5, 0x639F3CC))

VANILLA = 2500.0
SANE = (100.0, 10000.0)  # flhack caps at 10000; below 100 a lane is unusable

ADDR_CRUISE_CAP = 0x4D5936
CAP_ON = b"\x90\xe9"   # nop; jmp   -- no 300 limit
CAP_OFF = b"\x0f\x85"  # jnz        -- stock
ADDR_MAX_SHOWN = 0x4D597A
SHOWN_STOCK = 999
SHOWN_RAISED = 9999


def _base(pid, tail):
    """Lowest mapped address of the module whose path ends with `tail`."""
    found = None
    try:
        maps = open(f"/proc/{pid}/maps")
    except OSError as exc:
        raise NotRunning(f"cannot read the process map: {exc}") from exc
    with maps:
        for line in maps:
            if line.rstrip().endswith(tail):
                start = int(line.split()[0].split("-")[0], 16)
                found = start if found is None else min(found, start)
    if found is None:
        raise NotRunning(f"{tail} is not mapped; is the game past the menu?")
    return found


def locate(pid):
    """(address of the trade lane speed, common.dll version)."""
    base = _base(pid, "common.dll")
    with open(f"/proc/{pid}/mem", "rb") as fh:
        for version, check, expect in CHECKS:
            fh.seek(check - COMMON_BASE + base)
            pointer = struct.unpack("<I", fh.read(4))[0]
            if pointer != expect:
                continue
            addr = pointer - COMMON_BASE + base
            fh.seek(addr)
            value = struct.unpack("<f", fh.read(4))[0]
            # The check site only proves which build this is. Reading the float
            # it names proves the pointer still means what it meant in 2014.
            low, high = SANE
            if not low <= value <= high:
                raise NotRunning(
                    f"common.dll v{version} found, but the value at "
                    f"{addr:#x} is {value!r}, not a speed; refusing to guess")
            return addr, version
    raise NotRunning("common.dll is neither of the two builds flhack knows")


def read(pid=None):
    """(speed, version) for the running game."""
    pid = pid or find_pid()
    addr, version = locate(pid)
    with open(f"/proc/{pid}/mem", "rb") as fh:
        fh.seek(addr)
        return struct.unpack("<f", fh.read(4))[0], version


def set_speed(value, pid=None):
    """Set the trade lane speed, read it back, and confirm."""
    low, high = SANE
    if not low <= value <= high:
        raise ValueError(f"{value:g} is outside {low:g} to {high:g}")
    pid = pid or find_pid()
    addr, _version = locate(pid)
    with open(f"/proc/{pid}/mem", "r+b") as fh:
        fh.seek(addr)
        fh.write(struct.pack("<f", float(value)))
        fh.seek(addr)
        got = struct.unpack("<f", fh.read(4))[0]
    if abs(got - value) > 0.5:
        raise NotRunning(f"wrote {value:g} but read back {got:g}")
    return got


def read_cap(pid=None):
    """(uncapped?, the readout's current maximum) for the running game."""
    pid = pid or find_pid()
    with open(f"/proc/{pid}/mem", "rb") as fh:
        fh.seek(ADDR_CRUISE_CAP)
        patch = fh.read(2)
        fh.seek(ADDR_MAX_SHOWN)
        shown = struct.unpack("<I", fh.read(4))[0]
    if patch not in (CAP_ON, CAP_OFF):
        raise NotRunning(f"unexpected bytes at {ADDR_CRUISE_CAP:#x}: "
                         f"{patch.hex(' ')}; refusing to write")
    return patch == CAP_ON, shown


def set_cap(uncapped, pid=None):
    """Raise or restore the speed the HUD is willing to show."""
    pid = pid or find_pid()
    read_cap(pid)  # validates the site before writing to it
    with open(f"/proc/{pid}/mem", "r+b") as fh:
        fh.seek(ADDR_CRUISE_CAP)
        fh.write(CAP_ON if uncapped else CAP_OFF)
        fh.seek(ADDR_MAX_SHOWN)
        fh.write(struct.pack("<I", SHOWN_RAISED if uncapped else SHOWN_STOCK))
    return read_cap(pid)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("speed", nargs="?", type=float, help="new trade lane speed")
    ap.add_argument("--uncap", action="store_true", help="show speeds over 999")
    ap.add_argument("--recap", action="store_true", help="restore the 999 limit")
    args = ap.parse_args()

    try:
        pid = find_pid()
        if args.speed is not None:
            print(f"trade lane speed now {set_speed(args.speed, pid):g}")
        if args.uncap or args.recap:
            on, shown = set_cap(args.uncap, pid)
            print(f"speed readout {'uncapped' if on else 'capped'}, max {shown}")
        if args.speed is None and not (args.uncap or args.recap):
            value, version = read(pid)
            on, shown = read_cap(pid)
            print(f"common.dll v{version}, trade lane speed {value:g} "
                  f"(vanilla {VANILLA:g})")
            print(f"speed readout {'uncapped' if on else 'capped'}, max {shown}")
    except (NotRunning, ValueError, OSError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
