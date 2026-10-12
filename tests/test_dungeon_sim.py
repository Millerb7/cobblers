"""tools/dungeon_sim.py: the machinery the dungeon difficulty numbers are made of (unit DG-SIM, 2026-10-10).

What is asserted is the simulator's own correctness, never a verdict on a dungeon:

  - one fight worked by hand from the mainline formula (damage per hit, turns, who wins, the HP left), written out in the
    test and not read from the function under test;
  - the pieces a dungeon run adds to battle_sim's fight: HP carried from fight to fight, PP running out into Struggle, recoil
    and drain, a heal event restoring everything, no heal between a boss's stages;
  - agreement with battle_sim on 1v1 duels, so the new loop is checked against the old one on the same Pokemon;
  - the preview of a move having no side effects (battle_sim.damage heals a Water Absorb holder as it merely evaluates);
  - the dungeon's fights read from the GENERATED classes agree with the authored record: boss stages, stand sizes and levels,
    nest counts, the safe room's heal, the ace last;
  - determinism: the same seed gives the same answer, a different seed a different one;
  - the availability parser, the TM badge gate and the cap-to-gym mapping.

Not covered, and it is most of what matters: whether any rate printed by the tool resembles play. The module docstring
lists what is not modelled (items, secondary effects, switching, the foe's real moveset); only playing the dungeon on a
server closes that gap.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import battle_sim as BS  # noqa: E402
import dungeon as DG  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import dungeon_sim as DS  # noqa: E402


@pytest.fixture(scope="module")
def pack():
    try:
        return DS.load_pack()
    except BS.SimError as e:
        pytest.skip(str(e))


@pytest.fixture(scope="module")
def doc():
    return DG.load()


BASE = {"hp": 100, "attack": 100, "defence": 100, "special_attack": 100, "special_defence": 100, "speed": 100}
SYNTH = {
    "bonk": {"power": 100, "category": "Physical", "type": "Normal", "accuracy": 100, "contact": False},
    "struggle": {"power": 50, "category": "Physical", "type": "Normal", "accuracy": 100, "contact": True},
    "ram": {"power": 100, "category": "Physical", "type": "Normal", "accuracy": 100, "contact": True},
    "drain": {"power": 100, "category": "Physical", "type": "Normal", "accuracy": 100, "contact": False},
    "douse": {"power": 100, "category": "Special", "type": "Water", "accuracy": 100, "contact": False},
}
EXTRAS = {"bonk": {"pp": 15}, "struggle": {"pp": 1}, "ram": {"pp": 15, "recoil": (33, 100)},
          "drain": {"pp": 15, "drain": (1, 2)}, "douse": {"pp": 15}}


def synth_pack(real):
    return DS.Pack({}, SYNTH, real.chart, EXTRAS)


def mon(pk, name, types, moveset, *, level=50, ivs=15, ability="none", speed=100, hp=100):
    base = dict(BASE, speed=speed, hp=hp)
    sp = {name: {"name": name, "primaryType": types[0], "secondaryType": types[1] if len(types) > 1 else None,
                 "baseStats": base, "abilities": [ability], "moves": []}}
    m = BS.Mon(sp, name, level, pk.moves, pk.chart, ivs=ivs, ability=ability, moveset=list(moveset))
    return DS.init_pp(pk, m)


# ------------------------------------------------------------------ one fight, by hand

# removing this lets the battle loop drift from the mainline formula without any other test noticing: the damage per hit,
# who moves first, and when the fight ends are all derived here from the formula, not from the code.
def test_a_fight_worked_by_hand(pack):
    pk = synth_pack(pack)
    a = mon(pk, "alpha", ["normal"], ["bonk"])
    b = mon(pk, "beta", ["normal"], ["bonk"])
    # level 50, IV 15, EV 0, base 100: stat = floor((200 + 15) * 50 / 100) + 5 = 112; HP = 107 + 50 + 10 = 167
    assert (a.atk, a.df, a.hp) == (112, 112, 167)
    # the hit: floor(floor(floor(2*50/5 + 2) * 100 * 112 / 112) / 50) + 2 = 46; STAB x1.5 = 69; the average roll 0.925
    hit = 46 * 1.5 * 0.925
    assert hit == pytest.approx(63.825)
    # 167 / 63.825 = 2.6: three hits kill. Equal speed: the player moves first, so beta lands only twice
    res = DS.run_battle([a], [b], DS.Ctx(pk, None))
    assert res.won and res.turns == 3 and res.faints == 0
    assert a.hp_now == pytest.approx(167 - 2 * hit)
    assert res.hp_lost == pytest.approx(2 * hit / 167)
    assert b.hp_now <= 0


# removing this lets the speed order flip: the slower side must lose the race it would otherwise win
def test_the_faster_side_moves_first(pack):
    pk = synth_pack(pack)
    slow = mon(pk, "slow", ["normal"], ["bonk"], speed=10)
    fast = mon(pk, "fast", ["normal"], ["bonk"], speed=200)
    res = DS.run_battle([slow], [fast], DS.Ctx(pk, None))
    assert not res.won and res.faints == 1 and res.killers == ["fast"]
    assert fast.hp_now == pytest.approx(167 - 2 * 46 * 1.5 * 0.925)


# ------------------------------------------------------------------ what a dungeon run adds

# removing this lets every fight start from full health again, which is battle_sim's loop and exactly what a dungeon's
# chain of fights is not
def test_health_is_carried_from_one_fight_to_the_next(pack):
    pk = synth_pack(pack)
    a = mon(pk, "alpha", ["normal"], ["bonk"])
    DS.run_battle([a], [mon(pk, "one", ["normal"], ["bonk"])], DS.Ctx(pk, None))
    after_first = a.hp_now
    assert after_first < a.hp
    # a frail second foe (level 10: 23 HP) dies to the first 63.8 hit, and alpha moves first: it takes nothing more, and
    # nothing is given back either
    r2 = DS.run_battle([a], [mon(pk, "two", ["normal"], ["bonk"], level=10)], DS.Ctx(pk, None))
    assert r2.won and r2.turns == 1 and r2.hp_lost == 0.0
    assert a.hp_now == pytest.approx(after_first) and a.hp_now < a.hp
    # a level-30 foe survives alpha's first hit (defence floor(215*30/100)+5 = 69: floor(floor(22*100*112/69)/50)+2 = 73,
    # STAB and the roll make 101.3 against its 104 HP) and lands one itself: floor(floor(14*100*69/112)/50)+2 = 19, STAB 1.5,
    # the average roll, taken from alpha's carried health. Alpha's second hit ends it.
    r3 = DS.run_battle([a], [mon(pk, "three", ["normal"], ["bonk"], level=30)], DS.Ctx(pk, None))
    assert r3.won and r3.turns == 2
    assert a.hp_now == pytest.approx(after_first - 19 * 1.5 * 0.925)


# removing this lets a fainted Pokemon fight on, or the heal skip PP and status
def test_a_heal_restores_health_pp_status_and_revives(pack):
    pk = synth_pack(pack)
    a = mon(pk, "alpha", ["normal"], ["bonk"])
    b = mon(pk, "beta", ["normal"], ["bonk"])
    a.hp_now, a.status, a.pp["bonk"] = 0.0, "par", 2
    b.hp_now = 5.0
    DS.heal_party([a, b])
    assert a.hp_now == a.hp and b.hp_now == b.hp and a.status is None and a.pp["bonk"] == 15


# removing this lets a spent move stay playable: a dungeon is long, and the PP of a 5-PP move is part of its cost
def test_pp_runs_out_into_struggle(pack):
    pk = synth_pack(pack)
    a = mon(pk, "alpha", ["normal"], ["bonk"])
    d = mon(pk, "dummy", ["normal"], ["bonk"], hp=250)
    assert DS.usable(a) == ["bonk"]
    a.pp["bonk"] = 1
    DS._attack(a, d, "bonk", 10.0, DS.Ctx(pk, None), BS.Field())
    assert a.pp["bonk"] == 0 and DS.usable(a) == ["struggle"]


# removing this lets Double-Edge cost nothing and Giga Drain heal nothing
def test_recoil_and_drain_apply_to_the_user(pack):
    pk = synth_pack(pack)
    d = mon(pk, "dummy", ["normal"], ["bonk"], hp=500)
    a = mon(pk, "alpha", ["normal"], ["ram"])
    DS._attack(a, d, "ram", 100.0, DS.Ctx(pk, None), BS.Field())
    assert a.hp_now == pytest.approx(a.hp - 33.0)                         # a third of the 100 dealt
    b = mon(pk, "beta", ["normal"], ["drain"])
    b.hp_now = 50.0
    d2 = mon(pk, "dummy2", ["normal"], ["bonk"], hp=500)
    DS._attack(b, d2, "drain", 80.0, DS.Ctx(pk, None), BS.Field())
    assert b.hp_now == pytest.approx(50.0 + 40.0)                         # half the 80 dealt


# removing this lets a fight start from a healed team although no heal event stands before it, and lets a heal event do
# nothing (the boss chain's own heal is such an event: test_what_ifs_change_only_what_they_name_and_leave_the_input_alone)
def test_health_carries_between_fights_unless_a_heal_event_stands_between_and_a_heal_event_restores(pack, monkeypatch):
    team = [DS.make_player(pack, "machamp", 30, None, "tm", 2), DS.make_player(pack, "gengar", 30, None, "tm", 2)]
    seen = []
    real = DS.run_battle

    def spy(t, foes, ctx):
        start = sum(m.hp_now for m in t)
        r = real(t, foes, ctx)
        seen.append((start, sum(m.hp_now for m in t)))
        return r
    monkeypatch.setattr(DS, "run_battle", spy)
    events = [DS.event("fight", "boss stage 1", "arena", [("onix", 28), ("geodude", 29)], "boss", stage=1),
              DS.event("fight", "boss stage 2", "arena", [("graveler", 29), ("golem", 30)], "boss", stage=2),
              DS.event("heal", "a heal", "cabin", [], "heal"),
              DS.event("fight", "after", "x", [("rattata", 10)], "stand")]
    out = DS.run_sequence(team, events, DS.Ctx(pack, None), "smart")
    assert len(seen) == 3 or not out["cleared"]
    # stage 2 began with exactly the health stage 1 left: no heal event stood between them in THIS sequence
    assert seen[1][0] == pytest.approx(seen[0][1])
    assert seen[0][0] == sum(m.hp for m in team)
    if len(seen) == 3:
        # the heal event ran: the last fight began from a full team
        assert seen[2][0] == pytest.approx(sum(m.hp for m in team))


# ------------------------------------------------------------------ the previews

# removing this lets merely EVALUATING a move heal a Water Absorb holder (battle_sim.damage does, as a side effect), so
# the choice of move would change the defender's health
def test_previewing_a_move_has_no_side_effects(pack):
    pk = synth_pack(pack)
    att = mon(pk, "att", ["normal"], ["douse"])
    absorber = mon(pk, "wet", ["normal"], ["bonk"], ability="waterabsorb")
    absorber.hp_now = absorber.hp - 40.0
    before = absorber.hp_now
    assert DS.preview(att, absorber, "douse", DS.Ctx(pk, None), BS.Field()) == 0.0
    assert absorber.hp_now == before
    assert BS.damage(att, absorber, "douse", pk.moves, pk.chart) == 0.0
    assert absorber.hp_now > before, "the premise (battle_sim heals on evaluation) no longer holds: revisit DS.preview"


# ------------------------------------------------------------------ against battle_sim

# removing this lets the new loop disagree with the old one on the simplest case, where both claim the same arithmetic
@pytest.mark.parametrize("a,b,level", [("pikachu", "wingull", 30), ("machop", "geodude", 20), ("bulbasaur", "charmander", 15),
                                       ("onix", "squirtle", 25), ("gastly", "abra", 20), ("arcanine", "golem", 50)])
def test_one_on_one_agrees_with_battle_sim(pack, a, b, level):
    pa = BS.Mon(pack.species, a, level, pack.moves, pack.chart)
    pb = BS.Mon(pack.species, b, level, pack.moves, pack.chart)
    winner, turns = BS.duel(pa, pb, pack.moves, pack.chart, species=pack.species)
    ma = DS.init_pp(pack, BS.Mon(pack.species, a, level, pack.moves, pack.chart))
    mb = DS.init_pp(pack, BS.Mon(pack.species, b, level, pack.moves, pack.chart))
    res = DS.run_battle([ma], [mb], DS.Ctx(pack, None))
    assert res.won == (winner is not None and winner.name == BS.key(a)), (a, b, winner, res.won)
    if winner is not None:
        assert res.turns == turns


# ------------------------------------------------------------------ the dungeon's fights read from generated data

def _band(doc, n):
    return next(b for b in doc["engine"]["bands"] if b["band"] == n)


# removing this lets the events drift from the record: the boss's stages and crews are read back from the authored teams,
# the ace last at the stage level and the crew one level under (member_level_offset)
def test_boss_events_match_the_authored_crews(doc):
    for d in doc["dungeons"]:
        bo = d["boss"]
        for b in doc["engine"]["bands"]:
            ev = [e for e in DS.dungeon_paths(doc, d, b["band"])["paths"][0][1] if e["category"] == "boss"]
            assert len(ev) == len(bo["stage_level_offsets"]) == 2     # two stages (the owner, 2026-10-10)
            for k, e in enumerate(ev):
                crew = bo["teams"][str(b["band"])][k]
                assert [s for s, _l in e["foes"]] == crew
                ace = min(b["caps"]) + bo["stage_level_offsets"][k]
                assert e["foes"][-1][1] == ace
                assert all(l == ace + bo["member_level_offset"] for _s, l in e["foes"][:-1])
                assert ace <= max(b["caps"])


def _trainers(node):
    """Every trainer record (a dict with a team_by_band, or a rotation pool's team_pool_by_band, PRIZE-POOLS) anywhere under
    a dungeon record."""
    if isinstance(node, dict):
        if "team_by_band" in node or "team_pool_by_band" in node:
            yield node
        for v in node.values():
            yield from _trainers(v)
    elif isinstance(node, list):
        for v in node:
            yield from _trainers(v)


# removing this lets a stand seat the wrong number of members or a level above the cap it is built against
def test_stand_events_have_the_band_sizes_and_stay_under_the_cap(doc):
    st = doc["engine"]["stands"]
    for d in doc["dungeons"]:
        for b in doc["engine"]["bands"]:
            lo = min(b["caps"])
            for label, seq in DS.dungeon_paths(doc, d, b["band"])["paths"]:
                for e in seq:
                    if e["category"] not in ("stand", "gauntlet"):
                        continue
                    # the band's size less the trainer's declared easing (members_eased_by_band, the 2026-10-10 tuning)
                    # a rotating stand's label ends " [team k/n]" (tools/dungeon_sim.py room_events, PRIZE-POOLS)
                    name = re.sub(r" \[team \d+/\d+\]$", "", e["label"].split(": ", 1)[1])
                    eased = max(int((t.get("members_eased_by_band") or {}).get(str(b["band"]), 0)) for t in _trainers(d)
                                if t["name"] == name)
                    assert len(e["foes"]) == st["members_by_band"][str(b["band"])] - eased, (d["id"], b["band"], e["label"])
                    lv = [l for _s, l in e["foes"]]
                    assert lv == sorted(lv)
                    if b["band"] == 6:
                        assert st["band6_levels"][0] <= lv[0] and lv[-1] <= st["band6_levels"][1]
                    else:
                        assert lv[0] == lo - st["low_offset"] and lv[-1] == lo - st["high_offset"] < lo


# removing this lets a nest or a miniboss read the wrong band's count or level
def test_wild_events_match_the_record(doc):
    for d in doc["dungeons"]:
        items = {it["rec"]["id"]: it["rec"] for it in R.flatten(d)}
        for b in doc["engine"]["bands"]:
            up = max(b["caps"])
            pe = DS.dungeon_paths(doc, d, b["band"])
            everything = [e for _l, seq in pe["paths"] for e in seq] + pe["optional"]
            for rid, rec in items.items():
                p = rec.get("params") or {}
                if rec["kind"] == "nest" and isinstance(p.get("species"), list):
                    got = {e["label"] for e in everything if e["room"] == rid}
                    assert len(got) == p["count_by_band"][str(b["band"])], (d["id"], rid, b["band"])
                if rec["kind"] == "miniboss" and "species_by_band" in p:
                    got = [e for e in everything if e["room"] == rid]
                    assert len(got) >= 1 and got[0]["foes"][0] == (p["species_by_band"][str(b["band"])], up + p.get("level_offset", 0))


# removing this lets a prize fight be built at a level the ball refusal would turn away: it is the band's LOWER cap
def test_the_prize_is_a_rare_below_the_beast_ball_band_and_a_legendary_from_it(doc):
    start = doc["engine"]["prize"]["legendary_from_band"]
    for d in doc["dungeons"]:
        for b in doc["engine"]["bands"]:
            prize = [e for e in DS.dungeon_paths(doc, d, b["band"])["optional"] if e["category"] == "prize"]
            for e in prize:
                assert e["optional"] and e["foes"][0][1] == min(b["caps"])
                assert e["legendary"] == (b["band"] >= start)


# removing this lets a heal event go missing: the safe room's heal and the boss chain's (one between the stages) are the run's heals
def test_every_dungeon_path_passes_one_heal_before_the_boss(doc):
    for d in doc["dungeons"]:
        homes = [it["rec"] for it in R.flatten(d) if it["rec"]["kind"] == "safe_room" and (it["rec"].get("params") or {}).get("healer")]
        for label, seq in DS.dungeon_paths(doc, d, 1)["paths"]:
            heals = [i for i, e in enumerate(seq) if e["kind"] == "heal"]
            boss = [i for i, e in enumerate(seq) if e["category"] == "boss"]
            # the safe room's heal comes before the boss; the boss chain's own heal (one between each pair of stages,
            # from the record's heal_between_stages) is the only heal after it
            chain = len(boss) - 1 if d["boss"].get("heal_between_stages") else 0
            assert len(heals) == len(homes) + chain and len(homes) >= 1
            assert sorted(heals)[:len(homes)] == [i for i in heals if i < min(boss)] and len([i for i in heals if i < min(boss)]) == len(homes)
            assert all(min(boss) < i < max(boss) for i in heals if i > min(boss))
            assert seq[-1]["category"] == "boss"


# removing this lets an optional wing leak into the required sequence, which would also be what the clock pays for
def test_optional_fights_stay_out_of_the_required_sequence(doc):
    for d in doc["dungeons"]:
        for b in doc["engine"]["bands"]:
            pe = DS.dungeon_paths(doc, d, b["band"])
            for _l, seq in pe["paths"]:
                assert not [e for e in seq if e["optional"]]
                assert not [e for e in seq if e["category"] == "prize"]


# ------------------------------------------------------------------ determinism

OPTS = {"samples": 2, "reps": 1, "under": 0, "moves": "tm", "foe_moves": "smart", "seed": "t1", "bag": 0}


# removing this lets a run depend on hash order or the clock: the same seed must give the same cell, bit for bit
def test_the_same_seed_gives_the_same_cell_and_another_seed_another(pack, doc):
    d = doc["dungeons"][0]
    b = _band(doc, 1)
    one = DS.run_cell(doc, d, b, 20, OPTS)
    two = DS.run_cell(doc, d, b, 20, OPTS)
    assert json.dumps(one["runs"], sort_keys=True) == json.dumps(two["runs"], sort_keys=True)
    other = DS.run_cell(doc, d, b, 20, dict(OPTS, seed="t2"))
    assert json.dumps(one["runs"], sort_keys=True) != json.dumps(other["runs"], sort_keys=True)


# removing this lets the what-if comparison stop being paired: the unchanged base transform must reproduce the base run
def test_a_what_if_runs_the_same_teams(pack, doc):
    d = doc["dungeons"][0]
    b = _band(doc, 1)
    base = DS.run_cell(doc, d, b, 20, OPTS)
    changed = DS.run_cell(doc, d, b, 20, dict(OPTS, whatif="boss -1 member"))
    assert [r["team"] for r in base["runs"]] == [r["team"] for r in changed["runs"]]
    assert DS.summarise(changed)["win"] >= 0.0


# ------------------------------------------------------------------ the inputs

# removing this lets the committed availability tables stop parsing into eight cumulative lists
def test_availability_parses_into_eight_cumulative_gyms():
    av = DS.availability()
    assert sorted(av) == list(range(1, 9))
    sizes = [len(av[g]) for g in range(1, 9)]
    assert sizes == sorted(sizes) and sizes[0] > 20
    assert "bulbasaur" in {r["species"] for r in av[1]}
    assert {r["species"] for r in av[1]} <= {r["species"] for r in av[8]}


def test_the_cap_to_gym_and_badge_mapping():
    assert [DS.gym_of_cap(c) for c in (20, 25, 55, 60, 62, 100)] == [1, 2, 8, 8, 8, 8]
    assert [DS.badges_of_cap(c) for c in (20, 25, 30, 55, 60, 100)] == [0, 1, 2, 7, 8, 8]


# removing this lets a TM be played before its gate badge: the gate is TM_POWER_GATE.json's power_badge
def test_players_only_carry_tms_their_badges_allow(pack):
    gate = DS.tm_badges()
    assert gate["earthquake"] >= 1
    for cap in (25, 40, 55):
        badges = DS.badges_of_cap(cap)
        for name in ("machop", "pikachu", "onix", "gengar"):
            sp = pack.species[name]
            ids = DS.candidate_moves(pack, sp, cap, "tm", badges)
            lvl = set(BS.level_moves(sp, cap))
            for mid in ids:
                assert mid in lvl or gate.get(mid, 99) <= badges, (name, cap, mid)
            floor = DS.candidate_moves(pack, sp, cap, "levelup", badges)
            assert set(floor) <= set(ids)


# removing this lets a move the loop cannot play be carried by a player: charge turns, recharge and self-destruct
def test_a_player_never_carries_a_move_the_loop_cannot_play(pack):
    for name in ("snorlax", "golem", "electabuzz", "venusaur", "gengar", "kabutops"):
        ms = DS.player_moveset(DS.pack_id(pack), name, 60, "tm", 8)
        for mid in ms:
            assert mid not in DS.UNPLAYABLE and not pack.extras.get(mid, {}).get("unplayable"), (name, mid)
    for mid in ("hyperbeam", "solarbeam", "explosion", "gigaimpact"):
        assert pack.extras[mid].get("unplayable"), mid


# removing this lets multi-hit moves count one hit, which understates every Bullet Seed and Icicle Spear
def test_multi_hit_and_the_extras_are_read_from_the_jar(pack):
    assert pack.extras["bulletseed"]["hits"] == 3.1
    assert pack.moves["bulletseed"]["power"] == pytest.approx(25 * 3.1)
    assert pack.raw_moves["bulletseed"]["power"] == 25
    assert pack.extras["doubleedge"]["recoil"] == (33, 100)
    assert pack.extras["gigadrain"]["drain"] == (1, 2)
    assert pack.extras["seismictoss"]["fixed"] == "level"
    assert pack.extras["flamethrower"]["pp"] == 15


# ------------------------------------------------------------------ the readings

# removing this lets the cut-offs drift unseen: they are stated in the report, so the tests state them too
def test_classification_and_clock_verdict_cutoffs():
    assert DS.classify({"win": 0.0, "win_scouted": 0.0, "hp_lost": 0.9}) == "IMPOSSIBLE"
    assert DS.classify({"win": 0.0, "win_scouted": 0.5, "hp_lost": 0.9}) == "hard"
    assert DS.classify({"win": 0.4, "win_scouted": 1.0, "hp_lost": 0.9}) == "hard"
    assert DS.classify({"win": 1.0, "win_scouted": 1.0, "hp_lost": 0.05}) == "trivial"
    assert DS.classify({"win": 1.0, "win_scouted": 1.0, "hp_lost": 0.30}) == "ok"
    assert DS.clock_verdict(1.20, 1.25) == "TIGHT"
    assert DS.clock_verdict(1.25, 1.25) == "ok"
    assert DS.clock_verdict(1.90, 1.25) == "loose"


# removing this lets the bag spend a use between boss stages or revive a Pokemon without cost
def test_the_bag_revives_first_and_heals_only_a_hurt_team(pack):
    pk = synth_pack(pack)
    a, b, c = (mon(pk, n, ["normal"], ["bonk"]) for n in "abc")
    a.hp_now = 0.0
    assert DS.use_bag([a, b, c], 5) == 1 and a.hp_now == pytest.approx(a.hp * 0.5)
    b.hp_now, c.hp_now = b.hp * 0.2, c.hp * 0.9
    n = DS.use_bag([a, b, c], 5)
    assert n == 1 and b.hp_now == b.hp and c.hp_now == pytest.approx(c.hp * 0.9)
    assert DS.use_bag([a, b, c], 0) == 0


# ------------------------------------------------------------------ the what-ifs

# removing this lets a what-if change the wrong fights, or the input: each is a pure transform of the event list
def test_what_ifs_change_only_what_they_name_and_leave_the_input_alone(doc):
    d = next(x for x in doc["dungeons"] if x["id"] == "night_shift")
    seq = DS.dungeon_paths(doc, d, 3)["paths"][0][1]
    snapshot = json.dumps(seq, sort_keys=True, default=list)
    boss = [e for e in seq if e["category"] == "boss"]
    cut = [e for e in DS.WHATIFS["boss -1 member"](seq) if e["category"] == "boss"]
    assert [len(e["foes"]) for e in cut] == [len(e["foes"]) - 1 for e in boss]
    assert [e["foes"][-1] for e in cut] == [e["foes"][-1] for e in boss]            # the ace stays
    low = [e for e in DS.WHATIFS["boss -2 levels"](seq) if e["category"] == "boss"]
    assert [[l for _s, l in e["foes"]] for e in low] == [[l - 2 for _s, l in e["foes"]] for e in boss]
    # the record heals between the two stages already (boss.heal_between_stages): the what-if adds none, and the
    # base sequence has exactly one heal between the stages and none right before the first or after the last
    assert d["boss"]["heal_between_stages"] is True
    bidx = [i for i, e in enumerate(seq) if e["category"] == "boss"]
    assert len(bidx) == 2 and seq[bidx[1] - 1]["kind"] == "heal" and seq[bidx[0] - 1]["kind"] != "heal"
    assert bidx[1] == bidx[0] + 2 and seq[-1]["category"] == "boss"
    healed = DS.WHATIFS["heal between boss stages"](seq)
    assert [e["kind"] for e in healed] == [e["kind"] for e in seq], "a heal already stands before stage 2"
    # without the record's heal the what-if inserts one before stage 2 only
    bare = [e for i, e in enumerate(seq) if i != bidx[1] - 1]
    again = DS.WHATIFS["heal between boss stages"](bare)
    stages = [i for i, e in enumerate(again) if e["category"] == "boss"]
    assert len(again) == len(bare) + 1 and again[stages[1] - 1]["kind"] == "heal"
    assert healed[stages[0] - 1]["kind"] != "heal"
    stands = [e for e in DS.WHATIFS["stands -1 member"](seq) if e["category"] in ("stand", "gauntlet")]
    assert all(len(a["foes"]) == len(b["foes"]) - 1 for a, b in zip(stands, [e for e in seq if e["category"] in ("stand", "gauntlet")]))
    assert json.dumps(seq, sort_keys=True, default=list) == snapshot


# removing this lets the second heal land after the boss, or twice in the same gap
def test_the_midfield_heal_sits_in_the_fights_before_the_boss_once(doc):
    for d in doc["dungeons"]:
        seq = DS.dungeon_paths(doc, d, 1)["paths"][0][1]
        out = DS._midfield_heal(seq)
        first_boss = next(i for i, e in enumerate(out) if e["category"] == "boss")
        new = [i for i, e in enumerate(out) if e["kind"] == "heal" and "what-if" in e["label"]]
        assert len(new) <= 1 and all(i < first_boss for i in new)
        assert not any(out[i]["kind"] == "heal" and out[i + 1]["kind"] == "heal" for i in range(len(out) - 1))
        assert [e for e in out if e["kind"] == "fight"] == [e for e in seq if e["kind"] == "fight"]
