#!/usr/bin/env python
"""The players' training-coach guide, docs/player/training.html: the eight coaches, what each service does, and what it
costs at every badge count.

  python tools/player_guide_training.py            # write docs/player/training.html and register it in guides.json
  python tools/player_guide_training.py --check    # regenerate in memory; exit 1 if the page or its entry is stale
  python tools/player_guide_training.py --out F    # write elsewhere (not the site's page, not registered)

EVERY FIGURE IS READ FROM THE FILE THE GAME USES, never typed here:
  data/training_services.json   services.raise|ev|iv.price_by_tier / price_per_stat_by_tier (the live price fields the
                                dialogue and the purchase functions read, tools/training_services.py), the six EV spreads,
                                the cap the raise writes (price_rule.cap_by_badges_held), max_cap, the keepers (name,
                                ground, position) and the coach's own greeting
  data/training_grounds.json    each keeper's ground (its name and town)
  data/towns.json               the town's name
  data/markets.json             the badge names (badges)
The worked examples multiply those prices; nothing else is added. The page prints no rule of the owner's, no design note,
no dialogue other than the coach's greeting, and nothing from the secret files tests/test_player_site_leaks.py reads.

Not checked in a running game: data/training_services.json says (status) the services are built and NOT run in game
(experiment EXP-062); the page says so.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import player_site  # noqa: E402  the shared header, footer, filter and manifest of docs/player/
import player_guide_items as PI  # noqa: E402  dollars()

OUT = ROOT / "docs" / "player" / "training.html"
GUIDE = {"file": "training.html", "title": "Training coaches", "label": "Training", "order": 31,
         "description": "The eight coaches who raise a Pokemon to your level cap, train its effort or perfect its stats: "
                        "where they stand, what each service does and what it costs at every badge.",
         "generator": "tools/player_guide_training.py"}
TIERS = tuple(range(9))
STATS = {"hp": "HP", "attack": "Attack", "defence": "Defence", "special_attack": "Sp. Atk", "special_defence": "Sp. Def",
         "speed": "Speed"}
esc = player_site.esc
dollars = PI.dollars


def doc(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ inputs


def collect():
    ts = doc("data/training_services.json")
    sv = ts["services"]
    cap = {int(k): v for k, v in ts["price_rule"]["cap_by_badges_held"].items()}
    prices = {"raise": {int(k): v for k, v in sv["raise"]["price_by_tier"].items()},
              "ev": {int(k): v for k, v in sv["ev"]["price_by_tier"].items()},
              "iv": {int(k): v for k, v in sv["iv"]["price_per_stat_by_tier"].items()}}
    for name, row in list(prices.items()) + [("cap", cap)]:
        if set(row) != set(TIERS):
            raise SystemExit("data/training_services.json %s is not priced at every badge count 0-8: %s" % (name, sorted(row)))
    grounds = {g["id"]: g for g in doc("data/training_grounds.json")["grounds"]}
    towns = {t["id"]: t.get("name") or t.get("display_name") for t in doc("data/towns.json")["towns"]}
    badges = doc("data/markets.json").get("badges", {})
    coaches = []
    for k in ts["keepers"]:
        g = grounds.get(k["ground"])
        if g is None:
            raise SystemExit("keeper %s stands at %s, which data/training_grounds.json does not have" % (k["name"], k["ground"]))
        coaches.append({"name": k["name"], "gym": g["gym"], "ground": g["name"], "town": towns.get(g["town"], g["town"]),
                        "at": k["at"]})
    coaches.sort(key=lambda c: c["gym"])
    if [c["gym"] for c in coaches] != list(range(1, len(coaches) + 1)):
        raise SystemExit("the coaches are not one a gym: %s" % [c["gym"] for c in coaches])
    spreads = [{"name": s["name"], "evs": s["evs"]} for s in sv["ev"]["spreads"]]
    return {"cap": cap, "prices": prices, "coaches": coaches, "badges": badges, "spreads": spreads,
            "max_cap": sv["raise"]["max_cap"], "iv_value": sv["iv"]["value"], "greeting": ts["messages"]["greeting"],
            "status": ts["status"], "stat_count": len(STATS)}


def team_cost(m, tier, size=6):
    """(raise total, EV total, IV total, grand total) to train `size` Pokemon at badge count `tier`: a raise, an EV plan and
    all six IVs each. The IV service prices a stat, six stats per Pokemon."""
    p = m["prices"]
    r, e, i = size * p["raise"][tier], size * p["ev"][tier], size * m["stat_count"] * p["iv"][tier]
    return r, e, i, r + e + i


# ------------------------------------------------------------------------------------------------ render


def badge_label(m, t):
    return "no badge" if t == 0 else "%d badge%s" % (t, "" if t == 1 else "s")


def render_services(m):
    p = m["prices"]
    spreads = "".join(
        "<li><b>%s</b>: %s</li>" % (esc(s["name"]), esc(", ".join(
            "%d %s" % (v, STATS[k]) for k, v in sorted(s["evs"].items(), key=lambda kv: -kv[1]))))
        for s in m["spreads"])
    return (
        '<section %s><h2>What the coaches do</h2><p>Each coach sells three services. You pay in CobbleDollars, the coach '
        'asks which Pokemon (slot 1 to 6 of your party), and nothing is charged if the request cannot be done. Prices rise '
        'with your badges; see <a href="#prices">What it costs</a>.</p><ul>'
        '<li><b>Train a Pokemon to your cap.</b> One Pokemon is raised straight to your current level cap and no higher. It '
        'will not train one already at or above the cap, and it stops once your cap is above %d. Moves it would have learned '
        'on the way are worth checking afterwards.</li>'
        '<li><b>Effort training.</b> The Pokemon\'s effort values are cleared and one of these plans trained in:<ul>%s</ul>'
        'One price a Pokemon, whichever plan.</li>'
        '<li><b>Perfect a stat.</b> One stat of a Pokemon set to %d (the best a stat can be), or all six for six times the '
        'price. A stat already at %d costs the same again.</li></ul>'
        '<p>A Pokemon above your badges\' level is priced as the badge count its level needs, for effort training and for '
        'perfecting a stat. A raise is always priced by the badges you hold. The cap a raise writes at each badge count: %s.'
        '</p></section>'
        % (player_site.section_attr("services"), m["max_cap"], spreads, m["iv_value"], m["iv_value"],
           esc("; ".join("%s: %d" % (badge_label(m, t), m["cap"][t]) for t in TIERS))))


def render_prices(m):
    p = m["prices"]
    rows = "".join(
        '<tr><td>%s</td><td class="n">%d</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td>'
        '<td class="n">%s</td></tr>' % (
            esc(badge_label(m, t) + (" (%s)" % m["badges"]["gym%d_cleared" % t].replace("the ", "", 1)
                                     if t and "gym%d_cleared" % t in m["badges"] else "")),
            m["cap"][t], dollars(p["raise"][t]), dollars(p["ev"][t]), dollars(p["iv"][t]),
            dollars(m["stat_count"] * p["iv"][t])) for t in TIERS)
    return (
        '<section %s><h2>What it costs</h2><p>By the badges you hold. The raise is one Pokemon; effort training is one '
        'Pokemon; perfecting is one stat, and all six cost six times that.</p><div class="wide"><table><thead><tr>'
        '<th>Badges held</th><th class="n">Your cap</th><th class="n">Raise to cap</th><th class="n">Effort training</th>'
        '<th class="n">Perfect one stat</th><th class="n">Perfect all six</th></tr></thead><tbody>%s</tbody></table></div>'
        '</section>' % (player_site.section_attr("prices"), rows))


def render_examples(m):
    p = m["prices"]
    a_t, b_t = 1, 5
    one = (p["raise"][a_t], p["ev"][a_t], m["stat_count"] * p["iv"][a_t])
    r, e, i, tot = team_cost(m, b_t)
    return (
        '<section %s><h2>Worked examples</h2>'
        '<div class="box"><p><b>One Pokemon, with %s.</b> Raised to your cap of %d: %s. Its effort trained: %s. All six '
        'stats perfected: %s. All three together: %s.</p></div>'
        '<div class="box"><p><b>A full team of six, with %s.</b> Six raises to your cap of %d at %s each: %s. Six effort '
        'plans at %s each: %s. Thirty-six stats perfected at %s each: %s. All of it: %s.</p></div>'
        '<p class="small">These are the prices above multiplied out; the coaches charge them one purchase at a time.</p></section>'
        % (player_site.section_attr("examples"), esc(badge_label(m, a_t)), m["cap"][a_t], dollars(one[0]), dollars(one[1]),
           dollars(one[2]), dollars(sum(one)), esc(badge_label(m, b_t)), m["cap"][b_t], dollars(p["raise"][b_t]),
           dollars(r), dollars(p["ev"][b_t]), dollars(e), dollars(p["iv"][b_t]), dollars(i), dollars(tot)))


def render_coaches(m):
    rows = "".join(
        '<tr><td>%s</td><td>%s</td><td>%s</td><td><code>%d %d %d</code></td></tr>' % (
            esc(c["name"]), esc(c["ground"]), esc(c["town"]), *c["at"]) for c in m["coaches"])
    return (
        '<section %s><h2>The eight coaches</h2><p>One coach stands at the training ground of each gym town. Coordinates are '
        'block positions (x y z). The coach\'s greeting: "%s"</p><div class="wide"><table><thead><tr><th>Coach</th>'
        '<th>Training ground</th><th>Town</th><th>Stands at</th></tr></thead><tbody>%s</tbody></table></div></section>'
        % (player_site.section_attr("coaches"), esc(m["greeting"]), rows))


def sections():
    return [("coaches", "Coaches"), ("services", "Services"), ("prices", "Prices"), ("examples", "Examples")]


def render(m):
    body = ('<main><h1>Training coaches</h1><p class="lead">Eight coaches will raise a Pokemon to your level cap, train its '
            'effort or perfect its stats, for a price that rises with your badges.</p>%s%s%s%s%s'
            '<section id="not-covered"><h2>What this page leaves out</h2><ul>'
            '<li>How the services play in a running game. The data says they are built and have not been run in game yet; '
            'the prices are read from it. Where the game differs, the game is right: say so.</li>'
            '<li>What happens to a Pokemon\'s moves or evolution after a raise: not checked.</li>'
            '<li>Once your cap is past %d (after the Champion): a raise is refused, and the other two services stay at the '
            'eight-badge price.</li></ul></section></main>'
            % (player_site.filter_nav(sections(), label="Show one part"), render_coaches(m), render_services(m),
               render_prices(m), render_examples(m), m["max_cap"]))
    sources = '<p class="src">From data/training_services.json, data/training_grounds.json, data/towns.json and data/markets.json.</p>'
    return player_site.page(GUIDE, body, body_class="page-training", not_covered_href="#not-covered", sources_html=sources)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--check", action="store_true", help="regenerate in memory; exit 1 if the page differs or its "
                                                        "guides.json entry is not current")
    a = p.parse_args(argv)
    model = collect()
    text = render(model)
    out = Path(a.out)
    entry = GUIDE if out.resolve() == OUT.resolve() else None
    counts = "%d coaches, %d badge counts priced" % (len(model["coaches"]), len(TIERS))
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
