"""Infocards: the long text the game shows, out of the resource DLLs.

    fl.py infocards 131196

Freelancer keeps two kinds of text in its resource DLLs and they are not
interchangeable:

    RT_STRING (6)   short names. `flvisits.load_names` reads these, and every
                    `ids_name` in the game data resolves through it.
    RT_HTML   (23)  infocards. A UTF-16 XML document per id, in a markup the
                    game calls RDL, and **the only place bar rumors live**.

`MiscText.dll` carries 3101 of the second kind and not one of the first, which
is why a rumor id looked unresolvable until the type was the thing that changed
rather than the file. All 3030 distinct rumor ids resolve here, none missing.

Indexing is the same arithmetic `load_names` uses: `dll index * 65536 + id`,
with the dll order taken from `[Resources]` in `freelancer.ini` and
`resources.dll` implicitly first.
"""

import argparse
import os
import re

from . import flvisits as fl

# The RDL wrapper. `<PARA/>` is a line break and every other tag is furniture:
# `<PUSH/>` and `<POP/>` push formatting state the game's own renderer cares
# about and a reader does not.
XML_HEAD = re.compile(r"<\?xml[^>]*\?>", re.I)
PARA = re.compile(r"<PARA\s*/?>", re.I)
TAG = re.compile(r"<[^>]*>")
BLANKS = re.compile(r"\n{3,}")


def plain(raw):
    """One RT_HTML resource as readable text."""
    if isinstance(raw, bytes):
        # UTF-16 with a BOM, which decodes to a leading U+FEFF rather than
        # being consumed, so it is stripped by hand.
        raw = raw.decode("utf-16-le", "replace").lstrip("﻿")
    text = PARA.sub("\n", XML_HEAD.sub("", raw))
    return BLANKS.sub("\n\n", TAG.sub("", text)).strip()


def load_cards(game_dir):
    """ids -> plain text, across every resource DLL, indexed the way FL does.

    5307 cards on a stock install. Read once and kept, the same way the name
    table is: this is 3 MB of XML to parse and nothing in it ever changes.
    """
    out = {}
    for index, dll in enumerate(fl.resource_dlls(game_dir)):
        path = fl.ipath(fl.ipath(game_dir, "EXE"), dll)
        if not os.path.exists(path):
            continue
        for rid, raw in fl.read_string_table(path, fl.RT_HTML).items():
            out[index * 65536 + rid] = plain(raw)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ids", nargs="*", type=int, help="ids to print")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    args = ap.parse_args()

    cards = load_cards(args.game)
    if not args.ids:
        print(f"{len(cards)} infocards")
        return
    for ids in args.ids:
        text = cards.get(ids)
        print(f"--- {ids}")
        print(text if text is not None else "(no card with that id)")
