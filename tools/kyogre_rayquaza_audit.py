#!/usr/bin/env python
"""Independent audit of Kyogre's cave (step R18KC) and Rayquaza's sky (step R14R), read from the BUILT function text.

Written by test-author, who built neither. The expectations come from docs/world-building/KYOGRE_CAVE.md (section 7, what an
audit must prove; section 6 and the owner's answers in section 9 for Rayquaza), from vanilla movement and fall physics, and
from the authored records the builders were given. Nothing is taken from either builder's model:

  * it never imports tools/kyogre_cave.py, tools/rayquaza_sky.py, tools/legendaries.py or tools/portals.py;
  * every block is REPLAYED from the packs' `fill`/`setblock` lines into this file's own voxel model, state by state
    (built, lamps lit, every drain slice, drained, Kyogre awake, reset around a solver);
  * every place a player can stand or swim is this file's own flood fill over that replay (Kyogre: whole blocks, swim,
    one-block steps, falls; Rayquaza: half-block collision, 0.5 steps, 1-block jumps, vanilla fall damage);
  * every gate is read off the command lines themselves (selectors, `execute` chains and the call graph).

The heightmap enters through tools/ground.py only (the overworld side: the reef's ground, Rayquaza's summit terrain).

  python tools/kyogre_rayquaza_audit.py [--kyogre-pack DIR] [--rayquaza-pack DIR] [--out FILE]

The packs default to build/datapacks/cobblers_kyogre_cave and cobblers_rayquaza (each with its _build sibling): build them
first with the builders' own `build` commands. The full result goes to --out (default derived/kyogre_rayquaza_audit.json);
one verdict line is printed. Exit 1 on any failed property.

What this does NOT cover (validity is not runtime behaviour, .claude/rules/testing.md): whether spawnpokemonat places a
legendary inside a barrier-filled cage, whether the capture callback fires and attributes the catch (E2), whether a Dive
swimmer beats the Race (E3), whether a NoAI Kyogre can be battled after the awake NBT (E5), whether Slow Falling is applied
in time in a real fall, the RCT level cap at eight badges (legendaries_audit rct_caps does not cover Kyogre, which is not a
data/legendaries.json record), and anything a player builds or breaks. The flowing water of the Race is modelled only as an
over-approximated spread, never as a current.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data"
KPACK = ROOT / "build" / "datapacks" / "cobblers_kyogre_cave"
RPACK = ROOT / "build" / "datapacks" / "cobblers_rayquaza"
OUT = ROOT / "derived" / "kyogre_rayquaza_audit.json"

POCKET = "cobblers:pocket"
GUARDIAN = "cobblers.guardian"
KF = "cobblers:kyogre_cave"
RF = "cobblers:rayquaza"
SHELL_MIN = 4             # KYOGRE_CAVE.md 7.1: "at least 4 blocks of shell in all six directions"
REACH = 3.0               # vanilla survival entity_interaction_range, from the eyes to the entity's box
EYE = 1.62                # vanilla standing eye height
LETHAL_FALL = 23          # vanilla: fall damage = blocks fallen - 3, a player has 20 health
DAMAGE_FALL = 4           # the first fall that hurts
# KYOGRE_CAVE.md section 9 answer 6 (the owner, 2026-10-06), contract C26: the three advancements of Rayquaza's gate
RAY_GATE = ("cobblers:flag/champion_cleared", "cobblers:legendary/kyogre/met", "cobblers:legendary/groudon/met")
# KYOGRE_CAVE.md section 1-2 and 9 answer 2: the crossing needs the dive tag, gym8_cleared and the station's quest
KY_FLAG = "cobblers:flag/gym8_cleared"

VOID, AIR, WATER, SOLID = 0, 1, 2, 3


class AuditError(Exception):
    pass


def _j(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def base(block):
    return block.split("[")[0].split("{")[0]


# ================================================================================================ reading the packs

def read_pack(runtime_dir):
    """{fns: {id: [lines]}, adv: {id: json}, other: {rel: text}, build_fns: set} of a pack and its _build sibling."""
    d = Path(runtime_dir)
    out = {"fns": {}, "adv": {}, "other": {}, "build_fns": set()}
    for root in (d, d.with_name(d.name + "_build")):
        if not root.exists():
            if root == d:
                raise AuditError("no pack at %s: build it first with its builder's `build` command" % d)
            continue
        for f in sorted(root.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(root).as_posix()
            parts = rel.split("/")
            text = f.read_text(encoding="utf-8")
            if len(parts) >= 4 and parts[0] == "data" and parts[2] == "function" and rel.endswith(".mcfunction"):
                fid = "%s:%s" % (parts[1], "/".join(parts[3:])[:-len(".mcfunction")])
                out["fns"][fid] = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
                if root != d:
                    out["build_fns"].add(fid)
            elif len(parts) >= 4 and parts[0] == "data" and parts[2] == "advancement" and rel.endswith(".json"):
                out["adv"]["%s:%s" % (parts[1], "/".join(parts[3:])[:-len(".json")])] = json.loads(text)
            else:
                out["other"][rel] = text
    return out


def split_top(s, sep=","):
    out, cur, depth, q = [], [], 0, None
    for ch in s:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch in "[{(":
            depth += 1
        elif ch in "]})":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def tokens(line):
    return [t for t in split_top(line, " ") if t]


class Sel:
    """An entity selector: kind (@a, @e, @s ...), its arguments, and the readings an audit needs."""

    def __init__(self, tok):
        m = re.match(r"^@([aesprn])(?:\[(.*)\])?$", tok, re.S)
        if not m:
            raise AuditError("not a selector: %r" % tok)
        self.kind = "@" + m.group(1)
        self.args = []
        for a in split_top(m.group(2) or ""):
            k, _, v = a.partition("=")
            self.args.append((k.strip(), v.strip()))
        self.text = tok

    def get(self, k):
        return [v for kk, v in self.args if kk == k]

    def tags(self):
        return self.get("tag")

    def advancements(self):
        out = {}
        for v in self.get("advancements"):
            for kv in split_top(v.strip()[1:-1]):
                k, _, val = kv.partition("=")
                out[k.strip()] = val.strip()
        return out

    def box(self):
        """(x0, y0, z0, x1, y1, z1) of the cells an x/y/z/dx/dy/dz volume covers, or None."""
        if not self.get("dx"):
            return None
        x, y, z = (float(self.get(k)[0]) for k in "xyz")
        dx, dy, dz = (float(self.get(k)[0]) for k in ("dx", "dy", "dz"))
        return (int(math.floor(x)), int(math.floor(y)), int(math.floor(z)),
                int(math.floor(x + dx)), int(math.floor(y + dy)), int(math.floor(z + dz)))

    def is_pokemon(self):
        return "cobblemon:pokemon" in self.get("type")

    def excludes_guardian(self):
        return ("!" + GUARDIAN) in self.tags()


def parse_exec(line):
    """The `execute` chain of a line: {as, in, positioned, conds, run, returned}."""
    raw = line[1:] if line.startswith("$") else line
    t = tokens(raw)
    ctx = {"as": None, "in": None, "positioned": None, "conds": [], "run": t, "returned": False, "tokens": t}
    if t and t[0] == "execute":
        i = 1
        run = []
        while i < len(t):
            w = t[i]
            if w == "run":
                run = t[i + 1:]
                break
            if w == "as":
                ctx["as"] = Sel(t[i + 1])
                i += 2
            elif w == "at":
                i += 2
            elif w == "in":
                ctx["in"] = t[i + 1]
                i += 2
            elif w == "positioned":
                if t[i + 1] == "as":
                    i += 3
                else:
                    ctx["positioned"] = tuple(float(v) for v in t[i + 1:i + 4])
                    i += 4
            elif w in ("if", "unless"):
                kind = t[i + 1]
                if kind == "entity":
                    ctx["conds"].append((w, "entity", Sel(t[i + 2]), ctx["positioned"], ctx["in"]))
                    i += 3
                elif kind == "score":
                    if t[i + 4] == "matches":
                        ctx["conds"].append((w, "score", t[i + 2], t[i + 3], "matches", t[i + 5]))
                        i += 6
                    else:
                        ctx["conds"].append((w, "score", t[i + 2], t[i + 3], t[i + 4], t[i + 5], t[i + 6]))
                        i += 7
                elif kind == "block":
                    ctx["conds"].append((w, "block", t[i + 2:i + 5], t[i + 5]))
                    i += 6
                elif kind == "loaded":
                    i += 5
                else:
                    raise AuditError("an execute condition this audit cannot read: %r in %r" % (kind, line))
            elif w == "store":
                if t[i + 2] != "score":
                    raise AuditError("an execute store this audit cannot read: %r" % line)
                i += 5
            else:
                raise AuditError("an execute subcommand this audit cannot read: %r in %r" % (w, line))
        ctx["run"] = run
    while len(ctx["run"]) >= 2 and ctx["run"][0] == "return" and ctx["run"][1] == "run":
        ctx["run"] = ctx["run"][2:]
        ctx["returned"] = True
    if ctx["run"][:1] == ["return"]:
        ctx["returned"] = True
    return ctx


def calls(fns):
    """[(caller, line index, callee, ctx, scheduled)] over every function line."""
    out = []
    for fid, lines in fns.items():
        for i, ln in enumerate(lines):
            ctx = parse_exec(ln)
            r = ctx["run"]
            if r[:1] == ["function"] and len(r) >= 2:
                out.append((fid, i, r[1], ctx, False))
            elif r[:2] == ["schedule", "function"]:
                out.append((fid, i, r[2], ctx, True))
    return out


def callers_of(cg, fid):
    return [c for c in cg if c[2] == fid]


# ================================================================================================ the Kyogre replay

class Vox:
    """A voxel replay: st (VOID never written, AIR, WATER, SOLID) and the block id of every written cell."""

    def __init__(self, box, pad=6):
        x0, y0, z0, x1, y1, z1 = box
        self.o = (x0 - pad, max(0, y0 - pad), z0 - pad)
        self.shape = (x1 - x0 + 2 * pad + 1, y1 + pad + 1 - self.o[1], z1 - z0 + 2 * pad + 1)
        self.st = np.zeros(self.shape, np.uint8)
        self.bk = np.zeros(self.shape, np.uint16)
        self.names = ["(void)"]
        self.idx = {}

    def copy(self):
        v = Vox.__new__(Vox)
        v.o, v.shape, v.names, v.idx = self.o, self.shape, self.names, self.idx
        v.st, v.bk = self.st.copy(), self.bk.copy()
        return v

    def bid(self, name):
        if name not in self.idx:
            self.idx[name] = len(self.names)
            self.names.append(name)
        return self.idx[name]

    def sl(self, b):
        x0, y0, z0, x1, y1, z1 = b
        lo = (min(x0, x1) - self.o[0], min(y0, y1) - self.o[1], min(z0, z1) - self.o[2])
        hi = (max(x0, x1) - self.o[0] + 1, max(y0, y1) - self.o[1] + 1, max(z0, z1) - self.o[2] + 1)
        if min(lo) < 0 or any(h > s for h, s in zip(hi, self.shape)):
            raise AuditError("a write %s falls outside the replay box" % (b,))
        return tuple(slice(a, c) for a, c in zip(lo, hi))

    def write(self, b, block, filt=None, keep=False):
        name = base(block)
        code = AIR if name in ("minecraft:air", "minecraft:cave_air", "minecraft:void_air") else (
            WATER if name == "minecraft:water" else SOLID)
        s = self.sl(b)
        if filt is None and not keep:
            self.st[s] = code
            self.bk[s] = self.bid(name)
            return
        if keep or base(filt) == "minecraft:air":
            m = (self.st[s] == VOID) | (self.st[s] == AIR)
        else:
            m = self.bk[s] == self.idx.get(base(filt), -1)
        self.st[s] = np.where(m, code, self.st[s])
        self.bk[s] = np.where(m, self.bid(name), self.bk[s])

    def at(self, x, y, z):
        return int(self.st[x - self.o[0], y - self.o[1], z - self.o[2]])

    def flat(self, x, y, z):
        nx, ny, nz = self.shape
        return ((x - self.o[0]) * ny + (y - self.o[1])) * nz + (z - self.o[2])

    def xyz(self, f):
        nx, ny, nz = self.shape
        i, r = divmod(f, ny * nz)
        j, k = divmod(r, nz)
        return (i + self.o[0], j + self.o[1], k + self.o[2])


def block_writes(lines):
    """[(box, block, filter, keep)] of every fill/setblock line (with or without an execute prefix)."""
    out = []
    for ln in lines:
        r = parse_exec(ln)["run"]
        if not r:
            continue
        if r[0] == "fill":
            box = tuple(int(v) for v in r[1:7])
            block, filt, keep = r[7], None, False
            if len(r) > 8:
                if r[8] == "replace" and len(r) > 9:
                    filt = r[9]
                elif r[8] == "keep":
                    keep = True
                elif r[8] not in ("replace", "destroy"):
                    raise AuditError("a fill mode this audit cannot replay: %r" % ln)
            out.append((box, block, filt, keep))
        elif r[0] == "setblock":
            x, y, z = (int(v) for v in r[1:4])
            keep = len(r) > 5 and r[5] == "keep"
            out.append(((x, y, z, x, y, z), r[4], None, keep))
    return out


def replay(V, lines):
    for box, block, filt, keep in block_writes(lines):
        V.write(box, block, filt, keep)


class Graph:
    """Whole-block player positions over a replay: a position is a cell whose cell and the one above are not solid."""

    def __init__(self, V):
        st = V.st
        pas = st != SOLID
        pos = np.zeros_like(pas)
        pos[:, :-1, :] = pas[:, :-1, :] & pas[:, 1:, :]
        pos[0], pos[-1] = False, False
        pos[:, :1, :], pos[:, -3:, :] = False, False
        pos[:, :, 0], pos[:, :, -1] = False, False
        self.V = V
        self.pos = bytearray(pos.ravel().astype(np.uint8).tobytes())
        self.st = bytearray(st.ravel().tobytes())
        nx, ny, nz = st.shape
        self.DX, self.DY = ny * nz, nz

    def moves(self, f):
        st, pos, DX, DY = self.st, self.pos, self.DX, self.DY
        wet = st[f] == WATER
        if not wet and st[f - DY] != SOLID:
            return [f - DY] if pos[f - DY] else []                       # falling (into water too)
        out = []
        head = st[f + 2 * DY] != SOLID
        for d in (DX, -DX, 1, -1):
            n = f + d
            if pos[n]:
                out.append(n)
            elif head and st[n] == SOLID and pos[n + DY]:
                out.append(n + DY)                                         # a one-block step up (or out of water)
        for a, b in ((DX, 1), (DX, -1), (-DX, 1), (-DX, -1)):
            n = f + a + b
            if pos[n] and (pos[f + a] or pos[f + b]):
                out.append(n)                                              # a diagonal through an open corner
        if wet:
            if pos[f + DY]:
                out.append(f + DY)
            if pos[f - DY]:
                out.append(f - DY)
        return out

    def reach(self, starts):
        seen = bytearray(len(self.pos))
        stack = [f for f in starts if self.pos[f]]
        for f in stack:
            seen[f] = 1
        while stack:
            for n in self.moves(stack.pop()):
                if not seen[n]:
                    seen[n] = 1
                    stack.append(n)
        return seen

    def back(self, R, targets):
        """Of the reachable set R, the positions from which a target can be reached."""
        rev = {}
        members = [i for i, v in enumerate(R) if v]
        for f in members:
            for n in self.moves(f):
                rev.setdefault(n, []).append(f)
        ok = bytearray(len(R))
        stack = [f for f in targets if R[f]]
        for f in stack:
            ok[f] = 1
        while stack:
            for q in rev.get(stack.pop(), ()):
                if not ok[q]:
                    ok[q] = 1
                    stack.append(q)
        return members, ok

    def members(self, R):
        return [i for i, v in enumerate(R) if v]


def body_mask(G, R):
    """Boolean array of the cells occupied by a player at any position of R (feet and head)."""
    a = np.frombuffer(bytes(R), dtype=np.uint8).reshape(G.V.shape).astype(bool)
    b = a.copy()
    b[:, 1:, :] |= a[:, :-1, :]
    return b


def in_box(c, b):
    return b[0] <= c[0] <= b[3] and b[1] <= c[1] <= b[4] and b[2] <= c[2] <= b[5]


def pos_in_sel(c, b):
    """A player standing at cell c (feet) is selected by a dx volume covering cells b (hitbox 0.6 x 1.8)."""
    return b[0] <= c[0] <= b[3] and b[2] <= c[2] <= b[5] and b[1] - 1 <= c[1] <= b[4]


def box_contains(outer, inner):
    return all(outer[i] <= inner[i] for i in range(3)) and all(outer[i] >= inner[i] for i in range(3, 6))


def usable_from(G, click, w, h):
    """Flat positions from which an interaction entity at `click` (its summon point, width w, height h) is in reach and
    in sight."""
    V = G.V
    cx, cy, cz = click
    lo = (cx - w / 2, cy, cz - w / 2)
    hi = (cx + w / 2, cy + h, cz + w / 2)
    out = []
    for x in range(int(cx) - 5, int(cx) + 6):
        for y in range(int(cy) - 5, int(cy) + 5):
            for z in range(int(cz) - 5, int(cz) + 6):
                try:
                    f = V.flat(x, y, z)
                except Exception:
                    continue
                if not (0 <= f < len(G.pos)) or not G.pos[f]:
                    continue
                e = (x + 0.5, y + EYE, z + 0.5)
                p = tuple(min(max(e[i], lo[i]), hi[i]) for i in range(3))
                d = math.dist(e, p)
                if d > REACH:
                    continue
                n = max(1, int(d / 0.1))
                clear = True
                for k in range(1, n):
                    q = tuple(e[i] + (p[i] - e[i]) * k / n for i in range(3))
                    if V.at(int(math.floor(q[0])), int(math.floor(q[1])), int(math.floor(q[2]))) == SOLID:
                        clear = False
                        break
                if clear:
                    out.append(f)
    return out


# ================================================================================================ the report

class Report:
    def __init__(self):
        self.items = []

    def add(self, pid, ok, detail, cases=None, kind="property"):
        self.items.append({"id": pid, "kind": kind, "ok": bool(ok), "detail": detail, "cases": list(cases or [])[:12]})

    def get(self, pid):
        for it in self.items:
            if it["id"] == pid:
                return it
        raise KeyError(pid)

    def failed(self):
        return [it["id"] for it in self.items if it["kind"] == "property" and not it["ok"]]


# ================================================================================================ Kyogre

def kyogre(pack_dir, rep, ground=None):
    P = read_pack(pack_dir)
    fns, adv = P["fns"], P["adv"]
    doc = _j(DATA / "kyogre_cave.json")
    portals = _j(DATA / "portals.json")
    blackout = _j(DATA / "blackout.json")
    station = _j(DATA / "coldwater_station.json")
    dive_tag = portals["gates"]["dive"]["tag"]
    cg = calls(fns)

    def fn(name):
        fid = "%s/%s" % (KF, name)
        if fid not in fns:
            raise AuditError("the Kyogre pack has no %s" % fid)
        return fns[fid]

    # ---- which build functions run in the pocket: those a build step runs `in cobblers:pocket`
    pocket_fns = []
    for caller, _i, callee, ctx, _s in cg:
        if caller in P["build_fns"] and ctx["in"] == POCKET and callee in fns and block_writes(fns[callee]):
            pocket_fns.append(callee)
    pocket_fns = sorted(set(pocket_fns), key=lambda f: [int(n) if n.isdigit() else n for n in re.split(r"(\d+)", f)])
    overworld_fns = [f for f in P["build_fns"] if f not in pocket_fns and block_writes(fns[f])]
    if not pocket_fns:
        raise AuditError("no build function of the Kyogre pack runs in %s" % POCKET)

    # ---- the replay box: every pocket write, build and runtime
    runtime_writers = [f for f in fns if f not in P["build_fns"] and block_writes(fns[f])]
    boxes = [w[0] for f in pocket_fns + runtime_writers for w in block_writes(fns[f])]
    bb = (min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
          max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes))
    V0 = Vox(bb)
    for f in pocket_fns:
        replay(V0, fns[f])

    # ---- the states, replayed from the runtime functions
    lamps = sorted(f for f in fns if f.startswith(KF + "/click/lamp_"))
    slices = sorted(f for f in fns if re.match(re.escape(KF) + r"/drain/s_\d+$", f))
    S = {"built": V0}
    V = V0.copy()
    for f in lamps:
        replay(V, fns[f])
    S["lamps lit"] = V
    drain_states = []
    for f in slices:
        V = V.copy()
        replay(V, fns[f])
        drain_states.append((f.rsplit("/", 1)[1], V))
    V = V.copy()
    replay(V, fn("drain/done"))
    S["drained"] = V
    W = V.copy()
    replay(W, fn("ky/wake"))
    S["awake"] = W
    Rs = W.copy()
    replay(Rs, fn("reset_writes"))
    S["reset around a solver"] = Rs

    # ---- 7.1 the seal: four written cells along all six axes of every carved cell
    carved = (V0.st == AIR) | (V0.st == WATER)
    void = V0.st == VOID
    bad = np.zeros_like(carved)
    for ax in range(3):
        for sgn in (1, -1):
            for k in range(1, SHELL_MIN + 1):
                sh = np.roll(void, -sgn * k, axis=ax)
                bad |= carved & sh
    cases = [V0.xyz(int(f)) for f in np.flatnonzero(bad.ravel())[:6]]
    rep.add("kyogre.seal", not bad.any(),
            "%d carved cells have the void within %d along an axis (KYOGRE_CAVE.md 7.1); %d carved cells replayed, shell %s"
            % (int(bad.sum()), SHELL_MIN, int(carved.sum()), doc["shell"]["margin"]), cases)

    # ---- water stability: a written source with air or void beside or under it flows (every state)
    rc = doc["rooms"]["race"]
    src_box = rc["sources"]
    unstable = []
    for label, Vs in list(S.items()) + drain_states:
        w = Vs.st == WATER
        op = (Vs.st == AIR) | (Vs.st == VOID)
        hit = np.zeros_like(w)
        for ax, d in ((0, 1), (0, -1), (2, 1), (2, -1), (1, -1)):
            hit |= w & np.roll(op, -d, axis=ax)
        for f in np.flatnonzero(hit.ravel())[:400]:
            c = Vs.xyz(int(f))
            if not in_box(c, src_box):
                unstable.append("%s: %s" % (label, c))
                break
    rep.add("kyogre.water_still", not unstable,
            "every written water source is walled on its sides and floor in every replayed state (built, lamps lit, each of "
            "%d drain slices, drained, awake, reset), except the Race's declared sources %s" % (len(drain_states), src_box),
            unstable)

    # ---- the Race's stream: an over-approximated vanilla spread (no flow preference) stays in its channel and sump
    flow = race_flow(V0, src_box)
    xs0 = rc["x_start"]
    out_of = [c for c in flow if not (xs0 <= c[0] <= src_box[3] and rc["z"][0] <= c[2] <= rc["z"][1])]
    hub_floor = [c for c in flow if c[1] >= rc["standing0"] and c[0] < xs0 + 1]
    rep.add("kyogre.race_contained", not out_of and not hub_floor,
            "%d cells the Race's sources can flow into (spread 7, falls reset); every one inside x %d..%d, z %s, none on "
            "the hub's walking level" % (len(flow), xs0, src_box[3], rc["z"]), (out_of + hub_floor)[:8])

    # ---- reachability, state by state
    arrive = None
    for ln in fn("enter"):
        ctx = parse_exec(ln)
        if ctx["in"] == POCKET and ctx["run"][:1] == ["tp"]:
            arrive = tuple(int(math.floor(float(v))) for v in ctx["run"][2:5])
            enter_ctx = ctx
    if arrive is None:
        raise AuditError("enter has no tp into %s" % POCKET)

    clicks = {}
    for f in P["build_fns"]:
        for ln in fns[f]:
            m = re.search(r"summon minecraft:interaction (\S+) (\S+) (\S+) \{width:([\d.]+)f,height:([\d.]+)f.*Tags:\[(.*)\]", ln)
            if m and parse_exec(ln)["in"] == POCKET:
                tags = [t.strip('"') for t in m.group(6).split(",")]
                for t in tags:
                    if t.startswith("cobblers.kc.click.") and t.count(".") == 3:
                        clicks[t] = (float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)), float(m.group(5)))
    click_fn = {}
    for aid, a in adv.items():
        r = a.get("rewards", {}).get("function")
        s = json.dumps(a)
        for t in clicks:
            if '\\"%s\\"' % t in s and r:
                click_fn[t] = r
    # a way out: a click whose function runs `out` (a tp to the overworld) with no return before it
    exits = []
    for t, f in click_fn.items():
        for ln in fns.get(f, []):
            if ln == "function %s/out" % KF:
                exits.append(t)
                break
            ctx = parse_exec(ln)
            if ctx["returned"] or ctx["conds"]:
                break                                    # a condition or a return before `out`: gated, not a way out
    out_tp = [parse_exec(ln) for ln in fn("out") if parse_exec(ln)["run"][:1] == ["tp"]]
    rep.add("kyogre.ways_out_ungated",
            len(exits) >= 2 and all(c["in"] == "minecraft:overworld" and not c["conds"] for c in out_tp) and bool(out_tp),
            "%d clicks call `out` before any return or condition (%s); `out` tps to the overworld unconditionally"
            % (len(exits), ", ".join(sorted(e.rsplit(".", 1)[1] for e in exits))))

    graphs, reach = {}, {}
    for label in ("built", "drained", "awake"):
        G = Graph(S[label])
        graphs[label] = G
        reach[label] = G.reach([S[label].flat(*arrive)])
    Gr = Graph(S["reset around a solver"])
    graphs["reset around a solver"] = Gr
    reach["reset around a solver"] = Gr.reach(G.members(reach["awake"]))

    # 7.2: the Trench and the Basin are sealed until the puzzles are solved
    t = doc["rooms"]["trench"]
    hw = t["half_width"][0] + t["half_width"][1] + 1
    trench_box = (t["x"][0], t["floor"], int(t["centre_z"] - hw), t["x"][1], t["roof"], int(math.ceil(t["centre_z"] + hw)))
    basin_box = tuple(doc["kyogre"]["basin_box"])
    leak = [V0.xyz(f) for f in graphs["built"].members(reach["built"])
            if in_box(V0.xyz(f), trench_box) or in_box(V0.xyz(f), basin_box)]
    rep.add("kyogre.sealed_until_solved", not leak,
            "with the lamps unlit and the Tide Gate shut, no position in the Trench %s or the Basin %s is reachable from the "
            "arrival %s (%d positions reachable)" % (trench_box, basin_box, arrive, len(graphs["built"].members(reach["built"]))),
            leak[:6])

    def usable(label, tag):
        G = graphs[label]
        cx, cy, cz, w, h = clicks[tag]
        return [f for f in usable_from(G, (cx, cy, cz), w, h) if reach[label][f]]

    need = ["cobblers.kc.click.shrine", "cobblers.kc.click.pedestal_catchers", "cobblers.kc.click.arch_f"]
    missing = [t for t in need if t not in clicks or not usable("drained", t)]
    rep.add("kyogre.basin_reachable_when_solved", not missing,
            "with the lamps lit and the hall drained, the wake shrine, the catcher's pedestal and the Basin's way out are each "
            "in reach (%.1f) and sight of a reachable position" % REACH, missing)

    # REVIEW 87 as a proof: from every reachable position, in every state, a way out is reachable
    lost = []
    for label in ("built", "drained", "awake", "reset around a solver"):
        G, R = graphs[label], reach[label]
        targets = []
        for e in exits:
            cx, cy, cz, w, h = clicks[e]
            targets += usable_from(G, (cx, cy, cz), w, h)
        members, ok = G.back(R, targets)
        bad_ = [f for f in members if not ok[f]]
        if bad_:
            lost.append("%s: %d of %d positions reach no way out, e.g. %s" % (label, len(bad_), len(members), G.V.xyz(bad_[0])))
    rep.add("kyogre.always_a_way_out", not lost,
            "every position reachable in the built, drained, awake and reset-around-a-solver states reaches a position from "
            "which a way-out click is in reach", lost)

    union = None
    for label in ("built", "drained", "awake", "reset around a solver"):
        m = body_mask(graphs[label], reach[label])
        union = m if union is None else (union | m)

    # the sweeps: everybody the cave can hold is in the keeper's here/eject box; nobody it can hold is in the rescue box
    tick = fn("tick")
    here_box = None
    for ln in tick:
        ctx = parse_exec(ln)
        if ctx["run"][:1] == ["tag"] and ctx["run"][-2:] == ["add", "cobblers.kc.here"] and ctx["in"] == POCKET:
            here_box = Sel(ctx["run"][1]).box()
    eject_box = rescue_box = eject_pred = None
    for ln in fn("occupied"):
        ctx = parse_exec(ln)
        if ctx["run"][:2] == ["function", KF + "/eject"]:
            eject_box = ctx["as"].box()
            eject_pred = [c[2] for c in ctx["conds"] if c[0] == "unless" and c[1] == "entity"]
        if ctx["run"][:2] == ["function", KF + "/rescue"]:
            rescue_box = ctx["as"].box()
    held = [V0.xyz(int(f)) for f in np.flatnonzero(union.ravel())]
    miss_here = [c for c in held if here_box is None or not in_box(c, here_box)]
    miss_eject = [c for c in held if eject_box is None or not in_box(c, eject_box)]
    in_rescue = [c for c in held if rescue_box is not None and in_box(c, rescue_box)]
    rep.add("kyogre.sweeps_cover_the_cave", not miss_here and not miss_eject and not in_rescue and rescue_box is not None,
            "%d cells a player can occupy in any state: all inside the keeper's here box %s and eject box %s, none inside "
            "the rescue box %s" % (len(held), here_box, eject_box, rescue_box), (miss_here + miss_eject + in_rescue)[:6])

    # 7.3 no trap: a blocking write onto a cell a player can occupy runs only under a no-player guard in the pocket
    def guards(fid, need_box, seen=()):
        """True when every call path into fid passes a line that refuses to run with a player in need_box."""
        cs = callers_of(cg, fid)
        if not cs or fid in seen:
            return False
        for caller, i, _callee, ctx, _s in cs:
            if line_guards(fns[caller], i, ctx, need_box):
                continue
            if not guards(caller, need_box, seen + (fid,)):
                return False
        return True

    def line_guards(lines, i, ctx, need_box):
        for c in ctx["conds"]:
            if c[0] != "unless" or c[1] != "entity" or c[2].kind != "@a":
                continue
            b = c[2].box()
            if b is not None and c[4] == POCKET and box_contains(b, need_box):
                return True
            for tg in c[2].tags():
                for j in range(i):
                    cj = parse_exec(lines[j])
                    if (cj["run"][:1] == ["tag"] and cj["run"][-2:] == ["add", tg] and cj["in"] == POCKET
                            and Sel(cj["run"][1]).box() is not None and box_contains(Sel(cj["run"][1]).box(), need_box)
                            and any(parse_exec(lines[k])["run"] == ["tag", "@a", "remove", tg] for k in range(j))):
                        return True
        return False

    unguarded, checked = [], 0
    for f in runtime_writers:
        for box, block, filt, keep in block_writes(fns[f]):
            if base(block) in ("minecraft:air",):
                continue
            s = V0.sl(box)
            if not union[s].any():
                continue
            checked += 1
            if not guards(f, box):
                unguarded.append("%s writes %s over %s, where a player can stand, with no no-player guard" % (f, base(block), box))
    rep.add("kyogre.no_write_over_a_player", not unguarded,
            "%d runtime writes of a blocking block or water cover cells a player can occupy; each runs only past a line, in "
            "%s, that refuses with a player in a box containing the write (KYOGRE_CAVE.md 7.3)" % (checked, POCKET), unguarded)

    # the cage: closing it never writes over a cell reachable while it stands closed (online or not)
    close_w = [w for w in block_writes(fn("ky/close")) if base(w[1]) == "minecraft:barrier"]
    closed_body = body_mask(graphs["drained"], reach["drained"]) | body_mask(graphs["built"], reach["built"])
    over = []
    for w in close_w:
        s = V0.sl(w[0])
        sub = closed_body[s]
        if sub.any():
            i, j, k = [int(v[0]) for v in np.nonzero(sub)]
            over.append((s[0].start + i + V0.o[0], s[1].start + j + V0.o[1], s[2].start + k + V0.o[2]))
    rep.add("kyogre.cage_closes_only_on_its_own_cells", bool(close_w) and not over,
            "the cage's barrier fill %s covers no cell a player can occupy while the cage stands closed"
            % ([w[0] for w in close_w],), over)

    # KYOGRE_CAVE.md section 3: the barrier "encloses only the sleeper's cell in the pool, never a walkable or swimmable cell
    # a player can occupy". The guard sees only ONLINE players, so a player who logs out on the dais is closed in.
    awake_body = body_mask(graphs["awake"], reach["awake"])
    walk = []
    for w in close_w:
        sub = awake_body[V0.sl(w[0])]
        walk.append(int(sub.sum()))
    rep.add("kyogre.cage_never_encloses_a_walkable_cell", bool(close_w) and sum(walk) == 0,
            "with Kyogre awake (cage open) %d cells of the cage's barrier fill are cells a player can occupy; the close is "
            "guarded by `unless entity @a[...]`, which sees online players only, so a player who logs out there is "
            "filled in with barrier when it closes" % sum(walk),
            ["cage %s" % (w[0],) for w in close_w] if sum(walk) else [])

    # 7.5 the gate: the tp into the pocket carries the dive tag, gym8_cleared and the attunement; the eject reads the same
    att = doc["gate"]["advancement"]
    def pred_of(conds):
        tags, advs = set(), {}
        for c in conds:
            if c[0] == "if" and c[1] == "entity" and c[2].kind == "@s":
                tags |= set(c[2].tags())
                advs.update(c[2].advancements())
        return tags, advs
    tg_, ad_ = pred_of(enter_ctx["conds"])
    gate_ok = dive_tag in tg_ and ad_.get(KY_FLAG) == "true" and ad_.get(att) == "true"
    ej_ok = bool(eject_pred) and dive_tag in eject_pred[0].tags() and eject_pred[0].advancements().get(KY_FLAG) == "true" \
        and eject_pred[0].advancements().get(att) == "true"
    # every other tp landing inside the cave: only the rescue, whose callers select players already in the pocket box
    stray = []
    for f, lines in fns.items():
        for ln in lines:
            ctx = parse_exec(ln)
            if ctx["run"][:1] != ["tp"] or len(ctx["run"]) < 5:
                continue
            try:
                c = tuple(int(math.floor(float(v))) for v in ctx["run"][2:5])
            except ValueError:
                continue
            if here_box and in_box(c, here_box) and ctx is not enter_ctx and ln not in fn("enter"):
                if f.startswith(KF + "/ky/") or f.startswith(KF + "/sp"):
                    continue                                    # a Pokemon held on its spot
                cs = callers_of(cg, f)
                if not cs or not all(cc[3]["in"] == POCKET and cc[3]["as"] is not None and cc[3]["as"].box() is not None
                                     and here_box and box_contains(here_box, cc[3]["as"].box()) for cc in cs):
                    stray.append("%s: %s" % (f, ln[:80]))
    # the attunement is granted only by `attune`, which only Calder's topic the_key runs, on gym8_cleared and two_sleepers
    granters = [f for f, lines in fns.items() for ln in lines if "advancement grant" in ln and att in ln]
    runners = []
    for r in station.get("researchers", []):
        for tp in r.get("topics", []):
            for e in tp.get("effects", []):
                if e.get("kind") == "function" and e.get("function") == KF + "/attune":
                    runners.append((r.get("id"), tp.get("id"), json.dumps(tp.get("visible_when"))))
    topic_ok = bool(runners) and all("gym8_cleared" in v and "two_sleepers" in v for _r, _t, v in runners)
    rep.add("kyogre.gate", gate_ok and ej_ok and not stray and granters == [KF + "/attune"] and topic_ok,
            "the crossing's tp into %s carries tag=%s, %s and %s on its own line; the keeper's eject reads the same three; "
            "no other tp lands in the cave from outside it; %s is granted only by attune, run only by the station topic(s) %s "
            "on gym8_cleared and two_sleepers (KYOGRE_CAVE.md 1 stage 3, 9 answers 2-3)"
            % (POCKET, dive_tag, KY_FLAG, att, att, [(r, t) for r, t, _v in runners]),
            ([] if gate_ok else ["tp predicate %s %s" % (sorted(tg_), ad_)]) + ([] if ej_ok else ["eject predicate"]) + stray
            + ([] if granters == [KF + "/attune"] else ["granted by %s" % granters]) + ([] if topic_ok else ["topic %s" % runners]))

    weather = [f for f, lines in fns.items() for ln in lines if parse_exec(ln)["run"][:1] == ["weather"]]
    rep.add("kyogre.no_overworld_rain", not weather,
            "no function runs `weather` (the owner, KYOGRE_CAVE.md 9 answer 4: no overworld rain)", weather)

    # 7.5 the wake carries caught=false on every path; the catcher's pedestal requires the catch
    caught = doc["kyogre"]["caught_advancement"]
    rep.add("kyogre.wake_needs_no_catch", requires_false(fns, cg, KF + "/ky/wake", caught),
            "every path into ky/wake (barrier removed, Kyogre woken, met granted) holds %s=false for the waker" % caught)
    ped = fns.get(KF + "/click/pedestal_catchers", [])
    gives = [i for i, ln in enumerate(ped) if " give @s " in ln]
    need_adv = [caught] + [r for p in doc["pedestals"]["list"] if p["id"] == "catchers" for r in p["requires"]]
    held_ = set()
    for ln in ped[:gives[0] if gives else 0]:
        ctx = parse_exec(ln)
        for c in ctx["conds"]:
            if c[0] == "unless" and c[1] == "entity" and c[2].kind == "@s" and ctx["returned"]:
                held_ |= {k for k, v in c[2].advancements().items() if v == "true"}
    rep.add("kyogre.catchers_pedestal_needs_the_catch", bool(gives) and all(a in held_ for a in need_adv),
            "the catcher's pedestal returns before any give unless the clicker holds %s" % need_adv, sorted(set(need_adv) - held_))

    # Kyogre is only ever put where a player can reach it (once awake), inside its cage
    spots = []
    for f in fns:
        if not f.startswith(KF + "/ky/"):
            continue
        for ln in fns[f]:
            r = parse_exec(ln)["run"]
            if r[:2] == ["tp", "@s"]:
                spots.append((f, tuple(int(math.floor(float(v))) for v in r[2:5])))
            if r[:2] == ["function", KF + "/spawn_at"]:
                m = re.search(r'x:"?([\d.]+)"?,y:"?([\d.]+)"?,z:"?([\d.]+)"?', ln)
                spots.append((f, (int(float(m.group(1))), int(float(m.group(2))), int(float(m.group(3))))))
    Ga = graphs["awake"]
    far = [s for s in spots if not reach["awake"][S["awake"].flat(*s[1])]]
    caged = all(any(in_box(s[1], w[0]) for w in close_w) for s in spots)
    shrine_ok = bool(usable("drained", "cobblers.kc.click.shrine"))
    rep.add("kyogre.kyogre_is_reachable", bool(spots) and not far and caged and shrine_ok,
            "%d places the keeper puts Kyogre (spawn and tp): each a position reachable once it is awake, each inside the "
            "cage's fill; the wake shrine is in reach while it sleeps" % len(spots), far)

    # 7.7 every set piece spawns into water or onto a ledge a player can reach in some state
    sp_bad, nsp = [], 0
    for f in fns:
        if not f.startswith(KF + "/sp/") or f.endswith("/pass"):
            continue
        for ln in fns[f]:
            if "/spawn_at " not in ln:
                continue
            nsp += 1
            m = re.search(r'x:"?([\d.]+)"?,y:"?([\d.]+)"?,z:"?([\d.]+)"?', ln)
            c = (int(float(m.group(1))), int(float(m.group(2))), int(float(m.group(3))))
            here = [lab for lab in ("built", "drained") if reach[lab][S[lab].flat(*c)]]
            st_ = S["drained"].at(*c)
            ledge = st_ == AIR and S["drained"].at(c[0], c[1] - 1, c[2]) == SOLID
            if not here or not (st_ == WATER or ledge):
                sp_bad.append("%s at %s (%s)" % (f.rsplit("/", 1)[1], c, "unreachable" if not here else "not water or a ledge"))
    rep.add("kyogre.set_pieces_are_reachable", nsp > 0 and not sp_bad,
            "%d set-piece spawns, each into water or onto a ledge reachable in the built or solved cave" % nsp, sp_bad)

    # air: the ladder's depth under every roof flooded to the top (contract KC2), the dry alcoves, the breath gap
    deep = blackout["water"]["deep_blocks"]
    Gd = graphs["drained"]
    shallow = set()
    for lab in ("built", "drained"):
        G = graphs[lab]
        Vs = S[lab]
        for f in G.members(reach[lab]):
            if G.st[f] != WATER or G.st[f - G.DY] != SOLID:
                continue
            h, g = 0, f
            while G.st[g] == WATER:
                h += 1
                g += G.DY
            if G.st[g] == SOLID and h < deep + 2:
                c = Vs.xyz(f)
                shallow.add((c[0], c[2], c[1], h))
    cols_ = sorted({(c[0], c[1]) for c in shallow})
    ext = (min(c[0] for c in cols_), min(c[1] for c in cols_), max(c[0] for c in cols_), max(c[1] for c in cols_)) if cols_ else None
    rep.add("kyogre.flooded_passages_hold_the_ladder", not shallow,
            "every reachable water column flooded floor to roof holds at least data/blackout.json water.deep_blocks + 2 = "
            "%d cells (contract KC2: under a lower roof Dive's air gives nothing); %d columns do not, x/z extent %s"
            % (deep + 2, len(cols_), ext), ["(x %d, z %d) floor y%d, %d of water under rock" % c for c in sorted(shallow)[:8]])
    sb = doc["rooms"]["sounding"]["box"]
    Gb = graphs["built"]
    dry = []
    for L in doc["rooms"]["sounding"]["alcoves"]:
        ok = any(c[1] == L and c[0] < sb[0] and sb[2] <= c[2] <= sb[5] and V0.at(*c) == AIR
                 and V0.at(c[0], c[1] + 1, c[2]) == AIR for c in (V0.xyz(f) for f in Gb.members(reach["built"])
                                                                  if sb[0] - 6 <= V0.xyz(f)[0] < sb[0] and V0.xyz(f)[1] == L))
        if not ok:
            dry.append(L)
    rep.add("kyogre.sounding_alcoves_are_dry", not dry,
            "a reachable dry standing place at each alcove level %s, west of the Sounding (KYOGRE_CAVE.md 3 room B)"
            % doc["rooms"]["sounding"]["alcoves"], dry)
    gap = breath_gap(Gb, reach["built"])
    rep.add("kyogre.breath_gap", True,
            "the longest run of moves a player must make with their eyes under water to reach air, over every position "
            "reachable in the built cave: %d moves (vanilla air lasts 15 s; a player without Dive is meant to use the "
            "alcoves, KYOGRE_CAVE.md 3 puzzle 1). Measured, not judged" % gap, kind="measurement")

    # spawn conditions: no written block is in data/spawn_blocks.json (the data's own claim)
    # (the water itself is the design's, KYOGRE_CAVE.md 3; it is recorded below as a measurement, never hidden)
    sbd = _j(DATA / "spawn_blocks.json")["blocks"]
    written = {base(w[1]) for f in fns for w in block_writes(fns[f])}
    hit = sorted((written - {"minecraft:water"}) & set(sbd))
    rep.add("kyogre.no_spawn_condition_blocks", not hit,
            "%d distinct blocks written by both packs (cave, runtime and reef); apart from the design's water, none is a key "
            "of data/spawn_blocks.json (data/kyogre_cave.json shell.skin_why's claim)" % len(written), hit)
    if "minecraft:water" in written:
        rep.add("kyogre.water_is_a_spawn_condition", True,
                "the cave writes minecraft:water, which data/spawn_blocks.json names for %d spawn entries "
                "(neededNearbyBlocks); allowed by contract C4, and whether any pool matches the pocket's void biome is "
                "KYOGRE_CAVE.md E1, not verified" % len(sbd.get("minecraft:water", [])), kind="measurement")

    # the overworld side: the reef sits on the heightmap's ground, one contiguous run per column
    if ground is not None and overworld_fns:
        cols = {}
        for f in overworld_fns:
            for box, block, _filt, _keep in block_writes(fns[f]):
                for x in range(box[0], box[3] + 1):
                    for z in range(box[2], box[5] + 1):
                        cols.setdefault((x, z), set()).update(range(box[1], box[4] + 1))
        off = []
        for (x, z), ys in cols.items():
            g = ground(x, z)
            if min(ys) != g + 1 or len(ys) != max(ys) - min(ys) + 1:
                off.append((x, z, g, min(ys), max(ys)))
        rep.add("kyogre.reef_sits_on_heightmap_ground", bool(cols) and not off,
                "%d reef columns in the overworld: each a contiguous run starting at round(ground) + 1 (tools/ground.py)"
                % len(cols), off[:8])
        st_ = [parse_exec(ln)["run"] for ln in fn("out") if parse_exec(ln)["run"][:1] == ["tp"]][0]
        sx, sy, sz = (int(math.floor(float(v))) for v in st_[2:5])
        rep.add("kyogre.return_point_height", True,
                "the way back lands on the sea floor at (%d, %d, %d): %+d against round(ground) + 1 = %d (the arch's apron, "
                "Coldwater's, is not replayed here)" % (sx, sy, sz, sy - ground(sx, sz) - 1, ground(sx, sz) + 1),
                kind="measurement")

    # kills: KC1, every kill line spares a guardian; Kyogre's bind carries the blackout's exempt tag
    def may_be_pokemon(tok):
        if not tok.startswith("@e"):
            return tok.startswith("@s")
        ty = Sel(tok).get("type")
        return not ty or "cobblemon:pokemon" in ty
    kills = [(f, ln) for f, lines in fns.items() for ln in lines
             if parse_exec(ln)["run"][:1] == ["kill"] and may_be_pokemon(parse_exec(ln)["run"][1])
             and ("!" + GUARDIAN) not in ln]
    exempt = blackout["claims"]["exempt_tag"]
    bind_ok = any(ln == "tag @s add %s" % exempt for ln in fns.get(KF + "/ky/bind", []))
    rep.add("kyogre.kills_spare_guardians", not kills and bind_ok,
            "no kill line lacks tag=!%s, and ky/bind adds %s (contract KC1)" % (GUARDIAN, exempt), [k[0] for k in kills])
    return rep


def requires_false(fns, cg, fid, advancement, seen=()):
    """Every call path into fid holds advancement=false for its executor (@s): the function returns on it first, or every
    caller line keeps the executor and tests it (or follows a line that returned on it), or the caller requires it."""
    lines = fns.get(fid, [])
    for ln in lines:
        ctx = parse_exec(ln)
        if ctx["returned"] and any(c[0] == "if" and c[1] == "entity" and c[2].kind == "@s"
                                   and c[2].advancements().get(advancement) == "true" for c in ctx["conds"]):
            return True
        if not ctx["conds"] or not ctx["returned"]:
            break
    cs = callers_of(cg, fid)
    if not cs or fid in seen:
        return False
    for caller, i, _c, ctx, sched in cs:
        if sched or (ctx["as"] is not None and ctx["as"].kind != "@s"):
            return False
        if any(c[0] == "if" and c[1] == "entity" and c[2].kind == "@s" and c[2].advancements().get(advancement) == "false"
               for c in ctx["conds"]):
            continue
        pre = False
        for ln in fns[caller][:i]:
            cj = parse_exec(ln)
            if cj["returned"] and cj["as"] is None and any(
                    c[0] == "if" and c[1] == "entity" and c[2].kind == "@s" and c[2].advancements().get(advancement) == "true"
                    for c in cj["conds"]):
                pre = True
        if pre:
            continue
        if not requires_false(fns, cg, caller, advancement, seen + (fid,)):
            return False
    return True


def race_flow(V, src_box):
    """{(x, y, z)} a vanilla stream from the sources can wet: spread 7 on a floor, a fall resets it; no flow preference,
    so a superset of where the water really goes."""
    best = {}
    q = deque()
    for x in range(src_box[0], src_box[3] + 1):
        for y in range(src_box[1], src_box[4] + 1):
            for z in range(src_box[2], src_box[5] + 1):
                q.append(((x, y, z), 8))
    while q:
        c, lvl = q.popleft()
        if best.get(c, -1) >= lvl:
            continue
        best[c] = lvl
        x, y, z = c
        below = V.at(x, y - 1, z)
        if below in (AIR, VOID):
            q.append(((x, y - 1, z), 8))
            continue
        if lvl <= 1:
            continue
        for n in ((x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)):
            if V.at(*n) in (AIR, VOID):
                q.append((n, lvl - 1))
    return set(best)


def breath_gap(G, R):
    """The largest number of moves, over reachable positions with the eyes in water, to the nearest position whose eyes
    are in air."""
    rev = {}
    members = G.members(R)
    for f in members:
        for n in G.moves(f):
            rev.setdefault(n, []).append(f)
    dist = {}
    q = deque()
    for f in members:
        if G.st[f + G.DY] != WATER:
            dist[f] = 0
            q.append(f)
    while q:
        f = q.popleft()
        for p in rev.get(f, ()):
            if p not in dist:
                dist[p] = dist[f] + 1
                q.append(p)
    return max(dist.values()) if dist else 0


# ================================================================================================ Rayquaza

PASSABLE = ("minecraft:air", "minecraft:cave_air", "minecraft:short_grass", "minecraft:fern", "minecraft:moss_carpet",
            "minecraft:hanging_roots", "minecraft:tall_grass")


def profile(block):
    """The half-block collision of a block: (lower half, upper half, the lower half of the cell above)."""
    b = base(block)
    if b in PASSABLE or b.endswith("_sign") or b.endswith("_carpet"):
        return (0, 0, 0)
    if b.endswith("_slab"):
        if "type=top" in block:
            return (0, 1, 0)
        if "type=double" in block:
            return (1, 1, 0)
        return (1, 0, 0)
    if b.endswith("_wall") or b.endswith("_fence") or b.endswith("_fence_gate"):
        return (1, 1, 1)                             # 1.5 high: never stepped or jumped onto
    return (1, 1, 0)                                 # a full block (a lantern too: an obstacle, never a floor it is not)


class Sky:
    """Half-block columns: the heightmap's terrain (round(ground) and below solid) under the build's writes."""

    def __init__(self, cells, ground, ybase):
        self.cells = cells
        self.g = ground
        self.yb = ybase
        self.cache = {}
        self.terrain_top = {}

    def col(self, x, z):
        k = (x, z)
        c = self.cache.get(k)
        if c is not None:
            return c
        gy = self.g(x, z)
        top = 2 * (gy - self.yb) + 1
        bits = (1 << (top + 1)) - 1 if top >= 0 else 0
        ups = []
        for y, block in sorted(self.cells.get(k, {}).items()):
            lo, hi, up = profile(block)
            i = 2 * (y - self.yb)
            bits &= ~(3 << i)
            bits |= (lo << i) | (hi << (i + 1))
            if up:
                ups.append(i + 2)
        for i in ups:                                # a wall's collision reaches into the cell above, whatever is there
            bits |= 1 << i
        self.cache[k] = bits
        self.terrain_top[k] = top
        return bits


def _free(c, a, b):
    if a < 0:
        return False
    return (c >> a) & ((1 << (b - a + 1)) - 1) == 0


def _set(c, i):
    return i >= 0 and (c >> i) & 1 == 1


STAND, SNEAK = 4, 3       # the player's height in half-blocks: 1.8 standing, 1.5 sneaking (vanilla), each rounded up


def sky_moves(S, p, jump=True, sneak_ok=True):
    """[(dest, kind, fall blocks)] from a state (x, z, h, hh): h the standing height in half-blocks, hh the player's
    height (STAND or SNEAK). A step up of half a block needs the rise clear over the column left behind as well (vanilla
    Entity.collide lifts the box in place before it moves); a sneaking player never walks off an edge deeper than half a
    block (vanilla backs off the edge)."""
    x, z, h, hh = p
    o = S.col(x, z)
    out = []
    if sneak_ok:
        other = SNEAK if hh == STAND else STAND
        if _free(o, h, h + other - 1):
            out.append(((x, z, h, other), "stance", 0))
    nbrs = [(x + 1, z, None), (x - 1, z, None), (x, z + 1, None), (x, z - 1, None)]
    for a, b in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        nbrs.append((x + a, z + b, ((x + a, z), (x, z + b))))
    for nx, nz, corner in nbrs:
        c = S.col(nx, nz)
        cands = []
        if _free(c, h, h + hh - 1):
            if _set(c, h - 1):
                cands.append((h, "walk", 0))
            else:
                s = (c & ((1 << h) - 1)).bit_length() - 1
                if hh == STAND or h - (s + 1) <= 1:
                    cands.append((s + 1, "fall", (h - s - 1) / 2.0))
        elif _set(c, h) and _free(c, h + 1, h + hh) and _free(o, h + hh, h + hh):
            cands.append((h + 1, "step", 0))
        elif jump and _set(c, h + 1) and _free(c, h + 2, h + hh + 1) and _free(o, h + hh, h + hh + 2):
            cands.append((h + 2, "jump", 0))
        for nh, kind, fall in cands:
            if corner is not None:
                lo, hi = min(h, nh), max(h, nh) + hh - 1
                if not any(_free(S.col(cx, cz), lo, hi) for cx, cz in corner):
                    continue
            out.append(((nx, nz, nh, hh), kind, fall))
    return out


def fall_ticks_distance(ticks):
    """Vanilla free fall from rest: blocks fallen after `ticks` (position += v, then v = (v - 0.08) * 0.98)."""
    v, d = 0.0, 0.0
    for _ in range(ticks):
        d -= v
        v = (v - 0.08) * 0.98
    return d


def rayquaza(pack_dir, rep, ground):
    P = read_pack(pack_dir)
    fns = P["fns"]
    spec = _j(DATA / "rayquaza_sky.json")
    cg = calls(fns)

    def fn(name):
        fid = "%s/%s" % (RF, name)
        if fid not in fns:
            raise AuditError("the Rayquaza pack has no %s" % fid)
        return fns[fid]

    OKt, FRESHt = None, None
    # ---- the gate: the tag every use reads, recomputed from the three advancements
    q = fn("qualify")
    adds = [(i, parse_exec(ln)) for i, ln in enumerate(q) if parse_exec(ln)["run"][:1] == ["tag"]]
    removes = {tuple(c["run"][1:]) for _i, c in adds if c["run"][2:3] == ["remove"]}
    gate_cases = []
    for i, c in adds:
        r = c["run"]
        if r[2] != "add":
            continue
        s = Sel(r[1])
        a = s.advancements()
        if not s.tags() and set(a) == set(RAY_GATE) and all(v == "true" for v in a.values()):
            OKt = r[3]
        elif s.tags():
            FRESHt = (r[3], s)
    caught_adv = "cobblers:legendary/rayquaza/caught"
    fresh_ok = bool(FRESHt) and OKt in FRESHt[1].tags() and FRESHt[1].advancements() == {caught_adv: "false"}
    if not OKt:
        gate_cases.append("no tag is added for exactly %s=true: %s" % (list(RAY_GATE), [c["run"] for _i, c in adds]))
    if OKt and ("@a", "remove", OKt) not in removes:
        gate_cases.append("%s is never cleared before it is recomputed" % OKt)
    if not fresh_ok:
        gate_cases.append("the not-yet-caught tag is not %s plus %s=false" % (OKt, caught_adv))
    FRESH = FRESHt[0] if FRESHt else None
    if FRESH and ("@a", "remove", FRESH) not in removes:
        gate_cases.append("%s is never cleared before it is recomputed" % FRESH)

    def qualified_first(fid, upto):
        return any(ln == "function %s/qualify" % RF for ln in fns[fid][:upto])

    # every use: cross (the arch), spawn, wake, met
    for callee, tag in (("cross", OKt), ("met", OKt)):
        for caller, i, _c, ctx, _s in callers_of(cg, "%s/%s" % (RF, callee)):
            if ctx["as"] is None or tag not in ctx["as"].tags() or not qualified_first(caller, i):
                gate_cases.append("%s runs %s without %s freshly computed: %s" % (caller, callee, tag, fns[caller][i][:90]))
    for caller, i, _c, ctx, _s in callers_of(cg, "%s/spawn" % RF):
        guarded = any(parse_exec(ln)["returned"] and any(c[0] == "unless" and c[1] == "entity" and FRESH in c[2].tags()
                                                           for c in parse_exec(ln)["conds"]) for ln in fns[caller][:i])
        if not guarded or not qualified_first(caller, i):
            gate_cases.append("%s spawns without a %s player near" % (caller, FRESH))
    for caller, i, _c, ctx, _s in callers_of(cg, "%s/wake" % RF):
        cs = ctx["conds"]
        has_fresh = any(c[0] == "if" and c[1] == "entity" and FRESH in c[2].tags() for c in cs)
        no_stranger = any(c[0] == "unless" and c[1] == "entity" and ("!" + str(OKt)) in c[2].tags() for c in cs)
        if not (has_fresh and no_stranger):
            gate_cases.append("%s wakes without a %s player and no stranger on the crown" % (caller, FRESH))
    tp_island = []
    icx, icz, top_y = spec["island"]["centre"]["x"], spec["island"]["centre"]["z"], spec["island"]["top_y"]
    for f, lines in fns.items():
        for ln in lines:
            r = parse_exec(ln)["run"]
            if r[:2] == ["tp", "@s"] and len(r) >= 5 and float(r[3]) >= top_y - spec["island"]["depth_max"] \
                    and abs(float(r[2]) - icx) <= spec["island"]["half_x"] + 2 and abs(float(r[4]) - icz) <= spec["island"]["half_z"] + 2:
                if f not in ("%s/cross" % RF, "%s/hold" % RF, "%s/settle" % RF, "%s/bind" % RF):
                    tp_island.append(f)
    if tp_island:
        gate_cases.append("tps onto the island outside cross: %s" % tp_island)
    rep.add("rayquaza.gate", not gate_cases,
            "the arch's crossing, the spawn, the wake and the met grant each read a tag recomputed in the same function from "
            "exactly %s (contract C26); the spawn and the wake add %s=false" % (list(RAY_GATE), caught_adv), gate_cases)

    # ---- C27: no selector that acts on a Pokemon can reach a guardian
    ctxs = {f: set() for f in fns}
    roots = [f for f in fns if not callers_of(cg, f)]
    for f in roots:
        ctxs[f].add("none")
    changed = True
    while changed:
        changed = False
        for caller, _i, callee, ctx, sched in cg:
            if callee not in ctxs:
                continue
            if sched:
                new = {"none"}
            elif ctx["as"] is not None and ctx["as"].kind != "@s":
                s = ctx["as"]
                new = {("pokemon_safe" if s.excludes_guardian() else "pokemon_unsafe") if s.is_pokemon() else "player"}
            else:
                new = set(ctxs[caller])
            if not new <= ctxs[callee]:
                ctxs[callee] |= new
                changed = True
    acting = ("tp", "kill", "data", "tag", "effect")
    viol = []
    for f, lines in fns.items():
        for i, ln in enumerate(lines):
            ctx = parse_exec(ln)
            r = ctx["run"]
            if not r or r[0] not in acting:
                continue
            target = r[2] if r[0] == "data" and len(r) > 2 else (r[1] if len(r) > 1 else "")
            if r[0] == "effect":
                target = r[2] if len(r) > 2 else ""
            if target.startswith("@e"):
                s = Sel(target)
                if s.is_pokemon() and not s.excludes_guardian():
                    viol.append("%s: %s" % (f, ln[:90]))
            elif target.startswith("@s") and "pokemon_unsafe" in ctxs[f]:
                if not bind_dominated(fns, cg, f, OKt):
                    viol.append("%s acts on @s, which a guardian can be: %s" % (f, ln[:70]))
    rep.add("rayquaza.keeper_never_touches_a_guardian", not viol,
            "every tp, kill, data merge, tag or effect on a Pokemon, directly or through the function it runs, comes through "
            "a selector carrying tag=!%s; bind's spawn-side selector is accepted only because the keep line before it "
            "returns while a guardian of the species stands within its reach of the same spot (contract C27)" % GUARDIAN,
            sorted(set(viol)))

    # ---- the End's shiny Rayquaza is overridden empty at its own path
    up = spec["upstream_neutralised"]
    body = P["other"].get(up["path"])
    if body is None:
        fid = up["function"]
        body = "\n".join(fns.get(fid, ["MISSING"]))
    rep.add("rayquaza.end_spawn_overridden_empty", body is not None and not any(
        ln.strip() and not ln.strip().startswith("#") for ln in body.splitlines()),
            "%s ships at %s with no command (the owner, KYOGRE_CAVE.md 9 answer 5)" % (up["function"], up["path"]))

    # ---- the level
    lv = [ln for ln in fn("spawn_at") if "spawnpokemonat" in ln]
    rep.add("rayquaza.level", len(lv) == 1 and re.search(r"\brayquaza\b.*\blevel=%d\b" % spec["occupant"]["level"], lv[0]) is not None,
            "the only spawn line spawns rayquaza at level=%d (KYOGRE_CAVE.md 9 answer 6)" % spec["occupant"]["level"], lv)

    # ---- spawn conditions
    sb_ = set(_j(DATA / "spawn_blocks.json")["blocks"])
    writes = [w for f in P["build_fns"] for w in block_writes(fns[f])]
    hit = sorted({base(w[1]) for w in writes} & sb_)
    rep.add("rayquaza.no_spawn_condition_blocks", not hit,
            "%d distinct blocks written; none is a key of data/spawn_blocks.json" % len({base(w[1]) for w in writes}), hit)

    # ---- geometry: the walker over the replayed blocks and the heightmap
    cells = {}
    for box, block, filt, keep in writes:
        if filt or keep:
            raise AuditError("a filtered write in the Rayquaza build: %s" % (box,))
        for x in range(box[0], box[3] + 1):
            for z in range(box[2], box[5] + 1):
                col = cells.setdefault((x, z), {})
                for y in range(box[1], box[4] + 1):
                    col[y] = block
    ybase = min(min(c) for c in cells.values()) - 40
    S = Sky(cells, ground, ybase)

    def one_tp(name):
        r = [parse_exec(ln)["run"] for ln in fn(name) if parse_exec(ln)["run"][:2] == ["tp", "@s"]][0]
        return tuple(int(math.floor(float(v))) for v in r[2:5])

    def sel_box_of(name, callee):
        for ln in fn(name):
            ctx = parse_exec(ln)
            if ctx["run"][:2] == ["function", "%s/%s" % (RF, callee)] and ctx["as"] is not None:
                return ctx["as"].box()
        raise AuditError("%s never runs %s" % (name, callee))

    landing = one_tp("cross")
    ret = one_tp("return")
    recess = sel_box_of("island", "return")
    door = sel_box_of("arch", "cross")
    rescue = None
    for ln in fn("island"):
        r = parse_exec(ln)["run"]
        if r[:2] == ["effect", "give"] and "slow_falling" in ln:
            rescue = Sel(r[2]).box()
    top = None
    for ln in fn("island"):
        ctx = parse_exec(ln)
        if ctx["run"][:2] == ["function", "%s/met" % RF]:
            top = ctx["as"].box()
    hp = lambda c: (c[0], c[2], 2 * (c[1] - ybase), STAND)

    def valid(p):
        c = S.col(p[0], p[1])
        return _set(c, p[2] - 1) and _free(c, p[2], p[2] + p[3] - 1)

    def p_in(p, b):
        y = p[2] / 2.0 + ybase
        return b[0] <= p[0] <= b[3] and b[2] <= p[1] <= b[5] and y < b[4] + 1 and y + (1.8 if p[3] == STAND else 1.5) > b[1]

    def yy(p):
        return p[2] / 2.0 + ybase

    loops = []
    if not valid(hp(landing)):
        loops.append("the island landing %s is not a place to stand" % (landing,))
    if p_in(hp(landing), recess):
        loops.append("the island landing %s is inside the way-down box %s" % (landing, recess))
    if not valid(hp(ret)):
        loops.append("the way-down point %s is not a place to stand" % (ret,))
    if p_in(hp(ret), door):
        loops.append("the way-down point %s is inside the arch's doorway box %s" % (ret, door))

    period = spec["gate"]["period_ticks"]
    catch = fall_ticks_distance(2 * period)

    def protected(p, col, fall):
        y = p[2] / 2.0 + ybase
        return (rescue is not None and rescue[0] <= col[0] <= rescue[3] and rescue[2] <= col[1] <= rescue[5]
                and rescue[4] >= y - 1 and rescue[1] <= y - min(catch, fall))

    def explore(start, jump=True, sneak_ok=True, limit=600000):
        seen = {start: None}
        q = deque([start])
        drops = []
        edges = {}
        while q:
            p = q.popleft()
            if p_in(p, recess):
                continue                                            # taken down to the summit
            outs = []
            for d, kind, fall in sky_moves(S, p, jump, sneak_ok):
                if kind == "fall" and fall >= DAMAGE_FALL:
                    safe = protected(p, d, fall)
                    drops.append((p, d, fall, safe))
                    if safe or fall >= LETHAL_FALL:
                        outs.append(("exit" if safe else "dead", d))
                        continue
                outs.append(("pos", d))
                if d not in seen:
                    seen[d] = p
                    q.append(d)
                    if len(seen) > limit:
                        raise AuditError("the island walk did not close after %d positions" % limit)
            edges[p] = outs
        return seen, drops, edges

    pc = (spec["island"]["centre"]["x"] + spec["pillar"]["offset"]["x"], spec["island"]["centre"]["z"] + spec["pillar"]["offset"]["z"])
    yF = landing[1] - 1 + spec["pillar"]["top_floor"]
    R, drops, edges = explore(hp(landing))                          # everything a player can do: jump, sneak
    crown = [p for p in R if p_in(p, top)]
    R_st, _d, _e = explore(hp(landing), sneak_ok=False)             # the climb as walked upright
    crown_st = [p for p in R_st if p_in(p, top)]
    R_nj, _d, _e = explore(hp(landing), jump=False, sneak_ok=False)
    crown_nj = [p for p in R_nj if p_in(p, top)]
    stuck = []
    if not crown_st:
        inside = [p for p in R_st if math.hypot(p[0] - pc[0], p[1] - pc[1]) <= spec["pillar"]["outer_radius"]]
        hi_ = max(inside, key=lambda p: p[2]) if inside else None
        if hi_:
            c = S.col(hi_[0], hi_[1])
            ceil = next((i for i in range(hi_[2], hi_[2] + 40) if _set(c, i)), None)
            stuck.append("standing, the climb tops out at (%d, %.1f, %d) with %.1f blocks of headroom; the next half-block "
                         "step needs %.1f over the column it leaves (1.8 + 0.5), so only a SNEAKING player (1.5) passes"
                         % (hi_[0], yy(hi_), hi_[1], (ceil - hi_[2]) / 2.0 if ceil else -1, 2.3))
    rep.add("rayquaza.crown_reachable", not loops and bool(crown),
            "from the island landing %s (the arch's tp), by the climb (walking, 1-block jumps, sneaking where a player can): "
            "%d positions, %d on the crown %s" % (landing, len(R), len(crown), top), loops)
    rep.add("rayquaza.crown_reachable_upright", not loops and bool(crown_st),
            "walking upright (no sneak) with 1-block jumps: %d positions, %d on the crown. Upright without any jump (the "
            "data's 'walked without a jump'): %d" % (len(R_st), len(crown_st), len(crown_nj)), loops + stuck)

    # the climb is roofed: every reachable position inside the pillar under its top floor has a block over the head
    open_ = set()
    topi = 2 * (yF - ybase) + 1
    for p in R:
        y = yy(p)
        if math.hypot(p[0] - pc[0], p[1] - pc[1]) <= spec["pillar"]["inner_radius"] and y < yF:
            c = S.col(p[0], p[1])
            hd = p[2] + p[3]
            if topi < hd or (c >> hd) & ((1 << (topi - hd + 1)) - 1) == 0:
                open_.add((p[0], round(y, 1), p[1]))
    # KYOGRE_CAVE.md 6 roofed the climb "so a flying mount does not skip it"; in the overworld the crown is open to the sky
    # (data/rayquaza_sky.json design.supersedes), so a flyer reaches the crown anyway and the roof is measured, not judged
    low_open = min((o[1] for o in open_), default=None)
    rep.add("rayquaza.climb_roof", True,
            "%d reachable positions inside the pillar (radius %s about %s) below its top floor y%d have open sky over the "
            "head, the lowest at y%s, all where the helix comes up through the top floor (the design's opening onto the "
            "crown). A flyer reaches the open crown without the climb: the arch, not the roof, is the gate"
            % (len(open_), spec["pillar"]["inner_radius"], pc, yF, low_open), sorted(open_)[:4], kind="measurement")

    # nobody is stranded: every reachable position reaches the way down, or a fall the Slow Falling catches
    rev = {}
    goal = set()
    for p, outs in edges.items():
        for kind, d in outs:
            if kind == "exit":
                goal.add(p)
            elif kind == "pos":
                rev.setdefault(d, []).append(p)
    for p in R:
        if p_in(p, recess):
            goal.add(p)
    ok = set(goal)
    stack = list(goal)
    while stack:
        for qn in rev.get(stack.pop(), ()):
            if qn not in ok:
                ok.add(qn)
                stack.append(qn)
    stranded = [p for p in R if p not in ok]
    rec = set()
    st2 = [p for p in R if p_in(p, recess)]
    rec.update(st2)
    while st2:
        for qn in rev.get(st2.pop(), ()):
            if qn not in rec:
                rec.add(qn)
                st2.append(qn)
    no_way_down = [p for p in R if p not in rec]
    rep.add("rayquaza.nobody_is_stranded", not stranded,
            "of %d positions reachable from the landing, %d reach no way off (the way-down alcove %s, or a fall the Slow "
            "Falling box %s catches within %d ticks, %.1f blocks); %d cannot reach the alcove itself" %
            (len(R), len(stranded), recess, rescue, 2 * period, catch, len(no_way_down)),
            [(p[0], p[2] / 2.0 + ybase, p[1]) for p in stranded[:6]])

    lethal = sorted({(p[0], p[2] / 2.0 + ybase, p[1], fall) for p, d, fall, safe in drops if not safe and fall >= LETHAL_FALL},
                    key=lambda r: -r[3])
    hurt = {(p[0], p[2], p[1], fall) for p, d, fall, safe in drops if not safe and DAMAGE_FALL <= fall < LETHAL_FALL}
    floor_lethal = sorted({r for r in lethal if r[1] <= yF + 1}, key=lambda r: (r[1], -r[3]))
    rep.add("rayquaza.no_lethal_fall", not lethal,
            "%d walk-offs reachable from the landing fall %d blocks or more outside the Slow Falling box (vanilla: fall "
            "damage = blocks - 3, 20 health), %d of them straight off the crown's floor (y%d) through a gap in its broken "
            "wall, the rest from its broken wall's tops (y%s..y%s); %d further walk-offs hurt without killing; the worst "
            "falls %s" % (len(lethal), LETHAL_FALL, len(floor_lethal), yF + 1, min((r[1] for r in lethal), default="-"),
                          max((r[1] for r in lethal), default="-"), len(hurt), lethal[0][3] if lethal else 0),
            ["from (%d, %.1f, %d), %.1f blocks" % r for r in (floor_lethal[:4] + lethal[:4])])

    # the way up starts on foot: the arch's doorway is walkable from the way-down point over the replayed plinth and terrain
    seen = {hp(ret)}
    q = deque([hp(ret)])
    hit_door = False
    while q and not hit_door:
        p = q.popleft()
        for d, kind, fall in sky_moves(S, p):
            if abs(d[0] - ret[0]) > 40 or abs(d[1] - ret[2]) > 40 or d in seen:
                continue
            if p_in(d, door):
                hit_door = True
                break
            seen.add(d)
            q.append(d)
    rep.add("rayquaza.doorway_walkable_from_the_summit", hit_door,
            "the arch's doorway box %s is reached on foot from the way-down point %s over the plinth and the heightmap's "
            "summit (%d positions searched)" % (door, ret, len(seen)))
    return rep


def bind_dominated(fns, cg, fid, oktag):
    """bind runs as a Pokemon picked near the spot without tag=!guardian. It is safe only when its one caller (spawn) is
    run only by a function that, earlier, returns while a guardian of the species is within the picker's reach of the
    same point."""
    cs = callers_of(cg, fid)
    if not cs:
        return False
    for caller, i, _c, ctx, _s in cs:
        s = ctx["as"]
        if s is None or ctx["positioned"] is None or not s.get("distance"):
            return False
        d_pick = float(s.get("distance")[0].lstrip("."))
        spec_nbt = s.get("nbt")
        ok_all = True
        for up, j, _c2, ctx2, sched in callers_of(cg, caller):
            if sched:
                return False
            lines = fns[up]
            guard_ln = None
            for k in range(j):
                c = parse_exec(lines[k])
                for cond in c["conds"]:
                    if cond[0] == "if" and cond[1] == "entity" and GUARDIAN in cond[2].tags():
                        g = cond[2]
                        gx = tuple(float(g.get(a)[0]) for a in "xyz") if g.get("x") else None
                        gd = float(g.get("distance")[0].lstrip(".")) if g.get("distance") else 0
                        if gx == ctx["positioned"] and gd >= d_pick and g.get("nbt") == spec_nbt \
                                and c["run"][:3] == ["scoreboard", "players", "set"]:
                            guard_ln = (k, c["run"][3], c["run"][4])
            if guard_ln is None:
                ok_all = False
                break
            k, holder, obj = guard_ln
            ret = any(parse_exec(lines[m])["returned"] and any(cc[1] == "score" and cc[2] == holder and cc[3] == obj
                                                                and cc[5].startswith("1") for cc in parse_exec(lines[m])["conds"])
                      for m in range(k + 1, j))
            if not ret:
                ok_all = False
                break
        if not ok_all:
            return False
    return True


# ================================================================================================ the run

def audit(kyogre_pack=KPACK, rayquaza_pack=RPACK, ground=None, only=None):
    rep = Report()
    if ground is None:
        import ground as GR
        ground = GR.Ground()
    if only in (None, "kyogre"):
        kyogre(kyogre_pack, rep, ground)
    if only in (None, "rayquaza"):
        rayquaza(rayquaza_pack, rep, ground)
    if only is None:
        # contract C26 across the two packs: the Kyogre met that Rayquaza's gate reads is defined, and granted, by Kyogre's
        K = read_pack(kyogre_pack)
        met = RAY_GATE[1]
        grants = sorted(f for f, lines in K["fns"].items() for ln in lines
                        if parse_exec(ln)["run"][:4] == ["advancement", "grant", "@s", "only"] and parse_exec(ln)["run"][4:5] == [met])
        rep.add("trio.kyogre_met_is_defined_and_granted", met in K["adv"] and bool(grants),
                "%s, which Rayquaza's gate reads, is an advancement of the Kyogre pack and granted by %s" % (met, grants))
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kyogre-pack", default=str(KPACK))
    ap.add_argument("--rayquaza-pack", default=str(RPACK))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--only", choices=("kyogre", "rayquaza"))
    a = ap.parse_args(argv)
    try:
        rep = audit(a.kyogre_pack, a.rayquaza_pack, only=a.only)
    except AuditError as e:
        print("kyogre_rayquaza_audit: FAIL (could not run: %s)" % e)
        return 1
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated_by": "tools/kyogre_rayquaza_audit.py", "kyogre_pack": a.kyogre_pack,
                               "rayquaza_pack": a.rayquaza_pack, "items": rep.items}, indent=1) + "\n", encoding="utf-8")
    props = [it for it in rep.items if it["kind"] == "property"]
    bad = rep.failed()
    if bad:
        print("kyogre_rayquaza_audit: FAIL %d of %d properties (%s); detail in %s" % (len(bad), len(props), ", ".join(bad), out))
        return 1
    print("kyogre_rayquaza_audit: PASS %d of %d properties; detail in %s" % (len(props), len(props), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
