"""tools/ursaluna_cave_audit.py against tools/ursaluna_cave.py: the clean pack passes, and a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for both), so the
independent half of the proof is the mutation standard of CLAUDE.md, "How to prove an audit is independent": every
tamper case below changes the generator's CODE and leaves data/ursaluna_cave.json alone. A record-side mutation
moves the expectation and the output together and proves nothing.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); a skip names it. NOT covered, and it needs a running server:
that the fills land, that the bear is twice normal size, that it sleeps, that the barrier stops a ball, and that
Teddiursa spawn in the Habitat Block's range.
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


def test_a_missing_curtain_exposes_the_bear(ground, tmp_path, monkeypatch):
    real = U.carve_lines
    monkeypatch.setattr(U, "carve_lines",
                        lambda doc, M: [l for l in real(doc, M) if "minecraft:barrier" not in l])
    assert "curtain" in checks(run(ground, tmp_path))


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
