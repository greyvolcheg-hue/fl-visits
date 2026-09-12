#!/usr/bin/env python3
"""Live web view of a Freelancer save.

    serve.py [save.fl] [--game DIR] [--port N]

Serves a page that re-reads the save every few seconds, so it keeps up while
you play. With no save argument it follows AutoSave.fl.

**This file routes and nothing else.** What a tab answers is in `backend/`,
what it draws is in `frontend/`, and which tabs exist is in `tabs.py`. The game
data and the per-request save live in `backend/common.py`, because more than
one tab needs them and none of them should have to import a web server to get
at the game.
"""

import argparse
import errno
import glob
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# What "the port is taken" is called. Linux raises EADDRINUSE; Windows raises
# WSAEADDRINUSE (10048), and with `allow_reuse_address` off it also raises
# WSAEACCES (10013) for a port another program holds exclusively.
ADDR_BUSY = {errno.EADDRINUSE, 10048, 10013}

import frontend  # noqa: E402
import tabs  # noqa: E402
from backend.common import Ctx, GameData  # noqa: E402
from backend.game import flvisits as fl  # noqa: E402

SAVE_TAIL = os.path.join(
    "drive_c", "users", "*", "Documents", "My Games",
    "Freelancer", "Accts", "SinglePlayer", "AutoSave.fl",
)
GAME_SAVES = os.path.join("My Games", "Freelancer", "Accts", "SinglePlayer",
                          "AutoSave.fl")


def _wine_saves(game_dir):
    """Every AutoSave.fl in a Wine prefix beside the game.

    The prefix holding the game files is not necessarily the prefix the game
    runs in. On this machine the install lives in an abandoned Proton prefix
    while play happens in a separate win32 one, so searching only the install's
    own prefix finds nothing. Searching the siblings is both simpler and right
    in either layout.
    """
    prefix = game_dir
    for _ in range(6):  # climb out of drive_c/Program Files/... to the prefix
        if os.path.isdir(os.path.join(prefix, "drive_c", "users")):
            break
        parent = os.path.dirname(prefix)
        if parent == prefix:
            break
        prefix = parent

    return (glob.glob(os.path.join(prefix, SAVE_TAIL))
            + glob.glob(os.path.join(os.path.dirname(prefix), "*", SAVE_TAIL)))


def _windows_saves():
    r"""Every AutoSave.fl under this user's Documents.

    **Documents is not always under the profile.** OneDrive moves it, and a
    domain profile can redirect it to a server, so the folder is asked for
    rather than assumed: `HKCU\Software\Microsoft\Windows\CurrentVersion\
    Explorer\Shell Folders`, value `Personal`, which is where Windows itself
    looks. `~/Documents` is the fallback when the value is missing.

    Not tested on Windows.
    """
    roots = []
    try:
        import winreg  # noqa: PLC0415 - Windows only, and imported only there
        with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                r"\Shell Folders") as key:
            roots.append(winreg.QueryValueEx(key, "Personal")[0])
    except (ImportError, OSError):
        pass
    roots.append(os.path.expanduser(os.path.join("~", "Documents")))
    return [p for p in (os.path.join(r, GAME_SAVES) for r in roots)
            if os.path.exists(p)]


def find_default_save(game_dir):
    """The freshest AutoSave.fl this machine has, or None.

    Where to look is the only thing that differs between the two platforms;
    **"newest wins" is the rule on both**, and it lives here rather than in
    either finder so that it cannot come to mean two things.
    """
    candidates = (_windows_saves() if sys.platform == "win32"
                  else _wine_saves(game_dir))
    if not candidates:
        return None
    return max(set(candidates), key=os.path.getmtime)


# --- the page -------------------------------------------------------------
#
# Assembled from the frontend modules, in the order `tabs.py` gives. The script
# is still one inline block: a parse error anywhere in it takes all of it,
# which is worth knowing but not worth splitting into files a browser would
# fetch one at a time.

PAGES = [frontend.shell] + [m for m in tabs.PAGES.values() if m]

PAGE = f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Freelancer visits</title>
<style>{frontend.css(PAGES)}</style>
{frontend.read("_shell.html")}
<script>
const $ = s => document.querySelector(s);
const TABS = {json.dumps(tabs.tabs())};
// Views register into this; see frontend/shell.py for the shape.
const VIEW = {{}};
{frontend.js(PAGES)}
{frontend.shell.BOOT}
</script>
"""


def make_handler(game, save_path):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype, cache="no-store"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            # Everything here reads a live save or a running game. A tab's own
            # FILES entry is what says otherwise, and the chart is the one that
            # does: 840 KB that never changes.
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, body):
            self._send(200, json.dumps(body).encode("utf-8"), "application/json")

        def _ctx(self):
            return Ctx(game, save_path, lock, parse_qs(urlparse(self.path).query))

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            name = path[len("/api/"):] if path.startswith("/api/") else None
            served = tabs.FILES.get(path.lstrip("/"))
            if path in ("/", "/index.html"):
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif name in tabs.GET:
                try:
                    self._json(tabs.GET[name](self._ctx()))
                except FileNotFoundError:
                    # The save the page follows is gone or not written yet.
                    # That is a missing thing, not a broken endpoint, and it
                    # reads far better on the page than a stack trace.
                    self._send(404, b'{"error":"save not found"}',
                               "application/json")
            elif served:
                ctype, file_path, cache = served
                try:
                    with open(file_path, "rb") as fh:
                        self._send(200, fh.read(), ctype, cache)
                except OSError:
                    self._send(404, b"not found", "text/plain")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            name = self.path.split("?", 1)[0][len("/api/"):]
            if name not in tabs.SET:
                self._send(404, b"not found", "text/plain")
                return
            size = int(self.headers.get("Content-Length") or 0)
            try:
                sent = json.loads(self.rfile.read(size) or b"{}")
            except ValueError:
                sent = {}
            ctx = self._ctx()
            ok, note = True, None
            try:
                note = tabs.SET[name](ctx, sent)
            except Exception as exc:  # noqa: BLE001 - any failure is a message
                # A write that failed is a note on the panel, not a broken
                # panel. The reading below is re-read either way, so it shows
                # what is actually true rather than a synthesised blank.
                ok, note = False, str(exc)
            body = tabs.GET[name](ctx) if name in tabs.GET else {}
            body["message"] = note
            body.setdefault("ok", ok)
            self._json(body)

        def log_message(self, *args):
            pass  # a poll every five seconds would bury anything worth reading

    return Handler


class Server(ThreadingHTTPServer):
    """**Refuses a port somebody else is holding, on both platforms.**

    `HTTPServer` sets `allow_reuse_address`, which on Linux means "bind over a
    socket still in TIME_WAIT" and is what lets this be restarted immediately
    after Ctrl+C. **On Windows the same flag means something else entirely**:
    `SO_REUSEADDR` there lets a second program bind a port another program is
    actively listening on, and which of the two gets a given connection is
    undefined. So it stays on where it is useful and goes off where it would
    hand somebody a page served by a process they thought they had replaced.
    """

    allow_reuse_address = sys.platform != "win32"


def _taken(host, port):
    """What to say when the port is held, including how to get it back.

    This refusal used to be a `/dev/tcp` probe in `run.sh`, where it could only
    ever be a guess: the script looked, decided the port was free, started the
    server and never found out whether it bound. It is here now because this is
    the only party that knows. What it prevents is the bad outcome from
    2026-09-12, where `serve.py` failed to bind and exited, the **old** server
    answered the wait loop, and the browser opened on a page whose new tab was
    missing because the code behind it was an hour old.
    """
    if sys.platform == "win32":
        how = (f"  netstat -ano | findstr :{port}\n"
               f"  taskkill /PID <the pid that prints> /F")
    else:
        how = ("  kill $(ss -ltnp | awk -F'pid=' "
               f"'/:{port} /{{split($2,p,\",\"); print p[1]}}')")
    return (f"something is already listening on {host}:{port}, so this did "
            f"not start.\nStop it first:\n{how}\n"
            f"or run this one somewhere else:  --port {port + 1}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("save", nargs="?", help="save to follow (default: AutoSave.fl)")
    ap.add_argument("--game", default=fl.DEFAULT_GAME)
    ap.add_argument("--port", type=int, default=8731)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--open", action="store_true",
                    help="open a browser on the page once it is listening")
    args = ap.parse_args()

    save = args.save or find_default_save(args.game)
    if not save or not os.path.exists(save):
        sys.exit("no save file found; pass one as an argument")

    # **The port is claimed before the game data is loaded**, so a refusal is
    # immediate rather than half a second of parsing that looks like it worked.
    # Bound now and handled later: the handler needs the game data, and
    # `BaseServer` reads `RequestHandlerClass` only when a request arrives, so
    # filling it in after the bind is exactly as good as passing it in.
    try:
        server = Server((args.host, args.port), None)
    except OSError as exc:
        sys.exit(_taken(args.host, args.port) if exc.errno in ADDR_BUSY
                 else f"cannot listen on {args.host}:{args.port}: {exc}")

    started = time.time()
    game = GameData(args.game)
    print(f"game data loaded in {time.time() - started:.2f}s "
          f"({len(game.bases)} bases, {len(game.names)} strings)")
    print(f"following {save}")
    url = f"http://{args.host}:{args.port}/"
    print(url)

    server.RequestHandlerClass = make_handler(game, save)
    if args.open:
        # The socket is already listening, so a browser that connects before
        # `serve_forever` starts waits in the backlog rather than failing.
        # `webbrowser` is `xdg-open` on Linux and `ShellExecute` on Windows.
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
