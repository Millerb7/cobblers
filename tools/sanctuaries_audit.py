#!/usr/bin/env python
"""The audit of the legendary sanctuaries (data/sanctuaries.json, pack cobblers_sanctuaries). Its derivation is its own.

INDEPENDENCE, AND ITS LIMIT. Written 2026-10-12 by the same session that wrote tools/sanctuaries.py (CLAUDE.md principle 16 asks
for a different agent; a second agent should grade this file). What it does to earn trust anyway:

  * it imports NOTHING from tools/sanctuaries.py, tools/mines.py or tools/mining_caves.py. A set piece is a composition, not a rule
    a second derivation could repeat, so this audit does not re-derive its cells: it replays the pack's text (fill and setblock in
    file order, last write wins) over the canonical heightmap (tools/ground.py) and tests what a player would meet there;
  * the restore is checked against the RETIRED CAVES AS APPLIED: their build text is re-emitted by tools/caves.py from the frozen
    record and must hash to the sha256 recorded from the applied pack, then it is parsed as text, and the restore is replayed over it;
  * tests/test_sanctuaries.py MUTATES THE GENERATOR (a wall cell left out, a lantern off its post, a floating block, a steep band, a
    keeper that forgets the guardian, a restore that skips a column) and requires this audit to fail each time with data/sanctuaries.json
    untouched (CLAUDE.md "How to prove an audit is independent").
Shared on purpose, because they are data readers and not derivations: tools/ground.py, and tools/caves.py for the retired caves' text.

What it checks, per sanctuary:
  walk       from anywhere outside, on foot (a step up of one block, any fall, two blocks of headroom; slabs, fences and walls taken as
             full blocks, which only ever finds MORE ways in), with the door CLOSED the court's centre cannot be reached and the
             forecourt can; with the door OPEN the centre can
  ground     no written block floats (every 6-connected group of written blocks rests on the heightmap's ground); no cut deeper than
             max_cut and no platform built higher than max_fill; the graded land never steps more than one block from its neighbour
  light      lanterns only: each stands on a fence, a wall or a chain, or hangs under a block; nothing else that gives light
  blocks     no spawn-condition block (data/spawn_blocks.json) the policy does not allow for `sanctuaries`
  look       at least eight different blocks, weathered ones among them; at least 12 above its floor and 25 across; no two
             sanctuaries built mostly of the same blocks
  gate       near / open / close: the flags are the record's, the open fill turns exactly the written barrier into air and the close
             fill puts exactly it back, the forecourt box lies in front of the door
  keeper     every selector that kills, holds, wakes or settles a Pokemon carries tag=!cobblers.guardian; nothing adds or removes it or
             the blackout's exempt tag; the clocks are 24,000 and 72,000; the spawn asks for a player holding the gate flag; the
             spot is the court's centre, one over its floor
  records    the Habitat Blocks (position = the court's centre floor cell, mimic = the block written there) and the pools; no record
             of a retired cave left in data/habitat_blocks.json, data/spawns.json or data/world_probes.json
  restore    per retired cave: its text hashes to the applied sha256; the act, replayed over the cave, leaves every one of its cells as
             the heightmap's terrain (air over the ground, rock at and under it); it runs only while a probe that is one of the
             cave's own written blocks still shows, and the act overwrites every probe; every cell a player could stand in is inside
             a box that holds the restore; the sanctuary's build refuses while a probe shows

Not covered, and it needs a running server: that the commands parse and behave as the vanilla semantics say; that the Habitat
Block's spawns stay in an open court (HB-1); the alpha re-level near a no_ai boss (AB-1); the callback firing (EXP-042); flight.

  python tools/sanctuaries_audit.py [--pack DIR] [--no-walk]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "sanctuaries.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_sanctuaries"
FN = "cobblers:sanctuaries/"
GUARD = "cobblers.guardian"
AIR = "minecraft:air"
PASSABLE = {"minecraft:air", "minecraft:cave_air", "minecraft:moss_carpet", "minecraft:water", "minecraft:short_grass"}
LIGHT = ("glowstone", "sea_lantern", "shroomlight", "torch", "campfire", "jack_o_lantern", "lantern", "end_rod", "beacon",
         "froglight", "redstone_lamp", "copper_bulb", "amethyst_cluster", "amethyst_bud", "magma_block", "crying_obsidian",
         "respawn_anchor", "glow_lichen", "sculk_catalyst", "light")
WEATHERED = ("mossy", "cracked", "moss_", "weathered", "oxidized", "exposed", "chiseled", "cobble")


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def jload(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def base(block):
    return block.split("[")[0].split("{")[0]


# ------------------------------------------------------------------ the pack, as text

def read_pack(pack=PACK):
    """({function name under sanctuaries/: [lines]}, callback text)."""
    pack = Path(pack)
    fdir = pack / "data" / "cobblers" / "function" / "sanctuaries"
    fns = {}
    for f in sorted(fdir.rglob("*.mcfunction")):
        fns[f.relative_to(fdir).as_posix()[:-len(".mcfunction")]] = f.read_text(encoding="utf-8").splitlines()
    cb = pack / "data" / "cobblemon" / "callbacks" / "pokemon_captured" / "cobblers_sanctuaries.molang"
    return fns, (cb.read_text(encoding="utf-8") if cb.is_file() else "")


WRITE = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)(?: (replace) (\S+))?$")


def replay(lines, world=None):
    """Apply the fill and setblock lines in order: {(x, y, z): block}. A `replace <block>` fill writes only over that block."""
    w = {} if world is None else world
    for line in lines:
        m = WRITE.match(line.strip())
        if not m:
            continue
        if m.group(1) == "setblock":
            x, y, z = int(m.group(2)), int(m.group(3)), int(m.group(4))
            w[(x, y, z)] = m.group(8)
            continue
        x0, y0, z0, x1, y1, z1 = (int(m.group(i)) for i in range(2, 8))
        blk, flt = m.group(8), m.group(10)
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    if flt is None or base(w.get((x, y, z), AIR)) == base(flt):
                        w[(x, y, z)] = blk
    return w


# ------------------------------------------------------------------ a player on foot

class Terrain:
    """The world a player meets: written cells over the heightmap (an unwritten cell is rock at or under the ground, air over it)."""

    def __init__(self, written, ground, open_door=False):
        self.w, self.g, self.open = written, ground, open_door
        self._gc = {}

    def ground(self, x, z):
        k = (x, z)
        if k not in self._gc:
            self._gc[k] = self.g(x, z)
        return self._gc[k]

    def passable(self, x, y, z):
        b = self.w.get((x, y, z))
        if b is None:
            return y > self.ground(x, z)
        bb = base(b)
        if bb == "minecraft:barrier" and self.open:
            return True
        return bb in PASSABLE

    def solid(self, x, y, z):
        b = self.w.get((x, y, z))
        if b is None:
            return y <= self.ground(x, z)
        bb = base(b)
        if bb == "minecraft:barrier" and self.open:
            return False
        return bb not in PASSABLE


def walk(t, box, starts=None):
    """Every feet cell reachable on foot inside box (x0, y0, z0, x1, y1, z1), from every standable cell on its rim."""
    x0, y0, z0, x1, y1, z1 = box

    def stand(x, y, z):
        return t.passable(x, y, z) and t.passable(x, y + 1, z) and t.solid(x, y - 1, z)
    seen = set()
    q = deque()
    if starts is None:
        starts = []
        for x in range(x0, x1 + 1):
            for z in (z0, z1):
                starts.append((x, z))
        for z in range(z0, z1 + 1):
            for x in (x0, x1):
                starts.append((x, z))
        starts = [(x, y, z) for (x, z) in starts for y in range(y0, y1) if stand(x, y, z)]
    for s in starts:
        if s not in seen:
            seen.add(s)
            q.append(s)
    while q:
        x, y, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (x0 <= nx <= x1 and z0 <= nz <= z1):
                continue
            nxt = None
            if stand(nx, y, nz):
                nxt = (nx, y, nz)
            elif t.passable(x, y + 2, z) and stand(nx, y + 1, nz):
                nxt = (nx, y + 1, nz)
            elif t.passable(nx, y, nz) and t.passable(nx, y + 1, nz):
                yy = y
                while yy > y0 and not t.solid(nx, yy - 1, nz) and t.passable(nx, yy - 1, nz):
                    yy -= 1
                if stand(nx, yy, nz):
                    nxt = (nx, yy, nz)
            if nxt and nxt not in seen and y0 <= nxt[1] <= y1:
                seen.add(nxt)
                q.append(nxt)
    return seen


# ------------------------------------------------------------------ per sanctuary

def zone_of(sel):
    m = re.search(r"x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)", sel)
    x, y, z, dx, dy, dz = (int(v) for v in m.groups())
    return (x, y, z, x + dx, y + dy, z + dz)


def floor_of(written):
    bars = [c for c, b in written.items() if base(b) == "minecraft:barrier"]
    return min(c[1] for c in bars) - 1 if bars else None, bars


def ground_problems(spec, sid, written, g, yf):
    gr = spec["ground"]
    out = []
    # 1. nothing floats: union the written solid cells by face; a group must touch the ground (a cell at or one over it)
    solid = {c for c, b in written.items() if base(b) not in PASSABLE}
    seen = set()
    for c in solid:
        if c in seen:
            continue
        comp, q, ok = [], deque([c]), False
        seen.add(c)
        while q:
            x, y, z = q.popleft()
            comp.append((x, y, z))
            if y <= g(x, z) + 1:
                ok = True
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                n = (x + d[0], y + d[1], z + d[2])
                if n in solid and n not in seen:
                    seen.add(n)
                    q.append(n)
        if not ok:
            out.append("%s: %d written block(s) float free of the ground, e.g. %s %s" % (sid, len(comp), min(comp), written[min(comp)]))
    # 2. the platform: a column written at the floor is cut at most max_cut and built at most max_fill
    cols = {}
    for (x, y, z), b in written.items():
        cols.setdefault((x, z), {})[y] = b
    for (x, z), ys in cols.items():
        gy = g(x, z)
        if yf in ys and base(ys[yf]) not in PASSABLE:
            if gy - yf > gr["max_cut"]:
                out.append("%s: column (%d, %d) is cut %d under the ground, over %d" % (sid, x, z, gy - yf, gr["max_cut"]))
            if yf - gy > gr["max_fill"]:
                out.append("%s: column (%d, %d) is built %d over the ground, over %d" % (sid, x, z, yf - gy, gr["max_fill"]))
    # 3. the graded land: a column whose written blocks are all the palette's grade blocks (and air) never stands further from a
    # neighbour that is land too (graded, untouched, or the platform's floor) than one block, or than the heightmap's own step
    # between the same two columns where the land itself is steeper: grading may not make a slope steeper than it found it
    pal = spec_palette(spec, sid)
    gradeset = {base(b) for k in ("grade_top", "grade_fill", "drift", "drift_top") for b in blocks_of(pal.get(k))}

    def surface(x, z):
        ys = cols.get((x, z))
        if ys is None:
            return g(x, z), "ground"
        top = max((y for y, b in ys.items() if base(b) not in PASSABLE), default=None)
        if top is None:
            return g(x, z), "ground"
        nonair = {base(b) for y, b in ys.items() if base(b) not in PASSABLE}
        if nonair <= gradeset:
            return top, "graded"
        if top == yf:
            return top, "floor"
        return top, "built"
    for (x, z) in cols:
        s, kind = surface(x, z)
        if kind != "graded":
            continue
        for dx, dz in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            s2, k2 = surface(x + dx, z + dz)
            if k2 == "built":
                continue
            if abs(s - s2) > max(1, abs(g(x, z) - g(x + dx, z + dz))):
                out.append("%s: graded column (%d, %d) at y%d stands %d from its neighbour (%d, %d) (%s) at y%d, where the land "
                           "steps %d" % (sid, x, z, s, abs(s - s2), x + dx, z + dz, k2, s2, abs(g(x, z) - g(x + dx, z + dz))))
                break
    return out


def blocks_of(e):
    if e is None:
        return []
    if isinstance(e, str):
        return [e]
    return [b for b, _w in e]


def spec_palette(spec, sid):
    return next(s for s in spec["sanctuaries"] if s["id"] == sid)["palette"]


def light_problems(sid, written):
    out = []
    for (x, y, z), b in written.items():
        bb = base(b)
        if not any(k in bb for k in LIGHT):
            continue
        if bb != "minecraft:lantern":
            out.append("%s: %s at (%d, %d, %d) gives light; lanterns on posts only" % (sid, bb, x, y, z))
            continue
        if "hanging=true" in b:
            if base(written.get((x, y + 1, z), AIR)) in PASSABLE:
                out.append("%s: the hanging lantern at (%d, %d, %d) hangs from nothing" % (sid, x, y, z))
        else:
            under = base(written.get((x, y - 1, z), AIR))
            if not (under.endswith("_fence") or under.endswith("_wall") or under == "minecraft:chain"):
                out.append("%s: the lantern at (%d, %d, %d) stands on %s, not a post" % (sid, x, y, z, under))
    return out


def spawn_problems(sid, written):
    spawn = set(jload("spawn_blocks.json")["blocks"])
    policy = jload("spawn_block_policy.json")
    allowed = {b for w in policy["whitelist"] if "sanctuaries" in (w.get("scope") or "") for b in w["blocks"]}
    placed = {base(b) for b in written.values()}
    return ["%s: places %s, a spawn condition the policy does not allow for sanctuaries" % (sid, b) for b in sorted((placed & spawn) - allowed)]


def look_problems(sid, written, yf):
    out = []
    kinds = {base(b) for b in written.values() if base(b) not in PASSABLE and base(b) != "minecraft:barrier"}
    if len(kinds) < 8:
        out.append("%s: only %d different blocks (%s): a set piece needs more than that" % (sid, len(kinds), sorted(kinds)))
    if not any(any(w in k for w in WEATHERED) for k in kinds):
        out.append("%s: nothing weathered (mossy, cracked, oxidized...)" % sid)
    solid = [c for c, b in written.items() if base(b) not in PASSABLE]
    if max(c[1] for c in solid) - yf < 12:
        out.append("%s: stands only %d over its floor; under 12 it does not read from a distance" % (sid, max(c[1] for c in solid) - yf))
    above = [c for c in solid if c[1] > yf]
    span = max(max(c[0] for c in above) - min(c[0] for c in above), max(c[2] for c in above) - min(c[2] for c in above))
    if span < 25:
        out.append("%s: only %d across" % (sid, span))
    return out, kinds


def gate_problems(spec, san, fns, written, bars, yf):
    sid = san["id"]
    out = []
    near = fns.get("gate/%s/near" % sid)
    opn = fns.get("gate/%s/open" % sid)
    cls = fns.get("gate/%s/close" % sid)
    if not (near and opn and cls):
        return ["%s: the gate's near / open / close are missing" % sid]
    want = "advancements={%s}" % ",".join("%s:flag/%s=true" % (spec["flag_namespace"], f) for f in san["gate"]["flags"])
    if want not in near[1]:
        out.append("%s: the gate does not ask for %s" % (sid, want))
    ante = zone_of(near[1])
    fo = next((l for l in opn if l.startswith("fill ")), "")
    fc = next((l for l in cls if l.startswith("fill ")), "")
    m1 = re.match(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) minecraft:air replace minecraft:barrier$", fo)
    m2 = re.match(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) minecraft:barrier replace minecraft:air$", fc)
    if not (m1 and m2) or m1.groups() != m2.groups():
        return out + ["%s: the open and close fills are not the same box, barrier <-> air" % sid]
    x0, y0, z0, x1, y1, z1 = (int(v) for v in m1.groups())
    box = {(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)}
    if box != set(bars):
        out.append("%s: the door's fill box (%d cells) is not exactly the written barrier (%d cells)" % (sid, len(box), len(bars)))
    cx, cz = san["site"]["centre"]
    # the forecourt lies in front of the door: the door sits between it and the court's centre
    ac = ((ante[0] + ante[3]) / 2, (ante[2] + ante[5]) / 2)
    dc = ((x0 + x1) / 2, (z0 + z1) / 2)
    if not ((ac[0] - dc[0]) * (cx - dc[0]) + (ac[1] - dc[1]) * (cz - dc[1]) < 0):
        out.append("%s: the forecourt %s is not in front of the door %s" % (sid, ante, (x0, z0, x1, z1)))
    if ante[1] != yf + 1:
        out.append("%s: the forecourt box starts at y%d, not one over the floor y%d" % (sid, ante[1], yf))
    return out


def keeper_problems(spec, san, fns, callback, yf):
    sid = san["id"]
    occ = san["occupant"]
    mine = {k: v for k, v in fns.items() if k.startswith("boss/%s/" % sid)}
    if occ["mode"] != "area_boss":
        return ["%s: boss functions for a sanctuary with no boss" % sid] if mine else []
    if not mine:
        return ["%s: an area boss with no keeper" % sid]
    out = []
    k = occ["keeper"]
    for fn, ls in mine.items():
        for l in ls:
            if re.search(r"\btag\b[^#]*\b(add|remove)\b\s+" + re.escape(GUARD) + r"\b", l):
                out.append("%s: %s adds or removes %s: %s" % (sid, fn, GUARD, l))
            if "exempt" in l and "tag" in l:
                out.append("%s: %s names an exempt tag: %s" % (sid, fn, l))
            if l.startswith("#"):
                continue
            acts = (" kill " in l) or ("run function" in l and ("/hold" in l or "/wake" in l or "/settle" in l))
            if acts and "@e[" in l and "tag=!%s" % GUARD not in l:
                out.append("%s: %s can reach a guardian: %s" % (sid, fn, l))
    for fn in ("hold", "wake", "settle", "bind"):
        for l in mine.get("boss/%s/%s" % (sid, fn), []):
            if re.match(r"(tp|data merge|tag)\b", l) and "@s" not in l:
                out.append("%s: %s acts on something other than the Pokemon itself: %s" % (sid, fn, l))
    keep = "\n".join(mine.get("boss/%s/keep" % sid, []))
    for n in (24000, 72000):
        if " %d" % n not in keep:
            out.append("%s: the keeper does not carry the clock %d" % (sid, n))
    fl = "advancements={%s}" % ",".join("cobblers:flag/%s=true" % f for f in san["gate"]["flags"])
    if fl not in keep or "champion_cleared" not in fl:
        out.append("%s: the keeper spawns without asking for a player holding champion_cleared" % sid)
    sp = mine.get("boss/%s/spawn_at" % sid, [])
    if len(sp) != 1 or not sp[0].startswith("$spawnpokemonat ") or "alpha=true" not in sp[0].split():
        out.append("%s: the spawn is not a single alpha macro line" % sid)
    cx, cz = san["site"]["centre"]
    m = re.search(r'x:"(-?\d+\.\d)",y:(-?\d+),z:"(-?\d+\.\d)"', "\n".join(mine.get("boss/%s/spawn" % sid, [])))
    if not m or (float(m.group(1)) - 0.5, int(m.group(2)), float(m.group(3)) - 0.5) != (cx, yf + 1, cz):
        out.append("%s: the boss spot %s is not the court's centre one over its floor %s" % (sid, m and m.groups(), (cx, yf + 1, cz)))
    want = "x=%d,y=%d,z=%d,distance=..%d" % (cx, yf + 1, cz, k["catch_radius"])
    if want not in callback or "cobblemon:%s" % occ["species"] not in callback:
        out.append("%s: the capture callback does not set the caught flag within %d of the spot" % (sid, k["catch_radius"]))
    if "PersistenceRequired:1b" not in "\n".join(mine.get("boss/%s/bind" % sid, [])):
        out.append("%s: the bound boss is not kept from the despawner" % sid)
    return out


def record_problems(spec, san, written, yf):
    sid = san["id"]
    out = []
    cx, cz = san["site"]["centre"]
    blocks = {b["id"]: b for b in jload("habitat_blocks.json")["blocks"]}
    for h in san.get("habitat") or []:
        b = blocks.get(h["id"])
        if b is None:
            out.append("%s: data/habitat_blocks.json lacks %s" % (sid, h["id"]))
            continue
        pos = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
        if pos != (cx, yf, cz):
            out.append("%s: %s stands at %s, not the court's centre floor cell %s" % (sid, h["id"], pos, (cx, yf, cz)))
        if b["mimic"] != base(written.get((cx, yf, cz), AIR)):
            out.append("%s: %s mimics %s, the floor written there is %s" % (sid, h["id"], b["mimic"], written.get((cx, yf, cz))))
        if b["pool"] != "cobblers:%s" % h["pool"]["id"] or b["style"] != "activated":
            out.append("%s: %s is not the activated block of pool %s" % (sid, h["id"], h["pool"]["id"]))
    if san["occupant"]["mode"] == "rare_spawn":
        sp = jload("spawns.json")
        for h in san["habitat"]:
            ents = [e for e in sp["entries"] if e.get("scope") == h["pool"]["id"]]
            want = {san["occupant"]["species"]} | set(san["occupant"].get("co_occupants") or [])
            ultra = {e["species"] for e in ents if e["bucket"] == "ultra-rare"}
            if not want <= ultra:
                out.append("%s: %s is not an ultra-rare entry of %s" % (sid, sorted(want - ultra), h["pool"]["id"]))
    if not (written.get((cx, yf + 1, cz)) is None or base(written[(cx, yf + 1, cz)]) in PASSABLE) or base(written.get((cx, yf + 2, cz), AIR)) not in PASSABLE:
        out.append("%s: no headroom over the court's centre" % sid)
    return out


def retired_left(spec):
    old = [rc["cave"]["id"] for rc in spec["retired_caves"]]
    out = []
    hb = [b["id"] for b in jload("habitat_blocks.json")["blocks"] if any(b["id"].startswith(o + "_") for o in old)]
    sp = jload("spawns.json")
    pools = [h["id"] for h in sp["habitats"] if any(h["id"].startswith(o + "_") for o in old)]
    ents = [e["id"] for e in sp["entries"] if any((e.get("scope") or "").startswith(o + "_") for o in old)]
    pr = [p["what"] for p in jload("world_probes.json")["places"].get("caves") or [] if any(p["what"].startswith(o + ":") for o in old)]
    caves = [c["id"] for c in jload("caves.json")["caves"] if c["id"] in old]
    for what, ids in (("data/habitat_blocks.json", hb), ("data/spawns.json pools", pools), ("data/spawns.json entries", ents),
                      ("data/world_probes.json places.caves", pr), ("data/caves.json", caves)):
        if ids:
            out.append("%s still carries a retired cave's record: %s" % (what, ids[:3]))
    return out


# ------------------------------------------------------------------ the restore

def old_written(rc, g):
    """The retired cave's writes, parsed from its build text as applied (tools/caves.py re-emits it; the sha256 must match)."""
    sys.path.insert(0, str(ROOT / "tools"))
    import caves as CV
    spec, cave = rc["frozen_spec"], rc["cave"]
    gm = CV.geometry(spec, cave, g)
    text = "\n".join(CV.build_lines(spec, {"cave": cave, "geometry": gm})) + "\n"
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != rc["applied_build_sha256"]:
        return None
    return replay(text.splitlines())


def restore_problems(spec, rc, fns, g, built):
    rid = rc["id"]
    out = []
    old = old_written(rc, g)
    if old is None:
        return ["%s: the retired cave's text does not hash to its applied sha256: the audit cannot know what was applied" % rid]
    entry = fns.get("restore/%s" % rid)
    act = fns.get("restore/%s_do" % rid)
    if not entry or not act:
        return ["%s: the restore's entry or act is missing" % rid]
    # the act, replayed over the cave as it stood (unwritten cells: the heightmap's terrain)
    world = dict(old)
    replay(act, world)
    t = rc["terrain"]
    for (x, y, z) in old:
        gy = g(x, z)
        b = base(world[(x, y, z)])
        if y > gy and b != AIR:
            out.append("%s: (%d, %d, %d) over the ground is %s after the restore, not air" % (rid, x, y, z, b))
            break
        if y <= gy and b in PASSABLE | {"minecraft:barrier", "minecraft:lantern"}:
            out.append("%s: (%d, %d, %d) at or under the ground is %s after the restore, not rock" % (rid, x, y, z, b))
            break
        if y == gy and b != base(t["surface"]):
            out.append("%s: the surface (%d, %d, %d) is %s, not the painted %s" % (rid, x, y, z, b, t["surface"]))
            break
    # the guard: a held count, then the act only while a probe that is one of the cave's own written blocks shows
    holder = None
    probes = []
    for l in entry:
        m = re.match(r"execute store result score #(\S+) cobblers_chunk_look if entity @a\[tag=(\S+)\]$", l)
        if m:
            holder = m.group(1)
        m = re.match(r"execute if score #(\S+) cobblers_chunk_look matches 0 if block (-?\d+) (-?\d+) (-?\d+) (\S+) run function (\S+)$", l)
        if m:
            probes.append(((int(m.group(2)), int(m.group(3)), int(m.group(4))), m.group(5), m.group(6)))
    if holder is None or not probes:
        out.append("%s: the restore does not count held players or has no probe" % rid)
    for (c, blk, fn) in probes:
        if fn != FN + "restore/%s_do" % rid:
            out.append("%s: a probe runs %s, not the act" % (rid, fn))
        if c not in old or base(old[c]) != base(blk):
            out.append("%s: the probe %s %s is not one of the cave's own written blocks (%s)" % (rid, c, blk, old.get(c)))
        if base(world.get(c, AIR)) == base(blk):
            out.append("%s: the act leaves the probe %s as %s: a second run would write again" % (rid, c, blk))
    # every open cell of the cave (where a player could stand) is inside a box that holds the restore
    boxes = [zone_of(l) for l in entry if l.startswith("tag @a[x=")]
    for (x, y, z), b in old.items():
        if base(b) in (AIR, "minecraft:barrier") and y > -64:
            if not any(bx[0] <= x <= bx[3] and bx[1] <= y <= bx[4] and bx[2] <= z <= bx[5] for bx in boxes):
                out.append("%s: the open cell (%d, %d, %d) is in no box that holds the restore" % (rid, x, y, z))
                break
    # the successor's build refuses while any probe shows
    succ = rc.get("successor")
    if succ:
        bl = fns.get("build_%s" % succ, [])
        for (c, blk, _fn) in probes:
            if "execute if block %d %d %d %s run return 0" % (c[0], c[1], c[2], blk) not in bl:
                out.append("%s: %s's build does not refuse while the probe %s shows" % (rid, succ, c))
    return out


# ------------------------------------------------------------------ the whole audit

def cached(g):
    memo = {}

    def gr(x, z):
        k = (x, z)
        if k not in memo:
            memo[k] = g(x, z)
        return memo[k]
    return gr


def audit(spec, fns, callback, ground, walk_it=True, only=None, restore=True):
    """(problems, notes). `only` limits the per-sanctuary checks to those ids; `restore` False skips the retired caves (tests)."""
    probs, notes = [], []
    sigs = {}
    for san in spec["sanctuaries"]:
        sid = san["id"]
        if only and sid not in only:
            continue
        lines = fns.get("build_%s" % sid)
        if not lines:
            probs.append("%s: no build function" % sid)
            continue
        written = replay(lines)
        yf, bars = floor_of(written)
        if yf is None:
            probs.append("%s: no barrier written: the door has no closed state" % sid)
            continue
        cx, cz = san["site"]["centre"]
        probs += ground_problems(spec, sid, written, ground, yf)
        probs += light_problems(sid, written)
        probs += spawn_problems(sid, written)
        lp, kinds = look_problems(sid, written, yf)
        probs += lp
        sigs[sid] = kinds
        probs += gate_problems(spec, san, fns, written, bars, yf)
        probs += keeper_problems(spec, san, fns, callback, yf)
        probs += record_problems(spec, san, written, yf)
        if walk_it:
            xs = [c[0] for c in written]
            zs = [c[2] for c in written]
            ys = [c[1] for c in written]
            box = (min(xs) - 4, min(ys) - 2, min(zs) - 4, max(xs) + 4, max(ys) + 3, max(zs) + 4)
            near = spec["gate"]
            ante = zone_of(fns["gate/%s/near" % sid][1])
            closed = walk(Terrain(written, ground, open_door=False), box)
            spot = (cx, yf + 1, cz)
            if spot in closed:
                probs.append("%s: with the door CLOSED a player on foot reaches the court's centre %s" % (sid, spot))
            if not any(ante[0] <= x <= ante[3] and ante[2] <= z <= ante[5] for (x, y, z) in closed):
                probs.append("%s: the forecourt %s cannot be reached on foot" % (sid, ante))
            opened = walk(Terrain(written, ground, open_door=True), box)
            if spot not in opened:
                probs.append("%s: with the door OPEN a player on foot does not reach the court's centre %s" % (sid, spot))
            notes.append("%s: walked %d cells closed, %d open (gate reach %d)" % (sid, len(closed), len(opened), near["reach"]))
    ids = sorted(sigs)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            j = len(sigs[a] & sigs[b]) / max(1, len(sigs[a] | sigs[b]))
            if j > 0.5:
                probs.append("%s and %s are built of mostly the same blocks (%.0f%% shared)" % (a, b, 100 * j))
    built = {}
    for rc in spec["retired_caves"] if restore else []:
        probs += restore_problems(spec, rc, fns, ground, built)
    probs += retired_left(spec)
    for rc in spec["retired_caves"]:
        if rc.get("successor") is None:
            notes.append("%s: retired with no successor (restored only)" % rc["id"])
    return probs, notes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pack", default=str(PACK))
    p.add_argument("--no-walk", action="store_true")
    p.add_argument("--source-root")
    p.add_argument("--inputs-root", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    sys.path.insert(0, str(ROOT / "tools"))
    import ground as G
    g = cached(G.Ground(a.source_root))
    spec = load()
    fns, cb = read_pack(a.pack)
    if not fns:
        raise SystemExit("FAILED: no pack at %s (python tools/sanctuaries.py build)" % a.pack)
    probs, notes = audit(spec, fns, cb, g, walk_it=not a.no_walk)
    for n in notes:
        print("  NOTE:", n)
    for pr in probs:
        print("PROBLEM:", pr)
    print("sanctuaries audit: %d sanctuaries, %d retired caves, %d problem(s)" % (len(spec["sanctuaries"]), len(spec["retired_caves"]), len(probs)))
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())
