"""Speed: cruise, thrusters, trade lanes, docking and draw distance, live.

The page half is in `frontend/speed.py`.
"""

from .live import bestpath as bp
from .live import dockdist as dkd
from .live import drawdist as dd
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
# A multiple of each field's own vanilla value. Geometry grows with the cube of
# the radius, so 2x is roughly 8x the rocks.
DRAWDIST_CHOICES = [1, 1.25, 1.5, 2]


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


def _bestpath(ctx):
    """Whether the router is using jump holes, or why it cannot say."""
    body = {"on": False, "version": None, "slots": [],
            "error": None}
    try:
        # One pid lookup and one build detection for the whole reply.
        # state() and routes() each used to do both, so a poll cost
        # two /proc scans and two fingerprint reads to return 3 bytes.
        pid = sp.find_pid()
        version, _kind = bp.detect(pid)
        body["on"], _v = bp.state(pid, version)
        body["version"] = version
        body["slots"] = [{"at": at, "file": name}
                         for at, name in bp.routes(pid, version)]
    except (bp.NotRunning, OSError) as exc:
        body["error"] = str(exc)
    return body


API = {"speed": _speed, "thrusters": _thrusters, "tradelane": _tradelane, "drawdist": _drawdist, "bestpath": _bestpath}

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
            # A toggle: the distance is a setting, not a choice made here, and
            # only the game can say which way the patch is now.
            installed, _d, _v = dkd.takeover_state()
            if installed:
                dkd.takeover_off()
                return f"docking takes over at the stock {dkd.SENTINEL:g} again"
            dkd.takeover_on(dkd.NON_STATION)
            return (f"docking now takes over at {dkd.NON_STATION:g} "
                    "for lanes and gates")
        return f"trade lane speed set to {tl.set_speed(float(sent['value'])):g}"


def _set_drawdist(ctx, sent):
    with ctx.lock:
        if sent.get("restore"):
            return f"{dd.restore(ctx.game.dir)} fields back to vanilla"
        factor = float(sent["factor"])
        n = dd.apply(factor, ctx.game.dir)
    return (f"{n} fields scaled to {factor:g}x; takes effect the next time a "
            "system loads")


def _set_bestpath(ctx, _sent):
    with ctx.lock:
        pid = sp.find_pid()
        version, _kind = bp.detect(pid)
        on, _v = bp.state(pid, version)
        bp.apply(not on, pid, version)
    return "back to jump gates only" if on else "routing through jump holes"


def _set_persist(ctx, _sent):
    with ctx.lock:
        return "; ".join(pe.write(ctx.game.dir))


POST = {"speed": _set_speed, "thrusters": _set_thrusters,
        "tradelane": _set_tradelane, "drawdist": _set_drawdist,
        "bestpath": _set_bestpath, "persist": _set_persist}
