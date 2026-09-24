"""tools/reapply.py: Victory Road's cave, Habitat Block and NPC steps (R9C, R9E, R9F) and their packs.

Written by the test author, not by the session that wrote the tool.

What is asserted: the cave runs after the Deep, the Habitat Blocks after the cave, and the NPC step last of the
three; R9C runs every function cobblers_vr_caves lists, in the order it lists them; no step runs a retired or
staging-only Victory Road pack, and R9D is gone; every generated pack that ships functions is run by a step or
excluded with a reason (on the packs present in build/datapacks), and the retired and staging-only packs are among
the excluded with a reason that says which they are; npcs() derives each reward NPC from data/rewards.json and
data/dialogue.json and fails closed when a reward names a quest nothing runs; and the packs the cave needs are
installed on the server while the retired and staging-only ones are not.

steps() reads each generated pack's index.txt, so the order and coverage tests SKIP when build/datapacks does not
hold them (run `python tools/reapply.py prepare` first); that skip is not a pass.

Not covered, and it needs a boot or a functional test:
  - that the steps actually run against a server (RCON, the lock, the waits), and that a re-export followed by
    `reapply.py run` puts the cave, its Habitat Blocks and the NPC back;
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
    ("cobblers_deep", "deep"), ("cobblers_vr_caves", "vr_caves")
RETIRED = ("cobblers_victory_road", "cobblers_vr_regions")
STAGING_ONLY = ("cobblers_vr_clear",)


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


# Without it a re-apply builds the cave before the Deep its mouth opens from, places a Habitat Block before the floor
# it sits in is built (R9C's shell pass overwrites it), or places the NPC before the cavern it stands in exists.
@pytest.mark.parametrize("before,after", [("R9B", "R9C"), ("R9C", "R9E"), ("R9E", "R9F")])
def test_the_cave_follows_the_deep_the_habitat_blocks_the_cave_and_the_npcs_the_blocks(steps, before, after):
    assert _at(steps, before) < _at(steps, after)


# Without it R9C is present but runs nothing (an empty index.txt), or a subset, or runs the cave's passes out of the
# order the pack wrote them in (shell, air, floor, fluid, fittings), and the ordering above holds for a step that
# builds nothing or builds it wrong.
def test_r9c_runs_every_vr_caves_function_the_pack_lists_in_its_order(steps):
    acts = steps[_at(steps, "R9C")][2]
    listed = reapply.indexed("cobblers_vr_caves", "vr_caves")
    assert listed, "cobblers_vr_caves lists no functions: the test would pass on nothing"
    assert acts == [("fn", "cobblers:vr_caves/%s" % f) for f in listed]


# Without it a step still runs a retired pack on a re-apply (the schema 2 spine or its regions, carving the old road
# through the cave's rock) or the staging-only clear (filling the cave's surroundings with rock on a fresh export);
# or R9D survives as a step reading an index nothing writes any more.
def test_no_step_runs_a_retired_or_staging_only_victory_road_pack(steps):
    ran = {v.split(":", 1)[1].split("/", 1)[0] for _s, _t, acts in steps for k, v in acts if k == "fn" and ":" in v}
    assert not ran & {"victory_road", "vr_regions", "vr_clear"}, ran
    assert "R9D" not in [s[0] for s in steps]


# Without it R9F places no NPC, or a different set from the rewards that are given through one.
def test_r9f_places_exactly_the_npcs_the_rewards_are_given_through(steps):
    acts = steps[_at(steps, "R9F")][2]
    assert acts == [("npc", n) for n in reapply.npcs()]
    assert acts, "no npc_grant in data/rewards.json, or R9F places none"


# Without it a generated pack that writes blocks has no step and no reason, and a re-export erases what it built
# while the re-apply reports green (five Rift builds were lost this way until 2026-09-23).
def test_every_function_pack_present_is_run_by_a_step_or_excluded_with_a_reason(steps):
    assert reapply.uncovered(steps) == []


# Without it uncovered() could be passing because it looks at nothing: it must see the cave pack, and must report
# it when its step is gone.
def test_uncovered_sees_the_cave_pack_and_reports_it_when_its_step_is_gone(steps):
    assert "cobblers_vr_caves" in reapply.function_packs()
    without = [s for s in steps if s[0] != "R9C"]
    assert any(b.startswith("cobblers_vr_caves ") for b in reapply.uncovered(without))


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


# Without it a retired or staging-only Victory Road pack still sitting in build/datapacks falls into the fail-closed
# check and `prepare` stops, or somebody gives it a step back to make the check pass.
@pytest.mark.parametrize("pack", RETIRED + STAGING_ONLY)
def test_the_retired_and_staging_only_victory_road_packs_are_excluded_with_a_reason(pack):
    assert str(reapply.EXCLUDED.get(pack, "")).strip(), "%s is not in reapply.EXCLUDED with a reason" % pack


# Without it the exclusion reason could say anything: a retired pack has to be marked retired and the clear pack
# staging only, so neither is mistaken for the other when a re-export is planned.
def test_the_exclusion_reasons_say_retired_or_staging_only():
    for pack in RETIRED:
        assert "retired" in reapply.EXCLUDED[pack].lower(), (pack, reapply.EXCLUDED[pack])
    for pack in STAGING_ONLY:
        assert "staging only" in reapply.EXCLUDED[pack].lower(), (pack, reapply.EXCLUDED[pack])


# Without it a pack is built but never installed on the server: the cave, its Habitat Blocks, the finds, or the NPC
# classes and dialogue the reward NPC needs are missing from the running game.
@pytest.mark.parametrize("pack", ["cobblers_vr_caves", "cobblers_habitats", "cobblers_rewards", "cobblers_dialogue"])
def test_the_packs_the_cave_needs_are_installed_on_the_server(pack):
    assert pack in reapply.SERVER_PACKS


# Without it install() still copies a retired or staging-only pack onto the server, where its functions sit one
# /function away from carving the old road through the cave, or from filling cells round it with rock.
@pytest.mark.parametrize("pack", RETIRED + STAGING_ONLY)
def test_no_retired_or_staging_only_victory_road_pack_is_installed_on_the_server(pack):
    assert pack not in reapply.SERVER_PACKS
