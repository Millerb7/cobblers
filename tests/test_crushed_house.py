"""The Pallet crushed house (Hank and Lena): the world-scoped quest field, the two conversations, the seats.

Unit PALLET-HANK-LENA, 2026-10-13. WRITTEN BY THE SAME AGENT THAT WROTE THE COMPILER CHANGE: an independent audit is
still owed (CLAUDE.md "Content implementation and its test/review use different agents"). What is asserted:

  scoping     the house's state is ONE score on a fake player, never a key in any player's data; the dialogue cursor, the
              stage and the reward claim are each player's own data. Played through a simulator of the compiled Molang
              (tests/molang_dialogue_sim.py) with several players in one world.
  flows       player 1 hears the hundred lines, finds Lena, relocates her and is paid; player 2 arrives after and gets
              Hank's recap, Lena's recap and their own reward without the monologue; both finish at once and both are
              paid once; a restart-shaped state (score set, Lena still inside) is caught up by the apply step.
  seats       Hank's and Lena's stands: the relocation target in the dialogue is the seat the apply uses for the
              relocated state; the stands are on the heightmap, off the road, and on the right sides of the house.
  apply       reapply R18CH, run against a fake RCON: a fresh world seats Lena inside, a rescued world seats her outside,
              and a Lena left inside is moved, never doubled.

NOT covered, and it needs a running server: that Minecraft accepts each emitted command, that Cobblemon keeps a dialogue
open when its NPC is teleported away mid-conversation, and that the NPC selector finds her (the house is not built).
"""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import compile_dialogue as CD  # noqa: E402
import npc_seats  # noqa: E402
import molang_dialogue_sim as SIM  # noqa: E402
import keeper_sim as KS  # noqa: E402
import scenes_pack as SP  # noqa: E402

DATA = ROOT / "data"
HANK, LENA = "dlg_pallet_crushed_house_hank", "dlg_pallet_crushed_house_lena"
QUEST = "evt_pallet_crushed_house"
STAGE = "cobblers__quest__%s__stage" % QUEST
FIELD = "quest.%s.house_state" % QUEST
SEATS = json.loads((DATA / "npc_seats.json").read_text(encoding="utf-8"))
HOUSE = json.loads((DATA / "crushed_house.json").read_text(encoding="utf-8"))
MK = SEATS["markers"]
IN, OUT = MK["marker_pallet_crushed_house_interior_safe"], MK["marker_pallet_crushed_house_exterior_safe"]
HANK_SEAT = next(s for s in SEATS["seats"] if s["id"] == "npc_pallet_crushed_house_hank")
RESCUED, HOLD = "cobblers_pallet_rescued", "cobblers_hold"
SCENE = "cobblers/function/scenes/pallet_crushed_house"
SCENE_FILES, _SCENES = SP.build(DATA)       # the scene pack as generated: the keeper, the zone's beat and the two functions


def compile_pair(cd=CD):
    dialogue, quests, fields = cd.load(DATA)
    out = {}
    for cid in (HANK, LENA):
        conv = next(c for c in dialogue["conversations"] if c["id"] == cid)
        files = cd.compile_conversation(conv, quests, fields, DATA)
        out[cid] = files["data/cobblers/dialogues/%s.json" % cid]
    return out


@pytest.fixture(scope="module")
def packs():
    return compile_pair()


class Game:
    """A world with Lena inside the house and nobody on the scoreboard, plus helpers to play a player's talk."""

    def __init__(self, packs):
        self.packs, self.w = packs, SIM.World()
        self.lena = SIM.Npc("lena", *IN["at"])
        self.w.npcs += [self.lena, SIM.Npc("hank", *HANK_SEAT["at"])]
        self.w.pos = {}
        for name in ("lena_talk", "lena_release"):
            self.w.functions["cobblers:scenes/pallet_crushed_house/fn/%s" % name] = SCENE_FILES["data/%s/fn/%s.mcfunction" % (SCENE, name)]
        self.keeper = KS.Keeper(self.w, SCENE_FILES["data/%s/keep_lena.mcfunction" % SCENE])
        self.beat = SCENE_FILES["data/%s/beat.mcfunction" % SCENE]

    def enter(self, who):
        """The player walks into the scene's area (beside Hank)."""
        self.w.player(who)
        self.w.pos[who] = (1510.5, 118.0, 5254.5)

    def leave(self, who):
        self.w.pos.pop(who, None)

    def tick(self):
        """One scene cycle (tools/scenes_pack.py cycle): each player in the area runs the zone's transitions, then the keeper."""
        for who in list(self.w.pos):
            for line in self.beat:
                m = re.fullmatch(r'execute if entity @s\[.*?\] run runmolang "(.*)" @s', line)
                if m and "q.player.data()" in m.group(1):
                    self.w.run_molang(self.w.player(who), m.group(1))
        self.keeper.cycle()

    def where(self):
        pos = self.lena.pos
        if pos == (IN["at"][0] + .5, IN["at"][1], IN["at"][2] + .5):
            return "in"
        return "out" if pos == (OUT["at"][0] + .5, OUT["at"][1], OUT["at"][2] + .5) else pos

    def open(self, who, which):
        return SIM.Dialogue(self.w, self.w.player(who), self.packs[which])

    def talk(self, who, which, acks=0):
        """Open the conversation and click `acks` times; (the dialogue, every page shown)."""
        d = self.open(who, which)
        for _ in range(acks):
            d.ack()
        return d

    def run_out(self, who, which, limit=400):
        """Open and click until it closes; every page shown."""
        d = self.open(who, which)
        for _ in range(limit):
            if d.ack() is None:
                break
        return d.shown

    def monologue(self, who):
        """Hank's whole hundred, to the objective line and the close."""
        return self.run_out(who, HANK)

    def finish_lena(self, who):
        """Click through Lena's lines to the one that pays; returns the dialogue stopped on l012 and the pages."""
        d = self.open(who, LENA)
        for _ in range(40):
            if d.page == "l012":
                return d
            d.ack()
        raise AssertionError("never reached l012; shown %s" % d.shown)

    def stage(self, who):
        return self.w.player(who).data.get(STAGE)

    def seeds(self, who):
        return self.w.player(who).inv["cobblemon:miracle_seed"]

    def world_score(self):
        return self.w.scores.get(("#%s.house_state" % QUEST, CD.WORLD_OBJECTIVE))


# ---------------------------------------------------------------------------------------------------- compile
def test_both_conversations_compile_and_nothing_else_is_refused():
    # Without it the crushed-house pair silently stops shipping again, or a new refusal passes unnoticed.
    _files, done, refused = CD.build_all(DATA)
    assert refused == {}
    assert HANK in done and LENA in done


def test_the_world_constructs_appear_only_in_the_crushed_house_dialogues():
    # Without it the new compiler paths leak into a conversation that was compiling before (the other 173 were diffed
    # byte for byte against the pre-change compiler on 2026-10-13; this keeps them from changing in the way that matters).
    files, _done, _refused = CD.build_all(DATA)
    # Lena reads the keeper's record of where she stands; Hank reads nothing from the world (2026-10-21), and nothing relocates her
    users = {k for k, v in files.items() if isinstance(v, dict) and (CD.WORLD_OBJECTIVE in json.dumps(v) or "cobblers_actor_" in json.dumps(v))}
    assert users == {"data/cobblers/dialogues/%s.json" % LENA}


def test_a_world_field_is_refused_where_only_a_player_field_works():
    # Without it a world field named by a condition kind the compiler does not handle would read a player-data key
    # nobody ever writes, and the quest would look fine until two players played it.
    dialogue, quests, fields = CD.load(DATA)
    conv = next(c for c in dialogue["conversations"] if c["id"] == LENA)
    bad = json.loads(json.dumps(conv))
    bad["cursor"]["progression_field"] = FIELD
    with pytest.raises(CD.Unsupported):
        CD.compile_conversation(bad, quests, fields, DATA)


def test_a_world_enum_whose_initial_is_not_its_first_value_is_refused():
    # Without it a world field could start at a value an unset score cannot represent (an unset score reads as index 0).
    dialogue, quests, fields = CD.load(DATA)
    fields = json.loads(json.dumps(fields))
    fields[FIELD]["initial"] = "lena_relocated"
    conv = next(c for c in dialogue["conversations"] if c["id"] == LENA)
    with pytest.raises(CD.Unsupported):
        CD.compile_conversation(conv, quests, fields, DATA)


# ---------------------------------------------------------------------------------------------------- scoping
def test_the_house_state_is_a_score_and_the_players_fields_are_player_data(packs):
    # Without it the world field would be copied per player (each could rescue Lena separately) or the per-player
    # cursor/claim would be shared (one friend could consume another's hundred lines).
    text = json.dumps(packs)
    assert "cobblers__quest__%s__house_state" % QUEST not in text
    for per_player in ("dialogue_cursor", "reward_claimed", "stage"):
        assert "cobblers__quest__%s__%s" % (QUEST, per_player) in text
    assert "#%s.house_state" % QUEST in text and CD.WORLD_OBJECTIVE in text


def test_every_world_read_creates_the_objective_first(packs):
    # Without it a world nobody has written to yet fails every `execute ... score` read with an error (Minecraft fails the
    # command rather than reading false), so "blocked" would hold for nobody on a fresh world.
    for src in (packs[LENA]["initializationAction"],):
        first_read = src.index("if score #") if "if score #" in src else src.index("unless score #")
        assert "objectives add %s dummy" % CD.WORLD_OBJECTIVE in src[:first_read]


def test_the_naive_index_zero_probe_is_caught_on_a_fresh_world():
    # Mutate the GENERATOR, not the data: a probe for the initial value written as `matches 0` reads false on a holder
    # nobody has written. The fresh-world scenario must notice (Lena would say "still hidden" to everyone).
    real = CD.Compiler.world_test

    def naive(self, fid, value):
        idx = self.world_index(fid, value)
        return "if score %s %s matches %d" % (CD.world_holder(fid), CD.WORLD_OBJECTIVE, idx)
    CD.Compiler.world_test = naive
    try:
        g = Game(compile_pair())
        g.monologue("p1")
        d = g.open("p1", LENA)
        assert d.page != "l001"
    finally:
        CD.Compiler.world_test = real
    g = Game(compile_pair())
    g.monologue("p1")
    assert g.open("p1", LENA).page == "l001"


def test_a_probe_that_forgets_the_objective_is_caught_by_the_simulator():
    # Mutate the generator: with no `objectives add` before the read, the simulator (like Minecraft) fails the command.
    real = CD.Compiler.world_objective
    CD.Compiler.world_objective = lambda self: ""
    try:
        g = Game(compile_pair())
        with pytest.raises(RuntimeError, match="unknown objective"):
            g.open("p1", LENA)
    finally:
        CD.Compiler.world_objective = real


# ---------------------------------------------------------------------------------------------------- flows
def test_hank_says_the_hundred_lines_in_order_then_the_objective(packs):
    # Without it a line is skipped or repeated, or the hundred does not end at the objective.
    g = Game(packs)
    shown = g.monologue("p1")
    assert shown == ["h%03d" % i for i in range(1, 101)] + ["check_house_objective"]
    assert g.stage("p1") == "check_house"


def test_leaving_preserves_the_current_line_and_each_player_has_their_own(packs):
    # Without it a friend's progress is consumed by another's talk, or a closed dialogue restarts at line 1.
    g = Game(packs)
    d = g.talk("p1", HANK, acks=4)
    assert d.page == "h005"
    g.talk("p2", HANK, acks=1)
    assert g.open("p1", HANK).page == "h005"
    assert g.open("p2", HANK).page == "h002"


def test_lenas_not_yet_line_does_not_overwrite_hanks_cursor(packs):
    # Without it a player who tries Lena mid-monologue finds Hank answering with a page he does not have (the cursor is
    # shared by both conversations of the quest, and a terminal line used to write its own id into it).
    g = Game(packs)
    g.talk("p1", HANK, acks=9)
    assert g.open("p1", LENA).page == "lena_unavailable"
    d = g.open("p1", LENA)
    d.ack()
    assert g.open("p1", HANK).page == "h010"


def test_hank_after_lena_has_been_tried_mid_dialogue_repeats_the_objective(packs):
    # Without it a player who leaves Lena's lines and goes back to Hank gets a silent close.
    g = Game(packs)
    g.monologue("p1")
    d = g.open("p1", LENA)
    d.ack()
    assert g.stage("p1") == "lena_dialogue"
    assert g.open("p1", HANK).page == "check_house_objective"
    assert g.open("p1", LENA).page == "l002"


def test_player_one_rescues_lena_the_dialogue_moves_nobody_and_the_keeper_stands_her_outside(packs):
    # Without it the rescue still moves her from inside the dialogue (for everyone, at once), does not pay, or pays without
    # finishing the quest.
    g = Game(packs)
    g.monologue("p1")
    g.enter("p1")
    g.tick()
    assert g.where() == "in" and g.world_score() == 0
    d = g.finish_lena("p1")
    assert g.seeds("p1") == 0
    assert d.ack() == "post_lena_1"
    assert g.seeds("p1") == 1 and g.stage("p1") == "complete"
    assert RESCUED in g.w.player("p1").tags and g.w.player("p1").scores.get(HOLD) == 0
    assert g.where() == "in" and len(g.w.npcs) == 2          # the dialogue moved nobody and summoned nobody
    g.tick()
    assert g.where() == "out" and g.world_score() == 1 and len(g.w.npcs) == 2
    assert g.open("p1", HANK).page == "post_hank_1"
    assert g.open("p1", LENA).page == "post_lena_1"


def test_player_two_arrives_after_and_gets_the_whole_scene_with_lena_inside(packs):
    # Without it a late friend, or a player whose data was reset, finds her outside and never gets the scene (the owner's
    # report, 2026-10-21): the first rescue must not change what the next player meets.
    g = Game(packs)
    g.monologue("p1")
    g.enter("p1")
    g.finish_lena("p1").ack()
    g.tick()
    assert g.where() == "out"
    g.enter("p2")
    g.tick()
    assert g.where() == "in" and g.world_score() == 0
    assert g.monologue("p2") == ["h%03d" % i for i in range(1, 101)] + ["check_house_objective"]
    d = g.finish_lena("p2")
    assert d.ack() == "post_lena_1"
    assert (g.seeds("p1"), g.seeds("p2")) == (1, 1)
    g.tick()
    assert g.where() == "out" and len(g.w.npcs) == 2


def test_she_goes_outside_only_when_every_player_in_the_area_has_finished(packs):
    # Without it the first finisher sends her out from under a friend who is still on the way to her.
    g = Game(packs)
    for who in ("p1", "p2"):
        g.monologue(who)
        g.enter(who)
    g.finish_lena("p1").ack()
    g.tick()
    assert g.where() == "in"
    g.finish_lena("p2").ack()
    g.tick()
    assert g.where() == "out" and (g.seeds("p1"), g.seeds("p2")) == (1, 1)


def test_a_player_who_has_not_finished_and_finds_her_outside_is_told_to_wait_and_loses_nothing(packs):
    # Without it the unfinished player is shown "the opening is hidden" (she is not inside), or is paid for nothing, or
    # their cursor is overwritten. The keeper is held off while a player's conversation with her is open (the hold).
    g = Game(packs)
    g.monologue("p1")
    g.enter("p1")
    g.finish_lena("p1").ack()
    g.tick()
    assert g.where() == "out"
    g.open("p1", LENA)                                    # p1 talks to her again: the hold is set
    assert g.w.player("p1").scores[HOLD] == 40
    g.enter("p2")
    g.monologue("p2")
    g.tick()
    assert g.where() == "out" and g.world_score() == 1    # held off: nobody moves her from under p1
    d = g.open("p2", LENA)
    assert d.page == "lena_outside_wait" and g.stage("p2") == "check_house" and g.seeds("p2") == 0
    d.ack()
    assert g.stage("p2") == "check_house" and g.open("p2", LENA).page == "lena_outside_wait"
    for _ in range(39):
        g.tick()
        assert g.where() == "out"
    g.tick()                                              # the hold has run out
    assert g.where() == "in" and g.world_score() == 0
    assert g.open("p2", LENA).page == "l001"


def test_a_player_who_has_not_met_hank_and_finds_her_inside_is_told_the_opening_is_hidden(packs):
    # Without it a stranger inside the area gets the quest's first Lena line before Hank has asked anything of them.
    g = Game(packs)
    g.enter("p1")
    g.tick()
    assert g.where() == "in"
    assert g.open("p1", LENA).page == "lena_unavailable"


def test_a_player_whose_data_was_reset_gets_her_inside_again(packs):
    # Without it the tag outlives the data it mirrors: the player's quest is back at the start, the tag still says finished,
    # and Lena stays outside for them (the owner's reset, 2026-10-21).
    g = Game(packs)
    g.monologue("p1")
    g.enter("p1")
    g.finish_lena("p1").ack()
    g.tick()
    assert g.where() == "out"
    g.w.player("p1").data.clear()                         # the reset: Cobblemon's player data goes, the scoreboard tag stays
    assert RESCUED in g.w.player("p1").tags
    g.tick()
    assert RESCUED not in g.w.player("p1").tags and g.where() == "in"
    assert g.monologue("p1")[0] == "h001"


def test_a_player_who_finished_before_the_tag_existed_is_tagged_by_the_zone(packs):
    # Without it every player who finished under the old build keeps Lena inside until they talk to someone.
    g = Game(packs)
    g.w.player("old").data[STAGE] = "complete"
    g.enter("old")
    g.tick()
    assert RESCUED in g.w.player("old").tags and g.where() == "out"


def test_a_player_saved_at_the_retired_recap_stage_goes_back_to_check_house(packs):
    # Without it a player saved at shared_rescue_recap by the earlier build has no entry rule on Hank, and is shown nothing.
    g = Game(packs)
    p = g.w.player("late")
    p.data[STAGE] = "shared_rescue_recap"
    p.data["cobblers__quest__%s__dialogue_cursor" % QUEST] = "late_lena_recap"
    g.enter("late")
    g.tick()
    assert g.stage("late") == "check_house"
    assert g.open("late", HANK).page == "check_house_objective"


def test_each_player_is_paid_once_however_often_they_talk(packs):
    # Without it a talk repeats the reward (the claim is per player and must be written with the item).
    g = Game(packs)
    for who in ("p1", "p2"):
        g.monologue(who)
        g.enter(who)
        g.finish_lena(who).ack()
    for who in ("p1", "p2"):
        for _ in range(3):
            g.run_out(who, LENA, limit=6)
            g.open(who, HANK).ack()
        assert g.seeds(who) == 1


def test_hank_no_longer_reads_the_world_and_nothing_in_the_dialogue_relocates_her(packs):
    # Without it a dialogue effect moves her again for everyone, against the keeper (it did, until 2026-10-21).
    assert CD.WORLD_OBJECTIVE not in json.dumps(packs[HANK])
    for conv in packs.values():
        text = json.dumps(conv)
        assert "tp @e" not in text and "cobblers_actor_" not in text
    quests = json.loads((DATA / "quests.json").read_text(encoding="utf-8"))
    effects = [e["kind"] for q in quests["quests"] if q["id"] == QUEST for t in q["transitions"] for e in t["effects"]]
    assert "relocate_actor" not in effects and "compare_and_set_progression" not in effects


# ---------------------------------------------------------------------------------------------------- seats
def test_the_keepers_stands_are_the_stands_the_apply_uses(packs):
    # Without it the keeper stands her at one place and a re-apply (R18CH, which seats her by the score the keeper writes)
    # at another, and the two fight.
    (conv, at, cls, yaw, sel), = npc_seats.relocating_placements()
    assert (conv, cls) == (LENA, "cobblers:npc_pallet_crushed_house_lena")
    assert (at, yaw) == (tuple(IN["at"]), IN["yaw"])
    prog = json.loads((DATA / "progression.json").read_text(encoding="utf-8"))
    allowed = next(f for f in prog["quest_fields"] if f["id"] == FIELD)["allowed_values"]
    assert sel == {"objective": CD.WORLD_OBJECTIVE, "holder": CD.world_holder(FIELD), "value": allowed.index("lena_relocated"),
                   "at": tuple(OUT["at"]), "yaw": OUT["yaw"]}
    keep = "\n".join(SCENE_FILES["data/%s/keep_lena.mcfunction" % SCENE])
    tps = re.findall(r"run tp @s (-?\d+)\.5 (-?\d+) (-?\d+)\.5 (-?\d+) 0", keep)
    assert [tuple(map(int, t)) for t in tps] == [(*IN["at"], IN["yaw"]), (*OUT["at"], OUT["yaw"])]
    # the score the keeper writes for each stand is the one R18CH reads for it: 0 inside (also an unset score), 1 outside
    sets = re.findall(r"matches (\d) run scoreboard players set (\S+) %s (\d)" % CD.WORLD_OBJECTIVE, keep)
    assert sets == [("1", CD.world_holder(FIELD), "0"), ("0", CD.world_holder(FIELD), "1")]


def test_the_seats_pass_their_own_offline_checks_and_lena_is_not_double_seated():
    # Without it Lena is in R17N (a second one after the rescue) or the markers are off the ground or the road.
    assert "npc_pallet_crushed_house_lena" not in {s["id"] for s in SEATS["seats"]}
    probs = npc_seats.relocating_problems()
    assert probs == [], probs


def test_the_stands_are_one_above_the_canonical_heightmap_and_off_the_road():
    # Without it an NPC is buried, floats, or stands in the road. Heights are the heightmap's, read through tools/ground.py.
    import ground as G
    from terrain import TerrainUnavailable
    try:
        g = G.load()
    except TerrainUnavailable as e:      # a missing or mismatched heightmap (tests/test_npc_seats.py skips the same way)
        pytest.skip("heightmap unreadable: %s" % e)
    for name, rec in (("hank", HANK_SEAT), ("in", IN), ("out", OUT)):
        x, y, z = rec["at"]
        assert y == g(x, z) + 1 == rec["ground"]["y"] + 1, name
    assert npc_seats.relocating_problems(ground=g) == []


def test_the_stands_are_on_the_right_sides_of_the_house():
    # Without it Hank stands inside the house, Lena's pocket is outside it, or her post-rescue spot is in the debris.
    (x0, x1), (z0, z1) = HOUSE["site"]["lot"]["x"], HOUSE["site"]["lot"]["z"]
    inside = lambda p: x0 <= p[0] <= x1 and z0 <= p[2] <= z1   # noqa: E731
    assert inside(IN["at"]) and not inside(OUT["at"]) and not inside(HANK_SEAT["at"])
    door = HOUSE["front"]["door"]
    assert HANK_SEAT["at"][0] < door[0] and abs(HANK_SEAT["at"][2] - door[1]) <= 1      # outside the blocked front, west
    assert HOUSE["pocket"]["at"] == IN["at"] and HOUSE["after_rescue"]["at"] == OUT["at"]
    # the town's footprint (data/towns.json hometown), which the event doc says the house must stand inside
    assert 1397 <= x0 and x1 <= 1528 and 5228 <= z0 and z1 <= 5359


# ---------------------------------------------------------------------------------------------------- the apply
class FakeRcon:
    """Just enough of a server for reapply's `npc` action: a scoreboard value, NPCs with positions, spawnnpcat and tp."""

    def __init__(self, score, npcs):
        self.score, self.npcs, self.log = score, [list(map(float, p)) for p in npcs], []
        self.count = 0

    def _near(self, cmd):
        m = re.search(r"@e\[type=cobblemon:npc,x=(-?\d+),y=(-?\d+),z=(-?\d+),distance=\.\.2(?:,limit=1)?\]", cmd)
        if not m:
            return []
        c = tuple(map(int, m.groups()))
        return [n for n in self.npcs if sum((a - b) ** 2 for a, b in zip(n, c)) ** .5 <= 2]

    def __call__(self, cmd, timeout=None):
        self.log.append(cmd)
        if cmd.startswith("scoreboard players get"):
            return "%s has %d [%s]" % (cmd.split()[3], self.score, cmd.split()[4]) if self.score else "Can't get value of x; none is set"
        if cmd.startswith("execute if loaded"):
            return "Test passed"
        if cmd.startswith("execute if entity"):
            return "Test passed, count: 1" if self._near(cmd) else "Test failed"
        if cmd.startswith("execute store result storage cobblers:reapply npcs"):
            self.count = len(self._near(cmd))
            return ""
        if cmd.startswith("data get storage cobblers:reapply npcs"):
            return "Storage cobblers:reapply has the following contents: %d" % self.count
        if cmd.startswith("spawnnpcat"):
            x, y, z = map(int, cmd.split()[1:4])
            self.npcs.append([x + .5, float(y), z + .5])
            return "spawned"
        if cmd.startswith("tp @e["):
            m = re.fullmatch(r"tp (@e\[.*\]) (-?\d+)\.5 (-?\d+) (-?\d+)\.5 (-?\d+) 0", cmd)
            for n in self._near(m.group(1)):
                n[:] = [int(m.group(2)) + .5, float(m.group(3)), int(m.group(4)) + .5]
            return ""
        return ""


def run_r18ch(score, npcs, monkeypatch, tmp_path):
    """reapply's own handler (_run_steps) over the step's action, against a fake RCON. The action is built here from
    npc_seats.relocating_placements(), which is what reapply.steps() puts in R18CH (test_r18ch_* below says so), because
    steps() itself needs a prepared build/ that a worktree does not have."""
    import reapply
    monkeypatch.setattr(reapply.time, "sleep", lambda s: None)
    step = ("R18CH", "Lena", [("npc", n) for n in npc_seats.relocating_placements()])
    rc = FakeRcon(score, npcs)
    rec = {"steps": []}
    reapply._run_steps(SimpleNamespace(server_dir="x"), rc, [step], rec, tmp_path / "rec.json")
    return rc, rec


def centre(p):
    return (p[0] + .5, float(p[1]), p[2] + .5)


def test_r18ch_is_wired_after_r17n_from_the_relocating_placements():
    # Without it the apply never seats Lena (a step defined and never listed), or seats her before the town exists.
    # Read from the source, because reapply.steps() needs a prepared build/ (the test below runs it when there is one).
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    i17, i18 = src.index('out.append(("R17N"'), src.index('out.append(("R18CH"')
    assert i17 < i18
    assert 'for n in npc_seats.relocating_placements()' in src[i18:i18 + 400]


def test_r18ch_is_one_npc_action_for_lena_and_hank_stays_in_r17n():
    # Without it Lena is seated by R17N too, or not at all. Needs reapply.steps(), so a prepared build/.
    import reapply
    try:
        with pytest.MonkeyPatch.context() as mp:
            import ambient
            mp.setattr(reapply, "indexed", lambda *a, **k: [])
            mp.setattr(ambient, "placement_steps", lambda *a, **k: [])
            steps = reapply.steps()
    except SystemExit as e:
        pytest.skip("NOT_EXECUTED: reapply.steps() needs a prepared build/ (%s)" % str(e)[:80])
    acts = {s[0]: s[2] for s in steps}
    assert [(k, v[2]) for k, v in acts["R18CH"]] == [("npc", "cobblers:npc_pallet_crushed_house_lena")]
    assert "cobblers:npc_pallet_crushed_house_hank" in [v[2] for k, v in acts["R17N"]]
    assert "cobblers:npc_pallet_crushed_house_lena" not in [v[2] for k, v in acts["R17N"]]


def test_a_fresh_world_seats_lena_inside(monkeypatch, tmp_path):
    # Without it a first apply seats her outside, where she is already "rescued".
    rc, rec = run_r18ch(0, [], monkeypatch, tmp_path)
    assert rec["steps"][0]["problems"] == []
    assert [centre(IN["at"])] == [tuple(n) for n in rc.npcs]


def test_a_rescued_world_seats_lena_outside(monkeypatch, tmp_path):
    # Without it a re-apply after the rescue puts her back in the house, or spawns her where nobody finds her.
    rc, rec = run_r18ch(1, [], monkeypatch, tmp_path)
    assert rec["steps"][0]["problems"] == []
    assert [centre(OUT["at"])] == [tuple(n) for n in rc.npcs]


def test_a_rescued_world_moves_a_lena_left_inside_and_never_doubles_her(monkeypatch, tmp_path):
    # Without it a re-apply after the rescue leaves one Lena in the house and spawns another outside.
    rc, rec = run_r18ch(1, [centre(IN["at"])], monkeypatch, tmp_path)
    assert rec["steps"][0]["problems"] == []
    assert [centre(OUT["at"])] == [tuple(n) for n in rc.npcs]
    assert not [c for c in rc.log if c.startswith("spawnnpcat")]


def test_a_second_apply_changes_nothing(monkeypatch, tmp_path):
    # Without it every re-apply stacks another Lena.
    for score, at in ((0, IN), (1, OUT)):
        rc, rec = run_r18ch(score, [centre(at["at"])], monkeypatch, tmp_path)
        assert rec["steps"][0]["problems"] == []
        assert [centre(at["at"])] == [tuple(n) for n in rc.npcs]
        assert not [c for c in rc.log if c.startswith("spawnnpcat")]
