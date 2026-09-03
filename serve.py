#!/usr/bin/env python3
"""Live web view of Freelancer base visits.

    serve.py [save.fl] [--game DIR] [--port N]

Serves a page that re-reads the save every few seconds, so it keeps up while
you play. With no save argument it follows AutoSave.fl.

This file wraps flvisits.py and never modifies it: that module is frozen, see
CLAUDE.md in this folder. The bucket logic below is therefore a deliberate
duplicate of the one inside `flvisits.main()`, which is not importable on its
own. If the two ever disagree, flvisits.py is the authority.
"""

import argparse
import glob
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docking as dk  # noqa: E402
import drawdist as dd  # noqa: E402
import flvisits as fl  # noqa: E402
import navmap  # noqa: E402
import netlog as nl  # noqa: E402
import persist as pe  # noqa: E402
import reputation as rep  # noqa: E402
import speed as sp  # noqa: E402
import thrusters as th  # noqa: E402
import tradelane as tl  # noqa: E402
import weapons as wp  # noqa: E402
import wrecks as wr  # noqa: E402

# Offered on the Speed tab. 300 is roughly vanilla, 1000 is what constants.ini
# carries, and the top of the range is where ANOM_LIMITS_MAX_VELOCITY sits, so
# 10000 may clamp: that cap is a separate constant this does not touch.
SPEED_CHOICES = [300, 500, 750, 1000, 1500, 2000, 2500, 5000]

# Trade lane speed. 2500 is vanilla and 10000 is flhack's own ceiling, which
# this keeps rather than inventing a different one.
TRADELANE_CHOICES = [2500, 5000, 7500, 10000]

# Asteroid draw distance, as a multiple of each field's own vanilla value.
# Geometry grows with the cube of the radius, so 2x is roughly 8x the rocks.
DRAWDIST_CHOICES = [1, 1.25, 1.5, 2]

REVEALED = 1  # story put it on the nav map; the player has never docked there

# The house is the first two characters of a system's nickname. The four houses
# and the three frontier groups cover 46 of the 47 systems that carry a dockable
# base; the 47th is Omicron Minor, whose `st` prefix marks the story systems and
# which the fallback below puts in Edge Worlds. That is the fallback earning its
# keep rather than a gap: the prefix list was written from the systems that had
# bases at the time, and one more turned up the moment it was checked.
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


SAVE_TAIL = os.path.join(
    "drive_c", "users", "*", "Documents", "My Games",
    "Freelancer", "Accts", "SinglePlayer", "AutoSave.fl",
)


def find_default_save(game_dir):
    """Newest AutoSave.fl across every Wine prefix that sits beside the game.

    The prefix holding the game files is not necessarily the prefix the game
    runs in. On this machine the install lives in an abandoned Proton prefix
    while play happens in a separate win32 one, so searching only the install's
    own prefix finds nothing. Searching the siblings and taking the freshest
    file is both simpler and right in either layout.
    """
    prefix = game_dir
    for _ in range(6):  # climb out of drive_c/Program Files/... to the prefix
        if os.path.isdir(os.path.join(prefix, "drive_c", "users")):
            break
        parent = os.path.dirname(prefix)
        if parent == prefix:
            break
        prefix = parent

    candidates = glob.glob(os.path.join(prefix, SAVE_TAIL))
    candidates += glob.glob(os.path.join(os.path.dirname(prefix), "*", SAVE_TAIL))
    if not candidates:
        return None
    return max(set(candidates), key=os.path.getmtime)


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
        dockable = dk.dockable_bases(game_dir, data_dir, fl.system_files, fl.ipath)
        self.bases = {k: v for k, v in bases.items() if k in dockable}

        self.names = fl.load_names(game_dir)
        self.system_ids = {nick.lower(): ids for nick, ids in systems.items()}
        self.by_hash = {fl.fl_hash(nick): nick for nick in self.objects}
        self.wrecks = wr.load_wrecks(game_dir)
        # Where each base sits on the nav map, from the same walk that decided
        # which bases are dockable at all.
        self.sectors = dk.base_sectors(
            data_dir, fl.system_files,
            navmap.load_scales(data_dir, fl.read_ini, fl.ipath))
        # Static: no save and no running game needed, so the DPS tab works with
        # Freelancer closed.
        self.weapons = wp.load_weapons(game_dir)
        # The empathy table never changes; only the player's own
        # standings come from the save, and those are read per request.
        self.repmodel = rep.load_model(game_dir)

    def label(self, ids, fallback):
        try:
            return self.names.get(int(ids), fallback)
        except (TypeError, ValueError):
            return fallback

    def system_label(self, system):
        return self.label(self.system_ids.get(system, 0), system)


def _visit_rank(row):
    """Order the Visits tab by how much work a system still needs.

    Three tiers, because "zero" means two opposite things here. A system with
    nothing left is finished and a system with nothing docked has not been
    started, and sorting on the remaining count alone would put the finished
    ones first and bury the nearly-finished ones behind every untouched system.

    So: in progress first, most bases left at the top, then the finished ones,
    then the never-opened ones, the last two alphabetically.

    The tier number is load-bearing and not decoration. A never-opened system
    has the largest remaining count there is, so on the remaining count alone
    it would head the list; the tier is the only thing holding it at the bottom.
    """
    docked = len(row["docked"])
    if docked == 0:
        return (2, 0, row["system"])
    if row["remaining"] == 0:
        return (1, 0, row["system"])
    return (0, -row["remaining"], row["system"])


def read_state(game, save_path):
    """Split every base into docked / revealed / unknown, grouped by system."""
    # Decoded once and used twice: the visit flags and the Neural Net log come
    # out of the same save text, and decoding is the expensive half.
    saved = fl.decode_save(save_path)
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

    systems = {}
    for key, (system, ids) in game.bases.items():
        row = systems.setdefault(
            system,
            {"system": game.label(game.system_ids.get(system, 0), system),
             "house": house_of(system),
             "docked": [], "revealed": [], "unknown": []},
        )
        flag = flags.get(key)
        bucket = "docked" if flag in fl.DOCKED else "revealed" if flag == REVEALED else "unknown"
        row[bucket].append({"name": game.label(ids, key),
                            "at": game.sectors.get(key, "")})

    out = []
    for row in systems.values():
        for bucket in ("docked", "revealed", "unknown"):
            row[bucket].sort(key=lambda base: base["name"])
        row["total"] = len(row["docked"]) + len(row["revealed"]) + len(row["unknown"])
        row["remaining"] = row["total"] - len(row["docked"])
        row["percent"] = round(100 * len(row["docked"]) / row["total"]) if row["total"] else 0
        out.append(row)
    out.sort(key=_visit_rank)

    wreck_rows = wr.group_by_system(game.wrecks, visits, game.system_label)
    for row in wreck_rows:
        row["house"] = house_of(row["nickname"])

    return {
        "systems": out,
        "wrecks": wreck_rows,
        "log": nl.entries(saved, game.names),
        "house_order": HOUSE_ORDER,
        # Only emptied wrecks count, mirroring "docked" on the Visits tab. The
        # game records the loot being taken as bit 8 of the visit flag.
        "wrecks_stripped": sum(r["stripped"] for r in wreck_rows),
        "wrecks_open": sum(r["found_open"] for r in wreck_rows),
        "wrecks_total": len(game.wrecks),
        "wrecks_systems": sum(1 for r in wreck_rows if r["stripped"]),
        "wrecks_systems_total": len(wreck_rows),
        "save": os.path.basename(save_path),
        "saved_at": os.path.getmtime(save_path),
        "docked": sum(len(r["docked"]) for r in out),
        "revealed": sum(len(r["revealed"]) for r in out),
        "bases": sum(r["total"] for r in out),
        "systems_touched": sum(1 for r in out if r["docked"]),
        "systems_total": len(out),
    }


PAGE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Freelancer visits</title>
<style>
  :root {
    --bg: #0d1117; --card: #161b22; --line: #30363d;
    --text: #e6edf3; --dim: #8b949e;
    --docked: #3fb950; --revealed: #d29922; --unknown: #6e7681;
  }
  * { box-sizing: border-box; }
  /* The page hides things with the `hidden` property, and a class selector
     carrying `display: flex` outranks the browser's own `[hidden]` rule. The
     Speed tab set `hidden` on the totals row and the Show All bar and both
     stayed on screen because of exactly that. Make the property mean what it
     says rather than adding a second mechanism beside it. */
  [hidden] { display: none !important; }
  body { margin: 0; padding: 2rem 1.5rem 4rem; background: var(--bg); color: var(--text);
         font: 15px/1.5 ui-sans-serif, system-ui, sans-serif; }
  .wrap { max-width: 60rem; margin: 0 auto; }
  h1 { font-size: 1.4rem; margin: 0 0 .25rem; font-weight: 600; }
  .sub { color: var(--dim); font-size: .85rem; margin-bottom: 1.5rem; }
  .totals { display: flex; gap: 2rem; flex-wrap: wrap; padding: 1rem 1.25rem; margin-bottom: 1.5rem;
            background: var(--card); border: 1px solid var(--line); border-radius: 10px; }
  .totals div span { display: block; }
  .n { font-size: 1.6rem; font-weight: 650; line-height: 1.1; }
  .lbl { color: var(--dim); font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; }
  label.toggle { display: inline-flex; align-items: center; gap: .5rem; cursor: pointer;
                 color: var(--dim); font-size: .85rem; margin-bottom: 1.25rem; }
  .controls { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
              margin-bottom: 1.25rem; }
  .controls label.toggle { margin-bottom: 0; }
  .groupacts { display: flex; gap: .4rem; margin-left: auto; }
  .groupacts button { background: var(--card); color: var(--dim); cursor: pointer;
                      border: 1px solid var(--line); border-radius: 6px;
                      font: inherit; font-size: .78rem; padding: .25rem .6rem; }
  .groupacts button:hover { color: var(--text); border-color: var(--docked); }
  /* DPS tab. One grid for the head, the rows and the total, so the columns
     line up without every cell carrying a hardcoded width. */
  .guns { overflow-x: auto; }
  .guntable { min-width: 46rem; }
  .reptable { min-width: 42rem; }
  .reptable .gun, .reptable .gunhead {
    grid-template-columns: minmax(14rem, 1fr) 5rem 4rem 14rem; }
  .reprow { cursor: pointer; }
  .reprow .others { text-align: left; color: var(--dim); font-size: .82rem;
                    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .reprow:hover { border-color: var(--docked); }
  .repwhy { margin: -.2rem 0 .5rem 1rem; padding-left: .9rem;
            border-left: 2px solid var(--line); }
  .repline { display: grid; gap: .5rem; padding: .15rem 0; font-size: .85rem;
             grid-template-columns: minmax(12rem, 1fr) 4.5rem 4.5rem 4.5rem; }
  .repline .nm { color: var(--dim); }
  .repline span:not(.nm) { text-align: right; }
  .rephead { color: var(--dim); font-size: .7rem; text-transform: uppercase;
             letter-spacing: .05em; padding-bottom: .1rem; }
  .rephead .nm { text-align: left; }
  .gunhead .othershead { text-align: left; }
  .reppick { display: flex; gap: .6rem; flex-wrap: wrap; margin-bottom: 1rem; }
  .reppick select { background: var(--card); color: var(--text); font: inherit;
                    border: 1px solid var(--line); border-radius: 8px;
                    padding: .45rem .7rem; }
  .reppick select:focus { outline: none; border-color: var(--docked); }
  .gun, .gunhead {
    display: grid; align-items: baseline; gap: .5rem;
    grid-template-columns: minmax(9rem, 1fr) repeat(2, 4.2rem) repeat(2, 5rem)
                           4.2rem 4.2rem 1.4rem;
  }
  .gun { padding: .55rem .9rem; background: var(--card); border: 1px solid var(--line);
         border-radius: 8px; margin-bottom: .4rem; }
  .gun .nm { min-width: 0; overflow: hidden; text-overflow: ellipsis;
             white-space: nowrap; }
  .gun .num { text-align: right; font-variant-numeric: tabular-nums; }
  .gun .num.h { color: var(--docked); }
  .gun .num.s { color: var(--revealed); }
  .gun .num.raw { color: var(--dim); font-size: .85rem; }
  .gun .kill { background: none; border: none; color: var(--dim); cursor: pointer;
               font: inherit; padding: 0; text-align: right; }
  .gun .kill:hover { color: #f85149; }
  .gun.sum { background: none; border-color: transparent;
             border-top: 1px solid var(--line); border-radius: 0; margin-top: .4rem;
             font-weight: 650; }
  .gunhead { padding: 0 .9rem .35rem; color: var(--dim); font-size: .7rem;
             text-transform: uppercase; letter-spacing: .05em; }
  .gunhead span { text-align: right; }
  .gunhead .nm { text-align: left; }
  .gunhead .grp { color: var(--text); opacity: .55; }
  #gunsearch { width: 100%; padding: .5rem .75rem; background: var(--card);
               color: var(--text); border: 1px solid var(--line); border-radius: 8px;
               font: inherit; }
  #gunsearch:focus { outline: none; border-color: var(--docked); }
  .hits { margin: .4rem 0 0; max-height: 17rem; overflow-y: auto; }
  .hit { display: flex; gap: .75rem; align-items: baseline; width: 100%; text-align: left;
         background: none; border: none; color: var(--text); font: inherit;
         cursor: pointer; padding: .35rem .9rem; border-radius: 6px; }
  .hit:hover { background: var(--card); }
  .hit .num { flex: none; width: 5rem; text-align: right; color: var(--dim);
              font-variant-numeric: tabular-nums; }
  .addgun { background: var(--card); color: var(--text); cursor: pointer;
            border: 1px dashed var(--line); border-radius: 8px; font: inherit;
            padding: .5rem 1rem; }
  .addgun:hover { border-color: var(--docked); color: var(--docked); }
  .addgun:disabled { opacity: .4; cursor: default; border-style: solid; }
  /* Neural Net tab */
  .logbar { display: flex; align-items: center; gap: .6rem; margin-bottom: 1rem; }
  .logbar button { background: var(--card); color: var(--text); cursor: pointer;
                   border: 1px solid var(--line); border-radius: 8px; font: inherit;
                   font-size: .85rem; padding: .35rem .8rem; }
  .logbar button:hover { border-color: var(--docked); }
  .logbar button.on { color: var(--docked); border-color: var(--docked); }
  .logbar .count { color: var(--dim); font-size: .85rem; margin-left: auto; }
  .entry { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
           padding: .85rem 1.1rem; margin-bottom: .5rem; }
  .entry.read { opacity: .5; }
  .entry.star { border-left: 3px solid var(--revealed); }
  .entry .body { white-space: pre-wrap; overflow-wrap: anywhere; }
  .entry .subs { margin: .5rem 0 0; padding-left: 1rem; color: var(--dim);
                 font-size: .85rem; }
  .entry .acts { display: flex; gap: .4rem; margin-top: .6rem; }
  .entry .acts button { background: none; border: 1px solid var(--line);
                        border-radius: 6px; color: var(--dim); cursor: pointer;
                        font: inherit; font-size: .75rem; padding: .15rem .6rem; }
  .entry .acts button:hover { color: var(--text); }
  .entry .acts button.on { color: var(--revealed); border-color: var(--revealed); }
  .entry .acts button.on.done { color: var(--docked); border-color: var(--docked); }
  h2.house[data-house] { cursor: pointer; user-select: none; }
  h2.house[data-house]:hover { color: var(--text); }
  .caret { flex: none; width: .8rem; font-size: .7rem; }
  h2.house { display: flex; align-items: baseline; gap: .75rem; font-size: .8rem;
             font-weight: 600; text-transform: uppercase; letter-spacing: .08em;
             color: var(--dim); margin: 1.75rem 0 .6rem; padding-bottom: .4rem;
             border-bottom: 1px solid var(--line); }
  h2.house:first-child { margin-top: 0; }
  .hcount { margin-left: auto; letter-spacing: 0; text-transform: none;
            font-variant-numeric: tabular-nums; font-weight: 500; }
  .sys { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
         padding: 1rem 1.25rem; margin-bottom: .75rem; }
  .head { display: flex; align-items: baseline; gap: .75rem; }
  .head b { font-size: 1.05rem; font-weight: 600; }
  .count { color: var(--dim); font-size: .85rem; margin-left: auto; font-variant-numeric: tabular-nums; }
  .bar { height: 5px; border-radius: 3px; background: #21262d; margin: .6rem 0 .8rem; overflow: hidden; }
  .bar i { display: block; height: 100%; background: var(--docked); }
  .row { display: flex; gap: .6rem; margin: .35rem 0; font-size: .9rem; align-items: baseline; }
  .tag { flex: none; width: 6.5rem; font-size: .75rem; text-transform: uppercase;
         letter-spacing: .05em; padding-top: .1rem; }
  .tag.d { color: var(--docked); } .tag.r { color: var(--revealed); } .tag.u { color: var(--unknown); }
  .row.u span { color: var(--dim); }
  .empty { color: var(--dim); font-style: italic; }
  .tabs { display: flex; gap: .25rem; margin-bottom: 1.25rem;
          border-bottom: 1px solid var(--line); }
  .tab { background: none; border: none; border-bottom: 2px solid transparent;
         color: var(--dim); font: inherit; font-size: .95rem; padding: .5rem .9rem;
         cursor: pointer; margin-bottom: -1px; }
  .tab:hover { color: var(--text); }
  .tab.on { color: var(--text); border-bottom-color: var(--docked); }
  .wreck { display: flex; gap: .6rem; margin: .3rem 0; font-size: .9rem; align-items: baseline; }
  .wreck .mark { flex: none; width: 1rem; text-align: center; }
  .wreck.f .mark { color: var(--docked); }
  .wreck.o .mark { color: var(--revealed); }
  .wreck.o .nm { color: var(--revealed); }
  .wreck.m .mark { color: var(--unknown); }
  .wreck.m .nm { color: var(--dim); }
  .wreck .nm { flex: none; min-width: 12rem; }
  .loot { color: var(--dim); font-size: .82rem; }
  .atlist { display: flex; flex-direction: column; gap: .15rem; }
  .atrow { display: flex; gap: .5rem; align-items: baseline; }
  .cell { flex: none; width: 3.4rem; color: var(--dim);
          font-variant-numeric: tabular-nums; }
  .speeds { display: flex; flex-wrap: wrap; gap: .5rem; margin: .25rem 0 1rem; }
  .speeds button { background: var(--card); color: var(--text); cursor: pointer;
                   border: 1px solid var(--line); border-radius: 8px;
                   font: inherit; font-variant-numeric: tabular-nums;
                   padding: .55rem 1.1rem; min-width: 5.5rem; }
  .speeds button:hover:not(:disabled) { border-color: var(--docked); }
  .speeds button.on { border-color: var(--docked); color: var(--docked); font-weight: 650; }
  .speeds button:disabled { opacity: .4; cursor: default; }
  .note { color: var(--dim); font-size: .85rem; margin: 0 0 1rem; }
  .note.warn { color: var(--revealed); }
</style>
<div class="wrap">
  <h1>Freelancer</h1>
  <div class="sub" id="sub">loading…</div>
  <nav class="tabs">
    <button class="tab on" data-tab="visits">Visits</button>
    <button class="tab" data-tab="wrecks">Wrecks</button>
    <button class="tab" data-tab="speed">Speed</button>
    <button class="tab" data-tab="dps">DPS</button>
    <button class="tab" data-tab="log">Neural Net</button>
    <button class="tab" data-tab="rep">Reputation</button>
  </nav>
  <div class="totals" id="totals"></div>
  <div class="controls" id="togglewrap">
    <label class="toggle">
      <input type="checkbox" id="ext" checked> <span id="extlabel"></span>
    </label>
    <label class="toggle">
      <input type="checkbox" id="hidedone" checked> <span id="hidelabel"></span>
    </label>
    <span class="groupacts">
      <button id="collapseall">Collapse all</button>
      <button id="expandall">Expand all</button>
    </span>
  </div>
  <div id="list"></div>
</div>
<script>
const $ = s => document.querySelector(s);
// One checkbox, but its state belongs to the tab, not to the page: what you
// want expanded on Visits has nothing to do with what you want on Wrecks.
const extended = { visits: true, wrecks: true };
// Per tab, same as the checkbox above it: what counts as finished differs
// between the two, so remembering one answer for both would be wrong.
const hideDone = { visits: true, wrecks: true };
// Which house headings are folded, per tab, same reasoning as the checkbox.
const collapsed = { visits: {}, wrecks: {} };
// Everything starts folded, but only once per tab. Doing it on every render
// would re-fold a house the moment the five-second poll came back, and the
// page would fight whoever opened it.
const folded = { visits: false, wrecks: false };

function foldOnFirstSight(d) {
  if (folded[tab] || !d || !d.house_order) return;
  folded[tab] = true;
  d.house_order.forEach(h => { collapsed[tab][h] = true; });
}
let latest = null, speed = null, thrusters = null, lane = null,
    draw = null, tab = 'visits';

// DPS tab. `catalogue` is the game's own data, fetched once because it cannot
// change while the page is open; `loadout` is the player's pick, held as
// nicknames so it survives a reload and stays valid if the numbers are ever
// recomputed. localStorage is the right home for it: it is one person's
// scratch selection on their own machine, not something the server should own.
let catalogue = null, gunQuery = null;
let loadout = [];
try {
  loadout = JSON.parse(localStorage.getItem('fl.loadout') || '[]');
} catch (e) { loadout = []; }

function saveLoadout() {
  try { localStorage.setItem('fl.loadout', JSON.stringify(loadout)); } catch (e) {}
}

// Neural Net marks. Keyed by netlog.py's stable key, which counts an entry's
// duplicates up from the oldest end precisely so these do not slide onto the
// wrong line when the game writes a new entry at the top. Newest first is the
// default because that is the end the game appends to.
let logNewestFirst = true, logPersonalOnly = true;

// Reputation tab. `repData` is whatever the server last worked out; `repOpen`
// is which action rows have their collateral expanded, by index, because the
// damage a plan does is the half people skip and it has to be one click away.
let repData = null, repTarget = '', repGoal = 'neutral';
const repOpen = {};

// The write-to-files button on the Speed tab. Not remembered anywhere: it
// reports the last press and nothing more.
let persistBusy = false, persistOk = false, persistMsg = null;
let marks = { star: {}, read: {} };
try {
  const held = JSON.parse(localStorage.getItem('fl.netlog') || '{}');
  marks = { star: held.star || {}, read: held.read || {} };
} catch (e) {}

function saveMarks() {
  try { localStorage.setItem('fl.netlog', JSON.stringify(marks)); } catch (e) {}
}

// Delegated, because render() replaces the list wholesale on every poll and a
// handler bound to a heading would not survive it.
$('#list').addEventListener('click', e => {
  const head = e.target.closest('h2.house[data-house]');
  if (!head) return;
  const state = collapsed[tab] || (collapsed[tab] = {});
  const key = head.dataset.house;
  state[key] = !state[key];
  render();
});

function foldAll(shut) {
  const d = latest;
  if (!d) return;
  folded[tab] = true;  // the owner has decided; stop opening on our own
  collapsed[tab] = {};
  if (shut) (d.house_order || []).forEach(h => { collapsed[tab][h] = true; });
  render();
}
$('#collapseall').addEventListener('click', () => foldAll(true));
$('#expandall').addEventListener('click', () => foldAll(false));

$('#ext').addEventListener('change', e => { extended[tab] = e.target.checked; render(); });
$('#hidedone').addEventListener('change', e => { hideDone[tab] = e.target.checked; render(); });
document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => {
  tab = b.dataset.tab;
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x === b));
  $('#ext').checked = !!extended[tab];
  $('#hidedone').checked = !!hideDone[tab];
  // Leaving the DPS tab closes the picker, so coming back shows the loadout
  // rather than a half-typed search from last time.
  if (tab !== 'dps') gunQuery = null;
  render();
  // The live tab is only polled while it is open, so opening it has to ask.
  if (tab === 'speed') poll();
  if (tab === 'dps') loadCatalogue();
  if (tab === 'rep' && !repData) loadRep();
}));

function esc(s) { return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function line(cls, tag, items, withAt) {
  if (!items.length) return '';
  // Only the unknown bucket gets coordinates, one base per line. Docked and
  // revealed stay comma-separated runs: docked you have flown to already, and
  // revealed the story has put on your nav map, so both are findable without
  // a cell reference and the extra column would only make the card taller.
  const body = withAt
    ? '<span class="atlist">' + items.map(b =>
        `<span class="atrow"><span class="cell">${esc(b.at)}</span>` +
        `<span>${esc(b.name)}</span></span>`).join('') + '</span>'
    : `<span>${items.map(b => esc(b.name)).join(', ')}</span>`;
  return `<div class="row ${cls}"><span class="tag ${cls}">${tag} ${items.length}</span>` +
         body + '</div>';
}

function totals(pairs) {
  $('#totals').innerHTML = pairs
    .map(([n, l]) => `<div><span class="n">${n}</span><span class="lbl">${l}</span></div>`).join('');
}

function card(title, done, total, percent, body) {
  return `<div class="sys">
    <div class="head"><b>${esc(title)}</b><span class="count">${done} / ${total}</span></div>
    <div class="bar"><i style="width:${percent}%"></i></div>${body}</div>`;
}

// Rows arrive already in the order the server chose; grouping must not disturb
// it, so each house keeps its rows in the order they came in. A house with
// nothing to show under the current checkbox is dropped rather than left as an
// empty heading.
function byHouse(d, rows, renderRow, tally) {
  const bucket = {};
  rows.forEach(r => (bucket[r.house] = bucket[r.house] || []).push(r));
  const shutState = collapsed[tab] || {};
  return (d.house_order || []).filter(h => bucket[h]).map(h => {
    const rs = bucket[h];
    const [done, total] = tally(rs);
    const shut = !!shutState[h];
    // Only a grouped heading carries data-house; the Speed tab reuses the same
    // look for Cruise and Thrusters and must stay unfoldable.
    return `<h2 class="house" data-house="${esc(h)}">` +
           `<span class="caret">${shut ? '▸' : '▾'}</span>${esc(h)}` +
           `<span class="hcount">${done} / ${total}</span></h2>` +
           `<div class="housebody"${shut ? ' hidden' : ''}>` +
           rs.map(renderRow).join('') + `</div>`;
  }).join('');
}

function renderVisits(d) {
  const ext = extended.visits;
  totals([[d.docked, 'docked'], [d.revealed, 'revealed'],
          [d.bases - d.docked - d.revealed, 'unknown'],
          [`${d.systems_touched}/${d.systems_total}`, 'systems']]);
  // "Finished" is whatever the card's own counter calls done, so the toggle
  // agrees with the number the reader is looking at rather than inventing a
  // second definition beside it.
  const rows = d.systems.filter(s => (ext || s.docked.length || s.revealed.length)
                                  && !(hideDone.visits && s.percent === 100));
  if (!rows.length) return '<p class="empty">' + (hideDone.visits
    ? 'Every system with anything in it is finished.'
    : 'Nothing docked at yet.') + '</p>';
  return byHouse(d, rows,
    s => card(s.system, s.docked.length, s.total, s.percent,
      line('d', 'docked', s.docked) + line('r', 'revealed', s.revealed) +
      (ext ? line('u', 'unknown', s.unknown, true) : '')),
    rs => [rs.reduce((n, s) => n + s.docked.length, 0),
           rs.reduce((n, s) => n + s.total, 0)]);
}

function wreckLine(w, found) {
  // Three states, not two: a wreck you found but never opened still holds its
  // loot, and the game says so in bit 8 of the visit flag.
  const cls = !found ? 'm' : w.emptied ? 'f' : 'o';
  const mark = !found ? '-' : w.emptied ? '+' : '*';
  // The loot of an untouched wreck is what you would actually collect, so it
  // stays on screen without the checkbox; for an emptied one it is history.
  const showLoot = w.loot.length && (extended.wrecks || (found && !w.emptied));
  const loot = showLoot
    ? `<span class="loot">${w.loot.map(([i, n]) => `${n}x ${esc(i)}`).join(', ')}</span>` : '';
  const where = [w.sector, w.spot].filter(Boolean).join(' ');
  return `<div class="wreck ${cls}"><span class="mark">${mark}</span>` +
         `<span class="cell">${esc(where)}</span>` +
         `<span class="nm">${esc(w.name)}</span>${loot}</div>`;
}

function renderWrecks(d) {
  totals([[d.wrecks_stripped, 'stripped'], [d.wrecks_open, 'still loaded'],
          [d.wrecks_total - d.wrecks_stripped - d.wrecks_open, 'left'],
          [`${d.wrecks_systems}/${d.wrecks_systems_total}`, 'systems']]);
  const ext = extended.wrecks;
  const rows = d.wrecks.filter(s => (ext || s.found.length)
                                 && !(hideDone.wrecks && s.percent === 100));
  if (!rows.length)
    return '<p class="empty">' + (hideDone.wrecks
      ? 'Every system with a wreck in it is stripped.'
      : 'No wrecks found yet. Tick the box to see where they are.') + '</p>';
  return byHouse(d, rows,
    s => card(s.system, s.stripped, s.total, s.percent,
      s.found.map(w => wreckLine(w, true)).join('') +
      (ext ? s.missing.map(w => wreckLine(w, false)).join('') : '')),
    rs => [rs.reduce((n, s) => n + s.stripped, 0),
           rs.reduce((n, s) => n + s.total, 0)]);
}

function renderSpeed() {
  const s = speed;
  if (!s) return '<p class="empty">Reading the game…</p>';
  // No game running is the ordinary case, not a failure: the page is usually
  // open before Freelancer is.
  const head = `<h2 class="house">Cruise</h2>` + (s.error
    ? `<p class="note warn">${esc(s.error)}</p>`
    : `<p class="note">Cruise speed is <b>${s.value}</b>. A change applies to the
       next cruise burn, no reload. It lasts until the game is closed; the file
       still says what it said.</p>`);
  const msg = s.message ? `<p class="note">${esc(s.message)}</p>` : '';
  const buttons = s.choices.map(v =>
    `<button data-speed="${v}" ${s.error ? 'disabled' : ''}` +
    `${!s.error && Math.abs(s.value - v) < 0.5 ? ' class="on"' : ''}>${v}</button>`
  ).join('');
  return head + msg + `<div class="speeds">${buttons}</div>` +
    `<p class="note">A separate constant, ANOM_LIMITS_MAX_VELOCITY in
     <code>constants.ini</code>, caps velocity at 10000 and is not touched
     here. Nothing offered above reaches it.</p>`;
}

function renderTradeLane() {
  const t = lane;
  if (!t) return '';
  const head = '<h2 class="house">Trade lanes</h2>' + (t.error
    ? `<p class="note warn">${esc(t.error)}</p>`
    : `<p class="note">Lane speed is <b>${t.value}</b>, vanilla is
       ${t.vanilla}. Not in any data file: it is a constant inside
       <code>common.dll</code>, so this is memory only and lasts until the game
       closes.</p>`);
  const msg = t.message ? `<p class="note">${esc(t.message)}</p>` : '';
  const buttons = t.choices.map(v =>
    `<button data-lane="${v}" ${t.error ? 'disabled' : ''}` +
    `${!t.error && Math.abs(t.value - v) < 0.5 ? ' class="on"' : ''}>${v}</button>`
  ).join('');
  const extras = t.error ? '' :
    `<p class="note">Picking a speed also sets the wind-up to near-instant,
     since at the stock rate a ship spends most of a short lane still
     accelerating and the higher number is barely felt. Deceleration is left
     alone: that one needs code injected into the game, not a number changed.
     <br>The HUD refuses to print a speed over <b>${t.shown}</b>, and a lane
     faster than that shows a dash instead of a number.</p>` +
    '<div class="speeds">' +
    `<button id="instant" class="${t.instant ? 'on' : ''}">` +
    `${t.instant ? '✓ wind-up near-instant' : 'Wind-up: stock'}</button>` +
    `<button id="uncap" class="${t.uncapped ? 'on' : ''}">` +
    `${t.uncapped ? '✓ readout raised to 9999' : 'Raise the readout to 9999'}` +
    '</button></div>';
  return head + msg + `<div class="speeds">${buttons}</div>` + extras;
}

async function setLane(body) {
  document.querySelectorAll('.speeds button').forEach(b => b.disabled = true);
  try {
    const r = await fetch('api/tradelane', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (r.ok) { lane = await r.json(); render(); }
  } catch (e) { /* leave the buttons as they were */ }
}

function renderDrawDist() {
  const d = draw;
  if (!d) return '';
  if (d.error) return '<h2 class="house">Asteroid draw distance</h2>' +
    `<p class="note warn">${esc(d.error)}</p>`;
  const msg = d.message ? `<p class="note">${esc(d.message)}</p>` : '';
  const buttons = d.choices.map(v =>
    `<button data-draw="${v}"${Math.abs(d.factor - v) < 0.02 ? ' class="on"' : ''}>` +
    `${v}x</button>`).join('');
  return '<h2 class="house">Asteroid draw distance</h2>' +
    `<p class="note">${d.fields} fields, median <b>${d.median}</b> against a
     vanilla ${d.vanilla}. This is a file change, so it lands the next time a
     system loads, and each field is scaled from its own vanilla value rather
     than from wherever it is now, so pressing 1.5x twice is still 1.5x.</p>` +
    `<p class="note">Rocks fill a sphere, so 2x the distance is about 8x the
     geometry on a single-threaded 2003 renderer. Billboards are deliberately
     left alone: they are scattered independently of the real rocks, which is
     why a sprite vanishes and a rock turns up somewhere else, and adding more
     of them makes that worse rather than better.</p>` +
    `<div class="speeds">${buttons}</div>` + msg;
}

async function setDraw(body) {
  document.querySelectorAll('.speeds button').forEach(b => b.disabled = true);
  try {
    const r = await fetch('api/drawdist', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (r.ok) { draw = await r.json(); render(); }
  } catch (e) { /* leave the buttons as they were */ }
}

function renderPersist() {
  if (!speed || speed.error) return '';
  const note = persistMsg
    ? `<p class="note${persistOk ? '' : ' warn'}">${esc(persistMsg)}</p>` : '';
  return '<h2 class="house">Keep these</h2>' +
    `<p class="note">Writes the speeds above into <code>constants.ini</code> and
     <code>st_equip.ini</code>, so the next launch starts with them. Safe to
     press while the game is running: it reads those files once at startup, so
     nothing changes until you relaunch.</p>` +
    `<div class="speeds"><button id="persist"${persistBusy ? ' disabled' : ''}>` +
    `${persistBusy ? 'writing…' : 'Write to the game files'}</button></div>` + note;
}

async function doPersist() {
  persistBusy = true; persistMsg = null; render();
  try {
    const r = await fetch('api/persist', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
    });
    const d = await r.json();
    persistOk = !!d.ok;
    persistMsg = d.message;
  } catch (e) {
    persistOk = false;
    persistMsg = 'the server went away';
  }
  persistBusy = false;
  render();
}

function renderThrusters() {
  const t = thrusters;
  if (!t) return '';
  if (t.error) return `<h2 class="house">Thrusters</h2>` +
    `<p class="note warn">${esc(t.error)}</p>`;
  const msg = t.message ? `<p class="note">${esc(t.message)}</p>` : '';
  const head = `<h2 class="house">Thrusters</h2>` +
    `<p class="note">These are <b>bonuses</b>, added to your ship's
    normal speed, not the speed itself. Vanilla is 120. Only the thruster you
    have fitted matters; the rest are here because swapping one should not need
    a code change.</p>`;
  const rows = t.items.map(it => {
    const buttons = t.choices.map(v =>
      `<button data-ids="${it.ids}" data-speed="${v}"` +
      `${Math.abs(it.speed - v) < 0.5 ? ' class="on"' : ''}>${v}</button>`
    ).join('');
    return `<div class="sys"><div class="head"><b>${esc(it.name)}</b>` +
           `<span class="count">+${it.speed}</span></div>` +
           `<div class="speeds">${buttons}</div></div>`;
  }).join('');
  return head + msg + rows;
}

async function setThruster(ids, value) {
  document.querySelectorAll('.speeds button').forEach(b => b.disabled = true);
  try {
    const r = await fetch('api/thrusters', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids, value })
    });
    if (r.ok) { thrusters = await r.json(); render(); }
  } catch (e) { /* leave the buttons as they were */ }
}

async function setSpeed(value) {
  document.querySelectorAll('.speeds button').forEach(b => b.disabled = true);
  try {
    const r = await fetch('api/speed', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value })
    });
    if (r.ok) { speed = await r.json(); render(); }
  } catch (e) { /* leave the buttons as they were */ }
}

function gunByNick(nick) {
  return (catalogue ? catalogue.weapons : []).find(w => w.nickname === nick);
}

function renderDPS() {
  if (!catalogue) return '<p class="empty">reading the game data…</p>';
  // Keep each weapon's slot in `loadout` beside it. The remove button splices
  // `loadout`, so indexing a filtered copy would delete the wrong gun the
  // moment one nickname failed to resolve.
  const chosen = loadout
    .map((nick, slot) => ({ w: gunByNick(nick), slot }))
    .filter(x => x.w);
  let out = '';

  if (chosen.length) {
    const dps = (v, cls) => `<span class="num ${cls}">${v.toFixed(1)}</span>`;
    // Per-shot figures are floored, which is what the game itself prints: the
    // Adv. Skyrail is 121.2 in the files and 121 on the dealer screen. Showing
    // them the game's way is the point, since these columns exist to be
    // checked against it. The DPS columns keep the full precision.
    const shot = v => `<span class="num raw">${Math.floor(v)}</span>`;
    out += '<div class="guns"><div class="guntable">' +
      '<div class="gunhead"><span class="nm">weapon</span>' +
      '<span class="grp">hull</span><span class="grp">shield</span>' +
      '<span>hull dps</span><span>shield dps</span>' +
      '<span>rate</span><span>refire</span><span></span></div>' +
      chosen.map(({ w, slot }) =>
        `<div class="gun"><span class="nm">${esc(w.name)}` +
        (w.turret ? ' <span class="loot">turret</span>' : '') + '</span>' +
        shot(w.hull) + shot(w.shield) +
        dps(w.hull_dps, 'h') + dps(w.shield_dps, 's') +
        `<span class="num raw">${(1 / w.refire).toFixed(2)}</span>` +
        `<span class="num raw">${w.refire.toFixed(2)}s</span>` +
        `<button class="kill" data-drop="${slot}" title="remove">&times;</button></div>`).join('') +
      `<div class="gun sum"><span class="nm">${chosen.length} mounted</span>` +
      '<span></span><span></span>' +
      dps(chosen.reduce((a, x) => a + x.w.hull_dps, 0), 'h') +
      dps(chosen.reduce((a, x) => a + x.w.shield_dps, 0), 's') +
      '<span></span><span></span><span></span></div></div></div>';
  } else {
    out += '<p class="empty">Nothing mounted. Add a weapon to see what it does.</p>';
  }

  if (gunQuery === null) {
    out += '<p><button class="addgun" id="addgun">+ Add weapon</button></p>';
    return out;
  }

  // 40 is enough to see whether the search is working without turning the
  // panel into the whole catalogue again.
  const q = gunQuery.trim().toLowerCase();
  const hits = catalogue.weapons
    .filter(w => !q || w.name.toLowerCase().includes(q))
    .slice(0, 40);
  out += '<p><input id="gunsearch" placeholder="type a weapon name" ' +
         `value="${esc(gunQuery)}" autocomplete="off"></p><div class="hits">` +
    (hits.length ? hits.map(w =>
      `<button class="hit" data-add="${esc(w.nickname)}">` +
      `<span class="nm">${esc(w.name)}` +
      (w.turret ? ' <span class="loot">turret</span>' : '') + '</span>' +
      `<span class="num">${w.hull_dps.toFixed(0)}</span>` +
      `<span class="num">${w.shield_dps.toFixed(0)}</span></button>`).join('')
      : '<p class="empty">Nothing by that name.</p>') +
    '</div>';
  return out;
}

function wireDPS() {
  const add = $('#addgun');
  if (add) add.addEventListener('click', () => { gunQuery = ''; render(); });
  document.querySelectorAll('.gun .kill').forEach(b =>
    b.addEventListener('click', () => {
      loadout.splice(Number(b.dataset.drop), 1);
      saveLoadout();
      render();
    }));
  document.querySelectorAll('.hit').forEach(b =>
    b.addEventListener('click', () => {
      loadout.push(b.dataset.add);
      saveLoadout();
      gunQuery = null;
      render();
    }));
  const box = $('#gunsearch');
  if (box) {
    // Re-rendering replaces the input, so put the caret back where it was or
    // typing a second character would send it to the front of the box.
    box.focus();
    box.setSelectionRange(box.value.length, box.value.length);
    box.addEventListener('input', e => { gunQuery = e.target.value; render(); });
    box.addEventListener('keydown', e => {
      if (e.key === 'Escape') { gunQuery = null; render(); }
    });
  }
}

function renderLog(d) {
  const all = logNewestFirst ? d.log : d.log.slice().reverse();
  const rows = logPersonalOnly ? all.filter(e => e.personal) : all;
  const personal = all.filter(e => e.personal).length;
  if (!all.length) return '<p class="empty">The log is empty.</p>';
  const starred = rows.filter(e => marks.star[e.key]).length;
  const read = rows.filter(e => marks.read[e.key]).length;
  return '<div class="logbar">' +
    `<button id="logsort">${logNewestFirst ? 'Newest first' : 'Oldest first'}</button>` +
    `<button id="logpersonal" class="${logPersonalOnly ? 'on' : ''}">` +
    `${logPersonalOnly ? '✓ ' : ''}Personal only (${personal})</button>` +
    `<span class="count">${rows.length}` +
    (logPersonalOnly ? ` of ${all.length}` : '') +
    ` entries · ${starred} interesting · ${read} read</span></div>` +
    (rows.length ? '' : '<p class="empty">No personal entries yet.</p>') +
    rows.map(e => {
      const star = !!marks.star[e.key], done = !!marks.read[e.key];
      const cls = ['entry', star ? 'star' : '', done ? 'read' : ''].filter(Boolean).join(' ');
      const subs = e.subs.length
        ? `<ul class="subs">${e.subs.map(s => `<li>${esc(s)}</li>`).join('')}</ul>` : '';
      const key = esc(e.key);
      return `<div class="${cls}"><div class="body">${esc(e.text)}</div>${subs}` +
        `<div class="acts">` +
        `<button data-star="${key}" class="${star ? 'on' : ''}">` +
        `${star ? '★' : '☆'} interesting</button>` +
        `<button data-read="${key}" class="${done ? 'on done' : ''}">` +
        `${done ? '✓ read' : 'mark read'}</button></div></div>`;
    }).join('');
}

function wireLog() {
  const sort = $('#logsort');
  if (sort) sort.addEventListener('click', () => {
    logNewestFirst = !logNewestFirst;
    render();
  });
  const only = $('#logpersonal');
  if (only) only.addEventListener('click', () => {
    logPersonalOnly = !logPersonalOnly;
    render();
  });
  const flip = (which, key) => {
    if (marks[which][key]) delete marks[which][key];
    else marks[which][key] = true;
    saveMarks();
    render();
  };
  document.querySelectorAll('[data-star]').forEach(b =>
    b.addEventListener('click', () => flip('star', b.dataset.star)));
  document.querySelectorAll('[data-read]').forEach(b =>
    b.addEventListener('click', () => flip('read', b.dataset.read)));
}

async function loadCatalogue() {
  if (catalogue) return;
  try {
    const r = await fetch('api/weapons', { cache: 'no-store' });
    if (r.ok) { catalogue = await r.json(); render(); }
  } catch (e) { /* the tab shows its loading line until this succeeds */ }
}

function renderRep() {
  const d = repData;
  if (!d) return '<p class="empty">reading the save…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;

  const opts = d.factions.map(f =>
    `<option value="${esc(f.nickname)}"${f.nickname === repTarget ? ' selected' : ''}>` +
    `${esc(f.name)} (${f.current >= 0 ? '+' : ''}${f.current.toFixed(2)})</option>`).join('');
  const goals = d.goals.map(g =>
    `<option value="${g}"${g === repGoal ? ' selected' : ''}>${g}</option>`).join('');
  let out = '<div class="reppick">' +
    `<select id="reptarget"><option value="">pick a faction…</option>${opts}</select>` +
    `<select id="repgoal">${goals}</select></div>`;

  if (!d.target) return out + '<p class="empty">Pick a faction and a target standing.</p>';

  const head = `<p class="note">${esc(nameOf(d, d.target))} is at ` +
    `<b>${d.current >= 0 ? '+' : ''}${d.current.toFixed(2)}</b>, ` +
    `you want <b>${d.goal}</b>. Gap ${d.needed >= 0 ? '+' : ''}${d.needed.toFixed(2)}.</p>`;
  if (!d.rows.length)
    return out + head + '<p class="empty">Already there. Nothing to do.</p>';

  const bribes = d.rows.filter(r => r.event === 'bribe').length;
  out += head + `<p class="note">${d.rows.length - bribes} of 220 repeatable
    actions move it the right way${bribes ? ', plus a bribe' : ''}, all listed.
    Counts are rounded up, so the last one takes you past the goal rather than
    onto it. <b>+n/-n</b> is how many other factions the run helps and hurts;
    click a row for the full list.</p>`;

  out += '<div class="guns"><div class="reptable">' +
    '<div class="gunhead"><span class="nm">action</span><span>each</span>' +
    '<span>times / cost</span><span class="othershead">side effects</span></div>' +
    d.rows.map((r, i) => {
      const loss = r.collateral.filter(c => c.change < 0);
      const gain = r.collateral.filter(c => c.change > 0);
      // Spelled out. Read as "+2/-21 Bretonia -0.280" the middle number looks
      // like it belongs to the name, and the owner read a fall as a rise.
      const worst = loss.length
        ? `, worst hit ${esc(loss[0].name)} ${loss[0].change.toFixed(2)}` : '';
      const body = repOpen[i] ? '<div class="repwhy">' +
        '<span class="repline rephead"><span class="nm">also moves</span>' +
        '<span>now</span><span>after</span><span>change</span></span>' +
        r.collateral.map(c =>
        `<span class="repline"><span class="nm">${esc(c.name)}` +
        (c.pinned ? ' <span class="loot">pinned</span>' : '') + '</span>' +
        `<span class="num raw">${c.before >= 0 ? '+' : ''}${c.before.toFixed(2)}</span>` +
        `<span class="num raw">${c.after >= 0 ? '+' : ''}${c.after.toFixed(2)}</span>` +
        `<span class="num ${c.change < 0 ? 's' : 'h'}">` +
        `${c.change >= 0 ? '+' : ''}${c.change.toFixed(2)}</span></span>`).join('')
        + '</div>' : '';
      return `<div class="gun reprow" data-row="${i}">` +
        `<span class="nm">${esc(r.event_label)} &middot; ${esc(r.doer_name)}` +
        (r.bartenders ? ` <span class="loot">${r.bartenders} bars</span>` : '') +
        (r.legality ? ` <span class="loot">${esc(r.legality)}</span>` : '') + '</span>' +
        // Standings round to two, but not this: 18 of the 69 Corsair rows are
        // worth under 0.005 a go and would all read +0.00, turning "142 times"
        // into nonsense. The small numbers here are the whole reason the repeat
        // counts are large.
        `<span class="num raw">${r.effect >= 0 ? '+' : ''}${r.effect.toFixed(4)}</span>` +
        `<span class="num h">${r.price ? r.price.toLocaleString() + ' cr' : r.repeats}</span>` +
        `<span class="others">${gain.length} up, ${loss.length} down${worst}</span>` +
        '</div>' + body;
    }).join('') + '</div></div>';
  return out;
}

function nameOf(d, nick) {
  const f = d.factions.find(x => x.nickname === nick);
  return f ? f.name : nick;
}

async function loadRep() {
  const q = repTarget ? `?to=${encodeURIComponent(repTarget)}&goal=${repGoal}` : '';
  try {
    const r = await fetch('api/reputation' + q, { cache: 'no-store' });
    if (r.ok) { repData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}

function wireRep() {
  const t = $('#reptarget'), g = $('#repgoal');
  if (t) t.addEventListener('change', e => {
    repTarget = e.target.value;
    for (const k in repOpen) delete repOpen[k];
    loadRep();
  });
  if (g) g.addEventListener('change', e => {
    repGoal = e.target.value;
    for (const k in repOpen) delete repOpen[k];
    loadRep();
  });
  document.querySelectorAll('.reprow').forEach(b =>
    b.addEventListener('click', () => {
      const i = b.dataset.row;
      repOpen[i] = !repOpen[i];
      render();
    }));
}

function render() {
  // The Speed tab reads the running process rather than the save, so it carries
  // neither the totals row nor the Show All box. Cruise and thrusters live on it
  // together: they are one question, "how fast does this ship go".
  const live = tab === 'speed';
  // Only the two per-system reports want the totals row and the Show All box.
  // The rest carry their own controls, or none.
  const bare = live || tab === 'dps' || tab === 'log';
  $('#totals').hidden = bare;
  $('#togglewrap').hidden = bare;
  if (tab === 'rep') {
    $('#totals').hidden = true;
    $('#togglewrap').hidden = true;
    $('#sub').textContent = 'what it takes to change how a faction feels';
    $('#list').innerHTML = renderRep();
    wireRep();
    return;
  }
  if (tab === 'dps') {
    $('#sub').textContent = 'damage per second, from the weapon stats alone';
    $('#list').innerHTML = renderDPS();
    wireDPS();
    return;
  }
  if (live) {
    $('#sub').textContent = 'live speed of the running game';
    $('#list').innerHTML =
      renderSpeed() + renderThrusters() + renderTradeLane() +
      renderDrawDist() + renderPersist();
    // Every button in a .speeds row is told apart by the data it carries: a
    // thruster names its thruster, a lane button names its speed, a cruise
    // button carries neither. The two by-id buttons are bound separately.
    document.querySelectorAll('.speeds button').forEach(b => {
      if (b.id === 'persist' || b.id === 'uncap' || b.id === 'instant') return;
      if (b.dataset.draw) {
        b.addEventListener('click',
          () => setDraw({ factor: Number(b.dataset.draw) }));
        return;
      }
      b.addEventListener('click', () => {
        if (b.dataset.lane) setLane({ value: Number(b.dataset.lane) });
        else if (b.dataset.ids)
          setThruster(Number(b.dataset.ids), Number(b.dataset.speed));
        else setSpeed(Number(b.dataset.speed));
      });
    });
    const keep = $('#persist');
    if (keep) keep.addEventListener('click', doPersist);
    const uncap = $('#uncap');
    if (uncap) uncap.addEventListener('click',
      () => setLane({ uncapped: !(lane && lane.uncapped) }));
    const inst = $('#instant');
    if (inst) inst.addEventListener('click',
      () => setLane({ instant: !(lane && lane.instant) }));
    return;
  }
  if (!latest) return;
  const d = latest;
  $('#sub').textContent =
    `${d.save} · updated ${new Date(d.saved_at * 1000).toLocaleTimeString()}`;
  if (tab === 'log') {
    $('#list').innerHTML = renderLog(d);
    wireLog();
    return;
  }
  $('#extlabel').textContent = tab === 'visits'
    ? 'show every system and the bases you have not found'
    : 'show every system, the wrecks you have not found, and what they hold';
  $('#hidelabel').textContent = tab === 'visits'
    ? 'hide systems where every base is docked at'
    : 'hide systems where every wreck is stripped';
  foldOnFirstSight(d);
  $('#list').innerHTML = tab === 'visits' ? renderVisits(d) : renderWrecks(d);
}

async function poll() {
  try {
    const r = await fetch('api/state', { cache: 'no-store' });
    if (r.ok) { latest = await r.json(); }
  } catch (e) { /* the server went away; keep showing the last good state */ }
  // Only the live tab you are looking at gets polled. Locating a value means
  // scanning some 440 MiB of process memory, so asking for both every five
  // seconds would burn real CPU to refresh a panel nobody has open.
  try {
    if (tab === 'speed') {
      const [a, b, c, e] = await Promise.all([
        fetch('api/speed', { cache: 'no-store' }),
        fetch('api/thrusters', { cache: 'no-store' }),
        fetch('api/tradelane', { cache: 'no-store' }),
        fetch('api/drawdist', { cache: 'no-store' })
      ]);
      if (a.ok) { const s = await a.json(); speed = { ...s, message: speed && speed.message }; }
      if (b.ok) { const s = await b.json(); thrusters = { ...s, message: thrusters && thrusters.message }; }
      if (c.ok) { const s = await c.json(); lane = { ...s, message: lane && lane.message }; }
      if (e.ok) { const s = await e.json(); draw = { ...s, message: draw && draw.message }; }
    }
  } catch (e) { /* the game went away; keep showing the last good state */ }
  render();
}
poll();
setInterval(poll, 5000);
</script>
"""


def make_handler(game, save_path):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/state":
                try:
                    with lock:
                        state = read_state(game, save_path)
                    body = json.dumps(state).encode("utf-8")
                    self._send(200, body, "application/json")
                except FileNotFoundError:
                    self._send(404, b'{"error":"save not found"}', "application/json")
            elif path == "/api/weapons":
                # Static game data, so it is fetched once and never polled.
                body = json.dumps({"weapons": game.weapons}).encode("utf-8")
                self._send(200, body, "application/json")
            elif path == "/api/speed":
                self._send_speed()
            elif path == "/api/thrusters":
                self._send_thrusters()
            elif path == "/api/tradelane":
                self._send_tradelane()
            elif path == "/api/reputation":
                self._send_reputation()
            elif path == "/api/drawdist":
                self._send_drawdist()
            else:
                self._send(404, b"not found", "text/plain")

        def _send_reputation(self):
            """The faction list, or a worked plan when one is asked for."""
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(self.path).query)
            body = {"goals": sorted(rep.GOALS), "factions": [],
                    "target": None, "goal": None, "current": None,
                    "needed": None, "rows": [], "error": None}
            try:
                with lock:
                    reps = rep.player_reps(fl.decode_save(save_path))
                    model = game.repmodel
                events, empathy, names, legality, _bribes = model
                # Ordered by standing rather than by name: the faction you
                # want to do something about is the one at the bottom of the
                # list of how everyone feels, so it should be the first thing
                # in the dropdown, not filed under its initial letter.
                body["factions"] = sorted(
                    ({"nickname": k, "name": names.get(k, k),
                      "legality": legality.get(k, ""),
                      "current": round(reps.get(k, 0.0), 4)}
                     for k in events),
                    key=lambda f: (f["current"], f["name"]))
                want = (query.get("to") or [None])[0]
                goal = (query.get("goal") or ["neutral"])[0]
                if want and want.lower() in events and goal in rep.GOALS:
                    current, needed, rows = rep.plan(
                        want.lower(), rep.GOALS[goal], reps, *model)
                    body.update(target=want.lower(), goal=goal,
                                current=round(current, 4),
                                needed=round(needed, 4), rows=rows)
            except (OSError, ValueError, KeyError) as exc:
                body["error"] = str(exc)
            self._send(200, json.dumps(body).encode("utf-8"), "application/json")

        def _send_drawdist(self, message=None):
            """Where asteroid fields currently start being real rocks."""
            body = {"choices": DRAWDIST_CHOICES, "factor": None, "fields": 0,
                    "median": None, "vanilla": None,
                    "error": None, "message": message}
            try:
                rows = dd.survey(game.dir)
                if rows:
                    base = sorted(r[1] for r in rows)
                    now = sorted(r[2] for r in rows)
                    mid = len(rows) // 2
                    body["fields"] = len(rows)
                    body["vanilla"] = round(base[mid])
                    body["median"] = round(now[mid])
                    # One number for the whole set only makes sense because
                    # every field is scaled from its own vanilla value.
                    body["factor"] = round(now[mid] / base[mid], 3)
            except (dd.WriteFailed, OSError) as exc:
                body["error"] = str(exc)
            self._send(200, json.dumps(body).encode("utf-8"), "application/json")

        def _send_tradelane(self, message=None):
            """Trade lane speed and the HUD's own ceiling, or why not."""
            body = {"choices": TRADELANE_CHOICES, "vanilla": tl.VANILLA,
                    "value": None, "uncapped": False, "shown": None,
                    "instant": False, "error": None, "message": message}
            try:
                value, version = tl.read()
                body["value"] = round(value, 1)
                _rate, body["instant"] = tl.read_accel(version=version)
                body["uncapped"], body["shown"] = tl.read_cap()
            except (tl.NotRunning, OSError) as exc:
                body["error"] = str(exc)
            self._send(200, json.dumps(body).encode("utf-8"), "application/json")

        def _send_thrusters(self, message=None):
            """Every thruster and its bonus, or why they cannot be read."""
            body = {"choices": th.SPEED_CHOICES, "items": [],
                    "error": None, "message": message}
            try:
                # The infocards are already loaded for the rest of the report,
                # so the names come from there rather than a second read.
                labels = {ids: game.names.get(ids) or nick
                          for ids, nick in th.THRUSTERS.items()}
                _pid, rows = th.read_all()
                body["items"] = [
                    {"ids": ids, "name": labels.get(ids, nick),
                     "speed": round(value, 1)}
                    for ids, nick, _addr, value in rows
                ]
            except (th.NotRunning, OSError) as exc:
                body["error"] = str(exc)
            self._send(200, json.dumps(body).encode("utf-8"), "application/json")

        def _send_speed(self, message=None):
            """Current cruise speed, or why it cannot be read.

            A missing game is the normal case, not an error: the page is
            usually open before Freelancer is started.
            """
            body = {"choices": SPEED_CHOICES, "value": None,
                    "error": None, "message": message}
            try:
                _pid, _addr, value = sp.current()
                body["value"] = round(value, 1)
            except sp.NotRunning as exc:
                body["error"] = str(exc)
            self._send(200, json.dumps(body).encode("utf-8"), "application/json")

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/persist":
                try:
                    with lock:
                        told = pe.write(game.dir)
                    body = {"ok": True, "message": "; ".join(told)}
                except (sp.NotRunning, pe.WriteFailed, OSError) as exc:
                    body = {"ok": False, "message": str(exc)}
                self._send(200, json.dumps(body).encode("utf-8"), "application/json")
                return
            if path == "/api/drawdist":
                try:
                    size = int(self.headers.get("Content-Length") or 0)
                    sent = json.loads(self.rfile.read(size) or b"{}")
                    with lock:
                        if sent.get("restore"):
                            note = f"{dd.restore(game.dir)} fields back to vanilla"
                        else:
                            factor = float(sent["factor"])
                            n = dd.apply(factor, game.dir)
                            note = (f"{n} fields scaled to {factor:g}x; takes "
                                    "effect the next time a system loads")
                    self._send_drawdist(message=note)
                except (ValueError, KeyError, TypeError, dd.WriteFailed, OSError) as exc:
                    body = {"choices": DRAWDIST_CHOICES, "factor": None,
                            "fields": 0, "median": None, "vanilla": None,
                            "error": str(exc), "message": None}
                    self._send(200, json.dumps(body).encode("utf-8"),
                               "application/json")
                return
            if path == "/api/tradelane":
                try:
                    size = int(self.headers.get("Content-Length") or 0)
                    sent = json.loads(self.rfile.read(size) or b"{}")
                    with lock:
                        if "uncapped" in sent:
                            on, shown = tl.set_cap(bool(sent["uncapped"]))
                            note = (f"speed readout {'uncapped' if on else 'capped'}"
                                    f", max {shown}")
                        elif "instant" in sent:
                            rate, on = tl.set_accel(bool(sent["instant"]))
                            note = (f"wind-up {rate:g}, "
                                    f"{'near-instant' if on else 'stock'}")
                        else:
                            got = tl.set_speed(float(sent["value"]))
                            note = f"trade lane speed set to {got:g}"
                    self._send_tradelane(message=note)
                except (ValueError, KeyError, TypeError, tl.NotRunning, OSError) as exc:
                    body = {"choices": TRADELANE_CHOICES, "vanilla": tl.VANILLA,
                            "value": None, "uncapped": False, "shown": None,
                            "error": str(exc), "message": None}
                    self._send(200, json.dumps(body).encode("utf-8"),
                               "application/json")
                return
            if path not in ("/api/speed", "/api/thrusters"):
                self._send(404, b"not found", "text/plain")
                return
            try:
                size = int(self.headers.get("Content-Length") or 0)
                sent = json.loads(self.rfile.read(size) or b"{}")
                wanted = float(sent["value"])
            except (ValueError, KeyError, TypeError):
                self._send(400, b'{"error":"bad value"}', "application/json")
                return

            if path == "/api/thrusters":
                try:
                    ids = int(sent["ids"])
                    with lock:
                        th.set_speed(ids, wanted)
                    name = game.names.get(ids) or th.THRUSTERS.get(ids, ids)
                    self._send_thrusters(message=f"{name} set to +{wanted:g}")
                except (th.NotRunning, ValueError, KeyError, TypeError) as exc:
                    body = {"choices": th.SPEED_CHOICES, "items": [],
                            "error": str(exc), "message": None}
                    self._send(200, json.dumps(body).encode("utf-8"), "application/json")
                return

            try:
                # Re-locate rather than trusting a cached address: common.dll
                # moves between runs, and the game may have been restarted
                # since the page was loaded.
                with lock:
                    sp.set_speed(wanted)
                self._send_speed(message=f"cruise speed set to {wanted:g}")
            except (sp.NotRunning, ValueError) as exc:
                body = {"choices": SPEED_CHOICES, "value": None,
                        "error": str(exc), "message": None}
                self._send(200, json.dumps(body).encode("utf-8"), "application/json")

        def log_message(self, *args):
            pass  # a poll every five seconds would bury anything worth reading

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save", nargs="?", help="save file to follow (default: AutoSave.fl)")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--port", type=int, default=8731)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    save = args.save or find_default_save(args.game)
    if not save or not os.path.exists(save):
        sys.exit("no save file found; pass one as an argument")

    started = time.time()
    game = GameData(args.game)
    print(f"game data loaded in {time.time() - started:.2f}s "
          f"({len(game.bases)} bases, {len(game.names)} strings)")
    print(f"following {save}")
    print(f"http://{args.host}:{args.port}/")

    server = ThreadingHTTPServer((args.host, args.port), make_handler(game, save))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
