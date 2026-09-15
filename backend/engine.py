"""The engine strip: cruise, thrusters, lanes, docking and draw distance.

The page half is in `frontend/engine.py`, and unlike every other pair here it
is not a tab: the strip sits above the tab row on every page, because what it
changes applies to the whole running game.

**`/api/engine` is what the strip polls, and it exists to make one request
where there were five.** It also stops at the first `find_pid`: with no game
running there is nothing to read and four more failed scans say so four more
times. The two expensive readings are behind `?all=1`, because `drawdist`
surveys 153 files on disk and the strip is polled every five seconds whether
or not anyone has opened the drawer.
"""

import threading

from .live import callsign as cs
from .live import dockdist as dkd
from .live import routetable as rt
from .live import drawdist as dd
from .live import empathy as em
from .live import trade as td
from .live import persist as pe
from .live import speed as sp
from .live import thrusters as th
from .live import tradelane as tl

# 300 is roughly vanilla and 1000 is what constants.ini carries. The top of the
# range is where ANOM_LIMITS_MAX_VELOCITY sits, so 10000 may clamp: that cap is
# a separate constant this does not touch.
SPEED_CHOICES = [300, 500, 750, 1000, 1500, 2000, 2500, 5000]
# 2500 is vanilla, 10000 is flhack's own ceiling, kept rather than reinvented.
TRADELANE_CHOICES = [2500, 5000, 7500, 10000]
# Where the docking takeover slider may go. 1000 is stock and 200 is what
# settled after the owner flew 100, 200, 400 and 600 on 2026-09-05.
TAKEOVER_RANGE = [100, 1000, 50]
# A multiple of each field's own vanilla value. Geometry grows with the cube of
# the radius, so 2x is roughly 8x the rocks.
DRAWDIST_CHOICES = [1, 2, 3, 4]


def _speed(ctx):
    """Current cruise speed, or why it cannot be read.

    A missing ctx.game is the normal case, not an error: the page is
    usually open before Freelancer is started.
    """
    body = {"choices": SPEED_CHOICES, "value": None,
            "error": None}
    try:
        _pid, _addr, value = sp.current()
        body["value"] = round(value, 1)
    except sp.NotRunning as exc:
        body["error"] = str(exc)
    return body


def _thrusters(ctx):
    """Every thruster and its bonus, or why they cannot be read."""
    body = {"choices": th.SPEED_CHOICES, "items": [],
            "error": None}
    try:
        # The infocards are already loaded for the rest of the report,
        # so the names come from there rather than a second read.
        labels = {ids: ctx.game.names.get(ids) or nick
                  for ids, nick in th.THRUSTERS.items()}
        _pid, rows = th.read_all()
        body["items"] = [
            {"ids": ids, "name": labels.get(ids, nick),
             "speed": round(value, 1)}
            for ids, nick, _addr, value in rows
        ]
    except (th.NotRunning, OSError) as exc:
        body["error"] = str(exc)
    return body


def _tradelane(ctx):
    """Trade lane speed and the HUD's own ceiling, or why not."""
    body = {"choices": TRADELANE_CHOICES, "vanilla": tl.VANILLA,
            "takeover_range": TAKEOVER_RANGE,
            "value": None, "uncapped": False, "shown": None,
            "instant": False, "takeover": None,
            "takeover_default": dkd.NON_STATION,
            "takeover_stock": dkd.SENTINEL,
            "error": None}
    try:
        value, version = tl.read()
        body["value"] = round(value, 1)
        _rate, body["instant"] = tl.read_accel(version=version)
        body["uncapped"], body["shown"] = tl.read_cap()
        # None means the patch is out, which is a different state from
        # "in, at the stock distance" and has to read differently.
        # `version` is already in hand from tl.read; without it this
        # re-scanned every /proc/N/cmdline and re-located the build,
        # every five seconds, for one bool and one float.
        installed, distance, _v = dkd.takeover_state(version=version)
        body["takeover"] = round(distance, 1) if installed else None
    except (tl.NotRunning, OSError) as exc:
        body["error"] = str(exc)
    return body


def _drawdist(ctx):
    """Where asteroid fields currently start being real rocks."""
    body = {"choices": DRAWDIST_CHOICES, "factor": None, "fields": 0,
            "median": None, "vanilla": None,
            "error": None}
    try:
        rows = dd.survey(ctx.game.dir)
        if rows:
            base = sorted(r[1] for r in rows)
            now = sorted(r[2] for r in rows)
            mid = len(rows) // 2
            body["fields"] = len(rows)
            body["vanilla"] = round(base[mid])
            body["median"] = round(now[mid])
            # One number for the whole set only makes sense because
            # every field is scaled from its own vanilla value.
            body["factor"] = round(now[mid] / base[mid], 3)
    except (dd.WriteFailed, OSError) as exc:
        body["error"] = str(exc)
    return body


def _callsign(ctx):
    """What the bots call you, and every word they are able to say.

    The three lists are read off the game's own data every time rather than
    cached: they are a few thousand INI lines and this is only asked for when
    the drawer is open, which is the same bargain `_drawdist` makes.
    """
    body = {"faction": None, "desig": None, "wing": None, "slot": None,
            "says": None, "factions": [], "designators": [], "numbers": [],
            "error": None}
    try:
        state = cs.read(ctx.game.dir)
        body.update(state)
        body["says"] = cs.sentence(ctx.game.dir, state)
        body["factions"] = [{"key": k, "label": v}
                            for k, v in cs.factions(ctx.game.dir)]
        body["designators"] = [{"key": n, "label": v}
                               for n, v in cs.designators(ctx.game.dir)]
        body["numbers"] = cs.numbers(ctx.game.dir)
    except (cs.WriteFailed, OSError, ValueError) as exc:
        body["error"] = str(exc)
    return body


def _routetable(ctx):
    """Which route table Set Best Path is reading, and what is in it."""
    body = {"mode": None, "systems": 0, "rows": 0, "stock": True,
            "modes": sorted(rt.MODES), "files": {k: v["file"]
                                                 for k, v in rt.MODES.items()},
            "error": None}
    try:
        mode, systems, rows, _kept, stock = rt.state(ctx.game.dir)
        body.update(mode=mode, systems=systems, rows=rows, stock=stock)
    except (rt.WriteFailed, OSError, ValueError) as exc:
        body["error"] = str(exc)
    return body


def _empathy(ctx):
    """What one Nomad kill does to everybody else's opinion of you."""
    body = {"kill": None, "rate": None, "per": None, "kills": None, "n": 0,
            "choices": list(em.KILLS), "floor": em.SOFT_FLOOR,
            "error": None}
    try:
        state = em.read(ctx.game.dir)
        body.update(kill=state["kill"], rate=state["rate"], n=state["n"],
                    kills=None if state["kills"] is None
                    else round(state["kills"]))
        if state["rate"] is not None and state["kill"] is not None:
            body["per"] = round(state["kill"] * state["rate"], 5)
    except (em.WriteFailed, OSError, ValueError) as exc:
        body["error"] = str(exc)
    return body


def _engine(ctx):
    """Every reading the strip shows, in one request and one pid lookup.

    The per-knob endpoints below it are still real and still the ones a POST
    answers with, so a reading has one spelling and this composes them rather
    than repeating any of them.
    """
    body = {"running": False, "error": None, "cruise": None, "lane": None,
            "thrusters": None, "draw": None, "call": None,
            "paths": None, "nomads": None, "trade": None}
    try:
        sp.find_pid()
        body["running"] = True
    except sp.NotRunning as exc:
        body["error"] = str(exc)
        # The draw distance is a file, not a process, so it is readable with
        # the game shut and is the one thing worth answering here.
        if ctx.one("all"):
            body["draw"] = _drawdist(ctx)
            body["call"] = _callsign(ctx)
            body["paths"] = _routetable(ctx)
            body["nomads"] = _empathy(ctx)
            body["trade"] = _trade(ctx)
        return body
    body["cruise"] = _speed(ctx)
    body["lane"] = _tradelane(ctx)
    if ctx.one("all"):
        body["thrusters"] = _thrusters(ctx)
        body["draw"] = _drawdist(ctx)
        body["call"] = _callsign(ctx)
        body["paths"] = _routetable(ctx)
        body["nomads"] = _empathy(ctx)
        body["trade"] = _trade(ctx)
    return body


# **No `bestpath` here any more, and not only because the control went.** This
# module and `backend/bestpath.py` both offered an endpoint by that name, and
# `tabs.py` builds one table with `dict.update`, so the later module silently
# won and this one was unreachable. Two tabs cannot share an endpoint name;
# `_table` raises on a repeat now rather than picking by import order.


# **One watcher for the whole server, not one per request.** The hold only
# exists in the running game between saves, so something has to be looking at
# it continuously; a per-request object would see one frame and never a change.
# It is built on first use because building it reads the game's data.
_WATCH = {"it": None}
_watch_lock = threading.Lock()


def _watcher(ctx):
    with _watch_lock:
        if _WATCH["it"] is None:
            _WATCH["it"] = td.Watcher(
                ctx.game.dir, lambda: ctx.save, ctx.game.repmodel,
                ctx.game.market[0], ctx.game.market[1], ctx.game.owners)
            if td.load_setting()["on"]:
                _WATCH["it"].start()
        return _WATCH["it"]


def _trade(ctx):
    """What trading is currently worth, and what it has done lately."""
    setting = td.load_setting()
    body = dict(setting)
    body["rate"] = td.rate_for(setting["credits"])
    body["cap"] = td.MAX_STEP
    body["floor"] = td.SOFT_FLOOR
    body["least"] = None if td.MAX_STEP is None else round(td.SPAN / td.MAX_STEP)
    try:
        w = _watcher(ctx)
        body["running"] = w.running()
        body["error"] = w.error
        body["base"] = w.last_base
        body["history"] = w.history
        body["trace"] = w.trace
    except Exception as exc:                               # noqa: BLE001
        body.update(running=False, error=f"{type(exc).__name__}: {exc}",
                    base=None, history=[], trace=[])
    return body


API = {"engine": _engine, "trade": _trade, "speed": _speed, "thrusters": _thrusters,
       "tradelane": _tradelane, "drawdist": _drawdist, "callsign": _callsign,
       "routetable": _routetable, "empathy": _empathy}

def _set_speed(ctx, sent):
    # Re-located every time: common.dll moves between runs, and the game may
    # have been restarted since the page was loaded.
    with ctx.lock:
        sp.set_speed(float(sent["value"]))
    return f"cruise speed set to {float(sent['value']):g}"


def _set_thrusters(ctx, sent):
    ids, want = int(sent["ids"]), float(sent["value"])
    with ctx.lock:
        th.set_speed(ids, want)
    name = ctx.game.names.get(ids) or th.THRUSTERS.get(ids, ids)
    return f"{name} set to +{want:g}"


def _set_tradelane(ctx, sent):
    with ctx.lock:
        if "uncapped" in sent:
            on, shown = tl.set_cap(bool(sent["uncapped"]))
            return f"speed readout {'uncapped' if on else 'capped'}, max {shown}"
        if "instant" in sent:
            rate, on = tl.set_accel(bool(sent["instant"]))
            return f"wind-up {rate:g}, {'near-instant' if on else 'stock'}"
        if "takeover" in sent:
            # A distance, or a falsy value meaning "take the patch out". The
            # distance is four bytes in the cave once the stub is in, so
            # changing it does not re-patch anything.
            want = sent["takeover"]
            installed, _d, _v = dkd.takeover_state()
            if not want:
                if installed:
                    dkd.takeover_off()
                return f"docking takes over at the stock {dkd.SENTINEL:g} again"
            want = float(want)
            if installed:
                dkd.set_takeover(want)
            else:
                dkd.takeover_on(want)
            return f"docking now takes over at {want:g} for lanes and gates"
        return f"trade lane speed set to {tl.set_speed(float(sent['value'])):g}"


def _set_drawdist(ctx, sent):
    with ctx.lock:
        if sent.get("restore"):
            return f"{dd.restore(ctx.game.dir)} fields back to vanilla"
        factor = float(sent["factor"])
        n = dd.apply(factor, ctx.game.dir)
    return (f"{n} fields scaled to {factor:g}x; takes effect the next time a "
            "system loads")


def _set_callsign(ctx, sent):
    """Set any of the four words. This one writes to a file, not to memory.

    **Not in `allhacks`**, and for the same reason cruise and the thruster
    bonuses are not: these are four choices out of 48, 29, 21 and 21, and
    picking them on the owner's behalf is not "enable".
    """
    with ctx.lock:
        if sent.get("restore"):
            cs.restore(ctx.game.dir)
            return "content.dll back to vanilla; they will call you Freelancer again"
        pick = lambda key: None if sent.get(key) in (None, "") else sent[key]
        state, _kept = cs.write(
            faction=pick("faction"),
            desig=None if pick("desig") is None else int(sent["desig"]),
            wing=None if pick("wing") is None else int(sent["wing"]),
            slot=None if pick("slot") is None else int(sent["slot"]),
            game_dir=ctx.game.dir)
    return (f"they will call you {cs.sentence(ctx.game.dir, state)}; "
            "takes effect the next time a save loads")


def _set_routetable(ctx, sent):
    """Switch which table Set Best Path reads, and write it.

    **The table and the five bytes move together**, which is what `rt.write`
    guarantees: a hole table with the bytes off points the course at a star,
    and gates with them on reads the wrong file.
    """
    with ctx.lock:
        if sent.get("revert"):
            done = rt.revert(ctx.game.dir)
            return f"{len(done)} tables and the five bytes back to shipped"
        mode = sent.get("mode", "gates")
        if mode not in rt.MODES:
            raise ValueError(f"no such mode: {mode}")
        changed, saved = rt.write(ctx.game.dir, "jumps", mode)
    return (f"{mode}: {changed} routes into {rt.MODES[mode]['file']}, "
            f"{saved} jumps saved; load a save")


def _set_trade(ctx, sent):
    """Set the credits-to-friendly figure, and switch the watcher on or off."""
    setting = td.load_setting()
    if "credits" in sent:
        credits = int(sent["credits"])
        if credits <= 0:
            raise ValueError("credits to friendly must be a positive number")
        setting["credits"] = credits
    if "on" in sent:
        setting["on"] = bool(sent["on"])
    td.save_setting(setting)

    w = _watcher(ctx)
    if setting["on"]:
        w.start()
    else:
        w.stop()

    said = [f"{setting['credits']:,} credits of trade from neutral to friendly"]
    if td.MAX_STEP is not None:
        said.append(f"one trade capped at {td.MAX_STEP:+.3f}, so "
                    f"{round(td.SPAN / td.MAX_STEP)} trades at least")
    said.append("watching" if setting["on"] else "not watching")
    if setting["credits"] < td.SOFT_FLOOR:
        said.append(f"That is under {td.SOFT_FLOOR:,}, about one good run, "
                    f"which is a handout rather than a grind, and your call")
    return ". ".join(said)


def _set_empathy(ctx, sent):
    """Set what a Nomad kill is worth to the other 51 factions."""
    with ctx.lock:
        if sent.get("restore"):
            em.restore(ctx.game.dir)
            return "empathy.ini back to shipped; nobody cares about Nomads again"
        kills = float(sent["kills"])
        touched, _kept = em.write(kills, ctx.game.dir)
        em.read(ctx.game.dir)
    if not kills:
        return f"{touched} factions back to indifferent"
    # Assembled from whole sentences and joined once, because appending
    # already-punctuated clauses is how a message grows a double full stop.
    where = "friendly" if kills > 0 else "hostile"
    said = [f"{touched} factions, {abs(kills):.0f} Nomads from neutral to "
            f"{where}; read at startup, so restart the game"]
    if kills < 0:
        said.append("Sirius will mourn every one of them")
    if abs(kills) < em.SOFT_FLOOR:
        said.append(f"That is under {em.SOFT_FLOOR}, fast enough that the "
                    f"ordinary endgame stops being worth flying, and your call")
    return ". ".join(said)


def _set_allhacks(ctx, _sent):
    """Every on/off patch at once, because they are always wanted together.

    Idempotent: each is asked for its current state and only switched if it is
    not already there, so pressing this twice says so rather than toggling
    anything back off. That is the difference between this and the per-box
    buttons, which are toggles by design.

    The knobs with a value in them are deliberately not here. Cruise, the
    thruster bonuses, lane speed and the takeover distance are settings, not
    switches, and picking a number on the owner's behalf is not "enable".
    """
    done = []
    with ctx.lock:
        on, shown = tl.set_cap(True)
        done.append(f"speed readout uncapped to {shown}" if on
                    else "speed readout left capped")
        rate, quick = tl.set_accel(True)
        done.append(f"lane wind-up near-instant at {rate:g}" if quick
                    else f"lane wind-up {rate:g}")
        installed, _d, _v = dkd.takeover_state()
        if installed:
            done.append("docking takeover already in")
        else:
            dkd.takeover_on(dkd.NON_STATION)
            done.append(f"docking takes over at {dkd.NON_STATION:g}")
    return "; ".join(done)


def _set_persist(ctx, _sent):
    with ctx.lock:
        return "; ".join(pe.write(ctx.game.dir))


POST = {"speed": _set_speed, "thrusters": _set_thrusters,
        "tradelane": _set_tradelane, "drawdist": _set_drawdist,
        "allhacks": _set_allhacks, "persist": _set_persist,
        "callsign": _set_callsign, "routetable": _set_routetable,
        "empathy": _set_empathy, "trade": _set_trade}
