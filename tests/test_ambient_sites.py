"""Where the working Pokemon stand, and how the pack is put together and re-applied (tools/ambient.py,
data/ambient.json, build/datapacks/cobblers_ambient, tools/reapply.py R16C).

Written by the test author, not by the session that built the pack (e3c84ed). The site rules are recomputed here
without ambient.Site or tools/town_dressing.py, from:
  derived/towns/<town>_plan.json       lots, anchors, lamps, street cells (tools/town_plan.py: a shared input)
  derived/towns/<town>_placement.json  every placed building's footprint, as tools/place_town.py recorded it
  data/placements.json                 donors and gyms by position and size; earthwork commands
  build/datapacks/cobblers_town_dressing  the dressing's non-air block writes (what a worker would stand in)
  derived/water_shape/changed.npy      columns the pending water export changes (margin: rules.water_changed_margin)
  tools/ground.py                      the canonical heightmap, rounded (slow; COBBLERS_SOURCE_ROOT)
and checked against every position the shipped pack moves a worker to (its spawn, its stored route, every tp in its
step), plus the data's own routes sampled finely.

Needs the built pack and derived/ambient/plan.json (python tools/ambient.py build --source-root <root>); without them
the pack tests SKIP (NOT_EXECUTED). Not covered: that the town looks right around a worker, that a worker's hop does
not clip a block the plan does not know (a fence, a sign), anything in a world.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ambient  # noqa: E402
import function_limits  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_ambient"
FNDIR = PACK / "data" / "cobblers" / "function" / "ambient"
DRESSING = ROOT / "build" / "datapacks" / "cobblers_town_dressing" / "data" / "cobblers" / "function" / "town_dressing"
DATA = json.loads((ROOT / "data" / "ambient.json").read_text(encoding="utf-8"))
RULES = DATA["rules"]
WORKERS = {w["id"]: w for w in DATA["workers"] + (DATA.get("superseded_workers") or {}).get("workers", [])}  # superseded records are the format samples since the town files (2026-10-05)
DOC = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
WORLD = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
SPAWN_BLOCKS = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
F = "cobblers:ambient"


def pack():
    idx = FNDIR / "index.txt"
    if not idx.is_file() or idx.read_text(encoding="utf-8").split() != list(WORKERS):
        pytest.skip("NOT_EXECUTED: build/datapacks/cobblers_ambient is not built from data/ambient.json here "
                    "(python tools/ambient.py build --source-root <root>)")
    return {p.relative_to(FNDIR).with_suffix("").as_posix(): p.read_text(encoding="utf-8").splitlines()
            for p in FNDIR.rglob("*.mcfunction")}


def rect(r, m=0):
    x0, z0, x1, z1 = r
    return {(x, z) for x in range(min(x0, x1) - m, max(x0, x1) + m + 1) for z in range(min(z0, z1) - m, max(z0, z1) + m + 1)}


XZ = re.compile(r"^(fill|setblock)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)(?:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+))?\s+(\S+)")


def write_columns(lines, non_air=True):
    out = set()
    for l in lines:
        m = XZ.match(l.strip())
        if not m:
            continue
        kind, x0, _y0, z0, x1, _y1, z1, block = m.groups()
        if kind == "setblock":
            x1, z1 = x0, z0
        if non_air and block.split("[")[0] in ("minecraft:air", "air", "minecraft:cave_air"):
            continue
        out |= rect((int(x0), int(z0), int(x1), int(z1)))
    return out


def forbidden(settlement):
    """{(x, z): why} a worker may not stand on in one settlement, from sources independent of the generator."""
    why = {}

    def mark(cells, w):
        for c in cells:
            why.setdefault(c, w)
    plan = json.loads((ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)).read_text(encoding="utf-8"))
    for lot in plan.get("lots") or []:
        mark(rect(lot["rect"]), "lot %s" % lot["id"])
    for an in plan.get("anchors") or []:
        mark(rect(an["rect"]), "anchor %s" % an["id"])
    for lamp in plan.get("lamps") or []:
        mark(rect((lamp["at"][0], lamp["at"][2], lamp["at"][0], lamp["at"][2]), 1), "lamp")
    rec = json.loads((ROOT / "derived" / "towns" / ("%s_placement.json" % settlement)).read_text(encoding="utf-8"))
    for b in rec["buildings"]:
        mark(rect(b["footprint"], 1), "building %s" % b["id"])
    for q in DOC["placements"]:
        if q.get("settlement") != settlement:
            continue
        if q.get("kind") == "earthwork":
            mark(write_columns(q.get("commands") or [], non_air=False), "earthwork %s" % q["id"])
        elif q.get("size") and q.get("position"):
            w, d = q["size"][0], q["size"][2]
            if q.get("rotation") in ("clockwise_90", "counterclockwise_90"):
                w, d = d, w
            x, z = q["position"]["x"], q["position"]["z"]
            mark(rect((x, z, x + w - 1, z + d - 1), 1), "building %s" % q["id"])
    f = DRESSING / ("%s.mcfunction" % settlement)
    dressed = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8")).get("towns") or {}
    if settlement in dressed:
        if not f.is_file():
            pytest.skip("NOT_EXECUTED: %s is not built (the dressing's blocks cannot be checked)" % f)
        mark(write_columns(f.read_text(encoding="utf-8").splitlines()), "dressing")
    return why


def street_y(settlement):
    plan = json.loads((ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)).read_text(encoding="utf-8"))
    out = {}
    for st in (plan.get("streets") or {}).values():
        for z, y, xa, xb in st.get("cells") or []:
            for x in range(xa, xb + 1):
                out[(x, z)] = int(y)
    return out


NUMS = r"(-?\d+(?:\.\d+)?)"


def stand_positions(fns, wid):
    """Every (x, y, z) the shipped pack puts worker `wid` at: its spawn, its stored route, every tp in its step."""
    out = []
    m = re.search(r'x:"%s",y:%s,z:"%s"' % (NUMS, NUMS, NUMS), "\n".join(fns["w/%s/spawn" % wid]))
    out.append(tuple(float(v) for v in m.groups()))
    route = fns.get("w/%s/route" % wid)
    if route:
        for m in re.finditer(r'\{x:"%s",y:"%s",z:"%s"' % (NUMS, NUMS, NUMS), route[0]):
            out.append(tuple(float(v) for v in m.groups()))
    for l in fns["w/%s/step" % wid]:
        m = re.search(r"tag=cobblers\.amb\.%s\] run tp @s %s %s %s" % (re.escape(wid), NUMS, NUMS, NUMS), l)
        if m:
            out.append(tuple(float(v) for v in m.groups()))
    return out


def data_cells(w, step=0.05):
    """The cells a worker's data says it uses: a route's polyline sampled finely, a station, a blink's spots."""
    if w["job"] == "carry":
        cells = set()
        pts = [(x + 0.5, z + 0.5) for x, z in w["route"]]
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            n = max(1, int(math.dist((ax, az), (bx, bz)) / step))
            for i in range(n + 1):
                t = i / n
                cells.add((math.floor(ax + (bx - ax) * t), math.floor(az + (bz - az) * t)))
        return cells
    if w["job"] == "work":
        return {tuple(w["at"])}
    return {tuple(s["at"]) for s in w["spots"]}


@pytest.fixture(scope="module")
def water():
    p = ROOT / "derived" / "water_shape" / "changed.npy"
    if not p.is_file():
        pytest.skip("NOT_EXECUTED: derived/water_shape/changed.npy is absent")
    import numpy as np
    return np.load(p)


# ------------------------------------------------------------------------------------------------ site rules

# Without it a worker could stand in a house, on a lot a house is coming to, on a lamp, inside a dressing piece or an
# earthwork's blocks, or on ground the pending water export will change (the owner, 2026-09-28).
# (The hop cells are included: every tp in the step. The rangers' Growlithe hopped into anchor rimpost_overlook until
# 2026-09-28.)
@pytest.mark.parametrize("wid", list(WORKERS))
def test_every_cell_a_worker_stands_on_is_free_by_the_plan(wid, water):
    fns = pack()
    w = WORKERS[wid]
    why = forbidden(w["settlement"])
    cells = {(math.floor(x), math.floor(z)) for x, _y, z in stand_positions(fns, wid)} | data_cells(w)
    bad = sorted((c, why[c]) for c in cells if c in why)
    assert not bad, bad[:5]
    m = int(RULES["water_changed_margin"])
    assert m == 8
    ox, oz = WORLD["grid"]["origin_x"], WORLD["grid"]["origin_z"]
    wet = [c for c in cells if water[c[1] - oz - m:c[1] - oz + m + 1, c[0] - ox - m:c[0] - ox + m + 1].any()]
    assert not wet, "within %d of a column the water export changes: %s" % (m, sorted(wet)[:5])


# The check above is only as good as its map: without this, an empty or partial recomputation (a source file read
# wrongly) would pass every worker.
def test_the_recomputed_site_map_marks_every_kind_of_forbidden_cell():
    why = forbidden("gym7_town")
    kinds = {v.split()[0] for v in why.values()}
    assert kinds >= {"lot", "anchor", "lamp", "building", "dressing"}, kinds
    earth = write_columns([c for q in DOC["placements"] if q.get("settlement") == "gym7_town"
                           and q.get("kind") == "earthwork" for c in q.get("commands") or []], non_air=False)
    assert earth and earth <= set(why)                  # (the lights' columns lie under other marks, which win)
    plan = json.loads((ROOT / "derived" / "towns" / "gym7_town_plan.json").read_text(encoding="utf-8"))
    x0, z0, _x1, _z1 = plan["lots"][0]["rect"]
    assert why[(x0, z0)].startswith(("lot", "building"))


# Without it a carrier would climb or drop two blocks between neighbouring points: a jump no walk makes.
@pytest.mark.parametrize("wid", [w for w in WORKERS if WORKERS[w]["job"] == "carry"])
def test_a_route_never_steps_more_than_one_block(wid):
    fns = pack()
    pts = stand_positions(fns, wid)[1:]
    route = [p for p in pts]
    assert len(route) >= 2
    steps = [abs(b[1] - a[1]) for a, b in zip(route, route[1:])]
    assert max(steps) <= 1, max(steps)


# Without it a worker stands a block in the air, or buried, wherever the paved street and the heightmap differ.
@pytest.mark.slow
def test_every_worker_stands_one_above_the_heightmap_or_its_street():
    fns = pack()
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("NOT_EXECUTED: COBBLERS_SOURCE_ROOT is not set: the canonical heightmap is outside the repo")
    import ground as G
    g = G.Ground(root)
    bad = []
    for wid, w in WORKERS.items():
        assert not (DOC["settlements"].get(w["settlement"]) or {}).get("ground"), "a settlement off the heightmap"
        sy = street_y(w["settlement"])
        for x, y, z in stand_positions(fns, wid):
            if y != int(y):
                continue                                   # a hop in the air, 0.35 above its station
            c = (math.floor(x), math.floor(z))
            want = (sy[c] if c in sy else int(round(float(g.heights[c[1] - g.oz, c[0] - g.ox])))) + 1
            if int(y) != want:
                bad.append((wid, c, int(y), want))
    assert not bad, bad[:8]


# ------------------------------------------------------------------------------------------------ the tool refuses

class FlatSite:
    def __init__(self, rise_at_x=None, rise=0):
        self.rise_at_x, self.rise = rise_at_x, rise

    def y(self, x, z):
        return 65 + (self.rise if self.rise_at_x is not None and x >= self.rise_at_x else 0)

    def blocked(self, x, z):
        return None


def carrier(route):
    return {"id": "syn", "settlement": "synthetic", "species": "machop", "job": "carry", "route": route,
            "carry": "minecraft:stone", "interact": "A test worker."}


# Without it a route over a two-block ledge would be built, and the carrier would teleport up and down it.
def test_a_route_with_a_two_block_step_is_refused_and_one_block_is_not():
    rules = dict(RULES, step_blocks=1.0)
    ambient.plan_worker(carrier([[0, 0], [4, 0]]), FlatSite(rise_at_x=2, rise=1), rules)
    with pytest.raises(ambient.AmbientError, match="steps 2 blocks"):
        ambient.plan_worker(carrier([[0, 0], [4, 0]]), FlatSite(rise_at_x=2, rise=2), rules)


# Without it a worker authored onto a house lot would be placed where the house goes.
def test_a_worker_on_a_house_lot_is_refused():
    plan = json.loads((ROOT / "derived" / "towns" / "gym1_town_plan.json").read_text(encoding="utf-8"))
    x0, z0, x1, z1 = plan["lots"][0]["rect"]
    at = [(x0 + x1) // 2, (z0 + z1) // 2]
    dressing = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))
    site = ambient.Site("gym1_town", lambda x, z: 140, DOC, dressing, None, RULES)
    w = {"id": "syn_lot", "settlement": "gym1_town", "species": "machop", "job": "work", "at": at,
         "face": [at[0] + 1, at[1]], "effect": {"particle": "minecraft:crit"}, "interact": "A test worker."}
    with pytest.raises(ambient.AmbientError, match="lot"):
        ambient.plan_worker(w, site, RULES)


# Without it two workers with one id would share one tag: each keeper would kill the other's Pokemon as a duplicate.
def test_a_duplicate_worker_id_is_refused(tmp_path, monkeypatch):
    import ground as G

    class Flat:
        def __init__(self, *a, **k):
            pass

        def __call__(self, x, z):
            return 100

    w = dict(WORKERS["tableland_sandshrew_sifter"])
    doc = dict(DATA, workers=[w, dict(w)])
    p = tmp_path / "ambient.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(ambient, "DATA", p)
    monkeypatch.setattr(ambient, "WATER_CHANGED", tmp_path / "absent.npy")
    monkeypatch.setattr(G, "Ground", Flat)
    with pytest.raises(ambient.AmbientError, match="duplicate"):
        ambient.plan()


# ------------------------------------------------------------------------------------------------ the pack's shape

# Without it a worker is spawned by a plain spawnpokemonat line, which does nothing after a restart until a /reload
# (EXP-046), or spawned and not claimed at once, and the despawner takes it within a minute.
def test_every_spawn_goes_through_the_macro_and_is_claimed_in_the_same_function():
    fns = pack()
    for name, lines in fns.items():
        for l in lines:
            if "spawnpokemonat" in l and not l.lstrip().startswith("#"):
                assert l.startswith("$spawnpokemonat ") and name == "spawn_at", (name, l)
    callers = [n for n, lines in fns.items() if any("function %s/spawn_at " % F in l for l in lines)]
    assert sorted(callers) == sorted("w/%s/spawn" % w for w in WORKERS)
    for n in callers:
        lines = [l for l in fns[n] if l and not l.startswith("#")]
        i = next(k for k, l in enumerate(lines) if "/spawn_at " in l)
        wid = n.split("/")[1]
        claim = [l for l in lines[i + 1:] if l.endswith("run function %s/w/%s/claim" % (F, wid))]
        assert len(claim) == 1 and "tag=!cobblers.amb" in claim[0] and "nbt={NoAI:1b}" in claim[0], n
        c = fns["w/%s/claim" % wid]
        assert "tag @s add cobblers.amb.%s" % wid in c and any("PersistenceRequired:1b" in l for l in c)


# Without it a generated function could hold a command the server refuses or silently drops (a fill over the limit, a
# write into a chunk nothing loaded).
def test_every_ambient_function_passes_the_function_limits():
    fns = pack()
    bad = {n: function_limits.check_lines(lines, n) for n, lines in fns.items()}
    assert not {n: b for n, b in bad.items() if b}


# Without it a worker's `clear` could erase blocks outside its own track, or run where its chunks are not loaded (a
# fill into an unloaded chunk does nothing), or be released by the station's own forceload removal.
@pytest.mark.parametrize("wid", [w for w in WORKERS if WORKERS[w].get("clear")])
def test_the_tread_clears_only_the_workers_own_cells_and_loads_its_own_chunks(wid):
    fns = pack()
    lines = fns["w/%s/tread" % wid]
    own = {}
    for x, y, z in stand_positions(fns, wid):
        if y == int(y):
            own[(math.floor(x), math.floor(z))] = int(y)
    fills = [l for l in lines if l.startswith("fill ")]
    assert fills
    for l in fills:
        t = l.split()
        x0, y0, z0, x1, y1, z1 = (int(v) for v in t[1:7])
        assert (x0, z0) == (x1, z1) and (x0, z0) in own, l
        assert (y0, y1) == (own[(x0, z0)], own[(x0, z0)] + 1), l
        assert t[7] == "minecraft:air" and t[8] == "replace" and t[9] in WORKERS[wid]["clear"], l
    assert {(int(l.split()[1]), int(l.split()[3])) for l in fills} == set(own), "a cell of its track left untrodden"
    assert not any(re.match(r"#\s*chunks-loaded-by:", l) for l in lines)
    assert function_limits.unloaded_writes(lines) == []
    first_fill = next(i for i, l in enumerate(lines) if l.startswith("fill "))
    assert any(l.startswith("forceload add") for l in lines[:first_fill])
    # its own function: nothing that runs every tick or every keep calls it
    for n, other in fns.items():
        if n != "w/%s/tread" % wid:
            assert not any("/tread" in l for l in other), n


def r16c():
    if not ambient.PLAN.is_file():
        pytest.skip("NOT_EXECUTED: derived/ambient/plan.json is absent (python tools/ambient.py build)")
    import reapply
    steps = [s for s in reapply.steps() if s[0] == "R16C"]
    assert len(steps) == 1
    return reapply, steps[0][2]


# Without it an export erases every worker (they are entities) and nothing puts them back, or the packs land in the
# global folder every world loads (the live one included).
def test_reapply_installs_the_pack_world_local_and_r16c_places_and_checks_every_worker():
    reapply, actions = r16c()
    assert "cobblers_ambient" in reapply.SERVER_PACKS and "cobblers_ambient" in reapply.WORLD_LOCAL
    assert "cobblers_ambient" not in reapply.EXCLUDED
    assert actions[-1] == ("check", "ambient")
    places = [v for k, v in actions if k == "fn" and v.endswith("/place")]
    assert places == ["%s/w/%s/place" % (F, w) for w in WORKERS for _ in (0, 1)]
    for wid in WORKERS:
        i = actions.index(("fn", "%s/w/%s/place" % (F, wid)))
        before = [a for a in actions[:i] if a[0] == "cmd" and a[1].startswith("forceload add")]
        assert before, wid
        # the tread (if any) runs before the station is force-loaded and placed, never after
        if WORKERS[wid].get("clear"):
            t = actions.index(("fn", "%s/w/%s/tread" % (F, wid)))
            fl = max(k for k, a in enumerate(actions[:i]) if a[0] == "cmd" and a[1].startswith("forceload add"))
            assert t < fl < i
        else:
            assert ("fn", "%s/w/%s/tread" % (F, wid)) not in actions


# Without it the pack could place a block that a spawn condition names, and decide encounters where it stands.
def test_the_pack_places_no_block_and_the_tread_writes_only_air():
    fns = pack()
    for n, lines in fns.items():
        for l in lines:
            s = l.lstrip("$")
            assert not re.match(r"(execute .* run )?setblock\b", s), (n, l)
            assert not re.search(r"summon minecraft:(block_display|falling_block)", s), (n, l)
            m = XZ.match(s)
            if m:
                assert m.group(8) == "minecraft:air" and m.group(8) not in SPAWN_BLOCKS, (n, l)
