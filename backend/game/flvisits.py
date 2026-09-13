"""Report which Freelancer bases a save game has visited, grouped by system.

    fl.py visits <save.fl> [--game DIR] [--all]

`--game` points at the Freelancer install directory (the one holding EXE/ and
DATA/); it defaults to the win32 prefix on this machine. `--all` also lists the
systems where nothing has been visited yet.

Three formats have to be unpicked to get an answer:

  Save*.fl   FLS1, a symmetric XOR whose key is derived from the bytes "Gene".
             Decoded, it is plain INI with `visit = <hash>, <flag>` lines.
  DATA/*.ini BINI, Freelancer's binary INI. Decoded by scripts/bini.py.
  EXE/*.dll  display names live in PE string tables, addressed by the `ids_name`
             number: DLL index is ids // 65536, string id is ids % 65536.

The `visit` hash is one-way, so the mapping is built the other way round: every
nickname in the game data is hashed and the result looked up. That covered all
301 hashes of the first save this was tested against.
"""

import argparse
import os
import re
import struct
import sys
from collections import defaultdict

M32 = 0xFFFFFFFF

# `visit` flag values seen on dockable objects. 30 and 31 mean the player has
# actually docked; 1 means the object is merely revealed on the nav map, which
# is what the story hands you for bases you have never been to.
DOCKED = {30, 31}

# Where the install is when nobody says. Two spellings because there are two
# ways to be running this, and neither is a guess the other would survive.
WINE_GAME = os.path.expanduser(
    "~/Games/freelancer/drive_c/Program Files (x86)/Microsoft Games/Freelancer"
)
WINDOWS_GAME = r"C:\Program Files (x86)\Microsoft Games\Freelancer"


def _installed():
    r"""The game directory, asked of the registry on Windows.

    **The installer records where it put the game**, under
    `HKLM\SOFTWARE\Microsoft\Microsoft Games\Freelancer\1.0`, value
    `AppPath`, and on a 64-bit Windows that key is mirrored under
    `WOW6432Node` because the game is a 32-bit program. Both are tried, in that
    order, and the hardcoded Program Files path is the fallback for an install
    that was moved or copied rather than installed.

    Not tested on Windows. If it returns the wrong place the symptom is a clean
    "no such file" rather than a wrong answer, and `--game DIR` is the way past
    it in the meantime.
    """
    if sys.platform != "win32":
        return WINE_GAME
    import winreg  # noqa: PLC0415 - Windows only, and imported only there
    for hive in (r"SOFTWARE\Microsoft\Microsoft Games\Freelancer\1.0",
                 r"SOFTWARE\WOW6432Node\Microsoft\Microsoft Games\Freelancer\1.0"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, hive) as key:
                path = winreg.QueryValueEx(key, "AppPath")[0]
        except OSError:
            continue
        if path and os.path.isdir(path):
            return path.rstrip("\\")
    return WINDOWS_GAME


DEFAULT_GAME = _installed()

import bini

from . import bases as bs


# --- save file ------------------------------------------------------------

def decode_save(path):
    """FLS1 is XOR with a key cycling over 'Gene', offset by the byte index."""
    blob = open(path, "rb").read()
    if blob[:4] != b"FLS1":
        return blob.decode("latin-1")
    key = b"Gene"
    body = blob[4:]
    return bytes(
        c ^ (((key[i % 4] + i) % 256) | 0x80) for i, c in enumerate(body)
    ).decode("latin-1")


def parse_visits(text):
    visits = {}
    for line in text.splitlines():
        m = re.match(r"visit\s*=\s*(\d+)\s*,\s*(\d+)", line.strip())
        if m:
            visits[int(m.group(1))] = int(m.group(2))
    return visits


# --- the nickname hash ----------------------------------------------------

def _make_table():
    poly = (0xA001 << 14) & M32
    table = []
    for i in range(256):
        v = i
        for _ in range(8):
            v = ((v >> 1) ^ poly) & M32 if v & 1 else v >> 1
        table.append(v)
    return table


_TABLE = _make_table()


def fl_hash(nickname):
    """Freelancer's CreateID: a CRC-16-IBM table widened to 32 bits, byte
    swapped, shifted right two and flagged with the top bit."""
    h = 0
    for b in nickname.lower().encode("utf-8"):
        h = ((h >> 8) ^ _TABLE[(h & 0xFF) ^ b]) & M32
    h = (
        (h >> 24) | ((h >> 8) & 0xFF00) | ((h << 8) & 0xFF0000) | ((h << 24) & 0xFF000000)
    ) & M32
    return ((h >> 2) | 0x80000000) & M32


# --- game data ------------------------------------------------------------

def ipath(base, *parts):
    """Join case-insensitively.

    The game ships `DATA/UNIVERSE/SYSTEMS/LI01/li01.ini` with directories upper
    case and files lower, while its own ini files spell the same path
    `universe\\universe.ini`. Invisible on Windows, fatal on Linux.
    """
    cur = base
    for part in parts:
        if os.path.exists(os.path.join(cur, part)):
            cur = os.path.join(cur, part)
            continue
        try:
            listing = os.listdir(cur)
        except OSError:
            return os.path.join(cur, part)
        match = next((e for e in listing if e.lower() == part.lower()), part)
        cur = os.path.join(cur, match)
    return cur


def read_ini(path):
    """Return [(section, {key: [values]})]. Handles both BINI and plain text."""
    blob = open(path, "rb").read()
    if blob[:4] == b"BINI":
        return [
            (name, {k: v for k, v in entries})
            for name, entries in bini.decode(blob)
        ]
    out, section, entries = [], None, {}
    for raw in blob.decode("latin-1").splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if section is not None:
                out.append((section, entries))
            section, entries = line[1:-1], {}
        elif "=" in line and section is not None:
            k, v = line.split("=", 1)
            entries[k.strip()] = [p.strip() for p in v.split(",")]
    if section is not None:
        out.append((section, entries))
    return out


def load_universe(data_dir):
    """bases: nickname -> (system, ids_name). systems: nickname -> ids_name."""
    bases, systems = {}, {}
    for section, entries in read_ini(ipath(data_dir, "universe", "universe.ini")):
        nick = entries.get("nickname")
        if not nick:
            continue
        nick = str(nick[0])
        if section.lower() == "base":
            # keyed lower: universe.ini mixes `Li01_11_Base` and `Li01_13_base`
            bases[nick.lower()] = (
                str(entries.get("system", ["?"])[0]).lower(),
                entries.get("strid_name", [0])[0],
            )
        elif section.lower() == "system":
            systems[nick] = entries.get("strid_name", [0])[0]
    return bases, systems


def load_objects(data_dir, systems):
    """Dockable space objects: object nickname -> (system, base nickname, ids_name).

    Only objects carrying a `base =` key are kept; those are the ones a player
    can actually dock with, which is what "visited a station" means.
    """
    objects = {}
    for path, system in system_files(data_dir):
        for section, entries in read_ini(path):
            if section.lower() != "object":
                continue
            nick, base = entries.get("nickname"), entries.get("base")
            if nick and base:
                objects[str(nick[0])] = (
                    system,
                    str(base[0]),
                    entries.get("ids_name", [0])[0],
                )
    return objects


def system_files(data_dir):
    """Yield (path, system nickname) for each system universe.ini declares.

    Not a walk of SYSTEMS/. That directory also holds INTRO/intro.ini, a
    cutscene which universe.ini does not list as a system, and taking the
    folder name as the system attributed its objects to real ones: Ithaca
    Research Station showed up as an unvisited base in New York, where it does
    not exist. Following the `file` each system names excludes strays by
    construction rather than by a list of exceptions.
    """
    # A [system]'s `file` is relative to DATA/UNIVERSE, while a [Base]'s is
    # relative to DATA and spells the "Universe\" prefix out. Same key name,
    # two different roots.
    universe = ipath(data_dir, "universe")
    for section, entries in read_ini(ipath(universe, "universe.ini")):
        if section.lower() != "system":
            continue
        nick, rel = entries.get("nickname"), entries.get("file")
        if not nick or not rel:
            continue
        path = universe
        for part in str(rel[0]).replace("\\", "/").split("/"):
            path = ipath(path, part)
        if os.path.exists(path):
            yield path, str(nick[0]).lower()


# --- display names from the resource DLLs ---------------------------------

RT_STRING = 6   # names: 16 to a resource id
RT_HTML = 23    # infocards: one UTF-16 RDL document per resource id


def _rva_to_offset(sections, rva):
    for va, vsize, raw_ptr, raw_size in sections:
        if va <= rva < va + max(vsize, raw_size):
            return raw_ptr + (rva - va)
    return None


def read_string_table(path, rtype=RT_STRING):
    """Pull one resource type out of a PE and return {id: text}.

    Two types are in use and they are indexed differently, which is the whole
    reason this takes a parameter rather than being copied:

      RT_STRING (6)  names, and 16 strings share one resource id, so the id is
                     `(block - 1) * 16 + slot`.
      RT_HTML   (23) infocards, one per resource id, and the payload is UTF-16
                     RDL markup rather than a bare string. `infocards.py`
                     unwraps it.

    Bar rumors are RT_HTML and nothing else in this project reads them, so the
    alternative was a second copy of the PE resource walk below. One walk, one
    constant told apart.
    """
    blob = open(path, "rb").read()
    pe = struct.unpack_from("<I", blob, 0x3C)[0]
    if blob[pe:pe + 4] != b"PE\0\0":
        return {}
    n_sections = struct.unpack_from("<H", blob, pe + 6)[0]
    opt_size = struct.unpack_from("<H", blob, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", blob, opt)[0]
    dir_off = opt + (112 if magic == 0x20B else 96)
    res_rva = struct.unpack_from("<I", blob, dir_off + 8 * 2)[0]
    if not res_rva:
        return {}
    sec_off = opt + opt_size
    sections = []
    for i in range(n_sections):
        s = sec_off + 40 * i
        vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", blob, s + 8)
        sections.append((va, vsize, raw_ptr, raw_size))
    base = _rva_to_offset(sections, res_rva)
    if base is None:
        return {}

    def entries(off):
        n_named, n_id = struct.unpack_from("<HH", blob, off + 12)
        for i in range(n_named + n_id):
            yield struct.unpack_from("<II", blob, off + 16 + 8 * i)

    strings = {}
    for name, child in entries(base):
        if name != rtype:
            continue
        for block_id, block_child in entries(base + (child & 0x7FFFFFFF)):
            for _, leaf in entries(base + (block_child & 0x7FFFFFFF)):
                data_rva, size = struct.unpack_from("<II", blob, base + leaf)
                pos = _rva_to_offset(sections, data_rva)
                if pos is None:
                    continue
                if rtype != RT_STRING:
                    # One resource, one id, and the bytes are the payload.
                    strings[block_id] = blob[pos:pos + size]
                    continue
                end = pos + size
                for i in range(16):
                    if pos + 2 > end:
                        break
                    length = struct.unpack_from("<H", blob, pos)[0]
                    pos += 2
                    if length:
                        text = blob[pos:pos + length * 2].decode("utf-16-le", "replace")
                        strings[(block_id - 1) * 16 + i] = text
                        pos += length * 2
    return strings


def resource_dlls(game_dir):
    """The resource DLLs, in the order that decides an ids block.

    `resources.dll` is index 0 and implicit; the rest come from `[Resources]`
    in `freelancer.ini`, and an id is `index * 65536 + local id`. Pulled out of
    `load_names` on 2026-09-07 because `infocards.py` reads the same seven
    files for a different resource type, and a second copy of this loop would
    have been a second answer to "which dll is index 2".
    """
    exe = ipath(game_dir, "EXE")
    dlls = ["resources.dll"]
    ini = ipath(exe, "freelancer.ini")
    if os.path.exists(ini):
        in_res = False
        for raw in open(ini, encoding="latin-1"):
            line = raw.split(";", 1)[0].strip()
            if line.startswith("["):
                in_res = line.lower() == "[resources]"
            elif in_res and line.lower().startswith("dll"):
                dlls.append(line.split("=", 1)[1].strip())
    return dlls


def load_names(game_dir):
    """ids_name -> text, across every resource DLL, indexed the way FL does it."""
    exe = ipath(game_dir, "EXE")
    names = {}
    for index, dll in enumerate(resource_dlls(game_dir)):
        path = ipath(exe, dll)
        if not os.path.exists(path):
            continue
        for sid, text in read_string_table(path).items():
            names[index * 65536 + sid] = text
    return names


# --- report ---------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save")
    ap.add_argument("--game", default=DEFAULT_GAME)
    ap.add_argument("--all", action="store_true", help="include unvisited systems")
    args = ap.parse_args()

    data_dir = ipath(args.game, "DATA")
    bases, systems = load_universe(data_dir)
    objects = load_objects(data_dir, systems)
    names = load_names(args.game)

    # Keep only bases a player can actually dock at: 197 in universe.ini, 181
    # that anything in space points at, 163 that can be docked. The other 34
    # would put a permanent floor under every percentage. Which 34 and why is
    # in bases.py, deliberately not restated here.
    dockable = bs.dockable_bases(args.game, data_dir, system_files, ipath)
    bases = {k: v for k, v in bases.items() if k in dockable}

    def label(ids, fallback):
        try:
            return names.get(int(ids), fallback)
        except (TypeError, ValueError):
            return fallback

    systems_ci = {nick.lower(): ids for nick, ids in systems.items()}
    visits = parse_visits(decode_save(args.save))
    by_hash = {fl_hash(nick): nick for nick in objects}

    # The denominator is universe.ini's [Base] list, not the space objects:
    # a planet's mooring fixture is a second object pointing at the same base,
    # so counting objects would inflate every system with a planet in it.
    total = defaultdict(int)
    for system, _ in bases.values():
        total[system] += 1

    # base nickname -> strongest flag seen for any object pointing at it
    state = {}
    for hid, flag in visits.items():
        nick = by_hash.get(hid)
        if not nick:
            continue
        key = objects[nick][1].lower()
        if flag in DOCKED or key not in state:
            state[key] = flag

    docked, known = defaultdict(list), defaultdict(list)
    for key, flag in state.items():
        if key not in bases:
            continue
        system, ids = bases[key]
        bucket = docked if flag in DOCKED else known
        bucket[system].append(label(ids, key))

    order = sorted(total, key=lambda s: (-len(docked[s]), -len(known[s]), s))
    n_docked = sum(len(v) for v in docked.values())
    print(f"Docked at {n_docked} of {len(bases)} bases "
          f"across {len([s for s in docked if docked[s]])} of {len(total)} systems\n")
    for system in order:
        if not docked[system] and not known[system] and not args.all:
            continue
        sysname = label(systems_ci.get(system, 0), system)
        print(f"{sysname:<22} {len(docked[system])}/{total[system]:<4}  "
              + ", ".join(sorted(docked[system])))
        if known[system]:
            print(f"{'':22} {'seen':>5}   " + ", ".join(sorted(known[system])))

