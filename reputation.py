#!/usr/bin/env python3
"""What to do to change how a faction feels about you, and what it costs.

    reputation.py <save.fl> --to fc_ou_grp --goal neutral
    reputation.py <save.fl> --list

`DATA/MISSIONS/empathy.ini` holds the whole model as 55 `[RepChangeEffects]`
sections, one per faction:

    group        = fc_ou_grp
    event        = object_destruction,      -0.006
    event        = random_mission_success,   0.14
    event        = random_mission_failure,  -0.045
    event        = random_mission_abortion, -0.0675
    empathy_rate = li_n_grp, -0.4
    ... 54 empathy_rate lines, one per other faction

An event against faction T moves your standing with T by that event's own delta,
and with every other faction F by `delta * empathy_rate[T][F]`.

**All four events matter.** Aborting a mission for an enemy of your target
*raises* your standing with the target: abortion is negative to the faction that
offered it, the empathy rate between enemies is negative, and the two signs
cancel. For the Corsairs that ranks above succeeding for the Junkers. A version
of this that only counted kills and successes would look right and be wrong.

So the action space is 55 factions x 4 events = 220, and every one of them is
scored rather than a shortlist being guessed at.

**The bound is +/-0.9**, established from the saves rather than from the files:
values sit inside it, and factions are found sitting exactly on both ends. The
goal levels are well inside it, so reaching a goal never saturates, but a long
grind pins bystanders at the bound and the collateral figures clamp there.

Whose numbers are hurt is half the answer. A plan that fixes one standing is
also a plan to wreck several others, so every action carries what it does to
everyone else at the repeat count it would actually be performed.

Bribes are in too, as a one-purchase row with a price instead of a repeat
count. A bribe *sets* your standing to 0.6 rather than adding to it, so it is
worth nothing above that and buying a second changes nothing. See BRIBE_TO.
"""

import argparse
import math
import os
import sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flvisits as fl  # noqa: E402
import wrecks as wr  # noqa: E402

BOUND = 0.9
GOALS = {"enemy": -0.5, "neutral": 0.0, "friend": 0.5}

# A bribe SETS your standing to 0.6. It does not add to it, so it is worth
# nothing once you are already above that, and buying two changes nothing.
#
# Established from flhack, not from the game's files, which carry no usable
# number: the `bribe` lines in `mbases.ini` all read a flat 10000, all 2386 of
# them, so that is a placeholder and the engine computes the real price.
# flhack's flexible bribes shift the result by 0.3, -0.6 and -0.4 from a base,
# landing on the 0.9, 0.0 and 0.2 its own documentation quotes, which puts the
# base at 0.6. Its assembly divides the price by the change in reputation
# before scaling it, so price is proportional to distance travelled.
#
# **The rate is derived, not measured.** flhack documents those three options as
# costing +30000, -60000 and -40000, and 30000/0.3, 60000/0.6 and 40000/0.4 all
# come to 100000 per point of reputation. Consistent across three figures, but
# nobody has read a bartender's price and checked. Verify before trusting it to
# the credit: a bribe for a faction at -0.44 should ask about 104000.
BRIBE_TO = 0.6
BRIBE_RATE = 100000

# The four repeatable things a player can do to a faction, in the order they
# read best: the one you do in space, then the three you do to a job.
EVENTS = [
    ("object_destruction", "destroy a ship"),
    ("random_mission_success", "complete a mission"),
    ("random_mission_failure", "fail a mission"),
    ("random_mission_abortion", "abort a mission"),
]
EVENT_LABEL = dict(EVENTS)


def _entries(pairs):
    out = {}
    for key, values in pairs:
        out.setdefault(key.lower(), []).append(values)
    return out


# The house a faction nickname's prefix belongs to, for suffixing a colliding
# short name. Only the four houses are here on purpose: `co_`, `fc_` and `gd_`
# are corporations, criminals and guilds and have no house to name, so they
# fall back to the nickname rather than being assigned one.
HOUSE_CODE = {"li": "LI", "br": "BR", "ku": "KU", "rh": "RH"}


def _disambiguate(labels, suffix):
    """Suffix in place, but only the labels worn by more than one faction.

    Decorating everything would put a parenthesis on 45 names to fix 4. The
    ones that read cleanly are the ones that stay untouched.
    """
    seen = {}
    for key, label in labels.items():
        seen.setdefault(label, []).append(key)
    for label, keys in seen.items():
        if len(keys) > 1:
            for key in keys:
                labels[key] = f"{label} ({suffix(key)})"


class Model(NamedTuple):
    """The reputation model, by field name rather than by position.

    A plain tuple here cost the Reputation tab a crash on 2026-09-05. Adding
    `shorts` for the Visits badges made it six long, and `serve.py` splatted
    the whole thing into `plan()` with `*model`, so `plan` got nine arguments
    and every faction click 500'd. The two explicit unpack sites were both
    updated; the splat was invisible because it named nothing.

    Named fields make that mistake impossible: a call site asks for what it
    wants and a new field cannot change what any other call receives. Do not
    go back to positional unpacking, and do not splat this into anything.
    """

    events: dict
    empathy: dict
    names: dict
    shorts: dict
    legality: dict
    bribes: dict


def load_model(game_dir=None):
    """A `Model`, every field keyed by lowered faction nickname.

    `shorts` is the badge form, from `ids_short_name`: "Police", "Samura",
    "IMG". It comes out of the same pass over `initialworld.ini` that builds
    `names`, because a second reader for one file is a second thing to keep in
    step.
    """
    game_dir = game_dir or fl.DEFAULT_GAME
    data_dir = fl.ipath(game_dir, "DATA")
    strings = fl.load_names(game_dir)

    events, empathy = {}, {}
    path = fl.ipath(fl.ipath(data_dir, "MISSIONS"), "empathy.ini")
    for section, pairs in wr.read_multi(path):
        if section.lower() != "repchangeeffects":
            continue
        group, ev, rates = None, {}, {}
        for key, values in pairs:
            name = key.lower()
            if name == "group":
                group = str(values[0]).lower()
            elif name == "event" and len(values) > 1:
                ev[str(values[0]).lower()] = float(values[1])
            elif name == "empathy_rate" and len(values) > 1:
                rates[str(values[0]).lower()] = float(values[1])
        if group:
            events[group], empathy[group] = ev, rates

    # initialworld.ini is plain text, not BINI. read_multi sniffs the magic.
    names, shorts = {}, {}
    for section, pairs in wr.read_multi(fl.ipath(data_dir, "initialworld.ini")):
        if section.lower() != "group":
            continue
        entry = _entries(pairs)
        nick = entry.get("nickname")
        if not nick:
            continue
        key = str(nick[0][0]).lower()

        def text(field, entry=entry):
            ids = entry.get(field)
            try:
                return strings.get(int(ids[0][0]), "").strip() if ids else ""
            except (TypeError, ValueError):
                return ""

        # `fc_uk_grp` resolves to a single space in the string table, which as a
        # dropdown entry is an invisible row that sorts to the top. Fall back to
        # the nickname rather than showing nothing.
        names[key] = text("ids_name") or key
        # Short falls back through the full name before the nickname: a badge
        # reading "Farmers Alliance" is worse than "Alliance" and far better
        # than `fc_fa_grp`. Only `fc_uk_grp` reaches the last step.
        shorts[key] = text("ids_short_name") or names[key]

    # Three display names are worn by two factions each: li_n_grp and fc_ln_grp
    # are both "Liberty Navy", and the same for Kusari Naval Forces and
    # Rheinland Military. The `fc_` ones are the encounter factions and sit far
    # lower than the house navy the player actually deals with, so an
    # undecorated list sorted by standing puts the wrong "Liberty Navy" on top
    # and the reading is nonsense against what the game shows. Tag the
    # nickname on, but only where the name is genuinely ambiguous.
    _disambiguate(names, lambda key: key)
    # Short names collide harder: all four house police forces are called
    # "Police" by the game itself. A nickname suffix would be unreadable on a
    # badge, so they take the house code instead, `Police (LI)`. Anything whose
    # prefix is not a house keeps the nickname, because a wrong house is worse
    # than an ugly one and no `co_`/`fc_`/`gd_` short name collides today.
    _disambiguate(shorts, lambda key: HOUSE_CODE.get(key[:2].lower(), key))

    legality = {}
    prop = fl.ipath(fl.ipath(data_dir, "MISSIONS"), "faction_prop.ini")
    for section, pairs in wr.read_multi(prop):
        if section.lower() != "factionprops":
            continue
        entry = _entries(pairs)
        aff, legal = entry.get("affiliation"), entry.get("legality")
        if aff and legal:
            legality[str(aff[0][0]).lower()] = str(legal[0][0]).lower()

    return Model(events, empathy, names, shorts, legality, load_bribes(data_dir))


def load_bribes(data_dir):
    """faction (lower) -> how many bartenders will take a bribe for it.

    41 of the 55 factions can be bribed at all, across 610 of the game's
    bar NPCs. The count is worth carrying because "nobody will take your money
    for this faction" is a real answer and an empty row is not.
    """
    out = {}
    path = fl.ipath(fl.ipath(data_dir, "MISSIONS"), "mbases.ini")
    for section, pairs in wr.read_multi(path):
        if section.lower() != "gf_npc":
            continue
        for key, values in pairs:
            if key.lower() == "bribe" and values:
                faction = str(values[0]).lower()
                out[faction] = out.get(faction, 0) + 1
    return out


def player_reps(save_text):
    """faction (lower) -> the player's current standing."""
    import re
    block = re.search(r"^\[Player\]\s*$(.*?)^\[", save_text, re.M | re.S)
    if not block:
        return {}
    out = {}
    for line in re.findall(r"^\s*house\s*=\s*([^\n]+)$", block.group(1), re.M):
        value, _, faction = line.partition(",")
        try:
            out[faction.strip().lower()] = float(value)
        except ValueError:
            continue
    return out


def effect_on(events, empathy, doer, event, target):
    """What one `event` against `doer` does to your standing with `target`."""
    delta = events.get(doer, {}).get(event)
    if delta is None:
        return 0.0
    if doer == target:
        return delta
    return delta * empathy.get(doer, {}).get(target, 0.0)


def clamp(value):
    return max(-BOUND, min(BOUND, value))


def plan(target, goal, reps, events, empathy, names, legality, bribes=None):
    """Every action that moves `target` towards `goal`, cheapest first.

    Actions worth nothing to the target are dropped, and so are the ones that
    move it the wrong way: shooting Outcasts is not a way to make the Outcasts
    like you. That test is only ever about the target. What an action does to
    everyone else is carried on the row, never a reason to drop it.
    """
    current = reps.get(target, 0.0)
    needed = goal - current
    if abs(needed) < 1e-9:
        return current, needed, []

    rows = []
    bribes = bribes or {}
    # A bribe is one purchase rather than a grind, so it goes in as a row with
    # repeats of 1 and a price. It only appears when it would actually move the
    # target the right way: buying a jump to 0.6 is no help when the goal is to
    # be hated, and none at all once you are already above 0.6.
    bar = bribes.get(target)
    if bar and reps.get(target, 0.0) < BRIBE_TO:
        jump = BRIBE_TO - current
        if (jump > 0) == (needed > 0):
            rows.append({
                "doer": target,
                "doer_name": names.get(target, target),
                "legality": legality.get(target, ""),
                "event": "bribe",
                "event_label": "bribe a bartender",
                "effect": jump,
                "repeats": 1,
                "price": round(BRIBE_RATE * jump),
                "bartenders": bar,
                "reaches": BRIBE_TO,
                "collateral": collateral(target, None, 1, target, events,
                                         empathy, names, reps, delta=jump),
            })

    for doer in sorted(events):
        for event, _label in EVENTS:
            effect = effect_on(events, empathy, doer, event, target)
            if abs(effect) < 1e-9 or (effect > 0) != (needed > 0):
                continue
            repeats = math.ceil(needed / effect)
            rows.append({
                "doer": doer,
                "doer_name": names.get(doer, doer),
                "legality": legality.get(doer, ""),
                "event": event,
                "event_label": EVENT_LABEL[event],
                "effect": effect,
                "repeats": repeats,
                "reaches": clamp(current + repeats * effect),
                "collateral": collateral(doer, event, repeats, target,
                                         events, empathy, names, reps),
            })
    rows.sort(key=lambda r: (r["repeats"], -abs(r["effect"]), r["doer_name"]))
    return current, needed, rows


def collateral(doer, event, repeats, target, events, empathy, names, reps,
               delta=None):
    """Every other faction this run of actions moves, worst loss first.

    Computed at the repeat count rather than per action, because the repeat
    count is what will actually happen and nobody should be multiplying small
    decimals in their head.

    One clamp rather than a loop: the per-action effect is constant, so the
    total is linear and only the endpoint can saturate. Bystanders saturate
    often, which is the point of showing this at all.
    """
    # `delta` is passed in for a bribe, whose size is the jump to 0.6 rather
    # than a fixed event value. It spreads through empathy like anything else:
    # flhack's ALT option exists precisely to switch that off, and costs double.
    if delta is None:
        delta = events.get(doer, {}).get(event)
    if delta is None:
        return []
    out = []
    for faction, rate in empathy.get(doer, {}).items():
        if faction == target or abs(rate) < 1e-12:
            continue
        before = reps.get(faction, 0.0)
        after = clamp(before + repeats * delta * rate)
        if abs(after - before) < 1e-9:
            continue  # already pinned at the bound: no change to report
        out.append({
            "faction": faction,
            "name": names.get(faction, faction),
            "before": before,
            "after": after,
            "change": after - before,
            "pinned": abs(abs(after) - BOUND) < 1e-9,
        })
    out.sort(key=lambda c: c["change"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save", nargs="?")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--to", dest="target", help="faction nickname to change")
    ap.add_argument("--goal", choices=sorted(GOALS), default="neutral")
    ap.add_argument("--list", action="store_true", help="show faction nicknames")
    ap.add_argument("--show", type=int, default=5,
                    help="expand the collateral of the top N rows")
    args = ap.parse_args()

    model = load_model(args.game)
    events, names = model.events, model.names
    if args.list or not args.target:
        for key in sorted(events):
            print(f"  {key:<14} {names.get(key, key)}")
        return
    if not args.save:
        sys.exit("a save file is needed to know where you stand")

    reps = player_reps(fl.decode_save(args.save))
    target = args.target.lower()
    if target not in events:
        sys.exit(f"no such faction: {target}")

    current, needed, rows = plan(target, GOALS[args.goal], reps,
                                 model.events, model.empathy, model.names,
                                 model.legality, model.bribes)
    label = names.get(target, target)
    print(f"{label}: now {current:+.4f}, want {GOALS[args.goal]:+.2f} "
          f"({args.goal})")
    if not rows:
        print("  already there, nothing to do" if abs(needed) < 1e-9
              else "  no repeatable action moves this")
        return
    bribe = sum(1 for r in rows if r["event"] == "bribe")
    print(f"  gap {needed:+.4f}, {len(rows) - bribe} of 220 repeatable actions "
          f"help{', plus a bribe' if bribe else ''}\n")

    for i, row in enumerate(rows):
        loss = [c for c in row["collateral"] if c["change"] < 0]
        gain = [c for c in row["collateral"] if c["change"] > 0]
        worst = f", worst {loss[0]['name']} {loss[0]['change']:+.3f}" if loss else ""
        cost = f"  {row['price']:,} cr" if row.get("price") else ""
        print(f"  {row['repeats']:>5} x {row['event_label']:<18} "
              f"{row['doer_name'][:26]:<27} {row['effect']:+.4f} each"
              f"{cost}  [+{len(gain)}/-{len(loss)}{worst}]")
        if i < args.show:
            for c in row["collateral"]:
                pin = " (pinned)" if c["pinned"] else ""
                print(f"          {c['name'][:30]:<31} "
                      f"{c['before']:+.3f} -> {c['after']:+.3f}"
                      f"  {c['change']:+.3f}{pin}")


if __name__ == "__main__":
    main()
