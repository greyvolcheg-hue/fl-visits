"""Map → Jobs: the best-paying board in every system you have opened."""

ID, LABEL = "jobs", "Jobs"

CSS = """
  .jobtable { min-width: 48rem; }
  .jobtable .gun, .jobtable .gunhead {
    grid-template-columns: minmax(11rem, 1.4fr) minmax(8rem, 1fr) 3.6rem
                           6rem 6rem 4.5rem minmax(7rem, 1fr); }
  /* A row is a button in all but name: clicking one opens who is offering. */
  .board { cursor: pointer; }
  .board.on { border-color: var(--docked); }
  /* A base you have already landed on. The bar down the left is the same
     signal Equipment uses for a favourite, in the docked colour. */
  .board.been { border-left: 2px solid var(--docked); }
  .jobtable .gun .nm .been { color: var(--docked); font-family: var(--mono);
                             font-size: 9px; letter-spacing: .12em;
                             margin-left: .4rem; }
  .jobtable .gun .num.pay { color: var(--cyan-hi); font-weight: 600; }
  .boardwho .atrow .cell { width: 11rem; }
"""

JS = r"""
let jobsData = null, jobsSort = 'best', jobsDir = 'down',
    jobsAll = false, jobsDockedOnly = false, jobsOpen = '';

// Which columns exist, what they are called, and how each one is read off a
// row. The sort reads the same table, so a heading and the order it produces
// cannot drift apart: that is the bug this project shipped twice with grid
// columns and their cell lists living in two places.
const JOBCOLS = [
  ['system', 'system', r => r.system],
  ['at', 'cell', r => r.at],
  ['best', 'best job', r => r.best],
  ['floor', 'floor', r => r.floor],
  ['offers', 'on board', r => r.offers[1]],
  ['from', 'offered by', r => (r.board[0] || {}).short || ''],
];

function renderJobs() {
  const d = jobsData;
  if (!d) return '<p class="empty">reading the boards…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;

  const rows = d.rows
    .filter(r => jobsAll || r.open)
    .filter(r => !jobsDockedOnly || r.docked);
  const read = JOBCOLS.find(c => c[0] === jobsSort);
  const get = read ? read[2] : (r => r.best);
  // A stable second key, so two boards paying the same never swap places
  // between draws. Sorting on the page rather than at the endpoint: 160 rows
  // with no filter language is the Routes case, and the rows are already here.
  const sorted = rows.slice().sort((a, b) => {
    const x = get(a), y = get(b);
    const by = typeof x === 'string' ? String(x).localeCompare(String(y))
                                     : (Number(x) || 0) - (Number(y) || 0);
    return (jobsDir === 'down' ? -by : by) || a.name.localeCompare(b.name);
  });
  const arrow = k => k !== jobsSort ? '' : (jobsDir === 'down' ? ' ↓' : ' ↑');
  const money = v => Math.round(v).toLocaleString();

  let out = '<div class="reppick">' +
    '<label class="toggle"><input type="checkbox" id="joball"' +
    (jobsAll ? ' checked' : '') +
    '> <span>every system in Sirius, not just the ones I have opened</span></label>' +
    '<label class="toggle"><input type="checkbox" id="jobdocked"' +
    (jobsDockedOnly ? ' checked' : '') +
    '> <span>only bases I have docked at</span></label></div>';

  out += `<p class="note">${rows.length} board${rows.length === 1 ? '' : 's'}` +
    (jobsAll
      ? ` in all ${d.systems} systems that offer work`
      : ` in the ${d.open_systems} system${d.open_systems === 1 ? '' : 's'}
          you have opened, of ${d.total} in Sirius`) +
    `, by ${esc((read || ['', 'best job'])[1])}${jobsDir === 'down' ? ', biggest first' : ', smallest first'}.
     <b>best job</b> is what the richest faction on that board can offer at the
     top of its band, and <b>floor</b> is the least any of them can. What is
     actually pinned up when you walk in is drawn from between the two.
     Click any heading to sort by it, or any row for who is offering.</p>`;

  if (!sorted.length) return out + '<p class="empty">' + (jobsDockedOnly
    ? 'No base you have docked at runs a job board.'
    : 'No system you have opened has a job board in it yet.') + '</p>';

  out += '<div class="guns"><div class="jobtable">' +
    '<div class="gunhead"><span class="sortby nm" data-sort="name">base' +
    `${arrow('name')}</span>` +
    JOBCOLS.map(([k, label]) =>
      `<span class="sortby" data-sort="${esc(k)}">${esc(label)}${arrow(k)}</span>`
    ).join('') + '</div>' +
    sorted.map(r => {
      const open = r.id === jobsOpen;
      let line = '<div class="gun board' + (open ? ' on' : '') +
        (r.docked ? ' been' : '') + `" data-board="${esc(r.id)}">` +
        `<span class="nm">${esc(r.name)}` +
        (r.docked ? '<span class="been">DOCKED</span>' : '') + '</span>' +
        `<span class="num raw">${esc(r.system)}</span>` +
        `<span class="num raw">${esc(r.at)}</span>` +
        `<span class="num pay">${money(r.best)}</span>` +
        `<span class="num raw">${money(r.floor)}</span>` +
        `<span class="num raw">${r.offers[0]}-${r.offers[1]}</span>` +
        `<span class="num raw">${esc((r.board[0] || {}).short || '-')}` +
        (r.board.length > 1 ? ` +${r.board.length - 1}` : '') + '</span>' +
        '</div>';
      if (!open) return line;
      // Who is offering, in the same shape Equipment expands a row into its
      // dealers. The share is the weight this faction carries in the draw
      // against the others standing in the same bar.
      const who = r.board.map(j =>
        `<div class="atrow"><span class="cell">${esc(j.label)}</span>` +
        `<span class="num pay">${money(j.best)}</span>` +
        `<span class="loot">down to ${money(j.floor)}, ` +
        `${j.share}% of what comes up, ${esc(j.kind)}</span></div>`).join('');
      return line + `<div class="gearwhere boardwho">${who}</div>`;
    }).join('') +
    '</div></div>';
  return out;
}

function wireJobs() {
  const all = $('#joball');
  if (all) all.addEventListener('change', e => {
    jobsAll = e.target.checked; render();
  });
  const only = $('#jobdocked');
  if (only) only.addEventListener('change', e => {
    jobsDockedOnly = e.target.checked; render();
  });
  document.querySelectorAll('.jobtable .gunhead .sortby').forEach(h =>
    h.addEventListener('click', () => {
      const k = h.dataset.sort;
      // Same column twice flips the direction; a new one starts biggest first,
      // except the two that read as words, where A to Z is what you want.
      if (k === jobsSort) jobsDir = jobsDir === 'down' ? 'up' : 'down';
      else { jobsSort = k; jobsDir = (k === 'name' || k === 'system' ||
                                      k === 'at' || k === 'from') ? 'up' : 'down'; }
      render();
    }));
  document.querySelectorAll('.jobtable .board').forEach(row =>
    row.addEventListener('click', () => {
      jobsOpen = jobsOpen === row.dataset.board ? '' : row.dataset.board;
      render();
    }));
}

async function loadJobs() {
  try {
    const r = await fetch('api/jobs', { cache: 'no-store' });
    if (r.ok) { jobsData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}

VIEW.jobs = {
  bare: true,
  sub: 'what the best board you can reach is capable of paying',
  draw: renderJobs, wire: wireJobs,
  // Refetched on every entry, unlike Equipment's catalogue: which systems are
  // open is a fact about the save, and docking somewhere new between two looks
  // at this tab is exactly the thing it is for.
  open: () => loadJobs(),
};
"""
