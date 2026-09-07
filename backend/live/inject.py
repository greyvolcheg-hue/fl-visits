"""Put a few bytes of our own code into the running game, and take them out.

    fl.py inject            # show the cave, and whether anything is patched

Some things flhack does cannot be done by changing a number. `[ebp+0x50]`, the
distance at which automatic docking takes over, is a field of a descriptor, so
the only place to change it is the instruction that loads it. That means a code
patch, and a code patch needs somewhere to put the code.

**flhack allocates; we do not have to.** On Windows it calls `VirtualAllocEx`
for an executable block and stores the pointer in the game's own memory, at
0x67bf40, which used to hold the random intro number. `/proc/<pid>/mem` cannot
allocate anything, so that route is closed. It is also unnecessary:

    common.dll .text ends at 0x6398730 with 2256 bytes of zero padding,
    inside a mapping that is already r-xp

That is linker slack between the end of the code and the end of the section.
The game never writes there, it is mapped executable because the whole section
is, and `/proc/<pid>/mem` writes straight through the read-only page protection
the same way `tradelane.py` has written to `.rdata` since 2026-09-02. So the
stub goes in the padding and the call site gets a `call`. Two ordinary writes.

**Nothing here is remembered on disk, on purpose.** The original bytes of any
site are read back out of the shipped `common.dll`, so "what was here before"
and "is a patch applied" are both answered by comparing the process against the
file. A state file would be a second source of truth that can go stale while
the game is running, and the one that goes stale is the one that restores
garbage into a live process.

Everything reverts on the next launch regardless, because nothing on disk is
touched.
"""

import struct
import sys
from functools import lru_cache

from ..game import flvisits as fl
from . import speed as sp
from .speed import NotRunning

MODULE = "common.dll"

# How much slack to insist on. The stubs are tens of bytes; asking for a few
# hundred means a cave that is only just big enough is rejected rather than
# filled to the brim, and leaves room for the ones still to come.
CAVE_WANTED = 256


@lru_cache(maxsize=8)
def _headers(path):
    """(preferred image base, [(rva, vsize, raw_ptr, raw_size)]) for a PE.

    **Reads a header, not the file.** An earlier version kept the whole DLL in
    the cache, which is 3.8 MB resident across the three modules for the life
    of the server, on a box that runs at a few hundred MB free. Every consumer
    wants either `image_base` or a slice of eleven bytes, so the blob is fetched
    per slice in `disk_bytes` instead.

    Keyed by path, which is safe to cache forever: the file does not change
    while the game holds it open.
    """
    with open(path, "rb") as fh:
        head = fh.read(0x400)
    pe = struct.unpack_from("<I", head, 0x3C)[0]
    if head[pe:pe + 4] != b"PE\0\0":
        raise NotRunning(f"{path} is not a PE file")
    count = struct.unpack_from("<H", head, pe + 6)[0]
    opt_size = struct.unpack_from("<H", head, pe + 20)[0]
    opt = pe + 24
    image_base = struct.unpack_from("<I", head, opt + 28)[0]
    table = opt + opt_size
    out = []
    for i in range(count):
        entry = table + 40 * i
        vsize, rva, raw_size, raw_ptr = struct.unpack_from("<IIII", head, entry + 8)
        out.append((rva, vsize, raw_ptr, raw_size))
    return image_base, out


def module_info(pid, module=MODULE, maps=None):
    """(path, preferred base, load base) for a module, from one maps walk.

    **One walk, not three.** Every read used to resolve the path, parse the
    headers and find the load base independently, and each of those opened and
    parsed all 1536 lines of `/proc/<pid>/maps`. Reading eleven bytes cost
    272 KB and about 3100 parsed lines. Pass `maps` in when a caller already
    has the list.

    The path comes from the process rather than the install layout, because
    the process is the authority on which file it opened and the layout does
    not agree with itself: `common.dll` and `server.dll` live in `EXE/`,
    `content.dll` in `DLLS/BIN/`.
    """
    want = module.lower()
    path, load = None, None
    for lo, _hi, _perms, name in (maps if maps is not None else _mappings(pid)):
        if name.rsplit("/", 1)[-1].lower() != want:
            continue
        path = name
        load = lo if load is None else min(load, lo)
    if path is None:
        raise NotRunning(f"{module} is not mapped; is a game loaded?")
    image_base, _sections = _headers(path)
    return path, image_base, load


def disk_bytes(pid, va, count, module=MODULE):
    """The bytes the shipped file holds at this virtual address.

    This is the definition of "original". Restoring means writing these back,
    and "is it patched" means the process disagrees with them.
    """
    path, image_base, _load = module_info(pid, module)
    _base, sections = _headers(path)
    off = fl._rva_to_offset(sections, va - image_base)
    if off is None:
        raise NotRunning(f"{va:#x} is not inside any section of {module}")
    with open(path, "rb") as fh:
        fh.seek(off)
        return fh.read(count)


def base(pid, module=MODULE, maps=None):
    """Where `module` is loaded in this process."""
    return module_info(pid, module, maps)[2]


def _at(pid, va, module=MODULE, maps=None):
    """A quoted address turned into a live one.

    Addresses here are quoted against each module's own preferred base, which
    is what flhack's are relative to and what the PE header declares. Every
    module in this game happens to load at its preferred base, so the sum is
    usually a no-op, but doing the arithmetic means a relocated module gives a
    wrong-looking read instead of a silent write into a stranger.
    """
    _path, image_base, load = module_info(pid, module, maps)
    return va - image_base + load


def at_offset(pid, module, offset, maps=None):
    """A module-relative offset turned into an address this module's API takes.

    For callers that hold offsets rather than flhack's absolutes. Going through
    the quoted form rather than straight to `load + offset` keeps one
    definition of what an address means here, and `bestpath.py` used to do the
    conversion itself with a helper whose two terms cancelled against `_at`.
    """
    _path, image_base, _load = module_info(pid, module, maps)
    return image_base + offset


def read_raw(pid, addr, count):
    """Read at a literal address, with no rebasing at all.

    For pointers read out of the process, which are already where they say
    they are. Putting one through `_at` would shift it a second time, which is
    invisible today only because every module loads at its preferred base.
    """
    with open(f"/proc/{pid}/mem", "rb") as fh:
        fh.seek(addr)
        return fh.read(count)


def live_bytes(pid, va, count, module=MODULE):
    """Read from the process, at an address quoted against the module base."""
    return read_raw(pid, _at(pid, va, module), count)


def write_bytes(pid, va, data, module=MODULE):
    """Write, read back, and refuse quietly to believe it worked otherwise."""
    addr = _at(pid, va, module)
    with open(f"/proc/{pid}/mem", "r+b") as fh:
        fh.seek(addr)
        fh.write(data)
        fh.seek(addr)
        got = fh.read(len(data))
    if got != data:
        raise NotRunning(
            f"wrote {len(data)} bytes at {va:#x} but read back "
            f"{got.hex(' ')} instead of {data.hex(' ')}")
    return got


def find_cave(pid, size=CAVE_WANTED):
    """Address of the `.text` padding in common.dll, verified empty right now.

    One place, computed rather than searched: the gap between where `.text`'s
    code ends (its VirtualSize) and where the section ends on disk (its raw
    size). That is slack the linker left, the game never writes there, and it
    is mapped executable because the whole section is.

    Searching for the largest zero run instead picks the relocation table,
    which is 17 KB and looks tempting. Relocations happen to be dead here only
    because common.dll loaded at its preferred base, which is a fact about this
    run, not about the format. Padding is dead by construction.

    **Verified in the live process, not from the file.** The file cannot say
    whether something else has already claimed the space, and writing a stub
    over live code is the one mistake in this module that corrupts a running
    game.
    """
    maps = _mappings(pid)
    path, image_base, _load = module_info(pid, MODULE, maps)
    rva, vsize, _raw_ptr, raw_size = _headers(path)[1][0]
    if raw_size <= vsize:
        raise NotRunning(f"{MODULE} .text has no padding to use")
    start = image_base + rva + vsize
    room = raw_size - vsize
    # Align, so the dwords at the front of the cave are aligned too.
    addr = (start + 15) & ~15
    room -= addr - start
    if room < size:
        raise NotRunning(
            f"{MODULE} .text padding is {room} bytes, need {size}")

    # Resolved once, above the loop. It used to be inside it, so `base()`
    # reparsed all 1536 lines of the maps file for every line of the maps file:
    # 116 full reads, 15 MB of text, to check one address.
    live = _at(pid, addr, MODULE, maps)
    for lo, hi, perms, name in maps:
        if lo <= live < hi and name.endswith(MODULE):
            if "x" not in perms:
                raise NotRunning(
                    f"the padding at {addr:#x} is mapped {perms}, not executable")
            break
    else:
        raise NotRunning(f"the padding at {addr:#x} is not mapped")

    seen = live_bytes(pid, addr, room)
    if seen.count(0) != len(seen):
        used = len(seen) - seen.count(0)
        raise NotRunning(
            f"the cave at {addr:#x} is not empty ({used} non-zero bytes); "
            f"something is already there, refusing to overwrite it")
    return addr, room


def find_scratch(pid, size=16):
    """A few writable zero bytes, for anything the stub writes at runtime.

    **The code cave cannot be used for this, and getting that wrong crashes the
    game instantly.** `.text` padding is mapped `r-xp`. `/proc/<pid>/mem` writes
    through that protection, so filling the cave from outside works and looks
    fine; the moment the game's own `mov [cave], eax` runs it takes an access
    violation. Learned on 2026-09-05 by doing exactly that.

    flhack has the same split and solves it the same way: its code goes in
    allocated executable memory, its data at a static address it first makes
    writable with `VirtualProtect`. We cannot change protection, so the data
    has to go somewhere already writable.

    Taken from the middle of a long zero run, not the start: a run that turns
    out to be a live buffer is most likely to be filled from one end.

    **Read in chunks, matched in C, and stopped at the first hit.** The first
    version pulled whole mappings into Python and walked them byte by byte.
    This machine is a 7.6 GB tablet that sits at a few hundred MB free with the
    game up, so that was megabytes of buffer plus millions of interpreter
    steps, and on 2026-09-06 the desktop stalled hard enough to look like a
    freeze. Nothing in the journal, because nothing was wrong at the kernel
    level; it was just this being greedy on a small box.
    """
    want = size * 8  # insist on a comfortably long run, then sit in its middle
    need = bytes(want)
    maps = _mappings(pid)
    _path, image_base, load = module_info(pid, MODULE, maps)
    for lo, hi, perms, name in maps:
        if "w" not in perms or not name.endswith(MODULE):
            continue
        for start, buf in _chunks(pid, lo, hi, overlap=want):
            at = buf.find(need)
            if at == -1:
                continue
            # Extend to the true end of the run, but no further than this
            # chunk: a slightly short measurement costs nothing here.
            end = at + want
            while end < len(buf) and buf[end] == 0:
                end += 1
            middle = (start + at + (end - at) // 2) & ~15
            quoted = middle - load + image_base
            if read_raw(pid, middle, size) == bytes(size):
                return quoted, end - at
    raise NotRunning(f"no writable run of zeros in {MODULE} for {size} bytes")


def _chunks(pid, lo, hi, overlap=0, span=1 << 20):
    """Walk a mapping a megabyte at a time, overlapping so runs are not split."""
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


def _mappings(pid):
    try:
        maps = open(f"/proc/{pid}/maps")
    except OSError as exc:
        raise NotRunning(f"cannot read the process map: {exc}") from exc
    out = []
    with maps:
        for line in maps:
            parts = line.split()
            lo, hi = (int(x, 16) for x in parts[0].split("-"))
            name = " ".join(parts[5:]) if len(parts) > 5 else ""
            out.append((lo, hi, parts[1], name))
    return out


def call_to(site, target, length):
    """`call <target>` padded with nops to exactly `length` bytes.

    `length` is the size of the instructions being displaced, and it is passed
    in rather than assumed because getting it wrong leaves half an instruction
    behind, which is not a crash you can read afterwards.
    """
    if length < 5:
        raise ValueError(f"need 5 bytes for a call, only {length} available")
    rel = target - (site + 5)
    if not -0x80000000 <= rel <= 0x7FFFFFFF:
        raise ValueError(f"{target:#x} is out of reach of a call at {site:#x}")
    return b"\xe8" + struct.pack("<i", rel) + b"\x90" * (length - 5)


def patched(pid, site, length, module=MODULE):
    """Does the process disagree with the shipped file at this site?"""
    return (live_bytes(pid, site, length, module)
            != disk_bytes(pid, site, length, module))


def patch(pid, site, replacement, module=MODULE):
    """Install `replacement` at `site`, but only over the shipped bytes.

    Refusing when what is there is not what the file says is the guard against
    a different build, a second tool, and this tool run twice. Restoring first
    is always available and is never ambiguous.
    """
    length = len(replacement)
    original = disk_bytes(pid, site, length, module)
    current = live_bytes(pid, site, length, module)
    if current != original:
        raise NotRunning(
            f"{module}+{site:#x} holds {current.hex(' ')}, not the shipped "
            f"{original.hex(' ')}; refusing to write over it")
    return write_bytes(pid, site, replacement, module)


def restore(pid, site, length, module=MODULE):
    """Put the shipped bytes back. Safe to call when nothing is patched."""
    return write_bytes(pid, site, disk_bytes(pid, site, length, module), module)


# --- a patch as a list of sites ---------------------------------------------
#
# `[(module, address, replacement), ...]`. Three functions over that list
# replace three hand-rolled copies of the same bookkeeping, and undo is derived
# from do: `bestpath` used to apply five writes of 1, 2, 1, 1 and 2 bytes and
# undo them by restoring 11 bytes at the first address and 1, 1 and 2 at the
# others, a shape re-derived by hand and so a shape that can be wrong.

def install(pid, sites):
    """Apply every site, but only after checking all of them.

    Verification is hoisted above the first write, which is the difference
    that matters: a patch that fails halfway leaves the game in a state no
    caller described, and `state` cannot tell it from a whole one.
    """
    for module, site, replacement in sites:
        original = disk_bytes(pid, site, len(replacement), module)
        current = live_bytes(pid, site, len(replacement), module)
        if current != original:
            raise NotRunning(
                f"{module}+{site:#x} holds {current.hex(' ')}, not the shipped "
                f"{original.hex(' ')}; refusing to write over it")
    for module, site, replacement in sites:
        write_bytes(pid, site, replacement, module)
    return len(sites)


def revert(pid, sites):
    """Put every site back to what the shipped file says."""
    for module, site, replacement in sites:
        restore(pid, site, len(replacement), module)
    return len(sites)


def installed(pid, sites):
    """True only when every site differs from the shipped file.

    All of them, not the first: reporting a half-applied patch as on is how a
    partial failure hides.
    """
    return all(patched(pid, site, len(replacement), module)
               for module, site, replacement in sites)


def main():
    try:
        pid = sp.find_pid()
        print(f"pid {pid}, {MODULE} at {base(pid):#x}")
        addr, room = find_cave(pid)
        print(f"cave at {addr:#x}, {room} bytes of .text padding, all zero")
    except (NotRunning, OSError) as exc:
        sys.exit(str(exc))

