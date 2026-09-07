"""Engine: cruise, thrusters, lanes, docking and draw distance, live.

The endpoints are in `backend/engine.py`; every number this tab offers arrives
in the payload, so the choice lists live there and not here.

**A tab, not a strip.** These controls sat above the tab row on every page for
a few hours on 2026-09-07, following the design canvas, and it was a mistake in
two ways that are worth keeping written down. It polled the running game from
every page, which means scanning process memory for a panel nobody was reading.
And being redrawn on every tick of that poll, it kept losing clicks: a browser
only fires `click` when the press and the release land on the same element.

Two things follow from every control here writing into a live game:

  * **A slider posts on `change`, never on `input`.** `input` fires per pixel of
    drag, and each one would be a write into process memory. The number under
    the slider follows your thumb; the game hears about it when you let go.
  * **A redraw is held off while you are dragging**, because the five-second
    poll would otherwise replace the slider under your hand.

Every control appears exactly once. The strip carried best path and the docking
takeover twice, in the strip and again in the drawer, which is two places to
read one setting.
"""

ID, LABEL = "engine", "Engine"

CSS = """
  /* The sliders, straight off the canvas. A browser's own range control is
     the one widget that will not inherit a thing, so every part is drawn:
     WebKit and Gecko name the pieces differently and both lists are needed. */
  .engine input[type=range], .engine .box input[type=range] {
    -webkit-appearance: none; appearance: none; background: transparent;
    width: 100%; height: 19px; cursor: ew-resize; margin: 0;
  }
  .engine input[type=range]::-webkit-slider-runnable-track {
    height: 7px; background: rgba(111, 216, 255, .12);
    border: 1px solid rgba(111, 216, 255, .45);
    box-shadow: inset 0 0 6px rgba(111, 216, 255, .18); }
  .engine input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none; width: 9px; height: 19px; margin-top: -7px;
    border: 0; background: var(--docked);
    box-shadow: 0 0 8px rgba(111, 216, 255, .8); }
  .engine input[type=range]::-moz-range-track {
    height: 7px; background: rgba(111, 216, 255, .12);
    border: 1px solid rgba(111, 216, 255, .45); }
  .engine input[type=range]::-moz-range-thumb {
    width: 9px; height: 19px; border: 0; border-radius: 0;
    background: var(--docked); box-shadow: 0 0 8px rgba(111, 216, 255, .8); }
  .engine input[type=range]:disabled::-webkit-slider-thumb {
    background: var(--unknown); box-shadow: none; }
  .engine input[type=range]:disabled::-moz-range-thumb {
    background: var(--unknown); box-shadow: none; }
  .engine input.big { height: 27px; }
  .engine input.big::-webkit-slider-runnable-track {
    height: 11px; background: rgba(111, 216, 255, .14);
    border: 1px solid rgba(111, 216, 255, .55); }
  .engine input.big::-webkit-slider-thumb {
    width: 13px; height: 27px; margin-top: -9px; }
  .engine input.big::-moz-range-track {
    height: 11px; background: rgba(111, 216, 255, .14);
    border: 1px solid rgba(111, 216, 255, .55); }
  .engine input.big::-moz-range-thumb { width: 13px; height: 27px; }
"""


JS = r"""
let eng = null, engBusy = false;
let engSaid = null, engSaidBad = false;
// While a slider is under a thumb, neither the poll nor a redraw may touch the
// markup: the drag would go with it. A timestamp rather than a flag, because a
// pointer can leave the window and never send its release.
let engHeld = 0;
let persistBusy = false;

const CRUISE_RANGE = [300, 5000, 50];
const HOLD = 2000;

const held = () => Date.now() - engHeld < HOLD;
const engBox = () => document.querySelector('#list .engine');

function engRange(label, value, unit, min, max, step, act, live, cls) {
  return `<div class="knob"><div class="top">` +
    `<span class="lbl">${label}</span>` +
    `<span class="val" id="v-${act}">${value === null ? '—' : money(value) + unit}</span>` +
    `</div><input class="${cls || ''}" type="range" min="${min}" max="${max}" ` +
    `step="${step}" value="${value === null ? min : value}" data-knob="${act}" ` +
    `data-unit="${unit}"${live ? '' : ' disabled'}></div>`;
}

function engStrip() {
  const live = !!(eng && eng.running);
  const c = eng && eng.cruise, l = eng && eng.lane;
  const cruise = c && !c.error ? c.value : null;
  const [lo, hi, step] = CRUISE_RANGE;
  const presets = (c ? c.choices : []).filter(v => v >= lo && v <= hi).map(v =>
    `<button data-cruise="${v}"${cruise === v ? ' class="on"' : ''}` +
    `${live ? '' : ' disabled'}>${money(v)}</button>`).join('');

  return '<div class="strip wrapgrid"><div class="main">' +
    `<div class="lead"><span class="pip${live ? '' : ' cold'}"></span>` +
    `<span class="live${live ? '' : ' cold'}">` +
    `${live ? 'ENGINE LIVE' : 'NO GAME RUNNING'}</span>` +
    `<span class="range">/ CRUISE ${lo}–${money(hi)}</span></div>` +
    `<div class="big"><span class="val" id="v-cruise">` +
    `${cruise === null ? '—' : money(cruise)}</span>` +
    `<div class="presets">${presets}</div></div>` +
    `<input class="big" type="range" min="${lo}" max="${hi}" step="${step}" ` +
    `value="${cruise === null ? lo : cruise}" data-knob="cruise" data-unit=""` +
    `${live ? '' : ' disabled'}></div>` +
    engRange('TRADE LANE', l && !l.error ? l.value : null, '', 2500, 10000, 100,
             'lane', live) +
    '</div>';
}

function engLiveBox(label, value, unit, min, max, step, act, why, from) {
  return '<div class="box"><div class="top">' +
    `<span class="lbl">${label}</span>` +
    `<span class="val" id="v-${act}">${value === null ? '—' : money(value) + unit}</span>` +
    `</div><input type="range" min="${min}" max="${max}" step="${step}" ` +
    `value="${value === null ? min : value}" data-knob="${act}" ` +
    `data-unit="${unit}"${eng && eng.running ? '' : ' disabled'}>` +
    `<div class="why">${why}</div><div class="from">${from}</div></div>`;
}

function engFlipBox(label, on, text, offText, act, why, from) {
  return '<div class="box"><div class="top">' +
    `<span class="lbl">${label}</span>` +
    `<span class="val ${on ? 'on' : 'off'}">${on ? 'ON' : 'OFF'}</span>` +
    `</div><button class="chip${on ? ' on' : ''}" data-flip="${act}"` +
    `${eng && eng.running ? '' : ' disabled'}>${on ? text : offText}</button>` +
    `<div class="why">${why}</div><div class="from">${from}</div></div>`;
}

function engMemory() {
  const l = eng.lane || {}, t = eng.thrusters;
  // One box for all six thrusters. They differ by a number and a name and
  // share every word of explanation, so six copies of the same paragraph is
  // what the repetition would actually buy.
  let boxes = '';
  if (t && t.error) {
    boxes += `<div class="box"><div class="why">${esc(t.error)}</div></div>`;
  } else if (t) {
    boxes += '<div class="box many"><div class="top">' +
      '<span class="lbl">THRUSTERS (BONUS)</span></div>' +
      t.items.map(it =>
        `<div class="top"><span class="lbl">${esc(it.name).toUpperCase()}</span>` +
        `<span class="val" id="v-th${it.ids}">${money(it.speed)}</span></div>` +
        `<input type="range" min="120" max="420" step="10" value="${it.speed}" ` +
        `data-knob="th${it.ids}" data-unit=""` +
        (eng.running ? '' : ' disabled') + '>').join('') +
      '<div class="why">A <b>bonus</b> added to your normal speed, not the ' +
      'speed itself. Vanilla is 120 on all six. Only the one you have fitted ' +
      'matters; the rest are here so swapping does not need a code change.</div>' +
      '<div class="from">st_equip.ini values, patched in memory</div></div>';
  }

  boxes += engFlipBox('LANE WIND-UP', !!l.instant, 'NEAR-INSTANT', 'STOCK RAMP',
    'instant',
    'At the stock rate a ship spends most of a short lane still accelerating, ' +
    'so a higher speed alone is barely felt. Deceleration is left alone: that ' +
    'one needs code injected, not a number changed.',
    'same setting in practice as lane speed');
  boxes += engFlipBox('HUD SPEED CAP', !!l.uncapped, 'RAISED TO 9999',
    'STOCK ' + (l.shown || 999), 'uncap',
    'The HUD refuses to print a speed over ' + (l.shown || 999) + ', so a ' +
    'raised lane speed shows a dash instead of a number.',
    'not in files; never written to disk');
  const b = eng.best || {};
  boxes += engFlipBox('BEST PATH VIA JUMP HOLES', !!b.on, 'ON', 'OFF', 'best',
    'Swaps which route table gets read: <code>systems_shortest_path.ini</code> ' +
    'includes jump holes, <code>shortest_legal_path.ini</code> only gates. ' +
    '<b>Dies on every save load</b> — content.dll and server.dll reload with ' +
    'the save, so press it again.',
    'bestpath.py · five bytes in three places');
  const stock = l.takeover_stock || 1000;
  boxes += (l.takeover === null || l.takeover === undefined)
    ? engFlipBox('DOCKING TAKEOVER', false, '', 'PUT THE STUB IN', 'takeover',
        'Where the game stops flying you and starts docking you. Stock is ' +
        stock + ' m; ' + (l.takeover_default || 200) + ' is what settled after ' +
        'flying 100, 200, 400 and 600. Lanes and jump gates share it, stations ' +
        'and planets keep 600.',
        'dockdist.py · memory only, relaunch restores stock')
    : engLiveBox('DOCKING TAKEOVER', l.takeover, ' m',
        (l.takeover_range || [100])[0], (l.takeover_range || [0, 1000])[1],
        (l.takeover_range || [0, 0, 50])[2], 'takeover',
        'Where the game stops flying you and starts docking you. Stock is ' +
        stock + ' m. Lanes and jump gates share this; stations and planets ' +
        'keep 600, because a planet has a radius.',
        'dockdist.py · memory only, relaunch restores stock');

  return '<div class="banner"><span class="kind">LIVE MEMORY</span>' +
    '<span class="say">Written into the running game, never to a save or a ' +
    'file. Cruise lands on your next burn with no reload; close the game and ' +
    'every one of these is gone.</span></div>' +
    `<div class="grid wrapgrid">${boxes}</div>`;
}

function engFiles() {
  const d = eng.draw, c = eng.cruise, t = eng.thrusters;
  const cruise = c && !c.error ? money(c.value) : '—';
  const thrust = t && !t.error && t.items.length ? '+' + t.items[0].speed : '—';
  const write = '<div class="box file">' +
    '<div class="lbl">WRITE CRUISE + THRUSTERS TO FILES</div>' +
    '<div class="why">Takes the two speeds you have set live and puts them in ' +
    '<code>constants.ini</code> and <code>st_equip.ini</code>, so the next ' +
    'launch starts with them. Safe to press mid-flight: both files are read ' +
    'once at startup.</div>' +
    '<div class="why">Trade lane speed, the HUD cap, docking and best path are ' +
    'not written, because they are not in files to begin with.</div>' +
    `<button class="chip" id="persist"${persistBusy || !(c && !c.error) ? ' disabled' : ''}>` +
    `${persistBusy ? 'WRITING…' : 'WRITE ' + cruise + ' / ' + thrust}</button></div>`;

  let rocks;
  if (!d || d.error) {
    rocks = '<div class="box file"><div class="lbl">ASTEROID DRAW DISTANCE</div>' +
      `<div class="why">${esc((d && d.error) || 'not read yet')}</div></div>`;
  } else {
    const cube = Math.round(Math.pow(d.factor, 3) * 10) / 10;
    rocks = '<div class="box file"><div class="top">' +
      '<span class="lbl">ASTEROID DRAW DISTANCE</span>' +
      `<span class="val" id="v-draw">${d.factor}×</span></div>` +
      `<input type="range" min="1" max="3" step="0.25" value="${d.factor}" ` +
      'data-knob="draw" data-unit="×">' +
      `<div class="why">Scales <code>[Field] fill_dist</code> across ${d.fields} ` +
      `field files. Vanilla median is ${d.vanilla}, yours is ${d.median} — which ` +
      'is why a field reads as empty until you are nearly inside it.</div>' +
      '<div class="why">' + (d.factor === 1
        ? 'At 1× nothing changes: the shipped numbers stay as they are.'
        : `${d.factor}× the distance is roughly ${cube}× the geometry, on a ` +
          'single-threaded 2003 renderer. Billboards are left alone on purpose.') +
      '</div><div class="from">lands the next time a system loads</div></div>';
  }

  return '<div class="banner files"><span class="kind">GAME FILES</span>' +
    '<span class="say">Touches files on disk. Each one is backed up to ' +
    '<code>.vanilla</code> the first time, and an existing backup is never ' +
    'overwritten.</span></div>' +
    `<div class="grid wrapgrid">${write}${rocks}</div>`;
}

function renderEngine() {
  // null means "leave the panel exactly as it is". Mid-drag that is the whole
  // point: a repaint would take the slider out from under the thumb.
  if (held()) return null;
  if (!eng) return '<p class="empty">reading the game…</p>';
  const said = engSaid
    ? `<div class="banner"><span class="said${engSaidBad ? ' bad' : ''}">` +
      `${esc(engSaid)}</span></div>` : '';
  return '<div class="engine">' + engStrip() + said +
    `<div class="drawer">${engMemory()}${engFiles()}</div></div>`;
}

// One POST shape for every control here. Three copies of this drifted apart
// once already, so what is being set is a parameter rather than a function.
async function engPost(url, body) {
  if (engBusy) return;
  engBusy = true;
  const box = engBox();
  if (box) box.querySelectorAll('button, input').forEach(b => b.disabled = true);
  try {
    const r = await fetch('api/' + url, {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    const got = await r.json();
    engSaid = got.message || null;
    engSaidBad = got.ok === false;
  } catch (e) {
    engSaid = 'the server went away';
    engSaidBad = true;
  }
  engBusy = false;
  engHeld = 0;
  await loadEngine();
}

const KNOB = {
  cruise: v => engPost('speed', { value: v }),
  lane: v => engPost('tradelane', { value: v }),
  takeover: v => engPost('tradelane', { takeover: v }),
  draw: v => engPost('drawdist', { factor: v }),
};

const FLIP = {
  best: () => engPost('bestpath'),
  instant: () => engPost('tradelane', { instant: !(eng.lane && eng.lane.instant) }),
  uncap: () => engPost('tradelane', { uncapped: !(eng.lane && eng.lane.uncapped) }),
  takeover: () => engPost('tradelane', {
    takeover: (eng.lane && eng.lane.takeover) ? false
              : ((eng.lane && eng.lane.takeover_default) || 200) }),
};

function wireEngine() {
  const box = engBox();
  if (!box) return;
  box.querySelectorAll('input[type=range]').forEach(r => {
    // The number follows the thumb; the game hears about it on release.
    r.oninput = () => {
      engHeld = Date.now();
      const out = $('#v-' + r.dataset.knob);
      if (out) out.textContent = money(Number(r.value)) + r.dataset.unit;
    };
    r.onchange = () => {
      const v = Number(r.value), act = r.dataset.knob;
      if (act.startsWith('th')) engPost('thrusters', { ids: Number(act.slice(2)), value: v });
      else if (KNOB[act]) KNOB[act](v);
    };
  });
  box.querySelectorAll('[data-cruise]').forEach(b =>
    b.onclick = () => KNOB.cruise(Number(b.dataset.cruise)));
  box.querySelectorAll('[data-flip]').forEach(b =>
    b.onclick = () => { const f = FLIP[b.dataset.flip]; if (f) f(); });
  const p = $('#persist');
  if (p) p.onclick = async () => {
    persistBusy = true; render();
    await engPost('persist');
    persistBusy = false;
    render();
  };
}

async function loadEngine() {
  if (held()) return;
  try {
    // Always `?all=1`: this is a tab now, so everything it shows is on screen
    // and there is no half to fetch later.
    const r = await fetch('api/engine?all=1', { cache: 'no-store' });
    if (r.ok) { eng = await r.json(); render(); }
  } catch (e) { /* keep the last reading; the panel says nothing new */ }
}

VIEW.engine = {
  bare: true,
  sub: 'the running game: speed, docking, and what gets written to disk',
  draw: renderEngine, wire: wireEngine,
  open: loadEngine, poll: loadEngine,
};
"""
