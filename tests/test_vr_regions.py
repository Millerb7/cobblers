"""tools/vr_regions.py and data/vr_regions.json: Victory Road's five regions, and the records that must agree with them.

Written by the test author, not by the session that wrote the tool or the data.

Three tiers here:
  - the tool's pure pieces, offline, on synthetic input: runs() (the fill/setblock writer), smooth_heights() (the
    Raw Tear's floor clamp), room_columns() (a room and its shell ring), densify() (a fork's path), base();
  - the committed data: each region's roster, Habitat Block, find, and spawn-block policy, read straight from
    data/vr_regions.json, data/spawns.json, data/habitat_blocks.json, data/rewards.json, data/spawn_blocks.json and
    data/spawn_block_policy.json;
  - one real build (marked slow): it needs the canonical heightmap and the owner's annotated tracing under
    COBBLERS_SOURCE_ROOT and derived/victory_road/plan.json, and SKIPS, never passes, when any is absent.

Not covered, and it needs a boot or a functional test:
  - that the written functions load and run (command limits, forceloading, /fill counts): write() is not called;
  - that the blocks the palettes name exist in the installed mod set: build() runs with no --server-dir, so every
    block resolves to its first choice and no fallback is exercised;
  - that the world matches the model after a run (tools/vr_regions.py verify / verify --full on a stopped copy);
  - that lava and water stay where the model puts them once the game ticks them, and that a player can in fact
    walk out: the walk-out check is the tool's own voxel model, not Minecraft's movement;
  - that each Habitat Block spawns its roster at 60-65 (EXP-033), and that a find is granted in game.
"""
import hashlib
import json
import math
import os
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import vr_regions as V  # noqa: E402


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


SPEC = _load("vr_regions.json")
SPAWNS = _load("spawns.json")
HABITATS = _load("habitat_blocks.json")
REWARDS = _load("rewards.json")
TRIGGERS = _load("spawn_blocks.json")["blocks"]
POLICY = _load("spawn_block_policy.json")
WORLD = _load("world.json")
RIFT_REGIONS = _load("rift_regions.json")
REGIONS = SPEC["regions"]
IDS = [r["id"] for r in REGIONS]


def _state_free(block):
    return block.split("[", 1)[0]


# ------------------------------------------------------------------ runs()

def _expand(cmds):
    """The (x, y, z, block) cells a list of fill/setblock commands writes."""
    out = []
    for c in cmds:
        t = c.split()
        if t[0] == "setblock":
            out.append((int(t[1]), int(t[2]), int(t[3]), t[4]))
        else:
            assert t[0] == "fill", c
            x0, y0, z0, x1, y1, z1 = map(int, t[1:7])
            assert (x0, z0) == (x1, z1), "a column's fill leaves its column: %s" % c
            assert y1 > y0, "a fill of one cell (setblock is the single-cell form): %s" % c
            out += [(x0, y, z0, t[7]) for y in range(y0, y1 + 1)]
    return out


# Without it a column of identical blocks is written one setblock per cell: tens of thousands more commands, past
# the function limits tools/function_limits.py enforces.
def test_runs_merges_a_consecutive_same_block_run_into_one_fill():
    assert V.runs(4, 9, [(5, "minecraft:stone"), (6, "minecraft:stone"), (7, "minecraft:stone")]) == \
        ["fill 4 5 9 4 7 9 minecraft:stone"]


# Without it a single cell is written as `fill x y z x y z`, which is valid but not what the verify passes expect.
def test_runs_uses_setblock_for_a_single_cell():
    assert V.runs(4, 9, [(5, "minecraft:stone")]) == ["setblock 4 5 9 minecraft:stone"]


# Without it a fill spans a gap (overwriting a cell another pass owns: air, a lake) or writes one block over a
# different one.
@pytest.mark.parametrize("ys,want", [
    ([(5, "a:b"), (7, "a:b")], ["setblock 4 5 9 a:b", "setblock 4 7 9 a:b"]),
    ([(5, "a:b"), (6, "a:c")], ["setblock 4 5 9 a:b", "setblock 4 6 9 a:c"]),
    ([(5, "a:b"), (6, "a:b"), (8, "a:b"), (9, "a:b")], ["fill 4 5 9 4 6 9 a:b", "fill 4 8 9 4 9 9 a:b"]),
    ([(5, "a:b"), (6, "a:b"), (7, "a:c"), (8, "a:b")], ["fill 4 5 9 4 6 9 a:b", "setblock 4 7 9 a:c",
                                                        "setblock 4 8 9 a:b"]),
    ([(5, "a:b[x=1]"), (6, "a:b[x=2]")], ["setblock 4 5 9 a:b[x=1]", "setblock 4 6 9 a:b[x=2]"]),
], ids=["gap", "different_block", "two_runs_across_a_gap", "interrupted", "different_state"])
def test_runs_never_merges_across_a_gap_or_a_different_block(ys, want):
    assert V.runs(4, 9, ys) == want


# Without it the writer can drop, duplicate or re-colour a cell in a column it was never shown in a fixed example.
def test_runs_writes_exactly_the_cells_it_is_given_and_no_run_could_have_been_longer():
    rng = random.Random(7331)
    for _ in range(300):
        ys, y = [], rng.randint(-10, 10)
        for _ in range(rng.randint(1, 40)):
            y += rng.choice((1, 1, 1, 2, 3))
            ys.append((y, rng.choice(("a:x", "a:y", "a:z[s=1]"))))
        cmds = V.runs(3, -2, ys)
        assert sorted(_expand(cmds)) == sorted((3, yy, -2, b) for yy, b in ys)
        ends = [(_expand([c])[0], _expand([c])[-1]) for c in cmds]
        for (_a, last), (first, _b) in zip(ends, ends[1:]):
            assert not (first[1] == last[1] + 1 and first[3] == last[3]), "two runs that should be one: %s" % cmds


# ------------------------------------------------------------------ smooth_heights()

def _violations(h, cols):
    return [(c, h[c], n, h[n]) for c in cols for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1),
                                                       (c[0], c[1] - 1)) if n in h and h[c] > h[n] + 1]


def _room(r):
    seed = SPEC["seed"] + sum(ord(c) for c in r["id"])
    return V.room_columns(r["at"][0], r["at"][1], r["radius"], seed)


# Without it the Raw Tear's broken floor has a two-block step somewhere, which a player cannot walk up: the room
# the spec calls "broken without being unwalkable" is split into places that cannot be left.
def test_smooth_heights_leaves_no_column_more_than_one_above_a_neighbour_on_the_tears_own_range():
    tear = next(r for r in REGIONS if r["form"]["kind"] == "tear")
    cols = _room(tear)
    rng = random.Random(3)
    for _ in range(20):
        h = {c: rng.randint(-1, tear["form"]["terrace"]) for c in cols}
        V.smooth_heights(h, cols)
        assert _violations(h, cols) == []


# Without it the clamp can raise a column, building a wall where the docstring promises only a broken floor.
def test_smooth_heights_only_ever_lowers_a_column():
    tear = next(r for r in REGIONS if r["form"]["kind"] == "tear")
    cols = _room(tear)
    rng = random.Random(11)
    h0 = {c: rng.randint(-8, 8) for c in cols}
    h = V.smooth_heights(dict(h0), cols)
    assert all(h[c] <= h0[c] for c in cols)


# Without it the promise holds only for fields that happen to converge within the fixed number of passes: a floor
# whose one low column sits at the far end of the iteration order keeps a cliff (the docstring says no column is
# ever more than one above a neighbour, for any input).
def test_smooth_heights_leaves_no_column_more_than_one_above_a_neighbour_however_far_the_clamp_must_spread():
    cols = [(x, 0) for x in range(19, 0, -1)]          # visited from the far end back towards the low column
    h = {(x, 0): 100 for x in range(1, 20)}
    h[(0, 0)] = 0
    V.smooth_heights(h, cols)
    assert _violations(h, cols) == [], "left: %s" % [h[(x, 0)] for x in range(20)]


# ------------------------------------------------------------------ room_columns()

def _brute(cx, cz, R, seed, ring):
    f = V.outline(seed, R)
    out = {}
    span = int(R * 2) + ring + 8                        # far wider than any outline can reach
    for x in range(cx - span, cx + span + 1):
        for z in range(cz - span, cz + span + 1):
            loc = f(math.atan2(z - cz, x - cx))
            d = math.hypot(x - cx, z - cz) - loc
            if d <= ring:
                out[(x, z)] = d
    return out


# Without it the room's scan box can be too small for its own outline, clipping the room or its shell on one side,
# or a ring of the wrong width is returned: walls thinner than asked for, or rock carved beyond them.
@pytest.mark.parametrize("ring", [0, 1, 2, 4])
@pytest.mark.parametrize("r", REGIONS[:2], ids=lambda r: r["id"])
def test_room_columns_returns_every_interior_column_and_a_ring_of_the_requested_width(r, ring):
    seed = SPEC["seed"] + sum(ord(c) for c in r["id"])
    cx, cz = r["at"]
    got = V.room_columns(cx, cz, r["radius"], seed, ring=ring)
    want = _brute(cx, cz, r["radius"], seed, ring)
    assert set(got) == set(want)
    assert all(abs(got[c][1] - want[c]) < 1e-9 for c in got)
    assert (cx, cz) in got and got[(cx, cz)][1] <= 0
    assert max(d for _rr, d in got.values()) <= ring
    if ring:
        assert any(0 < d for _rr, d in got.values()), "no ring at all"


# Without it an interior column can sit on the edge of the model with no shell column beside it: the room's side
# would open straight onto unauthored rock or cave.
@pytest.mark.parametrize("r", [r for r in REGIONS if r["form"]["kind"] != "gallery"], ids=lambda r: r["id"])
def test_every_interior_column_of_a_real_room_has_a_ring_column_on_every_side(r):
    cols = _room(r)
    inside = [c for c, (_rr, d) in cols.items() if d <= 0]
    assert inside
    missing = [c for c in inside for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1))
               if n not in cols]
    assert missing == []


# ------------------------------------------------------------------ densify()

# Without it a fork's path jumps two blocks somewhere, leaving a gap in the passage's floor or a step a player cannot
# climb, and the carve leaves a wall between two of its own steps.
def test_densify_steps_at_most_one_block_per_step_in_each_axis_and_keeps_every_waypoint():
    rng = random.Random(42)
    for _ in range(400):
        pts = [(rng.randint(-60, 60), rng.randint(-10, 10), rng.randint(-60, 60)) for _ in range(rng.randint(2, 5))]
        path = V.densify(pts)
        assert path[0] == tuple(pts[0]) and path[-1] == tuple(pts[-1])
        for a, b in zip(path, path[1:]):
            assert all(abs(p - q) <= 1 for p, q in zip(a, b)), (pts, a, b)
        k = 0
        for w in pts:                                   # every waypoint, in order
            k = path.index(tuple(w), k)


# ------------------------------------------------------------------ base()

# Without it the spawn-policy and walk-out checks compare "minecraft:barrel[facing=up]" with "minecraft:barrel" and
# miss a trigger block, or treat a stateful passable block as rock.
@pytest.mark.parametrize("block,want", [
    ("minecraft:barrel[facing=up]", "minecraft:barrel"),
    ("minecraft:cave_vines[age=25,berries=true]", "minecraft:cave_vines"),
    ("minecraft:stone", "minecraft:stone"),
    ("legendarymonuments:distortion_deepslate", "legendarymonuments:distortion_deepslate"),
])
def test_base_strips_block_states_and_nothing_else(block, want):
    assert V.base(block) == want


# ------------------------------------------------------------------ the committed data

# Without it a region's Habitat Block names a pool with no habitat behind it: the block spawns nothing, or
# upstream species at their own bands, at the endgame.
@pytest.mark.parametrize("r", REGIONS, ids=IDS)
def test_every_region_has_a_roster_habitat_at_the_endgame_band(r):
    hab = {h["id"]: h for h in SPAWNS["habitats"]}
    h = hab.get(r["roster"])
    assert h, "%s's roster %s is not a habitat in data/spawns.json" % (r["id"], r["roster"])
    assert h["level_band"] == {"minimum": 60, "maximum": 65}


# Without it the spec and the Habitat Block manifest drift: the block placed in the world names another pool or
# reaches further than the clearance the tool checked (the road, the rig, the other regions).
@pytest.mark.parametrize("r", REGIONS, ids=IDS)
def test_every_region_has_a_habitat_block_with_its_roster_pool_and_range(r):
    by = {b["id"]: b for b in HABITATS["blocks"]}
    b = by.get("vr_%s" % r["id"])
    assert b, "no data/habitat_blocks.json record vr_%s" % r["id"]
    assert b["pool"] == "cobblers:%s" % r["roster"]
    assert b["range_of_influence"] == r["habitat_range"]
    assert b.get("replace_spawns") is True


# Without it a region is built with a barrel and no find behind it, or the Abandoned Cut's dialogue-given find is
# turned into an advancement the dig camp cannot refer to (the owner's decision, data/rewards.json).
@pytest.mark.parametrize("r", REGIONS, ids=IDS)
def test_every_region_has_its_find_as_a_cache_or_for_the_npc_region_an_npc_grant(r):
    by = {x["id"]: x for x in REWARDS["rewards"]}
    x = by.get("vr_%s" % r["id"])
    assert x, "no data/rewards.json record vr_%s" % r["id"]
    if "npc" in r:
        assert x["kind"] == "npc_grant"
        assert x["quest"] == r["npc"]["quest"]
    else:
        assert x["kind"] == "cache"


# Without it exactly one region stops being the npc one, or a second is added, and the reapply NPC step (R9F)
# places the wrong number of NPCs.
def test_exactly_one_region_is_given_through_an_npc():
    assert sum(1 for r in REGIONS if "npc" in r) == 1


# Without it two regions' Habitat Blocks both claim the columns between them, and which roster spawns there
# depends on the game's tie-break, not on the design.
def test_no_two_victory_road_habitat_block_ranges_overlap_horizontally():
    vr = [b for b in HABITATS["blocks"] if b["id"].startswith("vr_")]
    assert len(vr) == len(REGIONS)
    bad = []
    for i, a in enumerate(vr):
        for b in vr[i + 1:]:
            d = math.hypot(a["position"]["x"] - b["position"]["x"], a["position"]["z"] - b["position"]["z"])
            if d < a["range_of_influence"] + b["range_of_influence"]:
                bad.append((a["id"], b["id"], round(d, 1)))
    assert bad == []


def _whitelisted_here():
    out = {}
    for w in POLICY.get("whitelist") or []:
        if "Victory Road regions" in str(w.get("scope", "")):
            for b in w.get("blocks") or []:
                out[b] = str(w.get("why") or "").strip()
    return out


def _palette_blocks(r, fallbacks=False):
    blocks = {_state_free(b) for b in r["palette"].values()}
    if fallbacks:
        blocks |= {_state_free(b) for b in (r.get("fallbacks") or {}).values()}
    return blocks


# Without it a room is built out of a block that summons upstream species at their own bands (a magma floor, a
# lake), unreviewed: the region's roster is no longer what spawns there.
@pytest.mark.parametrize("r", REGIONS, ids=IDS)
def test_every_spawn_conditioning_palette_block_is_whitelisted_for_the_regions_with_a_reason(r):
    ok = _whitelisted_here()
    bad = ["%s (%s)" % (b, TRIGGERS[b][0]) for b in sorted(_palette_blocks(r)) if b in TRIGGERS and not ok.get(b)]
    assert bad == [], "%s: not whitelisted under 'Victory Road regions' with a why: %s" % (r["id"], bad)


# Without it a room built on a server without the modded block (the fallback path the tests never build) uses a
# trigger block nobody reviewed.
@pytest.mark.parametrize("r", [r for r in REGIONS if r.get("fallbacks")], ids=lambda r: r["id"])
def test_every_spawn_conditioning_fallback_block_is_whitelisted_for_the_regions_with_a_reason(r):
    ok = _whitelisted_here()
    fb = _palette_blocks(r, fallbacks=True) - _palette_blocks(r)
    bad = [b for b in sorted(fb) if b in TRIGGERS and not ok.get(b)]
    assert bad == []


# ------------------------------------------------------------------ one real build (slow)

@pytest.fixture(scope="module")
def built():
    """(plan, spec) from one real build, strict, or a skip naming what is absent. Never a pass on absence."""
    import rift_deep as RD
    import terrain as T
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT unset: the regions' cover is checked against the canonical heightmap")
    if not (Path(root) / WORLD["heightmap"]["path"]).is_file():
        pytest.skip("the canonical heightmap %s is not under COBBLERS_SOURCE_ROOT" % WORLD["heightmap"]["path"])
    ann = Path(root) / RIFT_REGIONS["source"]["file"].split(" ")[0]
    if not ann.is_file():
        pytest.skip("the owner's annotated tracing %s is not under COBBLERS_SOURCE_ROOT" % ann.name)
    if hashlib.sha256(ann.read_bytes()).hexdigest() != RIFT_REGIONS["source"]["sha256"]:
        pytest.skip("the annotated tracing on disk is not the one data/rift_regions.json pins")
    if not V.ROAD_PLAN.is_file():
        pytest.skip("no derived/victory_road/plan.json: build the road first (python tools/victory_road.py build)")
    try:
        return V.build(root, None, strict=True)
    except (T.TerrainUnavailable, RD.DeepError) as e:  # an unusable or unpinned heightmap is a skip, recorded here
        pytest.skip("the build's inputs are unusable: %s" % e)


# Without it a region can be built that traps a player (a fall with no way back to the fork), hides floor no one
# can reach, or puts walkable floor against lava with no lip; or its Habitat Block and cache records drift from
# where the model puts them. build(strict=True) raises on each; this also asserts the numbers it reports.
@pytest.mark.slow
def test_a_strict_build_has_no_traps_no_unreached_floor_and_no_lava_without_a_lip(built):
    plan, spec = built
    assert sorted(plan["walk"]) == sorted(IDS)
    for rid, w in plan["walk"].items():
        assert w["reachable"] > 0 and w["floor_cells"] > 0, "%s: an empty walk proves nothing" % rid
        assert (w["traps"], w["unreached_floor"], w["lava_without_lip"]) == (0, 0, 0), (rid, w)
    assert plan["records"] == {rid: "ok" for rid in IDS}
