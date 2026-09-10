"""Neural Net: the story log, the news wire, and what the bars are saying.

The endpoint is in `backend/log.py`.

**One list, three sources, and the chips narrow it.** They used to be three
sub-views behind an exclusive switch, each with its own renderer and its own
bar, which meant three places to add a filter and no way to ask "what have I
not read". They are now filters on one list: all three on is the default, and
a chip takes one away.

The three do not share a clock and the panel says so rather than inventing
one. The save's log has no date at all, only its position. News is dated by
the story state it broke at. Bar talk carries no date either, but the save
records the order you first docked at each base, so it is ranked by which bar
you walked into last. Each stream is therefore in true receipt order, and the
streams sit one after another because nothing joins them end to end.
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
  /* No measure of its own. The border is the container, and a cap here left
     the prose stopping some 800px short of its own frame on a wide window. */
  .entry .body { white-space: pre-wrap; overflow-wrap: anywhere;
                 font-size: 12.5px; line-height: 1.5; }
  .entry .subs { margin: .5rem 0 0; padding-left: 1rem; color: var(--faint);
                 font-size: 11.5px; }
  .entry .acts { display: flex; gap: .35rem; margin-top: .6rem; }
  .entry .acts button { padding: .15rem .6rem; font-size: 9.5px; }
  .entry .acts button.on.done { background: rgba(95, 224, 160, .12);
                                border-color: rgba(95, 224, 160, .4);
                                color: var(--ok); }
  /* Every row leads with the same line: which stream it came from, then
     whatever that stream has to say about when. One structure for three
     sources is what lets one function draw all of them. */
  .entry .when { display: flex; align-items: baseline; gap: .7rem;
                 flex-wrap: wrap;
                 font-family: var(--mono); font-size: 9.5px; letter-spacing: .16em;
                 color: var(--fainter); margin-bottom: .35rem; }
  .entry .when .state { color: var(--docked); }
  .entry .when .live { color: var(--ok); }
  .entry .when .past { color: var(--faint); }
  .entry .when .crit { color: var(--revealed); }
  .entry .when .again { color: var(--amber-dim); }
  /* The stream badge. Dim by design: with the streams contiguous under their
     own headings this is for the reader who has scrolled past one, not a
     label anybody needs to read on every row. */
  .srctag { flex: none; color: #4d7d96; border: 1px solid var(--line);
            padding: 0 .35rem; }
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
  h2.house.stream { color: var(--docked); }
"""

JS = r"""
let logData = null;
// Which streams are in the list. All three is the combined view, and a chip
// takes one away rather than switching to it.
const logOn = { save: true, news: true, rumors: true };
const SOURCES = ['save', 'news', 'rumors'];
const SRC_LABEL = { save: 'SAVE', news: 'NEWS', rumors: 'BAR TALK' };
let logNewestFirst = true, logPersonalOnly = true, logLiveOnly = false;
let logUnreadOnly = false;
let logBase = '';

// Which entries are starred and which are read. One person's marks on their own
// machine, and **the server keeps them now**, not `localStorage`.
//
// A save key starts with a digit (netlog counts duplicates up from the oldest
// end, so `3:log = 22505,...`), which is why news and rumor keys carry a word
// prefix and cannot collide with one, and why marks made before the two other
// sources existed still find their entries.
//
// `localStorage` lost them, and not by corrupting anything: it is scoped to a
// browsing context, so a container tab, a second profile and a second browser
// each hold their own invisible copy. See `backend/common.py` for the full
// account. This is a cache of what the server said, never the owner of it.
let marks = { star: {}, read: {} };

// A toggle in flight beats the poll. `loadLog` runs every five seconds, so a
// payload prepared before the POST landed would hand back the old value and the
// mark would visibly flip itself back. Same guard, and the same reason, as the
// slider under a thumb in `frontend/engine.py`.
let marksHeld = 0;
const MARKS_HOLD = 3000;
const marksBusy = () => Date.now() - marksHeld < MARKS_HOLD;

// The one-time carry-over. Whatever this browsing context still holds is folded
// into the server's set, once, and the flag stops it happening again. It is a
// union, so every context that ever held marks can contribute its own, and the
// `localStorage` copy is deliberately left where it is: it costs nothing and it
// is the only fallback if the file is ever lost.
async function importOldMarks() {
  let held = null;
  try {
    if (localStorage.getItem('fl.netlog.pushed')) return false;
    held = JSON.parse(localStorage.getItem('fl.netlog') || 'null');
  } catch (e) { return false; }
  if (!held || (!held.star && !held.read)) return false;
  try {
    const r = await fetch('api/marks', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ import: held }),
    });
    if (!r.ok) return false;
    const got = await r.json();
    if (got.marks) marks = got.marks;
  } catch (e) { return false; }
  try { localStorage.setItem('fl.netlog.pushed', '1'); } catch (e) {}
  return true;
}

async function postMark(kind, key, on) {
  marksHeld = Date.now();
  try {
    const r = await fetch('api/marks', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: kind, key: key, on: on }),
    });
    if (r.ok) {
      const got = await r.json();
      if (got.marks) marks = got.marks;
    }
  } catch (e) {
    // The mark stays where the click put it. The next payload corrects it.
  }
  // **The hold is released by the caller, not here.** A row with two keys posts
  // twice, and clearing it after the first would open a window for the poll to
  // land holding the value the second write has not reached yet.
}

// **A row can answer to more than one key.** A news item filed twice under two
// story windows has a mark key per filing, and `news.py` folds those copies
// into one row. Reading the whole list is what stops the fold taking the mark
// with it: nine of the marks on this machine sat on a key that would otherwise
// have vanished.
const marked = (which, keys) => keys.some(k => !!marks[which][k]);

// Every drawn row's key list, by index. A button carries the index, so a key
// never has to survive being written into an HTML attribute.
let logKeys = [];

function logActs(keys) {
  const at = logKeys.push(keys) - 1;
  const star = marked('star', keys), done = marked('read', keys);
  return '<div class="acts">' +
    `<button data-star="${at}" class="${star ? 'on' : ''}">` +
    `${star ? '★' : '☆'} interesting</button>` +
    `<button data-read="${at}" class="${done ? 'on done' : ''}">` +
    `${done ? '✓ read' : 'mark read'}</button></div>`;
}

function logClass(keys, extra) {
  return ['entry', extra, marked('star', keys) ? 'star' : '',
          marked('read', keys) ? 'read' : ''].filter(Boolean).join(' ');
}

// --- three builders, one row shape ----------------------------------------
//
// Each source turns its own payload into the same object, and one renderer
// draws it. That is the whole of the merge: `src` picks the badge, `keys` are
// what the marks hang on, and `lead`, `title` and `body` are html the builder
// has already escaped. `place` is the heading a row sits under, or nothing.

function saveRows(d) {
  const all = logNewestFirst ? d.save : d.save.slice().reverse();
  const rows = logPersonalOnly ? all.filter(e => e.personal) : all;
  return rows.map(e => ({
    src: 'save', keys: [e.key], cls: '', place: '', lead: '', title: '',
    body: `<div class="body">${esc(e.text)}</div>` + (e.subs.length
      ? `<ul class="subs">${e.subs.map(s => `<li>${esc(s)}</li>`).join('')}</ul>` : ''),
  }));
}

function newsRows(d) {
  const open = logLiveOnly ? d.news.filter(e => e.live) : d.news;
  // The payload arrives newest debut first, so oldest first is that reversed.
  // `debut` is the story state the item opens at, which is the only date news
  // has: the wire carries no clock.
  const all = logNewestFirst ? open : open.slice().reverse();
  return all.map(e => ({
    src: 'news',
    keys: e.debuts.map(n => 'news:' + n + ':' + e.headline),
    cls: e.live ? '' : 'past',
    place: '',
    lead: `<span class="state">${esc(e.debut_label)}</span>` +
      `<span class="${e.live ? 'live' : 'past'}">` +
      `${e.live ? 'ON THE WIRE' : 'RAN UNTIL ' + esc(e.expires_label)}</span>` +
      (e.icon === 'critical' ? '<span class="crit">CRITICAL</span>' : '') +
      (e.runs > 1 ? `<span class="again">FILED ${e.runs}x</span>` : '') +
      `<span>${e.carried} of your bases carry it</span>`,
    title: `<div class="head">${esc(e.headline)}</div>`,
    body: `<div class="body">${esc(e.text)}</div>`,
  }));
}

function rumorRows(d) {
  const picked = logBase
    ? d.rumors.filter(r => r.system + ' · ' + r.base === logBase) : d.rumors;
  // The payload arrives most recently docked first: `seen` is the base's rank
  // in the save's own `base_visited`, which is the order the bars were walked
  // into. See `backend/log.py`.
  const all = logNewestFirst ? picked : picked.slice().reverse();
  return all.map(r => ({
    src: 'rumors', keys: ['rumor:' + r.ids], cls: '',
    place: r.system + ' · ' + r.base,
    lead: r.room ? `<span>${esc(r.room)}</span>` : '',
    title: '<div class="said">' +
      `<span class="who">${esc(r.who || 'someone at the bar')}</span>` +
      `<span class="fac">${esc(r.faction)}</span></div>`,
    body: `<div class="body">${esc(r.text)}</div>`,
  }));
}

const BUILD = { save: saveRows, news: newsRows, rumors: rumorRows };

function logRows(d) {
  let out = [];
  SOURCES.forEach(s => { if (logOn[s]) out = out.concat(BUILD[s](d)); });
  return out;
}

// --- the one renderer ------------------------------------------------------

function logDraw(rows, streams) {
  logKeys = [];
  let out = '', stream = null, place = null;
  rows.forEach(r => {
    if (r.src !== stream) {
      stream = r.src;
      place = null;
      if (streams > 1) out += `<h2 class="house stream">${SRC_LABEL[r.src]}</h2>`;
    }
    if (r.place && r.place !== place) {
      place = r.place;
      out += `<h2 class="house">${esc(r.place)}</h2>`;
    }
    out += `<div class="${logClass(r.keys, r.cls)}">` +
      `<div class="when"><span class="srctag">${SRC_LABEL[r.src]}</span>` +
      r.lead + '</div>' + r.title + r.body + logActs(r.keys) + '</div>';
  });
  return out;
}

// What the panel says about the order it is in. Only for the streams actually
// on: a sentence about news is noise while news is switched off.
function logWhy(streams) {
  const bits = [];
  if (logOn.save) bits.push('the save log carries no date at all, only its place in the file');
  if (logOn.news) bits.push('news is dated by the story state it broke at');
  if (logOn.rumors) bits.push('bar talk is ranked by the order you first docked there');
  if (streams < 2) return bits[0] ? bits[0][0].toUpperCase() + bits[0].slice(1) + '.' : '';
  return 'Each stream is in true order and the three are not interleaved, ' +
    'because they share no clock: ' + bits.join(', ') + '.';
}

function renderLog() {
  const d = logData;
  if (!d) return '<p class="empty">reading the save…</p>';
  if (d.error) return `<p class="note warn">${esc(d.error)}</p>`;

  const streams = SOURCES.filter(s => logOn[s]).length;
  const all = logRows(d);
  const unread = all.filter(r => !marked('read', r.keys)).length;
  const rows = logUnreadOnly ? all.filter(r => !marked('read', r.keys)) : all;

  const chips = SOURCES.map(id =>
    `<button class="src ${logOn[id] ? 'on' : ''}" data-src="${id}">` +
    `${SRC_LABEL[id]} ${d[id].length}</button>`).join('');

  let bar =
    `<button id="logsort">${logNewestFirst ? 'Newest first' : 'Oldest first'}</button>` +
    `<button id="logunread" class="${logUnreadOnly ? 'on' : ''}">` +
    `${logUnreadOnly ? '✓ ' : ''}Unread only (${unread})</button>`;
  if (logOn.save) {
    const personal = d.save.filter(e => e.personal).length;
    bar += `<button id="logpersonal" class="${logPersonalOnly ? 'on' : ''}">` +
      `${logPersonalOnly ? '✓ ' : ''}Personal only (${personal})</button>`;
  }
  if (logOn.news) {
    const live = d.news.filter(e => e.live).length;
    bar += `<button id="loglive" class="${logLiveOnly ? 'on' : ''}">` +
      `${logLiveOnly ? '✓ ' : ''}On the wire now (${live})</button>`;
  }
  if (logOn.rumors) {
    const places = [...new Set(d.rumors.map(r => r.system + ' · ' + r.base))];
    bar += '<select id="logplace">' +
      '<option value="">every base I have docked at</option>' +
      places.map(p =>
        `<option value="${esc(p)}"${p === logBase ? ' selected' : ''}>` +
        `${esc(p)}</option>`).join('') + '</select>';
  }

  const count = `${rows.length} of ${all.length} · ${unread} unread`;
  const head = '<div class="logbar">' + chips + '<span class="sep"></span>' + bar +
    `<span class="count">${count} · marks are kept by the server</span></div>`;
  const why = logWhy(streams);
  const note = why ? `<p class="note">${why}</p>` : '';
  if (!streams) return head + '<p class="empty">Every source is switched off.</p>';
  if (!rows.length) return head + note + '<p class="empty">' +
    (logUnreadOnly ? 'Nothing left unread here.' : 'Nothing to show.') + '</p>';
  return head + note + logDraw(rows, streams);
}

function wireLog() {
  document.querySelectorAll('.logbar .src').forEach(b =>
    b.addEventListener('click', () => {
      logOn[b.dataset.src] = !logOn[b.dataset.src];
      render();
    }));
  const on = (id, fn) => { const b = $('#' + id); if (b) b.onclick = fn; };
  on('logsort', () => { logNewestFirst = !logNewestFirst; render(); });
  on('logunread', () => { logUnreadOnly = !logUnreadOnly; render(); });
  on('logpersonal', () => { logPersonalOnly = !logPersonalOnly; render(); });
  on('loglive', () => { logLiveOnly = !logLiveOnly; render(); });
  const place = $('#logplace');
  if (place) place.addEventListener('change', e => { logBase = e.target.value; render(); });
  // Optimistic: the mark moves under the cursor and the server hears about it
  // afterwards, because a round trip to localhost is still a round trip.
  //
  // Turning a mark **off** clears every key the row answers to, turning it on
  // writes only the primary. Otherwise a mark left on a folded news copy could
  // never be cleared from the page that shows it.
  const flip = async (which, at) => {
    const keys = logKeys[Number(at)] || [];
    if (!keys.length) return;
    const want = !marked(which, keys);
    const touched = want ? [keys[0]] : keys.filter(k => marks[which][k]);
    touched.forEach(k => {
      if (want) marks[which][k] = true; else delete marks[which][k];
    });
    marksHeld = Date.now();
    render();
    for (const k of touched) await postMark(which, k, want);
    // Every write is home, so the next payload is the authority again.
    marksHeld = 0;
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
    if (!r.ok) return;
    const got = await r.json();
    logData = got;
    // Not while a toggle is travelling: this payload predates it.
    if (got.marks && !marksBusy()) marks = got.marks;
    render();
  } catch (e) { /* the tab keeps its loading line */ }
}

async function openLog() {
  if (await importOldMarks()) render();
  await loadLog();
}

VIEW.log = {
  bare: true,
  sub: 'the log, the wire, and what the bars are saying',
  draw: renderLog, wire: wireLog,
  open: openLog,
  // The save grows while you fly, so this one is worth re-reading on the tick.
  poll: loadLog,
};
"""
