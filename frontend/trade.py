"""Trade → Market: one question, asked from whichever end you know.

The endpoint is in `backend/trade.py`, and it says why these are one thing.

**One picker and one table, not two screens behind a switch.** The first merge
of Data and Deltas kept both renderers and put a mode button over them, which
is the same two pages with an extra click. This is the pipeline instead:

    axis  ->  pick a commodity            ->  every base that trades it
    axis  ->  pick a base -> its shelf    ->  every base that trades it,
                                              measured against what you pay

The last stage is one function on both paths, and so is the widget you choose
with. `pickList` draws commodities and bases from the same row shape, because
the two lists differ in what a row says and never in how you search it. Two
search widgets for one job was the actual duplication, and it outlived the two
tabs it came from.
"""

ID, LABEL = "market", "Market"

CSS = """
  /* The axis switch. Layout only: the look comes from the one button rule in
     `_theme.css`, which `.modebar button` is named in, so these read as the
     same control as COLLAPSE ALL. */
  .modebar { display: flex; gap: .4rem; margin: 0 0 .9rem; }

  /* One picker, for commodities and for bases alike. */
  .pickbox { background: var(--panel); border: 1px solid var(--line);
             clip-path: var(--notch); padding: .7rem 1rem; margin-bottom: .7rem; }
  .pickbox .row { display: flex; align-items: center; gap: .6rem;
                  flex-wrap: wrap; }
  .pickbox input[type=search] { flex: 1 1 18rem; }
  .hits { display: grid; gap: .25rem; margin-top: .6rem;
          grid-template-columns: repeat(auto-fill, minmax(20rem, 1fr)); }
  .hits .hit { display: grid; align-items: baseline; gap: .5rem;
               grid-template-columns: minmax(7rem, 1fr) minmax(4rem, .9fr)
                                      3.2rem 4rem;
               text-align: left; }
  .hits .hit .num.up { color: var(--ok); }

  /* What you picked, kept on screen: everything under it is read against it. */
  .pick { display: flex; align-items: baseline; gap: .7rem; flex-wrap: wrap;
          background: var(--panel); border: 1px solid var(--line);
          border-left: 2px solid var(--docked);
          padding: .55rem 1rem; margin-bottom: .7rem; }
  .pick .sys { color: var(--faint); font-family: var(--mono); font-size: 11px; }
  .pick .addgun { margin-left: auto; }

  /* The destinations table. One vocabulary whichever way you got here; the
     gain column is simply absent when there is no base to measure from. */
  .tradetable { min-width: 40rem; }
  .tradetable .gun, .tradetable .gunhead {
    grid-template-columns: 5rem 4.5rem minmax(12rem, 1fr) minmax(8rem, 1fr) 5rem; }
  .tradetable.plain .gun, .tradetable.plain .gunhead {
    grid-template-columns: 5rem minmax(12rem, 1fr) minmax(8rem, 1fr) 5rem; }
  .tradetable .gunhead span:first-child { text-align: right; }
  /* Green edge means the shelf has it: the only rows you can buy at. */
  .traderow.sells { border-color: rgba(95, 224, 160, .45); }

  .holdbar { display: flex; align-items: baseline; flex-wrap: wrap; gap: .6rem;
             background: var(--panel); border: 1px solid var(--line);
             clip-path: var(--notch); padding: .6rem 1rem; margin: 0 0 .8rem; }
  .holdbar .when { color: var(--faint); font-family: var(--mono);
                   font-size: 10.5px; margin-left: auto; }
  .holdtable { min-width: 40rem; }
  .holdtable .gun, .holdtable .gunhead {
    grid-template-columns: minmax(10rem, 1fr) 6rem 3.5rem 6rem minmax(8rem, 1fr); }
  .holdrow { cursor: pointer; }
  .holdrow.on { border-color: var(--docked); }
  /* Same grid as the row above it minus the system, so the figures line up
     under the total they add to. */
  .holdleg { display: grid; align-items: baseline; gap: .9rem;
             grid-template-columns: minmax(8rem, 1fr) 7rem 6rem
                                    minmax(8rem, 1fr) 5rem;
             font-size: 11.5px; }
"""

JS = r"""
// The axis: 'good' or 'base'. Which end of the question you happen to know.
let tradeBy = 'good';
// One selection, whichever axis found it. `tradeBase` stays set across a
// switch back, so returning to the base you were standing on costs no typing.
let tradeGood = '', tradeBase = '';
// Just the search text. **It used to decide what was on screen as well**, and
// that made "change" after picking a commodity reopen the base picker instead
// of the shelf, because one flag cannot say which of two pickers to reopen.
// Clearing the value is what reopens its own picker now.
let tradeQuery = '';
let tradeData = null, tradeVisitedOnly = false, holdSys = '';

// One system's breakdown: which base takes which part of the load, and what
// staying on a single dock would cost.
function holdLegs(s) {
  return '<div class="gearwhere">' +
    s.goods.map(g =>
      `<div class="holdleg"><span class="nm">${esc(g.name)}</span>` +
      `<span class="num raw">${g.units} × ${money(g.price)}</span>` +
      `<span class="num h">${money(g.value)}</span>` +
      `<span class="nm">${esc(g.base.name)}</span>` +
      `<span class="cell">${esc(g.base.at)}</span></div>`).join('') +
    (s.one && s.bases > 1
      ? `<p class="note">Or ${money(s.one.total)} at ${esc(s.one.base.name)} on
         its own: ${money(s.total - s.one.total)} less, and one stop instead of
         ${s.bases}.</p>`
      : '') + '</div>';
}

function renderHold(h) {
  if (!h.items.length) return '';
  const load = h.items.map(i => `${i.units} ${esc(i.name)}`).join(' · ');
  let out = '<div class="holdbar"><b>In the hold:</b> ' + load +
    `<span class="when">from the save, ${ago(h.saved)}</span>` +
    '<button id="holdagain">re-read</button></div>';
  if (!h.systems.length)
    return out + '<p class="note">Nowhere buys any of it.</p>';

  // When nothing takes the lot, the systems taking most of it are the answer,
  // so the table shows those instead of nothing.
  const whole = h.systems.filter(s => !s.missing.length);
  const shown = whole.length ? whole : h.systems;
  // `h.whole` counts every system that takes the lot; `shown` is the ten that
  // fit. Counting the array here would only ever be able to say ten.
  const more = h.whole > shown.length ? `, best ${shown.length} shown` : '';
  out += '<p class="note">' + (h.whole
    ? `${h.whole} system${h.whole > 1 ? 's take' : ' takes'} the whole
       load${more}. <b>total</b> is what it all fetches there, <b>stops</b> is
       how many bases that means, and <b>one base</b> is the best you can do
       without undocking twice. Click a row for the breakdown.`
    : 'Nothing takes the whole load. These take the most of it.') + '</p>';

  out += '<div class="guns"><div class="holdtable">' +
    '<div class="gunhead"><span class="nm">system</span><span>total</span>' +
    '<span>stops</span><span>one base</span>' +
    '<span class="nm">not taken here</span></div>' +
    shown.map(s => {
      const open = s.sys === holdSys;
      return `<div class="gun holdrow${open ? ' on' : ''}" ` +
        `data-hold="${esc(s.sys)}">` +
        `<span class="nm">${esc(s.system)}</span>` +
        `<span class="num h big">${money(s.total)}</span>` +
        `<span class="num raw">${s.bases}</span>` +
        `<span class="num${s.one && s.one.total === s.total ? ' h' : ' raw'}">` +
        `${s.one ? money(s.one.total) : '-'}</span>` +
        `<span class="nm raw">${esc(s.missing.join(', '))}</span></div>` +
        (open ? holdLegs(s) : '');
    }).join('') + '</div></div>';
  return out;
}

// --- the one picker -------------------------------------------------------
//
// `rows` is [{key, name, sub, at, num, tone}], which is all either list needs:
// a commodity says "43 bases", a base says "12 kinds in stock", and neither
// difference reaches the widget.
function pickList(rows, placeholder, note) {
  const q = (tradeQuery || '').trim().toLowerCase();
  const found = rows.filter(r => !q ||
      r.name.toLowerCase().includes(q) ||
      (r.sub || '').toLowerCase().includes(q));
  // Capped, because 160 bases is a wall rather than a list. The cap has to be
  // said out loud: a note claiming 160 over a list of 60 is the page lying
  // about what you are looking at, and the missing ones are exactly the ones
  // late in the alphabet.
  const hits = found.slice(0, 60);
  const clipped = found.length - hits.length;
  return '<div class="pickbox"><div class="row">' +
    `<input type="search" id="pickbox" placeholder="${esc(placeholder)}" ` +
    `value="${esc(tradeQuery || '')}" autocomplete="off">` +
    '<label class="toggle"><input type="checkbox" id="tradeseen"' +
    (tradeVisitedOnly ? ' checked' : '') +
    '> <span>only bases I have docked at</span></label></div>' +
    // `wrapgrid`: this flows and wraps by design, so `check_views.py` must not
    // read its cell count as a table row that has drifted from its columns.
    '<div class="hits wrapgrid">' +
    (hits.length ? hits.map(r =>
      `<button class="hit" data-pick="${esc(r.key)}">` +
      `<span class="nm">${esc(r.name)}</span>` +
      `<span class="nm">${esc(r.sub || '')}</span>` +
      `<span class="cell">${esc(r.at || '')}</span>` +
      `<span class="num${r.tone ? ' ' + r.tone : ''}">${esc(r.num || '')}</span>` +
      '</button>').join('')
      : '<p class="empty">Nothing by that name.</p>') +
    '</div><p class="note">' + note(found.length, rows.length) +
    (clipped ? ` Showing the first ${hits.length}; ${clipped} more match, so
                 type to narrow it.` : '') + '</p></div>';
}

function pickedBar(name, sub) {
  return '<div class="pick">' +
    `<span class="nm">${esc(name)}</span>` +
    (sub ? `<span class="sys">${esc(sub)}</span>` : '') +
    '<button class="addgun" id="repick">change</button></div>';
}

// --- the one destinations table -------------------------------------------
//
// With a source base each row carries `delta`, the profit a unit, and the
// column appears. Without one there is nothing to measure against and the
// column is absent rather than empty: a dash in every cell of a column reads
// as missing data, and this is not missing, it is not asked.
function destTable(d) {
  const rows = tradeVisitedOnly ? d.rows.filter(r => r.visited) : d.rows;
  const gain = !!d.source;
  if (!rows.length)
    return '<p class="empty">Nowhere you have docked trades it.</p>';
  return `<div class="guns"><div class="tradetable${gain ? '' : ' plain'}">` +
    '<div class="gunhead"><span>price</span>' + (gain ? '<span>gain</span>' : '') +
    '<span class="nm">base</span><span class="nm">system</span>' +
    '<span class="cell">at</span></div>' +
    rows.map(r =>
      `<div class="gun traderow${r.buy ? ' sells' : ''}">` +
      `<span class="num h">${money(r.price)}</span>` +
      (gain ? `<span class="num${r.delta > 0 ? ' up' : ' raw'}">` +
              `${r.delta > 0 ? '+' : ''}${money(r.delta)}</span>` : '') +
      `<span class="nm">${esc(r.base.name)}</span>` +
      `<span class="nm">${esc(r.base.system)}</span>` +
      `<span class="cell">${esc(r.base.at)}</span></div>`).join('') +
    '</div></div>';
}

function axisBar() {
  return '<div class="modebar">' +
    [['good', 'BY COMMODITY'], ['base', 'BY BASE']].map(([k, label]) =>
      `<button class="mode${tradeBy === k ? ' on' : ''}" data-by="${k}">` +
      `${label}</button>`).join('') + '</div>';
}

function renderTrade() {
  const d = tradeData;
  if (!d) return '<p class="empty">reading the markets…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;

  let out = renderHold(d.hold) + axisBar();

  // Stage one, by base only: which base am I standing on.
  if (tradeBy === 'base') {
    if (!d.base)
      return out + pickList(
        d.bases.map(b => ({ key: b.id, name: b.name, sub: b.system,
                            at: b.at, num: b.goods })),
        'type a base or system name',
        (found, all) => `${found} of ${all} bases sell something` +
          (tradeVisitedOnly ? ' and are ones you have docked at' : '') +
          '. The number on the right is how many kinds of cargo it stocks.');
    out += pickedBar(d.base.name, `${d.base.system} · ${d.base.at}`);
  }

  // Stage two: which commodity. The list is every commodity, or this base's
  // shelf, and it is the same widget either way.
  if (!d.good) {
    if (!d.goods.length)
      return out + '<p class="empty">This base has nothing in stock.</p>';
    return out + pickList(
      d.goods.map(g => ({
        key: g.nickname, name: g.name,
        sub: g.best ? `best: ${g.best.base.name}` : (g.price === null ? '' : 'nowhere else'),
        at: g.price === null ? '' : money(g.price),
        num: g.best ? '+' + money(g.best.delta) : (g.price === null ? g.bases : ''),
        tone: g.best ? 'up' : '' })),
      tradeBy === 'base' ? 'type a commodity on this shelf'
                         : 'type a commodity name',
      (found, all) => tradeBy === 'base'
        ? `${found} of ${all} on the shelf here. <b>at</b> is what it costs
           you, and the figure on the right is what the best run in the game
           leaves you a unit.`
        : `${found} of ${all} commodities are traded somewhere. The number on
           the right is how many bases trade each one.`);
  }

  const chosen = d.goods.find(g => g.nickname === d.good);
  out += pickedBar(chosen ? chosen.name : d.good,
    d.source ? `bought here at ${money(d.source.price)}` : 'every base trading it');
  out += `<p class="note">` + (d.source
    ? `Every base that trades it, by what it leaves you a unit over the
       ${money(d.source.price)} you pay here.`
    : `Every base that trades it, dearest first: the best place to sell is at
       the top and the cheapest place to buy is at the bottom.`) +
    ` <b class="ok">Green means the base has it on the shelf</b>, so it will
      sell it to you as well as buy it. Prices are per unit.</p>`;
  return out + destTable(d);
}

function wireTrade() {
  document.querySelectorAll('.modebar .mode').forEach(b =>
    b.addEventListener('click', () => {
      if (tradeBy === b.dataset.by) return;
      tradeBy = b.dataset.by;
      // The commodity does not survive the switch: by base it has to be one
      // this base stocks, and by base it was chosen off a shelf. The base
      // does survive, so switching back is free.
      tradeGood = '';
      tradeQuery = '';
      loadTrade();
    }));

  document.querySelectorAll('.hit[data-pick]').forEach(b =>
    b.addEventListener('click', () => {
      const key = b.dataset.pick;
      if (tradeBy === 'base' && !tradeData.base) tradeBase = key;
      else tradeGood = key;
      tradeQuery = '';
      loadTrade();
    }));

  const again = $('#repick');
  if (again) again.addEventListener('click', () => {
    // "change" undoes the last choice: the commodity if one is picked, else
    // the base. Clearing the value is what reopens that picker, so going back
    // one step from a commodity lands on the shelf and not on the base list.
    if (tradeGood) tradeGood = '';
    else tradeBase = '';
    tradeQuery = '';
    loadTrade();
  });

  const seen = $('#tradeseen');
  if (seen) seen.addEventListener('change', e => {
    // A refetch, not a redraw. The table can hide its own rows, but the hold
    // advice names a system chosen out of bases this page never received, so
    // only the server can choose it again.
    tradeVisitedOnly = e.target.checked;
    loadTrade();
  });

  const box = $('#pickbox');
  if (box) {
    // Re-rendering replaces the input, so the caret has to be put back or the
    // second character types itself at the front.
    box.focus();
    box.setSelectionRange(box.value.length, box.value.length);
    box.addEventListener('input', e => { tradeQuery = e.target.value; render(); });
    box.addEventListener('keydown', e => {
      if (e.key === 'Escape') { tradeQuery = ''; render(); }
    });
  }

  // The save is only written when the game writes it, so the hold goes stale
  // while you fly. This tab is not polled; the button is the refresh.
  const refresh = $('#holdagain');
  if (refresh) refresh.addEventListener('click', loadTrade);
  document.querySelectorAll('.holdrow').forEach(b =>
    b.addEventListener('click', () => {
      holdSys = b.dataset.hold === holdSys ? '' : b.dataset.hold;
      render();
    }));
}

async function loadTrade() {
  const q = ['by=' + tradeBy];
  if (tradeBy === 'base' && tradeBase) q.push('base=' + encodeURIComponent(tradeBase));
  if (tradeGood) q.push('good=' + encodeURIComponent(tradeGood));
  if (tradeVisitedOnly) q.push('visited=1');
  try {
    const r = await fetch('api/market?' + q.join('&'), { cache: 'no-store' });
    if (r.ok) { tradeData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}

VIEW.market = {
  bare: true,
  sub: 'who buys and sells what, from either end',
  draw: renderTrade, wire: wireTrade,
  open: () => { if (!tradeData) loadTrade(); },
};
"""
