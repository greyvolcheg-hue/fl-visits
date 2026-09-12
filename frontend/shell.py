"""The frame every view sits in: top bar, tabs, render, poll.

Views register themselves into `VIEW`:

    VIEW.routes = {
      sub:  subtitle line,
      bare: true to hide the totals row and the two checkboxes,
      save: true to wait for the save before drawing,
      draw: d => html,   returning null to leave the panel alone,
      wire: () => {},    after the html lands,
      open: () => {},    when the tab is entered,
      poll: async () => {},  on the five-second tick, only while open,
    }

`render` and `poll` then have no idea what a tab is. They used to: `render`
was a 133-line chain of `if (tab === ...)` that repeated the same four steps
per view.

**Only the open tab is polled**, including the Engine tab. Reading the running
game means scanning process memory, so a panel nobody is looking at must not
cost anything. The engine controls were a strip above the tab row for a few
hours on 2026-09-07 and that is exactly what went wrong with it: it polled the
game from every page, and it was rebuilt on every tick whatever you were
reading.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
CSS = (open(os.path.join(HERE, "_theme.css")).read()
       + open(os.path.join(HERE, "_shell.css")).read())

JS = r"""
// Where you were inside each parent, so coming back to Map does not always
// dump you on Systems.
// Which child of each parent you were last on, so coming back lands where you
// left. **Seeded empty on purpose.** It used to be written out as
// `{ map: 'systems', gear: 'dps', trade: 'data' }`, which was a second copy of
// the site map living outside `tabs.py`: every one of those values was simply
// the parent's first child, so the literal bought nothing and went stale the
// moment a tab was renamed. It did, twice in one commit, and both tabs then
// opened the panel that was there before.
const leaf = {};
// `topTab`, not `top`: `window.top` is non-configurable, so a global `let top`
// is a SyntaxError that kills the whole script before a line of it runs.
let topTab = 'overview', tab = 'overview', latest = null, polledAt = null;
// Whether the header is showing where the save actually is, and what the
// server last said when asked to open that folder. Folded away by default:
// the path is six levels deep and belongs on screen when asked for, not
// across the top of every tab. The note survives a fold, because a failure
// has to stay readable: `xdg-open` is spawned and never waited for, so
// "opened" means asked rather than "a window appeared".
let showPath = false, pathNote = '';

// Per tab, not per page: what you want expanded on Systems has nothing to do
// with anywhere else, and "finished" means something different on each.
const extended = { systems: true };
const hideDone = { systems: true };
const collapsed = { systems: {} };
// Fold everything, but once per tab. On every render the five-second poll
// would re-fold whatever you just opened.
const folded = { systems: false };

function foldOnFirstSight(d) {
  if (folded[tab] || !d || !d.house_order) return;
  folded[tab] = true;
  d.house_order.forEach(h => { collapsed[tab][h] = true; });
}

function esc(s) { return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
const money = v => v.toLocaleString();

// How long ago, in words. Used by the top bar and by the hold panel, which is
// where it was until the top bar wanted the same sentence.
function ago(t) {
  const s = Date.now() / 1000 - t;
  // **One definition, and it took a while to be one.** `trade.py` carried a
  // second copy of this function, differing only in this line, and a function
  // declaration silently replaces an earlier one: the copy was answering for
  // the top bar too, so the header read "polled just now" while the code that
  // claims to own it said "3s ago". Kept the wording that was actually on
  // screen; the point is that there is now one place to change it.
  if (s < 90) return 'just now';
  if (s < 5400) return Math.round(s / 60) + ' min ago';
  return Math.round(s / 3600) + ' h ago';
}

// Write html into a node only when it differs from what is already there, and
// say whether anything was written.
//
// **This is not an optimisation.** Assigning `innerHTML` destroys and rebuilds
// every child, and a browser only fires `click` when the press and the release
// land on the same element. The five-second poll was rewriting the engine strip
// and the whole panel with byte-identical markup on every tick, so any click
// whose press and release straddled a tick was swallowed with no error and no
// trace: the ALL KNOBS button "worked once and then stopped". Text selection,
// focus and scroll position went the same way.
//
// Proved rather than guessed, in a headless browser: press the button, run a
// poll, release it, and the release lands on a different element.
//
// **What it compares against is the whole trick, and the first version got it
// wrong.** It read `node.innerHTML` back and compared that, which does not work
// and cannot: the browser hands back its own serialisation, not the string it
// was given. Measured on 2026-09-10, per view:
//
//     search  wrote <option value="guns" selected>   read back  selected=""
//     rep     the same
//     systems wrote <div class="housebody" hidden>   read back  hidden=""
//     log     a U+00A0 inside a rumor, written raw   read back  &nbsp;
//
// A bare boolean attribute comes back with `=""` and a character the serialiser
// prefers as an entity comes back as one, so those four panels never matched
// and were destroyed and rebuilt on **every five-second tick**. That is what
// shut a `<select>` under the cursor and took the focus out of the Equipment
// search box, which read as a browser fault and was ours. Writing the markup
// more carefully does not fix it; the comparison itself was the bug.
//
// So the last html written is remembered here, where it is exactly the string
// that went in. Cheaper too: reading `innerHTML` on a 700-row table serialised
// the whole subtree once a tick to answer a question about a string.
const painted = new WeakMap();

function paint(node, html) {
  if (painted.get(node) === html) return false;
  node.innerHTML = html;
  painted.set(node, html);
  return true;
}

// Empty a node **and forget what it held**, so the next paint really writes.
// Anything that clears a painted node by hand has to come through here or the
// record says it still holds markup that is no longer on screen.
// `check_views.py` is the one caller: it blanks the panel between views so a
// view that draws nothing is not measured against the previous one's markup.
function clear(node) {
  node.innerHTML = '';
  painted.delete(node);
}

function totals(pairs) {
  paint($('#totals'), pairs
    .map(([n, l]) => `<div><span class="n">${n}</span><span class="lbl">${l}</span></div>`).join(''));
}

// `fold` is optional: {id, open} makes the card a fold with a caret and a
// data-sys handle. Anything reusing this look and passing nothing stays open
// and unclickable.
function card(title, done, total, percent, body, fold) {
  const shell = fold ? `class="sys foldable" data-sys="${esc(fold.id)}"` : 'class="sys"';
  const caret = fold ? `<span class="caret">${fold.open ? '▾' : '▸'}</span>` : '';
  return `<div ${shell}>
    <div class="head">${caret}<b>${esc(title)}</b><span class="count">${done} / ${total}</span></div>
    <div class="bar"><i style="width:${percent}%"></i></div>${body}</div>`;
}

// Rows arrive in the order the server chose and grouping must not disturb it.
// A house with nothing under the current checkbox is dropped, not left empty.
//
// **`shown` and `every` are two different questions and used to be one
// argument.** `shown` survived the page's filters and is what gets drawn;
// `every` is the whole house and is what the heading counts. Counting the
// filtered list made a heading answer "what am I looking at", which is the one
// thing the screen already says. With finished systems hidden, Bretonia read
// `3 / 4` while the house was really `38 / 39`: a house three objects from
// complete, drawn as one barely started. Reported 2026-09-12.
//
// `every` is optional, so a caller with nothing to filter passes one list and
// gets the old behaviour, which is then the correct one.
function byHouse(d, shown, renderRow, tally, every) {
  const bucket = {}, whole = {};
  shown.forEach(r => (bucket[r.house] = bucket[r.house] || []).push(r));
  (every || shown).forEach(r => (whole[r.house] = whole[r.house] || []).push(r));
  const shut = collapsed[tab] || {};
  return (d.house_order || []).filter(h => bucket[h]).map(h => {
    const rs = bucket[h], [done, total] = tally(whole[h]), off = !!shut[h];
    // Only a grouped heading carries data-house; anything reusing the look
    // must stay unfoldable.
    return `<h2 class="house" data-house="${esc(h)}">` +
           `<span class="caret">${off ? '▸' : '▾'}</span>${esc(h)}` +
           `<span class="hcount">${done} / ${total}</span></h2>` +
           // `wrapgrid`: on a wide screen this is a two-column layout grid
           // holding however many systems the house has, not a table row whose
           // cell count must match its columns. check_views.py says why the
           // difference cannot be read off the computed style.
           `<div class="housebody wrapgrid"${off ? ' hidden' : ''}>` +
           rs.map(renderRow).join('') + `</div>`;
  }).join('');
}

function drawTabs() {
  $('#tabs').innerHTML = TABS.map(t =>
    `<button class="tab${t.id === topTab ? ' on' : ''}" data-top="${t.id}">` +
    `${t.label}</button>`).join('');
  const kids = (TABS.find(t => t.id === topTab) || {}).kids;
  const bar = $('#subtabs');
  bar.hidden = !kids;
  bar.innerHTML = !kids ? '' : kids.map(([id, label]) =>
    `<button class="tab${id === tab ? ' on' : ''}" data-leaf="${id}">` +
    `${label}</button>`).join('');
  $('#tabs').querySelectorAll('.tab').forEach(b =>
    b.addEventListener('click', () => go(b.dataset.top)));
  bar.querySelectorAll('.tab').forEach(b =>
    b.addEventListener('click', () => go(topTab, b.dataset.leaf)));
}

function go(parent, child) {
  topTab = parent;
  const entry = TABS.find(t => t.id === topTab) || {};
  // `entry.leaf` is what `tabs.py` says this parent opens on, and every parent
  // has one, so there is no case here for a parent with no second row.
  tab = child || leaf[topTab] || entry.leaf;
  leaf[topTab] = tab;
  drawTabs();
  $('#ext').checked = !!extended[tab];
  $('#hidedone').checked = !!hideDone[tab];
  render();
  const v = VIEW[tab];
  if (v && v.open) v.open();
}

// The save this page is following, and how fresh what you are looking at is.
// Two different ages and both matter: the save is written by the game when it
// feels like it, the poll is us.
function drawStatus() {
  const cold = !latest;
  // The name is a button: the server is the only party that knows which file
  // out of which Wine prefix is being followed, and until this it kept it to
  // itself. Open, it shows the folder and offers to walk you there.
  paint($('#status'),
    `<span class="dot${cold ? ' cold' : ''}"></span>` +
    (cold ? '<span>no save read yet</span>'
          : `<button class="file" id="savename" title="where is this file?">` +
            `${esc(latest.save)}</button>` +
            `<span class="sep">|</span><span>saved ${ago(latest.saved_at)}</span>`) +
    (polledAt ? `<span class="sep">|</span><span>polled ${ago(polledAt)}</span>` : '') +
    (showPath && latest
      ? `<span class="savepath"><span class="dir">${esc(latest.save_dir)}</span>` +
        `<button class="openat" id="openat">OPEN FOLDER</button>` +
        (pathNote ? `<span class="said">${esc(pathNote)}</span>` : '') + '</span>'
      : ''));
}

// Delegated on the header, not bound in `drawStatus`: the poll repaints this
// node every five seconds and a handler bound to the button would go with it.
$('#status').addEventListener('click', async e => {
  if (e.target.closest('#savename')) { showPath = !showPath; pathNote = ''; drawStatus(); return; }
  if (!e.target.closest('#openat')) return;
  try {
    const r = await fetch('api/reveal', { method: 'POST', body: '{}' });
    const d = await r.json();
    // On success the folder is already on the line above, so the server's
    // `opened <path>` would print it twice. A failure keeps every word of it.
    pathNote = d.ok ? 'opened' : (d.message || 'nothing happened');
  } catch (err) { pathNote = 'the server did not answer'; }
  drawStatus();
});

function render() {
  const v = VIEW[tab];
  // **A tab with no view must say so.** Falling through to `{}` here draws
  // nothing, and drawing nothing leaves the previous tab's panel on screen: the
  // page then looks like it ignored the click rather than like it broke. That
  // is how a stale leaf id hid for a whole commit.
  if (!v) {
    $('#statusrow').hidden = true;
    drawStatus();
    paint($('#list'),
      `<p class="note warn">No view is registered as <code>${esc(tab)}</code>. ` +
      'That is a name in <code>tabs.py</code> that no <code>frontend</code> ' +
      'module answers to.</p>');
    return;
  }
  // The numbers and the controls are one panel now, so there is one thing to
  // hide. They were only ever shown and hidden together.
  $('#statusrow').hidden = !!v.bare;
  $('#wrap').classList.toggle('chart', tab === 'chart');
  $('#sub').textContent = v.sub || 'SIRIUS SECTOR / FL-VISITS';
  drawStatus();
  if (v.save && !latest) return;
  if (v.draw) {
    const html = v.draw(latest);
    // A draw returning null means "leave the panel alone"; identical markup
    // means the same thing and must not cost the panel its event handlers.
    if (html !== null && !paint($('#list'), html)) return;
  }
  if (v.wire) v.wire();
}

// Only the open tab is polled. Locating a value in the game means scanning
// some 440 MiB of process memory, so refreshing a panel nobody is looking at
// would burn real CPU. Nothing is exempt from that, the Engine tab included.
async function poll() {
  try {
    const r = await fetch('api/state', { cache: 'no-store' });
    if (r.ok) { latest = await r.json(); polledAt = Date.now() / 1000; }
  } catch (e) { /* server gone; keep the last good state */ }
  const v = VIEW[tab];
  if (v && v.poll) { try { await v.poll(); } catch (e) {} }
  render();
}

// Delegated: render() replaces the list wholesale, so a handler bound to a
// heading would not survive the next poll.
$('#list').addEventListener('click', e => {
  const head = e.target.closest('h2.house[data-house]');
  if (!head) return;
  const state = collapsed[tab] || (collapsed[tab] = {});
  state[head.dataset.house] = !state[head.dataset.house];
  render();
});

function foldAll(shut) {
  if (!latest) return;
  folded[tab] = true;  // the owner has decided; stop opening on our own
  collapsed[tab] = {};
  if (shut) (latest.house_order || []).forEach(h => { collapsed[tab][h] = true; });
  render();
}
$('#collapseall').addEventListener('click', () => foldAll(true));
$('#expandall').addEventListener('click', () => foldAll(false));
$('#ext').addEventListener('change', e => { extended[tab] = e.target.checked; render(); });
$('#hidedone').addEventListener('change', e => { hideDone[tab] = e.target.checked; render(); });
"""

BOOT = """
drawTabs();
poll();
setInterval(poll, 5000);
"""
