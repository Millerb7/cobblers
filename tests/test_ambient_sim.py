"""The working Pokemon pack (tools/ambient.py -> build/datapacks/cobblers_ambient) run over ticks in a small command
interpreter (tests/mcfunction_sim.py), for every worker in data/ambient.json.

Written by the test author, not by the session that built the pack (e3c84ed). Expectations come from data/ambient.json
(stations, routes, faces, spots, species, levels, the carried item, the rules' radii) and from Minecraft's own
semantics, never from derived/ambient/plan.json: the plan is used only to put a test player at a worker. A synthetic
flat site (hand-computable: a 4-point route at y 65) covers what the real data does not exercise (short pauses).

The pack must be built here (python tools/ambient.py build --source-root <root>); without it, or when its index does
not list exactly data/ambient.json's workers, the pack tests SKIP (NOT_EXECUTED), and a skip is not a pass.

Not covered (runtime, EXP-046 and its successors): that Cobblemon's spawnpokemonat, NoAI, Unbattleable and the
interaction box behave as modelled; entity load timing after a restart or a chunk load; tp interpolation; whether the
work reads as work; tick cost on a server.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import mcfunction_sim as M  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_ambient"
DATA = json.loads((ROOT / "data" / "ambient.json").read_text(encoding="utf-8"))
RULES = DATA["rules"]
WORKERS = {w["id"]: w for w in DATA["workers"]}
WORLD = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
SPAWN = (float(WORLD["export"]["spawn"][0]), 64.0, float(WORLD["export"]["spawn"][1]))   # the server's own position
TAG = "cobblers.amb"
F = "cobblers:ambient"
CARRIERS = [w for w in WORKERS if WORKERS[w]["job"] == "carry"]
WORKS = [w for w in WORKERS if WORKERS[w]["job"] == "work"]
BLINKS = [w for w in WORKERS if WORKERS[w]["job"] == "blink"]

_FNS = {}


def pack_functions():
    if not _FNS:
        idx = PACK / "data" / "cobblers" / "function" / "ambient" / "index.txt"
        if not idx.is_file():
            pytest.skip("NOT_EXECUTED: %s is not built (python tools/ambient.py build --source-root <root>)" % PACK)
        if idx.read_text(encoding="utf-8").split() != [w["id"] for w in DATA["workers"]]:
            pytest.skip("NOT_EXECUTED: the built pack's workers are not data/ambient.json's; rebuild it")
        w = M.World.from_pack(PACK)
        _FNS.update(functions=w.functions, tags=w.tags)
    return _FNS


def new_world(loaded=None, functions=None, tags=None):
    if functions is None:
        p = pack_functions()
        functions, tags = p["functions"], p["tags"]
    w = M.World(functions, spawn=SPAWN, loaded=loaded)
    w.tags = tags
    return w


def station(wid, functions=None):
    """Where the pack spawns a worker: the spawn call's arguments (only to put a player there)."""
    fns = functions or pack_functions()["functions"]
    line = [l for l in fns["%s/w/%s/spawn" % (F, wid)] if "spawn_at" in l][0]
    m = re.search(r'x:"(-?[\d.]+)",y:(-?\d+),z:"(-?[\d.]+)"', line)
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def workers(w, wid):
    return w.living("cobblemon:pokemon", "%s.%s" % (TAG, wid))


def boxes(w, wid):
    return w.living("minecraft:interaction", "%s.i.%s" % (TAG, wid))


def displays(w, wid):
    return w.living("minecraft:item_display", "%s.c.%s" % (TAG, wid))


def placed(wid, **kw):
    """A world with one player at the worker's station, ticked until the first keeper has run."""
    w = new_world(**kw)
    w.add_player(station(wid, kw.get("functions")))
    w.run_load()
    w.tick(RULES["keep_every"])
    return w


def centre(c):
    return (c[0] + 0.5, c[1] + 0.5)


def yaw_to(ax, az, bx, bz):
    """Minecraft yaw from (ax, az) towards (bx, bz): 0 faces +z (south), 90 faces -x (west)."""
    return math.degrees(math.atan2(-(bx - ax), bz - az)) % 360.0


# ------------------------------------------------------------------------------------------------ the keeper

# Without it a worker can be missing, doubled, left without its box or its carried display, or lose the flags that
# keep it from despawning, being hurt or being battled: the keeper is the only thing that holds each one.
@pytest.mark.parametrize("wid", list(WORKERS))
def test_keeper_holds_exactly_one_protected_worker_with_its_box_and_display(wid):
    w = placed(wid)
    spec = WORKERS[wid]
    assert not w.errors, w.errors
    assert not [e for e in w.log if e[1] == "inert_spawn"], "a spawn line that does nothing after a restart ran"
    (poke,) = workers(w, wid)
    assert len(boxes(w, wid)) == 1
    assert len(displays(w, wid)) == (1 if spec["job"] == "carry" else 0)
    assert poke.nbt["Pokemon"]["Species"] == spec["species"]
    assert poke.nbt["Pokemon"]["Level"] == spec.get("level", RULES["level"])
    for flag in ("NoAI", "PersistenceRequired", "Invulnerable", "Unbattleable"):
        assert poke.nbt.get(flag) == 1, flag
    assert set(poke.effects) >= {"minecraft:resistance", "minecraft:regeneration"}
    sx, sy, sz = station(wid)
    # the box stands on the worker (a station worker's on its station: the worker itself may be mid-hop)
    on = (sx, sy, sz) if spec["job"] == "work" else poke.pos
    assert math.dist(boxes(w, wid)[0].pos, on) < 1e-6, "the box is not on the worker"

    # a restart (effects lost, a flag cleared by something) with a duplicate worker, two extra boxes and a display
    poke.effects.clear()
    poke.nbt["Invulnerable"] = 0
    dup = w.add(M.Entity("cobblemon:pokemon", (sx + 40, sy, sz), nbt={"NoAI": 1, "Pokemon": {"Level": 1}},
                         tags={TAG, "%s.%s" % (TAG, wid)}))
    for _ in range(2):
        w.add(M.Entity("minecraft:interaction", (sx, sy, sz), tags={TAG + ".i", "%s.i.%s" % (TAG, wid)}))
    if spec["job"] == "carry":
        w.add(M.Entity("minecraft:item_display", (sx, sy, sz), tags={TAG + ".c", "%s.c.%s" % (TAG, wid)}))
    w.tick(3 * RULES["keep_every"])
    assert len(workers(w, wid)) == 1 and len(boxes(w, wid)) == 1
    assert len(displays(w, wid)) == (1 if spec["job"] == "carry" else 0)
    # (which one survives is not asserted: the step moves every tagged worker, so the two stand together before a keep)
    (kept,) = workers(w, wid)
    assert kept.nbt.get("Invulnerable") == 1 and kept.nbt.get("PersistenceRequired") == 1
    assert set(kept.effects) >= {"minecraft:resistance", "minecraft:regeneration"}
    assert not w.errors, w.errors


# Without it a keeper would spawn into an unloaded chunk (a Pokemon that vanishes, or a duplicate when the saved one
# loads) or populate a town nobody is in.
@pytest.mark.parametrize("wid", [CARRIERS[0], WORKS[0], BLINKS[0]])
def test_keeper_spawns_nothing_in_an_unloaded_chunk_or_with_no_player_in_keep_radius(wid):
    w = new_world(loaded=lambda x, z: False)
    w.add_player(station(wid))
    w.run_load()
    w.tick(3 * RULES["keep_every"])
    assert not workers(w, wid) and not [c for c in w.calls if c[1].endswith("/%s/step" % wid)]

    sx, sy, sz = station(wid)
    w = new_world()
    w.add_player((sx + RULES["keep_radius"] + 4, sy, sz))
    w.run_load()
    w.tick(3 * RULES["keep_every"])
    assert not workers(w, wid) and not [c for c in w.calls if c[1].endswith("/%s/step" % wid)]


# Without it every worker would animate every tick for the whole server, the cost the doc says an empty town does not pay.
@pytest.mark.parametrize("wid", [CARRIERS[0], WORKS[0], BLINKS[0]])
def test_step_runs_only_while_a_player_is_within_active_radius(wid):
    sx, sy, sz = station(wid)
    w = new_world()
    p = w.add_player((sx + RULES["active_radius"] + 6, sy, sz))    # kept, not active
    w.run_load()
    w.tick(3 * RULES["keep_every"])
    assert len(workers(w, wid)) == 1
    steps = lambda: [c for c in w.calls if c[1] == "%s/w/%s/step" % (F, wid)]
    assert not steps()
    p.pos = [sx, sy, sz]
    w.tick(RULES["keep_every"])
    n0 = len(steps())
    w.tick(20)
    assert len(steps()) == n0 + 20, "active: one step a tick"
    p.pos = [sx + RULES["keep_radius"] + 30, sy, sz]                # gone, the chunk still loaded
    w.tick(RULES["keep_every"])
    n1 = len(steps())
    w.tick(3 * RULES["keep_every"])
    assert len(steps()) == n1, "the step kept running after the players left"


# Without it a town whose chunk unloads before the next keeper (a player who teleports away) keeps its worker's step
# running every tick until someone comes back.
@pytest.mark.xfail(strict=True, reason="tools/ambient.py:313: the keeper, the only thing that resets #<id>_on, runs "
                                       "only under `execute if loaded`, so a chunk that unloads while the flag is 1 "
                                       "leaves the step running every tick (chunk unload timing not measured in game)")
def test_step_stops_when_the_players_leave_and_the_chunk_unloads():
    wid = WORKS[0]
    loaded = {"yes": True}
    w = new_world(loaded=lambda x, z: loaded["yes"])
    p = w.add_player(station(wid))
    w.run_load()
    w.tick(2 * RULES["keep_every"])
    p.alive = False                                                  # logs off or teleports away
    loaded["yes"] = False
    n0 = len([c for c in w.calls if c[1] == "%s/w/%s/step" % (F, wid)])
    w.tick(3 * RULES["keep_every"])
    assert len([c for c in w.calls if c[1] == "%s/w/%s/step" % (F, wid)]) == n0


# ------------------------------------------------------------------------------------------------ carriers

def on_polyline(pt, route):
    """(distance to the route polyline of cell centres, arc length of the nearest point)."""
    best, arc, run = math.inf, 0.0, 0.0
    cs = [centre(c) for c in route]
    for a, b in zip(cs, cs[1:]):
        L = math.dist(a, b)
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((pt[0] - a[0]) * (b[0] - a[0]) + (pt[1] - a[1]) * (b[1] - a[1])) / L ** 2))
        q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        d = math.dist(pt, q)
        if d < best - 1e-9:
            best, arc = d, run + t * L
        run += L
    return best, arc


def run_carrier(wid, cycles=2, **kw):
    """Tick a placed carrier through `cycles` round trips; per tick: (leg, worker pos, display pos, box pos, item)."""
    w = placed(wid, **kw)
    out = w.storage["cobblers:ambient"]["p"][wid]["out"]
    n = len(out)
    trace = []
    pause = WORKERS[wid].get("pause_ticks", RULES["pause_ticks"]) if wid in WORKERS else kw.get("pause", 0)
    for _ in range(cycles * 2 * (n + pause + 20)):
        k = len(w.lookups)
        w.tick()
        legs = {p.rsplit(".", 1)[-1].split("[")[0] for p, _i, _n in w.lookups[k:]}
        (poke,) = workers(w, wid)
        (disp,) = displays(w, wid)
        (box,) = boxes(w, wid)
        trace.append((legs.pop() if legs else None, tuple(poke.pos), tuple(disp.pos), tuple(box.pos), disp.item))
    return w, out, trace


# Without it a carrier could skip, repeat or reverse route points, walk off its route, or index past its stored route
# (a failed macro: it would freeze mid-walk).
@pytest.mark.parametrize("wid", CARRIERS)
def test_carrier_walks_every_route_point_in_order_both_ways_within_its_stored_route(wid):
    spec = WORKERS[wid]
    w, out, trace = run_carrier(wid)
    back = w.storage["cobblers:ambient"]["p"][wid]["back"]
    n = len(out)
    xyz = lambda e: (e["x"], e["y"], e["z"], e["h"])
    assert [xyz(e) for e in back] == [xyz(e) for e in reversed(out)], "the back leg is the out leg reversed"
    # the stored route lies on data/ambient.json's route, from its first cell centre to its last, forward, in steps
    # no longer than rules.step_blocks
    pts = [(float(e["x"]), float(e["z"])) for e in out]
    assert math.dist(pts[0], centre(spec["route"][0])) < 0.011
    assert math.dist(pts[-1], centre(spec["route"][-1])) < 0.011
    arcs = []
    for p in pts:
        d, a = on_polyline(p, spec["route"])
        assert d < 0.011, (p, d)
        arcs.append(a)
    assert all(b >= a - 0.011 for a, b in zip(arcs, arcs[1:])), "the route goes backwards"
    assert max(math.dist(a, b) for a, b in zip(pts, pts[1:])) <= RULES["step_blocks"] * 1.1 + 0.02
    # every lookup inside the stored list, and each leg reads 0..n-1 in order, once per leg
    assert not w.errors, w.errors
    assert all(0 <= i < ln for _p, i, ln in w.lookups), [l for l in w.lookups if not 0 <= l[1] < l[2]][:3]
    runs = []
    for path, i, _ln in w.lookups:
        leg = path.rsplit(".", 1)[-1].split("[")[0]
        if runs and runs[-1][0] == leg:
            runs[-1][1].append(i)
        else:
            runs.append((leg, [i]))
    assert [r[0] for r in runs[:4]] == ["out", "back", "out", "back"]
    for leg, idx in runs[:-1]:
        assert idx == list(range(n)), (leg, idx[:5], len(idx))
    # the worker stands where the stored point says, with its box on it and the display above it
    h = float(spec.get("carry_height", RULES["carry_height"]))
    for leg, pos, disp, box, _item in trace:
        if leg:
            assert (round(pos[0], 2), round(pos[2], 2)) in {(round(float(e["x"]), 2), round(float(e["z"]), 2)) for e in out}
            assert math.dist(box, pos) < 1e-6 and math.dist(disp, (pos[0], pos[1] + h, pos[2])) < 1e-6


# Without it the carried item could show on the walk back, or be missing on the walk out: the work would read backwards.
@pytest.mark.parametrize("wid", CARRIERS)
def test_carried_item_shows_from_pickup_at_the_start_to_drop_at_the_end(wid):
    spec = WORKERS[wid]
    w, out, trace = run_carrier(wid)
    a = (float(out[0]["x"]), float(out[0]["z"]))
    b = (float(out[-1]["x"]), float(out[-1]["z"]))
    picks = [e for e in w.log if e[1] == "item"]
    assert picks and picks[0][2][1] == spec["carry"]
    start = next(i for i, t in enumerate(trace) if t[0] == "out")
    seen_out = seen_back = False
    for i in range(start, len(trace)):
        leg, pos, _d, _b, item = trace[i]
        if leg == "out":
            seen_out = True
            assert item == spec["carry"], (i, "out leg without the item")
        elif leg == "back":
            seen_back = True
            assert item == "minecraft:air", (i, "back leg with the item")
        if i and trace[i - 1][4] != item:
            at = (pos[0], pos[2])
            if item == spec["carry"]:
                assert math.dist(at, a) < 0.011, "picked up away from the start"
            else:
                assert math.dist(at, b) < 0.011, "set down away from the end"
    assert seen_out and seen_back
    # the pickup's and the drop's sounds sound where they happen (a neighbouring worker may share a sound name)
    (disp,) = displays(w, wid)
    for t, _k, (e, item) in [x for x in w.log if x[1] == "item" and x[2][0] is disp]:
        name, where = (spec["pickup"]["sound"], a) if item == spec["carry"] else (spec["drop"]["sound"], b)
        same = [d for tt, k, d in w.log if tt == t and k == "playsound" and d[0] == name]
        assert any(math.dist((pos[0], pos[2]), where) < 0.011 for _n, pos, _who in same), (t, name)


# Without it every R16C placement (and any re-made display) shows the load before the carrier has picked it up.
@pytest.mark.xfail(strict=True, reason="tools/ambient.py:342-345: the keeper summons the display already showing "
                                       "the carried item, and the spawn resets the clock to 0, so a new carrier holds "
                                       "it for pause-6 ticks at the start before its pickup")
@pytest.mark.parametrize("wid", CARRIERS[:1])
def test_a_newly_placed_carrier_holds_nothing_before_its_first_pickup(wid):
    w = placed(wid)
    (disp,) = displays(w, wid)
    assert disp.item in (None, "minecraft:air")


# ------------------------------------------------------------------------------------------------ station and blink jobs

# Without it a worker could strike somewhere other than its work, drift off its station, or face away from the work.
@pytest.mark.parametrize("wid", WORKS)
def test_worker_strikes_at_its_work_and_returns_to_its_station_facing_it(wid):
    spec = WORKERS[wid]
    w = placed(wid)
    every = spec.get("every", RULES["work_every"])
    w.tick(4 * every + 5)
    (poke,) = workers(w, wid)
    fx, fz = centre(spec["face"])
    sx, sz = centre(spec["at"])
    parts = [d for _t, d in w.logged("particle", "%s/w/%s/" % (F, wid))]      # its own (a neighbour may be active)
    assert parts, "no strike"
    for _name, pos in parts:
        assert (round(pos[0], 2), round(pos[2], 2)) == (fx, fz), pos
    moves = [e[2] for e in w.log if e[1] == "tp" and e[2][0] is poke]
    assert moves
    home = lambda pos: math.dist((pos[0], pos[2]), (sx, sz)) < 1e-6
    for (_e, pos, _r), nxt in zip(moves, moves[1:] + [None]):
        if not home(pos) and nxt is not None:
            assert home(nxt[1]), "a hop not followed by the return to the station"
        if not home(pos):
            # the hop leans towards the work
            assert math.dist((pos[0], pos[2]), (fx, fz)) < math.dist((sx, sz), (fx, fz))
    face_yaw = yaw_to(sx, sz, fx, fz)
    at_station = [r for _e, pos, r in moves if math.dist((pos[0], pos[2]), (sx, sz)) < 1e-6]
    assert any(abs((r[0] - face_yaw + 180) % 360 - 180) < 0.02 for r in at_station), (face_yaw, at_station[:3])
    assert not w.errors, w.errors


# Without it the Abra could skip a spot, or teleport while its box (the thing a player clicks) stays behind.
@pytest.mark.parametrize("wid", BLINKS)
def test_blinker_visits_each_spot_in_order_with_its_box(wid):
    spec = WORKERS[wid]
    w = placed(wid)
    every = spec.get("every", RULES["blink_every"])
    w.tick(2 * every * len(spec["spots"]) + 3)
    (poke,) = workers(w, wid)
    (box,) = boxes(w, wid)
    by_tick = {}
    for t, kind, d in w.log:
        if kind == "tp" and d[0] in (poke, box):
            by_tick.setdefault(t, {})[d[0].type] = (round(d[1][0], 2), round(d[1][2], 2))
    blinks = [v for t, v in sorted(by_tick.items()) if "cobblemon:pokemon" in v]
    want = [centre(s["at"]) for s in spec["spots"]]
    assert [v["cobblemon:pokemon"] for v in blinks[:2 * len(want)]] == want * 2
    assert all(v.get("minecraft:interaction") == v["cobblemon:pokemon"] for v in blinks)


# ------------------------------------------------------------------------------------------------ player-facing

# Without it a click on a worker's box says nothing, or says it forever (the click never cleared).
@pytest.mark.parametrize("wid", [CARRIERS[0], WORKS[0], BLINKS[0]])
def test_a_click_on_the_box_tells_the_clicker_the_workers_line_once(wid):
    w = placed(wid)
    p = [e for e in w.entities if e.type == "minecraft:player"][0]
    (box,) = boxes(w, wid)
    box.nbt["interaction"] = {"player": p.uid}
    w.tick(3)
    assert [m["text"] for m in p.messages] == [WORKERS[wid]["interact"]]
    assert "interaction" not in box.nbt


# Without it the sound of the work is played to players near the world spawn instead of the player watching.
@pytest.mark.xfail(strict=True, reason="tools/ambient.py:286: `playsound ... @a[distance=..24] x y z` selects players "
                                       "within 24 of the command's own position, which for a tick function is the "
                                       "world spawn, not the worker; no worker is within 24 of the spawn")
@pytest.mark.parametrize("wid", [WORKS[0]])
def test_a_player_beside_the_worker_hears_its_work(wid):
    w = placed(wid)
    p = [e for e in w.entities if e.type == "minecraft:player"][0]
    w.tick(2 * WORKERS[wid].get("every", RULES["work_every"]) + 5)
    assert [e for e in w.log if e[1] == "playsound"], "no sound was played at all"
    assert p.heard


# ------------------------------------------------------------------------------------------------ synthetic flat site

class FlatSite:
    """Ground at y 64 everywhere, nothing blocked: a worker stands at y 65. `rise_at_x` puts a cliff there."""

    def __init__(self, rise_at_x=None, rise=0):
        self.rise_at_x, self.rise = rise_at_x, rise

    def y(self, x, z):
        return 65 + (self.rise if self.rise_at_x is not None and x >= self.rise_at_x else 0)

    def blocked(self, x, z):
        return None


def synthetic(pause, route=((0, 0), (3, 0))):
    import ambient
    rules = dict(RULES, step_blocks=1.0)
    wk = {"id": "syn_carrier", "settlement": "synthetic", "species": "machop", "job": "carry", "route": [list(c) for c in route],
          "carry": "minecraft:stone", "pause_ticks": pause, "pickup": {"sound": "minecraft:block.stone.hit"},
          "drop": {"sound": "minecraft:block.stone.place"}, "interact": "A test worker."}
    pl = {"rules": rules, "workers": [ambient.plan_worker(wk, FlatSite(), rules)]}
    fns = {"%s/%s" % (F, k): v for k, v in ambient.functions(pl).items()}
    return fns, {"load": ["%s/load" % F], "tick": ["%s/tick" % F]}


# The fixture itself: a 3-block route at 1-block steps is the four cell centres x 0.5..3.5 at y 65, z 0.5, out and back.
def test_synthetic_carrier_walks_the_hand_computed_route():
    fns, tags = synthetic(10)
    w = new_world(functions=fns, tags=tags)
    w.add_player(station("syn_carrier", fns))
    w.run_load()
    w.tick(RULES["keep_every"] + 60)
    (poke,) = workers(w, "syn_carrier")
    stops = []
    for _t, kind, d in w.log:
        if kind == "tp" and d[0] is poke and (not stops or stops[-1] != d[1]):
            stops.append(d[1])
    assert stops[:7] == [(0.5, 65.0, 0.5), (1.5, 65.0, 0.5), (2.5, 65.0, 0.5), (3.5, 65.0, 0.5),
                         (2.5, 65.0, 0.5), (1.5, 65.0, 0.5), (0.5, 65.0, 0.5)]


def _item_by_leg(pause):
    fns, tags = synthetic(pause)
    w = new_world(functions=fns, tags=tags)
    w.add_player(station("syn_carrier", fns))
    w.run_load()
    w.tick(RULES["keep_every"])
    bad = []
    for _ in range(3 * 2 * (pause + 4)):
        k = len(w.lookups)
        w.tick()
        legs = {p.rsplit(".", 1)[-1].split("[")[0] for p, _i, _n in w.lookups[k:]}
        (disp,) = displays(w, "syn_carrier")
        if w.tick_no > RULES["keep_every"] + 2 * (pause + 4):          # after one full round trip
            if "out" in legs and disp.item != "minecraft:stone":
                bad.append((w.tick_no, "out", disp.item))
            if "back" in legs and disp.item != "minecraft:air":
                bad.append((w.tick_no, "back", disp.item))
    return bad


# Without it a longer or shorter pause could move the pickup or the drop onto a walk.
@pytest.mark.parametrize("pause", [6, 10, 40])
def test_item_on_the_out_leg_only_for_pauses_of_six_ticks_or_more(pause):
    assert _item_by_leg(pause) == []


# Without it a worker authored with a short pause shows its load on the walk back (the pickup tick wraps round the loop).
@pytest.mark.xfail(strict=True, reason="tools/ambient.py:455-456: `up = pause - 6` is negative below 6 ticks and wraps "
                                       "(tk % period) onto the back leg, and `down = pause + n + 4` falls on the back "
                                       "leg below 4; plan_worker does not refuse pause_ticks < 6")
@pytest.mark.parametrize("pause", [1, 3, 5])
def test_item_on_the_out_leg_only_for_short_pauses(pause):
    assert _item_by_leg(pause) == []
