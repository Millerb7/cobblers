"""Named residents (data/resident_encounters.json) obey the rules the encounter hearts obey.

The owner, 2026-10-02, reviewing #107: a resident is a big Pokemon at a fixed spot, so the hearts' rules hold for it
(docs/mechanics/ENCOUNTER_DESIGN.md section 10, data/encounter_design.json rules.hearts):

  - nothing big within clear_of_path_blocks (128) of a route path. Hornwall stood 59 blocks from Route 8's.
  - nothing above the place's ceiling: rules.hearts.next_cap of its sub-region's tier. Wiremother was L33 in a tier-2
    place whose ceiling is 30; a gate that keeps the fight shut until later does not excuse it.
  - its fight does not overlap a nest: from every activated Habitat Block, at least that block's spawn_range plus
    the resident's own leash. Six of ten stood about 24 blocks from one.

Every expectation is read from the data the rule lives in, never from data/resident_encounters.json itself.

The southern residents' two Pokemon (data/southern_residents.json, 2026-10-03: Grandmother Cap, Ash) are held to the
same three rules, at the site centre plus the record's `at`, with the record's leash. So are the northern residents'
(data/northern_residents.json, 2026-10-03), read the same way, and the far south's three (data/far_south.json,
2026-10-04: Greymane, the Fifth Chimney, the Old Watcher), whose records have the same shape.
"""
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
LEASH = 28          # a resident with no built leash: the largest any brief names ("trigger 24, leash 28", "20/28")


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def _southern(name="southern_residents.json"):
    """data/southern_residents.json's named Pokemon (2026-10-03) in this file's shape: the anchor's x/z is the site's
    centre plus the record's `at`, read from the record's geometry, not from its recorded anchor. The northern
    residents' file (data/northern_residents.json) has the same shape and is read by the same function."""
    out = []
    for r in load(name)["residents"]:
        pk = r.get("pokemon")
        if pk:
            cx, cz = r["site"]["centre"]
            out.append({"id": pk["id"], "level": pk["level"], "build": {"leash": pk["leash"]},
                        "location": {"x": cx + pk["at"][0], "z": cz + pk["at"][1]}})
    return out


RES = load("resident_encounters.json")["encounters"] + _southern() + _southern("northern_residents.json") \
    + _southern("far_south.json") + _southern("rookery.json")
    + _southern("far_south.json") + _southern("long_count.json")
DESIGN = load("encounter_design.json")
HEARTS = DESIGN["rules"]["hearts"]
IDS = [e["id"] for e in RES]
SOUTH_IDS = {e["id"] for e in _southern()} | {e["id"] for e in _southern("northern_residents.json")} \
    | {e["id"] for e in _southern("far_south.json")} | {e["id"] for e in _southern("rookery.json")}
    | {e["id"] for e in _southern("far_south.json")} | {e["id"] for e in _southern("long_count.json")}
FAR_SOUTH = {"greymane", "fifth_chimney", "old_watcher"}


# Without it the far south's file could lose a resident (or this file stop reading it) and the three rules below would
# silently stop holding those Pokemon.
def test_the_far_south_residents_are_held_to_the_rules():
    assert FAR_SOUTH <= set(IDS), sorted(FAR_SOUTH - set(IDS))


# The same for the Long Count's Grotle (data/long_count.json, 2026-10-09, gym 2).
def test_the_long_counts_grotle_is_held_to_the_rules():
    assert "old_pace" in set(IDS), "data/long_count.json's Grotle is not read by this file's three rules"


def _sub_of(x, z):
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from subregion_boxes import point_in_polygon
    return [s["id"] for s in load("regions.json")["subregions"]
            if any(point_in_polygon(x, z, p) for p in s.get("polygons") or [])]


def _at(e):
    return e["location"]["x"], e["location"]["z"]


@pytest.mark.parametrize("rid", IDS)
def test_a_resident_stands_clear_of_every_route_path(rid):
    e = next(r for r in RES if r["id"] == rid)
    x, z = _at(e)
    pts = np.array([p for pl in load("route_paths.json")["paths"].values() for p in pl], float)
    d = float(np.min(np.hypot(pts[:, 0] - x, pts[:, 1] - z)))
    assert d >= HEARTS["clear_of_path_blocks"], "%s is %.0f blocks from a route path" % (rid, d)


@pytest.mark.parametrize("rid", IDS)
def test_a_residents_fight_does_not_overlap_a_nest(rid):
    e = next(r for r in RES if r["id"] == rid)
    x, z = _at(e)
    leash = (e.get("build") or {}).get("leash") or LEASH
    act = [b for b in load("habitat_blocks.json")["blocks"] if b.get("style") == "activated"]
    near = [(math.hypot(b["position"]["x"] - x, b["position"]["z"] - z), b["activated"]["spawn_range"] + leash, b["id"])
            for b in act]
    bad = sorted(n for n in near if n[0] < n[1])
    assert not bad, "%s's %d-block leash overlaps an activated Habitat Block's spawns: %s" % (
        rid, leash, ["%s at %.0f, needs %d" % (i, d, need) for d, need, i in bad[:3]])


CEILING_PENDING = {
    # L63 in long_isle_south (tier 8, ceiling 60), BY DECISION: the owner, 2026-10-02, raised it from Codex's 62 so
    # it sits above Champion Blue's ace and cannot be caught between the Elite Four and the Champion
    # (data/resident_encounters.json split_bark build.level_why). Strict, so a level brought back under 61 is noticed
    "split_bark": "L63 over long_isle_south's ceiling of 60: the owner's decision (2026-10-02), above the Champion's ace",
}


@pytest.mark.parametrize("rid", [pytest.param(i, marks=pytest.mark.xfail(strict=True, reason=CEILING_PENDING[i]))
                                 if i in CEILING_PENDING else i for i in IDS])
def test_a_residents_level_is_within_its_places_ceiling(rid):
    e = next(r for r in RES if r["id"] == rid)
    subs = [s for s in _sub_of(*_at(e)) if s in DESIGN["tables"]]
    if not subs:
        pytest.skip("%s stands in no sub-region with a table (a river): no tier to read a ceiling from" % rid)
    tier = DESIGN["tables"][subs[0]]["tier"]
    ceiling = HEARTS["next_cap"][str(tier)]
    assert e["level"] <= ceiling, "%s is L%d in %s, tier %s, ceiling %d" % (rid, e["level"], subs[0], tier, ceiling)


@pytest.mark.parametrize("rid", [i for i in IDS if i not in SOUTH_IDS])
def test_a_residents_recorded_ground_is_the_heightmaps(rid):
    # the southern residents' anchors are re-derived from the heightmap by tools/southern_residents_audit.py; the
    # northern residents' by tools/northern_residents_audit.py (tests/test_northern_residents_audit.py)
    if not os.environ.get("COBBLERS_SOURCE_ROOT"):
        pytest.skip("NOT_EXECUTED: COBBLERS_SOURCE_ROOT is not set: the canonical heightmap is outside the repo")
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import ground
    e = next(r for r in RES if r["id"] == rid)
    x, z = _at(e)
    got = float(ground.load()(x, z))
    loc = e["location"]
    rec = loc.get("measured_surface_or_bed_y", loc.get("measured_bed_y"))   # River Grip records its bed
    assert rec is not None and abs(got - rec) <= 1, (rid, got, rec)
