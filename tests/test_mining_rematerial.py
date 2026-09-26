"""The Craters' mining town in stone: data/rematerial.json house_sets mining_deepslate and mining_tuff, and the 14
mining_town houses in data/placements.json that name them.

Written by the test author, not by the session that wrote the sets.

Expectations come from the donor templates (Repurposed Structures' dark_forest houses under
kits/structures/incoming/, gitignored; the tests that need them skip with the reason when they are absent), a
wood-block rule and a block-state table for vanilla 1.21.1 written out here from the game's block states, and
data/spawn_blocks.json. The copy check runs tools/place_town.py rewrite_template into tmp_path.

Not covered: how the houses look, whether the copper doors and trapdoors open by hand in game (they do in vanilla,
not verified on this server), the house furniture (bookshelves, barrels, chests, ladders, lecterns and cartography
tables stay wooden: they are not building material and no set maps them), and town_audit's reading of the placed
houses.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import nbt  # noqa: E402
import place_town as P  # noqa: E402

SETS = json.loads((ROOT / "data" / "rematerial.json").read_text(encoding="utf-8"))["house_sets"]
MINING_SETS = ("mining_deepslate", "mining_tuff")
PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
HOUSES = [p for p in PLACEMENTS if p.get("settlement") == "mining_town" and p.get("kind") == "house"]
SPAWN_BLOCKS = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])

WOODS = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry", "bamboo", "crimson", "warped")
WOOD_SHAPES = ("planks", "log", "wood", "stairs", "slab", "fence", "fence_gate", "door", "trapdoor", "pressure_plate",
               "button", "sign", "wall_sign", "hanging_sign", "wall_hanging_sign")


def is_wood(name):
    """A wooden building block: a species' planks, logs, wood, stairs, slabs, fences, gates, doors, trapdoors, plates,
    buttons and signs, stripped or not."""
    short = name.split(":", 1)[1]
    short = short[len("stripped_"):] if short.startswith("stripped_") else short
    return name.startswith("minecraft:") and any(short == "%s_%s" % (w, s) for w in WOODS for s in WOOD_SHAPES)


B = {"true", "false"}
STAIRS = {"facing", "half", "shape", "waterlogged"}
SLAB = {"type", "waterlogged"}
PANE = {"north", "east", "south", "west", "waterlogged"}
DOOR = {"facing", "half", "hinge", "open", "powered"}
TRAPDOOR = {"facing", "half", "open", "powered", "waterlogged"}
# every property each involved block accepts in vanilla 1.21.1 (from the game's block states, not from the data)
PROPS = {
    "minecraft:dark_oak_log": {"axis"}, "minecraft:stripped_dark_oak_log": {"axis"},
    "minecraft:dark_oak_fence": PANE, "minecraft:dark_oak_door": DOOR, "minecraft:dark_oak_trapdoor": TRAPDOOR,
    "minecraft:dark_oak_pressure_plate": {"powered"}, "minecraft:dark_oak_planks": set(),
    "minecraft:dark_oak_stairs": STAIRS, "minecraft:dark_oak_slab": SLAB,
    "minecraft:polished_basalt": {"axis"}, "minecraft:basalt": {"axis"}, "minecraft:iron_bars": PANE,
    "minecraft:waxed_weathered_copper_door": DOOR, "minecraft:waxed_weathered_copper_trapdoor": TRAPDOOR,
    "minecraft:polished_blackstone_pressure_plate": {"powered"},
    "minecraft:deepslate_bricks": set(), "minecraft:deepslate_brick_stairs": STAIRS, "minecraft:deepslate_brick_slab": SLAB,
    "minecraft:tuff_bricks": set(), "minecraft:tuff_brick_stairs": STAIRS, "minecraft:tuff_brick_slab": SLAB,
}


def _donors_missing():
    return [p["file"] for p in HOUSES if not (ROOT / p["file"]).is_file()]


needs_donors = pytest.mark.skipif(bool(_donors_missing()), reason="Repurposed Structures dark_forest donor templates are "
                                  "not in kits/structures/incoming/townkit (gitignored): %s" % _donors_missing()[:3])


def _parse(state):
    if "[" not in state:
        return state, {}
    name, rest = state.split("[", 1)
    return name, dict(kv.split("=", 1) for kv in rest.rstrip("]").split(",") if "=" in kv)


def _placed_states(path):
    """[(name, props)] of every block the house places: palette blocks, and each jigsaw's final state."""
    _, doc = nbt.load(path)
    out = []
    for b in doc["blocks"]:
        e = doc["palette"][b["state"]]
        if e["Name"] == "minecraft:jigsaw":
            out.append(_parse((b.get("nbt") or {}).get("final_state") or "minecraft:air"))
        else:
            out.append((e["Name"], dict(e.get("Properties") or {})))
    return out


# removing this lets a mining house be built in its donor's dark oak, or name a set that does not exist (place_town
# refuses the whole town at build time)
def test_every_mining_house_names_a_mining_material_set():
    assert len(HOUSES) == 14
    assert all(p["template"].startswith("repurposed_structures:villages/dark_forest/houses/") for p in HOUSES)
    bad = [(p["id"], p.get("materials")) for p in HOUSES if p.get("materials") not in MINING_SETS]
    assert not bad, bad
    assert all(s in SETS for s in MINING_SETS)
    assert {p["materials"] for p in HOUSES} == set(MINING_SETS), "both sets are used, so the street is not one colour"


# removing this lets a wooden block the dark_forest houses carry (a log, a stair, a jigsaw's plank final state) reach
# the Craters unmapped, or be mapped to another wood, when the owner's rule is that the mining town has no wooden houses
@needs_donors
@pytest.mark.parametrize("set_id", MINING_SETS)
def test_set_maps_every_wood_block_of_the_dark_forest_houses_to_non_wood(set_id):
    m = SETS[set_id]["map"]
    wood = {n for p in HOUSES for n, _ in _placed_states(ROOT / p["file"]) if is_wood(n)}
    assert {"minecraft:dark_oak_planks", "minecraft:dark_oak_log", "minecraft:dark_oak_stairs"} <= wood, sorted(wood)
    assert not sorted(wood - set(m)), ("wood the set leaves unmapped", sorted(wood - set(m)))
    assert not [(s, t) for s, t in m.items() if is_wood(t)], "a wood mapped to a wood"


# removing this lets a mapping drop a block's state (a stair's facing, a door's half), so the re-materialed copy holds a
# block state Minecraft rejects or silently defaults: doors split, stairs face north, logs lie down
@pytest.mark.parametrize("set_id", MINING_SETS)
def test_each_mapping_is_like_for_like(set_id):
    for src, dst in SETS[set_id]["map"].items():
        assert src in PROPS and dst in PROPS, ("extend the property table for", src, dst)
        assert PROPS[src] <= PROPS[dst], (src, dst, sorted(PROPS[src] - PROPS[dst]))


# removing this lets a donor's own states outrun the table above (a property the table does not list for the source)
@needs_donors
def test_donor_states_are_within_the_property_table():
    for p in HOUSES:
        m = SETS[p["materials"]]["map"]
        for n, pr in _placed_states(ROOT / p["file"]):
            if n in m:
                assert set(pr) <= PROPS[n], (p["id"], n, sorted(set(pr) - PROPS[n]))


# removing this lets the stone the houses are rebuilt in decide encounters (data/spawn_blocks.json), so the mining town
# changes what spawns round it
@pytest.mark.parametrize("set_id", MINING_SETS)
def test_no_mapping_target_is_a_spawn_block(set_id):
    targets = set(SETS[set_id]["map"].values())
    assert targets and not (targets & SPAWN_BLOCKS), sorted(targets & SPAWN_BLOCKS)


# removing this lets place_town's re-materialed copy keep wood or lose states even when the set is right (the copy is what
# the pack places)
@needs_donors
def test_rematerialed_copy_holds_no_wood_and_keeps_every_state(tmp_path):
    for p in HOUSES:
        m = SETS[p["materials"]]["map"]
        dest = tmp_path / (p["id"] + ".nbt")
        P.rewrite_template(ROOT / p["file"], dest, materials=m)
        _, a = nbt.load(ROOT / p["file"])
        _, b = nbt.load(dest)
        assert len(a["blocks"]) == len(b["blocks"]), p["id"]
        changed = 0
        for ba, bb in zip(a["blocks"], b["blocks"]):
            ea, eb = a["palette"][ba["state"]], b["palette"][bb["state"]]
            assert ba["pos"] == bb["pos"] and (ea.get("Properties") or {}) == (eb.get("Properties") or {}), p["id"]
            assert eb["Name"] == m.get(ea["Name"], ea["Name"]), (p["id"], ea["Name"], eb["Name"])
            assert not is_wood(eb["Name"]), (p["id"], eb["Name"])
            changed += eb["Name"] != ea["Name"]
        assert changed > 0, p["id"]
