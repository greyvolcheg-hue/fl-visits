"""The page: one module per tab, plus the shell they all sit in.

A module here is style and behaviour and nothing else. It declares `ID`,
`LABEL`, an optional `CSS` block of its own selectors, and a `JS` block ending
in one `VIEW.<id> = {...}` registration. `tabs.py` says which ones exist and in
what order; `shell.py` holds what every tab shares.

**The whole page is one inline script.** A syntax error anywhere in it, a
duplicate top-level `let` for instance, is not a broken tab: it is a page with
no behaviour at all, served happily with a 200. `check_views.py` is the only
thing that catches that, so run it after touching anything here.
"""

import os

from . import shell  # noqa: F401  (the frame; every tab sits in it)

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    return open(os.path.join(HERE, name)).read()


def css(modules):
    return "\n".join(m.CSS for m in modules if getattr(m, "CSS", ""))


def js(modules):
    return "\n".join(m.JS for m in modules if getattr(m, "JS", ""))
