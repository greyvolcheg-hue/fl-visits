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

The web page has two tabs, Visits and Wrecks, and one checkbox. Ticked, it shows
every system, the things still to find, and what the wrecks contain. Unticked,
it shows only progress.

## What the numbers mean

**Bases** fall into three buckets. *Docked* is where you have actually landed.
*Revealed* is a base the story has put on your nav map that you have never
visited. *Unknown* is the rest. The denominator counts only bases that exist in
space to be docked at, which is 181, not the 197 entries in the game's own
universe list: the other 16 are cutscene copies and story-only locations that no
save can ever record.

**Wrecks** are the 157 objects the game marks as secrets, spread over 33
systems. Found is found: a wreck counts once whether or not you emptied it, so
the total never goes backwards. The list still marks the difference, because the
game records it. `+` is stripped, `*` is found but still holding its loot, `-`
is not found yet, and an untouched wreck lists its cargo without the checkbox,
since that is the part you can still go and collect.

Both tabs sort the same way: least explored first, and everything you have not
started at the bottom in alphabetical order.

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
