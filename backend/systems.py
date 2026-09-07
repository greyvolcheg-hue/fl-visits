"""Map → Systems: every system, its bases and its wrecks, in one tree.

The page half is in `frontend/systems.py`.

This tab owns `/api/state`, and the shell polls it for every save-backed tab:
the payload is the save turned into systems, and the header's save name and
timestamp come out of the same read. Other tabs borrow it through
`ctx.state()` rather than decoding the save a second time.
"""


def _state(ctx):
    return ctx.state()


API = {"state": _state}
