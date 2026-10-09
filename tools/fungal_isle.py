#!/usr/bin/env python
"""The Fungal Isle ("Mushroom Island") grown over: giant and small mushrooms, stumps with shelf fungi, fallen logs,
podzol and moss, and three glades with a Pokemon nest each, from data/fungal_isle.json.

The owner, 2026-10-09: "MUSHROOM ISLAND: foliage and life. It is empty." The island (data/regions.json fungal_isle,
0.77 km2, cell F1) was painted minecraft:mushroom_fields over mycelium with a 4% plant layer of single red and brown
mushrooms: no tree, no cap, no stump, no pool, and its water table (Tadbulb, Dewpider) with no water to spawn in. The
rosters (data/spawns.json fungal_north, fungal_south) are full; what was missing was the island itself and life that
stays where a player can see it. Rungs, in CLAUDE.md principle 6's order:

  foliage      NOT data/foliage.json: that file feeds the WorldPainter export, the world is already exported, and a type
               added there would reach only a future re-export (and move the canopy hash data/visibility.json was
               measured on). The live world gets blocks through a re-apply step, so this tool owns the growth, and
               reuses tools/foliage.py's density helpers (noise(), Spacing) rather than a second copy of them.
  glades       three authored places, each different: the Cap Wood (a 30-block beacon cap ringed by elders), the Stump
               Court (a bare sparring floor of cut stumps with shelf fungi) and the Glowcap Hollow (a sunken bowl with a
               pool and froglight-capped stems).
  the nests    NOT in this pack: three ACTIVATED Habitat Blocks and their pools, records this tool writes into
               data/habitat_blocks.json and data/spawns.json (`records --write`), placed by tools/habitat_blocks.py with
               every other block (R9E). An activated block keeps up to max_spawns of its pool alive within its range,
               which is what "life you can see" needs (the Ursaluna's Teddiursa outskirts, the Old Orchard's Applin).
               The Glowcap Hollow's keepers are the one group above the island's catchable band.
  idle         Pokemon that are simply there, as the towns have them (tools/ambient_idle.py), are NOT built: that is a
               town model needing derived/ plans, and the only wild-site seam is a place module exposing idlers()
               (tools/pokemon_farm.py). Not exercised here, so not touched.

Every Y is round(ground) from tools/ground.py. Paint is `fill ... replace minecraft:mycelium` over a slab, so it follows
a slope without being told the height. Nothing is read from a world.

OUR LIST IS NOT THE WORLD. The keep_clear list is derived from the records of what stands on the island (the fairy ring,
the Zapdos tower, the Newmoon island), and the authored-points sweep (tools/southern_residents.py authored_points) covers
every other x/z any data/*.json authors, with the files it ignores named in the data and why. It does not see what a
donor template or a mod placed that no data file mentions, nor anything a player built.

  python tools/fungal_isle.py build   [--out DIR]        write build/datapacks/cobblers_fungal_isle
  python tools/fungal_isle.py report                      counts, boxes, commands, checks; nothing written
  python tools/fungal_isle.py records [--write]           the Habitat Block and pool records
  python tools/fungal_isle.py probes  [--write]           presence probes into data/world_probes.json

The re-application (tools/reapply.py): placement_steps() is R9FI, with the other block passes BEFORE R9E.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "fungal_isle.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_fungal_isle"
HABITATS = ROOT / "data" / "habitat_blocks.json"
SPAWNS = ROOT / "data" / "spawns.json"
PROBES = ROOT / "data" / "world_probes.json"
SCHEMA = "cobblers.fungal-isle/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()

CELL = 4                                  # the raster's cell, blocks (tools/foliage.py's grid)
X0, X1, Z0, Z1 = 0, 1008, 5200, 6272      # the raster's extent: the island's bounds with a margin
NX, NZ = (X1 - X0) // CELL, (Z1 - Z0) // CELL
RED, BROWN, STEM = "minecraft:red_mushroom_block", "minecraft:brown_mushroom_block", "minecraft:mushroom_stem"
LOG, STRIPPED = "minecraft:dark_oak_log", "minecraft:stripped_dark_oak_log"


class FungalError(SystemExit):
    pass


def jload(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise FungalError("%s: schema must be %s" % (path, SCHEMA))
    ids = [g["id"] for g in doc["glades"]]
    if len(ids) != len(set(ids)):
        raise FungalError("glade ids must be unique")
    nid = [n["id"] for n in doc["nests"]]
    if sorted(nid) != sorted(ids):
        raise FungalError("one nest per glade: glades %s, nests %s" % (sorted(ids), sorted(nid)))
    return doc


def base(state):
    return state.split("[")[0].split("{")[0]


def h32(*parts):
    return int.from_bytes(hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()[:4], "big")


def frac(*parts):
    return h32(*parts) / 4294967296.0


def pick(palette, *parts):
    total = sum(w for _b, w in palette)
    k = h32(*parts) % total
    for b, w in palette:
        if k < w:
            return b
        k -= w
    return palette[-1][0]


# ------------------------------------------------------------------ the terrain raster


class Terrain:
    """The island on a 4-block raster: rounded ground, the island mask, slope, the coast and what is allowed. All from the
    canonical heightmap (tools/ground.py) and data/regions.json; a world is never read."""

    def __init__(self, g, doc):
        self.g = g
        self.doc = doc
        rules = doc["rules"]
        self.sea = int(jload("world.json")["vertical"]["sea_level"])
        xs = X0 + CELL * np.arange(NX)
        zs = Z0 + CELL * np.arange(NZ)
        self.H = np.array(g.heights[Z0 - g.oz:Z1 - g.oz:CELL, X0 - g.ox:X1 - g.ox:CELL], float)
        self.Hr = np.round(self.H).astype(int)
        self.xs, self.zs = xs, zs
        self.inside = self._inside()
        gy, gx = np.gradient(self.H, CELL)
        self.slope = np.degrees(np.arctan(np.hypot(gx, gy)))
        coast = ~self.inside | (self.Hr <= self.sea + 2)
        self.near_coast = dilate(coast, int(math.ceil(rules["shore_clear"] / CELL)))
        self.ok = self.inside & (self.Hr >= rules["min_ground"]) & ~self.near_coast & (self.slope <= rules["max_slope_deg"])

    def _inside(self):
        from PIL import Image, ImageDraw
        reg = [r for r in jload("regions.json")["regions"] if r["id"] == self.doc["island"]["region"]]
        if len(reg) != 1:
            raise FungalError("data/regions.json has no region %s" % self.doc["island"]["region"])
        polys = reg[0].get("polygons")
        if not polys:      # the region record carries no polygons: its sub-regions' are the island
            polys = [p for s in jload("regions.json")["subregions"] if s.get("parent") == reg[0]["id"] for p in s["polygons"]]
        img = np.zeros((NZ, NX), bool)
        for ring in polys:
            im = Image.new("L", (NX, NZ), 0)
            ImageDraw.Draw(im).polygon([((x - X0) / CELL, (z - Z0) / CELL) for x, z in ring], fill=1)
            img ^= np.asarray(im, bool)
        return img

    def cell(self, x, z):
        return (int(z) - Z0) // CELL, (int(x) - X0) // CELL

    def column_ok(self, x, z):
        """The terrain rules for one block column: inside the island, dry ground above min_ground, off the coast, not steep."""
        j, i = self.cell(x, z)
        return 0 <= j < NZ and 0 <= i < NX and bool(self.ok[j, i])


def shift(mask, dz, dx):
    """mask moved by (dz, dx) cells, False filling the edge."""
    out = np.zeros_like(mask)
    zs0, zs1 = max(0, dz), NZ + min(0, dz)
    xs0, xs1 = max(0, dx), NX + min(0, dx)
    out[zs0:zs1, xs0:xs1] = mask[zs0 - dz:zs1 - dz, xs0 - dx:xs1 - dx]
    return out


def dilate(mask, r):
    out = mask.copy()
    for dz in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dz * dz <= r * r + r:
                out |= shift(mask, dz, dx)
    return out



# ------------------------------------------------------------------ keep-clear regions, from the records of the things


def keep_clear(doc):
    """[(id, kind, geometry, margin, giants_only)] derived from the files that place the things, never from the data's own
    copy of a number: the ring from southern_residents.json, the tower and the Newmoon island from placements.json."""
    out = []
    for e in doc["rules"]["keep_clear"]:
        if e["id"] == "fairy_ring":
            r = [x for x in jload("southern_residents.json")["residents"] if x["id"] == "fairy_ring"][0]
            cx, cz = r["site"]["centre"]
            reach = max(max(abs(b[0]), abs(b[2])) for p in r["pieces"] if p["kind"] == "ground_blocks" for b in p["blocks"])
            ring = max(p["r"] for p in r["pieces"] if p["kind"] == "ring")
            out.append((e["id"], "circle", (cx, cz, max(reach, ring + 1) + 1), e["margin"], False))
        else:
            pid = e["source"].split()[-1]
            p = [x for x in jload("placements.json")["placements"] if x["id"] == pid]
            if len(p) != 1:
                raise FungalError("data/placements.json has no placement %s" % pid)
            pos, size = p[0]["position"], p[0]["size"] if "size" in p[0] else None
            if size is None:
                size = {"legendary_zapdos_tower": [31, 66, 29], "legendary_newmoon_island": [101, 58, 100]}[pid]
            out.append((e["id"], "box", (pos["x"], pos["z"], pos["x"] + size[0] - 1, pos["z"] + size[2] - 1, pos["y"]),
                        e["margin"], bool(e.get("giants_only"))))
    return out


def clear_mask(items, include_giants_only):
    """True where a keep_clear region (grown by its margin) covers a raster cell centre."""
    zz, xx = np.meshgrid(Z0 + CELL * np.arange(NZ) + CELL / 2.0, X0 + CELL * np.arange(NX) + CELL / 2.0, indexing="ij")
    m = np.zeros((NZ, NX), bool)
    for _id, kind, geo, margin, giants_only in items:
        if giants_only and not include_giants_only:
            continue
        if kind == "circle":
            cx, cz, r = geo
            m |= np.hypot(xx - cx, zz - cz) <= r + margin
        else:
            x0, z0, x1, z1 = geo[:4]
            m |= (xx >= x0 - margin) & (xx <= x1 + margin + 1) & (zz >= z0 - margin) & (zz <= z1 + margin + 1)
    return m


# ------------------------------------------------------------------ objects and the plan


class Obj:
    """One thing the pack builds: everything it writes, by layer, and the function (tile or glade) that runs it."""

    def __init__(self, oid, kind, ax, az, fn):
        self.id, self.kind, self.ax, self.az, self.fn = oid, kind, ax, az, fn
        self.carve = []        # (x0, y0, z0, x1, y1, z1): fill air
        self.clears = []       # (x0, y0, z0, x1, y1, z1, filter): fill air replace <filter>
        self.paints = []       # (x0, ymin, z0, x1, ymax, z1, block): fill ... replace minecraft:mycelium
        self.floor = {}        # (x, y, z) -> state: explicit ground blocks, before the structure
        self.water = {}        # (x, y, z) -> "minecraft:water"
        self.solid = {}        # (x, y, z) -> state: the structure
        self.hung = {}         # (x, y, z) -> state: what hangs on it (lights, brackets), after the structure
        self.meta = {}


class Plan:
    def __init__(self, doc, g, T):
        self.doc, self.g, self.T = doc, g, T
        self.objs = []
        self.fns = {}          # function name -> [Obj]
        self.claimed = {}      # (x, y, z) -> object id, for every block the plan puts anywhere
        self.allowed = set(doc["blocks"]["ids"])
        self.wards = {}
        self.written_cols = set()

    def new(self, oid, kind, ax, az, fn):
        o = Obj(oid, kind, ax, az, fn)
        self.objs.append(o)
        self.fns.setdefault(fn, []).append(o)
        return o

    def put(self, o, layer, x, y, z, state):
        b = base(state)
        if b not in self.allowed:
            raise FungalError("%s: %s is not in data/fungal_isle.json blocks.ids" % (o.id, b))
        k = (x, y, z)
        prev = self.claimed.get(k)
        if prev is not None and prev != (o.id, layer, state):
            raise FungalError("%s: (%d, %d, %d) is already written by %s (%s %s)" % (o.id, x, y, z, prev[0], prev[1], prev[2]))
        self.claimed[k] = (o.id, layer, state)
        getattr(o, layer)[k] = state
        self.written_cols.add((x, z))

    def ground_runs(self, o, x0, x1, z, block):
        ys = [self.g(x, z) for x in range(x0, x1 + 1)]
        o.paints.append((x0, min(ys), z, x1, max(ys), z, block))
        for x in range(x0, x1 + 1):
            self.written_cols.add((x, z))

    def paint_disc(self, o, cx, cz, r_in, r_out, block):
        """Rows of a disc (or annulus) painted: one fill per run, replacing mycelium whatever the ground's height is."""
        R = int(math.ceil(r_out)) + 1
        for dz in range(-R, R + 1):
            xs = [dx for dx in range(-R, R + 1)
                  if dx * dx + dz * dz <= r_out * r_out and (r_in <= 0 or dx * dx + dz * dz > r_in * r_in)]
            if not xs:
                continue
            s0 = p = xs[0]
            for dx in xs[1:]:
                if dx == p + 1:
                    p = dx
                    continue
                self.ground_runs(o, cx + s0, cx + p, cz + dz, block)
                s0 = p = dx
            self.ground_runs(o, cx + s0, cx + p, cz + dz, block)


# ---------------------------------------------------------------- shapes


def _disc(r):
    out = []
    ri = int(math.ceil(r))
    for dx in range(-ri, ri + 1):
        for dz in range(-ri, ri + 1):
            if dx * dx + dz * dz <= r * r + 0.5:
                out.append((dx, dz))
    return out


def dome_cap(r, ch, thick, state, spot, seed):
    """The cap of a red or brown dome as {(dx, dy, dz): state}: a hollow half-ellipsoid shell on a full base plate at dy 0;
    the top is spotted with stem-white blocks where `spot` is set."""
    out = {}
    ri = max(r - thick, 0.5)
    chi = max(ch - thick, 0.5)
    R = int(math.ceil(r))
    for dx in range(-R, R + 1):
        for dz in range(-R, R + 1):
            d2 = dx * dx + dz * dz
            for dy in range(0, int(ch) + 1):
                e = d2 / (r * r) + dy * dy / (ch * ch)
                if e > 1.0 + 1e-9:
                    continue
                ein = d2 / (ri * ri) + dy * dy / (chi * chi)
                if dy == 0 or ein > 1.0:
                    out[(dx, dy, dz)] = state
    if spot:
        top = {}
        for (dx, dy, dz) in out:
            if (dx, dz) not in top or dy > top[(dx, dz)]:
                top[(dx, dz)] = dy
        for (dx, dz), dy in top.items():
            if dy >= 1 and h32(seed, "spot", dx, dz) % 6 == 0:
                out[(dx, dy, dz)] = STEM
    return out


def umbrella_cap(r, state, droop=True):
    """A flat brown cap: the plate at dy 0, a drooping skirt at dy -1, a shoulder at dy 1 and a button at dy 2 for big ones."""
    out = {}
    for dx, dz in _disc(r):
        out[(dx, 0, dz)] = state
    if r >= 4:
        for dx, dz in _disc(r - 1.6):
            out[(dx, 1, dz)] = state
        if r >= 6:
            for dx, dz in _disc(r * 0.4):
                out[(dx, 2, dz)] = state
        if droop:
            for dx, dz in _disc(r):
                if dx * dx + dz * dz > (r - 1.4) ** 2:
                    out[(dx, -1, dz)] = state
    return out


STEMS = {
    "1": [(0, 0)],
    "plus": [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)],
    "3x3": [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1)],
}


def mushroom(plan, o, ax, az, kind, H, r, seed, stem=None, lean=(0, 0), lamps=0, lamp_ring=0.0):
    """A giant or medium mushroom: its stem columns each from their own ground to the plate, then the cap. Returns the top y
    and the cap radius. `lean` shifts the cap sideways (the audience's); `lamps` hangs shroomlight under the cap."""
    g = plan.g
    B = g(ax, az)
    if stem is None:
        stem = "3x3" if r >= 11 else ("plus" if r >= 7 else "1")
    ty = B + H                                   # the plate's y
    for sx, sz in STEMS[stem]:
        for y in range(g(ax + sx, az + sz) + 1, ty):
            plan.put(o, "solid", ax + sx, y, az + sz, STEM)
    cap = {}
    if kind == "dome":
        ch = max(2, int(round(r * 0.72)))
        cap = dome_cap(r, ch, 1.45, RED, True, seed)
    elif kind == "umbrella":
        cap = umbrella_cap(r, BROWN)
    elif kind == "tiered":
        tiers = [(r, 0, RED), (r * 0.68, 4, BROWN), (r * 0.42, 8, RED)]
        for tr, dy, st in tiers:
            for (dx, ddy, dz), v in umbrella_cap(tr, st, droop=True).items():
                cap[(dx, dy + ddy, dz)] = v
        # the stem climbs through the upper tiers
        for sy in range(1, 8):
            if (0, sy, 0) not in cap:
                plan.put(o, "solid", ax, ty + sy, az, STEM)
    top = ty
    lx, lz = lean
    for (dx, dy, dz), v in cap.items():
        plan.put(o, "solid", ax + lx + dx, ty + dy, az + lz + dz, v)
        top = max(top, ty + dy)
    if lamps:
        for k in range(lamps):
            a = 2 * math.pi * (k + 0.5) / lamps
            lx2, lz2 = ax + lx + int(round(lamp_ring * math.sin(a))), az + lz + int(round(-lamp_ring * math.cos(a)))
            plan.put(o, "hung", lx2, ty - 1, lz2, "minecraft:shroomlight")
    o.meta.update({"stem_base": (ax, B + 1, az), "plate_y": ty, "top_y": top, "radius": r, "kind": kind})
    return top


def stump(plan, o, ax, az, wide, height, seed):
    g = plan.g
    cols = [(0, 0), (1, 0), (0, 1), (1, 1)] if wide else [(0, 0)]
    B = max(g(ax + a, az + b) for a, b in cols)
    for a, b in cols:
        for y in range(g(ax + a, az + b) + 1, B + height):
            plan.put(o, "solid", ax + a, y, az + b, LOG)
        plan.put(o, "solid", ax + a, B + height, az + b, STRIPPED)
    nb = {(a + da, b + db) for a, b in cols for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1))} - set(cols)
    nb = sorted(nb)
    nbr = 1 + h32(seed, "nb") % 3
    for k in range(nbr):
        a, b = nb[h32(seed, "bk", k) % len(nb)]
        y = B + 1 + h32(seed, "by", k) % max(1, height)
        if g(ax + a, az + b) < y:
            st = BROWN if h32(seed, "bc", k) % 3 else RED
            if (ax + a, y, az + b) not in plan.claimed:
                plan.put(o, "hung", ax + a, y, az + b, st)
    o.meta.update({"stem_base": (ax, B + 1, az), "top_y": B + height})


def fallen_log(plan, o, ax, az, length, seed):
    g = plan.g
    axis = "x" if h32(seed, "axis") % 2 else "z"
    for k in range(length):
        x, z = (ax + k, az) if axis == "x" else (ax, az + k)
        y = g(x, z) + 1
        plan.put(o, "solid", x, y, z, "minecraft:dark_oak_log[axis=%s]" % axis)
        if h32(seed, "moss", k) % 5 < 2:
            plan.put(o, "hung", x, y + 1, z, "minecraft:moss_carpet")
    k = h32(seed, "br") % length
    x, z = (ax + k, az + 1) if axis == "x" else (ax + 1, az + k)
    y = g(x, z) + 1
    if (x, y, z) not in plan.claimed:
        plan.put(o, "hung", x, y, z, BROWN if h32(seed, "brc") % 2 else RED)
    o.meta.update({"stem_base": (ax, g(ax, az) + 1, az), "top_y": g(ax, az) + 2})


def tuft(plan, o, ax, az, count, radius, seed):
    g = plan.g
    seen = set()
    for k in range(count):
        a = 2 * math.pi * frac(seed, "a", k)
        d = radius * math.sqrt(frac(seed, "d", k))
        x, z = ax + int(round(d * math.cos(a))), az + int(round(d * math.sin(a)))
        if (x, z) in seen:
            continue
        seen.add((x, z))
        y = g(x, z)
        if (x, y, z) in plan.claimed or (x, y + 1, z) in plan.claimed:
            continue                            # a neighbouring tuft's column: one writer per block
        plan.put(o, "floor", x, y, z, "minecraft:podzol")
        plan.put(o, "solid", x, y + 1, z, "minecraft:red_mushroom" if h32(seed, "c", k) % 2 else "minecraft:brown_mushroom")
    o.meta.update({"stem_base": (ax, g(ax, az) + 1, az), "top_y": g(ax, az) + 1})


# ------------------------------------------------------------------ the scatter


def scatter_density(doc):
    import foliage as F
    sc = doc["scatter"]
    n = max(NX, NZ)
    seed = sc["seed"]
    clump = F.noise(n, sc["clump_scale"], seed)[:NZ, :NX]
    glade = F.noise(n, sc["glade_scale"], seed + 1)[:NZ, :NX]
    return clump, glade


def edge_factor(T, doc):
    """0 at the coast ramping to 1 inland: the distance, in cells, from the nearest cell that is not island above the sea."""
    lo, hi = doc["scatter"]["edge_ramp"]
    sea = ~T.inside | (T.Hr <= T.sea + 2)
    d = np.zeros((NZ, NX), np.float32)
    cur = sea.copy()
    for k in range(1, int(math.ceil(hi / CELL)) + 1):
        grown = dilate(cur, 1)
        d[grown & ~cur] = k * CELL
        cur = grown
    d[~cur] = hi
    d[sea] = 0
    t = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


def build_scatter(plan, glade_discs):
    import foliage as F
    doc, T = plan.doc, plan.T
    sc = doc["scatter"]
    clump, glade = scatter_density(doc)
    ed = edge_factor(T, doc)
    dens = (sc["base_density"] + (1 - sc["base_density"]) * np.clip(clump * 1.3, 0, 1)) * (glade > sc["glade_share"]) * ed
    kc = keep_clear(doc)
    zz, xx = np.meshgrid(Z0 + CELL * np.arange(NZ) + CELL / 2.0, X0 + CELL * np.arange(NX) + CELL / 2.0, indexing="ij")
    glade_block = np.zeros((NZ, NX), bool)
    margin = doc["rules"]["glade_scatter_margin"]
    for cx, cz, r in glade_discs:
        glade_block |= np.hypot(xx - cx, zz - cz) <= r + margin
    rng = np.random.default_rng(sc["seed"])
    sp = F.Spacing(cell=8)
    for o in plan.objs:                                   # the glades' own stems keep their spacing from the scatter
        if o.meta.get("stem_base"):
            sp.add(o.meta["stem_base"][0], o.meta["stem_base"][2], 6)
    counts = {}
    order = [("giants", True), ("mediums", False), ("stumps", False), ("logs", False), ("tufts", False)]
    for name, is_giant in order:
        p = sc[name]
        bad = ~T.ok | glade_block | clear_mask(kc, is_giant)
        bad = dilate(bad, int(math.ceil((p["clear_radius"] + 1) / CELL)))
        k = int(math.ceil((doc["rules"]["map_margin"] + p["clear_radius"]) / CELL)) + 1
        bad[:, :k] = True
        bad[:, -k:] = True
        bad[:k, :] = True
        bad[-k:, :] = True
        P = p["per_ha"] * dens * (CELL * CELL / 10000.0)
        u = rng.random((NZ, NX))
        cand = np.argwhere((u < P) & ~bad)
        cand = cand[rng.permutation(len(cand))]
        n = 0
        for j, i in cand:
            x = X0 + CELL * int(i) + int(rng.integers(0, CELL))
            z = Z0 + CELL * int(j) + int(rng.integers(0, CELL))
            if not sp.ok(x, z, p["spacing"], 30):
                continue
            oid = "%s_%03d" % (name[:-1] if name != "tufts" else "tuft", n)
            seed = h32(sc["seed"], name, x, z)
            tile = (x // doc["build"]["tile"], z // doc["build"]["tile"])
            o = plan.new(oid, name, x, z, "t_%d_%d" % tile)
            if name in ("giants", "mediums"):
                kinds = p["kinds"]
                kind = pick(list(kinds.items()), seed, "kind")
                H = p["height"][0] + h32(seed, "H") % (p["height"][1] - p["height"][0] + 1)
                r = round(p["radius"][0] + (p["radius"][1] - p["radius"][0]) * frac(seed, "r"), 1)
                mushroom(plan, o, x, z, kind, H, r, seed)
                if name == "giants":
                    pr = r + 1
                    plan.paint_disc(o, x, z, 0, pr, "minecraft:podzol")
                    plan.paint_disc(o, x, z, pr, pr + 2.5, "minecraft:moss_block")
            elif name == "stumps":
                stump(plan, o, x, z, frac(seed, "w") < p["wide_share"], p["height"][0] + h32(seed, "h") % (p["height"][1] - p["height"][0] + 1), seed)
            elif name == "logs":
                fallen_log(plan, o, x, z, p["length"][0] + h32(seed, "L") % (p["length"][1] - p["length"][0] + 1), seed)
            else:
                tuft(plan, o, x, z, p["count"][0] + h32(seed, "n") % (p["count"][1] - p["count"][0] + 1), p["radius"], seed)
            sp.add(x, z, p["spacing"])
            n += 1
        counts[name] = n
    return counts


# ------------------------------------------------------------------ the glades


def _glade(doc, gid):
    return [x for x in doc["glades"] if x["id"] == gid][0]


def build_cap_wood(plan):
    doc, g = plan.doc, plan.g
    gl = _glade(doc, "cap_wood")
    cx, cz = gl["centre"]
    P = gl["pieces"]
    fn = "cap_wood"
    seed = h32(doc["scatter"]["seed"], "cap_wood")
    b = P["beacon"]
    o = plan.new("cap_wood_beacon", "beacon", cx, cz, fn)
    mushroom(plan, o, cx, cz, "dome", b["height"], b["cap_radius"], seed, stem="3x3", lamps=b["lamps"], lamp_ring=b["lamp_ring"])
    plan.wards["cap_wood"] = (cx, g(cx, cz) + 2, cz)
    plan.paint_disc(o, cx, cz, 0, P["floor"]["podzol_radius"], "minecraft:podzol")
    # moss in ragged 8-block cells out to the wood's edge, thinning with distance
    R = gl["radius"]
    for ci in range(-R // 8 - 1, R // 8 + 2):
        for cj in range(-R // 8 - 1, R // 8 + 2):
            x0, z0 = cx + ci * 8, cz + cj * 8
            d = math.hypot(x0 + 4 - cx, z0 + 4 - cz)
            if d <= P["floor"]["podzol_radius"] or d > R:
                continue
            if frac(seed, "moss", ci, cj) < P["floor"]["moss_noise_share"] * (1 - d / R):
                for z in range(z0, z0 + 8):
                    plan.ground_runs(o, x0, x0 + 7, z, "minecraft:moss_block")
    placed = [(cx, cz, 18.0)]
    el = P["elders"]
    for k in range(el["count"]):
        a = 2 * math.pi * (k + 0.5 * frac(seed, "ea", k)) / el["count"]
        x, z = cx + int(round(el["ring"] * math.sin(a))), cz + int(round(-el["ring"] * math.cos(a)))
        e = plan.new("cap_wood_elder_%d" % k, "elder", x, z, fn)
        H = el["height"][0] + h32(seed, "eh", k) % (el["height"][1] - el["height"][0] + 1)
        r = round(el["radius"][0] + (el["radius"][1] - el["radius"][0]) * frac(seed, "er", k), 1)
        mushroom(plan, e, x, z, "dome" if k % 2 == 0 else "umbrella", H, r, h32(seed, "el", k))
        plan.paint_disc(e, x, z, 0, r + 1, "minecraft:podzol")
        placed.append((x, z, r + 3.0))
    w = P["wood"]
    tries = 0
    n = 0
    rng = np.random.default_rng(h32(seed, "wood"))
    while n < w["count"] and tries < 4000:
        tries += 1
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(w["inner"], w["outer"])
        x, z = cx + int(round(d * math.sin(a))), cz + int(round(-d * math.cos(a)))
        r = round(w["radius"][0] + (w["radius"][1] - w["radius"][0]) * rng.random(), 1)
        if any(math.hypot(x - px, z - pz) < max(w["min_spacing"], pr + r + 2) for px, pz, pr in placed):
            continue
        if not plan.T.column_ok(x, z):
            continue
        H = w["height"][0] + int(rng.integers(0, w["height"][1] - w["height"][0] + 1))
        kind = ("dome", "umbrella", "tiered")[int(rng.integers(0, 3))]
        t = plan.new("cap_wood_wood_%d" % n, "wood", x, z, fn)
        mushroom(plan, t, x, z, kind, H, r, h32(seed, "w", n))
        plan.paint_disc(t, x, z, 0, r + 1, "minecraft:podzol")
        plan.paint_disc(t, x, z, r + 1, r + 3.5, "minecraft:moss_block")
        placed.append((x, z, r + 3.0))
        n += 1
    u = P["understory"]
    for k in range(u["count"]):
        a = 2 * math.pi * (k + 0.5) / u["count"] + 0.3 * frac(seed, "ua", k)
        d = u["ring"][0] + (u["ring"][1] - u["ring"][0]) * frac(seed, "ud", k)
        x, z = cx + int(round(d * math.sin(a))), cz + int(round(-d * math.cos(a)))
        m = plan.new("cap_wood_under_%d" % k, "under", x, z, fn)
        mushroom(plan, m, x, z, "dome" if k % 2 else "umbrella", 4 + h32(seed, "uh", k) % 4, round(2.2 + 1.4 * frac(seed, "ur", k), 1), h32(seed, "u", k))
    return {"id": "cap_wood", "centre": (cx, cz), "radius": gl["radius"], "fn": fn}


def build_stump_court(plan):
    doc, g = plan.doc, plan.g
    gl = _glade(doc, "stump_court")
    cx, cz = gl["centre"]
    P = gl["pieces"]
    fn = "stump_court"
    seed = h32(doc["scatter"]["seed"], "stump_court")
    f = P["floor"]
    o = plan.new("stump_court_floor", "floor", cx, cz, fn)
    pr = f["radius"]
    # a trodden floor: small mushrooms cleared off, then 4-block cells of a coarse, bare palette
    for dz in range(-pr, pr + 1):
        half = int(math.sqrt(max(pr * pr - dz * dz, 0)))
        ys = [g(cx + dx, cz + dz) for dx in range(-half, half + 1)]
        for st in ("minecraft:red_mushroom", "minecraft:brown_mushroom"):
            o.clears.append((cx - half, min(ys) + 1, cz + dz, cx + half, max(ys) + 1, cz + dz, st))
    for ci in range(-pr // 4 - 1, pr // 4 + 2):
        for cj in range(-pr // 4 - 1, pr // 4 + 2):
            x0, z0 = cx + ci * 4, cz + cj * 4
            if math.hypot(x0 + 2 - cx, z0 + 2 - cz) > pr - 1.5:
                continue
            blk = pick(f["palette"], seed, "fl", ci, cj)
            for z in range(z0, z0 + 4):
                plan.ground_runs(o, x0, x0 + 3, z, blk)
    gs = P["great_stump"]
    s = plan.new("stump_court_great_stump", "great_stump", cx, cz, fn)
    B = max(g(cx + dx, cz + dz) for dx, dz in _disc(gs["radius"]))
    for dx, dz in _disc(gs["radius"]):
        for y in range(g(cx + dx, cz + dz) + 1, B + gs["height"]):
            plan.put(s, "solid", cx + dx, y, cz + dz, LOG)
        plan.put(s, "solid", cx + dx, B + gs["height"], cz + dz, STRIPPED)
    # a cut face: the great stump's rim brackets
    disc = set(_disc(gs["radius"]))
    rim = sorted({(a + da, b + db) for a, b in disc for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1))} - disc,
                 key=lambda t: math.atan2(t[1], t[0]))              # the cells face-adjacent to the cut face
    for k in range(gs["brackets"]):
        dx, dz = rim[(k * len(rim)) // gs["brackets"]]
        y = B + 1 + (k % 3)
        if g(cx + dx, cz + dz) < y:
            plan.put(s, "hung", cx + dx, y, cz + dz, BROWN if k % 3 else RED)
    s.meta.update({"stem_base": (cx, B + 1, cz), "top_y": B + gs["height"]})
    plan.wards["stump_court"] = (cx, B + 2, cz)
    ring = P["ring"]
    for k in range(ring["count"]):
        a = 2 * math.pi * (k + 0.5 * frac(seed, "ra", k)) / ring["count"]
        x, z = cx + int(round(ring["radius"] * math.sin(a))), cz + int(round(-ring["radius"] * math.cos(a)))
        t = plan.new("stump_court_stump_%d" % k, "stump", x, z, fn)
        stump(plan, t, x, z, k % 4 == 0, ring["height"][0] + h32(seed, "rh", k) % (ring["height"][1] - ring["height"][0] + 1), h32(seed, "rs", k))
    au = P["audience"]
    for k in range(au["count"]):
        a = 2 * math.pi * (k + 0.5 * frac(seed, "aa", k)) / au["count"]
        x, z = cx + int(round(au["ring"] * math.sin(a))), cz + int(round(-au["ring"] * math.cos(a)))
        t = plan.new("stump_court_audience_%d" % k, "audience", x, z, fn)
        H = au["height"][0] + h32(seed, "ah", k) % (au["height"][1] - au["height"][0] + 1)
        r = round(au["radius"][0] + (au["radius"][1] - au["radius"][0]) * frac(seed, "ar", k), 1)
        lean = (int(round(-2 * math.sin(a))), int(round(2 * math.cos(a))))
        mushroom(plan, t, x, z, "umbrella", H, r, h32(seed, "au", k), lean=lean)
        plan.paint_disc(t, x, z, 0, r + 1, "minecraft:podzol")
    bt = P["border_tufts"]
    for k in range(bt["count"]):
        a = 2 * math.pi * (k + 0.5 * frac(seed, "ta", k)) / bt["count"]
        x, z = cx + int(round(bt["ring"] * math.sin(a))), cz + int(round(-bt["ring"] * math.cos(a)))
        t = plan.new("stump_court_tuft_%d" % k, "tuft", x, z, fn)
        tuft(plan, t, x, z, 4, 2.0, h32(seed, "tf", k))
    return {"id": "stump_court", "centre": (cx, cz), "radius": gl["radius"], "fn": fn}


def hollow_profile(P, yc, r):
    """(floor y, pool depth) at radius r from the hollow's middle: flat out to flat_radius, a smoothstep up to the rim."""
    bw, pl = P["bowl"], P["pool"]
    D, flat, R = bw["depth"], bw["flat_radius"], bw["rim_radius"]
    if r >= R:
        return None
    if r <= flat:
        t = yc - D
    else:
        u = (r - flat) / (R - flat)
        t = yc - D + int(round(D * u * u * (3 - 2 * u)))
    extra = 0
    if r <= pl["deep_radius"]:
        extra = pl["deep"]
    elif r <= pl["mid_radius"]:
        extra = pl["mid"]
    elif r <= pl["shallow_radius"]:
        extra = pl["shallow"]
    return t - extra, extra


def build_hollow(plan):
    doc, g = plan.doc, plan.g
    gl = _glade(doc, "glowcap_hollow")
    cx, cz = gl["centre"]
    P = gl["pieces"]
    fn = "glowcap_hollow"
    seed = h32(doc["scatter"]["seed"], "hollow")
    yc = g(cx, cz)
    bw = P["bowl"]
    yw = yc - bw["depth"]                       # the pool's surface
    R = bw["rim_radius"]
    o = plan.new("glowcap_hollow_bowl", "bowl", cx, cz, fn)
    floor_y = {}
    for dx in range(-R - 2, R + 3):
        for dz in range(-R - 2, R + 3):
            r = math.hypot(dx, dz)
            x, z = cx + dx, cz + dz
            gy = g(x, z)
            pr = hollow_profile(P, yc, r)
            if pr is None:
                floor_y[(x, z)] = gy
                continue
            fy, extra = pr
            if extra == 0 and fy >= gy:
                floor_y[(x, z)] = gy          # the ground already lies at or under the profile: untouched
                continue
            floor_y[(x, z)] = min(fy, gy)
    # the cut, the lining and the water
    pool_cols = []
    for (x, z), fy in sorted(floor_y.items()):
        r = math.hypot(x - cx, z - cz)
        gy = g(x, z)
        if fy >= gy and not (r <= P["pool"]["shallow_radius"]):
            continue
        if fy < gy:
            o.carve.append((x, fy + 1, z, x, gy + 2, z))
        in_pool = r <= P["pool"]["shallow_radius"] and fy < yw
        if in_pool:
            top = "minecraft:mud"
            pool_cols.append((x, z))
        else:
            pal = P["floor"]["inner"] if r <= P["floor"]["inner_radius"] else P["floor"]["outer"]
            top = pick(pal, seed, "t", x // 3, z // 3)
        if (x, z) != (cx + 9, cz):
            plan.put(o, "floor", x, fy, z, top)
        else:
            plan.put(o, "floor", x, fy, z, "minecraft:moss_block")
        for k, lin in ((1, "minecraft:dirt"), (2, "minecraft:mud" if in_pool else "minecraft:dirt")):
            if fy - k > 0:
                plan.put(o, "floor", x, fy - k, z, lin)
        if in_pool:
            for y in range(fy + 1, yw + 1):
                plan.put(o, "water", x, y, z, "minecraft:water")
    plan.wards["glowcap_hollow"] = (cx + 9, floor_y[(cx + 9, cz)], cz)
    o.meta.update({"pool_level": yw, "pool_cols": len(pool_cols), "centre_floor": floor_y[(cx, cz)], "yc": yc, "floor_y": floor_y})
    # lamps: stems topped with froglight caps on the slopes, buds round the water
    lamps = P["lamps"]
    light = lamps["light"]
    used = set()
    big = []
    for k in range(lamps["big"]):
        a = 2 * math.pi * (k + 0.5 * frac(seed, "la", k)) / lamps["big"]
        rr = 10 + 7 * frac(seed, "lr", k)
        x, z = cx + int(round(rr * math.sin(a))), cz + int(round(-rr * math.cos(a)))
        big.append((x, z))
    lamp_o = plan.new("glowcap_hollow_lamps", "lamps", cx, cz, fn)
    for k, (x, z) in enumerate(big):
        by = floor_y[(x, z)]
        nbmax = max(floor_y[(x + a, z + b)] for a in (-1, 0, 1) for b in (-1, 0, 1))
        h = 2 + h32(seed, "lh", k) % 3
        cap_y = max(by + h + 1, nbmax + 1)
        if any((x + a, z + b) in used for a in range(-3, 4) for b in range(-3, 4)):
            continue
        used.add((x, z))
        blk = light[k % 2]
        for y in range(by + 1, cap_y):
            plan.put(lamp_o, "solid", x, y, z, STEM)
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                plan.put(lamp_o, "solid", x + a, cap_y, z + b, blk)
        lamp_o.meta.setdefault("big", []).append((x, cap_y, z, blk))
    for k in range(lamps["buds"]):
        a = 2 * math.pi * (k + 0.37 * frac(seed, "ba", k)) / lamps["buds"]
        rr = P["pool"]["shallow_radius"] + 1.5 + 8 * frac(seed, "br", k)
        x, z = cx + int(round(rr * math.sin(a))), cz + int(round(-rr * math.cos(a)))
        if any((x + a2, z + b2) in used for a2 in range(-2, 3) for b2 in range(-2, 3)):
            continue
        by = floor_y[(x, z)]
        used.add((x, z))
        plan.put(lamp_o, "solid", x, by + 1, z, STEM)
        plan.put(lamp_o, "solid", x, by + 2, z, light[k % 2])
        lamp_o.meta.setdefault("buds", []).append((x, by + 2, z, light[k % 2]))
    rim = P["rim"]
    for k in range(rim["count"]):
        a = 2 * math.pi * (k + 0.5 * frac(seed, "ra", k)) / rim["count"]
        x, z = cx + int(round(rim["ring"] * math.sin(a))), cz + int(round(-rim["ring"] * math.cos(a)))
        t = plan.new("glowcap_hollow_rim_%d" % k, "rim", x, z, fn)
        H = rim["height"][0] + h32(seed, "rh", k) % (rim["height"][1] - rim["height"][0] + 1)
        r = round(rim["radius"][0] + (rim["radius"][1] - rim["radius"][0]) * frac(seed, "rr", k), 1)
        mushroom(plan, t, x, z, "dome" if k % 2 else "umbrella", H, r, h32(seed, "rm", k))
        plan.paint_disc(t, x, z, 0, r + 1, "minecraft:podzol")
    return {"id": "glowcap_hollow", "centre": (cx, cz), "radius": gl["radius"], "fn": fn}


# ------------------------------------------------------------------ the plan, its checks and its pack


@functools.lru_cache(maxsize=2)
def _plan_cached(source_root, path):
    """The plan for the committed data and the canonical heightmap, built once per process: reapply.py asks for the steps
    many times in one prepare, and a plan is a few seconds."""
    import ground as G
    g = G.load(source_root)
    doc = load(Path(path))
    return _plan(doc, g, Terrain(g, doc))


def plan(doc=None, g=None, source_root=None, path=DATA):
    if doc is None or g is None:
        return _plan_cached(source_root, str(path))
    return _plan(doc, g, Terrain(g, doc))


def _plan(doc, g, T):
    pl = Plan(doc, g, T)
    discs = []
    for build in (build_cap_wood, build_stump_court, build_hollow):
        r = build(pl)
        discs.append((r["centre"][0], r["centre"][1], r["radius"]))
    pl.glades = discs
    pl.counts = build_scatter(pl, discs)
    return pl


def box_commands(blocks):
    """setblock / fill lines for {(x, y, z): state}: runs along x, then merged along z, then along y."""
    rows = {}
    for (x, y, z), st in blocks.items():
        rows.setdefault((y, z, st), []).append(x)
    runs = []
    for (y, z, st), xs in rows.items():
        xs.sort()
        s = p = xs[0]
        for x in xs[1:]:
            if x == p + 1:
                p = x
                continue
            runs.append((y, st, s, p, z))
            s = p = x
        runs.append((y, st, s, p, z))
    byz = {}
    for y, st, x0, x1, z in runs:
        byz.setdefault((y, st, x0, x1), []).append(z)
    slabs = []
    for (y, st, x0, x1), zs in byz.items():
        zs.sort()
        s = p = zs[0]
        for z in zs[1:]:
            if z == p + 1:
                p = z
                continue
            slabs.append((st, x0, x1, s, p, y))
            s = p = z
        slabs.append((st, x0, x1, s, p, y))
    byy = {}
    for st, x0, x1, z0, z1, y in slabs:
        byy.setdefault((st, x0, x1, z0, z1), []).append(y)
    out = []
    for (st, x0, x1, z0, z1), ys in byy.items():
        ys.sort()
        s = p = ys[0]
        for y in ys[1:]:
            if y == p + 1:
                p = y
                continue
            out.append((s, z0, x0, p, z1, x1, st))
            s = p = y
        out.append((s, z0, x0, p, z1, x1, st))
    out.sort()
    cmds = []
    for y0, z0, x0, y1, z1, x1, st in out:
        if (y0, z0, x0) == (y1, z1, x1):
            cmds.append("setblock %d %d %d %s" % (x0, y0, z0, st))
        else:
            cmds.append("fill %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, st))
    return cmds


def fn_box(objs):
    xs, zs = [], []
    for o in objs:
        for d in (o.floor, o.water, o.solid, o.hung):
            for (x, _y, z) in d:
                xs.append(x)
                zs.append(z)
        for c in o.carve:
            xs += [c[0], c[3]]
            zs += [c[2], c[5]]
        for c in o.clears:
            xs += [c[0], c[3]]
            zs += [c[2], c[5]]
        for c in o.paints:
            xs += [c[0], c[3]]
            zs += [c[2], c[5]]
    return (min(xs), min(zs), max(xs), max(zs))


def fn_lines(name, objs):
    out = ["# Generated by tools/fungal_isle.py from data/fungal_isle.json: %s" % name,
           "# chunks-loaded-by: the re-application R9FI (forceload add %d %d %d %d over RCON before this runs)" % fn_box(objs)]
    cl = [c for o in objs for c in o.clears]
    cv = [c for o in objs for c in o.carve]
    pt = [c for o in objs for c in o.paints]
    if cl:
        out.append("# 1. small mushrooms cleared off the floor")
        for x0, y0, z0, x1, y1, z1, f in sorted(set(cl)):
            out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, f))
    if cv:
        out.append("# 2. the cut")
        for x0, y0, z0, x1, y1, z1 in sorted(set(cv)):
            out.append("fill %d %d %d %d %d %d minecraft:air" % (x0, y0, z0, x1, y1, z1))
    if pt:
        out.append("# 3. paint: mycelium replaced over a slab, whatever the ground's height")
        for x0, ya, z0, x1, yb, z1, blk in sorted(set(pt)):
            out.append("fill %d %d %d %d %d %d %s replace minecraft:mycelium" % (x0, ya, z0, x1, yb, z1, blk))
    for label, layer in (("4. the ground laid", "floor"), ("5. water", "water"), ("6. the structure", "solid"), ("7. what hangs on it", "hung")):
        merged = {}
        for o in objs:
            merged.update(getattr(o, layer))
        if merged:
            out.append("# " + label)
            out += box_commands(merged)
    return out


def functions(pl):
    """{function name: [lines]}, glades first then the scatter tiles, each a function that runs after its forceload."""
    names = ["cap_wood", "stump_court", "glowcap_hollow"] + sorted(n for n in pl.fns if n.startswith("t_"))
    out = {}
    for n in names:
        lines = fn_lines(n, pl.fns[n])
        bad = function_limits.check_lines(lines, "fungal_isle/%s" % n)
        if bad:
            raise FungalError("fungal_isle/%s: %d command(s) the server would refuse: %s" % (n, len(bad), bad[:3]))
        out[n] = lines
    return out


def files(doc=None, g=None, pl=None, check=True):
    pl = pl or plan(doc, g)
    doc = pl.doc
    if check:
        probs = check_plan(pl)
        if probs:
            raise FungalError("fungal_isle: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs[:30])))
    b = doc["build"]
    out = {}
    for n, lines in functions(pl).items():
        out["data/%s/function/%s/%s.mcfunction" % (b["namespace"], b["folder"], n)] = "\n".join(lines) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: the Fungal Isle grown over (tools/fungal_isle.py)"}}, indent=2) + "\n"
    return out, pl


def write(out_files, out=OUT):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ the builder's guards


def all_blocks(pl):
    for o in pl.objs:
        for layer in ("floor", "water", "solid", "hung"):
            for k, v in getattr(o, layer).items():
                yield o, layer, k, v


def policy_whitelist():
    """The spawn-condition blocks data/spawn_block_policy.json lets this place write: an entry whose scope names fungal_isle
    (the scope rule of tests/test_system_contracts.py, contract C4)."""
    return {b for w in jload("spawn_block_policy.json")["whitelist"] if "fungal_isle" in (w.get("scope") or "")
            for b in w.get("blocks") or []}


def check_plan(pl):
    """The builder's guards (not an audit): the terrain rules, the keep-clear regions, the Newmoon ceiling, spawn-condition
    blocks and concrete, support for every small mushroom, the pool's containment and the Habitat Blocks' mimics."""
    doc, T, g = pl.doc, pl.T, pl.g
    rules = doc["rules"]
    probs = []
    glade_fns = {"cap_wood", "stump_court", "glowcap_hollow"}
    spawn = set(jload("spawn_blocks.json")["blocks"])
    written = {base(v) for _o, _l, _k, v in all_blocks(pl)} | {p[6] for o in pl.objs for p in o.paints}
    ok_spawn = policy_whitelist()
    for b in sorted(written & spawn - ok_spawn):
        probs.append("writes %s, a block a spawn condition names (data/spawn_blocks.json) and no data/spawn_block_policy.json "
                     "entry scoped to fungal_isle allows it" % b)
    edge = [(x, z) for (x, z) in pl.written_cols if x < rules["map_margin"]]
    if edge:
        probs.append("%d written column(s) within %d blocks of the map's west edge, e.g. %s" % (len(edge), rules["map_margin"], sorted(edge)[:3]))
    for b in sorted(written):
        if "concrete" in b:
            probs.append("writes %s: no concrete (contract C4)" % b)
        if b not in pl.allowed:
            probs.append("writes %s, not in blocks.ids" % b)
    # terrain: every written column of a scatter object must pass; glades are checked on the same terms except hollow cut
    kc = keep_clear(doc)
    cols = {}
    for o, layer, (x, y, z), v in all_blocks(pl):
        cols.setdefault(o.id, set()).add((x, z))
    for o in pl.objs:
        for p in o.paints:
            for x in range(p[0], p[3] + 1):
                cols.setdefault(o.id, set()).add((x, p[2]))
    bad_t, bad_k = [], []
    for o in pl.objs:
        for (x, z) in cols.get(o.id, ()):
            if not T.column_ok(x, z):
                bad_t.append((o.id, x, z))
            for _id, kind, geo, margin, giants_only in kc:
                if kind == "circle":
                    inside = math.hypot(x - geo[0], z - geo[1]) <= geo[2] + margin
                else:
                    inside = geo[0] - margin <= x <= geo[2] + margin and geo[1] - margin <= z <= geo[3] + margin
                if inside and not (giants_only and o.kind not in ("giants", "beacon", "elder", "wood", "audience", "rim")):
                    bad_k.append((o.id, _id, x, z))
    if bad_t:
        probs.append("%d written column(s) fail the terrain rules (inside the island, ground >= %d, %d from the coast, slope <= %d), e.g. %s"
                     % (len(bad_t), rules["min_ground"], rules["shore_clear"], rules["max_slope_deg"], bad_t[:3]))
    if bad_k:
        probs.append("%d written column(s) inside a keep_clear region, e.g. %s" % (len(bad_k), bad_k[:3]))
    # the Newmoon island: nothing written reaches its ceiling inside the (grown) footprint
    for _id, kind, geo, margin, giants_only in kc:
        if _id != "newmoon_island":
            continue
        hi = [(o.id, x, y, z) for o, _l, (x, y, z), _v in all_blocks(pl)
              if geo[0] - margin <= x <= geo[2] + margin and geo[1] - margin <= z <= geo[3] + margin and y > rules["newmoon_ceiling"]]
        if hi:
            probs.append("%d block(s) above y%d inside the Newmoon island's footprint, e.g. %s" % (len(hi), rules["newmoon_ceiling"], hi[:3]))
    # support: every small mushroom stands on podzol or mycelium written beneath it
    for o, layer, (x, y, z), v in all_blocks(pl):
        if layer == "solid" and base(v) in ("minecraft:red_mushroom", "minecraft:brown_mushroom"):
            below = pl.claimed.get((x, y - 1, z))
            if not below or base(below[2]) not in ("minecraft:podzol", "minecraft:mycelium"):
                probs.append("%s: a small mushroom at (%d, %d, %d) has no podzol or mycelium written under it" % (o.id, x, y, z))
    # the authored-points sweep
    probs += authored_sweep(pl)
    # the hollow
    probs += hollow_checks(pl)
    # the wards
    for n in doc["nests"]:
        w = pl.wards.get(n["glade"])
        if w is None:
            probs.append("nest %s: no ward position" % n["id"])
            continue
        st = pl.claimed.get(tuple(w))
        if st is None or base(st[2]) != n["mimic"]:
            probs.append("nest %s: the ward at %s is %s, the mimic is %s" % (n["id"], w, st and base(st[2]), n["mimic"]))
    # an empty function is a fault
    for name in glade_fns:
        if name not in pl.fns:
            probs.append("glade function %s has no objects" % name)
    # counts
    for name, p in doc["scatter"].items():
        if isinstance(p, dict) and "per_ha" in p and pl.counts.get(name, 0) == 0:
            probs.append("the scatter placed no %s" % name)
    return probs


def clear_mask_points(items):
    """A predicate: is (x, z) inside any keep_clear region grown by its margin? Authored points there are those regions' own."""
    def inside(x, z):
        for _id, kind, geo, margin, _go in items:
            if kind == "circle":
                if math.hypot(x - geo[0], z - geo[1]) <= geo[2] + margin:
                    return True
            elif geo[0] - margin <= x <= geo[2] + margin and geo[1] - margin <= z <= geo[3] + margin:
                return True
        return False
    return inside


def authored_sweep(pl):
    import southern_residents as SR
    doc = pl.doc
    ignore = set(doc["rules"]["authored_clearance_ignore"]) | {DATA.name}
    covered = clear_mask_points(keep_clear(doc))
    mine = {(w[0], w[2]) for w in pl.wards.values()}          # this place's own Habitat Block records
    pts = [(x, z, f) for x, z, f in SR.authored_points({"residents": []}, own_file=DATA)
           if f not in ignore and X0 <= x <= X1 and Z0 <= z <= Z1 and not covered(x, z)
           and not (f == "habitat_blocks.json" and (x, z) in mine)]
    if not pts:
        return []
    P = np.array([(a, b) for a, b, _f in pts], float)
    C = np.array(sorted(pl.written_cols), float)
    m = doc["rules"]["authored_clearance"]
    probs = []
    for i in range(0, len(C), 4096):
        blk = C[i:i + 4096]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(int(np.argmin(d)), d.shape)
        if d[j] < m:
            probs.append("(%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                         % (blk[j[0]][0], blk[j[0]][1], d[j], pts[j[1]][2], m))
            break
    return probs


def hollow_checks(pl):
    """The pool's water cannot escape: every water column's four neighbours are water or a column whose ground holds the
    surface; the water's flood stays inside the rim; and the bowl is the profile the data says."""
    probs = []
    o = [x for x in pl.objs if x.id == "glowcap_hollow_bowl"][0]
    yw = o.meta["pool_level"]
    ff = o.meta["floor_y"]
    water_cols = {(x, z) for (x, y, z) in o.water}
    g = pl.g
    gl = _glade(pl.doc, "glowcap_hollow")
    cx, cz = gl["centre"]
    for (x, z) in water_cols:
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, z + dz)
            if n in water_cols:
                continue
            top = ff.get(n, g(*n))
            if top < yw:
                probs.append("the pool leaks at (%d, %d): the neighbour (%d, %d) has its ground at y%d, under the surface y%d" % (x, z, n[0], n[1], top, yw))
                return probs
    if not water_cols:
        probs.append("the hollow has no water")
    far = max(math.hypot(x - cx, z - cz) for x, z in water_cols) if water_cols else 0
    if far > gl["pieces"]["pool"]["shallow_radius"] + 1.5:
        probs.append("the pool reaches %.1f blocks from the middle, past its shallow radius" % far)
    if o.meta["centre_floor"] > yw - 1:
        probs.append("the pool is not deeper than the surface at the middle")
    return probs


# ------------------------------------------------------------------ the re-application


def placement_steps(doc=None, g=None, pl=None):
    """R9FI, BEFORE R9E: per function hold its box, run it, release it (R9FS's shape)."""
    pl = pl or plan(doc, g)
    b = pl.doc["build"]
    steps = []
    for n in functions_order(pl):
        x0, z0, x1, z1 = fn_box(pl.fns[n])
        hold = "%d %d %d %d" % (x0, z0, x1, z1)
        steps += [("cmd", "forceload add " + hold), ("wait", b["wait_seconds"]),
                  ("fn", "%s:%s/%s" % (b["namespace"], b["folder"], n)), ("cmd", "forceload remove " + hold)]
    return steps


def functions_order(pl):
    return ["cap_wood", "stump_court", "glowcap_hollow"] + sorted(n for n in pl.fns if n.startswith("t_"))


# ------------------------------------------------------------------ the nests' records


def pool_species_positions():
    sd = json.loads(SPAWNS.read_text(encoding="utf-8"))
    pos = {}
    for e in sd["entries"]:
        pos.setdefault(e["species"], e.get("spawnable_position") or "grounded")
    return pos


def records(doc, pl, positions=None):
    """(habitat block records, [pool {habitat, entries}]) this place owns in the shared files."""
    sd = json.loads(SPAWNS.read_text(encoding="utf-8"))
    rar = sd["rarity"]
    positions = positions or pool_species_positions()
    habs, pools = [], []
    roles = {}
    for n in doc["nests"]:
        w = pl.wards[n["glade"]]
        gl = _glade(doc, n["glade"])
        habs.append({
            "id": n["block"],
            "place": "the Fungal Isle's %s (data/fungal_isle.json): %s" % (gl["name"], n["place"]),
            "pool": "cobblers:%s" % n["pool"],
            "style": "activated",
            "replace_spawns": False,
            "position": {"x": w[0], "y": w[1], "z": w[2]},
            "mimic": n["mimic"],
            "activated": dict(n["activated"]),
            "status": "planned",
            "why": "written by tools/fungal_isle.py records --write from the plan (data/fungal_isle.json nests.%s). An activated block "
                   "keeps up to %d of the pool alive within %d blocks of itself and refills as they are caught or despawn; cancel_range "
                   "-1, so the island's own rosters continue round it. Kept in a block the pack writes (%s), so the pack runs BEFORE "
                   "R9E. UNPROVEN in game: that this block keeps its pool visible (EXP-021, the Ursaluna's den and the Old Orchard "
                   "use the same shape)." % (n["id"], n["activated"]["max_spawns"], n["activated"]["spawn_range"], n["mimic"]),
            "mimic_why": "the block the pack writes at that position: %s" % n["place"]})
        lo, hi = n["band"]
        rows = n["entries"]
        role_of = {r["species"]: r["role"] for r in rows}
        hab_entries, entries = [], []
        for r in rows:
            fam = r.get("family", r["species"])
            bucket = rar[r["role"]]["bucket"]
            weight = rar[r["role"]]["family_weight"]
            display = r["species"].capitalize()
            cond = dict(r.get("conditions") or {})
            hab_entries.append({"species": display, "pokemon": r["species"], "family": fam,
                                "family_priority": role_of.get(fam, r["role"]), "ambient": True,
                                "eligibility_reason": r["why"], "level": r["level"], "bucket": bucket,
                                "weight": weight, "conditions": cond})
            entries.append({"id": "habitat.%s.%s" % (n["pool"], r["species"]), "species": r["species"], "bucket": bucket,
                            "level": r["level"], "weight": weight, "ambient": True, "scope": n["pool"],
                            "mechanism": "habitat_block", "conditions": cond, "eligibility_reason": r["why"],
                            "spawnable_position": r.get("position") or positions.get(r["species"], "grounded")})
        habitat = {"id": n["pool"], "display_name": n["display_name"],
                   "intended_location": "the Fungal Isle's %s at (%d, %d) (data/fungal_isle.json): one activated Habitat Block, %s in "
                                        "data/habitat_blocks.json, at (%d, %d, %d), keeping up to %d alive within %d"
                                        % (gl["name"], gl["centre"][0], gl["centre"][1], n["block"], w[0], w[1], w[2],
                                           n["activated"]["max_spawns"], n["activated"]["spawn_range"]),
                   "mechanism": "habitat_block", "replace_spawns": False,
                   "level_band": {"minimum": lo, "maximum": hi}, "level_band_why": n["band_why"],
                   "why": n["entries_why"], "entries": hab_entries,
                   "placement_status": "authored: data/habitat_blocks.json %s, status planned" % n["block"]}
        pools.append({"habitat": habitat, "entries": entries})
    return habs, pools


def write_records(habs, pools):
    def dump(path, d):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    hd = json.loads(HABITATS.read_text(encoding="utf-8"))
    ids = {h["id"] for h in habs}
    hd["blocks"] = [b for b in hd["blocks"] if b.get("id") not in ids] + habs
    sd = json.loads(SPAWNS.read_text(encoding="utf-8"))
    pids = {p["habitat"]["id"] for p in pools}
    sd["habitats"] = [h for h in sd["habitats"] if h.get("id") not in pids] + [p["habitat"] for p in pools]
    sd["entries"] = [e for e in sd["entries"] if e.get("scope") not in pids] + [e for p in pools for e in p["entries"]]
    dump(HABITATS, hd)
    dump(SPAWNS, sd)


# ------------------------------------------------------------------ the presence probes


def presence_probes(pl):
    """{place id: [probe]} in data/world_probes.json's shape: blocks the pack writes, read from the plan."""
    doc = pl.doc
    pr = doc["probes"]
    rows = []

    def row(what, x, y, z, state, expect=True):
        rows.append({"what": what, "block": [x, y, z, state], "expect": expect})

    wards = {tuple(w) for w in pl.wards.values()}
    for gid in ("cap_wood", "stump_court", "glowcap_hollow"):
        objs = pl.fns[gid]
        cand = []
        for o in objs:
            for layer in ("solid", "hung", "floor"):
                for (x, y, z), v in sorted(getattr(o, layer).items()):
                    if base(v) in ("minecraft:red_mushroom", "minecraft:brown_mushroom", "minecraft:moss_carpet"):
                        continue
                    if (x, y, z) in wards:
                        continue          # R9E replaces it with the Habitat Block that mimics it
                    cand.append((o.id, layer, x, y, z, base(v)))
        want = pr["per_glade"]
        step = max(1, len(cand) // want)
        chosen = cand[::step][:want]
        for oid, layer, x, y, z, v in chosen:
            row("%s: %s (%s)" % (gid, v.split(":")[1], oid), x, y, z, v)
        if gid == "glowcap_hollow":
            o = [x for x in objs if x.id == "glowcap_hollow_bowl"][0]
            cx, cz = _glade(doc, gid)["centre"]
            row("the pool's surface at the middle", cx, o.meta["pool_level"], cz, "minecraft:water")
            row("no water on the rim path", cx + 14, o.meta["pool_level"], cz, "minecraft:water", False)
            lamps =[x for x in objs if x.id == "glowcap_hollow_lamps"][0]
            for (x, y, z, blk) in lamps.meta["big"][:3]:
                row("a froglight cap", x, y, z, blk)
    giants = [o for o in pl.objs if o.kind == "giants"]
    step = max(1, len(giants) // pr["scatter_giants"])
    for o in giants[::step][:pr["scatter_giants"]]:
        x, y, z = o.meta["stem_base"]
        row("a scatter giant's stem (%s)" % o.id, x, y, z, STEM)
    stumps = [o for o in pl.objs if o.kind == "stumps"]
    step = max(1, len(stumps) // pr["scatter_stumps"])
    for o in stumps[::step][:pr["scatter_stumps"]]:
        x, y, z = o.meta["stem_base"]
        row("a scatter stump (%s)" % o.id, x, y, z, LOG)
    return {pr["key"]: rows}


# ------------------------------------------------------------------ the CLI


def report(pl):
    doc = pl.doc
    lines = []
    fns = functions(pl)
    total = sum(sum(1 for l in v if l and not l.startswith("#")) for v in fns.values())
    land = int(pl.T.ok.sum()) * CELL * CELL
    lines.append("island: %d 4x4 cells inside, %d allowed for scatter = %.1f ha usable; counts %s" %
                 (int(pl.T.inside.sum()), int(pl.T.ok.sum()), land / 10000.0, json.dumps(pl.counts)))
    lines.append("objects %d; blocks written %d; functions %d; commands %d" % (len(pl.objs), len(pl.claimed), len(fns), total))
    for n in functions_order(pl):
        cmds = sum(1 for l in fns[n] if l and not l.startswith("#"))
        b = fn_box(pl.fns[n])
        ch = ((b[2] // 16 - b[0] // 16) + 1) * ((b[3] // 16 - b[1] // 16) + 1)
        lines.append("  %-14s %6d commands, %3d chunks, box %s, %d objects" % (n, cmds, ch, b, len(pl.fns[n])))
    for gname in ("cap_wood", "stump_court", "glowcap_hollow"):
        w = pl.wards[gname]
        lines.append("ward %-15s %s" % (gname, w))
    o = [x for x in pl.objs if x.id == "glowcap_hollow_bowl"][0]
    lines.append("hollow: yc %d, pool surface y%d, centre floor y%d, %d pool columns, %d water blocks"
                 % (o.meta["yc"], o.meta["pool_level"], o.meta["centre_floor"], o.meta["pool_cols"], len(o.water)))
    big = [x for x in pl.objs if x.id == "cap_wood_beacon"][0]
    lines.append("beacon: stem base %s, plate y%d, top y%d" % (big.meta["stem_base"], big.meta["plate_y"], big.meta["top_y"]))
    probs = check_plan(pl)
    for p in probs:
        lines.append("PROBLEM %s" % p)
    lines.append("steps %s: %d actions" % (doc["build"]["step"], len(placement_steps(pl=pl))))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "report", "records", "probes"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--write", action="store_true", help="records, probes: replace this place's records in the shared files")
    a = ap.parse_args(argv)
    pl = plan(source_root=a.source_root, path=a.data)
    doc = pl.doc
    if a.cmd == "report":
        print("\n".join(report(pl)))
        return 0
    if a.cmd == "records":
        habs, pools = records(doc, pl)
        if a.write:
            write_records(habs, pools)
            print("fungal_isle: wrote %d habitat blocks, %d pools with %d entries"
                  % (len(habs), len(pools), sum(len(p["entries"]) for p in pools)))
        else:
            print(json.dumps({"habitat_blocks": habs, "pools": pools}, indent=1))
        return 0
    if a.cmd == "probes":
        pr = presence_probes(pl)
        if a.write:
            d = json.loads(PROBES.read_text(encoding="utf-8"))
            d["places"].update(pr)
            with open(PROBES, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
            print("fungal_isle: wrote %d probes into data/world_probes.json (%s)" % (sum(len(v) for v in pr.values()), ", ".join(pr)))
        else:
            for k, v in pr.items():
                print(k, len(v), "probes")
        return 0
    written, _pl = files(pl=pl)
    write(written, a.out)
    n = sum(1 for rel, t in written.items() if rel.endswith(".mcfunction") for l in t.splitlines() if l and not l.startswith("#"))
    print("fungal_isle: %d files -> %s (%d commands)" % (len(written), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
