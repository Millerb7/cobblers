"""tools/hq_tower_audit.py: the independent audit of the Compact HQ tower as its packs build it.

Written by test-author, 2026-10-04; the tower (tools/hq_tower.py) was built by another agent. Three kinds of test:

  synthetic   the replay (fill, setblock, a sign's NBT with spaces, keep, replace), the tread rule for unwritten
              cells, the walk and the walk-back (a one-way drop), on hand-written fixtures computed in the comments
  real        the REAL generators emit into tmp -- tools/deep_city.py's block functions, tools/hq_tower.py's pack,
              tools/route_trainers.py's cycle -- and the audit replays them over tools/rift_deep.py's tread
  mutation    tools/hq_tower.py changed in memory (data untouched) and the audit must fail: the stair's holes left
              shut, a barrel on a trainer's seat, a write outside the interior, the climb's set-back put inside its
              own gate

The real and mutation tests need the canonical heightmap (terrain.env_source_root()); they skip without it. Not
covered: anything in game (see the tool's docstring); R9RU's writes unless its pack is built.
"""
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import hq_tower_audit as H  # noqa: E402


# ====================================================================== synthetic

# Protects: the replay's command forms; hand: a 3x1x3 stone floor at y0, air y1-y2 in the middle, a sign with
# spaced NBT at (0,1,0), a keep that cannot overwrite stone, a replace that only hits air.
def test_replay_by_hand():
    lines = ["fill 0 0 0 2 0 2 minecraft:stone", "setblock 1 1 1 minecraft:air",
             "setblock 0 1 0 minecraft:oak_sign[rotation=0]{front_text:{messages:['{\"text\":\"A B\"}']}}",
             "fill 0 0 0 2 0 2 minecraft:gold_block keep", "fill 1 1 1 1 1 1 minecraft:glass replace minecraft:air",
             "forceload add 0 0 2 2"]
    cells = H.replay_into({}, [("f", lines)], (0, 0, 0, 2, 3, 2))
    assert cells[(1, 0, 1)] == "minecraft:stone"                      # keep did not replace stone
    assert cells[(1, 1, 1)] == "minecraft:glass"                      # replace hit the air cell
    assert H.norm(cells[(0, 1, 0)]) == "minecraft:oak_sign" and H.nonsolid(cells[(0, 1, 0)])
    with pytest.raises(H.Unmodelled):
        H.replay_into({}, [("f", ["clone 0 0 0 1 1 1 5 5 5"])], (0, 0, 0, 2, 3, 2))


# Protects: unwritten cells follow the tread (rock at or below, air above), and the walk's step/drop rules and the
# walk-back; hand: tread y0 everywhere, a 2-high block at (2..4, 1..2, 0) forms a platform reached from x=1 by...
# nothing (a two-block rise); a 1-high step at (2,1,0) is climbed; a drop of 3 from a ledge is walked down but not up.
def test_walk_and_walk_back_by_hand():
    tread = lambda x, z: 0
    # a ledge: blocks at x 3..5 from y1 to y3, so its top stands at y4; a one-block step at x2 y1 (stand y2)
    cells = {}
    for x in range(3, 6):
        for y in (1, 2, 3):
            cells[(x, y, 0)] = "minecraft:stone"
    cells[(2, 1, 0)] = "minecraft:stone"
    m = H.Model(cells, tread)
    assert m.stand((0, 1, 0)) and m.stand((2, 2, 0)) and m.stand((4, 4, 0)) and not m.stand((4, 2, 0))
    box = (0, -1, 0, 7, 10, 0)
    reach, graph = H.walk(m, (0, 1, 0), box)
    # hand: (0,1)->(1,1)->(2,2) step up; (2,2)->(3,4) is a two-block rise, refused; past the ledge nothing
    assert (2, 2, 0) in reach and (3, 4, 0) not in reach and (6, 1, 0) not in reach
    # from the ledge top: walk east, drop 3 to (6,1), never back up
    reach2, graph2 = H.walk(m, (4, 4, 0), box)
    assert (6, 1, 0) in reach2 and (7, 1, 0) in reach2
    back = H.back_reach(graph2, (4, 4, 0))
    assert (6, 1, 0) not in back and (5, 4, 0) in back


# Protects: the hold points and the gate set-backs are read from the emitted lines, not the data; hand: one trainer
# tp line and one gate tp line.
def test_emitted_line_readers_by_hand(tmp_path):
    f = tmp_path / "cobblers_trainers" / "data" / "cobblers" / "function" / "trainers" / "cycle.mcfunction"
    f.parent.mkdir(parents=True)
    f.write_text('execute as @e[type=rctmod:trainer,nbt={TrainerId:"t1",InBattle:0b}] positioned 1 2 3 unless '
                 'entity @s[distance=..0.75] run tp @s 10.5 67 20.5\n')
    assert H.hold_points(tmp_path, ["t1", "t2"]) == {"t1": (10.5, 67.0, 20.5)}
    g = tmp_path / "cobblers_hq_tower" / "data" / "cobblers" / "function" / "hq_tower" / "cycle.mcfunction"
    g.parent.mkdir(parents=True)
    g.write_text("tp @a[x=0,y=0,z=0,dx=1,dy=1,dz=1,tag=!a] 5.5 6 7.5 90 0\n")
    assert H.set_backs(tmp_path) == [("@a[x=0,y=0,z=0,dx=1,dy=1,dz=1,tag=!a]", (5.5, 6.0, 7.5))]


# ====================================================================== the real generators

def source_root():
    try:
        from terrain import env_source_root
        r = env_source_root()
    except Exception:          # noqa: BLE001 -- no heightmap configured is a skip, not a failure
        return None
    return r if r and Path(r).exists() else None


SRC = source_root()
needs_heightmap = pytest.mark.skipif(SRC is None, reason="the canonical heightmap is not available")


@pytest.fixture(scope="module")
def city(tmp_path_factory):
    """The city's pack and the trainers' pack emitted once into tmp; the city's cells handed to tools/hq_tower.py's
    memo so it does not build the city a second time."""
    import deep_city as DC
    import hq_tower as HQ
    import route_trainers as RT
    out = tmp_path_factory.mktemp("hq_city")
    cv, plan, services, spec = DC.build(SRC, None)
    real_out = DC.OUT
    DC.OUT = out / "cobblers_deep_city"
    try:
        DC.emit(cv, services, plan)
    finally:
        DC.OUT = real_out
    HQ._MEMO[SRC] = ({k: v[0] for k, v in cv.v.items()}, plan, spec)
    assert RT.main(["--out", str(out / "cobblers_trainers")]) == 0
    return out, H.tread_of(SRC)


def tower(base, mutate=None):
    """tools/hq_tower.py's pack emitted next to the city's, a generator changed by mutate(HQ) first."""
    import hq_tower as HQ
    import shutil
    out = base.parent / ("hq_%s" % (mutate.__name__ if mutate else "real"))
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(base, out)
    undo = mutate(HQ) if mutate else None
    real_out = HQ.OUT
    HQ.OUT = out / "cobblers_hq_tower"
    try:
        spec = HQ.load()
        cells, _plan, _dc = HQ.city(SRC)
        HQ.emit(spec, HQ.writes(spec, cells))
    finally:
        HQ.OUT = real_out
        if undo:
            undo()
    return out


# Protects: the tower as built -- H1..H7 -- except the spawn-condition finding (H2), a known defect reported to the
# builder: if removed, a sealed stair, a buried seat, an unreachable cache or a trapping gate ships unseen.
@needs_heightmap
def test_the_tower_as_built(city):
    base, tread = city
    probs, notes = H.audit(tower(base), SRC, tread=tread)
    assert [p for p in probs if not p.startswith("H2 ")] == [], probs
    # hand: 7 trainers (data/hq_trainers.json) + Brann, Elara, Oren in the tower = 10 seats; 4 caches; 2 gates
    assert "10 seats, 4 caches, 2 set-backs" in notes[-1], notes


# Protects: H2 is live: the relay hall's lightning rods are a spawn-condition block (data/spawn_blocks.json:
# electrode, magnemite, joltik ... neededNearbyBlocks), KNOWN and reported, not fixed here. If the builder removes
# them this test fails and should be deleted with the finding; if removed while they stand, the finding is lost.
@needs_heightmap
def test_known_finding_lightning_rods(city):
    base, tread = city
    probs, _ = H.audit(tower(base), SRC, tread=tread)
    assert any(p.startswith("H2 ") and "minecraft:lightning_rod" in p for p in probs), probs


def shut_stair(HQ):
    real = HQ.stair_cells

    def sc(spec):
        out = real(spec)
        for c in out.values():
            c["holes"] = []
        return out
    HQ.stair_cells = sc
    return lambda: setattr(HQ, "stair_cells", real)


# Protects: INDEPENDENCE of H3. hq_tower leaving every floor above the stairs shut (data untouched) must fail: the
# walk never leaves the ground storey; if removed, the walk could pass a tower nobody can climb.
@needs_heightmap
def test_mutation_stairs_left_shut(city):
    base, tread = city
    probs, _ = H.audit(tower(base, shut_stair), SRC, tread=tread)
    assert any(p.startswith("H3 ") and "hq_s10" in p for p in probs), probs


def barrel_on_a_seat(HQ):
    real = HQ.furnishing

    def fu(spec):
        f = real(spec)
        f["hq_s2"] = f["hq_s2"] + [(3436 - 3429, 3306 - 3304, 0, HQ.BARREL)]   # hq_tower_trainer_02's seat
        return f
    HQ.furnishing = fu
    return lambda: setattr(HQ, "furnishing", real)


# Protects: INDEPENDENCE of H4. hq_tower furnishing a barrel onto trainer 02's seat (data untouched) must fail;
# if removed, a trainer held inside a block goes unseen.
@needs_heightmap
def test_mutation_barrel_on_a_seat(city):
    base, tread = city
    probs, _ = H.audit(tower(base, barrel_on_a_seat), SRC, tread=tread)
    assert any(p.startswith("H4 ") and "hq_tower_trainer_02" in p for p in probs), probs


def write_outside(HQ):
    real = HQ.writes

    def wr(spec, city_cells=None):
        W = real(spec, city_cells)
        W[(3427, 70, 3308)] = ("minecraft:stone", 1)                      # one west of the tower's wall
        return W
    HQ.writes = wr
    return lambda: setattr(HQ, "writes", real)


# Protects: INDEPENDENCE of H1. hq_tower writing one block west of its wall must fail; if removed, the tower pack
# could overwrite the relic site's hatch or the street.
@needs_heightmap
def test_mutation_write_outside_the_interior(city):
    base, tread = city
    probs, _ = H.audit(tower(base, write_outside), SRC, tread=tread)
    assert any(p.startswith("H1 ") for p in probs), probs


def climb_set_back_inside(HQ):
    real = HQ.gate_lines

    def gl(spec):
        return [l.replace(" 3430.5 74 3305.5 ", " 3430.5 80 3305.5 ") for l in real(spec)]
    HQ.gate_lines = gl
    return lambda: setattr(HQ, "gate_lines", real)


# Protects: INDEPENDENCE of H7. hq_tower setting a climber back onto the foundry floor (inside the climb gate's own
# box) must fail; if removed, a gate that holds a player in place every 10 ticks goes unseen.
@needs_heightmap
def test_mutation_set_back_inside_its_gate(city):
    base, tread = city
    probs, _ = H.audit(tower(base, climb_set_back_inside), SRC, tread=tread)
    assert any(p.startswith("H7 ") and "inside the box" in p for p in probs), probs
