"""Trade → Data: who buys and sells what."""

import trade as td


ID, LABEL = "data", "Data"

JS = r"""
let tradeData = null, tradeGood = '', tradeVisitedOnly = false;
// Deltas sub-tab. `deltaQuery` is the base picker's search box, null when it is
// closed, exactly like `gunQuery` on the DPS tab and for the same reason: 160
// bases is well past what a dropdown is for.

function renderTrade() {
  const d = tradeData;
  if (!d) return '<p class="empty">reading the markets…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;

  const opts = d.goods.map(g =>
    `<option value="${esc(g.nickname)}"${g.nickname === tradeGood ? ' selected' : ''}>` +
    `${esc(g.name)} (${g.bases})</option>`).join('');
  let out = '<div class="reppick">' +
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
    run = ` Best run here: buy at ${esc(low.base_name)} for
      ${low.price.toLocaleString()}, sell at ${esc(high.base_name)} for
      ${high.price.toLocaleString()},
      <b class="ok">${(high.price - low.price).toLocaleString()} a unit</b>.`;

  out += `<p class="note">${esc(name)} at ${rows.length} bases, dearest first.
    <b class="ok">Green means the base has it on the shelf</b>, so that is where
    you can load up; the rest hold none and only want to be sold it.${run}
    Bases you cannot dock at are not listed at all.</p>`;

  out += '<div class="guns"><div class="tradetable">' +
    '<div class="gunhead"><span>price</span><span>way</span>' +
    '<span class="nm">base</span><span class="nm">system</span></div>' +
    rows.map(r =>
      `<div class="gun traderow${r.buy ? ' sells' : ''}">` +
      `<span class="num h">${r.price.toLocaleString()}</span>` +
      `<span class="num raw">${r.buy ? 'buy' : 'sell'}</span>` +
      `<span class="nm">${esc(r.base_name)}</span>` +
      `<span class="nm">${esc(r.system)}</span></div>`).join('') +
    '</div></div>';
  return out;
}

async function loadTrade() {
  const q = tradeGood ? `?good=${encodeURIComponent(tradeGood)}` : '';
  try {
    const r = await fetch('api/trade' + q, { cache: 'no-store' });
    if (r.ok) { tradeData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}

function wireTrade() {
  const g = $('#tradegood');
  if (g) g.addEventListener('change', e => { tradeGood = e.target.value; loadTrade(); });
  const v = $('#tradeseen');
  if (v) v.addEventListener('change', e => {
    tradeVisitedOnly = e.target.checked;
    render();
  });
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


def _trade(ctx):
    """The commodity list, or every base trading one of them."""
    names, rows = ctx.game.market
    body = {"goods": [], "good": None, "rows": [], "error": None}
    try:
        counts = {}
        for row in rows:
            counts[row["good"]] = counts.get(row["good"], 0) + 1
        body["goods"] = sorted(
            ({"nickname": k, "name": names[k], "bases": counts.get(k, 0)}
             for k in names),
            key=lambda g: g["name"])
        want = (ctx.query.get("good") or [None])[0]
        if want and want.lower() in names:
            state = ctx.state()
            visited = set(state["docked_bases"])
            body["good"] = want.lower()
            body["rows"] = td.find(rows, want.lower(), visited)
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"trade": _trade}