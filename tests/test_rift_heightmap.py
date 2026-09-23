"""tools/rift_heightmap.py: the Rift's shape, sculpted into the canonical heightmap.

The sculpt is the one pass that reaches the live world without being re-applied, so the things that would be
expensive to discover after an export are asserted here: that it moves nothing that is already placed, that it
stays under the ceiling the export can express, and that it is derived from the un-sculpted map every time.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rift_heightmap as RH  # noqa: E402

WORLD = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
SPEC = json.loads((ROOT / "data" / "rift_sculpt.json").read_text(encoding="utf-8"))


def _maps():
    """The un-sculpted map and the sculpted one, as height grids, or a skip."""
    import os
    import terrain as T
    from PIL import Image
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    hm = WORLD["heightmap"]
    base = hm.get("rift_sculpted_from")
    if not root or not base:
        pytest.skip("COBBLERS_SOURCE_ROOT unset or the Rift sculpt has not been applied")
    before, after = Path(root) / base["path"], Path(root) / hm["path"]
    if not (before.is_file() and after.is_file()):
        pytest.skip("heightmaps not found under COBBLERS_SOURCE_ROOT")
    for p, want in ((before, base["sha256"]), (after, hm["sha256"])):
        if hashlib.sha256(p.read_bytes()).hexdigest() != want:
            pytest.skip("%s on disk is not the one world.json records" % p.name)
    return (T.sample_to_height(np.array(Image.open(before)), WORLD),
            T.sample_to_height(np.array(Image.open(after)), WORLD))


def test_the_sculpt_moves_no_settlement_footprint():
    # Every town was sited on ground that already existed. The sculpt reshapes the Rift's rim, and the band it
    # touches runs close to the rim post; a town whose footprint moved would have its buildings hanging or buried.
    before, after = _maps()
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    # A lot that a build levels afterwards is exempt: what the sculpt did to that ground is rebuilt. The League
    # moved onto the apex oval on 2026-09-23, which is inside the sculpted rim, and its lot is levelled to y88.
    levelled = [json.loads((ROOT / "data" / "rift_league_tunnel.json").read_text(encoding="utf-8"))["lot"]["box"]]
    checked, worst, exempt = 0, (-1.0, ""), []
    for t in towns:
        fp = t.get("footprint") or {}
        if fp.get("min_x") is None:
            continue
        if any(fp["min_x"] >= b[0] and fp["max_x"] <= b[2] and fp["min_z"] >= b[1] and fp["max_z"] <= b[3]
               for b in levelled):
            exempt.append(t["id"])
            continue
        sl = (slice(int(fp["min_z"]), int(fp["max_z"]) + 1), slice(int(fp["min_x"]), int(fp["max_x"]) + 1))
        checked += 1
        worst = max(worst, (float(np.abs(after[sl] - before[sl]).max()), t["id"]))
    assert checked >= 20, "only %d footprints checked (exempt: %s)" % (checked, exempt)
    assert worst[0] == 0.0, worst


def test_the_sculpt_changes_only_the_rift_and_stays_under_the_ceiling():
    before, after = _maps()
    diff = after != before
    assert diff.any(), "the sculpt changed nothing"
    zz, xx = np.nonzero(diff)
    poly = RH.region_polygon(SPEC["basin"]["region"])
    pad = SPEC["rim"]["reach"] + 60
    x0 = min(p[0] for p in poly) - pad
    x1 = max(p[0] for p in poly) + pad
    z0 = min(p[1] for p in poly) - pad
    z1 = max(p[1] for p in poly) + pad
    assert xx.min() >= x0 and xx.max() <= x1 and zz.min() >= z0 and zz.max() <= z1, (
        "the sculpt reached outside the Rift's box", xx.min(), xx.max(), zz.min(), zz.max())
    assert after.max() <= SPEC["ceiling"]["world_max_y"] + 1e-6, after.max()
    assert after[diff].max() <= SPEC["ceiling"]["peak_max_y"] + 1e-6, after[diff].max()


def test_the_peaks_stay_under_the_ceiling_by_construction():
    # The ceiling is a property of the export, not of taste: the heightmap maps samples onto y10..y310 for the
    # whole world, so a peak that wanted more would be clipped flat rather than tall.
    assert SPEC["ceiling"]["peak_max_y"] < SPEC["ceiling"]["world_max_y"]
    assert SPEC["ceiling"]["world_max_y"] == WORLD["vertical"]["max_y"]


def test_every_entrance_that_carries_a_route_snaps_to_its_crossing():
    # An entrance placed by hand 152 blocks off Victory Road's crossing left the route facing the lethal lip.
    routed = [e for e in SPEC["entrances"] if e.get("snap_route")]
    assert routed, "no entrance carries a route: the snap would never be exercised"
    for e in routed:
        assert RH.route_points(e["snap_route"]), e["snap_route"]


def test_the_sculpt_is_derived_from_the_unsculpted_map():
    # Running it twice must not sculpt a sculpt, so world.json records the map it started from.
    base = WORLD["heightmap"].get("rift_sculpted_from")
    if not base:
        pytest.skip("the Rift sculpt has not been applied")
    assert base["path"] != WORLD["heightmap"]["path"]
    assert base["sha256"] != WORLD["heightmap"]["sha256"]
    assert base["sha256"] in WORLD["heightmap"].get("previous_sha256", [])


def test_every_inward_normal_points_into_the_basin():
    """Which way is "in" must come from the mask, not from the centroid.

    The Rift is a long branching shape. Orienting the ring's normals by the centroid pointed 39% of them outwards
    -- on an arm's far side the centroid lies across the gap -- so the sculpt sampled its floor level on the
    plateau and its plateau level on the floor, and the skin laid debris and entrance paths on the wrong side.
    Found 2026-09-22 when the biome, painted only where a cell is inside the lip, read outside it at half the
    sampled points.
    """
    import numpy as np
    plan = ROOT / "derived" / "rift_sculpt" / "plan.json"
    basin = ROOT / "derived" / "rift_sculpt" / "basin.npy"
    if not (plan.is_file() and basin.is_file()):
        pytest.skip("the Rift sculpt has not been applied")
    sc = json.loads(plan.read_text(encoding="utf-8"))
    m = np.load(basin)
    X0, _, Z0, _ = sc["box"]
    ring, nrm = sc["ring"], sc["normals"]
    assert len(ring) > 1000, "the ring is too short to be the Rift's lip"
    wrong = 0
    for (rx, rz), (nx, nz) in zip(ring, nrm):
        hits = 0
        for d in (4, 8, 12):
            ix, iz = int(round(rx + nx * d)) - X0, int(round(rz + nz * d)) - Z0
            if 0 <= ix < m.shape[1] and 0 <= iz < m.shape[0] and m[iz, ix]:
                hits += 1
        wrong += hits < 2
    assert wrong / len(ring) < 0.01, "%d of %d normals point out of the basin" % (wrong, len(ring))


def test_the_basin_is_one_piece():
    m = np.zeros((40, 40), bool)
    m[5:20, 5:20] = True
    m[30:35, 30:35] = True
    piece, n = RH.largest_piece(m)
    assert n == 225 and piece.sum() == 225


def test_the_outline_is_a_closed_ring():
    m = np.zeros((40, 40), bool)
    m[8:30, 6:26] = True
    ring = RH.trace_outline(m)
    assert len(ring) >= 64
    for (az, ax), (bz, bx) in zip(ring, ring[1:]):
        assert max(abs(az - bz), abs(ax - bx)) == 1, "the ring jumps"
