#!/usr/bin/env python
"""Independent audit of Hummock Mere (data/hummock_mere.json, tools/hummock_mere.py): the built pack replayed.

It does NOT import the builder to derive an expectation. What it reads: the pack's own .mcfunction text, the authored
record's NUMBERS (radius, profile, bearings, level, trigger) and rules, the canonical heightmap (tools/ground.py), the
lake level (tools/water_mask.py directly), data/route_paths.json, towns.json, habitat_blocks.json, regions.json,
encounter_design.json, trainers.json and spawn_blocks.json. Every expectation is computed here from those, with its own
loops (the island's column heights, the trunks' connectivity by flood fill, the way-in's depths, the sign's side from a
cross product). The builder's functions are never called, except that the re-application steps it emits are READ as the
artifact under test (and checked against what the replay says is written).

  python tools/hummock_mere_audit.py [--pack DIR] [--source-root R]     exit 1 on any problem

What it cannot check: whether the world matches (tools/presence_audit.py, the probes in data/world_probes.json), whether
the creature looks right at scale_modifier 2.2 on its island, and tools/signposts.py's own post positions (its plan needs
build/paint).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data" / "hummock_mere.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_hummock_mere"


def jload(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def bid(state):
    return state.split("[")[0].split("{")[0]


# ------------------------------------------------------------------ the replay


def replay(text_lines):
    """({(x, y, z): state}, [clear boxes (x0, y0, z0, x1, y1, z1, tag)], [unparsed command]) from a function's lines."""
    blocks, clears, odd = {}, [], []
    for ln in text_lines:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        t = ln.split(" ", 4)
        if t[0] == "setblock":
            m = re.match(r"setblock (-?\d+) (-?\d+) (-?\d+) (.+)$", ln)
            if not m:
                odd.append(ln)
                continue
            blocks[(int(m[1]), int(m[2]), int(m[3]))] = m[4]
        elif t[0] == "fill":
            m = re.match(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$", ln)
            if not m:
                odd.append(ln)
                continue
            x0, y0, z0, x1, y1, z1 = (int(m[i]) for i in range(1, 7))
            if m[8]:
                clears.append((min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1), m[7] + " replace " + m[8]))
            else:
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    for y in range(min(y0, y1), max(y0, y1) + 1):
                        for z in range(min(z0, z1), max(z0, z1) + 1):
                            blocks[(x, y, z)] = m[7]
        else:
            odd.append(ln)
    return blocks, clears, odd


def read_pack(pack):
    pack = Path(pack)
    fdir = pack / "data" / "cobblers" / "function" / "hummock_mere"
    out = {}
    for f in fdir.rglob("*.mcfunction"):
        out[f.relative_to(fdir).as_posix()[:-len(".mcfunction")]] = f.read_text(encoding="utf-8").splitlines()
    return out


# ------------------------------------------------------------------ independent ground and water


class World:
    def __init__(self, source_root=None):
        import ground as G
        import water_mask as WM
        self.g = G.load(source_root)
        self.WM = WM
        self.bodies = WM.bodies()

    def level(self, x, z):
        return self.WM.level_at(x, z, self.g, self.bodies)[1]


def _path_dist(x, z, paths):
    return min(math.hypot(px - x, pz - z) for pl in paths.values() for px, pz in pl[::3])


# ------------------------------------------------------------------ the checks


def audit(pack=PACK, data=DATA, source_root=None):
    probs, notes = [], []
    doc = json.loads(Path(data).read_text(encoding="utf-8"))
    W = World(source_root)
    g = W.g
    fns = read_pack(pack)
    r = doc["residents"][0]
    cx, cz = r["site"]["centre"]
    pk = r["pokemon"]
    L = W.level(cx, cz)
    if L is None or int(L) != r["site"]["water_level"]:
        probs.append("the lake level at the centre is %s, the record says %s" % (L, r["site"]["water_level"]))
        return probs, notes
    L = int(L)

    build = fns.get("hummock_mere/build") or []
    blocks, clears, odd = replay(build)
    if odd:
        probs.append("the build holds %d command(s) the replay cannot read, e.g. %s" % (len(odd), odd[:2]))
    if not blocks:
        probs.append("the build writes no block")
        return probs, notes
    notes.append("build: %d blocks written, %d clear commands" % (len(blocks), len(clears)))

    # A. the palette
    spawn = set(jload("spawn_blocks.json")["blocks"])
    allowed = set(doc["blocks"]["ids"])
    used = {bid(v) for v in blocks.values()}
    for b in sorted(used):
        if b not in allowed:
            probs.append("palette: %s is written but not in blocks.ids" % b)
        if b in spawn:
            probs.append("palette: %s is a spawn condition (data/spawn_blocks.json)" % b)
        if "concrete" in b or "water" in b or "lava" in b or "chest" in b or "bed" in b.split(":")[1].split("_"):
            probs.append("palette: %s is never allowed here" % b)
    for (x, y, z), st in sorted(blocks.items()):
        if "waterlogged=true" in st:
            lv = W.level(x, z)
            if lv is None or not (g(x, z) < y <= int(lv)):
                probs.append("waterlogged block at %s is not under water (a source on dry land leaks)" % ((x, y, z),))

    # B. the flood rule: no clear reaches the water
    for c in clears:
        if c[1] <= L:
            probs.append("flood: a clear starts at y%d, at or under the lake (y%d): %s" % (c[1], L, c))
        if "replaceable" in c[6] and c[1] <= L:
            probs.append("flood: #replaceable holds water, and %s starts under the surface" % (c,))

    # C. the island, column by column, from the profile and the heightmap
    R = float(next(p for p in r["pieces"] if p["kind"] == "mound")["radius"])
    mound = next(p for p in r["pieces"] if p["kind"] == "mound")
    prof = sorted((float(a), int(b)) for a, b in mound["profile"])
    crest = L + max(b for _a, b in prof)
    n_cols = 0
    for dx in range(-8, 9):
        for dz in range(-8, 9):
            d = math.hypot(dx, dz)
            dy = next((b for a, b in prof if d <= a), None)
            x, z = cx + dx, cz + dz
            if dy is None:
                continue
            top, gy = L + dy, g(x, z)
            n_cols += 1
            for y in range(gy + 1, top + 1):
                st = blocks.get((x, y, z))
                if st is None or bid(st) not in ("minecraft:mud", "minecraft:moss_block"):
                    probs.append("island: column (%d, %d) is %s at y%d, expected mud up to y%d" % (x, z, st, y, top))
                    break
    notes.append("island: %d columns checked, crest y%d" % (n_cols, crest))

    # D/E. the creature's spot and its headroom
    ax, az = cx + pk["at"][0], cz + pk["at"][1]
    ay = crest + 1
    if list(pk["anchor"]) != [ax, ay, az]:
        probs.append("anchor: the record says %s, the island's crest gives %s" % (pk["anchor"], [ax, ay, az]))
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            # the crest's own radius holds the crest height; the shoulder (the next ring out) one lower
            yy = next(L + b for a, b in prof if math.hypot(dx, dz) <= a) if math.hypot(dx, dz) <= prof[-1][0] else None
            st = blocks.get((ax + dx, yy, az + dz)) if yy is not None else None
            if st is None or bid(st) not in ("minecraft:mud", "minecraft:moss_block"):
                probs.append("anchor: no solid under (%d, %s, %d)" % (ax + dx, yy, az + dz))
    hr = doc["rules"]["headroom_blocks"]
    for (x, y, z), st in blocks.items():
        if abs(x - ax) <= 4 and abs(z - az) <= 4 and ay <= y < ay + hr:
            probs.append("headroom: %s written at %s inside the creature's %d blocks" % (st, (x, y, z), hr))
    low = min((y for (x, y, z), st in blocks.items()
               if bid(st) == "minecraft:mangrove_leaves" and math.hypot(x - ax, z - az) <= 8), default=None)
    if low is not None and low < ay + hr:
        probs.append("headroom: a leaf at y%d is within 8 of the creature and under y%d" % (low, ay + hr))
    if bid(blocks.get((ax, ay, az), "minecraft:air")) != "minecraft:air":
        probs.append("anchor: the spot itself is written")

    # F. the grove: each trunk unbroken from the bed to lake + height, by flood fill over the written logs
    gp = next(p for p in r["pieces"] if p["kind"] == "mangrove")
    logs = {k for k, v in blocks.items() if bid(v) == "minecraft:mangrove_log"}
    lights = {k for k, v in blocks.items() if bid(v) == gp["light"]}
    for k, t in enumerate(gp["trees"]):
        b = math.radians(t["bearing"])
        bx, bz = cx + int(round(t["r"] * math.sin(b))), cz + int(round(-t["r"] * math.cos(b)))
        start = (bx, g(bx, bz) + 1, bz)
        if start not in logs:
            probs.append("tree %d: no log at its foot %s" % (k, start))
            continue
        seen, todo = {start}, [start]
        while todo:
            x, y, z = todo.pop()
            for n in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)):
                if n in logs and n not in seen:
                    seen.add(n)
                    todo.append(n)
        topy = max(y for _x, y, _z in seen)
        if topy != L + gp["height"]:
            probs.append("tree %d: the trunk reaches y%d, expected y%d" % (k, topy, L + gp["height"]))
        tx, ty, tz = max(seen, key=lambda q: q[1])
        if not any(math.hypot(lx - tx, lz - tz) <= gp["crown"]["in"] + 1.5 and 0 <= ly - ty <= gp["crown"]["up"] + 1 for lx, ly, lz in lights):
            probs.append("tree %d: no froglight under a crown over its top %s" % (k, (tx, ty, tz)))
    if len(lights) != len(gp["trees"]):
        probs.append("grove: %d froglights for %d trees" % (len(lights), len(gp["trees"])))

    # F2. the way in stays open at wading height: nothing solid in the 80-100 degree sector, 6-16 out, lake+1 .. lake+7
    for (x, y, z), st in blocks.items():
        if not (L + 1 <= y <= L + 7) or bid(st) in ("minecraft:mud", "minecraft:moss_block", "minecraft:mangrove_sign"):
            continue
        d = math.hypot(x - cx, z - cz)
        if 6 <= d <= 16:
            bearing = math.degrees(math.atan2(x - cx, -(z - cz))) % 360
            if 80 <= bearing <= 100:
                probs.append("way in: %s at %s blocks the 80-100 degree gap" % (st, (x, y, z)))

    # G. the furrow: contiguous mud from the spit to the island, wading depth at most 1
    seg = next(p for p in r["pieces"] if p["kind"] == "bed_strip")["segments"][0]
    (sx0, sz0), (sx1, sz1) = seg
    if sz0 != sz1:
        probs.append("furrow: the audit reads an east-west furrow; the record's is not")
    else:
        for dx in range(min(sx0, sx1), max(sx0, sx1) + 1):
            x, z = cx + dx, cz + sz0
            gy = g(x, z)
            if bid(blocks.get((x, gy, z), "")) != "minecraft:mud":
                probs.append("furrow: no mud at the bed (%d, %d, %d)" % (x, gy, z))
            lv = W.level(x, z)
            if lv is not None and int(lv) - gy > 1:
                probs.append("furrow: %d deep at (%d, %d): wading is 1" % (int(lv) - gy, x, z))
    # the same depth rule for the whole approach corridor, +-2 wide, to the island's rim
    deepest = 0
    for dx in range(int(R) + 1, 30):
        for dz in range(-2, 3):
            lv = W.level(cx + dx, cz + dz)
            if lv is not None:
                deepest = max(deepest, int(lv) - g(cx + dx, cz + dz))
    if deepest > 1:
        probs.append("way in: the corridor east of the island is %d deep at its deepest" % deepest)
    notes.append("way in: deepest wading column %d" % deepest)

    # H. the resident
    keep = "\n".join(fns.get("the_hummock/spawn") or [])
    sp = re.search(r'spawn_at \{x:"([\d.]+)",y:(\d+),z:"([\d.]+)",species:"(\w+)",props:"([^"]*)"\}', keep)
    if not sp:
        probs.append("resident: the spawn function carries no spawn_at call")
    else:
        if (float(sp[1]), int(sp[2]), float(sp[3])) != (ax + 0.5, ay, az + 0.5):
            probs.append("resident: spawns at %s, the spot is %s" % ((sp[1], sp[2], sp[3]), (ax + 0.5, ay, az + 0.5)))
        if sp[4] != pk["species"].split(":")[1]:
            probs.append("resident: species %s" % sp[4])
        if "level=%d" % pk["level"] not in sp[5].split() or "scale_modifier=%s" % pk["scale_modifier"] not in sp[5].split():
            probs.append("resident: props %r lack level or scale_modifier" % sp[5])
    if not (0 < pk["trigger"] < pk["leash"]):
        probs.append("resident: trigger %s is not inside leash %s" % (pk["trigger"], pk["leash"]))
    for need in ("tag @s add cobblers.res_dormant", "NoAI:1b", "PersistenceRequired:1b"):
        if need not in "\n".join(fns.get("the_hummock/bind") or []):
            probs.append("resident: bind lacks %s" % need)
    keeper = "\n".join(fns.get("keeper") or [])
    if "hummock_mere/the_hummock/keep" not in keeper:
        probs.append("resident: the keeper loop never runs its keep")
    keepf = "\n".join(fns.get("the_hummock/keep") or [])
    if "tag=!cobblers.guardian" not in keepf:
        probs.append("resident: keep does not skip a guardian (the blackout's)")

    # I. level and gate, from trainers.json
    tiers = jload("encounter_design.json")["rules"]["tiers"]
    sub = _sub_of(ax, az)
    tier = jload("encounter_design.json")["tables"][sub]["tier"] if sub else None
    cap = tiers[str(tier)]["cap"] if tier else None
    if sub != r["subregion"]:
        probs.append("site: the creature stands in %s, the record says %s" % (sub, r["subregion"]))
    if cap is not None and pk["level"] < cap + doc["rules"]["level_over_cap_min"]:
        probs.append("level: L%d is under %d over the tier-%s cap %d" % (pk["level"], doc["rules"]["level_over_cap_min"], tier, cap))
    aces = jload("trainers.json")["generation_contract"]["gym_ace_levels"]
    holds = [i for i, v in enumerate(aces) if v >= pk["level"]]
    if not holds or pk["gate"] != "gym%d_cleared" % holds[0]:
        probs.append("gate: %s but the first cap holding L%d is after gym %s" % (pk["gate"], pk["level"], holds[:1]))
    elif holds[0] >= 1 and aces[holds[0] - 1] >= pk["level"]:
        probs.append("gate: a player one badge earlier already holds the cap")
    notes.append("level L%d vs tier %s cap %s; caps after n badges %s -> gate %s" % (pk["level"], tier, cap, aces, pk["gate"]))

    # J. siting, recomputed
    paths = jload("route_paths.json")["paths"]
    cols = {(x, z) for (x, _y, z) in blocks} | {(c[0], c[2]) for c in clears} | {(c[3], c[5]) for c in clears}
    dp = min(_path_dist(x, z, paths) for x, z in list(cols)[::37] + [(ax, az), (cx, cz)])
    if dp < doc["rules"]["path_clearance"]:
        probs.append("siting: %.0f blocks from a route path (needs %d)" % (dp, doc["rules"]["path_clearance"]))
    tmin = 1e9
    for t in jload("towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        for x, z in list(cols)[::7]:
            tmin = min(tmin, math.hypot(max(f["min_x"] - x, x - f["max_x"], 0), max(f["min_z"] - z, z - f["max_z"], 0)))
    if tmin < doc["rules"]["town_clearance"]:
        probs.append("siting: %.0f blocks from a town footprint (needs %d)" % (tmin, doc["rules"]["town_clearance"]))
    for b in jload("habitat_blocks.json")["blocks"]:
        if b.get("style") == "activated":
            d = math.hypot(b["position"]["x"] - ax, b["position"]["z"] - az)
            if d < b["activated"]["spawn_range"] + pk["leash"]:
                probs.append("siting: the leash overlaps Habitat Block %s" % b["id"])
    for k, zone in jload("rift_zones.json")["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                probs.append("siting: inside Rift zone %s" % k)
    notes.append("siting: path %.0f, town %.0f" % (dp, tmin))

    # K. the roadside sign, from the route and the footprint
    w = doc["waysign"]
    wf = fns.get("hummock_waysign/build") or []
    wb, wc, wodd = replay(wf)
    signs = [(k, v) for k, v in wb.items() if bid(v) == "minecraft:mangrove_sign"]
    if len(signs) != 1 or wodd:
        probs.append("waysign: expected one mangrove sign and nothing unreadable, got %d / %s" % (len(signs), wodd[:1]))
    else:
        (sx, sy, sz), st = signs[0]
        path = jload("route_paths.json")["paths"][w["route"]]
        fp = next(t for t in jload("towns.json")["towns"] if t["id"] == w["after_town"])["footprint"]
        i0 = next(i for i, p in enumerate(path) if not (fp["min_x"] <= p[0] <= fp["max_x"] and fp["min_z"] <= p[1] <= fp["max_z"]))
        i = i0 + w["beyond_blocks"]
        q = path[i]
        dist = math.hypot(sx - q[0], sz - q[1])
        if abs(dist - w["offset"]) > 1.5:
            probs.append("waysign: %.1f blocks from the route point %d past the footprint, expected %d" % (dist, w["beyond_blocks"], w["offset"]))
        vx, vz = path[i + 3][0] - path[i - 3][0], path[i + 3][1] - path[i - 3][1]
        cross = vx * (sz - q[1]) - vz * (sx - q[0])
        if (cross < 0) != (w["side"] == "left"):
            probs.append("waysign: on the wrong side of the road (cross %.1f, wanted %s)" % (cross, w["side"]))
        if sy != g(sx, sz) + 1 or W.level(sx, sz) is not None:
            probs.append("waysign: not on a dry column's ground + 1")
        rot = int(re.search(r"rotation=(\d+)", st)[1])
        fx, fz = -math.sin(math.radians(rot * 22.5)), math.cos(math.radians(rot * 22.5))
        n = math.hypot(vx, vz)
        if (fx * -vx + fz * -vz) / n < math.cos(math.radians(23)):
            probs.append("waysign: the face does not point back at the traveller (rotation %d)" % rot)
        lines = re.findall(r"'\"([^\"]*)\"'", st)
        if lines != w["lines"] or len(lines) != 4 or any(len(t) > 15 for t in lines):
            probs.append("waysign: text %s" % lines)
        if any(c[1] <= W.level(sx, sz) if W.level(sx, sz) is not None else False for c in wc):
            probs.append("waysign: a clear reaches the water")
    for sg in next(p for p in r["pieces"] if p["kind"] == "signs")["signs"]:
        lines = sg["lines"]
        if len(lines) != 4 or any(len(t) > 15 for t in lines):
            probs.append("sign text %s does not fit" % lines)

    # L. the probes name what the replay writes, and the steps hold what is written
    pr = jload("world_probes.json")["places"].get("hummock_mere")
    if not pr:
        probs.append("probes: places.hummock_mere is absent from data/world_probes.json")
    else:
        allw = dict(blocks)
        allw.update(wb)
        for p in pr:
            if "block" in p:
                x, y, z, st = p["block"]
                if bid(st) == "minecraft:air":
                    if (x, y, z) in allw:
                        probs.append("probe %r: expects air where the pack writes %s" % (p["what"], allw[(x, y, z)]))
                elif bid(allw.get((x, y, z), "")) != bid(st):
                    probs.append("probe %r: the pack writes %s at %s, the probe expects %s" % (p["what"], allw.get((x, y, z)), (x, y, z), st))
            else:
                if "cobblers.res.%s" % pk["id"] not in p["entity"] or p.get("count") != 1:
                    probs.append("probe %r: not the resident by its tag" % p["what"])
    box = [min(x for x, _y, _z in blocks), min(z for _x, _y, z in blocks), max(x for x, _y, _z in blocks), max(z for _x, _y, z in blocks)]
    import hummock_mere as HM      # the artifact under test: the steps it emits are read, not used to derive anything
    steps = HM.placement_steps() + HM.entity_steps()
    holds = [s[1] for s in steps if s[0] == "cmd" and s[1].startswith("forceload add ")]
    boxes = [tuple(int(v) for v in h.split()[2:]) for h in holds]
    if not any(b[0] <= box[0] and b[1] <= box[1] and box[2] <= b[2] and box[3] <= b[3] for b in boxes):
        probs.append("steps: no forceload hold covers the written box %s (holds %s)" % (box, boxes))
    summon = [s[1] for s in steps if s[0] == "cmd" and "spawnpokemonat" in s[1]]
    if len(summon) != 1:
        probs.append("steps: %d summons, expected one" % len(summon))
    else:
        c = summon[0]
        if "unless entity @e[type=cobblemon:pokemon,tag=cobblers.res.%s]" % pk["id"] not in c or "Species:\"%s\"" % pk["species"] not in c:
            probs.append("steps: the summon is not guarded on tag AND species")
        if "scale_modifier=%s" % pk["scale_modifier"] not in c or "level=%d" % pk["level"] not in c:
            probs.append("steps: the summon lacks level or scale_modifier")
    # M. registration
    rt = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    for need in ('"R9HM"', '"R18HM"'):
        if need not in rt:
            probs.append("reapply.py does not register %s" % need)
    if '"R9HM"' in rt and '("R9E"' in rt and not rt.index('"R9HM"') < rt.index('("R9E"'):
        probs.append("reapply.py: R9HM does not come before R9E")
    if '"R18HM"' in rt and '"R18FS"' in rt and not rt.index('"R18FS"') < rt.index('"R18HM"'):
        probs.append("reapply.py: R18HM does not come after R18FS")
    if rt.count('"cobblers_hummock_mere"') != 2:
        probs.append("reapply.py names cobblers_hummock_mere %d times (SERVER_PACKS and WORLD_LOCAL once each)" % rt.count('"cobblers_hummock_mere"'))
    return probs, notes


def _sub_of(x, z):
    from subregion_boxes import point_in_polygon
    design = jload("encounter_design.json")
    subs = [s["id"] for s in jload("regions.json")["subregions"]
            if any(point_in_polygon(x, z, p) for p in s.get("polygons") or []) and s["id"] in design["tables"]]
    return subs[0] if subs else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    probs, notes = audit(a.pack, source_root=a.source_root)
    for n in notes:
        print("  " + n)
    for p in probs:
        print("PROBLEM " + p)
    print("hummock_mere_audit: %d problem(s)" % len(probs))
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())
