#!/usr/bin/env python
"""Victory Road: the climb out of the wound, as a labyrinth in stone.

Four flat galleries stacked over one another, joined by switchback shafts, inside a 16-block lattice. Each gallery
is a spanning tree over its nodes, so there are no loops and every wrong turn is retreatable; leaves longer than a
few steps are pruned, so getting lost costs a player half a minute and their bearings and never their run. The 84
blocks of climb are spent in the shafts, not spread over a grade. A chamber on the middle gallery exposes the
Rift's own material, which is the one thing that is not corridor and so the thing to orient by.

Ground comes from the canonical heightmap, never from a world; `verify` reads a world only to check.

    python tools/victory_road.py build  --source-root <root> [--server-dir <server>]
    python tools/victory_road.py verify --world <stopped world copy>
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np

import function_limits as FL

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "victory_road.json"
REGIONS = ROOT / "data" / "rift_regions.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_victory_road"
PLAN = ROOT / "derived" / "victory_road" / "plan.json"
TILE = 64
PART = 3500

WORLD_READS = {"verify", "main"}


class RoadError(Exception):
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


def spanning_tree(nodes, salt):
    """A randomised depth-first spanning tree over a 4-connected node set: no loops, so nothing to circle in."""
    nodes = set(nodes)
    start = sorted(nodes)[0]
    seen, edges, stack = {start}, [], [start]
    while stack:
        a = stack[-1]
        opts = [n for n in ((a[0] + 1, a[1]), (a[0] - 1, a[1]), (a[0], a[1] + 1), (a[0], a[1] - 1))
                if n in nodes and n not in seen]
        if not opts:
            stack.pop()
            continue
        b = opts[int(unit(a[0], len(seen), a[1], salt) * len(opts)) % len(opts)]
        seen.add(b)
        edges.append((a, b))
        stack.append(b)
    return edges, seen


def prune_leaves(edges, keep, max_len):
    """Cut every dead end longer than max_len steps, so the worst wrong turn stays short."""
    adj = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    protected = set(keep)
    changed = True
    while changed:
        changed = False
        for _ in range(max_len + 1, 0, -1):
            pass
        # walk each leaf back to its first junction; if that run is too long, drop its far end
        for node in [n for n, nb in adj.items() if len(nb) == 1 and n not in protected]:
            run, cur, prev = [node], node, None
            while True:
                nb = [m for m in adj[cur] if m != prev]
                if len(nb) != 1:
                    break
                prev, cur = cur, nb[0]
                if len(adj[cur]) > 2 or cur in protected:
                    break
                run.append(cur)
            if len(run) > max_len:
                drop = run[0]
                for m in list(adj[drop]):
                    adj[m].discard(drop)
                del adj[drop]
                changed = True
    out = []
    for a, nb in adj.items():
        for b in nb:
            if (b, a) not in out:
                out.append((a, b))
    return out, set(adj)


def build(source_root, server_dir=None):
    import ground as G
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    have = installed_blocks(server_dir)
    g = G.load(source_root)
    lat = spec["lattice"]
    step = lat["step"]
    x0, z0, x1, z1 = lat["box"]
    gal = spec["galleries"]["y"]
    exit_y = spec["galleries"]["exit_y"]
    cor = spec["corridor"]
    wall_b = pick(cor["wall"], cor["wall_fallback"], have)
    floor_b = pick(cor["floor"], cor["floor_fallback"], have)
    light_b = pick(spec["light"]["block"], spec["light"]["fallback"], have)
    w, h = cor["width"], cor["height"]

    nodes = [(i, j) for i in range((x1 - x0) // step + 1) for j in range((z1 - z0) // step + 1)]
    if len(nodes) < 40:
        raise RoadError("only %d lattice nodes: the labyrinth would be a corridor" % len(nodes))
    nx = (x1 - x0) // step
    nz = (z1 - z0) // step

    lines, checks, counts = [], [], {}

    def count(k, v=1):
        counts[k] = counts.get(k, 0) + v

    def wx(i):
        return x0 + i * step

    def wz(j):
        return z0 + j * step

    # Two passes, and the order is the whole point: every wall in the road goes down before any air is cut. A
    # corridor that wrote its own walls as it went would seal an earlier corridor wherever the two cross, and the
    # labyrinth branches over itself on purpose, so crossings are everywhere.
    solid_lines, air_lines = [], []

    def carve(xa, ya, za, xb, yb, zb):
        """One corridor: rock around it and under it, then air through the middle."""
        n = max(abs(xb - xa), abs(zb - za), abs(yb - ya))
        for k in range(n + 1):
            f = k / float(max(1, n))
            cx = int(round(xa + (xb - xa) * f))
            cz = int(round(za + (zb - za) * f))
            cy = int(round(ya + (yb - ya) * f))
            for dx in range(-(w // 2) - 1, w - w // 2 + 1):
                for dz in range(-(w // 2) - 1, w - w // 2 + 1):
                    X, Z = cx + dx, cz + dz
                    if abs(dx) > w // 2 or abs(dz) > w // 2:
                        solid_lines.append("fill %d %d %d %d %d %d %s" % (X, cy - 1, Z, X, cy + h, Z, wall_b))
                    else:
                        solid_lines.append("fill %d %d %d %d %d %d %s" % (X, cy - 1, Z, X, cy - 1, Z, floor_b))
                        solid_lines.append("fill %d %d %d %d %d %d %s" % (X, cy + h, Z, X, cy + h, Z, wall_b))
                        air_lines.append("fill %d %d %d %d %d %d minecraft:air" % (X, cy, Z, X, cy + h - 1, Z))
            count("corridor blocks", (w + 2) * (w + 2) * (h + 2))

    # ---- the galleries, each a pruned spanning tree
    entry = (0, nz)                      # nearest the Deep (high z)
    exitn = (nx // 2, 0)                 # nearest the shelf (low z)
    trees = []
    for gi, gy in enumerate(gal):
        keep = [entry] if gi == 0 else []
        if gi == len(gal) - 1:
            keep.append(exitn)
        edges, seen = spanning_tree(nodes, 200 + gi)
        edges, seen = prune_leaves(edges, keep, spec["maze"]["dead_end_max"])
        trees.append((gy, edges, seen))
        for a, b in edges:
            carve(wx(a[0]), gy, wz(a[1]), wx(b[0]), gy, wz(b[1]))
        count("gallery %d corridors (y%d)" % (gi, gy), len(edges))

    # ---- the shafts: switchback stairs, the only places the road climbs
    sh = spec["shafts"]
    shafts = []
    for gi in range(len(gal) - 1):
        lo, hi = gal[gi], gal[gi + 1]
        pool = sorted(trees[gi][2] & trees[gi + 1][2])
        placed = []
        for t in range(400):
            if len(placed) >= sh["per_gallery"]:
                break
            c = pool[int(unit(t, gi, 0, 210) * (len(pool) - 1))]
            if any(abs(c[0] - p[0]) + abs(c[1] - p[1]) < 3 for p in placed):
                continue
            placed.append(c)
        if not placed:
            raise RoadError("no shaft could be placed between gallery %d and %d" % (gi, gi + 1))
        for c in placed:
            bx, bz = wx(c[0]), wz(c[1])
            rise = hi - lo
            legs = 4
            per = rise / float(legs)
            for L in range(legs):
                sgn = 1 if L % 2 == 0 else -1
                ya = int(round(lo + per * L))
                yb = int(round(lo + per * (L + 1)))
                carve(bx - sgn * 7, ya, bz, bx + sgn * 7, yb, bz)
            shafts.append([bx, lo, bz, hi])
            count("shafts")

    # ---- the landmark: the Rift's own material breaking through, on the middle gallery
    lm = spec["landmark"]
    gy = gal[lm["at_gallery"]]
    pool = sorted(trees[lm["at_gallery"]][2])
    c = pool[int(unit(0, 0, 0, 220) * (len(pool) - 1))]
    lx, lz = wx(c[0]), wz(c[1])
    face_b = pick(lm["face"], lm["face_fallback"], have)
    vein_b = pick(lm["vein"], lm["vein_fallback"], have)
    R, HH = lm["radius"], lm["height"]
    for dx in range(-R, R + 1):
        for dz in range(-R, R + 1):
            rr = math.hypot(dx, dz) / float(R)
            if rr > 1:
                continue
            top = gy + int(HH * (1 - rr ** 1.5))
            lines.append("fill %d %d %d %d %d %d minecraft:air" % (lx + dx, gy, lz + dz, lx + dx, top, lz + dz))
            if rr > 0.72:
                lines.append("setblock %d %d %d %s" % (lx + dx, gy - 1, lz + dz, face_b))
            if unit(lx + dx, gy, lz + dz, 221) < 0.05:
                lines.append("setblock %d %d %d %s" % (lx + dx, gy - 1, lz + dz, vein_b))
            elif unit(lx + dx, gy, lz + dz, 222) < 0.04:
                lines.append("setblock %d %d %d %s" % (lx + dx, gy - 1, lz + dz, lm["seep"]))
    # on the rim, where the exposed face is: the chamber's centre is open floor on purpose
    for ang in (0, 90, 180, 270):
        rx = lx + int(round(math.cos(math.radians(ang)) * R * 0.85))
        rz = lz + int(round(math.sin(math.radians(ang)) * R * 0.85))
        checks.append((rx, gy - 1, rz, [face_b, vein_b, lm["seep"]], "landmark"))
    count("landmark chamber blocks", int(math.pi * R * R * HH * 0.5))
    landmark = [lx, gy, lz]

    # ---- the exit: up onto the entrance shelf, facing the League
    ex, ez = wx(exitn[0]), wz(exitn[1])
    # g.box, not g(...): calling the Ground instance resolves to the whole class in
    # tools/ground_rule.py, and one of its methods names a region file, so build would be
    # reported as reading a world. It reads the heightmap.
    surf = int(g.box(ex, ez, ex, ez)[0, 0])
    carve(ex, gal[-1], ez, ex, min(exit_y, surf + 1), ez)
    lines.append("fill %d %d %d %d %d %d minecraft:air" % (ex - 2, min(exit_y, surf + 1), ez - 2,
                                                           ex + 2, surf + 4, ez + 2))
    checks.append((ex, surf + 2, ez, ["minecraft:air"], "exit open"))
    count("exit surface y", surf)

    # ---- light: scarce and placed
    n_light = 0
    for gi, (gy_, edges, seen) in enumerate(trees):
        for k, nd in enumerate(sorted(seen)):
            if k % spec["light"]["every_nodes"]:
                continue
            X, Z = wx(nd[0]), wz(nd[1])
            lines.append("setblock %d %d %d %s" % (X, gy_ + h - 1, Z, light_b))
            checks.append((X, gy_ + h - 1, Z, [light_b], "light"))
            n_light += 1
    count("lights", n_light)

    # ---- the nine trainers, on the main path only
    # not named `main`: tools/ground_rule.py resolves a local of that name to the module's own main(), which made
    # build look as though it read a world
    route = walked_route(trees, entry, exitn, shafts, wx, wz, gal)
    tr = spec["trainers"]
    stand_b = pick(tr["stand"], tr["stand_fallback"], have)
    stands = []
    for i in range(tr["count"]):
        p = route[int((i + 1) * len(route) / float(tr["count"] + 1))]
        stands.append(p)
        lines.append("setblock %d %d %d %s" % (p[0], p[1] - 1, p[2], stand_b))
        checks.append((p[0], p[1] - 1, p[2], [stand_b], "trainer stand"))
    count("trainer stands", len(stands))
    if len(stands) != tr["count"]:
        raise RoadError("marked %d trainer stands, not %d" % (len(stands), tr["count"]))

    # walls first, then air, then everything that stands in the finished space
    plan_lines = solid_lines + air_lines + lines
    return {"lines": plan_lines, "checks": checks, "counts": counts, "stands": stands,
            "landmark": landmark, "shafts": shafts, "exit": [ex, surf, ez],
            "galleries": gal}, spec


def walked_route(trees, entry, exitn, shafts, wx, wz, gal):
    """The route a player actually walks: entry, up each shaft in turn, out. Used only to place the trainers."""
    pts = []
    for gi, (gy, edges, seen) in enumerate(trees):
        adj = {}
        for a, b in edges:
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
        start = entry if gi == 0 else None
        if start is None or start not in adj:
            start = sorted(seen)[0]
        goal = exitn if gi == len(trees) - 1 else None
        if goal is None or goal not in adj:
            goal = sorted(seen)[-1]
        prev, q = {start: None}, deque([start])
        while q:
            a = q.popleft()
            if a == goal:
                break
            for b in adj.get(a, ()):
                if b not in prev:
                    prev[b] = a
                    q.append(b)
        node, run = goal, []
        while node is not None:
            run.append((wx(node[0]), gy + 1, wz(node[1])))
            node = prev.get(node)
        pts += list(reversed(run))
    return pts


def write(plan):
    import shutil
    if OUT.exists():
        shutil.rmtree(OUT)
    fn = OUT / "data" / "cobblers" / "function" / "victory_road"
    fn.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48, "description": "Cobblers: Victory Road"}}, indent=2) + "\n", encoding="utf-8")
    tiles = {}
    for ln in plan["lines"]:
        t = ln.split()
        tiles.setdefault((int(t[1]) // TILE, int(t[3]) // TILE), []).append(ln)
    order = []
    for t in sorted(tiles):
        body = tiles[t]
        for k in range(0, len(body), PART):
            name = "vr_%d_%d%s" % (t[0], t[1], "" if k == 0 else "_%d" % (k // PART + 1))
            out = FL.ensure_loaded(["# Generated by tools/victory_road.py: tile %d %d" % t] + body[k:k + PART])
            probs = FL.check_lines(out, name)
            if probs:
                raise RoadError("function %s would be refused: %s" % (name, probs[:3]))
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
        print("FAIL: no derived/victory_road/plan.json: run the build first")
        return 1
    p = json.loads(PLAN.read_text(encoding="utf-8"))
    kinds = {c[4] for c in p["checks"]}
    need = {"light", "trainer stand", "landmark", "exit open"}
    if not need <= kinds:
        print("FAIL: the plan checks %s, missing %s" % (sorted(kinds), sorted(need - kinds)))
        return 1
    if len(p["stands"]) != 9:
        print("FAIL: %d trainer stands, not 9" % len(p["stands"]))
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
    print("Victory Road: %s" % ("clean" if total == 0 else "%d MISMATCHES" % total))
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
        print("  %-40s %9d" % (k, v))
    print("Victory Road: %d functions, %d commands" % (len(order), len(plan["lines"])))
    print("  landmark at %s, exit at %s" % (plan["landmark"], plan["exit"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
