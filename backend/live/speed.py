"""Read and set the cruise speed of a running Freelancer, without a restart.

    fl.py speed            # what the running game is using
    fl.py speed 2000       # set it, takes effect on the next cruise

`CRUISING_SPEED` is one global in `DATA/constants.ini`, read once at startup.
There is no per-system or per-zone version of it: the key appears in exactly
one file out of 8370 under DATA/. So changing it for "fast in open space, slow
in an asteroid field" cannot be done through the game's data at all, and the
only way to change it mid-flight is to write to the process.

That works. Confirmed on 2026-09-01 by writing 20.0 into a live game: the ship
slowed immediately, no reload, no crash. The value is read per cruise burn
rather than cached at spawn, which is what makes a selector worth having.

**The address is not stable and must never be hardcoded.** It sits in
`common.dll`, whose load address moves between runs. It is found instead by
the three floats that follow it, `5.0, 3.0, 0.25`, which are unique in the
whole address space: one hit, every time. Searching for the speed value itself
is useless, 1000.0 alone matches 6948 places.

Writing needs no privileges beyond being the same user, provided
`kernel.yama.ptrace_scope` is 0, which it is on this machine.

**Finding the game and reaching its memory is `proc.py`'s job**, not this
module's, and the two names re-exported below are here because half the
project already imports them from this file. `proc` is where they live now,
and it is where the Windows implementation of them lives too.
"""

import struct
import sys

from . import proc
from .proc import NotRunning, PROCESS, find_pid, regions  # noqa: F401

# The floats that follow CRUISING_SPEED in the loaded EngineEquipConsts block.
SIGNATURE = struct.pack("<fff", 5.0, 3.0, 0.25)
SANE = (1.0, 100000.0)


def locate(pid):
    """Address of CRUISING_SPEED in the live process.

    Raises when the signature is not found exactly once: zero means the game
    has not loaded its data yet (or the layout changed), more than one means
    the anchor is no longer unique and writing would be a guess.
    """
    hits = []
    for start, end in regions(pid):
        try:
            buf = proc.read(pid, start, end - start)
        except OSError:
            # A mapping the kernel will not hand over. Skipping it is right:
            # the anchor is in the game's own data, not in something locked.
            continue
        i = buf.find(SIGNATURE)
        while i != -1:
            if i >= 4:
                hits.append(start + i - 4)
            i = buf.find(SIGNATURE, i + 1)
    if not hits:
        raise NotRunning("cruise speed not found; is the game past the menu?")
    if len(hits) > 1:
        raise NotRunning(f"signature matched {len(hits)} places, refusing to guess")
    return hits[0]


def read(pid, addr):
    return struct.unpack("<f", proc.read(pid, addr, 4))[0]


def write(pid, addr, value):
    """Set the speed, then read it back and confirm."""
    low, high = SANE
    if not low <= value <= high:
        raise ValueError(f"{value} is outside {low} to {high}")
    proc.write(pid, addr, struct.pack("<f", float(value)))
    got = read(pid, addr)
    if abs(got - value) > 0.5:
        raise NotRunning(f"wrote {value} but read back {got}")
    return got


def current():
    """(pid, address, speed) for the running game."""
    pid = find_pid()
    addr = locate(pid)
    return pid, addr, read(pid, addr)


def set_speed(value):
    pid, addr, _ = current()
    return write(pid, addr, value)


def main():
    try:
        if len(sys.argv) > 1:
            print(f"cruise speed now {set_speed(float(sys.argv[1]))}")
        else:
            pid, addr, speed = current()
            print(f"pid {pid}, {addr:#x}, cruise speed {speed}")
    except (NotRunning, ValueError) as exc:
        sys.exit(str(exc))

