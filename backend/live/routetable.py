"""Put the shortest routes into the game's own route tables.

    fl.py routetable            # what would change, change nothing
    fl.py routetable --write
    fl.py routetable --revert   # back to the shipped tables

Freelancer answers Set Best Path out of precomputed tables in `UNIVERSE/`, and
**they are not shortest paths**. `game/jumps.py` builds the real graph out of
the system files and `fl.py jumps --check` does the comparison: against
`systems_shortest_path.ini` it is equal on 1502 of the 2079 pairs, shorter on
577 and longer on none.

`live/bestpath.py` switches the game between two of these tables. This rewrites
them, which is a different and better thing:

  * it survives loading a save. The byte patch does not, because `content.dll`
    and `server.dll` are loaded with the save.
  * it needs no running game, no `/proc/<pid>/mem` and no injected code.

## Which rule goes in which file, and why it is not one rule

    shortest_legal_path.ini      35 systems, 1225 pairs   gates only
    systems_shortest_path.ini    50 systems, 2079 pairs   holes too

**Each file is rewritten under its own rule**, and that is the whole safety
argument. A route through a jump hole passes through systems the gates-only
table has never heard of: 234 of the 1225 pairs would name one, and whether the
game validates a path against its own table is not known. Routing the legal
table on gates alone keeps every hop inside the 35 systems it already lists,
measured, and the holes table likewise stays inside its 50.

So the shape of each file never changes. Same sections, same pairs, same
vocabulary of system names; only the hops between the two ends are replaced.

What it is worth, counted on a stock install:

    shortest_legal_path.ini      136 pairs shorter,   136 jumps saved
    systems_shortest_path.ini    577 pairs shorter,   648 jumps saved

So it pays with the patch off and pays four times more with it on.

**Fewest jumps, not least flying.** That is what the game's own feature means
and what the table it replaces was trying to be; the distance tie-break comes
free and is the only sense in which this is opinionated. `--flying` asks for
the other one, which is a different feature wearing the same button.

The three rules from `persist.py` are not restated here because this file uses
that module's own `_backup` and `_save`: round trip before replacing, swap
atomically, and never overwrite an existing `.vanilla`.
"""

import argparse
import os

import bini

from .persist import WriteFailed, _backup, _save
from ..game import flvisits as fl
from ..game import jumps as jm

# file -> may a route in it go through a jump hole
TABLES = {
    "shortest_legal_path.ini": False,
    "systems_shortest_path.ini": True,
}
PATH_KEY = "path"


def _path(game_dir, name):
    return fl.ipath(fl.ipath(fl.ipath(game_dir, "DATA"), "UNIVERSE"), name)


def plan(game_dir=None, by="jumps"):
    """[(name, sections, changed, saved, outside)] without writing anything.

    `sections` is the whole file ready for `_save`, with every `Path` rewritten.
    `outside` counts any rewritten route naming a system the file does not
    already list, which must be zero: see the module docstring for what it
    would risk.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    jumps = jm.load_jumps(game_dir)
    out = []
    for name, holes in TABLES.items():
        path = _path(game_dir, name)
        sections = bini.decode(open(path, "rb").read())
        known = {str(values[0]).lower()
                 for _s, pairs in sections for key, values in pairs
                 if key.lower() == PATH_KEY and values}
        changed = saved = outside = 0
        fresh = []
        for section, pairs in sections:
            rows = []
            for key, values in pairs:
                if key.lower() != PATH_KEY or len(values) < 2:
                    rows.append((key, values))
                    continue
                src, dst = str(values[0]), str(values[1])
                steps = jm.route(jumps, src.lower(), dst.lower(),
                                 by=by, holes=holes)
                if steps is None:
                    # The table knows a pair the graph cannot join. Leave the
                    # game's own answer alone rather than emptying the row.
                    rows.append((key, values))
                    continue
                chain = [src] + [jumps[s["jump"]["id"]]["to_sys"] for s in steps]
                if any(x.lower() not in known for x in chain):
                    outside += 1
                was = [str(v) for v in values[2:]]
                if [c.lower() for c in chain] != [w.lower() for w in was]:
                    changed += 1
                    saved += max(len(was) - len(chain), 0)
                rows.append((key, [src, dst] + chain))
            fresh.append((section, rows))
        out.append((name, fresh, changed, saved, outside))
    return out


def write(game_dir=None, by="jumps"):
    """Back up once, then replace both tables. Refuses on a route out of set."""
    game_dir = game_dir or fl.DEFAULT_GAME
    work = plan(game_dir, by)
    for name, _sections, _changed, _saved, outside in work:
        if outside:
            raise WriteFailed(
                f"{name}: {outside} routes name a system that file does not "
                f"list. That is the case this module exists to avoid; nothing "
                f"was written")
    done = []
    for name, sections, changed, saved, _outside in work:
        path = _path(game_dir, name)
        _backup(path)
        _save(path, sections)
        done.append((name, changed, saved))
    return done


def revert(game_dir=None):
    """Put the shipped tables back, from the `.vanilla` beside each."""
    game_dir = game_dir or fl.DEFAULT_GAME
    done = []
    for name in TABLES:
        path = _path(game_dir, name)
        keep = path + ".vanilla"
        if not os.path.exists(keep):
            continue
        with open(keep, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        done.append(name)
    return done


def state(game_dir=None):
    """[(name, is a `.vanilla` beside it)] , which is "has this been written"."""
    game_dir = game_dir or fl.DEFAULT_GAME
    return [(name, os.path.exists(_path(game_dir, name) + ".vanilla"))
            for name in TABLES]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--write", action="store_true", help="replace the tables")
    ap.add_argument("--revert", action="store_true",
                    help="restore the shipped tables from .vanilla")
    ap.add_argument("--flying", action="store_true",
                    help="least distance instead of fewest jumps")
    args = ap.parse_args()
    by = "flying" if args.flying else "jumps"

    try:
        if args.revert:
            done = revert(args.game)
            print("restored " + (", ".join(done) if done else "nothing: no .vanilla"))
            return
        if args.write:
            for name, changed, saved in write(args.game, by):
                print(f"{name}: {changed} routes replaced, {saved} jumps saved")
            print("\nthe game reads these when a world loads, so restart it")
            return
        for name, _sections, changed, saved, outside in plan(args.game, by):
            print(f"{name}")
            print(f"   {changed} routes would change, {saved} jumps saved")
            print(f"   routes naming a system the file does not list: {outside}")
        print("\nnothing written. --write does it, --revert undoes it")
        for name, backed in state(args.game):
            print(f"   {name}: {'written, .vanilla kept' if backed else 'untouched'}")
    except (WriteFailed, OSError) as exc:
        raise SystemExit(str(exc))
