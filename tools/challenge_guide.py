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

LAYOUT (the owner, 2026-10-05: "splits per gym and the end game, e4. have a sidebar for navigation as well through
the fight. im going to add fights so this will be the starter template"). One section per split in travel order --
split N ends at gym leader N, an "After the eighth badge" split holds the HQ tower, the end game is Victory Road, the
Elite Four in order and the Champion -- each one table of its fights whose rows open onto the team. A sidebar of
bare-token anchors (#split-3, #fight-route_02_trainer_01), sticky on desktop and a "Fights" drawer at <=700px,
highlights the current split. Without JavaScript every team is shown and the sidebar is plain links.

HOW FIGHTS ARE PLACED (no fight is hand-placed; RULE below is printed at the foot of the page). Every trainer record
in data/trainers.json and every entry of the seat-only files is placed by the first match: (1) its own `split` (1-8,
"hq" or "endgame"); (2) a gym leader by its `order`; (3) the Elite Four and Champion in the end game; (4) a seat-only
file's entries where SIDE puts that file (mansion: split 1; HQ tower: "hq"); (5) a `route_id` in the split of the gym
in the town data/routes.json says that route leads to, or the end game if it leads to the League. Anything else is
listed under Unplaced with its reason (and printed by the CLI), never dropped.

WHAT THIS DOES NOT COVER. In-game behaviour: valid output is not proof any trainer battles as listed. Trainers that
are not ours (Cobbleverse's own, anything a donor template places) are not listed. The Heaven's Arena exam teams
(data/arena_trainers.json, unseated since 2026-10-03) are not route trainers and are left out.

NOT ON THE PUBLIC SITE (decided 2026-10-08, when docs/player/ became one): this page stays in build/maps/ and does not
import tools/player_site.py. (1) tests/test_player_site_leaks.py finds a story quest's id in it: the status section
quotes data/trainers.json generation_contract.runtime_mode_selection, which names quest.main_worldshift_reveal. (2) It repeats
docs/player/battles.html, which already shows every fight in both modes, and adds what that guide leaves out on
purpose: the Gastly mansion's Channelers and the HQ tower's fights, and each seat's "why it is unavoidable". (3) Its
output is a fragment for another publisher (page_problems(): no <html>, one <style>), not a page that can carry the
site's shared header and stylesheet. Publishing it would need all three changed first.

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


# The seat-only files: their entries carry one team and no route, so the file says where they sit. An entry's own
# `split` still overrides this.
SIDE = (("data/mansion_guardians.json", {"split": 1, "area": "The Gastly mansion",
                                         "note": "The Gastly mansion, off Route 1: five possessed Channelers, one per "
                                                 "room (data/mansion_guardians.json)."}),
        ("data/hq_trainers.json", {"split": "hq", "area": "The Compact HQ tower", "note": None}))
WORDS = ("hq", "endgame")
RANK = {"route": 0, "side": 1, "other": 2, "leader": 3, "e4": 4, "champion": 5}
RULE = ("Every trainer record in data/trainers.json and every entry of the seat-only files (data/mansion_guardians.json, "
        "data/hq_trainers.json) is placed by the first rule that matches: (1) its own `split` field, 1 to 8 for a gym's "
        "split, \"hq\" for after the eighth badge or \"endgame\"; (2) a gym leader goes in the split of its `order`; "
        "(3) the Elite Four and the Champion go in the end game; (4) a seat-only file's entries go where that file is "
        "placed (the mansion in split 1, the HQ tower after the eighth badge); (5) a record with a `route_id` goes in "
        "the split of the gym in the town its route in data/routes.json leads to, or the end game if the route leads "
        "to the League. Anything else is listed under Unplaced with the reason, never dropped. Within a split: route "
        "trainers by trainer_order (optional ones after), then side areas, then other placed fights, then the gym "
        "leader; the end game ends with the Elite Four in order and the Champion.")


def short_route(name):
    """'Route 1 — Pallet to Brock' -> 'Route 1'."""
    return re.split(r"\s+[–—-]\s+", name or "", maxsplit=1)[0]


def split_value(v, n_gyms):
    if isinstance(v, bool):
        return None
    if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
        return int(v) if 1 <= int(v) <= n_gyms else None
    return v if v in WORDS else None


def place(rec, seat, side, route_by_id, gym_by_town, n_gyms):
    """(split, kind, area, reason) by RULE; split is None (and reason says why) when nothing matches."""
    cls = rec.get("class")
    kind = {"gym_leader": "leader", "elite_four": "e4", "champion": "champion"}.get(cls) or (
        "side" if side else "route" if rec.get("route_id") else "other")
    rt = route_by_id.get(rec.get("route_id"))
    area = side["area"] if side else short_route(rt["display_name"]) if rt else None
    explicit = rec.get("split", (seat or {}).get("split"))
    if explicit is not None:
        k = split_value(explicit, n_gyms)
        if k is None:
            return None, kind, area, "its split %r is not 1-%d, \"hq\" or \"endgame\"" % (explicit, n_gyms)
        return k, kind, area, None
    if kind == "leader":
        k = split_value(rec.get("order"), n_gyms)
        return (k, kind, area, None) if k else (None, kind, area, "a gym leader whose order %r is not 1-%d"
                                                % (rec.get("order"), n_gyms))
    if kind in ("e4", "champion"):
        return "endgame", kind, "The League", None
    if side:
        return side["split"], kind, area, None
    if rec.get("route_id"):
        if not rt:
            return None, kind, area, "route_id %r is not in data/routes.json" % rec["route_id"]
        if rt.get("to_town") in gym_by_town:
            return gym_by_town[rt["to_town"]], kind, area, None
        if rt.get("to_town") == "league":
            return "endgame", kind, area, None
        return None, kind, area, "its route %s leads to %r, which has no gym and is not the League" % (
            rt["id"], rt.get("to_town"))
    return None, kind, area, "class %r with no route_id and no split" % cls


def build_splits(recs, seat_of, routes, gyms, league_meta, caps, side_entries, town_name):
    """[split], [unplaced fight]: every record and side entry placed by RULE, none dropped."""
    n = len(gyms)
    route_by_id = {r["id"]: r for r in routes}
    gym_by_town = {g["town_id"]: g["n"] for g in gyms}
    fights, unplaced = {}, []
    items = [(r, seat_of.get(r["id"]), None) for r in recs] + [(e, seat_of.get(e["id"], e), s) for e, s in side_entries]
    for i, (rec, seat, side) in enumerate(items):
        k, kind, area, reason = place(rec, seat, side, route_by_id, gym_by_town, n)
        f = {"rec": rec, "seat": seat, "kind": kind, "area": area, "reason": reason, "side": side,
             "sort": (RANK[kind], rec.get("class") != "route" if kind == "route" else 0,
                      rec.get("trainer_order") or rec.get("order") or 0, i)}
        if kind in ("leader", "e4", "champion"):
            f["meta"] = (next((g for g in gyms if g["n"] == k), {}) if kind == "leader"
                         else league_meta.get(rec["id"], {}))
        (unplaced if k is None else fights.setdefault(k, [])).append(f)
    after = caps.get(n + 1, (None, None))
    splits = []
    for g in gyms:
        rt = next((r for r in routes if r.get("to_town") == g["town_id"]), None)
        frm = town_name(rt["from_town"]) if rt else None
        splits.append({"key": str(g["n"]), "title": "Split %d: %s%s" % (g["n"], (frm + " → ") if frm else "", g["town"]),
                       "nav": "%d · %s" % (g["n"], g["rec"]["display_name"]), "cap": caps.get(g["n"], (None, None)),
                       "gym": g, "fights": fights.get(g["n"], [])})
    if fights.get("hq"):
        splits.append({"key": "hq", "title": "After the eighth badge", "nav": "After badge %d" % n, "cap": after,
                       "gym": None, "fights": fights["hq"]})
    road = next((r for r in routes if r.get("to_town") == "league"), None)
    splits.append({"key": "endgame", "title": "End game: %sthe League" % (
        (short_route(road["display_name"]) + " and ") if road else ""), "nav": "End game", "cap": after,
                   "gym": None, "fights": fights.get("endgame", [])})
    for s in splits:
        s["fights"].sort(key=lambda f: f["sort"])
        notes = []
        for f in s["fights"]:
            rt = route_by_id.get(f["rec"].get("route_id"))
            note = (f["side"] or {}).get("note") or (rt and "%s: %s → %s" % (
                f["area"], town_name(rt["from_town"]), town_name(rt["to_town"])))
            if note and note not in notes:
                notes.append(note)
        s["notes"] = notes
    return splits, unplaced


def collect():
    import nuzlocke_map as NM
    import route_trainers as RT

    doc = load_json("data/trainers.json")
    recs = doc["trainers"]
    town = {t["id"]: t for t in NM.towns()}
    caps = NM.level_caps()
    gpos = NM.gyms()
    gmeta = {e["id"]: e for e in load_json("data/gym_trainers.json")["trainers"]}
    lmeta = {e["id"]: e for e in load_json("data/league_trainers.json")["trainers"]}

    gyms = []
    for r in sorted((r for r in recs if r["class"] == "gym_leader"), key=lambda r: r["order"]):
        n, g, meta = r["order"], gpos[r["order"]], gmeta.get(r["id"], {})
        gyms.append({"rec": r, "n": n, "town_id": g["town"], "town": town.get(g["town"], {}).get("name", g["town"]),
                     "x": g["x"], "z": g["z"], "type": meta.get("theme"), "theme": r.get("theme"),
                     "format": meta.get("battle_format") or r["rct"].get("battleFormat") or r.get("format"),
                     "cap": caps[n][0], "upstream": meta.get("upstream_trainer_id")})
    league_meta = {}
    for r in recs:
        if r["class"] in ("elite_four", "champion"):
            meta = lmeta.get(r["id"], {})
            league_meta[r["id"]] = {"type": meta.get("theme") or r.get("theme"),
                                    "format": meta.get("battle_format") or r["rct"].get("battleFormat") or r.get("format"),
                                    "upstream": meta.get("upstream_trainer_id")}

    _recs, seats, _fields = RT.load()
    seat_of = {s["id"]: s for s in seats}
    routes = sorted(load_json("data/routes.json")["routes"], key=lambda r: int(r["order"]))
    side_entries = []
    for rel, spec in SIDE:
        d = load_json(rel)
        spec = dict(spec)
        if spec["note"] is None and rel.endswith("hq_trainers.json"):
            spec["note"] = "The Compact HQ tower: " + d["band"]["why"].split(";")[0] + "."
        side_entries += [(e, spec) for e in d["trainers"]]
    splits, unplaced = build_splits(recs, seat_of, routes, gyms, league_meta, caps, side_entries,
                                    lambda t: town.get(t, {}).get("name", t))

    tally = {"normal": 0, "challenge": 0, "both": 0, None: 0}
    for r in recs:
        tally[live_mode(r)] += 1
    return {"splits": splits, "unplaced": unplaced, "league_at": town.get("league", {}), "tally": tally,
            "records": len(recs), "contract": doc.get("generation_contract", {}).get("runtime_mode_selection"),
            "emitter": emitter_lines(), "init_cap": NM.rct_setting("initialLevelCap"),
            "rel_cap": NM.rct_setting("relativeLevelCap"), "nm_style": NM.STYLE}


# ------------------------------------------------------------------ page
#
# Layout (the owner, 2026-10-05: "splits per gym and the end game, e4. have a sidebar for navigation as well through
# the fight. im going to add fights so this will be the starter template"): one section per split in travel order,
# each ONE table of its fights whose rows open onto that fight's team as a compact table; a sidebar (sticky on
# desktop, a "Fights" drawer at <=700px) of in-page anchors. Without JavaScript the page is complete: every team row
# is shown and the sidebar is a plain list of links. The script only hides, reveals and highlights.

TYPE_LIGHT = dict(zip(TYPES, ("#e4e1d3", "#f8cfb0", "#c6dcf5", "#f6e59a", "#cde8b8", "#cdeeed", "#efc0b8", "#e0c4e6",
                              "#ecd9ad", "#d6d9f5", "#f6c4d6", "#dfe7a6", "#e0d6b0", "#d2c8e4", "#c9c2f2", "#d4ccc6",
                              "#d8dde3", "#f6cfe9")))
TYPE_DARK = dict(zip(TYPES, ("#4a4636", "#6e3218", "#1f4170", "#5e5010", "#2f5a1f", "#1f5a5a", "#6a2420", "#522a5e",
                             "#5e4a1e", "#363f78", "#6c2442", "#4a5414", "#574c26", "#3e3260", "#362a7a", "#3d332d",
                             "#3e4650", "#6a2a58")))
OWN_LIGHT = "--warn-bg:#fff3cd; --warn-rule:#d9a400; --live:#0e766c; --plan:#8a3b9a; --zebra:#e9eee5; --sight:#b01a31;"
OWN_DARK = "--warn-bg:#3a3010; --warn-rule:#c99a1c; --live:#52c7b8; --plan:#d39be0; --zebra:#222c32; --sight:#ff8a96;"

# WCAG AA, checked on the page's own CSS in both themes (page_problems): text 4.5:1, the focus ring 3:1
TEXT_PAIRS = ([("ink", bg) for bg in ("paper", "card", "zebra", "tag-bg", "warn-bg")]
              + [("ink-soft", bg) for bg in ("paper", "card", "zebra", "tag-bg")]
              + [("sight", "tag-bg"), ("plan", "tag-bg"), ("marker-ink", "marker"), ("gold-ink", "gold")]
              + [("ink", "t-" + t) for t in TYPES])
UI_PAIRS = [("marker", bg) for bg in ("paper", "card", "zebra")]


def tokens(palette, own):
    return " ".join("--t-%s:%s;" % (t, c) for t, c in palette.items()) + " " + own


def style(nm_style):
    base = nm_style.split("*{box-sizing")[0]          # the map page's @import and its three token blocks
    light, dark = tokens(TYPE_LIGHT, OWN_LIGHT), tokens(TYPE_DARK, OWN_DARK)
    css = """:root{ @@LIGHT@@ }
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){ @@DARK@@ color-scheme:dark; }}
:root[data-theme="dark"]{ @@DARK@@ color-scheme:dark; }
*{box-sizing:border-box}
.cg [hidden]{display:none !important}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);font-size:16px;line-height:1.45}
.cg{max-width:1360px;margin:0 auto;padding:20px 16px 48px}
.cg h1{font-family:var(--display);font-weight:700;font-size:clamp(1.7rem,4.5vw,2.6rem);margin:0 0 4px}
.cg h2{font-family:var(--display);font-weight:700;font-size:1.4rem;margin:26px 0 8px;border-bottom:2px solid var(--path);padding-bottom:4px;display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline}
.sub{color:var(--ink-soft);margin:0 0 10px}
.status{background:var(--warn-bg);border:1px solid var(--warn-rule);border-left:6px solid var(--warn-rule);border-radius:10px;padding:12px 16px;margin:0 0 14px}
.status p{margin:4px 0}.status .big{font-weight:700;font-size:1.08rem}
.status code,.src code{font-size:.82rem;overflow-wrap:anywhere}
.mapline{color:var(--ink-soft);font-style:italic;margin:0 0 14px}
.layout{display:grid;grid-template-columns:minmax(0,1fr);gap:20px;align-items:start}
@media (min-width:701px){.layout{grid-template-columns:260px minmax(0,1fr)}
.side{position:sticky;top:0;max-height:100vh;overflow:auto;padding:10px 0}
.drawer > summary{display:none}}
.side{background:var(--paper)}
.seg{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 10px}
.seg button{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--rule);border-radius:999px;padding:4px 14px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--marker);color:var(--marker-ink);border-color:var(--marker)}
.drawer > summary{font-family:var(--display);font-weight:700;font-size:1.05rem;cursor:pointer;padding:8px 12px;background:var(--card);border:1px solid var(--rule);border-radius:10px}
.nav{font-size:.92rem}
.nav ol{list-style:none;margin:0;padding:0}
.nav > ol > li{margin:0 0 4px}
.nav a{display:block;color:var(--ink);text-decoration:none;border-radius:6px;padding:3px 8px;overflow-wrap:anywhere}
.nav a:hover{text-decoration:underline}
.nav a.sp{font-weight:700}
.nav a[aria-current]{background:var(--marker);color:var(--marker-ink)}
.nav details{margin:0 0 0 8px}
.nav details > summary{cursor:pointer;color:var(--ink-soft);font-size:.85rem;padding:1px 8px}
.nav details ol{border-left:2px solid var(--rule);margin:2px 0 6px 10px}
.cg a:focus-visible,.cg button:focus-visible,.cg summary:focus-visible{outline:3px solid var(--marker);outline-offset:2px}
.split,.sum{scroll-margin-top:12px}
.tbl{overflow:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--rule);border-radius:10px;background:var(--card);margin:0 0 10px}
.cg.js .tbl{max-height:85vh}
.tbl > table{border-collapse:separate;border-spacing:0;width:100%;min-width:680px;font-size:.93rem}
.cg table caption{caption-side:top;text-align:left;font-weight:700;padding:8px 10px;color:var(--ink)}
.cg th,.cg td{padding:6px 10px;text-align:left;border-top:1px solid var(--rule);vertical-align:top}
.cg thead th{border-top:0;color:var(--ink-soft);font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;background:var(--card)}
.tbl > table > thead th{position:sticky;top:0;z-index:1;box-shadow:inset 0 -1px 0 var(--rule)}
.sum.z > *{background:var(--zebra)}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.tm > td{background:var(--card);padding:4px 10px 14px}
.xp{font:inherit;font-weight:700;color:var(--ink);background:none;border:0;padding:0;cursor:pointer;text-align:left}
.xp::before{content:"\\25B8";display:inline-block;width:1.1em;transition:transform .15s}
.xp[aria-expanded="true"]::before{transform:rotate(90deg)}
@media (prefers-reduced-motion:reduce){.xp::before{transition:none}}
.team{border-collapse:collapse;width:100%;font-size:.9rem;margin:6px 0 0;border:1px solid var(--rule)}
.team caption{padding:4px 0}
.team tbody tr:nth-child(even) > *{background:var(--zebra)}
.team .spc{margin-right:4px}
.gymline{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:8px 12px;margin:0 0 10px}
.badge{display:inline-grid;place-items:center;min-width:1.9em;height:1.9em;border-radius:999px;background:var(--gold);color:var(--gold-ink);font-weight:700;margin-right:4px}
.cap{font-family:var(--display);font-weight:700;font-size:1rem;background:var(--gold);color:var(--gold-ink);border-radius:999px;padding:1px 10px;white-space:nowrap}
.meta{color:var(--ink-soft);font-size:.92rem;margin:4px 0;overflow-wrap:anywhere}
.tag{display:inline-block;font-size:.78rem;background:var(--tag-bg);border-radius:4px;padding:0 6px;margin:1px 2px 1px 0;white-space:nowrap}
.tag.sight{color:var(--sight);font-weight:700}.tag.live{color:var(--live);font-weight:700}.tag.plan{color:var(--plan);font-weight:700}
.ty{display:inline-block;font-size:.74rem;font-weight:700;border-radius:4px;padding:0 6px;margin:1px 2px 1px 0;text-transform:uppercase;letter-spacing:.03em;background:var(--tag-bg);color:var(--ink)}
.plan-note{font-size:.92rem;margin:6px 0 0}
.compact{font-size:.88rem;color:var(--ink-soft);margin:8px 0 0;overflow-wrap:anywhere}
.compact b{color:var(--ink)}
.cg[data-mode="normal"] .m-ch,.cg[data-mode="normal"] .c-no{display:none}
.cg:not([data-mode="normal"]) .m-no,.cg:not([data-mode="normal"]) .c-ch{display:none}
.how{margin-top:28px}
.src{margin-top:12px;color:var(--ink-soft);font-size:.85rem}
.src li{margin:3px 0}
@media (max-width:700px){
.cg.js .side{position:sticky;top:0;z-index:3;padding:6px 0}
.cg.js .drawer[open] .nav{max-height:60vh;overflow:auto;background:var(--card);border:1px solid var(--rule);border-radius:10px;margin-top:4px;padding:6px}
.cg.js .split,.cg.js .sum{scroll-margin-top:96px}
}
@media (max-width:480px){
.stk,.stk > tbody,.stk > tbody > tr,.stk > tbody > tr > th,.stk > tbody > tr > td,.stk > caption{display:block;width:100%}
.stk > thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.tbl > table{min-width:0}
.cg.js .tbl{max-height:none}
.stk > tbody > tr{border-top:1px solid var(--rule);padding:6px 0}
.stk > tbody > tr > th,.stk > tbody > tr > td{border-top:0;padding:2px 10px}
.stk > tbody > tr > td[data-l]::before{content:attr(data-l) ": ";font-weight:700;color:var(--ink-soft)}
.tm > td{padding:4px 6px 12px}
}
"""
    return base + css.replace("@@LIGHT@@", light).replace("@@DARK@@", dark) + "".join(
        ".ty.%s{background:var(--t-%s)}\n" % (t, t) for t in TYPES)


SCRIPT = """<script>
(function(){var cg=document.getElementById('cg');if(!cg)return;cg.className+=' js';
var bar=document.getElementById('modebar');
if(bar){bar.hidden=false;var bs=bar.querySelectorAll('button');
var setMode=function(m){cg.setAttribute('data-mode',m);for(var i=0;i<bs.length;i++){bs[i].setAttribute('aria-pressed',bs[i].getAttribute('data-m')===m?'true':'false');}};
for(var i=0;i<bs.length;i++){bs[i].addEventListener('click',function(){setMode(this.getAttribute('data-m'));});}}
var hosts=cg.querySelectorAll('[data-team]');
for(var j=0;j<hosts.length;j++){(function(h){var row=document.getElementById(h.getAttribute('data-team')),nm=h.querySelector('.nm');if(!row||!nm)return;
var b=document.createElement('button');b.type='button';b.className='xp';b.setAttribute('aria-expanded','false');b.setAttribute('aria-controls',row.id);
nm.parentNode.insertBefore(b,nm);b.appendChild(nm);row.hidden=true;
b.addEventListener('click',function(){var o=b.getAttribute('aria-expanded')!=='true';b.setAttribute('aria-expanded',o?'true':'false');row.hidden=!o;});})(hosts[j]);}
var drawer=document.getElementById('drawer'),mq=window.matchMedia?window.matchMedia('(max-width:700px)'):null;
var narrow=function(){return !!(mq&&mq.matches);};
var fit=function(){if(drawer)drawer.open=!narrow();};fit();
if(mq){if(mq.addEventListener)mq.addEventListener('change',fit);else if(mq.addListener)mq.addListener(fit);}
var open=function(id){var t=id?document.getElementById(id):null;if(!t)return;var xb=t.querySelector('.xp');if(xb&&xb.getAttribute('aria-expanded')!=='true')xb.click();};
var nav=document.getElementById('nav');
if(nav){nav.addEventListener('click',function(e){var a=e.target.closest?e.target.closest('a'):null;if(!a)return;open(a.getAttribute('href').slice(1));if(narrow()&&drawer)drawer.open=false;});}
if(location.hash){open(decodeURIComponent(location.hash.slice(1)));}
if(nav&&'IntersectionObserver' in window){var links={},al=nav.querySelectorAll('a');for(var k=0;k<al.length;k++){links[al[k].getAttribute('href').slice(1)]=al[k];}
var cur={};var mark=function(kind,id){if(cur[kind]===id||!links[id])return;if(cur[kind]&&links[cur[kind]])links[cur[kind]].removeAttribute('aria-current');cur[kind]=id;links[id].setAttribute('aria-current','location');
if(kind==='s'&&!narrow()){var d=links[id].parentNode.querySelector('details');if(d)d.open=true;}};
var io=new IntersectionObserver(function(es){for(var i=0;i<es.length;i++){if(es[i].isIntersecting){var el=es[i].target;mark(el.tagName==='SECTION'?'s':'f',el.id);}}},{rootMargin:'0px 0px -75% 0px'});
var obs=cg.querySelectorAll('section.split,tr.sum');for(var o=0;o<obs.length;o++)io.observe(obs[o]);}
})();
</script>"""


def anchor(prefix, s):
    """A bare-token in-page anchor: letters, digits, _ - . only."""
    return prefix + re.sub(r"[^A-Za-z0-9_.-]", "-", str(s))


def fmt(f):
    return FORMATS.get(f, pretty(f or "unknown"))


def type_chip(t):
    t = (t or "").lower()
    return '<span class="ty %s">%s</span>' % (esc(t) if t in TYPES else "", esc(pretty(t) or "?"))


def theme_html(typ, theme=None):
    chip = type_chip(typ) if (typ or "").lower() in TYPES else '<span class="tag">%s</span>' % esc(typ or "?")
    return chip + (" " + esc(theme) if theme else "")


def ace(team):
    return max(m["level"] for m in team)


def thead(cols):
    return "<thead><tr>%s</tr></thead>" % "".join('<th scope="col">%s</th>' % esc(c) for c in cols)


TEAM_COLS = ("Pokemon", "Lv", "Ability", "Item", "Nature", "Moves")


def mon_row(m, names):
    sp, types = names.species(m["species"])
    moves = ", ".join(names.move(mv)[0] for mv in m.get("moveset") or [])
    cell = lambda label, v, cls="": '<td%s data-l="%s">%s</td>' % (' class="%s"' % cls if cls else "", label, v)
    return ('<tr><th scope="row"><span class="spc">%s</span>%s</th>%s%s%s%s%s</tr>'
            % (esc(sp), "".join(type_chip(t) for t in types), cell("Level", "%d" % m["level"], "num"),
               cell("Ability", esc(names.ability(m["ability"])) if m.get("ability") else "none"),
               cell("Item", esc(names.item(m["heldItem"])) if m.get("heldItem") else "none"),
               cell("Nature", esc(pretty(m["nature"])) if m.get("nature") else "unset"),
               cell("Moves", esc(moves) or "unset")))


def team_table(team, names, caption):
    return ('<table class="team stk"><caption>%s</caption>%s<tbody>%s</tbody></table>'
            % (esc(caption), thead(TEAM_COLS), "".join(mon_row(m, names) for m in team)))


def compact(team, names, label):
    return '<p class="compact"><b>%s:</b> %s</p>' % (
        esc(label), esc(" · ".join("%s %d" % (names.species(m["species"])[0], m["level"]) for m in team)))


def modes_block(rec, names, plan_key, who):
    """The Challenge team as a table (the Normal one compact under it), or the reverse when the toggle says Normal."""
    modes = rec.get("modes") or {}
    if "challenge" not in modes:
        return ('<p class="meta"><span class="tag">One team: no Challenge version authored</span></p>'
                + team_table(rec["team"], names, "%s: the one team" % who))
    ch, no = modes["challenge"], modes["normal"]
    note = lambda mode, m: (plan_key(rec, mode, m) and '<p class="plan-note"><b>%s plan:</b> %s</p>'
                            % (mode.capitalize(), esc(plan_key(rec, mode, m)))) or ""
    if ch["team"] == no["team"]:
        return ('<p class="meta"><span class="tag plan">Challenge team is a placeholder, identical to Normal</span></p>'
                + team_table(no["team"], names, "%s: Normal team (Challenge is the same placeholder)" % who)
                + note("normal", no))
    answers = ch.get("open_line")
    ans = ('<p class="compact"><b>Answers the design expects:</b> %s</p>'
           % esc(", ".join(names.species(s)[0] for s in answers))) if answers else ""
    return ('<div class="m-ch">%s%s%s</div><div class="m-no">%s%s</div>%s%s'
            % (team_table(ch["team"], names, "%s: Challenge team" % who), note("challenge", ch), ans,
               team_table(no["team"], names, "%s: Normal team" % who), note("normal", no),
               '<div class="c-no">%s</div>' % compact(no["team"], names, "Normal team (live in game)"),
               '<div class="c-ch">%s</div>' % compact(ch["team"], names, "Challenge team (planned)")))


def mode_val(rec, f, mark=False):
    """f(team) for the mode the toggle shows; one value when there is one team or the two are identical."""
    modes = rec.get("modes") or {}
    if "challenge" not in modes:
        return esc(f(rec["team"]))
    ch, no = modes["challenge"]["team"], modes["normal"]["team"]
    if ch == no:
        return esc(f(no)) + (' <span class="tag plan">placeholder</span>' if mark else "")
    return '<span class="m-ch">%s</span><span class="m-no">%s</span>' % (esc(f(ch)), esc(f(no)))


def boss_plan(rec, mode, m):
    return m.get("strategy")


def route_plan(rec, mode, m):
    return (rec.get("mode_intent") or {}).get(mode)


def team_desc(t):
    return "%d, ace Lv %d" % (len(t), ace(t))


FIGHT_COLS = ("#", "Fight", "Where", "Stands at", "Unavoidable", "Team", "Ace Lv")


def fight_name(f):
    r = f["rec"]
    return r.get("display_name") or r.get("name") or r["id"]


def fight_rows(f, i, names):
    rec, seat, kind = f["rec"], f["seat"], f["kind"]
    meta = f.get("meta") or {}
    rid = rec["id"]
    kinds, tags, extra = [], [], []
    if kind == "leader":
        kinds.append('<span class="tag">Gym leader, badge %d</span>' % rec["order"])
    elif kind == "e4":
        kinds.append('<span class="tag">Elite Four %d</span>' % rec.get("order", 0))
    elif kind == "champion":
        kinds.append('<span class="tag">Champion</span>')
    if rec.get("class") == "optional_route":
        kinds.append('<span class="tag">Optional</span>')
    if rec.get("archetype"):
        kinds.append('<span class="tag">%s</span>' % esc(pretty(rec["archetype"])))
    if seat and seat.get("eye_contact"):
        sd = seat.get("sight_distance")
        tags.append('<span class="tag sight">Battles on sight%s</span>' % (" (%g blocks)" % sd if sd else ""))
    elif seat and seat.get("eye_contact") is False:
        tags.append('<span class="tag">Talk to battle</span>')
    fmt_ = meta.get("format") or rec.get("format") or (rec.get("rct") or {}).get("battleFormat")
    if fmt_:
        tags.append('<span class="tag">%s</span>' % esc(fmt(fmt_)))
    if kind in ("e4", "champion") and meta.get("type"):
        tags.append(theme_html(meta["type"]))
    if f.get("reason"):
        extra.append("<b>Unplaced:</b> " + esc(f["reason"]))
    if seat and seat.get("unavoidable"):
        extra.append("<b>Unavoidable:</b> " + esc(seat["unavoidable"]))
    if seat and seat.get("why"):
        extra.append("<b>Why here:</b> " + esc(seat["why"]))
    if rec.get("lesson"):
        extra.append("<b>Lesson:</b> " + esc(rec["lesson"]))
    boss = kind in ("leader", "e4", "champion")
    if kind == "leader" and "x" in meta:
        where, pos = "%s gym" % meta["town"], "x %d, z %d (gym spawner)" % (meta["x"], meta["z"])
    elif kind in ("e4", "champion"):
        where, pos = "The League", "League building, no authored coordinate"
    else:
        where = f["area"] or "No route"
        pos = ("x %d, y %d, z %d" % tuple(seat["seat"])) if seat and seat.get("seat") else "No seat authored"
    unav = "Boss" if boss else "Yes" if seat and seat.get("unavoidable") else "No"
    name = fight_name(f)
    cells = ('<td class="num" data-l="#">%d</td><th scope="row" data-team="%s"><span class="nm">%s</span>%s</th>'
             '<td data-l="Where">%s</td><td class="num" data-l="Stands at">%s</td><td data-l="Unavoidable">%s</td>'
             '<td class="num" data-l="Team">%s</td><td class="num" data-l="Ace Lv">%s</td>'
             % (i + 1, anchor("team-", rid), esc(name), (" " + " ".join(kinds)) if kinds else "", esc(where), esc(pos),
                unav, mode_val(rec, lambda t: "%d" % len(t), True), mode_val(rec, lambda t: "%d" % ace(t))))
    inner = (('<p class="meta">%s</p>' % " ".join(tags) if tags else "")
             + "".join('<p class="meta">%s</p>' % x for x in extra)
             + modes_block(rec, names, boss_plan if boss else route_plan, name))
    return ('<tr class="sum%s" id="%s" data-tm="%s">%s</tr><tr class="tm" id="%s"><td colspan="%d">%s</td></tr>'
            % (" z" if i % 2 else "", anchor("fight-", rid), anchor("team-", rid), cells, anchor("team-", rid),
               len(FIGHT_COLS), inner))


def fights_table(fights, names, caption):
    return ('<div class="tbl"><table class="stk"><caption>%s</caption>%s<tbody>%s</tbody></table></div>'
            % (esc(caption), thead(FIGHT_COLS), "".join(fight_rows(f, i, names) for i, f in enumerate(fights))))


def gym_line(g):
    r = g["rec"]
    return ('<p class="gymline"><span class="badge">%d</span><b>%s</b> · %s · %s · %s · team %s · gym spawner '
            '<span class="num">x %d, z %d</span></p>'
            % (g["n"], esc(r["display_name"]), esc(g["town"]), theme_html(g["type"], g["theme"]), esc(fmt(g["format"])),
               mode_val(r, team_desc, True), g["x"], g["z"]))


def split_section(s, model, names):
    cap, who = s["cap"]
    sid = anchor("split-", s["key"])
    capline = '<span class="cap">Cap Lv %d</span>' % cap if cap else ""
    lead = ('<p class="sub">Level cap set by %s\'s ace.</p>' % esc(who)) if who else ""
    if s["key"] == "endgame":
        la = model.get("league_at") or {}
        lead += ('<p class="sub">%sThe Elite Four\'s and Champion\'s spawners come with the League building; no '
                 "coordinate is authored for them.</p>"
                 % (("The League stands near x %d, z %d. " % (la["x"], la["z"])) if la.get("x") is not None else ""))
    body = (fights_table(s["fights"], names, "%s: %d fights in order. Open a fight for the team."
                         % (s["title"], len(s["fights"])))
            if s["fights"] else '<p class="meta">No fights placed here yet.</p>')
    return ('<section class="split" id="%s" aria-labelledby="h-%s"><h2 id="h-%s">%s %s</h2>%s%s%s%s</section>'
            % (sid, sid, sid, esc(s["title"]), capline, lead, gym_line(s["gym"]) if s.get("gym") else "",
               "".join('<p class="sub">%s</p>' % esc(n) for n in s["notes"]), body))


def unplaced_section(model, names):
    u = model.get("unplaced") or []
    if not u:
        return ""
    return ('<section class="split" id="split-unplaced" aria-labelledby="h-split-unplaced"><h2 id="h-split-unplaced">'
            'Unplaced</h2><p class="sub">%d fights match no placement rule; each row says why.</p>%s</section>'
            % (len(u), fights_table(u, names, "Unplaced fights. Open a fight for the reason and the team.")))


def sidebar(model):
    items = []
    groups = [(anchor("split-", s["key"]), s["nav"], s["fights"]) for s in model["splits"]]
    if model.get("unplaced"):
        groups.append(("split-unplaced", "Unplaced", model["unplaced"]))
    for sid, label, fights in groups:
        sub = "".join('<li><a href="#%s">%s</a></li>' % (anchor("fight-", f["rec"]["id"]), esc(fight_name(f)))
                      for f in fights)
        items.append('<li><a class="sp" href="#%s">%s</a>%s</li>'
                     % (sid, esc(label), ('<details><summary>%d fights</summary><ol>%s</ol></details>'
                                          % (len(fights), sub)) if fights else ""))
    return ('<aside class="side" aria-label="Guide navigation">'
            '<div class="seg" id="modebar" role="group" aria-label="Teams shown in full" hidden><span>Teams:</span>'
            '<button type="button" data-m="challenge" aria-pressed="true">Challenge</button>'
            '<button type="button" data-m="normal" aria-pressed="false">Normal</button></div>'
            '<details class="drawer" id="drawer" open><summary>Fights</summary>'
            '<nav class="nav" id="nav" aria-label="Fights by split"><ol>%s</ol></nav></details></aside>'
            % "".join(items))


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
    names_src = ("Pokemon, move, ability and item names and types: the Cobblemon 1.8 jar's Showdown data (%s)"
                 % esc(Path(names.sd["source"]).name)) if names.sd else (
        "No Cobblemon jar was found, so names are the data's ids title-cased and no types are shown")
    if names.missing:
        names_src += "; not found there, shown title-cased: %s" % esc(", ".join(sorted(names.missing)))
    n_fights = sum(len(s["fights"]) for s in model["splits"])
    return "".join([
        "<title>Challenge Mode Trainers</title>\n<style>%s</style>\n" % style(model["nm_style"]),
        '<main class="cg" id="cg" data-mode="challenge">',
        "<h1>Challenge Mode Trainers</h1>",
        '<p class="sub">Every fight, split by gym in travel order and then the end game: %d fights in %d splits. Each '
        "row opens onto that fight's team; Challenge teams are shown in full, with the Normal team summarised under "
        "them.</p>" % (n_fights, len(model["splits"])),
        status_html(model),
        '<p class="mapline">Map: see the Region Nuzlocke Map page</p>',
        '<p class="sub">Cap: rctmod\'s level cap while that split\'s boss is your next required trainer, '
        "max(initialLevelCap %d, the ace's level + relativeLevelCap %d), from the live team. \"Battles on sight\" "
        "means the trainer starts the fight when it sees you; the others wait to be spoken to. Unavoidable \"Yes\" "
        "means the trainer's seat file records why it cannot be walked past.</p>" % (model["init_cap"], model["rel_cap"]),
        '<div class="layout">', sidebar(model), '<div class="content">',
        "".join(split_section(s, model, names) for s in model["splits"]),
        unplaced_section(model, names),
        '<section class="how" id="how" aria-labelledby="h-how"><h2 id="h-how">How fights are placed</h2>'
        '<p class="sub">%s To add a fight: add a trainer record to <code>data/trainers.json</code> with a '
        "<code>route_id</code> from <code>data/routes.json</code> (or a <code>split</code> of 1-8, \"hq\" or "
        "\"endgame\") and re-run <code>python tools/challenge_guide.py</code>.</p></section>" % esc(RULE),
        '<ul class="src"><li>Teams: <code>data/trainers.json</code>; seats: <code>data/route_trainers.json</code>, '
        "<code>data/late_route_trainers.json</code>, <code>data/mansion_guardians.json</code>, "
        "<code>data/vr_trainers.json</code>, <code>data/hq_trainers.json</code>; routes: "
        "<code>data/routes.json</code>; gyms: <code>data/gym_buildings/</code>, <code>data/gym_trainers.json</code>; "
        "caps: <code>modpack/config/rctmod-server.toml</code>.</li><li>%s.</li>"
        "<li>Generated by <code>tools/challenge_guide.py</code>. Valid page, not proof of in-game behaviour.</li></ul>"
        % names_src,
        "</div></div></main>\n", SCRIPT, "\n"])


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def luminance(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    lin = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(int(c[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


THEMES = (("light", r":root\{"), ("dark", r':root\[data-theme="dark"\]\{'),
          ("dark (system)", r':root:not\(\[data-theme="light"\]\)\{'))


def theme_tokens(css):
    """Every hex token the CSS declares, per theme block: :root, :root[data-theme=dark], and the
    prefers-color-scheme block (each checked, since a page can be shown in any of the three)."""
    pick = lambda blocks: {k: v for b in blocks for k, v in re.findall(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\b", b)}
    light = pick(re.findall(THEMES[0][1] + r"([^}]*)\}", css))
    return [light] + [{**light, **pick(re.findall(rx + r"([^}]*)\}", css))} for _n, rx in THEMES[1:]]


def contrast_problems(css):
    out = []
    for theme, tok in zip([n for n, _rx in THEMES], theme_tokens(css)):
        for pairs, need in ((TEXT_PAIRS, 4.5), (UI_PAIRS, 3.0)):
            for fg, bg in pairs:
                if fg not in tok or bg not in tok:
                    out.append("contrast: the %s theme lacks --%s or --%s" % (theme, fg, bg))
                    continue
                r = contrast(tok[fg], tok[bg])
                if r < need:
                    out.append("contrast: %s --%s on --%s is %.2f, under %.1f" % (theme, fg, bg, r, need))
    return out


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
    out += contrast_problems(css)
    for a in re.findall(r'\b(?:id|href)="#?([^"]*)"', page):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", a):
            out.append("an anchor that is not a bare token: %r" % a)
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
    print("wrote %s (%d bytes): %d splits (%s), %d unplaced; live roster normal=%d challenge=%d "
          "identical=%d neither=%d; names from %s%s"
          % (out, len(page.encode("utf-8")), len(model["splits"]),
             ", ".join("%s:%d" % (s["key"], len(s["fights"])) for s in model["splits"]), len(model["unplaced"]),
             t["normal"], t["challenge"], t["both"], t[None],
             jar or "ids (no jar)", ("; %d ids not in the jar" % len(names.missing)) if names.missing else ""))
    for f in model["unplaced"]:
        print("UNPLACED %s: %s" % (f["rec"]["id"], f["reason"]))


if __name__ == "__main__":
    main()
