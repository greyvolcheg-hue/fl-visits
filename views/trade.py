"""Trade → Data: who buys and sells what."""

import os

import trade as td


ID, LABEL = "data", "Data"

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


# One spelling of the empty hold. `_trade` seeds the payload with it and
# `_hold` returns it, so writing it out twice makes the payload's shape depend
# on which of the two ran.
NO_HOLD = {"items": [], "systems": [], "whole": 0, "saved": None}


def _docked(ctx, want):
    """Bases the player has docked at, or None if the save will not open.

    None rather than an empty set: an empty set is the claim "docked nowhere",
    which greys out every row on the page, and a save the game has not written
    yet makes no claim at all.

    Read only when something needs it. `read_state` walks every base in the
    game and the Neural Net log on top of the decode, and the first load of
    this tab wants neither the checkbox nor a row list.
    """
    if not want:
        return None
    try:
        return ctx.docked()
    except (OSError, ValueError):
        return None


def _hold(ctx, names, rows, only):
    """The hold and where to unload it, or an empty hold and no advice.

    A save that will not open costs the hold section and nothing else. The
    commodity picker and all 1786 market rows below it are static game data
    that never needed the save, and taking the whole tab down for a file the
    game has not written yet throws away the part that still works.
    `ships.player_ship` returns None on the same grounds.
    """
    out = dict(NO_HOLD)
    try:
        held = td.hold(ctx.saved(), names)
        saved_at = os.path.getmtime(ctx.save)
    except (OSError, ValueError):
        return out
    if not held:
        return out
    out["saved"] = saved_at
    out["items"] = sorted(
        ({"good": g, "name": names[g], "units": n} for g, n in held.items()),
        key=lambda i: -i["units"])
    runs = td.hold_runs(rows, held, only, names)
    # Counted over every run, not over the ten kept: 43 systems take a hold of
    # water, and a count taken after the slice can only ever say ten.
    out["whole"] = sum(1 for r in runs if not r["missing"])
    # Ten is well past where this stops being a decision: the eleventh-best
    # system is not somewhere anyone flies a full hold.
    out["systems"] = runs[:10]
    return out


def _trade(ctx):
    """The commodity list, or every base trading one of them."""
    names, rows = ctx.game.market
    body = {"goods": [], "good": None, "rows": [],
            "hold": dict(NO_HOLD), "error": None}
    try:
        want = (ctx.query.get("good") or [None])[0]
        want = want.lower() if want else None
        seen_only = bool((ctx.query.get("visited") or [""])[0])
        visited = _docked(ctx, seen_only or want in names)
        # The checkbox has to be answered here, not in the page. A row the
        # page hides is still a row, but the system the hold advice names was
        # chosen out of bases the page never received, so only this side can
        # choose it again. `_deltas` and `_routes` read the flag the same way.
        body["hold"] = _hold(ctx, names, rows, visited if seen_only else None)
        counts = {}
        for row in rows:
            counts[row["good"]] = counts.get(row["good"], 0) + 1
        body["goods"] = sorted(
            ({"nickname": k, "name": names[k], "bases": counts.get(k, 0)}
             for k in names),
            key=lambda g: g["name"])
        if want in names:
            body["good"] = want
            # Every row carries its own visited flag whatever the checkbox
            # says, so the table can re-filter itself without another request.
            body["rows"] = td.find(rows, want, visited)
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"trade": _trade}