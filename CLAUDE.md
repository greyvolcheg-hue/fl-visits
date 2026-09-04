# fl-visits

Reads a Freelancer save game and reports what the player has found, grouped by
system. Own git repo; the history in this folder is the undo button.

| File | What |
|---|---|
| `flvisits.py` | save decoding, the nickname hash, game data loading, bases CLI. **Frozen, see below.** |
| `wrecks.py` | the 157 secret wrecks and their loot, as data and as a CLI |
| `docking.py` | which bases can actually be docked at, and the denominator both programs use |
| `navmap.py` | world position to nav map cell |
| `speed.py` | reads and writes the cruise speed of the *running* game |
| `thrusters.py` | the same for the six thruster bonuses |
| `tradelane.py` | trade lane speed and the 999 cap on the HUD readout, live |
| `persist.py` | writes the live cruise and thruster speeds back into the game's files |
| `drawdist.py` | scales asteroid `fill_dist` across the 153 field files |
| `weapons.py` | gun and munition stats turned into DPS, static game data |
| `netlog.py` | the Neural Net log out of a save, as readable text |
| `reputation.py` | the empathy model: what an action does to every faction |
| `trade.py` | commodity prices per base, which way each trade runs, and the margin between two of them |
| `serve.py` | local web view on 127.0.0.1:8731, six tabs, two of them with sub-tabs |
| `freelancer-map.jpg` | the Sirius sector chart, served at `/map.jpg` |
| `run.sh` | start the server and open a browser on it |

Everything new goes in its own file. `flvisits.py` supplies the primitives;
`wrecks.py` adds its own INI reader because loadouts repeat their `equip` and
`cargo` keys and the frozen reader collapses repeats.

## `flvisits.py` is frozen. Do not edit it.

Not to refactor it, not to tidy it, not to "improve" it, not to fix its style.
Frozen 2026-08-31 at the owner's request, and the reason is not sentiment:

It unpicks three undocumented formats in a row. FLS1 save encryption, BINI
binary INI, and PE string tables in the resource DLLs. On top of that it
resolves a **one-way** hash by brute force, hashing every nickname in the game
data and looking the result up, because the mapping cannot be inverted.

None of that is re-derivable by reading the code. The constants were found by
searching, then confirmed empirically against real saves, and several plausible
alternatives were tried and scored zero. A tidy-looking edit can therefore break
it silently: the script will still run, still print a report, and the report
will be wrong. That is the worst failure mode there is, because it looks like
success.

**Build new things beside it, in their own files.** Import from it, wrap it,
read its output. Do not touch it.

If a change is genuinely unavoidable, say plainly what breaks without it, get
the owner's go, and re-run the checks below first.

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

The edit was kept to the smallest shape that removes the duplicate rather than
adding a third copy of it: the rule moved to `docking.py` and both callers now
ask that. Eight lines changed in the frozen file, all of them in `main()`, none
in the decoding, the hash or the loaders.

Checked afterwards, against the same save, with the committed version of the
file and the thawed one side by side: 3430 object nicknames, 2188 visit
entries, **486 resolved by both**. Identical. That is the check that matters
here, because it is the one that would have gone quietly wrong.

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
  planet. 197 then narrows to 181 reachable and 164 dockable; `docking.py` owns
  that and says why. 164 rather than 167 because Tohoku's two and Alaska's one
  are excluded by name: both systems are story-gated and nothing in the data
  says so. That rests on the owner's knowledge of the game, not on evidence.
  An earlier note here cited the saves, which was wrong: Tohoku is M09 and
  Alaska is M11, the save is on Mission_05, so their absence means only that
  he has not reached them. `docking.py` carries the correction.

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
this document, not as something re-checkable. If you want it on disk, note a
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
the reason is in the data and the denominator is now 167, not 181.

The rule, and the three candidates that had to be eliminated to find it, are in
`docking.py`. It is not restated here, and it is not duplicated in `flvisits.py`
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

## Writing to the running game

The Speed tab changes cruise speed in a live Freelancer, and this is the only
part of the project that writes anything anywhere. It writes to process memory,
never to a save and never to a game file.

It exists because `CRUISING_SPEED` is a single global in `constants.ini`, read
once at startup, with no per-system or per-zone variant anywhere in the data:
the key appears in exactly one file of the 8370 under `DATA/`. Wanting 5000 in
open space and 500 in an asteroid field therefore cannot be expressed in the
game's own data at all.

Confirmed working on 2026-09-01 by writing 20.0 into a live game: the ship
slowed on the spot, no reload and no crash, and the owner then asked for the
tab. So the value is read per cruise burn, not cached when the ship spawns.

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
should say so rather than being "fixed" by loosening it.

## Systems are identified by nickname, never by display name

Found 2026-09-04 while adding the Routes sub-tab. Five system display names are
shared by more than one system: **Omicron Beta** is `Ew02` and `St02`, **Omicron
Major** is `St03`, `St03b`, `St02c` and `FP7_system`, and **Unknown** is `Ew05`
and `Ew06`.

Only one of each group has a market, so keying the trade selectors on labels
would have worked today, by luck, and broken the moment anything looked at the
single-player-only or multiplayer-only systems. `trade.py` rows therefore carry
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

## Dependency

`bini.py` lives in `../scripts/` and is shared with other work in this area. It
is not part of this project and is not frozen.
