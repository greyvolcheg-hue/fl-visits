"""Neural Net: the story log, the news wire, and what the bars are saying.

The page half is in `frontend/log.py`.

Three sources, and they do not behave alike, which is the whole reason they are
labelled rather than merged into one list:

    save    the pilot's own log, `log =` lines out of the save. Newest first,
            no dates, because the save holds none.
    news    `news.ini`, gated on the story state. **This is the one that grows
            as you play**: 223 of 403 items have opened at mission 3, 385 by
            mission 13, and an item whose window has closed reads differently
            from one you have not reached yet.
    rumors  `mbases.ini`. Every one of the 7803 lines carries the same wide
            open gate, so none of them ever unlocks. What changes is where you
            have docked, so that is what they are scoped to.

**Its own endpoint, not part of `/api/state`.** Resolving 113 log entries
against the string tables was being done on every five-second poll, for every
tab, whether or not anyone was reading the log.
"""

from . import common as cm
from .game import netlog as nl
from .game import news as nw
from .game import rumors as ru
from .game import story as st


def _news(ctx, index, docked):
    """Everything that has opened, newest debut first.

    Not narrowed to bases you have docked at. A news item is on 21 to 31 bases
    and the wire is the same wire; `carried` says how many of yours have it,
    which is the interesting half without hiding anything.
    """
    out = []
    for row in nw.since(ctx.game.news, index):
        out.append({
            # Every debut this item was filed under, not just the surviving
            # one. `news.py::_collapse` says why: a mark's key is built from
            # the debut, so a folded copy takes its marks with it unless the
            # page can still see the keys it used to have.
            "debuts": row["debuts"], "runs": row["runs"],
            "debut": row["debut"], "debut_state": row["debut_state"],
            "debut_label": st.label(row["debut_state"]),
            "expires_state": row["expires_state"],
            "expires_label": st.label(row["expires_state"]),
            "live": row["live"], "icon": row["icon"],
            "headline": row["headline"], "text": row["text"],
            "carried": len(set(row["bases"]) & docked),
        })
    return out


def _rumors(ctx, docked):
    """What is said at every base you have docked at, most recent stop first.

    **A rumor carries no date of its own** and never will: all 7803 lines are
    on from the first minute of a new game and none of them ever moves. What
    it has is a place, and the save records the order you first docked at
    those places, so "when you heard it" is the rank of the bar it is said in.
    See `common.dock_order` for how that order was established.

    A base the save has no rank for sorts last rather than dropping out.
    """
    game = ctx.game
    order = ctx.dock_order()
    out = []
    for row in ru.for_bases(ctx.game.rumors, docked):
        system, ids = game.bases.get(row["base"], (None, 0))
        out.append({
            "base": game.label(ids, row["base"]),
            "system": game.system_label(system) if system else "",
            "who": row["who"],
            "faction": game.faction_name.get(row["faction"], row["faction"]),
            "room": row["room"],
            "text": row["text"],
            "ids": row["ids"],
            "seen": order.get(row["base"], -1),
        })
    out.sort(key=lambda r: (-r["seen"], r["system"], r["base"],
                            r["faction"], r["ids"]))
    return out


def _log(ctx):
    """The three sources, and the story state the news was filtered at."""
    body = {"state": None, "save": [], "news": [], "rumors": [],
            "bases": 0, "marks": cm.load_marks(), "error": None}
    try:
        text = ctx.saved()
        docked = ctx.docked()
        here = st.where(text)
        body["state"] = here
        body["save"] = nl.entries(text, ctx.game.names)
        body["news"] = _news(ctx, here["index"], docked)
        body["rumors"] = _rumors(ctx, docked)
        body["bases"] = len({r["base"] for r in body["rumors"]})
    except (OSError, ValueError) as exc:
        body["error"] = str(exc)
    return body


def _marks(_ctx):
    """Every mark, for a page that has just opened."""
    return {"marks": cm.load_marks()}


def _set_marks(_ctx, sent):
    """One toggle, or a browser's whole store folded in.

    Two shapes down one endpoint because they are one question, "what is
    marked", asked with one key or with a hundred. The import is what carries a
    browser's existing marks over the first time it is seen; see the comment on
    the store in `common.py` for why there is more than one of them.
    """
    if isinstance(sent.get("import"), dict):
        marks = cm.merge_marks(sent["import"])
        counted = sum(len(marks[k]) for k in cm.KINDS)
        return f"{counted} marks now held"
    cm.set_mark(sent.get("kind"), sent.get("key"), bool(sent.get("on")))
    return None  # a toggle is its own feedback; a banner would be noise


API = {"log": _log, "marks": _marks}
POST = {"marks": _set_marks}
