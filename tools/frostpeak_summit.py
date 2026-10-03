#!/usr/bin/env python
"""Frostpeak's summit dressed round Articuno's tower: wind-scoured tors with rime and a sheltered lee of fellfield
plants, and the old pilgrims' way to the tower's north door, marked by cairns.

Generated from data/frostpeak_summit.json into the world-local datapack build/datapacks/cobblers_frostpeak_summit.

The owner, 2026-10-02, standing on the summit in staging: "there should be some foliage and something else up here."
The design and every rule are in the data file; in short, one west wind (the repository's krummholz already lean
east, tools/foliage_objects.py krummholz) explains every block:

  the tors     one per 30-degree slot on the rim (radius 40-54), bearing and radius nudged by a hash of the slot,
               each a repository boulder (tools/foliage_objects.py boulder, moss off) sunk one block. A slot whose
               tor, rime or lee would touch the way, the tower or the edge is skipped and reported.
  the rime     packed ice on the west face of each tor, its share rising with the tor's exposure to the west wind.
  the lee      east of each row of a tor, out to twice the row's height: coarse soil with ferns and grass nearest the
               rock, then dead cushions, then scoured stone with moss, then a drift of snow layers. Each cell's plant
               comes from a hash of the cell against its band's shares, never a random stream, so a rebuild is
               byte-identical. Nothing woody: y310 is 165 blocks above the snowy_peak preset's treeline.
  the way      a threshold of old flagstones straight out of the north door, then a worn line of gravel and stone
               to the rim on the long west ridge, the bearing whose ground stays highest 100-200 blocks out.
  the cairns   gateposts at the threshold, one every 11 blocks along the way alternating sides (every third fallen,
               strewn downwind), and a taller marker at the rim.

Nothing here refers to the tower's altar, runs a command or gates anything; nothing emits light (dark by design); no
block is a spawn condition (tools/frostpeak_summit_audit.py checks all of it from the written pack, independently).
Ground comes from tools/ground.py (the canonical heightmap, rounded), never a world.

The step for tools/reapply.py, after R18A (the tower): placement_steps() -- hold the summit's chunks, run
`cobblers:frostpeak_summit/build`, release. The function also force-loads its own chunks.

  python tools/frostpeak_summit.py build [--source-root R] [--out DIR]   write the pack and derived/frostpeak_summit/
  python tools/frostpeak_summit.py plan  [--source-root R]               the numbers, the step and the probes
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import foliage_objects  # noqa: E402
import function_limits  # noqa: E402

DATA = ROOT / "data" / "frostpeak_summit.json"
SITES = ROOT / "data" / "adopted_legendary_sites.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_frostpeak_summit"
REPORT = ROOT / "derived" / "frostpeak_summit"
NS = "cobblers"
FN = "frostpeak_summit"
ROCK = ("minecraft:stone", "minecraft:andesite", "minecraft:cobblestone", "minecraft:tuff")
SEAT_LIFT = 0           # added to every tor's seat; 0. A test mutates it to prove the audit's sight-line check bites
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class SummitError(SystemExit):
    pass


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def unit(*key):
    """A number in [0, 1) from a hash of the key: the same cell always gets the same answer."""
    h = hashlib.sha256("|".join(str(k) for k in key).encode()).hexdigest()
    return int(h[:12], 16) / float(16 ** 12)


def pick(table, u):
    """The first entry of [(value, share), ...] whose cumulative share exceeds u, or None."""
    acc = 0.0
    for value, share in table:
        acc += share
        if u < acc:
            return value
    return None


def tower_box(doc=None):
    """(x0, z0, x1, z1) inclusive of the tower's template box, from its placement and size."""
    doc = doc or load()
    rec = next((s for s in json.loads(SITES.read_text(encoding="utf-8"))["sites"]
                if s.get("id") == doc["tower"]["site"]), None)
    if rec is None:
        raise SummitError("data/adopted_legendary_sites.json has no %s" % doc["tower"]["site"])
    (x0, z0), (sx, _sy, sz) = rec["placement"]["corner"], rec["size"]
    return x0, z0, x0 + sx - 1, z0 + sz - 1


def _near_box(x, z, box, margin):
    x0, z0, x1, z1 = box
    return x0 - margin <= x <= x1 + margin and z0 - margin <= z <= z1 + margin


def _seg_dist(p, a, b):
    (px, pz), (ax, az), (bx, bz) = p, a, b
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz)), t


# ------------------------------------------------------------------------------------------------------------ the way
def arrival_bearing(g, doc):
    cx, cz = doc["site"]["centre"]
    rs = doc["way"]["ridge_search"]
    best = None
    for b in range(0, 360, rs["step_degrees"]):
        a = math.radians(b)
        dx, dz = math.sin(a), -math.cos(a)
        rr = range(rs["from"], rs["to"] + 1, rs["every"])
        score = sum(g(round(cx + dx * r), round(cz + dz * r)) for r in rr) / len(rr)
        if best is None or score > best[0]:
            best = (score, b)
    return best[1], best[0]


def way_line(g, doc, box):
    """The way's centreline [door end, threshold end, rim] as (x, z) floats, and the arrival bearing."""
    door = doc["tower"]["door"]
    cx, cz = doc["site"]["centre"]
    dx = (door["x"][0] + door["x"][1]) / 2.0
    p0 = (dx, box[1] - 1.0)                                   # the cell just north of the tower's box
    p1 = (dx, p0[1] - doc["way"]["threshold_length"])
    b, _score = arrival_bearing(g, doc)
    a = math.radians(b)
    r = doc["way"]["arrive_radius"]
    p2 = (cx + math.sin(a) * r, cz - math.cos(a) * r)
    return [p0, p1, p2], b


def way_cells(g, doc, line, box):
    """{(x, z): surface block or None (left under snow)} for every cell within half_width of the centreline and
    outside the tower's box (the way stops at the box's north edge; the template's own steps take over)."""
    hw = doc["way"]["half_width"] + 0.5
    xs = [p[0] for p in line]
    zs = [p[1] for p in line]
    out = {}
    for x in range(math.floor(min(xs) - hw), math.ceil(max(xs) + hw) + 1):
        for z in range(math.floor(min(zs) - hw), math.ceil(max(zs) + hw) + 1):
            if _near_box(x, z, box, 0):
                continue
            d0, _ = _seg_dist((x, z), line[0], line[1])
            d1, _ = _seg_dist((x, z), line[1], line[2])
            if min(d0, d1) > hw:
                continue
            table = doc["way"]["threshold"] if d0 <= d1 else doc["way"]["worn"]
            out[(x, z)] = pick(table, unit("way", x, z))
    return out


def cairns(doc, line):
    """[(kind, x, z)]: gateposts, then the way's cairns alternating sides, then the rim marker."""
    c = doc["cairns"]
    off, step = c["offset"], c["spacing"]
    out = []
    (ax, az), (bx, bz), (rx, rz) = line
    gz = round(bz + c["gatepost_back"])
    for side in (-1, 1):
        out.append(("standing", round(bx + side * off), gz))
    dx, dz = rx - bx, rz - bz
    L = math.hypot(dx, dz)
    ux, uz = dx / L, dz / L
    nx, nz = -uz, ux                                          # the left normal
    k, s = 0, float(step)
    while s < L - step / 2.0:
        side = 1 if k % 2 == 0 else -1
        kind = "fallen" if k % 3 == 2 else "standing"
        out.append((kind, round(bx + ux * s + nx * off * side), round(bz + uz * s + nz * off * side)))
        k += 1
        s += step
    out.append(("marker", round(rx + nx * 3), round(rz + nz * 3)))
    return out


def cairn_blocks(doc, kind, x, z, g):
    c = doc["cairns"]
    y = g(x, z)
    if kind == "fallen":
        return [(x, y + 1, z, c["fallen"]), (x + 1, y + 1, z, c["fallen"]),
                (x + 2, y + 1, z + (1 if unit("fallen", x, z) < 0.5 else -1), c["fallen"])]
    stack = c["marker"] if kind == "marker" else c["standing"]
    return [(x, y + 1 + i, z, b) for i, b in enumerate(stack)]


# ----------------------------------------------------------------------------------------------------------- the tors
def tor_shape(name, size):
    """{(dx, dy, dz): block} of a repository boulder with its moss turned off; dy 0 is its bottom layer."""
    rng = np.random.default_rng(int(hashlib.sha256(name.encode()).hexdigest()[:12], 16))
    b = foliage_objects.boulder(rng, *size, mossy=0.0)
    out = {k: v[0] for k, v in b.blocks.items() if v[0] in ROCK}
    lo = min(k[1] for k in out)
    return {(x, y - lo, z): v for (x, y, z), v in out.items()}


def plan_tor(g, doc, slot, name):
    t = doc["tors"]
    cx, cz = doc["site"]["centre"]
    b = t["first_bearing"] + slot * (360.0 / t["slots"]) + (unit(name, "b") * 2 - 1) * t["jitter_bearing"]
    r = t["ring"][0] + unit(name, "r") * (t["ring"][1] - t["ring"][0])
    a = math.radians(b)
    ox, oz = round(cx + math.sin(a) * r), round(cz - math.cos(a) * r)
    size = t["sizes"][slot % len(t["sizes"])]
    shape = tor_shape(name, size)
    rock = {}
    for (dx, dy, dz), blk in shape.items():
        x, z = ox + dx, oz + dz
        rock[(x, g(x, z) - t["sink"] + 1 + dy + SEAT_LIFT, z)] = blk
    return {"name": name, "bearing": b % 360, "radius": r, "origin": (ox, oz), "size": size, "rock": rock}


def rime(doc, tor, g):
    rm = doc["rime"]
    share = rm["low"] + (rm["high"] - rm["low"]) * (1 + math.cos(math.radians(tor["bearing"] - 270))) / 2
    out = {}
    for (x, y, z) in tor["rock"]:
        if y <= g(x, z) or (x - 1, y, z) in tor["rock"] or y <= g(x - 1, z):
            continue
        if unit(tor["name"], "rime", x, y, z) < share:
            out[(x - 1, y, z)] = rm["block"]
    return out, share


def lee(doc, tor, g):
    """{(x, y, z): block} east of each row of the tor."""
    L = doc["lee"]
    rows = {}
    for (x, y, z) in tor["rock"]:
        h = y - g(x, z)
        if h < 1:
            continue
        xe, hh = rows.get(z, (x, 0))
        rows[z] = (max(xe, x), max(hh, h))
    out = {}
    for z, (xe, h) in rows.items():
        reach = min(2 * h, L["reach_max"])
        for d in range(1, reach + 1):
            x = xe + d
            if any((x, yy, z) in tor["rock"] for yy in range(g(x, z) - 2, g(x, z) + 8)):
                continue
            band = next(bd for bd in L["bands"] if bd["d"][0] <= d <= bd["d"][1] or bd is L["bands"][-1])
            gy = g(x, z)
            out[(x, gy, z)] = band["soil"]
            plant = pick(band["plants"], unit(tor["name"], "lee", x, z))
            if plant == "minecraft:large_fern":
                out[(x, gy + 1, z)] = "minecraft:large_fern[half=lower]"
                out[(x, gy + 2, z)] = "minecraft:large_fern[half=upper]"
            else:
                out[(x, gy + 1, z)] = plant or "minecraft:air"
        for i, layers in enumerate(L["drift_layers"]):
            x = xe + reach + 1 + i
            out[(x, g(x, z) + 1, z)] = "minecraft:snow[layers=%d]" % layers
    return out


def _footprint(blocks):
    return {(x, z) for x, _y, z in blocks}


# ----------------------------------------------------------------------------------------------------------- the plan
def plan(doc, g):
    box = tower_box(doc)
    cx, cz = doc["site"]["centre"]
    line, bearing = way_line(g, doc, box)
    way = way_cells(g, doc, line, box)
    blocks = {}
    for (x, z), surface in sorted(way.items()):
        gy = g(x, z)
        if surface:
            blocks[(x, gy, z)] = surface
        blocks[(x, gy + 1, z)] = "minecraft:air"
    cairn_list = cairns(doc, line)
    for kind, x, z in cairn_list:
        for bx, by, bz, blk in cairn_blocks(doc, kind, x, z, g):
            blocks[(bx, by, bz)] = blk
    t = doc["tors"]
    taken = set(_footprint(blocks))
    tors, skipped = [], []
    for slot in range(t["slots"]):
        name = "frostpeak_summit_tor_%02d" % (slot + 1)
        tor = plan_tor(g, doc, slot, name)
        ice, share = rime(doc, tor, g)
        lee_blocks = lee(doc, tor, g)
        cells = _footprint(tor["rock"]) | _footprint(ice) | _footprint(lee_blocks)
        why = None
        for (x, z) in cells:
            if _near_box(x, z, box, doc["tower"]["clearance"]):
                why = "the tower"
            elif min(_seg_dist((x, z), line[0], line[1])[0], _seg_dist((x, z), line[1], line[2])[0]) < t["path_clearance"]:
                why = "the way"
            elif math.hypot(x - cx, z - cz) > doc["site"]["dress_radius"]:
                why = "the edge"
            elif math.hypot(x - cx, z - cz) < doc["table"]["keep_bare_radius"]:
                why = "the bare table"
            elif (x, z) in taken:
                why = "another tor"
            if why:
                break
        if why:
            skipped.append({"tor": name, "bearing": round(tor["bearing"], 1), "radius": round(tor["radius"], 1),
                            "why": "would reach %s" % why})
            continue
        taken |= cells
        blocks.update(lee_blocks)
        blocks.update(ice)
        blocks.update(tor["rock"])
        tors.append({"tor": name, "origin": list(tor["origin"]), "bearing": round(tor["bearing"], 1),
                     "radius": round(tor["radius"], 1), "rock": len(tor["rock"]), "rime": len(ice),
                     "rime_share": round(share, 2),
                     "plants": sum(1 for v in lee_blocks.values()
                                   if v.split("[")[0] in ("minecraft:large_fern", "minecraft:fern",
                                                          "minecraft:short_grass", "minecraft:dead_bush",
                                                          "minecraft:moss_carpet") and "upper" not in v),
                     "top_y": max(y for _x, y, _z in tor["rock"])})
    return {"blocks": blocks, "way": {"line": [[round(a, 1), round(b, 1)] for a, b in line], "bearing": bearing,
                                      "cells": len(way), "worn": sum(1 for v in way.values() if v)},
            "cairns": [{"kind": k, "at": [x, z]} for k, x, z in cairn_list], "tors": tors, "skipped": skipped}


def commands(p):
    lines = ["# Generated by tools/frostpeak_summit.py from data/frostpeak_summit.json. Re-run to rebuild; do not edit.",
             "# Frostpeak's summit round Articuno's tower: tors, rime, the lee's plants, the pilgrims' way and its cairns.",
             "# Run after the tower (re-apply step R18A). Writes no light, no spawn condition, nothing in the tower's box."]
    # bottom-up, so a plant's soil and a large fern's lower half are in place before what stands on them
    for (x, y, z), blk in sorted(p["blocks"].items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        lines.append("setblock %d %d %d %s" % (x, y, z, blk))
    lines = function_limits.ensure_loaded(lines)
    bad = function_limits.check_lines(lines, "%s/build" % FN)
    if bad:
        raise SummitError("the build has %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    return lines


def build(g):
    doc = load()
    p = plan(doc, g)
    files = {"pack.mcmeta": {"pack": {"pack_format": 48, "description":
                                      "Cobblers: Frostpeak's summit round Articuno's tower (generated by "
                                      "tools/frostpeak_summit.py from data/frostpeak_summit.json)"}},
             "data/%s/function/%s/build.mcfunction" % (NS, FN): commands(p)}
    return files, p


def hold_box(doc=None):
    """(x0, z0, x1, z1): the square round the table that holds everything the pack may write (the audit refuses a
    write past path_radius + HOLD_PAD - 1, so this box always covers the build)."""
    doc = doc or load()
    (cx, cz), r = doc["site"]["centre"], doc["site"]["path_radius"] + HOLD_PAD
    return cx - r, cz - r, cx + r, cz + r


HOLD_PAD = 4


def placement_steps():
    """[(kind, value)] for tools/reapply.py, after R18A: hold the summit's chunks, build, release. Needs no
    heightmap: the box comes from the data file."""
    hold = "%d %d %d %d" % hold_box()
    return [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (NS, FN)),
            ("cmd", "forceload remove " + hold)]


def probes(p):
    """In-world checks for the integrating session, each an `execute if block` that should succeed."""
    out = []
    b = p["blocks"]

    def first(pred, what):
        for (x, y, z), blk in sorted(b.items()):
            if pred(blk):
                out.append({"what": what, "check": "execute if block %d %d %d %s" % (x, y, z, blk.split("[")[0])})
                return

    top = max(((x, y, z) for (x, y, z), v in b.items() if v in ROCK), key=lambda k: (k[1], k), default=None)
    if top:
        out.append({"what": "the highest rock of the summit's tors",
                    "check": "execute if block %d %d %d %s" % (top + (b[top],))})
    first(lambda v: v == "minecraft:packed_ice", "rime on a tor's west face")
    first(lambda v: v == "minecraft:fern", "a fern in a tor's lee")
    first(lambda v: v.startswith("minecraft:large_fern[half=lower"), "a large fern in a tor's lee")
    first(lambda v: v == "minecraft:cobblestone_wall", "a cairn's cap")
    first(lambda v: v == "minecraft:stone_bricks", "a flagstone of the threshold")
    first(lambda v: v == "minecraft:gravel", "the worn way")
    return out


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, content in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(content) + "\n" if isinstance(content, list) else json.dumps(content, indent=2) + "\n"
        f.write_text(body, encoding="utf-8", newline="\n")


def summary(p):
    counts = {}
    for v in p["blocks"].values():
        k = v.split("[")[0]
        counts[k] = counts.get(k, 0) + 1
    return {"way": p["way"], "cairns": p["cairns"], "tors": p["tors"], "skipped": p["skipped"],
            "blocks": dict(sorted(counts.items())), "probes": probes(p)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("build", "plan"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    g = G.Ground(a.source_root)
    if a.action == "plan":
        p = plan(load(), g)
        s = summary(p)
        s["steps"] = placement_steps()
        print(json.dumps(s, indent=1))
        return 0
    files, p = build(g)
    write(files, a.out)
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "report.json").write_text(json.dumps(summary(p), indent=1) + "\n", encoding="utf-8")
    n = len(files["data/%s/function/%s/build.mcfunction" % (NS, FN)])
    print("wrote %s (%d lines in %s:%s/build; %d tors, %d skipped, %d cairns, way %d cells at bearing %d)"
          % (a.out, n, NS, FN, len(p["tors"]), len(p["skipped"]), len(p["cairns"]), p["way"]["cells"],
             p["way"]["bearing"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
