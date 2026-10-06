"""How far away a station is still drawn at all.

    fl.py solardist             # what the file says now
    fl.py solardist 40000       # nothing is culled closer than 40 km
    fl.py solardist --restore   # back to the .vanilla copy

`LODranges` in `DATA/SOLAR/solararch.ini` is a ladder of distances per solar
archetype. The values before the last are where the renderer swaps to a coarser
mesh; **the last one is where it stops drawing the object at all**. 255 of the
file's 321 `[Solar]` sections carry one, and all 836 shipped values are ints.

`stararch.ini` and `asteroidarch.ini` have no `LODranges`, so this is the only
file involved. Asteroid fields are a different mechanism entirely and live in
`drawdist.py`.

## Half of what was asked for is already true

Planets and jump holes are never culled in a stock game: 54 of 55 `PLANET`
archetypes and all 5 `JUMP_HOLE` ones ship with no `LODranges` at all, which
covers 172 of the 511 placed base and jump objects. Jump gates are generous
too, at 50000, and the Nomad gate at 60000.

**Stations are the whole problem.** `miningbase_badlands` and
`miningbase_nomad` stop being drawn at 3000, `docking_fixture` (the mooring you
actually dock at on a planet, 21 of them) at 6000, six `miningbase_*` at 7000,
and most stations at 15000. A mining base disappears at 3 km while a jump gate
is visible at 50.

## A floor, not a multiplier

The control is one absolute distance and it is applied as `last = max(last,
floor)`.

A multiplier was the obvious shape, because `drawdist` is one, and it is wrong
here. The spread of shipped values is two orders of magnitude wide, so 3x moves
`miningbase_badlands` from 3000 to 9000, which is still too close, while moving
`space_arch` from 150000 to 450000, which buys nothing. The complaint is
objects vanishing, so the fix belongs at the bottom of the spread. A floor is
also idempotent: running it twice is running it once.

**Only the last value moves.** The earlier entries are switch points tuned to
apparent size; stretching them keeps a high-poly mesh on screen while the
object is a few pixels across, which costs and shows nothing. Moving the cull
alone means the cheapest mesh keeps being drawn further out, which is the whole
of what was asked for. The number of values never changes, so the ladder cannot
fall out of step with the model's own LODs.

The ceiling is 150000 because that is the largest value vanilla itself ships,
on `space_arch` and `space_arch_asteroid`, and both are placed in a system. Past
that, nothing in the shipped data says the engine is happy.

## Two archetypes are invisible on purpose, and two kinds are traps

`fuchu_core` ships `0, 1` and `planet_storm_5000` ships `0, 1, 2, 3, 4, 5`.
Both are placed in a system and both are meant never to be drawn. The next
value up anywhere in the file is 1000, so `HIDDEN = 100` sits in a clear gap
rather than on a judgement call. Raising these would put an object on screen
that the designers hid, which reads as a broken game rather than a mod.

`suprise_*`, the game's own spelling, is the ambush spawn set: 35
`MISSION_SATELLITE` archetypes at 1000 and 2 `DESTROYABLE_DEPOT` baits at 1800.
Drawing those early shows you the trap before it springs.

Everything else is raised, the 23 `rm_*` random-mission props included, whose
battleships have a 4000 radius and currently vanish at 15 to 20 km.

## When it lands

**On the next launch, not the next system load.** `EXE/freelancer.ini` reads
`solar = solar\\solararch.ini` once at startup, and by its own comment before
the universe, because the universe inspects solar `OBJECT_TYPE` values.

The three rules from `persist.py` are not restated here because this module
uses that module's own `_backup` and `_save`: round trip before replacing, swap
atomically, and never overwrite an existing `.vanilla`.
"""
# Measured facts and open questions: docs/patching-files.md

import argparse
import os
import sys

import bini

from ..game import flvisits as fl
from .persist import WriteFailed, _backup, _save

SECTION = "solar"
KEY = "lodranges"
NAME = "nickname"
TYPE = "type"

# A shipped cull below this means the object is hidden on purpose. Exactly two
# archetypes are, at 1 and 5, and the next value up in the file is 1000.
HIDDEN = 100
# The ambush spawns, in the game's own spelling. `surprise` is there too: two
# DESTROYABLE_DEPOTs that are the bait.
AMBUSH = ("suprise", "surprise")
# 150000 is the largest value vanilla ships, on an archetype that is placed.
SANE = (5000, 150000)


def _path(game_dir):
    return fl.ipath(fl.ipath(fl.ipath(game_dir, "DATA"), "SOLAR"),
                    "solararch.ini")


def _source(path):
    """The pristine file if one was kept, else the file itself.

    The floor is absolute, so it is always measured against what shipped.
    Building on the live file instead would make a lower floor a no-op: values
    already raised are above it and would simply stay there.
    """
    keep = path + ".vanilla"
    return keep if os.path.exists(keep) else path


def touchable(nickname, ranges):
    """Whether this archetype's cull distance may be raised."""
    return (len(ranges) >= 2
            and ranges[-1] >= HIDDEN
            and not nickname.lower().startswith(AMBUSH))


def _ladders(path):
    """[(nickname, type, ranges)] for every [Solar] carrying LODranges."""
    out = []
    for name, entries in bini.decode(open(path, "rb").read()):
        if name.lower() != SECTION:
            continue
        row = {key.lower(): values for key, values in entries}
        lod = row.get(KEY)
        if not lod:
            continue
        out.append((str((row.get(NAME) or [""])[0]),
                    str((row.get(TYPE) or ["?"])[0]).upper(),
                    [float(v) for v in lod]))
    return out


_CACHE = (None, None)


def survey(game_dir=None):
    """[(nickname, type, shipped cull, current cull, touchable)].

    Cached on the two files' mtimes, the same bargain `drawdist.survey` makes
    and for the same reason: the Engine strip asks for this on a poll and the
    answer only changes when a button is pressed. One file here rather than
    158, so the stamp is a pair rather than a tuple of 158.
    """
    global _CACHE
    game_dir = game_dir or fl.DEFAULT_GAME
    path = _path(game_dir)
    source = _source(path)
    stamp = (os.stat(path).st_mtime_ns, os.stat(source).st_mtime_ns)
    if _CACHE[0] == stamp:
        return _CACHE[1]

    # Paired by nickname rather than by position: the order is the same in
    # practice, and relying on that would hand a mismatched file the wrong
    # vanilla number rather than an error.
    live = {nick.lower(): ranges for nick, _kind, ranges in _ladders(path)}
    out = []
    for nick, kind, base in _ladders(source):
        now = live.get(nick.lower(), base)
        out.append((nick, kind, base[-1], now[-1], touchable(nick, base)))
    _CACHE = (stamp, out)
    return out


def setting(rows):
    """The floor in force, or None when the file is as shipped.

    Every raised archetype was raised to the same number, so one distinct
    value is the floor. Anything else, including nothing raised, answers None:
    the file then is not the product of one run of this.
    """
    raised = {now for _n, _k, base, now, ok in rows if ok and now > base}
    return raised.pop() if len(raised) == 1 else None


def apply(floor, game_dir=None):
    """Raise every touchable cull distance to `floor`. Returns how many moved."""
    low, high = SANE
    if not low <= floor <= high:
        raise WriteFailed(
            f"{floor:g} is outside {low:g} to {high:g}. The top is the largest "
            f"value vanilla itself ships; past it nothing in the game's own "
            f"data says the engine is happy. Nothing was written.")
    game_dir = game_dir or fl.DEFAULT_GAME
    path = _path(game_dir)
    sections = bini.decode(open(_source(path), "rb").read())

    moved = 0
    for name, entries in sections:
        if name.lower() != SECTION:
            continue
        row = {key.lower(): values for key, values in entries}
        lod = row.get(KEY)
        if not lod:
            continue
        nick = str((row.get(NAME) or [""])[0])
        ranges = [float(v) for v in lod]
        if not touchable(nick, ranges) or ranges[-1] >= floor:
            continue
        for i, (key, values) in enumerate(entries):
            if key.lower() == KEY:
                # The earlier values are carried across untouched, so they keep
                # the int encoding the file shipped with.
                entries[i] = (key, list(values[:-1]) + [int(floor)])
        moved += 1

    _backup(path)
    _save(path, sections)
    return moved


def restore(game_dir=None):
    """Put the shipped file back. False when there is no `.vanilla` to go to."""
    game_dir = game_dir or fl.DEFAULT_GAME
    path = _path(game_dir)
    keep = path + ".vanilla"
    if not os.path.exists(keep):
        return False
    _save(path, bini.decode(open(keep, "rb").read()))
    return True


def _report(rows):
    live = [r for r in rows if r[4]]
    held = [r for r in rows if not r[4]]
    floor = setting(rows)
    print(f"{len(rows)} archetypes carry LODranges, {len(live)} of them may be "
          f"raised")
    if not live:
        return
    print(f"  shipped: closest cull {min(r[2] for r in live):.0f}, "
          f"median {sorted(r[2] for r in live)[len(live) // 2]:.0f}, "
          f"furthest {max(r[2] for r in live):.0f}")
    print(f"  now:     closest cull {min(r[3] for r in live):.0f}, "
          f"median {sorted(r[3] for r in live)[len(live) // 2]:.0f}, "
          f"furthest {max(r[3] for r in live):.0f}")
    raised = sum(1 for r in live if r[3] > r[2])
    print(f"  {raised} raised, floor in force "
          f"{'none, this is the shipped file' if floor is None else f'{floor:.0f}'}")
    print(f"  {len(held)} left alone: hidden on purpose or an ambush spawn")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("floor", nargs="?", type=float,
                    help="nothing is culled closer than this")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--restore", action="store_true", help="undo, from .vanilla")
    args = ap.parse_args()

    try:
        if args.restore:
            print("solararch.ini restored" if restore(args.game)
                  else "nothing to restore: no .vanilla copy was ever made")
        elif args.floor:
            moved = apply(args.floor, args.game)
            print(f"{moved} archetypes now cull no closer than {args.floor:g}")
            print("relaunch the game; solararch.ini is read once at startup")
        _report(survey(args.game))
    except (WriteFailed, OSError, ValueError) as exc:
        sys.exit(str(exc))
