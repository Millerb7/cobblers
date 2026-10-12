"""The seas (data/marine_seas.json -> data/spawns.json marine_zones, tools/marine_seas.py) and the marine geometry.

The owner, 2026-10-12: "Is the Windward Sea the only defined ocean? All water should have regions as well." Written by
the implementer of the seas (the lead's brief asked for the tests in the same unit; a second reader should still grade
them). Each check reads the COMPILED pack or an independent data file (regions.json, encounter_design.json's tier
table, the dungeon prize roster, the jar's labels), never the generator's own derivation.

  python -m pytest tests/test_marine_seas.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import battle_sim as BS  # noqa: E402
import compile_spawns as CS  # noqa: E402

DATA = ROOT / "data"


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("marine_pack")
    CS.main(["--out", str(out)])
    return out / "data" / "cobblers" / "spawn_pool_world"


def box_of(spawn):
    c = spawn["condition"]
    return (c["minX"], c["maxX"], c["minZ"], c["maxZ"])


def marine_files(pack):
    out = {}
    for p in sorted((pack / "marine").glob("*.json")):
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))["spawns"]
    return out


def is_heart(spawn_id, band):
    import re
    return re.match(re.escape(band) + r"_h\d{4}_", spawn_id) is not None


def band_boxes(spawns, band):
    return sorted({box_of(s) for s in spawns if not is_heart(s["id"], band)})


def overlap(a, b):
    return not (a[1] < b[0] or b[1] < a[0] or a[3] < b[2] or b[3] < a[2])


def test_spawns_json_is_what_the_seas_table_produces():
    # Without it data/marine_seas.json (the authored table) and data/spawns.json (what compile_spawns reads) could drift:
    # an edit to either alone would change nothing in the pack, or change it from a record nobody authored.
    try:
        BS.load_pack(BS.find_jar())
    except BS.SimError as exc:
        pytest.skip("no Cobblemon 1.8 jar: the stages come from it (%s)" % exc)
    import marine_seas
    assert marine_seas.main(["--check"]) == 0, "run python tools/marine_seas.py, then python tools/build_encounters.py"


def test_every_sea_zone_names_a_marine_region_that_exists():
    # Without it a zone's region (the map's colour, the Nuzlocke zone's region, the habitat audit's climate) would be a
    # label nothing resolves: spawn_habitat_audit raises on a band whose region is unknown.
    regions = {m["id"] for m in load("regions.json")["marine_regions"]}
    zones = load("spawns.json")["marine_zones"]
    assert len(zones) >= 7, "the Windward Sea and the six seas of 2026-10-12 are zones; got %d" % len(zones)
    assert not [z["id"] for z in zones if z["marine_region"] not in regions], "a zone names no marine region"
    assert {z["marine_region"] for z in zones} == regions, "a marine region of data/regions.json has no sea over it"


def test_no_two_marine_boxes_overlap_anywhere_in_the_pack(pack):
    # Without it two zones (or a coarse cell and a fine seam strip) could cover the same block and double a weight: the
    # claim a zone's cells make on marine_bands is the whole reason a cell goes to one zone only.
    files = marine_files(pack)
    seen = []
    for band, spawns in files.items():
        for b in band_boxes(spawns, band):
            seen.append((band, b))
    assert len(seen) > 300, "too few marine boxes were read (%d): the check measured nothing" % len(seen)
    bad = [(a[0], b[0], a[1], b[1]) for i, a in enumerate(seen) for b in seen[i + 1:] if overlap(a[1], b[1])]
    assert not bad, "%d overlapping marine box pairs, e.g. %s" % (len(bad), bad[:3])


def test_each_sea_band_compiles_a_roster_with_a_heart_inside_its_own_boxes(pack):
    files = marine_files(pack)
    for zone in load("spawns.json")["marine_zones"]:
        for b in zone["bands"]:
            spawns = files.get(b["id"])
            assert spawns, "band %s compiled no file" % b["id"]
            base = band_boxes(spawns, b["id"])
            hearts = {box_of(s) for s in spawns if is_heart(s["id"], b["id"])}
            assert hearts, "band %s has no heart (every area has one, section 10)" % b["id"]
            # a heart may span several adjacent base boxes: every 16-block sample of it lies in the union of the base
            for h in hearts:
                for x in range(h[0], h[1] + 1, 16):
                    for z in range(h[2], h[3] + 1, 16):
                        assert any(q[0] <= x <= q[1] and q[2] <= z <= q[3] for q in base), \
                            "a heart box of %s lies outside its own base boxes at (%d, %d)" % (b["id"], x, z)


def test_a_sea_heart_covers_at_most_a_ninth_of_its_band_and_keeps_128_blocks_from_every_route(pack):
    # Without it a heart (the band's boss table, alphas above the cap) could swallow a band or sit beside the path.
    # ENCOUNTER_DESIGN.md section 10: at most 1/9 of the compiled area; no heart cell within 128 blocks of a corridor box.
    routes = [(b["min_x"], b["max_x"], b["min_z"], b["max_z"])
              for r in load("routes.json")["routes"] for b in r["spawn_scope"]["boxes"]]
    area = lambda bs: sum((b[1] - b[0] + 1) * (b[3] - b[2] + 1) for b in bs)  # noqa: E731
    files = marine_files(pack)
    for z in load("spawns.json")["marine_zones"]:
        if z["id"] == "windward_sea":
            continue
        for b in z["bands"]:
            spawns = files[b["id"]]
            base = band_boxes(spawns, b["id"])
            hearts = sorted({box_of(s) for s in spawns if is_heart(s["id"], b["id"])})
            assert area(hearts) <= area(base) / 9.0 + 1, "%s: the heart is %.3f of the band" % (b["id"], area(hearts) / area(base))
            for h in hearts:
                gap = min(max(0, max(h[0] - r[1], r[0] - h[1]), max(h[2] - r[3], r[2] - h[3])) for r in routes)
                assert gap > 128, "%s: a heart box %s is %d blocks from a route box" % (b["id"], h, gap)


def test_new_seas_levels_rise_one_gym_cap_per_band_and_stay_under_victory_roads_cap(pack):
    # Without it a sea's bands could skip a leg or run past the last cap (60). The cap table is the design file's own.
    caps = sorted(t["cap"] for t in load("encounter_design.json")["rules"]["tiers"].values())
    files = marine_files(pack)
    zones = [z for z in load("spawns.json")["marine_zones"] if z["id"] != "windward_sea"]
    assert len(zones) >= 6
    for z in zones:
        prev_hi = None
        for b in z["bands"]:
            lo, hi = b["level_band"]["minimum"], b["level_band"]["maximum"]
            assert hi in caps, "%s tops out at %d, not a gym cap %s" % (b["id"], hi, caps)
            assert hi <= 60 and lo < hi
            if prev_hi is not None:
                assert lo == prev_hi, "%s starts at %d, the band inside it ends at %d" % (b["id"], lo, prev_hi)
            prev_hi = hi
            for s in files[b["id"]]:
                if is_heart(s["id"], b["id"]):
                    continue
                a, c = (int(v) for v in s["level"].split("-"))
                assert lo <= a <= c <= hi, "%s: %s spawns %s outside the band %d-%d" % (b["id"], s["id"], s["level"], lo, hi)


def test_no_legendary_mythical_ultra_beast_paradox_or_dungeon_prize_spawns_in_a_sea(pack):
    # Without it a sea could carry a species a dungeon pays out or a one-of-a-kind (the owner's brief, 2026-10-12).
    try:
        species = BS.load_pack(BS.find_jar())[0]
    except BS.SimError as exc:
        pytest.skip("no Cobblemon 1.8 jar: the labels come from it (%s)" % exc)
    prizes = set()

    def walk(o):
        if isinstance(o, str):
            prizes.add(o)
        elif isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in ("rules", "why", "consumer"):
                    walk(v)
    roster = load("dungeon_prize_roster.json")
    walk(roster["dungeons"])
    walk(roster["world_proposals"])
    walk(roster["fallback_homes"])
    banned = {"legendary", "mythical", "ultra_beast", "paradox", "restricted"}
    bad = []
    new = [b["id"] for z in load("spawns.json")["marine_zones"] if z["id"] != "windward_sea" for b in z["bands"]]
    for band in new:
        for s in marine_files(pack)[band]:
            sp = str(s["pokemon"]).split()[0].lower()
            labels = set((species.get(sp) or {}).get("labels") or [])
            if labels & banned or sp in prizes:
                bad.append((band, sp, sorted(labels & banned)))
    assert not bad, bad[:5]


def test_the_new_seas_add_few_boxes_beside_everything_else_compiled(pack):
    # Without it a finer grid or a wider sea could quietly double the spawn conditions the server holds in memory (a
    # measured class histogram: ~0.4 GB of GroundedSpawningCondition plus maps). The lead's budget, 2026-10-12: the new
    # seas' boxes grow the total by under 25%.
    marine_new = rest = 0
    for p in pack.rglob("*.json"):
        spawns = json.loads(p.read_text(encoding="utf-8"))["spawns"]
        boxes = {box_of(s) for s in spawns if all(k in s["condition"] for k in ("minX", "maxX", "minZ", "maxZ"))}
        if p.parent.name == "marine" and not p.stem.startswith("windward"):
            marine_new += len(boxes)
        else:
            rest += len(boxes)
    assert marine_new > 300 and rest > 3000, (marine_new, rest)
    assert marine_new <= 0.25 * rest, "%d new marine boxes against %d others (%.1f%%)" % (marine_new, rest, 100.0 * marine_new / rest)


# ---------------------------------------------------------------- the engine, on a toy coast

REGIONS = {"subregions": [{"id": "toy", "polygons": [[[-900, -900], [-700, -900], [-700, -700], [-900, -700]]]}]}
ROUTES = {"routes": []}


def zone(zid, clips, grid, cuts, share=0.5):
    bands, prev = [], 0
    for i, c in enumerate(list(cuts) + [None]):
        bands.append({"id": "%s_%d" % (zid, i), "from_blocks": prev, "to_blocks": c})
        prev = c
    return {"id": zid, "clip_boxes": clips, "grid": grid, "max_land_share": share, "bands": bands}


def clip(x0, x1, z0, z1):
    return {"min_x": x0, "max_x": x1, "min_z": z0, "max_z": z1}


def test_two_zones_never_share_a_cell_even_where_their_clips_overlap():
    # Without the claim, an overlapping clip box doubled every weight over the overlap.
    spawns = {"marine_zones": [zone("a", [clip(-1024, -513, -1024, -513)], 32, [64]),
                               zone("b", [clip(-768, -513, -768, -513)], 32, [64])]}
    out = CS.marine_bands(spawns, REGIONS, ROUTES)
    a = [b for k, v in out.items() if k.startswith("a_") for b in v]
    b = [b for k, v in out.items() if k.startswith("b_") for b in v]
    assert a and not b, "the first zone takes every cell of the overlap; the second has nothing left (%d, %d)" % (len(a), len(b))
    assert not [(x, y) for i, x in enumerate(a) for y in a[i + 1:] if overlap(x, y)]


def test_a_coarse_grid_takes_the_same_water_in_far_fewer_boxes_and_clamps_the_coast_to_band_zero():
    # Without the clamp, a coarse cell holding land measures a negative distance (its centre is nearer land than half a
    # cell) and matches no band: the whole coast was silently dropped (found 2026-10-12, 2.1 of 58.9 km2 unserved).
    clips = [clip(-1024, -513, -1024, -513)]
    fine = CS.marine_bands({"marine_zones": [zone("z", clips, 32, [96, 256])]}, REGIONS, ROUTES)
    coarse = CS.marine_bands({"marine_zones": [zone("z", clips, 128, [96, 256], share=0.5)]}, REGIONS, ROUTES)
    nf = sum(len(v) for v in fine.values())
    nc = sum(len(v) for v in coarse.values())
    assert nc < nf, (nc, nf)
    assert coarse["z_0"], "the coast band (0-96 blocks) must hold the coarse cells that touch land"
    # the water hugging the toy island (its polygon is x and z -900..-700) is in the coast band, at every side
    for x, z in ((-680, -800), (-800, -680), (-920, -800), (-800, -920)):
        assert any(b[0] <= x <= b[1] and b[2] <= z <= b[3] for b in coarse["z_0"]), \
            "the water at (%d, %d), 20 blocks off the island, is in no coast-band box" % (x, z)
    area = lambda v: sum((b[1] - b[0] + 1) * (b[3] - b[2] + 1) for bs in v.values() for b in bs)  # noqa: E731
    assert area(coarse) >= 0.85 * area(fine), "the coarse grid must keep most of the water (%d vs %d)" % (area(coarse), area(fine))
    allc = [b for v in coarse.values() for b in v]
    assert not [(x, y) for i, x in enumerate(allc) for y in allc[i + 1:] if overlap(x, y)]
