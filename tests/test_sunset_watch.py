"""tools/sunset_watch_audit.py against tools/sunset_watch.py: the clean pack passes, and a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for the data, the generator, the
audit and the tests), so it is NOT an independent grading of them: the independent half of the proof is the mutation
standard of CLAUDE.md, "How to prove an audit is independent". Every tamper case below changes the generator's CODE (a
function wrapped or replaced, a constant changed) and leaves data/sunset_watch.json and the shared data files alone. A
record-side mutation moves the expectation and the output together and proves nothing. An independent reader should
still re-run the audit and read tools/sunset_watch_audit.py's checks against the record.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT, or .claude/settings.json); a skip names it. NOT covered, and it
needs a running server: that the fills land, that the Habitat Blocks spawn their pools and that the `timeRange` gate
holds in an ACTIVATED block, that the cache grants, that the keeper renders and talks, that the sun sets through the gate.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sunset_watch as L  # noqa: E402
import sunset_watch_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "sunset_watch.json").read_text(encoding="utf-8"))


def jload(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT") or T.env_source_root())
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def run(ground, out):
    doc = L.load()
    written, _pl = L.files(doc, ground)
    L.write(written, out)
    return A.audit(REC, ground, out, L.placement_steps(doc), L.npc_placements(doc, ground))


def checks(rep):
    return sorted({e.split(":", 1)[0] for e in rep.errors})


# ------------------------------------------------------------------------------------------------- the clean pack
def test_the_committed_watch_is_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []


def test_the_pack_is_one_function_that_a_step_runs(ground, tmp_path):
    doc = L.load()
    written, _pl = L.files(doc, ground)
    assert sorted(written) == ["data/cobblers/function/sunset_watch/build.mcfunction", "pack.mcmeta"]
    steps = L.placement_steps(doc)
    assert [s[1] for s in steps if s[0] == "fn"] == ["cobblers:sunset_watch/build"]
    held = [s[1] for s in steps if s[0] == "cmd" and s[1].startswith("forceload add")]
    freed = [s[1] for s in steps if s[0] == "cmd" and s[1].startswith("forceload remove")]
    assert [h.split(" ", 2)[2] for h in held] == [f.split(" ", 2)[2] for f in freed] and len(held) == 2


def test_nothing_in_the_pack_is_a_spawn_condition_chest_or_bed(ground):
    doc = L.load()
    pl = L.plan(doc, ground)
    sb = jload("spawn_blocks.json")["blocks"]
    used = {A.base(s) for s in pl["blocks"].values()}
    assert not (used & set(sb)), used & set(sb)
    assert not [b for b in used if b.endswith("_bed") or b.endswith("chest")]
    assert used <= set(REC["blocks"]["ids"])


def test_the_records_in_the_shared_files_are_what_the_generator_would_write(ground):
    doc = L.load()
    pl = L.plan(doc, ground)
    habs, pools, reward, probes = L.records(doc, pl, {})
    hb = {b["id"]: b for b in jload("habitat_blocks.json")["blocks"]}
    for h in habs:
        assert hb[h["id"]] == h
    sd = jload("spawns.json")
    for pool in pools:
        assert [h for h in sd["habitats"] if h["id"] == pool["habitat"]["id"]] == [pool["habitat"]]
        assert [e for e in sd["entries"] if e.get("scope") == pool["habitat"]["id"]] == pool["entries"]
    assert [r for r in jload("rewards.json")["rewards"] if r["id"] == reward["id"]] == [reward]
    assert jload("world_probes.json")["places"]["sunset_watch"] == probes


def test_the_pools_reach_the_datapack_with_their_time_of_day():
    import compile_spawns as CS
    sd = jload("spawns.json")
    for key, tr in (("dusk", "dusk"), ("day", "day")):
        hab = next(h for h in sd["habitats"] if h["id"] == REC[key]["habitat"])
        flat = [e for e in sd["entries"] if e.get("scope") == REC[key]["habitat"]]
        comp, _s = CS.compile_habitat(hab, flat)
        assert comp["spawns"] and all(s.get("timeRange") == tr for s in comp["spawns"])
    dusk = next(h for h in sd["habitats"] if h["id"] == REC["dusk"]["habitat"])
    assert {e["pokemon"] for e in dusk["entries"]} == {"dreepy", "lycanroc dusk", "drakloak"}


def test_the_keeper_and_the_rumours_exist():
    dl = jload("dialogue.json")
    conv = next(c for c in dl["conversations"] if c["id"] == REC["npc"]["conversation"])
    assert conv["nodes"][-1]["id"] == "repeat" and conv["nodes"][-1]["next"] == "repeat"
    fe = jload("ferries.json")
    docks = {d["id"]: d for d in fe["docks"]}
    assert "Watch" in docks["sunset_south_pier"]["ferryman"]["greeting"]
    assert "Watch" in docks["sunset_isle_landing"]["ferryman"]["greeting"]
    # the rumour tells the truth about the direction: west of the landing, and the sea on the right walking west
    assert "west" in docks["sunset_isle_landing"]["ferryman"]["greeting"].lower()


def test_the_place_is_empty_of_other_authored_data_within_150(ground):
    cx, cz = REC["site"]["centre"]
    mine = {"sunset_watch.json", "habitat_blocks.json", "spawns.json", "rewards.json", "world_probes.json", "dialogue.json",
            "progression.json", "quests.json", "regions.json", "system_contracts.json", "id_authorship.json"}
    hits = []

    def walk(o, f, p):
        if isinstance(o, dict):
            if isinstance(o.get("x"), (int, float)) and isinstance(o.get("z"), (int, float)):
                if abs(o["x"] - cx) <= 150 and abs(o["z"] - cz) <= 150:
                    hits.append((f, p))
            for k, v in o.items():
                walk(v, f, p + "/" + k)
        elif isinstance(o, list):
            if len(o) in (2, 3) and all(isinstance(v, (int, float)) for v in o):
                px, pz = (o[0], o[1]) if len(o) == 2 else (o[0], o[2])
                if abs(px - cx) <= 150 and abs(pz - cz) <= 150:
                    hits.append((f, p))
            for i, v in enumerate(o):
                walk(v, f, p + "[%d]" % i)
    data = ROOT / "data"
    for f in sorted(list(data.glob("*.json")) + list(data.glob("*/*.json"))):
        if f.name in mine:
            continue
        try:
            walk(json.loads(f.read_text(encoding="utf-8")), f.name, "")
        except (ValueError, UnicodeDecodeError):
            continue
    assert hits == []


def test_reapply_runs_the_watch_before_the_habitat_blocks_and_the_keeper_after_r17n():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    order = [src.index(s) for s in ('("R9SO"', '("R9SW"', '("R9E"', '("R17N"', '("R18SO"', '("R18SW"')]
    assert order == sorted(order)
    assert '"cobblers_sunset_watch"' in src
    assert 'add("sunset_watch:build"' in src and 'add("sunset_watch_audit"' in src


def test_the_probes_name_the_world_the_pack_builds(ground):
    doc = L.load()
    pl = L.plan(doc, ground)
    probes = jload("world_probes.json")["places"]["sunset_watch"]
    blocks = pl["blocks"]
    for pr in probes:
        if "block" not in pr:
            continue
        x, y, z, want = pr["block"]
        have = blocks.get((x, y, z))
        assert have is not None, pr["what"]
        assert have.startswith(want.rstrip("]").split("[")[0]), (pr["what"], have, want)
        if "[" in want:
            assert want.rstrip("]").split("[")[1] in have, (pr["what"], have, want)


# ------------------------------------------------------------------------------------------- generator mutations
def test_a_terrace_laid_a_block_too_high_is_caught(ground, tmp_path, monkeypatch):
    orig = L.terrace_level
    monkeypatch.setattr(L, "terrace_level", lambda p: orig(p) + 1)
    rep = run(ground, tmp_path)
    assert {"dial", "terrace", "hut"} & set(checks(rep))


def test_a_terrace_with_no_foundation_is_caught(ground, tmp_path, monkeypatch):
    orig = L.paving

    def paving(p, P):
        orig(p, P)
        for k in [k for k in p.solid if k[1] < P and p.doc["terrace"]["lx"][0] <= k[0] - p.cx <= p.doc["terrace"]["lx"][1]
                  and p.doc["terrace"]["lz"][0] <= k[2] - p.cz <= p.doc["terrace"]["lz"][1]]:
            p.solid.pop(k)
    monkeypatch.setattr(L, "paving", paving)
    rep = run(ground, tmp_path)
    assert "terrace" in checks(rep)


def test_a_pillar_one_block_short_is_caught(ground, tmp_path, monkeypatch):
    orig = L.gate

    def gate(p, P):
        orig(p, P)
        gt = p.doc["gate"]
        x, z = p.W(gt["lx"][0], gt["pillar_lz"][0][0])
        p.solid.pop((x, P + gt["height"], z), None)
    monkeypatch.setattr(L, "gate", gate)
    rep = run(ground, tmp_path)
    assert "gate" in checks(rep)


def test_a_gate_blocked_in_the_sightline_is_caught(ground, tmp_path, monkeypatch):
    orig = L.benches

    def benches(p, P):
        orig(p, P)
        x, z = p.W(0, p.doc["dial"]["centre"][1])
        p.put(x, P + 2, z, "minecraft:stone_bricks")        # a block at head height on the axis
    monkeypatch.setattr(L, "benches", benches)
    rep = run(ground, tmp_path)
    assert "gate" in checks(rep)


def test_a_bench_turned_round_is_caught(ground, tmp_path, monkeypatch):
    def benches(p, P):
        b = p.doc["benches"]
        for lx in b["rows_lx"]:
            for lo, hi in b["groups_lz"]:
                for lz in range(lo, hi + 1):
                    x, z = p.W(lx, lz)
                    p.put(x, P + 1, z, L.stairs("stone_brick", "west"))
    monkeypatch.setattr(L, "benches", benches)
    rep = run(ground, tmp_path)
    assert "benches" in checks(rep)


def test_a_barrel_moved_out_of_its_cache_is_caught(ground, tmp_path, monkeypatch):
    orig = L.hut

    def hut(p, P):
        hf, ridge, barrel, trig = orig(p, P)
        p.put(barrel[0], barrel[1], barrel[2], "minecraft:air")
        p.put(barrel[0] - 1, barrel[1], barrel[2] + 1, "minecraft:barrel[facing=up,open=false]")
        return hf, ridge, (barrel[0] - 1, barrel[1], barrel[2] + 1), trig
    monkeypatch.setattr(L, "hut", hut)
    rep = run(ground, tmp_path)
    assert {"hut", "find"} & set(checks(rep))


def test_leaves_that_decay_are_caught(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LEAVES", "minecraft:acacia_leaves[persistent=false,waterlogged=false]")
    rep = run(ground, tmp_path)
    assert "blocks" in checks(rep)


def test_a_waymark_facing_the_wrong_way_is_caught(ground, tmp_path, monkeypatch):
    orig = L.landing_post

    def post(p):
        r = orig(p)
        for k, s in list(p.hung.items()):
            if s.startswith("minecraft:spruce_sign"):
                p.hung[k] = s.replace("rotation=8", "rotation=0")
        return r
    monkeypatch.setattr(L, "landing_post", post)
    rep = run(ground, tmp_path)
    assert "landing" in checks(rep)


def test_posts_without_lanterns_are_caught(ground, tmp_path, monkeypatch):
    def post(p, x, y, z):
        p.put(x, y, z, L.FENCE)
        p.put(x, y + 1, z, L.FENCE)
    monkeypatch.setattr(L, "lantern_post", post)
    rep = run(ground, tmp_path)
    assert "attached" in checks(rep)


def test_a_mast_a_block_short_is_caught(ground, tmp_path, monkeypatch):
    orig = L.mast

    def mast(p, P):
        r = orig(p, P)
        x, z = p.W(*p.doc["mast"]["at"])
        p.solid.pop((x, P + p.doc["mast"]["height"], z), None)
        return r
    monkeypatch.setattr(L, "mast", mast)
    rep = run(ground, tmp_path)
    assert "mast" in checks(rep)


def test_a_stair_run_that_starts_a_block_low_is_caught(ground, tmp_path, monkeypatch):
    orig = L.stair_run

    def run_(p, P):
        return orig(p, P - 1)
    monkeypatch.setattr(L, "stair_run", run_)
    rep = run(ground, tmp_path)
    assert "stairs" in checks(rep)


def test_a_hut_without_a_roof_over_a_corner_is_caught(ground, tmp_path, monkeypatch):
    orig = L.hut

    def hut(p, P):
        r = orig(p, P)
        hx, hz = p.W(*p.doc["hut"]["centre"])
        h = p.doc["hut"]["half"]
        for k in [k for k in list(p.solid) if k[0] in (hx + 1, hx + 2) and k[2] in (hz + 1, hz + 2) and k[1] > r[0] + p.doc["hut"]["wall_height"]]:
            p.solid.pop(k)
        return r
    monkeypatch.setattr(L, "hut", hut)
    rep = run(ground, tmp_path)
    assert "hut" in checks(rep)


def test_a_dusk_pool_that_lost_its_time_of_day_is_caught(ground, tmp_path, monkeypatch):
    import compile_spawns as CS
    orig = CS.compile_habitat

    def compile_habitat(h, entries):
        doc, s = orig(h, entries)
        for sp in doc["spawns"]:
            sp.pop("timeRange", None)
        return doc, s
    monkeypatch.setattr(CS, "compile_habitat", compile_habitat)
    rep = A.audit(REC, ground, _built(ground, tmp_path), L.placement_steps(), L.npc_placements(None, ground))
    assert "habitat" in checks(rep)


def _built(ground, out):
    doc = L.load()
    written, _pl = L.files(doc, ground)
    L.write(written, out)
    return out
