"""How far through the campaign a save is, and what that is called.

    fl.py story <save.fl>

A Freelancer save carries two story fields:

    [StoryInfo]
    Mission = Mission_03
    MissionNum = 9

**`MissionNum` is an index into a table of 42 state names**, and the names are
what the rest of the game gates content on. `news.ini` gates all 403 of its
items on a pair of them, `mbases.ini` gates its rumors the same way, and
neither is readable without this table.

The table is not in any INI. It sits as a contiguous block of strings in
`DLLS/BIN/content.dll`, written in reverse, and is kept here as
`data/story-states.txt` rather than read out of a binary at run time.

Checked on every save on this disk, 18 of them, and every one agreed:

    Restart.fl   Mission_01a  MissionNum 1   -> mission_01a_loaded
    Save116a.fl  Mission_02   MissionNum 7   -> mission_02_accepted
    Save707c.fl  No_Mission   MissionNum 5   -> freetime_01_02
    Save144d.fl  Mission_13   MissionNum 40  -> mission_13_accepted

The `No_Mission` row is the one worth keeping: the states between two missions
are real states with their own name, and a reading that only understood
`Mission_NN` would have called that save "nowhere".
"""

import argparse
import os
import re

from . import flvisits as fl

TABLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "story-states.txt")

NUM = re.compile(r"^\s*MissionNum\s*=\s*(\d+)\s*$", re.M | re.I)
NAME = re.compile(r"^\s*Mission\s*=\s*(\S+)\s*$", re.M | re.I)


def load_states(path=TABLE):
    """The 42 state names, lowest first. Index is the state."""
    return [line.strip() for line in open(path, encoding="utf-8")
            if line.strip() and not line.startswith("#")]


STATES = load_states()
INDEX = {name: i for i, name in enumerate(STATES)}


def where(save_text, states=None):
    """{index, state, mission, label} for a save, or index 0 if it says nothing.

    Index 0 is `base_0_rank`, the state a brand new pilot is in, so a save that
    carries no `[StoryInfo]` at all reads as "the very beginning" rather than
    as an error. Nothing downstream has to special-case it: gating on
    `0 <= index` is what every caller wants anyway.
    """
    states = states or STATES
    found = NUM.search(save_text)
    index = int(found.group(1)) if found else 0
    index = min(max(index, 0), len(states) - 1)
    named = NAME.search(save_text)
    state = states[index]
    return {
        "index": index,
        "state": state,
        "mission": named.group(1) if named else None,
        # What to print. `mission_03_loaded` is the truth and unreadable;
        # "Mission 3, briefed" is the truth said out loud.
        "label": label(state),
        "total": len(states) - 1,
    }


def label(state):
    """`mission_03_loaded` -> `Mission 3 · briefed`, for a human."""
    if state == "base_0_rank":
        return "Before the first mission"
    if state == "mission_end":
        return "Campaign finished"
    parts = state.split("_")
    if parts[0] == "freetime":
        return f"Between missions {parts[1].lstrip('0')} and {parts[2].lstrip('0')}"
    number = parts[1].lstrip("0")
    # `loaded` is the game's word for "offered and read"; `accepted` is taken.
    stage = "briefed" if parts[2] == "loaded" else "flying it"
    return f"Mission {number} · {stage}"


def window(rank, states=None):
    """A `rank = <from>, <to>` pair from the game data, as two indexes.

    Missing or unknown ends read as wide open, because that is what the game
    does with them and a news item silently dropped is worse than one shown a
    state early.
    """
    states = states or STATES
    lo = INDEX.get(str(rank[0]).lower(), 0) if len(rank) > 0 else 0
    hi = INDEX.get(str(rank[1]).lower(), len(states) - 1) if len(rank) > 1 \
        else len(states) - 1
    return lo, hi


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save")
    args = ap.parse_args()

    here = where(fl.decode_save(args.save))
    print(f"{here['mission'] or '(no Mission key)'}  "
          f"MissionNum {here['index']}  ->  {here['state']}")
    print(f"  {here['label']}, {here['index']} of {here['total']} states")
