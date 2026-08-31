#!/usr/bin/env python3
"""Report which Freelancer bases a save game has visited, grouped by system.

    flvisits.py <save.fl> [--game DIR] [--all]

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

DEFAULT_GAME = os.path.expanduser(
    "~/Games/freelancer/drive_c/Program Files (x86)/Microsoft Games/Freelancer"
)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import bini  # noqa: E402


def ipath(base, *parts):
    """Join a path, matching each component case-insensitively.

    The game ships `DATA/UNIVERSE/SYSTEMS/LI01/li01.ini`: directories upper
    case, files lower. That is invisible on Windows and fatal on Linux, which
    is the same trap `SETUP.EXE` set during the install.
    """
    path = base
    for part in parts:
        candidate = os.path.join(path, part)
        if os.path.exists(candidate):
            path = candidate
            continue
        try:
            match = next(e for e in os.listdir(path) if e.lower() == part.lower())
        except (StopIteration, OSError):
            return candidate  # let the caller fail with a real path in the error
        path = os.path.join(path, match)
    return path


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
    """Join case-insensitively. The game ships DATA/UNIVERSE but its own ini
    files spell it `universe\\universe.ini`, and Linux cares."""
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
    root = ipath(data_dir, "universe", "systems")
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if not fn.lower().endswith(".ini"):
                continue
            system = os.path.basename(dirpath)
            for section, entries in read_ini(os.path.join(dirpath, fn)):
                if section.lower() != "object":
                    continue
                nick, base = entries.get("nickname"), entries.get("base")
                if nick and base:
                    objects[str(nick[0])] = (
                        system.lower(),
                        str(base[0]),
                        entries.get("ids_name", [0])[0],
                    )
    return objects


# --- display names from the resource DLLs ---------------------------------

def _rva_to_offset(sections, rva):
    for va, vsize, raw_ptr, raw_size in sections:
        if va <= rva < va + max(vsize, raw_size):
            return raw_ptr + (rva - va)
    return None


def read_string_table(path):
    """Pull RT_STRING (type 6) out of a PE and return {string id: text}."""
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
        if name != 6:  # RT_STRING
            continue
        for block_id, block_child in entries(base + (child & 0x7FFFFFFF)):
            for _, leaf in entries(base + (block_child & 0x7FFFFFFF)):
                data_rva, size = struct.unpack_from("<II", blob, base + leaf)
                pos = _rva_to_offset(sections, data_rva)
                if pos is None:
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


def load_names(game_dir):
    """ids_name -> text, across every resource DLL, indexed the way FL does it."""
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
    names = {}
    for index, dll in enumerate(dlls):
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


if __name__ == "__main__":
    main()
