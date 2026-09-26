#!/usr/bin/env python
"""Build the foliage object library: tree, debris and understory objects for WorldPainter custom object layers.

Two sources, one library (kits/structures/foliage/library.json):

  harvest    vanilla configured features placed on a scratch pad with /place feature over RCON, then read
             back from the region files (tools/structure_nbt.py capture). Each placement is a different tree,
             so a group of N captures is N real vanilla variants. Needs the server running; writes to the
             live world only on scratch pads over the sea in the export margin, which the next export
             replaces.
  generate   objects vanilla does not have, built from seeded code so they regenerate identically: ancient
             2x2 spruces, snags, fallen logs, boulders, krummholz, bushes, leaf-litter patches and the
             landmark giants.
  index      recompute library.json (size, height, crown radius, trunk footprint, sha256) from the .nbt files.

  python tools/foliage_objects.py harvest --server <disposable-server-dir>
  python tools/foliage_objects.py generate
  python tools/foliage_objects.py index
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import time
from pathlib import Path

import numpy as np

import structure_nbt as S

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "kits" / "structures" / "foliage"

# group -> (configured feature, variants). Feature ids are Minecraft 1.21.1's (data/minecraft/worldgen/configured_feature).
VANILLA = {
    "spruce": ("minecraft:spruce", 10),
    "pine": ("minecraft:pine", 10),
    "mega_spruce": ("minecraft:mega_spruce", 10),
    "mega_pine": ("minecraft:mega_pine", 10),
    "oak": ("minecraft:oak", 8),
    "fancy_oak": ("minecraft:fancy_oak", 10),
    "birch": ("minecraft:birch", 8),
    "tall_birch": ("minecraft:super_birch_bees_0002", 8),
    "dark_oak": ("minecraft:dark_oak", 8),
    "jungle": ("minecraft:jungle_tree", 8),
    "mega_jungle": ("minecraft:mega_jungle_tree", 8),
    "jungle_bush": ("minecraft:jungle_bush", 8),
    "swamp_oak": ("minecraft:swamp_oak", 8),
    "cherry": ("minecraft:cherry", 8),
    "acacia": ("minecraft:acacia", 8),
    "azalea": ("minecraft:azalea_tree", 6),
    "huge_brown_mushroom": ("minecraft:huge_brown_mushroom", 4),
    "huge_red_mushroom": ("minecraft:huge_red_mushroom", 4),
    "forest_rock": ("minecraft:forest_rock", 6),
}
# blocks a capture never keeps: bee nests lose their bees without entity data, ground the feature converted
DROP = {"minecraft:bee_nest", "minecraft:beehive", "minecraft:grass_block", "minecraft:podzol", "minecraft:dirt",
        "minecraft:coarse_dirt", "minecraft:rooted_dirt", "minecraft:moss_block", "minecraft:structure_block",
        "minecraft:redstone_block"}
PAD_Y = 150
CELL = 40
HALF = 16
TOP = 48


# The ground rule (tools/ground_rule.py): the functions here that read a world, each only to check, never to
# decide a position: harvests object templates from a disposable probe world into the kit library; no position is decided from it.
WORLD_READS = {'harvest', 'main'}


def rcon_module(server):
    import runtime_guard
    server = runtime_guard.check(server, "use RCON through")
    spec = importlib.util.spec_from_file_location("server_rcon", Path(server) / "rcon.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pw = (Path(server) / ".rcon-password").read_text(encoding="utf8").strip()
    return lambda cmds: mod.run(cmds, pw)


def harvest(server, world_name, groups, origin=(-980, -980)):
    run = rcon_module(server)
    world = Path(server) / world_name
    LIB.mkdir(parents=True, exist_ok=True)
    report = {}
    row = 0
    for group in groups:
        feature, count = VANILLA[group]
        z = origin[1] + row * CELL
        x0 = origin[0]
        xs = [x0 + i * CELL for i in range(count)]
        run(["forceload add %d %d %d %d" % (x0 - CELL, z - CELL, xs[-1] + CELL, z + CELL)])
        cmds = []
        for x in xs:
            cmds.append("fill %d %d %d %d %d %d minecraft:air" % (x - HALF, PAD_Y - 1, z - HALF, x + HALF, PAD_Y + TOP, z + HALF))
            cmds.append("fill %d %d %d %d %d %d minecraft:grass_block" % (x - 5, PAD_Y - 1, z - 5, x + 5, PAD_Y - 1, z + 5))
        run(cmds)
        placed = []
        for x in xs:
            ok = False
            for _ in range(6):
                reply = run(["place feature %s %d %d %d" % (feature, x, PAD_Y, z)])[0]
                if reply.startswith("Placed"):
                    ok = True
                    break
            placed.append(ok)
        run(["save-all flush"])
        time.sleep(1.0)
        kept = 0
        for i, (x, ok) in enumerate(zip(xs, placed)):
            if not ok:
                continue
            b = S.capture(world, (x - HALF, PAD_Y, z - HALF), (x + HALF, PAD_Y + TOP, z + HALF))
            for k in [k for k, v in b.blocks.items() if v[0] in DROP]:
                del b.blocks[k]
            if len(b.blocks) < 3:
                continue
            # template coordinates put the placement origin at shift + (x, PAD_Y, z)
            data, shift = b.to_bytes()
            name = "%s_%02d" % (group, kept + 1)
            (LIB / (name + ".nbt")).write_bytes(data)
            meta = {"group": group, "source": "vanilla", "feature": feature,
                    "origin": [x + shift[0], PAD_Y + shift[1], z + shift[2]]}
            (LIB / (name + ".json")).write_text(json.dumps(meta, indent=1), encoding="utf-8")
            kept += 1
        run(["fill %d %d %d %d %d %d minecraft:air" % (x0 - HALF, PAD_Y - 1, z - HALF, xs[-1] + HALF, PAD_Y + TOP, z + HALF),
             "forceload remove %d %d %d %d" % (x0 - CELL, z - CELL, xs[-1] + CELL, z + CELL)])
        report[group] = {"feature": feature, "placed": sum(placed), "kept": kept}
        print("%-20s %-36s placed %d kept %d" % (group, feature, sum(placed), kept), flush=True)
        row += 1
    return report


# ------------------------------------------------------------------ generated objects

def leaves(kind):
    return ("minecraft:%s_leaves" % kind, {"distance": "1", "persistent": "true", "waterlogged": "false"})


def log(kind, axis="y"):
    return ("minecraft:%s_log" % kind, {"axis": axis})


def disk(b, cx, cy, cz, r, block, rng, ragged=0.25, only_empty=True):
    rr = int(math.ceil(r))
    for dx in range(-rr, rr + 1):
        for dz in range(-rr, rr + 1):
            d = math.hypot(dx, dz)
            if d > r + 0.35:
                continue
            if d > r - 1.2 and rng.random() < ragged:
                continue
            (b.setdefault if only_empty else b.set)(cx + dx, cy, cz + dz, *block)


def blob(b, cx, cy, cz, rx, ry, rz, block, rng, ragged=0.2):
    for dx in range(-int(rx) - 1, int(rx) + 2):
        for dy in range(-int(ry) - 1, int(ry) + 2):
            for dz in range(-int(rz) - 1, int(rz) + 2):
                e = (dx / max(rx, .5)) ** 2 + (dy / max(ry, .5)) ** 2 + (dz / max(rz, .5)) ** 2
                if e > 1.0:
                    continue
                if e > 0.6 and rng.random() < ragged:
                    continue
                b.setdefault(cx + dx, cy + dy, cz + dz, *block)


def line(b, a, c, block_fn):
    ax, ay, az = a
    cx, cy, cz = c
    n = int(max(abs(cx - ax), abs(cy - ay), abs(cz - az))) + 1
    dx, dy, dz = cx - ax, cy - ay, cz - az
    axis = "y" if abs(dy) >= max(abs(dx), abs(dz)) else ("x" if abs(dx) >= abs(dz) else "z")
    for i in range(n):
        t = i / max(n - 1, 1)
        b.set(round(ax + dx * t), round(ay + dy * t), round(az + dz * t), *block_fn(axis))


def trunk(b, x0, z0, w, y0, y1, kind):
    for y in range(y0, y1):
        for dx in range(w):
            for dz in range(w):
                b.set(x0 + dx, y, z0 + dz, *log(kind))


def ancient_spruce(rng, height, crown_share=0.62, max_r=6.0, kind="spruce"):
    """A 2x2 spruce taller than vanilla's: bare lower trunk, root flare, layered drooping whorls."""
    b = S.Builder()
    trunk(b, 0, 0, 2, 0, height - 1, kind)
    for (x, z) in ((-1, 0), (-1, 1), (2, 0), (2, 1), (0, -1), (1, -1), (0, 2), (1, 2)):
        for y in range(int(rng.integers(0, 3))):
            b.set(x, y, z, *log(kind))
    base = int(height * (1 - crown_share))
    y = height - 1
    whorl = 0
    while y >= base:
        f = (height - y) / max(height - base, 1)
        r = 1.0 + max_r * (f ** 0.85)
        if whorl % 3 == 0:
            disk(b, 0.5, y, 0.5, r, leaves(kind), rng, ragged=0.35)
            disk(b, 0.5, y - 1, 0.5, r * 0.55, leaves(kind), rng, ragged=0.4)
            for ang in rng.uniform(0, 2 * math.pi, int(rng.integers(2, 5))):
                L = max(1, int(r - 1.5))
                ex, ez = round(0.5 + math.cos(ang) * L), round(0.5 + math.sin(ang) * L)
                line(b, (int(round(0.5 + math.cos(ang))), y - 1, int(round(0.5 + math.sin(ang)))), (ex, y - 1, ez),
                     lambda ax: log(kind, "x" if ax == "x" else ("z" if ax == "z" else "y")))
                b.setdefault(ex, y - 2, ez, *leaves(kind))
        else:
            disk(b, 0.5, y, 0.5, r * 0.6, leaves(kind), rng, ragged=0.3)
        whorl += 1
        y -= 1
    for k in range(3):
        b.setdefault(0, height - 1 + k, 0, *leaves(kind))
    return b


def snag(rng, height, kind):
    b = S.Builder()
    for y in range(height):
        b.set(0, y, 0, *(("minecraft:stripped_%s_log" % kind, {"axis": "y"}) if y >= height - 2 else log(kind)))
    for _ in range(int(rng.integers(1, 4))):
        y = int(rng.integers(height // 3, max(height // 3 + 1, height - 2)))
        dx, dz = [(1, 0), (-1, 0), (0, 1), (0, -1)][int(rng.integers(0, 4))]
        L = int(rng.integers(1, 3))
        for i in range(1, L + 1):
            b.set(dx * i, y, dz * i, *log(kind, "x" if dx else "z"))
    return b


def fallen_log(rng, length, kind):
    b = S.Builder()
    for i in range(length):
        b.set(i, 0, 0, *log(kind, "x"))
        r = rng.random()
        if r < 0.45:
            b.set(i, 1, 0, "minecraft:moss_carpet")
        elif r < 0.55:
            b.set(i, 1, 0, "minecraft:brown_mushroom")
    # the root plate at the butt end
    for dy in range(0, 3):
        for dz in (-1, 0, 1):
            if dy == 2 and dz != 0:
                continue
            b.set(-1, dy, dz, "minecraft:rooted_dirt")
    b.set(-1, 0, 2 if rng.random() < .5 else -2, "minecraft:rooted_dirt")
    return b


def boulder(rng, rx, ry, rz, mossy=0.5):
    b = S.Builder()
    mats = ["minecraft:stone", "minecraft:andesite", "minecraft:cobblestone", "minecraft:tuff"]
    for dx in range(-int(rx) - 1, int(rx) + 2):
        for dy in range(0, int(ry) + 2):
            for dz in range(-int(rz) - 1, int(rz) + 2):
                e = (dx / rx) ** 2 + ((dy - 0.3) / ry) ** 2 + (dz / rz) ** 2
                if e > 1.0 + rng.normal(0, 0.08):
                    continue
                top = ((dx / rx) ** 2 + ((dy + 1 - 0.3) / ry) ** 2 + (dz / rz) ** 2) > 1.0
                if top and rng.random() < mossy:
                    m = "minecraft:mossy_cobblestone" if rng.random() < .6 else "minecraft:moss_block"
                else:
                    m = mats[int(rng.integers(0, len(mats)))]
                b.set(dx, dy, dz, m)
                if top and rng.random() < mossy * 0.5:
                    b.setdefault(dx, dy + 1, dz, "minecraft:moss_carpet")
    return b


def krummholz(rng, height, kind="spruce"):
    """Wind-flagged low spruce: a short trunk, leaves streaming to one side."""
    b = S.Builder()
    for y in range(height):
        b.set(0, y, 0, *log(kind))
    for y in range(1, height + 1):
        f = y / (height + 1)
        r = 1.2 + 2.0 * (1 - f)
        blob(b, 1, y, 0, r + 0.8, 0.7, r * 0.7, leaves(kind), rng, ragged=0.35)
    return b


def bush(rng, kind, r):
    b = S.Builder()
    b.set(0, 0, 0, *log("oak" if kind in ("azalea", "flowering_azalea") else kind))
    blob(b, 0, 1, 0, r, max(1.0, r * 0.7), r, leaves(kind), rng, ragged=0.3)
    return b


def litter_patch(rng, r):
    b = S.Builder()
    for dx in range(-r, r + 1):
        for dz in range(-r, r + 1):
            if math.hypot(dx, dz) > r + 0.3 or rng.random() < 0.35:
                continue
            b.set(dx, 0, dz, "minecraft:leaf_litter",
                  {"segment_amount": str(int(rng.integers(1, 5))), "facing": ["north", "south", "east", "west"][int(rng.integers(0, 4))]})
    if len(b.blocks) == 0:
        b.set(0, 0, 0, "minecraft:leaf_litter", {"segment_amount": "2", "facing": "north"})
    return b


# ------------------------------------------------------------------ swamp: mangroves, tall vine-hung trees, snags
# Vanilla Minecraft 1.21.1 blocks only. A hanging propagule survives under mangrove leaves; a vine names the face it
# clings to, and a vine under another vine with the same face hangs from it, which is how a curtain holds.

MANGROVE_ROOTS = ("minecraft:mangrove_roots", {"waterlogged": "false"})
MUDDY_ROOTS = ("minecraft:muddy_mangrove_roots", {"axis": "y"})
PROPAGULE = ("minecraft:mangrove_propagule", {"age": "4", "hanging": "true", "stage": "0", "waterlogged": "false"})
MOSS_CARPET = "minecraft:moss_carpet"
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))
FACE = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}


def hang_propagules(b, rng, share, floor_y=2):
    """A hanging propagule under a share of the mangrove leaves that have air below, never lower than floor_y."""
    for (x, y, z) in sorted(k for k, v in b.blocks.items() if v[0] == "minecraft:mangrove_leaves"):
        if y - 1 >= floor_y and (x, y - 1, z) not in b.blocks and rng.random() < share:
            b.set(x, y - 1, z, *PROPAGULE)


def vine_curtains(b, rng, share, lo, hi, floor_y=2):
    """Vine chains on the open sides of leaves: each clings to its leaf (the face it names points at the leaf) and
    hangs straight down lo..hi blocks, stopping at anything already there and never below floor_y, so a curtain is
    never ground contact and never in the eye-level layer."""
    for (x, y, z) in sorted(k for k, v in b.blocks.items() if v[0].endswith("_leaves")):
        for dx, dz in SIDES:
            vx, vz = x + dx, z + dz
            if (vx, y, vz) in b.blocks or (vx, y - 1, vz) in b.blocks or y < floor_y:
                continue
            if rng.random() >= share:
                continue
            face = FACE[(-dx, -dz)]
            for k in range(int(rng.integers(lo, hi + 1))):
                vy = y - k
                if vy < floor_y or (vx, vy, vz) in b.blocks:
                    break
                b.set(vx, vy, vz, "minecraft:vine", {face: "true"})


def climbing_vines(b, rng, share, min_y=2):
    """Vines up the faces of logs from min_y: each names the face of the log it clings to."""
    for (x, y, z) in sorted(k for k, v in b.blocks.items() if v[0].endswith("_log") and k[1] >= min_y):
        for dx, dz in SIDES:
            vx, vz = x + dx, z + dz
            if (vx, y, vz) not in b.blocks and rng.random() < share:
                b.set(vx, y, vz, "minecraft:vine", {FACE[(-dx, -dz)]: "true"})


def moss_on_roots(b, rng, share):
    """Moss carpet on top of a share of the root blocks with air above (vanilla puts moss over mangrove roots)."""
    for (x, y, z) in sorted(k for k, v in b.blocks.items() if v[0] in ("minecraft:mangrove_roots",
                                                                        "minecraft:muddy_mangrove_roots")):
        if (x, y + 1, z) not in b.blocks and rng.random() < share:
            b.set(x, y + 1, z, MOSS_CARPET)


def prop_root(b, cx, cz, ang, top, reach):
    """An arching prop root: leaves the raised trunk nearly level at height top and plunges to a foot reach blocks
    out on the origin layer. The foot is muddy roots, the object's lowest layer, which WorldPainter's extend
    foundation carries down to uneven ground."""
    n = int(3 * (reach + top)) + 2
    for i in range(n + 1):
        t = i / n
        y = int(round(top * (1 - t * t)))
        r = 0.6 + reach * t
        x, z = int(round(cx + math.cos(ang) * r)), int(round(cz + math.sin(ang) * r))
        if y <= 0:
            b.set(x, 0, z, *MUDDY_ROOTS)
        else:
            b.setdefault(x, y, z, *MANGROVE_ROOTS)


def mangrove(rng, top, trunk_h, roots, reach, crown_r, branches, propagules=0.05, vines=(0.12, 2, 7)):
    """A mangrove on prop roots: a 1x1 trunk raised top blocks on a root column and arching roots, leaning a little,
    branching into leaf clouds, hung with propagules and vine curtains, moss on the roots."""
    b = S.Builder()
    b.set(0, 0, 0, *MUDDY_ROOTS)
    for y in range(1, top):
        b.set(0, y, 0, *MANGROVE_ROOTS)
    for k in range(roots):
        ang = 2 * math.pi * (k + rng.uniform(-0.25, 0.25)) / roots
        prop_root(b, 0, 0, ang, max(1, top - int(rng.integers(0, 2))), reach * rng.uniform(0.75, 1.1))
    lean_ang = rng.uniform(0, 2 * math.pi)
    lean = rng.uniform(0.0, 0.12)
    col = {}
    px, pz = 0, 0
    for y in range(top, top + trunk_h):
        tx = int(round(math.cos(lean_ang) * lean * (y - top)))
        tz = int(round(math.sin(lean_ang) * lean * (y - top)))
        if (tx, tz) != (px, pz):
            b.set(px, y, pz, *log("mangrove"))          # keep the leaning trunk joined face to face
        b.set(tx, y, tz, *log("mangrove"))
        col[y] = (tx, tz)
        px, pz = tx, tz
    y_top = top + trunk_h - 1
    tips = [(px, y_top, pz)]
    base_ang = rng.uniform(0, 2 * math.pi)
    for k in range(branches):
        ang = base_ang + 2 * math.pi * (k + rng.uniform(-0.2, 0.2)) / branches
        yb = top + int(trunk_h * rng.uniform(0.5, 0.8))
        bx, bz = col.get(yb, (px, pz))
        L = crown_r * rng.uniform(0.6, 1.0)
        tip = (int(round(bx + math.cos(ang) * L)), yb + int(round(L * 0.7)), int(round(bz + math.sin(ang) * L)))
        line(b, (bx, yb, bz), tip, lambda ax: log("mangrove", ax))
        tips.append(tip)
    for (cx, cy, cz) in tips:
        r = crown_r * rng.uniform(0.75, 1.0)
        blob(b, cx, cy + 1, cz, r, max(1.6, crown_r * 0.45), r, leaves("mangrove"), rng, ragged=0.25)
    hang_propagules(b, rng, propagules)
    vine_curtains(b, rng, *vines)
    moss_on_roots(b, rng, 0.35)
    return b


def swamp_giant(rng, height, crown_r, limbs):
    """A tall swamp oak: 2x2 trunk on log knees, limbs to a broad flat crown, a drooping rim and heavy vine
    curtains, moss on the knees."""
    b = S.Builder()
    kind = "oak"
    trunk(b, 0, 0, 2, 0, height - 2, kind)
    for (x, z) in ((-1, 0), (-1, 1), (2, 0), (2, 1), (0, -1), (1, -1), (0, 2), (1, 2)):
        for y in range(int(rng.integers(1, 4))):
            b.set(x, y, z, *log(kind))
    for (x, z) in ((-2, 0), (3, 1), (1, -2), (0, 3)):
        if rng.random() < 0.6:
            b.set(x, 0, z, *log(kind))
    base_ang = rng.uniform(0, 2 * math.pi)
    tips = []
    for k in range(limbs):
        ang = base_ang + 2 * math.pi * (k + rng.uniform(-0.2, 0.2)) / limbs
        yb = int(height * rng.uniform(0.55, 0.75))
        L = crown_r * rng.uniform(0.55, 0.85)
        sx, sz = (1 if math.cos(ang) > 0 else 0), (1 if math.sin(ang) > 0 else 0)
        tip = (int(round(0.5 + math.cos(ang) * L)), yb + int(round(L * 0.5)), int(round(0.5 + math.sin(ang) * L)))
        line(b, (sx, yb, sz), tip, lambda ax: log(kind, ax))
        tips.append(tip)
    disk(b, 0.5, height - 2, 0.5, crown_r, leaves(kind), rng, ragged=0.3)
    disk(b, 0.5, height - 1, 0.5, crown_r * 0.7, leaves(kind), rng, ragged=0.3)
    disk(b, 0.5, height, 0.5, crown_r * 0.4, leaves(kind), rng, ragged=0.3)
    for (cx, cy, cz) in tips:
        r = crown_r * rng.uniform(0.4, 0.55)
        blob(b, cx, cy + 1, cz, r, 1.6, r, leaves(kind), rng, ragged=0.25)
    # a drooping rim: leaves hang one or two blocks under the crown's outer edge
    for (x, y, z) in sorted(k for k, v in b.blocks.items() if v[0].endswith("_leaves")):
        if math.hypot(x - 0.5, z - 0.5) > crown_r - 1.5 and (x, y - 1, z) not in b.blocks and rng.random() < 0.3:
            for k in range(1, int(rng.integers(2, 4))):
                b.setdefault(x, y - k, z, *leaves(kind))
    vine_curtains(b, rng, 0.3, 3, 12)
    climbing_vines(b, rng, 0.2)
    for (x, y, z) in sorted(k for k, v in b.blocks.items() if v[0].endswith("_log") and k[1] <= 2):
        if (x, y + 1, z) not in b.blocks and rng.random() < 0.5:
            b.set(x, y + 1, z, MOSS_CARPET)
    return b


def vine_snag(rng, height, kind):
    """A dead standing trunk wrapped in vines."""
    b = snag(rng, height, kind)
    climbing_vines(b, rng, 0.45)
    return b


def root_tangle(rng, r):
    """A knee-high knot of mangrove roots with moss: the root floor between the trees."""
    b = S.Builder()
    b.set(0, 0, 0, *MUDDY_ROOTS)
    b.set(0, 1, 0, *MANGROVE_ROOTS)
    n = int(rng.integers(3, 6))
    for k in range(n):
        ang = 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / n
        prop_root(b, 0, 0, ang, int(rng.integers(1, 3)), r * rng.uniform(0.7, 1.0))
    moss_on_roots(b, rng, 0.45)
    return b


def jungle_emergent(rng, height, crown_r, limbs):
    """An emergent jungle giant for the jungle isles (docs/world-building/FOLIAGE_MARSH_JUNGLE.md): a 2x2 jungle trunk
    well above vanilla's tallest mega jungle tree (31), log buttresses at its foot, bare to its upper third, limbs out
    to a flat umbrella crown that stands clear of the canopy, vine curtains under the crown, vines and cocoa up the
    trunk. Vanilla Minecraft 1.21.1 blocks only."""
    b = S.Builder()
    kind = "jungle"
    trunk(b, 0, 0, 2, 0, height - 2, kind)
    # buttresses: fins of log running out from the trunk's faces, tallest against the trunk
    for (sx, sz, dx, dz) in ((0, 0, -1, 0), (0, 0, 0, -1), (1, 0, 1, 0), (1, 0, 0, -1),
                             (0, 1, -1, 0), (0, 1, 0, 1), (1, 1, 1, 0), (1, 1, 0, 1)):
        if rng.random() < 0.7:
            reach = int(rng.integers(1, 4))
            for k in range(1, reach + 1):
                for y in range(max(1, int(round((reach - k + 1) * rng.uniform(1.2, 2.0))))):
                    b.set(sx + dx * k, y, sz + dz * k, *log(kind))
    base_ang = rng.uniform(0, 2 * math.pi)
    tips = []
    for k in range(limbs):
        ang = base_ang + 2 * math.pi * (k + rng.uniform(-0.2, 0.2)) / limbs
        yb = int(height * rng.uniform(0.66, 0.82))
        L = crown_r * rng.uniform(0.55, 0.85)
        sx, sz = (1 if math.cos(ang) > 0 else 0), (1 if math.sin(ang) > 0 else 0)
        tip = (int(round(0.5 + math.cos(ang) * L)), min(height - 3, yb + int(round(L * 0.45))),
               int(round(0.5 + math.sin(ang) * L)))
        line(b, (sx, yb, sz), tip, lambda ax: log(kind, ax))
        tips.append(tip)
    # the umbrella: a broad flat layer with a lower rim and a shallow dome
    disk(b, 0.5, height - 3, 0.5, crown_r, leaves(kind), rng, ragged=0.3)
    disk(b, 0.5, height - 2, 0.5, crown_r * 0.8, leaves(kind), rng, ragged=0.3)
    disk(b, 0.5, height - 1, 0.5, crown_r * 0.55, leaves(kind), rng, ragged=0.3)
    disk(b, 0.5, height, 0.5, crown_r * 0.3, leaves(kind), rng, ragged=0.3)
    for (cx, cy, cz) in tips:
        r = crown_r * rng.uniform(0.35, 0.5)
        blob(b, cx, cy + 1, cz, r, 1.8, r, leaves(kind), rng, ragged=0.25)
    for (x, y, z) in sorted(k for k, v in b.blocks.items() if v[0].endswith("_leaves")):
        if math.hypot(x - 0.5, z - 0.5) > crown_r - 1.5 and (x, y - 1, z) not in b.blocks and rng.random() < 0.25:
            for k in range(1, int(rng.integers(2, 4))):
                b.setdefault(x, y - k, z, *leaves(kind))
    # cocoa on the lower trunk (facing names the log it hangs on), then vines
    for (x, y, z) in sorted(k for k, v in b.blocks.items() if v[0] == "minecraft:jungle_log" and 3 <= k[1] <= 12
                            and 0 <= k[0] <= 1 and 0 <= k[2] <= 1):
        for dx, dz in SIDES:
            cx_, cz_ = x + dx, z + dz
            if (cx_, y, cz_) not in b.blocks and rng.random() < 0.05:
                b.set(cx_, y, cz_, "minecraft:cocoa", {"age": str(int(rng.integers(0, 3))), "facing": FACE[(-dx, -dz)]})
    vine_curtains(b, rng, 0.22, 4, 14)
    climbing_vines(b, rng, 0.28, min_y=3)
    return b


def generated_objects():
    """name -> (group, builder). Seeds are fixed per object so the files regenerate byte for byte."""
    out = {}

    def rng_for(name):
        return np.random.default_rng(int(hashlib.sha256(name.encode()).hexdigest()[:12], 16))

    for i, h in enumerate((34, 37, 40, 43, 46, 49)):
        n = "ancient_spruce_%02d" % (i + 1)
        out[n] = ("ancient_spruce", ancient_spruce(rng_for(n), h, max_r=5.5 + i * 0.3))
    for i, h in enumerate((30, 34, 38)):
        n = "ancient_pine_%02d" % (i + 1)
        out[n] = ("ancient_pine", ancient_spruce(rng_for(n), h, crown_share=0.32, max_r=4.5))
    for i, (h, kind) in enumerate(((6, "spruce"), (9, "spruce"), (12, "spruce"), (7, "oak"), (10, "birch"), (8, "dark_oak"))):
        n = "snag_%s_%02d" % (kind, i + 1)
        out[n] = ("snag_" + ("conifer" if kind == "spruce" else "broadleaf"), snag(rng_for(n), h, kind))
    for i, (L, kind) in enumerate(((6, "spruce"), (9, "spruce"), (11, "spruce"), (5, "oak"), (8, "oak"), (7, "birch"), (8, "dark_oak"))):
        n = "fallen_%s_%02d" % (kind, i + 1)
        out[n] = ("fallen_log_" + ("conifer" if kind == "spruce" else "broadleaf"), fallen_log(rng_for(n), L, kind))
    for i, (rx, ry, rz) in enumerate(((1.6, 1.2, 1.4), (2.2, 1.6, 1.8), (2.8, 2.0, 2.3), (3.4, 2.4, 2.6), (2.0, 1.1, 3.0), (4.0, 2.6, 3.2))):
        n = "boulder_%02d" % (i + 1)
        out[n] = ("boulder", boulder(rng_for(n), rx, ry, rz))
    for i, h in enumerate((1, 2, 2, 3, 3, 4, 5)):
        n = "krummholz_%02d" % (i + 1)
        out[n] = ("krummholz", krummholz(rng_for(n), h))
    for i, (kind, r) in enumerate((("oak", 1.2), ("oak", 1.8), ("spruce", 1.3), ("azalea", 1.5), ("flowering_azalea", 1.5), ("birch", 1.4), ("jungle", 1.8), ("dark_oak", 1.6))):
        n = "bush_%s_%02d" % (kind, i + 1)
        out[n] = ("bush_" + ("conifer" if kind == "spruce" else "broadleaf"), bush(rng_for(n), kind, r))
    for i, r in enumerate((1, 2, 2, 3)):
        n = "litter_%02d" % (i + 1)
        out[n] = ("leaf_litter", litter_patch(rng_for(n), r))
    # swamp (data/foliage.json overlays; docs/world-building/FOLIAGE_MARSH_JUNGLE.md)
    for i, (top, th, roots, reach, cr, br) in enumerate(((3, 5, 5, 3.0, 3.5, 2), (3, 6, 6, 3.5, 3.8, 2),
                                                         (4, 6, 6, 3.5, 4.0, 3), (4, 7, 7, 4.0, 4.2, 2),
                                                         (4, 8, 7, 4.0, 4.5, 3), (5, 8, 8, 4.5, 4.5, 3))):
        n = "mangrove_%02d" % (i + 1)
        out[n] = ("mangrove", mangrove(rng_for(n), top, th, roots, reach, cr, br))
    for i, (top, th, roots, reach, cr, br) in enumerate(((5, 13, 7, 4.5, 4.8, 3), (5, 15, 8, 5.0, 5.0, 3),
                                                         (6, 16, 8, 5.0, 5.3, 4), (6, 18, 9, 5.5, 5.5, 4))):
        n = "tall_mangrove_%02d" % (i + 1)
        out[n] = ("tall_mangrove", mangrove(rng_for(n), top, th, roots, reach, cr, br, propagules=0.04,
                                            vines=(0.16, 3, 10)))
    for i, (th, reach, cr, br) in enumerate(((2, 2.0, 2.0, 0), (3, 2.2, 2.3, 1), (3, 2.5, 2.4, 1))):
        n = "mangrove_scrub_%02d" % (i + 1)
        out[n] = ("mangrove_scrub", mangrove(rng_for(n), 2, th, 4, reach, cr, br, propagules=0.06, vines=(0.08, 1, 3)))
    for i, (h, cr, limbs) in enumerate(((16, 6.5, 4), (18, 7.0, 4), (20, 7.5, 5), (22, 8.0, 5))):
        n = "swamp_giant_%02d" % (i + 1)
        out[n] = ("swamp_giant", swamp_giant(rng_for(n), h, cr, limbs))
    for i, (h, kind) in enumerate(((6, "oak"), (8, "mangrove"), (10, "oak"))):
        n = "vine_snag_%s_%02d" % (kind, i + 1)
        out[n] = ("vine_snag", vine_snag(rng_for(n), h, kind))
    for i, r in enumerate((2.0, 2.5, 3.0, 3.0)):
        n = "root_tangle_%02d" % (i + 1)
        out[n] = ("root_tangle", root_tangle(rng_for(n), r))
    # jungle isles (data/foliage.json overlay jungle_emergents): crowns at 34-46, over vanilla's 14-31 mega jungle
    for i, (h, cr, limbs) in enumerate(((34, 9.0, 4), (38, 10.0, 5), (42, 11.0, 5), (46, 12.0, 6))):
        n = "jungle_emergent_%02d" % (i + 1)
        out[n] = ("jungle_emergent", jungle_emergent(rng_for(n), h, cr, limbs))
    import landmark_trees as LT
    for n, (group, builder) in LT.designs().items():
        out[n] = (group, builder)
    return out


def generate():
    LIB.mkdir(parents=True, exist_ok=True)
    rows = {}
    for name, (group, b) in generated_objects().items():
        data, shift = b.to_bytes()
        (LIB / (name + ".nbt")).write_bytes(data)
        meta = {"group": group, "source": "generated", "generator": "tools/foliage_objects.py",
                "origin": [int(shift[0]), int(shift[1]), int(shift[2])]}
        (LIB / (name + ".json")).write_text(json.dumps(meta, indent=1), encoding="utf-8")
        rows[name] = group
    print("generated %d objects" % len(rows))
    return rows


# ------------------------------------------------------------------ index

TRUNK_SUFFIX = ("_log", "_wood", "_stem")
NOT_BLOCKING = {"minecraft:moss_carpet", "minecraft:leaf_litter", "minecraft:pink_petals", "minecraft:brown_mushroom",
                "minecraft:red_mushroom", "minecraft:vine"}


def measure(t, origin):
    """Height above the origin, crown radius from the trunk, trunk footprint at the origin layer."""
    pal = t["palette"]
    ox, oy, oz = origin
    pts = np.array([(x, y, z) for x, y, z, _ in t["blocks"]]) if t["blocks"] else np.zeros((0, 3))
    names = [pal[s][0] for *_, s in t["blocks"]]
    base = [(x, z) for (x, y, z), n in zip(pts.tolist(), names) if y == oy and n.endswith(TRUNK_SUFFIX)]
    leafy = np.array([p for p, n in zip(pts.tolist(), names) if "leaves" in n or n.endswith("_block")] or [[ox, oy, oz]])
    crown = float(np.hypot(leafy[:, 0] - ox, leafy[:, 2] - oz).max()) if len(leafy) else 0.0
    # what blocks a standing player's view: the widest extent of solid blocks one layer above the base
    eye = [(x, z) for (x, y, z), nm in zip(pts.tolist(), names) if y == oy + 1 and nm not in NOT_BLOCKING]
    eye_width = 0
    if eye:
        e = np.array(eye)
        eye_width = int(max(e[:, 0].max() - e[:, 0].min(), e[:, 1].max() - e[:, 1].min()) + 1)
    # ground contact: every non-leaf block in the lowest two layers (litter and moss too: an object cannot sit on
    # water), as the largest square distance from the origin
    # column. A 2x2 trunk at the origin corner counts 1, so placement checks the 3x3 that covers every rotation.
    ground = [(x, z) for (x, y, z), nm in zip(pts.tolist(), names)
              if y <= oy + 1 and "leaves" not in nm and nm != "minecraft:vine"]
    ground_radius = int(max(max(abs(x - ox), abs(z - oz)) for x, z in ground)) if ground else 0
    return {"size": t["size"], "blocks": len(t["blocks"]), "height": int(pts[:, 1].max() - oy + 1) if len(pts) else 0,
            "eye_width": eye_width, "ground_radius": ground_radius,
            "crown_radius": round(crown, 1), "trunk_footprint": len(set(base)) or 1,
            "depth_below_origin": int(max(0, oy - pts[:, 1].min())) if len(pts) else 0}


def index():
    rows = []
    for nbt_path in sorted(LIB.glob("*.nbt")):
        meta_path = nbt_path.with_suffix(".json")
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        t = S.load(nbt_path)
        m = measure(t, meta["origin"])
        rows.append(dict(name=nbt_path.stem, file=nbt_path.name, group=meta["group"], source=meta["source"],
                         feature=meta.get("feature"), origin=meta["origin"],
                         sha256=hashlib.sha256(nbt_path.read_bytes()).hexdigest(), **m))
    groups = {}
    for r in rows:
        g = groups.setdefault(r["group"], {"objects": 0, "height": [999, 0], "crown_radius": [999, 0]})
        g["objects"] += 1
        g["height"] = [min(g["height"][0], r["height"]), max(g["height"][1], r["height"])]
        g["crown_radius"] = [min(g["crown_radius"][0], r["crown_radius"]), max(g["crown_radius"][1], r["crown_radius"])]
    doc = {"schema": "cobblers.foliage_library/1", "generator": "tools/foliage_objects.py index",
           "note": "origin is the template coordinate of the object's base column (trunk corner for 2x2 trunks); "
                   "WorldPainter's offset is its negation. Vanilla objects are captures of Minecraft 1.21.1 "
                   "configured features; generated objects come from seeded code in this repository.",
           "groups": groups, "objects": rows}
    (LIB / "library.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print("indexed %d objects in %d groups" % (len(rows), len(groups)))
    return doc


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("harvest")
    h.add_argument("--server", required=True)
    h.add_argument("--world-name", required=True, help="world folder of a disposable harvest server")
    h.add_argument("--groups", nargs="*", default=list(VANILLA))
    sub.add_parser("generate")
    sub.add_parser("index")
    a = p.parse_args(argv)
    if a.cmd == "harvest":
        harvest(a.server, a.world_name, a.groups)
        index()
    elif a.cmd == "generate":
        generate()
        index()
    else:
        index()


if __name__ == "__main__":
    main()
