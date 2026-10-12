"""docs/player/dungeons.html (tools/player_guide_dungeons.py).

Properties held here, and what breaks without each:

  1. The page never prints the name of a legendary, mythical, Ultra Beast or paradox species (a public page must not
     name a dungeon prize or any other legendary). The labels and names are read from the Cobblemon 1.8.0 jar's own
     species files by this file's reader, not from the generator; names are matched case-insensitively, as whole words,
     with spaces, hyphens, colons and none between the words, in the species' `name`, its English display name and its
     file stem ("Tapu Koko", "Iron Hands", "Type: Null", "Ho-Oh").
     test_the_name_check_bites injects a name into a real fragment; test_the_generator_withholds_a_labelled_species
     mutates the GENERATOR (its Dex.is_legend is told Onix is legendary) and shows Onix leaves the page.
  2. Every run clock printed equals tools/dungeon.py clock_s(dungeon, band) for that dungeon and band, read here from
     data/dungeons.json (the table is found by this file's own regexes in the published page).
  3. Every hidden-prize chance printed equals tools/dungeon_prize.py chance(doc, room, band), over the dungeon's own
     habitat rooms found here by this file's own walk of data/dungeons.json, and the kind printed is the kind the pool
     is (rare below the legendary band, legendary from it; "none" where there is no pool), never a species.
  4. All thirteen dungeons are on the page, the cut Zero Dig is not, the page is registered in guides.json, and
     --check agrees the committed page is current.

The jar: the offline snapshot's (player_guide_battles.find_jar), else the installed server's mods folder only when
COBBLERS_SERVER_ROOT is set by the caller (tools/position_types.py default_jar). Without a jar the tests that need it
SKIP with the reason; they never pass without reading one. This file reads a jar only: no server, RCON, lock or world.

Written by the same agent that wrote the page (the owner allowed one agent for this unit); the clock and prize
expectations are still derived from the data files and the engine functions, not from the generator's model.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

PAGE = ROOT / "docs" / "player" / "dungeons.html"
GUIDES = ROOT / "docs" / "player" / "guides.json"
LABELS = {"legendary", "mythical", "ultra_beast", "paradox"}


# ------------------------------------------------------------------------------------------------ the jar


def _jar():
    try:
        import player_guide_battles as PB
        hits = sorted(PB.MODS.glob(PB.JAR_GLOB)) if PB.MODS.is_dir() else []
        if hits:
            return hits[0]
    except Exception:  # noqa: BLE001  any trouble finding the snapshot falls through to the explicit server root
        pass
    if os.environ.get("COBBLERS_SERVER_ROOT"):
        import position_types as PT
        return PT.default_jar()
    return None


JAR = _jar()
needs_jar = pytest.mark.skipif(JAR is None or not Path(JAR).is_file(),
                               reason="no Cobblemon 1.8 jar: set COBBLERS_SNAPSHOT_MODS to the offline snapshot's mods "
                                      "folder, or COBBLERS_SERVER_ROOT for the installed server")


def _species():
    """{stem: {"names": set of name forms, "labels": set}} for every legendary-class species in the jar."""
    out = {}
    with zipfile.ZipFile(JAR) as z:
        lang = json.loads(z.read("assets/cobblemon/lang/en_us.json").decode("utf-8"))
        for n in z.namelist():
            m = re.fullmatch(r"data/cobblemon/species/[^/]+/([a-z0-9_]+)\.json", n)
            if not m:
                continue
            j = json.loads(z.read(n).decode("utf-8"))
            labels = set(j.get("labels") or [])
            if labels & LABELS:
                names = {m.group(1), str(j.get("name") or ""), lang.get("cobblemon.species.%s.name" % m.group(1)) or ""}
                out[m.group(1)] = {"names": {x for x in names if x}, "labels": labels}
    return out


def _pattern(name):
    toks = re.findall(r"[a-z0-9]+", name.lower())
    return re.compile(r"(?<![a-z0-9])" + r"[\W_]*".join(re.escape(t) for t in toks) + r"(?![a-z0-9])")


def named_species(text, species):
    """The legendary-class species whose name appears in `text` (HTML or plain), case-insensitively, as whole words."""
    t = html.unescape(text).lower()
    hits = set()
    for stem, e in species.items():
        if any(_pattern(n).search(t) for n in e["names"]):
            hits.add(stem)
    return hits


# ------------------------------------------------------------------------------------------------ reading the page and data


@pytest.fixture(scope="module")
def page():
    assert PAGE.is_file(), "run python tools/player_guide_dungeons.py"
    return PAGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def doc():
    return json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))


def _slug(did):
    return did.replace("_", "-")


def section(page_text, did):
    m = re.search(r'<section id="%s" data-section="%s">(.*?)</section>' % (_slug(did), _slug(did)), page_text, re.S)
    assert m, "no section for %s" % did
    return m.group(1)


def _walk(rooms):
    """Every room record of a rooms list, forks' routes and sides included (this file's own walk)."""
    for r in rooms:
        if r.get("kind") == "fork":
            for rt in r.get("routes", []):
                yield from _walk(rt.get("rooms", []))
        elif r.get("kind") == "side":
            yield from _walk(r.get("rooms", []))
        else:
            yield r


def cells(row_html):
    return [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td>(.*?)</td>", row_html, re.S)]


# ------------------------------------------------------------------------------------------------ 1. no legendary names


@needs_jar
def test_the_page_names_no_legendary_class_species(page):
    species = _species()
    assert len(species) > 100, "the jar reader found only %d legendary-class species" % len(species)
    assert named_species(page, species) == set()


@needs_jar
def test_the_name_check_bites(page):
    # a name check that finds nothing in a clean page proves nothing until it is shown to find one when it is there
    species = _species()
    for needle in ("Tapu Koko", "iron hands", "TYPE: NULL", "Ho-Oh", "mewtwo", "Zygarde", "Kartana", "Roaring Moon"):
        injected = page.replace("</main>", "<p>A strange %s waits here.</p></main>" % needle, 1)
        assert named_species(injected, species), "the check missed %r" % needle
    # a whole-word check: a name inside a longer word is not a hit, and a plain page word is not either
    assert not named_species("<p>the mewling cat</p>", species)


@needs_jar
def test_the_generator_withholds_a_labelled_species(tmp_path):
    # mutate the GENERATOR: the jar reader is told Onix is legendary; the finished page must then not name it
    import player_guide_dungeons as G
    model = G.collect()
    assert "Onix" in G.render(model), "the premise: Onix is on the real page"
    real = G.Dex.is_legend
    try:
        G.Dex.is_legend = lambda self, sp: G.compact(sp) == "onix" or real(self, sp)
        mutated = G.render(G.collect())
    finally:
        G.Dex.is_legend = real
    assert "Onix" not in mutated
    assert re.search(r"Steelix", mutated), "only the labelled species is withheld"


# ------------------------------------------------------------------------------------------------ 2. the clocks


def test_every_printed_clock_is_the_engines(page, doc):
    import dungeon as D
    bands = doc["engine"]["bands"]
    assert len(doc["dungeons"]) == 13
    for d in doc["dungeons"]:
        m = re.search(r"<tr><td>Run clock</td>((?:<td>[^<]*</td>)+)</tr>", section(page, d["id"]))
        assert m, "%s: no run clock row" % d["id"]
        printed = cells(m.group(1))
        want = []
        for b in bands:
            s = D.clock_s(d, b)
            want.append("%d:%02d" % (s // 60, s % 60))
        assert printed == want, "%s: printed %s, clock_s gives %s" % (d["id"], printed, want)


# ------------------------------------------------------------------------------------------------ 3. the hidden prize


def test_every_prize_chance_and_kind_is_the_engines(page, doc):
    import dungeon_prize as DP
    bands = [b["band"] for b in doc["engine"]["bands"]]
    seen = 0
    for d in doc["dungeons"]:
        sec = section(page, d["id"])
        m = re.search(r"<summary>The hidden prize</summary>(.*?)</details>", sec, re.S)
        rooms = [r for r in _walk(d["rooms"]) if r.get("kind") == "habitat" and (r.get("params") or {}).get("prize")]
        if not rooms:
            assert not m, "%s prints a prize it does not have" % d["id"]
            continue
        assert m, "%s has a hidden prize and the page does not say so" % d["id"]
        rows = {}
        for tr in re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S):
            c = cells(tr)
            if c and c[0].isdigit():
                rows[int(c[0])] = c[1:]
        assert sorted(rows) == bands
        room = rooms[0]
        for b in bands:
            pool = DP.pool_at(doc, room, b)
            if pool is None:
                assert rows[b][0] == "none", "%s band %d" % (d["id"], b)
                continue
            assert rows[b][0] == "%d%%" % DP.chance(doc, room, b), "%s band %d chance" % (d["id"], b)
            assert rows[b][1] == ("a legendary Pokemon" if b >= DP.legendary_from(doc) else "a rare Pokemon"), \
                "%s band %d kind" % (d["id"], b)
            assert pool[1] == (b >= DP.legendary_from(doc)), "the pool's kind and the legendary band disagree"
            seen += 1
    assert seen >= 13 * 3, "only %d prize rows were compared" % seen


# ------------------------------------------------------------------------------------------------ 4. the page itself


def test_all_thirteen_dungeons_and_not_the_zero_dig(page, doc):
    for d in doc["dungeons"]:
        assert d["name"] in page, d["name"]
        section(page, d["id"])
    assert not re.search(r"zero[\s_-]*dig", page, re.I)
    assert "zero_dig" not in {d["id"] for d in doc["dungeons"]}


def test_the_draw_note_and_no_walkthrough(page):
    assert "DUNGEON_DRAW.md" in page and "test rip" in page
    # the vault code and rip coordinates are left to find
    assert not re.search(r"\b\d{3,4}\s*,\s*\d{2,3}\s*,\s*\d{3,4}\b", html.unescape(page)), "a coordinate triple"


def test_registered_and_current():
    entry = [g for g in json.loads(GUIDES.read_text(encoding="utf-8"))["guides"] if g["file"] == "dungeons.html"]
    assert len(entry) == 1 and entry[0]["generator"] == "tools/player_guide_dungeons.py"


@needs_jar
def test_check_agrees_the_page_is_current():
    import player_guide_dungeons as G
    assert G.main(["--check"]) == 0
