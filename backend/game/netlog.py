"""The Neural Net log out of a Freelancer save, as readable text.

    fl.py netlog <save.fl> [--game DIR]

The save stores the log as repeated lines of the form

    log = <ids>, <count>, [<param ids>, <type>, <0>] * count

where `ids` indexes the same string tables the rest of the tool reads, so an
entry resolves to real text: 23340 is "Take the Jump Hole to the Kyushu System"
and 30730 is a `*PERSONAL ENTRY:` note.

**There is no date in an entry.** No timestamp, no seconds count, no day
number: only the string id and its substitutions. Position in the file is the
only chronology there is, and a date column would have to be invented.

**The `type` on a substitution is the ASCII code of the placeholder letter.**
Settled 2026-09-07. `22505` reads "Meet Juni on Planet Manhattan%M" and its
parameters are `(196609, 83)`, `(0, 82)` and `(1, 77)`; 77 is `M`, so the `%M`
takes the third one. Where the line's detail is real, that is the whole second
half of the entry: "Start scanning nearby ships%M" plus `(25240, 77)` is
"Start scanning nearby ships / Scan nearby ships and look for anything
suspicious".

Checked across every save on disk: 210 log texts carry a placeholder, all of
them `%M`, and 186 have a parameter of the matching type. The other 24 have
none, which is the game's way of saying the detail is empty, so the placeholder
is dropped rather than printed. Before this the page printed a bare `%M` at the
end of a sentence, which reads as corruption.

**New entries are prepended.** Established by comparing two saves, not assumed:
the 69 log lines of an older `Save52f5.fl` were an exact suffix of the 113 in
the `AutoSave.fl` written after it. So index 0 is the newest entry.

That fact decides how an entry is named. The same text repeats often, "Awaiting
Mission Objective" many times over, so a key needs the raw line plus which
occurrence of it this is. Counted from the top, every older entry is renumbered
the moment the log grows, and anything keyed to it (the read and interesting
marks the page keeps) silently slides onto the wrong line. Counted from the
bottom, existing keys never move. Hence `key_from_end`.
"""

import argparse
import os
import re
import sys
from collections import Counter

from . import flvisits as fl

LINE = re.compile(r"^\s*log\s*=\s*([^\n]+)$", re.M)
PERSONAL = "*PERSONAL ENTRY"  # the game's own heading on the pilot's diary


def raw_lines(save_text):
    """The `log =` values in save order, which is newest first."""
    return [line.strip() for line in LINE.findall(save_text)]


def _numbers(raw):
    out = []
    for part in raw.split(","):
        try:
            out.append(int(part.strip()))
        except ValueError:
            return []
    return out


PLACEHOLDER = re.compile(r"%([A-Za-z])")


def _fill(text, params):
    """Put each parameter where its letter says, and return what is left over.

    A parameter whose letter never appears in the text is not dropped: it is
    returned as a leftover and the page lists it under the entry, which is what
    the entry looked like before any of this was understood.
    """
    spare = list(params)

    def take(match):
        want = ord(match.group(1))
        for i, (kind, filled) in enumerate(spare):
            if kind == want:
                spare.pop(i)
                return filled
        return ""  # no parameter of that type: the detail is empty

    body = PLACEHOLDER.sub(take, text)
    left, seen = [], set()
    for _kind, filled in spare:
        clean = filled.strip()
        if clean and clean not in seen:
            seen.add(clean)
            left.append(clean)
    return body.strip(), left


def entries(save_text, names):
    """Readable log entries, newest first.

    Each carries a `key` that survives the log growing, so the page can hang
    per-entry marks on it. See the module docstring for why it counts up from
    the oldest end rather than down from the newest.
    """
    raws = raw_lines(save_text)

    seen = Counter()
    keys = []
    for raw in reversed(raws):
        seen[raw] += 1
        keys.append(f"{seen[raw]}:{raw}")
    keys.reverse()

    out = []
    for raw, key in zip(raws, keys):
        nums = _numbers(raw)
        if not nums:
            continue
        text = names.get(nums[0])
        params = []
        count = nums[1] if len(nums) > 1 else 0
        for i in range(count):
            at = 2 + i * 3
            if at + 1 >= len(nums):
                break
            # 0 is the game's own "nothing here" and resolves to the useless
            # string "Object Unknown", so it is dropped rather than shown.
            if not nums[at]:
                continue
            filled = names.get(nums[at]) or ""
            # Three kinds of nothing, all of which appear in real saves and
            # none of which tell a reader anything: blanks, the infocard
            # boilerplate "Body Text", and a copy of the line's own text.
            if (not filled.strip() or filled.strip() == "Body Text"
                    or filled.strip() == (text or "").strip()):
                continue
            params.append((nums[at + 1], filled))
        body, subs = _fill(text or f"(no text for id {nums[0]})", params)
        out.append({
            "key": key,
            "ids": nums[0],
            "text": body,
            "known": text is not None,
            # The pilot's own diary, 66 of the 113 entries in a mid-campaign
            # save. The game marks them itself with this heading, so this reads
            # a label rather than guessing from the prose.
            "personal": body.lstrip().upper().startswith(PERSONAL),
            "subs": subs,
        })
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--oldest", action="store_true", help="oldest first")
    args = ap.parse_args()

    names = fl.load_names(args.game)
    rows = entries(fl.decode_save(args.save), names)
    if args.oldest:
        rows = list(reversed(rows))
    print(f"{len(rows)} entries, {sum(1 for r in rows if not r['known'])} unresolved\n")
    for row in rows:
        head = row["text"].splitlines()[0]
        print(f"  {head[:96]}")
        for sub in row["subs"]:
            print(f"      + {sub.splitlines()[0][:88]}")

