#!/usr/bin/env python
"""The rift guide: the general rules of a dungeon run, in ONE text that two places print.

  1. A written book, given to a player once, the first time they arrive in any dungeon run (tools/dungeon.py: the slot's
     `arrive` function calls `dungeons/guide_book` for a player without the tag BOOK_TAG; that function tags them and gives
     the book). The owner, 2026-10-12: "Can't read most of the signs. The player should just get a dungeon guide book the
     first time they enter one of these to quick read through; it also should be covered on the site."
  2. The section "Your first rift" of the players' dungeon guide (tools/player_guide_dungeons.py, docs/player/dungeons.html).

Both call sections() below, so the book and the page cannot drift. The text is general: what a rip is, the sigil, the
clock and the points, falls, deaths, leaving, relics and the optional rooms. What differs between dungeons (its clock at
each band, its rumour, its relic count, its legs) stays on the entry room's board (tools/dungeon.py board_text). No
species, legendary or otherwise, is named here, and the hidden prize is not mentioned.

EVERY FIGURE IS READ, NEVER TYPED, from the file that owns it:
  data/dungeons.json engine      clock.titles_at_s, countdown_last_s, fall_penalty_s; lockout_ticks; members_max;
                                 sigils.accept and refund_before_threshold; rift_pick.name
  data/dungeon_greed.json rate   per_step_cp, base, cap (the points system)
  data/blackout.json money       cap and percent (the money a death costs)
  data/dungeon_puzzles.json      defaults.vault_chests and vault_clock_cost_s (a puzzle vault)
  data/dungeon_extras.json       bank_vault.defaults (digits, max_tries, penalty_s, chests, clock_cost_s) and
                                 wishing_well.defaults (throws, min_cp)
  data/dungeon_extras2.json      eggs.price (clock_s_by_band, min_left_s), fossils.greed_cp
The generator refuses to run when a rule its prose describes is not the one the data now holds (need()).

THE BOOK'S COMMAND (1.21.1, unverified in game; there was no written book in this repository before it):
  give @s minecraft:written_book[minecraft:written_book_content={title:"Rift Guide",author:"The Rift",pages:['<json>',...]}] 1
Each page is a JSON text component inside an SNBT single-quoted string, as the engine's item_name components already are
(tools/dungeon.py snbt_str). A page is kept to PAGE_LINES lines of LINE_W characters, a conservative reading of the
book screen (14 lines, about 19 characters), so none runs past the page.
"""
from __future__ import annotations

import json
import math
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

BOOK_TAG = "cobblers.dg_book"        # on the player once the book has been given (a persistent tag, as cobblers.dg_playtest)
BOOK_FUNCTION = "guide_book"         # cobblers:dungeons/guide_book
TITLE = "Rift Guide"                 # 32 characters at most (the book's title field)
AUTHOR = "The Rift"
PAGE_LINES = 14
LINE_W = 19
DATA = ROOT / "data"


class GuideError(ValueError):
    pass


def _j(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def need(cond, what):
    if not cond:
        raise GuideError("the guide's wording no longer matches the data: %s" % what)


def clock_text(s):
    return "%d:%02d" % (s // 60, s % 60)


def points_text(cp):
    return ("%.2f" % (cp / 100.0)).rstrip("0").rstrip(".")


def facts(doc):
    """{name: value}: every figure the text prints, read from its owning file."""
    e = doc["engine"]
    gt = _j("dungeon_greed.json")["rate"]
    bo = _j("blackout.json")["money"]
    puz = _j("dungeon_puzzles.json")["defaults"]
    x1, x2 = _j("dungeon_extras.json"), _j("dungeon_extras2.json")
    need(e["sigils"]["accept"] == "own_or_higher", "sigils.accept is no longer own_or_higher")
    need(e["sigils"]["refund_before_threshold"] is True, "sigils.refund_before_threshold is no longer true")
    need(e["death"]["pre_threshold_death_refund"] is False, "a death before the threshold now refunds the sigil")
    prices = x2["eggs"]["price"]["clock_s_by_band"]
    bv, ww = x1["bank_vault"]["defaults"], x1["wishing_well"]["defaults"]
    return {
        "solo": e["members_max"] == 1,
        "pick": e["rift_pick"]["name"],
        "lockout_min": e["lockout_ticks"] // 20 // 60,
        "warn1": e["clock"]["titles_at_s"][0], "warn2": e["clock"]["titles_at_s"][1],
        "countdown": e["clock"]["countdown_last_s"], "fall_s": e["clock"]["fall_penalty_s"],
        "step_pts": gt["per_step_cp"] // 100, "cap_x": gt["cap"] // gt["base"],
        "cap_pts": (gt["cap"] - gt["base"]) * gt["per_step_cp"] // 100,
        "death_money": int(math.ceil(bo["cap"] * bo["percent"] / 100.0)),
        "vault_chests": puz["vault_chests"], "vault_cost": puz["vault_clock_cost_s"],
        "bank_digits": bv["digits"], "bank_tries": bv["max_tries"], "bank_wrong": bv["penalty_s"],
        "bank_chests": bv["chests"], "bank_cost": bv["clock_cost_s"],
        "well_throws": ww["throws"], "well_min": points_text(ww["min_cp"]),
        "egg_min": min(prices.values()), "egg_max": max(prices.values()), "egg_left": x2["eggs"]["price"]["min_left_s"],
        "fossil_pts": points_text(x2["fossils"]["greed_cp"]),
    }


def sections(doc=None):
    """[(key, title, [paragraph, ...])]: the guide, plain ASCII text. One section starts a book page."""
    if doc is None:
        import dungeon as D
        doc = D.load()
    f = facts(doc)
    who = "alone" if f["solo"] else "with a party"
    return [
        ("rip", "What a rip is", [
            "A rip opens onto a timed pocket dungeon, played %s." % who,
            "Cross the entry room's far doorway and your clock starts. Reach the far rip before it ends.",
            "You are lent a %s for ore." % f["pick"]]),
        ("sigil", "The sigil", [
            "A rip takes one sigil of your band, or the lowest higher band you hold.",
            "Back out before the board's doorway and it is returned. Past it, it is spent, and a death never returns it."]),
        ("clock", "The clock", [
            "A bar shows your time. You are warned at %s and %s, then the last %d seconds are counted. At zero the rift puts you out."
            % (clock_text(f["warn1"]), clock_text(f["warn2"]), f["countdown"]),
            "Ore, chests and catches are points. Every %d points make the clock run 0.1x faster, up to x%d at %d points, and never slower again."
            % (f["step_pts"], f["cap_x"], f["cap_pts"])]),
        ("falls", "Falls and deaths", [
            "A fall costs %d seconds. It does not end the run." % f["fall_s"],
            "A death ends it. No items are lost: it costs $%d and the run you paid for." % f["death_money"],
            "Trainers inside pay no money. What you mined and picked up is yours."]),
        ("leaving", "Leaving", [
            "Leave by the back rip, or the far rip at the end. Once you cross the board, that dungeon is locked to you for %d minutes." % f["lockout_min"],
            "Logging out does not stop the rift. Your time away is charged when you return."]),
        ("relics", "Relics", [
            "Some rooms hide a secret with a relic on a pedestal. Walk up and it is yours, once. It costs no clock time."]),
        ("vaults", "Vaults", [
            "Bank vault or strongroom: a lock of %d digits, written on signs in other rooms of the dungeon and changed every run. %d tries; a wrong code costs %d seconds. %d chests, %d seconds each."
            % (f["bank_digits"], f["bank_tries"], f["bank_wrong"], f["bank_chests"], f["bank_cost"]),
            "Puzzle vault: %d chests, %d seconds each." % (f["vault_chests"], f["vault_cost"])]),
        ("well", "Wishing well", [
            "Throw in items of worth: %d throws a run, nothing under %s of a point. It pays back a share, sometimes nothing." % (f["well_throws"], f["well_min"])]),
        ("bait", "Bait room", [
            "Leave a bait on the altar. Something follows the scent into a room of your next run, catchable."]),
        ("fishing", "Fishing pool", [
            "A still pool with a rod on a post, lent for the run. What bites depends on the dungeon and your band."]),
        ("eggs", "Egg seller", [
            "One egg a run, paid in clock time: %d to %d seconds by band, and you need %d left. It hatches in your pack as you walk."
            % (f["egg_min"], f["egg_max"], f["egg_left"])]),
        ("fossils", "Fossil dig", [
            "Break the dig blocks with the rift pick until the rock gives up its fossil. It is worth %s points." % f["fossil_pts"]]),
        ("board", "The board", [
            "The entry room's board gives this dungeon's clock at each band and its legs. Read it before you cross."]),
    ]


# ------------------------------------------------------------------------------------------------- the book


def _lines(s):
    return sum(max(1, len(textwrap.wrap(p, LINE_W))) for p in s.split("\n"))


def pages(doc=None):
    """[[(kind, text), ...]]: the book's pages, kind "h" (a heading line) or "p" (a paragraph). Sections follow one another
    on a page while they fit whole; one that does not fit starts the next page; one longer than a page goes on over
    continuation pages, a paragraph at a time. A single paragraph longer than a page is refused (the author splits it)."""
    out, cur, used = [], [], 0

    def new():
        nonlocal cur, used
        if cur:
            out.append(cur)
        cur, used = [], 0

    for _key, title, paras in sections(doc):
        cost = 1 + sum(_lines(p) for p in paras)
        if used + cost > PAGE_LINES:
            new()
        if cost <= PAGE_LINES:
            cur += [("h", title)] + [("p", p) for p in paras]
            used += cost
            continue
        head = title
        for p in paras:
            if 1 + _lines(p) > PAGE_LINES:
                raise GuideError("a paragraph does not fit on one page (%d lines): %s" % (1 + _lines(p), p))
            if used + 1 + _lines(p) > PAGE_LINES or not cur:
                new()
                cur, used = [("h", head)], 1
                head = title + " (cont.)"
            cur.append(("p", p))
            used += _lines(p)
    new()
    return out


def page_component(page):
    """The JSON text component of one page: each heading in bold, each paragraph in black, one line break between."""
    parts = [""]
    for i, (kind, text) in enumerate(page):
        tail = "\n" if i < len(page) - 1 else ""
        parts.append({"text": text + tail, "bold": True, "color": "dark_purple"} if kind == "h"
                     else {"text": text + tail, "color": "black"})
    return json.dumps(parts, ensure_ascii=True)


def _snbt_str(s):
    return "'%s'" % s.replace("\\", "\\\\").replace("'", "\\'")


def give_command(doc=None):
    """The book as one `give` (1.21.1 minecraft:written_book_content)."""
    if len(TITLE) > 32:
        raise GuideError("the book's title is longer than 32 characters")
    ps = ",".join(_snbt_str(page_component(pg)) for pg in pages(doc))
    return ('give @s minecraft:written_book[minecraft:written_book_content={title:"%s",author:"%s",pages:[%s]}] 1'
            % (TITLE, AUTHOR, ps))


def function_lines(doc=None):
    """dungeons/guide_book, run as the player by the arrive function when they do not hold BOOK_TAG: tag first, so a
    failure after it can never give two books, then the book and one line to tell them."""
    return ["# Generated by tools/dungeon_guide.py; never edit (build/ is regenerated).",
            "# As a player arriving in a dungeon run for the first time (tag %s unset): the rift guide, once" % BOOK_TAG,
            "tag @s add %s" % BOOK_TAG,
            give_command(doc),
            'tellraw @s %s' % json.dumps({"text": "The rift hands you a guide. Read it from your pack.",
                                            "color": "light_purple", "italic": True})]


def arrive_line():
    """The one line the slot's arrive function carries."""
    return "execute unless entity @s[tag=%s] run function cobblers:dungeons/%s" % (BOOK_TAG, BOOK_FUNCTION)


if __name__ == "__main__":
    for pg in pages():
        print("--- page,", sum(_lines(t) for _k, t in pg), "lines")
        print("\n".join(t for _k, t in pg))
