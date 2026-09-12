# fl-visits

Reads a Freelancer save game and reports what the player has found, grouped by
system. Own git repo; the history in this folder is the undo button.

## Where things live

Three folders, one per layer, settled 2026-09-07 to the owner's own spec in
`bug-and-feature-tracker.md`. **The folder a file sits in says what it may do**,
and that is the whole point of the split:

| Folder | Holds | May |
|---|---|---|
| `data/` | files the app ships or is given | nothing; it is data |
| `backend/` | one `<tab>.py` per tab, plus `common.py` | read the game, answer an endpoint |
| `backend/game/` | readers of the game's own formats | read files. No HTTP, no state |
| `backend/live/` | the patchers | **write**: process memory, or a game file with a `.vanilla` beside it |
| `frontend/` | one `<tab>.py` per tab, plus the shell | style and behaviour, nothing else |

`tabs.py` at the root is the site map and the only place the shape of the page
can be read at once. It is neither backend nor frontend because the shape is
neither. `fl.py` is the one entry point for every command line.

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
| `backend/game/infocards.py` | the RT_HTML half of the resource DLLs, which is where rumor text lives |
| `backend/game/jobs.py` | what the job board at every base is capable of paying |
| `backend/game/jumps.py` | every jump between systems, and the shortest way through them |
| `data/story-states.txt` | the 42 story states in order. `MissionNum` in a save indexes this |
| `data/marks.json` | which log entries are starred and read. **Untracked**: personal state |
| `backend/live/proc.py` | the only code that touches another process. Picks its implementation at import |
| `backend/live/proc_linux.py` | `/proc/<pid>/{maps,mem}` |
| `backend/live/proc_windows.py` | `ReadProcessMemory` and friends. **Never run** |
| `backend/live/speed.py` | cruise speed of the *running* game |
| `backend/live/thrusters.py` | the same for the six thruster bonuses |
| `backend/live/tradelane.py` | trade lane speed and the 999 cap on the HUD readout |
| `backend/live/dockdist.py` | when the autopilot cruises to a dock, and where it takes over |
| `backend/live/bestpath.py` | let Set Best Path route through jump holes |
| `backend/live/inject.py` | the code cave, and how a stub gets into it |
| `backend/live/persist.py` | writes the live speeds back into the game's files |
| `backend/live/routetable.py` | writes the shortest routes into the game's own route tables |
| `backend/live/drawdist.py` | scales asteroid `fill_dist` across the 153 field files |
| `backend/live/newgame.py` | what a new game starts you in |
| `data/freelancer-map.jpg` | the sector chart, served at `/map.jpg`. **Untracked**: fan-made and not ours to redistribute. Drop your own copy in. |
| `design/` | the visual design, as a Claude Design canvas. The source the page is built from, not a screenshot of it. |
| `run.sh` | start the server and open a browser on it |
| `run.cmd` | the same three lines for Windows. **Never run** |

**A tab is a pair of files with the same name**, `backend/<name>.py` and
`frontend/<name>.py`, and either half may be absent: a tab that only draws what
`/api/state` already carries has no endpoints of its own. Adding one is a row in
`tabs.py` plus the file or two it names.

**Modules under `backend/` have no `if __name__ == "__main__"` block.** Inside a
package a relative import has no parent, so `python3 backend/live/dockdist.py`
cannot work and an entry point that cannot run is worse than none. Every one of
them still has its `main()`, reached through `fl.py`.

Everything new goes in its own file. `flvisits.py` supplies the primitives;
`wrecks.py` adds its own INI reader because loadouts repeat their `equip` and
`cargo` keys and the one in `flvisits.py` collapses repeats.

## `flvisits.py` is no longer frozen. `check_frozen.py` is the guard instead.

**Unfrozen 2026-09-07, permanently, at the owner's request.** The freeze was
the right call in August and the ceremony around it had stopped paying: three
thaws in five weeks, each one obviously correct, each one costing a round trip.
What made every one of those safe was never the rule. It was the check.

The reason for the caution has not changed, so read this before editing:

It unpicks three undocumented formats in a row. FLS1 save encryption, BINI
binary INI, and PE resource tables in the DLLs. On top of that it resolves a
**one-way** hash by brute force, hashing every nickname in the game data and
looking the result up, because the mapping cannot be inverted.

None of that is re-derivable by reading the code. The constants were found by
searching, then confirmed empirically against real saves, and several plausible
alternatives were tried and scored zero. A tidy-looking edit can therefore break
it silently: the script will still run, still print a report, and the report
will be wrong. That is the worst failure mode there is, because it looks like
success.

**So the rule is now one line: run `check_frozen.py` before and after, and diff.**
Not "read the diff and think about it". The one save that legitimately moves is
`AutoSave.fl`, because the game rewrites it while you play; everything else must
be identical byte for byte. If you cannot produce that diff, do not commit the
edit.

Everything below is the record of what was changed and why. Keep adding to it.

**Thawed once, 2026-08-31, with the owner's explicit go.** The denominator
counted all 197 `[Base]` entries in `universe.ini`, including 15 that no space
object points at. Three of those are intro-cutscene copies of Manhattan sharing
one `strid_name`, so the report printed "Planet Manhattan" three times as
unvisited. Left alone the two programs here would have disagreed with each
other on the same data, 197 against 182, which reads as a bug in whichever one
you check second. The freeze stands; this is the precedent for what clears it,
not for how easily it clears.

**Thawed a second time, 2026-09-01, with the owner's explicit go.** The
Asteroid Miners turned out to be undockable (see below), which changes the
denominator, and the denominator filter sat in both `flvisits.py` and
`serve.py`. Editing only one would have left them disagreeing, 167 against 181,
the same failure the first thaw was for.

The edit was kept to the smallest shape that removes the duplicate instead of
adding a third copy of it: the rule moved to `bases.py` and both callers now
ask that. Eight lines changed in the frozen file, all of them in `main()`, none
in the decoding, the hash or the loaders.

Checked afterwards, against the same save, with the committed version of the
file and the thawed one side by side: 3430 object nicknames, 2188 visit
entries, **486 resolved by both**. Identical. That is the check that matters
here, because it is the one that would have gone quietly wrong.

**Thawed a third time, 2026-09-06, with the owner's explicit go**, to run the
file through the same cleanup as the rest of the repo. Two changes, both in
what the file says rather than what it computes:

- **`ipath` was defined twice**, at lines 47 and 121, and the second shadowed
  the first. Nineteen lines of dead code carrying a docstring that described
  behaviour nothing ran. That is worse than clutter in a file people are told
  not to touch: whoever read the first definition was reading a lie about how
  paths resolve. The live one absorbed the useful half of the dead one's
  docstring.
- A comment in `main()` said 167 dockable and 30 dropped. The real figures are
  164 and 33, stale since the story-locked three were excluded.

**Edited twice on 2026-09-07, after the freeze was lifted**, both times so that
the bar rumors could be read at all:

- `read_string_table(path)` became `read_string_table(path, rtype=RT_STRING)`.
  Rumor text is RT_HTML (type 23) and names are RT_STRING (type 6); the PE
  resource walk is identical and only the type constant and the indexing differ.
  The alternative was a second copy of that walk in `infocards.py`.
- `resource_dlls()` came out of `load_names()`. `infocards.py` reads the same
  seven DLLs in the same order, and a second copy of that loop would have been
  a second answer to "which DLL is index 2".

`check_frozen.py` identical on both, across all 123 stable lines.

**`check_frozen.py` is what made every one of these safe.**
It fingerprints everything the module decides, across every save on disk, and
prints it in a stable order: the hash table, the string tables, the system
walk, the dockable set, and each save's resolved visits with their flags. Run
it before, run it after, diff. On the 2026-08-31 thaw that was **96 saves,
219,634 visit entries, 7,372 resolved, and every digest identical**.

Use it rather than reasoning about whether an edit was safe. This file's
failure mode is a report that is wrong while looking right, and no amount of
reading catches that.

## What it was verified against

- Every one of the 301 hashes in a live save resolved to a nickname in the game
  data. Zero unresolved.
- The same brute force without lowercasing the nickname scores 40 of 301, so the
  match is not coincidence.
- The flag model held across a play session: flag 1 means the story revealed the
  base on the nav map, flags 30 and 31 mean the player actually docked. A base
  moved from the first bucket to the second while the player was flying, exactly
  as the model predicts.
- Denominator starts from the `[Base]` list in `universe.ini` (197), not the
  count of dockable space objects (250). A planet's mooring fixture is a second
  object pointing at the same base, so counting objects double counts every
  planet. 197 then narrows to 181 reachable and 164 dockable; `bases.py` owns
  that and says why. 164 instead of 167 because Tohoku's two and Alaska's one
  are excluded by name: both systems are story-gated and nothing in the data
  says so. That rests on the owner's knowledge of the game and on no evidence.
  An earlier note here cited the saves, which was wrong: Tohoku is M09 and
  Alaska is M11, the save is on Mission_05, so their absence means only that
  he has not reached them. `bases.py` carries the correction.

## Known gaps, deliberately not fixed

- 19 `visit` entries carry small ids from a different id space and flag 65.
  `FLHash` does not cover them. They are not bases and do not affect the report.
- `AutoSave.fl` changes under your hands while the game is running. Test against
  a fixed `Save*.fl`, or you will chase differences that are just play.
- **Adv. Dissolver and Adv. Sunrail are stocked by exactly one base and that
  base is Battleship Essex in Leeds (`br05_04_base`), which `dockable_bases`
  says you cannot land on.** Found 2026-09-12 while adding the loot source.
  Either the docking rule is wrong about Essex or those two guns, at 24790
  credits and rank 22, are genuinely unbuyable in a normal game. The Equipment
  tab says which rather than guessing: their row reads "stocked by 1 base you
  cannot dock at". Resolving it means reopening the rule in `bases.py`, which
  is the owner's call and is not this change.

## What the `visit` flags mean

Read them as bits. Bit 1 is "seen, it is on the nav map" and bit 16 is "this is
a secret", so a recorded wreck reads 17. Bases read 30 or 31 once docked at, and
1 when the story has only revealed them.

**Bit 8 means the wreck has been emptied.** Settled 2026-09-01, replacing the
note that called it not understood. A wreck found but not looted reads 17, and
the same wreck reads 25 once the loot is taken.

The save that settled it held five found wrecks: four at 25 and exactly one at
17, the Storm in Dublin (D6). The owner confirmed independently that the Storm
is the one he had found and deliberately not emptied, and that he was leaving it
alone. One save cannot distinguish "not looted" from "some other property of
that particular hull", so the second leg is the old reading this note used to
carry: New York's three Patrol 27 hulls were 25, 17, 17 and are now 25, 25, 25.
Two of them changed while the player flew, which a fixed property of the object
cannot do and being emptied is exactly what does.

**The transition was never caught in a file.** All 20 saves on disk already hold
their final flags, so the 25/17/17 reading survives only as the earlier entry in
this document and is no longer re-checkable. If you want it on disk, note a
wreck's flag, empty it, and keep that pair of saves.

**An empty wreck counts as emptied the moment it is found.** 54 of the 157
carry nothing at all, which is the game's own design and not a gap in the
reader: the owner confirmed Sigma-13 alone is full of them. The game never sets
bit 8 on those, because there was never anything to take, so they sat in the
report as found-but-still-loaded forever and the stripped count could not reach
157 however thoroughly they were searched. There is no second visit that would
ever change one, so finding it is emptying it.

Do not chase this as a loot-parsing bug. It was, briefly, on the theory that
`load_item_names` was dropping items with no display name; the first wreck
checked turned out to hold eight kinds of cargo and parse correctly. The empty
ones are simply empty.

**The report shows it, and progress deliberately does not count it.** Found is
found: a wreck counts once for the totals and the percentage whether or not it
was emptied, because reaching it is the discovery. The bit only changes how the
line is drawn, `*` and amber for one still holding its loot against `+` and
green for one already stripped, plus a "still loaded" tally. That way the number
you are trying to drive to 157 never moves backwards, while the list still tells
you where there is something left to collect. An untouched wreck also shows its
loot without the checkbox, since that is cargo you can still go and get.

## Settled: the Asteroid Miners are not dockable, and the rule is in the data

Closed 2026-09-01 by screenshot, at 100 m from the Asteroid Miner in Omega-7
with the target selected and no dock prompt. The guess in the previous version
of this section, run-time reputation gating invisible in the files, was wrong:
the reason is in the data and the denominator is now 167 instead of 181.

The rule, and the three candidates that had to be eliminated to find it, are in
`bases.py`. It is not restated here, and it is not duplicated in `flvisits.py`
or `serve.py`: both call it. Those two held their own copies of the old
"reachable" filter and that is exactly how they drifted apart in August.

## Settled: Ithaca Research Station is not reachable

It showed up as an unvisited base in New York. It is not one. Its space object
`Li01_05` is defined in `UNIVERSE/SYSTEMS/INTRO/intro.ini`, and `universe.ini`
does not list `INTRO` among its 53 systems. It exists for the opening cutscene
only.

The cause was structural: objects were gathered by walking the `SYSTEMS/`
directory and taking the system from the folder name, so a cutscene file was
read as if it were a system. The fix is to follow the `file` key that
`universe.ini` gives for each declared system instead, which excludes stray
files by construction.

## Settled: the reader's marks belong to the server, not to the browser

Closed 2026-09-09, after the owner marked news and rumours read one day and
found them gone the next.

**Nothing was corrupted and no key had changed.** Every one of the 17 rumor
ids and every news key regenerated byte-identically the following day. There
were simply two stores. `localStorage` is scoped to a **browsing context**, and
the marks had been made in a Zen workspace, which is a container
(`userContextId=1`, 75 marks), while the tab open the next day was a plain one
(`userContextId=0`, 20 marks). Save looked fine only because its 16 marks were
a strict subset of the other store's 49; it had lost 33.

**`run.sh` is what moved the tab**, and it will do it again: it ends in an
unconditional `xdg-open`, which always opens a plain tab and never a container
one, so every server restart spawns a tab in the default context.

So the old comment was right about who owns the marks and wrong about where the
machine keeps them. They live in `data/marks.json` now, written through a temp
file in the same directory and `os.replace`, under one lock because `serve.py`
is threaded. A missing or unreadable file reads as no marks: a corrupt file
should cost the marks, not the tab.

Two rules that fall out of it and are worth keeping:

- **`merge_marks` unions and can never delete.** That is what makes it safe to
  run against a browser store nobody has seen before, and it is why every
  context that ever held marks can still contribute its own.
- **The page is a cache, not the owner.** A toggle applies locally and posts
  afterwards, and a `marksHeld` timestamp stops the five-second poll handing
  back a payload that predates the write. Same guard and same reason as the
  slider under a thumb in `engine.py`.

`localStorage` is deliberately not cleared. It costs nothing and it is the only
fallback if the file is ever lost.

## Settled: the header says which save, and `api/reveal` takes no argument

Added 2026-09-12 at the owner's request: *"при нажатии на autosave.fl указывать
папку с сейвами"*. The header showed `AutoSave.fl` and nothing else, while the
file it names sits at

    ~/Games/freelancer-win32/drive_c/users/<account>/Documents/My Games/
    Freelancer/Accts/SinglePlayer/AutoSave.fl

six levels down a Wine prefix, in one of several accounts, picked by mtime at
startup. **The browser cannot work that out and the server never said.** So
`api/state` now carries `save_path` and `save_dir` beside the basename, the
name in the header is a button, and opening it shows the folder with a button
that hands it to the file manager.

**`api/reveal` takes no argument, and that is the design rather than an
omission.** The only folder it can open is the one this process chose at
startup, so there is nothing for a page to point it at. An endpoint that opened
a path the browser sent would be a local server that opens arbitrary folders on
request, which is a different and much worse thing to have running on
localhost.

**The opener is spawned and never waited for**, so "opened" means asked. A
misconfigured handler would otherwise hang the POST and freeze the panel, and
the panel would be reporting on a window rather than on a request. The path is
printed next to the answer, which is what makes a silent no-op readable. The
three spellings of the action, `xdg-open`, `os.startfile` and `open`, live in
one function in `common.py`, because the second copy of that is how a project
ends up opening folders two different ways.

## Settled: a faction with nobody in any bar is nobody you can deal with

Closed 2026-09-09, cutting the Reputation tab from 55 factions to 47 at the
owner's request to drop "the nomads and the story factions".

**The rule is in the data, not in a list.** A faction with no `[GF_NPC]`
anywhere in `mbases.ini` has no one standing in any bar in the game, so there
is nobody to fly for or against. That is exactly eight of the 55 groups in
`empathy.ini`: Nomads, `fc_f_grp` (Fugitive), Kress's Men, Quintaine's Men,
`fc_uk_grp`, which resolves to a single space in the string table and has no
display name at all, and the three story doubles `fc_kn_grp`, `fc_ln_grp` and
`fc_rn_grp`. The next faction up has **seven** bar NPCs, so the boundary is
nowhere near close.

**Cut from `events` and `empathy`, never from `names`.** Being nobody you can
deal with is not being nobody: `fc_kn_grp` and `fc_uk_grp` own bases, and
cutting them out of the naming table blanked the owner badge on every one of
them. That was found by checking the owners after the cut, not by reading the
code, and it is the reason the two are separated at all.

**The `(nickname)` suffix on three faction names is gone with the clash that
caused it.** `fc_ln_grp` was the other "Liberty Navy", and the same for Kusari
Naval Forces and Rheinland Military; all three were the cut half. So
`_disambiguate` is now told which keys can actually collide and finds nothing.
It stays in place: the clash was real, and a mod that gives one of those
factions a bartender brings it straight back. The four house police forces
still collide and still take their house code.

## Settled: the story state is `MissionNum`, and only news moves with it

Closed 2026-09-07, and it is three findings that have to be read together.

**A save's story state is `[StoryInfo] MissionNum`, an index into a table of 42
names.** The names are not in any INI: they sit as a contiguous block of strings
in `DLLS/BIN/content.dll`, written in reverse, and they are kept as
`data/story-states.txt` rather than read out of a binary at run time. Verified
on **all 18 saves on this disk**, every one consistent:

    Restart.fl   Mission_01a  MissionNum 1   -> mission_01a_loaded
    Save116a.fl  Mission_02   MissionNum 7   -> mission_02_accepted
    Save707c.fl  No_Mission   MissionNum 5   -> freetime_01_02
    Save144d.fl  Mission_13   MissionNum 40  -> mission_13_accepted

The `No_Mission` row is the one worth keeping: the states between two missions
are real states with their own names, so a reader that only understood
`Mission_NN` would call that save "nowhere".

**News is gated on that state and genuinely grows as you play.** All 403
`[NewsItem]` entries in `DATA/MISSIONS/news.ini` carry
`rank = <from state>, <to state>`, and 223 of them have opened at
`mission_03_loaded` against 385 at `mission_13_accepted`. An item whose window
has closed behind you is a different thing from one you have not reached, which
is why the tab draws them by debut and marks each one live or past.

**Bar rumors are gated too, and the gate is decorative.** All **7803** `rumor`
lines in `mbases.ini` carry exactly one window, `base_0_rank .. mission_end`.
Not one of them ever opens or closes: every rumor in Sirius is available from
the first minute of a new game. It is read and applied anyway so a mod that
does gate them keeps working, but **do not go looking for a rumor that
unlocks**. What changes is where you have docked, so that is what the tab
scopes them to: 161 bases carry rumors, a median of 16 each.

**Mission dialogue cannot be added, because the text does not exist.** A
`[Dialog] Line` in a mission script names a `.utf` audio asset;
`DATA/AUDIO/DIALOGUE/` is 40 folders of sound and nothing else. Freelancer
ships no subtitles for in-space comms. This was checked before the work started
and it is the reason "news and dialogue" became "news and bar rumors".

**Rumor text is RT_HTML, not RT_STRING.** `MiscText.dll` holds 3101 resources
of type 23 and **zero** of type 6, which is why a rumor id reads as unresolvable
until the resource *type* is the thing you change rather than the file. All 3030
distinct rumor ids resolve once it is, none missing. `infocards.py` unwraps the
RDL: `<PARA/>` is a line break and everything else is furniture.

**Deliberately not done: `rumorknowdb`.** 564 lines over 112 targets name the
hidden jump hole (`li02_to_li04_hole`), wreck or base a given speaker knows
about. That is a real cross-link between the Neural Net and the Systems tree
and it is out of scope until someone asks for it.

## Settled: the `type` on a log substitution is the placeholder's letter

Closed 2026-09-07. A save's log line is
`log = <ids>, <count>, [<param ids>, <type>, 0] * count`, and `type` is the
**ASCII code of the letter in the text**. `22505` reads
"Meet Juni on Planet Manhattan%M" and its parameters are `(196609, 83)`,
`(0, 82)` and `(1, 77)`; 77 is `M`, so `%M` takes the third.

Where the detail is real that is the whole second half of the entry:
"Start scanning nearby ships%M" plus `(25240, 77)` is "Start scanning nearby
ships / Scan nearby ships and look for anything suspicious".

Checked across every save on disk: 210 log texts carry a placeholder, all of
them `%M`, and 186 have a parameter of the matching type. The other 24 have
none, which is the game saying the detail is empty, so the placeholder is
dropped rather than printed. Until this was understood the page printed a bare
`%M` at the end of a sentence, which reads as corruption.


## Settled: what in the Neural Net has a date, and what does not

Closed 2026-09-10, when the three sources became one list and the owner asked
for it sorted by when each entry arrived. The answer is different for each of
the three and none of them shares a clock with another, so the tab says so
rather than inventing one.

**A save log entry has no date at all.** No timestamp, no seconds count. The
whole save holds exactly one clock, `tstamp`, a Windows FILETIME of when the
file was written, plus `total_time_played`. Position in the log is the entire
chronology, and new entries are prepended, so index 0 is the newest.

**`base_visited` is the docked bases in the order you first docked at them**,
and that is a real receipt time for a bar rumor. Proved twice, because an order
that looks right on one save is worth nothing:

  * across the **162** saves on this disk an older save's `base_visited` is a
    prefix of a newer one's, **137** times against **14**, and every one of the
    14 sits where two saves at the same `total_time_played` belong to different
    playthroughs. A branch is not a counter-example;
  * on the live save all **24** values resolve to base nicknames, the resolved
    set is **exactly** the docked set the visit flags give, neither way round,
    and the order opens Planet Manhattan, Planet Pittsburgh, Baltimore
    Shipyard, which is the campaign order.

The values are `FLHash` of the base nickname, the same one-way hash the visit
flags and the cargo lines use. `common.dock_order` reads it, and **it supplies
order only**: `Ctx.docked` stays the authority on which bases have been docked
at, so a save carrying no `base_visited` leaves rumors unranked rather than
losing them.

**Deliberately not done: dating a log entry from its mission file.** A save log
entry can be placed on the story axis. 97 of the 299 distinct log ids across all
162 saves appear as `Act_NNIds` in exactly one `DATA/MISSIONS/M*/` file, none in
two, and a mission maps to a story state, which is the axis `news.debut` already
uses. The other 202 are the random job generator's objective text and have no
story position at all. So a true interleave of save and news is buildable: date
the 97, interpolate the rest by position between two dated neighbours, since the
log is monotonic. It is not built, because the owner picked streams-in-order
over one interleaved timeline on 2026-09-10. This note exists so nobody
re-derives the bridge from scratch to find that out.

## Settled: the game's own route tables are not shortest paths

Closed 2026-09-12, building Map → Best Path after the owner reported that the
in-game hack does not work.

**The graph is in the system files and is complete.** An `[Object]` carrying a
`goto = <system>, <object>, <tunnel>` is a jump: **232 of them across 52
systems, every one two-way, and every `goto` naming an object the same walk
found.** 84 gates, 140 holes of five kinds, two `nomad_gate` and six Dyson
airlocks. The save records which ones you have seen the same way it records a
base, by `FLHash` of the nickname, all at flag 1.

**Checked against `UNIVERSE/systems_shortest_path.ini`, the table the hack
switches the game to: equal on 1502 of its 2079 pairs, this tool shorter on
577, longer on none.** `fl.py jumps --check` is that comparison and it is the
guard on the graph: a route longer than the table's would mean an edge was
lost. New York to New London is the example, four jumps in the table against
three through Magellan.

**The nodes are jump objects, not systems**, and that is what makes it right.
New York holds both a gate and a hole to Texas and which one you want depends
on where you came in; a graph of systems cannot say that. Start at any jump in
the departure system for free, a jump costs one hop and no distance because it
is instant, flying to another jump in the same system costs the distance
between them, and arriving is the first jump that lands in the destination.

**Two costs, and they disagree on 49% of the 2182 reachable pairs**, which is
why both are drawn. Fewest jumps ties-break on distance and least flying
ties-breaks on jumps, so it is one Dijkstra under two orderings of the same
pair. Checked across every pair: no route by flying is longer than the
fewest-jumps one, and none by jumps has more hops than the least-flying one.

**Distance covers the middle systems only, and trade lanes are not in it.**
Both ends are picked by hand, so where you stand in the first system and where
you are going in the last are not things this knows; lanes would change real
travel time completely but need where the lane runs and whether it is standing,
which the files do not settle. Same rule as the perishable cargo.

**A link counts as found when either end has been seen**, not just the one you
stand at. 14 of the 116 links in the save of that day were marked at one end
only, and refusing the return trip on those would be the tool pretending not to
know about a hole whose far side it just described. Each step still carries
`found` for its own object, so the page marks what your nav map will not show.

**Five systems are a closed island**: `st01`, `st02`, `st02c`, `st03` and
`st03b`, the single-player-only Omicrons. They join each other and nothing
else, so 470 of the 2652 ordered pairs have no route at all. That is the data,
not a missing edge.

## Settled: the route tables are files, so the shortest paths go in them

Closed 2026-09-12, at the owner's go, after Map → Best Path proved the shipped
tables are not shortest paths. `live/routetable.py` rewrites them.

**This beats the byte patch on its own ground.** `live/bestpath.py` swaps which
table the game reads and dies on every save load, because `content.dll` and
`server.dll` load with the save. A file survives, needs no running game, no
`/proc/<pid>/mem` and no injected code.

### The byte patch cannot work, and that is settled by observation

**The order of events kills it.** The game reads the table **once, when the
world loads**, and `content.dll` and `server.dll` are reloaded by that same
load, which wipes the patch. So the only moment the patch can be applied is
after the read has happened, and swapping a filename pointer does nothing to a
table already in memory. flhack hooks the load itself to get in first; a button
pressed afterwards is too late by construction.

Established on 2026-09-12 by a route the owner flew, not by reasoning about
bytes: with the patch reading **ON** and all five sites verified against the
shipped files, the game routed Hokkaido to Tau-23 as `Hokkaido > New Tokyo >
Kyushu > Tau-29 > Tau-31`, which is the gates-only table's own row, where the
holes table says `Hokkaido > Kyushu` in two. Toggling the patch changed
nothing. The route tables are also not held open by the process, which fits.

**Three earlier answers were each true and each beside the point**, and that is
worth remembering: the patch does apply, the build is right, and the swap
direction is right. None of them is the question. The question was what the
game does, and only flying it answered that.

### One content, written to both files

The game ships three tables, strictly nested, and the split is jump holes:

    shortest_legal_path.ini      35 systems, 1225 pairs    0.0% hole-only hops
    shortest_illegal_path.ini    46 systems, 2071 pairs   58.4%
    systems_shortest_path.ini    50 systems, 2079 pairs   38.5%

`shortest_legal_path.ini` is what Set Best Path reads by default and is
gates-only by construction, so the 15 systems unreachable without a hole are
simply absent: **Chugoku answers "no best path" in a stock game and is right
to.** All three also omit Alaska, which is story-locked, and that exclusion is
kept.

Both targets are therefore written with **the same content, shaped from the
widest table the game ships**: its 50 systems and its 2079 pairs, section for
section. The engine then reads a shape it already parses, under either name,
and which table it picks stops mattering. The two files come out byte-identical
and `write()` checks that they did.

**Filling the gates-only file at its own width was measured and refused**:
234 of its 1225 rows would name a system it has never listed. Widening the file
to the shape of one the engine already reads is what removes that objection,
and it is the difference between this and the first attempt.

What it bought on this install: 1752 routes written into
`shortest_legal_path.ini` for 1044 jumps saved, including 854 pairs it did not
carry at all. Hokkaido to Tau-23 goes from five jumps to two.

**The cost, stated because it is real.** The lawful table stops being lawful:
its routes now run through jump holes. Whether anything else in the game reads
that distinction is not known. `--revert` puts both files back, and the
`.vanilla` copies are the shipped 35-system and 50-system files.

**More rows change than shorten**, which is the tie-break rather than a fault:
among routes of equal length the search prefers less flying between the jumps.
`--flying` asks for least distance outright, a different feature wearing the
same button, and is not the default because fewest jumps is what the game's own
feature means.


### The check went self-referential the moment this ran

**`fl.py jumps --check` compares the graph against the game's table, and
`routetable.py` writes that table.** After the first write it reported 2079
equal, 0 shorter: a tautology that reads exactly like good news, which is this
project's worst failure mode and is called out three times elsewhere in this
file. It now prefers `<name>.vanilla` when one is there, and reads 1502 / 577 /
0 / 0 again.

The general shape, worth keeping: **a tool that writes a file must not be
checked against that file.** `check_frozen.py` gets this right by comparing two
runs of the same reader; this one got it wrong by comparing a reader to
something it had edited.

## Closed: the hack applied, was aimed right, and still could not work

**The control is gone from the Engine tab**, removed 2026-09-12 at the owner's
request once the file rewrite made it redundant. `live/bestpath.py` and
`fl.py bestpath` stay; what went is the box, its reader, its POST handler and
the `bestpath` entry in `backend/engine.py`'s `API`.

**That entry was also a name collision, and a silent one.** `backend/engine.py`
and `backend/bestpath.py` both offered a GET called `bestpath`, and `tabs.py`
built one table with `dict.update`, so the later module won by import order and
the earlier endpoint was unreachable with nothing said. `_table` raises on a
repeat now, and the guard was proved to fire before being relied on. An
endpoint name is a tab's address; two tabs cannot share one.

Opened and shut on 2026-09-12. Kept because every step of it was a true answer
to the wrong question, which is the part worth not repeating.

**It applied.** `fl.py bestpath` read ON against the running game with all five
sites differing from the shipped files, verified byte by byte against both the
vanilla and the patched values.

**The build was right.** `server.dll` holds `0x0A` at RVA `0x1ACE3` and
`content.dll` `0xC4` at `0x89492`, exactly flhack's build 10; build 11's
offsets give `0x24` and `0x90`.

**The swap direction was right**, which the module's own `routes()` had always
said was unestablished. The deduction, from two checkable facts: unpatched
Freelancer routes through gates only, which is the whole reason the option
exists; and unpatched, the slot at content.dll `+0x89492` points at
`systems_shortest_path.ini` while `+0x89512` points at
`shortest_legal_path.ini`. For vanilla to behave as it does the router must
read `+0x89512`, and the swap puts the holes table there.

**And it still does nothing**, because the table is read once when the world
loads and the patch is wiped by that same load. The account, and the flown
route that settled it, are under *the route tables are files* above.

**The lesson is the sequence.** Three correct measurements in a row, each
answering a question nobody had asked, while the actual question, "what does
the game do", stayed untouched until the owner flew a route and reported
`Hokkaido > New Tokyo` where two jumps existed. **A patch reading ON is not a
patch working**, and no amount of reading bytes was going to say so.

`live/bestpath.py` is left in place and is now redundant: with both tables
carrying the same routes, which one the game reads no longer matters.

## Settled: a bribe has a place, and 11 factions have none you can reach

Closed 2026-09-12. The Reputation tab offered "bribe a bartender" with a price
and no idea where, and the count beside it was **bartenders**, which answers
"can I bribe this faction at all" and nothing else.

**A `[GF_NPC]` belongs to the `[MBase]` above it in `mbases.ini`**, which is the
whole mechanism: the file nests by position and by nothing else, so one walk
that remembers the current base attributes every `bribe` line to a station.
`game/jobs.py` makes the same walk for the job boards, and `reputation.load_bar`
now makes it too rather than throwing the base away.

Counted, not assumed:

  * 41 of the 55 factions are bribable, across **162 distinct bases**.
  * **Every one of the 2386 `bribe` lines reads a flat 10000**, so there is no
    cheapest bartender and the list answers *where*, never *where cheapest*.
    Same shape as equipment prices. What the engine actually charges is a
    separate finding and is in the section on `BRIBE_RATE`.
  * Bases per faction run 3 to 94, median 22. Too many to list, which is why
    the page lists only the ones the save has docked at: median 7 on the save
    this was built against, and that is a list worth reading.

**The number that turned out to matter is zero.** On that save, 11 of the 41
bribable factions had no reachable bar at all, the Rheinland Police among them:
25 stations will take the money and the player had landed on none. The row used
to print a price and imply it could be paid. It now says so in a sentence, and
`bases_total` is carried precisely so that an empty list reads as a journey
rather than as a lookup that failed.

**The split across layers is the same one Jobs uses.** `load_bar` returns base
nicknames and knows nothing else; `backend/rep.py` narrows them against
`GameData.bases` for dockability and against the save for where you have been,
and turns them into the shared base shape out of data `GameData` already holds.
No second base index was built, and `market.base_index` was deliberately not
imported for it.

Fixed in passing, because this endpoint now needs two facts from the save:
`_reputation` read the file itself with `fl.decode_save(ctx.save)`, outside
`Ctx`. That is the second-read trap `common.Ctx` exists to prevent, and adding
the docked set would have made it a third. It reads `ctx.saved()` now, and the
standings and the docked bases come from one decode.

## Settled: a job board's ceiling is two files multiplied together

Closed 2026-09-12 for the Jobs tab. A bar shows you what it is offering today
and never what it can offer, and the difference is what the tab exists to show.

| File | What it gives |
|---|---|
| `DATA/MISSIONS/mbases.ini` | `[MVendor] num_offers = 2, 4`, the slots on the board, and `[BaseFaction] mission_type = DestroyMission, <min>, <max>, <weight>`, one faction's band of difficulty and its weight in the draw |
| `DATA/RANDOMMISSIONS/diff2money.ini` | 23 rungs, difficulty to credits, 1800 at 0.0 up to 247065 at 100.0 |

So a board's ceiling is the money at its highest `max`, and its floor the money
at its lowest `min`. Counted, never assumed:

  * **160 of the 164 dockable bases run a live board.** Planet Primus, Planet
    Gammu and Planet Toledo carry no offering faction at all; Planet Sprague
    carries one and `num_offers = 0, 0`, so its board has no slots. `fl.py jobs
    --all` lists the four.
  * **All 241 `mission_type` rows in the game are `DestroyMission`**, the only
    random mission type vanilla ships. The kind is carried through anyway, so a
    mod that adds one gets listed rather than silently counted as a bounty.
  * 101 bases have one faction offering, 51 have two, 11 have three, one has
    five. Trafalgar Base is the five, and its weights read 40/20/20/10/10.
  * The ceiling is 146192, at Ruiz Base, Planet Malta, Planet Crete and Tripoli
    Shipyard. The lowest live board pays 2200.

**The interpolation between two rungs is load-bearing and must not be flattened
into a lookup.** Four of the 19 band edges in `mbases.ini` miss their rung by
float32 noise between the two files, `0.11239` against the ladder's `0.112387`,
the same number written twice at different precision. Walking between the
neighbours puts those within a credit of where they belong. A lookup would have
to decide what a value on no rung means, and every answer to that is invented.

**Two numbers are deliberately not printed, and they are the two you want
next.** What the job sends at you, and what the best of a full board comes to.
`npcranktodiff.ini` maps (NPC rank, wing size) to the same difficulty scale, so
the game plainly inverts it to choose your opposition, but the direction of that
inversion is in no file, and neither is how the draw is spread inside a band.
This is the `decay_per_second` rule one section down, for the same reason: a
number on the page implies a model, and neither model is checkable.

**"Open" means a system holding at least one base you have docked at**, the
owner's call on 2026-09-12 over the wider "or merely revealed". The bases inside
such a system that you have *not* landed on are the point of the tab. Measured
on the save of that day: 12 open systems, 63 bases in them, 62 running a board,
55 of those already docked at.

**Sorting and both filters are done on the page.** 160 rows and no filter
language is the Routes case, not the Equipment one, and the endpoint has already
sent every figure. The view does refetch on every entry, which Equipment's does
not: which systems are open is a fact about the save, and docking somewhere new
between two looks at the tab is precisely what it is for.

## Settled: `run.sh` used to serve the old code and look like it had started

Closed 2026-09-12, from the owner restarting the server for a new tab and the
tab not being there. Nothing was wrong with the tab.

`run.sh` started `serve.py` in the background and then waited for the port by
connecting to it. With a server already up, the new one died on `bind` while the
wait loop connected on its **first** try, because the old process answered, and
`xdg-open` then put a browser on it. The only trace was a bind error in a
terminal nobody reads. A restart that is not a restart is worse than a failed
one: the page looks exactly as it should and the new work appears to be missing.

It now refuses a port somebody already holds, names the port, and prints the
command that frees it.

**The refusal moved into `serve.py` on 2026-09-12 and that is where it belongs.**
The first fix was a `/dev/tcp` probe in the script, which is a guess by
construction: a script can look at a port, decide it is free, start the server
and never learn whether it bound. `serve.py` is the only party that knows, so
it binds before it loads anything, prints the refusal itself and exits 1.
`run.sh` is now three lines around `serve.py --open`, and `run.cmd` is the same
three for Windows.

**Two traps from the shell era, kept because both cost a session.** Nothing in
`run.sh` can trip either any more, which is precisely why they are written down
here rather than there:

  * `exec` carrying only redirections applies them to the script for good, so
    `exec 3<&- 2>/dev/null` sends every later line to `/dev/null`. That was
    written, to tidy up after the probe, and it silenced the very messages the
    fix exists to print. Proved with
    `bash -c 'exec 3<&- 2>/dev/null; echo hi >&2'`, which prints nothing.
  * **`allow_reuse_address` does not mean the same thing on both platforms.**
    `HTTPServer` sets it, and on Linux it means "bind over a socket in
    TIME_WAIT", which is what lets this be restarted straight after Ctrl+C. On
    Windows `SO_REUSEADDR` lets a second program bind a port another program is
    **actively listening on**, with no rule about which one gets a connection.
    That is this whole bug, handed out by the operating system. So `serve.py`
    keeps the flag on Linux and turns it off on Windows.

## Found 2026-09-12, not fixed: one base spells `Base` and falls out of the index

`flvisits.load_objects` keeps an `[Object]` only when it carries both `nickname`
and `base`, and it reads that key case-sensitively while `read_ini` preserves
the case it found. Across all 53 system files, **247 objects spell it `base` and
exactly one spells it `Base`**: Planet Toledo, `St01_01_Base` in Omicron Minor.

What follows, measured rather than reasoned:

  * `load_objects` returns 247 objects where the files hold 248.
  * `bases.dockable_bases` uses `read_multi` plus a key-lowering helper, so it
    sees the object and counts Planet Toledo among the 164. The two walks
    disagree about the same base.
  * Nothing can therefore resolve a visit to it: `common.read_state` maps a
    visit hash through `game.objects`, which has no entry, so Planet Toledo sits
    in `unknown` for ever even after docking. It is one of the 164 in the
    denominator and can never move to the numerator.
  * `market.base_index` cannot name it either, which is how this surfaced:
    `fl.py jobs --all` printed a bare nickname and an empty system.

The Jobs tab is not affected, because Toledo's board is shut and never reaches
it. This is left alone on purpose: it is a one-word change in `flvisits.py`,
which has its own procedure (`check_frozen.py` before and after, and diff), and
it moves a number the whole app is about. **The owner's call, not a tidy-up.**

## Settled: three commodities spoil, and the data says so twice

Closed 2026-09-10 for the Routes tab.

| Commodity | `decay_per_second` | `hit_pts` | the game's own infocard |
|---|---|---|---|
| Alien Organisms | 1.0 | 100 | `>>>HIGHLY PERISHABLE <<<` |
| Luxury Food | 1.0 | 100 | `>>>HIGHLY PERISHABLE <<<` |
| MOX | 1.0 | 200 | `>>>PERISHABLE <<<` |

Every other one of the 105 commodities reads `decay_per_second = 0`,
`hit_pts = 250`, and carries no banner. All three are traded.

**The two halves of the rule are independent and they agree.** *Which*
commodities spoil is a number in `select_equip.ini`; *how badly* is text in the
item's own infocard, which is RT_HTML and therefore a different resource type in
a different table. The set the field picks out and the set the text picks out
are the same three, which is why `market.perishable` derives it rather than
holding three nicknames somebody typed.

**What none of it says is what spoiling costs you on a run**, and the page must
not print a number that implies it does. `decay_per_second` sits among
`pod_appearance`, `loot_appearance` and `hit_pts`, every one of which is a
property of the container once it is floating in space, so the files do not
prove a hold loses cargo in flight. Routes shows the game's own label, keeps
`run` as the plain multiplication it is, says so in the note, and offers a
checkbox. Do not let a decay model in later without evidence for it.

## Settled: 39 of the 403 news items are noise

Closed 2026-09-10. `news.ini` files 403 `[NewsItem]` entries and holds **364**
distinct ones.

  * **17** carry no headline, no text, no category and no base, and every one
    of them debuts at `mission_end`. They drew as empty boxes.
  * **22** are exact duplicates, same headline and same text as an item already
    in the list, differing only in the window they run in and sometimes the
    icon. "Arrival of Freeport 7 Survivors" is filed at `mission_01a_loaded` as
    `critical` and again at `mission_01a_accepted` as `world`.

A duplicate folds into the copy that broke first, taking the wider window, the
union of the bases and `critical` if either had it.

**The fold would have eaten nine of the owner's marks, and that is the part
worth remembering.** A mark's key on the page is `news:<debut>:<headline>`, so
every filed copy has its own key and the survivor keeps only one of them. Nine
of the 266 news marks on this machine sat on a copy that would have gone.
`_collapse` therefore carries `debuts`, the full list, the payload passes it
through, and the page treats a row as marked if **any** of its keys is and
clears every one of them when the mark comes off. Measured after the change:
zero held keys unreachable, 18 marks living on a folded row.

## Settled: the engine controls are a tab, not a strip

Tried on 2026-09-07, following the design canvas, and reverted the same day at
the owner's call after it would not work for him. Two things were wrong with it
and both are structural, not cosmetic:

- **It polled the running game from every page.** Reading cruise, lane, best
  path and the docking takeover means scanning process memory, and the strip
  did it every five seconds whether you were reading Trade, the log or nothing
  at all. A tab polls only while it is open, which is the rule everything else
  on this page already follows.
- **It was rebuilt on every tick of that poll**, and a browser only fires
  `click` when the press and the release land on the same element. See the next
  section. `paint()` fixed the mechanism and the owner still could not open the
  drawer, so the strip went rather than the hunt continuing.

As a tab it also stopped showing two of its controls twice. Best path and the
docking takeover were in the strip and again in the drawer, which is two places
to read one setting.

The canvas still draws it as a strip. That part of the design is not
implemented and this is why.

## Settled: a poll that rewrites identical markup swallows clicks

Found 2026-09-07, an hour after the redesign shipped, from the owner's report
that `ALL KNOBS` "opened once and then stopped opening".

`render()` runs on the five-second poll and was assigning `innerHTML` on the
engine strip, the panel and the totals row every single time. **The markup was
byte-identical**, 1389 characters of it for the strip, because the values it
prints only change when you change them.

Assigning `innerHTML` destroys and rebuilds every child, and **a browser only
fires `click` when the press and the release land on the same element**. So a
click whose mousedown and mouseup straddled a tick produced no `click` event at
all: no error, no console line, nothing to see. Every button on every tab was
exposed, not just that one.

Proved in a headless browser rather than reasoned about: press the button, run
one `render()`, release it, and `document.querySelector('#engmore')` is a
different object from the one the press landed on.

The fix is `paint(node, html)` in `frontend/shell.py`, which writes only when
the html differs and returns whether it did. **It is not an optimisation and
must not be removed as one.** Rewiring is skipped along with the paint, which
is correct: handlers survive because the elements they are on do. Text
selection, focus and scroll position stop being thrown away every five seconds
as a side effect.

The general rule for anything on this page: a five-second poll is allowed to
compare, never to rebuild. If a panel must be rebuilt on a tick, its buttons
are not clickable and no amount of testing the handler will show it.

### `paint` was comparing against the wrong thing, and four views never matched

Reopened and closed again 2026-09-10, from the owner's report that *"селекты
скрываются после нажатия мышью"* and that the Equipment search box loses focus
after a while. He guessed a browser fault. It was this section's own fix, half
done.

`paint` wrote only when its markup differed from **`node.innerHTML`**, and that
comparison cannot work: the browser hands back its own serialisation, not the
string it was given. Measured per view:

| View | Written | Read back |
|---|---|---|
| `search` | `<option value="guns" selected>` | `selected=""` |
| `rep` | the same | |
| `systems` | `<div class="housebody" hidden>` | `hidden=""` |
| `log` | a U+00A0 inside a rumor, raw | `&nbsp;` |

A bare boolean attribute comes back with `=""`, and a character the serialiser
prefers as an entity comes back as one. So four of the nine views never matched
and were destroyed and rebuilt on **every tick**, for three years of
five-second intervals, with nothing to see: `wire()` re-ran, so the buttons
still worked. What went was the open `<select>`, the focused input, the
half-typed text, the selection and the scroll position. `overview`, `chart`,
`market`, `routes` and `engine` were stable, which is why it hid.

**Writing the markup more carefully is not the fix and must not be attempted.**
The comparison was the bug. `paint` now remembers the last html it wrote, in a
`WeakMap` keyed on the node, where it is exactly the string that went in. It is
also cheaper: reading `innerHTML` on a 700-row table serialised the whole
subtree once a tick to answer a question about a string.

Two consequences worth keeping:

- **Anything that empties a painted node by hand goes through `clear(node)`**,
  or the record says it still holds markup that is no longer on screen and the
  next legitimate write is skipped. `check_views.py` is the one caller.
- **`check_views.py` now measures the invariant**, by identity rather than by
  asking `paint` whether it wrote: render a view twice with the same data and
  no node may be replaced. Proved to fire by putting the old comparison back on
  purpose: 12 `POLL` lines, naming exactly `systems`, `search`, `rep` and the
  two log views that carry rumors.


## The look: `design/Neural Companion.dc.html` is the source, not a screenshot

Added 2026-09-07. The page's visual language is a Claude Design canvas that
lives in `design/`, drawn by the owner: dark HUD, Chakra Petch over IBM Plex
Mono, cyan for the instrument and amber for anything that touches a file.
Overview and Systems are drawn in full; Equipment, Trade, Reputation and Neural
Net are drawn as markup; **Chart is the one screen it does not cover**, and was
built from the same panel, border and label vocabulary as the rest.

Read it before changing how anything looks. Its values are in
`frontend/_theme.css` as tokens and nowhere else, so a colour has one spelling.

**The canvas emits inline styles because that is how its editor works; the page
uses classes.** Do not port a `style="..."` across. And a tab's own selectors
live in that tab's module rather than in the theme: the two grid-column bugs
this project has shipped were both a row template and its column list drifting
apart in two different files.

Three places the page deliberately departs from the canvas, all for the same
reason, that every engine control writes into a live game: a slider posts on
release rather than per pixel of drag, a redraw is held off while a slider is
under a thumb, and the two expensive readings behind `ALL KNOBS` are fetched
only when it is open. `frontend/engine.py` says so at the top.

`check_views.py` skips any grid carrying `wrapgrid`. That is the marker for a
grid that is meant to wrap, the Overview's panel flow and its label/value list,
as against a table row whose cell count must match its column list. It cannot
be told from the computed style, because `repeat(auto-fit, ...)` resolves to
concrete tracks and reads exactly like a hand-written column list.

## Writing to the running game

The Engine tab changes cruise speed in a live Freelancer, and this is the only
part of the project that writes anything anywhere. It writes to process memory,
never to a save and never to a game file.

It exists because `CRUISING_SPEED` is a single global in `constants.ini`, read
once at startup, with no per-system or per-zone variant anywhere in the data:
the key appears in exactly one file of the 8370 under `DATA/`. Wanting 5000 in
open space and 500 in an asteroid field therefore cannot be expressed in the
game's own data at all.

Confirmed working on 2026-09-01 by writing 20.0 into a live game: the ship
slowed on the spot, no reload and no crash, and the owner then asked for the
tab. So the value is read per cruise burn and never cached when the ship spawns.

**Never hardcode the address.** It lives in `common.dll`, which loads at a
different place each run. `speed.py` finds it by the three floats that follow
it, `5.0, 3.0, 0.25`, unique in the whole address space: one hit every time.
Searching for the speed value is useless, plain `1000.0` matched 6948 places,
which is what killed the first two attempts.

A change lasts until the game is closed. `constants.ini` still says what it
said, which is the intended split: the file is the default, the tab is the
session.

`kernel.yama.ptrace_scope` is 0 on this machine, so no privileges beyond the
same user are needed. On a machine where it is not, this stops working and
should say so, and must not be "fixed" by loosening it.

**Two kinds of address, and only one of them is searched for.** `speed.py`
scans, because `CRUISING_SPEED` sits in a loaded copy of `constants.ini` whose
position is not fixed. `tradelane.py` and `dockdist.py` do not: their constants
are in `common.dll` itself, at addresses taken from **flhack** (Jason Hood,
2014, source at `~/Downloads/flhack/`), resolved against the module's own base
from `/proc/<pid>/maps`. A scan is the wrong tool there and was tried first: it
found a lone 2500.0 that turned out to be a CommConsts value in the loaded
`constants.ini` and never the trade lane speed. Both modules validate what they
found before writing to it, by reading the float and refusing if it is not a
plausible value, which is what catches a wrong build or a moved address.

Those addresses land in `.rdata`, which is read-only in the process.
`/proc/<pid>/mem` bypasses page protection, so no `mprotect` is needed the way
flhack needs one on Windows.

## Settled: the dock cruise distance lives in `common.dll`, and in no INI

Closed 2026-09-05, after a fix aimed at the wrong number did nothing. Worth
reading before anyone reaches for `select_equip.ini` again.

**There is no docking distance anywhere in the game's data.** A sweep of all
1252 INI files under `DATA/` for any key whose name contains `dock` returns
`docking_sphere` and `dock_with` on objects, `act_lockdock` and friends in the
mission scripts, and nothing global. `Trade_Lane_Ring` in `solararch.ini`
carries no `docking_sphere` at all, where `jumpgate` carries 225 and `jumphole`
150. `constants.ini` has nothing either.

**It is a float in `common.dll`, and the compare is one instruction:**

    0x62fe171  d8 1d c0223a06   fcomp dword [0x63a22c0]   ; 1750.0

Confirmed both in the shipped file and in the running game. `0x63a22c0` is
flhack's `ADDR_DOCK_DIST10`, its "Cruise to dock from" setting, and its default
table calls it "activate cruise for docking from this". Four instructions read
it, one `fcomp` and three `fmul` about 1250 bytes earlier in the same function,
so changing it moves more than the cut point.

**Why a trade lane runs through the dock path at all:** flhack's help says the
proximity radius default of 495 "is that used by Trade Lanes". Entering a lane
is a dock, which is the lead the owner gave and the reason this was found.

**That constant is only half the job, and the half that is not the interesting
one.** `0x63a22c0` decides *whether* the autopilot uses cruise for a dock run,
and the compare is gated by `[esi+0x365]`, which is cleared straight after, so
the answer is latched once when the dock is ordered and never recomputed as
you close in. Moving it from 1750 to 300 changed nothing anyone could feel,
because at any real trade lane range both answer "use cruise".

**The distance at which docking takes over is a code patch, never a number**, and
that is why every constant tried did nothing. It is `[ebp+0x50]`, a descriptor
field loaded at `0x62fe758`, so the only place to change it is the instruction
that reads it. flhack calls this "Closer docking". `dockdist.py --takeover`
ports its stub; `inject.py` carries how the code gets in. Settled at **200 m**
for lanes and gates on 2026-09-05 after the owner flew 100, 200, 400 and 600,
which is the value flhack picked independently.

**One global was tried and disproved: `0x639f44c`.** It initialises a field
that holds the same 1000.0 and looked like the same thing. The owner flew it at
100, 1000, 5000 and 10000 with no difference to a lane approach. The knob was
removed the same day. Do not go looking for it again.

## Injecting code: the cave, and the page that is not writable

`inject.py`, 2026-09-06. flhack allocates executable memory with
`VirtualAllocEx` and stores the pointer at `0x67bf40`. `/proc/<pid>/mem` cannot
allocate, and it does not need to:

    common.dll .text ends at 0x6398730 with 2256 bytes of zero padding,
    inside a mapping that is already r-xp

That is linker slack between the end of the code and the start of `.rdata`.
Nothing writes there, and writing to it from outside works because
`/proc/<pid>/mem` goes through page protection, the same way `tradelane.py` has
written to `.rdata` since 2026-09-02.

**The trap, and it kills the game instantly.** Writing to the cave from outside
is fine; the game writing to it is not, because the page is read-only. The
first version of the stub stored `dockwith` into the cave and Freelancer died
on the first call. flhack has the same split and solves it the same way, with
its data at a static address it first makes writable. We cannot change
protection, so anything the stub writes at runtime goes to `inject.find_scratch`,
a zero run in a mapping that is already writable. Constants stay in the cave,
because only this tool ever writes them, from outside.

**Be frugal reading `/proc/<pid>/mem` on this machine.** `volkface` is a 7.6 GB
tablet that sits at a few hundred MB free with the game up. The first
`find_scratch` pulled whole mappings into Python and walked them byte by byte,
and the desktop stalled hard enough to look like a freeze. It now reads in 1 MB
chunks, matches in C with `bytes.find`, and stops at the first hit: 0.1 s and
14 MB.

**Not every patch needs a stub.** Best path through jump holes is five bytes in
`server.dll` and `content.dll` and no injected code at all, because the thing
being changed is a pair of pointers and no computed value. flhack wraps
it in a runtime hook only because it patches at launch, before those libraries
exist; patching from outside while a game is already loaded needs none of that.
Reach for `inject.py` when a value is computed, never by habit.

Two facts that shape `bestpath.py`:

  * **The build fingerprint is the byte the patch changes.** flhack identifies
    v1.0 by `server.dll` holding 0x0A at the type site, and the patch writes
    0x03 there. So "wrong build" and "already patched" are one check in one
    place, and neither can be read as the other.
  * **Those two libraries load with the save**, so the patch dies on every game
    load. That is stated in the UI and not worked around, because the
    workaround is a loader hook and the honest version is a button.

**Not every freeze is yours.** The one on 2026-09-05 was
`i915 GT0: rcs0 reset request timed out`, an Iris Xe GPU hang the driver could
not recover from, with the injected stub in memory at the time and entirely
innocent. Read the journal before assuming.

## Settled: equipment costs the same everywhere, and `npc_` gear is not for sale

Both closed 2026-09-04 while building the Equipment search, both by counting
and never by assuming, and both shape what the page can offer.

**One price, every dealer.** `market_misc.ini` rows carry the same seven fields
as a commodity row, but the multiplier is exactly `1.0` on all 10871 of them and
no item's differs between bases. So there is no cheapest dealer to find: the
price belongs on the item and the expansion answers *where*. Do not port the
Trade tab's dearest-versus-cheapest logic over; it has nothing to work on. The
rank (0 to 30) and reputation (-1 to +0.8) gates are the same everywhere too,
checked across the 366 goods sold at more than one base.

**No item whose nickname starts with `npc_` is sold anywhere**, guns or shields.
That plus "has no `[Good]`, so no price and no dealer" is the whole of what the
catalogue drops, and the counts are in `equipment.py`. The visible symptom if
the filter is ever removed: the shield list is led by `npc_shield01_mark10` at
10127 capacity, which no player can buy.

**The rule for what gets listed is acquirability**, not a nickname pattern.
It was *sold at a dockable base, or present in a wreck*, which kept the 17
codenamed guns (the hardest hitting in the game, all of them wreck loot) and
dropped 12 others. **A third way was added on 2026-09-12**, shooting whoever is
flying it; see the next section. Same shape as `bases.py`'s rule and the Trade
tab's undockable markets.

## Settled: a gun has four sources, and "nowhere" is one of them

Closed 2026-09-12 on the owner's report: *"в списке оборудования нет руки
смерти мк3 и номадских пушек"*. **Two different causes under one sentence**, and
finding that out was the whole job.

**The Nomad guns were a real gap.** The obtainable rule knew dealers and
wrecks. There is a third route the data states plainly and nothing here had
ever read: `MISSIONS/lootprops.ini` gives `special_nomad_gun01` and `02` a
`drop_properties` of 10, and `SHIPS/loadouts.ini` hangs them off five and four
Nomad loadouts. You shoot a Nomad and it falls out, which is exactly as
obtainable as a wreck. They are the two hardest-hitting guns in the game at
2568 and 2543 hull DPS, above CERBERUS, so their absence was not a detail.

**Death's Hand Mk III is referenced by nothing.** A grep for it across all of
`DATA/` returns `weapon_equip.ini` and `weapon_good.ini` and no third file: no
dealer, no wreck, no loadout, no mission script, no loot entry. It shipped and
was never wired up, and the same is true of Reaper Mk III, the two Order
turrets Mk II, Vengeance Mk III, Rowlett's Revenge and the Nomad Prototype
(which NPCs carry but nothing can drop). The owner's save carries none of the
twelve, checked against the `equip` lines.

So every row now carries a `source`: `sold`, `wreck`, `loot`, `none`, and the
tab shows the first three by default with a checkbox for the fourth.
**Absence that cannot be explained was the actual bug**: the list gave no way
to tell "this is not in the game" from "the reader lost it", and it was the
second of those the owner reasonably assumed.

**Both halves of the loot rule are required, and dropping either breaks it.**
Measured both ways:

  * a drop chance alone lets in the twelve `shield01_mark08_lf`-shaped shields,
    which carry a 6 and sit on no ship in the game, so nothing can drop them;
  * a loadout alone lets in all 26 `npc_` shields, which carry no chance at all
    and would head the capacity list at 10127 against a best buyable 289150,
    which is the exact failure the `npc_` rule above exists to prevent.

The pair keeps one rule honest for guns and shields alike, so there is no
gun-only exception to remember. Shields still come out at 79 of 121.

**There is deliberately no "the story gave it to you" source.**
`msn_playerloadout`, the ship the campaign hands you at the end, carries exactly
one thing no dealer sells, `special_nomad_gun01`, which already qualifies by
dropping off Nomads. A source that can never be the answer is worse than no
source. Whatever else the mission scripts hand over is not in these files.

**On the percentage.** `drop_properties[0]` is read as a chance: across all 434
entries it runs 0 to 100, it is 100 on every commodity, 33 on nanobots and
shield batteries and 8 on most guns. Nothing depends on that reading beyond it
being non-zero, so a wrong unit costs a word on the page and not a row in the
list. Fields 2 and 3 are always equal to each other and are not the price.

## Settled: a media query asks the viewport, and the layout is not in it

Closed 2026-09-10, one day after it was introduced. Systems lays a house out
two cards abreast, and it was written as `@media (min-width: 1400px)`. The
owner never saw it fire, at any zoom.

**1400 was a number picked out of the air, and his page is not the viewport.**
His browser carries a sidebar that takes some 600px off the window, so the page
sat at roughly 1396 CSS px: a hair under the guess. Zooming out widens the CSS
viewport and should have crossed it, which is why it read as "the feature does
not work" rather than "the window is too narrow".

It is now a container rule with no breakpoint in it:

    grid-template-columns: repeat(auto-fit, minmax(max(34rem, 48%), 1fr));

`48%` is what caps it at two, because three tracks of 48% cannot fit however
wide the screen gets. `34rem` is the floor, so it drops back to one column
rather than squeezing a system's base list into something unreadable. Measured:
one column at 900 and 1100, two from about 1130px of page width, two at 1256,
1396, 1500 and 1920, never three.

**The general rule: a media query measures the window, and almost nothing on
this page lives in the window.** `.wrap` caps at 1680, a sidebar takes what it
likes, and the panel is inside both. Where a layout should change because *this
box* got wider, size it from the box: `auto-fit` with a percentage floor says
that directly and cannot be wrong about somebody else's chrome. `.totals` and
`.hits` were already written this way; Systems was the odd one out.

## Settled: docked-only filters, and a favourite outranks every filter

Closed 2026-09-10, and the first half **reverses a decision this file used to
defend**, so read both halves before restoring anything.

**"Only bases I have docked at" now drops rows.** It used to rewrite each row's
`bases` and keep the row, so the page could say "nowhere you have docked sells
it", and `backend/search.py` and `equipment.py::search` both carried paragraphs
explaining that this was the opposite of the system filter and must not be
merged with it. The owner's verdict: *"бесполезна в текущей реализации"*, and
he is right. It left 187 of the 235 guns on screen with nothing under them,
wreck loot included, which is not a filter. Measured against a save with 30
docked bases: guns 235 → 51, shields 79 → 36. It is a filter kind inside
`eqp.search` now, so one function still decides what is kept. `search.py` still
narrows each surviving row's `bases` to the docked dealers, which is a
different job, runs after, and can no longer empty a row.

**A favourite bypasses every filter.** `eqp.search` takes `keep`, a set of
nicknames checked before the filters and then **carried through the same
sort**, which is what puts a favourite in the ranking rather than in a pile on
top of it. Verified: starring the weakest gun in the game and asking for
`hull_dps >= 100` returns 226 rows instead of 225, with that gun last.

**The favourites live in `data/marks.json`, under their own kind.** Not
`localStorage`: that is the trap that lost the Neural Net's marks on
2026-09-09, and the account is under *the reader's marks belong to the server*.
`fav` rather than a share of `star`, because a starred news item and a
favourite gun are different things. The key is the bare item nickname, which is
unique across guns and shields (314 rows, 314 nicknames), so it needs no prefix
and carries none.

**The Equipment tab has no `marksHeld` guard and does not need one.** It
registers no `poll`, so nothing arrives to overwrite a star between the click
and the reload that follows it. The Neural Net's guard sits next door because
that tab re-reads its log every five seconds. Said out loud in the code, or the
absence reads as an oversight.

## Settled: the Equipment table shows every column, and you can drop one

Closed 2026-09-10, in two passes. It used to show the sorted column plus
whatever was being filtered on, two or three of nine, which is what *"в таблице
мало данных"* meant. Measured with all of them on: guns need 1335px and shields
1244px, no header is clipped at any width, and the page never scrolls sideways.
Below about 1350px the table scrolls inside its own `.guns` box, which is what
`overflow-x: auto` is there for. So all of them are drawn.

**Dropping one is a `×` on its heading, not a row of switches and not a
stepper.** Both of those were offered and the owner picked the heading: there
is no extra control on the page at all until something is off, and then a
`+ add a column…` select appears beside the `+ add a parameter…` one that was
already there. `gearHidden` holds **the exceptions, not the selection**, so an
empty set is the full table and a parameter added to the game later appears
without being named anywhere.

**A column you sort or filter on cannot be hidden and carries no `×`.** An
arrow pointing at a column that is not on screen, or a filter narrowing the
list by a number you cannot see, is the table lying about itself.

Neither dropping nor restoring a column asks the server for anything: the
figures are already in the payload. Verified, along with the click not falling
through to the sort the heading also answers, and with the row cells staying in
step with the grid at 12, 9 and 10 columns.

`price` stays out of the parameter columns: it has a fixed column of its own
further right, and listing it twice is how a table starts lying about itself.
`default` came out of the payload with the old column rule, its only reader.

## Settled: rank needed is a comparison, and the other numbers are not

Closed 2026-09-10. `rank` is `cmp` in `PARAMETERS`, which draws the same
`[= <= >=]` select the mount class does. Every other numeric parameter stays a
plain minimum, at the owner's call: *"at least 400 hull DPS"* is the question
people have about a gun, and *"at least rank 16"* is not a question about
anything. What you want to know is what you can fly now.

**Both comparisons are inclusive**, changed from `<`/`>` on the owner's call
the same day, and that has a naming consequence worth keeping: **`>=` on a
number is `num`**, which every other numeric filter already sends, because "at
least" is precisely what `num` means. So the page sends `num` for it and there
is no `over` kind. `<=` has no twin and is `upto`.

**`le`/`ge` are not those two under different names.** They compare mount
classes and refuse to answer across a socket family, because a shield's
`fighter 6` and `elite 6` are different mounts; the numeric pair compares
numbers. One name for both would put that family rule on a price.

Checked against the catalogue, and the inclusive figures compose exactly with
the strict ones they replaced:

| | `=` | `<=` | `>=` |
|---|---|---|---|
| rank 16, guns | 51 | 160 (109 + 51) | 126 (75 + 51) |
| mount 6, guns | 51 | 145 (94 + 51) | 141 (90 + 51) |
| mount `fighter 6`, shields | 3 | 18 | 11 |

The shield rows are all `fighter`, none of them `elite` or `freighter`, which
is the family rule holding. And 126 is what `num 16` gave before any of this,
which is the check that `>=` really did collapse into it rather than becoming
a second implementation of it.

## Systems are identified by nickname, never by display name

Found 2026-09-04 while adding the Routes sub-tab. Five system display names are
shared by more than one system: **Omicron Beta** is `Ew02` and `St02`, **Omicron
Major** is `St03`, `St03b`, `St02c` and `FP7_system`, and **Unknown** is `Ew05`
and `Ew06`.

Only one of each group has a market, so keying the trade selectors on labels
would have worked today, by luck, and broken the moment anything looked at the
single-player-only or multiplayer-only systems. `market.py` rows therefore carry
both `sys_nick` and `system`: the nickname is the identity, the label is what
gets printed.

Same shape as the three duplicated faction names on the Reputation tab, and the
same answer: the display string is not a key.

## The page is one inline script, so a parse error takes all of it

Added 2026-09-04 after the tab strip came up empty. The whole UI lives in one
`<script>` in `PAGE`, which means a *syntax* error is not a broken feature, it
is a page with no behaviour at all: static HTML, a stuck "loading…", no tabs.
The server serves that quite happily, so curl says 200 and the API answers.

The specific cause was `let top = 'map'`. `window.top` is a non-configurable
property of the global object, and a global `let` or `const` on such a name is a
SyntaxError rather than a shadowing declaration. `window`, `self`, `location`
and `document` behave the same way. The variable is `topTab` now.

**Verifying this needs a browser.** `firefox --headless --screenshot` renders
the page and shows whether the strip drew. The shot fires at the load event,
before the first `fetch` resolves, so an empty body in it is expected and is not
evidence of anything; the tab strip is the part that tells you.

**`check_views.py` has to survive the page script being dead, and did not.**
Found 2026-09-07, when an unclosed template literal in `frontend/log.py` took
the whole inline script down. The driver's own first act was
`Object.keys(VIEW)`, and with the script dead `VIEW` is undefined, so the driver
threw before it could write a single line and the report came out as a blank
page. The one failure the tool exists for was the one failure it could not
report. It now checks `$` and `VIEW` first and says so in words, and the seeding
runs inside a try of its own.

## Changes made to this install by hand, outside the tool

Not everything in the game files is vanilla, and a value that looks wrong may be
deliberate. Anything the tool wrote has a `.vanilla` beside it, which is the
audit trail; this section covers what was changed by hand.

**`DATA/EQUIPMENT/select_equip.ini` is back to vanilla as of 2026-09-06, and
the round trip is the lesson.** On 2026-09-04 `[TradeLane] basic_trade_lane_eq`
had `activation_start` cut from 750 to 100 and `activation_end` from 500 to 50,
to make cruise hold until the ring was close. It did nothing, because those two
are the *ring's* equipment and govern its spin-up window; they never reach the
ship's engine state. Restored from `select_equip.ini.vanilla` once the real
mechanism was found, verified key by key at 15 `[TradeLane]` keys matching.

**Do not reach for this section again to change docking behaviour.** What the
edit was trying to do is now `dockdist.py --takeover`, which patches code in
memory and needs no file change at all. The only thing this file would still
affect is how quickly the ring itself spins up, which is a separate complaint
and has `spin_accel` and `secs_before_enter` beside it if it ever comes up.

**`DATA/MISSIONS/M13/m13.ini` has the end-of-campaign reputation reset zeroed,
and this is the second time it has been applied.** The `[Trigger]` named
`enter_bar` fires on walking into the bar at the end of M13 and hard-sets 47
reputations: Liberty 0.91, a band of factions 0.65, pirates -0.3 and -0.65, and
17 already at 0. That is the game overwriting every relationship you spent the
campaign building. All 47 now read 0.0, so the story ends on neutral.

**It was applied once before and vanished without trace.** On 2026-09-02 the
file was written back to vanilla content, mtime 21:31, later than the `.vanilla`
copy taken on 09-01, and nothing in this repo records what did it. There is no
module for this edit: it was a one-off then and a one-off again on 2026-09-09 at
the owner's call, which is why it gets a paragraph here instead. **If the
reputations come back at the end of a campaign, check this file first** rather
than looking for a bug in the reputation model.

Re-applying it is a decode, zero every numeric third field of `Act_SetRep` in
that one trigger, re-encode through `persist._save`, which refuses to write
unless the round trip is identical. Leave the `Act_SetRep` entries in the other
triggers alone: theirs are symbols like `REP_FRIEND_THRESHOLD`, not numbers.

Also worth knowing when reading these files: `CRUISING_SPEED` in
`constants.ini` currently says 5000.0, written by the Engine tab's persist
button, and 153 asteroid field files carry a scaled `fill_dist` from
`drawdist.py`. Both have `.vanilla` backups.

## Settled: an RTC is not a cutscene, and the first mission cannot be trimmed

Tried on 2026-09-06 at the owner's request, broke the game twice, and reverted.
Both facts are worth keeping, because both look obvious in the wrong direction.

**`Act_AddRTC` populates a room.** The file it names is a
`[CharacterEncounter]`: a `Location`, one `action` scene, and a list of `[Char]`
entries. `m001a_s003x` puts the bartender, Juni and the Liberty diplomat in the
Manhattan bar; `m001a_s004x` puts Juni and the diplomat there; `m000_s002xe`
puts the wounded Lonnigan on the cityscape. Removing the `Act_AddRTC` does not
skip a scene, it empties the room. With no Juni to click there is no
`Cnd_CharSelect`, so no job offer, no `Act_SetShipAndLoadout` and no ship.

The distinction that does exist is `autoplay`, present on 61 of the game's 68
character encounters. With it the scene runs on entering the room; without it,
`s004x` being the one example in this mission, it runs when the character is
clicked. Dropping that key is the surgical version and was written but never
tested, because the owner called the whole line of work off first.

**`tr_fp7_cam_end` is not a wait.** The Freeport 7 opening is a chain of timers
on the 33 triggers scoped to `FP7_system`, and this one is started by the first
trigger, runs beside the whole chain, and ends it with `Act_ForceLand` on
Manhattan. Its 68.5 seconds is the length of the sequence, not a pause in it.
Capping every timer to 1s therefore force-landed the player one second in while
the chain went on spawning ships and lighting fuses in a system being torn down,
which is the crash. Vanilla runs a 42.8s chain under a 68.5s marker, x1.60, so
a compressed chain needs the marker recomputed rather than capped.

Neither is applied. `newgame.py` writes the starting ship and nothing else, and
its `.vanilla` copies cover only `loadouts.ini` and `m01a.ini`.

## Settled: one codebase for both platforms, and the Windows half is unproven

Added 2026-09-12 on the owner's ask, *"попробовать адаптировать это всё и под
винду"*, with their answer to how it would be tested: write it and mark it.

**There is no Windows fork and there must never be one.** No second `serve.py`,
no `_win` copy of a reader, no branch. Three things differ between the two
platforms and each picks its spelling at import from `sys.platform`:

| What | Linux | Windows |
|---|---|---|
| where the game is | the Wine prefix under `~/Games` | `AppPath` out of the registry, `Program Files (x86)` as the fallback |
| where the saves are | every Wine prefix beside the game | the `Personal` shell folder, because OneDrive moves Documents |
| process memory | `/proc/<pid>/{maps,mem}` | `ReadProcessMemory` and friends |

Everything else was already portable and needed nothing: the save decoder, the
BINI reader, the PE string tables, the DPS model, the jump graph, the job
boards and the whole page are plain Python on `os.path`.

**`backend/live/proc.py` is the only code in the project that touches another
process.** Before this, 22 places across `speed.py`, `inject.py`,
`tradelane.py` and `thrusters.py` opened `/proc/<pid>/mem` themselves, which is
22 copies of a decision with one right answer per platform. They now call six
functions: `find_pid`, `mappings`, `regions`, `read`, `write`, `chunks`.
`mappings` yields `(lo, hi, perms, name)` with `perms` spelled the way
`/proc/<pid>/maps` spells it, `rwxp`, on both platforms, because that is what
the callers already read.

**The refactor was proved by the game that was running at the time.** Every
`fl.py` live command was captured before and after and the two are byte
identical, and each write path was then exercised with a value equal to the one
already there: `fl.py speed 300`, a thruster set to its own speed, and a POST
to `api/allhacks`, which writes into `.text` and into data and reported
everything already on. The output was identical again afterwards.

### The Windows half has never run, and three traps are designed around

Written against the Win32 documentation in one pass. Each of these returns a
wrong answer rather than an error, which is why they are designed around rather
than waited for:

  * **Toolhelp cannot enumerate a 32-bit process's modules from 64-bit Python.**
    `CreateToolhelp32Snapshot(TH32CS_SNAPMODULE32)` fails with
    `ERROR_PARTIAL_COPY` across WOW64, and Freelancer is 32-bit while the Python
    most people install is 64-bit. Modules come from `EnumProcessModulesEx` with
    `LIST_MODULES_ALL`. Toolhelp is still used for the process list, where it
    has no such problem.
  * **`MEMORY_BASIC_INFORMATION` is laid out for the caller, not the target**,
    so its pointer fields are `c_void_p` and `RegionSize` is `c_size_t`.
    Declared as `c_uint32` it would look right on a 32-bit Python and read
    garbage on a 64-bit one.
  * **Every function gets `argtypes`.** Without them ctypes passes a `HANDLE`
    as a C `int`, truncating it on 64-bit, and the call then fails or succeeds
    against nothing.

**Writing needs `VirtualProtectEx` and Linux does not.** `/proc/<pid>/mem`
writes straight through page protection; `WriteProcessMemory` does not, and
every target here is in `.text` or `.rdata`. So the Windows `write` lifts the
protection, writes, puts it back and flushes the instruction cache, which is
not decoration: a patched instruction still in the CPU's instruction cache is
the game running the old byte for a while. **This does not change
`find_scratch`.** That exists because the game's own `mov` into a read-only
page faults, which is the game's problem and not ours; being able to lift
protection from outside does not make `.text` padding safe for the game to
write.

### What `check_windows.py` settles, and what it cannot

It puts the Windows-sized types back into `ctypes.wintypes`, fakes `WinDLL`,
imports `proc_windows.py` for real and then measures it. That settles every
name, every struct size and offset against the documented Windows numbers, and
that every imported function has `argtypes` and `restype`.

**`ctypes.wintypes` imports on Linux and lies about sizes**, which is the trap
the check itself had to be written around: `wintypes.DWORD` is `c_ulong`, four
bytes on Windows and **eight on 64-bit Linux**. Imported as-is,
`MEMORY_BASIC_INFORMATION` measures 56 bytes here and 48 where it matters, and
a check that accepted 56 would be reporting on a struct that does not exist.
`c_wchar` is two bytes on Windows and four on Linux, so the check measures
`WCHAR` with a two-byte stand-in.

It earned its place immediately: `pcPriClassBase` was declared `ctypes.c_long`,
which is a Win32 `LONG` on Windows and eight bytes on Linux, and the check
caught `PROCESSENTRY32W` coming out 1096 bytes instead of 568.

What it cannot settle is whether the calls do what the module thinks. Only
Windows answers that, and `fl.py proc` is the command that asks: pid, modules,
sixteen bytes of `common.dll`, nothing written.

## Dependency

`bini.py` lives in `../scripts/` and is shared with other work in this area. It
is not part of this project and is not frozen. **The path is derived from
`backend/__init__.py`'s own location**, two levels up, and that file now checks
the file is there and says where it looked. Without the check the first thing a
checkout without the vault beside it sees is `ModuleNotFoundError: No module
named 'bini'`, which names a module nobody has heard of and no path at all.
