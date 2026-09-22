"""tools/place_donor.py force-loads what /place template checks, not only what it writes.

Vanilla's /place template refuses ("That position is not loaded") unless the UNROTATED extent (origin to origin +
size) is loaded, although it writes the rotated one. The League turned clockwise_90 on the Rift's floor placed
nothing in a whole staging run (2026-09-21); the audit caught it at 0 of 159,471 blocks. Written in the same session
as the fix.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import place_donor as PD  # noqa: E402


@pytest.mark.parametrize("rot", ["none", "clockwise_90", "180", "counterclockwise_90"])
def test_the_load_box_covers_the_rotated_footprint_and_the_unrotated_extent(rot):
    rec = {"position": {"x": 3636, "y": 84, "z": 2591}, "size": [111, 159, 120], "rotation": rot}
    x0, z0, x1, z1 = PD.load_box(rec, margin=0)
    lo, hi = PD.box(rec)
    assert x0 <= lo[0] and z0 <= lo[2] and x1 >= hi[0] and z1 >= hi[2], "the rotated footprint"
    assert x0 <= 3636 and z0 <= 2591 and x1 >= 3636 + 110 and z1 >= 2591 + 119, "the unrotated extent"


def test_every_donor_function_force_loads_its_load_box():
    import json
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    for rec in PD.records(doc):
        lines = PD.commands(rec, [])
        assert lines[1] == "forceload add %d %d %d %d" % PD.load_box(rec), rec["id"]
