"""What more than one tab needs: the loaded game, and one save per request.

`GameData` is the static half, everything that comes out of the install, loaded
once at startup. `Ctx` is the per-request half: the decoded save, read once and
under the lock, and the state derived from it.

Both sat in `serve.py` until 2026-09-07, which meant a tab endpoint had to
import the web server to reach the game data. The server now serves and this
holds what is served.
"""

import functools
import json
import os
import re
import subprocess
import sys
import tempfile
import threading

from .game import bases as bs
from .game import equipment as eqp
from .game import flvisits as fl
from .game import market as mk
from .game import infocards as ic
from .game import jobs as jb
from .game import jumps as jm
from .game import news as nw
from .game import reputation as rep
from .game import rumors as ru
from .game import ships as sh
from .game import wrecks as wr

REVEALED = 1  # story put it on the nav map; the player has never docked there

# The house is a system nickname's first two characters. The seven prefixes
# cover 46 of the 47 systems with a dockable base; the 47th is Omicron Minor,
# whose `st` marks the story systems, and the fallback puts it in Edge Worlds.
HOUSES = [
    ("Liberty", ("li",)),
    ("Bretonia", ("br",)),
    ("Kusari", ("ku",)),
    ("Rheinland", ("rh",)),
    ("Border Worlds", ("bw",)),
    ("Independent Worlds", ("iw",)),
    ("Edge Worlds", ("ew", "hi")),
]
HOUSE_ORDER = [name for name, _ in HOUSES]


def house_of(nickname):
    """Group name for a system nickname.

    An unknown prefix joins Edge Worlds rather than disappearing: a system
    silently dropped from every group would make the totals disagree with the
    sum of the headings, and that is the sort of thing nobody notices.
    """
    prefix = str(nickname)[:2].lower()
    for name, prefixes in HOUSES:
        if prefix in prefixes:
            return name
    return HOUSE_ORDER[-1]


class GameData:
    """The static half: everything that comes out of the install, loaded once.

    It takes about a fifth of a second, so this is comfort rather than need.
    """

    def __init__(self, game_dir):
        self.dir = game_dir  # persist.py needs it to find the files to write
        data_dir = fl.ipath(game_dir, "DATA")
        bases, systems = fl.load_universe(data_dir)
        self.objects = fl.load_objects(data_dir, systems)

        # Keep only bases a player can actually dock at. Same rule as the CLI,
        # from the same place, because these two used to hold their own copies
        # of it and drifted apart. Why 30 of the 197 are dropped is in
        # docking.py and is deliberately not restated here.
        dockable = bs.dockable_bases(game_dir, data_dir, fl.system_files, fl.ipath)
        self.bases = {k: v for k, v in bases.items() if k in dockable}

        self.names = fl.load_names(game_dir)
        self.system_ids = {nick.lower(): ids for nick, ids in systems.items()}
        self.by_hash = {fl.fl_hash(nick): nick for nick in self.objects}
        self.wrecks = wr.load_wrecks(game_dir)
        # Where each base sits on the nav map, from the same walk that decided
        # which bases are dockable at all.
        self.sectors = bs.base_sectors(
            data_dir, fl.system_files,
            bs.load_scales(data_dir, fl.read_ini, fl.ipath))
        # Who owns each base. Static, so it is read once here rather than per
        # request, and the names it resolves against come from the reputation
        # model below, which reads initialworld.ini for the Reputation tab.
        self.owners = bs.base_owners(data_dir, fl.system_files)
        # The empathy table never changes; only the player's own
        # standings come from the save, and those are read per request.
        self.repmodel = rep.load_model(game_dir)
        # Pulled out by name so the Visits tab does not have to know the shape
        # of the reputation model to put a badge on a base.
        self.faction_name = self.repmodel.names
        self.faction_short = self.repmodel.shorts
        # Prices never change while the game runs; only which bases
        # you have seen does, and that comes from the save.
        self.market = mk.load_market(game_dir)
        # The 115 ship archetypes, by the hash a save names them with. Read
        # once here because two tabs want the hold size and re-reading every
        # DATA/SHIPS/*.ini per request to learn one number is absurd.
        self.ships = sh.load_ships(game_dir)
        # Guns and shields with their stats, prices and dealers. Static too,
        # and it reuses `weapons` and `trade.base_index` rather than parsing
        # any of it a second time.
        #
        # **The whole catalogue, unobtainable items included**, and the tab
        # narrows it. The unobtainable are a checkbox on the page, so loading
        # them out here would mean either a second parse of the same files or
        # a checkbox that cannot be ticked. Each row carries a `source` saying
        # how you get it, and `none` is one of the four answers.
        self.gear = eqp.load_catalogue(game_dir, obtainable_only=False)

    # --- the Neural Net's three big tables, loaded on first use ------------
    #
    # Not in `__init__` because they are the expensive ones and only one tab
    # wants them: the infocards are 3 MB of XML to parse and the rumor walk
    # covers 3051 sections. Startup is the thing being protected here, and a
    # page opened on Trade should not pay for a log it will never draw.

    @functools.cached_property
    def cards(self):
        return ic.load_cards(self.dir)

    @functools.cached_property
    def jobs(self):
        """Every live job board, richest first. See `game/jobs.py`.

        Out here with the log's three tables rather than in `__init__` for the
        same reason they are: `mbases.ini` is 42 ms to parse against about 200
        ms of total startup, and one tab wants it. A page opened on Trade
        should not pay for a board list it will never draw.
        """
        return jb.load_boards(self.dir)

    @functools.cached_property
    def jumps(self):
        """Every jump between systems. See `game/jumps.py`.

        Out here with the rest for the same reason: one tab wants it, and it is
        a walk of all 53 system files. Startup is the thing being protected.
        """
        return jm.load_jumps(self.dir)

    @functools.cached_property
    def news(self):
        return nw.load_news(self.dir, self.names)

    @functools.cached_property
    def rumors(self):
        return ru.load_rumors(self.dir, self.names, self.cards)

    def label(self, ids, fallback):
        try:
            return self.names.get(int(ids), fallback)
        except (TypeError, ValueError):
            return fallback

    def system_label(self, system):
        return self.label(self.system_ids.get(system, 0), system)


def _tally(done, total):
    """The three numbers a progress bar needs, for bases or for wrecks alike.

    One shape for both halves of a system row, so the page draws them with one
    function instead of knowing which of `docked` and `stripped` it is holding.
    """
    return {"done": done, "total": total,
            "percent": round(100 * done / total) if total else 0}


VISITED = re.compile(r"^\s*base_visited\s*=\s*(\d+)", re.M | re.I)


def dock_order(saved, game):
    """base -> how many bases you had docked at before this one. First is 0.

    **`base_visited` is the docked bases in the order you first docked at
    them**, which is the only receipt time anything in the Neural Net has.
    Settled 2026-09-10 by measurement, twice, because an order that looks right
    on one save is worth nothing:

      * across the 162 saves on this disk an older save's `base_visited` is a
        prefix of a newer one's, 137 times against 14, and every one of the 14
        sits where two saves at the same `total_time_played` belong to
        different playthroughs. A branch is not a counter-example;
      * on the live save all 24 values resolve to base nicknames, the resolved
        set is **exactly** the docked set the visit flags give, neither way
        round, and the order opens Planet Manhattan, Planet Pittsburgh,
        Baltimore Shipyard, which is the campaign order.

    The values are `FLHash` of the base nickname, the same one-way hash the
    visit flags and the cargo lines use.

    **This says order and nothing else.** `Ctx.docked` stays the authority on
    which bases have been docked at, and a save that carries no `base_visited`
    at all leaves every rumor unranked rather than dropping it.
    """
    by_hash = {fl.fl_hash(key): key for key in game.bases}
    out = {}
    for token in VISITED.findall(saved):
        key = by_hash.get(int(token))
        if key is not None:
            out.setdefault(key, len(out))
    return out


def read_state(game, save_path, saved):
    """Split every base into docked / revealed / unknown, grouped by system.

    Takes the decoded text as well as the path, because decoding is the
    expensive half and one request wants the visit flags, the Neural Net log
    and the hold out of a single read. `Ctx.saved` is what does that read,
    once per request and under the lock; the path is still needed for the
    name and the mtime, which are file facts rather than save contents.
    """
    visits = fl.parse_visits(saved)

    flags = {}
    for hid, flag in visits.items():
        nick = game.by_hash.get(hid)
        if not nick:
            continue
        key = game.objects[nick][1].lower()
        # Docking wins over merely knowing: a planet is reachable through both
        # its mooring fixture and the planet object, and they carry different
        # flags for the same base.
        if flag in fl.DOCKED or key not in flags:
            flags[key] = flag

    bases = {}
    for key, (system, ids) in game.bases.items():
        row = bases.setdefault(system, {"docked": [], "revealed": [], "unknown": []})
        flag = flags.get(key)
        bucket = "docked" if flag in fl.DOCKED else "revealed" if flag == REVEALED else "unknown"
        # The owning faction rides on every base, not just the revealed ones.
        # It costs two dictionary lookups and it is the page, not the payload,
        # that decides where a badge is worth showing.
        owner = game.owners.get(key, "")
        row[bucket].append({"name": game.label(ids, key),
                            "at": game.sectors.get(key, ""),
                            "faction": game.faction_short.get(owner, ""),
                            "faction_full": game.faction_name.get(owner, "")})

    wrecks = {r["nickname"]: r
              for r in wr.group_by_system(game.wrecks, visits, game.system_label)}

    # Bases and wrecks are two counts of the same place, so a system is one row
    # carrying both. They used to be two lists with two different shapes, one
    # of which had lost the system nickname, which is why the wreck rows had to
    # re-derive their house from a field the base rows did not have.
    out = []
    for nick in set(bases) | set(wrecks):
        found = bases.get(nick, {"docked": [], "revealed": [], "unknown": []})
        for bucket in found.values():
            bucket.sort(key=lambda base: base["name"])
        found.update(_tally(len(found["docked"]),
                            sum(len(v) for v in found.values())))
        hulls = wrecks.get(nick, {"found": [], "missing": [], "stripped": 0,
                                  "total": 0, "scenery": 0})
        hulls = dict(found=hulls["found"], missing=hulls["missing"],
                     # How many of them can never hold anything. The page says
                     # it once per system, because an empty hull and an
                     # unopened loaded one look the same in a list.
                     scenery=hulls.get("scenery", 0),
                     **_tally(hulls["stripped"], hulls["total"]))
        out.append({
            "nickname": nick,
            "system": game.system_label(nick),
            "house": house_of(nick),
            "bases": found,
            "wrecks": hulls,
            # One flag for the whole place, because that is what the page hides
            # on: a system is finished when every base is docked at and every
            # wreck is stripped.
            "done": found["done"] == found["total"]
                    and hulls["done"] == hulls["total"],
        })
    out.sort(key=lambda r: r["system"])

    return {
        "systems": out,
        "house_order": HOUSE_ORDER,
        "save": os.path.basename(save_path),
        # The whole path as well as the name. Which file is being followed is
        # a question the header asks and only this process can answer: the
        # save sits six levels down a Wine prefix nobody reconstructs from
        # memory, and the browser has no way to find out on its own.
        "save_path": save_path,
        "save_dir": os.path.dirname(save_path),
        "saved_at": os.path.getmtime(save_path),
        "docked": sum(r["bases"]["done"] for r in out),
        "revealed": sum(len(r["bases"]["revealed"]) for r in out),
        "bases_total": sum(r["bases"]["total"] for r in out),
        # Only an emptied wreck counts, the same way only a base you docked at
        # counts. The game records the loot being taken as bit 8.
        "stripped": sum(r["wrecks"]["done"] for r in out),
        "wrecks_total": sum(r["wrecks"]["total"] for r in out),
        "systems_done": sum(1 for r in out if r["done"]),
        "systems_total": len(out),
        # The Trade tab needs to know where you have actually been, and this
        # is the only place the save has already been read for exactly that.
        "docked_bases": sorted(k for k, v in game.bases.items()
                               if flags.get(k) in fl.DOCKED),
    }


# --- showing somebody a folder -------------------------------------------

def open_folder(path):
    """Ask the desktop to show a folder, and do not wait to find out.

    Three spellings of one action, kept in one place because a second copy is
    how a project ends up opening folders two different ways: `xdg-open` on
    Linux, `os.startfile` on Windows, `open` on macOS.

    **Spawned and never waited for.** `xdg-open` returns at once on this
    desktop, but a handler that is misconfigured can sit there, and this is
    called from a POST, so waiting would hang the panel rather than the
    folder. The answer therefore means "asked", not "a window appeared", and
    the page prints the path it asked for so that a silent no-op is still
    readable. The finished `xdg-open` is left as a zombie until the next call,
    which `subprocess` reaps on its next `Popen`, so at most one is ever
    outstanding and there is no reaper worth writing here.
    """
    if not os.path.isdir(path):
        raise FileNotFoundError(f"{path} is not a folder")
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - a directory, and one we chose
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, path], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    return path


# --- the reader's own marks ----------------------------------------------
#
# Which log entries are starred and which are read. One person's marks on their
# own machine, which is why they never leave it.
#
# **They used to live in `localStorage` and that lost them.** The reasoning was
# right about who owns the marks and wrong about where the machine keeps them:
# `localStorage` is scoped to a *browsing context*, so a container tab, a second
# profile and a second browser each get their own copy of it, invisible to the
# others. On 2026-09-08 the marks were made in a Zen workspace, which is a
# container; `run.sh` ends in `xdg-open`, which always opens a plain tab; and
# the next day's tab could not see any of them. Nothing was corrupted and no key
# had changed. Two stores existed and the page was reading the empty one.
#
# The server is just as local as the browser and is the same for every tab, so
# this is where they live now.

MARKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "marks.json")
# `fav` is the Equipment tab's own: a starred gun ignores every filter and
# stays in the list. Its own kind rather than a share of `star`, because a
# starred news item and a favourite gun are different things and the vault's
# first rule is one spelling per meaning. The key is the item nickname, which
# is unique across guns and shields, so it needs no prefix and carries none.
KINDS = ("star", "read", "fav")
_marks_lock = threading.Lock()


def _blank_marks():
    return {kind: {} for kind in KINDS}


def load_marks(path=MARKS):
    """Every mark on disk. A missing file is no marks, never an error."""
    with _marks_lock:
        return _read_marks(path)


def _read_marks(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            held = json.load(fh)
    except (OSError, ValueError):
        # Unreadable reads the same as absent, on purpose. A corrupt file
        # should cost the marks, not the whole Neural Net tab.
        return _blank_marks()
    out = _blank_marks()
    for kind in KINDS:
        got = held.get(kind)
        if isinstance(got, dict):
            out[kind] = {str(k): True for k, v in got.items() if v}
    return out


def _write_marks(marks, path):
    """Replace the file in one step, so a crash cannot truncate it.

    `tempfile` in the same directory rather than anywhere else: `os.replace` is
    only atomic within a filesystem, and `/tmp` is not guaranteed to be on this
    one.
    """
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=folder, prefix=".marks-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            json.dump(marks, fh, ensure_ascii=False, sort_keys=True)
        os.replace(temp, path)
    except BaseException:
        # Leaving a stray temp file beside the real one would be read as a
        # second, older set of marks by anyone looking in the folder.
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    return marks


def set_mark(kind, key, on, path=MARKS):
    """Turn one mark on or off, and hand back everything."""
    if kind not in KINDS:
        raise ValueError(f"no such mark as {kind!r}")
    key = str(key)
    with _marks_lock:
        marks = _read_marks(path)
        if on:
            marks[kind][key] = True
        else:
            marks[kind].pop(key, None)
        return _write_marks(marks, path)


def merge_marks(sent, path=MARKS):
    """Fold a browser's own marks in, and hand back everything.

    A union rather than a replacement, because the marks that went missing are
    spread across more than one browsing context and each of them is entitled to
    contribute. Nothing here can delete a mark: that is what makes it safe to
    run on first sight of a store nobody has seen before.
    """
    with _marks_lock:
        marks = _read_marks(path)
        for kind in KINDS:
            got = (sent or {}).get(kind)
            if not isinstance(got, dict):
                continue
            for key, value in got.items():
                if value:
                    marks[kind][str(key)] = True
        return _write_marks(marks, path)


class Ctx:
    """What a view's endpoint is handed: the data, the save, the query."""

    def __init__(self, game, save, lock, query=None):
        self.game, self.save, self.lock = game, save, lock
        self.query = query or {}
        self._saved = self._state = self._order = None

    def one(self, key, default=None):
        return (self.query.get(key) or [default])[0]

    def saved(self):
        """The decoded save text, read once per request and under the lock.

        Every save read in a request goes through here. A view that reads the
        file itself gets a second copy taken at a different moment, so the
        hold can come from one save and the visit flags from the next one the
        game writes, and pays the decode twice for the privilege.
        """
        if self._saved is None:
            with self.lock:
                self._saved = fl.decode_save(self.save)
        return self._saved

    def state(self):
        if self._state is None:
            self._state = read_state(self.game, self.save, self.saved())
        return self._state

    def docked(self):
        return set(self.state()["docked_bases"])

    def visits(self):
        """The raw `visit` table, hash -> flag, off the one decode.

        `state()` resolves these against the base list and throws the rest away,
        which is right for it and wrong for anything asking about a different
        kind of object: jump gates and holes are recorded here too and no base
        ever matches their hashes.
        """
        return fl.parse_visits(self.saved())

    def dock_order(self):
        """Which base you reached first, second, third. See `dock_order`."""
        if self._order is None:
            self._order = dock_order(self.saved(), self.game)
        return self._order
