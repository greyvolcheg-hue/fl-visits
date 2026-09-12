"""Map → Best Path: the shortest way from one system to another.

The page half is in `frontend/bestpath.py`.

**Not the same thing as `backend/live/bestpath.py`**, which patches a running
game so its own Set Best Path reads the route table that knows about jump
holes. This one works the route out itself, and it has to: measured over all
2079 pairs, the game's table is longer than the real shortest path on 577 of
them. `game/jumps.py` carries that comparison and `fl.py jumps --check` runs it.
"""

from .game import jumps as jm


def _bestpath(ctx):
    """Two routes between two systems, against what this save has found."""
    body = {"systems": [], "from": None, "to": None,
            "jumps": None, "flying": None, "same": False,
            "known": 0, "total": 0, "found_only": True, "gates_only": False,
            "error": None}
    try:
        jumps = ctx.game.jumps
        body["systems"] = jm.systems(jumps)
        body["total"] = len(jumps)

        # Which jumps this save has been told about. Read even when the box is
        # off, because every step still says whether it is on your nav map.
        found = jm.seen_in(jumps, ctx.visits())
        body["known"] = len(found)

        # Default is what you have found. The box widens it to the whole game,
        # which doubles as "what would open up if I went looking".
        everything = (ctx.query.get("all") or [""])[0]
        gates = (ctx.query.get("gates") or [""])[0]
        body["found_only"] = not everything
        body["gates_only"] = bool(gates)
        allow = None if everything else jm.usable(jumps, found)

        src = (ctx.query.get("from") or [None])[0]
        dst = (ctx.query.get("to") or [None])[0]
        keys = {s["key"] for s in body["systems"]}
        if src in keys and dst in keys:
            body["from"], body["to"] = src, dst
            plan = jm.plan(jumps, src, dst, allow, holes=not gates)
            body["same"] = plan["same"]
            for by in ("jumps", "flying"):
                one = plan[by]
                if one is None:
                    continue
                body[by] = dict(one, steps=[
                    dict(step, found=step["id"] in found)
                    for step in one["steps"]])
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"bestpath": _bestpath}
