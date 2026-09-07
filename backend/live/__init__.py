"""The only code in the project that writes anything.

Two kinds, and they are not interchangeable:

    process memory   speed, thrusters, tradelane, dockdist, bestpath, inject.
                     Lasts until the game is closed, and a relaunch reverts it.
    game files       persist, drawdist, newgame. Each keeps a `.vanilla` copy
                     the first time and never overwrites an existing one.
"""
