# fl-visits

Reads a Freelancer save game and reports what the player has found, grouped by
system. Own git repo; the history in this folder is the undo button.

| File | What |
|---|---|
| `flvisits.py` | save decoding, the nickname hash, game data loading, bases CLI. **Frozen, see below.** |
| `wrecks.py` | the 157 secret wrecks and their loot, as data and as a CLI |
| `serve.py` | local web view on 127.0.0.1:8731, tabs for both |

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

## What it was verified against

- Every one of the 301 hashes in a live save resolved to a nickname in the game
  data. Zero unresolved.
- The same brute force without lowercasing the nickname scores 40 of 301, so the
  match is not coincidence.
- The flag model held across a play session: flag 1 means the story revealed the
  base on the nav map, flags 30 and 31 mean the player actually docked. A base
  moved from the first bucket to the second while the player was flying, exactly
  as the model predicts.
- Denominator is the `[Base]` list in `universe.ini` (197), not the count of
  dockable space objects (250). A planet's mooring fixture is a second object
  pointing at the same base, so counting objects double counts every planet.

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

**The report shows it, and progress deliberately does not count it.** Found is
found: a wreck counts once for the totals and the percentage whether or not it
was emptied, because reaching it is the discovery. The bit only changes how the
line is drawn, `*` and amber for one still holding its loot against `+` and
green for one already stripped, plus a "still loaded" tally. That way the number
you are trying to drive to 157 never moves backwards, while the list still tells
you where there is something left to collect. An untouched wreck also shows its
loot without the checkbox, since that is cargo you can still go and get.

## Open: are the Asteroid Miner bases really dockable

The report counts them. Three checks in the data all say they can be docked at:
the space object carries `dock_with`, the base has a room file, and that file
declares `[BaseInfo] start_room = Deck` with the room present. They are distinct
bases that share one display name, which is the game's own naming, not a bug:
Dresden has three, Tau-31 three, Omega-7 and Tau-29 two each.

The owner reports the dock button is greyed out on them in play. Proof pending:
a screenshot once he reaches those systems. If it holds, the cause is almost
certainly reputation gating at run time, which is invisible in the files, and
the choice is then between dropping them from the denominator or giving them a
bucket of their own. The second is more useful once achievements exist.

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

## Dependency

`bini.py` lives in `../scripts/` and is shared with other work in this area. It
is not part of this project and is not frozen.
