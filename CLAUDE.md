# fl-visits

Reads a Freelancer save and reports what the player has found, grouped by
system; further tabs read the game's data and patch the game. Own git repo,
mirrored to GitHub: the history is the undo button. The game ran on `volkface`
and was uninstalled by 2026-10-06; the open questions in `docs/` wait for a
reinstall.

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
- **A five-second poll compares, never rebuilds** (see `docs/page.md`).

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
| `docs/` | what was measured and settled, one file per topic; see the table below |

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

The file was frozen in August and unfrozen on 2026-09-07: the check made the
edits safe, not the freeze. Every edit gets a line in `docs/saves.md`.

## Before touching a topic, read its doc

Each file holds what was measured, what was refuted, and what is still open.
Skipping it is how a refuted theory gets tried again.

| Topic | Read |
|---|---|
| the save format, visit flags, story state, the log, edits to `flvisits.py` | `docs/saves.md` |
| which bases count, the `Base` bug, wrecks and their loot | `docs/bases-and-wrecks.md` |
| factions, reputation model, news, rumors, commodities, equipment, job boards, bribes | `docs/game-data.md` |
| the jump graph, route tables, Best Path, flhack's bytes | `docs/routes.md` |
| writing process memory: cruise speed, docking, code injection, trade reputation | `docs/patching-memory.md` |
| writing game files: levels, draw distance, Nomad kills, callsign, new game, hand changes to the install | `docs/patching-files.md` |
| the page: design, polling, marks, layout, Equipment tab; starting the server | `docs/page.md` |
| Windows support and `check_windows.py` | `docs/windows.md` |

Several modules carry the same findings in their docstrings. Where a doc and a
docstring disagree, the doc names which one is stale.

## Dependency

`bini.py` lives in `../scripts/`, shared with the rest of this area. Its path is
derived from `backend/__init__.py`'s own location, two levels up, and that file
checks `bini.py` exists and says where it looked; without the check a checkout
without the vault beside it fails with `No module named 'bini'` and no path.
