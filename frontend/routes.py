"""Trade → Routes: what to carry between two systems."""

ID, LABEL = "routes", "Routes"

CSS = """
  /* The nav map cell, trailing the base it belongs to. */
  .at { color: var(--dim); font-style: normal; font-size: .85em; margin-left: .35rem; }
"""

JS = r"""
let routeData = null, routeFrom = '', routeTo = '', routeVisitedOnly = false;

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
    '> <span>only bases I have docked at</span></label></div>';

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

  const losses = d.traded - d.rows.length;
  out += `<p class="note">${d.rows.length} worth carrying ${ends}` +
    (losses ? `, out of ${d.traded} traded in both` : '') + `.
    One line per commodity: the cheapest place to buy it at this end against
    the dearest place to sell it at that one.` +
    (d.hold
      ? ` <b>run</b> is a full hold of your ${esc(d.ship)}, ${d.hold} units.`
      : ' No ship found in the save, so only the per-unit figure is shown.') +
    '</p>';

  out += '<div class="guns"><div class="routetable' + (d.hold ? ' withrun' : '') +
    '"><div class="gunhead"><span class="nm">commodity</span><span>buy</span>' +
    '<span>sell</span><span>gain</span>' +
    (d.hold ? '<span>run</span>' : '') +
    '<span class="nm">from</span><span class="nm">to</span></div>' +
    d.rows.map(r =>
      '<div class="gun">' +
      `<span class="nm">${esc(r.name)}</span>` +
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
