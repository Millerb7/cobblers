"""tools/challenge_guide.py on a fixture: the placement rule, which roster is live, the split/sidebar page, the page
contract, and that the contract check bites."""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import challenge_guide as CG  # noqa: E402
import nuzlocke_map as NM  # noqa: E402

MON = {"species": "geodude", "level": 18, "moveset": ["rocktomb", "bulldoze"], "ability": "rockhead",
       "heldItem": "oran_berry", "nature": "impish"}
HARD = {**MON, "level": 19, "moveset": ["rocktomb", "thunderpunch"], "heldItem": "berry_juice"}
ROUTES = [{"id": "r1", "order": 1, "display_name": "Route 1 — Pallet to Brock", "from_town": "hometown",
           "to_town": "gym1_town"},
          {"id": "vr", "order": 2, "display_name": "Victory Road — Brock to the League", "from_town": "gym1_town",
           "to_town": "league"},
          {"id": "lost", "order": 3, "display_name": "Route 9 — nowhere", "from_town": "gym1_town",
           "to_town": "a_hamlet"}]
TOWNS = {"hometown": "Pallet", "gym1_town": "Stoneford", "league": "The League"}


def rec(rid, cls, normal, challenge, live, **kw):
    return {"id": rid, "display_name": rid.title(), "class": cls, "format": "GEN_9_SINGLES", "team": live,
            "rct": {"team": live, "battleFormat": "GEN_9_SINGLES"},
            "modes": {"normal": {"team": normal, "strategy": "normal plan"},
                      "challenge": {"team": challenge, "strategy": "challenge plan", "open_line": ["krabby"]}}, **kw}


def fixture(live_team=None):
    leader = rec("gym_01_brock", "gym_leader", [MON], [MON, HARD], live_team or [MON], order=1, theme="Fault Line")
    e4 = rec("elite_01_lorelei", "elite_four", [HARD], [HARD], [HARD], order=1)
    champ = rec("champion_blue", "champion", [MON], [HARD], [MON], order=1)
    route = rec("route_01_trainer_01", "route", [MON], [HARD], [MON], route_id="r1", trainer_order=1,
                archetype="one_pokemon", lesson="a <lesson> & more",
                mode_intent={"normal": "learn", "challenge": "learn harder"})
    later = rec("route_01_trainer_02", "route", [MON], [HARD], [MON], route_id="r1", trainer_order=2)
    road = rec("vr_trainer_01", "route", [MON], [HARD], [MON], route_id="vr", trainer_order=1)
    pinned = rec("finale_grunt", "route", [MON], [HARD], [MON], split="hq")              # explicit split wins
    stray = rec("rival_1", "rival", [MON], [HARD], [MON])                                 # no rule matches
    bad_route = rec("route_x", "route", [MON], [HARD], [MON], route_id="nowhere")
    bad_split = rec("route_y", "route", [MON], [HARD], [MON], route_id="r1", split=5)
    dead_end = rec("route_z", "route", [MON], [HARD], [MON], route_id="lost")
    recs = [champ, e4, leader, later, route, road, pinned, stray, bad_route, bad_split, dead_end]
    guard = {"id": "mansion_guardian_1", "display_name": "Channeler Hope", "team": [MON], "rct": {"team": [MON]}}
    seat_of = {"route_01_trainer_01": {"seat": [1, 2, 3], "eye_contact": True, "sight_distance": 7.0,
                                       "why": "the eye-contact lesson"},
               "mansion_guardian_1": {**guard, "seat": [4, 5, 6], "eye_contact": True, "unavoidable": "the only door"}}
    gyms = [{"rec": leader, "n": 1, "town_id": "gym1_town", "town": "Stoneford", "x": 1832, "z": 3696, "type": "Rock",
             "theme": "Fault Line", "format": "GEN_9_SINGLES", "cap": 20, "upstream": "kanto_brock"}]
    side = [(guard, {"split": 1, "area": "The Gastly mansion", "note": "five"})]
    splits, unplaced = CG.build_splits(recs, seat_of, ROUTES, gyms,
                                       {"elite_01_lorelei": {"type": "Ice", "format": "GEN_9_SINGLES"}},
                                       {1: (20, "Brock"), 2: (60, "Lorelei")}, side, lambda t: TOWNS.get(t, t))
    tally = {"normal": 0, "challenge": 0, "both": 0, None: 0}
    for r in recs:
        tally[CG.live_mode(r)] += 1
    return {"splits": splits, "unplaced": unplaced, "league_at": {"x": 4000, "z": 5000}, "tally": tally,
            "records": len(recs), "contract": "not implemented; top-level team and rct mirror normal",
            "emitter": ["tools/route_trainers.py:364"], "init_cap": 5, "rel_cap": 0, "nm_style": NM.STYLE}


def page_of(model=None):
    return CG.render(model or fixture(), CG.Names(None))


class Balance(HTMLParser):
    VOID = CG.VOID

    def __init__(self):
        super().__init__()
        self.stack, self.bad = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.bad.append(tag)


def ids_of(fights):
    return [f["rec"]["id"] for f in fights]


def test_live_mode_reads_the_emitted_team():
    leader = rec("b", "gym_leader", [MON], [MON, HARD], [MON])
    assert CG.live_mode(leader) == "normal"
    assert CG.live_mode(rec("e", "elite_four", [HARD], [HARD], [HARD])) == "both"   # placeholder
    assert CG.live_mode(rec("x", "route", [MON], [HARD], [HARD])) == "challenge"
    assert CG.live_mode(rec("y", "route", [MON], [HARD], [{**MON, "level": 99}])) is None


def test_every_fight_lands_by_the_rule_and_none_is_dropped():
    m = fixture()
    by = {s["key"]: s for s in m["splits"]}
    assert [s["key"] for s in m["splits"]] == ["1", "hq", "endgame"]                  # travel order
    # route trainers by trainer_order, then the side area, then the leader last
    assert ids_of(by["1"]["fights"]) == ["route_01_trainer_01", "route_01_trainer_02", "mansion_guardian_1",
                                          "gym_01_brock"]
    assert ids_of(by["hq"]["fights"]) == ["finale_grunt"]
    # the road to the League first, then the Elite Four, then the Champion
    assert ids_of(by["endgame"]["fights"]) == ["vr_trainer_01", "elite_01_lorelei", "champion_blue"]
    reasons = {f["rec"]["id"]: f["reason"] for f in m["unplaced"]}
    assert set(reasons) == {"rival_1", "route_x", "route_y", "route_z"}
    assert "no route_id and no split" in reasons["rival_1"]
    assert "not in data/routes.json" in reasons["route_x"]
    assert "split 5" in reasons["route_y"]                                             # a bad split is not ignored
    assert "a_hamlet" in reasons["route_z"]
    placed = sum(len(s["fights"]) for s in m["splits"]) + len(m["unplaced"])
    assert placed == 12                                                                # 11 records + 1 guardian
    assert by["1"]["cap"] == (20, "Brock") and by["endgame"]["cap"] == (60, "Lorelei")
    assert by["1"]["title"] == "Split 1: Pallet → Stoneford"
    assert by["endgame"]["title"] == "End game: Victory Road and the League"


def test_fixture_page_meets_the_contract():
    page = page_of()
    assert CG.page_problems(page) == []
    p = Balance()
    p.feed(page)
    assert p.bad == [] and p.stack == []
    assert page.startswith("<title>Challenge Mode Trainers</title>")
    assert "In game today every trainer uses its Normal team." in page
    assert "Map: see the Region Nuzlocke Map page" in page
    assert "placeholder, identical to Normal" in page                  # the E4 fixture
    assert "One team: no Challenge version authored" in page          # the guardian
    assert "Battles on sight (7 blocks)" in page and "x 1, y 2, z 3" in page
    assert "a &lt;lesson&gt; &amp; more" in page                      # escaped
    assert NM.STYLE.split("*{box-sizing")[0] in page                  # the map page's tokens and fonts
    assert 'class="m-ch"' in page and 'class="c-no"' in page
    assert "Rocktomb, Bulldoze" in page and "No Cobblemon jar was found" in page
    assert "How fights are placed" in page and "re-run <code>python tools/challenge_guide.py</code>" in page
    assert 'id="split-unplaced"' in page and "no route_id and no split" in page


def test_splits_and_sidebar():
    m = fixture()
    page = page_of(m)
    ids = set(re.findall(r' id="([^"]+)"', page))
    for s in m["splits"]:
        assert 'id="split-%s"' % s["key"] in page and 'href="#split-%s"' % s["key"] in page
    for f in [f for s in m["splits"] for f in s["fights"]] + m["unplaced"]:
        assert 'href="#fight-%s"' % f["rec"]["id"] in page
    assert all(h in ids for h in re.findall(r'href="#([^"]+)"', page))    # every sidebar entry lands somewhere
    assert '<nav class="nav" id="nav" aria-label="Fights by split">' in page
    assert re.search(r'<details class="drawer" id="drawer" open>', page)    # open without JS: plain links
    assert "IntersectionObserver" in page
    sec = page[page.index('id="split-1"'):page.index('id="split-hq"')]
    assert 'class="gymline"' in sec and "Cap Lv 20" in sec


def test_every_gym_leader_has_a_team_table():
    m = fixture()
    page = page_of(m)
    leaders = [s["gym"]["rec"]["id"] for s in m["splits"] if s.get("gym")]
    assert leaders
    for lid in leaders:
        row = page[page.index('<tr class="tm" id="team-%s">' % lid):]
        row = row[:row.index("</section>")]                              # the leader is the split's last fight
        assert row.count('<table class="team stk">') == 2                # Challenge and Normal, toggled
        assert "<caption>Gym_01_Brock: Challenge team</caption>" in row
        assert '<th scope="col">Moves</th>' in row


def test_toggle_defaults_to_challenge():
    page = page_of()
    assert '<main class="cg" id="cg" data-mode="challenge">' in page
    assert '<button type="button" data-m="challenge" aria-pressed="true">' in page
    assert '<button type="button" data-m="normal" aria-pressed="false">' in page
    assert '.cg:not([data-mode="normal"]) .m-no' in page                 # Normal tables hidden at rest


def test_status_follows_the_emitted_team():
    page = page_of(fixture(live_team=[MON, HARD]))                    # leader's rct now carries Challenge
    assert "In game today every trainer uses its Normal team." not in page
    assert "live roster is mixed" in page


@pytest.mark.parametrize("breakage, finding", [
    (lambda p: "<!doctype html>" + p, "<title>"),
    (lambda p: p.replace("<main", "<body><main", 1), "<body>"),
    (lambda p: p + '<link href="https://example.com/x.css">', "external reference"),
    (lambda p: p.replace("*{box-sizing:border-box}", "*{box-sizing:border-box;color:#ff0000}", 1), "literal colour"),
    (lambda p: p.replace("</main>", "", 1), "unclosed"),
    (lambda p: p + '<script src="x.js"></script>', "external script"),
    (lambda p: p.replace("--zebra:#e9eee5", "--zebra:#1b2830", 1), "contrast: light --ink on --zebra"),
    (lambda p: p.replace("--sight:#ff8a96", "--sight:#3a1015", 1), "contrast: dark (system) --sight"),
    (lambda p: p.replace("--sight:#ff8a96", "--sight:#3a1015"), "contrast: dark --sight"),
    (lambda p: p.replace('id="split-1"', 'id="split 1"', 1), "not a bare token"),
])
def test_contract_check_bites(breakage, finding):
    page = breakage(page_of())
    assert any(finding in b for b in CG.page_problems(page)), CG.page_problems(page)
