"""tools/arena_audit.py: Heaven's Arena (schema 2, the halls) audited from the canvas tools/deep_city.py writes.

Written by an agent that did not build the arena (CLAUDE.md principle 16). Every expectation comes from
data/deep_city.json `arena` and data/arena_trainers.json through the audit's own geometry; the build is only the
artifact under test.

Independence was proved by MUTATING THE GENERATOR with the data untouched (CLAUDE.md "How to prove an audit is
independent"). Run 2026-10-03 by hand, then kept as test_audit_catches_a_mutated_generator below:

  ring    tools/deep_city.py build_arena_halls, the ring's x loop `range(-half, half + 1)` -> `range(-half + 1,
          half + 1)` (its west column gone; the builder's own stand check still passes and the build completes).
          The audit: 77 ring PROBLEMS, "tier 1's ring is not one step over the floor at (3604, 16, 3248):
          minecraft:air on rechiseled:blackstone_polished_connecting"; nothing else.
  taper   arena_geometry's shell_r `if y > ty` -> `if y >= ty` (the setback floors shrink with the course above;
          the build completes). The audit: 372 floors PROBLEMS, "the floor at y100 has no floor at (3593, 3245)
          (r=16.5, reaching 16): minecraft:air".
  air     build_arena_halls' drum loop skips every AIR write (the guarantee that schema 1's core and decks do not
          survive in a world applied before 2026-10-03; the build completes). The audit: "86473 block(s) of the
          drum are never written", with shell, ring, seats and gates problems for the unwritten cells. The walk
          does not see it (an unwritten cell is air to it): only the drum check does.

Each mutation was applied in memory to the generator's source and the data files were untouched; the same three
run on every test session (test_audit_catches_a_mutated_generator). tools/deep_city.py is unchanged by this work.

Synthetic: the gate walk is also tested on a hand-made stair (no heightmap) with hand-computed results, so the
walk is not only proved on the one surface it was written against.

Not covered (validity is not runtime behaviour, .claude/rules/testing.md): whether the cycle really turns a player
back in game, a player's real position inside a cell (the walk centres him), knockback, flying mounts, block
breaking through the shell from the city's streets at y32-y66, rctmod battles, and whether the emitted function
files place the canvas faithfully (tests/test_deep_city.py and tools/deep_walk_audit.py read the commands).
"""
from __future__ import annotations

import ast
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import arena_audit as A  # noqa: E402
import deep_city as DC  # noqa: E402
from terrain import env_source_root  # noqa: E402

AR, TRAINERS = A.load()


@pytest.fixture(scope="module")
def root():
    r = env_source_root()
    if not r or not Path(r).is_dir():
        pytest.skip("no source root: the Deep's city is built from the heightmap")
    return r


@pytest.fixture(scope="module")
def built(root):
    cv, plan, _s, spec = DC.build(root, None)
    return cv, plan, spec


@pytest.fixture(scope="module")
def result(built):
    cv, plan, _spec = built
    return A.audit(cv.get, AR, TRAINERS, tuple(plan["spire"]["centre"]), int(plan["arena"]["lobby"]),
                   A.cycle_lines())


# ------------------------------------------------------------------ hand-computed, no heightmap

def test_a_player_on_the_floor_is_outside_his_tiers_gate_box():
    # Removing this lets a box that swallows the floor (a tp that fires on the landing itself) pass unnoticed.
    box = [3607, 18, 3239, 4, 13, 4]                     # tier 1's: [x, x + dx + 1) on each axis
    assert not A.in_box(box, (3609, 16, 3241))            # feet on the y15 floor: head 17.8 < 18
    assert A.in_box(box, (3609, 17, 3241))                # one step up: head 18.8 > 18
    assert A.in_box(box, (3609, 31, 3241))                # the last shaft cell under y32
    assert not A.in_box(box, (3609, 32, 3241))            # standing at y32: 32 < 32 is false
    assert not A.in_box(box, (3612, 20, 3241))            # the bay's wall column, x 3612: 3612.2 < 3612 is false
    assert A.in_box(box, (3611, 20, 3243))


def test_the_taper_narrows_only_the_courses_above_a_setback():
    # Removing this lets a reading of `taper` that shrinks the setback's own floor (the ledge) pass.
    ar = {"radius": 16, "taper": [[117, 12], [100, 14]]}
    assert [A.shell_radius(ar, y) for y in (99, 100, 101, 116, 117, 118, 128)] == [16, 16, 14, 14, 14, 12, 12]


def test_expectations_from_the_data_match_hand_arithmetic():
    # Removing this lets the audit's own geometry drift from the data's meaning with nothing to compare it to.
    # centre (3609, 3249): bay centre (0, -8) -> (3609, 3241), 5x5 interior 3607..3611 x 3239..3243; tier 1 y15,
    # next y32 -> box y 18, dy 32 - 18 - 1 = 13; tier 7 y117, crown 128 -> dy 128 - 120 - 1 = 7.
    # ring corner r = hypot(0 + 5, 4 + 5) = 10.296; rows fit while hall - rows >= 11.796: tiers 1-5 hall 15.5 -> 3,
    # tier 6 (y101 is r14) 13.5 -> 1, tier 7 (r12) 11.5 -> 0 -- benches_why's "all three ... one ... none".
    E = A.expect(AR, TRAINERS, (3609, 3249), 0)
    assert E["tier"][1]["box"] == [3607, 18, 3239, 4, 13, 4]
    assert E["tier"][7]["box"] == [3607, 120, 3239, 4, 7, 4]
    assert [E["tier"][n]["rows"] for n in range(1, 8)] == [3, 3, 3, 3, 3, 1, 0]
    assert E["tier"][1]["stand"] == (3609, 17, 3257) and E["tier"][1]["mark"] == (3609, 17, 3249)


def _stair_world():
    """A hand-made world: ground at y0 everywhere (None under y1 is rock), and a solid stair along +x, step i at
    (i, 1..i, 0) for i = 1..6, onto an upper floor at y6 for x 6..8."""
    v = {}
    for i in range(1, 7):
        for y in range(1, i + 1):
            v[(i, y, 0)] = "minecraft:stone"
    for x in range(6, 9):
        for z in (-1, 0, 1):
            v[(x, 6, z)] = "minecraft:stone"
    E = {"centre": (0, 0), "rad": 9, "lobby": 0, "crown": 10}
    return (lambda x, y, z: v.get((x, y, z))), E


def test_the_gate_stops_the_climb_and_never_the_descent_on_a_hand_made_stair():
    # Removing this leaves the gate walk proved only on the arena it was written against.
    get, E = _stair_world()
    wk, drum = A.make_walker(get, E)
    free, _f = A.gated_walk(wk, [(-3, 1, 0)], drum, [])
    assert (8, 7, 0) in free                               # no gate: the upper floor is reached
    box, landing = [3, 3, -1, 2, 2, 2], (-3, 1, 0)         # x 3..5, y [3, 6): steps 3..5's feet 4..6 overlap
    up, fired = A.gated_walk(wk, [(-3, 1, 0)], drum, [(box, landing)])
    assert (3, 4, 0) in up and fired == {0}                # step 3 is reached, and turned back
    assert (4, 5, 0) not in up and (8, 7, 0) not in up      # nothing past it
    down, fired = A.gated_walk(wk, [(8, 7, 0)], drum, [(box, landing)])
    assert (5, 6, 0) in down                               # feet y6: hitbox [6, 7.8) misses [3, 6)
    assert landing in down and fired == {0}                # caught on the way down, and put lower still


# ------------------------------------------------------------------ the real build

@pytest.mark.slow
@pytest.mark.parametrize("check", A.CHECKS)
def test_the_built_arena_holds(result, check):
    # Removing this lets the named property of the built arena (A.CHECKS; tools/arena_audit.py's docstring) break
    # with nothing failing.
    problems, _stats = result
    got = [m for k, m in problems if k == check]
    assert not got, "%d: %s" % (len(got), got[:5])


@pytest.mark.slow
def test_the_climb_is_walked_tier_by_tier(result):
    # Removing this lets the walk quietly reach nothing (a start not on a floor) and every walk check pass vacuously.
    _p, stats = result
    tiers, crown = AR["tiers"], AR["crown"]
    for k, top in stats["climb_top"].items():
        if k < len(tiers):
            assert tiers[k] + 1 <= top < (tiers[k + 1] if k + 1 < len(tiers) else crown) + 1, (k, top)
        else:
            assert top >= crown + 1
    assert stats["bench_rows"] == {1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 0}
    assert len(stats["exits"]) == len(tiers)


@pytest.mark.slow
def test_schema_one_leaves_nothing_the_halls_do_not_overwrite(built):
    # Removing this lets a block of schema 1 (2026-10-01, still in the staging world) outside the volume the audit
    # requires written survive a re-apply. build_spire_ring here only lists what the OLD world holds; nothing
    # about schema 2 is expected from it.
    cv, plan, spec = built
    scx, scz = plan["spire"]["centre"]
    g0 = int(plan["arena"]["lobby"])
    old = DC.Canvas()
    DC.build_spire_ring(old, DC.Palette(spec, None), None, spec, spec["spire"], spec["arena"], scx, scz, g0,
                        int(spec["arena"]["radius"]))
    left = [p for p, (b, _ph) in old.v.items() if p[1] > g0 and not A.is_air(b) and cv.get(*p) is None]
    assert old.v and not left, left[:5]


@pytest.mark.slow
def test_a_seat_moved_off_its_stand_is_named(built):
    # Removing this lets the seat check go blind: a record whose seat no longer names the stand passes.
    cv, plan, _spec = built
    moved = json.loads(json.dumps(TRAINERS))
    moved[2]["seat"][0] += 1
    problems, _s = A.audit(cv.get, AR, moved, tuple(plan["spire"]["centre"]), int(plan["arena"]["lobby"]), None)
    assert any(k == "seats" and "arena_tier_3_champion" in m for k, m in problems)


@pytest.mark.slow
def test_a_cycle_missing_a_tiers_tp_is_named(built):
    # Removing this lets a cycle that announces the gate but never turns the player back pass.
    cv, plan, _spec = built
    cycle = [ln for ln in A.cycle_lines() if not (ln.startswith("tp @a[") and "arena_tier_4_champion" in ln)]
    problems, _s = A.audit(cv.get, AR, TRAINERS, tuple(plan["spire"]["centre"]), int(plan["arena"]["lobby"]), cycle)
    assert any(k == "cycle" and "arena_tier_4_champion" in m for k, m in problems)


MUTATIONS = {
    # name: (exact source text in tools/deep_city.py, its mutant, the check that must fire)
    "ring": ("        for dx in range(-half, half + 1):\n            for dz in range(-half, half + 1):\n"
             "                edge = max(abs(dx), abs(dz)) == half",
             "        for dx in range(-half + 1, half + 1):\n            for dz in range(-half, half + 1):\n"
             "                edge = max(abs(dx), abs(dz)) == half", "ring"),
    "taper": ("            if y > ty:\n                r = tr", "            if y >= ty:\n                r = tr",
              "floors"),
    "air": ('cv.put(x, y, z, b, owner="spire", exterior=ext)',
            'b == "minecraft:air" or cv.put(x, y, z, b, owner="spire", exterior=ext)', "drum"),
}


@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_audit_catches_a_mutated_generator(root, name):
    # Removing this loses the proof that the audit does not share the builder's derivation: each mutation changes
    # tools/deep_city.py's code (in memory) and leaves every data file alone, and the audit must fail.
    src = Path(DC.__file__).read_text(encoding="utf-8")
    old, new, check = MUTATIONS[name]
    assert src.count(old) == 1, "the generator changed under this mutation; re-point it at the same rule"
    mod = types.ModuleType("deep_city_mutant_%s" % name)
    mod.__file__ = DC.__file__
    exec(compile(src.replace(old, new), DC.__file__, "exec"), mod.__dict__)
    cv, plan, _s, _spec = mod.build(root, None)
    problems, _st = A.audit(cv.get, AR, TRAINERS, tuple(plan["spire"]["centre"]), int(plan["arena"]["lobby"]), None)
    assert any(k == check for k, _m in problems), sorted({k for k, _m in problems})


def test_the_audit_takes_no_expectation_from_the_builder():
    # Removing this lets a later edit take the arena's geometry from tools/deep_city.py, and the audit would then
    # agree with whatever the builder does.
    tree = ast.parse((ROOT / "tools" / "arena_audit.py").read_text(encoding="utf-8"))
    forbidden = {"arena_geometry", "build_arena_halls", "arena_plan_halls", "frame", "ring_cells", "_outward_wall",
                 "build_spire_ring", "ARENA_BACK", "stair_plan"}
    used = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
           {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
           {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not used & forbidden, used & forbidden


def test_prepare_runs_the_arena_audit_right_after_the_city_build():
    # Removing this lets prepare ship an arena no audit read, or audit it before the city it reads is built.
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    build = src.index('add("deep_city:build", "deep_city.py", "build", *src)')
    audit = src.index('add("arena_audit", "arena_audit.py", *src)')
    assert build < audit < src.index('add("deep_city_audit", "deep_city_audit.py", *src)')
