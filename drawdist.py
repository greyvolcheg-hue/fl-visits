#!/usr/bin/env python3
"""How far away asteroid fields are drawn as real rocks.

    drawdist.py              # what the files say now
    drawdist.py 1.5          # multiply every fill_dist by 1.5
    drawdist.py --restore    # back to the .vanilla copies

`[Field] fill_dist` in `DATA/SOLAR/ASTEROIDS/*.ini` is the radius inside which
the game fills space with actual asteroid geometry. Vanilla runs 1000 to 2500,
most fields sitting at 1300 to 1600, which is why a field reads as empty until
you are almost in it.

**The billboards are not the answer, tempting as they look.** Each field also
carries `[AsteroidBillboards]`, several hundred sprites, and raising `count`
looks like a cheap way to see a field from further out. It is not: the sprites
have no relationship to the rocks. `[Cube]` is a fixed pattern of five
asteroids at fractional offsets, tiled on a `cube_size` grid with
`empty_cube_frequency` thinning it, and the billboards are scattered
independently of that grid. So a sprite winks out at close range and a real
rock appears somewhere else, which is exactly what the owner reported. More
sprites means more of that, not less.

**Cost, because it is not small.** Fields fill cubes of `cube_size`, 400 in 135
of the 158 files, throughout a sphere of `fill_dist`. Geometry grows with the
cube of the radius, so 2x the distance is about 8x the rocks: the median field
goes from roughly 385 filled cubes to 3077. This is a single-threaded 2003
renderer. Start at 1.5 and look at the frame rate before going further.

**The multiplier always applies to the vanilla value, never to the current
one.** Otherwise running 1.5 twice would silently give 2.25 and there would be
no way to tell from the file which had happened. The `.vanilla` backup is the
reference, so the setting is absolute rather than cumulative and `--restore`
always has somewhere to go back to.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import bini  # noqa: E402
import flvisits as fl  # noqa: E402
from persist import WriteFailed, _backup, _save  # noqa: E402

FIELD = "field"
KEY = "fill_dist"
SANE = (0.5, 4.0)  # below 0.5 fields vanish; above 4 the cube count is absurd


def field_files(game_dir):
    """Every asteroid definition the game ships, in a stable order."""
    folder = fl.ipath(fl.ipath(fl.ipath(game_dir, "DATA"), "SOLAR"), "ASTEROIDS")
    if not os.path.isdir(folder):
        raise WriteFailed(f"no asteroid folder at {folder}")
    return [os.path.join(folder, name)
            for name in sorted(os.listdir(folder))
            if name.lower().endswith(".ini")]


def _source(path):
    """The pristine file if one was kept, else the file itself."""
    keep = path + ".vanilla"
    return keep if os.path.exists(keep) else path


def survey(game_dir=None):
    """[(name, vanilla fill_dist, current fill_dist)] for every field."""
    game_dir = game_dir or fl.DEFAULT_GAME
    out = []
    for path in field_files(game_dir):
        base = _read_fill(_source(path))
        now = _read_fill(path)
        if base is None or now is None:
            continue
        out.append((os.path.basename(path), base, now))
    return out


def _read_fill(path):
    try:
        sections = bini.decode(open(path, "rb").read())
    except Exception:
        return None
    for name, entries in sections:
        if name.lower() != FIELD:
            continue
        for key, values in entries:
            if key.lower() == KEY and values:
                return float(values[0])
    return None


def apply(factor, game_dir=None):
    """Scale every fill_dist from its vanilla value. Returns what changed."""
    low, high = SANE
    if not low <= factor <= high:
        raise WriteFailed(f"{factor:g} is outside {low:g} to {high:g}")
    game_dir = game_dir or fl.DEFAULT_GAME

    touched = 0
    for path in field_files(game_dir):
        source = _source(path)
        try:
            sections = bini.decode(open(source, "rb").read())
        except Exception:
            continue  # not every file in there is a field definition

        changed = False
        for name, entries in sections:
            if name.lower() != FIELD:
                continue
            for i, (key, values) in enumerate(entries):
                if key.lower() == KEY and values:
                    entries[i] = (key, [float(values[0]) * factor])
                    changed = True
        if not changed:
            continue

        _backup(path)
        _save(path, sections)
        touched += 1
    return touched


def restore(game_dir=None):
    """Put every field back to its `.vanilla` copy."""
    game_dir = game_dir or fl.DEFAULT_GAME
    back = 0
    for path in field_files(game_dir):
        keep = path + ".vanilla"
        if not os.path.exists(keep):
            continue
        sections = bini.decode(open(keep, "rb").read())
        _save(path, sections)
        back += 1
    return back


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("factor", nargs="?", type=float, help="multiply fill_dist")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--restore", action="store_true", help="undo, from .vanilla")
    args = ap.parse_args()

    try:
        if args.restore:
            print(f"{restore(args.game)} fields restored")
        elif args.factor:
            print(f"{apply(args.factor, args.game)} fields scaled by {args.factor:g}")
        rows = survey(args.game)
        if not rows:
            print("no asteroid fields found")
            return
        base = sorted(r[1] for r in rows)
        now = sorted(r[2] for r in rows)
        mid = len(rows) // 2
        print(f"{len(rows)} fields")
        print(f"  vanilla fill_dist  {base[0]:.0f} to {base[-1]:.0f}, "
              f"median {base[mid]:.0f}")
        print(f"  current fill_dist  {now[0]:.0f} to {now[-1]:.0f}, "
              f"median {now[mid]:.0f}")
        scaled = sum(1 for _n, b, c in rows if abs(b - c) > 0.5)
        print(f"  {scaled} of {len(rows)} differ from vanilla")
    except (WriteFailed, OSError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
