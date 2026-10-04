"""Every building keep-clear is computed where the building's placer actually puts it.

tools/place_donor.py places a pack donor with `/place template <id> <position> <rotation> <mirror>`, which turns the
template ABOUT that position; tools/place_town.py offsets a town building so its position is the turned footprint's
minimum corner. town_dressing.building_footprints (plaza_centre, ambient, shrines), markets.donor_footprints and
markets_audit.building_footprints all once treated a pack donor's position as its minimum corner, so the 16 turned
donors were kept clear on the wrong side of their own origin (found 2026-10-04: Brock's gym, turned 180, overlapped
its computed footprint by one column of 648).

The expectation here is not place_donor's: it is StructureTemplate.transform written out again from the vanilla
source (pivot, mirror then rotation), applied to every cell of a template rather than to its corners.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import place_donor as PD  # noqa: E402
import place_town as PT  # noqa: E402

ROTS = ("none", "clockwise_90", "180", "counterclockwise_90")
MIRRORS = ("none", "left_right", "front_back")
DOC = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))


def vanilla(pos, mirror, rotation, pivot=(0, 0)):
    """net.minecraft.world.level.levelgen.structure.templatesystem.StructureTemplate.transform, x and z only."""
    i, k = pos
    if mirror == "left_right":
        k = -k
    elif mirror == "front_back":
        i = -i
    l, i1 = pivot
    if rotation == "counterclockwise_90":
        return (l - i1 + k, l + i1 - i)
    if rotation == "clockwise_90":
        return (l + i1 - k, i1 - l + i)
    if rotation == "180":
        return (l + l - i, i1 + i1 - k)
    return (i, k)


def placed_cells(x, z, size, rot, mirror):
    sx, _sy, sz = size
    return {(x + a, z + b) for a, b in (vanilla((tx, tz), mirror, rot) for tx in range(sx) for tz in range(sz))}


def rect_of(cells):
    xs, zs = [c[0] for c in cells], [c[1] for c in cells]
    return (min(xs), min(zs), max(xs), max(zs))


@pytest.mark.parametrize("rot", ROTS)
@pytest.mark.parametrize("mirror", MIRRORS)
def test_a_pack_donors_footprint_is_every_cell_place_template_writes(rot, mirror):
    rec = {"id": "t", "pack_template": "x:y", "position": {"x": 1000, "y": 64, "z": 2000}, "rotation": rot,
           "mirror": mirror, "size": [7, 3, 4]}
    want = rect_of(placed_cells(1000, 2000, rec["size"], rot, mirror))
    assert PD.footprint(rec, rec["size"]) == want
    lo, hi = PD.box(rec)
    assert (lo[0], lo[2], hi[0], hi[2]) == want


@pytest.mark.parametrize("rot", ROTS)
def test_a_town_buildings_footprint_starts_at_its_position(rot):
    # place_town puts the template's origin at position - (turned min corner), so its cells start at the position
    rec = {"id": "t", "file": "kits/x.nbt", "position": {"x": 1000, "y": 64, "z": 2000}, "rotation": rot}
    size = [7, 3, 4]
    mnx, mnz, _w, _d = PT.footprint(size, rot)
    want = rect_of(placed_cells(1000 - mnx, 2000 - mnz, size, rot, "none"))
    assert want[:2] == (1000, 2000)
    assert PD.footprint(rec, size) == want


def test_a_record_no_placer_seats_is_refused():
    with pytest.raises(SystemExit):
        PD.footprint({"id": "t", "position": {"x": 0, "y": 0, "z": 0}}, [3, 3, 3])


TURNED = [q for q in DOC["placements"] if q.get("pack_template") and (q.get("rotation") or "none") != "none"]


def test_the_turned_donors_are_there_to_check():
    assert len(TURNED) >= 10, [q["id"] for q in TURNED]


@pytest.mark.parametrize("rec", TURNED, ids=[q["id"] for q in TURNED])
def test_every_consumer_keeps_a_turned_donor_clear_where_place_template_puts_it(rec):
    import markets as M
    import markets_audit as MA
    import town_dressing as TD
    p = rec["position"]
    want = rect_of(placed_cells(p["x"], p["z"], rec["size"], rec.get("rotation") or "none", rec.get("mirror") or "none"))
    assert TD.building_footprints(rec["settlement"], DOC)[rec["id"]] == want
    fps, unknown = MA.building_footprints(rec["settlement"], DOC, None)
    assert fps[rec["id"]] == want and rec["id"] not in unknown
    fps, unknown = M.donor_footprints(rec["settlement"], DOC)
    assert rec["id"] in unknown or fps[rec["id"]] == want
