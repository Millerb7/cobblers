"""The Overgrown Temple (`jungle`, dungeon 2 in data/dungeons.json): the full-length test dungeon of unit DG-JUNGLE.

The author's own tests (the independent review is another agent's): the record builds, walks (the room kit's walk
check, entry to exit and back through every room), is 1,200-1,600 blocks walked, has every room type the owner named
in an order that paces, writes its params to the wave-2 params contract, names only species in the Cobblemon 1.8.0
jar, and keeps its rip by the Night Shift's on dry ground. One GENERATOR mutation: the glow-vine op the tall rooms
are lit by, turned off, leaves the sanctum dark and the walk check says so.

Not covered: anything in a running Minecraft, and the fight and puzzle kinds' behaviour (DG-FIGHTS, DG-PUZZLES).
"""
from __future__ import annotations

import copy
import json
import re
import sys
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_kinds as K  # noqa: E402
import dungeon_rooms as R  # noqa: E402

DOC = D.load()
JG = next(d for d in DOC["dungeons"] if d["id"] == "jungle")
SLOT = next(s for s in D.slots(DOC) if s["dungeon"]["id"] == "jungle")
FIGHTS = {"stand", "gauntlet", "ambush", "nest", "miniboss", "habitat", "boss_arena"}
OWNER_NAMED = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room"}


@pytest.fixture(scope="module")
def built():
    R._BUILT.clear()
    return R.slot_build(DOC, JG, SLOT)


def path_len(b):
    """Shortest walk across one built room, door in to door out, over the walk check's own reachable cells (one block
    a step, a parkour jump counted as its length)."""
    r, g = b.room, b.grid
    jumps = R.flags_of(r["kind"])["jumps"]
    sx = r["xa"] + 3 if r["kind"] == "entry_room" else r["ix0"]
    a = g.local(sx, r["floor_in"], r["z_in"])
    reach = G.walk(g, [a], jumps=jumps, cls=g.cls())
    gx = g.local(r["ix1"] if r["door_out"] else r["ix1"] - 1, 0, 0)[0]
    gz = g.local(0, 0, r["z_out"])[2]
    dist, q = {a: 0}, deque([a])
    while q:
        c = q.popleft()
        if c[0] == gx and (not r["door_out"] or abs(c[2] - gz) <= 1):
            return dist[c]
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for n in range(1, (G.JUMP_FLAT_MAX if jumps else 1) + 1):
                for dy in (0, 1, -1):
                    t = (c[0] + dx * n, c[1] + dy, c[2] + dz * n)
                    if t in reach and t not in dist:
                        dist[t] = dist[c] + n
                        q.append(t)
    return None


# ------------------------------------------------------------------------------------------------- the record


def test_the_jungle_is_dungeon_two_a_test_dungeon_with_its_own_short_and_no_clock_of_its_own():
    ids = [d["id"] for d in DOC["dungeons"]]
    assert ids.index("jungle") == 1, ids                  # the brief: the Night Shift first, the jungle second
    assert JG["theme"] == "jungle" and JG["test"] is True and JG["test_why"]
    assert JG["gate_flag"] is None and "spine" not in JG
    assert JG["short"] not in [d["short"] for d in DOC["dungeons"] if d is not JG]
    # filled at integration with DG-NS's formula; problems() refuses a clock under the derived one
    assert set(JG["clock_s_by_band"]) == {str(b["band"]) for b in DOC["engine"]["bands"]}


def test_the_engine_and_the_room_kit_find_no_problem_with_it():
    assert R.problems(DOC, JG) == []
    assert [p for p in D.problems(DOC) if "jungle" in p or "jg" in p.split()] == []


def test_it_walks_entry_to_exit_and_back_through_every_room(built):
    assert R.walk_problems(DOC, JG, SLOT) == []
    for b in built:
        r, g = b.room, b.grid
        if not r["door_out"]:
            continue
        cls = g.cls()
        jumps = R.flags_of(r["kind"])["jumps"]
        a = g.local(r["ix0"] if r["kind"] != "entry_room" else r["xa"] + 3, r["floor_in"], r["z_in"])
        z = g.local(r["ix1"], r["floor_out"], r["z_out"])
        assert z in G.walk(g, [a], jumps=jumps, cls=cls), r["id"]
        assert a in G.walk(g, [z], jumps=jumps, cls=cls), (r["id"], "back")


def test_it_is_full_length_1200_to_1600_walked_with_wide_rooms_and_short_connectors(built):
    walked = sum(path_len(b) + 2 for b in built)          # + the two door columns each room shares
    assert 1200 <= walked <= 1600, walked
    assert 1200 <= R.points(DOC, SLOT)["length"] <= walked
    for r in JG["rooms"]:
        if R.flags_of(r["kind"])["connector"]:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
        elif r["kind"] not in ("entry_room", "exit_room", "safe_room", "vault", "collapse_bridge"):
            assert 30 <= r["width"] <= 60, r["id"]
    assert max(r["height"] for r in JG["rooms"]) >= 20, "a canopy hall"


def test_every_room_type_the_owner_named_is_there_and_three_of_ours():
    kinds = [r["kind"] for r in JG["rooms"]]
    assert OWNER_NAMED <= set(kinds), OWNER_NAMED - set(kinds)
    ours = set(kinds) & OURS
    assert any(r["kind"] == "safe_room" and r.get("params", {}).get("healer") for r in JG["rooms"])
    assert len(ours - {"ambush"}) >= 3, ours
    assert kinds[-2:] == ["boss_arena", "exit_room"] and kinds[0] == "entry_room"


def test_the_pacing_no_two_fights_meet_the_heal_is_two_thirds_in_the_orchard_before_the_hard_stretch(built):
    kinds = [r["kind"] for r in JG["rooms"]]
    for a, b in zip(kinds, kinds[1:]):
        assert not (a in FIGHTS and b in FIGHTS), (a, b)
    walk = [path_len(b) + 2 for b in built]
    total = sum(walk)
    i_safe = kinds.index("safe_room")
    assert 0.55 <= sum(walk[:i_safe]) / total <= 0.75, sum(walk[:i_safe]) / total
    i_res = kinds.index("resources")
    hard = [i for i, k in enumerate(kinds) if k in ("habitat", "miniboss", "boss_arena")]
    assert all(i_res < i for i in hard)
    assert i_res < kinds.index("gauntlet")


def test_the_temple_is_felt_dressed_stone_and_the_jungle_dense_in_the_connectors(built):
    by = {b.room["id"]: b for b in built}
    names = lambda b: {G.base(op[2]) for op in b.ops if op[0] in ("fill", "set")}  # noqa: E731
    for rid in ("colonnade", "sanctum", "altar", "glyph_door"):
        assert {"minecraft:mossy_stone_bricks", "minecraft:chiseled_stone_bricks"} <= names(by[rid]), rid
    for r in JG["rooms"]:
        if r["kind"] == "drift":
            assert "minecraft:jungle_log" in names(by[r["id"]]) and "minecraft:vine" in names(by[r["id"]]), r["id"]
    assert "minecraft:cave_vines" in names(by["sanctum"]), "the canopy hall is lit by glow berries"


# ------------------------------------------------------------------------------------------------- the params contract


def rooms_of(*kinds):
    return [r for r in JG["rooms"] if r["kind"] in kinds]


def test_the_stands_and_the_ambush_follow_the_members_by_band_and_the_triggers_are_one_per_trainer():
    for r in rooms_of("stand", "gauntlet", "ambush"):
        assert r["gate"] == "cleared"
        assert DF.stand_problems(DOC, r) == [], r["id"]
    for r in rooms_of("gauntlet", "ambush"):
        tr = r["params"]["triggers"]
        assert len(tr) == len(r["params"]["trainers"]) and tr == sorted(tr) and 0 < tr[0] and tr[-1] < 1


def test_the_wild_rooms_and_the_set_pieces_carry_the_contracts_fields_within_the_band_caps():
    bands = {str(b["band"]): b for b in D.bands(DOC)}
    for r in rooms_of("nest"):
        p = r["params"]
        assert p["species"] and set(p["count_by_band"]) == set(bands)
        lo, hi = p["level_spread"]
        assert 0 <= lo <= hi        # offsets BELOW the band's upper cap, as the nest kind reads them (tools/dungeon_fights.py)
    for r in rooms_of("miniboss"):
        p = r["params"]
        assert set(p["species_by_band"]) == set(bands) and p["level_offset"] <= 0 and p.get("catchable") is False
    for r in rooms_of("habitat"):
        p = r["params"]
        assert p["fight_only"] is True and set(p["level_by_band"]) == set(bands)
        for k, lv in p["level_by_band"].items():
            assert lv <= max(bands[k]["caps"]), (k, lv)            # never above the band's upper cap
        assert 95 <= p["level_by_band"]["6"] <= 100
    for r in rooms_of("puzzle"):
        p = r["params"]
        assert p["variant"] in ("levers", "sequence", "plates") and 3 <= p.get("size", p.get("length", p.get("count", 0))) <= 6
        assert p["penalty_s"] > 0 and r["gate"] == "cleared" and r["height"] >= 6
    for r in rooms_of("vault"):
        p = r["params"]
        assert r.get("gate", "open") == "open" and 1 <= p["chests"] <= 8 and p["clock_cost_s"] > 0
        assert set(p["loot_by_band"]) == set(bands)
        assert r["length"] >= 4 * p["chests"] + 12
    for r in rooms_of("safe_room"):
        assert r["params"]["healer"] is True


def test_the_boss_has_a_crew_per_stage_per_band_the_ace_last_and_the_same_ace_in_every_stage():
    bo = JG["boss"]
    assert bo["name"] != DOC["dungeons"][0]["boss"]["name"]
    for b in D.bands(DOC):
        crews = bo["teams"][str(b["band"])]
        assert len(crews) == len(bo["stage_level_offsets"])
        aces = {c[-1] for c in crews}
        assert len(aces) == 1, (b["band"], aces)
        assert all(1 <= len(c) <= 6 for c in crews)


# ------------------------------------------------------------------------------------------------- species


def all_species():
    out = set()
    for r in JG["rooms"]:
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for team in t["team_by_band"].values():
                out |= set(team)
        out |= set(p.get("species", [])) if isinstance(p.get("species"), list) else ({p["species"]} if "species" in p else set())
        out |= set(p.get("species_by_band", {}).values())
    for crews in JG["boss"]["teams"].values():
        for c in crews:
            out |= set(c)
    return out


@pytest.fixture(scope="module")
def jar_species():
    import battle_sim as B
    try:
        sp, _m, _c = B.load_pack(B.find_jar())
    except B.SimError:
        pytest.skip("no Cobblemon 1.8 jar on this machine")
    return sp


def test_every_species_is_in_the_cobblemon_jar(jar_species):
    import battle_sim as B
    missing = sorted(s for s in all_species() if B.key(s) not in jar_species)
    assert missing == []


def test_the_habitat_is_a_mythical_no_other_data_file_uses_and_not_an_ultra_beast(jar_species):
    import battle_sim as B
    (hab,) = rooms_of("habitat")
    sp = hab["params"]["species"]
    labels = set(jar_species[B.key(sp)].get("labels", []))
    assert labels & {"legendary", "mythical"} and "ultra_beast" not in labels, labels
    users = [p.name for p in (ROOT / "data").rglob("*.json")
             if p.name != "dungeons.json" and re.search(r"\b%s\b" % sp, p.read_text(encoding="utf-8"), re.I)]
    assert users == []


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_stands_by_the_night_shifts_on_the_trail_clear_of_the_old_mine_and_the_other_rips():
    import route1_old_mine as M
    f = JG["rip"]["frame"]
    ns = DOC["dungeons"][0]["rip"]["frame"]
    cx, cz = (f["x0"] + f["x1"]) / 2, f["z"]
    assert ((cx - (ns["x0"] + ns["x1"]) / 2) ** 2 + (cz - ns["z"]) ** 2) ** 0.5 <= 60
    assert f["x0"] > max(M.TRAIL[-1][0], max(x for x, _z in M.TRAIL)) + 4, "east of the old mine's footprint"
    for x in range(f["x0"], f["x1"] + 1):
        assert M.rise(x, f["z"]) == 0 and M.rise(x, f["z"] + 1) == 0
    for d in DOC["dungeons"]:
        if d is JG:
            continue
        o = d["rip"]["frame"]
        assert f["x1"] + 3 < o["x0"] or o["x1"] + 3 < f["x0"] or abs(f["z"] - o["z"]) > 3, d["id"]
    assert JG["rip"]["click"] == [cx, f["y"], f["z"] + 1]


def test_the_rip_stands_on_the_heightmaps_ground_and_above_the_sea():
    try:
        import ground as GR
        import terrain as T
        g = GR.load()
    except Exception as e:                                   # no heightmap on this machine
        pytest.skip("no canonical heightmap: %s" % e)
    f = JG["rip"]["frame"]
    sea = T.sea_level(g.world)
    for x in range(f["x0"], f["x1"] + 1):
        for z in (f["z"], f["z"] + 1):
            assert g(x, z) + 1 == f["y"] and g(x, z) > sea, (x, z, g(x, z))
    ox, oy, oz, _yaw = JG["rip"]["outside"]
    assert g(int(ox), int(oz)) + 1 == oy


# ------------------------------------------------------------------------------------------------- generator mutation


def test_mutating_the_glow_vines_off_leaves_the_tall_rooms_dark_and_the_walk_check_says_so(monkeypatch):
    R._BUILT.clear()
    monkeypatch.setitem(R.DRESS, "glow_vines", (lambda ctx, spec: None, "light"))
    bad = R.walk_problems(DOC, JG, SLOT)
    R._BUILT.clear()
    assert any("sanctum" in p and "no light" in p for p in bad), bad[:3]


def test_the_build_writes_one_shell_function_per_room_inside_the_chain_budget(built):
    files = D.build(DOC)
    shell = [k for k in files if "/shells/s%d/" % SLOT["g"] in k]
    assert len(shell) == len(JG["rooms"])
    assert R.chain_problems(DOC, JG, SLOT) == []
    assert R.total_blocks(DOC, SLOT) < 1.2e6
