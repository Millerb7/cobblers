#!/usr/bin/env python
"""The players' battle guide: one self-contained HTML page of every trainer fight, docs/player/battles.html.

For Nuzlocke and Challenge players planning their fights (the owner, 2026-10-09: "That is how challenge hacks ship
documentation"). One file, no server, no network: inline CSS and a few lines of inline JavaScript for the
Normal / Challenge switch and the theme; without JavaScript both teams are shown, labelled.

EVERY FACT IS READ FROM THE LIVE DATA, never from a design document:

  teams         what the trainer files hold: tools/route_trainers.files(), the emitter's own in-memory pack
                (build/datapacks/cobblers_trainers), data/rctmod/trainers/<id>.json for Normal and <id>_challenge.json
                for Challenge (tools/challenge_mode.py). Species, level, ability, held item, nature, moves.
  sight         the same pack's mob files: forceBattleOnSight and forceBattleMaxDistance
  who           data/trainers.json display_name and class (never dialogue, lesson or story)
  where         data/route_trainers.json, data/late_route_trainers.json (Routes 1-8), data/vr_trainers.json (Victory
                Road), data/gym_junior_trainers.json (the juniors); the leaders' spawners through
                tools/challenge_mode.normal_seat / challenge_seat (data/gym_buildings, data/gym_interiors.json,
                data/challenge_mode.json); place names from data/routes.json, data/towns.json, data/gym_buildings
                and data/gym_interiors.json
  order         route trainers by their seat's measured walked_distance along the route (Victory Road by
                route_progress); juniors by the order a player first comes surely into each one's sight, measured
                by tools/gym_trainers_audit.audit() from the replayed hall builds (review N100: trainer_order is
                wrong in gyms 4, 6 and 7). Sections follow rctmod's own kanto chain.
  level caps    rctmod's rule (LevelUtils, as tools/challenge_mode_audit.py models it): the cap while heading to the
                next required trainer is max(initialLevelCap, that trainer's strongest member + relativeLevelCap,
                and the same over its requiredDefeats), from modpack/config/rctmod-server.toml, upstream's kanto
                chain (the offline server snapshot's COBBLEVERSE-RCT zip) and our cobblers_challenge series
  the fight     a leader's own fields in data/trainers.json, quoted: modes.<mode>.strategy, ace_species and
                ace_math_change, availability_contract.answers, and Challenge's open_line and line_obviousness.
                The data has no field named "engine" or "answer"; the page says so instead of paraphrasing
  names, types  the Cobblemon 1.8 jar in the offline snapshot: assets/cobblemon/lang/en_us.json (the names a player
                sees), data/cobblemon/species (types), and its Pokemon Showdown moves.js (move type and category)

Where two data files disagree, or a data file and the measured order, the page shows the trainer files and lists
the disagreement under "Data notes".

ART. None. The Cobblemon jar's Pokemon textures are UV skins for 3D models, not portraits, and its art (including
gui/types.png) is under a Creative Commons licence, not an MIT-style one, so a committed page cannot carry it
(CLAUDE.md). The type badges are drawn in CSS.

WHAT IT LEAVES OUT on purpose: legendaries, resident encounters, Mega dens, shrines, caches, portals, quests, story
and dialogue; the Gastly mansion's five Channelers (data/mansion_guardians.json), the Compact HQ tower's seven
(data/hq_trainers.json) and Heaven's Arena's exam teams (data/arena_trainers.json, unseated); Cobbleverse's own
roaming trainers and anything a donor template places. In-game behaviour is not verified by this page.

  python tools/player_guide_battles.py            # write docs/player/battles.html
  python tools/player_guide_battles.py --check    # regenerate in memory; exit 1 if the file differs
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

OUT = ROOT / "docs" / "player" / "battles.html"
MODS = Path(os.environ.get("COBBLERS_SNAPSHOT_MODS")
            or "C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods")
JAR_GLOB = "Cobblemon-fabric-1.8*.jar"
SHOWDOWN_MOVES = "assets/cobblemon/showdown/node_modules/pokemon-showdown/data/moves.js"
ENTRY = re.compile(r"^  (\w+): \{\n(.*?)^  \},?$", re.S | re.M)
TRAINERS = "data/rctmod/trainers/%s.json"
MOBS = "data/rctmod/mobs/trainers/single/%s.json"
CLASS_LABEL = {"route": "Route trainer", "optional_route": "Optional, off the road", "gym_trainer": "Gym trainer",
               "gym_leader": "Gym Leader", "elite_four": "Elite Four", "champion": "Champion"}
# the eighteen types' badge colours (the familiar palette); text colour is chosen for contrast below
TYPE_COLOURS = {"normal": "#9fa19f", "fire": "#e62829", "water": "#2980ef", "electric": "#fac000",
                "grass": "#3fa129", "ice": "#3dcef3", "fighting": "#ff8000", "poison": "#9141cb",
                "ground": "#915121", "flying": "#81b9ef", "psychic": "#ef4179", "bug": "#91a119",
                "rock": "#afa981", "ghost": "#704170", "dragon": "#5060e1", "dark": "#624d4e",
                "steel": "#60a1b8", "fairy": "#ef70ef"}
CATEGORY = {"Physical": "Phys", "Special": "Spec", "Status": "Status"}


def doc(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def esc(s):
    return html.escape(str(s), quote=True)


def pretty(slug):
    return " ".join(w.capitalize() for w in re.split(r"[_\s-]+", str(slug or "").split(":")[-1]) if w)


def compact(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").split(":")[-1].lower())


# ------------------------------------------------------------------------------------------------ names and types


class Dex:
    """Display names and types from the Cobblemon jar. Anything it cannot name is title-cased and counted."""

    def __init__(self, jar):
        self.jar = Path(jar)
        z = zipfile.ZipFile(self.jar)
        self.lang = json.loads(z.read("assets/cobblemon/lang/en_us.json").decode("utf-8"))
        self.types = {}
        for n in z.namelist():
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                s = json.loads(z.read(n).decode("utf-8"))
                t = [s.get("primaryType"), s.get("secondaryType")]
                self.types[n.rsplit("/", 1)[1][:-5]] = [x.lower() for x in t if x]
        self.moves = {}
        for m in ENTRY.finditer(z.read(SHOWDOWN_MOVES).decode("utf-8", "replace")):
            typ = re.search(r'^    type: "([^"]*)"', m.group(2), re.M)
            cat = re.search(r'^    category: "([^"]*)"', m.group(2), re.M)
            if typ:
                self.moves[m.group(1)] = (typ.group(1).lower(), cat.group(1) if cat else None)
        if len(self.types) < 500 or len(self.moves) < 500:
            raise SystemExit("read only %d species and %d moves from %s" % (len(self.types), len(self.moves), jar))
        self.missing = set()

    def _name(self, key, ident):
        v = self.lang.get(key)
        if v is None:
            self.missing.add(key)
            return pretty(ident)
        return v

    def species(self, ident):
        t = self.types.get(ident)
        if t is None:
            self.missing.add("species:" + ident)
        return self._name("cobblemon.species.%s.name" % ident, ident), t or []

    def move(self, ident):
        typ, cat = self.moves.get(compact(ident), (None, None))
        if typ is None:
            self.missing.add("move type:" + ident)
        return self._name("cobblemon.move.%s" % compact(ident), ident), typ, cat

    def ability(self, ident):
        return self._name("cobblemon.ability.%s" % compact(ident), ident)

    def item(self, ident):
        ns, _, path = str(ident).rpartition(":")
        return self._name("item.%s.%s" % (ns or "cobblemon", path), path)

    def nature(self, ident):
        return self._name("cobblemon.nature.%s" % compact(ident), ident)

    def type_name(self, t):
        return self._name("cobblemon.type.%s" % t, t)


def find_jar(explicit=None):
    if explicit:
        return Path(explicit)
    hits = sorted(MODS.glob(JAR_GLOB)) if MODS.is_dir() else []
    if not hits:
        raise SystemExit("no %s in %s: pass --jar, or set COBBLERS_SNAPSHOT_MODS to the offline snapshot's mods "
                         "folder" % (JAR_GLOB, MODS))
    return hits[0]


# ------------------------------------------------------------------------------------------------ inputs


def junior_order(pack):
    """{gym: [junior ids in the order met]}, measured by tools/gym_trainers_audit.audit() against the trainers pack
    written from `pack` (so the sight it measures is this data's, not an older build's)."""
    import gym_trainers_audit as GA
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "datapacks" / "cobblers_trainers"
        for rel, content in pack.items():
            f = base / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            text = "\n".join(content) + "\n" if isinstance(content, list) else json.dumps(content, indent=2)
            f.write_text(text, encoding="utf-8", newline="\n")
        miss = GA.inputs_missing(tmp)
        if miss:
            raise SystemExit("cannot measure the juniors' meet order: %s" % miss)
        report = GA.audit(build=tmp)
    return {g: [o[0] for o in (r.get("info") or {}).get("order") or []] for g, r in report["gyms"].items()}


def level_caps(pack, bosses):
    """{trainer id: cap while heading to it} for both modes' chains, and the in-game series titles."""
    import challenge_mode_audit as CA
    import challenge_mode as CM
    up = CA.Upstream()
    toml = ROOT / "modpack" / "config" / "rctmod-server.toml"
    initial = CA.toml_value(toml, "initialLevelCap")
    cfg_rel = CA.toml_value(toml, "relativeLevelCap") or 0
    kanto = sorted(up.series_members("kanto"))
    order = CA.chain_order({u: up.mobs[u] for u in kanto})
    if order is None or set(order) != set(bosses):
        raise SystemExit("rctmod's kanto series is not one chain of our thirteen overrides: %s" % order)
    top = lambda tid: max(m["level"] for m in pack[TRAINERS % tid]["team"])
    sfx = CM.suffix()
    series = pack["data/rctmod/series/%s.json" % CM.series_id()]
    k_series = up.series_files.get("kanto") or {}
    nlev = {u: CA.trainer_level(u, {v: top(v) for v in order}, {v: up.mobs[v] for v in order},
                                k_series.get("relativeLevelCap"), cfg_rel) for u in order}
    cmobs = {u + sfx: pack[MOBS % (u + sfx)] for u in order}
    clev = {u + sfx: CA.trainer_level(u + sfx, {v + sfx: top(v + sfx) for v in order}, cmobs,
                                      series.get("relativeLevelCap"), cfg_rel) for u in order}
    ncurve = CA.cap_curve(order, nlev, k_series.get("initialLevelCap", initial))
    ccurve = CA.cap_curve([u + sfx for u in order], clev, series.get("initialLevelCap", initial))
    caps = {"normal": dict(zip(order, ncurve)), "challenge": dict(zip(order, ccurve))}
    titles = {"normal": text_of(k_series.get("title")) or "kanto", "challenge": text_of(series.get("title"))}
    rule = {"initial": initial, "relative": cfg_rel, "after_champion": ncurve[-1]}
    return order, caps, titles, rule


def text_of(v):
    if isinstance(v, dict):
        return v.get("literal") or v.get("translate") or ""
    return v or ""


# ------------------------------------------------------------------------------------------------ the model


def mon(dex, m):
    name, types = dex.species(m["species"])
    moves = [dex.move(x) for x in m.get("moveset") or []]
    return {"species": m["species"], "name": name, "types": types, "level": m["level"],
            "ability": dex.ability(m["ability"]) if m.get("ability") else None,
            "item": dex.item(m["heldItem"]) if m.get("heldItem") else None,
            "nature": dex.nature(m["nature"]) if m.get("nature") else None, "moves": moves}


def collect(jar=None):
    import route_trainers as RT
    import challenge_mode as CM
    dex = Dex(find_jar(jar))
    pack = RT.files()
    sfx = CM.suffix()
    recs = {r["id"]: r for r in doc("data/trainers.json")["trainers"]}
    routes = {r["id"]: r for r in doc("data/routes.json")["routes"]}
    towns = {t["id"]: t.get("name") or t.get("display_name") for t in doc("data/towns.json")["towns"]}
    notes = []

    def team(tid):
        f = pack.get(TRAINERS % tid)
        return [mon(dex, m) for m in f["team"]] if f else None

    def sight(tid):
        mob = pack.get(MOBS % tid) or {}
        if mob.get("forceBattleOnSight"):
            return "Battles on sight within %g blocks" % mob.get("forceBattleMaxDistance", 0)
        return "Talk to battle" if mob else None

    def fight(rec, tid, seat, place, extra=None):
        n = team(tid)
        c = team(tid + sfx)
        if n is None:
            raise SystemExit("%s: no trainer file %s in the emitted pack" % (rec["id"], TRAINERS % tid))
        f = {"id": rec["id"], "name": rec["display_name"], "class": CLASS_LABEL.get(rec["class"], pretty(rec["class"])),
             "teams": {"normal": n, "challenge": c}, "same": c is not None and pack[TRAINERS % tid]["team"] ==
             pack[TRAINERS % (tid + sfx)]["team"], "seat": seat, "place": place, "sight": sight(tid)}
        f.update(extra or {})
        return f

    # -- rules every file shares: stated once, and a trainer that breaks them is named
    rules = {}
    for rel, f in pack.items():
        if rel.startswith("data/rctmod/trainers/"):
            rules.setdefault(json.dumps({"rules": f.get("battleRules"), "bag": f.get("bag"),
                                         "format": f.get("battleFormat", "GEN_9_SINGLES")}, sort_keys=True), []
                             ).append(rel.rsplit("/", 1)[1][:-5])
    if len(rules) != 1:
        notes.append("Not every trainer file plays by the same rules: %s" % "; ".join(
            "%s for %d" % (k, len(v)) for k, v in sorted(rules.items())))
    shared = json.loads(next(iter(sorted(rules))))

    # -- held items the Cobblemon jar has no item for: what such a Pokemon holds in game is not known from here
    bad_items = {}
    for rel, f in sorted(pack.items()):
        if rel.startswith("data/rctmod/trainers/"):
            for m in f["team"]:
                it = m.get("heldItem")
                ns, _, path = str(it or "").rpartition(":")
                if it and "item.%s.%s" % (ns or "cobblemon", path) not in dex.lang:
                    bad_items.setdefault(it, []).append("%s (%s)" % (rel.rsplit("/", 1)[1][:-5], m["species"]))
    for it, where in sorted(bad_items.items()):
        notes.append("Held item %r: the Cobblemon jar has no item with that id, so what it becomes in game is not "
                     "verified. Carried by %s." % (it, ", ".join(where)))

    # -- route seats, by the measured distance walked along the route
    by_route = {}
    for name in ("data/route_trainers.json", "data/late_route_trainers.json"):
        for s in doc(name)["trainers"]:
            r = recs[s["id"]]
            by_route.setdefault(r["route_id"], []).append((s["walked_distance"], s, r))
    for s in doc("data/vr_trainers.json")["trainers"]:
        r = recs[s["id"]]
        by_route.setdefault(r["route_id"], []).append((s["route_progress"], s, r))
    for rid, lst in by_route.items():
        lst.sort(key=lambda x: (x[0], x[1]["id"]))
        said = [x[2].get("trainer_order") for x in lst]
        if said != sorted(said):
            notes.append("%s: trainer_order in data/trainers.json is %s, but the seats are met in the order %s "
                         "(walked distance); the page follows the seats." % (
                             routes[rid]["display_name"], said, [x[1]["id"] for x in lst]))

    def route_fights(rid):
        out = []
        rname = routes[rid]["display_name"]
        for _d, s, r in by_route.get(rid, []):
            place = rname
            if r["class"] == "optional_route":
                place += " (off the road: optional)"
            if "stand_index" in s:
                place += ", stand %d of %d" % (s["stand_index"], len(by_route[rid]))
            out.append(fight(r, r["id"], s["seat"], place))
        return out

    # -- juniors, in the measured order
    met = junior_order(pack)
    jseats = {s["id"]: s for s in doc("data/gym_junior_trainers.json")["trainers"]}
    halls = {}
    for f in sorted((ROOT / "data" / "gym_buildings").glob("gym*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        halls[g["id"]] = (g.get("name"), g.get("settlement"))
    # Misty's hall is the donor template's island (data/gym_junior_trainers.json gyms.gym2), with no data/gym_buildings
    # record; data/gym_interiors.json's gym2 title names the carved cistern under it, not the hall the juniors and
    # Misty stand in, so the page names it by its leader instead
    for g in doc("data/gym_interiors.json")["gyms"]:
        if g.get("built") and g["id"] not in halls:
            halls[g["id"]] = ("%s's gym" % g["leader_name"] if g.get("leader_name") else None, g.get("settlement"))
    for gym, ids in sorted(met.items()):
        said = sorted(ids, key=lambda t: (recs[t].get("trainer_order") or 0, t))
        if said != ids:
            notes.append("Gym %s's juniors: trainer_order in data/trainers.json (from docs/story/TRAINER_RULES.json) "
                         "puts them %s; walking the hall meets them %s (measured by tools/gym_trainers_audit.py). "
                         "The page follows the walk." % (gym[3:], " < ".join(t.split("_", 1)[1] for t in said),
                                                         " < ".join(t.split("_", 1)[1] for t in ids)))
    unmet = sorted(set(jseats) - {t for v in met.values() for t in v})
    if unmet:
        raise SystemExit("juniors with no measured meet order: %s" % unmet)

    def hall_place(gym, room=None):
        name, town = halls.get(gym, (None, None))
        bits = [b for b in (pretty(room) if room else None, name, towns.get(town)) if b]
        return ", ".join(bits)

    # -- the thirteen bosses and their caps
    over, held = RT.overrides()
    if held:
        notes.append("Held, nothing emitted: %s" % ", ".join(t for t, _w in held))
    bosses = CM.boss_ids(over)
    order, caps, titles, rule = level_caps(pack, [u for _r, u, _c, _e in bosses])
    summary = {e["id"]: e for n in ("data/gym_trainers.json", "data/league_trainers.json") for e in doc(n)["trainers"]}
    contract = doc("data/trainers.json")["generation_contract"]
    boss = {}
    for rec, up, cid, entry in bosses:
        n_at, c_at = CM.normal_seat(up, entry), CM.challenge_seat(up, entry)
        gym = "gym%d" % rec["order"] if rec["class"] == "gym_leader" else None
        place = hall_place(gym) if gym else towns.get("league", "The League")
        if gym and not halls.get(gym):
            place = towns.get("%s_town" % gym, gym)
        asks = {}
        for mode, tid in (("normal", up), ("challenge", cid)):
            md = rec["modes"][mode]
            tm = pack[TRAINERS % tid]["team"]
            ace = [m for m in tm if m["species"] == md.get("ace_species")]
            if not ace:
                notes.append("%s (%s): the record names %s as the ace, and the team does not carry it."
                             % (rec["display_name"], mode, md.get("ace_species")))
            asks[mode] = {"strategy": md.get("strategy"), "ace": dex.species(md["ace_species"])[0]
                          if md.get("ace_species") else None, "ace_level": ace[0]["level"] if ace else None,
                          "ace_note": md.get("ace_math_change"),
                          "open_line": [dex.species(s)[0] for s in md.get("open_line") or []],
                          "obviousness": md.get("line_obviousness")}
        av = rec.get("availability_contract") or {}
        s = summary.get(rec["id"]) or {}
        nt = pack[TRAINERS % up]["team"]
        lv = [m["level"] for m in nt]
        top_m = max(nt, key=lambda m: m["level"])
        said = []
        if s.get("members") is not None and s["members"] != len(nt):
            said.append("%d members" % s["members"])
        if s.get("levels") and list(s["levels"]) != [min(lv), max(lv)]:
            said.append("levels %d-%d" % tuple(s["levels"]))
        if s.get("ace") and (s["ace"].get("level") != max(lv)
                             or s["ace"].get("species") not in [m["species"] for m in nt if m["level"] == max(lv)]):
            said.append("ace %s Lv %s" % (pretty(s["ace"].get("species")), s["ace"].get("level")))
        if said:
            src = "data/gym_trainers.json" if rec["class"] == "gym_leader" else "data/league_trainers.json"
            notes.append("%s: %s says %s; the Normal trainer file holds %d members at levels %d-%d, strongest %s "
                         "Lv %d. The page shows the trainer file." % (rec["display_name"], src, ", ".join(said),
                                                                      len(nt), min(lv), max(lv),
                                                                      dex.species(top_m["species"])[0], max(lv)))
        if rec["class"] == "gym_leader":
            want = contract["gym_ace_levels"][rec["order"] - 1]
            for mode, tid in (("Normal", up), ("Challenge", cid)):
                got = max(m["level"] for m in pack[TRAINERS % tid]["team"])
                if got != want:
                    notes.append("%s (%s) tops out at Lv %d; generation_contract.gym_ace_levels says %d."
                                 % (rec["display_name"], mode, got, want))
        boss[up] = fight(rec, up, n_at, place, {
            "seat_challenge": c_at, "theme": s.get("theme"), "asks": asks,
            "answers": av.get("answers") or [], "answers_status": av.get("status"),
            "cap": {m: caps[m][up] for m in caps}})
        # the Challenge leader is a second id: its file, not the Normal one, is the Challenge team
        boss[up]["teams"]["challenge"] = team(cid)
        boss[up]["same"] = pack[TRAINERS % up]["team"] == pack[TRAINERS % cid]["team"]
        boss[up]["sight"] = None

    for k, want in (("route_trainers", sum(1 for r in recs.values() if r.get("route_id"))),
                    ("gym_trainers", sum(1 for r in recs.values() if r["class"] == "gym_trainer"))):
        if contract.get(k) != want:
            notes.append("data/trainers.json generation_contract.%s says %s; the roster holds %d."
                         % (k, contract.get(k), want))

    # -- sections, in rctmod's chain order
    leg_to = {r["to_town"]: rid for rid, r in routes.items()}
    sections = []
    gym_ups = [u for u in order if recs_for(bosses, u)["class"] == "gym_leader"]
    for u in gym_ups:
        rec = recs_for(bosses, u)
        k = rec["order"]
        gym = "gym%d" % k
        rid = leg_to.get("%s_town" % gym)
        parts = []
        if rid:
            parts.append((routes[rid]["display_name"], route_fights(rid)))
        juniors = [fight(recs[t], t, jseats[t]["seat"], hall_place(gym, jseats[t].get("room"))) for t in met.get(gym, [])]
        if juniors:
            hn = halls.get(gym, (None, None))
            parts.append(("Inside %s" % (hn[0] or "the gym"), juniors))
        parts.append(("The Gym Leader", [boss[u]]))
        sections.append({"id": "gym-%d" % k, "title": "Gym %d: %s" % (k, rec["display_name"]),
                         "sub": ", ".join(b for b in (boss[u].get("theme"), towns.get("%s_town" % gym)) if b),
                         "cap": boss[u]["cap"], "parts": parts})
    vr = leg_to.get("league")
    first_e4 = [u for u in order if u not in gym_ups][0]
    if vr:
        sections.append({"id": "victory-road", "title": routes[vr]["display_name"].split(" \u2014 ")[0],
                         "sub": routes[vr]["display_name"].split(" \u2014 ")[-1], "cap": boss[first_e4]["cap"],
                         "parts": [(routes[vr]["display_name"], route_fights(vr))]})
    league = [boss[u] for u in order if u not in gym_ups]
    sections.append({"id": "league", "title": "The Elite Four and the Champion", "sub": towns.get("league", ""),
                     "cap": None, "parts": [("In order", league)]})
    covered = {f["id"] for s in sections for _t, fs in s["parts"] for f in fs}
    missing = sorted(set(recs) - covered)
    if missing:
        raise SystemExit("records in data/trainers.json with no place on the page: %s" % missing)
    return {"sections": sections, "notes": notes, "titles": titles, "rule": rule, "shared": shared,
            "jar": dex.jar.name, "missing": sorted(dex.missing), "count": len(covered)}


def recs_for(bosses, up):
    return next(r for r, u, _c, _e in bosses if u == up)


# ------------------------------------------------------------------------------------------------ rendering


def text_colour(hexc):
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return "#111" if (lum + 0.05) / 0.05 > 1.05 / (lum + 0.05) else "#fff"


CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1f23;--muted:#5d636d;--rule:#d9d6cc;--accent:#b2402f;--accent-ink:#fff;
--soft:#efece4;--warn:#fff6d8;--warn-rule:#d6a400;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15171b;--card:#1f2228;--ink:#e8e6e1;
--muted:#a3a8b1;--rule:#353a43;--accent:#e0705c;--accent-ink:#15171b;--soft:#262a31;--warn:#2d2816;--warn-rule:#a07c10;
color-scheme:dark}}
:root[data-theme=dark]{--bg:#15171b;--card:#1f2228;--ink:#e8e6e1;--muted:#a3a8b1;--rule:#353a43;--accent:#e0705c;
--accent-ink:#15171b;--soft:#262a31;--warn:#2d2816;--warn-rule:#a07c10;color-scheme:dark}
*{box-sizing:border-box}
html{scroll-padding-top:64px}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}
.bar{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--rule);padding:8px 16px;
display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.bar b{font-size:1.05rem;margin-right:auto}
.seg{display:inline-flex;border:1px solid var(--rule);border-radius:999px;overflow:hidden}
.seg button{font:inherit;font-size:.9rem;color:var(--ink);background:var(--card);border:0;padding:5px 14px;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--accent);color:var(--accent-ink);font-weight:600}
.nojs .seg{display:none}
main{max-width:1180px;margin:0 auto;padding:12px 16px 60px}
h1{font-size:1.7rem;margin:14px 0 4px}
h2{font-size:1.35rem;margin:34px 0 4px;padding-bottom:4px;border-bottom:2px solid var(--accent)}
h2 small{font-weight:400;color:var(--muted);font-size:.95rem;margin-left:8px}
h3{font-size:1.05rem;margin:20px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.lead{color:var(--muted);margin:0 0 12px}
.box{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:10px 14px;margin:10px 0}
.box.warn{background:var(--warn);border-left:5px solid var(--warn-rule)}
.box p,.box ul{margin:4px 0}
.toc ol{columns:2 260px;margin:4px 0;padding-left:22px}
.toc li{break-inside:avoid;margin:2px 0}
.cap{display:inline-block;background:var(--soft);border:1px solid var(--rule);border-radius:8px;padding:3px 10px;
margin:6px 0 2px;font-size:.95rem}
.tr{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:10px 12px;margin:0 0 12px}
.tr.boss{border:2px solid var(--accent)}
.th{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px}
.th .no{color:var(--muted);font-variant-numeric:tabular-nums;font-size:.85rem}
.th h4{margin:0;font-size:1.1rem}
.tag{font-size:.78rem;border:1px solid var(--rule);border-radius:999px;padding:0 8px;color:var(--muted)}
.loc{margin:2px 0 8px;color:var(--muted);font-size:.9rem}
.loc code{color:var(--ink);background:var(--soft);border-radius:4px;padding:0 5px;font-size:.88rem}
.ml{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:6px 0 4px}
.team{display:grid;grid-template-columns:repeat(auto-fill,minmax(205px,1fr));gap:8px}
.mon{border:1px solid var(--rule);border-radius:8px;padding:6px 8px;background:var(--bg)}
.mh{display:flex;justify-content:space-between;gap:6px;align-items:baseline}
.mh b{font-size:1rem}
.lv{font-variant-numeric:tabular-nums;font-weight:600}
.ty{margin:2px 0 4px}
.t{display:inline-block;border-radius:4px;padding:0 6px;font-size:.72rem;font-weight:700;text-transform:uppercase;
letter-spacing:.03em;line-height:1.5;margin-right:3px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:0 8px;margin:0;font-size:.85rem}
.kv dt{color:var(--muted)}
.kv dd{margin:0}
.mv{list-style:none;margin:4px 0 0;padding:0;font-size:.88rem}
.mv li{display:flex;gap:6px;align-items:baseline}
.mv .t{min-width:3.4em;text-align:center;font-size:.66rem}
.mv small{color:var(--muted);margin-left:auto}
.asks{background:var(--soft);border-radius:8px;padding:8px 12px;margin:8px 0 0}
.asks dl{margin:0}
.asks dt{font-weight:700;font-size:.85rem;margin-top:6px}
.asks dd{margin:0}
.asks .f{font-weight:400;color:var(--muted);font-size:.78rem}
.js[data-mode=normal] .m-c,.js[data-mode=challenge] .m-n{display:none}
.nojs .cv.m-n::before{content:"Normal "}.nojs .cv.m-c::before{content:" / Challenge "}
.notes li{margin:4px 0}
footer{color:var(--muted);font-size:.85rem;border-top:1px solid var(--rule);margin-top:40px;padding-top:10px}
@media (max-width:560px){body{font-size:14px}.bar{padding:6px 10px}main{padding:8px 10px 40px}
.team{grid-template-columns:1fr}.tr{padding:8px}h2 small{display:block;margin:0}}
@media print{.bar{position:static}.seg{display:none}}
"""

SCRIPT_HEAD = ("(function(){var d=document.documentElement;d.className='js';var m='normal',t='';"
               "try{m=localStorage.getItem('cobblers-mode')||'normal';t=localStorage.getItem('cobblers-theme')||''}"
               "catch(e){}d.setAttribute('data-mode',m==='challenge'?'challenge':'normal');"
               "if(t)d.setAttribute('data-theme',t)})();")
SCRIPT_BODY = ("(function(){var d=document.documentElement;"
               "function sync(){var m=d.getAttribute('data-mode');document.querySelectorAll('[data-set-mode]')"
               ".forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-set-mode')===m)})}"
               "document.querySelectorAll('[data-set-mode]').forEach(function(b){b.addEventListener('click',function(){"
               "var m=b.getAttribute('data-set-mode');d.setAttribute('data-mode',m);"
               "try{localStorage.setItem('cobblers-mode',m)}catch(e){}sync()})});"
               "var tb=document.getElementById('theme');tb.addEventListener('click',function(){"
               "var cur=d.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');"
               "var n=cur==='dark'?'light':'dark';d.setAttribute('data-theme',n);"
               "try{localStorage.setItem('cobblers-theme',n)}catch(e){}});sync()})();")


def badge(dex_type, label=None):
    return '<span class="t t-%s">%s</span>' % (esc(dex_type), esc(label or dex_type))


def render_mon(m):
    out = ['<div class="mon"><div class="mh"><b>%s</b><span class="lv">Lv %d</span></div>' % (esc(m["name"]), m["level"])]
    out.append('<div class="ty">%s</div>' % ("".join(badge(t) for t in m["types"]) or '<span class="tag">type unknown</span>'))
    kv = [("Ability", m["ability"] or "not set in the file"), ("Item", m["item"] or "none")]
    if m["nature"]:
        kv.append(("Nature", m["nature"]))
    out.append('<dl class="kv">%s</dl>' % "".join("<dt>%s</dt><dd>%s</dd>" % (esc(k), esc(v)) for k, v in kv))
    mv = []
    for name, typ, cat in m["moves"]:
        chip = badge(typ, typ[:3]) if typ else '<span class="t">?</span>'
        mv.append("<li>%s<span>%s</span><small>%s</small></li>" % (chip, esc(name), esc(CATEGORY.get(cat, cat or ""))))
    out.append('<ul class="mv">%s</ul></div>' % "".join(mv))
    return "".join(out)


def render_team(team, label, cls, only=True):
    return ('<div class="%s"><div class="ml%s">%s</div><div class="team">%s</div></div>'
            % (cls, " only" if only else "", esc(label), "".join(render_mon(m) for m in team)))


def coords(seat):
    return "<code>%d %d %d</code>" % tuple(seat)


def render_asks(f):
    out = ['<div class="asks"><b>What the fight asks</b> <span class="f">(the record\'s own fields in '
           'data/trainers.json, quoted)</span>']
    for mode, cls in (("normal", "m-n"), ("challenge", "m-c")):
        a = f["asks"][mode]
        rows = []
        if a["strategy"]:
            rows.append(("Plan", "strategy", esc(a["strategy"])))
        if a["ace"]:
            ace = esc(a["ace"]) + (" (Lv %d)" % a["ace_level"] if a["ace_level"] else "")
            if a["ace_note"]:
                ace += ": " + esc(a["ace_note"])
            rows.append(("Ace", "ace_species, ace_math_change", ace))
        if f["answers"]:
            st = " <span class=\"f\">(status: %s)</span>" % esc(f["answers_status"]) if f["answers_status"] else ""
            rows.append(("Answers in reach", "availability_contract.answers, both modes",
                         esc(", ".join(f["answers"])) + st))
        if a["open_line"]:
            rows.append(("An open line", "open_line", esc(", ".join(a["open_line"]))))
        if a["obviousness"]:
            rows.append(("How visible that line is", "line_obviousness", esc(a["obviousness"])))
        out.append('<div class="%s"><div class="ml">%s</div><dl>%s</dl></div>' % (
            cls, "Normal" if mode == "normal" else "Challenge",
            "".join('<dt>%s <span class="f">%s</span></dt><dd>%s</dd>' % (esc(k), esc(src), v) for k, src, v in rows)))
    out.append("</div>")
    return "".join(out)


def render_fight(f, no):
    boss = "asks" in f
    out = ['<article class="tr%s" id="t-%s"><div class="th"><span class="no">#%d</span><h4>%s</h4>'
           '<span class="tag">%s</span>' % (" boss" if boss else "", esc(f["id"]), no, esc(f["name"]),
                                             esc(f["class"] + (", " + f["theme"] if f.get("theme") else "")))]
    if f.get("sight"):
        out.append('<span class="tag">%s</span>' % esc(f["sight"]))
    if boss:
        out.append('<span class="tag">Level cap here: <b class="cv m-n">%d</b><b class="cv m-c">%d</b></span>'
                   % (f["cap"]["normal"], f["cap"]["challenge"]))
    out.append("</div>")
    if boss and tuple(f["seat"]) != tuple(f["seat_challenge"]):
        out.append('<p class="loc">%s, <span class="m-n">Normal spawner %s</span> <span class="m-c">Challenge '
                   'spawner %s</span></p>' % (esc(f["place"]), coords(f["seat"]), coords(f["seat_challenge"])))
    else:
        out.append('<p class="loc">%s, %s%s</p>' % (esc(f["place"]), coords(f["seat"]),
                                                    " (spawner)" if boss else ""))
    if f["same"] or f["teams"]["challenge"] is None:
        label = "Same team in both modes" if f["same"] else "Normal team (no Challenge team)"
        out.append(render_team(f["teams"]["normal"], label, "", only=False))
    else:
        out.append(render_team(f["teams"]["normal"], "Normal team", "m-n"))
        out.append(render_team(f["teams"]["challenge"], "Challenge team", "m-c"))
    if boss:
        out.append(render_asks(f))
    out.append("</article>")
    return "".join(out)


def render(model):
    css = CSS + "".join(".t-%s{background:%s;color:%s}" % (t, c, text_colour(c)) for t, c in TYPE_COLOURS.items())
    secs = model["sections"]
    count = lambda s: sum(len(fs) for _t, fs in s["parts"])
    toc = []
    for s in secs:
        cap = (' <span class="lead">(cap <span class="cv m-n">%d</span><span class="cv m-c">%d</span>)</span>'
               % (s["cap"]["normal"], s["cap"]["challenge"]) if s["cap"] else "")
        toc.append('<li><a href="#%s">%s</a>, %d fights%s</li>' % (s["id"], esc(s["title"]), count(s), cap))
    sh = model["shared"]
    rules = ("Every trainer file here plays %s, uses no items in battle (maxItemUses %s, bag %s), does not heal you "
             "(healPlayers %s) and does not scale anyone's levels (adjustPlayerLevels %s, adjustNPCLevels %s)."
             % ("singles" if sh["format"] == "GEN_9_SINGLES" else esc(sh["format"]),
                sh["rules"].get("maxItemUses"), "empty" if not sh["bag"] else esc(json.dumps(sh["bag"])),
                str(sh["rules"].get("healPlayers")).lower(), str(sh["rules"].get("adjustPlayerLevels")).lower(),
                str(sh["rules"].get("adjustNPCLevels")).lower()))
    ru = model["rule"]
    body = []
    body.append('<div class="bar"><b>Cobblers: trainer battles</b>'
                '<span class="seg" role="group" aria-label="Difficulty">'
                '<button type="button" data-set-mode="normal" aria-pressed="true">Normal</button>'
                '<button type="button" data-set-mode="challenge" aria-pressed="false">Challenge</button></span>'
                '<span class="seg"><button type="button" id="theme" aria-label="Switch light or dark">Light / dark'
                '</button></span><a href="#contents">Contents</a></div><main>')
    body.append("<h1>Every trainer fight, in the order you meet them</h1>")
    body.append('<p class="lead">%d trainers: each gym\'s route, its juniors and its leader, then Victory Road, the '
                'Elite Four and the Champion. The switch at the top changes every team on the page between '
                '<b>Normal</b> (in game: %s) and <b>Challenge</b> (in game: %s). Coordinates are block positions '
                '(x y z).</p>' % (model["count"], esc(model["titles"]["normal"]), esc(model["titles"]["challenge"])))
    body.append('<div class="box"><p><b>Level caps.</b> Your Pokemon stop gaining experience at the cap. The cap is '
                'the strongest Pokemon of the next leader you have not beaten, plus %s (rctmod relativeLevelCap); '
                'it is at least %s from the start (initialLevelCap), and %s after the Champion. A trainer refuses '
                'to battle a party over the cap. Each section shows the cap that holds until its leader falls.</p>'
                '<p><b>Rules.</b> %s</p><p><b>Battles on sight</b> means the trainer starts the fight when it sees '
                'you within that distance; <b>Talk to battle</b> means you choose when.</p></div>'
                % (esc(ru["relative"]), esc(ru["initial"]), esc(ru["after_champion"]), rules))
    body.append('<nav class="box toc" id="contents"><b>Contents</b><ol>%s<li><a href="#data-notes">Data notes</a>'
                '</li><li><a href="#not-covered">What this page does not cover</a></li></ol></nav>' % "".join(toc))
    no = 0
    for s in secs:
        body.append('<section id="%s"><h2>%s<small>%s</small></h2>' % (s["id"], esc(s["title"]), esc(s["sub"])))
        if s["cap"]:
            body.append('<div class="cap">Level cap through this section: <b class="cv m-n">%d</b>'
                        '<b class="cv m-c">%d</b></div>' % (s["cap"]["normal"], s["cap"]["challenge"]))
        else:
            body.append('<div class="cap">Each member\'s own cap is on its card.</div>')
        for title, fights in s["parts"]:
            body.append("<h3>%s</h3>" % esc(title))
            for f in fights:
                no += 1
                body.append(render_fight(f, no))
        body.append("</section>")
    notes = model["notes"] or ["None: the data files agree with each other and with the measured order."]
    body.append('<section id="data-notes"><h2>Data notes</h2><p class="lead">Where two data files, or a data file '
                'and a measurement, disagree. The page always shows what the trainer files hold.</p>'
                '<ul class="box notes">%s</ul>' % "".join("<li>%s</li>" % esc(n) for n in notes))
    if model["missing"]:
        body.append('<p class="lead">Names or types the Cobblemon jar did not have (shown title-cased): %s</p>'
                    % esc(", ".join(model["missing"])))
    body.append("</section>")
    body.append('<section id="not-covered"><h2>What this page does not cover</h2><div class="box warn"><ul>'
                "<li>Wild Pokemon, resident and legendary encounters, Mega dens, shrines, caches and portals.</li>"
                "<li>Story, quests and anything a trainer says.</li>"
                "<li>The Gastly mansion's Channelers, the Compact HQ tower's fights and Heaven's Arena's rank-up "
                "exams: left out until it is settled how they are fought.</li>"
                "<li>Cobbleverse's own roaming trainers and any trainer a borrowed building brings with it.</li>"
                "<li>Pokemon art. The pack's only Pokemon images are skins for its 3D models, not pictures, and "
                "Cobblemon's art is licensed in a way this repository cannot republish; the type badges are drawn "
                "instead.</li>"
                "<li>How the fights actually play. This page is generated from the data files; it has not been "
                "checked fight by fight in a running game. Where the game and this page differ, the game is "
                "right: say so.</li></ul></div></section>")
    body.append("<footer>Generated by tools/player_guide_battles.py from data/ and the emitted trainer files "
                "(tools/route_trainers.py), with names and types from %s. Regenerate with "
                "<code>python tools/player_guide_battles.py</code>; do not edit this file by hand.</footer>"
                "</main>" % esc(model["jar"]))
    return ('<!doctype html>\n<html lang="en" class="nojs" data-mode="normal"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>Cobblers: trainer battles</title><script>%s</script><style>%s</style></head><body>\n%s\n"
            "<script>%s</script></body></html>\n" % (SCRIPT_HEAD, css, "\n".join(body), SCRIPT_BODY))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--jar", help="the Cobblemon 1.8 jar (default: the offline snapshot's mods folder)")
    p.add_argument("--check", action="store_true", help="regenerate in memory; exit 1 if the file differs")
    a = p.parse_args(argv)
    model = collect(a.jar)
    text = render(model)
    out = Path(a.out)
    fights = sum(len(fs) for s in model["sections"] for _t, fs in s["parts"])
    if a.check:
        have = out.read_text(encoding="utf-8") if out.is_file() else None
        if have != text:
            print("%s is %s: run python tools/player_guide_battles.py" % (out, "stale" if have else "missing"))
            return 1
        print("%s is current (%d fights, %d data notes)" % (out, fights, len(model["notes"])))
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %s: %d fights in %d sections, %d data notes, %d bytes" % (
        out, fights, len(model["sections"]), len(model["notes"]), len(text.encode("utf-8"))))
    for s in model["sections"]:
        print("  %-34s %s" % (s["title"], ", ".join("%s %d" % (t, len(fs)) for t, fs in s["parts"])))
    if model["missing"]:
        print("  not named by the jar: %s" % ", ".join(model["missing"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
