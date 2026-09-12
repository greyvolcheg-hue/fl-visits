"""Map → Best Path: the shortest way from one system to another."""

ID, LABEL = "bestpath", "Best Path"

CSS = """
  /* A route is a numbered list of jumps, not a table: the interesting part is
     the name of the thing to fly to, and the rest annotates it. */
  /* Capped rather than left to fill the window: the row is six short cells
     and stretching it puts the distance an inch from the name it belongs to. */
  .routeplan { margin-bottom: 1.1rem; max-width: 52rem; }
  .routeplan > h3 { font-family: var(--mono); font-size: 9.5px;
                    letter-spacing: .18em; text-transform: uppercase;
                    color: var(--fainter); margin: 0 0 .4rem; font-weight: 400; }
  .routeplan > h3 b { color: var(--cyan-hi); font-size: 12px; letter-spacing: 0;
                      font-family: var(--display); margin-left: .5rem; }
  .hop { display: grid; gap: .5rem; align-items: baseline;
         grid-template-columns: 1.6rem minmax(8rem, 1fr) 4.2rem
                                minmax(11rem, 1.4fr) 3rem 5rem;
         padding: .4rem .85rem; background: var(--card);
         border: 1px solid transparent; border-left: 2px solid var(--line);
         margin-bottom: .2rem; font-size: 12.5px; }
  .hop .n { color: var(--fainter); font-family: var(--mono); font-size: 11px; }
  /* **Not `.sys`.** That class is the system card in the theme and carries a
     border and a background, so a cell wearing it is drawn as a box. The
     spelling for a system's name inside a list is `.sysname`, the same one
     `rep.py` uses for the bribe bars. */
  .hop .sysname { color: var(--dim); }
  .hop .obj { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .hop .leg { text-align: right; font-family: var(--mono); font-size: 11px;
              color: var(--faint); }
  .hop .kind { font-family: var(--mono); font-size: 9px; letter-spacing: .12em; }
  .hop.gate { border-left-color: var(--docked); }
  .hop.gate .kind { color: var(--docked); }
  /* A hole you have not found is the one thing on this page you cannot simply
     fly to off the nav map, so it is the one thing marked in the warning ink. */
  .hop.hole { border-left-color: var(--revealed); }
  .hop.hole .kind { color: var(--revealed); }
  .hop.lost { border-left-color: var(--unknown); }
  .hop.lost .kind, .hop.lost .obj { color: var(--unknown); }
"""

JS = r"""
let pathData = null, pathFrom = '', pathTo = '',
    pathAll = false, pathGates = false;

const km = m => (m / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + ' km';

function hopRow(step, i) {
  // `lost` beats `hole`: what matters about a step you have not found is that
  // it is not on your map, not what kind of thing it is.
  const cls = !step.found ? 'lost' : step.kind === 'gate' ? 'gate' : 'hole';
  return `<div class="hop ${cls}"><span class="n">${i + 1}</span>` +
    `<span class="sysname">${esc(step.system)}</span>` +
    `<span class="cell">${esc(step.at)}</span>` +
    `<span class="obj">${esc(step.name)}</span>` +
    `<span class="kind">${step.found ? esc(step.kind) : 'unseen'}</span>` +
    `<span class="leg">${step.leg ? km(step.leg) : ''}</span></div>`;
}

function routeBlock(title, one) {
  return `<div class="routeplan"><h3>${title}<b>${one.hops} ` +
    `jump${one.hops === 1 ? '' : 's'}, ${km(one.flying)}</b></h3>` +
    one.steps.map(hopRow).join('') + '</div>';
}

function renderPath() {
  const d = pathData;
  if (!d) return '<p class="empty">reading the jump map…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;

  const opts = sel => d.systems.map(s =>
    `<option value="${esc(s.key)}"${s.key === sel ? ' selected' : ''}>` +
    `${esc(s.label)}</option>`).join('');
  let out = '<div class="reppick">' +
    `<select id="pathfrom"><option value="">departure system…</option>${opts(pathFrom)}</select>` +
    '<span class="sys">to</span>' +
    `<select id="pathto"><option value="">destination system…</option>${opts(pathTo)}</select>` +
    '<label class="toggle"><input type="checkbox" id="pathall"' +
    (pathAll ? ' checked' : '') +
    '> <span>every jump in the game, not just the ones I have found</span></label>' +
    '<label class="toggle"><input type="checkbox" id="pathgates"' +
    (pathGates ? ' checked' : '') +
    '> <span>jump gates only</span></label></div>';

  const scope = d.found_only
    ? `Routed over the <b>${d.known}</b> jumps this save has found, of ${d.total}
       in the game. A link counts as found when either of its two ends has been
       seen, because being shown the far side of a hole is knowing it is there.`
    : `Routed over all <b>${d.total}</b> jumps in the game, so a step marked
       <b>unseen</b> is one your nav map will not show you. The cell is still
       where it is.`;
  out += `<p class="note">${scope}
    Distance is raw flying between the jumps inside each system, in the game's
    own metres, and trade lanes are not in it. <b>It covers the systems in the
    middle only</b>: where you are in the one you leave, and where you are going
    in the one you arrive in, are not things a route between two systems knows.</p>`;

  if (!d.from || !d.to) return out + '<p class="empty">Pick both ends.</p>';
  if (d.from === d.to) return out + '<p class="empty">Same system both ends.</p>';
  if (!d.jumps && !d.flying)
    return out + '<p class="empty">' + (d.found_only
      ? `No way there over the ${d.known} jumps you have found. Tick the box to
         see the route over every jump in the game.`
      : (d.gates_only
         ? 'No way there on jump gates alone. Untick the box to allow holes.'
         : 'Nothing in the game joins those two. The five Omicron systems of the '
           + 'St group are a closed island and connect to nothing else.')) + '</p>';

  // The same route twice is one route. Saying so beats printing it again and
  // leaving the reader to diff two lists by eye.
  if (d.same) return out + routeBlock('fewest jumps and least flying, the same route', d.jumps);
  return out + routeBlock('fewest jumps', d.jumps) +
               routeBlock('least flying', d.flying);
}

function widePath() {
  const q = [];
  if (pathFrom) q.push('from=' + encodeURIComponent(pathFrom));
  if (pathTo) q.push('to=' + encodeURIComponent(pathTo));
  if (pathAll) q.push('all=1');
  if (pathGates) q.push('gates=1');
  return q.length ? '?' + q.join('&') : '';
}

async function loadPath() {
  try {
    const r = await fetch('api/bestpath' + widePath(), { cache: 'no-store' });
    if (r.ok) { pathData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}

function wirePath() {
  const f = $('#pathfrom'), t = $('#pathto'),
        a = $('#pathall'), g = $('#pathgates');
  if (f) f.addEventListener('change', e => { pathFrom = e.target.value; loadPath(); });
  if (t) t.addEventListener('change', e => { pathTo = e.target.value; loadPath(); });
  if (a) a.addEventListener('change', e => { pathAll = e.target.checked; loadPath(); });
  if (g) g.addEventListener('change', e => { pathGates = e.target.checked; loadPath(); });
}

VIEW.bestpath = {
  bare: true,
  sub: 'the shortest way from one system to another',
  draw: renderPath, wire: wirePath,
  // Refetched on entry, like Jobs and unlike Equipment: which jumps you have
  // found is a fact about the save, and finding one is the thing that changes
  // the answer.
  open: () => loadPath(),
};
"""
