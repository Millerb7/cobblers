#!/usr/bin/env python
"""Where monsters would spawn in a place, and the lights that stop them, from committed data only.

Overworld monsters spawn on a spawnable block with two passable blocks over it where block light is 0. A town's
streets are lit by their lamps, but a house with no light in a room, a roof, a covered street, or the Displaced
City's whole cavern (no sun, ever) fills with zombies. This tool models a place in voxels from what the repository
says is there, propagates the light its lamps, lanterns and torches give, lists every spawnable position left at block
light 0, and places lights until there are none:

  model     ground from tools/ground.py (the heightmap, or the cavern floor or islet), streets and squares from the
            derived plan, every building and earthwork exactly as tools/town_audit.py expects it (templates, donors,
            replayed commands), and each lamp the plan lights
  light     block light, 15 from a lantern falling 1 a block through anything not opaque. Slabs and stairs are treated
            as opaque, so the model can only under-light, never over-light: a place it calls lit is lit
  scope     the Displaced City: the whole cavern, which has no sky. Every other place: every position with a roof over
            it (within 8 blocks) inside a building footprint or on a street: rooms, covered streets, the mansion
  fix       indoors, a standing lantern on the dark floor (the lit windows); outdoors in the cavern, a lantern post
            (a fence and a lantern), never on a street; each round lights the darkest positions, then the model is run
            again, until nothing is dark

It writes an earthwork `<settlement>_lights` into data/placements.json, which the town builds with everything else,
and it never reads a world to decide (CLAUDE.md, the ground rule). `check` reads a STOPPED world's own light arrays to
see whether the result is what the model said: that is the verification.

  python tools/light_plan.py plan <settlement>... --source-root <root> --server-dir <server>
  python tools/light_plan.py check <settlement>... --world <stopped world copy> --server-dir <server>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

EMIT = {"lantern": 15, "sea_lantern": 15, "glowstone": 15, "shroomlight": 15, "jack_o_lantern": 15, "beacon": 15,
        "ochre_froglight": 15, "pearlescent_froglight": 15, "verdant_froglight": 15, "campfire": 15, "lava": 15,
        "fire": 15, "end_rod": 14, "torch": 14, "wall_torch": 14, "soul_lantern": 10, "soul_torch": 10,
        "soul_wall_torch": 10, "soul_campfire": 10, "glow_lichen": 7, "redstone_torch": 7, "redstone_wall_torch": 7,
        "magma_block": 3, "crying_obsidian": 10, "respawn_anchor": 0, "copper_bulb": 0}
# Exact names, then suffixes. Substrings were wrong both ways: "light" made light-gray wool see-through, "snow" made
# a snow block see-through, and a model that thinks light passes where it does not says a dark room is lit.
SEE_THROUGH_EXACT = {"air", "cave_air", "void_air", "light", "structure_void", "glass", "iron_bars", "chain", "ladder",
                     "rail", "powered_rail", "detector_rail", "activator_rail", "flower_pot", "snow", "short_grass",
                     "tall_grass", "fern", "large_fern", "vine", "glow_lichen", "water", "campfire", "soul_campfire",
                     "lectern", "cauldron", "water_cauldron", "chest", "trapped_chest", "ender_chest", "cobweb",
                     "scaffolding", "dead_bush", "azalea", "flowering_azalea", "pink_petals", "poppy", "dandelion",
                     "blue_orchid", "allium", "azure_bluet", "oxeye_daisy", "cornflower", "lily_of_the_valley",
                     "rose_bush", "peony", "lilac", "sunflower", "carrots", "potatoes", "beetroots", "wheat", "sugar_cane",
                     "sweet_berry_bush", "candle", "hanging_roots", "moss_carpet", "torch", "wall_torch", "soul_torch",
                     "soul_wall_torch", "redstone_torch", "redstone_wall_torch", "lantern", "soul_lantern", "end_rod",
                     "lily_pad", "seagrass", "tall_seagrass", "kelp", "kelp_plant", "brewing_stand", "bell", "grindstone",
                     "anvil", "enchanting_table", "decorated_pot", "composter"}
SEE_THROUGH_SUFFIX = ("_pane", "_fence", "_fence_gate", "_leaves", "_door", "_trapdoor", "_carpet", "_sign",
                      "_wall_sign", "_hanging_sign", "_button", "_pressure_plate", "_bed", "_banner", "_wall_banner",
                      "_sapling", "_tulip", "_candle", "_glass", "_coral", "_coral_fan", "_head", "_skull")
NO_SPAWN_ON = ("_slab", "_stairs", "_wall", "bedrock", "barrier", "magma_block", "farmland", "lava", "ice")


def short(name):
    return name.split(":")[-1].split("[")[0]


def see_through(name):
    s = short(name)
    return s in SEE_THROUGH_EXACT or s.endswith(SEE_THROUGH_SUFFIX)


def spawn_surface(name):
    s = short(name)
    return not see_through(name) and not any(s == k or s.endswith(k) for k in NO_SPAWN_ON)


class Model:
    """A voxel box: opaque (bool), emit (0-15), surface (bool: a monster may stand on it), name lookups."""

    def __init__(self, box, y0, y1):
        self.x0, self.z0, self.x1, self.z1 = box
        self.y0, self.y1 = y0, y1
        shape = (self.x1 - self.x0 + 1, y1 - y0 + 1, self.z1 - self.z0 + 1)
        self.opaque = np.zeros(shape, bool)
        self.surface = np.zeros(shape, bool)
        self.emit = np.zeros(shape, np.int8)
        self.solid_any = np.zeros(shape, bool)           # anything at all (for "passable")

    def idx(self, x, y, z):
        i, j, k = x - self.x0, y - self.y0, z - self.z0
        if 0 <= i < self.opaque.shape[0] and 0 <= j < self.opaque.shape[1] and 0 <= k < self.opaque.shape[2]:
            return i, j, k
        return None

    def set(self, x, y, z, name):
        t = self.idx(x, y, z)
        if t is None:
            return
        s = short(name)
        air = s in ("air", "cave_air", "void_air")
        self.opaque[t] = not see_through(name)
        self.surface[t] = spawn_surface(name)
        self.solid_any[t] = not air and s not in ("short_grass", "tall_grass", "fern", "large_fern", "snow", "dead_bush")
        self.emit[t] = EMIT.get(s, 0)

    def column(self, x, z, top, name_top="minecraft:dirt"):
        """Solid ground up to `top`, air above."""
        t = self.idx(x, self.y0, z)
        if t is None:
            return
        i, _, k = t
        h = top - self.y0
        if h >= 0:
            self.opaque[i, :h + 1, k] = True
            self.surface[i, :h + 1, k] = True
            self.solid_any[i, :h + 1, k] = True
        self.opaque[i, max(h + 1, 0):, k] = False
        self.surface[i, max(h + 1, 0):, k] = False
        self.solid_any[i, max(h + 1, 0):, k] = False
        self.emit[i, :, k] = 0
        if 0 <= h < self.opaque.shape[1]:
            self.set(x, top, z, name_top)

    def light(self):
        L = self.emit.astype(np.int16).copy()
        clear = ~self.opaque
        for _ in range(15):
            nb = np.zeros_like(L)
            nb[1:, :, :] = np.maximum(nb[1:, :, :], L[:-1, :, :])
            nb[:-1, :, :] = np.maximum(nb[:-1, :, :], L[1:, :, :])
            nb[:, 1:, :] = np.maximum(nb[:, 1:, :], L[:, :-1, :])
            nb[:, :-1, :] = np.maximum(nb[:, :-1, :], L[:, 1:, :])
            nb[:, :, 1:] = np.maximum(nb[:, :, 1:], L[:, :, :-1])
            nb[:, :, :-1] = np.maximum(nb[:, :, :-1], L[:, :, 1:])
            L = np.maximum(L, np.where(clear, nb - 1, 0))
        return L

    def spawn_cells(self):
        """(i, j, k) of every cell a monster could spawn in: a spawn surface below, it and the cell over it passable."""
        passable = ~self.solid_any
        ok = np.zeros_like(self.opaque)
        ok[:, 1:-1, :] = self.surface[:, :-2, :] & passable[:, 1:-1, :] & passable[:, 2:, :]
        return ok


def build_model(settlement, doc, source_root, server_dir, extra=None):
    """-> (model, scope mask, street cells, indoor mask). Everything from data; nothing from a world."""
    import ground as G
    import town_audit as TA
    g = G.for_settlement(settlement, source_root, doc)
    pp = ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)
    # the hometown has roads, not a town plan: its buildings are modelled, its roads are open sky
    plan = json.loads(pp.read_text(encoding="utf-8")) if pp.is_file() else {"streets": {}}
    buildings = TA.expected_buildings(settlement, doc, server_dir)
    pts = [p for _, s, r, _ in buildings if s for p in list(s) + list(r or {})]
    cells = {}
    for st in (plan.get("streets") or {}).values():
        for z, y, xa, xb in st["cells"]:
            for x in range(xa, xb + 1):
                cells[(x, z)] = (y, st["surface"])
    cavern = g.kind == "cavern_floor"
    if cavern:
        box = g.ceiling["box"]
        ceil = g.ceiling["grid"]
        y0, y1 = int(g.box(*box).min()) - 2, int(ceil.max()) + 1
    else:
        xs = [p[0] for p in pts] + [c[0] for c in cells]
        zs = [p[2] for p in pts] + [c[1] for c in cells]
        box = (min(xs) - 16, min(zs) - 16, max(xs) + 16, max(zs) + 16)
        ys = [p[1] for p in pts] + [v[0] for v in cells.values()]
        y0, y1 = min(ys) - 4, max(ys) + 8
    m = Model(box, y0, y1)
    grid = g.box(*box)
    for k in range(grid.shape[0]):
        for i in range(grid.shape[1]):
            m.column(box[0] + i, box[1] + k, int(grid[k, i]), "minecraft:grass_block")
    if cavern:
        cx0, cz0, cx1, cz1 = box
        for k in range(cz1 - cz0 + 1):
            for i in range(cx1 - cx0 + 1):
                c = int(ceil[k, i])
                j = c - y0
                if 0 <= j < m.opaque.shape[1]:
                    m.opaque[i, j:, k] = True
                    m.solid_any[i, j:, k] = True
    for (x, z), (y, surf) in cells.items():
        m.column(x, z, y, surf)
    if plan.get("plaza"):
        x0, z0, x1, z1 = plan["plaza"]["rect"]
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                m.column(x, z, plan["plaza"]["y"], plan["plaza"]["surface"])
    for l in (plan.get("lots") or []) + (plan.get("anchors") or []):
        if l.get("level") is not None:
            x0, z0, x1, z1 = l["rect"]
            for x in range(x0, x1 + 1):
                for z in range(z0, z1 + 1):
                    m.column(x, z, l["level"], "minecraft:grass_block")
    lamp = plan.get("lamp_block")
    for L in plan.get("lamps") or []:
        x, y, z = L["at"]
        if lamp and lamp != "none":
            m.set(x, y - 1, z, lamp)
    footprint = set()
    for _, solid, rooms, _ in buildings:
        for p, name in (rooms or {}).items():
            m.set(*p, "minecraft:air")
        for p, name in (solid or {}).items():
            m.set(*p, name)
            footprint.add((p[0], p[2]))
    for p, name in (extra or {}).items():
        m.set(*p, name)
    # scope
    scope = np.zeros_like(m.opaque)
    if cavern:
        scope[:] = True
    else:
        for (x, z) in footprint:
            t = m.idx(x, m.y0, z)
            if t:
                scope[t[0], :, t[2]] = True
        # a street cell with anything built over it within 6 blocks is a covered street
        for (x, z), (y, _) in cells.items():
            t = m.idx(x, y, z)
            if t and m.solid_any[t[0], t[1] + 2:t[1] + 7, t[2]].any():
                scope[t[0], :, t[2]] = True
    # indoors: something opaque within 8 blocks overhead (a roof or a ceiling), not the cavern's far rock roof
    covered = np.zeros_like(m.opaque)
    if cavern:
        rock = np.zeros_like(m.opaque)
        cx0, cz0, cx1, cz1 = box
        for k in range(cz1 - cz0 + 1):
            for i in range(cx1 - cx0 + 1):
                j = int(ceil[k, i]) - y0
                if 0 <= j < rock.shape[1]:
                    rock[i, j:, k] = True
        built = m.opaque & ~rock
    else:
        built = m.opaque
    for d in range(1, 9):
        covered[:, :-d, :] |= built[:, d:, :]
    if not cavern:
        # under open sky, monsters spawn outdoors at night wherever the lamps do not reach, as in any town; this is
        # about what has a roof over it: rooms, covered streets, the mansion
        scope &= covered
    return m, scope, cells, covered


def designed(plan_doc, derived, m, cells):
    """The lighting a plan asks for by design, before any gap is filled: lantern posts along named streets every
    `every` blocks, alternating sides, just off the paving; and one at each corner of the square. -> [(x, y, z)]
    of post feet (a fence there, a lantern on it)."""
    spec = (plan_doc or {}).get("lighting") or {}
    out = []
    for sid, every in (spec.get("streets") or {}).items():
        st = (derived.get("streets") or {}).get(sid)
        src = next((q for q in plan_doc.get("streets") or [] if q["id"] == sid), None)
        if not st or not src:
            continue
        import math
        pts, acc = [], 0.0
        poly = src["polyline"]
        for (ax, az), (bx, bz) in zip(poly, poly[1:]):
            L = math.hypot(bx - ax, bz - az)
            for t in range(int(L)):
                pts.append((ax + (bx - ax) * t / L, az + (bz - az) * t / L, (bx - ax) / L, (bz - az) / L, acc + t))
            acc += L
        side, last = 1, -10 ** 6
        for x, z, dx, dz, dist in pts:
            if dist - last < every:
                continue
            off = src["width"] // 2 + 1
            px, pz = int(round(x - dz * off * side)), int(round(z + dx * off * side))
            if (px, pz) in cells:
                continue
            # the post stands on the ground beside the road: the first spawnable surface near the road's level
            yref = cells.get((int(round(x)), int(round(z))), (None,))[0]
            t0 = m.idx(px, (yref or m.y0) - 4, pz)
            if yref is None or t0 is None:
                continue
            col_i, _, col_k = t0
            for y in range(yref + 4, yref - 5, -1):
                t = m.idx(px, y, pz)
                if t and m.surface[col_i, t[1] - 1, col_k] and not m.solid_any[t]:
                    out.append((px, y, pz))
                    side, last = -side, dist
                    break
    # authored posts: a nook the heightmap model does not hold (a hillside that stands higher than the rounded
    # heightmap says), found dark by `check` and lit by hand in data, each with its reason in the plan
    out += [tuple(p["at"]) for p in spec.get("posts") or []]
    if spec.get("square_corners") and derived.get("plaza"):
        x0, z0, x1, z1 = derived["plaza"]["rect"]
        y = derived["plaza"]["y"] + 1
        out += [(x0, y, z0), (x1, y, z0), (x0, y, z1), (x1, y, z1)]
    return out


def dark(m, scope):
    L = m.light()
    sp = m.spawn_cells() & scope
    return sp & (L <= 0), L


def plan_lights(settlement, doc, source_root, server_dir, extra=None, max_rounds=60, spacing=20):
    m, scope, cells, covered = build_model(settlement, doc, source_root, server_dir, extra)
    before = int(dark(m, scope)[0].sum())
    dp = ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)
    derived = json.loads(dp.read_text(encoding="utf-8")) if dp.is_file() else {}
    added = [(x, y, z, False) for x, y, z in designed(doc["settlements"][settlement].get("plan"), derived, m, cells)]
    for x, y, z, _ in added:
        m.set(x, y, z, "minecraft:spruce_fence")
        m.set(x, y + 1, z, "minecraft:lantern")
    n_design = len(added)
    d, L = dark(m, scope)
    sp_all = m.spawn_cells()
    for _ in range(max_rounds):
        idx = np.argwhere(d)
        if not len(idx):
            break
        chosen = []
        for i, j, k in idx[np.lexsort((idx[:, 1], idx[:, 2], idx[:, 0]))]:
            x, y, z = m.x0 + i, m.y0 + j, m.z0 + k
            if any(abs(x - a) + abs(z - c) + abs(y - b) < spacing for a, b, c, _ in chosen):
                continue
            indoor = bool(covered[i, j, k])
            if not indoor and (x, z) in cells:
                # never a post on a street: the nearest spawnable cell beside it that is not street takes the post
                near = [(abs(dx) + abs(dz), x + dx, z + dz) for dx in range(-4, 5) for dz in range(-4, 5)
                        if (x + dx, z + dz) not in cells]
                spot = None
                for _, nx, nz in sorted(near):
                    for dy in (0, 1, -1, 2, -2):
                        t = m.idx(nx, y + dy, nz)
                        if t and sp_all[t] and not covered[t]:
                            spot = (nx, y + dy, nz)
                            break
                    if spot:
                        break
                if not spot:
                    continue
                x, y, z = spot
            chosen.append((x, y, z, indoor))
        if not chosen:
            break
        for x, y, z, indoor in chosen:
            if indoor:
                m.set(x, y, z, "minecraft:lantern")
            else:
                m.set(x, y, z, "minecraft:spruce_fence")
                m.set(x, y + 1, z, "minecraft:lantern")
            added.append((x, y, z, indoor))
        d, L = dark(m, scope)
    return {"before": before, "after": int(d.sum()), "lights": added, "designed": n_design,
            "left": [(int(m.x0 + i), int(m.y0 + j), int(m.z0 + k)) for i, j, k in np.argwhere(d)[:20]]}


def commands(settlement, added, wood="spruce"):
    c = ["# lights for %s (tools/light_plan.py): no walkable position here is left at block light 0" % settlement]
    for x, y, z, indoor in added:
        if indoor:
            c.append("setblock %d %d %d minecraft:lantern[hanging=false]" % (x, y, z))
        else:
            c.append("setblock %d %d %d minecraft:%s_fence" % (x, y, z, wood))
            c.append("setblock %d %d %d minecraft:lantern[hanging=false]" % (x, y + 1, z))
    return c


def cmd_plan(a):
    path = ROOT / "data" / "placements.json"
    for sid in a.settlements:
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["placements"] = [q for q in doc["placements"] if q["id"] != "%s_lights" % sid]
        res = plan_lights(sid, doc, a.source_root, a.server_dir)
        print("%-16s dark positions %5d -> %d with %d lights (%d by design, %d indoors)%s" % (
            sid, res["before"], res["after"], len(res["lights"]), res["designed"], sum(1 for l in res["lights"] if l[3]),
            "  LEFT %s" % res["left"][:5] if res["after"] else ""))
        if res["lights"]:
            doc["placements"].append({"id": "%s_lights" % sid, "settlement": sid, "kind": "earthwork",
                                      "cell": next((q.get("cell") for q in doc["placements"] if q.get("settlement") == sid and q.get("cell")), None),
                                      "status": "planned", "after": "donors",
                                      "chosen_because": "no walkable position left at block light 0, where monsters spawn: %d positions were dark, "
                                                        "%d lights placed by tools/light_plan.py from the model of what the data builds"
                                                        % (res["before"], len(res["lights"])),
                                      "commands": commands(sid, res["lights"])})
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return 0


def world_light(world, x, y, z, cache):
    """Block light at (x, y, z) from a saved world's light arrays, or None when the section has none."""
    import nbt
    key = (x >> 4, z >> 4)
    if key not in cache:
        cache[key] = {}
        p = Path(world) / "region" / ("r.%d.%d.mca" % (x >> 9, z >> 9))
        if ("r", x >> 9, z >> 9) not in cache:
            cache[("r", x >> 9, z >> 9)] = True
            for cx, cz, ch in nbt.region_chunks(p):
                cache[(ch.get("xPos", cx), ch.get("zPos", cz))] = {s.get("Y"): s.get("BlockLight") for s in ch.get("sections") or []}
    secs = cache.get(key) or {}
    bl = secs.get(y >> 4, "missing")
    if bl == "missing":
        return None
    if bl is None:
        return 0
    i = ((y & 15) << 8) | ((z & 15) << 4) | (x & 15)
    b = bl[i >> 1] & 0xFF
    return (b >> 4) if i & 1 else (b & 0x0F)


def connected_air(m, cols):
    """The world's passable cells joined to the cavern the plan carved: seeded strictly between the planned floor and
    ceiling (derived/cavern/plan.npz) where the world is open, grown face to face through the world's own passable
    cells. -> bool array on the model's grid. What it leaves out is not the cavern: the mountain's open surface over
    the rim of the plan's box, and voids sealed in the rock of the ceiling (2026-09-21: 445 such positions)."""
    shape = m.opaque.shape
    open_ = np.zeros(shape, bool)
    seen = {}
    for (x, z), col in cols.items():
        for j in range(shape[1]):
            b = col[j]
            if b not in seen:
                seen[b] = see_through(b) and short(b) not in ("water", "lava")
            open_[x - m.x0, j, z - m.z0] = seen[b]
    plan = json.loads((ROOT / "derived" / "cavern" / "plan.json").read_text(encoding="utf-8"))
    arr = np.load(ROOT / "derived" / "cavern" / "plan.npz")
    cx0, cz0 = plan["cavern"][0], plan["cavern"][1]
    seed = np.zeros(shape, bool)
    for jz in range(arr["floor"].shape[0]):
        for ix in range(arr["floor"].shape[1]):
            t = m.idx(cx0 + ix, m.y0, cz0 + jz)
            if t is None:
                continue
            lo = max(int(arr["floor"][jz, ix]) + 1 - m.y0, 0)
            hi = min(int(arr["ceiling"][jz, ix]) - m.y0, shape[1])
            seed[t[0], lo:hi, t[2]] = True
    reach = open_ & seed
    while True:
        nb = reach.copy()
        nb[1:] |= reach[:-1]
        nb[:-1] |= reach[1:]
        nb[:, 1:] |= reach[:, :-1]
        nb[:, :-1] |= reach[:, 1:]
        nb[:, :, 1:] |= reach[:, :, :-1]
        nb[:, :, :-1] |= reach[:, :, 1:]
        nb &= open_
        if (nb == reach).all():
            return reach
        reach = nb


def cmd_check(a):
    """Read the saved world: every spawnable position in scope (from the world's own blocks) at block light 0."""
    import build_audit as BA
    if "cobblers-10240" in Path(a.world).as_posix():
        raise SystemExit("refusing to read the live world")
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    w = BA.World(a.world)
    bad = 0
    dump = []
    for sid in a.settlements:
        m, scope, cells, _ = build_model(sid, doc, os.environ.get("COBBLERS_SOURCE_ROOT") or a.source_root, a.server_dir)
        cache = {}
        n = dark_n = 0
        examples = []
        cavern = bool(scope.all())                       # build_model scopes the whole cavern, a town only its roofs
        idx = np.argwhere(scope.any(axis=1))
        cols = {}
        for i, k in idx:
            x, z = m.x0 + int(i), m.z0 + int(k)
            cols[(x, z)] = [w.block(x, y, z) for y in range(m.y0, m.y1 + 9)]
        reach = connected_air(m, cols) if cavern else None
        for (x, z), col in cols.items():
            for y in range(m.y0 + 1, m.y1 - 1):
                prev, a1, a2 = col[y - 1 - m.y0], col[y - m.y0], col[y + 1 - m.y0]
                if not (spawn_surface(prev) and short(a1) in ("air", "cave_air") and short(a2) in ("air", "cave_air")):
                    continue
                # the same scope the plan used, judged on the world's own blocks: in the cavern every position the
                # cavern's own air reaches (a natural cave sealed off in the rock round it is not the cavern); in a
                # surface town only a position with a roof or a ceiling within 8 blocks over it (open sky is not in
                # scope: outdoors at night monsters spawn wherever lamps do not reach, as in any town)
                if cavern and not reach[x - m.x0, y - m.y0, z - m.z0]:
                    continue
                if not cavern and not any(not see_through(b) and short(b) not in ("air", "cave_air", "void_air")
                                          for b in col[y + 1 - m.y0:y + 9 - m.y0]):
                    continue
                n += 1
                if world_light(a.world, x, y, z, cache) == 0:
                    dark_n += 1
                    dump.append((sid, x, y, z, short(prev)))
                    if len(examples) < 8:
                        examples.append((x, y, z, short(prev)))
        bad += dark_n
        print("%-16s %6d spawnable positions in scope, %d at block light 0%s" % (sid, n, dark_n, "  e.g. %s" % examples if dark_n else ""))
    if a.dump:
        Path(a.dump).write_text(json.dumps(dump) + "\n", encoding="utf-8")
    return 1 if bad else 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "check"):
        q = sub.add_parser(name)
        q.add_argument("settlements", nargs="+")
        q.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
        q.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_ROOT"))
        if name == "check":
            q.add_argument("--world", required=True)
            q.add_argument("--dump", help="write every dark position to this JSON file")
    a = p.parse_args(argv)
    return {"plan": cmd_plan, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
