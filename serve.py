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
import flvisits as fl  # noqa: E402
import speed as sp  # noqa: E402
import wrecks as wr  # noqa: E402

# Offered on the Speed tab. 300 is roughly vanilla, 1000 is what constants.ini
# carries, and the top of the range is where ANOM_LIMITS_MAX_VELOCITY sits, so
# 10000 may clamp: that cap is a separate constant this does not touch.
SPEED_CHOICES = [300, 500, 1000, 2000, 5000, 7500, 10000]

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
    # Least explored first, so the systems with something left to do are at the
    # top. Systems with nothing docked at are not "0% done and therefore first":
    # they are the ones you have not started, so they go to the bottom in name
    # order rather than heading the list every time.
    out.sort(key=lambda r: (r["percent"] == 0, r["percent"], r["system"]))

    wreck_rows = wr.group_by_system(game.wrecks, visits, game.system_label)

    return {
        "systems": out,
        "wrecks": wreck_rows,
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
  .wreck.o .mark { color: var(--revealed); }
  .wreck.o .nm { color: var(--revealed); }
  .wreck.m .mark { color: var(--unknown); }
  .wreck.m .nm { color: var(--dim); }
  .wreck .nm { flex: none; min-width: 12rem; }
  .loot { color: var(--dim); font-size: .82rem; }
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
  </nav>
  <div class="totals" id="totals"></div>
  <label class="toggle" id="togglewrap">
    <input type="checkbox" id="ext"> <span id="extlabel"></span>
  </label>
  <div id="list"></div>
</div>
<script>
const $ = s => document.querySelector(s);
let extended = false, latest = null, speed = null, tab = 'visits';

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
  // Three states, not two: a wreck you found but never opened still holds its
  // loot, and the game says so in bit 8 of the visit flag.
  const cls = !found ? 'm' : w.emptied ? 'f' : 'o';
  const mark = !found ? '-' : w.emptied ? '+' : '*';
  // The loot of an untouched wreck is what you would actually collect, so it
  // stays on screen without the checkbox; for an emptied one it is history.
  const showLoot = w.loot.length && (extended || (found && !w.emptied));
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
  const rows = d.wrecks.filter(s => extended || s.found.length);
  return rows.length ? rows.map(s => card(s.system, s.stripped, s.total, s.percent,
      s.found.map(w => wreckLine(w, true)).join('') +
      (extended ? s.missing.map(w => wreckLine(w, false)).join('') : ''))).join('')
    : '<p class="empty">No wrecks found yet. Tick the box to see where they are.</p>';
}

function renderSpeed() {
  const s = speed;
  if (!s) return '<p class="empty">Reading the game…</p>';
  // No game running is the ordinary case, not a failure: the page is usually
  // open before Freelancer is.
  const head = s.error
    ? `<p class="note warn">${esc(s.error)}</p>`
    : `<p class="note">Cruise speed is <b>${s.value}</b>. A change applies to the
       next cruise burn, no reload. It lasts until the game is closed; the file
       still says what it said.</p>`;
  const msg = s.message ? `<p class="note">${esc(s.message)}</p>` : '';
  const buttons = s.choices.map(v =>
    `<button data-speed="${v}" ${s.error ? 'disabled' : ''}` +
    `${!s.error && Math.abs(s.value - v) < 0.5 ? ' class="on"' : ''}>${v}</button>`
  ).join('');
  return head + msg + `<div class="speeds">${buttons}</div>` +
    `<p class="note">10000 is where ANOM_LIMITS_MAX_VELOCITY sits, so it may
     clamp; that cap is a separate constant this does not touch.</p>`;
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

function render() {
  const onSpeed = tab === 'speed';
  $('#totals').hidden = onSpeed;
  $('#togglewrap').hidden = onSpeed;
  if (onSpeed) {
    $('#sub').textContent = 'live cruise speed of the running game';
    $('#list').innerHTML = renderSpeed();
    document.querySelectorAll('.speeds button').forEach(b =>
      b.addEventListener('click', () => setSpeed(Number(b.dataset.speed))));
    return;
  }
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
    if (r.ok) { latest = await r.json(); }
  } catch (e) { /* the server went away; keep showing the last good state */ }
  try {
    // Polled too, so the tab notices the game starting or stopping on its own.
    const r = await fetch('api/speed', { cache: 'no-store' });
    if (r.ok) { const s = await r.json(); speed = { ...s, message: speed && speed.message }; }
  } catch (e) { /* same */ }
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
            elif path == "/api/speed":
                self._send_speed()
            else:
                self._send(404, b"not found", "text/plain")

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
            if self.path.split("?", 1)[0] != "/api/speed":
                self._send(404, b"not found", "text/plain")
                return
            try:
                size = int(self.headers.get("Content-Length") or 0)
                wanted = float(json.loads(self.rfile.read(size) or b"{}")["value"])
            except (ValueError, KeyError, TypeError):
                self._send(400, b'{"error":"bad value"}', "application/json")
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
