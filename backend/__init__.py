"""Everything that is not the page: game data, live patching, tab endpoints.

Three tiers, and the tier a file sits in says what it may do:

    backend/<tab>.py   one per tab, the endpoint layer. Reads, never writes.
    backend/common.py  what more than one tab needs: the loaded game, the
                       per-request save, base lookup, the house grouping.
    backend/game/      readers of the game's own formats. No HTTP, no state.
    backend/live/      the only code that writes: process memory and, where a
                       setting exists in a file at all, the file beside it.

`backend/tabs.py` is the site map and the only place the whole shape of the
page can be read at once.

This file stays small on purpose. `python3 fl.py netlog save.fl` imports one
module out of `game/`, and it should not drag eleven tab modules and the whole
game load in behind it, which is what putting the site map here would do.
"""

import os
import sys

# `bini.py` is shared with the rest of 40-computer-geek and lives outside this
# repo, so the path is derived from this file rather than written down: two
# machines, two absolute paths, and a hardcoded one fails silently on the other.
_SCRIPTS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
