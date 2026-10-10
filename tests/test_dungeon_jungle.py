"""The Overgrown Temple (`jungle`, dungeon 2 in data/dungeons.json), as re-authored for pass 2 by unit DG2-JUNGLE.

The author's own tests (the independent review is another agent's): the record builds and walks in all four variants
(the room kit's walk check, every door of every room, both ways over the fork, the side room, the secrets with their
tricks), its required time is about 32 minutes at band 1 with every clock at most an hour (so no lockout of its own),
its rooms turn, climb, drop and double back with most of them shaped, it has every room type the owner named, a fork
(fast and dangerous / safe and long), a side room, a cracked and a balcony secret with their relics, a shortcut back
toward the entry, four distinct variants and the lights-out set piece before the boss, names only species in the
Cobblemon 1.8.0 jar, and keeps its rip by the Night Shift's on dry ground. Two GENERATOR mutations: the glow vines off
leave rooms dark, and rooms that never touch lose the shortcut; the walk and plan checks say so.

Not covered: anything in a running Minecraft, the fight and puzzle kinds' behaviour, the relics' reward (DG2-RELICS).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_audit as DA  # noqa: E402
import dungeon_clock as DC  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import dungeon_setpieces as SP  # noqa: E402

DOC = D.load()
JG = next(d for d in DOC["dungeons"] if d["id"] == "jungle")
SLOTS = [s for s in D.slots(DOC) if s["dungeon"]["id"] == "jungle"]
SLOT = SLOTS[0]
RECORDS = list(R._walk_records(JG["rooms"]))     # every room of the record, routes and the side room (no swaps)
FIGHTS = {"stand", "gauntlet", "ambush", "nest", "miniboss", "habitat", "boss_arena"}
OWNER_NAMED = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room", "setpiece"}
CONNECTORS = {"drift", "stairs"}


def kinds_in_order(rooms):
    return [r["kind"] for r in rooms]


@pytest.fixture(scope="module")
def walks():
    """{variant id: [walked rows]} over the slot of each variant (tools/dungeon_clock.py, the kit's own grids)."""
    out = {}
    for s in R.variant_slots(DOC, JG, SLOTS):
        out[R.variant_of(DOC, JG, s)["id"]] = DC.walked(DOC, JG, s)[0]
    return out


# ------------------------------------------------------------------------------------------------- the record


def test_the_jungle_is_dungeon_two_a_test_dungeon_with_its_own_short_clock_and_no_lockout_of_its_own():
    ids = [d["id"] for d in DOC["dungeons"]]
    assert ids.index("jungle") == 1, ids
    assert JG["theme"] == "jungle" and JG["test"] is True and JG["test_why"]
    assert JG["gate_flag"] is None and "spine" not in JG
    assert JG["short"] not in [d["short"] for d in DOC["dungeons"] if d is not JG]
    assert set(JG["clock_s_by_band"]) == {str(b["band"]) for b in DOC["engine"]["bands"]}
    # every band's clock is at most an hour, so D17's hour lockout applies again (the brief: drop the dungeon's own)
    assert max(JG["clock_s_by_band"].values()) <= 3600
    assert "lockout_ticks" not in JG and "lockout_why" not in JG
    assert D.lockout_of(DOC, JG) == DOC["engine"]["lockout_ticks"]


def test_the_engine_and_the_room_kit_find_no_problem_with_it_in_any_variant():
    assert R.problems(DOC, JG) == []
    assert [p for p in D.problems(DOC) if "jungle" in p or "jg" in p.split()] == []
    for s in R.variant_slots(DOC, JG, SLOTS):
        assert R.walk_problems(DOC, JG, s) == [], R.variant_of(DOC, JG, s)["id"]
        assert SP.check_setpieces(DOC, R.resolve(DOC, JG, s), s) == []


def test_the_clock_is_about_32_minutes_required_at_band_one_and_the_authored_clock_covers_the_formula(walks):
    slack = DOC["engine"]["clock"]["slack_factor"]
    want = DC.derive(DOC, JG)
    own = JG["clock_s_by_band"]
    for b, s in want.items():
        assert s <= own[b] <= s + 120, (b, own[b], s)       # the formula, plus the set piece's allowance (clock_why)
    req1 = max(sum(DC.required(DOC, JG, 1, DC.clock_rooms(DOC, JG, 1, w)).values()) for w in walks.values())
    assert 30 * 60 <= req1 <= 34 * 60, req1 / 60
    assert 38 * 60 <= own["1"] <= 42 * 60 and abs(own["1"] - req1 * slack) <= 120
    assert DC.clock_problems(DOC, JG) == []
    assert DA.design_room_clocks()["jungle"] == [own[str(b)] // 60 for b in range(1, 7)]
    assert "setpiece" in JG["clock_why"] or "set piece" in JG["clock_why"]


def test_fewer_rooms_than_pass_one_wide_rooms_and_short_connectors(walks):
    assert len(RECORDS) < 26                                 # pass 1 had 26 rooms; this counts both ways over the gorge and the side room
    for r in R.layout(DOC, JG, SLOT):
        if R.flags_of(r["kind"])["connector"]:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
        elif r["route"] == "main" and r["kind"] not in ("entry_room", "exit_room", "safe_room"):
            assert 24 <= r["width"] <= 62, (r["id"], r["width"])   # the undercroft, 24, runs under the colonnade
    assert max(r["height"] for r in RECORDS) >= 20, "a canopy hall"


def test_most_rooms_are_shaped_and_the_route_turns_climbs_drops_and_doubles_back():
    rooms = R.layout(DOC, JG, SLOT)
    shaped = [r for r in rooms if r["shape"] != "box"]
    can = [r for r in rooms if r["kind"] not in R.BOX_ONLY_KINDS | {"stairs", "entry_room", "exit_room", "vault", "puzzle"}]
    assert len(shaped) >= 0.8 * len(can) and len(shaped) > len(rooms) / 2, (len(shaped), len(can), len(rooms))
    assert len({r["shape"] for r in shaped}) >= 5
    sides = {d["side"] for r in rooms for d in r["doors"]}
    assert sides == {"north", "south", "east", "west"}
    assert any(r["doors"] and any(d["y"] > r["floor_in"] for d in r["doors"] if d["dir"] == "out") for r in rooms), "a landing"
    assert [r["id"] for r in rooms if r.get("dir") == "west"], "a stretch walked back west"
    floors = [r["floor_in"] for r in rooms]
    assert max(floors) - min(floors) >= 10, "climbs and drops"
    by = {r["id"]: r for r in rooms}
    # the undercroft is walked UNDER the colonnade: stacked rooms
    u, c = by["undercroft"], by["colonnade"]
    assert u["xa"] < c["xb"] and c["xa"] < u["xb"] and u["za"] < c["zb"] and c["za"] < u["zb"] and u["ceil_y"] < c["hull_lo"]


def test_every_room_type_the_owner_named_is_there_with_ours_the_heal_and_the_set_piece():
    kinds = {r["kind"] for r in RECORDS}
    assert OWNER_NAMED <= kinds, OWNER_NAMED - kinds
    assert len(kinds & OURS) >= 5, kinds & OURS
    assert any(r["kind"] == "safe_room" and r.get("params", {}).get("healer") for r in RECORDS)
    main = [r for r in JG["rooms"] if r["kind"] not in R.CONTAINERS]
    assert main[0]["kind"] == "entry_room" and kinds_in_order(main)[-2:] == ["boss_arena", "exit_room"]


def test_the_pacing_no_two_fights_meet_on_any_route_the_heal_about_two_thirds_in(walks):
    for s in R.variant_slots(DOC, JG, SLOTS):
        rooms = R.layout(DOC, JG, s)
        by_i = {r["i"]: r for r in rooms}
        for r in rooms:                                     # along every door out, on every route
            for d in r["doors"]:
                if d["dir"] == "out" and not d.get("shortcut"):
                    n = by_i[d["to"]]
                    assert not (r["kind"] in FIGHTS and n["kind"] in FIGHTS), (r["id"], n["id"])
    for vid, rows in walks.items():
        path = [r for r in DC.clock_rooms(DOC, JG, 1, rows)]
        order = {r["id"]: k for k, r in enumerate(rows)}
        path.sort(key=lambda r: order[r["id"]])
        total = sum(r["walk"] for r in path)
        before = 0
        for r in path:
            if r["kind"] == "safe_room":
                break
            before += r["walk"]
        assert 0.6 <= before / total <= 0.8, (vid, before / total)
    ids = [r["id"] for r in JG["rooms"]]
    kinds = [r["kind"] for r in JG["rooms"]]
    assert kinds.index("resources") < min(kinds.index(k) for k in ("habitat", "miniboss", "boss_arena"))


def test_the_temple_is_dressed_stone_and_the_jungle_dense(walks):
    by = {b.room["id"]: b for b in R.slot_build(DOC, JG, SLOT)}
    names = lambda b: {op[2].split("[")[0] for op in b.ops if op[0] in ("fill", "set")}  # noqa: E731
    for rid in ("colonnade", "sanctum", "altar"):
        assert {"minecraft:mossy_stone_bricks", "minecraft:chiseled_stone_bricks"} & names(by[rid]), rid
    logs = [r["id"] for r in R.layout(DOC, JG, SLOT) if r["kind"] == "drift" and "minecraft:jungle_log" in names(by[r["id"]])]
    assert len(logs) >= 4, logs
    assert "minecraft:cave_vines" in names(by["sanctum"]), "the canopy hall is lit by glow berries"


# ------------------------------------------------------------------------------------------------- replayability


def test_one_fork_fast_and_dangerous_against_safe_and_long_rejoining_at_the_orchard(walks):
    forks = [r for r in JG["rooms"] if r["kind"] == "fork"]
    assert len(forks) == 1 and len(forks[0]["routes"]) == 2
    fast, safe = forks[0]["routes"]
    assert [r["kind"] for r in fast["rooms"]] == ["collapse_bridge"], "the fast way can drop the walker"
    assert not {r["kind"] for r in safe["rooms"]} & {"collapse_bridge", "parkour", "setpiece"}
    ids = [r["id"] for r in JG["rooms"]]
    assert ids[ids.index(forks[0]["id"]) + 1] == "orchard"
    for vid, rows in walks.items():
        w = {k: sum(r["walk"] for r in rows if r["route"] == "%s/%s" % (forks[0]["id"], k)) for k in (fast["id"], safe["id"])}
        assert w[safe["id"]] > w[fast["id"]], (vid, w)       # longer to walk; the bridge's price is its fall
        fall = DOC["engine"]["clock"]["fall_penalty_s"]
        assert fall > 0
    orchard = next(r for r in R.layout(DOC, JG, SLOT) if r["id"] == "orchard")
    assert len([d for d in orchard["doors"] if d["dir"] == "in"]) == 2, "both ways come in by the orchard's west wall"


def test_one_side_room_a_dead_end_the_clock_does_not_count(walks):
    sides = [r for r in JG["rooms"] if r["kind"] == "side"]
    assert len(sides) == 1
    side_ids = {r["id"] for r in sides[0]["rooms"]}
    rooms = R.layout(DOC, JG, SLOT)
    for r in rooms:
        if r["id"] in side_ids:
            assert r["route"] == sides[0]["id"]
    last = next(r for r in rooms if r["id"] == sides[0]["rooms"][-1]["id"])
    assert not [d for d in last["doors"] if d["dir"] == "out"]
    for rows in walks.values():
        assert not side_ids & {r["id"] for r in DC.clock_rooms(DOC, JG, 1, rows)}


def test_two_secrets_one_cracked_one_balcony_each_room_carrying_a_unique_relic_and_short_lore():
    secret_rooms = [r for r in RECORDS if r.get("secrets")]
    types = sorted(s["type"] for r in secret_rooms for s in r["secrets"])
    assert types == ["balcony", "cracked"], types
    relics = []
    for r in secret_rooms:
        assert len(r["secrets"]) == 1, r["id"]               # one secret per room: the relic is the room's param
        p = r["params"]
        assert re.fullmatch(r"[a-z0-9_]+", p["relic"]) and p["relic"].startswith("jg_")
        assert 0 < len(p["lore"]) <= 160 and p["lore"].isascii() and p["lore"].isprintable()
        assert 1 <= p["lore"].count(".") + p["lore"].count("!") + p["lore"].count("?") <= 3
        assert len(p.get("relic_name", "")) <= 32
        relics.append(p["relic"])
    assert len(relics) == len(set(relics)) == 2
    assert not [r["id"] for r in RECORDS if r.get("params", {}).get("relic") and not r.get("secrets")]
    for s in R.variant_slots(DOC, JG, SLOTS):                 # built in every variant, with its relic spot
        built = {b.room["id"]: b for b in R.slot_build(DOC, JG, s)}
        for r in secret_rooms:
            meta = built[r["id"]].meta["secrets"]
            assert len(meta) == 1 and built[r["id"]].anchors.get("secret"), (r["id"], s["k"])


def test_a_shortcut_back_toward_the_entry_opened_from_the_far_side_only():
    scs = [(r["id"], sc) for r in RECORDS for sc in r.get("shortcuts") or []]
    assert len(scs) == 1
    far_id, sc = scs[0]
    for s in R.variant_slots(DOC, JG, SLOTS):
        rooms = {r["id"]: r for r in R.layout(DOC, JG, s)}
        far, near = rooms[far_id], rooms[sc["to"]]
        assert near["i"] < far["i"] and not far.get("layout_errors")
        assert [d for d in far.get("shortcut_doors", []) if d["dir"] == "out"]
        assert [d for d in near.get("shortcut_doors", []) if d["dir"] == "in"]
    files = D.build(DOC)
    assert any(k.endswith("/room/jungle/%s/s%d/shortcut_%s.mcfunction" % (far_id, SLOT["g"], sc["id"])) for k in files)


def test_four_distinct_variants_one_per_slot_using_mirror_seed_and_swap():
    vs = JG["variants"]
    assert len(vs) == 4 and len({v["id"] for v in vs}) == 4
    assert [R.variant_of(DOC, JG, s)["id"] for s in SLOTS] == [v["id"] for v in vs]
    assert any(v.get("mirror") for v in vs) and any(v.get("seed") for v in vs) and any(v.get("swap") for v in vs)
    assert len({json.dumps({k: v[k] for k in v if k != "id"}, sort_keys=True) for v in vs}) == 4
    shapes = []
    for s in SLOTS:
        rooms = R.layout(DOC, JG, s)
        built = R.slot_build(DOC, JG, s)
        shapes.append(tuple((r["id"], r["za"] - s["z0"], r["kind"], len(b.ops)) for r, b in zip(rooms, built)))
        assert rooms[0]["kind"] == "entry_room" and rooms[-1]["kind"] == "exit_room"
    assert len(set(shapes)) == 4, "each slot lays its rooms differently"


def test_the_set_piece_is_the_lights_out_the_climax_before_the_boss():
    main = [r for r in JG["rooms"] if r["kind"] not in R.CONTAINERS]
    sp = [r for r in RECORDS if r["kind"] == "setpiece"]
    assert len(sp) == 1 and sp[0]["params"]["piece"] == "lights_out" and sp[0]["params"]["pit"] == 0
    assert main[-3]["kind"] == "setpiece" and main[-2]["kind"] == "boss_arena"


# ------------------------------------------------------------------------------------------------- the params contract


def rooms_of(*kinds):
    return [r for r in RECORDS if r["kind"] in kinds]


def test_the_stands_and_the_ambushes_follow_the_members_by_band_and_the_triggers_are_one_per_trainer():
    for s in R.variant_slots(DOC, JG, SLOTS):
        for r in R._walk_records(R.resolve(DOC, JG, s)["rooms"]):
            if r["kind"] in ("stand", "gauntlet", "ambush"):
                assert r["gate"] == "cleared"
                assert DF.stand_problems(DOC, r) == [], r["id"]
            if r["kind"] in ("gauntlet", "ambush"):
                tr = r["params"]["triggers"]
                assert len(tr) == len(r["params"]["trainers"]) and tr == sorted(tr) and 0 < tr[0] and tr[-1] < 1


def test_the_wild_rooms_carry_the_contracts_fields_within_the_band_caps():
    bands = {str(b["band"]): b for b in D.bands(DOC)}
    for r in rooms_of("nest"):
        p = r["params"]
        assert p["species"] and set(p["count_by_band"]) == set(bands) and r["gate"] == "cleared"
        lo, hi = p["level_spread"]
        assert 0 <= lo <= hi
    for r in rooms_of("miniboss"):
        p = r["params"]
        assert set(p["species_by_band"]) == set(bands) and p["level_offset"] <= 0 and p.get("catchable", True) is True   # the owner, 2026-10-10: every dungeon Pokemon catchable
    for r in rooms_of("habitat"):
        p = r["params"]
        assert p["fight_only"] is False and set(p["level_by_band"]) == set(bands)
        assert r.get("gate", "open") == "open", "Zarude is optional: the slack pays for it (clock_why)"
        for k, lv in p["level_by_band"].items():
            assert lv <= max(bands[k]["caps"]), (k, lv)
        assert 95 <= p["level_by_band"]["6"] <= 100
    for r in rooms_of("puzzle"):
        p = r["params"]
        assert p["variant"] in ("levers", "sequence", "plates") and p["penalty_s"] > 0 and r["gate"] == "cleared"
    for r in rooms_of("vault"):
        p = r["params"]
        assert r.get("gate", "open") == "open" and 1 <= p["chests"] <= 8 and p["clock_cost_s"] > 0
        assert set(p["loot_by_band"]) == set(bands) and r["length"] >= 4 * p["chests"] + 12
    for r in rooms_of("safe_room"):
        assert r["params"]["healer"] is True


def test_the_boss_has_a_crew_per_stage_per_band_the_ace_last_and_the_same_ace_in_every_stage():
    bo = JG["boss"]
    assert bo["name"] != DOC["dungeons"][0]["boss"]["name"]
    for b in D.bands(DOC):
        crews = bo["teams"][str(b["band"])]
        assert len(crews) == len(bo["stage_level_offsets"])
        assert len({c[-1] for c in crews}) == 1
        assert all(1 <= len(c) <= 6 for c in crews)


# ------------------------------------------------------------------------------------------------- species


def all_species():
    out = set()
    for r in RECORDS:
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
    assert sorted(s for s in all_species() if B.key(s) not in jar_species) == []


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


# ------------------------------------------------------------------------------------------------- generator mutations


def test_mutating_the_glow_vines_off_leaves_rooms_dark_and_the_walk_check_says_so(monkeypatch):
    R._BUILT.clear()
    monkeypatch.setitem(R.DRESS, "glow_vines", (lambda ctx, spec: None, "light"))
    bad = R.walk_problems(DOC, JG, SLOT)
    R._BUILT.clear()
    assert any("no light" in p for p in bad), bad[:3]


def test_mutating_the_kit_so_rooms_never_touch_loses_the_shortcut_and_the_plan_check_says_so(monkeypatch):
    R._BUILT.clear()
    monkeypatch.setattr(R, "_touch", lambda far, near: None)
    bad = R.plan_problems(DOC, JG, SLOT)
    R._BUILT.clear()
    assert any("shortcut c1" in p and "does not touch" in p for p in bad), bad[:3]


def test_the_build_writes_one_shell_function_per_room_inside_the_chain_budget():
    files = D.build(DOC)
    shell = [k for k in files if "/shells/s%d/" % SLOT["g"] in k]
    assert len(shell) == len(R.layout(DOC, JG, SLOT))
    for s in SLOTS:
        assert R.chain_problems(DOC, JG, s) == []
    assert R.total_blocks(DOC, SLOT) < 1.2e6
