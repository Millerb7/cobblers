#!/usr/bin/env python
"""Offline audit of the Frostpeak research camp pack (build/datapacks/cobblers_frostpeak_camp), independent of its
generator.

What it reads: the WRITTEN pack (functions, dialogues, NPC classes, steps.txt), the authored data
(data/frostpeak_camp.json, data/adopted_legendary_sites.json, data/towns.json, data/spawn_blocks.json,
data/progression.json, data/world.json), the canonical heightmap through tools/ground.py, and, from --inputs-root
(the full checkout, because a worktree has no build/ or derived/), the other built packs, the painted water and the
water export's changed columns. It imports nothing from tools/frostpeak_camp.py: every expectation below is computed
here from the data and the heightmap, with its own maths (the tube's axis by quaternion-vector rotation rather than
the generator's matrix; sight lines by stepping column boundaries rather than fixed steps).

  C1  site       every written block is inside the authored site square
  C2  seat       every column's lowest solid block is ground + 1 (nothing buried, nothing floating), except a column
                 that holds only a wall sign, whose support is checked under C3
  C3  support    blocks that need support have it: carpet, campfire and standing lantern on a solid block below, a
                 hanging lantern under one, a wall sign on the block behind it
  C4  palette    every block is in data/frostpeak_camp.json blocks.ids, none is a spawn condition in
                 data/spawn_blocks.json, and nothing sets a respawn point (no bed, no respawn anchor)
  C5  clearing   every written column is cleared of replaceables (snow layers, plants) from its ground up, before
                 its first setblock
  C6  NPCs       every researcher in the data has a class, a dialogue and one spawnnpcat line; each stands on a written
                 solid block with two blocks of air above, at least 3 blocks from the next
  C7  aim        the telescope's tube points at the tower's centre column (bearing within 0.5 degrees) and meets it
                 between the lowest visible layer and the top, along a line clear of the terrain; the theodolite's
                 tube lies on the summit's bearing at the false crest's elevation; the summit platform is NOT visible
                 from it (so the false-crest line is true); each tube's axis passes through its pivot and clears its
                 pier, and each tube's block is a declared display block
  C8  numbers    every bearing, range, crown height, climb, distance and count of crown layers showing over the
                 crest that a sign or a page states matches this audit's own computation. The tower's top is
                 derived here as y + the template's height (data/structures.json footprint) - 1, not read from the
                 record's top_y, and the record's top_y is checked against it (C7 tower top)
  C9  no gate    the dialogues run no command, write no player data but their own cursor, show every option to every
                 player, and promise no summon (data/adopted_legendary_sites.json a_dead_altar_must_not_block)
  C10 clearance  no other built pack writes or summons within 8 blocks of the camp, no column is water (sea level or
                 painted), and no column within 8 is changed by the water export
  C11 limits     tools/function_limits.py finds nothing the server would refuse

Mutation record (2026-10-02, the generator mutated, the data untouched): flipping the yaw sign in the generator's
quaternion() (atan2(-dx, dz), the convention tools/rift_skin.py uses for sheets) fails C7 on both tubes. Raising every
floor by one in the generator's seat() PASSED the first version of this audit -- the foundation simply grew a course,
so nothing floated and nothing had a gap -- which is why C2 max+1 exists; with it, that mutation fails. The first run
of this audit also caught the generator's own crest search stepping whole blocks and aiming the theodolite 0.06
degrees into the crest; the generator now steps a quarter block. When the tower moved to the summit (2026-10-02) this
audit caught two more: the generator's quarter-block sight walk called the crown visible from y369 where the exact
column walk here says y370 (so a page stating 15 layers showing was one too many; the generator's sight test is now an
exact clip of the line to each column's square, a different method from this one), and the 40-degree telescope's
eyepiece end dipped 0.2 into its pier (the generator now shortens the tube's back end when it is steep).

  python tools/frostpeak_camp_audit.py [--pack DIR] [--inputs-root <full checkout>] [--source-root R]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402
import ground as G  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_frostpeak_camp"
FN = "data/cobblers/function/frostpeak_camp"
WORLD_READS: set = set()

SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+?)(\{.*\})?$")
CLEAR = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) minecraft:air replace #minecraft:replaceable$")
SUMMON = re.compile(r"^summon minecraft:block_display (\S+) (\S+) (\S+) (\{.*\})$")
OTHER_WRITE = re.compile(r"\b(fill|setblock|clone|summon \S+|place (?:template|feature|structure|jigsaw) \S+|spawnnpcat)\s+"
                         r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+))?")
NON_SOLID = ("minecraft:air", "minecraft:red_carpet", "minecraft:lantern", "minecraft:spruce_wall_sign",
             "minecraft:campfire")
DIR = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
PROMISES = re.compile(r"\b(will (summon|call|bring|appear|come)|guarantee|summons? it|it answers|always answers)\b", re.I)


class Report:
    def __init__(self):
        self.problems, self.passed = [], []

    def check(self, ok, name, msg):
        if ok:
            self.passed.append(name)
        else:
            self.problems.append("%s: %s" % (name, msg))


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def name_of(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def props(state):
    m = re.match(r"^[^\[{]+\[([^\]]*)\]", state)
    return dict(kv.split("=") for kv in m.group(1).split(",")) if m else {}


def compass(dx, dz):
    return math.degrees(math.atan2(dx, -dz)) % 360


def angdiff(a, b):
    return abs((a - b + 180) % 360 - 180)


def qrot(q, v):
    """v rotated by the unit quaternion q = [x, y, z, w]: v + 2w(u x v) + 2 u x (u x v)."""
    u, w = np.array(q[:3]), q[3]
    v = np.array(v, dtype=float)
    t = 2 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def ray_clear(g, a, b, skip=3.0):
    """Walk the columns the segment a->b crosses (boundary to boundary) and require the segment to stay above every
    column's ground block top at both the entry and the exit of the column."""
    ax, ay, az = a
    bx, by, bz = b
    dx, dz = bx - ax, bz - az
    hd = math.hypot(dx, dz)
    ts = {0.0, 1.0}
    for c0, c1, d in ((ax, bx, dx), (az, bz, dz)):
        if d:
            lo, hi = sorted((c0, c1))
            for k in range(math.floor(lo) + 1, math.floor(hi) + 1):
                ts.add((k - c0) / d)
    ts = sorted(t for t in ts if 0 <= t <= 1)
    for t0, t1 in zip(ts, ts[1:]):
        tm = (t0 + t1) / 2
        if tm * hd < skip:
            continue
        x, z = ax + dx * tm, az + dz * tm
        top = g(math.floor(x), math.floor(z)) + 1
        if min(ay + (by - ay) * t0, ay + (by - ay) * t1) <= top:
            return False
    return True


def parse_nbt_floats(blob, key):
    m = re.search(r"%s:\[([^\]]*)\]" % key, blob)
    return [float(v.rstrip("f")) for v in m.group(1).split(",")] if m else None


def audit(pack, inputs_root, source_root):
    rep = Report()
    doc = load_json(ROOT / "data" / "frostpeak_camp.json")
    g = G.Ground(source_root)
    build_lines = (pack / FN / "build.mcfunction").read_text(encoding="utf-8").splitlines()
    inst_lines = (pack / FN / "instruments.mcfunction").read_text(encoding="utf-8").splitlines()

    blocks, order, cleared = {}, {}, {}
    for n, line in enumerate(build_lines):
        m = SETBLOCK.match(line)
        if m:
            x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
            blocks[(x, y, z)] = m.group(4) + (m.group(5) or "")
            order.setdefault((x, z), n)
            continue
        m = CLEAR.match(line)
        if m:
            x0, y0, z0, x1, y1, z1 = map(int, m.groups())
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    cleared.setdefault((x, z), []).append((min(y0, y1), max(y0, y1), n))
    rep.check(len(blocks) > 100, "C0 pack", "only %d setblocks in build.mcfunction" % len(blocks))
    solid = {p: s for p, s in blocks.items() if name_of(s) not in NON_SOLID}
    cols = {}
    for (x, y, z), s in blocks.items():
        cols.setdefault((x, z), []).append((y, s))

    # C1
    sx0, sz0 = doc["site"]["corner"]
    n = doc["site"]["size"]
    out = [c for c in cols if not (sx0 <= c[0] < sx0 + n and sz0 <= c[1] < sz0 + n)]
    rep.check(not out, "C1 site", "%d columns outside the site square, first %s" % (len(out), out[:3]))

    # C2
    bad = []
    for c, ys in cols.items():
        gy = g(*c)
        real = [(y, s) for y, s in ys if name_of(s) != "minecraft:air"]
        if not real:
            continue
        if all(name_of(s) == "minecraft:spruce_wall_sign" for _y, s in real):
            continue
        low = min(y for y, _s in real)
        if low != gy + 1:
            bad.append("%s lowest block y%d over ground y%d" % (c, low, gy))
        if any(y <= gy for y, _s in real):
            bad.append("%s writes at or below its ground y%d" % (c, gy))
        # no hole in a column's solid stack from the ground to its floor
        sy = sorted(y for y, s in real if name_of(s) not in NON_SOLID)
        if sy and sy[0] == gy + 1:
            run = sy[0]
            for y in sy[1:]:
                if y == run + 1:
                    run = y
            floor_gap = [y for y in range(gy + 1, run + 1) if (c[0], y, c[1]) not in solid]
            if floor_gap:
                bad.append("%s has a gap at %s" % (c, floor_gap))
    rep.check(not bad, "C2 seat", "; ".join(bad[:5]) + (" (+%d more)" % (len(bad) - 5) if len(bad) > 5 else ""))
    # max(ground) + 1: in every cluster of columns (within 3 of each other) at least one stands straight on the
    # ground with no foundation course; a piece seated a block high has a foundation under every column
    fnd = doc["blocks"]["foundation"]
    course = {}
    for c in cols:
        gy, k = g(*c), 0
        while name_of(blocks.get((c[0], gy + 1 + k, c[1]), "")) == fnd:
            k += 1
        if any(name_of(s) not in ("minecraft:air", "minecraft:spruce_wall_sign") for _y, s in cols[c]):
            course[c] = k
    seen, raised = set(), []
    for c0 in sorted(course):
        if c0 in seen:
            continue
        stack, comp = [c0], []
        seen.add(c0)
        while stack:
            c = stack.pop()
            comp.append(c)
            for dx in range(-3, 4):
                for dz in range(-3, 4):
                    nb = (c[0] + dx, c[1] + dz)
                    if nb in course and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        if min(course[c] for c in comp) != 0:
            raised.append((min(comp), min(course[c] for c in comp)))
    rep.check(not raised, "C2 max+1", "clusters seated above max(ground) + 1 (first column, lowest foundation): %s" % raised[:4])

    # C3
    bad = []
    for (x, y, z), s in blocks.items():
        nm, pr = name_of(s), props(s)
        if nm == "minecraft:spruce_wall_sign":
            dx, dz = DIR[pr["facing"]]
            need = (x - dx, y, z - dz)
        elif nm == "minecraft:lantern" and pr.get("hanging") == "true":
            need = (x, y + 1, z)
        elif nm in ("minecraft:lantern", "minecraft:red_carpet", "minecraft:campfire"):
            need = (x, y - 1, z)
            if y - 1 == g(x, z):
                continue
        else:
            continue
        if need not in solid:
            bad.append("%s at %s has nothing at %s" % (nm, (x, y, z), need))
    rep.check(not bad, "C3 support", "; ".join(bad[:5]))

    # C4
    allowed = set(doc["blocks"]["ids"]) | {"minecraft:air"}
    names = {name_of(s) for s in blocks.values()}
    sb = load_json(ROOT / "data" / "spawn_blocks.json")["blocks"]
    spawn = set(sb) if isinstance(sb, (dict, list)) else set()
    if isinstance(sb, list):
        spawn = {e if isinstance(e, str) else e.get("id") for e in sb}
    rep.check(names <= allowed, "C4 palette", "blocks outside blocks.ids: %s" % sorted(names - allowed))
    rep.check(not (names & spawn), "C4 spawn blocks", "spawn-condition blocks placed: %s" % sorted(names & spawn))
    rep.check(not any(nm.endswith("_bed") or nm == "minecraft:respawn_anchor" for nm in names), "C4 respawn",
              "a bed or respawn anchor is placed")

    # C5
    bad = []
    for c, ys in cols.items():
        lo = min(y for y, _s in ys)
        hi = max(y for y, _s in ys)
        gy = g(*c)
        want_lo = min(lo - 1, gy) if lo == gy + 1 else lo - 1
        ok = any(a <= want_lo and b >= hi + 1 and n < order[c] for a, b, n in cleared.get(c, []))
        if not ok:
            bad.append(c)
    rep.check(not bad, "C5 clearing", "%d columns not cleared from the ground before their first setblock, first %s"
              % (len(bad), bad[:3]))

    # C6
    steps = (pack / "steps.txt").read_text(encoding="utf-8").splitlines()
    spawns = [l.split() for l in steps if l.startswith("spawnnpcat ")]
    want = {"cobblers:npc_%s" % r["id"] for r in doc["researchers"]}
    got = [s[4] for s in spawns]
    rep.check(sorted(got) == sorted(want), "C6 NPC set", "spawn lines %s, researchers %s" % (sorted(got), sorted(want)))
    spots = []
    for _c, xs, ys, zs, cls in spawns:
        x, y, z = int(xs), int(ys), int(zs)
        spots.append((x, y, z))
        npc_id = cls.split(":", 1)[1]
        f = pack / "data" / "cobblers" / "npcs" / ("%s.json" % npc_id)
        if not f.is_file():
            rep.check(False, "C6 class", "%s has no class file" % cls)
            continue
        cl = load_json(f)
        dlg = cl.get("interaction", {}).get("dialogue", "")
        rep.check((pack / "data" / "cobblers" / "dialogues" / ("%s.json" % dlg.split(":", 1)[-1])).is_file(),
                  "C6 dialogue", "%s opens %s, which the pack does not have" % (cls, dlg))
        rep.check((x, y - 1, z) in solid, "C6 stand", "%s at %s does not stand on a written solid block" % (cls, (x, y, z)))
        for dy in (0, 1):
            s = blocks.get((x, y + dy, z))
            ok = (s is None and y + dy > g(x, z)) or (s is not None and name_of(s) == "minecraft:air")
            rep.check(ok, "C6 headroom", "%s: (%d, %d, %d) is not air (%s)" % (cls, x, y + dy, z, s))
    for i, a in enumerate(spots):
        for b in spots[i + 1:]:
            rep.check(math.dist(a, b) >= 3, "C6 spacing", "NPCs at %s and %s are %.1f apart" % (a, b, math.dist(a, b)))

    # C7
    shrine = next(s for s in load_json(ROOT / "data" / "adopted_legendary_sites.json")["sites"]
                  if s["id"] == "adopted_articuno_shrine")
    tcx, tcz = shrine["placement"]["centre"]
    tseat = shrine["placement"]["y"]
    # the top occupied layer from the template's own height, not from the record's top_y (which is checked against it)
    tpl = next(s for s in load_json(ROOT / "data" / "structures.json")["structures"] if s["id"] == shrine["template"])
    ttop = tseat + int(re.match(r"^(\d+)x(\d+)x(\d+)", tpl["footprint"]).group(2)) - 1
    rep.check(shrine["placement"]["top_y"] == ttop, "C7 tower top",
              "the record's top_y is %s; y%d + the template's height - 1 is y%d" % (shrine["placement"]["top_y"], tseat, ttop))
    summit = next(t for t in load_json(ROOT / "data" / "towns.json")["towns"] if t["id"] == "frostpeak_shrine")["centre"]
    disp_ok = set(doc["blocks"].get("display_blocks") or [])
    tubes = {}
    for line in inst_lines:
        m = SUMMON.match(line)
        if not m:
            continue
        blob = m.group(4)
        tag = re.search(r'Tags:\["[^"]+","([^"]+)"\]', blob).group(1)
        tubes[tag] = {"pos": tuple(float(v) for v in m.groups()[:3]),
                      "q": parse_nbt_floats(blob, "left_rotation"), "t": parse_nbt_floats(blob, "translation"),
                      "s": parse_nbt_floats(blob, "scale"), "r": parse_nbt_floats(blob, "right_rotation"),
                      "block": re.search(r'Name:"([^"]+)"', blob).group(1)}
    inst = {p["id"]: p for p in doc["pieces"] if p["kind"] == "instrument"}
    rep.check(set(tubes) == set(inst), "C7 tubes", "summoned %s, instruments %s" % (sorted(tubes), sorted(inst)))
    rep.check(any(l.startswith("kill @e[type=minecraft:block_display,tag=") and "distance=.." in l for l in inst_lines),
              "C7 re-run", "the instruments function does not remove its own previous displays")
    measured = {}
    for tid, tb in tubes.items():
        q = tb["q"]
        rep.check(abs(math.sqrt(sum(v * v for v in q)) - 1) < 1e-3, "C7 unit", "%s left_rotation is not a unit quaternion" % tid)
        rep.check(tb["r"] == [0.0, 0.0, 0.0, 1.0], "C7 right", "%s right_rotation is not the identity" % tid)
        rep.check(tb["block"] in disp_ok, "C7 block", "%s shows %s, not a declared display block" % (tid, tb["block"]))
        axis = qrot(q, [0, 0, 1])
        w, _w2, ln = tb["s"]
        back_centre = np.array(tb["t"]) + qrot(q, [w / 2, w / 2, 0])
        # distance from the pivot (the entity origin, local 0) to the axis line, and where along it the pivot falls
        k = -float(np.dot(back_centre, axis))
        off = float(np.linalg.norm(back_centre + k * axis))
        rep.check(off < 0.01 and 0 <= k <= ln, "C7 pivot", "%s: the axis misses its pivot by %.3f (at %.2f of %.2f)" % (tid, off, k, ln))
        px, py, pz = tb["pos"]
        pier = blocks.get((math.floor(px), math.floor(py) - 1, math.floor(pz)))
        rep.check(pier is not None and name_of(pier) in ("minecraft:cobblestone_wall", "minecraft:spruce_fence"),
                  "C7 pier", "%s has no wall or fence pier under it (%s)" % (tid, pier))
        ends = [np.array([px, py, pz]) + back_centre, np.array([px, py, pz]) + back_centre + ln * axis]
        lowest = min(e[1] for e in ends) - (w / 2) * math.cos(math.asin(min(1.0, abs(axis[1]))))
        rep.check(lowest >= math.floor(py) - 1 + 1 - 0.05, "C7 rests", "%s dips to y%.2f, into its pier top y%d"
                  % (tid, lowest, math.floor(py)))
        brg = compass(axis[0], axis[2])
        elev = math.degrees(math.asin(axis[1]))
        target = inst[tid]["target"]
        if target == "shrine":
            want_b = compass(tcx + 0.5 - px, tcz + 0.5 - pz)
            rep.check(angdiff(brg, want_b) <= 0.5, "C7 telescope bearing", "%.2f against %.2f to the tower" % (brg, want_b))
            hd = math.hypot(tcx + 0.5 - px, tcz + 0.5 - pz)
            hy = py + math.tan(math.radians(elev)) * hd
            lo = next((y for y in range(tseat, ttop + 1) if ray_clear(g, (px, py, pz), (tcx + 0.5, y + 0.5, tcz + 0.5))), None)
            rep.check(lo is not None, "C7 tower visible", "no layer of the tower is visible from the telescope")
            rep.check(lo is not None and lo <= hy <= ttop + 1, "C7 telescope height",
                      "the tube meets the tower column at y%.1f; visible layers y%s..%d" % (hy, lo, ttop))
            rep.check(ray_clear(g, (px, py, pz), (tcx + 0.5, hy, tcz + 0.5)), "C7 telescope line",
                      "the line along the tube runs into the terrain before the tower")
            measured["shrine_bearing"], measured["shrine_range"] = want_b, hd
            measured["climb"] = g(tcx, tcz) - g(math.floor(px), math.floor(pz))
            if lo is not None:
                measured["crown_showing"] = ttop - lo + 1
        else:
            sx, sz = summit["x"] + 0.5, summit["z"] + 0.5
            want_b = compass(sx - px, sz - pz)
            rep.check(angdiff(brg, want_b) <= 0.5, "C7 theodolite bearing", "%.2f against %.2f to the summit" % (brg, want_b))
            hd = math.hypot(sx - px, sz - pz)
            crest, crest_d, i = -90.0, None, 4
            while i < hd:
                x, z = px + (sx - px) * i / hd, pz + (sz - pz) * i / hd
                a = math.degrees(math.atan2(g(math.floor(x), math.floor(z)) + 1 - py, i))
                if a > crest:
                    crest, crest_d = a, i
                i += 0.5
            rep.check(-0.05 <= elev - crest <= 0.5, "C7 theodolite elevation",
                      "%.2f against the crest's %.2f on that bearing" % (elev, crest))
            visible = ray_clear(g, (px, py, pz), (sx, summit["ground_y"] + 1.5, sz))
            rep.check(not visible, "C7 false crest", "the summit platform IS visible from the theodolite: the camp's lines are wrong")
            measured["summit_bearing"], measured["summit_beyond"] = want_b, hd - crest_d
            measured["crest_elevation"] = crest

    # C8
    texts = []
    sign_texts = []
    for (x, y, z), s in blocks.items():
        if name_of(s) == "minecraft:spruce_wall_sign":
            msgs = re.findall(r"'((?:[^'\\]|\\.)*)'", s)
            sign_texts.append(" ".join(json.loads(t.replace("\\'", "'")) for t in msgs))
    pages = {}
    for f in sorted((pack / "data" / "cobblers" / "dialogues").glob("*.json")):
        d = load_json(f)
        for pg in d["pages"]:
            pages[(f.stem, pg["id"])] = " ".join(pg["lines"])
            if isinstance(pg.get("input"), dict):
                for o in pg["input"].get("options", []):
                    pages[(f.stem, pg["id"], o["value"])] = o["text"]
    texts = sign_texts + list(pages.values())
    blob = "\n".join(texts)
    if "shrine_bearing" in measured and "summit_bearing" in measured:
        bearings = [int(b) for b in re.findall(r"bearing (\d{3})", blob)]
        rep.check(bearings and all(min(angdiff(b, measured["shrine_bearing"]), angdiff(b, measured["summit_bearing"])) <= 1
                                   for b in bearings), "C8 bearings",
                  "stated %s; measured shrine %.1f, summit %.1f" % (sorted(set(bearings)), measured["shrine_bearing"], measured["summit_bearing"]))
        board = " ".join(sign_texts)
        for key in ("shrine_bearing", "summit_bearing"):
            rep.check(any(angdiff(int(b), measured[key]) <= 1 for b in re.findall(r"bearing (\d{3})", board)),
                      "C8 board", "the notes board does not state the %s" % key)
        checks = [(r"~(\d+) blocks", measured["shrine_range"], 10), (r"about (\d+) blocks off", measured["shrine_range"], 10),
                  (r"crown y(\d+)", ttop, 0), (r"another (\d+) blocks behind", measured["summit_beyond"], 10),
                  (r"rises about (\d+) blocks", measured["climb"], 5),
                  (r"the top (\d+) blocks of it", measured.get("crown_showing", -1), 0)]
        for pat, val, tol in checks:
            found = [int(v) for v in re.findall(pat, blob)]
            rep.check(found and all(abs(v - val) <= tol for v in found), "C8 %s" % pat,
                      "stated %s, measured %.1f (tolerance %d)" % (found, val, tol))

    # C9
    fields = {f_["id"]: f_ for f_ in load_json(ROOT / "data" / "progression.json")["quest_fields"]}
    for f in sorted((pack / "data" / "cobblers" / "dialogues").glob("*.json")):
        raw = f.read_text(encoding="utf-8")
        rep.check("run_command" not in raw, "C9 commands", "%s runs a command" % f.stem)
        own = "cobblers__quest__frostpeak_camp__%s_cursor" % f.stem.rsplit("_", 1)[-1]
        writes = set(re.findall(r"t\.d\.(\w+) = ", raw))
        rep.check(writes <= {own}, "C9 state", "%s writes %s, not only its cursor %s" % (f.stem, sorted(writes - {own}), own))
        fid = "quest.frostpeak_camp.%s_cursor" % f.stem.rsplit("_", 1)[-1]
        fd = fields.get(fid) or {}
        rep.check(fd.get("scope") == "player" and fd.get("type") == "enum", "C9 field",
                  "%s is not declared in data/progression.json as a player enum" % fid)
        rep.check("isVisible" not in raw, "C9 options", "%s hides an option from some players" % f.stem)
    promised = [t for t in texts if PROMISES.search(t)]
    rep.check(not promised, "C9 no promise", "texts that promise the altar works: %s" % promised[:2])

    # C10
    if inputs_root is None:
        rep.check(False, "C10 inputs", "no --inputs-root: the other packs, the painted water and the water export "
                                       "cannot be checked (a worktree has no build/ or derived/); refusing")
    else:
        ir = Path(inputs_root)
        xs = [c[0] for c in cols]
        zs = [c[1] for c in cols]
        m = 8
        box = (min(xs) - m, min(zs) - m, max(xs) + m, max(zs) + m)
        base = ir / "build" / "datapacks"
        hits = []
        if not base.is_dir():
            rep.check(False, "C10 packs", "no %s" % base)
        else:
            for p in sorted(q for q in base.iterdir() if q.is_dir() and q.name != pack.name):
                for f in p.rglob("*.mcfunction"):
                    for mm in OTHER_WRITE.finditer(f.read_text(encoding="utf-8", errors="replace")):
                        gr = mm.groups()
                        x, z = math.floor(float(gr[1])), math.floor(float(gr[3]))
                        xb, zb = (int(gr[4]), int(gr[6])) if gr[4] is not None else (x, z)
                        if max(x, xb) >= box[0] and min(x, xb) <= box[2] and max(z, zb) >= box[1] and min(z, zb) <= box[3]:
                            hits.append("%s/%s" % (p.name, f.name))
            rep.check(not hits, "C10 packs", "other packs write within %d: %s" % (m, sorted(set(hits))[:5]))
        world = load_json(ROOT / "data" / "world.json")
        sea = float((world.get("vertical") or {}).get("sea_level", 62))
        rep.check(all(g(*c) > sea for c in cols), "C10 sea", "a camp column is at or under the sea level")
        man_p = ir / "build" / "paint" / "manifest.json"
        if not man_p.is_file():
            rep.check(False, "C10 painted water", "no %s" % man_p)
        else:
            from PIL import Image
            man = load_json(man_p)
            wet = []
            for wl in man.get("water") or []:
                key = "levels" if "levels" in wl else "mask"
                img = np.asarray(Image.open(ir / "build" / "paint" / wl[key])) > 0
                for c in cols:
                    ix, iz = c[0] - g.ox - wl["x"], c[1] - g.oz - wl["z"]
                    if 0 <= iz < img.shape[0] and 0 <= ix < img.shape[1] and img[iz, ix]:
                        wet.append(c)
            rep.check(not wet, "C10 painted water", "painted water under %s" % wet[:3])
        ch = ir / "derived" / "water_shape" / "changed.npy"
        if not ch.is_file():
            rep.check(False, "C10 water export", "no %s" % ch)
        else:
            arr = np.load(ch, mmap_mode="r")
            sub = arr[box[1] - g.oz:box[3] - g.oz + 1, box[0] - g.ox:box[2] - g.ox + 1]
            rep.check(not bool(np.asarray(sub).any()), "C10 water export", "the water export changes a column within %d" % m)

    # C11
    for nm, lines in (("build", build_lines), ("instruments", inst_lines)):
        bad = function_limits.check_lines(lines, nm)
        rep.check(not bad, "C11 %s" % nm, "%s" % bad[:2])
    return rep, measured


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--inputs-root", help="a full checkout holding build/datapacks, build/paint and derived/water_shape")
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    rep, measured = audit(Path(a.pack), a.inputs_root, a.source_root)
    for p in rep.problems:
        print("PROBLEM", p)
    print("measured: " + ", ".join("%s %.2f" % kv for kv in sorted(measured.items())))
    print("%d checks passed, %d problems" % (len(rep.passed), len(rep.problems)))
    return 1 if rep.problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
