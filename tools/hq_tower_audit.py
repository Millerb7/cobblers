#!/usr/bin/env python
"""Independent audit of the Compact HQ tower as its packs build it (tools/hq_tower.py, R9HQ; its trainers R17, its
NPCs R18HQ).

Written by test-author, 2026-10-04, who did not build the tower (commits 7e0524e, da3ceba, 62b953c).

WHAT IT READS, never the builder's in-memory model:
  build/datapacks/cobblers_deep_city          the city's block functions, REPLAYED in index order (R9DC): the tower's
                                              walls, its floor every 6, the ring-0 section round it
  build/datapacks/cobblers_relic_underground  R9RU's, when built (it runs between); otherwise said in the report
  build/datapacks/cobblers_hq_tower           the tower's block functions, REPLAYED after them; its gate cycle's
                                              set-back targets and boxes
  build/datapacks/cobblers_trainers           the seven HQ trainers' hold points (the cycle's tp lines)
  tools/hq_tower.py npc_placements()          where R18HQ spawns the NPCs (the list it is handed), at x.5 / z.5
  tools/rift_deep.py model()                  the Deep's ring-0 tread under the tower (R9B, which nothing above
                                              writes): a cell nobody writes is rock at or below its tread, air above
  data/hq_tower.json                          the DECLARED tower: interior, base, top, door cells, storeys, caches
  data/hq_trainers.json                       which trainers are the tower's
  data/spawn_blocks.json                      the blocks a loaded spawn condition names

WHAT IT CHECKS.
  H1  every write of the tower pack is a fill/setblock inside the declared interior (base..top) or a door cell
  H2  no block the tower pack writes is a spawn-condition block
  H3  the walk from outside the doorway (4-neighbour, one up with head room, up to three down, every block solid but
      air, light and the few non-colliding blocks NONSOLID lists) reaches every storey's floor, the top storey
      (anchor control) included
  H4  every trainer hold point and every NPC in the tower stands on a floor with two clear above, inside the
      interior, with a reached cell beside it
  H5  every cache: a barrel at its `at`, and a reached cell whose player hitbox meets its trigger box
  H6  walk-out: from every cell the walk reaches inside the tower, the doorway's outside cell is reached back
  H7  the gate cycle's set-backs: each tp target is a standable cell the walk reaches and lies outside the box of
      the selector that sends a player there (so the gate never traps)

WHAT IT DOES NOT COVER. Nothing ran in Minecraft: stairs climbed as a one-block step, slabs and furniture as full
blocks, ladders and doors not modelled (none is written in the tower), entities not modelled (a trainer stands where
it is held; that it is held there is R17's). The relic pack's writes only when it is built.

  python tools/hq_tower_audit.py [--packs build/datapacks] [--source-root DIR] [--json OUT]
Exit 0 clean, 1 problems.
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
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
PACKS = ROOT / "build" / "datapacks"

# the block may carry NBT with spaces (a sign's text), so it is everything up to an optional trailing mode
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (.+?)(?: (replace|keep|destroy|hollow|"
                  r"outline)(?: (\S+))?)?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (.+?)(?: (replace|keep|destroy))?$")
PLACE = re.compile(r"^place template \S+ (-?\d+) (-?\d+) (-?\d+)")
AIR = "minecraft:air"
ROCK = "deep:rock"
# blocks with no collision box a player walks through; everything else is solid (the conservative side)
NONSOLID = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:light"}
NONSOLID_SUFFIX = ("_torch", "torch", "_sign", "_button", "_pressure_plate", "_carpet", "rail", "short_grass",
                   "tall_grass", "fern", "redstone_wire", "tripwire", "lever")


class Unmodelled(Exception):
    pass


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def norm(b):
    b = b.split("[")[0].split("{")[0]
    return b if ":" in b else "minecraft:" + b


def nonsolid(b):
    n = norm(b)
    return n in NONSOLID or n.endswith(NONSOLID_SUFFIX)


def lines_of(pack, folder):
    """[(function name, [lines])] for a pack's indexed block functions, in its index order; [] when not built."""
    fdir = Path(pack) / "data" / "cobblers" / "function" / folder
    idx = fdir / "index.txt"
    if not idx.is_file():
        return None
    out = []
    for name in [l.strip() for l in idx.read_text(encoding="utf-8").splitlines() if l.strip()]:
        out.append((name, (fdir / (name + ".mcfunction")).read_text(encoding="utf-8").splitlines()))
    return out


def ops(lines, name=""):
    """Each block-writing line as (x0, y0, z0, x1, y1, z1, block, mode, filter); forceloads and comments skipped. A
    `place template` is returned as ("place", x, y, z)."""
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("forceload "):
            continue
        m = FILL.match(s)
        if m:
            x0, y0, z0, x1, y1, z1 = (int(v) for v in m.group(1, 2, 3, 4, 5, 6))
            yield (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1), m.group(7),
                   m.group(8), m.group(9))
            continue
        m = SETBLOCK.match(s)
        if m:
            x, y, z = (int(v) for v in m.group(1, 2, 3))
            yield (x, y, z, x, y, z, m.group(4), m.group(5), None)
            continue
        m = PLACE.match(s)
        if m:
            yield ("place",) + tuple(int(v) for v in m.group(1, 2, 3))
            continue
        raise Unmodelled("%s: %s" % (name, s))


def replay_into(cells, funcs, box, tags=None, place_margin=64):
    """Apply funcs ([(name, lines)]) to cells {(x, y, z): block} inside box (x0, y0, z0, x1, y1, z1)."""
    X0, Y0, Z0, X1, Y1, Z1 = box
    for name, lines in funcs:
        for op in ops(lines, name):
            if op[0] == "place":
                _p, x, y, z = op
                if X0 - place_margin <= x <= X1 + place_margin and Z0 - place_margin <= z <= Z1 + place_margin:
                    raise Unmodelled("%s: a template placed at %s, near the tower: its blocks are not modelled"
                                     % (name, (x, y, z)))
                continue
            x0, y0, z0, x1, y1, z1, b, mode, filt = op
            if mode in ("hollow", "outline", "destroy"):
                raise Unmodelled("%s: fill mode %s" % (name, mode))
            xa, xb, ya, yb, za, zb = max(x0, X0), min(x1, X1), max(y0, Y0), min(y1, Y1), max(z0, Z0), min(z1, Z1)
            if xa > xb or ya > yb or za > zb:
                continue
            for x in range(xa, xb + 1):
                for y in range(ya, yb + 1):
                    for z in range(za, zb + 1):
                        cur = cells.get((x, y, z))
                        if mode == "keep" and cur is None:
                            raise Unmodelled("%s: keep over a cell no pack wrote at %s" % (name, (x, y, z)))
                        if mode == "keep" and not nonsolid(cur):
                            continue
                        if mode == "replace" and filt:
                            if filt.startswith("#"):
                                raise Unmodelled("%s: replace by tag %s inside the tower's box" % (name, filt))
                            if cur is None or norm(cur) != norm(filt):
                                continue
                        cells[(x, y, z)] = b
    return cells


class Model:
    """block_at over the replayed packs, the Deep's tread below anything unwritten."""

    def __init__(self, cells, tread):
        self.cells, self.tread = cells, tread

    def at(self, p):
        b = self.cells.get(p)
        if b is not None:
            return b
        t = self.tread(p[0], p[2])
        return ROCK if t is None or p[1] <= t else AIR

    def clear(self, p):
        return nonsolid(self.at(p))

    def stand(self, p):
        x, y, z = p
        return self.clear(p) and self.clear((x, y + 1, z)) and not self.clear((x, y - 1, z))


def tread_of(source_root):
    """(x, z) -> the Deep's tread y (rift_deep.model), or None outside the pit."""
    import rift_deep
    m = rift_deep.model(source_root)
    X0, Z0, X1, Z1 = m["box"]
    ty, ring = m["tread_y"], m["ring"]

    def f(x, z):
        if not (X0 <= x <= X1 and Z0 <= z <= Z1) or ring[z - Z0, x - X0] < 0:
            return None
        return int(ty[z - Z0, x - X0])
    return f


def walk(model, start, box):
    """Every standable cell reached from start, and the move graph (cell -> successors)."""
    X0, Y0, Z0, X1, Y1, Z1 = box
    seen, q, graph = {start}, deque([start]), {}
    while q:
        c = q.popleft()
        x, y, z = c
        nxt = []
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (X0 <= nx <= X1 and Z0 <= nz <= Z1):
                continue
            for dy in (1, 0, -1, -2, -3):
                n = (nx, y + dy, nz)
                if not (Y0 < n[1] < Y1) or not model.stand(n):
                    continue
                if dy == 1 and not model.clear((x, y + 2, z)):
                    continue                              # no head room to step up
                if dy < 0 and not all(model.clear((nx, y + k, nz)) for k in range(dy + 1, 2)):
                    continue                              # the drop's column must be open
                nxt.append(n)
                break
        graph[c] = nxt
        for n in nxt:
            if n not in seen:
                seen.add(n)
                q.append(n)
    return seen, graph


def back_reach(graph, target):
    rev = {}
    for c, ns in graph.items():
        for n in ns:
            rev.setdefault(n, []).append(c)
    seen, q = {target}, deque([target])
    while q:
        c = q.popleft()
        for p in rev.get(c, ()):
            if p not in seen:
                seen.add(p)
                q.append(p)
    return seen


def hold_points(packs, ids):
    """{trainer id: (x, y, z)} from the emitted trainer cycle's hold (tp) lines."""
    f = Path(packs) / "cobblers_trainers" / "data" / "cobblers" / "function" / "trainers" / "cycle.mcfunction"
    out = {}
    if not f.is_file():
        return out
    for line in f.read_text(encoding="utf-8").splitlines():
        for tid in ids:
            if 'TrainerId:"%s"' % tid in line and " run tp @s " in line:
                out[tid] = tuple(float(v) for v in line.rsplit(" run tp @s ", 1)[1].split()[:3])
    return out


def npc_spots():
    import hq_tower
    return {cls.split(":", 1)[1]: (x + 0.5, float(y), z + 0.5) for _c, (x, y, z), cls, _yaw in hq_tower.npc_placements()}


def cell(pos):
    return (math.floor(pos[0]), int(round(pos[1])), math.floor(pos[2]))


SEL = re.compile(r"^tp (@a\[[^\]]*\]) (\S+) (\S+) (\S+)")


def set_backs(packs):
    """[(selector, target)] from the emitted gate cycle's tp lines."""
    f = Path(packs) / "cobblers_hq_tower" / "data" / "cobblers" / "function" / "hq_tower" / "cycle.mcfunction"
    out = []
    if not f.is_file():
        return out
    for line in f.read_text(encoding="utf-8").splitlines():
        m = SEL.match(line.strip())
        if m:
            out.append((m.group(1), tuple(float(v) for v in m.group(2, 3, 4))))
    return out


def audit(packs=PACKS, source_root=None, data=DATA, tread=None):
    packs = Path(packs)
    spec = jload(Path(data) / "hq_tower.json")
    t = spec["tower"]
    ix0, iz0, ix1, iz1 = t["interior"]
    bx0, bz0, bx1, bz1 = t["box"]
    door = {tuple(c) for c in spec["door"]["cells"]}
    probs, notes = [], []
    hq = lines_of(packs / "cobblers_hq_tower", "hq_tower")
    city = lines_of(packs / "cobblers_deep_city", "deep_city")
    if hq is None:
        return ["the tower pack is not built at %s" % (packs / "cobblers_hq_tower")], notes
    if city is None:
        return ["the city pack is not built at %s: the tower's walls and floors are not known"
                % (packs / "cobblers_deep_city")], notes
    relic = lines_of(packs / "cobblers_relic_underground", "relic_underground")
    if relic is None:
        notes.append("R9RU's writes NOT modelled (cobblers_relic_underground not built)")

    # H1, H2: what the tower pack writes
    inside = lambda p: ix0 <= p[0] <= ix1 and iz0 <= p[2] <= iz1 and t["base"] <= p[1] <= t["top"]
    spawn = set()
    sb = jload(Path(data) / "spawn_blocks.json")["blocks"]
    for e in sb:
        spawn.add(e if isinstance(e, str) else e.get("id"))
    out_of, written = [], {}
    try:
        for name, lines in hq:
            for op in ops(lines, name):
                if op[0] == "place":
                    probs.append("H1 %s places a template at %s" % (name, op[1:]))
                    continue
                written[norm(op[6])] = written.get(norm(op[6]), 0) + 1
                if any(not inside(p) and p not in door for p in box_cells(op)):
                    out_of.append((name, op[:7]))
    except Unmodelled as e:
        return ["H1 the tower pack has a line the audit cannot read: %s" % e], notes
    if out_of:
        probs.append("H1 %d writes outside the interior and the door cells, e.g. %s" % (len(out_of), out_of[:3]))
    bad_spawn = sorted(set(written) & spawn)
    if bad_spawn:
        probs.append("H2 the tower writes spawn-condition blocks %s (data/spawn_blocks.json)" % bad_spawn)

    # the model
    box = (bx0 - 6, t["base"] - 3, bz0 - 6, bx1 + 6, t["top"] + 4, bz1 + 6)
    cells = {}
    try:
        replay_into(cells, city, box)
        if relic is not None:
            replay_into(cells, relic, box)
        replay_into(cells, hq, box)
    except Unmodelled as e:
        return probs + ["the replay cannot model a line: %s" % e], notes
    if tread is None:
        if source_root is None:
            from terrain import env_source_root
            source_root = env_source_root()
        tread = tread_of(source_root)
    m = Model(cells, tread)
    dx = max(c[0] for c in door)
    dz = min(c[2] for c in door)
    dy = min(c[1] for c in door)
    start = (dx + 1, dy, dz)
    if not m.stand(start):
        return probs + ["H3 the cell outside the doorway %s is not standable: under %s, feet %s, head %s"
                        % (start, m.at((start[0], start[1] - 1, start[2])), m.at(start),
                           m.at((start[0], start[1] + 1, start[2])))], notes
    reach, graph = walk(m, start, box)
    in_tower = {c for c in reach if ix0 <= c[0] <= ix1 and iz0 <= c[2] <= iz1}

    # H3: every storey's floor
    for s in spec["storeys"]:
        if not any(c[1] == s["floor"] + 1 for c in in_tower):
            probs.append("H3 the walk from the doorway never stands on storey %s (y%d)" % (s["id"], s["floor"] + 1))

    # H4: seats
    ids = [r["id"] for r in jload(Path(data) / "hq_trainers.json")["trainers"]]
    holds = hold_points(packs, ids)
    spots = npc_spots()
    seats = [("trainer", i, holds.get(i)) for i in ids]
    seats += [("npc", n["id"], spots.get(n["id"])) for n in spec["npcs"] if n.get("storey")]
    for kind, sid, pos in seats:
        if pos is None:
            probs.append("H4 %s %s: no hold point / placement emitted" % (kind, sid))
            continue
        c = cell(pos)
        if not (ix0 <= c[0] <= ix1 and iz0 <= c[2] <= iz1):
            probs.append("H4 %s %s at %s is outside the tower's interior" % (kind, sid, c))
        if not m.stand(c):
            probs.append("H4 %s %s at %s: under %s, feet %s, head %s -- not a floor with two clear"
                         % (kind, sid, c, m.at((c[0], c[1] - 1, c[2])), m.at(c), m.at((c[0], c[1] + 1, c[2]))))
        near = [(c[0] + a, c[1] + b, c[2] + d) for a, d in ((1, 0), (-1, 0), (0, 1), (0, -1)) for b in (-1, 0, 1)]
        if c not in reach and not any(n in reach for n in near):
            probs.append("H4 %s %s at %s: the walk reaches no cell beside it" % (kind, sid, c))

    # H5: caches
    for ca in spec.get("hq_caches") or []:
        b = cells.get(tuple(ca["at"]))
        if not b or norm(b) != "minecraft:barrel":
            probs.append("H5 cache %s: %s at %s, not a barrel" % (ca["id"], b, ca["at"]))
        (tx0, ty0, tz0), (tx1, ty1, tz1) = ca["trigger"]["min"], ca["trigger"]["max"]
        hit = [c for c in reach if c[0] + 0.8 > tx0 and c[0] + 0.2 < tx1 + 1 and c[1] + 1.8 > ty0 and c[1] < ty1 + 1
               and c[2] + 0.8 > tz0 and c[2] + 0.2 < tz1 + 1]
        if not hit:
            probs.append("H5 cache %s: the walk reaches no cell whose hitbox meets its trigger %s"
                         % (ca["id"], ca["trigger"]))

    # H6: walk-out
    back = back_reach(graph, start)
    stuck = sorted(c for c in in_tower if c not in back)
    if stuck:
        probs.append("H6 %d cells inside the tower cannot walk back out to %s, e.g. %s" % (len(stuck), start, stuck[:3]))

    # H7: the gate set-backs
    sys.path.insert(0, str(ROOT / "tools"))
    import finale_audit as FA
    sbs = set_backs(packs)
    if len(sbs) < 2:
        probs.append("H7 the gate cycle has %d set-back lines, not one per gate" % len(sbs))
    for sel, target in sbs:
        c = cell(target)
        if not m.stand(c):
            probs.append("H7 the set-back %s is not standable" % (target,))
        if c not in reach:
            probs.append("H7 the set-back %s is not on the walk from the doorway" % (target,))
        pl = FA.Player(pos=target)              # survival, no tags: the player the gate sets back
        try:
            caught = FA.select(pl, sel[2:], target)
        except FA.Unmodelled as e:
            probs.append("H7 cannot read the selector %s: %s" % (sel, e))
            continue
        if caught:
            probs.append("H7 the set-back %s lies inside the box of the selector that sends a player there (%s): "
                         "the gate would hold a player in place" % (target, sel))
    notes.append("tower: %d cells replayed, %d standable cells reached from %s (%d inside), %d seats, %d caches, "
                 "%d set-backs, the tower writes %d blocks kinds"
                 % (len(cells), len(reach), start, len(in_tower), len(seats), len(spec.get("hq_caches") or []),
                    len(sbs), len(written)))
    return probs, notes


def box_cells(op):
    x0, y0, z0, x1, y1, z1 = op[:6]
    return [(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--packs", default=str(PACKS))
    ap.add_argument("--source-root")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    probs, notes = audit(a.packs, a.source_root)
    if a.json:
        Path(a.json).write_text(json.dumps({"problems": probs, "notes": notes}, indent=1), encoding="utf-8")
    for n in notes:
        print("  " + n)
    for p in probs:
        print("PROBLEM " + p)
    print("hq_tower_audit: %d problem(s)" % len(probs))
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())
