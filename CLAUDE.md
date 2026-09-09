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
| `data/story-states.txt` | the 42 story states in order. `MissionNum` in a save indexes this |
| `backend/live/speed.py` | cruise speed of the *running* game |
| `backend/live/thrusters.py` | the same for the six thruster bonuses |
| `backend/live/tradelane.py` | trade lane speed and the 999 cap on the HUD readout |
| `backend/live/dockdist.py` | when the autopilot cruises to a dock, and where it takes over |
| `backend/live/bestpath.py` | let Set Best Path route through jump holes |
| `backend/live/inject.py` | the code cave, and how a stub gets into it |
| `backend/live/persist.py` | writes the live speeds back into the game's files |
| `backend/live/drawdist.py` | scales asteroid `fill_dist` across the 153 field files |
| `backend/live/newgame.py` | what a new game starts you in |
| `data/freelancer-map.jpg` | the sector chart, served at `/map.jpg`. **Untracked**: fan-made and not ours to redistribute. Drop your own copy in. |
| `design/` | the visual design, as a Claude Design canvas. The source the page is built from, not a screenshot of it. |
| `run.sh` | start the server and open a browser on it |

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

**The rule for what gets listed is acquirability**, not a nickname pattern: sold
at a dockable base, or present in a wreck. That keeps the 17 codenamed guns,
which are the hardest hitting in the game and are wreck loot, and drops the 12
mission weapons that are in neither place. Same shape as `bases.py`'s rule and
the Trade tab's undockable markets.

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

## Dependency

`bini.py` lives in `../scripts/` and is shared with other work in this area. It
is not part of this project and is not frozen.
