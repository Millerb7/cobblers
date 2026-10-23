"""docs/player/challenge.html (tools/player_guide_challenge.py): the cash at the mode choice and at each badge, the TMs given
with each, and the TM Case are the data's; the page links the battle guide and the training guide.

The expectations are read from data/challenge_mode.json (voucher.computed.schedule, tm_gifts.by_step, tm_gifts.case) and the TM
score table (docs/mechanics/TM_POWER_GATE.json) by this file, not from the generator's model.

Mutation: test_the_cash_check_bites changes the GENERATOR (collect is made to read each payment one step late) and shows this
file's check, which reads the schedule itself, reports the page.
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
import player_guide_challenge as PC  # noqa: E402

PAGE = ROOT / "docs" / "player" / "challenge.html"
STEPS = ["oak_mode_choice"] + ["gym%d_cleared" % n for n in range(1, 9)]


def _json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _text(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def _money(n):
    return "${:,}".format(n)


def _raw():
    assert PAGE.is_file(), "run python tools/player_guide_challenge.py"
    return PAGE.read_text(encoding="utf-8")


def _table(raw, key):
    sec = re.search(r'<section id="%s".*?</section>' % key, raw, re.S).group(0)
    return [[_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)] for tr in re.findall(r"<tr>(.*?)</tr>", sec, re.S)[1:]]


def cash_problems(raw):
    sched = {s["at"]: s["cash"] for s in _json("data/challenge_mode.json")["voucher"]["computed"]["schedule"]}
    rows = _table(raw, "cash")
    if len(rows) != len(STEPS):
        return ["%d cash rows, not %d" % (len(rows), len(STEPS))]
    return ["row %d (%s) reads %s, the schedule says %s" % (i, at, rows[i][1], _money(sched[at]))
            for i, at in enumerate(STEPS) if rows[i][1] != _money(sched[at])]


def test_the_filter_is_whole():
    assert FILTER.filter_problems(_raw()) == []


def test_the_cash_is_the_schedule():
    assert cash_problems(_raw()) == []
    d = _json("data/challenge_mode.json")["voucher"]["computed"]
    assert _money(d["total"]) in _text(_raw()), "the total is not stated"
    assert d["total"] == sum(s["cash"] for s in d["schedule"])


def test_every_gifted_tm_is_listed_with_its_move_at_its_step():
    """Each step's row names the move of every item the data gifts there, in the score table's own spelling."""
    gifts = _json("data/challenge_mode.json")["tm_gifts"]["by_step"]
    scores = _json("docs/mechanics/TM_POWER_GATE.json")["tms"]
    rows = _table(_raw(), "tms")
    assert len(rows) == len(STEPS)
    for i, at in enumerate(STEPS):
        cell = rows[i][2]
        got = [x.strip() for x in cell.split("),")]
        want = ["%s (%s" % (scores[it]["move"], scores[it]["type"]) for it in gifts[at]["items"]]
        assert len(got) == len(want), (at, cell)
        for g, w in zip(got, want):
            assert g.startswith(w), (at, g, w)


def test_the_tm_case_is_named_and_given_at_the_mode_choice():
    case = _json("data/challenge_mode.json")["tm_gifts"]["case"]
    assert case["at"] == "oak_mode_choice"
    assert "The %s" % case["name"] in _text(_raw())


def test_the_page_points_at_the_battle_and_training_guides():
    raw = _raw()
    assert 'href="battles.html"' in raw and 'href="training.html"' in raw and 'href="tms.html"' in raw


def test_the_cash_check_bites(monkeypatch):
    """A generator that reads each payment one step late produces a page this file's check rejects."""
    real = PC.doc

    def late(rel):
        d = real(rel)
        if rel == "data/challenge_mode.json":
            s = d["voucher"]["computed"]["schedule"]
            for i in range(len(s) - 1, 0, -1):
                s[i]["cash"] = s[i - 1]["cash"]
        return d
    monkeypatch.setattr(PC, "doc", late)
    assert cash_problems(PC.render(PC.collect())) != []


def test_the_page_is_current():
    import player_site
    ok, why = player_site.check(PAGE, PC.render(PC.collect()), PC.GUIDE)
    assert ok, why


def test_the_mode_is_described_in_the_series_wording_not_the_dialogue():
    """The series title and description are the data file's; the conversation (data/dialogue.json) is never quoted."""
    s = _json("data/challenge_mode.json")["series"]
    t = _text(_raw())
    assert s["title"] in t and s["description"] in t
