#!/usr/bin/env python3
"""What a new game starts you with: the ship and what is bolted to it.

    newgame.py              # what a new game currently gives you
    newgame.py --apply      # write the loadout below
    newgame.py --restore    # back to the .vanilla copies

**`EXE/newplayer.fl` is not where the starting ship comes from**, however much
it looks like it. The file says so itself, in its own comment:

    ; Debug Ship - gets replaced if missions active

Single player always starts M01, so the ship comes from one trigger in
`DATA/MISSIONS/M01A/m01a.ini`:

    Act_SetShipAndLoadout = ge_fighter, msn_playerloadout

and `msn_playerloadout` is a `[Loadout]` in `DATA/SHIPS/loadouts.ini`. Those
two files are what this module writes; `newplayer.fl` is deliberately left
alone, because writing a file the game overwrites is noise that later reads as
a second, disagreeing source of truth.

`msn_playerloadout` is safe to edit in place: that trigger is its only user in
the game. The near-identical `msn_playerloadout_faux` belongs to the `fauxplayer`
NPC and is a separate section.

The same file carries the first mission's cutscenes, so `--skip-scenes` and
`--fast-intro` live here too rather than in a module of their own: two modules
each keeping a `.vanilla` of `m01a.ini` would overwrite each other's work.

**The gun placement is forced by the data, not chosen.** A Sabre takes class 10
on `HpWeapon01` to `04` and caps at class 9 on `05` and `06`. Nomad guns are
class 10 and the Salamanca Mk II is class 9, so four Nomads forward and two
Salamancas outboard is the only arrangement that mounts at all.
"""

import argparse
import math
import os
import shutil
import sys
import tarfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import bini  # noqa: E402
import flvisits as fl  # noqa: E402

LOADOUT = "msn_playerloadout"
INTRO = "FP7_system"
# The trigger that opens the sequence, and the one that ends it by force-landing
# you on Manhattan. The second is not a wait and must never be capped like one.
INTRO_START, INTRO_END = "tr_fp7_cam", "tr_fp7_cam_end"

# The first mission's in-engine cutscenes, by the RTC that plays each.
#
# `s005a`/`s005d`, Juni offering the job, are deliberately not here: that is
# where `Act_SetShipAndLoadout` fires, so cutting it costs you the ship above.
# `s006x`, King on the Pittsburgh pad, is not here either, for the opposite
# reason: its scene file and its 16 voice lines ship with the game but no
# `Act_AddRTC` anywhere plays it, so listing it would be a name that matches
# nothing.
CUTSCENES = ("m000_s002xe_li01_01_nrml",   # Sinclair, the Manhattan cityscape
             "m001a_s003x_li01_01_nrml",   # the bar
             "m001a_s004x_li01_01_nrml")   # Juni in the bar
TRIGGER = "act_setshipandloadout"
SHIP = "bw_elite2"  # Sabre

# The Sabre's own hull kit, taken from its `bwe2_package` in goods.ini. The
# ge_fighter parts a new game ships with do not fit it.
EQUIP = [
    ("ge_bwe2_engine_01",),
    ("bw_elite2_power01",),
    ("shield01_mark07_hf", "HpShield01"),
    ("ge_s_scanner_01",),
    ("ge_s_tractor_01",),
    ("ge_s_thruster_01", "HpThruster01"),
] + [("special_nomad_gun01", f"HpWeapon0{n}") for n in (1, 2, 3, 4)] \
  + [("fc_c_gun01_mark05", f"HpWeapon0{n}") for n in (5, 6)] \
  + [("LargeWhiteSpecial", "HpHeadlight")] \
  + [("SlowSmallWhite", f"HpRunningLight0{n}") for n in range(1, 9)] \
  + [("contrail01", f"HpContrail0{n}") for n in range(1, 5)] \
  + [("DockingLightRedSmall", f"HpDockLight0{n}") for n in (1, 2)]

CARGO = [("ge_s_battery_01", 3), ("ge_s_repair_01", 3)]


class WriteFailed(Exception):
    pass


def _paths(game_dir=None):
    data = fl.ipath(game_dir or fl.DEFAULT_GAME, "DATA")
    return (fl.ipath(data, "SHIPS", "loadouts.ini"),
            fl.ipath(data, "MISSIONS", "M01A", "m01a.ini"))


def _read(path):
    """Sections from the file as it stands.

    Deliberately not drawdist's "always from the vanilla copy". There a
    multiplier would compound; here the three switches touch different keys of
    the same file and have to compose, so each reads what the last one wrote
    and each is written to be a no-op when it has already been applied. The
    `.vanilla` copy is the undo and nothing else.
    """
    return bini.decode(open(path, "rb").read())


def _scene(value):
    """The bare name of an RTC, whichever way the path was spelled."""
    return os.path.basename(str(value).replace("\\", "/")).lower().removesuffix(".ini")


def _write(path, sections):
    """Keep a pristine copy the first time, then write. Same shape as drawdist."""
    keep = path + ".vanilla"
    if not os.path.exists(keep):
        shutil.copy2(path, keep)
    blob = bini.encode(sections)
    if bini.decode(blob) != sections:
        raise WriteFailed(f"{os.path.basename(path)} would not round-trip")
    open(path, "wb").write(blob)


def _loadout(sections):
    """The [Loadout] entries for msn_playerloadout, or None."""
    for name, entries in sections:
        if name.lower() != "loadout":
            continue
        for key, values in entries:
            if key.lower() == "nickname" and str(values[0]).lower() == LOADOUT:
                return entries
    return None


def _triggers(sections):
    """Every (entries, index) where the mission sets the player's ship."""
    out = []
    for _name, entries in sections:
        for i, (key, values) in enumerate(entries):
            if key.lower() == TRIGGER and str(values[0]).lower() != "none":
                out.append((entries, i))
    return out


def state(game_dir=None):
    """What a new game currently gives you, and how much of it you sit through.

    (ship, [(item, hardpoint)], cutscenes still played, longest intro wait).
    """
    loadouts, mission = _paths(game_dir)
    sections = _read(mission)
    ship = None
    for entries, i in _triggers(sections):
        ship = str(entries[i][1][0])
    scenes, wait = [], 0.0
    for name, entries in sections:
        for key, values in entries:
            if key.lower() == "act_addrtc" and _scene(values[0]) in CUTSCENES:
                scenes.append(_scene(values[0]))
        if name.lower() != "trigger":
            continue
        if any(k.lower() == "system" and str(v[0]) == INTRO for k, v in entries):
            for key, values in entries:
                if key.lower() == "cnd_timer":
                    wait = max(wait, float(values[0]))
    gear = [(str(v[0]), str(v[1]) if len(v) > 1 else "")
            for k, v in _loadout(_read(loadouts)) or []
            if k.lower() == "equip"]
    return ship, gear, scenes, wait


def backup(game_dir=None):
    """A dated copy of both files, beside the `.vanilla` pair. Returns the path."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(HERE, f"m01a-backup-{stamp}.tar")
    with tarfile.open(out, "w") as tar:
        for path in _paths(game_dir):
            tar.add(path, arcname=os.path.basename(path))
            keep = path + ".vanilla"
            if os.path.exists(keep):
                tar.add(keep, arcname=os.path.basename(keep))
    return out


def apply(game_dir=None):
    """Put SHIP and EQUIP into the mission trigger and the loadout."""
    loadouts, mission = _paths(game_dir)

    sections = _read(loadouts)
    entries = _loadout(sections)
    if entries is None:
        raise WriteFailed(f"no [Loadout] named {LOADOUT} in loadouts.ini")
    # Rebuilt rather than patched: the vanilla list is a different ship's, so
    # every line in it is either replaced or wrong.
    entries[:] = ([("nickname", [LOADOUT]), ("archetype", [SHIP])]
                  + [("equip", list(e)) for e in EQUIP]
                  + [("cargo", [n, c]) for n, c in CARGO])
    _write(loadouts, sections)

    sections = _read(mission)
    found = _triggers(sections)
    if not found:
        raise WriteFailed(f"no {TRIGGER} in m01a.ini")
    for entries, i in found:
        key, values = entries[i]
        entries[i] = (key, [SHIP] + list(values[1:]))
    _write(mission, sections)
    return len(found)


def skip_scenes(game_dir=None):
    """Drop the mission's cutscenes. Returns (scenes cut, waits released).

    Two triggers hold the mission until a scene reports itself finished, and a
    scene that was never added never reports. So `Cnd_RTCDone` becomes
    `Cnd_True`, which is this mission's own idiom: it uses it 47 times already.
    """
    _loadouts, mission = _paths(game_dir)
    sections = _read(mission)
    cut = freed = 0
    for _name, entries in sections:
        for i, (key, values) in enumerate(list(entries)):
            if not values or _scene(values[0]) not in CUTSCENES:
                continue
            if key.lower() == "act_addrtc":
                entries.remove((key, values))
                cut += 1
            elif key.lower() == "cnd_rtcdone":
                entries[i] = ("Cnd_True", ["no_params"])
                freed += 1
    if cut or freed:
        _write(mission, sections)
    return cut, freed


def _graph(sections):
    """{trigger: (wait, waits on a spoken line, what it activates)} for FP7."""
    out = {}
    for name, entries in sections:
        if name.lower() != "trigger":
            continue
        if not any(k.lower() == "system" and str(v[0]) == INTRO for k, v in entries):
            continue
        nick = next((str(v[0]) for k, v in entries if k.lower() == "nickname"), None)
        if nick:
            out[nick] = (
                next((float(v[0]) for k, v in entries if k.lower() == "cnd_timer"), 0.0),
                any(k.lower() == "cnd_commcomplete" for k, _v in entries),
                [str(v[0]) for k, v in entries if k.lower() == "act_acttrig"])
    return out


def _chain(sections, cap=None):
    """Seconds along the longest run of the sequence, end marker excluded.

    The marker is excluded because it is what the answer is *for*: it has to
    outlast every branch, so it cannot be one of the branches measured.
    """
    graph = _graph(sections)

    def walk(node, seen):
        wait, comm, kids = graph[node]
        if node in seen:
            return 0.0
        held = 0.0 if node == INTRO_START else (
            cap if cap is not None and (comm or wait > cap) else wait)
        rest = [walk(k, seen | {node}) for k in kids
                if k in graph and k != INTRO_END]
        return held + (max(rest) if rest else 0.0)

    return walk(INTRO_START, set()) if INTRO_START in graph else 0.0


def fast_intro(cap=1.0, game_dir=None):
    """Cap every wait in the Freeport 7 sequence. Returns how many were cut.

    The opening is not a cutscene you can remove: it is one chain of timers on
    the 33 triggers scoped to `FP7_system`, ending at `tr_fp7_cam_end` after
    **68.5 seconds**, which is the length of the thing stated in the data.

    Capping rather than scaling, because the order of the chain is what carries
    the sequence and a cap preserves it while compressing every wait to the
    same ceiling. It also means running this twice changes nothing, which is
    what lets it sit beside the other two switches.

    The three waits on a spoken line go too. They are `Cnd_CommComplete`, and
    left alone they would hold the whole compressed chain at the pace of the
    dialogue, which is the pace being cut.

    **`tr_fp7_cam_end` is exempt, and getting that wrong crashed the game
    twice.** Its 68.5 seconds is not a wait between two steps: the opening
    trigger starts it, it runs beside the whole sequence, and it ends the scene
    with `Act_ForceLand` on Manhattan. Capped to 1s like everything else, it
    force-landed the player one second in, while the rest of the chain went on
    spawning ships, lighting fuses and calling cameras into a system that was
    being torn down.

    So it is not capped, it is recomputed: the longest surviving branch, times
    the headroom vanilla gives itself, which is 68.5 over a 42.8-second chain.
    Both numbers are read out of the files rather than written down here, so
    any cap gets a marker that still outlasts what it has to cover.
    """
    _loadouts, mission = _paths(game_dir)
    sections = _read(mission)
    cut = 0
    for name, entries in sections:
        if name.lower() != "trigger":
            continue
        if not any(k.lower() == "system" and str(v[0]) == INTRO for k, v in entries):
            continue
        marker = any(k.lower() == "nickname" and str(v[0]) == INTRO_END
                     for k, v in entries)
        for i, (key, values) in enumerate(list(entries)):
            if marker:
                continue
            if key.lower() == "cnd_timer" and float(values[0]) > cap:
                entries[i] = (key, [cap])
                cut += 1
            elif key.lower() == "cnd_commcomplete":
                entries[i] = ("Cnd_Timer", [cap])
                cut += 1

    keep = mission + ".vanilla"
    van = bini.decode(open(keep, "rb").read()) if os.path.exists(keep) else sections
    slack = (_graph(van)[INTRO_END][0] / _chain(van)) if _chain(van) else 1.0
    end = math.ceil(_chain(sections) * slack)
    for name, entries in sections:
        for i, (key, values) in enumerate(list(entries)):
            if key.lower() == "cnd_timer" and any(
                    k.lower() == "nickname" and str(v[0]) == INTRO_END
                    for k, v in entries):
                entries[i] = (key, [float(end)])
    _write(mission, sections)
    return cut, end


def restore(game_dir=None):
    """Put both files back from their .vanilla copies."""
    back = 0
    for path in _paths(game_dir):
        keep = path + ".vanilla"
        if os.path.exists(keep):
            shutil.copy2(keep, path)
            back += 1
    return back


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--apply", action="store_true", help="write the loadout")
    ap.add_argument("--skip-scenes", action="store_true",
                    help="drop the first mission's cutscenes")
    ap.add_argument("--fast-intro", nargs="?", type=float, const=1.0,
                    metavar="SECONDS",
                    help="cap every wait in the Freeport 7 sequence (default 1)")
    ap.add_argument("--backup", action="store_true", help="dated tar of both files")
    ap.add_argument("--restore", action="store_true", help="undo, from .vanilla")
    args = ap.parse_args()

    if args.backup:
        print(f"backed up to {backup(args.game)}")
    if args.restore:
        print(f"restored {restore(args.game)} file(s)")
    if args.apply:
        print(f"patched {apply(args.game)} trigger(s) and the loadout")
    if args.skip_scenes:
        cut, freed = skip_scenes(args.game)
        print(f"cut {cut} cutscene(s), released {freed} wait(s) on them")
    if args.fast_intro:
        n, end = fast_intro(args.fast_intro, args.game)
        print(f"capped {n} wait(s) at {args.fast_intro:g}s, "
              f"scene ends after {end}s")

    ship, gear, scenes, wait = state(args.game)
    print(f"\na new game starts you in: {ship}")
    for item, hp in gear:
        print(f"   {item:<24} {hp}")
    print(f"\ncutscenes still played: {', '.join(scenes) if scenes else 'none'}")
    print(f"longest wait in the Freeport 7 sequence: {wait:g}s")


if __name__ == "__main__":
    main()
