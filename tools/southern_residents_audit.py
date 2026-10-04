#!/usr/bin/env python
"""The six southern residents' offline audit: the emitted pack, the re-application steps and the dialogue records,
against data/southern_residents.json, every other data file and the canonical heightmap.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/southern_residents.py
to derive anything, nor tools/resident_encounters.py (whose keeper it calls). It reads the data, the heightmap
(tools/ground.py), the painted water (tools/water_mask.py) and the river corridors (data/rivers.json), and derives what
it expects with its own code: every structure's floor from max(ground) over its footprint, every other block on its own
column's ground, the ring and post positions from the record's geometry, every standing spot from the expected blocks
(the first two passable cells over something solid), never from the builder's "on" or its spot(). The only things taken
from the generator are its OUTPUTS: the pack and the steps it hands tools/reapply.py (main() asks for those, as
tools/resident_encounters_audit.py does). tests/test_southern_residents_audit.py mutates the GENERATOR's code and leaves
the data alone. The compiled dialogue is tools/compile_dialogue.py's output, checked as an artifact.

  ys        every pokemon.anchor, npc.feet, quest npc_at, reward npc_at, the cache's trigger and container, and the
            record's bbox, re-derived from the heightmap and the expected blocks
  writes    the build functions replayed: every block where the data puts it with the data's block (a structure's floor
            at max ground under its footprint, foundation under it), nothing off-plan, nothing missing; inside the
            bbox; blocks.ids only; no spawn condition (data/spawn_blocks.json) unless data/spawn_block_policy.json
            whitelists it for this place; no chest, no bed; nothing under the ground, and at ground level only a block
            the data swaps in there; nothing on a wet column but a post built for water (shaft waterlogged and at or
            under the water level, top above it); every clear is a logs/leaves/replaceable clear inside the bbox that
            never reaches water; every standing spot has two cells of room and is cleared
  siting    every written or cleared column, spot and anchor: at least rules.authored_clearance from every x/z authored
            in another data file (our own quest, conversation and reward records excepted by id; small boxes as filled
            rectangles), outside the keep-out box, rules.away_from, every town footprint + clearance and every Rift
            zone box, south of rules.south_of_z, and at least rules.path_clearance from every route path point
  residents level within the anchor's sub-region tier ceiling (data/encounter_design.json rules.hearts.next_cap); leash
            clear of every activated Habitat Block's spawn_range; catch window from data/trainers.json gym_ace_levels
            alone (above the cap before the gate, within the cap after it); the keeper's anchor, leash, trigger,
            settle, yaw, level and gate; every kill spares cobblers.guardian; a gated resident has no summon step and
            an ungated one exactly one, guarded on tag and species
  dialogue  every NPC: its conversation and quest exist and name each other; every node reachable, every next exists;
            the cursor's allowed values are the nodes; every field it reads or writes is declared in
            data/progression.json; the flags it reads are exactly the progression flags its record names, and every
            reward behind a flag is reachable only through that flag (in the data and in the compiled option); it is
            placed exactly once (R9F through an npc_grant record, or an R18SR step at its feet, class and yaw)
  rewards   each quest reward's contents are data/rewards.json's record's, and the compiled dialogue gives exactly
            those; the cache is a data/rewards.json cache whose container is the barrel the build writes
  hand-in   a consume_held_item may take ONE item: a compiled hand-in that replaces the whole main-hand slot with air
            is a fault unless the item cannot stack

NOT checked, and it needs a running server: that the blocks land, that the keeper spawns, holds and wakes the two
Pokemon, that the presence gate admits only a gym7_cleared player, that the NPCs appear and their dialogue runs, that
the cache pays once, that Hale's option appears after gym 8, that the gatehouse wall is in sight from the bench
(trees and buildings are not modelled), and every in-game item of the record's audit_checklist.

  python tools/southern_residents_audit.py [--pack build/datapacks/cobblers_southern_residents] [--source-root R] [-v]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_southern_residents"
RECORD = "southern_residents.json"
SCHEMA = "cobblers.southern-residents/1"
GUARDIAN = "cobblers.guardian"     # tools/blackout_pack.py: the tag every claim's guardian carries
CLEAR_TAGS = ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable")
PASSABLE = {"minecraft:air", "minecraft:red_carpet", "minecraft:brown_carpet"}
NEVER = {"minecraft:chest", "minecraft:trapped_chest", "minecraft:ender_chest"}
# Items whose stack is one, so emptying the hand slot takes exactly one (vanilla 1.21.1: buckets of fluid and milk,
# Item.Properties().stacksTo(1)). Anything else may be held as a stack, and the whole stack would go.
# Files whose boxes are AREAS every site stands inside by design, not places: a sub-region's or region's extent (the
# residents check requires the anchor to be in one). Their boxes count by their corners only, as a cell's do.
AREA_FILES = {"regions.json"}
UNSTACKABLE = {"minecraft:water_bucket", "minecraft:lava_bucket", "minecraft:milk_bucket", "minecraft:powder_snow_bucket"}


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, check, msg):
        self.errors.append("%s: %s" % (check, msg))

    def note(self, msg):
        self.notes.append(msg)


def jload(name, data=DATA):
    return json.loads((Path(data) / name).read_text(encoding="utf-8"))


def base(state):
    return state.split("[")[0].split("{")[0]


def vbase(v):
    """A block value of the record: a state string, or {"sign": {...}} -> the sign block's id."""
    if isinstance(v, dict):
        s = v["sign"]
        return "minecraft:%s_%ssign" % (s["wood"], "wall_" if "wall" in s else "")
    return base(v)


def _code(text):
    return [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]


# ------------------------------------------------------------------ the world, from data


class Water:
    """(x, z) -> the water surface y, or None where dry: the painted water (tools/water_mask.py) and the river
    corridors of data/rivers.json (half the widest width, plus one), near the sites only."""

    def __init__(self, ground, centres, data=DATA):
        import water_mask as WM
        self.g, self.WM, self.bodies = ground, WM, WM.bodies()
        self.river = []
        for c in jload("rivers.json", data).get("courses") or []:
            w = max((c.get("character") or {}).get("width") or [32])
            for p in c.get("graded_polyline") or []:
                if any(math.hypot(p[0] - x, p[1] - z) < 600 for x, z in centres):
                    self.river.append((p[0], p[1], p[2], w / 2.0 + 1))
        self.cache = {}

    def __call__(self, x, z):
        k = (x, z)
        if k not in self.cache:
            lv = self.WM.level_at(x, z, self.g, self.bodies)[1]
            if lv is None:
                gy = self.g(x, z)
                for px, pz, sy, half in self.river:
                    if math.hypot(px - x, pz - z) <= half and gy < sy:
                        lv = round(sy)
                        break
            self.cache[k] = None if lv is None else int(lv)
        return self.cache[k]


class Expect:
    """What one resident's record says is built, on this ground: {(x, y, z): set of allowed block ids}, solid then
    hung (a hung block wins its cell), each later write winning its cell, as the record lists them."""

    def __init__(self, r, g, water):
        self.r, self.g, self.water = r, g, water
        self.cx, self.cz = r["site"]["centre"]
        self.solid, self.hung, self.signs = {}, {}, {}
        self.floors, self.posts, self.swap = {}, [], set()
        self.wet_posts = {}               # (x, y, z) -> ("shaft" | "top", water y)
        self.cols = set()
        self.problems = []

    def put(self, x, y, z, v, hung=False, allowed=None):
        pos = (x, y, z)
        (self.hung if hung else self.solid)[pos] = frozenset(allowed or {vbase(v)})
        if isinstance(v, dict):
            self.signs[pos] = list(v["sign"]["lines"])
        self.cols.add((x, z))

    def final(self, pos):
        return self.hung.get(pos) or self.solid.get(pos)

    def all(self):
        out = dict(self.solid)
        out.update(self.hung)
        return out


def _box(a0, a1):
    return range(min(a0, a1), max(a0, a1) + 1)


def _structure(E, p):
    x0, z0, x1, z1 = p["footprint"]
    cols = [(E.cx + lx, E.cz + lz) for lx in range(x0, x1 + 1) for lz in range(z0, z1 + 1)]
    wet = [c for c in cols if E.water(*c) is not None]
    if wet:
        E.problems.append("%s: its footprint stands on water at %s" % (p["name"], wet[:3]))
    B = max(E.g(x, z) for x, z in cols)
    E.floors[p["name"]] = (B, set(cols))
    for x, z in cols:
        for y in range(E.g(x, z) + 1, B):
            E.put(x, y, z, p["foundation"])
    for a0, d0, b0, a1, d1, b1, v in p.get("fills") or []:
        if min(d0, d1) <= 0 <= max(d0, d1):
            E.swap.add(vbase(v))
        for lx in _box(a0, a1):
            for dy in _box(d0, d1):
                for lz in _box(b0, b1):
                    E.put(E.cx + lx, B + dy, E.cz + lz, v)
    for key in ("blocks", "hung"):
        for lx, dy, lz, v in p.get(key) or []:
            if dy == 0:
                E.swap.add(vbase(v))
            E.put(E.cx + lx, B + dy, E.cz + lz, v, hung=(key == "hung"))


def _surface(E, p):
    cols = set()
    for (ax, az), (bx, bz) in p.get("segments") or []:
        r = p.get("half_width", 0) + 0.5
        for dx in range(math.floor(min(ax, bx) - r), math.ceil(max(ax, bx) + r) + 1):
            for dz in range(math.floor(min(az, bz) - r), math.ceil(max(az, bz) + r) + 1):
                vx, vz = bx - ax, bz - az
                L2 = vx * vx + vz * vz
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((dx - ax) * vx + (dz - az) * vz) / L2))
                if math.hypot(dx - ax - t * vx, dz - az - t * vz) <= r:
                    cols.add((dx, dz))
    if p.get("ring"):
        rad, w = p["ring"]
        n = rad + w + 1
        cols |= {(dx, dz) for dx in range(-n, n + 1) for dz in range(-n, n + 1) if abs(math.hypot(dx, dz) - rad) <= w + 0.5}
    cols -= {tuple(c) for c in p.get("except") or []}
    ox, oz = p.get("at") or (0, 0)
    pal = {b for b, _w in p["palette"]}
    E.swap |= pal
    for dx, dz in cols:
        x, z = E.cx + ox + dx, E.cz + oz + dz
        if E.water(x, z) is None:
            E.put(x, E.g(x, z), z, None, allowed=pal)


def _ground_blocks(E, name, blocks_by_key, ax, az):
    for key in ("blocks", "hung"):
        for dx, dy, dz, v in blocks_by_key.get(key) or []:
            x, z = E.cx + ax + dx, E.cz + az + dz
            if E.water(x, z) is not None:
                E.problems.append("%s: the record puts %s on a wet column (%d, %d)" % (name, vbase(v), x, z))
            if dy == 0:
                E.swap.add(vbase(v))
            E.put(x, E.g(x, z) + dy, z, v, hung=(key == "hung"))


def _ring(E, p):
    n, rad = int(p["count"]), float(p["r"])
    ox, oz = p.get("at") or (0, 0)
    for k in range(n):
        a = 2 * math.pi * (k + 0.5 * float(p.get("offset", 0))) / n
        ax, az = ox + round(rad * math.sin(a)), oz + round(-rad * math.cos(a))
        _ground_blocks(E, p["name"], {"blocks": p["objects"][k % len(p["objects"])]}, ax, az)


def _posts(E, p):
    b = math.radians(p["bearing"])
    fx, fz = p["from"]
    for k in range(int(p["count"])):
        d = p["spacing"] * (k + int(p.get("skip", 0)))
        x, z = E.cx + fx + round(math.sin(b) * d), E.cz + fz + round(-math.cos(b) * d)
        gy, lv = E.g(x, z), E.water(x, z)
        if lv is None:
            for j, v in enumerate(p["dry"]):
                E.put(x, gy + 1 + j, z, v)
            E.posts.append((x, z, "dry"))
            continue
        if lv - gy > int(p.get("max_depth", 6)):
            break                                   # too deep to set a pole: the line ends here
        for y in range(gy + 1, lv + 1):
            E.put(x, y, z, p["wet_shaft"])
            E.wet_posts[(x, y, z)] = ("shaft", lv)
        for j, v in enumerate(p["wet_top"]):
            E.put(x, lv + 1 + j, z, v)
            E.wet_posts[(x, lv + 1 + j, z)] = ("top", lv)
        E.posts.append((x, z, "wet"))


def expect(r, g, water):
    E = Expect(r, g, water)
    for p in r["pieces"]:
        k = p["kind"]
        if k == "structure":
            _structure(E, p)
        elif k == "surface":
            _surface(E, p)
        elif k == "ground_blocks":
            _ground_blocks(E, p["name"], p, *(p["at"]))
        elif k == "ring":
            _ring(E, p)
        elif k == "posts":
            _posts(E, p)
        else:
            E.problems.append("unknown piece kind %s" % k)
    return E


def passable(E, x, y, z):
    v = E.final((x, y, z))
    if v is None:
        return y > E.g(x, z)
    return v <= PASSABLE


def stand(E, x, z):
    """Feet y at (x, z): the lowest cell over something solid with two passable cells, from the ground up."""
    gy = E.g(x, z)
    for y in range(gy + 1, gy + 64):
        if passable(E, x, y, z) and passable(E, x, y + 1, z) and not passable(E, x, y - 1, z):
            return y
    return None


def spot(E, at):
    x, z = E.cx + at[0], E.cz + at[1]
    return (x, stand(E, x, z), z)


# ------------------------------------------------------------------ the pack, replayed


SET = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (.+)$")
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")


class Replay:
    def __init__(self, text):
        self.blocks, self.clears, self.bad = {}, [], []
        for line in _code(text):
            m, f = SET.match(line), FILL.match(line)
            if m:
                self.blocks[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = m.group(4)
            elif f:
                c = [int(v) for v in f.groups()[:6]]
                st, rep = f.group(7), f.group(8)
                if rep is not None:
                    self.clears.append((min(c[0], c[3]), min(c[1], c[4]), min(c[2], c[5]),
                                        max(c[0], c[3]), max(c[1], c[4]), max(c[2], c[5]), st, rep))
                    continue
                for x in _box(c[0], c[3]):
                    for y in _box(c[1], c[4]):
                        for z in _box(c[2], c[5]):
                            self.blocks[(x, y, z)] = st
            else:
                self.bad.append(line)

    def cleared(self, pos):
        x, y, z = pos
        tags = {c[7] for c in self.clears if c[0] <= x <= c[3] and c[1] <= y <= c[4] and c[2] <= z <= c[5]
                and c[6] == "minecraft:air"}
        return all(t in tags for t in CLEAR_TAGS)

    def columns(self):
        cols = {(x, z) for x, _y, z in self.blocks}
        for c in self.clears:
            cols |= {(x, z) for x in range(c[0], c[3] + 1) for z in range(c[2], c[5] + 1)}
        return cols


def load_pack(pack, ns, folder):
    fdir = Path(pack) / "data" / ns / "function" / folder
    fns = {p.relative_to(fdir).with_suffix("").as_posix(): p.read_text(encoding="utf-8") for p in fdir.rglob("*.mcfunction")}
    tag = Path(pack) / "data" / "minecraft" / "tags" / "function" / "load.json"
    fns["__load_tag__"] = tag.read_text(encoding="utf-8") if tag.is_file() else ""
    return fns


# ------------------------------------------------------------------ the checks


def check_ys(doc, r, E, spots, rep, data):
    """The records other builders read: the anchor, the NPC's feet, the quest's and reward's npc_at, the cache."""
    i = r["id"]
    for p in E.problems:
        rep.err("ys", "%s %s" % (i, p))
    qs = {q["id"]: q for q in jload("quests.json", data)["quests"]}
    rw = {x["id"]: x for x in jload("rewards.json", data)["rewards"]}
    rec = r.get("records") or {}
    pk = r.get("pokemon")
    if pk:
        a = spots["anchor"]
        if a[1] is None or list(a) != list(pk.get("anchor") or []):
            rep.err("ys", "%s: the heightmap and the record's blocks put %s's feet at %s, the record says %s"
                    % (i, pk["name"], list(a), pk.get("anchor")))
    n = r.get("npc")
    if n:
        f = spots["npc"]
        if f[1] is None or list(f) != list(n.get("feet") or []):
            rep.err("ys", "%s: %s stands at %s, the record says %s" % (i, n["name"], list(f), n.get("feet")))
        on = n["at"][2]
        if f[1] is not None:
            if on == "ground" and f[1] != E.g(f[0], f[2]) + 1:
                rep.err("ys", "%s: %s is recorded on the ground, but stands at y%d over ground y%d"
                        % (i, n["name"], f[1], E.g(f[0], f[2])))
            if on != "ground" and (on not in E.floors or f[1] != E.floors[on][0] + 1):
                rep.err("ys", "%s: %s is recorded on %s's floor, but stands at y%d" % (i, n["name"], on, f[1]))
        q = qs.get(rec.get("quest"))
        if q is None:
            rep.err("ys", "%s: quest %s is not in data/quests.json" % (i, rec.get("quest")))
        elif list(q.get("npc_at") or []) != list(f):
            rep.err("ys", "%s: data/quests.json %s npc_at %s, the site gives %s" % (i, q["id"], q.get("npc_at"), list(f)))
        if rec.get("reward") and rw.get(rec["reward"], {}).get("kind") == "npc_grant":
            if list(rw[rec["reward"]].get("npc_at") or []) != list(f):
                rep.err("ys", "%s: data/rewards.json %s npc_at %s, the site gives %s"
                        % (i, rec["reward"], rw[rec["reward"]].get("npc_at"), list(f)))
    for c, s in zip(r.get("caches") or [], spots["caches"]):
        w = rw.get(c["reward"])
        if not w or w.get("kind") != "cache":
            rep.err("ys", "%s: data/rewards.json %s is not a cache" % (i, c["reward"]))
            continue
        if s[1] is None:
            rep.err("ys", "%s: the cache spot at %s has no standing room" % (i, s))
            continue
        cont = (s[0], s[1] - 1, s[2])
        if list((w.get("container") or {}).get("at") or []) != list(cont):
            rep.err("ys", "%s: %s container at %s, the site gives %s" % (i, c["reward"], (w.get("container") or {}).get("at"), list(cont)))
        if E.final(cont) != frozenset({(w.get("container") or {}).get("block")}):
            rep.err("ys", "%s: %s's container %s is not what the record builds at %s (%s)"
                    % (i, c["reward"], (w.get("container") or {}).get("block"), list(cont), sorted(E.final(cont) or [])))
        t = w.get("trigger") or {}
        lo, hi = t.get("min") or [0, 0, 0], t.get("max") or [-1, -1, -1]
        if not all(lo[k] <= s[k] <= hi[k] for k in range(3)):
            rep.err("ys", "%s: %s trigger %s..%s does not hold the spot %s" % (i, c["reward"], lo, hi, list(s)))


def check_writes(doc, r, E, R, spots, rep, data, spawn, whitelist):
    i = r["id"]
    for line in R.bad[:3]:
        rep.err("writes", "%s: a build line that is neither a setblock nor a fill: %s" % (i, line[:100]))
    x0, z0, x1, z1 = r["bbox"]
    ids = set(doc["blocks"]["ids"])
    exp = E.all()
    off, wrong, missing = [], [], []
    seen_bad = {}
    for pos, st in sorted(R.blocks.items()):
        b = base(st)
        x, y, z = pos
        why = None
        gy, lv = E.g(x, z), E.water(x, z)
        if not (x0 <= x <= x1 and z0 <= z <= z1):
            why = "outside the bbox %s" % r["bbox"]
        elif b not in ids:
            why = "not in blocks.ids"
        elif b in spawn and b not in whitelist:
            why = "a spawn condition (data/spawn_blocks.json) no policy entry whitelists here"
        elif b in NEVER or b.endswith("_bed"):
            why = "a chest or a bed"
        elif y < gy:
            why = "under the ground y%d" % gy
        elif y == gy and b not in E.swap:
            why = "swapped for the ground block, which the record does not do with %s" % b
        elif lv is not None:
            kind = E.wet_posts.get(pos)
            if kind is None:
                why = "on a wet column (water y%d), and not a post built for water" % lv
            elif kind[0] == "shaft" and not ("waterlogged=true" in st and gy < y <= lv):
                why = "a post's shaft that is not waterlogged at or under the water y%d" % lv
            elif kind[0] == "top" and not y > lv:
                why = "a post's top at or under the water y%d" % lv
        if why:
            seen_bad[why] = seen_bad.get(why, 0) + 1
            if seen_bad[why] <= 3:
                rep.err("writes", "%s: %s at %s %s" % (i, st[:60], pos, why))
        want = exp.get(pos)
        if want is None:
            off.append(pos)
        elif b not in want:
            wrong.append((pos, b, sorted(want)))
        elif pos in E.signs and not all(json.dumps(t) in st.replace("\\'", "'") for t in E.signs[pos] if t):
            wrong.append((pos, "sign text", E.signs[pos]))
    for pos, want in exp.items():
        if pos not in R.blocks:
            missing.append((pos, sorted(want)))
    for name, lst in (("off-plan (no piece of the record puts a block there)", off),
                      ("not the block the record puts there", wrong), ("in the record, never written", missing)):
        if lst:
            rep.err("writes", "%s: %d block(s) %s, e.g. %s" % (i, len(lst), name, lst[:3]))
    # each structure seated on max(ground) under its footprint: its first floor fill lands there
    for p in r["pieces"]:
        if p["kind"] != "structure":
            continue
        B, cols = E.floors[p["name"]]
        floor = [f for f in p.get("fills") or [] if f[1] == 0 and f[4] == 0]
        if not floor:
            continue
        a0, _d0, b0, _a1, _d1, _b1, v = floor[0]
        x, z = E.cx + a0, E.cz + b0
        ys = sorted(y for (bx, y, bz), st in R.blocks.items() if (bx, bz) == (x, z) and base(st) == vbase(v))
        if B not in ys:
            rep.err("seat", "%s %s: the floor (%s) is not at max ground y%d under its footprint; written at %s"
                    % (i, p["name"], vbase(v), B, ys[:4]))
    # the clears: logs, leaves and plants only, inside the bbox, never into water (#minecraft:replaceable holds water)
    wet_clears = set()
    for c in R.clears:
        if c[6] != "minecraft:air" or c[7] not in CLEAR_TAGS:
            rep.err("writes", "%s: a fill with replace that is not a plant clear: %s" % (i, c))
            continue
        if not (x0 <= c[0] and c[3] <= x1 and z0 <= c[2] and c[5] <= z1):
            rep.err("writes", "%s: a clear outside the bbox: %s" % (i, c[:6]))
        for x in range(c[0], c[3] + 1):
            for z in range(c[2], c[5] + 1):
                lv = E.water(x, z)
                if lv is not None and c[1] <= lv:
                    if c[:6] not in wet_clears and len(wet_clears) < 3:
                        rep.err("writes", "%s: the clear %s reaches the water y%d at (%d, %d)" % (i, c[:6], lv, x, z))
                    wet_clears.add(c[:6])
    # standing room where someone stands, in the written world, and cleared of plants
    who = [("anchor", spots.get("anchor")), ("npc", spots.get("npc"))]
    for name, s in who:
        if not s or s[1] is None:
            continue
        x, y, z = s
        for yy in (y, y + 1):
            st = R.blocks.get((x, yy, z))
            if st is not None and base(st) not in PASSABLE:
                rep.err("writes", "%s: the %s's spot %s holds %s at y%d" % (i, name, list(s), st[:40], yy))
            elif st is None and not R.cleared((x, yy, z)):
                rep.err("writes", "%s: the %s's spot %s is not cleared of logs, leaves and plants at y%d" % (i, name, list(s), yy))
        under = R.blocks.get((x, y - 1, z))
        if (under is None and E.g(x, z) != y - 1) or (under is not None and base(under) in PASSABLE):
            rep.err("writes", "%s: the %s's spot %s has nothing under it" % (i, name, list(s)))
    # the record's bbox holds every write, clear and spot (the box a forceload holds and other builders check)
    xs = [p[0] for p in R.blocks] + [c[0] for c in R.clears] + [c[3] for c in R.clears]
    zs = [p[2] for p in R.blocks] + [c[2] for c in R.clears] + [c[5] for c in R.clears]
    for s in [spots.get("anchor"), spots.get("npc")] + list(spots.get("caches") or []):
        if s:
            xs.append(s[0])
            zs.append(s[2])
    if xs:
        tight = [min(xs), min(zs), max(xs), max(zs)]
        if not (x0 <= tight[0] and z0 <= tight[1] and tight[2] <= x1 and tight[3] <= z1):
            rep.err("writes", "%s: the writes span %s, outside the record's bbox %s" % (i, tight, r["bbox"]))
        elif tight != list(r["bbox"]):
            rep.note("%s: the writes span %s inside the record's larger bbox %s" % (i, tight, r["bbox"]))
    else:
        rep.err("writes", "%s: the build writes nothing" % i)


def authored(doc, data, record=RECORD):
    """Every x/z another data file authors (`record` is the residents file skipped whole: tools/northern_residents_audit.py
    passes its own, so THIS file's sites count against the northern ones like any other): (points [(x, z, file)], rects [(x0, z0, x1, z1, file)]).

    A dict with numeric x and z; a list of two numbers; a list of three read both as [x, y, z] and [x, z, y]; a list
    of four with x1 >= x0, z1 >= z0 a box, read as a FILLED rectangle (stricter than corners: a column inside another
    place's box is 0 from it); a dict with min_x/max_x/min_z/max_z the same. An AREA is different: a box a cell wide or
    wider, or any box in AREA_FILES, is an extent every site stands inside by design, so a listed box counts by its
    corners only and a min/max dict (a measured bounds, data/world.json: "bounds are derived ... not authored by hand")
    not at all. A dict whose id is one of our own records is skipped."""
    own = set()
    for r in doc["residents"]:
        own |= {v for v in (r.get("records") or {}).values() if v}
    # an area a cell wide or wider is an index, not a place: data/world.json grid.cell_size, and CLAUDE.md "a cell
    # indexes location only". Every column of the map is inside one
    cell = jload("world.json", data)["grid"]["cell_size"]
    pts, rects = [], []

    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def box(a, b, c, d, f, listed):
        if c - a + 1 < cell and d - b + 1 < cell and f not in AREA_FILES:
            rects.append((a, b, c, d, f))
        elif listed:
            pts.extend([(a, b, f), (c, b, f), (a, d, f), (c, d, f)])

    def walk(o, f):
        if isinstance(o, dict):
            if o.get("id") in own:
                return
            if num(o.get("x")) and num(o.get("z")):
                pts.append((o["x"], o["z"], f))
            if all(num(o.get(k)) for k in ("min_x", "max_x", "min_z", "max_z")):
                box(o["min_x"], o["min_z"], o["max_x"], o["max_z"], f, False)
            for v in o.values():
                walk(v, f)
        elif isinstance(o, list):
            if o and all(num(v) for v in o) and len(o) in (2, 3, 4):
                if len(o) == 2:
                    pts.append((o[0], o[1], f))
                elif len(o) == 3:
                    pts.extend([(o[0], o[2], f), (o[0], o[1], f)])
                else:
                    a, b, c, d = o
                    if c >= a and d >= b:
                        box(a, b, c, d, f, True)
            else:
                for v in o:
                    walk(v, f)

    for p in sorted(Path(data).glob("*.json")):
        if p.name == record:
            continue
        walk(json.loads(p.read_text(encoding="utf-8")), p.name)
    return pts, rects


def check_siting(doc, r, cols, A, rep, data):
    import numpy as np
    i, rules = r["id"], doc["rules"]
    pts, rects = A
    C = np.array(sorted(cols), float)
    P = np.array([(a, b) for a, b, _f in pts], float)
    best = (1e18, None, None)
    for k in range(0, len(C), 128):
        blk = C[k:k + 128]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] < best[0]:
            best = (float(d[j]), tuple(int(v) for v in blk[j[0]]), pts[j[1]][2])
    for x0, z0, x1, z1, f in rects:
        dx = np.maximum(np.maximum(x0 - C[:, 0], C[:, 0] - x1), 0)
        dz = np.maximum(np.maximum(z0 - C[:, 1], C[:, 1] - z1), 0)
        d = np.hypot(dx, dz)
        j = int(np.argmin(d))
        if d[j] < best[0]:
            best = (float(d[j]), tuple(int(v) for v in C[j]), f + " (box %s)" % [x0, z0, x1, z1])
    if best[0] < rules["authored_clearance"]:
        rep.err("siting", "%s: (%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                % (i, best[1][0], best[1][1], best[0], best[2], rules["authored_clearance"]))
    rep.note("%s: nearest authored x/z %.0f, our column %s, in data/%s" % (i, best[0], best[1], best[2]))
    fx0, fz0, fx1, fz1 = rules["keep_out_box"]["box"]
    if any(fx0 <= x <= fx1 and fz0 <= z <= fz1 for x, z in cols):
        rep.err("siting", "%s: writes inside the keep-out box %s" % (i, rules["keep_out_box"]["box"]))
    for ax, az in rules["away_from"]["points"]:
        d = float(np.min(np.hypot(C[:, 0] - ax, C[:, 1] - az)))
        if d < rules["away_from"]["blocks"]:
            rep.err("siting", "%s: %.0f blocks from (%d, %d) (needs %d)" % (i, d, ax, az, rules["away_from"]["blocks"]))
    m = rules["authored_clearance"]
    for t in jload("towns.json", data)["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            rep.err("siting", "%s: within %d of town %s's footprint" % (i, m, t["id"]))
    for k, zone in jload("rift_zones.json", data)["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                rep.err("siting", "%s: inside Rift zone %s" % (i, k))
                break
    if any(z < rules["south_of_z"] for _x, z in cols):
        rep.err("siting", "%s: writes north of z %d" % (i, rules["south_of_z"]))
    paths = np.array([p[:2] for pl in jload("route_paths.json", data)["paths"].values() for p in pl], float)
    dmin = 1e18
    for k in range(0, len(C), 128):
        blk = C[k:k + 128]
        dmin = min(dmin, float(np.min(np.hypot(paths[None, :, 0] - blk[:, None, 0], paths[None, :, 1] - blk[:, None, 1]))))
    if dmin < rules["path_clearance"]:
        rep.err("siting", "%s: a column is %.0f blocks from a route path (needs %d)" % (i, dmin, rules["path_clearance"]))
    rep.note("%s: nearest route path %.0f" % (i, dmin))


def _subregion(x, z, data):
    design = jload("encounter_design.json", data)
    for s in jload("regions.json", data)["subregions"]:
        if s["id"] not in design["tables"]:
            continue
        for poly in s.get("polygons") or []:
            inside, n = False, len(poly)
            for k in range(n):
                (xa, za), (xb, zb) = poly[k], poly[(k + 1) % n]
                if (za > z) != (zb > z) and x < xa + (z - za) * (xb - xa) / (zb - za):
                    inside = not inside
            if inside:
                tier = design["tables"][s["id"]]["tier"]
                return s["id"], tier, design["rules"]["hearts"]["next_cap"][str(tier)]
    return None, None, None


def check_resident(doc, r, anchor, rep, data):
    pk, i = r["pokemon"], r["pokemon"]["id"]
    ax, _ay, az = anchor
    sub, tier, ceiling = _subregion(ax, az, data)
    if sub is None:
        rep.err("residents", "%s stands in no sub-region with an encounter table" % i)
    elif sub != r.get("subregion"):
        rep.err("residents", "%s stands in %s, the record says %s" % (i, sub, r.get("subregion")))
    if sub and pk["level"] > ceiling:
        rep.err("residents", "%s: L%d over %s's tier-%s ceiling %d" % (i, pk["level"], sub, tier, ceiling))
    for b in jload("habitat_blocks.json", data)["blocks"]:
        if b.get("style") != "activated" or not b.get("position"):
            continue
        d = math.hypot(b["position"]["x"] - ax, b["position"]["z"] - az)
        need = b["activated"]["spawn_range"] + pk["leash"]
        if d < need:
            rep.err("residents", "%s: its leash overlaps Habitat Block %s (%.0f, needs %d)" % (i, b["id"], d, need))
    if not 0 < pk["trigger"] < pk["leash"]:
        rep.err("residents", "%s: trigger %d is not inside leash %d" % (i, pk["trigger"], pk["leash"]))
    aces = jload("trainers.json", data)["generation_contract"]["gym_ace_levels"]
    m = re.fullmatch(r"gym(\d)_cleared", pk.get("gate") or "")
    if pk["catch_rule"] == "catchable_after_gate":
        if not m:
            rep.err("residents", "%s: catchable after a gate, but its gate %s is not a gym" % (i, pk.get("gate")))
        else:
            n = int(m.group(1))
            lo, hi = aces[n - 1], (aces[n] if n < len(aces) else None)
            if not pk["level"] > lo:
                rep.err("residents", "%s: L%d is within the cap %d a player can hold before %s" % (i, pk["level"], lo, pk["gate"]))
            if hi is not None and pk["level"] > hi:
                rep.err("residents", "%s: L%d is above the cap %d a player holds just after %s" % (i, pk["level"], hi, pk["gate"]))
            if pk.get("intended_stage") != "post_gym_%d" % n:
                rep.err("residents", "%s: intended_stage %s, gate %s" % (i, pk.get("intended_stage"), pk["gate"]))
            rep.note("%s: L%d, catch window %d..%s for %s, %s tier %s ceiling %s"
                     % (i, pk["level"], lo + 1, hi, pk["gate"], sub, tier, ceiling))
    flags = {f["id"] for f in jload("progression.json", data)["flags"]}
    for k in ("gate", "appears_after"):
        if pk.get(k) and pk[k] not in flags:
            rep.err("residents", "%s: %s %s is not a flag in data/progression.json" % (i, k, pk[k]))


def check_keeper(doc, built, fns, rep, data):
    b = doc["build"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    if b.get("guardian_tag") != GUARDIAN:
        rep.err("keeper", "build.guardian_tag %s is not the blackout's %s" % (b.get("guardian_tag"), GUARDIAN))
    keeper, load = _code(fns.get("keeper", "")), _code(fns.get("load", ""))
    if "scoreboard players set #resp %s %d" % (obj, b["respawn_ticks"]) not in load:
        rep.err("keeper", "load does not set the respawn to build.respawn_ticks %d" % b["respawn_ticks"])
    if "%s:%s/load" % (ns, F) not in fns.get("__load_tag__", ""):
        rep.err("keeper", "the load tag does not run %s:%s/load" % (ns, F))
    kp = b["keeper"]
    for r, anchor in built:
        pk = r["pokemon"]
        i = pk["id"]
        ax, ay, az = anchor
        sx = "x=%.1f,y=%d,z=%.1f" % (ax + 0.5, ay, az + 0.5)
        at = "%.1f %d %.1f" % (ax + 0.5, ay, az + 0.5)
        P = "%s:%s/%s" % (ns, F, i)
        rtag = "%s.%s" % (b["tag"], i)
        if "execute if loaded %d %d %d run function %s/keep" % (ax, ay, az, P) not in keeper:
            rep.err("keeper", "%s: the keeper does not run its keep at its anchor %s" % (i, list(anchor)))
        keep, hold = _code(fns.get("%s/keep" % i, "")), _code(fns.get("%s/hold" % i, ""))
        if not any("as @e[type=cobblemon:pokemon,tag=%s,tag=!%s] run function %s/hold" % (rtag, GUARDIAN, P) in l for l in keep):
            rep.err("keeper", "%s: hold is not run only on its non-guardian resident" % i)
        if not any("if entity @a[%s,distance=..%d] run return 0" % (sx, kp["spawn_clear"]) in l for l in keep):
            rep.err("keeper", "%s: no refusal to spawn within %d of a player at its anchor" % (i, kp["spawn_clear"]))
        want = {"leash": "unless entity @s[%s,distance=..%d] run tp @s %s" % (sx, pk["leash"], at),
                "trigger": "if entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/wake" % (sx, pk["trigger"], P),
                "settle": "unless entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/settle"
                          % (sx, pk["leash"] + kp["settle_margin"], P),
                "home": "run tp @s %s %s 0" % (at, float(pk["yaw"]))}
        for k, v in want.items():
            if not any(v in l for l in hold):
                rep.err("keeper", "%s: hold lacks its %s (%s)" % (i, k, v))
        settle = " ".join(_code(fns.get("%s/settle" % i, "")))
        if "tp @s %s %s 0" % (at, float(pk["yaw"])) not in settle:
            rep.err("keeper", "%s: settle does not put it back on %s facing %s" % (i, at, float(pk["yaw"])))
        spawn = " ".join(_code(fns.get("%s/spawn" % i, "")))
        sp = pk["species"].split(":", 1)[1]
        m = re.search(r'spawn_at \{x:"([-\d.]+)",y:(-?\d+),z:"([-\d.]+)",species:"([^"]+)",props:"([^"]*)"\}', spawn)
        if not m:
            rep.err("keeper", "%s: the spawn does not call the macro spawn_at" % i)
        else:
            if (float(m.group(1)), int(m.group(2)), float(m.group(3))) != (ax + 0.5, ay, az + 0.5) or m.group(4) != sp:
                rep.err("keeper", "%s: the spawn is %s at %s, expected %s at %s" % (i, m.group(4), m.groups()[:3], sp, at))
            props = m.group(5).split()
            if "level=%d" % pk["level"] not in props:
                rep.err("keeper", "%s: the spawn lacks level=%d (props %s)" % (i, pk["level"], props))
            if ("uncatchable" in props) != (pk["catch_rule"] == "permanently_uncatchable"):
                rep.err("keeper", "%s: uncatchable is %s, its catch_rule %s" % (i, "uncatchable" in props, pk["catch_rule"]))
        gate = pk.get("appears_after")
        adv = [l for l in keep if "advancements=" in l]
        if gate:
            if not any("advancements={%s:flag/%s=true}" % (ns, gate) in l and "run return 0" in l for l in adv):
                rep.err("keeper", "%s: the spawn is not gated on %s" % (i, gate))
        elif adv:
            rep.err("keeper", "%s: the spawn carries a gate the record does not: %s" % (i, adv[0][:120]))
        bind = " ".join(_code(fns.get("%s/bind" % i, "")))
        if "data merge entity @s {NoAI:1b,PersistenceRequired:1b" not in bind or "tag @s add %s" % rtag not in bind:
            rep.err("keeper", "%s: bind does not tag it and make it persistent and dormant" % i)
    for name, text in fns.items():
        for l in _code(text):
            if re.search(r"\bkill\b", l):
                if "tag=!%s" % GUARDIAN not in l or not re.search(r"tag=%s\.\w+" % re.escape(b["tag"]), l):
                    rep.err("keeper", "%s: a kill that could reach a guardian or a non-resident: %s" % (name, l[:120]))
            if re.search(r"tag \S+ (add|remove) %s\b" % re.escape(GUARDIAN), l):
                rep.err("keeper", "%s: touches the blackout's guardian tag: %s" % (name, l[:120]))
            if re.match(r"(give|loot)\b", l) or " run give " in l or " run loot " in l or "summon minecraft:item" in l:
                rep.err("keeper", "%s: an item reward (no_loot_drops): %s" % (name, l[:120]))


def check_steps(doc, spots_by_id, steps, rep, data, npc_step="R18SR"):
    """`npc_step` names the step that places the NPCs R9F does not (tools/northern_residents_audit.py passes R18NR)."""
    b = doc["build"]
    held, summons, built_fns, npcs = [], {}, {}, []
    for s in steps:
        if s[0] == "cmd" and s[1].startswith("forceload add "):
            held.append([int(v) for v in s[1].split()[2:6]])
        elif s[0] == "cmd" and s[1].startswith("forceload remove "):
            box = [int(v) for v in s[1].split()[2:6]]
            if box in held:
                held.remove(box)
        elif s[0] == "fn":
            built_fns.setdefault(s[1], []).append([list(h) for h in held])
        elif s[0] == "cmd" and "spawnpokemonat" in s[1]:
            m = re.search(r"tag=%s\.(\w+)" % re.escape(b["tag"]), s[1])
            summons.setdefault(m.group(1) if m else "?", []).append((s[1], [list(h) for h in held]))
        elif s[0] == "npc":
            npcs.append(s[1])
    if held:
        rep.err("steps", "forceloads never released: %s" % held)
    rw = {x["id"]: x for x in jload("rewards.json", data)["rewards"]}
    dl = {c["id"]: c for c in jload("dialogue.json", data)["conversations"]}
    for r in doc["residents"]:
        i = r["id"]
        fn = "%s:%s/%s/build" % (b["namespace"], b["folder"], i)
        if not any(list(r["bbox"]) in h for h in built_fns.get(fn, [])):
            rep.err("steps", "%s: its build does not run inside a forceload of its bbox %s" % (i, r["bbox"]))
        if len(built_fns.get(fn, [])) != 1:
            rep.err("steps", "%s: its build runs %d times" % (i, len(built_fns.get(fn, []))))
        pk = r.get("pokemon")
        if pk:
            got = summons.get(pk["id"], [])
            ax, ay, az = spots_by_id[i]["anchor"]
            at = "%.1f %d %.1f" % (ax + 0.5, ay, az + 0.5)
            if pk.get("appears_after"):
                if got:
                    rep.err("steps", "%s is presence-gated on %s but the re-application summons it" % (pk["id"], pk["appears_after"]))
            elif len(got) != 1:
                rep.err("steps", "%s: %d summon steps, expected 1" % (pk["id"], len(got)))
            else:
                cmd, h = got[0]
                if list(r["bbox"]) not in h:
                    rep.err("steps", "%s: the summon is not inside the forceload of its bbox" % pk["id"])
                if "unless entity @e[type=cobblemon:pokemon,tag=%s.%s]" % (b["tag"], pk["id"]) not in cmd:
                    rep.err("steps", "%s: the summon guard does not key on its tag" % pk["id"])
                for guard in re.findall(r"unless entity (@e\[[^\]]*\])", cmd):
                    if "distance=" in guard and pk["species"] not in guard:
                        rep.err("steps", "%s: a guard keys on distance without the species: %s" % (pk["id"], guard))
                if "spawnpokemonat %s %s " % (at, pk["species"].split(":", 1)[1]) not in cmd + " ":
                    rep.err("steps", "%s: the summon is not at %s" % (pk["id"], at))
                if "level=%d" % pk["level"] not in cmd.split():
                    rep.err("steps", "%s: the summon lacks level=%d" % (pk["id"], pk["level"]))
                fnb = "%s:%s/%s/bind_new" % (b["namespace"], b["folder"], pk["id"])
                if fnb not in built_fns:
                    rep.err("steps", "%s: the summon is not bound (no %s step)" % (pk["id"], fnb))
        n = r.get("npc")
        if not n:
            continue
        feet = tuple(spots_by_id[i]["npc"])
        conv = dl.get(r["records"]["conversation"])
        mine = [x for x in npcs if x[0] == r["records"]["conversation"]]
        grant = rw.get((r.get("records") or {}).get("reward") or "", {})
        is_grant = grant.get("kind") == "npc_grant"
        if n["placed_by"] == "R9F":
            if not is_grant:
                rep.err("steps", "%s: placed by R9F, but data/rewards.json has no npc_grant %s" % (i, r["records"].get("reward")))
            if mine:
                rep.err("steps", "%s: placed by R9F and again by %s" % (i, npc_step))
        elif n["placed_by"] == npc_step:
            if is_grant:
                rep.err("steps", "%s: placed by %s and again by R9F (an npc_grant record)" % (i, npc_step))
            if len(mine) != 1:
                rep.err("steps", "%s: %d %s npc steps, expected 1" % (i, len(mine), npc_step))
            elif conv is not None and (tuple(mine[0][1]) != feet or mine[0][2] != "cobblers:%s" % conv.get("npc_id")
                                       or float(mine[0][3]) != float(n["yaw"])):
                rep.err("steps", "%s: the npc step %s, expected %s at %s facing %s"
                        % (i, mine[0], conv.get("npc_id"), list(feet), n["yaw"]))
        else:
            rep.err("steps", "%s: placed_by %s is neither R9F nor %s" % (i, n["placed_by"], npc_step))


def _conds(c):
    """Flatten a condition tree to its leaves."""
    if not c:
        return []
    if c.get("kind") in ("all", "any"):
        return [x for y in c["conditions"] for x in _conds(y)]
    if c.get("kind") == "not":
        return _conds(c["condition"])
    return [c]


def _fields(o):
    out = set()
    if isinstance(o, dict):
        for k in ("field", "claim_field", "progression_field"):
            if isinstance(o.get(k), str) and o[k].startswith("quest."):
                out.add(o[k])
        for v in o.values():
            out |= _fields(v)
    elif isinstance(o, list):
        for v in o:
            out |= _fields(v)
    return out


def _gated(q, tid, flag, depth=0):
    """True when transition tid of quest q can only run behind the flag: it names the flag, or it requires a field
    every setter of which is itself behind the flag."""
    if depth > 6:
        return False
    tr = {t["id"]: t for t in q["transitions"]}[tid]
    leaves = [x for c in tr["conditions"] for x in _conds(c)]
    if any(c.get("kind") == "flag" and c.get("flag") == flag for c in leaves):
        return True
    for c in leaves:
        if c.get("kind") == "progression_equals" and c.get("value") is True:
            setters = [t["id"] for t in q["transitions"] if any(
                e["kind"] == "set_progression" and e["field"] == c["field"] and e["value"] is True for e in t["effects"])]
            if setters and all(_gated(q, s, flag, depth + 1) for s in setters):
                return True
    return False


def check_dialogue(doc, r, rep, data, compile_fn, flags_named=None, grant_flags=None):
    """`flags_named` replaces the scan of the record for the flags the conversation must read; `grant_flags` names
    the ones every grant must require (default: all of them). Both are tools/northern_residents_audit.py's."""
    i, rec = r["id"], r.get("records") or {}
    dl = {c["id"]: c for c in jload("dialogue.json", data)["conversations"]}
    qs = {q["id"]: q for q in jload("quests.json", data)["quests"]}
    rw = {x["id"]: x for x in jload("rewards.json", data)["rewards"]}
    prog = jload("progression.json", data)
    flags = {f["id"] for f in prog["flags"]}
    fields = {f["id"]: f for f in prog["quest_fields"]}
    conv, q = dl.get(rec.get("conversation")), qs.get(rec.get("quest"))
    if conv is None or q is None:
        rep.err("dialogue", "%s: conversation %s or quest %s is missing" % (i, rec.get("conversation"), rec.get("quest")))
        return
    if conv.get("quest_id") != q["id"] or q.get("dialogue_id") != conv["id"]:
        rep.err("dialogue", "%s: %s and %s do not name each other" % (i, conv["id"], q["id"]))
    nodes = {n["id"]: n for n in conv["nodes"]}
    if len(nodes) != len(conv["nodes"]):
        rep.err("dialogue", "%s: duplicate node ids in %s" % (i, conv["id"]))
    trs = {t["id"]: t for t in q["transitions"]}
    edges, used_tr = {}, set()
    for n in conv["nodes"]:
        nx = [n["next"]] if n.get("next") else []
        for a in n.get("actions_after_acknowledge") or []:
            if a.get("kind") == "quest_transition":
                used_tr.add(a["transition"])
        for resp in n.get("responses") or []:
            if resp.get("next"):
                nx.append(resp["next"])
            for a in resp.get("actions") or []:
                if a.get("kind") == "quest_transition":
                    used_tr.add(a["transition"])
        for t in nx:
            if t not in nodes:
                rep.err("dialogue", "%s: %s %s goes to %s, which is not a node" % (i, conv["id"], n["id"], t))
        edges[n["id"]] = nx
    starts = [conv["cursor"]["initial_node"]]
    for e in conv.get("entry_rules") or []:
        if e.get("node") and e["node"] != "$cursor":
            starts.append(e["node"])
        for a in e.get("actions") or []:
            if a.get("kind") == "quest_transition":
                used_tr.add(a["transition"])
    seen, todo = set(), list(starts)
    while todo:
        n = todo.pop()
        if n in seen or n not in nodes:
            continue
        seen.add(n)
        todo += edges.get(n, [])
    if set(nodes) - seen:
        rep.err("dialogue", "%s: nodes no path reaches: %s" % (i, sorted(set(nodes) - seen)))
    for t in sorted(used_tr - set(trs)):
        rep.err("dialogue", "%s: the dialogue runs transition %s, which %s does not have" % (i, t, q["id"]))
    for t in sorted(set(trs) - used_tr):
        rep.err("dialogue", "%s: transition %s.%s is run by nothing in %s" % (i, q["id"], t, conv["id"]))
    cur = conv["cursor"]["progression_field"]
    fd = fields.get(cur)
    if fd is None or set(fd.get("allowed_values") or []) != set(nodes) or fd.get("initial") != conv["cursor"]["initial_node"]:
        rep.err("dialogue", "%s: the cursor %s's allowed values/initial are not the nodes and %s"
                % (i, cur, conv["cursor"]["initial_node"]))
    for t in q["transitions"]:
        for e in t["effects"]:
            if e["kind"] == "set_progression" and e["field"] == cur and e["value"] not in nodes:
                rep.err("dialogue", "%s: %s sets the cursor to %s, not a node" % (i, t["id"], e["value"]))
    used = _fields(conv) | _fields(q)
    for f in sorted(used - set(fields)):
        rep.err("dialogue", "%s: field %s is not declared in data/progression.json quest_fields" % (i, f))
    # the flags: exactly the progression flags this resident's record names, and every reward behind them
    leaves = [x for n in conv["nodes"] for resp in n.get("responses") or [] for x in _conds(resp.get("visible_when") or {})]
    leaves += [x for t in q["transitions"] for c in t["conditions"] for x in _conds(c)]
    leaves += [x for c in (q.get("progression_gate") or []) for x in _conds(c if isinstance(c, dict) else {"kind": "flag", "flag": c})]
    read = {c["flag"] for c in leaves if c.get("kind") == "flag"}
    for f in sorted(read - flags):
        rep.err("dialogue", "%s: reads flag %s, which data/progression.json does not have" % (i, f))
    text = json.dumps({k: v for k, v in r.items() if k not in ("pokemon",)})
    declared = {f for f in flags if re.search(r"\b%s\b" % re.escape(f), text)}
    if flags_named is not None:
        # the caller's own expectation (tools/northern_residents_audit.py: a record that names its flags as a range,
        # "gymN_cleared", in prose this scan cannot read)
        declared = set(flags_named)
    if read != declared:
        rep.err("dialogue", "%s: the conversation reads flags %s, the record names %s" % (i, sorted(read), sorted(declared)))
    grants = [t["id"] for t in q["transitions"] if any(e["kind"] == "grant_reward_once" for e in t["effects"])]
    for f in sorted(declared):
        for g in grants:
            if grant_flags is not None and f not in grant_flags:
                continue
            if not _gated(q, g, f):
                rep.err("dialogue", "%s: %s.%s grants a reward without requiring %s" % (i, q["id"], g, f))
        gated_tr = {t for t in trs if t != "start" and _gated(q, t, f)}
        for n in conv["nodes"]:
            for resp in n.get("responses") or []:
                runs = {a["transition"] for a in resp.get("actions") or [] if a.get("kind") == "quest_transition"}
                vis = {c.get("flag") for c in _conds(resp.get("visible_when") or {}) if c.get("kind") == "flag"}
                if runs & gated_tr and f not in vis:
                    rep.err("dialogue", "%s: option %s runs %s and is shown without %s" % (i, resp["id"], sorted(runs), f))
    # rewards: the quest's contents are data/rewards.json's, and the record's kind matches who gives it
    qr = {x["id"]: x for x in q.get("rewards") or []}
    want_items = {}
    for t in q["transitions"]:
        for e in t["effects"]:
            if e["kind"] != "grant_reward_once":
                continue
            x = qr.get(e["reward"])
            w = rw.get(rec.get("reward") or "")
            if x is None or w is None:
                rep.err("rewards", "%s: grant %s has no quest reward or no data/rewards.json %s" % (i, e["reward"], rec.get("reward")))
                continue
            a = sorted((c["item"], c["count"]) for c in x.get("contents") or [])
            b = sorted((c["item"], c["count"]) for c in w.get("contents") or [])
            if a != b:
                rep.err("rewards", "%s: the quest gives %s, data/rewards.json %s says %s" % (i, a, w["id"], b))
            if w.get("quest") != q["id"] or w.get("kind") != "npc_grant":
                rep.err("rewards", "%s: data/rewards.json %s is %s for %s, not an npc_grant for %s"
                        % (i, w["id"], w.get("kind"), w.get("quest"), q["id"]))
            for item, count in b:
                want_items[item] = want_items.get(item, 0) + count
    if rec.get("reward") and rec["reward"] in rw and rw[rec["reward"]].get("kind") == "npc_grant" and not grants:
        rep.err("rewards", "%s: data/rewards.json %s is an npc_grant, and no transition grants it" % (i, rec["reward"]))
    for c in r.get("caches") or []:
        if c["reward"] != rec.get("reward"):
            rep.err("rewards", "%s: the cache %s is not the record's reward %s" % (i, c["reward"], rec.get("reward")))
    # the compiled conversation: it compiles, the flag-gated option probes the flag, it gives exactly the record's
    # contents, and no hand-in takes more than one item
    try:
        files = compile_fn(conv["id"], data)
    except SystemExit as e:
        rep.err("dialogue", "%s: %s does not compile: %s" % (i, conv["id"], e))
        return
    if "data/cobblers/npcs/%s.json" % conv.get("npc_id") not in files:
        rep.err("dialogue", "%s: the compiled pack has no NPC class %s" % (i, conv.get("npc_id")))
    page_doc = files.get("data/cobblers/dialogues/%s.json" % conv["id"])
    page_doc = json.loads(page_doc) if isinstance(page_doc, str) else page_doc
    acts = []
    for page in (page_doc or {}).get("pages") or []:
        inp = page.get("input")
        for o in (inp.get("options") or []) if isinstance(inp, dict) else []:
            acts.append((o.get("value"), o.get("isVisible", "") or "", o.get("action", "") or ""))
    allact = " ".join(a for _v, _s, a in acts) + " " + json.dumps(page_doc)
    for f in sorted(declared):
        for n in conv["nodes"]:
            for resp in n.get("responses") or []:
                if f in {c.get("flag") for c in _conds(resp.get("visible_when") or {}) if c.get("kind") == "flag"}:
                    probe = "advancements={cobblers:flag/%s=true}" % f
                    if probe not in allact:
                        rep.err("dialogue", "%s: the compiled %s never probes %s" % (i, resp["id"], probe))
    given = {}
    for m in re.finditer(r"run give @s (\S+) (\d+)", allact):
        given[m.group(1)] = given.get(m.group(1), 0)
        given[m.group(1)] = max(given[m.group(1)], int(m.group(2)))
    if set(given) != set(want_items) or any(given[k] != want_items[k] for k in want_items):
        rep.err("rewards", "%s: the compiled dialogue gives %s, the records say %s" % (i, given, want_items))
    for v, _s, a in acts:
        for m in re.finditer(r"if items entity @s weapon\.mainhand (\S+) run item replace entity @s weapon\.mainhand with minecraft:air", a):
            if m.group(1) not in UNSTACKABLE:
                rep.err("hand-in", "%s: option %s takes the WHOLE main-hand stack of %s (item replace ... with "
                        "minecraft:air), not one: a player holding several gives them all" % (i, v, m.group(1)))


def _compile(conv_id, data):
    import compile_dialogue as CD
    return CD.build(conv_id, Path(data))


def audit(doc, ground, water, pack, steps, data=DATA, compile_fn=None):
    """The whole audit. `water(x, z)` is the water surface y or None; `steps` are the generator's R9SR + R18SR."""
    rep = Report()
    compile_fn = compile_fn or _compile
    if doc.get("schema") != SCHEMA:
        rep.err("spec", "schema %s, expected %s" % (doc.get("schema"), SCHEMA))
    if "placed" in doc.get("status", "").replace("Not applied", "").replace("not placed", ""):
        rep.note("the record's status mentions placement: %s" % doc["status"][:80])
    b = doc["build"]
    fdir = Path(pack) / "data" / b["namespace"] / "function" / b["folder"]
    if not fdir.is_dir():
        rep.err("pack", "%s is missing: run tools/southern_residents.py first" % fdir)
        return rep
    fns = load_pack(pack, b["namespace"], b["folder"])
    import function_limits
    for name, text in fns.items():
        if name.startswith("__"):
            continue
        for n, cmd, why in function_limits.check_lines(text.splitlines(), where=name):
            rep.err("functions", "%s:%d %s" % (name, n, why))
    spawn = set(jload("spawn_blocks.json", data)["blocks"])
    pol = jload("spawn_block_policy.json", data)
    whitelist = {x for w in pol.get("whitelist") or [] if "southern_residents" in (w.get("scope") or "") for x in w["blocks"]}
    A = authored(doc, data)
    spots_by_id, keeper_built = {}, []
    for r in doc["residents"]:
        E = expect(r, ground, water)
        spots = {"caches": [spot(E, c["at"]) for c in r.get("caches") or []]}
        if r.get("pokemon"):
            spots["anchor"] = spot(E, r["pokemon"]["at"])
        if r.get("npc"):
            spots["npc"] = spot(E, r["npc"]["at"])
        spots_by_id[r["id"]] = spots
        check_ys(doc, r, E, spots, rep, data)
        text = fns.get("%s/build" % r["id"])
        if text is None:
            rep.err("writes", "%s has no build function" % r["id"])
            continue
        R = Replay(text)
        check_writes(doc, r, E, R, spots, rep, data, spawn, whitelist)
        cols = R.columns() | E.cols | {(s[0], s[2]) for k in ("anchor", "npc") if spots.get(k) for s in [spots[k]]} \
            | {(s[0], s[2]) for s in spots["caches"]}
        check_siting(doc, r, cols, A, rep, data)
        if r.get("pokemon"):
            check_resident(doc, r, spots["anchor"], rep, data)
            if spots["anchor"][1] is not None:
                keeper_built.append((r, spots["anchor"]))
        if r.get("npc"):
            check_dialogue(doc, r, rep, data, compile_fn)
    check_keeper(doc, keeper_built, fns, rep, data)
    check_steps(doc, spots_by_id, steps, rep, data)
    # every function is reached: the load tag, the keeper loop, and the steps
    reached, todo = set(), ["load"] + [s[1].split(":", 1)[1].split("/", 1)[1] for s in steps if s[0] == "fn"]
    while todo:
        f = todo.pop()
        if f in reached or f not in fns:
            continue
        reached.add(f)
        todo += re.findall(r"function %s:%s/(\S+)" % (b["namespace"], b["folder"]), fns[f])
    for f in sorted(set(fns) - reached - {"__load_tag__"}):
        rep.err("functions", "%s is reached by nothing" % f)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    ap.add_argument("-v", "--verbose", action="store_true", help="print the notes too")
    a = ap.parse_args(argv)
    import ground as G
    doc = jload(RECORD)
    g = G.load(a.source_root)
    rep_steps = []
    try:
        import southern_residents as SR       # for its OUTPUT only: the steps it hands tools/reapply.py
        sd = SR.load()
        rep_steps = SR.placement_steps(sd, g) + SR.entity_steps(sd, g)
    except SystemExit as e:
        print("PROBLEM steps: the generator refuses to give its steps: %s" % e)
        return 1
    water = Water(g, [tuple(r["site"]["centre"]) for r in doc["residents"]])
    rep = audit(doc, g, water, Path(a.pack), rep_steps)
    if a.verbose:
        for n in rep.notes:
            print("note: %s" % n)
    for e in rep.errors:
        print("PROBLEM %s" % e)
    print("southern_residents_audit: %s" % ("clean" if not rep.errors else "%d problem(s)" % len(rep.errors)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
