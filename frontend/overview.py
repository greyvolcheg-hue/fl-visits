"""Overview: where you are, what is nearby, and what to do next.

The endpoint is in `backend/overview.py`.

Six panels and a pair of meters. Every one of them is a doorway: the numbers
are the Systems totals, the cargo rows are the Deltas answer for the base you
are standing on, the actions are the Reputation plan for whoever likes you
least. Nothing here is only on this page, which is the point — this is the
glance you take on undocking, not a seventh place to work.
"""

ID, LABEL = "overview", "Overview"

CSS = """
  .ovgrid { display: grid; gap: 12px; align-items: start;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
  .ovwide { grid-column: 1 / -1; }
  .ovpanel { border: 1px solid var(--line); background: var(--panel);
             padding: 14px 16px; clip-path: var(--notch);
             display: flex; flex-direction: column; gap: 8px; }
  .ovpanel.lift { background: var(--card-lift); padding: 20px 22px; gap: 26px;
                  border-color: rgba(111, 216, 255, .22);
                  display: grid;
                  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
  .ovhead { display: flex; align-items: baseline; gap: 10px;
            font-family: var(--mono); font-size: 10px; letter-spacing: .24em;
            color: var(--fainter); }
  .ovhead .what { min-width: 0; overflow: hidden; text-overflow: ellipsis;
                  white-space: nowrap; }
  .ovhead .more { margin-left: auto; flex: none; color: var(--docked);
                  cursor: pointer; }
  .ovhead .more:hover { color: var(--cyan-hi); }
  .meter { display: flex; flex-direction: column; gap: 9px; }
  .meter .top { display: flex; align-items: baseline; justify-content: space-between; }
  .meter .pct { font-family: var(--mono); font-size: 11px; color: var(--faint); }
  .meter .fig { display: flex; align-items: baseline; gap: 8px; }
  .meter .have { font-family: var(--mono); font-size: 40px; font-weight: 600;
                 line-height: 1; color: var(--cyan-hi);
                 text-shadow: 0 0 22px rgba(111, 216, 255, .5); }
  .meter .of { font-family: var(--mono); font-size: 19px; color: #4d6b7e; }
  .meter .why { font-size: 12px; color: var(--faint); line-height: 1.4; }
  .story .now { font-size: 20px; font-weight: 600; color: var(--text);
                letter-spacing: .03em; }
  .story .state { font-family: var(--mono); font-size: 10.5px;
                  letter-spacing: .12em; color: var(--faint); }
  .wherelist { display: grid; grid-template-columns: auto 1fr; gap: 4px 14px;
               align-items: baseline; }
  .wherelist .k { font-family: var(--mono); font-size: 9.5px; letter-spacing: .18em;
                  color: var(--fainter); }
  .wherelist .v { font-size: 13px; color: var(--text); }
  .wherelist .v.cyan { color: var(--cyan-hi); }
  .wherelist .v.ok { color: var(--ok); font-family: var(--mono); }
  .ovrow { display: flex; align-items: baseline; gap: 9px; padding: 4px 0;
           border-bottom: 1px dashed var(--line-soft); font-size: 12.5px; }
  .ovrow:last-child { border-bottom: 0; }
  .ovrow .mk { flex: none; width: 10px; font-family: var(--mono); }
  .ovrow .nm { flex: 1 1 auto; min-width: 0; overflow: hidden;
               text-overflow: ellipsis; white-space: nowrap; }
  .ovrow .kind { font-family: var(--mono); font-size: 10px; color: var(--fainter); }
  .ovrow .num { font-family: var(--mono); font-size: 12px; text-align: right;
                font-variant-numeric: tabular-nums; }
  .ovrow.unknown .mk { color: var(--unknown); }
  .ovrow.unknown .nm { color: #6a899c; }
  .ovrow.revealed .mk { color: var(--docked); }
  .ovrow.loaded .mk, .ovrow.loaded .kind { color: var(--revealed); }
  .ovrow .up { color: var(--ok); }
  .worst { display: flex; align-items: baseline; gap: 12px; }
  .worst .who { font-size: 15px; font-weight: 600; color: var(--text); }
  .worst .rep { font-family: var(--mono); font-size: 22px; font-weight: 600;
                color: var(--bad); margin-left: auto; }
  /* Four lines and a fade. A single campaign entry runs to 25 lines and this
     is the glance panel, not the log; the Neural Net tab is one click away and
     the OPEN link is right there in the heading. */
  .ovlog .body { font-size: 12.5px; line-height: 1.45; color: var(--dim);
                 padding: 6px 0; border-bottom: 1px dashed var(--line-soft);
                 display: -webkit-box; -webkit-box-orient: vertical;
                 -webkit-line-clamp: 4; overflow: hidden; }
  .ovlog .body:last-child { border-bottom: 0; }
  .ovlog .tag { width: auto; display: block; margin-bottom: 2px; }
  .ovlog .tag.p { color: var(--revealed); }
  .ovlog .tag.g { color: var(--fainter); }
"""

JS = r"""
let ovData = null;

function ovPanel(title, body, jump) {
  const more = jump
    ? `<span class="more" data-jump="${jump[0]}" data-leaf="${jump[1] || ''}">` +
      'OPEN →</span>' : '';
  return '<div class="ovpanel"><div class="ovhead">' +
         `<span class="what">${title}</span>${more}</div>${body}</div>`;
}

function ovMeters(ms) {
  return '<div class="ovpanel lift ovwide wrapgrid">' + ms.map(m =>
    '<div class="meter"><div class="top">' +
    `<span class="ovhead">${esc(m.label)}</span>` +
    `<span class="pct">${m.percent}%</span></div>` +
    `<div class="fig"><span class="have">${money(m.have)}</span>` +
    `<span class="of">/ ${money(m.total)}</span></div>` +
    `<div class="bar"><i style="width:${m.percent}%"></i></div>` +
    `<div class="why">${esc(m.note)}</div></div>`).join('') + '</div>';
}

function ovStory(s) {
  if (!s) return '';
  return ovPanel('STORY',
    `<div class="story"><div class="now">${esc(s.label)}</div>` +
    `<div class="state">${esc(s.state)} · state ${s.index} of ${s.total}</div>` +
    `<div class="bar"><i style="width:${Math.round(100 * s.index / s.total)}%"></i></div>` +
    '</div><p class="note">News on the wire is gated on this exact state, so ' +
    'the Neural Net tab shows a different set the moment it moves.</p>',
    ['log']);
}

function ovWhere(rows) {
  return ovPanel('WHERE I AM', '<div class="wherelist wrapgrid">' + rows.map(r =>
    `<span class="k">${esc(r.k)}</span>` +
    `<span class="v ${r.tone || ''}">${esc(r.v)}</span>`).join('') + '</div>');
}

function ovNear(n) {
  if (!n || !n.system) return ovPanel('UNFOUND NEARBY',
    '<p class="empty">Nothing to place you in yet.</p>');
  const body = n.rows.length
    ? n.rows.map(r =>
        `<div class="ovrow ${r.tone}"><span class="mk">${r.mark}</span>` +
        `<span class="nm">${esc(r.name)}</span>` +
        `<span class="kind">${esc(r.kind)}</span>` +
        `<span class="cell">${esc(r.at)}</span></div>`).join('')
    : '<p class="empty">This system is closed out. Nothing left here.</p>';
  return ovPanel(`UNFOUND NEARBY · ${esc(n.system)}`, body, ['map', 'systems']);
}

function ovCargo(c) {
  if (!c) return '';
  if (!c.base) return ovPanel('BEST CARGO FROM HERE',
    '<p class="empty">You are in flight. Dock somewhere and this fills in.</p>');
  const body = c.rows.length
    ? c.rows.map(r =>
        `<div class="ovrow"><span class="nm">${esc(r.name)}</span>` +
        `<span class="kind">${esc(r.to)}</span>` +
        `<span class="num up">+${money(r.diff)}</span></div>`).join('') +
      '<p class="note">Per unit, and only to bases you have already docked at. ' +
      'A run you cannot fly is not advice.</p>'
    : `<p class="empty">${esc(c.note || 'Nothing worth carrying from here.')}</p>`;
  return ovPanel(`BEST CARGO FROM ${esc(c.base).toUpperCase()}`, body,
                 ['trade', 'deltas']);
}

function ovStanding(s) {
  if (!s || !s.faction) return '';
  return ovPanel('WORST STANDING',
    `<div class="worst"><span class="who">${esc(s.faction)}</span>` +
    `<span class="rep">${s.rep}</span></div>` +
    s.rows.map(r =>
      `<div class="ovrow"><span class="nm">${esc(r.what)}</span>` +
      `<span class="kind">${esc(r.side)}</span>` +
      `<span class="num">${esc(r.count)}</span></div>`).join('') +
    '<p class="note">What it takes to reach neutral, cheapest first. ' +
    '<b>+n / −n</b> is how many other factions each one helps and hurts.</p>',
    ['rep']);
}

function ovLog(rows) {
  if (!rows || !rows.length) return '';
  return ovPanel('NEURAL NET · LATEST', '<div class="ovlog">' + rows.map(e =>
    `<div class="body"><span class="tag ${e.personal ? 'p' : 'g'}">` +
    `${e.personal ? '*PERSONAL ENTRY' : 'BRIEFING'}</span>` +
    `${esc(e.text.replace(/^\*PERSONAL ENTRY:?\s*/i, ''))}</div>`).join('') +
    '</div>', ['log']);
}

function renderOverview() {
  const d = ovData;
  if (!d) return '<p class="empty">reading the save…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;
  return '<div class="ovgrid wrapgrid">' + ovMeters(d.meters) + ovStory(d.story) +
    ovWhere(d.where) + ovNear(d.near) + ovCargo(d.cargo) +
    ovStanding(d.standing) + ovLog(d.log) + '</div>';
}

function wireOverview() {
  document.querySelectorAll('.ovhead .more').forEach(b =>
    b.addEventListener('click', () =>
      go(b.dataset.jump, b.dataset.leaf || undefined)));
}

async function loadOverview() {
  try {
    const r = await fetch('api/overview', { cache: 'no-store' });
    if (r.ok) { ovData = await r.json(); render(); }
  } catch (e) { /* the panel keeps its loading line */ }
}

VIEW.overview = {
  bare: true,
  sub: 'SIRIUS SECTOR / FL-VISITS',
  draw: renderOverview, wire: wireOverview,
  open: loadOverview, poll: loadOverview,
};
"""
