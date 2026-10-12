"""The maze forest's glade shrines: data/maze_shrines.json, tools/maze_shrines.py, tools/maze_shrines_audit.py and R12MS.

NOT written by an independent test author: the session that built the shrines wrote these (the brief asked for the audit,
the tests and the wiring together). Treat the verdicts below as the implementer's; an independent read is still owed.

Four parts:
  1. The data: six shrines, one per glade of the maze plan, the plan's own list of openings derived here from
     tools/maze_forest.py CLEARINGS (kind glade / secret), the sapling and mansion clearings untouched.
  2. The audit's independence, by GENERATOR mutation (the data is never edited): the pack is built through the generator's
     own functions with one thing wrong in the generator, bypassing the generator's own guards, and the audit must name
     it: a footprint pushed out of its glade and onto a corridor, a piece floating a block up, a spawn-condition block, a
     second barrel in an old shrine. The same audit passes the real build, so it is not refusing everything. Two source
     mutations (data/legendaries.json read through a changed copy) prove the hints are checked against the legendaries.
  3. The finds: data/rewards.json's three new records are what the build writes, early consumables only.
  4. The wiring: the pack is installed, R12MS runs every function after R12 and before R12R5, prepare builds and audits it.

Needs the canonical heightmap (tools/ground.py); SKIPS without it. A skip is not a pass. Not covered: anything in a world
(the functions have not run on staging), and painted trees in a glade.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402
import maze_forest as MF  # noqa: E402
import maze_shrines as MS  # noqa: E402
import maze_shrines_audit as MA  # noqa: E402
import rewards_pack  # noqa: E402

DATA = json.loads((ROOT / "data" / "maze_shrines.json").read_text(encoding="utf-8"))
SHRINES = DATA["shrines"]


@pytest.fixture(scope="module")
def ground():
    import ground as G
    try:
        return G.Ground(None)
    except Exception as e:  # no heightmap in this checkout
        pytest.skip("no canonical heightmap here: %s" % str(e)[:100])


def make_pack(out, ground, kinds=None, shift=(0, 0)):
    """The generator's output for the real data, bypassing its guards (check_site, the block allow-list), so a mutated
    generator can write what its own checks would have refused. `kinds` replaces MS.KINDS; `shift` moves every block."""
    old = dict(MS.KINDS)
    if kinds:
        MS.KINDS.update(kinds)
    try:
        funcs = out / "data" / "cobblers" / "function" / MS.FOLDER
        funcs.mkdir(parents=True)
        for spec in SHRINES:
            blocks, floor = MS.world_blocks(spec, ground)
            blocks = [(x + shift[0], y, z + shift[1], s, n) for x, y, z, s, n in blocks]
            cmds = function_limits.ensure_loaded(MS.commands_for(spec, blocks, floor))
            (funcs / ("%s.mcfunction" % spec["id"])).write_text("\n".join(cmds) + "\n", encoding="utf-8")
        (funcs / "index.txt").write_text("\n".join(s["id"] for s in SHRINES) + "\n", encoding="utf-8")
    finally:
        MS.KINDS.clear()
        MS.KINDS.update(old)
    return out


def audit(pack):
    problems, _n = MA.audit(pack)
    return problems


def mutated(name, fn):
    build, width = MS.KINDS[name]
    return {name: (lambda spec, h: fn(build(spec, h)), width)}


# ------------------------------------------------------------------------------------------------------- 1. the data
# Without it a glade goes unmarked, a shrine lands in the sapling or mansion clearing, or a hint names an unsited legendary.
def test_the_shrines_are_exactly_the_plans_glades_and_secret_glades():
    plan = {c["id"]: c for c in MF.CLEARINGS}
    want = sorted(c["id"] for c in MF.CLEARINGS if c["kind"] in ("glade", "secret"))
    assert sorted(s["glade"] for s in SHRINES) == want and len(want) == 6
    assert not [s for s in SHRINES if s["glade"] in ("sapling", "mansion")]
    assert sorted(plan[g]["r"] for g in want if plan[g]["kind"] == "glade") == [10, 10, 11]   # docs/world-building/STRUCTURE_DECISIONS.md
    assert MS.validate_data(DATA) == []


# Without it a secret glade's older shrine and a glade's stele are swapped, or a stele has no find of its own.
def test_a_glade_gets_a_stele_with_its_own_find_and_a_secret_glade_an_old_shrine_over_the_existing_one():
    plan = {c["id"]: c for c in MF.CLEARINGS}
    existing = {"fern_glade": "r1_fern_glade", "west_hollow": "r1_west_hollow", "north_ring": "r1_north_ring"}
    for s in SHRINES:
        if plan[s["glade"]]["kind"] == "glade":
            assert s["kind"] == "stele" and s["reward"].startswith("r1_glade_")
        else:
            assert s["kind"] == "old_shrine" and s["existing_find"] == existing[s["glade"]] and "reward" not in s


# ----------------------------------------------------------------------------------------------- 2. the audit by mutation
# Without it the audit is shown to pass nothing: the real build must come out clean.
def test_the_real_build_is_clean(tmp_path, ground):
    pack = make_pack(tmp_path / "p", ground)
    problems, n = MA.audit(pack)
    assert problems == [] and n >= 150


# Without it a piece that spills out of its glade onto a corridor (the 3-wide dead ends and the paths must stay open) passes.
def test_a_generator_that_shifts_the_footprint_out_of_the_glade_is_caught(tmp_path, ground):
    pack = make_pack(tmp_path / "p", ground, shift=(6, 0))
    got = "\n".join(audit(pack))
    assert "outside r" in got and "edge of corridor" in got


# Without it a piece that grows wider than a glade can hold (the generator's width is its own claim) passes.
def test_a_generator_that_widens_a_piece_is_caught(tmp_path, ground):
    def widen(p):
        return p + [(x, 0, z, MS.MCOB, "") for x in (-4, 4) for z in range(0, 4)]
    pack = make_pack(tmp_path / "p", ground, kinds=mutated("old_shrine", widen))
    assert any("footprint" in m or "outside r" in m for m in audit(pack))


# Without it a shrine hovering a block over the ground (or buried) passes.
def test_a_generator_that_lifts_a_piece_a_block_is_caught(tmp_path, ground):
    def lift(p):
        return [(x, dy + 1, z, s, n) for x, dy, z, s, n in p]
    pack = make_pack(tmp_path / "p", ground, kinds=mutated("stele", lift))
    assert any("floating or buried" in m for m in audit(pack))


# Without it a spawn-condition block (a flower, a flowering azalea) decides Route 1's encounters.
def test_a_generator_that_adds_a_spawn_condition_block_is_caught(tmp_path, ground):
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    assert "minecraft:flowering_azalea" in spawn

    def azalea(p):
        return p + [(1, 0, 1, "minecraft:flowering_azalea", "")]
    pack = make_pack(tmp_path / "p", ground, kinds=mutated("stele", azalea))
    got = "\n".join(audit(pack))
    assert "spawn condition" in got and "not in data/maze_shrines.json" in got


# Without it an old shrine grows a second reward in a glade that already has one.
def test_a_generator_that_puts_a_barrel_in_an_old_shrine_is_caught(tmp_path, ground):
    def barrel(p):
        return p + [(2, 0, 3, MS.BARREL, "")]
    pack = make_pack(tmp_path / "p", ground, kinds=mutated("old_shrine", barrel))
    assert any("holds no barrel" in m for m in audit(pack))


# Without it a light block lights the glade, against the lantern-on-a-post rule.
def test_a_generator_that_writes_a_light_block_is_caught(tmp_path, ground):
    def light(p):
        return p + [(1, 0, 3, "minecraft:light[level=12]", "")]
    pack = make_pack(tmp_path / "p", ground, kinds=mutated("stele", light))
    assert any("minecraft:light" in m for m in audit(pack))


# Without it a lantern hangs in the air (the forest's lamps are lanterns on posts).
def test_a_generator_that_floats_a_lantern_is_caught(tmp_path, ground):
    def drop_post(p):
        return [b for b in p if b[3] != "minecraft:oak_fence"]
    pack = make_pack(tmp_path / "p", ground, kinds=mutated("stele", drop_post))
    assert any("not on a fence post" in m for m in audit(pack))


# Without it a clearing fill reaching past the piece's own columns wipes the forest round the glade.
def test_a_clearing_fill_outside_the_pieces_columns_is_caught(tmp_path, ground):
    pack = make_pack(tmp_path / "p", ground)
    f = pack / "data" / "cobblers" / "function" / MS.FOLDER / "mesprit_stone.mcfunction"
    f.write_text(f.read_text(encoding="utf-8") + "fill 1400 120 4800 1410 130 4810 minecraft:air replace #minecraft:replaceable\n",
                 encoding="utf-8")
    assert any("clearing fills reach columns" in m for m in audit(pack))


def _with_legendaries(monkeypatch, edit):
    real = MA.load

    def load(p):
        d = real(p)
        if Path(p).name == "legendaries.json":
            edit(d)
        return d
    monkeypatch.setattr(MA, "load", load)


# Without it a tablet can name a place the legendary does not sleep at.
def test_a_hint_whose_site_the_legendaries_do_not_hold_is_caught(tmp_path, ground, monkeypatch):
    pack = make_pack(tmp_path / "p", ground)

    def edit(d):
        for e in d["encounters"]:
            if e["id"] == "uxie":
                e["site"] = "somewhere_else"
    _with_legendaries(monkeypatch, edit)
    assert any("uxie" in m and "site" in m for m in audit(pack))


# Without it a tablet's compass word can be false: Tornadus is north of the ring, so a mover of its portal east breaks it.
def test_a_direction_the_bearing_contradicts_is_caught(tmp_path, ground, monkeypatch):
    pack = make_pack(tmp_path / "p", ground)

    def edit(d):
        for e in d["encounters"]:
            if e["id"] == "tornadus":
                e["portal"] = [9000, 4376]
    _with_legendaries(monkeypatch, edit)
    assert any("tornadus" in m and "lies east" in m for m in audit(pack))


# Without it a hint toward an encounter that is only proposed passes as true.
def test_a_hint_toward_an_unsited_encounter_is_caught(tmp_path, ground, monkeypatch):
    pack = make_pack(tmp_path / "p", ground)

    def edit(d):
        for e in d["encounters"]:
            if e["id"] == "azelf":
                e["status"] = "proposed"
    _with_legendaries(monkeypatch, edit)
    assert any("azelf" in m and "status" in m for m in audit(pack))


# ------------------------------------------------------------------------------------------------------- 3. the finds
# Without it a find drifts from its barrel (the trigger would fire somewhere else) or gives more than a first route's worth.
def test_the_glade_finds_match_the_build_and_are_early_consumables(ground):
    class A:
        source_root = None
    data, built = MS.sites(A)
    assert MS.record_drift(data, built) == []
    recs = {r["id"]: r for r in json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))["rewards"]}
    mine = [s["reward"] for s in SHRINES if s["kind"] == "stele"]
    assert len(mine) == 3 and rewards_pack.problems({"rewards": [recs[i] for i in mine]}) == []
    for rid in mine:
        r = recs[rid]
        assert r["kind"] == "cache" and sum(c["count"] for c in r["contents"]) <= DATA["rules"]["max_find_items"]
        assert {c["item"] for c in r["contents"]} <= {"cobblemon:oran_berry", "cobblemon:pecha_berry", "cobblemon:potion"}
        assert "tools/maze_shrines.py" in r["built_by"]


# Without it a data/world_probes.json entry goes stale and presence_audit probes the wrong block.
def test_the_presence_probes_are_the_builds(ground):
    class A:
        source_root = None
        write = False
    assert MS.probes(A) == 0


# ------------------------------------------------------------------------------------------------------- 4. the wiring
# Without it the pack is built and never installed, or run by no step (the project's recurring failure).
def test_the_pack_is_installed_and_prepare_builds_and_audits_it():
    import reapply
    assert "cobblers_maze_shrines" in reapply.SERVER_PACKS
    assert "cobblers_maze_shrines" not in reapply.EXCLUDED and "cobblers_maze_shrines" not in reapply.WORLD_LOCAL
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert 'add("maze_shrines:build", "maze_shrines.py", "build", *src)' in src
    assert 'add("maze_shrines_audit", "maze_shrines_audit.py", *src)' in src
    assert src.index('add("maze_shrines:build"') < src.index('add("maze_shrines_audit"')


# Without it the shrines go up before the forest and the event sites they stand beside, or after what R17 places.
def test_r12ms_is_between_r12_and_r12r5_in_the_step_list():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    i12, ims, i125 = (src.index('out.append(("%s"' % s) for s in ("R12", "R12MS", "R12R5"))
    assert i12 < ims < i125
    assert "indexed(\"cobblers_maze_shrines\", \"maze_shrines\")" in src


def _built_pack():
    import reapply
    if not (reapply.PACKS / "cobblers_maze_shrines" / "data" / "cobblers" / "function" / MS.FOLDER / "index.txt").is_file():
        pytest.skip("cobblers_maze_shrines is not built here (python tools/maze_shrines.py build)")
    return reapply


# Without it the fail-closed coverage check cannot tell that nothing runs the pack (the project's recurring failure).
def test_a_step_that_runs_the_pack_covers_it_and_no_step_leaves_it_uncovered():
    reapply = _built_pack()
    listed = reapply.indexed("cobblers_maze_shrines", MS.FOLDER)
    assert listed == [s["id"] for s in SHRINES]
    todo = [("R12MS", "x", [("fn", "cobblers:maze_shrines/%s" % f) for f in listed])]
    assert not [b for b in reapply.uncovered(todo) if b.startswith("cobblers_maze_shrines ")]
    assert any(b.startswith("cobblers_maze_shrines ") for b in reapply.uncovered([]))


# Without it steps() builds a different R12MS from the one the pack lists, or it runs out of order. Needs every other pack
# and derived/ (a main checkout after prepare); SKIPS elsewhere.
def test_the_real_step_list_runs_every_function_in_order():
    reapply = _built_pack()
    try:
        steps = reapply.steps()
    except SystemExit as e:
        pytest.skip("reapply.steps() needs packs and derived files this checkout lacks: %s" % str(e)[:100])
    ids = [s[0] for s in steps]
    listed = reapply.indexed("cobblers_maze_shrines", MS.FOLDER)
    assert steps[ids.index("R12MS")][2] == [("fn", "cobblers:maze_shrines/%s" % f) for f in listed]
    assert ids.index("R12") < ids.index("R12MS") < ids.index("R12R5") < ids.index("R17")
    assert not [b for b in reapply.uncovered(steps) if b.startswith("cobblers_maze_shrines ")]
