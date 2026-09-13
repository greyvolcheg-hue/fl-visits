"""Write the speeds the running game is using back into the game's files.

    fl.py persist            # show what would be written, change nothing
    fl.py persist --write

`speed.py` and `thrusters.py` change the live process, which is what makes them
useful mid-flight and also what makes the change die with the game. This puts
the same numbers where the next launch will read them:

    cruise speed   DATA/constants.ini          [EngineEquipConsts] CRUISING_SPEED
    thrusters      DATA/EQUIPMENT/st_equip.ini `max_force` on six [Thruster]s

`max_force = speed * 600`, the conversion `thrusters.py` already uses in the
other direction.

Writing while the game runs is fine and is the expected case: Freelancer reads
both files once at startup, so the write cannot disturb the session in front of
you and the next launch picks it up. Until that launch the file and the process
legitimately disagree.

Three rules that are not negotiable, because the failure they prevent is a game
that will not start:

  * re-decode what was encoded before replacing anything, and compare it key by
    key against what was intended. A BINI file the game cannot parse is not a
    thing you find out about until launch.
  * replace atomically through a temp file in the same directory. A half
    written constants.ini is worse than an unchanged one.
  * back up to `<name>.vanilla` only when that file does not exist yet. It is
    the pristine copy; overwriting it with already-modded content destroys the
    only way back.
"""

import argparse
import os
import sys
import tempfile

import bini

from . import speed as sp
from . import thrusters as th
from ..game import flvisits as fl

CRUISE_SECTION = "engineequipconsts"
CRUISE_KEY = "cruising_speed"
THRUSTER_SECTION = "thruster"
FORCE_KEY = "max_force"
IDS_KEY = "ids_name"


class WriteFailed(Exception):
    """The file was not changed, and the reason is in the message."""


def _paths(game_dir):
    data = fl.ipath(game_dir, "DATA")
    return (fl.ipath(data, "constants.ini"),
            fl.ipath(fl.ipath(data, "EQUIPMENT"), "st_equip.ini"))


def _backup(path):
    """Keep the first version ever seen, and never touch it again."""
    keep = path + ".vanilla"
    if not os.path.exists(keep):
        try:
            with open(path, "rb") as src, open(keep, "wb") as dst:
                dst.write(src.read())
        except PermissionError as exc:
            raise WriteFailed(
                f"cannot keep a vanilla copy beside {os.path.basename(path)}: "
                f"{exc}. Nothing was changed. On Windows a game under Program "
                "Files needs an elevated shell, or an install somewhere else."
            ) from exc
        return keep
    return None


def write_raw(path, blob):
    """Replace a file's bytes atomically, keeping the mode it had.

    **Not every file this project writes is BINI.** `_save` below encodes an
    INI; `content.dll` and `server.dll` are PEs and `callsign.py` and
    `bestpath.py` patch a handful of bytes in them. Both wanted the same
    temp-plus-`os.replace` swap, so it lives here once rather than twice.

    **It puts the mode back.** `mkstemp` creates 0600 and the game has to be
    able to read what it wrote. The BINI writer below does not do that and gets
    away with it only because the game runs as the same user.
    """
    folder = os.path.dirname(path)
    try:
        mode = os.stat(path).st_mode & 0o777
        handle, temp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    except PermissionError as exc:
        raise WriteFailed(
            f"cannot write in {folder}: {exc}. On Windows a game under Program "
            "Files needs an elevated shell, or an install somewhere else; on "
            "Linux check who owns the prefix.") from exc
    try:
        with os.fdopen(handle, "wb") as fh:
            fh.write(blob)
        os.chmod(temp, mode)
        os.replace(temp, path)
    except Exception:
        if os.path.exists(temp):
            os.unlink(temp)
        raise
    back = open(path, "rb").read()
    if back != blob:
        raise WriteFailed(f"{os.path.basename(path)} read back differently "
                          "from what was written; restore it before trusting it")


def _save(path, sections):
    """Encode, prove it decodes back to the same thing, then swap it in."""
    blob = bini.encode(sections)

    try:
        back = bini.decode(blob)
    except Exception as exc:
        raise WriteFailed(f"{os.path.basename(path)}: encoded to something "
                          f"unreadable, not written ({exc})") from exc
    if _flat(back) != _flat(sections):
        raise WriteFailed(f"{os.path.basename(path)}: round trip changed the "
                          "contents, not written")

    folder = os.path.dirname(path)
    try:
        handle, temp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    except PermissionError as exc:
        # **The common Windows case, and it reads as a bug if it is not named.**
        # A game installed under `C:\Program Files (x86)` is not writable by a
        # normal user, so every writer in `live/` stops here, on the temp file
        # rather than on the game file, which is confusing on its own.
        raise WriteFailed(
            f"cannot write in {folder}: {exc}. On Windows a game under "
            "Program Files needs an elevated shell, or an install somewhere "
            "else; on Linux check who owns the prefix.") from exc
    try:
        with os.fdopen(handle, "wb") as fh:
            fh.write(blob)
        os.replace(temp, path)
    except PermissionError as exc:
        os.unlink(temp)
        raise WriteFailed(
            f"{os.path.basename(path)}: cannot be replaced ({exc}). On Windows "
            "that means something else has the file open.") from exc
    except Exception:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def _flat(sections):
    """Comparable form: floats are rounded, since BINI stores 32-bit."""
    out = []
    for name, entries in sections:
        for key, values in entries:
            out.append((name.lower(), key.lower(),
                        tuple(round(v, 3) if isinstance(v, float) else v
                              for v in values)))
    return out


def plan(game_dir=None, pid=None):
    """What would be written: (cruise speed, [(ids, nickname, speed)]).

    Reads the live process, so it raises `speed.NotRunning` when the game is
    not up. There is nothing to persist in that case, which is the honest
    answer rather than writing whatever the file already said.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    pid = pid or sp.find_pid()
    cruise = sp.read(pid, sp.locate(pid))
    _, rows = th.read_all(pid)
    return cruise, [(ids, nick, value) for ids, nick, _addr, value in rows]


def write(game_dir=None, pid=None):
    """Persist the live speeds. Returns a list of lines describing what moved."""
    game_dir = game_dir or fl.DEFAULT_GAME
    cruise, thrusters = plan(game_dir, pid)
    constants, equip = _paths(game_dir)

    low, high = sp.SANE
    if not low <= cruise <= high:
        raise WriteFailed(f"cruise speed {cruise:g} is outside {low:g}..{high:g}")
    tlow, thigh = th.SANE_SPEED
    for _ids, nick, value in thrusters:
        if not tlow <= value <= thigh:
            raise WriteFailed(f"{nick} at {value:g} is outside {tlow:g}..{thigh:g}")

    told = []

    sections = bini.decode(open(constants, "rb").read())
    before = None
    hit = False
    for name, entries in sections:
        if name.lower() != CRUISE_SECTION:
            continue
        for i, (key, values) in enumerate(entries):
            if key.lower() == CRUISE_KEY:
                before = values[0] if values else None
                entries[i] = (key, [float(cruise)])
                hit = True
    if not hit:
        # Vanilla constants.ini has no CRUISING_SPEED at all; the engine
        # default lives in the executable. Add the key rather than failing.
        for name, entries in sections:
            if name.lower() == CRUISE_SECTION:
                entries.append(("CRUISING_SPEED", [float(cruise)]))
                hit = True
                break
    if not hit:
        raise WriteFailed("constants.ini has no [EngineEquipConsts] section")

    kept = _backup(constants)
    _save(constants, sections)
    told.append(f"cruise speed {before if before is not None else '(absent)'}"
                f" -> {cruise:g}")
    if kept:
        told.append(f"backed up {os.path.basename(kept)}")

    sections = bini.decode(open(equip, "rb").read())
    wanted = {ids: value for ids, _nick, value in thrusters}
    changed = 0
    for name, entries in sections:
        if name.lower() != THRUSTER_SECTION:
            continue
        fields = {k.lower(): v for k, v in entries}
        ids = fields.get(IDS_KEY, [None])[0]
        if ids not in wanted:
            continue
        force = float(wanted[ids]) * th.PER_SPEED
        for i, (key, values) in enumerate(entries):
            if key.lower() == FORCE_KEY:
                entries[i] = (key, [force])
                changed += 1
    if changed != len(wanted):
        raise WriteFailed(f"matched {changed} of {len(wanted)} thrusters in "
                          "st_equip.ini, not written")

    kept = _backup(equip)
    _save(equip, sections)
    told.append(f"{changed} thrusters written")
    if kept:
        told.append(f"backed up {os.path.basename(kept)}")

    return told


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--write", action="store_true", help="actually write")
    args = ap.parse_args()

    try:
        if args.write:
            for line in write(args.game):
                print(line)
        else:
            cruise, thrusters = plan(args.game)
            print(f"cruise speed {cruise:g}")
            for _ids, nick, value in thrusters:
                print(f"  {nick:<20} {value:g}  (max_force {value * th.PER_SPEED:g})")
            print("\nnothing written; pass --write")
    except (sp.NotRunning, WriteFailed, OSError) as exc:
        sys.exit(str(exc))

