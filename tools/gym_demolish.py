#!/usr/bin/env python
"""Fill in the underground gym works and take down the donor shells over them.

The owner rejected the pattern on sight (docs/world-building/GYM_BUILDINGS_BRIEF.md): "a scaffold to a cave feels
dumb every time, i get it on misty, thats the way to go up, but id rather have a large gym building with a puzzle
inside than whatever that was". So at gyms 1, 3, 4, 5 and 7 the carve goes back to rock and the COBBLEVERSE shell
comes down, and an authored hall (tools/gym_buildings.py) is built on the lot instead.

GYM 2 TOO, since 2026-10-09. Misty's was kept (the owner, 2026-09-29) until the owner reversed it: "Misty needs to
have the template building removed, make it match the rest of the world." Its record names the walk-through hall
that replaces it (data/gym_arenas/gym2.json), whose bounds take in the whole template; so here, below and beside that
hall, the works (the well, cistern, race and ledger gallery) go back to rock, the template's quay plinth (data/
placements.json gym2_misty_gym `plinth`, derived from the record like the shell) comes out, and the old boat house's
never-built shore stair box (the hall's replaces.arena.exit_passages) is set back to the ground. Misty's lot is on
the lake shore, so every box here is restored to the WATER where tools/bridges.py water() says there is water: rock to
the ground, the lake (or river, or sea) from there to its level, air above it. At Misty's lot the mask puts no water
in any of those boxes (the lake's edge is z2896 at its nearest), which this tool reports rather than assumes.

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
WATER = "minecraft:water"

# The ground rule (tools/ground_rule.py): nothing here reads a world at all.
WORLD_READS = set()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def superseded():
    """The gym records this tool acts on: every one that names the building that replaces it."""
    doc = load(INTERIORS)
    out = []
    for g in doc.get("gyms") or []:
        if not g.get("superseded_by"):
            continue
        if g.get("built"):
            raise SystemExit("%s: data/gym_interiors.json marks it both `built` and `superseded_by`: R16E would carve "
                             "the works this step fills in, every apply" % g["id"])
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


def water_fn(G, boxes):
    """((x, z) -> the water level y where tools/bridges.py water() marks the column wet, else None; wet column count)
    over the window holding `boxes`. The same committed water the export paints (lakes' basins at their level, cut
    river courses, the sea), from the heightmap, never from a world."""
    import bridges
    x0, z0 = min(b[0] for b in boxes), min(b[2] for b in boxes)
    x1, z1 = max(b[3] for b in boxes), max(b[5] for b in boxes)
    level, wet, _definite = bridges.water(G.heights, G.world, (x0, z0, x1, z1))

    def f(x, z):
        if x0 <= x <= x1 and z0 <= z <= z1 and wet[z - z0, x - x0]:
            return int(level[z - z0, x - x0])
        return None

    cols = {(x, z) for b in boxes for x in range(b[0], b[3] + 1) for z in range(b[2], b[5] + 1)}
    return f, sum(1 for c in cols if f(*c) is not None)


def box_commands(box, gy, why, reserved=(), wl=None):
    """Rock back under the ground, the water from there to its level where `wl` (water_fn) says the column is wet,
    air over that, for every column of the box -- except inside `reserved`, the volumes only a gym's own arena or
    hall function may write (tools/gym_arenas.py reserved_boxes). Returns (lines, rock, air, water) cell counts.

    THE DEFECT THIS EXCLUSION CLOSES (2026-10-09, "a room I can't leave from"): this step runs every apply, BEFORE
    the arenas (R16GA). The works it refills (gyms 1, 3, 4, 5, 7) and the shells it clears overlap the arenas
    carved under the lots since 2026-10-09, so a run of R16F that R16GA did not follow (`--only R16F`, or an apply
    that stopped between them) filled the arena -- and anyone standing in it -- with stone. The arena's own
    function writes every cell of its volume (shell, then carve), so leaving it alone here loses nothing."""
    import gym_arenas
    x0, y0, z0, x1, y1, z1 = box
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    z0, z1 = min(z0, z1), max(z0, z1)
    out, rock, air, water = ["# %s" % why], 0, 0, 0

    def emit(b, state):
        n = 0
        parts = [b]
        for r in reserved:
            parts = [q for p_ in parts for q in gym_arenas.box_minus(p_, r)]
        for q in parts:
            out.append("fill %d %d %d %d %d %d %s" % (q[0], q[1], q[2], q[3], q[4], q[5], state))
            n += (q[3] - q[0] + 1) * (q[4] - q[1] + 1) * (q[5] - q[2] + 1)
        return n

    def key(x, z):
        return (gy(x, z), wl(x, z) if wl else None)

    for a, b, c, d, (g, lv) in rects(x0, z0, x1, z1, key):
        if lv is not None and lv <= g:
            # wet but not definite (tools/bridges.py: the paint's water, h < level, over a ground that rounds to the
            # level or above, so h >= level - 0.5): the export may or may not stand water on it. Under the level the
            # ground is certain and goes back to rock; the level's own course is not written -- the world keeps
            # whether it is water or bank -- and only the air over it is restored
            if y0 <= lv - 1:
                rock += emit((a, y0, c, b, min(lv - 1, y1), d), ROCK)
            if lv < y1:
                air += emit((a, max(y0, lv + 1), c, b, y1, d), AIR)
            continue
        if y0 <= g:
            rock += emit((a, y0, c, b, min(g, y1), d), ROCK)
        top = g
        if lv is not None and lv > g:
            if max(y0, g + 1) <= min(lv, y1):
                water += emit((a, max(y0, g + 1), c, b, min(lv, y1), d), WATER)
            top = lv
        if top < y1:
            air += emit((a, max(y0, top + 1), c, b, y1, d), AIR)
    if reserved:
        out.insert(1, "# never inside the gym's arena or hall (tools/gym_arenas.py reserved_boxes): %s"
                   % [list(r) for r in reserved])
    return out, rock, air, water


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
    import gym_arenas
    import gym_buildings as GB
    # never inside the gym's arena or hall, nor inside the box its building clears and rebuilds every run (R16G):
    # this step runs before both, so whatever it wrote there was theirs to write again, and run alone (`--only
    # R16F`) it took the standing building down round anyone inside it (tools/gym_arenas_audit.py ORDER)
    reserved = list(gym_arenas.reserved_boxes(gym["id"]))
    bdoc = {d["id"]: d for _p, d in GB.records()}.get(gym["id"])
    if bdoc and not bdoc.get("superseded_by") and GB.clear_box(bdoc):
        reserved.append(tuple(GB.clear_box(bdoc)))
    # what else of the donor this step restores, each derived from a record, never authored as a box here: the
    # template's quay plinth (data/placements.json `plinth`: tools/place_donor.py fills air and water with it from
    # `from_y` to the course under the template, over the template's footprint), and, where a walk-through hall
    # replaced an arena that declared a way out to the surface, that passage's box (replaces.arena.exit_passages)
    extra = []
    plinth = rec.get("plinth")
    if plinth:
        extra.append(([sx0, int(plinth.get("from_y", sy0 - 9)), sz0, sx1, sy0 - 1, sz1],
                      "the template's quay plinth (%s from y%s, data/placements.json %s plinth), back to the ground"
                      % (plinth.get("material"), plinth.get("from_y"), gym["donor"])))
    hall = gym_arenas.record_of(gym["id"])
    if gym_arenas.is_hall(hall):
        for p_ in ((hall.get("replaces") or {}).get("arena") or {}).get("exit_passages") or []:
            extra.append((list(gym_arenas.norm(p_["box"])), "the replaced arena's way out %s "
                          "(data/gym_arenas/%s.json replaces.arena.exit_passages), back to the ground"
                          % (p_.get("id"), gym["id"])))
    boxes = ([gym["dig"]] if gym.get("dig") else []) + [shell] + [b_ for b_, _w in extra]
    wl, wet_n = water_fn(G, [gym_arenas.norm(b_) for b_ in boxes])
    if wet_n:
        lines.append("# water: tools/bridges.py water() marks %d column(s) of these boxes wet; they are set back to "
                     "their water level" % wet_n)
    else:
        lines.append("# water: tools/bridges.py water() marks no column of these boxes wet, so no water is written")
    if gym.get("dig"):
        a, r1, v1, w1 = box_commands(gym["dig"], gy, "the works, back to rock", reserved, wl)
    else:
        # `works_existed: false`, checked in superseded(): nothing was ever cut under this gym, so the
        # demolition is the shell alone and the works pass writes no command rather than a vacuous one.
        a, r1, v1, w1 = [], 0, 0, 0
        lines.append("# no works under this gym: it was a donor shell on an uncut lot, so only the shell comes down")
    b, r2, v2, w2 = box_commands(shell, gy, "the donor shell, and the ground it stood on", reserved, wl)
    lines += a + b
    r3 = v3 = w3 = 0
    for box, why in extra:
        c, r_, v_, w_ = box_commands(box, gy, why, reserved, wl)
        lines += c
        r3, v3, w3 = r3 + r_, v3 + v_, w3 + w_
    return lines, {"id": gym["id"], "donor": gym["donor"], "settlement": rec["settlement"],
                   "dig": gym.get("dig"), "shell_box": shell, "lot": lot[0] if lot else None,
                   "lot_level": lot[1] if lot else None, "also": [b_ for b_, _w in extra],
                   "rock_cells": r1 + r2 + r3, "air_cells": v1 + v2 + v3, "water_cells": w1 + w2 + w3,
                   "wet_columns": wet_n,
                   "commands": len([l for l in lines if not l.startswith("#")])}


def write_function(name, lines):
    cmds = function_limits.ensure_loaded(lines)
    refused = function_limits.check_lines(cmds, name)
    if refused:
        raise SystemExit("%s: %d command(s) the server would refuse: %s" % (name, len(refused), refused[:3]))
    (FUNCS / ("%s.mcfunction" % name)).write_text("\n".join(cmds) + "\n", encoding="utf-8")
    return cmds


def main(argv=None):
    global PACK
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("report", "build"):
        q = sub.add_parser(name)
        q.add_argument("--source-root", default=None)
        if name == "build":
            q.add_argument("--out", default=str(PACK))
    a = p.parse_args(argv)
    if a.cmd == "build" and Path(a.out) != PACK:
        # --out was accepted and ignored: every build wrote build/datapacks/cobblers_gym_demolish, so a test that asked
        # for a scratch pack replaced the real one and read it back (found 2026-10-09 by tests/test_gym_arenas_audit.py)
        global FUNCS
        PACK = Path(a.out)
        FUNCS = PACK / "data" / "cobblers" / "function" / "gym_demolish"
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
        print("%s: %d commands, %d cells back to rock, %d to air, %d to water over %d wet column(s) (shell %s, "
              "dig %s, also %s)" % (row["id"], row["commands"], row["rock_cells"], row["air_cells"],
                                    row["water_cells"], row["wet_columns"], row["shell_box"], row["dig"], row["also"]))
    if a.cmd == "build":
        (FUNCS / "index.txt").write_text("\n".join(done) + "\n", encoding="utf-8")
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "demolish.json").write_text(json.dumps({"note": "every gym data/gym_interiors.json marks superseded_by; "
                                                     "gym 2 since 2026-10-09.", "gyms": rows}, indent=1) + "\n",
                                          encoding="utf-8")
    if a.cmd == "build":
        print("wrote", PACK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
