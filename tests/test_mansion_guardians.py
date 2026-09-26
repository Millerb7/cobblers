"""The Gastly mansion's five Channeler guardians (data/mansion_guardians.json) against the escort they gate.

Written by the test author, not by the session that added the guardians.

What is asserted, on the real data (data/mansion_guardians.json, data/quests.json evt_route1_gastly_family,
data/progression.json, data/dialogue.json, data/scenes.json route1_gastly_family, data/placements.json):

  records     five guardians, distinct ids none of which data/trainers.json uses, one per escort room in checkpoint
              order, each with its own guard field; the record's `team` is the team rct ships
  fields      quest.evt_route1_gastly_family.guard_1..5 are declared once each, player-scoped booleans, initial false,
              and listed in the quest's progression_field_refs
  gating      each guardian's `gates` is a transition of the quest that moves the checkpoint off the guardian's room;
              it requires exactly that guardian's guard field == true; no other transition reads a guard field; and
              every transition that moves the checkpoint off a room (except `start`) is the gated one
  RCT data    tools/route_trainers.files() for each guardian: trainer keys within {name, ai, bag, team, battleRules},
              team == the record's rct.team; the mob never spawns naturally, is beaten once, forces a battle on sight,
              wears the record's rctmod single-trainer texture; the dialog keys carry the record's three lines; the
              won function sets exactly the record's `sets` (never quest.<id>.defeated) and saves; the advancement is
              defeat_count for this id at count 1
  seats       replaying the house (data/placements.json route1_mansion_house), each seat is standable (feet air or
              thin, head air, solid below), inside the scene's area, and not within one block of a prop or of any
              marker slot of scene route1_gastly_family
  walk        an offline breadth-first walk over every click a player can make (open any of the quest's
              conversations, acknowledge a line, pick any visible response, walk into a zone, beat a guardian that is
              allowed in that walk): with guardian N unbeaten the checkpoint never passes N's room, and no dialogue
              page or entry rule offers N's room's way forward; with every guardian beatable the escort reaches
              `family`, completes, and grants reward_spell_tag exactly once. Run under two readings of a response
              that runs a transition: "compiled" (tools/compile_dialogue.py: the page shown next is whatever the
              cursor field holds after the transition) and "authored" (the response's `next`, as the data reads)
  R17         tools/route_trainers.placements() is the route seats followed by the guardians' seats; R17's trainer
              branch (driven with a fake RCON, never a server) selects the trainer by its TrainerId, teleports it to
              its seat and yaw, and pins it with movement_speed 0, whether it was just summoned or already there

Not covered, and it needs a running server: that rctmod's defeat_count fires for a guardian's winner (EXP-027 proved
the form for gym leaders); that nbt={TrainerId:"..."} is the key rctmod saves and the selector matches; that a
trainer at movement speed 0 still turns and battles on sight (forceBattleOnSight) and does not drift; that the
channeler_* textures exist in rctmod 0.18.1 (the jar is not in the repository); that the movesets are legal in
Cobblemon 1.8.0; that one guardian's sight line does not reach through a wall into the next room; that the scene
runtime and the compiled dialogue behave as the walk models them.
"""
import json
import math
import re
import sys
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_audit as BA  # noqa: E402
import reapply  # noqa: E402
import route1_mansion as RM  # noqa: E402
import route_trainers as RT  # noqa: E402


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


QID = "evt_route1_gastly_family"
GUARDS = _load("mansion_guardians.json")["trainers"]
GIDS = [g["id"] for g in GUARDS]
QUEST = next(q for q in _load("quests.json")["quests"] if q["id"] == QID)
T = {t["id"]: t for t in QUEST["transitions"]}
PROG = _load("progression.json")["quest_fields"]
FIELDS = {f["id"]: f for f in PROG}
CONVS = {c["id"]: c for c in _load("dialogue.json")["conversations"] if c["id"] in QUEST["dialogue_ids"]}
SCENE = next(s for s in _load("scenes.json")["scenes"] if s["id"] == "route1_gastly_family")
ROUTE_SEATS = _load("route_trainers.json")["trainers"]
ROUTE_TRAINER_IDS = {r["id"] for r in _load("trainers.json")["trainers"]}
PLACEMENTS = _load("placements.json")

CP_FIELD = "quest.%s.checkpoint" % QID
CHECKPOINTS = FIELDS[CP_FIELD]["allowed_values"].split("|")
GUARD_FIELD = {g["id"]: g["sets"][0] for g in GUARDS}
RECORD_KEYS = {"id", "display_name", "room", "checkpoint", "gates", "sets", "seat", "yaw", "skin", "eye_contact",
               "team", "dialogue_text", "after_win", "rct", "sight_distance"}
ALLOWED_TRAINER_KEYS = {"name", "ai", "bag", "team", "battleRules"}


def _guard_conds(t):
    return [c for c in t["conditions"] if c.get("field") in GUARD_FIELD.values()]


def _sets(t, field):
    return [e["value"] for e in t["effects"] if e["kind"] == "set_progression" and e["field"] == field]


# ------------------------------------------------------------------------------------------------ records and fields

# Without it a guardian is dropped, doubled, or reuses a route trainer's id and one of the two overwrites the other's
# RCT files in cobblers_trainers.
def test_there_are_five_guardians_with_distinct_ids_no_route_trainer_uses():
    assert len(GIDS) == 5 and len(set(GIDS)) == 5
    assert not set(GIDS) & ROUTE_TRAINER_IDS


# Without it a record loses a field the generator or R17 reads (seat, skin, sets) or grows one nothing reads.
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_each_guardian_record_has_exactly_the_documented_fields(g):
    assert set(g) == RECORD_KEYS, set(g) ^ RECORD_KEYS
    assert g["eye_contact"] is True
    assert g["rct"]["name"] == {"literal": g["display_name"]}


# Without it the readable `team` and the shipped rct.team drift apart, and a review of one approves the other.
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_the_records_team_is_the_team_rct_ships(g):
    assert g["team"] and g["team"] == g["rct"]["team"]


# Without it two guardians guard one room and another room has none, or the gauntlet runs out of order.
def test_the_guardians_take_the_five_rooms_in_checkpoint_order_each_with_its_own_field():
    assert [g["checkpoint"] for g in GUARDS] == CHECKPOINTS[:5]
    assert CHECKPOINTS[5] == "family"
    assert [g["sets"] for g in GUARDS] == [["quest.%s.guard_%d" % (QID, n)] for n in range(1, 6)]


# Without it a guard field is undeclared (the generator refuses, or the runtime reads an unset key), world-scoped (one
# player's win opens the room for everyone), or starts true (the room is open from the start).
@pytest.mark.parametrize("n", range(1, 6))
def test_each_guard_field_is_a_declared_player_boolean_starting_false(n):
    fid = "quest.%s.guard_%d" % (QID, n)
    decl = [f for f in PROG if f["id"] == fid]
    assert len(decl) == 1, "%s declared %d times" % (fid, len(decl))
    f = decl[0]
    assert (f["quest_id"], f["type"], f["scope"], f["initial"]) == (QID, "boolean", "player", False)
    assert fid in QUEST["progression_field_refs"]


# ------------------------------------------------------------------------------------------------ gating

# Without it a guardian names a transition the quest does not have (its room is not gated at all), or one that does
# not move the checkpoint off its room (the gate holds a puzzle step, not the exit).
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_each_guardian_gates_the_transition_that_leaves_its_room(g):
    t = T.get(g["gates"])
    assert t is not None, "%s gates %s, which the quest does not have" % (g["id"], g["gates"])
    assert {"kind": "progression_equals", "field": CP_FIELD, "value": g["checkpoint"]} in t["conditions"]
    nxt = CHECKPOINTS[CHECKPOINTS.index(g["checkpoint"]) + 1]
    assert _sets(t, CP_FIELD) == [nxt]


# Without it a room opens on another room's guardian, on a guard == false, or on no guardian at all.
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_the_gated_transition_requires_exactly_its_guardians_field_true(g):
    assert _guard_conds(T[g["gates"]]) == [{"kind": "progression_equals", "field": GUARD_FIELD[g["id"]], "value": True}]


STARTS = {"start", "start_guarded"}
STARTED = "quest.%s.started" % QID
CURSOR = "quest.%s.dialogue_cursor" % QID


# Without it a second, ungated transition moves the checkpoint off a room (a bypass), or some transition reads a
# guard field nobody reasoned about. The two starts may read guard_1, and only to choose Pip's opening page.
def test_only_the_gated_transitions_leave_a_room_or_read_a_guard_field():
    gated = {g["gates"] for g in GUARDS}
    readers = {tid for tid, t in T.items() if _guard_conds(t)}
    assert readers == gated | STARTS
    leavers = {tid for tid, t in T.items() if _sets(t, CP_FIELD) and _sets(t, CP_FIELD) != [CHECKPOINTS[0]]}
    assert leavers == gated
    entrants = {tid for tid, t in T.items() if _sets(t, CP_FIELD) == [CHECKPOINTS[0]]}
    assert entrants == STARTS
    # nothing but a guardian's won function writes a guard field: no transition sets one
    assert not [tid for tid, t in T.items() for e in t["effects"] if e.get("field") in GUARD_FIELD.values()]


# Without it a start transition could read another guardian's field, start an escort already under way, or the two
# starts could overlap (both fire, the last cursor wins) or leave a gap (neither fires and Pip's "Come with me."
# does nothing). They must differ only in the page Pip opens on.
def test_the_two_starts_split_on_guard_1_and_differ_only_in_pips_page():
    g1 = GUARD_FIELD[GIDS[0]]
    for tid in STARTS:
        t = T[tid]
        assert {"kind": "progression_equals", "field": STARTED, "value": False} in t["conditions"]
        assert {c["field"] for c in _guard_conds(t)} == {g1}
    assert {c["value"] for tid in STARTS for c in _guard_conds(T[tid])} == {True, False}
    assert _guard_conds(T["start"]) == [{"kind": "progression_equals", "field": g1, "value": True}]
    assert _guard_conds(T["start_guarded"]) == [{"kind": "progression_equals", "field": g1, "value": False}]
    other = lambda t: [e for e in t["effects"] if e.get("field") != CURSOR]
    assert other(T["start"]) == other(T["start_guarded"])
    assert _sets(T["start"], CURSOR) == ["p_foyer"]
    guarded_page = [r["node"] for r in CONVS[PIP]["entry_rules"]
                    if {"kind": "progression_equals", "field": g1, "value": False} in r["when"].get("conditions", [])]
    assert _sets(T["start_guarded"], CURSOR) == guarded_page


# Without it Pip's conversation (or a prop's) is refused by tools/compile_dialogue.py and silently left out of the
# pack: every click on Pip opens nothing and the escort cannot start. This is how p_come_guarded first shipped.
def test_every_escort_conversation_compiles_into_the_pack():
    import compile_dialogue as CD
    files, done, refused = CD.build_all(ROOT / "data")
    ids = QUEST["dialogue_ids"]
    assert PIP in ids and len(ids) >= 10
    assert {c: refused[c] for c in ids if c in refused} == {}
    assert set(ids) <= set(done)
    assert all("data/cobblers/dialogues/%s.json" % c in files for c in ids)


# ------------------------------------------------------------------------------------------------ RCT data

@pytest.fixture(scope="module")
def files():
    return RT.files()


# Without it a key rctapi does not read is shipped and silently ignored, or the guardian fights with another team.
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_guardian_trainer_files_carry_only_read_keys_and_the_records_team(files, g):
    doc = files["data/rctmod/trainers/%s.json" % g["id"]]
    assert set(doc) <= ALLOWED_TRAINER_KEYS, set(doc) - ALLOWED_TRAINER_KEYS
    assert doc["team"] == g["rct"]["team"] and doc["team"]
    assert doc["name"] == g["rct"]["name"]


# Without it a Channeler spawns naturally across the world, can be farmed, lets the player walk past without a fight,
# sees as far as a route trainer (8 blocks, through walls, into the next room), or wears a texture that is not the
# record's (or not one of rctmod's own, so a client shows a missing skin).
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_guardian_mobs_never_spawn_are_beaten_once_battle_on_sight_and_wear_the_records_skin(files, g):
    mob = files["data/rctmod/mobs/trainers/single/%s.json" % g["id"]]
    assert mob["spawnWeightFactor"] == 0
    assert mob["maxTrainerDefeats"] == 1
    assert mob.get("forceBattleOnSight") is True
    assert mob["forceBattleMaxDistance"] == float(g["sight_distance"]) and 0 < g["sight_distance"] < 8
    assert mob["textureResource"] == g["skin"]
    assert re.fullmatch(r"rctmod:textures/trainers/single/[a-z0-9_]+\.png", mob["textureResource"])


# Without it a Channeler says her losing line when the player wins, or another guardian's lines.
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_guardian_dialog_keys_carry_the_records_lines(files, g):
    d = files["data/rctmod/dialogs/trainers/single/%s.json" % g["id"]]
    text = g["dialogue_text"]
    want = {"on_battle_start": text["pre"], "on_battle_lost": text["player_win"], "trainer_lost": text["player_win"],
            "on_battle_won": text["player_loss"], "trainer_won": text["player_loss"],
            "on_cooldown": "Leave me be a moment."}
    assert d == {k: [{"text": v}] for k, v in want.items()}


def _key(field):
    return "cobblers__" + field.replace(".", "__")


# Without it a win opens another room, writes an undeclared quest.<id>.defeated field, or is never saved (the room
# shuts again on the next restart).
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_guardian_won_function_sets_exactly_the_records_fields_and_saves(files, g):
    lines = files["data/cobblers/function/trainers/won/%s.mcfunction" % g["id"]]
    mol = [l for l in lines if l.startswith("runmolang ")]
    assert len(mol) == 1
    body = re.fullmatch(r'runmolang "(.*)" @s', mol[0]).group(1)
    assigned = set(re.findall(r"t\.d\.([A-Za-z0-9_]+)\s*=", body))
    assert assigned == {_key(f) for f in g["sets"]}
    assert _key("quest.%s.defeated" % g["id"]) not in body
    assert body.startswith("t.d = q.player.data();") and body.endswith("q.player.save_data();")
    assert [l for l in lines if l.startswith("tag ")] == ["tag @s add cobblers_beat_%s" % g["id"]]
    assert not [l for l in lines if l.split(" ", 1)[0] in ("scoreboard", "data", "advancement", "function")]
    assert any(l.startswith("tellraw @s ") and json.dumps(g["after_win"]) in l for l in lines)


# Without it the guard field is set by another trainer's win, or only on a count the first win does not reach.
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_guardian_advancement_is_defeat_count_for_this_id_at_count_1(files, g):
    adv = files["data/cobblers/advancement/trainer/%s.json" % g["id"]]
    assert adv["criteria"] == {"won": {"trigger": "rctmod:defeat_count",
                                       "conditions": {"trainer_ids": [g["id"]], "count": 1}}}
    assert adv["rewards"]["function"] == "cobblers:trainers/won/%s" % g["id"]


# ------------------------------------------------------------------------------------------------ seats in the house

AIR = {"minecraft:air", "minecraft:cave_air"}
THIN = ("_carpet", "minecraft:leaf_litter", "minecraft:candle", "_candle", "_trapdoor")
DEFAULT_SLOTS = [[0.0, 0.0], [0.9, 0.0], [0.0, 0.9], [-0.9, 0.0]]     # tools/scenes_pack.py SLOTS


def _thin(b):
    return b is not None and (b in AIR or b.endswith(THIN))


def _solid(b):
    return b is not None and b not in AIR and not _thin(b)


@pytest.fixture(scope="module")
def house():
    recs = [p for p in PLACEMENTS["placements"] if p["id"] == "route1_mansion_house"]
    assert len(recs) == 1, "data/placements.json must hold the house exactly once"
    cmds = recs[0]["commands"]
    assert len(cmds) > 1000, "the recorded house is (nearly) empty: nothing to check against"
    cols = {(x, z) for x in range(RM.X0 - 2, RM.X1 + 3) for z in range(RM.Z0 - 2, RM.Z1 + 3)}
    rep = BA.replay(cmds, cols)
    return lambda x, y, z: rep.get((x, z), {}).get(y)


def _marker_cells():
    out = []
    for name, m in SCENE["markers"].items():
        at = m["at"]
        for ox, oz in m.get("slots") or SCENE.get("slots") or DEFAULT_SLOTS:
            out.append((name, (math.floor(at[0] + 0.5 + ox), at[1], math.floor(at[2] + 0.5 + oz))))
    return out


# Without it a Channeler is summoned into a table, a wall or a stair, or over the stairwell, and R17 teleports her
# where she suffocates or falls.
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_each_guardian_seat_is_standable_in_the_replayed_house(house, g):
    x, y, z = g["seat"]
    feet, head, below = house(x, y, z), house(x, y + 1, z), house(x, y - 1, z)
    assert _thin(feet), "feet at %s: %s" % (g["seat"], feet)
    assert head in AIR, "head at %s: %s" % ((x, y + 1, z), head)
    assert _solid(below), "below %s: %s" % (g["seat"], below)
    lo, hi = SCENE["area"]["from"], SCENE["area"]["to"]
    assert all(lo[i] <= g["seat"][i] <= hi[i] for i in range(3)), "%s seat outside the scene area" % g["id"]


# Without it a Channeler stands on a prop's click box (the click opens her battle, not the puzzle) or on the slot an
# actor spawns into (Pip or a second player's Pip is shoved off his checkpoint).
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_each_guardian_seat_clears_every_prop_and_marker_slot(g):
    x, y, z = g["seat"]
    for p in SCENE["props"]:
        for cell in ([math.floor(v) for v in p["at"]], p["on"]):
            same_storey = y - 1 <= cell[1] <= y + 2
            assert not (same_storey and max(abs(cell[0] - x), abs(cell[2] - z)) <= 1), \
                "%s at %s within a block of prop %s %s" % (g["id"], g["seat"], p["id"], cell)
    for name, cell in _marker_cells():
        assert not (cell[1] == y and max(abs(cell[0] - x), abs(cell[2] - z)) <= 1), \
            "%s at %s within a block of marker %s slot %s" % (g["id"], g["seat"], name, cell)


# Without it the seat checks above could pass on a scene with nothing in it.
def test_the_scene_has_props_and_markers_to_clear():
    assert len(SCENE["props"]) >= 10 and len(_marker_cells()) >= 20


# ------------------------------------------------------------------------------------------------ the escort walk

REFS = list(QUEST["progression_field_refs"])
PUZZLE_FIELDS = {f for f in REFS if FIELDS[f]["type"] == "boolean"}
PIP = "dlg_route1_gastly_pip"
ZONE_TRANSITIONS = [t for z in SCENE.get("zones") or [] for t in z["transitions"]]


def _reads(c, out):
    if c.get("field"):
        out.add(c["field"])
    for x in c.get("conditions") or []:
        _reads(x, out)
    if c.get("condition"):
        _reads(c["condition"], out)
    return out


def _read_fields():
    """Fields whose value can change what happens next: read by a condition, or a cursor something pages from (a
    $cursor entry rule, or a response the compiler sends to the cursor's page). The rest (an actor's cursor nobody
    reads) are held at their initial value in the walk's state key: same behaviour, far fewer states."""
    out = set()
    for t in T.values():
        for c in t["conditions"]:
            _reads(c, out)
    for cid, c in CONVS.items():
        for r in c["entry_rules"]:
            _reads(r["when"], out)
            if r["node"] == "$cursor":
                out.add(c["cursor"]["progression_field"])
        for n in c["nodes"]:
            for r in n.get("responses") or []:
                if r.get("visible_when"):
                    _reads(r["visible_when"], out)
                if any(a["kind"] == "quest_transition" for a in r.get("actions") or []):
                    out.add(c["cursor"]["progression_field"])
    return out


READ = _read_fields()


def _cond(c, st):
    k = c["kind"]
    if k == "always":
        return True
    if k == "all":
        return all(_cond(x, st) for x in c["conditions"])
    if k == "any":
        return any(_cond(x, st) for x in c["conditions"])
    if k == "not":
        return not _cond(c["condition"], st)
    if k == "progression_equals":
        return st[c["field"]] == c["value"]
    if k == "progression_in":
        return st[c["field"]] in c["values"]
    raise AssertionError("the walk does not model condition kind %s: extend it rather than guess" % k)


def _run(tid, st, grants):
    """Apply transition tid if its conditions hold; returns whether it ran."""
    t = T[tid]
    if not all(_cond(c, st) for c in t["conditions"]):
        return False
    for e in t["effects"]:
        if e["kind"] == "set_progression":
            st[e["field"]] = e["value"]
        elif e["kind"] == "grant_reward_once":
            if not st[e["claim_field"]]:
                grants[e["reward"]] = grants.get(e["reward"], 0) + 1
                st[e["claim_field"]] = True
        elif e["kind"] in ("sync_scene", "scene_function"):
            pass                                  # the scene runtime: writes no quest state (quests.json scene_effect_rule)
        else:
            raise AssertionError("the walk does not model effect kind %s (transition %s)" % (e["kind"], tid))
    return True


def _node(cid, nid):
    return next((n for n in CONVS[cid]["nodes"] if n["id"] == nid), None)


def _cursor(cid):
    return CONVS[cid]["cursor"]["progression_field"]


def _room_steps(g):
    """The transitions that make progress in guardian g's room: its exit, and every transition gated on its checkpoint
    that sets a puzzle field away from its initial value (a lamp or a ward lit; resets are not progress)."""
    out = {g["gates"]}
    for tid, t in T.items():
        if {"kind": "progression_equals", "field": CP_FIELD, "value": g["checkpoint"]} in t["conditions"]:
            if any(e["kind"] == "set_progression" and e["field"] in PUZZLE_FIELDS and e["value"] != FIELDS[e["field"]]["initial"]
                   for e in t["effects"]):
                out.add(tid)
    return out


def walk(mode, beatable):
    """Every state a player reaches. mode: 'compiled' or 'authored' (how a response that runs a transition picks the
    next page). beatable: guard fields the player may set (by winning) at any moment.

    Returns (states, offered): states are (fields, page, grants); offered lists (transition, fields) for every
    transition a shown page or a firing entry rule put in front of the player."""
    init = {f: FIELDS[f]["initial"] for f in REFS}

    def freeze(st, page, grants):
        return (tuple(st[f] if f in READ else init[f] for f in REFS), page, tuple(sorted(grants.items())))

    def thaw(key):
        vals, page, grants = key
        return dict(zip(REFS, vals)), page, dict(grants)

    offered = []
    start = freeze(init, None, {})
    seen, todo = {start}, deque([start])

    def push(st, page, grants):
        k = freeze(st, page, grants)
        if k not in seen:
            seen.add(k)
            todo.append(k)

    def show(cid, nid, st):
        """The page as the player sees it: what it offers (visible responses) is recorded."""
        n = _node(cid, nid)
        if n is None:
            return None
        for r in n.get("responses") or []:
            if not r.get("visible_when") or _cond(r["visible_when"], st):
                for a in r.get("actions") or []:
                    if a["kind"] == "quest_transition":
                        offered.append((a["transition"], dict(st)))
        return (cid, nid)

    while todo:
        key = todo.popleft()
        st0, page, g0 = thaw(key)
        if page is None:
            for f in beatable:                                       # win a guardian's battle
                if not st0[f]:
                    st, g = dict(st0), dict(g0)
                    st[f] = True
                    push(st, None, g)
            for tid in ZONE_TRANSITIONS:                             # walk into a zone
                st, g = dict(st0), dict(g0)
                _run(tid, st, g)
                push(st, None, g)
            for cid, c in CONVS.items():                             # click an actor or a prop
                st, g = dict(st0), dict(g0)
                for rule in sorted(c["entry_rules"], key=lambda r: r["priority"]):
                    if _cond(rule["when"], st):
                        for a in rule.get("actions") or []:
                            if a["kind"] == "quest_transition":
                                offered.append((a["transition"], dict(st)))
                                _run(a["transition"], st, g)
                        nid = rule["node"]
                        if nid == "$cursor":
                            nid = st[_cursor(cid)]
                            if _node(cid, nid) is None:
                                nid = c["cursor"]["initial_node"]
                        push(st, show(cid, nid, st), g)
                        break
            continue
        cid, nid = page
        n = _node(cid, nid)
        push(st0, None, g0)                                          # walk away mid-conversation
        if n.get("responses"):
            for r in n["responses"]:
                if r.get("visible_when") and not _cond(r["visible_when"], st0):
                    continue
                st, g = dict(st0), dict(g0)
                tids = [a["transition"] for a in r.get("actions") or [] if a["kind"] == "quest_transition"]
                for tid in tids:
                    _run(tid, st, g)
                for a in r.get("actions") or []:
                    if a["kind"] == "set_cursor":
                        st[_cursor(cid)] = a["node"]
                if any(a["kind"] == "close_dialogue" for a in r.get("actions") or []):
                    push(st, None, g)
                elif tids and mode == "compiled":
                    # tools/compile_dialogue.py: q.dialogue.set_page(<cursor field>) after the transitions
                    push(st, show(cid, st[_cursor(cid)], st), g)
                else:
                    st[_cursor(cid)] = r["next"]
                    push(st, show(cid, r["next"], st), g)
        else:
            st, g = dict(st0), dict(g0)
            for a in n.get("actions_after_acknowledge") or []:
                if a["kind"] == "quest_transition":
                    _run(a["transition"], st, g)
            st[_cursor(cid)] = n["next"]
            push(st, None if n["next"] == nid else show(cid, n["next"], st), g)
    return [thaw(k) for k in seen], offered


MODES = ["compiled", "authored"]
_WALKS = {}


def _walk(mode, unbeaten=None):
    k = (mode, unbeaten)
    if k not in _WALKS:
        _WALKS[k] = walk(mode, [f for gid, f in GUARD_FIELD.items() if gid != unbeaten])
    return _WALKS[k]


def _rank(st):
    return CHECKPOINTS.index(st[CP_FIELD])


# Without it some click, zone or response sequence moves a player past a Channeler they have not beaten: the gauntlet
# is optional in practice. Also fails if the walk never reaches the guarded room (the check would pass on nothing).
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_an_unbeaten_guardian_holds_the_escort_in_her_room(mode, g):
    states, _offered = _walk(mode, g["id"])
    room = CHECKPOINTS.index(g["checkpoint"])
    reached = max(_rank(st) for st, _p, _g in states)
    assert reached == room, "with %s unbeaten the checkpoint reaches %s" % (g["id"], CHECKPOINTS[reached])
    assert not any(st["quest.%s.completed" % QID] for st, _p, _g in states)
    assert not any(gr.get("reward_spell_tag") for _s, _p, gr in states)
    # the player is told why: Pip's guarded line for this room is shown
    guarded = [r["node"] for r in CONVS[PIP]["entry_rules"]
               if {"kind": "progression_equals", "field": GUARD_FIELD[g["id"]], "value": False} in r["when"].get("conditions", [])]
    assert len(guarded) == 1, "Pip has %d guarded entry rules for %s" % (len(guarded), g["id"])
    assert any(p == (PIP, guarded[0]) and st[CP_FIELD] == g["checkpoint"] for st, p, _g in states)


# Without it an unbeaten Channeler's room still shows its puzzle (Pip offers the way across the foyer, a candle lights,
# a ward mark takes), and the player learns or half-solves it before the fight the design puts first. This is where
# a response's page, not its entry rule, can reopen the room: `next` continues inside the conversation.
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("g", GUARDS, ids=GIDS)
def test_an_unbeaten_guardians_room_offers_no_way_forward(mode, g):
    _states, offered = _walk(mode, g["id"])
    steps = _room_steps(g)
    leaks = sorted({tid for tid, st in offered
                    if tid in steps and st[CP_FIELD] == g["checkpoint"] and not st[GUARD_FIELD[g["id"]]]})
    assert not leaks, "with %s unbeaten, the %s room still offers %s" % (g["id"], g["checkpoint"], leaks)


# Without it the escort cannot be finished even after every fight (a dead end), finishes without all five wins, or
# the spell tag is granted twice (a repeat click, a reconnect, a replayed line).
@pytest.mark.parametrize("mode", MODES)
def test_with_every_guardian_beaten_the_escort_reaches_family_and_grants_the_spell_tag_once(mode):
    states, _offered = _walk(mode)
    done = [st for st, _p, _g in states if st[CP_FIELD] == "family" and st["quest.%s.completed" % QID]]
    assert done, "the escort never completes with every guardian beaten"
    for st, _p, _g in states:
        for g in GUARDS:
            if _rank(st) > CHECKPOINTS.index(g["checkpoint"]):
                assert st[GUARD_FIELD[g["id"]]], "past %s without beating %s" % (g["checkpoint"], g["id"])
    tags = [gr.get("reward_spell_tag", 0) for _s, _p, gr in states]
    assert max(tags) == 1
    assert max(gr.get("reward_mansion_cache", 0) for _s, _p, gr in states) == 1


# ------------------------------------------------------------------------------------------------ R17

# Without it R17 places only the route trainers (the guardians are generated but never stand in the house), or seats
# a guardian somewhere other than its record.
def test_r17_placements_are_the_route_seats_then_the_guardians():
    want = [(s["id"], tuple(s["seat"]), s["yaw"]) for s in ROUTE_SEATS] + \
           [(g["id"], tuple(g["seat"]), g["yaw"]) for g in GUARDS]
    assert len(want) == 18
    assert RT.placements() == want


class _FakeRcon:
    """Stands in for RCON: records every command, answers as a server with the trainer present or absent."""

    def __init__(self, present):
        self.cmds, self.present = [], present

    def __call__(self, cmd, timeout=None):
        self.cmds.append(cmd)
        if cmd.startswith("execute if loaded"):
            return "Test passed"
        if cmd.startswith("execute if entity"):
            return "Test passed" if self.present else "Test failed"
        if cmd.startswith("data get storage cobblers:reapply trainers"):
            return "Storage cobblers:reapply has the following contents: 1"
        return ""


def _drive_r17_trainer(monkeypatch, tmp_path, present):
    g = GUARDS[0]
    x, y, z = g["seat"]
    fake = _FakeRcon(present)
    monkeypatch.setattr(reapply, "Rcon", lambda server_dir: fake)
    monkeypatch.setattr(reapply, "OUT", tmp_path)
    monkeypatch.setattr(reapply, "steps", lambda *a, **k: [("R17", "trainer", [("trainer", (g["id"], (x, y, z), g["yaw"]))])])
    monkeypatch.setattr(reapply.time, "sleep", lambda s: None)
    reapply.run(SimpleNamespace(server_dir=str(tmp_path / "no-server"), with_spawns=False, only=None, from_step=None,
                                no_reload=True))
    return g, fake.cmds


# Without it R17 finds "a trainer" near the seat rather than this one (a neighbouring guardian satisfies the check and
# this one is never summoned), or teleports and counts some other trainer. Driven with a fake RCON, never a server.
@pytest.mark.parametrize("present", [False, True], ids=["absent", "present"])
def test_r17_selects_the_trainer_by_its_trainer_id(monkeypatch, tmp_path, present):
    g, cmds = _drive_r17_trainer(monkeypatch, tmp_path, present)
    sel = 'nbt={TrainerId:"%s"}' % g["id"]
    targeting = [c for c in cmds if "rctmod:trainer" in c]
    assert targeting, "R17 issued no trainer command"
    assert all(sel in c for c in targeting), [c for c in targeting if sel not in c]
    summons = [c for c in cmds if "summon_persistent" in c]
    assert summons == ([] if present else ["rctmod trainer summon_persistent %s %d %d %d" % (g["id"], *g["seat"])])


# Without it a placed guardian strolls off her seat (on staging one climbed the grand stair in two minutes), whether
# she was just summoned or was already standing there from an earlier run, or is left facing the wrong way.
@pytest.mark.parametrize("present", [False, True], ids=["absent", "present"])
def test_r17_seats_the_trainer_and_pins_it_at_speed_0(monkeypatch, tmp_path, present):
    g, cmds = _drive_r17_trainer(monkeypatch, tmp_path, present)
    x, y, z = g["seat"]
    tps = [c for c in cmds if c.startswith("tp ")]
    pins = [c for c in cmds if re.fullmatch(
        r'execute as @e\[type=rctmod:trainer,[^\]]*nbt=\{TrainerId:"%s"\}\] run attribute @s '
        r'minecraft:generic\.movement_speed base set 0' % re.escape(g["id"]), c)]
    assert len(tps) == 1 and len(pins) == 1, cmds
    assert tps[0].endswith(" %d.5 %d %d.5 %d 0" % (x, y, z, g["yaw"]))


# Without it a Channeler can be hurt (and killed) in her own battle or by a player's sword, and her room's gate has no
# one left to open it; or the merge lands on some other trainer, or on every trainer the selector finds.
@pytest.mark.parametrize("present", [False, True], ids=["absent", "present"])
def test_r17_makes_exactly_its_own_trainer_invulnerable(monkeypatch, tmp_path, present):
    g, cmds = _drive_r17_trainer(monkeypatch, tmp_path, present)
    merges = [c for c in cmds if c.startswith("data merge entity ")]
    assert len(merges) == 1, cmds
    m = re.fullmatch(r"data merge entity @e\[(.*)\] \{Invulnerable:1b\}", merges[0])
    assert m, merges[0]
    args = m.group(1)
    assert "type=rctmod:trainer" in args and 'nbt={TrainerId:"%s"}' % g["id"] in args
    assert args.endswith(",limit=1"), args
