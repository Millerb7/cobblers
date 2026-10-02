"""The Seaward Drift (tools/sea_drift.py) against its independent audit (tools/sea_drift_audit.py).

The audit replays the generated pack over a world made from the heightmap alone and checks rules the data states.
Clean on the pack as built is necessary and proves little on its own, so every other test here MUTATES THE GENERATOR
(CLAUDE.md, "How to prove an audit is independent"): data/sea_drift.json is left untouched, one function of the
generator is changed, the pack is rebuilt into a temporary folder, and the audit must catch it. A mutation of the data
would move the expectation with the output and prove nothing.

Three of the pool's species (Binacle, Clauncher, Dragonair) are in no other table, so the audit judges their positions
against the Cobblemon jar (COBBLERS_SERVER_ROOT). Where the jar cannot be read, the audit says so as a problem; these
tests set those three lines aside BY NAME and assert everything else, so a run without the jar still tests the build.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sea_drift as SD            # noqa: E402
import sea_drift_audit as SA      # noqa: E402

NO_JAR = "COBBLERS_SERVER_ROOT is unset: cannot judge its position"


@pytest.fixture(scope="module")
def ground():
    import ground as G
    from terrain import TerrainUnavailable
    try:
        return G.load()
    except TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])


def build(tmp_path, monkeypatch):
    out = tmp_path / "cobblers_sea_drift"
    monkeypatch.setattr(SD, "OUT", out)
    m = SD.model()
    SD.write(m)
    return m, out


def audit(out):
    res = SA.audit(pack=out)
    res["problems"] = [p for p in res["problems"] if NO_JAR not in p]
    return res


def problems(out):
    return audit(out)["problems"]


def test_the_audit_is_clean_on_the_pack_as_built(ground, tmp_path, monkeypatch):
    m, out = build(tmp_path, monkeypatch)
    assert not m.problems
    res = audit(out)
    assert not res["problems"], res["problems"][:5]
    assert res["cover_min_measured"] >= res["cover_required"] == 4
    assert res["walk_nodes"] > 1000 and res["dark_floor_cells"] == 0 and res["leaks"] == 0
    assert [b["wall_holes"] + b["roof_holes"] for b in res["buildings"]] == [0, 0]
    assert all(b["named"] for b in res["buildings"]) and res["tower_wall_holes"] == 0 and len(res["lamp"]) == 2


def test_the_road_is_one_straight_leg_between_the_owners_mouth_and_the_isle(ground):
    """The owner, 2026-10-02: "a straight shot to the island for sure". Both ends on z1795, the owner's point (1455 113
    1795) inside the gatehouse, the trip at the cited 8 blocks a second well under the first line's three minutes."""
    m = SD.model()
    (ax, az), (bx, bz) = SD.route(m.spec)
    assert az == bz == 1795 and {z for _x, z, _d in m.cells} == {1795}
    gx0, gz0, gx1, gz1 = m.spec["gatehouse"]["box"]
    assert gx0 < 1455 < gx1 and gz0 < 1795 < gz1 and m.P[[x for x, _z, _d in m.cells].index(1455)] == 113
    assert SD.trip_seconds(m) == len(m.cells) / 8.0 < 1420 / 8.0
    assert m.P[m.s_top] == m.spec["island"]["pad_y"] + 1


def test_the_records_in_the_shared_files_are_the_models(ground):
    """records --write was run after the last change to the model: a stale habitat block would sit in the wrong rock."""
    m = SD.model()
    habs, rew, pool = SD.records(m)
    hdoc = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))
    rdoc = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
    sdoc = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    assert [b for b in hdoc["blocks"] if b["id"].startswith(SD.HABITAT_PREFIX)] == habs
    assert [r for r in rdoc["rewards"] if r["id"].startswith(SD.REWARD_PREFIX)] == rew
    assert [h for h in sdoc["habitats"] if h["id"] == pool["habitat"]["id"]] == [pool["habitat"]]
    assert [e for e in sdoc["entries"] if e.get("scope") == pool["habitat"]["id"]] == pool["entries"]


def test_the_audit_catches_a_drift_built_with_too_little_cover(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(SD, "cover_blocks", lambda spec: 3)
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("water:") for p in problems(out))


def test_the_audit_catches_a_drift_with_no_lanterns(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(SD, "HANG", "minecraft:air")
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("light:") for p in problems(out))


def test_the_audit_catches_steps_without_stairs(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(SD, "stair", lambda block, facing: "minecraft:stone")
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("walk:") for p in problems(out))


def test_the_audit_catches_an_ore_that_is_a_spawn_condition(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(SD, "deep", lambda m, ore, y: "minecraft:coal_ore")
    _m, out = build(tmp_path, monkeypatch)
    ps = problems(out)
    assert any(p.startswith("blocks: minecraft:coal_ore is a spawn condition") for p in ps)
    assert any("is not an ore the data lists" in p for p in ps)


def test_the_audit_catches_a_shell_that_leaves_natural_ground_beside_the_drift(ground, tmp_path, monkeypatch):
    real = SD.shell_cells
    monkeypatch.setattr(SD, "shell_cells", lambda m: real(m) & ~SD.dilate(m.env, 1))
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("sealed:") for p in problems(out))


def test_the_rail_line_runs_stop_to_stop_with_power(ground, tmp_path, monkeypatch):
    """The owner, 2026-10-02: the rails must work for a player who builds a minecart."""
    m, out = build(tmp_path, monkeypatch)
    res = audit(out)
    assert not [p for p in res["problems"] if p.split(":")[0] in ("rails", "power", "stops", "boost", "straight")]
    assert res["rail_line_length"] == res["rails"] == len(m.line) == len(m.cells)
    assert res["rail_boosted"] == len(m.levers) and res["max_unboosted_run"] <= res["boost_limit"]
    assert res["rail_kinds"]["minecraft:rail"] == 0 and res["rail_line_off_axis"] == 0


def _skip_nth(monkeypatch, name, n, swap=None):
    """Wrap one of the generator's writers so its n-th call writes nothing (or `swap(block)`)."""
    real = getattr(SD, name)
    calls = []

    def wrapped(m, p, *rest):
        calls.append(p)
        if len(calls) == n:
            if swap is None:
                return None
            return real(m, p, swap(*rest))
        return real(m, p, *rest)
    monkeypatch.setattr(SD, name, wrapped)


def test_the_audit_catches_a_powered_rail_whose_lever_is_dropped(ground, tmp_path, monkeypatch):
    _skip_nth(monkeypatch, "write_power", 120)
    _m, out = build(tmp_path, monkeypatch)
    ps = problems(out)
    assert sum(1 for p in ps if p.startswith("power:") and "no power source" in p) == 1


def test_the_audit_catches_a_gap_in_the_line(ground, tmp_path, monkeypatch):
    _skip_nth(monkeypatch, "write_rail", 700)
    _m, out = build(tmp_path, monkeypatch)
    ps = problems(out)
    assert any(p.startswith("rails:") and "breaks" in p for p in ps)


def test_the_audit_catches_a_bend_in_the_line(ground, tmp_path, monkeypatch):
    """The generator made to lay a jog: the line steps one block aside on a flat stretch and back, with four curves.
    Joined and powered, so only the straightness rules can catch it."""
    real = SD.line_cells

    def jog(m):
        c = real(m)
        a = next(s for s in range(m.s_p + 40, len(c) - 60)
                 if len({c[t][1] for t in range(s - 1, s + 22)}) == 1 and not set(range(s - 1, s + 22)) & set(m.stairs))
        b = a + 20
        y, z = c[a][1], c[a][2]
        return (c[:a] + [(c[a - 1][0], y, z + 1)] + [(x, yy, zz + 1) for x, yy, zz in c[a:b]]
                + [(c[b][0], y, z + 1)] + c[b:])
    monkeypatch.setattr(SD, "line_cells", jog)
    monkeypatch.setattr(SD, "refuse_turn", lambda cell, shape: None)
    _m, out = build(tmp_path, monkeypatch)
    ps = problems(out)
    assert any(p.startswith("straight:") and "leave its axis" in p for p in ps)
    assert sum(1 for p in ps if p.startswith("rails:") and "turns" in p) == 4


def test_the_audit_catches_boosts_too_far_apart(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(SD, "boost_every", lambda spec: 40)
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("boost:") and "without a powered one" in p for p in problems(out))


def test_the_audit_catches_a_detector_beside_a_stop(ground, tmp_path, monkeypatch):
    """The station rail parts the stop from the line; a detector there would power the stop under an arriving cart."""
    real = SD.write_rail
    monkeypatch.setattr(SD, "write_rail", lambda m, p, b: real(m, p, b.replace("activator_rail", "detector_rail")))
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("stops:") and "detector" in p for p in problems(out))


def test_the_audit_catches_a_plain_rail_on_the_line(ground, tmp_path, monkeypatch):
    """minecraft:rail is a spawn condition and, with the line straight, whitelisted nowhere here."""
    real = SD.write_rail
    monkeypatch.setattr(SD, "write_rail", lambda m, p, b: real(m, p, b.replace("detector_rail", "rail")))
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("blocks: minecraft:rail is a spawn condition") for p in problems(out))


def test_the_audit_catches_a_lamp_that_is_a_spawn_condition(ground, tmp_path, monkeypatch):
    """The owner, 2026-10-02: the house you come out is a lighthouse. Its lamp must give light and decide no spawn."""
    real = SD.tower

    def tower(m, *a):
        real(m, *a)
        for p in m.lamp:
            m.surf[p] = "minecraft:redstone_lamp[lit=false]"
    monkeypatch.setattr(SD, "tower", tower)
    _m, out = build(tmp_path, monkeypatch)
    ps = problems(out)
    assert any(p.startswith("lighthouse: no light-emitting block") for p in ps)
    assert any(p.startswith("blocks: minecraft:redstone_lamp is a spawn condition") for p in ps)


def test_the_audit_catches_a_lantern_room_walled_up(ground, tmp_path, monkeypatch):
    real = SD.tower

    def tower(m, lh, pad, tdoor):
        real(m, lh, pad, tdoor)
        tx0, tz0, _tx1, _tz1 = lh["tower"]["box"]
        m.surf[(tx0 + 3, lh["tower"]["lantern_room_feet"], tz0)] = "minecraft:stone_bricks"
    monkeypatch.setattr(SD, "tower", tower)
    _m, out = build(tmp_path, monkeypatch)
    ps = problems(out)
    assert any(p.startswith("lighthouse: the lamp") and "hidden from the north" in p for p in ps)


def test_the_audit_catches_a_gatehouse_without_its_sign(ground, tmp_path, monkeypatch):
    real = SD.surface

    def surface(m):
        real(m)
        for p in m.gate_signs:
            del m.surf[p]
    monkeypatch.setattr(SD, "surface", surface)
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("gatehouse: no sign on Foothill Gate") for p in problems(out))


def test_the_audit_catches_a_buffer_left_out_of_the_halls_wall(ground, tmp_path, monkeypatch):
    real = SD.surface

    def surface(m):
        real(m)
        st = m.stops[1]["buffer"]
        m.surf[tuple(st)] = "minecraft:air"
    monkeypatch.setattr(SD, "surface", surface)
    _m, out = build(tmp_path, monkeypatch)
    ps = problems(out)
    assert any(p.startswith("gatehouse: the keeper's hall's wall is open") for p in ps)
    assert any(p.startswith("stops:") and "not a solid block" in p for p in ps)


def test_the_staging_cleanup_restores_the_first_drift_and_never_touches_the_new(ground):
    """The one-off cleanup of staging-2026-10-01: every cell the first drift opened that the new build does not write
    goes back to rock (under the heightmap's ground) or water and air (over it), and no cell the new build writes is in
    it. Built from the first drift's own generator and data at its commit."""
    m = SD.model()
    lines, counts, old = SD.cleanup(m)
    cleaned = SD.written_cells(lines["restore"])
    new = SD.written_cells([ln for p in SD.PASSES for ln in m.lines[p]])
    assert cleaned and not set(cleaned) & set(new)
    g, sea = m.g, m.sea
    oenv = {(int(i + old.X0), int(j + old.Y0), int(k + old.Z0)) for i, k, j in SD.np.argwhere(old.env)}
    left = [p for p in oenv if p not in new and p not in cleaned and p[1] <= g(p[0], p[2])]
    assert not left, left[:3]
    for (x, y, z), b in cleaned.items():
        gy = g(x, z)
        if y > gy:
            assert b == ("minecraft:water" if y <= sea else "minecraft:air"), ((x, y, z), b)
        else:
            assert SD.bid_of(b) not in ("minecraft:air", "minecraft:water"), ((x, y, z), b)
    # the first isle and its ten Habitat Blocks' rock are gone: nothing of it is left solid over the seabed (the cells
    # the first build itself opened again, its well and hall, are air already and need nothing)
    olds = SD.written_cells([ln for lns in old.lines.values() for ln in lns])
    oisle = [p for p in old.isle_cells if p not in new and SD.bid_of(olds[p]) != "minecraft:air"]
    assert oisle and all((x, y, z) in cleaned for (x, y, z) in oisle)
    assert counts["isle_and_buildings_to_water"] > 0 and counts["void_to_rock"] > 0


def test_the_isles_pool_has_no_species_the_owner_is_tired_of():
    sdoc = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    pool = json.loads((ROOT / "data" / "sea_drift.json").read_text(encoding="utf-8"))["waters"]["pool"]
    species = {e["species"] for e in sdoc["entries"] if e.get("scope") == pool}
    assert species and not species & set(SA.NOT_WANTED)


def test_no_spawn_policy_exception_is_left_for_the_drift():
    """The first line's 12 curves needed minecraft:rail whitelisted for the drift; a straight line needs nothing."""
    pol = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    assert not [w for w in pol["whitelist"] if "sea_drift" in (w.get("scope") or "")]


def test_relic_islands_shape_is_unchanged_by_the_new_parameters():
    """tools/islet.py's island_top took radius, crown and grid parameters for the new isle; its defaults are Relic
    Island's and must give the same island they always did."""
    import numpy as np
    import islet as I
    a, ra = I.island_top(None, 62)
    b, rb = I.island_top(None, 62, seed=I.SEED, radius=I.RADIUS, top=I.TOP, half=I.RADIUS)
    assert np.array_equal(np.nan_to_num(a, nan=-1), np.nan_to_num(b, nan=-1)) and np.array_equal(ra, rb)
    assert a.shape == (2 * I.RADIUS + 1, 2 * I.RADIUS + 1)
    assert int(np.nanmax(a)) == 70 and int((~np.isnan(a)).sum()) == 2628
