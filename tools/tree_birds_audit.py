#!/usr/bin/env python
"""Independent audit of the tree-bird nests (the `tbird_*` Habitat Block records) and their pools.

Written by the test author, not by the session that built tools/tree_birds.py. It deliberately imports NONE of
tools/tree_birds.py, tools/habitat_spawn_model.py or tools/tree_geometry.py: it re-seats every tree from the tree
templates (kits/structures/prefabs/trees/**/*.nbt and their sidecars) and the pinned sites, and re-derives the
Cobblemon zone rule from its own description (docs/world-building/SAPLING_BIRDS.md "The rule"; the jar read is the
builder's, relayed: this audit does not re-read the bytecode). The world tree is the one exception that needs the
generator that places it (tools/tree_grove.big_tree, tools/world_tree.CENTRE/GROUND): that is the tree itself, not the
builder's geometry of it.

Per nest it checks
  wood      the cell is a block of the tree's own template (never open air, never the floor), its block is the
            record's mimic, and all six face neighbours are solid blocks of the same template, so the nest is hidden
            and does not change what a player sees
  zone      after the re-centring rule (up first in the nest's own column, at most maxVerticalCorrectionBlocks, read
            from modpack/config/cobblemon/main.json) the (2r+1)^3 box holds grounded cells (solid with a non-solid
            block above), none of them the forest floor, and some of them on the nest's own storey of limbs
            (the storeys are measured from the template: runs of wood further out than the trunk; the world tree's
            come from the generator's own `floor_tier_y`), so a `low` nest produces birds on the first storey
  order     a tree's low zone is centred below its mid zone, and that below every zone its four existing nests give
  clear     the nest is not on a route path, not inside a placed structure's conservative footprint (data/placements.json
            with the template size read from its file), and not closer to a town centre than the elders' own siting
            rule (120, tools/elder_trees.py OFF_TOWN) less the nest's offset from its trunk axis
  records   no two habitat blocks share a cell or touch face to face
and over the whole set: every record has its pool and every tbird pool a record; the covered trees are exactly the
designer's trees (data/tree_bird_species.json) less the grove elders; each pool's species are exactly the designer's
band (weight above 0).

NOT COVERED (said, not hidden)
  - the 4 Foothill grove elders: their seat is in derived/sites/tree_grove_foothill_woods.json, gitignored: reported
    UNCOVERED, and the audit insists they have no tbird record;
  - terrain, neighbouring trees, a path's width (route_paths.json holds centreline cells only), structures with no
    template file (81 of 378 placements), and legs of derived/routes (absent);
  - that Minecraft takes the same zone: the rule is the builder's reading of the jar, relayed. A `snow` layer's
    solidity is uncertain: pass snow="lenient" (layers >= 3 solid) as well as the default strict (only 8 layers);
  - that a bird actually stands there. That is a staging observation (the doc's "How to prove it").

  python tools/tree_birds_audit.py [--no-world-tree] [--snow strict|lenient] > file 2>&1 ; grep PROBLEM file
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import nbt  # noqa: E402  (a generic reader of NBT: not tree geometry)

DATA = ROOT / "data"
PREFABS = ROOT / "kits" / "structures" / "prefabs" / "trees"
MAIN_JSON = ROOT / "modpack" / "config" / "cobblemon" / "main.json"
PREFIX = "tbird_"
WORLD_TREE = "world_tree_foothill_woods"
GROVE_ELDERS = ("elder_foothill_grove_1", "elder_foothill_grove_2", "elder_foothill_grove_3", "elder_foothill_grove_4")
OFF_TOWN = 120          # tools/elder_trees.py: elders are at least this far from a town centre
PATH_HALF_WIDTH = 2     # a route path is stored as centreline cells; no width is recorded, so only the cell and its
#                         immediate neighbours are called "on the path" (the measured minimum is far above it)
ROT = {"none": lambda x, z: (x, z), "clockwise_90": lambda x, z: (-z, x), "180": lambda x, z: (-x, -z),
       "counterclockwise_90": lambda x, z: (z, -x)}
FACES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))

# --- what a block is, decided here (an unlisted block name is a PROBLEM, never a silent guess)
FULL_SUFFIX = ("_log", "_wood", "_leaves", "_planks")
FULL_NAMES = {"minecraft:bone_block", "minecraft:nether_wart_block", "minecraft:shroomlight", "minecraft:magma_block",
              "minecraft:blackstone", "minecraft:polished_basalt", "minecraft:coal_block", "minecraft:packed_ice",
              "minecraft:mangrove_roots"}
NOT_SOLID = {"minecraft:cocoa", "minecraft:dead_bush", "minecraft:lightning_rod", "minecraft:air"}


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def block_solid(name, props, snow):
    """True when the block is `isSolid`-like. `snow`: 'strict' = only 8 layers, 'lenient' = 3 or more layers."""
    if name in NOT_SOLID:
        return False
    if name == "minecraft:snow":
        n = int((props or {}).get("layers", "1"))
        return n >= 8 if snow == "strict" else n >= 3
    if name in FULL_NAMES or name.endswith(FULL_SUFFIX):
        return True
    raise ValueError("unclassified block %s: add it to FULL_NAMES or NOT_SOLID after checking its collision shape" % name)


class Tree:
    """A seated tree: names {(x, y, z): name}, solid set, the ground, the storeys (h = y - ground - 1 runs)."""

    def __init__(self, tid, kind, ground, centre, names, props, snow):
        self.id, self.kind, self.ground, self.centre = tid, kind, ground, centre
        self.names = names
        self.solid = {p for p, n in names.items() if block_solid(n, props.get(p), snow)}
        self.storeys = []
        self._standing = None

    def is_solid(self, x, y, z):
        return y <= self.ground or (x, y, z) in self.solid

    def is_air(self, x, y, z):
        return y > self.ground and (x, y, z) not in self.names

    def standing(self):
        """Every solid cell of the tree with a non-solid block above it."""
        if self._standing is None:
            self._standing = [p for p in self.solid if (p[0], p[1] + 1, p[2]) not in self.solid]
        return self._standing

    def centre_y(self, x, y, z, max_correction):
        """The y the zone is re-centred on: the nearest valid start in the column, up first; None = no spawn."""
        def valid(yy):
            return self.is_air(x, yy, z) and not self.is_solid(x, yy + 1, z)
        if valid(y):
            return y
        for k in range(1, max_correction + 1):
            if valid(y + k):
                return y + k
            if valid(y - k):
                return y - k
        return None

    def zone(self, x, y, z, r, max_correction):
        """(centre y or None, grounded cells in the box, floor columns in the box)."""
        cy = self.centre_y(x, y, z, max_correction)
        if cy is None:
            return None, [], 0
        base = cy - (2 * r + 1) // 2
        top = base + 2 * r        # the box holds y in base .. base + 2r
        cells = [p for p in self.standing() if abs(p[0] - x) <= r and abs(p[2] - z) <= r and base <= p[1] <= top]
        floor = 0
        if base <= self.ground <= top:
            floor = sum(1 for cx in range(x - r, x + r + 1) for cz in range(z - r, z + r + 1)
                        if (cx, self.ground + 1, cz) not in self.solid)
        return cy, cells, floor

    def h(self, y):
        return y - self.ground - 1


def _runs(heights):
    out, start, prev = [], None, None
    for v in sorted(heights):
        if start is None:
            start = prev = v
        elif v == prev + 1:
            prev = v
        else:
            out.append((start, prev))
            start = prev = v
    if start is not None:
        out.append((start, prev))
    return out


def _template(path):
    _, doc = nbt.load(path)
    pal = doc["palette"]
    return [(tuple(b["pos"]), pal[b["state"]]["Name"], pal[b["state"]].get("Properties") or {}) for b in doc["blocks"]]


def _seat_template(blocks, trunk_origin, trunk_centre_local, rot, centre_xz, ground, tid, kind, snow, trunk_half):
    ox, oy, oz = trunk_origin
    qx, qz = ROT[rot](*trunk_centre_local)
    px, pz = centre_xz[0] - qx, centre_xz[1] - qz
    py = ground + 1 - oy
    names, props = {}, {}
    for (tx, ty, tz), name, pr in blocks:
        rx, rz = ROT[rot](tx, tz)
        p = (px + rx, py + ty, pz + rz)
        names[p] = name
        props[p] = pr
    # the tree's wood is whatever its trunk is made of: the block at the trunk centre, ten above the ground
    # (a themed skin may be bone, basalt or wart: it is never guessed from a name)
    trunk = names.get((centre_xz[0], ground + 1 + 10, centre_xz[1]))
    wood = {}
    for p, name in names.items():
        if name == trunk:
            e = max(abs(p[0] - centre_xz[0]), abs(p[2] - centre_xz[1]))
            h = p[1] - ground - 1
            wood[h] = max(wood.get(h, 0), e)
    t = Tree(tid, kind, ground, centre_xz, names, props, snow)
    t.trunk = trunk
    # storeys: runs of height (from h 6 up, clear of the root flare) where wood stands further out than the trunk
    limb = [h for h, e in wood.items() if h >= 6 and e > trunk_half + 1]
    t.storeys = _runs(limb)
    return t


def seat_tree(tid, snow="strict"):
    """A Tree for an elder or themed sapling from its template and pinned site, or None (a grove elder)."""
    elders = {e["id"]: e for e in _load(DATA / "elder_trees.json")["elders"]}
    themed = {s["id"]: s for s in _load(DATA / "themed_saplings.json")["saplings"]}
    if tid in elders:
        e = elders[tid]
        p = PREFABS / "tree_town" / ("elder_%s_%s" % (e["species"], e["variant"]))
        side = _load(p.with_suffix(".json"))
        ox, oy, oz = side["trunk_origin"]
        c = side["habitat"]["trunk"][0] // 2
        return _seat_template(_template(p.with_suffix(".nbt")), (ox, oy, oz), (ox + c, oz + c), e["rotation"],
                              (e["x"], e["z"]), e["ground_y"], tid, "elder", snow, c)
    if tid in themed:
        s = themed[tid]
        p = PREFABS / "themed" / ("sapling_%s" % s["theme"])
        side = _load(p.with_suffix(".json"))
        ox, oy, oz = side["trunk_origin"]
        return _seat_template(_template(p.with_suffix(".nbt")), (ox, oy, oz), (ox, oz), s["rotation"], (s["x"], s["z"]),
                              s["ground_y"], tid, "themed", snow, 3)
    return None


def seat_world_tree(nest_xz, r, snow="strict"):
    """The world tree from its generator, kept only in the columns a nest's box can reach."""
    import tree_grove as TG
    import world_tree as WT
    b, dims = TG.big_tree("oak", "a", "world")
    c = dims["trunk"][0] // 2
    ox, oz, oy = WT.CENTRE[0] - c, WT.CENTRE[1] - c, WT.GROUND + 1
    keep = {(x + dx, z + dz) for x, z in nest_xz for dx in range(-r - 1, r + 2) for dz in range(-r - 1, r + 2)}
    names, props = {}, {}
    for (x, y, z), blk in b.blocks.items():
        wx, wz = ox + x, oz + z
        if (wx, wz) in keep:
            names[(wx, oy + y, wz)] = blk[0] if isinstance(blk, tuple) else blk
    t = Tree(WORLD_TREE, "world", WT.GROUND, tuple(WT.CENTRE), names, props, snow)
    # the generator's own storeys, as heights over the builder's y0 = ground + 1
    t.storeys = [tuple(s) for s in dims["floor_tier_y"]]
    t.crown_y = tuple(dims["crown_y"])
    return t


# ------------------------------------------------------------------------------------------------ the checks
def _wood_checks(tree, rec, problems):
    p = rec["position"]
    cell = (p["x"], p["y"], p["z"])
    where = "%s at (%d, %d, %d), %d over the ground" % (rec["id"], cell[0], cell[1], cell[2], cell[1] - tree.ground)
    if cell not in tree.names or cell not in tree.solid:
        problems.append("PROBLEM %s: the cell is %s in the seated tree: OPEN AIR (or the floor), not wood"
                        % (where, tree.names.get(cell, "air")))
        return False
    if tree.names[cell] != rec["mimic"]:
        problems.append("PROBLEM %s: the tree's block here is %s but the record's mimic is %s"
                        % (where, tree.names[cell], rec["mimic"]))
    bad = []
    for dx, dy, dz in FACES:
        q = (cell[0] + dx, cell[1] + dy, cell[2] + dz)
        n = tree.names.get(q)
        if n is None or q not in tree.solid:
            bad.append((dx, dy, dz, n or "air"))
        elif n != rec["mimic"] and not (n.endswith("_log") and rec["mimic"].endswith("_log")) \
                and not (n.endswith("_leaves") and rec["mimic"].endswith("_leaves")):
            bad.append((dx, dy, dz, n))
    if bad:
        problems.append("PROBLEM %s: not hidden, face neighbours %s are not the tree's own %s"
                        % (where, bad, rec["mimic"]))
        return False
    return True


def _zone_checks(tree, rec, which, max_correction, problems, stats):
    p = rec["position"]
    r = rec["activated"]["spawn_range"]
    where = "%s at (%d, %d, %d)" % (rec["id"], p["x"], p["y"], p["z"])
    cy, cells, floor = tree.zone(p["x"], p["y"], p["z"], r, max_correction)
    if cy is None:
        problems.append("PROBLEM %s: no air within %d in its column, the area is dropped: it spawns NOTHING"
                        % (where, max_correction))
        return None
    if floor:
        problems.append("PROBLEM %s: its zone (centre %d over the ground) reaches the forest floor in %d columns: "
                        "birds would stand on the ground, not on the tree" % (where, cy - tree.ground, floor))
    if not cells:
        problems.append("PROBLEM %s: its zone holds no grounded cell of the tree" % where)
        return None
    hs = sorted(tree.h(c[1]) for c in cells)
    median = hs[len(hs) // 2]
    if which is not None:
        if which >= len(tree.storeys):
            problems.append("PROBLEM %s: the tree has no storey %d (storeys measured: %s)" % (where, which + 1, tree.storeys))
        else:
            lo, hi = tree.storeys[which]
            on = sum(1 for h in hs if lo <= h <= hi)
            if on == 0:
                problems.append("PROBLEM %s: its zone (centre %d over the ground) holds no standing cell on storey %d "
                                "(h %d..%d): its birds would not be on the limbs they are named for"
                                % (where, cy - tree.ground, which + 1, lo, hi))
            stats.setdefault("storey_share", []).append(round(on / len(hs), 3))
            # a LOW nest makes birds low: none of its cells is at or above the third run of limbs (the crown's
            # first limbs), which is where the old nests' birds all stood
            if which == 0 and tree.kind != "world" and len(tree.storeys) >= 3 and hs[-1] >= tree.storeys[2][0]:
                problems.append("PROBLEM %s: a low nest whose zone reaches h %d, into the crown limbs (from h %d)"
                                % (where, hs[-1], tree.storeys[2][0]))
    stats.setdefault("cells", []).append(len(cells))
    return {"cy": cy, "median": median, "cells": len(cells)}


def _footprints():
    """[(id, x, z, half_extent, height)] of the placements whose template file is here: the position is the anchor, the
    rotation and anchor mode are not modelled, so the footprint is the conservative square of the template's longest
    horizontal side either way round the position."""
    out = []
    for pl in _load(DATA / "placements.json")["placements"]:
        pos = pl.get("position")
        f = pl.get("file")
        if not (isinstance(pos, dict) and pos.get("x") is not None and f and (ROOT / f).is_file()):
            continue
        try:
            _, doc = nbt.load(ROOT / f)
            size = doc["size"]
        except Exception:
            continue
        out.append((pl["id"], pos["x"], pos["z"], max(size[0], size[2]), size[1]))
    return out


def _clear_checks(tree, rec, axis_offset, towns, foot, path_pts, problems, stats):
    p = rec["position"]
    where = "%s at (%d, %d, %d)" % (rec["id"], p["x"], p["y"], p["z"])
    for tid, x, z in towns:
        d = math.hypot(p["x"] - x, p["z"] - z)
        if d < OFF_TOWN - axis_offset:
            problems.append("PROBLEM %s: %.0f from the centre of %s, inside the elders' own 120-block clearance" % (where, d, tid))
    h = p["y"] - tree.ground - 1
    for pid, x, z, m, height in foot:
        if abs(p["x"] - x) <= m and abs(p["z"] - z) <= m and h <= height:
            problems.append("PROBLEM %s: inside the conservative footprint (+-%d, height %d) of placement %s at (%d, %d)"
                            % (where, m, height, pid, x, z))
    if path_pts:
        d = min(math.hypot(p["x"] - x, p["z"] - z) for x, z in path_pts)
        stats.setdefault("path_min", []).append(round(d, 1))
        if d <= PATH_HALF_WIDTH:
            problems.append("PROBLEM %s: %.1f from a route path cell: ON the path" % (where, d))


def _towns():
    return [(t["id"], t["centre"]["x"], t["centre"]["z"]) for t in _load(DATA / "towns.json")["towns"]
            if (t.get("centre") or {}).get("x") is not None]


def _path_points():
    return [tuple(c) for v in _load(DATA / "route_paths.json")["paths"].values() for c in v]


def _scope_species(spawns, pool):
    return {e["species"] for e in spawns["entries"]
            if e.get("mechanism") == "habitat_block" and e.get("scope") == pool and float(e.get("weight") or 0) > 0}


def audit(habitats=None, spawns=None, species=None, trees=None, world_tree=True, snow="strict"):
    """{'problems': [...], 'uncovered': [...], 'stats': {...}}. `trees` limits the per-tree checks (and the whole-set
    pool checks) to those ids: a test seats a mutated generator's output for a few trees and audits just those."""
    habitats = habitats or _load(DATA / "habitat_blocks.json")
    spawns = spawns or _load(DATA / "spawns.json")
    species = species or _load(DATA / "tree_bird_species.json")
    max_correction = int(_load(MAIN_JSON)["maxVerticalCorrectionBlocks"])
    problems, stats, uncovered = [], {}, []
    blocks = habitats["blocks"]
    recs = [b for b in blocks if b["id"].startswith(PREFIX)]
    designer = species["trees"]
    pool_ids = {h["id"] for h in spawns["habitats"]}

    def tree_of(rec):
        pool = rec["pool"].split(":", 1)[1]
        assert pool.startswith(PREFIX), rec["id"]
        rest = pool[len(PREFIX):]
        for t in list(designer) + [WORLD_TREE]:
            if rest.startswith(t + "_"):
                return t, rest[len(t) + 1:]
        return None, rest

    by_tree = {}
    for r in recs:
        t, band = tree_of(r)
        if t is None:
            problems.append("PROBLEM %s: its pool %s names no tree of the designer's file" % (r["id"], r["pool"]))
            continue
        by_tree.setdefault(t, []).append((band, r))
    if trees is not None:
        by_tree = {t: v for t, v in by_tree.items() if t in trees}
        for t in sorted(set(trees) - set(by_tree) - set(GROVE_ELDERS)):
            problems.append("PROBLEM %s: asked for, but no tbird record exists for it (a tree with no storey nests)" % t)
    towns, foot, path_pts = _towns(), _footprints(), _path_points()
    stats["structures_with_footprint"] = len(foot)

    # ---- the whole set: records <-> pools <-> the designer
    want_trees = (set(designer) - set(GROVE_ELDERS)) | {WORLD_TREE}
    have_trees = set(by_tree) if trees is None else None
    if have_trees is not None:
        missing = want_trees - have_trees
        extra = have_trees - want_trees
        if missing - {WORLD_TREE} or extra:
            problems.append("PROBLEM records vs designer: trees with no tbird record %s, records for trees that should "
                            "have none %s" % (sorted(missing - {WORLD_TREE}), sorted(extra)))
    for tid in sorted(by_tree):
        for band, r in by_tree[tid]:
            if r["pool"] != "cobblers:" + PREFIX + tid + "_" + band:
                problems.append("PROBLEM %s: pool %s does not follow tbird_<tree>_<band>" % (r["id"], r["pool"]))
            if r["pool"].split(":", 1)[1] not in pool_ids:
                problems.append("PROBLEM %s: pool %s is not a habitat of data/spawns.json" % (r["id"], r["pool"]))
            if tid != WORLD_TREE and r["id"] != PREFIX + tid + "_" + band:
                problems.append("PROBLEM %s: a small tree's nest is named tbird_<tree>_<band>" % r["id"])
            if r["style"] != "activated" or r.get("replace_spawns"):
                problems.append("PROBLEM %s: style/replace_spawns must be activated/false" % r["id"])
        if tid != WORLD_TREE:
            bands = sorted(b for b, _ in by_tree[tid])
            if bands != ["low", "mid"]:
                problems.append("PROBLEM %s: has nests for bands %s, want exactly one low and one mid" % (tid, bands))
            for band in ("low", "mid"):
                pool = PREFIX + tid + "_" + band
                if sorted(_scope_species(spawns, pool)) != sorted(designer[tid]["bands"][band]):
                    problems.append("PROBLEM pool %s: species %s are not the designer's %s band %s"
                                    % (pool, sorted(_scope_species(spawns, pool)), band, designer[tid]["bands"][band]))
            if sorted(_scope_species(spawns, tid)) != sorted(designer[tid]["bands"]["crown"]):
                problems.append("PROBLEM pool %s: species %s are not the designer's crown band %s"
                                % (tid, sorted(_scope_species(spawns, tid)), designer[tid]["bands"]["crown"]))
    if trees is None:
        used = {r["pool"].split(":", 1)[1] for r in recs}
        orphans = sorted(h for h in pool_ids if h.startswith(PREFIX) and h not in used)
        if orphans:
            problems.append("PROBLEM pools with no record: %s" % orphans)
        for g in GROVE_ELDERS:
            if g in by_tree:
                problems.append("PROBLEM %s has tbird records but no geometry here to audit them against" % g)

    # ---- no two habitat blocks share a cell or touch
    cells = {}
    for b in blocks:
        q = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
        cells.setdefault(q, []).append(b["id"])
    scan = {r["id"] for v in by_tree.values() for _, r in v}
    for b in blocks:
        if b["id"] not in scan:
            continue
        q = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
        if len(cells[q]) > 1:
            problems.append("PROBLEM %s: shares its cell with %s" % (b["id"], [i for i in cells[q] if i != b["id"]]))
        for dx, dy, dz in FACES:
            o = cells.get((q[0] + dx, q[1] + dy, q[2] + dz))
            if o:
                problems.append("PROBLEM %s: touches habitat block %s face to face (its mimic hides nothing there)" % (b["id"], o))

    # ---- per tree
    world_recs = by_tree.get(WORLD_TREE, []) if world_tree else []
    for tid in sorted(by_tree):
        if tid == WORLD_TREE:
            continue
        tree = seat_tree(tid, snow)
        if tree is None:
            uncovered.append(tid)
            continue
        info = {}
        for band, rec in by_tree[tid]:
            ok = _wood_checks(tree, rec, problems)
            which = {"low": 0, "mid": 1}.get(band)
            z = _zone_checks(tree, rec, which, max_correction, problems, stats) if ok else None
            info[band] = z
            axis = math.hypot(rec["position"]["x"] - tree.centre[0], rec["position"]["z"] - tree.centre[1])
            _clear_checks(tree, rec, axis, towns, foot, path_pts, problems, stats)
        # the four existing nests of the tree, by the same rule
        crown = []
        for b in blocks:
            if b["pool"] == "cobblers:" + tid and not b["id"].startswith(PREFIX):
                q = b["position"]
                cy, cl, _f = tree.zone(q["x"], q["y"], q["z"], b["activated"]["spawn_range"], max_correction)
                if cy is not None and cl:
                    crown.append(cy)
        if info.get("low") and info.get("mid") and info["low"]["cy"] >= info["mid"]["cy"]:
            problems.append("PROBLEM %s: the low nest's zone (centre %d) is not below the mid nest's (%d)"
                            % (tid, info["low"]["cy"] - tree.ground, info["mid"]["cy"] - tree.ground))
        if info.get("mid") and crown and info["mid"]["cy"] >= min(crown):
            problems.append("PROBLEM %s: the mid nest's zone (centre %d) is not below the existing nests' lowest (%d)"
                            % (tid, info["mid"]["cy"] - tree.ground, min(crown) - tree.ground))

    # ---- the world tree: its nests by the generator's own storeys and the doc's bands
    if world_recs:
        r = habitats.get("tbird_spawn_range", 16)
        wt = seat_world_tree([(rec["position"]["x"], rec["position"]["z"]) for _, rec in world_recs], r, snow)
        for band, rec in world_recs:
            label = rec["id"].rsplit("_", 1)[1]
            ok = _wood_checks(wt, rec, problems)
            storey = int(label[1]) - 1 if label[0] == "s" else None
            z = _zone_checks(wt, rec, storey, max_correction, problems, stats) if ok else None
            doc_band = None
            if label[0] == "s":
                doc_band = "low" if storey <= 1 else "mid" if storey <= 4 else "high"
            elif label[0] == "c":
                doc_band = "crown"
                if wt.crown_y[0] > rec["position"]["y"] - wt.ground - 1 or rec["position"]["y"] - wt.ground - 1 > wt.crown_y[1]:
                    problems.append("PROBLEM %s: not inside the canopy's height range %s" % (rec["id"], wt.crown_y))
            if doc_band != band:
                problems.append("PROBLEM %s: labelled %s, which the doc puts in band %s, but its pool is band %s"
                                % (rec["id"], label, doc_band, band))
            axis = math.hypot(rec["position"]["x"] - wt.centre[0], rec["position"]["z"] - wt.centre[1])
            _clear_checks(wt, rec, axis, towns, foot, path_pts, problems, stats)
            if z:
                stats.setdefault("world_cy", {})[label] = z["cy"] - wt.ground
        per = {}
        for k, v in stats.get("world_cy", {}).items():
            if k[0] == "s":
                per.setdefault(int(k[1]), []).append(v)
        for i in sorted(per):
            if i + 1 in per and max(per[i]) >= min(per[i + 1]):
                problems.append("PROBLEM world tree: storey %d's zone centres %s are not below storey %d's %s"
                                % (i, per[i], i + 1, per[i + 1]))
    if trees is None:
        uncovered += [g for g in GROVE_ELDERS if g in designer]
    return {"problems": problems, "uncovered": uncovered, "stats": stats}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-world-tree", action="store_true")
    ap.add_argument("--snow", choices=["strict", "lenient"], default="strict")
    a = ap.parse_args(argv)
    res = audit(world_tree=not a.no_world_tree, snow=a.snow)
    for line in res["problems"]:
        print(line)
    for t in res["uncovered"]:
        print("UNCOVERED %s: no geometry here" % t)
    st = res["stats"]
    if st.get("cells"):
        print("zones audited %d, cells per zone %d..%d, storey share %s..%s, nearest route path %s"
              % (len(st["cells"]), min(st["cells"]), max(st["cells"]), min(st.get("storey_share", [0])),
                 max(st.get("storey_share", [0])), min(st.get("path_min", [0]))))
    print("%d problem(s), %d uncovered" % (len(res["problems"]), len(res["uncovered"])))
    return 1 if res["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
