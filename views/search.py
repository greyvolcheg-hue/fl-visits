"""Equipment → Search: guns and shields by parameter."""

import equipment as eqp


ID, LABEL = "search", "Search"

JS = r"""
let gearData = null, gearKind = 'guns', gearFilters = [],
    gearOpen = '', gearVisitedOnly = false, gearSort = '', gearDir = 'down';
// Routes sub-tab. Two systems by nickname, never by display name: several
// systems share a label and only the nickname tells them apart.

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
    '<label class="toggle"><input type="checkbox" id="gearseen"' +
    (gearVisitedOnly ? ' checked' : '') +
    '> <span>only bases I have docked at</span></label></div>';

  // The filters, each its own removable row. A numeric one takes a minimum, a
  // categorical one takes a value from the list, because "at least Graviton"
  // is not a thing anybody means.
  out += '<div class="filters">';
  gearFilters.forEach((f, i) => {
    const p = param(f.key);
    out += `<div class="filter"><span class="nm">${esc(p.label)}</span>` +
      (p.kind === 'pick'
        ? `<select data-pick="${i}">` + (d.choices[f.key] || []).map(c =>
            `<option${String(c) === String(f.value) ? ' selected' : ''}>${esc(c)}</option>`
          ).join('') + '</select>'
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
    row is where, not where cheapest.</p>`;

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
            `<span>${esc(b.base_name)}</span></div>`).join('')
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
    loadGear();
  });
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
    gearFilters.push({ key, kind: p.kind,
                       value: p.kind === 'pick' ? (gearData.choices[key] || [''])[0] : 0 });
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
  gearFilters.forEach(f => q.push('f=' + encodeURIComponent(
    `${f.key}:${f.kind}:${f.value}`)));
  if (gearSort) q.push('sort=' + encodeURIComponent(gearSort) + '&dir=' + gearDir);
  if (gearVisitedOnly) q.push('visited=1');
  try {
    const r = await fetch('api/equipment?' + q.join('&'), { cache: 'no-store' });
    if (r.ok) { gearData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}

// Routes. Two systems in, one hold's worth of advice out.
VIEW.search = {
  bare: true,
  sub: 'what to look for, and where it is sold',
  draw: renderGear, wire: wireGear,
  open: () => { if (!gearData) loadGear(); },
};
"""


def _equipment(ctx):
    """One kind of gear, narrowed by whatever thresholds were asked for."""
    body = {"kinds": [], "kind": None, "parameters": [], "choices": {},
            "order": None, "default": None, "dir": "down",
            "rows": [], "total": 0, "error": None}
    try:
        cat = ctx.game.gear
        body["kinds"] = [
            {"key": k, "label": k.title(), "count": len(cat[k])}
            for k in sorted(cat)]
        kind = (ctx.query.get("kind") or ["guns"])[0]
        if kind not in cat:
            kind = "guns"
        rows = cat[kind]
        keys = {k for k, _l, _kd, _u in eqp.PARAMETERS[kind]}
        order = (ctx.query.get("sort") or [""])[0]
        if order not in keys:
            order = eqp.ORDER[kind]
        down = (ctx.query.get("dir") or ["down"])[0] != "up"
        body["kind"], body["total"] = kind, len(rows)
        body["order"], body["default"] = order, eqp.ORDER[kind]
        body["dir"] = "down" if down else "up"
        body["parameters"] = [
            {"key": k, "label": lab, "kind": knd, "unit": unit}
            for k, lab, knd, unit in eqp.PARAMETERS[kind]]
        body["choices"] = {
            k: eqp.choices(rows, k)
            for k, _lab, knd, _u in eqp.PARAMETERS[kind] if knd == "pick"}

        filters = []
        for raw in ctx.query.get("f", []):
            key, _, rest = raw.partition(":")
            knd, _, value = rest.partition(":")
            if knd == "num":
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
            filters.append((key, knd, value))
        found = eqp.search(rows, filters, order, down)

        # The docked filter narrows where you can buy, never what
        # exists: a gun is still a gun if you have not been to its
        # dealer. So it rewrites `bases` and leaves the row in place,
        # and the page says "nowhere you have docked" rather than
        # quietly dropping it.
        if (ctx.query.get("visited") or [""])[0]:
            state = ctx.state()
            seen = set(state["docked_bases"])
            found = [dict(r, bases=[b for b in r["bases"] if b["base"] in seen])
                     for r in found]
        body["rows"] = found
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"equipment": _equipment}