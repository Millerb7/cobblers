#!/usr/bin/env python
"""Independent offline audit of the written Frostpeak summit pack (build/datapacks/cobblers_frostpeak_summit).

It reads the pack's function text back into blocks and checks them against sources the generator does not use to
decide them. Nothing is imported from tools/frostpeak_summit.py.

  the tower box     data/adopted_legendary_sites.json placement corner and seat, with the size parsed from
                    data/structures.json's footprint string (the generator reads the site record's own `size`)
  the door lane     data/frostpeak_summit.json tower.door (read from the template; the record, not a derivation)
  the camp's view   data/frostpeak_camp.json: the telescope's column and its deck's floor by the seat convention
                    (max ground under the deck + 1), viewed from four heights over the floor (1.0, a player's eye
                    1.62, the pivot 2.2, and 2.5). The target is the tower's whole box from y370 to its top layer,
                    sampled every half block over its surface: stricter than the crown the camp actually sees.
  the ground        tools/ground.py, per column
  spawn conditions  data/spawn_blocks.json

Checks (each must hold):

  S1 footprint     no write in any column of the tower's box
  S2 door lane     in the lane straight out of the door (door width + half_width_beyond_door each side, from
                   approach.from_z to the box's north edge) nothing stands above the ground, and what lies at the
                   ground is a full block
  S3 sight line    no written non-air block meets any segment from the camp's viewpoints to the tower above y370
  S4 spawn         no written block is a spawn condition, and every written block is in the data file's palette
  S5 light         nothing written emits light, and nothing is a bed, chest, sign, barrel or other block entity
  S6 support       every block above the ground stands on something; a plant on soil the pack itself wrote; rime
                   only against a rock's west face; rock may overhang, but the rock it is joined to reaches the ground
  S7 bounds        every write within path_radius + 3 of the centre and within [ground - 1, ground + 6]
  S8 the table     no plant, rime, snow layer or tor rock (stone, tuff) above the ground inside keep_bare_radius
  S9 the wind      every plant has rock within 7 blocks to its west in its own row (it is in a lee), and every
                   rime block has rock immediately east of it
  S10 limits       tools/function_limits.py finds nothing the server would refuse
  S11 non-empty    at least 200 rock blocks, 30 plants, 20 rime, 80 gravel or flagstone way cells and 5 cairn caps

  python tools/frostpeak_summit_audit.py [--pack DIR] [--source-root R]   exit 1 on any problem
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_frostpeak_summit"
OUT = ROOT / "derived" / "frostpeak_summit" / "audit.json"
CROWN_FROM_Y = 370
EYES = (1.0, 1.62, 2.2, 2.5)
PLANTS = {"minecraft:fern", "minecraft:large_fern", "minecraft:short_grass", "minecraft:dead_bush"}
SOILS = {"minecraft:coarse_dirt", "minecraft:dirt", "minecraft:grass_block", "minecraft:podzol",
         "minecraft:moss_block", "minecraft:rooted_dirt"}
COVER = {"minecraft:moss_carpet", "minecraft:snow"}
ROCK = {"minecraft:stone", "minecraft:andesite", "minecraft:cobblestone", "minecraft:tuff"}
TOR_ONLY = {"minecraft:stone", "minecraft:tuff"}
NOT_FULL = PLANTS | COVER | {"minecraft:cobblestone_wall"}
EMITS = re.compile(r"(lantern|torch|glowstone|shroomlight|froglight|campfire|candle|beacon|magma|end_rod|redstone_lamp|"
                   r"glow_lichen|jack_o_lantern|lava|fire)$|^minecraft:light$")
ENTITY = re.compile(r"(chest|_bed$|sign|barrel|banner|spawner|shulker|hopper|furnace|smoker|lectern|respawn_anchor)")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)$")
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)$")
# The ground rule (tools/ground_rule.py): nothing here reads a world; ground comes from tools/ground.py.
WORLD_READS: set = set()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def name_of(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def replay(lines):
    """{(x, y, z): state} after every setblock and fill, in order; and the lines nothing parsed."""
    blocks, other = {}, []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("forceload "):
            continue
        m = SETBLOCK.match(line)
        if m:
            x, y, z, s = m.groups()
            blocks[(int(x), int(y), int(z))] = s
            continue
        m = FILL.match(line)
        if m:
            x0, y0, z0, x1, y1, z1, s = m.groups()
            for x in range(min(int(x0), int(x1)), max(int(x0), int(x1)) + 1):
                for y in range(min(int(y0), int(y1)), max(int(y0), int(y1)) + 1):
                    for z in range(min(int(z0), int(z1)), max(int(z0), int(z1)) + 1):
                        blocks[(x, y, z)] = s
            continue
        other.append(line)
    return blocks, other


def pack_lines(pack):
    fns = sorted(Path(pack).glob("data/*/function/**/*.mcfunction"))
    out = {}
    for f in fns:
        out[str(f.relative_to(pack))] = f.read_text(encoding="utf-8").splitlines()
    return out


def tower_box():
    """(x0, y0, z0, x1, y1, z1) inclusive, from the site's corner and seat and the structure catalogue's footprint."""
    site = next(s for s in load_json(ROOT / "data" / "adopted_legendary_sites.json")["sites"]
                if s["id"] == "adopted_articuno_shrine")
    foot = next(s for s in load_json(ROOT / "data" / "structures.json")["structures"]
                if s["id"] == site["template"])["footprint"]
    sx, sy, sz = (int(v) for v in re.match(r"^(\d+)x(\d+)x(\d+)", foot).groups())
    (x0, z0), y0 = site["placement"]["corner"], site["placement"]["y"]
    return x0, y0, z0, x0 + sx - 1, y0 + sy - 1, z0 + sz - 1


def viewpoints(g):
    camp = load_json(ROOT / "data" / "frostpeak_camp.json")
    scope = next(p for p in camp["pieces"] if p["id"] == "frostpeak_camp_telescope")
    deck = next(p for p in camp["pieces"] if p["id"] == scope["on"])
    (dx, dz), (hx, hz) = deck["at"], deck["half"]
    floor = max(g(x, z) for x in range(dx - hx, dx + hx + 1) for z in range(dz - hz, dz + hz + 1)) + 1
    tx, tz = scope["at"]
    return [(tx + 0.5, floor + e, tz + 0.5) for e in EYES]


def targets(box):
    x0, _y0, z0, x1, y1, z1 = box
    xs = np.arange(x0, x1 + 1.001, 0.5)
    zs = np.arange(z0, z1 + 1.001, 0.5)
    ys = np.arange(CROWN_FROM_Y, y1 + 1.001, 0.5)
    pts = []
    for y in ys:
        for x in xs:
            pts += [(x, y, z0), (x, y, z1 + 1)]
        for z in zs:
            pts += [(x0, y, z), (x1 + 1, y, z)]
    for x in xs:
        for z in zs:
            pts.append((x, y1 + 1, z))
    return np.array(pts, dtype=float)


def blocks_on_sight(blocks, eyes, tgt):
    """[(x, y, z)] of non-air blocks that meet a segment from an eye to a target point (exact slab test)."""
    hits = []
    for eye in eyes:
        e = np.array(eye)
        d = tgt - e
        # the horizontal wedge the segments sweep: a quick reject before the slab test
        ang = np.arctan2(d[:, 0], -d[:, 2])          # 0 = north: the tower is north of the camp
        lo, hi = ang.min() - 0.05, ang.max() + 0.05
        for (x, y, z), s in blocks.items():
            if name_of(s) == "minecraft:air" or (x, y, z) in hits:
                continue
            a = math.atan2(x + 0.5 - e[0], -(z + 0.5 - e[2]))
            if not (lo <= a <= hi):
                continue
            lo_c, hi_c = np.array([x, y, z], float), np.array([x + 1, y + 1, z + 1], float)
            with np.errstate(divide="ignore", invalid="ignore"):
                t1 = (lo_c - e) / d
                t2 = (hi_c - e) / d
            tmin = np.where(d == 0, np.where((e >= lo_c) & (e <= hi_c), -np.inf, np.inf), np.minimum(t1, t2))
            tmax = np.where(d == 0, np.where((e >= lo_c) & (e <= hi_c), np.inf, -np.inf), np.maximum(t1, t2))
            enter = np.maximum(tmin.max(axis=1), 0.0)
            leave = np.minimum(tmax.min(axis=1), 1.0)
            if np.any(enter <= leave):
                hits.append((x, y, z))
    return hits


class Report:
    def __init__(self):
        self.rows = []

    def check(self, ok, name, detail=""):
        self.rows.append({"check": name, "ok": bool(ok), "detail": "" if ok else detail})

    @property
    def problems(self):
        return [r for r in self.rows if not r["ok"]]


def audit(pack, g):
    doc = load_json(ROOT / "data" / "frostpeak_summit.json")
    rep = Report()
    files = pack_lines(pack)
    rep.check(bool(files), "S0 pack", "no function in %s" % pack)
    if not files:
        return rep
    blocks = {}
    for rel, lines in files.items():
        b, other = replay(lines)
        blocks.update(b)
        rep.check(not other, "S0 parse %s" % rel, "commands the audit cannot read: %s" % other[:3])
    solid = {k: v for k, v in blocks.items() if name_of(v) != "minecraft:air"}
    names = {k: name_of(v) for k, v in blocks.items()}
    ground = {}

    def gr(x, z):
        if (x, z) not in ground:
            ground[(x, z)] = g(x, z)
        return ground[(x, z)]

    # S1
    bx0, _by0, bz0, bx1, by1, bz1 = box = tower_box()
    inside = sorted(k for k in blocks if bx0 <= k[0] <= bx1 and bz0 <= k[2] <= bz1)
    rep.check(not inside, "S1 footprint", "%d writes in the tower's box x%d..%d z%d..%d, first %s"
              % (len(inside), bx0, bx1, bz0, bz1, inside[:3]))

    # S2
    door = doc["tower"]["door"]
    hw = door["approach"]["half_width_beyond_door"]
    lx0, lx1 = door["x"][0] - hw, door["x"][1] + hw
    lz0, lz1 = door["approach"]["from_z"], bz0 - 1
    bad = []
    for (x, y, z), nm in names.items():
        if not (lx0 <= x <= lx1 and lz0 <= z <= lz1):
            continue
        gy = gr(x, z)
        if (y > gy and nm != "minecraft:air") or (y == gy and nm in NOT_FULL):
            bad.append((x, y, z, nm))
    rep.check(not bad, "S2 door lane", "%d blocks stand in the lane x%d..%d z%d..%d, first %s"
              % (len(bad), lx0, lx1, lz0, lz1, sorted(bad)[:3]))
    rep.check(lz0 < lz1 and door["x"][0] >= bx0 and door["x"][1] <= bx1, "S2 lane geometry",
              "the door record does not sit on the tower box's north face")

    # S3
    eyes = viewpoints(g)
    hits = blocks_on_sight(solid, eyes, targets(box))
    rep.check(not hits, "S3 sight line", "%d blocks on the camp's line to the tower above y%d, first %s"
              % (len(hits), CROWN_FROM_Y, sorted(hits)[:3]))

    # S4
    spawn = set(load_json(ROOT / "data" / "spawn_blocks.json")["blocks"])
    used = set(names.values())
    palette = set(doc["blocks"]["ids"]) | {"minecraft:air"}
    rep.check(not (used & spawn), "S4 spawn conditions", "spawn-condition blocks written: %s" % sorted(used & spawn))
    rep.check(used <= palette, "S4 palette", "blocks outside data/frostpeak_summit.json blocks.ids: %s"
              % sorted(used - palette))

    # S5
    light = sorted(n for n in used if EMITS.search(n))
    ent = sorted(n for n in used if ENTITY.search(n)) + sorted({s for s in blocks.values() if "{" in s})
    rep.check(not light, "S5 light", "light-emitting blocks written (the summit is dark by design): %s" % light)
    rep.check(not ent, "S5 block entities", "beds, chests, signs or block data written: %s" % ent[:5])

    # S6
    comp = {}

    def grounded(x, y, z):
        if (x, y, z) not in comp:
            seen, todo, low = {(x, y, z)}, [(x, y, z)], False
            while todo:
                p = todo.pop()
                low = low or p[1] - 1 <= gr(p[0], p[2])
                for a, b, c in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                    q = (p[0] + a, p[1] + b, p[2] + c)
                    if q not in seen and names.get(q) in ROCK:
                        seen.add(q)
                        todo.append(q)
            for p in seen:
                comp[p] = low
        return comp[(x, y, z)]

    bad = []
    for (x, y, z), nm in names.items():
        if nm == "minecraft:air":
            continue
        gy = gr(x, z)
        if y <= gy:
            continue
        below = names.get((x, y - 1, z))
        below_solid = (below is not None and below != "minecraft:air") or (below is None and y - 1 <= gy)
        s = blocks[(x, y, z)]
        if nm == "minecraft:large_fern" and "half=upper" in s:
            ok = below == "minecraft:large_fern" and "half=lower" in blocks.get((x, y - 1, z), "")
        elif nm in PLANTS:
            ok = below in SOILS
        elif nm == "minecraft:packed_ice":
            ok = names.get((x + 1, y, z)) in ROCK
        elif nm in ROCK:
            # rock is rigid: an overhang is a tor's shape, so a rock block passes when the rock it is joined to
            # (face-connected) reaches down to the ground; a tor lifted off the ground as a whole does not
            ok = grounded(x, y, z)
        else:
            ok = below_solid
        if not ok:
            bad.append((x, y, z, nm))
    rep.check(not bad, "S6 support", "%d blocks with nothing proper under them, first %s" % (len(bad), sorted(bad)[:3]))

    # S7
    (cx, cz), rmax = doc["site"]["centre"], doc["site"]["path_radius"] + 3
    far = sorted(k for k in blocks if math.hypot(k[0] - cx, k[2] - cz) > rmax)
    rep.check(not far, "S7 radius", "%d writes beyond radius %d, first %s" % (len(far), rmax, far[:3]))
    off = sorted(k for k in blocks if not (gr(k[0], k[2]) - 1 <= k[1] <= gr(k[0], k[2]) + 6))
    rep.check(not off, "S7 height", "%d writes more than 1 below or 6 above the ground, first %s" % (len(off), off[:3]))

    # S8
    rb = doc["table"]["keep_bare_radius"]
    bare = sorted((k, nm) for k, nm in names.items() if math.hypot(k[0] - cx, k[2] - cz) < rb
                  and k[1] > gr(k[0], k[2]) and (nm in PLANTS | COVER | TOR_ONLY or nm == "minecraft:packed_ice"))
    rep.check(not bare, "S8 bare table", "%d plants, rime, drift or tor rock inside radius %d, first %s"
              % (len(bare), rb, bare[:3]))

    # S9
    bad = []
    for (x, y, z), nm in names.items():
        if nm in PLANTS and "half=upper" not in blocks[(x, y, z)]:
            if not any(names.get((x - d, yy, z)) in ROCK for d in range(1, 8) for yy in range(y - 1, y + 4)):
                bad.append((x, y, z, nm))
    rep.check(not bad, "S9 lee", "%d plants with no rock to their west in their row, first %s" % (len(bad), sorted(bad)[:3]))

    # S10
    for rel, lines in files.items():
        lim = function_limits.check_lines(lines, rel)
        rep.check(not lim, "S10 limits %s" % rel, "%s" % lim[:2])

    # S11
    count = {}
    for (x, y, z), nm in names.items():
        gy = gr(x, z)
        if nm in ROCK and y >= gy:
            count["rock"] = count.get("rock", 0) + 1
        if nm in PLANTS | {"minecraft:moss_carpet"} and "half=upper" not in blocks[(x, y, z)]:
            count["plants"] = count.get("plants", 0) + 1
        if nm == "minecraft:packed_ice":
            count["rime"] = count.get("rime", 0) + 1
        if y == gy and nm in {"minecraft:gravel", "minecraft:stone_bricks", "minecraft:cracked_stone_bricks"}:
            count["way"] = count.get("way", 0) + 1
        if nm == "minecraft:cobblestone_wall":
            count["cairns"] = count.get("cairns", 0) + 1
    need = {"rock": 200, "plants": 30, "rime": 20, "way": 80, "cairns": 5}
    short = {k: (count.get(k, 0), v) for k, v in need.items() if count.get(k, 0) < v}
    rep.check(not short, "S11 non-empty", "too little written (have, need): %s" % short)
    rep.counts = count
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    g = G.Ground(a.source_root)
    rep = audit(a.pack, g)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": rep.rows, "counts": getattr(rep, "counts", {})}, indent=1) + "\n",
                   encoding="utf-8")
    if rep.problems:
        for p in rep.problems:
            print("PROBLEM %s: %s" % (p["check"], p["detail"]))
        return 1
    print("CLEAN: %d checks over %s; counts %s" % (len(rep.rows), a.pack, getattr(rep, "counts", {})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
