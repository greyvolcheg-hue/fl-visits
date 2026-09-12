@echo off
rem Start the server and open the page. Ctrl+C stops it.
rem Any arguments are passed straight to serve.py (--port, --game, a save file).
rem
rem `py` is the launcher the python.org installer puts on PATH. If it is not
rem there, `python serve.py --open %*` is the same thing by another name.
rem
rem Never run: nothing on the Windows side of this project has been.
cd /d "%~dp0"
py serve.py --open %*
