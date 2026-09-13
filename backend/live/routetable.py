"""Put shorter routes into the table Set Best Path actually reads.

    fl.py routetable            # what would change, change nothing
    fl.py routetable --write
    fl.py routetable --revert   # back to the shipped table

Freelancer answers Set Best Path out of a precomputed table, and it is not
shortest paths. `game/jumps.py` builds the real graph from the system files and
this writes the answers back.

## Gates only, and the reason is a star

**The first version of this wrote hole routes into the file the game reads, and
it flew the owner into the sun.** Settled 2026-09-13, from Battleship Matsumoto
to Ohashi Border Station, which is Hokkaido to Shikoku:

    what was written   Hokkaido > Kyushu > Shikoku    2 jumps, 93 km of flying
    what the game did  pointed the course at 0,0,0, where `Ku05_Sun` sits

**The engine can only follow a hop that has a jump gate.** Hokkaido to Kyushu
exists only as a hole, the router could not turn that hop into a waypoint, and
it fell back to the system origin, which in Hokkaido is a red dwarf.

The three shipped tables say the same thing by their own shape, and this is the
measurement that should have been made first:

    shortest_legal_path.ini      35 systems, 1225 rows, **0** rows with a gateless hop
    shortest_illegal_path.ini    46 systems, 2071 rows
    systems_shortest_path.ini    50 systems, 2079 rows, 1440 rows with a gateless hop

`shortest_legal_path.ini` is gates-only **by construction**, and it is the one
Set Best Path reads. That is not an accident of content, it is the contract the
router relies on. The 15 systems no gate can reach are simply absent from it,
which is why Chugoku answers "no best path" in a stock game and is right to.

## What is written now

Gates-only shortest paths, into `shortest_legal_path.ini` alone, at that file's
own width. Measured over its 1225 rows: **136 shorter, 0 longer, 0 with no
gates-only route at all, and 0 naming a system the file does not already
list.** The last number is the one that matters, because with holes allowed it
is 234, and widening the file to fit them is exactly what broke it.

**The headline win never needed a hole.** New York to New London is four jumps
in the shipped table, `li01 > li02 > iw04 > br02 > br01`, and three through
Magellan, `li01 > iw03 > br02 > br01`. Every one of those is a gate. The hole
routes were never where the improvement was.

**`systems_shortest_path.ini` is not touched at all.** The game does not read
it, and the byte patch that made it read it cannot work: `content.dll` and
`server.dll` are reloaded by the same world load that reads the table, so a
patch applied afterwards is too late by construction. Hole routes live in
`Map -> Best Path`, which is a reader and needs no engine.

Alaska and Omicron Minor stay out, because they are out of the shipped table:
Alaska is story-locked and that exclusion is the designers' own.

The three rules from `persist.py` are not restated here because this file uses
that module's own `_backup` and `_save`: round trip before replacing, swap
atomically, and never overwrite an existing `.vanilla`.
"""

import argparse
import os

import bini

from . import bestpath as bp
from .persist import WriteFailed, _backup, _save
from ..game import flvisits as fl
from ..game import jumps as jm

# The one file Set Best Path reads, and the one this writes. It is its own
# shape: nothing is widened, so no row can name a system it has never listed.
# Two modes, and the difference is which file the engine is reading.
#
#   gates   the shipped arrangement. The router reads `shortest_legal_path.ini`
#           and treats a jump hole as a kind of object it cannot make a
#           waypoint from, so every hop must have a gate.
#   holes   five bytes in `server.dll` and `content.dll`, flhack's, which swap
#           which file is read **and** tell the router that gates and holes are
#           one type. Then the file it reads is `systems_shortest_path.ini` and
#           hole routes become flyable.
#
# **The two halves of `holes` are not separable.** The filename swap alone
# hands the router routes it is not allowed to fly and it points the course at
# the system origin, which is usually a star. `bestpath.file_write` owns those
# bytes; this module owns the tables.
MODES = {
    "gates": {"file": "shortest_legal_path.ini", "holes": False, "patch": False},
    "holes": {"file": "systems_shortest_path.ini", "holes": True, "patch": True},
}
TARGETS = tuple(m["file"] for m in MODES.values())
PATH_KEY = "path"


def _path(game_dir, name):
    return fl.ipath(fl.ipath(fl.ipath(game_dir, "DATA"), "UNIVERSE"), name)


def _shipped(game_dir, name):
    """The file as the game shipped it, which is `.vanilla` once we have run.

    Reading the live file instead would make this build on its own output: the
    second run would take its shape from the first. Same trap that made
    `jumps.check` compare the graph against a table this module had written.
    """
    path = _path(game_dir, name)
    return path + ".vanilla" if os.path.exists(path + ".vanilla") else path


def content(game_dir=None, by="jumps", mode="gates"):
    """(sections, outside, holed) : the table, ready for `_save`.

    `outside` counts rows naming a system the shipped file does not list and
    `holed` counts rows with a hop no gate can make. **Both must be zero**, and
    they are the two checks the first version of this module did not have: the
    first lets a route point at a system the router has no index for, and the
    second is what pointed a course at a star.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    rule = MODES[mode]
    jumps = jm.load_jumps(game_dir)
    sections = bini.decode(open(_shipped(game_dir, rule["file"]), "rb").read())
    known = set()
    for _s, pairs in sections:
        for key, values in pairs:
            if key.lower() == PATH_KEY:
                known.update(str(v).lower() for v in values)

    outside = holed = 0
    fresh = []
    for section, pairs in sections:
        rows = []
        for key, values in pairs:
            if key.lower() != PATH_KEY or len(values) < 2:
                rows.append((key, values))
                continue
            src, dst = str(values[0]), str(values[1])
            # `holes=False`, which is the whole point: a route the engine
            # cannot fly is worse than a longer one it can.
            steps = jm.route(jumps, src.lower(), dst.lower(), by=by,
                             holes=rule["holes"])
            if steps is None:
                # The shipped table knows a pair the graph cannot join on
                # gates. Keep the game's own answer rather than emptying it.
                rows.append((key, values))
                continue
            if not rule["holes"] and any(s["jump"]["kind"] != "gate"
                                         for s in steps):
                holed += 1
            chain = [src] + [jumps[s["jump"]["id"]]["to_sys"] for s in steps]
            if any(x.lower() not in known for x in chain):
                outside += 1
            rows.append((key, [src, dst] + chain))
        fresh.append((section, rows))
    return fresh, outside, holed


def _rows(sections):
    return [(str(v[0]).lower(), str(v[1]).lower(), tuple(str(x).lower() for x in v[2:]))
            for _s, pairs in sections for k, v in pairs if k.lower() == PATH_KEY]


def plan(game_dir=None, by="jumps", mode="gates"):
    """(changed, saved, outside, holed) against what is on disk now."""
    game_dir = game_dir or fl.DEFAULT_GAME
    fresh, outside, holed = content(game_dir, by, mode)
    want = {(a, b): hops for a, b, hops in _rows(fresh)}
    live = bini.decode(open(_path(game_dir, MODES[mode]["file"]), "rb").read())
    have = {(a, b): hops for a, b, hops in _rows(live)}
    changed = saved = 0
    for pair, hops in want.items():
        was = have.get(pair)
        if was is None or was != hops:
            changed += 1
            if was:
                saved += max(len(was) - len(hops), 0)
    return changed, saved, outside, holed


def write(game_dir=None, by="jumps", mode="gates"):
    """Write the table for a mode, and set the five bytes that mode needs.

    **The table and the bytes go together or not at all.** A hole table with
    the bytes off is the star; gates with them on reads the wrong file.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    rule = MODES[mode]
    fresh, outside, holed = content(game_dir, by, mode)
    if holed:
        raise WriteFailed(
            f"{holed} routes have a hop with no jump gate. The engine cannot "
            f"turn one into a waypoint and points the course at the system "
            f"origin, which is usually the star. Nothing was written.")
    if outside:
        raise WriteFailed(
            f"{outside} routes name a system {rule['file']} does not list, so "
            f"the "
            f"router has no index for them. Nothing was written.")
    changed, saved, _o, _h = plan(game_dir, by, mode)
    path = _path(game_dir, rule["file"])
    _backup(path)
    _save(path, fresh)
    bp.file_write(rule["patch"], game_dir)
    return changed, saved


def revert(game_dir=None):
    """Put the shipped table back, and any file an older version wrote."""
    game_dir = game_dir or fl.DEFAULT_GAME
    done = []
    for name in TARGETS:
        path = _path(game_dir, name)
        keep = path + ".vanilla"
        if not os.path.exists(keep):
            continue
        with open(keep, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        done.append(name)
    bp.file_write(False, game_dir)
    return done


def state(game_dir=None):
    """(mode the engine is in, systems listed, rows, .vanilla?, shipped?)."""
    game_dir = game_dir or fl.DEFAULT_GAME
    _v, patched = bp.file_state(game_dir)
    mode = "holes" if patched else "gates"
    path = _path(game_dir, MODES[mode]["file"])
    rows = _rows(bini.decode(open(path, "rb").read()))
    keep = path + ".vanilla"
    stock = not os.path.exists(keep) or (
        open(path, "rb").read() == open(keep, "rb").read())
    return mode, len({a for a, _b, _h in rows}), len(rows), os.path.exists(keep), stock


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    # No default: a bare run should report on the mode the engine is in, not
    # on one it is not, which read as a contradiction with the state line.
    ap.add_argument("--mode", choices=sorted(MODES),
                    help="gates: what the engine can fly as shipped. "
                         "holes: five bytes plus the wider table")
    ap.add_argument("--write", action="store_true", help="do it")
    ap.add_argument("--revert", action="store_true",
                    help="shipped tables and shipped bytes")
    ap.add_argument("--flying", action="store_true",
                    help="least distance instead of fewest jumps")
    args = ap.parse_args()
    by = "flying" if args.flying else "jumps"

    try:
        if args.mode is None:
            args.mode = state(args.game)[0]
        if args.revert:
            done = revert(args.game)
            print("restored " + (", ".join(done) if done else "nothing")
                  + ", and the five bytes are out")
        elif args.write:
            changed, saved = write(args.game, by, args.mode)
            print(f"{MODES[args.mode]['file']}: {changed} routes written, "
                  f"{saved} jumps saved")
            print("load a save; the table and the libraries are both read then")
        else:
            changed, saved, outside, holed = plan(args.game, by, args.mode)
            print(f"mode {args.mode} would write {changed} routes into "
                  f"{MODES[args.mode]['file']}, {saved} jumps saved")
            if holed or outside:
                print(f"  REFUSED: {holed} gateless hops, {outside} unlisted systems")
            print("  nothing written; --write to do it")
        mode, systems, rows, kept, stock = state(args.game)
        print(f"\nthe engine is in {mode} mode, reading "
              f"{MODES[mode]['file']}: {rows} rows over {systems} systems, "
              f"{'shipped' if stock else 'ours'}{', .vanilla kept' if kept else ''}")
    except (WriteFailed, OSError, ValueError) as exc:
        raise SystemExit(str(exc))
