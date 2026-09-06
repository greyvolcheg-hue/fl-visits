"""Map → Wrecks: which wrecks you have found and stripped."""

ID, LABEL = "wrecks", "Wrecks"

JS = r"""
function wreckLine(w, found) {
  // Three states, not two: a wreck you found but never opened still holds its
  // loot, and the game says so in bit 8 of the visit flag.
  const cls = !found ? 'm' : w.emptied ? 'f' : 'o';
  const mark = !found ? '-' : w.emptied ? '+' : '*';
  // Untouched loot is what you would collect, so it shows without the box.
  // For an emptied wreck it is history.
  const show = w.loot.length && (extended.wrecks || (found && !w.emptied));
  const loot = show
    ? `<span class="loot">${w.loot.map(([i, n]) => `${n}x ${esc(i)}`).join(', ')}</span>` : '';
  const where = [w.sector, w.spot].filter(Boolean).join(' ');
  return `<div class="wreck ${cls}"><span class="mark">${mark}</span>` +
         `<span class="cell">${esc(where)}</span>` +
         `<span class="nm">${esc(w.name)}</span>${loot}</div>`;
}

VIEW.wrecks = {
  save: true,
  draw(d) {
    totals([[d.wrecks_stripped, 'stripped'], [d.wrecks_open, 'still loaded'],
            [d.wrecks_total - d.wrecks_stripped - d.wrecks_open, 'left'],
            [`${d.wrecks_systems}/${d.wrecks_systems_total}`, 'systems']]);
    $('#extlabel').textContent =
      'show every system, the wrecks you have not found, and what they hold';
    $('#hidelabel').textContent = 'hide systems where every wreck is stripped';
    foldOnFirstSight(d);
    const ext = extended.wrecks;
    const rows = d.wrecks.filter(s => (ext || s.found.length)
                                   && !(hideDone.wrecks && s.percent === 100));
    if (!rows.length) return '<p class="empty">' + (hideDone.wrecks
      ? 'Every system with a wreck in it is stripped.'
      : 'No wrecks found yet. Tick the box to see where they are.') + '</p>';
    return byHouse(d, rows,
      s => card(s.system, s.stripped, s.total, s.percent,
        s.found.map(w => wreckLine(w, true)).join('') +
        (ext ? s.missing.map(w => wreckLine(w, false)).join('') : '')),
      rs => [rs.reduce((n, s) => n + s.stripped, 0),
             rs.reduce((n, s) => n + s.total, 0)]);
  },
};
"""
