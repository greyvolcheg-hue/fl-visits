"""`/proc/<pid>/maps` and `/proc/<pid>/mem`. See `proc.py` for the interface.

This is the code that was spread across `speed.py`, `inject.py`, `tradelane.py`
and `thrusters.py` until 2026-09-12, moved rather than rewritten: the Linux
half of this project works and the port was not the moment to improve it.

**Writing through `/proc/<pid>/mem` bypasses page protection**, so a `.text` or
`.rdata` target needs no `mprotect`. That is not true of the Windows side and
is the one real behavioural difference between the two files; `inject.py` says
what it costs and what it does not change.

Needs no privileges beyond being the same user, provided
`kernel.yama.ptrace_scope` is 0. Where it is not, every call here fails with a
permission error, which is the honest outcome and must not be "fixed" by
loosening the setting for the whole machine.
"""

import os

from .proc import NotRunning, PROCESS

FLAVOUR = "linux /proc"


def find_pid():
    """PID of the running game, or raise. The newest wins if several match."""
    found = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as fh:
                cmdline = fh.read().decode("latin-1")
        except OSError:
            continue
        # The Lutris wrapper and gamescope carry the exe path in their command
        # lines too, so match the process whose own binary it is: its cmdline
        # starts with the path rather than mentioning it later.
        first = cmdline.split("\0", 1)[0]
        if first.endswith(PROCESS):
            found.append(int(entry))
    if not found:
        raise NotRunning("Freelancer is not running")
    return max(found)


def mappings(pid):
    """[(lo, hi, perms, name)] for every mapping, in the kernel's order."""
    try:
        maps = open(f"/proc/{pid}/maps")
    except OSError as exc:
        raise NotRunning(f"cannot read the process map: {exc}") from exc
    out = []
    with maps:
        for line in maps:
            parts = line.split()
            lo, hi = (int(x, 16) for x in parts[0].split("-"))
            # A mapped file's name can hold spaces, and this game's path does.
            name = " ".join(parts[5:]) if len(parts) > 5 else ""
            out.append((lo, hi, parts[1], name))
    return out


def read(pid, addr, count):
    """`count` bytes at `addr`, or fewer. Raises `OSError` when unreadable.

    The short read is left as it is rather than padded or retried: a caller
    scanning a range wants to skip what it cannot have, and one asking for
    eleven bytes of a known module wants to know if it got four.
    """
    with open(f"/proc/{pid}/mem", "rb") as fh:
        fh.seek(addr)
        return fh.read(count)


def write(pid, addr, data):
    """Write, and say nothing about whether it took.

    Every caller reads back and compares, because a write into a page the
    kernel will not hand over can fail without raising here.
    """
    with open(f"/proc/{pid}/mem", "r+b") as fh:
        fh.seek(addr)
        fh.write(data)


def chunks(pid, lo, hi, overlap=0, span=1 << 20):
    """Walk a mapping a megabyte at a time, overlapping so runs are not split.

    One open file for the whole walk, which is the point: `find_scratch` pulls
    whole mappings through this on a 7.6 GB tablet, and an earlier version that
    read them into Python whole stalled the desktop hard enough to look like a
    freeze.
    """
    try:
        fh = open(f"/proc/{pid}/mem", "rb")
    except OSError:
        return
    with fh:
        pos = lo
        while pos < hi:
            end = min(pos + span, hi)
            try:
                fh.seek(pos)
                buf = fh.read(end - pos)
            except OSError:
                return
            if not buf:
                return
            yield pos, buf
            pos = end - overlap if end < hi else end
