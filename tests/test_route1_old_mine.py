"""The old mine west of Route 1 (tools/route1_old_mine.py, earthwork route1_old_mine_hill) against the heightmap,
data/rewards.json r1_old_mine and the spawn-block policy.

Written by the test author, not by the session that wrote the tool.

The recorded commands (data/placements.json) are replayed with tools/build_audit.replay. Where they write nothing, the
world is modelled from the canonical heightmap (tools/ground.py, rounded): solid at or below the ground, air above it.
Standable, lit and roofed are this file's own models, not the tool's:

  standable   feet in air, a rail or a closed bottom-half trapdoor (a sleeper, 3/16 high: the feet stand in its cell,
              as tests/test_route1_mansion.py's THIN has it); head in air or a rail; a floor below (any block that is
              not passable, not a sleeper, a lantern, a fence, water or pointed dripstone). The replay drops block
              states, so a trapdoor's half and open state are read from the setblock that left it standing
  walk        a side step onto a standable cell up to one block up (with room to jump) or down up to three
  light       every lantern is 15; light falls by one a step through anything but a full block (trapdoors pass it),
              and stairs, slabs and barrels count as full (so the model under-lights, never over-lights)
  roofed      a full block somewhere above the cell

What is asserted: the tool is one the ground rule analyses and it reads no world; the recorded commands are the ones
the tool builds now from the heightmap; the earthwork places nothing from data/spawn_blocks.json (and, the policy's
own rule, nothing it places is whitelisted only for another place); the record's
cell is its centre's cell (data/world.json grid), and so is the mansion's; the find's barrel is where rewards.json says;
from the notch outside the portal a walk reaches a standable cell next to the barrel, and the reward's trigger box holds
one of those; every walked, roofed cell is at block light 1 or more; the air inside (flooded from the find, not
crossing the portal) never reaches open sky; the ground surface is never left lowered except in the notch, and every
skin block is at or above the heightmap ground; the adit's centre line and the incline's steps have two blocks of
headroom.

The heightmap is outside the repository (COBBLERS_SOURCE_ROOT); without it the ground-dependent tests SKIP, and a skip
is not a pass.

Not covered, and it needs a running server: that the hill stands as replayed (tools/town_audit.py on a staging export);
that the advancement trigger fires in that box and gives the cache once; the light the game computes (stairs pass some);
what spawns in the cave; that the painted trees outside the cleared margin do not poke into the slopes.
"""
import json
import math
import os
import re
import sys
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_audit as BA  # noqa: E402

PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
REC = next(p for p in PLACEMENTS["placements"] if p["id"] == "route1_old_mine_hill")
MANSION = next(p for p in PLACEMENTS["placements"] if p["id"] == "route1_mansion_house")
REWARD = next(r for r in json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))["rewards"]
              if r["id"] == "r1_old_mine")
WORLD = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
TRIGGERS = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
POLICY = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))

# the brief's design (the coordinator, 2026-09-24): the portal's outer face and the adit's centre line, the level's
# last cell, the incline's eight steps on z 4119-4120
PORTAL_X, Z_AXIS, ADIT_END, DROP = 1347, 4120, 1334, 8

AIR = {"minecraft:air", "minecraft:cave_air"}
PASSABLE = AIR | {"minecraft:rail"}
# a closed, bottom-half trapdoor (the old track's sleepers) is 3/16 of a block: the player's feet stand in its cell,
# as tests/test_route1_mansion.py's THIN counts it. world() names it THIN_TRAPDOOR; any other trapdoor keeps its name
THIN_TRAPDOOR = "(closed bottom trapdoor)"
TRAPDOORS = {"minecraft:spruce_trapdoor", "minecraft:oak_trapdoor", "minecraft:dark_oak_trapdoor"}
NOT_FLOOR = PASSABLE | {THIN_TRAPDOOR, "minecraft:lantern", "minecraft:spruce_fence", "minecraft:water",
                        "minecraft:pointed_dripstone"}
TRANSPARENT = PASSABLE | TRAPDOORS | {THIN_TRAPDOOR, "minecraft:lantern", "minecraft:spruce_fence", "minecraft:water",
                                      "minecraft:pointed_dripstone", "minecraft:spruce_leaves"}
SKIN = {"minecraft:grass_block", "minecraft:coarse_dirt", "minecraft:gravel", "minecraft:podzol"}
GROUND = "(ground)"


def _cmd_blocks(cmds):
    for c in cmds:
        t = c.split()
        if t and t[0] == "fill":
            yield t[7].split("[")[0]
        elif t and t[0] == "setblock":
            yield t[4].split("[")[0]


def _columns(cmds):
    xs, zs = [], []
    for c in cmds:
        t = c.split()
        if t and t[0] == "fill":
            xs += [int(t[1]), int(t[4])]
            zs += [int(t[3]), int(t[6])]
        elif t and t[0] == "setblock":
            xs.append(int(t[1]))
            zs.append(int(t[3]))
    return min(xs), min(zs), max(xs), max(zs)


def _cell(x, z):
    gr = WORLD["grid"]
    return gr["row_labels"][(z - gr["origin_z"]) // gr["cell_size"]] + gr["column_labels"][(x - gr["origin_x"]) // gr["cell_size"]]


# ------------------------------------------------------------------------------------------------ data only

# Without it the tool could decide where the hill goes from a world's surface (its own last build) and climb on itself.
def test_the_ground_rule_analyses_the_mine_tool_and_it_reads_no_world():
    import ground_rule as GR
    tools = ROOT / "tools"
    src = {p.stem: p.read_text(encoding="utf-8") for p in tools.glob("*.py") if p.stem != "ground_rule"}
    assert "route1_old_mine" in src
    res = GR.analyse(sources=src)
    assert not res.get("route1_old_mine", {}).get("reads"), res.get("route1_old_mine")
    assert not [p for p in GR.problems(res) if "route1_old_mine" in p]
    # and the analyser does look at it: the same tool with a world read added is caught
    src["route1_old_mine"] += ("\n\ndef _ground_from_world(w, box):\n    import world_heights\n"
                               "    return world_heights.extract(w, box)\n")
    bad = GR.problems(GR.analyse(sources=src))
    assert [p for p in bad if "route1_old_mine" in p], bad


# Without it the mine's walls draw rolycoly, carkol, aron or aggron to Route 1's doorstep (coal and iron ore decide
# spawns), which is a balance decision and not dressing.
def test_the_mine_places_no_coal_or_iron_ore():
    blocks = set(_cmd_blocks(REC["commands"]))
    assert blocks, "the earthwork writes nothing"
    assert not {b for b in blocks if b.endswith(("coal_ore", "iron_ore"))}


# Without it the mine places a block that decides spawns (a rail draws rolycoly, carkol and coalossal; water draws the
# water pool) under a whitelist entry written for another place, and the policy's scope is ignored. The policy's
# entries are scoped in words ("scope"); one scoped to this place must name it.
def test_every_spawn_deciding_block_the_mine_places_is_whitelisted_for_the_mine():
    used = sorted(set(_cmd_blocks(REC["commands"])) & TRIGGERS)
    here = {b for w in POLICY["whitelist"] for b in w["blocks"]
            if re.search(r"old[_ ]mine", "%s %s" % (w.get("scope", ""), w.get("why", "")), re.I)}
    unscoped = [b for b in used if b not in here]
    assert not unscoped, ("the old mine places %s, each a spawn condition (data/spawn_blocks.json), and no whitelist "
                          "entry is scoped to it" % unscoped)


# Without it the mine places a block that decides spawns at all (the tool's stated rule, 2026-09-24: no ore, no rail,
# no water): a Route 1 cave drawing rolycoly, carkol or a water pool is a balance decision, not dressing.
def test_the_mine_places_nothing_that_decides_spawns():
    used = sorted(set(_cmd_blocks(REC["commands"])) & TRIGGERS)
    assert not used, "the old mine places %s, each a spawn condition (data/spawn_blocks.json)" % used


# Without it the placement is filed under the wrong cell (the mansion was once F2 while standing in E2).
@pytest.mark.parametrize("rec,sid", [(REC, "route1_old_mine"), (MANSION, "route1_mansion")], ids=["old_mine", "mansion"])
def test_the_earthwork_record_is_in_its_centres_cell(rec, sid):
    cx, cz = PLACEMENTS["settlements"][sid]["centre"]
    assert rec["cell"] == _cell(cx, cz) == "E2"


@pytest.fixture(scope="module")
def rep():
    x0, z0, x1, z1 = _columns(REC["commands"])
    cols = {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    return BA.replay(REC["commands"], cols)


# Without it the cache's advancement fires at a spot where no barrel stands, or the barrel is built somewhere the
# reward does not know about.
def test_the_finds_barrel_is_where_the_reward_says(rep):
    x, y, z = REWARD["container"]["at"]
    assert REWARD["container"]["block"] == "minecraft:barrel"
    assert rep[(x, z)].get(y) == "minecraft:barrel"
    t = REWARD["trigger"]
    assert all(t["min"][i] <= (x, y, z)[i] <= t["max"][i] for i in range(3))


# ------------------------------------------------------------------------------------------------ with the heightmap

@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    if not os.environ.get("COBBLERS_SOURCE_ROOT"):
        pytest.skip("COBBLERS_SOURCE_ROOT unset: the ground under the mine comes from the canonical heightmap")
    try:
        return G.Ground()
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


# Without it data/placements.json holds a mine the tool no longer builds (hand-edited, or the tool changed and was not
# re-run), and every check in this file is about a mine nobody will place.
def test_the_recorded_mine_is_the_one_the_tool_builds(ground):
    import route1_old_mine as OM
    assert REC["commands"] == OM.build(ground)


def _trapdoor_states(cmds):
    """{(x, y, z): full block string} for each trapdoor a setblock leaves standing (a later fill over it forgets it; the
    replay drops block states, and a trapdoor's half and open state decide whether it is walked over)."""
    states = {}
    for c in cmds:
        t = c.split()
        if t and t[0] == "setblock":
            p = (int(t[1]), int(t[2]), int(t[3]))
            if t[4].split("[")[0] in TRAPDOORS:
                states[p] = t[4]
            else:
                states.pop(p, None)
        elif t and t[0] == "fill" and states:
            lo = [min(int(t[i]), int(t[i + 3])) for i in (1, 2, 3)]
            hi = [max(int(t[i]), int(t[i + 3])) for i in (1, 2, 3)]
            for p in [p for p in states if all(lo[i] <= p[i] <= hi[i] for i in range(3))]:
                del states[p]
    return states


def _thin_trapdoor(state):
    return "half=bottom" in state and "open=false" in state


@pytest.fixture(scope="module")
def world(rep, ground):
    traps = _trapdoor_states(REC["commands"])

    def at(x, y, z):
        col = rep.get((x, z))
        if col is not None and y in col:
            b = col[y]
            if b in TRAPDOORS and _thin_trapdoor(traps.get((x, y, z), "")):
                return THIN_TRAPDOOR
            return b
        return GROUND if y <= ground(x, z) else "minecraft:air"
    return at


def _passable(b):
    return b in PASSABLE


def _feet_ok(b):
    return b in PASSABLE or b == THIN_TRAPDOOR


def _floor(b):
    return b not in NOT_FLOOR


def _standable(world, c):
    """Feet in air, a rail or a sleeper; head in air or a rail; a floor block below the feet cell."""
    x, y, z = c
    return _feet_ok(world(x, y, z)) and _passable(world(x, y + 1, z)) and _floor(world(x, y - 1, z))


@pytest.fixture(scope="module")
def feet(ground):
    return ground(PORTAL_X + 1, Z_AXIS) + 1


@pytest.fixture(scope="module")
def walk(world, feet, rep):
    """Every standable cell reachable from the notch floor outside the portal, over the replayed columns."""
    start = (PORTAL_X + 2, feet, Z_AXIS)
    assert _standable(world, start), "the notch floor outside the portal is not standable at %s" % (start,)
    seen, todo = {start}, deque([start])
    while todo:
        x, y, z = todo.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, z + dz) not in rep:
                continue
            for dy in (1, 0, -1, -2, -3):
                n = (x + dx, y + dy, z + dz)
                if n in seen or not _standable(world, n):
                    continue
                if dy == 1 and not _passable(world(x, y + 2, z)):
                    continue                                     # no room to jump
                seen.add(n)
                todo.append(n)
    return seen


def _beside_barrel():
    x, y, z = REWARD["container"]["at"]
    return [(x + a, y + e, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1) for e in (-1, 0, 1) if (a, b) != (0, 0)]


# Without it the find is sealed off (a cave-in, a step too high, no headroom on the incline): the mine is walked to
# and nothing at its end can be reached.
def test_a_walk_from_the_notch_reaches_the_barrel(walk):
    assert len(walk) > 50
    assert [c for c in _beside_barrel() if c in walk], "no walked cell stands next to the barrel"


# Without it the reward's trigger box sits in rock or air beside the barrel and the advancement never fires for a
# player who walks up to it.
def test_the_trigger_box_holds_a_walked_cell_next_to_the_barrel(walk):
    t = REWARD["trigger"]
    inside = [c for c in _beside_barrel() if c in walk and all(t["min"][i] <= c[i] <= t["max"][i] for i in range(3))]
    assert inside, "no walked cell next to the barrel is inside the trigger box %s-%s" % (t["min"], t["max"])


@pytest.fixture(scope="module")
def light(world, rep):
    lanterns = [(x, y, z) for (x, z), col in rep.items() for y, b in col.items() if b == "minecraft:lantern"]
    assert len(lanterns) >= 10, "the mine has almost no lanterns: nothing to light it with"
    lvl = {}
    for src in lanterns:
        todo = deque([(src, 15)])
        best = {src: 15}
        while todo:
            (x, y, z), l = todo.popleft()
            if l <= 1:
                continue
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                n = (x + d[0], y + d[1], z + d[2])
                if world(*n) not in TRANSPARENT or best.get(n, 0) >= l - 1:
                    continue
                best[n] = l - 1
                todo.append((n, l - 1))
        for c, l in best.items():
            lvl[c] = max(lvl.get(c, 0), l)
    return lvl


def _roofed(world, c, span=40):
    x, y, z = c
    return any(world(x, y + k, z) not in TRANSPARENT for k in range(2, span))


# Without it a stretch of the adit, the incline or the cave is pitch dark (the tool says nothing walkable inside is at
# block light 0), and a player walks into black.
def test_every_walked_roofed_cell_is_lit(world, walk, light):
    roofed = [c for c in walk if _roofed(world, c)]
    assert len(roofed) > 50, "almost nothing walked is under a roof: the check would pass on nothing"
    dark = sorted(c for c in roofed if light.get(c, 0) < 1)
    assert not dark, "%d roofed walked cells at block light 0, e.g. %s" % (len(dark), dark[:5])


# Without it the chamber or the level breaks through the hill or the ground to the sky: a hole in the slope a player
# falls into, and daylight in a cave that is meant to be dark.
def test_the_air_inside_never_reaches_open_sky(world, rep):
    x, y, z = REWARD["container"]["at"]
    start = next(c for c in _beside_barrel() if _passable(world(*c)))
    top = max(y for col in rep.values() for y in col) + 1
    seen, todo, open_sky = {start}, deque([start]), []
    while todo:
        c = todo.popleft()
        if not any(world(c[0], k, c[2]) not in TRANSPARENT for k in range(c[1] + 1, top + 1)):
            open_sky.append(c)
            continue
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (c[0] + d[0], c[1] + d[1], c[2] + d[2])
            if n in seen or n[0] >= PORTAL_X or (n[0], n[2]) not in rep:
                continue
            if world(*n) in TRANSPARENT and world(*n) != "minecraft:spruce_leaves":
                seen.add(n)
                todo.append(n)
    assert len(seen) > 200, "the flood inside is tiny: the find is walled in, or the check started in the wrong place"
    assert not open_sky, "the inside reaches the sky at %s" % sorted(open_sky)[:5]


# Without it the hill is laid below the ground it stands on (buried grass under a raised skin, or a pit where the
# slope should be), or its skin floats under the heightmap's surface.
def test_the_surface_is_never_lowered_and_the_skin_is_on_or_above_the_ground(world, rep, ground):
    lowered, sunk, skins = [], [], 0
    for (x, z), col in rep.items():
        if x >= PORTAL_X and Z_AXIS - 2 <= z <= Z_AXIS + 2:
            continue                                             # the notch: cut to the adit's floor by design
        g = ground(x, z)
        top = max(list(col) + [g]) + 1
        # the surface: the highest block in the model over this column that is not see-through (leaves excepted)
        surf = next((y for y in range(top, g - 41, -1) if world(x, y, z) not in TRANSPARENT), None)
        if surf is None or surf < g:
            lowered.append((x, z, surf, g))
        solid = [y for y, b in col.items() if b not in TRANSPARENT]
        if solid and col[max(solid)] in SKIN:
            skins += 1
            if max(solid) < g:
                sunk.append((x, max(solid), z, g))
    assert skins > 500, "almost no skin written: the hill is missing"
    assert not lowered, "surface below the heightmap ground at %s" % lowered[:5]
    assert not sunk, "skin under the heightmap ground at %s" % sunk[:5]


# Without it a player bumps their head in the level or on the stairs (a cap, a lantern or a step too low), or the
# level's centre line is blocked by a timber set. On the level's centre line the walked surface is the gravel bed or a
# sleeper's top (3/16 up the feet cell): the feet cell must be air or a sleeper and the cell above it air, which leaves
# at least 1.81 blocks over the sleeper for a 1.8-block player. On the incline each step is a stair block with two
# cells of air above it.
def test_the_adit_and_the_incline_have_two_blocks_of_headroom(world, feet):
    bad, sleepers = [], 0
    for x in range(ADIT_END, PORTAL_X + 1):
        c = (x, feet, Z_AXIS)
        sleepers += world(*c) == THIN_TRAPDOOR
        if not _standable(world, c):
            bad.append(("adit", c, world(x, feet - 1, Z_AXIS), world(*c), world(x, feet + 1, Z_AXIS)))
    for i in range(1, DROP + 1):
        x, y = ADIT_END - i, feet - i
        for z in (Z_AXIS - 1, Z_AXIS, Z_AXIS + 1):
            step = world(x, y, z)
            if not step.endswith("_stairs") or not (_passable(world(x, y + 1, z)) and _passable(world(x, y + 2, z))):
                bad.append(("incline", (x, y, z), step, world(x, y + 1, z), world(x, y + 2, z)))
    assert not bad, bad[:5]
    assert sleepers >= 3, "no sleepers on the level's centre line: the thin-block rule was never exercised"
