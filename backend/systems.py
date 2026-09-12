"""Map → Systems: every system, its bases and its wrecks, in one tree.

The page half is in `frontend/systems.py`.

This tab owns `/api/state`, and the shell polls it for every save-backed tab:
the payload is the save turned into systems, and the header's save name and
timestamp come out of the same read. Other tabs borrow it through
`ctx.state()` rather than decoding the save a second time.
"""

import os

from . import common


def _state(ctx):
    return ctx.state()


def _reveal(ctx, _sent):
    """Open the folder the save being followed lives in.

    **It takes no argument, and that is the design.** The only folder this can
    open is the one the server already chose at startup, so there is nothing
    for a page to point it at. An endpoint that opened a path the browser sent
    would be a different and much worse thing: a local server that opens
    arbitrary folders on request.

    It belongs to this module because this is the tab that owns `/api/state`,
    and the path it opens is the one that payload carries.
    """
    where = os.path.dirname(ctx.save)
    common.open_folder(where)
    return f"opened {where}"


API = {"state": _state}
POST = {"reveal": _reveal}
