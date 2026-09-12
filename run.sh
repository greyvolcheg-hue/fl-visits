#!/usr/bin/env bash
# Start the server and open the page. Ctrl+C stops both.
# Any arguments are passed straight to serve.py (--port, --game, a save file).
set -u

cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

# The port is read out of the arguments rather than assumed: passing
# `--port 8732` used to start the server there and then wait on 8731 forever.
PORT=8731
for i in $(seq $#); do
    [ "${!i}" = "--port" ] && { j=$((i + 1)); PORT="${!j}"; }
done
URL="http://127.0.0.1:$PORT/"

# **Refuse to start on a port somebody already holds.** Without this the script
# looks like it worked and silently serves the old code: `serve.py` fails to
# bind and exits, the wait loop below connects on its very first try because
# the *old* server answers, and `xdg-open` puts a browser on it. The only sign
# is a bind error in a terminal nobody is reading. That cost a restart that
# was never a restart on 2026-09-12, with a new tab that had gone missing.
# The probe runs in a subshell, so its fd 3 dies with it and there is nothing
# here to close. Do not add `exec 3<&- 2>/dev/null`: `exec` carrying only
# redirections applies them to this script for good, and that one sends every
# line below to /dev/null. Written after doing exactly that.
if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
    echo "something is already listening on 127.0.0.1:$PORT." >&2
    echo "Stop it first:  kill \$(ss -ltnp | awk -F'pid=' '/:$PORT /{split(\$2,p,\",\"); print p[1]}')" >&2
    echo "or run this one somewhere else:  ./run.sh --port 8732" >&2
    exit 1
fi

python3 serve.py "$@" &
server=$!

# Wait for the port instead of sleeping a fixed guess: loading the game data
# takes about a fifth of a second, but a cold disk makes that several.
for _ in $(seq 100); do
    (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null && break
    kill -0 "$server" 2>/dev/null || { wait "$server"; exit $?; }
    sleep 0.1
done

xdg-open "$URL" >/dev/null 2>&1

wait "$server"
