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


def test_the_league_plateau_is_a_zone():
    zones = CS.spawn_free_zones()
    assert any(x0 <= 3200 and x1 >= 3395 and z0 <= 2535 and z1 >= 2671 for x0, x1, z0, z1 in zones), \
        "the League precinct (its lot, forecourt and processional) must be inside a spawn-free zone"


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
