#!/usr/bin/env python
"""The sea's block pass: the shore before Dive, wrecks and Rift debris on the seabed, and the surfacing cave, from
data/sea_life.json (docs/mechanics/WATER_LIFE.md sections 3, 4 and 5).

Everything is decided from the data file, the canonical heightmap (tools/ground.py, rounded; it IS the applied water
export, so the bars, flats, skerries, the Relic reef platform and the seabed are ground) and the sea level in
data/world.json. Never a world. Nothing here changes a height: every write is a block on or under the ground.

  shore      kelp beds past the wade line and seagrass on the flats (the coasts data/water_shape.json shaped); coral,
             fans and sea pickles on the Relic reef platform only; rock pools as boulder RIMS on the ground at the
             tide line holding water above it (never a cut); a hull lying on its side on the south strand with a
             barrel in it; a waterline sea cave on the windward coast, walked into on foot, a barrel at its end
  finds      procedural wreck and Rift-debris kits written block by block (no template: licence and auditability,
             WATER_LIFE.md Departures), seated on the seabed, flooded (no air), spaced by a density rule per band and
             marine region; the debris in lines on rays from the Rift's centre, each facing it; a hook on every find in
             Surf reach; a barrel in one find in four
  surfacing  one cave under the windward headland: a mouth 20-40 deep on the shelf's edge, a flooded passage under the
             shelf rising into an air chamber whose pool is the only way in, dry galleries on foot to a barrel and to a
             sealed glass crack in the hillside; the underwater length longer than a Surf breath (data/blackout.json,
             read at run time); a lantern at the mouth

Exclusions come from the existing helpers: tools/water_shape.py's protect mask, lake mask, gate lines and coast
masks (run on the water export's own input heightmap, sha-checked, so they are the columns the export kept), and the
data files named in data/sea_life.json exclusions. tools/water_shape.py's gate-line endpoints are derived, so this
tool recomputes them (it needs the pre-water heightmap under the source root, never derived/).

WHAT THIS DOES NOT COVER (say it, CLAUDE.md "Our list is not the world"): things another pack writes in the sea that
no data file lists (a template's own blocks, the Lumyverse structures, anything an earlier pass left). The find's
spacing is against this pack's own writes and the listed exclusions only.

  python tools/sea_life.py report  [--source-root DIR]     the model's checks and numbers; nothing written
  python tools/sea_life.py build   [--source-root DIR]     -> build/datapacks/cobblers_sea_life, derived/sea_life/plan.json
  python tools/sea_life.py records [--write]               the cache records for data/rewards.json (only sea_life_*)

Run order on a world: every function in build/datapacks/cobblers_sea_life/data/cobblers/function/sea_life/index.txt in
order (shell, carve, build, flora, fittings), with the rewards pack installed. The independent offline audit is
tools/sea_life_audit.py (another hand's).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ground as G             # noqa: E402
import rift_mines as RM        # noqa: E402  (hashing, column runs and the tiled pack writer)
import terrain as T            # noqa: E402
import water_mask as WM        # noqa: E402
import water_shape as WS       # noqa: E402

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "sea_life.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_sea_life"
PLAN = ROOT / "derived" / "sea_life" / "plan.json"
REWARDS = ROOT / "data" / "rewards.json"
BLACKOUT = ROOT / "data" / "blackout.json"
NS = "cobblers"
FOLDER = "sea_life"
PASSES = ("shell", "carve", "build", "flora", "fittings")
AIR, WATER = "minecraft:air", "minecraft:water"
REWARD_PREFIX = "sea_life_"
FACINGS = ("north", "east", "south", "west")
STEP = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
BARREL = "minecraft:barrel[facing=up,open=false]"
LANTERN_WET = "minecraft:lantern[hanging=false,waterlogged=true]"
LANTERN_HANG = "minecraft:lantern[hanging=true,waterlogged=false]"
LANTERN_DRY = "minecraft:lantern[hanging=false,waterlogged=false]"
# block ids that carry a `waterlogged` state (stated here, used by the flooded check; vanilla 1.21.1)
WATERLOGGABLE = ("_slab", "_stairs", "_fence", "_wall", "glass_pane", "iron_bars", "chain", "lantern", "_trapdoor",
                 "powered_rail", "sea_pickle", "_coral", "_coral_fan", "_coral_wall_fan", "ladder")
# not waterloggable and not air: they keep water out of their own cell. Doors and beds block a fluid's spread in
# vanilla's FlowingFluid.canHoldFluid; a closed fence gate and a cauldron block motion. [A] read from vanilla, not run
DRY_IN_WATER = ("barrel",)    # a full block: no swimmer's eyes can enter it. Doors, beds, fence gates and
                               # cauldrons are partial and hold no water, so they are never written under water
NOT_FULL = ("_slab", "_stairs", "_fence", "_wall", "glass_pane", "iron_bars", "chain", "lantern", "_trapdoor", "rail",
            "sea_pickle", "coral", "_door", "_bed", "_fence_gate", "cauldron", "kelp", "seagrass")

h32, u, pick = RM.h32, RM.u, RM.pick


class LifeError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def bid(b):
    return b.split("[")[0]


def waterloggable(b):
    i = bid(b)
    return i.endswith(WATERLOGGABLE) and not i.endswith("_fence_gate") and "wall_sign" not in i


def running_min2d(a, r):
    return -WS.running_max2d(-np.asarray(a, np.float64), r)


def dilate3(a, n):
    """Chebyshev dilation of a 3-D bool array by n (sea_drift.dilate)."""
    out = a.copy()
    for axis in range(3):
        cur = out.copy()
        for k in range(1, n + 1):
            sa = [slice(None)] * 3
            sb = [slice(None)] * 3
            sa[axis], sb[axis] = slice(k, None), slice(None, -k)
            cur[tuple(sa)] |= out[tuple(sb)]
            cur[tuple(sb)] |= out[tuple(sa)]
        out = cur
    return out


# ------------------------------------------------------------------ block states and rotation

def rot_xz(dx, dz, steps):
    """Rotate a local offset clockwise by 90 degrees `steps` times (north -> east -> south -> west)."""
    for _ in range(steps % 4):
        dx, dz = -dz, dx
    return dx, dz


def rot_block(b, steps):
    if "[" not in b or steps % 4 == 0:
        return b
    name, props = b[:-1].split("[", 1)
    out = []
    for kv in props.split(","):
        k, v = kv.split("=")
        if k == "facing" and v in FACINGS:
            v = FACINGS[(FACINGS.index(v) + steps) % 4]
        elif k == "axis" and steps % 2 and v in ("x", "z"):
            v = "z" if v == "x" else "x"
        elif k == "shape" and steps % 2 and v in ("north_south", "east_west"):
            v = "east_west" if v == "north_south" else "north_south"
        out.append("%s=%s" % (k, v))
    return "%s[%s]" % (name, ",".join(out))


def slab(m):
    return "minecraft:%s_slab[type=bottom,waterlogged=true]" % m


def stairs(m, facing):
    return "minecraft:%s_stairs[facing=%s,half=bottom,shape=straight,waterlogged=true]" % (m, facing)


def fence(m):
    return "minecraft:%s_fence[waterlogged=true]" % m


def log(m, axis):
    return "minecraft:%s_log[axis=%s]" % (m, axis)


def trapdoor(m, facing, open_):
    return "minecraft:%s_trapdoor[facing=%s,half=bottom,open=%s,powered=false,waterlogged=true]" % (m, facing, open_)


# ------------------------------------------------------------------ the kits (canonical: the front faces north, -z)
# each returns {"cells": [(dx, dy, dz, block)], "cache": (dx, dy, dz), "hook": (kind, dx, dz)}; "HULL" is a planks
# block picked per world cell from the palette

def kit_rowboat(k):
    c = [(dx, 0, dz, "HULL") for dx in (-1, 0, 1) for dz in (-1, 0, 1)] + [(0, 0, -2, "HULL"), (0, 0, 2, "HULL")]
    c += [(dx, 1, dz, slab("spruce")) for dx in (-1, 1) for dz in (-1, 0, 1)]
    c += [(0, 1, -2, slab("spruce")), (0, 1, 2, slab("spruce")), (0, 1, 0, slab("spruce"))]
    return {"cells": c, "cache": (0, 1, 1), "hook": ("lantern", 0, -1), "kind": "vessel"}


def kit_fishing_boat(k):
    def w(dz):
        return 2 if -2 <= dz <= 4 else (1 if dz in (-4, -3, 5) else 0)
    c = []
    for dz in range(-5, 6):
        hw = w(dz)
        for dx in range(-max(hw - 1, 0), max(hw - 1, 0) + 1):
            c.append((dx, 0, dz, "HULL"))
        if hw >= 1 and dz < 5:
            for side in (-hw, hw):
                if h32(k, side, dz, 1) % 9:
                    c.append((side, 1, dz, "HULL"))
                c.append((side, 2, dz, slab("spruce")))
    c += [(dx, y, 5, "HULL") for dx in (-1, 0, 1) for y in (1, 2)]
    c += [(0, 1, -5, "HULL"), (0, 2, -5, slab("spruce"))]
    for dz in (2, 3, 4):                                  # the cabin at the stern
        for dx in (-1, 1):
            for y in (1, 2, 3):
                c.append((dx, y, dz, "minecraft:glass_pane[waterlogged=true]" if (y == 2 and dz == 3) else "HULL"))
        for dx in (-1, 0, 1):
            c.append((dx, 4, dz, "HULL"))
    c += [(0, 3, 4, "HULL")]
    c += [(0, y, -2, log("spruce", "y")) for y in (1, 2, 3, 4)]
    return {"cells": c, "cache": (0, 1, 3), "hook": ("mast", 0, -2), "kind": "vessel"}


def kit_two_master_broken(k):
    def hw(dz):
        a = abs(dz)
        return 3 if a <= 6 else (2 if a <= 8 else (1 if a <= 9 else 0))
    cells = []
    for dz in range(-10, 11):
        w = hw(dz)
        if w == 0:
            cells += [(0, y, dz, "HULL") for y in range(0, 4)]
            continue
        cells += [(dx, 0, dz, log("stripped_spruce", "z") if dx == 0 else "HULL") for dx in range(-(w - 1), w)]
        for side in (-w, w):
            for y in (1, 2, 3):
                if dz in (-1, 0) and h32(k, side, y, dz, 2) % 2:
                    continue                                  # the break is jagged
                cells.append((side, y, dz, "HULL"))
        if w >= 2:
            for dx in range(-(w - 1), w):
                if h32(k, dx, dz, 3) % 3 and dz not in (-1, 0):
                    cells.append((dx, 4, dz, slab("dark_oak")))
    m1 = 5 + h32(k, 4) % 3
    m2 = 4 + h32(k, 5) % 3
    cells += [(0, y, -6, log("spruce", "y")) for y in range(1, m1)]
    cells += [(0, y, 5, log("spruce", "y")) for y in range(1, m2)]
    out = []
    for (dx, y, dz, b) in cells:
        if dz < 0:                                            # the bow half lies two over and three forward
            dx, dz = dx + 2, dz - 3
        out.append((dx, y, dz, b))
    seen = {}
    for c in out:
        seen[(c[0], c[1], c[2])] = c[3]
    return {"cells": [(a, b, c, v) for (a, b, c), v in seen.items()], "cache": (0, 1, 7), "hook": ("mast", 0, 5),
            "kind": "vessel"}


def kit_log_raft(k):
    c = []
    for dx in range(-2, 3):
        for dz in range(-3, 4):
            if abs(dx) == 2 and h32(k, dx, dz, 6) % 7 == 0:
                continue
            c.append((dx, 0, dz, log("spruce", "z")))
    for dz in (-2, 2):
        c += [(dx, 1, dz, "minecraft:chain[axis=x,waterlogged=true]") for dx in range(-1, 2)]
    c += [(0, y, 0, log("stripped_spruce", "y")) for y in (1, 2, 3)]
    return {"cells": c, "cache": (1, 1, 1), "hook": ("mast", 0, 0), "kind": "vessel"}


def kit_house_broken(k):
    c = []
    for dx in range(-3, 4):
        for dz in range(-3, 4):
            c.append((dx, 0, dz, "minecraft:cobblestone" if (abs(dx) == 3 or abs(dz) == 3) else "minecraft:oak_planks"))
    for dx in range(-3, 4):
        for dz in range(-3, 4):
            if not (abs(dx) == 3 or abs(dz) == 3):
                continue
            corner = abs(dx) == 3 and abs(dz) == 3
            top = 3 if corner else 1 + h32(k, dx, dz, 7) % 3
            for y in range(1, top + 1):
                if dz == -3 and dx == 0 and y <= 2:
                    continue                                  # the doorway (the door is a fitting)
                if abs(dx) == 3 and dz == 0 and y == 2:
                    c.append((dx, y, dz, "minecraft:glass_pane[waterlogged=true]"))
                    continue
                c.append((dx, y, dz, log("spruce", "y") if corner else "minecraft:oak_planks"))
    for dx in (4, 5, 6):                                       # the roof, slid off onto the floor beside it
        for dz in range(-3, 4):
            if h32(k, dx, dz, 8) % 3:
                c.append((dx, 0, dz, stairs("spruce", "east")))
    c += [(2, y, 2, "minecraft:bricks") for y in (1, 2, 3)]   # the chimney stack
    # the door hangs open off its frame as two waterlogged trapdoors, and the bed is its mattress in wool: a door, a
    # bed, a fence gate or a cauldron holds no water, so a swimmer whose eyes reach its cell breathes there - a free
    # air pocket on the seabed, the ladder bypassed (tools/sea_life_audit.py, 2026-10-02)
    fit = [(0, 1, -3, "minecraft:oak_trapdoor[facing=east,half=bottom,open=true,powered=false,waterlogged=true]"),
           (0, 2, -3, "minecraft:oak_trapdoor[facing=east,half=top,open=true,powered=false,waterlogged=true]"),
           (-1, 1, 2, "minecraft:red_wool"),
           (-1, 1, 1, "minecraft:white_wool")]
    return {"cells": c, "pairs": fit, "cache": (1, 1, -1), "hook": ("chimney", 2, 2), "kind": "debris"}


def kit_rail_cart(k):
    c = [(0, 0, dz, "minecraft:polished_andesite") for dz in range(-5, 4)]
    c += [(0, 1, dz, "minecraft:powered_rail[shape=north_south,powered=false,waterlogged=true]")
          for dz in range(-5, 3) if dz != -1]
    c += [(1, 0, 3, "minecraft:iron_block"), (1, 0, 4, "minecraft:iron_trapdoor[facing=east,half=bottom,open=false,"
                                                     "powered=false,waterlogged=true]")]
    return {"cells": c, "cache": (-1, 0, 0), "hook": ("lantern", 0, 3), "kind": "debris"}


def kit_lamppost(k):
    c = [(0, 0, 0, "minecraft:stone_bricks")] + [(0, y, 0, fence("dark_oak")) for y in (1, 2, 3, 4)]
    c += [(0, 5, 0, LANTERN_WET)]
    return {"cells": c, "cache": (1, 0, 0), "hook": ("own", 0, 0), "kind": "debris"}


def kit_centre_sign(k):
    c = [(dx, y, 0, fence("dark_oak")) for dx in (-2, 2) for y in (0, 1)]
    for dx in range(-2, 3):
        for y in (2, 3, 4):
            if (dx, y) == (2, 4):
                continue                                      # a corner broken off
            c.append((dx, y, 0, "moarconcrete:white_concrete_texture" if y == 3 else "moarconcrete:red_concrete_texture"))
    return {"cells": c, "cache": (0, 0, -1), "hook": ("lantern", -2, 0), "kind": "debris"}


def kit_garden_gate_mailbox(k):
    c = []
    for dx in range(-3, 4):
        c.append((dx, 0, 0, fence("dark_oak")))       # the gate itself is gone: a fence gate holds no water
    c += [(2, 0, -2, fence("dark_oak")), (2, 1, -2, "minecraft:red_terracotta")]
    return {"cells": c, "cache": (-2, 0, -2), "hook": ("lantern", 2, -2), "kind": "debris"}


def kit_bench(k):
    c = [(dx, 0, 0, stairs("spruce", "south")) for dx in (-1, 0, 1)]
    c += [(-2, 0, 0, log("stripped_spruce", "y")), (2, 0, 0, log("stripped_spruce", "y"))]
    return {"cells": c, "cache": (0, 0, -2), "hook": ("lantern", -2, 0), "kind": "debris"}


def kit_bus_shelter(k):
    c = []
    for dx in (-2, 2):
        for dz in (-1, 1):
            c += [(dx, y, dz, "minecraft:andesite_wall[waterlogged=true]") for y in (0, 1)]
        c += [(dx, y, 0, "minecraft:iron_bars[waterlogged=true]") for y in (0, 1)]
    for dx in (-1, 0, 1):
        for y in (0, 1):
            if h32(k, dx, y, 9) % 4:
                c.append((dx, y, 1, "minecraft:glass_pane[waterlogged=true]"))
        c.append((dx, 0, 0, stairs("spruce", "north")))
    c += [(dx, 2, dz, "minecraft:smooth_stone") for dx in range(-2, 3) for dz in (-1, 0, 1)]
    c += [(2, 3, -1, "moarconcrete:yellow_concrete_texture")]   # data/spawn_block_policy.json substitutions: vanilla concrete spawns varoom
    return {"cells": c, "cache": (0, 0, -1), "hook": ("lantern", -2, -1), "kind": "debris"}


KITS = {"rowboat": kit_rowboat, "fishing_boat": kit_fishing_boat, "two_master_broken": kit_two_master_broken,
        "log_raft": kit_log_raft, "house_broken": kit_house_broken, "rail_cart": kit_rail_cart,
        "lamppost": kit_lamppost, "centre_sign": kit_centre_sign, "garden_gate_mailbox": kit_garden_gate_mailbox,
        "bench": kit_bench, "bus_shelter": kit_bus_shelter}


# ------------------------------------------------------------------ the exclusions (existing helpers)

class Exclusions:
    """Why a column may not hold anything this pack writes, from the helpers and data named in data/sea_life.json."""

    def __init__(self, spec, world, hm_path, N):
        ex = spec["exclusions"]
        self.N = N
        self.parts = []             # (name, x0, z0, x1, z1, mask or None), half-open
        wsd = world["heightmap"].get("water_shaped_from") or {}
        pre = Path(hm_path).parent / wsd.get("path", "")
        if not wsd or not pre.is_file():
            raise LifeError("the water export's input heightmap %s is not under the source root: the gate lines and "
                            "protect mask cannot be derived" % pre)
        if WS.sha256_file(pre) != wsd["sha256"]:
            raise LifeError("%s does not hash to the water_shaped_from sha256 data/world.json pins" % pre.name)
        raw = np.array(Image.open(pre))
        G0 = WS.ground_of_raw(raw, world)
        wspec = WS.load("water_shape.json")
        self.wspec = wspec
        ctx = WS.Ctx(world, wspec, raw, G0, pre)
        WS.build_protect(ctx)
        WS.build_lake_mask(ctx)
        self.protect_parts = dict(ctx.protect_parts)
        for c in wspec["crossings"]:
            if c["kind"] == "to_town":
                a, b = WS.to_town_endpoints(ctx, c, ctx.G0, "before")
            else:
                a, b = WS.crossing_endpoints(ctx, c, ctx.G0)
            ctx.crossing_lines[c["id"]] = (a, b)
        self.gate_lines = [[list(a), list(b)] for a, b in WS.gate_lines(ctx)]
        full = (0, 0, N, N)
        self.gate = WS.gate_mask(ctx, full, int(wspec["coasts"]["gate_line_clearance_blocks"]))
        self.P = ctx.P
        self.lake = ctx.lake_mask
        self.parts.append(("protect (towns, routes, bridges, the Rift, Victory Road, the islet, event sites)",
                           0, 0, N, N, self.P))
        self.parts.append(("a lake basin", 0, 0, N, N, self.lake))
        # docks and ferry lanes
        fe = json.loads((ROOT / "data" / "ferries.json").read_text(encoding="utf-8"))
        pts = {}
        for d in fe["docks"]:
            p = (d.get("landing") or {}).get("at")
            p = (p[0], p[2]) if p else (tuple(d["near"]) if d.get("near") else None)
            if p:
                pts[d["id"]] = p
                self.box("dock %s" % d["id"], p, ex["dock_margin_blocks"])
        fd = json.loads((ROOT / "data" / "ferry_docks.json").read_text(encoding="utf-8"))
        for d in fd["docks"]:
            for p in (d.get("near"), (d.get("shore") or {}).get("at")):
                if p:
                    self.box("dock %s" % d["id"], p, ex["dock_margin_blocks"] + int(d.get("length") or 0))
        lanes = []
        for ln in fe["lines"]:
            if ln.get("status") == "retired" or ln.get("retired_why"):
                continue
            stops = [pts[s] for s in ln["stops"] if s in pts]
            for a, b in zip(stops, stops[1:]):
                lanes.append([a, b])
        self.lanes = lanes
        lm = WS.raster_lines(lanes, full, 2 * ex["ferry_lane_half_width_blocks"] + 1)
        self.parts.append(("a ferry lane", 0, 0, N, N, lm))
        # portals, legendaries, adopted sites, placements
        for s in json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))["portals"]:
            self.box("portal %s" % s["id"], s["at"], ex["portal_margin_blocks"])
        for e in json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))["encounters"]:
            if e.get("spawn_free_zone"):
                x0, z0, x1, z1 = e["spawn_free_zone"]
                self.rect("legendary %s" % e["id"], x0, z0, x1, z1, ex["legendary_margin_blocks"])
            if e.get("mouth"):
                self.box("legendary %s" % e["id"], e["mouth"], ex["legendary_margin_blocks"])
        # every adopted site, scheduled or not, through tools/adopted_sites.py: reading `placement` alone dropped
        # each site once it was scheduled into data/placements.json (its block is deleted there)
        import adopted_sites
        for s in adopted_sites.sites():
            sz = s.get("size") or [48, 0, 48]
            half = int(max(sz[0], sz[-1]) if isinstance(sz, list) else 48) // 2 + 1
            self.box("adopted site %s" % s["id"], adopted_sites.centre(s), half + ex["legendary_margin_blocks"])
        for q in json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]:
            p = q.get("position")
            if isinstance(p, dict) and "x" in p and "z" in p:
                self.box("placement %s" % q["id"], (p["x"], p["z"]), ex["placement_margin_blocks"])
        # Pacifidlog
        town = WS.resited_town(ctx)
        xs = [c[0] for c in town["deck"]]
        zs = [c[1] for c in town["deck"]]
        self.rect("Pacifidlog (re-sited)", min(xs), min(zs), max(xs), max(zs), ex["pacifidlog_margin_blocks"])
        for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]:
            if t["id"] == "sea_town" and (t.get("footprint") or {}).get("min_x") is not None:
                fp = t["footprint"]
                self.rect("Pacifidlog (old footprint)", fp["min_x"], fp["min_z"], fp["max_x"], fp["max_z"],
                          ex["pacifidlog_margin_blocks"])
        # the First Cast hole and the Relic swim lines (water_shape's own masks)
        h = wspec["coasts"]["first_cast_hole"]
        r = int(h["radius"]) + 2 + ex["first_cast_hole_margin_blocks"]
        bx = WS.clip_box(h["centre"][0] - r, h["centre"][1] - r, h["centre"][0] + r + 1, h["centre"][1] + r + 1, N)
        hm = WS.grow(WS.hole_mask(wspec, bx), ex["first_cast_hole_margin_blocks"])
        self.parts.append(("the First Cast hole", bx[0], bx[1], bx[2], bx[3], hm))
        rc = wspec["coasts"]["relic_corridors"]
        xs = [p[0] for ln in rc["lines"] for p in ln]
        zs = [p[1] for ln in rc["lines"] for p in ln]
        hw = rc["half_width_blocks"] + 2
        bx = WS.clip_box(min(xs) - hw, min(zs) - hw, max(xs) + hw + 1, max(zs) + hw + 1, N)
        self.parts.append(("a Relic swim line", bx[0], bx[1], bx[2], bx[3], WS.relic_corridor_mask(ctx, bx)))
        # Driftmouth Isle and the Seaward Drift's cover
        sd = json.loads((ROOT / "data" / "sea_drift.json").read_text(encoding="utf-8"))
        isl = sd["island"]
        reach = max([isl["radius"] + isl["skirt"]] + [max(abs(st["x"] - isl["centre"]["x"]), abs(st["z"] - isl["centre"]["z"]))
                                                      + st["r"] for st in isl["stacks"]])
        self.box("Driftmouth Isle", (isl["centre"]["x"], isl["centre"]["z"]), reach + ex["drift_margin_blocks"])
        import sea_drift
        band = int(sd["tube"]["r"]) + sea_drift.cover_blocks(sd) + int(sd["shell_r"]) + ex["drift_margin_blocks"]
        dm = WS.raster_lines([sd["route"]["vertices"]], full, 2 * band + 1)
        self.parts.append(("the Seaward Drift's cover", 0, 0, N, N, dm))
        # the Deep
        rr = json.loads((ROOT / "data" / "rift_regions.json").read_text(encoding="utf-8"))
        x0, z0, x1, z1 = rr["regions"]["the_deep"]["bbox"]
        self.rect("the Deep", x0, z0, x1, z1, ex["deep_margin_blocks"])
        # the union, for fast rejection
        self.X = np.zeros((N, N), bool)
        for (_n, x0, z0, x1, z1, m) in self.parts:
            if m is None:
                self.X[z0:z1, x0:x1] = True
            else:
                self.X[z0:z1, x0:x1] |= m
        del raw, G0, ctx

    def box(self, name, p, m):
        x, z = int(p[0]), int(p[-1]) if len(p) == 2 else int(p[2])
        self.rect(name, x, z, x, z, m)

    def rect(self, name, x0, z0, x1, z1, m):
        b = WS.clip_box(min(x0, x1) - m, min(z0, z1) - m, max(x0, x1) + m + 1, max(z0, z1) + m + 1, self.N)
        if b[2] > b[0] and b[3] > b[1]:
            self.parts.append((name, b[0], b[1], b[2], b[3], None))

    def blocked(self, x0, z0, x1, z1):
        """The first exclusion over the inclusive rectangle, or None."""
        x0, z0, x1, z1 = max(0, x0), max(0, z0), min(self.N - 1, x1), min(self.N - 1, z1)
        if not self.X[z0:z1 + 1, x0:x1 + 1].any():
            return None
        for (name, a0, b0, a1, b1, m) in self.parts:
            c0, d0, c1, d1 = max(a0, x0), max(b0, z0), min(a1 - 1, x1), min(b1 - 1, z1)
            if c0 > c1 or d0 > d1:
                continue
            if m is None or m[d0 - b0:d1 - b0 + 1, c0 - a0:c1 - a0 + 1].any():
                return name
        return "an exclusion"

    def gated(self, x0, z0, x1, z1):
        return bool(self.gate[max(0, z0):z1 + 1, max(0, x0):x1 + 1].any())


# ------------------------------------------------------------------ the model

class Model:
    def __init__(self, spec, source_root=None):
        self.spec = spec
        self.g = G.load(source_root)
        self.world = self.g.world
        self.sea = int(WM.sea_level())
        self.H = np.round(self.g.heights).astype(np.int16)        # (z, x)
        self.N = self.H.shape[0]
        hm = T.resolve_heightmap(self.world, ROOT / "data" / "world.json", source_root)
        self.ex = Exclusions(spec, self.world, hm, self.N)
        self.wspec = self.ex.wspec
        self.writes = {}                    # (x, y, z) -> (block, pass, owner)
        self.order = {p: [] for p in PASSES}   # fittings keep insertion order (doors and beds in pairs)
        self.features = {}                  # owner -> record
        self.reserved = np.zeros((self.N, self.N), bool)
        self.problems = []
        self.notes = {}
        self.top_gap = int(spec["exclusions"]["top_gap_blocks"])

    def gy(self, x, z):
        return int(self.H[z, x])

    def wet(self, x, z):
        return 0 <= x < self.N and 0 <= z < self.N and self.H[z, x] < self.sea and not self.ex.lake[z, x]

    def put(self, x, y, z, b, pas, owner):
        k = (x, y, z)
        if k in self.writes and self.writes[k][2] != owner:
            self.problems.append("%s and %s both write (%d, %d, %d)" % (self.writes[k][2], owner, x, y, z))
            return False
        if k not in self.writes or self.writes[k][1] != pas:
            self.order[pas].append(k)
        self.writes[k] = (b, pas, owner)
        return True

    def reserve(self, cols, grow=4):
        for (x, z) in cols:
            self.reserved[max(0, z - grow):z + grow + 1, max(0, x - grow):x + grow + 1] = True

    def rock(self, x, y, z, salt=21):
        pal = self.spec["palette"]
        return pick(pal["rock_upper"] if y >= pal["rock_split_y"] else pal["rock_lower"], self.spec["seed"], x, y, z, salt)

    def hull(self, x, y, z):
        return pick(self.spec["palette"]["hull"], self.spec["seed"], x, y, z, 23)


# ------------------------------------------------------------------ voxel caves (shared by both caves)

class Vox:
    def __init__(self, m, x0, z0, x1, z1, y0, y1):
        self.m = m
        self.X0, self.Z0, self.Y0 = x0, z0, y0
        self.nx, self.nz, self.ny = x1 - x0 + 1, z1 - z0 + 1, y1 - y0 + 1
        if x0 < 0 or z0 < 0 or x1 >= m.N or z1 >= m.N:
            raise LifeError("cave box (%d, %d)-(%d, %d) leaves the map" % (x0, z0, x1, z1))
        self.G = m.H[z0:z1 + 1, x0:x1 + 1].T.astype(np.int32)         # (x, z)
        shape = (self.nx, self.nz, self.ny)
        self.water = np.zeros(shape, bool)
        self.air = np.zeros(shape, bool)
        self.mouth = np.zeros(shape, bool)
        self.solid_fit = set()

    def ix(self, x, y, z):
        return x - self.X0, z - self.Z0, y - self.Y0

    def inside(self, x, y, z):
        i, k, j = self.ix(x, y, z)
        return 0 <= i < self.nx and 0 <= k < self.nz and 0 <= j < self.ny

    def Gat(self, x, z):
        return int(self.G[x - self.X0, z - self.Z0])

    def open(self, xa, xb, za, zb, ya, yb, kind, mouth=False):
        a, b = self.ix(min(xa, xb), min(ya, yb), min(za, zb)), self.ix(max(xa, xb), max(ya, yb), max(za, zb))
        if min(a) < 0 or b[0] >= self.nx or b[1] >= self.nz or b[2] >= self.ny:
            raise LifeError("opening (%d..%d, %d..%d, %d..%d) leaves the cave's box" % (xa, xb, ya, yb, za, zb))
        sl = (slice(a[0], b[0] + 1), slice(a[1], b[1] + 1), slice(a[2], b[2] + 1))
        (self.water if kind == "water" else self.air)[sl] = True
        if mouth:
            self.mouth[sl] = True

    def void(self):
        return self.water | self.air

    def under(self):
        ys = np.arange(self.Y0, self.Y0 + self.ny)[None, None, :]
        return ys <= self.G[:, :, None]


def path_cells(vertices):
    """[(x, z, (dx, dz))] one per column along straight legs, and the corner indices (tools/sea_drift.py's)."""
    cells, corners = [], []
    for k, ((x0, z0), (x1, z1)) in enumerate(zip(vertices, vertices[1:])):
        if x0 != x1 and z0 != z1:
            raise LifeError("route leg %d is not straight along x or z" % k)
        n = max(abs(x1 - x0), abs(z1 - z0))
        d = ((x1 > x0) - (x1 < x0), (z1 > z0) - (z1 < z0))
        if k:
            corners.append(len(cells))
        for i in range(n):
            cells.append((x0 + d[0] * i, z0 + d[1] * i, d))
    x1, z1 = vertices[-1]
    cells.append((x1, z1, cells[-1][2]))
    return cells, corners


def section(x, z, d, r, square):
    if square:
        return x - r, x + r, z - r, z + r
    if d[1] == 0:
        return x, x, z - r, z + r
    return x - r, x + r, z, z


def cover_problems(v, C, label):
    """Every void cell outside the mouth must have C solid blocks between it and the outside in every direction
    (Chebyshev): its y at most the least ground within C round it, minus C (tools/sea_drift.py's rule)."""
    mg = running_min2d(v.G, C)
    vd = v.void() & ~v.mouth
    out = []
    if not vd.any():
        return ["%s: nothing opened" % label], None
    anyv = vd.any(axis=2)
    top = np.where(anyv, v.Y0 + v.ny - 1 - np.argmax(vd[:, :, ::-1], axis=2), -999)
    gap = np.where(anyv, mg - top, 10 ** 6)
    least = int(gap.min())
    if least < C:
        i, k = np.unravel_index(int(np.argmin(gap)), gap.shape)
        out.append("%s: %d solid blocks over the opening at (%d, %d), under the %d required" % (label, least, i + v.X0,
                                                                                               k + v.Z0, C))
    return out, least


def shell_cells(v, SR, skip=()):
    sh = dilate3(v.void(), SR) & ~v.void() & v.under()
    for (x, y, z) in skip:
        if v.inside(x, y, z):
            sh[v.ix(x, y, z)] = False
    return sh


def standable(v):
    """{(x, y, z)} dry cells a player can stand in: air void, not a fitting, solid under, air over."""
    out = set()
    for i, k, j in np.argwhere(v.air):
        x, z, y = int(i + v.X0), int(k + v.Z0), int(j + v.Y0)
        if (x, y, z) in v.solid_fit or j == 0 or j + 1 >= v.ny:
            continue
        below_void = v.water[i, k, j - 1] or v.air[i, k, j - 1]
        below_solid = (not below_void and (y - 1) <= v.G[i, k]) or (x, y - 1, z) in v.solid_fit
        above_air = (v.air[i, k, j + 1] or (y + 1) > v.G[i, k]) and (x, y + 1, z) not in v.solid_fit
        if below_solid and above_air:
            out.add((x, y, z))
    return out


def walk(v, cells, starts):
    """The cells reachable on foot from `starts`: a step of at most one block up or down, with headroom."""
    seen = set(s for s in starts if s in cells)
    todo = list(seen)
    while todo:
        x, y, z = todo.pop()
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1):
                q = (x + a, y + dy, z + b)
                if q in cells and q not in seen:
                    if dy == 1 and not (v.inside(x, y + 2, z) and (v.air[v.ix(x, y + 2, z)] or y + 2 > v.Gat(x, z))):
                        continue
                    seen.add(q)
                    todo.append(q)
    return seen


def write_vox(m, v, owner, sh, crack=()):
    """The cave's passes: rock shell, then the opened cells under the ground (air or water)."""
    for i, k, j in np.argwhere(sh):
        x, z, y = int(i + v.X0), int(k + v.Z0), int(j + v.Y0)
        m.put(x, y, z, m.rock(x, y, z), "shell", owner)
    for arr, blk in ((v.water, WATER), (v.air, AIR)):
        hit = arr & v.under()
        for i, k, j in np.argwhere(hit):
            x, z, y = int(i + v.X0), int(k + v.Z0), int(j + v.Y0)
            m.put(x, y, z, blk, "carve", owner)
    cols = set()
    for i, k in np.argwhere((sh | v.void()).any(axis=2)):
        cols.add((int(i + v.X0), int(k + v.Z0)))
    return cols


# ------------------------------------------------------------------ the surfacing cave

def air_budget(spec):
    """(blocks a Surf player swims before the knockout, the parts) from data/blackout.json, read now."""
    w = json.loads(BLACKOUT.read_text(encoding="utf-8"))["water"]
    a = spec["surfacing_cave"]["air"]
    ticks = int(w["surf_bonus_ticks"]) + int(a["vanilla_air_ticks"]) + int(w["pulse_ticks"])
    return ticks / 20.0 * float(a["surf_swim_blocks_per_second"]), {
        "surf_bonus_ticks": int(w["surf_bonus_ticks"]), "vanilla_air_ticks": int(a["vanilla_air_ticks"]),
        "pulse_ticks": int(w["pulse_ticks"]), "ticks_to_knockout": ticks,
        "surf_blocks_per_second": a["surf_swim_blocks_per_second"]}


def surfacing_cave(m):
    spec = m.spec["surfacing_cave"]
    sea, owner = m.sea, "sea_life_" + spec["id"]
    r, H = int(spec["tube"]["r"]), int(spec["tube"]["height"])
    SR = int(spec["shell"])
    C = SR + int(spec["export_tolerance"]) + int(spec["natural_seabed"])
    L = int(spec["pool_level"])
    cells, corners = path_cells(spec["route"])
    pts = [(c[0], c[1]) for c in cells]
    for gal in spec["galleries"]:
        pts += [tuple(p) for p in gal["path"]]
    ch = spec["chamber"]
    pts += [(ch["centre"][0] - ch["half_x"], ch["centre"][1] - ch["half_z"]),
            (ch["centre"][0] + ch["half_x"], ch["centre"][1] + ch["half_z"])]
    pad = C + SR + 20
    v = Vox(m, min(p[0] for p in pts) - pad, min(p[1] for p in pts) - pad, max(p[0] for p in pts) + pad,
            max(p[1] for p in pts) + pad, 2, 120)
    rec = {"id": owner, "category": "surfacing_cave", "display_name": spec["display_name"], "cover_required": C}
    mx, mz = spec["mouth"]
    if (mx, mz) != tuple(spec["route"][0]):
        raise LifeError("the surfacing cave's mouth is not its route's first vertex")
    g0 = v.Gat(mx, mz)
    rec["mouth"] = [mx, mz]
    rec["mouth_ground_y"] = g0
    rec["mouth_depth"] = sea - g0
    # the profile: the largest 1-Lipschitz bottom under the cover cap and the riser's start, joined to the mouth
    mgr = running_min2d(v.G, r + C)
    end_target = L - int(spec["end_depth_under_pool"])
    cap = [int(mgr[x - v.X0, z - v.Z0]) - C - (H - 1) for x, z, _d in cells]
    capp = [min(c, end_target) for c in cap]
    n = len(cells)
    F = [min(capp[t] + abs(s - t) for t in range(max(0, s - 400), min(n, s + 401))) for s in range(n)]
    y0 = g0 + 1
    Y = [max(F[s], y0 - s) for s in range(n)]
    mouth_n = 0
    while mouth_n < n and Y[mouth_n] > cap[mouth_n]:
        mouth_n += 1
    if any(Y[s] > cap[s] for s in range(mouth_n, n)):
        m.problems.append("surfacing cave: the passage breaks its cover after the mouth")
    rec["mouth_cells"] = mouth_n
    square = set(corners) | {n - 1}
    for s, (x, z, d) in enumerate(cells):
        xa, xb, za, zb = section(x, z, d, r, s in square)
        v.open(xa, xb, za, zb, Y[s], Y[s] + H - 1, "water", mouth=s < mouth_n)
    ex, ez, _ = cells[-1]
    v.open(ex - r, ex + r, ez - r, ez + r, Y[-1], L, "water")              # the riser, its top the pool
    cx, cz = ch["centre"]
    v.open(cx - ch["half_x"], cx + ch["half_x"], cz - ch["half_z"], cz + ch["half_z"], L + 1, L + ch["height"], "air")
    feet = L + 1
    rec["galleries"] = {}
    crack = []
    for gal in spec["galleries"]:
        gc, gco = path_cells(gal["path"])
        gr, gh = int(gal["r"]), int(gal["height"])
        keep = len(gc)
        if gal.get("trim_to_cover"):
            for s, (x, z, d) in enumerate(gc):
                if feet + gh - 1 > int(mgr[x - v.X0, z - v.Z0]) - C + (r - gr):
                    keep = s
                    break
            gc = gc[:keep]
        if len(gc) < 4:
            m.problems.append("surfacing cave: gallery %s keeps %d cells under its cover" % (gal["id"], len(gc)))
            continue
        sq = set(gco) | {len(gc) - 1}
        for s, (x, z, d) in enumerate(gc):
            xa, xb, za, zb = section(x, z, d, gr, s in sq)
            v.open(xa, xb, za, zb, feet, feet + gh - 1, "air")
        x, z, d = gc[-1]
        rec["galleries"][gal["id"]] = {"cells": len(gc), "end": [x, z]}
        if gal["end"] == "cache":
            v.open(x - 2, x + 2, z - 2, z + 2, feet, feet + gh - 1, "air")
            rec["barrel"] = (x + d[0] * 2, feet, z + d[1] * 2)
        elif gal["end"] == "crack":
            ck = spec["crack"]
            done = False
            for k in range(int(ck["max_length"])):
                px, pz = x + d[0] * (gr + 1 + k), z + d[1] * (gr + 1 + k)
                ylo = feet + k * int(ck["rise_per_block"])
                ys = [ylo + t for t in range(int(ck["height"]))]
                gpx = v.Gat(px, pz)
                if all(yy > gpx for yy in ys):
                    done = True
                    break
                crack += [(px, yy, pz) for yy in ys if yy <= gpx]
            if not done:
                m.problems.append("surfacing cave: the crack does not reach open air within %d blocks" % ck["max_length"])
            rec["crack"] = {"cells": len(crack), "from": [x, z], "dir": list(d)}
    v.solid_fit.add(rec.get("barrel", (0, 0, 0)))
    # checks
    probs, least = cover_problems(v, C, "surfacing cave")
    m.problems += probs
    rec["cover_min_measured"] = least
    if mouth_n > int(spec["max_mouth_cells"]):
        m.problems.append("surfacing cave: the mouth is %d cells long, over %d" % (mouth_n, spec["max_mouth_cells"]))
    if mouth_n == 0:
        m.problems.append("surfacing cave: no mouth (the passage never meets the sea)")
    if not (20 <= sea - g0 <= 40):
        m.problems.append("surfacing cave: the mouth is %d deep, not 20-40" % (sea - g0))
    # the pool: water meets air only from below, at the pool level
    wa = v.water
    ai = v.air
    bad = int((wa[:, :, :-1] & ai[:, :, 1:] & (np.arange(v.ny - 1)[None, None, :] + v.Y0 != L)).sum())
    bad += int((ai[:, :, :-1] & wa[:, :, 1:]).sum())                       # water over air
    for axis in (0, 1):
        sa = [slice(None)] * 3
        sb = [slice(None)] * 3
        sa[axis], sb[axis] = slice(1, None), slice(None, -1)
        bad += int((wa[tuple(sa)] & ai[tuple(sb)]).sum() + (ai[tuple(sa)] & wa[tuple(sb)]).sum())
    if bad:
        m.problems.append("surfacing cave: %d places where the water would flow into the air (the pool is not flat)" % bad)
    surf = wa[:, :, L - v.Y0] & ai[:, :, L + 1 - v.Y0]
    rec["pool_cells"] = int(surf.sum())
    if not surf.any():
        m.problems.append("surfacing cave: no pool surface")
    # the air is reached only through the pool: no air cell is in the mouth, and air has its cover everywhere
    if (ai & v.mouth).any():
        m.problems.append("surfacing cave: air in the mouth")
    # walk-out: every dry floor cell from the pool's edge
    st = standable(v)
    pool_cols = {(int(i + v.X0), int(k + v.Z0)) for i, k in np.argwhere(surf)}
    starts = [c for c in st if c[1] == L + 1 and any((c[0] + a, c[2] + b) in pool_cols
                                                       for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    reach = walk(v, st, starts)
    rec["floor_cells"] = len(st)
    rec["floor_unreached"] = len(st) - len(reach)
    if not starts:
        m.problems.append("surfacing cave: no dry floor beside the pool")
    if len(reach) != len(st):
        m.problems.append("surfacing cave: %d dry floor cells cannot be walked to from the pool" % (len(st) - len(reach)))
    if "barrel" in rec and not any(abs(c[0] - rec["barrel"][0]) + abs(c[2] - rec["barrel"][2]) == 1
                                   and c[1] == rec["barrel"][1] for c in reach):
        m.problems.append("surfacing cave: the barrel cannot be walked to")
    # the air ladder: down to the mouth, along the centre line, up the riser
    descent = sea - (Y[0] + 1)
    along = 0.0
    for s in range(1, n):
        a, b = cells[s - 1], cells[s]
        along += math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (Y[s] - Y[s - 1]) ** 2)
    riser = L - (Y[-1] + 1)
    length = descent + along + riser
    budget, parts = air_budget(m.spec)
    rec["underwater_length"] = round(length, 1)
    rec["underwater_parts"] = {"descent": descent, "passage": round(along, 1), "riser": riser}
    rec["surf_knockout_distance"] = round(budget, 1)
    rec["surf_air"] = parts
    rec["dive_seconds"] = round(length / float(m.spec["surfacing_cave"]["air"]["dive_swim_blocks_per_second"]), 1)
    if length <= budget:
        m.problems.append("surfacing cave: the underwater length %.0f is within a Surf player's %.0f" % (length, budget))
    rec["passage"] = {"cells": n, "lowest_bottom": min(Y), "end_bottom": Y[-1], "under_sea_cells":
                      sum(1 for x, z, _d in cells if v.Gat(x, z) < sea)}
    # the blocks
    sh = shell_cells(v, SR, skip=crack)
    unsealed = 0
    for (x, y, z) in crack:
        if not any(not v.inside(x + a, y + b, z + c) or (y + b) > v.Gat(x + a, z + c)
                   for a, b, c in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1))):
            continue
        unsealed += 1
    if crack and not unsealed:
        m.problems.append("surfacing cave: no crack cell meets the open air")
    rec["crack_cells_at_the_surface"] = unsealed
    cols = write_vox(m, v, owner, sh)
    rec["shell_cells"] = int(sh.sum())
    for (x, y, z) in crack:
        m.put(x, y, z, spec["crack"]["block"], "fittings", owner)
    if "barrel" in rec:
        m.put(*rec["barrel"], BARREL, "fittings", owner)
    m.put(cx, L + ch["height"], cz, LANTERN_HANG, "fittings", owner)
    for gal in spec["galleries"]:
        gc, _ = path_cells(gal["path"])
        for s, (x, z, d) in enumerate(gc):
            if s and s % int(spec["lantern_every"]) == 0 and v.inside(x, feet + gal["height"] - 1, z) \
                    and v.air[v.ix(x, feet + gal["height"] - 1, z)] and (x, feet + gal["height"] - 1, z) not in v.solid_fit:
                m.put(x, feet + gal["height"] - 1, z, LANTERN_HANG, "fittings", owner)
    # the mouth's lantern on a post on the seabed, beside the mouth
    d0 = cells[0][2]
    off = int(spec["mouth_lantern_offset"])
    lx, lz = mx - d0[1] * off, mz + d0[0] * off
    lg = m.gy(lx, lz)
    m.put(lx, lg + 1, lz, "minecraft:cobblestone_wall[waterlogged=true]", "build", owner)
    m.put(lx, lg + 2, lz, LANTERN_WET, "fittings", owner)
    rec["mouth_lantern"] = [lx, lg + 2, lz]
    cols |= {(lx, lz)}
    rec["columns"] = len(cols)
    bl = set()
    for (x, z) in cols:
        b = m.ex.blocked(x, z, x, z)
        if b:
            bl.add(b)
    if bl:
        m.problems.append("surfacing cave: inside %s" % sorted(bl))
    m.reserve(cols, 8)
    rec["passage_profile"] = [{"s": s, "x": cells[s][0], "z": cells[s][1], "bottom": Y[s], "ground": v.Gat(cells[s][0], cells[s][1])}
                              for s in list(range(0, n, 40)) + [n - 1]]
    m.features[owner] = rec
    m.cave_vox = v


# ------------------------------------------------------------------ the waterline sea cave

def sea_cave(m):
    spec = m.spec["shore"]["sea_cave"]
    sea, owner = m.sea, "sea_life_sea_cave"
    boxes = {s["id"]: s["box"] for s in m.wspec["coasts"]["skerries"]}
    x0, z0, x1, z1 = boxes[spec["coast_box"]]
    Gb = m.H[z0:z1, x0:x1].astype(np.int32)
    land = Gb >= sea
    wet = (Gb < sea) & ~m.ex.lake[z0:z1, x0:x1]
    tide = land & (Gb <= sea + 1) & WS.dilate4(wet)
    mx12 = WS.running_max2d(Gb, 12)
    share = WS.box_mean(land.astype(float), int(spec["mainland_radius_blocks"]))
    zs, xs = np.nonzero(tide & (share >= float(spec["mainland_share_min"])) & (mx12 - Gb >= int(spec["min_rise_in_12"])))
    rise = (mx12 - Gb)[zs, xs]
    order = np.lexsort((h32_arr(xs + x0, zs + z0, m.spec["seed"]), -rise))
    sc = m.features.get("sea_life_" + m.spec["surfacing_cave"]["id"], {}).get("mouth")
    tried = 0
    for i in order:
        x, z = int(xs[i] + x0), int(zs[i] + z0)
        if sc and math.hypot(x - sc[0], z - sc[1]) < float(spec["clear_of_surfacing_cave_blocks"]):
            continue
        heads = sorted(FACINGS, key=lambda f: -m.gy(x + STEP[f][0] * 12, z + STEP[f][1] * 12))
        for f in heads[:1]:
            tried += 1
            res = try_sea_cave(m, spec, x, z, f)
            if res is not None:
                res["candidates_tried"] = tried
                res["rise_in_12"] = int(rise[i])
                v, sh, rec = res["vox"], res["sh"], res["rec"]
                cols = write_vox(m, v, owner, sh)
                for (cx_, cz_) in res["clear"]:               # trees over the cleft and beside it
                    gg = m.gy(cx_, cz_)
                    for y in range(gg + 1, gg + 11):
                        if (cx_, y, cz_) not in m.writes:
                            m.put(cx_, y, cz_, AIR, "carve", owner)
                m.put(*rec["barrel"], BARREL, "fittings", owner)
                m.put(*rec["lantern"], LANTERN_HANG, "fittings", owner)
                for at in rec["passage_lanterns"]:
                    m.put(*at, LANTERN_HANG, "fittings", owner)
                rec["candidates_tried"] = tried
                rec["rise_in_12"] = int(rise[i])
                rec["columns"] = len(cols)
                m.reserve(cols, 6)
                m.features[owner] = rec
                return
        if tried >= 400:
            break
    m.problems.append("sea cave: no site on the windward coast passes (%d tried)" % tried)


def h32_arr(xs, zs, seed):
    return np.array([h32(seed, int(a), int(b), 61) for a, b in zip(xs, zs)], dtype=np.int64)


def try_sea_cave(m, spec, x, z, f):
    sea = m.sea
    d = STEP[f]
    r, H = int(spec["r"]), int(spec["height"])
    SR = int(spec["shell"])
    C = SR + int(spec["export_tolerance"])
    n = int(spec["length"])
    ch = spec["chamber"]
    g0 = m.gy(x, z)
    if not (sea <= g0 <= sea + 1) or not any(m.wet(x + a, z + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
        return None
    ds = spec["descent"]
    fmin = sea - int(ds["floor_below_sea"])

    def feet_at(s):
        drop = 0 if s < int(ds["start_cells"]) else (s - int(ds["start_cells"])) // int(ds["run"]) + 1
        return max(fmin, g0 + 1 - drop)
    pad = C + SR + ch["half"] + 4
    ex, ez = x + d[0] * (n - 1), z + d[1] * (n - 1)
    v = Vox(m, min(x, ex) - pad, min(z, ez) - pad, max(x, ex) + pad, max(z, ez) + pad, fmin - 12, g0 + 50)
    mgr = running_min2d(v.G, r + C)
    s_p = None
    for s in range(n):
        cx_, cz_ = x + d[0] * s, z + d[1] * s
        roofed = feet_at(s) + H - 1 <= int(mgr[cx_ - v.X0, cz_ - v.Z0]) - C
        if roofed and s_p is None:
            s_p = s
        if not roofed and s_p is not None:
            return None
    if s_p is None or s_p > n - 8:
        return None
    clear = set()
    for s in range(n):
        cx_, cz_ = x + d[0] * s, z + d[1] * s
        xa, xb, za, zb = section(cx_, cz_, d, r, False)
        fs_ = feet_at(s)
        if s < s_p:
            top = max(v.Gat(a, b) for a in range(xa, xb + 1) for b in range(za, zb + 1))
            v.open(xa, xb, za, zb, fs_, max(top, fs_ + H - 1), "air", mouth=True)
            for a in range(xa - 1, xb + 2):
                for b in range(za - 1, zb + 2):
                    clear.add((a, b))
        else:
            v.open(xa, xb, za, zb, fs_, fs_ + H - 1, "air")
    hc = int(ch["half"])
    feet = feet_at(n - 1)
    v.open(ex - hc, ex + hc, ez - hc, ez + hc, feet, feet + int(ch["height"]) - 1, "air")
    rec = {"id": "sea_life_sea_cave", "category": "sea_cave", "mouth": [x, z], "mouth_ground_y": g0, "heading": f,
           "mouth_feet_y": g0 + 1, "floor_y": feet, "open_cut_cells": s_p, "length": n, "cover_required": C}
    barrel = (ex + d[0] * hc, feet, ez + d[1] * hc)
    v.solid_fit.add(barrel)
    rec["barrel"] = barrel
    rec["lantern"] = (ex, feet + int(ch["height"]) - 1, ez)
    # hanging lanterns down the roofed passage, every 8 cells, so no floor cell between the mouth's daylight and the
    # chamber's lantern is dark (tools/sea_life_audit.py found 23 roofed cells at block light 0, 2026-10-02)
    rec["passage_lanterns"] = [(x + d[0] * s, feet_at(s) + H - 1, z + d[1] * s)
                               for s in range(s_p + 4, n - hc - 2, 8)]
    probs, least = cover_problems(v, C, "sea cave")
    if probs:
        return None
    rec["cover_min_measured"] = least
    # no opened cell at or under the sea level has sea water within water_clearance (Chebyshev)
    wc = int(ds["water_clearance"])
    wetc = (v.G < sea)
    near = None
    for i, k, j in np.argwhere(v.void() & (np.arange(v.ny)[None, None, :] + v.Y0 <= sea)):
        y = int(j + v.Y0)
        sub = v.G[max(0, i - wc):i + wc + 1, max(0, k - wc):k + wc + 1]
        wsub = wetc[max(0, i - wc):i + wc + 1, max(0, k - wc):k + wc + 1]
        if (wsub & (sub + 1 <= y + wc) & (sea >= y - wc)).any():
            near = (int(i + v.X0), y, int(k + v.Z0))
            break
    if near is not None:
        return None
    rec["water_clearance"] = wc
    st = standable(v)
    reach = walk(v, st, [(x, g0 + 1, z)])
    rec["floor_cells"], rec["floor_unreached"] = len(st), len(st) - len(reach)
    if len(reach) != len(st) or (x, g0 + 1, z) not in st:
        return None
    if not any(abs(c[0] - barrel[0]) + abs(c[2] - barrel[2]) == 1 and c[1] == feet for c in reach):
        return None
    sh = shell_cells(v, SR)
    cols = {(int(i + v.X0), int(k + v.Z0)) for i, k in np.argwhere((sh | v.void()).any(axis=2))} | clear
    for (a, b) in cols:
        if m.ex.blocked(a, b, a, b) or m.reserved[b, a]:
            return None
    if (v.mouth & v.air).sum() == 0:
        return None
    rec["shell_cells"] = int(sh.sum())
    rec["mouth_seaward"] = [x - d[0], z - d[1]]
    return {"vox": v, "sh": sh, "rec": rec, "clear": sorted(clear)}


# ------------------------------------------------------------------ kits placed in the world

def place_kit(m, name, k, steps, cx, cz):
    """(cells in world coordinates [(x, dy, z, block)], cache (x, dy, z), hook (kind, x, z), pairs, footprint)."""
    kit = KITS[name](k)
    cells = []
    for (dx, dy, dz, b) in kit["cells"]:
        rx, rz = rot_xz(dx, dz, steps)
        cells.append((cx + rx, dy, cz + rz, rot_block(b, steps)))
    pairs = []
    for (dx, dy, dz, b) in kit.get("pairs", []):
        rx, rz = rot_xz(dx, dz, steps)
        pairs.append((cx + rx, dy, cz + rz, rot_block(b, steps)))
    c = kit["cache"]
    rx, rz = rot_xz(c[0], c[2], steps)
    cache = (cx + rx, c[1], cz + rz)
    hk = kit["hook"]
    hx, hz = rot_xz(hk[1], hk[2], steps)
    foot = {(a, b) for a, _y, b, _bl in cells + pairs} | {(cache[0], cache[2])}
    return cells, cache, (hk[0], cx + hx, cz + hz), pairs, foot, kit["kind"]


def fit_find(m, name, k, steps, cx, cz, band_rng, with_hook):
    """A seated, flooded find at (cx, cz), or (None, why)."""
    fs = m.spec["finds"]
    cells, cache, hook, pairs, foot, kind = place_kit(m, name, k, steps, cx, cz)
    xs = [p[0] for p in foot]
    zs = [p[1] for p in foot]
    if min(xs) < 1 or min(zs) < 1 or max(xs) >= m.N - 1 or max(zs) >= m.N - 1:
        return None, "map edge"
    gs = [m.gy(a, b) for (a, b) in foot]
    if not all(m.wet(a, b) for (a, b) in foot):
        return None, "not all sea"
    lo, hi = min(gs), max(gs)
    if hi - lo > int(fs["max_relief"]):
        return None, "relief"
    depth = m.sea - lo
    if not (band_rng[0] <= depth <= band_rng[1]):
        return None, "band"
    base = lo + 1
    b = m.ex.blocked(min(xs) - 2, min(zs) - 2, max(xs) + 2, max(zs) + 2)
    if b:
        return None, b
    if m.reserved[min(zs) - 2:max(zs) + 3, min(xs) - 2:max(xs) + 3].any():
        return None, "reserved"
    world = {}
    for (x, dy, z, bl) in cells:
        world[(x, base + dy, z)] = bl
    world[(cache[0], base + cache[1], cache[2])] = None          # decided after (barrel or water)
    top_ok = m.sea - m.top_gap
    hook_rec = None
    if with_hook:
        kindh, hx, hz = hook
        col = [y for (x, y, z), bl in world.items() if x == hx and z == hz and bl]
        top = max(col) if col else base - 1
        if kindh in ("mast", "chimney"):
            blk = log("spruce", "y") if kindh == "mast" else "minecraft:bricks"
            want = min(base + int(fs["hooks"]["mast_max_above_base"]), top_ok)
            for y in range(top + 1, want + 1):
                world[(hx, y, hz)] = blk
            hook_rec = {"kind": kindh, "top": max(want, top), "below_surface": m.sea - max(want, top)}
        elif kindh == "lantern":
            under = world.get((hx, top, hz)) if col else None
            if under is None or (any(t in bid(under) for t in NOT_FULL) and not bid(under).endswith(("_fence", "_wall"))):
                return None, "no full block under the hook lantern"
            world[(hx, top + 1, hz)] = LANTERN_WET
            hook_rec = {"kind": "lantern", "top": top + 1, "below_surface": m.sea - (top + 1)}
        else:
            hook_rec = {"kind": "lantern (its own)", "top": top, "below_surface": m.sea - top}
    for (x, dy, z, bl) in pairs:
        world[(x, base + dy, z)] = bl
    ytop = max(y for (_x, y, _z) in world)
    if ytop > top_ok:
        return None, "top %d over sea - %d" % (ytop, m.top_gap)
    for (x, y, z) in world:
        if (x, y, z) in m.writes:
            return None, "overlap"
    return {"cells": world, "pairs": pairs, "base": base, "depth": depth, "relief": hi - lo, "foot": foot,
            "cache": (cache[0], base + cache[1], cache[2]), "hook": hook_rec, "kind": kind, "top": ytop}, None


def commit_find(m, fid, rec, name, steps, cx, cz, region, band, line=None):
    pair_cells = {(x, rec["base"] + dy, z) for (x, dy, z, _b) in rec["pairs"]}
    for (x, y, z), bl in rec["cells"].items():
        if bl is None or (x, y, z) in pair_cells:
            continue
        b = m.hull(x, y, z) if bl == "HULL" else bl
        pas = "fittings" if "lantern" in b else "build"
        m.put(x, y, z, b, pas, fid)
    for (x, dy, z, b) in rec["pairs"]:
        m.put(x, rec["base"] + dy, z, b, "fittings", fid)
    m.reserve(rec["foot"], 2)
    m.features[fid] = {"id": fid, "category": "find_" + rec["kind"], "kit": name, "facing": FACINGS[steps % 4],
                       "centre": [cx, cz], "base_y": rec["base"], "depth": rec["depth"], "band": band,
                       "region": region, "relief": rec["relief"], "top_y": rec["top"], "hook": rec["hook"],
                       "cache_cell": list(rec["cache"]), "line": line, "has_cache": False,
                       "lowest_ground": rec["base"] - 1}


def region_of(m, x, z):
    if not hasattr(m, "_marine"):
        doc = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
        polys = {r["id"]: r.get("polygons") or [] for r in doc["marine_regions"]}
        m._marine = [(rid, polys[rid]) for rid in m.spec["finds"]["region_order"]]
    for rid, p in m._marine:
        if p and WM.in_polygons(p, x, z):
            return rid
    return None


def rift_centre():
    doc = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    r = next(q for q in doc["regions"] if q["id"] == "the_rift")
    A = cx = cz = 0.0
    for ring in r["polygons"]:
        for (x0, z0), (x1, z1) in zip(ring, ring[1:] + ring[:1]):
            c = x0 * z1 - x1 * z0
            A += c
            cx += (x0 + x1) * c
            cz += (z0 + z1) * c
    A *= 0.5
    return cx / (6 * A), cz / (6 * A)


def band_of(fs, depth):
    for b, v in fs["bands"].items():
        if v["depth"][0] <= depth <= v["depth"][1]:
            return b
    return None


def finds(m):
    fs = m.spec["finds"]
    seed = m.spec["seed"]
    sp = float(fs["min_spacing_blocks"])
    placed = []                       # (x, z)
    rc = rift_centre()
    m.notes["rift_centre"] = [round(rc[0], 1), round(rc[1], 1)]

    def far(x, z, gap):
        return all((x - a) ** 2 + (z - b) ** 2 >= gap * gap for a, b in placed)

    all_bands = [min(v["depth"][0] for v in fs["bands"].values()), max(v["depth"][1] for v in fs["bands"].values())]
    # the debris lines
    lsp = fs["debris_line_spacing_blocks"]
    for ln in fs["debris_lines"]:
        br = math.radians(ln["bearing_deg"])
        dx, dz = math.sin(br), -math.cos(br)
        px, pz = -dz, dx
        t, n, started, k = 0.0, 0, False, 0
        while n < int(ln["count"]):
            t += 8.0 if not started else 0.0
            x, z = int(round(rc[0] + dx * t)), int(round(rc[1] + dz * t))
            if not (8 <= x < m.N - 8 and 8 <= z < m.N - 8):
                break
            if not started:
                if m.wet(x, z) and m.sea - m.gy(x, z) >= int(fs["debris_line_min_depth"]):
                    started = True
                    m.notes.setdefault("debris_line_start", {})[ln["id"]] = [x, z]
                continue
            j = (u(seed, ln["bearing_deg"], k, 71) * 2 - 1) * fs["debris_line_jitter_blocks"]
            cx, cz = int(round(x + px * j)), int(round(z + pz * j))
            dk = fs["debris_kits"]
            name = dk[(sum(1 for f in m.features.values() if f["category"] == "find_debris")) % len(dk)]
            to = math.degrees(math.atan2(rc[0] - cx, -(rc[1] - cz))) % 360
            steps = int(round(to / 90.0)) % 4
            ok = None
            if far(cx, cz, lsp[0]) and m.wet(cx, cz):
                for band in fs["debris_bands"]:
                    rec, _why = fit_find(m, name, h32(seed, cx, cz), steps, cx, cz, fs["bands"][band]["depth"],
                                         band == fs["hooks"]["on"])
                    if rec is not None:
                        ok = (rec, band)
                        break
            k += 1
            if ok:
                rec, band = ok
                fid = "%sdebris_%s_%d" % (REWARD_PREFIX, ln["id"], n + 1)
                commit_find(m, fid, rec, name, steps, cx, cz, region_of(m, cx, cz), band, line=ln["id"])
                m.features[fid]["toward_rift_deg"] = round(to, 1)
                m.features[fid]["off_line_blocks"] = round(abs((cx - rc[0]) * px + (cz - rc[1]) * pz), 1)
                placed.append((cx, cz))
                n += 1
                t += lsp[0] + (lsp[1] - lsp[0]) * u(seed, ln["bearing_deg"], n, 73)
            else:
                t += 8.0
        if n < int(ln["count"]):
            m.problems.append("debris line %s: %d of %d placed" % (ln["id"], n, ln["count"]))
    # the vessels: per region and band, seeded order on a jittered grid
    step = int(fs["grid_step_blocks"])
    gx = np.arange(step // 2, m.N - step // 2, step)
    pts = [(int(x), int(z)) for z in gx for x in gx]
    pts = [(x + int(u(seed, x, z, 74) * step / 2) - step // 4, z + int(u(seed, x, z, 75) * step / 2) - step // 4)
           for x, z in pts]
    pts = [(x, z) for x, z in pts if m.wet(x, z) and m.sea - m.gy(x, z) >= 4]
    by = {}
    for x, z in pts:
        rid = region_of(m, x, z)
        b = band_of(fs, m.sea - m.gy(x, z))
        if rid and b:
            by.setdefault((rid, b), []).append((x, z))
    for rid, want in fs["vessels"].items():
        kits = fs["vessel_kits"].get(rid, fs["vessel_kits"]["default"])
        for band, cnt in want.items():
            cand = sorted(by.get((rid, band), []), key=lambda p: h32(seed, p[0], p[1], 76, len(rid)))
            n = 0
            for (x, z) in cand:
                if n >= cnt:
                    break
                if not far(x, z, sp):
                    continue
                name = pick(kits, seed, x, z, 77)
                steps = h32(seed, x, z, 78) % 4
                rec, _why = fit_find(m, name, h32(seed, x, z), steps, x, z, fs["bands"][band]["depth"],
                                     band == fs["hooks"]["on"])
                if rec is None:
                    continue
                n += 1
                fid = "%sfind_%s_%s_%d" % (REWARD_PREFIX, rid, band, n)
                commit_find(m, fid, rec, name, steps, x, z, rid, band)
                placed.append((x, z))
            if n < cnt:
                m.problems.append("vessels %s %s: %d of %d placed" % (rid, band, n, cnt))
    # the caches: one in cache_every, by seeded rank
    ids = sorted((f for f in m.features if m.features[f]["category"].startswith("find_")),
                 key=lambda f: h32(seed, sum(ord(c) * (i + 1) for i, c in enumerate(f)), 79))
    want = int(round(len(ids) / float(fs["cache_every"])))
    for f in ids[:want]:
        m.features[f]["has_cache"] = True
    for f in ids:
        x, y, z = m.features[f]["cache_cell"]
        if m.features[f]["has_cache"]:
            m.put(x, y, z, BARREL, "fittings", f)


# ------------------------------------------------------------------ the beached wreck

def beached_hull(spec):
    """Local cells (dx = the hull's height axis, dy = its width axis, dz = its length) of a hull on its side."""
    bw = spec["shore"]["beached_wreck"]
    L, W, h = int(bw["length"]), int(bw["half_width"]), int(bw["height"])
    half = L // 2
    cells = []
    for dz in range(-half, half + 1):
        a = abs(dz)
        w = W if a <= half - 3 else (W - 1 if a == half - 2 else (W - 2 if a == half - 1 else 0))
        if w <= 0:
            cells += [(v, W, dz, "HULL") for v in range(0, h + 1)]
            continue
        for uu in range(-(w - 1), w):
            cells.append((0, uu + W, dz, log("stripped_spruce", "z")))            # the keel, now a wall
        for uu in (-w, w):
            for v in range(1, h + 1):
                if uu == w and h32(spec["seed"], v, dz, 81) % 8 == 0:
                    continue                                                    # stove-in planks on the upper side
                cells.append((v, uu + W, dz, "HULL"))
    return cells, (h // 2, 1, 0)


def beached_wreck(m):
    spec = m.spec
    bw = spec["shore"]["beached_wreck"]
    flats = {f["id"]: f["box"] for f in m.wspec["coasts"]["flats"]}
    x0, z0, x1, z1 = flats[bw["coast"]]
    cells, cache = beached_hull(spec)
    seed = spec["seed"]
    st = int(bw["search_step_blocks"])
    cand = [(x, z) for x in range(x0 + 8, x1 - 8, st) for z in range(z0 + 8, z1 - 8, st)
            if m.sea <= m.gy(x, z) <= m.sea + int(bw["ground_above_sea"][1])]
    cand.sort(key=lambda p: h32(seed, p[0], p[1], 82))
    owner = "sea_life_beached_wreck"
    for (cx, cz) in cand:
        for steps in sorted(range(4), key=lambda s: h32(seed, cx, cz, s, 83)):
            wc = []
            for (dx, dy, dz, b) in cells:
                rx, rz = rot_xz(dx, dz, steps)
                wc.append((cx + rx, dy, cz + rz, rot_block(b, steps)))
            rx, rz = rot_xz(cache[0], cache[2], steps)
            ca = (cx + rx, cache[1], cz + rz)
            foot = {(a, b) for a, _y, b, _bl in wc}
            gs = [m.gy(a, b) for a, b in foot]
            lo, hi = min(gs), max(gs)
            if lo < m.sea + int(bw["ground_above_sea"][0]) or hi > m.sea + int(bw["ground_above_sea"][1]):
                continue
            if hi - lo > int(bw["max_relief"]):
                continue
            xs = [p[0] for p in foot]
            zs = [p[1] for p in foot]
            ring = [(a, b) for a in range(min(xs) - 2, max(xs) + 3) for b in range(min(zs) - 2, max(zs) + 3)]
            if not any(m.wet(a, b) for a, b in ring):
                continue
            if m.ex.blocked(min(xs) - 2, min(zs) - 2, max(xs) + 2, max(zs) + 2):
                continue
            if m.reserved[min(zs) - 2:max(zs) + 3, min(xs) - 2:max(xs) + 3].any():
                continue
            base = lo + 1
            for (x, dy, z, b) in wc:
                m.put(x, base + dy, z, m.hull(x, base + dy, z) if b == "HULL" else b, "build", owner)
            bar = (ca[0], base + ca[1], ca[2])
            m.put(*bar, BARREL, "fittings", owner)
            m.reserve(foot, 3)
            m.features[owner] = {"id": owner, "category": "beached_wreck", "centre": [cx, cz], "facing": FACINGS[steps],
                                 "base_y": base, "lowest_ground": lo, "relief": hi - lo, "barrel": list(bar),
                                 "blocks": len(wc), "has_cache": True}
            return
    m.problems.append("beached wreck: no site on %s passes" % bw["coast"])


# ------------------------------------------------------------------ rock pools

def rock_pools(m):
    spec = m.spec
    rp = spec["shore"]["rock_pools"]
    seed = spec["seed"]
    boxes = {s["id"]: s["box"] for s in m.wspec["coasts"]["skerries"]}
    placed = []
    for coast in rp["coasts"]:
        x0, z0, x1, z1 = boxes[coast]
        Gb = m.H[z0:z1, x0:x1].astype(np.int32)
        land = Gb >= m.sea
        wet = (Gb < m.sea) & ~m.ex.lake[z0:z1, x0:x1]
        tide = land & (Gb <= m.sea + 1) & WS.dilate4(wet)
        pt = WS.box_mean(land.astype(float), int(rp["point_radius_blocks"]))
        ml = WS.box_mean(land.astype(float), int(rp["mainland_radius_blocks"]))
        ok = tide & (pt <= float(rp["point_land_share_max"])) & (ml >= float(rp["mainland_share_min"])) \
            & ~m.ex.X[z0:z1, x0:x1]
        zs, xs = np.nonzero(ok)
        order = sorted(range(len(xs)), key=lambda i: h32(seed, int(xs[i]) + x0, int(zs[i]) + z0, 84))
        n = 0
        R = float(rp["interior_radius"])
        ri = int(math.ceil(R))
        for i in order:
            if n >= int(rp["per_coast"]):
                break
            cx, cz = int(xs[i] + x0), int(zs[i] + z0)
            if not all((cx - a) ** 2 + (cz - b) ** 2 >= rp["min_spacing_blocks"] ** 2 for a, b in placed):
                continue
            lo, hi = m.sea + rp["interior_ground_above_sea"][0], m.sea + rp["interior_ground_above_sea"][1]
            inner = {(cx + a, cz + b) for a in range(-ri, ri + 1) for b in range(-ri, ri + 1)
                     if a * a + b * b <= R * R and lo <= m.gy(cx + a, cz + b) <= hi}
            if len(inner) < 9 or len(WS_component(inner, (cx, cz))) != len(inner):
                continue
            rim = {(a + p, b + q) for (a, b) in inner for p, q in ((1, 0), (-1, 0), (0, 1), (0, -1))} - inner
            if any(m.gy(a, b) < m.sea - 2 for a, b in rim):
                continue
            if not any(m.wet(a, b) for a, b in rim):
                continue                                         # at the tide line: the sea is against its rim
            allc = inner | rim
            xsx = [p[0] for p in allc]
            zsz = [p[1] for p in allc]
            if m.ex.blocked(min(xsx), min(zsz), max(xsx), max(zsz)) or \
                    m.reserved[min(zsz):max(zsz) + 1, min(xsx):max(xsx) + 1].any():
                continue
            L = max(m.gy(a, b) for a, b in inner) + 1 + (1 if u(seed, cx, cz, 85) < 0.4 else 0)
            if L > m.sea - m.top_gap and m.ex.gated(min(xsx), min(zsz), max(xsx), max(zsz)):
                continue
            owner = "sea_life_rock_pool_%s_%d" % (coast, n + 1)
            for (a, b) in sorted(rim):
                g = m.gy(a, b)
                top = L + (1 if u(seed, a, b, 86) < 0.35 else 0)
                for y in range(g + 1, top + 1):
                    m.put(a, y, b, pick(rp["rim"], seed, a, y, b, 87), "build", owner)
            water = 0
            for (a, b) in sorted(inner):
                for y in range(m.gy(a, b) + 1, L + 1):
                    m.put(a, y, b, WATER, "flora", owner)
                    water += 1
            m.reserve(allc, 3)
            placed.append((cx, cz))
            n += 1
            m.features[owner] = {"id": owner, "category": "rock_pool", "coast": coast, "centre": [cx, cz],
                                 "level_y": L, "interior": sorted([list(p) for p in inner]),
                                 "rim": sorted([list(p) for p in rim]), "water_cells": water}
        if n < int(rp["per_coast"]):
            m.problems.append("rock pools %s: %d of %d placed" % (coast, n, rp["per_coast"]))


def WS_component(cells, start):
    seen = {start} if start in cells else set()
    todo = list(seen)
    while todo:
        a, b = todo.pop()
        for p, q in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c = (a + p, b + q)
            if c in cells and c not in seen:
                seen.add(c)
                todo.append(c)
    return seen


# ------------------------------------------------------------------ flora: kelp, seagrass, the reef

def flora(m):
    spec = m.spec
    sh = spec["shore"]
    seed = spec["seed"]
    sea = m.sea
    boxes = {f["id"]: f["box"] for f in m.wspec["coasts"]["flats"]}
    boxes.update({s["id"]: s["box"] for s in m.wspec["coasts"]["skerries"]})
    done = np.zeros((m.N, m.N), bool)
    kp, sg = sh["kelp"], sh["seagrass"]
    m.notes["flora"] = {}
    for coast in sh["coasts"]:
        x0, z0, x1, z1 = boxes[coast["id"]]
        x0, z0, x1, z1 = max(0, x0), max(0, z0), min(m.N, x1), min(m.N, z1)
        Gb = m.H[z0:z1, x0:x1].astype(np.int32)
        sea_m = (Gb < sea) & ~m.ex.X[z0:z1, x0:x1] & ~m.reserved[z0:z1, x0:x1] & ~done[z0:z1, x0:x1]
        land = Gb >= sea
        depth = sea - Gb
        ZZ, XX = np.mgrid[z0:z1, x0:x1]
        gate = m.ex.gate[z0:z1, x0:x1]
        counts = {"kelp_columns": 0, "seagrass_columns": 0}
        if coast["kelp"]:
            dl = WS.distance(land, None, max_iter=int(kp["from_land_blocks"]) + 2)
            nz = WS.value_noise(XX, ZZ, kp["patch_scale_blocks"], seed + 1)
            dens = WS._hash01(XX, ZZ, seed + 2)
            hh = WS._hash01(XX, ZZ, seed + 3)
            km = sea_m & (depth >= kp["depth"][0]) & (depth <= kp["depth"][1]) & (dl <= kp["from_land_blocks"]) \
                & (nz > kp["patch_over"]) & (dens < kp["density"])
            for k_, i in np.argwhere(km):
                x, z = int(i + x0), int(k_ + z0)
                g = int(Gb[k_, i])
                tmax = sea - (m.top_gap if gate[k_, i] else int(kp["max_top_below_surface"]))
                if tmax <= g:
                    continue
                top = g + 1 + int(hh[k_, i] * (tmax - g))
                top = min(top, tmax)
                owner = "sea_life_kelp_%s" % coast["id"]
                for y in range(g + 1, top):
                    m.put(x, y, z, "minecraft:kelp_plant", "flora", owner)
                m.put(x, top, z, "minecraft:kelp[age=25]", "flora", owner)
                counts["kelp_columns"] += 1
                done[z, x] = True
        if coast["seagrass"]:
            nz = WS.value_noise(XX, ZZ, sg["patch_scale_blocks"], seed + 4)
            dens = WS._hash01(XX, ZZ, seed + 5)
            tall = WS._hash01(XX, ZZ, seed + 6)
            gm = sea_m & ~done[z0:z1, x0:x1] & (depth >= sg["depth"][0]) & (depth <= sg["depth"][1]) \
                & (nz > sg["patch_over"]) & (dens < sg["density"]) & ~gate
            owner = "sea_life_seagrass_%s" % coast["id"]
            for k_, i in np.argwhere(gm):
                x, z = int(i + x0), int(k_ + z0)
                g = int(Gb[k_, i])
                if depth[k_, i] >= 2 and tall[k_, i] < sg["tall_share_at_2"]:
                    m.put(x, g + 1, z, "minecraft:tall_seagrass[half=lower]", "flora", owner)
                    m.put(x, g + 2, z, "minecraft:tall_seagrass[half=upper]", "flora", owner)
                else:
                    m.put(x, g + 1, z, "minecraft:seagrass", "flora", owner)
                counts["seagrass_columns"] += 1
                done[z, x] = True
        m.notes["flora"][coast["id"]] = counts
    # the reef
    rf = sh["reef"]
    ws = m.wspec["coasts"]["relic_reef"]
    cx, cz = ws["centre"]
    R = int(ws["outer_radius"][1] + ws["drop_width_blocks"] + 8)
    bx = WS.clip_box(cx - R, cz - R, cx + R + 1, cz + R + 1, m.N)
    fp = WS.reef_footprint(m.wspec, bx)
    x0, z0, x1, z1 = bx
    Gb = m.H[z0:z1, x0:x1].astype(np.int32)
    depth = sea - Gb
    rm = fp & (Gb < sea) & (depth >= rf["depth"][0]) & (depth <= rf["depth"][1]) & ~m.ex.X[z0:z1, x0:x1] \
        & ~m.reserved[z0:z1, x0:x1] & ~done[z0:z1, x0:x1]
    ZZ, XX = np.mgrid[z0:z1, x0:x1]
    # reef_footprint is the flats pass's keep-out mask, 6 wider than the reef; coral stops at the reef's own outer
    # edge, its outer radius plus the drop (tools/sea_life_audit.py found 1,294 coral blocks past it, 2026-10-02)
    rm &= np.hypot(XX - cx, ZZ - cz) <= float(ws["outer_radius"][1] + ws["drop_width_blocks"])
    mound = WS.value_noise(XX, ZZ, rf["mound_scale_blocks"], seed + 7)
    kind = WS.value_noise(XX, ZZ, 14, seed + 8)
    h1 = WS._hash01(XX, ZZ, seed + 9)
    h2 = WS._hash01(XX, ZZ, seed + 10)
    owner = "sea_life_reef"
    cnt = {"coral_blocks": 0, "coral": 0, "fans": 0, "pickles": 0, "columns": 0}
    corals = rf["corals"]
    for k_, i in np.argwhere(rm):
        x, z = int(i + x0), int(k_ + z0)
        g = int(Gb[k_, i])
        c = corals[min(len(corals) - 1, int(kind[k_, i] * len(corals)))]
        top = g
        nb = 1 if mound[k_, i] > rf["mound_over"] else 0      # one high: a block under another is not always wet
        nb = min(nb, sea - 2 - g)
        for y in range(g + 1, g + 1 + nb):
            m.put(x, y, z, "minecraft:%s_coral_block" % c, "flora", owner)
            cnt["coral_blocks"] += 1
            top = y
        if top + 1 <= sea - 1:
            if h1[k_, i] < rf["plant_density"]:
                m.put(x, top + 1, z, "minecraft:%s_coral[waterlogged=true]" % c, "flora", owner)
                cnt["coral"] += 1
            elif h1[k_, i] < rf["plant_density"] + rf["fan_density"]:
                m.put(x, top + 1, z, "minecraft:%s_coral_fan[waterlogged=true]" % c, "flora", owner)
                cnt["fans"] += 1
            elif h2[k_, i] < rf["pickle_density"]:
                m.put(x, top + 1, z, "minecraft:sea_pickle[pickles=%d,waterlogged=true]" % (1 + int(h2[k_, i] * 100) % 4),
                      "flora", owner)
                cnt["pickles"] += 1
        cnt["columns"] += 1
    m.notes["reef"] = cnt


# ------------------------------------------------------------------ checks

def checks(m):
    p = m.problems
    sea = m.sea
    cats = {}
    for f in m.features.values():
        cats[f["category"]] = cats.get(f["category"], 0) + 1
    m.notes["categories"] = cats
    # nonempty per category
    for c in ("surfacing_cave", "sea_cave", "beached_wreck", "rock_pool", "find_vessel", "find_debris"):
        if not cats.get(c):
            p.append("category %s is empty" % c)
    for coast in m.spec["shore"]["coasts"]:
        fl = m.notes.get("flora", {}).get(coast["id"], {})
        if coast["kelp"] and not fl.get("kelp_columns"):
            p.append("no kelp on %s" % coast["id"])
        if coast["seagrass"] and not fl.get("seagrass_columns"):
            p.append("no seagrass on %s" % coast["id"])
    if not m.notes.get("reef", {}).get("coral_blocks"):
        p.append("no coral on the Relic reef")
    # every write: a column no exclusion holds; under the gate rule
    by_owner_cols = {}
    gated_high = 0
    for (x, y, z), (b, pas, owner) in m.writes.items():
        by_owner_cols.setdefault(owner, set()).add((x, z))
        if m.ex.gate[z, x] and y > sea - m.top_gap and m.wet(x, z):
            gated_high += 1
    if gated_high:
        p.append("%d writes inside a gate's clearance reach within %d of the surface" % (gated_high, m.top_gap - 1))
    excl = {}
    for owner, cols in by_owner_cols.items():
        for (x, z) in cols:
            if m.ex.X[z, x]:
                excl[owner] = m.ex.blocked(x, z, x, z)
                break
    for owner, why in sorted(excl.items()):
        p.append("%s writes inside %s" % (owner, why))
    # flora on valid supports, under the surface; kelp tops; coral only on the reef, touching water
    ws = m.wspec["coasts"]["relic_reef"]
    R = int(ws["outer_radius"][1] + ws["drop_width_blocks"] + 8)
    bx = WS.clip_box(ws["centre"][0] - R, ws["centre"][1] - R, ws["centre"][0] + R + 1, ws["centre"][1] + R + 1, m.N)
    fp = WS.reef_footprint(m.wspec, bx)
    bad = {"kelp": 0, "seagrass": 0, "coral_off_reef": 0, "coral_dry": 0, "kelp_top": 0}
    for (x, y, z), (b, pas, owner) in m.writes.items():
        i = bid(b)
        if i in ("minecraft:kelp", "minecraft:kelp_plant", "minecraft:seagrass", "minecraft:tall_seagrass"):
            g = m.gy(x, z)
            below = m.writes.get((x, y - 1, z))
            supported = (y == g + 1) or (below and bid(below[0]) in ("minecraft:kelp_plant", "minecraft:tall_seagrass"))
            if not supported or y > sea or not m.wet(x, z):
                bad["kelp" if "kelp" in i else "seagrass"] += 1
            if i == "minecraft:kelp" and y > sea - int(m.spec["shore"]["kelp"]["max_top_below_surface"]):
                bad["kelp_top"] += 1
        if "coral" in i:
            if not (bx[0] <= x < bx[2] and bx[1] <= z < bx[3] and fp[z - bx[1], x - bx[0]]):
                bad["coral_off_reef"] += 1
            if i.endswith("_coral_block"):
                wet_n = False
                for a, bb, c in ((0, 1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)):
                    q = (x + a, y + bb, z + c)
                    w = m.writes.get(q)
                    if q[1] <= sea and m.wet(q[0], q[2]) and q[1] > m.gy(q[0], q[2]) and \
                            (w is None or "waterlogged=true" in w[0] or bid(w[0]) == WATER):
                        wet_n = True
                        break
                if not wet_n:
                    bad["coral_dry"] += 1
    for k, n in bad.items():
        if n:
            p.append("%d %s faults" % (n, k))
    # rock pools hold their water; nothing cut
    for f in m.features.values():
        if f["category"] != "rock_pool":
            continue
        inner = {tuple(q) for q in f["interior"]}
        L = f["level_y"]
        leaks = 0
        for (a, b) in inner:
            for y in range(m.gy(a, b) + 1, L + 1):
                for pp, qq in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    c = (a + pp, b + qq)
                    if c in inner:
                        continue
                    w = m.writes.get((c[0], y, c[1]))
                    if not ((w and bid(w[0]) not in (WATER, AIR)) or m.gy(*c) >= y):
                        leaks += 1
        for (x, y, z), (bl, _pas, owner) in m.writes.items():
            if owner == f["id"] and y <= m.gy(x, z):
                leaks += 1000
        if leaks:
            p.append("%s: %d leaks or cuts" % (f["id"], leaks))
    # finds: totals, bands, spacing, seating, flooded, hooks, caches
    fs = m.spec["finds"]
    fl = [f for f in m.features.values() if f["category"].startswith("find_")]
    m.notes["finds"] = {"total": len(fl), "surf": sum(1 for f in fl if f["band"] == "surf"),
                        "caches": sum(1 for f in fl if f["has_cache"])}
    if not (fs["total"][0] <= len(fl) <= fs["total"][1]):
        p.append("%d finds, not %d-%d" % (len(fl), fs["total"][0], fs["total"][1]))
    if fl:
        share = m.notes["finds"]["surf"] / float(len(fl))
        m.notes["finds"]["surf_share"] = round(share, 3)
        if not (fs["surf_share"][0] <= share <= fs["surf_share"][1]):
            p.append("Surf-reach share %.2f outside %s" % (share, fs["surf_share"]))
        cs = m.notes["finds"]["caches"] / float(len(fl))
        m.notes["finds"]["cache_share"] = round(cs, 3)
        if not (fs["cache_share"][0] <= cs <= fs["cache_share"][1]):
            p.append("cache share %.2f outside %s" % (cs, fs["cache_share"]))
    per = {}
    for f in fl:
        per[(f["region"], f["band"])] = per.get((f["region"], f["band"]), 0) + 1
        if not (1 <= f["base_y"] - f["lowest_ground"] <= 2):
            p.append("%s is not seated" % f["id"])
        if f["band"] != band_of(fs, f["depth"]):
            p.append("%s: depth %d is not band %s" % (f["id"], f["depth"], f["band"]))
        if f["top_y"] > sea - m.top_gap:
            p.append("%s breaks the surface rule" % f["id"])
        if f["band"] == fs["hooks"]["on"] and not f["hook"]:
            p.append("%s is in Surf reach with no hook" % f["id"])
        if f["category"] == "find_debris" and f["off_line_blocks"] > fs["debris_line_jitter_blocks"] + 1:
            p.append("%s lies %.1f off its line" % (f["id"], f["off_line_blocks"]))
    m.notes["finds"]["per_region_band"] = {"%s/%s" % k: v for k, v in sorted(per.items())}
    kits_used = {f["kit"] for f in fl}
    declared = set(fs["debris_kits"]) | {k for ks in fs["vessel_kits"].values() for k in ks}
    m.notes["finds"]["kits"] = {k: sum(1 for f in fl if f["kit"] == k) for k in sorted(declared)}
    for k in sorted(declared - kits_used):
        p.append("kit %s is declared and never placed" % k)
    for rid, want in fs["vessels"].items():
        for band, cnt in want.items():
            got = sum(1 for f in fl if f["region"] == rid and f["band"] == band and f["category"] == "find_vessel")
            if got != cnt:
                p.append("vessels %s/%s: %d, declared %d" % (rid, band, got, cnt))
    for i, a in enumerate(fl):
        for b in fl[i + 1:]:
            gap = math.hypot(a["centre"][0] - b["centre"][0], a["centre"][1] - b["centre"][1])
            both_vessels = a["category"] == b["category"] == "find_vessel"
            need = fs["min_spacing_blocks"] if both_vessels else fs["debris_line_spacing_blocks"][0]
            if gap < need:
                p.append("%s and %s are %.0f apart" % (a["id"], b["id"], gap))
    for (x, y, z), (b, pas, owner) in m.writes.items():
        if owner.startswith(REWARD_PREFIX + "find_") or owner.startswith(REWARD_PREFIX + "debris_"):
            if b == AIR:
                p.append("%s writes air at (%d, %d, %d)" % (owner, x, y, z))
            elif waterloggable(b) and "waterlogged=true" not in b:
                p.append("%s writes %s dry under the sea" % (owner, b))
            elif not waterloggable(b) and any(t in bid(b) for t in NOT_FULL) and not bid(b).endswith(DRY_IN_WATER):
                p.append("%s writes %s, which holds neither water nor its own cell" % (owner, b))
    m.problems = p
    return p


# ------------------------------------------------------------------ the build

def model(source_root=None, spec=None):
    spec = spec or load()
    m = Model(spec, source_root)
    surfacing_cave(m)
    sea_cave(m)
    beached_wreck(m)
    finds(m)
    rock_pools(m)
    flora(m)
    checks(m)
    m.lines = lines(m)
    return m


def lines(m):
    out = {p: [] for p in PASSES}
    cols = {p: {} for p in PASSES}
    seen = set()
    for k in m.order["fittings"]:
        if k in seen or m.writes[k][1] != "fittings":
            continue
        seen.add(k)
        out["fittings"].append("setblock %d %d %d %s" % (k[0], k[1], k[2], m.writes[k][0]))
    for (x, y, z), (b, pas, _o) in m.writes.items():
        if pas != "fittings":
            cols[pas].setdefault((x, z), []).append((y, b))
    for pas in PASSES:
        if pas == "fittings":
            continue
        for (x, z) in sorted(cols[pas]):
            out[pas] += [RM.cmd(x, a, c, z, bl) for a, c, bl in RM.column_runs(x, z, cols[pas][(x, z)])]
    return out


def summary(m):
    feats = {}
    for f in m.features.values():
        feats.setdefault(f["category"], []).append(f["id"])
    sc = m.features.get("sea_life_" + m.spec["surfacing_cave"]["id"], {})
    return {
        "sea_level": m.sea,
        "rift_centre": m.notes.get("rift_centre"),
        "categories": m.notes.get("categories"),
        "flora": m.notes.get("flora"),
        "reef": m.notes.get("reef"),
        "finds": m.notes.get("finds"),
        "debris_line_start": m.notes.get("debris_line_start"),
        "surfacing_cave": {k: v for k, v in sc.items() if k not in ("passage_profile",)},
        "surfacing_cave_profile": sc.get("passage_profile"),
        "sea_cave": m.features.get("sea_life_sea_cave"),
        "beached_wreck": m.features.get("sea_life_beached_wreck"),
        "rock_pools": [{k: f[k] for k in ("id", "centre", "level_y", "water_cells")} for f in m.features.values()
                       if f["category"] == "rock_pool"],
        "find_list": [{k: f.get(k) for k in ("id", "kit", "centre", "depth", "band", "region", "facing", "has_cache",
                                             "hook", "line")} for f in m.features.values()
                      if f["category"].startswith("find_")],
        "gate_lines": m.ex.gate_lines,
        "ferry_lanes": len(m.ex.lanes),
        "writes": len(m.writes),
        "problems": m.problems,
        "commands": {k: len(v) for k, v in m.lines.items()},
    }


def write(m):
    _fn, order = RM.write_blocks(OUT, m.lines, PASSES, "tools/sea_life.py",
                                 "Cobblers: the sea's block pass - shore, wrecks and Rift debris, the surfacing cave "
                                 "(tools/sea_life.py)")
    return order


# ------------------------------------------------------------------ the records in data/rewards.json

def records(m):
    spec = m.spec
    verified = {}
    for r in json.loads(REWARDS.read_text(encoding="utf-8"))["rewards"]:
        if str(r.get("id", "")).startswith(REWARD_PREFIX):
            continue
        for it in r.get("contents", []):
            if it.get("verification"):
                verified.setdefault(it["item"], it["verification"])
    out = []

    def rec(rid, kind, at, place, built_by):
        c = spec["caches"][kind]
        missing = [it["item"] for it in c["contents"] if it["item"] not in verified]
        if missing:
            raise LifeError("cache %s: %s verified by no other record in data/rewards.json" % (rid, missing))
        x, y, z = at
        out.append({"id": rid, "kind": "cache", "place": place,
                    "contents": [dict(it, verification=verified[it["item"]]) for it in c["contents"]],
                    "message": c["message"],
                    "why": "data/sea_life.json caches.%s: %s" % (kind, "the find that pays for the swim or the walk"),
                    "built_by": built_by,
                    "trigger": {"min": [x - 2, y, z - 2], "max": [x + 2, y + 2, z + 2]},
                    "container": {"block": "minecraft:barrel", "at": [x, y, z]}})
    bb = "tools/sea_life.py (the barrel, in cobblers_sea_life's fittings pass)"
    for f in sorted(m.features.values(), key=lambda f: f["id"]):
        if f["category"].startswith("find_") and f["has_cache"]:
            what = "%s %s" % (f["kit"].replace("_", " "), "wreck" if f["category"] == "find_vessel" else "(Rift debris)")
            rec(f["id"], "surf_find" if f["band"] == "surf" else "dive_find", f["cache_cell"],
                "the seabed at (%d, %d), %d deep in the %s: a %s, its barrel" % (f["centre"][0], f["centre"][1],
                                                                               f["depth"], f["region"], what), bb)
    w = m.features.get("sea_life_beached_wreck")
    if w:
        rec(w["id"], "beached_wreck", w["barrel"], "the south strand at (%d, %d): the hull on its side on the sand"
            % tuple(w["centre"]), bb)
    c = m.features.get("sea_life_sea_cave")
    if c:
        rec(c["id"], "sea_cave", c["barrel"], "the windward coast's waterline sea cave, mouth at (%d, %d): its far "
            "chamber" % tuple(c["mouth"]), bb)
    s = m.features.get("sea_life_" + spec["surfacing_cave"]["id"])
    if s and s.get("barrel"):
        rec(s["id"], "surfacing_cave", s["barrel"], "%s under the windward headland: the end of the dry gallery "
            "past the pool" % spec["surfacing_cave"]["display_name"], bb)
    return out


def write_records(rew):
    doc = json.loads(REWARDS.read_text(encoding="utf-8"))
    doc["rewards"] = [r for r in doc["rewards"] if not str(r.get("id", "")).startswith(REWARD_PREFIX)] + rew
    with open(REWARDS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", choices=("report", "build", "records"))
    p.add_argument("--source-root", default=None)
    p.add_argument("--write", action="store_true", help="records: replace this build's records in data/rewards.json")
    a = p.parse_args(argv)
    m = model(a.source_root)
    s = summary(m)
    if a.cmd == "records":
        rew = records(m)
        if a.write:
            write_records(rew)
            print("wrote %d rewards (%s*)" % (len(rew), REWARD_PREFIX))
        else:
            print(json.dumps(rew, indent=1))
        return 1 if m.problems else 0
    brief = {k: v for k, v in s.items() if k not in ("find_list", "surfacing_cave_profile")}
    print(json.dumps(brief, indent=1, default=list))
    if a.cmd == "build":
        if m.problems:
            print("NOT BUILT: %d problems" % len(m.problems))
            return 1
        order = write(m)
        s["functions"] = ["%s:%s/%s" % (NS, FOLDER, f) for f in order]
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(s, indent=1, default=list) + "\n", encoding="utf-8")
        print("wrote %s (%d functions) and %s" % (OUT.relative_to(ROOT), len(order), PLAN.relative_to(ROOT)))
    return 1 if m.problems else 0


if __name__ == "__main__":
    sys.exit(main())
