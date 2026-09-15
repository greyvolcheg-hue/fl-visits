"""Make trading move reputation, which vanilla Freelancer does not.

    fl.py trade                 the hold, the base, and what a run is worth
    fl.py trade 3000000         three million credits of trade, neutral to friend

**Haul ten million credits through a Liberty station and nobody there thinks
any better of you.** The owner asked whether that can be changed. It can, but
not in the game's data, and that is the finding this module is built around.

## There is no trade event, and the binary says so

`DATA/MISSIONS/empathy.ini` uses four `event` names and all 55 faction blocks
carry all four. That is not merely what vanilla happens to use: the parser's own
keyword pool sits in `DLLS/BIN/content.dll` at file offset 0x11a860 and reads,
in order, `MarketGood`, `FactionGood`, `random_mission_abortion`,
`random_mission_failure`, `random_mission_success`, `object_destruction`,
`event`, `group`, `empathy_rate`, `RepChangeEffects`. **There is no fifth event
to switch on**, so a line added to `empathy.ini` would name a word the parser
does not know.

It fits what was measured on 2026-09-15: the engine's dispatch is selective and
`random_mission_abortion` does not reach the empathy table at all. See
*cancelling a mission hits the giver and nobody else* in CLAUDE.md.

So standing is moved from outside, the way the Engine tab moves cruise speed,
and **nothing here writes to a game file**. Standing lives in the save, so a
value written into the running game is kept the next time the game saves.

## The size of a trade is cargo times price, never the credit delta

**The owner's correction, and it is what makes this feature honest.** A single
visit to a base can sell equipment, buy a gun, pay for repairs and collect a
mission reward, and every one of those moves credits. Sizing the trade by what
the balance did would silently count all of it, which is this project's worst
failure mode: a number that is wrong and looks right.

So the credit balance is **deliberately not read**. What is read is the hold,
and a trade is worth the units that moved times what this base pays for them.
That is immune to everything above by construction, and it is the truer figure
anyway, since it is the market's valuation rather than whatever was haggled.

## What is in memory, and how it is found

    standings   copies of a 55-entry table, 0x1b8 (440) bytes apart. An entry
                is 8 bytes and starts with the float32 standing. The entries
                sit in **the order `initialworld.ini` declares its groups**,
                which is why `rep.Model` carries `order`.

                **It is not `empathy.ini`'s order**, and that is worth knowing
                because the two are the same for the first quarter and then
                diverge, so a wrong reading looks right for long enough to be
                believed. Measured against the running game on 2026-09-15:
                `initialworld.ini` agrees with 55 slots of 55, `empathy.ini`
                with 23. The failure it would have caused is the worst kind
                available here, writing a correct number onto the wrong
                faction.
    hold        a contiguous array, stride **48**, the item's `FLHash` at the
                start of an entry and its unit count at **+16**. Free slots
                follow the live entries, which is what lets a newly bought
                commodity appear without the array moving.

Both are found by searching for values this tool already knows from the save it
is following, so there is no constant to go stale and the search validates
itself. Same rule as `speed.py`, and the same reason.

**The base under your feet is not hunted for in memory.** The save carries
`[Player] base` as a plain nickname and the game rewrites it on docking, which
is exactly when trading happens. A memory scan for something already sitting in
a file this tool reads every five seconds would be work for nothing.

**The second dword of a standing entry is not identified.** It holds pointers
for some factions and small integers for others. Nothing here reads or writes
it.

**Which of the four standing tables is authoritative is not known.** Until it
is measured, `locate_standings` returns all of them and the caller decides.
"""

import argparse
import json
import os
import re
import struct
import sys
import tempfile
import threading
import time

from . import proc
from ..game import flvisits as fl
from ..game import market
from ..game import reputation as rep

# One standing entry: the float32, then a field deliberately left alone.
ENTRY = 8

# A hold entry. Measured against the save's own nine cargo lines: walking the
# array from a confirmed entry in both directions reproduces all nine at this
# stride, with the count always at +16.
CARGO_STRIDE = 48
CARGO_COUNT_AT = 16

# How far either side of a known entry to look for the rest of the hold. The
# free slots that follow the live entries are inside this, so a commodity
# bought after the scan shows up without relocating the array.
CARGO_SPAN = 64

# Neutral to friendly, taken from the Reputation tab's own goals rather than
# typed here, so the two can never drift. `empathy.py` takes it from the same
# place for the same reason.
SPAN = rep.GOALS["friend"] - rep.GOALS["neutral"]

# Below this a "grind" is one good run, which makes this a button that hands
# out standing rather than an expensive alternative to flying missions. It
# scolds and writes anyway: the owner's call for the Nomad count, and it is
# his game.
SOFT_FLOOR = 250_000

# **The most one transaction may move the faction you traded with, or None
# for no limit.** It was `SPAN / 10` until the numbers were on the table:
# the biggest hold a player can buy is a Dromedary's 275, the dearest cargo is
# Alien Organisms at 2000, so the largest single trade in the game is 550,000
# credits of value and asks for +0.0917, which is 18% of neutral-to-friendly.
# The cap turned 5.5 maximum loads into 10 and did nothing at all below
# 300,000, which is every ordinary run. The owner read that and took it off.
#
# `capped` still exists and still scales the whole spread by one factor rather
# than clipping each faction, because a limit that reshapes the relationships
# would be worse than none. Setting this to a number turns it back on.
MAX_STEP = None


class NotFound(Exception):
    """Something this module must locate is not where the save says it is."""


def rate_for(credits):
    """Standing per credit of traded value.

    `credits` is the whole journey from neutral to friendly, which is the only
    question worth asking of this feature and the axis the owner picked for the
    Nomad grind. The rate is derived so the two can never disagree.
    """
    if credits <= 0:
        raise ValueError("credits to friendly must be positive")
    return SPAN / credits


def spread(empathy, doer, delta):
    """`delta` to `doer`, and what the empathy table makes of it elsewhere.

    **The sign convention is the game's own and is not inverted here.** A
    faction's `empathy_rate` toward another is negative when they are enemies,
    so a positive delta for the doer times a negative rate is a loss for their
    enemy. Trading with Liberty Police cools the Rogues by exactly the
    arithmetic that killing a Rogue warms the Police.

    Only the 47 factions `rep.load_model` keeps are moved. The eight it cuts
    are the Nomads and the story doubles, who have nobody in any bar and no
    opinion to have about a cargo run.
    """
    out = {doer: delta}
    for target, rate in empathy.get(doer, {}).items():
        if target != doer and rate:
            out[target] = delta * rate
    return out


def capped(moves, doer):
    """`moves`, scaled down together if the doer's own step is too big.

    Scaling the whole dict by one factor rather than clipping each entry is
    what keeps the empathy ratios intact: a capped trade is a smaller trade,
    not a differently-shaped one.

    `MAX_STEP` of None is no limit, which is where the owner left it.
    """
    step = abs(moves.get(doer, 0.0))
    if MAX_STEP is None or step <= MAX_STEP or step == 0:
        return moves, 1.0
    factor = MAX_STEP / step
    return {k: v * factor for k, v in moves.items()}, factor


# --- what a trade was worth -----------------------------------------------

def prices_at(rows, base_id):
    """{commodity: price} for one base, from the market this tool already loads."""
    key = base_id.lower()
    return {r["good"]: r["price"] for r in rows
            if r["base"]["id"].lower() == key}


def turnover(before, after, prices):
    """What moved, valued at this base's own prices.

    Bought and sold both count and both count positive: the owner asked for
    *"за каждый купленный или проданный кредит"*, and being a customer is
    business either way.

    A commodity this base does not trade is skipped rather than guessed at. It
    cannot have been bought or sold here, so units of it moving means something
    else happened to the hold, and inventing a price for it would be inventing
    a trade.
    """
    moved, skipped = 0, []
    for nick in set(before) | set(after):
        units = abs(after.get(nick, 0) - before.get(nick, 0))
        if not units:
            continue
        if nick not in prices:
            skipped.append(nick)
            continue
        moved += units * prices[nick]
    return moved, skipped


# --- finding things in the running game ------------------------------------

def _scan(pid, needle):
    """Every address in writable memory holding `needle`."""
    hits = []
    for lo, hi, perms, _name in proc.mappings(pid):
        if "r" not in perms or "w" not in perms:
            continue
        for addr, buf in proc.chunks(pid, lo, hi, overlap=len(needle)):
            i = buf.find(needle)
            while i != -1:
                hits.append(addr + i)
                i = buf.find(needle, i + 1)
    return hits


def locate_standings(pid, standings, order, tol=0.05, need=50):
    """Every copy of the standing table, as a list of base addresses.

    Anchors on one faction whose value is unique among the 55, then tries that
    hit as each of the 55 slots in turn and keeps the alignments where the
    whole table lines up.

    **The tolerance is not slack, it is the clock.** The save was written in
    the past and the player has been flying since; on the run this was built
    against every standing had drifted about 0.003 in half a minute. `need` of
    them must still match, and every value must be a standing at all, which is
    what stops this locking onto a stretch of unrelated floats.
    """
    unique = [n for n in order
              if n in standings and abs(standings[n]) > 0.01
              and sum(1 for v in standings.values()
                      if abs(v - standings[n]) < 1e-6) == 1]
    if not unique:
        raise NotFound("no standing in this save is distinctive enough to "
                       "anchor on: every value is shared or near zero")
    # **Every distinctive standing is tried as the anchor, not just the first.**
    # The anchor has to match a float32 exactly, and the live value drifts away
    # from the save the moment the player shoots anything, so any one faction
    # is a coin toss. Some faction always has not moved: on the run this was
    # built against, 17 of the 55 were untouched between two saves half an hour
    # apart. Trying them in turn turns "usually works" into "works".
    found = []
    for anchor in unique:
        slot = order.index(anchor)
        for hit in _scan(pid, struct.pack("<f", standings[anchor])):
            base = hit - slot * ENTRY
            try:
                buf = proc.read(pid, base, len(order) * ENTRY)
            except OSError:
                continue
            if len(buf) < len(order) * ENTRY:
                continue
            ok = 0
            for i, nick in enumerate(order):
                v = struct.unpack_from("<f", buf, i * ENTRY)[0]
                if not -1.0 <= v <= 1.0:
                    ok = -1
                    break
                if nick in standings and abs(v - standings[nick]) <= tol:
                    ok += 1
            if ok >= need and base not in found:
                found.append(base)
        if found:
            break
    if not found:
        raise NotFound(
            f"no run of {len(order)} standings in the game matches this save "
            f"within {tol}. Either the save being followed is not the game "
            f"that is running, or the table has moved.")
    return sorted(found)


def read_standings(pid, base, order):
    """{faction: standing} out of one copy of the table."""
    buf = proc.read(pid, base, len(order) * ENTRY)
    return {nick: struct.unpack_from("<f", buf, i * ENTRY)[0]
            for i, nick in enumerate(order)}


def write_standings(pid, base, order, moves, current=None):
    """Add `moves` to the table at `base`. Returns what each faction became.

    Read, add, clamp, write, and only the entries that actually move. The
    game writes this table too, so touching a faction nobody traded with
    would be this tool picking a fight it does not need to.
    """
    now = current if current is not None else read_standings(pid, base, order)
    became = {}
    for i, nick in enumerate(order):
        delta = moves.get(nick)
        if not delta:
            continue
        value = rep.clamp(now[nick] + delta)
        proc.write(pid, base + i * ENTRY, struct.pack("<f", value))
        became[nick] = value
    return became


CARGO_LINE = re.compile(r"^\s*cargo\s*=\s*(\d+)\s*,\s*(\d+)", re.I | re.M)


def save_cargo(saved):
    """Every `cargo` line in the save as {hash: units}, commodity or not.

    **Equipment counts here and is filtered out later.** The anchor for the
    cargo array has to exist even when you are carrying no freight at all, and
    the nanobots, batteries and countermeasures always aboard sit in the same
    array as the cargo. Anchoring only on commodities would leave the watcher
    blind exactly when it matters most, on the run out to buy the first load.
    """
    out = {}
    for token, units in CARGO_LINE.findall(saved):
        out[int(token)] = out.get(int(token), 0) + int(units)
    return out


def locate_hold(pid, cargo):
    """Base addresses of every cargo-array entry the save agrees with.

    `cargo` is `save_cargo`'s mapping. A site counts only when an item's hash
    and its exact unit count sit 16 bytes apart, which is what separates a real
    hold entry from the hundreds of places an item hash appears in the loaded
    market tables: for the one commodity aboard when this was written, 286
    sites held the hash and 8 held the count as well.

    The anchor is the entry with the largest count, because a count of 1 is
    worth very little as a discriminator.
    """
    if not cargo:
        raise NotFound("the save lists no cargo at all, so there is nothing "
                       "to anchor the cargo array on")
    key, units = max(cargo.items(), key=lambda kv: kv[1])

    # **One entry is not a signature, and measuring that was the lesson.** The
    # first version anchored on the single largest count and found 218 sites:
    # the game keeps a pool of NPC loadouts that carry the same ordinary items
    # in the same shape, so "an item with this count" describes hundreds of
    # ships. What is unique to the player is carrying **this whole set at
    # once**, so a candidate is scored by how much of the save's cargo list
    # appears in its own array.
    want = min(len(cargo), 3)
    found = []
    for hit in _scan(pid, struct.pack("<I", key)):
        try:
            got = proc.read(pid, hit + CARGO_COUNT_AT, 4)
        except OSError:
            continue
        if len(got) != 4 or struct.unpack("<I", got)[0] != units:
            continue
        seen = _raw_entries(pid, hit)
        hits = sum(1 for k, u in cargo.items() if seen.get(k) == u)
        if hits >= want:
            found.append((hits, -sum(1 for k in seen if k not in cargo), hit))
    if not found:
        raise NotFound(
            f"no cargo array in the game carries the {len(cargo)} items this "
            f"save lists. The save being followed is probably not the game "
            f"that is running.")
    # **Best first, and "best" is fewest leftovers.** Several arrays carry the
    # save's whole list, because the game keeps more than one view of a hold.
    # The stale ones keep what you were carrying before: on the run this was
    # written, the save listed four items and no freight, and the array with
    # nine extra entries still held 70 sidearms that had already been sold.
    # The live one is the one that says what the save says and nothing else.
    found.sort(reverse=True)
    return [hit for _h, _e, hit in found]


def _raw_entries(pid, anchor):
    """{item hash: units} straight out of the array around `anchor`."""
    lo = anchor - CARGO_SPAN * CARGO_STRIDE
    span = (2 * CARGO_SPAN + 1) * CARGO_STRIDE
    try:
        buf = proc.read(pid, lo, span)
    except OSError:
        try:
            buf = proc.read(pid, anchor, CARGO_SPAN * CARGO_STRIDE)
        except OSError:
            return {}
    out = {}
    for off in range(0, len(buf) - CARGO_COUNT_AT - 4, CARGO_STRIDE):
        key = struct.unpack_from("<I", buf, off)[0]
        units = struct.unpack_from("<I", buf, off + CARGO_COUNT_AT)[0]
        if key and 0 < units < 100000:
            out[key] = out.get(key, 0) + units
    return out


def read_consensus(pid, anchors, goods):
    """The hold most of the candidate arrays agree on, and how many agreed.

    **No single array is trusted, because picking one is what failed twice.**
    The game keeps many copies of a hold and some of them are dead snapshots.
    Ranking them by how well they match the save picks the *worst* one for
    this job by construction: a snapshot that stopped updating matches a save
    written before the trade exactly, which is precisely the tick where it
    must not be believed. That is not a theory, it is what happened at
    `li03_01_base` on 2026-09-15: the chosen array read an empty hold for
    fifteen seconds across a purchase, while every other copy had the cargo.

    A dead copy cannot outvote seventeen live ones, so the answer is the one
    the most arrays give. Ties go to the best-ranked, which keeps it
    deterministic.
    """
    tally, first = {}, {}
    for a in anchors:
        got = read_hold(pid, a, goods)
        key = tuple(sorted(got.items()))
        tally[key] = tally.get(key, 0) + 1
        first.setdefault(key, len(first))
    if not tally:
        return {}, 0
    key = max(tally, key=lambda k: (tally[k], -first[k]))
    return dict(key), tally[key]


def read_hold(pid, anchor, goods):
    """{commodity: units} from the cargo array around `anchor`.

    Reads a window rather than walking to the ends of the array: the bounds
    are not marked in any way this has established, and a window wide enough to
    hold the free slots after the live entries is both simpler and what lets a
    newly bought commodity be seen.
    """
    by_hash = {fl.fl_hash(n): n for n in goods}
    return {by_hash[k]: u for k, u in _raw_entries(pid, anchor).items()
            if k in by_hash}


def current_base(saved):
    """The base the save says you are standing on, as a nickname.

    `[Player] base` is a plain nickname, not a hash, and the game rewrites it
    when you dock. That is the whole reason this module never hunts for the
    base in memory.
    """
    m = re.search(r"^\s*base\s*=\s*(\S+)\s*$", saved, re.M)
    return m.group(1).lower() if m else None


def main():
    ap = argparse.ArgumentParser(prog="fl.py trade")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--save", help="the save to read; the newest by default")
    ap.add_argument("credits", nargs="?", type=int,
                    help="credits of traded value from neutral to friendly")
    args = ap.parse_args()

    if args.credits is not None:
        if args.credits < SOFT_FLOOR:
            print(f"note: {args.credits:,} is under {SOFT_FLOOR:,}, about one "
                  f"good run. That is a handout rather than a grind, but it "
                  f"is your game.", file=sys.stderr)
        r = rate_for(args.credits)
        print(f"{args.credits:,} credits of trade from neutral to friendly")
        print(f"  {r:.3e} standing per credit")
        print(f"  one trade is capped at {MAX_STEP:+.4f}, so at least "
              f"{SPAN / MAX_STEP:.0f} separate trades to cross it")
        return

    # **Imported here rather than at the top.** `serve.py` is the server and
    # this is a backend module; importing it for a path would invert the two
    # layers for every caller, including the tabs that never need a save path.
    sys.path.insert(0, os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    import serve  # noqa: PLC0415

    save = args.save or serve.find_default_save(args.game)
    saved = fl.decode_save(save)
    model = rep.load_model(args.game)
    names, rows = market.load_market(args.game)
    held = market.hold(saved, names)
    base_id = current_base(saved)
    pid = proc.find_pid()

    print(f"save   {os.path.basename(save)}")
    print(f"base   {base_id or 'not docked'}")
    print(f"hold   {held or 'empty'}")

    tables = locate_standings(pid, rep.player_reps(saved), model.order)
    print(f"\nstanding tables found: {len(tables)} "
          f"{[hex(t) for t in tables]}")
    cargo = save_cargo(saved)
    if cargo:
        holds = locate_hold(pid, save_cargo(saved))
        print(f"cargo arrays found:    {len(holds)} {[hex(h) for h in holds]}")
        print(f"hold read from memory: {read_hold(pid, holds[0], names)}")
    if base_id:
        p = prices_at(rows, base_id)
        print(f"prices at this base:   {len(p)} commodities")


# --- the setting -----------------------------------------------------------

SETTINGS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "data", "trade.json")

DEFAULTS = {"credits": 3_000_000, "on": False}


def load_setting(path=SETTINGS):
    """What the owner asked for. A missing or broken file reads as the default.

    Same bargain as `common.load_marks`: unreadable is not an error, because a
    corrupt file should cost the setting rather than the Engine tab.
    """
    out = dict(DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            held = json.load(fh)
    except (OSError, ValueError):
        return out
    if isinstance(held.get("credits"), int) and held["credits"] > 0:
        out["credits"] = held["credits"]
    out["on"] = bool(held.get("on"))
    return out


def save_setting(setting, path=SETTINGS):
    """Replace the file in one step. `common._write_marks`'s idiom, and why."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=folder, prefix=".trade-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            json.dump(setting, fh, ensure_ascii=False, sort_keys=True)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    return setting


# --- applying it -----------------------------------------------------------

def validate(pid, base, standings, order, tol=0.05, need=50):
    """Does the table at `base` still look like the standing table?

    **Every write is preceded by this.** The cached address survives a world
    load only by luck, and the cost of being wrong is writing floats into
    whatever now lives there. It is one 440-byte read, so there is no reason
    to skip it and every reason not to.
    """
    try:
        buf = proc.read(pid, base, len(order) * ENTRY)
    except OSError:
        return False
    if len(buf) < len(order) * ENTRY:
        return False
    ok = 0
    for i, nick in enumerate(order):
        v = struct.unpack_from("<f", buf, i * ENTRY)[0]
        if not -1.0 <= v <= 1.0:
            return False
        if nick in standings and abs(v - standings[nick]) <= tol:
            ok += 1
    return ok >= need


def apply_trade(pid, tables, order, empathy, doer, value, credits):
    """Move standings for `value` credits of trade with `doer`.

    Returns what happened, in the shape the page shows: the faction dealt with,
    the credits, the raw and capped step, and what every moved faction became.

    **Every copy of the table is written.** Which one the engine reads is not
    established, they agree with each other to the bit, and writing one while
    leaving three behind would be a guess whose failure mode is a change that
    seems to work and then reverts.
    """
    raw = value * rate_for(credits)
    moves, factor = capped(spread(empathy, doer, raw), doer)
    became = {}
    for base in tables:
        became = write_standings(pid, base, order, moves)
    return {"faction": doer, "credits": value, "step": moves.get(doer, 0.0),
            "uncapped": raw, "capped": factor < 1.0, "moved": became}


# --- watching --------------------------------------------------------------

class Watcher:
    """Follows the hold while you are docked and bills the difference.

    **It only counts while something is watching.** The hold lives in the
    running game and nowhere else between saves, so a trade made with this
    stopped is a trade nobody saw. That is stated on the page rather than
    hidden, because the alternative is a player who thinks the feature is
    broken when it was simply not running.
    """

    POLL = 3.0

    def __init__(self, game_dir, save_for, model, names, rows, owners):
        self.game_dir = game_dir
        self.save_for = save_for          # callable -> current save path
        self.model, self.names, self.rows = model, names, rows
        # `GameData` already walked every system for these and the walk is
        # static, so it is handed in rather than repeated in this thread.
        self.owners = owners
        self.pid = None
        self.tables, self.anchors = [], []
        self.last_base, self.last_hold = None, None
        self.history = []
        self.trace = []
        self.error = None
        self._stop = threading.Event()
        self._thread = None

    # -- the one step, exposed so it can be driven by hand in a test --------

    def tick(self):
        saved = fl.decode_save(self.save_for())
        base = current_base(saved)
        if not base:
            # In space. Whatever the hold was at the last base is history, and
            # keeping it would bill the next dock for the journey.
            self.last_base, self.last_hold, self.anchors = None, None, []
            self._note(None, None, {}, False, False, 0)
            return None
        standings = rep.player_reps(saved)

        if self.pid is None:
            self.pid = proc.find_pid()
        if not self.tables or not validate(self.pid, self.tables[0],
                                           standings, self.model.order):
            self.tables = locate_standings(self.pid, standings,
                                           self.model.order)

        # **The anchor is chosen once per docking, and then left alone.**
        # Both halves of that are paid for:
        #
        #   Caching it across dockings failed, because the array moves. One
        #   address held from the first dock saw nothing ever again, since a
        #   dead copy answers reads perfectly well and so never looks stale.
        #
        #   Re-choosing it every tick failed too, and more subtly. Candidates
        #   are ranked against the save, the game rewrites the save when you
        #   trade, so **the event being watched for is itself what changes the
        #   ranking**. The anchor moved at the exact moment of the sale, the
        #   tick saw a different address, re-baselined, and billed nothing.
        #
        # Docking is the moment when the save is fresh and the ranking is
        # trustworthy, and it is the only moment the array is known to move.
        # **The candidate set is found once per docking; the answer is the
        # vote of all of them on every tick.** Docking is when the save is
        # fresh and the ranking can be trusted to find the arrays at all, and
        # it is the only moment they are known to move. Which one is live is
        # then never decided, because deciding it is what failed: see
        # `read_consensus`.
        if base != self.last_base or not self.anchors:
            self.anchors = locate_hold(self.pid, save_cargo(saved))
            self.last_hold = None
        hold, agreed = read_consensus(self.pid, self.anchors, self.names)
        anchor = self.anchors[0]

        # **Only ever diff two reads of the same array at the same base.** A
        # fresh anchor has no predecessor, and the cost of re-baselining is one
        # missed diff against standing handed out for a trade nobody made.
        done = None
        same = (self.last_hold is not None and self.last_base == base)
        if same:
            value, skipped = turnover(self.last_hold, hold,
                                      prices_at(self.rows, base))
            owner = self.owners.get(base)
            if value and owner and validate(self.pid, self.tables[0],
                                            standings, self.model.order):
                done = apply_trade(self.pid, self.tables, self.model.order,
                                   self.model.empathy, owner, value,
                                   load_setting()["credits"])
                done["base"], done["skipped"] = base, skipped
                self.history.insert(0, done)
                del self.history[8:]
        self.last_base, self.last_hold = base, hold
        self._note(base, anchor, hold, same, done, agreed)
        return done

    def _note(self, base, anchor, hold, diffed, billed, agreed=0):
        """**A tick that does nothing has to be able to say why.**

        Two rounds of debugging were spent guessing from an empty history,
        which only ever reports the ticks that fired. This reports the ones
        that did not, which is where both bugs were.
        """
        self.trace.insert(0, {
            "at": time.strftime("%H:%M:%S"), "base": base,
            "anchor": None if anchor is None else f"{anchor:#x}",
            "hold": dict(hold), "diffed": bool(diffed),
            "billed": bool(billed), "agreed": agreed,
            "of": len(self.anchors)})
        del self.trace[12:]

    # -- the thread --------------------------------------------------------

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def running(self):
        return bool(self._thread and self._thread.is_alive()
                    and not self._stop.is_set())

    def _run(self):
        while not self._stop.wait(self.POLL):
            try:
                self.tick()
                self.error = None
            except (NotFound, proc.NotRunning) as exc:
                # Expected: the game is closed, or between world loads. Say so
                # and keep waiting rather than killing the thread, because the
                # next dock is the whole point.
                self.error = str(exc)
                self.pid, self.tables, self.anchors = None, [], []
            except Exception as exc:                      # noqa: BLE001
                self.error = f"{type(exc).__name__}: {exc}"


def base_owners(game_dir):
    """base nickname -> owning faction, from the reader that already has it.

    `bases.base_owners` is the one walk that answers this and `common.Ctx`
    already builds it for the badges on every tab. The watcher runs beside the
    server rather than inside a request, so it takes its own copy once rather
    than reaching into a `Ctx` it does not own.
    """
    return bases.base_owners(fl.ipath(game_dir, "DATA"), fl.system_files)
