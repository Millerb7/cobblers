#!/usr/bin/env python
"""The long mine networks of the eastern half (the owner, 2026-10-21: "with no caves people wont be incentivized to mine at
all ... really really large and long mines every so often in the world ... i need some to be thousands long ... a few
hunderd block caves wont be enough for 10 people ... its looking more like 6 now"), from data/mine_networks.json.

Each network is an abandoned working cut into the rock under a hill: a timbered adit (or two) from the surface, main
haulage drifts 3 wide and 4 tall with timber sets every few blocks, rails on a cobblestone bed and sparse hanging lanterns
on the main line only, crosscuts and long side drifts 3 wide and 3 tall, stopes (chambers 6 tall with pillars left) where
six players can work at once, inclines of stairs and ladder shafts between the levels (16 blocks apart), dead ends, and
vanilla ore in the exposed walls: richer on the deeper levels and the farther from the adit, deepslate variants below y0.

  data/mine_networks.json  ->  tools/mine_networks.py  ->  build/datapacks/cobblers_mine_networks  ->  tools/mine_networks_audit.py
  (the plan: derived/mine_networks/plan.json; the pictures: tools/mine_networks_map.py; the step: tools/reapply.py R9MN)

THE HOUSE PATTERN, reused rather than invented: tools/mines.py's h32/sid (every choice is a hash of the seed, an id and a
position) and column_runs (vertical runs of ore); tools/mining_caves.py's tile of fills and its spawn-block policy check;
tools/function_limits.py ensure_loaded and check_lines on every function (fill <= 32,768 blocks, forceload <= 256 chunks).

THE RULES, each with where it is enforced (tools/mine_networks_audit.py re-checks every one from the BUILT FUNCTIONS, not
from this tool's geometry):

  ground       only tools/ground.py (the canonical heightmap, rounded); never a world.
  cover        at least `cover_min` (8) blocks of ground over every written cell above the adit's first `adit_exempt` cells:
               the drifts are grown only where the 5 x 5 least ground clears the beam above the roof by cover_min.
  water        no carved cell under or within `water_clear` (12) blocks of the sea, a lake basin, a river corridor or a
               waterway (tools/mine_nets_world.py): grown with the Chebyshev margin, audited with the Euclidean one.
  shell        the rock holds hidden water and lava (Groudon's cavern flooded from pockets in it, docs/STATE.md): every
               function carves, then replaces water and lava with stone in a shell `shell` (2) thick round every carved box,
               then carves again, so the shell work cannot refill a tunnel.
  authored     `authored_clear` (32) blocks from every x/z, box and short polyline any data/*.json carries (towns,
               placements, structures, dungeons, legendaries, caves, mines, the Rift ...), and from the border: x >= `x_min`.
  limits       tiles of 128 x 128 blocks, one function each; FL.ensure_loaded then FL.check_lines on each.
  rails        a cobblestone bed under every rail, the spawn-block policy entry scoped to mine_networks for the rail and the
               coal, iron, redstone and diamond ore the bank buys (data/spawn_block_policy.json).

WHAT THIS DOES NOT CHECK (CLAUDE.md "Our list is not the world"): water or lava the heightmap and data/ do not describe
beyond the shell's 2 blocks; a natural cave, a mod structure or a trader placed in the world and in no data file; the rock
actually being stone below the surface (it is assumed, as tools/mining_caves.py assumes it); derived/routes critical legs
and build/paint (generated, absent from a fresh checkout); whether the pillars, stairs, rails and ladders come out as
written in a running game. Nothing here has been applied to any world.

  python tools/mine_networks.py site <x0> <z0> <x1> <z1>   candidate adit sites in a box; nothing written
  python tools/mine_networks.py report                     every network's layout and counts; nothing written
  python tools/mine_networks.py build                      -> build/datapacks/cobblers_mine_networks, derived/mine_networks/plan.json
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402
import mines as M              # noqa: E402
import mine_nets_world as W    # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "mine_networks.json"
PACK = "cobblers_mine_networks"
OUT = ROOT / "build" / "datapacks" / PACK
PLAN = ROOT / "derived" / "mine_networks" / "plan.json"
NS = "cobblers"
FOLDER = "mine_networks"
F_ = "%s:%s" % (NS, FOLDER)
POLICY_SCOPE = "mine_networks"
AIR = "minecraft:air"
DIRS = {"east": (1, 0), "west": (-1, 0), "south": (0, 1), "north": (0, -1)}
NAME_OF = {v: k for k, v in DIRS.items()}
MAIN_KINDS = ("adit", "main", "link_main")
SPACING = 7          # reservation margin round a run: two unrelated centre lines stay at least SPACING + 1 apart
EXEMPT = 7           # a branch's first cells may sit inside its parent's reservation


class MineError(Exception):
    pass


def load(path=None):
    return json.loads(Path(path or SPEC).read_text(encoding="utf-8"))


_GROUND = {}


def read_ground(box, source_root=None):
    """int16 [z, x] canonical ground over a Box. The one place this tool reads the heightmap (tests patch it to prove the
    audit catches a generator that over-reads the ground)."""
    key = str(source_root)
    if key not in _GROUND:
        _GROUND[key] = G.Ground(source_root)
    return _GROUND[key].box(box.x0, box.z0, box.x1, box.z1).astype(np.int16)


def water_mask(box, hbox, rules):
    """bool [z, x]: where there is, or may be, water (tools/mine_nets_world.py). Tests patch it to prove the audit's bite."""
    return W.water_seed(box, hbox, rules)


def base(block):
    return block.split("[")[0]


def line_ok(v):
    return int(v)


# ------------------------------------------------------------------ the layout

class Layout:
    """One network, grown deterministically on the heightmap's ground: runs (straight drifts), stopes, inclines, shafts."""

    def __init__(self, spec, net, source_root=None):
        self.spec, self.net = spec, net
        self.rules, self.geo = spec["rules"], spec["geometry"]
        self.gro = dict(spec["growth"], **net.get("growth", {}))
        self.seed, self.sid = spec["seed"], M.sid(net["id"])
        bx0, bz0, bx1, bz1 = net["box"]
        if bx0 < self.rules["x_min"]:
            raise MineError("%s: box starts at x%d, west of x_min %d" % (net["id"], bx0, self.rules["x_min"]))
        pad = 40
        self.box = W.Box(bx0, bz0, bx1, bz1)
        self.pbox = pb = W.Box(bx0 - pad, bz0 - pad, bx1 + pad, bz1 + pad)
        self.H = read_ground(pb, source_root)
        self.gm5 = W.min_filter(self.H, 2)
        wet = water_mask(pb, self.H, self.rules)
        auth = W.authored_seed(pb)
        self.wet, self.auth = wet, auth
        self.fw = W.dilate_sq(wet, self.rules["water_clear"] + 2)
        self.fa = W.dilate_sq(auth, self.rules["authored_clear"] + 2)
        border = pb.zeros()
        pb.put_rect(border, pb.x0, pb.z0, self.rules["x_min"] + 1, pb.z1)
        self.forbid = self.fw | self.fa | border
        self.fok = ~self.forbid
        inbox = pb.zeros()
        pb.put_rect(inbox, bx0 + 6, bz0 + 6, bx1 - 6, bz1 - 6)
        self.inbox = inbox
        gap = self.geo["level_gap"]
        ax, az = net["adits"][0]["portal"]
        top = int(self.H[az - pb.z0, ax - pb.x0])
        self.levels = [top - gap * i for i in range(net["levels"])]
        if self.levels[-1] < self.rules["y_floor_min"]:
            raise MineError("%s: the lowest level y%d is under y_floor_min %d" % (net["id"], self.levels[-1], self.rules["y_floor_min"]))
        cov = self.rules["cover_min"]
        mh, sh = self.geo["main_height"], self.geo["side_height"]
        self.ok_main = [(self.gm5 >= F + mh + 1 + cov) & self.fok & inbox for F in self.levels]
        self.ok_side = [(self.gm5 >= F + sh + 1 + cov) & self.fok & inbox for F in self.levels]
        self.cnt = [np.zeros(pb.shape, np.int16) for _ in self.levels]
        self.runs, self.stopes, self.inclines, self.shafts, self.links = [], [], [], [], []
        self.feeds = [[] for _ in self.levels]
        self.problems = []
        self.notes = []
        self.used_ends = set()

    # -- hashing
    def hv(self, *v):
        return M.h32(self.seed, self.sid, *v)

    def rr(self, lo, hi, *v):
        return lo + self.hv(*v) % (hi - lo + 1)

    def chance(self, p, *v):
        return (self.hv(*v) & 0xFFFF) < int(p * 65536)

    def idx(self, x, z):
        return z - self.pbox.z0, x - self.pbox.x0

    # -- the reservation grid
    def reserve(self, k, rect, delta=1):
        pb = self.pbox
        xa, za, xb, zb = rect
        xa, xb = max(xa, pb.x0), min(xb, pb.x1)
        za, zb = max(za, pb.z0), min(zb, pb.z1)
        if xa <= xb and za <= zb:
            self.cnt[k][za - pb.z0:zb - pb.z0 + 1, xa - pb.x0:xb - pb.x0 + 1] += delta

    @staticmethod
    def in_rect(x, z, r):
        return r[0] <= x <= r[2] and r[1] <= z <= r[3]

    def walk(self, k, x, z, d, maxlen, kind, parent, cover_free=0, origin_rects=(), total=None):
        """How many steps along d from cell (x, z) a drift of this kind may go: every cell clear of water and the authored,
        under enough ground, and not in another run's reservation (a parent's own, for the first EXEMPT cells, excepted)."""
        ok = self.ok_main[k] if kind in MAIN_KINDS else self.ok_side[k]
        cnt = self.cnt[k]
        pb = self.pbox
        rects = [parent["rect"]] if parent else []
        rects += list(origin_rects)
        n = 0
        for i in range(1, maxlen + 1):
            cx, cz = x + d[0] * i, z + d[1] * i
            iz, ix = cz - pb.z0, cx - pb.x0
            if i <= cover_free:
                if not (self.inbox[iz, ix] and self.fok[iz, ix]):
                    break
            elif not ok[iz, ix]:
                break
            c = cnt[iz, ix]
            if c:
                near = i <= EXEMPT or (total is not None and i >= total - EXEMPT)
                if not (c == 1 and near and any(self.in_rect(cx, cz, r) for r in rects)):
                    break
            n = i
        return n

    # -- runs
    def add_run(self, k, x, z, d, n, kind, parent, attach, root_i=0, depth=0, d0=None, rail=None):
        xs = (x, x + d[0] * n)
        zs = (z, z + d[1] * n)
        run = {"id": len(self.runs) + 1, "level": k, "kind": kind, "x0": x, "z0": z, "d": d, "n": n,
               "height": self.geo["main_height"] if kind in MAIN_KINDS else self.geo["side_height"],
               "parent": parent["id"] if parent else None, "attach": attach, "root_i": root_i, "depth": depth,
               "d0": (parent["d0"] + abs(attach - parent["root_i"]) if d0 is None and parent else (d0 or 0)),
               "children": [], "rect": (min(xs) - SPACING, min(zs) - SPACING, max(xs) + SPACING, max(zs) + SPACING)}
        if parent:
            parent["children"].append((attach, run["id"]))
        self.runs.append(run)
        self.reserve(k, run["rect"])
        return run

    def cell(self, run, i):
        return run["x0"] + run["d"][0] * i, run["z0"] + run["d"][1] * i

    # -- a main chain with jogs
    def extend_main(self, k, feed):
        cur = (feed["x"], feed["z"])
        d = feed["d"]
        parent = feed.get("parent")
        attach = feed.get("attach", 0)
        remaining = feed["length"]
        made = []
        first = True
        jogs = 0
        while remaining > 0:
            exempt = feed.get("cover_free", 0) if first else 0
            n = self.walk(k, cur[0], cur[1], d, remaining, "adit" if (first and feed.get("adit")) else "main", parent,
                          cover_free=exempt, origin_rects=feed.get("rects", ()) if first else ())
            if n >= (1 if first else self.gro["min_run"]):
                kind = "adit" if (first and feed.get("adit")) else "main"
                run = self.add_run(k, cur[0], cur[1], d, n, kind, parent, attach, 0, feed.get("depth", 0), feed.get("d0"))
                if first and "d0" in feed:
                    run["d0"] = feed["d0"]
                made.append(run)
                remaining -= n
                end = self.cell(run, n)
                parent, attach = run, n
            elif first:
                raise MineError("%s: level %d feed at (%d, %d) heading %s cannot go %d cells" %
                                (self.net["id"], k + 1, cur[0], cur[1], NAME_OF[d], self.gro["min_run"]))
            else:
                break
            first = False
            if remaining <= self.gro["min_run"] * 2 or jogs >= self.gro["max_jogs"]:
                break
            # blocked or finished early: a jog sideways, then on in the same heading
            jl = self.rr(self.gro["jog"][0], self.gro["jog"][1], 11, k, run["id"])
            perp = [(-d[1], d[0]), (d[1], -d[0])]
            if self.hv(12, k, run["id"]) & 1:
                perp.reverse()
            moved = False
            for e in perp:
                m = self.walk(k, end[0], end[1], e, jl, "main", run)
                if m < jl:
                    continue
                jx, jz = end[0] + e[0] * jl, end[1] + e[1] * jl
                # the continuation must be worth the jog: probe it before registering anything
                probe = self.walk(k, jx, jz, d, self.gro["min_run"] * 2, "main", None, origin_rects=[self._jog_rect(end, e, jl)])
                if probe < self.gro["min_run"] * 2:
                    continue
                jog = self.add_run(k, end[0], end[1], e, jl, "main", run, n, 0, feed.get("depth", 0))
                made.append(jog)
                cur, parent, attach = (jx, jz), jog, jl
                jogs += 1
                moved = True
                break
            if not moved:
                break
        return made

    @staticmethod
    def _jog_rect(end, e, jl):
        xs = (end[0], end[0] + e[0] * jl)
        zs = (end[1], end[1] + e[1] * jl)
        return (min(xs) - SPACING, min(zs) - SPACING, max(xs) + SPACING, max(zs) + SPACING)

    # -- branches
    def branch(self, k, run, budget_left, max_new=3):
        """Crosscuts through a main or side run (at most max_new a call, so the runs of a level take turns), or side drifts
        from a crosscut's ends. Returns (the new runs, whether this run has more to give)."""
        new = []
        g = self.gro
        kind = run["kind"]
        if kind in MAIN_KINDS:
            spc, ln, depth_next = g["cross_spacing"], g["cross_len"], 1
            both_p = g["cross_both"]
        elif kind == "cross":
            return self.side_from_cross(k, run, budget_left), False
        elif kind == "side" and run["depth"] < g["max_depth"]:
            spc, ln, depth_next = g["cross2_spacing"], g["cross2_len"], run["depth"] + 1
            both_p = 0.4
        else:
            return new, False
        if "next_pos" not in run:
            run["next_pos"] = self.rr(g["first_cross"][0], g["first_cross"][1], 20, run["id"])
            run["j"] = 0
        while run["next_pos"] <= run["n"] - 12 and budget_left > 0 and len(new) < max_new:
            pos = run["next_pos"]
            run["j"] += 1
            j = run["j"]
            run["next_pos"] = pos + self.rr(spc[0], spc[1], 27, run["id"], j)
            if kind == "side" and not self.chance(g["cross2_chance"], 21, run["id"], j):
                continue
            if any(abs(pos - a) < 14 for a, _c in run["children"]):
                continue
            c = self.cell(run, pos)
            dp = (-run["d"][1], run["d"][0])
            sides = [dp, (-dp[0], -dp[1])]
            lens = []
            for s_i, s in enumerate(sides):
                want = self.rr(ln[0], ln[1], 24, run["id"], j, s_i)
                lens.append(self.walk(k, c[0], c[1], s, want, "cross" if kind in MAIN_KINDS else "side", run))
            if not self.chance(both_p, 25, run["id"], j):
                lens[self.hv(26, run["id"], j) & 1] = 0
            lens = [m if m >= g["cross_min"] else 0 for m in lens]
            if lens[0] or lens[1]:
                a, b = lens           # a along sides[0], b along sides[1]; the run starts b back along sides[0]
                s0 = sides[0]
                start = (c[0] - s0[0] * b, c[1] - s0[1] * b)
                cr = self.add_run(k, start[0], start[1], s0, a + b, "cross" if kind in MAIN_KINDS else "side",
                                  run, pos, b, depth_next)
                new.append(cr)
                budget_left -= cr["n"]
        more = run["next_pos"] <= run["n"] - 12
        return new, more

    def side_from_cross(self, k, cr, budget_left):
        """From a crosscut's far end(s): a long side drift running parallel to the main, one way or both."""
        g = self.gro
        new = []
        ends = []
        d = cr["d"]
        if cr["n"] != cr["root_i"]:
            ends.append((self.cell(cr, cr["n"]), 0))
        if cr["root_i"] > 0:
            ends.append((self.cell(cr, 0), 1))
        for e_i, (end, which) in enumerate(ends):
            if budget_left <= 0 or not self.chance(g["side_chance"], 30, cr["id"], which):
                continue
            ep = (-d[1], d[0])
            want = self.rr(g["side_len"][0], g["side_len"][1], 31, cr["id"], which)
            la = self.walk(k, end[0], end[1], ep, want, "side", cr)
            lb = self.walk(k, end[0], end[1], (-ep[0], -ep[1]), want, "side", cr)
            if not self.chance(g["side_both"], 32, cr["id"], which):
                if self.hv(33, cr["id"], which) & 1:
                    la = 0
                else:
                    lb = 0
            la = la if la >= g["side_min"] else 0
            lb = lb if lb >= g["side_min"] else 0
            if la or lb:
                start = (end[0] - ep[0] * lb, end[1] - ep[1] * lb) if lb else end
                att = cr["n"] if which == 0 else 0
                sd = self.add_run(k, start[0], start[1], ep, la + lb, "side", cr, att, lb, 2)
                sd["d0"] = cr["d0"] + abs(att - cr["root_i"])
                new.append(sd)
                budget_left -= sd["n"]
        return new

    def grow_level(self, k):
        made = []
        for feed in self.feeds[k]:
            made += self.extend_main(k, feed)
        work = deque(made)
        total = sum(r["n"] for r in made)
        budget = self.net["budgets"][k]
        while work and total < budget:
            r = work.popleft()
            kids, more = self.branch(k, r, budget - total)
            for c in kids:
                total += c["n"]
            work.extend(kids)
            if more:
                work.append(r)
        return total

    # -- the ends the connectors may use
    def free_ends(self, k):
        out = []
        for r in self.runs:
            if r["level"] != k or r["kind"] in ("link", "link_main"):
                continue
            ends = []
            if r["n"] != r["root_i"]:
                ends.append((r["n"], r["d"]))
            if r["root_i"] > 0 and r["kind"] in ("cross", "side"):
                ends.append((0, (-r["d"][0], -r["d"][1])))
            for i, dd in ends:
                if any(abs(a - i) <= 2 for a, _c in r["children"]):
                    continue
                if (r["id"], i) in self.used_ends:
                    continue
                if r["n"] < 12:
                    continue
                out.append((r, i, dd))
        return out

    def connect_down(self, k):
        """Inclines and ladder shafts from level k to level k + 1 at its run ends, farthest from the adit first."""
        want_i = self.net["inclines"][k]
        want_s = self.net["shafts"][k]
        gap = self.geo["level_gap"]
        cands = self.free_ends(k)
        far = [(r["d0"] + abs(i - r["root_i"]), self.hv(40, r["id"], i), r, i, dd) for r, i, dd in cands]
        far.sort(key=lambda t: (-t[0], t[1]))
        top_far = far[0][0] if far else 0
        keep = [t for t in far if t[0] >= top_far * self.gro["connector_far"]]
        keep.sort(key=lambda t: t[1])
        chosen = []
        made_i = made_s = 0
        for dist, _h, r, i, dd in keep:
            if made_i >= want_i and made_s >= want_s:
                break
            end = self.cell(r, i)
            if any(abs(end[0] - c[0]) + abs(end[1] - c[1]) < self.gro["connector_gap"] for c in chosen):
                continue
            if made_i < want_i and self.try_incline(k, r, i, dd, dist):
                made_i += 1
                chosen.append(end)
                self.used_ends.add((r["id"], i))
            elif made_s < want_s and self.try_shaft(k, r, i, dd, dist):
                made_s += 1
                chosen.append(end)
                self.used_ends.add((r["id"], i))
        if made_i + made_s == 0:
            self.problems.append("%s: level %d has no incline or shaft down: the levels below are unreachable" % (self.net["id"], k + 1))
        elif made_i < want_i or made_s < want_s:
            self.notes.append("%s: level %d wanted %d inclines and %d shafts, made %d and %d" %
                              (self.net["id"], k + 1, want_i, want_s, made_i, made_s))

    def try_incline(self, k, r, i, dd, dist):
        gap = self.geo["level_gap"]
        F = self.levels[k]
        E = self.cell(r, i)
        cov = self.rules["cover_min"]
        pb = self.pbox
        for s in range(1, gap + 1):
            cx, cz = E[0] + dd[0] * s, E[1] + dd[1] * s
            iz, ix = cz - pb.z0, cx - pb.x0
            if not (self.inbox[iz, ix] and self.fok[iz, ix]):
                return False
            top = F - s + 1 + self.geo["main_height"]
            if self.gm5[iz, ix] - top < cov:
                return False
            c0 = self.cnt[k][iz, ix]
            if s <= EXEMPT:
                if c0 > 1 or (c0 == 1 and not self.in_rect(cx, cz, r["rect"])):
                    return False
            if s >= 10 and self.cnt[k + 1][iz, ix]:
                return False
        L = (E[0] + dd[0] * (gap + 1), E[1] + dd[1] * (gap + 1))
        iz, ix = L[1] - pb.z0, L[0] - pb.x0
        if not (self.ok_main[k + 1][iz, ix] and self.cnt[k + 1][iz, ix] == 0):
            return False
        n = self.walk(k + 1, L[0], L[1], dd, self.gro["min_run"], "main", None)
        if n < self.gro["min_run"]:
            return False
        inc = {"id": len(self.inclines) + 1, "level": k, "x0": E[0], "z0": E[1], "d": dd, "steps": gap, "run": r["id"], "at": i}
        self.inclines.append(inc)
        top_rect = self._seg_rect(E, dd, 0, 8)
        low_rect = self._seg_rect(E, dd, gap - 6, gap + 1)
        self.reserve(k, top_rect)
        self.reserve(k + 1, low_rect)
        d0 = r["d0"] + abs(i - r["root_i"]) + gap + 1
        self.feeds[k + 1].append({"x": L[0], "z": L[1], "d": dd, "length": self.gro["main_len"][min(k + 1, len(self.gro["main_len"]) - 1)],
                                  "parent": None, "d0": d0, "depth": 0, "from": "incline %d" % inc["id"], "rects": [low_rect]})
        return True

    def _seg_rect(self, E, dd, a, b):
        xs = (E[0] + dd[0] * a, E[0] + dd[0] * b)
        zs = (E[1] + dd[1] * a, E[1] + dd[1] * b)
        return (min(xs) - SPACING, min(zs) - SPACING, max(xs) + SPACING, max(zs) + SPACING)

    def try_shaft(self, k, r, i, dd, dist):
        gap = self.geo["level_gap"]
        F = self.levels[k]
        E = self.cell(r, i)
        S = E                       # the shaft is cut down from the run's last cell; the wall beyond holds the ladder
        pb = self.pbox
        iz, ix = S[1] - pb.z0, S[0] - pb.x0
        cov = self.rules["cover_min"]
        if not (self.ok_side[k][iz, ix] and self.ok_main[k + 1][iz, ix] and self.cnt[k + 1][iz, ix] == 0):
            return False
        for s in (1, 2):
            bz, bx = S[1] + dd[1] * s - pb.z0, S[0] + dd[0] * s - pb.x0
            if self.cnt[k + 1][bz, bx] or self.cnt[k][bz, bx] > 1:
                return False
        back = (-dd[0], -dd[1])
        n = self.walk(k + 1, S[0], S[1], back, self.gro["main_len"][min(k + 1, len(self.gro["main_len"]) - 1)] // 2, "main", None)
        if n < self.gro["min_run"] * 2:
            return False
        sh = {"id": len(self.shafts) + 1, "level": k, "x": S[0], "z": S[1], "d": dd, "run": r["id"], "at": i}
        self.shafts.append(sh)
        # the wall behind the ladder is held at both levels: nothing may be cut into it later
        wall = (min(S[0] + dd[0], S[0] + dd[0] * 4) - 1, min(S[1] + dd[1], S[1] + dd[1] * 4) - 1,
                max(S[0] + dd[0], S[0] + dd[0] * 4) + 1, max(S[1] + dd[1], S[1] + dd[1] * 4) + 1)
        self.reserve(k, wall)
        srect = (S[0] - SPACING, S[1] - SPACING, S[0] + SPACING, S[1] + SPACING)
        self.reserve(k + 1, srect)
        d0 = r["d0"] + abs(i - r["root_i"]) + 1
        self.feeds[k + 1].append({"x": S[0], "z": S[1], "d": back, "length": self.gro["main_len"][min(k + 1, len(self.gro["main_len"]) - 1)],
                                  "parent": None, "d0": d0, "depth": 0, "from": "shaft %d" % sh["id"], "foot": True,
                                  "rects": [srect]})
        return True

    # -- stopes
    def place_stopes(self, k):
        want = self.net["stopes"][k]
        if not want:
            return
        g = self.geo
        F = self.levels[k]
        cands = [t for t in self.free_ends(k)]
        cands.sort(key=lambda t: self.hv(50, t[0]["id"], t[1]))
        made = 0
        taken = []
        for r, i, dd in cands:
            if made >= want:
                break
            if r["kind"] not in ("cross", "side", "main"):
                continue
            E = self.cell(r, i)
            if any(abs(E[0] - t[0]) + abs(E[1] - t[1]) < 60 for t in taken):
                continue
            L = self.rr(g["stope_len"][0], g["stope_len"][1], 51, r["id"], i)
            Wd = self.rr(g["stope_width"][0], g["stope_width"][1], 52, r["id"], i) | 1
            st = self.stope_at(k, r, i, dd, E, L, Wd)
            if st:
                made += 1
                taken.append(E)
                self.used_ends.add((r["id"], i))
        # a bay: a chamber opened sideways from a run's wall where no dead end would take one
        if made < want:
            bays = []
            for r in self.runs:
                if r["level"] != k or r["kind"] in ("link", "link_main") or r["n"] < 40:
                    continue
                for i in range(20, r["n"] - 20, 20):
                    for sgn in (1, -1):
                        bays.append((self.hv(53, r["id"], i, sgn), r, i, sgn))
            bays.sort(key=lambda t: t[0])
            for _h, r, i, sgn in bays:
                if made >= want:
                    break
                c = self.cell(r, i)
                dd = (-r["d"][1] * sgn, r["d"][0] * sgn)
                E = (c[0] + dd[0], c[1] + dd[1])
                if any(abs(E[0] - t[0]) + abs(E[1] - t[1]) < 60 for t in taken):
                    continue
                if any(abs(i - a) < 14 for a, _c in r["children"]):
                    continue
                L = self.rr(g["stope_len"][0], g["stope_len"][1], 54, r["id"], i)
                Wd = self.rr(g["stope_width"][0], g["stope_width"][1], 55, r["id"], i) | 1
                st = self.stope_at(k, r, i, dd, E, L, Wd)
                if st:
                    st["bay"] = True
                    made += 1
                    taken.append(E)
        if made < want:
            self.problems.append("%s: level %d wanted %d stopes, made %d" % (self.net["id"], k + 1, want, made))

    def stope_at(self, k, r, i, dd, E, L, Wd):
        g = self.geo
        F = self.levels[k]
        cov = self.rules["cover_min"]
        pb = self.pbox
        ep = (-dd[1], dd[0])
        h = g["stope_height"]
        half = Wd // 2
        cells = []
        for f in range(1, L + 1):
            for l in range(-half, half + 1):
                cells.append((E[0] + dd[0] * f + ep[0] * l, E[1] + dd[1] * f + ep[1] * l))
        xs = [c[0] for c in cells]
        zs = [c[1] for c in cells]
        xa, xb, za, zb = min(xs), max(xs), min(zs), max(zs)
        if xa - 3 < pb.x0 or xb + 3 > pb.x1 or za - 3 < pb.z0 or zb + 3 > pb.z1:
            return None
        sl = (slice(za - 2 - pb.z0, zb + 3 - pb.z0), slice(xa - 2 - pb.x0, xb + 3 - pb.x0))
        if not self.inbox[sl].all() or self.forbid[sl].any():
            return None
        if self.H[sl].min() - (F + h) < cov:
            return None
        # the footprint must be free of every other reservation but the parent's (cells near the entry)
        sub = self.cnt[k][sl]
        near = np.zeros(sub.shape, bool)
        er = r["rect"]
        gz, gx = np.mgrid[za - 2:zb + 3, xa - 2:xb + 3]
        near = (gx >= er[0]) & (gx <= er[2]) & (gz >= er[1]) & (gz <= er[3])
        if (sub > 1).any() or ((sub == 1) & ~near).any():
            return None
        # the stope's own reservation (the cells and a margin) so nothing else grows into it
        rect = (xa - 5, za - 5, xb + 5, zb + 5)
        st = {"id": len(self.stopes) + 1, "level": k, "x0": xa, "z0": za, "x1": xb, "z1": zb, "d": dd, "run": r["id"],
              "at": i, "len": L, "width": Wd, "cells": cells, "E": E, "height": h, "d0": r["d0"] + abs(i - r["root_i"])}
        self.stopes.append(st)
        self.reserve(k, rect)
        return st

    # -- links (so every working is reached from an adit)
    def components(self):
        parent = {r["id"]: r["id"] for r in self.runs}

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a, b):
            parent[find(a)] = find(b)

        for r in self.runs:
            if r["parent"]:
                union(r["id"], r["parent"])
        for l in self.links:
            union(l["from"], l["to"])
        # an incline or a shaft joins the run it hangs from to the feed run it makes
        for r in self.runs:
            if r.get("feed_from"):
                union(r["id"], r["feed_from"])
        groups = {}
        for r in self.runs:
            groups.setdefault(find(r["id"]), []).append(r)
        return list(groups.values())

    def link_components(self):
        for _round in range(12):
            comps = self.components()
            if len(comps) <= 1:
                return
            comps.sort(key=lambda c: -sum(r["n"] for r in c))
            main_ids = {r["id"] for r in comps[0]}
            done = False
            for comp in comps[1:]:
                best = None
                for rb in comp:
                    for ra in self.runs:
                        if ra["id"] in main_ids and ra["level"] == rb["level"]:
                            cand = self.link_between(rb, ra)
                            if cand and (best is None or cand["n"] < best["n"]):
                                best = cand
                if best:
                    self.commit_link(best)
                    done = True
                    break
            if not done:
                return

    def link_between(self, rb, ra):
        """A straight link from a cell of run rb perpendicular into the centre line of run ra, or None."""
        k = rb["level"]
        if ra["d"][0] * rb["d"][0] + ra["d"][1] * rb["d"][1] != 0 and ra["d"] != rb["d"]:
            pass
        best = None
        step = 6
        for i in list(range(0, rb["n"] + 1, step)) + [rb["n"]]:
            if (rb["id"], i) in self.used_ends:
                continue
            P = self.cell(rb, i)
            for dd in [(-rb["d"][1], rb["d"][0]), (rb["d"][1], -rb["d"][0])] + ([rb["d"]] if i == rb["n"] else []) \
                    + ([(-rb["d"][0], -rb["d"][1])] if i == 0 else []):
                if dd[0] * ra["d"][0] + dd[1] * ra["d"][1] != 0:
                    continue          # must meet the run's line at a right angle
                # the ray from P along dd meets ra's centre line at ...
                if ra["d"][0] != 0:        # ra runs along x: line z = ra.z0
                    if dd[1] == 0:
                        continue
                    t = (ra["z0"] - P[1]) * dd[1]
                    hit = (P[0], ra["z0"])
                    a, b = sorted((ra["x0"], ra["x0"] + ra["d"][0] * ra["n"]))
                    if not (a + 3 <= hit[0] <= b - 3):
                        continue
                else:
                    if dd[0] == 0:
                        continue
                    t = (ra["x0"] - P[0]) * dd[0]
                    hit = (ra["x0"], P[1])
                    a, b = sorted((ra["z0"], ra["z0"] + ra["d"][1] * ra["n"]))
                    if not (a + 3 <= hit[1] <= b - 3):
                        continue
                if t < 4 or t > self.gro["link_max"]:
                    continue
                if best is not None and t >= best["n"]:
                    continue
                n = self.walk(k, P[0], P[1], dd, t, "main", None, origin_rects=[rb["rect"], ra["rect"]], total=t)
                if n == t:
                    best = {"level": k, "x": P[0], "z": P[1], "d": dd, "n": t, "from": rb["id"], "to": ra["id"], "at": i,
                            "hit": hit}
        return best

    def commit_link(self, l):
        rb = self.runs[l["from"] - 1]
        ra = self.runs[l["to"] - 1]
        run = self.add_run(l["level"], l["x"], l["z"], l["d"], l["n"], "link", rb, l["at"], 0, 3)
        run["d0"] = rb["d0"]
        self.links.append({"from": rb["id"], "to": ra["id"], "run": run["id"]})
        ra["children"].append((int(abs(l["hit"][0] - ra["x0"]) + abs(l["hit"][1] - ra["z0"])), run["id"]))

    def exempt_of(self, adit):
        e = int(adit.get("exempt", self.geo["adit_exempt"]))
        if e > self.rules["adit_exempt_max"]:
            raise MineError("%s: exempt %d is over adit_exempt_max %d" % (adit["id"], e, self.rules["adit_exempt_max"]))
        return e

    # -- the whole network
    def build(self):
        net = self.net
        for a in net["adits"]:
            k = a["level"] - 1
            x, z = a["portal"]
            F = int(self.H[z - self.pbox.z0, x - self.pbox.x0])
            if F != self.levels[k]:
                raise MineError("%s adit %s: ground y%d at the portal but level %d is y%d" % (net["id"], a["id"], F, a["level"], self.levels[k]))
            self.feeds[k].append({"x": x, "z": z, "d": DIRS[a["heading"]], "length": a.get("length", self.gro["main_len"][min(k, len(self.gro["main_len"]) - 1)]), "parent": None,
                                  "adit": a["id"], "cover_free": self.exempt_of(a), "d0": 0, "depth": 0})
        for k in range(len(self.levels)):
            if not self.feeds[k]:
                self.problems.append("%s: level %d has no feed (no incline or shaft reached it); the levels below are not built" %
                                     (net["id"], k + 1))
                break
            nrun0 = len(self.runs)
            self.grow_level(k)
            # a feed run that comes from an incline or shaft is a child of the run that carries it
            if k < len(self.levels) - 1:
                self.connect_down(k)
            self.place_stopes(k)
            for f in self.feeds[k]:
                pass
            self._tag_feeds(k, nrun0)
        self.link_components()
        comps = self.components()
        if len(comps) > 1:
            self.problems.append("%s: %d unconnected workings after linking" % (self.net["id"], len(comps)))
        return self

    def _tag_feeds(self, k, nrun0):
        """Mark each feed run of level k with the run it hangs from (an incline's or a shaft's upper run)."""
        for r in self.runs:
            if r["level"] != k or r["parent"] is not None:
                continue
        # feeds made by connect_down(k - 1) were grown at level k; match them by start cell
        for f in self.feeds[k]:
            src = f.get("from")
            if not src:
                continue
            kind, num = src.split()
            num = int(num)
            rid = (self.inclines[num - 1] if kind == "incline" else self.shafts[num - 1])["run"]
            for r in self.runs:
                if r["level"] == k and r["parent"] is None and (r["x0"], r["z0"]) == (f["x"], f["z"]):
                    r["feed_from"] = rid

    def length(self):
        return sum(r["n"] for r in self.runs) + sum(i["steps"] + 1 for i in self.inclines)


# ------------------------------------------------------------------ the model: cells, fittings and ore

class Model:
    """What a layout writes: the carved boxes, the fittings (timber, rails, stairs, ladders, lanterns, pillars) and the ore."""

    def __init__(self, L):
        self.L = L
        self.air = {}           # (x, y, z) -> (level, walk distance from an adit, in a stope)
        self.air_boxes = []     # (x0, y0, z0, x1, y1, z1)
        self.fix = {}           # (x, y, z) -> block: every fitting cell (never ore)
        self.fills = []         # ordered fitting fills (x0, y0, z0, x1, y1, z1, block)
        self.ores = {}          # (x, y, z) -> block
        self.ore_counts = {}
        self.counts = {"sets": 0, "lanterns": 0, "rail_cells": 0, "pillars": 0}
        self.build_air()
        self.build_fittings()
        self.build_ore()

    # -- carved volume
    def put_box(self, box, level, dist, stope=0, pillars=()):
        x0, y0, z0, x1, y1, z1 = box
        self.air_boxes.append(box)
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                if (x, z) in pillars:
                    continue
                for y in range(y0, y1 + 1):
                    dd = dist(x, z) if callable(dist) else dist
                    self.air[(x, y, z)] = (level, dd, stope)

    def run_cells(self, r):
        return [(r["x0"] + r["d"][0] * i, r["z0"] + r["d"][1] * i, i) for i in range(r["n"] + 1)]

    def build_air(self):
        L = self.L
        g = L.geo
        for r in L.runs:
            F = L.levels[r["level"]]
            d = r["d"]
            (xa, za, _), (xb, zb, _) = self.run_cells(r)[0], self.run_cells(r)[-1]
            x0, x1 = sorted((xa, xb))
            z0, z1 = sorted((za, zb))
            if d[0] != 0:
                z0, z1 = z0 - 1, z1 + 1
            else:
                x0, x1 = x0 - 1, x1 + 1
            along = (lambda x, z, r=r: r["d0"] + abs(((x - r["x0"]) * r["d"][0] + (z - r["z0"]) * r["d"][1]) - r["root_i"]))
            self.put_box((x0, F + 1, z0, x1, F + r["height"], z1), r["level"], along)
        for inc in L.inclines:
            F = L.levels[inc["level"]]
            dd = inc["d"]
            perp = (-dd[1], dd[0])
            run = L.runs[inc["run"] - 1]
            base_d = run["d0"] + abs(inc["at"] - run["root_i"])
            for s in range(1, inc["steps"] + 1):
                cx, cz = inc["x0"] + dd[0] * s, inc["z0"] + dd[1] * s
                y = F - s + 1
                xs = sorted((cx - perp[0], cx + perp[0]))
                zs = sorted((cz - perp[1], cz + perp[1]))
                self.put_box((xs[0], y + 1, zs[0], xs[1], y + g["main_height"], zs[1]), inc["level"], base_d + s)
        for sh in L.shafts:
            F = L.levels[sh["level"]]
            lo = L.levels[sh["level"] + 1]
            run = L.runs[sh["run"] - 1]
            self.put_box((sh["x"], lo + 1, sh["z"], sh["x"], F + g["side_height"], sh["z"]), sh["level"],
                         run["d0"] + abs(sh["at"] - run["root_i"]) + 1)
        P = g["pillar_pitch"]
        for st in L.stopes:
            F = L.levels[st["level"]]
            dd, E = st["d"], st["E"]
            ep = (-dd[1], dd[0])
            half = st["width"] // 2
            pil = set()
            for f in range(1, st["len"] + 1):
                for l in range(-half, half + 1):
                    m = l + half
                    if f >= 5 and f <= st["len"] - 2 and abs(l) <= half - 2 and (f - 1) % P in (2, 3) and m % P in (2, 3):
                        pil.add((E[0] + dd[0] * f + ep[0] * l, E[1] + dd[1] * f + ep[1] * l))
            st["pillars"] = sorted(pil)
            self.put_box((st["x0"], F + 1, st["z0"], st["x1"], F + st["height"], st["z1"]), st["level"], st["d0"], 1, pil)

    # -- fittings
    def fit(self, box, block):
        x0, y0, z0, x1, y1, z1 = box
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                for y in range(y0, y1 + 1):
                    self.fix[(x, y, z)] = block
        self.fills.append((x0, y0, z0, x1, y1, z1, block))

    def build_fittings(self):
        L = self.L
        g, mat = L.geo, L.spec["materials"]
        rail_cells = [dict() for _ in L.levels]
        shaft_cells = {(sh["x"], sh["z"], sh["level"]) for sh in L.shafts} | {(sh["x"], sh["z"], sh["level"] + 1) for sh in L.shafts}
        # pillars first, in the host rock
        for st in L.stopes:
            F = L.levels[st["level"]]
            blk = mat["pillar_deepslate"] if F + 3 < 0 else mat["pillar_stone"]
            for (x, z) in st["pillars"]:
                self.fit((x, F + 1, z, x, F + st["height"], z), blk)
            self.counts["pillars"] += len(st["pillars"])
        # stairs
        for inc in L.inclines:
            F = L.levels[inc["level"]]
            dd = inc["d"]
            perp = (-dd[1], dd[0])
            face = NAME_OF[(-dd[0], -dd[1])]
            for s in range(1, inc["steps"] + 1):
                cx, cz = inc["x0"] + dd[0] * s, inc["z0"] + dd[1] * s
                xs = sorted((cx - perp[0], cx + perp[0]))
                zs = sorted((cz - perp[1], cz + perp[1]))
                self.fit((xs[0], F - s + 1, zs[0], xs[1], F - s + 1, zs[1]),
                         "%s[facing=%s,half=bottom,shape=straight]" % (mat["stair"], face))
        # ladders
        for sh in L.shafts:
            F = L.levels[sh["level"]]
            lo = L.levels[sh["level"] + 1]
            face = NAME_OF[(-sh["d"][0], -sh["d"][1])]
            self.fit((sh["x"], lo + 1, sh["z"], sh["x"], F + 2, sh["z"]), "%s[facing=%s]" % (mat["ladder"], face))
        # timber sets, the bed and the rails
        for r in L.runs:
            F = L.levels[r["level"]]
            h = r["height"]
            d = r["d"]
            perp = (-d[1], d[0])
            main = r["kind"] in MAIN_KINDS
            every = g["set_every_main"] if main else g["set_every_side"]
            sets = 0
            for i in range(0, r["n"] + 1):
                if i % every:
                    continue
                if i < 2 and r["parent"] is None and r["kind"] != "adit":
                    continue          # an incline's landing or a shaft's foot: no frame over the way in
                cx, cz = r["x0"] + d[0] * i, r["z0"] + d[1] * i
                posts = [(cx + perp[0] * s, cz + perp[1] * s) for s in (-2, 2)]
                beam = [(cx + perp[0] * s, cz + perp[1] * s) for s in (-2, -1, 0, 1, 2)]
                cells = [(x, y, z) for (x, z) in posts for y in range(F + 1, F + h + 1)] + [(x, F + h + 1, z) for (x, z) in beam]
                if any(c in self.air for c in cells):
                    continue
                for (x, z) in posts:
                    self.fit((x, F + 1, z, x, F + h, z), mat["post"])
                xs = sorted((beam[0][0], beam[-1][0]))
                zs = sorted((beam[0][1], beam[-1][1]))
                self.fit((xs[0], F + h + 1, zs[0], xs[1], F + h + 1, zs[1]),
                         "%s[axis=%s]" % (mat["beam"], "z" if d[0] != 0 else "x"))
                sets += 1
                self.counts["sets"] += 1
                if main and (sets % g["lantern_every_sets"]) == 1 and not (cx, F + h, cz) in self.fix:
                    self.fit((cx, F + h, cz, cx, F + h, cz), mat["lantern"])
                    self.counts["lanterns"] += 1
            if main:
                for i in range(0, r["n"] + 1):
                    cx, cz = r["x0"] + d[0] * i, r["z0"] + d[1] * i
                    if (i == 0 and self.is_shaft_foot(r)) or (cx, cz, r["level"]) in shaft_cells:
                        continue
                    rail_cells[r["level"]][(cx, cz)] = d
        for k, cells in enumerate(rail_cells):
            F = L.levels[k]
            # the bed
            for (x, z) in cells:
                self.fix[(x, F, z)] = L.spec["materials"]["bed"]
            beds = sorted(cells)
            for line in self.runs_of(beds, lambda c: None):
                (xa, za), (xb, zb) = line[0], line[-1]
                self.fills.append((min(xa, xb), F, min(za, zb), max(xa, xb), F, max(za, zb), mat["bed"]))
            shaped = {}
            for (x, z), d in cells.items():
                dirs = [nm for nm, (dx, dz) in DIRS.items() if (x + dx, z + dz) in cells]
                shaped[(x, z)] = self.rail_shape(dirs, d)
            for (x, z), sh in shaped.items():
                self.fix[(x, F + 1, z)] = "%s[shape=%s]" % (mat["rail"], sh)
            self.counts["rail_cells"] += len(cells)
            for line in self.runs_of(sorted(shaped), lambda c: shaped[c]):
                (xa, za), (xb, zb) = line[0], line[-1]
                self.fills.append((min(xa, xb), F + 1, min(za, zb), max(xa, xb), F + 1, max(za, zb),
                                   "%s[shape=%s]" % (mat["rail"], shaped[line[0]])))

    def is_shaft_foot(self, r):
        return any((r["x0"], r["z0"]) == (sh["x"], sh["z"]) for sh in self.L.shafts)

    @staticmethod
    def rail_shape(dirs, d):
        s = set(dirs)
        axis = "east_west" if d[0] != 0 else "north_south"
        if len(s) == 2 and not ({"east", "west"} <= s or {"north", "south"} <= s):
            a, b = sorted(s, key=lambda n: ("north", "south", "east", "west").index(n))
            return "%s_%s" % (a, b)
        if len(s) == 1:
            return "east_west" if (s & {"east", "west"}) else "north_south"
        return axis

    @staticmethod
    def runs_of(cells, key):
        """Straight runs of adjacent cells with the same key: each cell in exactly one run, the longer axis taken first."""
        cs = set(cells)
        out, seen = [], set()
        for c in sorted(cells):
            if c in seen:
                continue
            best = [c]
            for dx, dz in ((1, 0), (0, 1)):
                run, cur = [c], c
                while True:
                    nxt = (cur[0] + dx, cur[1] + dz)
                    if nxt in cs and nxt not in seen and key(nxt) == key(c):
                        run.append(nxt)
                        cur = nxt
                    else:
                        break
                if len(run) > len(best):
                    best = run
            out.append(best)
            seen.update(best)
        return out

    # -- ore
    def ore_block(self, o, y, x, z):
        if y < 0 or (y < 8 and M.h32(self.L.seed, self.L.sid, 71, x, y, z) % 8 > y):
            return o["deepslate"]
        return o["stone"]

    def build_ore(self):
        L = self.L
        cfg = L.spec["ores"]
        table = cfg["table"]
        cov = L.rules["cover_min"]
        pb = L.pbox
        cands = {}
        for (x, y, z), (lvl, dist, stope) in self.air.items():
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0)):
                c = (x + dx, y + dy, z + dz)
                if c in self.air or c in self.fix or c in cands:
                    continue
                cands[c] = (lvl, dist, stope)
        taken = set()
        for c in sorted(cands):
            x, y, z = c
            lvl, dist, stope = cands[c]
            if int(L.H[z - pb.z0, x - pb.x0]) - y < cov:
                continue
            u = (M.h32(L.seed, L.sid, 70, x, y, z) & 0xFFFFFF) / float(0x1000000)
            cum, pick = 0.0, None
            floor = L.levels[lvl]
            far = min(1.0, dist / float(cfg["far_blocks"]))
            for o in table:
                if floor > o["y_max"]:
                    continue
                p = o["p"] * (1 + o["depth_gain"] * lvl) * (1 + o["far_gain"] * far) * (cfg["stope_multiplier"] if stope else 1)
                cum += p
                if u < cum:
                    pick = o
                    break
            if pick is None:
                continue
            size = pick["vein"][0] + M.h32(L.seed, L.sid, 72, x, y, z) % (pick["vein"][1] - pick["vein"][0] + 1)
            cells = [c]
            for j in range(1, size * 3):
                if len(cells) >= size:
                    break
                base_c = cells[M.h32(L.seed, L.sid, 73, x, y, z, j) % len(cells)]
                o3 = M.h32(L.seed, L.sid, 74, x, y, z, j)
                n = (base_c[0] + o3 % 3 - 1, base_c[1] + (o3 // 3) % 3 - 1, base_c[2] + (o3 // 9) % 3 - 1)
                if n in cells or n in self.air or n in self.fix or n in taken:
                    continue
                if not (pb.x0 + 4 <= n[0] <= pb.x1 - 4 and pb.z0 + 4 <= n[2] <= pb.z1 - 4):
                    continue
                if int(L.H[n[2] - pb.z0, n[0] - pb.x0]) - n[1] < cov:
                    continue
                cells.append(n)
            for cc in cells:
                if cc in taken:
                    continue
                taken.add(cc)
                self.ores[cc] = self.ore_block(pick, cc[1], cc[0], cc[2])
            self.ore_counts[pick["id"]] = self.ore_counts.get(pick["id"], 0) + len(cells)


# ------------------------------------------------------------------ the functions

TILE = 128


def tiles_of(x0, z0, x1, z1):
    return [(tx, tz) for tx in range(x0 // TILE, x1 // TILE + 1) for tz in range(z0 // TILE, z1 // TILE + 1)]


def clip(box, tx, tz):
    x0, y0, z0, x1, y1, z1 = box
    xa, xb = max(x0, tx * TILE), min(x1, tx * TILE + TILE - 1)
    za, zb = max(z0, tz * TILE), min(z1, tz * TILE + TILE - 1)
    if xa > xb or za > zb:
        return None
    return (xa, y0, za, xb, y1, zb)


def fillline(box, block, filt=None):
    x0, y0, z0, x1, y1, z1 = box
    if (x0, y0, z0) == (x1, y1, z1) and not filt:
        return "setblock %d %d %d %s" % (x0, y0, z0, block)
    return "fill %d %d %d %d %d %d %s%s" % (x0, y0, z0, x1, y1, z1, block, (" " + filt) if filt else "")


def function_lines(L, m):
    """{tile: [lines]} for one network: per tile, carve, shell (water and lava to stone, 2 thick), carve again, fittings, ore."""
    shell = L.rules["shell"]
    mat = L.spec["materials"]
    tiles = {}

    def tile_lines(t):
        return tiles.setdefault(t, {"carve": [], "shell": [], "fit": [], "ore": []})

    for box in m.air_boxes:
        for (tx, tz) in tiles_of(box[0], box[2], box[3], box[5]):
            c = clip(box, tx, tz)
            if c:
                tile_lines((tx, tz))["carve"].append(fillline(c, AIR))
    shell_boxes = {(b[0] - shell, b[1] - shell, b[2] - shell, b[3] + shell, b[4] + shell, b[5] + shell) for b in m.air_boxes}
    for box in sorted(shell_boxes):
        for (tx, tz) in tiles_of(box[0], box[2], box[3], box[5]):
            c = clip(box, tx, tz)
            if c:
                tl = tile_lines((tx, tz))["shell"]
                tl.append("fill %d %d %d %d %d %d %s replace minecraft:water" % (c + (mat["shell_fill"],)))
                tl.append("fill %d %d %d %d %d %d %s replace minecraft:lava" % (c + (mat["shell_fill"],)))
    for (x0, y0, z0, x1, y1, z1, block) in m.fills:
        for (tx, tz) in tiles_of(x0, z0, x1, z1):
            c = clip((x0, y0, z0, x1, y1, z1), tx, tz)
            if c:
                tile_lines((tx, tz))["fit"].append(fillline(c, block))
    cells = {}
    for (x, y, z), b in m.ores.items():
        cells[(x, y, z)] = b
    for line in M.column_runs(cells):
        t = line.split()
        x, z = int(t[1]), int(t[3])           # fill x y0 z ... and setblock x y z ... both put x and z here
        tile_lines((x // TILE, z // TILE))["ore"].append(line)
    out = {}
    for t in sorted(tiles):
        d = tiles[t]
        head = ["# Generated by tools/mine_networks.py from data/mine_networks.json: %s, tile %d,%d (x%d-%d, z%d-%d)"
                % (L.net["id"], t[0], t[1], t[0] * TILE, t[0] * TILE + TILE - 1, t[1] * TILE, t[1] * TILE + TILE - 1),
                "# carve, then replace water and lava with stone %d blocks round every carved box, then carve again;"
                % shell, "# then timber, bed, rails, stairs, ladders, lanterns and pillars; then the ore"]
        body = (["# --- pass 1: carve"] + sorted(set(d["carve"])) + ["# --- shell: water and lava to stone, %d thick" % shell]
                + d["shell"] + ["# --- pass 2: carve again"] + sorted(set(d["carve"])) + ["# --- fittings"] + d["fit"]
                + ["# --- ore"] + d["ore"])
        out[t] = FL.ensure_loaded(head + body)
    return out


# ------------------------------------------------------------------ the checks this tool makes of itself

def self_check(L, m):
    """The hard rules over every carved cell, from the rasters the layout grew on. tools/mine_networks_audit.py repeats
    them from the built functions with its own derivation; this stops a bad layout being written at all."""
    out = []
    cov = L.rules["cover_min"]
    pb = L.pbox
    exempt = set()
    for a in L.net["adits"]:
        ax, az = a["portal"]
        dx, dz = DIRS[a["heading"]]
        for i in range(L.exempt_of(a) + 1):
            for l in range(-2, 3):
                exempt.add((ax + dx * i - dz * l, az + dz * i + dx * l))
    low = None
    wexact = W.dilate_sq(L.wet, L.rules["water_clear"])
    aexact = W.dilate_sq(L.auth, L.rules["authored_clear"])
    for (x, y, z) in m.air:
        iz, ix = z - pb.z0, x - pb.x0
        if wexact[iz, ix]:
            out.append("carved cell (%d, %d, %d) is within %d of water" % (x, y, z, L.rules["water_clear"]))
        if aexact[iz, ix]:
            out.append("carved cell (%d, %d, %d) is within %d of an authored place" % (x, y, z, L.rules["authored_clear"]))
        if int(L.H[iz, ix]) - y < cov and (x, z) not in exempt:
            out.append("carved cell (%d, %d, %d) has %d of ground over it, under %d" % (x, y, z, int(L.H[iz, ix]) - y, cov))
        if x < L.rules["x_min"]:
            out.append("carved cell (%d, %d, %d) is west of x_min" % (x, y, z))
        low = y if low is None else min(low, y)
    if low is not None and low < L.rules["y_floor_min"]:
        out.append("lowest carved y%d is under y_floor_min" % low)
    return out[:20]


# ------------------------------------------------------------------ build

def all_networks(spec=None, source_root=None):
    spec = spec or load()
    nets = []
    for net in spec["networks"]:
        L = Layout(spec, net, source_root).build()
        m = Model(L)
        nets.append((L, m))
    return nets


def pack_problems(spec, funcs):
    """Static rules: every spawn condition placed is allowed by a policy entry scoped to the mine networks."""
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    policy = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    allowed = {b for w in policy["whitelist"] if POLICY_SCOPE in (w.get("scope") or "") for b in w["blocks"]}
    placed = set()
    for lines in funcs.values():
        for ln in lines:
            t = ln.split()
            if not t or t[0].startswith("#"):
                continue
            if t[0] == "setblock":
                placed.add(base(t[4]))
            elif t[0] == "fill":
                placed.add(base(t[7]))
    return ["places %s, a spawn condition (data/spawn_blocks.json), and no data/spawn_block_policy.json entry scoped to %s allows it"
            % (b, POLICY_SCOPE) for b in sorted((placed & spawn) - allowed)]


def function_name(net_id, t):
    return "%s/%s_t_%d_%d" % (F_, net_id, t[0], t[1])


def build_functions(spec=None, funcs=None):
    """The function names step R9MN runs, in order: from the committed data when a built pack is not at hand."""
    if funcs is not None:
        return [function_name(n, t) for n in sorted(funcs) for t in sorted(funcs[n])]
    plan = json.loads(PLAN.read_text(encoding="utf-8")) if PLAN.is_file() else None
    if plan:
        return list(plan["build_functions"])
    raise MineError("no derived plan: run python tools/mine_networks.py build first")


def write(spec, nets, out=None, plan_path=None):
    out = Path(out or OUT)
    if out.exists():
        shutil.rmtree(out)
    fdir = out / "data" / NS / "function" / FOLDER
    fdir.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
        "Cobblers: the long mine networks (tools/mine_networks.py, data/mine_networks.json)"}}, indent=2) + "\n", encoding="utf-8")
    funcs, counts, stats = {}, {}, {}
    for L, m in nets:
        lines = function_lines(L, m)
        funcs[L.net["id"]] = lines
        for t, body in lines.items():
            bad = FL.check_lines(body, function_name(L.net["id"], t))
            if bad:
                raise MineError("function %s would be refused: %s" % (function_name(L.net["id"], t), bad[:3]))
            (fdir / ("%s_t_%d_%d.mcfunction" % ((L.net["id"],) + t))).write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
            counts[function_name(L.net["id"], t)] = sum(1 for b in body if b.strip() and not b.startswith("#"))
        stats[L.net["id"]] = block_stats(lines)
    probs = pack_problems(spec, {(n, t): b for n, d in funcs.items() for t, b in d.items()})
    if probs:
        raise MineError("; ".join(probs))
    order = sorted(counts, key=lambda s: (s.split("/")[1].rsplit("_t_", 1)[0], *map(int, s.rsplit("_t_", 1)[1].split("_"))))
    (fdir / "index.txt").write_text("\n".join(s.split("/")[1] for s in order) + "\n", encoding="utf-8", newline="\n")
    return funcs, counts, stats


def block_stats(lines):
    """Command lines and blocks written (fill volumes without a replace filter, setblocks) and scanned (filtered fills)."""
    n = written = scanned = 0
    for body in lines.values():
        for ln in body:
            t = ln.split()
            if not t or t[0].startswith("#") or t[0] == "forceload":
                continue
            n += 1
            if t[0] == "setblock":
                written += 1
            elif t[0] == "fill":
                a = [int(v) for v in t[1:7]]
                v = (abs(a[3] - a[0]) + 1) * (abs(a[4] - a[1]) + 1) * (abs(a[5] - a[2]) + 1)
                if "replace" in t:
                    scanned += v
                else:
                    written += v
    return {"command_lines": n, "blocks_written": written, "blocks_scanned_by_shell": scanned}


def plan_json(spec, nets, counts, stats):
    out = {}
    for L, m in nets:
        by_level = {}
        for r in L.runs:
            by_level.setdefault(r["level"] + 1, 0)
            by_level[r["level"] + 1] += r["n"]
        tc = towns_centres()
        a0 = L.net["adits"][0]["portal"]
        nt = min(tc, key=lambda q: (q[1] - a0[0]) ** 2 + (q[2] - a0[1]) ** 2)
        out[L.net["id"]] = {
            "name": L.net["name"], "levels": L.levels,
            "adits": [{"id": a["id"], "portal": a["portal"], "heading": a["heading"], "level": a["level"]} for a in L.net["adits"]],
            "nearest_town": nt[0], "nearest_town_distance": int(math.hypot(nt[1] - a0[0], nt[2] - a0[1])),
            "drift_length_blocks": L.length(), "drift_length_by_level": {str(k): v for k, v in sorted(by_level.items())},
            "runs": [{"id": r["id"], "level": r["level"] + 1, "kind": r["kind"], "x": r["x0"], "z": r["z0"],
                      "dx": r["d"][0], "dz": r["d"][1], "n": r["n"], "root": r["root_i"]} for r in L.runs],
            "inclines": [{"level": i["level"] + 1, "x": i["x0"], "z": i["z0"], "dx": i["d"][0], "dz": i["d"][1], "steps": i["steps"]}
                         for i in L.inclines],
            "shafts": [{"level": s["level"] + 1, "x": s["x"], "z": s["z"], "dx": s["d"][0], "dz": s["d"][1]} for s in L.shafts],
            "stopes": [{"level": s["level"] + 1, "bounds": [s["x0"], s["z0"], s["x1"], s["z1"]], "height": s["height"]} for s in L.stopes],
            "carved_cells": len(m.air), "ore_blocks": dict(sorted(m.ore_counts.items())), "fittings": m.counts,
            "stats": stats[L.net["id"]],
        }
    ordered = sorted(counts, key=lambda s: (s.split("/")[1].rsplit("_t_", 1)[0], *map(int, s.rsplit("_t_", 1)[1].split("_"))))
    return {"schema": "cobblers.derived.mine-networks/1", "build_functions": ordered, "commands": counts, "networks": out}


def report(nets):
    for L, m in nets:
        by = {}
        for r in L.runs:
            by.setdefault(r["level"] + 1, [0, 0])
            by[r["level"] + 1][0] += r["n"]
            by[r["level"] + 1][1] += 1
        a = L.net["adits"][0]
        print("%s: adit %s at %s heading %s, floor y%d; %d levels %s" % (L.net["id"], a["id"], a["portal"], a["heading"], L.levels[0],
                                                                            len(L.levels), L.levels))
        print("  drift %d blocks: %s; %d inclines, %d shafts, %d stopes, %d links; %d carved cells" % (
            L.length(), ", ".join("L%d %d in %d runs" % (k, v[0], v[1]) for k, v in sorted(by.items())),
            len(L.inclines), len(L.shafts), len(L.stopes), len(L.links), len(m.air)))
        print("  ore blocks %s; %d timber sets, %d lanterns, %d rail cells, %d pillars" % (
            m.ore_counts, m.counts["sets"], m.counts["lanterns"], m.counts["rail_cells"], m.counts["pillars"]))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("site", "report", "build"))
    p.add_argument("box", nargs="*", type=int)
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--source-root")
    p.add_argument("--inputs-root", help="accepted for tools/reapply.py prepare's sake; nothing is read from it")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    p.add_argument("--only", help="one network id")
    a = p.parse_args(argv)
    spec = load()
    if a.mode == "site":
        if len(a.box) != 4:
            raise SystemExit("site needs x0 z0 x1 z1")
        for o in site(spec, *a.box, top=a.top, source_root=a.source_root):
            print(json.dumps(o))
        return 0
    try:
        nets = all_networks(spec, a.source_root)
    except MineError as exc:
        raise SystemExit("FAILED: %s; nothing written" % exc)
    if a.only:
        nets = [(L, m) for L, m in nets if L.net["id"] == a.only]
    probs = []
    for L, m in nets:
        probs += L.problems
        probs += self_check(L, m)
    report(nets)
    if probs:
        for pr in probs[:40]:
            print("PROBLEM:", pr)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    if a.mode == "report":
        print("report: %d networks, 0 problems" % len(nets))
        return 0
    try:
        funcs, counts, stats = write(spec, nets)
    except MineError as exc:
        raise SystemExit("FAILED: %s" % exc)
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(plan_json(spec, nets, counts, stats), indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    tot = {k: sum(s[k] for s in stats.values()) for k in ("command_lines", "blocks_written", "blocks_scanned_by_shell")}
    print("wrote %s: %d networks, %d functions, %d command lines, %d blocks written, %d scanned by the shell; plan %s" % (
        OUT.relative_to(ROOT), len(nets), len(counts), tot["command_lines"], tot["blocks_written"], tot["blocks_scanned_by_shell"],
        PLAN.relative_to(ROOT)))
    return 0


# ------------------------------------------------------------------ siting

def towns_centres():
    doc = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))
    out = []
    for t in doc["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is not None:
            out.append((t["id"], (f["min_x"] + f["max_x"]) / 2.0, (f["min_z"] + f["max_z"]) / 2.0, f))
    return out


def site(spec, x0, z0, x1, z1, top=8, source_root=None):
    """Candidate adit portals in a box, best first: a portal where the ground rises into the hill (cover reached within 40
    blocks), scored by the free rock above its floor within 600 blocks and the straight run it opens. Coarse (4-block cells)."""
    rules = spec["rules"]
    pad = 40
    pb = W.Box(x0 - pad, z0 - pad, x1 + pad, z1 + pad)
    H = read_ground(pb, source_root)
    gm5 = W.min_filter(H, 2)
    wet = water_mask(pb, H, rules)
    fw = W.dilate_sq(wet, rules["water_clear"] + 2)
    fa = W.dilate_sq(W.authored_seed(pb), rules["authored_clear"] + 2)
    forbid = fw | fa
    pb.put_rect(forbid, pb.x0, pb.z0, rules["x_min"] + 1, pb.z1)
    S = 4
    hh, ww = (H.shape[0] // S) * S, (H.shape[1] // S) * S
    Hc, Wc = hh // S, ww // S
    gmc = gm5[:hh, :ww].reshape(Hc, S, Wc, S).min(axis=(1, 3))
    fc = forbid[:hh, :ww].reshape(Hc, S, Wc, S).any(axis=(1, 3))
    hc = H[:hh:S, :ww:S]
    R = 600 // S
    cov = rules["cover_min"] + spec["geometry"]["main_height"] + 1
    out = []
    for F in range(int(hc.min()), int(hc.max()) + 1):
        ok = (gmc >= F + cov) & ~fc
        ii = np.pad(np.cumsum(np.cumsum(ok.astype(np.int32), 0), 1), ((1, 0), (1, 0)))
        pz, px = np.nonzero((hc == F) & ~fc)
        for z, x in zip(pz, px):
            for dn, (dx, dz) in DIRS.items():
                good = True
                for kk in (8, 10, 12):
                    zz, xx = z + dz * kk, x + dx * kk
                    if not (0 <= zz < Hc and 0 <= xx < Wc and ok[zz, xx]):
                        good = False
                        break
                if not good:
                    continue
                n, zz, xx = 0, z + dz * 8, x + dx * 8
                while 0 <= zz < Hc and 0 <= xx < Wc and ok[zz, xx] and n < 250:
                    zz, xx, n = zz + dz, xx + dx, n + 1
                if n < 25:
                    continue
                za, zb, xa, xb = max(0, z - R), min(Hc, z + R), max(0, x - R), min(Wc, x + R)
                vol = int(ii[zb, xb] - ii[za, xb] - ii[zb, xa] + ii[za, xa]) * S * S
                out.append((vol, int(n * S), int(F), int(pb.x0 + x * S), int(pb.z0 + z * S), dn))
    out.sort(reverse=True)
    picked = []
    for o in out:
        if all((o[3] - p[3]) ** 2 + (o[4] - p[4]) ** 2 > 400 ** 2 for p in picked):
            picked.append(o)
        if len(picked) >= top:
            break
    tc = towns_centres()
    res = []
    for vol, reach, F, x, z, dn in picked:
        nt = min(tc, key=lambda q: (q[1] - x) ** 2 + (q[2] - z) ** 2)
        res.append({"portal": [x, z], "heading": dn, "floor": F, "free_rock_cells": vol, "straight_reach": reach,
                    "nearest_town": nt[0], "town_distance": int(math.hypot(nt[1] - x, nt[2] - z))})
    return res


if __name__ == "__main__":
    raise SystemExit(main())
