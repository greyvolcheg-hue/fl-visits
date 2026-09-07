"""Equipment → DPS: a loadout's damage per second."""

ID, LABEL = "dps", "DPS"

JS = r"""
let catalogue = null, gunQuery = null;
let loadout = [];
try {
  loadout = JSON.parse(localStorage.getItem('fl.loadout') || '[]');
} catch (e) { loadout = []; }

function saveLoadout() {
  try { localStorage.setItem('fl.loadout', JSON.stringify(loadout)); } catch (e) {}
}

// Neural Net marks. Keyed by netlog.py's stable key, which counts an entry's
// duplicates up from the oldest end precisely so these do not slide onto the
// wrong line when the game writes a new entry at the top. Newest first is the
// default because that is the end the game appends to.

function gunByNick(nick) {
  return (catalogue ? catalogue.weapons : []).find(w => w.nickname === nick);
}

function renderDPS() {
  if (!catalogue) return '<p class="empty">reading the game data…</p>';
  // Keep each weapon's slot in `loadout` beside it. The remove button splices
  // `loadout`, so indexing a filtered copy would delete the wrong gun the
  // moment one nickname failed to resolve.
  const chosen = loadout
    .map((nick, slot) => ({ w: gunByNick(nick), slot }))
    .filter(x => x.w);
  let out = '';

  if (chosen.length) {
    const dps = (v, cls) => `<span class="num ${cls}">${v.toFixed(1)}</span>`;
    // Per-shot figures are floored, which is what the game itself prints: the
    // Adv. Skyrail is 121.2 in the files and 121 on the dealer screen. Showing
    // them the game's way is the point, since these columns exist to be
    // checked against it. The DPS columns keep the full precision.
    const shot = v => `<span class="num raw">${Math.floor(v)}</span>`;
    out += '<div class="guns"><div class="guntable">' +
      '<div class="gunhead"><span class="nm">weapon</span>' +
      '<span class="grp">hull</span><span class="grp">shield</span>' +
      '<span>hull dps</span><span>shield dps</span>' +
      '<span>rate</span><span>refire</span><span></span></div>' +
      chosen.map(({ w, slot }) =>
        `<div class="gun"><span class="nm">${esc(w.name)}` +
        (w.turret ? ' <span class="loot">turret</span>' : '') + '</span>' +
        shot(w.hull) + shot(w.shield) +
        dps(w.hull_dps, 'h') + dps(w.shield_dps, 's') +
        `<span class="num raw">${(1 / w.refire).toFixed(2)}</span>` +
        `<span class="num raw">${w.refire.toFixed(2)}s</span>` +
        `<button class="kill" data-drop="${slot}" title="remove">&times;</button></div>`).join('') +
      `<div class="gun sum"><span class="nm">${chosen.length} mounted</span>` +
      '<span></span><span></span>' +
      dps(chosen.reduce((a, x) => a + x.w.hull_dps, 0), 'h') +
      dps(chosen.reduce((a, x) => a + x.w.shield_dps, 0), 's') +
      '<span></span><span></span><span></span></div></div></div>';
  } else {
    out += '<p class="empty">Nothing mounted. Add a weapon to see what it does.</p>';
  }

  if (gunQuery === null) {
    out += '<p><button class="addgun" id="addgun">+ Add weapon</button></p>';
    return out;
  }

  // 40 is enough to see whether the search is working without turning the
  // panel into the whole catalogue again.
  const q = gunQuery.trim().toLowerCase();
  const hits = catalogue.weapons
    .filter(w => !q || w.name.toLowerCase().includes(q))
    .slice(0, 40);
  out += '<p><input id="gunsearch" placeholder="type a weapon name" ' +
         `value="${esc(gunQuery)}" autocomplete="off"></p><div class="hits">` +
    (hits.length ? hits.map(w =>
      `<button class="hit" data-add="${esc(w.nickname)}">` +
      `<span class="nm">${esc(w.name)}` +
      (w.turret ? ' <span class="loot">turret</span>' : '') + '</span>' +
      `<span class="num">${w.hull_dps.toFixed(0)}</span>` +
      `<span class="num">${w.shield_dps.toFixed(0)}</span></button>`).join('')
      : '<p class="empty">Nothing by that name.</p>') +
    '</div>';
  return out;
}

function wireDPS() {
  const add = $('#addgun');
  if (add) add.addEventListener('click', () => { gunQuery = ''; render(); });
  document.querySelectorAll('.gun .kill').forEach(b =>
    b.addEventListener('click', () => {
      loadout.splice(Number(b.dataset.drop), 1);
      saveLoadout();
      render();
    }));
  document.querySelectorAll('.hit').forEach(b =>
    b.addEventListener('click', () => {
      loadout.push(b.dataset.add);
      saveLoadout();
      gunQuery = null;
      render();
    }));
  const box = $('#gunsearch');
  if (box) {
    // Re-rendering replaces the input, so put the caret back where it was or
    // typing a second character would send it to the front of the box.
    box.focus();
    box.setSelectionRange(box.value.length, box.value.length);
    box.addEventListener('input', e => { gunQuery = e.target.value; render(); });
    box.addEventListener('keydown', e => {
      if (e.key === 'Escape') { gunQuery = null; render(); }
    });
  }
}

async function loadCatalogue() {
  if (catalogue) return;
  try {
    const r = await fetch('api/weapons', { cache: 'no-store' });
    if (r.ok) { catalogue = await r.json(); render(); }
  } catch (e) { /* the tab shows its loading line until this succeeds */ }
}
VIEW.dps = {
  bare: true,
  sub: 'damage per second, from the weapon stats alone',
  draw: renderDPS, wire: wireDPS, open: loadCatalogue,
};
"""
