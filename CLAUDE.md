# fl-visits

Reads a Freelancer save and reports what the player has found, grouped by
system; further tabs read the game's data and patch the game. Own git repo,
mirrored to GitHub: the history is the undo button. The game runs on `volkface`.

## Working rules

Each rule comes from an incident recorded further down.

- **The owner is the instrument for what the files cannot settle**: what a bot
  says, where a course points, what floats in a system. The tool is the
  hypothesis. On 2026-09-13 his report was treated as something to disprove
  three times (route table, Omicron Gamma, callsign), and he was right twice.
- **An ambiguous report gets one question**: which reading he means. Not a page
  of evidence aimed at the wrong reading.
- **Measure, then state, with the date.** The saves grow as he plays: re-measure
  instead of quoting a count.
- **A check must not read what the tool wrote.** `fl.py jumps --check` once
  compared the graph with a table `routetable.py` had just written and reported
  2079 equal. A check that passes silently is this project's worst failure mode.
- **Key case in Freelancer INI files carries no meaning.** A reader that matches
  `base` and misses `Base` returns fewer rows and no error (Planet Toledo; 23
  wrecks spelling `Archetype`). Case-fold keys.
- **A display string is not a key.** System and faction names repeat.
- **One decision, one place.** The dockable rule is in `bases.py`, process
  access in `proc.py`, opening a folder in one function in `common.py`. In August
  `flvisits.py` and `serve.py` each held a copy of the base filter and disagreed,
  167 against 181.
- **Do not print a number that implies a model the files do not prove**
  (spoilage cost, job opposition).
- **Every game-file writer** keeps `<file>.vanilla`, builds from it so running
  twice equals running once, writes atomically and restores the file mode
  (`persist._save` for BINI, `persist.write_raw` for raw bytes), and in a file
  with two writers touches only its own bytes.
- **Find addresses and patch sites by signature**, never by a hardcoded offset.
- **A five-second poll compares, never rebuilds** (see *The page*).

## Where things live

Three folders, one per layer, settled 2026-09-07 to the owner's spec in
`bug-and-feature-tracker.md` (his own notes, untracked). The folder says what a
file may do:

| Folder | Holds | May |
|---|---|---|
| `data/` | files the app ships or is given | nothing; it is data |
| `backend/` | one `<tab>.py` per tab, plus `common.py` | read the game, answer an endpoint |
| `backend/game/` | readers of the game's own formats | read files. No HTTP, no state |
| `backend/live/` | the patchers | **write**: process memory, or a game file with a `.vanilla` beside it |
| `frontend/` | one `<tab>.py` per tab, plus the shell | style and behaviour, nothing else |

`tabs.py` at the root is the site map, the one place the shape of the page reads
at once; it is neither backend nor frontend. `fl.py` is the one entry point for
every command line.

| File | What |
|---|---|
| `serve.py` | routes, and nothing else. 127.0.0.1:8731 |
| `tabs.py` | which tabs exist, and which pair of files each one is |
| `fl.py` | `fl.py <command>`; run it bare for the list |
| `check_frozen.py` | fingerprints every value `flvisits.py` derives, over every save |
| `check_views.py` | draws every view in a real browser and reports which throw |
| `check_windows.py` | measures the Windows structs and symbols, from any platform |
| `backend/common.py` | the loaded game, the per-request save, the house grouping |
| `backend/game/flvisits.py` | save decoding, the nickname hash, game data loading |
| `backend/game/bases.py` | which bases can be docked at, who owns them, and the nav map cell they sit in |
| `backend/game/wrecks.py` | the 157 secret wrecks and their loot |
| `backend/game/market.py` | commodity prices per base, and the margin between two of them |
| `backend/game/weapons.py` | gun and munition stats turned into DPS |
| `backend/game/equipment.py` | buyable guns and shields, and which dealers stock them |
| `backend/game/reputation.py` | the empathy model: what an action does to every faction |
| `backend/game/ships.py` | which ship the save is flying, and how big its hold is |
| `backend/game/netlog.py` | the Neural Net log out of a save |
| `backend/game/story.py` | how far through the campaign a save is, and what that state is called |
| `backend/game/news.py` | the 403 news items and the story window each one runs in |
| `backend/game/rumors.py` | what the people in every bar say, and who is saying it |
| `backend/game/infocards.py` | the RT_HTML half of the resource DLLs, where rumor text lives |
| `backend/game/jobs.py` | what the job board at every base can pay |
| `backend/game/jumps.py` | every jump between systems, and the shortest way through them |
| `data/story-states.txt` | the 42 story states in order. `MissionNum` in a save indexes this |
| `data/marks.json` | which log entries are starred and read, and the favourite guns. **Untracked**: personal state |
| `data/trade.json` | the credits-to-friendly figure and whether the watcher is on. **Untracked**: personal state |
| `backend/live/proc.py` | the only code that touches another process. Picks its implementation at import |
| `backend/live/proc_linux.py` | `/proc/<pid>/{maps,mem}` |
| `backend/live/proc_windows.py` | `ReadProcessMemory` and friends. **Never run** |
| `backend/live/speed.py` | cruise speed of the *running* game |
| `backend/live/thrusters.py` | the same for the six thruster bonuses |
| `backend/live/tradelane.py` | trade lane speed and the 999 cap on the HUD readout |
| `backend/live/dockdist.py` | when the autopilot cruises to a dock, and where it takes over |
| `backend/live/bestpath.py` | flhack's five route bytes, in memory or in the DLL files |
| `backend/live/inject.py` | the code cave, and how a stub gets into it |
| `backend/live/persist.py` | writes the live speeds back into the game's files; `write_raw`, the atomic byte writer |
| `backend/live/routetable.py` | writes the shortest routes into the game's own route tables |
| `backend/live/drawdist.py` | scales asteroid `fill_dist` across the 153 field files |
| `backend/live/solardist.py` | puts a floor under the cull distance in `solararch.ini`, so stations stop vanishing |
| `backend/live/levels.py` | the level ladder in `ptough.ini`, and how far it goes |
| `backend/live/callsign.py` | what the bots call you: four sites patched in `content.dll` |
| `backend/live/empathy.py` | what killing a Nomad is worth to the other 51 factions |
| `backend/live/trade.py` | trading for standing: follows the hold, prices it, writes the result |
| `backend/live/newgame.py` | what a new game starts you in |
| `data/freelancer-map.jpg` | the sector chart, served at `/map.jpg`. **Untracked**: fan-made, not ours to redistribute. Drop your own copy in |
| `design/` | the visual design, a Claude Design canvas: the source the page is built from |
| `run.sh` | start the server and open a browser on it |
| `run.cmd` | the same three lines for Windows. **Never run** |

- **A tab is a pair of files with one name**, `backend/<name>.py` and
  `frontend/<name>.py`; either half may be absent (a tab that only draws what
  `/api/state` carries has no endpoints). Adding one is a row in `tabs.py` plus
  the files it names.
- **Modules under `backend/` have no `if __name__ == "__main__"` block.** Inside a
  package a relative import has no parent, so `python3 backend/live/dockdist.py`
  cannot run. Each keeps its `main()`, reached through `fl.py`.
- Everything new goes in its own file. `flvisits.py` supplies the primitives;
  `wrecks.py` has its own INI reader because loadouts repeat their `equip` and
  `cargo` keys and the reader in `flvisits.py` collapses repeats.

## `flvisits.py`: run `check_frozen.py` before and after every edit

The module unpicks three undocumented formats: FLS1 save encryption, BINI binary
INI, and PE resource tables in the DLLs. It resolves a **one-way** hash by brute
force: hash every nickname in the game data and look the result up. The
constants were found by search and confirmed against real saves; several
plausible alternatives scored zero. None of it can be re-derived from the code,
so a tidy edit breaks it silently: the report still prints, and it is wrong.

**Run `check_frozen.py` before and after, and diff.** Every line must match byte
for byte except `AutoSave.fl`, which the game rewrites while you play. No clean
diff, no commit. Reading the diff and reasoning about it does not replace this.
The script fingerprints the hash table, the string tables, the system walk, the
dockable set and each save's resolved visits with their flags, over every save
on disk. On 2026-08-31: 96 saves, 219,634 visit entries, 7,372 resolved, every
digest identical.

The file was frozen in August and unfrozen on 2026-09-07 at the owner's request:
three thaws in five weeks, each correct, each a round trip. The check made them
safe, not the freeze. Every edit gets a line here:

- **2026-08-31.** The denominator counted all 197 `[Base]` entries in
  `universe.ini`, 15 of which no space object points at; three are intro-cutscene
  copies of Manhattan sharing one `strid_name`, so "Planet Manhattan" printed
  three times as unvisited. The two programs would have disagreed, 197 against
  182.
- **2026-09-01.** The dockable filter sat in both `flvisits.py` and `serve.py`;
  it moved to `bases.py` and both call it. Eight lines in `main()`, none in the
  decoding, the hash or the loaders. Same save before and after: 3430 object
  nicknames, 2188 visit entries, 486 resolved by both, identical.
- **2026-09-06.** `ipath` was defined twice, at lines 47 and 121; the second
  shadowed the first, leaving 19 dead lines whose docstring described behaviour
  nothing ran. The live one took the useful half of that docstring. A comment's
  167 dockable / 30 dropped became 164 / 33 (163 / 34 since 2026-09-13).
- **2026-09-07**, for bar rumors. `read_string_table(path)` became
  `read_string_table(path, rtype=RT_STRING)`: rumor text is RT_HTML (type 23),
  names are RT_STRING (type 6), and the PE walk is the same. `resource_dlls()`
  came out of `load_names()`, so `infocards.py` reads the same seven DLLs in the
  same order. All 123 stable lines identical.

## Saves

### What the reader was verified against

- All 301 hashes in a live save resolved to a nickname in the game data. The same
  brute force without lowercasing the nickname scores 40 of 301, so the match is
  not coincidence.
- The flag model held across a play session: a base moved from "revealed" (1) to
  "docked" (30/31) while the player flew.

### Visit flags

Read them as bits. Bit 1: seen, on the nav map. Bit 16: a secret, so a found
wreck reads 17. **Bit 8: the wreck has been emptied**, so it then reads 25
(settled 2026-09-01). Bases read 30 or 31 once docked, 1 when the story has only
revealed them.

Evidence for bit 8: a save with five found wrecks, four at 25 and one at 17, the
Storm in Dublin (D6), which the owner had found and left loaded on purpose. And
New York's three Patrol 27 hulls read 25, 17, 17 in an earlier save and 25, 25,
25 later; a fixed property of an object cannot change in flight. That
transition was never caught in a file: the 20 saves then on disk all held final
flags. To get it on disk, note a wreck's flag, empty it, and keep both saves.

- 19 `visit` entries carry small ids from another id space and flag 65. `FLHash`
  does not cover them; they are not bases and do not affect the report.
- `AutoSave.fl` changes while the game runs. Test against a fixed `Save*.fl`.

### Story state: `[StoryInfo] MissionNum`

An index into a table of 42 names. The names are in no INI: they sit as a
contiguous block of strings in `DLLS/BIN/content.dll`, written in reverse, and
are kept as `data/story-states.txt`. Verified on all 18 saves on disk
(2026-09-07):

    Restart.fl   Mission_01a  MissionNum 1   -> mission_01a_loaded
    Save116a.fl  Mission_02   MissionNum 7   -> mission_02_accepted
    Save707c.fl  No_Mission   MissionNum 5   -> freetime_01_02
    Save144d.fl  Mission_13   MissionNum 40  -> mission_13_accepted

The states between missions have names of their own, so a reader that only
understood `Mission_NN` would call the `No_Mission` save "nowhere".

### The log

A log line is `log = <ids>, <count>, [<param ids>, <type>, 0] * count`, and
`type` is the **ASCII code of the placeholder's letter**. `22505` reads "Meet
Juni on Planet Manhattan%M" with parameters `(196609, 83)`, `(0, 82)`, `(1, 77)`;
77 is `M`, so `%M` takes the third. Where the detail is real it is the entry's
second half: "Start scanning nearby ships%M" plus `(25240, 77)` reads "Start
scanning nearby ships / Scan nearby ships and look for anything suspicious".
Across every save: 210 texts carry a placeholder, all `%M`, and 186 have a
parameter of that type. The other 24 have none, so the placeholder is dropped; a
bare `%M` reads as corruption.

**A log entry has no date.** The save holds one clock, `tstamp` (a Windows
FILETIME of the write), plus `total_time_played`. Position is the chronology:
new entries are prepended, index 0 is the newest.

**`base_visited` lists the docked bases in the order of first docking**, which is
a real receipt time for a bar rumor. Its values are `FLHash` of the base
nickname. Checked twice: across 162 saves an older save's list is a prefix of a
newer one's 137 times against 14, and all 14 are two playthroughs at the same
`total_time_played`; on the live save all 24 values resolve, the set equals the
docked set from the visit flags, and the order opens Planet Manhattan, Planet
Pittsburgh, Baltimore Shipyard, the campaign order. `common.dock_order` reads it
for order only. `Ctx.docked` stays the authority, so a save without
`base_visited` leaves rumors unranked, not lost.

**Not built: dating a log entry by its mission file.** 97 of the 299 distinct log
ids across 162 saves appear as `Act_NNIds` in exactly one `DATA/MISSIONS/M*/`
file, and a mission maps to a story state, the axis `news.debut` uses. The other
202 are random-job text with no story position. One interleaved timeline is
buildable: date the 97, place the rest by position between dated neighbours. On
2026-09-10 the owner chose the streams in order instead.

## Bases: what counts toward the total

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

### Open bug: one base spells `Base`

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

## Wrecks

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

## Factions, news, rumors, commodities

### A faction with nobody in any bar is out of the Reputation tab

Cut on 2026-09-09 at the owner's request, 55 factions to 47. A faction with no
`[GF_NPC]` in `mbases.ini` has nobody to fly for or against. That is eight of the
55 groups in `empathy.ini`: Nomads, `fc_f_grp` (Fugitive), Kress's Men,
Quintaine's Men, `fc_uk_grp` (its name resolves to a single space), and the
story doubles `fc_kn_grp`, `fc_ln_grp`, `fc_rn_grp`. The next faction up has
seven bar NPCs.

- **Cut from `events` and `empathy`, never from `names`.** `fc_kn_grp` and
  `fc_uk_grp` own bases; cutting their names blanked the owner badge on each.
- `_disambiguate` appended `(nickname)` to three names because `fc_ln_grp` was a
  second "Liberty Navy" (and likewise Kusari Naval Forces, Rheinland Military).
  All three doubles were cut, so nothing collides. The function stays: a mod that
  gives one of them a bartender brings the clash back. The four house police
  forces still collide and take their house code.

### News

All 403 `[NewsItem]` entries in `DATA/MISSIONS/news.ini` carry
`rank = <from state>, <to state>`: 223 have opened at `mission_03_loaded`, 385
at `mission_13_accepted`. A window closed behind you differs from one not
reached, so the tab draws items by debut and marks each live or past.

364 are distinct (2026-09-10). 17 are empty (no headline, text, category or
base; all debut at `mission_end`). 22 repeat another item's headline and text,
differing in window and sometimes icon: "Arrival of Freeport 7 Survivors" is
filed at `mission_01a_loaded` as `critical` and at `mission_01a_accepted` as
`world`. A duplicate folds into the copy that opened first, taking the wider
window, the union of the bases, and `critical` if either had it.

A mark's key is `news:<debut>:<headline>`, so the fold would have dropped 9 of
the 266 news marks. `_collapse` therefore carries `debuts`, the full list; the
page treats a row as marked if any of its keys is and clears all of them on
unmark. After the change: zero unreachable keys, 18 marks on folded rows.

### Bar rumors

- **Every rumor is available from the first minute.** All 7803 `rumor` lines in
  `mbases.ini` carry one window, `base_0_rank .. mission_end`. The window is
  applied anyway, for mods; **do not look for a rumor that unlocks**. The tab
  scopes rumors by where you have docked: 161 bases carry rumors, median 16.
- **Rumor text is RT_HTML, not RT_STRING.** `MiscText.dll` holds 3101 resources
  of type 23 and none of type 6. All 3030 distinct rumor ids resolve.
  `infocards.py` unwraps the RDL: `<PARA/>` is a line break, the rest is dropped.
- **Not built: `rumorknowdb`.** 564 lines over 112 targets name the hidden jump
  hole (`li02_to_li04_hole`), wreck or base a speaker knows about: a real link
  between the Neural Net and the Systems tree, out of scope until asked for.
- **Mission dialogue cannot be added**: a `[Dialog] Line` names a `.utf` audio
  asset, `DATA/AUDIO/DIALOGUE/` is 40 folders of sound, and the game ships no
  subtitles for in-space comms. That is why "news and dialogue" became "news and
  bar rumors".

### Three commodities spoil

| Commodity | `decay_per_second` | `hit_pts` | the game's own infocard |
|---|---|---|---|
| Alien Organisms | 1.0 | 100 | `>>>HIGHLY PERISHABLE <<<` |
| Luxury Food | 1.0 | 100 | `>>>HIGHLY PERISHABLE <<<` |
| MOX | 1.0 | 200 | `>>>PERISHABLE <<<` |

The other 102 of the 105 commodities read `decay_per_second = 0`,
`hit_pts = 250`, no banner. All three are traded. *Which* spoil is a number in
`select_equip.ini`; *how badly* is infocard text (RT_HTML, another table). The
two sets agree, so `market.perishable` derives the set instead of holding typed
nicknames.

**The files do not say what spoiling costs on a run.** `decay_per_second` sits
among `pod_appearance`, `loot_appearance` and `hit_pts`, properties of a
container floating in space. Routes shows the game's label, keeps `run` a plain
multiplication, says so in the note, and offers a checkbox. No decay model
without evidence. One observation exists: on 2026-09-15 the trade watcher saw
the owner's Alien Organisms lose a unit every few minutes in the hold. No rate
was measured.

### Systems are identified by nickname

Display names repeat: Omicron Beta is `Ew02` and `St02`; Omicron Major is
`St03`, `St03b`, `St02c` and `FP7_system`; Unknown is `Ew05` and `Ew06`. Only one
of each group has a market, so keying the trade selectors on labels works today
by luck. `market.py` rows carry `sys_nick`, the identity, and `system`, the
printed label.

## Equipment

- **One price at every dealer.** The multiplier in `market_misc.ini` is `1.0` on
  all 10871 rows, and no item's price differs between bases. The rank (0 to 30)
  and reputation (-1 to +0.8) gates are the same everywhere too, checked across
  the 366 goods sold at more than one base. The price sits on the item, the
  expansion answers *where*. Do not port the Trade tab's dearest-versus-cheapest
  logic.
- **No item whose nickname starts with `npc_` is sold anywhere.** That and "no
  `[Good]`, so no price and no dealer" are all the catalogue drops; the counts are
  in `equipment.py`. If the filter goes, `npc_shield01_mark10` at 10127 capacity
  heads the shield list, and no player can buy it.

**Listed means obtainable, and each row says how** (`source`, 2026-09-12): `sold`
at a dockable base, `wreck`, `loot` (drops off an NPC), or `none`. The tab shows
the first three; a checkbox adds `none`. The first rule (sold, or in a wreck)
kept the 17 codenamed guns, the hardest hitting in the game and all wreck loot,
and dropped 12 others.

- **`loot`**: `MISSIONS/lootprops.ini` gives `special_nomad_gun01` and `02`
  `drop_properties` of 10, and `SHIPS/loadouts.ini` hangs them on five and four
  Nomad loadouts. They are the two hardest-hitting guns in the game, 2568 and
  2543 hull DPS, above CERBERUS. The rule needs both halves: a drop chance alone
  admits the twelve `shield01_mark08_lf`-shaped shields, which carry a 6 and sit
  on no ship; a loadout alone admits all 26 `npc_` shields, which carry no chance
  and would head the capacity list (10127, against a best buyable 289150). One
  rule for guns and shields; shields come out at 79 of 121.
- **`none`**: Death's Hand Mk III appears in `weapon_equip.ini` and
  `weapon_good.ini` and nowhere else in `DATA/`: no dealer, wreck, loadout,
  mission script or loot entry. The same holds for Reaper Mk III, the two Order
  turrets Mk II, Vengeance Mk III, Rowlett's Revenge and the Nomad Prototype
  (NPCs carry it, nothing drops it). The owner's save carries none of the twelve.
  Without `source` the list could not tell "not in the game" from "the reader
  lost it".
- **No "the story gave it to you" source.** `msn_playerloadout`, the ship the
  campaign hands you at the end, carries one thing no dealer sells,
  `special_nomad_gun01`, which is already `loot`.
- `drop_properties[0]` is read as a chance: across all 434 entries it runs 0 to
  100; 100 on every commodity, 33 on nanobots and shield batteries, 8 on most
  guns. Only non-zero matters, so a wrong unit costs a word, not a row. Fields 2
  and 3 are always equal and are not the price.

## Job boards

A bar shows what it offers today, never what it can offer; the Jobs tab shows
the second (2026-09-12).

| File | What it gives |
|---|---|
| `DATA/MISSIONS/mbases.ini` | `[MVendor] num_offers = 2, 4`, the slots on the board, and `[BaseFaction] mission_type = DestroyMission, <min>, <max>, <weight>`, one faction's difficulty band and its weight in the draw |
| `DATA/RANDOMMISSIONS/diff2money.ini` | 23 rungs, difficulty to credits, 1800 at 0.0 up to 247065 at 100.0 |

A board's ceiling is the money at its highest `max`, its floor the money at its
lowest `min`.

- 160 of the 163 dockable bases run a live board. Planet Primus and Planet Gammu
  carry no offering faction; Planet Sprague carries one with
  `num_offers = 0, 0`. `fl.py jobs --all` lists the three. (Planet Toledo was the
  fourth until it left the denominator on 2026-09-13.)
- All 241 `mission_type` rows are `DestroyMission`, vanilla's only random type.
  The kind is carried anyway, so a mod's new type is listed, not counted as a
  bounty.
- 101 bases have one offering faction, 51 two, 11 three, one five: Trafalgar
  Base, weights 40/20/20/10/10.
- The ceiling is 146192, at Ruiz Base, Planet Malta, Planet Crete and Tripoli
  Shipyard. The lowest live board pays 2200.

**Interpolate between rungs; never turn it into a lookup.** Four of the 19 band
edges miss their rung by float32 noise, `0.11239` in one file against `0.112387`
in the other. Interpolation lands them within a credit; a lookup would have to
invent what a value between rungs means.

**Not printed**: what the job sends at you, and what the best of a full board
comes to. `npcranktodiff.ini` maps (NPC rank, wing size) to the same difficulty
scale, so the game inverts it to pick your opposition, but the direction of that
inversion and the spread of the draw inside a band are in no file.

"Open" means a system holding at least one base you have docked at (the owner's
call, 2026-09-12); the undocked bases in such a system are the point of the tab.
On that day's save: 12 open systems, 63 bases, 62 boards, 55 docked. Sorting and
filters run on the page (160 rows). The view refetches on every entry, because
docking somewhere new between two looks is what the tab is for.

## Bribes

A `[GF_NPC]` belongs to the `[MBase]` above it in `mbases.ini`: the file nests by
position only, so one walk that remembers the current base places every `bribe`
line. `game/jobs.py` and `reputation.load_bar` make the same walk. Counted
2026-09-12:

- 41 of the 55 factions are bribable, across 162 bases.
- All 2386 `bribe` lines read 10000, so the list answers *where*, never *where
  cheapest*. What the engine charges is `BRIBE_RATE` in `reputation.py`.
- 3 to 94 bases per faction, median 22, so the page lists only the ones the save
  has docked at (median 7 on that save).
- On that save 11 of the 41 had no bar he had reached, the Rheinland Police among
  them (25 stations take the money, he had landed on none). The row says so in a
  sentence, and `bases_total` makes an empty list read as a journey, not a failed
  lookup.

Layers as in Jobs: `load_bar` returns base nicknames; `backend/rep.py` narrows
them by `GameData.bases` (dockable) and by the save (visited) and builds the
shared base shape. No second base index; `market.base_index` is deliberately not
imported. `_reputation` reads `ctx.saved()`: one decode gives the standings and
the docked bases (a separate `fl.decode_save(ctx.save)` is the second-read trap
`common.Ctx` exists to prevent).

## Routes and Best Path

### The jump graph (Map -> Best Path)

An `[Object]` carrying `goto = <system>, <object>, <tunnel>` is a jump: 232
across 52 systems, all two-way, each `goto` naming an object the same walk found.
84 gates, 140 holes of five kinds, two `nomad_gate`, six Dyson airlocks. The save
records seen jumps as it records bases, by `FLHash` of the nickname, at flag 1.

- **The nodes are jump objects, not systems.** New York holds a gate and a hole
  to Texas, and which one you want depends on where you came in. Start at any
  jump in the departure system for free; a jump costs one hop and no distance;
  flying to another jump in the same system costs the distance between them;
  arrival is the first jump landing in the destination.
- **Two costs, disagreeing on 49% of the 2182 reachable pairs**, so both are
  drawn: fewest jumps (ties broken on distance) and least flying (ties broken on
  jumps), one Dijkstra under two orderings. No flying route is longer than the
  fewest-jumps one; no jumps route has more hops than the least-flying one.
- **Distance covers the middle systems only, without trade lanes.** Both ends are
  picked by hand; lanes would need where each runs and whether it stands, which
  the files do not settle.
- **A link counts as found when either end has been seen.** 14 of 116 links on
  that day's save were marked at one end only. Each step still carries `found`
  for its own object.
- **Five systems are an island**: `st01`, `st02`, `st02c`, `st03`, `st03b`, the
  single-player Omicrons. 470 of the 2652 ordered pairs have no route; that is
  the data.

Against `UNIVERSE/systems_shortest_path.ini`: equal on 1502 of its 2079 pairs,
this tool shorter on 577, longer on none. New York to New London is four jumps in
the table, `li01 > li02 > iw04 > br02 > br01`, and three through Magellan,
`li01 > iw03 > br02 > br01`, every hop a gate. `fl.py jumps --check` is that
comparison and guards the graph. It reads `<name>.vanilla` when one exists,
because after `routetable.py` wrote the table it reported 2079 equal.

### How the game routes

- **The game reads its route table once, when the world loads**, and that load
  also reloads `content.dll` and `server.dll`, wiping any memory patch in them.
- `shortest_legal_path.ini` is gates only, and it is what Set Best Path reads in
  vanilla. `systems_shortest_path.ini` includes holes. Rows whose route has a hop
  no gate makes: legal 0 of 1225, systems 1440 of 2029.
- In `content.dll` the two filename strings sit at `0x70a828c`
  (`Universe\shortest_legal_path.ini`) and `0x70a82c4`
  (`Universe\systems_shortest_path.ini`); the slots at `+0x89512` and `+0x89492`
  point at them, and the router reads `+0x89512`.
- **flhack's five bytes do two things**: swap the two filename pointers (the low
  halves `0x8C` and `0xC4`), **and** set a type byte its own source comments as
  `mov byte [edi], 0x03 ; treat jump gates & holes the same`. On build v1.0
  `server.dll` holds 0x0A at that site, so the byte the patch changes is also
  the build fingerprint: "wrong build" and "already patched" are one check.
  This install matches flhack's build 10: `server.dll` 0x0A at RVA `0x1ACE3`,
  `content.dll` 0xC4 at `0x89492` (build 11's offsets give 0x24 and 0x90).
- **Without the type byte, a hop with no gate sends the course to the system
  origin.** 2026-09-13: Set Best Path from Battleship Matsumoto to Ohashi Border
  Station (Hokkaido to Shikoku) pointed into `Ku05_Sun`, a `sun_2000` at
  `[0, 0, 0]`, because the written route's first hop, Hokkaido to Kyushu, exists
  only as a hole.

### What `routetable.py` writes: two modes

The table and the five bytes move together; either alone is broken.

| mode | the game reads | table | the five bytes |
|---|---|---|---|
| `gates` | `shortest_legal_path.ini` | gates-only shortest paths, 136 shorter | out |
| `holes` | `systems_shortest_path.ini` | hole-inclusive, 1170 routes, 648 jumps saved | in, written into the DLL files by `bestpath.file_write` |

`--revert` restores both tables and the bytes. The switch is a box in the Engine
tab: the mode lives in the files the game reads, not in the game.

- `gates` writes into `shortest_legal_path.ini` **at that file's own width**.
  Over its 1225 rows: 136 shorter, 0 longer, 0 without a gates-only route, and 0
  naming a system the file does not list. That last count is 234 with holes
  allowed; widening the file to fit them is what broke it: on 2026-09-12 one
  hole-inclusive content went into both files (1723 of 2029 rows with a gateless
  hop). 366 rows change: 136 shorter, 230 equal in jumps with less flying.
  `--flying` asks for least distance outright.
- `content()` refuses a gateless hop in `gates` mode and a system the file does
  not list. Both refusals were proved by running the 2026-09-12 rule through
  them: 1096 and 234, nothing written.

### Why the file works and a memory patch cannot

flhack hooks the load: a `jmp` over `add esp, 0x214` at
`Freelancer.exe+0x1a81a8`, the instruction right after both DLLs load
(`81 c4 14 02 00` is there in this install). `Freelancer.exe` is never reloaded,
so the trampoline fires on every world load, re-finds both DLLs with
`GetModuleHandleA`, re-checks the build and re-applies the bytes before the
router reads. flhack writes nothing to disk, so the hook is its only option. This
tool may write files: bytes in the DLL files come back with every load. No stub,
no cave.

`live/bestpath.py` first wrote the five bytes into memory from a button
(2026-09-12). It read ON, the build matched, the swap direction was right, and
the game still routed Hokkaido to Tau-23 as
`Hokkaido > New Tokyo > Kyushu > Tau-29 > Tau-31`, the gates-only row, where the
holes table says `Hokkaido > Kyushu`. The patch arrived after the table was read
and died at the next load. A patch reading ON is not a patch working: flying the
route settled it. The memory control left the Engine tab that day;
`fl.py bestpath` remains.

The removed control also hid a collision: `backend/engine.py` and
`backend/bestpath.py` both offered a GET `bestpath`, and `tabs.py` merged them
with `dict.update`, so the later module won silently. `_table` now raises on a
repeated name, and the guard was proved to fire. An endpoint name is a tab's
address.

## Changing the running game: memory

The Engine tab has two halves: process memory, and GAME FILES. Memory writes
last until the game closes; the files are the defaults.

### Cruise speed

`CRUISING_SPEED` is one global in `constants.ini`, read once at startup, in
exactly one of the 8370 files under `DATA/`: 5000 in open space and 500 in an
asteroid field cannot be expressed in data. Writing 20.0 into a live game on
2026-09-01 slowed the ship on the spot, without reload or crash, so the value is
read per cruise burn.

- **Never hardcode an address.** `common.dll` loads somewhere else each run.
  `speed.py` finds the value by the three floats after it, `5.0, 3.0, 0.25`, one
  hit in the whole address space. Searching for the speed itself fails: `1000.0`
  matched 6948 places.
- **Two kinds of address.** `speed.py` scans, because `CRUISING_SPEED` sits in a
  loaded copy of `constants.ini`. `tradelane.py` and `dockdist.py` use flhack's
  addresses (Jason Hood, 2014; source was at `~/Downloads/flhack/`) inside
  `common.dll`, resolved against the module base from `/proc/<pid>/maps`. A scan
  was tried first and found a lone 2500.0 that was a CommConsts value. Both
  modules read the float first and refuse an implausible value, which catches a
  wrong build or a moved address.
- Those addresses are in `.rdata`, read-only in the process. `/proc/<pid>/mem`
  bypasses page protection, so no `mprotect` is needed (flhack needs one on
  Windows).
- `kernel.yama.ptrace_scope` is 0 on `volkface`, so no privileges beyond the same
  user are needed. Where it is not 0 this stops working and must say so; never
  "fix" it by loosening the setting.
- **Read `/proc/<pid>/mem` frugally.** `volkface` has 7.6 GB and sits at a few
  hundred MB free with the game up. The first `find_scratch` pulled whole
  mappings into Python and walked them byte by byte, and the desktop stalled. It
  now reads 1 MB chunks, matches with `bytes.find` and stops at the first hit:
  0.1 s and 14 MB.

### Docking: cruise distance and takeover (2026-09-05)

**There is no docking distance in the game's data.** All 1252 INI files under
`DATA/`, searched for keys containing `dock`, give `docking_sphere` and
`dock_with` on objects and `act_lockdock` and friends in mission scripts, nothing
global. `Trade_Lane_Ring` in `solararch.ini` has no `docking_sphere` (`jumpgate`
has 225, `jumphole` 150); `constants.ini` has nothing.

- **Whether the autopilot cruises to a dock** is a float in `common.dll`:

      0x62fe171  d8 1d c0223a06   fcomp dword [0x63a22c0]   ; 1750.0

  In the shipped file and the running game. It is flhack's `ADDR_DOCK_DIST10`,
  "Cruise to dock from". Four instructions read it: this `fcomp` and three `fmul`
  about 1250 bytes earlier, so changing it moves more than the cut point. The
  compare is gated by `[esi+0x365]`, cleared right after, so the answer is
  latched once when the dock is ordered. At any real trade lane range 1750 and
  300 both answer "cruise": moving it changed nothing anyone could feel.
- Entering a trade lane is a dock: flhack's help says the proximity radius
  default of 495 "is that used by Trade Lanes". That was the owner's lead.
- **Where docking takes over is a code patch, never a number**: `[ebp+0x50]`, a
  descriptor field loaded at `0x62fe758`, so the only place to change it is the
  instruction that reads it. flhack calls it "Closer docking";
  `dockdist.py --takeover` ports its stub. Settled at **200 m** for lanes and
  gates after the owner flew 100, 200, 400 and 600; flhack picked the same value.
- **Disproved: `0x639f44c`.** It initialises a field holding the same 1000.0. The
  owner flew it at 100, 1000, 5000 and 10000 with no difference to a lane
  approach. The knob was removed the same day.
- `select_equip.ini` was the first wrong lead; see *Hand changes to the install*.

### Injecting code (`inject.py`, 2026-09-06)

flhack allocates executable memory with `VirtualAllocEx` and keeps the pointer at
`0x67bf40`. `/proc/<pid>/mem` cannot allocate and does not need to: `common.dll`
`.text` ends at `0x6398730` with 2256 bytes of zero padding inside a mapping that
is already `r-xp`, linker slack before `.rdata`. Writing there from outside works
because `/proc/<pid>/mem` goes through page protection.

- **The game must not write into the cave**: the page is read-only, and the first
  stub, which stored `dockwith` there, killed Freelancer on the first call.
  Anything the stub writes at run time goes to `inject.find_scratch`, a zero run
  in an already writable mapping. Constants stay in the cave, written only from
  outside.
- **Use a stub only for a computed value.** A pair of pointers or a constant is
  a byte patch.
- **Not every freeze is the tool's.** The one on 2026-09-05 was
  `i915 GT0: rcs0 reset request timed out`, an Iris Xe GPU hang, with the stub in
  memory and innocent. Read the journal first.

### Trade reputation (`live/trade.py`, 2026-09-15)

Hauling ten million credits through a Liberty station left everyone there
indifferent. **It cannot be a data edit.** The parser's keyword pool for
`[RepChangeEffects]` sits in `DLLS/BIN/content.dll` at file offset `0x11a860`:
`MarketGood`, `FactionGood`, `random_mission_abortion`, `random_mission_failure`,
`random_mission_success`, `object_destruction`, `event`, `group`,
`empathy_rate`, `RepChangeEffects`. Four events, no fifth. So `trade.py` writes
standing into the running game, and the game keeps it at its next save. No game
file is touched.

- **A trade's size is units moved times that base's price**, both directions,
  never the balance: one visit can also sell a gun, pay for repairs and collect a
  bounty. A base pays for goods it does not stock: ten Superconductors sold at
  Planet New Berlin moved the balance 301,186 to 302,186, 100.00 a unit, the
  `goods.ini` price, a seventh of the 700 Oder Shipyard pays two jumps away.
  `market.base_prices` is that walk, lifted out of `load_market`.
- **Standings in memory**: 55 entries of 8 bytes, `float32` first, in the order
  `initialworld.ini` declares its groups, in many copies 0x1b8 apart. **Not
  `empathy.ini`'s order**: the two agree for about twenty slots, then diverge.
  Against the running game `initialworld.ini` matches 55 of 55, `empathy.ini` 23;
  the wrong order writes a correct number onto the wrong faction. `rep.Model`
  carries `order`.
- **Clamp a write at ±1.0, the engine's limit, never at `reputation.BOUND`**
  (0.9, the tab's planning bound). Across 224 saves standings use the full ±1.0
  and 172 sit above 0.9. A clamp at 0.9 turned a 52,500-credit trade asking the
  Junkers for +0.00875 into four factions set to exactly 0.9: a loss six times
  the gain, the wrong way.
- Which copy the game reads is unknown, so all are written. Of 21 live copies
  after a verified write, 18 matched the save and 3 were stale.
- **The hold comes from the save.** Freelancer writes the save on the
  transaction (four of four), and not on docking. Reading the hold from memory
  failed three ways: a cached address (the cargo array moves between dockings,
  and a dead copy still answers), re-ranking copies every tick (the save they
  were scored against is rewritten by the trade itself), and a vote of all copies
  (the candidate set was pinned while the cargo was aboard). Ranking copies by
  their match to the save picks a stale one by construction. The hold is tracked
  continuously, flight included; the base decides only whether a change may be
  billed.
- **A change the balance does not account for bills nothing**: salvage, loot and
  spoilage move the baseline. The owner's Alien Organisms lost a unit every few
  minutes and would otherwise have read as sales.
- **Traps when checking**: the write lands in the save after the one that
  triggered it, a second later, so the two saves around a trade show nothing
  moved; and standings compare at 1e-6, never tighter (`float32` in memory,
  `float64` in a save: an exact compare calls 47 of 55 different while every
  difference prints as `+0.00000`).
- **No cap on one trade** (`MAX_STEP = None`, the owner's call). The largest
  trade the game allows is a Dromedary's 275 units of Alien Organisms at 2000,
  550,000 credits, asking +0.0917, 18% of neutral to friendly. A cap at a tenth
  of the span turned 5.5 maximum loads into 10 and did nothing below 300,000,
  which is every ordinary run.
- **It counts only while the server runs**; `serve.py` starts the watcher at
  boot, not on the first request.

Verified end to end: sixty Superconductors at Oder Shipyard for the listed
42,000:

    Rheinland Military   +0.01456 -> +0.02156    +0.00700   the billed step
    Rheinland Police     +0.01467 -> +0.01712    +0.00245
    Red Hessians         -0.61762 -> -0.62007    -0.00245
    Bundschuh            -0.28254 -> -0.28534    -0.00280

47 of 55 factions moved, all through the empathy table, and the step is exactly
what the rate asks.

## Changing the game: files

Every writer here follows the writer rule in *Working rules*. Both writers in
`persist.py` put the file mode back because `mkstemp` creates 0600 and
`os.replace` carried that onto the game file: by 2026-09-13 **161 files** sat at
0600 instead of 0644 (every asteroid field, both route tables, `constants.ini`).
It worked only because the game runs as the same user; a shared install, a
`cp -p` copy or another user would have broken it. The 161 were repaired from
their `.vanilla` siblings.

**Two writers in one file touch only their own bytes.** `callsign.py` patches
four sites in `content.dll` and `bestpath.file_write` three more. Both used to
rebuild the file from `.vanilla` and apply their own sites, so the best-path
patch silently reset the callsign to "Freelancer Alpha 1-1". Both now read
anchors and shipped values from `.vanilla` and apply them to the current file;
`callsign.restore` resets only its four sites. Proved by running both in both
orders.

**Backups**: 163 `.vanilla` files (2026-09-13), plus an archive of every binary
and writable data file at `~/Games/fl-backups/`, verified by extracting it and
comparing hashes with the live files.

### Levels (`fl.py levels`, 2026-09-12)

The info screen's Current Level, Current Worth and Next Level Requirements all
come from **`DATA/MISSIONS/ptough.ini`, `[PlayerToughnessScale]`**: 39 rows of
`ptough_graph_pt = <worth>, <level>`, from `0, 0` to `2409599, 38`, the vanilla
cap. The ladder rises about x1.14 a rung over its top ten. Proved in the live
game: worth 757221 sits between row 29 (738187) and row 30 (842492), the screen
said level 29, and 842492 - 757221 = 85271, the Next Level Requirement shown.

- **`[Player] rank` in a save is a cache**: the game recomputes it from worth.
  Edit the ladder, never the rank.
- **Worth is money plus the ship and everything on it.** A first pass measured
  `rank` against `money` over 220 saves, saw rank fixed inside each story state
  while money varied sixty-fold, and concluded the campaign sets the level. The
  campaign hands out ships, so worth tracks the story: one term of a sum is not
  the sum.
- **Found by the two numbers on the owner's screen.** No INI key is called rank,
  worth or level (`rank` in `news.ini` is a story state); four scans of all 40
  binaries for an ascending ladder found only relocation tables. Searching the
  running process for int32 757221 and 85271 found them adjacent in the player
  block, with the table 300 bytes away as `(worth, level)` pairs, stride 8; a
  grep of the install's 8594 files for 2409599 named the file.
- `fl.py levels` extends the ladder past 38, built from the vanilla rows every
  time. The first added rung continues x1.14, so there is no seam at the old cap;
  the rest are a geometric run landing exactly on the requested worth. It refuses
  a value past int32 (it would wrap negative) and a ladder that does not strictly
  rise (a level you could never leave).
- Applied 2026-09-12: levels 39 to 50, 2,746,943 to 1,160,922,100, step x1.733.
- **Unknown**: whether the game reads more than 39 rows (`--restore` if it will
  not start), and what else the curve drives. The name suggests it also sets how
  tough the world thinks you are, which would make encounters harder; that is a
  reading of the name, not a measurement.

### Draw distance (`solardist.py`, 2026-09-15)

The tracker asked to see every base, gate, planet and jump hole. Of the game's
three levers the owner picked `LODranges`; map reveal and scanner range are out
of scope.

- **Planets, jump holes and gates were never the problem.** 54 of 55 `PLANET`
  archetypes and all 5 `JUMP_HOLE` ones ship with no `LODranges` (172 of the 511
  placed base and jump objects); gates reach 50000, the Nomad gate 60000.
- **Stations were**:

  | archetype | placed | shipped cull |
  |---|---|---|
  | `miningbase_badlands`, `miningbase_nomad` | 3 | 3000 |
  | `docking_fixture`, the mooring you dock at on a planet | 21 | 6000 |
  | six `miningbase_*` | 15 | 7000 |
  | `roid_miner2`, `space_port_dmg` | 32 | 12000 |
  | `trade_lane_ring` | 1059 | 13000 |
  | most stations | ~120 | 15000 |
  | `outpost`, `smallstation1`, the battleships | ~40 | 20000 |

- `LODranges` is in `solararch.ini` only: 255 of its 321 `[Solar]` sections,
  none in `stararch.ini` or `asteroidarch.ini`. All 836 values are ints. The
  values before the last switch detail meshes; **the last is where the object
  stops being drawn**.
- **A floor on the last value, not a multiplier**: `last = max(last, floor)`. The
  shipped spread covers two orders of magnitude, so x3 takes
  `miningbase_badlands` to 9000 (still close) and `space_arch` to 450000 (useless).
  A floor is also idempotent. The earlier values are tuned to apparent size and
  stay. The ceiling is 150000, the largest vanilla value (`space_arch`,
  `space_arch_asteroid`).
- **39 archetypes are held back.** `fuchu_core` (`0, 1`) and `planet_storm_5000`
  (`0, 1, 2, 3, 4, 5`) are placed and meant never to be drawn; the next value up
  in the file is 1000, so `HIDDEN = 100` sits in a clear gap. `suprise_*` is the
  ambush set, 35 `MISSION_SATELLITE` at 1000 and 2 `surprise_*`
  `DESTROYABLE_DEPOT` baits at 1800: drawing them early shows the trap. The 23
  `rm_*` random-mission props are raised: their battleships have a 4000 radius
  and vanish at 15 to 20 km in a stock game.
- **It applies at the next launch**: `EXE/freelancer.ini` reads
  `solar = solar\solararch.ini` once at startup, before the universe. Asteroid
  files (`drawdist`) apply at the next system load.
- Measured at a 40000 floor: 195 of the 216 raisable archetypes moved, only their
  last value; every ladder still ascends; all 836 values are ints; the 39 held
  back are byte for byte unchanged. Set, restore, set through the page put the
  closest station at 3000, then 40000 again.
- **Watch the trade lanes**: 1059 rings go from 13000 to the floor. If the frame
  rate suffers, `TRADELANE_RING` goes on the held-back list first.

### Killing Nomads (`fl.py empathy`, 2026-09-13)

Killing Nomads after the campaign raised nobody's standing. In
`DATA/MISSIONS/empathy.ini` each faction has an `object_destruction` value (what
destroying one of its ships does to your standing with it) and `empathy_rate`
entries spreading that change to everyone else. The Nomad group `fc_n_grp`
carries 54 rates and three are non-zero, all `+1.000`: `fc_ln_grp`, `fc_kn_grp`,
`fc_rn_grp`, the infiltrated navies. With `object_destruction = -0.03`, those
three take the full penalty and **the other 51 move by zero**.

- **A negative rate is approval.** Killing a Liberty Rogue is `-0.018`; Liberty
  Police sit at `-0.250` toward Rogues, so the kill gives
  `-0.018 * -0.250 = +0.0045` Police standing, while the Outcasts at `+0.350`
  lose 0.0063.
- `fc_n_grp` owns `fc_n_no_fighter_d19`, the ordinary Nomad fighter (the story
  spawns `MSN`-prefixed ones), so an open-world kill fires that group's event.
- **The setting is a body count**: `fl.py empathy 400` sets the other 51 so that
  400 Nomad kills take all of them from neutral to friendly at once:

      rate = -(friend - neutral) / kills / |object_destruction|

  The span comes from `reputation.GOALS` (0.5), so it cannot drift from the
  Reputation tab. Plain ship counts, at the owner's request (not wings of four:
  a wing has no fixed size). The first version offered the file's own values,
  `-0.05` to `-0.45`; `-0.25` meant 67 kills, which the owner refused: the grind
  must be weighable against flying missions.
- **Below 100 kills (`SOFT_FLOOR`) it warns and writes anyway**: the owner's
  game. Nothing is refused except a value that is not a number. A sign flip is
  allowed: `-400` is four hundred Nomads from neutral to **hostile**. An earlier
  guard refused anything outside `-1.0..0.0`, which blocked every count under
  ten (two kills ask for `-8.33`).
- The three doubles keep `+1.000`: they are Nomads in a navy's colours, so the
  change reads "everyone who is not a Nomad approves".
- `empathy.ini` has one writer, so rebuilding it from `.vanilla` each time is
  right. It is a data file read at startup and survives a reboot.
- Calibrated on a save where 50 of 55 standings sat at `0.0000` because `m13.ini`
  was zeroed then. With vanilla `m13.ini` (since 2026-09-15) a finished campaign
  leaves Liberty at 0.91 and eight factions at -0.65, so the distance to friendly
  differs per faction. The code needs no change: it takes the span from
  `reputation.GOALS`, not from where the player stands.

### Callsign (`fl.py callsign`, 2026-09-13)

The owner asked for a callsign made of game assets that the bots speak, choosing
every part including the numbers, stored in a file. "Yanagi" and "Susuki" are
formation designators, in the list with Alpha, Beta and Gamma. **No personal name
is recorded**: `faction_prop.ini` has name pools (100 Kusari first names, 300
surnames, Suzuki among them) for the contact list, and across all 1852 distinct
message ids in every voice file `yanagi`, `suzuki`, `adams`, `aaron` return zero.
A callsign is three recorded vocabularies:

    <faction word>    <formation designator>    <number> - <number>
    48 recordings          29 recordings          0 to 20, both halves

All three lists are derived: faction words from the `gcs_refer_faction_*_short`
ids in the voice files, named through `InitialWorld.ini`; designators from the
union of every faction's `formation_desig` range, 197808..197836, 29 values
against 29 recordings `_01` to `_29`; numbers are those of 0 to 20 recorded both
with and without the trailing dash.

The four sites, in `DLLS/BIN/content.dll`, in the function that builds a
callsign:

| Slot | What is there | Patch |
|---|---|---|
| faction | the string `gcs_refer_faction_player`, 24 bytes and 4 NUL of slack | swapped whole |
| designator | the string `gcs_refer_formationdesig_01`, 27 bytes | last two digits |
| **second** number | `6a 01`, a literal `push 1`, feeding `gcs_misc_number_%d-` | one byte |
| **first** number | `(id - 1) % 20 + 1` in eleven bytes | `mov $N,%edx` plus six nops |

- **The dashed-format site is spoken second.** Until 2026-09-13 the labels were
  backwards: the file held 6 at the dashed site and 13 at the plain one, the bots
  said 13-6, `fl.py callsign` printed 6-13. The owner heard it; an argument from
  the disassembly that the tool was right came first and was wrong.
  `FIRST_SITE` and `SECOND_SITE` in `callsign.py` hold the mapping; the sites are
  named by byte shape, `pushed` and `computed`.
- The other arm of the branch does `add $0xfffcfb51,%edx` (-197807) and
  `push $0x70a6540` ("gcs_refer_formationdesig_%02d"), so the designator is
  `ids - 197807`: 197808 is Alpha, 197836 Yanagi. 29 recordings, 29 strings, 29
  values.
- **The branch is "has no formation", not "is the player"**: an NPC flying alone
  takes it too, so the words occasionally turn up on someone else's radio. The
  page says so.
- **Found by disassembly**: `objdump -D -b binary -m i386` over `content.dll` and
  about sixty lines of reading, after byte pattern matching had failed. The
  running process holds no assembled ids: the engine hashes a message id as soon
  as it builds it, as it does nicknames.
- Every site is found by signature (the two code signatures anchor on the address
  of a string itself found by search); `write` refuses unless each matches
  exactly once. Four refusals, each proved: a word with no recording (`fc_n`, the
  Nomads), a nonsense word, a designator above 29, a number above 20.
- `content.dll` reloads with every save load, so a write applies at the next load
  without a relaunch.
- Verified: `.vanilla` byte-identical to the shipped file and unchanged by three
  later writes; four changed runs, 20 bytes; PE headers and all five sections
  identical; code patches in section 0, strings in section 1; set B over set A
  equals set B over vanilla; the patch disassembles to `mov $0x6,%edx` plus six
  nops ending exactly at the following `push %edx`, and nothing jumps into the
  eleven replaced bytes. Confirmed by ear on 2026-09-13.
- The picker is a box in the Engine tab's GAME FILES half.

### New game: an RTC is not a cutscene (tried 2026-09-06, reverted)

Trimming the first mission broke the game twice. `newgame.py` writes the starting
ship and nothing else; its `.vanilla` copies cover only `loadouts.ini` and
`m01a.ini`.

- **`Act_AddRTC` populates a room.** Its file is a `[CharacterEncounter]`: a
  `Location`, one `action` scene, `[Char]` entries. `m001a_s003x` puts the
  bartender, Juni and the Liberty diplomat in the Manhattan bar; `m001a_s004x`
  Juni and the diplomat; `m000_s002xe` the wounded Lonnigan on the cityscape.
  Removing it empties the room: no Juni, no `Cnd_CharSelect`, no job, no
  `Act_SetShipAndLoadout`, no ship. `autoplay` (on 61 of 68 character encounters)
  is the real switch: with it the scene runs on entering, without it on clicking
  the character (`s004x` is this mission's one example). Dropping that key was written but never tested: the owner
  stopped the work first.
- **`tr_fp7_cam_end` is not a wait.** The Freeport 7 opening is a chain of timers
  on the 33 triggers scoped to `FP7_system`; this one starts with the first
  trigger, runs beside the chain and ends it with `Act_ForceLand` on Manhattan.
  Its 68.5 s is the sequence length. Capping every timer to 1 s force-landed the
  player one second in while the chain kept spawning ships in a system being torn
  down: the crash. Vanilla runs a 42.8 s chain under a 68.5 s marker (x1.60), so
  a compressed chain needs the marker recomputed, not capped.

### Hand changes to the install

A value that looks wrong may be deliberate. Tool writes have a `.vanilla`
beside them; this list covers the rest.

- **`DATA/EQUIPMENT/select_equip.ini` is vanilla again since 2026-09-06.** On
  2026-09-04 `[TradeLane] basic_trade_lane_eq` had `activation_start` cut from 750
  to 100 and `activation_end` from 500 to 50, to hold cruise until the ring. It
  did nothing: those keys are the ring's spin-up window and never reach the
  ship's engine state. Restored from `.vanilla`, 15 `[TradeLane]` keys checked.
  Docking is `dockdist.py --takeover`; this file now only matters for ring spin-up
  (`spin_accel`, `secs_before_enter` sit beside it).
- **`DATA/MISSIONS/M13/m13.ini` is vanilla again since 2026-09-15**, the owner's
  call: neutral with everyone after the campaign was boring. Its `[Trigger]`
  `enter_bar` fires on walking into the bar at the end of M13 and hard-sets 47
  reputations: Liberty Navy and LSF 0.91, seven factions 0.65, twelve -0.3, eight
  -0.65, seventeen already 0. It had been zeroed on 2026-09-02 and 2026-09-09. The
  zeroed version is kept as `m13.ini.neutral`: the first zeroing vanished without
  trace (mtime 21:31 on 09-02 against a `.vanilla` from 09-01), and there is no
  module for it. Switching is a copy through `persist.write_raw`. Re-making it:
  decode, zero every numeric third field of `Act_SetRep` in that one trigger,
  re-encode through `persist._save`, which refuses unless the round trip is
  identical; the `Act_SetRep` entries in other triggers are symbols like
  `REP_FRIEND_THRESHOLD`. **If end-of-campaign reputations look wrong, first
  check which of `m13.ini`, `.vanilla`, `.neutral` is in place.**
- Non-vanilla values written by the tool: `CRUISING_SPEED` 5000.0 in
  `constants.ini` (the Engine tab's persist button), a scaled `fill_dist` in 153
  asteroid field files (`drawdist.py`), a 40000 cull floor in `solararch.ini`
  (`solardist.py`), levels to 50 in `ptough.ini`, plus whatever `routetable`,
  `callsign` and `empathy` were last set to.

## The page

### Look: `design/Neural Companion.dc.html` is the source

A Claude Design canvas drawn by the owner (2026-09-07): dark HUD, Chakra Petch
over IBM Plex Mono, cyan for the instrument, amber for anything that touches a
file. Overview and Systems are drawn in full; Equipment, Trade, Reputation and
Neural Net as markup; Chart is not covered and uses the same panel, border and
label vocabulary. Read it before changing how anything looks.

- Its values live in `frontend/_theme.css` as tokens and nowhere else.
- The canvas emits inline styles; the page uses classes. Do not port a
  `style="..."`. A tab's own selectors live in its module, not in the theme: both
  grid-column bugs shipped so far were a row template and its column list
  drifting apart in two files.
- Three deliberate departures, because every engine control writes into a live
  game: a slider posts on release, a redraw waits while a slider is under a
  thumb, and the two expensive readings behind `ALL KNOBS` are fetched only when
  it is open. `frontend/engine.py` says so at the top.
- The canvas draws the engine controls as a strip on every page. That was built
  and reverted on 2026-09-07: it polled process memory every five seconds from
  every tab, and was rebuilt on every tick, which swallowed clicks (below). A tab
  polls only while open, and each setting shows in one place.
- `check_views.py` skips grids marked `wrapgrid`, the ones meant to wrap
  (Overview's panel flow and its label/value list). The computed style cannot
  tell them apart: `repeat(auto-fit, ...)` resolves to concrete tracks.

### One inline script: a parse error kills the whole page

The UI is one `<script>` in `PAGE`, so a syntax error leaves static HTML, a stuck
"loading…" and no tabs, while curl gets 200 and the API answers. 2026-09-04:
`let top = 'map'`; `window.top` is non-configurable, so a global `let` or `const`
on that name is a SyntaxError (also `window`, `self`, `location`, `document`).
The variable is `topTab`.

- **Verify in a browser.** `firefox --headless --screenshot` shows whether the tab
  strip drew. The shot fires at the load event, before the first `fetch`
  resolves, so an empty body proves nothing.
- `check_views.py` checks `$` and `VIEW` before anything else and says so in
  words; the seeding runs in its own try. On 2026-09-07 an unclosed template
  literal in `frontend/log.py` killed the script, the driver's
  `Object.keys(VIEW)` threw, and the report came out blank.

### The poll compares, never rebuilds

`render()` runs on a five-second poll. It used to assign `innerHTML` every tick
though the markup was byte-identical (1389 characters for the engine strip).
That destroys every child, and a browser fires `click` only when press and
release land on the same element, so a click straddling a tick did nothing,
silently, on every button of every tab. Proved headless: press, one `render()`,
release, and `#engmore` is a different object. (Reported 2026-09-07: `ALL KNOBS`
"opened once and then stopped opening".)

- **`paint(node, html)` in `frontend/shell.py` writes only when the html changed.
  It is not an optimisation; never remove it as one.** Handlers survive because
  their elements do; focus, selection and scroll survive too.
- **`paint` compares with the last string it wrote**, kept in a `WeakMap` keyed
  on the node, never with `node.innerHTML`, which returns the browser's own
  serialisation: `selected` comes back as `selected=""`, `hidden` as
  `hidden=""`, a U+00A0 as `&nbsp;`. Comparing with `innerHTML` left four of the
  nine views (`search`, `rep`, `systems`, `log`) rebuilt on every tick for three
  days, closing open `<select>`s and dropping focus and half-typed text (reported
  2026-09-10). Do not try to fix this by writing markup the browser echoes back.
- Anything that empties a painted node by hand goes through `clear(node)`, or the
  next real write is skipped. `check_views.py` is the one caller.
- `check_views.py` measures the invariant by identity: render a view twice with
  the same data, and no node may be replaced. With the old comparison put back it
  printed 12 `POLL` lines naming `systems`, `search`, `rep` and the two log views
  with rumors.

### Marks live on the server

On 2026-09-09 the owner's read marks vanished overnight. `localStorage` is scoped
to a browsing context: the marks were made in a Zen workspace container
(`userContextId=1`, 75 marks), the next day's tab was plain (`userContextId=0`,
20 marks). Every key regenerated identically; there were two stores. `run.sh`
ended in `xdg-open`, which always opens a plain tab.

- Marks live in `data/marks.json`, written through a temp file and
  `os.replace` under one lock (`serve.py` is threaded). A missing or unreadable
  file reads as no marks.
- **`merge_marks` unions and never deletes**, so any old browser store can still
  contribute.
- **The page is a cache.** A toggle applies locally, then posts; a `marksHeld`
  timestamp stops the poll returning a payload older than the write (the same
  guard as the slider under a thumb). The Equipment tab registers no poll and
  needs no guard; the code says so.
- `localStorage` is not cleared: it is the fallback if the file is lost.
- Favourite guns live in the same file under `fav`, keyed by the bare item
  nickname, unique across guns and shields (314 rows, 314 nicknames).

### The header names the save

`api/state` carries `save_path` and `save_dir`; the save name in the header is a
button that shows the folder and hands it to the file manager (2026-09-12). The
save sits six levels down a Wine prefix, in one of several accounts, picked by
mtime at startup:

    ~/Games/freelancer-win32/drive_c/users/<account>/Documents/My Games/
    Freelancer/Accts/SinglePlayer/AutoSave.fl

- **`api/reveal` takes no argument**: it opens only the folder this process chose.
  An endpoint opening a path the browser sends would open arbitrary folders on
  request.
- The opener is spawned and never awaited, so "opened" means asked; a stuck
  handler cannot hang the POST. The path is printed beside the answer.
  `xdg-open`, `os.startfile` and `open` live in one function in `common.py`.

### Layout: size from the box, not the window

Systems lays a house out two cards abreast. `@media (min-width: 1400px)` never
fired for the owner: a browser sidebar takes about 600px, so the page sat near
1396 CSS px. Now (2026-09-10):

    grid-template-columns: repeat(auto-fit, minmax(max(34rem, 48%), 1fr));

`48%` caps it at two; `34rem` is the floor below which it drops to one column.
Measured: one column at 900 and 1100, two from about 1130px of page width (two at
1256, 1396, 1500 and 1920), never three. A media query measures the window, and `.wrap` (capped at 1680), the
sidebar and the panel all sit between the window and the box. `.totals` and
`.hits` already work this way.

### Equipment tab

- **"Only bases I have docked at" drops rows** (2026-09-10, reversing the earlier
  design, which kept every row with an empty dealer list). The owner called that
  useless: it left 187 of 235 guns on screen with nothing under them. Against a
  save with 30 docked bases: guns 235 -> 51, shields 79 -> 36. It is a filter kind
  inside `eqp.search`; `search.py` then narrows each surviving row's `bases` to
  docked dealers and can no longer empty a row.
- **A favourite bypasses every filter.** `eqp.search` takes `keep`, checked
  before the filters and carried through the same sort, so a favourite sits in
  the ranking, not on top of it. Starring the weakest gun and asking for
  `hull_dps >= 100` returns 226 rows instead of 225, that gun last.
- **Every column shows; a `×` on a heading drops one.** All on, guns need 1335px
  and shields 1244px; below about 1350px the table scrolls inside its `.guns` box.
  A dropped column brings up a `+ add a column…` select beside
  `+ add a parameter…`. `gearHidden` holds the exceptions, so a parameter added
  later appears without being named. A column you sort or filter on carries no
  `×`. Dropping and restoring ask the server nothing; cells stay in step with the
  grid at 12, 9 and 10 columns. `price` has its own column and is not a
  parameter column.
- **Rank needed is a comparison**: `rank` is `cmp` in `PARAMETERS`, drawing the
  `[= <= >=]` select the mount class uses. Other numeric parameters stay a plain
  minimum. Both comparisons are inclusive; `>=` on a number is `num`, which every
  numeric filter sends, so there is no `over` kind; `<=` is `upto`. `le` and `ge` compare mount classes
  and refuse across socket families (a shield's `fighter 6` and `elite 6` differ);
  they are not the numeric pair.

  | | `=` | `<=` | `>=` |
  |---|---|---|---|
  | rank 16, guns | 51 | 160 (109 + 51) | 126 (75 + 51) |
  | mount 6, guns | 51 | 145 (94 + 51) | 141 (90 + 51) |
  | mount `fighter 6`, shields | 3 | 18 | 11 |

  The shield rows are all `fighter`, none `elite` or `freighter`: the family
  rule holding. 126 is what `num 16` gave before, so `>=` is that filter, not a
  copy of it.

## Starting the server

`serve.py` binds the port before it loads anything; if the port is taken it names
the port, prints the command that frees it and exits 1. `run.sh` is three lines
around `serve.py --open`; `run.cmd` is the same for Windows.

On 2026-09-12 the old `run.sh` started a second server, which died on `bind`
while its wait loop connected to the old one on the first try and opened a
browser on an hour-old server: the new tab seemed missing. A script probe
(`/dev/tcp`) only guesses whether the server bound; `serve.py` knows.

- `exec` with only redirections applies them to the rest of the script:
  `exec 3<&- 2>/dev/null` silenced every later message
  (`bash -c 'exec 3<&- 2>/dev/null; echo hi >&2'` prints nothing).
- **`allow_reuse_address` differs by platform.** `HTTPServer` sets it. On Linux
  it binds over a socket in TIME_WAIT, so a restart after Ctrl+C works. On Windows
  `SO_REUSEADDR` lets a second program bind a port another is listening on. So
  `serve.py` keeps the flag on Linux and turns it off on Windows.

## Windows: one codebase, the Windows half unproven

Asked for on 2026-09-12; the owner's test plan: write it and mark it. **There is
no Windows fork and must never be one.** Three things differ, each picked at
import from `sys.platform`:

| What | Linux | Windows |
|---|---|---|
| where the game is | the Wine prefix under `~/Games` | `AppPath` from the registry, `Program Files (x86)` as fallback |
| where the saves are | every Wine prefix beside the game | the `Personal` shell folder, because OneDrive moves Documents |
| process memory | `/proc/<pid>/{maps,mem}` | `ReadProcessMemory` and friends |

The rest (save decoder, BINI reader, PE string tables, DPS model, jump graph, job
boards, the page) is plain Python on `os.path`.

**`backend/live/proc.py` is the only code that touches another process.** It
replaced 22 direct `/proc/<pid>/mem` openings across `speed.py`, `inject.py`,
`tradelane.py` and `thrusters.py` with six functions: `find_pid`, `mappings`,
`regions`, `read`, `write`, `chunks`. `mappings` yields `(lo, hi, perms, name)`
with `perms` spelled `rwxp` on both platforms. Proved on the running game: every
`fl.py` live command gave byte-identical output before and after, and each write
path was run with the value already there (`fl.py speed 300`, a thruster set to
its own speed, a POST to `api/allhacks`).

Never run. Three traps return wrong answers instead of errors, so the code is
built around them:

- **Toolhelp cannot list a 32-bit process's modules from 64-bit Python**
  (`TH32CS_SNAPMODULE32` fails with `ERROR_PARTIAL_COPY` across WOW64). Modules
  come from `EnumProcessModulesEx` with `LIST_MODULES_ALL`; Toolhelp still lists
  processes.
- **`MEMORY_BASIC_INFORMATION` is laid out for the caller**: pointer fields
  `c_void_p`, `RegionSize` `c_size_t`.
- **Every function gets `argtypes`**, or ctypes passes a `HANDLE` as a C `int` and
  truncates it on 64-bit.

Windows `write` needs `VirtualProtectEx`: lift protection, write, restore, flush
the instruction cache (or the CPU runs the old byte for a while). This does not
change `find_scratch`: the game's own write into a read-only page still faults.

`check_windows.py` puts Windows-sized types into `ctypes.wintypes`, fakes
`WinDLL`, imports `proc_windows.py` and measures every name, struct size and
offset against the documented numbers, and that every function has `argtypes`
and `restype`. On Linux `wintypes.DWORD` is 8 bytes (4 on Windows) and `c_wchar`
4 (2), so imported as-is `MEMORY_BASIC_INFORMATION` measures 56 bytes instead of
48; `WCHAR` is measured with a two-byte stand-in. It caught `pcPriClassBase` declared `c_long`: `PROCESSENTRY32W` came out 1096
bytes instead of 568. Whether the calls work only Windows can say: `fl.py proc`
asks (pid, modules, sixteen bytes of `common.dll`, nothing written).

## Dependency

`bini.py` lives in `../scripts/`, shared with the rest of this area. Its path is
derived from `backend/__init__.py`'s own location, two levels up, and that file
checks `bini.py` exists and says where it looked; without the check a checkout
without the vault beside it fails with `No module named 'bini'` and no path.
