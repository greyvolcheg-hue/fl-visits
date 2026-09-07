"""Equipment → Search: guns and shields by parameter.

The page half is in `frontend/search.py`.
"""

from .game import equipment as eqp


def _equipment(ctx):
    """One kind of gear, narrowed by whatever thresholds were asked for."""
    body = {"kinds": [], "kind": None, "parameters": [], "choices": {},
            "order": None, "default": None, "dir": "down",
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
        body["order"], body["default"] = order, eqp.ORDER[kind]
        body["dir"] = "down" if down else "up"
        body["parameters"] = [
            {"key": k, "label": lab, "kind": knd, "unit": unit}
            for k, lab, knd, unit in eqp.PARAMETERS[kind]]
        body["choices"] = {
            k: eqp.choices(rows, k)
            for k, _lab, knd, _u in eqp.PARAMETERS[kind] if knd == "pick"}

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
        found = eqp.search(rows, filters, order, down)

        # The docked filter narrows where you can buy, never what
        # exists: a gun is still a gun if you have not been to its
        # dealer. So it rewrites `bases` and leaves the row in place,
        # and the page says "nowhere you have docked" rather than
        # quietly dropping it.
        if (ctx.query.get("visited") or [""])[0]:
            state = ctx.state()
            seen = set(state["docked_bases"])
            found = [dict(r, bases=[b for b in r["bases"] if b["id"] in seen])
                     for r in found]
        body["rows"] = found
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"equipment": _equipment}
