"""Read and set thruster speed in a running Freelancer, without a restart.

    fl.py thrusters                    # what every thruster is set to
    fl.py thrusters 263739 500         # set one, by its ids_name
    fl.py thrusters all 350            # set all six

Speed is `max_force / 600`, and it is a **bonus, not a total**: the number is
added to the ship's cruise-off speed rather than replacing it. Confirmed in
play, setting 300 gave "base plus 300". So 1000 here is not a 1000 speed ship,
it is a very fast one, and the numbers below read as "how much thruster".

The divisor is the game's own: vanilla `st_equip.ini` puts all six thrusters at
72000, which is the 120 everyone knows as the stock thruster bonus.

Confirmed working in play on 2026-09-01. Writing 600000 to the Heavy Thruster
changed the ship's thrust immediately, no re-equip and no reload, so the value
is read per burn rather than cached when the thruster is mounted. That is what
makes a live selector worth having, and it is the same behaviour cruise speed
turned out to have.

**Anchor on `ids_name`, never on `max_force`.** The six thruster records sit in
one array 160 bytes apart, but anchoring on the speed value would break the
moment we write to it, and searching for the value itself is hopeless anyway:
72000.0 matches in three places and 1000.0 in nearly seven thousand. The
`ids_name` numbers are unique constants nothing ever writes to, and each one
matched in exactly one place across the whole address space when checked.

The process plumbing is imported from `speed.py` rather than copied: same
game, same technique, and a second copy of the region scan would be a second
thing to keep right.
"""

import os
import struct
import sys

from .speed import NotRunning, find_pid, regions

# max_force sits this far after the ids_name that identifies its record, and the
# six records repeat at this stride, in st_equip.ini order.
OFFSET = 0x78
STRIDE = 0xA0
PER_SPEED = 600.0

# ids_name -> nickname. The display name comes from the game's infocards, so it
# is not repeated here; `labels()` reads it the way the rest of the tool does.
THRUSTERS = {
    263737: "ge_s_thruster_01",
    263738: "ge_s_thruster_02",
    263739: "ge_s_thruster_03",
    263740: "ge_s_thruster_04",
    263741: "order_thruster",
    263742: "no_thruster",
}

# Offered in the UI. 120 is vanilla.
SPEED_CHOICES = [120, 170, 220, 270, 320, 370, 420]

# A thruster below this is useless and above it the ship is unflyable; the range
# exists to turn a wrong address into a refusal rather than into a wrecked save.
SANE_SPEED = (10.0, 5000.0)


def locate(pid):
    """ids_name -> address of its max_force, for all six thrusters.

    Requiring each id to match exactly once is not good enough. An `ids_name`
    is a plain integer that also occurs in unrelated memory, so a thruster can
    pick up a second candidate and get silently dropped, which is what happened
    to the Deluxe on the first run: five of six, no error, no clue.

    The array itself is the disambiguator. The six records are contiguous at a
    160-byte stride in `st_equip.ini` order, so once any one candidate is
    assumed correct every other address is predicted rather than searched for.
    The base that predicts the most records wins, and a lone coincidence
    predicts nothing.
    """
    order = sorted(THRUSTERS)
    index = {ids: n for n, ids in enumerate(order)}
    wanted = {struct.pack("<i", ids): ids for ids in THRUSTERS}
    low, high = SANE_SPEED

    candidates = {}
    try:
        mem = open(f"/proc/{pid}/mem", "rb")
    except OSError as exc:
        raise NotRunning(f"cannot read process memory: {exc}") from exc
    with mem:
        for start, end in regions(pid):
            try:
                mem.seek(start)
                buf = mem.read(end - start)
            except OSError:
                continue
            for pattern, ids in wanted.items():
                i = buf.find(pattern)
                while i != -1:
                    at = i + OFFSET
                    if at + 4 <= len(buf):
                        force = struct.unpack_from("<f", buf, at)[0]
                        if low * PER_SPEED <= force <= high * PER_SPEED:
                            candidates.setdefault(ids, set()).add(start + at)
                    i = buf.find(pattern, i + 1)

    best = {}
    for ids, addrs in candidates.items():
        for addr in addrs:
            base = addr - index[ids] * STRIDE
            agreed = {
                other: base + index[other] * STRIDE
                for other in order
                if base + index[other] * STRIDE in candidates.get(other, ())
            }
            if len(agreed) > len(best):
                best = agreed
    if len(best) < len(THRUSTERS):
        missing = [THRUSTERS[i] for i in order if i not in best]
        raise NotRunning(
            f"found {len(best)} of {len(THRUSTERS)} thrusters, missing {', '.join(missing)}"
        )
    return best


def read_all(pid=None):
    """[(ids_name, nickname, address, speed)] for the running game."""
    pid = pid or find_pid()
    found = locate(pid)
    if not found:
        raise NotRunning("thrusters not found; is the game past the menu?")
    out = []
    with open(f"/proc/{pid}/mem", "rb") as fh:
        for ids, addr in sorted(found.items()):
            fh.seek(addr)
            force = struct.unpack("<f", fh.read(4))[0]
            out.append((ids, THRUSTERS[ids], addr, force / PER_SPEED))
    return pid, out


def set_speed(ids, speed, pid=None):
    """Set one thruster's speed, read it back, and confirm."""
    low, high = SANE_SPEED
    if not low <= speed <= high:
        raise ValueError(f"{speed} is outside {low:g} to {high:g}")
    if ids not in THRUSTERS:
        raise ValueError(f"unknown thruster {ids}")
    pid = pid or find_pid()
    found = locate(pid)
    if ids not in found:
        raise NotRunning(f"{THRUSTERS[ids]} not found in the process")
    addr, force = found[ids], float(speed) * PER_SPEED
    with open(f"/proc/{pid}/mem", "r+b") as fh:
        fh.seek(addr)
        fh.write(struct.pack("<f", force))
    with open(f"/proc/{pid}/mem", "rb") as fh:
        fh.seek(addr)
        got = struct.unpack("<f", fh.read(4))[0]
    if abs(got - force) > 1.0:
        raise NotRunning(f"wrote {force:g} but read back {got:g}")
    return got / PER_SPEED


def main():
    try:
        args = sys.argv[1:]
        if len(args) == 2:
            target, speed = args[0], float(args[1])
            ids_list = list(THRUSTERS) if target == "all" else [int(target)]
            for ids in ids_list:
                print(f"{THRUSTERS[ids]}: {set_speed(ids, speed):g}")
            return
        pid, rows = read_all()
        print(f"pid {pid}")
        for ids, nick, addr, speed in rows:
            print(f"  {ids}  {nick:<20} {addr:#012x}  speed {speed:g}")
    except (NotRunning, ValueError) as exc:
        sys.exit(str(exc))

