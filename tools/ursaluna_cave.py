#!/usr/bin/env python
"""The Ursaluna's den west of Highwire, from data/ursaluna_cave.json: the cave, the sleeping bear and its keeper.

The owner, 2026-10-02: "make an ursuluna cave at 1504 164 1414, dig a solid size caev for a large ursuluna, have
teddiursa spawn on the outskirt and have an npc one players can talk to". Four parts, each on a pattern the
repository already uses, so nothing here is new machinery:

  the cave      carved by this pack's cave/carve function. The legendary chambers' order (tools/legendaries.py):
                a stone shell filled SOLID first, reaching `margin` blocks beyond every void block, then the void
                cut out of it, so "at least margin blocks of rock round every void" holds by construction. Unlike a
                legendary chamber the cave is not a box: a level half-elliptical passage runs from the mouth on a
                diagonal axis into a half-ellipsoid hall, voxelised from the record and written as one `fill` per
                run of blocks along z. The shell never writes the top `keep_natural_top` blocks of a column, so the
                hill's grass is its own and its surface is never raised.
  the bear      a Pokemon entity, summoned over RCON by the re-application (placement_steps below), because
                `spawnpokemonat` in a plainly parsed function spawns nothing (tools/sapling_celebi.py, EXP-046).
                This pack dresses it (the sleeping Celebi's flags, EXP-023) and keeps it. A barrier curtain across
                the hall protects it, as the barrier shell protects the Celebi.
  Teddiursa     NOT in this pack: a Habitat Block record in data/habitat_blocks.json (placed by
                tools/habitat_blocks.py with every other block) and a Habitat pool in data/spawns.json (compiled by
                tools/compile_spawns.py). This tool only reads them, for the report.
  the watcher   NOT in this pack: a conversation in data/dialogue.json, compiled with every other one into
                cobblers_dialogue by tools/compile_dialogue.py --all. npc_placements() names where the
                re-application's "npc" action puts it.

THE SUMMON GUARD keys on the tag and on the species, never on a bare distance. R14C (the Celebi) uses
`unless entity @e[type=cobblemon:pokemon,distance=..3]`, and a wild Pokemon wandering past the sapling has satisfied
that twice and suppressed the summon (docs/HANDOVER_SESSION.md). Here: no tagged bear anywhere loaded, and no
Ursaluna of any tag within 4 blocks of the den spot (an undressed one from an interrupted run, which dress_new then
takes).

Ground comes from tools/ground.py (the canonical heightmap, rounded), never from a world.

  python tools/ursaluna_cave.py                  # -> build/datapacks/cobblers_ursaluna_cave
  python tools/ursaluna_cave.py --report         # the geometry, the steps and the measured cover; nothing written
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data" / "ursaluna_cave.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_ursaluna_cave"
SCHEMA = "cobblers.ursaluna-cave/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
FN = "ursaluna_cave"
# every boundary in the record is inclusive to within EPS (exclusive for the curtain's far face): a block centre on
# a diagonal axis lands exactly on s = 0 or on an ellipse, and float rounding must not decide which side it falls
EPS = 1e-6


class CaveError(ValueError):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise CaveError("%s: schema must be %s" % (path, SCHEMA))
    c = doc["cave"]
    if c["den"]["curtain_from"] + c["den"]["curtain_thickness"] > doc["ursaluna"]["at_s"]:
        raise CaveError("the bear stands in front of its own curtain")
    if doc["ursaluna"].get("encounter") != "resident":
        raise CaveError("only a resident (asleep, unbattleable) bear is built; a fight is the owner's decision")
    if "uncatchable" in doc["ursaluna"].get("spawn_properties", []):
        raise CaveError("`uncatchable` cannot be cleared on a spawned Pokemon (data/sapling_celebi.json)")
    return doc


# ------------------------------------------------------------------ the frame


def frame(doc):
    """(origin x, origin z, axis unit (ux, uz), across unit (vx, vz)): block centres are measured from the mouth's."""
    mx, mz = doc["site"]["mouth"]
    ax, az = doc["site"]["axis"]
    n = math.hypot(ax, az)
    ux, uz = ax / n, az / n
    return mx + 0.5, mz + 0.5, (ux, uz), (-uz, ux)


def world_xz(doc, s, p):
    """The block column at (s along the axis, p across it)."""
    ox, oz, (ux, uz), (vx, vz) = frame(doc)
    return int(math.floor(ox + s * ux + p * vx)), int(math.floor(oz + s * uz + p * vz))


def floor_y(doc, ground):
    mx, mz = doc["site"]["mouth"]
    return ground(mx, mz)


# ------------------------------------------------------------------ the voxels


class Model:
    """Every block the carve writes, as boolean arrays indexed [y - y0, z - z0, x - x0]."""

    def __init__(self, doc, ground):
        c = doc["cave"]
        pa, ch, den = c["passage"], c["chamber"], c["den"]
        m = int(c["margin"])
        self.floor = floor_y(doc, ground)
        ox, oz, (ux, uz), (vx, vz) = frame(doc)
        reach = max(pa["to"], ch["centre"] + ch["half_length"]) + m + 2
        wide = max(pa["half_width"], ch["half_width"]) + m + 2
        xs = [ox + s * ux + p * vx for s in (-m - 2, reach) for p in (-wide, wide)]
        zs = [oz + s * uz + p * vz for s in (-m - 2, reach) for p in (-wide, wide)]
        self.x0, self.x1 = int(math.floor(min(xs))), int(math.ceil(max(xs)))
        self.z0, self.z1 = int(math.floor(min(zs))), int(math.ceil(max(zs)))
        self.y0 = self.floor - m
        self.y1 = self.floor + 1 + max(pa["height"], ch["height"]) + m
        X, Z = np.meshgrid(np.arange(self.x0, self.x1 + 1) + 0.5, np.arange(self.z0, self.z1 + 1) + 0.5)
        self.S = (X - ox) * ux + (Z - oz) * uz
        self.P = (X - ox) * vx + (Z - oz) * vz
        self.G = ground.box(self.x0, self.z0, self.x1, self.z1)
        ys = np.arange(self.y0, self.y1 + 1)
        E = (ys + 0.5 - (self.floor + 1))[:, None, None]          # a block centre's height over the floor's surface
        S, P = self.S[None], self.P[None]
        up = E > 0
        passage = up & (S >= pa["from"] - EPS) & (S <= pa["to"] + EPS) & ((P / pa["half_width"]) ** 2 + (E / pa["height"]) ** 2 <= 1 + EPS)
        chamber = up & (((S - ch["centre"]) / ch["half_length"]) ** 2 + (P / ch["half_width"]) ** 2
                        + (E / ch["height"]) ** 2 <= 1 + EPS)
        self.void = passage | chamber
        Y = ys[:, None, None]
        under = Y <= (self.G[None] - int(c["keep_natural_top"]))
        self.shell = _dilate(self.void, m) & under
        cf, ct = den["curtain_from"], den["curtain_from"] + den["curtain_thickness"]
        self.curtain = self.void & (S >= cf - EPS) & (S < ct - EPS)
        cols = self.void.any(axis=0)
        level = (self.floor <= self.G)        # never lay a floor block over air: outside the hill there is none
        self.floor_cols = cols & level
        self.den_cols = self.floor_cols & (self.S >= ct - EPS)
        self.hall_cols = self.floor_cols & ~self.den_cols
        self.lanterns = []
        for s, p in c["lanterns"]:
            x, z = world_xz(doc, s, p)
            col = self.void[:, z - self.z0, x - self.x0]
            if not col.any():
                raise CaveError("lantern at s=%s p=%s, column (%d, %d), is not over the cave" % (s, p, x, z))
            top = int(np.nonzero(col)[0].max()) + self.y0
            self.lanterns.append((x, top, z))
        u = doc["ursaluna"]
        bx, bz = world_xz(doc, u["at_s"], u["at_p"])
        self.bear = (bx, self.floor + 1, bz)

    def runs(self, mask3d):
        """Inclusive (x0, y0, z0, x1, y1, z1) boxes, one per run of True along z at each (y, x)."""
        out = []
        ny, nz, nx = mask3d.shape
        for yi in range(ny):
            layer = mask3d[yi]
            for xi in range(nx):
                col = layer[:, xi]
                if not col.any():
                    continue
                d = np.diff(np.concatenate(([0], col.astype(np.int8), [0])))
                for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
                    x, y = xi + self.x0, yi + self.y0
                    out.append((x, y, a + self.z0, x, y, b - 1 + self.z0))
        return out

    def floor_runs(self, cols):
        m = np.zeros_like(self.void)
        m[self.floor - self.y0] = cols
        return self.runs(m)

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


# ------------------------------------------------------------------ the pack


def _fill(box, block, extra=""):
    return "fill %d %d %d %d %d %d %s%s" % (box + (block, extra))


def carve_lines(doc, M):
    b = doc["cave"]["blocks"]
    out = ["# Generated by tools/ursaluna_cave.py from data/ursaluna_cave.json: the Ursaluna's den west of Highwire",
           "# chunks-loaded-by: the re-application (forceload add %d %d %d %d over RCON before this runs)" % M.bbox(),
           "# 1. the shell, SOLID, %d blocks beyond every void and never in a column's top %d blocks"
           % (doc["cave"]["margin"], doc["cave"]["keep_natural_top"])]
    out += [_fill(r, b["shell"]) for r in M.runs(M.shell)]
    out.append("# 2. the void: the passage and the hall")
    out += [_fill(r, "minecraft:air") for r in M.runs(M.void)]
    out.append("# 3. the floor, only where the floor is under the hill's own ground")
    out += [_fill(r, b["floor"]) for r in M.floor_runs(M.hall_cols)]
    out += [_fill(r, b["den_floor"]) for r in M.floor_runs(M.den_cols)]
    out.append("# 4. the curtain: barriers across the hall, in front of the den")
    out += [_fill(r, b["curtain"], " replace minecraft:air") for r in M.runs(M.curtain)]
    out.append("# 5. the lanterns, hanging from the roof")
    out += ["setblock %d %d %d %s replace" % (x, y, z, b["light"]) for x, y, z in M.lanterns]
    return out


def _at(M, doc):
    x, y, z = M.bear
    return "%.1f %d %.1f" % (x + 0.5, y, z + 0.5)


def _species_sel(doc):
    return 'nbt={Pokemon:{Species:"cobblemon:%s"}}' % doc["ursaluna"]["species"]


def files(doc, ground):
    ns = doc["namespace"]
    u = doc["ursaluna"]
    k = u["keeper"]
    tag = u["tag"]
    obj = "cobblers.ursaluna"
    M = Model(doc, ground)
    at = _at(M, doc)
    nbt = ",".join("%s:%s" % (key, v) for key, v in u["nbt"].items())
    fn = {
        "%s/carve" % FN: carve_lines(doc, M),
        "%s/load" % FN: ["scoreboard objectives add %s dummy" % obj,
                         "schedule function %s:%s/keeper %dt replace" % (ns, FN, k["period_ticks"])],
        "%s/dress_new" % FN: [
            "# run by the re-application just after its summon: the nearest undressed Ursaluna at the den spot",
            "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..4,%s,limit=1,sort=nearest] "
            "run function %s:%s/dress" % (at, tag, _species_sel(doc), ns, FN)],
        "%s/dress" % FN: ["data merge entity @s {%s}" % nbt,
                          "tag @s add %s" % tag,
                          "tp @s %s %s 0" % (at, u["yaw"])],
        "%s/keeper" % FN: ["execute positioned %s if entity @a[distance=..%d] run function %s:%s/keep"
                           % (at, k["player_radius"], ns, FN),
                           "schedule function %s:%s/keeper %dt replace" % (ns, FN, k["period_ticks"])],
        "%s/keep" % FN: ["execute store result score #n %s if entity @e[tag=%s]" % (obj, tag),
                         "execute if score #n %s matches 2.. run kill @e[tag=%s,limit=1,sort=random]" % (obj, tag),
                         "execute as @e[tag=%s] positioned %s unless entity @s[distance=..%s] run tp @s %s %s 0"
                         % (tag, at, k["home_tolerance"], at, u["yaw"])],
    }
    out = {"data/%s/function/%s.mcfunction" % (ns, n): "\n".join(v) + "\n" for n, v in fn.items()}
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/load" % (ns, FN)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT,
                                              "description": "Cobblers: the Ursaluna's den west of Highwire "
                                                             "(tools/ursaluna_cave.py)"}}, indent=2) + "\n"
    return out


# ------------------------------------------------------------------ the re-application


def summon_command(doc, ground, M=None):
    M = M or Model(doc, ground)
    u = doc["ursaluna"]
    at = _at(M, doc)
    props = ["level=%d" % int(u["level"]), "scale_modifier=%s" % u["scale_modifier"]] + list(u["spawn_properties"])
    return ("execute unless entity @e[tag=%s] positioned %s unless entity @e[type=cobblemon:pokemon,distance=..4,%s] "
            "run spawnpokemonat %s %s %s" % (u["tag"], at, _species_sel(doc), at, u["species"], " ".join(props)))


def placement_steps(doc=None, ground=None):
    """For tools/reapply.py: hold the chunks, carve, summon over RCON, dress, release. Same tuple shape as
    tools/legendaries.py placement_steps (R14L) and tools/sapling_celebi.py (R14C)."""
    import ground as G
    doc = doc or load()
    ground = ground or G.load()
    M = Model(doc, ground)
    ns = doc["namespace"]
    hold = "%d %d %d %d" % M.bbox()
    return [("cmd", "forceload add " + hold), ("wait", 3),
            ("fn", "%s:%s/carve" % (ns, FN)),
            ("cmd", summon_command(doc, ground, M)),
            ("wait", 1),
            ("fn", "%s:%s/dress_new" % (ns, FN)),
            ("cmd", "forceload remove " + hold)]


def npc_placements(doc=None):
    """[(conversation id, (x, y, z), npc class)] for tools/reapply.py's "npc" action, from the committed data alone."""
    doc = doc or load()
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    conv = next((c for c in dl["conversations"] if c["id"] == doc["npc"]["conversation"]), None)
    if conv is None or not conv.get("npc_id"):
        raise CaveError("%s is not a conversation with an NPC in data/dialogue.json" % doc["npc"]["conversation"])
    return [(conv["id"], tuple(doc["npc"]["at"]), "%s:%s" % (doc["namespace"], conv["npc_id"]))]


# ------------------------------------------------------------------ CLI


def report(doc, ground):
    M = Model(doc, ground)
    c = doc["cave"]
    m = int(c["margin"])
    Y = np.arange(M.y0, M.y1 + 1)[:, None, None]
    cover = np.where(M.void, M.G[None] - Y, 10 ** 6)
    inner = M.S[None] > c["open_mouth_until"]
    worst = int(cover[M.void & inner].min()) if (M.void & inner).any() else None
    lines = ["mouth %s ground y%d = floor; cave voxels %d, shell %d, curtain %d, lanterns %d"
             % (doc["site"]["mouth"], M.floor, int(M.void.sum()), int((M.shell & ~M.void).sum()),
                int(M.curtain.sum()), len(M.lanterns)),
             "bbox x%d..%d z%d..%d y%d..%d" % (M.x0, M.x1, M.z0, M.z1, M.y0, M.y1),
             "least ground over a carved block past s=%s: %s (margin %d needs %d)"
             % (c["open_mouth_until"], worst, m, m + 1),
             "bear at %s, yaw %s, scale %s, level %d" % (M.bear, doc["ursaluna"]["yaw"],
                                                          doc["ursaluna"]["scale_modifier"], doc["ursaluna"]["level"])]
    ch = c["chamber"]
    for s in (ch["centre"], doc["ursaluna"]["at_s"]):
        x, z = world_xz(doc, s, 0)
        col = M.void[:, z - M.z0, x - M.x0]
        across = M.void[M.floor + 1 - M.y0] & (np.abs(M.S - s) < 0.75)
        ps = M.P[across]
        lines.append("at s=%d (%d, %d): ground y%d, %d blocks of air over the floor, %.1f blocks across at the floor"
                     % (s, x, z, ground(x, z), int(col.sum()), float(ps.max() - ps.min() + 1)))
    for s in (0, 8, 17, 20, 25):
        x, z = world_xz(doc, s, 0)
        col = M.void[:, z - M.z0, x - M.x0]
        top = int(np.nonzero(col)[0].max()) + M.y0 if col.any() else None
        lines.append("passage s=%d (%d, %d): ground y%d, roof block y%s" % (s, x, z, ground(x, z), top))
    lines.append("steps: " + json.dumps([list(s) for s in placement_steps(doc, ground)]))
    try:
        lines.append("npc: %s" % (npc_placements(doc),))
    except CaveError as e:
        lines.append("npc: NOT PLACEABLE: %s" % e)
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print the geometry and the steps; write nothing")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.report:
        print("\n".join(report(doc, g)))
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
    n = sum(1 for l in written["data/%s/function/%s/carve.mcfunction" % (doc["namespace"], FN)].splitlines()
            if l and not l.startswith("#"))
    print("ursaluna_cave: %d files -> %s (carve: %d commands)" % (len(written), out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
