"""Trade → Deltas: what a base sells, and where it is worth more.

The page half is in `frontend/deltas.py`.
"""

from .game import market as mk


def _deltas(ctx):
    """The base list, what one of them sells, and where that is worth more."""
    _names, rows = ctx.game.market
    body = {"bases": [], "base": None,
            "goods": [], "good": None, "rows": [], "error": None}
    try:
        only = None
        if (ctx.query.get("visited") or [""])[0]:
            state = ctx.state()
            only = set(state["docked_bases"])

        # Every base that has anything on the shelf. The filter applies
        # here as well as to the destinations: offering a base the next
        # step would then refuse to plan a run from is worse than not
        # offering it.
        stock = {}
        for row in rows:
            if not row["buy"]:
                continue
            if only is not None and row["base"]["id"] not in only:
                continue
            seen = stock.setdefault(row["base"]["id"], dict(row, goods=0))
            seen["goods"] += 1
        body["bases"] = sorted(
            (dict(r["base"], goods=r["goods"]) for r in stock.values()),
            key=lambda b: (b["name"], b["system"]))

        base = (ctx.query.get("base") or [None])[0]
        if not base or base.lower() not in stock:
            return body  # just the picker; nothing chosen yet
        base = base.lower()
        body["base"] = stock[base]["base"]
        body["goods"] = [
            {"nickname": r["good"], "name": r["good_name"],
             "price": r["price"], "best": r["best"]}
            for r in mk.best_runs(rows, base, only)]

        good = (ctx.query.get("good") or [None])[0]
        if good:
            good = good.lower()
            source = next((r for r in rows if r["base"]["id"] == base
                           and r["good"] == good and r["buy"]), None)
            if source:
                body["good"] = good
                body["rows"] = mk.deltas(rows, good, source, only)
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"deltas": _deltas}
