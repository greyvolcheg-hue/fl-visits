#!/usr/bin/env python3
"""One entry point for every command line in the project.

    fl.py                       list the commands
    fl.py <command> [args...]   run one

Each module under `backend/` keeps its own `main()`, because the way a format
reader is checked is by printing what it read, and the way a patch is applied
without the web page is by running it. What moved here is only the dispatch:
inside a package, `python3 backend/live/dockdist.py` cannot resolve its own
relative imports, and the alternative is `python3 -m backend.live.dockdist`
written out longhand every time.

Argument parsing stays in the module. `sys.argv` is rewritten so that a
module's own `--help` prints the command's name and not this file's.
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# command -> module. Grouped the way the folders are, because which tier a
# command sits in is the thing worth knowing before running it: `game` only
# reads, `live` writes to the running game or to a file beside a `.vanilla`.
COMMANDS = {
    "bases": "backend.game.bases",
    "equipment": "backend.game.equipment",
    "market": "backend.game.market",
    "netlog": "backend.game.netlog",
    "news": "backend.game.news",
    "reputation": "backend.game.reputation",
    "rumors": "backend.game.rumors",
    "ships": "backend.game.ships",
    "story": "backend.game.story",
    "infocards": "backend.game.infocards",
    "jobs": "backend.game.jobs",
    "jumps": "backend.game.jumps",
    "visits": "backend.game.flvisits",
    "weapons": "backend.game.weapons",
    "wrecks": "backend.game.wrecks",

    "bestpath": "backend.live.bestpath",
    "dockdist": "backend.live.dockdist",
    "drawdist": "backend.live.drawdist",
    "inject": "backend.live.inject",
    "newgame": "backend.live.newgame",
    "persist": "backend.live.persist",
    "speed": "backend.live.speed",
    "thrusters": "backend.live.thrusters",
    "tradelane": "backend.live.tradelane",
}

WRITES = {"bestpath", "dockdist", "drawdist", "inject", "newgame", "persist",
          "speed", "thrusters", "tradelane"}


def usage():
    print(__doc__.splitlines()[0])
    print()
    for tier, title in (("reads", "reads the game data"),
                        ("writes", "writes to the running game or its files")):
        print(f"  {title}:")
        for name in sorted(COMMANDS):
            if (name in WRITES) == (tier == "writes"):
                first = (importlib.import_module(COMMANDS[name]).__doc__
                         or "").splitlines()[0]
                print(f"    fl.py {name:<11} {first}")
        print()


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        usage()
        return
    name = sys.argv[1]
    if name not in COMMANDS:
        sys.exit(f"no such command: {name}\nrun `fl.py` for the list")
    module = importlib.import_module(COMMANDS[name])
    # The module's argparse prints `sys.argv[0]` in its usage line, so give it
    # the name the reader typed rather than "fl.py".
    sys.argv = [f"fl.py {name}"] + sys.argv[2:]
    module.main()


if __name__ == "__main__":
    main()
