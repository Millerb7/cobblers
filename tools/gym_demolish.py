#!/usr/bin/env python
"""Fill in the five sets of underground gym works and take down the five donor shells over them.

The owner rejected the pattern on sight (docs/world-building/GYM_BUILDINGS_BRIEF.md): "a scaffold to a cave feels
dumb every time, i get it on misty, thats the way to go up, but id rather have a large gym building with a puzzle
inside than whatever that was". So at gyms 1, 3, 4, 5 and 7 the carve goes back to rock and the COBBLEVERSE shell
comes down, and an authored hall (tools/gym_buildings.py) is built on the lot instead.

GYM 2 IS NEVER TOUCHED. Misty's hall stands on the template's own rock plinth and going down her well is the
building; the owner said so explicitly. This tool refuses to act on gym2 even if a record asks it to.

  python tools/gym_demolish.py report [--source-root <root>]
  python tools/gym_demolish.py build  [--out build/datapacks/cobblers_gym_demolish] [--source-root <root>]

What it writes, one function per gym (`cobblers:gym_demolish/<id>`):

  the works    every cell of data/gym_interiors.json gyms[<id>].dig set back to stone where it is under the
               ground, and to air where it is over it
  the shell    the same rule over the shell's box, derived from data/placements.json through tools/place_donor.py
               - so the template's walls, its floor, its 9 command blocks, its pressure plate and its own
               rctmod:trainer_spawner all go. After this the only kanto_brock in the town is the one the gym
               building puts at the head of its puzzle.

Where the ground comes from: the heightmap through tools/ground.py, rounded, and the gym lot's `level` from the
town plan in data/placements.json wherever a column lies on the levelled pad (the prep cuts and fills the lot to
that number, so on the pad that IS the ground). Never from a world save - which matters more here than anywhere
else, because the world under these five gyms currently holds the carve this tool is undoing, and a tool that
read it would restore the hole it is there to fill (the ground rule, tests/test_ground_rule.py).

What it does not do: entities. The templates place blocks and block entities only, so a fill removes everything
they stamped. The one exception is Brock's "Kanto Map Guide" villager, which exists only if somebody has stood on
the template's pressure plate before the shell came down (EXP-013 C); if one is standing in a demolished gym it
has to be removed by hand.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402
import ground as ground_mod  # noqa: E402
import place_donor  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_gym_demolish"
FUNCS = PACK / "data" / "cobblers" / "function" / "gym_demolish"
REPORT = ROOT / "derived" / "gym_buildings"
INTERIORS = ROOT / "data" / "gym_interiors.json"
PLACEMENTS = ROOT / "data" / "placements.json"
ROCK = "minecraft:stone"
AIR = "minecraft:air"
KEEP = "gym2"

# The ground rule (tools/ground_rule.py): nothing here reads a world at all.
WORLD_READS = set()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def superseded():
    """The gym records this tool acts on: every one that names the building that replaces it. Never gym 2."""
    doc = load(INTERIORS)
    out = []
    for g in doc.get("gyms") or []:
        if not g.get("superseded_by"):
            continue
        if g["id"] == KEEP:
            raise SystemExit("data/gym_interiors.json marks %s superseded. Misty's gym is kept exactly as built "
                             "and this tool will not touch it (the owner, 2026-09-29)." % KEEP)
        if not (g.get("shell") or {}).get("expect_box"):
            raise SystemExit("%s: a superseded gym needs `shell.expect_box`" % g["id"])
        # `dig` is the carved works under the gym, filled back to rock. Gyms 6 and 8 never had any: they
        # were donor shells on open lots and nothing was ever cut below them, so there is nothing to fill
        # and a demanded `dig` would have to be invented. Absence must still be DECLARED, not inferred from
        # a missing key, or a record that simply forgot its works would demolish the shell and leave the
        # works open. `works_existed: false` is that declaration.
        if not g.get("dig") and g.get("works_existed") is not False:
            raise SystemExit("%s: a superseded gym needs `dig`, or `works_existed: false` to say there were "
                             "never any works under it" % g["id"])
        if g.get("dig") and g.get("works_existed") is False:
            raise SystemExit("%s: declares `works_existed: false` and still has a `dig` box; one of them is "
                             "wrong" % g["id"])
        out.append(g)
    if not out:
        raise SystemExit("no gym in data/gym_interiors.json is `superseded_by` anything; there is nothing to "
                         "demolish (fail closed)")
    return out


def lot_of(settlement, placements):
    """(rect, level) of the settlement's gym lot, or (None, None) when the plan has no levelled gym lot."""
    plan = (placements.get("settlements") or {}).get(settlement) or {}
    for a in (plan.get("plan") or {}).get("anchors") or []:
        if a.get("role") == "gym" and a.get("level") is not None:
            return list(a["rect"]), int(a["level"])
    return None, None


def ground_fn(settlement, placements, G):
    """(x, z) -> the Y of the topmost solid block a rebuilt world has there: the lot's level on the levelled
    pad, the heightmap everywhere else."""
    rect, level = lot_of(settlement, placements)
    if rect is None:
        return lambda x, z: G(x, z), None
    x0, z0, x1, z1 = rect

    def gy(x, z):
        return level if x0 <= x <= x1 and z0 <= z <= z1 else G(x, z)

    return gy, (rect, level)


def rects(x0, z0, x1, z1, gy):
    """The box as (x0, x1, z0, z1, ground) rectangles of equal ground: runs along x, then merged over z."""
    rows = []
    for z in range(z0, z1 + 1):
        runs, start, cur = [], x0, gy(x0, z)
        for x in range(x0 + 1, x1 + 2):
            v = gy(x, z) if x <= x1 else None
            if v != cur:
                runs.append((start, x - 1, cur))
                start, cur = x, v
        rows.append((z, runs))
    out, i = [], 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1][1] == rows[i][1]:
            j += 1
        for a, b, v in rows[i][1]:
            out.append((a, b, rows[i][0], rows[j][0], v))
        i = j + 1
    return out


def box_commands(box, gy, why):
    """Rock back under the ground, air over it, for every column of the box."""
    x0, y0, z0, x1, y1, z1 = box
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    z0, z1 = min(z0, z1), max(z0, z1)
    out, rock, air = ["# %s" % why], 0, 0
    for a, b, c, d, g in rects(x0, z0, x1, z1, gy):
        if y0 <= g:
            out.append("fill %d %d %d %d %d %d %s" % (a, y0, c, b, min(g, y1), d, ROCK))
            rock += (b - a + 1) * (d - c + 1) * (min(g, y1) - y0 + 1)
        if g < y1:
            out.append("fill %d %d %d %d %d %d %s" % (a, max(y0, g + 1), c, b, y1, d, AIR))
            air += (b - a + 1) * (d - c + 1) * (y1 - max(y0, g + 1) + 1)
    return out, rock, air


def gym_commands(gym, placements, G):
    rec = {p["id"]: p for p in placements["placements"] if isinstance(p, dict) and p.get("id")}[gym["donor"]]
    (sx0, sy0, sz0), (sx1, sy1, sz1) = place_donor.box(rec)
    shell = [sx0, sy0, sz0, sx1, sy1, sz1]
    if shell != gym["shell"]["expect_box"]:
        raise SystemExit("%s: the shell box derived from data/placements.json is %s but the record expects %s; "
                         "the placement moved and the demolition must be re-fitted"
                         % (gym["id"], shell, gym["shell"]["expect_box"]))
    gy, lot = ground_fn(rec["settlement"], placements, G)
    lines = ["# %s (%s): the works filled in and the donor shell taken down (tools/gym_demolish.py)."
             % (gym["id"], gym.get("leader_name") or rec["settlement"]),
             "# %s" % gym["superseded_by"],
             "# ground: %s" % ("the gym lot %s levelled to y%d, the heightmap outside it" % (lot[0], lot[1])
                               if lot else "the heightmap (tools/ground.py, rounded)")]
    if gym.get("dig"):
        a, r1, v1 = box_commands(gym["dig"], gy, "the works, back to rock")
    else:
        # `works_existed: false`, checked in superseded(): nothing was ever cut under this gym, so the
        # demolition is the shell alone and the works pass writes no command rather than a vacuous one.
        a, r1, v1 = [], 0, 0
        lines.append("# no works under this gym: it was a donor shell on an uncut lot, so only the shell comes down")
    b, r2, v2 = box_commands(shell, gy, "the donor shell, and the ground it stood on")
    lines += a + b
    return lines, {"id": gym["id"], "donor": gym["donor"], "settlement": rec["settlement"],
                   "dig": gym.get("dig"), "shell_box": shell, "lot": lot[0] if lot else None,
                   "lot_level": lot[1] if lot else None,
                   "rock_cells": r1 + r2, "air_cells": v1 + v2,
                   "commands": len([l for l in lines if not l.startswith("#")])}


def write_function(name, lines):
    cmds = function_limits.ensure_loaded(lines)
    refused = function_limits.check_lines(cmds, name)
    if refused:
        raise SystemExit("%s: %d command(s) the server would refuse: %s" % (name, len(refused), refused[:3]))
    (FUNCS / ("%s.mcfunction" % name)).write_text("\n".join(cmds) + "\n", encoding="utf-8")
    return cmds


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("report", "build"):
        q = sub.add_parser(name)
        q.add_argument("--source-root", default=None)
        if name == "build":
            q.add_argument("--out", default=str(PACK))
    a = p.parse_args(argv)
    if a.source_root:
        import os
        os.environ["COBBLERS_SOURCE_ROOT"] = a.source_root

    placements = load(PLACEMENTS)
    G = ground_mod.load()
    gyms = superseded()
    done, rows = [], []
    if a.cmd == "build":
        if PACK.exists():
            shutil.rmtree(PACK)
        FUNCS.mkdir(parents=True)
        (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                          "Cobblers: the rejected gym works filled in and their donor shells "
                                          "taken down (tools/gym_demolish.py)"}}, indent=2) + "\n",
                                          encoding="utf-8")
    for gym in gyms:
        lines, row = gym_commands(gym, placements, G)
        rows.append(row)
        if a.cmd == "build":
            write_function(gym["id"], lines)
            done.append(gym["id"])
        print("%s: %d commands, %d cells back to rock, %d to air (shell %s, dig %s)"
              % (row["id"], row["commands"], row["rock_cells"], row["air_cells"], row["shell_box"], row["dig"]))
    if a.cmd == "build":
        (FUNCS / "index.txt").write_text("\n".join(done) + "\n", encoding="utf-8")
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "demolish.json").write_text(json.dumps({"note": "gym 2 is never here: Misty's gym is kept exactly "
                                                     "as built.", "gyms": rows}, indent=1) + "\n",
                                          encoding="utf-8")
    if a.cmd == "build":
        print("wrote", PACK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
