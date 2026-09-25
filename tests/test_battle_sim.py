"""tools/battle_sim.py: the parsers and the arithmetic the gym numbers are made of.

The report this tool prints is a deliverable, so what is asserted here is the machinery under it, never a
verdict. Three things would silently poison every number in the report and none of them is visible in the
output: a type chart row that failed to parse (a missing row reads as neutral, so a Water defender would
look neutral to Electric -- this really happened, the last entry of each Showdown file has no trailing
comma), a move whose power or accuracy was misread, and a species name that normalised to an id the jar does
not have. Those are checked against the real jar.

The engine is checked on synthetic Pokemon whose stats are written out here, one rule at a time, because a
battle result is the product of a dozen multipliers and a wrong one is invisible in the total: the damage
formula, STAB, the type multiplier, sun and rain, the stat-stage ladder and its clamp, Sturdy and Mold
Breaker, the type absorbers and what they are paid, who can take which status, the weight and speed-ratio
moves, the items that fire on being hit, the residual damage at the end of a turn, Intimidate, and the
gauntlet's carry-forward. The expected damage is derived
from the formula spelled out in the test, never from the function under test. Where the mainline rule is the
standard, the test asserts the mainline rule and not what the code happens to do.

The switching bound is opt-in and the tool documents it as untrustworthy -- it came out worse than never
switching at two of seven gyms -- so nothing here asserts that it is good. What is asserted is that it is
sound: it swaps only a losing matchup for a winning one, and it stays inside its own switch budget.

The real data is checked only for the shape the tool depends on: eight gym leaders, one of them (gym 8,
`status: held`) with no roster; every gym pool exactly the rows derived/availability.json records; and Blaine's
Drought lead actually reaching the field. A row that resolves to nothing has to be counted in `assess`'s
`unresolved` list rather than dropped, because a pool that shrank silently reads exactly like a pool that was
always narrow, and that is the one reading the tool exists to give.

Not covered, and it is most of what matters about a battle:
  - whether any of these numbers resemble play. The module docstring of the tool lists its own omissions --
    no hazards, no crits, no secondary effects, no bag items, most abilities inert -- and no pytest can close
    that gap. Only playing a gym can.
  - whether Cobblemon's own battle engine computes damage this way. The formula here is the standard
    mainline one; that Showdown-in-Cobblemon agrees with it at these levels is unverified and needs a battle
    run on a real server with the damage read back.
  - move legality: choose_moveset picks from the jar's level-up list only, so tutor, TM, egg and event moves
    are invisible, and nothing here checks that a leader's authored moveset is learnable at all.
  - the turn loop as a whole. Its pieces are tested; the order it runs them in, who moves first over a full
    fight, sleep and paralysis turn loss, and screens are not.
  - which move the AI reaches for and when. best_action's rule -- attack if it can, otherwise support, and
    recover again below 60% -- is exercised only through the pieces it calls, not as a policy.
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
    assert moves["rockslide"] == {"power": 75, "category": "Physical", "type": "Rock", "accuracy": 90,
                                  "contact": False}
    assert moves["thunderbolt"]["power"] == 90 and moves["thunderbolt"]["category"] == "Special"
    assert moves["earthquake"]["power"] == 100 and moves["earthquake"]["type"] == "Ground"
    assert "zippyzap" in moves, "the last move in moves.js was dropped: the trailing-comma bug is back"


# removing this lets the contact flag be read from the wrong place, or default to the move's category again.
# Contact is a per-move flag, not "is it physical": Rock Slide, Earthquake and Bullet Seed are physical and
# touch nothing, and a Rocky Helmet that taxed them would charge half the candidate list a sixth of its
# health for attacks it never made. 272 of the jar's 930 moves make contact.
def test_the_contact_flag_is_read_per_move_and_not_from_the_category(pack):
    _species, moves, _chart = pack
    for mid in ("tackle", "bodyslam", "closecombat", "lowkick", "gyroball", "grassknot", "wildcharge"):
        assert moves[mid]["contact"] is True, mid
    for mid in ("rockslide", "earthquake", "bulletseed", "surf", "thunderbolt", "flamethrower", "swift"):
        assert moves[mid]["contact"] is False, mid
    assert all(isinstance(m["contact"], bool) for m in moves.values())
    n = sum(1 for m in moves.values() if m["contact"])
    assert 200 < n < len(moves) / 2, "%d of %d moves make contact, which is not a per-move flag" % (
        n, len(moves))
    physical = [mid for mid, m in moves.items() if m["category"] == "Physical"]
    assert any(not moves[mid]["contact"] for mid in physical), "every physical move reads as contact again"
    assert any(moves[mid]["contact"] for mid in physical)


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
# and Nidoran(m) onto "nidoran", which is not a species id at all -- the jar has nidoranf and nidoranm. The
# pools happen to spell them as ids today, so nothing would break tomorrow; it would break the first time a
# name with a sign in it reached key() from a roster or a hand-written table, which is how the two species
# vanished from Gym 8 in the first place. They are distinct species, so the test asserts they stay distinct
# and not merely that each resolves to something.
def test_the_gender_signs_map_to_two_distinct_species_ids(pack):
    species, _moves, _chart = pack
    f, m = B.key("Nidoran♀"), B.key("Nidoran♂")
    assert (f, m) == ("nidoranf", "nidoranm")
    assert f in species and m in species and f != m
    assert species[f]["name"] != species[m]["name"]
    assert B.key("Nidorina") != f and B.key("nidoran") not in species


# removing this lets a gym's pool shrink between the generator and the simulation without anything saying so.
# parse_availability no longer scrapes the markdown; it reads derived/availability.json, so the property worth
# holding is that the two agree row for row. The count is taken from the sidecar rather than written here,
# because the pool grows whenever tools/availability.py reaches further -- what must not happen is the reader
# and the file disagreeing about how many species a gym has.
def test_every_gym_pool_is_exactly_what_the_sidecar_records(pack):
    species, _moves, _chart = pack
    side = json.loads(B.AVAIL_JSON.read_text(encoding="utf-8"))
    avail = B.parse_availability(B.AVAILABILITY)
    assert side["generated_by"] == "tools/availability.py"
    assert sorted(int(g) for g in side["gyms"]) == sorted(avail)
    for g in sorted(avail):
        want = [r["species"] for r in side["gyms"][str(g)]]
        got = [r["species"] for r in avail[g]["rows"]]
        assert got == want, "gym %d: the reader and the sidecar disagree" % g
    g8 = [r["species"] for r in avail[8]["rows"]]
    assert sorted(x for x in g8 if x.startswith("nidoran")) == ["nidoranf", "nidoranm"], \
        "both gendered Nidoran must be in Gym 8's pool"
    assert len(g8) == len(side["gyms"]["8"]) > 98, \
        "Gym 8's pool is %d, no larger than the markdown table it replaced" % len(g8)


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
        distinct = {B.key(r["species"]) for r in avail[g]["rows"]}
        assert len(out["candidates"]) == len(distinct), \
            "gym %d turned %d distinct species into %d candidates: some were dropped in silence" % (
                g, len(distinct), len(out["candidates"]))


# ------------------------------------------------------------------ synthetic Pokemon for the arithmetic

BASE = {"hp": 100, "attack": 100, "defence": 100, "special_attack": 100, "special_defence": 100, "speed": 100}

SYNTH_MOVES = {
    "bonk": {"power": 100, "category": "Physical", "type": "Normal", "accuracy": 100},
    "smash": {"power": 250, "category": "Physical", "type": "Normal", "accuracy": 100},
    "zap": {"power": 100, "category": "Physical", "type": "Electric", "accuracy": 100},
    "boo": {"power": 100, "category": "Physical", "type": "Ghost", "accuracy": 100},
    "flare": {"power": 100, "category": "Special", "type": "Fire", "accuracy": 100},
    "douse": {"power": 100, "category": "Special", "type": "Water", "accuracy": 100},
    "leafy": {"power": 100, "category": "Special", "type": "Grass", "accuracy": 100},
    "quake": {"power": 100, "category": "Physical", "type": "Ground", "accuracy": 100},
    "tap": {"power": 1, "category": "Physical", "type": "Normal", "accuracy": 100},
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
    # and the same stalemate in a 1v1 is resolved on the first turn rather than ground out to the cap: the
    # slot is spent the moment neither side has an action, and duel reports the turn it really took
    assert B.duel(normal_a, ghost, SYNTH_MOVES, chart) == (None, 1)


# ------------------------------------------------------------------ weather

# removing this lets sun and rain stop touching the damage they are supposed to touch. This is load-bearing
# rather than decorative: Blaine leads a Drought Torkoal, and turning the sun on reversed the verdict on his
# gym from a clean win to a loss. A weather multiplier that silently stopped applying would put it back.
def test_sun_and_rain_multiply_fire_and_water_and_nothing_else(pack):
    chart = _chart(pack)
    att = _M(SYNTH_MOVES, chart, "att", ["normal"], moveset=["flare", "douse", "leafy"])
    dfn = _M(SYNTH_MOVES, chart, "dfn", ["normal"], moveset=[])

    def d(mid, weather):
        f = B.Field()
        f.weather = weather
        return B.damage(att, dfn, mid, SYNTH_MOVES, chart, f)

    fire, water, grass = d("flare", None), d("douse", None), d("leafy", None)
    assert fire > 0 and fire == water == grass, "the reference moves are not interchangeable"
    assert d("flare", "sun") == pytest.approx(fire * 1.5)
    assert d("douse", "sun") == pytest.approx(water * 0.5)
    assert d("douse", "rain") == pytest.approx(water * 1.5)
    assert d("flare", "rain") == pytest.approx(fire * 0.5)
    for w in (None, "sun", "rain", "sand", "snow"):
        assert d("leafy", w) == pytest.approx(grass), "weather %r moved a Grass move" % w
    for w in ("sand", "snow"):                       # sand and snow are chip and nothing else here
        assert d("flare", w) == pytest.approx(fire) and d("douse", w) == pytest.approx(water)


# removing this lets a weather ability stop reaching the field, or lets two of them fight over it every turn.
# Drought on the leader's lead is the whole reason Blaine's gym reads the way it does, and the first setter
# has to keep it: a second ability overwriting it would make the result depend on iteration order.
def test_a_weather_ability_sets_the_field_once_from_either_side(pack):
    chart = _chart(pack)

    def mon(name, ability):
        return _M(SYNTH_MOVES, chart, name, ["normal"], ability=ability, moveset=["bonk"])

    plain = mon("plain", "none")
    for ability, weather in (("drought", "sun"), ("drizzle", "rain"),
                             ("sandstream", "sand"), ("snowwarning", "snow")):
        f = B.Field()
        assert f.weather is None
        B.start_battle([mon("p", ability)], [mon("f", "none")], f)
        assert f.weather == weather, "%s on the player's side did not set %s" % (ability, weather)
        f2 = B.Field()
        B.start_battle([plain], [mon("f", ability)], f2)
        assert f2.weather == weather, "%s on the leader's side did not set %s" % (ability, weather)
    # two setters: the first one wins and the second does not overwrite it
    f3 = B.Field()
    B.start_battle([mon("sunny", "drought")], [mon("rainy", "drizzle")], f3)
    assert f3.weather == "sun"
    # and weather already on the field survives a switch-in that would have set its own
    f4 = B.Field()
    f4.weather = "rain"
    B.start_battle([mon("sunny", "drought")], [plain], f4)
    assert f4.weather == "rain"


# removing this lets Blaine's lead stop turning the sun on without the gym report changing shape -- the same
# roster, the same numbers printed, and a Fire gym quietly reading half as dangerous as it is.
def test_blaines_drought_lead_turns_the_sun_on_for_his_own_roster(pack):
    species, moves, chart = pack
    leaders, _contract = B.gym_leaders()
    foes = B.build_leader(leaders[7], species, moves, chart, 15, False)
    assert foes[0].ability == "drought", "Blaine's lead no longer carries Drought: %s" % foes[0].ability
    player = _M(SYNTH_MOVES, chart, "player", ["normal"], moveset=["bonk"])
    field = B.Field()
    B.start_battle([player], foes, field)
    assert field.weather == "sun"
    fire = next((m for m in foes[0].moveset if moves.get(m, {}).get("type") == "Fire"), None)
    assert fire, "the Drought lead has no Fire move to be multiplied: %s" % foes[0].moveset
    clear = B.Field()
    assert B.damage(foes[0], player, fire, moves, chart, field, species) == pytest.approx(
        B.damage(foes[0], player, fire, moves, chart, clear, species) * 1.5)


# ------------------------------------------------------------------ stat stages

# removing this lets the boost ladder drift off the standard table. +1 is 1.5x and -1 is 2/3, not 1.5 and 0.5:
# an off-by-one row would make every Nasty Plot and every Intimidate the wrong size, and nothing in the report
# names a stage, so it would only show up as numbers that were always a bit wrong.
def test_the_stat_stage_ladder_is_the_standard_one(pack):
    chart = _chart(pack)
    assert B.STAGE[0] == 1.0
    assert B.STAGE[1] == pytest.approx(1.5) and B.STAGE[-1] == pytest.approx(2 / 3)
    assert B.STAGE[2] == pytest.approx(2.0) and B.STAGE[-2] == pytest.approx(0.5)
    assert B.STAGE[6] == pytest.approx(4.0) and B.STAGE[-6] == pytest.approx(0.25)
    assert sorted(B.STAGE) == list(range(-6, 7)), "the ladder is not the thirteen stages the game has"
    for i in range(-6, 6):                            # monotone: a boost never makes a stat smaller
        assert B.STAGE[i] < B.STAGE[i + 1]
    m = _M(SYNTH_MOVES, chart, "m", ["normal"], moveset=["bonk"])
    for stage, attr in (("atk", "eff_atk"), ("def", "eff_def"), ("spa", "eff_spa"), ("spd", "eff_spd")):
        raw = getattr(m, {"atk": "atk", "def": "df", "spa": "spa", "spd": "spd"}[stage])
        m.stages[stage] = 1
        assert getattr(m, attr)() == int(raw * 1.5), stage
        m.stages[stage] = -1
        assert getattr(m, attr)() == int(raw * 2 / 3), stage
        m.stages[stage] = 0


# removing this lets a boost run off the end of the ladder into a KeyError, or past +6 into damage the game
# cannot produce. Shell Smash twice is the case that reaches it.
def test_stat_stages_clamp_at_plus_and_minus_six(pack):
    chart = _chart(pack)
    a = _M(SYNTH_MOVES, chart, "a", ["normal"], moveset=["swordsdance"])
    b = _M(SYNTH_MOVES, chart, "b", ["normal"], moveset=["bonk"])
    field = B.Field()
    for _ in range(6):                                # +2 a time, so this asks for +12
        B.apply_support(a, b, "swordsdance", field, SYNTH_MOVES)
    assert a.stages["atk"] == 6
    assert a.eff_atk() == int(a.atk * 4.0)
    for _ in range(6):
        B.apply_support(b, a, "charm", field, SYNTH_MOVES)   # -2 a time to the target
    assert a.stages["atk"] == -6
    assert a.eff_atk() == max(1, int(a.atk * 0.25))


# removing this lets Choice Scarf or paralysis stop moving the speed that decides who hits first, which is
# the difference between a one-shot landing and being taken. Typhlosion holds a Scarf at Blaine's.
def test_choice_scarf_and_paralysis_both_scale_speed(pack):
    chart = _chart(pack)
    plain = _M(SYNTH_MOVES, chart, "plain", ["normal"], moveset=["bonk"])
    scarf = _M(SYNTH_MOVES, chart, "scarf", ["normal"], moveset=["bonk"], item="choice_scarf")
    assert plain.eff_spe() == plain.spe
    assert scarf.eff_spe() == int(scarf.spe * 1.5)
    par = _M(SYNTH_MOVES, chart, "par", ["normal"], moveset=["bonk"])
    par.status = "par"
    assert par.eff_spe() == int(par.spe * 0.5)
    both = _M(SYNTH_MOVES, chart, "both", ["normal"], moveset=["bonk"], item="choice_scarf")
    both.status = "par"
    assert both.eff_spe() == int(int(both.spe * 1.5) * 0.5)
    slow = _M(SYNTH_MOVES, chart, "slow", ["normal"], moveset=["bonk"])
    slow.stages["spe"] = -2
    assert slow.eff_spe() == int(slow.spe * 0.5)
    assert slow.eff_spe() >= 1, "a speed stat can never floor to zero"


# ------------------------------------------------------------------ items that fire on being hit

# removing this lets Focus Sash stop saving, or start saving twice, or save from half health. Seven leader
# Pokemon hold one, so a sash that fires from any HP would add a free turn to seven fights.
def test_focus_sash_saves_from_full_health_exactly_once(pack):
    chart = _chart(pack)
    att = _M(SYNTH_MOVES, chart, "att", ["normal"], moveset=["smash"])
    dfn = _M(SYNTH_MOVES, chart, "dfn", ["normal"], moveset=[], item="focus_sash")
    B.take_hit(dfn, att, dfn.hp * 3, False, False)
    assert dfn.hp_now == 1 and dfn.item_used is True
    B.take_hit(dfn, att, dfn.hp * 3, False, False)
    assert dfn.hp_now <= 0, "the sash saved a second time"
    # and it does nothing from partial health, which is what separates it from a revive
    part = _M(SYNTH_MOVES, chart, "part", ["normal"], moveset=[], item="focus_sash")
    part.hp_now = part.hp - 1
    B.take_hit(part, att, part.hp * 3, False, False)
    assert part.hp_now <= 0, "the sash saved from partial health"
    assert part.item_used is False


# removing this lets Weakness Policy fire on a neutral hit or fire every turn. Onix holds one at Gym 1, and a
# policy that triggered on anything would turn the first gym's wall into a sweeper.
def test_weakness_policy_fires_only_on_a_super_effective_hit_and_only_once(pack):
    chart = _chart(pack)
    att = _M(SYNTH_MOVES, chart, "att", ["normal"], moveset=["tap"])
    dfn = _M(SYNTH_MOVES, chart, "dfn", ["normal"], moveset=[], item="weakness_policy")
    B.take_hit(dfn, att, 5.0, False, False)
    assert (dfn.stages["atk"], dfn.stages["spa"]) == (0, 0), "a neutral hit set the policy off"
    B.take_hit(dfn, att, 5.0, True, False)
    assert (dfn.stages["atk"], dfn.stages["spa"]) == (2, 2)
    B.take_hit(dfn, att, 5.0, True, False)
    assert (dfn.stages["atk"], dfn.stages["spa"]) == (2, 2), "the policy fired twice"
    # a hit that faints the holder never pays out
    dead = _M(SYNTH_MOVES, chart, "dead", ["normal"], moveset=[], item="weakness_policy")
    dead.hp_now = 5.0
    B.take_hit(dead, att, 50.0, True, False)
    assert (dead.stages["atk"], dead.stages["spa"]) == (0, 0)


# removing this lets the pinch berries heal the wrong amount or heal at full health. Geodude's Oran and
# Arcanine's Sitrus are the two that decide whether a one-shot is a one-shot.
def test_sitrus_heals_a_quarter_and_oran_ten_only_below_half(pack):
    chart = _chart(pack)
    att = _M(SYNTH_MOVES, chart, "att", ["normal"], moveset=["tap"])

    def hit(item, dmg):
        m = _M(SYNTH_MOVES, chart, "m", ["normal"], moveset=[], item=item)
        B.take_hit(m, att, dmg, False, False)
        return m

    sit = hit("sitrus_berry", 100.0)                  # 167 - 100 = 67, under half
    assert sit.hp_now == pytest.approx(67 + sit.hp / 4.0) and sit.item_used is True
    ora = hit("oran_berry", 100.0)
    assert ora.hp_now == pytest.approx(67 + 10.0) and ora.item_used is True
    high = hit("sitrus_berry", 10.0)                  # still over half: the berry waits
    assert high.hp_now == pytest.approx(high.hp - 10.0) and high.item_used is False
    twice = hit("sitrus_berry", 100.0)
    before = twice.hp_now
    B.take_hit(twice, att, 1.0, False, False)
    assert twice.hp_now == pytest.approx(before - 1.0), "the berry healed a second time"


# removing this lets Rocky Helmet hurt an attacker that never touched it. Weezing holds one at Koga's, and a
# helmet that fired on special moves would tax the wrong half of the candidate list.
def test_rocky_helmet_only_pays_back_a_physical_hit(pack):
    chart = _chart(pack)
    dfn = _M(SYNTH_MOVES, chart, "dfn", ["normal"], moveset=[], item="rocky_helmet")
    phys = _M(SYNTH_MOVES, chart, "phys", ["normal"], moveset=["bonk"])
    spec = _M(SYNTH_MOVES, chart, "spec", ["normal"], moveset=["flare"])
    B.take_hit(dfn, phys, 10.0, False, True)
    assert phys.hp_now == pytest.approx(phys.hp - phys.hp / 6.0)
    B.take_hit(dfn, spec, 10.0, False, False)
    assert spec.hp_now == pytest.approx(spec.hp), "the helmet hit a move that made no contact"


# ------------------------------------------------------------------ the end of the turn

# removing this lets the residual damage that decides long fights drift. Leftovers is a sixteenth, Life Orb a
# tenth and only when the holder attacked, burn a sixteenth, poison an eighth, toxic climbs a sixteenth a
# turn, and sand skips Rock, Ground and Steel. Each of these is on a leader's Pokemon somewhere.
def test_residual_healing_and_chip_are_the_standard_fractions(pack):
    chart = _chart(pack)
    field = B.Field()

    def mon(**kw):
        m = _M(SYNTH_MOVES, chart, "m", ["normal"], moveset=["bonk"], **kw)
        return m

    lefto = mon(item="leftovers")
    lefto.hp_now = lefto.hp / 2
    B.end_of_turn(lefto, field)
    assert lefto.hp_now == pytest.approx(lefto.hp / 2 + lefto.hp / 16.0)
    full = mon(item="leftovers")
    B.end_of_turn(full, field)
    assert full.hp_now == pytest.approx(full.hp), "Leftovers healed past the maximum"

    orb = mon(item="life_orb")
    B.end_of_turn(orb, field)
    assert orb.hp_now == pytest.approx(orb.hp), "Life Orb charged a holder that did not attack"
    orb.hit_this_turn = True
    B.end_of_turn(orb, field)
    assert orb.hp_now == pytest.approx(orb.hp - orb.hp / 10.0)
    assert orb.hit_this_turn is False, "the attacked flag was not cleared, so the next turn charges again"

    burn = mon()
    burn.status = "brn"
    B.end_of_turn(burn, field)
    assert burn.hp_now == pytest.approx(burn.hp - burn.hp / 16.0)
    psn = mon()
    psn.status = "psn"
    B.end_of_turn(psn, field)
    assert psn.hp_now == pytest.approx(psn.hp - psn.hp / 8.0)
    tox = mon()
    tox.status = "tox"
    B.end_of_turn(tox, field)
    after_one = tox.hp - tox.hp / 16.0
    assert tox.hp_now == pytest.approx(after_one)
    B.end_of_turn(tox, field)
    assert tox.hp_now == pytest.approx(after_one - tox.hp * 2 / 16.0), "toxic did not escalate"


# removing this lets a sandstorm chip the types that are supposed to stand in it, which is most of Giovanni's
# gym and all of Brock's.
def test_sandstorm_chips_everything_except_rock_ground_and_steel(pack):
    chart = _chart(pack)
    sand = B.Field()
    sand.weather = "sand"
    for types, chipped in ((["normal"], True), (["water", "flying"], True), (["rock"], False),
                           (["ground"], False), (["steel"], False), (["rock", "ground"], False),
                           (["bug", "steel"], False)):
        m = _M(SYNTH_MOVES, chart, "m", types, moveset=["bonk"])
        B.end_of_turn(m, sand)
        if chipped:
            assert m.hp_now == pytest.approx(m.hp - m.hp / 16.0), types
        else:
            assert m.hp_now == pytest.approx(m.hp), types


# removing this lets Magic Guard stop cancelling indirect damage. Sabrina's Alakazam holds a Life Orb because
# Magic Guard eats the recoil; without it the ace loses a tenth of its health every turn it attacks.
def test_magic_guard_cancels_every_kind_of_residual_damage(pack):
    chart = _chart(pack)
    sand = B.Field()
    sand.weather = "sand"
    m = _M(SYNTH_MOVES, chart, "m", ["normal"], ability="magicguard", moveset=["bonk"], item="life_orb")
    m.status = "tox"
    m.hit_this_turn = True
    B.end_of_turn(m, sand)
    assert m.hp_now == pytest.approx(m.hp), "Magic Guard let residual damage through"
    plain = _M(SYNTH_MOVES, chart, "plain", ["normal"], moveset=["bonk"], item="life_orb")
    plain.status = "tox"
    plain.hit_this_turn = True
    B.end_of_turn(plain, sand)
    assert plain.hp_now < plain.hp, "the comparison case takes no residual damage either"


# removing this lets Magic Guard block healing as well as damage. It prevents indirect damage and nothing
# else: a Magic Guard holder with Leftovers heals every turn, and a version that skipped the healing too
# would understate any leader ever given that pair.
def test_magic_guard_does_not_block_leftovers(pack):
    chart = _chart(pack)
    field = B.Field()
    m = _M(SYNTH_MOVES, chart, "m", ["normal"], ability="magicguard", moveset=["bonk"], item="leftovers")
    m.status = "brn"
    m.hp_now = m.hp / 2.0
    B.end_of_turn(m, field)
    assert m.hp_now == pytest.approx(m.hp / 2.0 + m.hp / 16.0), \
        "Magic Guard ate the Leftovers healing, or let the burn through"


# ------------------------------------------------------------------ who can take which status

# removing this lets one status move shut down three whole gyms. A Fire type cannot be burned, an Electric
# type cannot be paralysed and a Poison or Steel type cannot be poisoned or badly poisoned -- which is
# Blaine's roster, Surge's roster and Koga's roster respectively. Without the immunities a single Will-O-Wisp
# halves every physical attacker Blaine has.
def test_a_type_cannot_take_the_status_its_own_type_makes(pack):
    chart = _chart(pack)
    field = B.Field()
    user = _M(SYNTH_MOVES, chart, "user", ["normal"], moveset=["bonk"])

    def inflict(types, mid):
        target = _M(SYNTH_MOVES, chart, "target", types, moveset=[])
        B.apply_support(user, target, mid, field, SYNTH_MOVES)
        return target.status

    assert inflict(["fire"], "willowisp") is None
    assert inflict(["electric"], "thunderwave") is None
    assert inflict(["electric", "flying"], "glare") is None
    assert inflict(["poison"], "toxic") is None
    assert inflict(["steel"], "toxic") is None
    assert inflict(["poison"], "poisonpowder") is None
    assert inflict(["steel", "psychic"], "poisonpowder") is None
    # and the same moves land on something that is not immune, or the test is proving nothing
    assert inflict(["normal"], "willowisp") == "brn"
    assert inflict(["normal"], "thunderwave") == "par"
    assert inflict(["normal"], "toxic") == "tox"
    assert inflict(["fire"], "toxic") == "tox", "a Fire type resists burn, not poison"
    assert inflict(["electric"], "willowisp") == "brn"
    assert B.status_immune(_M(SYNTH_MOVES, chart, "ice", ["ice"], moveset=[]), "frz", None) is True
    assert B.status_immune(_M(SYNTH_MOVES, chart, "n", ["normal"], moveset=[]), "frz", None) is False


# removing this lets powder moves work on Grass types, which is the difference between Erika's gym having a
# sleep answer and not having one.
def test_powder_moves_fail_on_grass_types(pack):
    chart = _chart(pack)
    field = B.Field()
    user = _M(SYNTH_MOVES, chart, "user", ["normal"], moveset=["bonk"])
    grass = _M(SYNTH_MOVES, chart, "grass", ["grass"], moveset=[])
    B.apply_support(user, grass, "sleeppowder", field, SYNTH_MOVES)
    assert grass.status is None
    other = _M(SYNTH_MOVES, chart, "other", ["grass"], moveset=[])
    B.apply_support(user, other, "hypnosis", field, SYNTH_MOVES)
    assert other.status == "slp", "Hypnosis is not a powder move and should still work on Grass"
    normal = _M(SYNTH_MOVES, chart, "normal", ["normal"], moveset=[])
    B.apply_support(user, normal, "sleeppowder", field, SYNTH_MOVES)
    assert normal.status == "slp"


# removing this lets an ability that really does confer immunity stop conferring it, or lets one that does not
# start. Magic Guard is the case that matters: it stops indirect damage and nothing else, and it was giving
# Alakazam a blanket status immunity it has never had in any game.
def test_only_the_abilities_that_confer_a_status_immunity_confer_one(pack):
    chart = _chart(pack)
    field = B.Field()
    user = _M(SYNTH_MOVES, chart, "user", ["normal"], moveset=["bonk"])

    def inflict(ability, mid):
        target = _M(SYNTH_MOVES, chart, "target", ["normal"], ability=ability, moveset=[])
        B.apply_support(user, target, mid, field, SYNTH_MOVES)
        return target.status

    assert inflict("limber", "thunderwave") is None
    assert inflict("immunity", "toxic") is None
    assert inflict("waterveil", "willowisp") is None
    assert inflict("insomnia", "hypnosis") is None
    assert inflict("vitalspirit", "spore") is None
    assert inflict("magicguard", "thunderwave") == "par", "Magic Guard is not a status immunity"
    assert inflict("magicguard", "toxic") == "tox"
    assert inflict("magicguard", "willowisp") == "brn"
    assert inflict("limber", "willowisp") == "brn", "Limber covers paralysis only"
    assert inflict("none", "thunderwave") == "par"


# removing this lets a status stick to something that already has one, which would let a second status move
# overwrite a burn with paralysis and make the leader's turn free.
def test_a_status_move_does_not_overwrite_a_status_already_there(pack):
    chart = _chart(pack)
    field = B.Field()
    user = _M(SYNTH_MOVES, chart, "user", ["normal"], moveset=["bonk"])
    target = _M(SYNTH_MOVES, chart, "target", ["normal"], moveset=[])
    B.apply_support(user, target, "willowisp", field, SYNTH_MOVES)
    assert target.status == "brn"
    B.apply_support(user, target, "thunderwave", field, SYNTH_MOVES)
    assert target.status == "brn"


# ------------------------------------------------------------------ type absorbers

# removing this lets an absorbing ability stop absorbing. Three of Surge's four have Lightning Rod: an
# Electric answer to the Electric gym does literally nothing, and a report that forgot it would recommend
# exactly the wrong team.
def test_every_absorbing_ability_takes_zero_from_its_type(pack):
    chart = _chart(pack)
    by_type = {"Electric": "zap", "Water": "douse", "Fire": "flare", "Grass": "leafy", "Ground": "quake"}
    att = _M(SYNTH_MOVES, chart, "att", ["normal"], moveset=list(by_type.values()))
    for ability, (typ, _payoff) in sorted(B.ABSORB.items()):
        mid = by_type[typ]
        holder = _M(SYNTH_MOVES, chart, "holder", ["normal"], ability=ability, moveset=[])
        assert B.damage(att, holder, mid, SYNTH_MOVES, chart) == 0.0, ability
        assert B.best_damage(att, holder, SYNTH_MOVES, chart)[0] > 0, \
            "%s absorbed a type it has no business absorbing" % ability
        other = "bonk"                                # Normal: nothing in the table absorbs it
        assert B.damage(att, holder, other, SYNTH_MOVES, chart) > 0, ability


# removing this lets Mold Breaker's reach drift. The mainline rule is that Mold Breaker ignores every one of
# these abilities -- Levitate, Lightning Rod, Volt/Water Absorb, Flash Fire, Sap Sipper, Motor Drive, Dry
# Skin and Earth Eater are all on its ignored list -- so a Mold Breaker attacker damages all of them.
def test_mold_breaker_gets_through_every_absorber(pack):
    chart = _chart(pack)
    by_type = {"Electric": "zap", "Water": "douse", "Fire": "flare", "Grass": "leafy", "Ground": "quake"}
    breaker = _M(SYNTH_MOVES, chart, "breaker", ["normal"], ability="moldbreaker",
                 moveset=list(by_type.values()))
    for ability, (typ, _payoff) in sorted(B.ABSORB.items()):
        holder = _M(SYNTH_MOVES, chart, "holder", ["normal"], ability=ability, moveset=[])
        assert B.damage(breaker, holder, by_type[typ], SYNTH_MOVES, chart) > 0, ability


# removing this lets an absorber go back to being immunity and nothing else. Lightning Rod is not just "takes
# no damage": it takes the hit and gets stronger, which is why an Electric attacker at Surge's gym is worse
# than useless, and Water Absorb undoes a quarter of the work that went into bringing the holder down.
def test_an_absorbed_hit_pays_the_absorber(pack):
    chart = _chart(pack)
    by_type = {"Electric": "zap", "Water": "douse", "Fire": "flare", "Grass": "leafy", "Ground": "quake"}
    att = _M(SYNTH_MOVES, chart, "att", ["normal"], moveset=list(by_type.values()))
    breaker = _M(SYNTH_MOVES, chart, "breaker", ["normal"], ability="moldbreaker",
                 moveset=list(by_type.values()))
    for ability, (typ, payoff) in sorted(B.ABSORB.items()):
        mid = by_type[typ]
        holder = _M(SYNTH_MOVES, chart, "holder", ["normal"], ability=ability, moveset=[])
        holder.hp_now = holder.hp / 2.0
        assert B.damage(att, holder, mid, SYNTH_MOVES, chart) == 0.0, ability
        if payoff == "heal":
            assert holder.hp_now == pytest.approx(holder.hp / 2.0 + holder.hp / 4.0), ability
            assert holder.stages == {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}, ability
        elif payoff:
            assert holder.stages[payoff] == 1, ability
            assert holder.hp_now == pytest.approx(holder.hp / 2.0), ability
        else:                                         # Levitate is immunity and nothing else
            assert holder.stages == {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}, ability
            assert holder.hp_now == pytest.approx(holder.hp / 2.0), ability
        # a Mold Breaker attacker takes the payoff away with the immunity
        broken = _M(SYNTH_MOVES, chart, "broken", ["normal"], ability=ability, moveset=[])
        broken.hp_now = broken.hp / 2.0
        assert B.damage(breaker, broken, mid, SYNTH_MOVES, chart) > 0, ability
        assert broken.stages == {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}, ability
        assert broken.hp_now == pytest.approx(broken.hp / 2.0), ability


# removing this lets the absorber's payoff run off the top of the ladder or heal past full, which is the one
# way a defensive ability can turn into a source of numbers the game cannot produce.
def test_the_absorbers_payoff_respects_the_ceiling(pack):
    chart = _chart(pack)
    att = _M(SYNTH_MOVES, chart, "att", ["normal"], moveset=["zap", "douse"])
    rod = _M(SYNTH_MOVES, chart, "rod", ["normal"], ability="lightningrod", moveset=[])
    for _ in range(9):
        B.damage(att, rod, "zap", SYNTH_MOVES, chart)
    assert rod.stages["spa"] == 6, "Lightning Rod boosted past +6"
    sponge = _M(SYNTH_MOVES, chart, "sponge", ["normal"], ability="waterabsorb", moveset=[])
    B.damage(att, sponge, "douse", SYNTH_MOVES, chart)
    assert sponge.hp_now == pytest.approx(sponge.hp), "Water Absorb healed past the maximum"


# removing this lets an Air Balloon stop floating, or float forever. Raichu carries one at Surge's, and it is
# the only reason a Ground answer to that gym is not automatic.
def test_an_air_balloon_ignores_ground_until_it_pops(pack):
    chart = _chart(pack)
    att = _M(SYNTH_MOVES, chart, "att", ["normal"], moveset=["quake", "bonk"])
    holder = _M(SYNTH_MOVES, chart, "holder", ["electric"], moveset=[], item="airballoon")
    assert B.damage(att, holder, "quake", SYNTH_MOVES, chart) == 0.0
    assert B.damage(att, holder, "bonk", SYNTH_MOVES, chart) > 0
    holder.balloon_popped = True
    assert B.damage(att, holder, "quake", SYNTH_MOVES, chart) > 0


# ------------------------------------------------------------------ variable power

# removing this lets Grass Knot, Low Kick and Gyro Ball go back to zero power. Showdown stores them with
# basePower 0 because the power is computed, and reading that as "status move" silently disarmed Raichu's
# Grass Knot, Bronzong's Gyro Ball and Bonsly's Low Kick -- three leader Pokemon carrying a dead slot.
def test_weight_moves_read_the_jars_weight_and_are_not_zero(pack):
    species, moves, chart = pack
    raichu = B.Mon(species, "raichu", 50, moves, chart, moveset=["grassknot"])
    heavy = B.Mon(species, "snorlax", 50, moves, chart, moveset=[])      # 460.0 kg
    light = B.Mon(species, "joltik", 50, moves, chart, moveset=[])       # 0.6 kg
    assert species["snorlax"]["weight"] == 4600 and species["joltik"]["weight"] == 6, \
        "the jar's weight field is not hectograms any more"
    assert B.variable_power("grassknot", raichu, heavy, moves, species) == 120
    assert B.variable_power("grassknot", raichu, light, moves, species) == 20
    assert B.variable_power("lowkick", raichu, heavy, moves, species) == 120
    hit_heavy = B.damage(raichu, heavy, "grassknot", moves, chart, None, species)
    hit_light = B.damage(raichu, light, "grassknot", moves, chart, None, species)
    assert hit_heavy > 0, "Raichu's Grass Knot is disarmed again"
    assert hit_light > 0 and hit_heavy > hit_light, (hit_heavy, hit_light)
    # the whole weight ladder, so a shifted threshold cannot hide inside one spot check
    powers = [B.variable_power("grassknot", raichu, heavy, moves, species)]
    for name, want in (("snorlax", 120), ("onix", 120), ("raichu", 60), ("pikachu", 20)):
        d = B.Mon(species, name, 50, moves, chart, moveset=[])
        got = B.variable_power("grassknot", raichu, d, moves, species)
        assert got == want, "%s weighs %s hg and got power %d" % (name, species[name]["weight"], got)
    assert powers


# removing this lets Gyro Ball stop reading the speed ratio, which is the only reason Bronzong's slowest stat
# is an attack at all.
def test_gyro_ball_scales_with_the_speed_ratio(pack):
    species, moves, chart = pack
    slow = _M(SYNTH_MOVES, chart, "slow", ["steel"], moveset=["gyroball"], speed=1)
    fast = _M(SYNTH_MOVES, chart, "fast", ["normal"], moveset=[], speed=200)
    same = _M(SYNTH_MOVES, chart, "same", ["normal"], moveset=[], speed=1)
    want = max(1, min(150, int(25 * fast.eff_spe() / slow.eff_spe())))
    assert B.variable_power("gyroball", slow, fast, moves, species) == want > 25
    assert B.variable_power("gyroball", slow, same, moves, species) == 25
    assert B.variable_power("gyroball", fast, slow, moves, species) < 25, \
        "a fast user's Gyro Ball is weak, not strong"
    assert B.variable_power("gyroball", fast, slow, moves, species) >= 1


# removing this lets the player's side be disarmed again. The leaders' movesets are authored, so the weight
# and speed moves reached them as soon as the power was computed; a player candidate only ever gets what
# choose_moveset picks, and it dropped every move Showdown stores at basePower 0. Croagunk learns Low Kick and
# Bronzor learns Gyro Ball off the level-up list, and a Fighting answer to a Rock gym is exactly the kind of
# thing the report exists to find.
def test_choose_moveset_picks_a_weight_or_speed_move_when_the_species_learns_one(pack):
    species, moves, chart = pack
    assert B.choose_moveset(species["croagunk"], 20, moves, chart).count("lowkick") == 1, \
        B.choose_moveset(species["croagunk"], 20, moves, chart)
    assert "gyroball" in B.choose_moveset(species["bronzor"], 20, moves, chart)
    # and nothing else with no power sneaks in: a status move is still not an attack
    for name in ("croagunk", "bronzor", "machop", "magby", "pikachu", "geodude"):
        for lvl in (20, 35, 50):
            for mid in B.choose_moveset(species[name], lvl, moves, chart):
                assert moves[mid]["power"] > 0 or mid in B.VARIABLE_NOMINAL, (name, lvl, mid)
    # the move it picked actually hurts something, computed from the real target rather than the nominal power
    frog = B.Mon(species, "croagunk", 20, moves, chart)
    onix = B.Mon(species, "onix", 20, moves, chart, moveset=[])
    assert "lowkick" in frog.moveset
    assert B.damage(frog, onix, "lowkick", moves, chart) > 0


# removing this lets a variable-power move go back to being a silent zero whenever a caller forgets to pass
# the dex. The dex travels on the Pokemon now, so there is no call shape that quietly disarms Grass Knot.
def test_a_variable_power_move_needs_no_dex_argument_from_the_caller(pack):
    species, moves, chart = pack
    raichu = B.Mon(species, "raichu", 50, moves, chart, moveset=["grassknot"])
    snorlax = B.Mon(species, "snorlax", 50, moves, chart, moveset=[])
    joltik = B.Mon(species, "joltik", 50, moves, chart, moveset=[])
    assert raichu.dex is species
    heavy = B.damage(raichu, snorlax, "grassknot", moves, chart)        # no species argument at all
    light = B.damage(raichu, joltik, "grassknot", moves, chart)
    assert heavy > 0 and light > 0 and heavy > light
    assert B.best_damage(raichu, snorlax, moves, chart)[0] == pytest.approx(heavy)
    assert B.duel(raichu, joltik, moves, chart)[0] is raichu


# ------------------------------------------------------------------ Intimidate

# removing this lets Intimidate stop landing, or land every turn instead of on the switch in. Arcanine brings
# it to Blaine's gym; an Intimidate that ticked each turn would wind a physical attacker down to nothing.
def test_intimidate_drops_the_opposing_attack_one_stage_on_entry(pack):
    chart = _chart(pack)
    scary = _M(SYNTH_MOVES, chart, "scary", ["normal"], ability="intimidate", moveset=["bonk"])
    victim = _M(SYNTH_MOVES, chart, "victim", ["normal"], moveset=["bonk"])
    B.switch_in(scary, victim)
    assert victim.stages["atk"] == -1
    assert victim.eff_atk() == int(victim.atk * 2 / 3)
    plain = _M(SYNTH_MOVES, chart, "plain", ["normal"], moveset=["bonk"])
    other = _M(SYNTH_MOVES, chart, "other", ["normal"], moveset=["bonk"])
    B.switch_in(plain, other)
    assert other.stages["atk"] == 0
    clear = _M(SYNTH_MOVES, chart, "clear", ["normal"], ability="clearbody", moveset=["bonk"])
    B.switch_in(scary, clear)
    assert clear.stages["atk"] == 0, "Clear Body did not refuse the drop"
    # and in a real run it lands exactly once, at the start, not on every turn of the fight
    player = _M(SYNTH_MOVES, chart, "player", ["normal"], moveset=["bonk"], speed=200)
    foe = _M(SYNTH_MOVES, chart, "foe", ["ghost"], ability="intimidate", moveset=["boo"], speed=1)
    B.run_gauntlet([player], [foe], SYNTH_MOVES, chart)
    assert player.stages["atk"] == -1, "Intimidate landed %d times" % -player.stages["atk"]


# ------------------------------------------------------------------ the switching bound

# removing this lets the switching bound switch for no reason. It is opt-in and the tool documents it as NOT
# trustworthy -- it came out worse than never switching at two of seven gyms -- so nothing here says it is
# good. What it does claim is soundness: it changes Pokemon only when the active one cannot win the matchup
# and the incoming one can. A bound that thrashes is measuring its own policy rather than the fight.
def test_the_switching_bound_only_swaps_a_losing_matchup_for_a_winning_one(pack):
    chart = _chart(pack)
    field = B.Field()

    def mon(name, types, mid):
        return _M(SYNTH_MOVES, chart, name, types, moveset=[mid])

    def pick(team, alive, active, foe):
        return B.best_matchup(team, alive, active, foe, SYNTH_MOVES, chart, field, None)

    water = mon("water", ["water"], "douse")
    fire = mon("fire", ["fire"], "flare")             # loses to Water both ways
    grass = mon("grass", ["grass"], "leafy")          # wins it both ways
    grass2 = mon("grass2", ["grass"], "leafy")
    team = [fire, grass, grass2]
    alive = [True, True, True]
    assert pick(team, alive, 0, water) in (1, 2), \
        "a losing active Pokemon was not swapped for a winning one"
    # already winning: stay in, even though an equally good Pokemon is on the bench
    assert pick(team, alive, 1, water) == 1
    # nobody wins it: do not spend a free hit on a switch that changes nothing
    doomed = [mon("f1", ["fire"], "flare"), mon("f2", ["fire"], "flare")]
    assert pick(doomed, [True, True], 0, water) == 0
    # a fainted team mate is never switched to
    assert pick(team, [True, False, False], 0, water) == 0


# removing this lets the gauntlet run past its guard, or lose count of what it did. The turn count is how the
# report tells a two-turn kill from a grind, and it silently returned the cap for every fight until the count
# was fixed (2026-09-23, caught by the Sturdy tests).
def test_the_gauntlet_reports_its_own_turns_and_switches(pack):
    chart = _chart(pack)
    a = _M(SYNTH_MOVES, chart, "a", ["normal"], moveset=["smash"], attack=200, speed=200)
    b = _M(SYNTH_MOVES, chart, "b", ["normal"], moveset=["tap"], defence=1, speed=1)
    stats = {}
    won, _f, _j, _left = B.run_gauntlet([a], [b], SYNTH_MOVES, chart, stats=stats)
    assert won and stats == {"turns": 1, "switches": 0}, stats
    # a grind is bounded by cap_turns and says so, rather than running away
    slow_a = _M(SYNTH_MOVES, chart, "slowa", ["normal"], moveset=["tap"], attack=1, defence=200, hp=255)
    slow_b = _M(SYNTH_MOVES, chart, "slowb", ["normal"], moveset=["tap"], attack=1, defence=200, hp=255)
    grind = {}
    won2, _f2, _j2, left2 = B.run_gauntlet([slow_a], [slow_b], SYNTH_MOVES, chart, cap_turns=5, stats=grind)
    assert grind["turns"] == 5 and not won2 and left2 > 0.5
    # and a switching run never exceeds its own switch budget
    water = _M(SYNTH_MOVES, chart, "water", ["water"], moveset=["douse"])
    team = [_M(SYNTH_MOVES, chart, "fire", ["fire"], moveset=["flare"]),
            _M(SYNTH_MOVES, chart, "grass", ["grass"], moveset=["leafy"])]
    sw = {}
    B.run_gauntlet(team, [water], SYNTH_MOVES, chart, switching=True, stats=sw)
    assert 0 <= sw["switches"] <= len(team) * 2
    assert sw["turns"] <= 500


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


# removing this lets the availability sidecar stop being usable -- a missing level band, an empty pool, a gym
# that lost its rows -- and the report would rank a shrinking candidate pool without saying so.
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
# Changed deliberately 2026-09-24: the owner set relativeLevelCap 0 in our overlay (modpack/config/rctmod-server.toml),
# which the simulation now reads; Cobbleverse's own file still says 5 (tests/test_rct_config_overlay.py).
def test_the_level_cap_comes_from_the_packs_own_rct_config():
    init, rel = B.level_caps(B.RCT_CONFIG)
    assert (init, rel) == (20, 0), "the RCT config the simulation reads no longer says initial 20, relative 0"


# removing this lets the trainers file the report reads drift out of the repository, which would turn every
# number above into a report about nothing.
def test_the_files_the_simulation_reads_are_the_repositorys_own():
    assert B.TRAINERS == ROOT / "data" / "trainers.json" and B.TRAINERS.is_file()
    assert B.AVAIL_JSON == ROOT / "derived" / "availability.json" and B.AVAIL_JSON.is_file()
    assert B.AVAILABILITY == ROOT / "docs" / "story" / "AVAILABILITY.md" and B.AVAILABILITY.is_file()
    assert B.RCT_CONFIG.is_file()
    assert json.loads(B.TRAINERS.read_text(encoding="utf-8"))["trainers"]
    assert B.WORLD_READS == set(), "battle_sim now reads a world: ground must not come from a world save"


# removing this lets the generator and the simulator keep two copies of the same name-normalisation rule.
# Two copies that must agree on both sides is exactly the shape of the bug that dropped both Nidoran: the
# sidecar spelled a name one way and the reader keyed it another, and neither said so.
def test_the_availability_generator_uses_the_simulators_own_normalisation():
    import availability as A
    jar = {"nidoranf": {"primaryType": "poison"}, "mrmime": {"primaryType": "psychic",
                                                             "secondaryType": "fairy"}}
    assert A.species_types(jar, "Nidoran♀") == ["poison"], \
        "the generator resolves gendered names differently from battle_sim.key"
    assert A.species_types(jar, "Mr. Mime") == ["psychic", "fairy"]
    assert A.species_types(jar, "Nidoran♂") is None, "both signs collapsed onto one id again"
    src = (ROOT / "tools" / "availability.py").read_text(encoding="utf-8")
    assert 'replace("♀"' not in src, "availability.py has its own copy of the gender-sign rule again"
