#!/usr/bin/env python3
"""Fingerprint everything `flvisits.py` decides, so a thaw can be checked.

    check_frozen.py > before.txt     # with the committed file
    check_frozen.py > after.txt      # with the edited one
    diff before.txt after.txt        # must be empty

`flvisits.py` unpicks three undocumented formats and resolves a one-way hash by
brute force. Its failure mode is not a crash: it keeps running, keeps printing a
report, and the report is wrong. That is why the file is frozen, and it is the
only reason a thaw needs this.

So the check is not "does it run". It is every value the module derives, over
every save on disk, printed in a stable order and compared byte for byte. The
two earlier thaws were cleared exactly this way.
"""

import glob
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.game import bases as bs  # noqa: E402
from backend.game import flvisits as fl  # noqa: E402

SAVES = os.path.expanduser(
    "~/Games/freelancer-win32/drive_c/users/*/Documents/My Games/"
    "Freelancer/Accts/SinglePlayer/*.fl")


def digest(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def main():
    game = fl.DEFAULT_GAME
    data = fl.ipath(game, "DATA")

    # 1. the hash. Every nickname the game data holds, hashed, in order.
    bases, systems = fl.load_universe(data)
    objects = fl.load_objects(data, systems)
    hashes = {fl.fl_hash(n): n for n in objects}
    print(f"universe   bases={len(bases)} systems={len(systems)} objects={len(objects)}")
    print(f"hashes     unique={len(hashes)} "
          f"digest={digest(''.join(f'{h}:{n}' for h, n in sorted(hashes.items())))}")

    # 2. the string tables out of the resource DLLs.
    names = fl.load_names(game)
    print(f"names      count={len(names)} "
          f"digest={digest(''.join(f'{k}:{v}' for k, v in sorted(names.items())))}")

    # 3. the system file walk.
    files = sorted(f"{s}:{os.path.basename(p)}" for p, s in fl.system_files(data))
    print(f"systemfile count={len(files)} digest={digest('|'.join(files))}")

    # 4. the dockable rule, which both programs take their denominator from.
    dock = bs.dockable_bases(game, data, fl.system_files, fl.ipath)
    print(f"dockable   count={len(dock)} digest={digest('|'.join(sorted(dock)))}")

    # 5. every save decoded, and every visit resolved through the hash.
    total_visits = total_hit = 0
    for path in sorted(glob.glob(SAVES)):
        try:
            text = fl.decode_save(path)
        except (OSError, ValueError) as exc:
            print(f"save {os.path.basename(path):<16} ERROR {exc}")
            continue
        visits = fl.parse_visits(text)
        hit = {h: f for h, f in visits.items() if h in hashes}
        total_visits += len(visits)
        total_hit += len(hit)
        # The resolved set and its flags are the actual product of this file.
        blob = "|".join(f"{hashes[h]}={f}" for h, f in sorted(hit.items()))
        print(f"save {os.path.basename(path):<16} len={len(text)} "
              f"visits={len(visits)} resolved={len(hit)} digest={digest(blob)}")
    print(f"TOTAL      visits={total_visits} resolved={total_hit}")


if __name__ == "__main__":
    main()
