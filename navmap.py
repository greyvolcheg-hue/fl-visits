#!/usr/bin/env python3
"""Turn a Freelancer world position into the sector the nav map shows.

The map divides a system into 8 by 8 cells, lettered A to H across (x) and
numbered 1 to 8 down (z), so an object sits in something like `E6`. Note that
guides disagree on the order: fl-guide.de writes `E6`, the GameFAQs wrecks FAQ
writes `6E`. Same cell.

The constant is not in the game's data files, only in the executable, so it was
fitted instead: against 66 wrecks whose sector the GameFAQs FAQ states, across
32 systems and every `NavMapScale` value in use, 63 come out right. The values
that score 63 form a plateau from 262464 to 268096 and MAP_SIZE is its middle.
Three entries stay wrong at every constant, which is what you would expect from
a hand-written guide, so they were not chased.
"""

MAP_SIZE = 265280  # world units across a system at NavMapScale 1
COLUMNS = "ABCDEFGH"


def sector(x, z, scale=1.0):
    """`E6`, or None when the position falls outside the drawn map."""
    size = MAP_SIZE / (scale or 1.0)
    cell = size / 8
    column = int((x + size / 2) // cell)
    row = int((z + size / 2) // cell)
    if not (0 <= column < 8 and 0 <= row < 8):
        return None
    return f"{COLUMNS[column]}{row + 1}"


def subcell(x, z, scale=1.0):
    """Where inside its cell a position sits: `UR`, `LL`, `C` and so on.

    The cell is divided three by three; the first letter is the row (Upper,
    Centre, Lower), the second the column (Left, Centre, Right), and the dead
    centre is written `C` the way the GameFAQs wrecks FAQ writes it.

    A hint, not a coordinate. Against that FAQ's hand-written annotations 48 of
    63 agree, which is about what two people eyeballing "upper right" would
    manage. The sector itself is far firmer: 63 of 66.
    """
    size = MAP_SIZE / (scale or 1.0)
    cell = size / 8
    across = ((x + size / 2) % cell) / cell
    down = ((z + size / 2) % cell) / cell
    if not (0 <= x + size / 2 <= size and 0 <= z + size / 2 <= size):
        return None
    row = "UCL"[min(2, int(down * 3))]
    column = "LCR"[min(2, int(across * 3))]
    return "C" if row == "C" and column == "C" else row + column


def load_scales(data_dir, read_ini, ipath):
    """system nickname (lower) -> NavMapScale, defaulting to 1.

    Takes the readers as arguments so this module does not import the frozen
    one and drag its game-loading along for callers that only want the maths.
    """
    scales = {}
    for section, entries in read_ini(ipath(ipath(data_dir, "universe"), "universe.ini")):
        if section.lower() != "system":
            continue
        nick = entries.get("nickname")
        if not nick:
            continue
        raw = entries.get("NavMapScale", [1])[0]
        try:
            scales[str(nick[0]).lower()] = float(raw) or 1.0
        except (TypeError, ValueError):
            scales[str(nick[0]).lower()] = 1.0
    return scales
