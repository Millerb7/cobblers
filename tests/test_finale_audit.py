"""tools/finale_audit.py: the independent audit of the Rift finale's confrontation and release.

Written by test-author, 2026-10-04; the finale (3e0f5ad, d968d79) and the z5 admit (33c277c) were built by another
agent. Three kinds of test:

  synthetic   the audit's own machinery (Molang interpreter, command model, cell replay and walk, jar legality, the
              cap rule) on hand-written fixtures whose answers are computed by hand in the comments
  real        the REAL generators emit into tmp (compile_dialogue --all, route_trainers, progression_pack, release_fx),
              and the audit reads what they wrote; the relic and z5 packs only when build/datapacks holds them
  mutation    a GENERATOR is changed in memory (data untouched) and the audit must fail: the elara condition dropped
              in compile_dialogue, the won function writing the wrong key in route_trainers, the flag made earnable in
              progression_pack, release_fx shown to everyone, Brann's home moved in the cycle

Not covered: anything in game (see the tool's docstring). The cradle and z5 tests skip when the packs are not built,
because building them needs the Rift skin's pack (derived/rift_sculpt); prepare runs the audit after both.
"""
import json
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
    return " && ".join(["(t.d.%s == 'rift_crisis_pending')" % K_STAGE] + ["(t.d.%s == 1)" % f for f in fields])


def tiny_dialogue(visible_fields, guard_fields):
    """A three-page conversation in the compiler's emitted shape: open -> ask (choice) -> release (grants on ack).
    `visible_fields` gate the choice, `guard_fields` gate the grant."""
    grant = ("(%s) ? { q.run_command('execute as ' + q.player.uuid + ' at @s run function %s'); t.d.%s = '%s'; "
             "q.player.save_data(); };" % (gate(*guard_fields), A.FLAG_GRANT_FN, K_STAGE, A.RELEASED))
    return {
        "initializationAction": "t.d = q.player.data(); v.e = 0; (v.e == 0 && t.d.%s == 'rift_crisis_pending') ? "
                                "{ v.e = 'ask'; }; v.e == 0 ? { q.dialogue.close(); } : { q.dialogue.set_page(v.e); };"
                                % K_STAGE,
        "pages": [
            {"id": "ask", "input": {"type": "option", "options": [
                {"text": A.CHOICE, "value": "r", "action": "t.d = q.player.data(); q.dialogue.set_page('release');",
                 "isVisible": "t.d = q.player.data(); return (%s);" % gate(*visible_fields)},
                {"text": "Not yet.", "value": "n", "action": "q.dialogue.close();"}]}},
            {"id": "release", "input": "t.d = q.player.data(); %s q.dialogue.close();" % grant},
        ]}


GRANT_FN = {A.FLAG_GRANT_FN: ["advancement grant @s only %s" % A.FLAG_ADV]}


# Protects: the walk finds the grant from the rule's state and from no other; if removed, a leak in the walker
# itself (e.g. never taking an option) would let every real conversation pass.
def test_walk_grants_only_at_the_rule_on_a_correct_fixture():
    dlg = tiny_dialogue([K_B, K_E], [K_B, K_E])
    # hand: (pending, 1, 1) opens 'ask', the choice is visible, 'release' runs the grant once
    g, _n, offered = A.walk(dlg, GRANT_FN, ({K_STAGE: A.PENDING, K_B: 1, K_E: 1}, set()))
    assert offered and len(g) == 1 and A.contract(g[0][0])
    # hand: (pending, 1, unset) opens 'ask' but the choice is hidden; no grant
    g, _n, offered = A.walk(dlg, GRANT_FN, ({K_STAGE: A.PENDING, K_B: 1}, set()))
    assert not offered and g == []
    # hand: wrong stage closes at once
    g, _n, offered = A.walk(dlg, GRANT_FN, ({K_STAGE: A.RELEASED, K_B: 1, K_E: 1}, set()))
    assert not offered and g == []


# Protects: a gate missing one field is caught by check_conversation; if removed, the audit could pass a release
# that needs only Brann.
def test_check_conversation_flags_a_gate_that_forgets_elara(tmp_path):
    for dlg, leaky in ((tiny_dialogue([K_B, K_E], [K_B, K_E]), False), (tiny_dialogue([K_B], [K_B]), True)):
        p = tmp_path / ("leaky" if leaky else "ok")
        f = p / "cobblers_dialogue" / "data" / "cobblers" / "dialogues" / ("%s.json" % A.CONV)
        f.parent.mkdir(parents=True)
        f.write_text(json.dumps(dlg), encoding="utf-8")
        bad, _ = A.check_conversation(p, GRANT_FN, DATA)
        if leaky:
            # hand: from (pending, brann 1, elara unset/0) the choice shows and the grant runs
            assert any("fails the rule" in b for b in bad) and any("is shown from" in b for b in bad)
        else:
            assert bad == []


# Protects: a visible choice whose TRANSITION still guards both is reported (shown where the rule fails) even
# though no grant leaks; if removed, a player could be offered a release that silently does nothing.
def test_check_conversation_reports_a_choice_shown_but_guarded(tmp_path):
    f = tmp_path / "cobblers_dialogue" / "data" / "cobblers" / "dialogues" / ("%s.json" % A.CONV)
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps(tiny_dialogue([K_B], [K_B, K_E])), encoding="utf-8")
    bad, _ = A.check_conversation(tmp_path, GRANT_FN, DATA)
    assert any("is shown from" in b for b in bad)
    assert not any("fails the rule" in b for b in bad)


# Protects: the Molang interpreter's semantics the walk rests on: an unset key reads 0, strings never equal
# numbers, `+` concatenates, ternary blocks; if removed, a wrong interpreter could agree with a wrong compiler.
def test_molang_semantics_by_hand():
    w, p = A.World({}), A.Player(uuid="U")
    m = A.Molang(w, p)
    assert m.run("t.d = q.player.data(); return t.d.missing;") == 0
    assert m.run("return ('a' == 0);") == 0
    assert m.run("return ('x' + q.player.uuid);") == "xU"
    m.run("t.d = q.player.data(); (t.d.k == 0) ? { t.d.k = 2; } : { t.d.k = 3; }; t.d.j = !(t.d.k == 2);")
    assert p.data == {"k": 2, "j": 0}


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


# Protects: the replay's fill semantics and the stand/sight walk; hand: stands are (x, 1, 0) for x 0..9, a trainer
# at (5.5, 1, 0.5) with sight 2 sees x 3..7, so from x=0 only x 0..2 are reached without entering it.
def test_replay_and_sight_walk_by_hand(tmp_path):
    box = (-2, -2, -2, 12, 6, 2)
    cells = A.replay(corridor_pack(tmp_path), box)
    ss = A.stands(cells, box)
    assert ss == {(x, 1, 0) for x in range(10)}
    sight = {c for c in ss if abs(c[0] + 0.5 - 5.5) <= 2}
    assert sight == {(x, 1, 0) for x in range(3, 8)}
    assert A.reach(cells, ss, {(0, 1, 0)}, frozenset(sight)) == {(0, 1, 0), (1, 1, 0), (2, 1, 0)}
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
    return j


# Protects: legality reads level, TM/egg and the pre-evolution line; hand: at level 25 tackle (1), bite (baby 20),
# surf (tm), wish (baby egg) are legal; slam (30) is not; sturdy (hidden) is a legal ability, blaze is not.
def test_legality_by_hand(tmp_path):
    sp = A.jar_species(fake_jar(tmp_path))
    ok = {"species": "testmon", "level": 25, "moveset": ["tackle", "bite", "surf", "wish"], "ability": "sturdy"}
    assert A.legality(sp, ok) == []
    bad = A.legality(sp, dict(ok, moveset=["slam"], ability="blaze"))
    assert len(bad) == 2 and "slam" in bad[0] and "blaze" in bad[1]
    assert A.legality(sp, dict(ok, level=30, moveset=["slam"])) == []
    assert A.legality(sp, dict(ok, species="nomon")) == ["species nomon is not in the jar"]


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
    import progression_pack as PP
    import relic_underground as RU
    import route_trainers as RT
    ns = types.SimpleNamespace(CD=CD, PP=PP, RU=RU, RT=RT)
    undo = mutate(ns) if mutate else None
    try:
        files, _done, _ref = CD.build_all(DATA)
        for rel, content in files.items():
            f = out / "cobblers_dialogue" / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        assert RT.main(["--out", str(out / "cobblers_trainers")]) == 0
        assert PP.main(["--out", str(out / "cobblers_progression")]) == 0
        fx = RU.guard_functions(RU.load())["release_fx"]
        f = out / "cobblers_relic_underground" / "data" / "cobblers" / "function" / "relic_underground" / "release_fx.mcfunction"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("\n".join(fx) + "\n", encoding="utf-8")
    finally:
        if undo:
            undo()
    return out, A.LazyFunctions(A.function_index(out))


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    return emit(tmp_path_factory.mktemp("finale_packs"))


IDS = A.finale_ids()


# Protects: both trainers are found by the finale doc's names and both fields are declared per-player booleans; if
# removed, a renamed trainer would leave every later check auditing nothing.
def test_doc_names_and_fields():
    assert sorted(IDS) == ["brann", "elara"]
    assert A.check_fields() == []


# Protects: the post-gym-8 cap is 60 (docs/mechanics/LEAGUE_LEVEL_CAP.md: "After gym 8 the cap stays at 60"),
# derived from RCT's rule and the Elite Four data; if removed, a cap change would go unnoticed by the team check.
def test_the_cap_after_gym_8_is_60():
    assert A.level_cap_after_gym8() == 60


# Protects: the emitted rctmod teams are under the cap, beaten once, outside any series, and (with the jar) legal;
# if removed, an over-cap or illegal team ships.
def test_emitted_trainers(real):
    packs, _f = real
    jar = A.find_jar()
    bad, notes = A.check_trainers(packs, IDS, 60, jar)
    if jar is None:
        bad = [b for b in bad if not b.startswith("no Cobblemon 1.8 jar")]
    assert bad == [], bad
    assert len(notes) == 2


# Protects: beating one trainer sets exactly its own field through the emitted advancement and won function; if
# removed, a won function writing the other trainer's field would let one win open the release.
def test_each_defeat_sets_only_its_own_field(real):
    packs, fns = real
    assert A.check_defeat_fields(packs, fns, IDS) == []


# Protects: THE RULE. Every start state walked through the compiled conversation: the grant only at
# rift_crisis_pending with both fields, and reachable from every such state; if removed, nothing executes the
# compiled gate.
def test_compiled_conversation_grants_only_under_the_rule(real):
    packs, fns = real
    bad, notes = A.check_conversation(packs, fns)
    assert bad == [], bad[:5]
    assert "the grant reachable from 6" in notes[0]          # 3 cursors x flag held or not, at (pending, 1, 1)


# Protects: the story path in order, on emitted artifacts only: briefing, Brann, still closed, Elara, release once,
# then the repeat; if removed, the per-path guarantees above could hold while the sequence a player walks does not.
def test_the_story_path_end_to_end(real):
    packs, fns = real
    dlg = A.dialogue_of(packs)
    p = A.Player()
    p.data = {K_STAGE: A.PENDING}

    def talk():
        g, _n, offered = A.walk(dlg, fns, (dict(p.data), set(p.adv)))
        return g, offered

    assert talk() == ([], False)                                         # the briefing, no release
    A.defeat_events(packs, fns, IDS["brann"], p, A.World(fns))
    assert p.data[K_B] == 1 and talk() == ([], False)                    # one win is not enough
    A.defeat_events(packs, fns, IDS["elara"], p, A.World(fns))
    g, offered = talk()
    # both: the release is offered and every grant on every path runs under the rule (the walk counts each path)
    assert offered and g and all(A.contract(d) for d, _a in g)
    w = A.World(fns)
    page = next(x for x in dlg["pages"] if x["id"] == "release_001")
    A.Molang(w, p).run(page["input"])
    assert A.FLAG_ADV in p.adv and p.data[K_STAGE] == A.RELEASED
    assert talk() == ([], False)                                         # after the flag: never again


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


# Protects: no other emitted file grants the flag or writes a defeat field; if removed, a second setter anywhere
# would open z5 behind the confrontation's back.
def test_sweep_finds_one_setter(real):
    packs, _f = real
    bad, seen = A.check_sweep(packs, IDS)
    assert bad == [], bad
    assert seen["grant_callers"] == ["cobblers_dialogue/data/cobblers/dialogues/%s.json" % A.CONV]


# Protects: the sweep's detector, by planting a second setter; hand: one extra function calling the grant must be
# named, and `advancement grant @a everything` must be named.
def test_sweep_names_a_planted_setter(real, tmp_path):
    packs, _f = real
    planted = tmp_path / "packs"
    shutil.copytree(packs, planted)
    f = planted / "rogue" / "data" / "cobblers" / "function" / "x.mcfunction"
    f.parent.mkdir(parents=True)
    f.write_text("function %s\nadvancement grant @a everything\n" % A.FLAG_GRANT_FN)
    bad, _ = A.check_sweep(planted, IDS)
    assert any("rogue/data/cobblers/function/x.mcfunction" in b and "only" in b for b in bad)
    assert any("everything" in b for b in bad)


# ====================================================================== mutations: the GENERATOR changed, data not

def drop_elara(ns):
    real_cond = ns.CD.Compiler.cond

    def cond(self, c, probes):
        if c.get("kind") == "progression_equals" and c.get("field") == A.ELARA_FIELD:
            return "1"
        return real_cond(self, c, probes)
    ns.CD.Compiler.cond = cond
    return lambda: setattr(ns.CD.Compiler, "cond", real_cond)


# Protects: INDEPENDENCE. compile_dialogue compiling every elara_defeated condition to "1" (data/dialogue.json and
# data/quests.json untouched) must fail the audit; if removed, the audit could share the compiler's blind spot.
def test_mutation_compiler_drops_elara(tmp_path):
    packs, fns = emit(tmp_path, drop_elara)
    bad, _ = A.check_conversation(packs, fns)
    assert any("fails the rule" in b for b in bad), bad[:3]
    assert any("is shown from" in b for b in bad)


def swap_key(ns):
    real_key = ns.RT.key

    def key(field):
        return real_key(A.BRANN_FIELD if field == A.ELARA_FIELD else field)
    ns.RT.key = key
    return lambda: setattr(ns.RT, "key", real_key)


# Protects: route_trainers' won function writing Brann's key for Elara (data untouched) fails the defeat check;
# if removed, one win could count as two.
def test_mutation_won_function_writes_the_wrong_field(tmp_path):
    packs, fns = emit(tmp_path, swap_key)
    bad = A.check_defeat_fields(packs, fns, IDS)
    assert any(IDS["elara"] in b for b in bad), bad


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


# ====================================================================== the built packs, when prepare made them

RELIC = BUILT / "cobblers_relic_underground" / "data" / "cobblers" / "function" / "relic_underground" / "index.txt"
needs_relic = pytest.mark.skipif(not RELIC.is_file(), reason="build/datapacks/cobblers_relic_underground not built "
                                                             "(needs the Rift skin's pack); prepare runs the audit")


def with_relic(packs):
    shutil.rmtree(packs / "cobblers_relic_underground")
    shutil.copytree(BUILT / "cobblers_relic_underground", packs / "cobblers_relic_underground")
    return packs, A.LazyFunctions(A.function_index(packs))


# Protects: both seats are a floor with two air in the cradle AS BUILT, and Brann's sight covers every way off the
# passage onto the cradle floor; if removed, a dressing block on a seat or a side way past him goes unseen.
@needs_relic
def test_cradle_as_built(tmp_path):
    packs, fns = with_relic(emit(tmp_path)[0])
    bad, notes = A.check_cradle(packs, fns, IDS)
    assert bad == [], bad
    assert "none on the cradle floor" in notes[0]


def move_brann_home(ns):
    real_cycle = ns.RT.cycle_lines

    def cycle(tid, seat, field):
        if tid == IDS["brann"]:
            seat = dict(seat, seat=[seat["seat"][0] - 10, seat["seat"][1], seat["seat"][2]])
        return real_cycle(tid, seat, field)
    ns.RT.cycle_lines = cycle
    return lambda: setattr(ns.RT, "cycle_lines", real_cycle)


# Protects: INDEPENDENCE of the sight check. route_trainers holding Brann ten blocks west (data untouched) must
# fail: his sight no longer covers the cut; if removed, the sight check could pass any seat.
@needs_relic
def test_mutation_brann_held_elsewhere(tmp_path):
    packs, fns = with_relic(emit(tmp_path, move_brann_home)[0])
    bad, _ = A.check_cradle(packs, fns, IDS)
    assert any("does not cover the way in" in b or "binder is reached" in b for b in bad), bad


Z5 = BUILT / "cobblers_rift_zones" / "data" / "cobblers" / "function" / "rift_zones" / "z5" / "zone.mcfunction"


# Protects: z5 admits a flag holder anywhere (qualify on entry) and turns back a survival player without it; if
# removed, the flag could stop opening the League precinct.
@pytest.mark.skipif(not Z5.is_file(), reason="build/datapacks/cobblers_rift_zones not built")
def test_z5_opens_on_the_flag():
    assert A.check_z5(BUILT, A.LazyFunctions(A.function_index(BUILT))) == []


# Protects: the audit runs in prepare after every pack it reads is built; if removed, it would read a stale or
# missing pack, or never run.
def test_prepare_runs_the_audit_after_its_inputs():
    import reapply
    names = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root="", server_dir=""))]
    at = names.index("finale_audit")
    for before in ("compile_dialogue", "route_trainers", "progression_pack", "relic_underground:build",
                   "rift_zones:build"):
        assert names.index(before) < at, before
