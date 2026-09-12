"""What the job board at every base is capable of paying.

    fl.py jobs --top 20
    fl.py jobs --all

A bar's board shows you what it is offering **today**. It never shows what it
is capable of offering, so the only way to learn that one base pays sixteen
times what your home station pays is to fly there and look. That number is in
the data, and two files hold it between them:

    DATA/MISSIONS/mbases.ini
        [MVendor]      num_offers  = 2, 4
                                     how many jobs hang on the board at once
        [BaseFaction]  mission_type = DestroyMission, 0.0, 0.1124, 30
                                     ^ kind          ^min  ^max    ^weight
                       the band of difficulty that faction draws inside, and
                       its weight against the other factions on the same base

    DATA/RANDOMMISSIONS/diff2money.ini
        Diff2Money = 0.1124, 2655    a 23-point ladder, difficulty -> credits,
                                     from 1800 at 0.0 to 247065 at 100.0

So a board's ceiling is the money at the highest `max` it offers, and its floor
is the money at the lowest `min`. Counted on a stock install:

  * **160 of the 164 dockable bases run a live board.** Planet Primus, Planet
    Gammu and Planet Toledo carry no `[BaseFaction] mission_type` at all, and
    Planet Sprague carries one but `num_offers = 0, 0`, so its board is shut.
    `--all` lists the four.
  * **All 241 `mission_type` rows in the game are `DestroyMission`**, which is
    the only random mission type vanilla ships. The kind is carried through
    rather than assumed, so a mod that adds another one gets listed instead of
    being silently counted as a bounty.
  * 101 bases have one faction offering work, 51 have two, 11 have three and
    one has five.
  * The ceiling is 146192, at Ruiz Base, Planet Malta, Planet Crete and Tripoli
    Shipyard. The lowest live board pays 2200.

**Deliberately not modelled: what the job sends at you.**
`DATA/RANDOMMISSIONS/npcranktodiff.ini` maps (NPC rank, wing size) to the same
difficulty number, so the game plainly inverts it to choose your enemy, and a
"rank 9, four ships" column would be worth having. The direction of that
inversion is nowhere in the files. Same for "what the best of N offers comes
to": how the draw is distributed inside a band is not written down either. This
is the `decay_per_second` rule in CLAUDE.md, and it applies here for the same
reason: a number on the page implies a model, and neither model is proven.
"""

import argparse
import bisect
import os

from . import flvisits as fl
from . import market as mk
from . import wrecks as wr

MBASES = os.path.join("MISSIONS", "mbases.ini")
LADDER = os.path.join("RANDOMMISSIONS", "diff2money.ini")


def _entries(pairs):
    out = {}
    for key, values in pairs:
        out.setdefault(key.lower(), []).append(values)
    return out


def load_ladder(data_dir):
    """[(difficulty, credits)], ascending. The game's own pay scale."""
    out = []
    for _section, pairs in wr.read_multi(fl.ipath(data_dir, LADDER)):
        for key, values in pairs:
            if key.lower() == "diff2money" and len(values) >= 2:
                out.append((float(values[0]), float(values[1])))
    return sorted(out)


def money(ladder, difficulty):
    """Credits at a difficulty, straight off the ladder or between two rungs.

    **The interpolation is not decoration, and must not be flattened into a
    lookup.** Four of the 19 band edges in `mbases.ini` miss their ladder rung
    by float32 noise between the two files: 0.11239 against the ladder's
    0.112387, the same value written twice at different precision. Walking
    between the neighbouring rungs puts those within a credit of where they
    belong. A lookup would have to decide what to do with a value that is on no
    rung, and every answer to that is a guess.
    """
    if not ladder:
        return 0.0
    steps = [d for d, _cr in ladder]
    i = bisect.bisect_left(steps, difficulty)
    if i <= 0:
        return ladder[0][1]
    if i >= len(ladder):
        return ladder[-1][1]
    (d0, c0), (d1, c1) = ladder[i - 1], ladder[i]
    if d1 == d0:
        return c1
    return c0 + (c1 - c0) * (difficulty - d0) / (d1 - d0)


def _boards(data_dir):
    """base nickname -> {offers, jobs}, straight out of `mbases.ini`.

    `wrecks.read_multi` rather than the reader in `flvisits.py`, because
    `mission_type` and `npc` repeat inside one `[BaseFaction]` and that one
    collapses repeats. Same borrow, from the same place, that `equipment.py`
    makes for the market files.
    """
    out, here = {}, None
    faction = ""
    for section, pairs in wr.read_multi(fl.ipath(data_dir, MBASES)):
        name = section.lower()
        entry = _entries(pairs)
        if name == "mbase":
            got = entry.get("nickname")
            here = got[0][0].lower() if got and got[0] else None
            if here:
                out[here] = {"offers": [0, 0], "jobs": []}
        elif here is None:
            continue
        elif name == "mvendor":
            got = entry.get("num_offers")
            if got and len(got[0]) >= 2:
                out[here]["offers"] = [int(float(got[0][0])),
                                       int(float(got[0][1]))]
        elif name == "basefaction":
            got = entry.get("faction")
            faction = got[0][0] if got and got[0] else ""
            for values in entry.get("mission_type", []):
                if len(values) < 4:
                    continue
                out[here]["jobs"].append({
                    "kind": str(values[0]),
                    "faction": faction,
                    "low": float(values[1]),
                    "high": float(values[2]),
                    "weight": int(float(values[3])),
                })
    return out


def load_boards(game_dir=None, live_only=True):
    """One row per base that offers work, richest board first.

    Every base is a `market.base_index` shape, `{id, name, system, sys, at}`,
    so a base looks the same here as it does on Trade and on Equipment. The
    faction is its **nickname**: turning that into a label needs the reputation
    model, which the server has loaded already and this module has no business
    loading a second time.

    `live_only` drops a board that can never show you anything, which is the
    three bases with no offering faction and the one whose `num_offers` is
    `0, 0`. Pass False to see them and why.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    data_dir = fl.ipath(game_dir, "DATA")
    ladder = load_ladder(data_dir)
    dockable, ref, _sysname = mk.base_index(game_dir, data_dir)

    rows = []
    for key, board in _boards(data_dir).items():
        # The same 164 the rest of the tool counts. A board at a base you can
        # never land on is not work you can take.
        if key not in dockable:
            continue
        jobs = board["jobs"]
        shut = not jobs or board["offers"][1] <= 0
        if shut and live_only:
            continue
        share = sum(j["weight"] for j in jobs) or 1
        offers = sorted(
            ({"kind": j["kind"], "faction": j["faction"],
              "floor": round(money(ladder, j["low"])),
              "best": round(money(ladder, j["high"])),
              "share": round(100 * j["weight"] / share)} for j in jobs),
            key=lambda j: (-j["best"], j["faction"]))
        row = dict(ref(key))
        row.update({
            "best": max((j["best"] for j in offers), default=0),
            "floor": min((j["floor"] for j in offers), default=0),
            "offers": board["offers"],
            "board": offers,
            # Why nothing is on this board, for the one caller that asks for
            # the dead ones. None when the board runs.
            "shut": ("nobody there offers work" if not jobs
                     else "the board holds no offers") if shut else None,
        })
        rows.append(row)
    rows.sort(key=lambda r: (-r["best"], r["name"]))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--all", action="store_true",
                    help="include the bases whose board never offers anything")
    args = ap.parse_args()

    rows = load_boards(args.game, live_only=not args.all)
    live = [r for r in rows if not r["shut"]]
    print(f"{len(live)} boards, richest first\n")
    print(f"{'BASE':<30}{'SYSTEM':<20}{'BEST':>9}{'FLOOR':>9}  OFFERS  FROM")
    for row in rows[:args.top]:
        if row["shut"]:
            continue
        low, high = row["offers"]
        who = ", ".join(sorted({j["faction"] for j in row["board"]}))
        print(f"{row['name'][:29]:<30}{row['system'][:19]:<20}"
              f"{row['best']:>9,}{row['floor']:>9,}   {low}-{high:<4}  {who}")
    if args.all:
        dead = [r for r in rows if r["shut"]]
        print(f"\n{len(dead)} dockable bases run no board at all")
        for row in dead:
            print(f"   {row['name'][:29]:<30}{row['system'][:19]:<20}{row['shut']}")
