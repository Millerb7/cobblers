"""Rayquaza's home (tools/rayquaza_sky.py, data/rayquaza_sky.json): the sealed arch on the great cone, the floating island, the
pillar's climb, the keeper and the End's override.

Written by the same session that wrote the generator (the 2026-10-13 brief asked the builder for its own tests; CLAUDE.md principle
16 wants a different agent for the independent audit, which is listed in the unit's report and NOT this file). These tests read the
generator's own model, so they prove the generator does what it says, not that what it says is right; what keeps them from being a
pure mirror: the walks are a separate voxel walker over the emitted cells, the keeper and the arch RUN on tests/gulch_sim.py's world
(the sanctuaries' Lake harness), and the wiring is read from tools/reapply.py's own step list.
"""
from __future__ import annotations

import collections
import functools
import json
import math
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import function_limits as FL  # noqa: E402
import rayquaza_sky as R  # noqa: E402

SPEC = R.load()
OCC = SPEC["occupant"]
KEEP = OCC["keeper"]
OBJ = SPEC["objective"]
CHAMPION = "cobblers:flag/champion_cleared"
KYOGRE = "cobblers:legendary/kyogre/met"
GROUDON = "cobblers:legendary/groudon/met"
CAUGHT = "cobblers:legendary/rayquaza/caught"
QUALIFIED = (CHAMPION, KYOGRE, GROUDON)
TAG, DORM, GUARD = OCC["tag"], OCC["dormant_tag"], OCC["guardian_tag"]


@functools.lru_cache(maxsize=None)
def _ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@functools.lru_cache(maxsize=None)
def _model():
    return R.geometry(SPEC, _ground())


@pytest.fixture(scope="module")
def model():
    return _model()


@functools.lru_cache(maxsize=None)
def _files():
    return R.pack_files(SPEC, _model())


def fns():
    pre = "data/cobblers/function/rayquaza/"
    return {"rayquaza/" + k[len(pre):-len(".mcfunction")]: v.splitlines() for k, v in _files().items()
            if k.startswith(pre) and k.endswith(".mcfunction")}


# ------------------------------------------------------------------ the record

def test_the_record_carries_the_owners_decisions():
    # without it the gate, the level or the species could drift from the owner's answer 6 (KYOGRE_CAVE.md section 9)
    assert OCC["species"] == "rayquaza" and OCC["level"] == 70
    assert SPEC["gate"]["flags"] == ["champion_cleared"] and sorted(SPEC["gate"]["requires_met"]) == ["groudon", "kyogre"]
    assert R.gate_advancements(SPEC) == [CHAMPION, KYOGRE, GROUDON]
    assert SPEC["upstream_neutralised"]["function"] == "cobbleverse:spawn_rayquaza"


def test_rayquaza_is_not_also_a_legendaries_encounter():
    # without it data/legendaries.json could gain a rayquaza record, and its pack would ship cobblers:legendary/rayquaza/met beside ours
    doc = json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))
    assert "rayquaza" not in {r["id"] for r in doc["encounters"]}


def test_the_summit_is_the_great_cones_highest_column():
    # without it the arch could stand on a shoulder: the owner put it on the great cone's summit
    g = _ground()
    s = SPEC["site"]["summit"]
    box = g.box(s["x"] - 300, s["z"] - 300, s["x"] + 300, s["z"] + 300)
    assert g(s["x"], s["z"]) == s["y"] == int(box.max())


# ------------------------------------------------------------------ the shape

def test_the_island_floats_high_over_the_cone_where_it_is_seen(model):
    # visible early: the island's top is well over the summit, every column of it clears the ground, and the crown stays under the
    # runtime ceiling with room to spare
    g = _ground()
    isl = model.marks["island"]
    assert isl["top_y"] - SPEC["site"]["summit"]["y"] >= 48
    assert isl["columns"] >= 2000
    assert model.marks["island_low"] - model.marks["arch"]["top"] >= 15
    x0, z0, x1, z1 = isl["bounds"]
    for x in range(x0, x1 + 1, 3):
        for z in range(z0, z1 + 1, 3):
            ys = [y for (cx, y, cz), b in model.cells.items()
                  if cx == x and cz == z and b != R.AIR and y > model.marks["arch"]["top"] + 8]
            if ys:
                assert min(ys) - g(x, z) >= 8, (x, z)
    assert model.marks["pillar"]["crown_top"] <= R.CEILING - 16


def test_it_is_built_of_many_weathered_blocks_and_no_light_block(model):
    # no engineering looks: a varied palette, lanterns only on posts or hanging, and no spawn-condition block
    kinds = {R.base(b) for b in model.cells.values()} - {R.AIR}
    assert len(kinds) >= 25, sorted(kinds)
    assert R.light_problems(model, SPEC) == []
    assert R.spawn_block_problems(model) == []
    assert "minecraft:lightning_rod" not in kinds


# ------------------------------------------------------------------ the walks

def _kind(cells, c):
    b = cells.get(c)
    if b is None:
        return "air"
    base = R.base(b)
    if base in ("minecraft:air", "minecraft:short_grass", "minecraft:fern", "minecraft:moss_carpet", "minecraft:hanging_roots") \
            or base.endswith("_wall_sign"):
        return "air"
    if base.endswith("_slab") and "type=bottom" in b:
        return "slab"
    if base in ("minecraft:lantern", "minecraft:mossy_cobblestone_wall"):
        return "post"
    return "full"


def _valid(cells, x, z, h2):
    if h2 % 2 == 0:
        k = h2 // 2
        return _kind(cells, (x, k - 1, z)) == "full" and _kind(cells, (x, k, z)) == "air" and _kind(cells, (x, k + 1, z)) == "air"
    k = (h2 - 1) // 2
    return _kind(cells, (x, k, z)) == "slab" and _kind(cells, (x, k + 1, z)) == "air" and _kind(cells, (x, k + 2, z)) == "air"


def walk(cells, start, up=1, down=6, limit=200000):
    """Every (x, z, 2 x stand height) a walker reaches from `start`: four ways, up at most `up` half-blocks (1: no jump), down
    at most `down`. Cells the model does not write are air (the island is in open sky)."""
    seen = {start}
    q = collections.deque([start])
    while q and len(seen) < limit:
        x, z, h2 = q.popleft()
        for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            for t in range(h2 + up, h2 - down - 1, -1):
                if (nx, nz, t) in seen:
                    break
                if _valid(cells, nx, nz, t):
                    seen.add((nx, nz, t))
                    q.append((nx, nz, t))
                    break
    return seen


def test_the_crown_is_climbed_from_the_landing_without_a_jump(model):
    # without it the helix has a step a walker cannot take, or the top floor never opens onto the crown
    lx, ly, lz = model.marks["pillar"]["landing"]
    start = (lx, lz, 2 * ly)
    assert _valid(model.cells, *start), start
    seen = walk(model.cells, start, up=1)
    yF = model.marks["pillar"]["top_floor_y"]
    sx, _sy, sz = model.marks["pillar"]["spot"]
    crown = [n for n in seen if n[2] == 2 * (yF + 1) and math.hypot(n[0] + 0.5 - sx, n[1] + 0.5 - sz) <= 4]
    assert crown, "the crown is not reached from the landing (highest stand %s)" % (max(n[2] for n in seen) / 2.0,)


def _recess_cells(model):
    x0, y0, z0, x1, _y1, z1 = model.marks["pillar"]["recess"]
    return {(x, z, 2 * y0) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}


def test_every_place_on_the_island_reaches_the_alcove_back_down(model):
    # never trap anyone: from the crown, from the landing and from the island's south overlook (an early flyer's landing), a walker
    # (jumps allowed) reaches the alcove that sends everyone back to the summit
    p = model.marks["pillar"]
    yF = p["top_floor_y"]
    recess = _recess_cells(model)
    starts = {"crown": (p["centre"][0] + 3, p["centre"][1] - 1, 2 * (yF + 1)),
              "landing": (p["landing"][0], p["landing"][2], 2 * p["landing"][1])}
    isl = model.marks["island"]
    ox, oz = p["centre"][0], isl["centre"][1] + int(SPEC["island"]["half_z"] * 0.6)
    top = max(y for (x, y, z), b in model.cells.items() if x == ox and z == oz and _kind(model.cells, (x, y, z)) == "full")
    starts["overlook"] = (ox, oz, 2 * (top + 1))
    for name, s in starts.items():
        assert _valid(model.cells, *s), (name, s)
        assert walk(model.cells, s, up=2) & recess, "%s does not reach the alcove" % name


def test_the_landings_are_clear_of_the_zones_that_send_a_player_back(model):
    # without it a player arriving at either end is bounced straight back by the other end's zone
    a, p = model.marks["arch"], model.marks["pillar"]

    def inside(c, b):
        return b[0] <= c[0] <= b[3] and b[1] <= c[1] <= b[4] and b[2] <= c[2] <= b[5]
    assert not inside(a["landing"], a["door"]) and not inside(p["landing"], p["recess"])
    assert _valid(model.cells, p["landing"][0], p["landing"][2], 2 * p["landing"][1])
    assert model.cells.get(tuple(a["landing"]), R.AIR) == R.AIR and model.cells.get((a["landing"][0], a["landing"][1] - 1, a["landing"][2]))
    assert not inside(p["landing"], model.marks["rescue"]) and not inside(a["landing"], model.marks["rescue"])


# ------------------------------------------------------------------ the packs

def test_the_build_is_its_own_pack_and_the_runtime_writes_no_blocks(tmp_path):
    # memory: the one-shot geometry must leave the heap after the apply (reapply.py strip), and the runtime pack stays small
    out, bout = R.write(_files(), tmp_path / "cobblers_rayquaza")
    built = sorted(p.relative_to(bout).as_posix() for p in bout.rglob("*.mcfunction"))
    assert built == ["data/cobblers/function/rayquaza/build.mcfunction"]
    for f in out.rglob("*.mcfunction"):
        for line in f.read_text(encoding="utf-8").splitlines():
            assert not line.startswith(("fill ", "setblock ", "clone ")), (f.name, line)
    body = (bout / built[0]).read_text(encoding="utf-8").splitlines()
    assert FL.check_lines(body, "build") == [] and any(l.startswith("forceload add") for l in body)


def test_the_ends_shiny_rayquaza_is_overridden_empty():
    # the owner's answer 5: every player's first End entry scheduled cobbleverse:spawn_rayquaza, a shiny level-100 Rayquaza
    text = _files()["data/cobbleverse/function/spawn_rayquaza.mcfunction"]
    assert [l for l in text.splitlines() if l.strip() and not l.startswith("#")] == []


def test_the_capture_callback_records_the_catcher_near_the_crown_only():
    cb = _files()["data/cobblemon/callbacks/pokemon_captured/cobblers_rayquaza.molang"]
    assert "t.id == 'cobblemon:rayquaza'" in cb and "distance=..%d] run function cobblers:rayquaza/caught" % KEEP["catch_radius"] in cb
    assert any(l == "advancement grant @s only %s" % CAUGHT for l in fns()["rayquaza/caught"])


def test_the_probes_are_in_sync(model):
    assert not R.probes_drift(SPEC, model)


def test_reapply_runs_the_build_after_the_chambers_and_installs_both_packs_world_local():
    import reapply
    assert "cobblers_rayquaza" in reapply.SERVER_PACKS and "cobblers_rayquaza_build" in reapply.SERVER_PACKS
    assert "cobblers_rayquaza" in reapply.WORLD_LOCAL and "cobblers_rayquaza_build" in reapply.WORLD_LOCAL
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert 'add("rayquaza_sky:build", "rayquaza_sky.py", "build", *src)' in src
    i, j = src.index('out.append(("R14L"'), src.index('out.append(("R14R"')
    assert i < j
    assert R.placement_steps() == [("fn", "cobblers:rayquaza/build")]


# ------------------------------------------------------------------ the arch, the alcove, the fall (run on the sim)

def _world():
    from test_sanctuaries import Lake
    w = Lake(fns())
    w.gt = 5_000_000
    w.call("rayquaza/load")
    return w


def _door_mid(model):
    d = model.marks["arch"]["door"]
    return ((d[0] + d[3]) / 2.0 + 0.5, d[1], (d[2] + d[5]) / 2.0 + 0.5)


def test_the_arch_takes_up_only_a_player_who_holds_the_gate(model):
    w = _world()
    lx, ly, lz = model.marks["pillar"]["landing"]
    yes = w.player(_door_mid(model), flags=QUALIFIED)
    no = w.player(_door_mid(model), flags=(CHAMPION, GROUDON))
    w.call("rayquaza/arch")
    assert yes["pos"] == (lx + 0.5, ly, lz + 0.5)
    assert no["pos"] == _door_mid(model)
    told = [l for l in w.log if l.startswith("tellraw @s") and "sea mark" in l]
    assert len(told) == 1 and not [l for l in w.log if "fire mark" in l]
    w.call("rayquaza/arch")
    assert len([l for l in w.log if "sea mark" in l]) == 1, "an unqualified player is told once a visit, not every pass"


def test_anyone_in_the_alcove_goes_back_down_to_the_summit(model):
    w = _world()
    x0, y0, z0, x1, _y1, z1 = model.marks["pillar"]["recess"]
    flyer = w.player((x0 + 0.5, y0, z0 + 0.5))
    w.call("rayquaza/island")
    rx, ry, rz = model.marks["arch"]["landing"]
    assert flyer["pos"] == (rx + 0.5, ry, rz + 0.5)


def test_a_fall_under_the_island_gets_slow_falling(model):
    b = model.marks["rescue"]
    line = next(l for l in fns()["rayquaza/island"] if l.startswith("effect give"))
    assert "minecraft:slow_falling" in line and R.sel_box(b) in line
    assert b[1] >= model.marks["ground_max_under"] + 3 and b[4] == SPEC["island"]["top_y"] - 1


# ------------------------------------------------------------------ the keeper (run on the sim)

PASS = KEEP["period_ticks"]


def rays(w):
    return [e for e in w.entities if TAG in e["tags"]]


def passes(w, n):
    out = []
    for _ in range(n):
        w.gt += PASS
        w.call("rayquaza/keeper")
        out.append(len(rays(w)))
    return out


def near(model, w, dx, dz, dy=0.0, flags=QUALIFIED):
    sx, sy, sz = model.marks["pillar"]["spot"]
    return w.player((sx + dx, sy + dy, sz + dz), flags=flags)


def on_crown(model, w, flags=QUALIFIED):
    return near(model, w, 3.0, 0.0, -1.0, flags)


def test_nothing_spawns_for_a_player_who_does_not_hold_the_gate_or_has_caught_it(model):
    for flags in ((), (CHAMPION,), (CHAMPION, GROUDON), (CHAMPION, KYOGRE), QUALIFIED + (CAUGHT,)):
        w = _world()
        near(model, w, KEEP["spawn_clear"] + 6, 0, -30, flags)
        assert passes(w, 4) == [0, 0, 0, 0], flags


def test_one_dormant_rayquaza_comes_for_a_qualified_player_and_never_in_front_of_anyone(model):
    w = _world()
    p = near(model, w, 0.4, 0.4)                     # standing on the spot
    assert passes(w, 3) == [0, 0, 0]
    p["pos"] = (p["pos"][0] + KEEP["spawn_clear"] + 4, p["pos"][1] - 30, p["pos"][2])
    assert passes(w, 2) == [1, 1]          # the absent passes were already counted while the player stood on the spot
    (r,) = rays(w)
    assert DORM in r["tags"] and r["nbt"]["Pokemon"]["Level"] == 70 and "no_ai" in r["props"]
    assert passes(w, 3) == [1, 1, 1]


def test_it_is_withdrawn_when_no_qualified_player_is_near_and_its_drops_go_under_the_world(model):
    w = _world()
    p = near(model, w, KEEP["spawn_clear"] + 4, 0, -30)
    passes(w, 2)
    assert len(rays(w)) == 1
    w.entities.remove(p)
    w.log.clear()
    passes(w, 1)
    assert rays(w) == []
    tp = [i for i, l in enumerate(w.log) if l.startswith("tp @s") and " -200 " in l]
    kill = [i for i, l in enumerate(w.log) if l == "kill @s"]
    assert tp and kill and tp[0] < kill[0]
    # a withdrawal starts no clock: the next qualified player brings it straight back
    near(model, w, KEEP["spawn_clear"] + 4, 0, -30)
    assert passes(w, KEEP["absent_passes"] + 1)[-1] == 1


def test_it_wakes_for_a_qualified_player_on_the_crown_but_never_with_a_stranger_there(model):
    w = _world()
    near(model, w, KEEP["spawn_clear"] + 4, 0, -30)
    passes(w, 2)
    (r,) = rays(w)
    stranger = on_crown(model, w, flags=(CHAMPION,))
    p = on_crown(model, w)
    passes(w, 2)
    assert DORM in r["tags"], "it woke with a stranger on the crown"
    w.entities.remove(stranger)
    passes(w, 1)
    assert DORM not in r["tags"] and str(r["nbt"].get("Unbattleable")) in ("0b", "0")
    stranger = on_crown(model, w, flags=())
    passes(w, 1)
    assert DORM in r["tags"] and any("will not answer" in l for l in w.log)
    del p


def test_a_guardian_is_never_held_withdrawn_or_discarded(model):
    # C27: the blackout's guardian holds a player's items; the keeper only counts it
    w = _world()
    near(model, w, KEEP["spawn_clear"] + 4, 0, -30)
    passes(w, 2)
    (r,) = rays(w)
    r["tags"].add(GUARD)
    r["pos"] = (r["pos"][0] + 6, r["pos"][1], r["pos"][2])
    for e in [e for e in w.entities if e.get("kind") == "player"]:
        w.entities.remove(e)
    passes(w, 4)
    assert w.alive(r) and r["pos"][0] == model.marks["pillar"]["spot"][0] + 6
    for name, body in fns().items():
        for line in body:
            # every selector that ACTS on one of ours (as, kill): a presence test or a count only reads
            if ("as @e[type=cobblemon:pokemon,tag=%s" % TAG in line) or ("kill @e[" in line):
                assert "tag=!%s" % GUARD in line, (name, line)


def test_a_catch_starts_the_short_clock_and_the_catcher_never_brings_it_back(model):
    w = _world()
    p = near(model, w, KEEP["spawn_clear"] + 4, 0, -30)
    passes(w, 2)
    (r,) = rays(w)
    w.me, w.pos = p, p["pos"]
    w.call("rayquaza/caught")
    w.me = None
    p["flags"].add(CAUGHT)
    w.entities.remove(r)
    friend = near(model, w, KEEP["spawn_clear"] + 5, 0, -30)
    n = (KEEP["cooldown_catch_ticks"] // PASS) - 1
    assert set(passes(w, n)) == {0}
    assert passes(w, 4)[-1] == 1, "the qualified friend who has not caught it gets their own"
    del friend


def test_a_faint_starts_the_long_clock(model):
    w = _world()
    near(model, w, KEEP["spawn_clear"] + 4, 0, -30)
    passes(w, 2)
    (r,) = rays(w)
    w.entities.remove(r)
    n = (KEEP["cooldown_faint_ticks"] // PASS) - 1
    assert set(passes(w, n)) == {0}
    assert passes(w, 4)[-1] == 1
