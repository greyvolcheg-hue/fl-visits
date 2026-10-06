---
type: research
project: computer-geek
status: done
created: 2026-10-06
---

# Saves

## `flvisits.py` edits

The file was frozen in August and unfrozen on 2026-09-07 at the owner's request:
three thaws in five weeks, each correct, each a round trip. The check made them
safe, not the freeze. Each edit, with what `check_frozen.py` showed:

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

## What the reader was verified against

- All 301 hashes in a live save resolved to a nickname in the game data. The same
  brute force without lowercasing the nickname scores 40 of 301, so the match is
  not coincidence.
- The flag model held across a play session: a base moved from "revealed" (1) to
  "docked" (30/31) while the player flew.

## Visit flags

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

## Story state: `[StoryInfo] MissionNum`

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

## The log

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
