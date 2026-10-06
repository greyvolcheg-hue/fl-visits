---
type: research
project: computer-geek
status: done
created: 2026-10-06
---

# The page

## Look: `design/Neural Companion.dc.html` is the source

A Claude Design canvas drawn by the owner (2026-09-07): dark HUD, Chakra Petch
over IBM Plex Mono, cyan for the instrument, amber for anything that touches a
file. Overview and Systems are drawn in full; Equipment, Trade, Reputation and
Neural Net as markup; Chart is not covered and uses the same panel, border and
label vocabulary. Read it before changing how anything looks.

- Its values live in `frontend/_theme.css` as tokens and nowhere else.
- The canvas emits inline styles; the page uses classes. Do not port a
  `style="..."`. A tab's own selectors live in its module, not in the theme: both
  grid-column bugs shipped so far were a row template and its column list
  drifting apart in two files.
- Three deliberate departures, because every engine control writes into a live
  game: a slider posts on release, a redraw waits while a slider is under a
  thumb, and the two expensive readings behind `ALL KNOBS` are fetched only when
  it is open. `frontend/engine.py` says so at the top.
- The canvas draws the engine controls as a strip on every page. That was built
  and reverted on 2026-09-07: it polled process memory every five seconds from
  every tab, and was rebuilt on every tick, which swallowed clicks (below). A tab
  polls only while open, and each setting shows in one place.
- `check_views.py` skips grids marked `wrapgrid`, the ones meant to wrap
  (Overview's panel flow and its label/value list). The computed style cannot
  tell them apart: `repeat(auto-fit, ...)` resolves to concrete tracks.

## One inline script: a parse error kills the whole page

The UI is one `<script>` in `PAGE`, so a syntax error leaves static HTML, a stuck
"loading…" and no tabs, while curl gets 200 and the API answers. 2026-09-04:
`let top = 'map'`; `window.top` is non-configurable, so a global `let` or `const`
on that name is a SyntaxError (also `window`, `self`, `location`, `document`).
The variable is `topTab`.

- **Verify in a browser.** `firefox --headless --screenshot` shows whether the tab
  strip drew. The shot fires at the load event, before the first `fetch`
  resolves, so an empty body proves nothing.
- `check_views.py` checks `$` and `VIEW` before anything else and says so in
  words; the seeding runs in its own try. On 2026-09-07 an unclosed template
  literal in `frontend/log.py` killed the script, the driver's
  `Object.keys(VIEW)` threw, and the report came out blank.

## The poll compares, never rebuilds

`render()` runs on a five-second poll. It used to assign `innerHTML` every tick
though the markup was byte-identical (1389 characters for the engine strip).
That destroys every child, and a browser fires `click` only when press and
release land on the same element, so a click straddling a tick did nothing,
silently, on every button of every tab. Proved headless: press, one `render()`,
release, and `#engmore` is a different object. (Reported 2026-09-07: `ALL KNOBS`
"opened once and then stopped opening".)

- **`paint(node, html)` in `frontend/shell.py` writes only when the html changed.
  It is not an optimisation; never remove it as one.** Handlers survive because
  their elements do; focus, selection and scroll survive too.
- **`paint` compares with the last string it wrote**, kept in a `WeakMap` keyed
  on the node, never with `node.innerHTML`, which returns the browser's own
  serialisation: `selected` comes back as `selected=""`, `hidden` as
  `hidden=""`, a U+00A0 as `&nbsp;`. Comparing with `innerHTML` left four of the
  nine views (`search`, `rep`, `systems`, `log`) rebuilt on every tick for three
  days, closing open `<select>`s and dropping focus and half-typed text (reported
  2026-09-10). Do not try to fix this by writing markup the browser echoes back.
- Anything that empties a painted node by hand goes through `clear(node)`, or the
  next real write is skipped. `check_views.py` is the one caller.
- `check_views.py` measures the invariant by identity: render a view twice with
  the same data, and no node may be replaced. With the old comparison put back it
  printed 12 `POLL` lines naming `systems`, `search`, `rep` and the two log views
  with rumors.

## Marks live on the server

On 2026-09-09 the owner's read marks vanished overnight. `localStorage` is scoped
to a browsing context: the marks were made in a Zen workspace container
(`userContextId=1`, 75 marks), the next day's tab was plain (`userContextId=0`,
20 marks). Every key regenerated identically; there were two stores. `run.sh`
ended in `xdg-open`, which always opens a plain tab.

- Marks live in `data/marks.json`, written through a temp file and
  `os.replace` under one lock (`serve.py` is threaded). A missing or unreadable
  file reads as no marks.
- **`merge_marks` unions and never deletes**, so any old browser store can still
  contribute.
- **The page is a cache.** A toggle applies locally, then posts; a `marksHeld`
  timestamp stops the poll returning a payload older than the write (the same
  guard as the slider under a thumb). The Equipment tab registers no poll and
  needs no guard; the code says so.
- `localStorage` is not cleared: it is the fallback if the file is lost.
- Favourite guns live in the same file under `fav`, keyed by the bare item
  nickname, unique across guns and shields (314 rows, 314 nicknames).

## The header names the save

`api/state` carries `save_path` and `save_dir`; the save name in the header is a
button that shows the folder and hands it to the file manager (2026-09-12). The
save sits six levels down a Wine prefix, in one of several accounts, picked by
mtime at startup:

    ~/Games/freelancer-win32/drive_c/users/<account>/Documents/My Games/
    Freelancer/Accts/SinglePlayer/AutoSave.fl

- **`api/reveal` takes no argument**: it opens only the folder this process chose.
  An endpoint opening a path the browser sends would open arbitrary folders on
  request.
- The opener is spawned and never awaited, so "opened" means asked; a stuck
  handler cannot hang the POST. The path is printed beside the answer.
  `xdg-open`, `os.startfile` and `open` live in one function in `common.py`.

## Layout: size from the box, not the window

Systems lays a house out two cards abreast. `@media (min-width: 1400px)` never
fired for the owner: a browser sidebar takes about 600px, so the page sat near
1396 CSS px. Now (2026-09-10):

    grid-template-columns: repeat(auto-fit, minmax(max(34rem, 48%), 1fr));

`48%` caps it at two; `34rem` is the floor below which it drops to one column.
Measured: one column at 900 and 1100, two from about 1130px of page width (two at
1256, 1396, 1500 and 1920), never three. A media query measures the window, and `.wrap` (capped at 1680), the
sidebar and the panel all sit between the window and the box. `.totals` and
`.hits` already work this way.

## Equipment tab

- **"Only bases I have docked at" drops rows** (2026-09-10, reversing the earlier
  design, which kept every row with an empty dealer list). The owner called that
  useless: it left 187 of 235 guns on screen with nothing under them. Against a
  save with 30 docked bases: guns 235 -> 51, shields 79 -> 36. It is a filter kind
  inside `eqp.search`; `search.py` then narrows each surviving row's `bases` to
  docked dealers and can no longer empty a row.
- **A favourite bypasses every filter.** `eqp.search` takes `keep`, checked
  before the filters and carried through the same sort, so a favourite sits in
  the ranking, not on top of it. Starring the weakest gun and asking for
  `hull_dps >= 100` returns 226 rows instead of 225, that gun last.
- **Every column shows; a `×` on a heading drops one.** All on, guns need 1335px
  and shields 1244px; below about 1350px the table scrolls inside its `.guns` box.
  A dropped column brings up a `+ add a column…` select beside
  `+ add a parameter…`. `gearHidden` holds the exceptions, so a parameter added
  later appears without being named. A column you sort or filter on carries no
  `×`. Dropping and restoring ask the server nothing; cells stay in step with the
  grid at 12, 9 and 10 columns. `price` has its own column and is not a
  parameter column.
- **Rank needed is a comparison**: `rank` is `cmp` in `PARAMETERS`, drawing the
  `[= <= >=]` select the mount class uses. Other numeric parameters stay a plain
  minimum. Both comparisons are inclusive; `>=` on a number is `num`, which every
  numeric filter sends, so there is no `over` kind; `<=` is `upto`. `le` and `ge` compare mount classes
  and refuse across socket families (a shield's `fighter 6` and `elite 6` differ);
  they are not the numeric pair.

  | | `=` | `<=` | `>=` |
  |---|---|---|---|
  | rank 16, guns | 51 | 160 (109 + 51) | 126 (75 + 51) |
  | mount 6, guns | 51 | 145 (94 + 51) | 141 (90 + 51) |
  | mount `fighter 6`, shields | 3 | 18 | 11 |

  The shield rows are all `fighter`, none `elite` or `freighter`: the family
  rule holding. 126 is what `num 16` gave before, so `>=` is that filter, not a
  copy of it.

# Starting the server

`serve.py` binds the port before it loads anything; if the port is taken it names
the port, prints the command that frees it and exits 1. `run.sh` is three lines
around `serve.py --open`; `run.cmd` is the same for Windows.

On 2026-09-12 the old `run.sh` started a second server, which died on `bind`
while its wait loop connected to the old one on the first try and opened a
browser on an hour-old server: the new tab seemed missing. A script probe
(`/dev/tcp`) only guesses whether the server bound; `serve.py` knows.

- `exec` with only redirections applies them to the rest of the script:
  `exec 3<&- 2>/dev/null` silenced every later message
  (`bash -c 'exec 3<&- 2>/dev/null; echo hi >&2'` prints nothing).
- **`allow_reuse_address` differs by platform.** `HTTPServer` sets it. On Linux
  it binds over a socket in TIME_WAIT, so a restart after Ctrl+C works. On Windows
  `SO_REUSEADDR` lets a second program bind a port another is listening on. So
  `serve.py` keeps the flag on Linux and turns it off on Windows.
