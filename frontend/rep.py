"""Reputation: what it takes to change how a faction feels."""

ID, LABEL = "rep", "Reputation"

CSS = """
  .reptable { min-width: 42rem; }
  .reptable .gun, .reptable .gunhead {
    grid-template-columns: minmax(14rem, 1fr) 5rem 4rem 14rem; }
  .reprow { cursor: pointer; }
  .reprow .others { text-align: left; color: var(--faint); font-size: 11px;
                    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .reprow:hover { border-color: var(--docked); }
  .repwhy { margin: -.1rem 0 .5rem 1rem; padding-left: .9rem;
            border-left: 2px solid var(--line); }
  .repline { display: grid; gap: .5rem; padding: .1rem 0; font-size: 11.5px;
             font-family: var(--mono);
             grid-template-columns: minmax(12rem, 1fr) 4.5rem 4.5rem 4.5rem; }
  .repline .nm { color: var(--faint); font-family: var(--display); }
  .repline span:not(.nm) { text-align: right; }
  .rephead { color: var(--fainter); font-family: var(--mono); font-size: 9.5px;
             letter-spacing: .18em; text-transform: uppercase; padding-bottom: .1rem; }
  .rephead .nm { text-align: left; }

  /* Where a bribe can actually be bought. A plain list rather than a table:
     it is three facts per line and the middle one is a four-character cell. */
  .repbars { display: flex; flex-direction: column; gap: .15rem;
             margin-bottom: .5rem; }
  .repbars .atrow .cell { width: 4rem; }
  .repbars .sysname { color: var(--dim); font-size: 11.5px; min-width: 9rem; }
"""

JS = r"""
let repData = null, repTarget = '', repGoal = 'neutral';
// Trade tab. The commodity list arrives once; the rows come per commodity,
// because 1994 of them is more than the page needs at any one moment.

const repOpen = {};

// The write-to-files button on the Speed tab. Not remembered anywhere: it
// reports the last press and nothing more.

function renderRep() {
  const d = repData;
  if (!d) return '<p class="empty">reading the save…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;

  const opts = d.factions.map(f =>
    `<option value="${esc(f.nickname)}"${f.nickname === repTarget ? ' selected' : ''}>` +
    `${esc(f.name)} (${f.current >= 0 ? '+' : ''}${f.current.toFixed(2)})</option>`).join('');
  const goals = d.goals.map(g =>
    `<option value="${g}"${g === repGoal ? ' selected' : ''}>${g}</option>`).join('');
  let out = '<div class="reppick">' +
    `<select id="reptarget"><option value="">pick a faction…</option>${opts}</select>` +
    `<select id="repgoal">${goals}</select></div>`;

  if (!d.target) return out + '<p class="empty">Pick a faction and a target standing.</p>';

  const head = `<p class="note">${esc(nameOf(d, d.target))} is at ` +
    `<b>${d.current >= 0 ? '+' : ''}${d.current.toFixed(2)}</b>, ` +
    `you want <b>${d.goal}</b>. Gap ${d.needed >= 0 ? '+' : ''}${d.needed.toFixed(2)}.</p>`;
  if (!d.rows.length)
    return out + head + '<p class="empty">Already there. Nothing to do.</p>';

  const bribes = d.rows.filter(r => r.event === 'bribe').length;
  out += head + `<p class="note">${d.rows.length - bribes} of 220 repeatable
    actions move it the right way${bribes ? ', plus a bribe' : ''}, all listed.
    Counts are rounded up, so the last one takes you past the goal rather than
    onto it. <b>+n/-n</b> is how many other factions the run helps and hurts;
    click a row for the full list.</p>`;

  out += '<div class="guns"><div class="reptable">' +
    '<div class="gunhead"><span class="nm">action</span><span>each</span>' +
    '<span>times / cost</span><span class="othershead">side effects</span></div>' +
    d.rows.map((r, i) => {
      const loss = r.collateral.filter(c => c.change < 0);
      const gain = r.collateral.filter(c => c.change > 0);
      // Spelled out. Read as "+2/-21 Bretonia -0.280" the middle number looks
      // like it belongs to the name, and the owner read a fall as a rise.
      const worst = loss.length
        ? `, worst hit ${esc(loss[0].name)} ${loss[0].change.toFixed(2)}` : '';
      // A bribe row opens with where to buy it, because that is the thing the
      // row does not already say. The collateral table follows, the same for
      // every row.
      const bars = (repOpen[i] && r.event === 'bribe')
        ? (r.bases.length
            ? '<div class="rephead">buy it at</div><div class="repbars">' + r.bases.map(b =>
                `<div class="atrow"><span class="sysname">${esc(b.system)}</span>` +
                `<span class="cell">${esc(b.at)}</span>` +
                `<span>${esc(b.name)}</span></div>`).join('') + '</div>'
            : `<p class="empty">${r.bases_total} bases in Sirius will take this
               bribe and you have docked at none of them. Nothing to buy until
               you have landed on one.</p>`)
        : '';
      const body = repOpen[i] ? '<div class="repwhy">' + bars +
        '<span class="repline rephead"><span class="nm">also moves</span>' +
        '<span>now</span><span>after</span><span>change</span></span>' +
        r.collateral.map(c =>
        `<span class="repline"><span class="nm">${esc(c.name)}` +
        (c.pinned ? ' <span class="loot">pinned</span>' : '') + '</span>' +
        `<span class="num raw">${c.before >= 0 ? '+' : ''}${c.before.toFixed(2)}</span>` +
        `<span class="num raw">${c.after >= 0 ? '+' : ''}${c.after.toFixed(2)}</span>` +
        `<span class="num ${c.change < 0 ? 's' : 'h'}">` +
        `${c.change >= 0 ? '+' : ''}${c.change.toFixed(2)}</span></span>`).join('')
        + '</div>' : '';
      return `<div class="gun reprow" data-row="${i}">` +
        `<span class="nm">${esc(r.event_label)} &middot; ${esc(r.doer_name)}` +
        // Bases, not bartenders. Two bartenders on one station is still one
        // trip, and the count that used to sit here answered "can I bribe at
        // all" where this answers "and where".
        (r.event === 'bribe'
          ? ` <span class="loot">${r.bases.length} of ${r.bases_total} bases</span>`
          : '') +
        (r.legality ? ` <span class="loot">${esc(r.legality)}</span>` : '') + '</span>' +
        // Standings round to two, but not this: 18 of the 69 Corsair rows are
        // worth under 0.005 a go and would all read +0.00, turning "142 times"
        // into nonsense. The small numbers here are the whole reason the repeat
        // counts are large.
        `<span class="num raw">${r.effect >= 0 ? '+' : ''}${r.effect.toFixed(4)}</span>` +
        `<span class="num h">${r.price ? r.price.toLocaleString() + ' cr' : r.repeats}</span>` +
        `<span class="others">${gain.length} up, ${loss.length} down${worst}</span>` +
        '</div>' + body;
    }).join('') + '</div></div>';
  return out;
}

function nameOf(d, nick) {
  const f = d.factions.find(x => x.nickname === nick);
  return f ? f.name : nick;
}

async function loadRep() {
  const q = repTarget ? `?to=${encodeURIComponent(repTarget)}&goal=${repGoal}` : '';
  try {
    const r = await fetch('api/reputation' + q, { cache: 'no-store' });
    if (r.ok) { repData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}

function wireRep() {
  const t = $('#reptarget'), g = $('#repgoal');
  if (t) t.addEventListener('change', e => {
    repTarget = e.target.value;
    for (const k in repOpen) delete repOpen[k];
    loadRep();
  });
  if (g) g.addEventListener('change', e => {
    repGoal = e.target.value;
    for (const k in repOpen) delete repOpen[k];
    loadRep();
  });
  document.querySelectorAll('.reprow').forEach(b =>
    b.addEventListener('click', () => {
      const i = b.dataset.row;
      repOpen[i] = !repOpen[i];
      render();
    }));
}
VIEW.rep = {
  bare: true,
  sub: 'what it takes to change how a faction feels',
  draw: renderRep, wire: wireRep,
  open: () => { if (!repData) loadRep(); },
};
"""
