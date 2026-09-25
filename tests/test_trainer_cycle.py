"""tools/route_trainers.py's trainer cycle: what stands in for rctmod's unsaved "beaten by this player" memory.

Written by the test author, not by the session that wrote the cycle.

rctmod 0.19.0-beta keeps a trainer's per-player wins and defeats only in the loaded entity (the implementer read it
from the bytecode, docs/STATE.md World facts), so after a restart or an unload a beaten trainer battles again. The
cycle (cobblers:trainers/cycle, every 10 ticks through #minecraft:tick) keeps each placed trainer home, gives each
nearby player a per-trainer tag from their own saved defeat field, and puts the trainer on Cooldown while only players
who have beaten it are near.

What is asserted, on tools/route_trainers.files() and placements() over the real data: the tick and load function
tags name cobblers:trainers/tick and /load; the load function creates the clock's objective; the clock, simulated
from the generated lines, runs the cycle every 10 ticks; for every placed trainer (13 route + 5 guardians) the cycle
has exactly one home line, one tag line and one cooldown line, each keyed to that trainer's own TrainerId, seat and
defeat field (a guardian's first `sets` field, a route trainer's quest.<id>.defeated); the tag is per trainer; the
cooldown requires both a tagged player near and no untagged player near; the tag radius is past the trainer's sight
(everyone it can battle on sight has a fresh tag).

Not covered, and it needs a running server: that rctmod honours Cooldown in canBattleAgainst and says on_cooldown;
that q.player.uuid and q.run_command work inside runmolang as the lines assume; that the nbt InBattle key exists;
that tp home does not fight rctmod's own goals; that a restart really forgets the win (the owner's report).
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import route_trainers as RT  # noqa: E402

FN = "data/cobblers/function/trainers/%s.mcfunction"
RECS, SEATS, _FIELDS = RT.load()
PLACED = RT.placements()
IDS = [t for t, _s, _y in PLACED]


@pytest.fixture(scope="module")
def files():
    return RT.files()


@pytest.fixture(scope="module")
def cycle(files):
    return [l for l in files[FN % "cycle"] if l.strip() and not l.startswith("#")]


def _field(tid):
    r = RECS[tid]
    return r["sets"][0] if "sets" in r else "quest.%s.defeated" % tid


def _sight(tid):
    seat = next(s for s in SEATS if s["id"] == tid)
    return float(seat.get("sight_distance", 8.0)) if seat.get("eye_contact") else 0.0


def _selector_ids(line):
    return re.findall(r'nbt=\{TrainerId:"([a-z0-9_]+)"', line)


def _classify(cycle):
    home, tags, cool, other = {}, {}, {}, []
    for l in cycle:
        if l.startswith("scoreboard players set #clock "):
            continue
        if " run tp @s " in l:
            for t in _selector_ids(l):
                home.setdefault(t, []).append(l)
        elif " run runmolang " in l:
            for t in re.findall(r"add cobblers_beat_([a-z0-9_]+)'", l):
                tags.setdefault(t, []).append(l)
        elif "{Cooldown:" in l:
            for t in _selector_ids(l):
                cool.setdefault(t, []).append(l)
        else:
            other.append(l)
    return home, tags, cool, other


# Without it the tick never runs the cycle (no function tag, or a tag naming a function the pack does not write), or
# the clock's objective is never created and every score command fails silently.
def test_the_tick_and_load_tags_name_the_trainer_functions(files):
    assert "cobblers:trainers/tick" in files["data/minecraft/tags/function/tick.json"]["values"]
    assert "cobblers:trainers/load" in files["data/minecraft/tags/function/load.json"]["values"]
    assert FN % "tick" in files and FN % "load" in files
    assert "scoreboard objectives add cobblers_trainers dummy" in files[FN % "load"]


# Without it the cycle runs every tick (a load on the server for nothing) or rarely enough that a beaten trainer's
# cooldown lapses and it battles the player again. Simulated from the generated lines, not read from a constant.
def test_the_cycle_runs_every_10_ticks(files):
    tick = files[FN % "tick"]
    inc = [l for l in tick if re.fullmatch(r"scoreboard players add #clock cobblers_trainers 1", l)]
    call = [re.fullmatch(r"execute if score #clock cobblers_trainers matches (\d+)\.\. run function cobblers:trainers/cycle", l)
            for l in tick]
    call = [m for m in call if m]
    assert len(inc) == 1 and len(call) == 1, tick
    at = int(call[0].group(1))
    resets = [re.fullmatch(r"scoreboard players set #clock cobblers_trainers (-?\d+)", l) for l in files[FN % "cycle"]]
    resets = [int(m.group(1)) for m in resets if m]
    assert len(resets) == 1
    clock, runs = 0, []
    for t in range(1, 61):
        clock += 1
        if clock >= at:
            runs.append(t)
            clock = resets[0]
    assert runs == list(range(10, 61, 10)), runs


# Without it a trainer is not held home, not tagged for, or not cooled down (it rebattles its beaten players after a
# restart), or is handled twice, or a line acts on some other trainer.
def test_every_placed_trainer_has_exactly_one_line_of_each_kind(cycle):
    assert len(IDS) == 18 and len(set(IDS)) == 18
    home, tags, cool, other = _classify(cycle)
    assert not other, other
    for kind, got in (("home", home), ("tag", tags), ("cooldown", cool)):
        assert sorted(got) == sorted(IDS), (kind, sorted(set(IDS) ^ set(got)))
        assert all(len(v) == 1 for v in got.values()), (kind, {k: len(v) for k, v in got.items() if len(v) != 1})
        assert all(len(set(_selector_ids(v[0])) | {k}) == 1 for k, v in got.items()), kind


# Without it a trainer knocked off its seat in battle stays wherever it was pushed, is pulled mid-battle, or is
# pulled to another trainer's seat.
@pytest.mark.parametrize("tid,seat,_yaw", PLACED, ids=IDS)
def test_the_home_line_returns_this_trainer_to_its_own_seat_out_of_battle(cycle, tid, seat, _yaw):
    home, _t, _c, _o = _classify(cycle)
    (l,) = home[tid]
    x, y, z = seat
    m = re.fullmatch(r"execute as @e\[type=rctmod:trainer,x=(\S+?),y=(\S+?),z=(\S+?),distance=\.\.\d+,"
                     r'nbt=\{TrainerId:"%s",InBattle:0b\}\] positioned (\S+) (\S+) (\S+) '
                     r"unless entity @s\[distance=\.\.0\.75\] run tp @s (\S+) (\S+) (\S+)" % re.escape(tid), l)
    assert m, l
    want = ("%d.5" % x, "%d" % y, "%d.5" % z)
    assert m.groups()[0:3] == want and m.groups()[3:6] == want and m.groups()[6:9] == want


# Without it a player's tag says "beaten" for the wrong trainer or from someone else's field, never clears, or is set
# before the player has won; or players the trainer can see on sight are outside the radius and keep a stale tag.
@pytest.mark.parametrize("tid,seat,_yaw", PLACED, ids=IDS)
def test_the_tag_line_sets_this_trainers_tag_from_the_players_own_field(cycle, tid, seat, _yaw):
    _h, tags, _c, _o = _classify(cycle)
    (l,) = tags[tid]
    x, y, z = seat
    m = re.fullmatch(r'execute positioned %d\.5 %d %d\.5 as @a\[distance=\.\.([0-9.]+)\] run runmolang "(.*)" @s' % (x, y, z), l)
    assert m, l
    radius, mol = float(m.group(1)), m.group(2)
    assert radius > _sight(tid) and radius >= 6
    key = RT.key(_field(tid))
    tag = "cobblers_beat_%s" % tid
    assert mol.startswith("t.d = q.player.data();")
    assert re.fullmatch(r"t\.d = q\.player\.data\(\); \(t\.d\.%s == 1\) \? "
                        r"\{ q\.run_command\('tag ' \+ q\.player\.uuid \+ ' add %s'\); \} : "
                        r"\{ q\.run_command\('tag ' \+ q\.player\.uuid \+ ' remove %s'\); \};"
                        % (re.escape(key), tag, tag), mol), mol


# Without it one trainer's tag also silences another (beating Hope would let a player walk past Paula).
def test_the_beaten_tag_is_per_trainer(cycle, files):
    _h, tags, _c, _o = _classify(cycle)
    names = {t: set(re.findall(r"(cobblers_beat_[a-z0-9_]+)", tags[t][0])) for t in IDS}
    assert all(names[t] == {"cobblers_beat_%s" % t} for t in IDS)
    assert len({n for s in names.values() for n in s}) == len(IDS)
    for t in IDS:
        assert "tag @s add cobblers_beat_%s" % t in files["data/cobblers/function/trainers/won/%s.mcfunction" % t]


# Without it the trainer cools down while a player who has not beaten it stands there (that player can never be
# battled on sight while a friend who won is near, and so never opens the room), or never cools down (it rebattles
# the players who beat it after every restart).
@pytest.mark.parametrize("tid,seat,_yaw", PLACED, ids=IDS)
def test_the_cooldown_needs_a_tagged_player_near_and_no_untagged_one(cycle, tid, seat, _yaw):
    _h, tags, cool, _o = _classify(cycle)
    (l,) = cool[tid]
    tag = "cobblers_beat_%s" % tid
    m = re.fullmatch(r'execute as @e\[type=rctmod:trainer,[^\]]*nbt=\{TrainerId:"%s"\}\] at @s '
                     r"if entity @a\[distance=\.\.([0-9.]+),tag=%s\] "
                     r"unless entity @a\[distance=\.\.([0-9.]+),tag=!%s\] "
                     r"run data merge entity @s \{Cooldown:(\d+)\}" % (re.escape(tid), tag, tag), l)
    assert m, l
    tag_radius = float(re.search(r"@a\[distance=\.\.([0-9.]+)\]", tags[tid][0]).group(1))
    assert float(m.group(1)) == float(m.group(2)) == tag_radius
    assert int(m.group(3)) > 10          # outlasts the 10-tick period, so the cooldown never lapses between cycles
