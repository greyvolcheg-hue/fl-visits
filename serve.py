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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import docking as dk  # noqa: E402
import equipment as eqp  # noqa: E402
import flvisits as fl  # noqa: E402
import navmap  # noqa: E402
import reputation as rep  # noqa: E402
import netlog as nl  # noqa: E402
import speed as sp  # noqa: E402
import trade as td  # noqa: E402
import weapons as wp  # noqa: E402
import wrecks as wr  # noqa: E402
import views  # noqa: E402

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
        # Who owns each base. Static, so it is read once here rather than per
        # request, and the names it resolves against come from the reputation
        # model below, which reads initialworld.ini for the Reputation tab.
        self.owners = dk.base_owners(data_dir, fl.system_files)
        # Static: no save and no running game needed, so the DPS tab works with
        # Freelancer closed.
        self.weapons = wp.load_weapons(game_dir)
        # The empathy table never changes; only the player's own
        # standings come from the save, and those are read per request.
        self.repmodel = rep.load_model(game_dir)
        # Pulled out by name so the Visits tab does not have to know the shape
        # of the reputation model to put a badge on a base.
        self.faction_name = self.repmodel.names
        self.faction_short = self.repmodel.shorts
        # Prices never change while the game runs; only which bases
        # you have seen does, and that comes from the save.
        self.market = td.load_market(game_dir)
        # Guns and shields with their stats, prices and dealers. Static too,
        # and it reuses `weapons` and `trade.base_index` rather than parsing
        # any of it a second time.
        self.gear = eqp.load_catalogue(game_dir)

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
        # The owning faction rides on every base, not just the revealed ones.
        # It costs two dictionary lookups and it is the page, not the payload,
        # that decides where a badge is worth showing.
        owner = game.owners.get(key, "")
        row[bucket].append({"name": game.label(ids, key),
                            "at": game.sectors.get(key, ""),
                            "faction": game.faction_short.get(owner, ""),
                            "faction_full": game.faction_name.get(owner, "")})

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
        # The Trade tab needs to know where you have actually been, and this
        # is the only place the save has already been read for exactly that.
        "docked_bases": sorted(k for k, v in game.bases.items()
                               if flags.get(k) in fl.DOCKED),
    }



# --- the page -------------------------------------------------------------
#
# Assembled from the view modules, in one order and one place. The script is
# still a single inline block: a parse error anywhere in it takes all of it,
# which is worth knowing but not worth splitting into files a browser would
# fetch one at a time.

BODY = open(os.path.join(HERE, "views", "_body.txt")).read()

PAGE = f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Freelancer visits</title>
<style>{views.css()}</style>
{BODY}
<script>
const $ = s => document.querySelector(s);
const TABS = {json.dumps(views.tabs())};
// Views register into this; see views/shell.py for the shape.
const VIEW = {{}};
{views.shell.JS}
{views.js()}
{views.shell.BOOT}
</script>
"""


class Ctx:
    """What a view's endpoint is handed: the data, the save, the query."""

    def __init__(self, game, save, lock, query=None):
        self.game, self.save, self.lock = game, save, lock
        self.query = query or {}

    def one(self, key, default=None):
        return (self.query.get(key) or [default])[0]

    def state(self):
        with self.lock:
            return read_state(self.game, self.save)

    def docked(self):
        return set(self.state()["docked_bases"])


def make_handler(game, save_path):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype, cache="no-store"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            # Everything here reads a live save or a running game. The chart is
            # the exception: 840 KB that never changes, on a page that redraws
            # every five seconds.
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, body):
            self._send(200, json.dumps(body).encode("utf-8"), "application/json")

        def _ctx(self):
            from urllib.parse import parse_qs, urlparse
            return Ctx(game, save_path, lock, parse_qs(urlparse(self.path).query))

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            name = path[len("/api/"):] if path.startswith("/api/") else None
            if path in ("/", "/index.html"):
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif name == "state":
                try:
                    self._json(self._ctx().state())
                except FileNotFoundError:
                    self._send(404, b'{"error":"save not found"}', "application/json")
            elif name == "weapons":
                self._json({"weapons": game.weapons})  # static; fetched once
            elif name in views.GET:
                self._json(views.GET[name](self._ctx()))
            elif path == "/map.jpg":
                try:
                    with open(views.chart.FILE, "rb") as fh:
                        self._send(200, fh.read(), "image/jpeg",
                                   "public, max-age=86400")
                except OSError:
                    self._send(404, b"chart not found", "text/plain")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            name = self.path.split("?", 1)[0][len("/api/"):]
            if name not in views.SET:
                self._send(404, b"not found", "text/plain")
                return
            size = int(self.headers.get("Content-Length") or 0)
            try:
                sent = json.loads(self.rfile.read(size) or b"{}")
            except ValueError:
                sent = {}
            ctx = self._ctx()
            ok, note = True, None
            try:
                note = views.SET[name](ctx, sent)
            except Exception as exc:  # noqa: BLE001 - any failure is a message
                # A write that failed is a note on the panel, not a broken
                # panel. The reading below is re-read either way, so it shows
                # what is actually true rather than a synthesised blank.
                ok, note = False, str(exc)
            body = views.GET[name](ctx) if name in views.GET else {}
            body["message"] = note
            body.setdefault("ok", ok)
            self._json(body)

        def log_message(self, *args):
            pass  # a poll every five seconds would bury anything worth reading

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save", nargs="?", help="save to follow (default: AutoSave.fl)")
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
