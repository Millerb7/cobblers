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
