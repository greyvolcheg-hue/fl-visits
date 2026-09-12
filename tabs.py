"""The site map: which tabs exist, and which pair of files each one is.

Every tab is two modules with the same name, one on each side:

    backend/<name>.py   API   {endpoint: fn(ctx)}          for GET  /api/<endpoint>
                        POST  {endpoint: fn(ctx, sent)}    for POST
                        FILES {url: (type, path, cache)}   for anything not JSON
    frontend/<name>.py  ID, LABEL, CSS, JS, and one `VIEW.<id> = {...}`

Neither half is required to exist: a tab that only draws what the shared
`/api/state` already carries has no endpoints of its own, and a tab that serves
a file has no page beyond the one that shows it.

This file is neither backend nor frontend, because the shape of the page is
neither. It is the only place the whole shape can be read at once, and adding a
tab is a row here plus the file or two it names.
"""

import importlib

# (parent id, parent label, [leaf names]). A parent with one leaf is that leaf:
# the strip shows no second row for it.
LAYOUT = [
    ("overview", "Overview", ["overview"]),
    ("engine", "Engine", ["engine"]),
    ("map", "Map", ["systems", "chart", "jobs", "bestpath"]),
    ("gear", "Equipment", ["search"]),
    ("trade", "Trade", ["trade", "routes"]),
    ("rep", "Reputation", ["rep"]),
    ("log", "Neural Net", ["log"]),
]

LEAVES = [name for _id, _label, kids in LAYOUT for name in kids]


def _half(side, name):
    """One side of a tab, or None where that side does not exist."""
    try:
        return importlib.import_module(f"{side}.{name}")
    except ModuleNotFoundError:
        return None


PAGES = {name: _half("frontend", name) for name in LEAVES}
ENDS = {name: _half("backend", name) for name in LEAVES}


def tabs():
    """The tab strip, as the JS wants it.

    `leaf` is the view a parent opens on, and **every parent has one**, whether
    or not it shows a second row. Without it the shell had to assume that a
    single-leaf parent's id doubled as its view id, which held only by
    coincidence: `overview`, `engine`, `rep` and `log` happen to be spelled the
    same on both sides and `gear`/`search` never was. Dropping the DPS sub-tab
    turned that coincidence into a tab that opened the previous panel.
    """
    out = []
    for tid, label, kids in LAYOUT:
        entry = {"id": tid, "label": label, "leaf": PAGES[kids[0]].ID}
        if len(kids) > 1:
            entry["kids"] = [[PAGES[k].ID, PAGES[k].LABEL] for k in kids]
        out.append(entry)
    return out


def _table(modules, attr):
    out = {}
    for m in modules:
        out.update(getattr(m, attr, {}) or {})
    return out


_ends = [m for m in ENDS.values() if m]
_pages = [m for m in PAGES.values() if m]

GET = _table(_ends, "API")
SET = _table(_ends, "POST")
FILES = _table(_ends, "FILES")
