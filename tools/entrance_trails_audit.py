#!/usr/bin/env python
"""Offline audit of the pack tools/entrance_trails.py wrote (build/datapacks/cobblers_entrance_trails).

It reads the GENERATED FUNCTIONS (the commands the game would run) and data/entrance_trails.json, and recomputes every
property from the heightmap (tools/ground.py) and from data/*.json by its own code. It imports nothing from
tools/entrance_trails.py, so a change to the planner's rules (its water margin, its open-cell test, its step limit)
cannot move the audit with it: the audit's limits are its own and are looser than the planner's margins, so a pass
means the output satisfies the properties, not that the planner agrees with itself.

What it checks, per trail:
  walk       the centre line (every dirt_path block) is ONE chain: from the cell at the trail's start to a cell within
             stop_short + 3 of its entrance, over 8-connected centre cells, no step more than 1 block of rounded ground and
             no edge steeper than 40 degrees on the raw heightmap; no centre cell is off that chain
  ground     every block it sets stands at the heightmap's rounded ground (the ribbon on it, a post and a sign on
             ground + 1), and nothing sets a block below the surface
  water      no ribbon, post or sign cell at sea level (ground <= the world's sea level), inside a lake basin polygon
             (data/landmarks.json), within a river's half width + 2 of its graded centre line (data/rivers.json), or within
             a waterway's half width + 2 (data/waterways.json)
  buildings  no ribbon cell inside another town's footprint, inside a placement's box (data/placements.json: its
             recorded size where it has one, else a generous 24 x 24 from its corner), or inside a box any other
             built pack writes (non-air setblock and fill) -- the start's first `start_open` blocks aside, where the
             trail joins the town's own street
  start      the start cell is on the named town's street (data/placements.json plan streets or roads) or the named
             route's walked line (data/route_paths.json), or within 3 of the town's footprint edge
  ends       the last centre cell is within stop_short + 3 of the entrance's x, z (data/cave_systems.json,
             data/mine_networks.json)
  length     the shortest walk along the chain is no more than max_length_blocks
  lanterns   each is a fence, a fence and a lantern stacked, 2 to 3 blocks from the centre line, and the count and
             spacing follow lantern_every along the walk
  sign       one post: a fence under a standing sign, within 14 blocks of the start, every line at most 15 characters,
             the front naming the entrance and the walk's length to within 10 percent, the back naming where the trail
             starts, the front facing the traveller coming from the start, clear of every seat in data/npc_seats.json
  blocks     only the blocks data/entrance_trails.json rules name (and air), none a spawn condition (data/spawn_blocks.json)
  limits     tools/function_limits.py finds nothing the server would refuse

NOT COVERED (CLAUDE.md "Our list is not the world"): trees, ponds and rock the world holds and no file carries (the
ribbon clears vegetation and nothing else); structures a mod or the world generator placed; packs not built here (the
building check against other packs reports how many it saw, and says so when there are none); the lanterns' light or
the ribbon's look in a running game.

  python tools/entrance_trails_audit.py [--pack <dir>]       exit 1 on any problem
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
PACK = ROOT / "build" / "datapacks" / "cobblers_entrance_trails"
GUIDE_PACK = ROOT / "build" / "datapacks" / "cobblers_entrance_guides"
DATA = ROOT / "data" / "entrance_trails.json"
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (.+)$")
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
TEXT = re.compile(r"'(\"(?:[^\"\\]|\\.)*\")'")
NEIGH8 = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
# the 1.21.1 standing-sign rotation: 0 faces south (+z), 4 west, 8 north, 12 east
EXTRA_BOX = 24


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def base(block):
    return block.split("[")[0].split("{")[0]


def parse_function(path):
    """{centre: {(x, z): y}, flank: {...}, posts: {(x, z): {y: block}}, signs: [(x, y, z, rotation, front, back)], blocks, lines}"""
    out = {"centre": {}, "flank": {}, "stacks": {}, "signs": [], "blocks": set(), "fills": [], "lines": []}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("forceload"):
            continue
        out["lines"].append(line)
        m = SETBLOCK.match(line)
        if m:
            x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
            blk = m.group(4)
            out["blocks"].add(base(blk))
            if "_sign[" in blk:
                rot = int(re.search(r"rotation=(\d+)", blk).group(1))
                texts = [json.loads(t) for t in TEXT.findall(blk)]
                out["signs"].append((x, y, z, rot, texts[:4], texts[4:8]))
            elif base(blk) == "minecraft:dirt_path":
                out["centre"][(x, z)] = y
            elif base(blk) in ("minecraft:gravel", "minecraft:coarse_dirt"):
                out["flank"][(x, z)] = y
            else:
                out["stacks"].setdefault((x, z), {})[y] = base(blk)
            continue
        m = FILL.match(line)
        if m:
            out["blocks"].add(base(m.group(7)))
            out["fills"].append(tuple(int(m.group(i)) for i in range(1, 7)) + (base(m.group(7)),))
            continue
        out["blocks"].add("<unparsed: %s>" % line[:40])
    return out


def point_in_ring(x, z, ring):
    inside = False
    j = len(ring) - 1
    for i, (xi, zi) in enumerate(ring):
        xj, zj = ring[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi:
            inside = not inside
        j = i
    return inside


def seg_distance(px, pz, pts):
    """Least distance from each (px[i], pz[i]) to the polyline pts (n, 2)."""
    best = np.full(px.shape, 1e18)
    for (ax, az), (bx, bz) in zip(pts[:-1], pts[1:]):
        dx, dz = bx - ax, bz - az
        L2 = dx * dx + dz * dz
        t = np.zeros(px.shape) if L2 == 0 else np.clip(((px - ax) * dx + (pz - az) * dz) / L2, 0, 1)
        best = np.minimum(best, np.hypot(px - (ax + t * dx), pz - (az + t * dz)))
    return best


class Water:
    """Where water is, by the audit's own reading of the data files (never from a world)."""

    def __init__(self, sea_level):
        self.sea = sea_level
        self.rings = []
        for lm in load_json(ROOT / "data" / "landmarks.json")["landmarks"]:
            for ring in (lm.get("water_body") or {}).get("basin_polygons") or []:
                self.rings.append([(q[0], q[1]) for q in ring])
        self.rivers = []
        for c in load_json(ROOT / "data" / "rivers.json")["courses"]:
            half = max([r.get("width", 0) for r in c.get("reaches") or []] + [0]) / 2.0
            self.rivers.append((np.array(c["graded_polyline"], dtype=float)[:, :2], half))
        self.ways = [(np.array(w["polyline"], dtype=float)[:, :2], w.get("half_width", 8)) for w in load_json(ROOT / "data" / "waterways.json")["waterways"]]

    def wet(self, cells, ground):
        """[(x, z, why)] for every cell that is water by this reading."""
        out = []
        cells = list(cells)
        xs = np.array([c[0] for c in cells], dtype=float)
        zs = np.array([c[1] for c in cells], dtype=float)
        for (x, z) in cells:
            if ground(x, z) <= self.sea:
                out.append((x, z, "ground y%d at or under sea level y%d" % (ground(x, z), self.sea)))
        for ring in self.rings:
            lx, hx = min(p[0] for p in ring), max(p[0] for p in ring)
            lz, hz = min(p[1] for p in ring), max(p[1] for p in ring)
            for (x, z) in cells:
                if lx <= x <= hx and lz <= z <= hz and point_in_ring(x, z, ring):
                    out.append((x, z, "inside a lake basin"))
        for pts, half in self.rivers + self.ways:
            if xs.min() - 400 > pts[:, 0].max() or xs.max() + 400 < pts[:, 0].min() or zs.min() - 400 > pts[:, 1].max() or zs.max() + 400 < pts[:, 1].min():
                continue
            d = seg_distance(xs, zs, pts)
            for i in np.nonzero(d < half + 2)[0]:
                out.append((cells[i][0], cells[i][1], "%.1f blocks from a river or waterway centre line (half width %.1f)" % (d[i], half)))
        return out


def entrances():
    out = {}
    for s in load_json(ROOT / "data" / "cave_systems.json")["systems"]:
        for m in s["mouths"]:
            out[m["id"]] = (m["x"], m["z"])
    for n in load_json(ROOT / "data" / "mine_networks.json")["networks"]:
        for a in n["adits"]:
            out[a["id"]] = tuple(a["portal"])
    return out


def building_boxes(skip_town):
    """[(x0, z0, x1, z1, why)] the audit will not let a ribbon cell enter."""
    boxes = []
    for t in load_json(ROOT / "data" / "towns.json")["towns"]:
        f = t["footprint"]
        if t["id"] != skip_town:
            boxes.append((f["min_x"] - 2, f["min_z"] - 2, f["max_x"] + 2, f["max_z"] + 2, "the footprint of %s" % t["id"]))
    for r in load_json(ROOT / "data" / "placements.json")["placements"]:
        pos = r.get("position")
        if not pos:
            continue
        x, z = pos["x"], pos["z"]
        size = r.get("size")
        if size:
            w, d = size[0], size[2]
            boxes.append((x - w - 1, z - d - 1, x + w + 1, z + d + 1, "placement %s (recorded size)" % r["id"]))
        else:
            boxes.append((x - 1, z - 1, x + EXTRA_BOX, z + EXTRA_BOX, "placement %s (corner + %d)" % (r["id"], EXTRA_BOX)))
    return boxes


def other_pack_boxes(windows, base_dir=None, skip=("cobblers_entrance_trails", "cobblers_entrance_guides")):
    """([(x0, z0, x1, z1, y0, y1, pack)], packs seen): every non-air setblock and fill the other built packs write that
    touches one of `windows` (x0, z0, x1, z1). A fill with a `replace` clause only changes what it replaces and is left
    out: the cave and mine packs' shells (stone for water) and clears (air for vegetation) are not placements."""
    base_dir = Path(base_dir) if base_dir else ROOT / "build" / "datapacks"
    boxes, packs = [], 0
    if not base_dir.is_dir():
        return boxes, 0

    def near(x0, z0, x1, z1):
        return any(x0 <= w[2] and x1 >= w[0] and z0 <= w[3] and z1 >= w[1] for w in windows)

    for pack in sorted(p for p in base_dir.iterdir() if p.is_dir() and p.name not in skip):
        packs += 1
        for f in pack.rglob("*.mcfunction"):
            for raw in f.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                m = SETBLOCK.match(line)
                if m:
                    x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    if base(m.group(4)) not in ("minecraft:air", "minecraft:cave_air") and near(x, z, x, z):
                        boxes.append((x, z, x, z, y, y, pack.name))
                    continue
                m = FILL.match(line)
                if m and not m.group(8) and base(m.group(7)) not in ("minecraft:air", "minecraft:cave_air"):
                    x0, x1 = sorted((int(m.group(1)), int(m.group(4))))
                    y0, y1 = sorted((int(m.group(2)), int(m.group(5))))
                    z0, z1 = sorted((int(m.group(3)), int(m.group(6))))
                    if near(x0, z0, x1, z1):
                        boxes.append((x0, z0, x1, z1, y0, y1, pack.name))
    return boxes, packs


def hit(boxes, cells, ground=None):
    """[(cell, why)] for cells inside boxes. A box with a y range (7-tuples) counts only where it reaches the ribbon's
    own band, ground - 1 to ground + 6: a cave's ore deep under the same x, z is not a collision."""
    if not boxes or not cells:
        return []
    arr = np.array([b[:4] for b in boxes], dtype=np.int64)
    ys = np.array([b[4:6] for b in boxes], dtype=np.int64) if len(boxes[0]) == 7 else None
    out = []
    for (x, z) in cells:
        m = (arr[:, 0] <= x) & (x <= arr[:, 2]) & (arr[:, 1] <= z) & (z <= arr[:, 3])
        if ys is not None and ground is not None:
            g = ground(x, z)
            m &= (ys[:, 1] >= g - 1) & (ys[:, 0] <= g + 6)
        if m.any():
            out.append(((x, z), boxes[int(np.nonzero(m)[0][0])][-1]))
    return out


def dijkstra(centre, ground, raw, start, max_step=1, max_deg=40.0):
    """{cell: walked distance} over 8-connected centre cells, stepping at most max_step in rounded ground and 40 degrees raw."""
    dist = {start: 0.0}
    pq = [(0.0, start)]
    while pq:
        d, c = heapq.heappop(pq)
        if d > dist.get(c, 1e18):
            continue
        for dx, dz in NEIGH8:
            n = (c[0] + dx, c[1] + dz)
            if n not in centre:
                continue
            if abs(ground(*n) - ground(*c)) > max_step:
                continue
            run = math.hypot(dx, dz)
            if math.degrees(math.atan2(abs(raw(*n) - raw(*c)), run)) > max_deg + 1e-9:
                continue
            nd = d + run
            if nd < dist.get(n, 1e18):
                dist[n] = nd
                heapq.heappush(pq, (nd, n))
    return dist


def start_on_line(spec, towns, placements):
    sx, sz = spec["from_at"]
    if spec.get("from_route"):
        paths = load_json(ROOT / "data" / "route_paths.json")["paths"][spec["from_route"]]
        d = min(math.hypot(px - sx, pz - sz) for px, pz in paths)
        return d <= 1.5, "%.1f blocks from the walked line of %s" % (d, spec["from_route"])
    t = next(t for t in towns if t["id"] == spec["from_town"])
    f = t["footprint"]
    st = placements["settlements"][spec["from_town"]]
    lines = []
    for s in (st.get("plan") or {}).get("streets") or st.get("roads") or []:
        if s.get("polyline"):
            lines.append(np.array(s["polyline"], dtype=float))
    best = min([float(seg_distance(np.array([sx], float), np.array([sz], float), p)[0]) for p in lines] or [1e9])
    edge = min(abs(sx - f["min_x"]), abs(sx - f["max_x"]), abs(sz - f["min_z"]), abs(sz - f["max_z"]))
    on_edge = f["min_x"] - 3 <= sx <= f["max_x"] + 3 and f["min_z"] - 3 <= sz <= f["max_z"] + 3 and edge <= 3
    return best <= 4 or on_edge, "%.1f from the nearest street, %d from the footprint edge" % (best, edge)


def audit_trail(spec, rules, fn, ground, raw, water, ents, boxes_all, other_boxes, seats, names, towns, placements):
    pid = spec["id"]
    probs = []
    centre, flank = fn["centre"], fn["flank"]
    if not centre:
        return ["%s: the function sets no dirt_path (no centre line)" % pid], {}
    ribbon = set(centre) | set(flank)
    # ground: every block at the heightmap's rounded ground
    for (x, z), y in list(centre.items()) + list(flank.items()):
        if y != ground(x, z):
            probs.append("%s: ribbon block at (%d, %d) is y%d, the heightmap's ground is y%d" % (pid, x, z, y, ground(x, z)))
            break
    stray = [(x, z) for (x, z) in flank if not any((x + dx, z + dz) in centre for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    if stray:
        probs.append("%s: %d flank cell(s) not beside the centre line, e.g. %s" % (pid, len(stray), stray[0]))
    # start, walk, end
    sx, sz = spec["from_at"]
    first = min(centre, key=lambda c: math.hypot(c[0] - sx, c[1] - sz))
    if math.hypot(first[0] - sx, first[1] - sz) > 2:
        probs.append("%s: no centre cell within 2 of the start %s (nearest %s)" % (pid, spec["from_at"], first))
    ok_start, how = start_on_line(spec, towns, placements)
    if not ok_start:
        probs.append("%s: start %s is not on the named street or route (%s)" % (pid, spec["from_at"], how))
    ex, ez = ents[spec["to"]]
    reach = rules["stop_short"] + 3
    dist = dijkstra(centre, ground, raw, first)
    goal = [c for c in dist if math.hypot(c[0] - ex, c[1] - ez) <= reach]
    if not goal:
        probs.append("%s: no walkable chain from the start to within %d of (%d, %d): the chain reaches %d of %d centre cells, "
                     "nearest %.0f from the entrance" % (pid, reach, ex, ez, len(dist), len(centre),
                                                         min(math.hypot(c[0] - ex, c[1] - ez) for c in dist)))
        return probs, {}
    walk = min(dist[c] for c in goal)
    off = len(centre) - len(dist)
    if off:
        probs.append("%s: %d centre cell(s) are off the walkable chain from the start (a gap in the line)" % (pid, off))
    if walk > rules["max_length_blocks"]:
        probs.append("%s: the walk is %.0f blocks, past %d" % (pid, walk, rules["max_length_blocks"]))
    # water over every cell a block goes on
    posts = []
    for (x, z), stack in fn["stacks"].items():
        if stack.get(ground(x, z) + 1) == rules["post"]:
            posts.append((x, z))
    cells = sorted(ribbon | set(posts))
    for x, z, why in water.wet(cells, ground)[:3]:
        probs.append("%s: (%d, %d) is water: %s" % (pid, x, z, why))
    # buildings
    near_start = lambda c: math.hypot(c[0] - sx, c[1] - sz) <= rules["start_open"]
    check_cells = [c for c in ribbon if not near_start(c)]
    for c, why in hit(boxes_all(spec), sorted(ribbon))[:3]:
        probs.append("%s: ribbon cell %s is inside %s" % (pid, c, why))
    for c, why in hit(other_boxes, check_cells, ground)[:3]:
        probs.append("%s: ribbon cell %s is inside a box pack %s writes" % (pid, c, why))
    # lanterns
    lamps = []
    for (x, z), stack in fn["stacks"].items():
        y = ground(x, z)
        if stack.get(y + 1) == rules["post"] and stack.get(y + 2) == rules["post"] and stack.get(y + 3) == rules["lamp"]:
            lamps.append((x, z))
        elif stack.get(y + 1) == rules["post"] and not stack.get(y + 2) and stack.get(y + 3) is None:
            pass        # the sign's own fence: one fence, the sign above it
        else:
            probs.append("%s: the blocks at (%d, %d) are %s, neither a lantern post nor the sign's post" % (pid, x, z, stack))
    arcs = []
    for (x, z) in lamps:
        near = min(centre, key=lambda c: math.hypot(c[0] - x, c[1] - z))
        d = math.hypot(near[0] - x, near[1] - z)
        if not 1.9 <= d <= 3.3:
            probs.append("%s: lantern post (%d, %d) is %.1f from the centre line, not 2 to 3" % (pid, x, z, d))
        arcs.append(dist.get(near, 0.0))
    arcs.sort()
    want = int(walk // rules["lantern_every"])
    if abs(len(lamps) - want) > 1:
        probs.append("%s: %d lanterns on a %.0f-block walk, expected %d (one per %d) plus or minus one"
                     % (pid, len(lamps), walk, want, rules["lantern_every"]))
    gaps = [b - a for a, b in zip(arcs, arcs[1:])]
    if gaps and (min(gaps) < rules["lantern_every"] * 0.6 or max(gaps) > rules["lantern_every"] * 1.8):
        probs.append("%s: lantern spacing %.0f to %.0f blocks along the walk, wanted about %d"
                     % (pid, min(gaps), max(gaps), rules["lantern_every"]))
    # sign
    if len(fn["signs"]) != 1:
        probs.append("%s: %d signs, expected 1" % (pid, len(fn["signs"])))
    else:
        x, y, z, rot, front, back = fn["signs"][0]
        if y != ground(x, z) + 2:
            probs.append("%s: the sign is at y%d, the post is at y%d" % (pid, y, ground(x, z) + 1))
        if fn["stacks"].get((x, z), {}).get(ground(x, z) + 1) != rules["post"]:
            probs.append("%s: no fence under the sign at (%d, %d)" % (pid, x, z))
        if math.hypot(x - sx, z - sz) > 14:
            probs.append("%s: the sign is %.0f blocks from the start" % (pid, math.hypot(x - sx, z - sz)))
        for t in front + back:
            if len(t) > 15:
                probs.append("%s: sign line %r is longer than 15 characters" % (pid, t))
        ftxt, btxt = " | ".join(t for t in front if t), " | ".join(t for t in back if t)
        want_name = " ".join(spec["sign"])
        if want_name.replace(" ", "") not in "".join(t for t in front if t).replace(" ", ""):
            probs.append("%s: the front says %r, not the entrance's name %r" % (pid, ftxt, want_name))
        m = re.search(r"(cave|mine) (\d+) blocks", ftxt)
        kind = "mine" if spec["to"].startswith("mn_") else "cave"
        if not m or m.group(1) != kind:
            probs.append("%s: the front says %r; expected '%s N blocks'" % (pid, ftxt, kind))
        else:
            n = int(m.group(2))
            if abs(n - walk) > max(10, 0.1 * walk):
                probs.append("%s: the sign says %d blocks, the walk along the line is %.0f" % (pid, n, walk))
        if names[spec.get("from_town") or spec["from_route"]].replace(" ", "") not in btxt.replace(" ", ""):
            probs.append("%s: the back says %r, expected the start's name %r" % (pid, btxt, names[spec.get("from_town") or spec["from_route"]]))
        # the front faces the traveller who comes from the start: its facing vector points back along the line
        ang = math.radians(rot * 22.5)
        fx, fz = -math.sin(ang), math.cos(ang)
        near = min(dist, key=lambda c: math.hypot(c[0] - x, c[1] - z))
        behind = [c for c in dist if abs(dist[c] - max(0, dist[near] - 6)) < 1.0]
        ahead = [c for c in dist if abs(dist[c] - (dist[near] + 6)) < 1.0]
        if behind and ahead:
            bx, bz = np.mean([c[0] for c in behind]) - np.mean([c[0] for c in ahead]), np.mean([c[1] for c in behind]) - np.mean([c[1] for c in ahead])
            L = math.hypot(bx, bz) or 1.0
            if (fx * bx + fz * bz) / L < 0.5:
                probs.append("%s: the sign's front does not face the traveller coming from the start (rotation %d)" % (pid, rot))
        for sid, (sx_, sy_, sz_) in seats:
            if abs(sx_ - x) <= 1 and abs(sz_ - z) <= 1 and abs(sy_ - (ground(x, z) + 1)) <= 3:
                probs.append("%s: the sign stands against NPC seat %s" % (pid, sid))
    return probs, {"walk": walk, "lamps": len(lamps), "ribbon": len(ribbon), "centre": len(centre)}


def audit(pack=PACK, doc=None, ground=None, raw=None, do_other_packs=True, other_base=None, source_root=None, guide_pack=GUIDE_PACK):
    """(problems, notes)."""
    import ground as G
    import function_limits
    import terrain as T
    from terrain import env_source_root
    doc = doc or load_json(DATA)
    rules = doc["rules"]
    if ground is None:
        g = G.Ground(source_root or env_source_root())
        ground = g
        raw = lambda x, z: float(g.heights[int(z) - g.oz, int(x) - g.ox])
    probs, notes = [], []
    pack = Path(pack)
    fdir = pack / "data" / "cobblers" / "function" / "trails"
    if not fdir.is_dir():
        return ["no %s: run python tools/entrance_trails.py build" % fdir], notes
    index = [l.strip() for l in (fdir / "index.txt").read_text(encoding="utf-8").splitlines() if l.strip()] if (fdir / "index.txt").is_file() else []
    want = [t["id"] for t in doc["trails"]]
    if index != want:
        probs.append("the pack's trail index is %s, data/entrance_trails.json lists %s" % (index, want))
    ents = entrances()
    world = load_json(ROOT / "data" / "world.json")
    water = Water(int(T.sea_level(world)))
    towns = load_json(ROOT / "data" / "towns.json")["towns"]
    placements = load_json(ROOT / "data" / "placements.json")
    seats = [(s["id"], tuple(s["at"])) for s in load_json(ROOT / "data" / "npc_seats.json")["seats"]]
    import signposts as SP
    SP.SUBNAMES.update(SP._subnames())
    names = dict(SP.place_names())
    for rid, label in load_json(ROOT / "data" / "signposts.json")["route_labels"].items():
        names[rid] = label
    fns = {}
    windows = []
    for spec in doc["trails"]:
        f = fdir / ("%s.mcfunction" % spec["id"])
        if f.is_file():
            fns[spec["id"]] = parse_function(f)
            cs = list(fns[spec["id"]]["centre"]) + list(fns[spec["id"]]["flank"])
            if cs:
                windows.append((min(c[0] for c in cs) - 3, min(c[1] for c in cs) - 3, max(c[0] for c in cs) + 3, max(c[1] for c in cs) + 3))
    other, npacks = other_pack_boxes(windows, other_base) if do_other_packs else ([], 0)
    spawn_blocks = set(load_json(ROOT / "data" / "spawn_blocks.json")["blocks"])
    allowed = {rules["centre"], rules["post"], rules["lamp"], "minecraft:air"} | set(rules["flank"]) | {"minecraft:%s_sign" % rules["sign_wood"]}
    boxes_cache = {}

    def boxes_all(spec):
        key = spec.get("from_town")
        if key not in boxes_cache:
            boxes_cache[key] = building_boxes(key)
        return boxes_cache[key]

    for spec in doc["trails"]:
        f = fdir / ("%s.mcfunction" % spec["id"])
        if not f.is_file():
            probs.append("%s: no function file" % spec["id"])
            continue
        fn = fns[spec["id"]]
        bad = sorted(b for b in fn["blocks"] - allowed)
        # a fill's block may also be the tag form used to clear; those are read separately below
        bad = [b for b in bad if not b.startswith("#") and not b.startswith("<unparsed")]
        if bad:
            probs.append("%s: sets blocks outside the table: %s" % (spec["id"], bad))
        un = [b for b in fn["blocks"] if b.startswith("<unparsed")]
        if un:
            probs.append("%s: %d command(s) the audit does not parse, e.g. %s" % (spec["id"], len(un), un[0]))
        spawners = sorted(b for b in fn["blocks"] if b in spawn_blocks)
        if spawners:
            probs.append("%s: sets blocks that are spawn conditions: %s" % (spec["id"], spawners))
        refused = function_limits.check_lines(function_limits.ensure_loaded(fn["lines"]), spec["id"])
        if refused:
            probs.append("%s: %d command(s) the server would refuse: %s" % (spec["id"], len(refused), refused[:2]))
        # fills write only air; under the surface nothing is set
        for (x0, y0, z0, x1, y1, z1, blk) in fn["fills"]:
            if blk != "minecraft:air":
                probs.append("%s: a fill writes %s, expected only air" % (spec["id"], blk))
                break
            if y0 < min(ground(x, z) for x in (x0, x1) for z in (z0, z1)):
                probs.append("%s: a fill reaches y%d, below the surface" % (spec["id"], y0))
                break
        p, got = audit_trail(spec, rules, fn, ground, raw, water, ents, boxes_all, other, seats, names, towns, placements)
        probs += p
        notes.append("%s: %s" % (spec["id"], got if got else "NOT WALKED"))
    notes.append("buildings checked against %d other built pack(s)%s" % (npacks, "" if npacks else " -- NONE built here: that check did not run"))
    # guides: one function each, a tellraw naming the entrance's waypoint
    gdir = Path(guide_pack) / "data" / "cobblers" / "function" / "guides"
    for gd in doc["guides"]:
        f = gdir / ("%s.mcfunction" % gd["id"])
        if not f.is_file():
            probs.append("%s: no guide function" % gd["id"])
            continue
        text = f.read_text(encoding="utf-8")
        ex, ez = ents[gd["goes_to"]]
        m = re.search(r"xaero-waypoint:([^:]+):([^:]+):(-?\d+):(-?\d+):(-?\d+):(\d+):false:0:Internal-overworld-waypoints", text)
        if not m:
            probs.append("%s: no xaero-waypoint share in %s" % (gd["id"], f.name))
            continue
        name, ini, x, y, z, col = m.group(1), m.group(2), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6))
        if (x, z) != (ex, ez) or y != ground(ex, ez) + 1:
            probs.append("%s: the waypoint is (%d, %d, %d), the entrance %s is at (%d, y%d, %d)" % (gd["id"], x, y, z, gd["goes_to"], ex, ground(ex, ez) + 1, ez))
        if not re.fullmatch(r"[A-Za-z0-9 ]{1,32}", name) or not re.fullmatch(r"[A-Za-z0-9]{1,3}", ini) or not 0 <= col <= 15:
            probs.append("%s: the share's name, initials or colour is not one Xaero's share format accepts" % gd["id"])
        if not text.splitlines()[1].startswith("tellraw @s "):
            probs.append("%s: the guide function does not tell the player (tellraw @s)" % gd["id"])
    return probs, notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root", default=None)
    a = ap.parse_args(argv)
    probs, notes = audit(a.pack, source_root=a.source_root)
    for n in notes:
        print("  " + n)
    for p in probs:
        print("  PROBLEM " + p)
    print("entrance trails audit: %s" % ("clean" if not probs else "%d problem(s)" % len(probs)))
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())
