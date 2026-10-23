"""docs/player/training.html (tools/player_guide_training.py): the eight coaches, the three services and the price of each at
every badge count are the data's, and the worked examples are those prices multiplied out.

The expectations are read from data/training_services.json by this file, not from the generator's model: the coaches are its
`keepers`, the prices its `price_by_tier` / `price_per_stat_by_tier`, the caps its price_rule. The worked examples are summed
here from the same price fields with this file's own arithmetic.

Mutation: test_the_example_check_bites changes the GENERATOR (team_cost is told one more dollar per Pokemon) and shows this
file's check, which does not call it, reports the page.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import test_player_site_filter as FILTER  # noqa: E402
import player_guide_training as PT  # noqa: E402

PAGE = ROOT / "docs" / "player" / "training.html"


def _json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _text(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def _money(n):
    return "${:,}".format(n)


def _raw():
    assert PAGE.is_file(), "run python tools/player_guide_training.py"
    return PAGE.read_text(encoding="utf-8")


def _price_rows(raw):
    """{badges held: [cap, raise, ev, one stat, six stats] as page text} from the price table."""
    sec = re.search(r'<section id="prices".*?</section>', raw, re.S).group(0)
    out = {}
    for tr in re.findall(r"<tr>(.*?)</tr>", sec, re.S)[1:]:
        cells = [_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        first = cells[0]
        n = 0 if first.startswith("no badge") else int(first.split()[0])
        out[n] = cells[1:]
    return out


def example_problems(raw):
    """The worked examples against the data's own price fields; [] when they agree."""
    ts = _json("data/training_services.json")
    sv = ts["services"]
    raise_p = {int(k): v for k, v in sv["raise"]["price_by_tier"].items()}
    ev_p = {int(k): v for k, v in sv["ev"]["price_by_tier"].items()}
    iv_p = {int(k): v for k, v in sv["iv"]["price_per_stat_by_tier"].items()}
    cap = {int(k): v for k, v in ts["price_rule"]["cap_by_badges_held"].items()}
    text = _text(re.search(r'<section id="examples".*?</section>', raw, re.S).group(0))
    one = (raise_p[1], ev_p[1], 6 * iv_p[1])
    team = (6 * raise_p[5], 6 * ev_p[5], 36 * iv_p[5])
    want = ["Raised to your cap of %d: %s" % (cap[1], _money(one[0])), "Its effort trained: %s" % _money(one[1]),
            "All six stats perfected: %s" % _money(one[2]), "All three together: %s" % _money(sum(one)),
            "Six raises to your cap of %d at %s each: %s" % (cap[5], _money(raise_p[5]), _money(team[0])),
            "Six effort plans at %s each: %s" % (_money(ev_p[5]), _money(team[1])),
            "Thirty-six stats perfected at %s each: %s" % (_money(iv_p[5]), _money(team[2])),
            "All of it: %s" % _money(sum(team))]
    return [w for w in want if w not in text]


def test_the_filter_is_whole():
    assert FILTER.filter_problems(_raw()) == []


def test_every_coach_is_listed_with_the_data_position():
    """Eight coaches, each by name with the keeper's own x y z. Without this a re-seated coach would stay at the old spot."""
    raw = _raw()
    keepers = _json("data/training_services.json")["keepers"]
    assert len(keepers) == 8
    sec = _text(re.search(r'<section id="coaches".*?</section>', raw, re.S).group(0))
    for k in keepers:
        assert "%s" % k["name"] in sec, k["name"]
        assert "%d %d %d" % tuple(k["at"]) in sec, (k["name"], k["at"])


def test_every_price_at_every_badge_count_is_the_data_s():
    ts = _json("data/training_services.json")
    sv = ts["services"]
    rows = _price_rows(_raw())
    assert sorted(rows) == list(range(9))
    for t in range(9):
        want = [str(ts["price_rule"]["cap_by_badges_held"][str(t)]),
                _money(sv["raise"]["price_by_tier"][str(t)]), _money(sv["ev"]["price_by_tier"][str(t)]),
                _money(sv["iv"]["price_per_stat_by_tier"][str(t)]), _money(6 * sv["iv"]["price_per_stat_by_tier"][str(t)])]
        assert rows[t] == want, (t, rows[t], want)


def test_the_worked_examples_are_the_prices_multiplied_out():
    assert example_problems(_raw()) == []


def test_the_example_check_bites(monkeypatch):
    """A generator that mis-adds the team cost produces a page this file's own arithmetic rejects."""
    real = PT.team_cost
    monkeypatch.setattr(PT, "team_cost", lambda m, tier, size=6: tuple(x + 1 for x in real(m, tier, size)))
    assert example_problems(PT.render(PT.collect())) != []


def test_the_page_is_current():
    """The published page is what the generator writes today (but for its generated-on line)."""
    import player_site
    ok, why = player_site.check(PAGE, PT.render(PT.collect()), PT.GUIDE)
    assert ok, why


def test_no_design_notes_reach_the_page():
    """The page states prices and services, not the owner's decisions or the superseded rules."""
    t = _text(_raw()).lower()
    for word in ("superseded", "the owner", "arbitrage", "exp-062"):
        assert word not in t, word
