"""One leader per gym (the owner, 2026-10-07; docs/mechanics/ONE_LEADER_SWAP.md): a boss in data/challenge_mode.json
single_leader.rollout gets no second spawner, a swap of its one spawner and standing trainer, and a one-shot retire
function for the second spawner a world already holds. Builder's tests: validity of the generated lines only. Nothing
here proves rctmod honours a TrainerIds or TrainerId merge (experiment E7) -- that is the staging proof."""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import challenge_mode as CM  # noqa: E402
import route_trainers as RT  # noqa: E402

DATA = json.loads((ROOT / "data" / "challenge_mode.json").read_text(encoding="utf-8"))
OVER, _HELD = RT.overrides()
TAG = DATA["mode"]["tag"]
SFX = DATA["id_suffix"]
FN = "data/cobblers/function/trainers/challenge/%s.mcfunction"


@pytest.fixture(scope="module")
def files():
    return RT.files()


def _with(monkeypatch, rollout):
    d = copy.deepcopy(DATA)
    d["single_leader"]["rollout"] = rollout
    monkeypatch.setattr(CM, "doc", lambda: d)
    return d


def _brock_seat():
    g = json.loads((ROOT / "data" / "gym_buildings" / "gym1.json").read_text(encoding="utf-8"))
    assert g["leader"]["id"] == "kanto_brock"
    return tuple(g["leader"]["spawner"])


# ------------------------------------------------------------------------------------------------ the switch
def test_the_rollout_is_brock_only_until_the_staging_proof():
    assert DATA["single_leader"]["rollout"] == ["kanto_brock"]
    assert CM.rollout() == {"kanto_brock"}


def test_a_rollout_naming_a_boss_that_does_not_exist_fails(monkeypatch):
    _with(monkeypatch, ["kanto_brok"])
    with pytest.raises(SystemExit):
        CM.rollout()


def test_rollout_all_fails_closed_while_the_template_bosses_lack_their_measurements(monkeypatch):
    # Misty's gym and the League are templates: no record carries what their second spawners replaced, and none
    # carries the League's own spawners, so "all" must refuse until single_leader.restore (and, for the League,
    # normal_at) is measured for each, rather than drive or restore a guessed cell
    _with(monkeypatch, "all")
    with pytest.raises(SystemExit) as e:
        CM.spawner_files(CM.boss_ids(OVER))
    assert "normal_at" in str(e.value) or "restore" in str(e.value)


# ------------------------------------------------------------------------------------------------ Brock: one spawner
def test_brock_gets_no_second_spawner(files):
    cid = "kanto_brock" + SFX
    assert FN % ("place_" + cid) not in files
    cyc = files[FN % "cycle"]
    assert not any(l.endswith("place_" + cid) for l in cyc)
    # nothing anywhere in the trainers pack sets a spawner holding the Challenge id
    for k, v in files.items():
        if k.endswith(".mcfunction"):
            assert not any(re.match(r"\s*setblock .*trainer_spawner\{TrainerIds:\[\"%s\"\]" % cid, l) for l in v), k


def test_brocks_swap_drives_his_one_spawner_and_his_trainer(files):
    x, y, z = _brock_seat()
    assert (x, y, z) == (1832, 155, 3696)
    up, cid = "kanto_brock", "kanto_brock" + SFX
    lines = [l for l in files[FN % "cycle"] if "data merge" in l and ("{TrainerIds:[" in l or "TrainerId:\"kanto_brock" in l)
             and "positioned %d.5 %d %d.5" % (x, y, z) in l]
    assert len(lines) == 6
    merge = lambda i: 'data merge block %d %d %d {TrainerIds:["%s"]}' % (x, y, z, i)
    to_c = [l for l in lines if l.endswith(merge(cid))]
    back = [l for l in lines if l.endswith(merge(up))]
    assert len(to_c) == 1 and "as @p[distance=..%g] if entity @s[tag=%s]" % (CM.reach(), TAG) in to_c[0]
    assert len(back) == 2
    assert any("unless entity @s[tag=%s]" % TAG in l for l in back)
    assert any("unless entity @a[distance=..%g]" % CM.reach() in l for l in back)
    ent = [l for l in lines if "data merge entity" in l]
    assert len(ent) == 3
    assert sum(l.endswith('{TrainerId:"%s"}' % cid) and 'nbt={TrainerId:"%s",InBattle:0b}' % up in l for l in ent) == 1
    assert sum(l.endswith('{TrainerId:"%s"}' % up) and 'nbt={TrainerId:"%s",InBattle:0b}' % cid in l for l in ent) == 2
    # the spawner is changed before the trainer, in the same run
    cyc = files[FN % "cycle"]
    assert max(cyc.index(l) for l in to_c + back) < min(cyc.index(l) for l in ent)


def test_the_swap_never_runs_during_a_battle_and_only_on_loaded_ground(files):
    x, y, z = _brock_seat()
    for l in files[FN % "cycle"]:
        if "positioned %d.5 %d %d.5" % (x, y, z) in l and "data merge" in l:
            assert l.startswith("execute if loaded %d %d %d if block %d %d %d rctmod:trainer_spawner " % (x, y, z, x, y, z))
            for i in ("kanto_brock", "kanto_brock" + SFX):
                assert 'unless entity @e[type=rctmod:trainer,x=%d.5,y=%d,z=%d.5,distance=..24,nbt={TrainerId:"%s",' \
                       'InBattle:1b}]' % (x, y, z, i) in l


def test_reach_is_rctmods_sight_distance_plus_one():
    cfg = (ROOT / "modpack" / "config" / "rctmod-server.toml").read_text(encoding="utf-8")
    sight = float(re.search(r"^\s*forceBattleMaxDistance\s*=\s*([0-9.]+)", cfg, re.M).group(1))
    assert CM.reach() == sight + 1
    assert CM.reach() > 9.0, "the leader hold-off acts at 9: the swap must already have chosen by then"


def test_brocks_challenge_hold_off_stands_at_his_one_spawner(files):
    x, y, z = _brock_seat()
    cid = "kanto_brock" + SFX
    hold = [l for l in files[FN % "cycle"] if 'nbt={TrainerId:"%s"}' % cid in l and "Cooldown:40" in l]
    assert len(hold) == 1 and "x=%d.5,y=%d,z=%d.5," % (x, y, z) in hold[0]


# ------------------------------------------------------------------------------------------------ the others: unchanged
@pytest.mark.parametrize("up", [u for u in DATA["bosses"] if u != "kanto_brock"])
def test_a_boss_not_in_the_rollout_keeps_its_second_spawner(files, up):
    cid = up + SFX
    assert FN % ("place_" + cid) in files
    assert FN % ("retire_" + cid) not in files
    assert sum(l.endswith("place_" + cid) for l in files[FN % "cycle"]) == 1
    assert not any("data merge block" in l and cid in l for l in files[FN % "cycle"])


def test_the_rollout_changes_nothing_for_the_bosses_outside_it(monkeypatch):
    bosses = CM.boss_ids(OVER)
    with_brock = CM.spawner_files(bosses)
    _with(monkeypatch, [])
    without = CM.spawner_files(CM.boss_ids(OVER))
    cid = "kanto_brock" + SFX
    keep = lambda d: {k: v for k, v in d.items() if k != "cycle" and cid not in k}
    assert keep(with_brock) == keep(without)
    assert [l for l in with_brock["cycle"] if "kanto_brock" not in l] == \
           [l for l in without["cycle"] if "kanto_brock" not in l]
    assert FN % ("place_" + cid) in without and FN % ("retire_" + cid) not in without


# ------------------------------------------------------------------------------------------------ the retire function
def test_the_retire_function_targets_exactly_the_recorded_second_spawner(files):
    sx, sy, sz = DATA["bosses"]["kanto_brock"]["spawner"]["at"]
    cid = "kanto_brock" + SFX
    body = [l for l in files[FN % ("retire_" + cid)] if not l.startswith("#")]
    sets = [tuple(int(v) for v in m.groups()) for l in body for m in [re.search(r"run setblock (-?\d+) (-?\d+) (-?\d+) ", l)] if m]
    assert sorted(sets) == sorted([(sx, sy - 1, sz), (sx, sy, sz)])
    for l in body:
        if " setblock " in l:
            assert l.startswith('execute if block %d %d %d rctmod:trainer_spawner{TrainerIds:["%s"]} ' % (sx, sy, sz, cid))
    # every kill: only while the second spawner stands (a re-run kills nothing), with nobody near the old seat, never in
    # a battle; one for the Challenge id, one for any Normal-id trainer but the kept one; all before the setblocks
    # (the 2026-10-07 integration fix of audit P1:retire / P1:retire_kills)
    kill = [i for i, l in enumerate(body) if " kill " in l]
    guard = ('execute if block %d %d %d rctmod:trainer_spawner{TrainerIds:["%s"]} positioned %d.5 %d %d.5 unless entity @a['
             % (sx, sy, sz, cid, sx, sy, sz))
    assert len(kill) == 2 and all(body[i].startswith(guard) for i in kill)
    assert 'nbt={TrainerId:"%s",InBattle:0b}]' % cid in body[kill[0]]
    assert 'nbt={TrainerId:"kanto_brock",InBattle:0b},tag=!cobblers_keep_leader]' in body[kill[1]]
    assert max(kill) < min(i for i, l in enumerate(body) if " setblock " in l)
    nx, ny, nz = _brock_seat()
    assert not any("%d %d %d" % (nx, ny, nz) in l for l in body), "the retire function must not touch the one spawner"


def test_the_retire_function_restores_the_floor_the_gym_model_built():
    sys.path.insert(0, str(ROOT / "tools"))
    import gym_buildings as GB
    sx, sy, sz = DATA["bosses"]["kanto_brock"]["spawner"]["at"]
    e, _r, _l = GB.build_one(GB.records("gym1")[0][1])
    lines = CM.retire_lines("kanto_brock", "kanto_brock" + SFX, DATA["bosses"]["kanto_brock"])
    assert any(l.endswith("run setblock %d %d %d %s" % (sx, sy, sz, e.at(sx, sy, sz))) for l in lines)
    assert any(l.endswith("run setblock %d %d %d %s" % (sx, sy - 1, sz, e.at(sx, sy - 1, sz))) for l in lines)
    assert "trainer_spawner" not in e.at(sx, sy, sz) and e.at(sx, sy + 1, sz) == "minecraft:air"


def test_the_retire_function_follows_the_recorded_position_not_a_constant(monkeypatch):
    d = _with(monkeypatch, ["kanto_brock"])
    d["bosses"]["kanto_brock"]["spawner"]["at"] = [1831, 155, 3697]
    lines = CM.retire_lines("kanto_brock", "kanto_brock" + SFX, d["bosses"]["kanto_brock"])
    assert any("run setblock 1831 155 3697 " in l for l in lines)
    assert not any("1830 155 3696" in l for l in lines)


def test_a_template_boss_in_the_rollout_needs_its_restore_blocks(monkeypatch):
    d = _with(monkeypatch, ["kanto_misty"])
    with pytest.raises(SystemExit):
        CM.retire_lines("kanto_misty", "kanto_misty" + SFX, d["bosses"]["kanto_misty"])


# ------------------------------------------------------------------------------------------------ the reapply step
def test_reapply_runs_every_retire_function_in_a_held_step_with_its_read_back(files):
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert 'out.append(("R17L", ' in src
    assert src.index('out.append(("R17", ') < src.index('out.append(("R17L", '), "after the restart that loads the pack"
    assert 'kind == "check" and v == "single_leader"' in src
    fns = CM.retire_functions()
    assert fns == ["cobblers:trainers/challenge/retire_kanto_brock" + SFX]
    for f in fns:
        assert FN % f.split("challenge/", 1)[1] in files
    (x0, z0, x1, z1), = CM.retire_hold()
    for (x, _y, z) in (DATA["bosses"]["kanto_brock"]["spawner"]["at"], _brock_seat()):
        assert x0 <= x - 24 and x + 24 <= x1 and z0 <= z - 24 and z + 24 <= z1


class _World:
    def __init__(self, blocks, player_near=False, stray=False):
        self.blocks, self.player_near, self.stray, self.sent = blocks, player_near, stray, []

    def __call__(self, cmd):
        self.sent.append(cmd)
        m = re.match(r"execute if block (-?\d+) (-?\d+) (-?\d+) (\S+)$", cmd)
        if m:
            at, want = tuple(int(v) for v in m.groups()[:3]), m.group(4)
            have = self.blocks.get(at, "minecraft:air")
            return "Test passed" if have.startswith(want) else "Test failed"
        if " if entity @a[" in cmd:
            return "Test passed, count: 1" if self.player_near else "Test failed"
        if " if entity @e[" in cmd:
            return "Test passed, count: 1" if self.stray else "Test failed"
        raise AssertionError(cmd)


def test_the_read_back_passes_on_a_retired_world_and_names_each_fault():
    s, n = tuple(DATA["bosses"]["kanto_brock"]["spawner"]["at"]), _brock_seat()
    one = 'rctmod:trainer_spawner{TrainerIds:["kanto_brock"]}'
    assert CM.single_leader_verify(_World({n: one})) == []
    # the second spawner left behind
    assert any("still there" in p for p in CM.single_leader_verify(
        _World({n: one, s: 'rctmod:trainer_spawner{TrainerIds:["kanto_brock_challenge"]}'})))
    # the one spawner missing
    assert any("no spawner" in p for p in CM.single_leader_verify(_World({})))
    # the one spawner stuck on the Challenge id with nobody near
    assert any("does not read" in p for p in CM.single_leader_verify(
        _World({n: 'rctmod:trainer_spawner{TrainerIds:["kanto_brock_challenge"]}'})))
    # a stray Challenge-id trainer
    assert any("still carries" in p for p in CM.single_leader_verify(_World({n: one}, stray=True)))
    # a player near: said so, never passed as checked
    assert any("NOT checked" in p for p in CM.single_leader_verify(_World({n: one}, player_near=True)))
