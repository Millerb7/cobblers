"""The Pallet crushed house BUILT (tools/crushed_house.py): the structure, its one way in, its restore, its probes and its step.

What is proved, and how. The walk checks do NOT read the generator's plan: they parse the BUILT function text
(`setblock` and `fill` lines, as the server would run them) over a world of heightmap ground, then walk a 0.6 by 1.8
player through it cell by cell. So a plan that disagrees with its own output, or an output whose commands order badly
(a fill laid over a setblock), is seen here and not in the plan. Every tamper case below changes the generator's CODE
(a function replaced) and leaves data/crushed_house.json alone (CLAUDE.md, "How to prove an audit is independent").

The walk model is deliberately generous to the player (a one-block step up with a free head cell, a drop of up to three,
a lantern and air passable) so that "sealed" is not a claim made by a stingy model. It has no diagonals: a player cannot
squeeze through a zero-width corner gap.

NOT covered (needs a running Minecraft): that the fills land, that the clear step leaves the town's own trees alone,
that the pane/stair/fence states connect as drawn, that Lena stands unhurt in the pocket, and what the house looks like.
Needs the canonical heightmap; a skip names it.
"""
import json
import re
import sys
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import crushed_house as C  # noqa: E402
import function_limits  # noqa: E402

DOC = json.loads((ROOT / "data" / "crushed_house.json").read_text(encoding="utf-8"))
SEATS = json.loads((ROOT / "data" / "npc_seats.json").read_text(encoding="utf-8"))
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
REAPPLY = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")

LOT_X, LOT_Z = DOC["site"]["lot"]["x"], DOC["site"]["lot"]["z"]
OPENING = (1516, 5262)
LENA_IN = tuple(SEATS["markers"]["marker_pallet_crushed_house_interior_safe"]["at"])
LENA_OUT = tuple(SEATS["markers"]["marker_pallet_crushed_house_exterior_safe"]["at"])
HANK = tuple(next(s for s in SEATS["seats"] if s["id"] == "npc_pallet_crushed_house_hank")["at"])
NONSOLID = {"minecraft:air", "minecraft:lantern"}


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        g = G.load()
        g(LOT_X[0], LOT_Z[0])
        return g
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


# ------------------------------------------------------------------------------------------------ a world from commands
class World:
    """Heightmap ground (grass at and under g) plus the effect of a function's setblock/fill lines, in order."""

    def __init__(self, g):
        self.g = g
        self.o = {}

    def block(self, x, y, z):
        b = self.o.get((x, y, z))
        if b is not None:
            return b
        return "minecraft:grass_block" if y <= self.g(x, z) else "minecraft:air"

    def solid(self, x, y, z):
        return self.block(x, y, z).split("[")[0] not in NONSOLID

    def run(self, text):
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            t = ln.split()
            if t[0] == "setblock":
                self.o[(int(t[1]), int(t[2]), int(t[3]))] = t[4]
            elif t[0] == "fill":
                if "replace" in t:
                    continue                        # the tag clears: natural plants only; the world here has none
                x0, y0, z0, x1, y1, z1 = map(int, t[1:7])
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    for y in range(min(y0, y1), max(y0, y1) + 1):
                        for z in range(min(z0, z1), max(z0, z1) + 1):
                            self.o[(x, y, z)] = t[7]
        return self


def build_world(g, gen=C):
    doc = gen.load()
    out, pl = gen.files(doc, g)
    key = "data/cobblers/function/crushed_house/%s.mcfunction"
    return World(g).run(out[key % "build"]), out, pl


# ------------------------------------------------------------------------------------------------------- the walk
X0, X1, Z0, Z1 = 1498, 1532, 5238, 5274


def standable(w, x, y, z):
    return w.solid(x, y - 1, z) and not w.solid(x, y, z) and not w.solid(x, y + 1, z)


def moves(w, c, ymin, ymax):
    x, y, z = c
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, nz = x + dx, z + dz
        if not (X0 <= nx <= X1 and Z0 <= nz <= Z1):
            continue
        if not w.solid(nx, y, nz) and not w.solid(nx, y + 1, nz):         # walk or drop (up to 3)
            ny = y
            for _ in range(4):
                if w.solid(nx, ny - 1, nz):
                    if ny >= ymin:
                        yield (nx, ny, nz)
                    break
                ny -= 1
        if (w.solid(nx, y, nz) and not w.solid(x, y + 2, z) and not w.solid(nx, y + 1, nz)
                and not w.solid(nx, y + 2, nz) and y + 1 <= ymax):            # one block up, head room to jump
            yield (nx, y + 1, nz)


def reach(w, start, limit=300000):
    ymin, ymax = w.g(1516, 5258) - 2, w.g(1516, 5258) + 30
    if not standable(w, *start):
        raise AssertionError("the walk's start %s is not standable" % (start,))
    seen, q = {start}, deque([start])
    while q and len(seen) < limit:
        for n in moves(w, q.popleft(), ymin, ymax):
            if n not in seen:
                seen.add(n)
                q.append(n)
    return seen


def far_start(w):
    x, z = 1500, 5240
    return (x, w.g(x, z) + 1, z)


@pytest.fixture(scope="module")
def built(ground):
    return build_world(ground)


@pytest.fixture(scope="module")
def reached(built):
    w = built[0]
    return reach(w, far_start(w))


# ---------------------------------------------------------------------------------------------- one way in, and only it
def test_lena_can_be_walked_to_through_the_opening(built, reached):
    # Without it the event is unfinishable: a house built shut, or a crawl too low for a player.
    assert LENA_IN in reached
    w = built[0]
    start = (OPENING[0], w.g(*OPENING) + 1, OPENING[1] + 2)             # (1516, 5264): the brief's own start
    assert LENA_IN in reach(w, start)
    assert (OPENING[0], LENA_IN[1], OPENING[1]) in reached                # the opening cell itself is walked through


def test_shutting_the_opening_leaves_no_other_way_to_lena(built):
    # Without it the "safe opening" is only one of several, and 'Look for a safe opening rather than breaking the front
    # wall' means nothing: a hole in the roof over her, a window, a gap in the shell.
    w, _, _ = built
    for y in (LENA_IN[1], LENA_IN[1] + 1):
        w.o[(OPENING[0], y, OPENING[1])] = "minecraft:stone"
    try:
        shut = reach(w, far_start(w))
    finally:
        for y in (LENA_IN[1], LENA_IN[1] + 1):
            del w.o[(OPENING[0], y, OPENING[1])]
    assert LENA_IN not in shut
    # nor can any standable cell of the pocket or its crawl be reached any other way
    pocket = {(x, LENA_IN[1], z) for x in (1515, 1516, 1517) for z in (5257, 5258, 5259)}
    crawl = {(1516, LENA_IN[1], z) for z in (5260, 5261, 5262)}
    assert not (shut & (pocket | crawl))


def test_the_front_door_cannot_be_entered(built, reached):
    # Without it the front is open and the event's own text ('rather than breaking the front wall') is a lie.
    w, _, _ = built
    door = DOC["front"]["door"]
    for y in (118, 119):
        assert w.block(door[0], y, door[1]) != "minecraft:air", "the doorway is open at y%d" % y
    # no standable cell at floor level in the doorway or the cell behind it (a player on the ruin's rubble at y120, reached from
    # the open east, is inside the ruin and still has the lintel and the pile between him and the street)
    in_door = {c for c in reached if door[0] <= c[0] <= door[0] + 1 and door[1] - 1 <= c[2] <= door[1] + 1 and 118 <= c[1] <= 119}
    assert not in_door


def test_the_stands_are_clear_standable_and_connected(built, reached):
    # Without it Hank stands in a wall, Lena after the rescue stands in a pile, or either is cut off from the other.
    w, _, _ = built
    for name, (x, y, z) in (("hank", HANK), ("lena_in", LENA_IN), ("lena_out", LENA_OUT)):
        assert not w.solid(x, y, z) and not w.solid(x, y + 1, z), name + " is boxed in"
        assert w.solid(x, y - 1, z), name + " has no floor"
        assert (x, y, z) in reached, name + " is not connected to the town"
    assert not (LOT_X[0] <= HANK[0] <= LOT_X[1]), "Hank must stand outside the lot"
    assert LENA_IN[1] == LENA_OUT[1] == HANK[1] == built[2]["y0"]


def test_lena_has_headroom_and_a_floor_in_the_pocket(built):
    # Without it she stands with her head in the ceiling or on air.
    w, _, _ = built
    x, y, z = LENA_IN
    assert (w.block(x, y, z), w.block(x, y + 1, z)) == ("minecraft:air", "minecraft:air")
    assert w.block(x, y - 1, z) == "minecraft:oak_planks"
    assert w.solid(x, y + 2, z)                                          # the beam: a ceiling, so a stable pocket


def test_the_house_looks_collapsed_not_whole_nor_rubble(built):
    # Without it the 'repairable ruin' is a whole house or a flat mound. West half roofed, east half open to the sky, walls
    # standing on the west, a tree lying across it.
    w, _, pl = built
    y_roof = pl["y0"] + 3
    west = [w.block(LOT_X[0] + lx, y_roof, LOT_Z[0] + lz) for lx in (0, 1, 2) for lz in range(0, 9)]
    east = [w.block(LOT_X[0] + lx, y_roof + dy, LOT_Z[0] + lz) for lx in (6, 7, 8) for lz in range(0, 9) for dy in range(0, 5)]
    assert sum(1 for b in west if "brick_stairs" in b) >= 4                  # eaves standing
    assert not any("brick_stairs" in b and "bottom" in b and "[facing=south,half=bottom]" in b for b in
                   [w.block(LOT_X[0] + lx, pl["y0"] + 5, LOT_Z[0] + 2) for lx in (6, 7, 8)])   # the east slope is down
    wall_logs = [w.block(LOT_X[0] + 6, pl["y0"] + 3, LOT_Z[0] + lz) for lz in range(1, 8)]
    assert sum(1 for b in wall_logs if b == "minecraft:oak_log[axis=z]") >= 6   # the fallen trunk


# ----------------------------------------------------------------------------------- tamper: change the GENERATOR, not the data
def test_a_generator_that_forgets_the_opening_is_caught(ground, monkeypatch):
    # The walk must fail when the crawl's mouth is walled up: proof the first test bites.
    real = C.pocket

    def closed(p):
        real(p)
        for dy in (0, 1):
            p.put(4, dy, 8, "minecraft:cobblestone")
    monkeypatch.setattr(C, "pocket", closed)
    with pytest.raises(SystemExit):                       # the builder's own check refuses a closed opening ...
        C.plan(C.load(), ground)
    monkeypatch.setattr(C, "check_plan", lambda doc, p: [])
    w = build_world(ground)[0]                            # ... and with that check off, the independent walk still catches it
    assert LENA_IN not in reach(w, far_start(w))


def test_a_generator_that_opens_the_front_door_is_caught(ground, monkeypatch):
    # The door test must see a doorway carved open (and the ring cell behind it): proof the second test bites.
    real = C.front

    def open_door(p):
        real(p)
        for lx in (0, 1):
            for dy in (0, 1, 2):
                p.put(lx, dy, 4, "minecraft:air")
    monkeypatch.setattr(C, "front", open_door)
    w = build_world(ground)[0]
    door = DOC["front"]["door"]
    r = reach(w, far_start(w))
    assert any(c[0] in (door[0], door[0] + 1) and c[2] == door[1] and 118 <= c[1] <= 119 for c in r)


def test_a_generator_with_a_hole_in_the_pocket_roof_is_caught(ground, monkeypatch):
    # A hole over Lena's room (the roof is open to the sky on that side) must be seen by the shut-opening walk.
    real = C.pocket

    def holed(p):
        real(p)
        p.put(5, 2, 4, "minecraft:air")
    monkeypatch.setattr(C, "pocket", holed)
    w = build_world(ground)[0]
    for y in (118, 119):
        w.o[(OPENING[0], y, OPENING[1])] = "minecraft:stone"
    assert LENA_IN in reach(w, far_start(w))


def test_a_generator_that_buries_hank_is_caught(ground, monkeypatch):
    # The builder itself refuses a plan that fills a stand; the test sees the refusal.
    real = C.front

    def bury(p):
        real(p)
        p.putg(-3, 0, 4, "minecraft:cobblestone")
        p.putg(-3, 1, 4, "minecraft:cobblestone")
    monkeypatch.setattr(C, "front", bury)
    with pytest.raises(SystemExit) as e:
        C.plan(C.load(), ground)
    assert "hank stand" in str(e.value)


# ------------------------------------------------------------------------------------------------ the blocks it writes
def test_every_written_block_is_declared_and_none_is_a_spawn_condition(built):
    # Without it a block that decides an encounter (data/spawn_blocks.json) lands in Pallet, or one the data does not list does.
    w, out, _ = built
    declared = set(DOC["structure"]["blocks"]["ids"])
    written = {re.split(r"[\[{]", b)[0] for b in w.o.values()}
    assert written <= declared, sorted(written - declared)
    assert not (written & SPAWN), sorted(written & SPAWN)
    assert not (declared & SPAWN), sorted(declared & SPAWN)
    assert not any(("chest" in b or "_bed" in b or "leaves" in b or "carpet" in b) for b in declared)


def test_nothing_is_written_under_the_ground_but_the_floor(built):
    # Without it the house digs a cellar or a foundation into the town's ground by accident.
    w, _, pl = built
    for (x, y, z), b in w.o.items():
        gy = w.g(x, z)
        inside = LOT_X[0] <= x <= LOT_X[1] and LOT_Z[0] <= z <= LOT_Z[1]
        if y <= gy:
            assert inside and y == pl["F"], "%s at (%d, %d, %d) is under the ground (y%d)" % (b, x, y, z, gy)


def test_the_build_stays_inside_its_declared_box(built):
    # Without it a stray fill (a wrong sign) rewrites a neighbouring street. The box is the lot plus the clear margin.
    w, _, pl = built
    x0, z0, x1, z1 = pl["clear"]
    ys = pl["clear_y"]
    for (x, y, z) in w.o:
        assert x0 <= x <= x1 and z0 <= z <= z1 and ys[0] - 1 <= y <= ys[1], (x, y, z)


def test_the_functions_pass_the_server_limits(built):
    # Without it the server drops a command silently (function_limits.py).
    _, out, _ = built
    for name in ("build", "restore"):
        text = out["data/cobblers/function/crushed_house/%s.mcfunction" % name]
        lines = text.splitlines()
        assert function_limits.check_lines(lines, name) == []


# ------------------------------------------------------------------------------------------------------------ the restore
def test_the_restore_leaves_only_the_heightmaps_ground(ground):
    # Without it the undo leaves a floor, a wall or a log in a field, or digs a hole in the ground it was meant to restore.
    w, out, pl = build_world(ground)
    assert any(b.startswith("minecraft:oak") for b in w.o.values())
    w.run(out["data/cobblers/function/crushed_house/restore.mcfunction"])
    x0, z0, x1, z1 = pl["clear"]
    y_top = pl["clear_y"][1]
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            for y in range(ground(x, z) + 1, y_top + 1):
                assert w.block(x, y, z) == "minecraft:air", (x, y, z, w.block(x, y, z))
    for x in range(LOT_X[0], LOT_X[1] + 1):
        for z in range(LOT_Z[0], LOT_Z[1] + 1):
            assert w.block(x, ground(x, z), z) == DOC["structure"]["terrain"]["surface"]


def test_the_restore_refuses_while_a_player_is_in_the_box(built):
    # Without it a held player is buried (the sanctuaries' restore refuses the same way).
    text = built[1]["data/cobblers/function/crushed_house/restore.mcfunction"]
    guard = [ln for ln in text.splitlines() if ln.startswith("execute if entity @a[")]
    assert len(guard) == 1 and guard[0].endswith("run return 0")
    first_write = next(i for i, ln in enumerate(text.splitlines()) if ln.startswith("fill "))
    assert text.splitlines().index(guard[0]) < first_write


def test_the_restore_is_named_in_the_build_so_prepare_finds_it_referenced(built):
    # Without it tools/reapply.py unreferenced() fails the prepare: a function no step runs and nothing names.
    assert "cobblers:crushed_house/restore" in built[1]["data/cobblers/function/crushed_house/build.mcfunction"]


# ------------------------------------------------------------------------------------------------------------- the probes
def test_the_committed_probes_match_the_built_world(built):
    # Without it the presence audit tests a different house than the one built. Compared with the PARSED build, not the plan.
    w, _, _ = built
    probes = json.loads((ROOT / "data" / "world_probes.json").read_text(encoding="utf-8"))["places"][C.PROBE_PLACE]
    assert len(probes) >= 15
    for pr in probes:
        x, y, z, want = pr["block"]
        have = w.block(x, y, z)
        same = have == want or have.split("[")[0] == want
        if pr.get("expect", True):
            assert same, "%s: built %s, probe wants %s" % (pr["what"], have, want)
        else:
            assert not same, "%s: probe says it must NOT be %s" % (pr["what"], want)
    kinds = {pr["what"] for pr in probes}
    assert any("opening" in k for k in kinds) and any("pocket" in k for k in kinds) and any("doorway" in k for k in kinds)


def test_the_probes_would_notice_a_wrong_house(ground, monkeypatch):
    # A probe set that passes every house proves nothing: with the opening walled up the same probes must fail.
    probes = json.loads((ROOT / "data" / "world_probes.json").read_text(encoding="utf-8"))["places"][C.PROBE_PLACE]
    real = C.pocket

    def closed(p):
        real(p)
        for dy in (0, 1):
            p.put(4, dy, 8, "minecraft:cobblestone")
    monkeypatch.setattr(C, "pocket", closed)
    monkeypatch.setattr(C, "check_plan", lambda doc, p: [])
    w = build_world(ground)[0]
    bad = 0
    for pr in probes:
        x, y, z, want = pr["block"]
        have = w.block(x, y, z)
        same = have == want or have.split("[")[0] == want
        bad += (same != pr.get("expect", True))
    assert bad >= 2


def test_the_builder_refuses_drifted_probes(ground, monkeypatch):
    # Without it a changed design ships probes that name the old house.
    doc = C.load()
    pl = C.plan(doc, ground)
    assert C.probe_problems(doc, pl) == []
    monkeypatch.setattr(C, "committed_probes", lambda: C.probes(doc, pl)[:-1])
    assert C.probe_problems(doc, pl)


# ---------------------------------------------------------------------------------------------------------- the apply
def test_the_step_holds_the_chunks_it_writes_and_runs_build(built):
    # Without it the fills land in unloaded chunks and do nothing (the three-times-bitten function_limits rule).
    steps = C.placement_steps()
    assert [s[0] for s in steps] == ["cmd", "wait", "fn", "cmd"]
    assert steps[2][1] == "cobblers:crushed_house/build"
    m = re.match(r"forceload add (-?\d+) (-?\d+) (-?\d+) (-?\d+)$", steps[0][1])
    x0, z0, x1, z1 = map(int, m.groups())
    w = built[0]
    assert all(x0 <= x <= x1 and z0 <= z <= z1 for (x, _, z) in w.o)
    assert steps[3][1] == steps[0][1].replace("add", "remove")


def test_r16ch_runs_after_the_town_and_before_hank_and_lena():
    # Without it Hank and Lena are seated into a field that the house is then built over, or the town re-levels the lot
    # under the house. (R7 hometown and the dressing come first; R17N seats Hank; R18CH seats Lena.)
    order = [m.group(1) for m in re.finditer(r'out\.append\(\("(R[0-9A-Z]+)"', REAPPLY)]
    # steps defined before the table of `out`: the first block is the initial list literal, so read the source positions
    pos = {k: REAPPLY.index('out.append(("%s"' % k) for k in ("R16CH", "R16D", "R17N", "R18CH", "R16E")}
    assert pos["R16D"] < pos["R16CH"] < pos["R16E"] < pos["R17N"] < pos["R18CH"]
    assert order.count("R16CH") == 1
    assert 'import crushed_house' in REAPPLY and 'crushed_house.placement_steps()' in REAPPLY
    assert REAPPLY.index('("R7", "hometown"') < pos["R16CH"]


def test_the_pack_is_installed_and_built_by_prepare():
    # Without it the pack is written and never installed (the fifth 'work done in the repo that never reached the game').
    import reapply
    assert "cobblers_crushed_house" in reapply.SERVER_PACKS
    assert "cobblers_crushed_house" not in reapply.WORLD_LOCAL           # a pure block pack: no tick, nothing to keep running
    assert 'add("crushed_house:build", "crushed_house.py", "build", *src)' in REAPPLY


def test_the_pack_holds_two_functions_and_no_runtime_data(ground, tmp_path):
    # Without it a runtime file sneaks in and the pack can never be stripped from the heap (tools/pack_roles.py: 'build' class).
    out, _ = C.files(C.load(), ground)
    assert sorted(out) == ["data/cobblers/function/crushed_house/build.mcfunction",
                           "data/cobblers/function/crushed_house/restore.mcfunction", "pack.mcmeta"]
    assert json.loads(out["pack.mcmeta"])["pack"]["pack_format"] == 48
