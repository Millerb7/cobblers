#!/usr/bin/env python
"""The Long Count of data/long_count.json: a woman, an old Grotle and a line of trees pointed at the world tree, in C3.

The owner's world sweep (docs/world-building/WORLD_SWEEP_2026-10-09.md, gap 4): C3 is 100% land beside Route 3, empty,
and nothing anywhere is gated at gym 2. This is the place that fills it: Perrin Hale's camp on Foothill Woods' east
side, a 42-block lantern pole that can be seen over the canopy, the Grotle that has walked toward the world tree for
thirteen years leaving a tree where it rested each spring (a line of thirteen, small to tall, with Perrin's year stakes),
and a tin at the first one. The design note is docs/world-building/LONG_COUNT.md.

Nothing here is new machinery. The block primitives (a structure on a levelled floor, surface work, blocks on their own
column's ground, a ring, a clearing) are tools/southern_residents.py's and tools/northern_residents.py's own functions,
CALLED, not copied, and through them tools/resident_encounters.py's keeper. This tool adds two primitives:

  ride          a lane through the wood: logs, leaves and plants off every dry column within half_width of a segment,
                from the lowest ground on the lane + 1 to the highest + up (never a block of ground)
  procession    the line itself: one stake (a fence post with a year sign, in the Grotle's own wake), one young tree
                (oak log trunk, azalea leaves: an oak leaf is a spawn-condition block, data/spawn_blocks.json) and one
                cold camp for each year, spaced along a compass bearing from the Grotle's present rest, the tallest
                tree at the oldest end. The tree for the year of the Grotle's rest is age 0, the stake of year 0 is the
                last one; sign lines may carry {years}, {line_paces}, {stakes} and {years_to_tree}, which are COMPUTED
                here from the geometry, so a sign can never say a number the layout does not give

Every Y is the canonical heightmap's rounded ground (tools/ground.py), never a world's. The siting rules fail the build
(data/long_count.json rules): every written column and every NPC, anchor and cache inside cell C3; at least
rules.authored_clearance from every x/z authored in any OTHER data/*.json (this place's own records skipped by id) and
from every route corridor box; outside every town footprint (+ the same clearance) and Rift zone box; the centre, NPC,
anchor and cache at least rules.path_clearance from a route path; the resident's leash clear of every activated
Habitat Block's spawn_range; its level within its sub-region's tier ceiling; no block a spawn condition names; and the
line must point at the world tree to within rules.tree_tolerance_degrees. These are the builder's guards, not an audit:
the independent audit is owed (data/long_count.json audit_checklist).

  python tools/long_count.py [--source-root R] [--out DIR]    write build/datapacks/cobblers_long_count
  python tools/long_count.py --report                          the site as measured, the checks, the steps
  python tools/long_count.py probes [--write]                  presence probes into data/world_probes.json

The re-application (tools/reapply.py): placement_steps() is R9LC, BEFORE R9E with the other block passes (after R9FS);
entity_steps() is R18LC, after R18FS: the Grotle (it has no presence gate) summoned and bound. Perrin is placed by R9F,
from the npc_grant record data/rewards.json long_count_thanks, as Hopgood is.
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
import northern_residents as NR  # noqa: E402
import southern_residents as SR  # noqa: E402

DATA = ROOT / "data" / "long_count.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_long_count"
SCHEMA = "cobblers.long-count/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
KINDS = NR.KINDS + ("ride", "procession")
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class CountError(SystemExit):
    pass


jload = SR.jload
base = SR.base


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise CountError("%s: schema must be %s" % (path, SCHEMA))
    if len(doc["residents"]) != 1:
        raise CountError("this file holds one place")
    for r in doc["residents"]:
        for p in r["pieces"]:
            if p["kind"] not in KINDS:
                raise CountError("%s: unknown piece kind %s" % (r["id"], p["kind"]))
        pk = r.get("pokemon")
        if pk and not (0 < pk["trigger"] < pk["leash"]):
            raise CountError("%s: the trigger must be inside the leash" % r["id"])
        caches = r.get("caches") or []
        if len(caches) != 1:
            raise CountError("%s: one cache (the tin at the first tree)" % r["id"])
        for c in caches:
            if not isinstance(c.get("items_hook"), dict):
                raise CountError("%s: the cache %s carries no items_hook" % (r["id"], c["reward"]))
    return doc


# ------------------------------------------------------------------ the geometry the signs and the checks share


def axis(p):
    """(ux, uz, vx, vz): the unit vector along a compass bearing (0 north, 90 east) and its right-hand perpendicular
    (which points south for an easterly bearing)."""
    b = math.radians(p["bearing"])
    ux, uz = math.sin(b), -math.cos(b)
    return ux, uz, -uz, ux


def procession_piece(r):
    ps = [p for p in r["pieces"] if p["kind"] == "procession"]
    if len(ps) != 1:
        raise CountError("%s: exactly one procession piece" % r["id"])
    return ps[0]


def facts(doc, r):
    """The numbers the signs state, computed from the layout and the world tree's recorded position, not typed.
    years_to_tree is the walk from the Grotle's rest to the trunk's near face at the data's pace, rounded up."""
    p = procession_piece(r)
    t = doc["tree"]
    ax, az = r["pokemon"]["at"]
    gx, gz = r["site"]["centre"][0] + ax, r["site"]["centre"][1] + az
    d_centre = math.hypot(t["centre"][0] - gx, t["centre"][1] - gz)
    to_face = d_centre - t["trunk_half_width"]
    return {"years": p["years_top"], "line_paces": p["spacing"] * (p["count"] - 1), "stakes": p["count"],
            "paces_per_year": p["spacing"], "years_to_tree": int(math.ceil(to_face / p["spacing"])),
            "grotle_to_trunk_face": round(to_face, 1),
            "bearing_to_tree": round(math.degrees(math.atan2(t["centre"][0] - gx, -(t["centre"][1] - gz))) % 360, 1)}


class Fmt(dict):
    def __missing__(self, k):
        raise CountError("a sign line names {%s}, which the generator does not compute" % k)


def fill_lines(lines, f):
    return [str(l).format_map(Fmt(f)) for l in lines]


# ------------------------------------------------------------------ the site plan


def piece_ride(s, p):
    """A lane through the wood: every dry column within half_width of the segment, cleared from the lane's lowest
    ground + 1 to its highest + up. Logs, leaves and replaceable plants only (the clears' tags), never ground."""
    cols = [(s.cx + dx, s.cz + dz) for dx, dz in SR._segment_cols(p["from"], p["to"], p["half_width"])]
    wet = [c for c in cols if s.wet(*c)]
    if wet:
        raise CountError("%s %s: the lane has wet columns, e.g. %s" % (s.r["id"], p["name"], wet[:3]))
    gs = [s.g(x, z) for x, z in cols]
    y0, y1 = min(gs) + 1, max(gs) + int(p["up"])
    for x, z in cols:
        s.clears.append((x, y0, z, x, y1, z))
    s.floors[p["name"]] = {"columns": len(cols), "y": [y0, y1]}


def tree_cells(h, radius, bx, by, bz):
    """(trunk [(x, y, z)], leaves [(x, y, z)]): h logs from by+1, a ball of leaves of `radius` round the top log."""
    trunk = [(bx, by + 1 + j, bz) for j in range(h)]
    tx, ty, tz = trunk[-1]
    ts = set(trunk)
    leaves = []
    for dx in range(-radius, radius + 1):
        for dy in range(-1, radius + 1):
            for dz in range(-radius, radius + 1):
                if math.sqrt(dx * dx + dy * dy + dz * dz) <= radius + 0.3 and (tx + dx, ty + dy, tz + dz) not in ts:
                    leaves.append((tx + dx, ty + dy, tz + dz))
    return trunk, leaves


def piece_procession(s, p):
    ux, uz, vx, vz = axis(p)
    fx, fz = p["from"]
    heights, notes, count = p["heights"], p.get("notes") or {}, int(p["count"])
    if len(heights) != count:
        raise CountError("%s: heights must hold one height per stake (%d)" % (s.r["id"], count))
    f = facts(s.doc, s.r)
    out = []
    for i in range(count):
        year = int(p["years_top"]) - i
        d = p["spacing"] * i

        def at(side):
            return (s.cx + int(round(fx + ux * d + vx * side)), s.cz + int(round(fz + uz * d + vz * side)))
        # the first stake and tree stand wider of the axis: the Grotle sits ON the axis at distance 0 and its 3x3 of
        # standing room is cleared, so a fence post two blocks off would be inside its body
        tx, tz = at(p["first_tree_side"] if i == 0 and "first_tree_side" in p else p["tree_side"])
        sx, sz = at(p["first_stake_side"] if i == 0 and "first_stake_side" in p else p["stake_side"])
        cols_wet = [c for c in ((tx, tz), (sx, sz)) if s.wet(*c)]
        if cols_wet:
            raise CountError("%s: stake %d stands on water at %s" % (s.r["id"], year, cols_wet))
        h = int(heights[i])
        rad = 1 if h <= 3 else (2 if h <= 6 else 3)
        gy = s.g(tx, tz)
        trunk, leaves = tree_cells(h, rad, tx, gy, tz)
        for x, y, z in trunk:
            s.put(x, y, z, p["trunk"])
        for x, y, z in leaves:
            if s.wet(x, z):
                raise CountError("%s: the year-%d tree's leaves reach water at (%d, %d)" % (s.r["id"], year, x, z))
            s.put(x, y, z, p["leaves"])
        sg = s.g(sx, sz)
        s.put(sx, sg + 1, sz, p["stake"])
        lines = ["YEAR %d" % year] + fill_lines(notes.get(str(year)) or p["default_note"], f)
        s.put(sx, sg + 2, sz, {"sign": {"wood": p["sign_wood"], "rotation": int(p["sign_rotation"]), "lines": lines}}, hung=True)
        fire = None
        if i > 0 and p.get("old_camp"):
            ox, oz = at(p["fire_side"])
            if s.wet(ox, oz):
                raise CountError("%s: the year-%d old camp stands on water" % (s.r["id"], year))
            og = s.g(ox, oz)
            s.put(ox, og + 1, oz, p["old_camp"])
            fire = (ox, og + 1, oz)
        out.append({"year": year, "age": i, "d": d, "tree": (tx, gy, tz), "height": h, "radius": rad,
                    "stake": (sx, sg + 1, sz), "sign": (sx, sg + 2, sz), "camp": fire, "lines": lines})
    s.floors[p["name"]] = out


def _subst(o, f):
    """The record with every sign's lines formatted from the computed facts (a deep copy; the record is untouched)."""
    if isinstance(o, dict):
        if "sign" in o and isinstance(o["sign"], dict) and "lines" in o["sign"]:
            sg = dict(o["sign"])
            sg["lines"] = fill_lines(sg["lines"], f)
            return {"sign": sg}
        return {k: _subst(v, f) for k, v in o.items()}
    if isinstance(o, list):
        return [_subst(v, f) for v in o]
    return o


def plan(doc, r, g, wet):
    r = _subst(r, facts(doc, r))
    s = SR.Site(doc, r, g, wet)
    for i, p in enumerate(r["pieces"]):
        k = p["kind"]
        if k == "clearing":
            NR.piece_clearing(s, p)
        elif k == "ride":
            piece_ride(s, p)
        elif k == "procession":
            piece_procession(s, p)
        elif k == "structure":
            SR.piece_structure(s, p)
        elif k == "surface":
            SR.piece_surface(s, p, i + 1)
        elif k == "ground_blocks":
            SR.piece_ground_blocks(s, p)
        elif k == "ring":
            SR.piece_ring(s, p)
        elif k == "posts":
            SR.piece_posts(s, p)
    return s


def sites(doc, g, wet=None):
    import resident_encounters as RE
    wet = wet or RE.Wet(g, [tuple(r["site"]["centre"]) for r in doc["residents"]])
    out = []
    for r in doc["residents"]:
        s = plan(doc, r, g, wet)
        extra = []
        if r.get("npc"):
            xyz = SR.spot(s, r["npc"]["at"])
            if r["npc"]["at"][2] == "ground":
                SR.stand_clears(s, xyz)
            SR.check_standing(s, xyz, r["npc"]["name"])
            extra.append(xyz)
        if r.get("pokemon"):
            a = SR.anchor(s, r)
            SR.stand_clears(s, a)
            SR.check_standing(s, a, r["pokemon"]["name"])
            extra.append(a)
        for c in r.get("caches") or []:
            extra.append(SR.spot(s, c["at"]))
        out.append((r, s, extra, SR.box_of(s, extra)))
    return out


# ------------------------------------------------------------------ the siting rules (the builder's guards)


def owned(doc):
    """A stub in the shape SR.owned_ids reads, naming every record this place owns in the shared files (the quest,
    the conversation, the NPC's reward AND the cache's), so the clearance scan skips them by id."""
    recs = []
    for r in doc["residents"]:
        recs.append({"records": dict(r.get("records") or {})})
        for c in r.get("caches") or []:
            recs.append({"records": {"reward": c["reward"]}})
    return {"residents": recs}


def authored_points(doc):
    """Every x/z another data file authors, except data/world_probes.json: that file holds this place's own probes (the
    plan's own blocks, written back by `probes --write`) and every other place's probes, which restate places their own
    data files already author, so skipping it loses no clearance and stops the place measuring itself."""
    pts = [p for p in SR.authored_points(owned(doc), own_file=DATA) if p[2] != "world_probes.json"]
    skip = superseded_samples(doc)
    return [p for p in pts if not (p[2] in skip and (float(p[0]), float(p[1])) in skip[p[2]])]


def superseded_samples(doc):
    """{file: {(x, z)}}: the nine points SR.authored_points() samples from a [x0, z0, x1, z1] box (corners, middle
    edges, centre) for each rules.superseded_points entry, which names a record a later decision replaced. The entry
    must name its file and the box, so only those nine points of that file are dropped and an exception cannot widen."""
    out = {}
    for e in (doc.get("rules") or {}).get("superseded_points") or []:
        x0, z0, x1, z1 = e["corners_of"]
        out.setdefault(e["file"], set()).update(
            (float(x), float(z)) for x in (x0, (x0 + x1) / 2.0, x1) for z in (z0, (z0 + z1) / 2.0, z1))
    return out


def cell_of(x, z):
    grid = jload("world.json")["grid"]
    s = grid["cell_size"]
    return grid["row_labels"][int(z - grid["origin_z"]) // s] + grid["column_labels"][int(x - grid["origin_x"]) // s]


def cell_box(cid):
    c = next(c for c in jload("cells.json")["cells"] if c["id"] == cid)
    b = c["bounds"]
    return b


def siting(doc, r, s, extra, pts):
    """Problems, as strings, for one planned site. `extra` are the NPC spot, the anchor and the cache spot (x, y, z)."""
    import numpy as np
    rules = doc["rules"]
    probs = []
    P = np.array([(a, b) for a, b, _f in pts], float)
    F = [f for _a, _b, f in pts]
    cols = set(s.cols) | {(e[0], e[2]) for e in extra}
    for c in s.clears:
        cols |= {(c[0], c[2]), (c[3], c[5])}
        if c[0] != c[3] or c[2] != c[5]:
            cols |= {(x, z) for x in range(c[0], c[3] + 1) for z in (c[2], c[5])}
            cols |= {(x, z) for z in range(c[2], c[5] + 1) for x in (c[0], c[3])}
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
    for t in jload("towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            probs.append("%s: within %d of town %s's footprint" % (r["id"], m, t["id"]))
    for k, zone in jload("rift_zones.json")["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                probs.append("%s: inside Rift zone %s" % (r["id"], k))
                break
    cb = cell_box(rules["cell"])
    out = sorted(c for c in cols if not (cb["min_x"] <= c[0] <= cb["max_x"] and cb["min_z"] <= c[1] <= cb["max_z"]))
    if out:
        probs.append("%s: %d written column(s) outside cell %s, e.g. %s" % (r["id"], len(out), rules["cell"], out[:3]))
    paths = np.array([p for pl in jload("route_paths.json")["paths"].values() for p in pl], float)
    cx, cz = r["site"]["centre"]
    dp = float(np.min(np.hypot(paths[:, 0] - cx, paths[:, 1] - cz)))
    if dp < rules["path_clearance"]:
        probs.append("%s: %.0f blocks from a route path (needs %d)" % (r["id"], dp, rules["path_clearance"]))
    for e in extra:
        de = float(np.min(np.hypot(paths[:, 0] - e[0], paths[:, 1] - e[2])))
        if de < rules["path_clearance"]:
            probs.append("%s: the NPC, anchor or cache %s is %.0f blocks from a route path (needs %d)"
                         % (r["id"], list(e), de, rules["path_clearance"]))
    pk = r.get("pokemon")
    if pk:
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
            if pk["level"] > ceiling:
                probs.append("%s: L%d over %s's tier-%s ceiling %d" % (r["id"], pk["level"], sub, tier, ceiling))
            if sub != r["subregion"]:
                probs.append("%s: the resident stands in %s, the record says %s" % (r["id"], sub, r["subregion"]))
    sub = SR._sub_of(cx, cz)[0]
    if sub != r["subregion"]:
        probs.append("%s: the centre is in %s, the record says %s" % (r["id"], sub, r["subregion"]))
    cell = cell_of(cx, cz)
    if cell != r["cell"]:
        probs.append("%s: the centre is in cell %s, the record says %s" % (r["id"], cell, r["cell"]))
    # the claim the whole place makes: the line points at the world tree
    f = facts(doc, r)
    p = procession_piece(r)
    off = abs((p["bearing"] + 180.0 - f["bearing_to_tree"] + 180.0) % 360.0 - 180.0)
    if off > rules["tree_tolerance_degrees"]:
        probs.append("%s: the line walks toward bearing %.1f but the world tree is at %.1f from the Grotle (%.1f off, "
                     "tolerance %.1f)" % (r["id"], (p["bearing"] + 180) % 360, f["bearing_to_tree"], off,
                                          rules["tree_tolerance_degrees"]))
    t = doc["tree"]
    if t["centre"] != [2016, 2280]:
        probs.append("%s: doc.tree.centre must be the world tree's [2016, 2280] (tools/world_tree.py CENTRE)" % r["id"])
    return probs, {"nearest_authored": best, "path": dp, "corridor": cbest, "facts": f}


def check_all(doc, built):
    pts = authored_points(doc)
    probs = []
    for r, s, extra, box in built:
        probs += siting(doc, r, s, extra, pts)[0]
    probs += SR.check_records(doc, built)
    spawn = set(jload("spawn_blocks.json")["blocks"])
    for r, s, extra, box in built:
        bad = sorted({base(v) for v in list(s.solid.values()) + list(s.hung.values())} & spawn)
        if bad:
            probs.append("%s: writes spawn-condition blocks %s (data/spawn_blocks.json)" % (r["id"], bad))
    rw = {x["id"]: x for x in jload("rewards.json")["rewards"]}
    for r, s, extra, box in built:
        for c in r.get("caches") or []:
            w = rw.get(c["reward"]) or {}
            if not w.get("contents"):
                probs.append("%s: data/rewards.json %s gives nothing" % (r["id"], c["reward"]))
    return probs


# ------------------------------------------------------------------ the pack


def files(doc, g, wet=None, check=True):
    import resident_encounters as RE
    built = sites(doc, g, wet)
    if check:
        probs = check_all(doc, built)
        if probs:
            raise CountError("long_count: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = doc["build"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    fn = {}
    sh = SR.shim(doc)
    load_ = ["# the Long Count's keeper state (tools/long_count.py, on tools/resident_encounters.py's keeper).",
             "# A clock that has never been set starts READY (respawn ticks already elapsed), so a fresh world fills at once",
             "scoreboard objectives add %s dummy" % obj,
             "scoreboard players set #resp %s %d" % (obj, int(b["respawn_ticks"])),
             "execute store result score #ready %s run time query gametime" % obj,
             "scoreboard players operation #ready %s -= #resp %s" % (obj, obj)]
    keeper = ["execute store result score #now %s run time query gametime" % obj]
    for r, s, extra, box in built:
        lines = SR.build_lines(doc, r, s, box)
        lines[0] = "# Generated by tools/long_count.py from data/long_count.json: %s" % r["name"]
        lines[1] = lines[1].replace("R9SR", b["steps"]["blocks"])
        bad = function_limits.check_lines(lines, "%s/build" % r["id"])
        if bad:
            raise CountError("%s/build: %d command(s) the server would refuse: %s" % (r["id"], len(bad), bad[:3]))
        fn["%s/build" % r["id"]] = lines
        if r.get("pokemon"):
            e = SR.resident_record(r)
            a = SR.anchor(s, r)
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
                                              "Cobblers: the Long Count (tools/long_count.py)"}}, indent=2) + "\n"
    return out, built


# ------------------------------------------------------------------ the re-application


def _built(doc=None, g=None):
    import ground as G
    doc = doc or load()
    g = g or G.load()
    return doc, g, sites(doc, g)


def placement_steps(doc=None, g=None):
    """R9LC, BEFORE R9E: per site, hold its box, build, release (R9FS's shape)."""
    doc, g, built = _built(doc, g)
    b = doc["build"]
    steps = []
    for r, s, extra, box in built:
        hold = "%d %d %d %d" % tuple(box)
        steps += [("cmd", "forceload add " + hold), ("wait", 3),
                  ("fn", "%s:%s/%s/build" % (b["namespace"], b["folder"], r["id"])), ("cmd", "forceload remove " + hold)]
    return steps


def entity_steps(doc=None, g=None):
    """R18LC, after R18FS: the Grotle (no presence gate) summoned over RCON, guarded on tag AND species (THE SUMMON
    GUARD), and bound, inside a forceload of the site's box. Perrin is not placed here: R9F seats her from the
    npc_grant record data/rewards.json long_count_thanks."""
    import resident_encounters as RE
    doc, g, built = _built(doc, g)
    b = doc["build"]
    sh = SR.shim(doc)
    steps = []
    for r, s, extra, box in built:
        if not r.get("pokemon") or r["pokemon"].get("appears_after"):
            continue
        e = SR.resident_record(r)
        a = SR.anchor(s, r)
        hold = "%d %d %d %d" % tuple(box)
        steps += [("cmd", "forceload add " + hold), ("wait", 3), ("cmd", RE.summon_command(sh, e, a)), ("wait", 1),
                  ("fn", "%s:%s/%s/bind_new" % (b["namespace"], b["folder"], e["id"])), ("cmd", "forceload remove " + hold)]
    return steps


# ------------------------------------------------------------------ the presence probes


def presence_probes(doc=None, g=None):
    """{place id: [probe]} in data/world_probes.json's shape (tools/presence_audit.py --only extra): blocks the build
    writes, taken from the plan (a probe is the plan's own block at the plan's own Y), and the cleared lane."""
    doc, g, built = _built(doc, g)
    rows = []
    for r, s, extra, box in built:
        p = procession_piece(r)
        st = s.floors[p["name"]]

        def blk(what, x, y, z, state):
            rows.append({"what": what, "block": [x, y, z, base(state) if "{" in state else state], "expect": True})
        hint = r["probe_hints"]["pole"]
        B = s.floors[hint["name"]]
        px, pz = s.cx + hint["trunk"][0], s.cz + hint["trunk"][1]
        blk("pole: the foot of the trunk", px, B + 1, pz, "minecraft:stripped_spruce_log[axis=y]")
        blk("pole: the trunk under the platform", px, B + 30, pz, "minecraft:stripped_spruce_log[axis=y]")
        blk("pole: the lantern at the top", px, B + 42, pz, "minecraft:lantern[hanging=false]")
        blk("pole: the ladder's foot", px - 1, B + 1, pz, "minecraft:ladder[facing=west]")
        blk("pole: the platform", px - 2, B + 35, pz + 1, "minecraft:spruce_planks")
        fire = r["probe_hints"]["fire"]
        fx, fz = s.cx + fire[0], s.cz + fire[1]
        gy = g(fx, fz)
        blk("the camp fire, lit on its hay", fx, gy + 1, fz, "minecraft:campfire[lit=true,signal_fire=true]")
        for k in (0, 6, 13):
            t = st[k]
            x, y, z = t["tree"]
            blk("the year-%d tree's trunk" % t["year"], x, y + 1, z, "minecraft:oak_log[axis=y]")
            # the top log is at y + height; the leaves' ball is centred on it, so one above it is always leaves
            blk("the year-%d tree's crown" % t["year"], x, y + t["height"] + 1, z, "minecraft:azalea_leaves")
            sx, sy, sz = t["stake"]
            blk("the year-%d stake" % t["year"], sx, sy, sz, "minecraft:oak_fence")
        cs = r["caches"][0]
        cx_, cy_, cz_ = SR.spot(s, cs["at"])
        blk("the tin's barrel at the first tree", cx_, cy_ - 1, cz_, "minecraft:barrel[facing=up]")
        # the lane is cleared: air a block above the ground, mid-lane, at three stakes (a clear that never ran leaves
        # the wood standing in it)
        ux, uz, vx, vz = axis(p)
        fx0, fz0 = p["from"]
        for k in (3, 8, 12):
            d = p["spacing"] * k + p["spacing"] // 2
            x, z = s.cx + int(round(fx0 + ux * d)), s.cz + int(round(fz0 + uz * d))
            rows.append({"what": "the lane is clear, between stakes %d and %d" % (st[k]["year"], st[k + 1]["year"]),
                         "block": [x, g(x, z) + 2, z, "minecraft:air"], "expect": True})
        e = SR.resident_record(r)
        a = SR.anchor(s, r)
        rows.append({"what": "the Grotle, once the summon has run", "hold": [a[0], a[1], a[2]],
                     "entity": "@e[type=cobblemon:pokemon,tag=%s.%s,distance=..%d]" % (doc["build"]["tag"], e["id"], 24),
                     "count": 1})
    return {doc["build"]["probe_key"]: rows}


# ------------------------------------------------------------------ CLI


def report(doc, g):
    built = sites(doc, g)
    pts = authored_points(doc)
    lines = []
    for r, s, extra, box in built:
        probs, m = siting(doc, r, s, extra, pts)
        na = m["nearest_authored"]
        sub = SR._sub_of(*r["site"]["centre"])
        lines.append("%-12s %-18s %s centre %s ground y%d sub %s tier %s; %d blocks, bbox %s; nearest authored %.0f "
                     "(our column %s to data/%s); corridor box %.0f; path %.0f"
                     % (r["id"], r["name"], r["cell"], r["site"]["centre"], g(*r["site"]["centre"]), sub[0], sub[1],
                        len(s.solid) + len(s.hung), box, na[0], tuple(int(v) for v in na[1]), na[2],
                        m["corridor"][0], m["path"]))
        lines.append("    facts %s" % m["facts"])
        for k, v in s.floors.items():
            if isinstance(v, list):
                lines.append("    %s: %d entries" % (k, len(v)))
            else:
                lines.append("    floor %s: %s" % (k, v))
        if r.get("npc"):
            lines.append("    NPC %s feet %s" % (r["npc"]["name"], list(SR.spot(s, r["npc"]["at"]))))
        if r.get("pokemon"):
            lines.append("    resident %s L%d anchor %s" % (r["pokemon"]["name"], r["pokemon"]["level"], list(SR.anchor(s, r))))
        for c in r.get("caches") or []:
            xyz = list(SR.spot(s, c["at"]))
            lines.append("    cache %s spot %s container %s" % (c["reward"], xyz, [xyz[0], xyz[1] - 1, xyz[2]]))
        for p in probs:
            lines.append("    PROBLEM %s" % p)
    for p in SR.check_records(doc, built):
        lines.append("PROBLEM %s" % p)
    lines.append("steps %s: %d actions; %s: %d actions" % (doc["build"]["steps"]["blocks"], len(placement_steps(doc, g)),
                                                        doc["build"]["steps"]["entities"], len(entity_steps(doc, g))))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "probes"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--write", action="store_true", help="probes: write them into data/world_probes.json")
    ap.add_argument("--report", action="store_true", help="print the site, the checks and the steps; write nothing")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.cmd == "probes":
        probes = presence_probes(doc, g)
        if a.write:
            wp = ROOT / "data" / "world_probes.json"
            d = json.loads(wp.read_text(encoding="utf-8"))
            d["places"].update(probes)
            wp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            print("wrote %d place(s) into data/world_probes.json" % len(probes))
        for k, v in probes.items():
            print(k, len(v), "probes")
        return 0
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
    print("long_count: %d files -> %s (%d site, build: %d commands)" % (len(written), out, len(built), n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
