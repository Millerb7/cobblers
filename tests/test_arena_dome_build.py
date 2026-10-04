"""The builder's own geometry checks for tools/arena_dome.py (Heaven's Arena as a dome on the Deep's north floor).

Written by the builder; the independent audit is someone else's. These check the shape against data/arena_dome.json
and the runtime contract: venues on floor with two air above every mark, spot and post, 13x13 clear rings with 8 of
headroom, nothing written outside the site's disc and its tower's box, the shell closed except at the door, every mark
walkable from the door, and the reapply wiring. The city check needs the canonical heightmap and is skipped without it.
"""
from __future__ import annotations

import json
import math
import sys
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import arena_dome as A  # noqa: E402

SPEC = json.loads((ROOT / "data" / "arena_dome.json").read_text(encoding="utf-8"))
FIGHTS = json.loads((ROOT / "data" / "arena_fights.json").read_text(encoding="utf-8"))
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])


@pytest.fixture(scope="module")
def cv():
    return A.geometry(SPEC)


def _cell(p):
    return math.floor(p[0]), int(p[1]), math.floor(p[2])


# ------------------------------------------------------------------ the contract

def test_the_contract_fields_are_present():
    # the owner, 2026-10-03: "can we move the tower to the center, it's very close to the spire"
    assert SPEC["site"]["centre"] == [3586, 3164] and SPEC["site"]["radius"] == 34 and SPEC["site"]["floor_y"] == 0
    e = SPEC["entrance"]
    assert len(e["door"]) == 3 and isinstance(e["route"], str) and e["route"]
    assert len(SPEC["venues"]) >= 4
    for v in SPEC["venues"]:
        assert isinstance(v["id"], str) and isinstance(v["name"], str) and v["name"]
        assert v["ranks"] and all(isinstance(r, int) for r in v["ranks"])
        assert len(v["challenger_mark"]) == 4 and len(v["opponent_spot"]) == 4 and len(v["post"]) == 3
    assert SPEC["venues"][0]["id"] == "venue_1"


def test_the_ranks_are_spread_over_the_venues():
    want = sorted(r["rank"] for r in FIGHTS["ranks"])
    got = sorted(r for v in SPEC["venues"] for r in v["ranks"])
    assert got == want
    assert SPEC["venues"][0]["ranks"] == [1, 2, 3]
    cx, cz = SPEC["site"]["centre"]
    grand = [v for v in SPEC["venues"] if 9 in v["ranks"]][0]
    assert grand["centre"] == [cx, cz]


def test_the_opponent_stands_8_across_facing_the_mark():
    for v in SPEC["venues"]:
        m, s = v["challenger_mark"], v["opponent_spot"]
        assert m[1] == s[1]
        assert math.hypot(m[0] - s[0], m[2] - s[2]) == pytest.approx(8)
        for a, b in ((m, s), (s, m)):
            look = (-math.sin(math.radians(a[3])), math.cos(math.radians(a[3])))
            assert look[0] * (b[0] - a[0]) / 8 + look[1] * (b[2] - a[2]) / 8 == pytest.approx(1, abs=1e-6), v["id"]
        p = v["post"]
        assert p[1] == m[1] and 1 <= math.hypot(p[0] - m[0], p[2] - m[2]) <= 3


def test_every_mark_spot_and_post_is_floor_with_two_air_above(cv):
    for v in SPEC["venues"]:
        for p in (v["challenger_mark"], v["opponent_spot"], v["post"]):
            x, y, z = _cell(p)
            assert p[0] == x + 0.5 and p[2] == z + 0.5
            assert A.solid(cv.get(x, y - 1, z)), (v["id"], p, cv.get(x, y - 1, z))
            assert cv.get(x, y, z) == "minecraft:air" and cv.get(x, y + 1, z) == "minecraft:air", (v["id"], p)


def test_every_venue_has_13x13_clear_floor_and_8_of_headroom(cv):
    for v in SPEC["venues"]:
        x, y, z = _cell(v["challenger_mark"])
        top = y - 1
        vx, vz = v["centre"]
        for dx in range(-6, 7):
            for dz in range(-6, 7):
                assert A.solid(cv.get(vx + dx, top, vz + dz)), (v["id"], dx, dz)
                assert all(cv.get(vx + dx, yy, vz + dz) == "minecraft:air" for yy in range(top + 1, top + 9)), (v["id"], dx, dz)


def test_venues_do_not_overlap_and_stay_off_the_drum_wall(cv):
    cx, cz = SPEC["site"]["centre"]
    inner = SPEC["drum"]["wall"][0]
    cols = {}
    for (x, _y, z), o in cv.owner.items():
        if o.startswith("venue_"):
            cols.setdefault(o, set()).add((x, z))
    assert sorted(cols) == sorted(v["id"] for v in SPEC["venues"])
    for vid, cs in cols.items():
        # at least one column of walkway between a venue (ring and steps) and the drum's inner face
        assert all(math.hypot(x - cx, z - cz) < inner - 1 for x, z in cs), vid
        for o, os_ in cols.items():
            if o != vid:
                assert not cs & os_, (vid, o)


# ------------------------------------------------------------------ the shape

def test_nothing_is_written_outside_the_disc_and_the_tower(cv):
    cx, cz = SPEC["site"]["centre"]
    R = SPEC["site"]["radius"]
    x0, z0, x1, z1 = SPEC["tower"]["box"]
    for (x, y, z) in cv.v:
        assert math.hypot(x - cx, z - cz) <= R or (x0 <= x <= x1 and z0 <= z <= z1), (x, y, z)
        assert y >= SPEC["site"]["floor_y"]


def test_the_crown_shows_over_the_lip_and_stays_under_the_hq(cv):
    top = max(y for (_x, y, _z) in cv.v)
    assert 83 < top <= 131


def test_no_light_block_no_water_no_iron_and_no_spawn_block(cv):
    used = {b.split("[")[0] for (b, _ph) in cv.v.values()}
    assert "minecraft:light" not in used and "minecraft:water" not in used
    assert not [b for b in used if "iron" in b]
    assert not used & SPAWN, sorted(used & SPAWN)
    assert not [b for (b, _ph) in cv.v.values() if "waterlogged=true" in b]


def test_the_lanterns_go_down_after_what_they_stand_on(cv):
    for (x, y, z), (b, ph) in cv.v.items():
        if b.startswith("minecraft:lantern"):
            assert ph == 2 and A.solid(cv.get(x, y - 1, z)) and cv.v[(x, y - 1, z)][1] == 1


def test_the_shell_is_closed_except_at_the_door(cv):
    """From the grand stage, through everything that is not solid, never to a cell this build does not write: with
    the door's opening filled, the dome and tower hold their air."""
    d = SPEC["tower"]["door"]
    door = {(x, y, d["z"]) for x in range(d["x"][0], d["x"][1] + 1) for y in range(1, d["to_y"] + 1)}
    start = _cell(SPEC["venues"][-1]["challenger_mark"])
    seen = {start}
    q = deque([start])
    while q:
        x, y, z = q.popleft()
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (x + dx, y + dy, z + dz)
            if n in seen or n in door:
                continue
            b = cv.get(*n)
            assert b is not None, "the air inside reaches %s, which this build does not write" % (n,)
            if A.solid(b):
                continue
            seen.add(n)
            q.append(n)
    # most of the volume under the shell: the drum's cylinder to its top and the inner half-ellipsoid above it
    ri = SPEC["drum"]["wall"][0]
    hi = SPEC["dome"]["rise"] - SPEC["dome"]["thickness"]
    assert len(seen) > 0.8 * math.pi * ri * ri * (SPEC["drum"]["top"] + 2 * hi / 3)


def test_every_mark_is_walkable_from_the_door(cv):
    def stand(x, y, z):
        return (not A.solid(cv.get(x, y, z)) and cv.get(x, y, z) is not None
                and not A.solid(cv.get(x, y + 1, z)) and cv.get(x, y + 1, z) is not None
                and A.solid(cv.get(x, y - 1, z)))

    start = tuple(SPEC["entrance"]["door"])
    assert stand(*start)
    seen = {start}
    q = deque([start])
    while q:
        x, y, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1):
                n = (x + dx, y + dy, z + dz)
                if n not in seen and 1 <= n[1] <= 6 and stand(*n):
                    seen.add(n)
                    q.append(n)
    for v in SPEC["venues"]:
        for p in (v["challenger_mark"], v["opponent_spot"], v["post"]):
            assert _cell(p) in seen, (v["id"], p)


# ------------------------------------------------------------------ the wiring

def test_the_pack_is_prepared_and_applied_after_the_city():
    import reapply
    assert "cobblers_arena_dome" in reapply.SERVER_PACKS and "cobblers_arena_dome" not in reapply.EXCLUDED
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    prep = src.split("def prepare")[1].split("def install")[0]
    assert prep.index('"deep_city.py"') < prep.index('"arena_dome.py", "build"')
    assert src.index('("R9DC"') < src.index('("R9AD"') < src.index('("R9RU"') < src.index('("R9E"')
    assert 'indexed("cobblers_arena_dome", "arena_dome")' in src


# ------------------------------------------------------------------ against the city (needs the heightmap)

@pytest.fixture(scope="module")
def city():
    from terrain import env_source_root
    root = env_source_root()
    if not root or not Path(root).is_dir():
        pytest.skip("no source root: the city's plan comes from the heightmap")
    return root, A.city_state(root)


def test_the_dome_touches_no_lot_tower_keep_clear_or_door(cv, city):
    root, state = city
    probs, stats = A.city_problems(SPEC, cv, root, state)
    assert not probs, probs
    assert stats["street"] >= SPEC["limits"]["min_street"]


def test_the_door_is_reached_on_foot_from_the_lift_bank_3_stair(cv, city):
    """2D: columns of y0 floor with nothing the city or the dome writes at y1-2, from beside the stair tower's door
    (3580, 3241) to the tower door's outside."""
    _root, (ccv, _plan, M) = city
    X0, Z0 = M["X0"], M["Z0"]
    NZ, NX = M["shape"]
    high = {(x, z) for (x, y, z), (b, _ph) in ccv.v.items() if y in (1, 2) and A.solid(b)}
    ours = {(x, z) for (x, _y, z) in cv.v}

    def ok(x, z):
        a, b = z - Z0, x - X0
        return (0 <= a < NZ and 0 <= b < NX and bool(M["mask"][a, b]) and int(M["T"][a, b]) == 0
                and (x, z) not in high and (x, z) not in ours)

    out = SPEC["entrance"]["outside"]
    goal = (out[0], out[2])
    start = (3581, 3241)
    assert ok(*start) and ok(*goal)
    dist = {start: 0}
    q = deque([start])
    while q:
        c = q.popleft()
        if c == goal:
            break
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dz)
            if n not in dist and ok(*n):
                dist[n] = dist[c] + 1
                q.append(n)
    assert goal in dist
    assert dist[goal] < 80


# ------------------------------------------------------------------ the move, and the staging-only undo of site A

SPIRE = ((3609, 3249), 16)     # the city's Core spire (data/deep_city.json arena drum), which stays


def _spire_gap(spec, cv):
    (sx, sz), sr = SPIRE
    cx, cz = spec["site"]["centre"]
    R = spec["site"]["radius"]
    drum = {(x, z) for (x, _y, z) in cv.v if math.hypot(x - cx, z - cz) <= R}
    return min(math.hypot(x - sx, z - sz) for x, z in drum) - sr


def test_the_dome_moved_away_from_the_spire_and_toward_the_middle(cv):
    old = A.superseded_spec(SPEC)
    assert old["site"]["centre"] == [3584, 3171] and old["site"]["radius"] == 40
    new_gap, old_gap = _spire_gap(SPEC, cv), _spire_gap(old, A.geometry(old))
    assert new_gap > old_gap + 10, (new_gap, old_gap)
    middle = (3586, 3147)      # the owner's "middle" of the north floor (relayed in the move's brief)
    d = lambda s: math.hypot(s["site"]["centre"][0] - middle[0], s["site"]["centre"][1] - middle[1])  # noqa: E731
    assert d(SPEC) < d(old)
    assert 30 <= SPEC["site"]["radius"] <= 34


def test_the_superseded_site_keeps_what_the_undo_needs():
    old = SPEC["superseded_site"]
    assert "very close to the spire" in old["owner"] and old["why"]
    for k in A.GEOMETRY_KEYS:
        assert k in old, k
    assert [v["id"] for v in old["venues"]] == [v["id"] for v in SPEC["venues"]]


def test_the_undo_never_lands_in_build_datapacks():
    assert A.UNDO_OUT.parent.name == "staging"
    with pytest.raises(A.DomeError):
        A.write_undo({}, [], ROOT / "build" / "datapacks" / "cobblers_arena_dome_undo")
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert "arena_dome_undo" not in src and '"arena_dome.py", "undo"' not in src


def test_the_undo_kills_the_old_posts_by_the_runtime_s_tag_and_never_a_live_one():
    import arena_runtime
    assert A.POST_TAG == arena_runtime.POST
    old = A.undo_posts(SPEC)
    assert len(old) == len(SPEC["superseded_site"]["venues"])
    for p in old:
        for v in SPEC["venues"]:
            q = v["post"]
            assert math.dist(p, (math.floor(q[0]) + 0.5, q[1], math.floor(q[2]) + 0.5)) >= 1.0


def test_the_undo_restores_the_city_and_leaves_the_new_dome_alone(cv, city):
    _root, state = city
    ccv, _plan, M = state
    cells, first, st = A.undo_plan(SPEC, state)
    old = A.geometry(A.superseded_spec(SPEC))
    assert st["box"] == [3544, 0, 3131, 3624, 126, 3216]
    # every cell the old dome wrote is either the new dome's or restored, never both, never neither
    assert set(cells) | {c for c in old.v if c in cv.v} == set(old.v)
    assert not set(cells) & set(cv.v)
    for c, b in cells.items():
        if c in ccv.v:
            assert b == ccv.v[c][0], c
        elif c[1] == 0:
            assert c in M["L1"], c
        else:
            assert b == "minecraft:air", c
    assert st["city"] > 0 and st["air"] > 0
    assert all(old.v[c][0].startswith("minecraft:lantern") for c in first)
    fns, order, _st = A.undo_functions(SPEC, state)
    assert order[-1] == "z_entities_release" and order[0].startswith("a_")
    assert fns[order[-1]][-1].startswith("forceload remove")
