---
type: research
project: computer-geek
status: done
created: 2026-10-06
---

# Changing the running game: memory

The Engine tab has two halves: process memory, and GAME FILES. Memory writes
last until the game closes; the files are the defaults.

## Cruise speed

`CRUISING_SPEED` is one global in `constants.ini`, read once at startup, in
exactly one of the 8370 files under `DATA/`: 5000 in open space and 500 in an
asteroid field cannot be expressed in data. Writing 20.0 into a live game on
2026-09-01 slowed the ship on the spot, without reload or crash, so the value is
read per cruise burn.

- **Never hardcode an address.** `common.dll` loads somewhere else each run.
  `speed.py` finds the value by the three floats after it, `5.0, 3.0, 0.25`, one
  hit in the whole address space. Searching for the speed itself fails: `1000.0`
  matched 6948 places.
- **Two kinds of address.** `speed.py` scans, because `CRUISING_SPEED` sits in a
  loaded copy of `constants.ini`. `tradelane.py` and `dockdist.py` use flhack's
  addresses (Jason Hood, 2014; source was at `~/Downloads/flhack/`) inside
  `common.dll`, resolved against the module base from `/proc/<pid>/maps`. A scan
  was tried first and found a lone 2500.0 that was a CommConsts value. Both
  modules read the float first and refuse an implausible value, which catches a
  wrong build or a moved address.
- Those addresses are in `.rdata`, read-only in the process. `/proc/<pid>/mem`
  bypasses page protection, so no `mprotect` is needed (flhack needs one on
  Windows).
- `kernel.yama.ptrace_scope` is 0 on `volkface`, so no privileges beyond the same
  user are needed. Where it is not 0 this stops working and must say so; never
  "fix" it by loosening the setting.
- **Read `/proc/<pid>/mem` frugally.** `volkface` has 7.6 GB and sits at a few
  hundred MB free with the game up. The first `find_scratch` pulled whole
  mappings into Python and walked them byte by byte, and the desktop stalled. It
  now reads 1 MB chunks, matches with `bytes.find` and stops at the first hit:
  0.1 s and 14 MB.

## Docking: cruise distance and takeover (2026-09-05)

**There is no docking distance in the game's data.** All 1252 INI files under
`DATA/`, searched for keys containing `dock`, give `docking_sphere` and
`dock_with` on objects and `act_lockdock` and friends in mission scripts, nothing
global. `Trade_Lane_Ring` in `solararch.ini` has no `docking_sphere` (`jumpgate`
has 225, `jumphole` 150); `constants.ini` has nothing.

- **Whether the autopilot cruises to a dock** is a float in `common.dll`:

      0x62fe171  d8 1d c0223a06   fcomp dword [0x63a22c0]   ; 1750.0

  In the shipped file and the running game. It is flhack's `ADDR_DOCK_DIST10`,
  "Cruise to dock from". Four instructions read it: this `fcomp` and three `fmul`
  about 1250 bytes earlier, so changing it moves more than the cut point. The
  compare is gated by `[esi+0x365]`, cleared right after, so the answer is
  latched once when the dock is ordered. At any real trade lane range 1750 and
  300 both answer "cruise": moving it changed nothing anyone could feel.
- Entering a trade lane is a dock: flhack's help says the proximity radius
  default of 495 "is that used by Trade Lanes". That was the owner's lead.
- **Where docking takes over is a code patch, never a number**: `[ebp+0x50]`, a
  descriptor field loaded at `0x62fe758`, so the only place to change it is the
  instruction that reads it. flhack calls it "Closer docking";
  `dockdist.py --takeover` ports its stub. Settled at **200 m** for lanes and
  gates after the owner flew 100, 200, 400 and 600; flhack picked the same value.
- **Disproved: `0x639f44c`.** It initialises a field holding the same 1000.0. The
  owner flew it at 100, 1000, 5000 and 10000 with no difference to a lane
  approach. The knob was removed the same day.
- `select_equip.ini` was the first wrong lead; see `patching-files.md`, *Hand changes to the install*.

## Injecting code (`inject.py`, 2026-09-06)

flhack allocates executable memory with `VirtualAllocEx` and keeps the pointer at
`0x67bf40`. `/proc/<pid>/mem` cannot allocate and does not need to: `common.dll`
`.text` ends at `0x6398730` with 2256 bytes of zero padding inside a mapping that
is already `r-xp`, linker slack before `.rdata`. Writing there from outside works
because `/proc/<pid>/mem` goes through page protection.

- **The game must not write into the cave**: the page is read-only, and the first
  stub, which stored `dockwith` there, killed Freelancer on the first call.
  Anything the stub writes at run time goes to `inject.find_scratch`, a zero run
  in an already writable mapping. Constants stay in the cave, written only from
  outside.
- **Use a stub only for a computed value.** A pair of pointers or a constant is
  a byte patch.
- **Not every freeze is the tool's.** The one on 2026-09-05 was
  `i915 GT0: rcs0 reset request timed out`, an Iris Xe GPU hang, with the stub in
  memory and innocent. Read the journal first.

## Trade reputation (`live/trade.py`, 2026-09-15)

The `trade.py` docstring holds the finding (the parser's keyword pool in
`content.dll` has no trade event, so standing is written into the running game
and no game file is touched), the rule that a trade's size is units moved times
that base's price, the memory layout of standings and hold, the end-to-end
verification, and the two traps when checking (the write lands in the next save;
compare standings at 1e-6). The `MAX_STEP` and `SOFT_FLOOR` comments hold the
cap decision. Not there:

- **A base pays for goods it does not stock.** Ten Superconductors sold at Planet
  New Berlin moved the balance 301,186 to 302,186, 100.00 a unit, the `goods.ini`
  price, a seventh of the 700 Oder Shipyard pays two jumps away.
  `market.base_prices` is that walk, lifted out of `load_market`.
- **Clamp a write at ±1.0, the engine's limit, never at `reputation.BOUND`**
  (0.9, the tab's planning bound). Across 224 saves standings use the full ±1.0
  and 172 sit above 0.9. A clamp at 0.9 turned a 52,500-credit trade asking the
  Junkers for +0.00875 into four factions set to exactly 0.9: a loss six times
  the gain, the wrong way.
- **The hold comes from the save.** Freelancer writes the save on the
  transaction (four of four). Reading the hold from memory failed three ways: a
  cached address (the cargo array moves between dockings, and a dead copy still
  answers), re-ranking copies every tick (the save they were scored against is
  rewritten by the trade itself), and a vote of all copies (the candidate set was
  pinned while the cargo was aboard). Ranking copies by their match to the save
  picks a stale one by construction. The hold is tracked continuously, flight
  included; the base decides only whether a change may be billed.
- **A change the balance does not account for bills nothing**: salvage, loot and
  spoilage move the baseline. The owner's Alien Organisms lost a unit every few
  minutes and would otherwise have read as sales.
- **It counts only while the server runs**; `serve.py` starts the watcher at
  boot, not on the first request.

Open, unresolved:

- **Is the save written on docking?** The docstring says the game rewrites
  `[Player] base` on docking; the hold work above recorded that no save is
  written on docking.
- **Mission abortion.** The docstring cites a measurement of 2026-09-15 that
  `random_mission_abortion` reaches the giver and not the empathy table; that
  measurement was never written down. `reputation.py` models
  abortion as spreading through empathy. See `game-data.md`, *Reputation model*.
