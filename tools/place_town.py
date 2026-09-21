#!/usr/bin/env python
"""Turn a settlement's placements (data/placements.json) into a datapack function that builds it in the world.

For each building, seated on the ground as the world has it (read from the region files of the stopped world,
--surface-world): the template's ground layer is the layer of its entrance jigsaw (the path block in front of
the door sits at grade), and that layer is placed at the ground height in front of the entrance, so the floor
meets the street at grade. Trees and plants in the footprint are cleared; ground above the floor inside the
building is replaced by the template's own air; where the ground falls away below the building, every column
under the ground layer (and any basement) gets a foundation course down to the ground, never a levelled pad.
Then /place template with the rotation that turns its entrance to the requested facing, every jigsaw block
replaced by its final state (a template placed by command keeps its jigsaws), donor loot tables removed, and
donor waystones stripped from a copy of the template before it is placed (one waystone per town, placed
deliberately; the Waystones mod registers a placed waystone and keeps it registered after the block is gone). Then paths (dirt path replacing the
grass surface, plants cleared above), the route's first stretch along the routed leg, the waystone, and the
world spawn.

  verify   over RCON, for every building: at each corner of its ground layer, the floor block is present,
           the block under it is solid (no gap), and the floor height against the natural ground outside

Rotation follows Minecraft's StructureTemplate transform about the placement origin:
  none (x, z) | clockwise_90 (-z, x) | 180 (-x, -z) | counterclockwise_90 (z, -x)
so the command position is the requested footprint corner minus the rotated template's minimum corner.

  python tools/place_town.py hometown --surface-world <stopped world> [--install <server>/datapacks]
  then in game or over RCON: /reload, /function cobblers:towns/hometown
  python tools/place_town.py hometown --verify --server-dir <server>
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import numpy as np

import function_limits
import nbt

ROOT = Path(__file__).resolve().parent.parent
DIRS = ["north", "east", "south", "west"]
ROT = ["none", "clockwise_90", "180", "counterclockwise_90"]
ORIENT_DIR = {"west": "west", "east": "east", "north": "north", "south": "south"}
PLANTS = ["minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern", "minecraft:large_fern", "#minecraft:flowers",
          "minecraft:sweet_berry_bush", "minecraft:dead_bush", "minecraft:leaf_litter", "minecraft:bush"]


def rotate(x, z, rot):
    return {"none": (x, z), "clockwise_90": (-z, x), "180": (-x, -z), "counterclockwise_90": (z, -x)}[rot]


def template_info(path):
    _, doc = nbt.load(path)
    pal = doc["palette"]
    size = doc["size"]
    jigsaws, loot, entrance, entrance_pos, waystones = [], [], None, None, []
    for b in doc["blocks"]:
        p = pal[b["state"]]
        n = b.get("nbt") or {}
        if p["Name"] == "minecraft:jigsaw":
            jigsaws.append((b["pos"], n.get("final_state") or "minecraft:air", (p.get("Properties") or {}).get("orientation", "")))
            if entrance is None and n.get("final_state") in ("minecraft:dirt_path", "minecraft:stone") and not (p.get("Properties") or {}).get("orientation", "").startswith("up"):
                entrance = (p.get("Properties") or {})["orientation"].split("_")[0]
                entrance_pos = b["pos"]
        if n.get("LootTable"):
            loot.append(b["pos"])
        if p["Name"].startswith("waystones:"):
            waystones.append(b["pos"])
    if entrance is None and jigsaws:
        # A donor whose doorstep is not a path block. The Pallet kit marks its entrance with a
        # dirt_path or stone jigsaw, but Repurposed Structures' village houses use the step itself
        # (birch_stairs, planks, a slab), so fall back to the lowest horizontal jigsaw: the one a
        # street connects to. A vertical jigsaw (orientation starting up_ or down_) is a roof or
        # floor connector and is never the door.
        horizontal = [j for j in jigsaws if j[2] and not j[2].startswith(("up", "down"))]
        if horizontal:
            pos, _, orientation = min(horizontal, key=lambda j: (j[0][1], j[0][0], j[0][2]))
            entrance, entrance_pos = orientation.split("_")[0], pos
    side = Path(path).with_suffix(".json")
    if entrance_pos is None and side.exists():
        # a kit prefab (tools/kit.py) records its door in the sidecar instead of an entrance jigsaw
        ent = (json.loads(side.read_text(encoding="utf-8")) or {}).get("entrance")
        if ent:
            entrance, entrance_pos = ent["facing"], list(ent["pos"])
    grade = entrance_pos[1] if entrance_pos else 0
    # columns the building stands on: a stored, non-air block at or below the ground layer
    base = {}
    for b in doc["blocks"]:
        x, y, z = b["pos"]
        nm = pal[b["state"]]["Name"]
        if y <= grade and nm not in ("minecraft:air", "minecraft:structure_void", "minecraft:cave_air"):
            base[(x, z)] = min(base.get((x, z), y), y)
    grade_cols = {(b["pos"][0], b["pos"][2]) for b in doc["blocks"] if b["pos"][1] == grade
                  and pal[b["state"]]["Name"] not in ("minecraft:air", "minecraft:structure_void", "minecraft:cave_air", "minecraft:jigsaw")}
    return {"grade_cols": grade_cols, "size": size, "jigsaws": jigsaws, "loot": loot, "entrance": entrance, "entrance_pos": entrance_pos,
            "grade_layer": grade, "base": base, "waystones": waystones}


def strip_waystones(src, dest):
    """Copy a structure template without its waystone blocks (type-preserving NBT, block entities and entities
    kept). Waystones registers a waystone the moment one is placed and does not forget it when the block is later
    replaced, so a donor's waystone has to be gone from the template itself."""
    import gzip
    import level_dat as L
    raw = Path(src).read_bytes()
    name, root = L.loads(raw)
    if gzip.decompress(L.dumps(name, root)) != gzip.decompress(raw):
        raise SystemExit("%s does not round-trip through the NBT writer; refusing to rewrite it" % src)
    pal = root["palette"][1][1]
    names = [L.plain(e["Name"]) for e in pal]
    lt, blocks = root["blocks"][1]
    keep = [b for b in blocks if not names[L.plain(b["state"])].startswith("waystones:")]
    root["blocks"] = (root["blocks"][0], (lt, keep))
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_bytes(L.dumps(name, root))
    return len(blocks) - len(keep)


def rotation_for(entrance, facing):
    k = (DIRS.index(facing) - DIRS.index(entrance)) % 4
    return ROT[k]


def footprint(size, rot):
    sx, _, sz = size
    corners = [rotate(x, z, rot) for x in (0, sx - 1) for z in (0, sz - 1)]
    xs, zs = [c[0] for c in corners], [c[1] for c in corners]
    return min(xs), min(zs), max(xs) - min(xs) + 1, max(zs) - min(zs) + 1


def fill_boxes(x0, y0, z0, x1, y1, z1, limit=32768):
    """Split a fill volume into boxes under the command's block limit (whole layers first)."""
    area = (x1 - x0 + 1) * (z1 - z0 + 1)
    per = max(1, limit // max(area, 1))
    if area > limit:
        half = (x0 + x1) // 2
        return fill_boxes(x0, y0, z0, half, y1, z1, limit) + fill_boxes(half + 1, y0, z0, x1, y1, z1, limit)
    return [(x0, y, z0, x1, min(y1, y + per - 1), z1) for y in range(y0, y1 + 1, per)]


def forceload_commands(box, verb, limit=256):
    """One or more forceload commands covering the box, each inside the 256-chunk limit.

    `/forceload add` refuses more than 256 chunks and refuses the whole command, so a single call over
    a big town leaves every later command running on unloaded ground. Brock's build function asked for
    270 chunks in one go (found 2026-09-20 by tools/function_limits.py), which is why the town's roads
    and waystone were written into chunks the server had not loaded.
    """
    x0, z0, x1, z1 = box
    cx0, cz0, cx1, cz1 = x0 // 16, z0 // 16, x1 // 16, z1 // 16
    wide = cx1 - cx0 + 1
    rows = max(1, min(cz1 - cz0 + 1, limit // max(wide, 1)))
    out = []
    for c in range(cz0, cz1 + 1, rows):
        c_end = min(c + rows - 1, cz1)
        out.append("forceload %s %d %d %d %d" % (verb, x0, c * 16, x1, c_end * 16 + 15))
    return out


def build(settlement, doc, ground_at, legs_doc=None, out_dir=None):
    """ground_at(x, z) -> Y of the world's ground (the highest block that is not air, water, a plant or a tree)."""
    s = doc["settlements"][settlement]
    plan = s.get("plan") or {}
    # lot id -> the top of the ground range tools/town_plan.py measured for it, off the heightmap
    lot_ground = {}
    _computed = ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)
    if _computed.is_file():
        _doc = json.loads(_computed.read_text(encoding="utf-8"))
        for _l in (_doc.get("lots") or []) + (_doc.get("anchors") or []):
            if _l.get("ground_range"):
                lot_ground[_l["id"]] = int(max(_l["ground_range"]))
    cmds = ["# Generated by tools/place_town.py from data/placements.json (%s). Re-run to rebuild." % settlement]
    report = {"buildings": [], "roads": {}, "placed_by_place_donor": []}
    boxes = []
    seated = {}                                     # (x, z) -> Y of the building's ground layer there
    # A placement with no local file is one of the pack's own structures, placed by
    # tools/place_donor.py from its resource id (Brock's gym is the first): its geometry cannot be
    # read here and its function is generated separately.
    skipped_donors = [q["id"] for q in doc["placements"]
                      if q.get("settlement") == settlement and not q.get("file")]
    for p in [q for q in doc["placements"] if q.get("settlement") == settlement and q.get("file")]:
        info = template_info(ROOT / p["file"])
        if info["entrance_pos"] is None:
            raise SystemExit("%s: template %s has no entrance jigsaw (a horizontal jigsaw whose final state is a dirt "
                             "path or stone) and no sidecar entrance, so its ground layer and door are unknown; refusing to seat it"
                             % (p["id"], p["template"]))
        rot = rotation_for(info["entrance"], p["facing"])
        if p.get("rotation") and p["rotation"] != rot:
            raise SystemExit("%s: rotation %s in data does not turn its %s entrance to face %s (needs %s)"
                             % (p["id"], p["rotation"], info["entrance"], p["facing"], rot))
        mnx, mnz, w, d = footprint(info["size"], rot)
        x0, z0 = p["position"]["x"], p["position"]["z"]
        x1, z1 = x0 + w - 1, z0 + d - 1
        for other in boxes:
            if not (x1 < other[1] or x0 > other[3] or z1 < other[2] or z0 > other[4]):
                raise SystemExit("%s overlaps %s" % (p["id"], other[0]))
        boxes.append((p["id"], x0, z0, x1, z1))
        px, pz = x0 - mnx, z0 - mnz
        G, H = info["grade_layer"], info["size"][1]

        def world_xz(tx, tz):
            rx, rz = rotate(tx, tz, rot)
            return px + rx, pz + rz
        # grade: the ground in front of the entrance, one block outside it
        ex, ez = world_xz(info["entrance_pos"][0], info["entrance_pos"][2])
        step = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}[p["facing"]]
        front = [ground_at(ex + step[0] * k + step[1] * j, ez + step[1] * k + step[0] * j) for k in (1, 2) for j in (-1, 0, 1)]
        under = [ground_at(xx, zz) for zz in range(z0, z1 + 1) for xx in range(x0, x1 + 1)]
        # The floor goes at the door's grade, but never below the highest ground the lot was measured
        # at: on a lot with any fall the uphill side is otherwise buried, which is what "the houses
        # are underground half the time by a block" meant.
        #
        # The lot's measured range comes from tools/town_plan.py, off the heightmap. It deliberately
        # does not come from the surface world: ground_at reads whatever is there now, and on a
        # rebuild that includes the last build, so a town re-run against itself climbs a few blocks
        # every time. That is what raised Brock's houses six to ten blocks above their own street.
        floor_floor = lot_ground.get(p.get("lot"))
        Y = int(np.median(front))
        if floor_floor is not None:
            Y = max(Y, floor_floor)
        oy = Y - G                                  # command Y of the template origin
        m = 2
        lo_clear = min(under) - 1
        cmds.append("forceload add %d %d %d %d" % (x0 - 16, z0 - 16, x1 + 16, z1 + 16))
        # trees and plants over the footprint and a 2-block margin, from below the lowest ground to above the roof
        for tag in ("#minecraft:logs", "#minecraft:leaves"):
            for bx in fill_boxes(x0 - m, lo_clear, z0 - m, x1 + m, oy + H + 6, z1 + m):
                cmds.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (bx + (tag,)))
        for plant in PLANTS:
            for bx in fill_boxes(x0 - m, lo_clear, z0 - m, x1 + m, max(Y, max(under)) + 2, z1 + m):
                cmds.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (bx + (plant,)))
        # any fluid the ground brought with it, cleared before the template lands so the building does
        # not enclose it. A template that wants water or lava puts its own back afterwards. One block
        # of natural lava sat inside Brock's armorer house until tools/town_audit.py found it, and
        # lava decides what spawns wherever it is.
        for fluid in ("minecraft:lava", "minecraft:water"):
            # over the margin too: a source just outside the footprint flows straight back in, which
            # is how the block in Brock's armorer house survived the first attempt at this
            # from below the floor, not from the template's lowest stored block: in Brock's armorer
            # house those differ by two, and the lava sat in the gap
            for bx in fill_boxes(x0 - m, min(lo_clear, Y - 2), z0 - m, x1 + m, oy + H + 2, z1 + m):
                cmds.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (bx + (fluid,)))
        template_id = p["template"]
        if info["waystones"]:
            if out_dir is None:
                raise SystemExit("%s carries waystones; building it needs an output datapack to hold the stripped copy" % p["id"])
            ns, path_ = template_id.split(":")
            template_id = "cobblers:towns/stripped/%s/%s" % (ns, path_)
            strip_waystones(ROOT / p["file"], Path(out_dir) / "data" / "cobblers" / "structure" / "towns" / "stripped" / ns / (path_ + ".nbt"))
        cmds.append("place template %s %d %d %d %s none 1.0 0" % (template_id, px, oy, pz, rot))
        for (jx, jy, jz), final, _ in info["jigsaws"]:
            wx, wz = world_xz(jx, jz)
            state = final if final != "minecraft:structure_void" else "minecraft:air"
            cmds.append("setblock %d %d %d %s" % (wx, oy + jy, wz, state))
        for (lx, ly, lz) in info["loot"]:
            wx, wz = world_xz(lx, lz)
            cmds.append("data remove block %d %d %d LootTable" % (wx, oy + ly, wz))
        stripped = [list(q) for q in info["waystones"]]
        # foundation: under every column the building stands on, down to the ground
        material = p.get("foundation") or "minecraft:stone_bricks"
        found_cols, found_max, cut_max, corners = 0, 0, 0, []
        cols = []
        for (tx, tz), by in info["base"].items():
            wx, wz = world_xz(tx, tz)
            bottom = oy + by                        # world Y of the lowest block in this column
            gy = ground_at(wx, wz)
            cols.append((wx, wz, bottom, gy))
            seated[(wx, wz)] = Y
            if gy < bottom - 1:
                cmds.append("fill %d %d %d %d %d %d %s" % (wx, gy + 1, wz, wx, bottom - 1, wz, material))
                found_cols += 1
                found_max = max(found_max, bottom - 1 - gy)
            if by > 0:
                # the template stores air under this column's lowest block (placed after it, so it would leave a
                # pocket): air below a column's lowest block is never a room, so fill it
                cmds.append("fill %d %d %d %d %d %d %s replace #minecraft:replaceable" % (wx, oy, wz, wx, bottom - 1, wz, material))
            cut_max = max(cut_max, gy - Y)
        cmds.append("forceload remove %d %d %d %d" % (x0 - 16, z0 - 16, x1 + 16, z1 + 16))
        # verification points: the ground-layer column nearest each footprint corner
        at_grade = {world_xz(tx, tz) for (tx, tz) in info["grade_cols"]}
        for cxx, czz in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
            bx, bz = min(at_grade, key=lambda q: (q[0] - cxx) ** 2 + (q[1] - czz) ** 2)
            ox = cxx + (-1 if cxx == x0 else 1)            # one block outside the footprint corner
            oz = czz + (-1 if czz == z0 else 1)
            corners.append({"corner": [cxx, czz], "column": [bx, bz], "floor_y": Y, "outside": [ox, oz],
                            "ground_outside_y": ground_at(ox, oz)})
        report["buildings"].append({"id": p["id"], "template": p["template"], "rotation": rot, "facing": p["facing"],
                                    "footprint": [x0, z0, x1, z1], "grade_layer": G, "floor_y": Y, "origin_y": oy,
                                    "entrance_ground": sorted(front), "ground_under": [min(under), max(under)],
                                    "foundation_columns": found_cols, "foundation_max_height": found_max,
                                    "cut_into_ground_max": cut_max, "waystones_stripped_from_template": stripped, "template_placed": template_id,
                                    "columns": [[c[0], c[1], c[2]] for c in cols], "corners": corners,
                                    "command_position": [px, oy, pz]})

    def surface(x, z):
        return seated.get((x, z), ground_at(x, z))

    def lay(points, width, material, rid):
        cols = set()
        half = width // 2
        for (ax, az), (bx, bz) in zip(points, points[1:]):
            n = int(max(abs(bx - ax), abs(bz - az))) + 1
            for i in range(n):
                t = i / max(n - 1, 1)
                cx, cz = round(ax + (bx - ax) * t), round(az + (bz - az) * t)
                for dx in range(-half, half + 1):
                    for dz in range(-half, half + 1):
                        cols.add((cx + dx, cz + dz))
        # group columns into short runs along x for compact commands
        by_row = {}
        for x, z in cols:
            by_row.setdefault(z, []).append(x)
        count = 0
        for z, xs in sorted(by_row.items()):
            xs.sort()
            run = [xs[0]]
            for x in xs[1:] + [None]:
                if x is not None and x == run[-1] + 1 and len(run) < 24:
                    run.append(x)
                    continue
                ys = [surface(xx, z) for xx in run]
                lo, hi = min(ys) - 3, max(ys) + 3
                cmds.append("fill %d %d %d %d %d %d %s replace minecraft:grass_block" % (run[0], lo, z, run[-1], hi, z, material))
                for plant in PLANTS:
                    cmds.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (run[0], lo + 3, z, run[-1], hi + 3, z, plant))
                count += len(run)
                if x is not None:
                    run = [x]
        report["roads"][rid] = count

    allx = [b[1] for b in boxes] + [b[3] for b in boxes]
    allz = [b[2] for b in boxes] + [b[4] for b in boxes]
    force = (min(allx) - 40, min(allz) - 40, max(allx) + 40, max(allz) + 40)
    cmds += forceload_commands(force, "add")
    # A planned town's streets carry the same three things a hometown road does: a polyline, a width
    # and a surface. The plaza is paved as a one-segment street across its own rectangle.
    ways = list(s.get("roads") or [])
    if not ways:
        ways = list(plan.get("streets") or [])
        pz = plan.get("plaza")
        if pz and (pz.get("rect") or pz.get("box")):
            x0, z0, x1, z1 = pz.get("rect") or pz["box"]
            ways.append({"id": pz.get("id", "plaza"),
                         "polyline": [[x0, (z0 + z1) // 2], [x1, (z0 + z1) // 2]],
                         "width": z1 - z0 + 1,
                         "surface": pz.get("surface", "minecraft:polished_andesite")})
    for r in ways:
        pts = r.get("polyline")
        if r.get("follow_leg"):
            leg = next(l for l in legs_doc["legs"] if "%s->%s" % (l["from"], l["to"]) == r["follow_leg"])
            poly = np.array(leg["polyline"], float)
            start = np.array(r["from"], float)
            i0 = int(np.argmin(np.hypot(*(poly - start).T)))
            pts, total = [list(map(int, start))], 0.0
            for q in poly[i0 + 1:]:
                total += math.dist(pts[-1], q)
                pts.append([int(q[0]), int(q[1])])
                if total >= r["length_blocks"]:
                    break
            report["route_points"] = pts
        lay(pts, r["width"], r["surface"], r["id"])
    # Clear any waystone already standing in the town before setting one. setblock places rather
    # than replaces, so every rebuild left another behind, and a waystone the player breaks still
    # leaves the mod's registry entry: the stacking is in waystones.dat as well as in the world,
    # and that file is cleared separately (REEXPORT.md R12).
    _ys = list(seated.values()) or [64]
    for _bx in fill_boxes(min(allx) - 24, min(_ys) - 8, min(allz) - 24,
                          max(allx) + 24, max(_ys) + 40, max(allz) + 24):
        cmds.append("fill %d %d %d %d %d %d minecraft:air replace waystones:waystone" % _bx)
    way = s.get("waystone") or plan.get("waystone")
    if way:
        wx, wz = way["position"]
        wy = surface(wx, wz) + 1
        cmds += ["setblock %d %d %d waystones:waystone[half=lower,facing=%s]" % (wx, wy, wz, way["facing"]),
                 "setblock %d %d %d waystones:waystone[half=upper,facing=%s]" % (wx, wy + 1, wz, way["facing"])]
    # only the hometown moves the world spawn
    if s.get("spawn"):
        sx, sz = s["spawn"]
        sy = surface(sx, sz) + 1
        cmds.append("setworldspawn %d %d %d" % (sx, sy, sz))
    cmds += forceload_commands(force, "remove")
    if way:
        report["waystone"] = [wx, wy, wz]
    if s.get("spawn"):
        report["spawn"] = [sx, sy, sz]
    report["commands"] = len(cmds)
    report["placed_by_place_donor"] = skipped_donors
    return cmds, report


def settlement_bounds(settlement, doc, margin=64):
    """The ground this build needs read, from whatever the settlement records.

    The hometown carries roads, a waystone and a world spawn. A town laid out by tools/town_plan.py
    carries a plan instead: streets with polylines, a plaza and a waystone. Both shapes are read here
    so a planned town does not need the hometown's schema to be built.
    """
    s = doc["settlements"][settlement]
    plan = s.get("plan") or {}
    xs, zs = [], []
    for q in doc["placements"]:
        if q.get("settlement") == settlement:
            xs.append(q["position"]["x"]); zs.append(q["position"]["z"])
    for r in s.get("roads") or []:
        for x, z in r.get("polyline") or []:
            xs.append(x); zs.append(z)
        if r.get("from"):
            L = r.get("length_blocks", 0)
            xs += [r["from"][0] - L, r["from"][0] + L]; zs += [r["from"][1] - L, r["from"][1] + L]
    for street in plan.get("streets") or []:
        for x, z in street.get("polyline") or []:
            xs.append(x); zs.append(z)
    for box in ([plan["plaza"]] if plan.get("plaza") else []):
        rect = box.get("rect") or box.get("box")
        if rect:
            xs += [rect[0], rect[2]]; zs += [rect[1], rect[3]]
    for key in ("waystone", "spawn"):
        v = s.get(key) or plan.get(key)
        if not v:
            continue
        v = v["position"] if isinstance(v, dict) else v
        xs.append(v[0]); zs.append(v[1])
    if not xs:
        raise SystemExit("%s: nothing to build, and no streets or roads to read ground from" % settlement)
    return min(xs) - margin, min(zs) - margin, max(xs) + margin, max(zs) + margin


def verify(settlement, server_dir):
    """Floor against ground over RCON for every building placed by the last build of this settlement."""
    import sys
    rep = json.loads((ROOT / "derived" / "towns" / ("%s_placement.json" % settlement)).read_text(encoding="utf-8"))
    import runtime_guard
    rcon, pw = runtime_guard.rcon(server_dir)

    def solid(x, y, z):
        return "passed" in rcon.run(["execute unless block %d %d %d #minecraft:replaceable" % (x, y, z)], pw)[0]

    def top_solid(x, z, start, stop, skip_trees=False):
        for y in range(start, stop, -1):
            if solid(x, y, z):
                if skip_trees and any("passed" in r for r in rcon.run(
                        ["execute if block %d %d %d #minecraft:%s" % (x, y, z, t) for t in ("leaves", "logs")], pw)):
                    continue
                return y
        return None
    out = {"buildings": [], "gaps": 0, "columns_checked": 0}
    fb = rep["buildings"]
    xs = [b["footprint"][0] for b in fb] + [b["footprint"][2] for b in fb]
    zs = [b["footprint"][1] for b in fb] + [b["footprint"][3] for b in fb]
    rcon.run(["forceload add %d %d %d %d" % (min(xs) - 4, min(zs) - 4, max(xs) + 4, max(zs) + 4)], pw)
    for b in fb:
        rows = []
        for c in b["corners"]:
            x, z = c["column"]
            Y = c["floor_y"]
            floor = solid(x, Y, z)
            support = top_solid(x, z, Y - 1, Y - 40)
            ox, oz = c["outside"]
            grade = top_solid(ox, oz, Y + 12, Y - 40, skip_trees=True)
            rows.append({"column": [x, z], "floor_y": Y, "floor_block_present": floor, "support_y": support,
                         "gap": (Y - 1 - support) if support is not None else None, "outside_ground_y": grade,
                         "floor_minus_outside_ground": (Y - grade) if grade is not None else None})
        # every column the building stands on: the block under its lowest block is solid
        gaps = []
        for x, z, bottom in b["columns"]:
            if not solid(x, bottom - 1, z):
                gaps.append([x, bottom - 1, z])
        out["columns_checked"] += len(b["columns"])
        out["gaps"] += len(gaps) + sum(1 for r in rows if r["gap"] != 0 or not r["floor_block_present"])
        out["buildings"].append({"id": b["id"], "floor_y": b["floor_y"], "corners": rows,
                                 "columns": len(b["columns"]), "columns_with_gap_below": gaps[:10], "gap_count": len(gaps)})
    rcon.run(["forceload remove %d %d %d %d" % (min(xs) - 4, min(zs) - 4, max(xs) + 4, max(zs) + 4)], pw)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("settlement")
    p.add_argument("--placements", default=str(ROOT / "data" / "placements.json"))
    p.add_argument("--legs", default=str(ROOT / "derived" / "routes" / "critical_legs.json"))
    p.add_argument("--surface-world", default=None, help="stopped world folder whose region files give the ground")
    p.add_argument("--out", default=None)
    p.add_argument("--install", default=None, help="copy the datapack into this datapacks folder")
    p.add_argument("--world", help="a STOPPED world copy; with --verify it also audits the town's blocks")
    p.add_argument("--verify", action="store_true", help="check the built settlement over RCON")
    p.add_argument("--server-dir", default=None)
    a = p.parse_args(argv)
    if a.verify:
        res = verify(a.settlement, a.server_dir)
        # the block audit runs with the floor check, not when somebody remembers it: the two failures
        # it catches (a refused substitution, a fluid the ground brought) both look fine from here
        if a.world:
            import town_audit
            res["spawn_block_audit"] = town_audit.audit(a.settlement, a.world)
            bad = res["spawn_block_audit"]["unsubstituted"], res["spawn_block_audit"]["not_in_policy"]
            res["spawn_block_problems"] = sum(len(x) for x in bad)
        path = ROOT / "derived" / "towns" / ("%s_verify.json" % a.settlement)
        path.write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(json.dumps(res, indent=1))
        raise SystemExit(0 if (res["gaps"] == 0 and not res.get("spawn_block_problems")) else 1)
    if not a.surface_world:
        raise SystemExit("--surface-world is required: buildings are seated on the ground as the world has it")
    import world_heights
    out = Path(a.out or ROOT / "build" / "datapacks" / "cobblers_towns")
    doc = json.loads(Path(a.placements).read_text(encoding="utf-8"))
    legs = json.loads(Path(a.legs).read_text(encoding="utf-8")) if Path(a.legs).exists() else None
    bx0, bz0, bx1, bz1 = settlement_bounds(a.settlement, doc)
    ground, _, meta = world_heights.extract(a.surface_world, (bx0, bz0, bx1, bz1))
    if meta["columns_without_ground"]:
        raise SystemExit("%d columns without ground in %s" % (meta["columns_without_ground"], a.surface_world))

    def ground_at(x, z):
        if not (bx0 <= x <= bx1 and bz0 <= z <= bz1):
            raise SystemExit("(%d, %d) is outside the extracted ground %s" % (x, z, (bx0, bz0, bx1, bz1)))
        return int(ground[z - bz0, x - bx0])
    cmds, report = build(a.settlement, doc, ground_at, legs, out)
    fn = out / "data" / "cobblers" / "function" / "towns" / ("%s.mcfunction" % a.settlement)
    fn.parent.mkdir(parents=True, exist_ok=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: settlement placement functions (tools/place_town.py)"}}, indent=2) + "\n", encoding="utf-8")
    # a command the server would refuse is never written: a refused command reports nothing, and
    # a build that quietly did half its work is worse than one that failed outright
    refused = function_limits.check_lines(cmds, str(fn))
    if refused:
        for _n, _cmd, _why in refused:
            print("REFUSED line %d: %s" % (_n, _why))
            print("   %s" % _cmd)
        raise SystemExit("%s: %d command(s) the server would refuse; not written" % (fn, len(refused)))
    fn.write_text("\n".join(cmds) + "\n", encoding="utf-8")
    rep = ROOT / "derived" / "towns" / ("%s_placement.json" % a.settlement)
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(dict(report, surface_world=str(a.surface_world), ground_bounds=[bx0, bz0, bx1, bz1]), indent=1), encoding="utf-8")
    print(json.dumps({"buildings": [{k: v for k, v in b.items() if k not in ("columns", "corners")} for b in report["buildings"]],
                      **{k: v for k, v in report.items() if k not in ("buildings", "route_points")}}, indent=1))
    if a.install:
        import runtime_guard
        dest = runtime_guard.check(a.install, "install into") / out.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(out, dest)
        print("installed", dest)


if __name__ == "__main__":
    main()
