"""tools/place_town.py: template reading, seating buildings on the ground (build), waystone stripping and fill
splitting.

Uses the real templates in kits/structures/campaign (read only) and a synthetic ground function; build() writes
only the stripped template copy, into tmp_path. Nothing here reads a world, touches a server or runs a command.

Not covered: whether the generated commands build correctly in Minecraft (/place template rotation, jigsaw
replacement, the Waystones registry), extraction of the ground from region files (world_heights.extract), roads,
and verify() over RCON. Those need the stopped world and a running server, recorded as an experiment.
"""
import gzip
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import level_dat as L  # noqa: E402
import nbt  # noqa: E402
import place_town as P  # noqa: E402
import structure_nbt as S  # noqa: E402

KIT = "kits/structures/campaign/f4"
POKECENTER = KIT + "/services/pokecenter.nbt"
POKEMART = KIT + "/services/structure_pokemart.nbt"
HOUSES = [KIT + "/pallet/buildings/%s.nbt" % n for n in ("large1", "large2", "small1", "small2", "small3")]
AIRS = ("minecraft:air", "minecraft:structure_void", "minecraft:cave_air")


def _raw_blocks(path):
    _, doc = nbt.load(ROOT / path)
    return doc, [doc["palette"][b["state"]]["Name"] for b in doc["blocks"]]


# ------------------------------------------------------------------ template_info

# removing this lets the ground layer be read from somewhere other than the entrance jigsaw, so the Pokemon Center
# (door three layers up, over a basement) floats or sinks by that difference again
@pytest.mark.parametrize("path,grade,entrance", [(POKECENTER, 3, "west"), (POKEMART, 0, "east")] +
                         [(h, 0, "west") for h in HOUSES])
def test_template_info_grade_layer_is_the_entrance_jigsaw_layer(path, grade, entrance):
    info = P.template_info(ROOT / path)
    assert info["grade_layer"] == grade == info["entrance_pos"][1]
    assert info["entrance"] == entrance
    doc, names = _raw_blocks(path)
    ent = [b for b, n in zip(doc["blocks"], names) if n == "minecraft:jigsaw" and list(b["pos"]) == list(info["entrance_pos"])]
    assert ent and (ent[0].get("nbt") or {}).get("final_state") in ("minecraft:dirt_path", "minecraft:stone")


# removing this lets base columns include air or blocks above the ground layer, or record a lowest block that is not
# the lowest, so foundations are poured under nothing or stop short
@pytest.mark.parametrize("path", [POKECENTER, HOUSES[2]])
def test_template_info_base_and_grade_columns(path):
    info = P.template_info(ROOT / path)
    doc, names = _raw_blocks(path)
    G = info["grade_layer"]
    want = {}
    for b, n in zip(doc["blocks"], names):
        x, y, z = b["pos"]
        if y <= G and n not in AIRS:
            want[(x, z)] = min(want.get((x, z), y), y)
    assert info["base"] == want
    grade = {(b["pos"][0], b["pos"][2]) for b, n in zip(doc["blocks"], names)
             if b["pos"][1] == G and n not in AIRS + ("minecraft:jigsaw",)}
    assert info["grade_cols"] == grade and grade <= set(want)


# removing this lets a donor's waystones go unnoticed, so placing the template registers a stray waystone
def test_template_info_finds_waystones():
    assert P.template_info(ROOT / POKECENTER)["waystones"] == [[4, 4, 4], [4, 5, 4]]
    for h in HOUSES:
        assert P.template_info(ROOT / h)["waystones"] == []


# ------------------------------------------------------------------ build

def ground_at(x, z):
    """A hillside rising one block every three blocks south and one every five blocks east, with 0-2 blocks of
    roughness, so the samples in front of a door differ and their median is not any single one of them."""
    return 60 + (z - 1000) // 3 + (x - 1000) // 5 + (x * 7 + z * 13) % 3


PLACEMENTS = [
    {"id": "center", "settlement": "t", "template": "cobblers:f4/services/pokecenter", "file": POKECENTER,
     "facing": "west", "position": {"x": 1000, "z": 1000}},
    {"id": "house", "settlement": "t", "template": "cobblers:f4/pallet/buildings/small1", "file": HOUSES[2],
     "facing": "south", "position": {"x": 1060, "z": 1000}},
    {"id": "mart", "settlement": "t", "template": "cobblers:f4/services/structure_pokemart", "file": POKEMART,
     "facing": "south", "position": {"x": 1000, "z": 1060}},
]
DOC = {"settlements": {"t": {"roads": [], "waystone": {"position": [990, 990], "facing": "north"}, "spawn": [985, 985]}},
       "placements": PLACEMENTS}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("pack")
    cmds, report = P.build("t", DOC, ground_at, None, out)
    return cmds, {b["id"]: b for b in report["buildings"]}, out


def _fills(cmds):
    rows = []
    for c in cmds:
        t = c.split()
        if t[0] == "fill":
            rows.append((tuple(int(v) for v in t[1:7]), t[7], " ".join(t[8:])))
    return rows


# removing this lets a column of a building hang over lower ground with nothing under it (the floating buildings the
# placer used to produce)
@pytest.mark.parametrize("bid", ["center", "house", "mart"])
def test_build_supports_every_base_column(built, bid):
    cmds, b, out = built
    fills = {(box, blk) for box, blk, rest in _fills(cmds) if rest == ""}
    material = "minecraft:stone_bricks"
    assert b[bid]["columns"]
    filled = 0
    for wx, wz, bottom in b[bid]["columns"]:
        gy = ground_at(wx, wz)
        if gy < bottom - 1:
            assert ((wx, gy + 1, wz, wx, bottom - 1, wz), material) in fills, (bid, wx, wz, gy, bottom)
            filled += 1
        else:
            assert gy >= bottom - 1
    assert filled > 0, "the slope leaves some columns above the ground, so the rule is exercised"
    assert b[bid]["foundation_columns"] == filled


# removing this lets the placer lay a levelled pad under a building (a fill wider than one column in any material)
def test_build_lays_no_pads(built):
    cmds, b, out = built
    for (x0, y0, z0, x1, y1, z1), blk, rest in _fills(cmds):
        if blk != "minecraft:air":
            assert x0 == x1 and z0 == z1, ("a fill of %s over more than one column" % blk, x0, z0, x1, z1)


# removing this lets the floor be seated anywhere but the ground in front of the door, so the entrance steps up or
# down from the street
# Changed 2026-09-20 with the rule it protects, after houses in Brock's town came out a block into
# the hill: the floor is the door's grade unless that would bury the uphill side, and then it is the
# highest ground the building covers. Without this a building on any fall is partly underground.
def test_build_floor_is_the_door_grade_but_never_below_the_ground_it_covers(built):
    cmds, b, out = built
    info = P.template_info(ROOT / POKECENTER)
    ex, ez = 1000 + info["entrance_pos"][0], 1000 + info["entrance_pos"][2]     # rotation none: facing west
    front = sorted(ground_at(ex - k, ez + j) for k in (1, 2) for j in (-1, 0, 1))
    # This fixture has no computed plan, so there is no measured lot ground and the rule falls back
    # to the door's grade. Where a lot ground exists it wins, which is what stops a building being
    # seated into the hill behind it.
    floor = int(np.median(front))
    assert front[0] < floor < front[-1], ("the samples differ, so min, max and median disagree", front)
    assert b["center"]["rotation"] == "none"
    assert b["center"]["floor_y"] == floor and b["center"]["origin_y"] == floor - 3
    assert "place template cobblers:towns/stripped/cobblers/f4/services/pokecenter 1000 %d 1000 none none 1.0 0" % (floor - 3) in cmds


# removing this lets a column whose lowest stored block sits above the template floor keep the pocket of air under
# it (the template's air is placed after the ground): those columns get a replace-#replaceable fill, others none
def test_build_fills_air_under_raised_lowest_blocks(built):
    cmds, b, out = built
    info = P.template_info(ROOT / POKECENTER)
    oy = b["center"]["origin_y"]
    replace = {box for box, blk, rest in _fills(cmds) if rest == "replace #minecraft:replaceable"}
    raised = [(tx, tz, by) for (tx, tz), by in info["base"].items() if by > 0]
    assert len(raised) == 316
    for tx, tz, by in raised:
        wx, wz = 1000 + tx, 1000 + tz
        assert (wx, oy, wz, wx, oy + by - 1, wz) in replace, (tx, tz, by)
    house_box = b["house"]["footprint"]
    mart_box = b["mart"]["footprint"]
    for x0, y0, z0, x1, y1, z1 in replace:
        for fx0, fz0, fx1, fz1 in (house_box, mart_box):
            assert not (fx0 <= x0 <= fx1 and fz0 <= z0 <= fz1), "houses and the mart stand on layer 0: no pockets"
    assert len(replace) == len(raised)


# removing this lets the corner check sample the ground inside the building instead of outside it
@pytest.mark.parametrize("bid", ["center", "house", "mart"])
def test_build_corner_outside_columns_lie_outside_the_footprint(built, bid):
    cmds, b, out = built
    x0, z0, x1, z1 = b[bid]["footprint"]
    assert len(b[bid]["corners"]) == 4
    for c in b[bid]["corners"]:
        ox, oz = c["outside"]
        assert not (x0 <= ox <= x1) and not (z0 <= oz <= z1), ("diagonally outside the corner", c)
        assert abs(ox - c["corner"][0]) == 1 and abs(oz - c["corner"][1]) == 1
        assert c["ground_outside_y"] == ground_at(ox, oz)


# removing this lets a rotated building's columns be computed outside its own footprint (wrong rotation transform)
@pytest.mark.parametrize("bid", ["house", "mart"])
def test_build_rotated_columns_stay_inside_the_footprint(built, bid):
    cmds, b, out = built
    x0, z0, x1, z1 = b[bid]["footprint"]
    assert b[bid]["rotation"] != "none"
    for wx, wz, bottom in b[bid]["columns"]:
        assert x0 <= wx <= x1 and z0 <= wz <= z1


# removing this lets the rotation turn the entrance to the wrong side (a transform that swaps clockwise and
# counterclockwise keeps every column inside the footprint but puts the door on the opposite face)
@pytest.mark.parametrize("bid,path", [("center", POKECENTER), ("house", HOUSES[2]), ("mart", POKEMART)])
def test_build_turns_the_entrance_to_the_requested_face(built, bid, path):
    cmds, b, out = built
    info = P.template_info(ROOT / path)
    px, oy, pz = b[bid]["command_position"]
    (ex, ey, ez), final = info["entrance_pos"], next(f for pos, f, _ in info["jigsaws"] if pos == info["entrance_pos"])
    rx, rz = P.rotate(ex, ez, b[bid]["rotation"])
    wx, wz = px + rx, pz + rz
    x0, z0, x1, z1 = b[bid]["footprint"]
    edge = {"west": wx == x0, "east": wx == x1, "north": wz == z0, "south": wz == z1}[b[bid]["facing"]]
    assert edge, (bid, b[bid]["facing"], (wx, wz), b[bid]["footprint"])
    assert "setblock %d %d %d %s" % (wx, oy + ey, wz, final) in cmds


# removing this lets a template with donor waystones be placed as is
def test_build_places_the_stripped_pokecenter(built):
    cmds, b, out = built
    stripped = out / "data" / "cobblers" / "structure" / "towns" / "stripped" / "cobblers" / "f4" / "services" / "pokecenter.nbt"
    assert stripped.is_file()
    assert P.template_info(stripped)["waystones"] == []
    assert b["center"]["template_placed"] == "cobblers:towns/stripped/cobblers/f4/services/pokecenter"
    assert b["house"]["template_placed"] == "cobblers:f4/pallet/buildings/small1"
    assert not any(c.startswith("place template cobblers:f4/services/pokecenter ") for c in cmds)


# removing this lets a template without a dirt-path or stone entrance jigsaw crash build() (it had raised a TypeError)
# or be refused without naming the placement and template to fix
def test_build_refuses_a_template_without_an_entrance(tmp_path):
    path = tmp_path / "doorless.nbt"
    path.write_bytes(S.dumps([3, 2, 3], [("minecraft:stone", {})], [(x, 0, z, 0) for x in range(3) for z in range(3)]))
    doc = {"settlements": DOC["settlements"],
           "placements": [{"id": "crate_placement", "settlement": "t", "template": "cobblers:test/doorless",
                           "file": str(path), "facing": "west", "position": {"x": 1000, "z": 1000}}]}
    with pytest.raises(SystemExit) as e:
        P.build("t", doc, ground_at, None, tmp_path)
    msg = str(e.value.code)
    assert msg.startswith("crate_placement:"), msg
    assert "cobblers:test/doorless" in msg and "entrance" in msg, msg


# ------------------------------------------------------------------ strip_waystones

# removing this lets stripping drop, reorder or alter anything but the waystone blocks (block entity data, other
# blocks, entities), or write a file that does not round-trip
def test_strip_waystones_removes_only_waystones(tmp_path):
    dest = tmp_path / "out" / "pokecenter.nbt"
    assert P.strip_waystones(ROOT / POKECENTER, dest) == 2
    raw = dest.read_bytes()
    name, root = L.loads(raw)
    assert gzip.decompress(L.dumps(name, root)) == gzip.decompress(raw)
    sname, sroot = L.loads((ROOT / POKECENTER).read_bytes())
    names = [L.plain(e["Name"]) for e in sroot["palette"][1][1]]
    src_blocks = sroot["blocks"][1][1]
    out_blocks = root["blocks"][1][1]
    assert (len(src_blocks), len(out_blocks)) == (6653, 6651)
    assert (sum(1 for b in src_blocks if "nbt" in b), sum(1 for b in out_blocks if "nbt" in b)) == (64, 62)
    kept = [b for b in src_blocks if not names[L.plain(b["state"])].startswith("waystones:")]
    assert out_blocks == kept
    assert not any(names[L.plain(b["state"])].startswith("waystones:") for b in out_blocks)
    for key in sroot:
        if key != "blocks":
            assert root[key] == sroot[key], key


# ------------------------------------------------------------------ fill_boxes

# removing this lets a fill command exceed Minecraft's 32768-block limit (the command fails and leaves the volume
# unfilled) or leave gaps or overlaps in the volume it splits
@pytest.mark.parametrize("vol", [(0, 0, 0, 0, 0, 0), (0, 60, 0, 21, 75, 22), (5, -10, 5, 204, 20, 204),
                                 (0, 0, 0, 180, 3, 1), (0, 0, 0, 1, 300, 1), (-40, 0, -40, 250, 2, 250)])
def test_fill_boxes_respect_the_limit_and_cover_the_volume_exactly(vol):
    x0, y0, z0, x1, y1, z1 = vol
    boxes = P.fill_boxes(*vol)
    cover = np.zeros((x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1), np.int32)
    for bx0, by0, bz0, bx1, by1, bz1 in boxes:
        assert bx0 <= bx1 and by0 <= by1 and bz0 <= bz1
        assert (bx1 - bx0 + 1) * (by1 - by0 + 1) * (bz1 - bz0 + 1) <= 32768
        cover[bx0 - x0:bx1 - x0 + 1, by0 - y0:by1 - y0 + 1, bz0 - z0:bz1 - z0 + 1] += 1
    assert (cover == 1).all()
