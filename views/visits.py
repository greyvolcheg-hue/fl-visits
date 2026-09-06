"""Map → Visits: which bases you have docked at, by system."""

ID, LABEL = "visits", "Visits"

CSS = """
  /* The owning faction, dimmed and a size down so it reads as an annotation
     rather than a second name. The dotted underline advertises the hover. */
  .fac { color: var(--dim); font-size: .85em; border-bottom: 1px dotted var(--line);
         cursor: help; }
  .atlist { display: flex; flex-direction: column; gap: .15rem; }
  .atrow { display: flex; gap: .5rem; align-items: baseline; }
"""

JS = r"""
function line(cls, tag, items, withAt, withFac) {
  if (!items.length) return '';
  // `title` is the whole hover mechanism: no JS, and it works on a long press.
  const fac = b => (withFac && b.faction)
    ? ` <span class="fac" title="${esc(b.faction_full || b.faction)}">${esc(b.faction)}</span>`
    : '';
  // A middot once badges are on: each item is then two visually distinct
  // parts and a comma gets lost between them.
  const sep = withFac ? ' · ' : ', ';
  // Only unknown bases get coordinates, one per line. Docked and revealed are
  // findable without a cell reference, and the column would only add height.
  const body = withAt
    ? '<span class="atlist">' + items.map(b =>
        `<span class="atrow"><span class="cell">${esc(b.at)}</span>` +
        `<span>${esc(b.name)}${fac(b)}</span></span>`).join('') + '</span>'
    : `<span>${items.map(b => esc(b.name) + fac(b)).join(sep)}</span>`;
  return `<div class="row ${cls}"><span class="tag ${cls}">${tag} ${items.length}</span>` +
         body + '</div>';
}

VIEW.visits = {
  save: true,
  draw(d) {
    const ext = extended.visits;
    totals([[d.docked, 'docked'], [d.revealed, 'revealed'],
            [d.bases - d.docked - d.revealed, 'unknown'],
            [`${d.systems_touched}/${d.systems_total}`, 'systems']]);
    $('#extlabel').textContent = 'show every system and the bases you have not found';
    $('#hidelabel').textContent = 'hide systems where every base is docked at';
    foldOnFirstSight(d);
    // "Finished" is whatever the card's own counter calls done, so the toggle
    // agrees with the number being looked at.
    const rows = d.systems.filter(s => (ext || s.docked.length || s.revealed.length)
                                    && !(hideDone.visits && s.percent === 100));
    if (!rows.length) return '<p class="empty">' + (hideDone.visits
      ? 'Every system with anything in it is finished.'
      : 'Nothing docked at yet.') + '</p>';
    return byHouse(d, rows,
      s => card(s.system, s.docked.length, s.total, s.percent,
        line('d', 'docked', s.docked) + line('r', 'revealed', s.revealed, false, true) +
        (ext ? line('u', 'unknown', s.unknown, true) : '')),
      rs => [rs.reduce((n, s) => n + s.docked.length, 0),
             rs.reduce((n, s) => n + s.total, 0)]);
  },
};
"""
