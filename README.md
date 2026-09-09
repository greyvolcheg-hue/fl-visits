# fl-visits

Reads a Freelancer save game and tells you what you have found: which bases you
have docked at and which wrecks you have picked up, per system, with map
coordinates. It reads the save; it never writes to it.

## Run it

```bash
cd ~/Projects/40-computer-geek/fl-visits

./run.sh                         # start the server and open the page
python3 serve.py                 # web view on http://127.0.0.1:8731/
python3 fl.py                    # every command line it has
python3 fl.py visits <save.fl>   # bases, in the terminal
python3 fl.py wrecks <save.fl>   # wrecks, in the terminal
```

`run.sh` is the one-command version: it starts `serve.py`, waits for the port to answer instead of sleeping a guess, and opens a browser on the page. Ctrl+C
stops both. Any arguments it gets are passed straight through to `serve.py`.

`serve.py` follows the newest `AutoSave.fl` on its own and re-reads it every
five seconds, so you can leave the page open on a second screen while you play.
Pass a specific `Save*.fl` to follow that instead. Ctrl+C stops it. It listens
on localhost only.

Useful flags: `--all` includes what you have not found yet, `--loot` lists what
each wreck holds, `--port` moves the server, `--game DIR` points at a different
install.

The web page has seven tabs, three of which carry sub-tabs:

| Tab | Sub-tabs |
|---|---|
| **Overview** | none |
| **Engine** | none |
| **Map** | Systems, Chart |
| **Equipment** | Search |
| **Trade** | Market, Routes |
| Reputation, Neural Net | none |

Two levels because the pairs group naturally, and because eight or nine buttons
on one line stops being a strip and becomes a menu. Which sub-tab you were last
on is remembered per parent, so leaving Routes for Map and coming back returns
to Routes.

**The strip sticks to the top of the window.** The tables under it run to
hundreds of rows and the rumor list to nearly a hundred thousand pixels, so
losing the tabs means scrolling all the way back up to change anything.

**Overview** is the glance you take on undocking: how much of the sector you
have opened, where the campaign has got to, what is unfound in the system you
are standing in, what the base under your feet is worth carrying out of, and
whoever likes you least. Every panel is a doorway into the tab that owns the
full answer, and nothing on it is computed only there.

**Systems** is one tree: house, then system, then the bases and the wrecks in
it. Both levels start shut. Bases and wrecks used to be two tabs asking the same
question about the same place, so you read them side by side to plan one trip.

*Show all* ticked shows every system, the bases and wrecks still to find, and
what the wrecks hold; unticked, only what you have found. *Hide completed* drops
a system once every base in it is docked at **and** every wreck is stripped, so
a system whose wrecks are all found but not all emptied stays in the list.

**Both tabs open with both boxes ticked and every house folded**, so the first thing on screen is
a short list of what is left. The folding happens once per tab: open a house and the five-second
poll will not shut it again.

**Engine** is every control that reaches into the running game, split into what
is written to memory and what is written to a file, because those two have
completely different lifetimes and one panel should not let you confuse them.

It was a strip above the tab row for a few hours on 2026-09-07, following the
design canvas, and that did not survive contact: it polled the game from every
page, and being redrawn on every tick of that poll it kept losing clicks. It is
a tab, and a tab is polled only while you are looking at it.

A slider posts when you let go of it, never while you drag: `input` fires per
pixel and every one of those would be a write into a live game. The number
under your thumb follows the drag; the game hears about it once.

**Cruise speed** runs 300 to 5000 and applies to the next cruise burn with no
reload. It writes to the game's memory, never to a save or a file. Close the
game and the setting is gone; `constants.ini` is still the default. The tab
says so when no game is running, which is the usual state.

This exists because cruise speed is a single global read once at startup, with
no per-zone version anywhere in the game data, so "fast in open space, slow in
an asteroid field" is not expressible in the files at all.

**Thrusters** do the same for the six thrusters, from 120 to 420. These are
**bonuses added to your normal speed, not the speed itself**: setting 320 gives
you base plus 320. Vanilla is 120 on all six. All six are listed, so swapping thrusters needs no code change. Same rules as
cruise: memory only, gone when the game closes.

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
in the loaded copy of `constants.ini`. The address is followed from a pointer in the code, so it works on either build
of `common.dll` and checks itself: if what it points at is not a plausible speed, it refuses.

**Write to the game files** takes the cruise and thruster speeds you have set
live and puts them in `constants.ini` and `st_equip.ini`, so the next launch
starts with them. Safe to press while playing, since Freelancer reads both once
at startup; nothing changes until you relaunch. It backs each file up to
`.vanilla` the first time, never overwriting a backup that already exists, and
replaces atomically after checking the result decodes back to what was intended.

Trade lane speed and the HUD cap are **not** written to files, because they are
not in files to begin with.

**`fl.py dockdist` is a command line only, and on purpose.** It owns docking, and
docking turned out to be two separate knobs that are easy to mistake for one.

```bash
python3 fl.py dockdist                 # what the running game is using
python3 fl.py dockdist --takeover 200  # docking takes over at 200 m
python3 fl.py dockdist --takeover-off  # remove the patch, game keeps running
python3 fl.py dockdist --vanilla       # everything back to stock
```

**`--takeover` is the one that does what you want.** It sets the distance at
which the game stops flying you and starts docking you, 1000 m stock. Lower it
and you cruise or thrust most of the way in instead of crawling the last
kilometre. **200** is where it settled after flying 100, 200, 400 and 600: below
that the approach is unplayable, and 200 is also what flhack picked on its own.
Lanes and jump gates share the number; stations and planets keep 600, because a
planet has a radius and 100 m from its centre is inside it.

The distance lives in a descriptor, so this one is a code patch. `backend/live/inject.py` puts a 75-byte stub in the zero
padding at the end of `common.dll`'s `.text` and points two call sites at it.
Nothing is allocated and nothing on disk is touched.

The bare number argument is the other knob, `DOCK_DIST`, which only decides
whether the autopilot bothers with cruise at all. It is latched once when you
press dock and never rechecked, so changing it is invisible unless you dock from
between the old value and the new one. It is measured from the object's centre,
so subtract 495 to get the figure on your HUD for a lane.

Memory only, both of them. A relaunch puts everything back and nothing can be
left in a bad state. `backend/live/dockdist.py` carries the disassembly.

**Set Best Path through jump holes.** The game ships two route tables and routes
with the duller one: `shortest_legal_path.ini` knows only jump gates, while
`systems_shortest_path.ini` includes jump holes, which are often the shortcut.
Both have been in the install since 2003. The button swaps which one gets read.

```bash
python3 fl.py bestpath         # is it on, and which file each slot points at
python3 fl.py bestpath --on
python3 fl.py bestpath --off
```

Five bytes in three places, no injected code, nothing written to disk. The catch
is worth knowing before you rely on it: `content.dll` and `server.dll` are loaded
**when a save is loaded**, so the setting dies on every load and has to be
pressed again. flhack hooks the loader to avoid that; pressing the button again
is cheaper and hides less.

**Asteroid draw distance** scales `[Field] fill_dist` across the 153 field
definitions in `DATA/SOLAR/ASTEROIDS/`. Vanilla runs 1000 to 2500 with a median
of 1400, which is why a field reads as empty until you are nearly inside it. A
file change, so it lands the next time a system loads, backed up to `.vanilla`
and restorable.

Each field scales from **its own vanilla value**, so pressing 1.5x twice is
still 1.5x and never 2.25x.

Two things worth knowing before turning it up. Rocks fill a sphere, so 2x the
distance is roughly 8x the geometry, from a median 385 filled cubes to 3077, on
a single-threaded 2003 renderer. And the billboards are deliberately left alone:
`[AsteroidBillboards]` is a few hundred sprites scattered independently of the
`[Cube]` grid that places the real rocks, which is why a sprite winks out and a
rock appears somewhere else. More sprites makes that worse.

**Equipment** answers *which* gun should I be after. Pick guns or shields, then
add the parameters you care about. A parameter is a filter **and** a column.
Filters stack, and **filtering never reorders**: that is what the column
headings are for, and clicking one twice turns it round. The default is hull DPS
for guns and capacity for shields.

Two filters sit outside that list, in the top row, because they are the two you
reach for first. **Name** is a plain substring. **System** is the one filter
that drops a row rather than emptying it: picking Colorado means "what does
Colorado sell", which has no answer for a gun Colorado does not sell, so a
wreck-only gun like ARCHANGEL disappears from it. That is the opposite of the
docked-only checkbox beside it, which keeps the row and empties its dealer list
so the page can say "nowhere you have docked sells it". The two look alike and
mean different things.

Picking a system on a list already sorted by hull DPS is the top guns sold
there. On the command line the same question is
`fl.py equipment --kind guns --system li01 --top 10`, and the two must agree.

There was a DPS sub-tab that added weapons up into a loadout. It is gone at the
owner's call.

A parameter with few enough values is an exact pick instead of a minimum,
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
too, so they sit on the row instead of the expansion.

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
`HULL_DAMAGE_FACTOR` from `constants.ini`, read from the file, never assumed. Checked against five dealer screens, all matching to the integer the
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
faction worth acting on is the one at the bottom and never the one filed
under A. Pick one and a target standing, enemy (-0.5), neutral (0) or friend (+0.5), and it lists every
repeatable action that moves it the right way, with how many times. All of them,
never truncated: "1400 kills" is a real answer and a cut-off list would hide it.

Each row also says what the run costs elsewhere, because a plan to fix one
standing is a plan to wreck several others. `+n/-n` counts the factions it helps
and hurts and names the worst loss; clicking the row lists every faction it
moves, before and after, with the ones pinned at the +/-0.9 bound marked.

**Bribes** are in the same list, as a one-purchase row with a price instead of
a repeat count, plus how many bars will take it. A bribe **sets** your standing to 0.6 instead of adding, so it never appears once you are already above
that, buying a second changes nothing, and it is no help when the goal is to be
hated. 41 of the 55 factions can be bribed at all, at 610 bartenders.

Price is `100000 x (0.6 - current)`, so about 124k for a faction at -0.64 and
7.6k for one at +0.52. **That rate is derived and has never been measured.** The `bribe` lines
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

**Trade → Market** is one pipeline, and the axis picks which end of it you
start from, not which page you get.

    by commodity   pick a commodity  →  every base that trades it
    by base        pick a base  →  its shelf  →  every base that trades that,
                                                 measured against what you pay

**The last stage is the same list both ways, and that is a fact about the game
data rather than a design preference.** `market.trades` answers "every base
trading this commodity"; hand it the row you would buy at and each result gains
a `delta` column and the source base drops out. The order does not change and
cannot, because `delta` is `price` minus a constant, so sorting by margin and
sorting by price are the same sort. That is why one table serves both, and the
gain column is simply absent when there is nothing to measure from: a dash in
every cell of a column reads as missing data, and this is not missing, it is
not asked.

Choosing is one widget too. A commodity row says how many bases trade it, a
base row says how many kinds it stocks, and neither difference reaches the
search box. Two search widgets for one job was the real duplication, and it
outlived the two tabs it came from by a full rewrite.

**Green marks the bases holding stock**, the only ones you can buy at; the rest
hold none and will only be sold to. A toggle narrows everything to bases you
have actually docked at, and it applies to where you start as well as where you
go: offering a base the next step would then refuse to plan from is worse than
not offering it.

The picker shows the first 60 matches and says how many more there are. 160
bases in one list is a wall, not a list.

**Trade → Routes** answers the question you have in flight, which neither end
of Market does. By commodity starts from a commodity; by base starts from the
base under your feet and will happily send you across the map. Routes takes a departure
system and a destination system and says what to put in the hold for a run you
are making anyway.

One line per commodity, never per pair of bases: the cheapest place to buy it at
this end against the dearest place to sell it at that one, which is by
definition the widest margin. New York alone has 12 market bases, so the
uncollapsed cross product would be mostly noise.

**Both ends may be the same system**, and often should be. Those same 12 New
York bases hold 21 profitable runs between them without a single jump: Cardamine
off Buffalo Base into Planet Manhattan is +270 a unit, 18,900 in a Sabre's hold.
Rows where the buy and the sell land on the same base are dropped, so a
single-system pick returns real runs and nothing degenerate.

**`run` is the figure to read**: the margin times a full hold of the ship you
are actually flying, read from the save. New York → Leeds pays 840 a unit on
Boron, which in a Sabre's 70-unit hold is 58,800 credits a trip. The
multiplication is plain because every commodity in the game has `volume = 1.0`,
so a hold of 70 is 70 units of anything; `backend/game/ships.py` carries the note, and the
column disappears rather than guessing if no ship can be read.

Only profitable lines are listed, with a count of what was dropped. There is no
green on this tab: every "from" base holds stock by construction, so the colour
that means *has it on the shelf* everywhere else would mark every row and
therefore mean nothing.

Three runs to check it against: New York → Leeds gives 14 of the 22 commodities
traded in both, led by Boron at 120 from Planet Pittsburgh against 960 at LD-14.
New York → New London gives 17 of 25, led by Optronics +644. Omicron Beta →
Cambridge gives 4 of 8, led by Alien Organisms +1900, and **that number has to
match what Market says for Ruiz Base**, because it is the same figure reached
from the other direction.

Two ways for a pair to come back empty, and they read differently because a
trader does different things about them: 13 of the 1806 ordered pairs trade no
commodity in common at all, and another 137 trade several but every one of them
cheaper at the far end. Hudson → Magellan is the first kind, Chugoku → Honshu
the second.

**Map → Chart** is the Sirius sector map, systems and every jump between them,
docked here so it is one click away while you are reading the other two.

**No chart ships with this repo.** The good ones are fan-made and not mine to
redistribute. Save any sector map as `data/freelancer-map.jpg` and
the tab picks it up; until then it says so. The community "wingless" chart is
the one this was built against.

It is the one response the server marks cacheable. Everything else here is a
live reading of a save or a running game and is sent `no-store`, but an image that
will never change, on a page that redraws every five seconds, is not something
to re-send 12 times a minute. The panel is drawn once for the same reason:
rewriting its markup on every poll would throw away a decoded 2560px image and
decode it again.

**Neural Net** carries three sources behind three chips, labelled rather than
merged because they do not behave alike. Mark anything interesting or read; the
marks live in your browser and survive reloads.

**SAVE** is the in-game log, readable while you fly. Sorting is newest first
with a button to flip it, and there is **no date column, because the save holds
no dates** at all, only the order the entries were written in. *Personal only*
narrows it to the pilot's diary, which the game heads with `*PERSONAL ENTRY`.
**It starts on**, since the diary is the half worth reading; untick it for the
objective lines as well.

An objective line like "Meet Juni on Planet Manhattan%M" is not corruption and
is no longer printed that way. The `type` on a log substitution is the ASCII
code of the placeholder's letter, so `%M` takes the parameter of type 77 and
the entry reads "Start scanning nearby ships / Scan nearby ships and look for
anything suspicious". Where no parameter of that type exists, the detail is
empty and the placeholder is dropped.

**NEWS** is the wire, and it is **the one thing here that genuinely appears as
you play**. All 403 items in `news.ini` carry `rank = <from state>, <to state>`,
a pair of story states, and the tab shows everything whose window has opened,
newest debut first. 223 of them have broken by mission 3 and 385 by mission 13.
An item still inside its window says *ON THE WIRE*; one the story has moved past
says what it ran until, because "gone now" and "not yet" are different answers.
*On the wire now* narrows to the first kind.

A save's story state is `[StoryInfo] MissionNum`, an index into a table of 42
names that lives in `content.dll` and nowhere else. `data/story-states.txt` is
that table; `python3 fl.py story <save.fl>` prints where a save sits in it.

**RUMORS** is what the people in the bars say, scoped to every base you have
docked at, grouped by system and base and attributed to the speaker and their
faction. It is real intelligence, not flavour: they name smuggling runs, where a
faction collects, and which fields are worth patrolling.

**They never unlock.** All 7803 rumor lines in `mbases.ini` carry the same wide
open window, so every one of them is available from the first minute of a new
game. What changes is where you have been, and the panel says so rather than
letting you wait for one that never comes.

Mission dialogue is not here and cannot be: a `[Dialog] Line` in a mission
script names a `.utf` audio asset, and Freelancer ships no subtitles for
in-space comms. There is no text to show.

## What the numbers mean

**Bases** fall into three buckets. *Docked* is where you have actually landed.
*Revealed* is a base the story has put on your nav map that you have never
visited. *Unknown* is the rest. The denominator is 164 and never the 197 entries in
the game's own universe list: 16 are cutscene copies and story-only locations
that no save can ever record, 15 are the Asteroid and Gas Miners, which look
dockable in the data but refuse in play, and 3 are in Tohoku and Alaska,
which are story-gated. `backend/game/bases.py` explains how each group is told apart, and
is honest that the last three are the one exclusion no rule in the data
produces, and that they rest on knowing the game and on nothing
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

Systems are alphabetical inside their house. Two tabs once sorted by two
different notions of progress, most bases left on one and fullest first on the
other, and neither survived the merge: one tree can only have one order, and a
name is the one key you can aim at without reading the list first.

Both levels fold. Click a house heading or a system card to open it, or use
Collapse all and Expand all on the houses.

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

**`backend/game/flvisits.py` is the delicate one.** It decodes three undocumented formats and resolves
a one-way hash by brute force; a tidy-looking edit can break it silently and
still print a plausible report. See `CLAUDE.md` for the rule and for what
clears it.

**Restart the server after every edit.** The page is a string in the process,
so the browser keeps getting the old markup until the process is replaced.

**A bare page with no tabs means the script never ran at all.** The whole UI is
one inline `<script>`, so a *parse* error takes out every line of it, and never only
the broken one, and what you see is the static HTML: a title, a stuck
subtitle, empty controls. It happened here on `let top = 'map'`. `window.top` is
a non-configurable property of the global object, and a global `let` or `const`
with a name like that is a SyntaxError, not a shadowing. `window`, `self`,
`location` and `document` are the others. The tab variable is called `topTab`
for exactly this reason and should stay that way.

Checking that class of failure needs a browser: curl cannot, because the server
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
