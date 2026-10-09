#!/usr/bin/env python
"""Gull Rock, the rookery off the north-east coast (cell C7), from data/rookery.json: a stack in the sea, six tidal
rocks round it, a colony of sea-birds on them and one great old Dragonite on the crown.

The brief of 2026-10-09 (gap 9 of docs/world-building/WORLD_SWEEP_2026-10-09.md): a nest on the model of the Ursaluna
den, a creature and a place that suits it, strong enough that meeting it early is a mistake. Nothing here is new
machinery; every part is a piece the repository already runs:

  the rock      vanilla blocks written by this pack's one `build` function, in the sea, from a heightfield this tool
                computes: ONE stack (a steep cone with a wobbling outline, three nest ledges, hay nests, guano streaks
                and a flat calcite crown) and six dome-shaped tidal rocks on a ring round it. Every Y is the canonical
                heightmap's rounded ground (tools/ground.py), the sea level and every wet column come from
                tools/water_mask.py (through tools/resident_encounters.py Wet), and the rock stands from two blocks under
                the bed so a bed that exports low leaves no gap. NOTHING is written on a dry column: a tidal-rock stack
                that touched the shore would be a path, and this one is a swim.
  the Gullmother a named Pokemon on the residents' keeper (tools/resident_encounters.py resident_files(), CALLED the way
                tools/northern_residents.py and tools/far_south.py call it): dormant (NoAI) on the crown until a player
                comes within the trigger, awake and leashed, asleep again when everyone has gone, respawned on the
                gulch's clock, never conjured in front of anyone, never touched once the blackout has made it a guardian.
                HER CATCH GATE IS THE LEVEL CAP, no flag check of her own: she is level 55 and the cap is 55 at seven
                badges (data/level_cap.json: a Pokemon over the thrower's cap breaks free from any ball).
  the colony    NOT in this pack: six activated Habitat Blocks in data/habitat_blocks.json and a Habitat pool in
                data/spawns.json (compiled by tools/compile_spawns.py, placed by tools/habitat_blocks.py with every
                other block, R9E). `records --write` writes this build's records into those two files.
  the probes    `probes --write` puts this place's presence probes under its own key in data/world_probes.json, read by
                tools/presence_audit.py --only extra.

THE NEST RULE. tests/test_resident_siting.py holds a resident's fight clear of every activated Habitat Block's spawns
(spawn_range + leash). So the colony cannot sit under her: the six rocks stand on a ring of radius 34 round her
(spawn_range 16 + leash 16 + 2), and the birds wheel round the stack at that distance.

The siting rules fail the build (the rules block of the record): every written column wet and inside cell C7; at least
authored_clearance from every x/z authored in any other data file and from every route corridor box (a filled
rectangle); clear of every town footprint and Rift zone; the stack's centre and the anchor at least path_clearance from
a route path; at least ferry_clearance from a ferry crossing; no spawn-condition block, no gravity block; the Habitat
Blocks clear of the Gullmother's leash and of each other's. These are the builder's guards, not an audit.

  python tools/rookery.py [--source-root R] [--out DIR]     write build/datapacks/cobblers_rookery
  python tools/rookery.py report                             the geometry as measured, the checks, the steps
  python tools/rookery.py records [--write]                   the Habitat Block and pool records (print, or replace)
  python tools/rookery.py probes [--write]                    the presence probes (print, or replace)

The re-application (tools/reapply.py): placement_steps() is R9RK, BEFORE R9E (the Habitat Blocks sit in this rock);
entity_steps() is R18RK, after R18FS: the Gullmother summoned (guarded on her tag AND species) and bound.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402
import southern_residents as SR  # noqa: E402

DATA = ROOT / "data" / "rookery.json"
HABITATS = ROOT / "data" / "habitat_blocks.json"
SPAWNS = ROOT / "data" / "spawns.json"
PROBES = ROOT / "data" / "world_probes.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_rookery"
SCHEMA = "cobblers.rookery/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
HABITAT_PREFIX = "rookery_skerry_"
PROBE_KEY = "rookery"
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()
# a block that falls (it would drop off a rock under water) is never written, whatever the allow-list says
GRAVITY = ("sand", "gravel", "concrete_powder", "anvil", "dragon_egg", "scaffolding")
AIR_OVER_CROWN = 4      # blocks of air over the anchor: the Gullmother stands 3.2 high at scale 0.9


class RookeryError(SystemExit):
    pass


jload = SR.jload
base = SR.base


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise RookeryError("%s: schema must be %s" % (path, SCHEMA))
    if len(doc["residents"]) != 1:
        raise RookeryError("one nest, one resident")
    pk = doc["residents"][0]["pokemon"]
    if not (0 < pk["trigger"] < pk["leash"]):
        raise RookeryError("the trigger must be inside the leash")
    allowed = set(doc["blocks"]["ids"])
    for b in allowed:
        if any(b.endswith(g) for g in GRAVITY):
            raise RookeryError("%s is a gravity block: it would fall off a rock under water" % b)
    sk, st, col = doc["skerries"], doc["stack"], doc["colony"]
    palettes = [st["palette_under"], st["palette_over"], st["guano"]["palette"], sk["palette"]]
    used = {b for p in palettes for b, _w in p} | {st["plate"], st["nest"]}
    if not used <= allowed:
        raise RookeryError("blocks outside blocks.ids: %s" % sorted(used - allowed))
    if sk["ring_radius"] < col["spawn_range"] + pk["leash"]:
        raise RookeryError("the ring (%d) is inside spawn_range + leash (%d): the nest would overlap her fight"
                           % (sk["ring_radius"], col["spawn_range"] + pk["leash"]))
    if doc["build"]["respawn_ticks"] < 72000:
        raise RookeryError("respawn_ticks under an hour: a Dragonite that returns that fast is a farm (the Ursaluna's is 72000)")
    if col["level_band"]["maximum"] > 45:
        raise RookeryError("the colony is catchable at band 5 (cap 45): its top level must be at most 45")
    return doc


# ------------------------------------------------------------------ the heightfield model


def _noise(b, seed):
    """Smooth angular noise in [-1, 1]: three harmonics, phases from the seed. b is a bearing in radians."""
    s = 0.0
    for m in (1, 2, 3):
        ph = (SR._h32(seed, m, 7) % 6283) / 1000.0
        s += math.sin(m * b + ph) / m
    return s / (1 + 1 / 2.0 + 1 / 3.0)


def _bearing(dx, dz):
    """Compass degrees of the offset (dx, dz): 0 north (-z), 90 east (+x), 270 west."""
    return math.degrees(math.atan2(dx, -dz)) % 360.0


def _angdiff(a, b):
    return abs(((a - b + 180.0) % 360.0) - 180.0)


def _cone(de, r_base, r_top, base_y, top_y, exp):
    """The column top (float) of a cone of the given plan radii at the effective distance `de`; None outside."""
    if de >= r_base:
        return None
    u = 1.0 if de <= r_top else (r_base - de) / (r_base - r_top)
    return base_y + (top_y - base_y) * (u ** exp)


def _pick(palette, x, y, z, salt):
    total = sum(w for _b, w in palette)
    k = SR._h32(x * 31 + y, z, salt) % total
    for b, w in palette:
        if k < w:
            return b
        k -= w
    return palette[-1][0]


class Model:
    """Every block the pack writes: {(x, y, z): state}, the columns' tops, the anchor and the Habitat Block positions."""

    def __init__(self, doc, g, wet):
        self.doc, self.g, self.wet = doc, g, wet
        r = doc["residents"][0]
        st, sk = doc["stack"], doc["skerries"]
        self.cx, self.cz = r["site"]["centre"]
        lv = wet.level(self.cx, self.cz)
        if lv is None:
            raise RookeryError("the stack's centre (%d, %d) is dry" % (self.cx, self.cz))
        self.sea = int(lv)
        self.crown = self.sea + int(st["crown_over_sea"])
        self.top = {}                # (x, z) -> (lo, T) for every column with rock
        self.kind = {}               # (x, z) -> "stack" | "skerry<k>"
        self.blocks = {}
        self.notes = {}
        self._stack()
        self.skerries = [self._skerry(k) for k in range(int(sk["count"]))]
        self._dress()
        self.anchor = (self.cx, self.crown + 1, self.cz)

    # -- the stack
    def _stack(self):
        st, g = self.doc["stack"], self.g
        rb, rt, ex, wob, seed = st["r_base"], st["r_top"], st["profile_exp"], st["wobble"], st["seed"]
        reach = int(math.ceil(rb * (1 + wob))) + int(math.ceil(max(l["depth"] for l in st["ledges"]))) + 2
        beds = [g(self.cx + dx, self.cz + dz) for dx in range(-reach, reach + 1) for dz in range(-reach, reach + 1)
                if dx * dx + dz * dz <= (rb * 1.1) ** 2]
        self.stack_base = min(beds)
        self.stack_bed = (min(beds), max(beds))
        base_y, crown = self.stack_base, self.crown
        found = int(st["foundation_below_bed"])
        tops = {}
        for dx in range(-reach, reach + 1):
            for dz in range(-reach, reach + 1):
                d = math.hypot(dx, dz)
                b = _bearing(dx, dz) if d else 0.0
                w = 1.0 + wob * _noise(math.radians(b), seed)
                t = _cone(d / w, rb, rt, base_y, crown, ex)
                T = int(round(t)) if t is not None else None
                for lg in st["ledges"]:
                    h = self.sea + int(lg["over_sea"])
                    u = ((h - base_y) / float(crown - base_y)) ** (1.0 / ex)
                    de_face = rb - (rb - rt) * u
                    if d and _angdiff(b, lg["bearing"]) <= lg["width_deg"] / 2.0 \
                            and de_face - 0.5 <= d / w <= de_face + lg["depth"] / w:
                        T = max(T if T is not None else h, h)
                if T is None:
                    continue
                x, z = self.cx + dx, self.cz + dz
                gy = g(x, z)
                if T <= gy:
                    continue
                tops[(x, z)] = (gy - found, T)
        self.top.update(tops)
        for c in tops:
            self.kind[c] = "stack"
        self.stack_cols = set(tops)

    # -- one skerry
    def _skerry(self, k):
        sk, g = self.doc["skerries"], self.g
        bearing = sk["first_bearing"] + sk["step_deg"] * k
        b = math.radians(bearing)
        sx = self.cx + int(round(sk["ring_radius"] * math.sin(b)))
        sz = self.cz - int(round(sk["ring_radius"] * math.cos(b)))
        top_y = self.sea + int(sk["top_over_sea"])
        rad = sk["radius"]
        beds = [g(sx + dx, sz + dz) for dx in range(-9, 10) for dz in range(-9, 10) if dx * dx + dz * dz <= 81]
        bed_min = min(beds)
        r_out = rad + 0.45 * (top_y - bed_min)
        reach = int(math.ceil(r_out * 1.2)) + 1
        seed = self.doc["stack"]["seed"] + 100 + k
        cols = {}
        for dx in range(-reach, reach + 1):
            for dz in range(-reach, reach + 1):
                d = math.hypot(dx, dz)
                bb = _bearing(dx, dz) if d else 0.0
                w = 1.0 + 0.18 * _noise(math.radians(bb), seed)
                t = _cone(d / w, r_out, rad * 0.55, bed_min, top_y, 0.7)
                if t is None:
                    continue
                T = int(round(t))
                x, z = sx + dx, sz + dz
                gy = g(x, z)
                if T <= gy:
                    continue
                cols[(x, z)] = (gy - int(self.doc["stack"]["foundation_below_bed"]), T)
        for c, v in cols.items():
            self.top[c] = v
            self.kind[c] = "skerry%d" % k
        crown_col = max(cols, key=lambda c: (cols[c][1], -math.hypot(c[0] - sx, c[1] - sz)))
        return {"k": k, "bearing": bearing, "centre": (sx, sz), "top": top_y, "bed_min": bed_min, "cols": set(cols),
                "habitat": (sx, top_y - int(sk["block_under_top"]), sz), "peak": crown_col}

    # -- the blocks
    def _dress(self):
        st, sk = self.doc["stack"], self.doc["skerries"]
        sea, top = self.sea, self.top
        gu = st["guano"]
        seed = st["seed"]

        def exposed(x, y, z):
            if y >= top[(x, z)][1]:
                return True
            for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                n = top.get((nx, nz))
                if n is None or n[1] < y:
                    return True
            return False

        for (x, z), (lo, T) in sorted(top.items()):
            kind = self.kind[(x, z)]
            dx, dz = x - self.cx, z - self.cz
            bear = _bearing(dx, dz) if (dx or dz) else 0.0
            streak = kind == "stack" and math.hypot(dx, dz) >= st["r_top"] * 0.6 and any(
                _angdiff(bear, s) <= gu["streak_half_deg"] for s in gu["streak_bearings"])
            for y in range(lo, T + 1):
                if kind == "stack":
                    if y == T and T == self.crown:
                        s = st["plate"]
                    elif exposed(x, y, z):
                        over = y - sea
                        if over >= gu["from_over_sea"] and (streak or (SR._h32(x * 7 + y, z, seed + 3) % 1000) / 1000.0 < gu["scatter"]):
                            s = _pick(gu["palette"], x, y, z, seed + 5)
                        else:
                            s = _pick(st["palette_over" if y > sea else "palette_under"], x, y, z, seed + 1)
                    else:
                        s = "minecraft:stone"
                else:
                    if y == T and (SR._h32(x, z, seed + 9) % 1000) / 1000.0 < sk["guano_scatter"]:
                        s = _pick(gu["palette"], x, y, z, seed + 11)
                    else:
                        s = _pick(sk["palette"], x, y, z, seed + 2) if exposed(x, y, z) else "minecraft:stone"
                self.blocks[(x, y, z)] = s
        # nests: a lip of hay on each ledge's outer edge, a half ring on the crown, one hay block on each skerry
        hay = st["nest"]
        self.ledge_nests = []
        for lg in st["ledges"]:
            h = sea + int(lg["over_sea"])
            for (x, z), (lo, T) in sorted(top.items()):
                if self.kind[(x, z)] != "stack" or T != h:
                    continue
                dx, dz = x - self.cx, z - self.cz
                if _angdiff(_bearing(dx, dz), lg["bearing"]) > lg["width_deg"] / 2.0 - 3:
                    continue
                if any((top.get(n) or (0, -1))[1] < h for n in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1))):
                    self.blocks[(x, h + 1, z)] = hay
                    self.ledge_nests.append((x, h + 1, z))
        cn = st["crown_nest"]
        self.crown_nest = []
        for (x, z), (lo, T) in sorted(top.items()):
            if self.kind[(x, z)] != "stack" or T != self.crown:
                continue
            dx, dz = x - self.cx, z - self.cz
            if (dx or dz) and abs(math.hypot(dx, dz) - cn["r"]) <= 0.7 and cn["from_bearing"] <= _bearing(dx, dz) <= cn["to_bearing"]:
                self.blocks[(x, self.crown + 1, z)] = hay
                self.crown_nest.append((x, self.crown + 1, z))
        self.skerry_nests = []
        for s in self.skerries:
            sx, sz = s["centre"]
            for ox, oz in (tuple(sk["nest_offset"]), (-sk["nest_offset"][0], sk["nest_offset"][1]),
                           (sk["nest_offset"][0], -sk["nest_offset"][1]), (0, 1), (1, 0)):
                c = (sx + ox, sz + oz)
                if c in top and top[c][1] == s["top"]:
                    self.blocks[(c[0], s["top"] + 1, c[1])] = hay
                    self.skerry_nests.append((c[0], s["top"] + 1, c[1]))
                    break
            else:
                raise RookeryError("skerry %d has no flat column for its nest" % s["k"])


def model(doc, g, wet=None):
    import resident_encounters as RE
    wet = wet or RE.Wet(g, [tuple(doc["residents"][0]["site"]["centre"])])
    return Model(doc, g, wet)


# ------------------------------------------------------------------ the siting rules (the builder's guards)


def box_of(m):
    xs = [c[0] for c in m.top] + [m.anchor[0]]
    zs = [c[1] for c in m.top] + [m.anchor[2]]
    return [min(xs), min(zs), max(xs), max(zs)]


def ferry_segments():
    """Every water crossing of data/water_shape.json with a from and a to: [(a, b, id)]."""
    out = []
    for c in jload("water_shape.json").get("crossings") or []:
        if c.get("from") and c.get("to"):
            out.append((tuple(c["from"]), tuple(c["to"]), c.get("id")))
    return out


def _dseg(x, z, a, b):
    vx, vz = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vz * vz
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - a[0]) * vx + (z - a[1]) * vz) / L2))
    return math.hypot(x - a[0] - t * vx, z - a[1] - t * vz)


def authored_points(doc, m):
    """tools/southern_residents.py authored_points() with this nest's OWN records taken out. Its six Habitat Blocks
    (data/habitat_blocks.json) and its entity probe (data/world_probes.json) are in the shared files this scan reads,
    and without the filter the nest would stand 0 blocks from itself the day `records --write` ran. Only points from
    those two files that sit exactly on one of our own positions go; anything else in them still counts."""
    own = {(s["habitat"][0], s["habitat"][2]) for s in m.skerries} | {(m.anchor[0], m.anchor[2])}
    return [p for p in SR.authored_points(doc, own_file=DATA)
            if not (p[2] in ("habitat_blocks.json", "world_probes.json") and (int(p[0]), int(p[1])) in own)]


def siting(doc, m, pts=None):
    """Problems, as strings, and the measured numbers."""
    import numpy as np
    rules = doc["rules"]
    r = doc["residents"][0]
    pk = r["pokemon"]
    probs = []
    cols = set(m.top)
    # 1. wet, and inside the cell
    dry = sorted(c for c in cols if not m.wet(*c))
    if dry:
        probs.append("%d written columns are not water, e.g. %s (a rock that touches the shore is a path)" % (len(dry), dry[:3]))
    x0, z0, x1, z1 = rules["cell_box"]
    out = [c for c in cols if not (x0 <= c[0] <= x1 and z0 <= c[1] <= z1)]
    if out:
        probs.append("%d columns outside cell %s: %s" % (len(out), rules["cell"], out[:3]))
    # 2. authored points, corridor boxes, towns, Rift zones
    pts = pts if pts is not None else authored_points(doc, m)
    P = np.array([(a, b) for a, b, _f in pts], float)
    F = [f for _a, _b, f in pts]
    C = np.array(sorted(cols | {(m.anchor[0], m.anchor[2])}), float)
    best = (1e9, None, None)
    for i in range(0, len(C), 256):
        blk = C[i:i + 256]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] < best[0]:
            best = (float(d[j]), tuple(blk[j[0]]), F[j[1]])
    if best[0] < rules["authored_clearance"]:
        probs.append("(%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                     % (best[1][0], best[1][1], best[0], best[2], rules["authored_clearance"]))
    cprobs, cbest = SR.corridor_check(r["id"], cols, rules["authored_clearance"])
    probs += cprobs
    mg = rules["authored_clearance"]
    for t in jload("towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is not None and any(f["min_x"] - mg <= x <= f["max_x"] + mg and f["min_z"] - mg <= z <= f["max_z"] + mg
                                              for x, z in cols):
            probs.append("within %d of town %s's footprint" % (mg, t["id"]))
    for k, zone in jload("rift_zones.json")["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                probs.append("inside Rift zone %s" % k)
                break
    # 3. route paths
    paths = np.array([p for pl in jload("route_paths.json")["paths"].values() for p in pl], float)
    ax, ay, az = m.anchor
    dp = min(float(np.min(np.hypot(paths[:, 0] - x, paths[:, 1] - z))) for x, z in ((m.cx, m.cz), (ax, az)))
    if dp < rules["path_clearance"]:
        probs.append("%.0f blocks from a route path (needs %d)" % (dp, rules["path_clearance"]))
    # 4. ferry crossings
    fd = min([min(_dseg(x, z, a, b) for x, z in cols) for a, b, _i in ferry_segments()] or [1e9])
    if fd < rules["ferry_clearance"]:
        probs.append("%.0f blocks from a ferry crossing (needs %d)" % (fd, rules["ferry_clearance"]))
    # 5. spawn-condition blocks
    spawn = set(jload("spawn_blocks.json")["blocks"])
    bad = sorted({base(v) for v in m.blocks.values()} & spawn)
    if bad:
        probs.append("writes spawn-condition blocks %s (data/spawn_blocks.json)" % bad)
    # 6. the anchor: the crown plate under it, air over it
    if m.blocks.get((ax, ay - 1, az)) != doc["stack"]["plate"]:
        probs.append("the anchor is not on the crown plate: %s" % m.blocks.get((ax, ay - 1, az)))
    if any((ax, ay + j, az) in m.blocks for j in range(AIR_OVER_CROWN)):
        probs.append("the anchor has less than %d blocks of air over it" % AIR_OVER_CROWN)
    plate = [c for c in m.stack_cols if m.top[c][1] == m.crown]
    if len(plate) < 20:
        probs.append("the crown plate is %d columns: too small to roost on" % len(plate))
    if list(m.anchor) != pk.get("anchor"):
        probs.append("the heightmap puts the anchor at %s, the record says %s" % (list(m.anchor), pk.get("anchor")))
    # 7. the nest rule and the ceiling
    act = [b for b in jload("habitat_blocks.json")["blocks"] if b.get("style") == "activated" and not str(b["id"]).startswith(HABITAT_PREFIX)]
    for b in act:
        d = math.hypot(b["position"]["x"] - ax, b["position"]["z"] - az)
        if d < b["activated"]["spawn_range"] + pk["leash"]:
            probs.append("her leash overlaps Habitat Block %s (%.0f, needs %d)" % (b["id"], d, b["activated"]["spawn_range"] + pk["leash"]))
    col = doc["colony"]
    for s in m.skerries:
        hx, hy, hz = s["habitat"]
        d = math.hypot(hx - ax, hz - az)
        if d < col["spawn_range"] + pk["leash"]:
            probs.append("rock %d's block is %.1f from her anchor (needs %d)" % (s["k"], d, col["spawn_range"] + pk["leash"]))
        if m.blocks.get((hx, hy, hz)) is None:
            probs.append("rock %d's Habitat Block position %s is not in its rock" % (s["k"], (hx, hy, hz)))
    sub, tier, ceiling = SR._sub_of(*r["site"]["centre"])
    near = nearest_land_subregion(m)
    if near is None:
        probs.append("no land sub-region with a table within reach to read a ceiling from")
    else:
        if pk["level"] > near[2]:
            probs.append("L%d over %s's tier-%s ceiling %d" % (pk["level"], near[0], near[1], near[2]))
        if near[0] != r["subregion"]:
            probs.append("the nearest land sub-region is %s, the record says %s" % (near[0], r["subregion"]))
    if m.top and box_of(m) != r.get("bbox"):
        probs.append("the writes' box is %s, the record's bbox %s" % (box_of(m), r.get("bbox")))
    return probs, {"nearest_authored": best, "corridor": cbest, "path": dp, "ferry": fd, "sub_at_centre": (sub, tier, ceiling),
                   "nearest_land_sub": near}


def nearest_land_subregion(m):
    """(id, tier, next_cap) of the closest land sub-region WITH a table, found by walking west from the centre along z to
    the first column inside one: the sea here is in no polygon (SR._sub_of is None), the coast's own is the ceiling."""
    for x in range(m.cx, m.cx - 400, -4):
        s = SR._sub_of(x, m.cz)
        if s[0]:
            return s
    return None


# ------------------------------------------------------------------ the pack


def build_lines(m, box):
    out = ["# Generated by tools/rookery.py from data/rookery.json: Gull Rock, the stack and its six tidal rocks",
           "# chunks-loaded-by: the re-application R9RK (forceload add %d %d %d %d over RCON before this runs)" % tuple(box),
           "# the rock, bottom up: every column is water; nothing here is written on dry land"]
    out += SR._runs(m.blocks)
    return out


def files(doc, g, wet=None, check=True):
    import resident_encounters as RE
    m = model(doc, g, wet)
    if check:
        probs, _meas = siting(doc, m)
        if probs:
            raise RookeryError("rookery: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = doc["build"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    box = box_of(m)
    r = doc["residents"][0]
    fn = {}
    sh = SR.shim(doc)
    lines = build_lines(m, box)
    bad = function_limits.check_lines(lines, "build")
    if bad:
        raise RookeryError("build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    fn["build"] = lines
    e = SR.resident_record(r)
    a = m.anchor
    i = e["id"]
    rf = RE.resident_files(sh, e, a, [], [], box)
    rf.pop("%s/dress" % i, None)
    fn.update(rf)
    fn["spawn_at"] = ["# a macro, so the mod's command is parsed when it runs (EXP-046, .claude/rules/datapacks.md)",
                      "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]
    fn["load"] = ["# the rookery's keeper state (tools/rookery.py, on tools/resident_encounters.py's keeper).",
                  "# A clock that has never been set starts READY (respawn ticks already elapsed), so a fresh world fills at once",
                  "scoreboard objectives add %s dummy" % obj,
                  "scoreboard players set #resp %s %d" % (obj, int(b["respawn_ticks"])),
                  "execute store result score #ready %s run time query gametime" % obj,
                  "scoreboard players operation #ready %s -= #resp %s" % (obj, obj),
                  "execute unless score #%s.gone %s matches -2147483648.. run scoreboard players operation #%s.gone %s = #ready %s"
                  % (i, obj, i, obj, obj),
                  "execute unless score #%s.abs %s matches -2147483648.. run scoreboard players set #%s.abs %s 0" % (i, obj, i, obj),
                  "schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"])]
    fn["keeper"] = ["execute store result score #now %s run time query gametime" % obj,
                    "execute if loaded %d %d %d run function %s:%s/%s/keep" % (a[0], a[1], a[2], ns, F, i),
                    "schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"])]
    out = {"data/%s/function/%s/%s.mcfunction" % (ns, F, n): "\n".join(v) + "\n" for n, v in fn.items()}
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/load" % (ns, F)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: Gull Rock, the rookery (tools/rookery.py)"}}, indent=2) + "\n"
    return out, m


# ------------------------------------------------------------------ the records (Habitat Blocks and the pool)


def habitat_records(doc, m):
    col = doc["colony"]
    out = []
    for s in m.skerries:
        x, y, z = s["habitat"]
        out.append({"id": "%s%d" % (HABITAT_PREFIX, s["k"]),
                    "place": "Gull Rock, tidal rock %d of 6 (bearing %d from the stack, %d out): in its rock one block under the top"
                             % (s["k"], s["bearing"], doc["skerries"]["ring_radius"]),
                    "pool": "cobblers:%s" % col["pool"], "style": "activated", "replace_spawns": False,
                    "position": {"x": x, "y": y, "z": z}, "mimic": "minecraft:stone",
                    "activated": {"spawn_range": col["spawn_range"], "chance": col["chance"], "trigger": col["trigger"],
                                  "cancel_range": col["cancel_range"], "max_spawns_per_activation": col["max_spawns_per_activation"],
                                  "max_spawns": col["max_spawns"]},
                    "status": "planned",
                    "why": "data/rookery.json colony: written by tools/rookery.py records --write from its model, in rock its "
                           "build pass writes (the mimic is that rock). Keeps up to %d of the colony alive within %d, the elder "
                           "nests' and Driftmouth Isle's settings; cancel_range %d, so the strait's own spawns continue. %d "
                           "blocks from the Gullmother's anchor, the nearest the nest rule allows. Over-water ACTIVATED spawning "
                           "is not verified" % (col["max_spawns"], col["spawn_range"], col["cancel_range"], doc["skerries"]["ring_radius"])})
    return out


def pool_records(doc, spawns=None):
    spawns = spawns or json.loads(SPAWNS.read_text(encoding="utf-8"))
    col = doc["colony"]
    lo, hi = col["level_band"]["minimum"], col["level_band"]["maximum"]
    level = "%d-%d" % (lo, hi)
    rar = spawns["rarity"]
    evo = {"pelipper": "Wingull evolves at 25, under the band's floor %d" % lo,
           "swanna": "Ducklett evolves at 35, under the band's floor %d" % lo,
           "altaria": "Swablu evolves at 35, under the band's floor %d" % lo,
           "kilowattrel": "Wattrel evolves at 25, under the band's floor %d" % lo}
    hab, top = [], []
    derived = {}
    for e in spawns["entries"]:
        if e.get("scope") != col["pool"] and e.get("spawnable_position"):
            derived.setdefault(e["species"].split()[0].lower(), []).append(e["spawnable_position"])
    for ro in col["roster"]:
        sp = ro["pokemon"]
        why = ("final stage: " + evo[sp]) if sp in evo else "base stage with no level evolution inside the band"
        bucket, weight = rar[ro["rarity"]]["bucket"], float(rar[ro["rarity"]]["family_weight"])
        hab.append({"species": sp.capitalize(), "pokemon": sp, "family": ro["family"], "family_priority": ro["rarity"],
                    "ambient": True, "eligibility_reason": why, "level": level, "bucket": bucket, "weight": weight,
                    "conditions": {}})
        entry = {"id": "habitat.%s.%s" % (col["pool"], sp), "species": sp, "bucket": bucket, "level": level, "weight": weight,
                 "ambient": True, "scope": col["pool"], "mechanism": "habitat_block", "conditions": {},
                 "eligibility_reason": why, "spawnable_position": ro["position"]}
        if ro.get("position_why"):
            entry["spawnable_position_authored"] = {"position": ro["position"], "why": ro["position_why"]}
        top.append(entry)
    r = doc["residents"][0]
    pool = {"id": col["pool"], "display_name": "Gull Rock's colony",
            "intended_location": "the sea round Gull Rock (%d, %d): six activated Habitat Blocks in its tidal rocks, %d blocks "
                                 "from the stack (data/habitat_blocks.json %s*), each keeping up to %d alive within %d"
                                 % (r["site"]["centre"][0], r["site"]["centre"][1], doc["skerries"]["ring_radius"],
                                    HABITAT_PREFIX, col["max_spawns"], col["spawn_range"]),
            "mechanism": "habitat_block", "replace_spawns": False,
            "level_band": {"minimum": lo, "maximum": hi},
            "why": "data/rookery.json colony: %s %s" % (col["level_band_why"], col["roster_why"]),
            "placement_status": "pending_or_authored_world_asset", "entries": hab}
    return {"habitat": pool, "entries": top}


def write_records(doc, m):
    habs = habitat_records(doc, m)
    pool = pool_records(doc)
    hd = json.loads(HABITATS.read_text(encoding="utf-8"))
    hd["blocks"] = [b for b in hd["blocks"] if not str(b.get("id", "")).startswith(HABITAT_PREFIX)] + habs
    sd = json.loads(SPAWNS.read_text(encoding="utf-8"))
    pid = pool["habitat"]["id"]
    sd["habitats"] = [h for h in sd["habitats"] if h.get("id") != pid] + [pool["habitat"]]
    sd["entries"] = [e for e in sd["entries"] if e.get("scope") != pid] + pool["entries"]
    for path, d in ((HABITATS, hd), (SPAWNS, sd)):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    return habs, pool


# ------------------------------------------------------------------ the presence probes


def presence_probes(doc, m):
    """data/world_probes.json's shape: block probes from this model's own blocks, and the Gullmother."""
    rows = []
    ax, ay, az = m.anchor
    rows.append({"what": "the crown plate under the Gullmother", "block": [ax, ay - 1, az, m.blocks[(ax, ay - 1, az)]], "expect": True})
    for j in range(AIR_OVER_CROWN):
        rows.append({"what": "air over the crown (%d)" % (j + 1), "block": [ax, ay + j, az, "minecraft:air"], "expect": True})
    mid = (m.cx, m.sea + 6, m.cz)
    rows.append({"what": "the stack's core", "block": [mid[0], mid[1], mid[2], m.blocks[mid]], "expect": True})
    for n, (x, y, z) in enumerate(m.ledge_nests[:3] + m.crown_nest[:1]):
        rows.append({"what": "a nest of hay (%d)" % (n + 1), "block": [x, y, z, base(m.blocks[(x, y, z)])], "expect": True})
    guano = sorted(k for k, v in m.blocks.items() if v == "minecraft:calcite" and k[1] < m.crown)
    if guano:
        x, y, z = guano[len(guano) // 2]
        rows.append({"what": "guano on a face", "block": [x, y, z, "minecraft:calcite"], "expect": True})
    for s in m.skerries:
        sx, sz = s["peak"]
        rows.append({"what": "tidal rock %d: its top" % s["k"], "block": [sx, s["top"], sz, m.blocks[(sx, s["top"], sz)]], "expect": True})
        hx, hy, hz = s["habitat"]
        rows.append({"what": "tidal rock %d: its Habitat Block (after R9E)" % s["k"],
                     "block": [hx, hy, hz, "cobblemon:habitat_block"], "expect": True})
    rows.append({"what": "open water between the stack and the nearest rock (the stack did not fill the strait)",
                 "block": [m.cx - 22, m.sea, m.cz, "minecraft:water"], "expect": True})
    i = doc["residents"][0]["pokemon"]["id"]
    sp = doc["residents"][0]["pokemon"]["species"]
    rows.append({"what": "the Gullmother present after R18RK (ungated)",
                 "entity": "@e[type=cobblemon:pokemon,tag=cobblers.res.%s,nbt={Pokemon:{Species:\"%s\"}}]" % (i, sp),
                 "count": 1, "hold": [ax, ay, az]})
    return {PROBE_KEY: rows}


# ------------------------------------------------------------------ the re-application


def _built(doc=None, g=None):
    import ground as G
    doc = doc or load()
    g = g or G.load()
    return doc, g, model(doc, g)


def placement_steps(doc=None, g=None):
    """R9RK, BEFORE R9E: hold the site's box, build, release."""
    doc, g, m = _built(doc, g)
    b = doc["build"]
    hold = "%d %d %d %d" % tuple(box_of(m))
    return [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (b["namespace"], b["folder"])),
            ("cmd", "forceload remove " + hold)]


def entity_steps(doc=None, g=None):
    """R18RK, after R18FS: the Gullmother summoned (guarded on tag AND species: THE SUMMON GUARD) and bound, inside a
    forceload of the site's box."""
    import resident_encounters as RE
    doc, g, m = _built(doc, g)
    b = doc["build"]
    sh = SR.shim(doc)
    e = SR.resident_record(doc["residents"][0])
    hold = "%d %d %d %d" % tuple(box_of(m))
    return [("cmd", "forceload add " + hold), ("wait", 3), ("cmd", RE.summon_command(sh, e, m.anchor)), ("wait", 1),
            ("fn", "%s:%s/%s/bind_new" % (b["namespace"], b["folder"], e["id"])), ("cmd", "forceload remove " + hold)]


# ------------------------------------------------------------------ the report


def measurements(doc, m, g):
    """Numbers the design note quotes, all from the heightmap and the model."""
    sea, cx, cz = m.sea, m.cx, m.cz
    out = {}
    row = [(x, g(x, cz)) for x in range(cx, cx - 260, -1)]
    dry = [x for x, h in row if h > sea]
    out["first_dry_x"] = dry[0]
    out["shore_to_centre"] = cx - dry[0]
    depth = {x: sea - g(x, cz) for x in range(dry[0], cx + 1)}
    wade = [x for x in sorted(depth) if depth[x] <= 1]
    out["wading_ends_x"] = max(x for x in wade if all(depth[xx] <= 1 for xx in range(dry[0], x + 1)))
    deep_x = next(x for x in sorted(depth) if depth[x] >= 2 and x > out["wading_ends_x"])
    foot = min(x for x, z in m.stack_cols if z == cz)
    out["deep_from_x"] = deep_x
    out["swim_to_stack_foot"] = foot - deep_x
    skx = min(x for s in m.skerries for x, z in s["cols"] if abs(z - cz) <= 12)
    out["swim_to_nearest_rock"] = skx - deep_x
    out["stack_foot_x"] = foot
    # line of sight to the Gullmother's head along z = cz: the westmost run of columns from which it is seen
    head = m.crown + 1 + 3
    seen = []
    for x in range(cx - 460, cx - 40, 2):
        eye = g(x, cz) + 1.62
        ok = True
        for i in range(1, 160):
            t = i / 160.0
            xx = x + (cx - x) * t
            if g(int(round(xx)), cz) > eye + (head - eye) * t and t < 0.96:
                ok = False
                break
        seen.append((x, ok))
    out["seen_from_x"] = [x for x, ok in seen if ok][:1] and [x for x, ok in seen if ok][0]
    out["seen_from_ground"] = g(out["seen_from_x"], cz) if out["seen_from_x"] else None
    out["blocks"] = len(m.blocks)
    out["columns"] = len(m.top)
    out["plate_columns"] = len([c for c in m.stack_cols if m.top[c][1] == m.crown])
    out["stack_bed"] = m.stack_bed
    out["rock_beds"] = [(s["k"], s["bed_min"]) for s in m.skerries]
    return out


def report(doc, g):
    m = model(doc, g)
    probs, meas = siting(doc, m)
    me = measurements(doc, m, g)
    r = doc["residents"][0]
    na = meas["nearest_authored"]
    lines = ["Gull Rock centre %s sea y%d crown y%d anchor %s; %d columns, %d blocks, bbox %s"
             % (r["site"]["centre"], m.sea, m.crown, list(m.anchor), me["columns"], me["blocks"], box_of(m)),
             "  stack bed y%d-%d; crown plate %d columns; %d ledge nests, %d crown nests; skerry beds %s"
             % (m.stack_bed[0], m.stack_bed[1], me["plate_columns"], len(m.ledge_nests), len(m.crown_nest), me["rock_beds"]),
             "  beach: last dry x%d (%d west of the centre); wading to x%d; deep (>= 2) from x%d; swim to the stack's foot (x%d) %d, to the nearest rock %d"
             % (me["first_dry_x"], me["shore_to_centre"], me["wading_ends_x"], me["deep_from_x"], me["stack_foot_x"],
                me["swim_to_stack_foot"], me["swim_to_nearest_rock"]),
             "  the Gullmother's head is in sight from x%s (ground y%s) westward along z=%d" % (me["seen_from_x"], me["seen_from_ground"], m.cz),
             "  nearest authored %.0f (our column %s to data/%s); corridor box %.0f (%s); route path %.0f; ferry crossing %.0f"
             % (na[0], tuple(int(v) for v in na[1]), na[2], meas["corridor"][0], meas["corridor"][2], meas["path"], meas["ferry"]),
             "  ceiling: nearest land sub-region %s" % (meas["nearest_land_sub"],)]
    for s in m.skerries:
        lines.append("  rock %d bearing %d centre %s top y%d bed >= y%d block %s" % (s["k"], s["bearing"], s["centre"], s["top"], s["bed_min"], s["habitat"]))
    for p in probs:
        lines.append("  PROBLEM %s" % p)
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "report", "records", "probes"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--write", action="store_true", help="records / probes: replace this build's entries in the shared files")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.cmd == "report":
        print("\n".join(report(doc, g)))
        return 0
    m = model(doc, g)
    if a.cmd == "records":
        if a.write:
            habs, pool = write_records(doc, m)
            print("wrote %d habitat blocks and 1 pool with %d entries" % (len(habs), len(pool["entries"])))
        else:
            print(json.dumps({"habitat_blocks": habitat_records(doc, m), "pool": pool_records(doc)}, indent=1)[:4000])
        return 0
    if a.cmd == "probes":
        probes = presence_probes(doc, m)
        if a.write:
            d = json.loads(PROBES.read_text(encoding="utf-8"))
            d["places"].update(probes)
            with open(PROBES, "w", encoding="utf-8", newline="\n") as fh:      # the file's own LF, on any platform
                fh.write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
            print("wrote %d probes into data/world_probes.json under %r" % (len(probes[PROBE_KEY]), PROBE_KEY))
        else:
            print(json.dumps(probes, indent=1)[:3000])
        return 0
    written, m = files(doc, g)
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in written.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    n = sum(1 for rel, t in written.items() if rel.endswith("/build.mcfunction")
            for line in t.splitlines() if line and not line.startswith("#"))
    print("rookery: %d files -> %s (build: %d commands, %d blocks)" % (len(written), out, n, len(m.blocks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
