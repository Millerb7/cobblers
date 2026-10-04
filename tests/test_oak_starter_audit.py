"""The independent audit of "Oak gives the starter" (tools/oak_starter_audit.py), and the proof that it is independent.

Written by a test author who did not build the feature (builder commit a93f059). Nothing here imports
tools/compile_dialogue.py or reuses tests/test_oak_starter.py: the compiler is RUN (as a subprocess) and its output
is read back by the audit's own Molang parser and player model.

Independence is proved by MUTATING THE GENERATOR: a copy of tools/compile_dialogue.py with one change, run over the
real, untouched data/; the audit must fail on each mutant, on the property the mutation breaks. A mutation of the data
would move the expectation and the output together and prove nothing.

Not covered here (runtime, an experiment): that the starter_chosen callback fires, that the client keeps the screen
when the dialogue closes, that a locked player's own key is refused, and what openstarterscreen really returns
(the audit's model takes the builder's reading of OpenStarterScreenCommand.kt @1.8.0 and prints it as OPEN).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import oak_starter_audit as A  # noqa: E402

DATA = ROOT / "data"
COMPILER = ROOT / "tools" / "compile_dialogue.py"
STAGE = "cobblers__quest__main_worldshift_reveal__stage"


def compile_with(tmp, mutate=None):
    """Compile every conversation from the real data with the real compiler, or a copy carrying one mutation."""
    tools = tmp / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    src = COMPILER.read_text(encoding="utf-8")
    if mutate is not None:
        old, new = mutate
        assert src.count(old) == 1, "mutation anchor not unique or gone: %r" % old
        src = src.replace(old, new)
    (tools / "compile_dialogue.py").write_text(src, encoding="utf-8")
    shutil.copy(ROOT / "tools" / "arena_runtime.py", tools / "arena_runtime.py")
    out = tmp / "cobblers_dialogue"
    r = subprocess.run([sys.executable, str(tools / "compile_dialogue.py"), "--all", "--data", str(DATA),
                        "--out", str(out)], capture_output=True, text=True, timeout=200)
    assert r.returncode == 0, r.stderr[-800:]
    return out


def audit(dialogue, tmp, config=None, packs=None):
    a = A.Audit(dialogue, packs or (tmp / "no_packs"), config or A.CONFIG, DATA, A.RCT)
    a.run()
    return a


def keys(a):
    return {(c, k) for c, k, _ in a.problems}


def checks(a):
    return {c + ":" + k.split(":")[0] for c, k, _ in a.problems}


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("oak_real")
    return tmp, compile_with(tmp)


# --------------------------------------------------------------------------------------------- the real build
def test_real_compiled_dialogue_meets_the_starter_gate(real):
    # Protects all six properties on today's compiler and data; removing it leaves the audit unrun in the suite.
    tmp, dlg = real
    a = audit(dlg, tmp)
    assert keys(a) == set(A.KNOWN), a.problems


def test_audit_explores_oaks_offer_and_finds_the_lead_in(real):
    # Protects against a vacuous pass: an audit that never reached the offer would report nothing.
    tmp, dlg = real
    a = audit(dlg, tmp)
    oak = [n for n in a.notes if n.startswith("P1/P3/P6 Oak")]
    assert oak and "screen openings" in oak[0] and "lead-in [" in oak[0], a.notes


# --------------------------------------------------------------------------------------------- generator mutations
MUTATIONS = {
    # the starter_chosen entry rule dropped: a player who has chosen lands back on the offer
    "drop_starter_entry_rule": (
        ('        for rule in sorted(self.conv["entry_rules"], key=lambda r: r["priority"]):\n',
         '        for rule in sorted(self.conv["entry_rules"], key=lambda r: r["priority"]):\n'
         '            if "starter_chosen" in json.dumps(rule["when"]):\n                continue\n'),
        {"P3:tagged_sees_offer"}),
    # the screen command emitted twice
    "screen_twice": (
        ('                run(["execute as ", UUID, " store result score @s %s run openstarterscreen @s" % STARTER_SCORE]) +\n',
         '                run(["execute as ", UUID, " store result score @s %s run openstarterscreen @s" % STARTER_SCORE]) +\n'
         '                run(["execute as ", UUID, " store result score @s %s run openstarterscreen @s" % STARTER_SCORE]) +\n'),
        {"P2:screen_count"}),
    # "Not yet" falls through to the send-off instead of closing
    "not_yet_falls_through": (
        ('                act += "q.player.save_data(); q.dialogue.close();"\n',
         '                nx = next((x["next"] for x in n["responses"] if x.get("next")), None)\n'
         '                act += self.goto(nx) if nx else "q.player.save_data(); q.dialogue.close();"\n'),
        {"P1:write_without_starter", "P3:not_yet_returns"}),
    # the opener tagged whatever the command returned
    "tag_without_zero_check": (
        ('" if score @s %s matches 0 run tag @s add %s" % (STARTER_SCORE, STARTER_TAG)',
         '" run tag @s add %s" % STARTER_TAG'),
        {"P1:write_without_starter"}),
    # the score's objective never created: the store is silently dropped and a legacy chooser is stuck forever
    "no_objective": (
        ('        return (run(["scoreboard objectives add %s dummy" % STARTER_SCORE]) +\n',
         '        return (\n'),
        {"P6:chosen_cannot_reach_sendoff"}),
    # an unset cursor enters past the offer (the third node of the conversation, data untouched)
    "fresh_skips_offer": (
        ('target = "(%s == 0 ? %s : %s)" % (c, lit(self.initial), c)',
         'target = "(%s == 0 ? %s : %s)" % (c, lit(self.conv["nodes"][2]["id"]), c)'),
        {"P1:write_before_offer", "P1:write_without_starter"}),
    # a second opener of the screen, in the starter_chosen callback
    "callback_opens_screen": (
        ('''    return "q.run_command('tag ' + q.player.username + ' add %s');\\n" % STARTER_TAG''',
         '''    return ("q.run_command('tag ' + q.player.username + ' add %s');\\n" % STARTER_TAG) + '''
         '''"q.run_command('openstarterscreen ' + q.player.username);\\n"'''),
        {"P2:screen_count"}),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_generator_mutation_is_caught(name, tmp_path):
    # Protects the audit's independence: each mutant compiler, over untouched data, must fail the named property.
    (old, new), expected = MUTATIONS[name]
    dlg = compile_with(tmp_path, (old, new))
    a = audit(dlg, tmp_path)
    got = checks(a)
    missing = expected - got
    assert not missing, "mutation %s not caught by %s; audit said %s" % (name, sorted(missing), a.problems)


# --------------------------------------------------------------------------------------------- hand-made fixtures
def oak_pack(root, not_yet_action=None, offer_entry_guard=True):
    """A minimal compiled-style Oak dialogue written by hand: offer -> (screen | not yet) -> sendoff."""
    cur = "t.d.cobblers__quest__main_worldshift_reveal__pallet_oak_cursor"
    stage = "t.d." + STAGE
    tag = "cobblers_starter_chosen"
    screen = ("t.d = q.player.data(); q.run_command('scoreboard objectives add s dummy');"
              "q.run_command('execute as ' + q.player.uuid + ' run scoreboard players set @s s -1');"
              "q.run_command('execute as ' + q.player.uuid + ' store result score @s s run openstarterscreen @s');"
              "q.run_command('execute as ' + q.player.uuid + ' if score @s s matches 0 run tag @s add %s');"
              " q.player.has_tag('%s') ? { %s = 'send'; q.player.save_data(); q.dialogue.set_page('send'); }"
              " : { q.dialogue.close(); };" % (tag, tag, cur))
    entry = ("t.d = q.player.data(); v.e = 0; "
             + ("(v.e == 0 && q.player.has_tag('%s') && (%s == 0 || %s == 'offer')) ? { v.e = 'send'; }; "
                % (tag, cur, cur) if offer_entry_guard else "")
             + "(v.e == 0) ? { v.e = (%s == 0 ? 'offer' : %s); }; q.dialogue.set_page(v.e);" % (cur, cur))
    send = ("t.d = q.player.data(); (%s == 0) ? { %s = 'oak_sendoff'; }; %s = 'done'; q.player.save_data(); "
            "q.dialogue.close();" % (stage, stage, cur))
    done = "t.d = q.player.data(); q.dialogue.close();"
    dlg = {"initializationAction": entry, "pages": [
        {"id": "offer", "lines": ["x"], "input": {"type": "option", "options": [
            {"text": "Let me see them.", "value": "choose", "action": screen},
            {"text": "Not yet.", "value": "wait", "action": not_yet_action or
             "t.d = q.player.data(); %s = 'offer'; q.player.save_data(); q.dialogue.close();" % cur}]}},
        {"id": "send", "lines": ["x"], "input": send},
        {"id": "done", "lines": ["x"], "input": done}]}
    d = root / "data" / "cobblers"
    (d / "dialogues").mkdir(parents=True)
    (d / "npcs").mkdir(parents=True)
    (d / "dialogues" / "oak.json").write_text(json.dumps(dlg), encoding="utf-8")
    (d / "npcs" / "oak.json").write_text(json.dumps({"names": ["Professor Oak"], "interaction": {
        "type": "dialogue", "dialogue": "cobblers:oak"}}), encoding="utf-8")
    cb = root / "data" / "cobblemon" / "callbacks" / "starter_chosen"
    cb.mkdir(parents=True)
    (cb / "t.molang").write_text("q.run_command('tag ' + q.player.username + ' add %s');\n" % tag, encoding="utf-8")
    return root


def test_hand_fixture_with_a_correct_gate_passes(tmp_path):
    # Protects against a model that fails everything: a hand-built correct gate must pass P1, P2, P3 and P6.
    a = audit(oak_pack(tmp_path / "dlg"), tmp_path)
    assert not [p for p in a.problems if p[0] in ("P1", "P2", "P3", "P6")], a.problems


def test_hand_fixture_where_not_yet_sends_off_fails(tmp_path):
    # Protects P1/P3 on a fixture whose answer is known by hand: "Not yet" that writes the stage is a send-off
    # with no starter.
    bad = ("t.d = q.player.data(); t.d.%s = 'oak_sendoff'; q.player.save_data(); q.dialogue.close();" % STAGE)
    a = audit(oak_pack(tmp_path / "dlg", not_yet_action=bad), tmp_path)
    assert {"P1:write_without_starter", "P3:not_yet_returns"} <= checks(a), a.problems


def test_hand_fixture_without_the_tag_entry_rule_shows_a_chooser_the_offer(tmp_path):
    # Protects P3's "never sees the offer again" on a fixture with no tagged entry rule.
    a = audit(oak_pack(tmp_path / "dlg", offer_entry_guard=False), tmp_path)
    assert "P3:tagged_sees_offer" in checks(a), a.problems


def test_a_pack_function_giving_a_starter_species_is_caught(tmp_path):
    # Protects P2's sweep: a built function that gives Kubfu outside the starter screen must fail.
    dlg = oak_pack(tmp_path / "dlg")
    packs = tmp_path / "packs"
    fn = packs / "cobblers_x" / "data" / "cobblers" / "function"
    fn.mkdir(parents=True)
    (fn / "gift.mcfunction").write_text("givepokemon @s kubfu level=5\n", encoding="utf-8")
    a = audit(dlg, tmp_path, packs=packs)
    assert "P2:starter_given" in checks(a), a.problems


def test_a_pack_shipping_a_starters_folder_is_caught(tmp_path):
    # Protects P4: with useConfigStarters false a datapack's starters/ replaces the config's five.
    dlg = oak_pack(tmp_path / "dlg")
    packs = tmp_path / "packs"
    st = packs / "cobblers_x" / "data" / "cobblemon" / "starters"
    st.mkdir(parents=True)
    (st / "kanto.json").write_text("{}", encoding="utf-8")
    a = audit(dlg, tmp_path, packs=packs)
    assert "P4:starters_datapack" in checks(a), a.problems


def test_a_second_screen_opener_in_another_pack_is_caught(tmp_path):
    # Protects P2's "exactly one place": a function anywhere under build/datapacks running the command fails.
    dlg = oak_pack(tmp_path / "dlg")
    packs = tmp_path / "packs"
    fn = packs / "cobblers_x" / "data" / "cobblers" / "function"
    fn.mkdir(parents=True)
    (fn / "open.mcfunction").write_text("execute as @a run openstarterscreen @s\n", encoding="utf-8")
    a = audit(dlg, tmp_path, packs=packs)
    assert "P2:screen_count" in checks(a), a.problems


@pytest.mark.parametrize("edit,check", [
    (lambda c: c.update(allowStarterOnJoin=True), "P4:allow_on_join"),
    (lambda c: c["starters"][0]["pokemon"].append("bulbasaur level=5 aspect=cobblers_starter_1"), "P4:five_entries"),
    (lambda c: c["starters"][0]["pokemon"].__setitem__(0, "cosmog level=5"), "P4:five_entries"),
])
def test_starter_config_faults_are_caught(tmp_path, edit, check):
    # Protects P4 on the config the server installs: unlocked on join, a sixth entry, or an entry without the aspect.
    cfg = json.loads(A.CONFIG.read_text(encoding="utf-8"))
    edit(cfg)
    p = tmp_path / "starters.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    a = audit(oak_pack(tmp_path / "dlg"), tmp_path, config=p)
    assert check in checks(a), a.problems


# --------------------------------------------------------------------------------------------- wiring
def test_prepare_runs_the_audit_after_the_dialogue_and_every_pack():
    # Without it the audit exists and never runs, or runs before the dialogue it reads is compiled.
    import types
    import inspect
    import reapply
    jobs = reapply.prepare_jobs(types.SimpleNamespace(source_root="x", server_dir="x"))
    names = [n for n, _f in jobs]
    mine = [i for i, (n, f) in enumerate(jobs) if inspect.getclosurevars(f).nonlocals.get("tool") == "oak_starter_audit.py"]
    assert len(mine) == 1, names
    assert mine[0] > names.index("compile_dialogue")
    assert mine[0] == len(jobs) - 1, "the sweep must follow every pack's build: %s" % names[mine[0]:]


# --------------------------------------------------------------------------------------------- the Molang model
def test_molang_model_by_hand():
    # Protects the interpreter the whole audit rests on, against values computed by hand.
    m = A.Model("k")
    w = {"data": {}, "tags": set(), "scores": {}, "objectives": set(), "chosen": False, "unlocked": False,
         "offer_seen": False, "notyet": False}
    r = A.Run(w, m)
    r.exec("t.d = q.player.data(); t.d.a = (t.d.b == 0 ? 'x' : 'y'); v.n = 1 + 2;")
    assert w["data"]["a"] == "x" and r.v["n"] == 3.0
    # a store into an objective that does not exist stores nothing (vanilla), so `matches 0` stays false
    m.command(w, "execute as PLAYER-UUID store result score @s s run openstarterscreen @s")
    m.command(w, "execute as PLAYER-UUID if score @s s matches 1 run tag @s add t")
    assert "s" not in w["scores"] and "t" not in w["tags"] and w["unlocked"]
    w["objectives"].add("s")
    w["chosen"] = True
    m.command(w, "execute as PLAYER-UUID store result score @s s run openstarterscreen @s")
    m.command(w, "execute as PLAYER-UUID if score @s s matches 0 run tag @s add t")
    assert w["scores"]["s"] == 0 and "t" in w["tags"]
