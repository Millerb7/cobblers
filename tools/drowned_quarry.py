#!/usr/bin/env python
"""The Drowned Quarry under Lake Tilpey's east wall, from data/drowned_quarry.json: a flooded working, a hall, and the
lake's oldest Gyarados asleep in its sump.

The owner, 2026-10-09: "a large lake monster in Lake Tilpey, with an underwater cave a player with Dive can reach."
The Ursaluna den's idea (a creature, a place that suits it, strong enough that meeting it early is a mistake) built in
the other medium, on patterns the repository already runs, so nothing here is new machinery:

  the place     carved by this pack's carve functions, in the legendary chambers' and the den's order
                (tools/legendaries.py, tools/ursaluna_cave.py): a stone shell filled SOLID first, reaching `margin`
                blocks beyond every void block and never in a column's top `keep_natural_top` blocks, then the void
                cut out of it and FLOODED (a water fill, so no air pocket exists), then the paving, the pit, the pillars,
                the timber sets, the lanterns and the dressing. Rooms are axis-aligned boxes and one round pit, voxelised
                from the record and written as boxes (one `fill` per maximal box, never over 32,768 blocks).
  the creature  a Pokemon entity, summoned by the re-application through tools/chunk_look.py's look-then-act chain
                (N155: a force-loaded chunk accepts a summon at once but its saved entities arrive later, so the act
                waits until one is seen and de-duplicates afterwards) and kept by this pack's keeper: the RESIDENTS'
                state machine (tools/resident_encounters.py): a dormant tag, a wake inside trigger_radius, settling
                back asleep when everyone has gone, and a return clock (the den's boss rules, the owner 2026-10-02).
  the gate      NONE of this pack's. The catch is gated by the level cap alone (data/level_cap.json): the Pokemon's
                level is the cap of eight badges, so it breaks free from every ball below that.

A guardian (the blackout's persistent claim holder, tag cobblers.guardian) is never touched here, and still counts as
present, as tools/resident_encounters.py does. The summon is a MACRO line (`drowned_quarry/spawn_at`): a plain
`spawnpokemonat` written in a function spawns nothing when parsed at server start (EXP-046).

Ground comes from tools/ground.py (the canonical heightmap, rounded) and the lake from tools/water_mask.py, never from
a world.

  python tools/drowned_quarry.py                  # -> build/datapacks/cobblers_drowned_quarry
  python tools/drowned_quarry.py --report         # the geometry, the measured cover and the steps; nothing written
  python tools/drowned_quarry.py probes [--write] # presence probes -> data/world_probes.json 'drowned_quarry'
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data" / "drowned_quarry.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_drowned_quarry"
SCHEMA = "cobblers.drowned-quarry/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
OBJ = "cobblers.dq"
PRESENT = -2147483648   # the return clock's "seen present" value; any other value is the game time it was first missed
FILL_MAX = 32768
CLEAR_LEVEL = "minecraft:air"


class QuarryError(ValueError):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise QuarryError("%s: schema must be %s" % (path, SCHEMA))
    g, m = doc["geometry"], doc["monster"]
    pts = g["road"]["points"]
    for a, b in zip(pts, pts[1:]):
        if a[0] != b[0] and a[1] != b[1]:
            raise QuarryError("the road is axis-aligned: %s -> %s is not" % (a, b))
    if not (0 < m["trigger_radius"] < m["keeper"]["settle_radius"]):
        raise QuarryError("the wake must be inside the settle radius, or it lies down mid-fight")
    k = m["keeper"]
    if k["spawn_clear"] >= k["spawn_radius"]:
        raise QuarryError("spawn_clear must be inside spawn_radius, or nothing ever spawns")
    if k["cooldown_ticks"] < 20 * 60 * 30:
        raise QuarryError("the return clock is under half an hour: a boss that returns faster is a farm "
                          "(the owner, 2026-10-02: 'one that returns is a place')")
    if k["absent_passes"] < 2:
        raise QuarryError("absent_passes must be at least 2 (entities load a moment after their chunk)")
    if (m["awake_nbt"] or {}).get("Unbattleable") != "0b" or "PoseType" in m["awake_nbt"]:
        raise QuarryError("a wake that leaves Unbattleable on is not a fight; only PoseType SLEEP is proven (EXP-023)")
    if "uncatchable" in m.get("spawn_properties", []):
        raise QuarryError("`uncatchable` cannot be cleared on a spawned Pokemon (data/sapling_celebi.json)")
    caps = json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))["level_caps"]["upper_bound_by_badges"]
    if m["level"] > caps["8"]:
        raise QuarryError("level %d is over the eight-badge cap %d: no ball would ever hold it" % (m["level"], caps["8"]))
    return doc


# ------------------------------------------------------------------ the voxels


def _h32(x, z, salt):
    d = hashlib.sha256(("%d,%d,%s" % (x, z, salt)).encode()).digest()
    return int.from_bytes(d[:4], "big") / 2 ** 32


def road_rects(doc):
    """Inclusive (x0, z0, x1, z1) per straight run of the road, each widened by half_width on every side so corners are
    full squares."""
    hw = doc["geometry"]["road"]["half_width"]
    pts = doc["geometry"]["road"]["points"]
    out = []
    for (xa, za), (xb, zb) in zip(pts, pts[1:]):
        out.append((min(xa, xb) - hw, min(za, zb) - hw, max(xa, xb) + hw, max(za, zb) + hw))
    return out


class Model:
    """Every block the carve writes, as boolean arrays indexed [y - y0, z - z0, x - x0]."""

    def __init__(self, doc, ground):
        g = doc["geometry"]
        self.doc = doc
        self.floor = int(g["floor_y"])
        m = self.margin = int(g["margin"])
        rd, hall, pit = g["road"], g["hall"], g["pit"]
        rects = road_rects(doc)
        self.rects = rects
        hx, hz = hall["x"], hall["z"]
        cx, cz = pit["centre"]
        r = pit["radius"]
        self.pit_floor = self.floor - int(pit["depth"])
        xs = [q[0] for q in rects] + [q[2] for q in rects] + list(hx) + [cx - r, cx + r]
        zs = [q[1] for q in rects] + [q[3] for q in rects] + list(hz) + [cz - r, cz + r]
        pad = m + 2
        self.x0, self.x1 = min(xs) - pad, max(xs) + pad
        self.z0, self.z1 = min(zs) - pad, max(zs) + pad
        self.y0 = self.pit_floor - m - 1
        self.y1 = self.floor + max(int(hall["height"]), int(rd["height"])) + 1 + m
        nx, nz, ny = self.x1 - self.x0 + 1, self.z1 - self.z0 + 1, self.y1 - self.y0 + 1
        self.G = ground.box(self.x0, self.z0, self.x1, self.z1)
        X = np.arange(self.x0, self.x1 + 1)[None, None, :]
        Z = np.arange(self.z0, self.z1 + 1)[None, :, None]
        Y = np.arange(self.y0, self.y1 + 1)[:, None, None]
        self.X, self.Z, self.Y = X, Z, Y
        road = np.zeros((ny, nz, nx), bool)
        yr = (Y >= self.floor + 1) & (Y <= self.floor + int(rd["height"]))
        for x0, z0, x1, z1 in rects:
            road |= yr & (X >= x0) & (X <= x1) & (Z >= z0) & (Z <= z1)
        hallv = (Y >= self.floor + 1) & (Y <= self.floor + int(hall["height"])) & (X >= hx[0]) & (X <= hx[1]) & \
                (Z >= hz[0]) & (Z <= hz[1])
        pil = hall["pillars"]
        pillars = np.zeros_like(hallv)
        for px in pil["xs"]:
            for pz in pil["zs"]:
                pillars |= (X >= px - pil["half"]) & (X <= px + pil["half"]) & (Z >= pz - pil["half"]) & \
                           (Z <= pz + pil["half"]) & (Y >= self.floor) & (Y <= self.floor + int(hall["height"]))
        hallv &= ~pillars
        circle = (X - cx) ** 2 + (Z - cz) ** 2 <= r * r
        pitv = circle & (Y >= self.pit_floor + 1) & (Y <= self.floor)
        self.pillars = pillars
        self.void = road | hallv | pitv
        self.pit_cols = circle[0]
        under = Y <= (self.G[None] - int(g["keep_natural_top"]))
        self.shell = _dilate(self.void, m) & under
        # the floor: a block at floor_y under every void column that has a void layer at floor_y + 1, not in the pit
        above = self.void[self.floor + 1 - self.y0]
        self.floor_cols = above & ~self.pit_cols
        self.pit_floor_cols = self.pit_cols
        self.road_cols = road[self.floor + 1 - self.y0]
        self.top = self.floor + max(int(hall["height"]), int(rd["height"]))

    def runs_of(self, mask3d):
        """Inclusive (x0, y0, z0, x1, y1, z1) boxes covering `mask3d` exactly, none over FILL_MAX blocks."""
        return boxes(mask3d, self.x0, self.y0, self.z0)

    def layer(self, y, cols):
        m = np.zeros_like(self.void)
        m[y - self.y0] = cols
        return m

    def bbox(self):
        return self.x0, self.z0, self.x1, self.z1


def _dilate(mask, m):
    """Box (Chebyshev) dilation by m in all three axes, separably."""
    out = mask
    for axis in range(3):
        acc = out.copy()
        for k in range(1, m + 1):
            fwd = np.zeros_like(out)
            bwd = np.zeros_like(out)
            sl = [slice(None)] * 3
            sl2 = [slice(None)] * 3
            sl[axis], sl2[axis] = slice(k, None), slice(None, -k)
            fwd[tuple(sl)] = out[tuple(sl2)]
            bwd[tuple(sl2)] = out[tuple(sl)]
            acc |= fwd | bwd
        out = acc
    return out


def boxes(mask, x0, y0, z0):
    """A list of inclusive (x0, y0, z0, x1, y1, z1) boxes that cover `mask` exactly. Per layer, runs along x are merged
    across consecutive z into rectangles; identical rectangles in consecutive layers merge into a box; a box over
    FILL_MAX blocks is split along y."""
    ny, nz, nx = mask.shape
    layers = []
    for yi in range(ny):
        layer = mask[yi]
        if not layer.any():
            layers.append([])
            continue
        active = {}
        rects = []
        for zi in range(nz + 1):
            row = {}
            if zi < nz and layer[zi].any():
                d = np.diff(np.concatenate(([0], layer[zi].astype(np.int8), [0])))
                for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
                    row[(int(a), int(b) - 1)] = True
            for key in list(active):
                if key not in row:
                    rects.append((key[0], active.pop(key), key[1], zi - 1))
            for key in row:
                active.setdefault(key, zi)
        layers.append(rects)
    out = []
    open_ = {}
    for yi in range(ny + 1):
        cur = set(layers[yi]) if yi < ny else set()
        for key in list(open_):
            if key not in cur:
                ys = open_.pop(key)
                out.append((key, ys, yi - 1))
        for key in cur:
            open_.setdefault(key, yi)
    res = []
    for (xa, za, xb, zb), ya, yb in out:
        area = (xb - xa + 1) * (zb - za + 1)
        step = max(1, FILL_MAX // area)
        y = ya
        while y <= yb:
            top = min(yb, y + step - 1)
            res.append((xa + x0, y + y0, za + z0, xb + x0, top + y0, zb + z0))
            y = top + 1
    res.sort(key=lambda b: (b[1], b[0], b[2]))
    return res


# ------------------------------------------------------------------ the dressing (every block a setblock)


def frame_positions(doc):
    """[(axis, along, across_centre)] for each timber set: axis 'x' = the run goes along x and the set spans z."""
    f = doc["geometry"]["frames"]
    rd = doc["geometry"]["road"]
    pts = rd["points"]
    out = []
    for i, ((xa, za), (xb, zb)) in enumerate(zip(pts, pts[1:])):
        if za == zb:                                   # a run along x
            lo, hi = sorted((xa, xb))
            start = rd["portal_x"] + f["from_portal"] if i == 0 else lo + f["stop_before_corner"]
            end = hi - f["stop_before_corner"]
            out += [("x", p, za) for p in range(start, end + 1, f["every"])]
        else:                                          # a run along z
            lo, hi = sorted((za, zb))
            start, end = lo + f["stop_before_corner"], hi - f["stop_before_corner"]
            out += [("z", p, xa) for p in range(start, end + 1, f["every"])]
    return out


def dressing(doc, M, ground):
    """[(x, y, z, block)] for everything that is not a plain fill: floor wear, timber sets, hung lanterns, road posts,
    the crane, the stacks, the bones and the wreck. Order matters only where two entries share a cell (none do)."""
    g = doc["geometry"]
    b = g["blocks"]
    fl, hw, h = M.floor, g["road"]["half_width"], g["road"]["height"]
    out = []
    # floor wear: mossy and cracked bricks scattered by a hash of the column (deterministic, no random module)
    share = g["blocks"]["floor_wear_share"]
    for zi, xi in zip(*np.nonzero(M.floor_cols)):
        x, z = int(xi) + M.x0, int(zi) + M.z0
        u = _h32(x, z, "wear")
        if u < share[0]:
            out.append((x, fl, z, b["floor_wear"][0]))
        elif u < share[0] + share[1]:
            out.append((x, fl, z, b["floor_wear"][1]))
    # timber sets
    for axis, p, c in frame_positions(doc):
        for s in (-hw, hw):
            for y in range(fl + 1, fl + h):
                out.append((p, y, c + s, b["timber"] + "[axis=y]") if axis == "x" else (c + s, y, p, b["timber"] + "[axis=y]"))
        for s in range(-hw, hw + 1):
            beam = b["timber"] + ("[axis=z]" if axis == "x" else "[axis=x]")
            out.append((p, fl + h, c + s, beam) if axis == "x" else (c + s, fl + h, p, beam))
        out.append((p, fl + h - 1, c, b["light_hung"]) if axis == "x" else (c, fl + h - 1, p, b["light_hung"]))
    # hall lanterns, hung from the roof
    hl = g["hall_lanterns"]
    top = fl + g["hall"]["height"]
    for x in hl["xs"]:
        for z in hl["zs"]:
            if not M.pillars[top - M.y0, z - M.z0, x - M.x0]:
                out.append((x, top, z, b["light_hung"]))
    # road posts on the open road, on the ground (or the floor, whichever is higher), both sides
    rp = g["road_posts"]
    zc = g["road"]["points"][0][1]
    for x in range(rp["from_x"], rp["until_x"] + 1, rp["every"]):
        for side in (-1, 1):
            z = zc + side * rp["offset"]
            base = max(int(M.G[z - M.z0, x - M.x0]), fl) + 1
            for i, blk in enumerate(b["post"]):
                out.append((x, base + i, z, blk))
    d = g["dressing"]
    cr = d["crane"]
    mx, mz = cr["mast"]
    for y in range(fl + 1, fl + cr["mast_height"] + 1):
        out.append((mx, y, mz, b["timber"] + "[axis=y]"))
    top_y = fl + cr["mast_height"]
    for i in range(1, cr["boom_len"] + 1):
        out.append((mx + i, top_y, mz, b["timber"] + "[axis=x]"))
    bx = mx + cr["boom_len"]
    for i in range(1, cr["chain_drop"] + 1):
        out.append((bx, top_y - i, mz, b["chain"]))
    out.append((bx, top_y - cr["chain_drop"] - 1, mz, cr["block"]))
    for sx, sz in d["stacks"]:
        for dx in (0, 1):
            for dz in (0, 1):
                for dy in (1, 2):
                    out.append((sx + dx, fl + dy, sz + dz, b["pillar"]))
    cx, cz = g["pit"]["centre"]
    for dx, dz, hgt in d["bones"]:
        for k in range(hgt):
            out.append((cx + dx, M.pit_floor + 1 + k, cz + dz, b["bones"]))
    for x, y, z, blk in d["wreck"]:
        out.append((x, y, z, blk))
    return out


# ------------------------------------------------------------------ the pack


def _fill(box, block, extra=""):
    return "fill %d %d %d %d %d %d %s%s" % (box + (block, extra))


def carve_files(doc, M, ground):
    g = doc["geometry"]
    b = g["blocks"]
    head = ["# Generated by tools/drowned_quarry.py from data/drowned_quarry.json: the Drowned Quarry under Lake Tilpey's east wall",
            "# chunks-loaded-by: the re-application (forceload add %d %d %d %d over RCON before this runs)" % M.bbox()]
    shell = M.shell & ~M.void
    pil = M.pillars
    fn = {}
    fn["carve"] = head[:1] + ["function cobblers:%s/carve_shell" % doc["folder"],
                              "function cobblers:%s/carve_void" % doc["folder"],
                              "function cobblers:%s/carve_floor" % doc["folder"],
                              "function cobblers:%s/carve_dress" % doc["folder"]]
    fn["carve_shell"] = head + ["# 1. the shell, SOLID, %d blocks beyond every void block and never in a column's top %d blocks"
                                % (g["margin"], g["keep_natural_top"])] + [_fill(r, b["shell"]) for r in M.runs_of(shell)]
    fn["carve_void"] = head + ["# 2. the void, FLOODED: water source blocks, so there is no air in any room"] + \
        [_fill(r, "minecraft:water") for r in M.runs_of(M.void)]
    floor_lines = head + ["# 3. the paving (stone bricks) at floor_y under every void column, the pit's gravel floor, the pillars dressed"]
    floor_lines += [_fill(r, b["floor"]) for r in M.runs_of(M.layer(M.floor, M.floor_cols))]
    floor_lines += [_fill(r, g["pit"]["floor_block"]) for r in M.runs_of(M.layer(M.pit_floor, M.pit_floor_cols))]
    floor_lines += [_fill(r, b["pillar"]) for r in M.runs_of(pil)]
    fn["carve_floor"] = floor_lines
    dl = head + ["# 4. the wear, timber sets, lanterns, posts, crane, stacks, bones and wreck, one setblock each"]
    dl += ["setblock %d %d %d %s replace" % (x, y, z, blk) for x, y, z, blk in dressing(doc, M, ground)]
    fn["carve_dress"] = dl
    return fn


def _sel_xyz(m):
    x, y, z = m["spot"]
    return "x=%.1f,y=%d,z=%.1f" % (x, y, z)


def _at(m):
    x, y, z = m["spot"]
    return "%.1f %d %.1f" % (x, y, z)


def _sp(m):
    return 'nbt={Pokemon:{Species:"cobblemon:%s"}}' % m["species"]


def _nbt(d):
    return "{%s}" % ",".join("%s:%s" % kv for kv in d.items())


def keeper_files(doc):
    ns, fo = doc["namespace"], doc["folder"]
    m = doc["monster"]
    k = m["keeper"]
    T, D, G = m["tag"], m["dormant_tag"], m["guardian_tag"]
    sx, at, yaw = _sel_xyz(m), _at(m), m["yaw"]
    P = "%s:%s" % (ns, fo)
    x, y, z = m["spot"]
    mon = json.dumps({"text": m["message"], "color": "gold", "italic": True}, ensure_ascii=False)
    fn = {}
    fn["load"] = ["# Generated by tools/drowned_quarry.py from data/drowned_quarry.json",
                  "scoreboard objectives add %s dummy" % OBJ,
                  "# the return clock is set here only when it was never set: a restart never moves it",
                  "execute unless score #gone %s matches -2147483648.. run scoreboard players set #gone %s %d" % (OBJ, OBJ, PRESENT),
                  "scoreboard players set #resp %s %d" % (OBJ, k["cooldown_ticks"]),
                  "schedule function %s/keeper %dt replace" % (P, k["period_ticks"])]
    fn["keeper"] = ["# the keeper's loop: only while the sump's chunk is loaded (nobody has to be near for the return clock)",
                    "execute store result score #now %s run time query gametime" % OBJ,
                    "execute if loaded %.0f %d %.0f run function %s/keep" % (x, y, z, P),
                    "schedule function %s/keeper %dt replace" % (P, k["period_ticks"])]
    fn["keep"] = [
        "# Present: ours by tag (a guardian keeps our tag), or a guardian the blackout REBUILT, which does not, found by its",
        "# tag and species near the spot. Never a bare distance (THE SUMMON GUARD, R14C's failure).",
        "execute store result score #n %s if entity @e[type=cobblemon:pokemon,tag=%s]" % (OBJ, T),
        "execute if score #n %s matches 0 if entity @e[type=cobblemon:pokemon,tag=%s,%s,distance=..%d,%s] run "
        "scoreboard players set #n %s 1" % (OBJ, G, sx, k["guardian_search_radius"], _sp(m), OBJ),
        "# a duplicate (a spawn that raced a slow entity load): the furthest one goes, and NEVER a guardian",
        "execute if score #n %s matches 2.. run kill @e[type=cobblemon:pokemon,tag=%s,tag=!%s,%s,limit=1,sort=furthest]"
        % (OBJ, T, G, sx),
        "execute if score #n %s matches 1.. run scoreboard players set #abs %s 0" % (OBJ, OBJ),
        "execute if score #n %s matches 1.. run scoreboard players set #gone %s %d" % (OBJ, OBJ, PRESENT),
        "# hold it: home, wake, settle. A guardian is the blackout's and is never held here",
        "execute if score #n %s matches 1.. as @e[type=cobblemon:pokemon,tag=%s,tag=!%s] run function %s/hold" % (OBJ, T, G, P),
        "execute if score #n %s matches 1.. run return 0" % OBJ,
        "# absent on %d loaded passes in a row (entities load a moment after their chunk) before it counts as gone"
        % k["absent_passes"],
        "scoreboard players add #abs %s 1" % OBJ,
        "execute if score #abs %s matches ..%d run return 0" % (OBJ, k["absent_passes"] - 1),
        "# first seen gone (beaten, caught or killed: all one thing here): the clock starts now. Only this line moves it",
        "execute if score #gone %s matches %d run scoreboard players operation #gone %s = #now %s" % (OBJ, PRESENT, OBJ, OBJ),
        "scoreboard players operation #d %s = #now %s" % (OBJ, OBJ),
        "scoreboard players operation #d %s -= #gone %s" % (OBJ, OBJ),
        "execute if score #d %s < #resp %s run return 0" % (OBJ, OBJ),
        "# never conjured in front of anyone, and only for a player to meet it",
        "execute if entity @a[%s,distance=..%d] run return 0" % (sx, k["spawn_clear"]),
        "execute unless entity @a[%s,distance=..%d,gamemode=!spectator] run return 0" % (sx, k["spawn_radius"]),
        "function %s/spawn" % P]
    fn["hold"] = [
        "# as the Gyarados (never a guardian). DORMANT: held on its spot, facing its yaw; it wakes for a player within %d."
        % m["trigger_radius"],
        "execute if entity @s[tag=%s] unless entity @s[%s,distance=..%s] run tp @s %s %s 0" % (D, sx, k["home_tolerance"], at, yaw),
        "execute if entity @s[tag=%s] if entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/wake"
        % (D, sx, m["trigger_radius"], P),
        "# AWAKE: it lies down again on its spot when nobody is within %d (a fight fled is not won)" % k["settle_radius"],
        "execute if entity @s[tag=!%s] unless entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/settle"
        % (D, sx, k["settle_radius"], P)]
    fn["wake"] = ["# as the Gyarados: the trigger, a STATE CHECK on the keeper's own loop, never an advancement (CELEBI_WAKE.md 1)",
                  "tag @s remove %s" % D,
                  "data merge entity @s %s" % _nbt(m["awake_nbt"]),
                  "tellraw @a[%s,distance=..48] %s" % (sx, mon),
                  "playsound %s hostile @a[%s,distance=..48] %s 2 0.6" % (m["sound"], sx, at)]
    fn["settle"] = ["# as the Gyarados: everyone has gone, so it goes back to its spot and sleeps",
                    "tp @s %s %s 0" % (at, yaw),
                    "data merge entity @s %s" % _nbt(m["dormant_nbt"]),
                    "tag @s add %s" % D]
    props = " ".join(["level=%d" % m["level"], "scale_modifier=%s" % m["scale_modifier"]] + list(m["spawn_properties"]))
    fn["spawn_at"] = ["$spawnpokemonat $(x) $(y) $(z) %s %s" % (m["species"], props)]
    fn["spawn"] = ["# a wild Gyarados through the macro (EXP-046), then bound at once",
                   "function %s/spawn_at {x:\"%.1f\",y:%d,z:\"%.1f\"}" % (P, x, y, z),
                   "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..3,%s,limit=1,sort=nearest] run function %s/bind"
                   % (at, T, _sp(m), P)]
    fn["bind"] = ["# as the new Gyarados: tagged, kept from the despawner (PersistenceRequired, EXP-041), dormant on its spot",
                  "tag @s add %s" % T, "tag @s add %s" % D,
                  "data merge entity @s %s" % _nbt(m["dormant_nbt"]),
                  "tp @s %s %s 0" % (at, yaw),
                  "scoreboard players set #gone %s %d" % (OBJ, PRESENT),
                  "scoreboard players set #abs %s 0" % OBJ]
    return fn


def chain_names(doc):
    ns, fo = doc["namespace"], doc["folder"]
    return "%s:%s/place" % (ns, fo), "dq_gyarados", doc["monster"]["tag"] + ".new"


def chain_files(doc):
    """The look-then-act chain the re-application starts (tools/chunk_look.py): act summons once the box's saved
    entities are in, and only if no tagged Gyarados stands; the de-duplication kills a second one."""
    import chunk_look as CL
    m = doc["monster"]
    base, holder, new = chain_names(doc)
    ns, fo = doc["namespace"], doc["folder"]
    scope = "type=cobblemon:pokemon,tag=%s" % m["tag"]
    x, y, z = m["spot"]
    box = (int(x) - 24, int(z) - 24, int(x) + 24, int(z) + 24)
    act = ["# the summon, once a look has seen this box's saved entities (or blind after %d ticks: a first run)" % CL.BLIND_TICKS,
           "execute unless entity @e[%s] run function %s:%s/spawn_new" % (scope, ns, fo)]
    fns = CL.chain(base, box, ["@e[%s]" % scope], act, [scope], new, scope, holder, note="tools/drowned_quarry.py")
    out = {ref.split("/", 1)[1]: lines for ref, lines in fns.items()}
    out["spawn_new"] = ["# as the act: the summon, then the new Gyarados marked for the chain's de-duplication",
                        "function %s:%s/spawn" % (ns, fo),
                        "execute positioned %s as @e[%s,distance=..3,limit=1,sort=nearest] run tag @s add %s"
                        % (_at(m), scope, new)]
    return out, box


def files(doc, ground):
    ns, fo = doc["namespace"], doc["folder"]
    M = Model(doc, ground)
    fn = {}
    fn.update(carve_files(doc, M, ground))
    fn.update(keeper_files(doc))
    chain, _box = chain_files(doc)
    fn.update(chain)
    out = {"data/%s/function/%s/%s.mcfunction" % (ns, fo, n): "\n".join(v) + "\n" for n, v in fn.items()}
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/load" % (ns, fo)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT,
                                              "description": "Cobblers: the Drowned Quarry under Lake Tilpey (tools/drowned_quarry.py)"}},
                                    indent=2) + "\n"
    return out


# ------------------------------------------------------------------ the re-application


def placement_steps(doc=None, ground=None):
    """For tools/reapply.py: hold the chunks, carve, release, then the look-then-act chain that summons the Gyarados
    and the read-back of its count. The step holds nothing across the chain (a forceload is per chunk, not counted:
    a release after the chain's entry would drop the chunk under it)."""
    import chunk_look as CL
    import ground as G
    doc = doc or load()
    ground = ground or G.load()
    M = Model(doc, ground)
    ns, fo = doc["namespace"], doc["folder"]
    hold = "%d %d %d %d" % M.bbox()
    base, holder, _new = chain_names(doc)
    return [("cmd", "forceload add " + hold), ("wait", 3),
            ("fn", "%s:%s/carve" % (ns, fo)),
            ("cmd", "forceload remove " + hold)] + \
        CL.steps(base, holder, 1, "the Drowned Quarry's Gyarados")


def probes(doc, ground):
    """{'drowned_quarry': [probe]} in data/world_probes.json's shape (tools/presence_audit.py extra)."""
    M = Model(doc, ground)
    g = doc["geometry"]
    fl = M.floor
    rows = []

    def blk(what, x, y, z, state):
        rows.append({"what": what, "block": [int(x), int(y), int(z), state], "expect": True})

    px, pz = g["hall"]["pillars"]["xs"][0], g["hall"]["pillars"]["zs"][0]
    blk("a pillar of the hall (stone bricks)", px, fl + 6, pz, "minecraft:stone_bricks")
    blk("the roof over the nave (stone, the shell)", g["hall"]["x"][0] + 20, fl + g["hall"]["height"] + 1, g["road"]["points"][-1][1],
        "minecraft:stone")
    blk("the flooded nave (water, no air)", g["hall"]["x"][0] + 18, fl + 8, g["road"]["points"][-1][1], "minecraft:water")
    blk("the flooded adit (water)", g["road"]["portal_x"] + 14, fl + 3, g["road"]["points"][0][1], "minecraft:water")
    blk("the open cutting (water)", g["road"]["points"][0][0] + 20, fl + 3, g["road"]["points"][0][1], "minecraft:water")
    cx, cz = g["pit"]["centre"]
    blk("the sump's gravel floor", cx, M.pit_floor, cz, g["pit"]["floor_block"])
    blk("the sump's water", cx, M.pit_floor + 4, cz, "minecraft:water")
    cr = g["dressing"]["crane"]
    blk("the crane's mast (spruce log)", cr["mast"][0], fl + 5, cr["mast"][1], "minecraft:spruce_log[axis=y]")
    hl = g["hall_lanterns"]
    blk("a hall lantern, hung and waterlogged", hl["xs"][0], fl + g["hall"]["height"], hl["zs"][0], g["blocks"]["light_hung"])
    fp = frame_positions(doc)[0]
    ax, p, c = fp
    blk("the first timber set's beam", *((p, fl + g["road"]["height"], c) if ax == "x" else (c, fl + g["road"]["height"], p)),
        g["blocks"]["timber"] + ("[axis=z]" if ax == "x" else "[axis=x]"))
    sx, sy, sz = doc["monster"]["spot"]
    rows.append({"what": "the Gyarados of the sump (one tagged %s; absent while its return clock runs)" % doc["monster"]["tag"],
                 "hold": [int(sx), int(sy), int(sz)],
                 "entity": "@e[type=cobblemon:pokemon,tag=%s]" % doc["monster"]["tag"], "count": 1})
    return {"drowned_quarry": rows}


# ------------------------------------------------------------------ CLI


def report(doc, ground):
    M = Model(doc, ground)
    g = doc["geometry"]
    m = doc["monster"]
    lines = ["floor y%d; void voxels %d, shell %d, pillars %d; bbox x%d..%d z%d..%d y%d..%d"
             % (M.floor, int(M.void.sum()), int((M.shell & ~M.void).sum()), int(M.pillars.sum()),
                M.x0, M.x1, M.z0, M.z1, M.y0, M.y1)]
    Y = np.arange(M.y0, M.y1 + 1)[:, None, None]
    cover = np.where(M.void, M.G[None] - Y, 10 ** 6)
    X = np.arange(M.x0, M.x1 + 1)[None, None, :]
    for x in range(g["road"]["portal_x"] - 6, g["road"]["portal_x"] + 3):
        c = cover[:, :, x - M.x0]
        lines.append("x%d: least ground over a carved block %s" % (x, int(c.min()) if (c < 10 ** 6).any() else None))
    inner = X > g["road"]["portal_x"]
    lines.append("past portal_x %d: least ground over a carved block %d (margin %d needs %d)"
                 % (g["road"]["portal_x"], int(cover[M.void & inner].min()), M.margin, M.margin + 1))
    lines.append("monster %s L%d scale %s at %s; trigger %d" % (m["species"], m["level"], m["scale_modifier"], m["spot"], m["trigger_radius"]))
    lines.append("steps: " + json.dumps([list(s) for s in placement_steps(doc, ground)]))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", choices=("build", "probes"), default="build")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print the geometry and the steps; write nothing")
    ap.add_argument("--write", action="store_true", help="probes: merge into data/world_probes.json")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.report:
        print("\n".join(report(doc, g)))
        return 0
    if a.cmd == "probes":
        rows = probes(doc, g)
        if a.write:
            wp = ROOT / "data" / "world_probes.json"
            d = json.loads(wp.read_text(encoding="utf-8"))
            d["places"].update(rows)
            wp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print("wrote %d place(s) into data/world_probes.json" % len(rows))
        for k, v in rows.items():
            print(k, len(v), "probes")
        return 0
    written = files(doc, g)
    import function_limits
    bad = []
    for rel, text in written.items():
        if rel.endswith(".mcfunction"):
            bad += ["%s:%d %s: %s" % (rel, n, cmd, why)
                    for n, cmd, why in function_limits.check_lines(text.splitlines(), where=rel)]
    for msg in bad:
        print("ERROR %s" % msg)
    if bad:
        return 1
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in written.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    n = {k.rsplit("/", 1)[1][:-len(".mcfunction")]: sum(1 for l in v.splitlines() if l and not l.startswith("#"))
         for k, v in written.items() if "/carve" in k}
    print("drowned_quarry: %d files -> %s (carve commands %s)" % (len(written), out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
