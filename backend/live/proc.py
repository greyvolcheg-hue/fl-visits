"""What this machine can see of a running Freelancer, and proof it can read it.

    fl.py proc            # pid, modules, and sixteen bytes out of common.dll

That command reads and never writes, which is why it is listed with the
readers. The module itself is the write path too: it is the only code in the
project that reaches into another process's memory at all, on either OS.

**Everything in `live/` that touches the running game comes through here.**
Five modules used to open `/proc/<pid>/mem` and `/proc/<pid>/maps` themselves,
22 times between them, which is 22 copies of a decision that has exactly one
right answer per platform. The technique is identical in all of them: find the
game, find where a module landed, read a few bytes, write a few bytes back.

The six calls below are what those 22 places actually wanted:

    find_pid()                    the running game, or raise
    mappings(pid)                 [(lo, hi, perms, name)], name = a module path
    regions(pid)                  the writable ones worth scanning
    read(pid, addr, count)        bytes, possibly fewer than asked for
    write(pid, addr, data)        no return; callers read back and check
    chunks(pid, lo, hi, ...)      walk a range without holding it in memory

`perms` is spelled the way `/proc/<pid>/maps` spells it, `rwxp`, because that
is what the callers already read and because a string of four flags survives
being printed. The Windows side builds the same four letters out of its own
page protection constants.

**On the import order below.** `NotRunning` and `PROCESS` are defined before
the implementation is imported, and the implementation imports them back from
here. That is a cycle only on paper: by the time it runs, this module is in
`sys.modules` with both names already bound. It is the same shape as `os`
importing `posixpath`. What it buys is one exception class across both
platforms, so `except proc.NotRunning` catches a Windows failure and a Linux
one alike, and every caller that already says `except sp.NotRunning` keeps
working unchanged.

**Never import `proc_linux` or `proc_windows` directly.** Doing so from a cold
start begins the cycle at the wrong end and leaves this module half built.
"""

import sys

PROCESS = "Freelancer.exe"

# Mappings larger than this are not searched. The game maps a few hundred MB of
# graphics at a stretch and nothing worth finding has ever been in one.
BIG = 512 * 1024 * 1024


class NotRunning(Exception):
    """No Freelancer process, or its memory cannot be reached."""


if sys.platform == "win32":
    from . import proc_windows as _impl
else:
    from . import proc_linux as _impl

find_pid = _impl.find_pid
mappings = _impl.mappings
read = _impl.read
write = _impl.write
chunks = _impl.chunks

#: Which implementation is in use, for anything that has to say so out loud.
FLAVOUR = _impl.FLAVOUR


def regions(pid):
    """Writable mappings worth searching, largest excluded as noise.

    Shared rather than per platform: the rule is about this game, not about
    how a kernel reports its address space, and having it in one place is why
    `thrusters.py` and `speed.py` scan the same set.
    """
    return [(lo, hi) for lo, hi, perms, _name in mappings(pid)
            if "w" in perms and hi - lo <= BIG]


def main():
    """Say what this can see, and prove a read works. Writes nothing."""
    try:
        pid = find_pid()
    except NotRunning as exc:
        sys.exit(str(exc))
    print(f"{FLAVOUR}: pid {pid}")

    seen = {}
    for lo, _hi, _perms, name in mappings(pid):
        if not name:
            continue
        base = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if base.endswith(".dll") or base.endswith(".exe"):
            seen[base] = min(seen.get(base, lo), lo)
    for name in sorted(seen):
        mark = "  <-- ours" if name in ("common.dll", "server.dll",
                                        "content.dll", "freelancer.exe") else ""
        print(f"  {seen[name]:#012x}  {name}{mark}")
    print(f"{len(seen)} modules, {len(mappings(pid))} mappings, "
          f"{len(regions(pid))} writable and worth scanning")

    where = seen.get("common.dll")
    if where is None:
        sys.exit("common.dll is not mapped; is a game loaded?")
    got = read(pid, where, 16)
    print(f"common.dll at {where:#x} starts {got.hex(' ')}")
    if got[:2] != b"MZ":
        sys.exit("that does not start with MZ, so the read is not landing "
                 "where it thinks it is")
    print("read OK")


if __name__ == "__main__":
    main()
