"""tools/ursaluna_cave_audit.py against tools/ursaluna_cave.py: the clean pack passes, and a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for both), so the
independent half of the proof is the mutation standard of CLAUDE.md, "How to prove an audit is independent": every
tamper case below changes the generator's CODE and leaves data/ursaluna_cave.json alone. A record-side mutation
moves the expectation and the output together and proves nothing.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); a skip names it. NOT covered, and it needs a running server
(experiments/EXP-049-ursaluna-wake): that the fills land, that the bear is twice normal size, that it sleeps, that the
wake fires and a battle can then start, and that Teddiursa spawn round the activated block.

Since 2026-10-02 the den has no barrier and the bear wakes as a boss (the owner: "Wake it as a boss fight"); the old
"a missing curtain exposes the bear" proof is inverted into "a barrier put back is refused", and the wake has its own
generator mutations: a radius that reaches the passage, a wake that leaves Unbattleable on, a keeper that does not
stand down, and a dress that forgets to reset the awake score.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ursaluna_cave as U  # noqa: E402
import ursaluna_cave_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "ursaluna_cave.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def run(ground, out):
    doc = U.load()
    for rel, text in U.files(doc, ground).items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return A.audit(REC, ground, out, U.placement_steps(doc, ground))


def checks(rep):
    return sorted({e.split(":", 1)[0] for e in rep.errors})


def test_the_committed_cave_is_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []


def test_a_thinner_shell_breaks_the_seal(ground, tmp_path, monkeypatch):
    real = U._dilate
    monkeypatch.setattr(U, "_dilate", lambda mask, m: real(mask, m - 1))
    assert "seal" in checks(run(ground, tmp_path))


def test_a_taller_hall_is_not_the_planned_void(ground, tmp_path, monkeypatch):
    real = U.Model.__init__

    def taller(self, doc, g):
        real(self, doc, g)
        self.void = self.void | np.roll(self.void, 1, axis=0)

    monkeypatch.setattr(U.Model, "__init__", taller)
    assert "void" in checks(run(ground, tmp_path))


def test_a_barrier_put_back_is_refused(ground, tmp_path, monkeypatch):
    real = U.carve_lines

    def walled(doc, M):
        # the old curtain, re-derived in the generator's own frame: a 2-thick band across the hall at s 63-64
        band = M.void & (M.S[None] >= 63 - U.EPS) & (M.S[None] < 65 - U.EPS)
        return real(doc, M) + [U._fill(r, "minecraft:barrier", " replace minecraft:air") for r in M.runs(band)]

    monkeypatch.setattr(U, "carve_lines", walled)
    assert "barrier" in checks(run(ground, tmp_path))


def test_a_wake_that_reaches_the_passage_is_refused(ground, tmp_path, monkeypatch):
    real = U.wake_selector
    r = REC["ursaluna"]["wake"]["radius"]
    monkeypatch.setattr(U, "wake_selector", lambda doc: real(doc).replace("distance=..%d," % r, "distance=..40,"))
    assert "wake" in checks(run(ground, tmp_path))


def test_a_wake_that_leaves_the_bear_unbattleable_is_refused(ground, tmp_path, monkeypatch):
    real = U.files

    def asleep(doc, g):
        out = real(doc, g)
        k = "data/cobblers/function/ursaluna_cave/wake.mcfunction"
        out[k] = out[k].replace("Unbattleable:0b,", "")
        return out

    monkeypatch.setattr(U, "files", asleep)
    assert "wake" in checks(run(ground, tmp_path))


def test_a_keeper_that_does_not_stand_down_is_refused(ground, tmp_path, monkeypatch):
    real = U.awake_if
    monkeypatch.setattr(U, "awake_if", lambda doc, v: real(doc, 2) if v == 1 else real(doc, v))
    assert "wake" in checks(run(ground, tmp_path))


def test_a_dress_that_keeps_the_bear_awake_is_refused(ground, tmp_path, monkeypatch):
    real = U.awake_set
    monkeypatch.setattr(U, "awake_set", lambda doc, v: real(doc, 1))
    assert "wake" in checks(run(ground, tmp_path))


@pytest.mark.parametrize("mutate", [
    lambda d: d["cave"]["blocks"].__setitem__("curtain", "minecraft:barrier"),
    lambda d: d["ursaluna"]["wake"]["awake_nbt"].__setitem__("Unbattleable", "1b"),
    lambda d: d["ursaluna"]["wake"]["awake_nbt"].__setitem__("PoseType", '"STAND"'),
    lambda d: d["ursaluna"]["wake"].__setitem__("radius", 48),
    lambda d: d["ursaluna"].__setitem__("encounter", "resident"),
], ids=["curtain", "unbattleable", "posetype", "radius-past-keeper", "resident"])
def test_the_generator_refuses_a_record_that_is_not_the_boss(mutate, tmp_path):
    """The generator's own guard, not the audit's: a record that puts a wall back or wakes a bear that cannot fight."""
    import copy
    d = copy.deepcopy(U.load())
    mutate(d)
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(U.CaveError):
        U.load(p)


def test_the_teddiursa_block_is_activated_and_audited(ground, tmp_path, monkeypatch):
    blk = next(b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
               if b["id"] == REC["teddiursa"]["block"])
    assert blk["style"] == "activated" and blk["replace_spawns"] is False
    assert blk["activated"]["max_spawns"] == REC["teddiursa"]["group"]
    import habitat_blocks as HB
    cmds = HB.commands(blk)
    assert cmds[0].startswith("setblock 1514 158 1424 %s" % blk["mimic"])
    assert "SpawningStyle:\"cobblemon:activated\"" in cmds[1] and "MaxSpawns:%d" % REC["teddiursa"]["group"] in cmds[1]


def test_a_bare_distance_guard_is_refused(ground, tmp_path, monkeypatch):
    real = U.summon_command
    monkeypatch.setattr(U, "summon_command", lambda doc, g, M=None: real(doc, g, M).replace(
        "unless entity @e[tag=%s] " % REC["ursaluna"]["tag"], "").replace(
        ',nbt={Pokemon:{Species:"cobblemon:ursaluna"}}', ""))
    assert "summon" in checks(run(ground, tmp_path))


def test_a_floor_over_air_is_caught(ground, tmp_path, monkeypatch):
    real = U.Model.__init__

    def everywhere(self, doc, g):
        real(self, doc, g)
        self.hall_cols = self.void.any(axis=0) & ~self.den_cols

    monkeypatch.setattr(U.Model, "__init__", everywhere)
    assert "floor" in checks(run(ground, tmp_path))
