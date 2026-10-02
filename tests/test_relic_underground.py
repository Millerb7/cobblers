"""tools/relic_underground.py, its audit tools/relic_underground_audit.py, the capped surface in tools/deep_city.py and the
R9RU wiring in tools/reapply.py.

Written by the session that wired the generator and wrote the audit, so the independent half of the proof is CLAUDE.md's
mutation standard ("How to prove an audit is independent"): every tamper case below changes the GENERATOR's code (a
function replaced in-process) and leaves data/relic_underground.json and data/deep_city.json alone. A record-side
mutation moves the expectation and the output together and proves nothing.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); a skip names it. NOT covered, and it needs a running server: that
the fills land, that the zone turns a passless player back, and every probe in RELIC_UNDERGROUND.md section 9.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import relic_underground as R  # noqa: E402
import relic_underground_audit as A  # noqa: E402

SPEC = json.loads((ROOT / "data" / "relic_underground.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ no heightmap needed

def test_paint_seed_is_paint_maps_default():
    src = (ROOT / "tools" / "paint_maps.py").read_text(encoding="utf-8")
    m = re.search(r'"--seed", type=int, default=(\d+)', src)
    assert m and int(m.group(1)) == R.PAINT_SEED


def test_r9ru_runs_after_the_city_and_before_the_habitat_blocks():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    i_dc, i_ru, i_e = src.index('("R9DC"'), src.index('("R9RU"'), src.index('("R9E"')
    assert i_dc < i_ru < i_e
    import reapply
    assert "cobblers_relic_underground" in reapply.SERVER_PACKS
    assert "cobblers_relic_underground" in reapply.WORLD_LOCAL       # the zone advancement acts on its own
    assert '"relic_underground.py", *src, "build"' in src and '"relic_underground_audit.py"' in src


def test_the_zone_geometry_is_consistent():
    z = SPEC["zone"]

    def inbox(x, zz):
        return any(b[0] <= x <= b[2] and b[1] <= zz <= b[3] for b in z["boxes"])
    kb = z["knock"]["box"]
    assert not any(inbox(x, zz) for x in range(kb[0], kb[3] + 1) for zz in range(kb[2], kb[5] + 1))
    tx, ty, tz = z["turn_back"]["at"]
    assert not inbox(int(tx), int(tz)) and ty > z["y"][1]
    assert "cobblers:flag/rift_crisis_resolved" not in z["pass"]["threshold_advancements"]
    air, _floor = A.expected_air(SPEC)
    # the gallery reaches through the passage's north wall: the fault found 2026-10-02
    assert (3390, 6, 3304) in air and (3390, 7, 3305) in air and (3390, 6, 3303) in air
    out = [c for c in air if c[0] < z["threshold_x"] and not inbox(c[0], c[2])]
    assert not out


def test_deep_city_verify_no_longer_needs_the_ring():
    src = (ROOT / "tools" / "deep_city.py").read_text(encoding="utf-8")
    need = re.search(r"need = \{([^}]*)\}", src).group(1)
    assert "relic ring" not in need and "relic seal" in need


def test_the_open_decisions_are_recorded_not_invented():
    assert SPEC["composition"]["spawn_decision"]["status"].startswith("OPEN")
    assert SPEC["zone"]["hq_access"]["status"].startswith("NOT BUILT")
    hb = (ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8")
    assert "relic_underground" not in hb and "hoopa" not in hb.lower()


# ------------------------------------------------------------------ the heightmap

@pytest.fixture(scope="module")
def sr():
    import ground as G
    import terrain as T
    s = os.environ.get("COBBLERS_SOURCE_ROOT")
    try:
        G.Ground(s)
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)
    return s


@pytest.fixture(scope="module")
def inputs(sr):
    """What the audit checks against, computed ONCE and before any tamper: the ground, the pit, the old build, the
    city as the current generator builds it."""
    import ground as G
    import rift_deep as RD
    import relic_surface_superseded as S
    g = G.load(sr)
    m = RD.model(sr)
    X0, Z0 = m["box"][0], m["box"][1]

    def pit(x, z):
        i, j = z - Z0, x - X0
        if 0 <= i < m["mask"].shape[0] and 0 <= j < m["mask"].shape[1] and m["mask"][i, j]:
            return int(m["tread_y"][i, j])
        return None
    city = R.city_cells(sr)
    view = A._CityView(set(city), {c for c, b in city.items() if b.split("[")[0] != A.AIR})
    rm, (RX0, RZ0, _a, _b), _n = RD.region_mask("relic_area_shrine", sr)
    H, W = rm.shape
    edge = [(j + RX0, i + RZ0) for i in range(H) for j in range(W) if rm[i, j] and any(
        not (0 <= i + di < H and 0 <= j + dj < W) or not rm[i + di, j + dj]
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    return {"g": g, "pit": pit, "old": dict(S.old_write_set(sr)), "city": view, "edge": edge}


def build_and_audit(sr, inputs, out):
    R.cmd_build(argparse.Namespace(source_root=sr, out=str(out)))
    fns, order, zone = A.read_pack(out)
    probs, st = A.audit(fns, order, zone, SPEC, inputs["g"], inputs["pit"], {"cobblers_deep_city": inputs["city"]["all"]},
                        inputs["old"], inputs["city"])
    undo = {c: A.base(w[6]) for n in order if n.startswith("undo") for w in fns[n] for c in A.cells(w)}
    left = A.cordon_check(undo, inputs["edge"], inputs["g"], inputs["city"]["all"])
    if left:
        probs.append(("cordon", "%d fence cells not cleared" % len(left)))
    return {k for k, _m in probs}, probs, st


def test_the_built_pack_is_clean(sr, inputs, tmp_path):
    kinds, probs, st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert not probs, probs
    assert st["undo_air"] > 0 and st["undo_ground"] > 0 and st["shell"] > 0


def test_the_capped_city_writes_no_shrine_and_no_fence(sr):
    import deep_city as DC
    spec = json.loads(DC.SPEC.read_text(encoding="utf-8"))
    cv = DC.Canvas()
    DC.build_relic(cv, DC.Palette(spec), spec, sr, lambda *a, **k: None, [])
    blocks = {b.split("[")[0] for b, _ph in cv.v.values()}
    for gone in ("minecraft:tinted_glass", "legendarymonuments:distortion_stone", "minecraft:purple_stained_glass"):
        assert gone not in blocks
    assert "minecraft:reinforced_deepslate" in blocks and "minecraft:raw_gold_block" in blocks   # the seal, the dig


# ------------------------------------------------------------------ tamper the GENERATOR; the audit must bite

def test_a_gallery_one_short_of_the_passage_fails_the_route(sr, inputs, tmp_path, monkeypatch):
    # the generator's geometry stops the gallery one block short, as it did before 2026-10-02; the data is untouched
    real = R.Geo.__init__

    def short(self, spec):
        real(self, spec)
        self.gz1 -= 1
    monkeypatch.setattr(R.Geo, "__init__", short)
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert "route" in kinds, probs


def test_an_undo_that_forgets_the_city_fails(sr, inputs, tmp_path, monkeypatch):
    real = R.city_cells

    def forgetful(s):
        import inspect
        if any(f.function == "undo_plan" for f in inspect.stack()):
            return {}
        return real(s)
    monkeypatch.setattr(R, "city_cells", forgetful)
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert "undo" in kinds, probs


def test_an_undo_that_skips_the_fence_fails_the_independent_cordon_check(sr, inputs, tmp_path, monkeypatch):
    import relic_surface_superseded as S
    real = S.old_write_set

    def no_fence(s, *a, **k):
        return {c: b for c, b in real(s, *a, **k).items() if "tinted_glass" not in b and "iron_bars" not in b}
    monkeypatch.setattr(S, "old_write_set", no_fence)
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert "cordon" in kinds and "undo" in kinds, probs
