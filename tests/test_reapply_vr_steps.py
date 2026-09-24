"""tools/reapply.py: the Victory Road regions, Habitat Block, reward and NPC steps (R9D, R9E, R9F) and their packs.

Written by the test author, not by the session that wrote the tool.

What is asserted: the regions run after the road and the Habitat Blocks after the regions, the NPC step last of
the three; every generated pack that ships functions is run by a step or excluded with a reason (on the packs
present in build/datapacks); npcs() derives each reward NPC from data/rewards.json and data/dialogue.json and fails
closed when a reward names a quest nothing runs; and the new packs are installed on the server.

steps() reads each generated pack's index.txt, so the order and coverage tests SKIP when build/datapacks does not
hold them (run `python tools/reapply.py prepare` first); that skip is not a pass.

Not covered, and it needs a boot or a functional test:
  - that the steps actually run against a server (RCON, the lock, the waits), and that a re-export followed by
    `reapply.py run` puts the regions, blocks and NPC back;
  - that spawnnpcat places the NPC with its class loaded and its dialogue working (NPC classes load at server start);
  - that the Habitat Blocks are live after the 20 second wait (EXP-021 says a chunk reload is needed).
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import reapply  # noqa: E402

NEEDS_INDEX = ("cobblers_rift", "rift"), ("cobblers_rift_biome", "rift"), ("cobblers_league_tunnel", "league_tunnel"), \
    ("cobblers_deep", "deep"), ("cobblers_victory_road", "victory_road"), ("cobblers_vr_regions", "vr_regions")


@pytest.fixture(scope="module")
def steps():
    if not reapply.PACKS.is_dir():
        pytest.skip("no build/datapacks: the generated packs are not built in this checkout")
    missing = [p for p, f in NEEDS_INDEX
               if not (reapply.PACKS / p / "data" / "cobblers" / "function" / f / "index.txt").is_file()]
    if missing:
        pytest.skip("steps() reads index.txt of packs not built here: %s (python tools/reapply.py prepare)" % missing)
    return reapply.steps()


def _at(steps, sid):
    ids = [s[0] for s in steps]
    assert sid in ids, "no step %s in %s" % (sid, ids)
    return ids.index(sid)


# Without it a re-apply re-runs the road after its regions: the road's walls close every fork again and the five
# regions are sealed off from the road (data/vr_regions.json re_apply_after); a Habitat Block is placed before the
# floor it sits in is built, and the NPC before the room it stands in.
@pytest.mark.parametrize("before,after", [("R9C", "R9D"), ("R9D", "R9E"), ("R9E", "R9F")])
def test_the_regions_follow_the_road_the_habitat_blocks_the_regions_and_the_npcs_the_blocks(steps, before, after):
    assert _at(steps, before) < _at(steps, after)


# Without it R9D is present but empty (an index.txt with nothing in it), and the order above holds for a step that
# builds nothing.
def test_r9d_runs_every_vr_regions_function_the_pack_lists(steps):
    acts = steps[_at(steps, "R9D")][2]
    listed = reapply.indexed("cobblers_vr_regions", "vr_regions")
    assert listed
    assert acts == [("fn", "cobblers:vr_regions/%s" % f) for f in listed]


# Without it R9F places no NPC, or a different set from the rewards that are given through one.
def test_r9f_places_exactly_the_npcs_the_rewards_are_given_through(steps):
    acts = steps[_at(steps, "R9F")][2]
    assert acts == [("npc", n) for n in reapply.npcs()]
    assert acts, "no npc_grant in data/rewards.json, or R9F places none"


# Without it a generated pack that writes blocks has no step and no reason, and a re-export erases what it built
# while the re-apply reports green (five Rift builds were lost this way until 2026-09-23).
def test_every_function_pack_present_is_run_by_a_step_or_excluded_with_a_reason(steps):
    assert reapply.uncovered(steps) == []


# Without it uncovered() could be passing because it looks at nothing: it must see the regions pack, and must
# report a pack no step runs.
def test_uncovered_sees_the_regions_pack_and_reports_it_when_its_step_is_gone(steps):
    assert "cobblers_vr_regions" in reapply.function_packs()
    without = [s for s in steps if s[0] != "R9D"]
    assert any(b.startswith("cobblers_vr_regions ") for b in reapply.uncovered(without))


# ------------------------------------------------------------------ npcs()

REWARDS = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
DIALOGUE = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))


# Without it an NPC is placed at the wrong spot, with the wrong class, or for the wrong conversation, and the quest
# that gives the find cannot be started.
def test_npcs_derives_conversation_position_and_class_for_every_npc_grant():
    want = []
    for r in REWARDS["rewards"]:
        if r.get("kind") != "npc_grant":
            continue
        (conv,) = [c for c in DIALOGUE["conversations"] if c.get("quest_id") == r["quest"]][:1]
        want.append((conv["id"], tuple(r["npc_at"]), "cobblers:%s" % conv["npc_id"]))
    assert want, "no npc_grant in data/rewards.json: the test would pass on nothing"
    assert reapply.npcs() == want


@pytest.fixture
def data_copy(tmp_path, monkeypatch):
    """A copy of data/rewards.json and data/dialogue.json under a tmp ROOT; the real files are never written."""
    (tmp_path / "data").mkdir()
    for name in ("rewards.json", "dialogue.json"):
        shutil.copy(ROOT / "data" / name, tmp_path / "data" / name)
    monkeypatch.setattr(reapply, "ROOT", tmp_path)
    return tmp_path / "data"


# Without it the tmp-ROOT fixture might not be read at all, and the refusal below could pass for the wrong reason.
def test_npcs_reads_the_data_under_root(data_copy):
    rw = json.loads((data_copy / "rewards.json").read_text(encoding="utf-8"))
    rw["rewards"] = [r for r in rw["rewards"] if r.get("kind") != "npc_grant"]
    (data_copy / "rewards.json").write_text(json.dumps(rw), encoding="utf-8")
    assert reapply.npcs() == []


# Without it a reward whose quest no conversation runs is placed as an NPC with no dialogue, or skipped silently,
# and the find can never be given.
def test_npcs_refuses_a_reward_whose_quest_no_conversation_runs(data_copy):
    rw = json.loads((data_copy / "rewards.json").read_text(encoding="utf-8"))
    grants = [r for r in rw["rewards"] if r.get("kind") == "npc_grant"]
    assert grants
    grants[0]["quest"] = "evt_no_conversation_runs_this"
    (data_copy / "rewards.json").write_text(json.dumps(rw), encoding="utf-8")
    with pytest.raises(SystemExit, match="evt_no_conversation_runs_this"):
        reapply.npcs()


# ------------------------------------------------------------------ the pack lists

# Without it the rewards pack falls into the fail-closed check (it ships functions no step runs) and `prepare`
# stops; or it is excluded without anyone having written down why.
def test_the_rewards_pack_is_excluded_with_a_reason():
    assert str(reapply.EXCLUDED.get("cobblers_rewards", "")).strip()


# Without it a pack is built but never installed on the server: the regions, their Habitat Blocks, the finds, or
# the NPC classes and dialogue the reward NPC needs are missing from the running game.
@pytest.mark.parametrize("pack", ["cobblers_dialogue", "cobblers_vr_regions", "cobblers_habitats", "cobblers_rewards"])
def test_the_new_packs_are_installed_on_the_server(pack):
    assert pack in reapply.SERVER_PACKS
