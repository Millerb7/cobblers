"""The fight rooms: stand, gauntlet/ambush, miniboss, nest, habitat and the safe room's healer (tools/dungeon_fights.py,
unit DG-FIGHTS, 2026-10-09). The builder's own tests; an independent author should extend them.

  static     the fixture (tests/fixtures/dungeon_fights_rooms.json: one of each kind, written the way the three
             dungeons will write them) has no problems in any theme; levels are read back from the built functions and
             compared with data/dungeons.json's bands, parsed here and not through the generator; every wild spawn is a
             macro line and is bound with the keep tag; the dispatch maps every stand id; no healing machine in a shell;
  runtime    the generated functions driven on tests/pocket_sim.py through the engine's keeper (enter once, a stand's
             trainers one after another, a forfeit offered again, the ambush's barrier up and down, a wild room clearing
             only after two absent passes, a failed spawn opening anyway, the healer healing once and never in battle,
             the run's end discarding what it summoned);
  mutation   the GENERATOR is edited in memory and the data left alone ("How to prove an audit is independent").

Not covered, needs a server: that a fainted wild Pokemon's entity is removed (the clear rule), that `no_ai` keeps a
battle startable, that any_block_use fires for a bell in adventure mode, `healpokemon` in the pocket restoring PP,
the callback and the clawback of a stand (DG-CLAW's, unrun).
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_clock as DC  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import pocket_sim as PS  # noqa: E402
import test_dungeon as TD  # noqa: E402
import test_dungeon_rooms as TR  # noqa: E402

FIX = json.loads((ROOT / "tests" / "fixtures" / "dungeon_fights_rooms.json").read_text(encoding="utf-8"))["rooms"]
DEMO = json.loads((ROOT / "tests" / "fixtures" / "dungeon_demo_rooms.json").read_text(encoding="utf-8"))["rooms"]
BASE = D.load()
DATA = json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))   # the bands, read again here
BANDS = {b["band"]: b["caps"] for b in DATA["engine"]["bands"]}
POCKET = DATA["engine"]["pocket"]["dimension"]
KEEP = DATA["engine"]["sweep"]["keep_tag"]
FN = "data/cobblers/function/dungeons/"
THEMES = ("mine", "jungle", "flooded_ruin")


def fights_doc(theme="mine", rooms=None):
    doc = copy.deepcopy(BASE)
    d = doc["dungeons"][0]
    d["theme"] = theme
    d["rooms"] = copy.deepcopy(rooms if rooms is not None else FIX)
    d.pop("spine", None)                # night_shift has been a rooms dungeon since the full-length rebuild
    doc["dungeons"] = [d]               # the fixture is one dungeon's slot 1; the other dungeons are their own tests'
    doc["engine"]["slots"]["per_dungeon"] = 1
    # a rooms dungeon carries the clock derived from ITS rooms (DUNGEON_ROOMS.md 7); night_shift's own clock is for its
    # 21 rooms, not the fixture's, and problems() rightly refuses it here
    try:
        d["clock_s_by_band"] = DC.derive(doc, d)
    except R.RoomError:
        d.pop("clock_s_by_band", None)  # rooms that cannot build have no clock; problems() names the room's fault
    return doc


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def fn_text(files, name):
    return files[FN + name + ".mcfunction"]


def ex(room_id, slot, name):
    return "room/night_shift/%s/s%d/%s" % (room_id, slot, name)


# ------------------------------------------------------------------------------------------------- static


@pytest.mark.parametrize("theme", THEMES)
def test_the_fixture_has_no_problems_and_every_kind_is_registered(theme):
    doc = fights_doc(theme)
    assert D.problems(doc) == []
    assert {"stand", "gauntlet", "ambush", "miniboss", "nest", "habitat"} <= set(R.KINDS)
    assert R.warnings(doc) == [] and DF.warnings(doc) == []


@pytest.mark.parametrize("theme", THEMES)
def test_trainers_lines_barriers_and_creatures_sit_on_reachable_open_floor_the_walk_check_proves(theme):
    doc = fights_doc(theme)
    s = D.slots(doc)[0]
    for b in R.slot_build(doc, doc["dungeons"][0], s):
        r = b.room
        if r["kind"] in ("stand", "gauntlet"):
            assert len(b.anchors["trainers"]) == len(r["params"]["trainers"])
        if r["kind"] == "gauntlet":
            plan = b.meta["fight_plan"]
            for bx, (tx, _tz) in zip(plan["barriers"], plan["trainers"]):
                assert r["ix0"] + 8 <= bx < tx <= r["ix1"] - 3, "the barrier sits well inside the room and ahead of its trainer"
        if r["kind"] == "nest":
            assert len(b.anchors["spawns"]) == 6


def test_the_demo_placeholders_of_the_kit_still_build_and_warn_and_behave_as_the_declared_kinds_did():
    doc = TR.demo_doc("mine")
    assert D.problems(doc) == []
    w = DF.warnings(doc)
    assert any("stand1" in m for m in w) and any("hab" in m for m in w) and any("nest" in m for m in w), w
    files = D.build(doc)
    assert not any("ns_stand1" in k for k in files), "no trainers, no classes: a placeholder is a themed empty room"
    assert not any("/wild_at" in k or "/wild/" in k for k in files)


def level_of(props):
    return int(re.search(r"level=(\d+)", props).group(1))


def spawn_lines(files, room_id):
    out = {}
    for b in range(1, 7):
        t = fn_text(files, ex(room_id, 1, "spawn_b%d" % b))
        out[b] = [m for m in re.findall(r"wild_at \{([^}]*)\}", t)]
    return out


def test_wild_levels_are_read_from_the_bands_never_above_the_upper_cap_and_band_6_is_95_to_100():
    files = D.build(fights_doc("mine"))
    mini = spawn_lines(files, "mini1")
    hab = spawn_lines(files, "hab1")
    nest = spawn_lines(files, "nest1")
    for b, caps in BANDS.items():
        up = max(caps)
        lv = [level_of(l) for l in mini[b]]
        assert lv == [up - 1], (b, lv)                                  # level_offset -1 in the fixture
        assert [level_of(l) for l in hab[b]] == [int(next(r for r in FIX if r["id"] == "hab1")["params"]["level_by_band"][str(b)])]
        assert all(1 <= level_of(l) <= up for l in nest[b]), (b, nest[b])
        lo, hi = next(r for r in FIX if r["id"] == "nest1")["params"]["level_spread"]
        if b < 6:                                                       # band 6 is lifted to 95-100 (below)
            assert all(up - hi <= level_of(l) <= up - lo for l in nest[b]), (b, nest[b])
    assert 95 <= level_of(mini[6][0]) <= 100 and 95 <= level_of(nest[6][0]) <= 100


def test_every_wild_spawn_is_a_macro_line_bound_in_the_same_function_with_the_keep_tag():
    files = D.build(fights_doc("mine"))
    for room in ("mini1", "nest1", "hab1"):
        for b in range(1, 7):
            t = [l for l in fn_text(files, ex(room, 1, "spawn_b%d" % b)).splitlines() if l and not l.startswith("#")]
            assert t and len(t) % 2 == 0
            for spawn, bind in zip(t[0::2], t[1::2]):
                assert "function cobblers:dungeons/wild_at {" in spawn and "spawnpokemonat" not in spawn
                assert "as @e[type=cobblemon:pokemon,tag=!%s,distance=" % KEEP in bind and bind.endswith("/s1/bind")
    macro = fn_text(files, "wild_at")
    assert "\n$spawnpokemonat $(x) $(y) $(z) $(species) $(props)" in macro
    assert not any("spawnpokemonat" in l for k, v in files.items() if k.startswith(FN) and not k.endswith("wild_at.mcfunction")
                   for l in v.splitlines() if l and not l.startswith("#") and not l.startswith("$"))
    bind = fn_text(files, "wild/s1/bind")
    exempt = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))["claims"]["exempt_tag"]
    for tag in (KEEP, "dg.s1", exempt):
        assert "tag @s add %s" % tag in bind
    assert "PersistenceRequired:1b" in bind and "dg.run = #s1 dg.run" in bind


def test_catching_follows_the_owners_rule_every_pokemon_and_a_legendary_from_the_beast_ball_band():
    # the owner, 2026-10-10 (replacing D8's "catches only after the Champion" for dungeon Pokemon): nests and
    # mini-bosses are catchable at every band unless the record says not; a habitat's legendary is a prize, catchable
    # from engine.prize.legendary_from_band on unless the record is fight_only
    lf = D.load()["engine"]["prize"]["legendary_from_band"]
    files = D.build(fights_doc("mine"))                       # the fixture's habitat is fight_only
    for room in ("mini1", "nest1"):
        for b, ls in spawn_lines(files, room).items():
            assert not any("uncatchable" in l for l in ls), (room, b)
    assert all("uncatchable" in l for ls in spawn_lines(files, "hab1").values() for l in ls)
    rooms = copy.deepcopy(FIX)
    next(r for r in rooms if r["id"] == "mini1")["params"]["catchable"] = False
    next(r for r in rooms if r["id"] == "hab1")["params"]["fight_only"] = False
    files = D.build(fights_doc("mine", rooms))
    assert all("uncatchable" in l for ls in spawn_lines(files, "mini1").values() for l in ls)
    ls = spawn_lines(files, "hab1")
    assert all("uncatchable" in l for b in range(1, lf) for l in ls[b])
    assert not any("uncatchable" in l for b in range(lf, 7) for l in ls[b])


def test_a_stand_id_is_unique_and_dispatched_to_its_trainers_won_function_and_every_class_file_exists():
    doc = fights_doc("mine")
    files = D.build(doc)
    disp = [l for l in fn_text(files, "stand/dispatch").splitlines() if l.startswith("execute")]
    sids = [int(re.search(r"matches (\d+)", l).group(1)) for l in disp]
    assert len(sids) == len(set(sids)) == 5, sids                       # 2 + 3 trainers
    for l in disp:
        name = re.search(r"function cobblers:dungeons/(\S+)", l).group(1)
        assert FN + name + ".mcfunction" in files, name
    for n in range(1, 3):
        for b in range(1, 7):
            assert "data/cobblers/npcs/dg_ns_st_stand1_t%d_b%d.json" % (n, b) in files
    for n in range(1, 4):
        for b in range(1, 7):
            assert "data/cobblers/npcs/dg_ns_st_ambush1_t%d_b%d.json" % (n, b) in files


@pytest.mark.parametrize("theme", THEMES)
def test_no_shell_holds_a_healing_machine_and_the_healer_is_a_bell_in_the_pocket_only(theme):
    doc = fights_doc(theme)
    files = D.build(doc)
    shell = "\n".join(v for k, v in files.items() if "/shells/" in k)
    assert "healing_machine" not in shell and "minecraft:bell[attachment=floor,facing=north]" in shell
    adv = json.loads(files["data/cobblers/advancement/dungeons/healer.json"])
    cond = adv["criteria"]["use"]["conditions"]["location"][0]["predicate"]
    assert cond["block"]["blocks"] == "minecraft:bell" and cond["dimension"] == POCKET
    assert adv["rewards"]["function"] == "cobblers:dungeons/healer/use"
    use = fn_text(files, "healer/use")
    assert "advancement revoke @s only cobblers:dungeons/healer" in use and "dg.st matches 3" in use


def test_bad_params_are_problems_not_traps():
    def bad(mutate):
        rooms = copy.deepcopy(FIX)
        mutate({r["id"]: r for r in rooms})
        return D.problems(fights_doc("mine", rooms))
    assert any("upper cap" in p for p in bad(lambda r: r["hab1"]["params"]["level_by_band"].update({"1": 26})))
    assert any("level_offset" in p for p in bad(lambda r: r["mini1"]["params"].update({"level_offset": 2})))
    assert any("band 3" in p for p in bad(lambda r: r["mini1"]["params"]["species_by_band"].pop("3")))
    assert any("increasing" in p for p in bad(lambda r: r["ambush1"]["params"].update({"triggers": [0.4, 0.2, 0.7]})))
    assert any("apart" in p for p in bad(lambda r: r["ambush1"]["params"].update({"triggers": [0.2, 0.3, 0.4]})))
    assert any("members" in p for p in bad(lambda r: r["stand1"]["params"]["trainers"][0]["team_by_band"].update({"1": ["geodude"]})))
    assert any("catchable nest" in p for p in bad(lambda r: r["nest1"]["params"].update({"catchable": True, "level_spread": [0, 3]})))
    assert any("uses" in p for p in bad(lambda r: r["rest1"]["params"].update({"uses": 0})))
    assert any("outside the room" in p for p in bad(lambda r: r["ambush1"].update({"length": 44})))
    assert any("band-6" in p for p in bad(lambda r: r["mini1"]["params"].update({"level_offset": -6})))


# ------------------------------------------------------------------------------------------------- mutation of the generator


def test_mutating_the_cap_in_the_generator_is_caught_by_the_level_check_that_reads_the_data(monkeypatch):
    monkeypatch.setattr(DF, "upper_cap", lambda b: max(b["caps"]) + 4)
    rooms = copy.deepcopy(FIX)       # the nest fight-only, so the catchable nest's own cap check does not refuse first
    next(r for r in rooms if r["id"] == "nest1")["params"]["catchable"] = False
    files = D.build(fights_doc("mine", rooms))
    mini = spawn_lines(files, "mini1")
    over = [b for b, caps in BANDS.items() if level_of(mini[b][0]) > max(caps)]
    assert over, "a generator that reads the cap wrong must put a level over the band's upper cap"


def test_mutating_the_keep_tag_in_the_generator_is_caught_by_the_sweep_check(monkeypatch):
    monkeypatch.setattr(DF, "keep_tag", lambda doc: "dg.nokeep")
    files = D.build(fights_doc("mine"))
    assert "tag @s add %s" % KEEP not in fn_text(files, "wild/s1/bind")


def test_mutating_the_ambush_stride_pushes_a_trainer_out_of_the_room_and_the_plan_check_says_so(monkeypatch):
    monkeypatch.setattr(DF, "AMBUSH_STEP", 60)
    assert any("outside the room" in p for p in D.problems(fights_doc("mine")))


# ------------------------------------------------------------------------------------------------- runtime


class FW(TR.RW):
    """RW plus `healpokemon`, a wild spawn that can be made to fail, and the pocket's spawned Pokemon."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.healed = []
        self.no_spawn = False

    def run_tokens(self, t, ctx, from_macro=False, raw=None):
        if t[0] == "healpokemon":
            self.healed.append(ctx.ent.name)
            return 1
        if t[0] == "spawnpokemonat" and self.no_spawn:
            return 0
        return super().run_tokens(t, ctx, from_macro, raw)


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    doc = fights_doc("mine")
    out = tmp_path_factory.mktemp("dg_fight_rooms")
    D.write(D.build(doc), out)
    return doc, out


def world(pack):
    doc, out = pack
    w = FW(out, dict(TD.FAKES))
    w.objectives |= {"cobblers.lc_cap", "tailend", "stale"}
    w.boot()
    return doc, w


def go(doc, w, room_id, band=1, name="Ash"):
    p, s = TR.enter_run(doc, w, name)
    w.set(p.name, "dg.band", band)
    return p, s, TR.room_of(doc, room_id)


def stand_at(w, p, r, x):
    p.pos = [x + 0.5, r["floor_in"], r["z_in"] + 0.5]


def hold(s, r, suffix=""):
    return "#s%dr%d%s" % (s["g"], r["i"], suffix)


def npcs(w, cls=None):
    return [e for e in w.ents if e.kind == "cobblemon:npc" and e.alive and (cls is None or e.nbt.get("NPCClass", "").endswith(cls))]


def mons(w, tag=None):
    return [e for e in w.ents if e.kind == "cobblemon:pokemon" and e.alive and (tag is None or tag in e.tags)]


def win(w, p, npc):
    w.run_callback("battle_victory", context={
        "scriptable_losers": [{"is_npc": 1, "uuid": npc.uid}], "player_winners": [{"player": {"username": p.name}}],
        "scriptable_winners": [], "player_losers": []})


def test_a_stand_seats_both_trainers_at_the_first_pass_and_fights_them_one_after_another(pack):
    doc, w = world(pack)
    p, s, r = go(doc, w, "stand1")
    plan = DF.fight_plan(doc, R.layout(doc, doc["dungeons"][0], s)[2])
    assert r["kind"] == "stand" and plan["n"] == 2
    stand_at(w, p, r, r["ix0"] + 4)
    w.passes(1)
    assert len(npcs(w)) == 2 and not w.started, "both stand visible and no fight begins before a line"
    assert w.get(hold(s, r), "dg.rs") == 1
    stand_at(w, p, r, plan["trips"][0] + 1)
    w.passes(2)
    assert w.get(hold(s, r, "t1"), "dg.rs") == 1 and len(w.started) == 1
    assert w.get(hold(s, r, "t2"), "dg.rs") == 0, "the second trainer waits for the first"
    stand_at(w, p, r, plan["trips"][1] + 1)
    w.passes(2)
    assert len(w.started) == 1 and w.get(hold(s, r, "t2"), "dg.rs") == 0, "past the second line, still the first fight"
    first = next(e for e in npcs(w) if "dg.stk.ns_stand1_t1_s1" in e.tags)
    win(w, p, first)
    assert w.get(hold(s, r, "t1"), "dg.rs") == 2 and w.get(hold(s, r), "dg.rs") == 1, "one beaten is not the room cleared"
    w.passes(2)
    assert w.get(hold(s, r, "t2"), "dg.rs") == 1 and len(w.started) == 2
    second = next(e for e in npcs(w) if "dg.stk.ns_stand1_t2_s1" in e.tags)
    n = len(w.block_writes)
    win(w, p, second)
    assert w.get(hold(s, r), "dg.rs") == 2
    x0, y0, z0, x1, y1, z1 = r["door_out"]
    assert "fill %d %d %d %d %d %d minecraft:air" % (x0, y0, z0, x1, y1, z1) in [c for _d, c in w.block_writes[n:]]


def test_a_forfeited_fight_is_offered_again_after_four_passes_out_of_battle_and_not_while_in_one(pack):
    doc, w = world(pack)
    p, s, r = go(doc, w, "stand1")
    plan = DF.fight_plan(doc, R.layout(doc, doc["dungeons"][0], s)[2])
    stand_at(w, p, r, r["ix0"] + 4)
    w.passes(1)
    stand_at(w, p, r, plan["trips"][0] + 1)
    w.passes(1)
    w.in_battle.add(p.name)
    w.passes(6)
    assert w.get(hold(s, r, "t1"), "dg.rs") == 1 and len(w.started) == 1, "in battle: nothing is offered again"
    w.in_battle.discard(p.name)
    w.passes(6)
    assert len(w.started) >= 2, "after the forfeit the trainer fights again while the member stands past the line"


def test_a_reset_removes_the_trainers_and_zeroes_the_stand(pack):
    doc, w = world(pack)
    p, s, r = go(doc, w, "stand1")
    stand_at(w, p, r, r["ix0"] + 4)
    w.passes(1)
    assert len(npcs(w)) == 2
    w.call("cobblers:dungeons/slot/s%d/reset" % s["g"], PS.Ctx(p, POCKET, p.pos))
    assert not npcs(w) and w.get(hold(s, r, "t1"), "dg.rs") == 0 and w.get(hold(s, r), "dg.rs") == 0


def test_the_gauntlet_hides_its_trainers_raises_a_barrier_at_the_trigger_and_lowers_it_on_the_win(pack):
    doc, w = world(pack)
    p, s, r = go(doc, w, "ambush1")
    plan = DF.fight_plan(doc, R.layout(doc, doc["dungeons"][0], s)[4])
    stand_at(w, p, r, r["ix0"] + 4)
    w.passes(1)
    assert not npcs(w), "an ambush is not seen before it springs"
    bx = plan["barriers"][0]
    bar = [c for _d, c in w.block_writes if re.match(r"fill %d \d+ \d+ %d" % (bx, bx), c)]
    n = len(w.block_writes)
    stand_at(w, p, r, plan["trips"][0] + 1)
    w.passes(2)
    writes = [c for _d, c in w.block_writes[n:]]
    # the barrier fills AIR only (DG-AUDIT finding 3: over every block it destroyed the room's lanterns and canopy)
    shut = [c for c in writes if re.match(r"fill %d \d+ \d+ %d \d+ \d+ minecraft:iron_bars replace minecraft:air$" % (bx, bx), c)]
    assert shut, writes
    assert len(npcs(w)) == 1 and len(w.started) == 1
    stand_at(w, p, r, bx + 3)                                           # past the barrier while it stands
    w.passes(1)
    assert p.pos[0] < bx, "a member found past the barrier is put back before it"
    door_in = r["door_in"]
    assert not any(re.match(r"fill %d " % door_in[0], c) or re.match(r"fill %d " % door_in[3], c) for c in shut), "the way back stays open"
    n = len(w.block_writes)
    win(w, p, npcs(w)[0])
    assert any(c.startswith("fill %d " % bx) and "minecraft:air replace minecraft:iron_bars" in c for _d, c in w.block_writes[n:])
    assert w.get(hold(s, r, "t1"), "dg.rs") == 2 and w.get(hold(s, r), "dg.rs") == 1


def test_the_gauntlet_clears_after_the_third_trainer_in_order(pack):
    doc, w = world(pack)
    p, s, r = go(doc, w, "ambush1")
    plan = DF.fight_plan(doc, R.layout(doc, doc["dungeons"][0], s)[4])
    stand_at(w, p, r, r["ix0"] + 4)
    w.passes(1)
    for k in range(3):
        stand_at(w, p, r, plan["trips"][k] + 1)
        w.passes(2)
        assert len(w.started) == k + 1 and w.get(hold(s, r), "dg.rs") == 1
        win(w, p, npcs(w)[-1])
        w.passes(1)
    assert w.get(hold(s, r), "dg.rs") == 2


def test_a_miniboss_spawns_once_clears_only_after_two_absent_passes_and_is_not_a_gate_while_it_stands(pack):
    doc, w = world(pack)
    p, s, r = go(doc, w, "mini1")
    stand_at(w, p, r, r["ix0"] + 4)
    w.passes(1)
    ms = mons(w, "dg.r.mini1")
    assert len(ms) == 1 and KEEP in ms[0].tags and "dg.s1" in ms[0].tags
    assert "level=24" in " ".join(ms[0].props) and "uncatchable" not in ms[0].props and "no_ai" in ms[0].props
    w.passes(3)
    assert len(mons(w, "dg.r.mini1")) == 1 and w.get(hold(s, r), "dg.rs") == 1, "alive: still guarding, not respawned"
    ms[0].alive = False                                                  # it faints in a battle
    w.passes(1)
    assert w.get(hold(s, r), "dg.rs") == 1, "one absent pass is a slow load, not a faint"
    w.passes(1)
    assert w.get(hold(s, r), "dg.rs") == 2


def test_a_room_whose_pokemon_never_appears_opens_anyway_with_a_message(pack):
    doc, w = world(pack)
    p, s, r = go(doc, w, "mini1")
    w.no_spawn = True
    stand_at(w, p, r, r["ix0"] + 4)
    w.passes(3)
    assert w.get(hold(s, r), "dg.rs") == 1
    w.passes(4)
    assert w.get(hold(s, r), "dg.rs") == 2, "a bad species id must never trap a player"


def test_a_band_6_run_meets_a_level_95_to_100_creature_and_a_nest_that_stays_in_its_room(pack):
    doc, w = world(pack)
    p, s, r = go(doc, w, "nest1", band=6)
    stand_at(w, p, r, r["ix0"] + 4)
    w.passes(1)
    ns = mons(w, "dg.r.nest1")
    assert len(ns) == 6 and all(95 <= level_of(" ".join(m.props)) <= 100 for m in ns)
    assert all("no_ai" not in m.props and "uncatchable" not in m.props for m in ns), \
        "a nest wanders and is catchable unless it says not (the owner, 2026-10-10)"
    assert w.catch(p, ns[0])
    ns[1].pos = [r["ix1"] + 40.0, 96.0, r["z_in"] + 0.5]                  # wandered out of the room
    w.passes(1)
    assert r["ix0"] <= ns[1].pos[0] <= r["ix1"], "the tick leashes a wanderer back"
    for m in ns[:5]:
        m.alive = False
    w.passes(3)
    assert w.get(hold(s, r), "dg.rs") == 1, "one left standing: the nest is not over"
    ns[5].alive = False
    w.passes(2)
    assert w.get(hold(s, r), "dg.rs") == 2


def test_a_nest_that_only_passes_clears_at_once(pack):
    rooms = copy.deepcopy(FIX)
    next(r for r in rooms if r["id"] == "nest1")["params"]["clear"] = "pass"
    next(r for r in rooms if r["id"] == "nest1")["gate"] = "cleared"
    doc = fights_doc("mine", rooms)
    R._BUILT.clear()
    files = D.build(doc)
    assert "nest1/s1/clear" in fn_text(files, ex("nest1", 1, "enter"))
    assert "wild_at" in fn_text(files, ex("nest1", 1, "spawn_b1")), "it still spawns: the nest is a hazard"


def test_the_habitat_shows_its_creature_from_the_viewpoint_once_and_clears_when_it_is_gone(pack):
    doc, w = world(pack)
    p, s, r = go(doc, w, "hab1", band=6)
    stand_at(w, p, r, r["ix0"] + 1)
    w.passes(1)
    ms = mons(w, "dg.r.hab1")
    assert len(ms) == 1 and "level=100" in " ".join(ms[0].props) and "uncatchable" in ms[0].props
    b = next(x for x in R.slot_build(doc, doc["dungeons"][0], s) if x.room["id"] == "hab1")
    vx, vy, vz = b.anchors["viewpoint"][:3]
    p.pos = [vx + 0.5, float(vy), vz + 0.5]
    n = len(w.titles)
    w.passes(1)
    assert len(w.titles) > n and w.get(hold(s, r, "v"), "dg.rs") == 1
    n = len(w.titles)
    w.passes(2)
    assert len(w.titles) == n or all("Volcanion" not in t for _, t in w.titles[n:]), "the title shows once"
    ms[0].alive = False
    w.passes(3)
    assert w.get(hold(s, r), "dg.rs") == 2


def test_the_healer_heals_once_never_in_battle_never_outside_the_room_and_a_reset_restores_it(pack):
    doc, w = world(pack)
    p, s, r = go(doc, w, "rest1")
    use = lambda: w.call("cobblers:dungeons/healer/use", PS.Ctx(p, POCKET, p.pos))  # noqa: E731
    stand_at(w, p, r, r["ix0"] + 4)
    w.passes(1)
    w.in_battle.add(p.name)
    use()
    w.drain()
    assert w.healed == [], "not in battle"
    w.in_battle.discard(p.name)
    use()
    w.drain()
    assert w.healed == [p.name] and w.get(hold(s, r, "h"), "dg.rs") == 1
    use()
    w.drain()
    assert w.healed == [p.name], "the bell has rung for this run"
    w.call("cobblers:dungeons/slot/s%d/reset" % s["g"], PS.Ctx(p, POCKET, p.pos))
    assert w.get(hold(s, r, "h"), "dg.rs") == 0
    q = TR.room_of(doc, "mini1")
    p.pos = [q["ix0"] + 4.5, q["floor_in"], q["z_in"] + 0.5]
    use()
    w.drain()
    assert w.healed == [p.name], "a bell rung outside a healer room heals nothing"


def test_the_runs_end_discards_what_the_run_summoned_and_a_stale_run_is_discarded_by_the_keeper(pack):
    doc, w = world(pack)
    p, s, r = go(doc, w, "nest1")
    stand_at(w, p, r, r["ix0"] + 4)
    w.passes(1)
    ns = mons(w, "dg.r.nest1")
    assert ns and all(w.get(m.holder, "dg.run") == w.get("#s%d" % s["g"], "dg.run") for m in ns)
    w.set(ns[0].holder, "dg.run", 999)                                    # left by an earlier run of the slot
    w.passes(1)
    assert not ns[0].alive and all(m.alive for m in ns[1:])
    w.call("cobblers:dungeons/slot/s%d/free" % s["g"], PS.Ctx(None, POCKET, (0, 0, 0)))
    assert not mons(w), "the slot's free discards the rest"
