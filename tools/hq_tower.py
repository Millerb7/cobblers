#!/usr/bin/env python
"""The Compact HQ tower's interior and its two per-player gates: build/datapacks/cobblers_hq_tower.

tools/deep_city.py (R9DC) builds the HQ tower as a sealed shell: walls on its 11 by 11 box, a floor every 6 and no way
in. This pack, run by tools/reapply.py step R9HQ after R9DC and R9RU, makes it the finale's building
(docs/story/NPCS_AND_RIFT_FINALE.md, Scenes 2-4; data/hq_tower.json): eleven storeys of a factory -- intake, briefing
hall, a double-height foundry with its catwalk, labs, records, a double-height relay hall with its catwalk, barracks,
the director's office and anchor control at the top -- one stair flight a storey, a door cut through the tower's east
wall into the ring-0 section's guarded room, and four cache barrels (data/hq_tower.json hq_caches, the hook the
obtainability sweep fills).

The gates are a tick function, not blocks (data/hq_tower.json gates): every 10 ticks each player near the tower is
tagged from their own quest.main_worldshift_reveal.stage, then a player inside the tower without the door tag
(deep_handoff_received or later) is set back outside the doorway, and a player above the briefing hall without the
climb tag (hq_crossed or later) is set back onto the hall's floor. Nothing is ever shut, so anyone inside walks out.

Every position comes from tools/deep_city.py's build run in memory (its plan's hq.tower box and top), never a world:
the build fails closed when the city's tower is not data/hq_tower.json's, when a write leaves the tower's interior or
its doorway, lands in a reserved volume (data/deep_city.json reserved) or on one of the city's own verify checks, when
a seat (data/hq_trainers.json, data/hq_tower.json npcs) is not a floor with two air above, or when the walk from the
doorway does not reach every seat, cache and the top.

The finale's two fights (data/hq_tower.json fights, the integration of 2026-10-04): Brann and Elara are the NPCs above,
each class carrying a party (tools/compile_dialogue.py), and this pack's battle_victory callback runs won_brann /
won_elara as the WINNING player, writing brann_defeated / elara_defeated into that player's data (fight_files()).
check_fights() holds the fights and data/hq_tower.json finale_order against the quest transitions.

What this does NOT cover: the trainers themselves (tools/route_trainers.py emits them from data/hq_trainers.json and
R17 summons them), the NPCs' conversations (tools/compile_dialogue.py) and their placement (R18HQ, npc_placements()),
and anything outside the tower -- the ring-0 room's iron door and its guards are data/relic_underground.json's.

  python tools/hq_tower.py build [--source-root DIR]
  python tools/hq_tower.py report [--source-root DIR]     the storeys, seats and the walk, writing nothing
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits as FL  # noqa: E402
from terrain import env_source_root  # noqa: E402

SPEC = ROOT / "data" / "hq_tower.json"
TRAINERS = ROOT / "data" / "hq_trainers.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_hq_tower"
NS = "cobblers"
FOLDER = "hq_tower"
PART = 3000
PERIOD = 10
STAGE_FIELD = "quest.main_worldshift_reveal.stage"
AIR = "minecraft:air"
WORLD_READS: set = set()

STEP = "minecraft:polished_deepslate_stairs"
SLAB_TOP = "minecraft:waxed_cut_copper_slab[type=top,waterlogged=false]"
SLAB_LOW = "minecraft:waxed_cut_copper_slab[type=bottom,waterlogged=false]"
BELT = "minecraft:polished_blackstone_slab[type=bottom,waterlogged=false]"
BARREL = "minecraft:barrel[facing=up,open=false]"
BULB = "minecraft:waxed_copper_bulb[lit=true,powered=false]"
LANTERN = "minecraft:lantern[hanging=true,waterlogged=false]"
CHAIN = "minecraft:chain[axis=y,waterlogged=false]"
# the relay masts' tips: an end rod, not a lightning rod -- a lightning rod is a spawn condition (data/spawn_blocks.json:
# electrode, magnemite, joltik ... neededNearbyBlocks); hq_tower_audit H2 found it, 2026-10-04
ROD = "minecraft:end_rod[facing=up]"
BARS = "minecraft:iron_bars"

# one flight a storey (data/hq_tower.json stairs_why): the cell a player starts from, the steps in climbing order and
# the way they face, and the floor cell above the last step. W6 is storey 0's six-step flight (its floor is 7 below)
SIDES = {
    "N": {"approach": (0, 0), "steps": [(i, 0) for i in range(1, 6)], "facing": "east", "landing": (6, 0), "inner": (0, 1)},
    "E": {"approach": (8, 0), "steps": [(8, k) for k in range(1, 6)], "facing": "south", "landing": (8, 6), "inner": (-1, 0)},
    "S": {"approach": (8, 8), "steps": [(i, 8) for i in range(7, 2, -1)], "facing": "west", "landing": (2, 8), "inner": (0, -1)},
    "W": {"approach": (0, 8), "steps": [(0, k) for k in range(7, 2, -1)], "facing": "north", "landing": (0, 2), "inner": (1, 0)},
    "W6": {"approach": (0, 8), "steps": [(0, k) for k in range(7, 1, -1)], "facing": "north", "landing": (0, 1), "inner": (1, 0)},
}
VOID = [(i, k) for i in range(2, 7) for k in range(2, 7)]
RING1 = [(i, k) for i in range(1, 8) for k in range(1, 8) if max(abs(i - 4), abs(k - 4)) == 3]


class HQError(SystemExit):
    pass


def load():
    return json.loads(SPEC.read_text(encoding="utf-8"))


def trainers():
    return json.loads(TRAINERS.read_text(encoding="utf-8"))["trainers"]


_MEMO = {}


def city(source_root):
    """(cells {(x, y, z): block}, plan, spec) of tools/deep_city.py's build, in memory, as R9RU's tool reads it."""
    if source_root not in _MEMO:
        import deep_city as DC
        cv, plan, _services, spec = DC.build(source_root, None)
        _MEMO[source_root] = ({k: v[0] for k, v in cv.v.items()}, plan, spec)
    return _MEMO[source_root]


# ------------------------------------------------------------------ geometry

def frame(spec):
    t = spec["tower"]
    ix0, iz0, ix1, iz1 = t["interior"]
    floors = [s["floor"] for s in spec["storeys"]] + [t["top"] + 1]
    return ix0, iz0, floors


def storey_index(spec, sid):
    return next(n for n, s in enumerate(spec["storeys"]) if s["id"] == sid)


def stair_cells(spec):
    """{storey index: {"steps": [(i, k, y, facing)], "holes": [(i, k, y)], "rails": [(i, k, y)], "approach", "landing"}}."""
    _x, _z, floors = frame(spec)
    out = {}
    for n, s in enumerate(spec["storeys"]):
        if not s.get("stair"):
            continue
        side = SIDES[s["stair"]]
        f0, f1 = floors[n], floors[n + 1]
        steps = side["steps"]
        if len(steps) != f1 - f0 - 1:
            raise HQError("storey %s: a %s flight has %d steps for a rise of %d" % (s["id"], s["stair"], len(steps), f1 - f0))
        st = [(i, k, f0 + 1 + j, side["facing"]) for j, (i, k) in enumerate(steps)]
        holes = [(i, k, f1) for (i, k, y, _f) in st if y >= f1 - 3]
        di, dk = side["inner"]
        rails = [(i + di, k + dk, f1 + 1) for (i, k, _y) in holes]
        far = steps[len(steps) - len(holes) - 1]
        rails.append((far[0], far[1], f1 + 1))
        out[n] = {"steps": st, "holes": holes, "rails": rails, "approach": side["approach"], "landing": side["landing"]}
    return out


def seats(spec):
    """[(kind, id, storey index, (x, y, z))] for every trainer and NPC standing in the tower."""
    out = []
    for t in trainers():
        out.append(("trainer", t["id"], storey_index(spec, t["storey"]), tuple(t["seat"])))
    for n in spec["npcs"]:
        if n.get("storey"):
            out.append(("npc", n["id"], storey_index(spec, n["storey"]), tuple(n["at"])))
    return out


def furnishing(spec):
    """{storey id: [(i, k, dy, block)]}: what each storey holds, dy above its stand level (floor + 1)."""
    f = {}
    f["hq_s0"] = ([(i, 4, 0, BELT) for i in range(3, 8)] + [(8, 4, 0, "minecraft:blast_furnace[facing=west,lit=false]")]
                  + [(i, k, 0, BARREL) for i in (7, 8) for k in (7, 8)] + [(8, 7, 1, BARREL), (8, 8, 1, BARREL)]
                  + [(i, 1, 0, SLAB_TOP) for i in (4, 5, 6)]
                  + [(2, 2, 5, LANTERN), (6, 6, 5, LANTERN)])
    f["hq_s1"] = ([(i, 4, 0, SLAB_TOP) for i in (4, 5, 6)]
                  + [(i, 3, 0, "%s[facing=north,half=bottom,shape=straight,waterlogged=false]" % STEP) for i in (4, 5, 6)]
                  + [(i, 5, 0, "%s[facing=south,half=bottom,shape=straight,waterlogged=false]" % STEP) for i in (4, 5, 6)]
                  + [(7, 7, 4, LANTERN), (1, 7, 4, LANTERN)])
    core = []
    for i in range(3, 6):
        for k in range(3, 6):
            for dy in range(0, 11):
                core.append((i, k, dy, "minecraft:sea_lantern" if (i, k) == (4, 4) else "minecraft:waxed_oxidized_copper_grate"))
    belt = [(i, k, 0, BELT) for (i, k) in VOID if max(abs(i - 4), abs(k - 4)) == 2]
    hang = []
    for (i, k) in ((2, 2), (2, 6), (6, 2), (6, 6)):
        hang += [(i, k, dy, CHAIN) for dy in (8, 9, 10)] + [(i, k, 7, LANTERN)]
    f["hq_s2"] = core + belt + hang + [(0, 8, 0, BARREL)]
    f["hq_s3"] = []
    store = [(i, k, dy, "moarconcrete:black_concrete_texture") for (i, k) in ((2, 5), (2, 6), (2, 8), (0, 5), (1, 5))
             for dy in range(0, 5)]
    f["hq_s4"] = ([(i, 3, 0, SLAB_TOP) for i in (2, 3, 4)]
                  + [(2, 3, 1, "minecraft:brewing_stand[has_bottle_0=false,has_bottle_1=false,has_bottle_2=false]"),
                     (4, 3, 1, "minecraft:brewing_stand[has_bottle_0=false,has_bottle_1=false,has_bottle_2=false]")]
                  + [(i, 5, 0, SLAB_TOP) for i in (5, 6, 7)] + store + [(0, 8, 0, BARREL)]
                  + [(4, 6, 4, LANTERN), (1, 7, 4, LANTERN)])
    f["hq_s5"] = ([(i, k, dy, "minecraft:bookshelf") for i in range(1, 6) for k in (2, 4) for dy in (0, 1)]
                  + [(0, 0, 0, BARREL), (6, 3, 4, LANTERN), (3, 6, 4, LANTERN)])
    relay = []
    for (i, k) in ((2, 2), (6, 2), (2, 6), (6, 6)):
        relay += [(i, k, dy, "minecraft:waxed_oxidized_copper") for dy in range(0, 4)] + [(i, k, 4, BULB), (i, k, 5, ROD)]
    relay += [(4, 4, dy, BULB if dy in (2, 5, 8) else "minecraft:waxed_oxidized_copper") for dy in range(0, 10)]
    relay += [(4, 4, 10, ROD)]
    f["hq_s6"] = relay + [(8, 0, 0, BARREL)]
    f["hq_s7"] = []
    f["hq_s8"] = ([(8, k, dy, "minecraft:barrel[facing=west,open=false]") for k in range(1, 6) for dy in (0, 1)]
                  + [(i, k, 0, SLAB_LOW) for i in (4, 5, 6) for k in (3, 5)]
                  + [(i, k, 2, SLAB_TOP) for i in (4, 5, 6) for k in (3, 5)]
                  + [(2, 2, 4, LANTERN), (6, 7, 4, LANTERN)])
    f["hq_s9"] = ([(i, 4, 0, SLAB_TOP) for i in (3, 4, 5)]
                  + [(i, 8, dy, "minecraft:bookshelf") for i in range(2, 8) for dy in (0, 1)]
                  + [(7, 4, 0, "minecraft:lectern[facing=west,has_book=false,powered=false]"), (6, 6, 4, LANTERN), (2, 2, 4, LANTERN)])
    desks = [(0, k, 0, SLAB_TOP) for k in range(2, 7)] + [(8, k, 0, SLAB_TOP) for k in range(2, 7)] + \
        [(i, 8, 0, SLAB_TOP) for i in range(2, 7)]
    lamps = [(0, 2, 1, BULB), (0, 6, 1, BULB), (8, 2, 1, BULB), (8, 6, 1, BULB), (4, 8, 1, BULB)]
    f["hq_s10"] = desks + lamps + [(4, 6, 0, "minecraft:lectern[facing=north,has_book=false,powered=false]"),
                                   (2, 4, 4, LANTERN), (6, 4, 4, LANTERN)]
    return f


def writes(spec, city_cells=None):
    """{(x, y, z): (block, phase)}: every block this pack writes. Phase 1 is the carve and the structure, phase 2 what
    hangs on it (bars, lanterns, chains, rods, stands and lecterns), written after it. Later entries replace earlier."""
    x0, z0, floors = frame(spec)
    W = {}

    def put(i, k, y, b, ph=1):
        W[(x0 + i, y, z0 + k)] = (b, ph)

    for c in spec["door"]["cells"]:
        W[tuple(c)] = (AIR, 1)
    st = stair_cells(spec)
    seat_cells = {}
    for _kind, _id, n, (x, y, z) in seats(spec):
        seat_cells.setdefault(n, set()).add((x - x0, z - z0))
    # the catwalk storeys: their floor's middle opened, a ring of bars on what is left, a seat's cell left unbarred
    for n, s in enumerate(spec["storeys"]):
        if s.get("void"):
            for (i, k) in VOID:
                put(i, k, floors[n], AIR)
            for (i, k) in RING1:
                if (i, k) not in seat_cells.get(n, set()):
                    put(i, k, floors[n] + 1, BARS, 2)
    for n, c in st.items():
        for (i, k, y) in c["holes"]:
            put(i, k, y, AIR)
        for (i, k, y) in c["rails"]:
            put(i, k, y, BARS, 2)
        for (i, k, y, facing) in c["steps"]:
            put(i, k, y, "%s[facing=%s,half=bottom,shape=straight,waterlogged=false]" % (STEP, facing))
    hangs = ("lantern", "chain", "lightning_rod", "brewing_stand", "lectern")
    for sid, items in furnishing(spec).items():
        n = storey_index(spec, sid)
        for (i, k, dy, b) in items:
            put(i, k, floors[n] + 1 + dy, b, 2 if any(h in b for h in hangs) else 1)
    # bars take their connections from their neighbours, as tools/deep_city.py's connect_panes does
    import deep_city as DC
    for p, (b, ph) in list(W.items()):
        if b != BARS:
            continue
        stt = {}
        for (dx, dz), name in DC.FACE.items():
            q = (p[0] + dx, p[1], p[2] + dz)
            nb = (W[q][0] if q in W else (city_cells or {}).get(q, AIR)).split("[")[0]
            stt[name] = "true" if (nb == BARS or DC._solid(nb)) else "false"
        W[p] = ("%s[east=%s,north=%s,south=%s,west=%s,waterlogged=false]" % (BARS, stt["east"], stt["north"],
                                                                            stt["south"], stt["west"]), ph)
    return W


# ------------------------------------------------------------------ checks

def _in(p, box):
    x0, y0, z0, x1, y1, z1 = box
    return x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and z0 <= p[2] <= z1


def check_city(spec, plan, cells):
    probs = []
    t = spec["tower"]
    if plan["hq"]["tower"] != t["box"]:
        probs.append("the city's HQ tower is %s, data/hq_tower.json says %s" % (plan["hq"]["tower"], t["box"]))
    if plan["hq"]["top"] != t["top"]:
        probs.append("the city's HQ tower tops out at %s, data/hq_tower.json says %s" % (plan["hq"]["top"], t["top"]))
    x0, z0, floors = frame(spec)
    ix0, iz0, ix1, iz1 = t["interior"]
    for n, f in enumerate(floors[1:-1], start=1):
        if f - floors[n - 1] != (7 if n == 1 else t["storey_pitch"]):
            probs.append("storey %d's floor y%d is not a pitch above the last" % (n, f))
        for x in range(ix0, ix1 + 1):
            for z in range(iz0, iz1 + 1):
                if cells.get((x, f, z), AIR) == AIR:
                    probs.append("the city lays no floor at %s" % ((x, f, z),))
                for y in range(f + 1, floors[n + 1]):
                    if cells.get((x, y, z), AIR) != AIR:
                        probs.append("the city writes %s inside storey %d at %s" % (cells[(x, y, z)], n, (x, y, z)))
    for c in spec["door"]["cells"]:
        if cells.get(tuple(c), AIR) == AIR:
            probs.append("the door cell %s is not a wall in the city's build" % (c,))
    return probs[:20]


def check_writes(spec, W, cells, plan, dc_spec):
    probs = []
    t = spec["tower"]
    ix0, iz0, ix1, iz1 = t["interior"]
    inside = (ix0, t["base"], iz0, ix1, t["top"], iz1)
    door = {tuple(c) for c in spec["door"]["cells"]}
    out = [p for p in W if not _in(p, inside) and p not in door]
    if out:
        probs.append("%d writes outside the tower's interior and doorway, e.g. %s" % (len(out), sorted(out)[:3]))
    for r in dc_spec["reserved"]:
        x0, y0, z0, x1, y1, z1 = r["box"]
        hit = [p for p in W if _in(p, (x0, y0, z0, x1, y1, z1))]
        if hit:
            probs.append("%d writes in data/deep_city.json reserved %s, e.g. %s" % (len(hit), r["id"], hit[:2]))
    checks = {(c[0], c[1], c[2]) for c in plan["checks"]}
    hit = sorted(p for p in W if p in checks)
    if hit:
        probs.append("%d writes on the city's own verify checks (derived/deep_city/plan.json), e.g. %s" % (len(hit), hit[:3]))
    return probs


def solid_at(W, cells, p):
    b = (W[p][0] if p in W else cells.get(p, AIR)).split("[")[0]
    return b != AIR


def model(spec, W, cells):
    """block_at(x, y, z) over the city, then this pack; the tread y66 of the Deep's ring 0 under the tower and the
    corridor (tools/rift_deep.py, R9B, which the city leaves unwritten there) counts as solid."""
    t = spec["tower"]

    def at(p):
        if p in W:
            return W[p][0]
        if p in cells:
            return cells[p]
        if p[1] == t["base"] - 1:
            return "minecraft:tread"
        return AIR
    return at


def passable(b):
    return b.split("[")[0] == AIR


def walk(spec, W, cells, start):
    """Every standable cell (feet) a player reaches from `start`: two passable cells over a non-passable one; a move
    goes to a side neighbour one up (a step or a jump), level, or up to three down."""
    at = model(spec, W, cells)
    t = spec["tower"]
    lo = (t["box"][0] - 1, t["base"] - 1, t["box"][1] - 1)
    hi = (t["box"][2] + 5, t["top"] + 2, t["box"][3] + 1)

    def stand(p):
        return passable(at(p)) and passable(at((p[0], p[1] + 1, p[2]))) and not passable(at((p[0], p[1] - 1, p[2])))
    seen = {start}
    q = deque([start])
    while q:
        x, y, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (lo[0] <= nx <= hi[0] and lo[2] <= nz <= hi[2]):
                continue
            for dy in (1, 0, -1, -2, -3):
                p = (nx, y + dy, nz)
                if not (lo[1] <= p[1] <= hi[1]):
                    continue
                if dy == 1 and not passable(at((x, y + 2, z))):
                    continue
                if dy < 0 and any(not passable(at((nx, y + d, nz))) for d in range(dy + 1, 2)):
                    continue
                if stand(p):
                    if p not in seen:
                        seen.add(p)
                        q.append(p)
                    break
    return seen


def check_walk(spec, W, cells):
    """The walk from the corridor outside the doorway: every seat's neighbour, every cache's trigger, the top storey,
    and back out from the top."""
    probs = []
    sb = spec["gates"]["door"]["set_back"]
    start = (int(sb[0] // 1), int(sb[1]), int(sb[2] // 1))
    at = model(spec, W, cells)
    reach = walk(spec, W, cells, start)
    for kind, sid, _n, (x, y, z) in seats(spec):
        if not (passable(at((x, y, z))) and passable(at((x, y + 1, z))) and not passable(at((x, y - 1, z)))):
            probs.append("%s %s at %s does not stand on a floor with two air above" % (kind, sid, (x, y, z)))
        if not any((x + dx, y + dy, z + dz) in reach for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)) for dy in (-1, 0, 1)):
            probs.append("%s %s at %s: the walk from the doorway reaches no cell beside it" % (kind, sid, (x, y, z)))
    for c in spec["hq_caches"]:
        tr = c["trigger"]
        if not any(_in(p, tuple(tr["min"]) + tuple(tr["max"])) for p in reach):
            probs.append("cache %s: the walk reaches no cell of its trigger %s" % (c["id"], tr))
        b = W.get(tuple(c["at"]), (None,))[0]
        if not b or not b.startswith("minecraft:barrel"):
            probs.append("cache %s: no barrel written at %s" % (c["id"], c["at"]))
    x0, z0, floors = frame(spec)
    top = [p for p in reach if p[1] == floors[-2] + 1 and spec["tower"]["interior"][0] <= p[0] <= spec["tower"]["interior"][2]]
    if not top:
        probs.append("the walk from the doorway never reaches the top storey (y%d)" % (floors[-2] + 1))
    else:
        back = walk(spec, W, cells, sorted(top)[0])
        if start not in back:
            probs.append("from the top storey the walk does not come back out to %s" % (start,))
    return probs, reach


def check_outside_seats(spec, cells):
    """An NPC seated outside the tower (Nia at her clinic): a block the city writes under it and nothing it writes in
    the two cells of the stand. The street's own tread is R9B's and is not modelled here, so the city's sidewalk under
    the seat is required."""
    probs = []
    for n in spec["npcs"]:
        if n.get("storey"):
            continue
        x, y, z = n["at"]
        if cells.get((x, y - 1, z), AIR) == AIR:
            probs.append("%s at %s: the city writes no floor under it" % (n["id"], n["at"]))
        for dy in (0, 1):
            if cells.get((x, y + dy, z), AIR) != AIR:
                probs.append("%s at %s: the city writes %s in its stand" % (n["id"], n["at"], cells[(x, y + dy, z)]))
    return probs


def check_caches(spec):
    probs = []
    rw = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))["rewards"]
    by = {r["id"]: r for r in rw}
    for c in spec["hq_caches"]:
        r = by.get(c["reward_id"])
        if r is None:
            continue
        if (r.get("container") or {}).get("at") != c["at"]:
            probs.append("data/rewards.json %s's container is %s, data/hq_tower.json places the barrel at %s"
                         % (r["id"], (r.get("container") or {}).get("at"), c["at"]))
        if r.get("trigger") != c["trigger"]:
            probs.append("data/rewards.json %s's trigger is not data/hq_tower.json's" % r["id"])
    return probs


# ------------------------------------------------------------------ the gates

def stages_from(stage):
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    f = next(f for f in prog["quest_fields"] if f["id"] == STAGE_FIELD)
    vals = f["allowed_values"]
    if stage not in vals:
        raise HQError("%s is not a value of %s in data/progression.json" % (stage, STAGE_FIELD))
    return vals[vals.index(stage):]


def _key(field):
    return "cobblers__" + field.replace(".", "__")


def _box(b):
    x0, y0, z0, x1, y1, z1 = b
    return "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (x0, y0, z0, x1 - x0, y1 - y0, z1 - z0)


def gate_lines(spec):
    g = spec["gates"]
    k = _key(g["field"])
    lines = ["scoreboard players set #clock cobblers_hq_tower 0",
             "# every player near the tower: its gate tags from their own stage (data/hq_tower.json gates)"]
    mol = "t.d = q.player.data(); "
    for name in ("door", "climb"):
        gg = g[name]
        cond = " || ".join("t.d.%s == '%s'" % (k, v) for v in stages_from(gg["from_stage"]))
        mol += ("(%s) ? { q.run_command('tag ' + q.player.uuid + ' add %s'); } : "
                "{ q.run_command('tag ' + q.player.uuid + ' remove %s'); }; " % (cond, gg["tag"], gg["tag"]))
    tb = g["tag_box"]
    lines.append('execute as @a[%s] run runmolang "%s" @s' % (_box(tb), mol.strip()))
    for name in ("door", "climb"):
        gg = g[name]
        who = "@a[%s,tag=!%s,gamemode=!creative,gamemode=!spectator]" % (_box(gg["box"]), gg["tag"])
        x, y, z, yaw = gg["set_back"]
        lines += ["# the %s gate: %s or later" % (name, gg["from_stage"]),
                  "title %s actionbar %s" % (who, json.dumps({"text": gg["say"], "color": "gold"})),
                  "tp %s %s %s %s %s 0" % (who, x, y, z, yaw)]
    return lines


# ------------------------------------------------------------------ the fights (Brann, Elara)

CALLBACK = "data/cobblemon/callbacks/battle_victory/cobblers_hq_tower.molang"


def _fight_spot(spec, f):
    at = {n["id"]: n["at"] for n in spec["npcs"]}
    return at[f["npc"]]


def fight_files(spec=None):
    """{relative path: text}: the battle_victory callback and one function per fight (data/hq_tower.json fights).

    The callback is the arena's in-game-proven shape (docs/research/notes/arena-per-player-opponents.md section 8;
    tools/arena_runtime.py callback()): for each NPC on the losing side and each PLAYER on the winning side, a
    server-sourced `execute as <npc uuid> if entity @s[...]` picks out the fight's NPC, then `as <player uuid>` runs the
    fight's function as that winning player. The NPC is matched by its fixed spot (R18HQ seats it at `at` + 0.5 and its
    class is not movable), not by a tag, because the placement tags nothing. A loss, a flee and every other NPC battle
    in the world match nothing here. Cobblemon fires callbacks only under its own namespace (EXP-042), hence the path."""
    spec = spec or load()
    out, calls = {}, []
    for f in spec["fights"]:
        x, y, z = _fight_spot(spec, f)
        sel = "@s[type=cobblemon:npc,x=%d.5,y=%d,z=%d.5,distance=..%s]" % (x, y, z, f["radius"])
        calls.append("      q.run_command('execute as ' + t.l.uuid + ' if entity %s as ' + t.w.player.uuid + "
                     "' run function %s:%s/%s');" % (sel, NS, FOLDER, f["function"]))
        mol = "t.d = q.player.data(); t.d.%s = 1; q.player.save_data();" % _key(f["sets"])
        out["data/%s/function/%s/%s.mcfunction" % (NS, FOLDER, f["function"])] = "\n".join([
            "# Generated by tools/hq_tower.py: run by the battle_victory callback as the player who beat %s "
            "(data/hq_tower.json fights). Writes %s into THAT player's Cobblemon data, as tools/route_trainers.py's won "
            "functions do" % (f["trainer"], f["sets"]),
            'runmolang "%s" @s' % mol,
            "title @s actionbar %s" % json.dumps({"text": f["won_say"], "color": "gold"})]) + "\n"
    out[CALLBACK] = "\n".join(
        ["'Generated by tools/hq_tower.py. The finale: a player who beat Brann or Elara runs their won function.';",
         "for_each(t.l, c.scriptable_losers, {",
         "  t.l.is_npc ? {",
         "    for_each(t.w, c.player_winners, {"]
        + calls + ["    });", "  };", "});", ""])
    return out


def check_fights(spec):
    """The fights' data against everything they name, and finale_order against the quest transitions. [] when clean."""
    probs = []
    npcs = {n["id"]: n for n in spec["npcs"]}
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    convs = {c["id"]: c for c in dl["conversations"]}
    fin = json.loads((ROOT / "data" / "finale_trainers.json").read_text(encoding="utf-8"))
    recs = {t["id"]: t for t in fin["trainers"]}
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    fields = {f["id"] for f in prog["quest_fields"]}
    for f in spec["fights"]:
        n = npcs.get(f["npc"])
        if n is None:
            probs.append("fight %s: no NPC %s in npcs" % (f["trainer"], f["npc"]))
            continue
        nb = (convs.get(n["conversation"]) or {}).get("npc_battle") or {}
        if nb.get("trainer") != f["trainer"] or nb.get("trainers") != "finale_trainers.json":
            probs.append("fight %s: %s's npc_battle names %s" % (f["trainer"], n["conversation"], nb or "nothing"))
        rec = recs.get(f["trainer"])
        if rec is None or not rec.get("team") or "seat" in rec:
            probs.append("fight %s: not a seatless record with a team in data/finale_trainers.json" % f["trainer"])
        elif f["sets"] not in rec.get("sets", []):
            probs.append("fight %s: sets %s, the record says %s" % (f["trainer"], f["sets"], rec.get("sets")))
        if f["sets"] not in fields:
            probs.append("fight %s: %s is not a declared quest field" % (f["trainer"], f["sets"]))
        # nothing else a cobblemon:npc could be within the radius: the callback must match this NPC only
        x, y, z = n["at"]
        for o in spec["npcs"]:
            if o["id"] != n["id"] and sum((a - b) ** 2 for a, b in zip(o["at"], (x, y, z))) ** 0.5 <= f["radius"] + 1:
                probs.append("fight %s: %s stands within its radius" % (f["trainer"], o["id"]))
    qd = json.loads((ROOT / "data" / "quests.json").read_text(encoding="utf-8"))
    tr = {t["id"]: t for q in qd["quests"] for t in q.get("transitions") or []}
    pre = "quest.main_worldshift_reveal."
    for s in spec["finale_order"]:
        t = tr.get(s["transition"])
        if t is None:
            probs.append("finale_order scene %s: no transition %s" % (s["scene"], s["transition"]))
            continue
        conds = [(c.get("field"), c.get("value")) for c in t["conditions"]]
        want = [(STAGE_FIELD, v) for v in s["reads"].split(" AND ")[:1]]
        if s.get("fight"):
            want.append((pre + s["then"], True))
        if s["scene"] == 5:
            want += [(pre + "brann_defeated", True), (pre + "elara_defeated", True)]
        if sorted(conds, key=str) != sorted(want, key=str):
            probs.append("finale_order scene %s: %s reads %s, the order says %s" % (s["scene"], s["transition"], conds, want))
        stage_to = [e["value"] for e in t["effects"] if e.get("field") == STAGE_FIELD]
        if stage_to != [s["writes"].split()[0]]:
            probs.append("finale_order scene %s: %s writes %s, the order says %s" % (s["scene"], s["transition"], stage_to,
                                                                                    s["writes"]))
    return probs


# ------------------------------------------------------------------ the pack

def _compress(vox):
    import deep_city as DC
    return DC._compress(vox)


def build(source_root):
    spec = load()
    cells, plan, dc_spec = city(source_root)
    probs = check_city(spec, plan, cells)
    W = writes(spec, cells)
    probs += check_writes(spec, W, cells, plan, dc_spec)
    walk_probs, reach = check_walk(spec, W, cells)
    probs += walk_probs + check_caches(spec) + check_outside_seats(spec, cells) + check_fights(spec)
    return spec, W, probs, reach


def emit(spec, W):
    if OUT.exists():
        shutil.rmtree(OUT)
    fn = OUT / "data" / NS / "function" / FOLDER
    fn.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                                          "Cobblers: the Compact HQ tower's interior and its gates (tools/hq_tower.py)"}},
                                                indent=2) + "\n", encoding="utf-8")
    order = []
    for phase in (1, 2):
        vox = {p: b for p, (b, ph) in W.items() if ph == phase}
        body = _compress(vox)
        if phase == 1:
            air = [l for l in body if l.endswith(" " + AIR)]
            body = air + [l for l in body if not l.endswith(" " + AIR)]
        for k in range(0, len(body), PART):
            name = "blocks_%d%s" % (phase, "" if k == 0 else "_%d" % (k // PART + 1))
            out = FL.ensure_loaded(["# Generated by tools/hq_tower.py: phase %d (data/hq_tower.json)" % phase] + body[k:k + PART])
            p = FL.check_lines(out, name)
            if p:
                raise HQError("function %s would be refused: %s" % (name, p[:3]))
            (fn / (name + ".mcfunction")).write_text("\n".join(out) + "\n", encoding="utf-8")
            order.append(name)
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    (fn / "cycle.mcfunction").write_text("\n".join(gate_lines(spec)) + "\n", encoding="utf-8")
    (fn / "tick.mcfunction").write_text("\n".join([
        "scoreboard players add #clock cobblers_hq_tower 1",
        "execute if score #clock cobblers_hq_tower matches %d.. run function %s:%s/cycle" % (PERIOD, NS, FOLDER)]) + "\n",
        encoding="utf-8")
    (fn / "load.mcfunction").write_text("scoreboard objectives add cobblers_hq_tower dummy\n", encoding="utf-8")
    for rel, text in fight_files(spec).items():
        f = OUT / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    tags = OUT / "data" / "minecraft" / "tags" / "function"
    tags.mkdir(parents=True)
    (tags / "tick.json").write_text(json.dumps({"values": ["%s:%s/tick" % (NS, FOLDER)]}, indent=2) + "\n", encoding="utf-8")
    (tags / "load.json").write_text(json.dumps({"values": ["%s:%s/load" % (NS, FOLDER)]}, indent=2) + "\n", encoding="utf-8")
    return order


def hold_box(spec=None):
    spec = spec or load()
    b = spec["tower"]["box"]
    return (b[0] - 2, b[1] - 2, b[2] + 4, b[3] + 2)


def placement_steps(pack_dir=None):
    """For tools/reapply.py step R9HQ, after R9DC and R9RU: hold the tower's chunks, run the indexed block functions,
    release. Named from the built pack's own index, as R9RU's are."""
    pack_dir = Path(pack_dir or OUT)
    idx = pack_dir / "data" / NS / "function" / FOLDER / "index.txt"
    if not idx.is_file():
        raise SystemExit("no %s: run `reapply.py prepare` first" % idx)
    names = [n for n in idx.read_text(encoding="utf-8").split("\n") if n.strip()]
    hold = "%d %d %d %d" % hold_box()
    return ([("cmd", "forceload add " + hold), ("wait", 3)] + [("fn", "%s:%s/%s" % (NS, FOLDER, n)) for n in names]
            + [("cmd", "forceload remove " + hold)])


def npc_placements(spec=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for tools/reapply.py step R18HQ, from the committed data alone.
    Fails closed when a conversation is not in data/dialogue.json with that NPC."""
    spec = spec or load()
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    convs = {c["id"]: c for c in dl["conversations"]}
    out = []
    for n in spec["npcs"]:
        c = convs.get(n["conversation"])
        if c is None or c.get("npc_id") != n["id"]:
            raise HQError("%s is not a conversation with NPC %s in data/dialogue.json" % (n["conversation"], n["id"]))
        out.append((c["id"], tuple(n["at"]), "%s:%s" % (NS, n["id"]), n["yaw"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "report"))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    spec, W, probs, reach = build(a.source_root or env_source_root())
    for p in probs:
        print("PROBLEM: %s" % p)
    if probs:
        print("hq_tower: %d problem(s), nothing written" % len(probs))
        return 1
    stairs = stair_cells(spec)
    print("hq_tower: %d storeys, %d stair flights, %d cells written (%d air), %d seats, %d caches, walk reaches %d cells"
          % (len(spec["storeys"]), len(stairs), len(W), sum(1 for b, _ in W.values() if b == AIR), len(seats(spec)),
             len(spec["hq_caches"]), len(reach)))
    if a.cmd == "build":
        order = emit(spec, W)
        print("hq_tower: wrote %s (%d block functions, the gate cycle)" % (OUT, len(order)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
