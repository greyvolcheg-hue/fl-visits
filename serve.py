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
import wrecks as wr  # noqa: E402

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
        self.wrecks = wr.load_wrecks(game_dir)

    def label(self, ids, fallback):
        try:
            return self.names.get(int(ids), fallback)
        except (TypeError, ValueError):
            return fallback

    def system_label(self, system):
        return self.label(self.system_ids.get(system, 0), system)


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

    wreck_rows = wr.group_by_system(game.wrecks, visits, game.system_label)

    return {
        "systems": out,
        "wrecks": wreck_rows,
        "wrecks_found": sum(len(r["found"]) for r in wreck_rows),
        "wrecks_total": len(game.wrecks),
        "wrecks_systems": sum(1 for r in wreck_rows if r["found"]),
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
  .wreck.m .mark { color: var(--unknown); }
  .wreck.m .nm { color: var(--dim); }
  .wreck .nm { flex: none; min-width: 12rem; }
  .loot { color: var(--dim); font-size: .82rem; }
  .cell { flex: none; width: 3.4rem; color: var(--dim);
          font-variant-numeric: tabular-nums; }
</style>
<div class="wrap">
  <h1>Freelancer</h1>
  <div class="sub" id="sub">loading…</div>
  <nav class="tabs">
    <button class="tab on" data-tab="visits">Visits</button>
    <button class="tab" data-tab="wrecks">Wrecks</button>
  </nav>
  <div class="totals" id="totals"></div>
  <label class="toggle">
    <input type="checkbox" id="ext"> <span id="extlabel"></span>
  </label>
  <div id="list"></div>
</div>
<script>
const $ = s => document.querySelector(s);
let extended = false, latest = null, tab = 'visits';

$('#ext').addEventListener('change', e => { extended = e.target.checked; render(); });
document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => {
  tab = b.dataset.tab;
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x === b));
  render();
}));

function esc(s) { return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function line(cls, tag, items) {
  if (!items.length) return '';
  return `<div class="row ${cls}"><span class="tag ${cls}">${tag} ${items.length}</span>` +
         `<span>${items.map(esc).join(', ')}</span></div>`;
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

function renderVisits(d) {
  totals([[d.docked, 'docked'], [d.revealed, 'revealed'],
          [d.bases - d.docked - d.revealed, 'unknown'],
          [`${d.systems_touched}/${d.systems_total}`, 'systems']]);
  const rows = d.systems.filter(s => extended || s.docked.length || s.revealed.length);
  return rows.length ? rows.map(s => card(s.system, s.docked.length, s.total, s.percent,
      line('d', 'docked', s.docked) + line('r', 'revealed', s.revealed) +
      (extended ? line('u', 'unknown', s.unknown) : ''))).join('')
    : '<p class="empty">Nothing docked at yet.</p>';
}

function wreckLine(w, found) {
  const loot = extended && w.loot.length
    ? `<span class="loot">${w.loot.map(([i, n]) => `${n}x ${esc(i)}`).join(', ')}</span>` : '';
  const where = [w.sector, w.spot].filter(Boolean).join(' ');
  return `<div class="wreck ${found ? 'f' : 'm'}"><span class="mark">${found ? '+' : '-'}</span>` +
         `<span class="cell">${esc(where)}</span>` +
         `<span class="nm">${esc(w.name)}</span>${loot}</div>`;
}

function renderWrecks(d) {
  totals([[d.wrecks_found, 'found'], [d.wrecks_total - d.wrecks_found, 'left'],
          [`${d.wrecks_systems}/${d.wrecks_systems_total}`, 'systems']]);
  const rows = d.wrecks.filter(s => extended || s.found.length);
  return rows.length ? rows.map(s => card(s.system, s.found.length, s.total, s.percent,
      s.found.map(w => wreckLine(w, true)).join('') +
      (extended ? s.missing.map(w => wreckLine(w, false)).join('') : ''))).join('')
    : '<p class="empty">No wrecks found yet. Tick the box to see where they are.</p>';
}

function render() {
  if (!latest) return;
  const d = latest;
  $('#sub').textContent =
    `${d.save} · updated ${new Date(d.saved_at * 1000).toLocaleTimeString()}`;
  $('#extlabel').textContent = tab === 'visits'
    ? 'show every system and the bases you have not found'
    : 'show every system, the wrecks you have not found, and what they hold';
  $('#list').innerHTML = tab === 'visits' ? renderVisits(d) : renderWrecks(d);
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
