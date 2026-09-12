"""Where the levels are, and how far the ladder goes.

    fl.py levels                       # what the table says now
    fl.py levels --to 50 --worth 1.16e9
    fl.py levels --restore             # back to the .vanilla copy

**`DATA/MISSIONS/ptough.ini` is the whole level system.** One section,
`[PlayerToughnessScale]`, 39 rows of `ptough_graph_pt = <worth>, <level>`,
running from `0, 0` to `2409599, 38`. That is the table behind all three
numbers the player info screen shows:

    Current Level              which row your worth has passed
    Current Worth              money plus the ship plus everything on it
    Next Level Requirements    the next row's worth, minus yours

Checked against a live game on 2026-09-12 rather than assumed: worth 757221
sits between row 29 (738187) and row 30 (842492), the screen said level 29, and
842492 - 757221 = 85271, which is exactly what it showed for the next level.

**`[Player] rank` in a save is a cache of that lookup, not the source.** So
editing a save to change level is pointless: the game recomputes it from worth
and puts it back. The ladder is the only thing worth changing, and it is a
file, so the change survives a reload and costs no patching.

**The name is not decoration and is the one real risk here.**
`PlayerToughnessScale` is what the game calls this, so the same curve very
likely also decides how tough the world thinks you are. Stretching the ladder
to make levels cost more should therefore make encounters harder, and
compressing it should make them easier. That is a reading of the name plus the
shape, not something measured.

**Whether the game will read more than 39 rows is unknown.** Vanilla ships 39
and nothing says the reader is bounded, but nothing proves it is not either.
The `.vanilla` copy is kept before the first write and `--restore` puts it
back, so the test is cheap: extend, launch, look at the info screen. If the
game will not start, restore.
"""

import argparse
import os
import sys

import bini

from ..game import flvisits as fl
from .persist import WriteFailed, _backup, _save

TABLE = ("MISSIONS", "ptough.ini")
SECTION = "playertoughnessscale"
KEY = "ptough_graph_pt"

# What the vanilla ladder does at the top: 1.1395 to 1.1413 over the last ten
# rows. The first added rung continues it rather than jumping, so the ladder
# has no seam at the point where ours begins.
TAIL = 1.14
INT32 = 2 ** 31 - 1


def _path(game_dir):
    return fl.ipath(fl.ipath(game_dir, "DATA"), *TABLE)


def _rows(sections):
    """[(worth, level)] out of decoded sections, in file order."""
    out = []
    for name, entries in sections:
        if name.lower() != SECTION:
            continue
        for key, values in entries:
            if key.lower() == KEY and len(values) >= 2:
                out.append((int(values[0]), int(values[1])))
    return out


def _shipped(game_dir):
    """The file as the game shipped it, which is `.vanilla` once we have run."""
    path = _path(game_dir)
    keep = path + ".vanilla"
    return keep if os.path.exists(keep) else path


def read(game_dir=None):
    """(vanilla rows, current rows)."""
    game_dir = game_dir or fl.DEFAULT_GAME
    path = _path(game_dir)
    if not os.path.exists(path):
        raise WriteFailed(f"no level table at {path}")
    base = _rows(bini.decode(open(_shipped(game_dir), "rb").read()))
    now = _rows(bini.decode(open(path, "rb").read()))
    return base, now


def plan(to_level, to_worth, game_dir=None):
    """The full table with the ladder carried on to `to_level`.

    **Built from the vanilla rows, never from the current ones**, so running
    this twice gives the same answer as running it once and there is no way to
    end up with a ladder that was stretched twice and says nothing about it.
    Same rule as `drawdist`.

    The first added rung continues the vanilla ratio; the rest are a geometric
    run that lands on `to_worth` exactly. So the shape is "one more ordinary
    step, then a steeper climb", which is what a longer game wants: the level
    after the old cap should not cost ten times the one before it.
    """
    base, _now = read(game_dir)
    if not base:
        raise WriteFailed("the level table is empty; refusing to write one")
    top_worth, top_level = base[-1]
    if to_level <= top_level:
        raise WriteFailed(f"the table already reaches level {top_level}")
    to_worth = int(round(to_worth))
    first = int(round(top_worth * TAIL))
    if to_worth <= first:
        raise WriteFailed(
            f"level {to_level} at {to_worth:,} is below the first added rung "
            f"({first:,}); pick a bigger number")

    steps = to_level - top_level - 1          # rungs after the first added one
    ratio = (to_worth / first) ** (1 / steps) if steps else 1.0
    rows = list(base)
    for i in range(to_level - top_level):
        level = top_level + 1 + i
        worth = first if i == 0 else int(round(first * ratio ** i))
        rows.append((worth, level))
    rows[-1] = (to_worth, to_level)           # land exactly where asked

    # Two refusals, because both failures are silent in the game rather than
    # loud: a value past int32 wraps negative, and a rung that does not rise
    # makes a level you can never leave.
    for worth, level in rows:
        if worth > INT32:
            raise WriteFailed(
                f"level {level} would need {worth:,}, past the {INT32:,} an "
                f"int32 holds. Lower the top.")
    for (w1, l1), (w2, l2) in zip(rows, rows[1:]):
        if w2 <= w1 or l2 != l1 + 1:
            raise WriteFailed(
                f"the ladder is not strictly rising at level {l2} "
                f"({w1:,} then {w2:,}); refusing to write it")
    return rows, ratio


def write(to_level, to_worth, game_dir=None):
    """Put the extended ladder in the file, keeping a vanilla copy first."""
    game_dir = game_dir or fl.DEFAULT_GAME
    rows, ratio = plan(to_level, to_worth, game_dir)
    path = _path(game_dir)
    sections = bini.decode(open(_shipped(game_dir), "rb").read())
    fresh = []
    for name, entries in sections:
        if name.lower() != SECTION:
            fresh.append((name, entries))
            continue
        keep = [(k, v) for k, v in entries if k.lower() != KEY]
        fresh.append((name, keep + [(KEY, [w, l]) for w, l in rows]))
    kept = _backup(path)
    _save(path, fresh)
    return rows, ratio, kept


def restore(game_dir=None):
    """Put the table back to its `.vanilla` copy."""
    game_dir = game_dir or fl.DEFAULT_GAME
    path = _path(game_dir)
    keep = path + ".vanilla"
    if not os.path.exists(keep):
        raise WriteFailed("there is no .vanilla copy; nothing to restore")
    _save(path, bini.decode(open(keep, "rb").read()))
    return _rows(bini.decode(open(path, "rb").read()))


def _show(rows, base):
    known = dict((l, w) for w, l in base)
    prev = None
    for worth, level in rows:
        step = f"x{worth / prev:.3f}" if prev else ""
        mark = "" if level in known and known[level] == worth else "  <-- ours"
        print(f"   level {level:<3} {worth:>16,} {step:>8}{mark}")
        prev = worth


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--to", type=int, help="carry the ladder up to this level")
    ap.add_argument("--worth", type=float, help="what that level should cost")
    ap.add_argument("--restore", action="store_true", help="undo, from .vanilla")
    ap.add_argument("--full", action="store_true", help="print every row")
    args = ap.parse_args()

    try:
        if args.restore:
            rows = restore(args.game)
            print(f"restored: {len(rows)} rows, top level {rows[-1][1]} "
                  f"at {rows[-1][0]:,}")
        elif args.to:
            if not args.worth:
                sys.exit("--to needs --worth: what should the top level cost?")
            rows, ratio, kept = write(args.to, args.worth, args.game)
            if kept:
                print(f"kept {os.path.basename(kept)}")
            print(f"written: {len(rows)} rows, top level {rows[-1][1]} "
                  f"at {rows[-1][0]:,}, step x{ratio:.3f}")
        base, now = read(args.game)
        print(f"\n{len(now)} rows, levels {now[0][1]} to {now[-1][1]}, "
              f"top worth {now[-1][0]:,}")
        _show(now if args.full else now[-14:], base)
        if not args.full and len(now) > 14:
            print(f"   ({len(now) - 14} earlier rows not shown; --full for all)")
    except (WriteFailed, OSError, ValueError) as exc:
        sys.exit(str(exc))
