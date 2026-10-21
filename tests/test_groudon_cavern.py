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


@mutation
def the_rim_left_unguarded(mp, ground):
    # review 2026-10-21 finding 1: the ravine's vertical walls make cliffs of up to 50 on the plateau
    mp.setattr(GC, "rim_guard_columns", lambda doc, M, cut: {})
    return "are not guarded"


@mutation
def a_rim_guard_one_block_high_beside_higher_ground(mp, ground):
    # a wall one block over its own ground is jumped onto from a neighbour standing higher, and walked off into the ravine
    orig = GC.rim_guard_columns
    mp.setattr(GC, "rim_guard_columns", lambda doc, M, cut: {c: (lo, lo) for c, (lo, _hi) in orig(doc, M, cut).items()})
    return "is under the feet"


@mutation
def the_cut_gives_no_slow_falling(mp, ground):
    # review finding 3: the stage's own slow falling line, deleted from the generator
    mp.setattr(GC, "cut_falling_lines", lambda box, seconds: [])
    return "gives no slow falling over its own cut"


@mutation
def tick_tests_the_states_in_ascending_order(mp, ground):
    # review finding 2: the first draft's order, under which the tremor and all three cuts fell in one tick
    mp.setattr(GC, "tick_order", lambda: (0, 1, 2, 3, 4))
    return "one pass of tick can move #quake"


@mutation
def the_summon_not_held_to_built(mp, ground):
    # review finding 4: a skipped carve must never put Groudon into rock
    mp.setattr(GC, "built_condition", lambda doc=None: "")
    return "the summon is not held to #built"


@mutation
def a_read_back_that_copies_nothing(mp, ground):
    # review finding 4: R14L reads #built back; a read-back function that never copies it is no read-back
    orig = GC.built_read_lines
    mp.setattr(GC, "built_read_lines", lambda doc: [l for l in orig(doc) if not l.startswith("execute store")])
    return "copies #built to a score R14L reads"


@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_a_mutated_generator_is_caught_by_the_audit(name, tmp_path, ground, monkeypatch):
    # If removed (or if any one of these passes): the audit has gone fail-open for that fault. Each changes generator CODE and
    # no data; the audit replays what the mutated generator EMITTED and must name the fault.
    want = MUTATIONS[name](monkeypatch, ground)
    rep = build_and_audit(tmp_path, ground)
    assert rep.errors, "%s: the audit passed a mutated generator" % name
    assert failing(rep, want), "%s: the audit failed but not for the fault (wanted %r); got %s" % (name, want, rep.errors[:4])


# ------------------------------------------------------------------------------------------- the review's findings


def tick_lines(ground):
    doc = GC.load()
    p = GC.plan(doc, ground)
    rfns, _info = GC.runtime_files(doc, p["M"], L.load()["objective"], 100)
    return doc, rfns


def test_no_pass_of_tick_moves_the_quake_more_than_one_state(ground):
    # Review 2026-10-21 finding 2. If removed: the stage lines can go back to ascending order, and one pass of tick (every
    # line run in order, each probe reading air) plays the tremor and cuts all three stages in the same tick.
    import re
    doc, rfns = tick_lines(ground)
    O = re.escape(doc["quake"]["objective"])
    drives = []
    for ln in rfns["tick"]:
        m = re.search(r"if score #quake %s matches (\d+) .*run function cobblers:groudon_cavern/(\S+)$" % O, ln)
        if m:
            to = [int(v) for b in rfns[m.group(2)] for v in re.findall(r"scoreboard players set #quake %s (\d+)" % O, b)]
            drives.append((int(m.group(1)), max(to)))
    assert sorted(s for s, _t in drives) == [0, 1, 2, 3, 4], drives
    for start in range(0, 5):
        s, moved = start, 0
        for when, to in drives:
            if s == when:
                s, moved = to, moved + 1
        assert moved == 1, "from #quake %d one pass moves it %d states (order %s)" % (start, moved, [d[0] for d in drives])


def test_a_rejoin_over_the_cut_is_seen_on_the_first_tick(ground):
    # Review finding 5. If removed: the rejoin's slow falling could go back to the 20-tick keeper and land up to a second late.
    doc, rfns = tick_lines(ground)
    left = doc["quake"]["left_objective"]
    loop = "schedule function %s/rejoin 1t replace" % GC.F
    assert loop in rfns["load"] and rfns["rejoin"].count(loop) == 1
    assert any("scores={%s=1..}" % left in l and "slow_falling" in l for l in rfns["rejoin"])
    assert not any("slow_falling" in l for l in rfns["tick"]), "the rejoin is still (also) on the 20-tick pass"


def test_the_rim_guard_stands_wherever_the_cut_drops_more_than_three(ground):
    # Review finding 1, on the generator's own model (the audit measures the replayed world instead): the rim is walled from
    # one over its ground, and the lip, where the mouth's walk-in entrance is, is left open.
    doc = GC.load()
    M = GC.plan(doc, ground)["M"]
    cols = GC.rim_guard_columns(doc, M, M.qa_r | M.qa_p)
    assert len(cols) > 50
    lx, lz = doc["spine"]["lip"]
    i, k = lx - M.o[0], lz - M.o[2]
    assert (i, k) not in cols and (i, k - 1) not in cols, "the mouth's walk-in entrance is walled"
    assert all(hi >= lo == int(M.G[c]) + 1 for c, (lo, hi) in cols.items())


def r14l_world(ground, carve_sets_built):
    import test_legendaries_rerun as R
    doc = L.load()
    one = dict(doc, encounters=[r for r in doc["encounters"] if r["id"] == "groudon"])
    fns = R.functions(one, ground)
    if not carve_sets_built:
        fns[GC.CARVE_ONCE] = []          # the carve skipped (a stale open score, a missing pack, a carve cut short)
    w = R.world(fns, delay=0)
    steps = [s for s in L.placement_steps(one, ground) if "retire_" not in str(s[1])]
    R.run_steps(w, steps)
    return w, one, steps, R


@pytest.mark.parametrize("built", [True, False])
def test_r14l_reads_built_back_and_never_summons_into_an_unbuilt_cavern(ground, built):
    # Review finding 4. If removed: carve_once can skip, R14L reports success, and Groudon is summoned into rock.
    import chunk_look as CL
    assert GC.CL_OBJ == CL.OBJ
    w, one, steps, R = r14l_world(ground, built)
    rec = one["encounters"][0]
    checks = [s[1] for s in steps if s[0] == "check" and s[1][1] == GC.BUILT_HOLDER]
    assert checks and checks[0][2] == 1, "R14L does not read #built back as 1"
    assert steps.index(("fn", GC.BUILT_READ)) > steps.index(("fn", GC.CARVE_ONCE))
    got = w.get_score("#" + GC.BUILT_HOLDER, CL.OBJ, w.server())
    assert got == (1 if built else 0), "the read-back holds %s" % got
    assert len(R.standing(w, rec, one)) == (1 if built else 0), "built=%s: wrong number of Groudon standing" % built


@pytest.mark.slow
def test_a_retired_chamber_whose_pedestal_a_player_took_is_still_restored(ground):
    # Review finding 4, the cleanup half. The live world's old Groudon chamber was opened (its score 1, its plug air, the
    # owner stood inside). Had the pedestal gone too, the restore (gated on it) never ran, the score stayed 1 and the
    # cavern's carve_once skipped. The second gate reads three cells of the old voids. Run on the cleanup tests' fixture.
    import copy as _copy
    import test_legendaries_retire as T
    doc = _copy.deepcopy(L.load())
    w, o, natural, live, old = T.set_up(doc, ground)
    carved = w.terrain
    ped = tuple(o["pedestal"])
    w.terrain = lambda x, y, z: "minecraft:air" if (x, y, z) == ped else carved(x, y, z)
    w.set_score("#regigigas", doc["objective"], 1, w.server())
    T.run_steps(w, T.retire_steps(doc, ground))
    bad = T.mismatches(w, o, natural, doc, ground)
    assert not bad, "%d cell(s) not terrain after the cleanup, e.g. %s" % (len(bad), bad[:3])
    assert w.get_score("#regigigas", doc["objective"], w.server()) == 0, "the old open score was not cleared"
    n = len(w.log)
    T.run_steps(w, T.retire_steps(doc, ground))
    assert not [1 for _t, k, _d in w.log[n:] if k in ("fill", "setblock")], "a second run wrote again"
