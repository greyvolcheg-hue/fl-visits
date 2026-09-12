"""Equipment → Search: guns and shields by parameter."""

ID, LABEL = "search", "Search"

CSS = """
  .geartable { min-width: 40rem; }
  .geartable .gun, .geartable .gunhead { grid-template-columns: inherit; }
  /* A row is a button in all but name: clicking one opens where to buy it. */
  .good { cursor: pointer; }
  .good.on { border-color: var(--docked); }
  /* Dropping a column. Hidden until the heading is hovered, because a row of
     nine crosses reads as clutter on a table nobody wants to change. The
     heading itself still sorts; this stops the click before it gets there. */
  .gunhead .sortby .dropcol { opacity: 0; background: none; border: 0;
                              margin-left: .3rem; padding: 0; cursor: pointer;
                              color: var(--faint); font-family: var(--mono);
                              font-size: 11px; }
  .gunhead .sortby:hover .dropcol { opacity: 1; }
  .gunhead .sortby .dropcol:hover { color: var(--bad); }

  /* The favourite star. Its own hit target inside the name cell, because the
     row it sits on already answers a click by opening the dealer list. */
  .favstar { background: none; border: 0; padding: 0 .45rem 0 0; margin: 0;
             cursor: pointer; color: var(--fainter); font-size: 13px;
             line-height: 1; }
  .favstar:hover { color: var(--revealed); }
  .favstar.on { color: var(--revealed); }
  .good.fav { border-left: 2px solid var(--revealed); }
"""

JS = r"""
let gearData = null, gearKind = 'guns', gearFilters = [],
    gearOpen = '', gearVisitedOnly = false, gearSort = '', gearDir = 'down';
// Whether the list also holds what nothing in the game hands out. Off by
// default, because the tab answers "what can I get"; on, because an item that
// is simply absent cannot be told apart from one the reader lost, and that is
// what sent the owner looking for Death's Hand Mk III.
let gearAll = false;
// Favourites: an item kept in the list whatever the filters say. The server
// owns them, in `data/marks.json` beside the Neural Net's read marks, and this
// is a cache of what it last said. Seeded on every `loadGear`.
let gearFavs = new Set();
// Columns switched off by hand. **The exceptions, not the selection**: every
// parameter is a column by default, so an empty set is the full table and a
// parameter added to the game later shows up without being listed anywhere.
let gearHidden = new Set();
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
  // The `where` cell for everything that is not sold. `sold` is absent on
  // purpose: its cell is the count of dealers, which is a number rather than
  // a word, and a lookup that answered for it would have to hold every count.
  const WHERE = { wreck: 'wreck', loot: 'off a ship', none: 'nowhere' };
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
    '> <span>only bases I have docked at</span></label>' +
    '<label class="toggle"><input type="checkbox" id="gearnowhere"' +
    (gearAll ? ' checked' : '') +
    `> <span>also what nothing in the game gives you (${d.hidden})</span></label>` +
    '</div>';

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
    // The operator row, shared by the two parameters that take one. `class`
    // picks its value off a list, `cmp` takes a typed number; the select in
    // front of them is the same control and reads the same way.
    const ops = list => `<select class="op" data-op="${i}">` +
      [['pick', '='], ['le', '<='], ['ge', '>=']].map(([v, sym]) =>
        `<option value="${v}"${f.op === v ? ' selected' : ''}>${sym}</option>`
      ).join('') + '</select>' + list;
    out += `<div class="filter"><span class="nm">${esc(p.label)}</span>` +
      (p.kind === 'class'
        // A mount class is a number, so it takes a comparison. `<=` and `>=`
        // stay inside the family: a shield's "fighter 6" and "elite 6" are
        // different sockets on the ship, not two sizes of one.
        ? ops(list())
        : p.kind === 'cmp'
        // A plain number, compared the obvious way, with no family rule on it.
        // Rank is the one parameter where "at least" is the wrong question:
        // what you want to know is what you can fly now.
        ? ops(`<input type="number" data-min="${i}" value="${esc(String(f.value))}">` +
              (p.unit ? `<span class="sys">${esc(p.unit)}</span>` : ''))
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
  // Only once something is off. A control offering nothing is furniture.
  const off = params.filter(p => p.key !== 'price' && gearHidden.has(p.key));
  if (off.length)
    out += '<div class="filter"><select id="gearcol">' +
      `<option value="">+ add a column… (${off.length} off)</option>` +
      off.map(p => `<option value="${esc(p.key)}">${esc(p.label)}</option>`).join('') +
      '</select></div>';
  out += '</div>';

  if (!d.rows.length)
    return out + '<p class="empty">Nothing matches all of those.</p>';

  // **Every parameter, in the order `PARAMETERS` declares them.** It used to
  // show only the sorted column plus whatever was being filtered on, which is
  // two or three of nine and is what the owner meant by "мало данных". They
  // fit: measured with all of them on, guns need 1335px and shields 1244px,
  // no header is clipped and the page never scrolls sideways. Below about
  // 1350px the table scrolls inside its own `.guns` box, which is what that
  // box is for.
  // `price` is left out: it has a fixed column of its own further right, and
  // listing it twice is how a table starts lying about itself.
  // A column you are sorting or filtering on is never hidden, whatever the set
  // says: an arrow pointing at a column that is not on screen, or a filter
  // narrowing the list by a number you cannot see, is the table lying about
  // itself. That is also why those two carry no × to click.
  const pinned = k => k === d.order || gearFilters.some(f => f.key === k);
  const cols = params.filter(p => p.key !== 'price')
    .filter(p => pinned(p.key) || !gearHidden.has(p.key)).map(p => p.key);
  const arrow = k => k !== d.order ? '' : (d.dir === 'down' ? ' ↓' : ' ↑');
  out += `<p class="note">${d.rows.length} of ${d.total},
    by ${esc(param(d.order).label)}${d.dir === 'down' ? ', biggest first' : ', smallest first'}.
    Click any heading to sort by it; filtering never changes the order on its
    own. Prices are the same at every dealer in the game, so the list under a
    row is where, not where cheapest.` +
    (gearSystem
      ? ` Only what <b>${esc(sysLabel(d, gearSystem))}</b> sells: a gun found
          in a wreck but sold nowhere there is not in this list.`
      : '') +
    (gearVisitedOnly
      ? ` Only what is sold at a base you have docked at, so wreck loot and
          anywhere you have not been are both out of it.`
      : '') +
    (gearFavs.size
      ? ` <b class="ok">${gearFavs.size} favourite${gearFavs.size > 1 ? 's' : ''}</b>
          stay in the list whatever the filters say.`
      : '') + '</p>';

  out += '<div class="guns"><div class="geartable" ' +
    `style="grid-template-columns: minmax(12rem,1fr) ${'6rem '.repeat(cols.length)}6rem 5rem">` +
    '<div class="gunhead"><span class="nm">item</span>' +
    cols.map(k => `<span class="sortby" data-sort="${esc(k)}">` +
      `${esc(param(k).label)}${arrow(k)}` +
      (pinned(k) ? ''
                 : `<button class="dropcol" data-col="${esc(k)}" ` +
                   'title="remove this column">&times;</button>') +
      '</span>').join('') +
    `<span class="sortby" data-sort="price">price${arrow('price')}</span>` +
    '<span>where</span></div>' +
    d.rows.map(r => {
      const open = r.nickname === gearOpen;
      const fav = gearFavs.has(r.nickname);
      let line = '<div class="gun good' + (open ? ' on' : '') + (fav ? ' fav' : '') +
        `" data-item="${esc(r.nickname)}">` +
        `<span class="nm"><button class="favstar${fav ? ' on' : ''}" ` +
        `data-fav="${esc(r.nickname)}" title="${fav
          ? 'a favourite: stays in the list whatever the filters say'
          : 'keep this one in the list whatever the filters say'}">` +
        `${fav ? '★' : '☆'}</button>${esc(r.name)}` +
        (r.rank ? ` <span class="loot">rank ${r.rank}</span>` : '') + '</span>' +
        cols.map(k => `<span class="num ${k === d.order ? 'h' : 'raw'}">` +
          `${fmt(r[k], param(k))}</span>`).join('') +
        `<span class="num">${r.price ? money(Math.round(r.price)) : '-'}</span>` +
        `<span class="num raw">${WHERE[r.source] || r.bases.length}</span>` +
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
          : r.source === 'loot'
            ? `<p class="note">No dealer and no wreck: you take it off whoever
                is flying it. ${r.carriers} loadout${r.carriers === 1 ? '' : 's'}
                in the game mount${r.carriers === 1 ? 's' : ''} one, and the
                game gives it a ${Math.round(r.drop)}% chance of surviving the
                kill as loot.</p>`
          : r.source === 'none'
            ? `<p class="note warn">${r.undockable
                ? `Stocked by ${r.undockable} base${r.undockable === 1 ? '' : 's'}
                   you cannot dock at, and nowhere else.`
                : `Nothing in the game gives you this. No dealer, no wreck,
                   nothing flying it: it is in the equipment files and the rest
                   of the game never refers to it.`}</p>`
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
    // Hidden columns are parameter keys as well, and the other kind's are not
    // the same keys. Carried over they would be a set of names nothing in the
    // table answers to, with no way to see why a column is missing.
    gearHidden = new Set();
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
  const nw = $('#gearnowhere');
  if (nw) nw.addEventListener('change', e => {
    gearAll = e.target.checked;
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
  document.querySelectorAll('.favstar').forEach(b =>
    b.addEventListener('click', e => {
      // The row under it opens the dealer list, and a star is not that.
      e.stopPropagation();
      const key = b.dataset.fav;
      const on = !gearFavs.has(key);
      if (on) gearFavs.add(key); else gearFavs.delete(key);
      render();
      favourite(key, on);
    }));
  // Columns are presentation and nothing else: the numbers are already on the
  // page, so neither of these asks the server for anything.
  document.querySelectorAll('.dropcol').forEach(b =>
    b.addEventListener('click', e => {
      e.stopPropagation();   // the heading under it sorts, and this is not that
      gearHidden.add(b.dataset.col);
      render();
    }));
  const col = $('#gearcol');
  if (col) col.addEventListener('change', e => {
    if (!e.target.value) return;
    gearHidden.delete(e.target.value);
    render();
  });
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

// **No `marksHeld` guard here, and none is needed.** The Neural Net keeps one
// because it re-reads the log every five seconds and a payload prepared before
// a click would undo it; Equipment registers no `poll`, so nothing arrives
// between the click and the reload below. The guard next door is not something
// this tab forgot.
//
// The reload is not optional. Un-starring an item that only survived the
// filters because of its star has to take it out of the list, and starring one
// changes what the server would send back, so the list is asked for again once
// the write is home.
async function favourite(key, on) {
  try {
    await fetch('api/marks', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'fav', key: key, on: on }),
    });
  } catch (e) {
    // The star stays where the click put it; the next load corrects it.
  }
  loadGear();
}

async function loadGear() {
  const q = ['kind=' + encodeURIComponent(gearKind)];
  // A parameter with an operator travels as that operator, so the server has
  // one place that decides what a row means rather than a kind plus a
  // modifier. `class` and `cmp` are the two, and they mean different things by
  // the same symbols: see `equipment.py::search`.
  //
  // **`>=` on a number is `num`**, which is what every other numeric filter
  // already sends, because "at least" is exactly what `num` means. Giving it a
  // second name would be two spellings of one thing.
  const OPS = { class: { pick: 'pick', le: 'le', ge: 'ge' },
                cmp: { pick: 'exactly', le: 'upto', ge: 'num' } };
  gearFilters.forEach(f => q.push('f=' + encodeURIComponent(
    `${f.key}:${(OPS[f.kind] || {})[f.op] || f.kind}:${f.value}`)));
  // Down the same road as every other filter, so one function decides what is
  // kept and what is dropped.
  if (gearName) q.push('f=' + encodeURIComponent(`name:text:${gearName}`));
  if (gearSystem) q.push('f=' + encodeURIComponent(`system:system:${gearSystem}`));
  if (gearSort) q.push('sort=' + encodeURIComponent(gearSort) + '&dir=' + gearDir);
  if (gearVisitedOnly) q.push('visited=1');
  if (gearAll) q.push('nowhere=1');
  try {
    const r = await fetch('api/equipment?' + q.join('&'), { cache: 'no-store' });
    if (r.ok) {
      gearData = await r.json();
      gearFavs = new Set(gearData.favs || []);
      render();
    }
  } catch (e) { /* the tab keeps its loading line */ }
}

VIEW.search = {
  bare: true,
  sub: 'what to look for, and where it is sold',
  draw: renderGear, wire: wireGear,
  open: () => { if (!gearData) loadGear(); },
};
"""
