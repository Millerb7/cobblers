#!/usr/bin/env python
"""Generate deterministic EXP-009 terrain masks, previews and placement commands."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "world/source/region.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dimensions(cfg: dict) -> tuple[int, int, int, int]:
    w = cfg["world"]
    width = w["hex_flat_to_flat"] * w["prototype_columns"]
    height = w["hex_flat_to_flat"] * w["prototype_rows"]
    bpp = w["blocks_per_pixel"]
    if width % bpp or height % bpp:
        raise ValueError("derived block dimensions must be divisible by blocks_per_pixel")
    return width, height, width // bpp, height // bpp


def make_arrays(cfg: dict):
    width, height, pw, ph = dimensions(cfg)
    seed = int(cfg["seed"])
    rng = np.random.default_rng(seed)
    x = (np.arange(pw) + 0.5) * width / pw
    z = (np.arange(ph) + 0.5) * height / ph
    xx, zz = np.meshgrid(x, z)

    # Smooth deterministic multi-frequency relief; no antialiased category masks.
    rolling = 5*np.sin(xx/155) + 4*np.cos(zz/190) + 2*np.sin((xx+zz)/83)
    noise = rng.normal(0, 1, (ph, pw))
    for _ in range(5):
        noise = (noise + np.roll(noise,1,0)+np.roll(noise,-1,0)+np.roll(noise,1,1)+np.roll(noise,-1,1))/5
    base = 82 + rolling + noise*2

    # A broad ridge rises through E5 and continues into D5, blocking long views.
    ridge_axis = 1840 + 0.12*(zz-1250)
    ridge = 82*np.exp(-((xx-ridge_axis)/350)**2) / (1+np.exp(-(zz-980)/180))
    foothill = 8/(1+np.exp(-(xx-1450)/180)) + 26/(1+np.exp(-(xx-1450)/180))/(1+np.exp(-(zz-1080)/180))

    # Sinuous north-south river with a broad valley and a narrow crossing near z=1500.
    river_x = 1110 + 130*np.sin(zz/350) + 45*np.sin(zz/91)
    dist = np.abs(xx-river_x)
    valley = 28*np.exp(-(dist/190)**2)
    river_half = 34 + 8*np.sin(zz/170)
    channel = dist <= river_half

    heights = base + foothill + ridge - valley
    heights[channel] = cfg["world"]["sea_level"] - 3
    heights = np.clip(np.rint(heights), cfg["world"]["minimum_height"], cfg["world"]["maximum_height"]).astype(np.uint8)
    river = heights < cfg["world"]["sea_level"]
    bank = (~river) & (dist <= river_half + 70)

    mountain = (heights >= 128) | ((xx > 1700) & (zz > 1400))
    forest_boundary = 1220 + 105*np.sin(zz/260) + 0.05*zz
    forest_south = 1430 + 115*np.sin(xx/330)
    forest_core = (xx > forest_boundary + 115) & (zz < forest_south - 70) & ~river & ~mountain
    forest_edge = (xx > forest_boundary - 75) & (zz < forest_south + 110) & ~forest_core & ~river & ~mountain
    plains = ~river & ~bank & ~mountain & ~forest_core
    land = ~river
    coast = bank

    # Categorical map values remain exact. Soft transitions are represented by bands.
    category = np.zeros((ph,pw),dtype=np.uint8)
    category[plains] = 1
    category[forest_edge] = 2
    category[forest_core] = 3
    category[mountain] = 4
    category[bank] = 5
    category[river] = 6
    transition = np.zeros((ph,pw),dtype=np.uint8)
    transition[forest_edge] = 85
    transition[(mountain) & (heights < 145)] = 170
    transition[bank] = 255
    return heights, {"land-water":land,"river":river,"forest":forest_core,"plains":plains,"mountain-rock":mountain,"beach-coast":coast}, category, transition


def sample_y(heights: np.ndarray, cfg: dict, x: int, z: int) -> int:
    width, height, pw, ph = dimensions(cfg)
    px = min(pw-1,max(0,int(x/width*pw)))
    pz = min(ph-1,max(0,int(z/height*ph)))
    return int(heights[pz,px])+1


def line_points(points):
    result=set()
    for (x1,z1),(x2,z2) in zip(points,points[1:]):
        steps=max(abs(x2-x1),abs(z2-z1))
        for i in range(steps+1):
            t=i/steps if steps else 0
            result.add((round(x1+(x2-x1)*t),round(z1+(z2-z1)*t)))
    return sorted(result)


def write_outputs(cfg: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    masks = out / "masks"; masks.mkdir(exist_ok=True)
    width, height, pw, ph = dimensions(cfg)
    heights, binary, category, transition = make_arrays(cfg)
    Image.fromarray(heights,"L").save(masks/"heightmap.png")
    for name, arr in binary.items(): Image.fromarray((arr.astype(np.uint8)*255),"L").save(masks/f"{name}.png")
    Image.fromarray(category,"L").save(masks/"terrain-categories.png")
    Image.fromarray(transition,"L").save(masks/"transition-bands.png")

    road_image = Image.new("L", (pw, ph), 0); road_draw = ImageDraw.Draw(road_image)
    for path in cfg["travel_paths"]:
        points=[(round(px/cfg["world"]["blocks_per_pixel"]),round(pz/cfg["world"]["blocks_per_pixel"])) for px,pz in path["points"]]
        road_draw.line(points, fill=255, width=max(1, round(7/cfg["world"]["blocks_per_pixel"])), joint="curve")
    road_image.save(masks/"roads-trails.png")
    event_image = Image.new("L", (pw, ph), 0); event_draw = ImageDraw.Draw(event_image)
    for event in cfg["events"]:
        ex=round(event["x"]/cfg["world"]["blocks_per_pixel"]); ez=round(event["z"]/cfg["world"]["blocks_per_pixel"])
        radius=round((48 if event["size"]=="medium" else 24)/cfg["world"]["blocks_per_pixel"])
        event_draw.ellipse((ex-radius,ez-radius,ex+radius,ez+radius), fill=255 if event["size"]=="medium" else 128)
    event_image.save(masks/"event-reservations.png")

    colours=np.array([[35,78,120],[126,174,86],[89,142,76],[42,91,57],[117,112,104],[211,193,142],[54,128,176]],dtype=np.uint8)
    preview=colours[category]
    shade=np.clip((heights.astype(float)-62)/122,0,1)[...,None]
    preview=np.clip(preview*(0.72+0.38*shade),0,255).astype(np.uint8)
    img=Image.fromarray(preview,"RGB").resize((1250,1250),Image.Resampling.NEAREST)
    draw=ImageDraw.Draw(img)
    for n in (625,): draw.line((n,0,n,1250),fill=(240,240,240),width=2); draw.line((0,n,1250,n),fill=(240,240,240),width=2)
    glyphs={
        "D":["1110","1001","1001","1001","1110"],
        "E":["1111","1000","1110","1000","1111"],
        "4":["1001","1001","1111","0001","0001"],
        "5":["1111","1000","1110","0001","1110"],
    }
    def pixel_label(label, x0, y0):
        cursor=x0
        for char in label:
            for gy,row in enumerate(glyphs[char]):
                for gx,on in enumerate(row):
                    if on=="1": draw.rectangle((cursor+gx*3,y0+gy*3,cursor+gx*3+2,y0+gy*3+2),fill="white")
            cursor += 15
    for c in cfg["cells"]: pixel_label(c["id"],c["column"]*625+18,c["row"]*625+16)
    for e in cfg["events"]:
        ex=int(e["x"]/2); ez=int(e["z"]/2); r=7 if e["size"]=="medium" else 4
        draw.rectangle((ex-r,ez-r,ex+r,ez+r),fill=(238,70,70),outline="white")
    s=cfg["settlement"]["center"]; draw.rectangle((s["x"]/2-8,s["z"]/2-8,s["x"]/2+8,s["z"]/2+8),fill=(255,216,70),outline="black")
    img.save(out/"prototype-preview.png")

    placements=[]
    commands=["# Generated by tools/generate_region.py; run after WorldPainter export.", "# Commands force-load only the disposable chunks they edit, then release them.", "# Build the five-block town road first."]
    def loaded_batch(batch, bounds):
        x1,z1,x2,z2=bounds
        commands.append(f"forceload add {x1} {z1} {x2} {z2}")
        commands.extend(batch)
        commands.append(f"forceload remove {x1} {z1} {x2} {z2}")
    main_route=next(p for p in cfg["travel_paths"] if p["id"]=="town-to-d5-center")
    road_blocks=set()
    for rx,rz in line_points(main_route["points"]):
        for offset in range(-2,3): road_blocks.add((rx,rz+offset))
    # A server command cannot edit unloaded chunks. Keep each road window well
    # below vanilla's 256 forced-chunk limit and release it immediately.
    for window in sorted({rx//224 for rx,_ in road_blocks}):
        points=sorted((rx,rz) for rx,rz in road_blocks if rx//224==window)
        road_commands=[f"setblock {rx} {sample_y(heights,cfg,rx,rz)-1} {rz} minecraft:dirt_path replace" for rx,rz in points]
        loaded_batch(road_commands,(min(x for x,_ in points)-16,min(z for _,z in points)-16,max(x for x,_ in points)+16,max(z for _,z in points)+16))
    plaza=cfg["settlement"]["plaza"]; plaza_y=sample_y(heights,cfg,cfg["settlement"]["center"]["x"],cfg["settlement"]["center"]["z"])
    loaded_batch([f"fill {plaza['min_x']} {plaza_y-1} {plaza['min_z']} {plaza['max_x']} {plaza_y-1} {plaza['max_z']} minecraft:dirt_path replace", f"fill {plaza['min_x']} {plaza_y} {plaza['min_z']} {plaza['max_x']} {plaza_y+2} {plaza['max_z']} minecraft:air replace"],(plaza["min_x"]-16,plaza["min_z"]-16,plaza["max_x"]+16,plaza["max_z"]+16))
    for p in cfg["settlement"]["placements"]:
        q=dict(p); q["y"]=sample_y(heights,cfg,p["x"],p["z"]); placements.append(q)
        placement_commands=[]
        if p["id"] != "town-well":
            x1,x2=p["x"]-32,p["x"]+63; z1,z2=p["z"]-32,p["z"]+63
            placement_commands.append(f"fill {x1} {q['y']-1} {z1} {x2} {q['y']-1} {z2} minecraft:grass_block replace")
            for y1 in range(q["y"],q["y"]+16,3): placement_commands.append(f"fill {x1} {y1} {z1} {x2} {min(y1+2,q['y']+15)} {z2} minecraft:air replace")
        else:
            x1,x2=p["x"]-32,p["x"]+63; z1,z2=p["z"]-32,p["z"]+63
        placement_commands.append(f"place template {p['structure_id']} {p['x']} {q['y']} {p['z']} {p['rotation']} {p['mirror']} 1.0 {cfg['seed']}")
        loaded_batch(placement_commands,(x1,z1,x2,z2))
    landmark=cfg["settlement"]["landmark"]
    ly=sample_y(heights,cfg,landmark["x"],landmark["z"])
    loaded_batch([f"setblock {landmark['x']} {ly} {landmark['z']} minecraft:lodestone", f"setblock {landmark['x']} {ly+1} {landmark['z']} minecraft:lantern"],(landmark["x"]-16,landmark["z"]-16,landmark["x"]+16,landmark["z"]+16))
    (out/"place-town.mcfunction").write_text("\n".join(commands)+"\n",encoding="utf-8")

    def length(points): return round(sum(math.dist(a,b) for a,b in zip(points,points[1:])),1)
    summary={"schema":"cobblers.region-output/1","seed":cfg["seed"],"required_versions":cfg["required_versions"],"dimensions_blocks":list(dimensions(cfg)[:2]),"dimensions_pixels":list(dimensions(cfg)[2:]),"height_range":[int(heights.min()),int(heights.max())],"sha256_pixels":{},"placements":placements,"travel_paths":[{"id":p["id"],"distance_blocks":length(p["points"]),"points":p["points"]} for p in cfg["travel_paths"]]}
    # Hash decoded pixels, not PNG bytes: encoder versions may choose different compression.
    for p in sorted(masks.glob("*.png")): summary["sha256_pixels"][p.name]=hashlib.sha256(Image.open(p).tobytes()).hexdigest()
    summary["preview_sha256_pixels"] = hashlib.sha256(Image.open(out/"prototype-preview.png").tobytes()).hexdigest()
    (out/"generation-summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--config",type=Path,default=DEFAULT_CONFIG); ap.add_argument("--output",type=Path,default=ROOT/"world/source/exp-009")
    a=ap.parse_args(); write_outputs(load(a.config),a.output); print(f"generated {a.output}"); return 0


if __name__ == "__main__": raise SystemExit(main())
