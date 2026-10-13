"""The rift guide book and the themed ground under a rip (tools/dungeon_guide.py, tools/dungeon.py rip_scorch).

Written by the same agent that wrote them (the brief's one-agent unit); the expectations are read from the data files
here, not from the generators' own helper functions, and the mutation tests change the GENERATOR and leave the data alone.

THE BOOK
  1. The give command is a 1.21.1 `minecraft:written_book_content` give: a title of at most 32 characters, an author and
     pages that are each a JSON text component inside an SNBT single-quoted string; at most 100 pages; no page past a
     14-line screen at 19 characters a line (this file's own wrap, not the generator's).
     NOT VERIFIED IN GAME: nothing in the repository gave a written book before this one.
  2. It is given once: the tag is added before the book in the function, and the arrive function of every slot runs the
     function only for a player without the tag. (The simulated run in tests/test_dungeon.py proves the second arrival
     gives no second book.)
  3. Every figure the text prints equals the data file that owns it.
  4. No legendary, mythical, Ultra Beast or paradox species is named, against the Cobblemon jar's own labels.
  5. The players' page prints the SAME paragraphs as the book (decoded here from the give command).

THE GROUND UNDER A RIP
  6. A rip's patch is the theme's hull floor (core) and hull wall (rim), read here from data/dungeon_themes.json; an
     explicit rip.scorch still overrides; mutating the GENERATOR's choice moves the blocks and the test notices.
  7. rip_close_lines fails closed without rip.under, and with it puts every patch cell back and the plane to rip.restore.
"""
from __future__ import annotations

import copy
import html
import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_guide as GB  # noqa: E402
import test_player_guide_dungeons as PG  # noqa: E402  (its jar finder and legendary-name reader)

DATA = ROOT / "data"
PAGE = ROOT / "docs" / "player" / "dungeons.html"


def j(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


DOC = D.load()


# ------------------------------------------------------------------------------------------------- reading the command


def decode_pages(cmd):
    """The page strings of a give command's `pages:[...]`, each un-escaped from its SNBT single-quoted literal, by this
    file's own scanner."""
    i = cmd.index("pages:[") + len("pages:[")
    out = []
    while cmd[i] != "]":
        assert cmd[i] == "'", "a page is not a single-quoted string at %d" % i
        i += 1
        buf = []
        while cmd[i] != "'":
            if cmd[i] == "\\":
                i += 1
            buf.append(cmd[i])
            i += 1
        i += 1
        out.append("".join(buf))
        if cmd[i] == ",":
            i += 1
    assert cmd[i:] == "]}] 1", cmd[i:i + 20]
    return out


def page_text(components):
    return "".join(c if isinstance(c, str) else c["text"] for c in components)


def wrap_lines(text, width=19):
    """Lines a page takes at `width` characters, word-wrapped; this file's own greedy wrap."""
    n = 0
    for para in text.split("\n"):
        line = ""
        rows = 1
        for w in para.split(" "):
            if line and len(line) + 1 + len(w) > width:
                rows += 1
                line = w
            else:
                line = (line + " " + w) if line else w
        n += rows
    return n


@pytest.fixture(scope="module")
def cmd():
    return GB.give_command(DOC)


# ------------------------------------------------------------------------------------------------- 1. the command


def test_the_book_is_a_written_book_content_give_with_json_pages(cmd):
    m = re.fullmatch(r'give @s minecraft:written_book\[minecraft:written_book_content=\{title:"([^"]+)",author:"([^"]+)",'
                     r'pages:\[(.*)\]\}\] 1', cmd, re.S)
    assert m, cmd[:160]
    assert len(m.group(1)) <= 32 and m.group(2)
    pages = decode_pages(cmd)
    assert 1 <= len(pages) <= 100
    for p in pages:
        comps = json.loads(p)
        assert isinstance(comps, list) and comps[0] == "", p[:80]
        assert all(isinstance(c, str) or "text" in c for c in comps)
        assert wrap_lines(page_text(comps)) <= 14, "a page runs past the screen:\n" + page_text(comps)


def test_the_item_parses_with_the_simulators_own_snbt_reader(cmd):
    # tests/pocket_sim.py reads components with a real SNBT parser (tests/mc_snbt), not this file's scanner
    import pocket_sim as PS
    name, comps = PS.parse_item(cmd[len("give @s "):-len(" 1")])
    assert name == "minecraft:written_book"
    c = comps["minecraft:written_book_content"]
    assert c["title"] == "Rift Guide" and c["author"] == "The Rift"
    assert len(c["pages"]) == len(decode_pages(cmd))
    assert all(isinstance(json.loads(p), list) for p in c["pages"])


def test_the_text_is_plain_ascii_and_has_no_quote_trouble(cmd):
    assert cmd.isascii()
    for p in decode_pages(cmd):
        json.loads(p)          # an apostrophe or backslash lost in the SNBT string would break the JSON


# ------------------------------------------------------------------------------------------------- 2. once


def test_the_function_tags_before_it_gives_and_every_arrival_asks_for_the_tag():
    lines = [l for l in GB.function_lines(DOC) if not l.startswith("#")]
    assert lines[0] == "tag @s add %s" % GB.BOOK_TAG
    assert lines[1].startswith("give @s minecraft:written_book[")
    assert GB.arrive_line() == ("execute unless entity @s[tag=%s] run function cobblers:dungeons/%s"
                                % (GB.BOOK_TAG, GB.BOOK_FUNCTION))
    assert GB.BOOK_TAG == "cobblers.dg_book"


# ------------------------------------------------------------------------------------------------- 3. the figures


def test_every_figure_is_its_data_files():
    text = " ".join(p for _k, _t, ps in GB.sections(DOC) for p in ps)
    doc = j("dungeons.json")
    clock = doc["engine"]["clock"]
    rate = j("dungeon_greed.json")["rate"]
    x1, x2 = j("dungeon_extras.json"), j("dungeon_extras2.json")
    bo = j("blackout.json")["money"]
    puz = j("dungeon_puzzles.json")["defaults"]
    bv, ww = x1["bank_vault"]["defaults"], x1["wishing_well"]["defaults"]
    prices = list(x2["eggs"]["price"]["clock_s_by_band"].values())
    want = [
        r"warned at %d:%02d and %d:%02d" % (clock["titles_at_s"][0] // 60, clock["titles_at_s"][0] % 60,
                                            clock["titles_at_s"][1] // 60, clock["titles_at_s"][1] % 60),
        r"last %d seconds" % clock["countdown_last_s"],
        r"A fall costs %d seconds" % clock["fall_penalty_s"],
        r"Every %d points make the clock run 0\.1x faster, up to x%d at %d points"
        % (rate["per_step_cp"] / 100, rate["cap"] / rate["base"], (rate["cap"] - rate["base"]) * rate["per_step_cp"] / 100),
        r"costs \$%d" % math.ceil(bo["cap"] * bo["percent"] / 100),
        r"locked to you for %d minutes" % (doc["engine"]["lockout_ticks"] / 20 / 60),
        r"lock of %d digits.*?%d tries.*?wrong code costs %d seconds\. %d chests, %d seconds each"
        % (bv["digits"], bv["max_tries"], bv["penalty_s"], bv["chests"], bv["clock_cost_s"]),
        r"Puzzle vault: %d chests, %d seconds each" % (puz["vault_chests"], puz["vault_clock_cost_s"]),
        r"%d throws a run, nothing under %s of a point" % (ww["throws"], ("%.2f" % (ww["min_cp"] / 100)).rstrip("0").rstrip(".")),
        r"%d to %d seconds by band, and you need %d left" % (min(prices), max(prices), x2["eggs"]["price"]["min_left_s"]),
        r"worth %d points" % (x2["fossils"]["greed_cp"] / 100),
        r"Rift Pick" if doc["engine"]["rift_pick"]["name"] == "Rift Pick" else re.escape(doc["engine"]["rift_pick"]["name"]),
    ]
    for pat in want:
        assert re.search(pat, text), "not in the guide: " + pat


def test_the_guide_refuses_when_a_rule_it_describes_changes():
    bad = copy.deepcopy(DOC)
    bad["engine"]["sigils"]["accept"] = "own_only"
    with pytest.raises(GB.GuideError):
        GB.sections(bad)
    bad = copy.deepcopy(DOC)
    bad["engine"]["death"]["pre_threshold_death_refund"] = True
    with pytest.raises(GB.GuideError):
        GB.sections(bad)


def test_a_changed_figure_moves_the_text():
    # Changes the DATA the figure is read from (the fall penalty) and shows the text follows; the paragraph is not typed.
    other = copy.deepcopy(DOC)
    other["engine"]["clock"]["fall_penalty_s"] = 37
    text = " ".join(p for _k, _t, ps in GB.sections(other) for p in ps)
    assert "A fall costs 37 seconds" in text and "A fall costs 15 seconds" not in text


# ------------------------------------------------------------------------------------------------- 4. no legendary


@PG.needs_jar
def test_no_legendary_species_is_named_in_the_book_or_the_section(cmd):
    species = PG._species()
    assert len(species) > 50
    text = "\n".join(page_text(json.loads(p)) for p in decode_pages(cmd))
    assert PG.named_species(text, species) == set()
    # and the check bites: a real name injected is found
    assert PG.named_species(text + " Mewtwo", species) == {"mewtwo"}


# ------------------------------------------------------------------------------------------------- 5. the same text


def test_the_players_page_prints_the_books_paragraphs(cmd):
    page = PAGE.read_text(encoding="utf-8")
    m = re.search(r'<section id="first-rift"[^>]*>(.*?)</section>', page, re.S)
    assert m, "no 'Your first rift' section: run python tools/player_guide_dungeons.py"
    on_page = [html.unescape(re.sub(r"<[^>]+>", "", x)) for x in re.findall(r"<p>(.*?)</p>", m.group(1), re.S)]
    in_book = []
    for p in decode_pages(cmd):
        for c in json.loads(p)[1:]:
            if not c.get("bold"):
                in_book.extend(c["text"].split("\n"))
    in_book = [x for x in in_book if x]
    assert in_book, "the book has no paragraphs"
    assert set(in_book) <= set(on_page), sorted(set(in_book) - set(on_page))[:3]
    assert len(in_book) == sum(len(ps) for _k, _t, ps in GB.sections(DOC))
    titles = [html.unescape(x) for x in re.findall(r"<h3>(.*?)</h3>", m.group(1))]
    assert titles == [t for _k, t, _ps in GB.sections(DOC)]


# ------------------------------------------------------------------------------------------------- 6. the ground


def test_a_rips_patch_is_its_themes_floor_and_wall():
    themes = j("dungeon_themes.json")["themes"]
    seen = set()
    # since 2026-10-13 the rips are data/dungeon_rips.json's, each with its theme. The 20 standing rips wear 8 patches; the 13
    # retired trail rips' records are kept and carry the other themes, so the table of themes is still what is checked
    for rec in DOC["rips"] + DOC["retired_rips"]:
        hull = themes[rec["scorch_theme"]]["hull"]
        assert "scorch" not in rec, "%s still carries an explicit scorch" % rec["id"]
        cells = D.rip_scorch_cells(rec)
        assert {b for _x, _y, _z, b in cells} == {hull["floor"], hull["wall"]}, rec["id"]
        f = rec["frame"]
        assert len(cells) == 3 + 1 + 2 + 2 and {y for _x, y, _z, _b in cells} == {f["y"] - 1}
        seen.add((hull["floor"], hull["wall"]))
    assert len(seen) >= 10, "the patches barely differ between themes: %s" % sorted(seen)


def test_an_explicit_scorch_still_overrides_the_theme():
    rec = copy.deepcopy(DOC["rips"][1])
    rec["scorch"] = {"rim": "minecraft:gravel"}
    sc = D.rip_scorch(rec)
    assert sc["rim"] == "minecraft:gravel"
    assert sc["core"] == j("dungeon_themes.json")["themes"][rec["scorch_theme"]]["hull"]["floor"]


def test_the_patch_follows_the_themes_data(monkeypatch):
    # Mutates the DATA the generator reads (a theme's floor) and shows the patch follows it: not a literal in the tool.
    themes = copy.deepcopy(j("dungeon_themes.json"))
    rec = DOC["rips"][1]
    themes["themes"][rec["scorch_theme"]]["hull"]["floor"] = "minecraft:calcite"
    assert "minecraft:calcite" in {b for _x, _y, _z, b in D.rip_scorch_cells(rec, themes)}


def test_the_patch_blocks_are_safe_ground():
    spawn = set(j("spawn_blocks.json")["blocks"])
    for d in DOC["rips"]:
        for b in D.rip_scorch(d).values():
            assert b not in spawn, "%s: %s is a block a spawn condition names" % (d["id"], b)
            # neither a portal, nor a block that hurts or slows a player who stands on it
            assert not any(w in b for w in ("portal", "magma", "soul_sand", "honey", "slime", "cactus"))


# ------------------------------------------------------------------------------------------------- 7. giving it back


def test_closing_a_rip_fails_closed_without_the_ground_it_replaced():
    with pytest.raises(D.DungeonError, match="rip.under is not recorded"):
        D.rip_close_lines(DOC["rips"][0])


def test_closing_a_rip_puts_back_the_plane_and_every_patch_cell():
    rec = copy.deepcopy(DOC["rips"][1])
    cells = D.rip_scorch_cells(rec)
    rec["under"] = {"%d,%d" % (x, z): "minecraft:dirt" for x, _y, z, _b in cells}
    lines = D.rip_close_lines(rec)
    assert lines[0].startswith("kill @e[type=minecraft:interaction,tag=") and lines[1].startswith("kill @e[type=minecraft:item_display")
    back = [l for l in lines if l.startswith("setblock") and l.endswith("minecraft:dirt")]
    assert len(back) == len(cells)
    f = rec["frame"]
    assert [l for l in lines[2:] if l not in back] == D.rip_plane_lines(rec) and len(D.rip_plane_lines(rec)) >= f["x1"] - f["x0"] + 1


def test_a_partial_under_is_refused():
    rec = copy.deepcopy(DOC["rips"][1])
    cells = D.rip_scorch_cells(rec)
    rec["under"] = {"%d,%d" % (x, z): "minecraft:dirt" for x, _y, z, _b in cells[:-1]}
    with pytest.raises(D.DungeonError, match="no block for"):
        D.rip_close_lines(rec)
