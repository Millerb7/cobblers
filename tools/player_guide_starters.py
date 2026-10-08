#!/usr/bin/env python
"""The players' starter guide, docs/player/starters.html: the starters on the starter screen, their stats at each tier,
how each one evolves, and the items a line needs (Kubfu's scrolls, Silvally's memories) with where a player gets them.

  python tools/player_guide_starters.py            # write docs/player/starters.html and register it in guides.json
  python tools/player_guide_starters.py --check    # regenerate in memory; exit 1 if the page or its entry is stale
  python tools/player_guide_starters.py --out F    # write elsewhere (not the site's page, not registered)

WHAT A TIER IS. There is one starter category (modpack/config/cobblemon/starters.json, `cobblers_mythical`), so a tier
is not a category or a power ranking: it is the stage of a line, and every line shares the same three.
  tier 1  the stage-1 form the screen gives, at levels.start (5), all eight at the same base-stat total
  tier 2  the stage-2 form at levels.stage_2 (30), again one total for all eight
  tier 3  the native final species at levels.final (45), the Cobblemon 1.8.0 species unchanged, so its totals differ;
          for a line with no evolution (Smeargle), its own third form (stages[2]), named "<species> (final)"
Tiers 1 and 2 are OUR forms (data/mythical_starters.json `stages`, built by tools/mythical_starters.py); tier 3 is read
from the jar.

SOURCES, each read, never copied in:
  data/mythical_starters.json           lines, stages, their stats and evolutions; levels; starter_category
  modpack/config/cobblemon/starters.json what the screen offers; must be exactly the lines' stage-1 species at levels.start
  the Cobblemon 1.8.0 jar (read only)   display names, types, the finals' base stats, Silvally's memory forms; the
                                        ability pools (species files) and each ability's name and one-line
                                        description (assets/cobblemon/lang/en_us.json `cobblemon.ability.<id>[.desc]`)

ABILITIES. A tier 1 or 2 stage shows its own `abilities` when data/mythical_starters.json sets them (Smeargle's three
forms carry Protean; tools/mythical_starters.py writes them onto the form), else the jar species' pool, which a form
that sets none inherits. A final shows the jar's pool for the form it evolves into (Urshifu's style form, else the
species). `h:` marks a hidden ability, shown as hidden; a hidden ability that is also a normal one is shown once.
COBBLEVERSE's species_additions for these species (COBBLEVERSE-DP-v31: cosmog, cosmoem, kubfu, lunala, meltan,
naganadel, solgaleo, urshifu) set no `abilities` (read 2026-10-08), so nothing overrides the jar's pools; this page
does not re-read that zip, which is not in the repository. An ability the lang file cannot name stops the run.

THE TAGLINE. Every line's `tagline` in data/mythical_starters.json is shown under its name: what the line offers over
the whole game, in a sentence. A line without one stops the run. Taglines name no place or person.
  data/trainers.json                    generation_contract.gym_ace_levels: when 30 and 45 are first reachable
  data/markets.json                     counters and stalls: where an item is sold, or that it is priced and held
  data/traders.json                     the Mart clerks: an item named there is "sold by a Mart clerk"
  STORY_FILES below                     an item those name and no shop sells is "earned in the story", never more

WHY A STARTER'S EVOLUTION COMES FROM THE DATA AND NOT THE JAR. A starter carries a forced aspect that selects our form,
and a form's `evolutions` replace the species' own (tools/mythical_starters.py docstring). The jar's own entries would
tell a player the wrong thing: Cosmog at 43 and 53, Type: Null by friendship, Poipole by knowing Dragon Pulse, Meltan
never. The page reads the stage evolutions; an evolution requirement it cannot put in words stops the run.

WHAT THE PAGE NEVER SAYS. docs/player/ is public and tests/test_player_site_leaks.py holds it to that. An item whose
only source is a story file is "earned in the story" with at most the badge it waits for: no place, person, id or
coordinate. A held line (markets.json `held_stock`: priced, sold by no merchant) that no story file gives is "not on
sale yet", without the counter it is held for; one a story file gives is "earned in the story" (Silvally's memories). A counter is named only for a line it actually stocks.

PUBLISHED (2026-10-08). The leak test reads data/mythical_starters.json as a legendary file; the five starter species
are public by the owner's decision and let through by its ALLOW list (`_STARTER`), and nothing else from that file is.

THE FILTER. Each line is one section whose id is the shared filter's key (tools/player_site.py filter_nav): "Show one
starter" shows that line's stats, evolutions and the items it needs, and only those. Without JavaScript every line
shows.

Not checked in a running game: the forms, the evolutions, the scrolls and the memories are as the data and the jar
say (EXP-049 has not run).
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
import player_site  # noqa: E402  the shared header, footer, stylesheet and manifest of docs/player/
import player_guide_battles as PB  # noqa: E402  the jar finder and its display names (Dex)

OUT = ROOT / "docs" / "player" / "starters.html"
DATA = "data/mythical_starters.json"
CONFIG = "modpack/config/cobblemon/starters.json"
STATS = (("hp", "HP"), ("attack", "Atk"), ("defence", "Def"), ("special_attack", "SpA"), ("special_defence", "SpD"),
         ("speed", "Spe"))
# data/ files an item can be given through without a shop: the page says "earned in the story" and nothing more.
STORY_FILES = ("data/rewards.json", "data/quests.json", "data/research_station.json", "data/dialogue.json")
GUIDE = {"file": "starters.html", "title": "Starters", "label": "Starters", "order": 10,
         "description": "The eight starters on the starter screen: their stats at each tier, how each line evolves, "
                        "and how to get the items two of them need.",
         "generator": "tools/player_guide_starters.py"}
# a stage that keeps the stage-1 species is named by what it is (Smeargle's three forms are all Smeargle)
SAME_SPECIES = {2: " (grown)", 3: " (final)"}
TIME = {"day": "during the day", "night": "at night", "dawn": "at dawn", "dusk": "at dusk"}


def doc(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


esc = player_site.esc


# ------------------------------------------------------------------------------------------------ the jar


class Jar:
    """Base stats, types and forms of the species this page names, read from the jar (read only)."""

    def __init__(self, path):
        self.dex = PB.Dex(path)
        z = zipfile.ZipFile(path)
        self.raw = {}
        for n in z.namelist():
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                self.raw[n.rsplit("/", 1)[1][:-5]] = n
        self.zip = z
        self.cache = {}
        self.lang = json.loads(z.read("assets/cobblemon/lang/en_us.json").decode("utf-8"))

    def species(self, sid):
        if sid not in self.raw:
            raise SystemExit("the jar has no species %r" % sid)
        if sid not in self.cache:
            self.cache[sid] = json.loads(self.zip.read(self.raw[sid]).decode("utf-8"))
        return self.cache[sid]

    def name(self, sid):
        return self.dex.species(sid)[0]

    def form(self, sid, aspect):
        """(stats, [types]) of `sid`, or of its form carrying `aspect`; a form inherits what it does not set."""
        s = self.species(sid)
        f = next((f for f in s.get("forms") or [] if aspect in (f.get("aspects") or [])), {}) if aspect else {}
        if aspect and not f:
            raise SystemExit("the jar's %s has no form with the aspect %r" % (sid, aspect))
        stats = f.get("baseStats") or s["baseStats"]
        typed = f if f.get("primaryType") else s
        return stats, [t.lower() for t in (typed.get("primaryType"), typed.get("secondaryType")) if t]

    def pool(self, sid, aspect=None):
        """The species-file ability pool (`id`, `h:id` hidden) of `sid` or of its form carrying `aspect`; a form that
        sets no `abilities` has the species'."""
        s = self.species(sid)
        f = next((f for f in s.get("forms") or [] if aspect in (f.get("aspects") or [])), {}) if aspect else {}
        return list(f.get("abilities") or s.get("abilities") or [])

    def ability(self, aid):
        """(display name, one-line description) of an ability id, from the jar's en_us.json. Stops the run on an id
        the lang file does not name: the page never shows an ability it cannot describe."""
        name = self.lang.get("cobblemon.ability.%s" % aid)
        desc = self.lang.get("cobblemon.ability.%s.desc" % aid)
        if not name or not desc:
            raise SystemExit("the jar's en_us.json has no name or description for the ability %r" % aid)
        return name, desc


def shown(pool, jar, where):
    """A pool as the page shows it: [{"id", "name", "desc", "hidden"}], the normal abilities in order, then each
    hidden one that is not also a normal one (Smeargle's `protean`, `h:protean` is one Protean, not two)."""
    if not pool:
        raise SystemExit("%s has no abilities: neither our form nor the jar's species sets any" % where)
    normal = [a for a in pool if not a.startswith("h:")]
    hidden = [a[2:] for a in pool if a.startswith("h:") and a[2:] not in normal]
    out = []
    for aid, h in [(a, False) for a in normal] + [(a, True) for a in hidden]:
        name, desc = jar.ability(aid)
        out.append({"id": aid, "name": name, "desc": desc, "hidden": h})
    return out


# ------------------------------------------------------------------------------------------------ inputs


def parse_result(result):
    """'urshifu wushu_style=rapid_strike unaspect=cobblers_starter_2' -> ('urshifu', {'wushu_style': 'rapid_strike',
    'unaspect': ..., 'aspect': ...})."""
    parts = result.split()
    return parts[0], dict(p.split("=", 1) for p in parts[1:] if "=" in p)


def item_names():
    """{item id: display name} from the shelves' own `name` fields (markets.json)."""
    out = {}

    def walk(n):
        if isinstance(n, dict):
            if isinstance(n.get("item"), str) and isinstance(n.get("name"), str):
                out.setdefault(n["item"], n["name"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(doc("data/markets.json"))
    return out


def sources(item):
    """How a player gets `item`: [(kind, words)], kind 'shop', 'held', 'mart', 'story' or 'none'. Names a town and
    its seller only for a line that seller stocks."""
    m = doc("data/markets.json")
    towns = {t["id"]: t.get("display_name") or t["id"] for t in doc("data/towns.json")["towns"]}
    out = []
    for rec in (m.get("counters") or []) + (m.get("stalls") or []):
        for line in rec.get("stock") or []:
            if isinstance(line, dict) and line.get("item") == item:
                who = (rec.get("keeper") or {}).get("name") or "the market"
                out.append(("shop", "Sold in %s by %s for $%s." % (towns.get(rec.get("town"), rec.get("town")), who,
                                                                  format(line.get("price", 0), ","))))
        for line in rec.get("held_stock") or []:
            if isinstance(line, dict) and line.get("item") == item:
                out.append(("held", "Not on sale yet: the campaign prices it for a shop counter, but no merchant "
                                    "stocks it today."))
    if item in (ROOT / "data/traders.json").read_text(encoding="utf-8"):
        out.append(("mart", "Sold by a Mart clerk."))
    for kind in ("shop", "mart"):  # a seller first
        hits = list(dict.fromkeys(o for o in out if o[0] == kind))
        if hits:
            return hits
    # a story source before a held line: a line held at a counter is sold by nobody, so when a story file gives the
    # item that is where a player gets it (Silvally's memories: held in data/markets.json, given by the station,
    # the owner, 2026-10-08)
    if any(item in (ROOT / f).read_text(encoding="utf-8") for f in STORY_FILES):
        return [("story", "Earned in the story.")]
    hits = list(dict.fromkeys(o for o in out if o[0] == "held"))
    if hits:
        return hits
    return [("none", "No source in the campaign's data yet.")]


def story_gate(item):
    """The badge a story-only item waits for, from data/research_station.json's economy record of it, or None. Only the
    badge number is taken: the record's place and people stay off the page."""
    for rec in doc("data/research_station.json").get("economy", {}).get("items") or []:
        items = rec.get("item") if isinstance(rec.get("item"), list) else [rec.get("item")]
        if item in items:
            g = re.fullmatch(r"gym(\d)_cleared", str(rec.get("gate") or ""))
            return int(g.group(1)) if g else None
    return None


def reach(level, aces):
    """(badges held, gym heading to) when `level` is first under the cap: the cap is the next leader's ace."""
    for k, ace in enumerate(aces):
        if ace >= level:
            return k, k + 1
    return len(aces), None


def words(ev, jar, final_name):
    """An evolution in plain words. Stops the run on a requirement it does not know."""
    bits = []
    for r in ev.get("requirements") or []:
        v = r.get("variant")
        if v == "level":
            bits.append("reaches level %d" % r["minLevel"])
        elif v == "time_range":
            bits.append(TIME.get(r["range"], "in the time range %s" % r["range"]))
        elif v == "friendship":
            bits.append("has friendship of %d or more" % r["amount"])
        elif v == "has_move":
            bits.append("knows %s" % jar.dex.move(r["move"])[0])
        elif v == "held_item":
            bits.append("holds %s" % jar.dex.item(r.get("itemCondition") or r.get("item")))
        else:
            raise SystemExit("%s: evolution %s has a requirement this page cannot put in words: %r"
                             % (DATA, ev.get("id"), r))
    # a time of day reads after the rest: "reaches level 45 during the day"
    said = " and ".join(b for b in bits if b not in TIME.values()) + "".join(" " + b for b in bits if b in TIME.values())
    if ev["variant"] == "level_up":
        if not bits:
            raise SystemExit("%s: level-up evolution %s has no requirement" % (DATA, ev.get("id")))
        how = "When it %s, it can evolve into %s" % (said.strip(), final_name)
    elif ev["variant"] == "item_interact":
        how = "Once it %s, use a %s on it to evolve it into %s" % (
            said.strip() or "is in your party", jar.dex.item(ev["requiredContext"]), final_name)
    elif ev["variant"] == "trade":
        how = "Trade it to evolve it into %s" % final_name
    else:
        raise SystemExit("%s: evolution %s has a variant this page cannot put in words: %r"
                         % (DATA, ev.get("id"), ev["variant"]))
    for d in (ev.get("drops") or {}).get("entries") or []:
        how += "; the evolution also leaves you a %s" % jar.dex.item(d["item"])
    return how + "."


def collect(jar_path=None):
    jar = Jar(PB.find_jar(jar_path))
    d = doc(DATA)
    cfg = doc(CONFIG)
    levels = d["levels"]
    aces = doc("data/trainers.json")["generation_contract"]["gym_ace_levels"]
    cats = cfg.get("starters") or []
    if [c.get("name") for c in cats] != [d["starter_category"]["name"]]:
        raise SystemExit("%s offers %s, %s names %s" % (CONFIG, [c.get("name") for c in cats], DATA,
                                                         d["starter_category"]["name"]))
    offered = []
    for e in cats[0]["pokemon"]:
        sp, props = parse_result(e)
        offered.append((sp, int(props.get("level", 0)), props.get("aspect")))
    want = [(ln["stages"][0]["species"], levels["start"], d["aspects"]["stage_1"]) for ln in d["lines"]]
    if sorted(offered) != sorted(want):
        raise SystemExit("%s offers %s; %s's lines start as %s" % (CONFIG, offered, DATA, want))
    names = item_names()
    lines, items = [], {}
    for ln in d["lines"]:
        tiers, steps = [], []
        for st in ln["stages"]:
            stats = st["baseStats"]
            if sum(stats.values()) != st["bst"]:
                raise SystemExit("%s %s stage %d: stats sum to %d, bst says %d" % (DATA, ln["id"], st["stage"],
                                                                                   sum(stats.values()), st["bst"]))
            _s, types = jar.form(st["species"], None)
            label = jar.name(st["species"]) + (SAME_SPECIES.get(st["stage"], "") if st["species"] ==
                                               ln["stages"][0]["species"] else "")
            # our form's own pool when the stage sets one (Smeargle's Protean), else the species' (the form inherits)
            pool = st.get("abilities") or jar.pool(st["species"])
            tiers.append({"tier": st["stage"], "name": label, "types": types, "stats": stats, "species": st["species"],
                          "level": {1: levels["start"], 2: levels["stage_2"]}.get(st["stage"], levels["final"]),
                          "abilities": shown(pool, jar, "%s %s stage %d" % (DATA, ln["id"], st["stage"]))})
            for ev in st["evolutions"]:
                sp, props = parse_result(ev["result"])
                final = "aspect" not in props
                if final:
                    style = props.get("wushu_style")
                    aspect = "%s-style" % style if style and style != "single_strike" else None
                    fname = jar.name(sp) + (" (%s Style)" % style.replace("_", " ").title() if style else "")
                    fstats, ftypes = jar.form(sp, aspect)
                    tiers.append({"tier": 3, "name": fname, "types": ftypes, "stats": fstats,
                                  "level": levels["final"], "species": sp,
                                  "abilities": shown(jar.pool(sp, aspect), jar, "the jar's %s" % fname)})
                    steps.append(words(ev, jar, fname))
                else:
                    to = 3 if props.get("aspect") == d["aspects"].get("stage_3") else 2
                    nxt = jar.name(sp) + (SAME_SPECIES[to] if sp == st["species"] else "")
                    steps.append(words(ev, jar, nxt))
                if ev.get("requiredContext"):
                    items.setdefault(ln["id"], []).append(ev["requiredContext"])
        # the anchor is the line's position: its data id names the species, which is not the page's to expose as an id
        notes = []
        if "sketch_cap" in ln:
            notes.append("Sketch copies the last move its target used, for good, and the copy stays among its moves. "
                         "Each %s can do it %d times; after that, Sketch fails."
                         % (jar.name(ln["stages"][0]["species"]), ln["sketch_cap"]["uses"]))
        if not str(ln.get("tagline") or "").strip():
            raise SystemExit("%s %s has no `tagline`: the page shows one under every line's name" % (DATA, ln["id"]))
        # a species of the line whose model has not reached players yet (data `models_pending`): it renders as the
        # placeholder doll in game, and the page's "What this page leaves out" says so
        pending = [jar.name(s) for s in (ln.get("models_pending") or {}).get("species") or []]
        lines.append({"id": ln["id"], "anchor": "line-%d" % (len(lines) + 1), "name": jar.name(ln["stages"][0]["species"]),
                      "tagline": ln["tagline"].strip(), "tiers": tiers, "steps": steps,
                      "gyms": ln.get("potent_at", {}).get("gyms") or [], "notes": notes,
                      "own_final": len(ln["stages"]) == 3, "models_pending": pending})
    specials = []
    for ln in lines:  # an item a starter evolves on
        for it in items.get(ln["id"], []):
            src = sources(it)
            gate = story_gate(it) if src[0][0] == "story" else None
            specials.append({"line": ln["name"], "for": "evolution", "item": it, "name": jar.dex.item(it),
                             "sources": src, "gate": gate})
    for ln in lines:  # a final whose form follows a held memory
        for t in ln["tiers"]:
            if t["tier"] != 3:
                continue
            forms = [f for f in jar.species(t["species"]).get("forms") or []
                     if any(a.endswith("-memory") for a in f.get("aspects") or [])]
            for f in forms:
                kind = next(a for a in f["aspects"] if a.endswith("-memory"))[:-len("-memory")]
                it = next((i for i in names if i.split(":")[-1] == "%s_memory" % kind), None)
                src = sources(it) if it else [("none", "No source in the campaign's data yet.")]
                specials.append({"line": ln["name"], "for": "form", "final": t["name"], "type": f.get("primaryType",
                                 kind).lower(), "item": it, "name": names.get(it) or "%s Memory" % kind.title(),
                                 "sources": src, "gate": story_gate(it) if it and src[0][0] == "story" else None})
    return {"lines": lines, "specials": specials, "levels": levels, "aces": aces, "missing": sorted(jar.dex.missing),
            "category": d["starter_category"]["displayName"]}


# ------------------------------------------------------------------------------------------------ render


def badges(types, dex=None):
    return "".join('<span class="t t-%s">%s</span>' % (esc(t), esc(t.title())) for t in types)


def render_line(ln, model):
    head = "".join("<th>%s</th>" % h for _k, h in STATS)
    rows = []
    for t in ln["tiers"]:
        cells = "".join('<td class="n">%d</td>' % t["stats"][k] for k, _h in STATS)
        rows.append('<tr><td>%d</td><td>%s</td><td>%s</td><td class="n">%d</td>%s<td class="n"><b>%d</b></td></tr>'
                    % (t["tier"], esc(t["name"]), badges(t["types"]), t["level"], cells, sum(t["stats"].values())))
    best = ", ".join(str(g) for g in ln["gyms"])
    # one row per ability a tier has; the tier and form are named on its first row only
    arows = []
    for t in ln["tiers"]:
        for i, a in enumerate(t["abilities"]):
            arows.append('<tr><td>%s</td><td>%s</td><td>%s%s</td><td>%s</td></tr>'
                         % ("%d" % t["tier"] if i == 0 else "", esc(t["name"]) if i == 0 else "", esc(a["name"]),
                            ' <span class="tag">hidden</span>' if a["hidden"] else "", esc(a["desc"])))
    # the section's id is the anchor the contents list links to, and the shared filter's key (player_site.filter_nav):
    # a line's items sit inside its own section, so "show this starter" shows everything about it
    return ('<section class="line" %s><h2>%s</h2><p class="tagline">%s</p>%s<table class="stats"><thead><tr>'
            '<th>Tier</th><th>Form</th><th>Type</th><th>Lv</th>%s<th>Total</th></tr></thead><tbody>%s</tbody></table>'
            '<h3>Abilities</h3><table class="stats abilities"><thead><tr><th>Tier</th><th>Form</th><th>Ability</th>'
            '<th>What it does</th></tr></thead><tbody>%s</tbody></table>'
            '<h3>How it evolves</h3><ol class="steps">%s</ol>%s%s</section>'
            % (player_site.section_attr(ln["anchor"]), esc(ln["name"]), esc(ln["tagline"]),
               '<p class="lead">At its strongest around gym%s %s.</p>' % ("s" if len(ln["gyms"]) > 1 else "", best)
               if best else "", head, "".join(rows), "".join(arows),
               "".join("<li>%s</li>" % esc(s) for s in ln["steps"]),
               "".join("<p>%s</p>" % esc(n) for n in ln.get("notes") or []),
               render_specials(model, ln["name"])))


def gated(src, gate):
    """'Earned in the story.' -> 'Earned in the story, once you hold 5 badges.' when the item waits for a badge."""
    return src[:-1] + ", once you hold %d badges." % gate if gate else src


def render_specials(model, line_name):
    """The items one line needs (its evolution items, its final's memories), or ""."""
    out = []
    specials = [s for s in model["specials"] if s["line"] == line_name]
    ev = [s for s in specials if s["for"] == "evolution"]
    for line in sorted({s["line"] for s in ev}):
        its = [s for s in ev if s["line"] == line]
        lis = []
        for s in its:
            src = gated(" ".join(w for _k, w in s["sources"]), s["gate"])
            lis.append("<li><b>%s</b>: %s</li>" % (esc(s["name"]), esc(src)))
        out.append('<h3>%s: the evolution items</h3><p>Which item you use decides what it becomes.</p><ul>%s</ul>'
                   % (esc(line), "".join(lis)))
    fm = [s for s in specials if s["for"] == "form"]
    for final in sorted({s["final"] for s in fm}):
        its = [s for s in fm if s["final"] == final]
        srcs = sorted({gated(" ".join(w for _k, w in s["sources"]), s["gate"]) for s in its})
        rows = "".join("<tr><td>%s</td><td>%s</td></tr>" % (esc(s["name"]), badges([s["type"]])) for s in its)
        out.append('<h3>%s: the memories</h3><p>%s takes the type of the memory it holds: give it one to hold and it '
                   'becomes that type. There are %d, one for every type but Normal; holding none, it stays Normal.</p>'
                   '<p>How to get them: %s</p><table class="stats"><thead><tr><th>Memory</th><th>Type</th></tr></thead>'
                   '<tbody>%s</tbody></table>' % (esc(final), esc(final), len(its), esc(" ".join(srcs)), rows))
    return "".join(out)


def render(model):
    lv, aces = model["levels"], model["aces"]
    held2, gym2 = reach(lv["stage_2"], aces)
    held3, gym3 = reach(lv["final"], aces)
    toc = "".join('<li><a href="#%s">%s</a></li>' % (esc(ln["anchor"]), esc(ln["name"]))
                  for ln in model["lines"])
    needs = sorted({s["line"] for s in model["specials"]})
    nav = player_site.filter_nav([(ln["anchor"], ln["name"]) for ln in model["lines"]], label="Show one starter")
    body = ('<main><h1>Starters</h1><p class="lead">The starter screen offers one category, %s, with %d Pokemon, '
            'each at level %d. This page shows what each becomes and when. %s</p>'
            '<nav class="toc"><ol>%s<li><a href="#not-covered">What this page leaves out</a></li></ol></nav>'
            '<div class="box"><p><b>Tiers.</b> Every line has the same three tiers:</p><ul>'
            '<li><b>Tier 1</b>, the form the starter screen gives you at level %d.</li>'
            '<li><b>Tier 2</b>, a stronger form at level %d. You can first reach it on the way to gym %d, holding %d '
            'badges.</li>'
            '<li><b>Tier 3</b>, the final Pokemon at level %d. You can first reach it on the way to gym %d, holding '
            '%d badges.</li></ul><p>Tiers 1 and 2 are the same total for all eight, so the lines differ in how '
            'their stats are spread, not in how many. Tier 3 is the standard final Pokemon%s. Your level cap is '
            'the next leader\'s ace (<a href="battles.html">Trainer battles</a>), which is why a tier waits for a '
            'badge. When your starter qualifies, the game offers the evolution; you can wait.</p>'
            '<p><b>Abilities.</b> Each line lists every tier\'s abilities and what they do, in the game\'s own words. '
            'One marked hidden is that form\'s hidden ability, not its usual one; where the hidden ability is the '
            'same as the usual one, it is listed once.</p></div>%s%s'
            '<section id="not-covered"><h2>What this page leaves out</h2><ul><li>Movesets: check the summary screen '
            'in game.</li><li>Where anything is found in the world: an item that is not sold is "earned in the '
            'story", with no more said.</li><li>Any Pokemon not given by the starter screen: the tiers and '
            'evolutions here are the starters\' own.</li>%s</ul></section></main>'
            % (esc(model["category"]), len(model["lines"]), lv["start"],
               esc("%s need items to evolve or change form: each one's are under its own heading."
                   % " and ".join(needs)) if needs else "", toc,
               lv["start"], lv["stage_2"], gym2, held2, lv["final"], gym3, held3,
               esc(", except for %s, which has no evolution: its tier 3 is a third form of its own"
                   % " and ".join(ln["name"] for ln in model["lines"] if ln.get("own_final")))
               if any(ln.get("own_final") for ln in model["lines"]) else "", nav,
               "".join(render_line(ln, model) for ln in model["lines"]),
               "".join('<li>%s, in the %s line, has no model in the client pack yet, so in game it shows as a '
                       'placeholder doll until its model ships. Its stats and evolution are as this page '
                       'says.</li>' % (esc(name), esc(ln["name"]))
                       for ln in model["lines"] for name in ln.get("models_pending") or [])))
    sources = ('<p class="src">From data/mythical_starters.json, modpack/config/cobblemon/starters.json, '
               'data/markets.json and the Cobblemon 1.8.0 species files.</p>')
    return player_site.page(GUIDE, body, body_class="page-starters", not_covered_href="#not-covered",
                            sources_html=sources)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--jar", help="the Cobblemon 1.8 jar (default: the offline snapshot's mods folder)")
    p.add_argument("--check", action="store_true", help="regenerate in memory; exit 1 if the page differs (but for "
                                                        "its generated-on line) or its guides.json entry is not current")
    a = p.parse_args(argv)
    model = collect(a.jar)
    text = render(model)
    out = Path(a.out)
    entry = GUIDE if out.resolve() == OUT.resolve() else None  # a page written elsewhere is not the site's
    if a.check:
        ok, why = player_site.check(out, text, entry)
        if not ok:
            print("%s is %s: run python tools/player_guide_starters.py" % (out, why))
            return 1
        print("%s is current (%d lines, %d items)" % (out, len(model["lines"]), len(model["specials"])))
        return 0
    did = player_site.write(out, text, entry)
    print("%s %s: %d lines, %d items, %d bytes" % (did, out, len(model["lines"]), len(model["specials"]),
                                                    len(text.encode("utf-8"))))
    for s in model["specials"]:
        print("  %-22s %-6s %s" % (s["name"], s["sources"][0][0], s["item"]))
    if model["missing"]:
        print("  not named by the jar: %s" % ", ".join(model["missing"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
