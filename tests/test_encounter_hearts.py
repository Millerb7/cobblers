"""Hearts and the mainline starters (docs/mechanics/ENCOUNTER_DESIGN.md sections 10 and 11), measured on the COMPILED pack.

Written by a test author, not by the session that designed or built the hearts. Nothing here reads or imports
tools/build_encounters.py or tools/encounter_audit.py, and nothing uses compile_spawns.heart_boxes: a heart is found
in the compiled files by its condition (test_encounter_design.split_heart), its area is measured from the compiled
boxes (and, for a summit, the canonical heightmap through tools/ground.py), and its distance to the path from the
compiled route boxes.

Independent sources: section 10's prose and its table of numbers (1/9, 11.2%, "cap + 5 ... and 62 at tier 9",
128 blocks), its list of where the 28 hearts are and their summit lines; section 11's table of the 27 families and
where each lives; section 2's caps and bands; data/mythical_starters.json `wild_traditional_starters` for which 27
species are the mainline starters (they left starters.json for the wild: NATIVE_STARTERS_COST.md sections 6a/7); the Cobblemon 1.8.0 jar for stages, types and the level each stage evolves at.

Section 10's four numbers were proposed and are confirmed by the owner (2026-10-02). They are tested AS WRITTEN and parsed
from the document (test_section_10s_numbers_are_still_the_documents), so they move only with it.

How a heart's spawn chance is computed: test_encounter_design's rule (bucket weight renormalised over the buckets
present in the context, then weight within the bucket), over the heart's whole table -- the base rows present at the
heart plus the heart's own rows -- with every level in a range equally likely (section 10 states the same
assumption). A base row whose `maxY` is under a summit's `minY` is not present at the summit.

Not covered, and it needs a running server: whether `minY` behaves as the jar's key suggests (section 10: "That
verifies the key, not its behaviour"), real spawn rates in the heart against the rest of the place, whether a player
actually sees the above-cap presences "first" and catches them "on a return", and whether a summit's area above its
line is where Pokemon can stand (caves and overhangs are not modelled: the heightmap's surface is).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools"))

import test_encounter_design as ED  # noqa: E402  the compiled pack, the placement and the chance rule
from test_encounter_design import jar, pack, world  # noqa: E402,F401  session fixtures

S10 = ED.flat(ED.section("10"))
S11_RAW = ED.section("11")
S2 = ED.section("2")
# The 27 mainline starters left the starter screen on 2026-10-02/03 (docs/mechanics/NATIVE_STARTERS_COST.md sections
# 6a and 7: the screen offers the five mythical lines; the 27 stay wild). starters.json therefore no longer names them;
# the record that carries the decision does, and tools/mythical_starters_audit.py holds that list equal to the
# upstream offer in base-pack/cobbleverse/config/cobblemon/starters.json.
WILD_STARTERS = json.loads((ROOT / "data" / "mythical_starters.json").read_text(encoding="utf-8"))[
    "wild_traditional_starters"]

# Section 2's bands: tier -> (low, high).
TIER_BAND = {int(t): (int(lo), int(hi)) for t, _c, lo, hi in
             re.findall(r"\|\s*(\d)\s*\|\s*(\d+)\s*\|\s*(\d+)-(\d+)\s*\|", S2)}

# Section 10's numbers, parsed from its table so they move only with the document.
_m = re.search(r"Most a heart may cover of its sub-region \| \*\*1/9 \(([\d.]+)\)\*\*", S10)
assert _m, "section 10 no longer proposes 1/9 as the most a heart may cover"
HEART_AREA_MAX = 1 / 9
_m = re.search(r"Most of a heart's spawn chance above the cap \| \*\*([\d.]+)%\*\*", S10)
assert _m, "section 10 no longer states the most of a heart's spawn chance above the cap"
ABOVE_CAP_MAX = float(_m.group(1)) / 100
_m = re.search(r"cap \+ (\d+) on tiers 1-8, and (\d+) at tier 9", S10)
assert _m, "section 10 no longer states how far above the cap a presence may go"
PRESENCE_STEP, PRESENCE_TOP_9 = int(_m.group(1)), int(_m.group(2))
_m = re.search(r"No heart cell within (\d+) blocks of a route corridor box", S10)
assert _m, "section 10 no longer states the near-path distance"
NEAR_PATH = int(_m.group(1))
_m = re.search(r"Where the hearts are \((\d+)\)", S10)
assert _m, "section 10 no longer counts its hearts"
HEART_COUNT = int(_m.group(1))

# Section 10, "Where the hearts are": each place it names, as the sub-region file it is. Merian's cirque is named in
# the paragraph on the three focal points that belong to the path ("the cirque's interior away from Route 4").
DOC_HEARTS = {
    "Frostpeak": "frostpeak", "Tri Peaks": "the_tri_peaks", "Mt Clay": "mt_clay", "Crags": "the_crags",
    "east cones": "east_cones", "Mt Vessu": "mt_vessu", "Shrew Lake": "shrew_lake_shores",
    "Arrow Lake": "arrow_lake_shores", "Lake Tilpey's open water": "tilpey_waters",
    "Ravine Head Tarn": "peak_pond_hollow", "Glacial Tear": "lower_trough", "Marshy Marsh": "marshy_marsh",
    "Great Crater": "great_crater", "dark Wedge": ("wedge_north", "wedge_south"),
    "Northgate's old growth": "northgate_west",
    "four **Rift** tables": ("rift_trunk", "rift_south_east_arm", "rift_south_west_arm", "rift_west_spur"),
    "Fungal North": "fungal_north", "Pine isles": ("north_pine_isle", "south_pine_isle"),
    "Sunset west": "sunset_west", "Long Isle": "long_isle_middle", "south-west fields": "south_west_fields",
    "Lake Viltri's hollow": "lake_viltri_hollow", "cirque's interior": "merian_cirque",
}
# Section 10's summit lines: "**Frostpeak** (y180, ...", "the **Tri Peaks** (y195)".
SUMMIT_LINE = {DOC_HEARTS[name]: int(y) for name, y in
               re.findall(r"\*\*(Frostpeak|Tri Peaks|Mt Clay|Crags|east cones)\*\* \(y(\d+)", S10)}


def doc_hearts():
    out = set()
    for name, ids in DOC_HEARTS.items():
        assert name in S10, "section 10 no longer names %r" % name
        out.update((ids,) if isinstance(ids, str) else ids)
    return out


# ------------------------------------------------------------------ geometry

def mask_of(box_set):
    """(x0, z0, bool mask[z, x]) covering a set of inclusive boxes."""
    bs = np.array(sorted(box_set), dtype=np.int64).reshape(-1, 4)
    if len(bs) == 0:
        return 0, 0, np.zeros((0, 0), dtype=bool)
    x0, z0 = int(bs[:, 0].min()), int(bs[:, 1].min())
    m = np.zeros((int(bs[:, 3].max()) - z0 + 1, int(bs[:, 2].max()) - x0 + 1), dtype=bool)
    for a, b, c, d in bs:
        m[b - z0:d - z0 + 1, a - x0:c - x0 + 1] = True
    return x0, z0, m


def boxes_of(spawns):
    return {ED.box_of(e) for e in spawns}


def heart_min_y(t):
    ys = {(e.get("condition") or {}).get("minY") for e in t["heart"]}
    assert len(ys) == 1, "one heart, one line: %s" % ys
    return ys.pop()


def hearts(world):
    return {k: t for k, t in world["subs"].items() if t["heart"]}


def next_cap(tier):
    return PRESENCE_TOP_9 if tier == 9 else ED.TIER_CAP[tier] + PRESENCE_STEP


def base_in_heart(t):
    """The base details present in the heart: all of them, less a base row a summit's line puts below its maxY."""
    y = heart_min_y(t)
    return [e for e in t["base"] if y is None or (e.get("condition") or {}).get("maxY", 10 ** 6) >= y]


def heart_table_details(t):
    """The details present in the heart: the heart's own and the base's present there."""
    return base_in_heart(t) + t["heart"]


def row_chances(rows, context):
    """[(row, chance)] within one context, by test_encounter_design's rule, one entry per distinct row."""
    rs = [r for r in rows if r[2] in ED.CONTEXTS[context] and r[3] > 0]
    by_bucket = {}
    for r in rs:
        by_bucket.setdefault(r[1], []).append(r)
    total = sum(ED.BUCKET_WEIGHT[b] for b in by_bucket)
    out = []
    for b, members in by_bucket.items():
        w = sum(r[3] for r in members)
        out.extend((r, ED.BUCKET_WEIGHT[b] / total * r[3] / w) for r in members)
    return out


def above(row, cap):
    """The share of a row's levels above the cap, every level equally likely."""
    lo, hi = row[4], row[5]
    return max(0, hi - max(lo, cap + 1) + 1) / (hi - lo + 1)


@pytest.fixture(scope="session")
def ground():
    import ground as G
    import terrain
    try:
        return G.load()
    except terrain.TerrainUnavailable as exc:  # the heightmap lives outside the repo (COBBLERS_SOURCE_ROOT)
        pytest.skip("no canonical heightmap (%s): a summit heart's area needs it; a skip is not a pass" % exc)


# ------------------------------------------------------------------ the inputs agree with their sources

def test_section_10s_numbers_are_still_the_documents():
    # Without it a threshold here could be edited until the data passed and nothing would say it left the doc.
    assert "are confirmed by the owner (2026-10-02)" in S10   # confirmed 2026-10-02; tested as written
    assert abs(float(re.search(r"\*\*1/9 \(([\d.]+)\)\*\*", S10).group(1)) - HEART_AREA_MAX) < 0.001
    assert abs(ABOVE_CAP_MAX - 0.112) < 1e-9 and (PRESENCE_STEP, PRESENCE_TOP_9) == (5, 62) and NEAR_PATH == 128
    # the 11.2% is Cobbleverse's uncommon and rare draw, as section 10 derives it: check the arithmetic still holds
    w = ED.BUCKET_WEIGHT
    assert abs((w["uncommon"] + w["rare"]) / (w["common"] + w["uncommon"] + w["rare"]) - ABOVE_CAP_MAX) < 0.0005
    assert HEART_COUNT == 28 and len(doc_hearts()) == HEART_COUNT
    assert SUMMIT_LINE == {"frostpeak": 180, "the_tri_peaks": 195, "mt_clay": 212, "the_crags": 171,
                           "east_cones": 228}, SUMMIT_LINE
    assert "ids `<sub>_h<n>_<species>`" in S10


def test_the_condition_split_agrees_with_the_documented_heart_ids(world):
    # Without it the split every heart test stands on could misfile a base spawn as heart (or the reverse) and the
    # targets would be measured on the wrong rows. Two independent readings: the condition and section 10's ids.
    wrong = {}
    for k, t in world["subs"].items():
        pat = re.compile(r"^%s_h\d+_" % re.escape(k))
        bad = [e["id"] for e in t["heart"] if not pat.match(e["id"])] + [e["id"] for e in t["base"] if pat.match(e["id"])]
        if bad:
            wrong[k] = bad[:3]
    assert not wrong, wrong


def test_the_hearts_are_the_places_section_10_names(world):
    # Without it a heart could appear somewhere the document keeps wholly catchable (Pallet's meadows, the first
    # leg's path) or vanish from a place it names.
    have = set(hearts(world))
    assert have == doc_hearts(), "compiled, not in the doc: %s; in the doc, not compiled: %s" % (
        sorted(have - doc_hearts()), sorted(doc_hearts() - have))


def test_a_summit_heart_is_cut_at_the_documents_line(world):
    # Without it a summit's line could drift down the mountain (more of the place above the cap) unseen; section 9
    # also says only a summit heart's entries carry minY.
    lines = {k: heart_min_y(t) for k, t in hearts(world).items() if heart_min_y(t) is not None}
    assert lines == SUMMIT_LINE, lines
    stray = sorted(k for k, t in world["subs"].items() for e in t["base"] if "minY" in (e.get("condition") or {}))
    assert not stray, "base rows carrying minY: %s" % stray


# ------------------------------------------------------------------ section 10: the path is always catchable

def base_signatures(t):
    if "_base_sigs" not in t:
        t["_base_sigs"] = {ED.detail_signature(e) for e in t["base"]}
    return t["_base_sigs"]


def test_no_heart_spawn_compiles_into_a_route_corridor(world):
    # Without it a route could carry a heart's above-cap presences or its bigger stages, and the road a new player
    # walks would stop being catchable (section 10, "The path is always catchable").
    subs = sorted(world["subs"], key=len, reverse=True)
    leaked, unread = {}, 0
    for r, spawns in world["route_details"].items():
        for e in spawns:
            if "minY" in (e.get("condition") or {}):
                leaked.setdefault(r, set()).add(e["id"])
                continue
            sub = next((s for s in subs if "_%s_" % s in e["id"]), None)
            if sub is None:
                unread += 1
                continue
            # a corridor carries its sub-region's base entries as they are (species, bucket, level, weight, every
            # condition but the box), so a detail that is not one of them came from somewhere else -- the heart
            if ED.detail_signature(e) not in base_signatures(world["subs"][sub]):
                leaked.setdefault(r, set()).add(e["id"])
    assert not leaked, {k: sorted(v)[:5] for k, v in leaked.items()}
    total = sum(len(v) for v in world["route_details"].values())
    assert unread < total, "no route spawn names its sub-region; the check read nothing"


# ------------------------------------------------------------------ section 10: most of a place is catchable

def test_a_heart_covers_at_most_a_ninth_of_its_place(world, ground):
    # Without it a heart could grow until above-cap Pokemon are the texture of the place rather than its exception
    # (section 10's first number, 1/9 of the compiled area; proposed, tested as written).
    over, shares = {}, {}
    for k, t in hearts(world).items():
        _bx, _bz, bm = mask_of(boxes_of(t["base"]))
        x0, z0, hm = mask_of(boxes_of(t["heart"]))
        if not bm.any():
            over[k] = "no base area at all"
            continue
        area = hm
        y = heart_min_y(t)
        if y is not None:
            g = ground.box(x0, z0, x0 + hm.shape[1] - 1, z0 + hm.shape[0] - 1)
            area = hm & (g >= y)
        share = area.sum() / bm.sum()
        shares[k] = round(float(share), 4)
        if share > HEART_AREA_MAX + 1e-9:
            over[k] = shares[k]
    assert not over, "heart: share of its place's compiled area over 1/9: %s" % over
    assert min(shares.values()) > 0, "a heart with no area: %s" % shares


def test_above_cap_spawns_are_at_most_the_documents_share_of_a_heart(world):
    # Without it a heart could be mostly uncatchable, so a new player meets a wall instead of pockets (section 10's
    # second number, 11.2%; proposed, tested as written).
    over, seen = {}, 0
    for k, t in hearts(world).items():
        cap = ED.TIER_CAP[t["tier"]]
        rows = ED.rows_of(heart_table_details(t))
        for ctx in ED.CONTEXTS:
            share = sum(p * above(r, cap) for r, p in row_chances(rows, ctx))
            if share > 0:
                seen += 1
            if share > ABOVE_CAP_MAX + 1e-9:
                over["%s/%s" % (k, ctx)] = round(share, 4)
    assert not over, "heart context: chance above the cap %s" % over
    assert seen, "no heart context holds anything above the cap; the check measured nothing"


def test_an_above_cap_spawn_is_never_in_the_common_bucket(world):
    # Without it the 11.2% ceiling's premise ("a presence is never common") fails, and a heart's above-cap Pokemon
    # would be what a player meets every few steps (section 10).
    common = {k: sorted({r[0] for r in t["heart_rows"] if r[5] > ED.TIER_CAP[t["tier"]] and r[1] == "common"})
              for k, t in hearts(world).items()}
    common = {k: v for k, v in common.items() if v}
    assert not common, common


def test_a_presence_goes_no_higher_than_the_next_legs_cap(world):
    # Without it a heart could hold Pokemon a player cannot catch on the next leg either, so "caught on a return"
    # stops being true (section 10's third number: cap + 5 on tiers 1-8, 62 at tier 9; proposed, as written).
    over = {}
    for k, t in hearts(world).items():
        top = max(r[5] for r in t["heart_rows"])
        if top > next_cap(t["tier"]):
            over[k] = (t["tier"], next_cap(t["tier"]), top)
    assert not over, "heart: (tier, next leg's cap, highest level) %s" % over


def test_no_heart_cell_is_within_the_near_path_distance_of_a_corridor(world):
    # Without it a heart could sit against the road, and the band beside the path -- where a new player finds
    # catchable pockets -- would hold above-cap Pokemon (section 10's fourth number, 128 blocks, Chebyshev).
    near = {}
    for k, t in hearts(world).items():
        hb = np.array(sorted(boxes_of(t["heart"])), dtype=np.int64)
        for r, rb in world["route_boxes"].items():
            g = ED.box_gap(hb, rb)
            if g is not None and g <= NEAR_PATH:
                near["%s~%s" % (k, r)] = g
    assert not near, "heart~route: gap in blocks %s" % near


def test_a_heart_is_mixed_with_its_catchable_base(world):
    # Without it a heart could be walled off -- its place's base rows absent where the heart is -- so at a summit or
    # a lake's centre a player would meet only the big presences (section 10, "A heart is mixed, not walled").
    walled = {}
    for k, t in hearts(world).items():
        bx, bz, bm = mask_of(boxes_of(t["base"]))
        hx, hz, hm = mask_of(boxes_of(t["heart"]))
        z, x = np.nonzero(hm)
        x, z = x + hx - bx, z + hz - bz
        inside = (x >= 0) & (z >= 0) & (x < bm.shape[1]) & (z < bm.shape[0])
        covered = np.zeros(len(x), dtype=bool)
        covered[inside] = bm[z[inside], x[inside]]
        if not covered.all():
            walled[k] = "%d heart columns outside every base box" % int((~covered).sum())
            continue
        cap = ED.TIER_CAP[t["tier"]]
        base_present = ED.rows_of(base_in_heart(t))
        for ctx in ED.CONTEXTS:
            if not any(r[2] in ED.CONTEXTS[ctx] for r in t["heart_rows"]):
                continue
            catchable_common = [r for r in base_present if r[2] in ED.CONTEXTS[ctx] and r[1] == "common" and r[5] <= cap]
            if not catchable_common:
                walled["%s/%s" % (k, ctx)] = "no catchable common-bucket base spawn present in the heart"
    assert not walled, walled


def test_every_off_path_find_is_in_the_base_table(world, jar):
    # Without it a heart's uncommon presence could stand in for an off-path place's find, and the find -- section
    # 6's reason to leave the path -- would only exist in a ninth of the place (section 10: "A heart holds no find").
    on = ED.on_path_families(world, jar)
    missing = []
    for k, t in ED.off_path_tables(world).items():
        finds = {jar.root(r[0]) for r in t["base_rows"] if r[1] in ("rare", "uncommon")
                 and jar.root(r[0]) not in on and jar.final_bst(jar.root(r[0])) >= ED.FIND_BST_MIN}
        if not finds:
            missing.append(k)
    assert not missing, "off-path tables whose only find is in the heart, or none: %s" % missing


# ------------------------------------------------------------------ section 11: the mainline starters

def mainline_starters():
    """The 27 mainline starters, by region, from data/mythical_starters.json `wild_traditional_starters` (the Hisui
    set was forms of three of them, not families, and the record drops it the same way)."""
    regions = WILD_STARTERS["regions"]
    assert len(regions) == 9, sorted(regions)
    out = [ED.BS.key(p) for names in regions.values() for p in names]
    assert len(out) == 27 == len(set(out)), out
    return out


# Section 11's table names, as the sub-region file each is.
S11_TABLES = {
    "Pallet's meadows": "pallet_meadows", "Route 1 forest": "route1_maze_forest", "Viltri plateau": "viltri_plateau",
    "west shore": "west_shore", "Lake Viltri's hollow": "lake_viltri_hollow",
    "Viltri's Path valley": "viltris_path_valley", "foothill woods": "foothill_woods",
    "north-west coast": "north_west_coast", "Arrow Lake": "arrow_lake_shores", "north shore downs": "north_shore_downs",
    "north-east downs": "north_east_downs", "Peak Pond Hollow": "peak_pond_hollow",
    "glacier-foot fields": "glacier_foot_fields", "Marshy Marsh": "marshy_marsh", "Sunset west": "sunset_west",
    "Lower Trough": "lower_trough", "Tilpey's north shore": "tilpey_north_shore",
    "Tilpey's east shore": "tilpey_east_shore", "north Wedge": "wedge_north",
    "Northgate's old growth": "northgate_west", "south Pine isle": "south_pine_isle",
    "Tilpey's south shore": "tilpey_south_shore", "crater rim": "crater_rim_north_west", "Rift's foot": "rift_foot",
    "Great Crater": "great_crater",
}


def section_11_plan():
    """family (base species key) -> {leg, table, notes}, parsed from section 11's table."""
    plan = {}
    for leg, cell in re.findall(r"^\|\s*(\d)\s*\|\s*(.+?)\s*\|\s*$", S11_RAW, re.M):
        for fam, rest in re.findall(r"([A-Z][a-z]+): (.+?)(?=\s+[A-Z][a-z]+: |$)", cell):
            m = re.match(r"^(?:the )?(.+?)\s*(?:\((.*)\))?\.?$", rest.strip())
            name, notes = m.group(1).strip().rstrip("."), (m.group(2) or "")
            assert name in S11_TABLES, "section 11 names a table this test does not map: %r" % name
            plan[ED.BS.key(fam)] = {"leg": int(leg), "table": S11_TABLES[name], "name": name, "notes": notes}
    return plan


# Section 5's water table: place -> the families of its water half.
S5_WATER = {place.strip(): flat_fams for place, flat_fams in
            re.findall(r"^\|\s*([A-Z][^|]*?)\s*\|\s*[\d-]+\s*\|\s*([^|]*?)\s*\|\s*$", ED.section("5"), re.M)}


def section_5_water_family(fam, p):
    """True when section 5 names the family in the water half of the very place section 11 puts it."""
    fams = S5_WATER.get(p["name"])
    return bool(fams) and re.search(r"\b%s\b" % re.escape(fam), fams, re.I) is not None


def family_rows(t, members, key="rows"):
    return [r for r in t[key] if r[0] in members]


def test_section_11_places_all_27_mainline_starters(jar):
    # Without it a starter family could drop out of the plan, or the plan could name one that is not a mainline
    # starter, and the owner's "starters from every region" would be half done.
    plan = section_11_plan()
    assert sorted(plan) == sorted(mainline_starters()), (sorted(set(mainline_starters()) - set(plan)),
                                                         sorted(set(plan) - set(mainline_starters())))
    assert all(jar.root(f) == f for f in plan), "a section 11 family is not named by its first stage"


def test_every_starter_family_spawns_in_its_table_on_its_leg(world, jar):
    # Without it a starter could be planned but never compiled, or sit on another leg than section 11 says
    # (Grass on the first three legs, Fire on the Grass gym's leg).
    wrong = {}
    for fam, p in section_11_plan().items():
        t = world["subs"][p["table"]]
        if not family_rows(t, jar.members(fam)):
            wrong[fam] = (p["table"], "absent")
        elif t["tier"] != p["leg"]:
            wrong[fam] = (p["table"], "tier %d, section 11 says leg %d" % (t["tier"], p["leg"]))
    assert not wrong, wrong


def test_a_starter_is_uncommon_on_the_path_and_a_find_off_it(world, jar):
    # Without it a starter could be a common sight on the road, or a "find" a player meets on the path (section 11:
    # "an uncommon family on or near the path, a find off it"; finds exclusive and off the corridors, section 6).
    wrong = {}
    on_fams = ED.on_path_families(world, jar)
    route_species = {ED.species_of(e) for spawns in world["route_details"].values() for e in spawns}
    for fam, p in section_11_plan().items():
        t, members = world["subs"][p["table"]], jar.members(fam)
        buckets = {r[1] for r in family_rows(t, members, "base_rows")}
        if "find" in p["notes"]:
            if t["on_path"]:
                wrong[fam] = "a find in an on-path table"
            elif buckets != {"rare"}:
                wrong[fam] = "find in buckets %s" % sorted(buckets)
            elif fam in on_fams or members & route_species:
                wrong[fam] = "a find also met on the path"
        elif section_5_water_family(fam, p):
            continue   # section 5 gave it this table's water half first; its bucket is section 4's role there
        elif t["on_path"] and buckets != {"uncommon"}:
            wrong[fam] = "on the path in buckets %s" % sorted(buckets)
        elif not t["on_path"]:
            wrong[fam] = "off the path but not a find"
    assert not wrong, wrong


def test_no_starter_section_11_added_is_a_water_tables_family(world, jar):
    # Without it a Water starter could be fished up, which section 11 rules out ("standing on land, so no starter is
    # any water table's family"). Totodile and Piplup are exempt only because section 5 itself names them as their
    # tables' water families (Marshy Marsh, the Lower Trough), and section 11 marks both "already": the document
    # disagrees with itself there, and the test follows the section that assigns the table.
    plan = section_11_plan()
    members = {m: fam for fam in plan for m in jar.members(fam)}
    wet = set()
    tables = [(k, t["base"] + t["heart"]) for k, t in world["subs"].items()] + list(world["route_details"].items())
    for k, spawns in tables:
        for e in spawns:
            s = ED.species_of(e)
            if s in members and e.get("spawnablePositionType", "grounded") != "grounded" \
                    and not (section_5_water_family(members[s], plan[members[s]])
                             and (k == plan[members[s]]["table"] or "_%s_" % plan[members[s]]["table"] in e["id"])):
                wet.add((k, s))
    assert not wet, "starters in a water context: %s" % sorted(wet)


def test_starter_levels_keep_their_tables_band(world, jar):
    # Without it a starter could spawn outside its leg's band -- uncatchable in the base, or past the next cap in a
    # heart (section 2's bands; section 10's presence limit).
    members = {m for fam in section_11_plan() for m in jar.members(fam)}
    wrong = {}
    for k, t in world["subs"].items():
        lo_band, hi_band = TIER_BAND[t["tier"]]
        for r in t["base_rows"]:
            if r[0] in members and (r[4] < lo_band or r[5] > hi_band):
                wrong["%s/%s" % (k, r[0])] = ("base", r[4], r[5], (lo_band, hi_band))
        for r in t["heart_rows"]:
            if r[0] in members and (r[4] < lo_band or r[5] > next_cap(t["tier"])):
                wrong["%s/%s/heart" % (k, r[0])] = ("heart", r[4], r[5], (lo_band, next_cap(t["tier"])))
    assert not wrong, wrong


def evolves_at(dex, stage):
    """The level at which a stage's parent evolves into it, when the evolution is by level; else None."""
    parent = dex.parent.get(stage)
    for ev in (dex.sp[parent].get("evolutions") or []) if parent else []:
        if ED.BS.key(str(ev.get("result") or "").split()[0]) == stage:
            lv = [q.get("minLevel") for q in ev.get("requirements") or [] if q.get("variant") == "level"]
            return lv[0] if lv else None
    return None


def test_no_starter_stage_spawns_below_the_level_it_evolves_at(world, jar):
    # Without it a Charizard could spawn at 20 or an Ivysaur at 10: stages would stop following the levels (section 3,
    # which section 11 applies: "maturity rising with the tier").
    members = {m for fam in section_11_plan() for m in jar.members(fam)}
    early = {}
    tables = list(world["subs"].items()) + [(r, {"rows": rows}) for r, rows in world["route_rows"].items()]
    for k, t in tables:
        for r in t["rows"]:
            at = evolves_at(jar, r[0]) if r[0] in members else None
            if at is not None and r[4] < at:
                early["%s/%s" % (k, r[0])] = (r[4], at)
    assert not early, "table/stage: (lowest level, evolves at) %s" % early


def test_starter_types_sit_where_section_11_puts_them(world, jar):
    # Without it the theme section 11 gives the starters could be lost: Grass starters off the first three legs, the
    # Fire pair off the Grass gym's leg, a Water starter away from water. (A table's 70% theme share, starters
    # included, is target 6 in test_encounter_design.py; section 7 sets no per-species rule, so none is invented here.)
    s11 = ED.flat(S11_RAW)
    plan = section_11_plan()
    m = re.search(r"Grass on the first three legs \(([^)]*)\), Fire on the Grass gym's leg \(([^)]*)\)", s11)
    assert m, "section 11 no longer says which starters go where by type"
    grass_leg = next(leg for leg, g in ED.GYM_TYPE.items() if g == "grass")
    wrong = {}
    for name in m.group(1).split(","):
        fam = ED.BS.key(name.strip())
        if "grass" not in jar.types(fam) or world["subs"][plan[fam]["table"]]["tier"] > 3:
            wrong[fam] = ("grass, legs 1-3", sorted(jar.types(fam)), world["subs"][plan[fam]["table"]]["tier"])
    for name in m.group(2).split(","):
        fam = ED.BS.key(name.strip())
        if "fire" not in jar.types(fam) or world["subs"][plan[fam]["table"]]["tier"] != grass_leg:
            wrong[fam] = ("fire, leg %d" % grass_leg, sorted(jar.types(fam)), world["subs"][plan[fam]["table"]]["tier"])
    assert not wrong, wrong
    # Water starters on shores: every detail of a Water starter's family needs water nearby, unless section 5 makes
    # the family that table's water half (see section_5_water_family).
    dry = set()
    for fam, p in plan.items():
        if "water" not in jar.types(fam) or section_5_water_family(fam, p):
            continue
        for k, t in world["subs"].items():
            for e in t["base"] + t["heart"]:
                if ED.species_of(e) in jar.members(fam) and \
                        "minecraft:water" not in ((e.get("condition") or {}).get("neededNearbyBlocks") or []):
                    dry.add((k, ED.species_of(e)))
        for r, spawns in world["route_details"].items():
            for e in spawns:
                if ED.species_of(e) in jar.members(fam) and \
                        "minecraft:water" not in ((e.get("condition") or {}).get("neededNearbyBlocks") or []):
                    dry.add((r, ED.species_of(e)))
    assert not dry, "Water starters spawning away from water: %s" % sorted(dry)


def test_the_final_forms_section_11_puts_in_a_heart_are_there(world, jar):
    # Without it the owner's named heart forms (Bayleef, Samurott, Swampert, Incineroar, Feraligatr, Empoleon,
    # Rillaboom, Decidueye, Charizard) could be missing from the hearts section 11 promises them.
    named = re.findall(r"(\w+): [^|:]*?\b([A-Z][a-z]+)(?: common)? in (?:the|its)(?: tarn)? heart", S11_RAW)
    plan = section_11_plan()
    assert len(named) >= 9, named
    missing = {}
    for fam, form in named:
        t = world["subs"][plan[ED.BS.key(fam)]["table"]]
        if ED.BS.key(form) not in {r[0] for r in t["heart_rows"]}:
            missing[form] = plan[ED.BS.key(fam)]["table"]
    assert not missing, "named heart form: table %s" % missing
