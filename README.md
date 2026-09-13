# fl-visits

I recently reinstalled Freelancer and realized that FLHack and other things are great, but lack everything I need. Plus, I'll need more skills to run them on my freshly installed Linux, then build the companion myself.

So I made a companion app to make the gameplay more 2020s-ish.

**The Overview tab** is a data compilation from all the other tabs.

**Engine tab** lets you change some params (mostly speed) in-game and later save them to the corresponding data files. You can change cruise, trade lane and thruster speeds as well as trade lane wind-up and asteroid draw distance. Be careful with that - it may cause freezes on x6 and higher settings.

**Map tab** has 4 sub-tabs. Chart draws you an image file that you put in 'data/freelancer-map.jpg'. Best path shows you the best path from system to system. This was not thoroughly tested yet. Jobs sub-tab lists the bases that offer best paying bounties. Can be limited to the bases that you've docked with. Systems is the sub-tab that this companion was built around. It shows the bases and wrecks that you have or haven't found.

**Equipment tab** lets you filter the top guns available to you.

**Trade** also has sub-tabs. Market shows you the by-base or by-commodity filter with top destinations. If you have cargo on board, it will count the most profitable system to sell it all without needing to roam the whole Sirius sector. The Routes sub-tab is easiest described with "If you're going from New York to Dresden anyway, what would be the best commodity to buy in one system and sell in the other?" My second favorite tab.

**Reputation tab** gives you more insight on what factions will be pissed off by your friendly actions towards other factions. One of the most useful, but also one of the most raw tabs - I still can't wrap my head around how to make it usable. If you have any ideas, you're welcome to share them.

**Neural Net** is a compilation of Trent's diary, News and Rumors with the ability to mark any item read or important. I was always pissed off on how the neural net resets its position and I was always lost on where I was at the moment.

If, after all this you want to buy me a coffee, I'd be happy: https://ko-fi.com/greyvolcheg

And important disclaimer: this app has been coded by AI.

## Run it

```bash
./run.sh                         # start the server and open the page
python3 serve.py                 # web view on http://127.0.0.1:8731/
python3 fl.py                    # every command line it has
python3 fl.py visits <save.fl>   # bases, in the terminal
python3 fl.py wrecks <save.fl>   # wrecks, in the terminal
```

`run.sh` is the one-command version, three lines that pass everything through
to `serve.py --open`. Ctrl+C stops it. `run.cmd` is the same for Windows.

**It refuses a port somebody is already holding**, names it, and prints the
command that frees it. That refusal is in `serve.py` rather than in the script
because only `serve.py` knows whether it got the port: the script used to
probe, decide the port was free, start the server and never find out, which on
one occasion put a browser on an hour-old server and made a new tab look
missing.

`serve.py` follows the newest `AutoSave.fl` on its own and re-reads it every
five seconds, so you can leave the page open on a second screen while you play.
Pass a specific `Save*.fl` to follow that instead. Ctrl+C stops it. It listens
on localhost only.

**Click the save name in the header to find out which file that is.** It opens
the folder the save lives in, as text you can select, with a button that shows
it in the file manager. Worth having because the answer is six levels down a
Wine prefix and the server is the only party that knows which one it picked.

### Levels

```bash
python3 fl.py levels                            # the ladder as it stands
python3 fl.py levels --to 50 --worth 1160922100 # carry it past the vanilla cap
python3 fl.py levels --restore                  # back to .vanilla
```

**The whole level system is one file**, `DATA/MISSIONS/ptough.ini`: 39 rows of
`worth, level` from `0, 0` to `2409599, 38`. Current Level is which row your
worth has passed, Next Level Requirements is the next row minus your worth, and
`[Player] rank` in a save is only a cache of that lookup, so editing a save to
change level does nothing that survives a dock.

The game calls the section `PlayerToughnessScale`, so the same curve probably
also sets how tough the world thinks you are. Stretching the ladder should make
encounters harder as well as levels dearer. That is the name and the shape
talking, not a measurement.

### What the bots call you

```bash
python3 fl.py callsign --list                 # every word the game can say
python3 fl.py callsign --faction fc_bd --desig 29 --wing 6 --slot 6
python3 fl.py callsign --restore              # back to .vanilla
```

Also a box in the Engine tab. A callsign is three recorded vocabularies in a
row, `<faction word> <formation designator> <n>-<n>`: 48 words, 29 designators
and the numbers 0 to 20. "Freelancer Alpha 1-1" is one pick out of each, and
every one of them can be changed.

**No personal name is recorded anywhere in the game**, so a name cannot be
spoken however it is spelled. Yanagi and Susuki are formation designators, from
the same list as Alpha and Beta, which is why they get heard and taken for
names.

The engine picks these words for any ship with no formation, which in single
player is you and is also any NPC flying alone, so **you will occasionally hear
your own words on somebody else's radio**. It writes four sites in
`content.dll`, keeps a `.vanilla` copy, and lands the next time a save loads.

### Windows

**Written, never run.** Every platform-specific thing has two spellings and
picks one at import: where the game is, where the saves are, and how another
process's memory is reached. The Linux half is what this is developed and used
on and is the only half with any evidence behind it. The Windows half was
written against the Win32 documentation in one pass and **no line of it has
ever executed**. Reports of what broke are welcome.

```
py serve.py --open              or run.cmd
py fl.py proc                   the one command that tests the memory layer
python3 check_windows.py        struct layouts and symbols, runs anywhere
```

`fl.py proc` prints the pid, every loaded module with its base address, and
sixteen bytes read out of `common.dll`. It writes nothing. If it ends in
`read OK` the hard part works and the Engine tab should follow; if it does not,
it says which call failed. Everything that only reads files (all of it except
the Engine tab) needs none of that and should work as it does here.

What is known to be Linux-shaped and is not being fixed: `check_views.py`
shells out to `firefox --headless`, which will work if `firefox` is on PATH and
is a development tool either way. `bini.py` lives outside this repo, in a
`scripts/` folder two levels up; without it the first import fails with a
message saying exactly where it looked. A game installed under
`C:\Program Files (x86)` is not writable by a normal user, so `fl.py persist`,
`routetable`, `drawdist` and `newgame` will refuse with a message saying so:
an elevated shell or an install elsewhere is the answer.

Useful flags: `--all` includes what you have not found yet, `--loot` lists what
each wreck holds, `--port` moves the server, `--game DIR` points at a different
install.

The web page has seven tabs, three of which carry sub-tabs:

| Tab | Sub-tabs |
|---|---|
| **Overview** | none |
| **Engine** | none |
| **Map** | Systems, Chart, Jobs, Best Path |
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
it. Both levels start shut, and a house lays its systems out two abreast as soon
as there is room for two, which is about 1130px of page width. There is no
breakpoint in it: it measures the panel, not the window, so a browser sidebar or
a zoom level cannot leave it in one column by accident. The numbers and the two
checkboxes share one panel, not two stacked ones. Bases and wrecks used to be two tabs asking the same
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

**Set Best Path is not a button here any more.** It used to be: the game ships
two route tables and reads the duller one, `shortest_legal_path.ini` knowing
only jump gates where `systems_shortest_path.ini` includes holes, and five bytes
in three places swapped which one gets read.

**It could not work, and that is settled by flying it.** The game reads the
table once when a world loads, and `content.dll` and `server.dll` are reloaded
by that same load, which wipes the patch. So the only moment it can be applied
is after the read, and swapping a filename pointer does nothing to a table
already in memory. With the patch reading ON and all five bytes verified, the
game still routed Hokkaido to Tau-23 the gates-only way, five jumps through New
Tokyo, where two exist through Kyushu.

`fl.py routetable` does the job instead, by writing gates-only shortest paths
into the table the game actually reads; see **Map → Best Path**. The patcher is
still there as `fl.py bestpath` and is redundant: the table it would switch to
carries routes through jump holes, and the engine cannot fly one.

**ENABLE ALL** sits on the LIVE MEMORY banner and turns on the three switches
under it in one press: the lane wind-up, the HUD speed cap and the docking
takeover. It is idempotent, so pressing it twice reports what was already on
rather than toggling anything back off, which is the difference between it and
the per-box buttons. The knobs that carry a number are deliberately not in it:
cruise, the thrusters, lane speed and the takeover distance are settings, and
picking one on your behalf is not what enable means.


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

**Equipment** answers *which* gun should I be after. Pick guns or shields and
**every parameter is a column**, all nine of them for guns and seven for
shields. Hover a heading and a `×` appears to drop that column; once anything
is off, a `+ add a column…` select turns up beside the filters to put it back.
A column you are sorting or filtering on cannot be dropped and offers no `×`,
because an arrow pointing at a column that is not on screen is the table lying
about itself. Add the ones you care about as filters on top. Filters stack, and
**filtering never reorders**: that is what the column headings are for, and
clicking one twice turns it round. The default is hull DPS for guns and
capacity for shields.

**A favourite ignores every filter.** Click the star on any row and it stays in
the list whatever you narrow it to, in its proper place in the sort rather than
pinned on top, so it is a bench to measure candidates against. Favourites are
kept by the server in `data/marks.json`, beside the Neural Net's read marks, so
they survive a reload, a restart and a different browser. A favourited shield
does not appear in the gun table: the columns are different and the row would
mean nothing.

Two filters sit outside the parameter list, in the top row, because they are
the two you reach for first. **Name** is a plain substring. **System** means
"what does Colorado sell", which has no answer for a gun Colorado does not
sell, so a wreck-only gun like ARCHANGEL disappears from it.

**Only bases I have docked at** drops rows too, and until 2026-09-10 it did
not: it used to empty a row's dealer list and keep the row, so 187 of the 235
guns sat there with nothing under them. Ticked, you now get only what is sold
at a base you have actually been to, which takes wreck loot with it. On a save
with 30 bases docked that is 51 guns of 235 and 36 shields of 79.

Picking a system on a list already sorted by hull DPS is the top guns sold
there. On the command line the same question is
`fl.py equipment --kind guns --system li01 --top 10`, and the two must agree.

There was a DPS sub-tab that added weapons up into a loadout. It is gone at the
owner's call.

**Rank needed takes `=`, `<=` and `>=`** rather than a plain minimum, because
"at least rank 16" is not a question about anything: what you want to know is
what you can fly right now, and that is `<=` your rank. Every other numeric
parameter stays a minimum, which is how they are actually asked, and nobody
wants a gun with *at most* 400 hull DPS.

**Mount class takes `=`, `<=` and `>=`** too, because it is the one categorical
parameter that is really a number: your ship has a class 6 hardpoint and the
question is what fits it. On a shield the label carries the socket too, and
the comparison stays inside it: `fighter 6` and `elite 6` are different mounts
on the ship, not two sizes of one, so a comparison across them would offer gear
the ship cannot take.

Both are inclusive on purpose. `<= 6` is 145 guns to `= 6`'s 51 and `< 6`'s 94,
which is the same list read without having to remember whether the number you
typed counts.

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

**The list is what you can actually get, and every row says how.** There are
three ways: a dealer at a base you can dock at, a wreck, or shooting whoever is
flying it. That is 237 guns of 247 and 79 shields of 121, and the `where`
column reads a dealer count, *wreck*, or *off a ship*.

The 17 codenamed guns, ARCHANGEL through SILVER FIRE, are in wrecks, and for
them the expansion names the wreck: ARCHANGEL reads *the Volsung wreck,
Omega-41*. The two Nomad guns are the ones you take off a Nomad: no dealer, no
wreck, a 10% chance of surviving the kill as loot, and the two highest hull DPS
figures in the game at 2568 and 2543.

**Tick *also what nothing in the game gives you* for the rest.** Ten guns and
42 shields exist in the equipment files and are handed out by nothing at all:
Death's Hand Mk III, Reaper Mk III, the Nomad Prototype, Rowlett's Revenge and
friends. They are hidden by default because the tab answers "what can I get",
and they are one click away because an item that is simply missing cannot be
told apart from one the reader lost. Left in unconditionally they would take
the top of the shield list, where `npc_shield01_mark10` shows 10127 capacity
against the best buyable Adv. Brigandine at 289150 credits.

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
a repeat count. A bribe **sets** your standing to 0.6 instead of adding, so it
never appears once you are already above that, buying a second changes nothing,
and it is no help when the goal is to be hated. 41 of the 55 factions can be
bribed at all.

**The row says where to buy it**, as `2 of 14 bases`: bases you have docked at,
against every dockable base in Sirius that offers this bribe. Open the row and
the reachable ones are listed with their system and nav map cell, above the side
effects. Bases rather than bartenders, which is the count that used to sit
there: two bartenders in one bar is still one trip.

**Zero of fourteen is the answer worth having.** On the save this was built
against, 11 of the 41 bribable factions had no reachable bar at all: the
Rheinland Police will take 10000 credits at 25 stations and you have landed on
none of them. The row used to show a price and imply you could pay it.

Price is the same everywhere, so the list answers *where* and never *where
cheapest*: all 2386 `bribe` lines in `mbases.ini` read a flat 10000. Same shape
as equipment prices, and see the next paragraph for what the real charge is.

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

**Three commodities spoil, and the table marks them.** Alien Organisms and
Luxury Food carry `>>>HIGHLY PERISHABLE<<<` in the game's own infocard, MOX
carries `>>>PERISHABLE<<<`, and all three are the only commodities in the game
with a non-zero `decay_per_second`. The field and the banner pick out the same
three, which is why the badge is derived from the data rather than typed in. The
files do **not** say what spoiling costs you on a run, so nothing here pretends
to: the `run` figure stays a plain multiplication and the note says as much.
*Hide perishable* takes them out if you would rather not think about it.

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

**Map → Jobs** answers where the money is. A bar's job board shows you what it
is offering today and never what it is *capable* of offering, so the only way to
learn that one base pays sixteen times what your home station does is to fly
there and look. That ceiling is in the game files, and this is it:

| | |
|---|---|
| **best job** | what the richest faction on that board can offer at the top of its band |
| **floor** | the least any faction there can offer |
| **on board** | how many jobs hang up at once |
| **offered by** | who is standing in that bar with work |

What is actually pinned up when you walk in is drawn from between the two
numbers, so `best job` is a ceiling and not a promise.

**It opens on the systems you have opened**, which means a system holding at
least one base you have docked at. The bases in it you have *not* landed on are
the point: you already know the way there. The checkbox widens it to all 160
boards in Sirius, which is how you find out what is worth the trip. On this save
the ceiling inside reach is 9 001, and Planet Crete, Planet Malta, Ruiz Base and
Tripoli Shipyard pay 146 192 out in the Edge Worlds.

**Click a row for who is offering**, each faction with its own band and its
share of the draw. Trafalgar Base runs five: Junkers take 40% of what comes up,
Corsairs and Outcasts 20% each, Gaians and Mollys 10%.

**Two numbers are deliberately missing, and they are the two you would want
next.** What the job sends at you, and what the best of a full board comes to.
`npcranktodiff.ini` maps enemy rank and wing size to the same difficulty scale,
so the game plainly inverts it to pick your opposition, but the direction of
that inversion is not in the files, and neither is how the draw is spread inside
a band. Same rule as the perishable cargo on Routes: the page shows the game's
own figures and does not print a number that implies a model nobody can check.

**160 of the 164 dockable bases run a board.** Planet Primus, Planet Gammu and
Planet Toledo have nobody in the bar offering work, and Planet Sprague has an
offering faction but a board with no slots on it. `fl.py jobs --all` lists the
four and says which is which.

**Map → Best Path** works out the way from one system to another, and it exists
because the game's own answer is not the shortest one. Freelancer ships three
precomputed route tables and `fl.py bestpath` switches it to the one that knows
about jump holes; checked against that very table, over all 2079 pairs in it,
this is equal on 1502 and **shorter on 577, longer on none**. New York to New
London it routes in four jumps through Cortez where there are three through
Magellan, on a jump gate that has been there since 2003.

**Two routes, because they disagree on half the map.** Fewest jumps and least
flying part company on 49% of the pairs that have a route at all, so both are
drawn, and one line says so when they are the same. Each step is the system you
are standing in, the nav map cell, the thing to fly to, and whether it is a gate
or a hole.

**It starts from what you have found**, which is the jumps the save has recorded
on your nav map. A link counts as found when either of its two ends has been
seen: being shown the far side of a hole is knowing it is there. The checkbox
widens it to all 232 jumps in the game and marks every step your map will not
show you, so it doubles as a list of what would open up.

**Distance is raw flying between the jumps inside each system, in the game's own
metres, and it covers the middle systems only.** Where you are in the one you
leave and where you are going in the one you arrive in are not things a route
between two systems knows. **Trade lanes are not modelled** and the page says
so: they change real travel time completely, but that needs to know where the
lane runs and whether it is still standing, which the files do not settle.

**Five systems are a closed island.** The single-player-only Omicrons, `st01`
through `st03b`, join each other and nothing else, so the page says that rather
than pretending to search.

**And the routes can go into the game itself.** `fl.py routetable` writes them
into Freelancer's own tables, so its Set Best Path gives the same answers this
tab does:

```bash
python3 fl.py routetable            # what would change, changes nothing
python3 fl.py routetable --write
python3 fl.py routetable --revert   # back to the shipped table
```

**This is the only thing that can work, and the byte patch behind `fl.py
bestpath` is not.** That patch swaps which table the game reads, but the game
reads the table once when a world loads and the patch is wiped by that same
load, so it is always applied too late to matter. Flown and confirmed: with the
patch reading ON the game still routed Hokkaido to Tau-23 the gates-only way,
five jumps through New Tokyo, where two exist through Kyushu.

**Gates only, and that is the whole lesson.** An earlier version wrote
hole-inclusive routes into the table the game reads, and Set Best Path pointed
the course at the system origin, which in Hokkaido is a red dwarf. The engine
can only turn a hop into a waypoint when a jump **gate** makes it; with only a
hole it falls back to 0,0,0. The shipped table it reads has zero gateless hops
in 1225 rows, and that is a contract, not a coincidence.

So one file is written, `shortest_legal_path.ini`, at its own width: **136
routes shorter, none longer, none needing a hole, and none naming a system the
file did not already list.** New York to New London goes from four jumps to
three through Magellan, every hop a gate. The hole routes were never where the
improvement was.

Hole routes stay on this tab, which is a reader and needs no engine. There is
nothing to switch between: the game can only fly one of the two.

A `.vanilla` sits beside the file, the game reads it when a world loads, and
`--revert` puts it back.

**Neural Net** is one list over three sources, and the three chips are filters
on it rather than a switch between three pages. All three are on by default,
which is the combined view; turning one off takes its stream out. *Unread only*
applies across whatever is on, so the tab answers "what have I not read" without
asking it three times. Mark anything interesting or read; **the marks are kept
by the server**, in `data/marks.json`, not by the browser.

**The three share no clock and the panel says so instead of inventing one.**
Each stream is in its own true order and they sit one after another under a
heading each. The save's log carries no date at all, only its place in the file.
News is dated by the story state it broke at. Bar talk carries no date either,
but the save records the order you first docked at every base, so it is ranked
by which bar you walked into last: the most recent stop is at the top.

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

**403 filed items are 364 distinct ones.** 17 carry no headline, no text, no
category and no base at all, and every one of them debuts at `mission_end`:
placeholders, and they used to draw as empty boxes. Another 22 are exact
duplicates of an item already in the list, same headline and same text, filed
again under a second window and sometimes a different icon. A duplicate is
folded into the copy that broke first, taking the wider window and the union of
the bases, and the row says *FILED 2x* rather than eating one silently.
An item still inside its window says *ON THE WIRE*; one the story has moved past
says what it ran until, because "gone now" and "not yet" are different answers.
*On the wire now* narrows to the first kind.

A save's story state is `[StoryInfo] MissionNum`, an index into a table of 42
names that lives in `content.dll` and nowhere else. `data/story-states.txt` is
that table; `python3 fl.py story <save.fl>` prints where a save sits in it.

**BAR TALK** is what the people in the bars say, scoped to every base you have
docked at, grouped by system and base and attributed to the speaker and their
faction. It is real intelligence, not flavour: they name smuggling runs, where a
faction collects, and which fields are worth patrolling.

**Most recent stop first.** `base_visited` in the save is the docked bases in
the order you first docked at them, so a rumor's place is also a rough date: the
bar you were standing in last hour is at the top and Manhattan is at the bottom.
That order was established by measurement, not assumed, and `backend/common.py`
carries the two checks.

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
