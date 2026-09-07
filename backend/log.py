"""Neural Net: the story log out of the save.

The page half is in `frontend/log.py`.

**Its own endpoint, not part of `/api/state`.** Resolving 113 log entries
against the string tables was being done on every five-second poll, for every
tab, whether or not anyone was reading the log. It is now done when this tab
is open and not otherwise.
"""

from .game import netlog as nl


def _log(ctx):
    """The log, newest first, or the reason the save would not open."""
    try:
        return {"entries": nl.entries(ctx.saved(), ctx.game.names), "error": None}
    except (OSError, ValueError) as exc:
        return {"entries": [], "error": str(exc)}


API = {"log": _log}
