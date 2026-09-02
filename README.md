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

The web page has five tabs. Visits and Wrecks each have their own state for the
checkbox: ticked, it shows every system, the things still to find, and what the
wrecks contain; unticked, only progress. Both group their systems by house,
Liberty through Edge Worlds, with a running count per house.

**Speed** changes the cruise speed of the running game, from 300 to 10000, and
it applies to the next cruise burn with no reload. It is the one thing here that
writes rather than reads, and it writes to the game's memory, never to a save or
a file. Close the game and the setting is gone; `constants.ini` is still the
default. The tab says so when no game is running, which is the usual state.

This exists because cruise speed is a single global read once at startup, with
no per-zone version anywhere in the game data, so "fast in open space, slow in
an asteroid field" is not expressible in the files at all.

**Thrusters** does the same for the six thrusters, from 120 to 1000. These are
**bonuses added to your normal speed, not the speed itself**: setting 300 gives
you base plus 300. Vanilla is 120 on all six. All of them are listed rather than
just the one fitted, so swapping thrusters needs no code change. Same rules as
Speed: memory only, gone when the game closes.

**DPS** adds up to five weapons and shows what they do per second, hull and
shield side by side. `+ Add weapon` opens a search box over the 247 guns a ship
can carry; the picks survive a reload. It needs neither a save nor a running
game, since it is reading the game's own equipment files.

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

**Neural Net** is the in-game log, readable while you fly. Mark an entry
interesting or read; the marks live in your browser and survive reloads. Sorting
is newest first with a button to flip it, and there is **no date column, because
the save holds no dates** at all, only the order the entries were written in.
*Personal only* narrows it to the pilot's diary, which the game heads with
`*PERSONAL ENTRY`, 66 of the 113 entries in a mid-campaign save.

## What the numbers mean

**Bases** fall into three buckets. *Docked* is where you have actually landed.
*Revealed* is a base the story has put on your nav map that you have never
visited. *Unknown* is the rest. The denominator is 167, not the 197 entries in
the game's own universe list: 16 are cutscene copies and story-only locations
that no save can ever record, and 15 are the Asteroid and Gas Miners, which look
dockable in the data but refuse in play. `docking.py` explains how they are
told apart.

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
`D6 UR`, the same notation the guides use. The cell is reliable. The `UR`/`C`
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
