"""The frame every view sits in: tab strip, shared helpers, render, poll.

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
"""

CSS = open(__file__.replace("shell.py", "_css.txt")).read()

JS = r"""
// Where you were inside each parent, so coming back to Map does not always
// dump you on Visits.
const leaf = { map: 'visits', gear: 'dps', trade: 'data' };
// `topTab`, not `top`: `window.top` is non-configurable, so a global `let top`
// is a SyntaxError that kills the whole script before a line of it runs.
let topTab = 'map', tab = 'visits', latest = null;

// Per tab, not per page: what you want expanded on Visits has nothing to do
// with Wrecks, and "finished" means something different on each.
const extended = { visits: true, wrecks: true };
const hideDone = { visits: true, wrecks: true };
const collapsed = { visits: {}, wrecks: {} };
// Fold everything, but once per tab. On every render the five-second poll
// would re-fold whatever you just opened.
const folded = { visits: false, wrecks: false };

function foldOnFirstSight(d) {
  if (folded[tab] || !d || !d.house_order) return;
  folded[tab] = true;
  d.house_order.forEach(h => { collapsed[tab][h] = true; });
}

function esc(s) { return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
const money = v => v.toLocaleString();

function totals(pairs) {
  $('#totals').innerHTML = pairs
    .map(([n, l]) => `<div><span class="n">${n}</span><span class="lbl">${l}</span></div>`).join('');
}

function card(title, done, total, percent, body) {
  return `<div class="sys">
    <div class="head"><b>${esc(title)}</b><span class="count">${done} / ${total}</span></div>
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
    // Only a grouped heading carries data-house; Speed reuses the look for
    // Cruise and Thrusters and must stay unfoldable.
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

function render() {
  const v = VIEW[tab] || {};
  $('#totals').hidden = !!v.bare;
  $('#togglewrap').hidden = !!v.bare;
  $('#wrap').classList.toggle('chart', tab === 'chart');
  if (v.sub) $('#sub').textContent = v.sub;
  else if (latest) $('#sub').textContent =
    `${latest.save} · updated ${new Date(latest.saved_at * 1000).toLocaleTimeString()}`;
  if (v.save && !latest) return;
  if (v.draw) {
    const html = v.draw(latest);
    if (html !== null) $('#list').innerHTML = html;
  }
  if (v.wire) v.wire();
}

// Only the open tab is polled. Locating a value in the game means scanning
// some 440 MiB of process memory, so refreshing a panel nobody is looking at
// would burn real CPU.
async function poll() {
  try {
    const r = await fetch('api/state', { cache: 'no-store' });
    if (r.ok) latest = await r.json();
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
