#!/usr/bin/env python
"""Parkour, version 2 (dungeons pass 2, unit PARKOUR2): replaces the kit's `parkour` kind (tools/dungeon_kinds.py).

The owner (2026-10-10): "The parkour should include longer and challenging jumps and not be a straight path."

WHAT IT BUILDS. A chasm room: a catch floor `pit` below, ledges (checkpoints) standing on pillars from it, and between
ledges a CHAIN of platforms the player jumps. The route winds across the room's width (legs along x and along z joined by
3x3 corner pads), climbs and falls (ledge and platform levels differ by up to `params.max_lv`, 4 by default), and one
section of three or more is a FORK: two chains from the same ledge to the same ledge, a short hard one (small platforms,
long jumps, a roller-coaster of heights) and a long safe one (wide platforms, short jumps, an S-bend). Either alone
connects the two ledges (tested by removing the other).

THE JUMPS ARE THE GRID'S (tools/dungeon_grid.py JUMP_FLAT_MAX 4, JUMP_RISE_MAX 3, DUNGEONS.md V6), counted in CELLS from
the take-off cell to the landing cell: flat 4 cells = an AIR gap of 3 blocks (the standard "4-block jump"), 3 cells with a
rise or fall of one = a gap of 2. Tier 1 hops are 2-3 cells, tier 2 3-4, tier 3 mostly 4 and 3. A 4-cell hop needs a
RUN-UP: the platform jumped from is at least 3 cells long along the jump (a standing jump does not carry 3 blocks of
air), so a 1-cell pole is only ever jumped from at 3 cells or fewer. Every jump is along an axis (the grid's and the
independent audit's edges are axis-aligned), the platforms of consecutive hops share the row (or column) jumped along,
and the planner rejects a layout in which any two platforms that are not meant to be joined are within the grid's reach
of each other (no short cuts). These are the player's rules as the checks model them; whether they FEEL right is the
owner's look (unproven).

NEVER THE VOID. The catch floor lies under every column; a fall onto it costs `clock.fall_penalty_s`, gives resistance
(F1, EXP-075: fall distance survives a teleport) and teleports to the last ledge stood on (`dg.ck`), exactly the protocol
of the kit's parkour so the independent audit reads it unchanged: a tick line `execute if entity @s[<catch box>] run
function <room>/fall`, `scoreboard players set @s dg.ck <i>` lines for the ledge boxes, and `execute if score @s dg.ck
matches <i> run tp @s ...` in the fall, behind a guard that sends a stale value to ledge 0.

RECORD. {"kind": "parkour", "length": 110, "width": 35, "height": 12, "params": {...}}; height at least 7 (the kit's
check); a platform's standing level is at most `height - 6` above the door's. params, all optional: sections (default
length // 33, at least 2), tiers (per section 1..3; default 1,2,3,3,2...), max_lv (4), fork (true when there are 3 or more
sections; false turns it off; an int is the section index), seed (re-roll). The room is a BOX: a non-box `shape` is refused.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_rooms as R  # noqa: E402
import dungeon_kinds  # noqa: E402,F401  (registers the kit's parkour FIRST, so this module's registration below wins however it is imported)
from dungeon_rooms import fill, setb, rng  # noqa: E402

LEDGE_L = 6          # a ledge is 6 long (x)
LEDGE_W = 7          # and 7 wide; a fork's are FORK_W
FORK_W = 15
PAD = 3              # a corner pad is 3x3
MARGIN = 3           # no platform centre closer than this to a side wall
FLAT_MAX = 4         # dungeon_grid.JUMP_FLAT_MAX, cells
RUN_UP = 3           # a hop of FLAT_MAX cells is taken from a platform at least this long along the jump
RISE_MAX = 3         # dungeon_grid.JUMP_RISE_MAX, cells
TIER_DEFAULT = [1, 2, 3, 3, 2]
LOADED = "# chunks-loaded-by: the member standing in the room (its chunks are loaded)"


def U(doc):
    c = doc["engine"]["clock"]
    return c["units_per_tick"] * 20


class Plat:
    """A rectangle of standing cells at one level (feet level is fy + lv)."""
    __slots__ = ("x0", "x1", "z0", "z1", "lv", "kind", "idx", "branch")

    def __init__(self, x0, x1, z0, z1, lv, kind, branch=None):
        self.x0, self.x1, self.z0, self.z1, self.lv, self.kind, self.branch = x0, x1, z0, z1, lv, kind, branch
        self.idx = -1

    def center(self):
        return ((self.x0 + self.x1) // 2, (self.z0 + self.z1) // 2)


class Route:
    def __init__(self):
        self.plats = []
        self.hops = []          # dicts: a, b (plat indices), axis, dir, n (cells), dy, branch

    def add(self, p):
        p.idx = len(self.plats)
        self.plats.append(p)
        return p


# ------------------------------------------------------------------------------------------------- the hop planner


def _tier_opts(tier, relaxed):
    """(hop sizes in cells, platform lengths) by tier; the lists are weighted by repeating."""
    if relaxed:
        return [2, 3, 4], [1, 2, 3]
    return {1: ([2, 3], [3]), 2: ([3, 4, 3, 2], [3, 2, 3]), 3: ([4, 3, 4, 3, 2], [1, 2, 3, 1])}[tier]


def plan_hops(rg, D, tier, prev_len, end_len, relaxed=False):
    """[(n, wlen)]: hops covering D cells from the take-off cell to the landing cell of the last. n is the hop in cells,
    wlen the along-axis length of the platform landed on (the last is `end_len`). A 4-cell hop needs prev >= 3."""
    N, W = _tier_opts(tier, relaxed)
    fail = set()

    def order(ns):
        """Longest hops first on the harder tiers (a quarter of the time swapped with its neighbour), shuffled on tier 1."""
        ns = sorted(set(ns), reverse=True)
        if tier == 1 or relaxed:
            rg.shuffle(ns)
        else:
            for i in range(len(ns) - 1):
                if rg.random() < 0.25:
                    ns[i], ns[i + 1] = ns[i + 1], ns[i]
        return ns

    def go(rem, prev):
        if (rem, prev) in fail:
            return None
        ns = order(N)
        for n in ns:
            if n == rem and (n < FLAT_MAX or prev >= RUN_UP):
                return [(n, end_len)]
        for n in ns:
            if n == FLAT_MAX and prev < RUN_UP:
                continue
            ws = sorted(set(W), reverse=True)        # a long platform first: it is the run-up for the next long hop
            if tier == 1 or relaxed or rg.random() < 0.3:
                rg.shuffle(ws)
            for w in ws:
                r2 = rem - n - (w - 1)
                if r2 < 2:
                    continue
                sub = go(r2, w)
                if sub:
                    return [(n, w)] + sub
        fail.add((rem, prev))
        return None
    out = go(D, prev_len)
    if out is None and not relaxed:
        return plan_hops(rg, D, tier, prev_len, end_len, True)
    return out


def assign_dy(rg, hops, lv0, lv1, lvmax, wiggle):
    """A dy in {-1, 0, 1} per hop (only hops of 3 cells or fewer change level) summing to lv1 - lv0, the running level in
    0..lvmax; `wiggle` extra up-and-down pairs where there is room. None when it cannot be done."""
    elig = [i for i, (n, _w) in enumerate(hops) if n <= RISE_MAX]
    need = lv1 - lv0
    if abs(need) > len(elig):
        return None
    for _ in range(80):
        dy = [0] * len(hops)
        for i in (rg.sample(elig, abs(need)) if need else []):
            dy[i] = 1 if need > 0 else -1
        spare = [i for i in elig if dy[i] == 0]
        for _k in range(wiggle):
            if len(spare) < 2:
                break
            i, j = sorted(rg.sample(spare, 2))
            s = rg.choice((1, -1))
            dy[i], dy[j] = s, -s
            spare = [t for t in spare if t not in (i, j)]
        lv, ok = lv0, True
        for d_ in dy:
            lv += d_
            if not 0 <= lv <= lvmax:
                ok = False
                break
        if ok and lv == lv1:
            return dy
    return None


# ------------------------------------------------------------------------------------------------- legs


def _rect(axis, a0, a1, b0, b1):
    a0, a1 = min(a0, a1), max(a0, a1)
    b0, b1 = min(b0, b1), max(b0, b1)
    return (a0, a1, b0, b1) if axis == "x" else (b0, b1, a0, a1)


def _along(p, axis):
    return (p.x0, p.x1) if axis == "x" else (p.z0, p.z1)


def _across(p, axis):
    return (p.z0, p.z1) if axis == "x" else (p.x0, p.x1)


def build_leg(rg, route, cur, take, axis, sgn, tier, lvmax, end, wiggle=0, branch=None, lv_end=None, D=None):
    """One straight leg of hops from platform `cur`, take-off cell `take` = (x, z), along `axis` in direction `sgn`.
    `end` is ("pad",) (a new 3x3 corner pad; D and lv_end given) or ("to", P) (the existing platform P, landed on at its
    near edge in the row/column jumped along; D and lv_end follow from it). Returns the platform the leg ends on."""
    a_take, lat = (take[0], take[1]) if axis == "x" else (take[1], take[0])
    if end[0] == "to":
        P = end[1]
        lo, hi = _along(P, axis)
        a_land = lo if sgn > 0 else hi
        D = (a_land - a_take) * sgn
        b0, b1 = _across(P, axis)
        if not b0 <= lat <= b1:
            raise R.RoomError("parkour: the row %d jumped along misses the platform it lands on (%d..%d)" % (lat, b0, b1))
        lv_end = P.lv
        end_len = hi - lo + 1
    else:
        end_len = PAD
    if D < 2:
        raise R.RoomError("parkour: a leg of %d cells is too short to jump" % D)
    cl = _along(cur, axis)
    prev_len = cl[1] - cl[0] + 1
    hops = dy = None
    for _attempt in range(120):
        hops = plan_hops(rg, D, tier, prev_len, end_len)
        if hops is None:
            break
        dy = assign_dy(rg, hops, cur.lv, lv_end, lvmax, wiggle if tier >= 2 else 0)
        if dy is not None:
            break
    if hops is None or dy is None:
        raise R.RoomError("parkour: no chain of hops covers %d cells from level %d to %d on tier %d" % (D, cur.lv, lv_end, tier))
    a, lv, prev = a_take, cur.lv, cur
    tier_w = _tier_opts(tier, False)[1]
    for k, ((n, wlen), d_) in enumerate(zip(hops, dy)):
        last = k == len(hops) - 1
        a_land = a + sgn * n
        lv += d_
        if last and end[0] == "to":
            p = end[1]
        else:
            if last:
                ax0, ax1, b0, b1, kind = a_land, a_land + sgn * (PAD - 1), lat - 1, lat + 1, "pad"
            else:
                d = rg.choice(tier_w)
                off = rg.randint(0, d - 1)
                ax0, ax1, b0, b1, kind = a_land, a_land + sgn * (wlen - 1), lat - off, lat - off + d - 1, "plat"
            x0, x1, z0, z1 = _rect(axis, ax0, ax1, b0, b1)
            p = route.add(Plat(x0, x1, z0, z1, lv, kind, branch))
        route.hops.append({"a": prev.idx, "b": p.idx, "axis": axis, "dir": sgn, "n": n, "dy": d_, "branch": branch, "lat": lat})
        a = (_along(p, axis)[1] if sgn > 0 else _along(p, axis)[0])
        prev = p
    return prev


def _pad_take(pad, axis, sgn):
    """The take-off cell on a corner pad for a leg along `axis` in direction `sgn` (the pad's centre row/column)."""
    cx, cz = pad.center()
    if axis == "x":
        return (pad.x1 if sgn > 0 else pad.x0, cz)
    return (cx, pad.z1 if sgn > 0 else pad.z0)


def _mid_level(rg, a, b, lvmax, tier):
    lo, hi = min(a, b), max(a, b)
    if tier >= 2:
        lo, hi = max(0, lo - 1), min(lvmax, hi + 1)
    return rg.randint(lo, hi)


def chain_straight(rg, route, A, B, row, tier, lvmax, wiggle, branch=None):
    return build_leg(rg, route, A, (A.x1, row), "x", 1, tier, lvmax, ("to", B), wiggle, branch)


def chain_z(rg, route, A, B, row0, rowB, tier, lvmax, wiggle, branch=None):
    """x along row0 to a pad, z to a second pad at rowB, x into B (two bends)."""
    t = 1 if rowB > row0 else -1
    lo = A.x1 + 3
    hi = B.x0 - PAD - 3
    if hi < lo:
        raise R.RoomError("parkour: %d cells between ledges are too few for a bend" % (B.x0 - A.x1))
    xp = rg.randint(lo + (hi - lo) // 4, hi - (hi - lo) // 4)
    l1 = _mid_level(rg, A.lv, B.lv, lvmax, tier)
    pad1 = build_leg(rg, route, A, (A.x1, row0), "x", 1, tier, lvmax, ("pad",), wiggle, branch, l1, xp - A.x1)
    cx = pad1.center()[0]
    l2 = _mid_level(rg, l1, B.lv, lvmax, tier)
    Dz = abs(rowB - row0) - 2
    pad2 = build_leg(rg, route, pad1, (cx, row0 + t), "z", t, tier, lvmax, ("pad",), wiggle, branch, l2, Dz)
    return build_leg(rg, route, pad2, _pad_take(pad2, "x", 1), "x", 1, tier, lvmax, ("to", B), wiggle, branch)


def chain_via(rg, route, A, B, row0, rowM, rowB, tier, lvmax, wiggle, branch=None, flat=False):
    """Five legs and four pads: x along row0, z out to rowM, x along rowM, z to rowB, x into B (two bends each way). The
    fork's long way and every section whose ledges are level with each other in z."""
    t1 = 1 if rowM > row0 else -1
    t2 = 1 if rowB > rowM else -1
    lo = A.x1 + 3
    hi = B.x0 - PAD - 3
    xp1 = lo + (hi - lo) // 5
    xp2 = hi - (hi - lo) // 5
    if xp2 - (xp1 + PAD - 1) < 3 or abs(rowM - row0) < 4 or abs(rowB - rowM) < 4:
        raise R.RoomError("parkour: no room for a detour (%d cells between ledges, rows %d %d %d)" % (B.x0 - A.x1, row0, rowM, rowB))
    lv = A.lv

    def mid(a, b):
        return lv if flat else _mid_level(rg, a, b, lvmax, tier)
    l1, l2, l3 = mid(A.lv, B.lv), mid(A.lv, B.lv), mid(A.lv, B.lv)
    w = 0 if flat else wiggle
    pad1 = build_leg(rg, route, A, (A.x1, row0), "x", 1, tier, lvmax, ("pad",), w, branch, l1, xp1 - A.x1)
    pad2 = build_leg(rg, route, pad1, (pad1.center()[0], row0 + t1), "z", t1, tier, lvmax, ("pad",), w, branch, l2, abs(rowM - row0) - 2)
    pad3 = build_leg(rg, route, pad2, _pad_take(pad2, "x", 1), "x", 1, tier, lvmax, ("pad",), w, branch, l2, xp2 - pad2.x1)
    pad4 = build_leg(rg, route, pad3, (pad3.center()[0], rowM + t2), "z", t2, tier, lvmax, ("pad",), w, branch, l3, abs(rowB - rowM) - 2)
    return build_leg(rg, route, pad4, _pad_take(pad4, "x", 1), "x", 1, tier, lvmax, ("to", B), w, branch)


# ------------------------------------------------------------------------------------------------- the plan of one room


def sections_of(room):
    L = room["ix1"] - room["ix0"] + 1
    return int(room["params"].get("sections", max(2, L // 33)))


def _fork_index(room, S):
    f = room["params"].get("fork", S >= 3)
    if f is True:
        i = S // 2
    elif f in (False, None):
        return None
    else:
        i = int(f)
    return i if 1 <= i <= S - 2 else None


def shortcuts(route, fork_pairs=()):
    """Platform pairs the grid lets a player cross that no hop of the plan joins (a flat gap of up to 3 blocks, a rise or
    fall of one over up to 2, along a shared row or column; an overlap or adjacency counts)."""
    joined = {frozenset((h["a"], h["b"])) for h in route.hops}
    out = []
    ps = [p for p in route.plats if p is not None]
    for i, p in enumerate(ps):
        for q in ps[i + 1:]:
            if frozenset((p.idx, q.idx)) in joined:
                continue
            dl = abs(p.lv - q.lv)
            if dl > 1:
                continue
            lim = FLAT_MAX if dl == 0 else RISE_MAX
            zr = not (p.z1 < q.z0 or q.z1 < p.z0)
            xr = not (p.x1 < q.x0 or q.x1 < p.x0)
            gx = max(q.x0 - p.x1, p.x0 - q.x1)       # cells from edge cell to edge cell (<= 0: overlapping)
            gz = max(q.z0 - p.z1, p.z0 - q.z1)
            if (zr and gx <= lim) or (xr and gz <= lim):
                out.append((p.idx, q.idx))
    return out


def plan_route(d, room):
    """The route of a parkour room: (Route, ledges, lvmax, fork index). Deterministic in the dungeon and room ids; a plan
    with a short cut or that does not fit is re-rolled (up to 40 times) before the room is refused."""
    p = room["params"]
    err = None
    for attempt in range(40):
        try:
            return _plan_once(rng(d, room, "parkour2:%s:%d" % (p.get("seed", 0), attempt)), room)
        except R.RoomError as e:
            err = e
    raise R.RoomError("%s room %s: no parkour route after 40 tries: %s" % (d["id"], room["id"], err))


def _plan_once(rg, room):
    p = room["params"]
    ix0, ix1, iz0, iz1 = room["ix0"], room["ix1"], room["iz0"], room["iz1"]
    L = ix1 - ix0 + 1
    S = sections_of(room)
    lvmax = max(1, min(int(p.get("max_lv", 4)), room["height"] - 6))
    tiers_in = p.get("tiers")
    tiers = [int(tiers_in[i % len(tiers_in)]) if tiers_in else TIER_DEFAULT[min(i, len(TIER_DEFAULT) - 1)] for i in range(S)]
    fork_i = _fork_index(room, S)
    xs = [ix0 + round(i * (L - LEDGE_L) / S) for i in range(S + 1)]
    z_in, z_out = room["z_in"], room["z_out"]
    zlo, zhi = iz0 + MARGIN + 3, iz1 - MARGIN - 3
    if zhi - zlo < 8 or L < 30 * S - 10:
        raise R.RoomError("parkour: %d sections do not fit a room %d long and %d wide" % (S, L, iz1 - iz0 + 1))
    # ledge z centres: a zig-zag between the two sides, so every section bends
    zc = [z_in]
    for i in range(1, S):
        zc.append(zhi - rg.randint(0, 2) if i % 2 else zlo + rg.randint(0, 2))
    zc.append(z_out)
    wid = [LEDGE_W] * (S + 1)
    if fork_i is not None:
        wid[fork_i] = wid[fork_i + 1] = FORK_W
        half = FORK_W // 2
        mid = (iz0 + iz1) // 2
        # the fork sits mid-room, pulled toward the hard side as far as the safe way needs for its full detour (a bulge of
        # 8 past its row, below) and the hard row allows (no nearer the wall than MARGIN): in a narrow room the middle
        # left the safe way 5 and it was barely the long way (the ruin's aqueduct, 29 wide, DG2-INTEGRATE)
        zf = min(mid, (iz1 - MARGIN) - 8 - 6)
        zf = max(zf, iz0 + MARGIN + 6)
        zc[fork_i] = zc[fork_i + 1] = min(max(zf, iz0 + 1 + half), iz1 - 1 - half)
    # ledge levels: 0 at the doors, 0..lvmax between, a step of at most 3 from the one before
    lvs = [0]
    for i in range(1, S):
        lvs.append(rg.randint(max(0, lvs[-1] - 3), min(lvmax, lvs[-1] + 3)))
    lvs.append(0)
    for i in range(S - 1, 0, -1):
        lvs[i] = min(lvs[i], lvs[i + 1] + 3)
    if fork_i is not None:
        lvs[fork_i + 1] = lvs[fork_i]
    # a full parkour (three sections or more) climbs: some ledge stands at least 3 above the doors (or the room's whole
    # headroom). A roll that keeps every ledge at 0..2 is a flat walk with hops and is re-rolled (DUNGEON_PASS2 note 4; the
    # night shift's collapse, slot 1, 2026-10-10, climbed 2). A short room of two sections keeps its free roll
    if S >= 3 and max(lvs) < min(3, lvmax):
        raise R.RoomError("parkour: the ledges never climb %d (levels %s)" % (min(3, lvmax), lvs))
    route = Route()
    ledges = []
    for i in range(S + 1):
        hw = (wid[i] - 1) // 2
        ledges.append(route.add(Plat(xs[i], xs[i] + LEDGE_L - 1, zc[i] - hw, zc[i] + wid[i] // 2, lvs[i], "ledge")))
    for i in range(S):
        A, B = ledges[i], ledges[i + 1]
        if i == fork_i:
            zf = zc[i]
            hard_row, safe_row = zf - 6, zf + 6
            bulge = min(8, (iz1 - MARGIN) - safe_row)
            chain_straight(rg, route, A, B, hard_row, 3, lvmax, 2, "hard")
            chain_via(rg, route, A, B, safe_row, safe_row + bulge, safe_row, 1, lvmax, 0, "safe", flat=True)
        else:
            r0, rB = zc[i], zc[i + 1]
            if abs(rB - r0) >= 8:
                chain_z(rg, route, A, B, r0, rB, tiers[i], lvmax, 1)
            else:
                # the ledges sit level in z: go out to the far side and back, so no section is a straight walk
                mid_z = (zlo + zhi) // 2
                rM = zhi - rg.randint(0, 2) if (r0 + rB) / 2 <= mid_z else zlo + rg.randint(0, 2)
                chain_via(rg, route, A, B, r0, rM, rB, tiers[i], lvmax, 1)
    # a full parkour (three sections or more) has hard jumps: at least 4 hops of FLAT_MAX cells (a gap of 3), however the
    # tiers rolled (DUNGEON_PASS2 note 4: "longer and challenging jumps"; the jungle's canopy, slot 7, rolled 3)
    if S >= 3 and sum(1 for h in route.hops if h["n"] == FLAT_MAX) < 4:
        raise R.RoomError("parkour: only %d hops of %d cells" % (sum(1 for h in route.hops if h["n"] == FLAT_MAX), FLAT_MAX))
    cuts = shortcuts(route)
    if cuts:
        raise R.RoomError("parkour: platforms %s can be crossed without the plan's hops" % (cuts[:3],))
    for q in route.plats:
        pad = 0 if q.kind == "ledge" else 1
        if not (ix0 + pad <= q.x0 and q.x1 <= ix1 - pad and iz0 + pad <= q.z0 and q.z1 <= iz1 - pad):
            raise R.RoomError("parkour: a platform at x %d..%d z %d..%d leaves the room" % (q.x0, q.x1, q.z0, q.z1))
    return route, ledges, lvmax, fork_i


# ------------------------------------------------------------------------------------------------- the kind


def kind_parkour2(doc, d, slot, room, theme):
    t = theme["parkour"]
    fy = room["floor_in"]
    y_lo = room["y_lo"]
    ix0, ix1, iz0, iz1 = room["ix0"], room["ix1"], room["iz0"], room["iz1"]
    route, ledges, lvmax, fork_i = plan_route(d, room)
    light = theme["hull"]["light"]
    ops = [fill((ix0, y_lo - 1, iz0, ix1, y_lo - 1, iz1), t["catch_floor"])]
    lights = []
    platforms, ck, ck_boxes = [], [], []
    for p in route.plats:
        top = fy + p.lv
        if p.kind == "ledge":
            ops.append(fill((p.x0, y_lo, p.z0, p.x1, top - 2, p.z1), t["pillar"]))
            ops.append(fill((p.x0, top - 1, p.z0, p.x1, top - 1, p.z1), t["ledge"]))
            if p.x1 - p.x0 >= 3 and p.z1 - p.z0 >= 3:
                ops.append(fill((p.x0 + 1, top - 1, p.z0 + 1, p.x1 - 1, top - 1, p.z1 - 1), t["ledge_top"]))
            # a light set flush in the ledge's top at each corner of its inner field: a ledge is lit from below
            for lx in (p.x0 + 1, p.x1 - 1):
                for lz in (p.z0 + 1, p.z1 - 1):
                    ops.append(setb((lx, top - 1, lz), light))
                    lights.append((lx, top - 1, lz))
            if p.z1 - p.z0 > 8:
                zm = (p.z0 + p.z1) // 2
                for lx in (p.x0 + 1, p.x1 - 1):
                    ops.append(setb((lx, top - 1, zm), light))
                    lights.append((lx, top - 1, zm))
            cx, cz = p.center()
            ck.append([cx, top, cz, -90])
            ck_boxes.append([p.x0, top, p.z0, p.x1, top + 2, p.z1])
        else:
            cx, cz = p.center()
            ops.append(fill((cx, y_lo, cz, cx, top - 2, cz), t["pillar"]))
            ops.append(fill((p.x0, top - 1, p.z0, p.x1, top - 1, p.z1), t["ledge_top"] if p.kind == "pad" else t["platform"]))
            platforms.append([cx, top, cz])
    # cracked lamps across the entry ledge's west edge: the no-deploy box's edge (3.4)
    ops.append(fill((ix0, fy - 1, room["z_in"] - 3, ix0, fy - 1, room["z_in"] + 3), theme["lamp"]))
    # catch floor lights, flush, so nothing walkable is dark
    for lx in range(ix0 + 4, ix1, 8):
        for lz in range(iz0 + 4, iz1, 8):
            ops.append(setb((lx, y_lo - 1, lz), light))
            lights.append((lx, y_lo - 1, lz))
    pen = int(doc["engine"]["clock"]["fall_penalty_s"]) * U(doc)
    catch = [ix0, y_lo, iz0, ix1, y_lo + 1, iz1]
    tick = [LOADED, "effect give @s minecraft:resistance 2 4 true"]
    for i, bx in enumerate(ck_boxes):
        tick.append("execute if entity @s[%s] run scoreboard players set @s dg.ck %d" % (R.sel_box(bx), i))
    tick.append("execute if entity @s[%s] run function %s" % (R.sel_box(catch), R.room_fn(d, room, slot, "fall")))
    fall = [R.HEAD, LOADED, "# a fall onto the catch floor: back to the last ledge stood on, the clock charged, no damage (F1: resistance)",
            "scoreboard players remove @s dg.clock %d" % pen,
            "effect give @s minecraft:resistance 3 4 true",
            # dg.ck is the member's own and other rooms set it: a value this room does not own means the first ledge
            # (DG-AUDIT finding 1, the collapse bridges)
            "execute unless score @s dg.ck matches 0..%d run scoreboard players set @s dg.ck 0" % (len(ck) - 1)]
    for i, c in enumerate(ck):
        fall.append("execute if score @s dg.ck matches %d run tp @s %d.5 %d %d.5 %d 0" % (i, c[0], c[1], c[2], c[3]))
    fall += ["playsound minecraft:entity.player.hurt master @s ~ ~ ~ 0.6 1",
             "title @s actionbar %s" % R.text(theme["messages"]["fall"].replace("{s}", str(doc["engine"]["clock"]["fall_penalty_s"])), "red")]
    hops = []
    pl = route.plats
    for h in route.hops:
        a, b = pl[h["a"]], pl[h["b"]]
        hops.append({"from": [a.x0, a.x1, a.z0, a.z1, fy + a.lv], "to": [b.x0, b.x1, b.z0, b.z1, fy + b.lv],
                     "axis": h["axis"], "dir": h["dir"], "n": h["n"], "dy": h["dy"], "branch": h["branch"], "lat": h["lat"]})
    anchors = {"checkpoints": ck, "platforms": platforms, "catch": catch, "center": ck[len(ck) // 2]}
    if fork_i is not None:
        anchors["fork"] = [ck[fork_i], ck[fork_i + 1]]
    branches = {}
    for h in route.hops:
        if h["branch"]:
            for key in ("a", "b"):
                q = pl[h[key]]
                if q.kind != "ledge":
                    branches.setdefault(h["branch"], [])
                    cell = [q.center()[0], fy + q.lv, q.center()[1]]
                    if cell not in branches[h["branch"]]:
                        branches[h["branch"]].append(cell)
    return {"blocks": ops, "anchors": anchors, "lights": lights,
            "functions": {"fall": fall, "enter": ["scoreboard players set @s dg.ck 0"], "tick": tick},
            "meta": {"light_ref_y": fy, "extra_drop": 0, "ledges": [[p.x0, p.x1, p.z0, p.z1, fy + p.lv] for p in ledges],
                     "platform_count": len(platforms), "hops": hops, "fork": fork_i, "branches": branches, "max_lv": lvmax,
                     "jump_limits": {"flat_cells": FLAT_MAX, "rise_cells": RISE_MAX}}}


def check_parkour2(doc, d, slot):
    bad = []
    for r in R.layout(doc, d, slot):
        if r["kind"] != "parkour":
            continue
        lab = "%s room %s" % (d["id"], r["id"])
        if r.get("shape") not in (None, "box"):
            bad.append("%s: a parkour is a box (shape %r): its catch floor and pillars are rectangular" % (lab, r.get("shape")))
        L = r["ix1"] - r["ix0"] + 1
        if L < 40:
            bad.append("%s: a parkour is at least 42 long (this one is %d)" % (lab, r["length"]))
        if r["width"] < 17:
            bad.append("%s: a parkour is at least 17 wide" % lab)
        if r["height"] < 7:
            continue                    # the kit's check names it
        try:
            plan_route(d, r)
        except R.RoomError as e:
            bad.append(str(e))
    return bad


R.register("parkour", kind_parkour2, dress="none", pit=6, no_deploy=True, jumps=True)
R.EXTRA_CHECKS.append(check_parkour2)
