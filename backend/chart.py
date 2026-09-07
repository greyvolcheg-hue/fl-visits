"""Map → Chart: the sector map, as a picture.

The page half is in `frontend/chart.py`.
"""

import os

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data")

# The chart is the one thing a tab serves that is not JSON, so this is where a
# tab gets to say "and this file, at this URL". `serve.py` carried a branch for
# `/map.jpg` by name until 2026-09-07, which meant a second such file would
# have wanted a second branch in a module that should not know about charts.
#
# Cached for a day: 840 KB that never changes, on a page that redraws every
# five seconds.
FILES = {"map.jpg": ("image/jpeg", os.path.join(DATA, "freelancer-map.jpg"),
                     "public, max-age=86400")}
