"""Trade → Market: one question, asked from whichever end you know.

The page half is in `frontend/trade.py`.

**This is one pipeline, not two pages behind a switch.** It was two, `Data` and
`Deltas`, and merging them by putting a mode button over two separate renderers
was the wrong merge: same two screens, one more click. What actually unifies
them is in the data.

    by commodity   which commodity  ->  every base that trades it
    by base        which base -> what is on its shelf -> every base that
                   trades that, measured against what you pay here

The last step is the same list both times. `market.trades` proves it: with a
source row it gains a `delta` column and drops the source base, and the order
does not change, because `delta` is `price` minus a constant. So the axis picks
where the pipeline starts, never what it computes.

Every stage answers with the same two shapes, `goods` and `rows`, so the page
draws one picker and one table however the question was asked.
"""

import os

from .game import market as mk

# One spelling of the empty hold. `_market` seeds the payload with it and
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


def _every_good(names, rows):
    """The commodity picker when no base has been chosen: all of them."""
    counts = {}
    for row in rows:
        counts[row["good"]] = counts.get(row["good"], 0) + 1
    spoils = {r["good"]: r["perishable"] for r in rows if r["perishable"]}
    return sorted(
        ({"nickname": k, "name": names[k], "bases": counts.get(k, 0),
          "perishable": spoils.get(k, ""),
          "price": None, "best": None} for k in names),
        key=lambda g: g["name"])


def _shelf(rows, base, only):
    """The commodity picker when a base has been chosen: what it stocks.

    Deliberately the same row shape as `_every_good`, filled in rather than
    replaced. The page has one picker, so a shelf that answered in its own
    shape would need a second one, which is the split this tab just came out
    of. `price` is what this base charges and `best` is where it is worth
    most, both of which are simply unknown before a base is named.
    """
    return [{"nickname": r["good"], "name": r["good_name"],
             "perishable": r["perishable"],
             "bases": 0, "price": r["price"], "best": r["best"]}
            for r in mk.best_runs(rows, base, only)]


def _stock(rows, only):
    """Every base with something on the shelf, for the base picker."""
    seen = {}
    for row in rows:
        if not row["buy"]:
            continue
        if only is not None and row["base"]["id"] not in only:
            continue
        # The docked filter applies to where you start as well as to where you
        # go: offering a base the next step would then refuse to plan from is
        # worse than not offering it.
        entry = seen.setdefault(row["base"]["id"], dict(row["base"], goods=0))
        entry["goods"] += 1
    return sorted(seen.values(), key=lambda b: (b["name"], b["system"]))


def _market(ctx):
    """The picker, the shelf and the destinations, whichever end you start at."""
    names, rows = ctx.game.market
    body = {"by": "good", "goods": [], "bases": [], "base": None, "good": None,
            "source": None, "rows": [], "hold": dict(NO_HOLD), "error": None}
    try:
        by = "base" if ctx.one("by") == "base" else "good"
        good = (ctx.one("good") or "").lower() or None
        want_base = (ctx.one("base") or "").lower() or None
        seen_only = bool(ctx.one("visited"))
        body["by"] = by

        visited = _docked(ctx, seen_only or by == "base" or good in names)
        only = visited if seen_only else None
        # The checkbox has to be answered here, not in the page. A row the page
        # hides is still a row, but the system the hold advice names was chosen
        # out of bases the page never received, so only this side can choose it
        # again. `_routes` reads the flag the same way.
        body["hold"] = _hold(ctx, names, rows, only)

        source = None
        if by == "base":
            body["bases"] = _stock(rows, only)
            here = next((b for b in body["bases"] if b["id"] == want_base), None)
            if not here:
                return body  # the base picker, and nothing chosen yet
            body["base"] = here
            body["goods"] = _shelf(rows, here["id"], only)
            if good:
                # The row you would buy at. Without one there is no margin to
                # measure, so the good is treated as unchosen rather than
                # answered against a price from somewhere else.
                source = next((r for r in rows if r["base"]["id"] == here["id"]
                               and r["good"] == good and r["buy"]), None)
        else:
            body["goods"] = _every_good(names, rows)

        if good in names and (by == "good" or source):
            body["good"] = good
            body["source"] = source
            # Every row carries its own visited flag whatever the checkbox
            # says, so the table can re-filter itself without another request.
            body["rows"] = mk.trades(rows, good, source, visited=visited,
                                     only=only)
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"market": _market}
