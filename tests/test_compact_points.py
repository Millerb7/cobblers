"""The Haven Compact's story points CP-04, CP-12 and CP-14 (tools/compact_points.py, data/compact_points.json,
data/compact_trainers.json).

Written by the builder (unit CP-CORE) as the unit's own tests; the design's W1-tests list is for test-author, who
should write the independent ones. What these protect:

  the records   data/ holds exactly what the generator makes from data/compact_points.json (no drift), and every
                conversation compiles through tools/compile_dialogue.py
  the story     a small evaluator of the generated entry rules, independent of the compiler's MoLang, walks each
                chain: a battle never opens before its window or out of order, CP-12 closes for a player the analyst's
                stand-in already told, and the Commander's win reaches crater_operation_stopped's grant
  the flags     crater_operation_stopped's declared setter is CP-12; the analyst's stand-in still runs the same grant;
                nothing here writes the main stage or grants a badge
  the pack      one callback block and one won function per fighter, at the fighter's seat, writing its own field
  the reapply   R18CP places every NPC with its yaw; the pack is registered as installed, world-local and self-driving

Mutations change the GENERATOR (CLAUDE.md "How to prove an audit is independent"), never the authored record.
Not covered: anything in game (EXP-091).
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import compact_points as CP  # noqa: E402

JAR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")
SPEC = CP.load()
POINTS = {p["id"]: p for p in SPEC["points"]}
DIALOGUE = {c["id"]: c for c in json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))["conversations"]}
QUESTS = {q["id"]: q for q in json.loads((ROOT / "data" / "quests.json").read_text(encoding="utf-8"))["quests"]}
PROG = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
STAGES = CP.stages()


# ------------------------------------------------------------------------------------------------- a rule evaluator
def holds(c, st):
    """A condition against a player state {"fields": {...}, "flags": set()} -- read from the data, not the MoLang."""
    k = c["kind"]
    if k == "always":
        return True
    if k == "all":
        return all(holds(x, st) for x in c["conditions"])
    if k == "any":
        return any(holds(x, st) for x in c["conditions"])
    if k == "not":
        return not holds(c["condition"], st)
    if k == "flag":
        return c["flag"] in st["flags"]
    if k == "progression_equals":
        v = st["fields"].get(c["field"], False if c["value"] in (True, False) else None)
        return v == c["value"]
    if k == "progression_in":
        return st["fields"].get(c["field"]) in c["values"]
    raise AssertionError("condition kind %s is not modelled" % k)


def run_transition(quest, tid, st):
    t = next(t for t in QUESTS[quest]["transitions"] if t["id"] == tid)
    if not all(holds(c, st) for c in t["conditions"]):
        return
    for e in t["effects"]:
        if e["kind"] == "set_progression":
            st["fields"][e["field"]] = e["value"]
        elif e["kind"] == "function":
            st.setdefault("functions", []).append(e["function"])
            if e["function"].startswith("cobblers:flag/") and e["function"].endswith("/grant"):
                st["flags"].add(e["function"].split("/")[1])


def talk(cid, st):
    """The node the conversation opens on for this state, running the matching rule's actions (as compiled)."""
    conv = DIALOGUE[cid]
    for r in sorted(conv["entry_rules"], key=lambda r: r["priority"]):
        if holds(r["when"], st):
            for a in r.get("actions") or []:
                run_transition(conv["quest_id"], a["transition"], st)
            return r["node"]
    return None


def read_through(cid, st):
    """Open the conversation and acknowledge every line to the end of its state, running the acks."""
    conv = DIALOGUE[cid]
    nodes = {n["id"]: n for n in conv["nodes"]}
    node, seen = talk(cid, st), set()
    while node and node not in seen:
        seen.add(node)
        n = nodes[node]
        if n["kind"] != "line":
            return node
        for a in n.get("actions_after_acknowledge") or []:
            run_transition(conv["quest_id"], a["transition"], st)
        node = n["next"]
    return node


def player(stage, **fields_and_flags):
    flags = set(fields_and_flags.pop("flags", ()))
    return {"fields": dict({CP.STAGE: stage}, **fields_and_flags), "flags": flags}


def f(point, name):
    return CP.field(POINTS[point], name)


def battle_open(cid, st):
    """True when talking (and reading through) reaches a choice that starts this NPC's battle."""
    node = read_through(cid, st)
    n = next((n for n in DIALOGUE[cid]["nodes"] if n["id"] == node), None)
    return bool(n and n["kind"] == "choice"
                and any(a["kind"] == "npc_battle" for r in n["responses"] for a in r["actions"]))


# ------------------------------------------------------------------------------------------------- 1. records
# Without it a hand edit to data/dialogue.json, quests.json or progression.json drifts from the authored point.
def test_data_holds_exactly_the_generated_records():
    assert CP.sync(False) == []


# Without it a conversation the compiler refuses would ship with no NPC class and R18CP would spawn nothing.
def test_every_generated_conversation_compiles():
    assert CP.compile_all() == []


# Without it the offline gate (seats, teams, flags) could regress unseen; the heightmap half skips without a source.
def test_the_offline_check_is_clean():
    import ground as G
    try:
        g = G.load()
    except (SystemExit, OSError, FileNotFoundError):
        g = None
    assert CP.check(g) == []


# ------------------------------------------------------------------------------------------------- 2. the chains
# Without it a Compact battle could open before the player has heard the rescue side (ARC rule 3; the design's
# 'No Compact battle opens before brock_account_heard').
@pytest.mark.parametrize("cid", sorted(c for c in DIALOGUE if c.startswith("dlg_compact_cp") and "npc_battle" in DIALOGUE[c]))
def test_no_battle_opens_before_its_window(cid):
    pid = next(p["id"] for p in SPEC["points"] if any(CP.conv_id(n) == cid for n in p["npcs"]))
    first = STAGES.index(POINTS[pid]["window"])
    assert first > STAGES.index("brock_account_heard")
    everything = {k: True for k in (CP.field(POINTS[pid], s) for t in POINTS[pid]["transitions"] for s in t["sets"])}
    everything.update({CP.defeated(POINTS[pid], n): False for n in POINTS[pid]["npcs"] if n.get("fight")})
    for stage in STAGES[:first]:
        st = player(stage, **everything)
        assert not battle_open(cid, st), (cid, stage)


def test_cp04_runs_in_order_and_varga_recovers_the_records():
    st = player("misty_reveal_complete")
    order = ["courier_1", "courier_2", "courier_3", "varga"]
    for i, who in enumerate(order):
        for later in order[i + 1:]:
            assert not battle_open("dlg_compact_cp04_%s" % later, st), (who, later)
        assert battle_open("dlg_compact_cp04_%s" % who, st), who
        st["fields"][f("cp04_records_run", "%s_defeated" % who)] = True    # the callback's write
    read_through("dlg_compact_cp04_varga", st)
    assert st["fields"][f("cp04_records_run", "records_recovered")] is True
    assert st["fields"][f("cp04_records_run", "completed")] is True


def test_cp12_needs_tomas_and_oren_then_three_anchors_then_the_commander_sets_the_flag():
    st = player("sabrina_reveal_complete", flags={"gym6_cleared"})
    guards = ["dlg_compact_cp12_guard_%d" % k for k in (1, 2, 3)]
    assert not any(battle_open(g, st) for g in guards)
    read_through("dlg_compact_cp12_oren_pell", st)                      # before Tomas: Oren holds back
    assert not st["fields"].get(f("cp12_crater_activation", "calibration_received"))
    read_through("dlg_compact_cp12_tomas_rill", st)
    read_through("dlg_compact_cp12_oren_pell", st)
    assert all(battle_open(g, st) for g in guards)
    for k, g in zip((3, 1, 2), (guards[2], guards[0], guards[1])):     # any order
        assert not battle_open("dlg_compact_cp12_commander", st)
        st["fields"][f("cp12_crater_activation", "guard_%d_defeated" % k)] = True
        talk(g, st)                                                     # the shutdown rides the next talk
    assert battle_open("dlg_compact_cp12_commander", st)
    st["fields"][f("cp12_crater_activation", "commander_defeated")] = True
    talk("dlg_compact_cp12_commander", st)
    assert "crater_operation_stopped" in st["flags"]
    assert st["fields"][f("cp12_crater_activation", "activation_stopped")] is True


# Without it a player who beat the Commander and then walked off (or beat Blaine first) would never get the flag.
def test_cp12_any_npc_after_the_commanders_defeat_grants_the_flag_even_past_blaine():
    for cid in ("dlg_compact_cp12_tomas_rill", "dlg_compact_cp12_aster", "dlg_compact_cp12_guard_2"):
        st = player("blaine_reveal_complete", flags={"gym7_cleared"},
                    **{f("cp12_crater_activation", "commander_defeated"): True})
        talk(cid, st)
        assert "crater_operation_stopped" in st["flags"], cid


# Without it CP-12 would keep its guards fighting for a player the analyst already told 'The activation is stopped'.
@pytest.mark.parametrize("flag", ["crater_operation_stopped", "gym7_cleared"])
def test_cp12_is_closed_for_a_player_past_it(flag):
    st = player("blaine_reveal_complete", flags={flag}, **{
        f("cp12_crater_activation", "calibration_received"): True,
        f("cp12_crater_activation", "occupied_confirmed"): True})
    for n in POINTS["cp12_crater_activation"]["npcs"]:
        cid = CP.conv_id(n)
        assert talk(cid, st).endswith("_closed_1"), cid
        assert not battle_open(cid, st), cid


def test_cp14_needs_nia_then_loyalist_1_then_the_sergeants_line_then_loyalist_2():
    st = player("blaine_reveal_complete", flags={"gym7_cleared"})
    l1, l2 = "dlg_compact_cp14_loyalist_1", "dlg_compact_cp14_loyalist_2"
    assert not battle_open(l1, st)
    read_through("dlg_compact_cp14_nia_calder", st)
    assert battle_open(l1, st) and not battle_open(l2, st)
    st["fields"][f("cp14_split", "loyalist_1_defeated")] = True
    assert not battle_open(l2, st)                                      # the watch's line comes between
    read_through("dlg_compact_cp14_watch_sergeant", st)
    assert battle_open(l2, st)
    st["fields"][f("cp14_split", "loyalist_2_defeated")] = True
    read_through("dlg_compact_cp14_watch_sergeant", st)
    assert st["fields"][f("cp14_split", "packet_kept")] is True


# Without it a loss (the cursor left on the choice) would replay the speech, or worse, never reoffer the battle.
@pytest.mark.parametrize("cid", sorted(c for c in DIALOGUE if c.startswith("dlg_compact_cp") and "npc_battle" in DIALOGUE[c]))
def test_a_loss_reoffers_the_battle_from_the_choice(cid):
    choice = next(n["id"] for n in DIALOGUE[cid]["nodes"] if n["kind"] == "choice")
    rule = next(r for r in DIALOGUE[cid]["entry_rules"] if r["node"] == choice)
    fields = [c for c in rule["when"]["conditions"] if c.get("field") == DIALOGUE[cid]["cursor"]["progression_field"]]
    assert fields and fields[0]["value"] == choice


# ------------------------------------------------------------------------------------------------- 3. the flags
def test_crater_operation_stopped_is_set_by_cp12_and_the_stand_in_still_grants_the_same():
    fl = next(x for x in PROG["flags"] if x["id"] == "crater_operation_stopped")
    sb = fl["set_by"]
    assert (sb["quest"], sb["transition"]) == ("evt_compact_crater", "stop_crater_activation")
    grant = "cobblers:flag/crater_operation_stopped/grant"
    t = next(t for t in QUESTS["evt_compact_crater"]["transitions"] if t["id"] == "stop_crater_activation")
    assert {"kind": "function", "function": grant} in t["effects"]
    stand = sb["stand_in_setter"]
    t2 = next(t for t in QUESTS[stand["quest"]]["transitions"] if t["id"] == stand["transition"])
    assert {"kind": "function", "function": grant} in t2["effects"]
    analyst = DIALOGUE["dlg_main_blaine_crater_analyst"]
    assert stand["transition"] in json.dumps(analyst)


# Without it a Compact point could move the main stage or gate a badge (the design: 'No point gates a badge').
def test_no_point_writes_the_stage_or_grants_any_flag_but_the_crater_one():
    for q in ("evt_compact_records_run", "evt_compact_crater", "evt_compact_split"):
        assert QUESTS[q]["optional"] is True and QUESTS[q]["progression_gate"] == []
        for t in QUESTS[q]["transitions"]:
            for e in t["effects"]:
                assert e.get("field") != CP.STAGE
                if e["kind"] == "function":
                    assert e["function"] == "cobblers:flag/crater_operation_stopped/grant", (q, t["id"])


# ------------------------------------------------------------------------------------------------- 4. the pack
def test_the_callback_has_one_block_per_fighter_at_its_seat_and_each_won_function_writes_its_own_field():
    files = CP.pack_files()
    cb = files[CP.CALLBACK]
    fights = CP.fight_list()
    assert cb.count("run function") == len(fights) == 10
    for fi in fights:
        x, y, z = fi["npc"]["at"]
        assert "x=%d.5,y=%d,z=%d.5,distance=..%s" % (x, y, z, CP.RADIUS) in cb
        ns, path = fi["function"].split(":", 1)
        body = files["data/%s/function/%s.mcfunction" % (ns, path)]
        assert "t.d.%s = 1" % CP._key(fi["sets"]) in body
        assert fi["sets"] in CP.teams()[fi["trainer"]]["sets"]


# Mutating the generator: a won function that wrote the wrong player field must be caught by check().
def test_mutated_generator_writing_the_wrong_field_is_caught(monkeypatch):
    real = CP.defeated
    monkeypatch.setattr(CP, "defeated", lambda p, n: real(p, n).replace("_defeated", "_beaten"))
    assert any("sets" in p for p in CP.check(None))


# Mutating the generator: dropping the stage window from the rules must open a battle before its window.
def test_mutated_generator_without_the_window_opens_a_battle_early(monkeypatch):
    real = CP.cond
    monkeypatch.setattr(CP, "cond", lambda p, n, t: {"kind": "always"} if t == "window" else real(p, n, t))
    conv = CP.conversation(POINTS["cp04_records_run"], POINTS["cp04_records_run"]["npcs"][0], set(CP.teams()))
    monkeypatch.setitem(DIALOGUE, conv["id"], conv)
    assert battle_open(conv["id"], player("pallet_complete"))


# ------------------------------------------------------------------------------------------------- 5. teams
def test_every_team_is_under_the_next_leaders_ace_and_varga_rises_under_her_tower():
    assert not [p for p in CP.check(None) if "ace" in p or "Varga" in p]
    roster = {t["id"]: t for t in json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))["trainers"]}
    for tid, t in CP.teams().items():
        town = POINTS[t["point"]]["settlement"]
        ace = max(m["level"] for m in roster[CP.NEXT_LEADER[town]]["team"])
        assert max(m["level"] for m in t["team"]) < ace, tid


@pytest.mark.skipif(not JAR.is_file(), reason="the Cobblemon 1.8.0 jar is local only")
def test_every_move_ability_and_species_is_legal_in_the_jar():
    assert CP.legality(JAR) == []


def test_legality_catches_a_move_the_species_cannot_learn(tmp_path, monkeypatch):
    jar = tmp_path / "fake.jar"
    species = {}
    for tid, t in CP.teams().items():
        for m in t["team"]:
            s = species.setdefault(m["species"], {"implemented": True, "abilities": [], "moves": []})
            s["abilities"].append(m.get("ability") or "x")
            s["moves"] += ["1:%s" % mv for mv in m["moveset"]]
    species["drilbur"]["moves"].remove("1:metalclaw")       # Varga's Drilbur, and only hers, loses one move
    with zipfile.ZipFile(jar, "w") as z:
        for name, s in species.items():
            z.writestr("data/cobblemon/species/generation0/%s.json" % name, json.dumps(s))
    probs = CP.legality(jar)
    assert len(probs) == 1 and "drilbur" in probs[0]


# ------------------------------------------------------------------------------------------------- 6. reapply
def test_r18cp_places_every_npc_with_its_yaw_and_the_pack_is_registered():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert '"R18CP"' in src and "compact_points.npc_placements()" in src
    assert '"compact:build", "compact_points.py", "build"' in src
    import reapply
    assert "cobblers_compact" in reapply.SERVER_PACKS
    assert "cobblers_compact" in reapply.WORLD_LOCAL
    assert "cobblers_compact" in reapply.EXCLUDED
    pl = CP.npc_placements()
    assert len(pl) == sum(len(p["npcs"]) for p in SPEC["points"]) == 16
    for conv, at, cls, yaw in pl:
        assert conv in DIALOGUE and cls == "cobblers:" + DIALOGUE[conv]["npc_id"] and -180 <= yaw <= 180


def test_every_npc_has_a_presence_probe():
    probes = json.loads((ROOT / "data" / "world_probes.json").read_text(encoding="utf-8"))["places"]
    held = {tuple(p["hold"]) for k, v in probes.items() if k.startswith("compact_") for p in v}
    assert held == {tuple(n["at"]) for p in SPEC["points"] for n in p["npcs"]}
