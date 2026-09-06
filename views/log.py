"""Neural Net: the story log out of the save."""

ID, LABEL = "log", "Neural Net"

JS = r"""
let logNewestFirst = true, logPersonalOnly = true;

// Reputation tab. `repData` is whatever the server last worked out; `repOpen`
// is which action rows have their collateral expanded, by index, because the
// damage a plan does is the half people skip and it has to be one click away.

function renderLog(d) {
  const all = logNewestFirst ? d.log : d.log.slice().reverse();
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
VIEW.log = { bare: true, save: true, draw: renderLog, wire: wireLog };
"""
