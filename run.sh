#!/usr/bin/env bash
# Start the server and open the page. Ctrl+C stops both.
# Any arguments are passed straight to serve.py (--port, --game, a save file).
set -u

cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

PORT=8731
URL="http://127.0.0.1:$PORT/"

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
