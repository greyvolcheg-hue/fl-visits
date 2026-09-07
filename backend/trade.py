"""Trade → Data: who buys and sells what.

The page half is in `frontend/trade.py`.
"""

import os

from .game import market as mk


# One spelling of the empty hold. `_trade` seeds the payload with it and
# `_hold` returns it, so writing it out twice makes the payload's shape depend
# on which of the two ran.
NO_HOLD = {"items": [], "systems": [], "whole": 0, "saved": None}


def _docked(ctx, want):
    """Bases the player has docked at, or None if the save will not open.

    None rather than an empty set: an empty set is the claim "docked nowhere",
    which greys out every row on the page, and a save the game has not written
    yet makes no claim at all.

    Read only when something needs it. `read_state` walks every base in the
    game and the Neural Net log on top of the decode, and the first load of
    this tab wants neither the checkbox nor a row list.
    """
    if not want:
        return None
    try:
        return ctx.docked()
    except (OSError, ValueError):
        return None


def _hold(ctx, names, rows, only):
    """The hold and where to unload it, or an empty hold and no advice.

    A save that will not open costs the hold section and nothing else. The
    commodity picker and all 1786 market rows below it are static game data
    that never needed the save, and taking the whole tab down for a file the
    game has not written yet throws away the part that still works.
    `ships.player_ship` returns None on the same grounds.
    """
    out = dict(NO_HOLD)
    try:
        held = mk.hold(ctx.saved(), names)
        saved_at = os.path.getmtime(ctx.save)
    except (OSError, ValueError):
        return out
    if not held:
        return out
    out["saved"] = saved_at
    out["items"] = sorted(
        ({"good": g, "name": names[g], "units": n} for g, n in held.items()),
        key=lambda i: -i["units"])
    runs = mk.hold_runs(rows, held, only, names)
    # Counted over every run, not over the ten kept: 43 systems take a hold of
    # water, and a count taken after the slice can only ever say ten.
    out["whole"] = sum(1 for r in runs if not r["missing"])
    # Ten is well past where this stops being a decision: the eleventh-best
    # system is not somewhere anyone flies a full hold.
    out["systems"] = runs[:10]
    return out


def _trade(ctx):
    """The commodity list, or every base trading one of them."""
    names, rows = ctx.game.market
    body = {"goods": [], "good": None, "rows": [],
            "hold": dict(NO_HOLD), "error": None}
    try:
        want = (ctx.query.get("good") or [None])[0]
        want = want.lower() if want else None
        seen_only = bool((ctx.query.get("visited") or [""])[0])
        visited = _docked(ctx, seen_only or want in names)
        # The checkbox has to be answered here, not in the page. A row the
        # page hides is still a row, but the system the hold advice names was
        # chosen out of bases the page never received, so only this side can
        # choose it again. `_deltas` and `_routes` read the flag the same way.
        body["hold"] = _hold(ctx, names, rows, visited if seen_only else None)
        counts = {}
        for row in rows:
            counts[row["good"]] = counts.get(row["good"], 0) + 1
        body["goods"] = sorted(
            ({"nickname": k, "name": names[k], "bases": counts.get(k, 0)}
             for k in names),
            key=lambda g: g["name"])
        if want in names:
            body["good"] = want
            # Every row carries its own visited flag whatever the checkbox
            # says, so the table can re-filter itself without another request.
            body["rows"] = mk.find(rows, want, visited)
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"trade": _trade}
