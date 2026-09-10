import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_region_dimensions_and_event_density():
    data = json.loads((ROOT / "world/source/region.json").read_text(encoding="utf-8"))
    world = data["world"]
    assert world["hex_flat_to_flat"] == 1250
    assert world["hex_flat_to_flat"] * world["prototype_columns"] == 2500
    assert world["hex_flat_to_flat"] * world["prototype_rows"] == 2500
    for cell in data["cells"]:
        events = [e for e in data["events"] if e["cell"] == cell["id"]]
        assert sum(e["size"] == "medium" for e in events) == 1
        assert 2 <= sum(e["size"] == "small" for e in events) <= 4


def test_generated_masks_are_deterministic(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "tools/generate_region.py"), "--output", str(tmp_path)], check=True)
    summary = json.loads((ROOT / "world/source/exp-009/generation-summary.json").read_text(encoding="utf-8"))
    for name, expected in summary["sha256_pixels"].items():
        actual = hashlib.sha256(Image.open(tmp_path / "masks" / name).tobytes()).hexdigest()
        assert actual == expected
        assert Image.open(tmp_path / "masks" / name).size == tuple(summary["dimensions_pixels"])
    actual_preview = hashlib.sha256(Image.open(tmp_path / "prototype-preview.png").tobytes()).hexdigest()
    assert actual_preview == summary["preview_sha256_pixels"]


def test_river_bed_is_below_water_level():
    config = json.loads((ROOT / "world/source/region.json").read_text(encoding="utf-8"))
    height = Image.open(ROOT / "world/source/exp-009/masks/heightmap.png")
    river = Image.open(ROOT / "world/source/exp-009/masks/river.png")
    wet_heights = [y for y, is_river in zip(height.getdata(), river.getdata()) if is_river]
    assert wet_heights
    assert max(wet_heights) < config["world"]["sea_level"]


def test_town_function_loads_and_releases_edited_chunks(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "tools/generate_region.py"), "--output", str(tmp_path)], check=True)
    commands = (tmp_path / "place-town.mcfunction").read_text(encoding="utf-8").splitlines()
    active = False
    placed = []
    for command in commands:
        if command.startswith("forceload add "):
            assert not active
            _, _, x1, z1, x2, z2 = command.split()
            chunks = (abs(int(x2) // 16 - int(x1) // 16) + 1) * (abs(int(z2) // 16 - int(z1) // 16) + 1)
            assert chunks <= 256
            active = True
        elif command.startswith("forceload remove "):
            assert active
            active = False
        elif command.startswith(("setblock ", "fill ", "place template ")):
            assert active, command
            if command.startswith("place template "):
                placed.append(command)
    assert not active
    assert len(placed) == 8


def test_event_scale_markers_are_visible_and_bounded(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "tools/generate_region.py"), "--output", str(tmp_path)], check=True)
    commands = (tmp_path / "place-scale-markers.mcfunction").read_text(encoding="utf-8").splitlines()
    summary = json.loads((tmp_path / "generation-summary.json").read_text(encoding="utf-8"))
    markers = summary["scale_test_markers"]
    marker = next(marker for marker in markers if marker["id"] == "d4-meadow-trial")

    assert len(markers) == 16
    assert {marker["id"] for marker in markers} == {
        event["id"] for event in json.loads((ROOT / "world/source/region.json").read_text(encoding="utf-8"))["events"]
    }
    assert marker["x"] == 930
    assert marker["z"] == 790
    assert marker["disposable"] is True
    assert sum(command.startswith("forceload add ") for command in commands) == 16
    assert sum(command.startswith("forceload remove ") for command in commands) == 16
    assert commands[-1].startswith("forceload remove ")
    assert marker["marker_style"] == "fenced_arena"
    assert not any(command.startswith("place template ") for command in commands)
    assert any(command == "execute positioned 930 80 790 run kill @e[type=cobblemon:npc,distance=..48]" for command in commands)
    assert any(command == f"setblock 930 {marker['y'] + 1} 774 minecraft:lantern" for command in commands)
    assert "# d4-berry-grove: reserved berry_grove (small)" in commands
    assert "# e5-cavern: reserved cavern_entrance (medium)" in commands
