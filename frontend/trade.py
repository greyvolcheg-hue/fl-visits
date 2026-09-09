"""Trade: who buys and sells what, asked from either end.

One tab, two modes, because they are one question from opposite ends: by
commodity is "who trades gold", by base is "what does this base sell and where
is it worth more". They were two sub-tabs until 2026-09-09.

The two modes keep their own state and their own endpoint. Nothing is shared
between them but the mode switch, which is deliberate: switching back has to
land where you left off, and a merged selection would mean one of the two
always started over.
"""

ID, LABEL = "market", "Market"

CSS = """
  /* Layout only. The look comes from the one button rule in `_theme.css`,
     which `.modebar button` is now named in, so these read as the same
     control as COLLAPSE ALL and the Neural Net's source chips. */
  .modebar { display: flex; gap: .4rem; margin: 0 0 .9rem; }


  .goodtable { min-width: 42rem; }
  .goodtable .gun, .goodtable .gunhead {
    grid-template-columns: minmax(11rem, 1fr) 4.5rem 4.5rem 5rem minmax(12rem, 1.4fr); }
  .desttable { min-width: 40rem; }
  .desttable .gun, .desttable .gunhead {
    grid-template-columns: 5rem 5rem minmax(12rem, 1fr) minmax(8rem, 1fr) 5rem; }
  /* A good is a button in all but name: clicking one opens its destinations. */
  .good { cursor: pointer; }
  .good.on { border-color: var(--docked); }

  /* --- by commodity --- */
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
// 'good' or 'base'. The first thing the tab asks, because everything under it
// is read against the answer.
let tradeBy = 'good';
let deltaData = null, deltaBase = '', deltaGood = '',
    deltaVisitedOnly = false, deltaQuery = null;

function renderDeltas() {
  const d = deltaData;
  if (!d) return '<p class="empty">reading the markets…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;

  let out = '<div class="reppick">' +
    '<label class="toggle"><input type="checkbox" id="deltaseen"' +
    (deltaVisitedOnly ? ' checked' : '') +
    '> <span>only bases I have docked at</span></label></div>';

  // Step one. Closed once a base is picked, because the pick is the context
  // everything below it is read against and it has to stay on screen.
  if (!d.base || deltaQuery !== null) {
    const q = (deltaQuery || '').trim().toLowerCase();
    const hits = d.bases
      .filter(b => !q || b.name.toLowerCase().includes(q)
                      || b.system.toLowerCase().includes(q))
      .slice(0, 40);
    out += `<p><input id="basesearch" placeholder="type a base or system name" ` +
      `value="${esc(deltaQuery || '')}" autocomplete="off"></p><div class="hits">` +
      (hits.length ? hits.map(b =>
        `<button class="hit" data-base="${esc(b.id)}">` +
        `<span class="nm">${esc(b.name)}</span>` +
        `<span class="nm">${esc(b.system)}</span>` +
        `<span class="cell">${esc(b.at)}</span>` +
        `<span class="num">${b.goods}</span></button>`).join('')
        : '<p class="empty">Nothing by that name.</p>') + '</div>' +
      `<p class="note">${d.bases.length} bases sell something` +
      (deltaVisitedOnly ? ' and are ones you have docked at' : '') +
      '. The number on the right is how many kinds of cargo it has in stock.</p>';
    return out;
  }

  out += '<div class="pick">' +
    `<span class="nm">${esc(d.base.name)}</span>` +
    `<span class="sys">${esc(d.base.system)} · ${esc(d.base.at)}</span>` +
    '<button class="addgun" id="rebase">change base</button></div>';

  if (!d.goods.length)
    return out + '<p class="empty">This base has nothing in stock.</p>';

  const money = v => v.toLocaleString();
  out += `<p class="note">${d.goods.length} on the shelf here, dearest first.
    <b>best</b> is the most anyone will pay for it and <b>gain</b> is what that
    leaves you a unit. Click a row for every base that trades it.</p>`;

  out += '<div class="guns"><div class="goodtable">' +
    '<div class="gunhead"><span class="nm">commodity</span><span>buy</span>' +
    '<span>best</span><span>gain</span><span class="nm">where</span></div>' +
    d.goods.map(g =>
      `<div class="gun good${g.nickname === d.good ? ' on' : ''}" ` +
      `data-good="${esc(g.nickname)}">` +
      `<span class="nm">${esc(g.name)}</span>` +
      `<span class="num raw">${money(g.price)}</span>` +
      (g.best
        ? `<span class="num">${money(g.best.price)}</span>` +
          `<span class="num up">+${money(g.best.delta)}</span>` +
          `<span class="nm">${esc(g.best.base.name)}, ${esc(g.best.base.system)}</span>`
        : '<span class="num raw">-</span><span class="num raw">-</span>' +
          '<span class="nm">nowhere else trades it</span>') +
      '</div>').join('') + '</div></div>';

  if (!d.good) return out;

  const good = d.goods.find(g => g.nickname === d.good);
  out += `<p class="note" style="margin-top:1.25rem">${esc(good ? good.name : d.good)}
    bought here at ${money(good ? good.price : 0)}, and every base that trades
    it, by what it leaves you.
    <b class="ok">Green still means the base has it on the shelf</b>, the same
    as on Data: those will sell it to you as well as buy it.</p>`;

  out += '<div class="guns"><div class="desttable">' +
    '<div class="gunhead"><span>price</span><span>gain</span>' +
    '<span class="nm">base</span><span class="nm">system</span>' +
    '<span class="cell">at</span></div>' +
    d.rows.map(r =>
      `<div class="gun traderow${r.buy ? ' sells' : ''}">` +
      `<span class="num h">${money(r.price)}</span>` +
      `<span class="num${r.delta > 0 ? ' up' : ' raw'}">` +
      `${r.delta > 0 ? '+' : ''}${money(r.delta)}</span>` +
      `<span class="nm">${esc(r.base.name)}</span>` +
      `<span class="nm">${esc(r.base.system)}</span>` +
      `<span class="cell">${esc(r.base.at)}</span></div>`).join('') +
    '</div></div>';
  return out;
}

function wireDeltas() {
  const v = $('#deltaseen');
  if (v) v.addEventListener('change', e => {
    deltaVisitedOnly = e.target.checked;
    loadDeltas();
  });
  const again = $('#rebase');
  if (again) again.addEventListener('click', () => { deltaQuery = ''; render(); });
  document.querySelectorAll('.hit[data-base]').forEach(b =>
    b.addEventListener('click', () => {
      deltaBase = b.dataset.base;
      deltaGood = '';
      deltaQuery = null;
      loadDeltas();
    }));
  document.querySelectorAll('.good').forEach(b =>
    b.addEventListener('click', () => {
      // Clicking the open row shuts it, so the table can be read on its own.
      deltaGood = b.dataset.good === deltaGood ? '' : b.dataset.good;
      loadDeltas();
    }));
  const box = $('#basesearch');
  if (box) {
    // Same as the weapon picker: re-rendering replaces the input, so the caret
    // has to be put back or the second character types itself at the front.
    box.focus();
    box.setSelectionRange(box.value.length, box.value.length);
    box.addEventListener('input', e => { deltaQuery = e.target.value; render(); });
    box.addEventListener('keydown', e => {
      if (e.key === 'Escape' && deltaBase) { deltaQuery = null; render(); }
    });
  }
}

async function loadDeltas() {
  const q = [];
  if (deltaBase) q.push('base=' + encodeURIComponent(deltaBase));
  if (deltaGood) q.push('good=' + encodeURIComponent(deltaGood));
  if (deltaVisitedOnly) q.push('visited=1');
  try {
    const r = await fetch('api/deltas' + (q.length ? '?' + q.join('&') : ''),
                          { cache: 'no-store' });
    if (r.ok) { deltaData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}

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

function modeBar() {
  return '<div class="modebar">' +
    ['good', 'BY COMMODITY', 'base', 'BY BASE'].reduce((acc, _, i, a) =>
      i % 2 ? acc + `<button class="mode${tradeBy === a[i - 1] ? ' on' : ''}" ` +
        `data-by="${a[i - 1]}">${a[i]}</button>` : acc, '') +
    '</div>';
}

function renderMarket() {
  return modeBar() + (tradeBy === 'base' ? renderDeltas() : renderTrade());
}

function wireMarket() {
  document.querySelectorAll('.modebar .mode').forEach(b =>
    b.addEventListener('click', () => {
      tradeBy = b.dataset.by;
      // Each mode fetches its own the first time it is opened, and keeps what
      // it had after that, so switching back lands where you left off.
      if (tradeBy === 'base' && !deltaData) loadDeltas();
      if (tradeBy === 'good' && !tradeData) loadTrade();
      render();
    }));
  if (tradeBy === 'base') wireDeltas(); else wireTrade();
}

VIEW.market = {
  bare: true,
  sub: 'who buys and sells what, from either end',
  draw: renderMarket, wire: wireMarket,
  open: () => { if (!tradeData) loadTrade(); },
};
"""
