"""The dungeon rip's animated oval (tools/rip_art.py, tools/rip_pack.py, tools/dungeon.py R16DR).

Expectations come from the OUTPUT (decoded PNG pixels, the emitted summon line, the pack's files) and from the
authored data; none is taken from rip_art's own colour constants or the pack's own derivation.
"""
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import rip_art  # noqa: E402
import rip_pack as RP  # noqa: E402

DOC = D.load()
ART = DOC["engine"]["rip_art"]
W, H, N = ART["frame"]["width"], ART["frame"]["height"], ART["frames"]


@pytest.fixture(scope="module")
def pack():
    return RP.files(DOC)


@pytest.fixture(scope="module")
def strip(pack):
    png = pack["assets/cobblers/textures/item/dungeon_rip.png"]
    return np.array(Image.open(io.BytesIO(png)).convert("RGBA"))


def frame_of(strip, k):
    return strip[k * H:(k + 1) * H]


# ------------------------------------------------------------------------------------------------ the pack
def test_pack_holds_exactly_the_five_files(pack):
    assert sorted(pack) == sorted([
        "pack.mcmeta",
        "assets/minecraft/models/item/amethyst_shard.json",
        "assets/cobblers/models/item/dungeon_rip.json",
        "assets/cobblers/textures/item/dungeon_rip.png",
        "assets/cobblers/textures/item/dungeon_rip.png.mcmeta"])
    assert json.loads(pack["pack.mcmeta"])["pack"]["pack_format"] == 34     # 1.21.1's resource format (client jar)


def test_carrier_override_points_at_the_data_values(pack):
    ov = json.loads(pack["assets/minecraft/models/item/amethyst_shard.json"])["overrides"]
    assert ART["item"] == "minecraft:amethyst_shard"
    assert ov == [{"predicate": {"custom_model_data": 4180}, "model": "cobblers:item/dungeon_rip"}]
    assert ART["custom_model_data"] == 4180 and ART["model"] == "cobblers:item/dungeon_rip"


def test_oval_model_is_two_flat_faces_over_the_texture(pack):
    m = json.loads(pack["assets/cobblers/models/item/dungeon_rip.json"])
    assert m["textures"]["0"] == "cobblers:item/dungeon_rip"
    (el,) = m["elements"]
    assert el["from"][2] == el["to"][2], "a flat plane, like block/cross"
    assert set(el["faces"]) == {"north", "south"}, "both sides, because the culling sheet hides a back face"
    assert el["from"][:2] == [0, 0] and el["to"][:2] == [16, 16]


def test_texture_is_a_vertical_strip_whose_mcmeta_names_the_frame(pack, strip):
    meta = json.loads(pack["assets/cobblers/textures/item/dungeon_rip.png.mcmeta"])["animation"]
    assert strip.shape == (H * N, W, 4)
    assert (meta["width"], meta["height"]) == (W, H)
    assert meta["frametime"] == 5 and meta["interpolate"] is True
    assert "frames" not in meta, "every frame in order: the strip is the whole loop"


def test_build_is_deterministic():
    a, b = RP.files(DOC), RP.files(DOC)
    assert a == b


def test_zip_round_trip(tmp_path):
    out = tmp_path / "x" / "cobblers-rip.zip"
    RP.write_zip(out, RP.files(DOC))
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        assert "assets/cobblers/textures/item/dungeon_rip.png" in z.namelist()


# ------------------------------------------------------------------------------------------------ the art, measured
def _polar(k):
    ys, xs = np.mgrid[0:H, 0:W]
    u = (xs + 0.5 - W / 2) / (W / 2)
    v = (ys + 0.5 - H / 2) / (H / 2)
    return np.sqrt(u * u + v * v)


def test_art_is_an_oval_with_clear_corners_and_a_solid_heart(strip):
    r = _polar(0)
    for k in range(N):
        f = frame_of(strip, k)
        assert f[0, 0, 3] == f[0, W - 1, 3] == f[H - 1, 0, 3] == f[H - 1, W - 1, 3] == 0
        assert f[..., 3][r > 1.02].max() == 0, "nothing outside the unit ellipse"
        assert f[..., 3][r < 0.5].min() >= 200, "the heart is nearly opaque"
        assert f[..., 3][r > 0.5].max() > 0


def test_art_reads_blue_then_lavender_then_pink(strip):
    """Colour classes by channel order, measured on the decoded pixels averaged over the whole loop."""
    r = _polar(0)
    rgb = strip.reshape(N, H, W, 4).astype(float)
    a = rgb[..., 3] > 128
    def mean(mask):
        sel = a & mask[None]
        return rgb[..., :3][sel].mean(axis=0)
    centre = mean(r < 0.15)
    band = mean((r > 0.42) & (r < 0.52))
    ring = mean((r > 0.74) & (r < 0.90))
    assert centre[2] > centre[1] > centre[0] and centre[2] > 230, "pale blue: b > g > r, bright"
    assert band[2] > band[0] > band[1], "lavender: b > r > g"
    assert ring[0] > ring[2] > ring[1], "pink: r > b > g"
    assert ring[0] > 220


def test_ring_is_puffy_not_a_hard_band(strip):
    """The outer edge moves: the ring's outermost opaque radius differs between angles and between frames."""
    r = _polar(0)
    ys, xs = np.mgrid[0:H, 0:W]
    ang = np.arctan2(ys + 0.5 - H / 2, xs + 0.5 - W / 2)
    edges = []
    for k in (0, N // 3, 2 * N // 3):
        f = frame_of(strip, k)
        for lo in np.linspace(-np.pi, np.pi, 9)[:-1]:
            sel = (ang >= lo) & (ang < lo + np.pi / 4) & (f[..., 3] > 128)
            edges.append(r[sel].max())
    assert max(edges) - min(edges) > 0.04


def test_loop_is_seamless_and_it_moves(strip):
    fs = [frame_of(strip, k).astype(float) for k in range(N)]
    step = [np.abs(fs[(k + 1) % N] - fs[k]).mean() for k in range(N)]   # includes the wrap N-1 -> 0
    assert step[-1] < 2.0 * np.mean(step[:-1]), "the wrap is no bigger a jump than any other step"
    assert np.mean(step) > 0, "it is not a still picture"
    assert np.abs(fs[0] - fs[N // 2]).mean() > np.mean(step), "half a loop later it is further from the start than one step is"


# ------------------------------------------------------------------------------------------------ the world side
def test_summon_line_carries_the_asset_and_stands_in_front_of_the_frame():
    d = DOC["rips"][0]          # the first standing rip (data/dungeon_rips.json; the Night Shift's trail rip was retired 2026-10-13)
    line = D.oval_summon(DOC, d)
    f, o = d["frame"], d["oval"]
    assert line.startswith("summon minecraft:item_display ")
    assert 'id:"minecraft:amethyst_shard"' in line and '"minecraft:custom_model_data":4180' in line
    assert "brightness:{sky:15,block:15}" in line
    assert "scale:[3.00f,4.00f,1f]" in line
    m = re.match(r"summon minecraft:item_display (\S+) (\S+) (\S+) ", line)
    x, y, z = (float(g) for g in m.groups())
    assert x == (f["x0"] + f["x1"]) / 2 + 0.5                        # the frame's column
    assert y - o["height"] / 2 == f["y"]                             # foot on the frame's y
    assert f["z"] < z <= f["z"] + 1.5 and z > f["z"] + 1             # in front of the opening's face, not in the block
    assert line.count("{") == line.count("}") and line.count("[") == line.count("]")
    for tag in (D.rip_tag(d), "dg.rip_oval", "dg.rip_new"):
        assert '"%s"' % tag in line


def test_oval_lies_over_the_click_interaction():
    d = DOC["rips"][0]
    x, y, z = D.oval_pos(d)
    cx, cy, cz = d["click"]
    assert abs(x - (cx + 0.5)) <= 1.5 and cz - 0.5 <= z <= cz + 3.5   # a click on it hits the 3-wide interaction behind


def test_chain_kills_and_summons_the_oval_with_the_interaction_and_counts_unchanged():
    out, _want_shell, want_rips = D.chains(DOC)
    act = "\n".join(out["cobblers:dungeons/rips/entities_act"])
    assert "summon minecraft:interaction" in act and "summon minecraft:item_display" in act
    tag = D.rip_tag(DOC["rips"][0])
    assert "kill @e[type=minecraft:item_display,tag=%s,tag=dg.rip_oval]" % tag in act
    done = "\n".join(out["cobblers:dungeons/rips/entities_done"])
    assert "type=minecraft:item_display,tag=%s,tag=dg.rip_oval" % tag in done      # de-duplicated like the interaction
    assert want_rips == len(DOC["rips"])                                           # the count is still the interactions, one a rip


def test_problems_refuse_a_stretched_or_buried_oval():
    bad = json.loads(json.dumps(DOC))
    bad["rips"][0]["oval"]["in_front"] = 0.0                             # in the opening's own face
    assert any("in front of the opening" in p for p in D.problems(bad))
    bad = json.loads(json.dumps(DOC))
    bad["rips"][0]["oval"]["width"] = 4.0                                # a 4:4 oval over 3:4 art
    assert any("stretched" in p for p in D.problems(bad))
    bad = json.loads(json.dumps(DOC))
    bad["engine"]["rip_art"]["custom_model_data"] = "4180"
    assert any("custom_model_data" in p for p in D.problems(bad))


def test_world_probe_names_the_display_and_its_model_value():
    # since 2026-10-13 the oval probes are the generated dungeon_rips place's (the Night Shift's hand-written ones went with its
    # retired trail rip): one standing-rip probe carries the item and the model value
    probes = json.loads((ROOT / "data" / "world_probes.json").read_text(encoding="utf-8"))["places"]["dungeon_rips"]
    nbt = [p for p in probes if "custom_model_data" in p.get("entity", "")]
    assert len(nbt) == 1 and nbt[0]["count"] == 1 and "4180" in nbt[0]["entity"] and "amethyst_shard" in nbt[0]["entity"]


def test_no_portal_block_or_network_in_the_art_tools():
    for name in ("rip_art.py", "rip_pack.py"):
        src = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import|from)\s+(urllib|requests|http)", src, re.M), "art is drawn, never fetched"
