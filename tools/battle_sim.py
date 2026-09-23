#!/usr/bin/env python
"""A deterministic battle filter for the eight gyms, from data alone. No server, no Minecraft, no play.

It answers one question: is there a structural problem with a gym -- nothing that beats it, or everything that
does. It is NOT a verdict on whether a fight is fun or fair, and it cannot be: see LIMITS below.

Where every number comes from:

  leaders      data/trainers.json, our own authored rosters (species, moveset, ability, held item, nature, level)
  availability docs/story/AVAILABILITY.md, the species a player could have caught before each gym and the wild
               level band they first appear at
  species      the Cobblemon 1.8 jar: data/cobblemon/species/**.json -- types, base stats, the level-up move list
               and the level evolutions
  moves        the Pokemon Showdown data the jar ships and the battle actually runs:
               assets/cobblemon/showdown/node_modules/pokemon-showdown/data/moves.js
  type chart   the same, data/typechart.js. Nothing about types is written down here.
  level cap    base-pack/cobbleverse/config/rctmod-server.toml: initialLevelCap 20, relativeLevelCap 5, so a
               player arrives at each gym capped at exactly that gym's ace level.

LIMITS, and they are large. This models one thing: two Pokemon at full health hitting each other with their best
damaging move until one faints.

  - no switching, so it cannot see a team that wins by pivoting, and it cannot see a gym that punishes one
  - no items in battle, no healing, no revives: a player with twenty potions is not modelled
  - no AI: the leader always picks its own best damaging move, which is better than most AI plays
  - no status moves at all. Every leader's hazards, screens, boosts and debuffs are dropped, so
    stealthrock, scaryface, tearfullook and protect are worth nothing here and are worth a lot in play
  - no secondary effects: no flinch, no burn, no paralysis, no confusion, no critical hits
  - abilities: only sturdy, levitate, moldbreaker, thickfat and filter are modelled. Every other ability,
    including intimidate, drought, chlorophyll and swiftswim, does nothing here
  - held items: only eviolite, life_orb, muscle_band, choice_band, assault_vest and the type-resist berries
    are modelled. focus_sash, weakness_policy, oran_berry, sitrus_berry and leftovers are dynamic and are NOT,
    which understates every leader that holds one
  - IVs 15 and EVs 0 on both sides. Real wild catches roll 0-31 and real trainers may not
  - damage takes the average roll (0.925) and multiplies by accuracy, so a 90% move does 90% of its damage
    every turn rather than missing one turn in ten

So: a species this says loses may well win in play, and a species it says wins may lose to a hazard it cannot
see. Read it for the shape -- how many answers a gym has and how hard they are to find -- not for the result of
any single fight.

  python tools/battle_sim.py                     # the report
  python tools/battle_sim.py --gym 3             # one gym, every candidate listed
  python tools/battle_sim.py --ivs 31            # sensitivity: both sides at perfect IVs
  python tools/battle_sim.py --stones            # allow item evolutions as well as level ones
  python tools/battle_sim.py --markdown docs/story/BATTLE_SIM.md
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
TRAINERS = ROOT / "data" / "trainers.json"
AVAILABILITY = ROOT / "docs" / "story" / "AVAILABILITY.md"
RCT_CONFIG = ROOT / "base-pack" / "cobbleverse" / "config" / "rctmod-server.toml"

JAR_CANDIDATES = [
    Path(r"C:\Users\wnd\Documents\github\cobblers\.claude\worktrees\cobblemon-campaign-setup-64929d"
         r"\experiments\EXP-000-cobblemon-1.8-compat\runtime\server\mods\Cobblemon-fabric-1.8.0+1.21.1.jar"),
    ROOT / "experiments" / "EXP-000-cobblemon-1.8-compat" / "runtime" / "server" / "mods"
    / "Cobblemon-fabric-1.8.0+1.21.1.jar",
]
SHOWDOWN = "assets/cobblemon/showdown/node_modules/pokemon-showdown/data/"

# This tool never decides where anything goes, so the ground rule does not apply to it; it reads no world.
WORLD_READS = set()


class SimError(Exception):
    pass


# ------------------------------------------------------------------ the pack's own data

def find_jar():
    for p in JAR_CANDIDATES:
        if p.is_file():
            return p
    hits = sorted(Path(r"C:\Users\wnd\Documents\github\cobblers").rglob("Cobblemon-fabric-1.8*.jar"))
    if hits:
        return hits[0]
    raise SimError("no Cobblemon 1.8 jar found: species, moves and the type chart all come from it")


def key(name):
    """Nidoran's gender sign, Mr. Mime's stop and Farfetch'd's apostrophe all have to fall out the same way
    on both sides, or a roster entry silently finds no species.

    The gender signs carry meaning and cannot just be stripped: the jar has nidoranf and nidoranm, and dropping
    the sign collapsed two species onto one id that does not exist in it.
    """
    s = (name or "").lower().replace("♀", "f").replace("♂", "m")
    return re.sub(r"[^a-z0-9]", "", s)


def load_pack(jar):
    z = zipfile.ZipFile(jar)
    species = {}
    for n in z.namelist():
        if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
            d = json.loads(z.read(n))
            if d.get("implemented") is False:
                continue
            species[key(d["name"])] = d
    moves = parse_moves(z.read(SHOWDOWN + "moves.js").decode("utf8", "replace"))
    chart = parse_typechart(z.read(SHOWDOWN + "typechart.js").decode("utf8", "replace"))
    return species, moves, chart


# The LAST entry of each Showdown file has no trailing comma. Without the `,?` the water row of the type chart
# was dropped, and every Water defender read as neutral to Electric and Grass (found 2026-09-24).
ENTRY = re.compile(r"^  (\w+): \{\n(.*?)^  \},?$", re.S | re.M)


def parse_moves(text):
    out = {}
    for m in ENTRY.finditer(text):
        mid, body = m.group(1), m.group(2)
        bp = re.search(r"^    basePower: (\d+)", body, re.M)
        cat = re.search(r'^    category: "(\w+)"', body, re.M)
        typ = re.search(r'^    type: "(\w+)"', body, re.M)
        acc = re.search(r"^    accuracy: (\d+|true)", body, re.M)
        if not (cat and typ):
            continue
        out[mid] = {"power": int(bp.group(1)) if bp else 0, "category": cat.group(1), "type": typ.group(1),
                    "accuracy": 100 if (not acc or acc.group(1) == "true") else int(acc.group(1))}
    if len(out) < 500:
        raise SimError("parsed only %d moves from the jar's Showdown data" % len(out))
    return out


def parse_typechart(text):
    out = {}
    for m in ENTRY.finditer(text):
        tid, body = m.group(1), m.group(2)
        taken = re.search(r"damageTaken: \{(.*?)\n    \}", body, re.S)
        if not taken:
            continue
        row = {}
        for k, v in re.findall(r"(\w+): (\d)", taken.group(1)):
            if k[:1].isupper():                       # the lowercase keys are statuses, not types
                row[k] = {0: 1.0, 1: 2.0, 2: 0.5, 3: 0.0}[int(v)]
        out[tid] = row
    if len(out) != 18:
        raise SimError("parsed %d types from the jar's type chart, not the 18 that exist: %s"
                       % (len(out), sorted(out)))
    return out


def effectiveness(chart, move_type, defender_types):
    x = 1.0
    for t in defender_types:
        if not t:
            continue
        row = chart.get(t.lower())
        if row is None:
            raise SimError("no type chart row for %r: a missing row reads as neutral and hides a weakness" % t)
        x *= row.get(move_type.capitalize(), 1.0)
    return x


# ------------------------------------------------------------------ availability

GYM_HEAD = re.compile(r"^## Gym (\d+): (\S+) \((\w+)\)", re.M)
ROW = re.compile(r"^\| ([A-Za-z'\u00e9\u2640\u2642. \-]+?) \| (\d+)-(\d+) \| ([^|]+?) \| ([^|]+?) \|$", re.M)


def parse_availability(path):
    text = path.read_text(encoding="utf-8")
    heads = list(GYM_HEAD.finditer(text))
    out = {}
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[h.end():end]
        rows = []
        for r in ROW.finditer(body):
            name = r.group(1).strip()
            if name.lower() in ("species", "---"):
                continue
            rows.append({"species": name, "lo": int(r.group(2)), "hi": int(r.group(3)),
                         "corridor": r.group(5).strip()})
        out[int(h.group(1))] = {"leader": h.group(2), "theme": h.group(3), "rows": rows}
    if not out:
        raise SimError("parsed no gyms out of %s" % path)
    return out


def level_caps(path):
    """The cap a player arrives at each gym with, from the RCT config and the gym ace levels."""
    txt = path.read_text(encoding="utf-8")
    init = int(re.search(r"^\s*initialLevelCap = (\d+)", txt, re.M).group(1))
    rel = int(re.search(r"^\s*relativeLevelCap = (-?\d+)", txt, re.M).group(1))
    return init, rel


# ------------------------------------------------------------------ building a Pokemon

NATURES = {
    "adamant": ("attack", "special_attack"), "modest": ("special_attack", "attack"),
    "impish": ("defence", "special_attack"), "careful": ("special_defence", "special_attack"),
    "jolly": ("speed", "special_attack"), "timid": ("speed", "attack"),
    "bold": ("defence", "attack"), "calm": ("special_defence", "attack"),
    "brave": ("attack", "speed"), "quiet": ("special_attack", "speed"),
    "relaxed": ("defence", "speed"), "sassy": ("special_defence", "speed"),
    "naughty": ("attack", "special_defence"), "rash": ("special_attack", "special_defence"),
    "lax": ("defence", "special_defence"), "gentle": ("special_defence", "defence"),
    "hasty": ("speed", "defence"), "naive": ("speed", "special_defence"),
    "lonely": ("attack", "defence"), "mild": ("special_attack", "defence"),
}
RESIST_BERRY = {"rindo_berry": "Grass", "coba_berry": "Flying", "shuca_berry": "Ground",
                "colbur_berry": "Dark", "occa_berry": "Fire", "passho_berry": "Water",
                "wacan_berry": "Electric", "chople_berry": "Fighting", "kebia_berry": "Poison",
                "charti_berry": "Rock", "babiri_berry": "Steel", "yache_berry": "Ice",
                "payapa_berry": "Psychic", "tanga_berry": "Bug", "kasib_berry": "Ghost",
                "haban_berry": "Dragon", "roseli_berry": "Fairy", "chilan_berry": "Normal"}


def stat(base, iv, ev, level, boost=1.0):
    return int((int(((2 * base + iv + ev // 4) * level) / 100) + 5) * boost)


def hp_stat(base, iv, ev, level):
    return int(((2 * base + iv + ev // 4) * level) / 100) + level + 10


def can_still_evolve(sp):
    return bool(sp.get("evolutions"))


def evolve(species, name, level, stones=False):
    """The form a player would actually have at this level, following level evolutions (and item ones with
    --stones). Conservative by default: a Pokemon that needs a stone stays unevolved."""
    seen = set()
    cur = name
    while cur not in seen:
        seen.add(cur)
        sp = species.get(cur)
        if not sp:
            return cur
        nxt = None
        for ev in sp.get("evolutions") or []:
            res = key((ev.get("result") or "").split()[0])
            if res not in species:
                continue
            reqs = ev.get("requirements") or []
            lv = next((r.get("minLevel") for r in reqs if r.get("variant") == "level"), None)
            if ev.get("variant") == "level_up" and lv is not None and level >= lv and len(reqs) == 1:
                nxt = res
                break
            if stones and ev.get("variant") in ("item_interact", "trade") and lv is None:
                nxt = res
                break
        if not nxt:
            return cur
        cur = nxt
    return cur


def level_moves(sp, level):
    out = []
    for entry in sp.get("moves") or []:
        m = re.match(r"^(\d+):(\w+)$", entry)
        if m and int(m.group(1)) <= level:
            out.append(m.group(2))
    return out


def choose_moveset(sp, level, moves, chart):
    """Four damaging moves a sensible player would carry: the best-powered move of each of its best types."""
    cands = []
    types = [sp.get("primaryType"), sp.get("secondaryType")]
    for mid in level_moves(sp, level):
        mv = moves.get(mid)
        if not mv or mv["power"] <= 0:
            continue
        stab = 1.5 if mv["type"].lower() in [t.lower() for t in types if t] else 1.0
        cands.append((mv["power"] * stab * mv["accuracy"] / 100.0, mid, mv))
    best_by_type = {}
    for score, mid, mv in sorted(cands, reverse=True):
        best_by_type.setdefault(mv["type"], (score, mid))
    picked = [mid for _s, mid in sorted(best_by_type.values(), reverse=True)][:4]
    return picked


class Mon:
    def __init__(self, species, name, level, moves, chart, ivs=15, nature=None, ability=None,
                 item=None, moveset=None, stones=False):
        self.given = name
        name = key(name)
        self.name = evolve(species, name, level, stones) if moveset is None else name
        sp = species.get(self.name)
        if sp is None:
            raise SimError("no species data for %r" % name)
        self.sp = sp
        self.level = level
        self.types = [t for t in (sp.get("primaryType"), sp.get("secondaryType")) if t]
        self.ability = (ability or (sp.get("abilities") or ["none"])[0]).replace("h:", "")
        self.item = item
        up, down = NATURES.get(nature or "", (None, None))
        b = sp["baseStats"]

        def s(key):
            boost = 1.1 if key == up else (0.9 if key == down else 1.0)
            return stat(b[key], ivs, 0, level, boost)

        self.hp = hp_stat(b["hp"], ivs, 0, level)
        self.atk, self.df = s("attack"), s("defence")
        self.spa, self.spd = s("special_attack"), s("special_defence")
        self.spe = s("speed")
        if self.item == "eviolite" and can_still_evolve(sp):
            self.df = int(self.df * 1.5)
            self.spd = int(self.spd * 1.5)
        if self.item == "assault_vest":
            self.spd = int(self.spd * 1.5)
        self.moveset = moveset if moveset is not None else choose_moveset(sp, level, moves, chart)

    def __repr__(self):
        return "%s L%d" % (self.name, self.level)


# ------------------------------------------------------------------ the fight

def damage(att, dfn, mid, moves, chart):
    mv = moves.get(mid)
    if not mv or mv["power"] <= 0:
        return 0.0
    eff = effectiveness(chart, mv["type"], dfn.types)
    if dfn.ability == "levitate" and mv["type"] == "Ground" and att.ability != "moldbreaker":
        eff = 0.0
    if eff == 0.0:
        return 0.0
    if mv["category"] == "Physical":
        a, d = att.atk, dfn.df
    else:
        a, d = att.spa, dfn.spd
    if att.item in ("choice_band", "muscle_band") and mv["category"] == "Physical":
        a = int(a * (1.5 if att.item == "choice_band" else 1.1))
    base = int(int(int(2 * att.level / 5 + 2) * mv["power"] * a / d) / 50) + 2
    dmg = base * eff
    if mv["type"].lower() in [t.lower() for t in att.types]:
        dmg *= 1.5
    if att.item == "life_orb":
        dmg *= 1.3
    if dfn.ability == "thickfat" and mv["type"] in ("Fire", "Ice") and att.ability != "moldbreaker":
        dmg *= 0.5
    if dfn.ability == "filter" and eff > 1 and att.ability != "moldbreaker":
        dmg *= 0.75
    if RESIST_BERRY.get(dfn.item or "") == mv["type"] and eff > 1:
        dmg *= 0.5
    return dmg * 0.925 * mv["accuracy"] / 100.0


def best_damage(att, dfn, moves, chart):
    best = 0.0
    pick = None
    for mid in att.moveset:
        d = damage(att, dfn, mid, moves, chart)
        if d > best:
            best, pick = d, mid
    return best, pick


def duel(a, b, moves, chart, cap_turns=60):
    """One on one from full health, best damaging move each turn, faster first. Returns (winner, turns)."""
    ha, hb = float(a.hp), float(b.hp)
    da, _ = best_damage(a, b, moves, chart)
    db, _ = best_damage(b, a, moves, chart)
    if da <= 0 and db <= 0:
        return None, cap_turns
    first_a = a.spe >= b.spe
    for t in range(cap_turns):
        order = [(a, b), (b, a)] if first_a else [(b, a), (a, b)]
        for att, dfn in order:
            dmg = da if att is a else db
            if dmg <= 0:
                continue
            full = (hb if dfn is b else ha) >= dfn.hp
            if dfn.ability == "sturdy" and att.ability != "moldbreaker" and full and dmg >= dfn.hp:
                dmg = dfn.hp - 1
            if dfn is b:
                hb -= dmg
                if hb <= 0:
                    return a, t + 1
            else:
                ha -= dmg
                if ha <= 0:
                    return b, t + 1
    return None, cap_turns


def run_gauntlet(team, foes, moves, chart):
    """Lead with team[0], never switch, never heal; both sides carry their damage forward. Returns
    (won, player faints, foes downed, the fraction of the last foe's health left)."""
    hp = {id(m): float(m.hp) for m in team + foes}
    i, j = 0, 0
    guard = 0
    while i < len(team) and j < len(foes) and guard < 400:
        guard += 1
        a, b = team[i], foes[j]
        da, _ = best_damage(a, b, moves, chart)
        db, _ = best_damage(b, a, moves, chart)
        if da <= 0 and db <= 0:                       # neither can hurt the other: the player has to switch
            i += 1
            continue
        first_a = a.spe >= b.spe
        for att, dfn in ([(a, b), (b, a)] if first_a else [(b, a), (a, b)]):
            dmg = da if att is a else db
            if dmg <= 0:
                continue
            full = hp[id(dfn)] >= dfn.hp
            if dfn.ability == "sturdy" and att.ability != "moldbreaker" and full and dmg >= dfn.hp:
                dmg = dfn.hp - 1
            hp[id(dfn)] -= dmg
            if hp[id(dfn)] <= 0:
                break
        if hp[id(b)] <= 0:
            j += 1
        elif hp[id(a)] <= 0:
            i += 1
    left = 0.0 if j >= len(foes) else max(0.0, hp[id(foes[j])] / foes[j].hp)
    return j >= len(foes), i, j, left


def pick_team(cands, species, moves, chart, cap, ivs, stones, how, n=6):
    """Six Pokemon a player might actually be carrying.

    informed  the six the simulation itself ranks highest: a player who looked up the answer
    walked    the six earliest-available species, one per family: a player who kept what they walked past
    """
    rows = list(cands)
    if how == "walked":
        rows = sorted(rows, key=lambda c: (c["first_at"], c["caught_as"]))
    seen, out = set(), []
    for c in rows:
        fam = c["used_as"]
        if fam in seen:
            continue
        seen.add(fam)
        out.append(Mon(species, c["caught_as"], cap, moves, chart, ivs=ivs, stones=stones))
        if len(out) == n:
            break
    return out


# ------------------------------------------------------------------ the report

def gym_leaders():
    d = json.loads(TRAINERS.read_text(encoding="utf-8"))
    out = {}
    for t in d["trainers"]:
        if t["class"] == "gym_leader":
            out[t["order"]] = t
    return out, d["generation_contract"]


def build_leader(t, species, moves, chart, ivs, stones):
    team = []
    for m in t["team"]:
        team.append(Mon(species, m["species"], m["level"], moves, chart, ivs=ivs, nature=m.get("nature"),
                        ability=m.get("ability"), item=m.get("heldItem"), moveset=m.get("moveset"),
                        stones=stones))
    return team


def assess(gym, avail, leaders, species, moves, chart, ivs, stones, caps):
    t = leaders.get(gym)
    rows = avail[gym]["rows"]
    init, rel = caps
    cap = t["team"][-1]["level"] if t and t["team"] else None
    out = {"gym": gym, "theme": avail[gym]["theme"], "leader": avail[gym]["leader"],
           "cap": cap, "candidates": [], "team": t["team"] if t else [],
           "status": t["status"] if t else "missing"}
    if not t or not t["team"]:
        return out
    foes = build_leader(t, species, moves, chart, ivs, stones)
    out["foes"] = foes
    seen = set()
    # A candidate the jar does not know is COUNTED, not dropped in silence. Gendered Nidoran fell out of Gym 8's
    # pool for exactly this reason and nothing said so (found by the test author, 2026-09-24): a shrinking pool
    # looks the same as a narrow one, which is the very thing this tool is for.
    out["unresolved"] = []
    for r in rows:
        k = key(r["species"])
        if k in seen:
            continue
        seen.add(k)
        if k not in species:
            out["unresolved"].append(r["species"])
            continue
        try:
            p = Mon(species, k, cap, moves, chart, ivs=ivs, stones=stones)
        except SimError as e:
            out["unresolved"].append("%s (%s)" % (r["species"], e))
            continue
        if not p.moveset:
            continue
        beats, turns = [], []
        for f in foes:
            w, n = duel(p, f, moves, chart)
            if w is p:
                beats.append(f.name)
                turns.append(n)
        out["candidates"].append({"caught_as": r["species"], "used_as": p.name, "beats": beats,
                                  "n": len(beats), "turns": turns, "first_at": r["lo"],
                                  "corridor": r["corridor"], "types": "/".join(p.types)})
    out["candidates"].sort(key=lambda c: (-c["n"], c["used_as"]))

    # How much of the ace one Pokemon can take off before it faints. 1v1 win/lose hides the case where nothing
    # beats the ace alone but two things between them bring it down comfortably.
    ace = foes[-1]
    chips = []
    for c in out["candidates"][:40]:
        p = Mon(species, c["caught_as"], cap, moves, chart, ivs=ivs, stones=stones)
        won, _f, downed, left = run_gauntlet([p], [ace], moves, chart)
        chips.append((1.0 if won else 1.0 - left, c["used_as"]))
    chips.sort(reverse=True)
    out["ace_chip"] = chips[:5]
    out["ace_cost"] = None
    if chips:
        total, used = 0.0, 0
        for frac, _name in chips:
            if total >= 1.0:
                break
            total += frac
            used += 1
        out["ace_cost"] = used if total >= 1.0 else None

    # what a super-effective attacker would have to be, and how many families can field one
    weak = [t for t in chart if effectiveness(chart, t, ace.types) > 1.0]
    out["ace_weak_to"] = sorted(weak)
    on_type = {}
    for c in out["candidates"]:
        p_types = [t.lower() for t in c["types"].split("/")]
        if any(t in weak for t in p_types):
            on_type.setdefault(c["used_as"], c)
    out["on_type"] = list(on_type.values())

    for how in ("informed", "walked"):
        team = pick_team(out["candidates"], species, moves, chart, cap, ivs, stones, how)
        won, faints, downed, left = run_gauntlet(team, build_leader(t, species, moves, chart, ivs, stones),
                                                 moves, chart)
        out[how] = {"team": [m.name for m in team], "won": won, "faints": faints, "downed": downed,
                    "left": left}
    return out


def starter_sensitivity(gym_rows, species, moves, chart, ivs, stones, starters):
    out = {}
    for s in starters:
        k = key(s)
        if k not in species:
            continue
        res = {}
        for g, a in gym_rows.items():
            if not a.get("foes"):
                continue
            p = Mon(species, k, a["cap"], moves, chart, ivs=ivs, stones=stones)
            beats = [f.name for f in a["foes"] if duel(p, f, moves, chart)[0] is p]
            res[g] = (p.name, len(beats), len(a["foes"]))
        out[s] = res
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gym", type=int)
    ap.add_argument("--ivs", type=int, default=15)
    ap.add_argument("--stones", action="store_true")
    ap.add_argument("--markdown")
    a = ap.parse_args(argv)

    jar = find_jar()
    species, moves, chart = load_pack(jar)
    avail = parse_availability(AVAILABILITY)
    leaders, contract = gym_leaders()
    caps = level_caps(RCT_CONFIG)

    lines = []

    def say(s=""):
        lines.append(s)
        print(s)

    say("Cobblemon jar: %s" % jar.name)
    say("species %d, moves %d, types %d; IVs %d, EVs 0, %s evolutions"
        % (len(species), len(moves), len(chart), a.ivs, "level and item" if a.stones else "level only"))
    say("level cap from rctmod-server.toml: initial %d, relative +%d" % caps)
    say("")

    results = {}
    for g in sorted(avail):
        results[g] = assess(g, avail, leaders, species, moves, chart, a.ivs, a.stones, caps)

    for g in sorted(results):
        r = results[g]
        if a.gym and g != a.gym:
            continue
        say("=" * 100)
        say("GYM %d  %s (%s)   leader status: %s" % (g, r["leader"], r["theme"], r["status"]))
        if not r.get("foes"):
            say("  NO ROSTER IN data/trainers.json. Nothing to simulate.")
            say("")
            continue
        say("  cap %d, roster: %s" % (r["cap"], ", ".join("%s L%d" % (m["species"], m["level"])
                                                          for m in r["team"])))
        cands = r["candidates"]
        n_foes = len(r["foes"])
        sweepers = [c for c in cands if c["n"] == n_foes]
        partial = [c for c in cands if 0 < c["n"] < n_foes]
        nothing = [c for c in cands if c["n"] == 0]
        ace = r["foes"][-1].name
        beats_ace = [c for c in cands if ace in c["beats"]]
        say("  %d catchable candidates: %d beat the whole roster 1v1, %d beat some, %d beat none"
            % (len(cands), len(sweepers), len(partial), len(nothing)))
        if r.get("unresolved"):
            say("  !! %d availability rows did not resolve to a species and are NOT in the pool: %s"
                % (len(r["unresolved"]), ", ".join(r["unresolved"][:6])))
        say("  beat the ace (%s): %d" % (ace, len(beats_ace)))
        say("  the ace is weak to: %s; %d catchable families can attack on one of those types"
            % (", ".join(r["ace_weak_to"]) or "nothing", len(r["on_type"])))
        if r["on_type"]:
            say("    %s" % ", ".join("%s (%s, first wild L%d)" % (c["used_as"], c["types"], c["first_at"])
                                     for c in r["on_type"][:10]))
        say("  most health taken off the ace by one Pokemon: %s"
            % ", ".join("%s %.0f%%" % (n, f * 100) for f, n in r["ace_chip"]))
        say("  Pokemon needed to bring the ace down: %s"
            % (r["ace_cost"] if r["ace_cost"] else "more than five: nothing available can finish it"))
        for how in ("informed", "walked"):
            g = r[how]
            say("  gauntlet, %-8s team %s" % (how, ", ".join(g["team"])))
            say("      %s -- %d of %d leader Pokemon downed, %d player Pokemon lost%s"
                % ("WIN" if g["won"] else "LOSS", g["downed"], n_foes, g["faints"],
                   "" if g["won"] else ", next foe on %.0f%% health" % (g["left"] * 100)))
        top = cands[:8] if not a.gym else cands
        for c in top:
            say("    %-12s as %-12s %-16s %d/%d  first wild L%-3d %s"
                % (c["caught_as"], c["used_as"], c["types"], c["n"], n_foes, c["first_at"],
                   ",".join(c["beats"]) if c["n"] else ""))
        say("")

    say("=" * 100)
    say("STARTERS")
    starters = ["charmander", "squirtle", "bulbasaur", "cyndaquil", "totodile", "chikorita",
                "torchic", "mudkip", "treecko"]
    sens = starter_sensitivity(results, species, moves, chart, a.ivs, a.stones, starters)
    hdr = "  %-12s" % "starter" + "".join("  G%d" % g for g in sorted(results) if results[g].get("foes"))
    say(hdr)
    for s, res in sens.items():
        row = "  %-12s" % s
        for g in sorted(results):
            if not results[g].get("foes"):
                continue
            form, b, n = res[g]
            row += "  %d/%d" % (b, n)
        say(row + "   (final form at cap: %s)" % res[max(res)][0])
    say("")
    if a.markdown:
        Path(a.markdown).write_text("# Gym battle simulation\n\n```\n" + "\n".join(lines) + "\n```\n",
                                    encoding="utf-8")
        print("wrote %s" % a.markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
