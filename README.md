# fl-visits

Reads a Freelancer save game and tells you what you have found: which bases you
have docked at and which wrecks you have picked up, per system, with map
coordinates. It reads the save; it never writes to it.

## Run it

```bash
cd ~/Projects/40-computer-geek/fl-visits

./run.sh                         # start the server and open the page
python3 serve.py                 # web view on http://127.0.0.1:8731/
python3 flvisits.py <save.fl>    # bases, in the terminal
python3 wrecks.py <save.fl>      # wrecks, in the terminal
```

`run.sh` is the one-command version: it starts `serve.py`, waits for the port
to answer rather than sleeping a guess, and opens a browser on the page. Ctrl+C
stops both. Any arguments it gets are passed straight through to `serve.py`.

`serve.py` follows the newest `AutoSave.fl` on its own and re-reads it every
five seconds, so you can leave the page open on a second screen while you play.
Pass a specific `Save*.fl` to follow that instead. Ctrl+C stops it. It listens
on localhost only.

Useful flags: `--all` includes what you have not found yet, `--loot` lists what
each wreck holds, `--port` moves the server, `--game DIR` points at a different
install.

The web page has six tabs. Visits and Wrecks each have their own state for the
two checkboxes. *Show all* ticked shows every system, the things still to find,
and what the wrecks contain; unticked, only progress. *Hide completed* drops the
systems with nothing left in them, which on Visits means every base docked at
and on Wrecks means every wreck stripped, so a system whose wrecks are all found
but not all emptied stays in the list. Both tabs group their systems by house,
Liberty through Edge Worlds, with a running count per house.

**Both tabs open with both boxes ticked and every house folded**, so the first
thing on screen is a short list of what is left rather than everything you have
already done. The folding happens once per tab: open a house and the five-second
poll will not shut it again.

**Speed** changes the cruise speed of the running game, from 300 to 5000, and
it applies to the next cruise burn with no reload. It is the one thing here that
writes rather than reads, and it writes to the game's memory, never to a save or
a file. Close the game and the setting is gone; `constants.ini` is still the
default. The tab says so when no game is running, which is the usual state.

This exists because cruise speed is a single global read once at startup, with
no per-zone version anywhere in the game data, so "fast in open space, slow in
an asteroid field" is not expressible in the files at all.

**Thrusters** does the same for the six thrusters, from 120 to 420. These are
**bonuses added to your normal speed, not the speed itself**: setting 320 gives
you base plus 320. Vanilla is 120 on all six. All of them are listed rather than
just the one fitted, so swapping thrusters needs no code change. Same rules as
Speed: memory only, gone when the game closes.

**Trade lanes** sets the speed inside a lane, 2500 (vanilla) to 10000. This one
is not in any data file at all: `constants.ini` has no key for it, the
`Trade_Lane_Ring` archetype has none, and `[TradeLane] basic_trade_lane_eq`
carries only timings and ring spin. It is a constant inside `common.dll`.

Picking a speed also sets the **wind-up to near-instant**, because the two are
one setting in practice: at the stock rate of 0.125 a ship spends most of a
short lane still accelerating, so a higher number on its own is barely felt.
There is a toggle if you want the stock ramp back.

Deceleration is deliberately left alone. flhack changes that too, but by
injecting a code stub that holds full speed until 90% through the ring, and
injecting code needs executable memory allocated inside the game. Changing a
number does not.

Beside it, **the HUD refuses to print a speed over 999**, so raising the lane
speed without raising that shows a dash instead of a number. The same panel
lifts it to 9999.

Addresses for both come from [flhack](https://github.com/adoxa/flhack) by Jason
Hood, whose source settles what a memory scan cannot: an earlier attempt here
found a lone 2500.0 near the cruise constant and it was the wrong one, sitting
in the loaded copy of `constants.ini`. The address is followed from a pointer in
the code rather than hardcoded, so it works on either build of `common.dll` and
checks itself: if what it points at is not a plausible speed, it refuses.

**Write to the game files** takes the cruise and thruster speeds you have set
live and puts them in `constants.ini` and `st_equip.ini`, so the next launch
starts with them. Safe to press while playing, since Freelancer reads both once
at startup; nothing changes until you relaunch. It backs each file up to
`.vanilla` the first time, never overwriting a backup that already exists, and
replaces atomically after checking the result decodes back to what was intended.

Trade lane speed and the HUD cap are **not** written to files, because they are
not in files to begin with.

**Asteroid draw distance** scales `[Field] fill_dist` across the 153 field
definitions in `DATA/SOLAR/ASTEROIDS/`. Vanilla runs 1000 to 2500 with a median
of 1400, which is why a field reads as empty until you are nearly inside it. A
file change, so it lands the next time a system loads, backed up to `.vanilla`
and restorable.

Each field scales from **its own vanilla value, not from wherever it is now**,
so pressing 1.5x twice is still 1.5x rather than 2.25x.

Two things worth knowing before turning it up. Rocks fill a sphere, so 2x the
distance is roughly 8x the geometry, from a median 385 filled cubes to 3077, on
a single-threaded 2003 renderer. And the billboards are deliberately left alone:
`[AsteroidBillboards]` is a few hundred sprites scattered independently of the
`[Cube]` grid that places the real rocks, which is why a sprite winks out and a
rock appears somewhere else. More sprites makes that worse, not better.

**DPS** adds up as many weapons as you like and shows what they do per second,
hull and shield side by side. `+ Add weapon` opens a search box over the 247
guns a ship can carry; the picks survive a reload. It needs neither a save nor
a running game, since it is reading the game's own equipment files.

The `hull` and `shield` columns are damage per shot and `rate` is shots per
second, all three printed the way the dealer screen prints them, so you can
check a row against the game directly. `refire` is the same rate as a delay in
seconds, which is what the file actually stores.

Shield damage per shot is `hull_damage x 0.5 + energy_damage`, where the 0.5 is
`HULL_DAMAGE_FACTOR` from `constants.ini`, read from the file rather than
assumed. Checked against five dealer screens, all matching to the integer the
game prints:

| weapon | hull | shield | game says |
|---|---|---|---|
| Adv. Starbeam | 18.4 | 18.4 x 0.5 + 0 = 9.2 | 18 / 9 |
| Heavy Starbeam | 22.4 | 22.4 x 0.5 + 0 = 11.2 | 22 / 11 |
| Adv. Skyrail | 121.2 | 121.2 x 0.5 + 0 = 60.6 | 121 / 60 |
| Stunpulse | 4.6 | 4.6 x 0.5 + 153 = 155.3 | 4 / 155 |
| Adv. Stunpulse | 5.6 | 5.6 x 0.5 + 186.8 = 189.6 | 5 / 189 |

The game truncates for display. Both terms are needed: `energy_damage` alone
gives 153 and 186 for the Stunpulses, and hull alone gives 2.3 for a weapon
sold as an anti-shield gun. Note that "Energy Usage" on the dealer screen is a
third field, `power_usage`, which is what a shot costs your own ship.

Station and battleship fixtures are left out: 190 of the 437 damaging guns
cannot be mounted on a ship, and they are where the confusing name clashes live,
five different guns called "Battleship Defense Turret" from 82 to 1060 DPS.

The figures are the weapon's own. Freelancer also carries a weapon-type against
shield-type table in `weaponmoddb.ini`, worth 0.8 to 1.2, and this deliberately
ignores it: putting it in would make every number depend on what the target
happens to be flying.

**Reputation** answers what to actually do about a faction. Pick one and a
target standing, enemy (-0.5), neutral (0) or friend (+0.5), and it lists every
repeatable action that moves it the right way, with how many times. All of them,
never truncated: "1400 kills" is a real answer and a cut-off list would hide it.

Each row also says what the run costs elsewhere, because a plan to fix one
standing is a plan to wreck several others. `+n/-n` counts the factions it helps
and hurts and names the worst loss; clicking the row lists every faction it
moves, before and after, with the ones pinned at the +/-0.9 bound marked.

**Bribes** are in the same list, as a one-purchase row with a price instead of
a repeat count, plus how many bars will take it. A bribe **sets** your standing
to 0.6 rather than adding to it, so it never appears once you are already above
that, buying a second changes nothing, and it is no help when the goal is to be
hated. 41 of the 55 factions can be bribed at all, at 610 bartenders.

Price is `100000 x (0.6 - current)`, so about 124k for a faction at -0.64 and
7.6k for one at +0.52. **That rate is derived, not measured.** The `bribe` lines
in `mbases.ini` all read a flat 10000, all 2386 of them, so the engine computes
the real figure; flhack's flexible-bribe options price +0.3, -0.6 and -0.4 at
30000, 60000 and 40000, which agree on 100000 a point. Worth checking against a
bartender before trusting it to the credit. Bribes spread through empathy like
anything else, which is why flhack has a costs-double option to switch that off.

The model is `DATA/MISSIONS/empathy.ini`: an action against a faction moves your
standing with it by that event's delta and with everyone else by
`delta x empathy_rate`. All four events are scored, 55 factions x 4 = 220
actions, and the abort rows are not filler: aborting a mission for an enemy of
your target raises your standing with the target, since abortion is negative to
the faction offering it and the empathy rate between enemies is negative too.

**Neural Net** is the in-game log, readable while you fly. Mark an entry
interesting or read; the marks live in your browser and survive reloads. Sorting
is newest first with a button to flip it, and there is **no date column, because
the save holds no dates** at all, only the order the entries were written in.
*Personal only* narrows it to the pilot's diary, which the game heads with
`*PERSONAL ENTRY`, 66 of the 113 entries in a mid-campaign save.

## What the numbers mean

**Bases** fall into three buckets. *Docked* is where you have actually landed.
*Revealed* is a base the story has put on your nav map that you have never
visited. *Unknown* is the rest. The denominator is 164, not the 197 entries in
the game's own universe list: 16 are cutscene copies and story-only locations
that no save can ever record, 15 are the Asteroid and Gas Miners, which look
dockable in the data but refuse in play, and 3 are in Tohoku and Alaska,
which are story-gated. `docking.py` explains how each group is told apart, and
is honest that the last three are the one exclusion no rule in the data
produces, and that they rest on knowing the game rather than on anything
checkable in the files.

**Wrecks** are the 157 objects the game marks as secrets, spread over 33
systems. Found is found: a wreck counts once whether or not you emptied it, so
the total never goes backwards. The list still marks the difference, because the
game records it. `+` is stripped, `*` is found but still holding its loot, `-`
is not found yet, and an untouched wreck lists its cargo without the checkbox,
since that is the part you can still go and collect.

The two tabs sort differently, on purpose. **Visits** is a to-do list: most
bases left first, so the system with the most still to find heads it, then the
systems you have finished, then the ones you have never opened, both
alphabetically. Note that a system you have never opened has the most left of
all, and it still goes to the bottom: not started and finished are different
kinds of nothing and they sit at opposite ends. **Wrecks** is a record of what
you have found, so the fullest systems lead.

Houses fold. Click a heading to collapse it, or use Collapse all and Expand all;
each tab remembers its own folds and its own checkbox.

**Coordinates** are the nav map cell and roughly where in it, `E6 C` or
`D6 UR`, the same notation the guides use. Wrecks carry them, and so do the
unknown bases. Docked and revealed stay plain comma-separated runs: one you
have flown to, the other the story has already marked on your nav map. The cell is reliable. The `UR`/`C`
part is a hint: it agrees with the GameFAQs wrecks FAQ about three times in
four, which is as well as two people eyeballing "upper right" ever agree.

## Traps

**`AutoSave.fl` moves under your feet.** It changes while you fly, so two runs a
minute apart legitimately disagree. Test against a fixed `Save*.fl`.

**The game files and the save can live in different Wine prefixes.** On this
machine the install sits in an abandoned Proton prefix while play happens in a
win32 one. `serve.py` searches sibling prefixes and takes the freshest save, so
it copes, but do not assume the two paths are related.

**`flvisits.py` is frozen.** It decodes three undocumented formats and resolves
a one-way hash by brute force; a tidy-looking edit can break it silently and
still print a plausible report. See `CLAUDE.md` for the rule and for what
clears it.

## How it works

The save is XOR-encrypted (`FLS1`), and inside it every place you have been is a
line like `visit = 2724680666, 31`. The number is a hash of the object's
nickname and the hash is one-way, so the mapping is built backwards: every
nickname in the game's data is hashed and looked up. All 301 hashes in the first
save tested resolved that way.

The game's data files are BINI, a binary INI format, decoded by `bini.py` in
`../scripts/`. Display names come out of the string tables in the game's
resource DLLs.

`CLAUDE.md` in this folder holds the rest: what the flags mean, what is still
unknown, and what not to touch.
