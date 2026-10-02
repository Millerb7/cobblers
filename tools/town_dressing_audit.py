#!/usr/bin/env python
"""The town dressing against the town plans: no written block on a lot, a road or a building, every piece present.

tools/town_dressing.py writes `cobblers:town_dressing/<settlement>` from data/town_dressing.json. This audit reads
those written functions (the output) and checks them against plan data it computes on its own, never against the
generator's mask or report:

  lots       every house lot and anchor lot (the Centre, the Mart, the gym, an open square) in the town plan
             (derived/towns/<settlement>_plan.json, tools/town_plan.py from data/placements.json)
  roads      the plan's paved street cells and plaza, and, independently, every street polyline in
             data/placements.json rasterised at its own width (a square brush, wider than the paving): both
  buildings  every placement's footprint from its position, its template's size (the kit file or the pack's own
             copy, tools/town_character.py Templates) and its rotation, turned here by the StructureTemplate
             transform, not by tools/place_town.py
  sites      every route event site's recorded area (data/scenes.json `area`, tools/route_events.py), which R12
             builds after the dressing
  ground     each piece's lowest block stands on the heightmap's ground (tools/ground.py, rounded): no piece floats
             more than a block over the highest ground under it, and none is buried
  pieces     every piece data/town_dressing.json lists is written, and every dressed town writes something (an
             empty function passes nothing)
  spawns     no block data/spawn_blocks.json lists as a spawn condition

Every write counts, the clearing fills (air) as well as the blocks: a clear on a lot would take a house's garden.

  python tools/town_dressing_audit.py [--pack build/datapacks/cobblers_town_dressing]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)

PACK = ROOT / "build" / "datapacks" / "cobblers_town_dressing"
N = r"(-?\d+)"
SETBLOCK = re.compile(r"^setblock %s %s %s (\S+)" % (N, N, N))
FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+)" % ((N,) * 6))
PIECE = re.compile(r"^# ([a-z0-9_]+): ([a-z_]+) \(")


def writes(lines):
    """[(piece id or None, x, y, z, block)] of every position a function writes, fills expanded."""
    out, piece = [], None
    for raw in lines:
        line = raw.strip()
        m = PIECE.match(line)
        if m:
            piece = m.group(1)
            continue
        m = SETBLOCK.match(line)
        if m:
            out.append((piece, int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)))
            continue
        m = FILL.match(line)
        if m:
            x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        out.append((piece, x, y, z, m.group(7)))
    return out


def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def turned_size(size, rotation):
    """(width along x, depth along z) of a template turned by a StructureTemplate rotation."""
    sx, _sy, sz = size
    return (sz, sx) if rotation in ("clockwise_90", "counterclockwise_90") else (sx, sz)


def footprints(settlement, doc, templates):
    """{placement id: (x0, z0, x1, z1)}: position is the footprint's minimum corner (data/placements.json note)."""
    out, unknown = {}, []
    for q in doc["placements"]:
        if q.get("settlement") != settlement or q.get("kind") == "earthwork" or not q.get("position"):
            continue
        size = q.get("size")
        if not size:
            tdoc, _where = templates.get(q)
            if tdoc is None:
                unknown.append(q["id"])
                continue
            size = [int(v) for v in tdoc["size"]]
        w, d = turned_size(size, q.get("rotation") or "none")
        x0, z0 = q["position"]["x"], q["position"]["z"]
        out[q["id"]] = (x0, z0, x0 + w - 1, z0 + d - 1)
    return out, unknown


def brushed_streets(plan_data):
    """Every street polyline of a settlement's plan in data/placements.json, rasterised with a square brush."""
    cells = set()
    for st in plan_data.get("streets") or []:
        half = int(st.get("width", 1)) // 2
        pts = st.get("polyline") or []
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            n = int(max(abs(bx - ax), abs(bz - az))) + 1
            for i in range(n + 1):
                t = i / max(n, 1)
                cx, cz = round(ax + (bx - ax) * t), round(az + (bz - az) * t)
                for dx in range(-half, half + 1):
                    for dz in range(-half, half + 1):
                        cells.add((cx + dx, cz + dz))
    return cells


def forbidden(plan, plan_data, building_rects, sites=()):
    """{(x, z): why} of the lots, roads, buildings and route event sites, from plan data."""
    why = {}

    def rect(r, label):
        for x in range(r[0], r[2] + 1):
            for z in range(r[1], r[3] + 1):
                why.setdefault((x, z), label)
    for lot in plan.get("lots") or []:
        rect(lot["rect"], "lot %s" % lot["id"])
    for an in plan.get("anchors") or []:
        rect(an["rect"], "anchor lot %s" % an["id"])
    for sid, st in (plan.get("streets") or {}).items():
        for z, _y, x0, x1 in st.get("cells") or []:
            for x in range(x0, x1 + 1):
                why.setdefault((x, z), "street %s" % sid)
    if plan.get("plaza"):
        rect(plan["plaza"]["rect"], "plaza")
    if plan_data.get("plaza") and plan_data["plaza"].get("rect"):
        rect(plan_data["plaza"]["rect"], "plaza")
    for c in brushed_streets(plan_data):
        why.setdefault(c, "street (data polyline)")
    for bid, r in building_rects.items():
        rect(r, "building %s" % bid)
    for sid, r in sites:
        rect(r, "event site %s" % sid)
    return why


def event_sites():
    """[(scene id, (x0, z0, x1, z1))] of every route event site's recorded area (data/scenes.json)."""
    doc = json.loads((ROOT / "data" / "scenes.json").read_text(encoding="utf-8"))
    return [(s["id"], (s["area"]["from"][0], s["area"]["from"][2], s["area"]["to"][0], s["area"]["to"][2]))
            for s in doc["scenes"] if s.get("area")]


def audit_town(settlement, lines, plan, plan_data, building_rects, ground, spawn_blocks, piece_ids, sites=()):
    """Problems (strings) for one town's function; an empty list means clean."""
    problems = []
    w = writes(lines)
    if not w:
        return ["%s: the function writes nothing" % settlement]
    bad = forbidden(plan, plan_data, building_rects, sites)
    hits = {}
    for piece, x, y, z, state in w:
        if (x, z) in bad:
            hits.setdefault((piece, bad[(x, z)]), []).append((x, y, z))
        if block_name(state) in spawn_blocks:
            problems.append("%s/%s: %s at %d %d %d is a spawn condition (data/spawn_blocks.json)"
                            % (settlement, piece, block_name(state), x, y, z))
    for (piece, why), cells in sorted(hits.items(), key=lambda kv: str(kv[0])):
        problems.append("%s/%s: %d write(s) on %s, first %s" % (settlement, piece, len(cells), why, cells[0]))
    written = {p for p, *_rest in w if p}
    for pid in piece_ids:
        if pid not in written:
            problems.append("%s/%s: listed in data/town_dressing.json, not written" % (settlement, pid))
    # seated on the heightmap: a piece's lowest block is at most one over the highest ground under the piece, and
    # not below the lowest ground under it
    by_piece = {}
    for piece, x, y, z, state in w:
        if piece and block_name(state) not in ("minecraft:air", "minecraft:cave_air"):
            by_piece.setdefault(piece, []).append((x, y, z))
    for piece, cells in sorted(by_piece.items()):
        g = [ground(x, z) for x, _y, z in cells]
        low = min(y for _x, y, _z in cells)
        if low > max(g) + 1:
            problems.append("%s/%s: floats, lowest block y%d over ground y%d-%d" % (settlement, piece, low, min(g), max(g)))
        if low < min(g) - 1:
            problems.append("%s/%s: buried, lowest block y%d under ground y%d-%d" % (settlement, piece, low, min(g), max(g)))
    return problems


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pack", default=str(PACK))
    p.add_argument("--source-root", default=env_source_root())
    a = p.parse_args(argv)
    import ground as G
    import town_character as TC
    data = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    spawn_blocks = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    templates = TC.Templates(TC.default_pack_dir(), TC.default_vanilla_jar())
    g = G.Ground(a.source_root)
    fdir = Path(a.pack) / "data" / "cobblers" / "function" / "town_dressing"
    all_problems, total = [], 0
    if not data.get("towns"):
        raise SystemExit("data/town_dressing.json dresses no town: nothing to audit is not a clean audit")
    for settlement, town in data["towns"].items():
        fn = fdir / ("%s.mcfunction" % settlement)
        if not fn.is_file():
            all_problems.append("%s: no function %s (run tools/town_dressing.py build)" % (settlement, fn))
            continue
        planp = ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)
        if not planp.is_file():
            all_problems.append("%s: no town plan %s (run tools/town_plan.py %s)" % (settlement, planp, settlement))
            continue
        plan = json.loads(planp.read_text(encoding="utf-8"))
        rects, unknown = footprints(settlement, doc, templates)
        all_problems += ["%s: building %s has a template this audit cannot read, so it is not checked" % (settlement, u)
                         for u in unknown]
        ids = ([town["landmark"].get("id", "landmark")] if town.get("landmark") else []) + [q["id"] for q in town.get("pieces") or []]
        lines = fn.read_text(encoding="utf-8").splitlines()
        probs = audit_town(settlement, lines, plan, doc["settlements"][settlement].get("plan") or {}, rects, g,
                           spawn_blocks, ids, event_sites())
        n = len(writes(lines))
        total += n
        print("%-12s %6d writes, %2d pieces, %3d buildings, %d problem(s)" % (settlement, n, len(ids), len(rects), len(probs)))
        all_problems += probs
    for pr in all_problems:
        print("  PROBLEM", pr)
    print("town dressing audit: %s (%d writes checked)" % ("CLEAN" if not all_problems else "%d PROBLEMS" % len(all_problems), total))
    return 1 if all_problems or total == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
