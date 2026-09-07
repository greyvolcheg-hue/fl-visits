"""Reputation: what it takes to change how a faction feels.

The page half is in `frontend/rep.py`.
"""

from .game import flvisits as fl
from .game import reputation as rep


def _reputation(ctx):
    """The faction list, or a worked plan when one is asked for."""
    body = {"goals": sorted(rep.GOALS), "factions": [],
            "target": None, "goal": None, "current": None,
            "needed": None, "rows": [], "error": None}
    try:
        reps = rep.player_reps(fl.decode_save(ctx.save))
        model = ctx.game.repmodel
        events, names, legality = model.events, model.names, model.legality
        # Ordered by standing rather than by name: the faction you
        # want to do something about is the one at the bottom of the
        # list of how everyone feels, so it should be the first thing
        # in the dropdown, not filed under its initial letter.
        body["factions"] = sorted(
            ({"nickname": k, "name": names.get(k, k),
              "legality": legality.get(k, ""),
              "current": round(reps.get(k, 0.0), 4)}
             for k in events),
            key=lambda f: (f["current"], f["name"]))
        want = (ctx.query.get("to") or [None])[0]
        goal = (ctx.query.get("goal") or ["neutral"])[0]
        if want and want.lower() in events and goal in rep.GOALS:
            # Named, never `*model`. Splatting the model tuple here is
            # what broke this tab when a sixth field was added: `plan`
            # got nine arguments and every faction click 500'd.
            current, needed, rows = rep.plan(
                want.lower(), rep.GOALS[goal], reps,
                model.events, model.empathy, model.names,
                model.legality, model.bribes)
            body.update(target=want.lower(), goal=goal,
                        current=round(current, 4),
                        needed=round(needed, 4), rows=rows)
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"reputation": _reputation}
