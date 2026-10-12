#!/usr/bin/env python
"""Every sea has a region: data/marine_seas.json -> data/spawns.json marine_zones and the marine entries.

The owner, 2026-10-12, looking at the region map: "Is the Windward Sea the only defined ocean? All water should have
regions as well." Until then data/spawns.json marine_zones held only the Windward Sea (hand-authored 2026-09-26); the
north coast, the strait, the east and south seas and the Outer Deep had no region, no Nuzlocke zone, no location title
and fell back to Cobbleverse's inherited ocean spawns.

The authored table is data/marine_seas.json (one record per sea: its clip boxes, grid, bands, and per band the families
and the heart). This tool is the translation: it expands each family through tools/build_encounters.py's own rules
(expand_family: stages from the jar's evolutions, maturity by tier, the stage's level range inside the band; build_heart:
the band's boss table, alphas) and writes, into data/spawns.json,

  marine_zones   one record per sea after the Windward Sea (which stays as authored), with the bands and, per band, the
                 mirror of its compiled roster (the shape the Windward bands carry)
  entries        the sea bands' marine_coordinate_boxes entries (ids marine.<band>.<species>, heart ids
                 marine.<band>.heart.<species>); the Windward Sea's entries are never touched

Run it, then `python tools/build_encounters.py` (it stamps rules.held_items on the entries and checks the alpha rule),
then `python tools/compile_spawns.py`. `--check` exits 1 if data/spawns.json is not what the table produces (held items
aside, which build_encounters owns).

A sea's three bands are the Windward Sea's scheme: the shallows (0-128 blocks from land), the open water (128-384) and
the deep (384 and beyond), each one gym cap above the last (the leg whose cap tops the band is its `tier`, which sets
the maturity of its families). The geometry is tools/compile_spawns.py marine_bands, on a coarse grid so the box count
stays small: every compiled box is a spawn condition the server holds in memory.

  python tools/marine_seas.py            # write data/spawns.json
  python tools/marine_seas.py --check    # exit 1 if it is stale
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import battle_sim  # noqa: E402
import build_encounters as B  # noqa: E402
import compile_spawns as CS  # noqa: E402
import subregion_boxes  # noqa: E402
import waterways as W  # noqa: E402

TABLE = ROOT / "data" / "marine_seas.json"
SPAWNS = ROOT / "data" / "spawns.json"
MECH = "marine_coordinate_boxes"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def bands_of(sea):
    """The compile-side band list of a sea: id, the distance span from land."""
    return [{"id": b["id"], "from_blocks": b["from_blocks"], "to_blocks": b["to_blocks"]} for b in sea["bands"]]


def zone_record(sea, common):
    """The marine_zones record the compiler and the tools read (bands filled in by the caller)."""
    z = {"id": sea["id"], "display_name": sea["display_name"], "marine_region": sea["marine_region"],
         "status": common["status"], "draft": common["draft"], "theme": sea["theme"], "legs": sea["legs"],
         "clip_boxes": sea["clip_boxes"], "clip_basis": sea["clip_basis"], "mechanism": MECH, "grid": sea["grid"],
         "max_land_share": sea["max_land_share"], "distance_measure": common["distance_measure"],
         "policy": common["policy"], "access": common["access"], "level_logic": sea["level_logic"],
         "depth": common["depth"]}
    return z


def place(dex, name, species, overrides):
    """(position, why) for a stage: the table's override by species, else the jar's most-used water position."""
    base = dex.split(name)[0]
    if base in overrides:
        return overrides[base]
    pos, _ = dex.position(name, True, False, species)
    return pos


def family_rows(dex, rules, band, fam, where, overrides):
    """[(row dict)] for one band family [species, role, (weight), (conditions)]: every stage the band keeps."""
    species, role, weight, cond = B.parse_family(fam, rules, where)
    tier = band["tier"]
    lo, hi = band["level_band"]
    rows = []
    for name, slo, shi, w, reason in B.expand_family(dex, rules, tier, (lo, hi), species, role, weight, where):
        pos = place(dex, name, species, overrides)
        c = dict(cond)
        if pos == "surface":
            c.setdefault("canSeeSky", True)
        rows.append({"name": name, "bucket": rules["roles"][role]["bucket"], "level": "%d-%d" % (slo, shi), "weight": w,
                     "conditions": c, "reason": reason, "position": pos, "family": dex.family(species), "priority": role,
                     "role": role})
    return rows


def heart_geometry(boxes, corridor, area_cap=1.0 / 9.0):
    """(x, z, radius) of a band's focus heart: the band's cell farthest from every route corridor box (Chebyshev gap),
    and the largest multiple of 16 whose heart covers at most a ninth of the band (docs/mechanics/ENCOUNTER_DESIGN.md
    section 10). The first of the farthest, in (x, z) order, so a rerun is the same."""
    import numpy as np
    g = CS.MARINE_GRID
    cells = []
    for x0, x1, z0, z1 in boxes:
        for cx in range(x0, x1 + 1, g):
            for cz in range(z0, z1 + 1, g):
                cells.append((cx, cz))
    if not cells:
        raise SystemExit("a band with no box cannot carry a heart")
    c = np.array(cells, dtype=np.int64)
    best, best_gap = None, -1
    b = np.array([q[:4] for q in corridor], dtype=np.int64)
    for i in range(0, len(c), 512):
        ch = c[i:i + 512]
        dx = np.maximum(0, np.maximum(ch[:, None, 0] - b[None, :, 1], b[None, :, 0] - (ch[:, None, 0] + g - 1)))
        dz = np.maximum(0, np.maximum(ch[:, None, 1] - b[None, :, 3], b[None, :, 2] - (ch[:, None, 1] + g - 1)))
        gap = np.maximum(dx, dz).min(axis=1)
        j = int(gap.argmax())
        if gap[j] > best_gap:
            best_gap, best = int(gap[j]), (int(ch[j, 0]), int(ch[j, 1]))
    if best_gap <= 128:
        raise SystemExit("no cell of a band is more than 128 blocks from every corridor (best gap %d)" % best_gap)
    x, z = best[0] + g // 2, best[1] + g // 2
    total = subregion_boxes.area(boxes)
    radius = 0
    for r in range(16, 4097, 16):
        hb = CS.focus_heart_boxes(boxes, {"kind": "focus", "x": x, "z": z, "radius": r, "clear_of_path_blocks": 128},
                                  g, corridor)
        if not hb or subregion_boxes.area(hb) > total * area_cap:
            break
        radius = r
    if not radius:
        raise SystemExit("a band's heart at (%d, %d) covers more than a ninth of the band even at radius 16" % (x, z))
    return x, z, radius, best_gap


def sea_entries(dex, rules, sea, band_boxes, corridor, alpha, overrides):
    """(entries, mirrors per band id, hearts per band id) for one sea."""
    entries, mirrors, hearts = [], {}, {}
    for band in sea["bands"]:
        where = "%s/%s" % (sea["id"], band["id"])
        lo, hi = band["level_band"]
        rows = []
        for fam in band["families"]:
            rows += family_rows(dex, rules, band, fam, where, overrides)
        seen = {}
        for r in rows:
            if r["name"] in seen:
                raise SystemExit("%s: %s comes twice in the band (a family and another share a stage)" % (where, r["name"]))
            seen[r["name"]] = r
        spec = band["heart"]
        t = {"tier": band["tier"], "heart": {"kind": "focus", "water": spec["families"]}}
        hrows = B.build_heart(dex, rules, where, t, (lo, hi), band["tier"])
        for r in hrows:
            r["position"] = place(dex, r["name"], r["name"], overrides)
            if r["position"] == "surface":
                r["conditions"] = dict(r["conditions"], canSeeSky=True)
        hx, hz, hr, gap = heart_geometry(band_boxes[band["id"]], corridor)
        heart = {"kind": "focus", "x": hx, "z": hz, "radius": hr, "clear_of_path_blocks": 128,
                 "why": "the owner, 2026-10-05: \"every area should have a rare, ultra rare, and boss table\": the band's "
                        "heart, the band cell farthest from every route corridor at (%d, %d), radius %d: the largest "
                        "multiple of 16 whose heart covers at most a ninth of the compiled band; its nearest heart cell is "
                        "%d blocks from a route corridor box (tools/marine_seas.py heart_geometry, "
                        "tools/compile_spawns.py focus_heart_boxes)" % (hx, hz, hr, gap)}
        for r in rows:
            e = {"id": "marine.%s.%s" % (band["id"], r["name"].replace(" ", "_")), "species": r["name"],
                 "bucket": r["bucket"], "level": r["level"], "weight": r["weight"], "ambient": True,
                 "scope": band["id"], "mechanism": MECH, "conditions": r["conditions"],
                 "conditions_basis": "%s: %s. No biome filter: the band's boxes hold only open sea" % (
                     band["display_name"], band.get("basis_short") or sea["theme"]),
                 "eligibility_reason": r["reason"], "biomes": [], "spawnable_position": r["position"]}
            entries.append(e)
        for r in hrows:
            e = {"id": "marine.%s.heart.%s" % (band["id"], r["name"].replace(" ", "_")), "species": r["name"],
                 "bucket": r["bucket"], "level": r["level"], "weight": r["weight"], "ambient": True,
                 "scope": band["id"], "mechanism": MECH, "conditions": r["conditions"],
                 "conditions_basis": "%s: heart presence. No biome filter: the band's boxes hold only open sea" % band["display_name"],
                 "eligibility_reason": r["reason"] if r["reason"].startswith("heart") else "heart: " + r["reason"], "heart": heart, "biomes": [],
                 "spawnable_position": r["position"], "alpha": alpha}
            entries.append(e)
        mirrors[band["id"]] = [B.mirror_of(dex, r) for r in rows]
        hearts[band["id"]] = heart
    return entries, mirrors, hearts


def generate(table, spawns, regions, routes, waterdoc, dex, rules):
    out = copy.deepcopy(spawns)
    common, overrides = table["common"], table.get("position_overrides") or {}
    seas = table["seas"]
    own_zones = {s["id"] for s in seas}
    own_bands = {b["id"] for s in seas for b in s["bands"]}
    zones = [z for z in out["marine_zones"] if z["id"] not in own_zones]
    water = []
    for w in waterdoc["waterways"]:
        for _, _, bs in W.boxes_by_segment(w["polyline"], w["half_width"], CS.WATERWAY_GRID):
            water.extend(bs)
    # the geometry first: marine_bands reads only the zones, so the hearts can be placed on the compiled boxes
    probe = copy.deepcopy(out)
    probe["marine_zones"] = zones + [dict(zone_record(s, common), bands=bands_of(s)) for s in seas]
    boxes = CS.marine_bands(probe, regions, routes, water)
    corridor = subregion_boxes.route_boxes(routes)
    alpha = rules["hearts"]["alpha"]
    new_entries = []
    for sea in seas:
        ents, mirrors, hearts = sea_entries(dex, rules, sea, boxes, corridor, alpha, overrides)
        new_entries += ents
        z = zone_record(sea, common)
        z["bands"] = [{"id": b["id"], "display_name": b["display_name"], "from_blocks": b["from_blocks"],
                       "to_blocks": b["to_blocks"],
                       "level_band": {"minimum": b["level_band"][0], "maximum": b["level_band"][1]},
                       "tier": b["tier"], "basis": b["basis"],
                       "compiled": {"boxes": len(boxes[b["id"]]), "blocks": subregion_boxes.area(boxes[b["id"]])},
                       "entries": mirrors[b["id"]]} for b in sea["bands"]]
        zones.append(z)
    out["marine_zones"] = zones
    kept = [e for e in out["entries"] if not (e.get("mechanism") == MECH and e.get("scope") in own_bands)]
    at = max((i for i, e in enumerate(kept) if e.get("mechanism") == MECH), default=len(kept) - 1) + 1
    out["entries"] = kept[:at] + new_entries + kept[at:]
    return out


def strip_held(doc):
    d = copy.deepcopy(doc)
    for e in d["entries"]:
        e.pop("held_items", None)
    return d


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true")
    p.add_argument("--table", default=str(TABLE))
    p.add_argument("--spawns", default=str(SPAWNS))
    a = p.parse_args(argv)
    spawns = load(a.spawns)
    design = load(ROOT / "data" / "encounter_design.json")
    dex = B.Dex(battle_sim.find_jar())
    try:
        out = generate(load(a.table), spawns, load(ROOT / "data" / "regions.json"), load(ROOT / "data" / "routes.json"),
                       load(ROOT / "data" / "waterways.json"), dex, design["rules"])
    except B.DesignError as ex:
        print("FAIL: %s" % ex, file=sys.stderr)
        return 1
    if a.check:
        same = json.dumps(strip_held(out), sort_keys=True) == json.dumps(strip_held(spawns), sort_keys=True)
        print("%s: %d marine entries" % ("identical" if same else "STALE (run tools/marine_seas.py)",
                                         sum(1 for e in out["entries"] if e.get("mechanism") == MECH)))
        return 0 if same else 1
    Path(a.spawns).write_text(B.dumps(out), encoding="utf-8", newline="\n")
    n = sum(1 for e in out["entries"] if e.get("mechanism") == MECH)
    print("wrote %s: %d seas after the Windward Sea, %d marine entries" % (a.spawns, len(load(a.table)["seas"]), n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
