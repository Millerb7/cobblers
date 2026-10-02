#!/usr/bin/env python
"""Shared, builder-free machinery for the two water-life audits (tools/lake_life_audit.py, tools/sea_life_audit.py).

Nothing here imports tools/lake_life.py or tools/sea_life.py, and nothing reads their derived/*/plan.json. What it
does:

  parse     a generated function's text into commands: `fill` (with `replace <filter>`, `keep`), `setblock`, and
            `execute if block ... run fill|setblock` guards. A command the parser does not model is an error, so a
            pack cannot slip a write past the audit by using a form it does not read.
  terrain   the world as the canonical heightmap alone describes it (tools/ground.py, rounded): solid to the
            ground, painted water over it (a lake basin's level where tools/water_mask.py's rule paints one, else the
            sea level where the ground is below it), air above. Basins are rasterised by the same even-odd rule as
            water_mask.in_polygons, by scanline, so a whole lake costs one pass.
  replay    the commands applied in index order over that world. A filtered fill writes only where the cell holds
            what the filter names; where the heightmap world cannot know (a natural block against a block tag, or an
            `if block` guard on a natural block) the write is assumed to land and is counted as conditional.
  columns   every column another pack writes in the overworld (the pocket dimension's functions are skipped).

Block facts used by the checks (full block, waterloggable, light source) are vanilla 1.21.1's, listed here by
name; a block the lists do not know is treated as NOT full, which is the stricter reading for every check.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
NATURAL, WATER, AIR = "natural", "minecraft:water", "minecraft:air"
NUM = r"(-?\d+)"
FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+)(?: (replace|keep|destroy)(?: (\S+))?)?$" % ((NUM,) * 6))
SET = re.compile(r"^setblock %s %s %s (\S+)(?: (replace|keep|destroy))?$" % ((NUM,) * 3))
GUARD = re.compile(r"^(if|unless) block %s %s %s (\S+) " % ((NUM,) * 3))
ANY_WRITE = re.compile(r"(?:^|run )(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))?")


class ReplayError(Exception):
    pass


def bid(b):
    return b.split("[")[0].split("{")[0]


def props(b):
    m = re.search(r"\[([^\]]*)\]", b)
    if not m:
        return {}
    return dict(kv.split("=", 1) for kv in m.group(1).split(",") if "=" in kv)


# ------------------------------------------------------------------------------------------------- block facts

# Blocks that are not a full cube (a body can share the cell, or water could, or it gives no sturdy top).
_NONFULL_SUFFIX = ("_slab", "_stairs", "_fence", "_fence_gate", "_wall", "_pane", "_door", "_trapdoor", "_bed",
                   "_rail", "rail", "_sign", "_button", "_pressure_plate", "_carpet", "lantern", "_coral",
                   "_coral_fan", "_coral_wall_fan", "_sapling", "_torch", "torch", "_bars", "chain", "_lichen",
                   "_pickle", "seagrass", "kelp", "kelp_plant", "lily_pad", "sugar_cane", "_flower", "_bush",
                   "ladder", "vine", "_candle", "candle", "_head", "_skull", "_banner", "_pot", "scaffolding")
_NONFULL = {"minecraft:air", "minecraft:cave_air", "minecraft:water", "minecraft:lava", "minecraft:light",
            "minecraft:bubble_column", NATURAL}
_FULL_DESPITE_SUFFIX = {"minecraft:sea_lantern"}
# A natural block is solid, but whether it is a full cube is not known offline; it is the heightmap's ground and is
# taken as a sturdy support (the paint lays full blocks: sand, dirt, grass, stone, gravel).
FLUID_FREE_PASSABLE = ("_door", "_bed", "_fence_gate", "sugar_cane", "lily_pad", "_carpet", "_sign")
# Waterloggable in vanilla 1.21.1 (SimpleWaterloggedBlock); a waterloggable block written without waterlogged=true
# in a water cell is a dry cell.
_WATERLOGGABLE_SUFFIX = ("_slab", "_stairs", "_fence", "_wall", "_pane", "_trapdoor", "_rail", "rail", "_sign",
                         "lantern", "chain", "_bars", "_lichen", "_pickle", "_coral", "_coral_fan",
                         "_coral_wall_fan", "ladder", "_candle", "candle", "scaffolding", "_head", "_skull")
_ALWAYS_WET = ("minecraft:seagrass", "minecraft:tall_seagrass", "minecraft:kelp", "minecraft:kelp_plant",
               "minecraft:bubble_column", "minecraft:water")
LIGHTS = {"minecraft:lantern": 15, "minecraft:soul_lantern": 10, "minecraft:sea_pickle": None,
          "minecraft:glow_lichen": 7, "minecraft:torch": 14, "minecraft:sea_lantern": 15, "minecraft:glowstone": 15,
          "minecraft:shroomlight": 15, "minecraft:light": 15, "minecraft:magma_block": 3}
FORBIDDEN = ("minecraft:light", "minecraft:bubble_column", "minecraft:soul_sand", "minecraft:magma_block")


def is_air(b):
    return bid(b) in ("minecraft:air", "minecraft:cave_air")


def is_full(b):
    """A full, solid cube: a sturdy support and nothing a body or water can share. Natural ground counts."""
    if b == NATURAL:
        return True
    i = bid(b)
    if i in _NONFULL:
        return False
    if i in _FULL_DESPITE_SUFFIX:
        return True
    name = i.split(":", 1)[1] if ":" in i else i
    return not any(name.endswith(s) for s in _NONFULL_SUFFIX)


def waterloggable(b):
    i = bid(b)
    name = i.split(":", 1)[1] if ":" in i else i
    return any(name.endswith(s) for s in _WATERLOGGABLE_SUFFIX)


def holds_water(b):
    """The cell has water in it once written: water, a plant that is always wet, or a waterlogged block."""
    if b == WATER:
        return True
    i = bid(b)
    if i.startswith("minecraft:tall_seagrass") or i in _ALWAYS_WET:
        return True
    return props(b).get("waterlogged") == "true"


def light_level(b):
    i = bid(b)
    if i not in LIGHTS:
        return 0
    if i == "minecraft:sea_pickle":
        # vanilla: 3 + 3 per extra pickle, and only waterlogged
        if props(b).get("waterlogged") != "true":
            return 0
        return 3 * int(props(b).get("pickles", "1")) + 3
    return LIGHTS[i]


# ------------------------------------------------------------------------------------------------------ parsing


class Cmd:
    __slots__ = ("fn", "line", "box", "block", "mode", "filter", "guards", "text")

    def __init__(self, fn, line, box, block, mode, flt, guards, text):
        self.fn, self.line, self.box, self.block = fn, line, box, block
        self.mode, self.filter, self.guards, self.text = mode, flt, guards, text

    def cells(self):
        x0, y0, z0, x1, y1, z1 = self.box
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                for y in range(y0, y1 + 1):
                    yield (x, y, z)

    def columns(self):
        x0, _, z0, x1, _, z1 = self.box
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                yield (x, z)


def _box(a, b, c, d, e, f):
    a, b, c, d, e, f = (int(v) for v in (a, b, c, d, e, f))
    return (min(a, d), min(b, e), min(c, f), max(a, d), max(b, e), max(c, f))


def parse_line(ln, fn="?", no=0):
    """One command, or None for a comment, blank or forceload line. Raises on anything not modelled."""
    s = ln.strip()
    if not s or s.startswith("#") or s.startswith("forceload "):
        return None
    guards = []
    body = s
    if body.startswith("execute "):
        rest = body[len("execute "):]
        while True:
            m = GUARD.match(rest)
            if not m:
                break
            guards.append((m.group(1), (int(m.group(2)), int(m.group(3)), int(m.group(4))), m.group(5)))
            rest = rest[m.end():]
        if not guards or not rest.startswith("run "):
            raise ReplayError("%s:%d: an execute form the audit does not model: %s" % (fn, no, s[:120]))
        body = rest[len("run "):]
    m = FILL.match(body)
    if m:
        g = m.groups()
        mode = g[7] or "replace"
        if mode == "destroy":
            mode = "replace"
        return Cmd(fn, no, _box(*g[:6]), g[6], mode, g[8], guards, s)
    m = SET.match(body)
    if m:
        g = m.groups()
        mode = g[4] or "replace"
        if mode == "destroy":
            mode = "replace"
        return Cmd(fn, no, _box(g[0], g[1], g[2], g[0], g[1], g[2]), g[3], mode, None, guards, s)
    raise ReplayError("%s:%d: a command the audit does not model: %s" % (fn, no, s[:120]))


def function_names(fn_dir):
    fn_dir = Path(fn_dir)
    idx = fn_dir / "index.txt"
    if idx.is_file():
        names = [l.strip() for l in idx.read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        names = sorted(p.stem for p in fn_dir.glob("*.mcfunction"))
    return names


def parse_pack(fn_dir):
    """[(function name, [Cmd])] in index order. Fails closed on a missing index, an empty one, a listed function
    that does not exist, or a function on disk that the index does not list (it would never run, and a check that
    reads only the index would never see it)."""
    fn_dir = Path(fn_dir)
    if not (fn_dir / "index.txt").is_file():
        raise ReplayError("no %s" % (fn_dir / "index.txt"))
    names = function_names(fn_dir)
    if not names:
        raise ReplayError("%s: the index is empty" % fn_dir)
    on_disk = {p.stem for p in fn_dir.glob("*.mcfunction")}
    missing = [n for n in names if n not in on_disk]
    if missing:
        raise ReplayError("%s: the index lists %d functions that do not exist, e.g. %s" % (fn_dir, len(missing),
                                                                                         missing[0]))
    unlisted = sorted(on_disk - set(names))
    out = []
    for n in names:
        cmds = []
        for i, ln in enumerate((fn_dir / (n + ".mcfunction")).read_text(encoding="utf-8").splitlines(), 1):
            c = parse_line(ln, n, i)
            if c is not None:
                cmds.append(c)
        out.append((n, cmds))
    return out, unlisted


def pack_columns(pack_dir, skip_parts=("pocket",)):
    """{(x, z): [(y0, y1, block)]} every overworld column a pack's functions write with absolute coordinates (fill
    or setblock, anywhere in a line), with the spans written there. Functions under a directory named in skip_parts
    (the portals' pocket dimension) and lines that move into another dimension are skipped. A pack that is absent
    returns None, not an empty dict."""
    root = Path(pack_dir) / "data"
    if not root.is_dir():
        return None
    cols = {}
    for f in root.rglob("*.mcfunction"):
        if any(p in skip_parts for p in f.parts):
            continue
        for ln in f.read_text(encoding="utf-8").splitlines():
            s = ln.strip()
            if not s or s.startswith("#") or "~" in s or "^" in s:
                continue
            if "execute in " in s and "execute in minecraft:overworld" not in s:
                continue
            for m in ANY_WRITE.finditer(s):
                x0, y0, z0 = int(m.group(2)), int(m.group(3)), int(m.group(4))
                if m.group(1) == "fill" and m.group(5) is not None:
                    x1, y1, z1 = int(m.group(5)), int(m.group(6)), int(m.group(7))
                else:
                    x1, y1, z1 = x0, y0, z0
                tail = s[m.end():].split()
                blk = tail[0] if tail else "?"
                span = (min(y0, y1), max(y0, y1), blk)
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        cols.setdefault((x, z), []).append(span)
    return cols


def foreign_overlap(ours, theirs):
    """Compare our written cells {(x, y, z)} with another pack's spans {(x, z): [(y0, y1, block)]}.

    Returns (cells in common, columns in common where every one of our cells stands above a full block the other
    pack wrote as its highest in that column (a sealed roof: we cannot reach what is under it), the other columns in
    common). Only the third and the first are faults; the second is reported."""
    by_col = {}
    for (x, y, z) in ours:
        by_col.setdefault((x, z), []).append(y)
    cells, sealed, open_ = [], [], []
    for c, ys in by_col.items():
        sp = theirs.get(c)
        if not sp:
            continue
        hit = [y for y in ys for (a, b, _blk) in sp if a <= y <= b]
        if hit:
            cells.append((c[0], hit[0], c[1]))
            continue
        top = max(reversed(sp), key=lambda s: s[1])        # the last written of the highest spans
        if min(ys) > top[1] and is_full(top[2]):
            sealed.append(c)
        else:
            open_.append(c)
    return cells, sealed, open_


# ------------------------------------------------------------------------------------------------------ terrain


def raster_polygons(rings, x0, z0, x1, z1):
    """A (z, x) bool array over the inclusive box: True where water_mask.in_polygons(rings, x, z) is True (each
    ring by the even-odd rule with the strict `x < crossing` test, the rings OR-ed), computed by scanline."""
    W, H = x1 - x0 + 1, z1 - z0 + 1
    out = np.zeros((H, W), bool)
    xs = np.arange(x0, x1 + 1, dtype=float)
    for ring in rings:
        if len(ring) < 3:
            continue
        P = np.array(ring, dtype=float)
        Q = np.roll(P, 1, axis=0)                       # j = i - 1, as in_polygons walks it
        xi, zi, xj, zj = P[:, 0], P[:, 1], Q[:, 0], Q[:, 1]
        for r in range(H):
            z = z0 + r
            sel = (zi > z) != (zj > z)
            if not sel.any():
                continue
            xc = (xj[sel] - xi[sel]) * (z - zi[sel]) / (zj[sel] - zi[sel]) + xi[sel]
            xc.sort()
            # inside if the count of crossings strictly greater than x is odd
            n_gt = len(xc) - np.searchsorted(xc, xs, side="right")
            out[r] |= (n_gt % 2) == 1
    return out


class Terrain:
    """The heightmap world: ground(x, z) rounded, lake basins, the sea level. `ground` is any callable (x, z) -> int
    (tools/ground.py in production, a synthetic function in the tests); `bodies` is tools/water_mask.bodies()'s
    shape {id: {"level_y", "basin"}}."""

    def __init__(self, ground, sea, bodies):
        self.g, self.sea = ground, int(sea)
        self.bodies = {}
        for k, b in bodies.items():
            if not b.get("basin"):
                continue
            pts = [p for ring in b["basin"] for p in ring]
            x0, z0 = int(math.floor(min(p[0] for p in pts))), int(math.floor(min(p[1] for p in pts)))
            x1, z1 = int(math.ceil(max(p[0] for p in pts))), int(math.ceil(max(p[1] for p in pts)))
            self.bodies[k] = {"level": int(b["level_y"]), "rings": b["basin"], "box": (x0, z0, x1, z1), "mask": None}
        self._cols = {}

    def _inside(self, k, x, z):
        b = self.bodies[k]
        x0, z0, x1, z1 = b["box"]
        if not (x0 <= x <= x1 and z0 <= z <= z1):
            return False
        if b["mask"] is None:
            b["mask"] = raster_polygons(b["rings"], x0, z0, x1, z1)
        return bool(b["mask"][z - z0, x - x0])

    def in_basin(self, k, x, z):
        return self._inside(k, x, z)

    def column(self, x, z):
        """(ground y, water level or None, body id: a lake id, "sea" or None)."""
        key = (x, z)
        c = self._cols.get(key)
        if c is None:
            gy = int(self.g(x, z))
            best = (None, None)
            for k, b in self.bodies.items():
                if gy < b["level"] and self._inside(k, x, z):
                    if best[1] is None or b["level"] > best[1]:
                        best = (k, b["level"])
            if best[0] is None and gy < self.sea:
                best = ("sea", self.sea)
            c = (gy, best[1], best[0])
            self._cols[key] = c
        return c

    def base(self, x, y, z):
        gy, lv, _ = self.column(x, z)
        if y <= gy:
            return NATURAL
        if lv is not None and y <= lv:
            return WATER
        return AIR


# ------------------------------------------------------------------------------------------------------- replay

VANILLA_TAGS = {
    # vanilla 1.21.1 data/minecraft/tags/block, only the two the lake pack's guards name
    "#minecraft:dirt": {"minecraft:dirt", "minecraft:grass_block", "minecraft:podzol", "minecraft:coarse_dirt",
                        "minecraft:mycelium", "minecraft:rooted_dirt", "minecraft:moss_block", "minecraft:mud",
                        "minecraft:muddy_mangrove_roots"},
    "#minecraft:sand": {"minecraft:sand", "minecraft:red_sand", "minecraft:suspicious_sand"},
}


class World:
    """The terrain with a pack's commands replayed over it, in order."""

    def __init__(self, terrain, tags=None):
        self.t = terrain
        self.w = {}                 # cell -> block id with states, the final state of every written cell
        self.group = {}             # cell -> the group (function-name prefix) that last wrote it
        self.tags = dict(VANILLA_TAGS)
        self.tags.update(tags or {})
        self.dead = []              # (cmd, cell) writes whose filter or guard did not match: they do nothing
        self.conditional = 0        # writes assumed to land on an unknowable natural block
        self.landed = []            # (cmd, cell, group, what was there before)

    def at(self, x, y, z):
        b = self.w.get((x, y, z))
        return b if b is not None else self.t.base(x, y, z)

    def _matches(self, cur, flt):
        """True, False, or None (cannot be known: a natural block against a tag or a named solid)."""
        if flt.startswith("#"):
            members = self.tags.get(flt)
            if members is None:
                raise ReplayError("a block tag the audit does not know: %s" % flt)
            if cur == NATURAL:
                return None
            return bid(cur) in members
        if cur == NATURAL:
            if flt in (WATER, "minecraft:air", "minecraft:cave_air"):
                return False
            return None
        return bid(cur) == bid(flt)

    def apply(self, cmd, group):
        for kind, (gx, gy, gz), what in cmd.guards:
            ok = self._matches(self.at(gx, gy, gz), what)
            if ok is None:
                self.conditional += 1
                continue
            if (kind == "if") != ok:
                for cell in cmd.cells():
                    self.dead.append((cmd, cell))
                return
        for cell in cmd.cells():
            cur = self.at(*cell)
            if cmd.mode == "keep":
                if not is_air(cur):
                    self.dead.append((cmd, cell))
                    continue
            elif cmd.filter:
                ok = self._matches(cur, cmd.filter)
                if ok is False:
                    self.dead.append((cmd, cell))
                    continue
                if ok is None:
                    self.conditional += 1
            self.landed.append((cmd, cell, group, cur))
            self.w[cell] = cmd.block
            self.group[cell] = group


def group_of(fn_name):
    """The function's group: its name up to the tile suffix (`2plants_12_40` -> `2plants`)."""
    return re.sub(r"(_-?\d+)+$", "", fn_name)


def replay(world, parsed):
    n = 0
    for name, cmds in parsed:
        g = group_of(name)
        for c in cmds:
            world.apply(c, g)
            n += 1
    return n


# ------------------------------------------------------------------------------------------------- geometry


class ColumnIndex:
    """A set of (x, z) columns with fast box queries (a boolean raster over their bounding box)."""

    def __init__(self, cols):
        self.cols = set(cols)
        if self.cols:
            xs = [c[0] for c in self.cols]
            zs = [c[1] for c in self.cols]
            self.x0, self.z0 = min(xs), min(zs)
            self.r = np.zeros((max(zs) - self.z0 + 1, max(xs) - self.x0 + 1), bool)
            self.r[np.array(zs) - self.z0, np.array(xs) - self.x0] = True
        else:
            self.r = None

    def in_box(self, box):
        """[(x, z)] of the set inside the inclusive box (x0, z0, x1, z1)."""
        if self.r is None:
            return []
        x0, z0, x1, z1 = box
        a0, a1 = max(z0 - self.z0, 0), min(z1 - self.z0 + 1, self.r.shape[0])
        b0, b1 = max(x0 - self.x0, 0), min(x1 - self.x0 + 1, self.r.shape[1])
        if a1 <= a0 or b1 <= b0:
            return []
        zz, xx = np.nonzero(self.r[a0:a1, b0:b1])
        return [(int(x + b0 + self.x0), int(z + a0 + self.z0)) for z, x in zip(zz, xx)]

    def near_points(self, pts, m):
        """[(x, z)] of the set within Chebyshev m of any of pts."""
        if not pts or self.r is None:
            return []
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        cand = self.in_box((min(xs) - m, min(zs) - m, max(xs) + m, max(zs) + m))
        if not cand:
            return []
        P = np.array(pts)
        out = []
        for (x, z) in cand:
            if (np.maximum(np.abs(P[:, 0] - x), np.abs(P[:, 1] - z)) <= m).any():
                out.append((x, z))
        return out


def chebyshev_box(cx, cz, r):
    return (cx - r, cz - r, cx + r, cz + r)


def in_box(box, x, z):
    x0, z0, x1, z1 = box
    return x0 <= x <= x1 and z0 <= z <= z1


def seg_dist(px, pz, ax, az, bx, bz):
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L2))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz))


def near_polyline(cols, pts, half):
    """[(x, z)] of `cols` (a set or a ColumnIndex) within `half` blocks (Euclidean) of the polyline `pts`."""
    ix = cols if isinstance(cols, ColumnIndex) else ColumnIndex(cols)
    if ix.r is None or len(pts) < 2:
        return []
    hit = set()
    for (ax, az), (bx, bz) in zip(pts[:-1], pts[1:]):
        h = int(math.ceil(half))
        cand = ix.in_box((min(ax, bx) - h, min(az, bz) - h, max(ax, bx) + h, max(az, bz) + h))
        for (x, z) in cand:
            if (x, z) not in hit and seg_dist(x, z, ax, az, bx, bz) <= half:
                hit.add((x, z))
    return sorted(hit)


def octile3_worst_ratio(samples=60):
    """The largest factor by which a 26-connected grid path (steps 1, sqrt 2, sqrt 3) can exceed the straight
    Euclidean length it follows, maximised numerically over directions. Dividing a 26-connected Dijkstra length by
    it gives a LOWER bound on the true swim length: derived, not tuned."""
    best = 1.0
    for i in range(samples + 1):
        for j in range(samples + 1):
            a, b = 1.0, i / samples
            c = b * j / samples                        # a >= b >= c >= 0 covers every direction by symmetry
            cost = math.sqrt(3) * c + math.sqrt(2) * (b - c) + (a - b)
            best = max(best, cost / math.sqrt(a * a + b * b + c * c))
    return best


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def town_boxes(towns_doc, protect):
    """[(id, (x0, z0, x1, z1))] every town footprint grown by data/water_shape.json protect.town_margin_blocks
    (with its overrides)."""
    m = int(protect.get("town_margin_blocks", 0))
    over = protect.get("town_margin_overrides") or {}
    out = []
    for t in towns_doc["towns"]:
        f = t.get("footprint") or {}
        if "min_x" not in f:
            continue
        mm = int(over.get(t["id"], m))
        out.append((t["id"], (f["min_x"] - mm, f["min_z"] - mm, f["max_x"] + mm, f["max_z"] + mm)))
    return out
