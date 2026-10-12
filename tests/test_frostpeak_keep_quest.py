"""tools/frostpeak_keep_quest.py and its audit tools/frostpeak_keep_quest_audit.py: Wardenhold's people in their burrow
on Mt Vessu's face, Giratina in the ruined keep's yard, the quest to beat it, and the old Distortion shrine taken down.

Written by the agent that wrote the generator and the audit (2026-10-09), disclosed: the repository prefers a different
author for a validator, and the audit should be re-read by someone else. The audit imports nothing from either
generator (asserted below): the lair comes from the keep's record and the heightmap, the shrine's box from its retired
placement record, the light from its own propagation, the walk from its own model.

Mutations are of the GENERATOR (monkeypatched functions of tools/frostpeak_keep_quest.py), never of the record.

NOT COVERED: anything in a running server. That Giratina sleeps and wakes, that battle_fainted reaches every player of
a multi-player wild battle, that the capture gate refuses in play, that the residents stand and talk, and that the
shrine's site looks right afterwards (its top block is stone: the trough's painted cover is in no data file).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import frostpeak_keep_quest as Q  # noqa: E402
import frostpeak_keep_quest_audit as A  # noqa: E402

FN = "data/cobblers/function/frostpeak_keep_quest/"


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
    out = tmp_path_factory.mktemp("quest")
    fs = Q.files(Q.load(), ground)
    Q.write(fs, out)
    return out, fs


def built(g, tmp):
    fs = Q.files(Q.load(), g)
    Q.write(fs, tmp)
    return fs


def failing(rep):
    return {r["check"].split(" ")[0] for r in rep.problems}


# ------------------------------------------------------------------------------------------------ the clean build
def test_the_clean_build_passes_the_independent_audit(ground, clean):
    out, _fs = clean
    rep = A.audit(out, ground)
    assert not rep.problems, rep.problems
    assert len(rep.rows) >= 25
    assert rep.facts["burrow_cells_reached"] > 300 and rep.facts["least_light"] >= 1
    assert set(rep.facts["residents"]) == {"maren", "sef", "pell"}


def test_the_build_is_deterministic(ground, clean, tmp_path):
    _out, fs = clean
    assert built(ground, tmp_path) == fs


def test_the_audit_imports_nothing_from_the_generators():
    text = (ROOT / "tools" / "frostpeak_keep_quest_audit.py").read_text(encoding="utf-8")
    for mod in ("frostpeak_keep_quest", "frostpeak_keep"):
        assert "import %s" % mod not in text and "from %s " % mod not in text


def test_a_truncated_pack_is_reported_not_crashed_on(ground, clean, tmp_path):
    _out, fs = clean
    fs = dict(fs)
    rel = FN + "burrow/build.mcfunction"
    lines = fs[rel].splitlines()
    fs[rel] = "\n".join(lines[: len(lines) // 3]) + "\n"
    Q.write(fs, tmp_path)
    assert failing(A.audit(tmp_path, ground)) & {"Q1", "Q3"}


# ------------------------------------------------------------------------------------------------ the decisions
def test_giratina_is_level_50_to_60_at_the_cap_after_seven_badges():
    lv = Q.load()["giratina"]["level"]
    aces = data("trainers.json")["generation_contract"]["gym_ace_levels"]
    assert 50 <= lv <= 60 and lv == aces[7]
    assert data("legendaries.json")["level_caps"]["upper_bound_by_badges"]["7"] == lv


def test_giratina_takes_ordinary_balls():
    # the owner, 2026-10-08: only dungeon bosses take the Beast Ball key; overworld legendaries stay catchable
    kb = (ROOT / "data" / "key_ball.json").read_text(encoding="utf-8")
    assert Q.load()["giratina"]["tag"] not in kb


def test_the_shrine_is_retired_everywhere_a_builder_reads():
    pl = data("placements.json")
    assert "legendary_giratina_shrine" not in {p.get("id") for p in pl["placements"]}
    assert "legendary_giratina_shrine" in {p.get("id") for p in pl["superseded_placements"]["records"]}
    assert "sweep_giratina_shrine" not in {s["id"] for s in data("adopted_legendary_sites.json")["sweep_sites"]}
    live = {r["id"] for r in data("rewards.json")["rewards"]}
    assert not live & {"sweep_red_chain", "giratina_griseous"}


def test_the_griseous_items_keep_one_source():
    items = {"mega_showdown:griseous_core", "mega_showdown:griseous_orb"}
    givers = [r["id"] for r in data("rewards.json")["rewards"] for c in r["contents"] if c["item"] in items]
    assert sorted(givers) == ["wardenhold_giratina", "wardenhold_giratina"]


def test_the_dialogue_compiles_and_reads_the_tag_the_pack_sets(clean):
    import compile_dialogue as CD
    dl = {c["id"]: c for c in data("dialogue.json")["conversations"]}
    qs = {q["id"]: q for q in data("quests.json")["quests"]}
    fields = {f["id"]: f for f in data("progression.json")["quest_fields"]}
    for r in Q.load()["residents"]:
        conv = dl[r["conversation"]]
        out = CD.Compiler(conv, qs[conv["quest_id"]], fields)
        assert out is not None
    tag = Q.load()["quest"]["beaten_tag"]
    assert ("tag @s add %s" % tag) in clean[1][FN + "giratina/fainted.mcfunction"]
    assert tag in json.dumps(dl["dlg_wardenhold_maren"])


# ------------------------------------------------------------------------------------------------ the step and the probes
def test_the_step_takes_the_shrine_down_digs_summons_and_places_three_residents(ground):
    steps = Q.placement_steps(Q.load(), ground)
    fns = [v for k, v in steps if k == "fn"]
    assert fns[:3] == ["cobblers:frostpeak_keep_quest/shrine_takedown", "cobblers:frostpeak_keep_quest/burrow/build",
                       "cobblers:frostpeak_keep_quest/place"]
    assert [v[0] for k, v in steps if k == "npc"] == ["dlg_wardenhold_maren", "dlg_wardenhold_sef", "dlg_wardenhold_pell"]
    for k, v in steps:
        if k == "cmd" and v.startswith("forceload add"):
            x0, z0, x1, z1 = (int(t) for t in v.split()[2:6])
            assert ((x1 // 16) - (x0 // 16) + 1) * ((z1 // 16) - (z0 // 16) + 1) <= 256


def test_reapply_registers_the_pack_its_jobs_and_r18fk_after_r9fk():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert src.count('"cobblers_frostpeak_keep_quest"') == 2          # SERVER_PACKS and WORLD_LOCAL
    assert 'add("frostpeak_keep_quest:build", "frostpeak_keep_quest.py", "build", *src)' in src
    assert 'add("frostpeak_keep_quest_audit", "frostpeak_keep_quest_audit.py", *src)' in src
    steps_src = src.split("\ndef steps(")[1].split("\ndef ")[0]
    assert steps_src.index('"R9FK"') < steps_src.index('"R18FK"')


def test_the_registered_probes_are_what_the_generator_writes(ground):
    assert data("world_probes.json")["places"]["frostpeak_keep_quest"] == Q.probes(Q.load(), ground)


def test_the_burrow_is_spawn_free():
    z = next(z for z in data("spawn_suppression.json")["spawn_free_zones"] if z["id"] == "wardenhold_burrow")
    x0, z0, x1, z1 = z["box"]
    for r in Q.load()["burrow"]["rooms"]:
        bx0, bz0, bx1, bz1 = r["box"]
        assert x0 <= bx0 and bx1 <= x1 and z0 <= bz0 and bz1 <= z1, r["id"]


# ------------------------------------------------------------------------------------------------ mutations of the generator
def test_lanterns_left_out_leave_the_burrow_dark(ground, tmp_path, monkeypatch):
    orig = Q.burrow_blocks

    def dark(doc, g):
        W, S = orig(doc, g)
        return {k: ("minecraft:air" if v.startswith("minecraft:lantern") or "campfire" in v else v) for k, v in W.items()}, S
    monkeypatch.setattr(Q, "burrow_blocks", dark)
    built(ground, tmp_path)
    assert "Q3" in failing(A.audit(tmp_path, ground))


def test_a_resident_walled_in_is_caught(ground, tmp_path, monkeypatch):
    orig = Q.burrow_blocks
    x, z = next(r["at_xz"] for r in Q.load()["residents"] if r["id"] == "pell")

    def walled(doc, g):
        W, S = orig(doc, g)
        fy = doc["burrow"]["floor_y"]
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if (dx, dz) != (0, 0):
                    W[(x + dx, fy + 1, z + dz)] = W[(x + dx, fy + 2, z + dz)] = "minecraft:stone"
        return W, S
    monkeypatch.setattr(Q, "burrow_blocks", walled)
    built(ground, tmp_path)
    assert "Q1" in failing(A.audit(tmp_path, ground))


def test_a_burrow_dug_toward_the_surface_is_caught(ground, tmp_path, monkeypatch):
    # a shaft dug up from the hall's middle to two blocks under the face's surface: a crust no one should walk under
    orig = Q.rooms
    hx, hz = Q.load()["burrow"]["hearth"]
    sx, sz = hx + 3, hz + 3

    def tall(doc):
        air, floor = orig(doc)
        return air | {(sx, y, sz) for y in range(doc["burrow"]["floor_y"] + 1, ground(sx, sz) - 1)}, floor
    monkeypatch.setattr(Q, "rooms", tall)
    monkeypatch.setattr(Q, "checks", lambda doc, g, W: [])         # past the builder's own refusal, to reach the audit
    built(ground, tmp_path)
    assert "Q2" in failing(A.audit(tmp_path, ground))


def test_a_first_player_only_credit_is_caught(ground, tmp_path, monkeypatch):
    orig = Q.callback_files

    def first_only(doc):
        out = orig(doc)
        k = Q.CALLBACKS % "battle_fainted"
        out[k] = out[k].replace("    for_each(t.a, c.players, {", "    t.done = 0;\n    for_each(t.a, c.players, {")
        return out
    monkeypatch.setattr(Q, "callback_files", first_only)
    built(ground, tmp_path)
    assert "Q6" in failing(A.audit(tmp_path, ground))


def test_a_catch_gate_that_forgets_the_one_catch_is_caught(ground, tmp_path, monkeypatch):
    orig = Q.giratina_files

    def lax(doc, p):
        fn = orig(doc, p)
        fn["catch_check"] = [l for l in fn["catch_check"] if "giratina_caught=true}] run tag" not in l]
        return fn
    monkeypatch.setattr(Q, "giratina_files", lax)
    built(ground, tmp_path)
    assert "Q6" in failing(A.audit(tmp_path, ground))


def test_a_giratina_summoned_off_its_lair_is_caught(ground, tmp_path, monkeypatch):
    orig = Q.spot
    monkeypatch.setattr(Q, "spot", lambda g: (orig(g)[0] + 1, orig(g)[1], orig(g)[2]))
    built(ground, tmp_path)
    assert "Q5" in failing(A.audit(tmp_path, ground))


def test_a_takedown_that_leaves_the_slab_is_caught(ground, tmp_path, monkeypatch):
    orig = Q.shrine_lines

    def partial(doc, g, wet=None):
        lines, rep = orig(doc, g, wet)
        return [l for l in lines if not l.endswith("minecraft:stone")], rep
    monkeypatch.setattr(Q, "shrine_lines", partial)
    built(ground, tmp_path)
    assert "Q8" in failing(A.audit(tmp_path, ground))
