"""What the bots call you, and every word they are able to say.

    fl.py callsign                      what it says now, and every choice
    fl.py callsign --faction fc_bd --desig 29 --wing 6 --slot 6
    fl.py callsign --restore

**A bot can only say what somebody recorded in 2003.** Searched across all 1852
distinct message ids in every voice file: there is no recording of a personal
name. `faction_prop.ini` does carry name pools per culture, 100 Kusari first
names and 300 surnames with Suzuki among them, but they are text for the
contact list and nothing ever speaks one. Three vocabularies are recorded, and
a callsign is those three in a row:

    <faction word>    <formation designator>    <number> - <number>
    48 recordings          29 recordings          0 to 20, both halves
    "Freelancer"             "Alpha"                "1"      "1"

"Yanagi" and "Susuki" are in the second column, not the first. They are
formation designators like Alpha and Beta, which is why they get heard and
mistaken for names.

**The shape cannot be changed, only the words.** `<word> <desig> <n>-<n>` is
assembled by the caller, one token per call, so there is no way to drop the
second number and be "Yanagi 6". Every word in it can be chosen.

## Where each one is decided

All four are in `DLLS/BIN/content.dll`, in the one function that builds a
callsign. Two are strings and two are code:

    faction       the string "gcs_refer_faction_player", swapped whole
    designator    the string "gcs_refer_formationdesig_01", last two digits
    first number  a literal `push 1` feeding "gcs_misc_number_%d-"
    second number `(id - 1) % 20 + 1`, eleven bytes, replaced by a constant

The designator arithmetic is what proves the reading rather than suggesting it.
The other arm of the same branch does

    add $0xfffcfb51,%edx          ; -197807
    push $0x70a6540               ; "gcs_refer_formationdesig_%02d"

so designator number is `ids - 197807`: 197808 is Alpha and 197836 is Yanagi.
That is exactly the 29 recordings `_01` to `_29`, and exactly the 29 strings in
the union of every faction's `formation_desig` range. Three counts agreeing.

**The branch is "has a formation", not "is the player".** The literal
designator and the literal 1 are the arms taken by a ship that has neither, and
in single player that is you. It is also any NPC flying alone, so **these words
will occasionally turn up on somebody else's radio.** That is the cost and
there is no version of this without it.

**`content.dll` is reloaded whenever a save loads**, which is recorded in
`CLAUDE.md` under the best-path work, so a write here lands on the next load
and not even a relaunch is needed. `os.replace` over a file Wine has mapped is
safe: the running process keeps the old inode.
"""

import argparse
import os
import struct
import sys
import tempfile

from ..game import flvisits as fl
from ..game import wrecks as wr
from .inject import _headers
from .persist import WriteFailed, _backup

TARGET = ("DLLS", "BIN", "content.dll")
VOICES = ("voices_space_male.ini", "voices_space_female.ini")

FACTION_PREFIX = "gcs_refer_faction_"
FACTION_SUFFIX = "_short"
DESIG_PREFIX = "gcs_refer_formationdesig_"
# What `ids - <this>` gives, taken from the instruction that does it rather
# than counted off the string table.
DESIG_BASE = 197807
NUMBER_FMT = "gcs_misc_number_%d"


def _path(game_dir):
    return fl.ipath(game_dir, *TARGET)


def _shipped(game_dir):
    """The file as the game shipped it, which is `.vanilla` once we have run.

    **Every offset is found in this, never in the live file.** A patched file no
    longer contains the strings the anchors search for, so reading the current
    setting would stop working the moment it was set once.
    """
    path = _path(game_dir)
    keep = path + ".vanilla"
    return keep if os.path.exists(keep) else path


# --- what the game can say ------------------------------------------------

def _spoken(game_dir):
    """Every message id that has a recording, as a set."""
    data = fl.ipath(game_dir, "DATA")
    out = set()
    for name in VOICES:
        path = fl.ipath(fl.ipath(data, "AUDIO"), name)
        if not os.path.exists(path):
            continue
        for section, pairs in wr.read_multi(path):
            if section.lower() != "sound":
                continue
            for key, values in pairs:
                if key.lower() == "msg" and values:
                    out.add(str(values[0]).lower())
    return out


def factions(game_dir):
    """[(nickname, label)] for every faction word a bot can pronounce.

    Derived, never typed: the ids present in the voice files, named from
    `InitialWorld.ini`, which spells them with a `_grp` suffix the audio drops.
    The player's own word belongs to no group, so it is named here, from what
    the owner reports hearing: "Freelancer".
    """
    data = fl.ipath(game_dir, "DATA")
    names = fl.load_names(game_dir)
    label = {}
    for section, pairs in wr.read_multi(fl.ipath(data, "InitialWorld.ini")):
        if section.lower() != "group":
            continue
        entry = {}
        for key, values in pairs:
            entry.setdefault(key.lower(), values)
        nick = str((entry.get("nickname") or [""])[0]).lower()
        short = nick[:-4] if nick.endswith("_grp") else nick
        try:
            label[short] = names.get(int((entry.get("ids_name") or [0])[0]), short)
        except (TypeError, ValueError):
            label[short] = short

    out = []
    for msg in _spoken(game_dir):
        if msg.startswith(FACTION_PREFIX) and msg.endswith(FACTION_SUFFIX):
            nick = msg[len(FACTION_PREFIX):-len(FACTION_SUFFIX)]
            out.append((nick, label.get(nick, "Freelancer")))
    return sorted(out, key=lambda row: (row[0] != "player", row[1].lower()))


def designators(game_dir):
    """[(number, name)] for the 29 formation words, in the game's own order.

    The range is the union of every faction's `formation_desig`, so a mod that
    adds one is picked up rather than being missing from a list typed in here.
    """
    data = fl.ipath(game_dir, "DATA")
    names = fl.load_names(game_dir)
    lo = hi = None
    for section, pairs in wr.read_multi(fl.ipath(data, "MISSIONS",
                                                 "faction_prop.ini")):
        for key, values in pairs:
            if key.lower() != "formation_desig" or len(values) < 2:
                continue
            try:
                a, b = int(values[0]), int(values[1])
            except (TypeError, ValueError):
                continue
            lo = a if lo is None else min(lo, a)
            hi = b if hi is None else max(hi, b)
    if lo is None:
        raise WriteFailed("no formation_desig ranges in faction_prop.ini")
    spoken = _spoken(game_dir)
    out = []
    for ids in range(lo, hi + 1):
        number = ids - DESIG_BASE
        if ids in names and f"{DESIG_PREFIX}{number:02d}" in spoken:
            out.append((number, names[ids]))
    return out


def numbers(game_dir):
    """Which numbers have a recording, as a sorted list.

    Both halves are checked: the first is spoken with a trailing dash and the
    second without, and a number is only offered when the game can say it both
    ways, because either half may be set to it.
    """
    spoken = _spoken(game_dir)
    return sorted(n for n in range(0, 100)
                  if f"gcs_misc_number_{n}" in spoken
                  and f"gcs_misc_number_{n}-" in spoken)


# --- where the four sites are ---------------------------------------------

def _once(blob, needle, what):
    """The one offset of `needle`, refusing anything but exactly one.

    **Never a hardcoded offset.** That rule is already in `speed.py` and the
    reason is the same: an address written down is an address that goes wrong
    quietly on somebody else's install, where a wrong write is a crash rather
    than a message.
    """
    hits, i = [], blob.find(needle)
    while i != -1:
        hits.append(i)
        i = blob.find(needle, i + 1)
    if len(hits) != 1:
        raise WriteFailed(
            f"{what} matches {len(hits)} places in content.dll, not one; "
            "this is not the build these patches were read from")
    return hits[0]


def _va(sections, image_base, off):
    """A file offset as the address the code will push."""
    for rva, _vsize, raw_ptr, raw_size in sections:
        if raw_ptr <= off < raw_ptr + raw_size:
            return image_base + rva + (off - raw_ptr)
    raise WriteFailed(f"file offset {off:#x} is in no section of content.dll")


def sites(game_dir=None):
    """{name: (offset, length)} for the four places, found in the shipped file.

    The two code sites anchor on the address of a string that was itself found
    by search, so nothing here is a constant except the instructions being
    replaced.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    blob = open(_shipped(game_dir), "rb").read()
    image_base, sections = _headers(_shipped(game_dir))

    faction = _once(blob, b"gcs_refer_faction_player\0", "the faction word")
    desig = _once(blob, (DESIG_PREFIX + "01\0").encode(), "the designator")

    dash = _va(sections, image_base,
               _once(blob, (NUMBER_FMT + "-\0").encode(), "the dashed number"))
    plain = _va(sections, image_base,
                _once(blob, (NUMBER_FMT + "\0").encode(), "the plain number"))

    # push 1 / lea 0x14(%esp),%eax / push <"gcs_misc_number_%d-">
    wing = _once(blob, bytes.fromhex("6a018d442414") + b"\x68"
                 + struct.pack("<I", dash), "the first number")
    # xor edx / dec eax / mov ecx,20 / div / inc edx / push edx / push <fmt>
    slot = _once(blob, bytes.fromhex("33d248b914000000f7f142") + b"\x52\x68"
                 + struct.pack("<I", plain), "the second number")
    return {"faction": (faction, 24), "desig": (desig, 27),
            "wing": (wing, 2), "slot": (slot, 11)}


# The eleven bytes the second number computes itself with, and what replaces
# them: `mov $N,%edx` is five bytes, so six nops make up the length exactly.
SLOT_VANILLA = bytes.fromhex("33d248b914000000f7f142")


def _slot_patch(value):
    return b"\xba" + struct.pack("<I", value) + b"\x90" * 6


# --- reading and writing --------------------------------------------------

def read(game_dir=None):
    """{faction, desig, wing, slot} as the file currently carries them.

    `slot` is None when the game is still working it out for itself, which is
    what vanilla does and which comes out as 1 for a ship with no formation.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    spots = sites(game_dir)
    blob = open(_path(game_dir), "rb").read()

    off, _n = spots["faction"]
    word = blob[off:blob.index(b"\0", off)].decode("latin-1")
    faction = word[len(FACTION_PREFIX):] if word.startswith(FACTION_PREFIX) else word

    off, _n = spots["desig"]
    desig = blob[off:blob.index(b"\0", off)].decode("latin-1")
    desig = int(desig[len(DESIG_PREFIX):]) if desig.startswith(DESIG_PREFIX) else None

    off, _n = spots["wing"]
    wing = blob[off + 1] if blob[off] == 0x6A else None

    off, _n = spots["slot"]
    chunk = blob[off:off + 11]
    if chunk == SLOT_VANILLA:
        slot = None
    elif chunk[0] == 0xBA:
        slot = struct.unpack_from("<I", chunk, 1)[0]
    else:
        raise WriteFailed(f"the second number site at {off:#x} holds bytes "
                          f"neither this tool nor the game put there: "
                          f"{chunk.hex(' ')}")
    return {"faction": faction, "desig": desig, "wing": wing, "slot": slot}


def _write_file(path, blob):
    """Replace a file atomically, keeping the mode it had."""
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
        # The temp file is created 0600; the game has to be able to read this.
        os.chmod(temp, mode)
        os.replace(temp, path)
    except Exception:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def write(faction=None, desig=None, wing=None, slot=None, game_dir=None):
    """Set any of the four. Anything left None keeps the shipped behaviour.

    **Built from the shipped bytes every time**, so running this twice is the
    same as running it once and there is no way to end up with a file that was
    patched twice and cannot say which. Same rule as `drawdist` and `levels`.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    spots = sites(game_dir)
    spoken = _spoken(game_dir)
    blob = bytearray(open(_shipped(game_dir), "rb").read())

    if faction is not None:
        msg = f"{FACTION_PREFIX}{faction}{FACTION_SUFFIX}"
        if msg.lower() not in spoken:
            raise WriteFailed(
                f"nothing in the game says {msg!r}, so the radio would go "
                f"silent instead of naming you. Run `fl.py callsign` for the "
                f"words that have a recording.")
        off, room = spots["faction"]
        text = f"{FACTION_PREFIX}{faction}".encode("latin-1")
        # The terminator has to fit too, and the slack after the string is
        # what there is: writing past it lands in the next string.
        if len(text) > room + 3:
            raise WriteFailed(f"{faction!r} needs {len(text)} bytes and there "
                              f"are {room + 3}")
        blob[off:off + len(text) + 1] = text + b"\0"

    if desig is not None:
        if f"{DESIG_PREFIX}{desig:02d}" not in spoken:
            raise WriteFailed(f"no recording of formation designator {desig}")
        off, _room = spots["desig"]
        blob[off:off + 27] = f"{DESIG_PREFIX}{desig:02d}".encode("latin-1")

    ok = numbers(game_dir)
    for name, value in (("wing", wing), ("slot", slot)):
        if value is None:
            continue
        if value not in ok:
            raise WriteFailed(f"{value} has no recording; the game can say "
                              f"{ok[0]} to {ok[-1]}")
    if wing is not None:
        off, _room = spots["wing"]
        blob[off + 1] = wing
    if slot is not None:
        off, _room = spots["slot"]
        blob[off:off + 11] = _slot_patch(slot)

    path = _path(game_dir)
    kept = _backup(path)
    _write_file(path, bytes(blob))
    back = open(path, "rb").read()
    if back != bytes(blob):
        raise WriteFailed("content.dll read back differently from what was "
                          "written; nothing can be trusted here, restore it")
    return read(game_dir), kept


def restore(game_dir=None):
    """Put the shipped `content.dll` back."""
    game_dir = game_dir or fl.DEFAULT_GAME
    path = _path(game_dir)
    keep = path + ".vanilla"
    if not os.path.exists(keep):
        raise WriteFailed("there is no .vanilla copy; nothing to restore")
    _write_file(path, open(keep, "rb").read())
    return read(game_dir)


def sentence(game_dir=None, state=None):
    """What you will be called, as a line of English."""
    game_dir = game_dir or fl.DEFAULT_GAME
    state = state or read(game_dir)
    word = dict(factions(game_dir)).get(state["faction"], state["faction"])
    desig = dict(designators(game_dir)).get(state["desig"], state["desig"])
    slot = "?" if state["slot"] is None else state["slot"]
    return f"{word} {desig} {state['wing']}-{slot}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--faction", help="the word instead of Freelancer")
    ap.add_argument("--desig", type=int, help="formation designator, 1 to 29")
    ap.add_argument("--wing", type=int, help="the number before the dash")
    ap.add_argument("--slot", type=int, help="the number after it")
    ap.add_argument("--restore", action="store_true", help="undo, from .vanilla")
    ap.add_argument("--list", action="store_true", help="every word available")
    args = ap.parse_args()

    try:
        if args.restore:
            state = restore(args.game)
            print("restored")
        elif any(v is not None for v in
                 (args.faction, args.desig, args.wing, args.slot)):
            state, kept = write(args.faction, args.desig, args.wing, args.slot,
                                args.game)
            if kept:
                print(f"kept {os.path.basename(kept)}")
            print("written; takes effect the next time a save loads")
        else:
            state = read(args.game)

        print(f"\nthey will call you:  {sentence(args.game, state)}")
        slot = "as the game works it out" if state["slot"] is None else state["slot"]
        print(f"  faction    {state['faction']}")
        print(f"  designator {state['desig']}")
        print(f"  numbers    {state['wing']} - {slot}")

        if args.list:
            fac = factions(args.game)
            print(f"\n{len(fac)} faction words a bot can say:")
            for nick, label in fac:
                print(f"   {nick:<9} {label}")
            des = designators(args.game)
            print(f"\n{len(des)} formation designators:")
            for n, label in des:
                print(f"   {n:<3} {label}")
            print(f"\nnumbers: {', '.join(str(n) for n in numbers(args.game))}")
        else:
            print(f"\n{len(factions(args.game))} faction words, "
                  f"{len(designators(args.game))} designators, "
                  f"numbers {numbers(args.game)[0]} to {numbers(args.game)[-1]}."
                  "  --list shows them")
    except (WriteFailed, OSError, ValueError) as exc:
        sys.exit(str(exc))
