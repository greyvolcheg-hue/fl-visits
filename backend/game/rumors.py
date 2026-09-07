"""What people in the bars say, and where each of them is standing.

    fl.py rumors <save.fl>        the bases you have docked at
    fl.py rumors --base li01_01_base

`DATA/MISSIONS/mbases.ini` puts named NPCs in each base's rooms and hangs lines
of talk on them:

    [GF_NPC]
    nickname = li0101_junkers_001_m
    individual_name = 220005
    affiliation = fc_j_grp
    room = bar
    rumor = base_0_rank, mission_end, 1, 131208
    rumorknowdb = li01_13

**The story gate on a rumor is decorative.** All 7803 `rumor` lines in the file
carry exactly one window, `base_0_rank .. mission_end`, so not one of them ever
opens or closes: every rumor in Sirius is available from the first minute of a
new game. It is read and applied anyway, so that a mod which does gate them
keeps working, but do not go looking for a rumor that "unlocks". News does that
and is in `news.py`; this does not.

What does change is where you have been. 161 bases carry rumors, a median of 16
each, and the useful question is what the people you have actually met said.

The text is an **infocard**, not a name: `MiscText.dll` holds 3101 RT_HTML
resources and no RT_STRING at all, which is why these ids look unresolvable
until the resource type is the thing that changes. All 3030 distinct rumor ids
resolve, none missing.

`rumorknowdb` is not read here. 564 lines over 112 targets name the hidden jump
hole or wreck a speaker knows about, which would tie this to the Systems tree.
Deliberately out of scope; see CLAUDE.md.
"""

import argparse

from . import bases as bs
from . import flvisits as fl
from . import infocards as ic
from . import story as st

WIDE = ("base_0_rank", "mission_end")


def _entries(pairs):
    out = {}
    for key, values in pairs:
        out.setdefault(key.lower(), []).append(values)
    return out


def load_rumors(game_dir, names=None, cards=None, states=None):
    """Every rumor line, with who says it and where they stand.

    One row per line rather than per speaker: the same line is often given to
    three NPCs of one faction on one base, and the page wants to say it once.
    """
    names = names if names is not None else fl.load_names(game_dir)
    cards = cards if cards is not None else ic.load_cards(game_dir)
    states = states or st.STATES
    path = fl.ipath(fl.ipath(fl.ipath(game_dir, "DATA"), "MISSIONS"), "mbases.ini")

    out, seen, base = [], set(), None
    for section, pairs in bs.read_multi(path):
        entry = _entries(pairs)
        name = section.lower()
        if name == "mbase":
            base = str(entry.get("nickname", [["?"]])[0][0]).lower()
            continue
        if name != "gf_npc":
            continue
        who = names.get(_int(entry.get("individual_name", [[0]])[0][0]), "")
        faction = str(entry.get("affiliation", [[""]])[0][0]).lower()
        room = str(entry.get("room", [[""]])[0][0]).lower()
        for line in entry.get("rumor", []):
            if len(line) < 4:
                continue
            ids = _int(line[3])
            # One line, one row, even where three NPCs on the base share it.
            key = (base, ids)
            if key in seen:
                continue
            seen.add(key)
            lo, hi = st.window(line[:2], states)
            out.append({
                "base": base,
                "ids": ids,
                # The speaker's name is two lines in the game data, the faction
                # and then the person. Only the person belongs on a row that
                # already carries the faction.
                "who": who.splitlines()[-1].strip() if who else "",
                "faction": faction,
                "room": room,
                "priority": _int(line[2]),
                "gated": tuple(str(x).lower() for x in line[:2]) != WIDE,
                "from": lo, "to": hi,
                "text": cards.get(ids, ""),
            })
    return out


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def for_bases(rows, wanted):
    """Rumors at the given bases, in the order the file lists them."""
    keep = {b.lower() for b in wanted}
    return [r for r in rows if r["base"] in keep]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save", nargs="?")
    ap.add_argument("--base", action="append", default=[])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    args = ap.parse_args()

    rows = load_rumors(args.game)
    gated = sum(1 for r in rows if r["gated"])
    print(f"{len(rows)} rumors across "
          f"{len({r['base'] for r in rows})} bases, {gated} story-gated")
    wanted = list(args.base)
    if args.save:
        text = fl.decode_save(args.save)
        data_dir = fl.ipath(args.game, "DATA")
        every, _systems = fl.load_universe(data_dir)
        objects = fl.load_objects(data_dir, _systems)
        by_hash = {fl.fl_hash(n): n for n in objects}
        for hid, flag in fl.parse_visits(text).items():
            nick = by_hash.get(hid)
            if nick and flag in fl.DOCKED:
                wanted.append(objects[nick][1].lower())
    if not wanted:
        return
    rows = for_bases(rows, wanted)
    print(f"{len(rows)} at {len({r['base'] for r in rows})} of them\n")
    for row in rows[:20]:
        print(f"  {row['base']}  {row['who'] or '(unnamed)'}")
        print(f"      {row['text'].splitlines()[0][:88] if row['text'] else '(no text)'}")
