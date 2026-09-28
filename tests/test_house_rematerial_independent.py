"""The houses re-materialed into their towns' palettes (be8cac7): data/rematerial.json `house_sets`, the `materials`
names on kind "house" placements in data/placements.json, and tools/place_town.py rewrite_template, which now maps
each jigsaw's final_state as well as the palette.

Written by the test author, not by the session that built the sets.

Independent sources: the Minecraft 1.21.1 client jar's blockstates (the real property lists; its tests SKIP without
the jar, and a skip is not a pass), data/spawn_blocks.json, and synthetic structure templates built here whose every
block is hand-placed, so the expected result of a rewrite is known before the tool runs. The placement function and
the copy are compared through tools/town_audit.py expected_buildings, which is what reads the copy in a real audit.

Not covered here:
  - the real Repurposed Structures houses (kits/structures/incoming, gitignored and absent from a clean checkout):
    test_every_real_materialed_house_rewrites_to_no_mapped_block SKIPS without them;
  - blockstate properties the jar's blockstates do not show (waterlogged; leaves' distance): a family check by
    block-name shape stands in;
  - anything in a world: whether the town looks right, or the server places the copy (a boot and tools/town_audit.py
    against a staging world).
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import level_dat as L  # noqa: E402
import nbt  # noqa: E402
import place_town as PT  # noqa: E402

REMAT = json.loads((ROOT / "data" / "rematerial.json").read_text(encoding="utf-8"))
SETS = REMAT.get("house_sets") or {}
PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
HOUSES = [q for q in PLACEMENTS["placements"] if q.get("kind") == "house"]
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
PAIRS = [(sid, a, b) for sid, s in SETS.items() for a, b in s["map"].items()]

# Defects found by this file (2026-09-28), strict xfail until the data changes: a full block mapped to a pillar gains
# `axis`, so every such block lands in the default axis=y whatever the house meant. Not like for like.
KNOWN_UNLIKE = {
    ("brock_mason_b", "minecraft:birch_planks"): "data/rematerial.json:438 birch_planks -> stripped_birch_wood gains axis",
    ("tea_terrace", "minecraft:yellow_terracotta"): "data/rematerial.json:605 yellow_terracotta -> stripped_cherry_wood "
                                                    "gains axis",
}


def pair_params():
    out = []
    for sid, a, b in PAIRS:
        why = KNOWN_UNLIKE.get((sid, a))
        marks = [pytest.mark.xfail(strict=True, reason=why)] if why else []
        out.append(pytest.param(sid, a, b, marks=marks, id="%s:%s" % (sid, a.split(":")[1])))
    return out


# --------------------------------------------------------------------------------------------- the jar's properties
def _jar():
    try:
        import town_character as TC
        jar = TC.default_vanilla_jar()
    except Exception:  # noqa: BLE001 - no jar is a skip, reported as such
        return None
    return zipfile.ZipFile(jar) if jar and Path(jar).is_file() else None


JAR = _jar()


def jar_properties(block):
    """The property names the 1.21.1 blockstates file of `block` varies on, or None if the jar has no such block."""
    try:
        doc = json.loads(JAR.read("assets/minecraft/blockstates/%s.json" % block.split(":", 1)[1]))
    except KeyError:
        return None
    out = set()
    for key in doc.get("variants") or {}:
        out |= {kv.split("=", 1)[0] for kv in key.split(",") if "=" in kv}

    def walk(when):
        for k, v in when.items():
            if k in ("OR", "AND"):
                for w in v:
                    walk(w)
            else:
                out.add(k)
    for part in doc.get("multipart") or []:
        walk(part.get("when") or {})
    return out


# --------------------------------------------------------------------------------------- the shape family, jar-free
SUFFIXES = ("_wall_sign", "_hanging_sign", "_sign", "_stairs", "_slab", "_fence_gate", "_fence", "_trapdoor", "_door",
            "_button", "_pressure_plate", "_pane", "_carpet", "_leaves", "_sapling", "_wall")
AXIS_SUFFIXES = ("_log", "_wood", "_stem", "_hyphae", "_pillar")
AXIS_BLOCKS = {"basalt", "polished_basalt", "hay_block", "bone_block", "bamboo_block", "stripped_bamboo_block",
               "deepslate", "infested_deepslate", "chain", "ochre_froglight", "verdant_froglight",
               "pearlescent_froglight", "muddy_mangrove_roots"}


def family(block):
    n = block.split(":", 1)[1]
    if n == "iron_bars":
        return "four_sides"
    for s in SUFFIXES:
        if n.endswith(s):
            # a fence and a pane or bars have the same four side connections (and waterlogged)
            return "four_sides" if s in ("_fence", "_pane") else s
    if n.endswith(AXIS_SUFFIXES) or n in AXIS_BLOCKS:
        return "axis"
    return "full"


# ------------------------------------------------------------------------------------------------------ the data
def test_every_material_set_a_house_names_exists_and_swaps_something():
    # Without it a house naming a missing or empty set is placed in its donor's materials, or the town build stops.
    for q in HOUSES:
        m = q.get("materials")
        if m is None:
            continue
        assert isinstance(m, str), "%s: materials should name a house set, not inline a map" % q["id"]
        assert m in SETS, "%s names material set %r, which data/rematerial.json house_sets lacks" % (q["id"], m)
        assert SETS[m].get("map"), "%s: set %s maps nothing" % (q["id"], m)


NO_JAR = "NOT_EXECUTED: no Minecraft 1.21.1 client jar for the real property lists"


@pytest.mark.skipif(JAR is None, reason=NO_JAR)
@pytest.mark.parametrize("sid,src,dst", PAIRS, ids=["%s:%s" % (s, a.split(":")[1]) for s, a, _b in PAIRS])
def test_no_house_set_swap_loses_a_block_state_property(sid, src, dst):
    # Without it a stair mapped to a full block (or a log to planks) loses its facing/half/axis: the properties the
    # target lacks are dropped and the roof or beam sets in the default state.
    a, b = jar_properties(src), jar_properties(dst)
    assert a is not None, "%s: %s is not a 1.21.1 block" % (sid, src)
    assert b is not None, "%s: %s is not a 1.21.1 block" % (sid, dst)
    assert a <= b, "%s: %s -> %s drops %s" % (sid, src, dst, sorted(a - b))


@pytest.mark.skipif(JAR is None, reason=NO_JAR)
@pytest.mark.parametrize("sid,src,dst", pair_params())
def test_every_house_set_swap_has_exactly_the_same_block_state_properties(sid, src, dst):
    # Without it a swap may also GAIN a property (a full block to a pillar): the house never set it, so every such
    # block stands in the default state. Like for like means the same property list.
    a, b = jar_properties(src), jar_properties(dst)
    assert a == b, "%s: %s %s -> %s %s is not like for like" % (sid, src, sorted(a), dst, sorted(b))


@pytest.mark.parametrize("sid,src,dst", pair_params())
def test_every_house_set_swap_stays_in_its_shape_family(sid, src, dst):
    # Jar-free stand-in for the check above: stairs to stairs, slab to slab, wall to wall, a pillar to a pillar.
    assert src.startswith("minecraft:") and dst.startswith("minecraft:") and src != dst, (sid, src, dst)
    assert family(src) == family(dst), "%s: %s (%s) -> %s (%s)" % (sid, src, family(src), dst, family(dst))


def test_no_house_set_puts_a_spawn_condition_into_a_town():
    # Without it a re-materialed house could carry a block a spawn entry names (quartz, which Sabrina's palette
    # lists, is one) and change what spawns in the town.
    bad = [(sid, b) for sid, _a, b in PAIRS if b in SPAWN]
    assert not bad, bad


def test_the_towns_with_two_sets_alternate_them_house_by_house():
    # Without it a two-set town could put its houses in runs of one colour, which is what the pairing prevents.
    by_town = {}
    for q in HOUSES:
        if isinstance(q.get("materials"), str):
            by_town.setdefault(q["settlement"], []).append(q["materials"])
    two = {t: seq for t, seq in by_town.items() if len(set(seq)) == 2}
    assert two, "no town uses two sets: the alternation has nothing to check"
    for town, seq in two.items():
        runs = [i for i in range(1, len(seq)) if seq[i] == seq[i - 1]]
        assert not runs, "%s: houses %s repeat the set of the house before" % (town, runs)
    # the bigger towns the brief pairs: each of them has two sets
    for town in ("gym1_town", "gym2_town", "gym5_town", "gym6_town", "gym8_town", "sunset_west"):
        assert len(set(by_town.get(town) or [])) == 2, town


def test_hometown_and_the_scar_keep_their_own_materials():
    # Without it Pallet (its being unaltered is the clue, ARC.md) or the Scar's ruins would be re-materialed.
    for q in HOUSES:
        if q.get("settlement") in ("hometown", "the_scar"):
            assert not q.get("materials"), "%s: %s is not re-materialed by design" % (q["id"], q["settlement"])


# ------------------------------------------------------------------------------------------ a synthetic template
MAP = {"minecraft:cobblestone": "minecraft:stone_bricks",
       "minecraft:cobblestone_stairs": "minecraft:stone_brick_stairs",
       "minecraft:oak_log": "minecraft:spruce_log"}


def _s(v):
    return (L.STRING, v)


def _ints(*v):
    return (L.LIST, (L.INT, list(v)))


def _jigsaw_nbt(final, name="minecraft:x"):
    return (L.COMPOUND, {"final_state": _s(final), "joint": _s("rollable"), "name": _s(name),
                         "pool": _s("minecraft:empty"), "target": _s("minecraft:empty")})


def write_template(path):
    """A 3 by 3 by 3 house: a cobblestone floor with a dirt-path entrance jigsaw on its north edge, a cobblestone
    stair and an oak log inside, and three more jigsaws whose final states are a mapped stair with properties, a
    mapped plain block and an unmapped block. Every expected name is known before the tool runs."""
    palette = [("minecraft:cobblestone", {}),
               ("minecraft:jigsaw", {"orientation": "north_up"}),
               ("minecraft:cobblestone_stairs", {"facing": "north", "half": "bottom", "shape": "straight",
                                                 "waterlogged": "false"}),
               ("minecraft:oak_log", {"axis": "y"}),
               ("minecraft:oak_planks", {}),
               ("minecraft:jigsaw", {"orientation": "west_up"}),
               ("minecraft:air", {})]
    blocks = []
    for x in range(3):
        for z in range(3):
            if (x, z) != (1, 0):
                blocks.append(((x, 0, z), 0, None))
    blocks.append(((1, 0, 0), 1, "minecraft:dirt_path"))                                   # the entrance
    blocks.append(((0, 1, 1), 5, "minecraft:cobblestone_stairs[facing=east,half=top,shape=straight]"))
    blocks.append(((2, 1, 1), 5, "minecraft:cobblestone"))
    blocks.append(((1, 2, 2), 5, "minecraft:oak_planks"))
    blocks.append(((1, 1, 1), 2, None))
    blocks.append(((1, 1, 2), 3, None))
    blocks.append(((2, 2, 2), 4, None))
    blocks.append(((1, 2, 1), 6, None))
    pal = (L.LIST, (L.COMPOUND, [
        {"Name": _s(n), **({"Properties": (L.COMPOUND, {k: _s(v) for k, v in p.items()})} if p else {})}
        for n, p in palette]))
    bl = (L.LIST, (L.COMPOUND, [
        {"pos": _ints(*pos), "state": (L.INT, st), **({"nbt": _jigsaw_nbt(fin)} if fin else {})}
        for pos, st, fin in blocks]))
    root = {"DataVersion": (L.INT, 3955), "size": _ints(3, 3, 3), "palette": pal, "blocks": bl,
            "entities": (L.LIST, (L.COMPOUND, []))}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(L.dumps("", root))
    return path


def used_names(path):
    """Every block name a template places: palette names in use, a jigsaw read as its final state."""
    _, doc = nbt.load(path)
    pal = doc["palette"]
    out = []
    for b in doc["blocks"]:
        n = pal[b["state"]]["Name"]
        if n == "minecraft:jigsaw":
            n = re.split(r"[\[{]", (b.get("nbt") or {}).get("final_state") or "minecraft:air", 1)[0]
        out.append(n)
    return out


def test_a_rewritten_template_holds_no_mapped_block_jigsaw_final_states_included(tmp_path):
    # Without it a jigsaw's final state stays in the donor's material: the town then sets that block and
    # tools/town_audit.py, reading the copy, expects the other (the defect be8cac7 fixed).
    src = write_template(tmp_path / "house.nbt")
    before = used_names(src)
    assert {"minecraft:cobblestone", "minecraft:cobblestone_stairs", "minecraft:oak_log"} <= set(before)
    dest = tmp_path / "copy.nbt"
    PT.rewrite_template(src, dest, materials=MAP)
    after = used_names(dest)
    assert not set(after) & set(MAP), sorted(set(after) & set(MAP))
    assert len(after) == len(before)
    # hand-computed: 8 floor blocks + 1 jigsaw to stone bricks, the stair and the stair jigsaw to brick stairs, the log
    assert after.count("minecraft:stone_bricks") == 9
    assert after.count("minecraft:stone_brick_stairs") == 2
    assert after.count("minecraft:spruce_log") == 1
    assert after.count("minecraft:oak_planks") == 2 and after.count("minecraft:dirt_path") == 1
    # a final state keeps its properties through the rename
    _, doc = nbt.load(dest)
    finals = sorted((b.get("nbt") or {}).get("final_state") for b in doc["blocks"] if b.get("nbt"))
    assert "minecraft:stone_brick_stairs[facing=east,half=top,shape=straight]" in finals
    # and a palette entry keeps its properties: the stair still faces north, the log stands on y
    props = {e["Name"]: e.get("Properties") for e in doc["palette"]}
    assert props["minecraft:stone_brick_stairs"]["facing"] == "north"
    assert props["minecraft:spruce_log"] == {"axis": "y"}


def test_the_placement_function_and_its_rewritten_copy_agree_on_every_block(tmp_path, monkeypatch):
    # Without it the town places one block and tools/town_audit.py (which reads the copy) expects another: the audit
    # reports a missing block that is there, or passes one that is not.
    import town_audit as TA
    src = write_template(tmp_path / "kit" / "house.nbt")
    doc = {"settlements": {"t": {"plan": {}}},
           "placements": [{"id": "t_house_1", "settlement": "t", "kind": "house", "template": "fx:houses/house",
                           "file": str(src), "position": {"x": 100, "z": 200}, "facing": "north",
                           "materials": dict(MAP)}]}
    out_dir = tmp_path / "build" / "datapacks" / "cobblers_towns"
    cmds, report = PT.build("t", doc, lambda x, z: 64, out_dir=out_dir)
    (b,) = report["buildings"]
    assert b["template_placed"] == "cobblers:towns/stripped/fx/houses/house__t_house_1"
    # what the audit expects, read from the copy exactly as a real audit reads it
    (tmp_path / "derived" / "towns").mkdir(parents=True)
    (tmp_path / "derived" / "towns" / "t_placement.json").write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(TA, "ROOT", tmp_path)
    ((bid, expected, _rooms, _note),) = [e for e in TA.expected_buildings("t", doc) if e[0] == "t_house_1"]
    assert expected, "the audit expects nothing of the house"
    # what the town places: the copy by `place template`, then the placement function's setblocks over it
    copy = out_dir / "data" / "cobblers" / "structure" / "towns" / "stripped" / "fx" / "houses" / "house__t_house_1.nbt"
    _, cdoc = nbt.load(copy)
    ox, oy, oz = b["command_position"]
    assert b["rotation"] == "none"
    world = {(ox + q["pos"][0], oy + q["pos"][1], oz + q["pos"][2]): cdoc["palette"][q["state"]]["Name"]
             for q in cdoc["blocks"]}
    placed = False
    for line in cmds:
        if line.startswith("place template "):
            placed = True
            continue
        m = re.match(r"setblock (-?\d+) (-?\d+) (-?\d+) (\S+)", line)
        if placed and m:
            world[tuple(int(v) for v in m.groups()[:3])] = re.split(r"[\[{]", m.group(4), 1)[0]
    assert placed
    differ = {p: (world.get(p), n) for p, n in expected.items() if world.get(p) != n}
    assert not differ, "placed vs expected: %s" % differ
    # hand-computed: the two mapped jigsaws are placed and expected in the set's blocks
    assert expected[(ox + 0, oy + 1, oz + 1)] == "minecraft:stone_brick_stairs"
    assert expected[(ox + 2, oy + 1, oz + 1)] == "minecraft:stone_bricks"
    assert not set(world.values()) & set(MAP)


# --------------------------------------------------------------------------------------- the real (local) houses
REAL = [q for q in HOUSES if isinstance(q.get("materials"), str) and q["materials"] in SETS]


def test_every_real_materialed_house_rewrites_to_no_mapped_block(tmp_path):
    # Without it a set that misses a block form a real house uses (a jigsaw's final state, a variant) leaves donor
    # material in the town. The houses are Repurposed Structures', local only: absent, this SKIPS.
    present = [q for q in REAL if (ROOT / q["file"]).is_file()]
    if not present:
        pytest.skip("NOT_EXECUTED: none of the %d materialed house templates is in this checkout "
                    "(kits/structures/incoming is local only)" % len(REAL))
    problems = []
    for q in present:
        m = SETS[q["materials"]]["map"]
        dest = tmp_path / (q["id"] + ".nbt")
        PT.rewrite_template(ROOT / q["file"], dest, materials=m)
        left = set(used_names(dest)) & set(m)
        if left:
            problems.append((q["id"], sorted(left)))
        if JAR is not None:
            _, doc = nbt.load(dest)
            for e in doc["palette"]:
                if e["Name"] in m.values() and e.get("Properties"):
                    known = jar_properties(e["Name"]) or set()
                    extra = set(e["Properties"]) - known - {"waterlogged"}
                    if extra:
                        problems.append((q["id"], e["Name"], sorted(extra)))
    assert not problems, problems[:10]
