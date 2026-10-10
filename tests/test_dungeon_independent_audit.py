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

Not covered here or in the tool: anything Minecraft decides at runtime -- Cobblemon removing a fainted wild Pokemon,
`runmolang`/`start_battle`/the victory callback as EXP-078 assumes them, partial-block collision, a sprinting member
outrunning a one-second keeper pass, co-op. Validity is not behaviour (.claude/rules/testing.md): those are
experiments, not pytest.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_independent_audit as A  # noqa: E402
import dungeon_kinds as K  # noqa: E402
import dungeon_puzzles as DP  # noqa: E402
import dungeon_rooms as R  # noqa: E402

SEVERE = {"TRAP", "SOFTLOCK", "WALK", "VOID", "PUZZLE", "BOSS", "RUN", "BOUNDS", "SLOT", "GATE", "PARKOUR", "MONEY",
          "LEVEL", "EXEMPT", "CLOCK", "VAULT"}


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
    bad = [A.fmt(f) for f in F if f["cat"] not in SEVERE]
    assert not bad, "\n".join(bad)
