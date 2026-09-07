"""Which ship the save is flying, and how much it can carry.

    fl.py ships <save.fl> [--game DIR]

The save names the ship by hash, the same one-way `FLHash` the base tracker
resolves, so the nickname comes back the same way: hash all 115 ship nicknames
in `DATA/SHIPS/*.ini` and look the result up.

    ship_archetype = 2805431751     ->  bw_elite2  ->  Sabre, hold 70

**Hold size is the number of units, not a volume to divide by.** All 40
commodities carry `volume = 1.0`, checked, so a hold of 70 is 70 units of
anything. If a mod ever gives a commodity a different volume this stops being
true and the Routes total would need the division put back.
"""

import argparse
import os
import sys

from . import flvisits as fl
from . import wrecks as wr


def load_ships(game_dir):
    """hash -> {nickname, name, hold}, over every ship file in DATA/SHIPS."""
    data_dir = fl.ipath(game_dir, "DATA")
    ships_dir = fl.ipath(data_dir, "SHIPS")
    names = fl.load_names(game_dir)
    out = {}
    for entry in sorted(os.listdir(ships_dir)):
        if not entry.lower().endswith(".ini"):
            continue
        for section, pairs in wr.read_multi(fl.ipath(ships_dir, entry)):
            if section.lower() != "ship":
                continue
            row = {}
            for key, values in pairs:
                row.setdefault(key.lower(), values)
            nick = row.get("nickname")
            if not nick:
                continue
            nick = str(nick[0])
            try:
                hold = int(float(row["hold_size"][0]))
            except (KeyError, IndexError, TypeError, ValueError):
                hold = None
            label = nick
            try:
                label = names.get(int(row["ids_name"][0]), nick)
            except (KeyError, IndexError, TypeError, ValueError):
                pass
            out[fl.fl_hash(nick.lower())] = {
                "nickname": nick, "name": label, "hold": hold}
    return out


def from_save(save_text, ships):
    """{nickname, name, hold} for the ship in this decoded save, or None.

    Takes the text and the loaded table because both are already in hand once
    per request: the save is decoded once under the lock and the 115 ship files
    are read once at startup. `player_ship` below is the version for a command
    line, where neither is.

    None rather than a guessed default: a wrong hold size would silently
    multiply every figure on the Routes tab by the wrong number, which is worse
    than the tab saying it does not know.
    """
    for line in save_text.splitlines():
        head, _, tail = line.partition("=")
        if head.strip().lower() == "ship_archetype":
            try:
                return ships.get(int(tail.split(",")[0].strip()))
            except (TypeError, ValueError):
                return None
    return None


def player_ship(game_dir, save_path):
    """The same, for a caller holding only paths."""
    try:
        return from_save(fl.decode_save(save_path), load_ships(game_dir))
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    args = ap.parse_args()

    ship = player_ship(args.game, args.save)
    if not ship:
        sys.exit("no ship archetype in that save, or it matched no known ship")
    print(f"{ship['name']} ({ship['nickname']}), hold {ship['hold']}")

