"""Equipment → DPS: a loadout's damage per second.

The page half is in `frontend/dps.py`.
"""


def _weapons(ctx):
    """Every gun in the game with its DPS, from the files alone.

    Static: no save and no running game. The page fetches it once and keeps
    it, which is why this is its own endpoint and not part of the poll.
    """
    return {"weapons": ctx.game.weapons}


API = {"weapons": _weapons}
