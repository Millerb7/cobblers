#!/usr/bin/env python
"""Pictures of the long mine networks: one top-down PNG of each network (drifts coloured by level, adits, stopes, shafts,
inclines, the towns round it, a scale bar) and one of the whole eastern half showing where they are.

Reads derived/mine_networks/plan.json (python tools/mine_networks.py build writes it) and the canonical heightmap
(tools/ground.py) for the relief; nothing else. Written under docs/world-building/ (the repository's place for world
maps), as MINE_NETWORKS_<id>.png and MINE_NETWORKS_EAST.png.

  python tools/mine_networks_map.py [--out docs/world-building]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ground as G   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "derived" / "mine_networks" / "plan.json"
LEVEL_COLOURS = [(230, 57, 70), (244, 162, 97), (233, 196, 106), (138, 177, 125), (42, 157, 143), (38, 70, 83), (131, 56, 236), (255, 0, 110)]
NET_COLOURS = [(230, 57, 70), (42, 157, 143), (131, 56, 236)]
SEA = 62


def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def relief(H, step=1):
    """RGB uint8 relief of a ground raster: sea blue, land shaded from the north-west."""
    z = H.astype(np.float32)
    gy, gx = np.gradient(z)
    shade = np.clip(0.62 + (-gx - gy) * 0.09, 0.25, 1.0)
    t = np.clip((z - SEA) / 160.0, 0, 1)
    land = np.stack([120 + 90 * t, 150 + 50 * t, 100 + 80 * t], axis=-1)
    img = land * shade[..., None]
    sea = z <= SEA
    deep = np.clip((SEA - z) / 40.0, 0, 1)
    img[sea] = np.stack([70 - 40 * deep, 120 - 50 * deep, 175 - 40 * deep], axis=-1)[sea]
    return np.clip(img, 0, 255).astype(np.uint8)


def text(d, xy, s, f, fill=(255, 255, 255), edge=(20, 20, 20)):
    x, y = xy
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if dx or dz:
                d.text((x + dx, y + dz), s, font=f, fill=edge)
    d.text(xy, s, font=f, fill=fill)


def towns():
    doc = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))
    out = []
    for t in doc["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is not None:
            out.append((t["id"], f["min_x"], f["min_z"], f["max_x"], f["max_z"]))
    return out


def scale_bar(d, x, y, per_px, f):
    for blocks in (100, 500):
        w = int(blocks / per_px)
        d.rectangle([x, y, x + w, y + 6], fill=(255, 255, 255), outline=(20, 20, 20))
        d.rectangle([x, y, x + w // 2, y + 6], fill=(20, 20, 20))
        text(d, (x + w + 6, y - 4), "%d blocks" % blocks, f)
        y += 20
    return y


def draw_network(net_id, net, out_path, g):
    runs = net["runs"]
    xs = [r["x"] for r in runs] + [r["x"] + r["dx"] * r["n"] for r in runs]
    zs = [r["z"] for r in runs] + [r["z"] + r["dz"] * r["n"] for r in runs]
    for s in net["stopes"]:
        xs += [s["bounds"][0], s["bounds"][2]]
        zs += [s["bounds"][1], s["bounds"][3]]
    x0, x1, z0, z1 = min(xs) - 120, max(xs) + 300, min(zs) - 120, max(zs) + 120
    H = g.box(x0, z0, x1, z1)
    rgb = relief(H)
    img = Image.fromarray(rgb, "RGB").convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    f = font(14)
    fb = font(20)

    def P(x, z):
        return (x - x0, z - z0)

    for t in towns():
        if t[3] < x0 or t[1] > x1 or t[4] < z0 or t[2] > z1:
            continue
        d.rectangle([P(t[1], t[2]), P(t[3], t[4])], outline=(25, 90, 200, 255), fill=(25, 90, 200, 70), width=2)
        text(d, (P(t[1], t[2])[0] + 3, P(t[1], t[2])[1] + 3), t[0], f, (190, 220, 255))
    nlev = len(net["levels"])
    for lev in range(nlev, 0, -1):
        col = LEVEL_COLOURS[(lev - 1) % len(LEVEL_COLOURS)] + (255,)
        for r in runs:
            if r["level"] != lev:
                continue
            a = P(r["x"], r["z"])
            b = P(r["x"] + r["dx"] * r["n"], r["z"] + r["dz"] * r["n"])
            d.line([a, b], fill=col, width=3 if r["kind"] in ("adit", "main") else 2)
        for s in net["stopes"]:
            if s["level"] == lev:
                bx0, bz0, bx1, bz1 = s["bounds"]
                d.rectangle([P(bx0, bz0), P(bx1, bz1)], fill=col[:3] + (200,), outline=(0, 0, 0, 255))
        for inc in net["inclines"]:
            if inc["level"] == lev:
                a = P(inc["x"], inc["z"])
                b = P(inc["x"] + inc["dx"] * inc["steps"], inc["z"] + inc["dz"] * inc["steps"])
                d.line([a, b], fill=(0, 0, 0, 255), width=5)
                d.line([a, b], fill=col, width=3)
                d.ellipse([b[0] - 4, b[1] - 4, b[0] + 4, b[1] + 4], fill=(0, 0, 0, 255))
        for sh in net["shafts"]:
            if sh["level"] == lev:
                a = P(sh["x"], sh["z"])
                d.rectangle([a[0] - 4, a[1] - 4, a[0] + 4, a[1] + 4], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    for a in net["adits"]:
        px, pz = P(*a["portal"])
        d.polygon([(px, pz - 12), (px - 9, pz + 8), (px + 9, pz + 8)], fill=(255, 40, 40, 255), outline=(255, 255, 255, 255))
        text(d, (px + 12, pz - 10), "adit %s (%d, %d)" % (a["id"].split("_")[-1], a["portal"][0], a["portal"][1]), f)
    # the map, scale bar and a header band with the legend above it
    w, h = img.size
    scale_bar(d, 20, h - 60, 1.0, f)
    text(d, (w - 330, h - 24), "north up, 1 pixel = 1 block, x%d..%d z%d..%d" % (x0, x1, z0, z1), f)
    band = 70 + 20 * ((nlev + 1) // 2)
    canvas = Image.new("RGB", (w, h + band), (15, 15, 20))
    canvas.paste(img.convert("RGB"), (0, band))
    d = ImageDraw.Draw(canvas)
    pad = 14
    d.text((pad, 8), net["name"], font=fb, fill=(255, 255, 255))
    d.text((pad, 36), "%d blocks of drift, %d levels, %d stopes, %d inclines, %d ladder shafts; adit %d blocks from %s" % (
        net["drift_length_blocks"], nlev, len(net["stopes"]), len(net["inclines"]), len(net["shafts"]),
        net["nearest_town_distance"], net["nearest_town"]), font=f, fill=(230, 230, 230))
    for lev in range(1, nlev + 1):
        col = LEVEL_COLOURS[(lev - 1) % len(LEVEL_COLOURS)]
        yy = 62 + 20 * ((lev - 1) // 2)
        xx = pad + ((lev - 1) % 2) * 360
        d.rectangle([xx, yy + 4, xx + 30, yy + 12], fill=col)
        d.text((xx + 40, yy), "level %d  floor y%d  %d blocks" % (lev, net["levels"][lev - 1], net["drift_length_by_level"].get(str(lev), 0)),
               font=f, fill=(230, 230, 230))
    d.text((pad + 740, 62), "white square: ladder shaft", font=f, fill=(230, 230, 230))
    d.text((pad + 740, 82), "black line + dot: incline (down)", font=f, fill=(230, 230, 230))
    d.text((pad + 740, 102), "large square: stope (chamber)", font=f, fill=(230, 230, 230))
    d.text((pad + 740, 122), "red triangle: adit    blue: town", font=f, fill=(230, 230, 230))
    canvas.save(out_path, optimize=True)


def draw_overview(plan, out_path, g):
    X0, X1, Z0, Z1 = 4096, 8191, 0, 8191
    S = 4
    H = g.box(X0, Z0, X1, Z1)
    Hs = H[::S, ::S]
    rgb = relief(Hs)
    img = Image.fromarray(rgb, "RGB").convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    f = font(15)
    fb = font(22)

    def P(x, z):
        return ((x - X0) / S, (z - Z0) / S)

    # the cell grid: columns 5-8, rows A-H
    for c in range(0, 5):
        x = X0 + c * 1024
        d.line([P(x, Z0), P(x, Z1)], fill=(255, 255, 255, 90), width=1)
    for r in range(0, 9):
        z = Z0 + r * 1024
        d.line([P(X0, z), P(X1, z)], fill=(255, 255, 255, 90), width=1)
    for ci, col in enumerate("5678"):
        for ri, row in enumerate("ABCDEFGH"):
            text(d, P(X0 + ci * 1024 + 14, Z0 + ri * 1024 + 10), row + col, f, (255, 255, 255, 200))
    for t in towns():
        if t[1] < X0:
            continue
        a, b = P(t[1], t[2]), P(t[3], t[4])
        d.rectangle([a, (max(b[0], a[0] + 5), max(b[1], a[1] + 5))], outline=(25, 90, 200, 255), fill=(25, 90, 200, 140))
        text(d, (a[0] + 7, a[1] - 7), t[0].replace("_town", ""), f, (200, 225, 255))
    for i, (nid, net) in enumerate(sorted(plan["networks"].items())):
        col = NET_COLOURS[i % len(NET_COLOURS)]
        for r in net["runs"]:
            a = P(r["x"], r["z"])
            b = P(r["x"] + r["dx"] * r["n"], r["z"] + r["dz"] * r["n"])
            d.line([a, b], fill=col + (255,), width=2)
        xs = [r["x"] for r in net["runs"]] + [r["x"] + r["dx"] * r["n"] for r in net["runs"]]
        zs = [r["z"] for r in net["runs"]] + [r["z"] + r["dz"] * r["n"] for r in net["runs"]]
        a, b = P(min(xs) - 40, min(zs) - 40), P(max(xs) + 40, max(zs) + 40)
        d.rectangle([a, b], outline=col + (255,), width=2)
        for ad in net["adits"]:
            px, pz = P(*ad["portal"])
            d.polygon([(px, pz - 10), (px - 8, pz + 7), (px + 8, pz + 7)], fill=(255, 40, 40, 255), outline=(255, 255, 255, 255))
        text(d, (a[0] + 4, a[1] - 24), "%d  %s  (%d blocks)" % (i + 1, net["name"], net["drift_length_blocks"]), fb, (255, 255, 255), tuple(int(c * 0.5) for c in col))
    w, h = img.size
    d.rectangle([0, 0, 470, 62], fill=(15, 15, 20, 215))
    text(d, (10, 6), "Long mine networks, eastern half (x4096-8191)", fb)
    text(d, (10, 36), "red triangle: adit    blue: town    white grid: 1,024-block cells", f)
    scale_bar(d, 20, h - 60, S, f)
    text(d, (w - 330, h - 24), "north up, 1 pixel = %d blocks" % S, f)
    img.convert("RGB").save(out_path, optimize=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(ROOT / "docs" / "world-building"))
    p.add_argument("--plan", default=str(PLAN))
    p.add_argument("--source-root")
    a = p.parse_args(argv)
    if not Path(a.plan).is_file():
        raise SystemExit("no %s: run python tools/mine_networks.py build first" % a.plan)
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    g = G.Ground(a.source_root)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for nid, net in sorted(plan["networks"].items()):
        draw_network(nid, net, out / ("MINE_NETWORKS_%s.png" % nid.replace("mn_", "").upper()), g)
    draw_overview(plan, out / "MINE_NETWORKS_EAST.png", g)
    for f in sorted(out.glob("MINE_NETWORKS_*.png")):
        print(f.relative_to(ROOT) if f.is_relative_to(ROOT) else f, f.stat().st_size // 1024, "KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
