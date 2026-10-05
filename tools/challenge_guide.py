#!/usr/bin/env python
"""Challenge Mode trainer guide: one self-contained HTML page of every gym leader, the League and every route trainer.

The owner, 2026-10-05: "make an html for that for the challenge mode so i can show my friend trainers and the gyms" --
a companion to tools/nuzlocke_map.py's page (build/maps/nuzlocke.html). It reuses that page's tokens and fonts
(nuzlocke_map.STYLE, everything before its first rule) so the two read as one guide, and its helpers for gym
positions, town names and level caps.

Every fact on the page is read, never invented:
  teams           data/trainers.json, each record's modes.challenge and modes.normal (species, level, ability, held
                  item, nature, moves; there are no EVs or IVs in the data, so none are shown), with the mode's
                  strategy (bosses) or mode_intent (route trainers) and, for leaders, the challenge open_line
  which is live   the team tools/route_trainers.py actually writes: data/rctmod/trainers/<id>.json comes from the
                  record's top-level `rct` (route seats and the thirteen overrides alike). This tool compares that
                  `rct.team` with both modes for every record and states the result; it does not assume it
  gyms            nuzlocke_map.gyms() (data/gym_buildings/gym<N>.json leader.spawner; gym 2 from data/placements.json
                  + data/gym_interiors.json), the type from data/gym_trainers.json theme, the format from its
                  battle_format (what the override writes)
  level caps      nuzlocke_map.level_caps(): rctmod's rule with modpack/config/rctmod-server.toml's values
  the League      nuzlocke_map.towns() "league"; the Elite Four's and Champion's spawners come with the
                  cobbleverse:kanto_league template and have no authored coordinate (data/league_trainers.json)
  route trainers  route_trainers.load(), the emitter's own union of seats: data/route_trainers.json (Routes 1-3),
                  data/late_route_trainers.json (4-8), data/mansion_guardians.json, data/vr_trainers.json and
                  data/hq_trainers.json; eye_contact, sight_distance, unavoidable and why are the seat files' own
  names, types    the Cobblemon 1.8 jar's Pokemon Showdown data (moves.js, abilities.js, items.js, pokedex.js), the
                  same source tools/battle_sim.py reads. Without the jar (--jar, or the EXP-000 runtime copy in this
                  checkout or a sibling worktree) ids are shown title-cased and untyped, and the page says so

WHAT THIS DOES NOT COVER. In-game behaviour: valid output is not proof any trainer battles as listed. Trainers that
are not ours (Cobbleverse's own, anything a donor template places) are not listed. The Heaven's Arena exam teams
(data/arena_trainers.json, unseated since 2026-10-03) are not route trainers and are left out.

  python tools/challenge_guide.py         # -> build/maps/challenge.html
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DEFAULT_OUT = ROOT / "build" / "maps" / "challenge.html"
EXP_JAR = "experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods"
SHOWDOWN = "assets/cobblemon/showdown/node_modules/pokemon-showdown/data/"
ENTRY = re.compile(r"^  (\w+): \{\n(.*?)^  \},?$", re.S | re.M)
TYPES = ("normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground", "flying", "psychic",
         "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy")
FORMATS = {"GEN_9_SINGLES": "Singles", "GEN_9_DOUBLES": "Doubles"}
EMITTER = "tools/route_trainers.py"


def load_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def esc(s):
    return html.escape(str(s), quote=True)


def key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").split(":")[-1].lower())


def pretty(slug):
    return " ".join(w.capitalize() for w in re.split(r"[_\s-]+", (slug or "").split(":")[-1]) if w)


# ------------------------------------------------------------------ names and types (the jar's Showdown data)


def find_jar(explicit=None):
    if explicit:
        return Path(explicit)
    places = [ROOT / EXP_JAR]
    for p in ROOT.parents:
        if p.name == "worktrees":
            places.append(p.parent.parent / EXP_JAR)       # the main checkout, then any sibling worktree
            places += sorted(p.glob("*/" + EXP_JAR))
            break
    for d in places:
        hits = sorted(d.glob("Cobblemon-fabric-1.8*.jar")) if d.is_dir() else []
        if hits:
            return hits[0]
    return None


def field(body, name):
    m = re.search(r'^    %s: "([^"]*)"' % name, body, re.M)
    return m.group(1) if m else None


def showdown(jar):
    """{moves: {id: (name, type, category)}, abilities/items: {id: name}, species: {id: (name, [types])}}."""
    z = zipfile.ZipFile(jar)
    read = lambda f: z.read(SHOWDOWN + f).decode("utf8", "replace")
    out = {"moves": {}, "abilities": {}, "items": {}, "species": {}, "source": str(jar)}
    for m in ENTRY.finditer(read("moves.js")):
        name, typ, cat = field(m.group(2), "name"), field(m.group(2), "type"), field(m.group(2), "category")
        if name and typ:
            out["moves"][m.group(1)] = (name, typ.lower(), cat)
    for f, k in (("abilities.js", "abilities"), ("items.js", "items")):
        for m in ENTRY.finditer(read(f)):
            name = field(m.group(2), "name")
            if name:
                out[k][m.group(1)] = name
    for m in ENTRY.finditer(read("pokedex.js")):
        name = field(m.group(2), "name")
        types = re.search(r"^    types: \[([^\]]*)\]", m.group(2), re.M)
        if name and types:
            out["species"][m.group(1)] = (name, [t.strip(' "').lower() for t in types.group(1).split(",")])
    if len(out["moves"]) < 500 or len(out["species"]) < 500:
        raise SystemExit("parsed only %d moves and %d species from %s" % (len(out["moves"]), len(out["species"]), jar))
    return out


class Names:
    def __init__(self, sd=None):
        self.sd = sd
        self.missing = set()

    def _get(self, table, ident):
        if not self.sd:
            return None
        hit = self.sd[table].get(key(ident))
        if hit is None:
            self.missing.add("%s:%s" % (table, ident))
        return hit

    def species(self, ident):
        hit = self._get("species", ident)
        return (hit[0], hit[1]) if hit else (pretty(ident), [])

    def move(self, ident):
        hit = self._get("moves", ident)
        return (hit[0], hit[1]) if hit else (pretty(ident), None)

    def ability(self, ident):
        return self._get("abilities", ident) or pretty(ident)

    def item(self, ident):
        return self._get("items", ident) or pretty(ident)


# ------------------------------------------------------------------ data


def live_mode(rec):
    """Which mode's team the emitted rctmod file carries: the record's top-level rct.team against each mode's team.
    'both' when the two modes are identical (a placeholder), None when it matches neither."""
    team = (rec.get("rct") or {}).get("team")
    modes = rec.get("modes") or {}
    hits = [m for m in ("normal", "challenge") if m in modes and modes[m].get("team") == team]
    return "both" if len(hits) == 2 else (hits[0] if hits else None)


def emitter_lines():
    """file:line of every place the emitter writes a data/rctmod/trainers file, read at build time so it cannot rot."""
    text = (ROOT / EMITTER).read_text(encoding="utf-8").splitlines()
    return ["%s:%d" % (EMITTER, i) for i, ln in enumerate(text, 1) if 'out["data/rctmod/trainers/' in ln]


def collect():
    import nuzlocke_map as NM
    import route_trainers as RT

    doc = load_json("data/trainers.json")
    recs = doc["trainers"]
    by_id = {r["id"]: r for r in recs}
    town = {t["id"]: t for t in NM.towns()}
    caps = NM.level_caps()
    gpos = NM.gyms()
    gmeta = {e["id"]: e for e in load_json("data/gym_trainers.json")["trainers"]}
    lmeta = {e["id"]: e for e in load_json("data/league_trainers.json")["trainers"]}

    gyms = []
    for r in sorted((r for r in recs if r["class"] == "gym_leader"), key=lambda r: r["order"]):
        n, g, meta = r["order"], gpos[r["order"]], gmeta.get(r["id"], {})
        gyms.append({"rec": r, "n": n, "town": town.get(g["town"], {}).get("name", g["town"]), "x": g["x"],
                     "z": g["z"], "type": meta.get("theme"), "theme": r.get("theme"),
                     "format": meta.get("battle_format") or r["rct"].get("battleFormat") or r.get("format"),
                     "cap": caps[n][0], "upstream": meta.get("upstream_trainer_id")})
    league_at = town.get("league", {})
    league = []
    for r in sorted((r for r in recs if r["class"] in ("elite_four", "champion")),
                    key=lambda r: (r["class"] == "champion", r.get("order", 0))):
        meta = lmeta.get(r["id"], {})
        league.append({"rec": r, "type": meta.get("theme") or r.get("theme"),
                       "format": meta.get("battle_format") or r["rct"].get("battleFormat") or r.get("format"),
                       "upstream": meta.get("upstream_trainer_id")})

    _recs, seats, _fields = RT.load()
    seat_of = {s["id"]: s for s in seats}
    routes = sorted(load_json("data/routes.json")["routes"], key=lambda r: int(r["order"]))
    groups = []
    for k, rt in enumerate(routes, 1):
        members = sorted((r for r in recs if r.get("route_id") == rt["id"]),
                         key=lambda r: (r["class"] != "route", r.get("trainer_order", 0)))
        groups.append({"key": rt["id"], "title": rt["display_name"],
                       "from": town.get(rt["from_town"], {}).get("name", rt["from_town"]),
                       "to": town.get(rt["to_town"], {}).get("name", rt["to_town"]),
                       "cap": caps.get(k, (None, None)), "note": None,
                       "trainers": [(r, seat_of.get(r["id"])) for r in members]})
    # the two record-and-seat files, which carry one team and no modes
    mg = load_json("data/mansion_guardians.json")
    hq = load_json("data/hq_trainers.json")
    side = {
        "route_01_pallet_to_brock": {"key": "mansion", "title": "The Gastly mansion (off Route 1)",
                                     "note": "Five possessed Channelers, one per room (data/mansion_guardians.json).",
                                     "trainers": [(e, seat_of.get(e["id"], e)) for e in mg["trainers"]]},
        "route_08_blaine_to_giovanni": {"key": "hq", "title": "The Compact HQ tower (after the eighth badge)",
                                        "note": hq["band"]["why"].split(";")[0] + ".",
                                        "trainers": [(e, seat_of.get(e["id"], e)) for e in hq["trainers"]]},
    }
    ordered = []
    for g in groups:
        ordered.append(g)
        if g["key"] in side:
            s = side[g["key"]]
            ordered.append({**s, "from": None, "to": None, "cap": g["cap"], "extra": True})

    tally = {"normal": 0, "challenge": 0, "both": 0, None: 0}
    for r in recs:
        tally[live_mode(r)] += 1
    return {"gyms": gyms, "league": league, "league_at": league_at, "routes": ordered, "tally": tally,
            "records": len(recs), "contract": doc.get("generation_contract", {}).get("runtime_mode_selection"),
            "emitter": emitter_lines(), "init_cap": NM.rct_setting("initialLevelCap"),
            "rel_cap": NM.rct_setting("relativeLevelCap"), "nm_style": NM.STYLE}


# ------------------------------------------------------------------ page

TYPE_LIGHT = dict(zip(TYPES, ("#e4e1d3", "#f8cfb0", "#c6dcf5", "#f6e59a", "#cde8b8", "#cdeeed", "#efc0b8", "#e0c4e6",
                              "#ecd9ad", "#d6d9f5", "#f6c4d6", "#dfe7a6", "#e0d6b0", "#d2c8e4", "#c9c2f2", "#d4ccc6",
                              "#d8dde3", "#f6cfe9")))
TYPE_DARK = dict(zip(TYPES, ("#4a4636", "#6e3218", "#1f4170", "#5e5010", "#2f5a1f", "#1f5a5a", "#6a2420", "#522a5e",
                             "#5e4a1e", "#363f78", "#6c2442", "#4a5414", "#574c26", "#3e3260", "#362a7a", "#3d332d",
                             "#3e4650", "#6a2a58")))
OWN_LIGHT = "--warn-bg:#fff3cd; --warn-rule:#d9a400; --live:#0e766c; --plan:#8a3b9a;"
OWN_DARK = "--warn-bg:#3a3010; --warn-rule:#c99a1c; --live:#52c7b8; --plan:#d39be0;"


def tokens(palette, own):
    return " ".join("--t-%s:%s;" % (t, c) for t, c in palette.items()) + " " + own


def style(nm_style):
    base = nm_style.split("*{box-sizing")[0]          # the map page's @import and its three token blocks
    light, dark = tokens(TYPE_LIGHT, OWN_LIGHT), tokens(TYPE_DARK, OWN_DARK)
    css = """:root{ @@LIGHT@@ }
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){ @@DARK@@ color-scheme:dark; }}
:root[data-theme="dark"]{ @@DARK@@ color-scheme:dark; }
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);font-size:16px;line-height:1.45}
.cg{max-width:1180px;margin:0 auto;padding:20px 16px 48px}
.cg h1{font-family:var(--display);font-weight:700;font-size:clamp(1.7rem,4.5vw,2.6rem);margin:0 0 4px}
.cg h2{font-family:var(--display);font-weight:700;font-size:1.4rem;margin:28px 0 10px;border-bottom:2px solid var(--path);padding-bottom:4px}
.cg h3{font-family:var(--display);font-weight:700;font-size:1.15rem;margin:0}
.sub{color:var(--ink-soft);margin:0 0 14px}
.status{background:var(--warn-bg);border:1px solid var(--warn-rule);border-left:6px solid var(--warn-rule);border-radius:10px;padding:12px 16px;margin:0 0 14px}
.status p{margin:4px 0}.status .big{font-weight:700;font-size:1.08rem}
.status code,.src code{font-size:.82rem;overflow-wrap:anywhere}
.mapline{color:var(--ink-soft);font-style:italic;margin:0 0 14px}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 6px}
.bar button{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--rule);border-radius:999px;padding:4px 14px;cursor:pointer}
.bar button[aria-pressed="true"]{background:var(--marker);color:var(--marker-ink);border-color:var(--marker)}
.tbl{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--rule);border-radius:10px;background:var(--card)}
.tbl table{border-collapse:collapse;width:100%;min-width:560px;font-size:.93rem}
.tbl th,.tbl td{padding:6px 10px;text-align:left;border-top:1px solid var(--rule);vertical-align:top}
.tbl th{border-top:0;color:var(--ink-soft);font-size:.8rem;text-transform:uppercase;letter-spacing:.04em}
.cards{display:grid;gap:16px;grid-template-columns:minmax(0,1fr)}
.card{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:14px 16px;min-width:0}
.card header{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:baseline;justify-content:space-between;margin-bottom:6px}
.badge{display:inline-grid;place-items:center;min-width:1.9em;height:1.9em;border-radius:999px;background:var(--gold);color:var(--gold-ink);font-weight:700;margin-right:6px}
.cap{font-family:var(--display);font-weight:700;background:var(--gold);color:var(--gold-ink);border-radius:999px;padding:1px 10px;white-space:nowrap}
.meta{color:var(--ink-soft);font-size:.92rem;margin:0 0 6px;overflow-wrap:anywhere}
.tag{display:inline-block;font-size:.78rem;background:var(--tag-bg);border-radius:4px;padding:0 6px;margin:1px 2px 1px 0;white-space:nowrap}
.tag.sight{color:var(--path);font-weight:700}.tag.live{color:var(--live);font-weight:700}.tag.plan{color:var(--plan);font-weight:700}
.ty{display:inline-block;font-size:.74rem;font-weight:700;border-radius:4px;padding:0 6px;margin:1px 2px 1px 0;text-transform:uppercase;letter-spacing:.03em;background:var(--tag-bg);color:var(--ink)}
.team{list-style:none;margin:6px 0 0;padding:0;display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}
.mon{border:1px solid var(--rule);border-radius:8px;padding:6px 8px;min-width:0}
.mon .nm{font-weight:700}.mon .lv{color:var(--ink-soft);font-size:.9rem;margin-left:4px}
.mon .det{font-size:.86rem;color:var(--ink-soft);margin:2px 0;overflow-wrap:anywhere}
.mv{display:flex;flex-wrap:wrap;gap:3px;margin-top:3px}
.mv span{font-size:.82rem;border-radius:4px;padding:1px 6px;background:var(--tag-bg);color:var(--ink)}
.plan-note{font-size:.92rem;margin:6px 0 0}
.compact{font-size:.88rem;color:var(--ink-soft);margin:8px 0 0;overflow-wrap:anywhere}
.compact b{color:var(--ink)}
.rt{margin:0;padding:0;list-style:none;display:grid;gap:12px;grid-template-columns:minmax(0,1fr)}
@media (min-width:900px){.cards.two{grid-template-columns:repeat(2,minmax(0,1fr))}}
.cg[data-mode="normal"] .m-ch,.cg[data-mode="normal"] .c-no{display:none}
.cg:not([data-mode="normal"]) .m-no,.cg:not([data-mode="normal"]) .c-ch{display:none}
.src{margin-top:28px;color:var(--ink-soft);font-size:.85rem}
.src li{margin:3px 0}
"""
    return base + css.replace("@@LIGHT@@", light).replace("@@DARK@@", dark) + "".join(".ty.%s,.mv span.%s{background:var(--t-%s)}\n" % (t, t, t) for t in TYPES)


TOGGLE = """<script>
(function(){var cg=document.getElementById('cg'),bar=document.getElementById('modebar');if(!cg||!bar)return;
bar.hidden=false;var bs=bar.querySelectorAll('button');
function set(m){cg.setAttribute('data-mode',m);for(var i=0;i<bs.length;i++){bs[i].setAttribute('aria-pressed',bs[i].getAttribute('data-m')===m?'true':'false');}}
for(var i=0;i<bs.length;i++){bs[i].addEventListener('click',function(){set(this.getAttribute('data-m'));});}})();
</script>"""


def fmt(f):
    return FORMATS.get(f, pretty(f or "unknown"))


def type_chip(t):
    t = (t or "").lower()
    return '<span class="ty %s">%s</span>' % (esc(t) if t in TYPES else "", esc(pretty(t) or "?"))


def mon_html(m, names):
    sp, types = names.species(m["species"])
    det = []
    if m.get("ability"):
        det.append("Ability " + esc(names.ability(m["ability"])))
    if m.get("heldItem"):
        det.append("Item " + esc(names.item(m["heldItem"])))
    if m.get("nature"):
        det.append(esc(pretty(m["nature"])) + " nature")
    moves = []
    for mv in m.get("moveset") or []:
        name, typ = names.move(mv)
        moves.append('<span class="%s"%s>%s</span>' % (esc(typ or ""), ' title="%s"' % esc(pretty(typ)) if typ else "",
                                                       esc(name)))
    return ('<li class="mon"><div><span class="nm">%s</span><span class="lv">Lv %d</span> %s</div>%s'
            '<div class="mv">%s</div></li>' % (esc(sp), m["level"], "".join(type_chip(t) for t in types),
                                               '<div class="det">%s</div>' % " · ".join(det) if det else "",
                                               "".join(moves)))


def team_html(team, names):
    return '<ul class="team">%s</ul>' % "".join(mon_html(m, names) for m in team)


def compact(team, names, label):
    return '<p class="compact"><b>%s:</b> %s</p>' % (
        esc(label), esc(" · ".join("%s %d" % (names.species(m["species"])[0], m["level"]) for m in team)))


def modes_html(rec, names, plan_key):
    """The Challenge team in full (the Normal one compact), or the reverse when the toggle says Normal."""
    modes = rec.get("modes") or {}
    if "challenge" not in modes:
        return ('<p class="meta"><span class="tag">One team: no Challenge version authored</span></p>'
                + team_html(rec["team"], names))
    ch, no = modes["challenge"], modes["normal"]
    note = lambda mode, m: (plan_key(rec, mode, m) and '<p class="plan-note"><b>%s plan:</b> %s</p>'
                            % (mode.capitalize(), esc(plan_key(rec, mode, m)))) or ""
    if ch["team"] == no["team"]:
        return ('<p class="meta"><span class="tag plan">Challenge team is a placeholder, identical to Normal</span></p>'
                + team_html(no["team"], names) + note("normal", no))
    answers = ch.get("open_line")
    ans = ('<p class="compact"><b>Answers the design expects:</b> %s</p>'
           % esc(", ".join(names.species(s)[0] for s in answers))) if answers else ""
    return ('<div class="m-ch">%s%s%s</div><div class="m-no">%s%s</div>%s%s'
            % (team_html(ch["team"], names), note("challenge", ch), ans, team_html(no["team"], names),
               note("normal", no), '<div class="c-no">%s</div>' % compact(no["team"], names, "Normal team (live in game)"),
               '<div class="c-ch">%s</div>' % compact(ch["team"], names, "Challenge team (planned)")))


def boss_plan(rec, mode, m):
    return m.get("strategy")


def route_plan(rec, mode, m):
    return (rec.get("mode_intent") or {}).get(mode)


def ace(team):
    return max(m["level"] for m in team)


def summary_table(model, names):
    rows = []
    for g in model["gyms"]:
        r = g["rec"]
        rows.append((str(g["n"]), r["display_name"], g["town"], g["type"] or "", "Lv %d" % g["cap"], r["modes"]["normal"]["team"],
                     r["modes"]["challenge"]["team"]))
    for e in model["league"]:
        r = e["rec"]
        rows.append(("E4" if r["class"] == "elite_four" else "Ch", r["display_name"], "The League", e["type"] or "", "",
                     r["modes"]["normal"]["team"], r["modes"]["challenge"]["team"]))
    body = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d, ace Lv %d</td>"
                   "<td>%d, ace Lv %d%s</td></tr>" % (esc(a), esc(b), esc(c), type_chip(d) if d.lower() in TYPES else esc(d),
                                                       esc(cap), len(no), ace(no), len(ch), ace(ch),
                                                       " (placeholder)" if ch == no else "")
                   for a, b, c, d, cap, no, ch in rows)
    return ('<div class="tbl"><table><thead><tr><th>Badge</th><th>Trainer</th><th>Where</th><th>Type</th><th>Cap</th>'
            '<th>Normal (live)</th><th>Challenge</th></tr></thead><tbody>%s</tbody></table></div>' % body)


def gym_card(g, names):
    r = g["rec"]
    return ('<article class="card" id="%s"><header><h3><span class="badge">%d</span>%s</h3><span class="cap">Cap Lv %d</span>'
            '</header><p class="meta">%s · %s %s · %s · Gym spawner at x %d, z %d</p>%s</article>'
            % (esc(r["id"]), g["n"], esc(r["display_name"]), g["cap"], esc(g["town"]),
               type_chip(g["type"]) if (g["type"] or "").lower() in TYPES else '<span class="tag">%s</span>' % esc(g["type"]),
               esc(g["theme"] or ""), esc(fmt(g["format"])), g["x"], g["z"], modes_html(r, names, boss_plan)))


def league_card(e, names):
    r = e["rec"]
    role = "Champion" if r["class"] == "champion" else "Elite Four %d" % r.get("order", 0)
    return ('<article class="card" id="%s"><header><h3>%s</h3><span class="meta">%s</span></header>'
            '<p class="meta">%s %s</p>%s</article>'
            % (esc(r["id"]), esc(r["display_name"]), esc(role),
               type_chip(e["type"]) if (e["type"] or "").lower() in TYPES else '<span class="tag">%s</span>' % esc(e["type"]),
               esc(fmt(e["format"])), modes_html(r, names, boss_plan)))


def trainer_card(rec, seat, names):
    tags = []
    if rec.get("class") == "optional_route":
        tags.append('<span class="tag">Optional</span>')
    if seat and seat.get("eye_contact"):
        sd = seat.get("sight_distance")
        tags.append('<span class="tag sight">Battles on sight%s</span>' % (" (%g blocks)" % sd if sd else ""))
    elif seat and seat.get("eye_contact") is False:
        tags.append('<span class="tag">Talk to battle</span>')
    if rec.get("archetype"):
        tags.append('<span class="tag">%s</span>' % esc(pretty(rec["archetype"])))
    where = ("Stands at x %d, y %d, z %d" % tuple(seat["seat"])) if seat and seat.get("seat") else "No seat authored"
    extra = []
    if seat and seat.get("unavoidable"):
        extra.append("<b>Unavoidable:</b> " + esc(seat["unavoidable"]))
    if seat and seat.get("why"):
        extra.append("<b>Why here:</b> " + esc(seat["why"]))
    if rec.get("lesson"):
        extra.append("<b>Lesson:</b> " + esc(rec["lesson"]))
    name = rec.get("display_name") or rec.get("name") or rec["id"]
    fmt_ = rec.get("format") or (rec.get("rct") or {}).get("battleFormat")
    return ('<li class="card" id="%s"><header><h3>%s</h3><span>%s</span></header><p class="meta">%s%s</p>%s%s</li>'
            % (esc(rec["id"]), esc(name), "".join(tags), esc(where), (" · " + esc(fmt(fmt_))) if fmt_ else "",
               "".join('<p class="meta">%s</p>' % x for x in extra), modes_html(rec, names, route_plan)))


def route_section(g, names):
    cap, who = g["cap"]
    head = ("%s → %s" % (g["from"], g["to"])) if g.get("from") else ""
    capline = (' <span class="cap">Cap Lv %d</span>' % cap) if cap else ""
    return ('<section id="%s"><h2>%s%s</h2>%s%s<ol class="rt">%s</ol></section>'
            % (esc(g["key"]), esc(g["title"]), capline,
               '<p class="sub">%s%s</p>' % (esc(head), (" · level cap set by %s's ace" % esc(who)) if who else "") if head else "",
               '<p class="sub">%s</p>' % esc(g["note"]) if g.get("note") else "",
               "".join(trainer_card(r, s, names) for r, s in g["trainers"])))


def status_html(model):
    t, n = model["tally"], model["records"]
    if t["challenge"] == 0 and t[None] == 0:
        big = ("In game today every trainer uses its Normal team. Challenge is the planned harder mode: it is authored "
               "here but cannot be selected in game.")
    elif t["normal"] == 0 and t["both"] == 0:
        big = "In game today every trainer uses its Challenge team."
    else:
        big = ("The live roster is mixed: %d records emit their Normal team, %d their Challenge team, %d neither."
               % (t["normal"] + t["both"], t["challenge"], t[None]))
    return ('<div class="status" role="note"><p class="big">%s</p>'
            '<p>Measured, not assumed: %s writes each trainer\'s game file from its record\'s <code>rct</code> team '
            '(%s). Of the %d records in <code>data/trainers.json</code>, that team equals the Normal team for %d, the '
            'Challenge team for %d (%d have identical Normal and Challenge teams), and neither for %d.</p>'
            '<p>The data says the same: <code>generation_contract.runtime_mode_selection</code> = "%s".</p>'
            '<p>The trainers below that are not in <code>data/trainers.json</code> (the mansion guardians, the HQ '
            'tower) have one team only.</p></div>'
            % (esc(big), esc(EMITTER), esc(", ".join(model["emitter"]) or "no emitter line found"), n,
               t["normal"] + t["both"], t["challenge"] + t["both"], t["both"], t[None], esc(model["contract"] or "absent")))


def render(model, names):
    gyms = "".join(gym_card(g, names) for g in model["gyms"])
    league = "".join(league_card(e, names) for e in model["league"])
    la = model.get("league_at") or {}
    routes = "".join(route_section(g, names) for g in model["routes"])
    n_route = sum(len(g["trainers"]) for g in model["routes"])
    names_src = ("Pokemon, move, ability and item names and types: the Cobblemon 1.8 jar's Showdown data (%s)"
                 % esc(Path(names.sd["source"]).name)) if names.sd else (
        "No Cobblemon jar was found, so names are the data's ids title-cased and no types are shown")
    if names.missing:
        names_src += "; not found there, shown title-cased: %s" % esc(", ".join(sorted(names.missing)))
    return "".join([
        "<title>Challenge Mode Trainers</title>\n<style>%s</style>\n" % style(model["nm_style"]),
        '<main class="cg" id="cg">',
        "<h1>Challenge Mode Trainers</h1>",
        '<p class="sub">The eight gyms, the League and every route trainer, in travel order, with the Challenge '
        "team first and the Normal team beside it.</p>",
        status_html(model),
        '<p class="mapline">Map: see the Region Nuzlocke Map page</p>',
        '<div class="bar" id="modebar" hidden><span>Show full team:</span>'
        '<button type="button" data-m="challenge" aria-pressed="true">Challenge</button>'
        '<button type="button" data-m="normal" aria-pressed="false">Normal</button></div>',
        "<h2>At a glance</h2>", summary_table(model, names),
        '<p class="sub">Cap: rctmod\'s level cap while that leader is your next required trainer, '
        "max(initialLevelCap %d, the ace's level + relativeLevelCap %d), from the live team.</p>"
        % (model["init_cap"], model["rel_cap"]),
        '<h2 id="gyms">The eight gyms</h2><div class="cards two">%s</div>' % gyms,
        '<h2 id="league">The League</h2><p class="sub">%s Their spawners come with the League building; '
        "no coordinate is authored for them.</p>"
        % (("The League stands near x %d, z %d." % (la["x"], la["z"])) if la.get("x") is not None else ""),
        '<div class="cards two">%s</div>' % league,
        '<h2 id="routes">Route trainers</h2><p class="sub">%d trainers. "Battles on sight" means the trainer '
        "starts the fight when it sees you; the others wait to be spoken to.</p>" % n_route,
        routes,
        '<ul class="src"><li>Teams: <code>data/trainers.json</code>; seats: <code>data/route_trainers.json</code>, '
        "<code>data/late_route_trainers.json</code>, <code>data/mansion_guardians.json</code>, "
        "<code>data/vr_trainers.json</code>, <code>data/hq_trainers.json</code>; gyms: "
        "<code>data/gym_buildings/</code>, <code>data/gym_trainers.json</code>; caps: "
        "<code>modpack/config/rctmod-server.toml</code>.</li><li>%s.</li>"
        "<li>Generated by <code>tools/challenge_guide.py</code>. Valid page, not proof of in-game behaviour.</li></ul>"
        % names_src,
        "</main>\n", TOGGLE, "\n"])


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def page_problems(page):
    """The publishing tool's contract: page content only, a <title> first, one <style>, colours only as tokens with the
    three theme blocks, fonts only from fonts.googleapis.com, no external script, balanced tags."""
    out = []
    if not page.lstrip().startswith("<title>"):
        out.append("the page does not open with <title>")
    for tag in ("!doctype", "html", "head", "body"):
        if re.search(r"<%s[\s>]" % re.escape(tag), page, re.I):
            out.append("the page carries <%s>" % tag)
    for url in re.findall(r"""(?:https?:)?//[^\s"')]+""", page):
        if not url.split("//", 1)[1].startswith("fonts.googleapis.com/"):
            out.append("external reference %s" % url)
    if re.search(r"<script[^>]*\bsrc=", page, re.I):
        out.append("an external script")
    css = "".join(re.findall(r"<style>(.*?)</style>", page, re.S))
    if not css:
        out.append("no <style>")
    for need in (':root{', '@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){',
                 ':root[data-theme="dark"]{', "color-scheme:dark", "background:var(--paper)"):
        if need not in css:
            out.append("the style lacks %s" % need)
    # every literal colour sits inside a token declaration (--name:value)
    for decl in re.findall(r"([\w-]+)\s*:\s*[^;{}]*(?:#[0-9a-fA-F]{3,8}\b|rgba?\()", css):
        if not decl.startswith("--"):
            out.append("a literal colour outside a token: %s" % decl)
    body = re.sub(r"<style>.*?</style>|<script>.*?</script>", "", page, flags=re.S)
    stack = []
    for close, name in re.findall(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>", body):
        name = name.lower()
        if name in VOID:
            continue
        if not close:
            stack.append(name)
        elif not stack or stack.pop() != name:
            out.append("unbalanced </%s>" % name)
            break
    if stack:
        out.append("unclosed tags: %s" % stack[-5:])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--jar", help="the Cobblemon 1.8 jar (names and types); found automatically when omitted")
    ap.add_argument("--no-jar", action="store_true", help="skip the jar: ids title-cased, no types")
    a = ap.parse_args(argv)
    jar = None if a.no_jar else find_jar(a.jar)
    names = Names(showdown(jar) if jar else None)
    model = collect()
    page = render(model, names)
    bad = page_problems(page)
    if bad:
        raise SystemExit("the page breaks its contract, not written:\n  " + "\n  ".join(bad))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    t = model["tally"]
    print("wrote %s (%d bytes): %d gyms, %d League, %d route-side trainers; live roster normal=%d challenge=%d "
          "identical=%d neither=%d; names from %s%s"
          % (out, len(page.encode("utf-8")), len(model["gyms"]), len(model["league"]),
             sum(len(g["trainers"]) for g in model["routes"]), t["normal"], t["challenge"], t["both"], t[None],
             jar or "ids (no jar)", ("; %d ids not in the jar" % len(names.missing)) if names.missing else ""))


if __name__ == "__main__":
    main()
