---
type: research
project: computer-geek
status: done
created: 2026-10-06
---

# Routes and Best Path

## The jump graph (Map -> Best Path)

An `[Object]` carrying `goto = <system>, <object>, <tunnel>` is a jump: 232
across 52 systems, all two-way, each `goto` naming an object the same walk found.
84 gates, 140 holes of five kinds, two `nomad_gate`, six Dyson airlocks. The save
records seen jumps as it records bases, by `FLHash` of the nickname, at flag 1.

- **The nodes are jump objects, not systems.** New York holds a gate and a hole
  to Texas, and which one you want depends on where you came in. Start at any
  jump in the departure system for free; a jump costs one hop and no distance;
  flying to another jump in the same system costs the distance between them;
  arrival is the first jump landing in the destination.
- **Two costs, disagreeing on 49% of the 2182 reachable pairs**, so both are
  drawn: fewest jumps (ties broken on distance) and least flying (ties broken on
  jumps), one Dijkstra under two orderings. No flying route is longer than the
  fewest-jumps one; no jumps route has more hops than the least-flying one.
- **Distance covers the middle systems only, without trade lanes.** Both ends are
  picked by hand; lanes would need where each runs and whether it stands, which
  the files do not settle.
- **A link counts as found when either end has been seen.** 14 of 116 links on
  that day's save were marked at one end only. Each step still carries `found`
  for its own object.
- **Five systems are an island**: `st01`, `st02`, `st02c`, `st03`, `st03b`, the
  single-player Omicrons. 470 of the 2652 ordered pairs have no route; that is
  the data.

Against `UNIVERSE/systems_shortest_path.ini`: equal on 1502 of its 2079 pairs,
this tool shorter on 577, longer on none. New York to New London is four jumps in
the table, `li01 > li02 > iw04 > br02 > br01`, and three through Magellan,
`li01 > iw03 > br02 > br01`, every hop a gate. `fl.py jumps --check` is that
comparison and guards the graph. It reads `<name>.vanilla` when one exists,
because after `routetable.py` wrote the table it reported 2079 equal.

## How the game routes

- **The game reads its route table once, when the world loads**, and that load
  also reloads `content.dll` and `server.dll`, wiping any memory patch in them.
- `shortest_legal_path.ini` is gates only, and it is what Set Best Path reads in
  vanilla. `systems_shortest_path.ini` includes holes. Rows whose route has a hop
  no gate makes: legal 0 of 1225, systems 1440 of 2029.
- In `content.dll` the two filename strings sit at `0x70a828c`
  (`Universe\shortest_legal_path.ini`) and `0x70a82c4`
  (`Universe\systems_shortest_path.ini`); the slots at `+0x89512` and `+0x89492`
  point at them, and the router reads `+0x89512`.
- **flhack's five bytes do two things**: swap the two filename pointers (the low
  halves `0x8C` and `0xC4`), **and** set a type byte its own source comments as
  `mov byte [edi], 0x03 ; treat jump gates & holes the same`. On build v1.0
  `server.dll` holds 0x0A at that site, so the byte the patch changes is also
  the build fingerprint: "wrong build" and "already patched" are one check.
  This install matches flhack's build 10: `server.dll` 0x0A at RVA `0x1ACE3`,
  `content.dll` 0xC4 at `0x89492` (build 11's offsets give 0x24 and 0x90).
- **Without the type byte, a hop with no gate sends the course to the system
  origin.** 2026-09-13: Set Best Path from Battleship Matsumoto to Ohashi Border
  Station (Hokkaido to Shikoku) pointed into `Ku05_Sun`, a `sun_2000` at
  `[0, 0, 0]`, because the written route's first hop, Hokkaido to Kyushu, exists
  only as a hole.

## What `routetable.py` writes: two modes

The table and the five bytes move together; either alone is broken.

| mode | the game reads | table | the five bytes |
|---|---|---|---|
| `gates` | `shortest_legal_path.ini` | gates-only shortest paths, 136 shorter | out |
| `holes` | `systems_shortest_path.ini` | hole-inclusive, 1170 routes, 648 jumps saved | in, written into the DLL files by `bestpath.file_write` |

`--revert` restores both tables and the bytes. The switch is a box in the Engine
tab: the mode lives in the files the game reads, not in the game.

- `gates` writes into `shortest_legal_path.ini` **at that file's own width**.
  Over its 1225 rows: 136 shorter, 0 longer, 0 without a gates-only route, and 0
  naming a system the file does not list. That last count is 234 with holes
  allowed; widening the file to fit them is what broke it: on 2026-09-12 one
  hole-inclusive content went into both files (1723 of 2029 rows with a gateless
  hop). 366 rows change: 136 shorter, 230 equal in jumps with less flying.
  `--flying` asks for least distance outright.
- `content()` refuses a gateless hop in `gates` mode and a system the file does
  not list. Both refusals were proved by running the 2026-09-12 rule through
  them: 1096 and 234, nothing written.

## Why the file works and a memory patch cannot

flhack hooks the load: a `jmp` over `add esp, 0x214` at
`Freelancer.exe+0x1a81a8`, the instruction right after both DLLs load
(`81 c4 14 02 00` is there in this install). `Freelancer.exe` is never reloaded,
so the trampoline fires on every world load, re-finds both DLLs with
`GetModuleHandleA`, re-checks the build and re-applies the bytes before the
router reads. flhack writes nothing to disk, so the hook is its only option. This
tool may write files: bytes in the DLL files come back with every load. No stub,
no cave.

`live/bestpath.py` first wrote the five bytes into memory from a button
(2026-09-12). It read ON, the build matched, the swap direction was right, and
the game still routed Hokkaido to Tau-23 as
`Hokkaido > New Tokyo > Kyushu > Tau-29 > Tau-31`, the gates-only row, where the
holes table says `Hokkaido > Kyushu`. The patch arrived after the table was read
and died at the next load. A patch reading ON is not a patch working: flying the
route settled it. The memory control left the Engine tab that day;
`fl.py bestpath` remains.

The removed control also hid a collision: `backend/engine.py` and
`backend/bestpath.py` both offered a GET `bestpath`, and `tabs.py` merged them
with `dict.update`, so the later module won silently. `_table` now raises on a
repeated name, and the guard was proved to fire. An endpoint name is a tab's
address.
