"""The independent audit of the dungeons (unit DG-AUDIT): tools/dungeon_independent_audit.py.

Three layers, each named after the property it protects:

* the audit's own machinery against SYNTHETIC worlds whose answers are worked by hand (a step of one, a fence, a gap of
  three and of four, a pit, a gate; the selector box, macros, `replace` fills, the victory callback's losers block);
* the GENERATOR mutated (never data/dungeons.json), the Night Shift rebuilt with the builders' own refusal switched off,
  and the audit required to name the new defect in the right room: a maze that loses its entrance passage, a wild room
  whose clear call is gone from the presence hook, a parkour tick that no longer catches a fall, a lever console with
  a lever missing;
* the three real dungeons, built from data/dungeons.json, required to have no finding (band 1, slot 1 per dungeon;
  the CLI's default runs all six bands and every slot).

Pass 2 (unit AUDIT2) adds the same three layers for variants, forks, secrets, relics, shortcuts, set pieces, parkour v2,
life and the return margin: synthetic worlds (a swimmer's way out, command storage and macros, rooms by box, a slot's
variant records, a U-shaped corridor's margin), the pass-2 fixtures (tests/fixtures/dungeon_kit2_demo.json and
dungeon_relics_demo.json in four variants; one dungeon per set piece and a parkour v2 room) required clean, and the
GENERATORS mutated (a fork route walled, one variant's door walled, cracked faces open or of plain rock, a balcony gap
bridged, a shortcut the reset leaves open, a flood onto its ledges, a collapse that never comes back, a canopy at head
height, a parkour fork with one way, a catch box over half the floor, a room reset that keeps its Pokemon, Pokemon in
the doorways), each named in the right room.

Not covered here or in the tool: anything Minecraft decides at runtime -- Cobblemon removing a fainted wild Pokemon,
`runmolang`/`start_battle`/the victory callback as EXP-078 assumes them, partial-block collision, a sprinting member
outrunning a one-second keeper pass, a walking member outrunning the collapse, a swimmer climbing two over the water,
the relic advancement and item, co-op. Validity is not behaviour (.claude/rules/testing.md): those are experiments,
not pytest.
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

import dungeon as D  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_independent_audit as A  # noqa: E402
import dungeon_kinds as K  # noqa: E402
import dungeon_life as L  # noqa: E402
import dungeon_parkour as P  # noqa: E402
import dungeon_puzzles as DP  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import dungeon_setpieces as S  # noqa: E402

SEVERE = {"TRAP", "SOFTLOCK", "WALK", "VOID", "PUZZLE", "BOSS", "RUN", "BOUNDS", "SLOT", "GATE", "PARKOUR", "MONEY",
          "LEVEL", "EXEMPT", "CLOCK", "VAULT", "SECRET", "SHORTCUT", "SETPIECE"}
OWN_TESTS = {"MARGIN", "LIFE"}      # pass 2 findings with a real-dungeon test of their own (below)


# ------------------------------------------------------------------------------------------------- synthetic worlds
def corridor(*writes):
    """A 1-wide corridor along +x at z 0: stone floor y 0 over x 0..20, stone walls at z -1 and z 1 from y -6 to 4,
    then `writes` [(a, b, block)] in order. The player stands on y 1."""
    w = A.World((-6, -8, -6), (26, 10, 6))
    w.write((-1, -7, -1), (21, 4, -1), "minecraft:stone")
    w.write((-1, -7, 1), (21, 4, 1), "minecraft:stone")
    w.write((0, 0, 0), (20, 0, 0), "minecraft:stone")
    for a, b, blk in writes:
        w.write(a, b, blk)
    return w


def reach(w, src=(1, 1, 0), gate=None):
    gr = A.Graph(w, gate)
    need, rev, voids = A.minimax_forward(gr, [gr.idx(*src)], set())
    return gr, need, rev, voids


def test_walk_steps_up_one_block_and_not_two():
    # Removing it lets the walk model climb walls (every trap disappears) or refuse stairs (every dungeon "unreachable").
    gr, need, _r, _v = reach(corridor(((5, 1, 0), (20, 1, 0), "minecraft:stone")))
    assert gr.idx(8, 2, 0) in need
    gr, need, _r, _v = reach(corridor(((5, 1, 0), (20, 2, 0), "minecraft:stone")))
    assert gr.idx(8, 3, 0) not in need


def test_a_fence_is_not_a_step():
    # Removing it lets the walk step onto fences, walls and iron bars, so a closed gate would read as passable.
    gr, need, _r, _v = reach(corridor(((5, 1, 0), (5, 1, 0), "minecraft:oak_fence"),
                                      ((6, 1, 0), (20, 1, 0), "minecraft:stone")))
    assert gr.idx(8, 2, 0) not in need


def test_walk_jumps_a_gap_of_three_and_not_four():
    # Removing it breaks the parkour rule (DUNGEONS.md V6): parkour rooms read as uncrossable, or wide gaps as fine.
    gr, need, _r, voids = reach(corridor(((5, 0, 0), (7, 0, 0), "minecraft:air")))
    assert gr.idx(9, 1, 0) in need
    assert voids, "stepping into the gap falls out of the world, and the walk must say so"
    gr, need, _r, _v = reach(corridor(((5, 0, 0), (8, 0, 0), "minecraft:air")))
    assert gr.idx(10, 1, 0) not in need


def test_a_pit_with_no_way_out_is_reachable_and_not_returnable():
    # Removing it loses the trap test itself: a pit you can fall into and not leave must read reachable, not back.
    # stone under the floor from x 9 to 11 down to y -3, then the pit x 10, y -2..0 carved: 3 deep, 1 wide, walled
    w = corridor(((9, -3, 0), (11, -1, 0), "minecraft:stone"), ((10, -2, 0), (10, 0, 0), "minecraft:air"))
    gr, need, rev, _v = reach(w)
    pit = gr.idx(10, -2, 0)
    assert pit in need
    back = A.minimax_back(rev, {gr.idx(1, 1, 0): -1})
    assert pit not in back
    assert gr.idx(15, 1, 0) in back            # the far side is still walked back from: the pit is the only trap


def test_a_gate_cell_is_shut_until_its_room_clears():
    # Removing it loses the per-state walk: a cleared door would be open in every state, so no trap is ever "until".
    import numpy as np
    w = corridor()
    gate = np.full(w.shape, -1, np.int16)
    for y in (1, 2):
        gate[10 - w.lo[0], y - w.lo[1], 0 - w.lo[2]] = 0
    gr, need, rev, _v = reach(w, gate=gate)
    assert need[gr.idx(5, 1, 0)] == -1
    assert need[gr.idx(15, 1, 0)] == 0
    back = A.minimax_back(rev, {gr.idx(1, 1, 0): -1})
    assert back[gr.idx(15, 1, 0)] == 0


def test_selector_boxes_are_block_inclusive_and_meet_the_hitbox():
    # Removing it lets the audit misread every room box, catch box and trigger line by a block.
    sim = A.Sim(A.Pack({}), A.World((-2, -2, -2), (4, 4, 4)))
    p = sim.add_player((1.9, 0.0, 0.5))
    ctx = A.Ctx(ex=p, pos=p.pos)
    sel = "@s[x=0,y=0,z=0,dx=1,dy=0,dz=0]"
    assert sim.select(sel, ctx)
    p.pos = (2.29, 0.0, 0.5)                  # hitbox from 1.99: inside [0, 2)
    assert sim.select(sel, ctx.but(ex=p))
    p.pos = (2.31, 0.0, 0.5)                  # hitbox from 2.01: outside
    assert not sim.select(sel, ctx.but(ex=p))


def test_interpreter_runs_macros_conditions_returns_and_replace_fills():
    # Removing it lets the simulated run read a hook wrong (a skipped `return`, an unsubstituted macro) unnoticed.
    pack = A.Pack({
        "data/t/function/a.mcfunction": "scoreboard players set #a o 3\n"
                                         "execute if score #a o matches 3 run function t:b {v:\"7\"}\n"
                                         "return 1\nscoreboard players set #a o 9\n",
        "data/t/function/b.mcfunction": "$scoreboard players set #b o $(v)\n",
    })
    w = A.World((0, 0, 0), (4, 4, 4))
    w.write((0, 0, 0), (4, 0, 0), "minecraft:iron_bars")
    w.write((2, 0, 0), (2, 0, 0), "minecraft:stone")
    sim = A.Sim(pack, w)
    assert sim.call("t:a", A.Ctx()) == 1
    assert sim.scores[("#a", "o")] == 3 and sim.scores[("#b", "o")] == 7
    sim.run_line("fill 0 0 0 4 0 0 minecraft:air replace minecraft:iron_bars", A.Ctx(), A.Frame())
    assert [A.base_id(w.get(x, 0, 0)) for x in range(5)] == ["air", "air", "stone", "air", "air"]


def test_victory_commands_are_the_npc_losers_block_only():
    # Removing it lets the simulated win run the loss branch (or skip the stand's dispatch), and the stands misread.
    body = ("for_each(t.l, c.scriptable_losers, { q.run_command('tag ' + t.w.player.username + ' add won'); "
            "q.run_command('execute as ' + t.w.player.username + ' run function x:won'); }); "
            "for_each(t.w, c.scriptable_winners, { q.run_command('tag ' + t.p.player.username + ' add lost'); });")
    pack = A.Pack({"data/cobblemon/callbacks/battle_victory/cobblers_dungeons.molang": body})
    cmds = A.victory(pack)
    assert len(cmds) == 2 and all("lost" not in c for c in cmds)
    assert A.molang_commands("q.run_command(%s);" % cmds[1], {"t.w.player.username": "P"}) == \
        ["execute as P run function x:won"]


# ------------------------------------------------------------------------------------------------- generator mutations
def ns_doc():
    doc = copy.deepcopy(D.load())
    doc["dungeons"] = [d for d in doc["dungeons"] if d["id"] == "night_shift"]
    return doc


def keys(findings):
    return {(f["cat"], f["room"]) for f in findings}


def audit_ns(files, doc):
    F, _info = A.audit(files, doc, only=["night_shift"], bands=[1], all_slots=False, modes=("win",))
    return F


@pytest.fixture(scope="module")
def ns_baseline():
    doc = ns_doc()
    R._BUILT.clear()                        # no room another module built with a mutated kind
    return doc, keys(audit_ns(D.build(doc), doc))


def mutated(monkeypatch, doc):
    """The Night Shift built with the builders' own refusal (dungeon.problems) switched off: the audit must find the
    defect by itself."""
    monkeypatch.setattr(D, "problems", lambda *a, **k: [])
    monkeypatch.setattr(R, "_BUILT", {})   # dungeon_rooms caches built rooms by DATA, so a code change needs a fresh cache
    return audit_ns(D.build(doc), doc)


def test_a_maze_that_loses_its_entrance_passage_is_named(monkeypatch, ns_baseline):
    # Removing it lets a maze generator that walls off its own entrance ship: the far rip unreachable, no one notified.
    doc, base = ns_baseline
    orig = K._maze_tree

    def broken(nx, nz, start, rg, loops):
        adj = orig(nx, nz, start, rg, loops)
        for n in list(adj[start]):
            adj[n].discard(start)
        adj[start] = set()
        return adj
    monkeypatch.setattr(K, "_maze_tree", broken)
    new = keys(mutated(monkeypatch, doc)) - base
    assert ("WALK", "old_workings") in new, new


def test_a_wild_room_whose_clear_call_is_gone_is_a_softlock(monkeypatch, ns_baseline):
    # Removing it lets a presence hook that never opens the gate after the creature is beaten ship (the_fall: miniboss).
    doc, base = ns_baseline
    orig = DF.presence_lines
    monkeypatch.setattr(DF, "presence_lines", lambda W, sel, clear_fn, fail_fn:
                        [ln for ln in orig(W, sel, clear_fn, fail_fn) if clear_fn not in ln])
    new = keys(mutated(monkeypatch, doc)) - base
    assert ("SOFTLOCK", "the_fall") in new, new


def test_a_parkour_floor_that_no_longer_catches_is_a_trap(monkeypatch, ns_baseline):
    # Removing it lets a parkour tick without its catch line ship: a fall lands in a pit with no teleport and no way out.
    doc, base = ns_baseline
    orig = R.KINDS["parkour"]

    def broken(*a):
        out = orig(*a)
        out["functions"]["tick"] = [ln for ln in out["functions"]["tick"] if "/fall" not in ln]
        return out
    monkeypatch.setitem(R.KINDS, "parkour", broken)
    new = keys(mutated(monkeypatch, doc)) - base
    assert ("TRAP", "collapse") in new, new


def test_a_lever_target_the_controls_cannot_set_is_unsolvable(monkeypatch, ns_baseline):
    # Removing it lets a console ship whose target needs a lever that is not there: a cleared gate nobody can open.
    doc, base = ns_baseline
    orig = DP.BUILDERS["levers"]

    def broken(c):
        out = orig(c)
        lev0 = tuple(out["anchors"]["controls"][0][:3])
        out["blocks"] = [op for op in out["blocks"] if not (op[0] == "set" and tuple(op[1]) == lev0)]
        at0 = "setblock %d %d %d " % lev0
        for k in ("reset", "wrong"):
            out["functions"][k] = [ln for ln in out["functions"][k] if at0 not in ln]
        return out
    monkeypatch.setitem(DP.BUILDERS, "levers", broken)
    new = keys(mutated(monkeypatch, doc)) - base
    assert ("PUZZLE", "winding_house") in new, new


# ------------------------------------------------------------------------------------------------- the real dungeons
@pytest.fixture(scope="module")
def real():
    doc = D.load()
    R._BUILT.clear()
    F, info = A.audit(D.build(doc), doc, bands=[1], all_slots=False)
    return doc, F, info


def test_every_gate_puzzle_vault_and_run_was_exercised(real):
    # Removing it lets the audit pass vacuously: a parser that finds no gate, puzzle, chest or run reports nothing wrong.
    doc, F, _info = real
    for d in doc["dungeons"]:
        st = F.stats[d["id"]]
        gated = [r for r in d["rooms"] if A.gated(r)]
        puzzles = [r for r in d["rooms"] if r["kind"] == "puzzle"]
        chests = sum(int(r["params"].get("chests", 0)) for r in d["rooms"] if r["kind"] == "vault")
        assert st["gates_opened"] == len(gated), (d["id"], st)
        assert st["puzzle_targets_solvable"] >= len(puzzles), (d["id"], st)
        assert st["vault_chests_checked"] == chests, (d["id"], st)
        assert st["runs_finished"] >= 1 and st["battles"] >= 1, (d["id"], st)
        assert st["cells_reached"] > 10000 and st["exit_cells"] and st["back_cells"], (d["id"], st)


def test_real_dungeons_have_no_trap_softlock_or_dead_end(real):
    # Removing it lets a room a player can enter and not leave, or a gate that never opens, reach the server.
    _doc, F, _info = real
    bad = [A.fmt(f) for f in F if f["cat"] in SEVERE]
    assert not bad, "\n".join(bad)


def test_real_dungeons_restore_what_a_run_changes_and_stay_under_the_chain_limit(real):
    # Removing it lets a run's barrier eat the dressing for good, or a function too long to finish stay in the pack.
    _doc, F, _info = real
    bad = [A.fmt(f) for f in F if f["cat"] not in SEVERE | OWN_TESTS]
    assert not bad, "\n".join(bad)


def test_real_dungeons_way_back_warning_never_comes_late(real):
    # Removing it lets m/margin, which prices the way back by x alone, warn a member after the walk back no longer fits
    # the clock (a maze, a turn or a route doubling back walks further than its x). The fix is the generator's.
    _doc, F, _info = real
    bad = [A.fmt(f) for f in F if f["cat"] == "MARGIN"]
    assert not bad, "\n".join(bad)


def test_real_dungeons_ambient_pokemon_never_spawn_in_a_doorway(real):
    # Removing it lets LIFE seat a wandering Pokemon in (or beside) a door it was told to keep off.
    _doc, F, _info = real
    bad = [A.fmt(f) for f in F if f["cat"] == "LIFE"]
    assert not bad, "\n".join(bad)


# ================================================================================================= pass 2 (AUDIT2)
# Synthetic first (hand-computed answers), then the pass-2 fixtures built by the real generators, then the generators
# mutated (tests/fixtures and data/ untouched): each new check must name the defect a mutation plants, and only it.
def test_a_swimmer_climbs_out_onto_ground_one_over_the_water_and_not_two():
    # Removing it lets a flooded hall read as a trap (no swimmer could leave it) or a deep pit as a way out.
    # a pool x 5..9 dug to y -2 under the corridor's floor (y 0); ground on to x 10 stands with its top block at y 0
    pool = (((5, -3, 0), (9, -3, 0), "minecraft:stone"), ((5, -2, 0), (9, 0, 0), "minecraft:air"))
    w = corridor(*pool, ((5, -2, 0), (9, -1, 0), "minecraft:water"))     # the water's top block y -1: ground is 2 over
    gr = A.Graph(w)
    assert gr.idx(12, 1, 0) in A.reach_from(gr, [gr.idx(7, -1, 0)])
    w = corridor(*pool, ((5, -2, 0), (9, -2, 0), "minecraft:water"))     # the water's top block y -2: ground is 3 over
    gr = A.Graph(w)
    assert gr.idx(12, 1, 0) not in A.reach_from(gr, [gr.idx(7, -2, 0)])


def test_command_storage_runs_lists_and_macros_as_the_pack_writes_them():
    # Removing it lets LIFE's spawn table (storage, `function ... with storage`) run as nothing: no ambient Pokemon is
    # ever spawned in the simulation, so none of their cleanup is tested.
    pack = A.Pack({
        "data/t/function/a.mcfunction": "data modify storage t:s list set value [{x:\"1\",n:2},{x:\"5\",n:3b}]\n"
                                         "function t:loop\n"
                                         "execute store result storage t:s v int 1 run scoreboard players get #sum o\n"
                                         "function t:echo with storage t:s\n",
        "data/t/function/loop.mcfunction": "execute unless data storage t:s list[0] run return 0\n"
                                            "function t:m with storage t:s list[0]\n"
                                            "data remove storage t:s list[0]\nfunction t:loop\n",
        "data/t/function/m.mcfunction": "$scoreboard players add #sum o $(n)\n",
        "data/t/function/echo.mcfunction": "$scoreboard players set #echo o $(v)\n",
    })
    sim = A.Sim(pack, A.World((0, 0, 0), (1, 1, 1)))
    sim.call("t:a", A.Ctx())
    assert sim.scores[("#sum", "o")] == 5 and sim.scores[("#echo", "o")] == 5
    assert sim.storage["t:s"]["list"] == []


def test_rooms_are_found_by_their_own_boxes_not_by_x():
    # Removing it maps a stacked room, or a route walked back west under the route, onto whatever room shares its x.
    s = A.Slot()
    s.boxes = {"low": (0, 0, 0, 10, 5, 10), "high": (0, 7, 0, 10, 12, 10), "east": (10, 0, 0, 30, 5, 10)}
    assert A.room_at(s, 5, 9, 5) == "high" and A.room_at(s, 5, 2, 5) == "low"
    assert A.room_at(s, 10, 2, 5) == "low"           # a shared face: the smaller box
    assert A.room_at(s, 5, 6, 5) is None


def test_a_slots_records_are_its_variant_with_routes_and_side_rooms_flattened():
    # Removing it lets the audit judge a swapped room by its base record (the wrong kind, the wrong params) and lose
    # the rooms inside forks and side rooms.
    d = {"rooms": [{"id": "e", "kind": "entry_room"},
                   {"id": "f", "kind": "fork", "routes": [{"id": "fast", "rooms": [{"id": "fa", "kind": "drift"}]},
                                                          {"id": "safe", "rooms": [{"id": "sa", "kind": "drift", "params": {"q": 1}},
                                                                                   {"id": "sb", "kind": "drift"}]}]},
                   {"id": "s", "kind": "side", "rooms": [{"id": "n1", "kind": "vault"}]},
                   {"id": "x", "kind": "exit_room"}],
         "variants": [{"id": "a"}, {"id": "b", "swap": {"sa": {"kind": "stand", "params": {"p": 2}}}}]}
    vi, recs, forks, sides = A.slot_records(d, 2)
    assert vi == 1 and recs["sa"]["kind"] == "stand" and recs["sa"]["params"] == {"q": 1, "p": 2}
    assert forks == {"f": {"fast": ["fa"], "safe": ["sa", "sb"]}} and sides == {"s": ["n1"]}
    assert set(recs) == {"e", "fa", "sa", "sb", "n1", "x"}
    vi, recs, _f, _s = A.slot_records(d, 3)
    assert vi == 0 and recs["sa"]["kind"] == "drift"


def test_the_return_margin_is_measured_against_the_real_walk_back():
    # Removing it lets a route that turns back on itself keep a way-back warning priced by x alone.
    # Two corridors (z 0 and z 2, x 0..100) joined only at x 100; the back rip at (0, 1, 0). From (0, 1, 2) the walk
    # back is 100 + 2 + 100 = 202 blocks; the margin below prices (x - 0) * 10 / 56 + 0 = 0 s; at its own pace of
    # 5.6 blocks a second (560 blocks of x = 100 s) the walk takes 202 / 5.6 = 36.07 s: 37 s late.
    w = A.World((-6, -8, -6), (110, 10, 10))
    w.write((-1, -7, -1), (101, 4, -1), "minecraft:stone")
    w.write((-1, -7, 3), (101, 4, 3), "minecraft:stone")
    w.write((-1, -7, -1), (-1, 4, 3), "minecraft:stone")
    w.write((101, -7, -1), (101, 4, 3), "minecraft:stone")
    w.write((0, 0, 0), (100, 0, 2), "minecraft:stone")
    w.write((0, 1, 1), (99, 4, 1), "minecraft:stone")
    gr = A.Graph(w)
    a = gr.idx(0, 1, 0)
    gr.info = {"need": A.reach_from(gr, [a]), "catch": set(), "backs": {a}}
    s = A.Slot()
    s.g, s.dungeon, s.rooms, s.boxes, s.arrive = 1, "t", ["r"], {"r": (-1, -1, -1, 101, 5, 3)}, (0.5, 1.0, 0.5)
    pre = "data/cobblers/function/dungeons/"
    pack = A.Pack({pre + "load.mcfunction": "scoreboard players set #10 dg.t 10\nscoreboard players set #56 dg.t 56\n",
                   pre + "m/margin.mcfunction":
                   "execute store result score @s dg.x run data get entity @s Pos[0]\n"
                   "scoreboard players operation #bk dg.t = @s dg.x\n"
                   "execute if score @s dg.dun matches 1 run scoreboard players remove #bk dg.t 0\n"
                   "scoreboard players operation #bk dg.t *= #10 dg.t\n"
                   "scoreboard players operation #bk dg.t /= #56 dg.t\n"
                   "scoreboard players add #bk dg.t 0\n"})
    F = A.Findings()
    A.margin_audit(pack, {"dungeons": [{"id": "t"}]}, s, gr, F)
    assert [(f["cat"], f["room"], f["at"]) for f in F] == [("MARGIN", "r", (0, 1, 2))], [A.fmt(f) for f in F]
    assert "37 s late" in F[0]["msg"] and "202 blocks" in F[0]["msg"], F[0]["msg"]


# ------------------------------------------------------------------------------------------------- the pass-2 fixtures
FIXTURES = ROOT / "tests" / "fixtures"
SP_DEMO = {r["id"]: r for r in json.loads((FIXTURES / "dungeon_demo_rooms.json").read_text(encoding="utf-8"))["rooms"]}
PIECES = {
    "collapse": ("mine", {"id": "sp", "kind": "setpiece", "length": 90, "width": 25, "height": 11,
                          "params": {"piece": "collapse"}}),
    "flood": ("flooded_ruin", {"id": "sp", "kind": "setpiece", "length": 64, "width": 31, "height": 14,
                               "params": {"piece": "flood", "pit": 10}}),
    "lights_out": ("jungle", {"id": "sp", "kind": "setpiece", "length": 100, "width": 33, "height": 12,
                              "params": {"piece": "lights_out", "pit": 0, "no_deploy": False}}),
    "parkour": ("mine", {"id": "pk", "kind": "parkour", "length": 110, "width": 35, "height": 12, "params": {}}),
}


def fixture_doc(name, theme="mine"):
    """tests/fixtures/dungeon_<name>.json as the only dungeon, its four variants in four slots."""
    fx = json.loads((FIXTURES / ("dungeon_%s.json" % name)).read_text(encoding="utf-8"))
    doc = copy.deepcopy(D.load())
    d = doc["dungeons"][0]
    d["theme"], d["rooms"], d["variants"] = theme, copy.deepcopy(fx["rooms"]), copy.deepcopy(fx.get("variants") or [])
    d.pop("spine", None)
    d.pop("clock_s_by_band", None)
    doc["dungeons"] = [d]
    doc["engine"]["sigils"]["free_first_entry"]["dungeons"] = [d["id"]]
    doc["engine"]["slots"]["per_dungeon"] = 4
    return doc


def piece_doc(name):
    """A short dungeon around one set piece (or a parkour v2 room): the demo's entry, a drift, the room, a drift, arena,
    exit (the rooms tests/test_dungeon_setpieces.py builds)."""
    theme, room = PIECES[name]
    doc = copy.deepcopy(D.load())
    d = doc["dungeons"][0]
    d["theme"] = theme
    d["rooms"] = [copy.deepcopy(SP_DEMO[k]) for k in ("entry", "d1")] + [copy.deepcopy(room)] + \
                 [copy.deepcopy(SP_DEMO[k]) for k in ("d5", "arena", "exit")]
    d.pop("spine", None)
    d.pop("clock_s_by_band", None)
    doc["dungeons"] = [d]
    doc["engine"]["sigils"]["free_first_entry"]["dungeons"] = [d["id"]]
    doc["engine"]["slots"]["per_dungeon"] = 1
    return doc


def audit_doc(doc):
    F, _info = A.audit(D.build(doc), doc, bands=[1], all_slots=False, modes=("win",))
    return F


def build_mutated(monkeypatch, doc):
    monkeypatch.setattr(D, "problems", lambda *a, **k: [])
    monkeypatch.setattr(R, "_BUILT", {})
    return audit_doc(doc)


def found(F, cat, room=None, text=""):
    return [f for f in F if f["cat"] == cat and (room is None or f["room"] == room) and text in f["msg"]]


@pytest.fixture(scope="module")
def kit2():
    R._BUILT.clear()
    doc = fixture_doc("kit2_demo")
    return doc, audit_doc(doc)


@pytest.fixture(scope="module")
def relics():
    R._BUILT.clear()
    doc = fixture_doc("relics_demo")
    return doc, audit_doc(doc)


@pytest.fixture(scope="module")
def pieces():
    out = {}
    for name in PIECES:
        R._BUILT.clear()
        doc = piece_doc(name)
        out[name] = (doc, audit_doc(doc))
    return out


def test_every_variant_is_walked_on_its_own_shell_and_its_routes_secrets_and_shortcut_checked(kit2):
    # Removing it lets the audit fall back to walking slot 1 and reusing it (false SOFTLOCKs in slots 2-4, real faults
    # there missed), or pass vacuously on a fixture whose fork, secrets and shortcut it never reached.
    _doc, F = kit2
    bad = [A.fmt(f) for f in F if f["cat"] in SEVERE]
    assert not bad, "\n".join(bad)
    st = F.stats["night_shift"]
    assert st["runs_finished"] == 4                         # one per variant, each on its own walk
    assert st["fork_routes_walked"] == 8                    # 2 routes x 4 variants
    assert st["cracked_faces_checked"] == 4 and st["balcony_rooms_checked"] == 4 and st["shortcuts_checked"] == 4


def test_the_relics_demo_reaches_every_relic_only_with_its_trick(relics):
    # Removing it lets a relic sit where the plain walk reaches it, or where no trick does, unnoticed.
    _doc, F = relics
    bad = [A.fmt(f) for f in F if f["cat"] in SEVERE]
    assert not bad, "\n".join(bad)
    assert F.stats["night_shift"]["relic_triggers"] == 12 and F.stats["night_shift"]["cracked_faces_checked"] == 8


def test_each_set_piece_is_swept_through_its_states_with_no_trap(pieces):
    # Removing it lets a collapse, flood or lights-out ship whose LATER states (not the shell) trap or cut the way on.
    for name, (_doc, F) in pieces.items():
        bad = [A.fmt(f) for f in F if f["cat"] in SEVERE]
        assert not bad, (name, bad)
    st = {n: F.stats["night_shift"] for n, (_d, F) in pieces.items()}
    assert st["collapse"]["setpiece_states"] >= 20      # entered, 19 collapse steps and more (the walk's restores)
    assert st["flood"]["setpiece_states"] >= 10         # entered and 9 water levels
    assert st["lights_out"]["setpiece_states"] == 4     # 0..3 sections closed
    assert st["parkour"]["parkour_fork_sections"] == 1


def test_a_route_of_a_fork_that_does_not_finish_alone_is_named(monkeypatch, kit2):
    # Removing it lets a fork ship whose second route is a dead end: the all-routes walk still finds the far rip.
    doc, _F = kit2
    orig = R.KINDS["drift"]

    def shut(doc_, d, slot, room, theme):
        out = orig(doc_, d, slot, room, theme)
        if room["id"] == "safe_c":                       # the safe route's last room: its way out walled
            for dr in room.get("doors") or []:
                if dr.get("dir") == "out":
                    out.setdefault("blocks", []).append(R.fill(tuple(dr["box"]), "minecraft:deepslate"))
        return out
    monkeypatch.setitem(R.KINDS, "drift", shut)
    F = build_mutated(monkeypatch, doc)
    assert {f["slot"] for f in found(F, "WALK", "safe_c", "[route f1/safe alone]")} == {1, 2, 3, 4}
    assert not found(F, "WALK", None, "[route f1/fast alone]")


def test_a_defect_in_one_variant_is_found_in_that_slot_only(monkeypatch, kit2):
    # Removing it lets the audit vouch for slots 2-4 with slot 1's walk: a fault only one variant builds goes unseen.
    doc, _F = kit2
    orig = R.KINDS["drift"]

    def shut(doc_, d, slot, room, theme):
        out = orig(doc_, d, slot, room, theme)
        if room["id"] == "d1" and slot.get("k") == 2:    # variant b only: d1's way out walled
            for dr in room.get("doors") or []:
                if dr.get("dir") == "out":
                    out.setdefault("blocks", []).append(R.fill(tuple(dr["box"]), "minecraft:deepslate"))
        return out
    monkeypatch.setitem(R.KINDS, "drift", shut)
    F = build_mutated(monkeypatch, doc)
    assert {f["slot"] for f in F if f["cat"] == "WALK"} == {2}, [A.fmt(f) for f in F if f["cat"] == "WALK"]


def _cracked_face(monkeypatch, block):
    """Every cracked face built of `block` (None: air) and not put back by the reset."""
    orig = R._cracked

    def bad(room, side, cx, s):
        g = orig(room, side, cx, s)
        if g:
            ops = g["ops"]
            g["reset"] = []
            g["ops"] = lambda wall, light, shp: [
                op if not (op[0] == "set" and op[2] == shp["secret_block"]) else ("set", op[1], block or wall)
                for op in ops(wall, light, shp)]
        return g
    monkeypatch.setattr(R, "_cracked", bad)


def test_a_cracked_secret_left_open_is_picked_up_without_the_trick(monkeypatch, relics):
    # Removing it lets a secret chamber ship open: its relic is taken by walking in, no pick, no secret.
    doc, _F = relics
    _cracked_face(monkeypatch, "minecraft:air")
    F = build_mutated(monkeypatch, doc)
    assert found(F, "SECRET", "a", "relic first_find is picked up with every face whole")
    assert found(F, "SECRET", "a", "relic second_find is picked up with every face whole")
    assert not found(F, "SECRET", "b")


def test_a_cracked_face_the_pick_cannot_break_is_named(monkeypatch, relics):
    # Removing it lets a secret ship behind plain rock: a relic nobody can ever reach.
    doc, _F = relics
    _cracked_face(monkeypatch, None)                     # the wall block
    F = build_mutated(monkeypatch, doc)
    assert found(F, "SECRET", "a", "no face the pick may break")
    assert found(F, "SECRET", "a", "relic first_find is not reached with any cracked face broken")


def test_a_balcony_alcove_reached_without_a_jump_is_named(monkeypatch, relics):
    # Removing it lets a balcony secret ship with its gap bridged: the relic is a walk, not a find.
    doc, _F = relics
    orig = R._balcony

    def bridged(room, side, sx, s):
        g = orig(room, side, sx, s)
        if g:
            ops = g["ops"]
            bx, by, _bz = g["anchors"]["balcony"][0][:3]
            zs = sorted({z for (_x, z) in g["lift"]})
            g["ops"] = lambda wall, light, shp: ops(wall, light, shp) + [R.fill((bx + 1, by - 1, zs[0], bx + 2, by - 1, zs[-1]), wall)]
        return g
    monkeypatch.setattr(R, "_balcony", bridged)
    F = build_mutated(monkeypatch, doc)
    assert {f["slot"] for f in found(F, "SECRET", "b", "relic high_find is picked up without a jump")} == {1, 2, 3, 4}
    assert not found(F, "SECRET", "a")


def test_a_shortcut_the_reset_does_not_shut_is_named(monkeypatch, kit2):
    # Removing it lets a shortcut opened in one run stay open for the next (and the route behind it be skipped).
    doc, _F = kit2
    orig = R.shortcut_hooks

    def open_for_good(*a):
        out = orig(*a)
        if "reset" in out["functions"]:
            out["functions"]["reset"] = [ln for ln in out["functions"]["reset"] if not ln.startswith("fill ")]
        return out
    monkeypatch.setattr(R, "shortcut_hooks", open_for_good)
    F = build_mutated(monkeypatch, doc)
    assert found(F, "RESET", "ring_room", "shortcut c1 is still open after the slot's reset")


def test_a_shortcut_opened_from_the_near_side_is_named(monkeypatch, kit2):
    # Removing it lets a shortcut's trigger stand on the near side of its door: the way back opens before the far room
    # is ever reached, and the rooms between are skipped.
    doc, _F = kit2
    orig = R.shortcut_hooks

    def near_side(*a):
        out = orig(*a)
        fns = out["functions"]
        for name in [k for k in fns if k.startswith("shortcut_")]:
            door = [int(v) for v in re.search(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) minecraft:air",
                                              "\n".join(fns[name])).groups()]
            ticks = []
            for ln in fns["tick"]:
                m = re.search(r"@s\[x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)\]", ln)
                if m and name in ln:
                    x, y, z, dx, dy, dz = (int(v) for v in m.groups())
                    lo, hi = [x, y, z], [x + dx, y + dy, z + dz]
                    for k in (0, 2):                   # reflected through the door, along the axis it lies across
                        if hi[k] < door[k]:
                            lo[k], hi[k] = door[k + 3] + (door[k] - hi[k]), door[k + 3] + (door[k] - lo[k])
                        elif lo[k] > door[k + 3]:
                            lo[k], hi[k] = door[k] - (hi[k] - door[k + 3]), door[k] - (lo[k] - door[k + 3])
                    ln = ln.replace(m.group(0), "@s[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d]" % (
                        lo[0], lo[1], lo[2], hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))
                ticks.append(ln)
            fns["tick"] = ticks
        return out
    monkeypatch.setattr(R, "shortcut_hooks", near_side)
    F = build_mutated(monkeypatch, doc)
    assert found(F, "SHORTCUT", "ring_room"), [A.fmt(f) for f in F if f["cat"] != "LIFE"]


def test_a_flood_that_rises_onto_the_ledges_is_named(monkeypatch, pieces):
    # Removing it lets the flood's top water block reach the ledges a swimmer climbs onto (and the doors beyond).
    doc, _F = pieces["flood"]
    monkeypatch.setattr(S, "TOP_BELOW_LEDGE", 0)
    F = build_mutated(monkeypatch, doc)
    assert found(F, "SETPIECE", "sp", "water stands on a ledge's top"), [A.fmt(f) for f in F]


def test_a_collapse_that_never_puts_its_floor_back_cuts_the_way_on(monkeypatch, pieces):
    # Removing it lets a collapse ship whose span never comes back: nobody is trapped (the falls teleport, the ledges
    # are safe) and nobody can ever cross -- only a sweep of the piece's states sees it.
    doc, _F = pieces["collapse"]
    orig = S.collapse

    def no_restore(*a):
        out = orig(*a)
        out["functions"]["tick"] = [ln for ln in out["functions"]["tick"] if "/restore" not in ln]
        return out
    monkeypatch.setattr(S, "collapse", no_restore)
    F = build_mutated(monkeypatch, doc)
    assert found(F, "SOFTLOCK", "sp", "the way out of the room stays cut"), [A.fmt(f) for f in F]


def test_lights_out_that_drops_its_sheet_onto_the_player_is_named(monkeypatch, pieces):
    # Removing it lets the canopy close at head height: blocks set where a player stands, the room sealed.
    doc, _F = pieces["lights_out"]
    orig = S.lights_out

    def low(doc_, d, slot, room, theme):
        out = orig(doc_, d, slot, room, theme)
        closes = [k for k in out["functions"] if k.startswith("close")]
        sheet = re.match(r"fill -?\d+ (-?\d+) ", next(ln for k in closes for ln in out["functions"][k]
                                                      if ln.startswith("fill "))).group(1)
        for k in closes:                                  # the sheet one over the floor the player's feet stand on
            out["functions"][k] = [ln.replace(" %s " % sheet, " %d " % (room["floor_in"] + 1)) if ln.startswith("fill ")
                                   else ln for ln in out["functions"][k]]
        return out
    monkeypatch.setattr(S, "lights_out", low)
    F = build_mutated(monkeypatch, doc)
    assert found(F, "TRAP", "sp", "cells a player may stand in are filled with blocks"), [A.fmt(f) for f in F]


def test_a_parkour_fork_with_one_way_is_named(monkeypatch, pieces):
    # Removing it lets a parkour "fork" ship whose safe chain is gone: one way, the choice the owner asked for lost.
    doc, _F = pieces["parkour"]
    orig = P.chain_via

    def no_safe(rg, route, a, b, row0, rowm, rowb, tier, lvmax, wiggle, branch=None, flat=False):
        if branch == "safe":
            return None
        return orig(rg, route, a, b, row0, rowm, rowb, tier, lvmax, wiggle, branch, flat)
    monkeypatch.setattr(P, "chain_via", no_safe)
    F = build_mutated(monkeypatch, doc)
    assert found(F, "PARKOUR", "pk", "no section has a second way"), [A.fmt(f) for f in F]


def test_a_parkour_catch_box_that_misses_part_of_the_floor_is_named(monkeypatch, pieces):
    # Removing it lets a chasm ship whose catch floor teleports from only part of it: a fall elsewhere is a pit.
    doc, _F = pieces["parkour"]
    orig = R.KINDS["parkour"]

    def half(*a):
        out = orig(*a)
        c = out["anchors"]["catch"]
        half_box = [c[0], c[1], c[2], (c[0] + c[3]) // 2, c[4], c[5]]
        out["functions"]["tick"] = [ln.replace(R.sel_box(c), R.sel_box(half_box)) for ln in out["functions"]["tick"]]
        return out
    monkeypatch.setitem(R.KINDS, "parkour", half)
    F = build_mutated(monkeypatch, doc)
    assert found(F, "PARKOUR", "pk", "are not a catch floor"), [A.fmt(f) for f in F]


def test_life_whose_room_reset_keeps_its_pokemon_is_named(monkeypatch, pieces):
    # Removing it lets a room's reset leave its ambient Pokemon for the next run (and the slot fill up with them).
    doc, _F = pieces["collapse"]
    fn, level = R.DRESS["life"]

    def keep(ctx, spec):
        out = fn(ctx, spec)
        f = ctx.built.functions
        f["reset"] = [ln for ln in f.get("reset", []) if "q.entity.discard" not in ln]
        return out
    monkeypatch.setitem(R.DRESS, "life", (keep, level))
    F = build_mutated(monkeypatch, doc)
    assert found(F, "LIFE", None, "the room's reset leaves"), [A.fmt(f) for f in F]


def test_life_seated_in_the_doorways_is_named(monkeypatch, pieces):
    # Removing it lets LIFE put its ambient Pokemon in the doors (it keeps clear of the door in only, where it can).
    doc, _F = pieces["collapse"]
    orig = L.spots_of

    def by_the_door(ctx, reach):
        out = orig(ctx, reach)
        dout = ctx.built.anchors.get("door_out_at")
        if not dout:
            return out
        return sorted(out, key=lambda c: (c[0] - dout[0]) ** 2 + (c[2] - dout[2]) ** 2)[:6]
    monkeypatch.setattr(L, "spots_of", by_the_door)
    F = build_mutated(monkeypatch, doc)
    assert found(F, "LIFE", None, "spawns in a doorway"), [A.fmt(f) for f in F]
