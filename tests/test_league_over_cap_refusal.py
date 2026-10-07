"""The Elite Four and the Champion refuse an over-cap player, in both modes: the offline half of the proof
(docs/UNFINISHED_SWEEP_2026-10-06.md section 3, U10; the owner asked for it "same class as Giovanni was").

rctmod refuses a battle in `TrainerMob.canBattleAgainst` when the player's highest level is over their level cap
(v0.19.0-beta source, read in that section; not re-read here). That check runs for every rctmod trainer entity, so
the refusal holds at a boss exactly when: the boss is an rctmod trainer stood by an rctmod spawner; it is a
REQUIRED, non-optional member of the player's series with a predecessor (rctmod's getNext skips optional and
edge-less nodes, so such a boss would never set the cap); and the cap a player meets there is below 100. These tests
assert exactly those properties from the built trainers pack, the upstream snapshot and our rctmod config, for the
five League ids and their five `_challenge` twins, with the cap computed here from LevelUtils as quoted in
docs/research/RCT_PER_PLAYER_MODE.md section 3 (not from any repository tool).

What only a player in game can prove: that the installed jar behaves as the source reads; that the League template's
five spawners stand in the world and spawn these ids; that our team override is the team rctmod loads; and the
refusal itself (the 5-minute staging test in the sweep's section 3: a party at cap + 1 at each member, then at cap).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import challenge_mode_audit as A  # noqa: E402
import route_trainers as RT  # noqa: E402

CM_DATA = json.loads((ROOT / "data" / "challenge_mode.json").read_text(encoding="utf-8"))
SFX = CM_DATA["id_suffix"]
CH_SERIES = CM_DATA["series"]["id"]
LEAGUE = [t["upstream_trainer_id"] for t in sorted(
    json.loads((ROOT / "data" / "league_trainers.json").read_text(encoding="utf-8"))["trainers"],
    key=lambda t: t["order"])]
CONFIG = ROOT / "modpack" / "config" / "rctmod-server.toml"


def cfg(key):
    return A.toml_value(CONFIG, key)


@pytest.fixture(scope="module")
def built():
    return RT.files()


@pytest.fixture(scope="module")
def up():
    try:
        return A.Upstream()
    except FileNotFoundError as e:
        pytest.skip("the local server snapshot is not here: %s" % e)


def top(team):
    return max(m["level"] for m in team["team"])


def trainer_level(tid, mob_of, team_of, series_rel, config_rel, memo):
    """LevelUtils.trainerLevel: max(clamp(highest team level + relativeLevelCap), max over requiredDefeats of the
    same), relativeLevelCap from the mob first, then the series file, then the config."""
    if tid not in memo:
        mob = mob_of(tid)
        rel = mob.get("relativeLevelCap", series_rel if series_rel is not None else config_rel)
        own = min(100, max(0, top(team_of(tid)) + rel))
        reqs = [r for group in mob.get("requiredDefeats") or [] for r in group]
        memo[tid] = max([own] + [trainer_level(r, mob_of, team_of, series_rel, config_rel, memo) for r in reqs])
    return memo[tid]


# Without it the trainers pack could pin a different rctmod than the one whose canBattleAgainst was read, and every
# claim below would rest on another version's source.
def test_the_pinned_rctmod_is_the_version_whose_refusal_was_read():
    text = (ROOT / "modpack" / "manifest" / "overlay.json").read_text(encoding="utf-8")
    assert set(re.findall(r"rctmod-fabric-[^\"/]+\.jar", text)) == {"rctmod-fabric-1.21.1-0.19.0-beta.jar"}


# Without it a config change could start new players outside Kanto or move the cap offset, and the caps below would
# be computed for a player who does not exist.
def test_players_start_in_kanto_with_the_config_offsets_the_caps_assume():
    assert cfg("initialSeries").strip('"') == "kanto"
    assert float(cfg("relativeLevelCap")) == 0
    assert int(float(cfg("initialLevelCap"))) == 20


# Without it an override could replace a League boss's mob file and drop it from Kanto, make it optional or cut its
# chain, and its over-cap gate would stop applying (getNext skips optional and edge-less nodes).
def test_the_league_five_stay_required_members_of_kanto(built, up):
    prev = "kanto_giovanni"
    for tid in LEAGUE:
        assert "data/rctmod/mobs/trainers/single/%s.json" % tid not in built, "%s: we override its mob file" % tid
        mob = up.mobs[tid]
        assert "kanto" in (mob.get("series") or []), tid
        assert not mob.get("optional"), tid
        assert [prev] in (mob.get("requiredDefeats") or []), (tid, mob.get("requiredDefeats"))
        prev = tid
    assert "data/rctmod/series/kanto.json" not in built


# Without it a Challenge twin could be optional, seriesless or chain-less: a Challenge player would meet a League
# boss whose cap gate never applies.
def test_the_five_twins_are_required_members_of_the_challenge_series(built):
    prev = "kanto_giovanni" + SFX
    for tid in LEAGUE:
        mob = built["data/rctmod/mobs/trainers/single/%s.json" % (tid + SFX)]
        assert mob.get("series") == [CH_SERIES], tid
        assert not mob.get("optional"), tid
        assert mob.get("requiredDefeats") == [[prev]], (tid, mob.get("requiredDefeats"))
        prev = tid + SFX
    series = built["data/rctmod/series/%s.json" % CH_SERIES]
    assert "initialLevelCap" not in series and "relativeLevelCap" not in series


# Without it a team or offset change could lift a League cap to 100 (a level-100 party walks in) or split the two
# modes' caps. Computed from LevelUtils over the whole chain from Brock, from the built teams and mob files.
def test_the_cap_at_each_league_boss_is_below_100_and_the_same_in_both_modes(built, up):
    conf = float(cfg("relativeLevelCap"))
    team = lambda t: built.get("data/rctmod/trainers/%s.json" % t) or pytest.fail("no built team for %s" % t)
    normal = lambda t: up.mobs[t]
    twin = lambda t: built["data/rctmod/mobs/trainers/single/%s.json" % t]
    srel_n = (up.series_files.get("kanto") or {}).get("relativeLevelCap")
    srel_c = built["data/rctmod/series/%s.json" % CH_SERIES].get("relativeLevelCap")
    mn, mc = {}, {}
    caps = []
    for tid in LEAGUE:
        n = trainer_level(tid, normal, team, srel_n, conf, mn)
        c = trainer_level(tid + SFX, twin, team, srel_c, conf, mc)
        assert n == c, "%s: Normal cap %d, Challenge cap %d" % (tid, n, c)
        assert n < 100, "%s: cap %d, so a level-100 party is not refused" % (tid, n)
        caps.append(n)
    # relayed from docs/mechanics/LEAGUE_LEVEL_CAP.md (60 through Lance, 62 at Blue); recomputed here
    assert caps == [60, 60, 60, 60, 62], caps


# Without it a boss could stand as a Cobblemon NPC or a summoned mob instead of a spawner's rctmod trainer, and
# canBattleAgainst would never be asked (the HQ fights, N57).
def test_all_ten_are_stood_by_an_rctmod_trainer_spawner(built, up):
    _size, cells = up.template("kanto_league")
    in_template = {i for s in cells.values() if A.bname(s) == A.SPAWNER for i in A.spawner_ids(s)}
    assert set(LEAGUE) <= in_template, set(LEAGUE) - in_template
    text = "\n".join("\n".join(v) if isinstance(v, list) else str(v)
                     for k, v in built.items() if k.endswith(".mcfunction"))
    for tid in LEAGUE:
        cid = tid + SFX
        assert re.search(r'rctmod:trainer_spawner\{TrainerIds:\["%s"\]\}' % cid, text) \
            or re.search(r'data merge block -?\d+ -?\d+ -?\d+ \{TrainerIds:\["%s"\]\}' % cid, text), cid


# Without it a refused player would get silence: every one of the ten says the over_level_cap line.
def test_all_ten_say_why_they_refuse_an_over_cap_player(built):
    for tid in LEAGUE:
        for i in (tid, tid + SFX):
            d = built["data/rctmod/dialogs/trainers/single/%s.json" % i]
            assert d.get("over_level_cap"), i
