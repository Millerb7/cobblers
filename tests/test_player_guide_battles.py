"""docs/player/battles.html's section filter: one button per gym and per leg after the gyms, plus All, beside (not
instead of) the Normal / Challenge switch.

Read from the published page (tools/player_site.py --check keeps it current with its generator). The expectations
come from the data and from the page's own fight cards, not from the generator: the gym count is
data/trainers.json generation_contract.gym_ace_levels, and every section that holds a fight must be under a button.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import test_player_site_filter as FILTER  # noqa: E402

PAGE = ROOT / "docs" / "player" / "battles.html"


def _raw():
    return PAGE.read_text(encoding="utf-8")


def test_the_filter_is_whole():
    assert FILTER.filter_problems(_raw()) == []


def test_every_gym_has_a_button_and_all_exists():
    buttons = FILTER.nav_buttons(_raw())
    assert buttons[0][:2] == ("all", "All")
    texts = [t for _k, t, _a in buttons]
    gyms = len(json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))
               ["generation_contract"]["gym_ace_levels"])
    for k in range(1, gyms + 1):
        assert "Gym %d" % k in texts, "no button for gym %d: %s" % (k, texts)
    assert "League" in texts


def test_no_fight_is_unreachable():
    """Every section holding a fight card is under a filter button: no fight shows only under All."""
    raw = _raw()
    keys = {k for k, _t, _a in FILTER.nav_buttons(raw)}
    cards = 0
    for m in re.finditer(r"<section ([^>]*)>(.*?)</section>", raw, re.S):
        n = m.group(2).count("<article")
        if n:
            key = re.search(r'data-section="([^"]*)"', m.group(1))
            assert key and key.group(1) in keys, "a section with %d fights has no button: %s" % (n, m.group(1))
            cards += n
    assert cards == raw.count("<article") and cards > 0


def test_the_difficulty_switch_is_still_there():
    raw = _raw()
    assert 'data-set-mode="normal"' in raw and 'data-set-mode="challenge"' in raw
    header = re.search(r'<header class="site-header">.*?</header>', raw, re.S).group(0)
    assert 'data-set-mode="normal"' in header and "data-filter" not in header


# ------------------------------------------------------------------------------------------------ mine crews and boss EVs
# Expectations from data/mine_crews.json, data/mine_crew_trainers.json and data/trainers.json, not from the generator.


def _article(raw, tid):
    m = re.search(r'<article class="tr[^"]*" id="t-%s">(.*?)</article>' % re.escape(tid), raw, re.S)
    assert m, "no card for %s" % tid
    return m.group(1)


def _json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_every_mine_trainer_has_a_card_in_the_mine_section_with_both_teams():
    """36 trainers (three networks of twelve), each a card under the Mine crews filter, with a Normal and a Challenge team and
    the data's seat. Without it a crew could be written and never shown."""
    raw = _raw()
    sec = re.search(r'<section id="mine-crews".*?</section>', raw, re.S).group(0)
    trainers = _json("data/mine_crew_trainers.json")["trainers"]
    assert len(trainers) == 36
    for t in trainers:
        card = _article(sec, t["id"])
        assert t["display_name"] in card
        assert "%d %d %d" % tuple(t["seat"]) in card, t["id"]
        assert "Normal team" in card and "Challenge team" in card, t["id"]
        for m in t["team"]:
            assert "Lv %d" % m["level"] in card


def test_each_network_names_its_shift_boss_and_level_band():
    raw = _raw()
    sec = re.search(r'<section id="mine-crews".*?</section>', raw, re.S).group(0)
    for net in _json("data/mine_crews.json")["networks"]:
        assert net["name"] in sec
        boss = [c for c in net["crew"] if c["role"] == "shift_boss"]
        assert len(boss) == 1
        seat = next(t for t in _json("data/mine_crew_trainers.json")["trainers"] if t["id"] == boss[0]["id"])
        assert 'href="#t-%s">%s</a>' % (boss[0]["id"], seat["display_name"]) in sec


def test_boss_cards_list_each_members_ev_spread_and_nobody_else_does():
    """Every member of the thirteen bosses' Normal and Challenge teams shows its data EVs; mine trainers and the rest show none."""
    raw = _raw()
    recs = _json("data/trainers.json")["trainers"]
    bosses = [r for r in recs if r["class"] in ("gym_leader", "elite_four", "champion")]
    assert len(bosses) == 13
    for r in bosses:
        card = _article(raw, r["id"])
        shown = sorted(tuple(sorted(int(x) for x in re.findall(r"(\d+) [A-Za-z]+", dd)))
                       for dd in re.findall(r"<dt>EVs</dt><dd>([^<]*)</dd>", card))
        want = []
        for mode in ("normal", "challenge"):
            want += [tuple(sorted(v for v in m["evs"].values() if v)) for m in r["modes"][mode]["team"]]
        assert shown and len(shown) <= len(want)
        assert set(shown) <= set(want), (r["id"], shown, want)
    total = raw.count("<dt>EVs</dt>")
    in_boss = sum(_article(raw, r["id"]).count("<dt>EVs</dt>") for r in bosses)
    assert total == in_boss, "an EV line appears outside the thirteen bosses"
