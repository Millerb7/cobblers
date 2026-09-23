"""tools/battle_sim.py: the parsers and the arithmetic the gym numbers are made of.

The report this tool prints is a deliverable, so what is asserted here is the machinery under it, never a
verdict. Three things would silently poison every number in the report and none of them is visible in the
output: a type chart row that failed to parse (a missing row reads as neutral, so a Water defender would
look neutral to Electric -- this really happened, the last entry of each Showdown file has no trailing
comma), a move whose power or accuracy was misread, and a species name that normalised to an id the jar does
not have. Those are checked against the real jar. The damage formula, STAB, the type multiplier, Sturdy and
the gauntlet's carry-forward are checked on synthetic Pokemon with stats written out here, and the expected
damage is derived from the formula spelled out in the test rather than from the function under test.

The real data is checked only for the shape the tool depends on: eight gym leaders, one of them (gym 8,
`status: held`) with no roster, and eight gyms of availability rows that all resolve to species. A row that
resolves to nothing has to be counted in `assess`'s `unresolved` list rather than dropped, because a pool
that shrank silently reads exactly like a pool that was always narrow, and that is the one reading the tool
exists to give.

Not covered, and it is most of what matters about a battle:
  - whether any of these numbers resemble play. The module docstring of the tool lists its own omissions --
    no switching, no items, no status moves, no secondary effects, no crits, almost no abilities -- and no
    pytest can close that gap. Only playing a gym can.
  - whether Cobblemon's own battle engine computes damage this way. The formula here is the standard
    mainline one; that Showdown-in-Cobblemon agrees with it at these levels is unverified.
  - move legality: choose_moveset picks from the jar's level-up list only, so tutor, TM, egg and event moves
    are invisible, and nothing here checks that a leader's authored moveset is learnable at all.
  - the report itself: the markdown, the team-picking heuristics, the ace-chip accounting and the printed
    `!!` line for unresolved rows are exercised by no test, only by reading the output. What is checked is
    the `unresolved` list `assess` returns, not that main() prints it.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import battle_sim as B  # noqa: E402


# ------------------------------------------------------------------ the jar, loaded once

@pytest.fixture(scope="module")
def pack():
    """(species, moves, chart) from the Cobblemon 1.8 jar, or a skip.

    Module-scoped on purpose: unzipping a thousand species files and two Showdown data files takes a couple
    of seconds, and every jar-backed test in this file shares the one result.
    """
    try:
        jar = B.find_jar()
    except B.SimError as e:
        pytest.skip(str(e))
    return B.load_pack(jar)


@pytest.fixture(scope="module")
def chart(pack):
    return pack[2]


# ------------------------------------------------------------------ the type chart

# removing this lets a type row go missing again. A row that does not parse is not an error anywhere: every
# defender of that type silently reads neutral, so a Water gym leader would look like it had no weakness and
# the whole report would still print clean numbers. `water` is the last entry in typechart.js, which is the
# one with no trailing comma, which is exactly the row an earlier regex dropped.
def test_the_type_chart_parses_all_eighteen_types_including_the_last_row_of_the_file(chart):
    assert len(chart) == 18, sorted(chart)
    assert set(chart) == {"bug", "dark", "dragon", "electric", "fairy", "fighting", "fire", "flying",
                          "ghost", "grass", "ground", "ice", "normal", "poison", "psychic", "rock",
                          "steel", "water"}
    assert chart["water"], "the water row parsed empty: every Water defender would read neutral"
    assert chart["water"]["Electric"] == 2.0 and chart["water"]["Grass"] == 2.0


# removing this lets the chart parse eighteen rows that mean the wrong thing -- Showdown encodes 1 as weak
# and 2 as resist, which is the opposite of the reading a person expects, and inverting it would make every
# gym look answerable by the type it is strong against.
def test_effectiveness_reads_double_weakness_resistance_and_immunity(chart):
    assert B.effectiveness(chart, "Electric", ["water", "flying"]) == 4.0
    assert B.effectiveness(chart, "Fighting", ["rock", "steel"]) == 4.0
    assert B.effectiveness(chart, "Ground", ["electric"]) == 2.0        # Raichu
    assert B.effectiveness(chart, "Electric", ["ground"]) == 0.0
    assert B.effectiveness(chart, "Normal", ["ghost"]) == 0.0
    assert B.effectiveness(chart, "Fighting", ["ghost"]) == 0.0
    assert B.effectiveness(chart, "Water", ["fire"]) == 2.0
    assert B.effectiveness(chart, "Water", ["water"]) == 0.5
    assert B.effectiveness(chart, "Water", ["normal"]) == 1.0
    assert B.effectiveness(chart, "Grass", ["water", "flying"]) == 1.0   # 2x into Water, 0.5x into Flying
    assert B.effectiveness(chart, "Dragon", ["fairy"]) == 0.0


# removing this lets a typo or a new type read as neutral instead of stopping: a defender whose row is not in
# the chart would quietly become immune to nothing and weak to nothing, which is the failure mode the whole
# tool is least able to notice from its output.
def test_effectiveness_refuses_an_unknown_defender_type(chart):
    with pytest.raises(B.SimError):
        B.effectiveness(chart, "Electric", ["plastic"])
    with pytest.raises(B.SimError):
        B.effectiveness(chart, "Electric", ["Water", "Sound"])


# ------------------------------------------------------------------ moves

# removing this lets the move regex drop most of the file and nobody notices: the tool only refuses under 500
# moves, and a parse that lost half the level-up pool would still build movesets, just worse ones. zippyzap is
# the last entry in moves.js -- the one with no trailing comma.
def test_move_parsing_reads_power_category_accuracy_and_the_last_move_in_the_file(pack):
    _species, moves, _chart = pack
    assert len(moves) > 900, len(moves)
    assert moves["rockslide"] == {"power": 75, "category": "Physical", "type": "Rock", "accuracy": 90}
    assert moves["thunderbolt"]["power"] == 90 and moves["thunderbolt"]["category"] == "Special"
    assert moves["earthquake"]["power"] == 100 and moves["earthquake"]["type"] == "Ground"
    assert "zippyzap" in moves, "the last move in moves.js was dropped: the trailing-comma bug is back"


# removing this lets a status move arrive with a power, which would make choose_moveset carry Stealth Rock as
# an attack and every leader that sets hazards look like it has an extra damaging move.
def test_a_status_move_parses_with_no_power(pack):
    _species, moves, chart = pack
    assert moves["stealthrock"]["category"] == "Status"
    assert moves["stealthrock"]["power"] == 0
    assert moves["swordsdance"]["power"] == 0 and moves["protect"]["power"] == 0
    # and a zero-power move deals nothing, so it can never be chosen as a best damaging move
    rocky = _M(moves, chart, "rocky", ["rock"], moveset=["stealthrock"])
    target = _M(moves, chart, "target", ["normal"], moveset=[])
    assert B.damage(rocky, target, "stealthrock", moves, chart) == 0.0
    assert B.best_damage(rocky, target, moves, chart) == (0.0, None)


# removing this lets `accuracy: true` (a move that cannot miss) crash the int() or, worse, parse as accuracy 1
# and make Swift and Aerial Ace deal one per cent of their damage.
def test_a_never_miss_move_parses_as_accuracy_one_hundred(pack):
    _species, moves, _chart = pack
    assert moves["swift"]["accuracy"] == 100
    assert moves["aerialace"]["accuracy"] == 100
    assert moves["shadowpunch"]["accuracy"] == 100
    assert all(1 <= m["accuracy"] <= 100 for m in moves.values())


# ------------------------------------------------------------------ species names

# removing this lets a name with punctuation stop resolving. Mr. Mime, Farfetch'd and Ho-Oh all appear in
# authored rosters or availability tables, and a key() that no longer strips the stop, the apostrophe or the
# hyphen would make them vanish from the candidate list with no message at all.
def test_species_keys_normalise_punctuation_to_ids_the_jar_actually_has(pack):
    species, _moves, _chart = pack
    for name, want in [("Mr. Mime", "mrmime"), ("Farfetch'd", "farfetchd"), ("Ho-Oh", "hooh"),
                       ("Porygon-Z", "porygonz"), ("Type: Null", "typenull"), ("Mime Jr.", "mimejr")]:
        assert B.key(name) == want, name
        assert want in species, "%s normalises to %r, which the jar does not have" % (name, want)
    assert B.key("PIKACHU") == B.key("pikachu") == "pikachu"
    assert B.key(None) == "" and B.key("") == ""


# removing this lets a roster entry whose species does not exist be skipped instead of reported: a gym leader
# would quietly field five Pokemon instead of six and the report would still look complete.
def test_a_roster_species_that_resolves_to_nothing_raises(pack):
    species, moves, chart = pack
    with pytest.raises(B.SimError):
        B.Mon(species, "definitelynotapokemon", 30, moves, chart)
    bogus = {"class": "gym_leader", "order": 1, "status": "authored",
             "team": [{"species": "definitelynotapokemon", "level": 30}]}
    with pytest.raises(B.SimError):
        B.build_leader(bogus, species, moves, chart, 15, False)


# removing this lets an authored roster drift onto a name the jar does not have -- a rename, a regional form,
# a typo -- and the tool would refuse to run at all the next time anyone asked for the report.
def test_every_authored_gym_roster_builds_against_the_jar(pack):
    species, moves, chart = pack
    leaders, _contract = B.gym_leaders()
    for order, t in sorted(leaders.items()):
        if not t["team"]:
            continue
        team = B.build_leader(t, species, moves, chart, 15, False)
        assert len(team) == len(t["team"]), order
        for m in team:
            assert m.types, "%s (gym %d) has no types" % (m.name, order)
            assert m.hp > 0


# removing this lets the gender signs be dropped again rather than mapped. Stripping them collapses Nidoran(f)
# and Nidoran(m) onto "nidoran", which is not a species id at all -- the jar has nidoranf and nidoranm -- and
# the availability ROW regex has to accept the signs too or both rows of Gym 8's table never reach key().
# Until 2026-09-24 both were broken and Gym 8's pool was two species short with nothing said. The two species
# are distinct, so the test asserts they stay distinct and not merely that each resolves to something.
def test_the_gendered_nidoran_rows_reach_two_distinct_species(pack):
    species, _moves, _chart = pack
    f, m = B.key("Nidoran♀"), B.key("Nidoran♂")
    assert (f, m) == ("nidoranf", "nidoranm")
    assert f in species and m in species and f != m
    assert species[f]["name"] != species[m]["name"]
    rows = B.parse_availability(B.AVAILABILITY)[8]["rows"]
    gendered = sorted(r["species"] for r in rows if r["species"].startswith("Nidoran"))
    assert gendered == ["Nidoran♀", "Nidoran♂"], gendered
    assert len(rows) == 98, "Gym 8's pool is %d rows, not the 98 the tables list" % len(rows)


# removing this lets a candidate the jar does not know be dropped in silence again, which is what hid the
# Nidoran defect: a pool that shrank because a name stopped resolving reads exactly like a pool that was
# always that narrow, and the whole point of the tool is to say how many answers a gym has.
def test_a_candidate_the_jar_does_not_know_is_counted_not_dropped(pack):
    species, moves, chart = pack
    avail = {1: {"leader": "kanto_brock", "theme": "Rock",
                 "rows": [{"species": "Pidgey", "lo": 5, "hi": 8, "corridor": "test"},
                          {"species": "Notapokemon", "lo": 5, "hi": 8, "corridor": "test"},
                          {"species": "Nidoran♀", "lo": 5, "hi": 8, "corridor": "test"}]}}
    leaders = {1: {"class": "gym_leader", "order": 1, "status": "authored",
                   "team": [{"species": "geodude", "level": 12}]}}
    out = B.assess(1, avail, leaders, species, moves, chart, 15, False, (20, 5))
    assert out["unresolved"] == ["Notapokemon"], out["unresolved"]
    used = {c["caught_as"] for c in out["candidates"]}
    assert "Pidgey" in used and "Nidoran♀" in used, used
    assert "Notapokemon" not in used
    assert len(out["candidates"]) + len(out["unresolved"]) == len(avail[1]["rows"]), \
        "rows went missing from both the pool and the unresolved list"


# removing this lets the real availability tables drift onto a name the jar cannot resolve without the report
# saying so anywhere a reader would look. Every gym that has a roster to simulate must resolve every row.
def test_no_real_availability_row_is_unresolved_for_any_gym_with_a_roster(pack):
    species, moves, chart = pack
    avail = B.parse_availability(B.AVAILABILITY)
    leaders, _contract = B.gym_leaders()
    caps = B.level_caps(B.RCT_CONFIG)
    for g in sorted(avail):
        out = B.assess(g, avail, leaders, species, moves, chart, 15, False, caps)
        if not out.get("foes"):                       # gym 8 is held: no roster, so nothing is assessed
            assert g == 8 and not out["candidates"]
            continue
        assert out["unresolved"] == [], "gym %d: %s" % (g, out["unresolved"])
        assert len(out["candidates"]) == len(avail[g]["rows"]), \
            "gym %d turned %d rows into %d candidates" % (g, len(avail[g]["rows"]), len(out["candidates"]))


# ------------------------------------------------------------------ synthetic Pokemon for the arithmetic

BASE = {"hp": 100, "attack": 100, "defence": 100, "special_attack": 100, "special_defence": 100, "speed": 100}

SYNTH_MOVES = {
    "bonk": {"power": 100, "category": "Physical", "type": "Normal", "accuracy": 100},
    "smash": {"power": 250, "category": "Physical", "type": "Normal", "accuracy": 100},
    "zap": {"power": 100, "category": "Physical", "type": "Electric", "accuracy": 100},
    "boo": {"power": 100, "category": "Physical", "type": "Ghost", "accuracy": 100},
}


def _chart(pack):
    return pack[2]


def _M(moves, chart, name, types, *, ability="none", moveset=(), level=50, ivs=15, item=None, **stats):
    """A Mon with stats written out here, so the arithmetic tests do not depend on any real species."""
    base = dict(BASE)
    base.update(stats)
    sp = {name: {"name": name, "primaryType": types[0], "secondaryType": types[1] if len(types) > 1 else None,
                 "baseStats": base, "abilities": [ability], "moves": []}}
    return B.Mon(sp, name, level, moves, chart, ivs=ivs, ability=ability, item=item, moveset=list(moveset))


# ------------------------------------------------------------------ the damage formula

# removing this lets the damage formula drift -- a missing floor, the wrong level term, the average roll or
# the accuracy weighting dropped -- and every number the report prints moves with it while still looking like
# a plausible battle. The expected value is written out from the mainline formula here, not taken from the
# function under test.
def test_the_damage_formula_is_the_standard_one(pack):
    species, moves, chart = pack
    level, ivs = 50, 15

    def stat(base):                       # (floor((2*base + iv + ev/4) * level / 100) + 5) * nature
        return int(((2 * base + ivs + 0) * level) / 100) + 5

    def hp(base):
        return int(((2 * base + ivs + 0) * level) / 100) + level + 10

    att = B.Mon(species, "pikachu", level, moves, chart, ivs=ivs, moveset=["thunderbolt"])
    dfn = B.Mon(species, "wingull", level, moves, chart, ivs=ivs, moveset=[])
    assert att.spa == stat(species["pikachu"]["baseStats"]["special_attack"]) == 62
    assert dfn.spd == stat(species["wingull"]["baseStats"]["special_defence"]) == 42
    assert att.hp == hp(species["pikachu"]["baseStats"]["hp"]) == 102

    power = moves["thunderbolt"]["power"]                                    # 90, Electric, Special, 100%
    base = (((2 * level // 5 + 2) * power * att.spa) // dfn.spd) // 50 + 2   # the mainline damage formula
    expected = base * 4.0 * 1.5 * 0.925 * 1.0                                # 4x into Water/Flying, STAB,
    got = B.damage(att, dfn, "thunderbolt", moves, chart)                    # average roll, 100% accuracy
    assert abs(got - expected) <= 2.0, (got, expected)
    assert got > dfn.hp, "the reference case is not the one-shot it was chosen to be"

    # and accuracy is priced in rather than rolled: a 90% move deals 90% of its damage every turn
    acc = B.Mon(species, "pikachu", level, moves, chart, ivs=ivs, moveset=["thunder"])
    if moves["thunder"]["accuracy"] == 70:
        p = moves["thunder"]["power"]
        exp = ((((2 * level // 5 + 2) * p * acc.spa) // dfn.spd) // 50 + 2) * 4.0 * 1.5 * 0.925 * 0.70
        assert abs(B.damage(acc, dfn, "thunder", moves, chart) - exp) <= 2.0


# removing this lets same-type attack bonus disappear or be applied to the defender's types instead of the
# attacker's, which would reshuffle every gym's answer list.
def test_stab_multiplies_damage_by_one_and_a_half(pack):
    chart = _chart(pack)
    target = _M(SYNTH_MOVES, chart, "target", ["water"], moveset=[])
    normal = _M(SYNTH_MOVES, chart, "plain", ["normal"], moveset=["bonk"])
    other = _M(SYNTH_MOVES, chart, "other", ["fighting"], moveset=["bonk"])
    with_stab = B.damage(normal, target, "bonk", SYNTH_MOVES, chart)
    without = B.damage(other, target, "bonk", SYNTH_MOVES, chart)
    assert without > 0
    assert with_stab == pytest.approx(without * 1.5)


# removing this lets the type multiplier stop reaching the damage -- effectiveness could be computed and then
# ignored, and the report would rank a resisted attacker exactly like a super-effective one.
def test_a_two_times_type_match_doubles_the_damage_and_an_immunity_zeroes_it(pack):
    chart = _chart(pack)
    zapper = _M(SYNTH_MOVES, chart, "zapper", ["bug"], moveset=["zap"])       # no STAB on an Electric move
    neutral = _M(SYNTH_MOVES, chart, "neutral", ["normal"], moveset=[])
    weak = _M(SYNTH_MOVES, chart, "weak", ["water"], moveset=[])
    double = _M(SYNTH_MOVES, chart, "double", ["water", "flying"], moveset=[])
    immune = _M(SYNTH_MOVES, chart, "immune", ["ground"], moveset=[])
    flat = B.damage(zapper, neutral, "zap", SYNTH_MOVES, chart)
    assert flat > 0
    assert B.damage(zapper, weak, "zap", SYNTH_MOVES, chart) == pytest.approx(flat * 2)
    assert B.damage(zapper, double, "zap", SYNTH_MOVES, chart) == pytest.approx(flat * 4)
    assert B.damage(zapper, immune, "zap", SYNTH_MOVES, chart) == 0.0
    # levitate is the ability form of the same immunity
    floater = _M(SYNTH_MOVES, chart, "floater", ["normal"], ability="levitate", moveset=[])
    digger = _M(SYNTH_MOVES, chart, "digger", ["bug"], moveset=["quake"])
    quake = dict(SYNTH_MOVES, quake={"power": 100, "category": "Physical", "type": "Ground", "accuracy": 100})
    assert B.damage(digger, floater, "quake", quake, chart) == 0.0


# ------------------------------------------------------------------ Sturdy

# removing this lets Sturdy stop working, or start working when it should not: Onix and Geodude are the first
# gym's roster, and a Sturdy that never triggers makes Gym 1 look one hit easier than it is.
def test_sturdy_leaves_a_full_health_pokemon_on_exactly_one_hp(pack):
    chart = _chart(pack)
    # the player strikes first and would one-shot; the foe survives on 1 HP and kills the player back
    player = _M(SYNTH_MOVES, chart, "glass", ["normal"], moveset=["smash"], attack=200, speed=200, hp=1)
    foe = _M(SYNTH_MOVES, chart, "rock", ["normal"], ability="sturdy", moveset=["smash"],
             attack=200, defence=1, speed=1)
    assert B.best_damage(player, foe, SYNTH_MOVES, chart)[0] >= foe.hp, "the hit is not lethal to begin with"
    won, faints, downed, left = B.run_gauntlet([player], [foe], SYNTH_MOVES, chart)
    assert (won, faints, downed) == (False, 1, 0)
    assert left == pytest.approx(1.0 / foe.hp), "Sturdy did not leave exactly 1 HP: %r" % (left,)
    # a second hit finishes it, so Sturdy costs a turn and no more
    tank = _M(SYNTH_MOVES, chart, "tank", ["normal"], moveset=["smash"], attack=200, speed=200, hp=255)
    assert B.duel(tank, foe, SYNTH_MOVES, chart)[1] == 2
    plain = _M(SYNTH_MOVES, chart, "plainrock", ["normal"], moveset=["smash"], attack=200, defence=1, speed=1)
    assert B.duel(tank, plain, SYNTH_MOVES, chart)[1] == 1, "the same hit is a one-shot without Sturdy"


# removing this lets Mold Breaker stop ignoring Sturdy, which is the only reason a leader holding one is
# worth modelling differently from any other ability.
def test_mold_breaker_ignores_sturdy(pack):
    chart = _chart(pack)
    breaker = _M(SYNTH_MOVES, chart, "breaker", ["normal"], ability="moldbreaker", moveset=["smash"],
                 attack=200, speed=200, hp=1)
    foe = _M(SYNTH_MOVES, chart, "rock", ["normal"], ability="sturdy", moveset=["smash"],
             attack=200, defence=1, speed=1)
    won, faints, downed, left = B.run_gauntlet([breaker], [foe], SYNTH_MOVES, chart)
    assert (won, downed, left) == (True, 1, 0.0), "Mold Breaker did not break Sturdy"
    assert B.duel(breaker, foe, SYNTH_MOVES, chart)[1] == 1


# ------------------------------------------------------------------ the gauntlet

# removing this lets the gauntlet heal the leader between player Pokemon, which is the difference between a
# six-slot team wearing an ace down and six separate 1v1s -- and the report's whole "how many Pokemon does it
# cost to bring the ace down" reading rests on it.
def test_the_gauntlet_carries_damage_forward_to_the_next_player_pokemon(pack):
    chart = _chart(pack)
    foe = _M(SYNTH_MOVES, chart, "wall", ["normal"], moveset=["smash"], attack=200, speed=1, hp=100)
    first = _M(SYNTH_MOVES, chart, "first", ["normal"], moveset=["bonk"], attack=180, speed=200, hp=1)
    second = _M(SYNTH_MOVES, chart, "second", ["normal"], moveset=["bonk"], attack=180, speed=200, hp=1)
    x = B.best_damage(first, foe, SYNTH_MOVES, chart)[0]
    y = B.best_damage(second, foe, SYNTH_MOVES, chart)[0]
    assert 0 < y < foe.hp <= x + y, "the fixture is not the two-hits-one-each case it has to be (%r)" % (
        (x, y, foe.hp),)
    alone = B.run_gauntlet([second], [foe], SYNTH_MOVES, chart)
    assert alone[0] is False and alone[3] == pytest.approx((foe.hp - y) / foe.hp)
    pair = B.run_gauntlet([first, second], [foe], SYNTH_MOVES, chart)
    assert pair[0] is True, "the same second Pokemon could not finish a foe the first had already damaged"
    assert (pair[1], pair[2]) == (1, 1)


# removing this lets the gauntlet spin on a pair that cannot hurt each other until the 400-iteration guard
# stops it, and report the guard's state as a result. A Normal attacker and a Ghost attacker are immune to
# each other, so the only correct move is for the player to give up the slot.
def test_the_gauntlet_gives_up_the_slot_when_neither_side_can_damage_the_other(pack):
    chart = _chart(pack)
    ghost = _M(SYNTH_MOVES, chart, "ghost", ["ghost"], moveset=["boo"], speed=1)
    normal_a = _M(SYNTH_MOVES, chart, "norm1", ["normal"], moveset=["bonk"], speed=200)
    normal_b = _M(SYNTH_MOVES, chart, "norm2", ["normal"], moveset=["bonk"], speed=200)
    assert B.best_damage(normal_a, ghost, SYNTH_MOVES, chart)[0] == 0
    assert B.best_damage(ghost, normal_a, SYNTH_MOVES, chart)[0] == 0
    won, faints, downed, left = B.run_gauntlet([normal_a, normal_b], [ghost], SYNTH_MOVES, chart)
    assert (won, faints, downed) == (False, 2, 0), "the stalemate did not end after the team ran out"
    assert left == pytest.approx(1.0), "the untouched foe is not on full health"
    # and the same stalemate in a 1v1 ends at the turn cap with no winner, rather than looping
    assert B.duel(normal_a, ghost, SYNTH_MOVES, chart) == (None, 60)


# ------------------------------------------------------------------ the real data the report is built from

# removing this lets the eight gyms become seven, or lets gym 8 gain a roster without anyone noticing that
# the report's "NO ROSTER IN data/trainers.json" line has quietly stopped being true.
def test_the_authored_gyms_are_eight_leaders_with_exactly_one_empty_roster():
    leaders, contract = B.gym_leaders()
    assert sorted(leaders) == [1, 2, 3, 4, 5, 6, 7, 8]
    empty = sorted(o for o, t in leaders.items() if not t["team"])
    assert empty == [8], "the empty gym roster is no longer gym 8 alone: %s" % empty
    assert leaders[8]["status"] == "held"
    for o in range(1, 8):
        assert leaders[o]["status"] == "authored", o
        assert 3 <= len(leaders[o]["team"]) <= 6, (o, len(leaders[o]["team"]))
        levels = [m["level"] for m in leaders[o]["team"]]
        assert levels == sorted(levels), "gym %d's ace is not its last slot: %s" % (o, levels)
        for m in leaders[o]["team"]:
            assert m["species"] and isinstance(m["level"], int)
    assert contract["gym_ace_levels"], "the generation contract no longer records the ace levels"


# removing this lets the availability tables stop parsing -- a changed column, a new heading level, a row that
# the regex silently drops -- and the report would rank a shrinking candidate pool without saying so.
def test_availability_parses_eight_gyms_each_with_a_non_empty_species_list(pack):
    species, _moves, _chart = pack
    avail = B.parse_availability(B.AVAILABILITY)
    assert sorted(avail) == [1, 2, 3, 4, 5, 6, 7, 8]
    counts = {}
    for g, a in sorted(avail.items()):
        assert a["rows"], "gym %d has no catchable species" % g
        assert a["leader"] and a["theme"]
        counts[g] = len(a["rows"])
        for r in a["rows"]:
            assert 1 <= r["lo"] <= r["hi"] <= 100, (g, r)
            assert r["corridor"], (g, r)
            assert B.key(r["species"]) in species, \
                "gym %d lists %r, which resolves to no species" % (g, r["species"])
    # availability only grows: a later gym can never offer fewer species than an earlier one
    assert list(counts.values()) == sorted(counts.values()), counts
    assert B.key(avail[1]["rows"][0]["species"]) in species


# removing this lets the level cap the whole simulation runs at be read from the wrong keys and silently
# default; the cap decides every stat on both sides, so a misread here moves every number in the report.
def test_the_level_cap_comes_from_the_packs_own_rct_config():
    init, rel = B.level_caps(B.RCT_CONFIG)
    assert (init, rel) == (20, 5), "rctmod-server.toml no longer says initial 20, relative +5"


# removing this lets the trainers file the report reads drift out of the repository, which would turn every
# number above into a report about nothing.
def test_the_files_the_simulation_reads_are_the_repositorys_own():
    assert B.TRAINERS == ROOT / "data" / "trainers.json" and B.TRAINERS.is_file()
    assert B.AVAILABILITY == ROOT / "docs" / "story" / "AVAILABILITY.md" and B.AVAILABILITY.is_file()
    assert B.RCT_CONFIG.is_file()
    assert json.loads(B.TRAINERS.read_text(encoding="utf-8"))["trainers"]
    assert B.WORLD_READS == set(), "battle_sim now reads a world: ground must not come from a world save"
