"""Trade → Routes: what to carry between two systems.

The page half is in `frontend/routes.py`.
"""

from .game import market as mk
from .game import ships as sh


def _routes(ctx):
    """What is worth carrying from one system to another."""
    _names, rows = ctx.game.market
    body = {"systems": [], "from": None, "to": None, "rows": [],
            "traded": 0, "ship": None, "hold": None, "error": None}
    try:
        # Per-unit margin is only half the answer: what a run is worth
        # is that times what the ship can carry. Read from the save, so
        # it follows the player into a new hull.
        ship = sh.player_ship(ctx.game.dir, ctx.save)
        if ship and ship.get("hold"):
            body["ship"] = ship["name"]
            body["hold"] = ship["hold"]
        only = None
        if (ctx.query.get("visited") or [""])[0]:
            state = ctx.state()
            only = set(state["docked_bases"])

        systems = {}
        for row in rows:
            if only is not None and row["base"]["id"] not in only:
                continue
            seen = systems.setdefault(
                row["base"]["sys"],
                {"nickname": row["base"]["sys"], "name": row["base"]["system"],
                 "bases": set()})
            seen["bases"].add(row["base"]["id"])
        body["systems"] = sorted(
            ({"nickname": s["nickname"], "name": s["name"],
              "bases": len(s["bases"])} for s in systems.values()),
            key=lambda s: s["name"])

        src = (ctx.query.get("from") or [None])[0]
        dst = (ctx.query.get("to") or [None])[0]
        # src == dst is allowed. `routes` already skips any row whose
        # buy and sell land on the same base, so one system on both
        # ends yields exactly its internal runs and nothing degenerate.
        if src in systems and dst in systems:
            found = mk.routes(rows, src, dst, only)
            body["from"] = src
            body["to"] = dst
            # `traded` counts everything both systems deal in, so the
            # page can tell "nothing is traded in both" apart from
            # "several are, and every one of them is a loss". A trader
            # acts on those two differently.
            body["traded"] = len(found)
            rows = [r for r in found if r["gain"] > 0]
            # Every commodity has volume 1.0, checked, so a hold of 70
            # carries 70 units of anything and the run is a plain
            # multiplication. `ships.py` carries the note.
            for row in rows:
                row["run"] = row["gain"] * body["hold"] if body["hold"] else None
            body["rows"] = rows
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"routes": _routes}
