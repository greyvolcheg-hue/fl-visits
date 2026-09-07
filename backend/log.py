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
    """What is said at every base you have docked at, grouped by where."""
    game = ctx.game
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
        })
    out.sort(key=lambda r: (r["system"], r["base"], r["faction"], r["ids"]))
    return out


def _log(ctx):
    """The three sources, and the story state the news was filtered at."""
    body = {"state": None, "save": [], "news": [], "rumors": [],
            "bases": 0, "error": None}
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


API = {"log": _log}
