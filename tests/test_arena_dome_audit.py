"""tools/arena_dome_audit.py: Heaven's Arena dome audited from the functions tools/arena_dome.py EMITS.

Written by an agent that did not build the dome (CLAUDE.md principle 16). The audit replays the emitted fill/setblock
commands into its own voxel map and takes every expectation from data/arena_dome.json's declared numbers, the
measurement in docs/world-building/ARENA_SITE_NORTH.md, the city's plan and canvas (tools/deep_city.py build) and the
pit's model (tools/rift_deep.py model). Nothing is imported from tools/arena_dome.py; here the builder is used only to
PRODUCE packs (its geometry() and emit(), the artifact under test), never for an expectation.

Independence was proved by MUTATING THE GENERATOR with every data file untouched (CLAUDE.md "How to prove an audit
is independent"). Run 2026-10-03 by hand, then kept as test_audit_catches_a_mutated_generator below (each mutation is
applied in memory to tools/arena_dome.py's source; the file on disk is never changed):

  drum      `Ri, Ro = dr["wall"]` -> both radii one smaller (37, 39). The audit: "drum: 16979 cells of the drum wall
            (38 < r <= 40, y1-70) are not solid", "floor: 239 footprint columns have no solid floor written at y0",
            "dome: 3540 columns' outer surface is off the half-ellipsoid (r40, rise 50)".
  venue     `vx, vz = v["centre"]` -> x + 2 (every venue two blocks east of its declared centre). The audit: "venues",
            five of them, "venue_1: 13 cells of its 13x13 floor at y1 are not solid" (its west column). The contract
            check alone does not see it: the shifted rings still cover every mark, spot and post.
  passage   the drum's passage air write removed (the lobby no longer opens into the dome). The audit: "drum: the
            passage is shut at 50 cells" and "shell: with the door open the inside does not reach the door's outside
            (3584, 1, 3217)".
  interior  the interior's air column write removed. The audit: "shell: 445620 cells inside the shell are never
            written (the world keeps what it held)"; nothing else, so only the shell check guards "interior written
            air".

A built-result mutation proves the city checks bite too (test_city_check_catches_a_dome_moved_onto_the_stacks): the
replayed dome moved 12 south lands on Stacks lots and the measured street.

Synthetic fixtures with hand-computed values test the replay, the flood and the walker away from the real dome, so
none of them is proved only on the surface it was written against.

Not covered (validity is not runtime behaviour, .claude/rules/testing.md): that R9AD runs the functions in a world,
forceload limits, light levels and mob spawning inside the dome, the arena runtime's use of the contract (spawning an
opponent at opponent_spot), a player's real hitbox and jump arc, and the world under the floor (the walk takes the pit
from tools/rift_deep.py model(), not from its emitted carve). Those need a boot and a functional test in experiments/.
"""
from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import arena_dome_audit as AU  # noqa: E402
import arena_dome as AD  # noqa: E402   (the artifact under test: geometry() and emit() only)
from terrain import env_source_root  # noqa: E402

SPEC, FIGHTS, FORBIDDEN = AU.load()


def _emit(mod, out):
    """The pack `mod` (the builder, or a mutant of it) would write, into `out`."""
    cv = mod.geometry(SPEC)
    old = mod.OUT
    mod.OUT = out
    try:
        mod.emit(cv)
    finally:
        mod.OUT = old
    return out


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    W, P = AU.replay_pack(_emit(AD, tmp_path_factory.mktemp("dome") / "pack"))
    assert not P, P
    return W


@pytest.fixture(scope="module")
def city():
    r = env_source_root()
    if not r or not Path(r).is_dir():
        pytest.skip("no source root: the city and the pit model are built from the heightmap")
    return AU.city_state(r)


# ------------------------------------------------------------------ synthetic: the replay, the flood, the walker

def test_replay_applies_fills_and_setblocks_in_command_order():
    # Removing this lets the voxeliser drift from Minecraft's command semantics, and every check reads a wrong dome.
    P = []
    W = AU.replay_lines(["# a comment", "forceload add 0 0 15 15",
                         "fill 0 0 0 2 0 2 minecraft:stone",
                         "setblock 1 0 1 minecraft:air",
                         "fill 0 2 0 0 1 0 minecraft:glass"], {}, P)
    assert P == []
    assert len(W) == 9 + 2
    assert W[(1, 0, 1)] == "minecraft:air" and W[(0, 0, 0)] == "minecraft:stone"
    assert W[(0, 1, 0)] == W[(0, 2, 0)] == "minecraft:glass"


def test_replay_refuses_what_it_cannot_replay():
    # Removing this lets an unreplayed command (a hollow fill, a clone, a say) pass as if it wrote nothing.
    P = []
    AU.replay_lines(["fill 0 0 0 1 1 1 minecraft:stone hollow", "clone 0 0 0 1 1 1 5 5 5", "say hi"], {}, P)
    assert [k for k, _m in P] == ["commands"] * 3


def test_a_missing_pack_is_a_problem_not_an_empty_pass(tmp_path):
    # Removing this lets the audit pass a dome that was never built, reading zero blocks as zero faults.
    W, P = AU.replay_pack(tmp_path)
    assert W == {} and [k for k, _m in P] == ["commands"]


def _box(door=False, hole=None):
    """A 5x5x5 stone shell round a 3x3x3 air room, every cell written; optionally a 1x2 door in the z=0 wall."""
    W = {}
    for x in range(5):
        for y in range(5):
            for z in range(5):
                inner = 1 <= x <= 3 and 1 <= y <= 3 and 1 <= z <= 3
                W[(x, y, z)] = "minecraft:air" if inner else "minecraft:stone"
    if door:
        W[(2, 1, 0)] = W[(2, 2, 0)] = "minecraft:oak_door[half=lower]"
    if hole:
        del W[hole]
    return W


def test_flood_of_a_closed_room_is_its_27_cells():
    # Removing this lets the shell check pass a flood that leaks or stops short, on a room whose answer is known.
    f = AU.shell_flood(_box(), (2, 2, 2), [])
    assert f["cells"] == 27 and not f["escaped"] and f["unwritten_inside"] == []


def test_flood_leaves_only_through_the_door_it_is_told_to_shut():
    # Removing this lets a dome whose door is its only opening be indistinguishable from one with a second hole.
    door = [(2, 1, 0), (2, 2, 0)]
    shut = AU.shell_flood(_box(door=True), (2, 2, 2), door)
    assert not shut["escaped"] and shut["cells"] == 27
    opened = AU.shell_flood(_box(door=True), (2, 2, 2), [])
    assert opened["escaped"] and (2, 1, -1) in opened["reached"]
    holed = AU.shell_flood(_box(door=True, hole=(4, 2, 2)), (2, 2, 2), door)
    assert holed["escaped"]


def test_flood_names_an_interior_cell_that_is_never_written():
    # Removing this lets the dome leave air unwritten inside, where the world keeps whatever it held before.
    f = AU.shell_flood(_box(hole=(2, 3, 2)), (2, 2, 2), [])
    assert f["unwritten_inside"] == [(2, 3, 2)] and not f["escaped"]


def _strip(step_height):
    """A 5x1 floor at y0 along x, with a block column `step_height` high at x2."""
    code = np.zeros((5, 6, 1), np.int8)
    code[:, 0, 0] = 1
    for y in range(1, 1 + step_height):
        code[2, y, 0] = 1
    return AU.Walk(code, (0, 0, 0))


def test_walker_steps_up_one_block_and_not_two():
    # Removing this lets the reachability checks pass over walls a player cannot climb, or fail on a single step.
    d = _strip(1).distances((0, 1, 0))
    assert d[(2, 2, 0)] == 2 and d[(4, 1, 0)] == 4
    assert (4, 1, 0) not in _strip(2).distances((0, 1, 0))


# ------------------------------------------------------------------ the real build

def test_the_emitted_dome_holds_its_shape_contract_and_shell(built):
    # Removing this lets a dome ship with an open shell, a ring short of its floor, a mark in a wall, a forbidden
    # block, or a write outside its site: every shape and contract check, from the replayed functions.
    P, st = AU.shape_audit(built, SPEC, FIGHTS, FORBIDDEN)
    assert P == [], P[:10]
    assert st["top"] == SPEC["dome"]["cupola"]["top"] and st["columns"] > AU.DISC_COLUMNS


def test_the_dome_sits_in_the_city_without_cutting_a_walk(built, city):
    # Removing this lets the dome stand on a lot, a stair tower or the mouth plaza, come nearer than 6 to a door, or
    # cut the way from the Core to Victory Road or to any Stacks home.
    P, st = AU.city_audit(built, SPEC, city)
    assert P == [], P[:10]
    assert st["street"][0] >= AU.MIN_STREET and st["door_street"][0] >= AU.MIN_STREET
    assert st["stair_to_door"] and st["vr_to_door"] and st["core_to_vr_with"]
    assert st["core_to_vr_with"] >= st["core_to_vr_without"]
    kept, checked = st["floor_doors"]
    assert checked and kept == checked
    assert SPEC["limits"]["crown_must_clear"] == st["lip"], "data's lip is not the heightmap's"
    assert SPEC["limits"]["crown_max"] < st["hq_top"]


def test_city_check_catches_a_dome_moved_onto_the_stacks(built, city):
    # Removing this loses the proof that the city checks bite: the replayed dome moved 12 south (onto the Stacks and
    # across the stair's walk) must fail them, with the city's plan, not the dome's data, as the expectation.
    moved = {(x, y, z + 12): b for (x, y, z), b in built.items()}
    P, _st = AU.city_audit(moved, SPEC, city)
    assert {k for k, _m in P} >= {"city"}, P[:5]


MUTATIONS = {
    "drum": ('    Ri, Ro = dr["wall"]\n', '    Ri, Ro = dr["wall"][0] - 1, dr["wall"][1] - 1\n', "drum"),
    "venue": ('        vx, vz = v["centre"]\n        h, top, st = ',
              '        vx, vz = v["centre"][0] + 2, v["centre"][1]\n        h, top, st = ', "venues"),
    "passage": ('                cv.col(x, z, y0 + 1, pa["to_y"], AIR, owner="passage")\n', "                pass\n",
                "shell"),
    "interior": ('            cv.col(x, z, y0 + 1, base + int(math.floor(hi)), AIR)\n', "            pass\n", "shell"),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_audit_catches_a_mutated_generator(name, tmp_path):
    # Removing this loses the proof that the audit does not share the builder's derivation: each mutation changes
    # tools/arena_dome.py's code (in memory) with data/arena_dome.json untouched, and the audit must fail.
    src = Path(AD.__file__).read_text(encoding="utf-8")
    old, new, check = MUTATIONS[name]
    assert src.count(old) == 1, "the generator changed under this mutation; re-point it at the same rule"
    mod = types.ModuleType("arena_dome_mutant_%s" % name)
    mod.__file__ = AD.__file__
    exec(compile(src.replace(old, new), AD.__file__, "exec"), mod.__dict__)
    W, P = AU.replay_pack(_emit(mod, tmp_path / "pack"))
    P2, _st = AU.shape_audit(W, SPEC, FIGHTS, FORBIDDEN)
    assert check in {k for k, _m in P + P2}, sorted({k for k, _m in P + P2})


# ------------------------------------------------------------------ independence and wiring

def test_the_audit_takes_no_expectation_from_the_builder():
    # Removing this lets a later edit import tools/arena_dome.py's geometry, and the audit would agree with any dome.
    tree = ast.parse((ROOT / "tools" / "arena_dome_audit.py").read_text(encoding="utf-8"))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "arena_dome" not in mods
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"geometry", "footprint", "contract_problems", "shape_problems", "city_problems", "_near"}


def test_prepare_runs_the_dome_audit_right_after_its_build():
    # Removing this lets prepare ship a dome pack no independent audit read.
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    build = src.index('add("arena_dome:build", "arena_dome.py", "build", *src)')
    audit = src.index('add("arena_dome_audit", "arena_dome_audit.py", *src)')
    assert build < audit < src.index('add("relic_underground:build"')
