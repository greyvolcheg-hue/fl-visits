"""Equipment → Search: guns and shields by parameter.

The page half is in `frontend/search.py`.
"""

from . import common as cm
from .game import equipment as eqp


def _equipment(ctx):
    """One kind of gear, narrowed by whatever thresholds were asked for."""
    body = {"kinds": [], "kind": None, "parameters": [], "choices": {},
            "systems": [], "order": None, "dir": "down", "favs": [],
            "rows": [], "total": 0, "error": None}
    try:
        cat = ctx.game.gear
        body["kinds"] = [
            {"key": k, "label": k.title(), "count": len(cat[k])}
            for k in sorted(cat)]
        kind = (ctx.query.get("kind") or ["guns"])[0]
        if kind not in cat:
            kind = "guns"
        rows = cat[kind]
        keys = {k for k, _l, _kd, _u in eqp.PARAMETERS[kind]}
        order = (ctx.query.get("sort") or [""])[0]
        if order not in keys:
            order = eqp.ORDER[kind]
        down = (ctx.query.get("dir") or ["down"])[0] != "up"
        body["kind"], body["total"] = kind, len(rows)
        body["order"] = order
        body["dir"] = "down" if down else "up"
        body["parameters"] = [
            {"key": k, "label": lab, "kind": knd, "unit": unit}
            for k, lab, knd, unit in eqp.PARAMETERS[kind]]
        # `class` offers the same list as `pick`; the difference is that the
        # page can also ask for below or above one of its values.
        body["choices"] = {
            k: eqp.choices(rows, k)
            for k, _lab, knd, _u in eqp.PARAMETERS[kind]
            if knd in ("pick", "class")}
        # Built from the whole catalogue for this kind, never from the rows
        # that survived the filters: a picker that shrank as you used it could
        # not be used to widen the search again.
        body["systems"] = eqp.systems(rows)

        filters = []
        for raw in ctx.query.get("f", []):
            key, _, rest = raw.partition(":")
            knd, _, value = rest.partition(":")
            if knd == "num":
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
            filters.append((key, knd, value))

        # Favourites are personal state and live where the read marks do, in
        # `data/marks.json`, so they survive a container tab and a second
        # browser. See the account in `common.py`; `localStorage` is where the
        # Neural Net's marks went missing.
        #
        # Narrowed to this kind's own nicknames: a favourited shield has no row
        # in the gun table and would only widen `keep` for nothing.
        favs = {n for n in cm.load_marks()["fav"]
                if any(r["nickname"] == n for r in rows)}
        body["favs"] = sorted(favs)

        # **Docked-only is a filter like any other and drops rows.** It used to
        # rewrite `bases` here and keep the row so the page could say "nowhere
        # you have docked sells it"; that left 187 of the 235 guns on screen
        # with nothing under them and filtered nothing, which is what the owner
        # reported on 2026-09-10. `eqp.search` carries the reversal and the
        # reasoning. A favourite still bypasses it, along with everything else.
        seen = None
        if (ctx.query.get("visited") or [""])[0]:
            seen = set(ctx.state()["docked_bases"])
            filters.append(("bases", "docked", seen))

        found = eqp.search(rows, filters, order, down, keep=favs)

        # Narrowing each surviving row to the dealers you have actually been
        # to. A different job from the filter above and it runs after it, so it
        # can no longer empty a row that was kept. It still can for a
        # favourite, which survived on its star alone: "nowhere you have
        # docked" is the honest line for that one.
        if seen is not None:
            found = [dict(r, bases=[b for b in r["bases"] if b["id"] in seen])
                     for r in found]
        body["rows"] = found
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"equipment": _equipment}
