"""A spawn-free zone has nothing spawning in it: no compiled pool reaches it, and the inherited pools are
suppressed over it.

Without this the League plateau, the owner's one ceremonial place, gets Sandygast and Smeargle on the champion's
processional (2026-09-21). The first compile still left 80 details in the zone, from sub-region cells that only
overlapped its edge.

Written by the same session that wrote the zones; not independently reviewed (docs/HANDOVER_CODEX.md).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_spawns as CS  # noqa: E402


def test_subtract_leaves_nothing_inside_and_everything_outside():
    zone = (10, 19, 10, 19)
    parts = CS.subtract((0, 29, 0, 29), [zone])
    cells = {(x, z) for x0, x1, z0, z1 in parts for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    assert not any(10 <= x <= 19 and 10 <= z <= 19 for x, z in cells)
    assert len(cells) == 30 * 30 - 10 * 10
    assert CS.subtract((0, 5, 0, 5), [zone]) == [(0, 5, 0, 5)]


def test_the_league_precinct_is_a_zone():
    # the League moved into the Rift, onto the trunk head's floor (2026-09-21): its lot, forecourt and Victory Road's
    # arrival, taken from its plan, must be inside a spawn-free zone
    plan = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]["league"]["plan"]
    lot = next(a["rect"] for a in plan["anchors"] if a["id"] == "league_building")
    pz = plan["plaza"]["rect"]
    x0p, z0p = min(lot[0], pz[0]), min(lot[1], pz[1])
    x1p, z1p = max(lot[2], pz[2]), max(lot[3], plan["entries"][0]["at"][1])
    zones = CS.spawn_free_zones()
    assert any(x0 <= x0p and x1 >= x1p and z0 <= z0p and z1 >= z1p for x0, x1, z0, z1 in zones), \
        "the League precinct (its lot, forecourt and Victory Road's arrival) must be inside a spawn-free zone"


def test_no_compiled_detail_reaches_a_zone():
    pack = ROOT / "build" / "datapacks" / "cobblers_spawns"
    if not pack.is_dir():
        import pytest
        pytest.skip("no compiled pack under build/ (python tools/compile_spawns.py)")
    zones = CS.spawn_free_zones()
    for f in pack.rglob("spawn_pool_world/**/*.json"):
        for s in json.loads(f.read_text(encoding="utf-8"))["spawns"]:
            c = s["condition"]
            if "minX" in c:
                assert CS.subtract((c["minX"], c["maxX"], c["minZ"], c["maxZ"]), zones) == [(c["minX"], c["maxX"], c["minZ"], c["maxZ"])], \
                    "%s: %s reaches into a spawn-free zone" % (f.name, s["id"])
