"""tools/player_guide_starters.py: the starter guide is current, carries every starter line, and says nothing about
where a story item comes from or which counter a held line is held for.

The expectations are read from the data and the jar directly, not from the generator's model: the lines and their
finals from data/mythical_starters.json, the display names from the jar's en_us.json, the keepers from
data/markets.json.

The page is NOT published (see the generator's docstring): tests/test_player_site_leaks.py forbids the stage-1 species
names on any public page, because data/mythical_starters.json is read there as a legendary file. Until the owner
decides, the currency test skips when the page is neither in docs/player/ nor in guides.json, and
`test_only_the_starter_species_would_leak` pins that the starters' own names are the ONLY thing the leak test would
object to.
"""
from __future__ import annotations

import html
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import player_guide_starters as G  # noqa: E402
import player_guide_battles as PB  # noqa: E402
import player_site  # noqa: E402
import test_player_site_leaks as LEAKS  # noqa: E402
import test_player_site_filter as FILTER  # noqa: E402


def _jar():
    try:
        return PB.find_jar()
    except SystemExit as e:
        pytest.skip("no Cobblemon 1.8 jar: %s" % e)


@pytest.fixture(scope="module")
def page():
    jar = _jar()
    return G.render(G.collect(str(jar))), jar


def _data():
    return json.loads((ROOT / G.DATA).read_text(encoding="utf-8"))


def _lang(jar):
    return json.loads(zipfile.ZipFile(jar).read("assets/cobblemon/lang/en_us.json").decode("utf-8"))


def _text(raw):
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def test_every_starter_line_is_on_the_page(page):
    raw, jar = page
    lang = _lang(jar)
    heads = [html.unescape(h) for h in re.findall(r'<section class="line" [^>]*><h2>(.*?)</h2>', raw)]
    sections = re.findall(r'<section class="line".*?</section>', raw, re.S)
    lines = _data()["lines"]
    assert len(sections) == len(lines)
    for ln in lines:
        first = lang["cobblemon.species.%s.name" % ln["stages"][0]["species"]]
        assert first in heads, "line %s has no section headed %r" % (ln["id"], first)
        body = _text(sections[heads.index(first)])
        for fin in ln["final"]:
            assert lang["cobblemon.species.%s.name" % fin] in body, (ln["id"], fin)
        for st in ln["stages"]:  # each tier's stats as the data gives them, in order
            row = " ".join(str(st["baseStats"][k]) for k, _h in G.STATS)
            assert row in " ".join(body.split()), (ln["id"], st["stage"], row)


def test_the_filter_has_a_button_per_line_and_all(page):
    """One button per starter line (named as the line's section is headed) plus All; every line's section is under
    its own button, and the line's items sit inside that section, so one button shows all of a line and nothing
    else."""
    raw, jar = page
    assert FILTER.filter_problems(raw) == []
    lang = _lang(jar)
    buttons = FILTER.nav_buttons(raw)
    assert buttons[0][:2] == ("all", "All")
    want = [lang["cobblemon.species.%s.name" % ln["stages"][0]["species"]] for ln in _data()["lines"]]
    assert sorted(t for _k, t, _a in buttons[1:]) == sorted(want)
    for key, text, _a in buttons[1:]:
        sec = re.search(r'<section class="line" id="%s" data-section="%s"><h2>(.*?)</h2>(.*?)</section>'
                        % (re.escape(key), re.escape(key)), raw, re.S)
        assert sec and html.unescape(sec.group(1)) == text, (key, text)
    # every contents link lands on an element that exists (the line links once pointed at ids no section had)
    ids = set(re.findall(r'\sid="([^"]+)"', raw))
    assert all(h in ids for h in re.findall(r'href="#([^"]+)"', raw)), sorted(set(re.findall(r'href="#([^"]+)"', raw)) - ids)
    # an item a line needs is inside that line's section, never in a section of its own
    for s in G.collect(str(jar))["specials"]:
        head = re.search(r'<section class="line" [^>]*><h2>%s</h2>(.*?)</section>' % re.escape(html.escape(s["line"])),
                         raw, re.S)
        assert head and html.escape(s["name"]) in head.group(1), (s["line"], s["name"])


def test_the_starter_screen_is_the_lines():
    cfg = json.loads((ROOT / G.CONFIG).read_text(encoding="utf-8"))
    offered = sorted(e.split()[0] for c in cfg["starters"] for e in c["pokemon"])
    assert offered == sorted(ln["stages"][0]["species"] for ln in _data()["lines"])


def test_the_page_is_current(page):
    if not G.OUT.is_file() and not player_site.registered(G.GUIDE):
        pytest.skip("docs/player/starters.html is not published: the leak test forbids the starter species names "
                    "(data/mythical_starters.json is a legendary file there); held for the owner's decision")
    assert G.main(["--check"]) == 0


def test_check_bites(tmp_path, page):
    out = tmp_path / "starters.html"
    jar = str(page[1])
    assert G.main(["--out", str(out), "--jar", jar]) == 0
    assert G.main(["--check", "--out", str(out), "--jar", jar]) == 0
    out.write_text(out.read_text(encoding="utf-8").replace("<td class=\"n\">", "<td class=\"n\">9", 1),
                   encoding="utf-8")
    assert G.main(["--check", "--out", str(out), "--jar", jar]) == 1


def test_only_the_starter_species_would_leak(page):
    raw, _jar = page
    species = {s["species"] for ln in _data()["lines"] for s in ln["stages"]}
    found = LEAKS.leaks(raw, LEAKS.secrets())
    other = [f for f in found if not (f[0] == "name" and f[1] in species and f[2].startswith(G.DATA))]
    assert not other, other


def test_held_lines_and_story_items_name_no_seller(page):
    raw, _jar = page
    text = " ".join(_text(raw).split())
    m = json.loads((ROOT / "data/markets.json").read_text(encoding="utf-8"))
    on_page = {s["item"] for s in G.collect(str(page[1]))["specials"]}
    for rec in m["counters"] + m["stalls"]:
        stocked = {line.get("item") for line in rec.get("stock") or []}
        held = {line.get("item") for line in rec.get("held_stock") or []}
        name = (rec.get("keeper") or {}).get("name")
        if name and (held & on_page) and not (stocked & on_page):
            assert name not in text, "the page names %s, which only holds %s" % (name, sorted(held & on_page))
    # a town is named only as the seller's town of a line it stocks ("Sold in <town> by ...")
    towns = json.loads((ROOT / "data/towns.json").read_text(encoding="utf-8"))["towns"]
    for t in towns:
        name = t.get("display_name")
        if name and len(name) > 3:
            for hit in re.finditer(r"\b%s\b" % re.escape(name), text):
                assert text[max(0, hit.start() - 8):hit.start()] == "Sold in ", "the page names %s" % name
    # the scrolls are given at the research station by its Director (data/research_station.json economy, npcs): the
    # page says "earned in the story" and neither word
    for word in ("station", "director", "research"):
        assert word not in text.lower(), word
