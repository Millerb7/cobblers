#!/usr/bin/env python
"""The legendaries sweep: catalogue templates seated where a surface paste cannot go, measured and re-checked.

The owner, 2026-10-06: "Go through the whole Cobbleverse catalogue and place what is left, in obscured spots ...
Use /place template, not /clone. Each one: what gates it, what a player gets, and how anyone would find it."

data/adopted_legendary_sites.json `sites` holds templates seated ON the ground (tests/test_adopted_legendary_sites.py:
the bottom layer is the cheapest seat in the measured range, every column dry). The two templates this sweep places
are not that shape, so they live in the same file's `sweep_sites`, each with a `seat`:

  sunk       the template's own floor slab is buried: layer `ground_layer` stands at the footprint's cheapest seat
             (the Giratina piece: a 12-layer distortion slab, layer 11 at ground level, its glass dome above).
             Every footprint column must be dry (data/world.json sea level and tools/water_mask.py's lakes).
  floating   the whole template hangs `gap` or more over the highest ground in its footprint, so its air writes
             over nothing (Newmoon Island: a floating island whose bottom layer is 28% air; seated on ground it
             would dig holes, on sea it would open dry pits).

Every sweep site is held to the hidden-site rules (tools/hidden_sites.py: 96 from every authored coordinate, the
keep-outs, 120 from every portal, 800 from every other legendary - Hoopa's cradle included now that Hoopa is an
encounter), to the residents' rules (tests/test_resident_siting.py: 128 from every route path, clear of every
activated Habitat Block's spawn range plus a 28-block leash), to the runtime ceiling y575, and to the bare-terrain
route sightings. The record's measured numbers are held to the heightmap (tools/ground.py, rounded), never a world.

  python tools/legendary_sweep.py measure <site id>     the numbers, as the record should state them
  python tools/legendary_sweep.py check                 every sweep site against the record and the rules
  python tools/legendary_sweep.py catalogue             the catalogue table's counts by status

What this does NOT cover (CLAUDE.md "Our list is not the world"): anything in the world no file in data/ authors.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import adopted_sites  # noqa: E402
import hidden_sites as H  # noqa: E402

SITES = ROOT / "data" / "adopted_legendary_sites.json"
REWARDS = ROOT / "data" / "rewards.json"
ROUTE_CLEAR = 128          # data/encounter_design.json rules.hearts.clear_of_path_blocks
LEASH = 28                 # tests/test_resident_siting.py LEASH: the largest leash any brief names
FLOAT_GAP_MIN = 16         # a floating template's bottom over the highest ground: the tallest vanilla tree it hangs over
HOOPA = (3357, 3306)       # data/hoopa_cradle.json spot: an encounter since 2026-10-06, so in the spread
KINDS = ("sunk", "floating")
STATUSES = ("adopted", "placed_by_sweep", "ours_authored", "planned", "stays_where_it_generates", "out_by_owner",
            "refused", "unplaced", "not_loaded")


def load(path=SITES):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sweep_sites(doc=None):
    doc = doc if doc is not None else load()
    return list(doc.get("sweep_sites") or [])


def runtime_top(doc=None):
    doc = doc if doc is not None else load()
    return int(doc["ceiling"]["runtime_top_y"])


def caches_for(site, rewards=None):
    rewards = rewards if rewards is not None else json.loads(REWARDS.read_text(encoding="utf-8"))
    ids = {(site.get("activation_item") or {}).get("source")}
    return [r for r in rewards["rewards"] if r["id"] in ids]


def legendary_centres(exclude, placements=None):
    out = H.legendary_centres(exclude, placements)
    out["hoopa_cradle"] = HOOPA
    return out


def wet_columns(g, box, step=1):
    import water_mask as W
    bodies, sea = W.bodies(), W.sea_level()
    x0, z0, x1, z1 = box
    n = 0
    for x in range(x0, x1 + 1, step):
        for z in range(z0, z1 + 1, step):
            if W.level_at(x, z, g, bodies, sea)[0] is not None:
                n += 1
    return n


def measure(site, g, placements=None, points=None, rewards=None):
    """Every number the record states, from the heightmap and the authored data alone."""
    import numpy as np
    w = adopted_sites.where(site, placements)
    box = adopted_sites.footprint(site, placements)
    h = g.box(*box)
    y = w["y"]
    height = site["size"][1]
    seat = H.seat(h)
    out = {"corner": w["corner"], "y": y, "top_y": y + height - 1, "box": list(box),
           "ground": {"min": int(h.min()), "max": int(h.max()), "median": float(np.median(h)), "columns": int(h.size)},
           "cheapest_seat": seat[0]}
    kind = site["seat"]["kind"]
    if kind == "sunk":
        level = y + int(site["seat"]["ground_layer"])
        out["ground_level_y"] = level
        out["displaces"] = {"cut_blocks": int(np.clip(h - level, 0, None).sum()), "cut_columns": int((h > level).sum()),
                            "fill_blocks": int(np.clip(level - h, 0, None).sum()), "fill_columns": int((h < level).sum())}
    elif kind == "floating":
        out["gap_over_highest_ground"] = y - int(h.max())
    skip = {site["id"], site.get("scheduled_as")} | {r["id"] for r in caches_for(site, rewards)}
    pts = [p for p in (points if points is not None else H.authored_points(skip))]
    near = H.nearest_authored(box, pts)
    routes = np.array([p for pl in json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))
                       ["paths"].values() for p in pl], float)
    x0, z0, x1, z1 = box
    dx = np.maximum(np.maximum(x0 - routes[:, 0], 0), routes[:, 0] - x1)
    dz = np.maximum(np.maximum(z0 - routes[:, 1], 0), routes[:, 1] - z1)
    hab = [b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
           if b.get("style") == "activated"]
    hab_margin = min((H.edge_distance(box, b["position"]["x"], b["position"]["z"]) - b["activated"]["spawn_range"] - LEASH
                      for b in hab), default=None)
    rule, portals = H.portal_rule()
    c = adopted_sites.centre(site, placements)
    spread = sorted((round(math.hypot(c[0] - a, c[1] - b)), k) for k, (a, b) in legendary_centres(site["id"], placements).items())
    seen, near_n, nearest_route = H.sightings(g, box, y + height - 1, pts)
    out["rules"] = {
        "nearest_authored": round(near[0]) if near else None,
        "nearest_authored_src": near[3] if near else None,
        "route_path_edge": round(float(np.min(np.hypot(dx, dz)))),
        "habitat_margin": round(hab_margin) if hab_margin is not None else None,
        "portal_edge": min(round(H.edge_distance(box, *p)) for _, p in portals),
        "spread_nearest": spread[0][0], "spread_nearest_id": spread[0][1],
        "keep_out": H.keep_out_problems(box),
        "route_sightings": seen, "route_points_within_1200": near_n,
        "wet_columns": wet_columns(g, box) if kind == "sunk" else None,
    }
    return out


def rule_problems(site, m, top):
    r = m["rules"]
    bad = []
    if r["nearest_authored"] is not None and r["nearest_authored"] < H.CLEARANCE:
        bad.append("authored point in %s %d from the footprint edge (rule %d)" % (r["nearest_authored_src"], r["nearest_authored"], H.CLEARANCE))
    if r["route_path_edge"] < ROUTE_CLEAR:
        bad.append("a route path %d from the footprint edge (rule %d)" % (r["route_path_edge"], ROUTE_CLEAR))
    if r["habitat_margin"] is not None and r["habitat_margin"] < 0:
        bad.append("inside an activated Habitat Block's spawn range plus a %d leash (margin %d)" % (LEASH, r["habitat_margin"]))
    rule, _ = H.portal_rule()
    if r["portal_edge"] < rule:
        bad.append("a portal %d from the footprint edge (rule %d)" % (r["portal_edge"], rule))
    if r["spread_nearest"] < H.SPREAD:
        bad.append("%s %d from this site's centre (spread %d)" % (r["spread_nearest_id"], r["spread_nearest"], H.SPREAD))
    bad += r["keep_out"]
    if m["top_y"] > top:
        bad.append("top occupied layer y%d over the runtime top y%d" % (m["top_y"], top))
    kind = site["seat"]["kind"]
    if kind not in KINDS:
        bad.append("seat kind %r is not one of %s" % (kind, KINDS))
    if kind == "sunk":
        if m["ground_level_y"] != m["cheapest_seat"]:
            bad.append("layer %d stands at y%d; the footprint's cheapest seat is y%d"
                       % (site["seat"]["ground_layer"], m["ground_level_y"], m["cheapest_seat"]))
        if r["wet_columns"]:
            bad.append("%d footprint columns are under painted water" % r["wet_columns"])
        if m["ground"]["min"] <= 62:
            bad.append("ground as low as y%d against sea level y62" % m["ground"]["min"])
    if kind == "floating":
        gap = int(site["seat"]["gap"])
        if gap < FLOAT_GAP_MIN:
            bad.append("gap %d is under %d" % (gap, FLOAT_GAP_MIN))
        if m["gap_over_highest_ground"] != gap:
            bad.append("the bottom layer is %d over the highest ground, the record says gap %d" % (m["gap_over_highest_ground"], gap))
    return bad


def record_problems(site, m):
    """[problem] where the record's stated numbers are not the measured ones."""
    bad = []
    for k in ("min", "max", "median", "columns"):
        if float(site["ground"].get(k, -1)) != float(m["ground"][k]):
            bad.append("ground.%s is %s, the heightmap says %s" % (k, site["ground"].get(k), m["ground"][k]))
    if site["seat"]["kind"] == "sunk":
        for k, v in m["displaces"].items():
            if site.get("displaces", {}).get(k) != v:
                bad.append("displaces.%s is %s, the heightmap says %s" % (k, site.get("displaces", {}).get(k), v))
    stated = site.get("rules_measured") or {}
    for k in ("nearest_authored", "route_path_edge", "portal_edge", "spread_nearest", "route_sightings"):
        if stated.get(k) != m["rules"][k]:
            bad.append("rules_measured.%s is %s, measured %s" % (k, stated.get(k), m["rules"][k]))
    text = site.get("placement_lives_in", "")
    want = "corner (%d, %d), y%d, top occupied layer y%d" % (m["corner"][0], m["corner"][1], m["y"], m["top_y"])
    if want not in text:
        bad.append("placement_lives_in does not quote %r" % want)
    return bad


def placement_problems(site, placements, rewards=None):
    """The contract between a sweep site, its one data/placements.json record and its activation item's one cache."""
    bad = []
    hits = [q for q in placements if q.get("id") == site.get("scheduled_as")]
    if len(hits) != 1:
        return ["scheduled_as %r names %d records" % (site.get("scheduled_as"), len(hits))]
    q = hits[0]
    for key, want in (("pack_template", site["template"]), ("template", site["template"]), ("kind", "donor"),
                      ("anchor_mode", "corner"), ("y_mode", "absolute"), ("rotation", "none"), ("mirror", "none"),
                      ("sweep_site", site["id"])):
        if q.get(key) != want:
            bad.append("%s.%s is %r, not %r" % (q["id"], key, q.get(key), want))
    if list(q.get("size") or []) != list(site["size"]):
        bad.append("%s.size %r is not the site's %r" % (q["id"], q.get("size"), site["size"]))
    if "adopted_site" in q:
        bad.append("%s carries adopted_site: that key is data/adopted_legendary_sites.json `sites`' contract" % q["id"])
    others = [o["id"] for o in placements if o is not q and site["template"] in (o.get("template"), o.get("pack_template"))]
    if others:
        bad.append("%s is also placed by %s" % (site["template"], others))
    item = site.get("activation_item") or {}
    cs = caches_for(site, rewards)
    if len(cs) != 1:
        bad.append("activation item %s: source %r names %d data/rewards.json records" % (item.get("item"), item.get("source"), len(cs)))
    else:
        r = cs[0]
        if [c["item"] for c in r["contents"]] != [item.get("item")] or r["contents"][0]["count"] != 1:
            bad.append("%s gives %s, not one %s" % (r["id"], [(c["item"], c["count"]) for c in r["contents"]], item.get("item")))
        if r.get("requires_flags") != site["gate"]["flags"]:
            bad.append("%s requires %s; the site's gate is %s" % (r["id"], r.get("requires_flags"), site["gate"]["flags"]))
        box = adopted_sites.footprint(site, placements)
        lo, hi = r["trigger"]["min"], r["trigger"]["max"]
        if not (box[0] <= lo[0] and hi[0] <= box[2] and box[1] <= lo[2] and hi[2] <= box[3]):
            bad.append("%s's trigger box is not inside the footprint %s" % (r["id"], box))
    # one source: no other cache, and no placement's remove/keep, hands the item out
    rdoc = rewards if rewards is not None else json.loads(REWARDS.read_text(encoding="utf-8"))
    every = [x["id"] for x in rdoc["rewards"] for c in x.get("contents") or [] if c.get("item") == item.get("item")]
    if len(every) > 1:
        bad.append("%s has %d sources in data/rewards.json %s; it has ONE" % (item.get("item"), len(every), every))
    return bad


def check(g, doc=None, placements=None):
    doc = doc if doc is not None else load()
    placements = placements if placements is not None else json.loads(
        adopted_sites.PLACEMENTS.read_text(encoding="utf-8"))["placements"]
    top = runtime_top(doc)
    out = {}
    for s in sweep_sites(doc):
        m = measure(s, g, placements)
        out[s["id"]] = rule_problems(s, m, top) + record_problems(s, m) + placement_problems(s, placements)
    return out


def catalogue_counts(doc=None):
    doc = doc if doc is not None else load()
    cat = doc.get("catalogue_2026_10_06", {}).get("templates") or []
    return Counter(t["status"] for t in cat), len(cat)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    mp = sub.add_parser("measure")
    mp.add_argument("site")
    sub.add_parser("check")
    sub.add_parser("catalogue")
    a = ap.parse_args(argv)
    if a.cmd == "catalogue":
        c, n = catalogue_counts()
        print("%d templates: %s" % (n, ", ".join("%s %d" % kv for kv in sorted(c.items()))))
        return 0
    import ground as G
    g = G.load()
    if a.cmd == "measure":
        s = next(x for x in sweep_sites() if x["id"] == a.site)
        print(json.dumps(measure(s, g), indent=1))
        return 0
    rc = 0
    for sid, bad in check(g).items():
        print("%s: %s" % (sid, "clean" if not bad else "%d problem(s)" % len(bad)))
        for b in bad:
            print("  PROBLEM %s" % b)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
