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
const leaf = { map: 'systems', gear: 'dps', trade: 'data' };
// `topTab`, not `top`: `window.top` is non-configurable, so a global `let top`
// is a SyntaxError that kills the whole script before a line of it runs.
let topTab = 'overview', tab = 'overview', latest = null, polledAt = null;

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
  if (s < 90) return Math.max(0, Math.round(s)) + 's ago';
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
function paint(node, html) {
  if (node.innerHTML === html) return false;
  node.innerHTML = html;
  return true;
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
function byHouse(d, rows, renderRow, tally) {
  const bucket = {};
  rows.forEach(r => (bucket[r.house] = bucket[r.house] || []).push(r));
  const shut = collapsed[tab] || {};
  return (d.house_order || []).filter(h => bucket[h]).map(h => {
    const rs = bucket[h], [done, total] = tally(rs), off = !!shut[h];
    // Only a grouped heading carries data-house; anything reusing the look
    // must stay unfoldable.
    return `<h2 class="house" data-house="${esc(h)}">` +
           `<span class="caret">${off ? '▸' : '▾'}</span>${esc(h)}` +
           `<span class="hcount">${done} / ${total}</span></h2>` +
           `<div class="housebody"${off ? ' hidden' : ''}>` +
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
  // A parent with no children is its own leaf, so the plain tabs need no case.
  tab = entry.kids ? (child || leaf[topTab] || entry.kids[0][0]) : topTab;
  if (entry.kids) leaf[topTab] = tab;
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
  paint($('#status'),
    `<span class="dot${cold ? ' cold' : ''}"></span>` +
    (cold ? '<span>no save read yet</span>'
          : `<span class="file">${esc(latest.save)}</span>` +
            `<span class="sep">|</span><span>saved ${ago(latest.saved_at)}</span>`) +
    (polledAt ? `<span class="sep">|</span><span>polled ${ago(polledAt)}</span>` : ''));
}

function render() {
  const v = VIEW[tab] || {};
  $('#totals').hidden = !!v.bare;
  $('#togglewrap').hidden = !!v.bare;
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
