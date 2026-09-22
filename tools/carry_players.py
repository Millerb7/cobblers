#!/usr/bin/env python
"""Carry every player's state from a stopped old world into a fresh export, so a re-export keeps what players earned.

A re-export builds a new world directory; without this step every player joins it with nothing: no party, no
Pokedex, no badges, no badge flags (the flags are advancements, `cobblers:flag/<id>`, in `advancements/`), and
rctmod forgets which trainers they beat, which also resets their level cap. Carried:

  advancements/  playerdata/  stats/                   vanilla: the badge flags, inventories, statistics
  cobblemonplayerdata/  pokedex/  pokemon/             Cobblemon 1.8: player data and quest fields, Pokedex, party and PC
  cobbledollarsplayerdata/                             CobbleDollars balances
  data/rctmod.player.*.dat  data/rctmod.trainers.*     rctmod: each player's series progress and each trainer's defeats
  data/scoreboard.dat                                  per-player scores

Not carried: region, entity and POI files (the new terrain replaces them), waystones.dat (the waystones stand in new
places), Distant Horizons' cache.

  python tools/carry_players.py --from <stopped old world copy> --to <new world>

Both must be outside the live server runtime (tools/runtime_guard.py). It refuses to overwrite: a fresh export has
no player files, so finding one in --to means --to is not a fresh export. It fails closed: an old world with no
player to carry fails, and every file is checked by sha256 after the copy.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import runtime_guard  # noqa: E402

PLAYER_DIRS = ("advancements", "playerdata", "stats", "cobblemonplayerdata", "pokedex", "pokemon",
               "cobbledollarsplayerdata")
DATA_GLOBS = ("rctmod.player.*.dat", "rctmod.trainers.*", "scoreboard.dat")


def to_carry(old: Path) -> list:
    """Every file to carry, relative to the world directory."""
    rel = []
    for d in PLAYER_DIRS:
        if (old / d).is_dir():
            rel += [p.relative_to(old) for p in sorted((old / d).rglob("*")) if p.is_file()]
    for g in DATA_GLOBS:
        rel += [p.relative_to(old) for p in sorted((old / "data").glob(g)) if p.is_file()]
    return rel


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def carry(old: Path, new: Path) -> int:
    old = runtime_guard.check(old, "carry players from")
    new = runtime_guard.check(new, "carry players into")
    for w, what in ((old, "--from"), (new, "--to")):
        if not (w / "level.dat").is_file():
            print("FAIL: %s %s has no level.dat: not a world" % (what, w))
            return 1
    files = to_carry(old)
    players = [f for f in files if f.parts[0] == "playerdata" and f.suffix == ".dat"]
    if not players:
        print("FAIL: %s has no player in playerdata/: nothing to carry" % old)
        return 1
    clash = [f for f in files if (new / f).exists()]
    if clash:
        print("FAIL: %d of the files to carry already exist in %s (first: %s): not a fresh export"
              % (len(clash), new, clash[0]))
        return 1
    for f in files:
        (new / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old / f, new / f)
    bad = [f for f in files if sha(old / f) != sha(new / f)]
    if bad:
        print("FAIL: %d files differ after the copy (first: %s)" % (len(bad), bad[0]))
        return 1
    by_top = {}
    for f in files:
        top = f.parts[0] if f.parts[0] != "data" else "data/" + f.name.split(".")[0]
        by_top[top] = by_top.get(top, 0) + 1
    print("carried %d files for %d players, all matching by sha256: %s"
          % (len(files), len(players), ", ".join("%s %d" % kv for kv in sorted(by_top.items()))))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="old", type=Path, required=True, help="the stopped old world copy")
    ap.add_argument("--to", dest="new", type=Path, required=True, help="the fresh export")
    a = ap.parse_args(argv)
    try:
        return carry(a.old, a.new)
    except runtime_guard.RuntimeAccessRefused as e:
        print("refused: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
