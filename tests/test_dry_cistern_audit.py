"""tools/dry_cistern_audit.py against tools/dry_cistern.py: the audit's derived levels are the hand-computed ones, and a
broken GENERATOR fails a named check.

Written by an agent that built none of the place (CLAUDE.md principle 16). Every mutation below changes the
generator's CODE (a function of tools/dry_cistern.py or of tools/wayside_kit.py wrapped or replaced) and leaves
data/dry_cistern.json and data/rewards.json alone (CLAUDE.md, "How to prove an audit is independent"). A mutation counts
as caught only by an error the unmutated build does not already have.

Most tests run on a synthetic dead-flat ground at y162, the least ground under the real cistern's footprint, so the
cache's barrel (data/rewards.json, y152) lands where the record puts it and every level is computable by hand: floor
162 - 11 = 151, room y152..156, water line 151 + 3 = 154, ground over the stair's passage 162 - (151 + j + 3) = 8 - j, so
steps 0..6 roofed (cover >= 2), 7..11 open, the top step j = 11 at y162; the shaft y157..161, the ladder y152..161 and the
trapdoor y162; the house floor 163. The committed place on the canonical heightmap is tested last (skipped, and says so,
without COBBLERS_SOURCE_ROOT).

NOT covered, and it needs a running server: that the fills land, that the cache is granted, whether a player can climb
out through the shaft past its slab ring and the lantern over its mouth.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dry_cistern as L  # noqa: E402
import dry_cistern_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "dry_cistern.json").read_text(encoding="utf-8"))
# The fault this audit found in the committed generator on 2026-10-03 (reported, not fixed: the builder's to fix).
KNOWN_REAL = [("headroom", "(4524, 5850) the cell y155 is minecraft:lantern")]   # a lantern in the third cell over step 1
KNOWN_FLAT = [("headroom", "(4524, 5850) the cell y155 is minecraft:lantern")]


class Flat:
    def __init__(self, y):
        self.y = y

    def __call__(self, x, z):
        return self.y


FLAT = Flat(162)


def run(g, out, steps=None):
    doc = L.load()
    written, _pl = L.files(doc, g)
    L.K.write(written, out)
    return A.audit(REC, g, out, steps if steps is not None else L.placement_steps(doc, g))


def matches(rep, known):
    hit, other = set(), []
    for e in rep.errors:
        k = [i for i, (check, text) in enumerate(known) if e.startswith(check + ":") and text in e]
        if k:
            hit.add(k[0])
        else:
            other.append(e)
    return other == [] and hit == set(range(len(known))), (other, rep.errors)


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    return set(run(FLAT, tmp_path_factory.mktemp("cistern_flat")).errors)


def caught(rep, baseline, check):
    return [e for e in rep.errors if e not in baseline and e.startswith(check + ":")]


def _wrap_plan(monkeypatch, after):
    orig = L.plan

    def wrapped(doc, g):
        pl = orig(doc, g)
        after(pl, doc, g)
        return pl
    monkeypatch.setattr(L, "plan", wrapped)


# Without it the audit's levels could drift from the record's arithmetic and still agree with the builder.
def test_on_flat_ground_the_audit_derives_the_hand_computed_levels():
    E = A.Expect(REC, FLAT)
    assert (E.F, E.wl, E.hf, E.gs, E.first, len(E.room)) == (151, 154, 163, 162, (4525, 5850), 315)
    assert sorted(y for (_x, y, _z) in E.shaft) == [157, 158, 159, 160, 161]


# Without it the stair could be read with the wrong count or the wrong roof and nothing would say so.
def test_on_flat_ground_the_flight_is_a_landing_and_eleven_steps_seven_roofed(tmp_path):
    rep = run(FLAT, tmp_path)
    assert any("a landing and 11 steps, 7 of the 12 roofed (least cover 2), top step y162" in n for n in rep.notes), \
        rep.notes


# Without it the audit could stop reporting the fault it found, or start reporting new ones, unseen.
def test_on_flat_ground_the_audit_finds_exactly_the_reported_fault(tmp_path):
    ok, why = matches(run(FLAT, tmp_path), KNOWN_FLAT)
    assert ok, why


# ------------------------------------------------------------------------------------------- generator mutations
# Without it a stair roofed under one block of ground (which the record forbids: two or more) would pass.
def test_the_roof_rule_cut_to_one_block_is_caught(tmp_path, monkeypatch, baseline):
    orig = L.K.stair_passage

    def thin_roof(g, first, direction, floor0, half_width, height):
        steps = orig(g, first, direction, floor0, half_width, height)
        for s in steps:
            s["open"] = any(g(x, z) - (s["floor"] + height) < 1 for x, z in s["cols"])
        return steps
    monkeypatch.setattr(L.K, "stair_passage", thin_roof)
    assert caught(run(FLAT, tmp_path), baseline, "cover")


# Without it a gap in the shaft's ladder (a player falls, or cannot climb) would pass.
def test_a_missing_ladder_is_caught(tmp_path, monkeypatch, baseline):
    def drop(pl, doc, g):
        sx, sz = doc["shaft"]["at"]
        del pl["plan"].hung[(sx, pl["floor"] + 3, sz)]
    _wrap_plan(monkeypatch, drop)
    assert caught(run(FLAT, tmp_path), baseline, "shaft")


# Without it an open trapdoor (a hole in the plateau over an 11-block drop) would pass.
def test_an_open_trapdoor_is_caught(tmp_path, monkeypatch, baseline):
    def open_it(pl, doc, g):
        sx, sz = doc["shaft"]["at"]
        k = (sx, g(sx, sz), sz)
        pl["plan"].hung[k] = pl["plan"].hung[k].replace("open=false", "open=true")
    _wrap_plan(monkeypatch, open_it)
    assert caught(run(FLAT, tmp_path), baseline, "shaft")


# Without it a cistern dug deeper or shallower than the record's depth would pass.
def test_a_cistern_floor_a_block_deep_is_caught(tmp_path, monkeypatch, baseline):
    def deeper(pl, doc, g):
        p, F = pl["plan"], pl["floor"]
        for (x, y, z) in list(pl["room"]):
            if y == F + 1:
                p.solid[(x, F, z)] = "minecraft:air"
                p.solid[(x, F - 1, z)] = "minecraft:smooth_red_sandstone"
    _wrap_plan(monkeypatch, deeper)
    assert caught(run(FLAT, tmp_path), baseline, "cistern")


# Without it the old water line could run anywhere, on any course, in any wall.
def test_the_water_line_on_the_wrong_course_is_caught(tmp_path, monkeypatch, baseline):
    def move(pl, doc, g):
        p = pl["plan"]
        for k in [k for k, s in p.solid.items() if s == "minecraft:white_terracotta"]:
            p.solid[k] = "minecraft:red_sandstone"
            p.solid[(k[0], k[1] + 1, k[2])] = "minecraft:white_terracotta"
    _wrap_plan(monkeypatch, move)
    assert caught(run(FLAT, tmp_path), baseline, "pillars")


# Without it a sign or lantern written before the block it hangs on would pass.
def test_hung_blocks_written_before_what_holds_them_are_caught(tmp_path, monkeypatch, baseline):
    def hung_first(header, p, clear, clear_y):
        return list(header) + L.K.runs(p.hung, top_down=True) + L.K.runs(
            {k: s for k, s in p.solid.items() if k not in p.hung})
    monkeypatch.setattr(L.K, "build_lines", hung_first)
    assert caught(run(FLAT, tmp_path), baseline, "attached")


# ------------------------------------------------------------------------------------------- the committed place
@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("NOT_EXECUTED: the canonical heightmap is unusable: %s" % e)


# Without it the place as it will be applied (on the tilted brow) could carry a fault the flat fixture cannot show.
def test_the_committed_cistern_has_exactly_the_reported_fault(ground, tmp_path):
    ok, why = matches(run(ground, tmp_path), KNOWN_REAL)
    assert ok, why


# Without it the audit could be written and never run: prepare runs it after the build.
def test_the_audit_runs_in_prepare_after_the_build():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    b = text.find('add("dry_cistern:build", "dry_cistern.py", "build"')
    a = text.find('add("dry_cistern_audit", "dry_cistern_audit.py"')
    assert 0 <= b < a
    assert '("R9CI"' in text
