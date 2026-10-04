"""tools/survey_benchmark_audit.py against tools/survey_benchmark.py: the clean pack passes, the audit's derived levels
are the hand-computed ones, and a broken GENERATOR fails a named check.

Written by an agent that built none of the place (CLAUDE.md principle 16). Every mutation below changes the
generator's CODE (a function of tools/survey_benchmark.py or of tools/wayside_kit.py wrapped or replaced) and leaves
data/survey_benchmark.json and data/rewards.json alone (CLAUDE.md, "How to prove an audit is independent").

Most tests run on a synthetic two-level ground, y114 west of x3712 and y115 from it east (the real rise's two levels
along the door's row, measured with tools/ground.py), so the cache's barrel (data/rewards.json, y117) lands where the
record puts it, the record's bbox holds, and every level is computable by hand: plinth top 115, pillar y116..119, cap
120, lantern 121; hut floor 116, walls to 120, roof 121; the ramp two steps (x3711 y116 and x3710 y115; the next, y114,
is not above the ground); each stake two posts at y115..116 and a lantern at y117. The committed place on the canonical
heightmap is tested last (skipped, and says so, without COBBLERS_SOURCE_ROOT).

NOT covered, and it needs a running server: that the fills land, that the cache is granted, how the place looks.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import survey_benchmark as L  # noqa: E402
import survey_benchmark_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "survey_benchmark.json").read_text(encoding="utf-8"))


class Step:
    """y114 west of x3712, y115 from it east."""

    def __call__(self, x, z):
        return 114 if x < 3712 else 115


FLAT = Step()


def run(g, out, steps=None):
    doc = L.load()
    written, _pl = L.files(doc, g)
    L.K.write(written, out)
    return A.audit(REC, g, out, steps if steps is not None else L.placement_steps(doc, g))


def checks(rep):
    return rep.checks()


def _wrap_plan(monkeypatch, after):
    orig = L.plan

    def wrapped(doc, g):
        pl = orig(doc, g)
        after(pl, doc, g)
        return pl
    monkeypatch.setattr(L, "plan", wrapped)


# Without it the audit's levels could drift from the record's arithmetic and still agree with the builder.
def test_on_stepped_ground_the_audit_derives_the_hand_computed_levels():
    E = A.Expect(REC, FLAT)
    assert (E.pb, E.cap, E.bf) == (115, 120, 116)


# Without it a broken build could pass on the fixture; the notes pin the hand-computed ramp and stakes.
def test_on_stepped_ground_the_benchmark_is_clean(tmp_path):
    rep = run(FLAT, tmp_path)
    assert rep.errors == []
    assert "ramp: 2 step(s) from the sill y116" in rep.notes
    assert "stakes: [(3694, 5683), (3699, 5694), (3703, 5705)]" in rep.notes


# ------------------------------------------------------------------------------------------- generator mutations
# Without it a hut seated a block over its ground (its floor where a player's feet go) would pass.
def test_a_hut_a_block_high_is_caught(tmp_path, monkeypatch):
    def lift(pl, doc, g):
        p, bf = pl["plan"], pl["hut_floor"]
        h = doc["hut"]
        inside = lambda k: h["x"][0] - 1 <= k[0] <= h["x"][1] + 1 and h["z"][0] - 1 <= k[2] <= h["z"][1] + 1 \
            and k[1] >= bf  # noqa: E731
        for d in (p.solid, p.hung):
            moved = {(x, y + 1, z): s for (x, y, z), s in d.items() if inside((x, y, z))}
            for k in [k for k in d if inside(k)]:
                del d[k]
            d.update(moved)
        for x in range(h["x"][0], h["x"][1] + 1):
            for z in range(h["z"][0], h["z"][1] + 1):
                p.solid[(x, bf, z)] = "minecraft:cobblestone"
    _wrap_plan(monkeypatch, lift)
    assert "hut" in checks(run(FLAT, tmp_path))


# Without it a hut with its only door walled up (the cache unreachable) would pass.
def test_a_walled_door_is_caught(tmp_path, monkeypatch):
    def wall(pl, doc, g):
        h = doc["hut"]
        for dy in (1, 2):
            pl["plan"].solid[(h["x"][0], pl["hut_floor"] + dy, h["door_z"])] = "minecraft:acacia_planks"
    _wrap_plan(monkeypatch, wall)
    assert "hut" in checks(run(FLAT, tmp_path))


# Without it the sighting stakes could point anywhere: the line toward the Rift entry is the record's.
def test_a_stake_off_its_line_is_caught(tmp_path, monkeypatch):
    def shift(pl, doc, g):
        p = pl["plan"]
        x, y, z = pl["stakes"][0]
        for k in ((x, y - 2, z), (x, y - 1, z)):
            p.solid[(k[0] + 3, k[1], k[2])] = p.solid.pop(k)
        p.hung[(x + 3, y, z)] = p.hung.pop((x, y, z))
    _wrap_plan(monkeypatch, shift)
    assert "stakes" in checks(run(FLAT, tmp_path))


# Without it a ramp with a missing step (a jump to the door) would pass.
def test_a_ramp_a_step_short_is_caught(tmp_path, monkeypatch):
    def short(pl, doc, g):
        h = doc["hut"]
        pl["plan"].solid[(h["x"][0] - 1, pl["hut_floor"], h["door_z"])] = "minecraft:air"
    _wrap_plan(monkeypatch, short)
    assert "ramp" in checks(run(FLAT, tmp_path))


# Without it the cache's barrel, which data/rewards.json and the advancement name, could be missing from the hut.
def test_a_missing_barrel_is_caught(tmp_path, monkeypatch):
    def no_barrel(pl, doc, g):
        pl["plan"].solid[pl["barrel"]] = "minecraft:air"
    _wrap_plan(monkeypatch, no_barrel)
    assert "find" in checks(run(FLAT, tmp_path))


# Without it a sign or lantern written before the block it hangs on would pass.
def test_hung_blocks_written_before_what_holds_them_are_caught(tmp_path, monkeypatch):
    def hung_first(header, p, clear, clear_y):
        return list(header) + L.K.runs(p.hung, top_down=True) + L.K.runs(
            {k: s for k, s in p.solid.items() if k not in p.hung})
    monkeypatch.setattr(L.K, "build_lines", hung_first)
    assert "attached" in checks(run(FLAT, tmp_path))


# ------------------------------------------------------------------------------------------- the committed place
@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("NOT_EXECUTED: the canonical heightmap is unusable: %s" % e)


# Without it the place as it will be applied (on the real rise) could carry a fault the flat fixture cannot show.
def test_the_committed_benchmark_is_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []


# Without it the audit could be written and never run: prepare runs it after the build.
def test_the_audit_runs_in_prepare_after_the_build():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    b = text.find('add("survey_benchmark:build", "survey_benchmark.py", "build"')
    a = text.find('add("survey_benchmark_audit", "survey_benchmark_audit.py"')
    assert 0 <= b < a
    assert '("R9BM"' in text
