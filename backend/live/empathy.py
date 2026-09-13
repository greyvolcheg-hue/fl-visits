"""Make killing a Nomad mean something to everybody else.

    fl.py empathy               what one Nomad kill does to Sirius now
    fl.py empathy -0.25
    fl.py empathy --restore

**Nobody in Sirius cares that you kill Nomads, and that is in the data.**
`DATA/MISSIONS/empathy.ini` gives every faction an `object_destruction` value,
what your standing with *them* does when you destroy one of their ships, and a
list of `empathy_rate` entries that spread that change to everyone else. The
Nomad group carries 54 rates and **exactly three of them are non-zero**:

    fc_ln_grp  +1.000    Liberty Navy          story double
    fc_kn_grp  +1.000    Kusari Naval Forces   story double
    fc_rn_grp  +1.000    Rheinland Military    story double

Those three are the infiltrated navies from the campaign, and +1.000 against an
`object_destruction` of -0.03 means they take the full penalty: killing a Nomad
makes them hate you. The other 51 factions move by zero.

## The sign, read off the game rather than guessed

A negative rate means that faction **approves**. Two of the game's own rows say
so plainly: killing a Liberty Rogue is `-0.018`, Liberty Police sit at `-0.250`
toward them, and `-0.018 * -0.250` is `+0.0045` of Police standing. The same
kill moves the Outcasts by `-0.0063`, because their rate is `+0.350`.

So the change is one number in 51 places, and it is a number the game already
uses: rates run `-0.45` to `+1.00`, and `-0.05`, `-0.10` and `-0.25` are the
common ones. At `-0.25` a Nomad kill is worth `+0.0075` to every faction that
is not a Nomad, which is the same order as the game's own bounties.

## The three story doubles keep their +1.000

They are Nomads wearing a navy's colours, so a Nomad kill should still count
against them. Leaving them alone is also what keeps this honest: the mod is
"everyone who is not a Nomad approves", not "every row in the file".

## It survives a reboot because it is a file

`empathy.ini` is BINI in `DATA/`, read at startup, and this writes it the way
every other file writer here does: `.vanilla` first, round trip before
replacing, and `--restore` puts it back. Nothing is patched in memory and there
is nothing to re-apply.

**This file has one writer**, unlike `content.dll`, so rebuilding it from the
shipped copy every time is right here: twice is the same as once, and no other
feature has bytes in it to lose.
"""

import argparse
import os
import sys

import bini

from ..game import flvisits as fl
from ..game import reputation as rep
from ..game import wrecks as wr
from .persist import WriteFailed, _backup, _save

TABLE = ("MISSIONS", "empathy.ini")
SECTION = "repchangeeffects"
GROUP = "fc_n_grp"          # the Nomads
DESTRUCTION = "object_destruction"
RATE_KEY = "empathy_rate"

# The infiltrated navies of the campaign. They are Nomads, so a Nomad kill
# should still count against them, and their shipped +1.000 stays.
DOUBLES = ("fc_ln_grp", "fc_kn_grp", "fc_rn_grp")

# **The setting is a length, not a rate, and the length is a body count.** The
# first version offered the values the game's own file uses, -0.05 to -0.45, on
# the reasoning that borrowing its vocabulary beat inventing a number. That was
# the wrong axis: nothing in the format constrains the value, and the only
# question worth asking of this feature is how long the grind is. At -0.25 it
# was 67 kills from neutral to friendly, which is no alternative to anything.
# This is meant to be the expensive way round a deliberately awkward faction
# balance, and the player has to be able to weigh it.
#
# Counted in ships rather than in wings of four, at the owner's call: it is the
# number he reasons in, and a wing is not a fixed thing anyway.
KILLS = (100, 200, 400, 800, 1600)

# **A nudge, not a rule.** Below this the grind stops being an alternative to
# the ordinary endgame and becomes a button that hands out standing, which is
# the thing this feature is deliberately not. Anyone who wants that anyway is
# allowed to have it: it is their game, and a refusal here would only teach
# them to edit the file by hand.
SOFT_FLOOR = 100


def span():
    """How far neutral is from friendly, out of the model the tab already uses.

    Derived rather than typed, so a change to `reputation.GOALS` cannot leave
    this quoting a distance nothing else agrees with.
    """
    return rep.GOALS["friend"] - rep.GOALS["neutral"]


def rate_for(kills, kill):
    """The empathy rate that makes `kills` ships the journey to friendly."""
    if not kills or not kill:
        return 0.0
    return -(span() / kills) / abs(kill)


def kills_for(rate, kill):
    """How many ships that rate asks for, or None when it asks for none."""
    per = abs(rate * kill)
    return None if not per else span() / per


def _path(game_dir):
    return fl.ipath(fl.ipath(game_dir, "DATA"), *TABLE)


def _shipped(game_dir):
    """The file as the game shipped it, which is `.vanilla` once we have run."""
    path = _path(game_dir)
    keep = path + ".vanilla"
    return keep if os.path.exists(keep) else path


def _group(sections, group=GROUP):
    """The (section, entries) pair for one faction, or None."""
    for name, entries in sections:
        if name.lower() != SECTION:
            continue
        for key, values in entries:
            if key.lower() == "group" and str(values[0]).lower() == group:
                return name, entries
    return None


def labels(game_dir):
    """faction nickname -> display name, for saying who is affected."""
    names = fl.load_names(game_dir)
    out = {}
    for section, pairs in wr.read_multi(
            fl.ipath(fl.ipath(game_dir, "DATA"), "InitialWorld.ini")):
        if section.lower() != "group":
            continue
        entry = {}
        for key, values in pairs:
            entry.setdefault(key.lower(), values)
        nick = str((entry.get("nickname") or [""])[0]).lower()
        try:
            out[nick] = names.get(int((entry.get("ids_name") or [0])[0]), nick)
        except (TypeError, ValueError):
            out[nick] = nick
    return out


def read(game_dir=None):
    """{"kill": delta, "rates": {faction: rate}, "rate": r or None, "n": count}.

    `rate` is the one value every non-Nomad faction is set to, or None when
    they do not agree, which is what the shipped file looks like.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    found = _group(bini.decode(open(_path(game_dir), "rb").read()))
    if not found:
        raise WriteFailed(f"no {GROUP} section in empathy.ini")
    _name, entries = found
    kill, rates = None, {}
    for key, values in entries:
        if key.lower() == "event" and str(values[0]).lower() == DESTRUCTION:
            kill = float(values[1])
        elif key.lower() == RATE_KEY and len(values) >= 2:
            rates[str(values[0]).lower()] = float(values[1])
    others = {k: v for k, v in rates.items() if k not in DOUBLES}
    seen = set(others.values())
    rate = others[next(iter(others))] if len(seen) == 1 else None
    return {"kill": kill, "rates": rates, "rate": rate,
            "kills": None if rate in (None, 0) else kills_for(rate, kill),
            "n": sum(1 for v in others.values() if v)}


def write(kills=None, game_dir=None, rate=None):
    """Set every non-Nomad faction, in ships to friendly. Keeps a `.vanilla`.

    `kills` is the setting; `rate` is the escape hatch for anyone who wants to
    say it in the file's own units, and `kills=0` puts everyone back to the
    shipped indifference.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    if rate is None:
        if kills is None:
            raise WriteFailed("say how many ships, or pass a rate")
        kill = read(game_dir)["kill"]
        rate = rate_for(float(kills), kill)
    rate = float(rate)
    if not -1.0 <= rate <= 0.0:
        raise WriteFailed(
            f"{rate:g} is outside -1.0 to 0.0. A positive rate would make "
            f"everyone hate you for killing Nomads, which the game already "
            f"does for the three story doubles.")
    sections = bini.decode(open(_shipped(game_dir), "rb").read())
    found = _group(sections)
    if not found:
        raise WriteFailed(f"no {GROUP} section in the shipped empathy.ini")
    _name, entries = found
    touched = 0
    for i, (key, values) in enumerate(entries):
        if key.lower() != RATE_KEY or len(values) < 2:
            continue
        who = str(values[0]).lower()
        if who in DOUBLES or who == GROUP:
            continue
        entries[i] = (key, [values[0], rate])
        touched += 1
    path = _path(game_dir)
    kept = _backup(path)
    _save(path, sections)
    return touched, kept


def restore(game_dir=None):
    """Put the shipped empathy.ini back."""
    game_dir = game_dir or fl.DEFAULT_GAME
    path = _path(game_dir)
    keep = path + ".vanilla"
    if not os.path.exists(keep):
        raise WriteFailed("there is no .vanilla copy; nothing to restore")
    _save(path, bini.decode(open(keep, "rb").read()))
    return read(game_dir)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kills", nargs="?", type=float,
                    help="Nomads to kill for neutral to friendly; "
                         "0 for the shipped indifference")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--rate", type=float, help="say it in the file's units")
    ap.add_argument("--restore", action="store_true", help="undo, from .vanilla")
    ap.add_argument("--who", action="store_true", help="list every faction")
    args = ap.parse_args()

    try:
        if args.restore:
            restore(args.game)
            print("restored")
        elif args.kills is not None or args.rate is not None:
            touched, kept = write(args.kills, args.game, args.rate)
            if kept:
                print(f"kept {os.path.basename(kept)}")
            print(f"{touched} factions changed")
        state = read(args.game)

        kill, rate, kills = state["kill"], state["rate"], state["kills"]
        print(f"\none Nomad kill: object_destruction {kill:+.4f}")
        if rate is None:
            print(f"  the other factions do not agree on a rate; "
                  f"{state['n']} of them are non-zero")
        elif not rate:
            print("  every other faction moves by 0.0000: nobody cares")
        else:
            print(f"  every other faction gains {kill * rate:+.5f}, so "
                  f"{kills:.0f} Nomads from neutral to friendly")
        for who in DOUBLES:
            got = state["rates"].get(who, 0.0)
            print(f"  {who:<11} loses {kill * got:+.4f}, a story double, "
                  f"left alone")
        if args.who:
            names = labels(args.game)
            print()
            for who, r in sorted(state["rates"].items(),
                                 key=lambda kv: (kv[1], kv[0])):
                print(f"   {who:<12} {kill * r:+.5f}   {names.get(who, who)}")
    except (WriteFailed, OSError, ValueError) as exc:
        raise SystemExit(str(exc))
