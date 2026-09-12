"""Put the shortest routes into the game's own route tables.

    fl.py routetable            # what would change, change nothing
    fl.py routetable --write
    fl.py routetable --revert   # back to the shipped tables

Freelancer answers Set Best Path out of precomputed tables in `UNIVERSE/`, and
they are not shortest paths. `game/jumps.py` builds the real graph out of the
system files and `fl.py jumps --check` does the comparison: against the shipped
`systems_shortest_path.ini` it is equal on 1502 of the 2079 pairs, shorter on
577 and longer on none.

## Why this replaces the byte patch rather than helping it

`live/bestpath.py` swaps which of these files the game reads. **It cannot
work, and that is settled by observation.** On 2026-09-12 the patch read ON,
all five bytes verified against the shipped files, and the game still routed
Hokkaido to Tau-23 as `Hokkaido > New Tokyo > Kyushu > Tau-29 > Tau-31`, which
is the gates-only table's row, where the holes table says `Hokkaido > Kyushu`
in two jumps.

The reason is the order of events. **The game reads the table once, when the
world loads, and `content.dll` and `server.dll` are reloaded by that same
load**, which wipes the patch. So the only moment the patch can be applied is
after the read has already happened, and swapping a filename pointer does
nothing to a table that is already in memory. flhack hooks the load itself to
get in first; a button pressed afterwards is too late by construction.

A file, on the other hand, is read every time a world loads. That is the whole
argument for doing it this way.

## One content, written to both files

The game ships three tables, strictly nested, and the split is jump holes:

    shortest_legal_path.ini      35 systems, 1225 pairs    0.0% hole-only hops
    shortest_illegal_path.ini    46 systems, 2071 pairs   58.4%
    systems_shortest_path.ini    50 systems, 2079 pairs   38.5%

`shortest_legal_path.ini` is the one Set Best Path reads by default, and it is
gates-only by construction, so the 15 systems that cannot be reached without a
hole are simply absent from it: **Chugoku answers "no best path" in a stock
game and is right to.**

So both targets are written with the same content, shaped from the widest table
the game ships: **its 50 systems and its 2079 pairs, section for section**. The
engine then reads a file of a shape it already reads, under either name, and
which table it picks stops mattering. The two files come out byte-identical,
which is checked.

Alaska and Omicron Minor stay out, because they are out of all three shipped
tables: Alaska is story-locked and that exclusion is the designers' own.

**The cost, stated because it is real.** The lawful table stops being lawful:
its routes now run through jump holes. Whether anything else in the game reads
that distinction is not known. `--revert` puts both files back.

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

# The table whose sections, pairs and system set the written files copy. The
# widest one the game ships, so nothing written is a shape the engine has not
# already parsed.
SHAPE = "systems_shortest_path.ini"
TARGETS = ("shortest_legal_path.ini", "systems_shortest_path.ini")
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


def content(game_dir=None, by="jumps"):
    """(sections, outside) : the table both files get, ready for `_save`.

    `outside` counts routes naming a system the shape does not list, which must
    be zero. It is the check that the shape is wide enough for the rule, and it
    is why the gates-only file cannot simply be filled with hole routes at its
    own width: 234 of its 1225 rows would name a system it has never heard of.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    jumps = jm.load_jumps(game_dir)
    sections = bini.decode(open(_shipped(game_dir, SHAPE), "rb").read())
    known = {str(values[0]).lower()
             for _s, pairs in sections for key, values in pairs
             if key.lower() == PATH_KEY and values}

    outside = 0
    fresh = []
    for section, pairs in sections:
        rows = []
        for key, values in pairs:
            if key.lower() != PATH_KEY or len(values) < 2:
                rows.append((key, values))
                continue
            src, dst = str(values[0]), str(values[1])
            steps = jm.route(jumps, src.lower(), dst.lower(), by=by)
            if steps is None:
                # The shipped table knows a pair the graph cannot join. Keep
                # the game's own answer rather than emptying the row.
                rows.append((key, values))
                continue
            chain = [src] + [jumps[s["jump"]["id"]]["to_sys"] for s in steps]
            if any(x.lower() not in known for x in chain):
                outside += 1
            rows.append((key, [src, dst] + chain))
        fresh.append((section, rows))
    return fresh, outside


def _rows(sections):
    return [(str(v[0]).lower(), str(v[1]).lower(), tuple(str(x).lower() for x in v[2:]))
            for _s, pairs in sections for k, v in pairs if k.lower() == PATH_KEY]


def plan(game_dir=None, by="jumps"):
    """[(name, changed, saved, pairs)] against what is on disk now."""
    game_dir = game_dir or fl.DEFAULT_GAME
    fresh, outside = content(game_dir, by)
    want = {(a, b): hops for a, b, hops in _rows(fresh)}
    out = []
    for name in TARGETS:
        live = bini.decode(open(_path(game_dir, name), "rb").read())
        have = {(a, b): hops for a, b, hops in _rows(live)}
        changed = saved = 0
        for pair, hops in want.items():
            was = have.get(pair)
            if was is None:
                changed += 1
                continue
            if was != hops:
                changed += 1
                saved += max(len(was) - len(hops), 0)
        out.append((name, changed, saved, len(want) - len(have)))
    return out, outside


def write(game_dir=None, by="jumps"):
    """Back up once, then write the same table into both files."""
    game_dir = game_dir or fl.DEFAULT_GAME
    fresh, outside = content(game_dir, by)
    if outside:
        raise WriteFailed(
            f"{outside} routes name a system the shape does not list; that is "
            f"the case this module exists to avoid, nothing was written")
    steps, _outside = plan(game_dir, by)
    for name in TARGETS:
        path = _path(game_dir, name)
        _backup(path)
        _save(path, fresh)
    same = len({open(_path(game_dir, n), "rb").read() for n in TARGETS}) == 1
    if not same:
        raise WriteFailed("the two files came out different, which they cannot "
                          "be from one content; look before trusting them")
    return steps


def revert(game_dir=None):
    """Put the shipped tables back, from the `.vanilla` beside each."""
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
    return done


def state(game_dir=None):
    """[(name, systems it lists, is there a .vanilla)] for each target."""
    game_dir = game_dir or fl.DEFAULT_GAME
    out = []
    for name in TARGETS:
        path = _path(game_dir, name)
        rows = _rows(bini.decode(open(path, "rb").read()))
        out.append((name, len({a for a, _b, _h in rows}),
                    os.path.exists(path + ".vanilla")))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--write", action="store_true", help="replace both tables")
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
            for name, changed, saved, added in write(args.game, by):
                print(f"{name}: {changed} routes written, {saved} jumps saved, "
                      f"{added} pairs the file did not have")
            print("\nboth files now hold the same table, and the game reads it "
                  "when a world loads, so restart it")
        else:
            steps, outside = plan(args.game, by)
            for name, changed, saved, added in steps:
                print(f"{name}")
                print(f"   {changed} routes would change, {saved} jumps saved")
                print(f"   {added} pairs the file does not have yet")
            print(f"   routes naming a system the shape does not list: {outside}")
            print("\nnothing written. --write does it, --revert undoes it")
        for name, systems, backed in state(args.game):
            print(f"   {name}: {systems} systems, "
                  f"{'.vanilla kept' if backed else 'NO BACKUP'}")
    except (WriteFailed, OSError) as exc:
        raise SystemExit(str(exc))
