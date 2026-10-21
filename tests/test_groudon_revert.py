"""The quake cavern undone and Groudon's sealed chamber back (the owner, 2026-10-21: "undo groudon cave", "Old chamber back").

What breaks without these: the cleanup R14L runs first could leave a void, lava or a rim wall in the Craters, bury a
player standing in the hall, write into an unloaded chunk (and silently do nothing), kill the wrong Groudon, run twice and
re-seal a chamber opened since, or let the old cavern's runtime keep cutting and ejecting. Each property is checked two
ways: by tools/groudon_revert_audit.py, which replays what the world received and then the cleanup onto the heightmap
without importing the generator, and by tests/mcfunction_sim.py running the emitted chain as R14L runs it.

Mutations change the GENERATOR (tools/groudon_cavern.py, the functions it calls), never the data, and each must make the
audit fail with its own message (CLAUDE.md "How to prove an audit is independent").

The same session wrote the generator, the audit and these tests (the brief asked for all three); the audit's independence
rests on its replay of the frozen record and on the heightmap, not on authorship.

NOT COVERED (needs a running server): that the chain's look sees the real Groudon, that `kill` takes it, that 88 force-loaded
chunks load in the chain's wait, that the fills land, and what a player sees.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import chunk_look as CL  # noqa: E402
import groudon_cavern as GC  # noqa: E402
import groudon_revert_audit as RA  # noqa: E402
import legendaries as L  # noqa: E402
import mcfunction_sim as S  # noqa: E402
from test_legendaries_rerun import functions, run_steps, world  # noqa: E402

BASE = "cobblers:legendary/groudon/retire_quake_cavern_v1"
HOLDER = "#legret_groudon_quake_cavern_v1"


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("NOT_EXECUTED: the canonical heightmap is unusable: %s" % e)


@pytest.fixture
def doc():
    return L.load()


def emit(doc, ground, out):
    """Both generators into a scratch tree: build/datapacks/cobblers_legendaries and the record of what was applied."""
    pack = out / "datapacks" / "cobblers_legendaries"
    for rel, text in L.files(doc, ground).items():
        f = pack / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    gdoc = GC.load()
    GC._PLANS.clear()
    GC.write_applied(gdoc, GC.plan(gdoc, ground), ground, out / "applied")
    return pack, out / "applied"


def run_audit(doc, ground, tmp_path):
    pack, applied = emit(doc, ground, tmp_path)
    return RA.audit(pack, applied, ground, leg=doc)


def failing(rep, text):
    return [e for e in rep.errors if text in e]


# --------------------------------------------------------------------------------------------------------- the data


def test_the_record_is_the_sealed_chamber_with_its_original_numbers(doc):
    # git show 9d764bcc^:data/legendaries.json, groudon; written out here, not read from the audit
    rec = next(r for r in doc["encounters"] if r["id"] == "groudon")
    assert rec["kind"] == "sealed_chamber" and rec["status"] == "sited"
    assert rec["portal"] == [6672, 5508]
    assert rec["approach"] == {"bearing_deg": 180, "drop": 40, "passage": 14}
    assert rec["chamber"] == {"width": 21, "length": 21, "height": 11, "alcove": 0}
    assert rec["plug_depth"] == 8
    assert rec["gate"]["flags"] == ["gym8_cleared"]
    assert rec["cache"]["reward"] == "groudon_red_orb" and rec["cache"]["container"] == "pedestal"
    assert [s["id"] for s in rec["retired_sites"]] == ["quake_cavern_v1"], "sealed_chamber_v1 is the live chamber again"


def test_rayquaza_still_reads_groudon_met(doc, ground, tmp_path):
    # data/rayquaza_sky.json requires_met reads cobblers:legendary/groudon/met: the advancement id must not change
    sky = json.loads((ROOT / "data" / "rayquaza_sky.json").read_text(encoding="utf-8"))
    assert "groudon" in json.dumps(sky["gate"]["requires_met"])
    assert "data/cobblers/advancement/legendary/groudon/met.json" in L.files(doc, ground)


def test_the_held_tag_is_the_retired_sites_own():
    assert GC.RETIRE_HELD == L.RETIRE_HELD == RA.HELD


def test_the_cavern_packs_are_withdrawn_and_installed_nowhere():
    import reapply as R
    for name in ("cobblers_groudon_cavern", "cobblers_groudon_cavern_build"):
        assert name in R.WITHDRAWN and R.WITHDRAWN[name]
        assert name not in R.SERVER_PACKS and name not in R.WORLD_LOCAL


# ----------------------------------------------------------------------------------------------------------- the audit


@pytest.mark.slow
def test_the_committed_cleanup_passes_its_audit(doc, ground, tmp_path):
    rep = run_audit(doc, ground, tmp_path)
    assert not rep.errors, rep.errors[:5]
    assert rep.checks >= 70, "the audit ran %d checks: it stopped early" % rep.checks


def _mutated_audit(doc, ground, tmp_path, monkeypatch, name, fn):
    monkeypatch.setattr(GC, name, fn)
    GC._PLANS.clear()
    try:
        return run_audit(doc, ground, tmp_path)
    finally:
        GC._PLANS.clear()


@pytest.mark.slow
def test_generator_mutation_lava_left_in_the_lake_is_caught(doc, ground, tmp_path, monkeypatch):
    orig = GC.touched_masks

    def no_lava(d, M, B):
        carve, cut, walls = orig(d, M, B)
        return carve & ~M.lava, cut, walls

    rep = _mutated_audit(doc, ground, tmp_path, monkeypatch, "touched_masks", no_lava)
    assert failing(rep, "lava:"), rep.errors[:5]


@pytest.mark.slow
def test_generator_mutation_a_surface_one_block_low_is_caught(doc, ground, tmp_path, monkeypatch):
    import numpy as np

    def low(rel):
        rel = np.asarray(rel)
        return np.where(rel == 0, 0, np.where(rel == -1, 3, np.where(rel >= -2, 2, 1)))

    rep = _mutated_audit(doc, ground, tmp_path, monkeypatch, "terrain_band", low)
    assert failing(rep, "surface:") and failing(rep, "void:"), rep.errors[:5]


@pytest.mark.slow
def test_generator_mutation_the_rim_walls_left_standing_is_caught(doc, ground, tmp_path, monkeypatch):
    orig = GC.restore_commands

    def keep_walls(d, M, B, terrain, masks=None):
        return [c for c in orig(d, M, B, terrain, masks) if " replace " not in c]

    rep = _mutated_audit(doc, ground, tmp_path, monkeypatch, "restore_commands", keep_walls)
    assert failing(rep, "wall:"), rep.errors[:5]


@pytest.mark.slow
def test_generator_mutation_the_restore_writing_air_over_the_ground_is_caught(doc, ground, tmp_path, monkeypatch):
    # a restore that also cleared the cut's air over the ground would take the owner's hand-placed stones out
    orig = GC.restore_commands

    def unfiltered(d, M, B, terrain, masks=None):
        return [c.split(" replace ")[0] for c in orig(d, M, B, terrain, masks)]

    rep = _mutated_audit(doc, ground, tmp_path, monkeypatch, "restore_commands", unfiltered)
    assert failing(rep, "reach:"), rep.errors[:5]


@pytest.mark.slow
def test_generator_mutation_no_held_box_over_the_hall_is_caught(doc, ground, tmp_path, monkeypatch):
    orig = GC.held_boxes

    def no_hall(d, M):
        return [(w, b) for w, b in orig(d, M) if w != "the hall"]

    rep = _mutated_audit(doc, ground, tmp_path, monkeypatch, "held_boxes", no_hall)
    assert failing(rep, "held:"), rep.errors[:5]


@pytest.mark.slow
def test_generator_mutation_an_unguarded_restore_is_caught(doc, ground, tmp_path, monkeypatch):
    orig = GC.retire_functions

    def unguarded(rec, site, leg_doc, gr, p=None):
        fns = orig(rec, site, leg_doc, gr, p)
        fns[BASE + "_act"] = [l.replace("execute unless entity @a[tag=%s] " % GC.RETIRE_HELD, "execute ")
                              for l in fns[BASE + "_act"]]
        return fns

    rep = _mutated_audit(doc, ground, tmp_path, monkeypatch, "retire_functions", unguarded)
    assert failing(rep, "act:"), rep.errors[:5]


@pytest.mark.slow
def test_generator_mutation_parts_that_hold_their_own_chunks_is_caught(doc, ground, tmp_path, monkeypatch):
    # a part's own forceload remove would release the chain's hold half way (a forceload is per chunk, not counted)
    import function_limits as FL
    orig = GC.retire_functions

    def own_forceload(rec, site, leg_doc, gr, p=None):
        fns = orig(rec, site, leg_doc, gr, p)
        for k in list(fns):
            if "_restore_p_" in k:
                fns[k] = FL.ensure_loaded([l for l in fns[k] if "chunks-loaded-by" not in l])
        return fns

    rep = _mutated_audit(doc, ground, tmp_path, monkeypatch, "retire_functions", own_forceload)
    assert failing(rep, "chunks:"), rep.errors[:5]


@pytest.mark.slow
def test_generator_mutation_a_changed_cavern_model_is_caught_by_the_frozen_record(doc, ground, tmp_path, monkeypatch):
    # the cleanup and the record of what was applied come from one model: widen the hall and both move together, so only
    # the frozen sha256 can say the cavern being undone is no longer the one that was built
    import numpy as np
    orig = GC.build_model

    def wider(d, gr):
        M = orig(d, gr)
        grow = np.zeros_like(M.ia)
        grow[1:, :, :] |= M.ia[:-1, :, :]
        M.ia = M.ia | (grow & (M.feat == 0))
        return M

    monkeypatch.setattr(GC, "build_model", wider)
    GC._PLANS.clear()
    pack = tmp_path / "datapacks" / "cobblers_legendaries"
    for rel, text in L.files(doc, ground).items():
        f = pack / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    gdoc = GC.load()
    GC.write_applied(gdoc, GC.plan(gdoc, ground), ground, tmp_path / "applied")
    GC._PLANS.clear()
    rep = RA.audit(pack, tmp_path / "applied", ground, leg=doc)
    assert failing(rep, "sha256"), rep.errors[:5]


@pytest.mark.slow
def test_generator_mutation_the_pedestal_not_last_is_caught(doc, ground, tmp_path, monkeypatch):
    orig = GC.retire_functions

    def early(rec, site, leg_doc, gr, p=None):
        fns = orig(rec, site, leg_doc, gr, p)
        body = fns[BASE + "_restore"]
        ped = next(l for l in body if l.startswith("setblock "))
        body.remove(ped)
        body.insert(next(i for i, l in enumerate(body) if l.startswith("function ")), ped)
        return fns

    rep = _mutated_audit(doc, ground, tmp_path, monkeypatch, "retire_functions", early)
    assert failing(rep, "last write"), rep.errors[:5]


# ------------------------------------------------------------------------------------------- the chain, as R14L runs it


def cleanup_steps(doc, ground):
    steps = L.placement_steps(doc, ground)
    i = steps.index(("fn", BASE))
    assert steps[i + 1][0] == "wait" and steps[i + 2][0] == "check" and steps[i + 2][1][2] == 0
    return steps[i:i + 3]


def cavern_world(doc, ground, built=True):
    """The live world as relayed on 2026-10-21: cavern built and open, the chamber's score 1, Groudon on the lava."""
    fns = functions(doc, ground)
    # the chambers' proximity tick (`near`, whose gate selectors the simulator does not model) is not under test here:
    # R14L's steps are, and they never call it
    fns["cobblers:legendary/tick"] = []
    w = world(fns, delay=20)
    obj = doc["objective"]
    w.set_score("#groudon", obj, 1, w.server())
    if built:
        w.command("scoreboard objectives add cobblers.gq dummy", w.server())
        w.set_score("#built", "cobblers.gq", 1, w.server())
        w.set_score("#quake", "cobblers.gq", 5, w.server())
        px, py, pz = GC.pedestal(GC.load())
        w.terrain = lambda x, y, z: "minecraft:smooth_basalt" if (x, y, z) == (px, py, pz) else "minecraft:stone"
    tag = doc["tag_prefix"] + "groudon"
    g = S.Entity("cobblemon:pokemon", RA.OWNER_GROUDON, nbt={"Pokemon": {"Species": "groudon"}},
                 tags=(tag, tag + ".awake"))
    w.save(g)
    return w, g


def restore_writes(w):
    return [d for _t, d in w.logged("fill", BASE + "_restore")] + [d for _t, d in w.logged("setblock", BASE + "_restore")]


@pytest.mark.slow
@pytest.mark.parametrize("where", [(6706.5, 105.0, 5520.5), (6706.5, 86.0, 5560.5), (6720.5, 75.0, 5590.5),
                                   (6764.5, 65.0, 5624.5)], ids=["ravine", "plug", "tunnel", "hall"])
def test_a_player_inside_holds_the_cleanup_and_the_step_reads_it(doc, ground, where):
    # Without the guard the fills bury the player; without the count the refusal would read as done and R14L go on.
    w, g = cavern_world(doc, ground)
    w.add_player(where)
    run_steps(w, cleanup_steps(doc, ground))
    assert not restore_writes(w), "the cleanup wrote blocks with a player at %s" % (where,)
    assert g.alive, "the cavern's Groudon was killed while the cleanup was refused"
    assert w.get_score("#groudon", doc["objective"], w.server()) == 1
    assert w.get_score(HOLDER, CL.OBJ, w.server()) == 1, "the step would read 0 held and call a refusal done"


@pytest.mark.slow
def test_a_player_on_the_bowl_floor_away_from_the_cut_does_not_hold_it(doc, ground):
    w, g = cavern_world(doc, ground)
    w.add_player((6640.5, 109.0, 5505.5))
    run_steps(w, cleanup_steps(doc, ground))
    assert w.get_score(HOLDER, CL.OBJ, w.server()) == 0 and restore_writes(w)


@pytest.mark.slow
def test_the_cleanup_restores_kills_clears_and_releases_every_chunk(doc, ground):
    w, g = cavern_world(doc, ground)
    run_steps(w, cleanup_steps(doc, ground))
    assert len(restore_writes(w)) > 1000
    assert not [e for e in w.errors if "unloaded" in e], "a write into an unloaded chunk: %s" % w.errors[:2]
    assert not w.errors, w.errors[:3]
    assert not g.alive, "the cavern's Groudon survived"
    obj = doc["objective"]
    assert w.get_score("#groudon", obj, w.server()) == 0, "the chamber's open score is still 1: carve_once would skip"
    assert w.get_score("#built", "cobblers.gq", w.server()) == 0 and w.get_score("#quake", "cobblers.gq", w.server()) == 0
    assert w.get_score(HOLDER, CL.OBJ, w.server()) == 0
    assert not w.forced, "the cleanup left chunks force-loaded"


@pytest.mark.slow
def test_a_second_run_writes_nothing_and_keeps_a_chamber_opened_since(doc, ground):
    w, g = cavern_world(doc, ground)
    run_steps(w, cleanup_steps(doc, ground))
    obj = doc["objective"]
    w.set_score("#groudon", obj, 1, w.server())       # the owner opens the rebuilt chamber's plug
    n = len(w.log)
    run_steps(w, cleanup_steps(doc, ground))
    again = [d for t, k, d in w.log[n:] if k in ("fill", "setblock")]
    assert not again, "a second run wrote: %s" % again[:2]
    assert w.get_score("#groudon", obj, w.server()) == 1, "a second run cleared the reopened chamber's score"


@pytest.mark.slow
def test_a_world_that_never_had_the_cavern_is_left_alone(doc, ground):
    w, g = cavern_world(doc, ground, built=False)
    run_steps(w, cleanup_steps(doc, ground))
    assert not restore_writes(w), "blocks written into a world with no cavern"
    assert w.get_score("#groudon", doc["objective"], w.server()) == 1, "the score of a world without the cavern was cleared"


@pytest.mark.slow
def test_after_the_cleanup_r14l_carves_the_chamber_and_summons_groudon_there(doc, ground):
    w, g = cavern_world(doc, ground)
    steps = L.placement_steps(doc, ground)
    i = steps.index(("fn", "cobblers:legendary/groudon/carve_once"))
    j = steps.index(("fn", "cobblers:legendary/groudon/place"))
    run_steps(w, cleanup_steps(doc, ground))
    run_steps(w, [steps[i - 2], steps[i - 1]] + steps[i:j + 3])
    assert w.logged("fill", "cobblers:legendary/groudon/carve"), "carve_once did not carve the chamber"
    rec = next(r for r in doc["encounters"] if r["id"] == "groudon")
    lx, ly, lz = L.geometry(rec, doc, ground)["legendary"]
    tag = doc["tag_prefix"] + "groudon"
    here = [e for e in w.living("cobblemon:pokemon", tag) if abs(e.pos[0] - (lx + 0.5)) < 1 and abs(e.pos[2] - (lz + 0.5)) < 1]
    assert len(here) == 1, "Groudon is not in the rebuilt chamber"
    assert not g.alive
    assert not [e for e in w.errors if "unloaded" in e], w.errors[:2]
