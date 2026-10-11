"""The Haven Compact's story points on the routes and in the towns (data/compact_routes.json, tools/compact_routes.py).

Written beside the builder in the same unit (CP-ROUTES, 2026-10-11) because the brief asked for the unit's own tests; the
independent audit is qa-reviewer's. So the expectations here come from sources the generator does not read:

  - the level ceilings: docs/story/TRAINER_RULES.json difficulty.gym_ace_levels (20..55), with the next leader for each
    point written HERE from the route order, not read from the table
  - the stage order: data/progression.json quest.main_worldshift_reveal.stage
  - where an actor stands: the heightmap (tools/ground.py), the walked lines (data/route_paths.json, distance to the
    SEGMENTS computed here), the subregion polygons of data/regions.json (point in polygon computed here), the plaza
    rects of data/placements.json, and every other seat file
  - how a conversation behaves: a small evaluator of entry rules and `next` links written here, run on the emitted
    data/dialogue.json (not on the generator's internals)
  - what Cobblemon would be given: tools/compile_dialogue.py's own output for the emitted conversations
  - which species are "homeless": parsed here from docs/story/ENCOUNTER_GAPS.md
  - move legality: the Cobblemon 1.8.0 jar's species files, when the jar is present

The mutation tests change the GENERATOR (tools/compact_routes.py), never the table, and prove the checks bite.

NOT covered (needs a running Minecraft): that an NPC is where its seat says, that npc_battle starts a fight, that the
battle_victory callback fires and writes the field, that a seated trainer fights on sight, and that anything is dry.
"""
import json
import math
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compact_routes as CP  # noqa: E402
import compile_dialogue as CD  # noqa: E402

STAGE = "quest.main_worldshift_reveal.stage"


def _j(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


TB = _j("data/compact_routes.json")
PROG = _j("data/progression.json")
FIELDS = {f["id"]: f for f in PROG["quest_fields"]}
STAGES = FIELDS[STAGE]["allowed_values"]
DIALOGUE = {c["id"]: c for c in _j("data/dialogue.json")["conversations"]}
QUESTS = {q["id"]: q for q in _j("data/quests.json")["quests"]}
NPC_SEATS = {s["id"]: s for s in _j("data/npc_seats.json")["seats"]}
TRAINERS = {t["id"]: t for t in _j("data/compact_route_trainers.json")["trainers"]}
NPC_TEAMS = {t["id"]: t for t in _j("data/compact_route_npc_teams.json")["trainers"]}
ACES = _j("docs/story/TRAINER_RULES.json")["difficulty"]["gym_ace_levels"]

ACTORS = [(p, a) for p in TB["points"] for a in p["actors"]]
POINTS = {p["id"]: p for p in TB["points"]}
BUILT = ["CP-01", "CP-02", "CP-03", "CP-05", "CP-06", "CP-07", "CP-08", "CP-09", "CP-10", "CP-11", "CP-13"]

# The leader whose ace is the ceiling for each point, from the ROUTE ORDER (route_N runs from badge N-1 to gym N), written
# here and not read from the table. gym_ace_levels is indexed gym 1..8.
NEXT_GYM = {"CP-01": 2, "CP-03": 3, "CP-05": 4, "CP-06": 4, "CP-07": 5, "CP-08": 5, "CP-09": 6, "CP-10": 7,
            "CP-11": 7, "CP-13": 8}
NPC_ACTORS = [(p, a) for p, a in ACTORS if a["role"] != "seated"]
FIGHTERS = [(p, a) for p, a in ACTORS if a["role"] in ("seated", "fighter", "sider")]
TEAM_ACTORS = FIGHTERS
VARGAS = ["npc_compact_varga_2", "npc_compact_varga_3", "npc_compact_varga_4"]


# ------------------------------------------------------------------------------------------------- the table itself
def test_the_table_builds_exactly_the_points_this_unit_owns_and_not_cp_core_s():
    # CP-04, CP-12 and CP-14 are unit CP-CORE's (the brief): a record here for one of them would be two authors
    assert sorted(POINTS) == sorted(BUILT)
    assert not {"CP-04", "CP-12", "CP-14"} & set(POINTS)


def test_the_owner_s_open_questions_are_listed_with_the_default_built():
    q = TB["owner_questions_defaults"]
    assert sorted(q, key=lambda k: int(k[1:])) == ["O%d" % i for i in range(1, 11)]
    assert all("Not decided" in q[k] or "Default" in q[k] or "Not applicable" in q[k] or "Not touched" in q[k] for k in q)


def test_every_point_names_what_is_built_and_what_is_not():
    for p in TB["points"]:
        assert p.get("built") and p.get("not_built") and p.get("mechanism") and p.get("where"), p["id"]


def test_the_counts_match_the_design_s_planned_trainers_for_these_points():
    # docs/story/HAVEN_COMPACT_PASS.md: CP-01 1, CP-03 2, CP-05 2, CP-06 1, CP-07 3, CP-08 3, CP-10 1, CP-11 2, CP-13 1.
    # (CP-02 and CP-09 have no fight; the design lists 26 in all, 10 of them CP-CORE's)
    want = {"CP-01": 1, "CP-02": 0, "CP-03": 2, "CP-05": 2, "CP-06": 1, "CP-07": 3, "CP-08": 3, "CP-09": 0,
            "CP-10": 1, "CP-11": 2, "CP-13": 1}
    got = {p["id"]: sum(1 for a in p["actors"] if a["role"] in ("seated", "fighter", "sider")) for p in TB["points"]}
    assert got == want
    assert sum(got.values()) == 16


def test_no_fight_in_the_two_points_the_design_keeps_a_place_where_nobody_fights():
    assert [a["id"] for a in POINTS["CP-02"]["actors"] if a["role"] != "talker"] == []
    assert [a["id"] for a in POINTS["CP-09"]["actors"] if a["role"] != "talker"] == []


# ------------------------------------------------------------------------------------------------- bands and teams
def _ceiling(pid):
    return ACES[NEXT_GYM[pid] - 1]


@pytest.mark.parametrize("pid,a", [(p["id"], a) for p, a in TEAM_ACTORS], ids=[a["id"] for _p, a in TEAM_ACTORS])
def test_every_team_tops_out_under_the_next_leader_s_ace_and_inside_its_declared_band(pid, a):
    levels = [m["level"] for m in a["team"]]
    assert max(levels) < _ceiling(pid), (a["id"], levels, _ceiling(pid))
    lo, hi = POINTS[pid]["band"]
    assert lo <= min(levels) and max(levels) <= hi, (a["id"], levels, (lo, hi))
    assert 2 <= len(levels) <= 5


def CP_CORE_VARGA_1():
    """compact_varga_1 from CP-CORE's data/compact_trainers.json when that unit's work is merged here, else None."""
    p = ROOT / "data" / "compact_trainers.json"
    if not p.is_file():
        return None
    return next((t for t in json.loads(p.read_text(encoding="utf-8")).get("trainers", []) if t["id"] == "compact_varga_1"), None)


def test_varga_s_ladder_rises_keeps_her_four_lines_and_stays_under_the_tower_s_58():
    teams = {a["id"]: a["team"] for _p, a in ACTORS if a["id"] in VARGAS}
    fam = {"skorupi": 0, "drapion": 0, "drilbur": 1, "excadrill": 1, "roggenrola": 2, "boldore": 2, "gigalith": 2,
           "zubat": 3, "golbat": 3, "crobat": 3}
    tops = []
    for vid in VARGAS:
        lines = {fam[m["species"]] for m in teams[vid] if m["species"] in fam}
        assert lines == {0, 1, 2, 3}, (vid, "her four lines are skorupi/drapion, drilbur/excadrill, roggenrola/boldore, zubat/golbat")
        tops.append(max(m["level"] for m in teams[vid]))
    assert tops == sorted(tops) and len(set(tops)) == 3, tops
    # the sizes grow or hold (4 at CP-04 is CP-CORE's, then 5, 5, 5)
    assert [len(teams[v]) for v in VARGAS] == sorted(len(teams[v]) for v in VARGAS)
    # once CP-CORE's compact_varga_1 (CP-04) is in data/, hers is the first rung: mine start above it and keep her lines
    first = CP_CORE_VARGA_1()
    if first:
        assert max(m["level"] for m in first["team"]) < tops[0]
        assert {m["species"] for m in first["team"]} <= set(fam), "her first team's species are the same four lines"
    tower = next(t for t in _j("data/hq_trainers.json")["trainers"] if t["id"] == "hq_tower_trainer_07")
    assert max(tops) < min(m["level"] for m in tower["team"]), (tops, [m["level"] for m in tower["team"]])


def _homeless():
    md = (ROOT / "docs/story/ENCOUNTER_GAPS.md").read_text(encoding="utf-8")
    sec = md.split("## Species with no authored home")[1].split("## Thin or incoherent")[0]
    names = []
    for ln in sec.splitlines():
        m = re.match(r"- \*\*Generation \d+ \((\d+)\):\*\* (.*)", ln)
        if m:
            names += [x.strip().rstrip(".") for x in m.group(2).split(",")]
    return {re.sub(r"[^a-z0-9]", "", n.lower().replace("\u2019", "")) for n in names}


# the Compact's signature (O7, default built): species the region has no wild home for, at least half of each team.
# Exempt on purpose: the Merian ranger (a native), and Varga, whose four lines are the HQ tower's own
EXEMPT_SIGNATURE = {"npc_compact_ranger_halloran", "npc_compact_varga_2", "npc_compact_varga_3", "npc_compact_varga_4"}


@pytest.mark.parametrize("a", [a for _p, a in TEAM_ACTORS if a["id"] not in EXEMPT_SIGNATURE],
                         ids=[a["id"] for _p, a in TEAM_ACTORS if a["id"] not in EXEMPT_SIGNATURE])
def test_a_compact_team_is_at_least_half_species_the_region_has_no_wild_home_for(a):
    homeless = _homeless()
    assert len(homeless) == 570          # ENCOUNTER_GAPS.md: "570 do not"
    got = sum(1 for m in a["team"] if m["species"] in homeless)
    assert got * 2 >= len(a["team"]), (a["id"], [m["species"] for m in a["team"]])


def _jar():
    cands = [Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")]
    try:
        import finale_audit
        j = finale_audit.find_jar(None)
        if j:
            cands.append(Path(j))
    except Exception:       # a missing sibling worktree or an unreadable audit must not fail the test, only skip it
        pass
    return next((c for c in cands if c.is_file()), None)


def test_every_move_of_every_team_is_learnable_by_its_species_in_the_1_8_0_jar():
    jar = _jar()
    if jar is None:
        pytest.skip("the Cobblemon 1.8.0 jar is not on this machine")
    z = zipfile.ZipFile(jar)
    names = {n.rsplit("/", 1)[1][:-5]: n for n in z.namelist() if n.startswith("data/cobblemon/species/") and n.endswith(".json")}
    bad = []
    for _p, a in TEAM_ACTORS:
        for m in a["team"]:
            sid = m["species"]
            if sid not in names:
                bad.append("%s: no species %s" % (a["id"], sid))
                continue
            chain, cur = [], sid
            while cur in names and len(chain) < 4:
                d = json.loads(z.read(names[cur]))
                chain.append(d)
                cur = (d.get("preEvolution") or "").split(" ")[0].lower() or None
            how = {}
            for d in chain:
                for e in d.get("moves") or []:
                    k, mv = e.split(":", 1)
                    how.setdefault(mv, set()).add(k)
            assert len(set(m["moveset"])) == len(m["moveset"]) and 3 <= len(m["moveset"]) <= 4, (a["id"], sid)
            for mv in m["moveset"]:
                ks = how.get(mv, set())
                if not (any(k in ("tm", "tutor", "egg") for k in ks) or any(k.isdigit() and int(k) <= m["level"] for k in ks)):
                    bad.append("%s: %s L%d cannot learn %s (jar: %s)" % (a["id"], sid, m["level"], mv, sorted(ks) or "never"))
    assert bad == []


# ------------------------------------------------------------------------------------------------- the emitted records
def test_the_derived_records_are_current_with_the_table():
    # the generator's own drift check, run on the committed files (no heightmap needed)
    assert CP.check(TB) == []


def test_every_id_has_exactly_one_author():
    import id_authorship as IA
    recs = IA.records(ROOT)
    mine = set()
    for _p, a in ACTORS:
        mine.add(a["id"])
        if a["role"] in ("fighter", "sider"):
            mine.add(a["trainer"])
        if a["role"] != "seated":
            mine.add(CP.conv_id(a))
    mine |= {p["quest"] for p in TB["points"] if p.get("quest")}
    multi = {i: sorted(recs.get(i, {})) for i in mine if len(recs.get(i, {})) != 1}
    assert multi == {}
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "id_authorship.py")], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout[-400:]


def test_the_emitted_fields_are_declared_once_and_typed():
    for p in TB["points"]:
        for f in CP.point_fields(p):
            got = FIELDS.get(f["id"])
            assert got == f, f["id"]
    ids = [f["id"] for f in PROG["quest_fields"]]
    assert len(ids) == len(set(ids))


def test_every_conversation_is_listed_by_its_quest_and_every_quest_field_is_listed_by_its_quest():
    for p in TB["points"]:
        npcs = [a for a in p["actors"] if a["role"] != "seated"]
        if not npcs:
            assert not p.get("quest")
            continue
        q = QUESTS[p["quest"]]
        assert sorted(q["dialogue_ids"]) == sorted(CP.conv_id(a) for a in npcs)
        for f in CP.point_fields(p):
            if f["quest_id"] == p["quest"]:
                assert f["id"] in q["progression_field_refs"]
        assert q["optional"] is True and q["progression_gate"] == []


# ------------------------------------------------------------------------------------------------- no badge is gated
def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def test_no_point_gates_a_badge_and_none_sets_one():
    # a point is optional: nothing it emits reads or writes a gym flag, a badge field or the league
    for p, a in NPC_ACTORS:
        for d in _walk(DIALOGUE[CP.conv_id(a)]):
            assert d.get("kind") != "flag", (a["id"], d)
            f = d.get("field") or ""
            assert not re.search(r"gym\d|badge|league|champion", f), (a["id"], f)
    for p in TB["points"]:
        if p.get("quest"):
            for d in _walk(QUESTS[p["quest"]]):
                assert d.get("kind") not in ("grant_flag", "set_flag"), p["quest"]
                f = d.get("field") or ""
                assert not f.startswith("quest.main_worldshift_reveal") or d.get("kind") != "set_progression", (p["quest"], f)
    for t in TRAINERS.values():
        assert "sets" not in t and "gates" not in t


# ------------------------------------------------------------------------------------------------- the window
def _cond(c, st):
    k = c["kind"]
    if k == "always":
        return True
    if k == "all":
        return all(_cond(x, st) for x in c["conditions"])
    if k == "progression_equals":
        return st(c["field"]) == c["value"]
    if k == "progression_in":
        return st(c["field"]) in c["values"]
    raise AssertionError("condition kind %s is not modelled" % k)


def _state(overrides):
    def st(field):
        if field in overrides:
            return overrides[field]
        return FIELDS[field]["initial"]
    return st


def _enter(conv, overrides):
    """The node the conversation opens on for a player in this state (entry rules in priority order)."""
    st = _state(overrides)
    for r in sorted(conv["entry_rules"], key=lambda r: r["priority"]):
        if _cond(r["when"], st):
            return st(conv["cursor"]["progression_field"]) if r["node"] == "$cursor" else r["node"]
    raise AssertionError("no entry rule matched for %s" % conv["id"])


def _nodes(conv):
    return {n["id"]: n for n in conv["nodes"]}


def _read(conv, node):
    """Follow `next` links from a node until a choice, a self-loop or the end: the ids read, and the node stopped on."""
    ns, seen = _nodes(conv), []
    while True:
        seen.append(node)
        n = ns[node]
        if n["kind"] == "choice":
            return seen, n
        nxt = n.get("next")
        if nxt is None or nxt == node or nxt in seen:
            return seen, n
        node = nxt


def _before(stage_idx):
    return {STAGE: STAGES[stage_idx]}


@pytest.mark.parametrize("pid,a", [(p["id"], a) for p, a in NPC_ACTORS], ids=[a["id"] for _p, a in NPC_ACTORS])
def test_no_compact_npc_opens_before_brock_account_heard_and_every_one_opens_at_its_own_stage(pid, a):
    conv = DIALOGUE[CP.conv_id(a)]
    point = POINTS[pid]
    first = STAGES.index(point["from_stage"])
    assert first >= STAGES.index("brock_account_heard")
    for i in range(0, first):
        node = _enter(conv, _before(i))
        assert node == CP.short(a) + "_before", (a["id"], STAGES[i], node)
        _seen, end = _read(conv, node)
        assert end["kind"] == "line", "a conversation outside its window offers no choice and so no fight"
    for i in range(first, len(STAGES)):
        node = _enter(conv, _before(i))
        assert node != CP.short(a) + "_before", (a["id"], STAGES[i])


# ------------------------------------------------------------------------------------------------- fights
def _battle_responses(conv):
    return [(n, r) for n in conv["nodes"] if n.get("kind") == "choice" for r in n["responses"]
            if any(x["kind"] == "npc_battle" for x in r.get("actions") or [])]


@pytest.mark.parametrize("pid,a", [(p["id"], a) for p, a in NPC_ACTORS if a["role"] in ("fighter", "sider")],
                         ids=[a["id"] for p, a in NPC_ACTORS if a["role"] in ("fighter", "sider")])
def test_every_npc_battle_names_an_over_cap_line_and_a_team_that_the_class_carries(pid, a):
    conv = DIALOGUE[CP.conv_id(a)]
    ns = _nodes(conv)
    resp = _battle_responses(conv)
    assert len(resp) == 1
    node, r = resp[0]
    act = next(x for x in r["actions"] if x["kind"] == "npc_battle")
    assert act["format"] == "singles"
    assert ns[act["over_cap_node"]]["kind"] == "line"
    assert ns[act["over_cap_node"]]["next"] == node["id"], "the refusal returns to the choice, not past it"
    assert conv["npc_battle"] == {"trainers": "compact_route_npc_teams.json", "trainer": a["trainer"], "skill": a["skill"]}
    assert NPC_TEAMS[a["trainer"]]["team"] == a["team"]


def test_the_compiler_accepts_every_conversation_and_gives_each_fighter_its_party():
    files, _done, refused = CD.build_all(ROOT / "data")
    mine = {CP.conv_id(a) for _p, a in NPC_ACTORS}
    assert not (mine & set(refused)), sorted(mine & set(refused))
    norm = {k.replace("\\", "/"): v for k, v in files.items()}
    for _p, a in NPC_ACTORS:
        cls = norm["data/cobblers/npcs/%s.json" % a["id"]]
        cls = json.loads(cls) if isinstance(cls, (str, bytes)) else cls
        if a["role"] in ("fighter", "sider"):
            party = cls["party"]["pokemon"]
            assert len(party) == len(a["team"])
            for m, s in zip(a["team"], party):
                assert s.startswith(m["species"] + " ") and "level=%d" % m["level"] in s
                assert "moves=" + ",".join(m["moveset"]) in s
            assert cls["battleConfiguration"] == {"canChallenge": False}
        else:
            assert "party" not in cls, "%s talks and never fights" % a["id"]
        assert cls["names"] == [a["name"]]


def _fight(pid, aid):
    p = POINTS[pid]
    return next(x for x in p["actors"] if x["id"] == aid)


def test_a_fighter_offers_the_choice_after_its_intro_and_afterwards_only_its_after_line():
    p = POINTS["CP-01"]
    a = _fight("CP-01", "npc_compact_courier_ansel")
    conv = DIALOGUE[CP.conv_id(a)]
    s = CP.short(a)
    ov = {STAGE: "brock_account_heard"}
    seen, end = _read(conv, _enter(conv, ov))
    assert seen == [s + "_001", s + "_002", s + "_003", s + "_choice"] and end["kind"] == "choice"
    # close mid-intro or at the choice and reopen at the choice
    ov2 = dict(ov, **{"quest.%s.%s_cursor" % (p["quest"], s): s + "_choice"})
    assert _enter(conv, ov2) == s + "_choice"
    # beaten: the after line, never the choice
    ov3 = dict(ov, **{"quest.evt_compact_courier_spar.compact_courier_ansel_defeated": True})
    seen, end = _read(conv, _enter(conv, ov3))
    assert end["kind"] == "line" and seen[0] == s + "_after_001"


def test_varga_refuses_until_the_crew_in_front_of_her_are_beaten():
    a = _fight("CP-07", "npc_compact_varga_2")
    conv = DIALOGUE[CP.conv_id(a)]
    base = {STAGE: "erika_reveal_complete"}
    c1, c2 = "quest.compact_anchor_crew_01.defeated", "quest.compact_anchor_crew_02.defeated"
    for ov in (base, dict(base, **{c1: True}), dict(base, **{c2: True})):
        _seen, end = _read(conv, _enter(conv, ov))
        assert end["kind"] == "line" and "_blocked_" in end["id"], ov
    seen, end = _read(conv, _enter(conv, dict(base, **{c1: True, c2: True})))
    assert end["kind"] == "choice" and seen[0].endswith("_001")


def test_varga_at_the_bridge_waits_for_the_guard_and_the_guard_is_not_blocked_by_anyone():
    g = _fight("CP-11", "npc_compact_bridge_guard")
    v = _fight("CP-11", "npc_compact_varga_3")
    base = {STAGE: "sabrina_reveal_complete"}
    _seen, end = _read(DIALOGUE[CP.conv_id(v)], _enter(DIALOGUE[CP.conv_id(v)], base))
    assert end["kind"] == "line" and "_blocked_" in end["id"]
    seen, end = _read(DIALOGUE[CP.conv_id(g)], _enter(DIALOGUE[CP.conv_id(g)], base))
    assert end["kind"] == "choice"
    done = dict(base, **{"quest.evt_compact_bridge.compact_bridge_guard_ode_defeated": True})
    _seen, end = _read(DIALOGUE[CP.conv_id(v)], _enter(DIALOGUE[CP.conv_id(v)], done))
    assert end["kind"] == "choice"


def test_the_cirque_choice_makes_the_other_one_fight_and_both_routes_end_in_the_same_fact():
    R = _fight("CP-05", "npc_compact_ranger_halloran")
    S = _fight("CP-05", "npc_compact_surveyor_marn")
    cr, cs = DIALOGUE[CP.conv_id(R)], DIALOGUE[CP.conv_id(S)]
    sw = "quest.evt_compact_cirque_survey.sided_with"
    base = {STAGE: "surge_reveal_complete"}
    # nobody has sided: each offers the side choice (and neither a fight)
    for conv in (cr, cs):
        seen, end = _read(conv, _enter(conv, base))
        assert end["kind"] == "choice" and end["id"].endswith("_side_choice")
        assert not _battle_responses(conv) or all(n["id"] != end["id"] for n, _r in _battle_responses(conv))
    # sided with the ranger: the SURVEYOR fights, the ranger only thanks. The transition that records the side also moves the
    # ranger's cursor to his thanks line (asserted below from the quest), so the state after it carries both
    thanks = "quest.evt_compact_cirque_survey.ranger_halloran_cursor"
    ov = dict(base, **{sw: "ranger", thanks: "ranger_halloran_side_thanks"})
    seen, end = _read(cs, _enter(cs, ov))
    assert end["id"].endswith("_choice") and not end["id"].endswith("side_choice")
    _seen, end = _read(cr, _enter(cr, ov))
    assert end["kind"] == "line" and "side" in end["id"]
    # sided with the surveyor: the RANGER fights
    ov = dict(base, **{sw: "surveyor"})
    seen, end = _read(cr, _enter(cr, ov))
    assert end["kind"] == "choice" and not end["id"].endswith("side_choice")
    # after the fight each loser says the same fact: the survey missed people
    won = dict(base, **{sw: "ranger", "quest.evt_compact_cirque_survey.compact_surveyor_marn_defeated": True})
    _seen, end = _read(cs, _enter(cs, won))
    assert "thirty-one children" in end["text"]
    won = dict(base, **{sw: "surveyor", "quest.evt_compact_cirque_survey.compact_ranger_halloran_defeated": True})
    _seen, end = _read(cr, _enter(cr, won))
    assert "counts nobody who lives in the huts" in end["text"]
    # the side transition exists, is one-shot (reads sided_with == none) and sets the cursor the choice points at
    tr = {t["id"]: t for t in QUESTS["evt_compact_cirque_survey"]["transitions"]}
    assert sorted(tr) == ["side_ranger", "side_surveyor"]
    for side, t in (("ranger", tr["side_ranger"]), ("surveyor", tr["side_surveyor"])):
        assert t["conditions"] == [{"kind": "progression_equals", "field": sw, "value": "none"}]
        who = "ranger_halloran" if side == "ranger" else "surveyor_marn"
        assert {"kind": "set_progression", "field": sw, "value": side} in t["effects"]
        assert {"kind": "set_progression", "field": "quest.evt_compact_cirque_survey.%s_cursor" % who,
                "value": who + "_side_thanks"} in t["effects"]
    assert FIELDS[sw]["allowed_values"] == ["none", "ranger", "surveyor"] and FIELDS[sw]["initial"] == "none"


def test_the_dissenter_medic_changes_what_she_says_once_varga_is_beaten():
    m = _fight("CP-13", "npc_compact_dissenter_medic")
    conv = DIALOGUE[CP.conv_id(m)]
    base = {STAGE: "blaine_reveal_complete"}
    seen, _e = _read(conv, _enter(conv, base))
    assert "Lieutenant Varga means to stop us" in _nodes(conv)[seen[1]]["text"]
    done = dict(base, **{"quest.evt_compact_rearguard.compact_varga_4_defeated": True})
    seen, end = _read(conv, _enter(conv, done))
    assert "She let us through" in _nodes(conv)[seen[0]]["text"]


# ------------------------------------------------------------------------------------------------- the result is recorded
def test_the_callback_matches_each_npc_fighter_by_its_stand_and_each_won_function_sets_that_players_field():
    files = CP.pack_files(TB)
    cb = files[CP.CALLBACK]
    fns = {k: v for k, v in files.items() if k.endswith(".mcfunction")}
    fighters = [(p, a) for p, a in NPC_ACTORS if a["role"] in ("fighter", "sider")]
    assert len(fns) == len(fighters) == 9
    sels = re.findall(r"@s\[type=cobblemon:npc,x=(-?\d+)\.5,y=(-?\d+),z=(-?\d+)\.5,distance=\.\.1\.5\] as ' \+ t\.w\.player\.uuid \+ "
                      r"' run function cobblers:compact_routes/(\w+)'", cb)
    assert len(sels) == len(fighters)
    for p, a in fighters:
        seat = NPC_SEATS[a["id"]]["at"]
        hit = [s for s in sels if s[3] == "won_" + a["trainer"]]
        assert len(hit) == 1 and [int(v) for v in hit[0][:3]] == seat, a["id"]
        text = fns["data/cobblers/function/compact_routes/won_%s.mcfunction" % a["trainer"]]
        field = "quest.%s.%s_defeated" % (p["quest"], a["trainer"])
        assert field in FIELDS and FIELDS[field]["type"] == "boolean"
        assert "t.d.cobblers__%s = 1;" % field.replace(".", "__") in text
        assert text.count("runmolang") == 1 and "@s" in text
    # no two stands inside one another's callback radius, and the callback fires only for a CPU NPC loser
    for i, a in enumerate(sels):
        for b in sels[i + 1:]:
            assert math.dist([int(v) for v in a[:3]], [int(v) for v in b[:3]]) > 3.0
    assert "t.l.is_npc ?" in cb and "c.player_winners" in cb
    assert CP.CALLBACK.startswith("data/cobblemon/callbacks/battle_victory/")


def test_the_pack_is_registered_where_reapply_installs_and_classifies_packs():
    import reapply
    assert "cobblers_compact_routes" in reapply.SERVER_PACKS
    assert "cobblers_compact_routes" in reapply.WORLD_LOCAL
    assert str(reapply.EXCLUDED.get("cobblers_compact_routes", "")).strip()


# ------------------------------------------------------------------------------------------------- the seated fighters
def test_the_seated_fighters_reach_route_trainers_with_a_defeat_advancement_and_one_home_line():
    import route_trainers as RT
    fs = RT.files()
    cycle = "\n".join(fs["data/cobblers/function/trainers/cycle.mcfunction"])
    placed = {p[0]: p for p in RT.placements()}
    for tid, t in TRAINERS.items():
        assert tid in placed and list(placed[tid][1]) == t["seat"] and placed[tid][2] == t["yaw"]
        adv = fs["data/cobblers/advancement/trainer/%s.json" % tid]
        assert adv["criteria"]["won"]["conditions"]["trainer_ids"][0] == tid
        assert "quest.%s.defeated" % tid in FIELDS
        team = fs["data/rctmod/trainers/%s.json" % tid]["team"]
        assert team == [m for _p, a in ACTORS if a["id"] == tid for m in a["team"]]
        mob = fs["data/rctmod/mobs/trainers/single/%s.json" % tid]
        assert mob["forceBattleOnSight"] is True if tid == "compact_relay_tech_01" else "forceBattleOnSight" not in mob
        assert cycle.count('TrainerId:"%s",InBattle:0b}]' % tid) == 1
    assert len(TRAINERS) == 7


# ------------------------------------------------------------------------------------------------- where they stand
def _ground():
    try:
        import ground as G
        from terrain import TerrainUnavailable
    except ImportError:
        pytest.skip("the ground module is not importable")
    try:
        return G.Ground()
    except (TerrainUnavailable, SystemExit, OSError) as e:
        pytest.skip("the canonical heightmap is not readable here: %s" % e)


def _seg_dist(x, z, paths):
    best = 1e9
    for cells in paths.values():
        for (ax, az), (bx, bz) in zip(cells, cells[1:]):
            if abs(ax - x) > 40 and abs(bx - x) > 40:
                continue
            dx, dz = bx - ax, bz - az
            L = dx * dx + dz * dz
            t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / L)) if L else 0.0
            best = min(best, math.hypot(ax + t * dx - x, az + t * dz - z))
    return best


def _seat_of(a):
    return TRAINERS[a["id"]]["seat"] if a["role"] == "seated" else NPC_SEATS[a["id"]]["at"]


def _ring_has(pt, ring):
    x, z = pt
    c = False
    for (x1, z1), (x2, z2) in zip(ring, ring[1:] + ring[:1]):
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            c = not c
    return c


def test_every_actor_stands_on_its_ground_off_the_road_and_apart_from_every_other_seat():
    g = _ground()
    paths = _j("data/route_paths.json")["paths"]
    others = []
    for f in ("route_trainers.json", "late_route_trainers.json", "vr_trainers.json", "mansion_guardians.json",
              "hq_trainers.json", "gym_junior_trainers.json"):
        others += [(t["id"], t["seat"]) for t in _j("data/" + f)["trainers"] if t.get("seat") and t.get("seated", True)]
    mine = {a["id"] for _p, a in ACTORS}
    others += [(s["id"], s["at"]) for s in _j("data/npc_seats.json")["seats"] if s["id"] not in mine]
    placements = _j("data/placements.json")["settlements"]
    for p, a in ACTORS:
        x, y, z = _seat_of(a)
        ground = TRAINERS[a["id"]]["ground"] if a["role"] == "seated" else NPC_SEATS[a["id"]]["ground"]
        if ground["kind"] == "plaza":
            plaza = placements[NPC_SEATS[a["id"]]["settlement"]]["plan"]["plaza"]
            r = plaza["rect"]
            assert r[0] <= x <= r[2] and r[1] <= z <= r[3] and ground["y"] == plaza["y"], a["id"]
        else:
            assert ground["y"] == g(x, z), (a["id"], "the heightmap says", g(x, z))
        assert y == ground["y"] + 1, a["id"]
        assert ground["y"] >= 64, "%s stands at y%d, a block or two over the sea (y62)" % (a["id"], ground["y"])
        d = _seg_dist(x, z, paths)
        assert d >= (2.2 if a["role"] == "seated" else 3.0), (a["id"], d)
        need = 8.0 if a["role"] == "seated" else 3.0
        for oid, (ox, _oy, oz) in others:
            assert math.hypot(ox - x, oz - z) >= need, (a["id"], oid)
    seats = [(a["id"], _seat_of(a)) for _p, a in ACTORS]
    for i, (ia, sa) in enumerate(seats):
        for ib, sb in seats[i + 1:]:
            assert math.hypot(sa[0] - sb[0], sa[2] - sb[2]) >= 3.0, (ia, ib)


def test_the_dock_and_the_bridge_are_kept_clear():
    g = _ground()
    x, y, z = NPC_SEATS["npc_compact_boarding_hask"]["at"]
    assert y - 1 >= 79 > 77, "the officer stands above Lake Tilpey's level (y77), on the north shore"
    dock = next(d for d in _j("data/ferry_docks.json")["docks"] if d["id"] == "tilpey_sabrina_dock")
    assert math.hypot(x - dock["shore"]["at"][0], z - dock["shore"]["at"][1]) >= 8.0
    br = next(b for b in _j("data/bridges.json")["bridges"] if b["id"] == "route7_tilpey_outflow")
    c = br["centre"]
    for aid in ("npc_compact_bridge_guard", "npc_compact_varga_3"):
        ax, _ay, az = NPC_SEATS[aid]["at"]
        assert abs(ax - c) >= 6 and az < br["along_from"], (aid, "stands beside the approach, not on the walkway or the deck")
    assert g(x, z) == y - 1


def test_every_actor_stands_in_the_subregion_the_table_says_by_the_polygons_of_regions_json():
    subs = {s["id"]: s for s in _j("data/regions.json")["subregions"]}
    want = TB["subregions"]
    named = {k for k in want if k != "why"}
    assert named <= {a["id"] for _p, a in ACTORS}
    # every actor on open ground is checked here; a town's plaza actors are checked against the plaza above
    outdoor = {a["id"] for _p, a in ACTORS
               if (TRAINERS[a["id"]] if a["role"] == "seated" else NPC_SEATS[a["id"]])["ground"]["kind"] == "heightmap"}
    assert outdoor <= named, sorted(outdoor - named)
    for aid in named:
        x, _y, z = _seat_of(next(a for _p, a in ACTORS if a["id"] == aid))
        assert any(_ring_has((x, z), r) for r in subs[want[aid]]["polygons"]), (aid, want[aid])


# ------------------------------------------------------------------------------------------------- the point's shape
def test_the_early_points_are_sympathy_and_the_first_secret_and_the_late_ones_carry_the_escalation():
    # ARC rule 3/5: nobody before the Craters is an enemy of the families; the escalation is Varga's ladder and the bridge
    for pid in ("CP-01", "CP-02"):
        text = json.dumps(POINTS[pid]).lower()
        assert "sympathy" in text
    assert [a["id"] for a in POINTS["CP-01"]["actors"] if a["role"] == "fighter"] == ["npc_compact_courier_ansel"]
    v = {a["id"]: POINTS[p["id"]] for p, a in ACTORS if a["id"] in VARGAS}
    assert [v[k]["id"] for k in VARGAS] == ["CP-07", "CP-11", "CP-13"]
    for aid in VARGAS:
        assert STAGES.index(v[aid]["from_stage"]) >= STAGES.index("erika_reveal_complete")


# ------------------------------------------------------------------------------------------------- mutation: the GENERATOR
def _window_problems(convs):
    probs = []
    for c in convs:
        a = next(x for _p, x in ACTORS if CP.conv_id(x) == c["id"])
        first = STAGES.index(next(p for p, x in ACTORS if x is a)["from_stage"])
        for i in range(first):
            node = _enter(c, _before(i))
            if node != CP.short(a) + "_before":
                probs.append((c["id"], STAGES[i]))
    return probs


def test_mutated_generator_opening_the_window_early_is_caught(monkeypatch):
    real = CP.window
    assert _window_problems(CP.derive(TB, CP.stored_seats(TB))["conversations"]) == []
    monkeypatch.setattr(CP, "window", lambda point: STAGES[STAGES.index("pallet_complete"):] if real(point) else None)
    got = _window_problems(CP.derive(TB, CP.stored_seats(TB))["conversations"])
    assert got, "a generator that opens every point at pallet_complete must be caught by the stage-window check"


def test_mutated_generator_dropping_the_over_cap_refusal_is_caught(monkeypatch):
    real_line = CP.line

    def broken(i, speaker, text, nxt, **extra):
        if i.endswith("_over_cap"):
            nxt = i                                             # the refusal no longer returns to the choice
        return real_line(i, speaker, text, nxt, **extra)
    monkeypatch.setattr(CP, "line", broken)
    convs = CP.derive(TB, CP.stored_seats(TB))["conversations"]
    bad = 0
    for c in convs:
        ns = _nodes(c)
        for node, r in _battle_responses(c):
            act = next(x for x in r["actions"] if x["kind"] == "npc_battle")
            if ns[act["over_cap_node"]]["next"] != node["id"]:
                bad += 1
    assert bad == 9, "all nine fighters' refusals must show as not returning to the choice"


def test_mutated_generator_unblocking_varga_is_caught(monkeypatch):
    real = CP.eq

    def broken(field, value):
        if value is False and "crew" in field:
            return {"kind": "always"}                           # the blocked rule would then fire for everyone
        return real(field, value)
    monkeypatch.setattr(CP, "eq", broken)
    convs = {c["id"]: c for c in CP.derive(TB, CP.stored_seats(TB))["conversations"]}
    conv = convs["dlg_compact_varga_2"]
    ov = {STAGE: "erika_reveal_complete", "quest.compact_anchor_crew_01.defeated": True,
          "quest.compact_anchor_crew_02.defeated": True}
    _seen, end = _read(conv, _enter(conv, ov))
    assert end["kind"] == "line" and "_blocked_" in end["id"], "the mutation must make Varga refuse a player who beat both"


def test_mutated_seat_finder_that_ignores_the_road_is_caught_by_the_road_check(monkeypatch):
    # the seats are proved against the walked SEGMENTS here; a finder that stops caring about the road would seat an
    # immovable NPC on it. Run it on one shoulder actor, on the heightmap, with route_dist forced far away.
    g = _ground()
    sea = CP.Seater(g)
    monkeypatch.setattr(sea, "route_dist", lambda x, z: 99.0)
    p = POINTS["CP-01"]
    a = p["actors"][0]
    spec = dict(a["seat"], offsets=[0, 1])                      # 0 and 1 off the line: on the road itself
    res = sea.seat_route_shoulder(p, a, spec)
    assert res is not None
    x, _y, z = res["at"]
    assert _seg_dist(x, z, _j("data/route_paths.json")["paths"]) < 3.0, "the mutated finder stands on the road, and the check sees it"
