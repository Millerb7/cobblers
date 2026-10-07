"""tools/finale_audit.py: the independent audit of the Rift finale -- the HQ chain, the two fights, the release.

Written by test-author, 2026-10-04; re-pointed the same day to the reconciled finale (62b953c at 9c51444: ONE Brann
and ONE Elara, Cobblemon NPCs in the HQ tower who talk and fight; the release at cradle_open). The finale was built
by other agents. Three kinds of test:

  synthetic   the audit's own machinery (Molang interpreter with for_each and members, the multi-entity command
              model, a hand-written battle_victory callback, the properties reader, cell replay and walk, jar
              legality, the cap rule) on fixtures whose answers are computed by hand in the comments
  real        the REAL generators emit into tmp (compile_dialogue --all, route_trainers, progression_pack,
              hq_tower's callback, won functions and gate cycle, release_fx) and the audit reads what they wrote
  mutation    a GENERATOR is changed in memory (data untouched) and the audit must fail: compile_dialogue dropping
              brann_defeated from record_hq_crossed's guard, or elara_defeated everywhere, or levelling a party
              member; hq_tower moving the callback's position match, widening it, or opening the climb a stage early;
              progression_pack making the flag earnable; release_fx shown to everyone

Not covered: anything in game (see the tool's docstring). The cradle and z5 tests read build/datapacks and skip when
those packs are not built (the relic pack needs the Rift skin's pack).
"""
import json
import re
import shutil
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import finale_audit as A  # noqa: E402

DATA = ROOT / "data"
BUILT = ROOT / "build" / "datapacks"
K_STAGE, K_B, K_E = A.key(A.STAGE), A.key(A.BRANN_FIELD), A.key(A.ELARA_FIELD)


# ====================================================================== synthetic fixtures

def gate(*fields):
    return " && ".join(["(t.d.%s == '%s')" % (K_STAGE, A.RELEASE_STAGE)] + ["(t.d.%s == 1)" % f for f in fields])


def tiny_dialogue(visible_fields, guard_fields):
    """A three-page conversation in the compiler's emitted shape: open -> ask (choice) -> release (grants on ack).
    `visible_fields` gate the choice, `guard_fields` gate the grant and the stage write."""
    grant = ("(%s) ? { q.run_command('execute as ' + q.player.uuid + ' at @s run function %s'); t.d.%s = '%s'; "
             "q.player.save_data(); };" % (gate(*guard_fields), A.FLAG_GRANT_FN, K_STAGE, A.RELEASED))
    return {
        "initializationAction": "t.d = q.player.data(); v.e = 0; (v.e == 0 && t.d.%s == '%s') ? "
                                "{ v.e = 'ask'; }; v.e == 0 ? { q.dialogue.close(); } : { q.dialogue.set_page(v.e); };"
                                % (K_STAGE, A.RELEASE_STAGE),
        "pages": [
            {"id": "ask", "input": {"type": "option", "options": [
                {"text": A.CHOICE, "value": "r", "action": "t.d = q.player.data(); q.dialogue.set_page('release');",
                 "isVisible": "t.d = q.player.data(); return (%s);" % gate(*visible_fields)},
                {"text": "Not yet.", "value": "n", "action": "q.dialogue.close();"}]}},
            {"id": "release", "input": "t.d = q.player.data(); %s q.dialogue.close();" % grant},
        ]}


GRANT_FN = {A.FLAG_GRANT_FN: ["advancement grant @s only %s" % A.FLAG_ADV]}


# Protects: the walk finds the grant from the rule's state (cradle_open, both) and from no other; if removed, a leak
# in the walker itself (e.g. never taking an option) would let every real conversation pass.
def test_walk_grants_only_at_the_rule_on_a_correct_fixture():
    dlg = tiny_dialogue([K_B, K_E], [K_B, K_E])
    # hand: (cradle_open, 1, 1) opens 'ask', the choice is visible, 'release' runs the grant once
    g, _n, offered = A.walk(dlg, GRANT_FN, ({K_STAGE: A.RELEASE_STAGE, K_B: 1, K_E: 1}, set()))
    assert offered and len(g) == 1 and A.contract(g[0][0])
    # hand: (cradle_open, 1, unset) opens 'ask' but the choice is hidden; no grant
    g, _n, offered = A.walk(dlg, GRANT_FN, ({K_STAGE: A.RELEASE_STAGE, K_B: 1}, set()))
    assert not offered and g == []
    # hand: the pre-merge release stage closes at once
    g, _n, offered = A.walk(dlg, GRANT_FN, ({K_STAGE: A.PENDING, K_B: 1, K_E: 1}, set()))
    assert not offered and g == []


def write_conv(root, conv, dlg):
    f = root / "cobblers_dialogue" / "data" / "cobblers" / "dialogues" / ("%s.json" % conv)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(dlg), encoding="utf-8")


# Protects: a gate missing one field is caught by check_conversation; if removed, the audit could pass a release
# that needs only Brann.
def test_check_conversation_flags_a_gate_that_forgets_elara(tmp_path):
    for dlg, leaky in ((tiny_dialogue([K_B, K_E], [K_B, K_E]), False), (tiny_dialogue([K_B], [K_B]), True)):
        p = tmp_path / ("leaky" if leaky else "ok")
        write_conv(p, A.CONV, dlg)
        bad, _ = A.check_conversation(p, GRANT_FN, DATA, only=["binder"])
        if leaky:
            # hand: from (cradle_open, brann 1, elara unset/0) the choice shows, the grant runs, the stage moves
            assert any("fails the rule" in b for b in bad) and any("is shown from" in b for b in bad)
            assert any("writes rift_released without" in b for b in bad)
        else:
            assert bad == [], bad[:3]


# Protects: a visible choice whose TRANSITION still guards both is reported (shown where the rule fails) even
# though no grant leaks; if removed, a player could be offered a release that silently does nothing.
def test_check_conversation_reports_a_choice_shown_but_guarded(tmp_path):
    write_conv(tmp_path, A.CONV, tiny_dialogue([K_B], [K_B, K_E]))
    bad, _ = A.check_conversation(tmp_path, GRANT_FN, DATA, only=["binder"])
    assert any("is shown from" in b for b in bad)
    assert not any("fails the rule" in b for b in bad)


# Protects: the Molang interpreter's semantics the walk rests on: an unset key reads 0, strings never equal
# numbers, `+` concatenates, ternary blocks, for_each over a context list with member access; if removed, a wrong
# interpreter could agree with a wrong compiler or callback.
def test_molang_semantics_by_hand():
    w, p = A.World({}), A.Player(uuid="U")
    m = A.Molang(w, p)
    assert m.run("t.d = q.player.data(); return t.d.missing;") == 0
    assert m.run("return ('a' == 0);") == 0
    assert m.run("return ('x' + q.player.uuid);") == "xU"
    m.run("t.d = q.player.data(); (t.d.k == 0) ? { t.d.k = 2; } : { t.d.k = 3; }; t.d.j = !(t.d.k == 2);")
    assert p.data == {"k": 2, "j": 0}
    # hand: two items, only the second has is_npc, so v.s = '' + 'B' = 'B' and v.n = 1
    m = A.Molang(w, p, ctx={"c.xs": [{"is_npc": 0, "uuid": "A"}, {"is_npc": 1, "uuid": "B"}]})
    m.run("v.s = ''; v.n = 0; for_each(t.l, c.xs, { t.l.is_npc ? { v.s = v.s + t.l.uuid; v.n = v.n + 1; }; });")
    assert m.vars == {"s": "B", "n": 1}


# Protects: the command model's execute chain (if/unless entity, score matches, unset scores match nothing,
# function calls, return fail); if removed, the z5 and release_fx checks would run on an untested model.
def test_command_model_by_hand():
    fns = {"t:zone": ["execute if entity @s[advancements={a:b=true}] unless score @s o matches 1.. run function t:admit",
                      "execute if entity @s[gamemode=!creative] unless score @s o matches 1.. run function t:back"],
           "t:admit": ["scoreboard players set @s o 1"], "t:back": ["tp @s 0 64 0"],
           "t:fx": ["execute unless entity @s[x=0,y=0,z=0,distance=..5] run return fail", "say near"]}
    for adv, mode, admitted, back in ((set(), "survival", False, True), ({"a:b"}, "survival", True, False),
                                      (set(), "creative", False, False)):
        w, p = A.World(fns), A.Player(pos=(100.0, 0.0, 0.0))
        p.adv, p.gamemode = set(adv), mode
        w.function("t:zone", p)
        assert (p.scores.get("o") == 1) is admitted
        assert any(d == "t:back" for k, d, *_ in w.log if k == "function") is back
    w = A.World(fns)
    w.function("t:fx", A.Player(pos=(10.0, 0.0, 0.0)))           # 10 > 5: returns before `say`
    assert not any(k == "say" for k, *_ in w.log)
    w.function("t:fx", A.Player(pos=(3.0, 0.0, 0.0)))
    assert any(k == "say" for k, *_ in w.log)


# Protects: the multi-entity model the gates and the callback run on: `execute as @a[box]` forks per player,
# `tp @a[...,tag=!x]` moves only the untagged, `execute as <uuid> if entity @s[type=..,distance=..]` picks an NPC by
# type and place; if removed, the gate and defeat checks would run on an untested model.
def test_multi_entity_model_by_hand():
    fns = {"t:c": ["execute as @a[x=0,y=0,z=0,dx=9,dy=9,dz=9] run tag @s add seen",
                   "tp @a[x=0,y=0,z=0,dx=9,dy=9,dz=9,tag=!ok] 20 0 0 0 0",
                   "execute as N1 if entity @s[type=cobblemon:npc,x=5.5,y=0,z=5.5,distance=..2] as P1 run tag @s add won"]}
    inside_ok, inside, out = (A.Player(uuid="P1", pos=(5.5, 0.0, 5.5)), A.Player(uuid="P2", pos=(2.5, 0.0, 2.5)),
                              A.Player(uuid="P3", pos=(50.5, 0.0, 0.5)))
    inside_ok.tags.add("ok")
    npc = A.Entity("N1", (6.5, 0.0, 5.5))                       # 1 block from (5.5, 0, 5.5): within ..2
    w = A.World(fns, [inside_ok, inside, out, npc])
    w.function("t:c", None)
    # hand: P1 and P2 are in the 10-cube and get 'seen'; P3 is not; only P2 (untagged ok) is moved to x=20;
    # N1 is a cobblemon:npc within 2 of the spot, so P1 gets 'won'
    assert "seen" in inside_ok.tags and "seen" in inside.tags and "seen" not in out.tags
    assert inside.pos == (20.0, 0.0, 0.0) and inside_ok.pos == (5.5, 0.0, 5.5) and out.pos == (50.5, 0.0, 0.5)
    assert "won" in inside_ok.tags and "won" not in inside.tags
    npc.pos = (8.5, 0.0, 5.5)                                    # 3 away: outside ..2
    inside_ok.tags.discard("won")
    A.World(fns, [inside_ok, inside, out, npc]).function("t:c", None)
    assert "won" not in inside_ok.tags


# Protects: the defeat check's machinery on a hand-written callback in the emitted shape: the winner gets the field,
# the loser and a bystander do not; if removed, check_defeat_fields could pass on a model that never runs a callback.
def test_victory_model_by_hand(tmp_path):
    fn = {"cobblers:hq_tower/won_brann": ['runmolang "t.d = q.player.data(); t.d.%s = 1; q.player.save_data();" @s'
                                          % K_B]}
    cb = tmp_path / A.CALLBACK
    cb.parent.mkdir(parents=True)
    cb.write_text("for_each(t.l, c.scriptable_losers, { t.l.is_npc ? { for_each(t.w, c.player_winners, { "
                  "q.run_command('execute as ' + t.l.uuid + ' if entity @s[type=cobblemon:npc,x=10.5,y=64,z=10.5,"
                  "distance=..2] as ' + t.w.player.uuid + ' run function cobblers:hq_tower/won_brann'); }); }; });")
    npc = A.Entity("00000000-0000-0000-0000-000000000001", (10.5, 64.0, 10.5))
    p, q = A.Player(uuid="00000000-0000-0000-0000-0000000000a1"), A.Player(uuid="00000000-0000-0000-0000-0000000000b2")
    A.victory(tmp_path, fn, [npc], [p], [q])
    assert p.data == {K_B: 1} and q.data == {}
    p.data = {}
    A.victory(tmp_path, fn, [p], [npc], [q])                   # hand: the player lost; no player winner
    assert p.data == {}


# Protects: a party member read back from its properties string, hand-written; if removed, the party-equals-team
# check could compare two wrong readings.
def test_parse_properties_by_hand():
    got = A.parse_properties("hariyama level=56 moves=fakeout,closecombat ability=thickfat "
                             "held_item=cobblemon:assault_vest nature=adamant")
    assert got == {"species": "hariyama", "level": 56, "moveset": ["fakeout", "closecombat"], "ability": "thickfat",
                   "heldItem": "assault_vest", "nature": "adamant"}
    assert A.parse_properties("ditto level=5 moves=transform shiny=yes")["shiny"] == "yes"


def corridor_pack(tmp_path, extra=()):
    """A 10-long corridor along x at z=0: floor y0 stone, air y1-y2, ceiling y3, walls rock (unknown).
    The relic pack's layout: index.txt, one function, and a void tag."""
    pack = tmp_path / "relic"
    fdir = pack / "data" / "cobblers" / "function" / "relic_underground"
    fdir.mkdir(parents=True)
    (pack / "data" / "cobblers" / "tags" / "block").mkdir(parents=True)
    (pack / "data" / "cobblers" / "tags" / "block" / "v.json").write_text('{"values": ["minecraft:air"]}')
    lines = ["fill 0 1 0 9 2 0 minecraft:air", "fill 0 0 0 9 0 0 stone", "fill 0 3 0 9 3 0 stone"] + list(extra)
    (fdir / "a.mcfunction").write_text("\n".join(lines) + "\n")
    (fdir / "index.txt").write_text("a\n")
    return pack


# Protects: the replay's fill semantics and the walk; hand: stands are (x, 1, 0) for x 0..9; with x 3..7 forbidden
# only x 0..2 are reached from x=0.
def test_replay_and_walk_by_hand(tmp_path):
    box = (-2, -2, -2, 12, 6, 2)
    cells = A.replay(corridor_pack(tmp_path), box)
    ss = A.stands(cells, box)
    assert ss == {(x, 1, 0) for x in range(10)}
    block = {(x, 1, 0) for x in range(3, 8)}
    assert A.reach(cells, ss, {(0, 1, 0)}, frozenset(block)) == {(0, 1, 0), (1, 1, 0), (2, 1, 0)}
    assert A.reach(cells, ss, {(0, 1, 0)}) == ss


# Protects: `replace <tag>` touches only matching cells and `keep` only open ones; hand: a replace-air-with-glass
# over y1..y3 turns the two air rows to glass and leaves the stone ceiling, so no stand remains.
def test_replay_replace_and_keep_by_hand(tmp_path):
    pack = corridor_pack(tmp_path, ["fill 0 1 0 9 3 0 minecraft:glass replace #cobblers:v",
                                    "fill 0 0 0 0 0 0 minecraft:gold_block keep"])
    cells = A.replay(pack, (-2, -2, -2, 12, 6, 2))
    assert cells[(4, 1, 0)] == cells[(4, 2, 0)] == "minecraft:glass"
    assert cells[(4, 3, 0)] == "minecraft:stone"
    assert cells[(0, 0, 0)] == "minecraft:stone"                          # keep: stone is not open
    assert A.stands(cells, (-2, -2, -2, 12, 6, 2)) == set()


def fake_jar(tmp_path):
    j = tmp_path / "Cobblemon-fabric-1.8.0+test.jar"
    with zipfile.ZipFile(j, "w") as z:
        z.writestr("data/cobblemon/species/generation1/babymon.json",
                   json.dumps({"abilities": ["guts"], "moves": ["20:bite", "egg:wish"]}))
        z.writestr("data/cobblemon/species/generation1/testmon.json",
                   json.dumps({"abilities": ["guts", "h:sturdy"], "preEvolution": "babymon",
                               "moves": ["1:tackle", "30:slam", "tm:surf"]}))
        z.writestr("assets/cobblemon/lang/en_us.json", json.dumps({"item.cobblemon.leftovers": "Leftovers",
                                                                   "item.cobblemon.leftovers.tooltip": "x"}))
    return j


# Protects: legality reads level, TM/egg and the pre-evolution line; hand: at level 25 tackle (1), bite (baby 20),
# surf (tm), wish (baby egg) are legal; slam (30) is not; sturdy (hidden) is a legal ability, blaze is not; the jar
# names one item, leftovers (the tooltip key is not an item).
def test_legality_by_hand(tmp_path):
    sp = A.jar_species(fake_jar(tmp_path))
    ok = {"species": "testmon", "level": 25, "moveset": ["tackle", "bite", "surf", "wish"], "ability": "sturdy"}
    assert A.legality(sp, ok) == []
    bad = A.legality(sp, dict(ok, moveset=["slam"], ability="blaze"))
    assert len(bad) == 2 and "slam" in bad[0] and "blaze" in bad[1]
    assert A.legality(sp, dict(ok, level=30, moveset=["slam"])) == []
    assert A.legality(sp, dict(ok, species="nomon")) == ["species nomon is not in the jar"]
    assert A.jar_items(fake_jar(tmp_path)) == {"leftovers"}


# Protects: the cap is RCT's rule over the first Elite Four member, not a number copied from the finale's data;
# hand: initial 20, relative -2, first member's highest 50 -> 48; relative 0 -> 50; initial 60 wins -> 60.
def test_level_cap_rule_by_hand(tmp_path):
    (tmp_path / "trainers.json").write_text(json.dumps({"trainers": [
        {"class": "elite_four", "order": 2, "rct": {"team": [{"level": 70}]}},
        {"class": "elite_four", "order": 1, "rct": {"team": [{"level": 45}, {"level": 50}]}},
        {"class": "gym_leader", "order": 8, "rct": {"team": [{"level": 99}]}}]}))
    for init, rel, want in ((20, -2, 48), (20, 0, 50), (60, 0, 60)):
        t = tmp_path / "rct.toml"
        t.write_text("initialLevelCap = %d\n\trelativeLevelCap = %d\n" % (init, rel))
        assert A.level_cap_after_gym8(tmp_path, t) == want


# ====================================================================== the real generators, emitted into tmp

def emit(out, mutate=None):
    """The real generators write into `out`; `mutate(ns)` may change a generator in memory first. Returns (packs,
    functions)."""
    import compile_dialogue as CD
    import hq_tower as HQ
    import levelcap_pack as LC
    import progression_pack as PP
    import relic_underground as RU
    import route_trainers as RT
    ns = types.SimpleNamespace(CD=CD, PP=PP, RU=RU, RT=RT, HQ=HQ, LC=LC)
    undo = mutate(ns) if mutate else None
    try:
        files, _done, _ref = CD.build_all(DATA)
        for rel, content in files.items():
            f = out / "cobblers_dialogue" / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        # the level-cap pack (U54): each fight's choice runs its battle_check before the battle
        for rel, text in ns.LC.files(json.loads((DATA / "level_cap.json").read_text(encoding="utf-8"))).items():
            f = out / "cobblers_levelcap" / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        assert RT.main(["--out", str(out / "cobblers_trainers")]) == 0
        assert PP.main(["--out", str(out / "cobblers_progression")]) == 0
        fx = RU.guard_functions(RU.load())["release_fx"]
        f = out / "cobblers_relic_underground" / "data" / "cobblers" / "function" / "relic_underground" / "release_fx.mcfunction"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("\n".join(fx) + "\n", encoding="utf-8")
        # the tower pack's non-block part, as tools/hq_tower.py emit() writes it: the callback, the won functions,
        # the gate cycle (its block functions need the city and are tools/hq_tower_audit.py's)
        spec = HQ.load()
        hq = out / "cobblers_hq_tower"
        for rel, text in HQ.fight_files(spec).items():
            g = hq / rel
            g.parent.mkdir(parents=True, exist_ok=True)
            g.write_text(text, encoding="utf-8")
        g = hq / "data" / "cobblers" / "function" / "hq_tower" / "cycle.mcfunction"
        g.write_text("\n".join(HQ.gate_lines(spec)) + "\n", encoding="utf-8")
        # and Elara's door_admit (2026-10-05), as emit() writes it: her conversation's "Let me through." runs it
        for name, lines in HQ.door_keeper_files(spec).items():
            (g.parent / (name + ".mcfunction")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    finally:
        if undo:
            undo()
    return out, A.LazyFunctions(A.function_index(out))


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    return emit(tmp_path_factory.mktemp("finale_packs"))


RECS = A.finale_ids()


# Protects: both fighters are found by the finale doc's names, both fields are declared per-player booleans, and
# the stage enum holds the chain in its order; if removed, a renamed trainer or a reordered enum goes unseen.
def test_doc_names_fields_and_order():
    assert sorted(RECS) == ["brann", "elara"]
    assert A.check_fields() == []


# Protects: the builder's own record of the order (data/hq_tower.json finale_order) agrees with the brief's chain;
# if removed, the two could drift and each look right alone.
def test_finale_order_matches_the_chain():
    assert A.check_finale_order() == []


# Protects: the post-gym-8 cap is 60 (docs/mechanics/LEAGUE_LEVEL_CAP.md: "After gym 8 the cap stays at 60"),
# derived from RCT's rule and the Elite Four data; if removed, a cap change would go unnoticed by the party check.
def test_the_cap_after_gym_8_is_60():
    assert A.level_cap_after_gym8() == 60


# Protects: each fighting NPC's class carries exactly data/finale_trainers.json's team, under the cap, legal in the
# jar (when found), never challengeable by a click; if removed, an over-cap, illegal or drifted party ships.
def test_emitted_parties(real):
    packs, _f = real
    jar = A.find_jar()
    bad, notes = A.check_parties(packs, RECS, 60, jar)
    if jar is None:
        bad = [b for b in bad if not b.startswith("no Cobblemon 1.8 jar")]
    assert bad == [], bad
    assert len(notes) == 2


# Protects: THE CALLBACK RULE. Beating Brann (Elara) at the spot R18HQ places them writes brann_defeated
# (elara_defeated) for every winning player and for nobody else; a loss, another NPC and an NPC elsewhere write
# nothing; if removed, one fight could count for another or for a bystander.
def test_each_defeat_sets_only_its_own_field(real):
    packs, fns = real
    assert A.check_defeat_fields(packs, fns) == []


# Protects: THE CHAIN. Every chain conversation from every start state: each stage written only by its scene, only
# from its stage and with its fight won; fights only at their stage; the grant only at cradle_open with both, and
# reachable there; if removed, nothing executes the compiled gates.
def test_compiled_conversations_follow_the_chain(real):
    packs, fns = real
    bad, notes = A.check_conversation(packs, fns)
    assert bad == [], bad[:5]
    # hand: nia/oren 1 stage x 9 field pairs x 2 flag x 3 cursors = 54; brann/elara 4 cursors -> 72; the binder's
    # rule needs both fields 1: 1 x 1 x 2 x 3 = 6
    assert "{'nia': 54, 'brann': 72, 'oren': 54, 'elara': 72, 'binder': 6}" in notes[0], notes


# Protects: each write carries its own guard (a page run directly, as a restored cursor would); if removed, a
# transition guarded only by the entry route could ship without its condition.
def test_every_write_carries_its_own_guard(real):
    packs, fns = real
    assert A.check_guards(packs, fns) == []


# Protects: the story end to end, all five in any order with both battle outcomes: the flag is reachable from
# rift_crisis_pending and no state breaks the order; if removed, per-conversation rules could hold while the
# sequence a player walks does not.
def test_the_story_reaches_the_release_in_order(real):
    packs, fns = real
    bad, notes = A.check_story(packs, fns)
    assert bad == [], bad[:5]
    assert "rift_released" in notes[0]


# Protects: THE LEVEL CAP at the two finale fights (sweep U54, review N57; test-author 2026-10-07, not the builder of
# 85be563). Brann and Elara are cobblemon:npc, outside rctmod's own refusal: a party strictly over the cap never starts
# their fight, is shown the AUTHORED over_cap_node and changes nothing; at the cap, and with a cap that does not read,
# the fight starts; from every state a refusal leaves, a party back under the cap reaches the fight (no trap). If
# removed, a level-100 Pokemon fights the finale again and nothing says so. Not covered: that `rctmod player get
# level_cap` and q.player.party.highest_level answer in game as modelled, and that a tag set by a nested run_command
# is visible to the dialogue's next expression (an experiment).
def test_an_over_cap_party_never_fights_brann_or_elara_and_is_never_trapped(real):
    packs, fns = real
    bad, notes = A.check_over_cap(packs, fns)
    assert bad == [], bad[:5]
    # hand: start states with the fight open = the one stage x fight field unset/0 (2) x the other field (3) x flag (2)
    # x the 4 cursors test_compiled_conversations_follow_the_chain counts = 48 each; a refusal leaves at least one
    for who in ("brann", "elara"):
        m = re.search(r"'%s': \((\d+), (\d+)\)" % who, notes[0])
        assert m and int(m.group(1)) == 48 and int(m.group(2)) > 0, notes


def ignore_the_overcap_tag(ns):
    real = ns.CD.Compiler.battle_action

    def battle_action(self, a):
        return real(self, a).replace("q.player.has_tag('", "q.player.has_tag('x")
    ns.CD.Compiler.battle_action = battle_action
    return lambda: setattr(ns.CD.Compiler, "battle_action", real)


# Protects: INDEPENDENCE of the over-cap check. compile_dialogue reading a tag battle_check never sets (data untouched)
# must let the over-cap party fight; if this passes, check_over_cap is not executing the compiled gate.
def test_mutation_dialogue_ignores_the_overcap_tag(tmp_path):
    packs, fns = emit(tmp_path, ignore_the_overcap_tag)
    bad, _ = A.check_over_cap(packs, fns)
    assert any("over a cap of" in b and "starts the fight" in b for b in bad), bad[:3]


LC_SRC = (ROOT / "tools" / "levelcap_pack.py").read_text(encoding="utf-8")


def levelcap_mutant(old, new):
    """tools/levelcap_pack.py's SOURCE mutated (data/level_cap.json untouched); emit() writes the pack from it."""
    assert LC_SRC.count(old) == 1, "mutant no longer matches tools/levelcap_pack.py: re-aim it (%r)" % old[:60]

    def mutate(ns):
        mod = types.ModuleType("levelcap_pack_under_test")
        mod.__file__ = str(ROOT / "tools" / "levelcap_pack.py")
        exec(compile(LC_SRC.replace(old, new), "levelcap_pack_under_test", "exec"), mod.__dict__)
        ns.LC = mod
        return None
    return mutate


# Protects: INDEPENDENCE of the boundary. party_compare at-or-over (`>=`) must refuse a party AT the cap, so the fight
# never starts there; if this passes, the check does not read the emitted comparison.
def test_mutation_levelcap_at_or_over_refuses_at_the_cap(tmp_path):
    packs, fns = emit(tmp_path, levelcap_mutant("highest_level > $(cap)", "highest_level >= $(cap)"))
    bad, _ = A.check_over_cap(packs, fns)
    assert any("at the cap never starts the fight" in b for b in bad), bad[:3]


# Protects: INDEPENDENCE of the fail-open direction. battle_check tagging a player whose cap does not read must stop
# the fight; if this passes, a fail-closed regression (the finale walled off while RCT is unreadable) goes unseen.
def test_mutation_levelcap_fail_closed_blocks_the_finale(tmp_path):
    old = ('"$execute store result score @s %s run rctmod player get level_cap @s$(x)" % CAP,\n'
           '            "execute unless score @s %s matches 1.. run return 0" % CAP,')
    new = ('"$execute store result score @s %s run rctmod player get level_cap @s$(x)" % CAP,\n'
           '            "execute unless score @s %s matches 1.. run tag @s add %s" % (CAP, PARTY_OVER),\n'
           '            "execute unless score @s %s matches 1.. run return 0" % CAP,')
    packs, fns = emit(tmp_path, levelcap_mutant(old, new))
    bad, _ = A.check_over_cap(packs, fns)
    assert any("with a cap that does not read never starts the fight" in b for b in bad), bad[:3]


def refusal_ends_the_chain(ns):
    real = ns.CD.Compiler.battle_action

    def battle_action(self, a):
        # the refusal also writes the stage back a step: a refusal that edits the story (and strands the player)
        out = real(self, a)
        return out.replace("q.player.has_tag('%s') ? { " % "cobblers.party_overcap",
                           "q.player.has_tag('%s') ? { t.d.%s = 'rift_crisis_pending'; "
                           % ("cobblers.party_overcap", A.key(A.STAGE)), 1)
    ns.CD.Compiler.battle_action = battle_action
    return lambda: setattr(ns.CD.Compiler, "battle_action", real)


# Protects: INDEPENDENCE of the no-trap / no-change half. A refusal that also moves the stage (data untouched) must be
# reported -- as a story change, and as a trap, since the fight's stage is gone; if this passes, a refusal that
# strands the player would go unseen.
def test_mutation_a_refusal_that_moves_the_story_is_reported(tmp_path):
    packs, fns = emit(tmp_path, refusal_ends_the_chain)
    bad, _ = A.check_over_cap(packs, fns)
    assert any("changes the story" in b for b in bad), bad[:3]


# Protects: the release writes the doc's stage and League cursor and runs release_fx after the grant, @s only,
# changing nothing; if removed, a release_fx that spawns or broadcasts would pass.
def test_release_effects(real):
    packs, fns = real
    assert A.check_release_effects(packs, fns) == []


# Protects: the flag's advancement cannot be earned by any criterion; if removed, a tick or location trigger could
# grant it with no release.
def test_flag_advancement_is_impossible(real):
    packs, _f = real
    assert A.check_progression(packs) == []


# Protects: the door and climb gates per stage, per player, in one cycle: open from deep_handoff_received and
# hq_crossed, set-backs outside their gates, creative passes; if removed, a gate open a stage early or trapping a
# player goes unseen.
def test_gates_per_stage(real):
    _packs, fns = real
    bad, notes = A.check_gates(fns)
    assert bad == [], bad[:5]
    assert "126 players" in notes[0]                     # hand: 21 stage values x 3 places x 2 modes


# Protects: no other emitted file grants the flag, writes a defeat field, calls a won function or writes a chain
# stage; if removed, a second setter anywhere would open z5 or the tower behind the chain's back.
def test_sweep_finds_one_setter_each(real):
    packs, _f = real
    bad, seen = A.check_sweep(packs)
    assert bad == [], bad
    assert seen["grant_callers"] == ["cobblers_dialogue/data/cobblers/dialogues/%s.json" % A.CONV]


# Protects: the sweep's detector, by planting setters; hand: one extra function calling the grant, `advancement
# grant @a everything`, and a molang writing elara_defeated must each be named.
def test_sweep_names_planted_setters(real, tmp_path):
    packs, _f = real
    planted = tmp_path / "packs"
    shutil.copytree(packs, planted)
    f = planted / "rogue" / "data" / "cobblers" / "function" / "x.mcfunction"
    f.parent.mkdir(parents=True)
    f.write_text("function %s\nadvancement grant @a everything\n" % A.FLAG_GRANT_FN)
    g = planted / "rogue" / "data" / "cobblemon" / "callbacks" / "battle_victory" / "y.molang"
    g.parent.mkdir(parents=True)
    g.write_text("t.d = q.player.data(); t.d.%s = 1;" % K_E)
    bad, _ = A.check_sweep(planted)
    assert any("rogue/data/cobblers/function/x.mcfunction" in b and "only" in b for b in bad)
    assert any("everything" in b for b in bad)
    assert any("rogue/data/cobblemon/callbacks/battle_victory/y.molang" in b for b in bad)


# ====================================================================== mutations: the GENERATOR changed, data not

def drop_brann_from_hq_crossed(ns):
    real_t = ns.CD.Compiler.transition

    def transition(self, tid):
        if tid != "record_hq_crossed":
            return real_t(self, tid)
        real_cond = self.cond
        self.cond = lambda c, probes: "1" if c.get("field") == A.BRANN_FIELD else real_cond(c, probes)
        try:
            return real_t(self, tid)
        finally:
            del self.cond
    ns.CD.Compiler.transition = transition
    return lambda: setattr(ns.CD.Compiler, "transition", real_t)


# Protects: INDEPENDENCE. compile_dialogue emitting record_hq_crossed without its brann_defeated guard
# (data/quests.json untouched) must fail the guard check; if removed, the transition's own condition is unaudited
# (the entry route alone hides it from the walk -- which is why check_guards exists).
def test_mutation_hq_crossed_loses_its_brann_guard(tmp_path):
    packs, fns = emit(tmp_path, drop_brann_from_hq_crossed)
    bad = A.check_guards(packs, fns)
    assert any("writes hq_crossed without" in b for b in bad), bad[:3]


def drop_elara(ns):
    real_cond = ns.CD.Compiler.cond

    def cond(self, c, probes):
        if c.get("kind") == "progression_equals" and c.get("field") == A.ELARA_FIELD:
            return "1"
        return real_cond(self, c, probes)
    ns.CD.Compiler.cond = cond
    return lambda: setattr(ns.CD.Compiler, "cond", real_cond)


# Protects: INDEPENDENCE. compile_dialogue compiling every elara_defeated condition to "1" (data/dialogue.json and
# data/quests.json untouched) must fail the chain walk; if removed, the audit could share the compiler's blind spot.
def test_mutation_compiler_drops_elara(tmp_path):
    packs, fns = emit(tmp_path, drop_elara)
    bad, _ = A.check_conversation(packs, fns)
    assert any("fails the rule" in b or "without" in b for b in bad), bad[:3]


def move_callback_spot(ns):
    real_spot = ns.HQ._fight_spot

    def spot(spec, f):
        x, y, z = real_spot(spec, f)
        return [x + 3, y, z] if f["npc"] == "npc_finale_brann_saye" else [x, y, z]
    ns.HQ._fight_spot = spot
    return lambda: setattr(ns.HQ, "_fight_spot", real_spot)


# Protects: INDEPENDENCE of the callback check. hq_tower matching Brann three blocks east of where R18HQ places him
# (data/hq_tower.json untouched) must fail: beating him records nothing, and the story never reaches the release;
# if removed, the callback's selector could drift from the placement unseen.
def test_mutation_callback_matches_the_wrong_spot(tmp_path):
    packs, fns = emit(tmp_path, move_callback_spot)
    bad = A.check_defeat_fields(packs, fns)
    assert any("one player beats brann" in b for b in bad), bad
    sbad, _ = A.check_story(packs, fns)
    assert any("never reaches" in b for b in sbad), sbad


def widen_callback(ns):
    real_ff = ns.HQ.fight_files

    def ff(spec=None):
        return {k: v.replace("distance=..2]", "distance=..64]") for k, v in real_ff(spec).items()}
    ns.HQ.fight_files = ff
    return lambda: setattr(ns.HQ, "fight_files", real_ff)


# Protects: INDEPENDENCE. hq_tower's callback matching any NPC within 64 of the spot must fail: beating Oren (6 above
# Elara) or a far NPC would count as beating Elara; if removed, "only when the loser is that NPC" is unaudited.
def test_mutation_callback_matches_any_nearby_npc(tmp_path):
    packs, fns = emit(tmp_path, widen_callback)
    bad = A.check_defeat_fields(packs, fns)
    assert any("is beaten: player" in b for b in bad), bad


def climb_early(ns):
    real_sf = ns.HQ.stages_from

    def sf(stage):
        return real_sf("deep_handoff_received" if stage == "hq_crossed" else stage)
    ns.HQ.stages_from = sf
    return lambda: setattr(ns.HQ, "stages_from", real_sf)


# Protects: INDEPENDENCE of the gate check. hq_tower opening the climb at deep_handoff_received (data untouched)
# must fail: a player who has not crossed Brann stays above the hall; if removed, the climb gate is unaudited.
def test_mutation_climb_opens_a_stage_early(tmp_path):
    _packs, fns = emit(tmp_path, climb_early)
    bad, _ = A.check_gates(fns)
    # hand: that player should be set onto the hall's floor; with the climb open they stay on the top storey
    assert any("stage deep_handoff_received on the top storey is moved to (3433.5, 128.0, 3308.5)" in b for b in bad), bad


def level_up_ace(ns):
    real_bc = ns.CD.battle_class

    def bc(nb, data_dir=None):
        out = real_bc(nb, data_dir)
        mons = out["party"]["pokemon"]
        mons[-1] = mons[-1].replace("level=60", "level=61").replace("level=58", "level=59")
        return out
    ns.CD.battle_class = bc
    return lambda: setattr(ns.CD, "battle_class", real_bc)


# Protects: INDEPENDENCE of the party check. compile_dialogue raising each ace a level (data untouched) must fail:
# the party no longer equals the team, and Elara's ace is over the cap; if removed, a drifted party ships.
def test_mutation_party_drifts_from_the_team(tmp_path):
    packs, _f = emit(tmp_path, level_up_ace)
    bad, _ = A.check_parties(packs, RECS, 60, None)
    assert any("is not data/finale_trainers.json's team" in b for b in bad), bad
    assert any("over the post-gym-8 cap" in b for b in bad), bad


def earnable_flag(ns):
    real_adv = ns.PP._flag_advancement

    def adv(n, flag):
        out = real_adv(n, flag)
        if flag["id"] == A.FLAG:
            out["criteria"] = {"t": {"trigger": "minecraft:tick"}}
        return out
    ns.PP._flag_advancement = adv
    return lambda: setattr(ns.PP, "_flag_advancement", real_adv)


# Protects: progression_pack emitting an earnable flag advancement fails the audit; if removed, the flag could be
# set by a tick with no release.
def test_mutation_flag_made_earnable(tmp_path):
    packs, _f = emit(tmp_path, earnable_flag)
    assert any("can be earned" in b for b in A.check_progression(packs))


def fx_for_all(ns):
    real_fx = ns.RU.release_fx_lines

    def fx(spec):
        return [l.replace(" @s", " @a") for l in real_fx(spec)]
    ns.RU.release_fx_lines = fx
    return lambda: setattr(ns.RU, "release_fx_lines", real_fx)


# Protects: relic_underground's release_fx shown to every player fails the audit; if removed, a partner who has not
# released would see the restraint go dark.
def test_mutation_release_fx_for_everyone(tmp_path):
    packs, fns = emit(tmp_path, fx_for_all)
    bad = A.check_release_effects(packs, fns)
    assert any("particle to more than the releasing player" in b for b in bad), bad
    assert any("sound to more than the releasing player" in b for b in bad), bad


# ====================================================================== Elara at the door (c2ef17c, 2026-10-05)
# Re-pointed by a second test-author who did not build the door keeper. Expectations come from the door GATE's stage
# (data/hq_tower.json gates.door.from_stage, which must equal the brief's DOOR_OPEN) and the tower's interior, from
# where R18HQ places her and her yaw, and from the EMITTED conversation and cycle -- never from door_keeper or
# tools/hq_tower.py check_door_keeper(). Not covered: anything in game (her body as a blocker, two players at once).

# Protects: Elara lets a player into the tower only at a door stage, from every action of her conversation run
# directly; every door stage gets in (anchor_shutdown only after her fight); her admit lands where the cycle leaves a
# door-stage player alone; behind her a player of any stage is set out in front of her; the threshold just inside is
# not ejected. If removed, a door keeper who admits early, strands a player inside or traps one behind her ships.
def test_door_keeper_admits_at_the_door_stages_and_strands_nobody(real):
    packs, fns = real
    bad, notes = A.check_door_keeper(packs, fns)
    assert bad == [], bad[:5]
    vals = A.stage_values()
    door_from = json.loads((DATA / "hq_tower.json").read_text(encoding="utf-8"))["gates"]["door"]["from_stage"]
    assert "admitted at %s" % vals[vals.index(door_from):] in notes[0], notes


# Protects: the battle precedes cradle_open and is Elara's only fight: in the story walk every state at cradle_open
# or later holds elara_defeated, and her conversation starts a battle only at anchor_shutdown (rule_events); if
# removed, the door's new pages could write the release stage without the fight.
def test_elara_fights_once_before_cradle_open(real):
    packs, fns = real
    bad, _ = A.check_conversation(packs, fns, only={"elara"})
    assert bad == [], bad[:5]
    sbad, notes = A.check_story(packs, fns)
    assert not [b for b in sbad if "elara" in b or "cradle_open" in b], sbad
    assert notes[0].endswith("'cradle_open', 'rift_released']"), notes


def admit_early(ns):
    real_t = ns.CD.Compiler.transition

    def transition(self, tid):
        if tid != "elara_door_admit":
            return real_t(self, tid)
        real_cond = self.cond
        self.cond = lambda c, probes: "1" if c.get("field") == A.STAGE else real_cond(c, probes)
        try:
            return real_t(self, tid)
        finally:
            del self.cond
    ns.CD.Compiler.transition = transition
    return lambda: setattr(ns.CD.Compiler, "transition", real_t)


# Protects: INDEPENDENCE of the admit's stage rule. compile_dialogue emitting elara_door_admit with its stage
# condition compiled to "1" (data/quests.json untouched) must fail: a player before Nia's packet gets in past her.
def test_mutation_admit_at_a_wrong_stage(tmp_path):
    packs, fns = emit(tmp_path, admit_early)
    bad, _ = A.check_door_keeper(packs, fns)
    assert any("lets a player at stage rift_crisis_pending into the tower" in b for b in bad), bad[:3]


def admit_into_the_hole(ns):
    real_dk = ns.HQ.door_keeper_files

    def dk(spec):
        return {k: [l.replace("tp @s 3436.5 ", "tp @s 3438.5 ") for l in v] for k, v in real_dk(spec).items()}
    ns.HQ.door_keeper_files = dk
    return lambda: setattr(ns.HQ, "door_keeper_files", real_dk)


# Protects: INDEPENDENCE of the landing. hq_tower's door_admit moving the player into the cell behind Elara (data
# untouched) must fail: the cycle sends them straight back out, so nobody ever gets in.
def test_mutation_admit_lands_behind_her(tmp_path):
    packs, fns = emit(tmp_path, admit_into_the_hole)
    bad, _ = A.check_door_keeper(packs, fns)
    assert any("is never let in" in b for b in bad), bad[:3]


def exit_widened_inward(ns):
    real_gl = ns.HQ.gate_lines

    def gl(spec):
        return [l.replace("x=3438,y=67,z=3306,dx=0,", "x=3437,y=67,z=3306,dx=1,") for l in real_gl(spec)]
    ns.HQ.gate_lines = gl
    return lambda: setattr(ns.HQ, "gate_lines", real_gl)


# Protects: INDEPENDENCE of "the exit cannot strand". hq_tower's step-out selector reaching one cell inward (data
# untouched) must fail: a door-stage player on the threshold inside is ejected.
def test_mutation_exit_ejects_the_threshold(tmp_path):
    packs, fns = emit(tmp_path, exit_widened_inward)
    bad, _ = A.check_door_keeper(packs, fns)
    assert any("legitimately inside" in b for b in bad), bad[:3]


# Protects: INDEPENDENCE of her stand. tools/hq_tower.py npc_placements() (R18HQ's spawn list) putting Elara one cell
# in, at the doorway's inner cell (data untouched), must fail: she no longer faces the corridor from the doorway.
def test_mutation_elara_at_the_inner_cell(real, monkeypatch):
    import hq_tower as HQ
    packs, fns = real
    real_np = HQ.npc_placements
    monkeypatch.setattr(HQ, "npc_placements", lambda spec=None: [
        (c, (at[0] - 1, at[1], at[2]) if cls.endswith("npc_finale_elara_venn") else at, cls, yaw)
        for c, at, cls, yaw in real_np(spec)])
    bad, _ = A.check_door_keeper(packs, fns)
    assert any("does not stand in the doorway facing out" in b for b in bad), bad[:3]


# ====================================================================== the built packs, when prepare made them

RELIC = BUILT / "cobblers_relic_underground" / "data" / "cobblers" / "function" / "relic_underground" / "index.txt"


# Protects: the binder's stand is reachable from the passage in the cradle AS BUILT; if removed, a dressing block
# or a sealed cut could leave the release unspeakable.
@pytest.mark.skipif(not RELIC.is_file(), reason="build/datapacks/cobblers_relic_underground not built (needs the "
                                                "Rift skin's pack); prepare runs the audit")
def test_cradle_binder_reachable_as_built(tmp_path):
    packs = emit(tmp_path)[0]
    shutil.rmtree(packs / "cobblers_relic_underground")
    shutil.copytree(BUILT / "cobblers_relic_underground", packs / "cobblers_relic_underground")
    bad, notes = A.check_cradle(packs, A.LazyFunctions(A.function_index(packs)))
    assert bad == [], bad
    assert "among them" in notes[0]


Z5 = BUILT / "cobblers_rift_zones" / "data" / "cobblers" / "function" / "rift_zones" / "z5" / "zone.mcfunction"


# Protects: z5 admits a flag holder anywhere (qualify on entry) and turns back a survival player without it; if
# removed, the flag could stop opening the League precinct.
@pytest.mark.skipif(not Z5.is_file(), reason="build/datapacks/cobblers_rift_zones not built")
def test_z5_opens_on_the_flag():
    assert A.check_z5(BUILT, A.LazyFunctions(A.function_index(BUILT))) == []


# Protects: the audits run in prepare after every pack they read is built; if removed, they would read a stale or
# missing pack, or never run.
def test_prepare_runs_the_audits_after_their_inputs():
    import reapply
    names = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root="", server_dir=""))]
    at = names.index("finale_audit")
    # levelcap_pack (U54): the fights' choices call its battle_check, which must be built before the audit reads it
    for before in ("compile_dialogue", "route_trainers", "progression_pack", "relic_underground:build",
                   "rift_zones:build", "hq_tower:build", "levelcap_pack"):
        assert names.index(before) < at, before
    at = names.index("hq_tower_audit")
    for before in ("deep_city:build", "relic_underground:build", "hq_tower:build", "route_trainers"):
        assert names.index(before) < at, before
