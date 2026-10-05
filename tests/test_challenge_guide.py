"""tools/challenge_guide.py on a fixture: which roster is live, the page contract, and that the contract check bites."""

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


def rec(rid, cls, normal, challenge, live, **kw):
    return {"id": rid, "display_name": rid.title(), "class": cls, "format": "GEN_9_SINGLES", "team": live,
            "rct": {"team": live, "battleFormat": "GEN_9_SINGLES"},
            "modes": {"normal": {"team": normal, "strategy": "normal plan"},
                      "challenge": {"team": challenge, "strategy": "challenge plan", "open_line": ["krabby"]}}, **kw}


def model(live_team=None):
    leader = rec("gym_01_brock", "gym_leader", [MON], [MON, HARD], live_team or [MON], order=1, theme="Fault Line")
    e4 = rec("elite_01_lorelei", "elite_four", [HARD], [HARD], [HARD], order=1)
    route = rec("route_01_trainer_01", "route", [MON], [HARD], [MON], route_id="r1", trainer_order=1,
                archetype="one_pokemon", lesson="a <lesson> & more",
                mode_intent={"normal": "learn", "challenge": "learn harder"})
    guard = {"id": "mansion_guardian_1", "display_name": "Channeler Hope", "team": [MON], "rct": {"team": [MON]}}
    tally = {"normal": 0, "challenge": 0, "both": 0, None: 0}
    for r in (leader, e4, route):
        tally[CG.live_mode(r)] += 1
    return {"gyms": [{"rec": leader, "n": 1, "town": "Stoneford", "x": 1832, "z": 3696, "type": "Rock",
                      "theme": "Fault Line", "format": "GEN_9_SINGLES", "cap": 20, "upstream": "kanto_brock"}],
            "league": [{"rec": e4, "type": "Ice", "format": "GEN_9_SINGLES", "upstream": "kanto_league_lorelei"}],
            "league_at": {"x": 4000, "z": 5000},
            "routes": [{"key": "r1", "title": "Route 1", "from": "Pallet", "to": "Stoneford", "cap": (20, "Brock"),
                        "note": None,
                        "trainers": [(route, {"seat": [1, 2, 3], "eye_contact": True, "sight_distance": 7.0,
                                              "why": "the eye-contact lesson"})]},
                       {"key": "mansion", "title": "Mansion", "from": None, "to": None, "cap": (20, "Brock"),
                        "note": "five", "trainers": [(guard, {"seat": [4, 5, 6], "eye_contact": True,
                                                              "unavoidable": "the only door"})]}],
            "tally": tally, "records": 3, "contract": "not implemented; top-level team and rct mirror normal",
            "emitter": ["tools/route_trainers.py:364"], "init_cap": 5, "rel_cap": 0, "nm_style": NM.STYLE}


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


def test_live_mode_reads_the_emitted_team():
    m = model()
    assert CG.live_mode(m["gyms"][0]["rec"]) == "normal"
    assert CG.live_mode(m["league"][0]["rec"]) == "both"          # placeholder: challenge == normal
    hard = rec("x", "route", [MON], [HARD], [HARD])
    assert CG.live_mode(hard) == "challenge"
    assert CG.live_mode(rec("y", "route", [MON], [HARD], [{**MON, "level": 99}])) is None


def test_fixture_page_meets_the_contract():
    page = CG.render(model(), CG.Names(None))
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
    # Challenge in full at rest, Normal compact beside it
    assert 'class="m-ch"' in page and 'class="c-no"' in page
    # no jar: ids title-cased and the page says so
    assert "Rocktomb" in page and "No Cobblemon jar was found" in page


def test_status_follows_the_emitted_team():
    page = CG.render(model(live_team=[MON, HARD]), CG.Names(None))   # leader's rct now carries Challenge
    assert "In game today every trainer uses its Normal team." not in page
    assert "live roster is mixed" in page


@pytest.mark.parametrize("breakage, finding", [
    (lambda p: "<!doctype html>" + p, "<title>"),
    (lambda p: p.replace("<main", "<body><main", 1), "<body>"),
    (lambda p: p + '<link href="https://example.com/x.css">', "external reference"),
    (lambda p: p.replace("*{box-sizing:border-box}", "*{box-sizing:border-box;color:#ff0000}", 1), "literal colour"),
    (lambda p: p.replace("</main>", "", 1), "unclosed"),
    (lambda p: p + '<script src="x.js"></script>', "external script"),
])
def test_contract_check_bites(breakage, finding):
    page = breakage(CG.render(model(), CG.Names(None)))
    assert any(finding in b for b in CG.page_problems(page)), CG.page_problems(page)
