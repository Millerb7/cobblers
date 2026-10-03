"""tools/challengers_cairn_audit.py against tools/challengers_cairn.py: the audit's derived levels are the hand-computed
ones, and a broken GENERATOR fails a named check.

Written by an agent that built none of the place (CLAUDE.md principle 16). Every mutation below changes the
generator's CODE (a function of tools/challengers_cairn.py or of tools/wayside_kit.py wrapped or replaced) and leaves
data/challengers_cairn.json and data/rewards.json alone: a record-side mutation moves the expectation and the output
together and proves nothing (CLAUDE.md, "How to prove an audit is independent"). A mutation counts as caught only by an
error the unmutated build does not already have.

Most tests run on a synthetic dead-flat ground at y109, the measured ground of the real terrace (data/challengers_cairn.json
site.why), so they need no heightmap and every level is computable by hand: cist floor 109 - 7 = 102, crown 109 + 7 =
116, ground over the stair's passage 109 - (102 + j + 3) = 4 - j, so steps 0..2 roofed (cover >= 2), 3..7 open, and the
top step j = 7 at y109. The committed place on the canonical heightmap is tested last (skipped, and says so, without
COBBLERS_SOURCE_ROOT).

NOT covered, and it needs a running server: that the fills land, that the cache is granted, how the place looks.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import challengers_cairn as L  # noqa: E402
import challengers_cairn_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "challengers_cairn.json").read_text(encoding="utf-8"))
# The faults this audit found in the committed generator on 2026-10-03 (reported, not fixed: the builder's to fix).
# When the builder is fixed this list empties and the tests that pin it say so.
KNOWN = [
    ("cist", "(3554, 103, 6110)"),        # four undeclared field stones in the cist's corners, in the declared void
    ("headroom", "(3556, 6116) the cell y106 is minecraft:lantern"),   # a lantern in the third cell over step 1
]


class Flat:
    """A dead-flat ground: every column y."""

    def __init__(self, y):
        self.y = y

    def __call__(self, x, z):
        return self.y


FLAT = Flat(109)


def run(g, out, steps=None):
    doc = L.load()
    written, _pl = L.files(doc, g)
    L.K.write(written, out)
    return A.audit(REC, g, out, steps if steps is not None else L.placement_steps(doc, g))


def known(rep):
    """The errors that are the reported faults, and the ones that are not."""
    hit, other = set(), []
    for e in rep.errors:
        k = [i for i, (check, text) in enumerate(KNOWN) if e.startswith(check + ":") and text in e]
        if k:
            hit.add(k[0])
        else:
            other.append(e)
    return hit, other


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    return set(run(FLAT, tmp_path_factory.mktemp("cairn_flat")).errors)


def caught(rep, baseline, check):
    return [e for e in rep.errors if e not in baseline and e.startswith(check + ":")]


# Without it the audit's levels could drift from the record's arithmetic and still agree with the builder.
def test_on_flat_ground_the_audit_derives_the_hand_computed_levels():
    E = A.Expect(REC, FLAT)
    assert (E.F, E.crown, E.first, len(E.room)) == (102, 116, (3556, 6115), 75)


# Without it the stair could be read with the wrong count or the wrong roof and nothing would say so.
def test_on_flat_ground_the_flight_is_a_landing_and_seven_steps_three_roofed(tmp_path):
    rep = run(FLAT, tmp_path)
    assert any("a landing and 7 steps, 3 of the 8 roofed (least cover 2), top step y109" in n for n in rep.notes), \
        rep.notes


# Without it the audit could stop reporting the faults it found, or start reporting new ones, unseen.
def test_on_flat_ground_the_audit_finds_exactly_the_reported_faults(tmp_path):
    rep = run(FLAT, tmp_path)
    hit, other = known(rep)
    assert other == [] and hit == set(range(len(KNOWN))), (other, rep.errors)


# ------------------------------------------------------------------------------------------- generator mutations
# Without it a carve that leaves the natural ground (gravel, a cave, water) against the cist would pass.
def test_a_thinner_shell_is_caught(tmp_path, monkeypatch, baseline):
    orig = L.K.shell
    monkeypatch.setattr(L.K, "shell", lambda g, voids, margin, keep: orig(g, voids, margin - 1, keep))
    assert caught(run(FLAT, tmp_path), baseline, "shell")


# Without it a stair with a two-block riser, which a player cannot walk, would pass.
def test_a_step_two_high_is_caught(tmp_path, monkeypatch, baseline):
    orig = L.K.stair_passage

    def two_high(*a, **k):
        steps = orig(*a, **k)
        for s in steps:
            if s["j"] >= 3:
                s["floor"] += 1
        return steps
    monkeypatch.setattr(L.K, "stair_passage", two_high)
    assert caught(run(FLAT, tmp_path), baseline, "stair")


# Without it the cache's barrel, which data/rewards.json and the advancement name, could be missing from the cist.
def test_a_missing_barrel_is_caught(tmp_path, monkeypatch, baseline):
    orig = L.plan

    def no_barrel(doc, g):
        pl = orig(doc, g)
        pl["plan"].solid[pl["barrel"]] = "minecraft:air"
        return pl
    monkeypatch.setattr(L, "plan", no_barrel)
    assert caught(run(FLAT, tmp_path), baseline, "find")


# Without it a cairn seated a block high (floating over its ground) would pass.
def test_a_cairn_floating_a_block_over_its_ground_is_caught(tmp_path, monkeypatch, baseline):
    orig = L.plan

    def lift(doc, g):
        pl = orig(doc, g)
        p = pl["plan"]
        cx, cz = doc["cairn"]["centre"]
        for (x, y, z) in [k for k in p.solid if k[1] == g(k[0], k[2]) + 1 and abs(k[0] - cx) <= 1
                          and abs(k[2] - cz) <= 1]:
            p.solid[(x, y, z)] = "minecraft:air"
        return pl
    monkeypatch.setattr(L, "plan", lift)
    assert caught(run(FLAT, tmp_path), baseline, "cairn")


# Without it a sign or lantern written before the block it hangs on (which pops off in game) would pass.
def test_hung_blocks_written_before_what_holds_them_are_caught(tmp_path, monkeypatch, baseline):
    def hung_first(header, p, clear, clear_y):
        return list(header) + L.K.runs(p.hung, top_down=True) + L.K.runs(
            {k: s for k, s in p.solid.items() if k not in p.hung})
    monkeypatch.setattr(L.K, "build_lines", hung_first)
    assert caught(run(FLAT, tmp_path), baseline, "attached")


# Without it R9CN could hold chunks that miss the build, and the fills would fail on unloaded chunks.
def test_a_build_outside_its_forceload_is_caught(tmp_path, baseline):
    doc = L.load()
    steps = [s for s in L.placement_steps(doc, FLAT) if not (s[0] == "cmd" and "forceload add" in s[1])]
    steps.insert(0, ("cmd", "forceload add 0 0 1 1"))
    assert caught(run(FLAT, tmp_path, steps), baseline, "steps")


# ------------------------------------------------------------------------------------------- the committed place
@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("NOT_EXECUTED: the canonical heightmap is unusable: %s" % e)


# Without it the place as it will be applied (on the real ground) could carry a fault the flat fixture cannot show.
def test_the_committed_cairn_has_exactly_the_reported_faults(ground, tmp_path):
    rep = run(ground, tmp_path)
    hit, other = known(rep)
    assert other == [] and hit == set(range(len(KNOWN))), (other, rep.errors)


# Without it an audit could start sharing the builder's derivation (CLAUDE.md, "How to prove an audit is independent"):
# the three wayside audits and their kit import no builder and not tools/wayside_kit.py, but for the re-application
# steps a main() takes from its own generator (its output, checked, never its geometry).
def test_the_wayside_audits_import_no_builder_outside_main():
    import ast
    builders = {"challengers_cairn", "dry_cistern", "survey_benchmark", "wayside_kit"}
    for name in ("wayside_audit", "challengers_cairn_audit", "dry_cistern_audit", "survey_benchmark_audit"):
        tree = ast.parse((ROOT / "tools" / ("%s.py" % name)).read_text(encoding="utf-8"))
        mains = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
        inside_main = {id(n) for m in mains for n in ast.walk(m)}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and id(node) not in inside_main:
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                assert not set(m.split(".")[0] for m in mods) & builders, (name, mods)


# Without it the audit could be written and never run: prepare runs it after the build, and R9CN is a re-apply step.
def test_the_audit_runs_in_prepare_after_the_build():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    b = text.find('add("challengers_cairn:build", "challengers_cairn.py", "build"')
    a = text.find('add("challengers_cairn_audit", "challengers_cairn_audit.py"')
    assert 0 <= b < a
    assert '("R9CN"' in text
