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

WHAT IS MODELLED. Enough to design a fight around abilities and items, which is what the gyms are built on.

  damage       the mainline formula, average roll, multiplied by accuracy; physical/special split; stat stages
  weather      Drought, Drizzle, Sand Stream, Snow Warning and the weather moves. Sun multiplies Fire by 1.5 and
               halves Water; rain does the reverse. This is not decoration: Blaine leads Drought Torkoal, and
               turning sun on reversed the verdict on his gym from a clean win to a loss.
  abilities    Sturdy, Levitate, Mold Breaker, Thick Fat, Filter/Solid Rock, Multiscale, Adaptability, Tinted
               Lens, Huge/Pure Power, Guts, Magic Guard, Intimidate (on switch-in), and the type absorbers:
               Lightning Rod, Motor Drive, Volt Absorb, Water Absorb, Dry Skin, Flash Fire, Sap Sipper, Earth
               Eater. Three of Surge's four have Lightning Rod, so an Electric answer to the Electric gym does
               literally nothing, and the tool now knows that.
  items        Focus Sash, Sturdy's twin, on seven leader Pokemon; Weakness Policy, Sitrus and Oran berries,
               Leftovers, Black Sludge, Life Orb and its recoil, Choice Band/Specs/Scarf, Muscle Band, Assault
               Vest, Eviolite, Rocky Helmet, Air Balloon and the type-resist berries.
  status       paralysis (half speed, a quarter of turns lost), burn (halved physical, chip), poison and toxic,
               sleep for two turns. Thunder Wave, Will-O-Wisp, Toxic, Sleep Powder, Hypnosis, Spore, Glare.
  status moves stat-stage moves both ways (Nasty Plot, Quiver Dance, Shell Smash, Scary Face, Tearful Look),
               screens, weather moves and recovery moves.
  variable     Grass Knot and Low Kick by the defender's weight, Gyro Ball by the speed ratio. Showdown stores
               these with basePower 0, and reading that as "status move" had silently disarmed Raichu.
  no bag items neither side uses one, which is correct: every authored leader sets `battleRules.maxItemUses: 0`.

LIMITS, and they are still large.

  - SWITCHING IS NOT TRUSTWORTHY and is off by default (`--switching` turns it on). The player-side bound
    implemented here came out WORSE than never switching at two of seven gyms, because every switch hands the
    foe a free hit and a greedy "who wins this matchup" rule spends them badly. A bound that can fall below the
    thing it bounds is measuring its own policy, not the fight. The leader never switches at all, though
    data/trainers.json declares a `switchBias` of 0.65 for every gym leader.
  - no healing items, no revives: a player with twenty potions is not modelled. The leaders need none.
  - no hazards. Stealth Rock, Spikes and Toxic Spikes are counted as unmodelled and do nothing, because they
    only pay off against switching.
  - no secondary effects: no flinch, no burn or freeze chance on an attacking move, no confusion, no crits.
  - no Protect, Substitute, Encore, Taunt, Pain Split, Trick Room, Tailwind or Baton Pass.
  - abilities outside the list above do nothing, including Static, Effect Spore, Cursed Body, Poison Point,
    Chlorophyll, Swift Swim and Solar Power.
  - Dry Skin is modelled as the Water immunity only. Its 1.25x vulnerability to Fire and its weather tick are
    not, so the holder reads as strictly better than it is. Nothing on an authored roster or in a catchable
    pool has it today, so it moves no number; it would the moment a leader takes it.
  - IVs 15 and EVs 0 on both sides. Real wild catches roll 0-31 and real trainers may not.
  - the player's moves are the level-up list only, while every leader carries a hand-picked set including TM
    moves. TMCraft is in the pack. This biases the whole simulation AGAINST the player.
  - it cannot tell you whether a fight is fun, how long it takes, or whether the answer is discoverable.

AND ONE THING IT CANNOT CHECK AT ALL: whether Cobblemon's own embedded Showdown computes damage the way the
mainline formula does at these levels. The tests prove this tool agrees with the published formula, not that the
game agrees with either. Settling that needs a battle run in a real server and the damage read back; see
docs/research/EXPERIMENT_BACKLOG.md.

  python tools/battle_sim.py                     # the report
  python tools/battle_sim.py --gym 3             # one gym, every candidate listed
  python tools/battle_sim.py --ivs 31            # sensitivity: both sides at perfect IVs
  python tools/battle_sim.py --stones            # allow item evolutions as well as level ones
  python tools/battle_sim.py --switching         # also run the (untrustworthy) switching bound
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
AVAIL_JSON = ROOT / "derived" / "availability.json"
GYM_NAMES = {1: ("kanto_brock", "Rock"), 2: ("kanto_misty", "Water"),
             3: ("kanto_ltsurge", "Electric"), 4: ("kanto_erika", "Grass"),
             5: ("kanto_koga", "Poison"), 6: ("kanto_sabrina", "Psychic"),
             7: ("kanto_blaine", "Fire"), 8: ("kanto_giovanni", "Ground")}
STARTER_OVERLAY = ROOT / "modpack" / "config" / "cobblemon" / "starters.json"
STARTER_CONFIG = ROOT / "base-pack" / "cobbleverse" / "config" / "cobblemon" / "starters.json"
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
# was dropped, and every Water defender read as neutral to Electric and Grass (found 2026-09-23).
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
                    "accuracy": 100 if (not acc or acc.group(1) == "true") else int(acc.group(1)),
                    "contact": bool(re.search(r"flags: \{[^}]*contact: 1", body))}
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
    """Read derived/availability.json, which tools/battle_sim.py's sibling generates from the compiled pools.

    This used to scrape docs/story/AVAILABILITY.md with a regex. A generated table is not an interface: the
    gendered Nidoran rows could not be matched and simply vanished from the candidate pool, and a pool that had
    silently shrunk looked exactly like one that was genuinely narrow.
    """
    if not AVAIL_JSON.is_file():
        raise SimError("no %s: run python tools/availability.py --write first" % AVAIL_JSON)
    d = json.loads(AVAIL_JSON.read_text(encoding="utf-8"))
    out = {}
    for g, rows in d["gyms"].items():
        g = int(g)
        leader, theme = GYM_NAMES.get(g, ("gym_%d" % g, "?"))
        out[g] = {"leader": leader, "theme": theme,
                  "rows": [{"species": r["species"], "lo": r["lo"], "hi": r["hi"],
                            "corridor": "%s (%s)" % (r["pool"], r["kind"])} for r in rows]}
    if not out:
        raise SimError("no gyms in %s" % AVAIL_JSON)
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
        if not mv:
            continue
        power = mv["power"]
        if power <= 0:
            # Grass Knot, Low Kick and Gyro Ball rank on a nominal power here because the real one depends on
            # the target. Dropping them is what stopped any player candidate carrying Low Kick into Onix.
            power = VARIABLE_NOMINAL.get(mid, 0)
        if power <= 0:
            continue
        stab = 1.5 if mv["type"].lower() in [t.lower() for t in types if t] else 1.0
        cands.append((power * stab * mv["accuracy"] / 100.0, mid, mv))
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
        self.dex = species
        self.side = "player"
        self.reset()

    # ---- battle state. A Mon is reused across duels, so every battle starts by clearing it.
    def reset(self):
        self.hp_now = float(self.hp)
        self.stages = {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
        self.status = None
        self.used_once = set()
        self.item_used = False
        self.balloon_popped = False
        self.tox_turns = 0
        self.sleep_turns = 0
        self.hit_this_turn = False

    def enter(self, side):
        self.reset()
        self.side = side

    def eff_atk(self):
        return max(1, int(self.atk * STAGE[self.stages["atk"]]))

    def eff_def(self):
        return max(1, int(self.df * STAGE[self.stages["def"]]))

    def eff_spa(self):
        return max(1, int(self.spa * STAGE[self.stages["spa"]]))

    def eff_spd(self):
        return max(1, int(self.spd * STAGE[self.stages["spd"]]))

    def eff_spe(self):
        s = int(self.spe * STAGE[self.stages["spe"]])
        if self.item == "choice_scarf":
            s = int(s * 1.5)
        if self.status == "par":
            s = int(s * 0.5)
        return max(1, s)

    def __repr__(self):
        return "%s L%d" % (self.name, self.level)


# ------------------------------------------------------------------ the fight

STAGE = {-6: 2 / 8, -5: 2 / 7, -4: 2 / 6, -3: 2 / 5, -2: 2 / 4, -1: 2 / 3,
         0: 1.0, 1: 3 / 2, 2: 4 / 2, 3: 5 / 2, 4: 6 / 2, 5: 7 / 2, 6: 8 / 2}

# Abilities that make an attacking type do nothing, and what the holder gets for it. These flip whole matchups:
# three of Surge's four have Lightning Rod, so an Electric answer to an Electric gym does literally zero.
ABSORB = {"lightningrod": ("Electric", "spa"), "motordrive": ("Electric", "spe"),
          "voltabsorb": ("Electric", "heal"), "waterabsorb": ("Water", "heal"),
          "dryskin": ("Water", "heal"), "flashfire": ("Fire", "spa"), "sapsipper": ("Grass", "atk"),
          "levitate": ("Ground", None), "eartheater": ("Ground", "heal")}
# Showdown gives these basePower 0 because the real power depends on the target. This is only for RANKING a
# player's moveset; the damage calculation computes the real number from the defender's weight or speed.
VARIABLE_NOMINAL = {"grassknot": 60, "lowkick": 60, "gyroball": 60}

# A type cannot take the status its own type produces. Koga's team is Poison and cannot be poisoned; Blaine's is
# Fire and cannot be burned; Surge's is Electric and cannot be paralysed. Leaving these out let the simulation
# shut down three whole gyms with a single status move.
STATUS_IMMUNE = {"par": ("electric",), "brn": ("fire",), "psn": ("poison", "steel"),
                 "tox": ("poison", "steel"), "frz": ("ice",)}
POWDER_MOVES = {"sleeppowder", "poisonpowder", "stunspore", "spore"}

WEATHER_ABILITY = {"drought": "sun", "drizzle": "rain", "sandstream": "sand", "snowwarning": "snow"}
SCREEN_MOVES = {"lightscreen": "special", "reflect": "physical", "auroraveil": "both"}
BOOST_MOVES = {"nastyplot": {"spa": 2}, "swordsdance": {"atk": 2}, "agility": {"spe": 2},
               "calmmind": {"spa": 1, "spd": 1}, "irondefense": {"def": 2}, "growth": {"atk": 1, "spa": 1},
               "quiverdance": {"spa": 1, "spd": 1, "spe": 1}, "shellsmash": {"atk": 2, "spa": 2, "spe": 2,
                                                                            "def": -1, "spd": -1},
               "dragondance": {"atk": 1, "spe": 1}, "bulkup": {"atk": 1, "def": 1}}
DROP_MOVES = {"scaryface": {"spe": -2}, "growl": {"atk": -1}, "tearfullook": {"atk": -1, "spa": -1},
              "charm": {"atk": -2}, "screech": {"def": -2}, "smokescreen": {}, "leer": {"def": -1}}
STATUS_MOVES = {"thunderwave": "par", "willowisp": "brn", "toxic": "tox", "sleeppowder": "slp",
                "spore": "slp", "hypnosis": "slp", "yawn": "slp", "poisonpowder": "psn", "glare": "par"}
WEATHER_MOVES = {"sunnyday": "sun", "raindance": "rain", "sandstorm": "sand", "hail": "snow", "snowscape": "snow"}
HEAL_MOVES = {"recover", "roost", "softboiled", "slackoff", "synthesis", "moonlight", "morningsun", "rest"}
# Modelled as a no-op, and counted as such in the report rather than quietly ignored.
UNMODELLED = {"stealthrock", "toxicspikes", "spikes", "protect", "encore", "painsplit", "trickroom",
              "tailwind", "substitute", "taunt", "whirlwind", "roar", "haze", "healbell", "batonpass"}


class Field:
    """What is true of the battle rather than of one Pokemon."""

    def __init__(self):
        self.weather = None
        self.screens = {"player": {}, "foe": {}}

    def screen(self, side, category):
        sc = self.screens[side]
        return 0.5 if (sc.get(category) or sc.get("both")) else 1.0


def side_of(mon, team):
    return "player" if mon in team else "foe"


def variable_power(mid, att, dfn, moves, species):
    """Grass Knot, Low Kick and Gyro Ball carry basePower 0 in Showdown because the power is computed. Treating
    them as status moves silently disarmed every leader that holds one -- Raichu's Grass Knot among them."""
    if mid in ("grassknot", "lowkick"):
        w = float((species.get(dfn.name) or {}).get("weight") or 0)   # hectograms in the jar
        kg = w / 10.0
        for bound, pw in ((200, 120), (100, 100), (50, 80), (25, 60), (10, 40)):
            if kg >= bound:
                return pw
        return 20
    if mid == "gyroball":
        return max(1, min(150, int(25 * max(1, dfn.eff_spe()) / max(1, att.eff_spe()))))
    if mid in ("seismictoss", "nightshade"):
        return None      # fixed damage, handled by the caller
    return None


def damage(att, dfn, mid, moves, chart, field=None, species=None):
    mv = moves.get(mid)
    if not mv:
        return 0.0
    power = mv["power"]
    if power <= 0:
        # the dex travels on the Pokemon, so a caller that forgets to pass one no longer gets a silent zero
        dex = species if species is not None else getattr(att, "dex", None)
        power = (variable_power(mid, att, dfn, moves, dex) or 0) if dex else 0
    if power <= 0:
        return 0.0
    eff = effectiveness(chart, mv["type"], dfn.types)
    absorb = ABSORB.get(dfn.ability)
    if absorb and absorb[0] == mv["type"] and att.ability != "moldbreaker":
        gain = absorb[1]
        if gain == "heal":
            dfn.hp_now = min(float(dfn.hp), dfn.hp_now + dfn.hp / 4.0)
        elif gain:
            dfn.stages[gain] = min(6, dfn.stages[gain] + 1)
        return 0.0
    if dfn.item == "airballoon" and mv["type"] == "Ground" and not dfn.balloon_popped:
        return 0.0
    if eff == 0.0:
        return 0.0
    physical = mv["category"] == "Physical"
    a = att.eff_atk() if physical else att.eff_spa()
    d = dfn.eff_def() if physical else dfn.eff_spd()
    if att.item in ("choice_band", "muscle_band") and physical:
        a = int(a * (1.5 if att.item == "choice_band" else 1.1))
    if att.item == "choice_specs" and not physical:
        a = int(a * 1.5)
    if att.ability in ("hugepower", "purepower") and physical:
        a *= 2
    if att.ability == "guts" and att.status in ("brn", "par", "psn", "tox") and physical:
        a = int(a * 1.5)
    elif att.status == "brn" and physical and att.ability != "guts":
        a = int(a * 0.5)
    base = int(int(int(2 * att.level / 5 + 2) * power * a / max(1, d)) / 50) + 2
    dmg = float(base) * eff
    stab = 2.0 if att.ability == "adaptability" else 1.5
    if mv["type"].lower() in [t.lower() for t in att.types]:
        dmg *= stab
    if field is not None and field.weather:
        if field.weather == "sun":
            dmg *= 1.5 if mv["type"] == "Fire" else (0.5 if mv["type"] == "Water" else 1.0)
        elif field.weather == "rain":
            dmg *= 1.5 if mv["type"] == "Water" else (0.5 if mv["type"] == "Fire" else 1.0)
    if field is not None:
        dmg *= field.screen(dfn.side, "physical" if physical else "special")
    if att.item == "life_orb":
        dmg *= 1.3
    if att.ability == "tintedlens" and eff < 1:
        dmg *= 2.0
    if dfn.ability == "thickfat" and mv["type"] in ("Fire", "Ice") and att.ability != "moldbreaker":
        dmg *= 0.5
    if dfn.ability in ("filter", "solidrock", "prismarmor") and eff > 1 and att.ability != "moldbreaker":
        dmg *= 0.75
    if dfn.ability == "multiscale" and dfn.hp_now >= dfn.hp and att.ability != "moldbreaker":
        dmg *= 0.5
    if RESIST_BERRY.get(dfn.item or "") == mv["type"] and eff > 1:
        dmg *= 0.5
    return dmg * 0.925 * mv["accuracy"] / 100.0


def best_damage(att, dfn, moves, chart, field=None, species=None):
    best, pick = 0.0, None
    for mid in att.moveset:
        d = damage(att, dfn, mid, moves, chart, field, species)
        if d > best:
            best, pick = d, mid
    return best, pick


def best_action(att, dfn, moves, chart, field, species):
    """What the Pokemon does this turn: its best damaging move, or a set-up move when it cannot hurt the target.

    This is not an AI. It is the best deterministic line available to a side that never switches, which is
    stronger than most play on the leader's side and weaker on the player's.
    """
    dmg, mid = best_damage(att, dfn, moves, chart, field, species)
    if dmg > 0:
        return ("attack", mid, dmg)
    for m in att.moveset:
        if m in att.used_once:
            continue
        if m in HEAL_MOVES:
            if att.hp_now <= att.hp * 0.6:
                att.used_once.discard(m)          # recovery is worth repeating, unlike a set-up move
                return ("support", m, 0.0)
            continue
        if m in BOOST_MOVES or m in DROP_MOVES or m in STATUS_MOVES or m in SCREEN_MOVES or m in WEATHER_MOVES:
            return ("support", m, 0.0)
    return ("stall", None, 0.0)


def status_immune(mon, want, mid):
    """Type immunities, and the abilities that actually confer one. Magic Guard is NOT among them: it stops
    indirect damage, not status, and Alakazam can be paralysed like anything else."""
    if any(t.lower() in STATUS_IMMUNE.get(want, ()) for t in mon.types):
        return True
    if mid in POWDER_MOVES and any(t.lower() == "grass" for t in mon.types):
        return True
    if mon.ability in ("immunity",) and want in ("psn", "tox"):
        return True
    if mon.ability in ("limber",) and want == "par":
        return True
    if mon.ability in ("waterveil", "waterbubble") and want == "brn":
        return True
    if mon.ability in ("insomnia", "vitalspirit") and want == "slp":
        return True
    return False


def apply_support(mon, foe, mid, field, moves):
    """Stat stages, screens, weather and status. Everything the leaders' movesets actually carry."""
    mon.used_once.add(mid)
    if mid in BOOST_MOVES:
        for k, v in BOOST_MOVES[mid].items():
            mon.stages[k] = max(-6, min(6, mon.stages[k] + v))
        return True
    if mid in DROP_MOVES:
        for k, v in DROP_MOVES[mid].items():
            foe.stages[k] = max(-6, min(6, foe.stages[k] + v))
        return True
    if mid in SCREEN_MOVES:
        field.screens[mon.side][SCREEN_MOVES[mid]] = True
        return True
    if mid in WEATHER_MOVES:
        field.weather = WEATHER_MOVES[mid]
        return True
    if mid in STATUS_MOVES:
        want = STATUS_MOVES[mid]
        if foe.status is None and not status_immune(foe, want, mid):
            foe.status = want
        return True
    if mid in HEAL_MOVES:
        mon.hp_now = min(float(mon.hp), mon.hp_now + mon.hp / 2.0)
        return True
    return False


def take_hit(dfn, att, dmg, eff_super, contact):
    """Focus Sash, Sturdy, Weakness Policy, Rocky Helmet, the pinch berries and the balloon."""
    full = dfn.hp_now >= dfn.hp
    if dmg >= dfn.hp_now and full:
        if dfn.ability == "sturdy" and att.ability != "moldbreaker":
            dmg = dfn.hp_now - 1
        elif dfn.item == "focus_sash" and not dfn.item_used:
            dmg = dfn.hp_now - 1
            dfn.item_used = True
    dfn.hp_now -= dmg
    if dfn.hp_now > 0:
        if eff_super and dfn.item == "weakness_policy" and not dfn.item_used:
            dfn.stages["atk"] = min(6, dfn.stages["atk"] + 2)
            dfn.stages["spa"] = min(6, dfn.stages["spa"] + 2)
            dfn.item_used = True
        if dfn.item in ("sitrus_berry", "oran_berry") and not dfn.item_used and dfn.hp_now <= dfn.hp / 2:
            dfn.hp_now = min(float(dfn.hp), dfn.hp_now + (dfn.hp / 4.0 if dfn.item == "sitrus_berry" else 10.0))
            dfn.item_used = True
        if contact and dfn.item == "rocky_helmet" and att.ability != "magicguard":
            att.hp_now -= att.hp / 6.0
    return dmg


def end_of_turn(mon, field):
    if mon.hp_now <= 0:
        return
    guarded = mon.ability == "magicguard"     # blocks indirect damage only: it does not stop Leftovers
    if mon.item == "leftovers":
        mon.hp_now = min(float(mon.hp), mon.hp_now + mon.hp / 16.0)
    elif mon.item == "black_sludge":
        poison = any(t.lower() == "poison" for t in mon.types)
        if poison:
            mon.hp_now = min(float(mon.hp), mon.hp_now + mon.hp / 16.0)
        elif not guarded:
            mon.hp_now -= mon.hp / 8.0
    if not guarded:
        if mon.item == "life_orb" and mon.hit_this_turn:
            mon.hp_now -= mon.hp / 10.0
        if mon.status == "brn":
            mon.hp_now -= mon.hp / 16.0
        elif mon.status == "psn":
            mon.hp_now -= mon.hp / 8.0
        elif mon.status == "tox":
            mon.tox_turns += 1
            mon.hp_now -= mon.hp * min(15, mon.tox_turns) / 16.0
        if field.weather == "sand" and not any(t.lower() in ("rock", "ground", "steel") for t in mon.types):
            mon.hp_now -= mon.hp / 16.0
    mon.hit_this_turn = False


def start_battle(team, foes, field):
    for m in team:
        m.enter("player")
    for m in foes:
        m.enter("foe")
    for m in team + foes:
        w = WEATHER_ABILITY.get(m.ability)
        if w and field.weather is None:
            field.weather = w


def switch_in(mon, foe):
    """Intimidate is the only switch-in ability that changes a matchup here, and four leader Pokemon have it."""
    if mon.ability == "intimidate" and foe is not None and foe.ability not in ("clearbody", "whitesmoke"):
        foe.stages["atk"] = max(-6, foe.stages["atk"] - 1)


def run_gauntlet(team, foes, moves, chart, species=None, switching=False, cap_turns=500, stats=None):
    """The player's team against the leader's, in order. Damage carries forward on both sides, nobody heals
    between battles, and no side uses a bag item -- which is what data/trainers.json specifies
    (`battleRules.maxItemUses: 0` on every authored leader).

    switching=False  the player never switches: the worst case, and the old behaviour.
    switching=True   the player switches to their best surviving matchup when the active one is losing. The
                     switch costs a turn, in which the foe attacks the incoming Pokemon for free, which is what
                     a switch costs in play. The leader never switches in either mode, so this is a bound and
                     not a prediction: the real fight is somewhere between the two runs.
    """
    field = Field()
    start_battle(team, foes, field)
    alive = [True] * len(team)
    active, j = 0, 0
    switch_in(team[active], foes[j] if foes else None)
    switch_in(foes[j], team[active] if team else None)
    guard, switches = 0, 0
    while any(alive) and j < len(foes) and guard < cap_turns:
        guard += 1
        b = foes[j]
        if switching:
            k = best_matchup(team, alive, active, b, moves, chart, field, species)
            if k != active and switches < len(team) * 2:
                switches += 1
                active = k
                a = team[active]
                switch_in(a, b)
                # the turn the switch costs: the foe hits the Pokemon coming in, and it does not act
                dmg, mid = best_damage(b, a, moves, chart, field, species)
                if dmg > 0:
                    mv = moves[mid]
                    take_hit(a, b, dmg, effectiveness(chart, mv["type"], a.types) > 1,
                             mv.get("contact", False))
                    b.hit_this_turn = True
                for m in (a, b):
                    end_of_turn(m, field)
                if a.hp_now <= 0:
                    alive[active] = False
                    nxt = next((q for q in range(len(team)) if alive[q]), None)
                    if nxt is None:
                        break
                    active = nxt
                    switch_in(team[active], foes[j])
                continue
        a = team[active]
        mine = best_action(a, b, moves, chart, field, species)
        theirs = best_action(b, a, moves, chart, field, species)
        if mine[0] == "stall" and theirs[0] == "stall":
            # neither can make progress: the slot is spent rather than looping to the turn cap
            alive[active] = False
            nxt = next((q for q in range(len(team)) if alive[q]), None)
            if nxt is None:
                break
            active = nxt
            switch_in(team[active], b)
            continue
        acts = [(a, b, mine), (b, a, theirs)]
        if a.eff_spe() < b.eff_spe():
            acts.reverse()
        for att, dfn, (kind, mid, dmg) in acts:
            if att.hp_now <= 0 or dfn.hp_now <= 0:
                continue
            if att.status == "par":
                dmg *= 0.75                      # a quarter of turns are lost to full paralysis
            if att.status == "slp":
                att.sleep_turns += 1
                if att.sleep_turns <= 2:
                    continue
                att.status = None
            if kind == "attack":
                mv = moves[mid]
                att.hit_this_turn = True
                take_hit(dfn, att, dmg, effectiveness(chart, mv["type"], dfn.types) > 1,
                         mv.get("contact", False))
            elif kind == "support":
                apply_support(att, dfn, mid, field, moves)
            else:
                break                            # neither side can make progress
        for m in (a, b):
            end_of_turn(m, field)
        if b.hp_now <= 0:
            j += 1
            if j < len(foes):
                switch_in(foes[j], team[active])
        if a.hp_now <= 0:
            alive[active] = False
            nxt = next((q for q in range(len(team)) if alive[q]), None)
            if nxt is None:
                break
            active = nxt
            if j < len(foes):
                switch_in(team[active], foes[j])
    faints = sum(1 for x in alive if not x)
    left = 0.0 if j >= len(foes) else max(0.0, foes[j].hp_now / foes[j].hp)
    if stats is not None:
        stats["turns"] = guard
        stats["switches"] = switches
    return j >= len(foes), faints, j, left


def best_matchup(team, alive, active, foe, moves, chart, field, species):
    """Which surviving team member beats this foe by the widest margin. Used only by the switching bound.

    It only recommends a change when the incoming Pokemon is clearly better, or the active one cannot win at
    all; without that the bound thrashes, switching every turn and never attacking.
    """
    def score(m):
        mine, _ = best_damage(m, foe, moves, chart, field, species)
        theirs, _ = best_damage(foe, m, moves, chart, field, species)
        if mine <= 0:
            return -999.0
        turns_me = foe.hp_now / mine
        turns_them = (m.hp_now / theirs) if theirs > 0 else 999.0
        return turns_them - turns_me

    here = score(team[active]) if alive[active] else -1000.0
    if here > 0:
        return active                             # already winning this one: stay in
    # Only switch when it turns a LOSS into a WIN. A looser rule -- switch whenever someone scores better --
    # made the bound perform worse than never switching at five of the seven gyms: every switch hands the foe a
    # free hit, and a chain of marginal switches is just a chain of free hits. A bound that can come out below
    # the thing it is bounding is measuring its own policy, not the fight.
    best, pick = 0.0, active
    for k in range(len(team)):
        if not alive[k] or k == active:
            continue
        sc = score(team[k])
        if sc > best:
            best, pick = sc, k
    return pick



def duel(a, b, moves, chart, cap_turns=60, species=None):
    """One on one from full health. Kept for the 1v1 table and for the tests."""
    for m in (a, b):
        m.reset()
    stats = {}
    won, _i, _j, _left = run_gauntlet([a], [b], moves, chart, species=species, cap_turns=cap_turns,
                                      stats=stats)
    alive_a = a.hp_now > 0
    for m in (a, b):
        m.reset()
    # the turn count is part of this function's contract: a caller uses it to tell a two-turn kill from a grind
    return (a if won else (b if not alive_a else None)), stats.get("turns", cap_turns)


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
    # rctmod-server.toml, verbatim: "The level cap of a player is based off the strongest pokemon from the party
    # of their NEXT required trainer ... The relativeLevelCap is added to the resulting value." So entering gym N
    # the cap is that gym's ace PLUS relativeLevelCap, not the ace itself. Running it at the ace understated the
    # player by five levels at every gym (found 2026-09-23).
    cap = (max(m["level"] for m in t["team"]) + rel) if t and t["team"] else None
    if cap is not None:
        cap = max(cap, init if gym == 1 else 0)
    out = {"gym": gym, "theme": avail[gym]["theme"], "leader": avail[gym]["leader"],
           "cap": cap, "candidates": [], "team": t["team"] if t else [],
           "status": t["status"] if t else "missing"}
    if not t or not t["team"]:
        return out
    foes = build_leader(t, species, moves, chart, ivs, stones)
    out["foes"] = foes
    seen = set()
    # A candidate the jar does not know is COUNTED, not dropped in silence. Gendered Nidoran fell out of Gym 8's
    # pool for exactly this reason and nothing said so (found by the test author, 2026-09-23): a shrinking pool
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
            w, n = duel(p, f, moves, chart, species=species)
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
        won, _f, downed, left = run_gauntlet([p], [ace], moves, chart, species=species)
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

    # Two teams, and each run twice: never switching is the worst case for the player and free switching is
    # the best, so the real fight sits between them. The leader never switches in either, which matches
    # data/trainers.json's own AI profile only loosely -- it declares a switchBias of 0.65.
    for how in ("informed", "walked"):
        for sw in (False, True):
            team = pick_team(out["candidates"], species, moves, chart, cap, ivs, stones, how)
            won, faints, downed, left = run_gauntlet(
                team, build_leader(t, species, moves, chart, ivs, stones), moves, chart,
                species=species, switching=sw)
            out[how + ("_switch" if sw else "")] = {"team": [m.name for m in team], "won": won,
                                                    "faints": faints, "downed": downed, "left": left}
    return out


def config_starters():
    """Every species the pack actually offers, from the config the game falls back to.

    `useConfigStarters: false` is Cobblemon's own default and does NOT disable this file: with no starter
    datapack present -- and the server has none -- `CobblemonStarterHandler.getStarterList` falls straight back
    to the config list. So the offer is 13 categories, not the Kanto three
    (docs/research/notes/starter-selection.md).
    """
    # the overlay is what players install, so it wins over the base pack when one exists
    src = STARTER_OVERLAY if STARTER_OVERLAY.is_file() else STARTER_CONFIG
    d = json.loads(src.read_text(encoding="utf-8"))
    out = []
    for cat in d.get("starters") or []:
        for entry in cat.get("pokemon") or []:
            name = entry.split()[0]
            if key(name) not in out:
                out.append(key(name))
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
            beats = [f.name for f in a["foes"] if duel(p, f, moves, chart, species=species)[0] is p]
            res[g] = (p.name, len(beats), len(a["foes"]))
        out[s] = res
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gym", type=int)
    ap.add_argument("--ivs", type=int, default=15)
    ap.add_argument("--cap-offset", type=int, default=None,
                    help="override relativeLevelCap: 0 is what GYM_SUFFICIENCY_AUDIT.md recommends")
    ap.add_argument("--stones", action="store_true")
    ap.add_argument("--switching", action="store_true",
                    help="also run the player-side switching bound: see LIMITS, it is not yet sound")
    ap.add_argument("--markdown")
    a = ap.parse_args(argv)

    jar = find_jar()
    species, moves, chart = load_pack(jar)
    avail = parse_availability(AVAILABILITY)
    leaders, contract = gym_leaders()
    caps = level_caps(RCT_CONFIG)
    if a.cap_offset is not None:
        caps = (caps[0], a.cap_offset)

    lines = []

    def say(s=""):
        lines.append(s)
        print(s)

    say("Cobblemon jar: %s" % jar.name)
    say("species %d, moves %d, types %d; IVs %d, EVs 0, %s evolutions"
        % (len(species), len(moves), len(chart), a.ivs, "level and item" if a.stones else "level only"))
    say("level cap: initial %d, relative %+d -- so the player meets each gym at its ace %+d" % (caps + (caps[1],)))
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
            say("  gauntlet, %-8s team %s" % (how, ", ".join(r[how]["team"])))
            modes = [("no switching", how)] + ([("switching bound", how + "_switch")] if a.switching else [])
            for label, k in modes:
                g = r[k]
                say("      %-15s %s -- %d of %d downed, %d lost%s"
                    % (label, "WIN " if g["won"] else "LOSS", g["downed"], n_foes, g["faints"],
                       "" if g["won"] else ", next foe on %.0f%%" % (g["left"] * 100)))
        top = cands[:8] if not a.gym else cands
        for c in top:
            say("    %-12s as %-12s %-16s %d/%d  first wild L%-3d %s"
                % (c["caught_as"], c["used_as"], c["types"], c["n"], n_foes, c["first_at"],
                   ",".join(c["beats"]) if c["n"] else ""))
        say("")

    say("=" * 100)
    say("STARTERS")
    starters = config_starters()
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
