"""The badge carry (commit dddcdf6): a player who beats the gyms in order always reaches the finale.

Written by the test author, not by the session that built the carry. Expectations come from the design, read here
independently of tools/progression_pack.py:

  story order   derived by walking data/quests.json main_worldshift_reveal's STRICT transitions (stage equals X ->
                stage Y) from the stage field's initial value; the generator uses the enum's allowed_values order
                instead, so test_the_stage_enum_is_declared_in_story_order holds the two together
  the badges    data/progression.json upstream_neutralised.first_win_rewards: the flag whose leader's first win gives
                a cobbleversebadges:kanto_<name>_badge item. Badge and leader names come from those ids
  carry target  the completion_stage of the beat whose world_change_flag is that badge (data/quests.json beats[])
  starter tag   tools/compile_dialogue.py STARTER_TAG, the tag the dialogue's starter_chosen condition reads
  stage store   tools/compile_dialogue.py key(): the q.player.data() key every conversation reads the stage from

The compiled carry (flag/<id>/carry.mcfunction, a `runmolang`) is RUN by tests/nbt_sim.py's Molang with Cobblemon's
q.player.data()/save_data()/has_tag modelled here; the conversations are run from data/dialogue.json by a small
interpreter of entry rules, line walks and quest transitions written here.

Not covered, and it needs a running server: that runmolang binds q.player and that q.player.data() is the store the
compiled dialogue reads (the same construct tools/hq_tower.py's won functions use, unobserved for the carry); that an
advancement reward runs as the winner; that the compiled dialogue (tools/compile_dialogue.py) behaves as the data
interpreter below models it (its own tests cover the compiler). The Pallet actors (Oak, Mina, Maren) are not walked:
their conversations carry responses, and the design declares them outside the carry (carry_forward.not_covered).

Generator mutations run 2026-10-04 (tools/progression_pack.py edited, data untouched, then restored):
  _carry `earlier` = every value (a carry that lowers)    8 failed: test_no_carry_lowers_a_stage_and_none_stops_short
  carry_molang without the requires_tag clause            9 failed: test_every_carry_needs_the_starter_tag x8, the
                                                          finale-stays-shut test
  granted no longer calls flag/<id>/carry                 3 failed: the reward test, the badge-reward finale walk,
                                                          the finale-stays-shut test
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

import compile_dialogue as CD  # noqa: E402
import nbt_sim as NS  # noqa: E402
import progression_pack as PP  # noqa: E402

DATA = ROOT / "data"


def _json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


PROG = _json("progression.json")
QUEST = next(q for q in _json("quests.json")["quests"] if q["id"] == "main_worldshift_reveal")
CONVS = {c["id"]: c for c in _json("dialogue.json")["conversations"]}
FIELDS = {f["id"]: f for f in PROG["quest_fields"]}
TRANS = {t["id"]: t for t in QUEST["transitions"]}
STAGE = "quest.main_worldshift_reveal.stage"
KEY = CD.key(STAGE)
STARTER = CD.STARTER_TAG
NIA = "dlg_main_finale_nia"
PACK = PP.files(PP.plan(PP.load(DATA / "progression.json"), placements=_json("placements.json")))


def _story_order():
    """not_started -> ... -> league_recognized, following each stage's one strict successor."""
    nxt = {}
    for t in QUEST["transitions"]:
        eq = [c["value"] for c in t["conditions"] if c["kind"] == "progression_equals" and c["field"] == STAGE]
        to = [e["value"] for e in t["effects"] if e["kind"] == "set_progression" and e["field"] == STAGE]
        if len(eq) == 1 and len(to) == 1:
            nxt.setdefault(eq[0], set()).add(to[0])
    order = [FIELDS[STAGE]["initial"]]
    while order[-1] in nxt:
        succ = nxt[order[-1]]
        assert len(succ) == 1, "stage %s has two strict successors %s" % (order[-1], succ)
        assert not succ & set(order), "the story loops at %s" % succ
        order.append(succ.pop())
    return order


ORDER = _story_order()
RANK = {s: i for i, s in enumerate(ORDER)}


def _badges():
    """{flag: (badge name, leader name)} from the leaders' first-win badge items; the leader's name is the last word of
    the leader's display_name in data/gym_trainers.json ("Lt. Surge" is "Surge" in a line)."""
    names = {t["upstream_trainer_id"]: (t["flag"], t["display_name"]) for t in _json("gym_trainers.json")["trainers"]}
    out = {}
    for tid, r in PROG["upstream_neutralised"]["first_win_rewards"]["trainers"].items():
        for item in r["items"]:
            m = re.fullmatch(r"cobbleversebadges:kanto_([a-z]+)_badge", item)
            if m:
                assert names[tid][0] == r["flag"], (tid, names[tid], r["flag"])
                out[r["flag"]] = ("%s Badge" % m.group(1).title(), names[tid][1].split()[-1])
    return out


BADGES = _badges()
BADGE_ORDER = sorted(BADGES, key=lambda f: next(b["order"] for b in QUEST["beats"] if b.get("world_change_flag") == f))


def _target(flag):
    return next(b["completion_stage"] for b in QUEST["beats"] if b.get("world_change_flag") == flag)


# ------------------------------------------------------------------------------------------------ the runtime

class PlayerMolang(NS.Molang):
    """Cobblemon's player Molang: q.player.data() is the player's saved compound (a key never written reads 0),
    q.player.has_tag reads the player's tags, q.player.save_data() is recorded."""

    def exec_block(self, stmts):
        for s in stmts:
            parts = s[1].split(".") if s[0] == "assign" else []
            if len(parts) == 3 and parts[0] in ("t", "temp") and isinstance(self.temp.get(parts[1]), dict):
                self.temp[parts[1]][parts[2]] = self.ev(s[2])
            else:
                super().exec_block([s])

    def lookup(self, name):
        try:
            return super().lookup(name)
        except NS.MolangError:
            parts = name.split(".")
            if len(parts) == 3 and parts[0] in ("t", "temp") and isinstance(self.temp.get(parts[1]), dict):
                return 0.0
            raise

    def ev(self, e):
        if e[0] == "call" and e[1] == "q.player.data":
            return self.query["_data"]
        if e[0] == "call" and e[1] == "q.player.save_data":
            self.query["_saved"].append(True)
            return 0.0
        if e[0] == "call" and e[1] == "q.player.has_tag":
            (tag,) = [self.ev(a) for a in e[2]]
            return 1.0 if tag in self.query["_tags"] else 0.0
        return super().ev(e)


def _carry_molang(flag):
    text = PACK["data/cobblers/function/flag/%s/carry.mcfunction" % flag]
    cmds = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    assert len(cmds) == 1, cmds
    m = re.fullmatch(r'runmolang "(.*)" @s', cmds[0])
    assert m, cmds[0]
    return m.group(1)


def run_carry(flag, data, tags):
    """Runs the compiled carry for `flag` as a player whose saved data is `data` (mutated) and tags `tags`."""
    saved = []
    PlayerMolang(_carry_molang(flag)).run(query={"_data": data, "_tags": set(tags), "_saved": saved})
    return saved


class Player:
    """One player's per-player state, in the same store the carry writes (q.player.data(), keys CD.key)."""

    def __init__(self, badges=(), starter=True):
        self.data, self.flags = {}, set(badges)
        self.tags = {STARTER} if starter else set()

    def get(self, field):
        v = self.data.get(CD.key(field), 0.0)
        return FIELDS[field]["initial"] if v == 0.0 else v

    def win(self, flag, carry=True):
        """The badge's advancement is granted; its reward runs the carry (unless the player won before it shipped)."""
        self.flags.add(flag)
        if carry:
            for line in PACK["data/cobblers/function/flag/%s/granted.mcfunction" % flag].splitlines():
                m = re.fullmatch(r"function cobblers:flag/([a-z0-9_]+)/carry", line)
                if m:
                    run_carry(m.group(1), self.data, self.tags)

    def holds(self, c):
        k = c["kind"]
        if k == "all":
            return all(self.holds(x) for x in c["conditions"])
        if k == "always":
            return True
        if k == "progression_equals":
            return self.get(c["field"]) == c["value"]
        if k == "progression_in":
            return self.get(c["field"]) in c["values"]
        if k == "flag":
            return c["flag"] in self.flags
        if k == "starter_chosen":
            return STARTER in self.tags
        raise AssertionError("condition kind %r is not modelled" % k)

    def transition(self, tid):
        t = TRANS[tid]
        if not all(self.holds(c) for c in t["conditions"]):
            return False
        for e in t["effects"]:
            if e["kind"] == "set_progression":
                self.data[CD.key(e["field"])] = e["value"]
            elif e["kind"] != "function":
                raise AssertionError("effect kind %r is not modelled" % e["kind"])
        return True

    def talk(self, cid):
        """Open conversation `cid` and read every line to its first repeat. Returns the node it opened on."""
        conv = CONVS[cid]
        rule = next(r for r in sorted(conv["entry_rules"], key=lambda r: r["priority"]) if self.holds(r["when"]))
        for a in rule.get("actions") or []:
            assert a["kind"] == "quest_transition", a
            self.transition(a["transition"])
        cursor = conv["cursor"]["progression_field"]
        node = rule["node"]
        if node == "$cursor":
            node = self.get(cursor)
        opened, seen = node, set()
        nodes = {n["id"]: n for n in conv["nodes"]}
        while node not in seen:
            seen.add(node)
            n = nodes[node]
            assert n["kind"] == "line", "%s: node kind %r is not modelled" % (cid, n["kind"])
            for a in n.get("actions_after_acknowledge") or []:
                assert a["kind"] == "quest_transition", a
                self.transition(a["transition"])
            self.data[CD.key(cursor)] = n["next"]
            node = n["next"]
        return opened


def _badge_gated():
    """[(conversation id, badge flag)] for every reveal conversation with an entry rule on a badge."""
    out = []
    for cid in QUEST["dialogue_ids"]:
        for r in CONVS[cid]["entry_rules"]:
            w = r["when"]
            for c in (w.get("conditions") or [w]):
                if c.get("kind") == "flag" and c["flag"] in BADGES and (cid, c["flag"]) not in out:
                    out.append((cid, c["flag"]))
    return out


GATED = _badge_gated()


# ------------------------------------------------------------------------------------------------ the derivations

# Without it the tests below would compare against an empty or partial story, or eight badges would be seven.
def test_the_derivations_are_whole():
    assert ORDER[0] == "not_started" and ORDER[-1] == "league_recognized"
    assert len(BADGES) == 8
    assert [BADGES[f][0] for f in BADGE_ORDER][:2] == ["Boulder Badge", "Cascade Badge"]
    assert len(GATED) >= 9  # Brock to the Rift surveyor, and Nia


# Without it the generator's "earlier" (the enum's order) could disagree with the story, and a carry would lower a
# stage the story had already passed.
def test_the_stage_enum_is_declared_in_story_order():
    assert FIELDS[STAGE]["allowed_values"] == ORDER


# ------------------------------------------------------------------------------------------------ the compiled carry

# Without it a badge would carry no one, or a gym's badge would open another gym's actor.
def test_every_badge_and_only_a_badge_has_a_carry():
    carries = {m.group(1) for k in PACK for m in [re.fullmatch(r"data/cobblers/function/flag/([a-z0-9_]+)/carry\.mcfunction", k)] if m}
    assert carries == set(BADGES)


# Without it a badge would carry a fresh player to the wrong stage: short of the next actor, or past one.
@pytest.mark.parametrize("flag", sorted(BADGES))
def test_each_badge_carries_to_the_stage_its_gyms_beat_completes(flag):
    data = {}
    run_carry(flag, data, {STARTER})
    assert data == {KEY: _target(flag)}


# Without it a player further along than the badge (a late gym, an early talker) would be thrown back down the
# story, or a player behind it left short.
@pytest.mark.parametrize("flag", sorted(BADGES))
def test_no_carry_lowers_a_stage_and_none_stops_short(flag):
    to = _target(flag)
    for start in [None] + ORDER:
        data = {} if start is None else {KEY: start}
        run_carry(flag, data, {STARTER})
        was = RANK[start or ORDER[0]]
        got = RANK[data.get(KEY, ORDER[0])]
        assert got >= was, "%s lowered %s to %s" % (flag, start, data.get(KEY))
        assert data.get(KEY, start) == (to if was < RANK[to] else start), (flag, start, data)


# Without it a player Cobblemon has not given a starter would be moved through the story (oak_starter_audit P1).
@pytest.mark.parametrize("flag", sorted(BADGES))
def test_every_carry_needs_the_starter_tag(flag):
    for tags in (set(), {"cobblers_something_else"}):
        for start in [None] + ORDER:
            data = {} if start is None else {KEY: start}
            before = copy.deepcopy(data)
            saved = run_carry(flag, data, tags)
            assert data == before and not saved, (flag, tags, start)


# Without it the carry is generated but never runs, or runs on every reward re-run instead of once from the badge's.
def test_the_badges_reward_runs_its_carry_once_and_no_other_reward_does():
    for flag in [f["id"] for f in PROG["flags"]]:
        adv = json.loads(PACK["data/cobblers/advancement/flag/%s.json" % flag])
        assert adv["rewards"]["function"] == "cobblers:flag/%s/granted" % flag
        granted = PACK["data/cobblers/function/flag/%s/granted.mcfunction" % flag].splitlines()
        calls = [l for l in granted if re.fullmatch(r"function cobblers:flag/[a-z0-9_]+/carry", l)]
        assert calls == (["function cobblers:flag/%s/carry" % flag] if flag in BADGES else []), flag


# ------------------------------------------------------------------------------------------------ the dialogue's carries

# Without it an actor's badge rule could lower a stage, skip the starter gate, or open on someone else's badge.
def test_every_dialogue_carry_needs_the_starter_and_its_badge_and_reads_only_earlier_stages():
    carries = [t for t in QUEST["transitions"] if t["id"].startswith("carry_by_")]
    assert carries
    for t in carries:
        m = re.fullmatch(r"carry_by_([a-z0-9_]+)_to_([a-z_]+)", t["id"])
        flag, to = m.group(1), m.group(2)
        assert flag in BADGES, t["id"]
        assert t["effects"] == [{"kind": "set_progression", "field": STAGE, "value": to}], t["id"]
        kinds = {c["kind"]: c for c in t["conditions"]}
        assert set(kinds) == {"starter_chosen", "flag", "progression_in"}, t["id"]
        assert kinds["flag"]["flag"] == flag
        assert kinds["progression_in"]["field"] == STAGE
        assert kinds["progression_in"]["values"] == ORDER[:RANK[to]], t["id"]
        # never past the stage the badge's own beat reaches, plus the one the finale's first actor reads
        assert RANK[to] <= RANK[_target(flag)] + 1, t["id"]


# Without it a rule could run a badge carry for a player who has no starter or does not hold that badge.
def test_every_entry_rule_that_runs_a_carry_checks_the_starter_and_the_badge_first():
    n = 0
    for cid in QUEST["dialogue_ids"]:
        for r in CONVS[cid]["entry_rules"]:
            runs = [a["transition"] for a in r.get("actions") or [] if a["transition"].startswith("carry_by_")]
            for tid in runs:
                n += 1
                conds = r["when"].get("conditions") or []
                assert {"kind": "starter_chosen"} in conds, (cid, tid)
                assert {"kind": "flag", "flag": tid.split("_to_")[0][len("carry_by_"):]} in conds, (cid, tid)
    assert n == len([t for t in TRANS if t.startswith("carry_by_")])


# Without it a locked actor would stand there saying nothing a player can act on, or name a badge that does not exist.
@pytest.mark.parametrize("cid,flag", GATED, ids=["%s-%s" % g for g in GATED])
def test_each_locked_line_names_the_badge_and_its_leader(cid, flag):
    conv = CONVS[cid]
    nodes = {n["id"]: n for n in conv["nodes"]}
    locked = nodes[conv["cursor"]["initial_node"]]
    badge, leader = BADGES[flag]
    assert badge in locked["text"], (cid, locked["text"])
    assert leader in locked["text"] or locked["speaker"] == leader.lower(), (cid, locked["text"])
    real = {b for b, _l in BADGES.values()}
    for named in re.findall(r"([A-Z][a-z]+ Badge)", locked["text"]):
        assert named in real, (cid, named)


# ------------------------------------------------------------------------------------------------ playing it

# Without it a player who skips one actor would find every later actor locked (CRITICAL_PATH_WALK_2 blocker 2).
@pytest.mark.parametrize("carry", [True, False], ids=["badge-reward", "won-before-the-carry-shipped"])
@pytest.mark.parametrize("cid,flag", GATED, ids=["%s-%s" % g for g in GATED])
def test_each_actor_opens_on_its_badge_with_no_one_else_heard(cid, flag, carry):
    p = Player()
    for f in BADGE_ORDER[:BADGE_ORDER.index(flag) + 1]:
        p.win(f, carry=carry)
    before = RANK[p.get(STAGE)]
    opened = p.talk(cid)
    assert opened != CONVS[cid]["cursor"]["initial_node"], (cid, p.get(STAGE))
    assert RANK[p.get(STAGE)] >= max(before, RANK[_target(flag)] if cid != NIA else 0), (cid, p.get(STAGE))


# Without it the finale is unreachable to a player who beat all eight gyms and talked to no one on the way.
@pytest.mark.parametrize("carry", [True, False], ids=["badge-reward", "won-before-the-carry-shipped"])
def test_eight_badges_and_no_conversations_reach_the_finale(carry):
    p = Player()
    for f in BADGE_ORDER:
        p.win(f, carry=carry)
    if carry:
        assert p.get(STAGE) == _target(BADGE_ORDER[-1])
    assert p.talk(NIA) == "nia_001"
    assert p.get(STAGE) == "deep_handoff_received"
    # the HQ tower's guard and Elara's door, the finale's way in, admit this player
    for gate in ("relic_hq_admit", "elara_door_admit"):
        assert all(p.holds(c) for c in TRANS[gate]["conditions"]), gate


# Without it the starter gate would be bypassed at the finale's door, or seven badges would open it.
def test_the_finale_stays_shut_without_a_starter_or_the_eighth_badge():
    p = Player(starter=False)
    for f in BADGE_ORDER:
        p.win(f)
    assert p.talk(NIA) == "nia_before" and p.get(STAGE) == ORDER[0]
    p = Player()
    for f in BADGE_ORDER[:-1]:
        p.win(f)
    assert p.talk(NIA) == "nia_before" and p.get(STAGE) == _target(BADGE_ORDER[-2])
