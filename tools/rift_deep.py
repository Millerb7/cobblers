#!/usr/bin/env python
"""The Windward Deep: a roofed cavern city carved under the Rift's floor.

The chamber, its rock shell, its three decks and their light. The buildings are town content and come after; this
makes the place they stand in. The region is the owner's own tracing, reproduced here from the annotated heightmap
whose sha256 data/rift_regions.json pins, so nothing depends on a file in a scratch directory.

Ground comes from the canonical heightmap, never from a world; `verify` reads a world only to check.

    python tools/rift_deep.py build  --source-root <root> [--server-dir <server>]
    python tools/rift_deep.py verify --world <stopped world copy>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

import function_limits as FL

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "rift_deep.json"
REGIONS = ROOT / "data" / "rift_regions.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_deep"
PLAN = ROOT / "derived" / "rift_deep" / "plan.json"
TILE = 64
PART = 3500

WORLD_READS = {"verify", "main"}

# what the rock over the chamber may be. Anything else there -- air above all -- means a cave met
# the roof and the Deep is open to the surface.
SOLID = ["minecraft:stone", "minecraft:deepslate", "minecraft:tuff", "minecraft:andesite",
         "minecraft:diorite", "minecraft:granite", "minecraft:dirt", "minecraft:gravel",
         "minecraft:coarse_dirt", "minecraft:clay", "minecraft:sand", "minecraft:sandstone",
         "legendarymonuments:distortion_deepslate", "legendarymonuments:distortion_stone"]


class DeepError(Exception):
    pass


def h3(x, y, z, salt):
    a = (np.asarray(x, np.int64) * 73856093) ^ (np.asarray(y, np.int64) * 19349663) \
        ^ (np.asarray(z, np.int64) * 83492791) ^ np.int64(salt * 2654435761)
    a &= np.int64(0x7FFFFFFF)
    a = (a ^ (a >> 15)) * np.int64(2246822519)
    a &= np.int64(0x7FFFFFFF)
    a = (a ^ (a >> 13)) * np.int64(3266489917)
    return a & np.int64(0x7FFFFFFF)


def unit(x, y, z, salt):
    return h3(x, y, z, salt) / float(0x7FFFFFFF)


def installed_blocks(server_dir):
    import glob
    import re
    import zipfile
    if not server_dir:
        return None
    import runtime_guard
    runtime_guard.require_lock("read the server's mod jars")
    mods = runtime_guard.check(Path(server_dir) / "mods", "read the mod jars in")
    ids = set()
    for jar in glob.glob(str(mods / "*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except (zipfile.BadZipFile, OSError):  # not a readable jar
            continue
        for n in z.namelist():
            m = re.match(r"assets/([^/]+)/blockstates/([^/]+)\.json$", n)
            if m:
                ids.add("%s:%s" % m.groups())
    return ids


def pick(block, fallback, have):
    return block if block.startswith("minecraft:") or have is None or block in have else fallback


def region_mask(region_id, source_root):
    """The owner's traced region, flood-filled from its seed on the annotated heightmap it pins."""
    from PIL import Image, ImageDraw
    doc = json.loads(REGIONS.read_text(encoding="utf-8"))
    src = doc["source"]
    name = src["file"].split(" ")[0]
    path = Path(source_root) / name
    if not path.is_file():
        raise DeepError("the annotated heightmap %s is not under the source root" % name)
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != src["sha256"]:
        raise DeepError("%s hashes to %s, not the %s data/rift_regions.json pins" % (name, got[:12],
                                                                                     src["sha256"][:12]))
    r = doc["regions"][region_id]
    x0, z0, x1, z1 = r["bbox"]
    pad = 80
    X0, Z0, X1, Z1 = x0 - pad, z0 - pad, x1 + pad, z1 + pad
    crop = np.asarray(Image.open(path).convert("RGB").crop((X0, Z0, X1 + 1, Z1 + 1))).astype(int)
    line = crop.max(axis=2) <= 20
    # .copy(): PIL floodfill is a silent no-op on an image backed by a read-only array
    b = Image.fromarray(np.where(line, 0, 255).astype(np.uint8)).copy()
    sx, sz = r["seed"]
    px, pz = sx - X0, sz - Z0
    for d in range(0, 60):
        if not line[pz, px + d]:
            px += d
            break
    ImageDraw.floodfill(b, (px, pz), 128)
    m = np.asarray(b) == 128
    n = int(m.sum())
    if not (0.8 * r["columns"] <= n <= 1.2 * r["columns"]):
        raise DeepError("the flood fill of %s gives %d columns, not the %d recorded: the outline has changed or "
                        "leaked" % (region_id, n, r["columns"]))
    return m, (X0, Z0, X1, Z1), n


def build(source_root, server_dir=None):
    import ground as G
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    have = installed_blocks(server_dir)
    mask, (X0, Z0, X1, Z1), n_cols = region_mask(spec["region"].split(",")[0], source_root)
    g = G.load(source_root)
    H = g.box(X0, Z0, X1, Z1)
    if H.shape != mask.shape:
        raise DeepError("the heightmap box %s and the mask %s disagree" % (H.shape, mask.shape))

    form = spec["form"]
    roof = form["roof"]
    shell_b = pick(form["shell"]["block"], form["shell"]["fallback"], have)
    deck = spec["deck"]
    deck_b = pick(deck["block"], deck["fallback"], have)
    edge_b = pick(deck["edge"], deck["edge_fallback"], have)
    light_b = pick(spec["light"]["block"], spec["light"]["fallback"], have)
    floor_y = spec["floor_y"]

    # distance from the chamber's edge, so the roof can dome and the decks can inset
    zz, xx = np.nonzero(mask)
    inside = np.zeros(mask.shape, np.int32)
    from collections import deque
    q = deque()
    for z, x in zip(zz.tolist(), xx.tolist()):
        if not (mask[z - 1, x] and mask[z + 1, x] and mask[z, x - 1] and mask[z, x + 1]):
            inside[z, x] = 1
            q.append((z, x))
    while q:
        z, x = q.popleft()
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nz, nx = z + dz, x + dx
            if 0 <= nz < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[nz, nx] and not inside[nz, nx]:
                inside[nz, nx] = inside[z, x] + 1
                q.append((nz, nx))
    far = float(inside.max())

    lines, checks, counts, roofs = [], [], {}, {}

    def count(k, v=1):
        counts[k] = counts.get(k, 0) + v

    # the chamber: carve from the floor up to a domed roof, clamped so it can never break the surface
    broke = 0
    for z, x in zip(zz.tolist(), xx.tolist()):
        wx, wz = x + X0, z + Z0
        f = min(1.0, inside[z, x] / max(1.0, far * 0.55))
        top = floor_y + int(roof["edge"] + (roof["centre"] - roof["edge"]) * (f ** (1.0 / roof["falloff"])))
        top += int(unit(wx, 0, wz, 71) * 5) - 2
        cap = int(H[z, x]) - roof["min_cover"]
        if top > cap:
            top = cap
            broke += 1
        if top <= floor_y:
            continue
        lines.append("fill %d %d %d %d %d %d minecraft:air" % (wx, floor_y + 1, wz, wx, top, wz))
        roofs[(z, x)] = top
        count("chamber columns")
        count("chamber blocks", top - floor_y)
        if unit(wx, 1, wz, 72) < 0.0006:
            checks.append((wx, floor_y + 2, wz, ["minecraft:air"], "chamber air"))
        # the rock just above the roof must still be rock. The shell closes the floor, not the ceiling, so a
        # natural cave meeting the roof would open the chamber to the surface without anything else noticing.
        if unit(wx, 2, wz, 74) < 0.0012:
            checks.append((wx, top + 3, wz, SOLID, "roof cover"))
    count("columns the roof was clamped to keep its cover", broke)

    # The shell, in every direction. The Displaced City's cavern seals over its roof and round its walls
    # (tools/cavern_plan.py, and build_audit reports voids as either); the Deep's first cut sealed only under its
    # floor, which left a cave meeting the roof or a wall free to open the chamber. Emitted first, before the carve.
    d = form["shell"]["depth"]
    shell_lines = []
    for z, x in zip(zz.tolist(), xx.tolist()):
        wx, wz = x + X0, z + Z0
        shell_lines.append("fill %d %d %d %d %d %d %s replace #cobblers:rift_void"
                           % (wx, floor_y - d, wz, wx, floor_y, wz, shell_b))
        shell_lines.append("fill %d %d %d %d %d %d %s replace #cobblers:rift_void"
                           % (wx, roofs[(z, x)] + 1, wz, wx, roofs[(z, x)] + d, wz, shell_b))
    # the walls: a ring `d` wide outside the chamber, from under its floor to over its tallest roof
    ring = set()
    for z, x in zip(zz.tolist(), xx.tolist()):
        for dz in range(-d, d + 1):
            for dx in range(-d, d + 1):
                nz, nx = z + dz, x + dx
                if 0 <= nz < mask.shape[0] and 0 <= nx < mask.shape[1] and not mask[nz, nx]:
                    ring.add((nz, nx))
    for z, x in sorted(ring):
        wx, wz = x + X0, z + Z0
        hi = min(int(H[z, x]) - 1, floor_y + roof["centre"] + d)
        if hi > floor_y - d:
            shell_lines.append("fill %d %d %d %d %d %d %s replace #cobblers:rift_void"
                               % (wx, floor_y - d, wz, wx, hi, wz, shell_b))
    lines[:0] = shell_lines
    count("shell fills under the floor and over the roof", 2 * int(mask.sum()))
    count("shell fills round the walls", len(ring))

    # the decks
    for lv in spec["levels"]:
        y, ins = lv["y"], lv["inset"]
        m = inside > ins
        lz, lx = np.nonzero(m & mask)
        edge = set()
        for z, x in zip(lz.tolist(), lx.tolist()):
            if not (m[z - 1, x] and m[z + 1, x] and m[z, x - 1] and m[z, x + 1]):
                edge.add((z, x))
        for z, x in zip(lz.tolist(), lx.tolist()):
            wx, wz = x + X0, z + Z0
            b = edge_b if (z, x) in edge else deck_b
            lines.append("fill %d %d %d %d %d %d %s" % (wx, y - deck["thickness"] + 1, wz, wx, y, wz, b))
            count("deck columns (%s)" % lv["name"])
            if wx % spec["light"]["every"] == 0 and wz % spec["light"]["every"] == 0:
                lines.append("setblock %d %d %d %s" % (wx, y, wz, light_b))
                count("deck lights")
                checks.append((wx, y, wz, [light_b], "deck light"))
            elif unit(wx, y, wz, 73) < 0.0015:
                checks.append((wx, y, wz, [b], "deck"))
    if not any(k.startswith("deck columns") for k in counts):
        raise DeepError("no deck was laid: the insets are larger than the chamber")

    # the lifts. The decks are 16 apart on purpose, so without these the Deep cannot be walked at all. An elevator
    # sits in the deck's own top surface: a player standing on it is carried to the deck above or below.
    lift = spec["lifts"]
    ys = [lv["y"] for lv in spec["levels"]]
    deepest = {lv["y"]: lv["inset"] for lv in spec["levels"]}
    banks, tries = [], 0
    top_inset = max(deepest.values())
    cand = [(int(z), int(x)) for z, x in zip(*np.nonzero((inside > top_inset + 4) & mask))]
    if not cand:
        raise DeepError("no column is inside every deck: the lifts would not reach the high deck")
    while len(banks) < lift["banks"] and tries < 4000:
        tries += 1
        z, x = cand[int(unit(tries, 0, 0, 75) * (len(cand) - 1))]
        if any(abs(x - bx) + abs(z - bz) < lift["apart"] for bz, bx in banks):
            continue
        banks.append((z, x))
    if len(banks) < 2:
        raise DeepError("only %d lift banks placed: the Deep would not be navigable" % len(banks))
    for z, x in banks:
        wx, wz = x + X0, z + Z0
        for i, y in enumerate(ys):
            for dx, target in ((0, ys[i + 1] if i + 1 < len(ys) else None),
                               (2, ys[i - 1] if i > 0 else None)):
                if target is None:
                    continue
                lines.append("setblock %d %d %d %s" % (wx + dx, y, wz, lift["block"]))
                lines.append('data merge block %d %d %d {yOffset:%d,requiredAdvancement:""}'
                             % (wx + dx, y, wz, target - y))
                count("lift blocks")
                checks.append((wx + dx, y, wz, [lift["block"]], "lift"))
    count("lift banks", len(banks))

    plan = {"lines": lines, "checks": checks, "counts": counts,
            "box": [X0, Z0, X1, Z1], "floor_y": floor_y, "columns": int(mask.sum())}
    return plan, spec


def write(plan):
    import shutil
    if OUT.exists():
        shutil.rmtree(OUT)
    fn = OUT / "data" / "cobblers" / "function" / "deep"
    fn.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48, "description": "Cobblers: the Windward Deep"}}, indent=2) + "\n",
        encoding="utf-8")
    tags = OUT / "data" / "cobblers" / "tags" / "block"
    tags.mkdir(parents=True)
    (tags / "rift_void.json").write_text(json.dumps(
        {"values": ["minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:water",
                    "minecraft:lava", "minecraft:bubble_column"]}, indent=2) + "\n", encoding="utf-8")
    tiles = {}
    for ln in plan["lines"]:
        t = ln.split()
        i = 3 if t[0] == "data" else 1          # `data merge block x y z {..}` puts its x at token 3
        tiles.setdefault((int(t[i]) // TILE, int(t[i + 2]) // TILE), []).append(ln)
    order = []
    for t in sorted(tiles):
        body = tiles[t]
        for k in range(0, len(body), PART):
            name = "deep_%d_%d%s" % (t[0], t[1], "" if k == 0 else "_%d" % (k // PART + 1))
            out = FL.ensure_loaded(["# Generated by tools/rift_deep.py: tile %d %d" % t] + body[k:k + PART])
            probs = FL.check_lines(out, name)
            if probs:
                raise DeepError("function %s would be refused: %s" % (name, probs[:3]))
            (fn / (name + ".mcfunction")).write_text("\n".join(out) + "\n", encoding="utf-8")
            order.append(name)
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps({k: v for k, v in plan.items() if k != "lines"}), encoding="utf-8")
    return order


def verify(world):
    import build_audit
    import runtime_guard
    runtime_guard.check(world, "read")
    if not PLAN.is_file():
        print("FAIL: no derived/rift_deep/plan.json: run the build first")
        return 1
    p = json.loads(PLAN.read_text(encoding="utf-8"))
    kinds = {c[4] for c in p["checks"]}
    need = {"chamber air", "deck", "deck light", "roof cover", "lift"}
    if not need <= kinds:
        print("FAIL: the plan checks %s, missing %s" % (sorted(kinds), sorted(need - kinds)))
        return 1
    W = build_audit.World(world)
    by, bad = {}, {}
    for x, y, z, allowed, what in p["checks"]:
        got = W.block(x, y, z)
        ok = got in allowed
        by.setdefault(what, [0, 0])[0 if ok else 1] += 1
        if not ok:
            bad.setdefault(what, []).append((x, y, z, got))
    for k in sorted(by):
        good, wrong = by[k]
        print("%-16s %7d of %7d as planned%s" % (k, good, good + wrong, ("   e.g. %s" % bad[k][:2]) if wrong else ""))
    total = sum(b for _, b in by.values())
    print("the Deep: %s" % ("clean" if total == 0 else "%d MISMATCHES" % total))
    return 0 if total == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "verify"))
    ap.add_argument("--source-root")
    ap.add_argument("--server-dir")
    ap.add_argument("--world")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        if not a.world:
            ap.error("verify needs --world")
        return verify(a.world)
    plan, spec = build(a.source_root, a.server_dir)
    order = write(plan)
    for k, v in sorted(plan["counts"].items()):
        print("  %-48s %9d" % (k, v))
    print("the Deep: %d functions, %d commands, floor y%d" % (len(order), len(plan["lines"]), plan["floor_y"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
