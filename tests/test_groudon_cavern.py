"""Groudon's quake cavern: tools/groudon_cavern.py (the generator) and tools/groudon_cavern_audit.py (its independent audit).

WHO WROTE THIS. The same session wrote the generator, the audit and this file (the owner's brief asked for all three in one
unit), so the usual separation of implementer and test author does NOT hold here: an independent reviewer should read the
mutation table below before trusting it. What stands in for that separation is the shape of the audit: it imports nothing from
the generator, replays the EMITTED commands onto a voxel grid of the heightmap's terrain, and measures the replayed world.

THE STANDARD (CLAUDE.md "How to prove an audit is independent"). Every mutation below changes the GENERATOR's code
(tools/groudon_cavern.py or tools/legendaries.py, by monkeypatch) and leaves data/ alone, and asserts the audit names the fault.
A mutation the builder's own fail-closed guards refuse is not a test of the audit: the helper fails it ("the builder refused
first"), so each mutation here is one the builder lets through.

NOT COVERED, and it needs a running server: that the quake, the rumble and the keeper behave as the text says in a game, that
`forceload add` loads a chunk in the same tick, that the lava stays where the model puts it, the natural terrain's blocks
(the heightmap has heights only), and everything a player sees. Validity is not behaviour (.claude/rules/testing.md).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import groudon_cavern as GC  # noqa: E402
import groudon_cavern_audit as A  # noqa: E402
import legendaries as L  # noqa: E402


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def build_and_audit(tmp_path, ground):
    """Build both packs from the generator AS IT STANDS (patched or not) into tmp_path and audit them."""
    doc = GC.load()
    try:
        p = GC.plan(doc, ground)
    except SystemExit as e:
        pytest.fail("the builder refused first (%s): a mutation of the audit's test must be one the builder lets through" % e)
    GC.write_pack(doc, p, ground, tmp_path / "rt")
    return A.audit(tmp_path / "rt", tmp_path / "rt_build", ground)


def failing(rep, needle):
    return [e for e in rep.errors if needle in e]


# ----------------------------------------------------------------------------------------------------------- positive


@pytest.mark.slow
def test_the_committed_cavern_passes_its_own_independent_audit(tmp_path, ground):
    # If removed: a cavern whose seal, walk, lava, keeper, stages or cleanup drifts ships with nobody noticing.
    rep = build_and_audit(tmp_path, ground)
    assert rep.errors == [], "\n".join(rep.errors)
    assert rep.checks > 300, "only %d checks: the audit has stopped looking at most of it" % rep.checks
    assert any(n.startswith("walk:") for n in rep.notes), "the audit measured no walk"


def test_the_audit_fails_closed_on_an_empty_pack(tmp_path, ground):
    # If removed: an audit of nothing could pass (the fail-open shape four earlier audits had, docs/STATE.md).
    rep = A.audit(tmp_path / "none", tmp_path / "none_build", ground)
    assert rep.errors and failing(rep, "NOTHING TO CHECK"), rep.errors


def test_the_audit_does_not_import_the_builder():
    # If removed: the audit could share the builder's derivation and agree with it about a wrong cavern.
    text = (ROOT / "tools" / "groudon_cavern_audit.py").read_text(encoding="utf-8")
    code = [ln for ln in text.splitlines() if ln.strip().startswith(("import ", "from "))]
    assert not any("groudon_cavern " in ln or ln.strip().endswith("groudon_cavern") or "groudon_cavern import" in ln
                   for ln in code), code


def test_the_pack_split_keeps_the_carve_out_of_the_runtime_pack(tmp_path, ground):
    # If removed: the carve's ~8,000 lines would stay parsed in the heap for good (docs/research/notes/function-heap.md).
    doc = GC.load()
    GC.write_pack(doc, GC.plan(doc, ground), ground, tmp_path / "rt")
    rt = A.Pack(tmp_path / "rt")
    bd = A.Pack(tmp_path / "rt_build")
    assert sum(len(rt.body(f)) for f in rt.fns) < 400, "the runtime pack is not small"
    assert all(f.startswith(GC.BUILD_PREFIX) or f == GC.CARVE_ONCE for f in bd.fns), sorted(bd.fns)
    assert not [f for f in rt.fns if f.startswith(GC.BUILD_PREFIX)]
    assert GC.CARVE_ONCE in bd.fns and sum(len(bd.body(f)) for f in bd.fns) > 4000


def test_the_record_geometry_agrees_with_the_reward_cache(ground):
    # If removed: the Red Orb could stay in the old chamber's rock (data/rewards.json groudon_red_orb) after the move.
    doc = L.load()
    assert L.cache_problems(doc, ground) == []
    rec = next(r for r in doc["encounters"] if r["id"] == "groudon")
    g = L.geometry(rec, doc, ground)
    rewards = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
    orb = next(r for r in rewards["rewards"] if r["id"] == "groudon_red_orb")
    assert list(g["pedestal"]) == orb["container"]["at"]
    assert g["legendary"][1] == g["pedestal"][1] + 1


def test_groudons_met_advancement_and_caught_record_are_unchanged():
    # If removed: Rayquaza's gate (data/rayquaza_sky.json gate.requires_met) would read an advancement that moved or went.
    import ground as G
    pack = L.files(L.load(), G.Ground())
    assert "data/cobblers/advancement/legendary/groudon/met.json" in pack
    assert any("advancement grant @s only cobblers:legendary/groudon/met" in t for k, t in pack.items()
               if k.endswith("/groudon/met.mcfunction"))
    rq = json.loads((ROOT / "data" / "rayquaza_sky.json").read_text(encoding="utf-8"))
    assert "groudon" in rq["gate"]["requires_met"]


def test_merge_boxes_rebuilds_exactly_the_cells_it_was_given():
    # If removed: the carve could silently drop or add a block while every later check read the same wrong boxes.
    rng = np.random.default_rng(7)
    ids = (rng.random((9, 7, 11)) < 0.55).astype(np.int16) * rng.integers(1, 4, (9, 7, 11)).astype(np.int16)
    back = np.zeros_like(ids)
    for x0, y0, z0, x1, y1, z1, b in GC.merge_boxes(ids, (100, 50, 200)):
        assert not back[x0 - 100:x1 - 99, y0 - 50:y1 - 49, z0 - 200:z1 - 199].any(), "two boxes overlap"
        back[x0 - 100:x1 - 99, y0 - 50:y1 - 49, z0 - 200:z1 - 199] = b
    assert (back == ids).all()


def test_the_chunk_distance_rule_counts_the_stage_s_own_extent():
    # If removed: a pad measured from the near edge only (the first draft) lets a long stage write 6 chunks from the player.
    assert GC.chunk_gap((6698, 86, 5534, 6715, 140, 5556), 64) == 6
    assert GC.chunk_gap((6698, 86, 5534, 6715, 140, 5556), 48) == 5


def test_static_problems_refuse_a_guard_that_misses_the_hall():
    # If removed: a keeper box smaller than the hall passes the data check and turns away nobody in the far half.
    doc = GC.load()
    doc["guard"]["box"][3] = doc["guard"]["box"][3] - 20
    assert any("guard box" in p for p in GC.static_problems(doc))


# ----------------------------------------------------------------------------------------------- the mutations

MUTATIONS = {}


def mutation(fn):
    MUTATIONS[fn.__name__] = fn
    return fn


@mutation
def steps_of_two_blocks(mp, ground):
    # the tunnel's floor falls two blocks at a time: down is a drop, but there is no way back up
    orig = GC.floor_profile

    def mut(S, sp, ravine_len):
        return orig(S, sp, ravine_len) - np.where(S > ravine_len, np.floor((S - ravine_len) / sp["tunnel_run"]), 0).astype(np.int32)
    mp.setattr(GC, "floor_profile", mut)
    return "NO WAY BACK"


@mutation
def tunnel_one_block_high(mp, ground):
    mp.setattr(GC, "tunnel_height", lambda doc, D, w: np.ones(np.shape(D), dtype=np.int32))
    return "NO WALK"


@mutation
def lake_without_its_wall(mp, ground):
    mp.setattr(GC, "parapet_columns", lambda lake_c, sel_h: np.zeros_like(lake_c))
    return "within one block of lava"


@mutation
def lava_raised_above_the_floor_and_unwalled(mp, ground):
    mp.setattr(GC, "parapet_columns", lambda lake_c, sel_h: np.zeros_like(lake_c))
    mp.setattr(GC, "lava_top", lambda doc: int(doc["hall"]["floor_y"]) + 1)
    return "it would flow"


@mutation
def hall_wider_than_the_keeper(mp, ground):
    orig = GC.hall_radius
    mp.setattr(GC, "hall_radius", lambda doc, PX, PZ: orig(doc, PX, PZ) + 5.0)
    return "stand outside the keeper's box"


@mutation
def thin_envelope(mp, ground):
    mp.setattr(GC, "envelope_margin", lambda doc: 1)
    return "were not written solid by the carve"


@mutation
def magma_in_the_floor(mp, ground):
    mp.setattr(GC, "accent_allowed", lambda is_floor: True)
    return "stand on a hurting block"


@mutation
def trigger_wider_than_the_simulation(mp, ground):
    orig = GC.trigger_box
    mp.setattr(GC, "trigger_box", lambda box, pad: orig(box, 200))
    return "chunks from a chunk it writes"


@mutation
def a_probe_that_was_already_air(mp, ground):
    def mut(M, mask, lip_x):
        x, z = lip_x, 5530
        return (x, int(M.G[x - M.o[0], z - M.o[2]]) + 5, z)
    mp.setattr(GC, "probe_cell", mut)
    return "is not rock before and air after"


@mutation
def a_cleanup_that_writes_no_blocks(mp, ground):
    orig = L.retire_restore_lines
    mp.setattr(L, "retire_restore_lines",
               lambda rec, site, doc, ground_: [ln for ln in orig(rec, site, doc, ground_) if not ln.startswith("fill")])
    return "cleanup:"


@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_a_mutated_generator_is_caught_by_the_audit(name, tmp_path, ground, monkeypatch):
    # If removed (or if any one of these passes): the audit has gone fail-open for that fault. Each changes generator CODE and
    # no data; the audit replays what the mutated generator EMITTED and must name the fault.
    want = MUTATIONS[name](monkeypatch, ground)
    rep = build_and_audit(tmp_path, ground)
    assert rep.errors, "%s: the audit passed a mutated generator" % name
    assert failing(rep, want), "%s: the audit failed but not for the fault (wanted %r); got %s" % (name, want, rep.errors[:4])
