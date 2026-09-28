#!/usr/bin/env python
"""The wayside shrines against the plans, the roads, the water and the other builds: offline, fail-closed.

tools/shrines.py writes `cobblers:shrines/<id>` from data/shrines.json. This audit reads those written functions (the
output) and checks every write against data it reads and computes on its own, never against the generator's clearance
or its report:

  present    every shrine data/shrines.json lists has a function, the pack's index names exactly them, each writes
             between 5 and 60 blocks (a few to a few dozen) and the function's run holds its chunks
             (tools/function_limits.py check_lines). An empty function, an empty list or no pack is a failure
  blocks     every block written is in data/shrines.json `blocks`, exists in the Minecraft 1.21.1 client jar (its
             blockstates), and is no spawn condition in data/spawn_blocks.json
  ground     every written column's lowest block stands exactly one over the heightmap's ground there (tools/ground.py,
             rounded): nothing floats, nothing is buried
  plans      no write on a lot, an anchor, a street (the plan's paved cells and, independently, each data polyline
             brushed at its width), the plaza, a building's footprint (its template's size turned by the
             StructureTemplate transform, tools/town_dressing_audit.py) or a route event site; and none within 2 of
             any placed building of any settlement
  legs       no write within `leg_margin` of a routed leg, measured as the distance to each segment of every
             data/routes.json corridor polyline and derived/routes/critical_legs.json leg
  water      no write on painted water (the sea level and build/paint's lake and river masks, read here), within
             `tree_reach` of a painted tree or object, or within `water_change_margin` (Euclidean) of a column the
             pending water export changes (derived/water_shape/changed.npy; missing is a failure)
  places     no write within `excluded_margin` of an excluded settlement (the sea town, the jungle ruins), and every
             shrine within `max_from_town` of its own settlement's footprint
  builds     no write within 2 of a block any other built pack writes at an absolute position (build/datapacks)

  python tools/shrines_audit.py [--pack build/datapacks/cobblers_shrines]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

PACK = ROOT / "build" / "datapacks" / "cobblers_shrines"
N = r"(-?\d+)"
SETBLOCK = re.compile(r"^setblock %s %s %s (\S+)" % (N, N, N))
FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+)" % ((N,) * 6))
AIR = ("minecraft:air", "minecraft:cave_air")
OTHER = re.compile(r"\b(setblock|fill|summon \S+|place template \S+)\s+(-?\d+(?:\.\d+)?)\s+-?\d+(?:\.\d+)?\s+"
                   r"(-?\d+(?:\.\d+)?)(?:\s+(-?\d+)\s+-?\d+\s+(-?\d+))?")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def writes(lines):
    """[(x, y, z, block)] of every position the function writes, fills expanded."""
    out = []
    for raw in lines:
        line = raw.strip()
        m = SETBLOCK.match(line)
        if m:
            out.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)))
            continue
        m = FILL.match(line)
        if m:
            x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        out.append((x, y, z, m.group(7)))
    return out


def seg_distance(px, pz, ax, az, bx, bz):
    vx, vz = bx - ax, bz - az
    L = vx * vx + vz * vz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * vx + (pz - az) * vz) / L))
    return math.hypot(px - (ax + t * vx), pz - (az + t * vz))


def all_legs():
    out = []
    p = ROOT / "derived" / "routes" / "critical_legs.json"
    if p.is_file():
        out += [[tuple(q) for q in leg.get("polyline") or []] for leg in load(p)["legs"]]
    for r in load(ROOT / "data" / "routes.json")["routes"]:
        out.append([(q["x"], q["z"]) for q in (r.get("corridor") or {}).get("polyline") or []])
    return [l for l in out if len(l) > 1], p.is_file()


def vanilla_blocks():
    import town_character as TC
    jar = TC.default_vanilla_jar()
    if jar is None or not Path(jar).is_file():
        return None
    with zipfile.ZipFile(jar) as z:
        return {"minecraft:" + n.rsplit("/", 1)[1][:-5] for n in z.namelist()
                if n.startswith("assets/minecraft/blockstates/") and n.endswith(".json")}


def other_builds(pack_name):
    """[(x0, z0, x1, z1)] every other built pack writes at an absolute position."""
    base = ROOT / "build" / "datapacks"
    out = []
    for pack in sorted(p for p in base.iterdir() if p.is_dir() and p.name != pack_name):
        for f in pack.rglob("*.mcfunction"):
            for m in OTHER.finditer(f.read_text(encoding="utf-8", errors="replace")):
                x, z = math.floor(float(m.group(2))), math.floor(float(m.group(3)))
                if m.group(1) == "fill" and m.group(4) is not None:
                    xb, zb = int(m.group(4)), int(m.group(5))
                    out.append((min(x, xb), min(z, zb), max(x, xb), max(z, zb)))
                else:
                    out.append((x, z, x, z))
    return out


def audit(pack=PACK, source_root=None):
    """(problems, number of writes checked)."""
    import numpy as np
    from PIL import Image
    import ground as G
    import terrain as T
    import town_character as TC
    import town_dressing_audit as TA

    problems = []
    data = load(ROOT / "data" / "shrines.json")
    shrines = data.get("shrines") or []
    rules = data.get("rules") or {}
    if not shrines:
        return ["data/shrines.json lists no shrine: nothing to audit is not a clean audit"], 0
    fdir = Path(pack) / "data" / "cobblers" / "function" / "shrines"
    if not fdir.is_dir():
        return ["no %s (run python tools/shrines.py build)" % fdir], 0
    idx = fdir / "index.txt"
    listed = [s["id"] for s in shrines]
    if not idx.is_file() or [x for x in idx.read_text(encoding="utf-8").split("\n") if x.strip()] != listed:
        problems.append("%s does not list exactly the shrines of data/shrines.json, in order" % idx)
    allowed = set(data["blocks"]["ids"])
    spawn = set(load(ROOT / "data" / "spawn_blocks.json")["blocks"])
    vanilla = vanilla_blocks()
    if vanilla is None:
        problems.append("no Minecraft 1.21.1 client jar found: the block ids cannot be checked (fail closed)")
    import function_limits
    by_shrine = {}
    for s in shrines:
        fn = fdir / ("%s.mcfunction" % s["id"])
        if not fn.is_file():
            problems.append("%s: no function %s" % (s["id"], fn))
            continue
        lines = fn.read_text(encoding="utf-8").splitlines()
        w = writes(lines)
        solid = [t for t in w if block_name(t[3]) not in AIR and not t[3].startswith("#")]
        if not 5 <= len(solid) <= 60:
            problems.append("%s: writes %d blocks, not a few to a few dozen (5-60)" % (s["id"], len(solid)))
        refused = function_limits.check_lines(lines, s["id"])
        if refused:
            problems.append("%s: %d command(s) the server would refuse, first %s" % (s["id"], len(refused), refused[0]))
        for x, y, z, st in solid:
            b = block_name(st)
            if b not in allowed:
                problems.append("%s: %s at %d %d %d is not in data/shrines.json blocks" % (s["id"], b, x, y, z))
            if b in spawn:
                problems.append("%s: %s at %d %d %d is a spawn condition (data/spawn_blocks.json)" % (s["id"], b, x, y, z))
            if vanilla is not None and b not in vanilla:
                problems.append("%s: %s is not a Minecraft 1.21.1 block" % (s["id"], b))
        by_shrine[s["id"]] = (s, w, solid)
    total = sum(len(v[1]) for v in by_shrine.values())
    if not total:
        return problems + ["the shrines write nothing"], 0

    g = G.Ground(source_root)
    ox, oz = g.ox, g.oz
    # ground: each written column's lowest block exactly one over the heightmap
    for sid, (s, _w, solid) in by_shrine.items():
        low = {}
        for x, y, z, _st in solid:
            low[(x, z)] = min(low.get((x, z), y), y)
        for (x, z), y in sorted(low.items()):
            if y != g(x, z) + 1:
                problems.append("%s: column %d,%d starts at y%d over ground y%d (%s)"
                                % (sid, x, z, y, g(x, z), "floats" if y > g(x, z) + 1 else "buried"))

    towns = {t["id"]: t["footprint"] for t in load(ROOT / "data" / "towns.json")["towns"]}
    doc = load(ROOT / "data" / "placements.json")
    templates = TC.Templates(TC.default_pack_dir(), TC.default_vanilla_jar())
    sites = TA.event_sites()
    # a shrine that writes nothing is already a problem (above); the checks below are over the ones that write
    cols = {sid: sorted({(x, z) for x, _y, z, _st in w}) for sid, (_s, w, _solid) in by_shrine.items() if w}

    def box_distance(fp, x, z):
        dx = max(fp["min_x"] - x, 0, x - fp["max_x"])
        dz = max(fp["min_z"] - z, 0, z - fp["max_z"])
        return math.hypot(dx, dz)

    # places
    for sid, cs in cols.items():
        s = by_shrine[sid][0]
        for ex in rules.get("excluded_settlements") or []:
            if any(box_distance(towns[ex], x, z) <= rules["excluded_margin"] for x, z in cs):
                problems.append("%s: writes within %d of %s" % (sid, rules["excluded_margin"], ex))
        d = min(box_distance(towns[s["settlement"]], x, z) for x, z in cs)
        if d > rules["max_from_town"]:
            problems.append("%s: %.0f from %s's footprint, over %d" % (sid, d, s["settlement"], rules["max_from_town"]))
    # plans, and every building of every settlement
    rects = []
    for st in sorted({q.get("settlement") for q in doc["placements"] if q.get("settlement")}):
        r, unknown = TA.footprints(st, doc, templates)
        rects += [(bid, v) for bid, v in r.items()]
        problems += ["%s: building %s has a template this audit cannot read" % (st, u) for u in unknown
                     if any(box_distance(towns.get(st, {"min_x": 0, "min_z": 0, "max_x": 8191, "max_z": 8191}), x, z) < 300
                            for c in cols.values() for x, z in c)]
    for sid, cs in cols.items():
        for bid, (x0, z0, x1, z1) in rects:
            if any(x0 - 2 <= x <= x1 + 2 and z0 - 2 <= z <= z1 + 2 for x, z in cs):
                problems.append("%s: writes within 2 of building %s" % (sid, bid))
        for st, rec in doc["settlements"].items():
            planp = ROOT / "derived" / "towns" / ("%s_plan.json" % st)
            fp = towns.get(st)
            if fp is None or not planp.is_file() or min(box_distance(fp, x, z) for x, z in cs) > 96:
                continue
            bad = TA.forbidden(load(planp), rec.get("plan") or {}, {}, sites)
            hit = [c for c in cs if c in bad]
            if hit:
                problems.append("%s: writes on %s at %s" % (sid, bad[hit[0]], hit[0]))
        for eid, (x0, z0, x1, z1) in sites:
            if any(min(x0, x1) <= x <= max(x0, x1) and min(z0, z1) <= z <= max(z0, z1) for x, z in cs):
                problems.append("%s: writes on event site %s" % (sid, eid))
    # legs
    legs, have_critical = all_legs()
    if not have_critical:
        problems.append("no derived/routes/critical_legs.json: the critical legs cannot be checked (fail closed)")
    for sid, cs in cols.items():
        near = min((seg_distance(x, z, *a, *b), (x, z)) for x, z in cs for leg in legs for a, b in zip(leg, leg[1:])
                   if abs(a[0] - x) < 600 and abs(a[1] - z) < 600)
        if near[0] < rules["leg_margin"]:
            problems.append("%s: column %s is %.1f from a routed leg (under %d)" % (sid, near[1], near[0], rules["leg_margin"]))
    # water, trees, the pending export
    world = g.world
    man = load(ROOT / "build" / "paint" / "manifest.json")
    chg_path = ROOT / "derived" / "water_shape" / "changed.npy"
    changed = np.load(chg_path, mmap_mode="r") if chg_path.is_file() else None
    if changed is None:
        problems.append("no %s: the pending water export cannot be checked (fail closed)" % chg_path)
    masks = []
    for wl in man["water"]:
        f = ROOT / "build" / "paint" / (wl.get("levels") or wl["mask"])
        if not f.is_file():
            problems.append("no painted water mask %s" % f)
            continue
        masks.append((wl["x"], wl["z"], np.asarray(Image.open(f)) > 0))
    objects = []
    for layer in man.get("objects") or []:
        f = ROOT / "build" / "paint" / layer["map"]
        if not f.is_file():
            problems.append("no painted object map %s" % f)
            continue
        objects.append(np.asarray(Image.open(f)) > 0)
    sea = T.sea_level(world)
    tr, wm = rules["tree_reach"], rules["water_change_margin"]
    for sid, cs in cols.items():
        for x, z in cs:
            ix, iz = x - ox, z - oz
            if g.heights[iz, ix] <= sea:
                problems.append("%s: column %d,%d is under the sea level" % (sid, x, z))
            for mx, mz, m in masks:
                if 0 <= iz - mz < m.shape[0] and 0 <= ix - mx < m.shape[1] and m[iz - mz, ix - mx]:
                    problems.append("%s: column %d,%d is painted water" % (sid, x, z))
            for m in objects:
                if m[max(0, iz - tr):iz + tr + 1, max(0, ix - tr):ix + tr + 1].any():
                    problems.append("%s: column %d,%d is within %d of a painted tree or object" % (sid, x, z, tr))
                    break
            if changed is not None:
                win = np.asarray(changed[iz - wm:iz + wm + 1, ix - wm:ix + wm + 1])
                zz, xx = np.nonzero(win)
                if len(zz) and (np.hypot(zz - wm, xx - wm) <= wm).any():
                    problems.append("%s: column %d,%d is within %d of a column the water export changes" % (sid, x, z, wm))
    # other builds
    others = other_builds(Path(pack).name)
    for sid, cs in cols.items():
        xs, zs = [c[0] for c in cs], [c[1] for c in cs]
        bx0, bz0, bx1, bz1 = min(xs) - 2, min(zs) - 2, max(xs) + 2, max(zs) + 2
        for r in others:
            if r[2] < bx0 or r[0] > bx1 or r[3] < bz0 or r[1] > bz1:
                continue
            if any(r[0] - 2 <= x <= r[2] + 2 and r[1] - 2 <= z <= r[3] + 2 for x, z in cs):
                problems.append("%s: writes within 2 of another pack's build at %s" % (sid, r))
                break
    return problems, total


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pack", default=str(PACK))
    p.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    a = p.parse_args(argv)
    problems, total = audit(Path(a.pack), a.source_root)
    for pr in problems:
        print("  PROBLEM", pr)
    print("shrines audit: %s (%d writes checked)" % ("CLEAN" if not problems and total else "%d PROBLEMS" % len(problems), total))
    return 1 if problems or total == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
