#!/usr/bin/env python3
"""Let Set Best Path route through jump holes, not just jump gates.

    bestpath.py          # is it on?
    bestpath.py --on
    bestpath.py --off

The game ships two route tables and uses the duller one. `Universe\\
shortest_legal_path.ini` knows only jump gates; `Universe\\
systems_shortest_path.ini` includes jump holes, which are often the shortcut.
Both have been sitting in the install since 2003.

This is flhack's "Best path uses jump holes", and unlike everything else ported
here it needs **no injected code at all**: five bytes, in three places.

    server.dll  +0x1ace3      0a -> 03        gates and holes are one type
    server.dll  +0x1acec   eb 05 -> 74 07     the branch that follows from it
    content.dll +0x89492      c4 -> 8c        which filename gets read
    content.dll +0x89512      8c -> c4        the other half of that swap
    content.dll +0x5fa6c   75 04 -> 89 f6     drop the waypoint on the way in

**The filename swap is literally a swap.** Those two bytes are the low halves
of a pair of pointers sitting 0x80 apart, and reading what they point at says
the whole story:

    0x70a828c  'Universe\\shortest_legal_path.ini'      gates only
    0x70a82c4  'Universe\\systems_shortest_path.ini'    holes too

Exchanging them makes the game load the other file. Nothing is written to disk
and neither file is touched.

## The one thing to know before using it

**`content.dll` and `server.dll` are loaded when a game is loaded**, so the
patch can only go in while you are in space, and it is gone again after loading
a save. flhack solves that by hooking the load itself, which needs a stub in
the process; pressing the button again is cheaper and hides nothing.

## How the build is told apart

flhack keys off one byte in each module, and for `server.dll` that byte is the
very one the patch changes, from 0x0A to 0x03. That is not a coincidence to
work around: it means "already patched" and "wrong build" are the same check,
read from the same place, and neither can be mistaken for the other.
"""

import argparse
import sys

import inject as ij
import speed as sp
from speed import NotRunning

SERVER, CONTENT = "server.dll", "content.dll"

# flhack's server10_addr / content10_addr tables, kept as the module-relative
# offsets they are there rather than as the absolute addresses its comments
# spell out, so a relocated module cannot silently land somewhere else.
BUILDS = {
    10: {"type": 0x1ACE3, "path": 0x89492, "jump": 0x5FA6C},
    11: {"type": 0x1B1D3, "path": 0x897D2, "jump": 0x5F711},
}

VANILLA_TYPE = 0x0A   # what the type byte reads before patching
PATCHED_TYPE = 0x03   # and after; also flhack's build fingerprint
CONTENT_MARK = 0xC0   # confirms which build content.dll is
CONTENT_MARK_AT = {10: 0xAAC6B, 11: 0xAAD6B}

PATH_APART = 0x80     # the two filename pointers, and the gap between them


def detect(pid):
    """(version, the type byte), by the two bytes flhack fingerprints.

    The type byte comes back with the version because it is also the on/off
    answer: the patch changes it from 0x0A to 0x03, so "wrong build" and
    "already patched" are one read from one place. `state` used to read it a
    second time.

    Checks `content.dll` as well as `server.dll` rather than trusting one:
    they are separate files and a mismatched pair is exactly the case where
    writing five bytes from the wrong table does damage.
    """
    for version, off in BUILDS.items():
        try:
            kind = ij.live_bytes(
                pid, ij.at_offset(pid, SERVER, off["type"]), 1, SERVER)
            mark = ij.live_bytes(
                pid, ij.at_offset(pid, CONTENT, CONTENT_MARK_AT[version]),
                1, CONTENT)
        except (NotRunning, OSError):
            continue
        if (kind and kind[0] in (VANILLA_TYPE, PATCHED_TYPE)
                and mark == bytes([CONTENT_MARK])):
            return version, kind
    raise NotRunning(
        "server.dll and content.dll are neither of the two builds flhack "
        "knows, or no game is loaded yet")


def sites(pid, version, low_a=b"\0", low_b=b"\0"):
    """The patch, as the list `inject.install`, `revert` and `installed` share.

    The two filename halves are given as the values they swap to, so `revert`
    restoring by length gets the shape right without anyone re-deriving it.
    Only `install` cares what those bytes are; the other two read lengths, so
    they may leave the defaults.
    """
    off = BUILDS[version]
    type_at = ij.at_offset(pid, SERVER, off["type"])
    path_at = ij.at_offset(pid, CONTENT, off["path"])
    jump_at = ij.at_offset(pid, CONTENT, off["jump"])
    return [
        (SERVER, type_at, bytes([PATCHED_TYPE])),
        (SERVER, type_at + 9, b"\x74\x07"),
        (CONTENT, path_at, low_b),
        (CONTENT, path_at + PATH_APART, low_a),
        (CONTENT, jump_at, b"\x89\xf6"),
    ]


def state(pid=None, version=None):
    """(on?, version). On means **all five** sites differ from the shipped file.

    Not just the type byte. Five separate writes can stop halfway if the game
    unloads `content.dll` between them, which is the documented normal case
    here since these libraries load with the save. Reading the first byte alone
    reported that as fully on.
    """
    pid = pid or sp.find_pid()
    if version is None:
        version, _kind = detect(pid)
    return ij.installed(pid, sites(pid, version)), version


def apply(on=True, pid=None, version=None):
    """Turn jump holes on or off in the router. Returns the version used."""
    pid = pid or sp.find_pid()
    if version is None:
        version, _kind = detect(pid)
    off = BUILDS[version]
    path_at = ij.at_offset(pid, CONTENT, off["path"])

    # The two filename pointers are exchanged, so read both before touching
    # either. Writing the first and then reading it back as the source for the
    # second is how a swap turns into "both the same".
    low_a = ij.live_bytes(pid, path_at, 1, CONTENT)
    low_b = ij.live_bytes(pid, path_at + PATH_APART, 1, CONTENT)
    if low_a == low_b:
        raise NotRunning(
            f"the two path pointers both end {low_a.hex()}; that is not a "
            f"pair to swap, refusing")

    patch = sites(pid, version, low_a, low_b)
    if on:
        # Every site is checked against the shipped file before any is
        # written. Five separate writes could otherwise stop halfway, and the
        # old `state` read only the first byte, so a half-applied patch
        # reported as fully on.
        ij.install(pid, patch)
    else:
        ij.revert(pid, patch)
    return version


def routes(pid=None, version=None):
    """[(slot address, filename)] for both pointers, by following each one.

    **Which slot the router reads is not claimed here**, because it has not
    been established: flhack exchanges the two and says the effect is jump
    holes, which pins down the change without pinning down the direction. The
    honest report is both slots and what each points at; the proof is flying
    it.
    """
    pid = pid or sp.find_pid()
    if version is None:
        version, _kind = detect(pid)
    path_at = ij.at_offset(pid, CONTENT, BUILDS[version]["path"])
    out = []
    for at in (path_at, path_at + PATH_APART):
        pointer = int.from_bytes(ij.live_bytes(pid, at, 4, CONTENT), "little")
        # `read_raw`, not `live_bytes`: this came out of the process and is
        # already where it says it is. Rebasing it a second time is invisible
        # only while content.dll loads at its preferred base.
        text = ij.read_raw(pid, pointer, 64).split(b"\0", 1)[0]
        out.append((at, text.decode("latin-1", "replace")))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--on", action="store_true", help="use jump holes too")
    ap.add_argument("--off", action="store_true", help="back to gates only")
    args = ap.parse_args()

    try:
        pid = sp.find_pid()
        # Detected once and threaded through, rather than each of apply,
        # state and routes fingerprinting the build again.
        version, _kind = detect(pid)
        if args.on or args.off:
            apply(args.on, pid, version)
            print(f"jump holes {'on' if args.on else 'off'} (build v{version})")
        on, version = state(pid)
        print(f"server.dll/content.dll v{version}, jump holes "
              f"{'ON' if on else 'off'}")
        for at, name in routes(pid, version):
            print(f"  slot {at:#x} -> {name}")
        if on:
            print("  lost when you load a save; run --on again after loading")
    except (NotRunning, ValueError, OSError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
