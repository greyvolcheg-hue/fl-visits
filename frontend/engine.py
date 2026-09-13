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
  /* The callsign picker. The faction list holds names as long as "Daumann
     Heavy Construction", so it is capped rather than allowed to push the
     other three onto a second line where a bare "1" says nothing. */
  .engine .csrow { margin: .2rem 0 .1rem; }
  .engine .csrow select { max-width: 11rem; }
  .engine .csrow .sys { color: var(--amber-dim); padding: 0 .1rem; }
  .engine .csacts { display: flex; gap: .5rem; flex-wrap: wrap;
                    margin-top: .4rem; }
  .engine .csacts button.chip { flex: none; }
  .engine .csrow input[type=number] { width: 6.5rem; }
  /* The scolding, and it is amber rather than red: this is allowed. */
  .engine .csrow .nag { flex-basis: 100%; color: var(--amber-dim);
                        font-size: 11px; line-height: 1.45; }

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

  /* The one button on a banner rather than in a box. `margin-left: auto` is
     what puts it at the far end of the flex row, away from the sentence. */
  .engine .banner button.chip.all { margin-left: auto; flex: none;
                                    align-self: center; }
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

// The six thrusters, across rather than down, in a block of their own.
//
// They used to be one tall box inside LIVE MEMORY, stacked, because they share
// every word of explanation and six copies of one paragraph is what splitting
// them would have bought. The banner is what pays for the split: the paragraph
// belongs to the block now, so each thruster is left with the two things that
// actually differ, a name and a number.
function engThrusters() {
  const t = eng.thrusters;
  if (!t) return '';
  const body = t.error
    ? `<div class="box"><div class="why">${esc(t.error)}</div></div>`
    : t.items.map(it =>
        '<div class="box"><div class="top">' +
        `<span class="lbl">${esc(it.name).toUpperCase()}</span>` +
        `<span class="val" id="v-th${it.ids}">${money(it.speed)}</span></div>` +
        `<input type="range" min="120" max="420" step="10" value="${it.speed}" ` +
        `data-knob="th${it.ids}" data-unit=""` +
        (eng.running ? '' : ' disabled') + '></div>').join('');
  return '<div class="banner"><span class="kind">THRUSTERS</span>' +
    '<span class="say">A <b>bonus</b> added to your normal speed, not the ' +
    'speed itself. Vanilla is 120 on all six. Only the one you have fitted ' +
    'matters; the rest are here so swapping does not need a code change. ' +
    'st_equip.ini values, patched in memory.</span></div>' +
    `<div class="grid thr wrapgrid">${body}</div>`;
}

function engMemory() {
  const l = eng.lane || {};
  let boxes = engFlipBox('LANE WIND-UP', !!l.instant, 'NEAR-INSTANT', 'STOCK RAMP',
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

  // One press for the three switches below, because nobody wants two of them.
  // Only the switches: the knobs beside them carry a number, and choosing one
  // for somebody is not what "enable" means.
  const all = `<button class="chip all" data-all="1"` +
    `${eng && eng.running ? '' : ' disabled'}>ENABLE ALL</button>`;
  return '<div class="banner"><span class="kind">LIVE MEMORY</span>' +
    '<span class="say">Written into the running game, never to a save or a ' +
    'file. Cruise lands on your next burn with no reload; close the game and ' +
    'every one of these is gone.</span>' + all + '</div>' +
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
    '<div class="why">Trade lane speed, the HUD cap and docking are not ' +
    'written, because they are not in files to begin with. Best path is a ' +
    'file and has its own command, <code>fl.py routetable</code>.</div>' +
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
      `<input type="range" min="1" max="10" step="1" value="${d.factor}" ` +
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
    `<div class="grid wrapgrid">${write}${rocks}${engCallsign()}` +
    `${engPaths()}${engNomads()}</div>`;
}

// What killing a Nomad is worth to everyone who is not one. Shipped, the
// answer is nothing: their group carries 54 empathy rates and the only three
// that are not zero belong to the campaign's infiltrated navies.
function engNomads() {
  const n = eng.nomads;
  if (!n || n.error) {
    return '<div class="box file"><div class="lbl">KILLING NOMADS</div>' +
      `<div class="why">${esc((n && n.error) || 'not read yet')}</div></div>`;
  }
  // Counted in ships, not in rep points: the question this setting exists to
  // pose is "is it worth flying", and nobody weighs that in thousandths.
  const to = n.kills > 0 ? 'friendly' : 'hostile';
  return '<div class="box file"><div class="top">' +
    '<span class="lbl">KILLING NOMADS</span>' +
    `<span class="val">${n.kills ? n.kills : 'nothing'}</span></div>` +
    '<div class="why">' + (n.kills
      ? `${Math.abs(n.kills)} Nomads to go from neutral to ${to} with ` +
        'everyone at once. The three infiltrated navies from the campaign ' +
        'still hate you for it, because they are Nomads.' +
        (n.kills < 0 ? ' Everybody else now mourns them too.' : '')
      : 'Shipped, nobody in Sirius reacts: 51 of the 54 rates in their ' +
        'group are zero.') + '</div>' +
    // A typed number, not a row of presets: the useful values are a continuum
    // and the presets were only ever examples. The poll cannot steal what is
    // being typed, because `paint` compares the markup it wrote and the `value`
    // attribute does not change while a field is edited.
    '<div class="reppick csrow">' +
    // No `min`, and `step="1"`: the sign is the direction, so a negative count
    // is a setting rather than a mistake, and a step of ten once made the
    // field itself call 2 invalid.
    `<input type="number" id="nomad-kills" step="1" ` +
    `value="${n.kills || 400}">` +
    `<span class="sys">Nomads</span>` +
    `<span class="nag" id="nomad-nag" hidden>under ${n.floor} is fast ` +
    'enough that the ordinary endgame stops being worth flying</span>' +
    '<span class="nag" id="nomad-flip" hidden>a minus runs it backwards: ' +
    'that many Nomads from neutral to <b>hostile</b>, with all of Sirius ' +
    'mourning every one you shoot</span></div>' +
    '<div class="csacts">' +
    '<button class="chip" id="nomad-set">SET</button>' +
    '<button class="chip" id="nomad-off">VANILLA</button></div>' +
    `<div class="from">kills to ${n.kills ? to : 'friendly'}; read at ` +
    'startup, so restart</div></div>';
}

// Which route table Set Best Path reads. Two modes and they are not a
// preference: `holes` is a table of routes through jump holes plus the five
// bytes that let the router fly one, and either half without the other points
// the course at a star. `routetable.py` moves them together.
function engPaths() {
  const p = eng.paths;
  if (!p || p.error) {
    return '<div class="box file"><div class="lbl">SET BEST PATH</div>' +
      `<div class="why">${esc((p && p.error) || 'not read yet')}</div></div>`;
  }
  const say = { gates: 'gates only, as shipped', holes: 'jump holes as well' };
  return '<div class="box file"><div class="top">' +
    '<span class="lbl">SET BEST PATH</span>' +
    `<span class="val">${esc(say[p.mode] || p.mode)}</span></div>` +
    `<div class="why">The game is reading <code>${esc(p.files[p.mode])}</code>: ` +
    `${p.rows} routes over ${p.systems} systems, ` +
    (p.stock ? 'the shipped table.' : 'ours.') + '</div>' +
    '<div class="why">Jump holes need five bytes in <code>server.dll</code> ' +
    'and <code>content.dll</code> as well as the wider table. Without them the ' +
    'router cannot make a waypoint out of a hole and aims at the system ' +
    'origin, which is usually the star.</div>' +
    '<div class="csacts">' +
    p.modes.map(m => `<button class="chip" data-mode="${esc(m)}"` +
      (m === p.mode ? ' disabled' : '') +
      `>${esc(m.toUpperCase())}</button>`).join('') +
    '<button class="chip" id="paths-vanilla">VANILLA</button></div>' +
    '<div class="from">lands the next time a save loads</div></div>';
}

// Four words out of three recorded vocabularies. A picker rather than a text
// box because a bot can only say what was recorded; `callsign.py` carries why.
function engCallsign() {
  const c = eng.call;
  if (!c || c.error) {
    return '<div class="box file"><div class="lbl">WHAT THEY CALL YOU</div>' +
      `<div class="why">${esc((c && c.error) || 'not read yet')}</div></div>`;
  }
  const pick = (id, rows, now, fmt) =>
    `<select id="${id}">` + rows.map(r => {
      const key = fmt ? r : r.key, label = fmt ? r : r.label;
      return `<option value="${esc(String(key))}"` +
        (String(key) === String(now) ? ' selected' : '') +
        `>${esc(String(label))}</option>`;
    }).join('') + '</select>';

  return '<div class="box file"><div class="top">' +
    '<span class="lbl">WHAT THEY CALL YOU</span>' +
    `<span class="val">${esc(c.says)}</span></div>` +
    // Two rows on purpose rather than four controls wrapping wherever the
    // box happens to end: the words belong together and the two numbers are
    // one reading, "six dash six". The dash is drawn for the same reason, as
    // two bare number selects do not say which half is which.
    '<div class="reppick csrow">' +
    pick('cs-faction', c.factions, c.faction) +
    pick('cs-desig', c.designators, c.desig) + '</div>' +
    '<div class="reppick csrow">' +
    pick('cs-wing', c.numbers, c.wing, true) +
    '<span class="sys">&ndash;</span>' +
    pick('cs-slot', c.numbers, c.slot === null ? 1 : c.slot, true) +
    '</div>' +
    '<div class="why">Every word the game has a recording of. Used for any ' +
    'ship with no formation, so a lone NPC may share them.</div>' +
    '<div class="csacts">' +
    '<button class="chip" id="cs-apply">SET</button>' +
    '<button class="chip" id="cs-restore">VANILLA</button></div>' +
    '<div class="from">lands the next time a save loads</div></div>';
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
    '<div class="drawer">' + engMemory() + engThrusters() + engFiles() +
    '</div></div>';
}

// One POST shape for every control here. Three copies of this drifted apart
// once already, so what is being set is a parameter rather than a function.
async function engPost(url, body) {
  if (engBusy) return;
  engBusy = true;
  const box = engBox();
  if (box) box.querySelectorAll('button, input, select')
    .forEach(b => b.disabled = true);
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
  // One POST, not three from here: three would race through `engPost`'s busy
  // flag and only the first would land.
  box.querySelectorAll('[data-all]').forEach(b =>
    b.onclick = () => engPost('allhacks'));
  const apply = $('#cs-apply');
  if (apply) apply.onclick = () => engPost('callsign', {
    faction: $('#cs-faction').value,
    desig: $('#cs-desig').value,
    wing: $('#cs-wing').value,
    slot: $('#cs-slot').value,
  });
  const vanilla = $('#cs-restore');
  if (vanilla) vanilla.onclick = () => engPost('callsign', { restore: 1 });
  box.querySelectorAll('[data-mode]').forEach(b =>
    b.onclick = () => engPost('routetable', { mode: b.dataset.mode }));
  const pv = $('#paths-vanilla');
  if (pv) pv.onclick = () => engPost('routetable', { revert: 1 });
  const nk = $('#nomad-kills'), nag = $('#nomad-nag'), flip = $('#nomad-flip');
  if (nk && nag && flip) {
    // Toggled on the nodes rather than through `render`, which would rebuild
    // the field and take the cursor with it.
    const check = () => {
      const v = Number(nk.value);
      nag.hidden = !(v && Math.abs(v) < eng.nomads.floor);
      flip.hidden = !(v < 0);
    };
    nk.addEventListener('input', check);
    check();
    const set = $('#nomad-set');
    if (set) set.onclick = () => {
      const want = Number(nk.value);
      if (!want) { engSaid = 'a count, or VANILLA for none'; render(); return; }
      engPost('empathy', { kills: want });
    };
  }
  const no = $('#nomad-off');
  if (no) no.onclick = () => engPost('empathy', { restore: 1 });
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
