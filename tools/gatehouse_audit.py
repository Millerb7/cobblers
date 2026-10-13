#!/usr/bin/env python
"""Audit the Rift's open gatehouses against what a player actually meets (the owner, 2026-10-12).

  python tools/gatehouse_audit.py [--pack <dir>] [--source-root <root>]     # exit 1 on any problem

"It shouldn't be a one-block corridor to squeeze through; it should just be a guard that stops you if you can't
enter." This reads the EMITTED gatehouse functions (build/datapacks/cobblers_rift_zones/.../rift_zones/) and
data/rift_zones.json, and shares no code with tools/rift_zones.py: the movement, the passage's rows and lanes and the
old shell's description are written here, from the owner's words and the record's numbers, so an agreement between
this and the generator is two derivations meeting and not one derivation read twice (CLAUDE.md, "How to prove an
audit is independent"). tests/test_rift_zones.py proves each check bites by mutating the GENERATOR with the data
untouched.

WHAT IT CHECKS, per gate, on the world the function leaves behind -- the retired shell's blocks (gatehouse.legacy, as
the world holds them today) with the function applied over them, over terrain that is solid up to `ground` (the
heightmap, rounded) and air above it:

  width      every row of the passage, from the outer mouth to the inner one, has an unbroken run of at least
             gatehouse.min_width (5) standable columns across it, all at the floor's level
  clear      over every column of the passage and of the approach, the four blocks above the floor are free (no
             overhang under gatehouse.min_clear = 4, no roof, no natural tunnel)
  open       nothing the retired shell built is left: no obsidian, crying obsidian or barrier anywhere in its old
             footprint, and in the passage's lanes nothing solid from the floor to the clear height; the only solid
             blocks it may leave in the footprint's rows above the floor are the two posts
  guard      the guard's placeholder stands beside the way (one column outside the passage's lanes, on the guard's own
             row t = 0), feet and head clear, on a floor at the passage's level, facing the approach, at least
             NPC_CLEAR (3.5) from every seated NPC in data/npc_seats.json and from the other guards
  walk       the guard's pad, the arrival, the whole knock box and the last column of every approach lane at both
             ends are one piece a player can walk (4-connected, one block up or down)
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "build" / "datapacks" / "cobblers_rift_zones" / "data" / "cobblers" / "function" / "rift_zones"
AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
RETIRED = {"minecraft:obsidian", "minecraft:crying_obsidian", "minecraft:barrier"}   # the old shell's own materials
NPC_CLEAR = 3.5       # the placed-NPC spacing the whole repository uses (tools/markets.py NPC_CLEAR; reapply counts 2)


# ------------------------------------------------------------------ reading the emitted text

def voxels(text, into=None):
    """{(x, y, z): block id} -- fills and setblocks applied in order, a later one winning. Block states are dropped."""
    vox = {} if into is None else into
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if " run " in line:
            line = line.split(" run ", 1)[1].strip()
        p = line.split()
        if p[0] == "fill" and len(p) >= 8:
            x0, y0, z0, x1, y1, z1 = (int(v) for v in p[1:7])
            b = re.split(r"[\[{]", p[7])[0]
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        vox[(x, y, z)] = b
        elif p[0] == "setblock" and len(p) >= 5:
            vox[(int(p[1]), int(p[2]), int(p[3]))] = re.split(r"[\[{]", p[4])[0]
    return vox


def guard_stands(text):
    """{gate name: (x, y, z, yaw)} from the guards_act function's summon lines (the gate's name is one of its tags)."""
    out = {}
    for line in text.splitlines():
        if not line.startswith("summon minecraft:armor_stand"):
            continue
        t = line.split()
        x, y, z = int(t[2]), int(t[3]), int(t[4])
        yaw = float(re.search(r"Rotation:\[(-?[\d.]+)f", line).group(1))
        tags = re.search(r"Tags:\[(.*?)\]", line).group(1).replace('"', "").split(",")
        for tg in tags:
            if tg not in ("cobblers_rift_guard", "cobblers_rift_guard_new"):
                out[tg] = (x, y, z, yaw)
    return out


# ------------------------------------------------------------------ the data, as this audit reads it

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gates(spec):
    """[(name, guard id, record, arrive, knock)] -- the zone's guard first, then each staffed post, live zones only."""
    out = []
    for zid, z in spec["zones"].items():
        if str(z.get("status", "")).startswith("SUPERSEDED") or not z.get("guard"):
            continue
        out.append((zid, z["guard"]["id"], z["guard"], z["arrive"], z["knock"]))
        for po in z.get("posts", []):
            out.append(("%s_%s" % (zid, po["id"]), po["guard_id"], po, po["arrive"], po["knock"]))
    return out


def held(spec):
    """Zone ids that cannot grant their pass yet (data zones.<id>.needs_*): R9Z builds their gatehouses' functions
    but summons no guard placeholder for them."""
    return {zid for zid, z in spec["zones"].items()
            if not str(z.get("status", "")).startswith("SUPERSEDED")
            and any(z.get(k) for k in ("needs_progression", "needs_dialogue", "needs_walls"))}


class Frame:
    """One gate's rows and lanes: t along the axis (0 the guard's row, positive inward), k across it (0 the guard's
    own lane, negative on the guard's side). The walkway is `walkway` lanes from -((w-1)//2) to w//2."""

    def __init__(self, rec, gh, legacy=False):
        self.bx, self.bz = rec["block"]
        ox, oz = rec["outward"]
        ax = (1 if ox > 0 else -1, 0) if abs(ox) >= abs(oz) else (0, 1 if oz > 0 else -1)
        self.out = ax
        self.ix, self.iz = -ax[0], -ax[1]
        self.cx, self.cz = abs(ax[1]), abs(ax[0])
        src = gh["legacy"] if legacy else gh
        w = src["walkway"]
        self.k0, self.k1 = -((w - 1) // 2), w // 2
        self.t0, self.t1 = -src["knock_out"], src["walkway_in"]
        self.fy = rec["ground_y"] + 1

    def at(self, t, k):
        return (self.bx + self.ix * t + self.cx * k, self.bz + self.iz * t + self.cz * k)

    def tk(self, x, z):
        dx, dz = x - self.bx, z - self.bz
        return (dx * self.ix + dz * self.iz, dx * self.cx + dz * self.cz)


def retired_shell(fr, rec, gh):
    """The world the 2026-10-03 shell left, as gatehouse.legacy describes it and the commit that built it did: an
    obsidian floor at fy - 1 over the walkway and its two wall columns, obsidian walls fy .. fy + 2 on the wall
    columns, an obsidian roof at fy + 2 over the walkway, a blackstone gate frame at each mouth row (roof row to
    blackstone, a blackstone course at fy + 3 over the row and its two flanking posts, the posts fy .. fy + 3), a
    two-high barrier across the row behind the guard (t = 1), a crying obsidian lamp over the guard, and the
    approach: obsidian floors from fill_from up to feet - 1, air for feet .. feet + 2."""
    lg = gh["legacy"]
    vox = {}
    fy = fr.fy
    ks = range(fr.k0, fr.k1 + 1)
    for t in range(fr.t0, fr.t1 + 1):
        for k in range(fr.k0 - 1, fr.k1 + 2):
            x, z = fr.at(t, k)
            vox[(x, fy - 1, z)] = "minecraft:obsidian"
            if k < fr.k0 or k > fr.k1:
                for y in range(fy, fy + lg["roof_at"] + 1):
                    vox[(x, y, z)] = "minecraft:obsidian"
        for k in ks:
            x, z = fr.at(t, k)
            vox[(x, fy, z)] = "minecraft:air"
            vox[(x, fy + 1, z)] = "minecraft:air"
            vox[(x, fy + lg["roof_at"], z)] = "minecraft:obsidian"
    for t in (fr.t0, fr.t1):
        for k in range(fr.k0 - 1, fr.k1 + 2):
            x, z = fr.at(t, k)
            vox[(x, fy + 3, z)] = "minecraft:blackstone"
            if k in (fr.k0 - 1, fr.k1 + 1):
                for y in range(fy, fy + 4):
                    vox[(x, y, z)] = "minecraft:blackstone"
        for k in ks:
            x, z = fr.at(t, k)
            vox[(x, fy + lg["roof_at"], z)] = "minecraft:blackstone"
    for k in ks:
        x, z = fr.at(1, k)
        for y in range(fy, fy + lg["barrier_height"]):
            vox[(x, y, z)] = "minecraft:barrier"
    vox[(rec["block"][0], fy + 2, rec["block"][1])] = "minecraft:crying_obsidian"
    for run in rec.get("approach", {}).get("outer", []) + rec.get("approach", {}).get("inner", []):
        for (x, z, feet, ff) in run:
            for y in range(feet - 1 if ff is None else ff, feet):
                vox[(x, y, z)] = "minecraft:obsidian"
            for y in range(feet, feet + 3):
                vox[(x, y, z)] = "minecraft:air"
    return vox


# ------------------------------------------------------------------ the audit

def stand_ok(block, x, y, z):
    return block(x, y, z) in AIR and block(x, y + 1, z) in AIR and block(x, y - 1, z) not in AIR


def pieces_link(cells, want):
    """True when every cell of `want` is in `cells` and they are all one 4-connected piece (a step of one up or down)."""
    if any(c not in cells for c in want):
        return False
    start = want[0]
    seen, stack = {start}, [start]
    while stack:
        x, y, z = stack.pop()
        for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            for ny in (y, y + 1, y - 1):
                if (nx, ny, nz) in cells and (nx, ny, nz) not in seen:
                    seen.add((nx, ny, nz))
                    stack.append((nx, ny, nz))
    return all(c in seen for c in want)


def audit(fn_texts, spec, ground, seats=None):
    """[problem, ...] for every gatehouse in `fn_texts` ({function name: text}, e.g. 'gatehouse_z2', 'guards_act').

    ground(x, z) is the heightmap's rounded ground: the terrain under the retired shell and round the function's
    writes. seats: [(x, z)] of every seated NPC; None reads data/npc_seats.json."""
    gh = spec["gatehouse"]
    min_w, min_c = gh["min_width"], gh["min_clear"]
    bad = []
    if seats is None:
        seats = [(s["at"][0], s["at"][2]) for s in load(ROOT / "data" / "npc_seats.json")["seats"]]
    stands = guard_stands(fn_texts.get("guards_act", ""))
    allg = gates(spec)
    for name, gid, rec, arr, knock in allg:
        text = fn_texts.get("gatehouse_%s" % name)
        if text is None:
            bad.append("%s: no gatehouse_%s function emitted" % (name, name))
            continue
        fr = Frame(rec, gh)
        old = Frame(rec, gh, legacy=True)
        fy = fr.fy
        # the world the function leaves: the retired shell, the function over it, terrain under both
        over = retired_shell(old, rec, gh)
        voxels(text, over)

        def block(x, y, z, over=over):
            b = over.get((x, y, z))
            if b is not None:
                return b
            return "minecraft:stone" if y <= ground(x, z) else "minecraft:air"

        # width: every row of the passage has an unbroken run of standable columns across it
        for t in range(fr.t0, fr.t1 + 1):
            ok = []
            for k in range(fr.k0 - 6, fr.k1 + 7):
                x, z = fr.at(t, k)
                ok.append(stand_ok(block, x, fy, z))
            run = best = 0
            for v in ok:
                run = run + 1 if v else 0
                best = max(best, run)
            if best < min_w:
                bad.append("%s row t=%d: the passage is %d standable column(s) wide at the floor (y%d), under "
                           "gatehouse.min_width %d" % (name, t, best, fy - 1, min_w))
        # clear: the four blocks over the floor are free over the passage's lanes and the approach
        cols = [(fr.at(t, k), fy) for t in range(fr.t0, fr.t1 + 1) for k in range(fr.k0, fr.k1 + 1)]
        for side in ("outer", "inner"):
            for run in rec["approach"][side]:
                cols += [((c[0], c[1]), c[2]) for c in run]
        low = []
        for (x, z), feet in cols:
            for y in range(feet, feet + min_c):
                if block(x, y, z) not in AIR:
                    low.append((x, y, z, block(x, y, z)))
                    break
        if low:
            bad.append("%s: %d column(s) of the passage or its approach have a block within %d of the floor, e.g. %s"
                       % (name, len(low), min_c, low[:3]))
        # open: nothing of the retired shell is left, and the footprint's rows hold only the two posts above the floor
        left = sorted(c for c, b in over.items() if b in RETIRED)
        if left:
            bad.append("%s: %d block(s) of the retired shell are still standing, e.g. %s"
                       % (name, len(left), [(c, block(*c)) for c in left[:3]]))
        posts = {fr.at(1, fr.k0 - 1), fr.at(1, fr.k1 + 1)}
        extra = []
        for t in range(fr.t0, fr.t1 + 1):
            for k in range(fr.k0 - 1, fr.k1 + 2):
                x, z = fr.at(t, k)
                if (x, z) in posts:
                    continue
                for y in range(fy, fy + min_c):
                    if block(x, y, z) not in AIR and y > ground(x, z):
                        extra.append((x, y, z, block(x, y, z)))
        if extra:
            bad.append("%s: %d solid block(s) stand in the old footprint above the floor that are neither terrain "
                       "nor a post, e.g. %s" % (name, len(extra), extra[:3]))
        # guard
        st = stands.get(name)
        if st is None:
            if name.split("_")[0] not in held(spec):
                bad.append("%s: no guard placeholder summoned in guards_act" % name)
        else:
            gx, gy, gz, yaw = st
            t, k = fr.tk(gx, gz)
            if fr.k0 <= k <= fr.k1:
                bad.append("%s: the guard stands at (%d, %d, %d), IN the walk line (lane %d of %d..%d)"
                           % (name, gx, gy, gz, k, fr.k0, fr.k1))
            elif min(abs(k - fr.k0), abs(k - fr.k1)) != 1 or not (fr.t0 <= t <= fr.t1):
                bad.append("%s: the guard at (%d, %d, %d) is not beside the way (row t=%d, lane %d; the passage is "
                           "lanes %d..%d, rows %d..%d)" % (name, gx, gy, gz, t, k, fr.k0, fr.k1, fr.t0, fr.t1))
            if gy != fy or not (block(gx, gy, gz) in AIR and block(gx, gy + 1, gz) in AIR):
                bad.append("%s: the guard's feet y%d / head are not clear at the floor's level y%d" % (name, gy, fy))
            if block(gx, gy - 1, gz) in AIR:
                bad.append("%s: nothing under the guard at (%d, %d, %d)" % (name, gx, gy - 1, gz))
            want = round(math.degrees(math.atan2(-fr.out[0], fr.out[1])), 1)
            if abs(((yaw - want) + 180) % 360 - 180) > 1.0:
                bad.append("%s: the guard faces yaw %.1f, not down the approach (%.1f)" % (name, yaw, want))
            others = [s for s in seats] + [(v[0], v[2]) for n2, v in stands.items() if n2 != name]
            near = [round(math.hypot(gx - sx, gz - sz), 1) for sx, sz in others
                    if math.hypot(gx - sx, gz - sz) < NPC_CLEAR]
            if near:
                bad.append("%s: the guard at (%d, %d) is %s from another NPC, under NPC_CLEAR %s"
                           % (name, gx, gz, near, NPC_CLEAR))
        # walk: pad, arrival, knock box, both approaches in one piece
        stand = set()
        xs = [fr.at(t, k) for t in range(fr.t0 - 20, fr.t1 + 21) for k in range(fr.k0 - 6, fr.k1 + 7)]
        for (x, z) in xs:
            for y in range(fy - 4, fy + 6):
                if stand_ok(block, x, y, z):
                    stand.add((x, y, z))
        want_cells = []
        if st is not None:
            want_cells.append((st[0], st[1], st[2]))
        want_cells.append((int(arr[0] - 0.5), int(arr[1]), int(arr[2] - 0.5)))
        want_cells += [(x, knock[1], z) for x in range(knock[0], knock[3] + 1) for z in range(knock[2], knock[5] + 1)]
        for side in ("outer", "inner"):
            for run in rec["approach"][side]:
                want_cells.append((run[-1][0], run[-1][2], run[-1][1]))
        if not pieces_link(stand, want_cells):
            miss = [c for c in want_cells if c not in stand]
            bad.append("%s: the pad, the arrival, the knock box and the approach ends are not one walkable piece "
                       "(not standable: %s)" % (name, miss[:4]))
    return bad


def read_pack(pack):
    return {p.stem: p.read_text(encoding="utf-8") for p in Path(pack).glob("*.mcfunction")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "tools"))
    import ground as GD
    g = GD.load(a.source_root)
    texts = read_pack(a.pack)
    if not any(k.startswith("gatehouse_") for k in texts):
        print("gatehouse_audit: no gatehouse function in %s; run `python tools/rift_zones.py build` first" % a.pack,
              file=sys.stderr)
        return 1
    bad = audit(texts, load(ROOT / "data" / "rift_zones.json"), g)
    for b in bad:
        print("PROBLEM " + b)
    print("gatehouse_audit: %d gatehouse(s), %d problem(s)" % (sum(1 for k in texts if k.startswith("gatehouse_")),
                                                             len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
