#!/usr/bin/env python3
"""Which bases a player can actually dock at.

`universe.ini` lists 197 `[Base]` entries. Most can be docked at, but three
groups cannot, and counting them puts a permanent floor under every percentage:

  * 15 that no space object points at, cutscene copies of Manhattan and story
    locations like Battleship Osiris. A `visit` is recorded against an object,
    so a base without one can never be recorded at all.
  * 15 mining platforms, the Asteroid Miners and two Gas Miners. These are the
    ones this module exists for, and they are the subtle case: they look
    dockable in the data. The space object carries `dock_with`, the base has a
    room file, and that file declares `[BaseInfo] start_room = Deck`. The dock
    button is nevertheless greyed out in play, confirmed by screenshot on
    2026-09-01 at 100 m from the Asteroid Miner in Omega-7.

The rule that separates them, found by elimination:

    a base is dockable if it is a planet, or if some object pointing at it has
    a docking sphere of type `berth`

`berth` is the sphere a fighter lands through. The miners carry only
`moor_medium` and `moor_large`, which are mooring points for capital ships.
Planets are the exception because a planet is docked at through a separate
`docking_fixture` object, whose spheres are also `moor_*`, so testing the
planet itself for a berth would wrongly drop every planet in the game.

Three other candidates were tested and rejected, recorded here so nobody
spends the evening on them again:

  * the `visit` key on the object. 141 bases lack it, Planet Manhattan and
    Planet New London among them.
  * "has only moor_* spheres". True of the miners, but equally true of every
    planet, for the reason above.
  * presence in `mbases.ini`. All 182 reachable bases are in it.

The rule excludes exactly 15 bases, 13 Asteroid Miner and 2 Gas Miner, and
nothing else. The game's own naming agrees: one of the two Gas Miner
archetypes is called `gas_miner_nodock`.

This lives in its own file because `flvisits.py` and `serve.py` both need the
denominator and had drifted apart once already. One spelling, one place.
It also needs an INI reader that keeps repeated keys, which the frozen reader
in `flvisits.py` does not: `docking_sphere` is repeated per archetype.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import bini  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navmap  # noqa: E402

BERTH = "berth"


def read_multi(path):
    """[(section, [(key, values), ...])] with repeated keys preserved."""
    blob = open(path, "rb").read()
    if blob[:4] == b"BINI":
        return bini.decode(blob)
    out, section, pairs = [], None, []
    for raw in blob.decode("latin-1").splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if section is not None:
                out.append((section, pairs))
            section, pairs = line[1:-1], []
        elif "=" in line and section is not None:
            key, value = line.split("=", 1)
            pairs.append((key.strip(), [p.strip() for p in value.split(",")]))
    if section is not None:
        out.append((section, pairs))
    return out


def _entries(pairs):
    """Lower-cased key -> list of value-lists. Case varies between files."""
    out = {}
    for key, values in pairs:
        out.setdefault(key.lower(), []).append(values)
    return out


def _solar_files(game_dir, data_dir, ipath):
    """Paths freelancer.ini lists under `solar`, the same way wrecks.py does."""
    ini = ipath(ipath(game_dir, "EXE"), "freelancer.ini")
    out = []
    for raw in open(ini, encoding="latin-1"):
        line = raw.split(";", 1)[0].strip()
        if "=" not in line:
            continue
        name, value = (p.strip() for p in line.split("=", 1))
        if name.lower() != "solar":
            continue
        path = data_dir
        for part in value.replace("\\", "/").split("/"):
            path = ipath(path, part)
        if os.path.exists(path):
            out.append(path)
    return out


def load_archetypes(game_dir, data_dir, ipath):
    """archetype nickname (lower) -> set of docking sphere types (lower)."""
    out = {}
    for path in _solar_files(game_dir, data_dir, ipath):
        for section, pairs in read_multi(path):
            if section.lower() != "solar":
                continue
            entry = _entries(pairs)
            nick = entry.get("nickname")
            if not nick:
                continue
            out[str(nick[0][0]).lower()] = {
                str(v[0]).lower() for v in entry.get("docking_sphere", [])
            }
    return out


def dockable_bases(game_dir, data_dir, system_files, ipath):
    """Set of base nicknames (lower) a player can dock at.

    `system_files` is the caller's own iterator of (path, system), so this
    module does not need a second opinion about which files are systems.
    """
    spheres = load_archetypes(game_dir, data_dir, ipath)

    is_planet, has_berth = set(), set()
    for path, _system in system_files(data_dir):
        for section, pairs in read_multi(path):
            if section.lower() != "object":
                continue
            entry = _entries(pairs)
            base = entry.get("base")
            if not base:
                continue
            key = str(base[0][0]).lower()
            arch = str(entry["archetype"][0][0]).lower() if entry.get("archetype") else ""
            if arch.startswith("planet_"):
                is_planet.add(key)
            if BERTH in spheres.get(arch, ()):
                has_berth.add(key)
    return is_planet | has_berth


def base_sectors(data_dir, system_files, scales):
    """base nickname (lower) -> "E6 UR", the nav map cell and where in it.

    Lives here rather than in a file of its own because it is the same walk of
    the same `[Object]` sections `dockable_bases` already does, and a third
    copy of that walk is worse than one more function beside the second.

    23 bases are pointed at by more than one object, a planet and its mooring
    fixture, and the first in file order wins. They sit within a few hundred
    metres of each other, far inside one cell of a map eight cells across, so
    which one is picked cannot change the answer.
    """
    out = {}
    for path, system in system_files(data_dir):
        scale = scales.get(system, 1.0)
        for section, pairs in read_multi(path):
            if section.lower() != "object":
                continue
            entry = _entries(pairs)
            base, pos = entry.get("base"), entry.get("pos")
            if not base or not pos or len(pos[0]) < 3:
                continue
            key = str(base[0][0]).lower()
            if key in out:
                continue
            try:
                x, z = float(pos[0][0]), float(pos[0][2])
            except (TypeError, ValueError):
                continue
            cell = navmap.sector(x, z, scale)
            if not cell:
                continue
            spot = navmap.subcell(x, z, scale)
            out[key] = f"{cell} {spot}".strip()
    return out


def main():
    """Print the split, so the rule can be checked against the game by eye."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import flvisits as fl

    game = sys.argv[1] if len(sys.argv) > 1 else fl.DEFAULT_GAME
    data_dir = fl.ipath(game, "DATA")
    bases, systems = fl.load_universe(data_dir)
    names = fl.load_names(game)
    objects = fl.load_objects(data_dir, systems)

    reachable = {b.lower() for _, b, _ in objects.values()}
    dockable = dockable_bases(game, data_dir, fl.system_files, fl.ipath)
    label = {}
    for _system, base, ids in objects.values():
        try:
            label[base.lower()] = names.get(int(ids), base)
        except (TypeError, ValueError):
            label[base.lower()] = base

    print(f"{len(bases)} [Base] entries in universe.ini")
    print(f"{len(reachable & set(bases))} reachable in space")
    print(f"{len(dockable & set(bases))} dockable\n")
    dropped = sorted((reachable & set(bases)) - dockable)
    print(f"reachable but not dockable ({len(dropped)}):")
    for key in dropped:
        print(f"   {label.get(key, key):<22} {key}")


if __name__ == "__main__":
    main()
