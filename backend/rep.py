"""Reputation: what it takes to change how a faction feels.

The page half is in `frontend/rep.py`.
"""

from .game import reputation as rep


def _place(game, key):
    """One bribe base, in the shape every base on this page takes.

    Built from what `GameData` already holds rather than from
    `market.base_index`: the name, the system and the nav map cell are all
    loaded at startup, and a second index would be a second answer to "where is
    this base".
    """
    system, ids = game.bases[key]
    return {"id": key, "name": game.label(ids, key),
            "system": game.system_label(system), "sys": system,
            "at": game.sectors.get(key, "")}


def _reputation(ctx):
    """The faction list, or a worked plan when one is asked for."""
    body = {"goals": sorted(rep.GOALS), "factions": [],
            "target": None, "goal": None, "current": None,
            "needed": None, "rows": [], "error": None}
    try:
        # `ctx.saved()`, not a read of our own. The docked set below comes
        # from the same decode, and `common.Ctx` exists so that one request
        # cannot read the save at two different moments.
        reps = rep.player_reps(ctx.saved())
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
            # A bribe is bought in a bar, so the row says which bars you can
            # walk into. Narrowed twice and both halves matter: to bases that
            # can be docked at at all, which is `bases_total`, then to the ones
            # this save has actually been to, which is the list. "2 of 14" then
            # reads as a journey rather than as a list that came up short, and
            # an empty list with a total behind it is a real answer.
            seen = ctx.docked()
            for row in rows:
                if row.get("event") != "bribe":
                    continue
                reach = [b for b in row["bases"] if b in ctx.game.bases]
                row["bases_total"] = len(reach)
                row["bases"] = sorted(
                    (_place(ctx.game, b) for b in reach if b in seen),
                    key=lambda b: (b["system"], b["name"]))
            body.update(target=want.lower(), goal=goal,
                        current=round(current, 4),
                        needed=round(needed, 4), rows=rows)
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"reputation": _reputation}
