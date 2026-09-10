"""Trade → Routes: what to carry between two systems."""

ID, LABEL = "routes", "Routes"

CSS = """
  .routetable { min-width: 46rem; }
  .routetable .gun, .routetable .gunhead {
    grid-template-columns: minmax(10rem, 1fr) 4.5rem 4.5rem 5rem
                           minmax(9rem, 1fr) minmax(9rem, 1fr); }
  .routetable.withrun { min-width: 52rem; }
  .routetable.withrun .gun, .routetable.withrun .gunhead {
    grid-template-columns: minmax(10rem, 1fr) 4.5rem 4.5rem 4.5rem 6rem
                           minmax(8rem, 1fr) minmax(8rem, 1fr); }

  /* The nav map cell, trailing the base it belongs to. */
  .at { color: var(--dim); font-style: normal; font-size: .85em; margin-left: .35rem; }

  /* The commodity cell is the one that may run to two lines, so the badge
     drops under the name instead of pushing it into an ellipsis. Every other
     cell keeps `.gun .nm`'s clip. */
  .routetable .gun .nm.good { white-space: normal; overflow: visible; }
"""

JS = r"""
let routeData = null, routeFrom = '', routeTo = '', routeVisitedOnly = false;
// Three of the game's commodities spoil, and it says so itself. Filtered here
// rather than by the endpoint: the rows are already on the page, the count
// line is recomputed from what is shown, and a round trip buys nothing.
let routeFresh = false;

function renderRoutes() {
  const d = routeData;
  if (!d) return '<p class="empty">reading the markets…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;

  // Both ends may be the same system. New York alone has 12 market bases, so
  // buying at the cheapest and selling at the dearest without leaving it is a
  // real run, and the server drops the degenerate same-base rows anyway.
  const opts = sel => d.systems.map(s =>
    `<option value="${esc(s.nickname)}"` +
    (s.nickname === sel ? ' selected' : '') +
    `>${esc(s.name)} (${s.bases})</option>`).join('');

  let out = '<div class="reppick">' +
    `<select id="routefrom"><option value="">departure system…</option>` +
    `${opts(routeFrom)}</select>` +
    '<span class="sys">to</span>' +
    `<select id="routeto"><option value="">destination system…</option>` +
    `${opts(routeTo)}</select>` +
    '<label class="toggle"><input type="checkbox" id="routeseen"' +
    (routeVisitedOnly ? ' checked' : '') +
    '> <span>only bases I have docked at</span></label>' +
    '<label class="toggle"><input type="checkbox" id="routefresh"' +
    (routeFresh ? ' checked' : '') +
    '> <span>hide perishable</span></label></div>';

  if (!d.from || !d.to) return out + '<p class="empty">Pick both ends.</p>';

  const name = n => (d.systems.find(s => s.nickname === n) || {}).name || n;
  const money = v => v.toLocaleString();
  // One system on both ends is a legitimate pick, and "from New York to New
  // York" reads like a bug. Only the sentence changes; the table is identical.
  const same = d.from === d.to;
  const ends = same
    ? `within ${esc(name(d.from))}`
    : `from ${esc(name(d.from))} to ${esc(name(d.to))}`;
  // Two different failures, and a trader does different things about them.
  if (!d.rows.length)
    return out + '<p class="empty">' + (d.traded
      ? (same
         ? `${esc(name(d.from))} trades ${d.traded} commodities, but no base in
            it sells one cheaper than another buys it. Nothing to carry here.`
         : `${esc(name(d.from))} and ${esc(name(d.to))} trade ${d.traded} of the
            same commodities, but every one of them is cheaper at the far end.
            Nothing to carry this way.`)
      : (same
         ? `Nothing in ${esc(name(d.from))} is both bought and sold.`
         : `Nothing is bought in ${esc(name(d.from))} and traded in
            ${esc(name(d.to))} at all.`)) + '</p>';

  const spoils = d.rows.filter(r => r.perishable).length;
  const rows = routeFresh ? d.rows.filter(r => !r.perishable) : d.rows;
  if (!rows.length)
    return out + `<p class="empty">Every one of the ${spoils} worth carrying
      ${ends} is cargo the game marks as perishable. Untick the box to see
      them.</p>`;

  const losses = d.traded - d.rows.length;
  out += `<p class="note">${rows.length} worth carrying ${ends}` +
    (losses ? `, out of ${d.traded} traded in both` : '') +
    (routeFresh && spoils ? `, with ${spoils} perishable hidden` : '') + `.
    One line per commodity: the cheapest place to buy it at this end against
    the dearest place to sell it at that one.` +
    (d.hold
      ? ` <b>run</b> is a full hold of your ${esc(d.ship)}, ${d.hold} units.`
      : ' No ship found in the save, so only the per-unit figure is shown.') +
    (spoils && !routeFresh
      ? ` <b>The game marks ${spoils} of these as perishable</b>, and the run
         figure is a plain multiplication that knows nothing about it.`
      : '') +
    '</p>';

  out += '<div class="guns"><div class="routetable' + (d.hold ? ' withrun' : '') +
    '"><div class="gunhead"><span class="nm">commodity</span><span>buy</span>' +
    '<span>sell</span><span>gain</span>' +
    (d.hold ? '<span>run</span>' : '') +
    '<span class="nm">from</span><span class="nm">to</span></div>' +
    rows.map(r =>
      '<div class="gun">' +
      `<span class="nm good">${esc(r.name)}` +
      (r.perishable ? ` <i class="spoil">${esc(r.perishable)}</i>` : '') +
      '</span>' +
      `<span class="num raw">${money(r.buy)}</span>` +
      `<span class="num h">${money(r.sell)}</span>` +
      `<span class="num up">+${money(r.gain)}</span>` +
      (d.hold ? `<span class="num up big">+${money(r.run)}</span>` : '') +
      `<span class="nm">${esc(r.from.name)} <i class="at">${esc(r.from.at)}</i></span>` +
      `<span class="nm">${esc(r.to.name)} <i class="at">${esc(r.to.at)}</i></span></div>`).join('') +
    '</div></div>';
  return out;
}

function wireRoutes() {
  const f = $('#routefrom'), t = $('#routeto'), v = $('#routeseen');
  if (f) f.addEventListener('change', e => { routeFrom = e.target.value; loadRoutes(); });
  if (t) t.addEventListener('change', e => { routeTo = e.target.value; loadRoutes(); });
  if (v) v.addEventListener('change', e => {
    routeVisitedOnly = e.target.checked;
    loadRoutes();
  });
  // No reload: the rows it hides are already here.
  const fresh = $('#routefresh');
  if (fresh) fresh.addEventListener('change',
    e => { routeFresh = e.target.checked; render(); });
}

async function loadRoutes() {
  const q = [];
  if (routeFrom) q.push('from=' + encodeURIComponent(routeFrom));
  if (routeTo) q.push('to=' + encodeURIComponent(routeTo));
  if (routeVisitedOnly) q.push('visited=1');
  try {
    const r = await fetch('api/routes' + (q.length ? '?' + q.join('&') : ''),
                          { cache: 'no-store' });
    if (r.ok) { routeData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}
VIEW.routes = {
  bare: true,
  sub: 'what to put in the hold for a run you are making anyway',
  draw: renderRoutes, wire: wireRoutes,
  open: () => { if (!routeData) loadRoutes(); },
};
"""
