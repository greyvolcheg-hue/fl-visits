"""Trade → Data: who buys and sells what."""

ID, LABEL = "data", "Data"

CSS = """
  .tradetable { min-width: 40rem; }
  .tradetable .gun, .tradetable .gunhead {
    grid-template-columns: 5rem 3.5rem minmax(12rem, 1fr) minmax(8rem, 1fr) 5rem; }
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
let tradeData = null, tradeGood = '', tradeVisitedOnly = false, holdSys = '';
// Deltas sub-tab. `deltaQuery` is the base picker's search box, null when it is
// closed, exactly like `gunQuery` on the DPS tab and for the same reason: 160
// bases is well past what a dropdown is for.

function ago(t) {
  const s = Date.now() / 1000 - t;
  if (s < 90) return 'just now';
  if (s < 5400) return Math.round(s / 60) + ' min ago';
  return Math.round(s / 3600) + ' h ago';
}

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

function renderTrade() {
  const d = tradeData;
  if (!d) return '<p class="empty">reading the markets…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;

  const opts = d.goods.map(g =>
    `<option value="${esc(g.nickname)}"${g.nickname === tradeGood ? ' selected' : ''}>` +
    `${esc(g.name)} (${g.bases})</option>`).join('');
  let out = renderHold(d.hold) + '<div class="reppick">' +
    `<select id="tradegood"><option value="">pick a commodity…</option>${opts}</select>` +
    '<label class="toggle"><input type="checkbox" id="tradeseen"' +
    (tradeVisitedOnly ? ' checked' : '') + '> <span>only bases I have docked at</span>' +
    '</label></div>';

  if (!d.good) return out + '<p class="empty">Pick a commodity.</p>';

  const rows = tradeVisitedOnly ? d.rows.filter(r => r.visited) : d.rows;
  if (!rows.length)
    return out + '<p class="empty">' + (tradeVisitedOnly
      ? 'None of the bases trading this are ones you have docked at.'
      : 'Nothing trades this.') + '</p>';

  const name = (d.goods.find(g => g.nickname === d.good) || {}).name || d.good;
  // The cheapest row is not always one you can buy at: gold's four cheapest
  // bases hold none of it. So the run is the cheapest *green* row to the
  // dearest row of any colour, which is not something the sort alone shows.
  const stock = rows.filter(r => r.buy);
  const low = stock[stock.length - 1], high = rows[0];
  let run = '';
  if (low && high && high.price > low.price)
    run = ` Best run here: buy at ${esc(low.base.name)} for
      ${low.price.toLocaleString()}, sell at ${esc(high.base.name)} for
      ${high.price.toLocaleString()},
      <b class="ok">${(high.price - low.price).toLocaleString()} a unit</b>.`;

  out += `<p class="note">${esc(name)} at ${rows.length} bases, dearest first.
    <b class="ok">Green means the base has it on the shelf</b>, so that is where
    you can load up; the rest hold none and only want to be sold it.${run}
    Bases you cannot dock at are not listed at all.</p>`;

  out += '<div class="guns"><div class="tradetable">' +
    '<div class="gunhead"><span>price</span><span>way</span>' +
    '<span class="nm">base</span><span class="nm">system</span>' +
    '<span class="cell">at</span></div>' +
    rows.map(r =>
      `<div class="gun traderow${r.buy ? ' sells' : ''}">` +
      `<span class="num h">${r.price.toLocaleString()}</span>` +
      `<span class="num raw">${r.buy ? 'buy' : 'sell'}</span>` +
      `<span class="nm">${esc(r.base.name)}</span>` +
      `<span class="nm">${esc(r.base.system)}</span>` +
      `<span class="cell">${esc(r.base.at)}</span></div>`).join('') +
    '</div></div>';
  return out;
}

async function loadTrade() {
  const q = [];
  if (tradeGood) q.push('good=' + encodeURIComponent(tradeGood));
  if (tradeVisitedOnly) q.push('visited=1');
  try {
    const r = await fetch('api/trade' + (q.length ? '?' + q.join('&') : ''),
                          { cache: 'no-store' });
    if (r.ok) { tradeData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}

function wireTrade() {
  const g = $('#tradegood');
  if (g) g.addEventListener('change', e => { tradeGood = e.target.value; loadTrade(); });
  const v = $('#tradeseen');
  if (v) v.addEventListener('change', e => {
    // A refetch, not a redraw. The table below can hide its own rows, but the
    // hold advice above names a system chosen out of bases this page never
    // received, so only the server can choose it again.
    tradeVisitedOnly = e.target.checked;
    loadTrade();
  });
  // The save is only written when the game writes it, so the hold goes stale
  // while you fly. This tab is not polled; the button is the refresh.
  const again = $('#holdagain');
  if (again) again.addEventListener('click', loadTrade);
  document.querySelectorAll('.holdrow').forEach(b =>
    b.addEventListener('click', () => {
      holdSys = b.dataset.hold === holdSys ? '' : b.dataset.hold;
      render();
    }));
}

// Deltas. Three steps down one panel: which base you are standing on, what it
// has on the shelf, and where each of those is worth more.
VIEW.data = {
  bare: true,
  sub: 'who buys and sells what, and for how much',
  draw: renderTrade, wire: wireTrade,
  open: () => { if (!tradeData) loadTrade(); },
};
"""
