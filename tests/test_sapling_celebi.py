"""The sleeping Celebi in Route 1's sapling (data/sapling_celebi.json, tools/sapling_celebi.py, tools/reapply.py R14C).

Written by the test author, not by the session that wrote the tool.

What is asserted: the Celebi's block and the one above it are open in the sapling prefab as tools/maze_forest.py
places it, above the heightmap ground there, and the block below is the prefab's oak log (the branch), with the
prefab's origin computed here from maze_forest.SAPLING, the prefab's own trunk_origin and trunk, and the rounded
heightmap ground (tools/ground.py); the shell's barriers cover every cell of the 3 x 4 x 3 box round the branch except
the Celebi's own two cells (the fills are replayed here and compared with a box computed from the position); the
dress sets every flag EXP-023 proved (Unbattleable, NoAI, NoGravity, PoseType SLEEP with RecalculatePose 0b,
HideLabel, PersistenceRequired) and puts it back on its spot; the spawn is an RCON "cmd" step at the data's position,
species and level, and no generated function carries Cobblemon's spawn command (it does nothing from a function); the
keeper never summons; the load tag names cobblers:celebi/load and every function the pack calls exists; the server
would accept every function (tools/function_limits); reapply's R14C carries those actions and the ("check", "celebi"),
runs after R6 (the forest pass that builds the sapling), and cobblers_celebi is a world-local server pack.

The heightmap is outside the repository (COBBLERS_SOURCE_ROOT); without it the prefab test SKIPs, and so does the
R14C step test when build/datapacks lacks the indexes reapply.steps() reads. A skip is not a pass.

Not covered, and it needs a running server: that spawnpokemonat over RCON spawns it (EXP-023), that dress_new finds
it one second later, that it sleeps and cannot be hurt through the barriers, that the keeper holds it across a
restart, and that nothing else in the sapling (leaves placed by R6's foliage) blocks the view of it.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402
import nbt  # noqa: E402
import sapling_celebi as SC  # noqa: E402

D = SC.load()
FILES = SC.files(D)
PREFAB = ROOT / "kits" / "structures" / "prefabs" / "trees" / "tree_town" / "sapling_oak_a"
SIDE = json.loads(PREFAB.with_suffix(".json").read_text(encoding="utf-8"))
CELL = tuple(int(v // 1) for v in D["position"])
# EXP-023's proven flags, as SNBT: the result the experiment recorded, not the tool's list
PROVEN = {"Unbattleable": "1b", "NoAI": "1b", "NoGravity": "1b", "PoseType": '"SLEEP"', "RecalculatePose": "0b",
          "HideLabel": "1b", "PersistenceRequired": "1b"}


def fn(name):
    return FILES["data/cobblers/function/%s.mcfunction" % name].splitlines()


def functions():
    return {k: v for k, v in FILES.items() if k.endswith(".mcfunction")}


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    if not os.environ.get("COBBLERS_SOURCE_ROOT"):
        pytest.skip("COBBLERS_SOURCE_ROOT unset: the sapling's seat comes from the canonical heightmap")
    try:
        return G.Ground()
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture(scope="module")
def placed(ground):
    """{world (x, y, z): block name} of the sapling prefab, placed the way tools/maze_forest.py places it."""
    import maze_forest
    sx, sz = maze_forest.SAPLING
    ox, oy, oz = SIDE["trunk_origin"]
    c = SIDE["habitat"]["trunk"][0] // 2
    x0, z0 = sx - c - ox, sz - c - oz
    y0 = ground(sx, sz) + 1 - oy
    _, doc = nbt.load(PREFAB.with_suffix(".nbt"))
    pal = doc["palette"]
    out = {(x0 + b["pos"][0], y0 + b["pos"][1], z0 + b["pos"][2]): pal[b["state"]]["Name"] for b in doc["blocks"]}
    assert len(out) > 1000, "the prefab is nearly empty: nothing to seat a Celebi on"
    return out


# Without it the Celebi is summoned inside the trunk or leaves (suffocating, or invisible) or on nothing (NoGravity
# holds it in mid-air, visibly off the branch): the sapling was re-seeded or re-seated and the data kept the old spot.
def test_the_celebi_sits_on_the_branch_log_with_its_two_cells_open(placed, ground):
    x, y, z = CELL
    assert placed.get((x, y - 1, z)) == "minecraft:oak_log", placed.get((x, y - 1, z))
    for dy in (0, 1):
        # absent from the prefab: the template leaves the world's block, which is air this far above the ground
        assert (x, y + dy, z) not in placed, placed.get((x, y + dy, z))
        assert y + dy > ground(x, z), "the Celebi's cell is in the terrain"
    assert D["position"][1] == float(y) and D["position"][0] % 1 == 0.5 and D["position"][2] % 1 == 0.5, \
        "the Celebi should stand centred on its block, feet on the log"


def _fills(lines):
    out = []
    for l in lines:
        t = l.split()
        if t and t[0] == "fill":
            a = [int(v) for v in t[1:7]]
            out.append(((min(a[0], a[3]), min(a[1], a[4]), min(a[2], a[5])),
                        (max(a[0], a[3]), max(a[1], a[4]), max(a[2], a[5])), t[7], t[8:]))
    return out


def _cells(lo, hi):
    return {(x, y, z) for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1) for z in range(lo[2], hi[2] + 1)}


# Without it the shell leaves a gap a sword or an arrow gets through (Cobblemon ignores Invulnerable: a sword killed it
# in three hits, EXP-023), or it closes the Celebi's own column and the summon lands inside a barrier.
def test_the_shell_walls_the_whole_box_except_the_celebis_column():
    x, y, z = CELL
    want = _cells((x - 1, y - 1, z - 1), (x + 1, y + 2, z + 1)) - {(x, y, z), (x, y + 1, z)}
    assert len(want) == 3 * 4 * 3 - 2
    barrier = set()
    for lo, hi, block, rest in _fills(fn("celebi/shell")):
        if block == "minecraft:barrier":
            assert rest == ["replace", "minecraft:air"], "the shell must only replace air (the branch log is in it)"
            barrier |= _cells(lo, hi)
        elif block == "minecraft:air":
            assert rest == ["replace", "minecraft:barrier"], "the re-opening must only clear barriers"
            barrier -= _cells(lo, hi)
    assert barrier == want, (sorted(barrier ^ want))


# Without it one of the flags EXP-023 proved is dropped, and the Celebi can be battled, wanders, falls, wakes or
# despawns.
def test_the_dress_sets_every_flag_exp_023_proved_and_puts_it_on_its_spot():
    dress = fn("celebi/dress")
    merge = [l for l in dress if l.startswith("data merge entity @s {")]
    assert len(merge) == 1
    got = dict(kv.split(":", 1) for kv in merge[0][len("data merge entity @s {"):-1].split(","))
    missing = {k: v for k, v in PROVEN.items() if got.get(k) != v}
    assert not missing, missing
    assert "tag @s add %s" % SC.TAG in dress
    at = "%s %s %s" % tuple(D["position"])
    assert any(l.startswith("tp @s %s %s" % (at, D["yaw"])) for l in dress)


# Without it the spawn moves into a function, where Cobblemon's spawn command does nothing (staging, 2026-09-25), and
# every re-export leaves the branch empty with no error.
def test_the_spawn_is_an_rcon_command_at_the_data_and_never_in_a_function():
    cmds = [v for k, v in SC.placement_steps(D) if k == "cmd" and "spawnpokemonat" in v]
    assert len(cmds) == 1
    at = "%s %s %s" % tuple(D["position"])
    assert re.search(r"run spawnpokemonat %s %s level=%d\b" % (re.escape(at), D["species"], D["level"]), cmds[0]), cmds[0]
    # a second run must not stack a second Celebi: guarded by the tag and by any Pokemon on the spot
    assert "unless entity @e[tag=%s]" % SC.TAG in cmds[0]
    bad = [k for k, v in functions().items() if "spawnpokemon" in v]
    assert not bad, bad


# Without it the keeper, which runs every two seconds near a player, could put a second Celebi on the branch.
def test_the_keeper_never_summons():
    for name in ("celebi/keeper", "celebi/keep"):
        text = "\n".join(fn(name))
        assert text.strip(), name
        assert "summon" not in text and "spawnpokemon" not in text, name


# Without it the keeper never starts (the load tag names another function) or a call lands on a function the pack
# does not hold, and the server logs an unknown function once per reload.
def test_the_load_tag_starts_the_keeper_and_every_called_function_exists():
    assert json.loads(FILES["data/minecraft/tags/function/load.json"])["values"] == ["cobblers:celebi/load"]
    have = {k[len("data/cobblers/function/"):-len(".mcfunction")] for k in functions()}
    called = set()
    for text in functions().values():
        called |= set(re.findall(r"function cobblers:([a-z0-9_/]+)", text))
    called |= {v.split(":", 1)[1] for k, v in SC.placement_steps(D) if k == "fn"}
    assert called and called <= have, sorted(called - have)
    assert "celebi/keeper" in "\n".join(fn("celebi/load"))


# Without it the server refuses or silently drops a line of the pack (an unloaded fill, an over-long command).
@pytest.mark.parametrize("name", sorted(functions()))
def test_the_server_would_accept_every_celebi_function(name):
    lines = FILES[name].splitlines()
    assert function_limits.check_lines(lines, name) == []


# ------------------------------------------------------------------------------------------------ reapply

import reapply  # noqa: E402

NEEDS_INDEX = (("cobblers_rift", "rift"), ("cobblers_rift_biome", "rift"), ("cobblers_league_tunnel", "league_tunnel"),
               ("cobblers_deep", "deep"), ("cobblers_vr_caves", "vr_caves"), ("cobblers_route_events", "route_events"))


@pytest.fixture(scope="module")
def steps():
    if not reapply.PACKS.is_dir():
        pytest.skip("no build/datapacks: the generated packs are not built in this checkout")
    missing = [p for p, f in NEEDS_INDEX
               if not (reapply.PACKS / p / "data" / "cobblers" / "function" / f / "index.txt").is_file()]
    if missing:
        pytest.skip("steps() reads index.txt of packs not built here: %s (python tools/reapply.py prepare)" % missing)
    return reapply.steps()


# Without it the re-application forgets the Celebi (an export erased it), or runs it before the forest pass has built
# the branch it sits on and the shell walls an empty clearing.
def test_r14c_summons_walls_dresses_and_checks_the_celebi_after_the_sapling_is_built(steps):
    ids = [s[0] for s in steps]
    assert "R14C" in ids and "R6" in ids
    assert ids.index("R6") < ids.index("R14C")
    acts = steps[ids.index("R14C")][2]
    x, _y, z = CELL
    assert ("cmd", "forceload add %d %d" % (x, z)) in acts
    assert ("fn", "cobblers:celebi/shell") in acts and ("fn", "cobblers:celebi/dress_new") in acts
    assert [v for k, v in acts if k == "cmd" and "spawnpokemonat" in v]
    assert ("check", "celebi") in acts
    assert acts[-1] == ("check", "celebi")
    # the chunk is released after the dress, never before
    i_rel = acts.index(("cmd", "forceload remove %d %d" % (x, z)))
    assert acts.index(("fn", "cobblers:celebi/dress_new")) < i_rel


# Without it the pack is not installed (the dress and keeper functions do not exist when R14C calls them), or it is
# installed server-wide instead of into the world, where the other world-local packs live.
def test_the_celebi_pack_is_a_world_local_server_pack():
    assert "cobblers_celebi" in reapply.SERVER_PACKS
    assert "cobblers_celebi" in reapply.WORLD_LOCAL
