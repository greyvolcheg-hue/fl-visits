"""Speed: cruise, thrusters, trade lanes, docking and draw distance, live.

The endpoints are in `backend/speed.py`; every number this panel offers
arrives in the payload, so the choice lists live there and not here.
"""

ID, LABEL = "speed", "Speed"

JS = r"""
let speed = null, thrusters = null, lane = null, draw = null, best = null;
// The "write it to the files" button's own state. It belongs to this view, and
// leaving it undeclared cost the whole panel: reading an undeclared variable is
// a ReferenceError, `renderPersist` is the last term of the concatenation that
// builds the panel, so the throw meant `innerHTML` was never assigned and the
// tab sat on "Reading the game…" forever. Python compiles, endpoints answer,
// and nothing catches it but opening the page.
let persistBusy = false, persistOk = false, persistMsg = null;
function renderSpeed() {
  const s = speed;
  if (!s) return '<p class="empty">Reading the game…</p>';
  // No game running is the ordinary case, not a failure: the page is usually
  // open before Freelancer is.
  const head = `<h2 class="house">Cruise</h2>` + (s.error
    ? `<p class="note warn">${esc(s.error)}</p>`
    : `<p class="note">Cruise speed is <b>${s.value}</b>. A change applies to the
       next cruise burn, no reload. It lasts until the game is closed; the file
       still says what it said.</p>`);
  const msg = s.message ? `<p class="note">${esc(s.message)}</p>` : '';
  const buttons = s.choices.map(v =>
    `<button data-speed="${v}" ${s.error ? 'disabled' : ''}` +
    `${!s.error && Math.abs(s.value - v) < 0.5 ? ' class="on"' : ''}>${v}</button>`
  ).join('');
  return head + msg + `<div class="speeds">${buttons}</div>` +
    `<p class="note">A separate constant, ANOM_LIMITS_MAX_VELOCITY in
     <code>constants.ini</code>, caps velocity at 10000 and is not touched
     here. Nothing offered above reaches it.</p>`;
}

function renderTradeLane() {
  const t = lane;
  if (!t) return '';
  const head = '<h2 class="house">Trade lanes</h2>' + (t.error
    ? `<p class="note warn">${esc(t.error)}</p>`
    : `<p class="note">Lane speed is <b>${t.value}</b>, vanilla is
       ${t.vanilla}. Not in any data file: it is a constant inside
       <code>common.dll</code>, so this is memory only and lasts until the game
       closes.</p>`);
  const msg = t.message ? `<p class="note">${esc(t.message)}</p>` : '';
  const buttons = t.choices.map(v =>
    `<button data-lane="${v}" ${t.error ? 'disabled' : ''}` +
    `${!t.error && Math.abs(t.value - v) < 0.5 ? ' class="on"' : ''}>${v}</button>`
  ).join('');
  const extras = t.error ? '' :
    `<p class="note">Picking a speed also sets the wind-up to near-instant,
     since at the stock rate a ship spends most of a short lane still
     accelerating and the higher number is barely felt. Deceleration is left
     alone: that one needs code injected into the game, not a number changed.
     <br>The HUD refuses to print a speed over <b>${t.shown}</b>, and a lane
     faster than that shows a dash instead of a number.</p>` +
    '<div class="speeds">' +
    `<button id="instant" class="${t.instant ? 'on' : ''}">` +
    `${t.instant ? '✓ wind-up near-instant' : 'Wind-up: stock'}</button>` +
    `<button id="uncap" class="${t.uncapped ? 'on' : ''}">` +
    `${t.uncapped ? '✓ readout raised to 9999' : 'Raise the readout to 9999'}` +
    '</button>' +
    `<button id="takeover" class="${t.takeover ? 'on' : ''}">` +
    (t.takeover
      ? `✓ docking takes over at ${t.takeover}`
      : `Dock from ${t.takeover_default} m, not ${t.takeover_stock}`) +
    '</button></div>' +
    // The one control here that is not a number being written. Say so, because
    // "it went away when I restarted" reads as a bug otherwise.
    `<p class="note">The last button is the only thing on this page that
     <b>puts code into the game</b>: a stub in the padding at the end of
     <code>common.dll</code>, so the game stops flying you and starts docking
     you at ${t.takeover_default} m instead of ${t.takeover_stock}. You keep
     cruise or thrust almost to the ring rather than crawling the last
     kilometre. Jump gates share the number; stations and planets keep 600,
     because a planet has a radius. Nothing is written to disk and a relaunch
     removes it.</p>`;
  return head + msg + `<div class="speeds">${buttons}</div>` + extras;
}

// Every live-game panel posts the same way: disable the row, POST, take the
// reply as the panel's new state. Three copies of this drifted apart once
// already, so the panel name is a parameter instead.

const PANELS = {
  lane: 'api/tradelane',
  best: 'api/bestpath',
  draw: 'api/drawdist',
};

async function post(panel, body) {
  document.querySelectorAll('.speeds button').forEach(b => b.disabled = true);
  try {
    const r = await fetch(PANELS[panel], body === undefined
      ? { method: 'POST' }
      : { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body) });
    if (!r.ok) return;
    const got = await r.json();
    if (panel === 'lane') lane = got;
    else if (panel === 'best') best = got;
    else draw = got;
    render();
  } catch (e) { /* leave the buttons as they were */ }
}

const setLane = body => post('lane', body);

function renderDrawDist() {
  const d = draw;
  if (!d) return '';
  if (d.error) return '<h2 class="house">Asteroid draw distance</h2>' +
    `<p class="note warn">${esc(d.error)}</p>`;
  const msg = d.message ? `<p class="note">${esc(d.message)}</p>` : '';
  const buttons = d.choices.map(v =>
    `<button data-draw="${v}"${Math.abs(d.factor - v) < 0.02 ? ' class="on"' : ''}>` +
    `${v}x</button>`).join('');
  return '<h2 class="house">Asteroid draw distance</h2>' +
    `<p class="note">${d.fields} fields, median <b>${d.median}</b> against a
     vanilla ${d.vanilla}. This is a file change, so it lands the next time a
     system loads, and each field is scaled from its own vanilla value rather
     than from wherever it is now, so pressing 1.5x twice is still 1.5x.</p>` +
    `<p class="note">Rocks fill a sphere, so 2x the distance is about 8x the
     geometry on a single-threaded 2003 renderer. Billboards are deliberately
     left alone: they are scattered independently of the real rocks, which is
     why a sprite vanishes and a rock turns up somewhere else, and adding more
     of them makes that worse rather than better.</p>` +
    `<div class="speeds">${buttons}</div>` + msg;
}

function renderBestPath() {
  const b = best;
  if (!b) return '';
  const head = '<h2 class="house">Set Best Path</h2>';
  if (b.error) return head + `<p class="note warn">${esc(b.error)}</p>`;
  const msg = b.message ? `<p class="note">${esc(b.message)}</p>` : '';
  return head +
    `<p class="note">The game ships two route tables and routes with the duller
     one. <code>shortest_legal_path.ini</code> knows only jump gates;
     <code>systems_shortest_path.ini</code> includes jump holes, which are
     often the shortcut. Both have been in the install since 2003, and this
     swaps which gets read. Five bytes, no code injected, nothing written to
     disk.</p>` +
    `<p class="note warn">The two libraries this touches are loaded when a save
     is loaded, so <b>the setting is gone every time you load a game</b> and
     has to be pressed again. That is the honest cost of not hooking the
     loader.</p>` +
    '<div class="speeds">' +
    `<button id="bestpath" class="${b.on ? 'on' : ''}">` +
    (b.on ? '✓ routing through jump holes' : 'Route through jump holes too') +
    '</button></div>' + msg;
}

const setBestPath = () => post('best');

const setDraw = body => post('draw', body);

function renderPersist() {
  if (!speed || speed.error) return '';
  const note = persistMsg
    ? `<p class="note${persistOk ? '' : ' warn'}">${esc(persistMsg)}</p>` : '';
  return '<h2 class="house">Keep these</h2>' +
    `<p class="note">Writes the speeds above into <code>constants.ini</code> and
     <code>st_equip.ini</code>, so the next launch starts with them. Safe to
     press while the game is running: it reads those files once at startup, so
     nothing changes until you relaunch.</p>` +
    `<div class="speeds"><button id="persist"${persistBusy ? ' disabled' : ''}>` +
    `${persistBusy ? 'writing…' : 'Write to the game files'}</button></div>` + note;
}

async function doPersist() {
  persistBusy = true; persistMsg = null; render();
  try {
    const r = await fetch('api/persist', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
    });
    const d = await r.json();
    persistOk = !!d.ok;
    persistMsg = d.message;
  } catch (e) {
    persistOk = false;
    persistMsg = 'the server went away';
  }
  persistBusy = false;
  render();
}

function renderThrusters() {
  const t = thrusters;
  if (!t) return '';
  if (t.error) return `<h2 class="house">Thrusters</h2>` +
    `<p class="note warn">${esc(t.error)}</p>`;
  const msg = t.message ? `<p class="note">${esc(t.message)}</p>` : '';
  const head = `<h2 class="house">Thrusters</h2>` +
    `<p class="note">These are <b>bonuses</b>, added to your ship's
    normal speed, not the speed itself. Vanilla is 120. Only the thruster you
    have fitted matters; the rest are here because swapping one should not need
    a code change.</p>`;
  const rows = t.items.map(it => {
    const buttons = t.choices.map(v =>
      `<button data-ids="${it.ids}" data-speed="${v}"` +
      `${Math.abs(it.speed - v) < 0.5 ? ' class="on"' : ''}>${v}</button>`
    ).join('');
    return `<div class="sys"><div class="head"><b>${esc(it.name)}</b>` +
           `<span class="count">+${it.speed}</span></div>` +
           `<div class="speeds">${buttons}</div></div>`;
  }).join('');
  return head + msg + rows;
}

async function setThruster(ids, value) {
  document.querySelectorAll('.speeds button').forEach(b => b.disabled = true);
  try {
    const r = await fetch('api/thrusters', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids, value })
    });
    if (r.ok) { thrusters = await r.json(); render(); }
  } catch (e) { /* leave the buttons as they were */ }
}

async function setSpeed(value) {
  document.querySelectorAll('.speeds button').forEach(b => b.disabled = true);
  try {
    const r = await fetch('api/speed', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value })
    });
    if (r.ok) { speed = await r.json(); render(); }
  } catch (e) { /* leave the buttons as they were */ }
}
function wireSpeed() {
  // Dispatch on what a button carries, never on a list of names to skip. The
  // old form enumerated every by-id toggle and fell through to
  // `setSpeed(Number(undefined))` for anything missed, so forgetting one
  // POSTed NaN as a cruise speed to the live game.
  document.querySelectorAll('.speeds button').forEach(b => {
    if (b.id) return;  // bound by id below
    if (b.dataset.draw) b.onclick = () => setDraw({ factor: Number(b.dataset.draw) });
    else if (b.dataset.lane) b.onclick = () => setLane({ value: Number(b.dataset.lane) });
    else if (b.dataset.ids)
      b.onclick = () => setThruster(Number(b.dataset.ids), Number(b.dataset.speed));
    else if (b.dataset.speed) b.onclick = () => setSpeed(Number(b.dataset.speed));
  });
  const on = (id, fn) => { const b = $('#' + id); if (b) b.onclick = fn; };
  on('persist', doPersist);
  on('uncap', () => setLane({ uncapped: !(lane && lane.uncapped) }));
  on('instant', () => setLane({ instant: !(lane && lane.instant) }));
  // A toggle, not a value: only the server can say which way the patch is now.
  on('takeover', () => setLane({ takeover: true }));
  on('bestpath', setBestPath);
}

VIEW.speed = {
  bare: true,
  sub: 'live speed of the running game',
  draw: () => renderSpeed() + renderThrusters() + renderTradeLane() +
               renderBestPath() + renderDrawDist() + renderPersist(),
  wire: wireSpeed,
  open: poll,
  async poll() {
    const names = ['speed', 'thrusters', 'tradelane', 'drawdist', 'bestpath'];
    const got = await Promise.all(names.map(n =>
      fetch('api/' + n, { cache: 'no-store' }).then(r => r.ok ? r.json() : null)));
    // The message is the panel's own, from the last button press; a poll
    // refreshes the readings without wiping what it said.
    const keep = (was, now) => now ? { ...now, message: was && was.message } : was;
    [speed, thrusters, lane, draw, best] =
      [speed, thrusters, lane, draw, best].map((was, i) => keep(was, got[i]));
  },
};
"""
