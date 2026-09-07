"""Neural Net: the story log out of the save.

The endpoint is in `backend/log.py`.
"""

ID, LABEL = "log", "Neural Net"

CSS = """
  .logbar { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap;
            padding: .7rem 1rem; margin-bottom: .7rem; background: var(--panel);
            border: 1px solid var(--line); clip-path: var(--notch); }
  .logbar .count { color: var(--faint); font-family: var(--mono);
                   font-size: 11px; margin-left: auto; }
  .entry { background: var(--panel); border: 1px solid var(--line-soft);
           border-left: 2px solid transparent; padding: .8rem 1rem;
           margin-bottom: .3rem; }
  .entry.read { opacity: .45; }
  .entry.star { border-left-color: var(--revealed); }
  .entry .body { white-space: pre-wrap; overflow-wrap: anywhere;
                 font-size: 12.5px; line-height: 1.5; max-width: 96ch; }
  .entry .subs { margin: .5rem 0 0; padding-left: 1rem; color: var(--faint);
                 font-size: 11.5px; }
  .entry .acts { display: flex; gap: .35rem; margin-top: .6rem; }
  .entry .acts button { padding: .15rem .6rem; font-size: 9.5px; }
  .entry .acts button.on.done { background: rgba(95, 224, 160, .12);
                                border-color: rgba(95, 224, 160, .4);
                                color: var(--ok); }
"""

JS = r"""
let logData = null, logNewestFirst = true, logPersonalOnly = true;

// Which entries are starred and which are read. One person's marks on their own
// machine, so localStorage owns them and the server never hears about it.
let marks = { star: {}, read: {} };
try {
  const held = JSON.parse(localStorage.getItem('fl.netlog') || '{}');
  marks = { star: held.star || {}, read: held.read || {} };
} catch (e) {}

function saveMarks() {
  try { localStorage.setItem('fl.netlog', JSON.stringify(marks)); } catch (e) {}
}

function renderLog() {
  const d = logData;
  if (!d) return '<p class="empty">reading the save…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;
  const all = logNewestFirst ? d.entries : d.entries.slice().reverse();
  const rows = logPersonalOnly ? all.filter(e => e.personal) : all;
  const personal = all.filter(e => e.personal).length;
  if (!all.length) return '<p class="empty">The log is empty.</p>';
  const starred = rows.filter(e => marks.star[e.key]).length;
  const read = rows.filter(e => marks.read[e.key]).length;
  return '<div class="logbar">' +
    `<button id="logsort">${logNewestFirst ? 'Newest first' : 'Oldest first'}</button>` +
    `<button id="logpersonal" class="${logPersonalOnly ? 'on' : ''}">` +
    `${logPersonalOnly ? '✓ ' : ''}Personal only (${personal})</button>` +
    `<span class="count">${rows.length}` +
    (logPersonalOnly ? ` of ${all.length}` : '') +
    ` entries · ${starred} interesting · ${read} read</span></div>` +
    (rows.length ? '' : '<p class="empty">No personal entries yet.</p>') +
    rows.map(e => {
      const star = !!marks.star[e.key], done = !!marks.read[e.key];
      const cls = ['entry', star ? 'star' : '', done ? 'read' : ''].filter(Boolean).join(' ');
      const subs = e.subs.length
        ? `<ul class="subs">${e.subs.map(s => `<li>${esc(s)}</li>`).join('')}</ul>` : '';
      const key = esc(e.key);
      return `<div class="${cls}"><div class="body">${esc(e.text)}</div>${subs}` +
        `<div class="acts">` +
        `<button data-star="${key}" class="${star ? 'on' : ''}">` +
        `${star ? '★' : '☆'} interesting</button>` +
        `<button data-read="${key}" class="${done ? 'on done' : ''}">` +
        `${done ? '✓ read' : 'mark read'}</button></div></div>`;
    }).join('');
}

function wireLog() {
  const sort = $('#logsort');
  if (sort) sort.addEventListener('click', () => {
    logNewestFirst = !logNewestFirst;
    render();
  });
  const only = $('#logpersonal');
  if (only) only.addEventListener('click', () => {
    logPersonalOnly = !logPersonalOnly;
    render();
  });
  const flip = (which, key) => {
    if (marks[which][key]) delete marks[which][key];
    else marks[which][key] = true;
    saveMarks();
    render();
  };
  document.querySelectorAll('[data-star]').forEach(b =>
    b.addEventListener('click', () => flip('star', b.dataset.star)));
  document.querySelectorAll('[data-read]').forEach(b =>
    b.addEventListener('click', () => flip('read', b.dataset.read)));
}
async function loadLog() {
  try {
    const r = await fetch('api/log', { cache: 'no-store' });
    if (r.ok) { logData = await r.json(); render(); }
  } catch (e) { /* the tab keeps its loading line */ }
}

VIEW.log = {
  bare: true, draw: renderLog, wire: wireLog,
  open: loadLog,
  // The save grows while you fly, so this one is worth re-reading on the tick.
  poll: loadLog,
};
"""
