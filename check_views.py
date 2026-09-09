#!/usr/bin/env python3
"""Draw every view in a real browser and show which ones throw.

    ./run.sh &
    python3 check_views.py        # writes a PNG; open it

**This is the check Python cannot do and curl cannot do.** The page is one
inline script concatenated from every view module, so a name a module uses but
nobody declares is a `ReferenceError` at draw time. Python compiles. The
endpoints answer 200. The tab just sits there saying "loading".

That shipped twice on 2026-09-06, both out of the same split: `persistBusy` and
its two neighbours were dropped from the shell, which stopped Speed drawing,
and then `marks` and `saveMarks` went the same way and took Neural Net with
them. Nothing but opening the page found either.

So this opens the page: real script, real API payloads seeded into the view
globals, all eleven views drawn one at a time so a failure names itself instead
of hiding the rest. Each view is drawn twice, once from an empty payload and
once from a populated one, because the picker a tab shows before you choose
anything and the table it shows afterwards are separate code and each has
broken on its own. The report is written into the page and photographed,
because a headless browser has no other way to tell you anything.

Needs `firefox` and a running server.
"""

import json
import os
import subprocess
import sys
import urllib.request

# `--port N` to check a second server without stopping the one you are using.
PORT = 8731
if "--port" in sys.argv:
    PORT = int(sys.argv[sys.argv.index("--port") + 1])
BASE = f"http://127.0.0.1:{PORT}"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "views-check.png")

# Which endpoint fills which view global. `state` feeds the save-backed tabs.
#
# **Every view is drawn twice, empty and populated, because they are different
# code.** A bare `api/deltas` returns the base picker and no rows, so its two
# tables are never built; a populated one draws the tables and never the
# picker, with its search box, its `.hit` buttons and its count. Both halves
# have shipped a ReferenceError, so asking only for the populated one trades
# one blind spot for the other. Where a view has two strings the second is the
# populated call; where it has one, the same payload is drawn in both passes.
PASSES = ("empty", "full")
FEEDS = {
    "latest": ["state"], "logData": ["log"], "ovData": ["overview"],
    "eng": ["engine?all=1"],
    "tradeData": ["market", "market?good=commodity_gold"],
    "routeData": ["routes", "routes?from=li01&to=rh01"],
    "gearData": ["equipment"], "repData": ["reputation"],
    # Trade is a pipeline, and one payload can only be at one stage of it. The
    # stage is what decides the markup, so the two stages the default feed does
    # not reach are seeded separately: the picker, and the by-base end.
    "pickSeed": ["market?by=good"],
    "deltaSeed": ["market?by=base&base=li01_01_base&good=commodity_water"],
}

# What the populated pass must actually have drawn, by view id.
#
# The query strings above name a real base, two real systems and two real
# commodities. If the game data moves under them the endpoint answers 200 with
# an empty `rows`, the view falls back to its picker branch, the table is never
# built and the pass reports `ok` for a page that answers nothing. Naming the
# table each string was chosen to produce is what tells those two apart.
DREW = {
    "engine": ".engine .box",
    "log": ".entry",
    "log:save": ".entry",
    "log:news": ".entry .head",
    "log:rumors": ".entry .said",
    "overview": ".ovpanel",
    "search": ".geartable .gun",
    "market": ".tradetable .gun",
    "market:pick": ".hits .hit",
    "market:base": ".tradetable .gun",
    "routes": ".routetable .gun",
}

# A row is a CSS grid and its cells are plain spans, so a template that emits
# one cell too many does not error: the extra wraps onto a second line and the
# whole table silently reads one column out of step. That shipped on
# 2026-09-06, when a nav map cell was added to four row templates and two of
# the grids were left at their old column count.
#
# **A grid that is meant to wrap says so with `wrapgrid`.** The Overview's
# panels flow into as many columns as fit and its label/value list runs two
# abreast for as long as it needs to, and neither is a row with a fixed set of
# cells. Marking them beats guessing from the computed style, which resolves
# `repeat(auto-fit, ...)` to concrete tracks and so cannot be told apart from a
# hand-written column list.
DRIVER = r"""
const REPORT = [], GRID = [];

// Every grid inside #list, not a list of the row classes somebody remembered.
// `.holdleg` and `.holdtable` were both added by the same commit that wrote
// the old `.gun, .gunhead` check, and neither was covered by it: a check that
// names the rows it knows about cannot see the next row template anybody adds.
// Childless elements are skipped first because a leaf is never a grid row and
// `getComputedStyle` on every span in the gear table is the slow half.
function grids(id) {
  document.querySelectorAll('#list *').forEach(row => {
    if (!row.children.length || row.classList.contains('wrapgrid')) return;
    const st = getComputedStyle(row);
    if (st.display !== 'grid') return;
    const cols = st.gridTemplateColumns.split(' ').length;
    const line = 'GRID  ' + id + '  .' + (row.className || '?')
               + '  cells=' + row.children.length + ' cols=' + cols;
    if (row.children.length !== cols && !GRID.includes(line)) GRID.push(line);
  });
}

// #list is emptied first: render() leaves it untouched when a draw returns
// null, so without this a view that drew nothing would be measured against
// the previous view's markup and pass on it.
// Rows that exist only once something has been clicked. `.holdleg` is drawn
// by expanding a hold row and by nothing else, so a check that never opens one
// can see the template exists and still never measure it.
function expand() {
  if (tradeData && tradeData.hold.systems.length)
    holdSys = tradeData.hold.systems[0].sys;
}

function draw(pass, id, want) {
  tab = id.split(':')[0];
  $('#list').innerHTML = '';
  try { render(); }
  catch (err) { REPORT.push('FAIL  ' + pass + ' ' + id + ': ' + err); return; }
  if (want && !document.querySelector(want))
    REPORT.push('EMPTY ' + pass + ' ' + id + ': nothing matched ' + want);
  else
    REPORT.push('ok    ' + pass + ' ' + id);
  grids(id);
}

// Every name the tab strip can select must be a view that exists.
//
// **The rest of this file could not have caught this.** It walks
// `Object.keys(VIEW)` and draws each one directly, so it never asks what the
// strip would hand it. On 2026-09-09 renaming two tabs left `gear` and `data`
// selectable with nothing registered under either; `render` fell through to an
// empty view, drew nothing, and left the previous tab's panel on screen. Every
// view drew fine. Two of them were simply unreachable.
function reachable() {
  for (const t of TABS) {
    const want = [t.leaf].concat((t.kids || []).map(k => k[0]));
    for (const id of want) {
      if (!id) REPORT.push('FAIL  tab ' + t.label + ' names no leaf at all');
      else if (!VIEW[id])
        REPORT.push('FAIL  tab ' + t.label + ' selects ' + id +
                    ', which no frontend module registers');
    }
  }
}

function sweep(pass, drew) {
  if (!alive()) return;
  reachable();
  try { expand(); } catch (err) { REPORT.push('FAIL  ' + pass + ' expand: ' + err); }
  for (const id of Object.keys(VIEW)) draw(pass, id, drew[id]);
  // The Neural Net's three sources are three separate branches with three
  // separate last-term concatenations, and only the default one is reached by
  // the loop above. All three have to be drawn or two of them are unchecked.
  ['news', 'rumors', 'save'].forEach(src => {
    logSource = src;
    draw(pass, 'log:' + src, drew['log:' + src]);
  });
  // Trade is one pipeline with three stages, and the loop above reaches only
  // whichever one the seeded payload happens to be at. Each stage builds
  // different markup, so each is drawn: the picker, and the destinations
  // reached from a base rather than from a commodity.
  const held = tradeData;
  if (typeof pickSeed !== 'undefined' && pickSeed) {
    // A payload with nothing chosen is what puts the picker on screen. Poking
    // the page's own state instead would only test the poke.
    tradeData = pickSeed; tradeBy = 'good';
    draw(pass, 'market:pick', drew['market:pick']);
  }
  if (typeof deltaSeed !== 'undefined' && deltaSeed) {
    tradeData = deltaSeed; tradeBy = 'base';
    draw(pass, 'market:base', drew['market:base']);
  }
  tradeData = held; tradeBy = 'good';
}

// **The report has to survive the page script being dead.** A SyntaxError in
// the inline script leaves `VIEW`, `$` and every view global undefined, which
// is the single failure this tool exists to catch, and the first version of
// this driver then threw on `Object.keys(VIEW)` before `finish()` could write
// anything. A blank page is not a report.
function alive() {
  if (typeof VIEW !== 'undefined' && typeof $ !== 'undefined') return true;
  REPORT.push('FAIL  the page script did not run at all: ' +
    (typeof $ === 'undefined' ? '`$` is undefined' : '`VIEW` is undefined') +
    '. That is a SyntaxError somewhere in one of the frontend modules; open ' +
    'the page in a browser and read the console for the line.');
  return false;
}

function finish() {
  // The hold table only exists when the save has cargo in it, so say which
  // way that went rather than let a silent pass stand for a check.
  if (typeof tradeData !== 'undefined' && tradeData && !tradeData.hold.items.length)
    REPORT.push('note  this save has an empty hold, so .holdtable never drew');
  const bad = REPORT.filter(r => r[0] === 'F' || r[0] === 'E').length + GRID.length;
  document.body.innerHTML =
    '<pre style="color:#e6edf3;background:#0d1117;font:13px monospace;padding:1rem">'
    + (bad ? bad + ' problem(s)\n\n'
           : 'every view drew twice, every row matches its grid\n\n')
    + REPORT.concat(GRID).join('\n') + '</pre>';
}
"""


def get(path):
    with urllib.request.urlopen(f"{BASE}/{path}", timeout=30) as fh:
        return fh.read().decode("utf-8")


def main():
    try:
        get("api/state")
    except OSError as exc:
        sys.exit(f"no server on {BASE}: {exc}")

    head, rest = get("").split("<script>", 1)
    script = rest.split("</script>", 1)[0]
    # One seed-and-sweep block per pass. A view with a single endpoint is
    # drawn from the same payload both times: that costs one redraw and keeps
    # every view in both columns of the report, which is cheaper than a rule
    # about which views are exempt from which pass.
    runs = []
    for i, name in enumerate(PASSES):
        seed = "\n".join(
            f"{var} = {get('api/' + eps[min(i, len(eps) - 1)])};"
            for var, eps in FEEDS.items())
        runs.append(f"try {{\n{seed}\n}} catch (err) {{ "
                    f"REPORT.push('FAIL  {name} seed: ' + err); }}\n"
                    f"sweep({name!r}, {json.dumps(DREW if i else {})});")

    harness = os.path.join(os.path.dirname(OUT), ".views-check.html")
    with open(harness, "w") as fh:
        fh.write(f"{head}<script>\n{script}\n</script>\n"
                 f"<script>\n{DRIVER}\n" + "\n".join(runs)
                 + "\nfinish();\n</script>\n")

    if os.path.exists(OUT):
        os.remove(OUT)
    # The driver runs before the load event, so what it wrote is on screen by
    # the time the shot is taken. That is the same timing that makes a plain
    # screenshot of the real page useless: it fires before the first fetch.
    subprocess.run(["firefox", "--headless", "--window-size=1000,900",
                    "--screenshot", OUT, f"file://{harness}"],
                   capture_output=True, timeout=180)
    os.remove(harness)
    if not os.path.exists(OUT):
        sys.exit("firefox produced no screenshot")
    print(f"wrote {OUT} - open it; every line should start with 'ok' or 'note'")


if __name__ == "__main__":
    main()
