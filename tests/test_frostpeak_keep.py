"""tools/frostpeak_keep.py and its audit tools/frostpeak_keep_audit.py: Wardenhold, the snow-covered keep on Frostpeak
Strand's southern lip, sited to be seen from Highwire.

Written by the agent that wrote the generator, the audit and the siting tool (2026-10-09), disclosed: the repository
prefers a different author for a validator, and the audit should be re-read by someone else. To keep it from sharing the
generator's derivation it imports nothing from the generator (asserted below), takes the courtyard floor from the
heightmap rather than from the pack, the observers from data/towns.json and data/placements.json, the polygon from
data/regions.json, and walks the written blocks with a model of its own.

Mutations are of the GENERATOR (monkeypatched functions and constants of tools/frostpeak_keep.py), never of the record:
data/frostpeak_keep.json is never edited here. Each mutation must make the named audit check fail.

NOT COVERED: anything in a running server (the integrating session's probes, from `python tools/frostpeak_keep.py plan`),
whether the Habitat Blocks spawn what the pools say (nothing here was run in game), how the keep looks as a Distant
Horizons LOD at 800 blocks, and tools/reapply.py's own steps() (it needs `reapply.py prepare`, which a worktree has not
run): the order is asserted from the source text.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import frostpeak_keep as K  # noqa: E402
import frostpeak_keep_audit as A  # noqa: E402

FN_REL = "data/cobblers/function/frostpeak_keep/build.mcfunction"


def data(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    from terrain import TerrainUnavailable
    try:
        return G.load()
    except TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])


@pytest.fixture(scope="module")
def clean(ground, tmp_path_factory):
    out = tmp_path_factory.mktemp("keep")
    files, p = K.build(ground)
    K.write(files, out)
    return out, files, p


def built(g, tmp):
    files, p = K.build(g)
    K.write(files, tmp)
    return files, p


def failing(rep):
    return {r["check"].split(" ")[0] for r in rep.problems}


# ------------------------------------------------------------------------------------------------ the clean build
def test_the_clean_build_passes_the_independent_audit(ground, clean):
    out, _files, _p = clean
    rep = A.audit(out, ground)
    assert not rep.problems, rep.problems
    assert len(rep.rows) >= 25
    assert rep.counts["blocks"] > 60000 and rep.counts["signs"] == 7


def test_the_build_is_deterministic(ground, clean, tmp_path):
    _out, files, _p = clean
    again, _ = built(ground, tmp_path)
    assert again[FN_REL] == files[FN_REL]


def test_the_audit_imports_nothing_from_the_generator():
    text = (ROOT / "tools" / "frostpeak_keep_audit.py").read_text(encoding="utf-8")
    assert "import frostpeak_keep\n" not in text and "from frostpeak_keep " not in text
    assert "frostpeak_keep as" not in text


def test_a_truncated_pack_is_reported_not_crashed_on(ground, clean, tmp_path):
    out, files, _p = clean
    lines = files[FN_REL]
    half = {"pack.mcmeta": files["pack.mcmeta"], FN_REL: lines[: len(lines) // 2]}
    K.write(half, tmp_path)
    rep = A.audit(tmp_path, ground)
    assert rep.problems and failing(rep) & {"K5", "K7", "K9", "K11"}


def test_the_pad_is_the_highest_ground_under_the_base_rectangle(ground, clean):
    _out, _files, p = clean
    doc = K.load()
    x0, z0, x1, z1 = K.base_rect(doc)
    assert p["info"]["pad"] == max(ground(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    assert p["info"]["pad"] - p["info"]["min_ground"] >= 10, "the test expects a real plinth under the north side"


def test_the_whole_build_is_one_function_and_every_command_is_one_the_server_runs(clean):
    out, _files, _p = clean
    fns = sorted((out / "data").glob("*/function/**/*.mcfunction"))
    assert len(fns) == 1
    import function_limits
    assert not function_limits.check_file(fns[0])


# ------------------------------------------------------------------------------------------------ the siting claim
def test_the_chosen_lip_is_seen_from_highwire_and_nothing_else_on_the_strand_is(ground):
    import frostpeak_keep_siting as S
    s = S.Siting(ground)
    pad, st, gy = s.fractions(*K.load()["site"]["centre"])
    assert sum(st) / len(st) >= 0.2 and min(st) >= 0.1, (sum(st) / len(st), min(st))
    assert max(gy) >= 0.3
    for name, (cx, cz) in S.ALTERNATIVES[2:]:           # the other Strand sites: A is the lip, B its own shoulder
        _p, st2, gy2 = s.fractions(cx, cz)
        assert max(st2) < 0.05, "%s is seen from the streets (%s): the lip is not the only site" % (name, max(st2))


def test_the_site_is_inside_the_strand_and_clear_of_every_authored_place(ground):
    pad, bad = K.siting(K.load(), ground)
    assert not bad, bad


# ------------------------------------------------------------------------------------------------ the spawn system
def test_the_habitat_blocks_sit_in_the_cells_the_pack_reserves_and_name_pools_that_exist(ground, clean):
    _out, _files, p = clean
    doc = K.load()
    cells = K.habitat_cells(doc, p["info"]["pad"])
    blocks = {b["id"]: b for b in data("habitat_blocks.json")["blocks"]}
    spawns = data("spawns.json")
    pools = {h["id"]: h for h in spawns["habitats"]}
    for rid, cell in (("frostpeak_keep_hall_ward", cells["hall"]), ("frostpeak_keep_beacon_ward", cells["beacon"])):
        b = blocks[rid]
        assert (b["position"]["x"], b["position"]["y"], b["position"]["z"]) == cell, rid
        assert b["style"] == "activated" and b["status"] == "planned" and b["replace_spawns"] is False
        assert b["pool"].split(":")[1] in pools and b["mimic"] == "minecraft:stone_bricks"
        assert p["blocks"][cell] == "minecraft:stone_bricks", "the pack must write the mimic floor under the block"


def test_the_pools_follow_the_band_and_the_next_cap():
    spawns = data("spawns.json")
    design = data("encounter_design.json")
    band = next(s for s in spawns["subregions"] if s["id"] == "frostpeak_strand")["level_band"]
    nxt = design["rules"]["hearts"]["next_cap"][str(design["tables"]["frostpeak_strand"]["tier"])]
    hall = next(h for h in spawns["habitats"] if h["id"] == "frostpeak_keep_hall")
    beacon = next(h for h in spawns["habitats"] if h["id"] == "frostpeak_keep_beacon")
    assert hall["level_band"] == {"minimum": band["minimum"], "maximum": band["maximum"]}
    assert all(e["level"] == "%d-%d" % (band["minimum"], band["maximum"]) for e in hall["entries"])
    lo, hi = beacon["level_band"]["minimum"], beacon["level_band"]["maximum"]
    assert band["maximum"] < lo <= hi < nxt, "the one boss-strength creature is above the band and under the next cap"
    flat = [e for e in spawns["entries"] if e["mechanism"] == "habitat_block" and e["scope"].startswith("frostpeak_keep_")]
    assert {e["scope"] for e in flat} == {"frostpeak_keep_hall", "frostpeak_keep_beacon"}
    for e in flat:
        pool = hall if e["scope"] == "frostpeak_keep_hall" else beacon
        assert e["species"] in [x["pokemon"] for x in pool["entries"]] and e["level"] in [x["level"] for x in pool["entries"]]
    assert len(beacon["entries"]) == 1 and beacon["entries"][0]["pokemon"] == "froslass"


def test_the_nuzlocke_file_lists_both_unplaced_pools():
    nz = data("nuzlocke_zones.json")
    names = [z["zone"] for z in nz["not_zones"]]
    assert "frostpeak_keep_hall" in names and "frostpeak_keep_beacon" in names
    assert nz["counts"]["not_zones"] == len(nz["not_zones"])


# ------------------------------------------------------------------------------------------------ the probes and the step
def test_the_registered_probes_are_what_the_generator_writes(ground, clean):
    _out, _files, p = clean
    mine = data("world_probes.json")["places"]["frostpeak_keep"]
    assert mine == K.probes(p, K.load())
    assert len(mine) >= 6 and all(q["expect"] is True and len(q["block"]) == 4 for q in mine)


def test_the_step_holds_the_chunks_runs_the_function_and_releases():
    steps = K.placement_steps()
    assert steps[0][0] == "cmd" and steps[0][1].startswith("forceload add ")
    assert steps[2] == ("fn", "cobblers:frostpeak_keep/build") and steps[3][1].startswith("forceload remove ")
    x0, z0, x1, z1 = K.hold_box()
    assert ((x1 - x0) // 16 + 1) * ((z1 - z0) // 16 + 1) <= 256


def test_reapply_runs_the_keep_before_the_habitat_blocks_and_registers_its_pack_and_jobs():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    steps_src = src.split("\ndef steps(")[1].split("\ndef ")[0]
    assert steps_src.index('"R9FK"') < steps_src.index('"R9E"'), "R9FK would lay stone bricks over R9E's blocks"
    assert '"cobblers_frostpeak_keep"' in src
    assert 'add("frostpeak_keep:build", "frostpeak_keep.py", "build", *src)' in src
    assert 'add("frostpeak_keep_audit", "frostpeak_keep_audit.py", *src)' in src


def test_the_step_is_in_steps_before_r9e_once_steps_can_be_built(monkeypatch):
    import reapply
    monkeypatch.setattr(reapply, "indexed", lambda *a, **k: ["stub"])
    try:
        steps = reapply.steps()
    except SystemExit as e:                   # a worktree has no derived/ or build/ (CLAUDE.md): reapply fails closed
        pytest.skip("NOT_EXECUTED: tools/reapply.py steps() could not be built here: %s" % str(e)[:100])
    ids = [s[0] for s in steps]
    assert "R9FK" in ids and ids.index("R9FK") < ids.index("R9E")
    assert not [m for m in reapply.uncovered(steps) if "frostpeak_keep" in m]


# ------------------------------------------------------------------------------------------------ mutations of the generator
def mutate_building(monkeypatch, fn):
    orig = K.building

    def wrapped(doc):
        V, notes = orig(doc)
        fn(V)
        return V, notes
    monkeypatch.setattr(K, "building", wrapped)


def test_a_lopped_spire_is_caught(ground, tmp_path, monkeypatch):
    def lop(V):
        for k in [k for k in V.b if k[1] > 45]:
            del V.b[k]
    mutate_building(monkeypatch, lop)
    built(ground, tmp_path)
    assert failing(A.audit(tmp_path, ground)) & {"K6", "K7", "K9"}


def test_a_clear_box_that_stops_short_is_caught(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(K, "CLEAR_TOP_CUT", 90)
    built(ground, tmp_path)
    assert "K1" in failing(A.audit(tmp_path, ground))


def test_a_pad_cut_into_the_hill_is_caught(ground, tmp_path, monkeypatch):
    orig = K.siting
    monkeypatch.setattr(K, "siting", lambda doc, g: (orig(doc, g)[0] - 3, []))
    built(ground, tmp_path)
    assert "K1" in failing(A.audit(tmp_path, ground))


def test_a_ladder_left_out_cuts_off_the_beacon(ground, tmp_path, monkeypatch):
    orig = K.Vox.put
    monkeypatch.setattr(K.Vox, "put", lambda self, u, y, v, s: None if s.startswith("minecraft:ladder") else orig(self, u, y, v, s))
    built(ground, tmp_path)
    assert "K9" in failing(A.audit(tmp_path, ground))


def test_stairs_left_out_cut_off_the_upper_floors(ground, tmp_path, monkeypatch):
    orig = K.Vox.put
    monkeypatch.setattr(K.Vox, "put", lambda self, u, y, v, s: None if s.startswith("minecraft:stone_brick_stairs") else orig(self, u, y, v, s))
    built(ground, tmp_path)
    assert "K9" in failing(A.audit(tmp_path, ground))


def test_a_spawn_condition_block_is_caught(ground, tmp_path, monkeypatch):
    orig = K.pyramid

    def bad(V, doc, *a, **k):
        r = orig(V, doc, *a, **k)
        for key, s in list(V.b.items()):
            if s == doc["palette"]["roof_trim"]:
                V.b[key] = "minecraft:white_concrete"
        return r
    monkeypatch.setattr(K, "pyramid", bad)
    built(ground, tmp_path)
    assert "K4" in failing(A.audit(tmp_path, ground))


def test_a_lantern_is_caught(ground, tmp_path, monkeypatch):
    mutate_building(monkeypatch, lambda V: V.put(0, 2, 0, "minecraft:lantern"))
    built(ground, tmp_path)
    assert "K4" in failing(A.audit(tmp_path, ground))


def test_a_cone_that_floats_above_its_tower_is_caught(ground, tmp_path, monkeypatch):
    orig = K.pyramid
    monkeypatch.setattr(K, "pyramid", lambda V, doc, cu, cv, y0, *a, **k: orig(V, doc, cu, cv, y0 + 3, *a, **k))
    built(ground, tmp_path)
    assert "K5" in failing(A.audit(tmp_path, ground))


def test_roofs_that_are_not_snow_are_caught(ground, tmp_path, monkeypatch):
    orig = K.pyramid

    def grey(V, doc, *a, **k):
        r = orig(V, doc, *a, **k)
        for key, s in list(V.b.items()):
            if s in (doc["palette"]["roof"], doc["palette"]["roof_trim"]):
                V.b[key] = "minecraft:cobbled_deepslate"
        return r
    monkeypatch.setattr(K, "pyramid", grey)
    built(ground, tmp_path)
    assert "K6" in failing(A.audit(tmp_path, ground))


def test_a_sign_line_too_long_is_caught(ground, tmp_path, monkeypatch):
    orig = K.Vox.sign
    monkeypatch.setattr(K.Vox, "sign", lambda self, u, y, v, f, lines: orig(self, u, y, v, f, [lines[0] + " and a long tail"] + list(lines[1:])))
    built(ground, tmp_path)
    assert "K4" in failing(A.audit(tmp_path, ground))


def test_a_plinth_that_ends_above_the_hill_is_refused(ground, monkeypatch):
    monkeypatch.setattr(K, "load", lambda: dict(json.loads(K.DATA.read_text(encoding="utf-8")),
                                                 dims=dict(json.loads(K.DATA.read_text(encoding="utf-8"))["dims"], batter_reach=6)))
    with pytest.raises(SystemExit):
        K.plan(K.load(), ground)
