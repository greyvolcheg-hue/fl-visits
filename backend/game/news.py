"""What is on the news wire, and at which point in the story it appeared.

    fl.py news <save.fl>          what is live at that save's story state
    fl.py news --all              every item, with the window it runs in

`DATA/MISSIONS/news.ini` files 403 `[NewsItem]` entries, of which **364 are
distinct items**: see `_collapse` for the 17 blanks and the 22 duplicates it
folds. Every one is gated on the story:

    [NewsItem]
    rank = freetime_02_03, mission_03_loaded
    icon = world
    category = 15003
    headline = 15003
    text = 15004
    base = Li01_01_Base
    base = Li01_02_Base ...

`rank` is a pair of story states, from `story.py`'s table, and the item is on
the wire while the player's state is between them. `base` says which bases
carry it, and an item is typically on 21 to 31 of the 164 dockable ones.

**This is the one thing in the game that genuinely appears as you play.** At
`mission_03_loaded` 223 of the 403 have opened; by the end of the campaign
nearly all of them have. The Neural Net tab shows them by *debut*, newest
first, which turns a gate into a timeline: an item is `live` while its window
is still open and `past` once the story has moved beyond it.

Bar rumors are the counter-example and are in `rumors.py`: all 7803 of them
carry the same wide-open gate and never move at all.
"""

import argparse

from . import bases as bs
from . import flvisits as fl
from . import story as st


def _entries(pairs):
    out = {}
    for key, values in pairs:
        out.setdefault(key.lower(), []).append(values)
    return out


def load_news(game_dir, names=None, states=None):
    """Every news item, with its window as two story indexes.

    Sorted by debut and then by file order, which is the order the game itself
    would offer them in, so two items opening at the same state keep the
    author's sequence rather than a sort's.
    """
    names = names if names is not None else fl.load_names(game_dir)
    states = states or st.STATES
    path = fl.ipath(fl.ipath(fl.ipath(game_dir, "DATA"), "MISSIONS"), "news.ini")
    out = []
    for section, pairs in bs.read_multi(path):
        if section.lower() != "newsitem":
            continue
        entry = _entries(pairs)
        rank = entry.get("rank", [[]])[0]
        lo, hi = st.window(rank, states)
        ids = lambda key: entry.get(key, [[0]])[0][0]  # noqa: E731
        head = names.get(_int(ids("headline")), "")
        out.append({
            "debut": lo,
            "debut_state": states[lo],
            "expires": hi,
            "expires_state": states[hi],
            # `critical` is the game's own word for a story headline; the rest
            # are `world`, `mission` and a handful of one-offs.
            "icon": str(entry.get("icon", [["world"]])[0][0]),
            "category": names.get(_int(ids("category")), ""),
            "headline": head,
            "text": names.get(_int(ids("text")), ""),
            "bases": sorted({str(b[0]).lower() for b in entry.get("base", [])}),
        })
    out.sort(key=lambda r: r["debut"])
    return _collapse(out)


def _collapse(rows):
    """The 403 filed items as the 364 distinct ones, blanks dropped.

    Two kinds of noise, both counted on a stock install rather than estimated:

        17  carry no headline, no text, no category and no base at all, and
            every one of them debuts at `mission_end`. They are placeholders
            and they draw as empty boxes.
        22  are exact duplicates: same headline, same text, already in the
            list. They differ only in the window they run in and in their
            icon. "Arrival of Freeport 7 Survivors" is filed once at
            `mission_01a_loaded` as `critical` and again at
            `mission_01a_accepted` as `world`.

    A duplicate is folded into the copy that broke first, taking the widest
    window of the two, the union of the bases, and `critical` if either was:
    the story ran once and the file says so twice.

    **`debuts` is not a detail.** A mark's key on the page is the debut plus
    the headline, so every copy has its own key and folding them would strip
    the mark off any copy that was not the survivor. Nine of the owner's 266
    news marks sat on one, measured before this was written. The list travels
    with the row and the page treats a row as marked if any of its keys is.
    """
    out, at = [], {}
    for row in rows:
        if not row["headline"].strip() and not row["text"].strip():
            continue
        key = (row["headline"], row["text"])
        seen = at.get(key)
        if seen is None:
            at[key] = len(out)
            out.append({**row, "debuts": [row["debut"]], "runs": 1})
            continue
        held = out[seen]
        held["debuts"].append(row["debut"])
        held["runs"] += 1
        if row["expires"] > held["expires"]:
            held["expires"] = row["expires"]
            held["expires_state"] = row["expires_state"]
        if row["icon"] == "critical":
            held["icon"] = "critical"
        held["bases"] = sorted(set(held["bases"]) | set(row["bases"]))
        held["category"] = held["category"] or row["category"]
    return out


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def since(rows, index, docked=None):
    """Everything whose window has opened by `index`, newest debut first.

    `live` is the distinction worth drawing and the reason this is not just a
    filter: an item whose window has closed behind you was on the wire once and
    is gone now, which is a different thing from one you have not reached.

    `docked` narrows to items carried by a base the player has actually docked
    at, which is the honest reading of "news you could have read". Passing None
    keeps the lot.
    """
    out = []
    for row in rows:
        if row["debut"] > index:
            continue
        if docked is not None and not (set(row["bases"]) & docked):
            continue
        out.append({**row, "live": row["expires"] >= index})
    out.reverse()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save", nargs="?")
    ap.add_argument("--all", action="store_true", help="every item, oldest first")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    args = ap.parse_args()

    rows = load_news(args.game)
    if args.all or not args.save:
        print(f"{len(rows)} news items")
        for row in rows:
            print(f"  [{row['debut_state']} .. {row['expires_state']}] "
                  f"{row['headline'][:70]}")
        return

    here = st.where(fl.decode_save(args.save))
    live = since(rows, here["index"])
    on = sum(1 for r in live if r["live"])
    print(f"{here['state']}: {len(live)} of {len(rows)} have opened, "
          f"{on} still on the wire\n")
    for row in live[:25]:
        mark = "*" if row["live"] else " "
        print(f"{mark} [{row['debut_state']}] {row['headline'][:66]}")
