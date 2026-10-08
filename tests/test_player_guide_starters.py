"""tools/player_guide_starters.py: the starter guide is current, carries every starter line, and says nothing about
where a story item comes from or which counter a held line is held for.

The expectations are read from the data and the jar directly, not from the generator's model: the lines and their
finals from data/mythical_starters.json, the display names from the jar's en_us.json, the keepers from
data/markets.json.

The page is published (2026-10-08; the generator's docstring): the leak test lets the starter species through by its
ALLOW list, and `test_only_the_starter_species_would_leak` pins that they are the ONLY thing from
data/mythical_starters.json it would otherwise object to. The abilities are checked against the data's own pools and
the jar's species files and lang directly; the taglines against the data.
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


def _sections(raw):
    """{line heading: section html}."""
    return {html.unescape(h): b for h, b in
            re.findall(r'<section class="line" [^>]*><h2>(.*?)</h2>(.*?)</section>', raw, re.S)}


def _ability_groups(section):
    """The abilities table of one line as [(form, [(ability name, hidden)])], in the page's order; a row with an empty
    form cell belongs to the form above it."""
    body = re.search(r'<table class="stats abilities">.*?<tbody>(.*?)</tbody>', section, re.S)
    assert body, "a line has no abilities table"
    groups = []
    for _tier, form, cell, desc in re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>",
                                              body.group(1)):
        assert _text(desc).strip(), "an ability with no description"
        if form:
            groups.append((html.unescape(form), []))
        hidden = '<span class="tag">hidden</span>' in cell
        groups[-1][1].append((_text(cell.replace('<span class="tag">hidden</span>', "")).strip(), hidden))
    return groups


def _species_pool(z, sid, forms=False):
    """A species file's ability pool, read straight from the jar; with `forms`, every form's own pool too."""
    s = json.loads(z.read(next(n for n in z.namelist()
                               if n.startswith("data/cobblemon/species/") and n.endswith("/%s.json" % sid)))
                   .decode("utf-8"))
    pools = [s["abilities"]]
    if forms:
        pools += [f["abilities"] for f in s.get("forms") or [] if f.get("abilities")]
    return pools


def _expect(pool, lang):
    normal = [a for a in pool if not a.startswith("h:")]
    return [(lang["cobblemon.ability.%s" % a], False) for a in normal] + \
           [(lang["cobblemon.ability.%s" % a[2:]], True) for a in pool if a.startswith("h:") and a[2:] not in normal]


def test_every_stage_shows_its_abilities(page):
    """Every tier of every line shows at least one ability with a description; tiers 1 and 2 show the stage's own
    `abilities` from the data when it sets them (Smeargle's Protean) and the jar species' pool otherwise; a final shows
    a pool its jar species file carries; a hidden ability is marked hidden. Expectations read from the data and the
    species files, not from the generator."""
    raw, jar = page
    lang = _lang(jar)
    z = zipfile.ZipFile(jar)
    secs = _sections(raw)
    for ln in _data()["lines"]:
        groups = _ability_groups(secs[lang["cobblemon.species.%s.name" % ln["stages"][0]["species"]]])
        assert len(groups) >= len(ln["stages"]) + (1 if ln["final"] else 0), (ln["id"], groups)
        for (form, got), st in zip(groups, ln["stages"]):
            assert got, (ln["id"], form)
            want = _expect(st.get("abilities") or _species_pool(z, st["species"])[0], lang)
            assert got == want, (ln["id"], st["stage"], got, want)
        finals = [_expect(p, lang) for fin in ln["final"] for p in _species_pool(z, fin, forms=True)]
        for form, got in groups[len(ln["stages"]):]:
            assert got and got in finals, (ln["id"], form, got, finals)
    # the owner's case: Smeargle's forms carry Protean, not the jar's Own Tempo / Technician / Moody
    sm = next(ln for ln in _data()["lines"] if ln["stages"][0]["species"] == "smeargle")
    assert all(g == [("Protean", False)] for _f, g in _ability_groups(secs[lang["cobblemon.species.smeargle.name"]])), \
        sm["id"]


def test_every_ability_shown_exists_in_the_jar(page):
    """Every ability name on the page is the jar's en_us.json name of an id the jar's running Showdown
    (data/abilities.js) knows, and its description is that id's own."""
    import mythical_starters as MS
    raw, jar = page
    lang = _lang(jar)
    known = MS.running_abilities(zipfile.ZipFile(jar))
    by_name = {v: k.split(".")[2] for k, v in lang.items() if re.fullmatch(r"cobblemon\.ability\.[a-z0-9]+", k)}
    seen = 0
    for sec in _sections(raw).values():
        body = re.search(r'<table class="stats abilities">.*?<tbody>(.*?)</tbody>', sec, re.S).group(1)
        for _t, _f, cell, desc in re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>", body):
            name = _text(cell.replace('<span class="tag">hidden</span>', "")).strip()
            assert name in by_name, name
            aid = by_name[name]
            assert aid in known, (name, aid)
            assert html.unescape(desc) == lang["cobblemon.ability.%s.desc" % aid], name
            seen += 1
    assert seen >= sum(len(ln["stages"]) for ln in _data()["lines"])


def test_every_line_has_its_tagline(page):
    """Every line carries a `tagline` in the data, shown first under its name; Smeargle's is the owner's words."""
    raw, jar = page
    lang = _lang(jar)
    secs = _sections(raw)
    for ln in _data()["lines"]:
        tag = (ln.get("tagline") or "").strip()
        assert tag, "%s has no tagline" % ln["id"]
        sec = secs[lang["cobblemon.species.%s.name" % ln["stages"][0]["species"]]]
        m = re.match(r'<p class="tagline">(.*?)</p>', sec)
        assert m and html.unescape(m.group(1)) == tag, ln["id"]
    sm = next(ln for ln in _data()["lines"] if ln["stages"][0]["species"] == "smeargle")
    assert sm["tagline"] == "An adaptive and despicable choice of your own fate."  # the owner, 2026-10-08


def test_a_line_without_a_tagline_stops_the_run(page, monkeypatch):
    d = _data()
    del d["lines"][0]["tagline"]
    real = G.doc
    monkeypatch.setattr(G, "doc", lambda rel: d if rel == G.DATA else real(rel))
    with pytest.raises(SystemExit, match="tagline"):
        G.collect(str(page[1]))


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
