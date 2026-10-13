"""A legendary's chamber that MOVES leaves nothing behind (2026-10-12, Regigigas to the North Pine Isle).

Regigigas's first chamber was built in staging and its legendary summoned. Re-siting the record alone would have left a
carved chamber, a shaft under a stone plug and a second Regigigas. tools/legendaries.py now emits, per `retired_sites`
entry, a look-then-act cleanup that R14L runs first; tools/legendaries_audit.py judges it. This file proves both.

Two halves, kept apart on purpose.

  AUDIT (text and arithmetic): the committed data passes; broken packs fail with a named reason. The expectation is
  tools/legendaries_audit.py own_old_site(), which derives the old chamber from the record's numbers and the heightmap
  WITHOUT calling the generator's geometry(). The mutations change the GENERATOR (tools/legendaries.geometry), never
  the data: a record-side edit would move the expectation and the output together and prove nothing.

  RUNTIME SHAPE (tests/mcfunction_sim.py): the generated functions are run by the simulator over a world whose old
  chamber is set up from the audit's independent derivation, never from the generator. It shows the cleanup restores
  every cell, kills the record's own old legendary and not the live one, refuses while a player stands in a void, writes
  nothing on a second run, and clears the open score exactly once.

NOT COVERED, and it needs the running server: that `fill` over a force-loaded old hull lands, that the real chunk's
saved entities arrive within the chain's 300 ticks, that the snow_block surface looks right (terrain.surface_verified
is false in the data), that the real selector's hitbox rules match the simulator's, and that R14L reads 0 held back.
The simulator models blocks only as plain fill/setblock writes over a terrain function.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import chunk_look as CL  # noqa: E402
import legendaries as L  # noqa: E402
import legendaries_audit as A  # noqa: E402
import mcfunction_sim as S  # noqa: E402
from test_legendaries_rerun import functions, run_steps, save_legendary, world  # noqa: E402

DATA = ROOT / "data"
WORLD = json.loads((DATA / "world.json").read_text(encoding="utf-8"))
LANDMARKS = json.loads((DATA / "landmarks.json").read_text(encoding="utf-8"))
WATER = json.loads((DATA / "water_shape.json").read_text(encoding="utf-8"))
PROGRESSION = json.loads((DATA / "progression.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture
def doc():
    return copy.deepcopy(L.load())


def rec_of(doc, rid="regigigas"):
    return next(r for r in doc["encounters"] if r["id"] == rid)


def site_of(doc):
    return rec_of(doc)["retired_sites"][0]


def emit(doc, ground, out: Path) -> Path:
    for rel, text in L.files(doc, ground).items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return out


def audit(doc, ground, out):
    return A.audit(doc, ground, emit(doc, ground, out), WATER, PROGRESSION, LANDMARKS, WORLD)


def retired_errors(rep):
    return [e for e in rep.errors if "retired site" in e or "retire functions" in e]


def fn_path(pack, doc, name):
    return pack / "data" / doc["namespace"] / "function" / "legendary" / "regigigas" / name


# ------------------------------------------------------------------------------------------------ the data


def test_the_committed_record_moved_and_keeps_its_old_site_frozen(doc):
    # Without it the cleanup could be deleted from the data and every test below would have nothing to look at.
    rec = rec_of(doc)
    site = site_of(doc)
    assert rec["portal"] == [7720, 552] and rec["site"] == "north_pine_isle"
    assert site["portal"] == [3560, 1760] and site["id"] == "first_chamber"
    assert rec["gate"]["flags"] == ["gym8_cleared"] and rec["gate"]["requires_met"] == ["regirock", "regice", "registeel"]
    assert rec["level"] == 60 and rec["cap_at_gate"] == 60 and rec["kind"] == "sealed_chamber"
    for k in ("bore", "shell_margin", "pedestal_block", "plug_depth", "approach", "chamber", "terrain"):
        assert k in site, "the retired site does not freeze %s" % k


@pytest.mark.parametrize("drop", ["bore", "pedestal_block", "terrain", "portal"])
def test_a_retired_site_that_leaves_a_number_to_be_guessed_is_refused(doc, tmp_path, drop):
    # The cleanup must never guess what it is undoing. Without the key check a later edit could delete a frozen
    # number and the cleanup would fall back to a default that has since changed.
    del site_of(doc)[drop]
    p = tmp_path / "l.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(L.LegendaryError, match=drop):
        L.load(p)


def test_a_retired_portal_equal_to_the_live_portal_is_refused(doc, tmp_path):
    # "Retired" means the record moved. A site that is also the live one would have the cleanup undo the chamber it
    # is about to build.
    site_of(doc)["portal"] = list(rec_of(doc)["portal"])
    p = tmp_path / "l.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(L.LegendaryError, match="nothing moved"):
        L.load(p)


# ------------------------------------------------------------------------------------------------ the audit


@pytest.mark.slow
def test_the_committed_cleanup_passes_its_audit_and_was_actually_looked_at(doc, ground, tmp_path):
    # Non-vacuous: the audit must have counted checks for the retired site, not passed over it.
    rep = audit(doc, ground, tmp_path / "pack")
    assert rep.errors == [], "\n".join(rep.errors)
    solo = copy.deepcopy(doc)
    rec_of(solo)["retired_sites"] = []
    base = A.audit(solo, ground, emit(solo, ground, tmp_path / "solo"), WATER, PROGRESSION, LANDMARKS, WORLD)
    assert rep.checks - base.checks >= 20, "the retired site added only %d checks" % (rep.checks - base.checks)


@pytest.mark.slow
def test_an_empty_restore_fails(doc, ground, tmp_path):
    # Partial output must not pass: a restore function stripped of its writes.
    pack = emit(doc, ground, tmp_path / "pack")
    fn_path(pack, doc, "retire_first_chamber_restore.mcfunction").write_text("# nothing\n", encoding="utf-8")
    rep = A.audit(doc, ground, pack, WATER, PROGRESSION, LANDMARKS, WORLD)
    assert retired_errors(rep), "an empty restore passed"
    assert any("not put back" in e or "only 0 writes" in e or "NOTHING TO CHECK" in e for e in rep.errors), rep.errors


@pytest.mark.slow
def test_a_missing_cleanup_function_fails(doc, ground, tmp_path):
    pack = emit(doc, ground, tmp_path / "pack")
    fn_path(pack, doc, "retire_first_chamber_act.mcfunction").unlink()
    rep = A.audit(doc, ground, pack, WATER, PROGRESSION, LANDMARKS, WORLD)
    assert any("the pack has no" in e for e in rep.errors), rep.errors


@pytest.mark.slow
def test_a_pack_that_still_writes_the_old_hull_elsewhere_fails(doc, ground, tmp_path):
    # "Nothing of the old chamber left in the pack's writes except the restore": the live carve re-pointed at the old
    # portal (a stale copy of the old record's carve) must be named.
    pack = emit(doc, ground, tmp_path / "pack")
    carve = fn_path(pack, doc, "carve.mcfunction")
    carve.write_text(carve.read_text(encoding="utf-8") + "fill 3576 81 1750 3596 91 1770 minecraft:air\n", encoding="utf-8")
    rep = A.audit(doc, ground, pack, WATER, PROGRESSION, LANDMARKS, WORLD)
    assert any("still reaches the old hull" in e and "carve" in e for e in rep.errors), rep.errors


@pytest.mark.slow
def test_a_kill_that_could_reach_the_live_legendary_fails(doc, ground, tmp_path):
    # The live Regigigas carries the same tag. A kill not boxed to the old chamber would take it.
    pack = emit(doc, ground, tmp_path / "pack")
    act = fn_path(pack, doc, "retire_first_chamber_act.mcfunction")
    lines = []
    for line in act.read_text(encoding="utf-8").splitlines():
        if "run kill @e[" in line:
            line = "execute unless entity @a[tag=%s] run kill @e[type=cobblemon:pokemon,tag=cobblers_leg_regigigas]" % A.HELD
        lines.append(line)
    act.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rep = A.audit(doc, ground, pack, WATER, PROGRESSION, LANDMARKS, WORLD)
    assert any("the kill is not held" in e for e in rep.errors), rep.errors


@pytest.mark.slow
def test_a_restore_called_without_the_held_guard_fails(doc, ground, tmp_path):
    # Without the guard the fill buries a player standing in the old chamber.
    pack = emit(doc, ground, tmp_path / "pack")
    act = fn_path(pack, doc, "retire_first_chamber_act.mcfunction")
    text = act.read_text(encoding="utf-8").replace("execute unless entity @a[tag=%s] if block" % A.HELD, "execute if block")
    act.write_text(text, encoding="utf-8")
    rep = A.audit(doc, ground, pack, WATER, PROGRESSION, LANDMARKS, WORLD)
    assert any("not called only while" in e or "does not recognise" in e for e in rep.errors), rep.errors


def _mutate(monkeypatch, change):
    orig = L.geometry

    def mutated(rec, doc_, ground_):
        g = orig(rec, doc_, ground_)
        if g["anchor"] == (3560, 1760):          # only the retired site's chamber; the live ones and the data stay
            g["chamber"] = change(g["chamber"])
        return g

    monkeypatch.setattr(L, "geometry", mutated)


@pytest.mark.slow
def test_generator_mutation_a_chamber_restored_too_small_is_caught(doc, ground, tmp_path, monkeypatch):
    # Mutates tools/legendaries.geometry, leaves data/legendaries.json alone. A shrunk restore leaves air in the
    # old chamber; the audit's own derivation says what was carved and names the cells.
    _mutate(monkeypatch, lambda c: (c[0] + 2, c[1], c[2] + 2, c[3] - 2, c[4], c[5] - 2))
    rep = audit(doc, ground, tmp_path / "pack")
    assert any("not put back" in e for e in retired_errors(rep)), rep.errors


@pytest.mark.slow
def test_generator_mutation_a_restore_that_overreaches_the_hull_is_caught(doc, ground, tmp_path, monkeypatch):
    # width + 12: the restore writes outside the hull the carve could have touched. (Widening by only 2 a side stays
    # inside the 4-block margin and writes stone over stone: harmless, so it is rightly not a failure.)
    _mutate(monkeypatch, lambda c: (c[0] - 6, c[1], c[2] - 6, c[3] + 6, c[4], c[5] + 6))
    rep = audit(doc, ground, tmp_path / "pack")
    assert any("outside the old hull" in e for e in retired_errors(rep)), rep.errors


@pytest.mark.slow
def test_generator_mutation_a_shifted_chamber_is_caught(doc, ground, tmp_path, monkeypatch):
    _mutate(monkeypatch, lambda c: (c[0] + 3, c[1], c[2], c[3] + 3, c[4], c[5]))
    rep = audit(doc, ground, tmp_path / "pack")
    assert any("not put back" in e for e in retired_errors(rep)), rep.errors


def test_terrain_lines_put_air_over_a_plug_column_standing_higher_than_the_ground():
    # The committed old site is flat enough that its plug columns all end at the ground, so the "air above" band is
    # not exercised by it. A column whose ground is lower than the plug's top must get air over the terrain.
    ground = lambda x, z: 100 if x == 0 else 98      # noqa: E731
    t = {"surface": "minecraft:snow_block", "under": "minecraft:stone", "deep": "minecraft:stone"}
    lines = L.terrain_lines({(0, 0): (90, 100), (1, 0): (90, 100)}, ground, t)
    assert "fill 0 100 0 0 100 0 minecraft:snow_block" in lines
    assert "fill 1 98 0 1 98 0 minecraft:snow_block" in lines
    assert "fill 1 99 0 1 100 0 minecraft:air" in lines
    assert not [l for l in lines if l.startswith("fill 0 101")]


# ------------------------------------------------------------------------------------------------ the runtime shape


def cell_blocks(o, ground, doc):
    """The old chamber as the carve left it, from the audit's independent derivation (never L.geometry): a function
    (x, y, z) -> block id, plus the natural terrain function (what the heightmap says should be there)."""
    site = site_of(doc)
    t = site["terrain"]

    def inside(b, x, y, z):
        return b[0] <= x <= b[3] and b[1] <= y <= b[4] and b[2] <= z <= b[5]

    def natural(x, y, z):
        gy = int(ground(x, z))
        if y > gy:
            return "minecraft:air"
        if y == gy:
            return t["surface"]
        return t["under"] if y >= gy - 2 else t["deep"]

    def carved(x, y, z):
        for name in ("chamber", "passage", "shaft"):
            if inside(o[name], x, y, z):
                return "minecraft:ladder" if inside(o["ladder"], x, y, z) else "minecraft:air"
        if inside(o["pedestal"], x, y, z):
            return site["pedestal_block"]
        if inside(o["envelope"], x, y, z) or inside(o["sleeve"], x, y, z) or inside(o["plug"], x, y, z):
            return doc["defaults"]["envelope_block"]
        return natural(x, y, z)

    return carved, natural


def hull_cells(o):
    """Every opened cell, every plug and sleeve cell, and a stride over the envelope: the cells a restore can get wrong."""
    cells = set()
    for name in ("chamber", "passage", "shaft", "ladder", "pedestal", "plug", "sleeve"):
        b = o[name]
        cells |= {(x, y, z) for x in range(b[0], b[3] + 1) for y in range(b[1], b[4] + 1) for z in range(b[2], b[5] + 1)}
    e = o["envelope"]
    cells |= {(x, y, z) for x in range(e[0], e[3] + 1, 3) for y in range(e[1], e[4] + 1, 3) for z in range(e[2], e[5] + 1, 3)}
    return cells


def set_up(doc, ground, delay=0):
    """(world, old-site derivation, natural terrain fn, live legendary entity, old legendary entity), the old chamber
    carved, both legendaries saved in their chunks."""
    rec, site = rec_of(doc), site_of(doc)
    o = A.own_old_site(site, ground)
    carved, natural = cell_blocks(o, ground, doc)
    w = world(functions(doc, ground), delay=delay)
    w.terrain = carved
    live = save_legendary(w, rec, doc, ground)
    tag = doc["tag_prefix"] + rec["id"]
    lx, ly, lz = o["legendary"]
    old = S.Entity("cobblemon:pokemon", (lx + 0.5, float(ly), lz + 0.5), nbt={"Pokemon": {"Species": rec["species"]}},
                   tags=(tag,))
    w.save(old)
    return w, o, natural, live, old


def retire_steps(doc, ground):
    steps = L.placement_steps(doc, ground)[:3]
    assert steps[0] == ("fn", "cobblers:legendary/regigigas/retire_first_chamber") and steps[1][0] == "wait"
    assert steps[2][0] == "check" and steps[2][1][2] == 0
    return steps


def mismatches(w, o, natural, doc, ground):
    """Cells whose block after the cleanup is not the terrain the heightmap says belongs there."""
    return [c for c in hull_cells(o) if w.block_at(*c).split("[")[0] != natural(*c)]


HOLDER = "#legret_regigigas_first_chamber"


@pytest.mark.parametrize("delay", [0, 35, 90])
@pytest.mark.slow
def test_the_cleanup_restores_the_hull_kills_only_the_old_legendary_and_reads_zero_held(doc, ground, delay):
    w, o, natural, live, old = set_up(doc, ground, delay)
    obj = doc["objective"]
    w.set_score("#regigigas", obj, 1, w.server())     # the old plug had been opened: its score is 1
    assert mismatches(w, o, natural, doc, ground), "the fixture's chamber is not carved: the test would pass vacuously"
    run_steps(w, retire_steps(doc, ground))
    bad = mismatches(w, o, natural, doc, ground)
    assert not bad, "%d cell(s) not terrain after the cleanup, e.g. %s" % (len(bad), bad[:3])
    assert not old.alive, "the old chamber's legendary survived"
    assert live.alive, "the LIVE legendary (same tag, elsewhere) was killed"
    assert w.get_score("#regigigas", obj, w.server()) == 0, "the retired chamber's open score was not cleared"
    assert w.get_score(HOLDER, CL.OBJ, w.server()) == 0, "the held count is not 0 after a clean run"
    assert not w.forced, "the cleanup left chunks force-loaded"
    assert not w.errors, w.errors


@pytest.mark.parametrize("where", ["chamber", "passage", "shaft"])
@pytest.mark.slow
def test_a_player_in_a_retired_void_stops_the_cleanup_and_the_step_reads_it(doc, ground, where):
    # Without the guard the fill buries the player. Without the held count the refusal would read as done.
    w, o, natural, live, old = set_up(doc, ground)
    obj = doc["objective"]
    w.set_score("#regigigas", obj, 1, w.server())
    b = o[where]
    w.add_player(((b[0] + b[3]) / 2 + 0.5, float(b[1]), (b[2] + b[5]) / 2 + 0.5))
    before = {c: w.block_at(*c) for c in list(hull_cells(o))[:2000]}
    run_steps(w, retire_steps(doc, ground))
    assert not [1 for _t, k, _d in w.log if k == "fill"], "the cleanup wrote blocks with a player in the %s" % where
    assert old.alive, "the old legendary was killed while the restore was refused"
    assert all(w.block_at(*c) == v for c, v in before.items())
    assert w.get_score("#regigigas", obj, w.server()) == 1, "the score was cleared although nothing was restored"
    assert w.get_score(HOLDER, CL.OBJ, w.server()) == 1, "the step would read 0 held and call a refusal done"


@pytest.mark.slow
def test_a_player_standing_on_the_plug_top_does_not_stop_the_cleanup(doc, ground):
    # The surface is not a void: feet at the plug's top block + 1 are outside the shaft's box.
    w, o, natural, live, old = set_up(doc, ground)
    px, pz = o["plug"][0] + 1, o["plug"][2] + 1
    w.add_player((px + 0.5, float(o["my"] + 1), pz + 0.5))
    run_steps(w, retire_steps(doc, ground))
    assert w.get_score(HOLDER, CL.OBJ, w.server()) == 0 and not mismatches(w, o, natural, doc, ground)


@pytest.mark.slow
def test_a_second_run_writes_nothing_and_does_not_reseal_a_chamber_opened_since(doc, ground):
    # R14L re-runs. After the first run the live chamber may have been opened (score 1): a second cleanup must not
    # clear that score (carve_once would then re-seal the opened chamber) and must write no block.
    w, o, natural, live, old = set_up(doc, ground)
    obj = doc["objective"]
    run_steps(w, retire_steps(doc, ground))
    w.set_score("#regigigas", obj, 1, w.server())
    n = len(w.log)
    run_steps(w, retire_steps(doc, ground))
    again = w.log[n:]
    assert not [1 for _t, k, _d in again if k in ("fill", "setblock", "kill")], "a second run wrote or killed: %s" % again[:3]
    assert w.get_score("#regigigas", obj, w.server()) == 1, "a second run cleared the live chamber's open score"
    assert w.get_score(HOLDER, CL.OBJ, w.server()) == 0 and live.alive
    assert not mismatches(w, o, natural, doc, ground)


@pytest.mark.slow
def test_a_world_that_never_had_the_old_chamber_is_left_alone(doc, ground):
    # The live server may never have built it. With no pedestal the restore must not run (it would stamp the guessed
    # surface block over real terrain); the probe is the old pedestal, read from the world.
    w, o, natural, live, old = set_up(doc, ground)
    w.terrain = natural
    run_steps(w, retire_steps(doc, ground))
    assert not [1 for _t, k, _d in w.log if k in ("fill", "setblock")], "blocks written into a world with no old chamber"
    assert live.alive and w.get_score(HOLDER, CL.OBJ, w.server()) == 0


@pytest.mark.slow
def test_generator_mutation_a_shrunk_restore_leaves_the_old_chamber_open_in_the_world(doc, ground, monkeypatch):
    # Mutates the generator; the world's old chamber is set up from the audit's derivation, so a restore that is too
    # small leaves cells that are not terrain. Proves mismatches() can fail, so the passing run above means something.
    orig = L.geometry

    def mutated(rec, doc_, ground_):
        g = orig(rec, doc_, ground_)
        if g["anchor"] == (3560, 1760):
            c = g["chamber"]
            g["chamber"] = (c[0] + 2, c[1], c[2] + 2, c[3] - 2, c[4], c[5] - 2)
        return g

    monkeypatch.setattr(L, "geometry", mutated)
    w, o, natural, live, old = set_up(doc, ground)
    run_steps(w, retire_steps(doc, ground))
    assert mismatches(w, o, natural, doc, ground), "a shrunk restore still left the world as terrain: the check is blind"


def test_the_cleanup_runs_before_any_chamber_step_and_every_chamber_step_still_follows(doc, ground):
    steps = L.placement_steps(doc, ground)
    first = next(i for i, s in enumerate(steps) if s[0] == "cmd")
    assert steps.index(("fn", "cobblers:legendary/regigigas/retire_first_chamber")) < first
    assert sum(1 for s in steps if s[0] == "fn" and s[1].endswith("/place")) == len(L.emitted(doc))
