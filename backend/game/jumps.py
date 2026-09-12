"""Every jump between systems, and the shortest way through them.

    fl.py jumps --from li01 --to br01
    fl.py jumps --check

The game ships three precomputed route tables under `UNIVERSE/`, and
`live/bestpath.py` exists to make it read the one that includes jump holes.
**Those tables are not shortest paths.** Checked against the graph this module
builds, over all 2079 pairs in `systems_shortest_path.ini`: equal on 1502, this
one shorter on 577, longer on none. New York to New London is the clean
example. The table goes New York, California, Cortez, Manchester, New London in
four jumps; there are three, New York, Magellan, Manchester, New London, through
a jump gate that has been in the game since 2003, and by flying inside the
systems it is 140 km against 337. So the patch and a good route are two
different things.

## The graph

An `[Object]` carrying a `goto` is a jump:

    goto = <target system>, <target object>, <tunnel effect>

232 of them across 52 systems, every one two-way, and every `goto` names an
object this module also has. 84 are `jumpgate`, 140 are holes of five kinds, two
are `nomad_gate` and six are Dyson airlocks; all of them are edges and the page
says which is which.

**The nodes are jump objects, not systems**, and that is the whole trick. New
York has both a gate and a hole to Texas, and which one you want depends on
where in New York you came in. A graph of systems cannot say that and would
have to guess.

    start      every jump object in the departure system, free
    jump       an object to its counterpart: one jump, no distance, it is instant
    transit    an object to another in the same system: the distance between them
    arrive     the first time a jump lands in the destination

## Two costs, because they disagree

`by="jumps"` is fewest jumps, ties broken by distance. `by="flying"` is least
distance, ties broken by jumps. One Dijkstra, two orderings of the same pair.

**Distance covers the systems in the middle and nothing else.** Where you are in
the system you start from, and where you are going in the one you end in, are
not things a route between two systems knows. Counting anything for either would
be inventing precision.

**Trade lanes are deliberately not modelled.** They are in the same files and
they change real travel time completely, but that needs where the lane runs and
whether it is still standing, which the data does not settle. The figure here is
raw flying in the game's own metres. Same rule as the perishable cargo in
`market.py`.
"""

import argparse
import heapq
import math
import os

from . import bases as bs
from . import flvisits as fl

# Which archetypes are a gate you can see coming and which are a hole you have
# to find. Read off the name rather than listed, because the holes come in five
# colours and a mod is free to add a sixth.
GATE = "gate"
HOLE = "hole"


def _kind(archetype):
    """`gate` or `hole`, from the archetype's own name.

    `nomad_gate` is a gate, `jumphole_light` and its four colours are holes, and
    the Dyson airlocks are holes: nothing puts them on your map for you.
    """
    return GATE if "gate" in archetype and "hole" not in archetype else HOLE


def load_jumps(game_dir=None):
    """Every jump object, by its own nickname, lower case.

    Each carries both spellings of the two systems it joins, `sys` and `to_sys`
    being the nicknames and `system` and `to_system` the labels, for the reason
    `market.py` gives: five display names in this game belong to more than one
    system, so the label is never the key.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    data_dir = fl.ipath(game_dir, "DATA")
    names = fl.load_names(game_dir)
    _bases, systems = fl.load_universe(data_dir)
    label = {}
    for nick, ids in systems.items():
        try:
            label[nick.lower()] = names.get(int(ids), nick)
        except (TypeError, ValueError):
            label[nick.lower()] = nick
    scales = bs.load_scales(data_dir, fl.read_ini, fl.ipath)

    out = {}
    for path, system in fl.system_files(data_dir):
        scale = scales.get(system, 1.0)
        for section, pairs in bs.read_multi(path):
            if section.lower() != "object":
                continue
            entry = bs._entries(pairs)
            if "goto" not in entry or "nickname" not in entry:
                continue
            goto = entry["goto"][0]
            if len(goto) < 2:
                continue
            pos = [float(v) for v in entry["pos"][0]] if entry.get("pos") else [0, 0, 0]
            arch = str(entry.get("archetype", [["?"]])[0][0]).lower()
            ids = entry.get("ids_name", [[0]])[0][0]
            cell = bs.sector(pos[0], pos[2], scale)
            spot = bs.subcell(pos[0], pos[2], scale)
            key = str(entry["nickname"][0][0]).lower()
            to_sys = str(goto[0]).lower()
            out[key] = {
                "id": key,
                "sys": system,
                "system": label.get(system, system),
                "name": names.get(int(ids), key) if ids else key,
                "arch": arch,
                "kind": _kind(arch),
                "at": " ".join(x for x in (cell, spot) if x),
                "pos": pos,
                "to_sys": to_sys,
                "to_system": label.get(to_sys, to_sys),
                "to_id": str(goto[1]).lower(),
            }
    return out


def systems(jumps):
    """[{key, label}] for a picker, every system with at least one jump."""
    seen = {}
    for jump in jumps.values():
        seen.setdefault(jump["sys"], jump["system"])
        seen.setdefault(jump["to_sys"], jump["to_system"])
    return sorted(({"key": k, "label": v} for k, v in seen.items()),
                  key=lambda s: s["label"])


def seen_in(jumps, visits):
    """Which jump objects a save has been told about.

    A jump is recorded the same way a base or a wreck is, by the `FLHash` of its
    nickname in the save's `visit` table. **Every jump in the save this was
    built against reads flag 1**, "it is on your nav map", and 73 of the 232
    appear at all: a gate you have flown past and a hole you have stumbled into
    record identically, so the flag carries nothing worth reading and only
    presence does.
    """
    known = {fl.fl_hash(key): key for key in jumps}
    return {known[h] for h in visits if h in known}


def usable(jumps, found):
    """The ids a route may use, given the set of jump objects a save has seen.

    **A link counts as known when either of its two ends has been seen**, not
    just the one you are standing at. 14 of the 116 links in this save are
    marked at one end only, and refusing the return trip on those would be the
    tool pretending not to know about a hole it just told you the far side of.
    The step itself still carries `found` for its own object, so a page can say
    which ones are not on your nav map yet.

    `found` of None means no filtering at all.
    """
    if found is None:
        return None
    return {k for k, j in jumps.items() if k in found or j["to_id"] in found}


def _dist(a, b):
    return math.dist(a["pos"], b["pos"])


def route(jumps, src, dst, allow=None, by="flying", holes=True):
    """The jumps taken from one system to another, or None when there is no way.

    `by` is `flying` or `jumps`; see the module docstring for what each costs.
    `allow` is a set of jump ids, from `usable`, or None for every jump.

    **The filters apply to departures only.** You may land anywhere, because
    landing is what the jump does to you; what you may choose is which jump to
    take. A hole you have not found is not a hole you can decide to fly into,
    and one you arrive through is already behind you.
    """
    if src == dst:
        return []

    def ok(jump):
        if allow is not None and jump["id"] not in allow:
            return False
        return holes or jump["kind"] != HOLE

    here = {}
    for jump in jumps.values():
        if ok(jump):
            here.setdefault(jump["sys"], []).append(jump)
    if src not in here:
        return None

    def cost(pair):
        hops, flown = pair
        return (hops, flown) if by == "jumps" else (flown, hops)

    # `best` is the cheapest way found to be standing at each object, `prev` the
    # object before it and what the flying between them cost. Both components
    # are additive and never negative, so ordering the pair lexicographically is
    # still a Dijkstra and the first pop of a node is its answer.
    best, prev, heap = {}, {}, []
    for jump in here[src]:
        best[jump["id"]] = (0, 0.0)
        prev[jump["id"]] = None
        heapq.heappush(heap, (cost((0, 0.0)), jump["id"]))

    while heap:
        _order, key = heapq.heappop(heap)
        at = best[key]
        if jumps[key]["sys"] == dst:
            return _walk(jumps, prev, key)
        hops, flown = at

        def relax(nxt, step, jumped):
            was = best.get(nxt)
            now = (hops + (1 if jumped else 0), flown + step)
            if was is not None and cost(was) <= cost(now):
                return
            best[nxt] = now
            prev[nxt] = (key, step)
            heapq.heappush(heap, (cost(now), nxt))

        # Take this one. Its counterpart is where standing next happens.
        if jumps[key]["to_id"] in jumps:
            relax(jumps[key]["to_id"], 0.0, True)
        # Or fly across this system to another jump you are allowed to take.
        for other in here.get(jumps[key]["sys"], ()):
            if other["id"] != key:
                relax(other["id"], _dist(jumps[key], other), False)
    return None


def _walk(jumps, prev, last):
    """The `prev` chain turned into the jumps actually taken.

    The chain alternates flying and jumping, so a step is any link whose next
    entry is that object's own counterpart. `leg` is what was flown to reach
    the object you jump from, which is zero for the first one: the flying inside
    the system you start in is not this function's to know.
    """
    chain, key = [], last
    while key is not None:
        came = prev.get(key)
        chain.append((key, came[1] if came else 0.0))
        key = came[0] if came else None
    chain.reverse()
    steps = []
    for i, (key, leg) in enumerate(chain[:-1]):
        if jumps[key]["to_id"] == chain[i + 1][0]:
            steps.append({"jump": jumps[key], "leg": leg})
    return steps


def plan(jumps, src, dst, allow=None, holes=True):
    """Both routes, and whether they came out the same.

    Returns `{"jumps": {...}, "flying": {...}, "same": bool}` where each route
    is `{"steps": [...], "hops": n, "flying": metres}`, or None for that one
    when there is no way at all.
    """
    out = {"same": False}
    for by in ("jumps", "flying"):
        steps = route(jumps, src, dst, allow, by, holes)
        out[by] = None if steps is None else {
            "steps": [{"leg": round(s["leg"]), **s["jump"]} for s in steps],
            "hops": len(steps),
            "flying": round(sum(s["leg"] for s in steps)),
        }
    a, b = out["jumps"], out["flying"]
    out["same"] = bool(a and b and [s["id"] for s in a["steps"]]
                       == [s["id"] for s in b["steps"]])
    return out


def check(game_dir=None):
    """Compare every pair against the game's own table. See the docstring."""
    import bini
    game_dir = game_dir or fl.DEFAULT_GAME
    path = fl.ipath(fl.ipath(fl.ipath(game_dir, "DATA"), "UNIVERSE"),
                    "systems_shortest_path.ini")
    table = {}
    for _section, pairs in bini.decode(open(path, "rb").read()):
        for key, values in pairs:
            if key.lower() == "path" and len(values) >= 2:
                table[(str(values[0]).lower(), str(values[1]).lower())] = [
                    str(v).lower() for v in values[2:]]
    jumps = load_jumps(game_dir)
    tally = {"equal": 0, "shorter": 0, "longer": 0, "none": 0}
    for (src, dst), want in table.items():
        if src == dst:
            tally["equal"] += 1
            continue
        steps = route(jumps, src, dst, by="jumps")
        if steps is None:
            tally["none"] += 1
            continue
        mine, theirs = len(steps), max(len(want) - 1, 0)
        tally["equal" if mine == theirs
              else "shorter" if mine < theirs else "longer"] += 1
    return len(table), tally


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--from", dest="src", help="departure system nickname")
    ap.add_argument("--to", dest="dst", help="destination system nickname")
    ap.add_argument("--gates", action="store_true", help="never use a jump hole")
    ap.add_argument("--check", action="store_true",
                    help="compare every pair with the game's own route table")
    args = ap.parse_args()

    if args.check:
        total, tally = check(args.game)
        print(f"{total} pairs in the game's systems_shortest_path.ini")
        for name in ("equal", "shorter", "longer", "none"):
            print(f"   {name:<8}{tally[name]:>6}")
        return

    jumps = load_jumps(args.game)
    if not args.src or not args.dst:
        links = len({frozenset((k, j["to_id"])) for k, j in jumps.items()})
        print(f"{len(jumps)} jump objects, {links} two-way links, "
              f"{len({j['sys'] for j in jumps.values()})} systems")
        for row in systems(jumps):
            print(f"   {row['key']:<8}{row['label']}")
        return

    found = plan(jumps, args.src.lower(), args.dst.lower(), holes=not args.gates)
    for by in ("jumps", "flying"):
        one = found[by]
        if one is None:
            print(f"\nby {by}: no route")
            continue
        if by == "flying" and found["same"]:
            print("\nfewest jumps and least flying are the same route")
            break
        print(f"\nby {by}: {one['hops']} jumps, {one['flying'] / 1000:,.1f} km")
        for i, step in enumerate(one["steps"], 1):
            leg = f"{step['leg'] / 1000:,.1f} km" if step["leg"] else ""
            print(f"  {i}. {step['system']:<16}{step['at']:<8}"
                  f"{step['name'][:30]:<31}{step['kind']:<5}{leg}")
