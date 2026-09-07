"""Overview: where you are, what is nearby, and the one thing worth doing next.

The page half is in `frontend/overview.py`.

**Nothing here reads the game a second time.** Every panel is a view of
something another tab already computes: the meters are the Systems totals, the
cargo panel is the Deltas calculation aimed at the base under your feet, and
the standing panel is the Reputation plan aimed at whoever likes you least.
This tab exists because those three answers are wanted together, at the moment
you undock, and not because they are three new questions.
"""

import re

from .game import market as mk
from .game import netlog as nl
from .game import reputation as rep
from .game import ships as sh
from .game import story as st

# The save's own words for where the player is. `base` is absent in flight,
# which is a state and not a failure.
FACT = {
    "system": re.compile(r"^\s*system\s*=\s*(\S+)\s*$", re.M | re.I),
    "base": re.compile(r"^\s*base\s*=\s*(\S+)\s*$", re.M | re.I),
    "money": re.compile(r"^\s*money\s*=\s*(\d+)\s*$", re.M | re.I),
    "rank": re.compile(r"^\s*rank\s*=\s*(\d+)\s*$", re.M | re.I),
}

# How many rows each panel is worth. Past these the panel stops being a glance
# and starts being the tab it borrowed from, which is one click away anyway.
NEARBY = 8
CARGO = 5
ACTIONS = 4
ENTRIES = 4


def _facts(text):
    out = {}
    for key, pattern in FACT.items():
        found = pattern.search(text)
        out[key] = found.group(1) if found else None
    return out


def _nearby(state, system):
    """What is left to find in the system you are standing in.

    Unknown bases before revealed ones before wrecks, because that is the order
    of how much they are worth knowing: a base you have never seen is a base
    the nav map will not draw for you.
    """
    row = next((r for r in state["systems"]
                if r["nickname"].lower() == (system or "").lower()), None)
    if not row:
        return {"system": None, "rows": []}
    out = []
    for base in row["bases"]["unknown"]:
        out.append({"mark": "−", "tone": "unknown", "name": base["name"],
                    "kind": base["faction_full"] or "base", "at": base["at"]})
    for base in row["bases"]["revealed"]:
        out.append({"mark": "□", "tone": "revealed", "name": base["name"],
                    "kind": base["faction_full"] or "base", "at": base["at"]})
    for hull in row["wrecks"]["found"]:
        if hull.get("emptied"):
            continue
        out.append({"mark": "*", "tone": "loaded", "name": hull["name"],
                    "kind": "wreck, cargo aboard",
                    "at": " ".join(x for x in (hull.get("sector"),
                                               hull.get("spot")) if x)})
    for hull in row["wrecks"]["missing"]:
        out.append({"mark": "−", "tone": "unknown", "name": hull["name"],
                    "kind": "wreck", "at": " ".join(
                        x for x in (hull.get("sector"), hull.get("spot")) if x)})
    return {"system": row["system"], "rows": out[:NEARBY]}


def _cargo(ctx, base, docked):
    """What the base under your feet sells, and where that is worth most.

    Sell ends are restricted to bases already docked at, never an unvisited
    one: a run you cannot fly is not advice. That is `only=` doing the work,
    the same argument the Deltas tab passes when its checkbox is ticked.
    """
    if not base:
        return {"base": None, "rows": [], "note": None}
    _names, rows = ctx.game.market
    key = base.lower()
    # A good with nowhere to take it carries `best` as None, and a good worth
    # less elsewhere is not a run. Both are dropped before the sort, so the
    # panel never leads with a line that loses money.
    runs = [r for r in mk.best_runs(rows, key, docked)
            if r["best"] and r["best"]["delta"] > 0]
    runs.sort(key=lambda r: -r["best"]["delta"])
    name = next((r["base"]["name"] for r in mk.best_runs(rows, key)), base)
    return {
        "base": name,
        "rows": [{"name": r["good_name"], "buy": r["price"],
                  "best": r["best"]["price"], "diff": r["best"]["delta"],
                  "to": r["best"]["base"]["name"],
                  "system": r["best"]["base"]["system"]}
                 for r in runs[:CARGO]],
        "note": None if runs else
                "Nothing here is worth carrying to a base you have docked at.",
    }


def _standing(ctx, text):
    """Whoever likes you least, and the cheapest ways to fix it.

    Aimed at neutral rather than friendly on purpose: -0.68 to 0.0 is the part
    that stops people shooting at you, and it is a tenth of the grind that
    getting them to like you is.
    """
    model = ctx.game.repmodel
    reps = rep.player_reps(text)
    if not reps:
        return {"faction": None, "rep": None, "rows": []}
    worst, value = min(reps.items(), key=lambda kv: kv[1])
    _current, _needed, rows = rep.plan(
        worst, rep.GOALS["neutral"], reps, model.events, model.empathy,
        model.names, model.legality, model.bribes)
    out = []
    for row in rows[:ACTIONS]:
        helps = sum(1 for c in row["collateral"] if c["change"] > 0)
        hurts = sum(1 for c in row["collateral"] if c["change"] < 0)
        out.append({
            "what": f"{row['event_label']} · {row['doer_name']}",
            "count": (f"{row['price']:,} cr." if row.get("price")
                      else f"×{row['repeats']}"),
            "side": f"+{helps} / −{hurts}",
        })
    return {"faction": model.names.get(worst, worst), "rep": round(value, 3),
            "rows": out}


def _overview(ctx):
    body = {"meters": [], "story": None, "where": [], "near": None,
            "cargo": None, "standing": None, "log": [], "error": None}
    try:
        state = ctx.state()
        text = ctx.saved()
        facts = _facts(text)
        docked = set(state["docked_bases"])

        body["meters"] = [
            {"label": "BASES / DOCKED", "have": state["docked"],
             "total": state["bases_total"],
             "percent": round(100 * state["docked"] / max(1, state["bases_total"])),
             "note": f"plus {state['revealed']} revealed by the story but "
                     f"never visited"},
            {"label": "WRECKS / STRIPPED", "have": state["stripped"],
             "total": state["wrecks_total"],
             "percent": round(100 * state["stripped"] / max(1, state["wrecks_total"])),
             "note": f"{state['systems_done']} of {state['systems_total']} "
                     f"systems closed out"},
        ]
        body["story"] = st.where(text)
        ship = sh.from_save(text, ctx.game.ships)
        body["where"] = [
            {"k": "SYSTEM", "v": ctx.game.system_label(
                (facts["system"] or "").lower()) or "—", "tone": "cyan"},
            {"k": "DOCKED AT", "v": (
                ctx.game.label(ctx.game.bases.get(
                    (facts["base"] or "").lower(), (None, 0))[1],
                    facts["base"]) if facts["base"] else "in flight")},
            {"k": "SHIP", "v": ship["name"] if ship else "—"},
            {"k": "HOLD", "v": f"{ship['hold']} units" if ship
                               and ship["hold"] else "—"},
            {"k": "BALANCE", "v": f"{int(facts['money']):,} credits"
                                  if facts["money"] else "—", "tone": "ok"},
            {"k": "RANK", "v": facts["rank"] or "—"},
        ]
        body["near"] = _nearby(state, facts["system"])
        body["cargo"] = _cargo(ctx, facts["base"], docked)
        body["standing"] = _standing(ctx, text)
        # The Neural Net tab owns the log and this is the newest corner of it.
        # Resolving all 113 entries to show four is the price of not keeping a
        # second, shorter reader that could disagree with the first.
        body["log"] = nl.entries(text, ctx.game.names)[:ENTRIES]
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"overview": _overview}
