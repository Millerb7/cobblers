#!/usr/bin/env python
"""Hummock Mere (data/hummock_mere.json): a large swamp monster in a den that is a drowned grove, not a cave.

The owner, 2026-10-09: "a large swamp monster in a den", on the model of the Ursaluna den: a creature, a place that
suits it, strong enough that meeting it early is a mistake. The Ursaluna den's MECHANISM is copied (a named resident, a
level well over the place's cap, a catch gate, Cobblemon's scale_modifier property); its FORM is not. Here:

  the place    a flooded flat on the Marshy Marsh's east shore (the lake is a block deep there). Eight mangroves stand in
               a ring in the shallows, leaning in; their crowns close over a round mud island; a green froglight hangs
               under each crown. A furrow of dark mud runs from the dry spit to the island's foot; a punt rots on the
               spit by a warning sign. NO WATER IS PLACED: the water is the lake's own, the roots are waterlogged where
               they stand under the surface, and no block of data/spawn_blocks.json is written.
  the creature a Clodsire (L52, scale_modifier 2.2) asleep on the island, on tools/resident_encounters.py's keeper,
               called not copied (through tools/southern_residents.py's shim): dormant (NoAI) on its spot until a
               player is within the trigger, leashed, respawned on the 30-minute clock, never touched once the blackout
               has made it a guardian. Its catch gate is the level-cap refusal: nothing is built for it.
  the rumour   a sign on Route 6, 80 blocks outside Fenhide, saying only that something huge sleeps in the east mere.

Every Y is the canonical heightmap's rounded ground (tools/ground.py), never a world's; the lake level is
tools/water_mask.py's (through resident_encounters.Wet). The siting rules fail the build (data/hummock_mere.json
rules): authored clearance (the lake's own outline excepted), route corridor boxes, 200 from every town, 128 from every
route path, the leash clear of every activated Habitat Block, the level over the tier's cap, no spawn-condition block,
and no clear that could drain the lake. These are the builder's guards, not an audit: the independent audit is
tools/hummock_mere_audit.py.

  python tools/hummock_mere.py [--source-root R] [--out DIR]    write build/datapacks/cobblers_hummock_mere
  python tools/hummock_mere.py --report                          the site as measured, the checks, the steps
  python tools/hummock_mere.py --probes                          write this place's probes into data/world_probes.json

The re-application (tools/reapply.py): placement_steps() is R9HM, BEFORE R9E with the other block passes (after R9FS);
entity_steps() is R18HM, after R18FS: the resident summoned under the summon guard and bound.
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

DATA = ROOT / "data" / "hummock_mere.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_hummock_mere"
PROBES = ROOT / "data" / "world_probes.json"
SCHEMA = "cobblers.hummock-mere/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
KINDS = ("bed_strip", "mound", "mangrove", "ground_blocks", "signs")
CLEAR_HALF = 20          # the clear box round the centre: x and z +-20
CLEAR_UP = 18            # ... from lake level + 1 to lake level + 18 (41 x 41 x 18 = 30,258 blocks, under /fill's 32,768)
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class MereError(SystemExit):
    pass


jload = SR.jload
base = SR.base


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise MereError("%s: schema must be %s" % (path, SCHEMA))
    if len(doc["residents"]) != 1:
        raise MereError("this file holds one place")
    r = doc["residents"][0]
    for p in r["pieces"]:
        if p["kind"] not in KINDS:
            raise MereError("%s: unknown piece kind %s" % (r["id"], p["kind"]))
    pk = r["pokemon"]
    if not (0 < pk["trigger"] < pk["leash"]):
        raise MereError("%s: the trigger must be inside the leash" % r["id"])
    return doc


# ------------------------------------------------------------------ the site plan


def lake_level(s):
    L = s.wet.level(s.cx, s.cz)
    if L is None:
        raise MereError("%s: the centre (%d, %d) is dry; the nest stands in the lake's shallows" % (s.r["id"], s.cx, s.cz))
    if int(L) != int(s.r["site"]["water_level"]):
        raise MereError("%s: the lake is at y%s, the record says y%s" % (s.r["id"], L, s.r["site"]["water_level"]))
    return int(L)


def mound_top(d, profile, L):
    """Surface y of the island at distance d from its centre, or None outside it. profile: [[radius, dy over lake level]]
    outward, the first radius that holds d wins."""
    for rad, dy in profile:
        if d <= rad:
            return L + int(dy)
    return None


def piece_bed_strip(s, p, salt):
    """The ground's top block (the bed, or the spit's grass) replaced: nothing is raised, nothing cleared."""
    cols = set()
    for seg in p["segments"]:
        cols.update(SR._segment_cols(seg[0], seg[1], p.get("half_width", 0)))
    for dx, dz in sorted(cols):
        x, z = s.cx + dx, s.cz + dz
        s.put(x, s.g(x, z), z, SR._pick(p["palette"], x, z, salt))


def piece_mound(s, p, L):
    ox, oz = p["at"]
    R = float(p["radius"])
    tops = {}
    for dx in range(-int(R) - 1, int(R) + 2):
        for dz in range(-int(R) - 1, int(R) + 2):
            top = mound_top(math.hypot(dx, dz), p["profile"], L)
            if top is None:
                continue
            x, z = s.cx + ox + dx, s.cz + oz + dz
            gy = s.g(x, z)
            tops[(x, z)] = top
            for y in range(gy + 1, top):
                s.put(x, y, z, "minecraft:mud")
            if top > gy:
                s.put(x, top, z, SR._pick(p["palette"], x, z, 7))
    s.floors[p["name"]] = max(tops.values())
    s.mound = tops


def _unit(dx, dz):
    n = math.hypot(dx, dz) or 1.0
    return dx / n, dz / n


def root(s, x, y, z, L):
    """A mangrove root block, waterlogged ONLY where water stands in its own cell: a wet column, above the bed, at or
    under the lake level. A waterlogged block on dry land (or inside the ground) is a water source and leaks."""
    wl = s.wet(x, z) and s.g(x, z) < y <= L
    return "minecraft:mangrove_roots[waterlogged=%s]" % ("true" if wl else "false")


def piece_mangrove(s, p, L):
    """Trees round the centre: trunk (leaning inward), prop roots (waterlogged under the surface), a persistent leaf crown
    with a froglight at its lowest centre, vines on the trunk's inward face."""
    top_y = L + int(p["height"])
    c = p["crown"]
    s.trees = []
    for k, t in enumerate(p["trees"]):
        b = math.radians(t["bearing"])
        bx = s.cx + int(round(t["r"] * math.sin(b)))
        bz = s.cz + int(round(-t["r"] * math.cos(b)))
        ux, uz = _unit(s.cx - bx, s.cz - bz)
        gy = s.g(bx, bz)
        trunk = []
        px, pz = bx, bz
        for y in range(gy + 1, top_y + 1):
            sh = max(0, y - (L + 1)) * float(p["lean"])
            nx, nz = bx + int(round(sh * ux)), bz + int(round(sh * uz))
            # up first, then sideways one axis at a time: every block is joined to the last by a face, never a corner
            trunk.append((px, y, pz))
            if nx != px:
                trunk.append((nx, y, pz))
            if nz != pz:
                trunk.append((nx, y, nz))
            px, pz = nx, nz
        for (x, y, z) in trunk:
            s.put(x, y, z, "minecraft:mangrove_log[axis=y]")
        tx, ty, tz = trunk[-1]
        # prop roots: out and down from the base, waterlogged where they stand at or under the surface
        for a in range(int(p["arms"])):
            ang = math.radians(t["bearing"] + 180 + 360.0 * a / int(p["arms"]) + 17 * k)
            ex, ez = math.sin(ang), -math.cos(ang)
            last = None
            for i in range(1, int(p["arm_len"]) + 1):
                x, z = bx + int(round(i * ex)), bz + int(round(i * ez))
                y = L + 3 - i
                last = (x, y, z)
                s.put(x, y, z, root(s, x, y, z, L))
            x, y, z = last
            for yy in range(s.g(x, z) + 1, y):
                s.put(x, yy, z, root(s, x, yy, z, L))
        # the crown: an ellipsoid of persistent leaves, centred `in` blocks inward of the trunk's top and `up` above it
        ccx, ccy, ccz = tx + int(round(c["in"] * ux)), ty + int(c["up"]), tz + int(round(c["in"] * uz))
        rr, ry = float(c["r"]), float(c["ry"])
        trunk_set = set(trunk)
        leaves = []
        for dx in range(-int(rr) - 1, int(rr) + 2):
            for dz in range(-int(rr) - 1, int(rr) + 2):
                for dy in range(-int(ry) - 1, int(ry) + 2):
                    if (dx / rr) ** 2 + (dy / ry) ** 2 + (dz / rr) ** 2 <= 1.0 and (ccx + dx, ccy + dy, ccz + dz) not in trunk_set:
                        leaves.append((ccx + dx, ccy + dy, ccz + dz))
        low = min(y for _x, y, _z in leaves)
        light = (ccx, low, ccz)
        for (x, y, z) in leaves:
            s.put(x, y, z, p["light"] if (x, y, z) == light else "minecraft:mangrove_leaves[persistent=true]")
        s.trees.append({"base": (bx, bz), "trunk": trunk, "crown": (ccx, ccy, ccz), "light": light, "low_leaf": low})
        # vines on the inward face of the trunk's top five blocks (the trunk is the support)
        sx = 1 if abs(ux) >= abs(uz) and ux > 0 else -1 if abs(ux) >= abs(uz) else 0
        sz = 0 if sx else (1 if uz > 0 else -1)
        face = {(1, 0): "west", (-1, 0): "east", (0, 1): "north", (0, -1): "south"}[(sx, sz)]
        for (x, y, z) in trunk[-5:]:
            vx, vz = x + sx, z + sz
            if (vx, y, vz) not in s.solid and (vx, y, vz) not in s.hung:
                s.put(vx, y, vz, "minecraft:vine[%s=true]" % face, hung=True)


def piece_signs(s, p):
    for sg in p["signs"]:
        x, z = s.cx + sg["at"][0], s.cz + sg["at"][1]
        if not s.dry(x, z):
            raise MereError("%s %s: the sign at (%d, %d) stands in water" % (s.r["id"], p["name"], x, z))
        gy = s.g(x, z)
        s.put(x, gy + 1, z, {"sign": {"wood": sg["wood"], "rotation": sg["rotation"], "lines": sg["lines"]}})
        s.clear_col(x, z, gy + 1, gy + 3)
        s.signs.append((x, gy + 1, z))


def plan(doc, r, g, wet):
    s = SR.Site(doc, r, g, wet)
    s.signs = []
    L = lake_level(s)
    s.L = L
    for i, p in enumerate(r["pieces"]):
        k = p["kind"]
        if k == "bed_strip":
            piece_bed_strip(s, p, i + 1)
        elif k == "mound":
            piece_mound(s, p, L)
        elif k == "mangrove":
            piece_mangrove(s, p, L)
        elif k == "ground_blocks":
            SR.piece_ground_blocks(s, p)
        elif k == "signs":
            piece_signs(s, p)
    # the one clear: logs, leaves and plants ABOVE the lake, over the whole nest. It starts at lake level + 1 so it can
    # never touch water (#minecraft:replaceable holds water); the painted marsh's own trees in the box go
    s.clears.append((s.cx - CLEAR_HALF, L + 1, s.cz - CLEAR_HALF, s.cx + CLEAR_HALF, L + CLEAR_UP, s.cz + CLEAR_HALF))
    return s


def anchor(s, r):
    pk = r["pokemon"]
    x, z = s.cx + pk["at"][0], s.cz + pk["at"][1]
    return x, s.mound[(x, z)] + 1, z


def check_standing(s, r):
    """The creature's spot: a mound column, and nothing written in the six blocks over it."""
    a = anchor(s, r)
    blocks = dict(s.solid)
    blocks.update(s.hung)
    for dy in range(0, 6):
        if (a[0], a[1] + dy, a[2]) in blocks:
            raise MereError("%s: %s is written %d over the creature's spot" % (r["id"], blocks[(a[0], a[1] + dy, a[2])], dy))
    return a


def waysign(doc, g, wet):
    """(x, y, z, rotation, route path index) of the roadside sign: `beyond_blocks` path points after the route leaves
    `after_town`'s footprint, `offset` blocks to the traveller's `side`."""
    w = doc["waysign"]
    path = jload("route_paths.json")["paths"][w["route"]]
    town = next(t for t in jload("towns.json")["towns"] if t["id"] == w["after_town"])
    f = town["footprint"]
    out = next(i for i, (x, z) in enumerate(path) if not (f["min_x"] <= x <= f["max_x"] and f["min_z"] <= z <= f["max_z"]))
    i = out + int(w["beyond_blocks"])
    (x0, z0), (x1, z1) = path[i - 3], path[i + 3]
    vx, vz = _unit(x1 - x0, z1 - z0)
    # left of travel in a z-down map (x east, z south): (vz, -vx)
    lx, lz = (vz, -vx) if w["side"] == "left" else (-vz, vx)
    x, z = path[i][0] + int(round(lx * w["offset"])), path[i][1] + int(round(lz * w["offset"]))
    if wet(x, z):
        raise MereError("the waysign's column (%d, %d) is wet" % (x, z))
    nx, nz = -vx, -vz          # the face points back at the traveller
    rot = int(round(math.degrees(math.atan2(-nx, nz)) / 22.5)) % 16
    return x, g(x, z) + 1, z, rot, i


def waysign_lines(doc, g, wet):
    x, y, z, rot, _i = waysign(doc, g, wet)
    w = doc["waysign"]
    spec = {"sign": {"wood": w["wood"], "rotation": rot, "lines": w["lines"]}}
    box = [x - 1, z - 1, x + 1, z + 1]
    return x, y, z, rot, box, [
        "# Generated by tools/hummock_mere.py from data/hummock_mere.json: the roadside warning",
        "# chunks-loaded-by: the re-application %s (forceload add %d %d %d %d over RCON before this runs)"
        % ((doc["build"]["steps"]["blocks"],) + tuple(box)),
        "fill %d %d %d %d %d %d minecraft:air replace #minecraft:replaceable" % (x, y, z, x, y + 2, z),
        "setblock %d %d %d %s" % (x, y, z, SR.state_of(spec))]


# ------------------------------------------------------------------ the siting rules (the builder's guards)


def authored_points(doc):
    """tools/southern_residents.py authored_points() with this file skipped whole and the records of rules.skip_records
    (the lake's own outline) skipped by id."""
    skip = set(doc["rules"]["skip_records"])
    pts = []

    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def walk(o, f):
        if isinstance(o, dict):
            if o.get("id") in skip:
                return
            if num(o.get("x")) and num(o.get("z")):
                pts.append((o["x"], o["z"], f))
            for v in o.values():
                walk(v, f)
        elif isinstance(o, list):
            if len(o) == 2 and all(num(v) for v in o):
                pts.append((o[0], o[1], f))
            elif len(o) == 3 and all(num(v) for v in o):
                pts.append((o[0], o[2], f))
                pts.append((o[0], o[1], f))
            elif len(o) == 4 and all(num(v) for v in o):
                x0, z0, x1, z1 = o
                if x1 >= x0 and z1 >= z0 and x1 - x0 < 2000 and z1 - z0 < 2000:
                    for xx in (x0, (x0 + x1) / 2.0, x1):
                        for zz in (z0, (z0 + z1) / 2.0, z1):
                            pts.append((xx, zz, f))
            else:
                for v in o:
                    walk(v, f)
    for p in sorted((ROOT / "data").glob("*.json")):
        if p.resolve() == DATA.resolve():
            continue
        doc_ = json.loads(p.read_text(encoding="utf-8"))
        if p.name == "world_probes.json":      # this place's own probes are not another system's authored points
            doc_["places"].pop("hummock_mere", None)
        walk(doc_, p.name)
    return pts


def _cols(s, extra):
    cols = set(s.cols) | {(e[0], e[2]) for e in extra}
    for c in s.clears:
        cols |= {(x, z) for x in range(c[0], c[3] + 1) for z in (c[2], c[5])}
        cols |= {(x, z) for z in range(c[2], c[5] + 1) for x in (c[0], c[3])}
    return cols


def siting(doc, r, s, extra, pts):
    import numpy as np
    rules = doc["rules"]
    probs = []
    P = np.array([(a, b) for a, b, _f in pts], float)
    F = [f for _a, _b, f in pts]
    cols = _cols(s, extra)
    C = np.array(sorted(cols), float)
    best = (1e9, None, None)
    for i in range(0, len(C), 256):
        blk = C[i:i + 256]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] < best[0]:
            best = (float(d[j]), tuple(blk[j[0]]), F[j[1]])
    m = rules["authored_clearance"]
    if best[0] < m:
        probs.append("%s: (%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                     % (r["id"], best[1][0], best[1][1], best[0], best[2], m))
    cprobs, cbest = SR.corridor_check(r["id"], cols, m)
    probs += cprobs
    tm = rules["town_clearance"]
    tbest = 1e9
    for t in jload("towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        for x, z in cols:
            d = math.hypot(max(f["min_x"] - x, x - f["max_x"], 0), max(f["min_z"] - z, z - f["max_z"], 0))
            tbest = min(tbest, d)
            if d < tm:
                probs.append("%s: (%d, %d) is %.0f from town %s's footprint (needs %d)" % (r["id"], x, z, d, t["id"], tm))
                break
    for k, zone in jload("rift_zones.json")["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                probs.append("%s: inside Rift zone %s" % (r["id"], k))
                break
    paths = np.array([p for pl in jload("route_paths.json")["paths"].values() for p in pl], float)
    dp = min(float(np.min(np.hypot(paths[:, 0] - x, paths[:, 1] - z))) for x, z in
             [(s.cx, s.cz)] + [(e[0], e[2]) for e in extra] + [(c[0], c[1]) for c in C[::97]])
    if dp < rules["path_clearance"]:
        probs.append("%s: %.0f blocks from a route path (needs %d)" % (r["id"], dp, rules["path_clearance"]))
    pk = r["pokemon"]
    ax, az = s.cx + pk["at"][0], s.cz + pk["at"][1]
    for b in jload("habitat_blocks.json")["blocks"]:
        if b.get("style") != "activated":
            continue
        d = math.hypot(b["position"]["x"] - ax, b["position"]["z"] - az)
        if d < b["activated"]["spawn_range"] + pk["leash"]:
            probs.append("%s: its leash overlaps Habitat Block %s (%.0f, needs %d)"
                         % (r["id"], b["id"], d, b["activated"]["spawn_range"] + pk["leash"]))
    sub, tier, ceiling = SR._sub_of(ax, az)
    if sub is None:
        probs.append("%s: the resident stands in no sub-region with a table" % r["id"])
    else:
        if sub != r["subregion"]:
            probs.append("%s: the resident stands in %s, the record says %s" % (r["id"], sub, r["subregion"]))
        cap = jload("encounter_design.json")["rules"]["tiers"][str(tier)]["cap"]
        if pk["level"] < cap + rules["level_over_cap_min"]:
            probs.append("%s: L%d is not %d over %s's tier-%s cap %d" % (r["id"], pk["level"], rules["level_over_cap_min"], sub, tier, cap))
    if SR._sub_of(s.cx, s.cz)[0] != r["subregion"]:
        probs.append("%s: the centre is in %s, the record says %s" % (r["id"], SR._sub_of(s.cx, s.cz)[0], r["subregion"]))
    cell = _cell(s.cx, s.cz)
    if cell != r["cell"]:
        probs.append("%s: the centre is in cell %s, the record says %s" % (r["id"], cell, r["cell"]))
    # the catch gate is the level-cap refusal: the first gym whose cap holds the level
    aces = jload("trainers.json")["generation_contract"]["gym_ace_levels"]
    # the cap a player holds after n badges is gym_ace_levels[n] (20 with none, 55 with seven), as the residents' table
    # in docs/world-building/RESIDENT_ENCOUNTERS.md 4.3 reads it: Old Jaw L25 is gym1, Wiremother L33 is gym3
    need = next((i for i, v in enumerate(aces) if v >= pk["level"]), None)
    if need is None or pk["gate"] != "gym%d_cleared" % need:
        probs.append("%s: the gate %s is not the first gym whose cap (%s, after gym n = ace n) holds L%d (gym %s)"
                     % (r["id"], pk["gate"], aces, pk["level"], need))
    return probs, {"nearest_authored": best, "path": dp, "corridor": cbest, "town": tbest}


def _cell(x, z):
    grid = jload("world.json")["grid"]
    sz = grid["cell_size"]
    return grid["row_labels"][int(z - grid["origin_z"]) // sz] + grid["column_labels"][int(x - grid["origin_x"]) // sz]


def check_all(doc, built, g, wet):
    r, s, a, extra, box = built
    pts = authored_points(doc)
    probs = siting(doc, r, s, extra, pts)[0]
    spawn = set(jload("spawn_blocks.json")["blocks"])
    bad = sorted({base(v) for v in list(s.solid.values()) + list(s.hung.values())} & spawn)
    if bad:
        probs.append("%s: writes spawn-condition blocks %s (data/spawn_blocks.json)" % (r["id"], bad))
    if any(c[1] <= s.L for c in s.clears):
        probs.append("%s: a clear starts at or under the lake level y%d (it would drain the lake)" % (r["id"], s.L))
    if a != tuple(r["pokemon"]["anchor"]):
        probs.append("%s: the heightmap puts the anchor at %s, the record says %s" % (r["id"], list(a), r["pokemon"]["anchor"]))
    if list(box) != r.get("bbox"):
        probs.append("%s: the writes' box is %s, the record's bbox %s" % (r["id"], box, r.get("bbox")))
    hr = doc["rules"]["headroom_blocks"]
    low = min(y for t in s.trees for y in [t["low_leaf"]])
    if low < a[1] + hr:
        probs.append("%s: the lowest leaf y%d is under the creature's headroom (anchor y%d + %d)" % (r["id"], low, a[1], hr))
    wx, wy, wz, rot, wbox, _lines = waysign_lines(doc, g, wet)
    if doc["waysign"].get("bbox") != wbox:
        probs.append("waysign: the box is %s, the record's bbox %s" % (wbox, doc["waysign"].get("bbox")))
    return probs


# ------------------------------------------------------------------ the pack


def sites(doc, g, wet=None):
    import resident_encounters as RE
    r = doc["residents"][0]
    wet = wet or RE.Wet(g, [tuple(r["site"]["centre"])])
    s = plan(doc, r, g, wet)
    a = check_standing(s, r)
    extra = [a] + list(s.signs)
    return r, s, a, extra, SR.box_of(s, extra), wet


def _props(doc, e):
    return "level=%d scale_modifier=%s" % (e["level"], doc["residents"][0]["pokemon"]["scale_modifier"])


def summon(doc, e, a):
    import resident_encounters as RE
    cmd = RE.summon_command(SR.shim(doc), e, a)
    plain = "level=%d" % e["level"]
    assert cmd.endswith(plain), cmd
    return cmd[:-len(plain)] + _props(doc, e)


def files(doc, g, wet=None, check=True):
    import resident_encounters as RE
    r, s, a, extra, box, wet = sites(doc, g, wet)
    built = (r, s, a, extra, box)
    if check:
        probs = check_all(doc, built, g, wet)
        if probs:
            raise MereError("hummock_mere: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = doc["build"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    fn = {}
    lines = SR.build_lines(doc, r, s, box)
    lines[0] = "# Generated by tools/hummock_mere.py from data/hummock_mere.json: %s" % r["name"]
    lines[1] = lines[1].replace("R9SR", b["steps"]["blocks"])
    bad = function_limits.check_lines(lines, "%s/build" % r["id"])
    if bad:
        raise MereError("%s/build: %d command(s) the server would refuse: %s" % (r["id"], len(bad), bad[:3]))
    fn["%s/build" % r["id"]] = lines
    wx, wy, wz, rot, wbox, wlines = waysign_lines(doc, g, wet)
    bad = function_limits.check_lines(wlines, "waysign/build")
    if bad:
        raise MereError("waysign/build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    fn["%s/build" % doc["waysign"]["id"]] = wlines
    sh = SR.shim(doc)
    e = SR.resident_record(r)
    i = e["id"]
    rf = RE.resident_files(sh, e, a, [], [], box)
    rf.pop("%s/dress" % i, None)
    # the spawn carries the size: the Ursaluna den's property (tools/ursaluna_cave.py spawn_at)
    sp = "%s/spawn" % i
    plain = 'props:"level=%d"' % e["level"]
    if not any(plain in ln for ln in rf[sp]):
        raise MereError("resident_encounters no longer writes %s into %s" % (plain, sp))
    rf[sp] = [ln.replace(plain, 'props:"%s"' % _props(doc, e)) for ln in rf[sp]]
    fn.update(rf)
    load_ = ["# Hummock Mere's keeper state (tools/hummock_mere.py, on tools/resident_encounters.py's keeper).",
             "# A clock that has never been set starts READY (respawn ticks already elapsed), so a fresh world fills at once",
             "scoreboard objectives add %s dummy" % obj,
             "scoreboard players set #resp %s %d" % (obj, int(b["respawn_ticks"])),
             "execute store result score #ready %s run time query gametime" % obj,
             "scoreboard players operation #ready %s -= #resp %s" % (obj, obj),
             "execute unless score #%s.gone %s matches -2147483648.. run scoreboard players operation #%s.gone %s = #ready %s"
             % (i, obj, i, obj, obj),
             "execute unless score #%s.abs %s matches -2147483648.. run scoreboard players set #%s.abs %s 0" % (i, obj, i, obj),
             "schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"])]
    keeper = ["execute store result score #now %s run time query gametime" % obj,
              "execute if loaded %d %d %d run function %s:%s/%s/keep" % (a[0], a[1], a[2], ns, F, i),
              "schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"])]
    fn["spawn_at"] = ["# a macro, so the mod's command is parsed when it runs (EXP-046, .claude/rules/datapacks.md)",
                      "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]
    fn["load"] = load_
    fn["keeper"] = keeper
    out = {"data/%s/function/%s/%s.mcfunction" % (ns, F, n): "\n".join(v) + "\n" for n, v in fn.items()}
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/load" % (ns, F)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: Hummock Mere (tools/hummock_mere.py)"}}, indent=2) + "\n"
    return out, built


# ------------------------------------------------------------------ the re-application


def _built(doc=None, g=None):
    import ground as G
    doc = doc or load()
    g = g or G.load()
    return doc, g, sites(doc, g)


def placement_steps(doc=None, g=None):
    """R9HM, BEFORE R9E: hold the nest's box, build it, release; then the same for the roadside sign."""
    doc, g, (r, s, a, extra, box, wet) = _built(doc, g)
    b = doc["build"]
    wx, wy, wz, rot, wbox, _l = waysign_lines(doc, g, wet)
    steps = []
    for name, bx in ((r["id"], box), (doc["waysign"]["id"], wbox)):
        hold = "%d %d %d %d" % tuple(bx)
        steps += [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/%s/build" % (b["namespace"], b["folder"], name)),
                  ("cmd", "forceload remove " + hold)]
    return steps


def entity_steps(doc=None, g=None):
    """R18HM, after R18FS: the resident summoned over RCON (guarded on tag AND species: THE SUMMON GUARD) and bound,
    inside a forceload of the nest's box. Ungated, so the step is not empty."""
    doc, g, (r, s, a, extra, box, wet) = _built(doc, g)
    b = doc["build"]
    e = SR.resident_record(r)
    hold = "%d %d %d %d" % tuple(box)
    return [("cmd", "forceload add " + hold), ("wait", 3), ("cmd", summon(doc, e, a)), ("wait", 1),
            ("fn", "%s:%s/%s/bind_new" % (b["namespace"], b["folder"], e["id"])), ("cmd", "forceload remove " + hold)]


# ------------------------------------------------------------------ the probes


def probes(doc, g):
    """This place's presence probes (data/world_probes.json places.hummock_mere): blocks the pack writes, read back from
    the plan, and the resident by its tag."""
    r, s, a, extra, box, wet = sites(doc, g)
    out = []
    cx, cz = s.cx, s.cz
    top = s.mound[(cx, cz)]
    out.append({"what": "the island's crest (mud or moss)", "block": [cx, top, cz, "minecraft:mud" if s.solid[(cx, top, cz)] == "minecraft:mud" else "minecraft:moss_block"], "expect": True})
    out.append({"what": "the island under the crest", "block": [cx, top - 1, cz, "minecraft:mud"], "expect": True})
    out.append({"what": "air over the creature's spot (feet + 4)", "block": [a[0], a[1] + 4, a[2], "minecraft:air"], "expect": True})
    for k in (0, 3):
        t = s.trees[k]
        x, y, z = t["trunk"][len(t["trunk"]) // 2]
        out.append({"what": "grove tree %d: trunk" % k, "block": [x, y, z, "minecraft:mangrove_log[axis=y]"], "expect": True})
        out.append({"what": "grove tree %d: the froglight under its crown" % k, "block": list(t["light"]) + ["minecraft:verdant_froglight"], "expect": True})
    sx, sy, sz = s.signs[0]
    out.append({"what": "the sign at the furrow's dry end", "block": [sx, sy, sz, "minecraft:mangrove_sign"], "expect": True})
    wx, wy, wz, rot, wbox, _l = waysign_lines(doc, g, wet)
    out.append({"what": "the roadside warning on Route 6", "block": [wx, wy, wz, "minecraft:mangrove_sign"], "expect": True})
    out.append({"what": "the Hummock (after R18HM)", "entity": "@e[type=cobblemon:pokemon,tag=cobblers.res.%s,x=%d,y=%d,z=%d,distance=..30]"
                % (r["pokemon"]["id"], a[0], a[1], a[2]), "count": 1, "hold": [a[0], a[1], a[2]]})
    return out


def write_probes(doc, g):
    d = json.loads(PROBES.read_text(encoding="utf-8"))
    d["places"]["hummock_mere"] = probes(doc, g)
    PROBES.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ CLI


def report(doc, g):
    r, s, a, extra, box, wet = sites(doc, g)
    probs, m = siting(doc, r, s, extra, authored_points(doc))
    na = m["nearest_authored"]
    sub = SR._sub_of(s.cx, s.cz)
    out = ["%s %s: centre %s ground y%d lake y%d sub %s tier %s cell %s; %d solid + %d hung blocks, bbox %s"
           % (r["id"], r["name"], r["site"]["centre"], g(s.cx, s.cz), s.L, sub[0], sub[1], _cell(s.cx, s.cz),
              len(s.solid), len(s.hung), box),
           "  nearest authored %.0f (our column %s to data/%s); corridor box %.0f; path %.0f; town %.0f"
           % (na[0], tuple(int(v) for v in na[1]), na[2], m["corridor"][0], m["path"], m["town"]),
           "  mound crest y%d, anchor %s, lowest leaf y%d (headroom needs y%d)"
           % (s.floors["the hummock"], list(a), min(t["low_leaf"] for t in s.trees), a[1] + doc["rules"]["headroom_blocks"]),
           "  sign at the spit %s" % list(s.signs[0])]
    wx, wy, wz, rot, wbox, _l = waysign_lines(doc, g, wet)
    out.append("  waysign %s rotation %d box %s (path index %d)" % ([wx, wy, wz], rot, wbox, waysign(doc, g, wet)[4]))
    for k, t in enumerate(s.trees):
        gb = g(*t["base"])
        out.append("  tree %d base %s bed y%d trunk %d blocks, top %s, crown %s, light %s" % (k, t["base"], gb, len(t["trunk"]),
                                                                                       t["trunk"][-1], t["crown"], t["light"]))
    for p in probs:
        out.append("  PROBLEM %s" % p)
    out.append("steps %s: %d actions; %s: %d actions" % (doc["build"]["steps"]["blocks"], len(placement_steps(doc, g)),
                                                         doc["build"]["steps"]["entities"], len(entity_steps(doc, g))))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print the site, the checks and the steps; write nothing")
    ap.add_argument("--probes", action="store_true", help="write this place's probes into data/world_probes.json")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.report:
        print("\n".join(report(doc, g)))
        return 0
    if a.probes:
        write_probes(doc, g)
        print("hummock_mere: %d probes -> data/world_probes.json places.hummock_mere" % len(probes(doc, g)))
        return 0
    written, built = files(doc, g)
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in written.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    n = sum(1 for rel, t in written.items() if rel.endswith("/build.mcfunction")
            for l in t.splitlines() if l and not l.startswith("#"))
    print("hummock_mere: %d files -> %s (build: %d commands)" % (len(written), out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
