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
of hiding the rest. The report is written into the page and photographed,
because a headless browser has no other way to tell you anything.

Needs `firefox` and a running server.
"""

import os
import subprocess
import sys
import urllib.request

BASE = "http://127.0.0.1:8731"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "views-check.png")

# Which endpoint fills which view global. `state` feeds the save-backed tabs.
#
# **Ask for a populated table, not an empty one.** A bare `api/deltas` returns
# the base picker and no rows, so its two tables are never built and anything
# wrong with them is invisible. The query strings below exist to make every
# table draw at least one row.
FEEDS = {
    "latest": "state", "speed": "speed", "thrusters": "thrusters",
    "lane": "tradelane", "draw": "drawdist", "best": "bestpath",
    "tradeData": "trade?good=commodity_gold",
    "deltaData": "deltas?base=li01_01_base&good=commodity_water",
    "routeData": "routes?from=li01&to=rh01",
    "gearData": "equipment", "repData": "reputation",
}

# A row is a CSS grid and its cells are plain spans, so a template that emits
# one cell too many does not error: the extra wraps onto a second line and the
# whole table silently reads one column out of step. That shipped on
# 2026-09-06, when a nav map cell was added to four row templates and two of
# the grids were left at their old column count.
DRIVER = """
const REPORT = [], GRID = [];
for (const id of Object.keys(VIEW)) {
  tab = id;
  try { render(); REPORT.push('ok    ' + id); }
  catch (err) { REPORT.push('FAIL  ' + id + ': ' + err); continue; }
  document.querySelectorAll('.gun, .gunhead').forEach(row => {
    const cols = getComputedStyle(row).gridTemplateColumns.split(' ').length;
    const line = 'GRID  ' + id + '  .' + (row.parentElement.className || '?')
               + '  cells=' + row.children.length + ' cols=' + cols;
    if (row.children.length !== cols && !GRID.includes(line)) GRID.push(line);
  });
}
const bad = REPORT.filter(r => r[0] === 'F').length + GRID.length;
document.body.innerHTML =
  '<pre style="color:#e6edf3;background:#0d1117;font:15px monospace;padding:1rem">'
  + (bad ? bad + ' problem(s)\\n\\n' : 'all views drew, every row matches its grid\\n\\n')
  + REPORT.concat(GRID).join('\\n') + '</pre>';
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
    seed = "\n".join(f"{var} = {get('api/' + ep)};" for var, ep in FEEDS.items())

    harness = os.path.join(os.path.dirname(OUT), ".views-check.html")
    with open(harness, "w") as fh:
        fh.write(f"{head}<script>\n{script}\n</script>\n"
                 f"<script>\n{seed}\n{DRIVER}\n</script>\n")

    if os.path.exists(OUT):
        os.remove(OUT)
    # The driver runs before the load event, so what it wrote is on screen by
    # the time the shot is taken. That is the same timing that makes a plain
    # screenshot of the real page useless: it fires before the first fetch.
    subprocess.run(["firefox", "--headless", "--window-size=1000,700",
                    "--screenshot", OUT, f"file://{harness}"],
                   capture_output=True, timeout=180)
    os.remove(harness)
    if not os.path.exists(OUT):
        sys.exit("firefox produced no screenshot")
    print(f"wrote {OUT} - open it; every line should start with 'ok'")


if __name__ == "__main__":
    main()
