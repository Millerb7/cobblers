#!/usr/bin/env python
"""The far south's offline audit: the emitted pack, the re-application steps, the three caches' rewards pack and the
tools/reapply.py wiring, against data/far_south.json, every other data file, the canonical heightmap and the Cobblemon
1.8 jar.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/far_south.py,
tools/southern_residents.py, tools/northern_residents.py or tools/resident_encounters.py to derive anything. It reads the
data, the heightmap (tools/ground.py, round(h)), the painted water (tools/water_mask.py) and the river corridors
(data/rivers.json), and derives what it expects with its own code. The block, standing-spot, replay, keeper and step
checks are tools/southern_residents_audit.py's and tools/northern_residents_audit.py's -- other AUDITS, written by agents
that built neither generator, whose derivation shares nothing with them -- and the species' climate is
tools/spawn_habitat_audit.py's (another auditor's jar reading and climate ladder). This file adds what the far south
adds: rows F-H, the keep-out box re-derived from the Rift arms it claims to cover, the Mega field and gulch polygons
(data/gulch_mine.json), every data/routes.json corridor box of any size as a filled rectangle, the path rule for every
centre, anchor AND cache, each centre's measured ground, the species' home climate, the caches' rewards pack (the
advancement's trigger box, the function paying exactly data/rewards.json's contents once), the gym 7 gate, and the
R9FS/R18FS wiring. The only things taken from the generator are its OUTPUTS: the pack and the steps it hands
tools/reapply.py. tests/test_far_south_audit.py mutates the GENERATOR's code and leaves the data alone.

  ys        every pokemon.anchor and each cache's data/rewards.json trigger and container, re-derived from the heightmap
            and the expected blocks; the record's bbox holds every expected block and spot; each site centre's ground
            is the y its `measured` text states, and dry
  writes    the build functions replayed (southern audit's check_writes: on plan, inside the bbox, blocks.ids, no spawn
            condition unless data/spawn_block_policy.json whitelists it for the far south, no chest or bed, nothing
            under the ground, nothing on a wet column, standing room cleared)
  siting    every written or cleared column and every spot: in rows F-H (data/world.json grid: row F's first z to the
            grid's end), at least rules.authored_clearance from every x/z another data file authors (our own three cache
            rewards excepted by id) and from every data/routes.json min/max box as a filled rectangle; outside the
            keep-out box, every town footprint + clearance, every Rift zone box, and the Mega field and gulch polygons by
            at least the clearance; the centre, every anchor and every cache at least
            data/encounter_design.json rules.hearts.clear_of_path_blocks from every route path; the record's cell and
            sub-region are where the centre is
  keep-out  rules.keep_out_box holds the two southern Rift arms' bounds (data/regions.json) widened by 300, as its why
            says; it holds the Mega field polygon and data/southern_residents.json's Mega farm keep-out
  residents level within the anchor's sub-region tier ceiling (rules.hearts.next_cap); leash clear of every activated
            Habitat Block's spawn_range; trigger < leash; catch window from data/trainers.json gym_ace_levels alone;
            gate and appears_after both GATE (the design: tier 8, after gym 7) and a data/progression.json flag; the
            species is in the jar and native (jar natives, tools/spawn_habitat_audit.py's ladder) within one climate
            step of its sub-region's paint
  keeper    the southern audit's keeper checks (anchor, leash, trigger, settle, yaw, level, the presence gate, no kill
            reaching a guardian, no item reward), and the objective is this pack's alone
  caches    each cache's record is a data/rewards.json cache with non-empty contents, every item in the jar; the barrel
            it names is written at container.at; the spot has two free cells in the plan and in the written world; the
            rewards pack's advancement fires on exactly the trigger box in the overworld and runs exactly
            cobblers:reward/<id>, whose gives are exactly the contents (nothing more, nothing twice), and nothing in the
            two packs or tools/ revokes it (so once per player)
  steps     each build inside a forceload of its bbox, once; a gated resident never summoned by a step; every `fn` step
            names a function the pack has; every function is reached
  wiring    tools/reapply.py: far_south and far_south_audit are prepare jobs, in that order; R9FS is
            far_south.placement_steps() after R9NR and before R9E; R18FS is far_south.entity_steps() after R18NR; the
            pack is in SERVER_PACKS and WORLD_LOCAL

NOT checked, and it needs a running server: that the blocks land; that the keeper spawns, holds and wakes the three
Pokemon and only for a gym7_cleared player; that the advancements fire and pay once; that the signs read; that the
level cap refuses the catch before gym 8 (relayed: data/far_south.json level_why); trees and structures a world already
holds at the sites (the heightmap is bare ground). Without a Cobblemon 1.8 jar (--jar, or tools/battle_sim.find_jar())
the species, habitat and item checks are NOT run, and the final line says so.

  python tools/far_south_audit.py [--pack DIR] [--rewards-pack DIR] [--jar JAR] [--source-root R] [-v]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import northern_residents_audit as NA  # noqa: E402  (an audit, not a generator)
import southern_residents_audit as SA  # noqa: E402  (an audit, not a generator)

DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_far_south"
REWARDS_PACK = ROOT / "build" / "datapacks" / "cobblers_rewards"
RECORD = "far_south.json"
SCHEMA = "cobblers.far-south/1"
GENERATOR = "far_south"
# The design, read by this audit from the brief and each record's story_rule ("Tier 8, gated after gym 7"): every
# resident appears after, and is catchable after, gym 7. Not a scan of the record: a resident moved to another gate fails.
GATE = "gym7_cleared"
# Where the two steps sit in tools/reapply.py: (after, before)
STEP_ORDER = {"blocks": ("placement_steps", "R9NR", "R9E"), "entities": ("entity_steps", "R18NR", None)}
# The Rift arms the keep-out box says it is built from, and by how much (data/far_south.json rules.keep_out_box.why)
KEEP_OUT_ARMS = ("rift_south_west_arm", "rift_south_east_arm")
KEEP_OUT_MARGIN = 300

# Defects this audit found in the committed build, reported to the builder and NOT fixed here (the data is not this
# audit's). Each is printed as KNOWN on every run and does not fail it; a KNOWN that no longer fires is STALE and does
# fail, so the list cannot outlive its defect (tools/spawn_habitat_audit.py's convention). (check, text, ruling)
KNOWN = [
    ("residents", "greymane: L57 is above the cap 55 a player holds just after gym7_cleared",
     "2026-10-04: catch_rule catchable_after_gate, gate gym7_cleared and intended_stage post_gym_7, but L57 is over "
     "the cap after gym 7 (data/trainers.json gym_ace_levels[7] = 55), so the level cap refuses the catch until gym 8. "
     "The record's level_why says that is the intent; then its gate and intended_stage say gym 7 where the catch is "
     "gym 8 (Ash, the southern gym-7 resident, is L53, inside 51..55). Builder or owner: the level or the gate"),
    ("residents", "fifth_chimney: L56 is above the cap 55 a player holds just after gym7_cleared",
     "2026-10-04: as greymane (L56 against the cap 55 after gym 7)"),
    ("residents", "old_watcher: L58 is above the cap 55 a player holds just after gym7_cleared",
     "2026-10-04: as greymane (L58 against the cap 55 after gym 7)"),
]

jload = SA.jload
Report = SA.Report


def classify(errors, known=None):
    """(real, known_hits, stale): errors no KNOWN entry names, those it does, and KNOWN entries that fired nothing."""
    known = KNOWN if known is None else known
    real, hits = [], []
    for e in errors:
        (hits if any(e.startswith(c + ":") and t in e for c, t, _w in known) else real).append(e)
    stale = [k for k in known if not any(e.startswith(k[0] + ":") and k[1] in e for e in errors)]
    return real, hits, stale


# ------------------------------------------------------------------ geometry


def _in_poly(x, z, poly):
    inside, n = False, len(poly)
    for k in range(n):
        (xa, za), (xb, zb) = poly[k][:2], poly[(k + 1) % n][:2]
        if (za > z) != (zb > z) and x < xa + (z - za) * (xb - xa) / (zb - za):
            inside = not inside
    return inside


def _poly_distance(C, poly):
    """Distance from each column of C (n x 2) to the polygon's edges (0 never: a column inside is tested separately)."""
    import numpy as np
    P = np.array([p[:2] for p in poly], float)
    A, B = P, np.roll(P, -1, axis=0)
    best = np.full(len(C), np.inf)
    for k in range(0, len(C), 256):
        c = C[k:k + 256, None, :]
        ab = B - A
        L2 = np.maximum((ab ** 2).sum(1), 1e-9)
        t = np.clip(((c - A) * ab).sum(2) / L2, 0, 1)
        q = A + t[..., None] * ab
        best[k:k + 256] = np.min(np.hypot(c[..., 0] - q[..., 0], c[..., 1] - q[..., 1]), axis=1)
    return best


def _grid(data):
    return jload("world.json", data)["grid"]


def row_f_line(data):
    gr = _grid(data)
    return gr["origin_z"] + gr["row_labels"].index("F") * gr["cell_size"]


def grid_south_edge(data):
    gr = _grid(data)
    return gr["origin_z"] + len(gr["row_labels"]) * gr["cell_size"]


def keep_out_derived(data):
    """The two southern Rift arms' bounds (data/regions.json measured.bounds), unioned and widened by the margin."""
    subs = {s["id"]: s for s in jload("regions.json", data)["subregions"]}
    bs = [subs[a]["measured"]["bounds"] for a in KEEP_OUT_ARMS]
    m = KEEP_OUT_MARGIN
    return [min(b["min_x"] for b in bs) - m, min(b["min_z"] for b in bs) - m,
            max(b["max_x"] for b in bs) + m, max(b["max_z"] for b in bs) + m]


def keep_out_polygons(data):
    g = jload("gulch_mine.json", data)
    return [("the Mega field (data/gulch_mine.json mega_field)", g["mega_field"]["polygon"]),
            ("the gulch (data/gulch_mine.json zone)", g["zone"]["polygon"])]


def corridor_rects(data):
    """Every min/max box in data/routes.json, of any size, as a filled rectangle."""
    out = []

    def walk(o):
        if isinstance(o, dict):
            if all(isinstance(o.get(k), (int, float)) for k in ("min_x", "max_x", "min_z", "max_z")):
                out.append((o["min_x"], o["min_z"], o["max_x"], o["max_z"], o.get("id")))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(jload("routes.json", data).get("routes"))
    return out


# ------------------------------------------------------------------ the checks this record adds


def check_keep_out(doc, rep, data):
    box = doc["rules"]["keep_out_box"]["box"]
    want = keep_out_derived(data)
    if not (box[0] <= want[0] and box[1] <= want[1] and want[2] <= box[2] and want[3] <= box[3]):
        rep.err("keep-out", "rules.keep_out_box %s does not hold the Rift arms %s widened by %d, %s"
                % (box, list(KEEP_OUT_ARMS), KEEP_OUT_MARGIN, want))
    for name, poly in keep_out_polygons(data)[:1]:
        out = [p for p in poly if not (box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3])]
        if out:
            rep.err("keep-out", "%s has %d vertex(es) outside the keep-out box, e.g. %s" % (name, len(out), out[:2]))
    sr = jload("southern_residents.json", data)["rules"]["keep_out_box"]["box"]
    if not (box[0] <= sr[0] and box[1] <= sr[1] and sr[2] <= box[2] and sr[3] <= box[3]):
        rep.err("keep-out", "the keep-out box %s does not hold data/southern_residents.json's Mega farm keep-out %s" % (box, sr))


def check_measured(r, g, water, rep):
    """The record states its centre's ground ('y107 at the centre'); the heightmap must agree, and the centre be dry."""
    i = r["id"]
    cx, cz = r["site"]["centre"]
    m = re.search(r"\by(\d+) at the centre", r["site"].get("measured") or "")
    if not m:
        rep.err("ys", "%s: site.measured states no 'yN at the centre'" % i)
    elif int(m.group(1)) != g(cx, cz):
        rep.err("ys", "%s: site.measured says y%s at the centre, the heightmap gives y%d" % (i, m.group(1), g(cx, cz)))
    if water(cx, cz) is not None:
        rep.err("ys", "%s: the centre (%d, %d) is wet, water y%d" % (i, cx, cz, water(cx, cz)))


def check_siting(doc, r, cols, spots, A, rep, data):
    import numpy as np
    i, rules = r["id"], doc["rules"]
    m = rules["authored_clearance"]
    pts, rects = A
    C = np.array(sorted(cols), float)
    P = np.array([(a, b) for a, b, _f in pts], float)
    best = (1e18, None, None)
    for k in range(0, len(C), 128):
        blk = C[k:k + 128]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] < best[0]:
            best = (float(d[j]), tuple(int(v) for v in blk[j[0]]), pts[j[1]][2])
    for x0, z0, x1, z1, f in list(rects) + [(a, b, c, d, "routes.json corridor %s" % n) for a, b, c, d, n in corridor_rects(data)]:
        dx = np.maximum(np.maximum(x0 - C[:, 0], C[:, 0] - x1), 0)
        dz = np.maximum(np.maximum(z0 - C[:, 1], C[:, 1] - z1), 0)
        d = np.hypot(dx, dz)
        j = int(np.argmin(d))
        if d[j] < best[0]:
            best = (float(d[j]), tuple(int(v) for v in C[j]), f + " (box %s)" % [x0, z0, x1, z1])
    if best[0] < m:
        rep.err("siting", "%s: (%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                % (i, best[1][0], best[1][1], best[0], best[2], m))
    rep.note("%s: nearest authored x/z %.0f, our column %s, in data/%s" % (i, best[0], best[1], best[2]))
    for t in jload("towns.json", data)["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            rep.err("siting", "%s: within %d of town %s's footprint" % (i, m, t["id"]))
    for k, zone in jload("rift_zones.json", data)["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                rep.err("siting", "%s: inside Rift zone %s" % (i, k))
                break
    kx0, kz0, kx1, kz1 = doc["rules"]["keep_out_box"]["box"]
    if any(kx0 <= x <= kx1 and kz0 <= z <= kz1 for x, z in cols):
        rep.err("siting", "%s: writes inside the keep-out box %s" % (i, [kx0, kz0, kx1, kz1]))
    for name, poly in keep_out_polygons(data):
        if any(_in_poly(x, z, poly) for x, z in cols):
            rep.err("siting", "%s: writes inside %s" % (i, name))
            continue
        d = float(np.min(_poly_distance(C, poly)))
        if d < m:
            rep.err("siting", "%s: %.0f blocks from %s (needs %d)" % (i, d, name, m))
    line, edge = row_f_line(data), grid_south_edge(data)
    if rules.get("south_of_z") != line:
        rep.err("siting", "rules.south_of_z %s is not row F's first z %d (data/world.json grid)" % (rules.get("south_of_z"), line))
    off = [c for c in cols if not line <= c[1] < edge]
    if off:
        rep.err("siting", "%s: %d column(s) outside rows F-H (z %d..%d), e.g. %s" % (i, len(off), line, edge - 1, sorted(off)[:2]))
    clear = jload("encounter_design.json", data)["rules"]["hearts"]["clear_of_path_blocks"]
    if rules.get("path_clearance") != clear:
        rep.err("siting", "rules.path_clearance %s is not rules.hearts.clear_of_path_blocks %d" % (rules.get("path_clearance"), clear))
    paths = np.array([p[:2] for pl in jload("route_paths.json", data)["paths"].values() for p in pl], float)
    cx, cz = r["site"]["centre"]
    who = [("the centre", (cx, cz))]
    if spots.get("anchor"):
        who.append(("the anchor", (spots["anchor"][0], spots["anchor"][2])))
    who += [("the cache", (s[0], s[2])) for s in spots.get("caches") or []]
    for name, (x, z) in who:
        d = float(np.min(np.hypot(paths[:, 0] - x, paths[:, 1] - z)))
        if d < clear:
            rep.err("siting", "%s: %s (%d, %d) is %.0f blocks from a route path (needs %d)" % (i, name, x, z, d, clear))
    dmin = float(min(np.min(np.hypot(paths[:, 0] - x, paths[:, 1] - z)) for x, z in cols))
    rep.note("%s: nearest route path to any column %.0f" % (i, dmin))
    if NA._cell(cx, cz, data) != r.get("cell"):
        rep.err("siting", "%s: the centre (%d, %d) is in cell %s, the record says %s" % (i, cx, cz, NA._cell(cx, cz, data), r.get("cell")))
    sub = SA._subregion(cx, cz, data)[0]
    if sub != r.get("subregion"):
        rep.err("siting", "%s: the centre is in sub-region %s, the record says %s" % (i, sub, r.get("subregion")))


def check_gate(r, rep):
    pk = r["pokemon"]
    for k in ("gate", "appears_after"):
        if pk.get(k) != GATE:
            rep.err("residents", "%s: %s is %s, the design gates every far-south resident on %s" % (pk["id"], k, pk.get(k), GATE))


def check_species(r, jar, rep, data):
    """The species is in the jar and lives within one climate step of its sub-region's paint (spawn_habitat_audit's
    jar natives and ladder)."""
    import spawn_habitat_audit as SH
    pk = r["pokemon"]
    name = pk["species"].split(":", 1)[1]
    if name not in jar.species:
        rep.err("residents", "%s: %s is not a species in the Cobblemon jar" % (pk["id"], pk["species"]))
        return
    subs = {s["id"]: s for s in jload("regions.json", data)["subregions"]}
    preset = ((subs.get(r.get("subregion")) or {}).get("paint") or {}).get("preset")
    place = SH.PRESET_CLIMATE.get(preset)
    if place is None:
        rep.err("residents", "%s: sub-region %s's paint %s has no climate class" % (pk["id"], r.get("subregion"), preset))
        return
    climates, _kinds, _cave, basis = jar.info((name, None))
    step = min(SH.distance(n, place) for n in climates)
    if step > 1:
        rep.err("residents", "%s: %s is native to %s (%s), %d steps from %s's %s (%s)"
                % (pk["id"], name, sorted(climates), basis, step, r.get("subregion"), place, preset))
    rep.note("%s: %s native %s, place %s (%s), %d step(s)" % (pk["id"], name, sorted(climates), place, preset, step))


def _jar_has_item(jar, item):
    ns, _, path = item.partition(":")
    return "assets/%s/models/item/%s.json" % (ns, path) in jar.names


def check_caches(doc, r, E, R, spots, rpack, jar, rep, data):
    i = r["id"]
    rw = {x["id"]: x for x in jload("rewards.json", data)["rewards"]}
    caches = r.get("caches") or []
    if caches and (r.get("records") or {}).get("reward") not in [c["reward"] for c in caches]:
        rep.err("caches", "%s: records.reward %s names none of its caches" % (i, (r.get("records") or {}).get("reward")))
    for c, s in zip(caches, spots["caches"]):
        rid = c["reward"]
        w = rw.get(rid)
        if not w or w.get("kind") != "cache":
            rep.err("caches", "%s: data/rewards.json %s is not a cache" % (i, rid))
            continue
        if (c.get("items_hook") or {}).get("reward") != rid:
            rep.err("caches", "%s: the cache %s has no items_hook naming it" % (i, rid))
        contents = w.get("contents") or []
        if not contents:
            rep.err("caches", "%s: %s gives nothing" % (i, rid))
        if jar is not None:
            for it in contents:
                if not _jar_has_item(jar, it["item"]):
                    rep.err("caches", "%s: %s gives %s, which is not an item in the Cobblemon jar" % (i, rid, it["item"]))
        cont = (w.get("container") or {}).get("at")
        if cont and SA.base(R.blocks.get(tuple(cont), "")) != (w.get("container") or {}).get("block"):
            rep.err("ys","%s: %s's container %s is not written at %s (the build writes %s)"
                    % (i, rid, (w.get("container") or {}).get("block"), cont, R.blocks.get(tuple(cont))))
        if s[1] is not None:
            x, y, z = s
            if E.water(x, z) is not None:
                rep.err("caches", "%s: the cache spot %s is on a wet column" % (i, list(s)))
            for yy in (y, y + 1):
                st = R.blocks.get((x, yy, z))
                if not SA.passable(E, x, yy, z) or (st is not None and SA.base(st) not in SA.PASSABLE):
                    rep.err("caches", "%s: the cache spot %s is not free at y%d" % (i, list(s), yy))
        check_reward_pack(i, w, rpack, rep)


def check_reward_pack(i, w, rpack, rep):
    """The rewards pack pays the cache: one location criterion on exactly the trigger box in the overworld, running
    exactly cobblers:reward/<id>, whose gives are exactly the record's contents."""
    rid = w["id"]
    if rpack is None:
        rep.err("caches", "%s: no rewards pack to read %s from" % (i, rid))
        return
    adv = Path(rpack) / "data" / "cobblers" / "advancement" / "reward" / ("%s.json" % rid)
    fn = Path(rpack) / "data" / "cobblers" / "function" / "reward" / ("%s.mcfunction" % rid)
    if not adv.is_file() or not fn.is_file():
        rep.err("caches", "%s: the rewards pack has no advancement or function for %s" % (i, rid))
        return
    a = json.loads(adv.read_text(encoding="utf-8"))
    crit = a.get("criteria") or {}
    lo, hi = w["trigger"]["min"], w["trigger"]["max"]
    want = {"x": {"min": lo[0], "max": hi[0] + 1}, "y": {"min": lo[1], "max": hi[1] + 1}, "z": {"min": lo[2], "max": hi[2] + 1}}
    if len(crit) != 1:
        rep.err("caches", "%s: %s's advancement has %d criteria, expected 1" % (i, rid, len(crit)))
    for c in crit.values():
        if c.get("trigger") != "minecraft:location":
            rep.err("caches", "%s: %s's advancement fires on %s, not minecraft:location" % (i, rid, c.get("trigger")))
            continue
        locs = [p.get("predicate", {}).get("location", {}) for p in (c.get("conditions") or {}).get("player") or []]
        if not any(l.get("position") == want and l.get("dimension") == "minecraft:overworld" for l in locs):
            rep.err("caches", "%s: %s's advancement box %s is not the trigger %s..%s in the overworld"
                    % (i, rid, [l.get("position") for l in locs], lo, hi))
    if (a.get("rewards") or {}).get("function") != "cobblers:reward/%s" % rid:
        rep.err("caches", "%s: %s's advancement runs %s" % (i, rid, (a.get("rewards") or {}).get("function")))
    if a.get("requirements") is not None and len(a["requirements"]) != 1:
        rep.err("caches", "%s: %s's advancement has extra requirements %s" % (i, rid, a["requirements"]))
    gives = Counter()
    for l in SA._code(fn.read_text(encoding="utf-8")):
        g = re.match(r"give @s (\S+?)(\[.*\])? (\d+)$", l)
        if g:
            gives[g.group(1)] += int(g.group(3))
        elif re.match(r"(give|loot|summon|function)\b", l) or " run " in l:
            rep.err("caches", "%s: %s's function does more than give and say: %s" % (i, rid, l[:100]))
    want_items = Counter()
    for it in w["contents"]:
        want_items[it["item"]] += int(it["count"])
    if gives != want_items:
        rep.err("caches", "%s: %s's function gives %s, data/rewards.json says %s" % (i, rid, dict(gives), dict(want_items)))


def check_never_revoked(doc, fns, rpack, rep):
    """Once per player: nothing in the far south's pack, the rewards pack or tools/ revokes a cache's advancement."""
    ids = [c["reward"] for r in doc["residents"] for c in r.get("caches") or []]
    texts = [("the far south's pack", "\n".join(v for k, v in fns.items() if not k.startswith("__")))]
    if rpack is not None:
        texts += [("the rewards pack", "\n".join(p.read_text(encoding="utf-8")
                                                 for p in Path(rpack).rglob("*.mcfunction")))]
    for p in sorted((ROOT / "tools").glob("*.py")):
        if p.name != Path(__file__).name:
            texts.append(("tools/" + p.name, p.read_text(encoding="utf-8")))
    for where, t in texts:
        for l in t.splitlines():
            if "advancement revoke" not in l:
                continue
            if any(rid in l for rid in ids) or "cobblers:reward" in l or " everything" in l:
                rep.err("caches", "%s revokes a cache's advancement: %s" % (where, l.strip()[:120]))


def check_objective(doc, rep, data):
    obj = doc["build"]["objective"]
    for p in sorted(Path(data).glob("*.json")):
        if p.name == RECORD:
            continue
        if re.search(r'"objective"\s*:\s*"%s"' % re.escape(obj), p.read_text(encoding="utf-8")):
            rep.err("keeper", "the objective %s is also data/%s's" % (obj, p.name))
    for p in sorted((ROOT / "tools").glob("*.py")):
        if p.stem in (GENERATOR, Path(__file__).stem):
            continue
        if obj in p.read_text(encoding="utf-8"):
            rep.err("keeper", "the objective %s is also named by tools/%s" % (obj, p.name))


def check_wiring(doc, rep, text=None):
    text = text if text is not None else (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    st = doc["build"]["steps"]
    pack = doc["build"]["pack"]
    jobs = [m.group(1) for m in re.finditer(r'add\("([^"]+)",\s*"[^"]+\.py"', text)]
    for j in (GENERATOR, GENERATOR + "_audit"):
        if j not in jobs:
            rep.err("wiring", "tools/reapply.py has no prepare job %s" % j)
    if GENERATOR in jobs and GENERATOR + "_audit" in jobs and jobs.index(GENERATOR) > jobs.index(GENERATOR + "_audit"):
        rep.err("wiring", "the prepare job %s_audit runs before the generator it audits" % GENERATOR)
    m = re.search(r'add\("%s_audit",\s*"([^"]+)"' % GENERATOR, text)
    if m and m.group(1) != Path(__file__).name:
        rep.err("wiring", "the prepare job %s_audit runs %s" % (GENERATOR, m.group(1)))
    order = [m.group(1) for m in re.finditer(r'out\.append\(\("(R[0-9A-Z]+)"', text)]
    calls = {m.group(1): m.group(2) for m in re.finditer(
        r'out\.append\(\("(R[0-9A-Z]+)",\s*"[^"]*",\s*\n?\s*([A-Za-z_]+\.[A-Za-z_]+)\(\)\)\)', text)}
    for kind, (fn, after, before) in STEP_ORDER.items():
        step = st[kind]
        if order.count(step) != 1:
            rep.err("wiring", "tools/reapply.py appends step %s %d times" % (step, order.count(step)))
            continue
        if calls.get(step) != "%s.%s" % (GENERATOR, fn):
            rep.err("wiring", "step %s is %s, not %s.%s()" % (step, calls.get(step), GENERATOR, fn))
        k = order.index(step)
        if after not in order or order.index(after) > k:
            rep.err("wiring", "step %s runs before %s" % (step, after))
        if before and (before not in order or order.index(before) < k):
            rep.err("wiring", "step %s runs after %s" % (step, before))
    tree = ast.parse(text)
    for name in ("SERVER_PACKS", "WORLD_LOCAL"):
        vals = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
                try:
                    vals = ast.literal_eval(node.value)
                except ValueError:
                    vals = None
        if vals is None or pack not in vals:
            rep.err("wiring", "%s is not in tools/reapply.py %s" % (pack, name))


# ------------------------------------------------------------------ the whole audit


def audit(doc, ground, water, pack, steps, data=DATA, rpack=None, jar=None, reapply_text=None):
    """`water(x, z)` is the water surface y or None; `steps` are the generator's R9FS + R18FS; `rpack` the rewards
    pack (tools/rewards_pack.py's output); `jar` a spawn_habitat_audit.Jar (or None: those checks are not run)."""
    rep = Report()
    if doc.get("schema") != SCHEMA:
        rep.err("spec", "schema %s, expected %s" % (doc.get("schema"), SCHEMA))
    check_wiring(doc, rep, reapply_text)
    check_keep_out(doc, rep, data)
    b = doc["build"]
    fdir = Path(pack) / "data" / b["namespace"] / "function" / b["folder"]
    if not fdir.is_dir():
        rep.err("pack", "%s is missing: run tools/far_south.py first" % fdir)
        return rep
    fns = SA.load_pack(pack, b["namespace"], b["folder"])
    import function_limits
    for name, text in fns.items():
        if name.startswith("__"):
            continue
        for n, cmd, why in function_limits.check_lines(text.splitlines(), where=name):
            rep.err("functions", "%s:%d %s" % (name, n, why))
    spawn = set(jload("spawn_blocks.json", data)["blocks"])
    pol = jload("spawn_block_policy.json", data)
    whitelist = {x for w in pol.get("whitelist") or [] if "far_south" in (w.get("scope") or "") for x in w["blocks"]}
    A = SA.authored(doc, data, record=RECORD)
    spots_by_id, keeper_built = {}, []
    for r in doc["residents"]:
        E = NA.expect(r, ground, water)
        spots = NA.spots_of(r, E)
        spots_by_id[r["id"]] = spots
        SA.check_ys(doc, r, E, spots, rep, data)
        NA.check_standing(r, E, spots, rep)
        NA.check_bbox(r, E, spots, rep)
        check_measured(r, ground, water, rep)
        text = fns.get("%s/build" % r["id"])
        if text is None:
            rep.err("writes", "%s has no build function" % r["id"])
            continue
        R = SA.Replay(text)
        SA.check_writes(doc, r, E, R, spots, rep, data, spawn, whitelist)
        cols = R.columns() | E.cols | {(s[0], s[2]) for k in ("anchor",) if spots.get(k) for s in [spots[k]]} \
            | {(s[0], s[2]) for s in spots["caches"]}
        check_siting(doc, r, cols, spots, A, rep, data)
        check_caches(doc, r, E, R, spots, rpack, jar, rep, data)
        if r.get("pokemon"):
            SA.check_resident(doc, r, spots["anchor"], rep, data)
            check_gate(r, rep)
            if jar is not None:
                check_species(r, jar, rep, data)
            if spots["anchor"][1] is not None:
                keeper_built.append((r, spots["anchor"]))
    SA.check_keeper(doc, keeper_built, fns, rep, data)
    check_objective(doc, rep, data)
    check_never_revoked(doc, fns, rpack, rep)
    SA.check_steps(doc, spots_by_id, steps, rep, data, npc_step=b["steps"]["entities"])
    for s in steps:
        if s[0] == "fn":
            ns, _, path = s[1].partition(":")
            rel = path[len(b["folder"]) + 1:] if path.startswith(b["folder"] + "/") else None
            if ns != b["namespace"] or rel not in fns:
                rep.err("steps", "the step runs function %s, which the pack does not have" % s[1])
    todo = ["load"] + [s[1].split(":", 1)[1].split("/", 1)[1] for s in steps if s[0] == "fn"]
    reached = set()
    while todo:
        f = todo.pop()
        if f in reached or f not in fns:
            continue
        reached.add(f)
        todo += re.findall(r"function %s:%s/(\S+)" % (b["namespace"], b["folder"]), fns[f])
    for f in sorted(set(fns) - reached - {"__load_tag__"}):
        rep.err("functions", "%s is reached by nothing" % f)
    return rep


def _run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, (res.stdout + res.stderr).strip()[-400:]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=None, help="default build/datapacks/cobblers_far_south; when that is absent the "
                                                  "generator is run into a temporary folder and that is audited")
    ap.add_argument("--rewards-pack", default=None, help="default build/datapacks/cobblers_rewards, else written to a "
                                                          "temporary folder by tools/rewards_pack.py")
    ap.add_argument("--jar", default=None, help="the Cobblemon 1.8 jar (default: tools/battle_sim.find_jar())")
    ap.add_argument("--source-root")
    ap.add_argument("-v", "--verbose", action="store_true", help="print the notes too")
    a = ap.parse_args(argv)
    import ground as G
    doc = jload(RECORD)
    g = G.load(a.source_root)
    try:
        import far_south as FS                # for its OUTPUT only: the steps it hands tools/reapply.py
        fd = FS.load()
        steps = FS.placement_steps(fd, g) + FS.entity_steps(fd, g)
    except SystemExit as e:
        print("PROBLEM steps: the generator refuses to give its steps: %s" % e)
        return 1
    tmp = tempfile.TemporaryDirectory()
    pack = Path(a.pack) if a.pack else PACK
    if a.pack is None and not PACK.is_dir():
        pack = Path(tmp.name) / "cobblers_far_south"
        cmd = [sys.executable, str(ROOT / "tools" / "far_south.py"), "--out", str(pack)]
        if a.source_root:
            cmd += ["--source-root", a.source_root]
        rc, out = _run(cmd)
        if rc != 0:
            print("PROBLEM pack: %s is absent and the generator refuses to write one: %s" % (PACK, out))
            return 1
        print("far_south_audit: %s is absent; auditing the generator's output written to a temporary folder" % PACK)
    rpack = Path(a.rewards_pack) if a.rewards_pack else REWARDS_PACK
    if a.rewards_pack is None and not REWARDS_PACK.is_dir():
        rpack = Path(tmp.name) / "cobblers_rewards"
        rc, out = _run([sys.executable, str(ROOT / "tools" / "rewards_pack.py"), "--out", str(rpack)])
        if rc != 0:
            print("PROBLEM caches: %s is absent and tools/rewards_pack.py refuses to write one: %s" % (REWARDS_PACK, out))
            return 1
    jar, jar_note = None, None
    try:
        import spawn_habitat_audit as SH
        jar = SH.Jar(a.jar or SH.find_jar())
        jar.names = set(jar.names)
    except Exception as e:                    # no jar anywhere: say so, never pass silently
        jar_note = "the species, habitat and item checks were NOT run: no Cobblemon 1.8 jar (%s)" % e
    water = SA.Water(g, [tuple(r["site"]["centre"]) for r in doc["residents"]])
    rep = audit(doc, g, water, pack, steps, rpack=rpack, jar=jar)
    tmp.cleanup()
    if a.verbose:
        for n in rep.notes:
            print("note: %s" % n)
    real, hits, stale = classify(rep.errors)
    for e in hits:
        print("KNOWN %s" % e)
    for e in real:
        print("PROBLEM %s" % e)
    for c, t, _w in stale:
        print("PROBLEM stale: the KNOWN fault '%s' no longer fires (fixed?): remove it from KNOWN" % t)
    if jar_note:
        print("NOT CHECKED %s" % jar_note)
    bad = len(real) + len(stale)
    verdict = "clean" if not bad else "%d problem(s)" % bad
    print("far_south_audit: %s, %d known defect(s)%s" % (verdict, len(hits), " (jar checks NOT run)" if jar_note else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
