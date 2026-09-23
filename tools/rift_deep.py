#!/usr/bin/env python
"""The Windward Deep: an open pit sunk into the Rift floor, terraced in five rings.

The pit, its wall shell, the five treads the city stands on, their lifts and their light. The buildings are town
content and come after; this makes the place they stand in. Schema 1 built a sealed cavern here, on the reasoning
that 83 blocks down has ground overhead; that was circular -- the ground is only overhead if the pit is not dug
through it -- and the Deep must read as the Rift's deepest point, not as a second Displaced City. The region is the owner's own tracing, reproduced here from the annotated heightmap
whose sha256 data/rift_regions.json pins, so nothing depends on a file in a scratch directory.

Ground comes from the canonical heightmap, never from a world; `verify` reads a world only to check.

    python tools/rift_deep.py build  --source-root <root> [--server-dir <server>]
    python tools/rift_deep.py verify --world <stopped world copy>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
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


def fill_holes(m):
    """Close every hole inside the mask.

    The owner's annotation writes each region's NAME across it in the same black the outlines use, so the flood
    fill stops at the letters and they survive as islands. Carved, that left "the deep (town)" standing in rock in
    the middle of the chamber (found on the owner's own map, 2026-09-22; 18,285 columns of lettering across the
    eleven regions). Anything enclosed by the region is part of it: flood the outside from the border, and
    whatever the outside cannot reach is a hole.
    """
    from collections import deque
    h, w = m.shape
    outside = np.zeros_like(m)
    q = deque()
    for i in range(w):
        for z in (0, h - 1):
            if not m[z, i] and not outside[z, i]:
                outside[z, i] = True
                q.append((z, i))
    for j in range(h):
        for x in (0, w - 1):
            if not m[j, x] and not outside[j, x]:
                outside[j, x] = True
                q.append((j, x))
    while q:
        z, x = q.popleft()
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nz, nx = z + dz, x + dx
            if 0 <= nz < h and 0 <= nx < w and not m[nz, nx] and not outside[nz, nx]:
                outside[nz, nx] = True
                q.append((nz, nx))
    return m | ~outside


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
    m = fill_holes(m)
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

    light_b = pick(spec["light"]["block"], spec["light"]["fallback"], have)
    floor_y = spec["floor_y"]

    # distance from the pit's edge, which is what puts each column in its ring
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

    lines, checks, counts = [], [], {}

    def count(k, v=1):
        counts[k] = counts.get(k, 0) + v

    # The pit: five rings stepping down to the floor, every column open to the sky above its own tread.
    rings = spec["rings"]
    treads, W = rings["treads"], rings["width"]
    tread = spec["tread"]
    tread_b = pick(tread["block"], tread["fallback"], have)
    edge_b = pick(tread["edge"], tread["edge_fallback"], have)
    restore_b = pick(spec["restore"]["block"], spec["restore"]["fallback"], have)
    d = spec["shell"]["depth"]

    # The sheer side: towards the tunnel the pit takes ring 0's street and then falls away in one face to the
    # floor, instead of stepping all five rings round. It gives the tunnel a back wall to come out of, and stops
    # the rings wrapping the pit like a stadium (owner, 2026-09-23).
    sheer = rings.get("sheer_side")
    cz_, cx_ = float(zz.mean()), float(xx.mean())
    toward = None
    if sheer:
        tb = json.loads(REGIONS.read_text(encoding="utf-8"))["regions"][sheer["toward"]]["bbox"]
        tx, tz = (tb[0] + tb[2]) / 2.0 - X0, (tb[1] + tb[3]) / 2.0 - Z0
        toward = math.atan2(tx - cx_, tz - cz_)

    ring_of, tread_of = {}, {}
    n_sheer = 0
    for z, x in zip(zz.tolist(), xx.tolist()):
        k = min(len(treads) - 1, int(inside[z, x]) // W)
        if toward is not None and k >= sheer["keeps_rings"]:
            a = math.atan2(x - cx_, z - cz_) - toward
            a = (a + math.pi) % (2 * math.pi) - math.pi
            if abs(math.degrees(a)) <= sheer["half_angle_degrees"]:
                k = len(treads) - 1          # straight to the floor: no terraces on this side
                n_sheer += 1
        ring_of[(z, x)] = k
        tread_of[(z, x)] = treads[k]
    count("columns on the sheer side, dropped straight to the floor", n_sheer)

    # 1. everything under a tread is rock. Schema 1's sealed chamber reached y22-52, which in the outer rings is
    #    below the new tread, so without this each street would be a shelf over that void.
    for z, x in zip(zz.tolist(), xx.tolist()):
        wx, wz = x + X0, z + Z0
        lines.append("fill %d %d %d %d %d %d %s replace #cobblers:rift_void"
                     % (wx, floor_y - d, wz, wx, tread_of[(z, x)] - 1, wz, restore_b))
    count("columns refilled under their tread", int(mask.sum()))

    # 2. the tread, with a margin of bare rock at the back against its riser
    margin = tread["rock_margin"]
    for z, x in zip(zz.tolist(), xx.tolist()):
        wx, wz = x + X0, z + Z0
        k, ty = ring_of[(z, x)], tread_of[(z, x)]
        within = int(inside[z, x]) - k * W
        if within < margin:
            continue
        b_ = edge_b if (k == len(treads) - 1 or within >= W - margin) else tread_b
        lines.append("fill %d %d %d %d %d %d %s" % (wx, ty - tread["thickness"] + 1, wz, wx, ty, wz, b_))
        count("tread columns (ring %d, y%d)" % (k, ty))
        if wx % spec["light"]["every"] == 0 and wz % spec["light"]["every"] == 0:
            lines.append("setblock %d %d %d %s" % (wx, ty, wz, light_b))
            count("tread lights")
            checks.append((wx, ty, wz, [light_b], "tread light"))
        elif unit(wx, ty, wz, 73) < 0.0012:
            checks.append((wx, ty, wz, [b_], "tread"))

    # 3. open it to the sky: everything above a tread comes out, all the way past the surface
    for z, x in zip(zz.tolist(), xx.tolist()):
        wx, wz = x + X0, z + Z0
        ty, surf = tread_of[(z, x)], int(H[z, x])
        if surf <= ty:
            continue
        lines.append("fill %d %d %d %d %d %d minecraft:air" % (wx, ty + 1, wz, wx, surf + 2, wz))
        count("pit columns")
        count("pit blocks", surf + 2 - ty)
        if unit(wx, 1, wz, 72) < 0.0006:
            checks.append((wx, ty + 2, wz, ["minecraft:air"], "pit air"))
        # Open to the sky. This replaces schema 1's roof-cover check, which existed only because there was a roof:
        # an open pit that is not open is the whole failure, so the column is checked at the old ground line.
        if unit(wx, 2, wz, 74) < 0.0012:
            checks.append((wx, surf, wz, ["minecraft:air"], "open to the sky"))

    # The wall shell: a ring of rock outside the pit, from under the floor to the surface, so no cave or aquifer
    # opens into a wall. There is no roof to seal -- the pit is open, which is the point.
    shell_b = pick(spec["shell"]["block"], spec["shell"]["fallback"], have)
    ringcols = set()
    for z, x in zip(zz.tolist(), xx.tolist()):
        for dz in range(-d, d + 1):
            for dx in range(-d, d + 1):
                nz, nx = z + dz, x + dx
                if 0 <= nz < mask.shape[0] and 0 <= nx < mask.shape[1] and not mask[nz, nx]:
                    ringcols.add((nz, nx))
    shell_lines = []
    for z, x in sorted(ringcols):
        wx, wz = x + X0, z + Z0
        hi = int(H[z, x]) - 1
        if hi > floor_y - d:
            shell_lines.append("fill %d %d %d %d %d %d %s replace #cobblers:rift_void"
                               % (wx, floor_y - d, wz, wx, hi, wz, shell_b))
    lines[:0] = shell_lines
    count("shell fills round the walls", len(ringcols))

    if not any(k.startswith("tread columns") for k in counts):
        raise DeepError("no tread was laid: the rings are wider than the pit")

    # The lifts, at the risers. A 17-block riser cannot be climbed, so these are the only way between rings and
    # so the only way down: the tunnel still matters. A pair straddles each boundary -- one on the lower tread
    # going up, one on the upper tread going down -- because a single column belongs to exactly one ring.
    lift = spec["lifts"]
    per = max(2, lift["banks"] // (len(treads) - 1))
    n_banks = 0
    for k in range(len(treads) - 1):
        stepped = np.zeros(mask.shape, bool)
        for (z_, x_), kk in ring_of.items():
            stepped[z_, x_] = (kk == int(inside[z_, x_]) // W)      # false wherever the sheer side flattened it
        edge_in = (inside >= (k + 1) * W) & (inside < (k + 1) * W + 2) & mask & stepped
        edge_out = (inside >= (k + 1) * W - 2) & (inside < (k + 1) * W) & mask & stepped
        ci = [(int(z), int(x)) for z, x in zip(*np.nonzero(edge_in))]
        co = [(int(z), int(x)) for z, x in zip(*np.nonzero(edge_out))]
        if not ci or not co:
            raise DeepError("ring boundary %d has no columns either side: its lift would go nowhere" % k)
        placed, tries = [], 0
        while len(placed) < per and tries < 3000:
            tries += 1
            z, x = ci[int(unit(tries, k, 0, 75) * (len(ci) - 1))]
            if any(abs(x - bx) + abs(z - bz) < lift["apart"] for bz, bx in placed):
                continue
            near = min(co, key=lambda c: abs(c[0] - z) + abs(c[1] - x))
            if abs(near[0] - z) + abs(near[1] - x) > 6:
                continue
            placed.append((z, x))
            n_banks += 1
            # on the lower tread, going up; on the upper tread, going down
            for (cz_, cx_), y, target in ((( z, x), treads[k + 1], treads[k]),
                                          (near, treads[k], treads[k + 1])):
                wx, wz = cx_ + X0, cz_ + Z0
                lines.append("setblock %d %d %d %s" % (wx, y, wz, lift["block"]))
                lines.append('data merge block %d %d %d {yOffset:%d,requiredAdvancement:""}'
                             % (wx, y, wz, target - y))
                count("lift blocks")
                checks.append((wx, y, wz, [lift["block"]], "lift"))
        if not placed:
            raise DeepError("no lift placed at ring boundary %d: that ring would be unreachable" % k)
    count("lift pairs", n_banks)

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
    need = {"pit air", "tread", "tread light", "open to the sky", "lift"}
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
