---
type: research
project: computer-geek
status: done
created: 2026-10-06
---

# Factions, news, rumors, commodities

## A faction with nobody in any bar is out of the Reputation tab

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

## Reputation model: open questions (2026-10-06)

- **Mission abortion.** `reputation.py` spreads all four events through
  `empathy_rate`, so aborting a mission for an enemy of your target raises your
  standing with the target. `trade.py` cites a measurement of 2026-09-15 that
  `random_mission_abortion` reaches only the giver; the measurement was never
  written down and the owner does not remember it. Until re-measured, the abort
  rows on the Reputation tab may be wrong. To settle it: note all 55 standings,
  abort one mission, save, compare.
- **The bound.** `reputation.py` says standings stay within ±0.9, "established
  from the saves". Across 224 saves they use the full ±1.0 and 172 sit above 0.9
  (`patching-memory.md`). Whether 0.9 is a deliberate planning margin or a wrong
  reading is open.

## News

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

## Bar rumors

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

## Three commodities spoil

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

## Systems are identified by nickname

Display names repeat: Omicron Beta is `Ew02` and `St02`; Omicron Major is
`St03`, `St03b`, `St02c` and `FP7_system`; Unknown is `Ew05` and `Ew06`. Only one
of each group has a market, so keying the trade selectors on labels works today
by luck. `market.py` rows carry `sys_nick`, the identity, and `system`, the
printed label.

# Equipment

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

# Job boards

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

# Bribes

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
