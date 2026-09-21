#!/usr/bin/env python
"""After the re-export builds are re-applied: does the world hold what they were meant to build?

A generated function reports nothing, so each build is checked by its result, the way tools/town_audit.py checks
a town. On 2026-09-21 39 of 72 generated functions were found writing into chunks they never force-loaded; they
had worked only where something else happened to hold the chunks. These checks are what would have noticed.

  cavern      every column of the Displaced City (derived/cavern/plan.npz): grass at the planned floor, open
              above it, the 4-block stone cap over the roof, and rock (not sky) above that
  forest      every trunk in the Route 1 maze: for each `place template` in the tile functions, a log where that
              template puts its trunk
  world_tree  the trunk and crown columns replayed from the tree's own functions and compared block by block,
              and the crown's top block
  islet       Relic Island's dry core: the columns the islet function raises above the sea, replayed from the
              function and compared, and nothing but air above them

  python tools/build_audit.py --world <stopped world copy> [--only cavern forest world_tree islet]

Reads region files of a stopped or saved disposable world; runtime_guard refuses the live save. Never writes.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import nbt  # noqa: E402

BUILD = ROOT / "build"
AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
FLUID = {"minecraft:water", "minecraft:lava"}
NUM = r"(-?\d+)"
FILL = re.compile(r"fill %s %s %s %s %s %s (\S+)(?: (replace|keep|destroy|hollow|outline)(?: (\S+))?)?$" % ((NUM,) * 6))
SETBLOCK = re.compile(r"setblock %s %s %s (\S+)" % ((NUM,) * 3))
PLACE = re.compile(r"place template (\S+) %s %s %s (\S+)" % ((NUM,) * 3))
# the thresholds a build must meet, set before any run, not fitted to one
FLOOR_OK = 0.98        # trees stand on dirt, and a trunk base replaces the grass under it
ROOF_OK = 1.0          # the cap is laid over every column whatever is there
TRUNKS_OK = 0.98       # a trunk can be cut by a later corridor dressing (the report counts them)
COLUMNS_OK = 0.99


def base(name):
    return name.split("[")[0]


class World:
    """Block lookups in a world's region files, one chunk decoded at a time and cached."""

    def __init__(self, world_dir):
        import runtime_guard
        self.dir = Path(runtime_guard.check(world_dir, "read"))
        self.chunks = {}

    def _chunk(self, cx, cz):
        key = (cx, cz)
        if key not in self.chunks:
            from structure_nbt import _section_states
            path = self.dir / "region" / ("r.%d.%d.mca" % (cx >> 5, cz >> 5))
            secs = {}
            if path.is_file():
                for _, _, ch in nbt.region_chunks(path, wanted={(cx & 31, cz & 31)}):
                    for sec in ch.get("sections") or []:
                        pal, idx = _section_states(sec)
                        if pal is not None:
                            secs[int(sec.get("Y", 0))] = ([p.get("Name") for p in pal], idx)
            self.chunks[key] = secs
        return self.chunks[key]

    def block(self, x, y, z):
        secs = self._chunk(x >> 4, z >> 4)
        s = secs.get(y >> 4)
        if s is None:
            return "minecraft:air"
        names, idx = s
        return names[int(idx[y & 15, z & 15, x & 15])]


def replay(lines, columns):
    """{(x, z): {y: block}} for the given columns, from a function's fills and setblocks, last write winning, with
    the replace filter honoured only as 'replace <block>' against what the replay itself has written."""
    out = {c: {} for c in columns}
    for raw in lines:
        l = raw.strip()
        m = FILL.match(l)
        if m:
            x0, y0, z0, x1, y1, z1 = map(int, m.groups()[:6])
            blk, mode, filt = base(m.group(7)), m.group(8), m.group(9)
            for (x, z), col in out.items():
                if min(x0, x1) <= x <= max(x0, x1) and min(z0, z1) <= z <= max(z0, z1):
                    for y in range(min(y0, y1), max(y0, y1) + 1):
                        if mode == "replace" and filt:
                            if filt.startswith("#") or col.get(y) != base(filt):
                                continue
                        if mode == "keep" and y in col:
                            continue
                        col[y] = blk
            continue
        m = SETBLOCK.match(l)
        if m:
            x, y, z = map(int, m.groups()[:3])
            if (x, z) in out:
                out[(x, z)][y] = base(m.group(4))
    return out


def compare_columns(world, expected):
    """(blocks compared, blocks matching, first mismatches)."""
    n = ok = 0
    bad = []
    for (x, z), col in expected.items():
        for y, blk in col.items():
            got = base(world.block(x, y, z))
            n += 1
            if got == blk or (blk in AIR and got in AIR):
                ok += 1
            elif len(bad) < 5:
                bad.append("(%d, %d, %d) holds %s, the function wrote %s" % (x, y, z, got, blk))
    return n, ok, bad


# ------------------------------------------------------------------ the four builds

def built_over(settlement, margin=2):
    """Columns a town later rebuilds on top of an earlier build: its streets, square, lots and anchors from its
    derived plan, every building's footprint with the margin tools/place_town.py clears round it, and every column
    its earthworks write. The cavern's floor and the islet's core are built first and then built on, so the Displaced
    City's streets and Relic Island's seam are not a floor or a core gone wrong; the staging run of 2026-09-21
    reported the cavern floor at 81% and the islet at 97% for that reason alone."""
    out = set()
    plan_path = ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)
    if plan_path.is_file():
        pl = json.loads(plan_path.read_text(encoding="utf-8"))
        for st in (pl.get("streets") or {}).values():
            for z, _, xa, xb in st.get("cells") or []:
                out |= {(x, z) for x in range(xa - 1, xb + 2)}
        rects = [a["rect"] for a in pl.get("anchors") or []] + [l["rect"] for l in pl.get("lots") or []]
        if pl.get("plaza"):
            rects.append(pl["plaza"]["rect"])
        for x0, z0, x1, z1 in rects:
            out |= {(x, z) for x in range(x0 - 1, x1 + 2) for z in range(z0 - 1, z1 + 2)}
    rep_path = ROOT / "derived" / "towns" / ("%s_placement.json" % settlement)
    if rep_path.is_file():
        for b in json.loads(rep_path.read_text(encoding="utf-8")).get("buildings") or []:
            x0, z0, x1, z1 = b["footprint"]
            out |= {(x, z) for x in range(x0 - margin, x1 + margin + 1) for z in range(z0 - margin, z1 + margin + 1)}
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    import town_audit
    for q in doc["placements"]:
        if q.get("settlement") == settlement and q.get("kind") == "earthwork":
            out |= set(town_audit._command_columns(q.get("commands") or []))
    return out


def cavern(world):
    plan = json.loads((ROOT / "derived" / "cavern" / "plan.json").read_text(encoding="utf-8"))
    town = built_over("displaced_city")
    arr = np.load(ROOT / "derived" / "cavern" / "plan.npz")
    floor, ceiling = arr["floor"], arr["ceiling"]
    x0, z0 = plan["cavern"][0], plan["cavern"][1]
    n = floor.size
    floor_ok = open_ok = roof_ok = 0
    n_ground = 0                                         # columns whose floor and interior the town has not rebuilt
    bad = Counter()
    for j in range(floor.shape[0]):
        for i in range(floor.shape[1]):
            x, z, f, c = x0 + i, z0 + j, int(floor[j, i]), int(ceiling[j, i])
            cap = [base(world.block(x, y, z)) for y in range(c, c + 4)]
            if all(b not in AIR and b not in FLUID for b in cap):
                roof_ok += 1
            else:
                bad["roof cap open (" + ",".join(b.split(":")[-1] for b in cap) + ")"] += 1
            if (x, z) in town:
                continue
            n_ground += 1
            surf = base(world.block(x, f, z))
            if surf in ("minecraft:grass_block", "minecraft:dirt", "minecraft:podzol", "minecraft:moss_block"):
                floor_ok += 1
            else:
                bad["floor holds " + surf] += 1
            mid = base(world.block(x, (f + c) // 2, z))
            if mid in AIR or not mid.endswith(("stone", "deepslate", "dirt", "gravel", "andesite", "diorite", "granite", "tuff")):
                open_ok += 1
            else:
                bad["filled at mid-height with " + mid] += 1
    # the shell (cavern_plan 02): no void within 24 blocks of the chamber, over the roof or round the walls, except
    # where the tunnel is dug through it and the town builds (its gate)
    shell_voids, shell_cols = Counter(), 0
    problems = []
    # fail closed: the plan's own box is the expected set; a floor grid of another size, no column left for the floor
    # check, or no shell data at all is a failure, not a pass (Codex review, 2026-09-21)
    cx0, cz0, cx1, cz1 = plan["cavern"]
    expected = (cx1 - cx0 + 1) * (cz1 - cz0 + 1)
    if expected <= 0 or n != expected:
        problems.append("cavern: the plan's box holds %d columns, its floor grid %d" % (expected, n))
    if n_ground == 0:
        problems.append("cavern: no column left to check the floor on (the town rebuilds all %d)" % n)
    if "shell_hi" not in arr.files:
        problems.append("cavern: no shell in the plan (derived/cavern/plan.npz): re-run tools/cavern_plan.py")
    else:
        import town_audit
        dug = set(town_audit._command_columns(
            (BUILD / "datapacks" / "cobblers_cavern" / "data" / "cobblers" / "function" / "cavern" / "50_tunnel.mcfunction")
            .read_text(encoding="utf-8").splitlines()))
        dug = {(x + dx, z + dz) for x, z in dug for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
        lo_a, hi_a = arr["shell_lo"], arr["shell_hi"]
        m = (lo_a.shape[0] - floor.shape[0]) // 2
        for j in range(lo_a.shape[0]):
            for i in range(lo_a.shape[1]):
                x, z = x0 - m + i, z0 - m + j
                inside = 0 <= i - m < floor.shape[1] and 0 <= j - m < floor.shape[0]
                if (x, z) in dug or (not inside and (x, z) in town):      # the town builds under the roof, not in it
                    continue
                shell_cols += 1
                for y in range(int(lo_a[j, i]), int(hi_a[j, i]) + 1):
                    b = base(world.block(x, y, z))
                    if b in AIR or b in FLUID:
                        shell_voids["%s %s" % ("over the roof," if inside else "in the walls,", b.split(":")[-1])] += 1
                        break
        if shell_cols == 0:
            problems.append("cavern: no shell column left to check")
    if sum(shell_voids.values()):
        problems.append("cavern shell: %d columns with a void within 24 blocks of the chamber (%s)"
                        % (sum(shell_voids.values()), dict(shell_voids)))
    for what, got, total, need in (("floor", floor_ok, n_ground, FLOOR_OK), ("roof cap", roof_ok, n, ROOF_OK),
                                   ("open interior", open_ok, n_ground, COLUMNS_OK)):
        if got < need * total:
            problems.append("cavern %s: %d of %d columns (%.2f%%), needs %.0f%%" % (what, got, total, 100 * got / max(total, 1), 100 * need))
    return {"columns": n, "rebuilt_by_the_town": n - n_ground, "floor_ok": floor_ok, "roof_ok": roof_ok, "open_ok": open_ok,
            "shell_columns": shell_cols, "shell_voids": dict(shell_voids),
            "worst": bad.most_common(5), "problems": problems}


def _trunk_offsets():
    """{template id: (dx, dy, dz) of its lowest log, or None} from the forest pack's own foliage templates."""
    out = {}
    root = BUILD / "datapacks" / "cobblers_route1" / "data" / "cobblers" / "structure" / "route1" / "foliage"
    for f in root.glob("*.nbt"):
        _, doc = nbt.load(f)
        pal = doc["palette"]
        logs = [b["pos"] for b in doc["blocks"] if pal[b["state"]]["Name"].endswith(("_log", "_wood", "_stem"))]
        out["cobblers:route1/foliage/" + f.stem] = min(logs, key=lambda p: (p[1], p[0], p[2])) if logs else None
    return out


def forest(world):
    import place_town
    offs = _trunk_offsets()
    fdir = BUILD / "datapacks" / "cobblers_route1" / "data" / "cobblers" / "function" / "route1"
    placed = present = no_trunk = 0
    missing = []
    for f in sorted(fdir.glob("tile_*.mcfunction")):
        for l in f.read_text(encoding="utf-8").splitlines():
            m = PLACE.match(l.strip())
            if not m:
                continue
            tid, rot = m.group(1), m.group(5)
            x, y, z = int(m.group(2)), int(m.group(3)), int(m.group(4))
            off = offs.get(tid)
            if off is None:
                no_trunk += 1
                continue
            placed += 1
            rx, rz = place_town.rotate(off[0], off[2], rot)
            got = base(world.block(x + rx, y + off[1], z + rz))
            if got.endswith(("_log", "_wood", "_stem")):
                present += 1
            elif len(missing) < 5:
                missing.append("%s at (%d, %d, %d): %s" % (tid.rsplit("/", 1)[-1], x + rx, y + off[1], z + rz, got))
    # Fail closed: the expected count is the plan's (derived/sites/route1_forest.json, written by tools/maze_forest.py
    # from data), never what the functions happen to contain. An empty or missing function set, or objects whose
    # template has no trunk to look for, used to pass with nothing checked (Codex review, 2026-09-21).
    plan = ROOT / "derived" / "sites" / "route1_forest.json"
    rep = json.loads(plan.read_text(encoding="utf-8")) if plan.is_file() else {}
    expected = int(rep.get("objects_placed") or 0)
    # the world-tree sapling is one more object, from the kits pack, whose template the forest pack does not carry
    sapling = 1 if rep.get("sapling_placed") else 0
    problems = []
    if expected <= 0:
        problems.append("forest: the plan (%s) expects no trees: nothing to check is a failure" % plan.name)
    if placed + no_trunk != expected + sapling:
        problems.append("forest: the functions place %d objects, the plan %d and %d sapling"
                        % (placed + no_trunk, expected, sapling))
    if no_trunk != sapling:
        problems.append("forest: %d placed objects have no trunk the audit can find (the plan allows %d, the sapling)"
                        % (no_trunk, sapling))
    if present < TRUNKS_OK * max(expected, 1):
        problems.append("forest: %d of %d planned trunks stand (%.2f%%), needs %.0f%%"
                        % (present, expected, 100 * present / max(expected, 1), 100 * TRUNKS_OK))
    return {"planned": expected, "objects_with_trunks": placed, "trunks_present": present, "objects_without_trunks": no_trunk,
            "first_missing": missing, "problems": problems}


def world_tree(world):
    rep = json.loads((ROOT / "derived" / "sites" / "world_tree_foothill_woods.json").read_text(encoding="utf-8"))
    cx, cz = rep["centre"]
    half = rep["trunk"][0] // 2 - 1                  # the trunk's width, so its wall is about this far out
    # the centre column, four columns just inside the trunk's wall, and a ring of crown columns
    cols = [(cx, cz), (cx - half, cz), (cx + half, cz), (cx, cz - half), (cx, cz + half)]
    r = rep["crown_radius"] // 2
    cols += [(cx + int(r * math.cos(a)), cz + int(r * math.sin(a))) for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
    lines = []
    for f in sorted((BUILD / "datapacks" / "cobblers_worldtree" / "data" / "cobblers" / "function" / "worldtree").glob("*.mcfunction")):
        lines += f.read_text(encoding="utf-8").splitlines()
    exp = replay(lines, cols)
    n, ok, bad = compare_columns(world, exp)
    # the crown's highest block, wherever the functions put it: it is not over the trunk. REEXPORT.md checked
    # (2016, 535, 2280), which the tree never reaches; its top is 28 blocks east of the trunk
    top_at, top_blk = None, None
    for l in lines:
        m = FILL.match(l.strip())
        if m and base(m.group(7)) not in AIR:
            x0, y0, z0, x1, y1, z1 = map(int, m.groups()[:6])
            if top_at is None or max(y0, y1) > top_at[1]:
                top_at, top_blk = (x0, max(y0, y1), z0), base(m.group(7))
    got = base(world.block(*top_at)) if top_at else None
    problems = []
    # fail closed: nothing replayed, or no crown found in the functions, is a failure, and the crown must be where
    # the plan (derived/sites/world_tree_foothill_woods.json top_y) says
    if n == 0:
        problems.append("world tree: the functions write nothing in the %d checked columns" % len(cols))
    elif ok < COLUMNS_OK * n:
        problems.append("world tree: %d of %d replayed blocks match (%.2f%%)" % (ok, n, 100 * ok / n))
    if top_at is None:
        problems.append("world tree: no crown block in the functions")
    else:
        if top_at[1] != rep["top_y"]:
            problems.append("world tree: the functions' crown top is y%d, the plan's y%d" % (top_at[1], rep["top_y"]))
        if got != top_blk:
            problems.append("world tree: crown top %s holds %s, the function wrote %s" % (top_at, got, top_blk))
    return {"columns": len(cols), "blocks_compared": n, "blocks_match": ok, "crown_top": [top_at, got],
            "first_mismatches": bad, "problems": problems}


def islet(world):
    rep = json.loads((ROOT / "derived" / "sites" / "relic_island.json").read_text(encoding="utf-8"))
    cx, cz = rep["centre"]
    sea = rep["sea_level"]
    lines = (BUILD / "islet" / "relic_island.mcfunction").read_text(encoding="utf-8").splitlines()
    r = rep["radius"]
    cols = [(x, z) for x in range(cx - r, cx + r + 1) for z in range(cz - r, cz + r + 1)
            if (x - cx) ** 2 + (z - cz) ** 2 <= (r // 2) ** 2]
    exp = replay(lines, cols)
    dry = {c: col for c, col in exp.items() if col and max(y for y, b in col.items() if b not in AIR) > sea}
    rebuilt = built_over("relic_island")
    dry = {c: col for c, col in dry.items() if c not in rebuilt}           # the house, its walk and its seam stand here
    n, ok, bad = compare_columns(world, dry)
    wet_top = [c for c, col in dry.items()
               if base(world.block(c[0], max(y for y, b in col.items() if b not in AIR) + 1, c[1])) in FLUID]
    problems = []
    if not dry or n == 0:
        problems.append("islet: the function raises no column of the core above the sea: nothing to check")
    elif ok < COLUMNS_OK * n:
        problems.append("islet: %d of %d replayed blocks match in the dry core (%.2f%%)" % (ok, n, 100 * ok / n))
    if wet_top:
        problems.append("islet: %d dry-core columns have water standing on them" % len(wet_top))
    return {"core_columns": len(dry), "blocks_compared": n, "blocks_match": ok, "first_mismatches": bad,
            "problems": problems}


CHECKS = {"cavern": cavern, "forest": forest, "world_tree": world_tree, "islet": islet}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--world", required=True, help="a stopped or saved DISPOSABLE world; the live save is refused")
    p.add_argument("--only", nargs="*", choices=sorted(CHECKS))
    p.add_argument("--json", action="store_true", dest="as_json")
    a = p.parse_args(argv)
    w = World(a.world)
    res, bad = {}, 0
    for name in a.only or list(CHECKS):
        res[name] = CHECKS[name](w)
        bad += len(res[name]["problems"])
        if not a.as_json:
            print("%-10s %s" % (name, json.dumps({k: v for k, v in res[name].items() if k != "problems"})))
            for msg in res[name]["problems"]:
                print("   BUILD MISMATCH  %s" % msg)
    if a.as_json:
        print(json.dumps(res, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
