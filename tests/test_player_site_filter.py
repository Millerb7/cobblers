"""The shared section filter of docs/player/ (markup from tools/player_site.py filter_nav and section_attr, behaviour in
docs/player/assets/site.js, look in docs/player/assets/site.css), checked as markup and as a contract between the
three. `filter_problems()` is the check the per-page tests (starters, battles, items) call on their own page.

What a page owes its reader:
  - one <nav data-filter-nav> with an "All" button (data-filter="all", pressed) and one button per filterable section;
  - every button's key is a section's id AND its data-section, and every data-section has a button: no section is
    reachable only by "All", and no button shows nothing;
  - buttons are <button type="button"> with aria-pressed, so a keyboard and a screen reader can use them;
  - without JavaScript every section shows: no section is hidden in the markup, and the stylesheet hides the nav only
    under .nojs.

Not checked here: the script's behaviour in a browser. That needs a person (or a headless browser) clicking.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs" / "player"


def nav_buttons(raw):
    """[(key, text, attrs)] of the filter nav's buttons, or None when the page has no filter nav."""
    navs = re.findall(r"<nav [^>]*data-filter-nav[^>]*>(.*?)</nav>", raw, re.S)
    if not navs:
        return None
    assert len(navs) == 1, "a page has one filter nav, this one has %d" % len(navs)
    return [(m.group(2), html.unescape(re.sub(r"<[^>]+>", "", m.group(3))).strip(), m.group(1))
            for m in re.finditer(r'<button([^>]*data-filter="([^"]*)"[^>]*)>(.*?)</button>', navs[0], re.S)]


def sections(raw):
    """{key: the opening tag} of every element carrying data-section."""
    return {m.group(2): m.group(0) for m in re.finditer(r'<(\w+)\b[^>]*\bdata-section="([^"]*)"[^>]*>', raw)}


def filter_problems(raw):
    out = []
    buttons = nav_buttons(raw)
    if buttons is None:
        return ["no filter nav"]
    keys = [k for k, _t, _a in buttons]
    if keys[:1] != ["all"] or keys.count("all") != 1:
        out.append("the first button, and only the first, must be All (data-filter=\"all\"): %s" % keys)
    for k, text, attrs in buttons:
        if 'type="button"' not in attrs or "aria-pressed=" not in attrs:
            out.append("button %r is not a type=button with aria-pressed" % k)
        if not text:
            out.append("button %r has no text" % k)
    if buttons and buttons[0][0] == "all" and 'aria-pressed="true"' not in buttons[0][2]:
        out.append("All is not pressed when the page loads")
    if len(set(keys)) != len(keys):
        out.append("repeated keys: %s" % keys)
    secs = sections(raw)
    for k in keys[1:]:
        tag = secs.get(k)
        if tag is None:
            out.append("button %r shows no section" % k)
        elif 'id="%s"' % k not in tag:
            out.append("section %r's id is not its key, so #%s does not link to it" % (k, k))
    for k, tag in secs.items():
        if k not in keys:
            out.append("section %r has no button: only All reaches it" % k)
        if re.search(r"\shidden\b", tag):
            out.append("section %r is hidden in the markup: without JavaScript it would never show" % k)
    return out


def test_the_check_bites():
    good = ('<nav class="filter" data-filter-nav aria-label="x"><button type="button" data-filter="all" '
            'aria-pressed="true">All</button><button type="button" data-filter="a" aria-pressed="false">A</button>'
            '</nav><section id="a" data-section="a"></section>')
    assert filter_problems(good) == []
    assert filter_problems(good.replace('data-filter="a"', 'data-filter="b"'))  # a button that shows nothing
    assert filter_problems(good + '<section id="c" data-section="c"></section>')  # a section only All reaches
    assert filter_problems(good.replace('<section id="a"', '<section id="a" hidden'))
    assert filter_problems(good.replace('data-filter="all"', 'data-filter="every"'))
    assert filter_problems("<p>no nav</p>") == ["no filter nav"]


def test_the_script_and_the_stylesheet_carry_the_contract():
    js = (SITE / "assets" / "site.js").read_text(encoding="utf-8")
    css = (SITE / "assets" / "site.css").read_text(encoding="utf-8")
    for needle in ("[data-filter-nav]", "data-filter", "data-section", "aria-pressed", "hashchange", "replaceState",
                   "input[data-search]", "data-name"):
        assert needle in js, "site.js does not handle %s" % needle
    # without JavaScript the controls do not show (the sections are never hidden in the markup)
    assert re.search(r"\.nojs \.filter\b[^{]*\{display:none\}", css)
    assert re.search(r"\.nojs [^{]*\.search\b[^{]*\{display:none\}", css)
    # one implementation: no guide generator writes the filter's behaviour itself
    for gen in ROOT.glob("tools/player_guide_*.py"):
        text = gen.read_text(encoding="utf-8")
        assert "data-filter-nav" not in text and "hashchange" not in text, \
            "%s writes the filter itself; use player_site.filter_nav" % gen.name
