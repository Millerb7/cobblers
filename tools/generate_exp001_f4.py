#!/usr/bin/env python
"""Generate the deterministic EXP-001 F4 Pallet coast and placement function."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "world/source/exp-001/f4-region.json"
DEFAULT_OUTPUT = ROOT / "world/source/exp-001"
FUNCTION_OUTPUT = ROOT / (
    "modpack/datapacks/cobblers_campaign/data/cobblers/function/exp_001/f4/setup.mcfunction"
)
STRUCTURE_ROOT = ROOT / "modpack/datapacks/cobblers_campaign/data/cobblers/structure"


def read_nbt(path: Path) -> dict:
    raw = path.read_bytes()
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    stream = io.BytesIO(raw)

    def unpack(fmt: str):
        size = struct.calcsize(">" + fmt)
        return struct.unpack(">" + fmt, stream.read(size))[0]

    def string() -> str:
        return stream.read(unpack("H")).decode("utf-8")

    def payload(tag: int):
        if tag == 1:
            return unpack("b")
        if tag == 2:
            return unpack("h")
        if tag == 3:
            return unpack("i")
        if tag == 4:
            return unpack("q")
        if tag == 5:
            return unpack("f")
        if tag == 6:
            return unpack("d")
        if tag == 7:
            return stream.read(unpack("i"))
        if tag == 8:
            return string()
        if tag == 9:
            child, length = unpack("b"), unpack("i")
            if child == 0 and length == 0:
                return []
            return [payload(child) for _ in range(length)]
        if tag == 10:
            value = {}
            while True:
                child = unpack("b")
                if child == 0:
                    return value
                key = string()
                value[key] = payload(child)
        if tag == 11:
            return [unpack("i") for _ in range(unpack("i"))]
        if tag == 12:
            return [unpack("q") for _ in range(unpack("i"))]
        raise ValueError(f"unsupported NBT tag {tag}")

    if unpack("b") != 10:
        raise ValueError(f"{path} does not have a compound root")
    string()
    return payload(10)


def smooth_noise(shape: tuple[int, int], seed: int) -> np.ndarray:
    noise = np.random.default_rng(seed).normal(0, 1, shape)
    for _ in range(7):
        noise = (
            noise
            + np.roll(noise, 1, 0)
            + np.roll(noise, -1, 0)
            + np.roll(noise, 1, 1)
            + np.roll(noise, -1, 1)
        ) / 5
    return noise


def make_arrays(cfg: dict):
    world = cfg["world"]
    width, height = world["width"], world["height"]
    x = np.arange(width) + 0.5
    z = np.arange(height) + 0.5
    xx, zz = np.meshgrid(x, z)
    sea = world["sea_level"]
    noise = smooth_noise((height, width), cfg["seed"])

    # Broad, asymmetrical coast with a sheltered Pallet bay.
    coastline = (
        520
        + 34 * np.sin((xx + 80) / 100)
        + 52 * np.exp(-((xx - 555) / 155) ** 2)
        - 18 * np.exp(-((xx - 190) / 100) ** 2)
    )
    mainland = zz <= coastline
    base = 72 + 3 * np.sin(xx / 93) + 2 * np.cos(zz / 71) + noise * 2.2
    northeast_hills = 18 * np.exp(-(((xx - 835) / 190) ** 2 + ((zz - 170) / 180) ** 2))
    northwest_rise = 8 * np.exp(-(((xx - 180) / 230) ** 2 + ((zz - 130) / 210) ** 2))
    land_height = base + northeast_hills + northwest_rise

    # Keep Pallet's building district broad and walkable without flattening the
    # entire hex. This remains terrain source, not a post-export giant platform.
    town_r = np.sqrt(((xx - 575) / 210) ** 2 + ((zz - 385) / 150) ** 2)
    town_blend = np.clip(1 - town_r, 0, 1)
    land_height = land_height * (1 - 0.90 * town_blend) + 73 * (0.90 * town_blend)

    ocean_floor = 50 + 2 * np.sin(xx / 125) + 2 * np.cos(zz / 90) + noise
    heights = np.where(mainland, land_height, ocean_floor)
    island_defs = [
        (420, 675, 82, 61, 70),
        (790, 785, 68, 53, 68),
        (625, 955, 108, 82, 72),
    ]
    island_land = np.zeros_like(mainland)
    island_edge = np.zeros_like(mainland)
    for cx, cz, rx, rz, peak in island_defs:
        angle = np.arctan2((zz - cz) / rz, (xx - cx) / rx)
        q = (
            ((xx - cx) / rx) ** 2
            + ((zz - cz) / rz) ** 2
            + 0.10 * np.sin(angle * 5 + cx / 90)
            + 0.06 * np.sin(angle * 9 + cz / 80)
            + noise * 0.055
        )
        footprint = q <= 1
        profile = sea + 1 + (peak - sea - 1) * np.clip(1 - q, 0, 1) ** 0.55
        heights = np.where(footprint, np.maximum(heights, profile), heights)
        island_land |= footprint
        island_edge |= footprint & (q >= 0.63)

    land = mainland | island_land
    mainland_beach = mainland & (zz >= coastline - 24)
    beach = mainland_beach | island_edge
    rocky_field = ((xx - 840) / 205) ** 2 + ((zz - 150) / 205) ** 2 + noise * 0.12
    rocky = mainland & (rocky_field < 0.92) & (land_height >= 79)
    northwest_forest = ((xx - 105) / 390) ** 2 + ((zz - 125) / 350) ** 2 + noise * 0.18
    northeast_forest = ((xx - 925) / 270) ** 2 + ((zz - 285) / 330) ** 2 + noise * 0.16
    forest = mainland & ((northwest_forest < 1) | (northeast_forest < 1))
    forest &= ~rocky
    # Authored clearings around the abandoned house and north route.
    forest &= (((xx - 835) / 72) ** 2 + ((zz - 175) / 62) ** 2 > 1)
    forest &= np.abs(xx - (595 + 0.08 * (300 - zz))) > 30

    heights = np.clip(
        np.rint(heights), world["minimum_height"], world["maximum_height"]
    ).astype(np.uint8)
    category = np.full((height, width), 5, dtype=np.uint8)
    category[land] = 1
    category[forest] = 2
    category[rocky] = 3
    category[beach] = 4
    return heights, category, forest, land, beach, coastline


def sample_y(heights: np.ndarray, x: int, z: int) -> int:
    return int(heights[max(0, min(heights.shape[0] - 1, z)), max(0, min(heights.shape[1] - 1, x))]) + 1


def line_points(points: list[list[int]]) -> set[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    for (x1, z1), (x2, z2) in zip(points, points[1:]):
        steps = max(abs(x2 - x1), abs(z2 - z1))
        for i in range(steps + 1):
            t = i / steps if steps else 0
            result.add((round(x1 + (x2 - x1) * t), round(z1 + (z2 - z1) * t)))
    return result


def structure_path(resource_id: str) -> Path:
    namespace, relative = resource_id.split(":", 1)
    if namespace != "cobblers":
        raise ValueError(f"cannot inspect external template {resource_id}")
    return STRUCTURE_ROOT / f"{relative}.nbt"


def place_template(commands: list[str], placement: dict, y: int, seed: int) -> None:
    template = placement["template"]
    data = read_nbt(structure_path(template))
    x, z = placement["x"], placement["z"]
    sx, sy, sz = data["size"]
    commands.extend(
        [
            f"forceload add {x-12} {z-12} {x+sx+12} {z+sz+12}",
            f"fill {x-3} {y-1} {z-3} {x+sx+3} {y-1} {z+sz+3} minecraft:grass_block replace",
            f"fill {x-3} {y} {z-3} {x+sx+3} {y+sy+5} {z+sz+3} minecraft:air replace",
            f"place template {template} {x} {y} {z} none none 1.0 {seed}",
        ]
    )
    for block in data["blocks"]:
        state = data["palette"][block["state"]]["Name"]
        bx, by, bz = block["pos"]
        if state == "minecraft:jigsaw":
            final_state = block.get("nbt", {}).get("final_state", "minecraft:air")
            commands.append(f"setblock {x+bx} {y+by} {z+bz} {final_state}")
        loot = block.get("nbt", {}).get("LootTable", "")
        if loot.startswith("cobblemoncitytowns:"):
            commands.append(f"data remove block {x+bx} {y+by} {z+bz} LootTable")
            commands.append(f"data remove block {x+bx} {y+by} {z+bz} Items")
    commands.append(f"forceload remove {x-12} {z-12} {x+sx+12} {z+sz+12}")


def write_outputs(cfg: dict, output: Path, function_output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    masks = output / "masks"
    masks.mkdir(exist_ok=True)
    heights, category, forest, land, beach, coastline = make_arrays(cfg)
    Image.fromarray(heights, "L").save(masks / "heightmap.png")
    Image.fromarray(category, "L").save(masks / "terrain-categories.png")
    Image.fromarray((forest.astype(np.uint8) * 255), "L").save(masks / "forest.png")
    Image.fromarray((land.astype(np.uint8) * 255), "L").save(masks / "land-water.png")
    Image.fromarray((beach.astype(np.uint8) * 255), "L").save(masks / "beach.png")

    routes = Image.new("L", heights.shape[::-1], 0)
    route_draw = ImageDraw.Draw(routes)
    for route in cfg["routes"]:
        route_draw.line([tuple(point) for point in route["points"]], fill=255, width=7, joint="curve")
    routes.save(masks / "routes.png")
    events = Image.new("L", heights.shape[::-1], 0)
    event_draw = ImageDraw.Draw(events)
    for event in cfg["events"]:
        event_draw.ellipse((event["x"] - 14, event["z"] - 14, event["x"] + 14, event["z"] + 14), fill=255)
    events.save(masks / "events.png")

    colours = np.array(
        [[0, 0, 0], [116, 165, 82], [50, 100, 55], [112, 108, 102], [217, 196, 139], [48, 105, 153]],
        dtype=np.uint8,
    )
    preview = colours[category]
    shade = np.clip((heights.astype(float) - 47) / 57, 0, 1)[..., None]
    preview = np.clip(preview * (0.76 + 0.30 * shade), 0, 255).astype(np.uint8)
    image = Image.fromarray(preview, "RGB")
    draw = ImageDraw.Draw(image)
    for route in cfg["routes"]:
        draw.line([tuple(point) for point in route["points"]], fill=(196, 151, 86), width=5)
    for placement in cfg["town"]["placements"]:
        draw.rectangle((placement["x"] - 4, placement["z"] - 4, placement["x"] + 8, placement["z"] + 8), fill=(245, 224, 111), outline=(55, 43, 31))
    for event in cfg["events"]:
        draw.ellipse((event["x"] - 7, event["z"] - 7, event["x"] + 7, event["z"] + 7), fill=(213, 68, 68), outline="white")
    image.save(output / "f4-preview.png")

    commands = [
        "# Generated by tools/generate_exp001_f4.py for the disposable F4 world.",
        "# Donor templates are copied under cobblers:; donor natural worldgen is not enabled.",
    ]
    road_points: set[tuple[int, int]] = set()
    for route in cfg["routes"]:
        for x, z in line_points(route["points"]):
            for offset in range(-2, 3):
                road_points.add((x + offset, z))
    for window in sorted({(x // 160, z // 160) for x, z in road_points}):
        points = sorted((x, z) for x, z in road_points if (x // 160, z // 160) == window)
        commands.append(f"forceload add {min(x for x,_ in points)-8} {min(z for _,z in points)-8} {max(x for x,_ in points)+8} {max(z for _,z in points)+8}")
        commands.extend(f"setblock {x} {sample_y(heights,x,z)-1} {z} minecraft:dirt_path replace" for x, z in points)
        commands.append(f"forceload remove {min(x for x,_ in points)-8} {min(z for _,z in points)-8} {max(x for x,_ in points)+8} {max(z for _,z in points)+8}")

    for placement in cfg["town"]["placements"]:
        place_template(commands, placement, sample_y(heights, placement["x"], placement["z"]), cfg["seed"])

    event_by_id = {event["id"]: event for event in cfg["events"]}
    fish = event_by_id["abandoned-fish-hut"]
    fish_y = sample_y(heights, fish["x"], fish["z"])
    place_template(commands, fish, fish_y, cfg["seed"])
    commands.extend([
        f"fill {fish['x']-2} 63 {fish['z']+7} {fish['x']+3} 63 {fish['z']+38} minecraft:oak_planks",
        f"fill {fish['x']-2} 62 {fish['z']+12} {fish['x']-2} 58 {fish['z']+38} minecraft:oak_log",
        f"fill {fish['x']+3} 62 {fish['z']+12} {fish['x']+3} 58 {fish['z']+38} minecraft:oak_log",
    ])
    abandoned = event_by_id["abandoned-house"]
    abandoned_y = sample_y(heights, abandoned["x"], abandoned["z"])
    place_template(commands, abandoned, abandoned_y, cfg["seed"])
    commands.extend([
        f"fill {abandoned['x']+5} {abandoned_y+5} {abandoned['z']+4} {abandoned['x']+8} {abandoned_y+8} {abandoned['z']+7} minecraft:air",
        f"setblock {abandoned['x']-3} {abandoned_y} {abandoned['z']+2} minecraft:cobweb",
    ])
    relic = event_by_id["relic-island"]
    commands.append(f"execute positioned {relic['x']} 62 {relic['z']} run function cobblers:exp_001/f4_relic_island/place")
    boat = event_by_id["broken-boat"]
    commands.extend([
        f"forceload add {boat['x']-20} {boat['z']-20} {boat['x']+20} {boat['z']+20}",
        f"fill {boat['x']-7} 64 {boat['z']-2} {boat['x']+7} 64 {boat['z']+2} minecraft:spruce_planks",
        f"fill {boat['x']-5} 65 {boat['z']-3} {boat['x']+5} 65 {boat['z']-3} minecraft:spruce_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]",
        f"fill {boat['x']-5} 65 {boat['z']+3} {boat['x']+5} 65 {boat['z']+3} minecraft:spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]",
        f"fill {boat['x']+2} 65 {boat['z']-1} {boat['x']+7} 67 {boat['z']+1} minecraft:air",
        f"setblock {boat['x']-1} 65 {boat['z']} minecraft:barrel[facing=up,open=false]",
        f"forceload remove {boat['x']-20} {boat['z']-20} {boat['x']+20} {boat['z']+20}",
    ])
    spawn = cfg["spawn"]
    spawn_y = sample_y(heights, spawn["x"], spawn["z"])
    commands.extend([
        f"setworldspawn {spawn['x']} {spawn_y} {spawn['z']}",
        "gamerule spawnRadius 0",
        f"tellraw @a {{\"text\":\"EXP-001 F4 Pallet prototype is ready. Spawn: {spawn['x']} {spawn_y} {spawn['z']}\",\"color\":\"aqua\"}}",
    ])
    function_output.parent.mkdir(parents=True, exist_ok=True)
    function_output.write_text("\n".join(commands) + "\n", encoding="utf-8")

    summary = {
        "schema": "cobblers.exp001-f4-output/1",
        "seed": cfg["seed"],
        "dimensions": [cfg["world"]["width"], cfg["world"]["height"]],
        "height_range": [int(heights.min()), int(heights.max())],
        "sea_level": cfg["world"]["sea_level"],
        "spawn": {**spawn, "y": spawn_y},
        "town_placements": [
            {**p, "y": sample_y(heights, p["x"], p["z"])} for p in cfg["town"]["placements"]
        ],
        "events": [
            {**e, "y": sample_y(heights, e["x"], e["z"])} for e in cfg["events"]
        ],
        "sha256_pixels": {
            path.name: hashlib.sha256(Image.open(path).tobytes()).hexdigest()
            for path in sorted(masks.glob("*.png"))
        },
        "setup_function_sha256": hashlib.sha256(function_output.read_bytes()).hexdigest(),
    }
    (output / "generation-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--function-output", type=Path, default=FUNCTION_OUTPUT)
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    write_outputs(cfg, args.output, args.function_output)
    print(f"generated {args.output} and {args.function_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
