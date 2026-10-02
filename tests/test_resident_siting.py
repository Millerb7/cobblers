"""Named residents (data/resident_encounters.json) obey the rules the encounter hearts obey.

The owner, 2026-10-02, reviewing #107: a resident is a big Pokemon at a fixed spot, so the hearts' rules hold for it
(docs/mechanics/ENCOUNTER_DESIGN.md section 10, data/encounter_design.json rules.hearts):

  - nothing big within clear_of_path_blocks (128) of a route path. Hornwall stood 59 blocks from Route 8's.
  - nothing above the place's ceiling: rules.hearts.next_cap of its sub-region's tier. Wiremother was L33 in a tier-2
    place whose ceiling is 30; a gate that keeps the fight shut until later does not excuse it.
  - its fight does not overlap a nest: at least the largest activated Habitat Block spawn_range plus the 28-block
    leash from every activated block. Six of ten stood about 24 blocks from one.

Every expectation is read from the data the rule lives in, never from data/resident_encounters.json itself.
"""
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
LEASH = 28          # the largest trigger/leash any resident brief names ("trigger 24, leash 28", "20/28")


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


RES = load("resident_encounters.json")["encounters"]
DESIGN = load("encounter_design.json")
HEARTS = DESIGN["rules"]["hearts"]
IDS = [e["id"] for e in RES]


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
    act = [b for b in load("habitat_blocks.json")["blocks"] if b.get("style") == "activated"]
    reach = max(b["activated"]["spawn_range"] for b in act) + LEASH
    d = min(math.hypot(b["position"]["x"] - x, b["position"]["z"] - z) for b in act)
    assert d >= reach, "%s is %.0f blocks from an activated Habitat Block; its fight needs %d" % (rid, d, reach)


CEILING_PENDING = {
    # L62 in long_isle_south (tier 8, ceiling 60). Gated on champion_cleared, the same argument the owner rejected
    # for Wiremother on 2026-10-02; found while writing this test, left for the owner rather than changed silently
    "split_bark": "L62 over long_isle_south's ceiling of 60: the owner's call (2026-10-02)",
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


@pytest.mark.parametrize("rid", IDS)
def test_a_residents_recorded_ground_is_the_heightmaps(rid):
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
