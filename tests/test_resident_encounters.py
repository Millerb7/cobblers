"""tools/resident_encounters_audit.py against tools/resident_encounters.py: the clean pack passes, a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for both), so the independent
half of the proof is CLAUDE.md's mutation standard ("How to prove an audit is independent"): every tamper case below
changes the generator's CODE (a monkeypatched function) and leaves data/resident_encounters.json alone. The two
record-side cases at the end test the GENERATOR's own refusals and the audit's declared-leak rule, not independence.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); a skip names it. NOT covered, and it needs a running server:
that the blocks land, that the summons and macro spawns produce one entity each, that NoAI merged on a live Pokemon
holds and releases it, that a woken resident can be battled, and every world probe in
docs/world-building/RESIDENT_ENCOUNTERS.md.
"""
import copy
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import resident_encounters as R  # noqa: E402
import resident_encounters_audit as A  # noqa: E402

DOC = json.loads((ROOT / "data" / "resident_encounters.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def run(ground, out, doc=None):
    gdoc = doc or R.load()
    for rel, text in R.files(gdoc, ground).items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return A.audit(doc or DOC, ground, out, R.placement_steps(gdoc, ground))


def checks(rep):
    return sorted({e.split(":", 1)[0] for e in rep.errors})


def test_the_committed_residents_are_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []
    # Split-Bark is 63 (the owner, 2026-10-02): it is no longer let through on a declared leak. Wiremother IS, by
    # the owner's other instruction the same day (L33 -> L30, its tier-2 place's ceiling; build.catch_gate_leak),
    # and whether to keep that leak is still the owner's call. The exact set is pinned, so a new leak fails.
    leaks = {n.split(":")[0] for n in rep.notes if "catch-gate leak" in n}
    assert leaks == {"wiremother"}, leaks


def test_the_record_holds_ten_built_never_placed():
    assert len(DOC["encounters"]) == 10
    assert all(e["status"] == "built_not_placed" for e in DOC["encounters"])
    assert DOC["build"]["step"] == "R18R" and DOC["build"]["pack"] == "cobblers_residents"


def test_a_kill_that_can_reach_a_guardian_is_refused(ground, tmp_path, monkeypatch):
    real = R.resident_files

    def careless(*a, **k):
        fn = real(*a, **k)
        return {n: [l.replace("tag=!cobblers.guardian,", "") if " kill " in l else l for l in v] for n, v in fn.items()}
    monkeypatch.setattr(R, "resident_files", careless)
    assert "blackout" in checks(run(ground, tmp_path))


def test_holding_a_guardian_is_refused(ground, tmp_path, monkeypatch):
    real = R.resident_files

    def grabby(*a, **k):
        fn = real(*a, **k)
        return {n: [l.replace(",tag=!cobblers.guardian] run function", "] run function") for l in v] for n, v in fn.items()}
    monkeypatch.setattr(R, "resident_files", grabby)
    assert "keeper" in checks(run(ground, tmp_path))


def test_a_dressing_sunk_into_the_ground_is_refused(ground, tmp_path, monkeypatch):
    real = R.dressing

    def sunk(e, g, wet):
        sets, clears = real(e, g, wet)
        return [(x, y - 1, z, b, n) for x, y, z, b, n in sets], clears
    monkeypatch.setattr(R, "dressing", sunk)
    assert "writes" in checks(run(ground, tmp_path))


def test_a_block_set_in_the_palms_template_box_is_refused(ground, tmp_path, monkeypatch):
    real = R.dressing

    def crowding(e, g, wet):
        sets, clears = real(e, g, wet)
        if e["id"] == "orchard_sleeper":   # one leaf a block east, into sapling_palm_sunset_east's box (x2814..)
            sets = sets + [(2814, g(2814, 7085) + 2, 7085, "minecraft:oak_leaves[persistent=true]", "crowding")]
        return sets, clears
    monkeypatch.setattr(R, "dressing", crowding)
    # 2026-10-02 the Sleeper moved out from under the palm (2816, 7080 -> 2816, 7128, out of its nest range), so its
    # bbox no longer reaches the palm's box and the bbox guard would refuse the leaf first. Widen the bbox in a copy
    # so the leaf reaches the guard this test is about: the keep-out
    doc = copy.deepcopy(R.load())
    e = next(r for r in doc["encounters"] if r["id"] == "orchard_sleeper")
    bb = e["build"]["bbox"]
    e["build"]["bbox"] = [min(bb[0], 2814), min(bb[1], 7085), max(bb[2], 2814), max(bb[3], 7085)]
    rep = run(ground, tmp_path, doc)
    assert any("orchard_sleeper" in e and "keep-out" in e for e in rep.errors)


def test_a_dressing_that_forgets_the_standing_space_is_refused(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(R, "stand_clears", lambda a, g: [])
    rep = run(ground, tmp_path)
    assert any("standing space" in e for e in rep.errors)


def test_a_spawn_that_ignores_the_presence_gate_is_refused(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(R, "gate_sel", lambda doc, e: "")
    rep = run(ground, tmp_path)
    assert any(e.startswith("keeper:") and "not gated" in e for e in rep.errors)


def test_a_permanently_uncatchable_resident_spawned_catchable_is_refused(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(R, "spawn_props", lambda doc, e: ["level=%d" % int(e["level"])])
    rep = run(ground, tmp_path)
    assert any("whiteback" in e and "uncatchable" in e for e in rep.errors)
    assert any("hornwall" in e and "uncatchable" in e for e in rep.errors)


def test_a_bare_distance_summon_guard_is_refused(ground, tmp_path, monkeypatch):
    real = R.summon_command

    def bare(doc, e, a):
        cmd = real(doc, e, a)
        bare = re.sub(r"(unless entity @e\[type=cobblemon:pokemon,distance=\.\.4),[^\]]*\]", r"\1]", cmd)
        assert bare != cmd
        return bare
    monkeypatch.setattr(R, "summon_command", bare)
    assert "steps" in checks(run(ground, tmp_path))


def test_a_resident_made_exempt_from_the_blackout_is_refused(ground, tmp_path, monkeypatch):
    real = R.resident_files

    def exempt(doc, e, *a, **k):
        fn = real(doc, e, *a, **k)
        fn["%s/bind" % e["id"]].append("tag @s add cobblers.gm")
        return fn
    monkeypatch.setattr(R, "resident_files", exempt)
    assert "blackout" in checks(run(ground, tmp_path))


def test_a_wider_leash_is_refused(ground, tmp_path, monkeypatch):
    real = R.resident_files

    def loose(doc, e, *a, **k):
        e2 = copy.deepcopy(e)
        e2["build"]["leash"] += 4     # the generator's view only: the record on disk is untouched
        return real(doc, e2, *a, **k)
    monkeypatch.setattr(R, "resident_files", loose)
    assert "keeper" in checks(run(ground, tmp_path))


def test_the_generator_refuses_a_stale_anchor(ground):
    doc = copy.deepcopy(R.load())
    doc["encounters"][0]["build"]["anchor"][1] += 1
    with pytest.raises(R.ResidentError):
        R.files(doc, ground)


# Without it, Split-Bark back at Codex's 62 (the Champion's ace) would be catchable between the Elite Four and the
# Champion, the window the owner closed on 2026-10-02, and nothing would say so.
def test_an_undeclared_catch_gate_leak_is_reported(ground, tmp_path):
    doc = copy.deepcopy(DOC)
    for e in doc["encounters"]:
        e["build"].pop("catch_gate_leak", None)
        if e["id"] == "split_bark":
            e["level"] = 62
    rep = run(ground, tmp_path, doc)
    assert any(e.startswith("catch:") and "split_bark" in e for e in rep.errors)


def test_r18r_follows_r17n_and_the_pack_is_world_local(ground, monkeypatch):
    import ambient
    import reapply
    monkeypatch.setattr(reapply, "indexed", lambda *a, **k: [])
    monkeypatch.setattr(ambient, "placement_steps", lambda *a, **k: [])
    ids = [s[0] for s in reapply.steps()]
    assert ids.count("R18R") == 1 and ids.index("R17N") < ids.index("R18R")
    assert "cobblers_residents" in reapply.SERVER_PACKS and "cobblers_residents" in reapply.WORLD_LOCAL
