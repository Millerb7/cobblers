#!/usr/bin/env python
"""The southern residents of data/southern_residents.json: a character with a situation, somewhere specific.

The owner, 2026-10-03: "The Lopunny house on the snow island is the model - a character with a situation, somewhere
specific, that you remember meeting. ... write and build more of them. The southern map is still the thinnest part of
the world - start there." Six sites in rows E-H, each a different kind of meeting. Every part is an existing, proven
piece; nothing here is new machinery:

  the sites      vanilla 1.21.1 blocks from small primitives (a structure on a levelled floor, surface work, blocks on
                 their own column's ground, a ring, a line of posts that walks into the sea), every Y from the canonical
                 heightmap's rounded ground (tools/ground.py), never from a world. A structure's floor is
                 max(ground under its footprint), with a foundation under it where the ground is lower (the Lopunny
                 house's convention). Nothing is written on a wet column but a post built for water. Every block is
                 checked against data/spawn_blocks.json (a block a spawn condition names would decide encounters) and
                 against the record's own allow-list. Plants, logs and leaves are cleared over each piece first.
  the NPCs       conversations in data/dialogue.json and quests in data/quests.json, compiled with every other one into
                 cobblers_dialogue by tools/compile_dialogue.py --all. An NPC who gives something through
                 grant_reward_once is recorded in data/rewards.json (npc_grant) and placed by tools/reapply.py's R9F,
                 as Hopgood is; this tool only checks that the record's npc_at is the spot it seats him on. Every
                 other NPC is placed by this tool's own step, after R17N, turned to its yaw (npc_seats' shape).
  the residents  the two named Pokemon run on tools/resident_encounters.py's own keeper, called here, not copied:
                 dormant (NoAI) on the spot until a player comes within the trigger, leashed, settled back asleep,
                 respawned on the gulch's clock, never conjured in front of anyone, never touched once the blackout
                 has made it a guardian (tag cobblers.guardian). They share Codex's resident tags (cobblers.res,
                 cobblers.res.<id>, cobblers.res_dormant) with their own objective, cobblers.sres.
  the cache      Bettany Oake's claim is a data/rewards.json cache (tools/rewards_pack.py gives it); the barrel at
                 the cairn is scenery this pack writes and never holds the reward.

The siting rules are checked here and fail the build (the brief of 2026-10-03, and tests/test_resident_siting.py's
rules for a big Pokemon): south of z 4096; every written block, NPC, anchor and cache at least rules.authored_clearance
from every x/z authored in any other data/*.json; outside the Mega farm box; away from the three new southern places;
every site at least rules.path_clearance from a route path; a resident's leash clear of every activated Habitat
Block's spawn_range; its level inside its sub-region's tier ceiling (data/encounter_design.json rules.hearts.next_cap).
These are the builder's guards, not an audit: the independent audit is another agent's (the report's checklist).

  python tools/southern_residents.py [--source-root R] [--out DIR]    write build/datapacks/cobblers_southern_residents
  python tools/southern_residents.py --report                          the sites as measured, the checks, the steps

The re-application (tools/reapply.py): placement_steps() is R9SR, BEFORE R9E with the other block passes;
entity_steps() is R18SR, after R18R: the ungated residents summoned and bound, then the NPCs R9F does not place.
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

DATA = ROOT / "data" / "southern_residents.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_southern_residents"
SCHEMA = "cobblers.southern-residents/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
KINDS = ("structure", "surface", "ground_blocks", "ring", "posts")
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class SouthError(SystemExit):
    pass


def jload(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise SouthError("%s: schema must be %s" % (path, SCHEMA))
    ids = [r["id"] for r in doc["residents"]]
    if len(ids) != len(set(ids)):
        raise SouthError("resident ids must be unique")
    for r in doc["residents"]:
        for p in r["pieces"]:
            if p["kind"] not in KINDS:
                raise SouthError("%s: unknown piece kind %s" % (r["id"], p["kind"]))
        pk = r.get("pokemon")
        if pk and not (0 < pk["trigger"] < pk["leash"]):
            raise SouthError("%s: the trigger must be inside the leash" % r["id"])
    return doc


def base(state):
    return state.split("[")[0].split("{")[0]


def sign(spec):
    """{"sign": {"wood", "wall": facing | "rotation": n, "lines": [...]}} -> a sign block state with its text."""
    s = spec["sign"]
    lines = (list(s["lines"]) + ["", "", "", ""])[:4]
    q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in lines)
    if "wall" in s:
        st = "minecraft:%s_wall_sign[facing=%s,waterlogged=false]" % (s["wood"], s["wall"])
    else:
        st = "minecraft:%s_sign[rotation=%d,waterlogged=false]" % (s["wood"], int(s["rotation"]))
    return "%s{front_text:{messages:[%s]}}" % (st, q)


def state_of(v):
    return sign(v) if isinstance(v, dict) else v


# ------------------------------------------------------------------ the site plan


class Site:
    """Every block one site writes, {(x, y, z): state} in two passes (the structure, then what hangs on it), and the
    clears that go first: (x0, y0, z0, x1, y1, z1, tag) boxes of logs, leaves and replaceable plants."""

    def __init__(self, doc, r, g, wet):
        self.doc, self.r, self.g, self.wet = doc, r, g, wet
        self.cx, self.cz = r["site"]["centre"]
        self.solid, self.hung, self.clears = {}, {}, []
        self.allowed = set(doc["blocks"]["ids"])
        self.floors = {}
        self.cols = set()

    def _check(self, st):
        b = base(st)
        if b not in self.allowed:
            raise SouthError("%s: %s is not in data/southern_residents.json blocks.ids" % (self.r["id"], b))

    def put(self, x, y, z, v, hung=False):
        st = state_of(v)
        self._check(st)
        (self.hung if hung else self.solid)[(x, y, z)] = st
        self.cols.add((x, z))

    def dry(self, x, z):
        return not self.wet(x, z)

    def clear_col(self, x, z, y0, y1):
        if y1 >= y0:
            self.clears.append((x, y0, z, x, y1, z))


def piece_structure(s, p):
    x0, z0, x1, z1 = p["footprint"]
    cols = [(s.cx + lx, s.cz + lz) for lx in range(x0, x1 + 1) for lz in range(z0, z1 + 1)]
    wet = [c for c in cols if s.wet(*c)]
    if wet:
        raise SouthError("%s %s: the footprint stands on water at %s" % (s.r["id"], p["name"], wet[:3]))
    B = max(s.g(x, z) for x, z in cols)
    s.floors[p["name"]] = B
    low = min(s.g(x, z) for x, z in cols)
    m = 1
    s.clears.append((s.cx + x0 - m, low + 1, s.cz + z0 - m, s.cx + x1 + m, B + int(p.get("clear_up", 12)), s.cz + z1 + m))
    found = p.get("foundation")
    for x, z in cols:
        for y in range(s.g(x, z) + 1, B):
            s.put(x, y, z, found)
    for f in p.get("fills") or []:
        a0, d0, b0, a1, d1, b1, v = f
        for lx in range(min(a0, a1), max(a0, a1) + 1):
            for dy in range(min(d0, d1), max(d0, d1) + 1):
                for lz in range(min(b0, b1), max(b0, b1) + 1):
                    s.put(s.cx + lx, B + dy, s.cz + lz, v)
    for lx, dy, lz, v in p.get("blocks") or []:
        s.put(s.cx + lx, B + dy, s.cz + lz, v)
    for lx, dy, lz, v in p.get("hung") or []:
        s.put(s.cx + lx, B + dy, s.cz + lz, v, hung=True)


def _segment_cols(a, b, half):
    (ax, az), (bx, bz) = a, b
    vx, vz = bx - ax, bz - az
    L2 = vx * vx + vz * vz
    r = half + 0.5
    out = []
    for dx in range(int(math.floor(min(ax, bx) - r)), int(math.ceil(max(ax, bx) + r)) + 1):
        for dz in range(int(math.floor(min(az, bz) - r)), int(math.ceil(max(az, bz) + r)) + 1):
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((dx - ax) * vx + (dz - az) * vz) / L2))
            if math.hypot(dx - (ax + t * vx), dz - (az + t * vz)) <= r:
                out.append((dx, dz))
    return out


def _h32(x, z, salt):
    return ((x * 73856093) ^ (z * 19349663) ^ (salt * 83492791)) & 0xFFFFFFFF


def _pick(palette, x, z, salt):
    total = sum(w for _b, w in palette)
    k = _h32(x, z, salt) % total
    for b, w in palette:
        if k < w:
            return b
        k -= w
    return palette[-1][0]


def piece_surface(s, p, salt):
    """The ground's TOP block replaced (the height never changes), plants cleared off it. Dry columns only."""
    cols = set()
    for seg in p.get("segments") or []:
        cols.update(_segment_cols(seg[0], seg[1], p.get("half_width", 0)))
    if p.get("ring"):
        r, w = p["ring"]
        for dx in range(-r - w - 1, r + w + 2):
            for dz in range(-r - w - 1, r + w + 2):
                if abs(math.hypot(dx, dz) - r) <= w + 0.5:
                    cols.add((dx, dz))
    skip = {tuple(c) for c in p.get("except") or []}
    ox, oz = p.get("at") or (0, 0)
    for dx, dz in sorted(cols):
        if (dx, dz) in skip:
            continue
        x, z = s.cx + ox + dx, s.cz + oz + dz
        if not s.dry(x, z):
            continue
        gy = s.g(x, z)
        s.put(x, gy, z, _pick(p["palette"], x, z, salt))
        s.clear_col(x, z, gy + 1, gy + 2)


def piece_ground_blocks(s, p, at=None):
    """Each block on its OWN column's ground + dy: an object seated on one level buries its uphill side."""
    ax, az = at or p["at"]
    for key in ("blocks", "hung"):
        for dx, dy, dz, v in p.get(key) or []:
            x, z = s.cx + ax + dx, s.cz + az + dz
            if not s.dry(x, z):
                raise SouthError("%s %s: (%d, %d) is wet" % (s.r["id"], p["name"], x, z))
            gy = s.g(x, z)
            s.put(x, gy + dy, z, v, hung=(key == "hung"))
            s.clear_col(x, z, gy + 1, gy + max(dy, 1) + 1)


def piece_ring(s, p):
    """`count` copies of one small object on a circle of radius r round the centre, each on its own ground."""
    n, r = int(p["count"]), float(p["r"])
    ox, oz = p.get("at") or (0, 0)
    for k in range(n):
        a = 2 * math.pi * (k + 0.5 * float(p.get("offset", 0))) / n
        ax, az = ox + int(round(r * math.sin(a))), oz + int(round(-r * math.cos(a)))
        obj = p["objects"][k % len(p["objects"])]
        piece_ground_blocks(s, {"name": p["name"], "blocks": obj}, at=(ax, az))


def piece_posts(s, p):
    """Posts every `spacing` blocks along a compass bearing (0 north, 90 east): on dry ground `dry` bottom up; in
    water a `wet_shaft` from the bed up to the surface, then `wet_top` above it."""
    b = math.radians(p["bearing"])
    ux, uz = math.sin(b), -math.cos(b)
    fx, fz = p["from"]
    out = []
    for k in range(int(p["count"])):
        d = p["spacing"] * (k + int(p.get("skip", 0)))
        x, z = s.cx + fx + int(round(ux * d)), s.cz + fz + int(round(uz * d))
        gy = s.g(x, z)
        lv = s.wet.level(x, z)
        if lv is None:
            for j, v in enumerate(p["dry"]):
                s.put(x, gy + 1 + j, z, v)
            s.clear_col(x, z, gy + 1, gy + len(p["dry"]))
            out.append((x, z, "dry"))
        else:
            lv = int(lv)
            if lv - gy > int(p.get("max_depth", 6)):
                break
            for y in range(gy + 1, lv + 1):
                s.put(x, y, z, p["wet_shaft"])
            for j, v in enumerate(p["wet_top"]):
                s.put(x, lv + 1 + j, z, v)
            out.append((x, z, "wet"))
    s.floors[p["name"]] = out


def plan(doc, r, g, wet):
    s = Site(doc, r, g, wet)
    for i, p in enumerate(r["pieces"]):
        k = p["kind"]
        if k == "structure":
            piece_structure(s, p)
        elif k == "surface":
            piece_surface(s, p, i + 1)
        elif k == "ground_blocks":
            piece_ground_blocks(s, p)
        elif k == "ring":
            piece_ring(s, p)
        elif k == "posts":
            piece_posts(s, p)
    return s


def spot(s, at):
    """[lx, lz, on] -> (x, y, z) feet: on a structure's floor (its name) or on the ground ("ground")."""
    lx, lz, on = at
    x, z = s.cx + lx, s.cz + lz
    y = (s.floors[on] + 1) if on != "ground" else s.g(x, z) + 1
    return x, y, z


def check_standing(s, xyz, who):
    blocks = dict(s.solid)
    blocks.update(s.hung)
    x, y, z = xyz
    feet = base(blocks.get((x, y, z), "minecraft:air"))
    head = base(blocks.get((x, y + 1, z), "minecraft:air"))
    if feet not in ("minecraft:air", "minecraft:brown_carpet", "minecraft:red_carpet") or head != "minecraft:air":
        raise SouthError("%s: %s's spot %s is not two blocks of standing room (%s, %s)" % (s.r["id"], who, xyz, feet, head))
    under = blocks.get((x, y - 1, z))
    if (under is None or base(under) == "minecraft:air") and s.g(x, z) != y - 1:
        raise SouthError("%s: %s's spot %s has nothing under it" % (s.r["id"], who, xyz))


def stand_clears(s, xyz):
    """The standing space: logs, leaves and plants off the spot's 3x3, from each column's own ground + 1 (never into
    the ground) up to the head (tools/resident_encounters.py stand_clears)."""
    x, y, z = xyz
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            s.clear_col(x + dx, z + dz, max(s.g(x + dx, z + dz) + 1, y), y + 1)


def box_of(s, extra=()):
    xs = [k[0] for k in list(s.solid) + list(s.hung)] + [c[0] for c in s.clears] + [c[3] for c in s.clears] + [e[0] for e in extra]
    zs = [k[2] for k in list(s.solid) + list(s.hung)] + [c[2] for c in s.clears] + [c[5] for c in s.clears] + [e[2] for e in extra]
    return [min(xs), min(zs), max(xs), max(zs)]


# ------------------------------------------------------------------ the siting rules (the builder's guards)


def owned_ids(doc):
    out = set()
    for r in doc["residents"]:
        for k in ("quest", "conversation", "reward"):
            if (r.get("records") or {}).get(k):
                out.add(r["records"][k])
    return out


def authored_points(doc, own_file=None):
    """Every x/z any other data/*.json authors: dicts with x and z; [x, z], [x, y, z] (read both ways, so a
    [x, z, y] polyline counts too) and [x0, z0, x1, z1] boxes (corners and centre). Our own records in the shared
    files are skipped by id, and this file is skipped whole. `own_file` names the residents file to skip when another
    tool calls this one (tools/northern_residents.py, whose sites are checked against THIS file as any other)."""
    own_path = Path(own_file) if own_file else DATA
    own = owned_ids(doc)
    pts = []

    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def walk(o, f):
        if isinstance(o, dict):
            if o.get("id") in own:
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
        if p.resolve() == own_path.resolve():
            continue
        walk(json.loads(p.read_text(encoding="utf-8")), p.name)
    return pts


def _sub_of(x, z):
    from subregion_boxes import point_in_polygon
    design = jload("encounter_design.json")
    subs = [s["id"] for s in jload("regions.json")["subregions"]
            if any(point_in_polygon(x, z, p) for p in s.get("polygons") or [])]
    subs = [s for s in subs if s in design["tables"]]
    if not subs:
        return None, None, None
    tier = design["tables"][subs[0]]["tier"]
    return subs[0], tier, design["rules"]["hearts"]["next_cap"][str(tier)]


def siting(doc, r, s, extra, pts=None):
    """Problems, as strings, for one planned site. `extra` are the NPC spots, anchors and cache boxes (x, y, z)."""
    import numpy as np
    rules = doc["rules"]
    probs = []
    pts = pts if pts is not None else authored_points(doc)
    P = np.array([(a, b) for a, b, _f in pts], float)
    F = [f for _a, _b, f in pts]
    cols = set(s.cols) | {(c[0], c[2]) for c in s.clears} | {(c[3], c[5]) for c in s.clears} | {(e[0], e[2]) for e in extra}
    C = np.array(sorted(cols), float)
    # nearest authored point to any written column
    best = (1e9, None, None)
    for i in range(0, len(C), 256):
        blk = C[i:i + 256]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] < best[0]:
            best = (float(d[j]), tuple(blk[j[0]]), F[j[1]])
    if best[0] < rules["authored_clearance"]:
        probs.append("%s: (%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                     % (r["id"], best[1][0], best[1][1], best[0], best[2], rules["authored_clearance"]))
    fx0, fz0, fx1, fz1 = rules["keep_out_box"]["box"]
    if any(fx0 <= x <= fx1 and fz0 <= z <= fz1 for x, z in cols):
        probs.append("%s: writes inside the keep-out box %s" % (r["id"], rules["keep_out_box"]["box"]))
    for ax, az in rules["away_from"]["points"]:
        d = min(math.hypot(x - ax, z - az) for x, z in cols)
        if d < rules["away_from"]["blocks"]:
            probs.append("%s: %.0f blocks from the new place at (%d, %d) (needs %d)" % (r["id"], d, ax, az, rules["away_from"]["blocks"]))
    # areas the point scan cannot see inside: a town's footprint and a Rift zone's boxes (dicts and boxes of min/max)
    for t in jload("towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        m = rules["authored_clearance"]
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            probs.append("%s: within %d of town %s's footprint" % (r["id"], m, t["id"]))
    for k, zone in jload("rift_zones.json")["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                probs.append("%s: inside Rift zone %s" % (r["id"], k))
                break
    if any(z < rules["south_of_z"] for _x, z in cols):
        probs.append("%s: writes north of z %d" % (r["id"], rules["south_of_z"]))
    paths = np.array([p for pl in jload("route_paths.json")["paths"].values() for p in pl], float)
    cx, cz = r["site"]["centre"]
    dp = float(np.min(np.hypot(paths[:, 0] - cx, paths[:, 1] - cz)))
    if dp < rules["path_clearance"]:
        probs.append("%s: %.0f blocks from a route path (needs %d)" % (r["id"], dp, rules["path_clearance"]))
    pk = r.get("pokemon")
    if pk:
        ax, az = s.cx + pk["at"][0], s.cz + pk["at"][1]
        act = [b for b in jload("habitat_blocks.json")["blocks"] if b.get("style") == "activated"]
        for b in act:
            d = math.hypot(b["position"]["x"] - ax, b["position"]["z"] - az)
            if d < b["activated"]["spawn_range"] + pk["leash"]:
                probs.append("%s: its leash overlaps Habitat Block %s (%.0f, needs %d)"
                             % (r["id"], b["id"], d, b["activated"]["spawn_range"] + pk["leash"]))
        sub, tier, ceiling = _sub_of(ax, az)
        if sub is None:
            probs.append("%s: the resident stands in no sub-region with a table" % r["id"])
        elif pk["level"] > ceiling:
            probs.append("%s: L%d over %s's tier-%s ceiling %d" % (r["id"], pk["level"], sub, tier, ceiling))
        dpa = float(np.min(np.hypot(paths[:, 0] - ax, paths[:, 1] - az)))
        if dpa < rules["path_clearance"]:
            probs.append("%s: the resident is %.0f from a route path" % (r["id"], dpa))
    return probs, {"nearest_authored": best, "path": dp}


# ------------------------------------------------------------------ the residents (tools/resident_encounters.py's keeper)


def shim(doc):
    """tools/resident_encounters.py's doc shape for our keeper: our build block, and the permanently uncatchable."""
    b = doc["build"]
    perm = [r["pokemon"]["id"] for r in doc["residents"] if r.get("pokemon") and r["pokemon"]["catch_rule"] == "permanently_uncatchable"]
    return {"build": {"namespace": b["namespace"], "folder": b["folder"], "tag": b["tag"], "dormant_tag": b["dormant_tag"],
                      "guardian_tag": b["guardian_tag"], "objective": b["objective"], "keeper": b["keeper"]},
            "rules": {"permanently_uncatchable": perm, "respawn_ticks_after_faint_death_or_catch": b["respawn_ticks"]}}


def resident_record(r):
    pk = r["pokemon"]
    return {"id": pk["id"], "name": pk["name"], "species": pk["species"], "level": pk["level"],
            "build": {"yaw": pk["yaw"], "trigger": pk["trigger"], "leash": pk["leash"],
                      "appears_after": pk.get("appears_after"), "message": pk["message"], "sound": pk["sound"],
                      "dormant_extra": pk.get("dormant_extra")}}


def anchor(s, r):
    pk = r["pokemon"]
    x, z = s.cx + pk["at"][0], s.cz + pk["at"][1]
    return x, s.g(x, z) + 1, z


# ------------------------------------------------------------------ the pack


def _runs(blocks, top_down=False):
    out = []
    keys = sorted(blocks, key=lambda k: (-k[1] if top_down else k[1], k[2], k[0]))
    i = 0
    while i < len(keys):
        x, y, z = keys[i]
        st = blocks[keys[i]]
        j = i
        while (j + 1 < len(keys) and keys[j + 1] == (keys[j][0] + 1, y, z) and blocks[keys[j + 1]] == st
               and "{" not in st):
            j += 1
        out.append("setblock %d %d %d %s" % (x, y, z, st) if j == i else
                   "fill %d %d %d %d %d %d %s" % (x, y, z, keys[j][0], y, z, st))
        i = j + 1
    return out


def merged_clears(clears):
    """The column clears deduplicated and joined into runs along x (same y range, same z); boxes pass unchanged."""
    cols = sorted({c for c in clears if c[0] == c[3] and c[2] == c[5]}, key=lambda c: (c[1], c[4], c[2], c[0]))
    out = [c for c in dict.fromkeys(clears) if not (c[0] == c[3] and c[2] == c[5])]
    i = 0
    while i < len(cols):
        x, y0, z, _x, y1, _z = cols[i]
        j = i
        while j + 1 < len(cols) and cols[j + 1][1:3] == (y0, z) and cols[j + 1][4] == y1 and cols[j + 1][0] == cols[j][0] + 1:
            j += 1
        out.append((x, y0, z, cols[j][0], y1, z))
        i = j + 1
    # then runs of identical x-spans along z (a line running north-south is one fill per y range)
    rows = sorted(out, key=lambda c: (c[0], c[3], c[1], c[4], c[2]))
    merged = []
    for c in rows:
        if merged:
            m = merged[-1]
            if (m[0], m[3], m[1], m[4]) == (c[0], c[3], c[1], c[4]) and c[2] == m[5] + 1:
                merged[-1] = (m[0], m[1], m[2], m[3], m[4], c[5])
                continue
        merged.append(c)
    return merged


def build_lines(doc, r, s, box):
    out = ["# Generated by tools/southern_residents.py from data/southern_residents.json: %s" % r["name"],
           "# chunks-loaded-by: the re-application R9SR (forceload add %d %d %d %d over RCON before this runs)" % tuple(box),
           "# 1. logs, leaves and plants off every piece (never a block of ground)"]
    for x0, y0, z0, x1, y1, z1 in merged_clears(s.clears):
        for tag in ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable"):
            out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out.append("# 2. the structure, bottom up")
    out += _runs({k: v for k, v in s.solid.items() if k not in s.hung})
    if s.hung:
        out.append("# 3. what hangs on it, from the top")
        out += _runs(s.hung, top_down=True)
    return out


def sites(doc, g, wet=None):
    import resident_encounters as RE
    wet = wet or RE.Wet(g, [tuple(r["site"]["centre"]) for r in doc["residents"]])
    out = []
    for r in doc["residents"]:
        s = plan(doc, r, g, wet)
        extra = []
        if r.get("npc"):
            xyz = spot(s, r["npc"]["at"])
            if r["npc"]["at"][2] == "ground":
                stand_clears(s, xyz)
            check_standing(s, xyz, r["npc"]["name"])
            extra.append(xyz)
        if r.get("pokemon"):
            a = anchor(s, r)
            stand_clears(s, a)
            check_standing(s, a, r["pokemon"]["name"])
            extra.append(a)
        for c in r.get("caches") or []:
            extra.append(spot(s, c["at"]))
        out.append((r, s, extra, box_of(s, extra)))
    return out


def check_records(doc, built):
    """The anchor, NPC spot and cache recorded in the data are the ones the heightmap gives: other builders check
    their collisions against the records, and data/rewards.json's npc_at is what R9F places."""
    probs = []
    rw = {x["id"]: x for x in jload("rewards.json")["rewards"]}
    qs = {q["id"]: q for q in jload("quests.json")["quests"]}
    for r, s, extra, box in built:
        rec = r.get("records") or {}
        if r.get("pokemon"):
            a = list(anchor(s, r))
            if a != r["pokemon"].get("anchor"):
                probs.append("%s: the heightmap puts the anchor at %s, the record says %s" % (r["id"], a, r["pokemon"].get("anchor")))
        if r.get("npc"):
            xyz = list(spot(s, r["npc"]["at"]))
            if xyz != r["npc"].get("feet"):
                probs.append("%s: the heightmap puts the NPC at %s, the record says %s" % (r["id"], xyz, r["npc"].get("feet")))
            q = qs.get(rec.get("quest"))
            if q is None:
                probs.append("%s: quest %s is not in data/quests.json" % (r["id"], rec.get("quest")))
            elif q.get("npc_at") != xyz:
                probs.append("%s: data/quests.json %s npc_at %s, the site gives %s" % (r["id"], q["id"], q.get("npc_at"), xyz))
            if r["npc"]["placed_by"] == "R9F":
                w = rw.get(rec.get("reward"))
                if not w or w.get("kind") != "npc_grant" or w.get("npc_at") != xyz:
                    probs.append("%s: data/rewards.json %s must be an npc_grant at %s" % (r["id"], rec.get("reward"), xyz))
        for c in r.get("caches") or []:
            xyz = list(spot(s, c["at"]))
            w = rw.get(c["reward"])
            if not w or w.get("kind") != "cache":
                probs.append("%s: data/rewards.json %s is not a cache" % (r["id"], c["reward"]))
                continue
            cont = [xyz[0], xyz[1] - 1, xyz[2]]
            if (w.get("container") or {}).get("at") != cont:
                probs.append("%s: %s container at %s, the site gives %s" % (r["id"], c["reward"], (w.get("container") or {}).get("at"), cont))
            if s.solid.get(tuple(cont)) is None or base(s.solid[tuple(cont)]) != w["container"]["block"]:
                probs.append("%s: no %s written at %s" % (r["id"], w["container"]["block"], cont))
            t = w.get("trigger") or {}
            if not (t.get("min", [0])[0] <= xyz[0] <= t.get("max", [0])[0] and t["min"][2] <= xyz[2] <= t["max"][2]
                    and t["min"][1] <= xyz[1] <= t["max"][1]):
                probs.append("%s: %s trigger %s does not hold the spot %s" % (r["id"], c["reward"], t, xyz))
        if list(box) != r.get("bbox"):
            probs.append("%s: the writes' box is %s, the record's bbox %s" % (r["id"], box, r.get("bbox")))
    return probs


def files(doc, g, wet=None, check=True):
    import resident_encounters as RE
    built = sites(doc, g, wet)
    if check:
        pts = authored_points(doc)
        probs = []
        for r, s, extra, box in built:
            probs += siting(doc, r, s, extra, pts)[0]
        probs += check_records(doc, built)
        spawn = set(jload("spawn_blocks.json")["blocks"])
        for r, s, extra, box in built:
            bad = sorted({base(v) for v in list(s.solid.values()) + list(s.hung.values())} & spawn)
            if bad:
                probs.append("%s: writes spawn-condition blocks %s (data/spawn_blocks.json)" % (r["id"], bad))
        if probs:
            raise SouthError("southern_residents: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = doc["build"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    fn = {}
    sh = shim(doc)
    load_ = ["# the southern residents' keeper state (tools/southern_residents.py, on tools/resident_encounters.py's keeper).",
             "# A clock that has never been set starts READY (respawn ticks already elapsed), so a fresh world fills at once",
             "scoreboard objectives add %s dummy" % obj,
             "scoreboard players set #resp %s %d" % (obj, int(b["respawn_ticks"])),
             "execute store result score #ready %s run time query gametime" % obj,
             "scoreboard players operation #ready %s -= #resp %s" % (obj, obj)]
    keeper = ["execute store result score #now %s run time query gametime" % obj]
    for r, s, extra, box in built:
        lines = build_lines(doc, r, s, box)
        bad = function_limits.check_lines(lines, "%s/build" % r["id"])
        if bad:
            raise SouthError("%s/build: %d command(s) the server would refuse: %s" % (r["id"], len(bad), bad[:3]))
        fn["%s/build" % r["id"]] = lines
        if r.get("pokemon"):
            e = resident_record(r)
            a = anchor(s, r)
            i = e["id"]
            rf = RE.resident_files(sh, e, a, [], [], box)
            rf.pop("%s/dress" % i, None)
            fn.update(rf)
            load_ += ["execute unless score #%s.gone %s matches -2147483648.. run scoreboard players operation #%s.gone %s = #ready %s"
                      % (i, obj, i, obj, obj),
                      "execute unless score #%s.abs %s matches -2147483648.. run scoreboard players set #%s.abs %s 0" % (i, obj, i, obj)]
            keeper.append("execute if loaded %d %d %d run function %s:%s/%s/keep" % (a[0], a[1], a[2], ns, F, i))
    if any(r.get("pokemon") for r, _s, _e, _b in built):
        fn["spawn_at"] = ["# a macro, so the mod's command is parsed when it runs (EXP-046, .claude/rules/datapacks.md)",
                          "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]
        load_.append("schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"]))
        keeper.append("schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"]))
        fn["load"] = load_
        fn["keeper"] = keeper
    out = {"data/%s/function/%s/%s.mcfunction" % (ns, F, n): "\n".join(v) + "\n" for n, v in fn.items()}
    if "load" in fn:
        out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/load" % (ns, F)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: the southern residents (tools/southern_residents.py)"}}, indent=2) + "\n"
    return out, built


# ------------------------------------------------------------------ the re-application


def _built(doc=None, g=None):
    import ground as G
    doc = doc or load()
    g = g or G.load()
    return doc, g, sites(doc, g)


def placement_steps(doc=None, g=None):
    """R9SR, BEFORE R9E: per site, hold its box, build, release (R9LH's shape)."""
    doc, g, built = _built(doc, g)
    b = doc["build"]
    steps = []
    for r, s, extra, box in built:
        hold = "%d %d %d %d" % tuple(box)
        steps += [("cmd", "forceload add " + hold), ("wait", 3),
                  ("fn", "%s:%s/%s/build" % (b["namespace"], b["folder"], r["id"])), ("cmd", "forceload remove " + hold)]
    return steps


def npc_placements(doc=None, g=None, built=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for the NPCs R9F does NOT place (no npc_grant record)."""
    if built is None:
        doc, g, built = _built(doc, g)
    dl = {c["id"]: c for c in jload("dialogue.json")["conversations"]}
    out = []
    for r, s, extra, box in built:
        n = r.get("npc")
        if not n or n["placed_by"] != "R18SR":
            continue
        conv = dl.get(r["records"]["conversation"])
        if conv is None or not conv.get("npc_id"):
            raise SouthError("%s: %s is not a conversation with an NPC in data/dialogue.json" % (r["id"], r["records"]["conversation"]))
        out.append((conv["id"], spot(s, n["at"]), "cobblers:%s" % conv["npc_id"], n["yaw"]))
    return out


def entity_steps(doc=None, g=None):
    """R18SR, after R18R: each ungated resident summoned over RCON (guarded on tag AND species, never a bare
    distance: THE SUMMON GUARD) and bound, inside a forceload of its site's box; then the NPCs R9F does not place."""
    import resident_encounters as RE
    doc, g, built = _built(doc, g)
    b = doc["build"]
    sh = shim(doc)
    steps = []
    for r, s, extra, box in built:
        if not r.get("pokemon") or r["pokemon"].get("appears_after"):
            continue
        e = resident_record(r)
        a = anchor(s, r)
        hold = "%d %d %d %d" % tuple(box)
        steps += [("cmd", "forceload add " + hold), ("wait", 3), ("cmd", RE.summon_command(sh, e, a)), ("wait", 1),
                  ("fn", "%s:%s/%s/bind_new" % (b["namespace"], b["folder"], e["id"])), ("cmd", "forceload remove " + hold)]
    steps += [("npc", n) for n in npc_placements(doc, g, built)]
    return steps


# ------------------------------------------------------------------ CLI


def report(doc, g):
    built = sites(doc, g)
    pts = authored_points(doc)
    lines = []
    for r, s, extra, box in built:
        probs, m = siting(doc, r, s, extra, pts)
        na = m["nearest_authored"]
        sub = _sub_of(*r["site"]["centre"])
        lines.append("%-14s %-34s centre %s ground y%d sub %s tier %s; %d blocks, bbox %s; nearest authored %.0f "
                     "(our column %s to data/%s); path %.0f"
                     % (r["id"], r["name"], r["site"]["centre"], g(*r["site"]["centre"]), sub[0], sub[1],
                        len(s.solid) + len(s.hung), box, na[0], tuple(int(v) for v in na[1]), na[2], m["path"]))
        for k, v in s.floors.items():
            lines.append("    floor %s: %s" % (k, v if not isinstance(v, list) else "%d posts (%d wet)" % (len(v), sum(1 for p in v if p[2] == "wet"))))
        if r.get("npc"):
            lines.append("    NPC %s feet %s" % (r["npc"]["name"], list(spot(s, r["npc"]["at"]))))
        if r.get("pokemon"):
            lines.append("    resident %s L%d anchor %s" % (r["pokemon"]["name"], r["pokemon"]["level"], list(anchor(s, r))))
        for c in r.get("caches") or []:
            lines.append("    cache %s spot %s" % (c["reward"], list(spot(s, c["at"]))))
        for p in probs:
            lines.append("    PROBLEM %s" % p)
    for p in check_records(doc, built):
        lines.append("PROBLEM %s" % p)
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print the sites, the checks and the steps; write nothing")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.report:
        print("\n".join(report(doc, g)))
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
    print("southern_residents: %d files -> %s (%d sites, build: %d commands)" % (len(written), out, len(built), n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
