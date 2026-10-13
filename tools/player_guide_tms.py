#!/usr/bin/env python
"""The players' TM guide, docs/player/tms.html: every TM a player can get, by the badge that opens it, with each way to
get it and when.

  python tools/player_guide_tms.py            # write docs/player/tms.html and register it in guides.json
  python tools/player_guide_tms.py --check    # regenerate in memory; exit 1 if the page or its entry is stale
  python tools/player_guide_tms.py --out F    # write elsewhere (not the site's page, not registered)

WHY A PAGE OF ITS OWN. items.html lists an item through a source a player uses on purpose and leaves out what only a
cache or a shrine gives; 802 TMs would bury that dictionary, and a player asks a different question of a TM: "what
does it do, and when can I have it". items.html is linked for prices and the bank, not repeated.

THE TMs ARE THE 802 OF THE SCORE TABLE (docs/mechanics/TM_POWER_GATE.json, written by tools/tm_power_score.py from Mega
Showdown's moves.js): the move, its type, category, power and accuracy are that table's. THE BADGE a TM opens at is the
crafting gate's own (tools/tm_gate.py), recomputed here from the same inputs without a server:
  tm_gate.place(data/tm_gate.json, the score table, the shelf lines)   the shelf wins, then an outlier group, then the
                                                                      band of the score (docs/mechanics/TM_POWER_GATE.md)
  then badge_rule.chain.raises                                         a TM crafted from another TM never opens first
The page stops when a raise's `from` is no longer the placed badge, and tests/test_player_guide_tms.py compares every
badge with the plan the gate prints for the 2026-10-05 server snapshot when that snapshot is present.

THE WAYS TO GET ONE (each is a source; a TM can have several):
  Craft         every TM: a crafting-table recipe that enters the recipe book once the player holds the badge (the
                cobblers_tm_gate pack, data/tm_gate.json). The disc grade is the score table's `disc_grade`; the rest of
                the recipe is the game's recipe book, not repeated here.
  Counter       data/markets.json `stock` of a SITED record (the items page's own shop_sources): town, the shop screen's
                title and the unit price. A `held_stock`, `superseded_stock` or unsited line is NEVER a source: no
                merchant sells it (price_policies.income_gate.held). The price is the gate: a counter cannot check a badge,
                so a TM is priced above the most a player one badge behind can have earned.
  Leader        data/progression.json first_win_rewards: the leader's one TM, drawn once, on the first win, from the
                listed `one_of` (a name listed twice is twice as likely).
  TM Machine    Cobblemon 1.8.0's own machine (data/cobblemon/tms/*.json in the jar): the same move, printed from gems.
                The campaign leaves it ungated (data/tm_gate.json does_not_cover).
  Poke Marts and the barter board carry no TM (read, not assumed: the page lists them if the data ever does).

WHAT THE PAGE NEVER LISTS. A TM that only a cache, a shrine or a reward chest gives (data/rewards.json and the other
secret files of tests/test_player_site_leaks.py) is not named as found anywhere: those are discoveries. So the page says
"TMs you find in the world are left for you to discover" and lists none. A TM with no counter and no leader reward is
still craftable; the page says which, and counts them. No coordinate, NPC seat or keeper position is printed.

Not checked in a running game: the crafting gate (experiment EXP-067), the counter prices (proof P-7) and the machine.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import player_site  # noqa: E402  the shared header, footer, filter, search and manifest of docs/player/
import player_guide_battles as PB  # noqa: E402  the Cobblemon jar finder
import player_guide_items as PI  # noqa: E402  the shops, Marts, barter and item names
import tm_gate as TG  # noqa: E402  the crafting gate's own placement

OUT = ROOT / "docs" / "player" / "tms.html"
GUIDE = {"file": "tms.html", "title": "TMs", "label": "TMs", "order": 32,
         "description": "Every TM and when you can have it: the badge that opens each one, its move, type and power, "
                        "and where to craft, buy or win it.",
         "generator": "tools/player_guide_tms.py"}
PROGRESSION = "data/progression.json"
GYMS = "data/gym_trainers.json"
BADGES = tuple(range(1, 9))
TYPES = ("Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison", "Ground", "Flying", "Psychic",
         "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy")
CATEGORIES = ("Physical", "Special", "Status")
MACHINE_WORDS = {"cobblemon:default": "always on offer", "cobblemon:unlockable": "unlocked through play in Cobblemon",
                 "cobblemon:advancement": "unlocked by an advancement in Cobblemon"}
# vanilla ids whose title-cased id is not the game's name (the Cobblemon jar has no vanilla names)
ACRONYMS = {"minecraft:tnt": "TNT"}
esc = player_site.esc
pretty = PI.pretty


def doc(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ inputs


def final_badges(gate, scores, shelf):
    """{tm item: {badge, rule, ...}} as tools/tm_gate.py plan() places it: place(), then the chain raises. Stops on a
    placement problem or a raise that no longer matches (the raises are listed exactly, or the gate fails too)."""
    placed, problems = TG.place(gate, scores, shelf)
    if problems:
        raise SystemExit("tm_gate.place reports %d problem(s); first: %s" % (len(problems), problems[0]))
    for r in gate["badge_rule"]["chain"]["raises"]:
        if placed[r["item"]]["badge"] != r["from"]:
            raise SystemExit("chain raise %s says from badge %s; the gate places it at %s: data/tm_gate.json is stale"
                             % (r["item"], r["from"], placed[r["item"]]["badge"]))
        placed[r["item"]] = dict(placed[r["item"]], badge=r["to"], rule=placed[r["item"]]["rule"] + "; chain raise")
    return placed


def leader_rewards():
    """{tm item: [{leader, gym, flag, number, of}]} from first_win_rewards: `number` copies of the item in the leader's
    `one_of` list of `of` entries. The leader's name is data/gym_trainers.json's display_name for its upstream id."""
    prog = doc(PROGRESSION)
    found = []

    def walk(n):
        if isinstance(n, dict):
            if isinstance(n.get("first_win_rewards"), dict):
                found.append(n["first_win_rewards"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(prog)
    if len(found) != 1:
        raise SystemExit("%s: expected one first_win_rewards, found %d" % (PROGRESSION, len(found)))
    gyms = {g["upstream_trainer_id"]: g for g in doc(GYMS)["trainers"]}
    out = {}
    for tid, rec in sorted(found[0]["trainers"].items()):
        pool = [i for i in rec.get("one_of") or [] if i.startswith("tmcraft:")]
        if not pool:
            continue
        g = gyms.get(tid)
        m = re.fullmatch(r"gym(\d)_cleared", rec["flag"])
        if g is None or not m:
            raise SystemExit("%s gives TMs on flag %s but is not one of the eight gym leaders" % (tid, rec["flag"]))
        for item in dict.fromkeys(pool):
            out.setdefault(item, []).append({"leader": g["display_name"], "gym": int(m.group(1)), "id": g["id"],
                                             "number": pool.count(item), "of": len(pool)})
    return out


def machine(jar, names):
    """{move id: {type, how, recipe [(count, name)]}} for every native TM in the jar."""
    z = zipfile.ZipFile(jar)
    lang = json.loads(z.read("assets/cobblemon/lang/en_us.json").decode("utf-8"))
    out = {}
    for n in z.namelist():
        if not (n.startswith("data/cobblemon/tms/") and n.endswith(".json")):
            continue
        d = json.loads(z.read(n).decode("utf-8-sig"))
        how = {o.get("variant") for o in d["obtainMethods"]}
        if len(how) != 1 or not how <= set(MACHINE_WORDS):
            raise SystemExit("%s: obtain methods %s are not ones this page can put in words" % (n, sorted(how, key=str)))
        rec = []
        for r in d["recipe"]:
            if "item" in r:
                what = ACRONYMS.get(r["item"]) or names(r["item"])
            elif "tag" in r:  # any item of a tag: "any Berries"
                what = PI.TAGS.get(r["tag"], "any " + pretty(r["tag"]))
            else:
                raise SystemExit("%s: a recipe line this page cannot put in words: %r" % (n, r))
            rec.append((int(r.get("count", 1)), what))
        out[d["moveName"]] = {"type": pretty(d["type"]), "how": MACHINE_WORDS[next(iter(how))], "recipe": rec,
                              "name": lang.get("cobblemon.move.%s" % d["moveName"]) or pretty(d["moveName"])}
    return out


def collect(jar_path=None):
    jar = PB.find_jar(jar_path)
    gate = TG.load()
    scores = TG.load_scores(gate)
    mk, td, dt = doc("data/markets.json"), doc("data/traders.json"), doc("data/direct_trades.json")
    towns = PI.place_names(mk)
    names = PI.Names(jar, mk)
    shelf = TG.shelf_badges(mk)
    placed = final_badges(gate, scores, shelf)
    shops, not_sold = PI.shop_sources(mk, towns)
    marts = PI.mart_sources(td, towns)
    barter = PI.barter_lines(dt, mk, towns)
    leaders = leader_rewards()
    native = machine(jar, names)
    tms = {}
    for item, row in scores["tms"].items():
        mid = item.split("tm_", 1)[1]
        tms[item] = {"item": item, "id": mid, "move": row["move"], "type": row["type"], "category": row["category"],
                     "power": row["base_power"], "accuracy": row["accuracy"], "pp": row["pp"],
                     "badge": placed[item]["badge"], "grade": row.get("disc_grade"),
                     "shop": shops.get(item, []), "mart": marts.get(item, []),
                     "barter": [b for b in barter if b["sell"]["id"] == item],
                     "leader": leaders.get(item, []), "machine": native.get(mid)}
    stray = sorted(set(leaders) - set(tms))
    if stray:
        raise SystemExit("a leader gives %s, which the score table does not have" % stray[:3])
    only_machine = sorted(set(native) - {t["id"] for t in tms.values()})
    held_only = sorted({line["item"] for _rid, _k, line in not_sold if line["item"] in tms} - set(shops))
    return {"tms": tms, "machine_only": {m: native[m] for m in only_machine}, "held": held_only,
            "badges": mk.get("badges", {}), "gate": gate, "jar": jar.name, "income": mk["income_basis"],
            "names": names}


# ------------------------------------------------------------------------------------------------ render


def dollars(n):
    return PI.dollars(n)


def badge_name(m, b):
    return m["badges"].get("gym%d_cleared" % b, "badge %d" % b)


def power_text(t):
    return "-" if not t["power"] else str(t["power"])


def accuracy_text(t):
    return "-" if t["accuracy"] is True or t["accuracy"] is None else "%d" % t["accuracy"]


def pct(n, of):
    return "%d%%" % round(100.0 * n / of)


def source_items(t, m):
    lis = []
    craft = "Craft" + (" (%s blank disc)" % t["grade"] if t["grade"] else "")
    lis.append('<li data-src="craft">%s</li>' % esc(craft))
    for s in sorted(t["shop"], key=lambda s: (s["town"], s["seller"])):
        lis.append('<li data-src="shop">Counter in %s (%s): %s</li>' % (esc(s["town"]), esc(s["seller"]),
                                                                        esc(dollars(s["price"]))))
    for s in t["mart"]:
        lis.append('<li data-src="mart">%s: %s</li>' % (esc(PI.where_words(s)), esc(PI.price_words(s))))
    for b in t["barter"]:
        lis.append('<li data-src="barter">Barter in %s: %s</li>' % (
            esc(b["town"]), esc(" and ".join("%d %s" % (g["count"], m["names"](g["id"])) for g in b["give"]))))
    for r in sorted(t["leader"], key=lambda r: r["gym"]):
        lis.append('<li data-src="leader">Gym %d leader <a href="battles.html#t-%s">%s</a>, first win only (%s)</li>'
                   % (r["gym"], esc(r["id"]), esc(r["leader"]),
                      "the one TM it gives" if r["of"] == 1 else "%s chance, one of %d" % (pct(r["number"], r["of"]), r["of"])))
    if t["machine"]:
        mac = t["machine"]
        lis.append('<li data-src="machine">TM Machine (%s): %s</li>'
                   % (esc(mac["how"]), esc(" + ".join("%d %s" % (c, n) if c > 1 else n for c, n in mac["recipe"]))))
    return "".join(lis)


def tm_row(t, m):
    words = " ".join([t["move"], t["type"], t["category"], t["id"], "badge %d" % t["badge"]]).lower()
    return ('<tr data-tm data-name="%s"><td>%s<span class="id">%s</span></td><td>%s</td><td>%s</td>'
            '<td class="n">%s</td><td class="n">%s</td><td><ul>%s</ul></td></tr>'
            % (esc(words), esc(t["move"]), esc(t["item"]), esc(t["type"]), esc(t["category"]), power_text(t),
               accuracy_text(t), source_items(t, m)))


def head():
    return ('<thead><tr><th>TM</th><th>Type</th><th>Kind</th><th class="n">Power</th><th class="n">Acc.</th>'
            '<th>How to get it</th></tr></thead>')


def render_how(m):
    tms = m["tms"].values()
    n = len(m["tms"])
    shop = sum(1 for t in tms if t["shop"] or t["mart"] or t["barter"])
    lead = sum(1 for t in tms if t["leader"])
    mach = sum(1 for t in tms if t["machine"])
    only = sum(1 for t in tms if not (t["shop"] or t["mart"] or t["barter"] or t["leader"] or t["machine"]))
    badges = "; ".join("gym %d (%s): %d" % (b, badge_name(m, b), sum(1 for t in tms if t["badge"] == b)) for b in BADGES)
    cum = m["income"]["cumulative_by_badge"]
    return (
        '<section %s><h2>How you get a TM</h2><p>There are %d TMs. Each is listed under the badge that opens it, the '
        'first moment you can craft it. Every TM can be crafted, and that is the one way that never runs out; the other '
        'ways are shortcuts for a few.</p><ul>'
        '<li><b>Craft it.</b> Hold the badge and the recipe appears in your crafting recipe book (most need a blank '
        'disc of the grade shown, plus the gems and items the recipe book lists). Before you hold the badge the recipe '
        'is not there. For %d of the %d TMs this is the only way: no shop, no leader and no machine offers them.</li>'
        '<li><b>Buy it at a counter.</b> %d TMs are on sale now at a counter shopkeeper. A counter cannot check your '
        'badges, so the price is the gate: each is priced above the most money you can have earned by then (a '
        'first-badge TM costs more than the %s you earn on the way to the first gym, a second-badge TM more than the '
        '%s you have earned by the second; see <a href="items.html#money">How money works</a>). The Poke Marts and '
        'the barter board sell no TM.</li>'
        '<li><b>Win it from a gym leader.</b> On your first win over each leader you receive one TM, drawn from that '
        'leader\'s list (%d TMs are on some leader\'s list). Rematches give none.</li>'
        '<li><b>Print it at a TM Machine.</b> Cobblemon\'s own machine (iron, tinted glass, copper and redstone; its '
        'blank TMs are two glass and two amethyst shards) prints a TM from gems and a few other items. It does not '
        'check badges here, so a player with the gems can print a TM before its badge. %d of these TMs, and %d '
        'more moves (below), are on its menu.</li></ul>'
        '<p class="small">TMs by badge: %s. Cobblemon marks some machine moves as unlocked through play; whether this '
        'server holds the machine to that has not been run.</p></section>'
        % (player_site.section_attr("how"), n, only, n, shop, dollars(cum["1"]), dollars(cum["2"]), lead, mach,
           len(m["machine_only"]), esc(badges)))


def render_badge(m, b):
    rows = sorted((t for t in m["tms"].values() if t["badge"] == b), key=lambda t: (t["move"].lower(), t["item"]))
    return ('<section %s><h2>After %s<small> (gym %d): %d TMs</small></h2><div class="wide"><table>%s<tbody>%s'
            '</tbody></table></div></section>'
            % (player_site.section_attr("badge-%d" % b), esc(badge_name(m, b)), b, len(rows), head(),
               "".join(tm_row(t, m) for t in rows)))


def render_machine(m):
    rows = []
    for mid, mac in sorted(m["machine_only"].items(), key=lambda kv: kv[1]["name"].lower()):
        recipe = " + ".join("%d %s" % (c, n) if c > 1 else n for c, n in mac["recipe"])
        words = " ".join([mac["name"], mac["type"], "machine", mid]).lower()
        rows.append('<tr data-tm data-name="%s"><td>%s</td><td>%s</td><td>%s (%s)</td></tr>'
                    % (esc(words), esc(mac["name"]), esc(mac["type"]), esc(recipe), esc(mac["how"])))
    return ('<section %s><h2>Only at the TM Machine</h2><p>These moves have no craftable TM here, only the machine\'s '
            'own.</p><div class="wide"><table><thead><tr><th>Move</th><th>Type</th><th>Printed from</th></tr></thead>'
            '<tbody>%s</tbody></table></div></section>' % (player_site.section_attr("machine"), "".join(rows)))


def chips():
    def chip(v):
        return ('<button type="button" data-fill="%s" data-fill-for="find" aria-pressed="false">%s</button>'
                % (esc(v.lower()), esc(v)))
    return ('<div class="filter chips" aria-label="Show one type or kind">%s%s</div>'
            % ("".join(chip(t) for t in TYPES), "".join(chip(c) for c in CATEGORIES)))


def sections(m):
    return ([("how", "How you get a TM")] + [("badge-%d" % b, "Badge %d" % b) for b in BADGES]
            + [("machine", "Machine only")])


def render(m):
    n = len(m["tms"])
    body = ('<main><h1>TMs</h1><p class="lead">Every TM and when you can have it. Pick a badge to see what it opens, or '
            'search by move, type or kind (try "ground", "status" or "earthquake").</p>%s%s%s%s%s%s'
            '<section id="not-covered"><h2>What this page leaves out</h2><ul>'
            '<li>TMs you can only find, win or be given somewhere in the world: those are left for you to discover.</li>'
            '<li>Counter lines that are written but that no shopkeeper sells yet (%d TMs have one): they are not '
            'listed as a way to buy. Those TMs can still be crafted or won.</li>'
            '<li>Prices of everything else and the bank: <a href="items.html">Items and money</a>.</li>'
            '<li>What happens in a running game: the badge that opens each TM and the prices are worked out from the '
            'campaign\'s data and have not been checked in play. Where the game differs, the game is right: say so.'
            '</li></ul></section></main>'
            % (player_site.filter_nav(sections(m), label="Show one part"),
               player_site.search_box("[data-tm]", "Find a TM", "e.g. Earthquake, ground, status"), chips(),
               render_how(m), "".join(render_badge(m, b) for b in BADGES), render_machine(m), len(m["held"])))
    sources = ('<p class="src">From the TM score table (docs/mechanics/TM_POWER_GATE.json), data/tm_gate.json, '
               'data/markets.json, data/progression.json, data/gym_trainers.json and the TM list and recipes in %s.</p>'
               % esc(m["jar"]))
    return player_site.page(GUIDE, body, body_class="page-tms", not_covered_href="#not-covered", sources_html=sources)


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
    tms = model["tms"].values()
    counts = "%d TMs (%d at a counter, %d from a leader, %d on the machine's menu), %d machine-only" % (
        len(model["tms"]), sum(1 for t in tms if t["shop"]), sum(1 for t in tms if t["leader"]),
        sum(1 for t in tms if t["machine"]), len(model["machine_only"]))
    if a.check:
        ok, why = player_site.check(out, text, entry)
        if not ok:
            print("%s is %s: run python tools/player_site.py" % (out, why))
            return 1
        print("%s is current (%s)" % (out, counts))
        return 0
    did = player_site.write(out, text, entry)
    print("%s %s: %s, %d bytes" % (did, out, counts, len(text.encode("utf-8"))))
    if model["names"].guessed:
        print("  named from the id (no shelf or jar name): %s" % ", ".join(sorted(model["names"].guessed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
