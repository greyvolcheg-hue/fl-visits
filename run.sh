#!/usr/bin/env bash
# Start the server and open the page. Ctrl+C stops it.
# Any arguments are passed straight to serve.py (--port, --game, a save file).
#
# **There is nothing left in here to get wrong, and that is the point.** This
# used to probe the port itself and then wait for it, which is a guess twice
# over: the script cannot know whether `serve.py` got the port, and on
# 2026-09-12 it started a browser on an hour-old server for exactly that
# reason. The refusal and the browser both live in `serve.py` now, because that
# is the only party that knows whether it bound. `run.cmd` is the same three
# lines for Windows. See CLAUDE.md for the whole account, the `exec 3<&-`
# trap included.
set -u

cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
exec python3 serve.py --open "$@"
