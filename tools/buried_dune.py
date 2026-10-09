#!/usr/bin/env python
"""Undertow Basin, from data/buried_dune.json: a Sandaconda held UNDER the east coast dunes that rises out of the floor
of a basin the first time a player steps into it.

The sweep's gap 8 (docs/world-building/WORLD_SWEEP_2026-10-09.md section 7): F8 had 0 sites. The owner's shape for it: a
creature BURIED in or under the dunes that a player finds by its signs before they find it; it emerges, it is not waiting
in a room. Every part is an existing, proven piece and nothing is new machinery:

  the signs     blocks, written by `build` (R9BD): a basin scooped out of the dune (a cut wall on the high side, the slip
                face, and a shallow mouth toward the sea), four trails scored into the slope (a V, two deep at the
                centre, one at the edge), bone block ribs, spine and skull. NO SAND is written: the basin and the
                trails are cut out of the dune and the dune's own sand is the wall; the bones and the sandstone shell of
                the sleeper's bed are the only blocks, and none is a spawn-condition block.
  the sleeper   a wild Pokemon entity in a sealed sandstone chamber under the basin's floor, held by the residents'
                keeper (tools/resident_encounters.py resident_files(), CALLED, as tools/far_south.py does): spawned by a
                MACRO (EXP-046), tagged, dormant (NoAI) on its spot, kept from the despawner, respawned on the keeper's
                clock. This pack replaces the keeper's `hold`, `wake`, `settle` and `spawn`: the creature is dormant in
                the chamber and awake at the basin, so its leash and its settle are measured from where it rose.
  the emerging  `wake`, from the keeper's own loop: the first player within `trigger` of the chamber floor (3D, so the
                basin's floor and nothing above its rim) clears the dormant tag and NoAI, teleports the creature to the
                basin's floor and bursts sand there with the warden's emerge sound. Everyone gone, `settle` puts it back.
  the slip face `signs`, on the keeper's loop while it sleeps: sand runs down the cut wall at random points and a slow
                heartbeat plays within `ring`. Particles and sounds only; no block, flag or command block.
  the summon    tools/chunk_look.py's look-then-act chain (R18BD): a guarded macro spawn, bound at once.
  the catch     the level-cap pack (data/level_cap.json), unchanged: the creature is level 55, the cap with seven badges.

What this pack does NOT do: start a battle (Cobblemon 1.8.0 has no command for a wild battle), change Fight or Flight,
drop or give anything, or write to a world other than through its two steps. It adds no Habitat Block and no spawn entry.

  python tools/buried_dune.py                    # write build/datapacks/cobblers_buried_dune
  python tools/buried_dune.py report             # the measured geometry, the checks and the steps; writes nothing
  python tools/buried_dune.py probes [--write]   # the presence probes (into data/world_probes.json under `buried_dune`)

Ownership: the output is generated (build/, gitignored); data/buried_dune.json is the source. The ground rule
(tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py (the canonical heightmap, rounded).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import chunk_look as CL  # noqa: E402
import function_limits  # noqa: E402
import resident_encounters as RE  # noqa: E402
import southern_residents as SR  # noqa: E402

DATA = ROOT / "data" / "buried_dune.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_buried_dune"
PROBES = ROOT / "data" / "world_probes.json"
SCHEMA = "cobblers.buried-dune/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
SEA = 62          # data/world.json sea level
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()
# the plants a dune grows, cleared off a column before it is cut (never #minecraft:replaceable: it holds water)
PLANTS = ("minecraft:cactus", "minecraft:dead_bush", "minecraft:short_grass", "minecraft:tall_grass")
SAND_PARTICLE = 'minecraft:block{block_state:{Name:"minecraft:sand"}}'


class DuneError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise DuneError("%s: schema must be %s" % (path, SCHEMA))
    pk = doc["pokemon"]
    if not (0 < pk["trigger"] < pk["leash"]):
        raise DuneError("the trigger must be inside the leash")
    k = doc["build"]["keeper"]
    if k["spawn_clear"] >= k["spawn_radius"]:
        raise DuneError("spawn_clear must be inside spawn_radius, or nothing ever spawns")
    ids = [t["id"] for t in doc["trails"]]
    if len(ids) != len(set(ids)):
        raise DuneError("trail ids must be unique")
    return doc


def jload(name):
    return SR.jload(name)


def base(state):
    return state.split("[")[0].split("{")[0]


# ------------------------------------------------------------------ the plan


class Plan:
    """Every write of the place. `carve` is {(x, z): [y0, y1]}: air from y0 to y1 inclusive, y1 being the column's own
    ground (so a column is only ever cut DOWN from its top, never built up). `put` is {(x, y, z): state}."""

    def __init__(self, doc, g, wet):
        self.doc, self.g, self.wet = doc, g, wet
        self.cx, self.cz = doc["site"]["centre"]
        self.carve, self.put, self.fills = {}, {}, []
        self.bowl = {}          # (x, z) -> floor surface block y (T), only where it cuts
        self.slip = []          # the slip face's points (x, y, z)
        self.lights = []
        self.trail_cols = {}    # trail id -> {(x, z): depth}
        self.problems = []
        self._bowl()
        self._trails()
        self._chamber()
        self._bones()
        self._slip()

    # -- helpers
    def surface(self, x, z):
        """The top solid block y of a column AFTER the bowl: the ground, or the bowl's floor where it cuts."""
        return self.bowl.get((x, z), self.g(x, z))

    def cut(self, x, z, depth, tag):
        gy = self.g(x, z)
        if self.wet(x, z) or gy < self.doc["rules"]["min_ground"]:
            self.problems.append("%s: (%d, %d) is wet or ground y%d under the sea margin %d"
                                 % (tag, x, z, gy, self.doc["rules"]["min_ground"]))
            return
        y0 = gy - depth + 1
        cur = self.carve.get((x, z))
        self.carve[(x, z)] = [min(cur[0], y0) if cur else y0, gy]

    # -- the bowl
    def _bowl(self):
        b = self.doc["bowl"]
        a, bz, depth, rise, flat = b["semi_axis_x"], b["semi_axis_z"], b["depth"], b["rise"], b["flat"]
        gc = self.g(self.cx, self.cz)
        self.floor = gc - depth            # the surface block of the bowl's floor at the centre
        for dx in range(-a, a + 1):
            for dz in range(-bz, bz + 1):
                rr = (dx / a) ** 2 + (dz / bz) ** 2
                if rr > 1:
                    continue
                x, z = self.cx + dx, self.cz + dz
                t = self.floor + int(round(rise * max(0.0, (math.sqrt(rr) - flat) / (1 - flat))))
                gy = self.g(x, z)
                if t < gy:
                    self.bowl[(x, z)] = t
                    self.carve[(x, z)] = [t + 1, gy]
                    if self.wet(x, z) or gy < self.doc["rules"]["min_ground"]:
                        self.problems.append("bowl: (%d, %d) is wet or too low (y%d)" % (x, z, gy))

    # -- the trails
    def _trails(self):
        tp = self.doc["trail_profile"]
        for t in self.doc["trails"]:
            pts = [tuple(p) for p in t["waypoints"]]
            seg = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
            total = sum(seg)
            cols = {}
            step, s = 0.5, 0.0
            while s <= total:
                i, acc = 0, 0.0
                while i < len(seg) - 1 and acc + seg[i] < s:
                    acc += seg[i]
                    i += 1
                f = (s - acc) / seg[i] if seg[i] else 0.0
                px = pts[i][0] + f * (pts[i + 1][0] - pts[i][0])
                pz = pts[i][1] + f * (pts[i + 1][1] - pts[i][1])
                dx, dz = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
                n = math.hypot(dx, dz) or 1.0
                nx, nz = -dz / n, dx / n
                env = min(1.0, s / 6.0, (total - s) / 8.0) if t.get("end_pit") is None else min(1.0, s / 6.0)
                off = t["amplitude"] * env * math.sin(2 * math.pi * s / t["wavelength"] + t["phase"])
                cx_, cz_ = px + nx * off, pz + nz * off
                hw = tp["half_width"]
                for x in range(int(math.floor(cx_ - hw)) - 1, int(math.floor(cx_ + hw)) + 2):
                    for z in range(int(math.floor(cz_ - hw)) - 1, int(math.floor(cz_ + hw)) + 2):
                        d = math.hypot(x + 0.5 - cx_, z + 0.5 - cz_)
                        if d <= hw:
                            depth = tp["centre_depth"] if d <= 0.6 else tp["edge_depth"]
                            if depth > cols.get((x, z), 0):
                                cols[(x, z)] = depth
                s += step
            pit = t.get("end_pit")
            if pit:
                ex, ez = pts[-1]
                r, dp = pit["radius"], pit["depth"]
                for x in range(ex - r - 1, ex + r + 2):
                    for z in range(ez - r - 1, ez + r + 2):
                        d = math.hypot(x - ex, z - ez)
                        if d <= r + 0.5:
                            depth = max(1, int(round(dp * (1 - (d / (r + 0.5)) ** 2))))
                            if depth > cols.get((x, z), 0):
                                cols[(x, z)] = depth
            self.trail_cols[t["id"]] = cols
            for (x, z), depth in cols.items():
                if (x, z) in self.bowl:        # the bowl is deeper than any trail: it already cut this column
                    continue
                self.cut(x, z, depth, "trail " + t["id"])

    # -- the chamber
    def _chamber(self):
        c = self.doc["chamber"]
        hx, hz, h, cover = c["half_x"], c["half_z"], c["height"], c["cover"]
        self.roof = self.floor - cover
        self.top = self.roof - 1                 # the interior's top row
        self.bed = self.top - h + 1              # the interior's bottom row: where the creature stands
        self.shell_floor = self.bed - 1
        x0, x1, z0, z1 = self.cx - hx, self.cx + hx, self.cz - hz, self.cz + hz
        self.interior = (x0, self.bed, z0, x1, self.top, z1)
        self.outer = (x0 - 1, self.shell_floor, z0 - 1, x1 + 1, self.roof, z1 + 1)
        if self.bed < self.doc["rules"]["min_ground"] - 10:
            self.problems.append("chamber: its floor y%d is under the sea margin" % self.bed)
        low = min(self.surface(x, z) for x in range(x0 - 1, x1 + 2) for z in range(z0 - 1, z1 + 2))
        if low - self.roof < cover:
            self.problems.append("chamber: only %d natural block(s) over its roof at the lowest column (needs %d)"
                                 % (low - self.roof, cover))
        self.fills = [(self.outer, c["shell"]), (self.interior, "minecraft:air")]
        for sx in (x0, x1):
            for sz in (z0, z1):
                self.lights.append((sx, self.top, sz))
        for p in self.lights:
            self.put[p] = "minecraft:light[level=1]"

    # -- the bones
    def _bones(self):
        g = self.g
        taken = set()

        def pillar(x, z, hgt, axis="y"):
            if (x, z) in self.carve:
                self.problems.append("bones: (%d, %d) stands in a cut column (the bone would float)" % (x, z))
                return
            gy = g(x, z)
            for k in range(1, hgt + 1):
                self.put[(x, gy + k, z)] = "minecraft:bone_block[axis=%s]" % axis
            taken.add((x, z))
        for b in self.doc["bones"]:
            ax, az = (self.cx + b["at"][0], self.cz + b["at"][1]) if "at" in b else (0, 0)
            if b["kind"] == "ribs":
                for k in range(b["arcs"]):
                    for i, hh in enumerate(b["heights"]):
                        if b["axis"] == "z":
                            pillar(ax + k * b["arc_gap"], az + i, hh)
                        else:
                            pillar(ax + i, az + k * b["arc_gap"], hh)
            elif b["kind"] == "spine":
                fx, fz = self.cx + b["from"][0], self.cz + b["from"][1]
                tx, tz = self.cx + b["to"][0], self.cz + b["to"][1]
                n = max(abs(tx - fx), abs(tz - fz))
                axis = "x" if abs(tx - fx) >= abs(tz - fz) else "z"
                for i in range(0, n + 1, b["every"]):
                    x = int(round(fx + (tx - fx) * i / n))
                    z = int(round(fz + (tz - fz) * i / n))
                    if (x, z) in self.carve:
                        continue                 # a vertebra on the trail's own groove would float: skipped, not an error
                    gy = g(x, z)
                    self.put[(x, gy + 1, z)] = "minecraft:bone_block[axis=%s]" % axis
                    taken.add((x, z))
            elif b["kind"] == "skull":
                for dx in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        pillar(ax + dx, az + dz, 1 if (dx, dz) != (0, 0) else 2, "y")
                for dz in (-1, 1):
                    gy = g(ax, az + dz)
                    self.put[(ax, gy + 2, az + dz)] = "minecraft:bone_block[axis=x]"
                pillar(ax + 2, az - 1, 3)
                pillar(ax + 2, az + 1, 3)

    # -- the slip face
    def _slip(self):
        s = self.doc["bowl"]["slip_face"]
        a, bz = self.doc["bowl"]["semi_axis_x"], self.doc["bowl"]["semi_axis_z"]
        cand = []
        for (x, z), t in self.bowl.items():
            cut = self.g(x, z) - t
            dx, dz = x - self.cx, z - self.cz
            rr = (dx / a) ** 2 + (dz / bz) ** 2
            ang = math.degrees(math.atan2(dz, dx)) % 360
            if cut >= s["min_cut"] and s["rim_from"] <= math.sqrt(rr) <= 0.95:
                cand.append((ang, cut, x, z))
        lo, hi = s["arc_degrees"]
        picks = []
        for i in range(s["points"]):
            tgt = lo + (hi - lo) * i / max(1, s["points"] - 1)
            best = None
            for ang, cut, x, z in cand:
                if not (lo - 5 <= ang <= hi + 5):
                    continue
                score = abs(ang - tgt) - 0.8 * cut
                if best is None or score < best[0]:
                    best = (score, x, z)
            if best:
                picks.append((best[1], self.g(best[1], best[2]), best[2]))
        self.slip = list(dict.fromkeys(picks))
        if len(self.slip) < max(2, s["points"] // 2):
            self.problems.append("slip face: only %d point(s) found where the wall is cut %d or more"
                                 % (len(self.slip), s["min_cut"]))

    # -- derived geometry
    def anchor(self):
        return self.cx, self.bed, self.cz

    def rise_at(self):
        """(x, feet y, z) where it comes up: the bowl's floor, one above its surface block."""
        return self.cx, self.floor + 1, self.cz

    def columns(self):
        cols = set(self.carve) | {(k[0], k[2]) for k in self.put}
        o = self.outer
        cols |= {(x, z) for x in range(o[0], o[3] + 1) for z in range(o[2], o[5] + 1)}
        return cols

    def box(self, margin=2):
        cols = self.columns()
        xs, zs = [c[0] for c in cols], [c[1] for c in cols]
        return [min(xs) - margin, min(zs) - margin, max(xs) + margin, max(zs) + margin]


# ------------------------------------------------------------------ the siting rules (the builder's guards)


def siting(doc, plan, pts=None):
    """Problems, as strings, for the planned site."""
    import numpy as np
    rules = doc["rules"]
    probs = list(plan.problems)
    cols = plan.columns()
    pts = pts if pts is not None else authored_points()
    P = np.array([(a, b) for a, b, _f in pts], float)
    F = [f for _a, _b, f in pts]
    C = np.array(sorted(cols), float)
    best = (1e9, None, None)
    for i in range(0, len(C), 256):
        blk = C[i:i + 256]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] < best[0]:
            best = (float(d[j]), tuple(blk[j[0]]), F[j[1]])
    m = rules["authored_clearance"]
    if best[0] < m:
        probs.append("(%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                     % (best[1][0], best[1][1], best[0], best[2], m))
    cprobs, cbest = SR.corridor_check(doc["id"], cols, m)
    probs += cprobs
    for t in jload("towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            probs.append("within %d of town %s's footprint" % (m, t["id"]))
    for k, zone in jload("rift_zones.json")["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                probs.append("inside Rift zone %s" % k)
                break
    paths = np.array([p for pl in jload("route_paths.json")["paths"].values() for p in pl], float)
    dp = float(np.min(np.hypot(paths[:, 0] - plan.cx, paths[:, 1] - plan.cz)))
    if dp < rules["path_clearance"]:
        probs.append("%.0f blocks from a route path (needs %d)" % (dp, rules["path_clearance"]))
    pk = doc["pokemon"]
    ex, _ey, ez = plan.rise_at()
    for b in jload("habitat_blocks.json")["blocks"]:
        if b.get("style") != "activated":
            continue
        d = math.hypot(b["position"]["x"] - ex, b["position"]["z"] - ez)
        if d < b["activated"]["spawn_range"] + pk["leash"]:
            probs.append("its leash overlaps Habitat Block %s (%.0f, needs %d)"
                         % (b["id"], d, b["activated"]["spawn_range"] + pk["leash"]))
    sub, tier, ceiling = SR._sub_of(plan.cx, plan.cz)
    if sub != doc["subregion"]:
        probs.append("the centre is in %s, the record says %s" % (sub, doc["subregion"]))
    elif pk["level"] > ceiling:
        probs.append("L%d over %s's tier-%s ceiling %d" % (pk["level"], sub, tier, ceiling))
    cell = SR_cell(plan.cx, plan.cz)
    if cell != doc["cell"]:
        probs.append("the centre is in cell %s, the record says %s" % (cell, doc["cell"]))
    spawn = set(jload("spawn_blocks.json")["blocks"])
    allowed = set(doc["blocks"]["ids"])
    for state in list(plan.put.values()) + [f[1] for f in plan.fills]:
        b = base(state)
        if b not in allowed:
            probs.append("%s is not in data/buried_dune.json blocks.ids" % b)
        if b in spawn:
            probs.append("writes spawn-condition block %s (data/spawn_blocks.json)" % b)
    return probs, {"nearest_authored": best, "path": dp, "corridor": cbest}


def authored_points():
    """Every x/z any other data file authors (tools/southern_residents.py authored_points(), this file skipped), less
    our own probes in data/world_probes.json: they are this place's own coordinates, not somebody else's."""
    own = set()
    if PROBES.is_file():
        for pr in json.loads(PROBES.read_text(encoding="utf-8"))["places"].get("buried_dune") or []:
            c = pr["block"] if "block" in pr else pr["hold"]
            own.add((c[0], c[2]))
            own.add((c[0], c[1]))      # authored_points() reads [x, y, z] both ways
    return [p for p in SR.authored_points({"residents": []}, own_file=DATA)
            if not (p[2] == "world_probes.json" and (p[0], p[1]) in own)]


def SR_cell(x, z):
    grid = jload("world.json")["grid"]
    s = grid["cell_size"]
    return grid["row_labels"][int(z - grid["origin_z"]) // s] + grid["column_labels"][int(x - grid["origin_x"]) // s]


def check_records(doc, plan):
    """What the data records about the geometry is what the heightmap gives."""
    probs = []
    gc = plan.g(plan.cx, plan.cz)
    if doc["measured"]["centre_ground"] != gc:
        probs.append("measured.centre_ground is %s, the heightmap gives %d" % (doc["measured"]["centre_ground"], gc))
    return probs


# ------------------------------------------------------------------ the functions


def _runs(cols, key):
    """[(x0, x1, z, value)] runs of consecutive x with the same value of key(x, z, v), in a stable order."""
    out = []
    for (x, z) in sorted(cols, key=lambda c: (c[1], c[0])):
        v = key(x, z)
        if out and out[-1][2] == z and out[-1][1] == x - 1 and out[-1][3] == v:
            out[-1] = (out[-1][0], x, z, v)
        else:
            out.append((x, x, z, v))
    return out


def build_lines(plan):
    box = plan.box()
    out = ["# Generated by tools/buried_dune.py from data/buried_dune.json: %s" % plan.doc["name"],
           "# chunks-loaded-by: the re-application %s (forceload add %d %d %d %d over RCON before this runs)"
           % ((plan.doc["build"]["steps"]["blocks"],) + tuple(box)),
           "# 1. the plants off every column about to be cut (a cactus left standing over a cut column would drop)"]
    g = plan.g
    for x0, x1, z, (lo, hi) in _runs(plan.carve, lambda x, z: (g(x, z) + 1, g(x, z) + 3)):
        for p in PLANTS:
            out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, lo, z, x1, hi, z, p))
    out.append("# 2. the basin and the trails: air from each column's own ground down to its cut, nothing built up")
    for x0, x1, z, (lo, hi) in _runs(plan.carve, lambda x, z: tuple(plan.carve[(x, z)])):
        out.append("fill %d %d %d %d %d %d minecraft:air" % (x0, lo, z, x1, hi, z))
    out.append("# 3. the sleeper's bed: a sandstone shell, then the air inside, then four invisible lights (no hostile mob "
               "spawns in the dark)")
    for (a, b, c, d, e, f), state in plan.fills:
        out.append("fill %d %d %d %d %d %d %s" % (a, b, c, d, e, f, state))
    out.append("# 4. the bones, and the lights")
    for (x, y, z), st in sorted(plan.put.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2])):
        out.append("setblock %d %d %d %s" % (x, y, z, st))
    return out


def shim(doc):
    """tools/resident_encounters.py's doc shape for our keeper."""
    b = doc["build"]
    return {"build": {"namespace": b["namespace"], "folder": b["folder"], "tag": b["tag"], "dormant_tag": b["dormant_tag"],
                      "guardian_tag": b["guardian_tag"], "objective": b["objective"], "keeper": b["keeper"]},
            "rules": {"permanently_uncatchable": [],
                      "respawn_ticks_after_faint_death_or_catch": doc["pokemon"]["returns"]["respawn_ticks"]}}


def resident_record(doc):
    pk = doc["pokemon"]
    return {"id": pk["id"], "name": pk["name"], "species": pk["species"], "level": pk["level"],
            "build": {"yaw": pk["yaw"], "trigger": pk["trigger"], "leash": pk["leash"], "appears_after": None,
                      "message": pk["message"], "sound": pk["sound"], "dormant_extra": None, "stays_still": False}}


def _props(doc):
    pk = doc["pokemon"]
    return "level=%d scale_modifier=%s" % (int(pk["level"]), pk["scale_modifier"])


def _xyz(p):
    return "%.1f %d %.1f" % (p[0] + 0.5, p[1], p[2] + 0.5)


def _sel(p):
    return "x=%.1f,y=%d,z=%.1f" % (p[0] + 0.5, p[1], p[2] + 0.5)


def creature_files(doc, plan):
    """The residents' keeper for the Undertow: resident_files() called, then hold, wake, settle and spawn replaced."""
    b, k, pk = doc["build"], doc["build"]["keeper"], doc["pokemon"]
    ns, F = b["namespace"], b["folder"]
    e = resident_record(doc)
    sh = shim(doc)
    a, r = plan.anchor(), plan.rise_at()
    rf = RE.resident_files(sh, e, a, [], [], plan.box())
    rf.pop("%s/dress" % e["id"], None)
    rf.pop("%s/bind_new" % e["id"], None)       # the chain binds (summon_chain), so nothing would call it
    i = e["id"]
    P = "%s:%s/%s" % (ns, F, i)
    dtag, rtag, gtag = b["dormant_tag"], "%s.%s" % (b["tag"], i), b["guardian_tag"]
    sa, sr_ = _sel(a), _sel(r)
    home, rise = _xyz(a), _xyz(r)
    msg = json.dumps({"text": pk["message"], "color": "gold", "italic": True}, ensure_ascii=False)
    rf["%s/hold" % i] = [
        "# as the resident (never a guardian): asleep in its bed under the basin, or awake and leashed to where it rose",
        "execute if entity @s[tag=%s] unless entity @s[%s,distance=..%s] run tp @s %s %s 0" % (dtag, sa, k["home_tolerance"], home, pk["yaw"]),
        "execute if entity @s[tag=%s] if entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/wake"
        % (dtag, sa, pk["trigger"], P),
        "execute if entity @s[tag=!%s] unless entity @s[%s,distance=..%d] run tp @s %s %s 0" % (dtag, sr_, pk["leash"], rise, pk["yaw"]),
        "execute if entity @s[tag=!%s] unless entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/settle"
        % (dtag, sr_, pk["leash"] + pk["settle_margin"], P)]
    rf["%s/wake" % i] = [
        "# as the resident: the first player within the trigger of its bed. It comes up through the basin's floor",
        "tag @s remove %s" % dtag,
        "data merge entity @s {NoAI:0b}",
        "tp @s %s %s 0" % (rise, pk["yaw"]),
        "particle %s %s 3 0.6 3 0.2 240 normal" % (SAND_PARTICLE, rise),
        "playsound %s hostile @a[%s,distance=..48] %s 2 0.8" % (pk["sound"], sr_, rise),
        "tellraw @a[%s,distance=..48] %s" % (sr_, msg)]
    rf["%s/settle" % i] = [
        "# as the resident: everyone has gone, so it goes back to its bed under the basin and sleeps",
        "tp @s %s %s 0" % (home, pk["yaw"]),
        "data merge entity @s {NoAI:1b,PersistenceRequired:1b}",
        "tag @s add %s" % dtag,
        "particle %s %s 2 0.4 2 0.1 60 normal" % (SAND_PARTICLE, rise)]
    rf["%s/spawn" % i] = [
        "# a wild %s through the macro (EXP-046), then bound at once" % e["name"],
        "function %s:%s/spawn_at {x:\"%.1f\",y:%d,z:\"%.1f\",species:\"%s\",props:\"%s\"}"
        % (ns, F, a[0] + 0.5, a[1], a[2] + 0.5, RE.species(e), _props(doc)),
        "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..2,%s,limit=1,sort=nearest] run function %s/bind"
        % (home, b["tag"], RE.species_sel(e), P)]
    # the slip face and the heartbeat: signs, on the keeper's loop, while it sleeps (particles and sounds, nothing placed)
    sg = pk["signs"]
    lines = ["# the dune is not still (tools/buried_dune.py): run while the keeper loop is loaded at the basin",
             "# only while it sleeps, and only with a player in range",
             "execute unless entity @e[type=cobblemon:pokemon,tag=%s,tag=%s] run return 0" % (rtag, dtag),
             "execute unless entity @a[%s,distance=..%d,gamemode=!spectator] run return 0" % (sr_, sg["radius"]),
             "execute store result score #r %s run random value 1..3" % b["objective"]]
    for n, (x, y, z) in enumerate(plan.slip):
        lines.append("execute if score #r %s matches %d run particle %s %.1f %.1f %.1f 0.3 0.9 0.3 0.02 14 normal"
                     % (b["objective"], n % 3 + 1, SAND_PARTICLE, x + 0.5, y + 0.2, z + 0.5))
    lines += ["execute if score #r %s matches 1..2 run playsound minecraft:block.sand.step ambient @a[%s,distance=..32] %s 0.6 0.6"
              % (b["objective"], sr_, rise),
              "execute if entity @a[%s,distance=..%d,gamemode=!spectator] run playsound minecraft:entity.warden.heartbeat "
              "ambient @a[%s,distance=..%d] %s 0.7 0.5" % (sr_, sg["ring"], sr_, sg["ring"], rise)]
    rf["%s/signs" % i] = lines
    return rf


def summon_chain(doc, plan):
    """tools/chunk_look.py's look-then-act chain for the reapply: summon it once if the chunk holds none, and bind it."""
    b, pk = doc["build"], doc["pokemon"]
    ns, F, s = b["namespace"], b["folder"], b["summon"]
    e = resident_record(doc)
    i = e["id"]
    P = "%s:%s/%s" % (ns, F, i)
    rtag, gtag = "%s.%s" % (b["tag"], i), b["guardian_tag"]
    a = plan.anchor()
    home = _xyz(a)
    sel = RE.species_sel(e)
    k = b["keeper"]
    act = ["execute unless entity @e[type=cobblemon:pokemon,tag=%s] positioned %s "
           "unless entity @e[type=cobblemon:pokemon,tag=%s,distance=..%d,%s] "
           "unless entity @e[type=cobblemon:pokemon,distance=..4,%s] "
           "run function %s:%s/spawn_at {x:\"%.1f\",y:%d,z:\"%.1f\",species:\"%s\",props:\"%s\"}"
           % (rtag, home, gtag, pk["leash"] + k["guardian_search_margin"], sel, sel, ns, F,
              a[0] + 0.5, a[1], a[2] + 0.5, RE.species(e), _props(doc)),
           "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..4,%s,limit=1,sort=nearest] run function %s/bind"
           % (home, b["tag"], sel, P),
           "tag @e[type=cobblemon:pokemon,tag=%s] add %s" % (rtag, s["new_tag"])]
    x0, z0 = a[0] - 8, a[2] - 8
    chain = CL.chain(s["base"], (x0, z0, x0 + 16, z0 + 16), ["type=cobblemon:pokemon,tag=%s" % rtag], act,
                     ["type=cobblemon:pokemon,tag=%s,tag=!%s" % (rtag, gtag)], s["new_tag"],
                     "type=cobblemon:pokemon,tag=%s" % rtag, s["holder"], note="tools/buried_dune.py")
    return CL.files(chain)


def files(doc, g, wet=None, check=True):
    wet = wet or RE.Wet(g, [tuple(doc["site"]["centre"])])
    plan = Plan(doc, g, wet)
    if check:
        probs = siting(doc, plan)[0] + check_records(doc, plan)
        if probs:
            raise DuneError("buried_dune: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = doc["build"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    k = b["keeper"]
    lines = build_lines(plan)
    bad = function_limits.check_lines(lines, "%s/build" % F)
    if bad:
        raise DuneError("%s/build: %d command(s) the server would refuse: %s" % (F, len(bad), bad[:3]))
    fn = {"build": lines}
    fn.update(creature_files(doc, plan))
    a, r = plan.anchor(), plan.rise_at()
    i = doc["pokemon"]["id"]
    fn["spawn_at"] = ["# a macro, so the mod's command is parsed when it runs (EXP-046, .claude/rules/datapacks.md)",
                      "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]
    fn["load"] = ["# the Undertow's keeper state (tools/buried_dune.py, on tools/resident_encounters.py's keeper).",
                  "# A clock that has never been set starts READY (respawn ticks already elapsed), so a fresh world fills at once",
                  "scoreboard objectives add %s dummy" % obj,
                  "scoreboard players set #resp %s %d" % (obj, int(doc["pokemon"]["returns"]["respawn_ticks"])),
                  "execute store result score #ready %s run time query gametime" % obj,
                  "scoreboard players operation #ready %s -= #resp %s" % (obj, obj),
                  "execute unless score #%s.gone %s matches -2147483648.. run scoreboard players operation #%s.gone %s = #ready %s"
                  % (i, obj, i, obj, obj),
                  "execute unless score #%s.abs %s matches -2147483648.. run scoreboard players set #%s.abs %s 0" % (i, obj, i, obj),
                  "schedule function %s:%s/keeper %dt replace" % (ns, F, k["period_ticks"])]
    fn["keeper"] = ["execute store result score #now %s run time query gametime" % obj,
                    "execute if loaded %d %d %d run function %s:%s/%s/keep" % (a[0], a[1], a[2], ns, F, i),
                    "execute if loaded %d %d %d run function %s:%s/%s/signs" % (r[0], r[1], r[2], ns, F, i),
                    "schedule function %s:%s/keeper %dt replace" % (ns, F, k["period_ticks"])]
    out = {"data/%s/function/%s/%s.mcfunction" % (ns, F, n): "\n".join(v) + "\n" for n, v in fn.items()}
    for path, ls in summon_chain(doc, plan).items():
        out[path] = "\n".join(ls) + "\n"
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/load" % (ns, F)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: Undertow Basin (tools/buried_dune.py)"}}, indent=2) + "\n"
    return out, plan


# ------------------------------------------------------------------ the re-application


def _plan(doc=None, g=None):
    import ground as G
    doc = doc or load()
    g = g or G.load()
    return doc, g, Plan(doc, g, RE.Wet(g, [tuple(doc["site"]["centre"])]))


def placement_steps(doc=None, g=None):
    """R9BD, BEFORE R9E: hold the box, build, release (R9FS's shape)."""
    doc, g, plan = _plan(doc, g)
    b = doc["build"]
    hold = "%d %d %d %d" % tuple(plan.box())
    return [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (b["namespace"], b["folder"])),
            ("cmd", "forceload remove " + hold)]


def entity_steps(doc=None, g=None):
    """R18BD, after R18FS: the sleeper summoned once and bound, through the look-then-act chain (tools/chunk_look.py),
    which holds and releases its own forceload; the count read back is 1."""
    doc = doc or load()
    s = doc["build"]["summon"]
    return CL.steps(s["base"], s["holder"], 1, "the Undertow in its bed under Undertow Basin")


# ------------------------------------------------------------------ the probes


def probes(doc=None, g=None):
    """{"buried_dune": [probe]} in data/world_probes.json's shape, for tools/presence_audit.py --only extra."""
    doc, g, plan = _plan(doc, g)
    cx, cz = plan.cx, plan.cz
    a = plan.anchor()
    out = []

    def blk(what, x, y, z, state, expect=True):
        out.append({"what": what, "block": [x, y, z, state], "expect": expect})
    blk("the chamber's roof (sandstone) under the basin", cx, plan.roof, cz, doc["chamber"]["shell"])
    blk("the chamber's floor shell", cx, plan.shell_floor, cz, doc["chamber"]["shell"])
    blk("air where the sleeper lies", a[0], a[1], a[2], "minecraft:air")
    lx, ly, lz = plan.lights[0]
    blk("a light block that keeps the bed from spawning mobs", lx, ly, lz, "minecraft:light[level=1]")
    blk("the basin's floor surface is solid", cx, plan.floor, cz, "!air")
    blk("air over the basin's floor", cx, plan.floor + 1, cz, "minecraft:air")
    sx, sy, sz = plan.slip[0]
    blk("the slip face's top block is cut away", sx, sy, sz, "minecraft:air")
    t0 = doc["trails"][0]["id"]
    deepest = max(((k, v) for k, v in plan.trail_cols[t0].items() if k not in plan.bowl),
                  key=lambda kv: (kv[1], -abs(kv[0][0] - cx), kv[0]))
    (tx, tz), td = deepest
    blk("the %s trail's groove is cut (ground y%d)" % (t0, g(tx, tz)), tx, g(tx, tz), tz, "minecraft:air")
    bone = max((k for k, v in plan.put.items() if v.startswith("minecraft:bone_block") and "axis=y" in v),
               key=lambda k: (k[1], k))
    blk("a rib of bone block", bone[0], bone[1], bone[2], "minecraft:bone_block[axis=y]")
    i = doc["pokemon"]["id"]
    out.append({"what": "%s present after R18BD (ungated)" % i,
                "entity": "@e[type=cobblemon:pokemon,tag=%s.%s,nbt={Pokemon:{Species:\"%s\"}}]"
                          % (doc["build"]["tag"], i, doc["pokemon"]["species"]),
                "count": 1, "hold": [a[0], a[1], a[2]]})
    return {"buried_dune": out}


# ------------------------------------------------------------------ CLI


def report(doc, g):
    doc, g, plan = _plan(doc, g)
    probs, m = siting(doc, plan)
    probs += check_records(doc, plan)
    r, a = plan.rise_at(), plan.anchor()
    o = plan.outer
    lines = ["%s (%s, cell %s) centre %s ground y%d" % (doc["name"], doc["id"], doc["cell"], doc["site"]["centre"], g(plan.cx, plan.cz)),
             "bowl: %d columns cut, floor surface y%d (feet y%d), deepest cut %d, slip face points %s"
             % (len(plan.bowl), plan.floor, r[1], max(g(x, z) - t for (x, z), t in plan.bowl.items()),
                [list(p) for p in plan.slip]),
             "chamber: shell %s, interior y%d..y%d x%d..%d z%d..%d, roof y%d (%d natural block(s) over the bowl floor), "
             "creature's feet %s, it rises at %s" % (doc["chamber"]["shell"], plan.bed, plan.top, plan.interior[0],
                                                    plan.interior[3], plan.interior[2], plan.interior[5], plan.roof,
                                                    plan.floor - plan.roof, list(a), list(r)),
             "trails: %s; written columns %d; put %d; box %s (%d chunks)"
             % ({k: len(v) for k, v in plan.trail_cols.items()}, len(plan.carve), len(plan.put), plan.box(),
                ((plan.box()[2] >> 4) - (plan.box()[0] >> 4) + 1) * ((plan.box()[3] >> 4) - (plan.box()[1] >> 4) + 1)),
             "nearest authored %.0f (our column %s to data/%s); corridor box %.0f; route path %.0f"
             % (m["nearest_authored"][0], tuple(int(v) for v in m["nearest_authored"][1]), m["nearest_authored"][2],
                m["corridor"][0], m["path"])]
    lines += ["PROBLEM " + p for p in probs]
    lines.append("steps %s: %d actions; %s: %d actions" % (doc["build"]["steps"]["blocks"], len(placement_steps(doc, g)),
                                                          doc["build"]["steps"]["entities"], len(entity_steps(doc, g))))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "report", "probes"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.cmd == "report":
        print("\n".join(report(doc, g)))
        return 0
    if a.cmd == "probes":
        pr = probes(doc, g)
        if a.write:
            d = json.loads(PROBES.read_text(encoding="utf-8"))
            d["places"].update(pr)
            PROBES.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print("wrote %d place(s) into data/world_probes.json" % len(pr))
        for k, v in pr.items():
            print(k, len(v), "probes")
        return 0
    written, plan = files(doc, g)
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in written.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    n = sum(1 for l in written["data/%s/function/%s/build.mcfunction" % (doc["build"]["namespace"], doc["build"]["folder"])].splitlines()
            if l and not l.startswith("#"))
    print("buried_dune: %d files -> %s (build: %d commands)" % (len(written), out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
