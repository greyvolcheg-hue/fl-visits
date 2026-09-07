"""Map → Systems: every system, its bases and its wrecks, in one tree.

House, then system, then what is in it. Both levels start shut, because the
point of a tree is that you open the branch you are working on, not that you
scroll past 47 systems to reach it.

This replaces the separate Visits and Wrecks tabs. They asked the same question
about the same place and answered it in two lists that had to be read side by
side, and their two system rows had drifted into different shapes.
"""

ID, LABEL = "systems", "Systems"

CSS = """
  /* The owning faction, dimmed and a size down so it reads as an annotation
     rather than a second name. The dotted underline advertises the hover. */
  .fac { color: var(--dim); font-size: .85em; border-bottom: 1px dotted var(--line);
         cursor: help; }
  .atlist { display: flex; flex-direction: column; gap: .15rem; }
  .atrow { display: flex; gap: .5rem; align-items: baseline; }
  .sys.foldable > .head { cursor: pointer; user-select: none; }
  .sys.foldable > .head:hover b { color: var(--docked); }
  /* Wrecks sit under the bases, told apart by a rule rather than a heading:
     the marks already say which is which and a second heading per system
     would double the height of a shut-by-default tree. */
  .hulls { margin-top: .5rem; padding-top: .5rem; border-top: 1px solid var(--line); }
"""

JS = r"""
// Which systems are open. Shut is the default, so this holds the exceptions.
const openSys = {};

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

function wreckLine(w, found) {
  // Three states, not two: a wreck you found but never opened still holds its
  // loot, and the game says so in bit 8 of the visit flag.
  const cls = !found ? 'm' : w.emptied ? 'f' : 'o';
  const mark = !found ? '-' : w.emptied ? '+' : '*';
  // Untouched loot is what you would collect, so it shows without the box.
  // For an emptied wreck it is history.
  const show = w.loot.length && (extended.systems || (found && !w.emptied));
  const loot = show
    ? `<span class="loot">${w.loot.map(([i, n]) => `${n}x ${esc(i)}`).join(', ')}</span>` : '';
  const where = [w.sector, w.spot].filter(Boolean).join(' ');
  return `<div class="wreck ${cls}"><span class="mark">${mark}</span>` +
         `<span class="cell">${esc(where)}</span>` +
         `<span class="nm">${esc(w.name)}</span>${loot}</div>`;
}

function systemBody(s, ext) {
  const b = s.bases, w = s.wrecks;
  const hulls = w.found.map(x => wreckLine(x, true)).join('') +
                (ext ? w.missing.map(x => wreckLine(x, false)).join('') : '');
  return line('d', 'docked', b.docked) +
         line('r', 'revealed', b.revealed, false, true) +
         (ext ? line('u', 'unknown', b.unknown, true) : '') +
         (hulls ? `<div class="hulls">${hulls}</div>` : '');
}

VIEW.systems = {
  save: true,
  draw(d) {
    const ext = extended.systems;
    totals([[d.docked, 'docked'], [d.revealed, 'revealed'],
            [d.stripped, 'wrecks stripped'],
            [`${d.systems_done}/${d.systems_total}`, 'systems done']]);
    $('#extlabel').textContent =
      'show every system, the bases and wrecks you have not found, and what they hold';
    $('#hidelabel').textContent =
      'hide systems where every base is docked at and every wreck is stripped';
    foldOnFirstSight(d);
    const rows = d.systems.filter(s =>
      (ext || s.bases.docked.length || s.bases.revealed.length || s.wrecks.found.length)
      && !(hideDone.systems && s.done));
    if (!rows.length) return '<p class="empty">' + (hideDone.systems
      ? 'Every system you have opened is finished.'
      : 'Nothing found yet. Tick the box to see what is out there.') + '</p>';
    // One bar for the whole place: a system is a to-do list of bases and
    // wrecks together, and two bars per card would be two answers to one
    // question.
    return byHouse(d, rows, s => {
      const done = s.bases.done + s.wrecks.done;
      const total = s.bases.total + s.wrecks.total;
      const open = !!openSys[s.nickname];
      return card(s.system, done, total,
                  total ? Math.round(100 * done / total) : 0,
                  open ? systemBody(s, ext) : '',
                  { id: s.nickname, open });
    }, rs => [rs.reduce((n, s) => n + s.bases.done + s.wrecks.done, 0),
              rs.reduce((n, s) => n + s.bases.total + s.wrecks.total, 0)]);
  },
  wire() {
    document.querySelectorAll('.sys.foldable > .head').forEach(h =>
      h.addEventListener('click', () => {
        const id = h.parentElement.dataset.sys;
        if (openSys[id]) delete openSys[id]; else openSys[id] = true;
        render();
      }));
  },
};
"""
