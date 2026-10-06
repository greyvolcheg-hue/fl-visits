---
type: research
project: computer-geek
status: done
created: 2026-10-06
---

# Changing the game: files

Every writer here follows the writer rule in `CLAUDE.md`. Both writers in
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

## Levels (`fl.py levels`, 2026-09-12)

The `levels.py` docstring holds the table (`DATA/MISSIONS/ptough.ini`,
`[PlayerToughnessScale]`, 39 rows up to `2409599, 38`), the proof against the
live game, why `[Player] rank` in a save is only a cache, and the two unknowns
(whether the game reads more than 39 rows, what else the curve drives). Not
there:

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
- The ladder rises about x1.14 a rung over its top ten. `fl.py levels` builds
  from the vanilla rows every time; the first added rung continues x1.14, so
  there is no seam at the old cap, and the rest are a geometric run landing
  exactly on the requested worth. It refuses a value past int32 (it would wrap
  negative) and a ladder that does not strictly rise (a level you could never
  leave).
- Applied 2026-09-12: levels 39 to 50, 2,746,943 to 1,160,922,100, step x1.733.

## Draw distance (`solardist.py`, 2026-09-15)

The `solardist.py` docstring holds where `LODranges` lives, why the tool sets a
floor on the last value instead of a multiplier, the 150000 ceiling, the hidden
and ambush archetypes, and why the change applies at the next launch. Not there:

- **Scope**: the tracker asked to see every base, gate, planet and jump hole. Of
  the game's three levers the owner picked `LODranges`; map reveal and scanner
  range are out of scope.
- **Shipped culls of the stations**:

  | archetype | placed | shipped cull |
  |---|---|---|
  | `miningbase_badlands`, `miningbase_nomad` | 3 | 3000 |
  | `docking_fixture`, the mooring you dock at on a planet | 21 | 6000 |
  | six `miningbase_*` | 15 | 7000 |
  | `roid_miner2`, `space_port_dmg` | 32 | 12000 |
  | `trade_lane_ring` | 1059 | 13000 |
  | most stations | ~120 | 15000 |
  | `outpost`, `smallstation1`, the battleships | ~40 | 20000 |

- 39 of the 255 archetypes with `LODranges` are held back (2 hidden, 37 ambush).
- Measured at a 40000 floor: 195 of the 216 raisable archetypes moved, only their
  last value; every ladder still ascends; all 836 values are ints; the 39 held
  back are byte for byte unchanged. Set, restore, set through the page put the
  closest station at 3000, then 40000 again.
- **Watch the trade lanes**: 1059 rings go from 13000 to the floor. If the frame
  rate suffers, `TRADELANE_RING` goes on the held-back list first.

## Killing Nomads (`fl.py empathy`, 2026-09-13)

The `empathy.py` docstring describes the first version (a rate argument,
`fl.py empathy -0.25`) and is stale; `rate_for`, `kills_for` and this section
are current.

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

## Callsign (`fl.py callsign`, 2026-09-13)

The `callsign.py` docstring holds the three recorded vocabularies (faction word,
formation designator, two numbers), why no personal name can be spoken, the four
sites, the corrected order of the two numbers, the designator arithmetic, and
why the words also reach NPCs flying alone. Not there:

- **The four sites in byte detail**, in `DLLS/BIN/content.dll`:

  | Slot | What is there | Patch |
  |---|---|---|
  | faction | the string `gcs_refer_faction_player`, 24 bytes and 4 NUL of slack | swapped whole |
  | designator | the string `gcs_refer_formationdesig_01`, 27 bytes | last two digits |
  | **second** number | `6a 01`, a literal `push 1`, feeding `gcs_misc_number_%d-` | one byte |
  | **first** number | `(id - 1) % 20 + 1` in eleven bytes | `mov $N,%edx` plus six nops |

- **The lists are derived, never typed**: faction words from the
  `gcs_refer_faction_*_short` ids in the voice files, named through
  `InitialWorld.ini`; designators from the union of every faction's
  `formation_desig` range, 197808..197836; numbers are those of 0 to 20 recorded
  both with and without the trailing dash.
- `FIRST_SITE` and `SECOND_SITE` hold the order mapping; the sites are named by
  byte shape, `pushed` and `computed`, so nothing claims an order it cannot
  check. When the owner reported the order as swapped, an argument from the
  disassembly that the tool was right came first and was wrong: the source of
  the first working rule in `CLAUDE.md`.
- **Found by disassembly**: `objdump -D -b binary -m i386` over `content.dll` and
  about sixty lines of reading, after byte pattern matching had failed. The
  running process holds no assembled ids: the engine hashes a message id as soon
  as it builds it, as it does nicknames.
- Every site is found by signature (the two code signatures anchor on the address
  of a string itself found by search); `write` refuses unless each matches
  exactly once. Four refusals, each proved: a word with no recording (`fc_n`, the
  Nomads), a nonsense word, a designator above 29, a number above 20.
- Verified: `.vanilla` byte-identical to the shipped file and unchanged by three
  later writes; four changed runs, 20 bytes; PE headers and all five sections
  identical; code patches in section 0, strings in section 1; set B over set A
  equals set B over vanilla; the patch disassembles to `mov $0x6,%edx` plus six
  nops ending exactly at the following `push %edx`, and nothing jumps into the
  eleven replaced bytes. Confirmed by ear on 2026-09-13.
- The picker is a box in the Engine tab's GAME FILES half.

## New game: an RTC is not a cutscene (tried 2026-09-06, reverted)

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

## Hand changes to the install

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
