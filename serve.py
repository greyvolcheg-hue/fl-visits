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
import flvisits as fl  # noqa: E402

REVEALED = 1  # story put it on the nav map; the player has never docked there


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
        data_dir = fl.ipath(game_dir, "DATA")
        bases, systems = fl.load_universe(data_dir)
        self.objects = fl.load_objects(data_dir, systems)

        # Keep only bases something in space actually points at. universe.ini
        # carries 15 that nothing does: the three intro-cutscene copies of
        # Manhattan (same strid_name, so they print as duplicates), plus story
        # locations like Battleship Osiris. A `visit` record is written against
        # a space object, so a base without one can never be recorded, and
        # counting it would put a permanent floor under every percentage.
        reachable = {base.lower() for _, base, _ in self.objects.values()}
        self.bases = {k: v for k, v in bases.items() if k in reachable}

        self.names = fl.load_names(game_dir)
        self.system_ids = {nick.lower(): ids for nick, ids in systems.items()}
        self.by_hash = {fl.fl_hash(nick): nick for nick in self.objects}

    def label(self, ids, fallback):
        try:
            return self.names.get(int(ids), fallback)
        except (TypeError, ValueError):
            return fallback


def read_state(game, save_path):
    """Split every base into docked / revealed / unknown, grouped by system."""
    visits = fl.parse_visits(fl.decode_save(save_path))

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
             "docked": [], "revealed": [], "unknown": []},
        )
        flag = flags.get(key)
        bucket = "docked" if flag in fl.DOCKED else "revealed" if flag == REVEALED else "unknown"
        row[bucket].append(game.label(ids, key))

    out = []
    for row in systems.values():
        for bucket in ("docked", "revealed", "unknown"):
            row[bucket].sort()
        row["total"] = len(row["docked"]) + len(row["revealed"]) + len(row["unknown"])
        row["percent"] = round(100 * len(row["docked"]) / row["total"]) if row["total"] else 0
        out.append(row)
    out.sort(key=lambda r: (-r["percent"], -len(r["docked"]), r["system"]))

    return {
        "systems": out,
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
</style>
<div class="wrap">
  <h1>Freelancer visits</h1>
  <div class="sub" id="sub">loading…</div>
  <div class="totals" id="totals"></div>
  <label class="toggle">
    <input type="checkbox" id="ext"> show every system and the bases you have not found
  </label>
  <div id="list"></div>
</div>
<script>
const $ = s => document.querySelector(s);
let extended = false, latest = null;

$('#ext').addEventListener('change', e => { extended = e.target.checked; render(); });

function esc(s) { return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function line(cls, tag, items) {
  if (!items.length) return '';
  return `<div class="row ${cls}"><span class="tag ${cls}">${tag} ${items.length}</span>` +
         `<span>${items.map(esc).join(', ')}</span></div>`;
}

function render() {
  if (!latest) return;
  const d = latest;
  $('#sub').textContent =
    `${d.save} · updated ${new Date(d.saved_at * 1000).toLocaleTimeString()}`;
  $('#totals').innerHTML = [
    [d.docked, 'docked'], [d.revealed, 'revealed'], [d.bases - d.docked - d.revealed, 'unknown'],
    [`${d.systems_touched}/${d.systems_total}`, 'systems'],
  ].map(([n, l]) => `<div><span class="n">${n}</span><span class="lbl">${l}</span></div>`).join('');

  const rows = d.systems.filter(s => extended || s.docked.length || s.revealed.length);
  $('#list').innerHTML = rows.length ? rows.map(s => `
    <div class="sys">
      <div class="head"><b>${esc(s.system)}</b>
        <span class="count">${s.docked.length} / ${s.total}</span></div>
      <div class="bar"><i style="width:${s.percent}%"></i></div>
      ${line('d', 'docked', s.docked)}
      ${line('r', 'revealed', s.revealed)}
      ${extended ? line('u', 'unknown', s.unknown) : ''}
    </div>`).join('') : '<p class="empty">Nothing visited yet.</p>';
}

async function poll() {
  try {
    const r = await fetch('api/state', { cache: 'no-store' });
    if (r.ok) { latest = await r.json(); render(); }
  } catch (e) { /* the server went away; keep showing the last good state */ }
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
            else:
                self._send(404, b"not found", "text/plain")

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
