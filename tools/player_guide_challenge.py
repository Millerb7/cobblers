#!/usr/bin/env python
"""The players' Challenge (Full-Team) guide, docs/player/challenge.html: what the mode is, what it pays and gives, and how
it differs from Standard.

  python tools/player_guide_challenge.py            # write docs/player/challenge.html and register it in guides.json
  python tools/player_guide_challenge.py --check    # regenerate in memory; exit 1 if the page or its entry is stale
  python tools/player_guide_challenge.py --out F    # write elsewhere (not the site's page, not registered)

EVERY FIGURE IS READ FROM THE FILE THE GAME USES, never typed here:
  data/challenge_mode.json   series.title and series.description (the rctmod series the mode puts a player in: its own
                             wording), voucher.computed.schedule (the cash at the mode choice and at each badge's first
                             clear) and .total, voucher.rule (team of six, two answer TMs, the multiplier),
                             tm_gifts.by_step (the TMs given at each step) and tm_gifts.case (the TM Case)
  data/trainers.json         the thirteen bosses' Normal and Challenge teams (member counts, held items) and the leaders'
                             names, for "the next boss" of a gift
  docs/mechanics/TM_POWER_GATE.json   each gifted TM's move and type (through tools/tm_gate.py, as tms.html does)
  data/markets.json          the badge names

OAK'S OWN WORDS ARE NOT QUOTED. The choice is a conversation in data/dialogue.json, a secret file: tests/test_player_site_leaks.py
fails on any of its lines, so the page puts the mode in the words of the series description above and in counts it measures
itself. Both leaders' teams are on battles.html (linked), not repeated here.

Not checked in a running game: data/challenge_mode.json says the cash and the gifts are built as data and not seen given in game;
the page says so.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import player_site  # noqa: E402  the shared header, footer, filter and manifest of docs/player/
import player_guide_items as PI  # noqa: E402  dollars()
import tm_gate as TG  # noqa: E402  the TM score table: move and type of a TM item

OUT = ROOT / "docs" / "player" / "challenge.html"
GUIDE = {"file": "challenge.html", "title": "Challenge mode", "label": "Challenge", "order": 25,
         "description": "Full-Team rules against Standard: what the mode changes, the cash and the TMs it gives at the "
                        "start and with each badge, and the TM Case.",
         "generator": "tools/player_guide_challenge.py"}
BOSS_CLASSES = ("gym_leader", "elite_four", "champion")
esc = player_site.esc
dollars = PI.dollars


def doc(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def compact(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


# ------------------------------------------------------------------------------------------------ inputs


def collect():
    cm = doc("data/challenge_mode.json")
    recs = doc("data/trainers.json")["trainers"]
    scores = TG.load_scores(TG.load())["tms"]
    badges = doc("data/markets.json").get("badges", {})
    bosses = [r for r in recs if r["class"] in BOSS_CLASSES]
    if len(bosses) != len(cm["bosses"]):
        raise SystemExit("data/challenge_mode.json holds %d bosses, data/trainers.json %d" % (len(cm["bosses"]), len(bosses)))
    leaders = {r["order"]: r for r in recs if r["class"] == "gym_leader"}
    sched = {s["at"]: s for s in cm["voucher"]["computed"]["schedule"]}
    gifts = cm["tm_gifts"]["by_step"]
    steps = ["oak_mode_choice"] + ["gym%d_cleared" % n for n in range(1, 9)]
    if set(sched) != set(steps) or set(gifts) != set(steps):
        raise SystemExit("the cash schedule %s or the gift steps %s are not Oak and the eight badges" % (sorted(sched), sorted(gifts)))
    rows = []
    for n, at in enumerate(steps):
        g = gifts[at]
        if n == 8:
            nxt = "the League"
        else:
            lead = leaders[n + 1]
            key = next((k for k, v in cm["bosses"].items() if compact(v.get("lang")) == compact(lead["display_name"])), None)
            if key is None or not g["boss"].startswith(key):
                raise SystemExit("step %s: the gift's boss %r is not leader %d (%s)" % (at, g["boss"], n + 1, lead["display_name"]))
            nxt = lead["display_name"]
        tms = []
        for item in g["items"]:
            row = scores.get(item)
            if row is None:
                raise SystemExit("%s gifts %s, which the TM score table does not have" % (at, item))
            tms.append({"move": row["move"], "type": row["type"]})
        rows.append({"at": at, "badge": n, "name": None if n == 0 else badges.get("gym%d_cleared" % n, "badge %d" % n),
                     "cash": sched[at]["cash"], "tier": sched[at]["tier"], "next": nxt, "tms": tms})
    teams = {"normal": [], "challenge": []}
    for r in bosses:
        for mode in teams:
            teams[mode].append((len(r["modes"][mode]["team"]), sum(1 for m in r["modes"][mode]["team"] if m.get("heldItem"))))
    case = cm["tm_gifts"]["case"]
    return {"series": cm["series"], "rows": rows, "total": cm["voucher"]["computed"]["total"], "rule": cm["voucher"]["rule"],
            "teams": teams, "bosses": len(bosses), "case": case, "leaders": len(leaders),
            "gym_leader_sizes": {mode: sorted({len(r["modes"][mode]["team"]) for r in leaders.values()}) for mode in teams}}


# ------------------------------------------------------------------------------------------------ render


def span(nums):
    return str(nums[0]) if len(nums) == 1 else "%d to %d" % (min(nums), max(nums))


def render_what(m):
    s = m["series"]
    t = m["teams"]
    n_all, c_all = [x[0] for x in t["normal"]], [x[0] for x in t["challenge"]]
    n_held, c_held = sum(x[1] for x in t["normal"]), sum(x[1] for x in t["challenge"])
    return (
        '<section %s><h2>What Challenge mode is</h2><p>The game calls it <b>%s</b>: "%s" Standard is the ordinary rules, and '
        'Challenge is the one other choice you are offered at the start of your journey.</p><ul>'
        '<li>The level limits are the same in both modes. Only the battles change.</li>'
        '<li>The %d bosses (the %d Gym Leaders, the Elite Four and the Champion): Standard teams run from %d to %d Pokemon; '
        'Challenge teams are all %s. Across the %d, %d Pokemon carry a held item in Standard and %d in '
        'Challenge.</li>'
        '<li>The choice is yours alone and is written down once: it stays. It is offered at the start of your journey, and not '
        'to a player who already holds the first badge.</li>'
        '<li>Challenge also pays a sum of cash and gives a few TMs when you choose it and with each badge (below), and a '
        'TM Case to keep them in.</li></ul>'
        '<p>Every team in both modes, boss by boss, is on <a href="battles.html">Trainer battles</a>: its switch at the top '
        'flips the whole page between Standard (shown as Normal there) and Challenge.</p></section>'
        % (player_site.section_attr("mode"), esc(s["title"]), esc(s["description"]), m["bosses"], m["leaders"], min(n_all),
           max(n_all), esc(span(sorted(set(c_all)))), m["bosses"], n_held, c_held))


def render_cash(m):
    r = m["rule"]
    rows = "".join(
        '<tr><td>%s</td><td class="n">%s</td></tr>' % (
            esc("When you choose Challenge" if x["badge"] == 0 else "After %s (badge %d)" % (x["name"], x["badge"])),
            dollars(x["cash"])) for x in m["rows"])
    return (
        '<section %s><h2>The cash</h2><p>Each payment is made once, as you first earn it: the first when you choose '
        'Challenge, the rest the first time you win each badge. Together they come to %s.</p><div class="wide"><table>'
        '<thead><tr><th>When</th><th class="n">You receive</th></tr></thead><tbody>%s</tbody></table></div>'
        '<p class="small">Each payment is %s times what it costs to train a full team of six at that badge (a raise, an effort '
        'plan and all six stats each, from <a href="training.html">Training coaches</a>) plus %d answer TMs for the next '
        'boss, rounded up to %s. Worked out from the data; not yet watched being paid in a running game.</p></section>'
        % (player_site.section_attr("cash"), dollars(m["total"]), rows, esc(r["multiplier"]), r["answer_tms"],
           dollars(r["round_to"])))


def tm_cell(tms):
    return ", ".join("%s (%s)" % (esc(t["move"]), esc(t["type"])) for t in tms)


def render_tms(m):
    rows = "".join(
        '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            esc("When you choose Challenge" if x["badge"] == 0 else "After %s (badge %d)" % (x["name"], x["badge"])),
            esc(x["next"]), tm_cell(x["tms"])) for x in m["rows"])
    c = m["case"]
    return (
        '<section %s><h2>The TMs</h2><p>A Challenge player is given TMs that answer the next boss, once, at the same moments as '
        'the cash. They are on top of the cash and do not come out of it. To use one, see <a href="tms.html">TMs</a>; '
        'whether your Pokemon can learn a given move is for you to check.</p><div class="wide"><table><thead><tr>'
        '<th>When</th><th>Aimed at</th><th>TMs given</th></tr></thead><tbody>%s</tbody></table></div>'
        '<h3>The %s</h3><p>When you choose Challenge you are also given a %s: an ordinary backpack with a new name, '
        'with room for any item, TMs among them. It does not sort anything for you. If your inventory is full, what does not '
        'fit is dropped at your feet.</p></section>'
        % (player_site.section_attr("tms"), rows, esc(c["name"]), esc(c["name"])))


def render_standard(m):
    t = m["teams"]
    return (
        '<section %s><h2>Against Standard</h2><ul>'
        '<li>The same level limits, badges, gyms and routes.</li>'
        '<li>The bosses: Standard teams hold %s Pokemon, Challenge teams %s, with %d held items against %d. The Gym Leaders alone: '
        'Standard %s Pokemon, Challenge %s.</li>'
        '<li>Challenge pays the cash and gives the TMs and the TM Case above. Standard does not.</li>'
        '<li>Route trainers have a Challenge team as well as a Standard one; both are on <a href="battles.html">Trainer '
        'battles</a>.</li></ul></section>'
        % (player_site.section_attr("standard"), esc(span(sorted({x[0] for x in t["normal"]}))),
           esc(span(sorted({x[0] for x in t["challenge"]}))), sum(x[1] for x in t["challenge"]),
           sum(x[1] for x in t["normal"]), esc(span(m["gym_leader_sizes"]["normal"])),
           esc(span(m["gym_leader_sizes"]["challenge"]))))


def sections():
    return [("mode", "What it is"), ("cash", "The cash"), ("tms", "The TMs"), ("standard", "Against Standard")]


def render(m):
    body = ('<main><h1>Challenge mode</h1><p class="lead">Full-Team rules: what you are offered at the start of your '
            'journey, what it gives you, and how it differs from Standard.</p>%s%s%s%s%s'
            '<section id="not-covered"><h2>What this page leaves out</h2><ul>'
            '<li>The conversation in which the choice is offered, and anything anyone says.</li>'
            '<li>How it plays in a running game. The cash and the gifts are worked out from the campaign\'s data and have not '
            'been watched being given; where the game differs, the game is right: say so.</li>'
            '<li>Which of your Pokemon can learn the TMs given.</li></ul></section></main>'
            % (player_site.filter_nav(sections(), label="Show one part"), render_what(m), render_cash(m), render_tms(m),
               render_standard(m)))
    sources = '<p class="src">From data/challenge_mode.json, data/trainers.json, data/markets.json and the TM score table.</p>'
    return player_site.page(GUIDE, body, body_class="page-challenge", not_covered_href="#not-covered", sources_html=sources)


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
    counts = "%d payments totalling %d, %d TMs given" % (len(model["rows"]), model["total"],
                                                         sum(len(r["tms"]) for r in model["rows"]))
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
