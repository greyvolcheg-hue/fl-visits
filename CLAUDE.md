# fl-visits

Reads a Freelancer save game and reports which bases the player has docked at,
grouped by system. Own git repo; the history in this folder is the undo button.

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

## Dependency

`bini.py` lives in `../scripts/` and is shared with other work in this area. It
is not part of this project and is not frozen.
