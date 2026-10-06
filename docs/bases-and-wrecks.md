---
type: research
project: computer-geek
status: done
created: 2026-10-06
---

# Bases: what counts toward the total

Count from the `[Base]` list in `universe.ini` (197), not from dockable space
objects (250): a planet's mooring fixture is a second object for the same base.
197 narrows to 181 reachable and **163 dockable**. `bases.py` owns the rule and
its reasons; `flvisits.py` and `serve.py` call it.

- **Ithaca Research Station** (`Li01_05`) is defined in
  `UNIVERSE/SYSTEMS/INTRO/intro.ini`, and `universe.ini` does not list `INTRO`
  among its 53 systems: it exists for the opening cutscene. Objects are gathered
  by following the `file` key `universe.ini` gives for each declared system, not
  by walking `SYSTEMS/`, which excludes stray files by construction.
- **The Asteroid Miners are not dockable** (2026-09-01): at 100 m from the one in
  Omega-7, target selected, no dock prompt. The reason is in the data, not in
  run-time reputation gating; the rule and the three candidates eliminated on
  the way are in `bases.py`. The total went from 181 to 167.
- **Story-locked bases are excluded by name** (`bases.STORY_LOCKED`): Tohoku's
  two, Alaska's one, and Planet Toledo, the only dockable thing in Omicron Minor
  (164, then 163 on 2026-09-13). Tohoku (M09) and Alaska (M11) rest on the
  owner's knowledge of the game, not on evidence: his save is on Mission_05, so
  their absence only means he has not reached them. Omicron Minor is backed by
  data: `st01` has no jump outside the five story Omicrons, so the system leaves
  the page.
- **Battleship Essex** in Leeds (`br05_04_base`) is undockable per
  `dockable_bases`, yet it is the only stockist of Adv. Dissolver and Adv.
  Sunrail (24790 credits, rank 22). Either the rule is wrong about Essex or the
  two guns are unbuyable in a normal game. The Equipment tab says "stocked by 1
  base you cannot dock at". Reopening the rule is the owner's call.

## Open bug: one base spells `Base`

`flvisits.load_objects` keeps an `[Object]` only when it carries both `nickname`
and `base`, matched case-sensitively, while `read_ini` keeps the case it found.
Across the 53 system files 247 objects spell it `base` and one spells it `Base`:
Planet Toledo, `St01_01_Base`. Measured 2026-09-12:

- `load_objects` returns 247 objects where the files hold 248.
- `bases.dockable_bases` lowers keys, so it counted Toledo: the two walks
  disagreed about one base.
- `common.read_state` maps a visit through `game.objects`, which had no entry, so
  Toledo sat in `unknown` even after docking.
- `market.base_index` could not name it: `fl.py jobs --all` printed a bare
  nickname and an empty system.

Story-locking Toledo removed the symptom, not the bug: the next object with a
capital `Base` falls out of the index the same way. The fix is one word in
`flvisits.py` and moves the number the app is about, so it is the owner's call,
made with `check_frozen.py`.

# Wrecks

**A wreck counts as found once its hash is in the save, emptied or not.** The
total and percentage never fall. A row's mark carries the rest, and each system
prints its tally once, above the list:

| | mark | reads |
|---|---|---|
| scenery | `·` | `empty hull`, in the dim not-found colour |
| not found | `-` | nothing |
| found, emptied | `+` | its loot, as history |
| found, still loaded | `*` | its loot, as something to collect, without the checkbox |

**A hull with no `loadout` key is scenery** (the `holds` flag): it holds nothing,
the game never sets bit 8 on it, and it counts as emptied the moment it is found.
Against all 220 saves on disk, over the 135 wrecks some save had recorded
(2026-09-13):

| the object | the game recorded the loot taken | count |
|---|---|---|
| has a `loadout` | yes | 82 |
| has no `loadout` | no | 53 |
| | disagreements | 0 |

The sample was 107 wrecks, then 109, then 135 the same day once he loaded
`Save707c.fl`, which alone carries 133; the ratio held at every size. Re-measure
with a throwaway script over `wrecks.load_wrecks` and `flvisits.parse_visits`.

**The game's mechanism confirms the rule.** Every wreck hull is
`destructible = true` with `hit_pts = 3600` and two fuses:

    fuse = fuse_suprise_<hull>,     0, 3601    ; fires at once, cosmetic damage
    fuse = fuse_suprise_drop_loot,  0, 3590    ; fires once you have shot it

`FX/fuse_suprise_solar.ini` defines the drop: 22 `[destroy_hp_attachment]`
blocks, all `fate = loot`, over `HpWeapon01..05`, `HpTurret01..06`, `HpShield01`,
`HpThruster01`, `HpMine01`, `HpCM01`, `HpCD01`, `HpTorpedo01`, `HpCargo01..04` and
`HpMount` (the `equip` half of the loadout), and one `[dump_cargo]` at
`origin_hardpoint = HpMount` (the `cargo` half). No loadout, nothing to drop. Of
the 157: 133 are `MISSION_SATELLITE` with that fuse, 23 the same with the key
spelled `Archetype`, and one is a `DESTROYABLE_DEPOT`, which has no fuse and
drops its cargo by being a depot. Checked and not the cause: `HpMount` exists on
all four hull models looked at; `lootable = true` on every gun involved.

- **The depot** is `Li04_depot_superconductors_surprise`, the Dallas Storage
  Container. A container names its cargo on its archetype
  (`surprise_superconductors` carries `loadout = surprise_superconductors`).
  `wrecks.archetype_loadouts` is the fallback: 40 Superconductors, and scenery is
  53, not 54.
- **23 wrecks spell the key `Archetype`.** `read_multi` keeps case, so
  `load_wrecks` case-folds the entry before the archetype lookup. Harmless today
  (all 23 carry their own loadout); `holds` and every loot list are byte
  identical across the 157 with and without the fold.

Scenery by system: Omega-5 (`bw02`) 23 of 27 hulls, Omicron Alpha (`hi01`) 19 of
24, Omega-11 (`bw04`) 6 of 10, Sigma-13 (`bw05`) 5 of 11, Omicron Gamma (`hi02`)
0 of 17. The owner remembered Sigma-13 as the empty one; it is not.

**Omicron Gamma is not broken.** Reported on 2026-09-13 as wrecks showing loot
that is not there, withdrawn by the owner the same day: all its wrecks are real.
It is a cache: 16 Corsair hulls carry `SECRET_c_co_elite2_hi02a` or `...b`, 20
Alien Artifacts plus two `fc_c_gun01_mark04` each (`lootable = true`). "Many
wrecks, most empty, a few with loot" describes Omicron Alpha. What was broken was
the page: `wreckLine` printed loot only when there was some, so a scenery hull
and a found, unopened, loaded one drew the same.

Refuted, do not retry:

- **The loot parser drops items** (`load_item_names` and unnamed items): the
  first wreck checked held eight kinds of cargo and parsed.
- **Repeated names confuse two hulls**: names repeat (68 over 157 wrecks,
  "Corsair Fighter" on 31), but every object has its own nickname and the visit
  flags key on its hash.
- **A tight cluster is one object drawn many times**: Omicron Alpha's are
  tighter and are separate objects.
- **The loadout belongs to the ship, not the wreck**: the same loadout sits on a
  wreck the owner emptied himself.
- **A loadout shared by several hulls means scenery**: New York's
  `Li01_suprise_li_elite_badlands_01`, `_02`, `_03` are three Patrol 27s sharing
  one loadout, and each holds four Justice Mk III.
