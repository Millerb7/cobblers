#!/usr/bin/env python
"""The players' dungeon guide, docs/player/dungeons.html: what a rip is, how sigils, the run clock, the points that speed
it up, deaths, the healer, relics and the six optional rooms work, and for each of the thirteen dungeons its theme, a
spoiler-light route summary, its clock at every band, its vault, its ore, the Pokemon you can catch and the chance of
its hidden prize.

  python tools/player_guide_dungeons.py            # write docs/player/dungeons.html and register it in guides.json
  python tools/player_guide_dungeons.py --check    # regenerate in memory; exit 1 if the page or its entry is stale
  python tools/player_guide_dungeons.py --out F    # write elsewhere (not the site's page, not registered)

EVERY NUMBER IS READ, NEVER TYPED. Sources, and the engine function that turns each into the figure printed:
  data/dungeons.json            bands and caps, the sigil ladder and accept rule, lockout, clock warnings, the death
                                titles, the stand and rooms of each dungeon; tools/dungeon.py clock_s(d, band) is the
                                run clock printed for a dungeon and band
  data/dungeon_greed.json       the points system; tools/dungeon_greed.py item_cp / block_cp / catch_cp / chest_cp /
                                rate_of / mult_of give every points figure and the speed it buys
  data/dungeon_prize.json, data/dungeon_prize_roster.json, tools/dungeon_prize.py chance(doc, room, band) and
                                pool_at(doc, room, band): the chance the hidden prize is there, and its KIND only
  data/dungeon_puzzles.json, dungeon_extras.json, dungeon_extras2.json, dungeon_resources.json, dungeon_relics.json,
  dungeon_setpieces.json, dungeon_themes.json, data/blackout.json (the money a death costs)
The few sentences of prose are the author's words about those figures; the generator refuses to run when a rule they
describe (sigil accept rule, recipe gate, refund, the prize's legendary band) is not the one the data now holds.

THE GUIDE'S LEGENDARY RULE. A Pokemon the Cobblemon 1.8.0 jar labels legendary, mythical, ultra_beast or paradox is
never named here, wherever the data lists it (a mini-boss pool, a bait, a fishing bucket): render() drops it and the
count is printed on the command line. The hidden prize is described by KIND only ("a rare Pokemon", "a legendary
Pokemon"), never by species. tests/test_player_guide_dungeons.py holds the finished page to this against the jar.

What this page does not say, on purpose: coordinates of any rip, the vault's code (it is rolled per run and the clue
rooms are left to find), relic names and places, the trainers' teams, the bosses, and room-by-room routes.

Not checked in a running game: the engine has not run on a server (data/dungeons.json status). Every clock and every
points figure is tunable data; where the game differs, the game is right.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import player_site  # noqa: E402  the shared header, footer, filter and manifest of docs/player/
import player_guide_battles as PB  # noqa: E402  the Cobblemon jar finder
import dungeon as D  # noqa: E402
import dungeon_greed as DG  # noqa: E402
import dungeon_life as DL  # noqa: E402
import dungeon_prize as DP  # noqa: E402
import dungeon_resources as DR  # noqa: E402
import dungeon_rooms as R  # noqa: E402

OUT = ROOT / "docs" / "player" / "dungeons.html"
GUIDE = {"file": "dungeons.html", "title": "Dungeons", "label": "Dungeons", "order": 40,
         "description": "How rift runs work (sigils, the clock, points, deaths, relics and the optional rooms) and, for each "
                        "dungeon, its clock at every band, its vault, its ore, what you can catch and the chance of its "
                        "hidden prize.",
         "generator": "tools/player_guide_dungeons.py"}
DATA = ROOT / "data"
LEGEND_LABELS = {"legendary", "mythical", "ultra_beast", "paradox"}      # the jar's labels the page never names
OPTIONAL_KINDS = ("bank_vault", "wishing_well", "bait_room", "fishing_room", "egg_room", "fossil_chamber")
GATE_WORDS = {"gym6_cleared": "the sixth badge", "gym8_cleared": "all eight badges", "champion_cleared": "the Champion's title"}
OPTIONAL_NAMES = {"bank_vault": "Bank vault", "wishing_well": "Wishing well", "bait_room": "Bait room",
                  "fishing_room": "Fishing pool", "egg_room": "Egg seller", "fossil_chamber": "Fossil dig"}
# the author's plain words for each set piece (the piece ids are data/dungeon_setpieces.json's keys)
SETPIECE_WORDS = {"collapse": "a stretch where the floor falls away behind you as you run",
                  "flood": "a sunken hall that fills with water while you climb out",
                  "lights_out": "a stretch where the light is shut off behind you"}
DEATH_CAUSE = {"1": "The clock ran out", "2": "A boss stage or a trainer beat you", "3": "Anything else",
               "4": "The run ended while you were logged out"}
ITEM_NAMES = {"mega_showdown:mega_stone": "Raw Mega Stone"}              # items the jar and vanilla do not name nicely
RES_ORDER = ("coal", "iron", "copper", "lapis", "redstone", "gold", "emerald", "diamond")
RARITY_ORDER = ("common", "uncommon", "rare", "ultra-rare")
esc = player_site.esc


# ------------------------------------------------------------------------------------------------ names and labels


def pretty(slug):
    return " ".join(w.capitalize() for w in re.split(r"[_\s-]+", str(slug or "").split(":")[-1]) if w)


def compact(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").split(":")[-1].lower())


class Dex:
    """Species names and labels, and Cobblemon item names, from the Cobblemon jar. Fails closed: a species the jar does
    not know cannot be checked against the legendary rule, so it stops the page."""

    def __init__(self, jar):
        self.jar = Path(jar)
        z = zipfile.ZipFile(self.jar)
        self.lang = json.loads(z.read("assets/cobblemon/lang/en_us.json").decode("utf-8"))
        self.species = {}
        for n in z.namelist():
            m = re.fullmatch(r"data/cobblemon/species/[^/]+/([a-z0-9_]+)\.json", n)
            if m:
                s = json.loads(z.read(n).decode("utf-8"))
                self.species[m.group(1)] = {"name": s.get("name"), "labels": set(s.get("labels") or [])}
        if len(self.species) < 900:
            raise SystemExit("read only %d species from %s" % (len(self.species), jar))
        self.withheld = set()

    def known(self, sp):
        key = compact(sp)
        if key not in self.species:
            raise SystemExit("species %r is in the dungeon data but not in %s: it cannot be checked against the legendary "
                             "rule" % (sp, self.jar.name))
        return key

    def is_legend(self, sp):
        return bool(self.species[self.known(sp)]["labels"] & LEGEND_LABELS)

    def name(self, sp):
        key = self.known(sp)
        return self.lang.get("cobblemon.species.%s.name" % key) or self.species[key]["name"] or pretty(sp)

    def show(self, sp):
        """The display name, or None for a species the page never names (counted in .withheld)."""
        if self.is_legend(sp):
            self.withheld.add(compact(sp))
            return None
        return self.name(sp)

    def shown(self, species):
        """Display names of a species list, legendary ones left out, de-duplicated in order."""
        out = []
        for sp in species:
            n = self.show(sp)
            if n and n not in out:
                out.append(n)
        return out

    def item(self, ident):
        if ident in ITEM_NAMES:
            name = ITEM_NAMES[ident]
        else:
            ns, _, path = ident.rpartition(":")
            name = self.lang.get("item.%s.%s" % (ns, path)) or pretty(ident)
        # an item named after a legendary-class Pokemon names that Pokemon (the owner, 2026-10-23: "hide calyrex on the
        # site"; the page printed "Calyrex Crown"): the drop is listed by kind only, as the page's prizes are
        if not hasattr(self, "_legend_words"):
            self._legend_words = {self.name(sp).lower() for sp, s in self.species.items()
                                  if s["labels"] & LEGEND_LABELS and self.name(sp)}
        words = set(re.findall(r"[a-z][a-z'-]*", name.lower()))
        if words & self._legend_words:
            self.withheld_items = getattr(self, "withheld_items", set()) | {ident}
            return "a legendary relic"
        return name


# ------------------------------------------------------------------------------------------------ small formatters


def clock_text(s):
    return "%d:%02d" % (s // 60, s % 60)


def minutes_text(s):
    return "%d min" % round(s / 60) if s % 60 == 0 else clock_text(s)


def points_text(cp):
    p = cp / 100.0
    s = ("%.2f" % p).rstrip("0").rstrip(".")
    return s


def mult_text(x):
    return "x%.1f" % x


def count_text(c):
    return str(c) if isinstance(c, int) else "%d-%d" % (c[0], c[1])


def pct_text(p):
    """A probability as a percentage: whole numbers, one decimal under 10% so a rare roll never reads 0%."""
    v = p * 100
    return ("%.1f%%" % v).replace(".0%", "%") if v < 10 else "%d%%" % round(v)


def stack_text(dex, s):
    chance = s.get("chance")
    tail = "" if chance is None else " (%s chance)" % pct_text(chance)
    if "one_of" in s:
        # the weighted form (tools/dungeon_puzzles.py loot_table): one roll picks one option by weight
        opts = s["one_of"]
        total = sum(o["weight"] for o in opts)
        parts = ["%s x %s (%s)" % (count_text(o.get("count", 1)), dex.item(o["item"]), pct_text(o["weight"] / total))
                 for o in opts]
        return "one of: %s%s" % (", ".join(parts), tail)
    return "%s x %s%s" % (count_text(s.get("count", 1)), dex.item(s["item"]), tail)


def need(cond, what):
    if not cond:
        raise SystemExit("the page's wording no longer matches the data: %s" % what)


def table(head, rows):
    th = "".join("<th>%s</th>" % esc(h) for h in head)
    body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in r) for r in rows)
    return '<div class="wide"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (th, body)


def slug(did):
    return did.replace("_", "-")


# ------------------------------------------------------------------------------------------------ the model


def base_rooms(d):
    return list(R._walk_records(d.get("rooms", [])))


def all_by_id(d):
    """{room id: [records]} over the authored rooms and every variant swap (a swap may change a room's species)."""
    out = {}
    for r in R.all_records(d):
        out.setdefault(r["id"], []).append(r)
    return out


def fork_summary(d):
    forks = []
    for r in d["rooms"]:
        if r["kind"] == "fork":
            forks.append([rt.get("look", "?") for rt in r["routes"]])
    return forks


def has_wing(d):
    for r in d["rooms"]:
        if r["kind"] == "side" and r["id"].startswith("w_"):
            return True
        if r["kind"] == "fork" and any(rt.get("optional") for rt in r["routes"]):
            return True
    return False


def loot_for(lb, band):
    keys = sorted(int(k) for k in lb if int(k) <= band)
    return lb[str(keys[-1])] if keys else None


def ambient_species(d, themes, band):
    cfg = DL.cfg_of(themes[d["theme"]])
    out = []
    for g in (cfg.get("ambient") or {}).get("groups", []):
        for line in g["lines"]:
            sp = line[DL.stage_of(band, len(line))]
            if sp not in out:
                out.append(sp)
    return out


def collect(jar=None):
    doc = D.load()
    gt = DG.load()
    themes = json.loads((DATA / "dungeon_themes.json").read_text(encoding="utf-8"))["themes"]
    puz = json.loads((DATA / "dungeon_puzzles.json").read_text(encoding="utf-8"))
    ex1 = json.loads((DATA / "dungeon_extras.json").read_text(encoding="utf-8"))
    ex2 = json.loads((DATA / "dungeon_extras2.json").read_text(encoding="utf-8"))
    relics = json.loads((DATA / "dungeon_relics.json").read_text(encoding="utf-8"))
    setp = json.loads((DATA / "dungeon_setpieces.json").read_text(encoding="utf-8"))
    blackout = json.loads((DATA / "blackout.json").read_text(encoding="utf-8"))
    dex = Dex(PB.find_jar(jar))
    eng = doc["engine"]
    bands = eng["bands"]
    nb = [b["band"] for b in bands]
    sig = eng["sigils"]
    need(sig["accept"] == "own_or_higher", "sigils.accept is no longer own_or_higher")
    need(sig["refund_before_threshold"] is True, "sigils.refund_before_threshold is no longer true")
    need(sig["recipe_gate"]["mode"] == "band", "sigils.recipe_gate.mode is no longer band")
    need(not sig["free_first_entry"]["dungeons"], "a dungeon now has a free first entry")
    need(eng["members_max"] == 1, "members_max is no longer 1")
    need(eng["death"]["pre_threshold_death_refund"] is False, "a death before the threshold now refunds the sigil")
    need(set(setp) - {"schema", "why"} == set(SETPIECE_WORDS), "the set pieces are not the three SETPIECE_WORDS describes")

    m = {"doc": doc, "gt": gt, "dex": dex, "bands": bands, "nb": nb, "jar": dex.jar.name}
    m["sigils"] = sig["ladder"]
    m["lockout_min"] = eng["lockout_ticks"] // 20 // 60
    m["clock"] = eng["clock"]
    m["warn"] = eng["clock"]["titles_at_s"]
    m["rift_pick"] = eng["rift_pick"]
    m["death_titles"] = eng["death"]["titles"]
    m["death_chat"] = eng["death"]["chat"]
    m["blackout_money"] = int(math.ceil(blackout["money"]["cap"] * blackout["money"]["percent"] / 100.0))
    m["rate"] = gt["rate"]
    m["puz"] = puz
    m["ex1"] = ex1
    m["ex2"] = ex2
    m["legend_from"] = DP.legendary_from(doc)

    # the points table
    ores = []
    for res in RES_ORDER:
        e = DR.resources()[res]
        blk = DG.block_cp(gt, e["blocks"]["stone"])
        icp = DG.item_cp(gt, e["item"])
        need(blk is not None and icp is not None, "the greed table does not price %s" % res)
        ores.append({"res": res, "item": dex.item(e["item"]), "item_cp": icp, "block_cp": blk})
    m["ores"] = ores
    m["catch_cp"] = {k: [DG.catch_cp(gt, k, b, doc) for b in nb] for k in ("ambient", "nest", "miniboss", "habitat")}
    m["fossil_cp"] = int(ex2["fossils"]["greed_cp"])
    m["cache"] = {b: DR.cache_items(b) for b in nb}
    m["steps"] = [(cp, DG.mult_of(gt, cp)) for cp in (0, 200, 1000, 2000, 3000, 4000)]
    m["cap_cp"] = (int(gt["rate"]["cap"]) - int(gt["rate"]["base"])) * int(gt["rate"]["per_step_cp"])

    dungeons = []
    for d in doc["dungeons"]:
        recs = base_rooms(d)
        byid = all_by_id(d)
        kinds = [r["kind"] for r in recs]
        x = {"id": d["id"], "name": d["name"], "theme_name": themes[d["theme"]]["name"], "theme": d["theme"],
             "forks": fork_summary(d), "wing": has_wing(d), "gate": d.get("gate_flag"), "first_band": d.get("first_band", 1),
             "clock": {b["band"]: D.clock_s(d, b) for b in bands},
             "piece": [(r.get("params") or {}).get("piece") for r in recs if r["kind"] == "setpiece"],
             "relics": sum(1 for r in recs if (r.get("params") or {}).get("relic")),
             "healers": sum(1 for r in recs if r["kind"] == "safe_room" and (r.get("params") or {}).get("healer")),
             "optional": [k for k in OPTIONAL_KINDS if k in kinds]}
        need(len(x["piece"]) == 1 and x["piece"][0] in SETPIECE_WORDS, "%s: set piece" % d["id"])
        # the hidden prize: chance and kind per band, from the engine's own functions
        prize = []
        for r in recs:
            if r["kind"] == "habitat" and (r.get("params") or {}).get("prize"):
                for b in nb:
                    got = DP.pool_at(doc, r, b)
                    prize.append({"band": b, "chance": DP.chance(doc, r, b) if got else None,
                                  "kind": None if not got else ("legendary" if got[1] else "rare")})
        x["prize"] = prize
        # vaults
        vaults = []
        for r in recs:
            p = r.get("params") or {}
            if r["kind"] == "vault":
                n = int(p.get("chests", puz["defaults"]["vault_chests"]))
                cost = int(p.get("clock_cost_s", puz["defaults"]["vault_clock_cost_s"]))
                lb = p.get("loot_by_band") or puz["default_loot_by_band"]
                need(all(isinstance(v, list) for v in lb.values()), "%s vault loot is a table id, not stacks" % d["id"])
                vaults.append({"kind": "vault", "name": pretty(r.get("name") or r["id"]), "chests": n, "cost": cost,
                               "rows": {b: loot_for(lb, b) for b in nb}})
            elif r["kind"] == "bank_vault":
                cfg = ex1["bank_vault"]
                lb = p.get("loot_by_band") or cfg["default_loot_by_band"]
                vaults.append({"kind": "bank_vault", "name": pretty(r["id"]),
                               "chests": int(p.get("chests", cfg["defaults"]["chests"])),
                               "cost": int(p.get("clock_cost_s", cfg["defaults"]["clock_cost_s"])),
                               "rows": {b: loot_for(lb, b) for b in nb}})
        x["vaults"] = vaults
        # ore
        cfg = DR.theme_cfg(d)
        res_rooms = [r for r in recs if r["kind"] == "resources"]
        need(len(res_rooms) == 1, "%s: one resources room" % d["id"])
        x["ore"] = None
        if cfg is not None:
            x["ore"] = {"piles": {b: DR.table_row(b) for b in nb},
                        "seam": {b: DR.seam_row(b) for b in nb} if DR.seam_uses_table(d["theme"]) else None,
                        "veins": bool(cfg.get("veins"))}
        # catchable Pokemon
        c = {"ambient": {b: ambient_species(d, themes, b) for b in nb}}
        nests = []
        for r in recs:
            if r["kind"] == "nest" and (r.get("params") or {}).get("catchable", True):
                sp = []
                for rr in byid[r["id"]]:
                    sp += list((rr.get("params") or {}).get("species") or [])
                nests.append({"species": sp, "count": (r.get("params") or {}).get("count_by_band") or {}})
        c["nests"] = nests
        mini = {}
        for r in recs:
            if r["kind"] == "miniboss" and (r.get("params") or {}).get("catchable", True):
                for rr in byid[r["id"]]:
                    p = rr.get("params") or {}
                    for b in nb:
                        one = (p.get("species_by_band") or {}).get(str(b))
                        pool = (p.get("species_pool_by_band") or {}).get(str(b)) or ([one] if one else [])
                        for sp in pool:
                            mini.setdefault(b, [])
                            if sp not in mini[b]:
                                mini[b].append(sp)
        c["miniboss"] = mini
        x["catch"] = c
        # fishing pool of the theme
        fp = ex2["fishing"]["species"].get(d["theme"]) if "fishing_room" in kinds else None
        x["fishing"] = {b: fp[str(b)] for b in nb} if fp else None
        dungeons.append(x)
    m["dungeons"] = dungeons
    return m


# ------------------------------------------------------------------------------------------------ rendering


def render_first_rift(m):
    """The rift guide book's text (tools/dungeon_guide.py sections(), the SAME function the book is built from, so the book
    handed to a player on their first arrival and this section cannot drift)."""
    import dungeon_guide as GB
    g = ['<section %s><h2>Your first rift</h2>' % player_site.section_attr("first-rift")]
    g.append('<p>The first time you arrive in a dungeon run, the rift hands you a written book, the <b>%s</b>. This section is '
             'its text, so you can read it before you go. It holds the rules every dungeon shares; what differs from one '
             'dungeon to the next is on the board in its entry room and on its card below.</p>' % esc(GB.TITLE))
    for _key, title, paras in GB.sections(m["doc"]):
        g.append('<h3>%s</h3>' % esc(title))
        g.extend('<p>%s</p>' % esc(p) for p in paras)
    g.append('</section>')
    return "".join(g)


def render_basics(m):
    dex, bands, nb = m["dex"], m["bands"], m["nb"]
    g = []
    sig_rows = []
    for s in m["sigils"]:
        rec = ", ".join("%d x %s" % (n, dex.item(i)) for i, n in s["recipe"])
        sig_rows.append([str(s["band"]), esc(s["caps"]), esc(s["name"]), esc(rec)])
    g.append('<section %s><h2>How a rift run works</h2>' % player_site.section_attr("basics"))
    g.append('<p>A <b>rip</b> is a tear in the world that opens onto a pocket dungeon: one timed run, played %s. You '
             'step through with a <b>sigil</b>, cross the dungeon\'s threshold, and have until the clock runs out to '
             'fight, climb, dig, catch and find your way to the far rip. Everything you pick up is yours to keep '
             'except what the rift lends you.</p>' % ("solo" if m["doc"]["engine"]["members_max"] == 1 else "in a party"))
    g.append('<div class="box warn"><p><b>A rip draws its dungeon from your progress, not from where it stands.</b> Any rip '
             'may open onto any dungeon. Your band (below) decides which are possible: a dungeon is never drawn below its '
             'first band, and some also ask for a badge (listed under each). Of the dungeons you may enter, the rift opens '
             'the one you drew least recently, and chance breaks a tie; backing out still counts as a draw. The thirteen '
             'rips on the old mine\'s trail are test rips and stay where they are, with more rips out in the regions '
             '(docs/mechanics/DUNGEON_DRAW.md). The figures on this page are working values, tuned as the dungeons are '
             'played; nothing here has been run on the live server yet.</p></div>')
    g.append('<h3>Bands and sigils</h3><p>Your <b>band</b> is set by your level cap when you enter and held for the whole '
             'run: it is the first band whose highest cap is at or above yours. Every dungeon has its own clock and its own '
             'prizes at each of the %d bands (below); a late dungeon is not drawn early, an early one scales up with you.</p>' % len(nb))
    g.append(table(["Band", "Level caps", "Sigil", "Crafted from"], sig_rows))
    g.append('<ul><li>One sigil is spent per run, when you cross the threshold (the far door of the entry room). It '
             'accepts <b>your own band\'s sigil, or else the lowest higher band\'s you hold</b>. A lower band\'s sigil is '
             'refused (&ldquo;This sigil is too weak for you now.&rdquo;).</li>'
             '<li>Leave by the back rip <b>before you cross the threshold</b> and the sigil is returned. A death before '
             'the threshold does not return it.</li>'
             '<li>You know the recipes of your own band and the bands below it.</li>'
             '<li>There is no free first run: a sigil is always needed.</li>'
             '<li>After a run, that dungeon is locked to you for %d minutes of server running time, counted from the '
             'threshold.</li>'
             '<li>You are lent a <b>%s</b> (an iron pickaxe) that breaks ore and a few marked blocks, and nothing '
             'else. The rift takes it back when the run ends.</li></ul>'
             % (m["lockout_min"], esc(m["rift_pick"]["name"])))
    g.append('<h3>The clock</h3>')
    t = m["warn"]
    g.append('<p>Each run has a clock that depends on the dungeon and your band (see each dungeon below). A bar shows it; '
             'you get a warning at %s and again at %s, and a count for the last %d seconds. When it reaches zero the '
             'rift closes and throws you out. A fall costs %d seconds. A wrong guess at a puzzle, and every chest you '
             'open in a vault, costs seconds too; the price is shown in the room.</p>'
             % (clock_text(t[0]), clock_text(t[1]), m["clock"]["countdown_last_s"], m["clock"]["fall_penalty_s"]))
    g.append('<h3>Points: the more you take, the faster the clock runs</h3>')
    r = m["rate"]
    per = int(r["per_step_cp"]) / 100.0
    g.append('<p>Everything valuable you take from a run is weighed in <b>points</b>. Every %s points make the clock run '
             '0.1x faster, up to %s at %s points. Points are only ever added: the clock never slows back down. They '
             'are counted for each person separately.</p>'
             % (("%g" % per), mult_text(r["cap"] / float(r["base"])), points_text(m["cap_cp"])))
    g.append(table(["Points taken", "Clock speed"],
                   [[points_text(cp), mult_text(x)] for cp, x in m["steps"]]))
    g.append('<p>What counts, and what it is worth:</p>')
    ore_rows = []
    for o in m["ores"]:
        ore_rows.append([esc(pretty(o["res"])), esc(o["item"]), points_text(o["block_cp"]), points_text(o["item_cp"])])
    g.append('<h4>Ore mined</h4>')
    g.append(table(["Ore", "Drops", "Points per ore block mined", "Points per piece dropped"], ore_rows))
    cc = m["catch_cp"]
    catch_rows = []
    for i, b in enumerate(nb):
        catch_rows.append([str(b), points_text(cc["ambient"][i]), points_text(cc["nest"][i]), points_text(cc["miniboss"][i]),
                           points_text(cc["habitat"][i])])
    g.append('<h4>Pokemon caught (points per catch)</h4>')
    g.append(table(["Band", "Roaming in a room", "From a nest or pool", "Mini-boss", "Hidden prize"], catch_rows))
    g.append('<p>A catch counts by the kind of room you stand in when the ball lands. The hidden prize is worth the most: '
             'a rare Pokemon before band %d, a legendary one from band %d. A fossil you dig up is worth %s points; an '
             'egg you buy counts as a nest catch; the wishing well charges only what it pays you above what you threw '
             'in; each vault chest counts its expected contents (see the vaults below).</p>'
             % (m["legend_from"], m["legend_from"], points_text(m["fossil_cp"])))
    g.append('<p><b>Not counted:</b> relics, and what wild Pokemon drop.</p>')
    g.append('<h3>Deaths and the timer</h3>')
    ti = m["death_titles"]
    need(sorted(ti) == sorted(DEATH_CAUSE), "the death messages are not the four causes DEATH_CAUSE describes")
    rows = [[esc(DEATH_CAUSE[k]), esc(ti[k]["title"]), esc(ti[k]["subtitle"] or "")] for k in sorted(ti)]
    g.append('<p>Any way of dying in a rift (the timer, a boss stage, a trainer, a Pokemon, a fall, lava) ends that run. '
             'There is no recovery claim inside a rift: no Pokemon or trainer there holds your things for you. A death '
             'costs exactly:</p><ul>'
             '<li>the blackout\'s money, $%d, which nothing in the rift holds for you, so it is gone for good;</li>'
             '<li>the run you paid a sigil for;</li><li>the price of trying again: another sigil, and the lockout.</li>'
             '</ul><p>Trainer battles inside a rift pay no money.</p>' % m["blackout_money"])
    g.append('<p>What you keep: %s</p>' % esc(" ".join(m["death_chat"][:1] + m["death_chat"][2:])))
    g.append('<p>The rift tells you how a run ended:</p>')
    g.append(table(["When", "Message", "Subtitle"], rows))
    g.append('<p>Pokemon you catch inside: the plan is that a catch is only yours if you leave alive. That is not built '
             'yet, so today a catch is kept either way.</p>')
    pc = m["doc"]["engine"]["prize"]["chance_by_band"]
    g.append('<h3>The hidden prize</h3><p>Each dungeon may hide one prize Pokemon. It is not there every run: whether it is '
             'is rolled when you cross the threshold, and the chance rises with your band (by default %s). Before band %d '
             'it is a rare Pokemon; from band %d it is a legendary Pokemon and only a Beast Ball will hold it. Each '
             'dungeon\'s card gives its own chance and kind at each band, and never the species.</p>'
             % (", ".join("%d%%" % c for c in pc), m["legend_from"], m["legend_from"]))
    g.append('<h3>The healer</h3>')
    need(all(x["healers"] >= 1 for x in m["dungeons"]), "a dungeon has no healer")
    g.append('<p>Each dungeon has a safe room with a healer that restores your party.</p>')
    g.append('<h3>Relics and collections</h3>')
    rl = [x["relics"] for x in m["dungeons"]]
    g.append('<p>Some rooms hide a secret, and at the secret a <b>relic</b> stands on a pedestal: walk up and it is yours, '
             'once, for good. A relic has no price and does not speed the clock; it is a reward for looking. Find every '
             'relic in a dungeon (%d to %d of them, per dungeon, listed below) to complete that dungeon\'s collection, '
             'shown as an advancement.</p>' % (min(rl), max(rl)))
    g.append('</section>')
    return "".join(g)


def render_optional(m):
    dex, nb = m["dex"], m["nb"]
    e1, e2 = m["ex1"], m["ex2"]
    g = ['<section %s><h2>The six optional rooms</h2>' % player_site.section_attr("optional")]
    g.append('<p>Most dungeons hide some of these side rooms. Each costs a little clock and gives something back. Which '
             'ones a dungeon has is on its own card.</p>')
    # bank vault
    bv = e1["bank_vault"]["defaults"]
    g.append('<h3>Bank vault</h3><p>A door with a code lock. The %d digits are written on signs in other rooms of the same '
             'dungeon; the code changes every run. You have %d tries, and a wrong code costs %d seconds. The vault holds '
             '%d chests; each one you open costs %d seconds. What is inside is on the dungeon\'s card.</p>'
             % (bv["digits"], bv["max_tries"], bv["penalty_s"], bv["chests"], bv["clock_cost_s"]))
    # wishing well
    ww = e1["wishing_well"]
    g.append('<h3>Wishing well</h3><p>Throw an item of worth into the well (up to %d throws a run; nothing worth less than '
             '%s of a point). The well keeps some, and pays back a share of what the item was worth, in a better item the '
             'more it pays. Throwing the reward back in loses on average.</p>'
             % (ww["defaults"]["throws"], points_text(ww["defaults"]["min_cp"])))
    share_name = {0: "The well keeps it"}
    rows = []
    for b in nb:
        parts = []
        for w, s in ww["shares_by_band"][str(b)]:
            parts.append("%d%%: %s" % (w, "nothing back" if s == 0 else "%d%% of its worth" % s))
        pays = ", ".join(p[1] for p in ww["ladders_by_band"][str(b)])
        rows.append([str(b), esc("; ".join(parts)), esc(pays)])
    g.append(table(["Band", "Odds of each return", "Pays in (small win to big win)"], rows))
    # bait
    g.append('<h3>Bait room</h3><p>Leave a bait on the altar. Something follows its scent and appears in a room of your '
             '<b>next</b> run, wandering and catchable. Which bait lures what:</p>')
    br = e1["bait_room"]
    tiers = br.get("tiers")          # absent: the older table, no shiny or alpha chance (this page then prints none)
    if tiers:
        g.append('<p>The lure is caught at your band\'s <b>lower</b> cap. It has two separate chances: to be <b>shiny</b> and to be '
                 'an <b>alpha</b>. Either, both or neither can happen; the chances depend on the bait\'s tier.</p>')
    rows = []
    for bt in br["baits"]:
        cells = [esc(bt["name"].capitalize())]
        if tiers:
            t = tiers[bt["tier"]]
            cells += [esc(bt["tier"].replace("_", " ").capitalize()), "%g%%" % round(t["shiny_chance"] * 100, 4),
                      "%g%%" % round(t["alpha_chance"] * 100, 4)]
        for b in nb:
            cells.append(esc(dex.show(bt["species_by_band"][str(b)]) or "?"))
        rows.append(cells)
    g.append(table(["Bait"] + (["Tier", "Shiny chance", "Alpha chance"] if tiers else []) + ["Band %d" % b for b in nb], rows))
    # fishing
    g.append('<h3>Fishing pool</h3><p>A still pool with a rod hanging on a post (lent to you for the run). What bites '
             'depends on the dungeon and on your band, and is listed on the dungeon\'s card. The fish are caught like any '
             'wild Pokemon, at or below your band\'s lower cap.</p>')
    # eggs
    eg = e2["eggs"]
    g.append('<h3>Egg seller</h3><p>A seller offers one egg a run, paid for in <b>clock time</b>, not money. It hatches in '
             'your pack while you walk. The seller needs at least %d seconds left on your clock to bargain. The three '
             'offers at each band, and the price:</p>' % eg["price"]["min_left_s"])
    rows = []
    for b in nb:
        offers = [o["species"] for o in eg["offers"][str(b)]]
        shown = dex.shown(offers)
        rows.append([str(b), esc(", ".join(shown)), "%d s" % eg["price"]["clock_s_by_band"][str(b)]])
    g.append(table(["Band", "Offers", "Price"], rows))
    # fossils
    fo = e2["fossils"]
    g.append('<h3>Fossil dig</h3><p>A bay of dig blocks with one fossil hidden in it. Break blocks with the rift pick until '
             'the rock gives it up. The fossil is one of these at your band, with the chance shown; the dig is worth %s '
             'points on the clock.</p>' % points_text(fo["greed_cp"]))
    rows = []
    for b in nb:
        items = fo["by_band"][str(b)]
        tot = sum(w for _, w in items)
        rows.append([str(b), esc(", ".join("%s (%d%%)" % (dex.item(i), round(100.0 * w / tot)) for i, w in items))])
    g.append(table(["Band", "Possible fossils"], rows))
    g.append('</section>')
    return "".join(g)


def render_dungeon(m, x):
    dex, nb, gt, doc = m["dex"], m["nb"], m["gt"], m["doc"]
    g = ['<section %s><h2>%s<small> %s</small></h2>' % (player_site.section_attr(slug(x["id"])), esc(x["name"]),
                                                      esc(x["theme_name"]))]
    # route summary
    forks = "; ".join("fork %d offers %d ways (%s)" % (i + 1, len(f), ", ".join(f)) for i, f in enumerate(x["forks"]))
    route = ["%d forks in the road: %s" % (len(x["forks"]), forks) if x["forks"] else "no forks",
             "an optional wing off the main road" if x["wing"] else "no optional wing",
             "one set piece: " + SETPIECE_WORDS[x["piece"][0]],
             "%s%s%s" % (("a safe room with a healer" if x["healers"] else "no healer"),
                         "; a vault" if any(v["kind"] == "vault" for v in x["vaults"]) else "",
                         "; a bank vault" if any(v["kind"] == "bank_vault" for v in x["vaults"]) else "")]
    g.append('<p><b>The road:</b> %s.</p>' % esc("; ".join(route)))
    # the draw (docs/mechanics/DUNGEON_DRAW.md 2.2): the dungeon's first band and the badge it asks for, in a player's words
    fb = x["first_band"]
    gate = ("all %d bands" % len(nb)) if fb <= nb[0] else ("band %d and up" % fb if fb < nb[-1] else "band %d only" % fb)
    if x["gate"]:
        gate += ", once you hold %s" % GATE_WORDS.get(x["gate"].rsplit("/", 1)[-1], x["gate"])
    g.append('<p><b>Bands served:</b> %s. <b>Relics:</b> %d.%s</p>'
             % (esc(gate), x["relics"],
                (" <b>Optional rooms:</b> %s." % esc(", ".join(OPTIONAL_NAMES[k] for k in x["optional"]))) if x["optional"] else ""))
    g.append(table([""] + ["Band %d" % b for b in nb], [["Run clock"] + [clock_text(x["clock"][b]) for b in nb]]))
    # prize
    if x["prize"]:
        rows = []
        for p in x["prize"]:
            if p["kind"] is None:
                rows.append([str(p["band"]), "none", ""])
            else:
                what = "a rare Pokemon" if p["kind"] == "rare" else "a legendary Pokemon"
                rows.append([str(p["band"]), "%d%%" % p["chance"], what])
        g.append('<details><summary>The hidden prize</summary><p>Somewhere in the dungeon a prize may be waiting. It is '
                 'not there every run: the chance is rolled when you cross the threshold, and word of it may reach you at '
                 'the gate. It is catchable, at your band\'s lower cap. From band %d the prize is legendary-class and '
                 'only a Beast Ball will hold it.</p>%s</details>'
                 % (m["legend_from"], table(["Band", "Chance it is there", "Kind"], rows)))
    # vaults
    for v in x["vaults"]:
        rows = []
        for b in nb:
            spec = v["rows"][b]
            cp = DG.chest_cp(gt, spec)
            rows.append([str(b), esc("; ".join(stack_text(dex, s) for s in spec)),
                         points_text(cp) if cp is not None else "?"])
        title = "Vault: %s" % v["name"] if v["kind"] == "vault" else "Bank vault: %s (code lock)" % v["name"]
        g.append('<details><summary>%s</summary><p>%d chests, every one the same; each costs %d seconds of clock to open. '
                 'The list is what one chest holds.</p>%s</details>'
                 % (esc(title), v["chests"], v["cost"], table(["Band", "Each chest holds", "Worth (points on the clock)"], rows)))
    # ore
    if x["ore"] is None:
        g.append('<details><summary>Ore</summary><p>This dungeon has no ore piles. Its resource room keeps only the seam '
                 'in its wall.</p></details>')
    else:
        rows = []
        for b in nb:
            piles = x["ore"]["piles"][b]
            cells = [str(b)] + [str(piles.get(res, "")) for res in RES_ORDER]
            cells.append("%d" % sum(piles.values()))
            rows.append(cells)
        note = "Heaps of ore%s. The table is how many ore blocks the heaps and walls hold at each band." % (
            " and veins in the wall" if x["ore"]["veins"] else "")
        cache = [(b, m["cache"][b]) for b in nb if m["cache"][b]]
        if cache:
            note += " A chest beside the heaps also holds, at band %s" % "; at band ".join(
                "%d: %s" % (b, ", ".join("%d x %s" % (n, dex.item(i)) for _k, i, n in items)) for b, items in cache) + "."
        seam = ""
        if x["ore"]["seam"]:
            seam = ("<p>The wall seam (24 blocks) holds, by band: " + esc("; ".join(
                "band %d: %s" % (b, ", ".join("%d %s" % (n, k) for k, n in x["ore"]["seam"][b].items())) for b in nb))
                    + ".</p>")
        g.append('<details><summary>Ore</summary><p>%s</p>%s%s</details>'
                 % (esc(note), table(["Band"] + [pretty(r) for r in RES_ORDER] + ["Total"], rows), seam))
    # catchable
    c = x["catch"]
    rows = []
    for b in nb:
        rows.append([str(b), esc(", ".join(dex.shown(c["ambient"][b])) or "-"),
                     esc(", ".join(dex.shown(c["miniboss"].get(b, []))) or "-")])
    nest_p = ""
    for n in c["nests"]:
        sp = dex.shown(n["species"])
        nest_p += ("<p>A nest holds %s; how many of them appear at each band: %s.</p>"
                   % (esc(", ".join(sp)), esc(", ".join("band %s: %s" % (b, n["count"][b]) for b in sorted(n["count"])))
                      if n["count"] else ""))
    g.append('<details><summary>Pokemon you can catch</summary><p>Roaming Pokemon in the rooms are catchable, at or below '
             'your band\'s lower cap. A mini-boss is one of the listed.</p>%s%s</details>'
             % (table(["Band", "Roaming in the rooms", "Mini-boss is one of"], rows), nest_p))
    if x["fishing"]:
        rows = []
        for b in nb:
            cells = [str(b)]
            for rarity in RARITY_ORDER:
                sp = [s for s, _w in x["fishing"][b].get(rarity, [])]
                cells.append(esc(", ".join(dex.shown(sp)) or "-"))
            rows.append(cells)
        g.append('<details><summary>Fishing pool</summary>%s</details>'
                 % table(["Band"] + [pretty(r) for r in RARITY_ORDER], rows))
    g.append('</section>')
    return "".join(g)


def render(m):
    secs = [("first-rift", "Your first rift"), ("basics", "How a run works"), ("optional", "Optional rooms")] + \
        [(slug(x["id"]), x["name"]) for x in m["dungeons"]]
    toc = "".join('<li><a href="#%s">%s</a></li>' % (esc(k), esc(t)) for k, t in secs)
    body = ['<main><h1>Dungeons</h1><p class="lead">Thirteen dungeons, each a timed run through a pocket world. How a run '
            'works, then the six optional rooms, then each dungeon. New to rifts? Start with Your first rift.</p>',
            '<nav class="box toc" id="contents"><b>Contents</b><ol>%s</ol></nav>' % toc,
            player_site.filter_nav(secs, label="Show one part")]
    body.append(render_first_rift(m))
    body.append(render_basics(m))
    body.append(render_optional(m))
    for x in m["dungeons"]:
        body.append(render_dungeon(m, x))
    body.append('<section id="not-covered"><h2>What this page leaves out</h2><ul>'
                '<li>Where the rips are, the vault codes, the relics\' names and places, the trainers and bosses: left for '
                'you to find.</li>'
                '<li>What the hidden prize is. Only its kind and its chance are here.</li>'
                '<li>The result of a real run: these figures come from the dungeon data, not from play. Where the game '
                'differs, the game is right: say so.</li></ul></section></main>')
    sources = ('<p class="src">From data/dungeons.json and the dungeon data files beside it, run through the dungeon '
               'engine\'s own functions, with Pokemon and item names from %s.</p>' % esc(m["jar"]))
    return player_site.page(GUIDE, "".join(body), body_class="page-items page-dungeons", not_covered_href="#not-covered",
                            sources_html=sources)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--jar", help="the Cobblemon 1.8 jar (default: the offline snapshot's mods folder)")
    p.add_argument("--check", action="store_true", help="regenerate in memory; exit 1 if the page differs or its "
                                                        "guides.json entry is not current")
    a = p.parse_args(argv)
    model = collect(a.jar)
    text = render(model)
    out = Path(a.out)
    entry = GUIDE if out.resolve() == OUT.resolve() else None  # a page written elsewhere is not the site's
    counts = "%d dungeons, %d species withheld" % (len(model["dungeons"]), len(model["dex"].withheld))
    if a.check:
        ok, why = player_site.check(out, text, entry)
        if not ok:
            print("%s is %s: run python tools/player_site.py" % (out, why))
            return 1
        print("%s is current (%s)" % (out, counts))
        return 0
    did = player_site.write(out, text, entry)
    print("%s %s: %s, %d bytes" % (did, out, counts, len(text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
