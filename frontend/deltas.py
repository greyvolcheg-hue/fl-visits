"""Trade → Deltas: what a base sells, and where it is worth more."""

ID, LABEL = "deltas", "Deltas"

CSS = """
  .goodtable { min-width: 42rem; }
  .goodtable .gun, .goodtable .gunhead {
    grid-template-columns: minmax(11rem, 1fr) 4.5rem 4.5rem 5rem minmax(12rem, 1.4fr); }
  .desttable { min-width: 40rem; }
  .desttable .gun, .desttable .gunhead {
    grid-template-columns: 5rem 5rem minmax(12rem, 1fr) minmax(8rem, 1fr) 5rem; }
  .traderow.sells { border-color: rgba(95, 224, 160, .45); }
  /* A good is a button in all but name: clicking one opens its destinations. */
  .good { cursor: pointer; }
  .good.on { border-color: var(--docked); }
"""

JS = r"""
let deltaData = null, deltaBase = '', deltaGood = '',
    deltaVisitedOnly = false, deltaQuery = null;
// Equipment search. `gearFilters` is [{key, kind, value}]; a "num" filter is a
// minimum and a "pick" is an exact match. The order never comes from them: the
// headline number stays in charge, so a threshold narrows without reshuffling.

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

// Equipment search. Pick a kind, stack thresholds, read the list.

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
VIEW.deltas = {
  bare: true,
  sub: 'what a base has on the shelf, and where it is worth more',
  draw: renderDeltas, wire: wireDeltas,
  open: () => { if (!deltaData) loadDeltas(); },
};
"""
