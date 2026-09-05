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

The web page has six tabs, two of which carry sub-tabs:

| Tab | Sub-tabs |
|---|---|
| **Map** | Visits, Wrecks, Chart |
| **Equipment** | DPS, Search |
| Speed, Neural Net, Reputation | none |
| **Trade** | Data, Deltas, Routes |

Two levels rather than one longer strip because the pairs group naturally, and
because eight or nine buttons on one line stops being a strip and becomes a
menu. Which sub-tab you were last on is remembered per parent, so leaving Wrecks
for Trade and coming back returns to Wrecks.

**Visits** and **Wrecks** each have their own state for the
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

**`dockdist.py` is a command line only, and on purpose.** It owns docking, and
docking turned out to be two separate knobs that are easy to mistake for one.

```bash
python3 dockdist.py                 # what the running game is using
python3 dockdist.py --takeover 200  # docking takes over at 200 m
python3 dockdist.py --takeover-off  # remove the patch, game keeps running
python3 dockdist.py --vanilla       # everything back to stock
```

**`--takeover` is the one that does what you want.** It sets the distance at
which the game stops flying you and starts docking you, 1000 m stock. Lower it
and you cruise or thrust most of the way in instead of crawling the last
kilometre. **200** is where it settled after flying 100, 200, 400 and 600: below
that the approach is unplayable, and 200 is also what flhack picked on its own.
Lanes and jump gates share the number; stations and planets keep 600, because a
planet has a radius and 100 m from its centre is inside it.

This one is a code patch, not a value, because the distance lives in a
descriptor rather than a global. `inject.py` puts a 75-byte stub in the zero
padding at the end of `common.dll`'s `.text` and points two call sites at it.
Nothing is allocated and nothing on disk is touched.

The bare number argument is the other knob, `DOCK_DIST`, which only decides
whether the autopilot bothers with cruise at all. It is latched once when you
press dock and never rechecked, so changing it is invisible unless you dock from
between the old value and the new one. It is measured from the object's centre,
so subtract 495 to get the figure on your HUD for a lane.

Memory only, both of them. A relaunch puts everything back and nothing can be
left in a bad state. `dockdist.py` carries the disassembly.

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

**Equipment → DPS** adds up as many weapons as you like and shows what they do
per second, hull and shield side by side. `+ Add weapon` opens a search box over
the 247 guns a ship can carry; the picks survive a reload. It needs neither a
save nor a running game, since it is reading the game's own equipment files.

**Equipment → Search** answers the question DPS cannot: *which* gun should I be
after. Pick guns or shields, then add the parameters you care about. A parameter
is a filter **and** a column. Filters stack, and **filtering never reorders**:
that is what the column headings are for, and clicking one twice turns it round.
The default is hull DPS for guns and capacity for shields.

A parameter with few enough values is an exact pick rather than a minimum,
because some questions have no threshold in them. **Projectile speed is one:**
there are 14 muzzle velocities in the whole game and the real question is
"which guns do exactly 600", which no minimum can express. The list offers
500, 550, 600, 650, 700, 702, 750 and 800.

Those are the raw figures rounded to whole numbers, which is how the game shows
them: 600.0, 600.3 and 600.4 are three separate values in the files and one
answer to that question, so 600 gives all 51. The odd 702 is not a rounding
artefact but ten turrets sitting at exactly 701.8.

**Guns and turrets are separate**, as they must be: `hp_gun_special_6` and
`hp_turret_special_6` are different sockets on the ship. Until 2026-09-04 the
mount filter labelled both "6" and quietly merged 32 guns with 19 turrets. The
class is one parameter now and gun-or-turret is another, so either can be asked
on its own. It matters more than it sounds: nothing at 600 m/s is a turret, and
everything at 702 and 800 is.

Expanding a row says where the thing is sold. **The price is the same at every
dealer in the game**, so that list answers *where*, not *where cheapest*: the
multiplier is exactly 1.0 on all 10871 rows of `market_misc.ini` and no item's
differs between bases. The rank and reputation gates are the same everywhere
too, so they sit on the row rather than in the expansion.

**The list is what you can actually get**: sold at a dockable base, or sitting
in a wreck. That is 235 guns of 247 and 79 shields of 121. The 42 shields
dropped are NPC gear (30 have an `npc_` nickname, and no `npc_` item is sold
anywhere in the game) or have no `[Good]` at all and so no price and no dealer.
Left in, they take the top of the list: `npc_shield01_mark10` shows 10127
capacity where the best buyable shield, the Adv. Brigandine, is 289150 credits.
The 12 guns dropped are Death's Hand, Adv. Dissolver and Adv. Sunrail, all
mission or NPC weapons. Same argument as the undockable bases on the Trade tab.

The 17 codenamed guns, ARCHANGEL through SILVER FIRE, stay precisely because
they are in wrecks, and for them the expansion names the wreck: ARCHANGEL reads
*the Volsung wreck, Omega-41*. They lead the list, since wreck loot is the
hardest hitting in the game.

The docked filter narrows where you can buy, never what exists. A gun whose
every dealer is somewhere you have not been keeps its row and says so; 54 guns
are in that position on the current save.

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

**Reputation** answers what to actually do about a faction. The dropdown is
ordered by how each one currently feels about you, worst first, since the
faction worth acting on is the one at the bottom rather than the one filed
under A. Pick one and a target standing, enemy (-0.5), neutral (0) or friend (+0.5), and it lists every
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

**Trade → Data** looks a commodity up and lists every base that trades it,
dearest first. **Green marks the bases holding stock**, the only ones you can
buy at; the rest hold none and will only be sold to. A toggle narrows the list
to bases you have actually docked at, taken from the save.

Green is on that rather than on where you have docked because the sort alone
does not answer the question the tab is for. The cheapest row is not always one
you can buy at: gold's four cheapest bases, all in New London at 255, hold none
of it. So the run printed above the table is the cheapest *green* row to the
dearest row of any colour, and being docked somewhere is a filter, not a colour.

Price is the commodity's own price from `goods.ini` times the base's multiplier
in `market_commodities.ini`: gold is 425 a unit and the multipliers run from
0.001 to 100, which is how the same cargo fetches 255 at one base and 1530 at
another. Which way the trade runs comes from a flag the data is unanimous
about: of the 1994 rows, 844 read flag 0 with real stock and 1150 read flag 1
with a stock of exactly zero, and nothing breaks the pattern.

18 of the 178 markets are dropped because you cannot dock at them: the 15
mining platforms, and three `[Base]` entries that no object in space points at,
one of which is the cutscene-only Ithaca Research Station. A price you can never
reach is not information.

**Trade → Deltas** starts from the other end: from where the ship is standing
rather than from a commodity. Pick a base by name or by system, and it lists
only what that base actually has on the shelf, each line carrying the buy price,
the most anyone in the game will pay, the difference, and where that is. Click a
line for every base trading it, ordered by what it leaves you a unit.

The best price is on the goods list rather than one click away because the pick
is otherwise blind: a base with 20 kinds of cargo would need 20 clicks to find
out which one is worth carrying.

All 160 bases with a market sell at least one thing, so the picker is every one
of them. They hold between 1 and 20 kinds of cargo, 4 being usual. The docked
filter applies to both lists at once: with it on you get the bases you have been
to, and destinations are drawn from those same bases, so the figure on the goods
list is one you can actually collect. Anything else would promise a run the next
click then refuses to show.

Two runs to check it against, both straight out of the shipped data: Planet
Pittsburgh in New York sells exactly one thing, Boron at 120, worth 960 at LD-14
in Leeds, +840. Ruiz Base in Omicron Beta sells Alien Organisms at 100 against
2000 at three separate research stations, **+1900, the largest margin in the
game**.

**Trade → Routes** answers the question you have in flight, which neither of the
other two does. Data starts from a commodity; Deltas starts from the base under
your feet and will happily send you across the map. Routes takes a departure
system and a destination system and says what to put in the hold for a run you
are making anyway.

One line per commodity, not per pair of bases: the cheapest place to buy it at
this end against the dearest place to sell it at that one, which is by
definition the widest margin. New York alone has 12 market bases, so the
uncollapsed cross product would be mostly noise.

**Both ends may be the same system**, and often should be. Those same 12 New
York bases hold 21 profitable runs between them without a single jump: Cardamine
off Buffalo Base into Planet Manhattan is +270 a unit, 18,900 in a Sabre's hold.
Rows where the buy and the sell land on the same base are dropped, so a
single-system pick returns real runs rather than nonsense.

**`run` is the figure to read**: the margin times a full hold of the ship you
are actually flying, read from the save. New York → Leeds pays 840 a unit on
Boron, which in a Sabre's 70-unit hold is 58,800 credits a trip. The
multiplication is plain because every commodity in the game has `volume = 1.0`,
so a hold of 70 is 70 units of anything; `ships.py` carries the note, and the
column disappears rather than guessing if no ship can be read.

Only profitable lines are listed, with a count of what was dropped. There is no
green on this tab: every "from" base holds stock by construction, so the colour
that means *has it on the shelf* everywhere else would mark every row and
therefore mean nothing.

Three runs to check it against: New York → Leeds gives 14 of the 22 commodities
traded in both, led by Boron at 120 from Planet Pittsburgh against 960 at LD-14.
New York → New London gives 17 of 25, led by Optronics +644. Omicron Beta →
Cambridge gives 4 of 8, led by Alien Organisms +1900, and **that number has to
match what Deltas says for Ruiz Base**, because it is the same figure reached
from the other direction.

Two ways for a pair to come back empty, and they read differently because a
trader does different things about them: 13 of the 1806 ordered pairs trade no
commodity in common at all, and another 137 trade several but every one of them
cheaper at the far end. Hudson → Magellan is the first kind, Chugoku → Honshu
the second.

**Map → Chart** is the Sirius sector map, systems and every jump between them,
docked here so it is one click away while you are reading the other two. It is
`freelancer-map.jpg` in this folder, served at `/map.jpg`, and clicking it opens
the full 2560x1826 image in its own browser tab. The file is the community
"wingless" chart, renamed from `2560px-Freelancer_wingless.jpg` to fit the
vault's hyphen-lowercase rule.

It is the one response the server marks cacheable. Everything else here is a
live reading of a save or a running game and is sent `no-store`, but 840 KB that
will never change, on a page that redraws every five seconds, is not something
to re-send 12 times a minute. The panel is drawn once for the same reason:
rewriting its markup on every poll would throw away a decoded 2560px image and
decode it again.

**Neural Net** is the in-game log, readable while you fly. Mark an entry
interesting or read; the marks live in your browser and survive reloads. Sorting
is newest first with a button to flip it, and there is **no date column, because
the save holds no dates** at all, only the order the entries were written in.
*Personal only* narrows it to the pilot's diary, which the game heads with
`*PERSONAL ENTRY`, 66 of the 113 entries in a mid-campaign save. **It starts
on**, since the diary is the half worth reading; untick it for the objective
lines as well.

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
systems. 54 of them hold nothing, which is deliberate on the game's part, and
those count as emptied as soon as they are found: the game never sets the
looted bit on a wreck with no loot, so waiting for it would leave them open
forever. Found is found: a wreck counts once whether or not you emptied it, so
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

**Revealed bases carry their owner**, in the short name the game itself uses:
*Fort Bush* `Police (LI)`, *Yanagi Depot* `Junkers`, *Ruiz Base* `Outcasts`.
Hover for the full one. Revealed is the bucket where it matters, because those
are the bases you have not been to yet and whether the trip is worth making is a
reputation question before it is a distance one. All 164 dockable bases carry an
owner; there are 46 of them.

The house code appears only where the game's own short name is ambiguous. Four
police forces are all called just "Police", so those four read `Police (LI)`,
`Police (BR)`, `Police (KU)`, `Police (RH)`. The other 45 owners are printed
exactly as the game prints them.

**Coordinates** are the nav map cell and roughly where in it, `E6 C` or
`D6 UR`, the same notation the guides use. Wrecks carry them, and so do the
unknown bases. Docked and revealed stay inline runs: one you
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

**Restart the server after every edit.** The page is a string in the process,
so the browser keeps getting the old markup until the process is replaced.

**A bare page with no tabs means the script never ran at all.** The whole UI is
one inline `<script>`, so a *parse* error takes out every line of it, not just
the broken one, and what you see is the static HTML: a title, a stuck
subtitle, empty controls. It happened here on `let top = 'map'`. `window.top` is
a non-configurable property of the global object, and a global `let` or `const`
with a name like that is a SyntaxError, not a shadowing. `window`, `self`,
`location` and `document` are the others. The tab variable is called `topTab`
for exactly this reason and should stay that way.

Checking that class of failure needs a browser, not curl, because the server
serves the broken page perfectly happily:

```bash
firefox --headless --window-size=1400,900 --screenshot /tmp/shot.png \
  http://127.0.0.1:8731/
```

The shot is taken at the load event, before the first `fetch` comes back, so
"loading…" and an empty body in it are normal and prove nothing. **What it does
prove is whether the tab strip drew**, which is the part that dies with the
script.

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
