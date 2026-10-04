"""tools/route_trainers.py's trainer cycle: what stands in for rctmod's unsaved "beaten by this player" memory.

Written by the test author, not by the session that wrote the cycle.

rctmod 0.19.0-beta keeps a trainer's per-player wins and defeats only in the loaded entity (the implementer read it
from the bytecode, docs/STATE.md World facts), so after a restart or an unload a beaten trainer battles again. The
cycle (cobblers:trainers/cycle, every 10 ticks through #minecraft:tick) keeps each placed trainer home, gives each
nearby player a per-trainer tag from their own saved defeat field, and puts the trainer on Cooldown while only players
who have beaten it are near.

What is asserted, on tools/route_trainers.files() and placements() over the real data: the tick and load function
tags name cobblers:trainers/tick and /load; the load function creates the clock's objective; the clock, simulated
from the generated lines, runs the cycle every 10 ticks; for every placed trainer (56 seats since the arena's seven
were unseated on 2026-10-03; counted from the seat files) the cycle has exactly
one home line, one tag line, and one cooldown line unless the seat is `repeatable` (none today; the arena's seven
were, and would get the home and tag lines and no cooldown if re-seated), each keyed to that trainer's own
TrainerId, seat and
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
# Seats marked `repeatable` in data/route_trainers.json (the arena's seven tiers, the owner 2026-10-01: plain
# standalone fights, endlessly repeatable). They deliberately get NO cooldown line -- our Cooldown merge is the only
# thing that refuses a rematch with a trainer we place -- so the cooldown tests run on the fight-once seats and
# the complement below asserts the absence.
REPEATABLE = {s["id"] for s in SEATS if s.get("repeatable")}
FIGHT_ONCE = [(t, s, y) for t, s, y in PLACED if t not in REPEATABLE]
FIGHT_ONCE_IDS = [t for t, _s, _y in FIGHT_ONCE]
REPEATABLE_SEATS = [(t, s, y) for t, s, y in PLACED if t in REPEATABLE]
REPEATABLE_IDS = [t for t, _s, _y in REPEATABLE_SEATS]


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
        elif re.match(r"(title|tp) @a\[x=-?\d+,y=-?\d+,z=-?\d+,dx=\d+,dy=\d+,dz=\d+,tag=!cobblers_beat_arena_tier_\d_champion,", l):
            # Heaven's Arena's climb gate (2026-10-03, data/arena_trainers.json gate_why): asserted on its own in
            # test_every_arena_tier_gates_its_shaft_once, not a kind every trainer has
            continue
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
    # 13 route + 28 late route (seated 2026-09-30) + 5 mansion guardians + 10 Victory Road + the arena's seated
    # tiers. Was 18, then 28, then 56, then 63 with the arena's seven (2026-10-01), and 56 again since 2026-10-03:
    # the owner retired the spire's battles ("leave current spire, but remove the trainer battles, have the middle
    # just be hubs"), so every data/arena_trainers.json record carries `seated: false` and its old stand under
    # `superseded_seat`, and its team became a rank-up exam spawned per player by tools/arena_runtime.py. The count
    # is read from the seat files, not written down, so re-seating a champion moves it back without an edit here.
    # Every seated one still needs exactly one home and one tag line, and one cooldown line UNLESS its seat is
    # `repeatable` (asserted absent below and in test_a_repeatable_seat_keeps_its_home_and_tag_and_has_no_cooldown).
    import json
    n = lambda f: json.loads((ROOT / "data" / f).read_text(encoding="utf-8"))["trainers"]
    arena = n("arena_trainers.json")
    seated_arena = [t["id"] for t in arena if "seat" in t and t.get("seated", True)]
    want = (len(n("route_trainers.json")) + len(n("late_route_trainers.json")) + len(n("mansion_guardians.json"))
            + len(n("vr_trainers.json")) + len(seated_arena))
    assert len(IDS) == want and len(set(IDS)) == want, (len(IDS), want)
    assert not ({t["id"] for t in arena} - set(seated_arena)) & set(IDS), "an unseated arena champion is placed"
    assert REPEATABLE == {s["id"] for s in SEATS if s.get("repeatable")} and REPEATABLE <= set(IDS), sorted(REPEATABLE)
    home, tags, cool, other = _classify(cycle)
    assert not other, other
    # The eight GYM LEADERS get a cooldown and nothing else, added 2026-09-30 after the owner beat Brock
    # and then started him again by sending a Pokemon at him. They are not ours to move or tag: each is
    # spawned by its gym's own rctmod:trainer_spawner, so there is no seat to send it home to, and its
    # "beaten" test is the gymN_cleared ADVANCEMENT rather than a quest field, so no tag is needed.
    # A leader with a home or a tag line would mean something had started seating them, which is a
    # change this test should catch, not wave through.
    # The Elite Four and the Champion are the same case, found by the sweep straight after the leaders:
    # overrides at the kanto_league template's own spawners, so also absent from placements(). Their
    # beaten test is UPSTREAM's defeat advancement, which Cobbleverse already grants.
    leaders = {"kanto_brock", "kanto_misty", "kanto_ltsurge", "kanto_erika",
               "kanto_koga", "kanto_sabrina", "kanto_blaine", "kanto_giovanni",
               "kanto_league_lorelei", "kanto_league_bruno", "kanto_league_agatha",
               "kanto_league_lance", "kanto_champion_blue"}
    for kind, got in (("home", home), ("tag", tags), ("cooldown", cool)):
        want = sorted((set(IDS) - REPEATABLE) | leaders) if kind == "cooldown" else sorted(IDS)
        assert sorted(got) == want, (kind, sorted(set(want) ^ set(got)))
        assert all(len(v) == 1 for v in got.values()), (kind, {k: len(v) for k, v in got.items() if len(v) != 1})
        assert all(len(set(_selector_ids(v[0])) | {k}) == 1 for k, v in got.items()), kind
    assert not (leaders & set(home)), "a leader has a home line: something is seating them now"
    assert not (leaders & set(tags)), "a leader has a tag line: its beaten test should be the badge advancement"


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


# Without a hold-off at all the trainer rebattles the players who beat it after every restart.
# This asserted the OLD clause, which also required that no untagged player was near -- and that was the
# mixed-progress fault: a pair at different progress got no cooldown and the winner was dragged back in
# (docs/STATE.md, World facts; tests/test_trainer_holdoff_mixed_progress.py reproduces it). A test that
# asserts a bug as correct is worse than no test, so the `unless` term is gone from the pattern and the
# radius and duration checks stay. The trade the interim accepts -- an unbeaten player standing with a
# beaten one must start the fight themselves -- is the owner's call of 2026-09-29, not an accident.
# It runs on the FIGHT-ONCE seats only: a `repeatable` seat has no cooldown line by design, and that
# absence is asserted by the complement below rather than by excusing a missing line here.
@pytest.mark.parametrize("tid,seat,_yaw", FIGHT_ONCE, ids=FIGHT_ONCE_IDS)
def test_the_cooldown_needs_a_tagged_player_near_and_no_untagged_one(cycle, tid, seat, _yaw):
    _h, tags, cool, _o = _classify(cycle)
    (l,) = cool[tid]
    tag = "cobblers_beat_%s" % tid
    m = re.fullmatch(r'execute as @e\[type=rctmod:trainer,[^\]]*nbt=\{TrainerId:"%s"\}\] at @s '
                     r"if entity @a\[distance=\.\.([0-9.]+),tag=%s\] "
                     r"run data merge entity @s \{Cooldown:(\d+)\}" % (re.escape(tid), tag), l)
    assert m, l
    assert "tag=!%s" % tag not in l, (
        "the mixed-progress fault is back: requiring that no unbeaten player is near means a pair at "
        "different progress gets no cooldown and the winner is force-battled again")
    tag_radius = float(re.search(r"@a\[distance=\.\.([0-9.]+)\]", tags[tid][0]).group(1))
    assert float(m.group(1)) == tag_radius
    assert int(m.group(2)) > 10          # outlasts the 10-tick period, so the cooldown never lapses between cycles


# The complement of the test above, and the only thing standing between "endlessly repeatable" and a champion that
# refuses a rematch: without it a later change to cycle_lines() -- or dropping `repeatable` from a seat -- gives the
# arena's tiers our Cooldown merge, and each tier can then be fought once per player per restart, which is the whole
# point of the arena gone. It also asserts what must NOT disappear with the cooldown: the home line (knockback still
# moves a champion pinned at movement speed 0) and the tag line (the per-player defeat field stays the record of
# having taken that tier, which a prize or a lift condition reads).
@pytest.mark.parametrize("tid,seat,_yaw", REPEATABLE_SEATS, ids=REPEATABLE_IDS)
def test_a_repeatable_seat_keeps_its_home_and_tag_and_has_no_cooldown(cycle, files, tid, seat, _yaw):
    home, tags, cool, _o = _classify(cycle)
    assert tid not in cool, "a repeatable seat has a Cooldown line: %s" % cool.get(tid)
    assert not [l for l in cycle if "{Cooldown:" in l and tid in l], "a Cooldown line names %s" % tid
    assert len(home.get(tid, [])) == 1 and len(tags.get(tid, [])) == 1, (home.get(tid), tags.get(tid))
    # rctmod's own per-player limit says the same thing in the mob record: -1 (documented as infinity) for a
    # repeatable seat, 1 for every other, so the data and the cycle cannot disagree about who may be refought
    mob = files["data/rctmod/mobs/trainers/single/%s.json" % tid]
    assert mob["maxTrainerDefeats"] == -1, mob["maxTrainerDefeats"]


# Without it the -1 above could be the default for every seat, which would quietly make every route trainer
# refightable on a spawner block (the documented path route_trainers.py names), and this file's one-line-of-each-kind
# test would not notice.
def test_only_a_repeatable_seat_is_given_an_unlimited_defeat_count(files):
    got = {t: files["data/rctmod/mobs/trainers/single/%s.json" % t]["maxTrainerDefeats"] for t in IDS}
    assert {t for t, v in got.items() if v == -1} == REPEATABLE, sorted(
        {t for t, v in got.items() if v == -1} ^ REPEATABLE)
    assert {v for t, v in got.items() if t not in REPEATABLE} == {1}, sorted(set(got.values()))


# Heaven's Arena (the owner, 2026-10-03: "a player fighting their way up"): each of the seven tiers turns a player in
# the stair shaft above it back to its floor until they carry that tier's tag, in exactly one title and one tp line,
# both on the record's own box and landing, and no other trainer has such a line.
def test_every_arena_tier_gates_its_shaft_once(cycle):
    import json
    every = json.loads((ROOT / "data" / "arena_trainers.json").read_text(encoding="utf-8"))["trainers"]
    # 2026-10-03: the gates went with the seats (the owner: the spire's middle is "just hubs"); a record keeps its
    # old gate under `superseded_seat`, and NO cycle line may still turn a player back on its behalf. Was 14 lines
    # (7 x title + tp); it is now 2 x the records still seated, which the data says is none.
    recs = {r["id"]: r for r in every if "seat" in r and r.get("seated", True)}
    gates = [l for l in cycle if re.match(r"(title|tp) @a\[x=", l)]
    assert len(gates) == 2 * len(recs), gates
    for r in every:
        if r["id"] not in recs:
            assert not [l for l in cycle if "cobblers_beat_%s" % r["id"] in l], r["id"]
    for tid, r in recs.items():
        x, y, z, dx, dy, dz = r["gate"]["box"]
        sel = "@a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d,tag=!cobblers_beat_%s,gamemode=!creative,gamemode=!spectator]" % (
            x, y, z, dx, dy, dz, tid)
        mine = [l for l in gates if sel in l]
        assert [l.split()[0] for l in mine] == ["title", "tp"], (tid, mine)
        lx, ly, lz, yaw = r["gate"]["landing"]
        assert mine[1] == "tp %s %s %s %s %s 0" % (sel, lx, ly, lz, yaw), mine[1]
        assert ly < y, "%s: the landing (feet y%s) must be BELOW the gate box (from y%d): down is never stopped" % (tid, ly, y)
