"""Equipment → Search: guns and shields by parameter."""

ID, LABEL = "search", "Search"

CSS = """
  .geartable { min-width: 40rem; }
  .geartable .gun, .geartable .gunhead { grid-template-columns: inherit; }
  /* A row is a button in all but name: clicking one opens where to buy it. */
  .good { cursor: pointer; }
  .good.on { border-color: var(--docked); }
"""

JS = r"""
let gearData = null, gearKind = 'guns', gearFilters = [],
    gearOpen = '', gearVisitedOnly = false, gearSort = '', gearDir = 'down';
// Name and system are not in the removable filter list with the rest. They are
// the two you reach for first, so they sit in the top row and are always there.
//
// `gearSystem` holds a system **nickname**, never a display name: five labels
// in this game are worn by more than one system, so the label cannot be the
// key. The option's text is the label and its value is the nickname.
let gearName = '', gearSystem = '';

const sysLabel = (d, key) =>
  ((d.systems || []).find(s => s.key === key) || { label: key }).label;

function renderGear() {
  const d = gearData;
  if (!d) return '<p class="empty">reading the catalogue…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;

  const params = d.parameters;
  const param = k => params.find(p => p.key === k) || { label: k, unit: '' };
  const money = v => (v === null || v === undefined) ? '-' : v.toLocaleString();
  const fmt = (v, p) => {
    if (v === null || v === undefined || v === '') return '-';
    if (p.kind === 'pick') return esc(String(v));
    const n = Number(v);
    return (Math.abs(n) >= 1000 ? Math.round(n).toLocaleString()
                                : n.toFixed(n % 1 ? 1 : 0)) + (p.unit ? ' ' + p.unit : '');
  };

  let out = '<div class="reppick">' +
    `<select id="gearkind">` +
    d.kinds.map(k => `<option value="${esc(k.key)}"` +
      (k.key === gearKind ? ' selected' : '') +
      `>${esc(k.label)} (${k.count})</option>`).join('') +
    '</select>' +
    `<input type="search" id="gearname" placeholder="name contains…" ` +
    `value="${esc(gearName)}">` +
    '<select id="gearsys"><option value="">sold in any system</option>' +
    (d.systems || []).map(sy =>
      `<option value="${esc(sy.key)}"${sy.key === gearSystem ? ' selected' : ''}>` +
      `${esc(sy.label)}</option>`).join('') +
    '</select>' +
    '<label class="toggle"><input type="checkbox" id="gearseen"' +
    (gearVisitedOnly ? ' checked' : '') +
    '> <span>only bases I have docked at</span></label></div>';

  // The filters, each its own removable row. A numeric one takes a minimum, a
  // categorical one takes a value from the list, because "at least Graviton"
  // is not a thing anybody means.
  out += '<div class="filters">';
  gearFilters.forEach((f, i) => {
    const p = param(f.key);
    const list = () => `<select data-pick="${i}">` +
      (d.choices[f.key] || []).map(c =>
        `<option${String(c) === String(f.value) ? ' selected' : ''}>${esc(c)}</option>`
      ).join('') + '</select>';
    out += `<div class="filter"><span class="nm">${esc(p.label)}</span>` +
      (p.kind === 'class'
        // A mount class is a number, so it takes a comparison. `<` and `>`
        // stay inside the family: a shield's "fighter 6" and "elite 6" are
        // different sockets on the ship, not two sizes of one.
        ? `<select class="op" data-op="${i}">` +
          [['pick', '='], ['lt', '<'], ['gt', '>']].map(([v, sym]) =>
            `<option value="${v}"${f.op === v ? ' selected' : ''}>${sym}</option>`
          ).join('') + '</select>' + list()
        : p.kind === 'pick'
        ? list()
        : `<span class="sys">at least</span>` +
          `<input type="number" data-min="${i}" value="${esc(String(f.value))}">` +
          (p.unit ? `<span class="sys">${esc(p.unit)}</span>` : '')) +
      `<button class="kill" data-drop="${i}" title="remove">&times;</button></div>`;
  });
  const spare = params.filter(p => !gearFilters.some(f => f.key === p.key));
  if (spare.length)
    out += '<div class="filter"><select id="gearadd">' +
      '<option value="">+ add a parameter…</option>' +
      spare.map(p => `<option value="${esc(p.key)}">${esc(p.label)}</option>`).join('') +
      '</select></div>';
  out += '</div>';

  if (!d.rows.length)
    return out + '<p class="empty">Nothing matches all of those.</p>';

  // Columns: the kind's headline number, whatever is being sorted on, and
  // whatever is being filtered on. A key appears once however many of those
  // it happens to be.
  // `price` is left out: it has a fixed column of its own further right, and
  // listing it twice is how a table starts lying about itself.
  const cols = [];
  [d.default, d.order].concat(gearFilters.map(f => f.key))
    .forEach(k => { if (k && k !== 'price' && !cols.includes(k)) cols.push(k); });
  const arrow = k => k !== d.order ? '' : (d.dir === 'down' ? ' ↓' : ' ↑');
  out += `<p class="note">${d.rows.length} of ${d.total},
    by ${esc(param(d.order).label)}${d.dir === 'down' ? ', biggest first' : ', smallest first'}.
    Click any heading to sort by it; filtering never changes the order on its
    own. Prices are the same at every dealer in the game, so the list under a
    row is where, not where cheapest.` +
    (gearSystem
      ? ` Only what <b>${esc(sysLabel(d, gearSystem))}</b> sells: a gun found
          in a wreck but sold nowhere there is not in this list.`
      : '') + '</p>';

  out += '<div class="guns"><div class="geartable" ' +
    `style="grid-template-columns: minmax(12rem,1fr) ${'6rem '.repeat(cols.length)}6rem 5rem">` +
    '<div class="gunhead"><span class="nm">item</span>' +
    cols.map(k => `<span class="sortby" data-sort="${esc(k)}">` +
      `${esc(param(k).label)}${arrow(k)}</span>`).join('') +
    `<span class="sortby" data-sort="price">price${arrow('price')}</span>` +
    '<span>where</span></div>' +
    d.rows.map(r => {
      const open = r.nickname === gearOpen;
      let line = `<div class="gun good${open ? ' on' : ''}" data-item="${esc(r.nickname)}">` +
        `<span class="nm">${esc(r.name)}` +
        (r.rank ? ` <span class="loot">rank ${r.rank}</span>` : '') + '</span>' +
        cols.map(k => `<span class="num ${k === d.order ? 'h' : 'raw'}">` +
          `${fmt(r[k], param(k))}</span>`).join('') +
        `<span class="num">${r.price ? money(Math.round(r.price)) : '-'}</span>` +
        `<span class="num raw">${r.bases.length || (r.wrecks.length ? 'wreck' : '-')}</span>` +
        '</div>';
      if (!open) return line;
      const where = r.bases.length
        ? r.bases.map(b =>
            `<div class="atrow"><span class="cell">${esc(b.system)}</span>` +
            `<span class="cell">${esc(b.at)}</span>` +
            `<span>${esc(b.name)}</span></div>`).join('')
        : r.wrecks.length
          ? r.wrecks.map(w =>
              `<div class="atrow"><span class="cell">${esc(w.system)}</span>` +
              `<span>the ${esc(w.name)} wreck</span></div>`).join('')
          : '<p class="empty">Nowhere you have docked sells it.</p>';
      return line + `<div class="gearwhere">${where}</div>`;
    }).join('') +
    '</div></div>';
  return out;
}

function wireGear() {
  const k = $('#gearkind');
  if (k) k.addEventListener('change', e => {
    gearKind = e.target.value;
    // Parameters differ per kind, so a filter carried over would be a key the
    // new kind does not have and would silently match nothing.
    gearFilters = [];
    gearOpen = '';
    // The sort column is a parameter too, so it cannot survive the switch
    // either; the server would fall back silently and the arrow would lie.
    gearSort = '';
    gearDir = 'down';
    // The name survives the switch, because it means the same thing for both
    // kinds. The system does not: the two catalogues are sold in different
    // places, and a nickname absent from the new list would filter to nothing
    // with no way to see why.
    if (!(gearData.systems || []).some(x => x.key === gearSystem)) gearSystem = '';
    loadGear();
  });
  const nm = $('#gearname');
  if (nm) {
    // `change`, not `input`: every keystroke would be a request, and the box
    // would lose focus to the repaint that followed.
    nm.addEventListener('change', e => { gearName = e.target.value.trim(); loadGear(); });
  }
  const sy = $('#gearsys');
  if (sy) sy.addEventListener('change', e => { gearSystem = e.target.value; loadGear(); });
  const v = $('#gearseen');
  if (v) v.addEventListener('change', e => {
    gearVisitedOnly = e.target.checked;
    loadGear();
  });
  const add = $('#gearadd');
  if (add) add.addEventListener('change', e => {
    const key = e.target.value;
    if (!key) return;
    const p = gearData.parameters.find(x => x.key === key);
    const listed = p.kind === 'pick' || p.kind === 'class';
    gearFilters.push({ key, kind: p.kind, op: 'pick',
                       value: listed ? (gearData.choices[key] || [''])[0] : 0 });
    loadGear();
  });
  document.querySelectorAll('.filter .kill').forEach(b =>
    b.addEventListener('click', () => {
      gearFilters.splice(Number(b.dataset.drop), 1);
      loadGear();
    }));
  document.querySelectorAll('.filter [data-pick]').forEach(s =>
    s.addEventListener('change', e => {
      gearFilters[Number(s.dataset.pick)].value = e.target.value;
      loadGear();
    }));
  document.querySelectorAll('.filter [data-op]').forEach(s =>
    s.addEventListener('change', e => {
      gearFilters[Number(s.dataset.op)].op = e.target.value;
      loadGear();
    }));
  document.querySelectorAll('.filter [data-min]').forEach(box => {
    box.addEventListener('change', e => {
      gearFilters[Number(box.dataset.min)].value = Number(e.target.value) || 0;
      loadGear();
    });
  });
  document.querySelectorAll('.geartable .good').forEach(b =>
    b.addEventListener('click', () => {
      gearOpen = b.dataset.item === gearOpen ? '' : b.dataset.item;
      render();
    }));
  document.querySelectorAll('.sortby').forEach(h =>
    h.addEventListener('click', () => {
      // Clicking the column already sorted on turns it round; a new column
      // starts big-first, which is what you want from every one of them.
      const key = h.dataset.sort;
      gearDir = (key === gearData.order && gearDir === 'down') ? 'up' : 'down';
      gearSort = key;
      loadGear();
    }));
}

async function loadGear() {
  const q = ['kind=' + encodeURIComponent(gearKind)];
  // A `class` filter travels as its operator, so the server has one place
  // that decides what a row means rather than a kind plus a modifier.
  gearFilters.forEach(f => q.push('f=' + encodeURIComponent(
    `${f.key}:${f.kind === 'class' ? f.op : f.kind}:${f.value}`)));
  // Down the same road as every other filter, so one function decides what is
  // kept and what is dropped.
  if (gearName) q.push('f=' + encodeURIComponent(`name:text:${gearName}`));
  if (gearSystem) q.push('f=' + encodeURIComponent(`system:system:${gearSystem}`));
  if (gearSort) q.push('sort=' + encodeURIComponent(gearSort) + '&dir=' + gearDir);
  if (gearVisitedOnly) q.push('visited=1');
  try {
    const r = await fetch('api/equipment?' + q.join('&'), { cache: 'no-store' });
    if (r.ok) { gearData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}

VIEW.search = {
  bare: true,
  sub: 'what to look for, and where it is sold',
  draw: renderGear, wire: wireGear,
  open: () => { if (!gearData) loadGear(); },
};
"""
