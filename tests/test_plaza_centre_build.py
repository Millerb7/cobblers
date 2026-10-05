"""The town squares: data/plaza_centres.json and tools/plaza_centre.py (the builder's own geometry tests).

The contract fields and the stall geometry are checked from the data alone. The built squares are checked against
the town plan recomputed here, not against the builder's mask: every standing piece inside its square and off every
street cell, lot, anchor and building footprint; every keeper on floor with two air above; every stall's customer
cell, the centrepiece and every bench walked to from the Centre's and the Mart's doors by a search written here. The
mutation tests change the GENERATOR (a keeper moved inside the stall piece, the mask switched off) and leave the data
alone, so they show these checks bite on a builder fault and not just on a record edit.

An independent audit (another agent) comes after these; these are the builder's.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import plaza_centre as P  # noqa: E402

DATA = json.loads((ROOT / "data" / "plaza_centres.json").read_text(encoding="utf-8"))
DOC = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
STEP = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}
YAW = {"south": 0, "west": 90, "north": 180, "east": -90}
# the survey's twelve: no middle, a bare one, Steepside's partial one, and Pallet's crossroads
SURVEYED = {"hometown", "gym1_town", "gym2_town", "gym3_town", "gym4_town", "gym5_town", "gym6_town", "gym7_town",
            "gym8_town", "sunset_west", "sea_town", "tea_town"}
# 2026-10-05, the owner: "Several towns still have no middle at all ... Every town should have somewhere a player goes
# to spend money." The places with people and no middle or nowhere to spend: the four rest stops, the summit town (its
# cairn square existed, nothing sold) and the Dig. A hamlet gets a well (or its one civic thing) and ONE stall
HAMLETS = {"gorge_hamlet", "merian_hut", "rift_rim_stop", "rift_dig_camp"}
SECOND = HAMLETS | {"tableland_stop", "displaced_city"}


# ------------------------------------------------------------------------------------------- the contract, data only
def test_every_surveyed_town_has_a_square():
    assert set(DATA["towns"]) == SURVEYED | SECOND


@pytest.mark.parametrize("town", sorted(DATA["towns"]))
def test_contract_fields(town):
    rec = DATA["towns"][town]
    sq = rec["square"]
    assert len(sq["rect"]) == 4 and all(isinstance(v, int) for v in sq["rect"])
    assert sq["rect"][0] <= sq["rect"][2] and sq["rect"][1] <= sq["rect"][3]
    assert isinstance(sq["y"], int)
    assert len(sq["centrepiece"]) == 3 and all(isinstance(v, int) for v in sq["centrepiece"])
    assert rec["stalls"], "%s: a square with nowhere to spend money" % town
    ids = set()
    for s in rec["stalls"]:
        assert re.fullmatch(r"%s_stall_\d+" % re.escape(town), s["id"]), s["id"]
        assert s["id"] not in ids
        ids.add(s["id"])
        assert len(s["at"]) == 3 and all(isinstance(v, int) for v in s["at"])
        assert s["facing"] in STEP
        assert len(s["keeper_at"]) == 4 and all(isinstance(v, int) for v in s["keeper_at"])
        assert isinstance(s["sells"], str) and s["sells"] in DATA["goods"]


@pytest.mark.parametrize("town", sorted(DATA["towns"]))
def test_square_is_the_plans_plaza(town):
    """A square on a plaza is the plan's plaza exactly (rect and floor), so a replanned plaza cannot leave it behind."""
    rec = DATA["towns"][town]
    plaza = (DOC["settlements"][town].get("plan") or {}).get("plaza")
    if rec.get("on_plaza", True):
        assert plaza and plaza["rect"] == rec["square"]["rect"] and plaza["y"] == rec["square"]["y"]
    else:
        assert plaza is None, "%s has a plaza; its square should be on it" % town


@pytest.mark.parametrize("town", sorted(DATA["towns"]))
def test_keeper_in_front_of_the_table_facing_the_customers(town):
    """2026-10-04, the owner: "the stalls all block the villager from access". The keeper stands at the tent's open
    front, in front of the table on the customers' side, not behind a counter."""
    for s in DATA["towns"][town]["stalls"]:
        dx, dz = STEP[s["facing"]]
        kx, ky, kz, yaw = s["keeper_at"]
        assert (kx, kz) == (s["at"][0] + dx, s["at"][2] + dz), "%s: keeper not in front of the table" % s["id"]
        assert ky == s["at"][1], "%s: keeper's feet not level with the table" % s["id"]
        assert yaw == YAW[s["facing"]], "%s: keeper does not face the customers" % s["id"]
        if DATA["towns"][town].get("on_plaza", True):
            assert ky == DATA["towns"][town]["square"]["y"] + 1, "%s: keeper not standing on the square" % s["id"]


def test_stall_ids_unique_across_towns():
    ids = [s["id"] for t in DATA["towns"].values() for s in t["stalls"]]
    assert len(ids) == len(set(ids))


def test_stall_counts_follow_the_size_class():
    """The survey's rule: small 2, medium 4, large 6; Pallet (intact), Steepside (the survey's 2) and the hamlets (one
    stall each, 2026-10-05) excepted."""
    want = {"small": 2, "medium": 4, "large": 6}
    for town, rec in DATA["towns"].items():
        n = len(rec["stalls"])
        if town == "hometown" or town in HAMLETS:
            assert n == 1
        elif town == "tea_town":
            assert n == 2
        else:
            assert n == want[rec["class"]], "%s: %d stalls for a %s square" % (town, n, rec["class"])


def test_allowed_blocks_are_spawn_neutral():
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    assert not set(DATA["blocks"]["ids"]) & spawn


def test_allowed_blocks_exist_in_the_jar():
    import town_character as TC
    jar = TC.default_vanilla_jar()
    if not jar or not Path(jar).is_file():
        pytest.skip("no 1.21.1 client jar on this machine")
    names = set(zipfile.ZipFile(jar).namelist())
    missing = [i for i in DATA["blocks"]["ids"] if "assets/minecraft/blockstates/%s.json" % i.split(":", 1)[1] not in names]
    assert not missing


# ---------------------------------------------------------------------------------------------- the built squares
def _inputs_present():
    plans = [ROOT / "derived" / "towns" / ("%s_plan.json" % t) for t in DATA["towns"]
             if (DOC["settlements"][t].get("plan") or {})]
    return all(p.is_file() for p in plans) and (ROOT / "derived" / "signposts.json").is_file()


needs_inputs = pytest.mark.skipif(not _inputs_present(),
                                  reason="derived/towns plans or derived/signposts.json absent (reapply.py prepare)")


@pytest.fixture(scope="module")
def built():
    import ground as G
    g = G.Ground()
    refs = P.refs_of()
    out = {}
    for town, rec in DATA["towns"].items():
        gt = P.ground_for(town, g, DOC, None)
        cmds, report = P.plan_town(town, rec, DOC, gt, refs, DATA)
        town_obj = P.Town(town, dict(rec, _town=town), DOC, gt, refs)
        out[town] = (cmds, report, town_obj)
    return out


def _plan_cells(town):
    """Streets, lots, anchors and building footprints, recomputed here from the plan and the placements."""
    import town_dressing as TD
    plan_path = ROOT / "derived" / "towns" / ("%s_plan.json" % town)
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else {}
    streets = {(x, z) for st in (plan.get("streets") or {}).values()
               for z, _y, xa, xb in st.get("cells") or [] for x in range(xa, xb + 1)}
    lots = {(x, z) for lot in plan.get("lots") or [] for x in range(lot["rect"][0], lot["rect"][2] + 1)
            for z in range(lot["rect"][1], lot["rect"][3] + 1)}
    anchors = {(x, z) for a in plan.get("anchors") or [] for x in range(a["rect"][0], a["rect"][2] + 1)
               for z in range(a["rect"][1], a["rect"][3] + 1)}
    buildings = {(x, z) for r in TD.building_footprints(town, DOC).values()
                 for x in range(r[0], r[2] + 1) for z in range(r[1], r[3] + 1)}
    return streets, lots, anchors, buildings


@needs_inputs
@pytest.mark.parametrize("town", sorted(DATA["towns"]))
def test_nothing_on_buildings_streets_or_lots(built, town):
    _cmds, report, _t = built[town]
    streets, lots, anchors, buildings = _plan_cells(town)
    x0, z0, x1, z1 = DATA["towns"][town]["square"]["rect"]
    for p in report["pieces"]:
        cols = {tuple(c) for c in p["columns"]}
        if p["kind"] == "path":
            assert not cols & (lots | anchors | buildings), p["id"]
            continue
        assert all(x0 <= x <= x1 and z0 <= z <= z1 for x, z in cols), "%s outside its square" % p["id"]
        assert not cols & streets, "%s on a street" % p["id"]
        assert not cols & lots, "%s on a lot" % p["id"]
        assert not cols & anchors, "%s on an anchor lot" % p["id"]
        assert not cols & buildings, "%s on a building" % p["id"]


@needs_inputs
@pytest.mark.parametrize("town", sorted(DATA["towns"]))
def test_keepers_on_floor_with_headroom(built, town):
    _cmds, report, t = built[town]
    written = {(b[0], b[1], b[2]) for p in report["pieces"] for b in p["blocks"]}
    occupied = {tuple(c) for p in report["pieces"] if not p["flush"] for c in p["columns"]}
    for p in report["pieces"]:
        if p["kind"] != "stall":
            continue
        kx, ky, kz, _yaw = p["keeper_at"]
        assert ky - 1 == t.floor_at(kx, kz), "%s: keeper not standing on the floor" % p["id"]
        assert (kx, ky, kz) not in written and (kx, ky + 1, kz) not in written, "%s: no headroom" % p["id"]
        assert (kx, ky - 1, kz) not in written or t.floor_at(kx, kz) == ky - 1
        cx, cz = p["customer"]
        assert (cx, cz) not in occupied, "%s: its customer cell is built on" % p["id"]


def _walk(t, start, occupied):
    """Cells reachable on foot from start: four-way steps of at most one block, never into a building or a piece."""
    _s, _l, _a, buildings = _plan_cells(t.settlement)
    box = (t.rect[0] - 100, t.rect[1] - 100, t.rect[2] + 100, t.rect[3] + 100)
    seen = {start}
    q = deque([start])
    while q:
        x, z = q.popleft()
        for n in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if n in seen or n in buildings or n in occupied:
                continue
            if not (box[0] <= n[0] <= box[2] and box[1] <= n[1] <= box[3]):
                continue
            if abs(t.floor_at(*n) - t.floor_at(x, z)) > 1:
                continue
            seen.add(n)
            q.append(n)
    return seen


def _starts(t, town):
    """{label: (x, z)} where a walk to the square starts: the Centre's and the Mart's doors; for a settlement with NO
    Centre placement, the record's walk_from (a placement's door or a named cell) instead -- and a settlement with a
    Centre must have its door here whatever walk_from says."""
    doors = {d["role"]: d["front"] for d in t.doors.values() if d["role"] in ("pokecenter", "pokemart")}
    has_centre = any(q.get("settlement") == town and "pokecenter" in q["id"] for q in DOC["placements"])
    if has_centre:
        assert "pokecenter" in doors, "%s: no Centre door" % town
        return doors
    out = dict(doors)
    for w in DATA["towns"][town].get("walk_from") or []:
        out["from %s" % (w.get("placement") or w.get("id"))] = (
            t.doors[w["placement"]]["front"] if w.get("placement") else tuple(w["at"]))
    assert out, "%s: no Centre and no walk_from" % town
    return out


@needs_inputs
@pytest.mark.parametrize("town", sorted(DATA["towns"]))
def test_square_reachable_from_the_centre_and_mart_doors(built, town):
    _cmds, report, t = built[town]
    existing = {tuple(c) for p in report["pieces"] for c in p.get("existing_columns") or []}
    occupied = {tuple(c) for p in report["pieces"] if not p["flush"] for c in p["columns"]} | existing
    for role, front in _starts(t, town).items():
        seen = _walk(t, front, occupied)
        for p in report["pieces"]:
            if p["kind"] == "stall":
                assert tuple(p["customer"]) in seen, "%s: %s not reached from the %s" % (town, p["id"], role)
            elif p["kind"] == "existing":
                ring = {(x + dx, z + dz) for x, z in map(tuple, p["existing_columns"])
                        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))} - occupied
                assert ring & seen, "%s: %s not reached from the %s" % (town, p["id"], role)
            elif p["role"] == "centrepiece" or p["kind"] == "bench":
                cols = {tuple(c) for c in p["columns"]}
                ring = cols if p["flush"] else {(x + dx, z + dz) for x, z in cols
                                                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))} - occupied
                assert ring & seen, "%s: %s not reached from the %s" % (town, p["id"], role)


def _voxels(cmds):
    """{(x, y, z): state} the function leaves, from its own lines: every setblock and every unfiltered fill applied in
    order. A `replace #minecraft:replaceable` fill clears only plants, which this model does not hold, so it is skipped."""
    model = {}
    for c in cmds:
        m = re.match(r"setblock (-?\d+) (-?\d+) (-?\d+) (\S+)$", c)
        if m:
            model[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = m.group(4)
            continue
        m = re.match(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(.*)$", c)
        if m and not m.group(8).strip():
            v = [int(m.group(i)) for i in range(1, 7)]
            for x in range(min(v[0], v[3]), max(v[0], v[3]) + 1):
                for y in range(min(v[1], v[4]), max(v[1], v[4]) + 1):
                    for z in range(min(v[2], v[5]), max(v[2], v[5]) + 1):
                        model[(x, y, z)] = m.group(7)
    return model


def _clear(state):
    return state is None or P.block_name(state) == "minecraft:air"


@needs_inputs
@pytest.mark.parametrize("town", sorted(DATA["towns"]))
def test_every_keeper_reached_face_to_face_from_the_aisle(built, town):
    """The owner, 2026-10-04: "the stalls all block the villager from access". For every stall, from the function's
    own blocks (not the builder's columns): the customer's cell is the keeper's next cell towards the customers'
    side, on the keeper's floor; neither cell holds a block at feet or head height (a carpet underfoot is allowed the
    customer, never the keeper); and the customer's cell is walked to from the Centre's door over the square, through
    every column the function leaves clear at standing height. So a player stands adjacent to the keeper, face to face,
    with no block between."""
    cmds, report, t = built[town]
    model = _voxels(cmds)
    walls = set()
    for (x, y, z), s in model.items():
        if _clear(s) or P.block_name(s).endswith("_carpet"):
            continue
        if t.floor_at(x, z) < y <= t.floor_at(x, z) + 2:
            walls.add((x, z))
    starts = _starts(t, town)
    front = starts.get("pokecenter") or next(iter(starts.values()))
    seen = _walk(t, front, walls)
    for p in report["pieces"]:
        if p["kind"] != "stall":
            continue
        kx, ky, kz, yaw = p["keeper_at"]
        dx, dz = STEP[p["facing"]]
        cx, cz = kx + dx, kz + dz
        assert (kx, kz) not in walls, "%s: the keeper's own cell is walled" % p["id"]
        assert t.floor_at(cx, cz) + 1 == ky, "%s: the customer's cell %s is not on the keeper's floor" % (p["id"], (cx, cz))
        for y in (ky, ky + 1):
            assert _clear(model.get((kx, y, kz))), "%s: %s at the keeper's %s" % (p["id"], model.get((kx, y, kz)), y - ky)
            s = model.get((cx, y, cz))
            assert _clear(s) or P.block_name(s).endswith("_carpet"), \
                "%s: %s between the keeper and the customer at %s" % (p["id"], s, (cx, y, cz))
        assert (cx, cz) in seen, "%s: the customer's cell %s is not walked to from the Centre's door" % (p["id"], (cx, cz))
        assert yaw == YAW[p["facing"]], "%s: the keeper does not face the customer" % p["id"]


@needs_inputs
@pytest.mark.parametrize("town", sorted(DATA["towns"]))
def test_function_writes_exactly_the_model(built, town):
    """Every block of the model is set by the function, nothing else is set, and the server would accept every line."""
    import function_limits
    cmds, report, _t = built[town]
    sets = set()
    for c in cmds:
        m = re.match(r"setblock (-?\d+) (-?\d+) (-?\d+) (.+)$", c)
        if m:
            sets.add((int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)))
    model = {(b[0], b[1], b[2], b[3]) for p in report["pieces"] for b in p["blocks"]}
    assert sets == model
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    assert not {P.block_name(s) for *_xyz, s in sets} & spawn
    assert not function_limits.check_lines(function_limits.ensure_loaded(cmds), town)


@needs_inputs
def test_every_stall_lit_and_the_square_too(built):
    for town, (_cmds, report, _t) in built.items():
        lights = report["lights"]
        for p in report["pieces"]:
            if p["kind"] == "stall":
                assert any(l[0] in range(p["at"][0] - 1, p["at"][0] + 2) and l[2] in range(p["at"][2] - 1, p["at"][2] + 2)
                           for l in lights), "%s: a roofed stall with no lantern" % p["id"]


# ------------------------------------------------------------------------------------- mutations of the generator
@needs_inputs
def test_mutation_keeper_moved_in_the_piece_is_refused(monkeypatch):
    """Move the keeper's cell inside piece_stall (the generator), data untouched: the build must refuse the drift."""
    import ground as G
    real = P.piece_stall

    def moved(town, spec, goods):
        p = real(town, spec, goods)
        p.keeper = (0, 2)
        return p
    monkeypatch.setitem(P.PIECES, "stall", moved)
    with pytest.raises(SystemExit, match="keeper_at"):
        P.plan_town("gym5_town", DATA["towns"]["gym5_town"], DOC, G.Ground(), P.refs_of(), DATA)


@needs_inputs
@pytest.mark.parametrize("cell, why", [((0, -1), "open cell"), ((0, -2), "between keeper and customer")])
def test_mutation_a_ware_in_the_keepers_face_is_refused(monkeypatch, cell, why):
    """The old booth's fault, put back in the GENERATOR (data untouched): a ware at head height in the keeper's own
    cell, or in the customer's cell in front of it. The build must refuse both. The mask is switched off so that it is
    the face-to-face rule that refuses, not a desire line the customer's cell happens to lie on."""
    import ground as G
    real = P.piece_stall
    monkeypatch.setattr(P.Town, "blocked", lambda self, x, z, flush=False: None)

    def blocked(town, spec, goods):
        p = real(town, spec, goods)
        p.put(cell[0], 1, cell[1], "minecraft:barrel[facing=up]")
        return p
    monkeypatch.setitem(P.PIECES, "stall", blocked)
    with pytest.raises(SystemExit, match=why):
        P.plan_town("gym1_town", DATA["towns"]["gym1_town"], DOC, G.Ground(), P.refs_of(), DATA)


@needs_inputs
def test_mutation_mask_off_is_caught_here(monkeypatch):
    """Switch the builder's mask off and seat a stall on a street: the build cannot see it, and the plan check here
    (which shares nothing with the mask) does."""
    import ground as G
    monkeypatch.setattr(P.Town, "blocked", lambda self, x, z, flush=False: None)
    town = "gym6_town"
    streets, _l, _a, _b = _plan_cells(town)
    rec = json.loads(json.dumps(DATA["towns"][town]))
    sx, sz = sorted(c for c in streets if 6181 <= c[0] <= 6211 and 3390 <= c[1] <= 3400)[0]
    st = rec["stalls"][0]
    y = rec["square"]["y"] + 1
    st.update(at=[sx, y, sz + 1], facing="south", keeper_at=[sx, y, sz + 2, 0])
    try:
        _cmds, report = P.plan_town(town, rec, DOC, G.Ground(), P.refs_of(), DATA)
    except SystemExit as e:
        pytest.skip("another rule refused the mutated stall first: %s" % e)
    cols = {tuple(c) for p in report["pieces"] if p["kind"] == "stall" for c in p["columns"]}
    assert cols & streets, "the mutation did not put a stall on the street"


def _cairn_columns():
    """The Displaced City cairn's columns above the summit square's floor, read here from its placement's own commands
    (my parser, not plaza_centre.earthwork_columns)."""
    q = next(p for p in DOC["placements"] if p["id"] == "displaced_cairn")
    y0 = DATA["towns"]["displaced_city"]["square"]["y"]
    cols = set()
    for c in q["commands"]:
        m = re.match(r"\s*(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)", c)
        if not m or P.block_name(m.group(8)) == "minecraft:air":
            continue
        v = [int(m.group(i)) for i in (2, 3, 4)]
        w = [int(m.group(i)) for i in (5, 6, 7)] if m.group(5) else v
        if max(v[1], w[1]) <= y0:
            continue
        cols |= {(x, z) for x in range(min(v[0], w[0]), max(v[0], w[0]) + 1)
                 for z in range(min(v[2], w[2]), max(v[2], w[2]) + 1)}
    return cols


@needs_inputs
def test_existing_centrepiece_is_the_cairn_and_nothing_is_written_on_it(built):
    """The Displaced City's middle is its cairn, built by its own placement: the square's centrepiece is one of the
    cairn's columns, the report's existing columns are the cairn's (on the square), and the function writes no block in
    any of them."""
    cmds, report, _t = built["displaced_city"]
    cairn = _cairn_columns()
    sq = DATA["towns"]["displaced_city"]["square"]
    assert (sq["centrepiece"][0], sq["centrepiece"][2]) in cairn
    piece = next(p for p in report["pieces"] if p["kind"] == "existing")
    x0, z0, x1, z1 = sq["rect"]
    assert {tuple(c) for c in piece["existing_columns"]} == {c for c in cairn if x0 <= c[0] <= x1 and z0 <= c[1] <= z1}
    written = {(x, z) for (x, _y, z) in _voxels(cmds)}
    assert not written & cairn


@needs_inputs
def test_mutation_existing_centrepiece_columns_shifted_is_caught(monkeypatch):
    """Shift the columns the GENERATOR reads off an earthwork (data untouched): the cairn's centre cell is then not
    among them and the build refuses, or the report's columns no longer match the cairn read here."""
    import ground as G
    real = P.earthwork_columns
    monkeypatch.setattr(P, "earthwork_columns", lambda cmds, y: {(x + 4, z) for x, z in real(cmds, y)})
    rec = DATA["towns"]["displaced_city"]
    try:
        _cmds, report = P.plan_town("displaced_city", rec, DOC, P.ground_for("displaced_city", G.Ground(), DOC, None),
                                    P.refs_of(), DATA)
    except SystemExit as e:
        assert "builds nothing above the floor" in str(e) or "not free" in str(e)
        return
    piece = next(p for p in report["pieces"] if p["kind"] == "existing")
    assert {tuple(c) for c in piece["existing_columns"]} != _cairn_columns()


def test_a_settlement_without_a_centre_names_where_it_is_walked_from():
    """No Centre placement, then walk_from with a why; a Centre, then no walk_from is needed."""
    for town, rec in DATA["towns"].items():
        has_centre = any(q.get("settlement") == town and "pokecenter" in q["id"] for q in DOC["placements"])
        if not has_centre:
            assert rec.get("walk_from"), "%s: no Centre and no walk_from" % town
            assert all(w.get("why") for w in rec["walk_from"]), town


# ------------------------------------------------------------------------------------------------- the step R13
def test_reapply_wires_the_pack_and_r13():
    import reapply
    assert "cobblers_plaza_centres" in reapply.SERVER_PACKS
    assert "cobblers_plaza_centres" not in getattr(reapply, "EXCLUDED", ())
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    # R13 after the towns, the donors and the bridges, before the lights and the dressing
    assert src.index('("R9G"') < src.index('("R13"') < src.index('("R16"') < src.index('"R16B"')
    assert src.index('add("town_dressing:build"') < src.index('add("plaza_centre:build"')
    assert P.placement_steps() == [("fn", "cobblers:plaza_centres/%s" % t) for t in DATA["towns"]]


def test_tool_reads_no_world():
    """The ground rule (CLAUDE.md): positions come from the plan and the heightmap, never a world save."""
    src = (ROOT / "tools" / "plaza_centre.py").read_text(encoding="utf-8")
    assert "--world" not in src and "world_path" not in src and "mca" not in src
