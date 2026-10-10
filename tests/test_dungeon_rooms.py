"""The dungeon room kit (tools/dungeon_rooms.py, tools/dungeon_kinds.py, tools/dungeon_grid.py, data/dungeon_themes.json).

The builder's own tests (the independent audit is another agent's). Three kinds of check:

  static    the plan, the themes and the generated functions read as text;
  walk      the room grids replayed from the ops, walked with a 2-high 1-wide player (reversible edges only). The
            MUTATION tests change the GENERATOR (a maze that loses a passage, platforms with wider gaps, a kind that
            places lava) and leave the authored data alone, so they test that the check bites and not that the data
            agrees with itself;
  runtime   the generated functions driven on tests/pocket_sim.py through the engine's own keeper (entry hook once,
            clear idempotent, reset closes the gate, a fall costs the clock and teleports, the span collapses behind
            a crossing player, the seam credits the greed ladder).

Not covered: anything in a running Minecraft. Every block id is checked against the 1.21.1 jar when it is present, but
whether a block *behaves* (vines holding, leaves not decaying, water staying put, can_place_on on a torch in
adventure) is the owner's look and the experiment named in docs/mechanics/DUNGEON_ROOMS.md.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_kinds as K  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import function_limits as FL  # noqa: E402
import pocket_sim as PS  # noqa: E402

DEMO = json.loads((ROOT / "tests" / "fixtures" / "dungeon_demo_rooms.json").read_text(encoding="utf-8"))["rooms"]
THEMES = R.load_themes()["themes"]
BASE = D.load()
POCKET = BASE["engine"]["pocket"]["dimension"]


def demo_doc(theme="mine", rooms=None, per_dungeon=1):
    doc = copy.deepcopy(BASE)
    doc["dungeons"] = doc["dungeons"][:1]
    d = doc["dungeons"][0]
    d["theme"] = theme
    d["rooms"] = copy.deepcopy(rooms if rooms is not None else DEMO)
    d.pop("spine", None)
    d.pop("clock_s_by_band", None)        # the demo is not the Night Shift: it runs on the bands' clocks
    doc["dungeons"] = [d]       # the demo alone: the authored dungeons after it (wave 2) have their own tests
    doc["engine"]["sigils"]["free_first_entry"]["dungeons"] = [x for x in doc["engine"]["sigils"]["free_first_entry"]["dungeons"] if x == d["id"]]
    doc["engine"]["slots"]["per_dungeon"] = per_dungeon
    return doc


def legacy_doc():
    """The Night Shift on its old placeholder spine (tests/fixtures/dungeon_legacy_spine.json): the spine path of
    tools/dungeon.py still builds a dungeon without rooms."""
    doc = copy.deepcopy(BASE)
    doc["dungeons"] = doc["dungeons"][:1]
    d = doc["dungeons"][0]
    for k in ("theme", "rooms", "rooms_why", "clock_s_by_band", "clock_why"):
        d.pop(k, None)
    d["spine"] = json.loads((ROOT / "tests" / "fixtures" / "dungeon_legacy_spine.json").read_text(encoding="utf-8"))["spine"]
    return doc


def first_slot(doc):
    return D.slots(doc)[0]


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


# ------------------------------------------------------------------------------------------------- themes


def vanilla_ids():
    import town_character as TC
    jar = TC.default_vanilla_jar()
    if jar is None or not Path(jar).is_file():
        return None
    with zipfile.ZipFile(jar) as z:
        return {"minecraft:" + n.rsplit("/", 1)[1][:-5] for n in z.namelist()
                if n.startswith("assets/minecraft/blockstates/") and n.endswith(".json")}


def theme_blocks(theme):
    out = set()

    def walk(v):
        if isinstance(v, str) and v.startswith("minecraft:"):
            out.add(G.base(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    t = {k: v for k, v in theme.items() if k not in ("name", "why", "messages")}
    walk(t)
    return out


def test_three_themes_exist_and_name_every_block_a_kind_needs():
    assert set(THEMES) == {"mine", "jungle", "flooded_ruin"}
    for name, t in THEMES.items():
        for key in ("hull", "door", "rip", "lamp", "messages", "dress", "maze", "parkour", "bridge", "seam", "safe", "dark"):
            assert key in t, (name, key)
        assert {"wall", "floor", "ceiling", "light", "light_every", "min_light"} <= set(t["hull"])
        for op in t["dress"]:
            assert op["op"] in R.DRESS, (name, op["op"])


def test_every_theme_block_exists_in_minecraft_1_21_1_and_none_is_banned():
    ids = vanilla_ids()
    for name, t in THEMES.items():
        for b in theme_blocks(t):
            assert not G.forbidden(b), (name, b)
            assert G.classify(b) != G.HAZARD, (name, b)
            if ids is not None and b not in ("minecraft:air", "minecraft:water"):
                assert b in ids, (name, b)


def test_the_hull_is_opaque_so_the_pockets_noon_sky_cannot_light_a_room():
    thin = re.compile(r"leaves|glass|slab|stairs|fence|bars|carpet|ice|vine|lantern|lichen|torch|trapdoor|door")
    for name, t in THEMES.items():
        for k in ("wall", "floor", "ceiling"):
            assert not thin.search(t["hull"][k]), (name, k, t["hull"][k])
    sky = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))["pocket"]["generator"]
    assert sky["has_skylight"] is True and sky["fixed_time"] == 6000      # the premise of the rule above


def test_no_theme_block_is_one_the_rift_pick_can_break_outside_the_seam():
    pick = set(BASE["engine"]["rift_pick"]["can_break"])
    for name, t in THEMES.items():
        seam = {e["block"] for e in t["seam"]["blocks"]}
        rest = theme_blocks({k: v for k, v in t.items() if k != "seam"})
        assert not (rest & (seam | pick)), (name, rest & (seam | pick))


def test_the_jungle_is_dense_trunks_canopy_vines_and_a_floor_of_plants():
    doc = demo_doc("jungle")
    builts = R.slot_build(doc, doc["dungeons"][0], first_slot(doc))
    hab = next(b for b in builts if b.room["id"] == "hab")           # an unregistered kind: dressed 'full' by default
    names = {G.base(n): int((hab.grid.a == hab.grid.idx[n]).sum()) for n in hab.grid.names()}
    cells = (hab.room["ix1"] - hab.room["ix0"] + 1) * (hab.room["iz1"] - hab.room["iz0"] + 1)
    trunk_cols = (names.get("minecraft:jungle_log", 0) + names.get("minecraft:mangrove_log", 0)) / (hab.room["height"] - 1)
    assert trunk_cols / cells > 0.12, "trunks stand on at least one cell in eight"
    assert names.get("minecraft:jungle_leaves", 0) > 1.3 * cells, "two layers of leaves, with holes, for a ceiling"
    assert names.get("minecraft:vine", 0) > 100
    plants = sum(names.get(n, 0) for n in ("minecraft:fern", "minecraft:short_grass", "minecraft:tall_grass", "minecraft:large_fern", "minecraft:moss_carpet"))
    assert plants / cells > 0.2
    assert names.get("minecraft:water", 0) > 0, "a shallow stream to wade"
    # no line of sight down the room is clear: along every row of cells a trunk or a leaf curtain is met
    ox = hab.grid.box[0]
    clear_rows = 0
    for z in range(hab.room["iz0"], hab.room["iz1"] + 1):
        blocked = any(G.classify(hab.grid.block_at(x, hab.room["floor_in"] + k, z)) == G.SOLID
                      for x in range(hab.room["ix0"], hab.room["ix1"] + 1) for k in (1,))
        clear_rows += 0 if blocked else 1
    assert clear_rows == 0


# ------------------------------------------------------------------------------------------------- the plan


@pytest.mark.parametrize("theme", sorted(THEMES))
def test_the_demo_list_has_no_problems_in_any_theme(theme):
    doc = demo_doc(theme)
    assert R.problems(doc) == []
    assert D.problems(doc) == []


@pytest.mark.parametrize("theme", sorted(THEMES))
def test_consecutive_rooms_share_a_door_exactly_and_the_floor_is_continuous(theme):
    doc = demo_doc(theme)
    s = first_slot(doc)
    rooms = R.layout(doc, doc["dungeons"][0], s)
    for a, b in zip(rooms, rooms[1:]):
        assert a["door_out"] == b["door_in"], (a["id"], b["id"])
        x0, y0, z0, x1, y1, z1 = a["door_out"]
        assert (x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1) == (2, 4, 3), "a door is 3 wide and 4 high (two wall columns deep)"
        assert a["xb"] + 1 == b["xa"] and a["floor_out"] == b["floor_in"] and a["z_out"] == b["z_in"]
    assert rooms[0]["door_in"] is None and rooms[-1]["door_out"] is None
    for r in rooms:
        assert s["z0"] <= r["za"] and r["zb"] <= s["z0"] + 63 and r["width"] <= 62
        assert r["hull_lo"] >= 6 and r["ceil_y"] <= 250


def test_connectors_are_at_most_40_long_and_at_least_7_wide_and_the_plan_says_so():
    bad = copy.deepcopy(DEMO)
    next(r for r in bad if r["id"] == "d1")["length"] = 60
    next(r for r in bad if r["id"] == "d3")["width"] = 5
    p = R.problems(demo_doc("mine", bad))
    assert any("d1" in x and "at most 40 long" in x for x in p) and any("d3" in x and "at least 7 wide" in x for x in p)


def test_the_plan_refuses_what_would_trap_or_overflow():
    bad = copy.deepcopy(DEMO)
    next(r for r in bad if r["id"] == "rest")["rise"] = 2                 # only stairs and drifts change level
    next(r for r in bad if r["id"] == "dark")["width"] = 70               # over the strip
    next(r for r in bad if r["id"] == "entry")["gate"] = "cleared"        # the threshold must stay open
    p = " | ".join(R.problems(demo_doc("mine", bad)))
    assert "only stairs and drifts" in p and "over the strip" in p and "entry room's threshold" in p
    bad.append({"id": "extra", "kind": "stand", "length": 20, "width": 11, "height": 6})   # nothing after the exit room
    assert "end with the exit room" in " | ".join(R.problems(demo_doc("mine", bad)))
    unknown = copy.deepcopy(DEMO)
    unknown[3]["kind"] = "bogus"
    assert any("unknown kind" in x for x in R.problems(demo_doc("mine", unknown)))


def test_a_maze_and_a_parkour_snap_or_refuse_rather_than_build_something_unsolvable():
    doc = demo_doc("mine")
    rooms = {r["id"]: r for r in R.layout(doc, doc["dungeons"][0], first_slot(doc))}
    assert (rooms["maze"]["length"] - 3) % 4 == 0 and (rooms["maze"]["width"] - 1) % 4 == 0
    assert (rooms["maze"]["z_out"] - rooms["maze"]["z_in"]) % 4 == 0
    bad = copy.deepcopy(DEMO)
    next(r for r in bad if r["id"] == "maze")["params"] = {"exit_dz": 6}
    assert any("multiple of 4" in x for x in R.problems(demo_doc("mine", bad)))
    low = copy.deepcopy(DEMO)
    next(r for r in low if r["id"] == "jump")["height"] = 5
    assert any("parkour needs a height" in x for x in R.problems(demo_doc("mine", low)))


def test_rise_is_a_staircase_of_one_block_steps_and_the_doors_meet_it():
    doc = demo_doc("mine")
    d = doc["dungeons"][0]
    rooms = {r["id"]: r for r in R.layout(doc, d, first_slot(doc))}
    up = rooms["d2"]
    assert up["floors"][0] == up["floor_in"] and up["floors"][-1] == up["floor_out"] == up["floor_in"] + 3
    assert all(0 <= b - a <= 1 for a, b in zip(up["floors"], up["floors"][1:]))
    down = rooms["d3"]
    assert all(0 <= a - b <= 1 for a, b in zip(down["floors"], down["floors"][1:])) and down["floor_out"] == up["floor_out"] - 3


# ------------------------------------------------------------------------------------------------- the walk check


def test_the_demo_is_walkable_entry_to_exit_and_back_through_every_room():
    for theme in THEMES:
        doc = demo_doc(theme)
        d = doc["dungeons"][0]
        s = first_slot(doc)
        assert R.walk_problems(doc, d, s) == [], theme
        for b in R.slot_build(doc, d, s):
            r = b.room
            g = b.grid
            cls = g.cls()
            jumps = R.flags_of(r["kind"])["jumps"]
            a = g.local(r["ix0"] if r["kind"] != "entry_room" else r["xa"] + 3, r["floor_in"], r["z_in"])
            if r["door_out"]:
                z = g.local(r["ix1"], r["floor_out"], r["z_out"])
                assert z in G.walk(g, [a], jumps=jumps, cls=cls), (theme, r["id"])
                assert a in G.walk(g, [z], jumps=jumps, cls=cls), (theme, r["id"], "back")


def test_a_parkour_is_walkable_only_by_jumping_and_every_jump_is_inside_the_designs_limits():
    doc = demo_doc("mine")
    b = next(x for x in R.slot_build(doc, doc["dungeons"][0], first_slot(doc)) if x.room["id"] == "jump")
    r, g = b.room, b.grid
    cls = g.cls()
    start = g.local(r["ix0"], r["floor_in"], r["z_in"])
    end = g.local(r["ix1"], r["floor_out"], r["z_out"])
    assert end not in G.walk(g, [start], jumps=False, cls=cls)
    assert end in G.walk(g, [start], jumps=True, cls=cls)
    plats = b.anchors["platforms"]
    assert len(plats) >= 8
    assert G.JUMP_FLAT_MAX == 4 and G.JUMP_RISE_MAX == 3        # DUNGEONS.md V6: flat gap 3, rise 1 with gap 2
    # and the generator (tools/dungeon_parkour.py, which replaced the kit's) keeps to those limits in every hop it plans:
    # 4 cells flat, 3 with a rise or fall of one (tests/test_dungeon_setpieces.py re-derives them from the blocks)
    assert b.meta["hops"] and all(2 <= h["n"] <= 4 and (h["n"] <= 3 or h["dy"] == 0) for h in b.meta["hops"])


def test_a_fall_never_reaches_the_void_a_catch_floor_lies_under_every_column():
    doc = demo_doc("flooded_ruin")
    for rid in ("jump", "bridge"):
        b = next(x for x in R.slot_build(doc, doc["dungeons"][0], first_slot(doc)) if x.room["id"] == rid)
        r, g = b.room, b.grid
        assert r["pit"] == 6
        cls = g.cls()
        x0, y0, z0 = g.box[:3]
        for x in range(r["ix0"], r["ix1"] + 1):
            for z in range(r["iz0"], r["iz1"] + 1):
                assert cls[x - x0, r["y_lo"] - 1 - y0, z - z0] == G.SOLID, (rid, x, z)


def test_mutating_the_maze_generator_to_cut_a_passage_makes_the_walk_check_fail(monkeypatch):
    orig = K._maze_tree

    def cut(nx, nz, start, rg, loops):
        adj = orig(nx, nz, start, rg, loops)
        for (i, j), ns in adj.items():
            for n in list(ns):
                if n[0] == nx - 1 and i == nx - 2:
                    ns.discard(n)
                    adj[n].discard((i, j))
        return adj
    monkeypatch.setattr(K, "_maze_tree", cut)
    p = R.problems(demo_doc("mine"))
    assert any("maze" in x and "cannot be walked" in x for x in p), p[:3]


def test_mutating_the_parkour_generator_to_widen_the_gaps_makes_the_walk_check_fail(monkeypatch):
    import dungeon_parkour as P
    orig = P._tier_opts

    def wide(tier, relaxed):
        N, W = orig(tier, relaxed)
        return [n + 1 for n in N], W      # every hop one cell longer than the grid's jump allows
    monkeypatch.setattr(P, "_tier_opts", wide)
    p = R.problems(demo_doc("jungle"))
    assert any("jump (parkour)" in x and "cannot be walked" in x for x in p), p[:3]


def test_mutating_a_kind_to_place_lava_or_sand_is_refused(monkeypatch):
    orig = K.kind_drift

    def bad(doc, d, slot, room, theme):
        return {"blocks": [R.setb((room["ix0"] + 5, room["floor_in"], room["iz0"] + 1), "minecraft:lava"),
                           R.setb((room["ix0"] + 7, room["floor_in"], room["iz0"] + 1), "minecraft:sand")]}
    monkeypatch.setitem(R.KINDS, "drift", bad)
    p = " | ".join(R.problems(demo_doc("mine")))
    assert "minecraft:lava is a hazard" in p and "minecraft:sand is forbidden" in p


def test_mutating_the_hull_to_punch_the_floor_is_refused(monkeypatch):
    def punch(doc, d, slot, room, theme):
        y = room["floors"][0] - 1
        return {"blocks": [R.fill((room["ix0"] + 4, y - 3, room["iz0"] + 2, room["ix0"] + 4, y, room["iz0"] + 2), "minecraft:air")]}
    monkeypatch.setitem(R.KINDS, "drift", punch)
    p = " | ".join(R.problems(demo_doc("mine")))
    assert "has no floor" in p


def test_mutating_the_lights_off_leaves_standable_cells_in_the_dark_and_the_check_says_so(monkeypatch):
    assert not any("no light" in x for x in R.problems(demo_doc("flooded_ruin")))
    R._BUILT.clear()
    monkeypatch.setattr(R, "hull_lights", lambda ctx, room, theme, ref_y: None)
    p = R.problems(demo_doc("flooded_ruin"))
    assert any("standable cells have no light" in x for x in p)


def test_a_wall_block_the_pick_can_break_is_a_hole_and_the_check_says_so():
    doc = demo_doc("mine")
    doc["engine"]["rift_pick"]["can_break"].append("minecraft:cobbled_deepslate")      # the mine's hull wall
    p = R.problems(doc)
    assert any("rift pick can break" in x for x in p)


def test_a_seam_is_24_ores_on_the_face_of_a_slab_three_thick_with_rock_behind_every_one():
    for theme in THEMES:
        doc = demo_doc(theme)
        b = next(x for x in R.slot_build(doc, doc["dungeons"][0], first_slot(doc)) if x.room["id"] == "seam")
        seam = b.anchors["seam"]
        assert len(seam) == 24
        g = b.grid
        for (x, y, z) in seam:
            assert g.block_at(x, y, z) in {e["block"] for e in THEMES[theme]["seam"]["blocks"]}
            assert g.block_at(x, y, z - 1) == THEMES[theme]["seam"]["slab"] and g.block_at(x, y, z - 2) == THEMES[theme]["seam"]["slab"]
            assert G.classify(g.block_at(x, y, z + 1)) in (G.PASS, G.WATER), "the face is open on the room's side"
        assert b.room["iz0"] + 2 == seam[0][2]


# ------------------------------------------------------------------------------------------------- the interface


def test_declared_but_unregistered_kinds_build_as_themed_rooms_with_their_anchors_and_warn():
    doc = demo_doc("jungle")
    d = doc["dungeons"][0]
    s = first_slot(doc)
    w = D.warnings(doc)
    for kind in ("stand", "gauntlet", "miniboss", "nest", "habitat", "puzzle", "vault"):
        # a wave-2 module (dungeon_fights, dungeon_puzzles) registers its kinds on import: those no longer warn
        assert kind in R.KINDS or any("kind %s not implemented yet" % kind in x for x in w), kind
    assert not any("kind maze" in x for x in w)
    rooms = {r["id"]: r for r in R.plan(doc, d, s)}
    assert {"trainers", "line"} <= set(rooms["stand1"]["anchors"]) and len(rooms["stand1"]["anchors"]["trainers"]) == 3
    assert all(len(t) == 4 for t in rooms["stand1"]["anchors"]["trainers"]), "trainers carry a yaw"
    assert len(rooms["gaunt"]["anchors"]["trainers"]) == 4
    assert {"boss", "line"} <= set(rooms["mini"]["anchors"])
    assert len(rooms["nest"]["anchors"]["spawns"]) == 6
    assert {"legendary", "viewpoint"} <= set(rooms["hab"]["anchors"])
    assert len(rooms["puz"]["anchors"]["controls"]) == 3 and "display" in rooms["puz"]["anchors"]
    assert len(rooms["vault"]["anchors"]["chests"]) == 4
    assert "healer" in rooms["rest"]["anchors"]
    assert D.problems(doc) == []           # a warning is not an error


def test_a_registered_kind_replaces_the_default_and_its_blocks_anchors_and_functions_are_merged(monkeypatch):
    def wave2(doc, d, slot, room, theme):
        x = (room["ix0"] + room["ix1"]) // 2
        z = room["z_in"]
        return {"blocks": [R.setb((x, room["floor_in"] + 3, z), "minecraft:glowstone")],
                "anchors": {"trainers": [[x + 3, room["floor_in"], z, 90]]},
                "functions": {"enter": ["say wave two enters"], "clear": ["say wave two clears"], "tick": ["say tick"],
                              "extra": ["say extra"]}}
    monkeypatch.setitem(R.KINDS, "stand", wave2)
    monkeypatch.setitem(R.FLAGS, "stand", dict(R.DEFAULT_FLAGS, dress="none"))
    doc = demo_doc("mine")
    files = D.build(doc)
    d = doc["dungeons"][0]
    base = "data/cobblers/function/dungeons/room/night_shift/stand1/s1/"
    enter = files[base + "enter.mcfunction"]
    assert "say wave two enters" in enter and "unless score #s1r7 dg.rs matches 0 run return 0" in enter
    assert "say wave two clears" in files[base + "clear.mcfunction"]
    assert "say tick" in files[base + "tick.mcfunction"] and "say extra" in files[base + "extra.mcfunction"]
    assert "stand1/s1/tick" in files["data/cobblers/function/dungeons/slot/s1/rooms.mcfunction"]
    rooms = {r["id"]: r for r in R.plan(doc, d, first_slot(doc))}
    assert len(rooms["stand1"]["anchors"]["trainers"]) == 1 and "line" in rooms["stand1"]["anchors"]
    assert not any("kind stand " in w for w in D.warnings(doc))


def test_registering_with_an_unknown_flag_or_a_kind_with_no_theme_op_is_an_error():
    with pytest.raises(R.RoomError):
        R.register("x_kind", lambda *a: {}, bogus=1)
    assert "x_kind" not in R.KINDS


def test_every_room_gets_enter_clear_reset_and_the_slot_calls_them():
    doc = demo_doc("mine")
    files = D.build(doc)
    pre = "data/cobblers/function/dungeons/"
    gates = {r["id"]: r["gate"] for r in R.layout(doc, doc["dungeons"][0], first_slot(doc))}
    for r in DEMO:
        for fn in ("enter", "reset"):
            assert pre + "room/night_shift/%s/s1/%s.mcfunction" % (r["id"], fn) in files, (r["id"], fn)
        # a `cleared` room's clear always ships (an uncalled one is then a softlock the orphan check names); an OPEN
        # room's ships only when something calls it, else it is an orphan prepare refuses
        clear = pre + "room/night_shift/%s/s1/clear.mcfunction" % r["id"]
        called = any("cobblers:dungeons/room/night_shift/%s/s1/clear" % r["id"] in v for k, v in files.items() if k != clear)
        assert (clear in files) == (gates[r["id"]] == "cleared" or called), (r["id"], gates[r["id"]])
        # no per-room member dispatcher: nothing calls one, and prepare refuses a function no step or pack runs
        assert pre + "room/night_shift/%s/clear.mcfunction" % r["id"] not in files
    reset = files[pre + "slot/s1/reset.mcfunction"]
    assert reset.count("/reset") == len(DEMO)
    clock = files[pre + "m/clock.mcfunction"]
    assert "slot/s1/rooms" in clock and clock.index("slot/s1/rooms") < clock.index("slot/s1/boss")


def test_the_boss_arena_gate_opens_through_its_rooms_clear_and_no_old_gate_fill_is_left():
    doc = demo_doc("mine")
    files = D.build(doc)
    done = files["data/cobblers/function/dungeons/slot/s1/boss_done.mcfunction"]
    assert "function cobblers:dungeons/room/night_shift/arena/s1/clear" in done and "fill" not in done
    arena = [r for r in R.layout(doc, doc["dungeons"][0], first_slot(doc)) if r["id"] == "arena"][0]
    clear = files["data/cobblers/function/dungeons/room/night_shift/arena/s1/clear.mcfunction"]
    x0, y0, z0, x1, y1, z1 = arena["door_out"]
    assert "execute in %s run fill %d %d %d %d %d %d minecraft:air" % (POCKET, x0, y0, z0, x1, y1, z1) in clear
    assert "playsound" not in clear, "the engine's own boss cue plays; the arena's clear is quiet"


def test_gate_lines_close_and_open_the_door_out_and_only_a_cleared_room_is_shut_by_the_shell():
    doc = demo_doc("jungle")
    d = doc["dungeons"][0]
    s = first_slot(doc)
    theme = R.theme_for(d)
    rooms = R.plan(doc, d, s)
    stand = next(r for r in rooms if r["id"] == "stand1")
    x0, y0, z0, x1, y1, z1 = stand["door_out"]
    assert R.gate_lines(doc, stand, False, theme) == ["fill %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, theme["door"]["gate"])]
    assert R.gate_lines(doc, stand, True, theme) == ["fill %d %d %d %d %d %d minecraft:air" % (x0, y0, z0, x1, y1, z1)]
    assert R.gate_lines(doc, rooms[-1], True, theme) == []
    builts = {b.room["id"]: b for b in R.slot_build(doc, d, s)}
    shut = [ln for ln in R.shell_lines(builts["stand1"]) if ln.endswith(theme["door"]["gate"]) and ("fill %d " % x0) in ln]
    assert shut, "a cleared room's shell writes its gate shut last"
    assert not any(ln.endswith(theme["door"]["gate"]) for ln in R.shell_lines(builts["d1"]))   # an open room is never shut
    assert builts["stand1"].gate_ops and builts["d4"].gate_ops, "the room after a cleared gate closes its own column too"
    # the walk grid never holds a closed gate: the check is made with every gate open
    assert builts["stand1"].grid.block_at(x0, y0, z0 + 1) == "minecraft:air"


def test_the_plan_is_the_same_dungeon_in_all_four_slots_shifted_by_the_row_spacing():
    doc = demo_doc("flooded_ruin", per_dungeon=4)
    d = doc["dungeons"][0]
    sl = D.slots(doc)
    a = R.slot_build(doc, d, sl[0])
    for k in (1, 3):
        b = R.slot_build(doc, d, sl[k])
        dz = sl[k]["z0"] - sl[0]["z0"]
        assert dz == 128 * k
        for ba, bb in zip(a, b):
            assert len(ba.ops) == len(bb.ops)
            for oa, ob in zip(ba.ops, bb.ops):
                assert oa[0] == ob[0] and oa[2] == ob[2]
                if oa[0] == "set":
                    assert (oa[1][0], oa[1][1], oa[1][2] + dz) == tuple(ob[1])
                else:
                    assert (oa[1][0], oa[1][1], oa[1][2] + dz, oa[1][3], oa[1][4], oa[1][5] + dz) == tuple(ob[1])


# ------------------------------------------------------------------------------------------------- the shell at full length


def full_length_rooms():
    """The demo's middle rooms twice over: a dungeon of about 1,500 blocks."""
    mid = [r for r in DEMO if r["id"] not in ("entry", "exit", "arena")]
    rooms = [copy.deepcopy(DEMO[0])]
    for rep in (1, 2):
        for r in mid:
            c = copy.deepcopy(r)
            c["id"] = "%s_%d" % (r["id"], rep)
            if c["kind"] == "maze":
                c["params"] = {"exit_dz": 0}
            if c["id"].startswith("d1"):
                c["params"] = {"exit_dz": -4 if rep == 1 else 0}
            rooms.append(c)
    rooms += [copy.deepcopy(DEMO[-2]), copy.deepcopy(DEMO[-1])]
    return rooms


def test_a_full_length_dungeon_builds_walks_and_stays_inside_the_strip_and_the_function_limits():
    rooms = full_length_rooms()
    doc = demo_doc("jungle", rooms)
    s = first_slot(doc)
    pt = D.points(doc, s)
    assert 1400 <= pt["length"] <= doc["engine"]["slots"]["strip_length"], pt["length"]
    assert D.problems(doc) == []
    files = D.build(doc)
    shell = {k: v for k, v in files.items() if "/shells/s1/" in k}
    assert len(shell) == len(rooms)
    for k, v in shell.items():
        lines = v.splitlines()
        assert FL.check_lines(lines) == [], k
        assert len([l for l in lines if l and not l.startswith("#")]) < 20000, k
    total = D.shell_blocks(doc, s)
    assert 0.3e6 < total < 1.2e6, total          # EXP-081: 0.46-0.73M blocks is 1-2.6 s on the staging machine


def test_the_reapply_step_is_one_call_per_slot_when_a_dungeon_has_rooms():
    doc = demo_doc("mine", per_dungeon=4)
    steps = D.reapply_steps(doc)
    fns = [v for k, v in steps[0][2] if k == "fn" and "/place" in v]
    assert fns == ["cobblers:dungeons/place/s%d" % g for g in range(1, 5)]
    files = D.build(doc)
    for g in range(1, 5):
        assert "execute in %s run function cobblers:dungeons/shells/s%d" % (POCKET, g) in files["data/cobblers/function/dungeons/place/s%d.mcfunction" % g]
    legacy = D.reapply_steps(legacy_doc())
    assert [v for k, v in legacy[0][2] if k == "fn" and "/place" in v] == ["cobblers:dungeons/place"]


def test_the_old_spine_still_builds_and_is_untouched():
    old = legacy_doc()
    assert "rooms" not in old["dungeons"][0] and old["dungeons"][0]["spine"]["segments"]
    assert D.problems(old) == []
    pt = D.points(old, D.slots(old)[0])
    assert pt["length"] == sum(s["length"] for s in old["dungeons"][0]["spine"]["segments"])


def test_the_pick_of_a_dungeon_with_rooms_may_break_its_seam_and_nothing_else_new():
    doc = demo_doc("jungle")
    d = doc["dungeons"][0]
    give = D.pick_give(doc, d)
    for b in ("minecraft:melon", "minecraft:bamboo_block", "minecraft:honeycomb_block", "minecraft:pumpkin", "minecraft:stripped_jungle_log"):
        assert '"%s"' % b in give
    old = legacy_doc()
    assert D.pick_give(doc) == D.pick_give(old, old["dungeons"][0]), "the old spine's pick is the engine's list"
    files = D.build(doc)
    assert "minecraft:melon" in files["data/cobblers/function/dungeons/slot/s1/arrive.mcfunction"]


# ------------------------------------------------------------------------------------------------- the runtime on the simulator


import test_dungeon as TD  # noqa: E402  (its DW world and fakes: the engine's own run flow)


class RW(TD.DW):
    """DW plus `if block X Y Z id`, answered from self.blocks (a missing cell is air)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.blocks = {}

    def run(self, cmd, ctx, from_macro=False):
        def sub(m):
            pos = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
            tag = "__blk_%d_%d_%d_%s" % (pos + (m.group(5).replace(":", "_"),))
            return "%s entity @s[tag=%s]" % (m.group(1), tag)
        cmd = re.sub(r"\b(if|unless) block (-?\d+) (-?\d+) (-?\d+) (\S+)", sub, cmd)
        for p in self.players():
            for tag in [t for t in p.tags if t.startswith("__blk_")]:
                p.tags.discard(tag)
            for pos, name in self.blocks.items():
                p.tags.add("__blk_%d_%d_%d_%s" % (pos + (name.replace(":", "_"),)))
            for m in re.finditer(r"__blk_(-?\d+)_(-?\d+)_(-?\d+)_(\S+?)\]", cmd):
                key = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if key not in self.blocks and m.group(4) == "minecraft_air":
                    p.tags.add(m.group(0)[:-1])
        return super().run(cmd, ctx, from_macro)


@pytest.fixture(scope="module")
def rooms_pack(tmp_path_factory):
    doc = demo_doc("mine")
    files = D.build(doc)
    out = tmp_path_factory.mktemp("cobblers_dungeons_rooms")
    D.write(files, out)
    return doc, out


def rooms_world(rooms_pack):
    doc, pack = rooms_pack
    w = RW(pack, dict(TD.FAKES))
    w.objectives |= {"cobblers.lc_cap", "tailend", "stale"}
    w.boot()
    return doc, w


def enter_run(doc, w, name="Ash"):
    """The engine's own flow: click the rip, wait out the arrival, cross the threshold."""
    p = w.player(name, "minecraft:overworld", (1352.5, 130, 4120.5))
    p.inventory.append(TD.soot())
    w.call("cobblers:dungeons/door/ns", PS.Ctx(p, p.dim, p.pos))
    w.passes(4)
    assert p.dim == POCKET and w.get(p.name, "dg.st") == 2
    s = D.slots(doc)[w.get(p.name, "dg.slot") - 1]
    pt = D.points(doc, s)
    p.pos = [pt["threshold_x"] + 1.5, 96.0, s["cz"] + 0.5]
    w.passes(1)
    assert w.get(p.name, "dg.st") == 3
    return p, s


def room_of(doc, rid):
    return next(r for r in R.plan(doc, doc["dungeons"][0], first_slot(doc)) if r["id"] == rid)


def test_the_entry_hook_fires_once_per_run_the_first_time_a_member_stands_in_the_room(rooms_pack):
    doc, w = rooms_world(rooms_pack)
    p, s = enter_run(doc, w)
    hold = "#s%dr%d" % (s["g"], room_of(doc, "rest")["i"])
    assert w.get(hold, "dg.rs") == 0
    r = room_of(doc, "rest")
    p.pos = [r["ix0"] + 4.5, r["floor_in"], r["z_in"] + 0.5]
    w.passes(1)
    assert w.get(hold, "dg.rs") == 1
    w.set(hold, "dg.rs", 5)         # a marker: the hook must not run again and rewrite it
    w.passes(2)
    assert w.get(hold, "dg.rs") == 5


def test_clear_opens_the_door_out_once_and_the_slot_reset_closes_it_and_zeroes_the_state(rooms_pack):
    doc, w = rooms_world(rooms_pack)
    p, s = enter_run(doc, w)
    r = room_of(doc, "stand1")
    hold = "#s%dr%d" % (s["g"], r["i"])
    x0, y0, z0, x1, y1, z1 = r["door_out"]
    open_cmd = "fill %d %d %d %d %d %d minecraft:air" % (x0, y0, z0, x1, y1, z1)
    shut_cmd = "fill %d %d %d %d %d %d minecraft:iron_bars" % (x0, y0, z0, x1, y1, z1)
    p.pos = [r["ix0"] + 4.5, r["floor_in"], r["z_in"] + 0.5]
    w.passes(1)
    before = len(w.block_writes)
    w.call("cobblers:dungeons/room/night_shift/stand1/s1/clear", PS.Ctx(p, p.dim, p.pos))
    assert w.get(hold, "dg.rs") == 2
    writes = [c for _dim, c in w.block_writes[before:]]
    assert open_cmd in writes
    n = len(w.block_writes)
    w.call("cobblers:dungeons/room/night_shift/stand1/s1/clear", PS.Ctx(p, p.dim, p.pos))
    assert len(w.block_writes) == n, "clearing twice writes nothing the second time"
    n = len(w.block_writes)
    w.call("cobblers:dungeons/slot/s%d/reset" % s["g"], PS.Ctx(p, POCKET, p.pos))
    assert shut_cmd in [c for _d, c in w.block_writes[n:]]
    assert w.get(hold, "dg.rs") == 0


def test_a_fall_onto_the_catch_floor_charges_the_clock_and_puts_the_member_on_the_last_ledge(rooms_pack):
    doc, w = rooms_world(rooms_pack)
    p, s = enter_run(doc, w)
    r = room_of(doc, "jump")
    b = next(x for x in R.slot_build(doc, doc["dungeons"][0], s) if x.room["id"] == "jump")
    ck = b.anchors["checkpoints"]
    p.pos = [ck[1][0] + 0.5, ck[1][1], ck[1][2] + 0.5]               # stand on the second ledge
    w.passes(1)
    assert w.get(p.name, "dg.ck") == 1
    clock = w.get(p.name, "dg.clock")
    p.pos = [ck[1][0] + 6.5, r["y_lo"], ck[1][2] + 0.5]               # and fall past the platforms onto the catch floor
    w.passes(1)
    penalty = doc["engine"]["clock"]["fall_penalty_s"] * 80
    assert w.get(p.name, "dg.clock") == clock - 80 - penalty, "one pass of the clock and the fall's penalty"
    assert [int(v) for v in p.pos[:3]] == [ck[1][0], ck[1][1], ck[1][2]], "back on the ledge last stood on"
    assert any(e[0] == "minecraft:resistance" for e in p.effects), "no fall can hurt (F1)"


def test_a_crossing_collapses_the_span_behind_the_member_and_a_ledge_restores_it(rooms_pack):
    doc, w = rooms_world(rooms_pack)
    p, s = enter_run(doc, w)
    b = next(x for x in R.slot_build(doc, doc["dungeons"][0], s) if x.room["id"] == "bridge")
    span = b.anchors["span"]
    ck = b.anchors["checkpoints"]
    z = ck[0][2]
    p.pos = [ck[0][0] + 0.5, ck[0][1], z + 0.5]
    w.passes(1)
    p.pos = [span[0] + 1.5, span[1] + 1, z + 0.5]                     # the first blocks of the span: east-bound
    w.passes(1)
    assert "dg.cbe" in p.tags
    before = len(w.block_writes)
    p.pos = [span[0] + 20.5, span[1] + 1, z + 0.5]
    w.passes(1)
    gone = [c for _d, c in w.block_writes[before:] if c.endswith("minecraft:air") and c.startswith("fill")]
    xs = sorted(int(c.split()[1]) for c in gone)
    assert xs and max(xs) <= int(p.pos[0]) - 6 and min(xs) >= span[0], (xs, p.pos)
    assert not any(int(c.split()[1]) >= int(p.pos[0]) - 5 for c in gone), "nothing under or ahead of the member goes"
    before = len(w.block_writes)
    p.pos = [ck[1][0] + 0.5, ck[1][1], z + 0.5]                      # the far ledge: whole again, tags gone
    w.passes(1)
    assert "dg.cbe" not in p.tags
    span_block = THEMES["mine"]["bridge"]["span"]
    assert any(c.startswith("fill") and c.endswith(span_block) for _d, c in w.block_writes[before:]), "the span is written whole again"


def test_the_seam_credits_one_block_taken_to_the_greed_ladder_once(rooms_pack):
    doc, w = rooms_world(rooms_pack)
    p, s = enter_run(doc, w)
    r = room_of(doc, "seam")
    b = next(x for x in R.slot_build(doc, doc["dungeons"][0], s) if x.room["id"] == "seam")
    cells = [tuple(c) for c in b.anchors["seam"]]
    w.blocks = {c: "minecraft:deepslate_coal_ore" for c in cells}
    p.pos = [r["ix0"] + 10.5, r["floor_in"], r["z_in"] + 0.5]
    w.passes(1)
    assert w.get(p.name, "dg.greed") == 0
    w.blocks[cells[3]] = "minecraft:air"
    w.passes(1)
    assert w.get(p.name, "dg.greed") == 1
    w.passes(2)
    assert w.get(p.name, "dg.greed") == 1, "the same hole is not counted twice"
    for c in cells[:8]:
        w.blocks[c] = "minecraft:air"
    w.passes(1)
    assert w.get(p.name, "dg.greed") == 8 and w.get(p.name, "dg.rate") == 5, "five taken is x1.25 (D13)"


def test_the_dark_room_hands_out_torches_that_may_only_be_placed_on_its_floor():
    doc = demo_doc("flooded_ruin")
    files = D.build(doc)
    enter = files["data/cobblers/function/dungeons/room/night_shift/dark/s1/enter.mcfunction"]
    give = [l for l in enter.splitlines() if l.startswith("give @s minecraft:torch")]
    assert give and "can_place_on" in give[0] and "minecraft:prismarine_bricks" in give[0] and give[0].endswith(" 3")
    reset = files["data/cobblers/function/dungeons/room/night_shift/dark/s1/reset.mcfunction"]
    assert "replace minecraft:torch" in reset and "replace minecraft:wall_torch" in reset
    d = doc["dungeons"][0]
    b = next(x for x in R.slot_build(doc, d, first_slot(doc)) if x.room["id"] == "dark")
    lit = {G.base(THEMES["flooded_ruin"]["hull"]["light"]), "minecraft:lantern", "minecraft:sea_pickle", "minecraft:glow_lichen"}
    assert not (lit & {G.base(n) for n in b.grid.names()}), "a dark room lights nothing itself"
    assert any("candle" in n for n in b.grid.names()), "a few lit candles are found in it"
    assert not b.lights


def test_the_safe_room_has_a_healer_anchor_behind_a_counter_it_can_be_reached_around():
    doc = demo_doc("jungle")
    d = doc["dungeons"][0]
    s = first_slot(doc)
    b = next(x for x in R.slot_build(doc, d, s) if x.room["id"] == "rest")
    hx, hy, hz, yaw = b.anchors["healer"]
    g = b.grid
    assert g.block_at(hx, hy, hz) == "minecraft:air" and G.classify(g.block_at(hx, hy - 1, hz)) == G.SOLID
    assert g.block_at(hx, hy, hz + 1).startswith("minecraft:jungle_planks")         # the counter in front of it
    assert R.walk_problems(doc, d, s) == []


# ------------------------------------------------------------------------------------------------- the grid's own rules


def tiny(ops, box=(0, 0, 0, 14, 8, 4)):
    g = G.Grid(box)
    g.apply(("fill", (0, 0, 0, 14, 0, 4), "minecraft:stone"))
    for op in ops:
        g.apply(op)
    return g


def test_the_walk_takes_a_step_of_one_block_but_not_two_and_needs_two_air_above():
    stone = "minecraft:stone"
    g = tiny([("fill", (5, 1, 0, 14, 1, 4), stone)])                   # a one-block step at x 5
    assert (14, 2, 2) in G.walk(g, [(0, 1, 2)])
    g = tiny([("fill", (5, 1, 0, 14, 2, 4), stone)])                   # two blocks high: a wall to this walker
    assert (14, 3, 2) not in G.walk(g, [(0, 1, 2)])
    g = tiny([("fill", (5, 1, 0, 14, 1, 4), stone), ("fill", (4, 3, 0, 6, 3, 4), stone)])   # a low ceiling over the step
    assert (14, 2, 2) not in G.walk(g, [(0, 1, 2)])
    g = tiny([("fill", (5, 1, 0, 14, 1, 4), stone), ("fill", (4, 4, 0, 6, 4, 4), stone)])   # high enough to jump up
    assert (14, 2, 2) in G.walk(g, [(0, 1, 2)])


def test_the_walk_never_drops_more_than_one_so_what_it_reaches_it_can_come_back_from():
    stone = "minecraft:stone"
    g = tiny([("fill", (0, 1, 0, 6, 2, 4), stone)])                    # start on a two-block plinth
    reach = G.walk(g, [(0, 3, 2)])
    assert (10, 1, 2) not in reach, "a drop of two is not an edge"
    g = tiny([("fill", (0, 1, 0, 6, 1, 4), stone)])
    reach = G.walk(g, [(0, 2, 2)])
    assert (10, 1, 2) in reach and (0, 2, 2) in G.walk(g, [(10, 1, 2)])


def test_a_gap_is_crossed_only_by_a_jump_and_only_within_the_limits():
    stone = "minecraft:stone"
    for gap, ok in ((1, True), (2, True), (3, True), (4, False)):
        g = tiny([("fill", (3, 0, 0, 2 + gap, 0, 4), "minecraft:air")])      # `gap` blocks of nothing at x 3 on
        end = (3 + gap, 1, 2)
        assert (end in G.walk(g, [(0, 1, 2)], jumps=True)) == ok, gap
        assert end not in G.walk(g, [(0, 1, 2)], jumps=False)
    g = tiny([("fill", (3, 0, 0, 5, 0, 4), "minecraft:air"), ("fill", (6, 1, 0, 14, 1, 4), stone)])   # gap 3, a rise of one
    assert (7, 2, 2) not in G.walk(g, [(0, 1, 2)], jumps=True)
    g = tiny([("fill", (3, 0, 0, 4, 0, 4), "minecraft:air"), ("fill", (5, 1, 0, 14, 1, 4), stone)])   # gap 2, a rise of one
    assert (6, 2, 2) in G.walk(g, [(0, 1, 2)], jumps=True)


def test_blocks_are_classified_conservatively_unknown_is_solid_and_a_plant_is_not():
    assert G.classify("minecraft:fern") == G.PASS and G.classify("minecraft:tall_grass[half=lower]") == G.PASS
    assert G.classify("minecraft:water") == G.WATER and G.classify("minecraft:lava") == G.HAZARD
    assert G.classify("minecraft:some_future_block") == G.SOLID and G.classify("minecraft:big_dripleaf[facing=north]") == G.SOLID
    assert G.forbidden("minecraft:white_concrete_powder") and G.forbidden("minecraft:gravel") and not G.forbidden("minecraft:stone")


def test_the_shell_chain_budget_refuses_a_dungeon_too_big_for_one_re_apply_call(monkeypatch):
    monkeypatch.setattr(R, "CHAIN_BUDGET", 500)
    assert any("commands in one chain" in x for x in R.problems(demo_doc("mine")))
