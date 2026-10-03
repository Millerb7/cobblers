"""tools/relic_underground.py, its audit tools/relic_underground_audit.py, the capped surface in tools/deep_city.py and the
R9RU wiring in tools/reapply.py.

Written by the session that wired the generator and wrote the audit, so the independent half of the proof is CLAUDE.md's
mutation standard ("How to prove an audit is independent"): every tamper case below changes the GENERATOR's code (a
function replaced in-process) and leaves data/relic_underground.json and data/deep_city.json alone. A record-side
mutation moves the expectation and the output together and proves nothing.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); a skip names it. NOT covered, and it needs a running server: that
the fills land, that the zone turns a passless player back, and every probe in RELIC_UNDERGROUND.md section 9.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import relic_underground as R  # noqa: E402
import relic_underground_audit as A  # noqa: E402

SPEC = json.loads((ROOT / "data" / "relic_underground.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ no heightmap needed

def test_paint_seed_is_paint_maps_default():
    src = (ROOT / "tools" / "paint_maps.py").read_text(encoding="utf-8")
    m = re.search(r'"--seed", type=int, default=(\d+)', src)
    assert m and int(m.group(1)) == R.PAINT_SEED


def test_r9ru_runs_after_the_city_and_before_the_habitat_blocks():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    i_dc, i_ru, i_e = src.index('("R9DC"'), src.index('("R9RU"'), src.index('("R9E"')
    assert i_dc < i_ru < i_e
    import reapply
    assert "cobblers_relic_underground" in reapply.SERVER_PACKS
    assert "cobblers_relic_underground" in reapply.WORLD_LOCAL       # the zone advancement acts on its own
    assert '"relic_underground.py", *src, "build"' in src and '"relic_underground_audit.py"' in src


def test_the_zone_geometry_is_consistent():
    z = SPEC["zone"]

    def inbox(x, zz):
        return any(b[0] <= x <= b[2] and b[1] <= zz <= b[3] for b in z["boxes"])
    kb = z["knock"]["box"]
    assert not any(inbox(x, zz) for x in range(kb[0], kb[3] + 1) for zz in range(kb[2], kb[5] + 1))
    tx, ty, tz = z["turn_back"]["at"]
    assert not inbox(int(tx), int(tz)) and ty > z["y"][1]
    assert "cobblers:flag/rift_crisis_resolved" not in z["pass"]["threshold_advancements"]
    air, _floor = A.expected_air(SPEC)
    # the gallery reaches through the passage's north wall: the fault found 2026-10-02
    assert (3390, 6, 3304) in air and (3390, 7, 3305) in air and (3390, 6, 3303) in air
    out = [c for c in air if c[0] < z["threshold_x"] and not inbox(c[0], c[2])]
    assert not out


def test_deep_city_verify_no_longer_needs_the_ring():
    src = (ROOT / "tools" / "deep_city.py").read_text(encoding="utf-8")
    need = re.search(r"need = \{([^}]*)\}", src).group(1)
    assert "relic ring" not in need and "relic seal" in need


def test_r9ru_runs_after_the_pit_it_cuts_the_stair_into():
    # the audit's EARLIER exemption (cobblers_deep's replace fills) is only sound while R9B runs before R9RU
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert src.index('("R9B"') < src.index('("R9DC"') < src.index('("R9RU"')
    assert set(A.EARLIER) == {"cobblers_deep"}
    # the undo leaves the Rift skin's cells (UNDO_LEAVES, relic_underground.skin_cells) only while R1 runs before R9RU
    assert src.index('[("R1"') < src.index('("R9RU"')
    assert set(A.UNDO_LEAVES) == {"cobblers_rift"}


def test_the_hq_way_down_stays_in_the_reserved_boxes():
    hp = R.hq_plan(SPEC)
    boxes = R.reserved_boxes(SPEC)
    assert set(boxes) == {"hq_basement", "hq_secure_shaft", "hq_shaft_head", "hq_room_north_partition"}
    out = [c for c in hp["cells"] if c not in hp["undo"] and not R.in_boxes(c, boxes.values())]
    assert not out, out[:3]
    # nothing at or over the HQ room's floor (the door's plates came off 2026-10-02); the stair's head opens the floor
    room_y = SPEC["geometry"]["hq"]["room"]["floor_y"]
    # except the one wall that closes the storey-0 room off from the next HQ section (2026-10-02): without it a player
    # walks in at that section's street door and never meets the guard. It lies on the room's north boundary, not in it.
    ix0, iz0, ix1, iz1 = SPEC["geometry"]["hq"]["room"]["interior"]
    over = {c for c in hp["cells"] if c[1] > room_y}
    seal = [d for d in SPEC["geometry"]["hq"]["dressing"] if d.get("seals_room")]
    assert len(seal) == 1
    f = seal[0]["fill"]
    assert over == {(x, y, z) for x in range(f[0], f[3] + 1) for y in range(f[1], f[4] + 1) for z in range(f[2], f[5] + 1)}
    assert f[2] == f[5] == iz0 - 1 and f[0] <= ix0 + 2 and f[3] >= ix1 + 1
    assert "plates" not in hp and "plates" not in SPEC["geometry"]["hq"]["front_door"]
    assert tuple(SPEC["zone"]["hq_access"]["shaft_head"]) in hp["air"]
    # the knock box is the records room's air, on its floor
    kb = SPEC["zone"]["knock"]["box"]
    for x in range(kb[0], kb[3] + 1):
        for z in range(kb[2], kb[5] + 1):
            assert hp["cells"][(x, kb[1] - 1, z)] != R.AIR
            assert all(hp["cells"][(x, y, z)] == R.AIR for y in range(kb[1], kb[4] + 1))
    # the audit's own re-derivation agrees with the generator on the air, cell for cell
    pair, _f = A.expected_air(SPEC)
    assert A.expected_hq(SPEC, pair)[0] == hp["air"]


def test_the_spawn_decision_is_recorded_and_made_real():
    # the owner, 2026-10-02: nothing spawns in Hoopa's hall. Spawn-free zones, the gyms' mechanism; no Habitat Block
    sd = SPEC["composition"]["spawn_decision"]
    assert sd["status"].startswith("DECIDED")
    ss = json.loads((ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))
    have = {z["id"]: z["box"] for z in ss["spawn_free_zones"]}
    assert sd["zones"] and all(have.get(k) == v for k, v in sd["zones"].items())
    import compile_spawns as CS
    for b in sd["zones"].values():
        assert (b[0], b[2], b[1], b[3]) in CS.spawn_free_zones()          # what compile_spawns and the suppression read
    assert SPEC["zone"]["hq_access"]["status"].startswith("BUILT")
    hb = (ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8")
    assert "relic_underground" not in hb and "hoopa" not in hb.lower()


def _zone_texts(fns):
    return {k + ".mcfunction": "\n".join(v) + "\n" for k, v in fns.items()}


def test_the_guard_is_the_only_edge_and_it_is_stage_gated():
    # the audit's guard reading, against the committed dialogue and the generator's guard functions (no heightmap)
    edges, probs = A.guard_edges(SPEC, _zone_texts(R.guard_functions(SPEC)))
    assert probs == []
    got = {name: to for name, _seat, _reach, to in edges}
    hq = SPEC["geometry"]["hq"]
    assert got == {"guard": tuple(hq["guard"]["inside_landing"]), "inside_guard": tuple(hq["guard"]["front_step"])}


def test_a_guard_function_that_moves_everyone_is_refused():
    # mutate the GENERATOR's function (the data untouched): @a would carry every player through the shut door
    fns = R.guard_functions(SPEC)
    fns["hq_admit"] = [l.replace("tp @s", "tp @a") for l in fns["hq_admit"]]
    _edges, probs = A.guard_edges(SPEC, _zone_texts(fns))
    assert any("other than @s" in p for p in probs), probs


def test_r18ru_places_both_guards_after_the_settlement_npcs():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert src.index('("R17N"') < src.index('("R18RU"')
    got = R.npc_placements()
    hq = SPEC["geometry"]["hq"]
    assert [(c, xyz, cls) for c, xyz, cls, _yaw in got] == [
        ("dlg_main_relic_hq_guard", tuple(hq["guard"]["at"]), "cobblers:npc_main_relic_hq_guard"),
        ("dlg_main_relic_hq_guard_inside", tuple(hq["inside_guard"]["at"]), "cobblers:npc_main_relic_hq_guard_inside"),
        # the binder at the relic ring who releases Hoopa (geometry.release, 2026-10-03)
        ("dlg_main_relic_hall_release", tuple(SPEC["geometry"]["release"]["at"]), "cobblers:npc_main_relic_hall_binder")]


# ------------------------------------------------------------------ the heightmap

@pytest.fixture(scope="module")
def sr():
    import ground as G
    import terrain as T
    s = os.environ.get("COBBLERS_SOURCE_ROOT")
    try:
        G.Ground(s)
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)
    return s


@pytest.fixture(scope="module")
def inputs(sr):
    """What the audit checks against, computed ONCE and before any tamper: the ground, the pit, the old build, the
    city as the current generator builds it."""
    import ground as G
    import rift_deep as RD
    import relic_surface_superseded as S
    g = G.load(sr)
    m = RD.model(sr)
    X0, Z0 = m["box"][0], m["box"][1]

    def pit(x, z):
        i, j = z - Z0, x - X0
        if 0 <= i < m["mask"].shape[0] and 0 <= j < m["mask"].shape[1] and m["mask"][i, j]:
            return int(m["tread_y"][i, j])
        return None
    city = R.city_cells(sr)
    view = A._CityView(set(city), {c for c, b in city.items() if b.split("[")[0] != A.AIR})
    rm, (RX0, RZ0, _a, _b), _n = RD.region_mask("relic_area_shrine", sr)
    H, W = rm.shape
    edge = [(j + RX0, i + RZ0) for i in range(H) for j in range(W) if rm[i, j] and any(
        not (0 <= i + di < H and 0 <= j + dj < W) or not rm[i + di, j + dj]
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    return {"g": g, "pit": pit, "old": dict(S.old_write_set(sr)), "city": view, "edge": edge, "blocks": dict(city)}


_SKIN_MEMO = {}


def _skin_written():
    """The Rift skin's definite writes in the undo's box, read with the AUDIT's parser (not the generator's skin_cells)."""
    if "skin" not in _SKIN_MEMO:
        x0, z0, x1, z1 = SPEC["bounds"]["undo"]
        out = set()
        for f in (A.PACKS / "cobblers_rift" / "data").rglob("*.mcfunction"):
            for w in A.parse(f.read_text(encoding="utf-8", errors="replace").splitlines()):
                if w[7] or w[3] < x0 or w[0] > x1 or w[5] < z0 or w[2] > z1:
                    continue
                out.update(c for c in A.cells(w) if x0 <= c[0] <= x1 and z0 <= c[2] <= z1)
        _SKIN_MEMO["skin"] = out
    return _SKIN_MEMO["skin"]


def build_and_audit(sr, inputs, out, swept=None):
    """swept: (others, others_definite) from A.other_packs, the other built packs as prepare's audit sees them; without
    it only the city is swept (what every test before 2026-10-02 did, and why none saw cobblers_deep or cobblers_rift)."""
    if not R.SKIN.is_dir():
        pytest.skip("no build/datapacks/cobblers_rift: the undo leaves the Rift skin's cells and fails closed without "
                    "it (run `python tools/rift_skin.py build`)")
    R.cmd_build(argparse.Namespace(source_root=sr, out=str(out)))
    fns, order, zone = A.read_pack(out)
    if swept:
        others, definite = swept
    else:
        # the city, and the Rift skin the undo now leaves (UNDO_LEAVES): without it the audit expects those cells back
        skin = _skin_written()
        others = {"cobblers_deep_city": inputs["city"]["all"], "cobblers_rift": skin}
        definite = {"cobblers_deep_city": inputs["city"]["all"], "cobblers_rift": skin}
    probs, st = A.audit(fns, order, zone, SPEC, inputs["g"], inputs["pit"], others,
                        inputs["old"], inputs["city"], city_blocks=inputs["blocks"], others_definite=definite)
    undo = {c: A.base(w[6]) for n in order if n.startswith("undo") for w in fns[n] for c in A.cells(w)}
    left = A.cordon_check(undo, inputs["edge"], inputs["g"], inputs["city"]["all"])
    if left:
        probs.append(("cordon", "%d fence cells not cleared" % len(left)))
    return {k for k, _m in probs}, probs, st


def test_the_built_pack_is_clean(sr, inputs, tmp_path):
    kinds, probs, st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert not probs, probs
    assert st["undo_air"] > 0 and st["undo_ground"] > 0 and st["shell"] > 0
    assert st["route_from"].startswith("outside the HQ's front door")
    assert st["route_via"] == {"stair": True, "records room": True, "guard": True}
    assert st["cradle_stands_reached"] == len(A.expected_cradle(SPEC)[2]) >= 4


def test_the_city_no_longer_lays_the_hatch(sr, inputs):
    for c in SPEC["geometry"]["hq"]["hatch_undo"]["cells"]:
        assert tuple(c) not in inputs["blocks"]
    door = inputs["blocks"][tuple(SPEC["geometry"]["hq"]["front_door"]["at"])]
    assert door.startswith("minecraft:iron_door[") and "half=lower" in door and "facing=east" in door


def test_the_capped_city_writes_no_shrine_and_no_fence(sr):
    import deep_city as DC
    spec = json.loads(DC.SPEC.read_text(encoding="utf-8"))
    cv = DC.Canvas()
    DC.build_relic(cv, DC.Palette(spec), spec, sr, lambda *a, **k: None, [])
    blocks = {b.split("[")[0] for b, _ph in cv.v.values()}
    for gone in ("minecraft:tinted_glass", "legendarymonuments:distortion_stone", "minecraft:purple_stained_glass"):
        assert gone not in blocks
    assert "minecraft:reinforced_deepslate" in blocks and "minecraft:raw_gold_block" in blocks   # the seal, the dig


# ------------------------------------------------------------------ tamper the GENERATOR; the audit must bite

def test_a_gallery_one_short_of_the_passage_fails_the_route(sr, inputs, tmp_path, monkeypatch):
    # the generator's geometry stops the gallery one block short, as it did before 2026-10-02; the data is untouched
    real = R.Geo.__init__

    def short(self, spec):
        real(self, spec)
        self.gz1 -= 1
    monkeypatch.setattr(R.Geo, "__init__", short)
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert "route" in kinds, probs


def test_the_cradle_is_carved_and_the_audit_expects_it():
    # without this the cradle checks below could pass by checking nothing: the record must carve it, and the audit's own
    # derivation must name its air, its floor, four stands and the marker
    assert SPEC["geometry"]["cradle"]["carve"] is True
    air, floor, stands, marker = A.expected_cradle(SPEC)
    cx, cz = SPEC["geometry"]["cradle"]["centre"]
    assert (cx, SPEC["geometry"]["cradle"]["floor_y"] + 1, cz) in air and len(floor) > 700
    assert len(stands) >= 4 and marker == (cx, 13, cz)
    assert all(s in air and (s[0], s[1] + 1, s[2]) in air for s in stands)


@pytest.mark.parametrize("off", [1, -1])
def test_a_cradle_radius_off_by_one_is_caught(sr, inputs, tmp_path, monkeypatch, off):
    # the GENERATOR's geometry carves the cradle one block wider or narrower; data/relic_underground.json is untouched.
    # The generator's own report is silenced so the audit is what bites
    real = R.Geo.__init__

    def wrong(self, spec):
        real(self, spec)
        if self.cradle:
            self.cr += off
    monkeypatch.setattr(R.Geo, "__init__", wrong)
    monkeypatch.setattr(R, "cmd_report", lambda a: 0)
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert "carve" in kinds, probs
    word = "air cells outside" if off > 0 else "the data says are air are not"
    assert any(word in m for k, m in probs if k == "carve"), probs


def test_a_dressing_block_on_a_cradle_stand_is_caught(sr, inputs, tmp_path, monkeypatch):
    # the GENERATOR's cradle dressing stands a console on the first stand (the data untouched): a block in the air is
    # composition, which the carve check allows, so only the stand check can see the standing spot is gone
    real = R.cradle_composition

    def blocked(geo, spec):
        cells = real(geo, spec)
        st = spec["composition"]["cradle"]["stands"]
        x, z = R._at(geo.cc, st["orbit"], st["bearings"][0])
        cells[(x, geo.cfloor + 1, z)] = "minecraft:polished_blackstone"
        return cells
    monkeypatch.setattr(R, "cradle_composition", blocked)
    with pytest.raises(R.RelicError):
        R.cmd_build(argparse.Namespace(source_root=sr, out=str(tmp_path / "refused")))
    monkeypatch.setattr(R, "cmd_report", lambda a: 0)
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert "cradle" in kinds, probs
    assert any("stand" in m and "two clear" in m for k, m in probs if k == "cradle"), probs


def _tampered_hq(monkeypatch, change):
    real = R.hq_plan

    def tampered(spec):
        hp = real(spec)
        change(hp, spec)
        hp["air"] = {c for c, v in hp["cells"].items() if v == R.AIR}
        return hp
    monkeypatch.setattr(R, "hq_plan", tampered)


def test_a_resealed_shaft_head_fails_the_route(sr, inputs, tmp_path, monkeypatch):
    # the generator lays the HQ room's floor back over the stair's head (the old hatch, in effect); the data is untouched
    def reseal(hp, spec):
        y = spec["geometry"]["hq"]["room"]["floor_y"]
        for c in [c for c in hp["cells"] if c[1] == y and hp["cells"][c] == R.AIR]:
            hp["cells"][c] = "minecraft:reinforced_deepslate"
    _tampered_hq(monkeypatch, reseal)
    kinds, probs, st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert "route" in kinds and "hq" in kinds, probs
    assert st["route_via"]["stair"] is False


def test_a_plate_put_back_at_the_door_is_refused(sr, inputs, tmp_path, monkeypatch):
    # the generator lays the first build's outside plate again (the data untouched): a door anyone can open
    def plate(hp, spec):
        hp["cells"][(3444, 67, 3282)] = "minecraft:polished_blackstone_pressure_plate"
    _tampered_hq(monkeypatch, plate)
    # the generator's own report catches it and refuses to build ...
    with pytest.raises(R.RelicError):
        R.cmd_build(argparse.Namespace(source_root=sr, out=str(tmp_path / "refused")))
    # ... and with that report silenced, the audit still does: the opener, and the room reached without the guard
    monkeypatch.setattr(R, "cmd_report", lambda a: 0)
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert {"hq", "route"} <= kinds, probs
    assert any("opener beside it" in m for k, m in probs if k == "hq"), probs
    assert any("WITHOUT the guard" in m for k, m in probs if k == "route"), probs


def test_a_guard_that_moves_the_player_nowhere_fails_the_route(sr, inputs, tmp_path, monkeypatch):
    # the generator's admit teleports back onto the doorstep (the data untouched): no edge past the shut door
    real = R.guard_functions

    def outside(spec):
        fns = real(spec)
        fns["hq_admit"] = [l.replace("tp @s 3440.5 67 3282.5", "tp @s 3444.5 67 3282.5") for l in fns["hq_admit"]]
        return fns
    monkeypatch.setattr(R, "guard_functions", outside)
    kinds, probs, st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert "route" in kinds, probs
    assert st["route_via"]["stair"] is False


def test_a_records_room_short_of_the_doorway_fails(sr, inputs, tmp_path, monkeypatch):
    # the generator stops the room's air one column east of the doorway: the knock box's first column is wall
    def short(hp, spec):
        for (x, y, z), v in list(hp["cells"].items()):
            if x == 3422 and v == R.AIR:
                hp["cells"][(x, y, z)] = "minecraft:deepslate_bricks"
    _tampered_hq(monkeypatch, short)
    # the generator's own report catches this one and refuses to build ...
    with pytest.raises(R.RelicError):
        R.cmd_build(argparse.Namespace(source_root=sr, out=str(tmp_path / "refused")))
    # ... and with that report silenced, the audit still does, from its own derivation
    monkeypatch.setattr(R, "cmd_report", lambda a: 0)
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert {"route", "zone", "hq"} <= kinds, probs


def test_an_undo_that_forgets_the_city_fails(sr, inputs, tmp_path, monkeypatch):
    real = R.city_cells

    def forgetful(s):
        import inspect
        if any(f.function == "undo_plan" for f in inspect.stack()):
            return {}
        return real(s)
    monkeypatch.setattr(R, "city_cells", forgetful)
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert "undo" in kinds, probs


def test_an_undo_that_skips_the_fence_fails_the_independent_cordon_check(sr, inputs, tmp_path, monkeypatch):
    import relic_surface_superseded as S
    real = S.old_write_set

    def no_fence(s, *a, **k):
        return {c: b for c, b in real(s, *a, **k).items() if "tinted_glass" not in b and "iron_bars" not in b}
    monkeypatch.setattr(S, "old_write_set", no_fence)
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack")
    assert "cordon" in kinds and "undo" in kinds, probs


# ------------------------------------------------------------------ the other built packs, swept as prepare's audit does
# 2026-10-02: prepare's audit failed 52 shell cells against cobblers_deep (the HQ room's north partition, a wall the
# integration added over R9B's void) and 62 undo cells against cobblers_rift (the undo paving the Rift skin, R1, with
# gravel). No test here saw either: build_and_audit swept only the city. These sweep every built pack.

@pytest.fixture(scope="module")
def swept():
    need = [A.PACKS / p for p in ("cobblers_deep", "cobblers_rift", "cobblers_deep_city")]
    if not all(p.is_dir() for p in need):
        pytest.skip("needs the built cobblers_deep, cobblers_rift and cobblers_deep_city packs in build/datapacks")
    b = SPEC["bounds"]
    box = (min(b["undo"][0], b["carve_with_shell"][0]), min(b["undo"][1], b["carve_with_shell"][1]),
           max(b["undo"][2], b["carve_with_shell"][2]), max(b["undo"][3], b["carve_with_shell"][3]))
    return A.other_packs(box)


def test_the_built_pack_is_clean_against_every_built_pack(sr, inputs, swept, tmp_path):
    kinds, probs, st = build_and_audit(sr, inputs, tmp_path / "pack", swept)
    assert not probs, probs
    assert st["undo_left_to_earlier"] > 0            # the skin and the old build do share cells: the case is live
    assert st["pit_fixtures"] == 13 * 4              # the north partition, x3431-3443 y67-70, and nothing more


def test_an_undo_that_paves_the_rift_skin_fails(sr, inputs, swept, tmp_path, monkeypatch):
    # the generator mutated back to before the fix: skin_cells() leaves nothing, so the undo lays painted ground on R1's
    # cells; data untouched
    monkeypatch.setattr(R, "skin_cells", lambda box: set())
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack", swept)
    assert any(k == "undo" and "cobblers_rift" in m for k, m in probs), probs


def test_a_wall_in_the_pit_outside_the_declared_partition_fails(sr, inputs, swept, tmp_path, monkeypatch):
    # the generator lays one more solid block in R9B's void, beside the declared partition but outside its reserved
    # box (x3430): the pit-fixture ordering admits the declared wall and nothing else
    def stray(hp, spec):
        hp["cells"][(3430, 68, 3278)] = "minecraft:polished_deepslate"
    _tampered_hq(monkeypatch, stray)
    # the generator's own report refuses it ...
    with pytest.raises(R.RelicError):
        R.cmd_build(argparse.Namespace(source_root=sr, out=str(tmp_path / "refused")))
    # ... and with that report silenced, the audit's sweep still does
    monkeypatch.setattr(R, "cmd_report", lambda a: 0)
    kinds, probs, _st = build_and_audit(sr, inputs, tmp_path / "pack", swept)
    assert any(k == "shell" and "cobblers_deep" in m for k, m in probs), probs


def test_the_skin_reader_fails_closed_without_the_skin(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "SKIN", tmp_path / "absent")
    monkeypatch.setattr(R, "_MEMO", {})
    with pytest.raises(R.RelicError):
        R.skin_cells((0, 0, 1, 1))


# ------------------------------------------------------------------ tools/presence_audit.py relic, on the capped plan

def test_the_presence_relic_probe_runs_on_the_capped_plan(sr, monkeypatch):
    # 2026-10-02: relic() read derived/deep_city/plan.json's relic ring, which the capped build no longer records, and
    # crashed with KeyError 'ring'. It now takes the old ring from the superseded generator's record.
    import deep_city as DC
    import presence_audit as PA
    import relic_surface_superseded as S
    spec = json.loads(DC.SPEC.read_text(encoding="utf-8"))
    assert spec["relic_area"]["capped"]["capped"] is True
    _cv, plan, _s, _sp = DC.build(sr, None)
    assert "ring" not in plan["relic"] and "cordon" not in plan["relic"]     # the plan the old probe crashed on

    def no_plan():
        raise AssertionError("the relic probe read derived/deep_city/plan.json")
    monkeypatch.setattr(PA, "_plan", no_plan)
    monkeypatch.setattr(PA.time, "sleep", lambda s: None)
    sent = []

    def rc(cmd):
        sent.append(cmd)
        return "Test failed" if cmd.startswith("execute if block") else "Test passed"
    rows = PA.relic(rc, sr)
    rec = S.old_record(sr)
    assert [r[0] for r in rows] == ["relic", "relic", "relic"]
    assert rows[0][2] == tuple(rec["ring"]["centre"])
    assert rows[1][2][0] == rec["cordon"]["gate"][0][0] and rows[1][2][2] == rec["cordon"]["gate"][0][1]
    hall = SPEC["geometry"]["hall"]
    assert rows[2][2] == (hall["centre"][0], hall["floor_y"] + 2, hall["centre"][1])
    ring = rec["ring"]
    probe = "execute if block %d %d %d minecraft:air" % (ring["centre"][0] + ring["radius"], ring["centre"][1],
                                                         ring["centre"][2])
    assert probe in sent
