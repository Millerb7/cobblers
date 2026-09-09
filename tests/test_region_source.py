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
