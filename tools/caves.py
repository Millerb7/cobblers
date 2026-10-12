#!/usr/bin/env python
"""The cave kit (docs/mechanics/LEGENDARY_HOMES.md section 4), from data/caves.json: a cave is a timbered mouth, an incline
down, a drift, an optional antechamber and gate, and an oval chamber with a habitat block and, for a boss, a keeper.

The first three caves: K1 Stoneford Cut (an ungated early cave, Gible its rare spawn), K2 The Singing Hollow (Meloetta, a
repeatable chamber spawn behind a partition that opens at gym6_cleared, Beldum its antechamber's power line) and K3 The Relay
Fault (Miraidon, a post-Champion area boss kept by a keeper, behind a partition that opens at champion_cleared).

What it reuses, by name (CLAUDE.md principle 6: nothing new where a pattern exists):

  siting and clearance   tools/mining_caves.py Clearance (towns, routed legs and route paths, spawn-corridor boxes, authored
                         x/z, earthworks and templates, other packs' writes, painted water, the water export) and the shape of
                         its search; tools/mines.py frame, h32, sid, column_runs, BoxGround. Spawn-free zones and the other
                         Habitat Blocks are keep-clear through the authored points (the zones live in data/spawn_suppression.json
                         and data/habitat_blocks.json, both read by authored_points)
  the shell              tools/legendaries.py's rule, solid rock round every void, but as a column hull (data/caves.json
                         geometry.rules), so the sealing is arithmetic
  the gate               tools/legendaries.py files() near / open / close: a barrier partition that opens while a flagged player
                         stands in the antechamber and closes when none does and nobody is in the door, link or chamber
  the Habitat Blocks     tools/habitat_blocks.py commands() writes them (this tool adds the records to data/habitat_blocks.json
                         and the pools to data/spawns.json; tools/compile_spawns.py compiles the pools, R9E places the blocks)
  the boss keeper        tools/drowned_quarry.py keeper_files(): one tagged wild Pokemon on its spot, dormant until a player is in
                         the chamber, gone on two loaded passes in a row, back after a return clock. Never touches a blackout
                         guardian (data/system_contracts.json C25). New here: the clock is 24,000 ticks after a faint and 72,000
                         after a catch (a pokemon_captured callback sets the flag), and it spawns only while a player holding
                         the gate flag is near

  python tools/caves.py site <cave id> [--top N]     candidate mouths, best first; nothing written
  python tools/caves.py author [<cave id>] [--resite] site every cave with no mouth yet; write data/caves.json and the derived
                                                     records in data/habitat_blocks.json, data/spawns.json, data/world_probes.json
  python tools/caves.py report                       every cave's checks and counts; nothing written
  python tools/caves.py build                        -> build/datapacks/cobblers_caves, derived/caves/plan.json

  --inputs-root <full checkout>   where build/datapacks, build/paint, derived/routes and derived/water_shape are read
                                  (default: this checkout). Run once per export by tools/reapply.py step R9CK.

What this does NOT cover (CLAUDE.md "Our list is not the world"): the keeper and the gate act only on the caves in
data/caves.json. A Pokemon another system keeps in a cave (a trainer's, a raid den's) is not a boss here; a guardian the
blackout rebuilds near a boss spot is counted as present by species and tag only within `guardian_search_radius`.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402
import mines as M              # noqa: E402
import mining_caves as MC      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "caves.json"
HABITATS = ROOT / "data" / "habitat_blocks.json"
SPAWNS = ROOT / "data" / "spawns.json"
PROBES = ROOT / "data" / "world_probes.json"
REGIONS = ROOT / "data" / "regions.json"
LEGENDARIES = ROOT / "data" / "legendaries.json"
PROGRESSION = ROOT / "data" / "progression.json"
PACK = "cobblers_caves"
OUT = ROOT / "build" / "datapacks" / PACK
PLAN = ROOT / "derived" / "caves" / "plan.json"
NS = "cobblers"
FOLDER = "caves"
F = "%s:%s" % (NS, FOLDER)
AIR = "minecraft:air"
BARRIER = "minecraft:barrier"
LANTERN_UP = "minecraft:lantern[hanging=false,waterlogged=false]"
LANTERN_HANG = "minecraft:lantern[hanging=true,waterlogged=false]"
CLUSTER = "minecraft:amethyst_cluster[facing=up,waterlogged=false]"
PRESENT = -2147483648     # a boss's clock: seen present
NEVER = -2147483647       # a boss's clock: never yet brought in
FRONTS = M.FRONTS
YAW = {"north": 180, "south": 0, "west": 90, "east": 270}   # facing the mouth, up the passage's -d: Minecraft yaw 0 is south, 90 west
KINDS = ("incline", "drift", "crawl")
FEATURES = ("none", "columns", "crystal")
MODES = ("power_line", "rare_spawn", "area_boss")
GENERATED = "tools/caves.py"
POLICY_SCOPE = "caves"
# ground: the functions that read a world, each only to check (tools/ground_rule.py); this tool reads none
WORLD_READS: set = set()


class CaveError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def base(block):
    return block.split("[")[0].split("{")[0]


def pool_of(h):
    return h["pool"]["id"]


def species_id(name):
    """A species' id as data/spawns.json writes it: lower case, no spaces ('Tapu Fini' -> 'tapufini')."""
    return name.lower().replace(" ", "")


# ------------------------------------------------------------------ the layout: rows along the axis

def layout(spec, cave):
    """The cave's rows, from its record alone (no ground): {"rows": [...], "drop", "ante": (a0, a1) | None, "door": d | None,
    "link": (l0, l1) | None, "chamber": {...}, "total"}. A row is {"d", "kind", "hw", "h"}; kinds: mouth, stair, level, ante,
    door, link."""
    geo = spec["geometry"]
    ps = cave["passages"]
    rows = []
    first = ps[0]
    hw0, h0 = (first["width"] - 1) // 2, first["height"]
    drop = first["length"]
    rows.append({"d": 0, "kind": "mouth", "hw": hw0, "h": h0})
    for d in range(1, drop + 1):
        rows.append({"d": d, "kind": "stair", "hw": hw0, "h": h0})
    d = drop + 1
    for pi, p in enumerate(ps[1:], 1):
        for _ in range(p["length"]):
            rows.append({"d": d, "kind": "level", "hw": (p["width"] - 1) // 2, "h": p["height"], "seg": p["kind"], "pi": pi})
            d += 1
    ante = door = link = None
    a = cave.get("antechamber")
    if a:
        ante = (d, d + a["length"] - 1)
        for _ in range(a["length"]):
            rows.append({"d": d, "kind": "ante", "hw": a["half_width"], "h": a["height"]})
            d += 1
    if (cave.get("gate") or {}).get("kind") == "partition":
        door = d
        rows.append({"d": d, "kind": "door", "hw": geo["door_half_width"], "h": geo["door_height"]})
        d += 1
        link = (d, d + geo["link_rows"] - 1)
        for _ in range(geo["link_rows"]):
            rows.append({"d": d, "kind": "link", "hw": geo["door_half_width"], "h": geo["door_height"]})
            d += 1
    ch = cave["chamber"]
    dc = d + ch["rz"]
    return {"rows": rows, "drop": drop, "ante": ante, "door": door, "link": link,
            "chamber": {"d0": d, "dc": dc, "d1": dc + ch["rz"], "rx": ch["rx"], "rz": ch["rz"], "h": ch["h"]},
            "total": dc + ch["rz"] + 1}


def in_oval(u, d, dc, rx, rz):
    return u * u * rz * rz + (d - dc) ** 2 * rx * rx <= rx * rx * rz * rz


def oval_cells(ch):
    out = []
    for d in range(ch["d0"], ch["d1"] + 1):
        for u in range(-ch["rx"], ch["rx"] + 1):
            if in_oval(u, d, ch["dc"], ch["rx"], ch["rz"]):
                out.append((u, d))
    return out


def lamp_posts(spec, cave, lay):
    """[(u, d)] where a lantern post stands on a level floor: passages, antechamber corners, chamber."""
    geo = spec["geometry"]
    if (cave.get("light") or {}).get("dark_by_design"):
        return []
    every = (cave.get("light") or {}).get("lantern_every", geo["lantern_every"])
    out = []
    firsts = {}
    k = 0
    for r in lay["rows"]:
        if r["kind"] != "level" or r.get("seg") == "crawl" or r["hw"] < 1:
            continue
        first = firsts.setdefault(r["pi"], r["d"])
        if (r["d"] - first) % every == every // 2:
            out.append((-r["hw"] if k % 2 == 0 else r["hw"], r["d"]))
            k += 1
    if lay["ante"]:
        a0, a1 = lay["ante"]
        ahw = cave["antechamber"]["half_width"]
        out += [(-(ahw - 1), a1 - 1), (ahw - 1, a1 - 1)]
    ch = lay["chamber"]
    n = (cave.get("light") or {}).get("chamber_lanterns", 4)
    ur, dr = round(0.6 * ch["rx"]), round(0.55 * ch["rz"])
    spots = [(-ur, ch["dc"] - dr), (ur, ch["dc"] - dr), (-ur, ch["dc"] + dr), (ur, ch["dc"] + dr)]
    out += spots[:n]
    return out


def feature_cells(spec, cave, lay):
    """(columns, crystals): [(u, d)] of the chamber's feature."""
    ch, rec = lay["chamber"], cave["chamber"]
    f = rec.get("feature", "none")
    if f == "columns":
        c = round(0.5 * ch["rx"])
        return [(-c, ch["dc"]), (c, ch["dc"])], []
    if f == "crystal":
        post = {(u, d) for u, d in lamp_posts(spec, cave, lay)}
        cells = [(u, d) for u, d in oval_cells(ch)
                 if (u * u) / (ch["rx"] ** 2) + ((d - ch["dc"]) ** 2) / (ch["rz"] ** 2) >= 0.16 and (u, d) not in post]
        seed, fid = spec["seed"], M.sid(cave["id"])
        cells.sort(key=lambda c: (M.h32(seed, fid, c[0], c[1]), c))
        return [], cells[:rec.get("crystal_count", 8)]
    if f == "pool":
        raise CaveError("%s: the `pool` chamber feature is not built (K4's water needs a spawn-block policy entry first)" % cave["id"])
    return [], []


# ------------------------------------------------------------------ the geometry

def mouth_floor(rows0, ground, xz):
    hw = rows0["hw"]
    gs = sorted(ground(*xz(u, -1)) for u in range(-hw - 1, hw + 2))
    return gs[(len(gs) - 1) // 2]


def geometry(spec, cave, ground, anchor=None, front=None):
    """Everything a cave writes, from its mouth and the ground: {"cells": {(x, y, z): role}, ...}. Roles: air, floor, stair,
    fill, shell, post, beam, fence, lantern, hanglantern, column, crystal, barrier. Every broken rule is a problem."""
    geo = spec["geometry"]
    m = cave.get("mouth") or {}
    anchor = tuple(anchor or m["anchor"])
    front = front or m["front"]
    xz = M.frame(anchor, front)
    lay = layout(spec, cave)
    rows = lay["rows"]
    ch = lay["chamber"]
    drop = lay["drop"]
    mar, cov = geo["margins"], geo["cover_min"]
    y0 = mouth_floor(rows[0], ground, xz)
    yh = y0 - drop
    probs, cells = [], {}
    cols = {}                                    # (x, z) -> {"top", "m", "cut", "kind"}: the air columns

    def ft_of(r):
        d = r["d"]
        return y0 if d == 0 else (y0 - d + 1 if d <= drop else yh)

    def kind_cover(kind):
        return cov["room"] if kind in ("ante", "chamber") else cov["passage"]

    def put_col(x, z, ft, top, kind, cut, role):
        cols[(x, z)] = {"ft": ft, "top": top, "m": mar["cutting"] if cut else (mar["room"] if kind in ("ante", "chamber") else mar["passage"]),
                        "cut": cut, "kind": kind}
        g = ground(x, z)
        if ft - 1 - g > geo["max_fill"]:
            probs.append("column (%d, %d): built up %d under its floor, over %d" % (x, z, ft - 1 - g, geo["max_fill"]))
        for y in range(g + 1, ft):
            cells[(x, y, z)] = "fill"
        cells[(x, ft, z)] = role
        for y in range(ft + 1, top + 1):
            cells[(x, y, z)] = "air"

    cutting = 0
    for r in rows:
        ft = ft_of(r)
        at = ft + r["h"]
        hw = r["hw"]
        if r["kind"] in ("mouth", "stair"):
            gmin = min(ground(*xz(u, r["d"])) for u in range(-hw - 1, hw + 2))
            cut = gmin < at + 1 + cov["passage"]
            cutting += 1 if cut else 0
        else:
            cut = False
        r["ft"], r["cut"] = ft, cut
        for u in range(-hw, hw + 1):
            x, z = xz(u, r["d"])
            g = ground(x, z)
            top = max(g, at) + geo["clear_above"] if cut else at
            put_col(x, z, ft, top, r["kind"], cut, "stair" if r["kind"] == "stair" else "floor")
            if not cut and g - top < kind_cover(r["kind"]):
                probs.append("row d=%d (%s) column (%d, %d): %d of ground over its air top y%d, under %d"
                             % (r["d"], r["kind"], x, z, g - top, top, kind_cover(r["kind"])))
    if cutting > geo["max_cutting_rows"]:
        probs.append("%d open cutting rows, over max_cutting_rows %d" % (cutting, geo["max_cutting_rows"]))
    # the chamber
    for u, d in oval_cells(ch):
        x, z = xz(u, d)
        top = yh + ch["h"]
        if (x, z) in cols:
            probs.append("chamber cell (%d, %d) is already an air column of a row" % (x, z))
            continue
        put_col(x, z, yh, top, "chamber", False, "floor")
        g = ground(x, z)
        if g - top < cov["room"]:
            probs.append("chamber column (%d, %d): %d of ground over its air top y%d, under %d" % (x, z, g - top, top, cov["room"]))
    # the mouth's timber frame
    hw0, h0 = rows[0]["hw"], rows[0]["h"]
    for u in (-hw0 - 1, hw0 + 1):
        x, z = xz(u, 0)
        g = ground(x, z)
        for y in range(g + 1, y0 + 1):
            cells[(x, y, z)] = "fill"
        for y in range(y0 + 1, y0 + h0 + 1):
            cells[(x, y, z)] = "post"
    for u in range(-hw0 - 1, hw0 + 2):
        x, z = xz(u, 0)
        cells[(x, y0 + h0 + 1, z)] = "beam"
    x, z = xz(0, 0)
    if cells.get((x, y0 + h0, z)) == "air":
        cells[(x, y0 + h0, z)] = "hanglantern"
    # the door's barrier
    if lay["door"] is not None:
        r = next(q for q in rows if q["d"] == lay["door"])
        for u in range(-r["hw"], r["hw"] + 1):
            x, z = xz(u, r["d"])
            for y in range(yh + 1, yh + r["h"] + 1):
                cells[(x, y, z)] = "barrier"
    # lantern posts, columns, crystals
    for u, d in lamp_posts(spec, cave, lay):
        x, z = xz(u, d)
        if cells.get((x, yh + 1, z)) == "air" and cells.get((x, yh + 2, z)) == "air":
            cells[(x, yh + 1, z)] = "fence"
            cells[(x, yh + 2, z)] = "lantern"
        else:
            probs.append("lantern post (%d, %d) at u=%d d=%d does not stand in free air" % (x, z, u, d))
    cs, xs_ = feature_cells(spec, cave, lay)
    for u, d in cs:
        x, z = xz(u, d)
        if not in_oval(u, d, ch["dc"], ch["rx"], ch["rz"]):
            probs.append("column (u=%d, d=%d) is outside the chamber" % (u, d))
            continue
        for y in range(yh + 1, yh + ch["h"] + 1):
            if cells.get((x, y, z)) != "air":
                probs.append("column cell (%d, %d, %d) is not free air" % (x, y, z))
            cells[(x, y, z)] = "column"
    for u, d in xs_:
        x, z = xz(u, d)
        if cells.get((x, yh + 1, z)) == "air":
            cells[(x, yh + 1, z)] = "crystal"
    # the shell: a column hull round every air column
    shell = {}
    for (x, z), c in cols.items():
        m = c["m"]
        lo, hi = c["ft"] + 1 - m, c["top"] + m
        for dx in range(-m, m + 1):
            for dz in range(-m, m + 1):
                k = (x + dx, z + dz)
                e = shell.get(k)
                if e is None:
                    shell[k] = [lo, hi, c["cut"]]
                else:
                    e[0], e[1], e[2] = min(e[0], lo), max(e[1], hi), e[2] or c["cut"]
    for (x, z), (lo, hi, cut) in shell.items():
        cap = ground(x, z) if cut else ground(x, z) - 1
        for y in range(lo, min(hi, cap) + 1):
            if (x, y, z) not in cells:
                cells[(x, y, z)] = "shell"
    tops = {}
    for (x, y, z) in cells:
        tops[(x, z)] = max(tops.get((x, z), -999), y)
    # the apron in front of the mouth
    for u in range(-hw0 - 1, hw0 + 2):
        for d in range(-geo["approach_rows"], 0):
            x, z = xz(u, d)
            if abs(ground(x, z) - y0) > geo["approach_tolerance"]:
                probs.append("approach column (%d, %d): ground y%d is more than %d from the mouth floor y%d"
                             % (x, z, ground(x, z), geo["approach_tolerance"], y0))
    total = lay["total"]
    if not geo["length_min"] <= total <= geo["length_max"]:
        probs.append("the cave is %d rows long, outside %d..%d" % (total, geo["length_min"], geo["length_max"]))
    surface = sorted({(x, z) for (x, y, z) in cells if y > ground(x, z) or (y == ground(x, z) and cells[(x, y, z)] == "air")})
    xs, ys, zs = zip(*cells)

    def wbox(u0, u1, d0, d1, ya, yb):
        pts = [xz(u0, d0), xz(u1, d1), xz(u0, d1), xz(u1, d0)]
        return [min(p[0] for p in pts), ya, min(p[1] for p in pts), max(p[0] for p in pts), yb, max(p[1] for p in pts)]

    out = {"cells": cells, "problems": probs, "y0": y0, "yh": yh, "front": front, "anchor": list(anchor), "layout": lay,
           "bounds": [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)],
           "columns": sorted({(x, z) for x, _y, z in cells}), "surface": surface, "cutting_rows": cutting,
           "dug": sum(1 for (x, y, z), r in cells.items() if r in ("air", "lantern", "fence") and y <= ground(x, z)),
           "stand": [xz(0, -2)[0], y0 + 1, xz(0, -2)[1]], "tunnel_rows": [r["d"] for r in rows if not r["cut"]],
           "centre": [xz(0, ch["dc"])[0], yh, xz(0, ch["dc"])[1]]}
    if lay["ante"]:
        a0, a1 = lay["ante"]
        ahw = cave["antechamber"]["half_width"]
        out["ante_zone"] = wbox(-ahw, ahw, a0, a1, yh + 1, yh + cave["antechamber"]["height"])
        am = (a0 + a1) // 2
        out["ante_centre"] = [xz(0, am)[0], yh, xz(0, am)[1]]
    if lay["door"] is not None:
        dr = next(q for q in rows if q["d"] == lay["door"])
        out["door_box"] = wbox(-dr["hw"], dr["hw"], lay["door"], lay["door"], yh + 1, yh + dr["h"])
        # never shut anyone in: the door row, the link and the chamber, one block round
        out["inside_zone"] = wbox(-max(ch["rx"], dr["hw"]) - 1, max(ch["rx"], dr["hw"]) + 1, lay["door"] - 1, ch["d1"] + 1,
                                  yh, yh + max(ch["h"], dr["h"]) + 1)
    out["chamber_zone"] = wbox(-ch["rx"], ch["rx"], ch["d0"], ch["d1"], yh + 1, yh + ch["h"])
    out["ground"] = ground
    return out


# ------------------------------------------------------------------ where a cave may stand

def extent(spec, cave):
    lay = layout(spec, cave)
    ch = lay["chamber"]
    hws = [r["hw"] for r in lay["rows"]] + [ch["rx"]]
    return max(hws) + spec["geometry"]["margins"]["room"] + 2, lay["total"] + spec["geometry"]["margins"]["room"] + 2


def check_box(spec, cave):
    ur, dr = extent(spec, cave)
    r = cave["ring"]["max"] + max(ur, dr) + 8
    hx, hz = cave["host_anchor"]
    return (hx - r, hz - r, hx + r, hz + r)


def authored_doc(spec):
    ids = {h["id"]: "a Habitat Block of this file, inside its own cave" for c in spec["caves"] for h in c.get("habitat") or []}
    files = dict(spec["authored_exempt"]["files"])
    return {"residents": [], "rules": {"authored_clearance_exempt": ids, "authored_clearance_exempt_files": files}}


def clearance(spec, cave, g0, inputs_root=None, need_packs=False):
    return MC.Clearance({"keep_clear": spec["keep_clear"]}, check_box(spec, cave), g0, inputs_root, own_pack=PACK,
                        need_packs=need_packs, own_file=SPEC, authored_doc=authored_doc(spec),
                        own_points=own_habitat_points(spec))


def own_habitat_points(spec):
    """{(x, z)} of this file's own Habitat Blocks as data/habitat_blocks.json records them: their single-column
    writes land in cobblers_habitats (tools/habitat_blocks.py), which the other-pack rule would otherwise count."""
    ids = {h["id"] for c in spec["caves"] for h in c.get("habitat") or []}
    blocks = json.loads(HABITATS.read_text(encoding="utf-8"))["blocks"]
    return {(b["position"]["x"], b["position"]["z"]) for b in blocks if b["id"] in ids}


def block_range(cave, part):
    """The spawn_range of a part's activated Habitat Block: the chamber's rx; an antechamber's half width + 4."""
    return cave["chamber"]["rx"] if part == "chamber" else cave["antechamber"]["half_width"] + 4


def foreign_problems(spec, cave, gm):
    """Spawn-free zones and other Habitat Blocks' influence (the design's: 'add spawn-free zones and existing Habitat Block
    ranges'): no written column inside a spawn-free zone grown by spawn_free_margin, and none of this cave's activated blocks'
    reach (spawn_range) overlapping a natural ReplaceSpawns block's range of influence (EXP-021: overlapping influence spawns nothing)."""
    out = []
    m = spec["keep_clear"]["spawn_free_margin"]
    for z in load(ROOT / "data" / "spawn_suppression.json")["spawn_free_zones"]:
        x0, z0, x1, z1 = z["box"]
        hit = [c for c in gm["columns"] if x0 - m <= c[0] <= x1 + m and z0 - m <= c[1] <= z1 + m]
        if hit:
            out.append("%d written column(s) within %d of the spawn-free zone %s, e.g. %s" % (len(hit), m, z["id"], hit[0]))
    mine = {h["id"] for c in spec["caves"] for h in c.get("habitat") or []}
    pos = {}
    for h in cave.get("habitat") or []:
        c = gm["centre"] if h["part"] == "chamber" else gm["ante_centre"]
        pos[h["id"]] = (c, block_range(cave, h["part"]))
    for b in load(HABITATS)["blocks"]:
        if b["id"] in mine or b["style"] != "natural" or not b.get("replace_spawns"):
            continue
        bp = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
        for hid, (c, rng) in pos.items():
            d = math.dist(c, bp)
            if d < b["range_of_influence"] + rng:
                out.append("%s (reach %d) is %.1f from the natural block %s (range %d): their influence overlaps" % (hid, rng, d, b["id"], b["range_of_influence"]))
    return out


def cave_problems(spec, cave, gm, clear):
    probs = list(gm["problems"]) + foreign_problems(spec, cave, gm)
    hx, hz = cave["host_anchor"]
    ax, az = gm["anchor"]
    dist = math.hypot(ax - hx, az - hz)
    if not cave["ring"]["min"] <= dist <= cave["ring"]["max"]:
        probs.append("the mouth is %.0f from its host anchor, outside the ring %s" % (dist, cave["ring"]))
    bad = {}
    for c in gm["columns"]:
        w = clear.why(*c)
        if w:
            bad.setdefault(w, []).append(c)
    for c in gm["surface"]:
        if clear.tree(*c):
            bad.setdefault("within %d of a painted tree (a surface column)" % spec["keep_clear"]["tree_reach"], []).append(c)
    for w, cs in sorted(bad.items()):
        probs.append("%d written column(s) %s, e.g. %s" % (len(cs), w, cs[0]))
    return probs


def search(spec, cave, g0, clear, top=8, step=4):
    """Candidate mouths, best first: [(score, anchor, front, y0, dug)]. Anchors on a `step` grid inside the ring whose whole
    footprint is free; a cover estimate on the heightmap; then the full checks. Score: the distance from the host anchor plus
    0.3 of the cells dug (nearer is more a side trip of the town's; less cut is less scar)."""
    geo = spec["geometry"]
    ur, dr = extent(spec, cave)
    lay = layout(spec, cave)
    ch = lay["chamber"]
    hx, hz = cave["host_anchor"]
    x0, z0, x1, z1 = clear.box
    ground = M.BoxGround(g0, x0 - 8, z0 - 8, x1 + 8, z1 + 8)
    garr = ground.arr
    gx0, gz0 = ground.x0, ground.z0
    free = clear.code == 0
    sat = np.zeros((free.shape[0] + 1, free.shape[1] + 1), np.int32)
    sat[1:, 1:] = np.cumsum(np.cumsum(~free, 0), 1)

    def clear_rect(xa, za, xb, zb):
        if xa < x0 or za < z0 or xb > x1 or zb > z1:
            return False
        i0, j0, i1, j1 = za - z0, xa - x0, zb - z0 + 1, xb - x0 + 1
        return sat[i1, j1] - sat[i0, j1] - sat[i1, j0] + sat[i0, j0] == 0

    hw0 = lay["rows"][0]["hw"]
    drop = lay["drop"]
    cov = geo["cover_min"]
    rmin, rmax = cave["ring"]["min"], cave["ring"]["max"]
    maxh = max(r["h"] for r in lay["rows"])
    cands = []
    for front in FRONTS:
        for cz in range(hz - rmax, hz + rmax + 1, step):
            for cx in range(hx - rmax, hx + rmax + 1, step):
                dist = math.hypot(cx - hx, cz - hz)
                if not rmin <= dist <= rmax:
                    continue
                xz = M.frame((cx, cz), front)
                (ax_, az_), (bx_, bz_) = xz(-ur, -geo["approach_rows"]), xz(ur, dr)
                if not clear_rect(min(ax_, bx_), min(az_, bz_), max(ax_, bx_), max(az_, bz_)):
                    continue
                row = sorted(int(garr[xz(u, -1)[1] - gz0, xz(u, -1)[0] - gx0]) for u in range(-hw0 - 1, hw0 + 2))
                y0 = row[(len(row) - 1) // 2]
                yh = y0 - drop
                # the level part and the chamber need cover over their whole rectangle
                (ax_, az_), (bx_, bz_) = xz(-ur, drop + 1), xz(ur, dr - 1)
                zone = garr[min(az_, bz_) - gz0:max(az_, bz_) + 1 - gz0, min(ax_, bx_) - gx0:max(ax_, bx_) + 1 - gx0]
                if int(zone.min()) < yh + max(maxh, ch["h"]) + cov["room"]:
                    continue
                # the mouth must not be a long trench: count the incline rows without cover
                cut = 0
                for d in range(0, drop + 1):
                    ft = y0 if d == 0 else y0 - d + 1
                    gmin = min(int(garr[xz(u, d)[1] - gz0, xz(u, d)[0] - gx0]) for u in range(-hw0 - 1, hw0 + 2))
                    cut += 1 if gmin < ft + lay["rows"][0]["h"] + 1 + cov["passage"] else 0
                if cut > geo["max_cutting_rows"]:
                    continue
                cands.append((dist + 0.3 * cut * 10, (cx, cz), front))
    cands.sort()
    out = []
    for dist, anchor, front in cands[:6000]:
        gm = geometry(spec, cave, ground, anchor, front)
        if cave_problems(spec, cave, gm, clear):
            continue
        out.append((round(math.hypot(anchor[0] - hx, anchor[1] - hz) + 0.3 * gm["dug"] / 10, 1), list(anchor), front, gm["y0"], gm["dug"]))
        if top and len(out) >= top * 3:
            break
    out.sort(key=lambda o: (o[0], o[1], o[2]))
    return out[:top] if top else out


# ------------------------------------------------------------------ levels and gates

def flag_caps():
    """{flag id: highest level a thrower's cap allows after holding it}, from data/legendaries.json level_caps (the badge table)
    and the flag's own name: gymN_cleared -> N badges; champion_cleared -> the champion's 100."""
    t = load(LEGENDARIES)["level_caps"]["upper_bound_by_badges"]
    caps = {"champion_cleared": int(t["champion"])}
    for n in range(1, 9):
        caps["gym%d_cleared" % n] = int(t[str(n)])
    return caps


def progression_flags():
    return {f["id"] for f in load(PROGRESSION)["flags"]}


def band_of(x, z):
    """(sub-region id, level_band min, max, tier) of a point, from data/regions.json polygons and data/spawns.json bands."""
    import subregion_boxes as SB
    regs = load(REGIONS)["subregions"]
    bands = {s["id"]: s for s in load(SPAWNS)["subregions"]}
    for r in regs:
        if any(SB.point_in_polygon(x, z, poly) for poly in r["polygons"]) and r["id"] in bands:
            b = bands[r["id"]]["level_band"]
            return r["id"], int(b["minimum"]), int(b["maximum"]), b.get("tier")
    return None, None, None, None


def level_range(entry, band):
    lv = entry["level"]
    if lv == "band":
        return band
    if "-" in str(lv):
        a, b = str(lv).split("-")
        return int(a), int(b)
    return int(lv), int(lv)


def static_problems(spec):
    out = []
    geo = spec["geometry"]
    seen, flags, caps = set(), None, None
    try:
        flags, caps = progression_flags(), flag_caps()
    except (OSError, KeyError, ValueError) as exc:
        out.append("cannot read the progression flags or the level caps: %s" % exc)
    for c in spec["caves"]:
        cid = c["id"]
        if cid in seen:
            out.append("%s: a duplicate id" % cid)
        seen.add(cid)
        ps = c["passages"]
        if not ps or ps[0]["kind"] != "incline":
            out.append("%s: the first passage must be an incline" % cid)
            continue
        for i, p in enumerate(ps):
            if p["kind"] not in KINDS:
                out.append("%s: passage %d kind %r is not one of %s" % (cid, i, p["kind"], ", ".join(KINDS)))
            if p["width"] % 2 == 0 or p["width"] < 1:
                out.append("%s: passage %d width %d must be odd" % (cid, i, p["width"]))
            if p["height"] < 2 or p["length"] < 1:
                out.append("%s: passage %d height/length" % (cid, i))
            if i > 0 and p["kind"] == "incline":
                out.append("%s: only the first passage may be an incline" % cid)
        a = c.get("antechamber")
        if a and a["half_width"] < 2:
            out.append("%s: antechamber half_width < 2" % cid)
        g = c.get("gate") or {"kind": "none"}
        if g["kind"] not in ("none", "partition"):
            out.append("%s: gate kind %r" % (cid, g["kind"]))
        if g["kind"] == "partition":
            if not a:
                out.append("%s: a partition needs an antechamber (the zone a flagged player stands in)" % cid)
            for f in g.get("flags") or []:
                if flags is not None and f not in flags:
                    out.append("%s: gate flag %s is not declared in data/progression.json" % (cid, f))
            if not g.get("flags"):
                out.append("%s: a partition gate needs flags" % cid)
        ch = c["chamber"]
        if ch["shape"] != "oval" or ch["rx"] < 3 or ch["rz"] < 3 or ch["h"] < 4:
            out.append("%s: chamber must be an oval with rx, rz >= 3 and h >= 4" % cid)
        if ch.get("feature", "none") not in FEATURES:
            out.append("%s: chamber feature %r is not built (%s)" % (cid, ch.get("feature"), ", ".join(FEATURES)))
        for k in ("shell", "floor", "stair", "timber", "fence", "column"):
            if k not in c["palette"]:
                out.append("%s: palette lacks %s" % (cid, k))
        occ = c["occupant"]
        if occ["mode"] not in MODES:
            out.append("%s: occupant mode %r" % (cid, occ["mode"]))
        if occ["mode"] == "area_boss":
            if "champion_cleared" not in (g.get("flags") or []):
                out.append("%s: an area boss is a native alpha, catchable only after the Champion; its gate must hold champion_cleared "
                           "(docs/mechanics/LEGENDARY_HOMES.md section 3)" % cid)
            if not 1 <= int(occ["level"]) <= 100:
                out.append("%s: boss level %r" % (cid, occ["level"]))
            if "alpha=true" not in occ["properties"]:
                out.append("%s: a boss is a native alpha (alpha=true)" % cid)
            k = occ["keeper"]
            if k["cooldown_faint_ticks"] != 24000 or k["cooldown_catch_ticks"] != 72000:
                out.append("%s: the respawn rule is 24,000 ticks after a faint and 72,000 after a catch (the owner, 2026-10-12)" % cid)
            if occ["guardian_tag"] != "cobblers.guardian":
                out.append("%s: guardian_tag must be cobblers.guardian (the blackout's)" % cid)
            if k["spawn_clear"] >= k["spawn_radius"] or k["trigger_radius"] >= k["settle_radius"]:
                out.append("%s: keeper radii out of order" % cid)
        # every habitat pool's levels are inside the gate's cap (the chamber of a gated cave) or the tier
        for h in c.get("habitat") or []:
            part = h["part"]
            if part not in ("antechamber", "chamber"):
                out.append("%s: habitat part %r" % (cid, part))
            if part == "antechamber" and not a:
                out.append("%s: a habitat block in an antechamber the cave does not have" % cid)
            for e in h["pool"]["entries"]:
                if e["bucket"] not in ("common", "uncommon", "rare", "ultra-rare"):
                    out.append("%s: pool %s entry %s bucket %r" % (cid, pool_of(h), e["species"], e["bucket"]))
                if part == "chamber" and caps and g.get("flags") and e["level"] != "band":
                    hi = level_range(e, (0, 0))[1]
                    known = [caps[f] for f in g["flags"] if f in caps]
                    if not known:
                        out.append("%s: gate flags %s have no level cap in data/legendaries.json" % (cid, g["flags"]))
                        continue
                    cap = min(known)
                    if hi > cap:
                        out.append("%s: pool %s: %s level %s is over the gate's cap %d" % (cid, pool_of(h), e["species"], e["level"], cap))
        if occ["mode"] == "rare_spawn":
            ents = [e for h in c["habitat"] for e in h["pool"]["entries"] if species_id(e["species"]) == occ["species"]]
            if not ents or ents[0]["bucket"] != "ultra-rare":
                out.append("%s: the rare-spawn occupant %s must be an ultra-rare entry of a habitat pool" % (cid, occ["species"]))
            # a second beast the same chamber hosts (K4: Nihilego beside Tapu Fini) is an ultra-rare entry of a chamber pool too
            for co in occ.get("co_occupants") or []:
                cents = [e for h in c["habitat"] if h["part"] == "chamber" for e in h["pool"]["entries"] if species_id(e["species"]) == co]
                if len(cents) != 1 or cents[0]["bucket"] != "ultra-rare":
                    out.append("%s: the co-occupant %s must be one ultra-rare entry of the chamber's pool" % (cid, co))
        elif occ.get("co_occupants"):
            out.append("%s: co_occupants are for a rare-spawn chamber only" % cid)
        if occ["mode"] == "power_line":
            ents = [e for h in c["habitat"] for e in h["pool"]["entries"] if species_id(e["species"]) == occ["species"]]
            if not ents or ents[0]["bucket"] not in ("rare", "ultra-rare"):
                out.append("%s: the power-line occupant %s must be a rare entry of a habitat pool" % (cid, occ["species"]))
    return out


# ------------------------------------------------------------------ the model

def model(spec=None, source_root=None, inputs_root=None, need_packs=False):
    """(plan, problems, notes): every cave's geometry."""
    spec = spec or load()
    g0 = G.Ground(source_root)
    probs = static_problems(spec)
    notes, plan = [], []
    for cave in spec["caves"]:
        if not cave.get("mouth"):
            probs.append("%s: no mouth (python tools/caves.py author)" % cave["id"])
            continue
        clear = clearance(spec, cave, g0, inputs_root, need_packs=need_packs)
        notes += ["%s: %s" % (cave["id"], n) for n in clear.notes]
        try:
            gm = geometry(spec, cave, g0)
        except CaveError as exc:
            probs.append(str(exc))
            continue
        probs += ["%s: %s" % (cave["id"], p) for p in cave_problems(spec, cave, gm, clear)]
        plan.append({"cave": cave, "geometry": gm})
    return plan, probs, notes


# ------------------------------------------------------------------ the pack

def block_of(cave, role, front):
    p = cave["palette"]
    if role in ("fill", "shell"):
        return p["shell"]
    if role == "floor":
        return p["floor"]
    if role == "stair":
        return "%s[facing=%s,half=bottom,shape=straight,waterlogged=false]" % (p["stair"], front)
    if role == "post":
        return "%s[axis=y]" % p["timber"]
    if role == "beam":
        return "%s[axis=%s]" % (p["timber"], "x" if front in ("north", "south") else "z")
    if role == "fence":
        return "%s[waterlogged=false]" % p["fence"]
    if role == "lantern":
        return LANTERN_UP
    if role == "hanglantern":
        return LANTERN_HANG
    if role == "column":
        return p["column"]
    if role == "crystal":
        return CLUSTER
    if role == "barrier":
        return BARRIER
    return AIR


def build_name(cave):
    return "build_%s" % cave["id"]


def build_lines(spec, entry):
    cave, gm = entry["cave"], entry["geometry"]
    front = gm["front"]
    cells = {c: block_of(cave, r, front) for c, r in gm["cells"].items()}
    head = ["# Generated by tools/caves.py from data/caves.json: %s (%s, %s)" % (cave["name"], cave["id"], cave["kind"]),
            "# chunks-loaded-by: the re-application (forceload add over RCON before this runs)",
            "# one final block for every cell: the shell, the floor and stairs, the air, the timber, the lantern posts, the"
            " feature and, behind a gate, the barrier door (closed)"]
    lines = head + M.column_runs(cells)
    if (cave.get("gate") or {}).get("kind") == "partition":
        lines.append("scoreboard players set #%s_open %s 0" % (cave["id"], spec["gate"]["objective"]))
    return lines


def box_args(b):
    return "%d %d %d %d %d %d" % tuple(b)


def sel_box(b):
    return "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (b[0], b[1], b[2], b[3] - b[0], b[4] - b[1], b[5] - b[2])


def flag_sel(spec, flags):
    return "advancements={%s}" % ",".join("%s:flag/%s=true" % (spec["flag_namespace"], f) for f in flags)


def grow(b, n):
    return [b[0] - n, b[1] - n, b[2] - n, b[3] + n, b[4] + n, b[5] + n]


def nbt(d):
    return "{%s}" % ",".join("%s:%s" % kv for kv in d.items())


def gate_files(spec, entry):
    cave, gm = entry["cave"], entry["geometry"]
    cid, obj = cave["id"], spec["gate"]["objective"]
    g = "gate/%s" % cid
    gf = "%s:%s/%s" % (NS, FOLDER, g)          # the function ids of this gate, as another function calls them
    fl = flag_sel(spec, cave["gate"]["flags"])
    ante, door, inside = gm["ante_zone"], gm["door_box"], gm["inside_zone"]
    fn = {}
    fn["%s/near" % g] = [
        "# %s. The gate is the advancement predicate on the line that opens it (tools/legendaries.py's near)." % cave["name"],
        "execute if entity @a[%s,%s] unless score #%s_open %s matches 1 run function %s/open" % (sel_box(ante), fl, cid, obj, gf),
        "# never shut anyone in: closed only when no flagged player is in the antechamber and nobody is in the door, link or chamber",
        "execute unless entity @a[%s,%s] unless entity @a[%s,gamemode=!spectator] if score #%s_open %s matches 1 run function %s/close"
        % (sel_box(ante), fl, sel_box(inside), cid, obj, gf)]
    fn["%s/open" % g] = [
        "# chunks-loaded-by: the player who trips it. %s/near only calls this while a flagged player stands in the antechamber" % gf,
        "scoreboard players set #%s_open %s 1" % (cid, obj),
        "fill %s %s replace %s" % (box_args(door), AIR, spec["gate"]["door_block"]),
        "playsound minecraft:block.beacon.activate master @a[%s] %d %d %d 1 0.6" % (sel_box(grow(inside, 6)), gm["centre"][0], gm["centre"][1], gm["centre"][2]),
        "tellraw @a[%s] %s" % (sel_box(grow(ante, 3)), json.dumps({"text": "The way opens.", "color": "aqua", "italic": True}))]
    fn["%s/close" % g] = [
        "# chunks-loaded-by: the player who trips it: near only runs while somebody is within %d blocks" % spec["gate"]["reach"],
        "scoreboard players set #%s_open %s 0" % (cid, obj),
        "fill %s %s replace %s" % (box_args(door), spec["gate"]["door_block"], AIR)]
    return fn


def boss_files(spec, entry):
    """The keeper of an area boss: tools/drowned_quarry.py keeper_files, with the clock set by how the last one ended and a spawn
    only for a player holding the gate flag."""
    cave, gm = entry["cave"], entry["geometry"]
    occ = cave["occupant"]
    k = occ["keeper"]
    cid, obj = cave["id"], spec["gate"]["objective"]
    T, D, Gd = occ["tag"], occ["dormant_tag"], occ["guardian_tag"]
    cx, cy, cz = gm["centre"]
    sy = cy + 1
    spot = (cx + 0.5, sy, cz + 0.5)
    sx = "x=%.1f,y=%d,z=%.1f" % spot
    at = "%.1f %d %.1f" % spot
    P = "%s:%s/boss/%s" % (NS, FOLDER, cid)
    fl = flag_sel(spec, cave["gate"]["flags"])
    sp = 'nbt={Pokemon:{Species:"cobblemon:%s"}}' % occ["species"]
    chz = gm["chamber_zone"]
    yaw = YAW[gm["front"]]
    n, ab, gone, resp, caught = ["#%s_%s" % (cid, s) for s in ("n", "abs", "gone", "resp", "caught")]
    mon = json.dumps({"text": occ["message"], "color": "gold", "italic": True}, ensure_ascii=False)
    fn = {}
    fn["boss/%s/load" % cid] = [
        "# the clock is set here only when it was never set: a restart never moves it",
        "execute unless score %s %s matches -2147483648.. run scoreboard players set %s %s %d" % (gone, obj, gone, obj, NEVER),
        "schedule function %s/keeper %dt replace" % (P, k["period_ticks"])]
    fn["boss/%s/keeper" % cid] = [
        "# the keeper's loop: only while the chamber's chunk is loaded (nobody has to be near for the return clock)",
        "execute store result score #now %s run time query gametime" % obj,
        "execute if loaded %d %d %d run function %s/keep" % (cx, cy, cz, P),
        "schedule function %s/keeper %dt replace" % (P, k["period_ticks"])]
    fn["boss/%s/keep" % cid] = [
        "# Present: ours by tag (a guardian keeps our tag), or a guardian the blackout REBUILT, which does not, found by its tag",
        "# and species near the spot. Never a bare distance, and never a guardian killed, held, woken or settled.",
        "execute store result score %s %s if entity @e[type=cobblemon:pokemon,tag=%s]" % (n, obj, T),
        "execute if score %s %s matches 0 if entity @e[type=cobblemon:pokemon,tag=%s,%s,distance=..%d,%s] run scoreboard players set %s %s 1"
        % (n, obj, Gd, sx, k["guardian_search_radius"], sp, n, obj),
        "# a duplicate (a spawn that raced a slow entity load): the furthest one goes, and NEVER a guardian",
        "execute if score %s %s matches 2.. run kill @e[type=cobblemon:pokemon,tag=%s,tag=!%s,%s,limit=1,sort=furthest]" % (n, obj, T, Gd, sx),
        "execute if score %s %s matches 1.. run scoreboard players set %s %s 0" % (n, obj, ab, obj),
        "execute if score %s %s matches 1.. run scoreboard players set %s %s %d" % (n, obj, gone, obj, PRESENT),
        "# a catch flag left by a Pokemon of this species caught while the boss lives (a released one recaught) is stale",
        "execute if score %s %s matches 1.. run scoreboard players set %s %s 0" % (n, obj, caught, obj),
        "execute if score %s %s matches 1.. as @e[type=cobblemon:pokemon,tag=%s,tag=!%s] run function %s/hold" % (n, obj, T, Gd, P),
        "execute if score %s %s matches 1.. run return 0" % (n, obj),
        "# absent on %d loaded passes in a row (entities load a moment after their chunk) before it counts as gone" % k["absent_passes"],
        "scoreboard players add %s %s 1" % (ab, obj),
        "execute if score %s %s matches ..%d run return 0" % (ab, obj, k["absent_passes"] - 1),
        "# first seen gone (fainted or caught): the length of the clock is chosen by how it ended (72,000 after a catch, 24,000 after",
        "# a faint), then the clock starts now. Only these lines move it, and only from the 'seen present' value",
        "execute if score %s %s matches %d run scoreboard players set %s %s %d" % (gone, obj, PRESENT, resp, obj, k["cooldown_faint_ticks"]),
        "execute if score %s %s matches %d if score %s %s matches 1 run scoreboard players set %s %s %d"
        % (gone, obj, PRESENT, caught, obj, resp, obj, k["cooldown_catch_ticks"]),
        "execute if score %s %s matches %d run scoreboard players operation %s %s = #now %s" % (gone, obj, PRESENT, gone, obj, obj),
        "scoreboard players set %s %s 0" % (caught, obj),
        "# the clock must have run; a boss never yet brought in (the 'never' value) has no clock",
        "scoreboard players operation #d %s = #now %s" % (obj, obj),
        "scoreboard players operation #d %s -= %s %s" % (obj, gone, obj),
        "execute if score %s %s matches %d run scoreboard players set #d %s 2000000000" % (gone, obj, NEVER, obj),
        "execute if score #d %s < %s %s run return 0" % (obj, resp, obj),
        "# never conjured in front of anyone, and only for a player holding the gate flag to meet it",
        "execute if entity @a[%s,distance=..%d] run return 0" % (sx, k["spawn_clear"]),
        "execute unless entity @a[%s,distance=..%d,gamemode=!spectator,%s] run return 0" % (sx, k["spawn_radius"], fl),
        "function %s/spawn" % P]
    fn["boss/%s/hold" % cid] = [
        "# as the Pokemon (never a guardian). DORMANT: held on its spot, facing the door; it wakes for a player in the chamber.",
        "execute if entity @s[tag=%s] unless entity @s[%s,distance=..%s] run tp @s %s %d 0" % (D, sx, k["home_tolerance"], at, yaw),
        "execute if entity @s[tag=%s] if entity @a[%s,gamemode=!spectator] run function %s/wake" % (D, sel_box(chz), P),
        "# AWAKE: it lies down again on its spot when nobody is within %d (a fight fled is not won)" % k["settle_radius"],
        "execute if entity @s[tag=!%s] unless entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/settle" % (D, sx, k["settle_radius"], P)]
    fn["boss/%s/wake" % cid] = [
        "# as the Pokemon: the trigger, a STATE CHECK on the keeper's own loop, never an advancement (CELEBI_WAKE.md 1)",
        "tag @s remove %s" % D,
        "data merge entity @s %s" % nbt(occ["awake_nbt"]),
        "tellraw @a[%s,distance=..48] %s" % (sx, mon),
        "playsound %s hostile @a[%s,distance=..48] %s 2 0.6" % (occ["sound"], sx, at)]
    fn["boss/%s/settle" % cid] = [
        "# as the Pokemon: everyone has gone, so it goes back to its spot and sleeps",
        "tp @s %s %d 0" % (at, yaw),
        "data merge entity @s %s" % nbt(occ["dormant_nbt"]),
        "tag @s add %s" % D]
    props = " ".join(["level=%d" % occ["level"]] + list(occ["properties"]))
    fn["boss/%s/spawn_at" % cid] = ["$spawnpokemonat $(x) $(y) $(z) %s %s" % (occ["species"], props)]
    fn["boss/%s/spawn" % cid] = [
        "# a wild one through the macro (EXP-046), then bound at once",
        "function %s/spawn_at {x:\"%.1f\",y:%d,z:\"%.1f\"}" % (P, spot[0], sy, spot[2]),
        "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..3,%s,limit=1,sort=nearest] run function %s/bind" % (at, T, sp, P)]
    fn["boss/%s/bind" % cid] = [
        "# as the new Pokemon: tagged, kept from the despawner (PersistenceRequired, EXP-041), dormant on its spot",
        "tag @s add %s" % T, "tag @s add %s" % D,
        "data merge entity @s %s" % nbt(occ["dormant_nbt"]),
        "tp @s %s %d 0" % (at, yaw),
        "scoreboard players set %s %s %d" % (gone, obj, PRESENT),
        "scoreboard players set %s %s 0" % (ab, obj),
        "scoreboard players set %s %s 0" % (caught, obj)]
    fn["boss/%s/caught" % cid] = [
        "# as the catcher of a %s within %d of the spot (the pokemon_captured callback): the keeper reads this at its next pass" % (occ["species"], k["catch_radius"]),
        "scoreboard players set %s %s 1" % (caught, obj)]
    return fn


def callbacks(spec, plan):
    """data/cobblemon/callbacks/pokemon_captured/cobblers_caves.molang: a boss species caught within catch_radius of its spot
    sets that boss's `caught` flag (MoLang strings are single-quoted: no apostrophe in a comment)."""
    lines = ["'Generated by tools/caves.py from data/caves.json. A boss species caught near its cave tells the cave keeper, which';",
             "'then waits the long clock. Anywhere else it does nothing.';", "t.id = q.pokemon.species.identifier;"]
    n = 0
    for e in plan:
        occ = e["cave"]["occupant"]
        if occ["mode"] != "area_boss":
            continue
        cx, cy, cz = e["geometry"]["centre"]
        k = occ["keeper"]
        cmd = ("execute as ' + q.player.uuid + ' at @s if entity @s[x=%d,y=%d,z=%d,distance=..%d] run function %s:%s/boss/%s/caught"
               % (cx, cy + 1, cz, k["catch_radius"], NS, FOLDER, e["cave"]["id"]))
        lines += ["t.id == 'cobblemon:%s' ? {" % occ["species"], "  q.run_command('%s');" % cmd, "};"]
        n += 1
    return {"data/cobblemon/callbacks/pokemon_captured/cobblers_caves.molang": "\n".join(lines) + "\n"} if n else {}


def pack_files(spec, plan):
    files = {"pack.mcmeta": json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: the cave kit (tools/caves.py, data/caves.json)"}}, indent=2) + "\n"}
    obj = spec["gate"]["objective"]
    load_ = ["# the caves' driver state (tools/caves.py): scores live in the world's scoreboard, so a restart repeats nothing",
             "scoreboard objectives add %s dummy" % obj]
    tick = ["# every %d ticks: each gate's driver, only while a player is within %d of its chamber" % (spec["gate"]["period_ticks"], spec["gate"]["reach"])]
    fns = {}
    for e in plan:
        cave, gm = e["cave"], e["geometry"]
        fns[build_name(cave)] = build_lines(spec, e)
        if (cave.get("gate") or {}).get("kind") == "partition":
            cx, cy, cz = gm["centre"]
            load_.append("execute unless score #%s_open %s matches -2147483648.. run scoreboard players set #%s_open %s 0" % (cave["id"], obj, cave["id"], obj))
            tick.append("execute positioned %d %d %d if entity @a[distance=..%d] run function %s:%s/gate/%s/near"
                        % (cx, cy, cz, spec["gate"]["reach"], NS, FOLDER, cave["id"]))
            fns.update(gate_files(spec, e))
        if cave["occupant"]["mode"] == "area_boss":
            bf = boss_files(spec, e)
            fns.update(bf)
            load_.append("function %s:%s/boss/%s/load" % (NS, FOLDER, cave["id"]))
    load_.append("schedule function %s/tick %dt replace" % (F, spec["gate"]["period_ticks"]))
    tick.append("schedule function %s/tick %dt replace" % (F, spec["gate"]["period_ticks"]))
    fns["load"], fns["tick"] = load_, tick
    for name, body in fns.items():
        bad = FL.check_lines(body, name)
        if bad:
            raise CaveError("function %s would be refused: %s" % (name, bad[:3]))
        files["data/%s/function/%s/%s.mcfunction" % (NS, FOLDER, name)] = "\n".join(body) + "\n"
    files["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s/load" % F]}, indent=2) + "\n"
    files.update(callbacks(spec, plan))
    return files


def write(spec, plan, out=None):
    out = Path(out or OUT)
    files = pack_files(spec, plan)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return {Path(r).stem: t.count("\n") for r, t in files.items() if r.endswith(".mcfunction")}


def build_functions(spec=None):
    """The build function names step R9CK runs, in order, from the committed data (not from a built pack)."""
    spec = spec or load()
    return ["%s/%s" % (F, build_name(c)) for c in spec["caves"]]


def forceload_box(gm):
    b = gm["bounds"]
    return (b[0] - 2, b[2] - 2, b[3] + 2, b[5] + 2)


def placement_steps(spec=None, g=None):
    """For tools/reapply.py, step R9CK BEFORE R9E: per cave hold its box, build it, release (the Scar Tarn's shape). The boxes come
    from the geometry on the heightmap alone (no clearance inputs), so listing the steps needs no derived/ or build/."""
    spec = spec or load()
    g = g or G.Ground()
    out = []
    for cave in spec["caves"]:
        if not cave.get("mouth"):
            raise SystemExit("%s has no mouth: python tools/caves.py author" % cave["id"])
        hold = "%d %d %d %d" % forceload_box(geometry(spec, cave, g))
        out += [("cmd", "forceload add " + hold), ("wait", 4), ("fn", "%s/%s" % (F, build_name(cave))), ("cmd", "forceload remove " + hold)]
    return out


# ------------------------------------------------------------------ the records in other files

def habitat_positions(entry):
    gm = entry["geometry"]
    out = {}
    for h in entry["cave"].get("habitat") or []:
        c = gm["centre"] if h["part"] == "chamber" else gm["ante_centre"]
        out[h["id"]] = (c[0], c[1], c[2])
    return out


def habitat_records(spec, plan):
    """[block record] for data/habitat_blocks.json."""
    d = spec["habitat_defaults"]
    out = []
    for e in plan:
        cave = e["cave"]
        pos = habitat_positions(e)
        ch = cave["chamber"]
        for h in cave.get("habitat") or []:
            x, y, z = pos[h["id"]]
            rng = block_range(cave, h["part"])
            out.append({
                "id": h["id"], "place": "%s (%s, %s) in data/caves.json: the %s's floor cell" % (cave["name"], cave["id"], cave["kind"], h["part"]),
                "pool": "cobblers:%s" % pool_of(h), "style": "activated", "replace_spawns": False,
                "position": {"x": x, "y": y, "z": z}, "mimic": cave["palette"]["floor"],
                "activated": {"spawn_range": rng, "chance": d["chance"], "trigger": d["trigger"], "cancel_range": d["cancel_range"],
                              "max_spawns": d["max_spawns"], "max_spawns_per_activation": d["max_spawns_per_activation"]},
                "status": d["status"], "generated_by": GENERATED,
                "why": "The %s's occupants (tools/caves.py; docs/mechanics/LEGENDARY_HOMES.md section 4): one activated block in the floor, "
                       "spawn_range %d (the part's reach), cancel_range -1 so nothing is cancelled, up to %d alive and %d refilled at a time. "
                       "Its position is the floor cell at the part's centre; it is written after the cave's build (R9CK before R9E). "
                       "Whether an activated block in a sealed room fills only that room is unmeasured (HB-1)."
                       % (h["part"], rng, d["max_spawns"], d["max_spawns_per_activation"])})
    return out


def pool_records(spec, plan):
    """([habitat pool record], [flat entry]) for data/spawns.json, with `band` levels resolved from the mouth's sub-region."""
    habs, ents = [], []
    for e in plan:
        cave, gm = e["cave"], e["geometry"]
        sub, bmin, bmax, tier = band_of(gm["centre"][0], gm["centre"][2])
        if sub is None:
            raise CaveError("%s: the chamber is in no sub-region with a level band" % cave["id"])
        for h in cave.get("habitat") or []:
            p = h["pool"]
            pid = p["id"]
            lv = [level_range(x, (bmin, bmax)) for x in p["entries"]]
            lo, hi = min(a for a, _b in lv), max(b for _a, b in lv)
            rec_entries, flat = [], []
            for x, (a, b) in zip(p["entries"], lv):
                lvl = "%d-%d" % (a, b) if a != b else "%d" % a
                sid = x["species"].lower().replace(" ", "")
                rec_entries.append({"species": x["species"], "pokemon": sid, "family": sid, "family_priority": x["family_priority"],
                                    "ambient": True, "eligibility_reason": x["reason"], "level": lvl, "bucket": x["bucket"],
                                    "weight": x["weight"], "conditions": {}})
                flat.append({"id": "habitat.%s.%s" % (pid, sid), "species": sid, "bucket": x["bucket"], "level": lvl, "weight": x["weight"],
                             "ambient": True, "scope": pid, "mechanism": "habitat_block", "conditions": {},
                             "eligibility_reason": x["reason"], "spawnable_position": "grounded"})
            pos = habitat_positions(e)[h["id"]]
            habs.append({
                "id": pid, "display_name": p["display_name"],
                "intended_location": "%s (data/caves.json %s, %s) at x%d z%d: one activated Habitat Block, %s in data/habitat_blocks.json, in the %s's floor"
                                     % (cave["name"], cave["id"], cave["kind"], pos[0], pos[2], h["id"], h["part"]),
                "mechanism": "habitat_block", "replace_spawns": False, "level_band": {"minimum": lo, "maximum": hi},
                "level_band_why": "entries marked `band` take the band of %s (%d-%d, tier %s), the sub-region the cave's chamber is in "
                                  "(data/spawns.json subregions); an explicit range is set by the cave's own gate (%s)"
                                  % (sub, bmin, bmax, tier, ", ".join(((cave.get("gate") or {}).get("flags")) or ["none"])),
                "why": p["why"], "entries": rec_entries,
                "placement_status": "authored: data/habitat_blocks.json %s, status planned (tools/caves.py)" % h["id"]})
            ents += flat
    return habs, ents


def probe_records(spec, plan):
    """{'caves': [probe]} in data/world_probes.json's shape (tools/presence_audit.py extra)."""
    rows = []
    for e in plan:
        cave, gm = e["cave"], e["geometry"]
        cid = cave["id"]
        cells = gm["cells"]
        front = gm["front"]

        def blk(what, c, state):
            rows.append({"what": "%s: %s" % (cid, what), "block": [c[0], c[1], c[2], state], "expect": True})
        x, y, z = gm["stand"]
        blk("air at the standing block outside the mouth", (x, y, z), AIR)
        blk("air in the middle of the chamber", (gm["centre"][0], gm["yh"] + 2, gm["centre"][2]), AIR)
        blk("the chamber's floor under the habitat block's neighbour", (gm["centre"][0] + 1, gm["yh"], gm["centre"][2]), cave["palette"]["floor"])
        blk("the shell over the chamber's roof", (gm["centre"][0], gm["yh"] + cave["chamber"]["h"] + 1, gm["centre"][2]), cave["palette"]["shell"])
        beam = next(c for c, r in sorted(cells.items()) if r == "beam")
        blk("the mouth's timber beam", beam, block_of(cave, "beam", front))
        if gm.get("door_box"):
            d = gm["door_box"]
            blk("the door's barrier (closed)", (d[0], d[1], d[2]), BARRIER)
        for hid, pos in habitat_positions(e).items():
            blk("the Habitat Block %s" % hid, pos, "cobblemon:habitat_block")
        if cave["occupant"]["mode"] == "area_boss":
            o = cave["occupant"]
            rows.append({"what": "%s: the boss (one tagged %s once a champion has come near; absent while the clock runs)" % (cid, o["tag"]),
                         "hold": [gm["centre"][0], gm["centre"][1] + 1, gm["centre"][2]],
                         "entity": "@e[type=cobblemon:pokemon,tag=%s]" % o["tag"], "count_max": 1})
    return {"caves": rows}


def record_problems(spec, plan):
    """The derived records in other files must equal what the spec and the geometry imply (drift is a fault)."""
    out = []
    blocks = {b["id"]: b for b in load(HABITATS)["blocks"]}
    for want in habitat_records(spec, plan):
        got = blocks.get(want["id"])
        if got is None:
            out.append("data/habitat_blocks.json lacks %s (python tools/caves.py author)" % want["id"])
        elif got != want:
            out.append("data/habitat_blocks.json %s differs from the geometry (python tools/caves.py author --resync)" % want["id"])
    sp = load(SPAWNS)
    habs = {h["id"]: h for h in sp["habitats"]}
    flat = {e["id"]: e for e in sp["entries"]}
    wh, we = pool_records(spec, plan)
    for h in wh:
        if habs.get(h["id"]) != h:
            out.append("data/spawns.json habitats %s is missing or differs (python tools/caves.py author --resync)" % h["id"])
    for e in we:
        if flat.get(e["id"]) != e:
            out.append("data/spawns.json entries %s is missing or differs" % e["id"])
    probes = load(PROBES)["places"].get("caves")
    if probes != probe_records(spec, plan)["caves"]:
        out.append("data/world_probes.json places.caves is missing or differs (python tools/caves.py author --resync)")
    return out


def pack_problems(spec, plan):
    """Static rules: every placed block that is a spawn condition must be allowed by a policy entry scoped to the caves."""
    out = []
    spawn = set(load(ROOT / "data" / "spawn_blocks.json")["blocks"])
    policy = load(ROOT / "data" / "spawn_block_policy.json")
    allowed = {b for w in policy["whitelist"] if POLICY_SCOPE in (w.get("scope") or "") for b in w["blocks"]}
    placed = set()
    for e in plan:
        for c, r in e["geometry"]["cells"].items():
            placed.add(base(block_of(e["cave"], r, e["geometry"]["front"])))
    for b in sorted((placed & spawn) - allowed):
        out.append("places %s, a spawn condition (data/spawn_blocks.json), and no data/spawn_block_policy.json entry scoped to %s allows it"
                   % (b, POLICY_SCOPE))
    return out


def plan_json(spec, plan, counts):
    caves = {}
    for e in plan:
        gm, cave = e["geometry"], e["cave"]
        lay = gm["layout"]
        caves[cave["id"]] = {"kind": cave["kind"], "anchor": gm["anchor"], "front": gm["front"], "mouth_floor": gm["y0"], "hall_floor": gm["yh"],
                             "stand": gm["stand"], "centre": gm["centre"], "bounds": gm["bounds"], "cutting_rows": gm["cutting_rows"],
                             "total_rows": lay["total"], "dug": gm["dug"], "cells": len(gm["cells"]),
                             "ante_zone": gm.get("ante_zone"), "door_box": gm.get("door_box"), "inside_zone": gm.get("inside_zone"),
                             "chamber_zone": gm["chamber_zone"], "habitat": {k: list(v) for k, v in habitat_positions(e).items()},
                             "occupant": {"mode": cave["occupant"]["mode"], "species": cave["occupant"]["species"]}}
    return {"schema": "cobblers.derived.caves/1", "build_functions": build_functions(spec), "commands": counts, "caves": caves}


# ------------------------------------------------------------------ authoring

def dump_json(path, doc):
    Path(path).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def sync_records(spec, plan):
    """Write the derived records: Habitat Blocks, pools, entries and probes. Replaces ours (by id), keeps every other record."""
    hb = load(HABITATS)
    ours = {b["id"] for c in spec["caves"] for h in c.get("habitat") or [] for b in [h]}
    hb["blocks"] = [b for b in hb["blocks"] if b["id"] not in ours] + habitat_records(spec, plan)
    dump_json(HABITATS, hb)
    sp = load(SPAWNS)
    habs, ents = pool_records(spec, plan)
    pids = {h["id"] for h in habs} | {pool_of(h) for c in spec["caves"] for h in c.get("habitat") or []}
    sp["habitats"] = [h for h in sp["habitats"] if h["id"] not in pids] + habs
    sp["entries"] = [e for e in sp["entries"] if e.get("scope") not in pids] + ents
    dump_json(SPAWNS, sp)
    pr = load(PROBES)
    pr["places"]["caves"] = probe_records(spec, plan)["caves"]
    dump_json(PROBES, pr)


def author(spec, only=None, source_root=None, inputs_root=None, resite=False, resync=False):
    """Site every cave with no mouth yet (or every cave, with --resite): the best candidate search() returns. Writes
    data/caves.json and the derived records; a cave that cannot be sited stops the run and nothing is written."""
    g0 = G.Ground(source_root)
    for cave in spec["caves"]:
        if only and cave["id"] != only:
            continue
        if cave.get("mouth") and not resite:
            continue
        clear = clearance(spec, cave, g0, inputs_root, need_packs=True)
        best = search(spec, cave, g0, clear, 1)
        if not best:
            raise SystemExit("%s: no mouth passes every rule; nothing written" % cave["id"])
        cave["mouth"] = {"anchor": best[0][1], "front": best[0][2], "frame": "timber",
                         "sited_by": "tools/caves.py author: the best of search() (distance from host_anchor + 0.3 x the cells dug / 10) over "
                                     "the canonical heightmap and the keep_clear rules"}
        print("%s: mouth %s front %s floor y%d (score %s, %d dug)" % (cave["id"], best[0][1], best[0][2], best[0][3], best[0][0], best[0][4]))
    plan, probs, _n = model(spec, source_root, inputs_root, need_packs=True)
    if probs:
        for p in probs:
            print("PROBLEM:", p)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    for e in plan:
        gm = e["geometry"]
        sub, bmin, bmax, tier = band_of(gm["centre"][0], gm["centre"][2])
        e["cave"]["site"] = {"mouth_floor": gm["y0"], "hall_floor": gm["yh"], "chamber_centre": gm["centre"], "subregion": sub,
                             "subregion_band": [bmin, bmax], "tier": tier}
    dump_json(SPEC, spec)
    sync_records(spec, plan)
    print("wrote data/caves.json and the derived records for %d caves" % len(plan))
    return 0


def nearest(spec, plan, g0, radius):
    """For `report`: what lies within radius of each cave's centre, by file (x/z points other files author), nearest first."""
    import southern_residents as SR
    pts = SR.authored_points(authored_doc(spec), own_file=SPEC)
    out = {}
    for e in plan:
        cx, _cy, cz = e["geometry"]["centre"]
        ax, az = e["geometry"]["anchor"]
        near = {}
        for x, z, f in pts:
            d = min(math.hypot(x - cx, z - cz), math.hypot(x - ax, z - az))
            if d <= radius:
                near.setdefault(f, d)
                near[f] = min(near[f], d)
        out[e["cave"]["id"]] = sorted(near.items(), key=lambda kv: kv[1])
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("site", "author", "report", "build"))
    p.add_argument("cave", nargs="?")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--resite", action="store_true")
    p.add_argument("--resync", action="store_true")
    p.add_argument("--source-root")
    p.add_argument("--inputs-root", help="a full checkout holding build/datapacks, build/paint, derived/routes and derived/water_shape "
                                         "(default: this checkout)")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    spec = load()
    if a.mode == "author":
        return author(spec, a.cave, a.source_root, a.inputs_root, a.resite, a.resync)
    if a.mode == "site":
        cave = next((c for c in spec["caves"] if c["id"] == a.cave), None)
        if cave is None:
            raise SystemExit("no cave %r" % a.cave)
        g0 = G.Ground(a.source_root)
        clear = clearance(spec, cave, g0, a.inputs_root, need_packs=True)
        for o in search(spec, cave, g0, clear, a.top):
            print(json.dumps(o))
        return 0
    try:
        plan, probs, notes = model(spec, a.source_root, a.inputs_root)
    except CaveError as exc:
        raise SystemExit("FAILED: %s; nothing written" % exc)
    if plan:
        probs += pack_problems(spec, plan)
        probs += record_problems(spec, plan)
    for e in plan:
        gm = e["geometry"]
        print("  %-18s %s mouth %s front %-5s floor y%d hall y%d  %d rows, %d cells, %d dug, %d cutting rows  %s" % (
            e["cave"]["id"], e["cave"]["kind"], gm["anchor"], gm["front"], gm["y0"], gm["yh"], gm["layout"]["total"], len(gm["cells"]),
            gm["dug"], gm["cutting_rows"], e["cave"]["occupant"]["mode"]))
    for n in notes:
        print("  NOTE:", n)
    if probs:
        for pr in probs:
            print("PROBLEM:", pr)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    if a.mode == "report":
        g0 = G.Ground(a.source_root)
        near = nearest(spec, plan, g0, spec["keep_clear"]["report_radius"])
        for cid, lst in near.items():
            print("  within %d of %s: %s" % (spec["keep_clear"]["report_radius"], cid, ", ".join("%s %.0f" % kv for kv in lst) or "nothing authored"))
        print("report: %d caves, 0 problems" % len(plan))
        return 0
    counts = write(spec, plan)
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(plan_json(spec, plan, counts), indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("wrote %s: %d caves; plan %s" % (OUT.relative_to(ROOT), len(plan), PLAN.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
