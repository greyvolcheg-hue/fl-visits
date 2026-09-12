"""Map → Jobs: the best-paying board in every system you have opened.

The page half is in `frontend/jobs.py`.
"""


def _jobs(ctx):
    """Every live board, flagged against where the save says you have been.

    The catalogue is static and cached on `GameData`; what this adds is the
    two facts that come out of the save, `docked` and `open`, plus the faction
    labels. Sorting and both filters are the page's job: 160 rows with no
    filter language is the Routes case, not the Equipment one, and the rows are
    already on the page.
    """
    body = {"rows": [], "total": 0, "systems": 0, "open_systems": 0,
            "docked": 0, "error": None}
    try:
        rows = ctx.game.jobs
        seen = ctx.docked()
        # A system is open when at least one base in it has been docked at.
        # The bases you have not landed on inside such a system are the point
        # of the tab: you already know the way there.
        opened = {ctx.game.bases[k][0] for k in seen if k in ctx.game.bases}

        short = ctx.game.faction_short
        full = ctx.game.faction_name
        out = []
        for row in rows:
            board = [dict(job,
                          short=short.get(job["faction"], job["faction"]),
                          label=full.get(job["faction"], job["faction"]))
                     for job in row["board"]]
            out.append(dict(row, board=board,
                            docked=row["id"] in seen,
                            open=row["sys"] in opened))
        body["rows"] = out
        body["total"] = len(out)
        body["systems"] = len({r["sys"] for r in out})
        body["open_systems"] = len(opened)
        body["docked"] = sum(1 for r in out if r["docked"])
    except (OSError, ValueError, KeyError) as exc:
        body["error"] = str(exc)
    return body


API = {"jobs": _jobs}
