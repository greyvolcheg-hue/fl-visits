"""One module per sub-tab. This file is the site map and the assembly.

A view module declares what it is and what it needs:

    JS    render/wire functions, plus one `VIEW.<id> = {...}` registration
    CSS   its own selectors, if any
    API   {endpoint: fn(ctx)} for GET  /api/<endpoint>
    POST  {endpoint: fn(ctx, sent)} for POST, returning a status note

`ctx` carries `game`, `save`, `query` and `lock`. Everything else is shared and
lives in `shell`.

Adding a sub-tab is a new file plus a row in LAYOUT. The row is deliberate
rather than discovered: LAYOUT is the only place the whole shape of the page
can be read at once.
"""

from . import (chart, deltas, dps, log, rep, routes, search, shell, speed,
               trade, visits, wrecks)

LAYOUT = [
    ("map", "Map", [visits, wrecks, chart]),
    ("speed", "Speed", [speed]),
    ("gear", "Equipment", [dps, search]),
    ("log", "Neural Net", [log]),
    ("rep", "Reputation", [rep]),
    ("trade", "Trade", [trade, deltas, routes]),
]

# A parent with one child is that child: the strip shows no second row for it.
MODULES = [m for _id, _label, kids in LAYOUT for m in kids]


def tabs():
    """The tab strip, as the JS wants it."""
    out = []
    for tid, label, kids in LAYOUT:
        entry = {"id": tid, "label": label}
        if len(kids) > 1:
            entry["kids"] = [[m.ID, m.LABEL] for m in kids]
        out.append(entry)
    return out


def css():
    return "\n".join(m.CSS for m in [shell] + MODULES if getattr(m, "CSS", ""))


def js():
    return "\n".join(m.JS for m in MODULES)


def _table(attr):
    out = {}
    for m in MODULES:
        out.update(getattr(m, attr, {}))
    return out


GET = _table("API")
SET = _table("POST")
