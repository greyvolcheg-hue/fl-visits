"""Equipment → Search: guns and shields by parameter.

The page half is in `frontend/search.py`.
"""

from .game import equipment as eqp


def _equipment(ctx):
    """One kind of gear, narrowed by whatever thresholds were asked for."""
    body = {"kinds": [], "kind": None, "parameters": [], "choices": {},
            "systems": [], "order": None, "default": None, "dir": "down",
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
        found = eqp.search(rows, filters, order, down)

        # The docked filter narrows where you can buy, never what
        # exists: a gun is still a gun if you have not been to its
        # dealer. So it rewrites `bases` and leaves the row in place,
        # and the page says "nowhere you have docked" rather than
        # quietly dropping it.
        #
        # **The system filter is the opposite and runs earlier**, inside
        # `eqp.search`: "what does Colorado sell" has no answer for a gun
        # Colorado does not sell, so that one drops the row. The two read
        # alike and are not the same question. Applied in this order a row
        # can survive the system and then show no dealer, which is exactly
        # right: sold there, and you have not been.
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
