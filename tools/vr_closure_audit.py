#!/usr/bin/env python
"""Victory Road's closure: is the cave the only way from the Deep to the League, and can it be finished?

  python tools/vr_closure_audit.py                 # reads build/datapacks/cobblers_rift_zones and cobblers_vr_caves
  python tools/vr_closure_audit.py --zones-pack <dir> --caves-pack <dir>

THE QUESTION (docs/world-building/CRITICAL_PATH_WALK_2.md items 1 and 3; the owner, 2026-10-08: "the caves are
meant to be the way"). A player who has released Hoopa (cobblers:flag/rift_crisis_resolved) and holds every other
pass must reach the League's lot ONLY by walking Victory Road's caves up from their mouth on the Deep's floor; and
walking them must get there.

WHAT IT READS, and nothing else:
  - the EMITTED zone pack: its location advancements (where a check fires) and its .mcfunction text (what it does),
    run by this file's own small interpreter against a modelled player. Never tools/rift_zones.py's code.
  - the EMITTED cave pack: its fill/setblock commands, applied in index order over the terrain, are the cave's
    blocks. Never tools/vr_caves.py's model or its walk-out.
  - the canonical heightmap (tools/ground.py), with the League's lot at data/vr_caves.json exit.lot_y over
    data/towns.json's league footprint; the Deep's pit from tools/rift_deep.model() (plan data from the heightmap
    and the owner's traced region), only to say where "the caves" begin; the mouth from data/vr_caves.json.

WHAT IT PROVES, three ways:
  1. SKY (fliers, riders, walkers, swimmers -- any body that does not go through rock): over every column any check
     covers, and every column of the League's lot, at every height from the ground up, no check admits a flag holder
     to the League's zone or lets a knock grant it, and every height over the lot turns such a player back. Movement
     is not modelled at all here, so this covers every way of moving through open air or water.
  2. OPENINGS: every carved cell of the cave reachable from the open sky outside the Deep's pit (the exit ravine),
     moving freely through air and water, without being admitted or granted.
  3. CAVES: from the mouth, a WALKING player holding the flag reaches the League's apron, is admitted on the way and
     is never turned back; the same walk without the flag never reaches it.
  And, for the record, the surface walk from the Deep's rim to G5's knock box (its step count), and what G5 does.

NOT COVERED: digging, ender pearls through blocks, the server's own reading of the commands (whether the location
check fires every 20 ticks, whether a selector volume tests the body as this file does), the Rift skin's block pass
and the gatehouse and wall blocks (ignored, which only ever opens more ground than the world has).

Written by the implementer of the closure (minecraft-systems-dev, 2026-10-08) at the caller's request, against
CLAUDE.md principle 16's preference: a separate reviewer should read it against the data before trusting it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

ZONES_PACK = ROOT / "build" / "datapacks" / "cobblers_rift_zones"
CAVES_PACK = ROOT / "build" / "datapacks" / "cobblers_vr_caves"
FLAG = "cobblers:flag/rift_crisis_resolved"
TOP = 320.0
PASSABLE = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:moss_carpet", "minecraft:rail",
            "minecraft:cave_vines", "minecraft:cave_vines_plant", "minecraft:spore_blossom", "minecraft:vine",
            "minecraft:glow_lichen"}
SOLID, AIR, WATER, LAVA = 0, 1, 2, 3


class AuditError(Exception):
    pass


# ------------------------------------------------------------------ the zone pack, run

class Pack:
    """The emitted zone pack: advancements [(name, [(x0, x1, y0, y1, z0, z1)], reward)] and functions {id: [tokens]}."""

    def __init__(self, path):
        path = Path(path)
        data = [d for d in (path / "data").iterdir() if d.is_dir() and d.name != "minecraft"]
        if not data:
            raise AuditError("no namespace in %s" % path)
        self.advs, self.fns = [], {}
        for ns in data:
            for p in sorted((ns / "advancement").rglob("*.json")):
                doc = json.loads(p.read_text(encoding="utf-8"))
                crit = doc["criteria"]["here"]
                if crit["trigger"] != "minecraft:location":
                    continue
                conds = crit["conditions"]["player"]
                terms = conds[0]["terms"] if conds[0]["condition"] == "minecraft:any_of" else conds
                boxes = []
                for t in terms:
                    pos = t["predicate"]["location"]["position"]
                    boxes.append((pos["x"]["min"], pos["x"]["max"], pos["y"]["min"], pos["y"]["max"],
                                  pos["z"]["min"], pos["z"]["max"]))
                self.advs.append((p.stem, boxes, doc["rewards"]["function"]))
            for p in sorted((ns / "function").rglob("*.mcfunction")):
                rel = p.relative_to(ns / "function").with_suffix("").as_posix()
                self.fns["%s:%s" % (ns.name, rel)] = [ln.split() for ln in p.read_text(encoding="utf-8").splitlines()
                                                      if ln.strip() and not ln.lstrip().startswith("#")]
        if not self.advs:
            raise AuditError("no location advancement in %s: is the zone pack built?" % path)
        self.objectives = sorted({t[4] for lines in self.fns.values() for t in lines
                                  if t[:3] == ["scoreboard", "players", "set"]})
        self.advancement_ids = sorted({a.split("=")[0] for lines in self.fns.values() for t in lines for w in t
                                       for m in re.finditer(r"advancements=\{([^}]*)\}", w)
                                       for a in m.group(1).split(",")})


def selector_args(sel):
    if not sel.startswith("@s"):
        raise AuditError("selector %r is not @s" % sel)
    if sel == "@s":
        return []
    body, out, cur, depth = sel[3:-1], [], "", 0
    for ch in body:
        depth += ch == "{"
        depth -= ch == "}"
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [tuple(a.split("=", 1)) for a in out if a]


class Player:
    def __init__(self, pos, advs, scores):
        self.pos, self.advs, self.scores = pos, set(advs), dict(scores)
        self.gamemode = "survival"
        self.moved = False
        self.posdep = False


_SEL = {}


def parsed(sel):
    """(gamemode tests, advancement tests, volume or None) of one selector, parsed once."""
    if sel not in _SEL:
        modes, advs, vol = [], [], {}
        for k, v in selector_args(sel):
            if k == "gamemode":
                modes.append((v.startswith("!"), v.lstrip("!")))
            elif k == "advancements":
                for term in v.strip("{}").split(","):
                    a, want = term.split("=")
                    advs.append((a, want == "true"))
            elif k in ("x", "y", "z", "dx", "dy", "dz"):
                vol[k] = float(v)
            else:
                raise AuditError("unmodelled selector argument %s in %s" % (k, sel))
        box = None
        if vol:
            if set(vol) != {"x", "y", "z", "dx", "dy", "dz"}:
                raise AuditError("a partial volume in %s" % sel)
            box = tuple((vol[c], vol[c] + vol["d" + c] + 1) for c in "xyz")
        _SEL[sel] = (modes, advs, box)
    return _SEL[sel]


def matches(pl, sel):
    """A selector on @s: gamemode, advancements, and a volume tested against the player's BODY (0.6 wide, 1.8 high),
    which is how a dx/dy/dz selector reads an entity: its box, not its feet."""
    modes, advs, box = parsed(sel)
    for neg, m in modes:
        if neg == (pl.gamemode == m):
            return False
    for a, want in advs:
        if (a in pl.advs) != want:
            return False
    if box is not None:
        pl.posdep = True
        x, y, z = pl.pos
        (x0, x1), (y0, y1), (z0, z1) = box
        if not (x - 0.3 < x1 and x + 0.3 > x0 and y < y1 and y + 1.8 > y0 and z - 0.3 < z1 and z + 0.3 > z0):
            return False
    return True


def run(pack, line, pl, depth=0):
    if depth > 12:
        raise AuditError("function depth over 12")
    t = line
    if t[0] == "execute":
        i = 1
        while i < len(t):
            if t[i] in ("if", "unless"):
                want = t[i] == "if"
                if t[i + 1] == "entity":
                    ok, i = matches(pl, t[i + 2]), i + 3
                elif t[i + 1] == "score":
                    if t[i + 2] != "@s" or t[i + 4] != "matches" or t[i + 5] != "1..":
                        raise AuditError("unmodelled score test %s" % " ".join(t))
                    ok, i = pl.scores.get(t[i + 3], 0) >= 1, i + 6
                else:
                    raise AuditError("unmodelled execute test %s" % " ".join(t))
                if ok != want:
                    return
            elif t[i] == "on" and t[i + 1] == "vehicle":
                return                    # the modelled player rides nothing; the player's own tp follows
            elif t[i] == "run":
                return run(pack, t[i + 1:], pl, depth + 1)
            else:
                raise AuditError("unmodelled execute part %s" % " ".join(t))
        return
    if t[0] == "function":
        if t[1] not in pack.fns:
            raise AuditError("function %s is called and not in the pack" % t[1])
        for ln in pack.fns[t[1]]:
            run(pack, ln, pl, depth + 1)
    elif t[:3] == ["scoreboard", "players", "set"] and t[3] == "@s":
        pl.scores[t[4]] = int(t[5])
    elif t[0] == "tp" and t[1] == "@s":
        pl.pos = (float(t[2]), float(t[3]), float(t[4]))
        pl.moved = True
    elif t[0] in ("title", "tellraw", "spawnpoint", "advancement", "playsound", "particle"):
        pass
    else:
        raise AuditError("unmodelled command %s" % " ".join(t))


_HASH = {}


def fires(adv, pos):
    """Whether a location advancement's boxes hold `pos` (inclusive bounds, as a location predicate reads them).
    The boxes are bucketed by 64-block cell once per advancement, which only changes the speed."""
    x, y, z = pos
    key = id(adv)
    if key not in _HASH:
        h = {}
        for b in adv[1]:
            for cx in range(int(b[0] // 64), int(b[1] // 64) + 1):
                for cz in range(int(b[4] // 64), int(b[5] // 64) + 1):
                    h.setdefault((cx, cz), []).append(b)
        _HASH[key] = (adv, h)
    for b in _HASH[key][1].get((int(x // 64), int(z // 64)), ()):
        if b[0] <= x <= b[1] and b[2] <= y <= b[3] and b[4] <= z <= b[5]:
            return True
    return False


class Rules:
    """What the pack does to one player at one position: 'turned' (a check moved them away), 'admit' (the League's
    score set where they stand), 'grant' (set and moved through a gate), or 'ok'. Per call, from the text."""

    def __init__(self, pack, league_obj, advs, scores):
        self.pack, self.obj, self.advs, self.scores = pack, league_obj, advs, scores
        self.cache = {}

    def fired(self, pos):
        if not hasattr(self, "_h"):
            self._h = {}
            for i, a in enumerate(self.pack.advs):
                for b in a[1]:
                    for cx in range(int(b[0] // 64), int(b[1] // 64) + 1):
                        for cz in range(int(b[4] // 64), int(b[5] // 64) + 1):
                            self._h.setdefault((cx, cz), []).append((i, b))
        x, y, z = pos
        out = set()
        for i, b in self._h.get((int(x // 64), int(z // 64)), ()):
            if i not in out and b[0] <= x <= b[1] and b[2] <= y <= b[3] and b[4] <= z <= b[5]:
                out.add(i)
        return tuple(sorted(out))

    def at(self, pos, scored):
        fired = self.fired(pos)
        if not fired:
            return "ok", None
        key = (fired, scored)
        if key in self.cache:
            return self.cache[key]
        verdict, posdep, where = "ok", False, None
        for i in fired:
            sc = dict(self.scores)
            if scored:
                sc[self.obj] = 1
            pl = Player(pos, self.advs, sc)
            for ln in [["function", self.pack.advs[i][2]]]:
                run(self.pack, ln, pl)
            posdep = posdep or pl.posdep
            got = pl.scores.get(self.obj, 0) >= 1 and not scored
            if pl.moved and got:
                verdict, where = "grant", pl.pos
                break
            if got:
                verdict = "admit"
            elif pl.moved and verdict == "ok":
                verdict = "turned"
        out = (verdict, where)
        if not posdep:
            self.cache[key] = out
        return out


# ------------------------------------------------------------------ the world model

def league_zone(pack, centre, lot_y):
    """(advancement index, objective) of the one zone check whose box holds the League's lot centre."""
    pos = (centre[0] + 0.5, lot_y + 1.0, centre[1] + 0.5)
    hits = []
    for i, a in enumerate(pack.advs):
        if not fires(a, pos):
            continue
        body = pack.fns.get(a[2], [])
        objs = {t[t.index("score") + 2] for t in body if "turn_back" in " ".join(t) and "score" in t}
        if objs:
            hits.append((i, objs.pop()))
    if len(hits) > 1:
        raise AuditError("%d zone checks hold the League's lot centre %s at y%d (want exactly 1): %s"
                         % (len(hits), centre, lot_y + 1, [pack.advs[i][0] for i, _ in hits]))
    if hits:
        return hits[0] + (True,)
    # no check holds the lot: the League's zone is then the one whose knock lets players through towards it, i.e.
    # the zone check nearest the lot. Reported as a problem by the caller; the sky proof then finds the lot open.
    best = None
    for i, a in enumerate(pack.advs):
        body = pack.fns.get(a[2], [])
        objs = {t[t.index("score") + 2] for t in body if "turn_back" in " ".join(t) and "score" in t}
        if not objs:
            continue
        d = min(max(b[0] - centre[0], centre[0] - b[1], 0) + max(b[4] - centre[1], centre[1] - b[5], 0) for b in a[1])
        if best is None or d < best[0]:
            best = (d, i, objs.pop())
    if best is None:
        raise AuditError("no zone check in the pack")
    return best[1], best[2], False


def cave_grid(caves_pack, g, lot, lot_y):
    """(code array [x, z, y], (X0, Z0, Y0), carved mask) from the cave pack's commands over the terrain."""
    fn_dirs = list((Path(caves_pack) / "data").glob("*/function/*"))
    idx = [d for d in fn_dirs if (d / "index.txt").is_file()]
    if len(idx) != 1:
        raise AuditError("want one function folder with an index.txt in %s, found %d" % (caves_pack, len(idx)))
    d = idx[0]
    cmd = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)")
    cmds = []
    for name in (d / "index.txt").read_text(encoding="utf-8").split():
        for ln in (d / (name + ".mcfunction")).read_text(encoding="utf-8").splitlines():
            m = cmd.match(ln)
            if m:
                v = [int(c) for c in m.groups()[1:7] if c is not None]
                if len(v) == 3:
                    v = v + v
                cmds.append((v, m.group(8).split("[")[0]))
    if not cmds:
        raise AuditError("no block command in %s" % caves_pack)
    xs = [c for v, _ in cmds for c in (v[0], v[3])]
    ys = [c for v, _ in cmds for c in (v[1], v[4])]
    zs = [c for v, _ in cmds for c in (v[2], v[5])]
    X0, X1, Y0, Y1, Z0, Z1 = min(xs) - 8, max(xs) + 8, min(ys) - 2, max(ys) + 8, min(zs) - 8, max(zs) + 8
    G = g.box(X0, Z0, X1, Z1).T.astype(np.int32)
    lx0, lz0, lx1, lz1 = lot
    G[max(lx0 - X0, 0):max(lx1 - X0 + 1, 0), max(lz0 - Z0, 0):max(lz1 - Z0 + 1, 0)] = lot_y
    yy = np.arange(Y0, Y1 + 1, dtype=np.int32)[None, None, :]
    code = np.where(yy > G[:, :, None], AIR, SOLID).astype(np.uint8)
    carved = np.zeros(code.shape, bool)
    for v, b in cmds:
        c = AIR if b in PASSABLE else WATER if b == "minecraft:water" else LAVA if b == "minecraft:lava" else SOLID
        sl = (slice(v[0] - X0, v[3] - X0 + 1), slice(v[2] - Z0, v[5] - Z0 + 1), slice(v[1] - Y0, v[4] - Y0 + 1))
        code[sl] = c
        carved[sl] = c in (AIR, WATER)
    return code, (X0, Z0, Y0), carved, G


def pit_mask(source_root):
    import rift_deep as RD
    m = RD.model(source_root)
    X0, Z0, _X1, _Z1 = m["box"]
    zz, xx = np.nonzero(m["mask"])
    return {(int(x) + X0, int(z) + Z0) for z, x in zip(zz, xx)}


# ------------------------------------------------------------------ the three proofs

def sky(rules, pack, g, lot, lot_y, problems, notes):
    """Every column a check covers, and the lot, at every height from the ground to the build limit."""
    rects = set()
    for a in pack.advs:
        for b in a[1]:
            rects.add((int(np.floor(b[0])), int(np.ceil(b[1])) - 1, int(np.floor(b[4])), int(np.ceil(b[5])) - 1))
    sel_vol = re.compile(r"x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)")
    ybreaks = {TOP}
    for lines in pack.fns.values():
        for t in lines:
            for w in t:
                for m in sel_vol.finditer(w):
                    x, y, z, dx, dy, dz = (int(c) for c in m.groups())
                    rects.add((x, x + dx, z, z + dz))
                    ybreaks.update((y - 1.8, y + dy + 1.0))
    for a in pack.advs:
        for b in a[1]:
            ybreaks.update((b[2], b[3]))
    X0 = min(r[0] for r in rects) - 1
    X1 = max(r[1] for r in rects) + 1
    Z0 = min(r[2] for r in rects) - 1
    Z1 = max(r[3] for r in rects) + 1
    rng = np.random.default_rng(1)
    sig = np.zeros((X1 - X0 + 1, Z1 - Z0 + 1), np.uint64)
    for r in sorted(rects):
        sig[r[0] - X0:r[1] - X0 + 1, r[2] - Z0:r[3] - Z0 + 1] += np.uint64(rng.integers(1, 2 ** 63))
    G = g.box(X0, Z0, X1, Z1).T.astype(np.int32)
    lx0, lz0, lx1, lz1 = lot
    on_lot = np.zeros(sig.shape, bool)
    on_lot[lx0 - X0:lx1 - X0 + 1, lz0 - Z0:lz1 - Z0 + 1] = True
    G[on_lot] = lot_y
    F0 = np.maximum(G + 1, 63)            # the lowest feet a body can have: on the ground, or on water at sea level
    covered = sig != 0
    want = covered | on_lot
    keys, inv = np.unique(sig[want], return_inverse=True)
    wi = np.argwhere(want)
    breaks = sorted(ybreaks)
    admits, bare, n = [], [], 0
    order = np.argsort(inv, kind="stable")
    bounds = np.searchsorted(inv[order], np.arange(len(keys) + 1))
    for gi in range(len(keys)):
        cols = wi[order[bounds[gi]:bounds[gi + 1]]]
        i0, k0 = cols[0]
        x, z = X0 + int(i0) + 0.5, Z0 + int(k0) + 0.5
        f0s = F0[cols[:, 0], cols[:, 1]].astype(float)
        fmin = float(f0s.min())
        # the verdict is constant between two breaks, so every column's own lowest feet and both sides of every
        # break above the lowest cover every height a body can have over this class of columns
        samples = sorted(set(f0s.tolist()) | {b + e for b in breaks for e in (-0.01, 0.01) if fmin <= b + e <= TOP})
        verdicts = [(f, rules.at((x, f, z), False)[0]) for f in samples]
        n += len(samples)
        worst = max([f for f, v in verdicts if v in ("admit", "grant")], default=-1e9)
        opened = max([f for f, v in verdicts if v != "turned"], default=-1e9)
        for c in cols[f0s <= worst]:
            admits.append((X0 + int(c[0]), Z0 + int(c[1])))
        lotc = on_lot[cols[:, 0], cols[:, 1]]
        for c in cols[(f0s <= opened) & lotc]:
            bare.append((X0 + int(c[0]), Z0 + int(c[1])))
    if admits:
        problems.append("SKY: %d column(s) admit or grant the League's pass to a flag holder who never walked the caves, "
                        "e.g. %s" % (len(admits), admits[0]))
    if bare:
        problems.append("SKY: %d column(s) of the League's lot let a flag holder stand or fly there unchecked, e.g. %s"
                        % (len(bare), bare[0]))
    notes.append("sky: %d columns (%d on the League's lot), %d column classes, %d heights run; %d admit, %d lot "
                 "column(s) open" % (int(want.sum()), int(on_lot.sum()), len(keys), n, len(admits), len(bare)))


def openings(rules, code, origin, carved, G, pit, problems, notes):
    """Every carved cell reachable from the open sky outside the Deep's pit, through air and water, 6-connected."""
    X0, Z0, Y0 = origin
    nx, nz, ny = code.shape
    open_ = (code == AIR) | (code == WATER)
    yy = np.arange(Y0, Y0 + ny)[None, None, :]
    sky_cell = open_ & ~carved & (yy > G[:, :, None])
    start = np.zeros(code.shape, bool)
    for ax in range(3):
        for s in (1, -1):
            start |= carved & np.roll(sky_cell, s, axis=ax)
    seen = np.zeros(code.shape, bool)
    q = deque()
    for i, k, j in np.argwhere(start):
        if (X0 + int(i), Z0 + int(k)) in pit:
            continue
        seen[i, k, j] = True
        q.append((int(i), int(k), int(j)))
    n_start = len(q)
    bad, turned, reached = [], 0, 0
    while q:
        i, k, j = q.popleft()
        pos = (X0 + i + 0.5, float(Y0 + j), Z0 + k + 0.5)
        v, _w = rules.at(pos, False)
        if v in ("admit", "grant"):
            bad.append((X0 + i, Y0 + j, Z0 + k, v))
            continue
        if v == "turned":
            turned += 1
            continue
        reached += 1
        for di, dk, dj in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            a, b, c = i + di, k + dk, j + dj
            if 0 <= a < nx and 0 <= b < nz and 0 <= c < ny and not seen[a, b, c] and carved[a, b, c]:
                seen[a, b, c] = True
                q.append((a, b, c))
    if bad:
        problems.append("OPENINGS: %d carved cell(s) reached from the open sky admit or grant the League's pass, e.g. %s"
                        % (len(bad), bad[0]))
    notes.append("openings: %d sky-adjacent carved cells outside the pit, %d carved cells reached, %d turned back, "
                 "%d admit" % (n_start, reached, turned, len(bad)))


def standable(code, i, k, j):
    nx, nz, ny = code.shape
    if not (0 <= i < nx and 0 <= k < nz and 1 <= j < ny - 1):
        return False
    feet, head = code[i, k, j], code[i, k, j + 1]
    if feet not in (AIR, WATER) or head not in (AIR, WATER):
        return False
    return feet == WATER or code[i, k, j - 1] in (SOLID, WATER)


def walk(rules, code, origin, start, lot, lot_y, carved):
    """BFS from `start` (a feet cell) with the pass state. Returns (lot cell reached or None, steps, admitted at,
    turned-back cells while unscored)."""
    X0, Z0, Y0 = origin
    lx0, lz0, lx1, lz1 = lot
    nx, nz, ny = code.shape
    si, sk, sj = start
    dist = {(si, sk, sj, False): 0}
    parent = {}
    q = deque([(si, sk, sj, False)])
    turned, admitted, goal = set(), None, None
    while q:
        i, k, j, s = q.popleft()
        x, z, y = X0 + i, Z0 + k, Y0 + j
        if s and lx0 <= x <= lx1 and lz0 <= z <= lz1 and y >= lot_y + 1:
            goal = (i, k, j, s)
            break
        moves = []
        for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, k + dk
            for dj in (0, 1, -1, -2, -3):
                c = j + dj
                if not standable(code, a, b, c):
                    continue
                if dj == 1 and (j + 2 >= ny or code[i, k, j + 2] not in (AIR, WATER)):
                    continue          # no headroom to jump from here
                if dj < 0 and any(code[a, b, c + h] not in (AIR, WATER) for h in range(2, 2 - dj)):
                    continue          # the drop is not clear
                moves.append((a, b, c))
                break
        if code[i, k, j] == WATER:
            for dj in (1, -1):
                if standable(code, i, k, j + dj) or (0 < j + dj < ny - 1 and code[i, k, j + dj] == WATER
                                                     and code[i, k, j + dj + 1] in (AIR, WATER)):
                    moves.append((i, k, j + dj))
        for (a, b, c) in moves:
            pos = (X0 + a + 0.5, float(Y0 + c), Z0 + b + 0.5)
            v, _w = rules.at(pos, s)
            ns = s
            if v == "turned":
                if not s:
                    turned.add((X0 + a, Y0 + c, Z0 + b))
                continue
            if v == "admit":
                ns = True
                if admitted is None:
                    admitted = (X0 + a, Y0 + c, Z0 + b)
            if v == "grant":
                continue              # a gate's teleport: not a step of a walk inside the cave
            key = (a, b, c, ns)
            if key not in dist:
                dist[key] = dist[(i, k, j, s)] + 1
                parent[key] = (i, k, j, s)
                q.append(key)
    steps = dist[goal] if goal else None
    path = []
    node = goal
    while node is not None:
        path.append((X0 + node[0], Y0 + node[2], Z0 + node[1]))
        node = parent.get(node)
    return (goal and (X0 + goal[0], Y0 + goal[2], Z0 + goal[1])), steps, admitted, turned, path[::-1]


def find_start(code, origin, at):
    X0, Z0, Y0 = origin
    i, k = at[0] - X0, at[2] - Z0
    for dj in (0, 1, -1, 2, -2, 3, -3):
        j = at[1] - Y0 + dj
        if standable(code, i, k, j):
            return (i, k, j)
    raise AuditError("Victory Road's mouth %s is not standable in the cave pack's blocks" % (at,))


def surface(rules, g, pit, rim, knocks, lot, lot_y, notes):
    """For the record: the walk on the heightmap from the Deep's rim to each knock box, with the zone checks."""
    X0, Z0 = rim[0] - 700, rim[1] - 900
    X1, Z1 = rim[0] + 700, rim[1] + 600
    H = g.box(X0, Z0, X1, Z1).T.astype(np.int32)
    lx0, lz0, lx1, lz1 = lot
    H[lx0 - X0:lx1 - X0 + 1, lz0 - Z0:lz1 - Z0 + 1] = lot_y
    F = np.maximum(H + 1, 63)
    dist = np.full(H.shape, -1, np.int32)
    i0, k0 = rim[0] - X0, rim[1] - Z0
    dist[i0, k0] = 0
    q = deque([(i0, k0)])
    at_knock, verdicts = {}, {}
    while q:
        i, k = q.popleft()
        for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, k + dk
            if not (0 <= a < H.shape[0] and 0 <= b < H.shape[1]) or dist[a, b] >= 0:
                continue
            if (X0 + a, Z0 + b) in pit or F[a, b] - F[i, k] > 1 or F[i, k] - F[a, b] > 3:
                continue
            x, z = X0 + a, Z0 + b
            for name, kb in knocks:
                if kb[0] <= x <= kb[1] - 1 and kb[4] <= z <= kb[5] - 1 and name not in at_knock:
                    at_knock[name] = int(dist[i, k]) + 1
                    verdicts[name] = rules.at((x + 0.5, float(kb[2]), z + 0.5), False)[0]
            v, _w = rules.at((x + 0.5, float(F[a, b]), z + 0.5), False)
            if v != "ok":
                continue
            dist[a, b] = dist[i, k] + 1
            q.append((a, b))
    for name in sorted(at_knock):
        notes.append("surface: from the Deep's rim %s to %s's knock box in %d steps on the heightmap; the knock answers "
                     "a flag holder who never walked the caves with: %s" % (rim, name, at_knock[name], verdicts[name]))
    return at_knock, verdicts


_INPUTS = {}


def audit(zones_pack=ZONES_PACK, caves_pack=CAVES_PACK, source_root=None, with_surface=True):
    import ground as GD
    from terrain import env_source_root
    source_root = source_root or env_source_root()
    problems, notes = [], []
    pack = Pack(zones_pack)
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))
    fp = next(t for t in towns["towns"] if t.get("id") == "league")["footprint"]
    lot = (fp["min_x"], fp["min_z"], fp["max_x"], fp["max_z"])
    vrc = json.loads((ROOT / "data" / "vr_caves.json").read_text(encoding="utf-8"))
    lot_y = vrc["exit"]["lot_y"]
    centre = ((lot[0] + lot[2]) // 2, (lot[1] + lot[3]) // 2)
    li, obj, holds = league_zone(pack, centre, lot_y)
    notes.append("the League's zone check: %s, objective %s" % (pack.advs[li][0], obj))
    if not holds:
        problems.append("no zone check holds the League's lot centre %s: the League is unzoned, so a flier lands on it "
                        "from anywhere (CRITICAL_PATH_WALK_2.md item 4)" % (centre,))
    if FLAG not in pack.advancement_ids:
        problems.append("no selector in the zone pack names %s: nothing reads the finale's flag" % FLAG)
    everything = set(pack.advancement_ids)
    others = {o: 1 for o in pack.objectives if o != obj}
    resolved = Rules(pack, obj, everything, others)
    unresolved = Rules(pack, obj, everything - {FLAG}, others)
    # the inputs that do not depend on the zone pack are read once per process (a mutation test runs several packs)
    if ("ground", source_root) not in _INPUTS:
        _INPUTS[("ground", source_root)] = (GD.load(source_root), pit_mask(source_root))
    g, pit = _INPUTS[("ground", source_root)]

    # 1. sky
    sky(resolved, pack, g, lot, lot_y, problems, notes)
    # 2. openings, and 3. the caves, on the cave pack's own blocks
    ck = ("caves", str(Path(caves_pack).resolve()), lot, lot_y)
    if ck not in _INPUTS:
        _INPUTS[ck] = cave_grid(caves_pack, g, lot, lot_y)
    code, origin, carved, G = _INPUTS[ck]
    openings(resolved, code, origin, carved, G, pit, problems, notes)
    start = find_start(code, origin, vrc["mouth"]["at"])
    goal, steps, admitted, turned, path = walk(resolved, code, origin, start, lot, lot_y, carved)
    if goal is None:
        problems.append("CAVES: a flag holder walking from Victory Road's mouth %s never reaches the League's apron"
                        % (vrc["mouth"]["at"],))
    else:
        notes.append("caves: a flag holder walks from the mouth %s to the League's apron at %s in %d steps, admitted "
                     "at %s" % (tuple(vrc["mouth"]["at"]), goal, steps, admitted))
    if turned:
        t = sorted(turned)
        problems.append("CAVES: a flag holder walking up from the mouth is turned back at %d cell(s) before being "
                        "admitted, e.g. %s: a crossing into the League's zone outside its admit ground" % (len(t), t[0]))
    g2, _s2, a2, _t2, _p2 = walk(unresolved, code, origin, start, lot, lot_y, carved)
    if g2 is not None:
        problems.append("CAVES: a player WITHOUT %s walks from the mouth to the League's apron at %s" % (FLAG, g2))
    if a2 is not None:
        problems.append("CAVES: a player without %s is admitted at %s" % (FLAG, a2))
    notes.append("caves without the flag: apron %s, admitted %s" % ("reached" if g2 else "never reached", a2))
    if with_surface:
        knocks = [(a[0], a[1][0]) for a in pack.advs if a[0].endswith("_knock")]
        rim = (3576, 3000)
        if (rim[0], rim[1]) in pit:
            raise AuditError("the rim point %s is inside the Deep's pit" % (rim,))
        _at, verdicts = surface(resolved, g, pit, rim, knocks, lot, lot_y, notes)
        for name, v in verdicts.items():
            if v in ("admit", "grant"):
                problems.append("SURFACE: %s's knock box, walked to from the Deep's rim, lets in a flag holder who never "
                                "walked the caves (%s)" % (name, v))
    return problems, notes, path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zones-pack", default=str(ZONES_PACK))
    ap.add_argument("--caves-pack", default=str(CAVES_PACK))
    ap.add_argument("--source-root")
    ap.add_argument("--no-surface", action="store_true", help="skip the record-only surface walk")
    a = ap.parse_args(argv)
    try:
        problems, notes, _path = audit(a.zones_pack, a.caves_pack, a.source_root, not a.no_surface)
    except AuditError as exc:
        print("vr_closure_audit: %s" % exc)
        return 2
    for n in notes:
        print("  " + n)
    for p in problems:
        print("  PROBLEM " + p)
    print("vr_closure_audit: %s, %d problem(s)" % ("FAILED" if problems else "the caves are the only way, and walkable",
                                                   len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
