"""The Scar's ruined houses: data/ruins.json, its 33 placements in data/placements.json, tools/ruins.py ruin_template and
the ruin branch of tools/place_town.py build.

Written by the test author, not by the session that wrote tools/ruins.py or data/ruins.json.

Expectations come from sources other than the ruined copy: the donor template itself (read with tools/nbt.py, the
reader tools/place_town.py uses, not the level_dat writer tools/ruins.py uses), the rules as data/ruins.json states
them, vanilla's block tags written out here, data/spawn_blocks.json, and place_town's own seating of the unruined
template. The copies and the pack are written into tmp_path only. The ground is a synthetic hillside (never a world).

The donor templates are Repurposed Structures houses under kits/structures/incoming/ (gitignored, not
redistributable); every test that needs one is skipped, with the reason, when the local copy is absent. The
record/placement agreement needs no donor and always runs.

The wall height the decay bound uses follows tools/ruins.py's docstring (the columns standing at the two layers over
the floor; the highest layer where 60% of them are still standing), recomputed here from the donor template. That
is not the "footprint perimeter ring" data/ruins.json wall_height describes; the two differ on most designs.

Not covered: how a ruin looks or reads in game, whether /place template of the copy lands where the report says,
town_audit's reading of the copy, snow and moss surviving a server tick, the towers, walls and plinth earthworks,
and the avenue end (not built).
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import nbt  # noqa: E402
import place_town as P  # noqa: E402
import ruins as R  # noqa: E402

AIRS = {"minecraft:air", "minecraft:cave_air", "minecraft:structure_void"}
RUINS_DOC = json.loads((ROOT / "data" / "ruins.json").read_text(encoding="utf-8"))
SITE = RUINS_DOC["sites"]["the_scar"]
RECORDS = SITE["ruins"]
PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
RUIN_PLACEMENTS = [p for p in PLACEMENTS["placements"] if p.get("ruin")]
BY_ID = {p["id"]: p for p in PLACEMENTS["placements"]}
SPAWN_BLOCKS = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
IDS = [r["id"] for r in RECORDS]

# vanilla 1.21.1 block tags that data/ruins.json names, written out from the game's data (not from tools/ruins.py)
COLOURS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray", "light_gray", "cyan",
           "purple", "blue", "brown", "green", "red", "black"]
WOODS = ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry", "bamboo", "crimson", "warped"]
COPPER = ["copper", "exposed_copper", "weathered_copper", "oxidized_copper"]
TAGS = {
    "#minecraft:beds": {"minecraft:%s_bed" % c for c in COLOURS},
    "#minecraft:doors": ({"minecraft:%s_door" % w for w in WOODS} | {"minecraft:iron_door"}
                         | {"minecraft:%s_door" % c for c in COPPER} | {"minecraft:waxed_%s_door" % c for c in COPPER}),
    "#minecraft:wool_carpets": {"minecraft:%s_carpet" % c for c in COLOURS},
    "#minecraft:banners": {"minecraft:%s_banner" % c for c in COLOURS} | {"minecraft:%s_wall_banner" % c for c in COLOURS},
    "#minecraft:flower_pots": {"minecraft:flower_pot"} | {"minecraft:potted_" + f for f in (
        "oak_sapling", "spruce_sapling", "birch_sapling", "jungle_sapling", "acacia_sapling", "dark_oak_sapling",
        "cherry_sapling", "mangrove_propagule", "fern", "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet",
        "red_tulip", "orange_tulip", "white_tulip", "pink_tulip", "oxeye_daisy", "cornflower", "lily_of_the_valley",
        "wither_rose", "torchflower", "red_mushroom", "brown_mushroom", "dead_bush", "cactus", "bamboo",
        "crimson_fungus", "warped_fungus", "crimson_roots", "warped_roots", "azalea_bush", "flowering_azalea_bush")},
    "#minecraft:crops": {"minecraft:" + c for c in ("wheat", "carrots", "potatoes", "beetroots", "melon_stem",
                                                     "pumpkin_stem", "torchflower_crop", "pitcher_crop")},
}
# blocks that give light in vanilla 1.21.1 and could come with a village house (the Scar is dark by design)
LIGHT_EMITTERS = ({"minecraft:" + b for b in (
    "torch", "wall_torch", "soul_torch", "soul_wall_torch", "redstone_torch", "redstone_wall_torch", "lantern",
    "soul_lantern", "campfire", "soul_campfire", "jack_o_lantern", "glowstone", "sea_lantern", "shroomlight",
    "redstone_lamp", "end_rod", "lava", "fire", "soul_fire", "magma_block", "glow_lichen", "sea_pickle", "beacon",
    "candle", "ochre_froglight", "verdant_froglight", "pearlescent_froglight", "copper_bulb", "crying_obsidian",
    "respawn_anchor", "brewing_stand")} | {"minecraft:%s_candle" % c for c in COLOURS})


def _expand(entry):
    return TAGS[entry] if entry.startswith("#") else {entry}


REMOVED = set().union(*(_expand(e) for k in ("light", "spawn_blocks", "belongings")
                        for e in SITE["transform"]["remove_blocks"][k]))
NEVER_RUBBLE = set(SITE["transform"]["rubble"]["never"])
RUBBLE_NAMES = {b["block"].split("[")[0] for b in SITE["transform"]["rubble"]["palette"]}
FLOOR_SWAP_FROM = {"minecraft:stone", "minecraft:cobblestone", "minecraft:stone_bricks"}   # overgrowth moss_block
DIRS = ["north", "east", "south", "west"]
STEP = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}


def _rotate(x, z, rot):
    # Minecraft's StructureTemplate transform about the origin, from the game, not from the tool
    return {"none": (x, z), "clockwise_90": (-z, x), "180": (-x, -z), "counterclockwise_90": (z, -x)}[rot]


def _parse(state):
    if "[" not in state:
        return state, {}
    name, rest = state.split("[", 1)
    return name, dict(kv.split("=", 1) for kv in rest.rstrip("]").split(",") if "=" in kv)


def _cells(path):
    """{(x, y, z): (name, props, block nbt)} of a template, read with tools/nbt.py."""
    _, doc = nbt.load(path)
    pal = doc["palette"]
    return doc, {tuple(b["pos"]): (pal[b["state"]]["Name"], dict(pal[b["state"]].get("Properties") or {}), b.get("nbt") or {})
                 for b in doc["blocks"]}


def _as_placed(cells):
    """The whole house as place_town leaves it: every jigsaw its final state (structure_void: nothing), no waystone."""
    out = {}
    for pos, (n, pr, bn) in cells.items():
        if n.startswith("waystones:"):
            continue
        if n == "minecraft:jigsaw":
            fn, fp = _parse(bn.get("final_state") or "minecraft:air")
            if fn == "minecraft:structure_void":
                continue
            out[pos] = (fn, fp)
        else:
            out[pos] = (n, pr)
    return out


def _donor_missing():
    return [p["file"] for p in RUIN_PLACEMENTS if not (ROOT / p["file"]).is_file()]


needs_donors = pytest.mark.skipif(bool(_donor_missing()), reason="Repurposed Structures donor templates are not in "
                                  "kits/structures/incoming/townkit (gitignored, not redistributable): %s" % _donor_missing()[:3])


@pytest.fixture(scope="module")
def ruined(tmp_path_factory):
    """id -> the donor (as placed), its template_info, and two independent builds of its ruined copy."""
    if _donor_missing():
        pytest.skip("donor templates absent under kits/structures/incoming/townkit: %s" % _donor_missing()[:3])
    a, b = tmp_path_factory.mktemp("ruins_a"), tmp_path_factory.mktemp("ruins_b")
    out = {}
    for rec in RECORDS:
        src = ROOT / BY_ID[rec["id"]]["file"]
        info = P.template_info(src)
        R.ruin_template(src, a / (rec["id"] + ".nbt"), info, rec, SITE)
        R.ruin_template(src, b / (rec["id"] + ".nbt"), P.template_info(src), rec, SITE)
        doc, orig = _cells(src)
        _, cp = _cells(a / (rec["id"] + ".nbt"))
        out[rec["id"]] = {"rec": rec, "info": info, "size": list(doc["size"]), "orig": orig, "placed": _as_placed(orig),
                          "copy": cp, "bytes": ((a / (rec["id"] + ".nbt")).read_bytes(), (b / (rec["id"] + ".nbt")).read_bytes())}
    return out


# ------------------------------------------------------------------ records and placements (no donor needed)

# removing this lets a ruin be designed in data/ruins.json and never built, or built from a placement whose lot,
# facing, rotation or corner has drifted from the record that the lot fit and the twin rule were checked against
def test_every_ruin_record_has_exactly_one_matching_placement_and_back():
    assert len(RECORDS) == 33 and len(RUIN_PLACEMENTS) == 33
    assert len(set(IDS)) == len(IDS)
    by_ruin = {}
    for p in RUIN_PLACEMENTS:
        by_ruin.setdefault(p["ruin"], []).append(p)
    assert set(by_ruin) == set(IDS), set(by_ruin) ^ set(IDS)
    for rec in RECORDS:
        (p,) = by_ruin[rec["id"]]
        assert p["settlement"] == SITE["settlement"], rec["id"]
        assert p["template"] == rec["template"], rec["id"]
        assert p.get("lot") == rec["lot"], rec["id"]
        assert p["facing"] == rec["facing"], rec["id"]
        assert p["rotation"] == rec["rotation"], rec["id"]
        assert [p["position"]["x"], p["position"]["z"]] == rec["footprint"][:2], rec["id"]
        ns, path = rec["template"].split(":")
        # file_rule: the local copy of the donor sits at the path the record's template id gives
        assert p["file"] == "kits/structures/incoming/townkit/%s/%s.nbt" % (ns, path), rec["id"]
        assert rec["decay"] in SITE["decay_classes"], rec["id"]


# removing this lets a record's footprint disagree with the template's size under its rotation, or a rotation turn the
# door away from the street, which place_town only discovers at build time
@needs_donors
@pytest.mark.parametrize("rid", IDS)
def test_ruin_footprint_is_the_template_under_its_rotation(rid):
    rec = next(r for r in RECORDS if r["id"] == rid)
    info = P.template_info(ROOT / BY_ID[rid]["file"])
    k = (DIRS.index(rec["facing"]) - DIRS.index(info["entrance"])) % 4
    assert rec["rotation"] == ["none", "clockwise_90", "180", "counterclockwise_90"][k]
    sx, _, sz = info["size"]
    w, d = (sx, sz) if k % 2 == 0 else (sz, sx)
    x0, z0, x1, z1 = rec["footprint"]
    assert (x1 - x0 + 1, z1 - z0 + 1) == (w, d)


# ------------------------------------------------------------------ the ruined copy

# removing this lets a ruin draw from an unseeded source, so every rebuild changes the Scar and town_audit's
# expectation moves with it
@needs_donors
def test_ruined_copy_is_byte_identical_when_generated_twice(ruined, tmp_path):
    for rid, r in ruined.items():
        assert r["bytes"][0] == r["bytes"][1], rid
    # teeth: the draw does depend on the seed, so identical output above is not a transform that draws nothing
    other = dict(SITE, seed=SITE["seed"] + "/other")
    changed = 0
    for rid, r in ruined.items():
        R.ruin_template(ROOT / BY_ID[rid]["file"], tmp_path / (rid + ".nbt"), r["info"], r["rec"], other)
        changed += (tmp_path / (rid + ".nbt")).read_bytes() != r["bytes"][0]
    assert changed >= len(ruined) // 2


# removing this lets the transform cut, swap or add blocks in the floor layer or below, so place_town's seating and its
# verify corners (computed from the whole house) no longer describe what is placed. Two changes are allowed: the
# overgrowth's moss_block swap (data/ruins.json keep) and dropping a remove_blocks block (removed_means: dropped from
# the copy), which data/ruins.json also requires; on the houses whose entrance layer is their room layer the two rules
# otherwise contradict each other
@needs_donors
@pytest.mark.parametrize("rid", IDS)
def test_ground_layer_and_below_are_the_whole_house_except_moss_block(ruined, rid):
    r = ruined[rid]
    G = r["info"]["grade_layer"]
    want = {p: v for p, v in r["placed"].items() if p[1] <= G}
    got = {p: (n, pr) for p, (n, pr, _) in r["copy"].items() if p[1] <= G}
    assert want, "the donor has a floor layer"
    added = sorted((p, got[p]) for p in set(got) - set(want))
    lost = sorted((p, want[p]) for p in set(want) - set(got) if want[p][0] not in REMOVED)
    assert not added and not lost, {"added_at_or_below_grade": added[:8], "lost_at_or_below_grade": lost[:8], "grade": G}
    for p, (n, pr) in got.items():
        if (n, pr) == want[p]:
            continue
        assert n == "minecraft:moss_block" and want[p][0] in FLOOR_SWAP_FROM, (p, want[p], (n, pr))


def _wall_height(r):
    """Tools/ruins.py docstring's measure, from the donor: columns standing at both layers over the floor, and the
    highest layer where at least 60% of them stand."""
    G, (sx, sy, sz) = r["info"]["grade_layer"], r["size"]
    solid = {p for p, (n, _) in r["placed"].items() if n not in AIRS}
    wall = {(x, z) for (x, y, z) in solid if y == G + 1} & {(x, z) for (x, y, z) in solid if y == G + 2}
    wall = wall or {(x, z) for (x, y, z) in solid if y == G + 1}
    eaves = G + 1
    for y in range(G + 1, sy):
        if wall and sum((x, y, z) in solid for x, z in wall) >= 0.6 * len(wall):
            eaves = y
    return max(1, eaves - G)


# removing this lets a ruin stand taller than its decay class allows (a stump with its walls, a roof left on a
# standing ruin), which is the whole reading of the Scar from the square to the rim
@needs_donors
@pytest.mark.parametrize("rid", IDS)
def test_no_block_stands_above_its_decay_class_height(ruined, rid):
    r = ruined[rid]
    G = r["info"]["grade_layer"]
    hi = SITE["decay_classes"][r["rec"]["decay"]]["wall_top_fraction"][1]
    cap = G + max(1, round(_wall_height(r) * hi))
    tall = [(p, n) for p, (n, _, _) in r["copy"].items() if n not in AIRS and p[1] > cap
            and not (n == "minecraft:snow" and p[1] == cap + 1)]     # snow lies one layer on the highest top
    assert not tall, (cap, tall[:8])
    if r["rec"]["decay"] == "stump":
        # the class's own words: one or two courses on the floor
        assert all(p[1] <= G + 2 or n == "minecraft:snow" for p, (n, _, _) in r["copy"].items() if n not in AIRS)


# removing this lets a light, a bell, a cobweb, a bed, a door, a container or a loot table survive into the Scar, which
# is dark by design and must hold nothing players race each other to (data/ruins.json remove_blocks, multiplayer)
@needs_donors
@pytest.mark.parametrize("rid", IDS)
def test_copy_holds_no_removed_block_jigsaw_waystone_or_loot_table(ruined, rid):
    r = ruined[rid]
    bad = sorted((p, n) for p, (n, _, _) in r["copy"].items()
                 if n in REMOVED or n == "minecraft:jigsaw" or n.startswith("waystones:"))
    loot = sorted(p for p, (_, _, bn) in r["copy"].items() if bn.get("LootTable"))
    lit = sorted((p, n) for p, (n, _, _) in r["copy"].items() if n in LIGHT_EMITTERS)
    assert not bad and not loot and not lit, {"removed_blocks_left": bad[:8], "loot_tables_left": loot[:8],
                                              "light_left": lit[:8], "grade_layer": r["info"]["grade_layer"]}


# removing this lets the rubble be laid in gravel, dirt or stone, which tools/town_audit.py reads as ground inside a room
# and reports the ruin buried
@needs_donors
def test_nothing_the_copy_adds_over_the_floor_is_ground_material(ruined):
    added = 0
    for rid, r in ruined.items():
        G = r["info"]["grade_layer"]
        for p, (n, _, _) in r["copy"].items():
            if p[1] > G and n not in AIRS and (r["placed"].get(p) or (None,))[0] != n:
                added += 1
                assert n not in NEVER_RUBBLE, (rid, p, n)
    assert added > 100, "the transform adds rubble, snow and moss over the floor, so the check has cases"


def _doorway(info):
    """The entrance column and one each side, from the door three deep into the house (data/ruins.json rubble)."""
    ex, _, ez = info["entrance_pos"]
    ox, oz = STEP[info["entrance"]]
    ix, iz = -ox, -oz                          # into the house
    px, pz = abs(oz), abs(ox)                  # across the door
    return {(ex + a * px + d * ix, ez + a * pz + d * iz) for a in (-1, 0, 1) for d in range(0, 4)}


def _rubble_added(r):
    swaps_to = {}
    for s in SITE["transform"]["weathering"]["swaps"]:
        if s["to"]:
            swaps_to.setdefault(s["to"], set()).add(s["from"])
    out = []
    for p, (n, _, _) in r["copy"].items():
        before = (r["placed"].get(p) or (None,))[0]
        if n in RUBBLE_NAMES and before != n and before not in swaps_to.get(n, ()):
            out.append((p, n))
    return out


# removing this lets rubble fill the doorway, so the one way into a ruin a player can count on is blocked
@needs_donors
def test_doorway_gets_no_rubble(ruined):
    total = 0
    for rid, r in ruined.items():
        door = _doorway(r["info"])
        rub = _rubble_added(r)
        total += len(rub)
        inside = [(p, n) for p, n in rub if (p[0], p[2]) in door]
        assert not inside, (rid, r["info"]["entrance"], r["info"]["entrance_pos"], inside)
    assert total > 20, "rubble is laid in the Scar, so the doorway rule is exercised (%d)" % total


# removing this lets the transform add a block a loaded spawn condition names (data/spawn_blocks.json), so a ruin
# decides encounters wherever it stands
@needs_donors
def test_every_block_the_copy_adds_is_outside_spawn_blocks(ruined):
    added = set()
    for rid, r in ruined.items():
        for p, (n, _, _) in r["copy"].items():
            if n not in AIRS and (r["placed"].get(p) or (None,))[0] != n:
                added.add(n)
                assert n not in SPAWN_BLOCKS, (rid, p, n)
    assert {"minecraft:snow", "minecraft:mossy_cobblestone"} <= added, sorted(added)


# ------------------------------------------------------------------ place_town build of the_scar

def ground_at(x, z):
    """A hillside: one block every 40 south and every 50 east, with 0-2 of roughness (synthetic, never a world)."""
    return 280 + (z - 900) // 40 + (x - 2000) // 50 + (x * 7 + z * 13) % 3


@pytest.fixture(scope="module")
def scar_builds(tmp_path_factory):
    if _donor_missing():
        pytest.skip("donor templates absent under kits/structures/incoming/townkit: %s" % _donor_missing()[:3])
    out_r, out_w = tmp_path_factory.mktemp("scar_ruined"), tmp_path_factory.mktemp("scar_whole")
    cmds, rep = P.build("the_scar", PLACEMENTS, ground_at, None, out_r)
    whole = copy.deepcopy(PLACEMENTS)
    for p in whole["placements"]:
        p.pop("ruin", None)
    cmds_w, rep_w = P.build("the_scar", whole, ground_at, None, out_w)
    return {"cmds": cmds, "rep": {b["id"]: b for b in rep["buildings"]}, "out": out_r,
            "cmds_w": cmds_w, "rep_w": {b["id"]: b for b in rep_w["buildings"]}}


def _ruined_id(rec):
    ns, path = rec["template"].split(":")
    return "cobblers:towns/ruined/%s/%s__%s" % (ns, path, rec["id"])


# removing this lets the Scar's function place the whole donor house (roof, beds, chests and all) instead of its
# ruined copy, or place a copy the pack does not hold, which /place refuses without a word
@needs_donors
def test_scar_function_places_every_ruin_from_its_ruined_copy(scar_builds, ruined):
    cmds, rep, out = scar_builds["cmds"], scar_builds["rep"], scar_builds["out"]
    placed = [c.split()[2] for c in cmds if c.startswith("place template ")]
    for rec in RECORDS:
        tid = _ruined_id(rec)
        assert placed.count(tid) == 1, rec["id"]
        assert rep[rec["id"]]["template_placed"] == tid
        assert {"removed", "decayed", "breached", "rubble", "snow"} <= set(rep[rec["id"]].get("ruin") or {}), rec["id"]
        ns, path = rec["template"].split(":")
        f = out / "data" / "cobblers" / "structure" / "towns" / "ruined" / ns / (path + "__" + rec["id"] + ".nbt")
        assert f.read_bytes() == ruined[rec["id"]]["bytes"][0], rec["id"]
    assert not [t for t in placed if t.startswith("repurposed_structures:")], "a donor house placed whole"


def _world_cols(rec, info, positions):
    """World (x, z) of template positions, from the record's corner and rotation (Minecraft's transform)."""
    sx, _, sz = info["size"]
    corners = [_rotate(x, z, rec["rotation"]) for x in (0, sx - 1) for z in (0, sz - 1)]
    px = rec["footprint"][0] - min(c[0] for c in corners)
    pz = rec["footprint"][1] - min(c[1] for c in corners)
    return {(px + _rotate(x, z, rec["rotation"])[0], pz + _rotate(x, z, rec["rotation"])[1]) for x, _, z in positions}


def _targets(cmds, verb):
    n = len(verb.split())
    return {(int(c.split()[n]), int(c.split()[n + 2])) for c in cmds if c.startswith(verb + " ")}


# removing this lets place_town set the donor's jigsaw final states or strip loot tables at a ruin after placing it,
# which puts back blocks the decay took (a doorstep on a fallen wall, a floating stair)
@needs_donors
def test_scar_function_sets_no_jigsaw_state_and_removes_no_loot_at_a_ruin(scar_builds, ruined):
    set_r, set_w = _targets(scar_builds["cmds"], "setblock"), _targets(scar_builds["cmds_w"], "setblock")
    loot_r = _targets(scar_builds["cmds"], "data remove block")
    jig_cols, loot_cols = set(), set()
    for rec in RECORDS:
        r = ruined[rec["id"]]
        jig_cols |= _world_cols(rec, r["info"], [p for p, (n, _, _) in r["orig"].items() if n == "minecraft:jigsaw"])
        loot_cols |= _world_cols(rec, r["info"], [p for p, (_, _, bn) in r["orig"].items() if bn.get("LootTable")])
    assert jig_cols and loot_cols
    assert not (set_r & jig_cols), sorted(set_r & jig_cols)[:8]
    assert not (loot_r & loot_cols), sorted(loot_r & loot_cols)[:8]
    # teeth: the same houses placed whole do get their jigsaw setblocks at exactly these columns
    assert set_w & jig_cols


# removing this lets a ruin sit at a different height or on different corners than the whole house would, so the
# verify (which tests the whole house's floor) and the foundations stop describing it
@needs_donors
def test_ruin_is_seated_exactly_as_the_whole_house(scar_builds):
    rep, rep_w = scar_builds["rep"], scar_builds["rep_w"]
    keys = ("rotation", "footprint", "grade_layer", "floor_y", "origin_y", "command_position", "corners", "columns",
            "foundation_columns", "foundation_max_height")
    for rid in IDS:
        assert rid in rep and rid in rep_w, rid
        for k in keys:
            assert rep[rid][k] == rep_w[rid][k], (rid, k)
        assert rep_w[rid]["template_placed"] == BY_ID[rid]["template"]
