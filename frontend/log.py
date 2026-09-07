"""Neural Net: the story log, the news wire, and what the bars are saying.

The endpoint is in `backend/log.py`.

Three sources behind three chips, labelled rather than merged, because they do
not behave alike. The save's log is what you wrote. The news is gated on the
story and genuinely grows as you play. The rumors never change at all, and the
panel says so rather than letting you wait for one to unlock.
"""

ID, LABEL = "log", "Neural Net"

CSS = """
  .logbar { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap;
            padding: .7rem 1rem; margin-bottom: .7rem; background: var(--panel);
            border: 1px solid var(--line); clip-path: var(--notch); }
  .logbar .count { color: var(--faint); font-family: var(--mono);
                   font-size: 11px; margin-left: auto; }
  .logbar .src { letter-spacing: .18em; }
  .logbar .sep { width: 1px; height: 1.1rem; background: var(--line); }
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
  /* A news row leads with when it broke, because that is the column the whole
     source exists to show. */
  .entry .when { display: flex; align-items: baseline; gap: .7rem;
                 font-family: var(--mono); font-size: 9.5px; letter-spacing: .16em;
                 color: var(--fainter); margin-bottom: .35rem; }
  .entry .when .state { color: var(--docked); }
  .entry .when .live { color: var(--ok); }
  .entry .when .past { color: var(--faint); }
  .entry .when .crit { color: var(--revealed); }
  .entry .head { font-size: 14px; font-weight: 600; color: var(--text);
                 letter-spacing: .02em; margin-bottom: .3rem; }
  .entry.past { border-left-color: var(--line); }
  .entry.past .head { color: var(--dim); }
  /* Rumors: who is talking, then what they said. */
  .entry .said { display: flex; align-items: baseline; gap: .7rem;
                 flex-wrap: wrap; margin-bottom: .3rem; }
  .entry .said .who { font-size: 13px; font-weight: 600; color: var(--text); }
  .entry .said .fac { border: 0; font-family: var(--mono); font-size: 10px;
                      letter-spacing: .12em; cursor: default; }
  .entry .said .at { margin-left: auto; font-family: var(--mono);
                     font-size: 10px; letter-spacing: .12em; color: var(--fainter); }
"""

JS = r"""
let logData = null, logSource = 'save';
let logNewestFirst = true, logPersonalOnly = true, logLiveOnly = false;
let logBase = '';

// Which entries are starred and which are read. One person's marks on their own
// machine, so localStorage owns them and the server never hears about it.
//
// A save key starts with a digit (netlog counts duplicates up from the oldest
// end, so `3:log = 22505,...`), which is why news and rumor keys carry a word
// prefix and cannot collide with one, and why marks made before the two other
// sources existed still find their entries.
let marks = { star: {}, read: {} };
try {
  const held = JSON.parse(localStorage.getItem('fl.netlog') || '{}');
  marks = { star: held.star || {}, read: held.read || {} };
} catch (e) {}

function saveMarks() {
  try { localStorage.setItem('fl.netlog', JSON.stringify(marks)); } catch (e) {}
}

function logActs(key) {
  const star = !!marks.star[key], done = !!marks.read[key];
  return '<div class="acts">' +
    `<button data-star="${esc(key)}" class="${star ? 'on' : ''}">` +
    `${star ? '★' : '☆'} interesting</button>` +
    `<button data-read="${esc(key)}" class="${done ? 'on done' : ''}">` +
    `${done ? '✓ read' : 'mark read'}</button></div>`;
}

function logClass(key, extra) {
  return ['entry', extra, marks.star[key] ? 'star' : '',
          marks.read[key] ? 'read' : ''].filter(Boolean).join(' ');
}

// --- the save's own log ---------------------------------------------------

function logSave(d) {
  const all = logNewestFirst ? d.save : d.save.slice().reverse();
  const rows = logPersonalOnly ? all.filter(e => e.personal) : all;
  const personal = all.filter(e => e.personal).length;
  const bar =
    `<button id="logsort">${logNewestFirst ? 'Newest first' : 'Oldest first'}</button>` +
    `<button id="logpersonal" class="${logPersonalOnly ? 'on' : ''}">` +
    `${logPersonalOnly ? '✓ ' : ''}Personal only (${personal})</button>`;
  const count = `${rows.length}` + (logPersonalOnly ? ` of ${all.length}` : '') +
    ' entries';
  if (!all.length) return [bar, count, '<p class="empty">The log is empty.</p>'];
  return [bar, count, rows.length ? rows.map(e => {
    const subs = e.subs.length
      ? `<ul class="subs">${e.subs.map(s => `<li>${esc(s)}</li>`).join('')}</ul>` : '';
    return `<div class="${logClass(e.key)}"><div class="body">${esc(e.text)}</div>` +
           subs + logActs(e.key) + '</div>';
  }).join('') : '<p class="empty">No personal entries yet.</p>'];
}

// --- the news wire --------------------------------------------------------

function logNews(d) {
  const all = logLiveOnly ? d.news.filter(e => e.live) : d.news;
  const live = d.news.filter(e => e.live).length;
  const bar = `<button id="loglive" class="${logLiveOnly ? 'on' : ''}">` +
    `${logLiveOnly ? '✓ ' : ''}On the wire now (${live})</button>` +
    `<span class="note" style="margin:0">${esc(d.state.label)} · newest first. ` +
    'Items above your state have not happened yet.</span>';
  const count = `${all.length} of ${d.news.length} opened`;
  if (!all.length) return [bar, count,
    '<p class="empty">Nothing has broken yet at this point in the story.</p>'];
  return [bar, count, all.map(e => {
    const key = 'news:' + e.debut + ':' + e.headline;
    return `<div class="${logClass(key, e.live ? '' : 'past')}">` +
      '<div class="when">' +
      `<span class="state">${esc(e.debut_label)}</span>` +
      `<span class="${e.live ? 'live' : 'past'}">` +
      `${e.live ? 'ON THE WIRE' : 'RAN UNTIL ' + esc(e.expires_label)}</span>` +
      (e.icon === 'critical' ? '<span class="crit">CRITICAL</span>' : '') +
      `<span>${e.carried} of your bases carry it</span></div>` +
      `<div class="head">${esc(e.headline)}</div>` +
      `<div class="body">${esc(e.text)}</div>` + logActs(key) + '</div>';
  }).join('')];
}

// --- what the bars are saying ---------------------------------------------

function logRumors(d) {
  const places = [...new Set(d.rumors.map(r => r.system + ' · ' + r.base))].sort();
  const rows = logBase ? d.rumors.filter(r => r.system + ' · ' + r.base === logBase)
                       : d.rumors;
  const bar = '<select id="logplace">' +
    '<option value="">every base I have docked at</option>' +
    places.map(p =>
      `<option value="${esc(p)}"${p === logBase ? ' selected' : ''}>` +
      `${esc(p)}</option>`).join('') +
    '</select>' +
    '<span class="note" style="margin:0">These never change with the story: ' +
    'all 7803 lines are on from the first minute. What changes is where you ' +
    'have been.</span>';
  const count = `${rows.length} lines at ${d.bases} bases`;
  if (!rows.length) return [bar, count,
    '<p class="empty">Dock somewhere and the people there start talking.</p>'];
  let out = '', place = null;
  rows.forEach(r => {
    const here = r.system + ' · ' + r.base;
    if (here !== place) {
      place = here;
      out += `<h2 class="house">${esc(here)}</h2>`;
    }
    const key = 'rumor:' + r.ids;
    out += `<div class="${logClass(key)}"><div class="said">` +
      `<span class="who">${esc(r.who || 'someone at the bar')}</span>` +
      `<span class="fac">${esc(r.faction)}</span>` +
      (r.room ? `<span class="at">${esc(r.room)}</span>` : '') + '</div>' +
      `<div class="body">${esc(r.text)}</div>` + logActs(key) + '</div>';
  });
  return [bar, count, out];
}

const LOG_SOURCE = { save: logSave, news: logNews, rumors: logRumors };

function renderLog() {
  const d = logData;
  if (!d) return '<p class="empty">reading the save…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;
  const [bar, count, body] = LOG_SOURCE[logSource](d);
  const chips = [['save', 'SAVE', d.save.length],
                 ['news', 'NEWS', d.news.length],
                 ['rumors', 'RUMORS', d.rumors.length]].map(([id, label, n]) =>
    `<button class="src ${id === logSource ? 'on' : ''}" data-src="${id}">` +
    `${label} ${n}</button>`).join('');
  return '<div class="logbar">' + chips + '<span class="sep"></span>' + bar +
    `<span class="count">${count} · marks live in your browser</span></div>` + body;
}

function wireLog() {
  document.querySelectorAll('.logbar .src').forEach(b =>
    b.addEventListener('click', () => { logSource = b.dataset.src; render(); }));
  const on = (id, fn) => { const b = $('#' + id); if (b) b.onclick = fn; };
  on('logsort', () => { logNewestFirst = !logNewestFirst; render(); });
  on('logpersonal', () => { logPersonalOnly = !logPersonalOnly; render(); });
  on('loglive', () => { logLiveOnly = !logLiveOnly; render(); });
  const place = $('#logplace');
  if (place) place.addEventListener('change', e => { logBase = e.target.value; render(); });
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
  bare: true,
  sub: 'the log, the wire, and what the bars are saying',
  draw: renderLog, wire: wireLog,
  open: loadLog,
  // The save grows while you fly, so this one is worth re-reading on the tick.
  poll: loadLog,
};
"""
