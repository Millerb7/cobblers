"""tools/drovers_hollow_audit.py against tools/drovers_hollow.py: the clean pack passes, and a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for both), so the independent
half of the proof is the mutation standard of CLAUDE.md, "How to prove an audit is independent": every tamper case
below changes the generator's CODE (a function wrapped or replaced) and leaves data/drovers_hollow.json,
data/habitat_blocks.json, data/rewards.json and the dialogue records alone. A record-side mutation moves the expectation
and the output together and proves nothing.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); a skip names it. NOT covered, and it needs a running server: that
the fills land, that the herd spawns and stays in the fold, that the cache is granted, that the drover talks.
"""
import copy
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import drovers_hollow as L  # noqa: E402
import drovers_hollow_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "drovers_hollow.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def run(ground, out, steps=None):
    doc = L.load()
    written, _pl = L.files(doc, ground)
    L.write(written, out)
    return A.audit(REC, ground, out, steps if steps is not None else L.placement_steps(doc, ground))


def checks(rep):
    return sorted({e.split(":", 1)[0] for e in rep.errors})


def test_the_committed_hollow_is_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []


def test_the_shared_records_name_the_places_the_generator_builds(ground):
    pl = L.plan(L.load(), ground)
    data = ROOT / "data"
    hb = {b["id"]: b for b in json.loads((data / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]}
    b = hb[REC["herd"]["block"]]
    assert pl["habitat_block"] == (b["position"]["x"], b["position"]["y"], b["position"]["z"])
    rw = {r["id"]: r for r in json.loads((data / "rewards.json").read_text(encoding="utf-8"))["rewards"]}
    assert tuple(rw[REC["find"]["reward"]]["container"]["at"]) == pl["barrel"]
    (conv, at, cls), = L.npc_placements(L.load(), ground)
    assert conv == REC["npc"]["conversation"] and at == pl["npc"] and cls == "cobblers:npc_drovers_hollow_drover"


def test_every_void_of_the_working_has_margin_plus_one_of_ground_over_it_outside_the_barn(ground):
    pl = L.plan(L.load(), ground)
    cover = L.cover(pl, ground)
    assert cover and min(cover.values()) >= REC["working"]["margin"] + 1


# ------------------------------------------------------------------------------------------- generator mutations
def _wrap(monkeypatch, name, after):
    orig = getattr(L, name)

    def wrapped(doc, p, *a, **k):
        r = orig(doc, p, *a, **k)
        after(p)
        return r
    monkeypatch.setattr(L, name, wrapped)


def test_a_thinner_shell_is_caught(ground, tmp_path, monkeypatch):
    orig = L.working_shell

    def thin(doc, p, voids):
        d = copy.deepcopy(doc)
        d["working"]["margin"] -= 1
        return orig(d, p, voids)
    monkeypatch.setattr(L, "working_shell", thin)
    assert "working" in checks(run(ground, tmp_path))


def test_a_taller_drift_is_caught(ground, tmp_path, monkeypatch):
    orig = L.working_voids

    def taller(doc, p):
        v = orig(doc, p)
        t = doc["working"]["tunnel"]
        top = p.wf + t["height"]
        return v | {(x, top + 1, z) for (x, y, z) in v if y == top and t["x"][0] <= x <= t["x"][1]}
    monkeypatch.setattr(L, "working_voids", taller)
    assert "working" in checks(run(ground, tmp_path))


def test_a_missing_trapdoor_is_caught(ground, tmp_path, monkeypatch):
    def drop(p):
        wx, wz = REC["well"]["at"]
        p.hung.pop((wx, p.bf, wz), None)
    _wrap(monkeypatch, "working", drop)
    got = checks(run(ground, tmp_path))
    assert "seat" in got and "walk" in got


def test_a_barn_seated_a_block_high_is_caught(ground, tmp_path, monkeypatch):
    orig = L.Plan.__init__

    def high(self, doc, g):
        orig(self, doc, g)
        self.bf += 1
        self.wf += 1
    monkeypatch.setattr(L.Plan, "__init__", high)
    assert "seat" in checks(run(ground, tmp_path))


def test_hung_blocks_written_before_what_holds_them_are_caught(ground, tmp_path, monkeypatch):
    def hung_first(doc, pl):
        p = pl["plan"]
        return L._runs(p.hung, top_down=True) + L._runs({k: s for k, s in p.solid.items() if k not in p.hung})
    monkeypatch.setattr(L, "build_lines", hung_first)
    assert "attached" in checks(run(ground, tmp_path))


def test_a_gap_in_the_fold_fence_is_caught(ground, tmp_path, monkeypatch):
    def gap(p):
        f = REC["fold"]
        x, z = f["x"][1], (f["z"][0] + f["z"][1]) // 2
        p.solid[(x, p.g(x, z) + 1, z)] = "minecraft:air"
    _wrap(monkeypatch, "fold", gap)
    assert "fold" in checks(run(ground, tmp_path))


def test_a_dark_working_is_caught(ground, tmp_path, monkeypatch):
    def dark(p):
        for k in [k for k, s in p.hung.items() if s.startswith("minecraft:lantern") and k[1] < p.bf]:
            del p.hung[k]
    _wrap(monkeypatch, "working", dark)
    assert "light" in checks(run(ground, tmp_path))


def test_a_barrel_left_out_is_caught(ground, tmp_path, monkeypatch):
    def no_barrel(p):
        for k in [k for k, s in p.solid.items() if s.startswith("minecraft:barrel")]:
            p.solid[k] = "minecraft:air"
    _wrap(monkeypatch, "working", no_barrel)
    assert "find" in checks(run(ground, tmp_path))


def test_a_build_outside_its_forceload_is_caught(ground, tmp_path):
    doc = L.load()
    steps = [s for s in L.placement_steps(doc, ground) if not (s[0] == "cmd" and "forceload add" in s[1])]
    steps.insert(0, ("cmd", "forceload add 0 0 1 1"))
    assert "steps" in checks(run(ground, tmp_path, steps))


# ------------------------------------------------------------------------------------------- the re-application
def test_the_steps_run_before_the_habitat_blocks_and_the_drover_after_the_settlement_npcs():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")

    def at(token):
        i = text.find(token)
        assert i >= 0, token
        return i
    assert at('("R9LH"') < at('("R9HF"') < at('("R9E"')
    assert at('("R17N"') < at('("R18HF"')
    assert '"cobblers_drovers_hollow"' in text
    assert 'add("drovers_hollow:build", "drovers_hollow.py", "build"' in text
    assert 'add("drovers_hollow_audit", "drovers_hollow_audit.py"' in text
