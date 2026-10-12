#!/usr/bin/env python
"""The audit of the cave kit (data/caves.json, pack cobblers_caves). Its derivation is its own; read the limits below.

INDEPENDENCE, AND ITS LIMIT. Written 2026-10-12 by the same session that wrote tools/caves.py (CLAUDE.md principle 16 asks for
a different agent; there was none to hand, so a second agent should grade this file). What it does to earn trust anyway:

  * it imports NOTHING from tools/caves.py, tools/mines.py or tools/mining_caves.py: the expectation is derived from
    data/caves.json's `geometry.rules` text, the cave's record and the canonical ground (tools/ground.py), by code of its own
    (column arrays and intervals here, a dict of cells there);
  * the pack is read as text and replayed by this file's own parser (fill and setblock in file order, last write wins), and the
    replay is compared with the expectation both ways: every cell the pack writes is a cell the rules give, with that block,
    and every cell the rules give is written;
  * tests/test_caves_audit.py MUTATES THE GENERATOR (the chamber's oval, the shell's margin, the door's width inside
    tools/caves.py), never the record, and requires this audit to fail each time (how to prove an audit is independent,
    CLAUDE.md).
Shared on purpose, because they are data readers and not derivations: tools/ground.py (the heightmap) and tools/function_limits.py.

What it checks, per cave:
  cells      the replay equals the expectation (above), and the pack writes only blocks of the palette and the fixed set; no light
             block, no torch, no block data/spawn_blocks.json names that data/spawn_block_policy.json does not allow for `caves`
  seal       every neighbour of an air cell is air or a written solid, except at the mouth's open cutting (the shell is real)
  cover      ground over every tunnel column's air top is at least the rules' cover_min
  walk       from outside the mouth, with the door CLOSED, the player reaches the antechamber and not the chamber; with the door
             OPEN, the chamber's centre; and back out, in 1-block steps
  gate       the near / open / close functions: flags equal the record's, the zone boxes equal the rules' (recomputed), the open
             fill removes exactly the barrier cells and the close fill puts exactly them back, never a flag-less opening
  keeper     static: every selector that kills, holds, wakes or settles a Pokemon carries tag=!cobblers.guardian; nothing in the
             pack adds or removes cobblers.guardian or the blackout's exempt tag; the clocks are 24,000 and 72,000; the spawn is a
             macro line; the callback sets the caught flag only within catch_radius of the spot
  records    the Habitat Blocks and pools in data/habitat_blocks.json and data/spawns.json match the rules (position, mimic, range,
             pool, ultra-rare occupant, levels under the gate's cap) and nothing else of the file's is touched
  natural    (mode `natural`) the cave carries no occupant, gate, habitat, antechamber, reward or keeper; no Habitat Block, pool, spawn
             entry or function of the pack names it but its build; nothing it writes is timber, a lantern, a barrier or a crystal; and
             the centre line of its written passage air moves at least 4 across and turns back (it winds), read off the cells and not
             the record. Its offset rows, the ore in exposed walls and the floor patches are derived from the rules text like the rest
  keep clear (--inputs-root <full checkout>) the nearest distance from every written column to towns, route paths and legs, corridor
             boxes, placements, earthworks, other packs' writes, authored x/z, painted water and the water export

Not covered, and it needs a running server: that the commands parse and behave as the stated vanilla semantics say; that a
Pokemon spawns in a sealed chamber from an activated block (HB-1, RS-1); the alpha re-level near a no_ai boss (AB-1); the
callback firing (EXP-042 says it does from this path); the barrier stopping a thrown ball (legendaries.py cites it, unmeasured).

  python tools/caves_audit.py [--pack DIR] [--inputs-root <full checkout>] [--no-walk]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "caves.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_caves"
FN = "cobblers:caves/"
GUARD = "cobblers.guardian"
EXEMPT_HINT = "exempt"           # data/blackout.json claims.exempt_tag's family: the pack must never name it
PASS = ("minecraft:air", "minecraft:cave_air")
# blocks that give light without being a lantern: a light block is never used (docs/STATE.md, places are lit as towns)
LIGHT = ("light", "torch", "glowstone", "sea_lantern", "shroomlight", "jack_o_lantern", "froglight", "lava", "fire", "candle", "campfire",
         "redstone_lamp", "end_rod", "beacon", "conduit")


class AuditError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def jload(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def base(block):
    return block.split("[")[0].split("{")[0]


def norm(block):
    """A block as compared: its id and the state keys that matter to what a player sees and walks on."""
    b = base(block)
    props = {}
    if "[" in block:
        for kv in block[block.index("[") + 1:block.rindex("]")].split(","):
            k, _, v = kv.partition("=")
            if k in ("facing", "axis", "hanging", "half"):
                props[k] = v
    return b + ("[" + ",".join("%s=%s" % kv for kv in sorted(props.items())) + "]" if props else "")


def frame(anchor, front):
    """(u, d) -> (x, z), from the rules text: north: the player stands north and d runs +z; south: -z; west: +x; east: -x; u runs
    +x on a north or south front and +z on a west or east one."""
    ax, az = anchor
    return {"north": lambda u, d: (ax + u, az + d), "south": lambda u, d: (ax + u, az - d),
            "west": lambda u, d: (ax + d, az + u), "east": lambda u, d: (ax - d, az + u)}[front]


def h32(*vals):
    """The 32-bit mix the rules text names (tools/mines.py's: FNV-style, two xor-shift-multiply rounds a value)."""
    a = 0x811C9DC5
    for v in vals:
        a = ((a ^ (int(v) & 0xFFFFFFFF)) * 0x01000193) & 0xFFFFFFFF
        a ^= a >> 15
        a = (a * 0x2C1B3C6D) & 0xFFFFFFFF
        a ^= a >> 12
    return a


def sid(s):
    return len(s) * 1000003 + sum(ord(c) * (i + 1) for i, c in enumerate(s))


# ------------------------------------------------------------------ the expectation, from the rules text

class Plan:
    """One cave's rows and parts, from its record (no ground): spans (d0, d1, kind, hw, h), the door, the link, the chamber."""

    def __init__(self, spec, cave):
        geo = spec["geometry"]
        ps = cave["passages"]
        self.spans = []
        hw0, h0 = (ps[0]["width"] - 1) // 2, ps[0]["height"]
        self.hw0, self.h0, self.drop = hw0, h0, ps[0]["length"]
        self.spans.append((0, 0, "mouth", hw0, h0))
        self.spans.append((1, self.drop, "stair", hw0, h0))
        d = self.drop + 1
        self.passages = []
        self.off = {}                    # row d -> the lateral offset of its centre line (a natural cave's bend, from the rules text)
        c0 = 0
        for i, q in enumerate(ps[1:], 1):
            n, b = q["length"], q.get("bend", 0)
            self.spans.append((d, d + n - 1, "level", (q["width"] - 1) // 2, q["height"]))
            self.passages.append((d, d + n - 1, (q["width"] - 1) // 2, q["kind"]))
            for k in range(n):
                self.off[d + k] = c0 + (2 * b * (k + 1) + n) // (2 * n)
            c0 += b
            d += n
        self.uc = c0
        a = cave.get("antechamber")
        self.ante = None
        if a:
            self.ante = (d, d + a["length"] - 1, a["half_width"], a["height"])
            self.spans.append((d, d + a["length"] - 1, "ante", a["half_width"], a["height"]))
            d += a["length"]
        self.door = None
        if (cave.get("gate") or {}).get("kind") == "partition":
            self.door = d
            self.spans.append((d, d, "door", geo["door_half_width"], geo["door_height"]))
            d += 1
            self.spans.append((d, d + geo["link_rows"] - 1, "link", geo["door_half_width"], geo["door_height"]))
            d += geo["link_rows"]
        ch = cave["chamber"]
        self.ch = dict(ch, d0=d, dc=d + ch["rz"], d1=d + 2 * ch["rz"])
        self.total = self.ch["d1"] + 1

    def row(self, d):
        for d0, d1, kind, hw, h in self.spans:
            if d0 <= d <= d1:
                return kind, hw, h
        return None

    def in_chamber(self, u, d):
        """u across the whole cave: the oval is centred on u = self.uc."""
        c = self.ch
        u = u - self.uc
        return c["d0"] <= d <= c["d1"] and u * u * c["rz"] ** 2 + (d - c["dc"]) ** 2 * c["rx"] ** 2 <= c["rx"] ** 2 * c["rz"] ** 2


def expected(spec, cave, ground):
    """{(x, y, z): normalised block} of everything the rules say the cave writes, and the facts the checks need."""
    geo, pal = spec["geometry"], cave["palette"]
    mar, cov = geo["margins"], geo["cover_min"]
    xz = frame(cave["mouth"]["anchor"], cave["mouth"]["front"])
    front = cave["mouth"]["front"]
    P = Plan(spec, cave)
    hw0, h0 = P.hw0, P.h0
    gs = sorted(ground(*xz(u, -1)) for u in range(-hw0 - 1, hw0 + 2))
    y0 = gs[(len(gs) - 1) // 2]
    yh = y0 - P.drop

    def ft(d):
        return y0 if d == 0 else (y0 - d + 1 if d <= P.drop else yh)

    E, role = {}, {}
    air_cols = {}                                  # (x, z) -> (floor, air top, margin, cut, kind)
    cuts = 0
    probs = []
    stair = "%s[facing=%s,half=bottom]" % (pal["stair"], front)

    def set_(c, blk, why):
        E[c] = norm(blk)
        role[c] = why

    # rows of the passages, rooms and the mouth
    for d in range(0, P.total):
        r = P.row(d)
        if r is None:
            continue
        kind, hw, h = r
        f = ft(d)
        top_air = f + h
        cut = False
        if kind in ("mouth", "stair"):
            gmin = min(ground(*xz(u, d)) for u in range(-hw - 1, hw + 2))
            cut = gmin < top_air + 1 + cov["passage"]
            cuts += cut
        c = P.off.get(d, 0)
        for u in range(c - hw, c + hw + 1):
            x, z = xz(u, d)
            g = ground(x, z)
            top = max(g, top_air) + geo["clear_above"] if cut else top_air
            air_cols[(x, z)] = (f, top, mar["cutting"] if cut else (mar["room"] if kind == "ante" else mar["passage"]), cut,
                                "room" if kind == "ante" else "passage")
            if not cut and g - top < (cov["room"] if kind == "ante" else cov["passage"]):
                probs.append("cover: row %d column (%d, %d) has %d of ground over its air top" % (d, x, z, g - top))
    for d in range(P.ch["d0"], P.ch["d1"] + 1):
        for u in range(P.uc - P.ch["rx"], P.uc + P.ch["rx"] + 1):
            if P.in_chamber(u, d):
                x, z = xz(u, d)
                top = yh + P.ch["h"]
                air_cols[(x, z)] = (yh, top, mar["room"], False, "room")
                if ground(x, z) - top < cov["room"]:
                    probs.append("cover: chamber column (%d, %d) has %d of ground over its air top" % (x, z, ground(x, z) - top))
    for (x, z), (f, top, m, cut, kind) in air_cols.items():
        g = ground(x, z)
        for y in range(g + 1, f):
            set_((x, y, z), pal["shell"], "fill")
        if f - 1 - g > geo["max_fill"]:
            probs.append("fill: column (%d, %d) is built up %d under its floor, over max_fill %d" % (x, z, f - 1 - g, geo["max_fill"]))
        set_((x, f, z), pal["floor"], "floor")
        for y in range(f + 1, top + 1):
            set_((x, y, z), "minecraft:air", "air")
    # stairs replace the floor on the incline rows
    for d in range(1, P.drop + 1):
        for u in range(-hw0, hw0 + 1):
            x, z = xz(u, d)
            set_((x, ft(d), z), stair, "stair")
    # the mouth's frame (a natural cave has none)
    natural = cave.get("mode") == "natural"
    if not natural:
        for u in (-hw0 - 1, hw0 + 1):
            x, z = xz(u, 0)
            for y in range(ground(x, z) + 1, y0 + 1):
                set_((x, y, z), pal["shell"], "fill")
            for y in range(y0 + 1, y0 + h0 + 1):
                set_((x, y, z), "%s[axis=y]" % pal["timber"], "post")
        for u in range(-hw0 - 1, hw0 + 2):
            x, z = xz(u, 0)
            set_((x, y0 + h0 + 1, z), "%s[axis=%s]" % (pal["timber"], "x" if front in ("north", "south") else "z"), "beam")
        x, z = xz(0, 0)
        if role.get((x, y0 + h0, z)) == "air":
            set_((x, y0 + h0, z), "minecraft:lantern[hanging=true]", "hanglantern")
    # the door
    door_cells = []
    if P.door is not None:
        _k, hw, h = P.row(P.door)
        for u in range(-hw, hw + 1):
            x, z = xz(u, P.door)
            for y in range(yh + 1, yh + h + 1):
                set_((x, y, z), "minecraft:barrier", "barrier")
                door_cells.append((x, y, z))
    # lantern posts
    posts = []
    every = (cave.get("light") or {}).get("lantern_every", geo["lantern_every"])
    if not natural and not (cave.get("light") or {}).get("dark_by_design"):
        k = 0
        for d0, d1, hw, kind in P.passages:
            if kind == "crawl" or hw < 1:
                continue
            for d in range(d0, d1 + 1):
                if (d - d0) % every == every // 2:
                    posts.append((P.off.get(d, 0) + (-hw if k % 2 == 0 else hw), d))
                    k += 1
        if P.ante:
            a0, a1, ahw, _ah = P.ante
            posts += [(-(ahw - 1), a1 - 1), (ahw - 1, a1 - 1)]
        ur, dr = round(0.6 * P.ch["rx"]), round(0.55 * P.ch["rz"])
        n = (cave.get("light") or {}).get("chamber_lanterns", 4)
        posts += [(P.uc - ur, P.ch["dc"] - dr), (P.uc + ur, P.ch["dc"] - dr), (P.uc - ur, P.ch["dc"] + dr), (P.uc + ur, P.ch["dc"] + dr)][:n]
    for u, d in posts:
        x, z = xz(u, d)
        if role.get((x, yh + 1, z)) == "air" and role.get((x, yh + 2, z)) == "air":
            set_((x, yh + 1, z), pal["fence"], "fence")
            set_((x, yh + 2, z), "minecraft:lantern[hanging=false]", "lantern")
        else:
            probs.append("lantern post u=%d d=%d does not stand in free air" % (u, d))
    # the chamber feature
    feat = cave["chamber"].get("feature", "none")
    if feat == "columns":
        c = round(0.5 * P.ch["rx"])
        for u in (P.uc - c, P.uc + c):
            x, z = xz(u, P.ch["dc"])
            for y in range(yh + 1, yh + P.ch["h"] + 1):
                set_((x, y, z), pal["column"], "column")
    elif feat in ("crystal", "knobs"):
        rx, rz, dc = P.ch["rx"], P.ch["rz"], P.ch["dc"]
        cand = [(u, d) for d in range(P.ch["d0"], P.ch["d1"] + 1) for u in range(P.uc - rx, P.uc + rx + 1)
                if P.in_chamber(u, d) and ((u - P.uc) / rx) ** 2 + ((d - dc) / rz) ** 2 >= 0.16 and (u, d) not in set(posts)]
        cand.sort(key=lambda c: (h32(spec["seed"], sid(cave["id"]), c[0], c[1]), c))
        for u, d in cand[:cave["chamber"].get("crystal_count", 8) if feat == "crystal" else cave["chamber"]["knob_count"]]:
            x, z = xz(u, d)
            if role.get((x, yh + 1, z)) == "air":
                if feat == "crystal":
                    set_((x, yh + 1, z), "minecraft:amethyst_cluster[facing=up]", "crystal")
                else:
                    set_((x, yh + 1, z), pal["knob"], "knob")
    # the shell: round every air column, the hull of its neighbours' intervals, under the ground
    hull = {}
    for (x, z), (f, top, m, cut, _k) in air_cols.items():
        for dx in range(-m, m + 1):
            for dz in range(-m, m + 1):
                cur = hull.get((x + dx, z + dz))
                lo, hi = f + 1 - m, top + m
                hull[(x + dx, z + dz)] = (lo, hi, cut) if cur is None else (min(cur[0], lo), max(cur[1], hi), cur[2] or cut)
    for (x, z), (lo, hi, cut) in hull.items():
        cap = ground(x, z) if cut else ground(x, z) - 1
        for y in range(lo, min(hi, cap) + 1):
            if (x, y, z) not in E:
                set_((x, y, z), pal["shell"], "shell")
    # a natural cave's dressing, from the rules text: ore showing in the walls, patches in the floor
    if natural:
        dr, sidc = cave["dressing"], sid(cave["id"])
        nb = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
        todo = []
        for (x, y, z), why in role.items():
            if why == "shell" and h32(spec["seed"], sidc, x, y, z) % dr["vein_one_in"] == 0 and any(role.get((x + a, y + b, z + c)) == "air" for a, b, c in nb):
                todo.append(((x, y, z), pal["vein"], "vein"))
            elif why == "floor" and h32(spec["seed"], sidc, x, z, 7) % dr["patch_one_in"] == 0:
                todo.append(((x, y, z), pal["patch"], "patch"))
        for c, blk, why in todo:
            set_(c, blk, why)
    return {"E": E, "role": role, "air_cols": air_cols, "y0": y0, "yh": yh, "plan": P, "xz": xz, "cuts": cuts, "door_cells": door_cells,
            "posts": posts, "problems": probs}


# ------------------------------------------------------------------ reading the pack

def read_pack(pack=PACK):
    pack = Path(pack)
    fdir = pack / "data" / "cobblers" / "function" / "caves"
    if not fdir.is_dir():
        raise AuditError("no built pack at %s (python tools/caves.py build)" % pack)
    fns = {p.relative_to(fdir).with_suffix("").as_posix(): p.read_text(encoding="utf-8").splitlines() for p in fdir.rglob("*.mcfunction")}
    cb = pack / "data" / "cobblemon" / "callbacks" / "pokemon_captured" / "cobblers_caves.molang"
    return fns, (cb.read_text(encoding="utf-8") if cb.is_file() else "")


def replay(lines):
    """{(x, y, z): normalised block} of a build function's fills and setblocks, in order."""
    out = {}
    for line in lines:
        t = line.split()
        if not t:
            continue
        if t[0] == "setblock":
            out[tuple(int(v) for v in t[1:4])] = norm(t[4])
        elif t[0] == "fill":
            x0, y0, z0, x1, y1, z1 = (int(v) for v in t[1:7])
            if len(t) > 8:
                raise AuditError("a filtered or modal fill in a build function: %s" % line)
            b = norm(t[7])
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        out[(x, y, z)] = b
    return out


# ------------------------------------------------------------------ the checks

def cell_problems(spec, cave, ex, written):
    probs = []
    E = ex["E"]
    miss = [c for c in E if c not in written]
    extra = [c for c in written if c not in E]
    wrong = [c for c in E if c in written and written[c] != E[c]]
    if miss:
        probs.append("%s: %d cell(s) the rules give are not written, e.g. %s %s" % (cave["id"], len(miss), min(miss), E[min(miss)]))
    if extra:
        probs.append("%s: %d cell(s) the pack writes are not in the rules, e.g. %s %s" % (cave["id"], len(extra), min(extra), written[min(extra)]))
    if wrong:
        c = min(wrong)
        probs.append("%s: %d cell(s) differ from the rules, e.g. %s is %s, the rules say %s" % (cave["id"], len(wrong), c, written[c], E[c]))
    pal = set(base(v) for v in cave["palette"].values())
    fixed = {"minecraft:air", "minecraft:barrier", "minecraft:lantern", "minecraft:amethyst_cluster"}
    for b in sorted({base(v) for v in written.values()} - pal - fixed):
        probs.append("%s: writes %s, a block outside the palette and the fixed set" % (cave["id"], b))
    for b in sorted({base(v) for v in written.values()}):
        if any(w in b for w in LIGHT):
            probs.append("%s: writes %s, a light source other than a lantern" % (cave["id"], b))
    spawn = set(jload("spawn_blocks.json")["blocks"])
    allowed = {b for w in jload("spawn_block_policy.json")["whitelist"] if "caves" in (w.get("scope") or "") for b in w["blocks"]}
    for b in sorted(({base(v) for v in written.values()} & spawn) - allowed):
        probs.append("%s: writes %s, a spawn condition no policy entry scoped to caves allows" % (cave["id"], b))
    probs += ["%s: %s" % (cave["id"], p) for p in ex["problems"]]
    if ex["cuts"] > spec["geometry"]["max_cutting_rows"]:
        probs.append("%s: %d open cutting rows over the rules' %d" % (cave["id"], ex["cuts"], spec["geometry"]["max_cutting_rows"]))
    return probs


def seal_problems(cave, ex, written, ground):
    """Every neighbour of an air cell is air or a written solid, but for the open cutting's sky and the mouth's air above ground."""
    probs = []
    for (x, y, z), b in written.items():
        if b not in PASS:
            continue
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0)):
            n = (x + dx, y + dy, z + dz)
            nb = written.get(n)
            if nb is None:
                if n[1] > ground(n[0], n[2]):
                    continue                      # the sky over a cutting
                probs.append("%s: air (%d, %d, %d) touches the unwritten natural cell %s: the shell does not seal it" % (cave["id"], x, y, z, n))
                return probs
    return probs


def solid(c, written, ground, open_door):
    b = written.get(c)
    if b is None:
        return c[1] <= ground(c[0], c[2])
    if b == "minecraft:barrier":
        return not open_door
    return b not in PASS and not b.startswith("minecraft:lantern[hanging=true")


def walk(cave, ex, written, ground, open_door):
    """BFS of standable feet cells (a 1 x 2 body), 1-block steps up or down, from outside the mouth. Fence posts and lanterns
    block (a fence is 1.5 high)."""
    xz = ex["xz"]
    hard = lambda c: solid(c, written, ground, open_door) or base(written.get(c, "")) in ("minecraft:spruce_fence", "minecraft:lantern")  # noqa: E731
    sx, sz = xz(0, -3)
    start = (sx, ground(sx, sz) + 1, sz)
    xs = [c[0] for c in written]
    zs = [c[2] for c in written]
    lim = (min(xs) - 8, min(zs) - 8, max(xs) + 8, max(zs) + 8)
    seen = {start}
    q = deque([start])
    while q:
        x, y, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (lim[0] <= nx <= lim[2] and lim[1] <= nz <= lim[3]):
                continue
            for dy in (0, 1, -1):
                ny = y + dy
                n = (nx, ny, nz)
                if n in seen or hard(n) or hard((nx, ny + 1, nz)) or not hard((nx, ny - 1, nz)):
                    continue
                if dy == 1 and hard((x, y + 2, z)):
                    continue
                if dy == -1 and hard((nx, y + 1, nz)):
                    continue
                seen.add(n)
                q.append(n)
    return seen


def walk_problems(spec, cave, ex, written, ground):
    probs = []
    P = ex["plan"]
    xz, yh = ex["xz"], ex["yh"]
    centre = xz(P.uc, P.ch["dc"])
    ante = xz(0, (P.ante[0] + P.ante[1]) // 2) if P.ante else None
    closed = walk(cave, ex, written, ground, False)
    opened = walk(cave, ex, written, ground, True)
    cc = (centre[0], yh + 1, centre[1])
    if P.door is not None:
        if cc in closed:
            probs.append("%s: the chamber is reachable with the door closed" % cave["id"])
        if ante and (ante[0], yh + 1, ante[1]) not in closed:
            probs.append("%s: the antechamber is not reachable from outside the mouth with the door closed" % cave["id"])
    elif cc not in closed:
        probs.append("%s: the chamber centre %s is not walkable from outside the mouth" % (cave["id"], cc))
    if cc not in opened:
        probs.append("%s: the chamber centre %s is not walkable with the door open" % (cave["id"], cc))
    return probs


def box_of(sel):
    m = re.search(r"x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(-?\d+),dy=(-?\d+),dz=(-?\d+)", sel)
    x, y, z, dx, dy, dz = (int(v) for v in m.groups())
    return [x, y, z, x + dx, y + dy, z + dz]


def zone(xz, u0, u1, d0, d1, ya, yb):
    pts = [xz(u0, d0), xz(u1, d1), xz(u0, d1), xz(u1, d0)]
    return [min(p[0] for p in pts), ya, min(p[1] for p in pts), max(p[0] for p in pts), yb, max(p[1] for p in pts)]


def gate_problems(spec, cave, ex, fns, written):
    cid = cave["id"]
    g = cave.get("gate") or {"kind": "none"}
    P = ex["plan"]
    names = ["gate/%s/%s" % (cid, n) for n in ("near", "open", "close")]
    if g["kind"] != "partition":
        return ["%s: a gate function exists for an ungated cave" % cid] if any(n in fns for n in names) else []
    probs = []
    if not all(n in fns for n in names):
        return ["%s: the gate's near / open / close functions are missing" % cid]
    near, opn, cls = ("\n".join(fns[n]) for n in names)
    xz, yh = ex["xz"], ex["yh"]
    adv = ",".join("cobblers:flag/%s=true" % f for f in g["flags"])
    ahw, a0, a1, ah = P.ante[2], P.ante[0], P.ante[1], P.ante[3]
    want_ante = zone(xz, -ahw, ahw, a0, a1, yh + 1, yh + ah)
    lines = [l for l in fns[names[0]] if l.startswith("execute")]
    openers = [l for l in lines if l.endswith("/open")]
    closers = [l for l in lines if l.endswith("/close")]
    if len(openers) != 1 or len(closers) != 1:
        return probs + ["%s: near must have exactly one opening line and one closing line" % cid]
    if "advancements={%s}" % adv not in openers[0]:
        probs.append("%s: the opening line does not ask for exactly the flags %s" % (cid, g["flags"]))
    if " unless score " not in openers[0]:
        probs.append("%s: the opening line does not test the open score" % cid)
    if box_of(openers[0]) != want_ante:
        probs.append("%s: the opening zone %s is not the antechamber %s" % (cid, box_of(openers[0]), want_ante))
    if "advancements={%s}" % adv not in closers[0] or "gamemode=!spectator" not in closers[0]:
        probs.append("%s: the closing line must test the flags and the inside zone" % cid)
    boxes = [box_of(s) for s in re.findall(r"@a\[[^\]]*dz=-?\d+[^\]]*\]", closers[0])]
    ch = P.ch
    need_inside = zone(xz, -ch["rx"], ch["rx"], P.door, ch["d1"], yh + 1, yh + ch["h"])
    inside = [b for b in boxes if b != want_ante]
    if not inside:
        probs.append("%s: the closing line has no inside zone: it would shut a player in" % cid)
    else:
        b = inside[0]
        if not (b[0] <= need_inside[0] and b[2] <= need_inside[2] and b[3] >= need_inside[3] and b[5] >= need_inside[5]
                and b[1] <= yh + 1 and b[4] >= yh + ch["h"]):
            probs.append("%s: the inside zone %s does not hold the door, link and chamber %s" % (cid, b, need_inside))
    door = sorted(ex["door_cells"])
    f_open = [l for l in opn.splitlines() if l.startswith("fill ")]
    f_close = [l for l in cls.splitlines() if l.startswith("fill ")]
    box = [min(c[0] for c in door), min(c[1] for c in door), min(c[2] for c in door), max(c[0] for c in door), max(c[1] for c in door), max(c[2] for c in door)]
    if len(box) and (len(door) != (box[3] - box[0] + 1) * (box[4] - box[1] + 1) * (box[5] - box[2] + 1)):
        probs.append("%s: the barrier cells are not a full box" % cid)
    if len(f_open) != 1 or [int(v) for v in f_open[0].split()[1:7]] != box or f_open[0].split()[7:] != ["minecraft:air", "replace", "minecraft:barrier"]:
        probs.append("%s: the open fill is not 'fill <the barrier box> air replace barrier': %s" % (cid, f_open))
    if len(f_close) != 1 or [int(v) for v in f_close[0].split()[1:7]] != box or f_close[0].split()[7:] != ["minecraft:barrier", "replace", "minecraft:air"]:
        probs.append("%s: the close fill is not 'fill <the barrier box> barrier replace air': %s" % (cid, f_close))
    barrier_written = sorted(c for c, b in written.items() if b == "minecraft:barrier")
    if barrier_written != door:
        probs.append("%s: the barrier cells written (%d) are not the door row's %d" % (cid, len(barrier_written), len(door)))
    # the door spans the whole cross-section of its row: no air cell of the door row's columns is left open
    _k, hw, h = P.row(P.door)
    for u in range(-hw, hw + 1):
        x, z = xz(u, P.door)
        for y in range(yh + 1, yh + h + 1):
            if written.get((x, y, z)) != "minecraft:barrier":
                probs.append("%s: door cell (%d, %d, %d) is %s, not a barrier" % (cid, x, y, z, written.get((x, y, z))))
                return probs
    if "scoreboard players set #%s_open cobblers.cv 0" % cid not in "\n".join(fns["build_%s" % cid]):
        probs.append("%s: the build does not reset the open score with the door closed" % cid)
    return probs


def natural_problems(spec, cave, ex, fns, written):
    """A natural cave has nothing in it: no occupant, gate, antechamber, reward, keeper, Habitat Block or pool, no function but its
    build, no timber, lantern, fence, column or barrier, and its passage really winds (read off the written air, not the record)."""
    cid = cave["id"]
    probs = []
    for k in ("occupant", "gate", "habitat", "antechamber", "reward", "keeper"):
        if k in cave:
            probs.append("%s: a natural cave carries %s" % (cid, k))
    pal = cave["palette"]
    if set(pal) != {"shell", "floor", "stair", "vein", "patch", "knob"}:
        probs.append("%s: a natural cave's palette is shell, floor, stair, vein, patch and knob, not %s" % (cid, sorted(pal)))
    for name, lines in fns.items():
        if name != "build_%s" % cid and any(cid in l for l in lines):
            probs.append("%s: the pack function %s names a natural cave" % (cid, name))
    if any(cid in k for k in fns if k != "build_%s" % cid):
        probs.append("%s: the pack has a function of its own for a cave that has none (gate, boss or driver)" % cid)
    for b in jload("habitat_blocks.json")["blocks"]:
        if cid in json.dumps(b):
            probs.append("%s: Habitat Block %s names a natural cave" % (cid, b["id"]))
    sp = jload("spawns.json")
    for h in sp["habitats"]:
        if cid in json.dumps(h):
            probs.append("%s: spawn pool %s names a natural cave" % (cid, h["id"]))
    for e in sp["entries"]:
        if cid in json.dumps(e):
            probs.append("%s: spawn entry %s names a natural cave" % (cid, e["id"]))
    for b in sorted({base(v) for v in written.values()} & {"minecraft:lantern", "minecraft:barrier", "minecraft:amethyst_cluster"}):
        probs.append("%s: a natural cave writes %s" % (cid, b))
    timber = sorted({base(v) for v in written.values() if base(v).endswith(("_log", "_fence", "_wood", "_planks"))})
    if timber:
        probs.append("%s: a natural cave writes timber: %s" % (cid, ", ".join(timber)))
    # the passage winds: the centre line of the written air along the level rows, read off the cells
    P = ex["plan"]
    xz, yh = ex["xz"], ex["yh"]
    centres = []
    for d0, d1, _hw, _k in P.passages:
        for d in range(d0, d1 + 1):
            us = []
            for u in range(-80, 81):
                x, z = xz(u, d)
                if written.get((x, yh + 1, z)) in PASS:
                    us.append(u)
            if not us:
                probs.append("%s: row %d of the passage has no air at floor level" % (cid, d))
                return probs
            centres.append((min(us) + max(us)) / 2)
    if max(centres) - min(centres) < 4:
        probs.append("%s: the passage's centre line moves only %.1f across: it does not wind" % (cid, max(centres) - min(centres)))
    steps = [b - a for a, b in zip(centres, centres[1:]) if b != a]
    if not any(s1 * s2 < 0 for s1, s2 in zip(steps, steps[1:])):
        probs.append("%s: the passage's centre line never turns back: it is a diagonal, not a winding way" % (cid))
    return probs


def keeper_problems(spec, cave, ex, fns, callback):
    if cave.get("mode") == "natural":
        return ["%s: boss functions exist for a natural cave" % cave["id"]] if any(k.startswith("boss/%s/" % cave["id"]) for k in fns) else []
    occ = cave["occupant"]
    cid = cave["id"]
    mine = {k: v for k, v in fns.items() if k.startswith("boss/%s/" % cid)}
    if occ["mode"] != "area_boss":
        return ["%s: boss functions exist for a cave that has no boss" % cid] if mine else []
    probs = []
    if not mine:
        return ["%s: an area boss with no keeper" % cid]
    k = occ["keeper"]
    text = "\n".join("\n".join(v) for v in mine.values())
    # nothing may add or remove the blackout's guardian or its exempt tag
    for fn, ls in mine.items():
        for l in ls:
            if re.search(r"\btag\b[^#]*\b(add|remove)\b\s+" + re.escape(GUARD) + r"\b", l):
                probs.append("%s: %s adds or removes %s: %s" % (cid, fn, GUARD, l))
            if EXEMPT_HINT in l and "tag" in l:
                probs.append("%s: %s names an exempt tag: %s" % (cid, fn, l))
    # a command that acts on a Pokemon must not reach a guardian
    for fn, ls in mine.items():
        for l in ls:
            if l.startswith("#"):
                continue
            acts = (" kill " in l) or ("run function" in l and ("/hold" in l or "/wake" in l or "/settle" in l))
            if acts and "@e[" in l and "tag=!%s" % GUARD not in l:
                probs.append("%s: %s can reach a guardian: %s" % (cid, fn, l))
    for fn in ("hold", "wake", "settle", "bind"):
        for l in mine.get("boss/%s/%s" % (cid, fn), []):
            if re.match(r"(tp|data merge|tag)\b", l) and "@s" not in l:
                probs.append("%s: %s acts on something other than the Pokemon itself: %s" % (cid, fn, l))
    keep = "\n".join(mine["boss/%s/keep" % cid])
    if str(k["cooldown_faint_ticks"]) not in keep or str(k["cooldown_catch_ticks"]) not in keep:
        probs.append("%s: the keeper does not carry the clocks %d and %d" % (cid, k["cooldown_faint_ticks"], k["cooldown_catch_ticks"]))
    if (k["cooldown_faint_ticks"], k["cooldown_catch_ticks"]) != (24000, 72000):
        probs.append("%s: the respawn clocks are not 24,000 / 72,000" % cid)
    fl = ",".join("cobblers:flag/%s=true" % f for f in cave["gate"]["flags"])
    if "advancements={%s}" % fl not in keep:
        probs.append("%s: the keeper spawns without asking for a player holding %s" % (cid, cave["gate"]["flags"]))
    if "champion_cleared" not in fl:
        probs.append("%s: a boss that is a native alpha is spawned only for the Champion's conqueror" % cid)
    sp = mine["boss/%s/spawn_at" % cid]
    if len(sp) != 1 or not sp[0].startswith("$spawnpokemonat "):
        probs.append("%s: the spawn is not a single macro line (EXP-046)" % cid)
    else:
        for want in ["level=%d" % occ["level"]] + list(occ["properties"]):
            if want not in sp[0].split():
                probs.append("%s: the spawn line lacks %s" % (cid, want))
        if "alpha=true" not in sp[0]:
            probs.append("%s: the boss is not an alpha" % cid)
    bind = "\n".join(mine["boss/%s/bind" % cid])
    if "PersistenceRequired:1b" not in bind:
        probs.append("%s: the bound boss is not kept from the despawner" % cid)
    if "tag @s add %s" % occ["tag"] not in bind:
        probs.append("%s: bind does not tag the boss" % cid)
    cx, cy, cz = ex["xz"](ex["plan"].uc, ex["plan"].ch["dc"])[0], ex["yh"], ex["xz"](ex["plan"].uc, ex["plan"].ch["dc"])[1]
    want = "x=%d,y=%d,z=%d,distance=..%d" % (cx, cy + 1, cz, k["catch_radius"])
    if want not in callback:
        probs.append("%s: the capture callback does not set the caught flag within %d of the spot (%s)" % (cid, k["catch_radius"], want))
    if "cobblemon:%s" % occ["species"] not in callback:
        probs.append("%s: the callback does not name the species" % cid)
    # the boss spot is in the chamber, one above its floor
    spawn_line = "\n".join(mine["boss/%s/spawn" % cid])
    m = re.search(r'x:"(-?\d+\.\d)",y:(-?\d+),z:"(-?\d+\.\d)"', spawn_line)
    if not m or (float(m.group(1)) - 0.5, int(m.group(2)), float(m.group(3)) - 0.5) != (cx, cy + 1, cz):
        probs.append("%s: the boss spot %s is not the chamber's centre, one above the floor %s" % (cid, m and m.groups(), (cx, cy + 1, cz)))
    if "execute if loaded %d %d %d" % (cx, cy, cz) not in "\n".join(mine["boss/%s/keeper" % cid]):
        probs.append("%s: the keeper does not wait for the chamber's chunk" % cid)
    return probs


def foreign_problems(spec, cave, ex, written):
    """Spawn-free zones (data/spawn_suppression.json) and natural Habitat Blocks' influence, against the written columns."""
    out = []
    cid = cave["id"]
    m = spec["keep_clear"]["spawn_free_margin"]
    cols = {(x, z) for (x, _y, z) in written}
    for z in jload("spawn_suppression.json")["spawn_free_zones"]:
        x0, z0, x1, z1 = z["box"]
        hit = [c for c in cols if x0 - m <= c[0] <= x1 + m and z0 - m <= c[1] <= z1 + m]
        if hit:
            out.append("%s: %d written column(s) within %d of the spawn-free zone %s" % (cid, len(hit), m, z["id"]))
    P = ex["plan"]
    xz, yh = ex["xz"], ex["yh"]
    mine = {h["id"] for c in spec["caves"] for h in c.get("habitat") or []}
    spots = []
    for h in cave.get("habitat") or []:
        if h["part"] == "chamber":
            cx, cz = xz(P.uc, P.ch["dc"])
            spots.append((h["id"], (cx, yh, cz), cave["chamber"]["rx"]))
        else:
            cx, cz = xz(0, (P.ante[0] + P.ante[1]) // 2)
            spots.append((h["id"], (cx, yh, cz), P.ante[2] + 4))
    for b in jload("habitat_blocks.json")["blocks"]:
        if b["id"] in mine or b["style"] != "natural" or not b.get("replace_spawns"):
            continue
        for hid, c, rng in spots:
            d = math.sqrt(sum((a - e) ** 2 for a, e in zip(c, (b["position"]["x"], b["position"]["y"], b["position"]["z"]))))
            if d < b["range_of_influence"] + rng:
                out.append("%s: %s (reach %d) is %.1f from the natural block %s (range %d)" % (cid, hid, rng, d, b["id"], b["range_of_influence"]))
    return out


def record_problems(spec, cave, ex):
    probs = []
    cid = cave["id"]
    P = ex["plan"]
    xz, yh = ex["xz"], ex["yh"]
    blocks = {b["id"]: b for b in jload("habitat_blocks.json")["blocks"]}
    sp = jload("spawns.json")
    pools = {h["id"]: h for h in sp["habitats"]}
    flat = {}
    for e in sp["entries"]:
        flat.setdefault(e.get("scope"), []).append(e)
    caps = jload("legendaries.json")["level_caps"]["upper_bound_by_badges"]
    g = cave.get("gate") or {"kind": "none"}
    cap = min((100 if f == "champion_cleared" else int(caps[f[3]])) for f in g["flags"]) if g.get("flags") else None
    sub = {s["id"]: s for s in sp["subregions"]}
    # every species a keeper brings (the spec's own area bosses): no pool may name one, in any cave (a boss in a pool is a second home)
    bosses = {c["occupant"]["species"] for c in spec["caves"] if c.get("mode") != "natural" and c["occupant"]["mode"] == "area_boss"}
    for h in cave.get("habitat") or []:
        b = blocks.get(h["id"])
        if b is None:
            probs.append("%s: Habitat Block %s is not in data/habitat_blocks.json" % (cid, h["id"]))
            continue
        if h["part"] == "chamber":
            c = xz(P.uc, P.ch["dc"])
            want = (c[0], yh, c[1])
        else:
            a0, a1 = P.ante[0], P.ante[1]
            c = xz(0, (a0 + a1) // 2)
            want = (c[0], yh, c[1])
        got = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
        if got != want:
            probs.append("%s: %s is at %s, the rules put it at %s" % (cid, h["id"], got, want))
        if b["style"] != "activated" or b["activated"]["cancel_range"] != -1 or b["replace_spawns"] is not False:
            probs.append("%s: %s must be activated, cancelling nothing" % (cid, h["id"]))
        if b["mimic"] != cave["palette"]["floor"]:
            probs.append("%s: %s's mimic is not the floor block" % (cid, h["id"]))
        if b["pool"] != "cobblers:%s" % h["pool"]["id"] or h["pool"]["id"] not in pools:
            probs.append("%s: %s's pool %s is not in data/spawns.json habitats" % (cid, h["id"], b["pool"]))
            continue
        # a cell of the floor, in the part's own room
        if ex["role"].get(want) != "floor":
            probs.append("%s: %s does not stand on a floor cell of the rules" % (cid, h["id"]))
        if h["part"] == "chamber" and b["activated"]["spawn_range"] != P.ch["rx"]:
            probs.append("%s: %s's spawn_range is not the chamber's rx" % (cid, h["id"]))
        entries = flat.get(h["pool"]["id"], [])
        if len(entries) != len(h["pool"]["entries"]):
            probs.append("%s: pool %s has %d entries in data/spawns.json, the record has %d" % (cid, h["pool"]["id"], len(entries), len(h["pool"]["entries"])))
        subid = cave.get("site", {}).get("subregion")
        band = sub[subid]["level_band"] if subid in sub else None
        for e in entries:
            lo, _, hi = str(e["level"]).partition("-")
            lo, hi = int(lo), int(hi or lo)
            gated = h["part"] == "chamber" and cap is not None
            if gated and hi > cap:
                probs.append("%s: pool %s %s level %s is over the gate's cap %d" % (cid, h["pool"]["id"], e["species"], e["level"], cap))
            if not gated and band and hi > band["maximum"]:
                probs.append("%s: pool %s %s level %s is over the sub-region's band top %d" % (cid, h["pool"]["id"], e["species"], e["level"], band["maximum"]))
            if e["species"] in bosses:
                probs.append("%s: pool %s names a boss species, which only a keeper brings" % (cid, h["pool"]["id"]))
        occ = cave["occupant"]
        if occ["mode"] == "rare_spawn":
            mine = [e for e in entries if e["species"] == occ["species"]]
            if h["part"] == "chamber":
                if len(mine) != 1 or mine[0]["bucket"] != "ultra-rare":
                    probs.append("%s: the rare-spawn occupant must be one ultra-rare entry of the chamber's pool" % cid)
                elif cap is not None and int(str(mine[0]["level"]).split("-")[-1]) > cap:
                    probs.append("%s: the occupant's level is over the gate's cap" % cid)
                if len([e for e in entries if e["bucket"] == "ultra-rare"]) != 2:
                    probs.append("%s: the ultra-rare bucket must hold the occupant and one local family (two entries)" % cid)
                for co in occ.get("co_occupants") or []:
                    cm = [e for e in entries if e["species"] == co]
                    if len(cm) != 1 or cm[0]["bucket"] != "ultra-rare":
                        probs.append("%s: the co-occupant %s must be one ultra-rare entry of the chamber's pool" % (cid, co))
                    elif cap is not None and int(str(cm[0]["level"]).split("-")[-1]) > cap:
                        probs.append("%s: the co-occupant %s is over the gate's cap" % (cid, co))
        if occ["mode"] == "power_line" and h["part"] == "chamber":
            mine = [e for e in entries if e["species"] == occ["species"]]
            if len(mine) != 1 or mine[0]["bucket"] not in ("rare", "ultra-rare"):
                probs.append("%s: the power-line occupant must be one rare entry" % cid)
    return probs


# ------------------------------------------------------------------ keeping clear, against a full checkout

WRITE = re.compile(r"\b(fill|setblock|clone)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)(?:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+))?")
PLACE = re.compile(r"\bplace\s+(template|structure|feature|jigsaw)\s+\S+\s+(?:\S+\s+\S+\s+)?(-?\d+)\s+(-?\d+)\s+(-?\d+)")
TEMPLATE_HINT = 25


def other_pack_writes(packs_dir, own="cobblers_caves"):
    out = []
    for pd in sorted(p for p in Path(packs_dir).iterdir() if p.is_dir() and p.name != own):
        for f in (pd / "data").rglob("*.mcfunction") if (pd / "data").is_dir() else []:
            text = f.read_text(encoding="utf-8", errors="replace")
            for m in WRITE.finditer(text):
                ax, az = int(m.group(2)), int(m.group(4))
                bx, bz = (int(m.group(5)), int(m.group(7))) if m.group(5) else (ax, az)
                out.append((min(ax, bx), min(az, bz), max(ax, bx), max(az, bz), "write", "%s/%s" % (pd.name, f.name)))
            for m in PLACE.finditer(text):
                out.append((int(m.group(2)), int(m.group(4)), int(m.group(2)), int(m.group(4)), "place " + m.group(1), "%s/%s" % (pd.name, f.name)))
    return out


def keep_clear(spec, written_by_cave, inputs_root, ground, R=64):
    """{(cave, rule): (nearest, need, what, metric)}: every written column against every rule, Chebyshev for rectangles and
    Euclidean for lines. A distance over R is reported as R + 1."""
    import numpy as np
    from PIL import Image
    sys.path.insert(0, str(ROOT / "tools"))
    import southern_residents as SR   # the shared reader of every x/z another data file authors (data, not a derivation)
    ir = Path(inputs_root)
    kc = spec["keep_clear"]
    towns = jload("towns.json")["towns"]
    legs = [("leg %s-%s" % (l.get("from"), l.get("to")), l.get("polyline") or [])
            for l in json.loads((ir / "derived" / "routes" / "critical_legs.json").read_text(encoding="utf-8"))["legs"]]
    paths = list(jload("route_paths.json")["paths"].items())
    routes = jload("routes.json")["routes"]
    placements = jload("placements.json")["placements"]
    others = other_pack_writes(ir / "build" / "datapacks")
    paint = ir / "build" / "paint"
    man = json.loads((paint / "manifest.json").read_text(encoding="utf-8"))
    changed = np.load(ir / "derived" / "water_shape" / "changed.npy", mmap_mode="r")
    ids = {h["id"]: "ours" for c in spec["caves"] for h in c.get("habitat") or []}
    pts = SR.authored_points({"residents": [], "rules": {"authored_clearance_exempt": ids,
                                                         "authored_clearance_exempt_files": dict(spec["authored_exempt"]["files"])}}, own_file=SPEC)
    res = {}
    for cave in spec["caves"]:
        cols = sorted({(x, z) for (x, y, z) in written_by_cave[cave["id"]]})
        X = np.array([c[0] for c in cols])
        Z = np.array([c[1] for c in cols])
        x0, z0, x1, z1 = int(X.min()) - R, int(Z.min()) - R, int(X.max()) + R, int(Z.max()) + R

        def note(rule, d, need, what, metric="chebyshev"):
            k = (cave["id"], rule)
            d = float(min(d, R + 1))
            if k not in res or d < res[k][0]:
                res[k] = (d, need, what, metric)

        def rects(rule, boxes, need):
            note(rule, R + 1, need, "none within %d" % R)
            for (xa, za, xb, zb, what) in boxes:
                if xb < x0 or xa > x1 or zb < z0 or za > z1:
                    continue
                note(rule, np.maximum(np.maximum(xa - X, X - xb), np.maximum(za - Z, Z - zb)).clip(min=0).min(), need, what)

        def grid(rule, mask, gx0, gz0, need, what):
            zz, xx = np.nonzero(mask)
            if not len(xx):
                note(rule, R + 1, need, "none within %d" % R)
                return
            px, pz = xx + gx0, zz + gz0
            best = R + 1
            for i in range(0, len(X), 256):
                best = min(best, int(np.maximum(np.abs(px[None, :] - X[i:i + 256, None]), np.abs(pz[None, :] - Z[i:i + 256, None])).min()))
            note(rule, best, need, what)

        rects("town footprint", [(t["footprint"]["min_x"], t["footprint"]["min_z"], t["footprint"]["max_x"], t["footprint"]["max_z"], t["id"])
                                 for t in towns if (t.get("footprint") or {}).get("min_x") is not None], kc["town_margin"] + 1)
        rects("spawn corridor box", [(b["min_x"], b["min_z"], b["max_x"], b["max_z"], "%s %s" % (rt["id"], b.get("id")))
                                     for rt in routes for b in (rt.get("spawn_scope") or {}).get("boxes") or []], kc["corridor_clearance"] + 1)
        rects("placement position", [(int(p["position"]["x"]), int(p["position"]["z"]), int(p["position"]["x"]), int(p["position"]["z"]), p["id"])
                                     for p in placements if isinstance(p.get("position"), dict)
                                     and isinstance(p["position"].get("x"), (int, float)) and isinstance(p["position"].get("z"), (int, float))],
              kc["placement_reach"] + 1)
        ew = []
        for p in placements:
            for cmd in p.get("commands") or []:
                for m in WRITE.finditer(cmd):
                    ax, az = int(m.group(2)), int(m.group(4))
                    bx, bz = (int(m.group(5)), int(m.group(7))) if m.group(5) else (ax, az)
                    ew.append((min(ax, bx), min(az, bz), max(ax, bx), max(az, bz), p["id"]))
        rects("earthwork command", ew, kc["earthwork_gap"] + 1)
        # the caves' own Habitat Blocks are written by tools/habitat_blocks.py into cobblers_habitats: a single column at a
        # record data/habitat_blocks.json itself marks generated_by tools/caves.py is the cave's own, not a neighbour's
        # (read here from the records, not from tools/caves.py)
        own_hb = {(b["position"]["x"], b["position"]["z"]) for b in json.loads((ROOT / "data" / "habitat_blocks.json")
                  .read_text(encoding="utf-8"))["blocks"] if b.get("generated_by") == "tools/caves.py"}
        rects("another pack's write", [(a, b, c, d, w) for a, b, c, d, k, w in others if k == "write"
                                       and not (a == c and b == d and (a, b) in own_hb)], kc["pack_gap"] + 1)
        rects("another pack's placed structure origin", [(a, b, c, d, w) for a, b, c, d, k, w in others if k != "write"], TEMPLATE_HINT)
        rects("an x/z another data file authors", [(int(round(x)), int(round(z)), int(round(x)), int(round(z)), f) for x, z, f in pts],
              kc["authored_clearance"] + 1)
        note("route path or leg", R + 1, kc["road_clear"], "none within %d" % R, "euclidean")
        for name, line in legs + paths:
            for a, b in zip(line, line[1:] or line):
                if max(a[0], b[0]) < x0 or min(a[0], b[0]) > x1 or max(a[1], b[1]) < z0 or min(a[1], b[1]) > z1:
                    continue
                vx, vz = b[0] - a[0], b[1] - a[1]
                L = vx * vx + vz * vz
                t = np.zeros(len(X)) if L == 0 else (((X - a[0]) * vx + (Z - a[1]) * vz) / L).clip(0, 1)
                note("route path or leg", float(np.hypot(X - a[0] - t * vx, Z - a[1] - t * vz).min()), kc["road_clear"], name, "euclidean")
        wet = np.zeros((z1 - z0 + 1, x1 - x0 + 1), bool)
        for w in man["water"]:
            mm = np.asarray(Image.open(paint / w["levels" if "levels" in w else "mask"])) > 0
            h_, w_ = mm.shape
            za, xa = max(z0, w["z"]), max(x0, w["x"])
            zb, xb = min(z1 + 1, w["z"] + h_), min(x1 + 1, w["x"] + w_)
            if za < zb and xa < xb:
                wet[za - z0:zb - z0, xa - x0:xb - x0] |= mm[za - w["z"]:zb - w["z"], xa - w["x"]:xb - w["x"]]
        grid("painted water (build/paint)", wet, x0, z0, kc["water_reach"] + 1, "build/paint/manifest.json water")
        sea = int(jload("world.json")["vertical"]["sea_level"])
        low = np.array([[ground(x, z) <= sea for x in range(x0, x1 + 1)] for z in range(z0, z1 + 1)])
        grid("the sea (heightmap ground <= sea level)", low, x0, z0, kc["water_reach"] + 1, "y%d" % sea)
        grid("a column the water export changes", np.array(changed[z0:z1 + 1, x0:x1 + 1]) > 0, x0, z0, kc["water_changed_reach"] + 1,
             "derived/water_shape/changed.npy")
    return res


# ------------------------------------------------------------------ the whole

def cached(g):
    memo = {}

    def ground(x, z):
        k = (int(x), int(z))
        if k not in memo:
            memo[k] = int(g(*k))
        return memo[k]
    return ground


def audit(spec, fns, callback, ground, walk_it=True):
    """[problem] over every cave. fns: {function path under cobblers/caves/: lines}."""
    probs, writes = [], {}
    names = {c["id"] for c in spec["caves"]}
    for cave in spec["caves"]:
        cid = cave["id"]
        if "build_%s" % cid not in fns:
            probs.append("%s: no build function in the pack" % cid)
            continue
        ex = expected(spec, cave, ground)
        written = replay(fns["build_%s" % cid])
        writes[cid] = written
        probs += cell_problems(spec, cave, ex, written)
        probs += seal_problems(cave, ex, written, ground)
        if walk_it:
            probs += walk_problems(spec, cave, ex, written, ground)
        probs += gate_problems(spec, cave, ex, fns, written)
        probs += keeper_problems(spec, cave, ex, fns, callback)
        if cave.get("mode") == "natural":
            probs += natural_problems(spec, cave, ex, fns, written)
        probs += record_problems(spec, cave, ex)
        probs += foreign_problems(spec, cave, ex, written)
    for k in fns:
        if k.startswith("build_") and k[len("build_"):] not in names:
            probs.append("the pack has a build function %s for a cave the record does not have" % k)
    return probs, writes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--inputs-root", help="a full checkout (build/datapacks, build/paint, derived/routes, derived/water_shape)")
    ap.add_argument("--no-walk", action="store_true")
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "tools"))
    import ground as G
    ground = cached(G.Ground(a.source_root))
    spec = load()
    fns, callback = read_pack(a.pack)
    probs, writes = audit(spec, fns, callback, ground, not a.no_walk)
    print("caves audit: %d cave(s), %d problem(s) before keeping clear" % (len(spec["caves"]), len(probs)))
    if a.inputs_root:
        for (cid, rule), (d, need, what, metric) in sorted(keep_clear(spec, writes, a.inputs_root, ground).items()):
            look = rule.endswith("structure origin")
            bad = d < need and not look
            print("keep clear %-20s %-42s nearest %5.1f (%s) need >= %d  %s%s" % (
                cid, rule, d, metric, need, what, "  PROBLEM" if bad else "  LOOK" if look and d < need else ""))
            if bad:
                probs.append("keep clear %s: %s at %.1f, under %d (%s)" % (cid, rule, d, need, what))
    for p in probs:
        print("PROBLEM:", p)
    print("caves audit: %d problem(s)" % len(probs))
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())
