#!/usr/bin/env python
"""Simulate each dungeon for the teams of its areas (unit DG-SIM, 2026-10-10). No server, no Minecraft, no play.

The owner (2026-10-10, docs/mechanics/DUNGEON_PASS2.md "Next phase"): "simulate the dungeon for teams in the areas" --
difficulty measured against the teams a player realistically has when they reach each band, not guessed.

WHAT IT DOES. For each dungeon x band x player cap (the band's lower and upper cap) it builds plausible teams from the
species a player can have caught by then, at the cap, with movesets from the jar's learnsets, and walks them through
the dungeon's fights IN ORDER, health and PP carried, with the safe room's one heal and the boss chain's full heal between its two
stages (DUNGEONS.md 3.2). It reports the win rate, the fight that kills most runs, HP and PP left at the boss, any
fight that is impossible or trivial, and prices the run's fight time against the clock.

WHERE EVERY INPUT COMES FROM (nothing is retyped here):

  the fights     the GENERATED data: tools/dungeon_fights.py stand_classes / wild_spawns (stands, gauntlets, the
                 miniboss, nest and habitat Pokemon), tools/dungeon.py boss_classes (the boss's stages),
                 tools/dungeon_prize.py species_at / level_at (the hidden prize), the safe room's healer from the
                 record. Rooms are walked in record order by tools/dungeon_rooms.flatten.
  the levels     data/dungeons.json engine.bands caps and engine.stands (via the generators above).
  the pool       docs/story/AVAILABILITY.md (derived/availability.json when present): the species catchable before
                 each gym, cumulative; gym N's list serves a player whose cap is gym N's ace (20, 25 ... 55); caps 60,
                 62 and 100 take gym 8's list with item evolutions allowed.
  the moves      the Cobblemon 1.8.0 jar: species learnsets, Showdown moves.js (power, type, PP, recoil, drain,
                 multi-hit, charge/recharge) and typechart.js, through tools/battle_sim.py's loaders. A player's TM
                 moves are the ones whose gate badge (docs/mechanics/TM_POWER_GATE.json power_badge) is at most the
                 badges the cap implies (cap 25 = 1 badge ... 55 = 7, 60+ = 8; TM_POWER_GATE.md section 1).
  the clock      tools/dungeon_clock.py (the walk, the planning fight paces, slack_factor).

HOW A FIGHT RUNS. The damage arithmetic is tools/battle_sim.py's (mainline formula, STAB, the type chart, the listed
abilities and statuses); the battle LOOP is this file's, because battle_sim's resets every Pokemon at the start of a
battle and cannot carry health across a dungeon. Differences from battle_sim, each deliberate:

  carry         HP, status and PP persist from fight to fight; a heal event restores all (and revives, assumed).
  PP            every move has its Showdown PP; an empty set falls back to Struggle.
  a free choice the player picks the best matchup at the start of a battle and after each faint (the game lets you);
                it never switches voluntarily mid-fight (battle_sim's switching bound is documented as unsound).
  rolls         damage carries a 0.85-1.00 roll per hit (mean 0.925 = battle_sim's constant) and IVs are drawn per
                Pokemon, from a seeded generator, so a result is a rate over samples and is exactly reproducible.
  moves         multi-hit moves count their mean hits (2-5 = 3.1), recoil and drain are applied, fixed-damage moves
                (Seismic Toss, Night Shade) deal the user's level, and a player never carries a move the loop cannot
                play (charge turns, recharge, self-destruct, Fake Out and the like).
  absorbers     evaluating a move never triggers Water Absorb and kin (battle_sim's `damage` heals the holder as a side
                effect of merely previewing). A move an absorber would soak is simply not chosen, so the heal or boost
                never fires: the foe's AI is not modelled blundering into one.

WHAT IT CANNOT MODEL (the report repeats this; "unmeasured" means no run here moves it, so its size is unknown):

  - abilities beyond battle_sim's list, and every held item on either side (a trainer's NPC party string carries none;
    players carry none here). Unmeasured. Choice/Life Orb/Leftovers players would be stronger; ability-driven foes
    (Static, Poison Point, Regenerator, weather setters) would be stronger.
  - secondary effects (flinch, burn/freeze/para chance), crits, Protect, hazards, and screens or status moves by the player.
    Unmeasured. Only the foe's status moves under --foe-moves latest are played.
  - the foe's real moveset: a datapack NPC party string names species and level only. `smart` (default) gives the foe
    battle_sim's best-damage level-up set; `latest` the last four level-up moves (Cobblemon's initial-moveset preference
    is unproven here). The sensitivity table measures the difference. Foe AI skill 3 is not modelled.
  - voluntary switching: the player never switches mid-fight, and a real player who does has an edge the sim cannot price
    (battle_sim's own switching bound is documented as unsound). Unmeasured; the bag, under-level, no-TM and latest-four
    rows bound the other assumptions, not this one.
  - bag items beyond --bag, and the real death rule (a loss here ends the run).
  - a wild Pokemon fleeing, a nest Pokemon wandering, catching instead of fighting.
  - real fight time: the setup/round/faint seconds are planning figures; XT1 (EXP-079) timed no fight.
  - whether Cobblemon's Showdown computes damage as the mainline formula does (battle_sim documents this gap).

OPTIONAL fights (a wing's prize, a nest with clear "pass", an optional fork route) are not in the required sequence; each
is run on its own from a rested team and listed separately.

  python tools/dungeon_sim.py                       # all dungeons, all bands, a compact table + derived/dungeon_sim/report.md
  python tools/dungeon_sim.py --dungeon jungle --band 3 --samples 12
  python tools/dungeon_sim.py --under 3             # players three levels under the cap
  python tools/dungeon_sim.py --moves levelup       # no TMs (the floor)  /  --foe-moves latest
  python tools/dungeon_sim.py --bag 4               # players carry four full-heal/revive uses (never used between boss stages)
  python tools/dungeon_sim.py --advise --sensitivity   # the full report: measured single changes for each failing cell, and
                                                    # the bag / under-levelled / no-TM / latest-four rows (about 3 minutes)

Each cell also fights the gym leader whose ace is the cap, rested, with the same teams: the difficulty the campaign already
asks of a player at that cap (data/trainers.json; not a dungeon fight).

derived/dungeon_sim/ is gitignored derived output: it is rebuilt by this command and never hand-edited.
"""
from __future__ import annotations

import argparse
import functools
import itertools
import json
import math
import random
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import battle_sim as BS  # noqa: E402
import dungeon as DG  # noqa: E402
import dungeon_clock as DC  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_prize as DP  # noqa: E402
import dungeon_rooms as R  # noqa: E402

DATA = ROOT / "data" / "dungeons.json"
TM_GATE = ROOT / "docs" / "mechanics" / "TM_POWER_GATE.json"
AVAIL_MD = ROOT / "docs" / "story" / "AVAILABILITY.md"
AVAIL_JSON = ROOT / "derived" / "availability.json"
OUT_DIR = ROOT / "derived" / "dungeon_sim"

# This tool never decides where anything goes and reads no world (tests/test_ground_rule.py).
WORLD_READS = set()

# ---- planning constants, all UNMEASURED (XT1, EXP-079, timed no fight): the seconds a fight takes in play
FIGHT_SETUP_S = 15       # the approach, the banner, the first send-out
TURN_S = 8               # one round: pick a move, the animations, the text
FAINT_S = 8              # the replacement prompt after each of the player's faints
TURN_CAP = 300           # a battle that has not ended by here is a draw (counted as not won)
ROLL_LO, ROLL_HI = 0.85, 1.0
MEAN_ROLL = 0.925        # battle_sim.damage's constant: the factor a roll is divided by

# cap -> the gym whose availability list serves a player at that cap (availability.py CAPS: gym N's cap is its ace)
CAP_GYM = {20: 1, 25: 2, 30: 3, 35: 4, 40: 5, 45: 6, 50: 7, 55: 8}
STONE_FROM_CAP = 60      # caps 60, 62 and 100 are after gym 8: item evolutions allowed (assumed; see the report)

# Moves the loop cannot play faithfully, so a player's set never carries them (the foe's smart set may: it only
# ever takes battle_sim's choice). Charge/recharge/selfdestruct flags are read from the jar as well.
UNPLAYABLE = {"fakeout", "firstimpression", "suckerpunch", "focuspunch", "dreameater", "lastresort", "belch",
              "futuresight", "doomdesire", "steelroller", "aurawheel", "thunderclap", "poltergeist", "counter",
              "mirrorcoat", "metalburst", "bide", "snore", "sleeptalk", "spitup", "uproar", "burnup", "doubleshock",
              "fling", "naturalgift", "struggle", "synchronoise", "dragonrage", "sonicboom", "superfang",
              "naturesmadness", "ruination", "endeavor", "finalgambit", "rage", "outrage", "thrash", "petaldance"}


class SimError(Exception):
    pass


# ------------------------------------------------------------------------------------------------- the pack

class Pack:
    """species, the effective moves table (multi-hit folded into power), the type chart and per-move extras."""

    def __init__(self, species, moves, chart, extras):
        self.species = species
        self.chart = chart
        self.extras = extras
        self.moves = {}
        for mid, mv in moves.items():
            hits = extras.get(mid, {}).get("hits", 1.0)
            self.moves[mid] = dict(mv, power=mv["power"] * hits) if hits != 1.0 and mv["power"] > 0 else mv
        self.raw_moves = moves


def jar_path():
    return DP.JAR if DP.JAR.is_file() else BS.find_jar()


def parse_extras(text):
    """{move id: {pp, recoil (n, d), drain (n, d), hits, unplayable, fixed ("level" or int)}} from Showdown's moves.js."""
    out = {}
    for m in BS.ENTRY.finditer(text):
        mid, body = m.group(1), m.group(2)
        e = {}
        pp = re.search(r"^    pp: (\d+)", body, re.M)
        e["pp"] = int(pp.group(1)) if pp else 10
        rec = re.search(r"^    recoil: \[(\d+), (\d+)\]", body, re.M)
        if rec:
            e["recoil"] = (int(rec.group(1)), int(rec.group(2)))
        dr = re.search(r"^    drain: \[(\d+), (\d+)\]", body, re.M)
        if dr:
            e["drain"] = (int(dr.group(1)), int(dr.group(2)))
        mh = re.search(r"^    multihit: (?:\[(\d+), (\d+)\]|(\d+))", body, re.M)
        if mh:
            if mh.group(3):
                e["hits"] = float(mh.group(3))
            else:
                lo, hi = int(mh.group(1)), int(mh.group(2))
                e["hits"] = 3.1 if (lo, hi) == (2, 5) else (lo + hi) / 2.0     # Showdown's 2-5 is 35/35/15/15 %
        fl = re.search(r"flags: \{([^}]*)\}", body)
        flags = fl.group(1) if fl else ""
        if re.search(r"\b(charge|recharge): 1", flags) or re.search(r"^    selfdestruct:", body, re.M):
            e["unplayable"] = True
        dm = re.search(r'^    damage: ("level"|\d+)', body, re.M)
        if dm:
            e["fixed"] = "level" if dm.group(1) == '"level"' else int(dm.group(1))
        out[mid] = e
    return out


@functools.lru_cache(maxsize=2)
def load_pack(jar=None):
    jar = Path(jar) if jar else jar_path()
    species, moves, chart = BS.load_pack(jar)
    text = zipfile.ZipFile(jar).read(BS.SHOWDOWN + "moves.js").decode("utf8", "replace")
    return Pack(species, moves, chart, parse_extras(text))


# ------------------------------------------------------------------------------------------------- availability, TMs

ROW = re.compile(r"^\| ([a-z0-9_\-]+) \| ([a-z/]+) \| (\d+)-(\d+) \|", re.M)


def parse_availability_md(text):
    """{gym: [{species, lo, hi}]} from the committed AVAILABILITY.md (each gym's table is cumulative)."""
    out = {}
    parts = re.split(r"^## ", text, flags=re.M)
    for part in parts:
        m = re.match(r"Gym (\d+):", part)
        if not m:
            continue
        rows = [{"species": r.group(1), "lo": int(r.group(3)), "hi": int(r.group(4))} for r in ROW.finditer(part)]
        out[int(m.group(1))] = rows
    return out


@functools.lru_cache(maxsize=1)
def availability():
    if AVAIL_JSON.is_file():
        d = json.loads(AVAIL_JSON.read_text(encoding="utf-8"))
        out = {int(g): [{"species": r["species"], "lo": r["lo"], "hi": r["hi"]} for r in rows] for g, rows in d["gyms"].items()}
    else:
        out = parse_availability_md(AVAIL_MD.read_text(encoding="utf-8"))
    if sorted(out) != list(range(1, 9)) or any(not v for v in out.values()):
        raise SimError("availability: gyms 1..8 with species expected, got %s" % {g: len(v) for g, v in out.items()})
    return out


def gym_of_cap(cap):
    return CAP_GYM.get(cap, 8)


def badges_of_cap(cap):
    """Badges the cap implies (TM_POWER_GATE.md section 1: badge 1 = cap 25 ... badge 7 = cap 55; the Elite Four after)."""
    return 8 if cap >= STONE_FROM_CAP else max(0, (cap - 20) // 5)


@functools.lru_cache(maxsize=1)
def tm_badges():
    """{move id: gate badge}: 'tmcraft:tm_<move>' -> power_badge in docs/mechanics/TM_POWER_GATE.json."""
    d = json.loads(TM_GATE.read_text(encoding="utf-8"))
    return {k.split("tm_", 1)[1]: v["power_badge"] for k, v in d["tms"].items()}


# ------------------------------------------------------------------------------------------------- building a Pokemon

def init_pp(pack, mon):
    mon.moves_all = list(mon.moveset)
    mon.pp_max = {m: pack.extras.get(m, {}).get("pp", 10) for m in mon.moves_all}
    mon.pp = dict(mon.pp_max)
    return mon


def draw_ivs(rng):
    """One IV for all six stats (battle_sim.Mon takes a single number): the mean of six 0-31 draws, which is what the
    average stat of a wild catch or an NPC party member is."""
    if rng is None:
        return 15
    return int(round(sum(rng.randint(0, 31) for _ in range(6)) / 6.0))


def candidate_moves(pack, sp, level, policy, badges):
    ids = BS.level_moves(sp, level)
    if policy == "tm":
        gate = tm_badges()
        for entry in sp.get("moves") or []:
            if entry.startswith("tm:"):
                mid = entry[3:]
                if gate.get(mid, 99) <= badges:
                    ids.append(mid)
    out = []
    for mid in dict.fromkeys(ids):
        if mid in UNPLAYABLE or pack.extras.get(mid, {}).get("unplayable"):
            continue
        mv = pack.moves.get(mid)
        if mv:
            out.append(mid)
    return out


@functools.lru_cache(maxsize=None)
def player_moveset(pack_id, name, level, policy, badges):
    """Four damaging moves a sensible player carries: the best-scoring move of each type (STAB x power x accuracy),
    best four of those. Same rule as battle_sim.choose_moveset, over the TM-extended candidates."""
    pack = _PACKS[pack_id]
    sp = pack.species[name]
    types = [t.lower() for t in (sp.get("primaryType"), sp.get("secondaryType")) if t]
    best_by_type = {}
    for mid in candidate_moves(pack, sp, level, policy, badges):
        mv = pack.moves[mid]
        power = mv["power"] if mv["power"] > 0 else BS.VARIABLE_NOMINAL.get(mid, 0)
        fixed = pack.extras.get(mid, {}).get("fixed")
        if fixed is not None:
            continue                              # excluded by UNPLAYABLE for the player; kept here as a belt
        if power <= 0:
            continue
        score = power * (1.5 if mv["type"].lower() in types else 1.0) * mv["accuracy"] / 100.0
        cur = best_by_type.get(mv["type"])
        if cur is None or score > cur[0]:
            best_by_type[mv["type"]] = (score, mid)
    picked = [mid for _s, mid in sorted(best_by_type.values(), reverse=True)][:4]
    return tuple(picked)


_PACKS = {}


def pack_id(pack):
    _PACKS[id(pack)] = pack
    return id(pack)


def make_player(pack, name, level, rng, policy="tm", badges=0):
    ms = player_moveset(pack_id(pack), name, level, policy, badges)
    if not ms:
        raise SimError("no playable damaging move for %s at level %d" % (name, level))
    mon = BS.Mon(pack.species, name, level, pack.moves, pack.chart, ivs=draw_ivs(rng), moveset=list(ms))
    return init_pp(pack, mon)


def foe_moveset(pack, name, level, how):
    sp = pack.species[name]
    if how == "latest":
        seen, last = set(), []
        for mid in reversed(BS.level_moves(sp, level)):
            if mid in pack.moves and mid not in seen:
                seen.add(mid)
                last.append(mid)
            if len(last) == 4:
                break
        ms = last
    else:
        ms = BS.choose_moveset(sp, level, pack.moves, pack.chart)
    return ms or ["struggle"]


def make_foe(pack, species, level, rng, how="smart"):
    name = BS.key(species)
    if name not in pack.species:
        raise SimError("the jar has no species %r" % species)
    mon = BS.Mon(pack.species, name, level, pack.moves, pack.chart, ivs=draw_ivs(rng),
                 moveset=foe_moveset(pack, name, level, how))
    return init_pp(pack, mon)


# ------------------------------------------------------------------------------------------------- the battle

class Ctx:
    def __init__(self, pack, rng=None):
        self.pack = pack
        self.rng = rng

    def roll(self):
        """The factor on a hit's damage: the roll over battle_sim's mean roll (1.0 with no generator)."""
        if self.rng is None:
            return 1.0
        return self.rng.uniform(ROLL_LO, ROLL_HI) / MEAN_ROLL


def usable(mon):
    ms = [m for m in mon.moves_all if mon.pp.get(m, 0) > 0]
    return ms or ["struggle"]


def preview(att, dfn, mid, ctx, field):
    """The expected damage of a move, with NO side effects (battle_sim.damage heals an absorber as it evaluates)."""
    pack = ctx.pack
    mv = pack.moves.get(mid)
    if not mv:
        return 0.0
    ab = BS.ABSORB.get(dfn.ability)
    if ab and ab[0] == mv["type"] and att.ability != "moldbreaker":
        return 0.0
    fixed = pack.extras.get(mid, {}).get("fixed")
    if fixed is not None:
        if BS.effectiveness(pack.chart, mv["type"], dfn.types) == 0.0:
            return 0.0
        return float(att.level if fixed == "level" else fixed) * mv["accuracy"] / 100.0
    return BS.damage(att, dfn, mid, pack.moves, pack.chart, field, pack.species)


def choose_action(att, dfn, ctx, field):
    best, pick = 0.0, None
    for mid in usable(att):
        d = preview(att, dfn, mid, ctx, field)
        if d > best:
            best, pick = d, mid
    if pick:
        return ("attack", pick, best)
    for m in usable(att):
        if m in att.used_once:
            continue
        if m in BS.HEAL_MOVES:
            if att.hp_now <= att.hp * 0.6:
                att.used_once.discard(m)
                return ("support", m, 0.0)
            continue
        if (m in BS.BOOST_MOVES or m in BS.DROP_MOVES or m in BS.STATUS_MOVES or m in BS.SCREEN_MOVES
                or m in BS.WEATHER_MOVES):
            return ("support", m, 0.0)
    return ("stall", None, 0.0)


def matchup(m, foe, ctx, field):
    """How well m does against foe, in turns of margin (BS.best_matchup's score, plus half a turn for moving first)."""
    mine = max((preview(m, foe, mid, ctx, field) for mid in usable(m)), default=0.0)
    if mine <= 0:
        return -999.0
    theirs = max((preview(foe, m, mid, ctx, field) for mid in usable(foe)), default=0.0)
    t_me = foe.hp_now / mine
    t_them = (m.hp_now / theirs) if theirs > 0 else 999.0
    return t_them - t_me + (0.5 if m.eff_spe() >= foe.eff_spe() else 0.0)


def pick_next(team, spent, foe, ctx, field):
    best, pick = None, None
    for i, m in enumerate(team):
        if m.hp_now <= 0 or i in spent:
            continue
        s = matchup(m, foe, ctx, field)
        if best is None or s > best:
            best, pick = s, i
    return pick


def enter_field(mon, foe, field):
    w = BS.WEATHER_ABILITY.get(mon.ability)
    if w:
        field.weather = w
    BS.switch_in(mon, foe)


def begin_battle(mon, side):
    """Start of a battle for a Pokemon that already has health, status and PP: clear only what a battle clears."""
    mon.side = side
    mon.stages = {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
    mon.used_once = set()
    mon.tox_turns = 0
    mon.sleep_turns = 0
    mon.hit_this_turn = False


def heal_party(team):
    """The safe room's `healpokemon @s`: everyone whole, PP and status restored. Fainted Pokemon are revived (assumed:
    Cobblemon's /healpokemon heals the whole party; the revive is unproven)."""
    for m in team:
        m.hp_now = float(m.hp)
        m.status = None
        m.pp = dict(m.pp_max)


class Result:
    def __init__(self):
        self.won = False
        self.turns = 0
        self.faints = 0
        self.hp_lost = 0.0        # share of the team's total max HP lost in this battle
        self.killers = []         # the foe species active when each player Pokemon fell
        self.foe_left = 1.0       # the active foe's HP share at the end when lost

    def seconds(self):
        return FIGHT_SETUP_S + TURN_S * self.turns + FAINT_S * self.faints


def run_battle(team, foes, ctx):
    """The player's team (health carried) against `foes` (fresh), the foes in order. Returns a Result."""
    pack = ctx.pack
    res = Result()
    field = BS.Field()
    for m in team:
        begin_battle(m, "player")
    for f in foes:
        f.enter("foe")
    total = float(sum(m.hp for m in team))
    before = sum(max(0.0, m.hp_now) for m in team)
    spent = set()
    j = 0
    cur = pick_next(team, spent, foes[0], ctx, field)
    if cur is None:
        res.foe_left = 1.0
        return res
    enter_field(team[cur], foes[0], field)
    enter_field(foes[0], team[cur], field)
    while j < len(foes) and res.turns < TURN_CAP:
        a, b = team[cur], foes[j]
        res.turns += 1
        mine = choose_action(a, b, ctx, field)
        theirs = choose_action(b, a, ctx, field)
        if mine[0] == "stall" and theirs[0] == "stall":
            spent.add(cur)
            nxt = pick_next(team, spent, b, ctx, field)
            if nxt is None:
                break
            cur = nxt
            enter_field(team[cur], b, field)
            continue
        acts = [(a, b, mine), (b, a, theirs)]
        if a.eff_spe() < b.eff_spe():
            acts.reverse()
        for att, dfn, (kind, mid, dmg) in acts:
            if att.hp_now <= 0 or dfn.hp_now <= 0:
                continue
            if att.status == "par":
                dmg *= 0.75
            if att.status == "slp":
                att.sleep_turns += 1
                if att.sleep_turns <= 2:
                    continue
                att.status = None
            if kind == "attack":
                _attack(att, dfn, mid, dmg, ctx, field)
            elif kind == "support":
                if mid in att.pp:
                    att.pp[mid] = max(0, att.pp[mid] - 1)
                BS.apply_support(att, dfn, mid, field, pack.moves)
        for m in (a, b):
            BS.end_of_turn(m, field)
        if b.hp_now <= 0:
            j += 1
            if j < len(foes):
                enter_field(foes[j], team[cur], field)
        if a.hp_now <= 0:
            res.faints += 1
            res.killers.append(b.name)
            if j >= len(foes):
                break
            nxt = pick_next(team, spent, foes[j], ctx, field)
            if nxt is None:
                break
            cur = nxt
            enter_field(team[cur], foes[j], field)
    res.won = j >= len(foes)
    if not res.won and j < len(foes):
        res.foe_left = max(0.0, foes[j].hp_now / foes[j].hp)
    after = sum(max(0.0, m.hp_now) for m in team)
    res.hp_lost = (before - after) / total if total else 0.0
    return res


def _attack(att, dfn, mid, dmg, ctx, field):
    pack = ctx.pack
    mv = pack.moves[mid]
    ex = pack.extras.get(mid, {})
    if mid in att.pp:
        att.pp[mid] = max(0, att.pp[mid] - 1)
    if dmg <= 0:
        return
    att.hit_this_turn = True
    before = max(0.0, dfn.hp_now)
    eff_super = BS.effectiveness(pack.chart, mv["type"], dfn.types) > 1
    BS.take_hit(dfn, att, dmg * ctx.roll(), eff_super, mv.get("contact", False))
    dealt = before - max(0.0, dfn.hp_now)
    if "recoil" in ex:
        att.hp_now -= dealt * ex["recoil"][0] / ex["recoil"][1]
    if "drain" in ex:
        att.hp_now = min(float(att.hp), att.hp_now + dealt * ex["drain"][0] / ex["drain"][1])
    if mid == "struggle":
        att.hp_now -= att.hp / 4.0


# ------------------------------------------------------------------------------------------------- the dungeon's fights

def parse_party(party):
    """['roggenrola level=18', ...] -> [('roggenrola', 18), ...]"""
    out = []
    for s in party:
        sp = s.split()[0]
        lv = int(re.search(r"level=(\d+)", s).group(1))
        out.append((sp, lv))
    return out


_ANCHORS = {"boss": (0, 0, 0, 0), "legendary": (0, 0, 0, 0), "spawns": [(0, 0, 0, 0)]}


def event(kind, label, room, foes, category, optional=False, **extra):
    e = {"kind": kind, "label": label, "room": room, "foes": foes, "category": category, "optional": optional}
    e.update(extra)
    return e


def room_events(doc, d, rec, band, optional=False):
    """The events of one room record at one band: fights from the generated classes, heals from the record."""
    kind = rec["kind"]
    p = rec.get("params") or {}
    out = []
    if kind in DF.KINDS_STAND and DF.is_stand_room(rec):
        classes = DF.stand_classes(doc, d, rec)
        for n, t in enumerate(DF.trainers_of(doc, rec), 1):
            name = DF.stand_class_name(d, rec, n, band)
            party = parse_party(classes[name][0]["party"]["pokemon"])
            cat = "gauntlet" if DF.mode_of(rec) == "gauntlet" else "stand"
            out.append(event("fight", "%s: %s" % (rec["id"], t["name"]), rec["id"], party, cat, optional))
    elif kind == "miniboss" and DF.is_wild_room(rec):
        for sp, lv, _props, _pos in DF.wild_spawns(doc, rec, _ANCHORS)[band]:
            out.append(event("fight", "%s: %s" % (rec["id"], sp), rec["id"], [(sp, lv)], "miniboss", optional))
    elif kind == "nest" and DF.is_wild_room(rec):
        pass_mode = p.get("clear", "all") == "pass"
        for k, (sp, lv, _props, _pos) in enumerate(DF.wild_spawns(doc, rec, _ANCHORS)[band], 1):
            out.append(event("fight", "%s: %s #%d" % (rec["id"], sp, k), rec["id"], [(sp, lv)], "nest",
                             optional or pass_mode))
    elif kind == "habitat" and DP.prize_of(rec):
        got = DP.species_at(doc, rec, band)
        if got:
            sp, legendary = got
            out.append(event("fight", "%s: prize %s" % (rec["id"], sp), rec["id"], [(sp, DP.level_at(doc, band))],
                             "prize", True, legendary=legendary))
    elif kind == "safe_room" and p.get("healer"):
        out.append(event("heal", "%s: the safe room's heal" % rec["id"], rec["id"], [], "heal", optional))
    elif kind == "boss_arena":
        for k in range(1, len(d["boss"]["stage_level_offsets"]) + 1):
            name = "dg_%s_boss_b%d_s%d" % (d["short"], band, k)
            party = parse_party(DG.boss_classes(doc, d)[name][0]["party"]["pokemon"])
            if k > 1 and d["boss"].get("heal_between_stages"):      # the chain's healpokemon (tools/dungeon.py `next`)
                out.append(event("heal", "the chain's heal before boss stage %d" % k, rec["id"], [], "heal", False))
            out.append(event("fight", "boss stage %d" % k, rec["id"], party, "boss", False, stage=k))
    return out


def route_choices(items):
    """[(label, chosen route names)] for every combination of the non-optional route of each fork."""
    forks = {}
    for it in items:
        rt = it["route"]
        if "/" in rt:
            f, k = rt.split("/", 1)
            if not it.get("optional"):
                forks.setdefault(f, [])
                if k not in forks[f]:
                    forks[f].append(k)
    names = sorted(forks)
    combos = []
    for pick in itertools.product(*[forks[f] for f in names]):
        combos.append(("+".join("%s=%s" % (f, k) for f, k in zip(names, pick)) or "main",
                       {"%s/%s" % (f, k) for f, k in zip(names, pick)}))
    return combos or [("main", set())]


def dungeon_paths(doc, d, band):
    """{"paths": [(label, [events])], "optional": [events]}: the required sequence for each route combination, and the
    fights off the required path (wings, fork routes marked optional, a nest that is only passed)."""
    items = R.flatten(d)
    paths = []
    for label, chosen in route_choices(items):
        seq = []
        for it in items:
            rt = it["route"]
            if rt == "main" or rt in chosen:
                seq += [e for e in room_events(doc, d, it["rec"], band, optional=False)]
        paths.append((label, seq))
    opt = []
    for it in items:
        rt = it["route"]
        wing = rt != "main" and "/" not in rt                   # a side entry: a dead-end wing
        opt_fork = "/" in rt and it.get("optional")
        if wing or opt_fork:
            opt += [dict(e, optional=True) for e in room_events(doc, d, it["rec"], band, optional=True)
                    if e["kind"] == "fight"]
    # a nest that is only passed sits in the main sequence as optional events: lift them out
    base = []
    for label, seq in paths:
        base.append((label, [e for e in seq if not e["optional"]]))
        for e in seq:
            if e["optional"] and e["kind"] == "fight" and e not in opt:
                opt.append(e)
    return {"paths": base, "optional": opt}


# ------------------------------------------------------------------------------------------------- teams

def pool_of(pack, cap, under):
    """{evolved species: first wild level} a player at `cap` can field: the availability list of the cap's gym, each
    caught form evolved as far as its level (and, from cap 60, item evolutions) allow."""
    rows = availability()[gym_of_cap(cap)]
    lvl = cap - under
    stones = cap >= STONE_FROM_CAP
    out = {}
    for r in rows:
        k = BS.key(r["species"])
        if k not in pack.species:
            continue
        ev = BS.evolve(pack.species, k, lvl, stones)
        out[ev] = min(out.get(ev, 999), r["lo"])
    return out


def bst(pack, name):
    return sum(pack.species[name]["baseStats"].values())


def cover(pack, moveset_names):
    """The set of defender types a moveset hits super effectively."""
    out = set()
    for mid in moveset_names:
        t = pack.moves[mid]["type"]
        for dt in pack.chart:
            if BS.effectiveness(pack.chart, t, [dt]) > 1:
                out.add(dt)
    return out


class Cell:
    """One (dungeon, band, cap) cell: its pool, and the builders of the four team archetypes."""

    def __init__(self, pack, cap, under, policy, foe_species):
        self.pack = pack
        self.cap = cap
        self.level = cap - under
        self.policy = policy
        self.badges = badges_of_cap(cap)
        self.pool = pool_of(pack, cap, under)
        self.names = []
        self.moveset = {}
        for n in sorted(self.pool):
            ms = player_moveset(pack_id(pack), n, self.level, policy, self.badges)
            if ms:
                self.names.append(n)
                self.moveset[n] = ms
        if len(self.names) < 6:
            raise SimError("cap %d: only %d usable families" % (cap, len(self.names)))
        self.foes = foe_species      # [(species, level)] the dungeon's distinct required foes

    def walked(self):
        return sorted(self.names, key=lambda n: (self.pool[n], n))[:6]

    def casual(self, rng):
        return rng.sample(self.names, 6)

    def balanced(self, rng):
        chosen, covered = [], set()
        left = list(self.names)
        while len(chosen) < 6:
            best, pick = None, None
            for n in left:
                new = len(cover(self.pack, self.moveset[n]) - covered)
                s = new * 10 + bst(self.pack, n) / 60.0 + rng.random() * 4
                if best is None or s > best:
                    best, pick = s, n
            chosen.append(pick)
            left.remove(pick)
            covered |= cover(self.pack, self.moveset[pick])
        return chosen

    def scouted(self, rng):
        """The best response to this dungeon's own roster: a player who read the board and brought the answers."""
        ctx = Ctx(self.pack, None)
        field = BS.Field()
        top = sorted(self.names, key=lambda n: -bst(self.pack, n))[:80]
        mons = {n: make_player(self.pack, n, self.level, None, self.policy, self.badges) for n in top}
        foes = [make_foe(self.pack, s, lv, None) for s, lv in self.foes]
        score = {}
        for n in top:
            row = []
            for f in foes:
                mu = matchup(mons[n], f, ctx, field)
                row.append(max(0.0, min(3.0, 1.0 + mu / 4.0)) if mu > 0 else 0.0)
            score[n] = row
        chosen = []
        for _ in range(6):
            best, pick = None, None
            for n in top:
                if n in chosen:
                    continue
                gain = sum(max(s - max([score[c][i] for c in chosen] or [0.0]), 0.0) for i, s in enumerate(score[n]))
                key = (round(gain, 3), bst(self.pack, n))
                if best is None or key > best:
                    best, pick = key, n
            chosen.append(pick)
        return chosen

    def build(self, names, rng):
        return [make_player(self.pack, n, self.level, rng, self.policy, self.badges) for n in names]


# ------------------------------------------------------------------------------------------------- running a cell

def pp_fraction(team):
    tot = sum(sum(m.pp_max.values()) for m in team)
    return sum(sum(m.pp.values()) for m in team) / tot if tot else 1.0


def hp_fraction(team):
    return sum(max(0.0, m.hp_now) for m in team) / float(sum(m.hp for m in team))


ITEM_S = 6               # planning: seconds to open the bag and use one item on one Pokemon
BAG_PER_GAP = 3          # at most this many uses between two fights (the clock pays for each)


def use_bag(team, left):
    """Between fights, spend bag uses the way a sensible player does: revive the biggest fainted Pokemon (to half), else
    fully heal the most hurt one while the team is under 70% health and someone is under half. One use = a Max Revive or a
    Max Potion class item; the dungeon and the economy decide how many a player really carries (bag size is the knob)."""
    used = 0
    while left - used > 0 and used < BAG_PER_GAP:
        down = [m for m in team if m.hp_now <= 0]
        if down:
            m = max(down, key=lambda x: x.hp)
            m.hp_now = m.hp * 0.5
            m.status = None
        else:
            hurt = [m for m in team if m.hp_now < m.hp * 0.5]
            if not hurt or hp_fraction(team) >= 0.7:
                break
            m = min(hurt, key=lambda x: x.hp_now / x.hp)
            m.hp_now = float(m.hp)
        used += 1
    return used


def run_sequence(team, events, ctx, foe_how, bag=0):
    """Walk the team through the events. Returns {cleared, failed_at, results, boss_hp, boss_pp, fight_s, bag_used}.
    The bag is spent before a fight, never between the boss's stages (the 60-tick gap: DUNGEONS.md 3.2)."""
    results = []
    out = {"cleared": True, "failed_at": None, "boss_hp": None, "boss_pp": None, "fight_s": 0.0, "bag_used": 0}
    for i, ev in enumerate(events):
        if ev["kind"] == "heal":
            heal_party(team)
            results.append(None)
            continue
        if bag - out["bag_used"] > 0 and not (ev["category"] == "boss" and ev.get("stage", 1) > 1):
            n = use_bag(team, bag - out["bag_used"])
            out["bag_used"] += n
            out["fight_s"] += n * ITEM_S
        if ev["category"] == "boss" and ev.get("stage") == 1:
            out["boss_hp"], out["boss_pp"] = hp_fraction(team), pp_fraction(team)
        foes = [make_foe(ctx.pack, s, lv, ctx.rng, foe_how) for s, lv in ev["foes"]]
        r = run_battle(team, foes, ctx)
        results.append(r)
        out["fight_s"] += r.seconds()
        if not r.won:
            out["cleared"] = False
            out["failed_at"] = i
            break
    out["results"] = results
    return out


def distinct_foes(paths):
    seen = []
    for _label, seq in paths:
        for e in seq:
            for f in e["foes"]:
                if f not in seen:
                    seen.append(f)
    return seen


ARCHETYPES = ("walked", "balanced", "casual", "scouted")


def run_cell(doc, d, band_entry, cap, opts):
    """All the samples of one (dungeon, band, cap) cell. Returns a plain dict (picklable)."""
    pack = load_pack()
    band = band_entry["band"]
    pe = dungeon_paths(doc, d, band)
    cell = Cell(pack, cap, opts["under"], opts["moves"], distinct_foes(pe["paths"]))
    seed = "%s/%s/%d/%d" % (opts["seed"], d["id"], band, cap)
    plan = [("walked", 1), ("scouted", 1), ("balanced", opts["samples"]), ("casual", opts["samples"])]
    teams = []
    for arch, n in plan:
        for i in range(n):
            rng = random.Random("%s/%s/%d" % (seed, arch, i))
            if arch == "walked":
                names = cell.walked()
            elif arch == "scouted":
                names = cell.scouted(rng)
            elif arch == "balanced":
                names = cell.balanced(rng)
            else:
                names = cell.casual(rng)
            teams.append((arch, i, names))
    runs = []
    whatif = opts.get("whatif")
    paths = [(l, WHATIFS[whatif](seq) if whatif else seq) for l, seq in pe["paths"]]
    for arch, i, names in teams:
        for pi, (label, seq) in enumerate(paths):
            for rep in range(opts["reps"]):
                rng = random.Random("%s/%s/%d/%d/%d/%d" % (seed, arch, i, pi, rep, 1))
                team = cell.build(names, rng)
                ctx = Ctx(pack, rng)
                s = run_sequence(team, seq, ctx, opts["foe_moves"], opts["bag"])
                runs.append({"arch": arch, "team": [m.name for m in team], "path": label, "pi": pi,
                             "cleared": s["cleared"], "failed_at": s["failed_at"], "boss_hp": s["boss_hp"],
                             "boss_pp": s["boss_pp"], "fight_s": s["fight_s"], "bag_used": s["bag_used"],
                             "per_event": [None if r is None else
                                           {"won": r.won, "turns": r.turns, "faints": r.faints, "hp_lost": r.hp_lost,
                                            "killers": r.killers, "s": r.seconds()} for r in s["results"]]})
    if whatif or opts.get("lean"):
        return {"dungeon": d["id"], "band": band, "cap": cap, "runs": runs, "iso": {}, "gym": None,
                "paths": [(l, [dict(e) for e in seq]) for l, seq in paths], "optional": [], "pool": len(cell.names)}
    # each fight on its own, from a rested team: the fight's difficulty without the run behind it
    iso = defaultdict(lambda: defaultdict(list))
    isolated_events = {}
    all_events = []
    for _l, seq in pe["paths"]:
        for e in seq:
            if e["kind"] == "fight" and e["label"] not in isolated_events:
                isolated_events[e["label"]] = e
    for e in pe["optional"]:
        isolated_events.setdefault(e["label"], e)
    for arch, i, names in teams:
        for label, e in isolated_events.items():
            rng = random.Random("%s/%s/%d/iso/%s" % (seed, arch, i, label))
            team = cell.build(names, rng)
            ctx = Ctx(pack, rng)
            foes = [make_foe(pack, s, lv, rng, opts["foe_moves"]) for s, lv in e["foes"]]
            r = run_battle(team, foes, ctx)
            iso[label][arch].append({"won": r.won, "hp_lost": r.hp_lost, "faints": r.faints, "turns": r.turns,
                                     "killers": r.killers, "s": r.seconds()})
    gym = gym_reference(pack, cell, teams, cap, opts, seed)
    return {"dungeon": d["id"], "band": band, "cap": cap, "runs": runs, "iso": {k: dict(v) for k, v in iso.items()},
            "gym": gym,
            "paths": [(l, [dict(e) for e in seq]) for l, seq in pe["paths"]],
            "optional": [dict(e) for e in pe["optional"]], "pool": len(cell.names)}


def _map_events(seq, cats, fn):
    return [dict(e, foes=fn(e["foes"])) if (e["kind"] == "fight" and e["category"] in cats) else e for e in seq]


def _insert_heals(seq, before_boss_stage):
    out = []
    for e in seq:
        if e["kind"] == "fight" and e["category"] == "boss" and e.get("stage") in before_boss_stage                 and not (out and out[-1]["kind"] == "heal"):
            out.append(event("heal", "a heal before boss stage %d (what-if)" % e["stage"], e["room"], [], "heal"))
        out.append(e)
    return out


def _midfield_heal(seq):
    """A second heal halfway through the fights that come before the boss (none if there is one right there already)."""
    first_boss = next((i for i, e in enumerate(seq) if e["category"] == "boss"), len(seq))
    fights = [i for i, e in enumerate(seq[:first_boss]) if e["kind"] == "fight"]
    if len(fights) < 2:
        return list(seq)
    at = fights[len(fights) // 2]
    if at > 0 and seq[at - 1]["kind"] == "heal":
        return list(seq)
    return seq[:at] + [event("heal", "a second heal (what-if)", "mid", [], "heal")] + seq[at:]


# What a designer could change, each as a transform of the required event list. Paired with the base run: the same
# teams, seeds and rolls, so a difference is the change and not the sampling.
WHATIFS = {
    "boss -1 member": lambda seq: _map_events(seq, ("boss",), lambda f: f[1:] if len(f) > 1 else f),
    "boss -2 levels": lambda seq: _map_events(seq, ("boss",), lambda f: [(sp, max(1, lv - 2)) for sp, lv in f]),
    "heal between boss stages": lambda seq: _insert_heals(seq, (2, 3)),   # a no-op where the record already heals
    "heal before the boss": lambda seq: _insert_heals(seq, (1,)),
    "second heal mid-field": _midfield_heal,
    "stands -1 member": lambda seq: _map_events(seq, ("stand", "gauntlet"), lambda f: f[1:] if len(f) > 1 else f),
    "stands -2 levels": lambda seq: _map_events(seq, ("stand", "gauntlet"), lambda f: [(sp, max(1, lv - 2)) for sp, lv in f]),
}


def gym_reference(pack, cell, teams, cap, opts, seed):
    """The same teams against the gym leader whose ace is the cap (data/trainers.json, the authored roster with moves,
    items and abilities): the difficulty the campaign already asks of a player at this cap, one battle from a rested team.
    None for the caps after gym 8."""
    g = CAP_GYM.get(cap)
    if not g:
        return None
    leaders, _contract = BS.gym_leaders()
    t = leaders.get(g)
    if not t or not t.get("team"):
        return None
    rows = []
    for arch, i, names in teams:
        if arch not in TYPICAL:
            continue
        rng = random.Random("%s/%s/%d/gym" % (seed, arch, i))
        team = cell.build(names, rng)
        foes = [init_pp(pack, f) for f in BS.build_leader(t, pack.species, pack.moves, pack.chart, draw_ivs(rng), False)]
        r = run_battle(team, foes, Ctx(pack, rng))
        rows.append({"won": r.won, "hp_lost": r.hp_lost, "faints": r.faints})
    return {"gym": g, "leader": t.get("name") or t.get("id"), "win": rate([x["won"] for x in rows]),
            "hp_lost": mean([x["hp_lost"] for x in rows]), "faints": mean([x["faints"] for x in rows])}


# ------------------------------------------------------------------------------------------------- summaries

def rate(xs):
    return (sum(1 for x in xs if x) / len(xs)) if xs else float("nan")


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


TYPICAL = ("walked", "balanced", "casual")


def summarise(cellres):
    """The numbers one cell reports: win rates, the killer, HP and PP at the boss, per-fight table, fight time."""
    runs = cellres["runs"]
    typ = [r for r in runs if r["arch"] in TYPICAL]
    sc = [r for r in runs if r["arch"] == "scouted"]
    paths = dict((l, seq) for l, seq in cellres["paths"])
    out = {"win": rate([r["cleared"] for r in typ]), "win_scouted": rate([r["cleared"] for r in sc]),
           "n": len(typ), "pool": cellres["pool"]}
    # the worst route combination (lowest typical win rate)
    by_path = defaultdict(list)
    for r in typ:
        by_path[r["path"]].append(r["cleared"])
    out["by_path"] = {k: rate(v) for k, v in by_path.items()}
    out["win_worst_path"] = min(out["by_path"].values()) if out["by_path"] else float("nan")
    out["worst_path"] = min(out["by_path"], key=out["by_path"].get) if out["by_path"] else None
    # where runs end: label of the failed event, over typical runs, on the path of the run
    fails = Counter()
    killers = defaultdict(Counter)
    for r in typ:
        if r["failed_at"] is not None:
            lab = paths[r["path"]][r["failed_at"]]["label"]
            fails[lab] += 1
            ev = r["per_event"][r["failed_at"]]
            if ev:
                killers[lab].update(ev["killers"])
    out["fails"] = dict(fails)
    out["killers"] = {k: dict(v.most_common(3)) for k, v in killers.items()}
    nf = sum(fails.values())
    out["killer"] = fails.most_common(1)[0][0] if fails else None
    out["killer_share"] = (fails.most_common(1)[0][1] / nf) if nf else 0.0
    out["reach_boss"] = rate([r["boss_hp"] is not None for r in typ])
    out["boss_hp"] = mean([r["boss_hp"] for r in typ if r["boss_hp"] is not None])
    out["boss_pp"] = mean([r["boss_pp"] for r in typ if r["boss_pp"] is not None])
    cleared = [r for r in typ if r["cleared"]]
    out["fight_s"] = mean([r["fight_s"] for r in cleared]) if cleared else float("nan")
    # per fight on its own
    iso = {}
    for label, per_arch in cellres["iso"].items():
        t = [x for a in TYPICAL for x in per_arch.get(a, [])]
        s = per_arch.get("scouted", [])
        iso[label] = {"win": rate([x["won"] for x in t]), "win_scouted": rate([x["won"] for x in s]),
                      "hp_lost": mean([x["hp_lost"] for x in t]), "faints": mean([x["faints"] for x in t]),
                      "turns": mean([x["turns"] for x in t]), "s": mean([x["s"] for x in t])}
    out["iso"] = iso
    # the time the required fights take when the team survives them: the rested seconds of each, summed along the slowest route
    out["fight_s_rested"] = max((sum(iso[e["label"]]["s"] for e in seq_ if e["kind"] == "fight" and e["label"] in iso)
                                 for _l, seq_ in cellres["paths"]), default=float("nan"))
    best = None
    for _l, seq_ in cellres["paths"]:
        rows_ = [iso[e["label"]] for e in seq_ if e["kind"] == "fight" and e["label"] in iso]
        tot = {"n": len(rows_), "turns": sum(r["turns"] for r in rows_), "faints": sum(r["faints"] for r in rows_)}
        if best is None or tot["turns"] > best["turns"]:
            best = tot
    out["fight_totals"] = best
    seq = {}
    for r in typ:
        healed = False
        for ev, res in zip(paths[r["path"]], r["per_event"]):
            if res is None:
                healed = True
                continue
            row = seq.setdefault(ev["label"], {"reached": 0, "won": 0, "hp_lost": 0.0, "faints": 0.0, "category": ev["category"],
                                               "after_heal": healed,
                                               "foes": len(ev["foes"]), "levels": (min(l for _s, l in ev["foes"]), max(l for _s, l in ev["foes"]))})
            row["reached"] += 1
            row["won"] += 1 if res["won"] else 0
            row["hp_lost"] += res["hp_lost"]
            row["faints"] += res["faints"]
    for row in seq.values():
        n = row["reached"] or 1
        row["hp_lost"] /= n
        row["faints"] /= n
    out["seq"] = seq
    out["total_typical"] = len(typ)
    out["gym"] = cellres.get("gym")
    out["bag_used"] = mean([r["bag_used"] for r in typ])
    return out


def _budget(sm):
    """(before the heal, after it) and the boss chain: sums of the rested HP lost, as strings. A sum over 100% cannot be
    carried by an average team without items; it is arithmetic on the table above, not a tuned threshold."""
    before = after = boss = 0.0
    for label, q in sm["seq"].items():
        iso = sm["iso"].get(label)
        if not iso:
            continue
        if q["category"] == "boss":
            boss += iso["hp_lost"]
        elif q["after_heal"]:
            after += iso["hp_lost"]
        else:
            before += iso["hp_lost"]
    return (pct(before).strip(), pct(after).strip()), pct(boss).strip()


def classify(iso_row):
    """impossible / hard / trivial / ok for one fight on its own. The cut-offs are reading aids, stated in the report:
    impossible = no sampled team (scouted included) ever wins; hard = under half the typical teams win; trivial = every
    typical team wins losing under 10% of its health."""
    if iso_row["win"] == 0 and iso_row["win_scouted"] == 0:
        return "IMPOSSIBLE"
    if iso_row["win"] < 0.5:
        return "hard"
    if iso_row["win"] >= 1.0 and iso_row["hp_lost"] < 0.10:
        return "trivial"
    return "ok"


# ------------------------------------------------------------------------------------------------- clock

def clock_rows(doc, d, sums_by_band, rooms, totals_by_band=None):
    """Per band: the authored clock, the planning fight seconds and the sim's, the clock the sim implies.

    required (tools/dungeon_clock.py) = walk + fights + fixed; the sim replaces the fights with its own seconds and the
    clock is ceil(required x slack_factor) to the minute, as the generator does. The ratio authored / sim-required is the
    slack the player really has; the design asks for engine.clock.slack_factor."""
    slack = float(doc["engine"]["clock"]["slack_factor"])
    rows = {}
    for b in doc["engine"]["bands"]:
        band = b["band"]
        path = DC.clock_rooms(doc, d, band, rooms)
        parts = DC.required(doc, d, band, path)
        planned = parts["trainers"] + parts["wild"] + parts["boss"]
        rest = sum(parts.values()) - planned
        sim = sums_by_band.get(band)
        authored = DG.clock_s(d, b)
        row = {"authored": authored, "planned_fight": planned, "rest": rest, "required_planned": sum(parts.values())}
        tot = (totals_by_band or {}).get(band)
        if tot and tot["turns"] > 0:
            # the round length at which the sim's fight seconds equal the planning pace: if real rounds run longer than
            # this, the planning pace is the realistic one and the sim's fights are too short
            row["breakeven_round_s"] = (planned - FIGHT_SETUP_S * tot["n"] - FAINT_S * tot["faints"]) / tot["turns"]
        if sim is not None and not math.isnan(sim):
            req = rest + sim
            row.update({"sim_fight": sim, "required_sim": req, "implied": int(math.ceil(req * slack / 60.0)) * 60,
                        "ratio": authored / req})
        rows[band] = row
    return rows, slack


def clock_verdict(ratio, slack):
    """Tight under the design's own slack_factor (the player cannot loot as designed); loose over 1.5x of it."""
    if ratio < slack:
        return "TIGHT"
    if ratio > slack * 1.5:
        return "loose"
    return "ok"


# ------------------------------------------------------------------------------------------------- recommendations

def recommend(doc, d, band, summ, whatif=None):
    """Notes for the balance designer, from the numbers above; never an edit. `whatif` is {change: typical win at the lower
    cap} for this cell when --advise ran: each change is a measured alternative, paired with the base run."""
    notes = []
    lo = min(summ)
    for cap, s in sorted(summ.items()):
        g = s.get("gym")
        tail = ""
        if g:
            tail = " (the cap-%d gym leader, rested, is cleared by %s of the same teams)" % (cap, pct(g["win"]).strip())
        if s["win"] < 0.35 and s["killer"]:
            km = s["killers"].get(s["killer"], {})
            who = ", ".join("%s (%d)" % kv for kv in km.items())
            fld, boss = _budget(s) if s.get("seq") else (("?", "?"), "?")
            line = ("band %d, cap %d: typical teams clear %s (scouted %s); %.0f%% of failures at '%s' (their Pokemon fell to %s)%s. "
                    "HP budget: before the heal %s, after %s, boss chain %s of a team." % (
                        band, cap, pct(s["win"]).strip(), pct(s["win_scouted"]).strip(), s["killer_share"] * 100, s["killer"],
                        who or "?", tail, fld[0], fld[1], boss))
            if cap == lo and whatif:
                good = sorted([(w, k) for k, w in whatif.items() if w >= 0.5], reverse=True)
                best = max(whatif.items(), key=lambda kv: kv[1])
                if good:
                    line += " Measured changes that lift the cap-%d typical win to 50%% or more: %s." % (
                        cap, "; ".join("%s -> %s" % (k, pct(w).strip()) for w, k in good))
                else:
                    line += " No single change reaches 50%% (best: %s -> %s); it needs two together." % (best[0], pct(best[1]).strip())
            notes.append(line)
        elif s["win"] > 0.9 and s["boss_hp"] == s["boss_hp"] and s["boss_hp"] > 0.6:
            notes.append("band %d, cap %d: typical teams clear %s reaching the boss with %s health: the run does not wear a team "
                         "down; the field fights could carry a member more or a level more." % (
                             band, cap, pct(s["win"]).strip(), pct(s["boss_hp"]).strip()))
        triv = []
        for label, row in s["iso"].items():
            c = classify(row)
            if c == "IMPOSSIBLE":
                notes.append("band %d, cap %d: '%s' is IMPOSSIBLE for every sampled team, even the scouted one: rebuild it."
                             % (band, cap, label))
            elif c == "trivial" and cap == lo and s["seq"].get(label, {}).get("category") in ("stand", "gauntlet", "miniboss"):
                triv.append(label)
        if triv:
            notes.append("band %d, cap %d (the cap the fights are built against): trivial, every typical team wins losing under "
                         "10%% of its health: %s. A stand's lever is a member (its levels are already cap-2..cap-1, never above "
                         "the cap); a wild miniboss is one Pokemon at the band's upper cap, so its lever is a second Pokemon or "
                         "a bulkier species, not a level." % (band, cap, "; ".join(triv)))
    return notes


# ------------------------------------------------------------------------------------------------- report

def pct(x):
    return "n/a" if x != x else "%3.0f%%" % (x * 100)


def short(label, n=34):
    return label if len(label) <= n else label[: n - 1] + "~"


def table_rows(results, doc):
    """[(dungeon, band, cap_lo summary, cap_hi summary)] in dungeon then band order."""
    idx = defaultdict(dict)
    for r in results:
        idx[(r["dungeon"], r["band"])][r["cap"]] = r["summary"]
    rows = []
    for d in doc["dungeons"]:
        for b in doc["engine"]["bands"]:
            if (d["id"], b["band"]) in idx:
                rows.append((d["id"], b, idx[(d["id"], b["band"])]))
    return rows


def compact_table(results, doc):
    lines = ["%-13s %-4s %-12s %-10s %-10s %-34s %-12s %-9s" % (
        "dungeon", "band", "caps", "win lo/hi", "scouted", "hardest fight (lowest cap)", "boss reach/HP", "fight min")]
    for did, b, by_cap in table_rows(results, doc):
        lo, hi = min(by_cap), max(by_cap)
        s_lo, s_hi = by_cap[lo], by_cap[hi]
        hardest = s_lo["killer"] or _hardest_iso(s_lo)
        lines.append("%-13s %-4d %-12s %-10s %-10s %-34s %-12s %-9s" % (
            did, b["band"], "/".join(str(c) for c in sorted(by_cap)),
            "%s/%s" % (pct(s_lo["win"]).strip(), pct(s_hi["win"]).strip()),
            "%s/%s" % (pct(s_lo["win_scouted"]).strip(), pct(s_hi["win_scouted"]).strip()),
            short(hardest or "-"), "%s/%s" % (pct(s_lo["reach_boss"]).strip(), pct(s_lo["boss_hp"]).strip()),
            "n/a" if s_lo["fight_s_rested"] != s_lo["fight_s_rested"] else "%.1f" % (s_lo["fight_s_rested"] / 60.0)))
    return "\n".join(lines)


def _hardest_iso(s):
    """The fight with the lowest rested win rate then the most HP lost, when no run failed."""
    if not s["iso"]:
        return None
    return min(s["iso"], key=lambda k: (s["iso"][k]["win"], -s["iso"][k]["hp_lost"]))


def write_report(results, doc, clocks, opts, path):
    L = []
    w = L.append
    w("# Dungeon simulation: each dungeon against the teams of its areas")
    w("")
    w("**Generated** by `python tools/dungeon_sim.py` (unit DG-SIM, 2026-10-10). This is **derived output**: `derived/` is")
    w("gitignored and rebuilt by the command above, never hand-edited. Seed `%s`, %d samples per random archetype, %d reps,"
      " players %d levels under the cap, player moves `%s`, foe moves `%s`." % (
          opts["seed"], opts["samples"], opts["reps"], opts["under"], opts["moves"], opts["foe_moves"]))
    w("")
    w("A **cell** is a dungeon, a band and one player cap (the band's lower and upper cap). The dungeon's fights are pegged to the")
    w("band's LOWER cap (stands cap-2..cap-1, boss stages cap-2, cap-1, cap), the wild Pokemon to the upper, so the lower-cap")
    w("player is the one the dungeon is built against and the upper-cap player has the margin. Teams: `walked` (the six")
    w("earliest-available families), `balanced` (type coverage, random tie-break), `casual` (six random families), `scouted`")
    w("(the best response to this dungeon's roster). **Win** = the typical teams (walked+balanced+casual) clearing every required")
    w("fight in sequence, health and PP carried, the safe room's one heal, a full heal between the boss's two stages (the record's heal_between_stages).")
    w("")
    w("## Headline")
    w("")
    w("```")
    w(compact_table(results, doc))
    w("```")
    w("")
    w("`win lo/hi`: typical win rate at the band's lower / upper cap. `scouted`: the best-response team. `boss reach/HP`:")
    w("the share of typical runs that reach the boss at all, and the mean health share of those that do (lower cap). `fight min`: the required fights' simulated minutes if the team survives them (rested seconds, summed along the slowest route).")
    w("")
    wfs = opts.get("_whatifs")
    if wfs:
        w("## What-ifs: single changes to a failing dungeon, measured")
        w("")
        w("Each row is a cell whose typical win rate at the band's lower cap is under 50%. The columns re-run the SAME teams, seeds "
          "and rolls with one change to the required fights (so a difference is the change, not the sampling): fewer boss members "
          "(each stage drops its weakest-first member), boss stages two levels lower, a heal between the boss's stages (a bell "
          "after each), a heal before the boss, stands and gauntlets one member fewer or two levels lower. These are what the "
          "balance designer can choose between; none is applied.")
        w("")
        names = list(WHATIFS)
        w("| dungeon | band | base | " + " | ".join(names) + " |")
        w("| --- | --- | --- | " + " | ".join("---" for _ in names) + " |")
        for (did, band), res in sorted(wfs.items()):
            base = next((r["summary"]["win"] for r in results if r["dungeon"] == did and r["band"] == band
                         and r["cap"] == min(x["cap"] for x in results if x["dungeon"] == did and x["band"] == band)), float("nan"))
            w("| %s | %d | %s | %s |" % (did, band, pct(base).strip(), " | ".join(pct(res.get(n, float("nan"))).strip() for n in names)))
        w("")
    sens = opts.get("_sens")
    if sens:
        w("## Sensitivity: how much the answer moves with what the sim cannot know")
        w("")
        w("Typical win rate at the band's lower cap (the cap the dungeon is built against), the base run first. `bag N`: the player "
          "carries N full-heal/revive uses, spent between fights and never between the boss's stages. `under 3`: Pokemon three "
          "levels under the cap. `levelup`: no TM moves. `latest4`: foes carry their last four level-up moves instead of "
          "battle_sim's best set.")
        w("")
        names = [n for n, _ in sens]
        w("| dungeon | band | base | " + " | ".join(names) + " |")
        w("| --- | --- | --- | " + " | ".join("---" for _ in names) + " |")
        for did, b, by_cap in table_rows(results, doc):
            lo = min(by_cap)
            cols = [pct(by_cap[lo]["win"]).strip()]
            for _n, res in sens:
                cols.append(pct(res.get((did, b["band"], lo), float("nan"))).strip())
            w("| %s | %d | %s |" % (did, b["band"], " | ".join(cols)))
        w("")
    for d in doc["dungeons"]:
        mine = [r for r in results if r["dungeon"] == d["id"]]
        if not mine:
            continue
        w("## %s" % d["name"])
        w("")
        for b in doc["engine"]["bands"]:
            cells = sorted([r for r in mine if r["band"] == b["band"]], key=lambda r: r["cap"])
            if not cells:
                continue
            w("### Band %d (caps %s)" % (b["band"], "/".join(str(c) for c in b["caps"])))
            w("")
            for c in cells:
                s = c["summary"]
                w("- **cap %d**: typical win %s (route worst: %s %s), scouted %s; pool %d families; %s reach the boss with %s health, PP %s; "
                  "%s" % (c["cap"], pct(s["win"]).strip(), s["worst_path"], pct(s["win_worst_path"]).strip(),
                          pct(s["win_scouted"]).strip(), s["pool"], pct(s["reach_boss"]).strip(), pct(s["boss_hp"]).strip(),
                          pct(s["boss_pp"]).strip(),
                          ("most failures at '%s' (%.0f%%)" % (s["killer"], s["killer_share"] * 100)) if s["killer"]
                          else "no typical run failed"))
                g = s.get("gym")
                if g:
                    w("  - reference: the same teams against gym %d's leader (ace %d), rested: typical win %s, %s of the team's "
                      "health lost, %.1f faints." % (g["gym"], c["cap"], pct(g["win"]).strip(), pct(g["hp_lost"]).strip(), g["faints"]))
            lo = cells[0]
            w("")
            sm = lo["summary"]
            w("| fight (cap %d) | foes (levels) | rested win | scouted | rested HP lost | rested faints | in the run: reached | cleared | HP lost | reading |" % lo["cap"])
            w("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
            for label, row in sm["iso"].items():
                q = sm["seq"].get(label)
                if q:
                    foes = "%d (L%d-%d)" % (q["foes"], q["levels"][0], q["levels"][1])
                    inrun = "%s | %s | %s" % (pct(q["reached"] / float(sm["total_typical"])).strip(),
                                              pct(q["won"] / float(q["reached"])).strip() if q["reached"] else "n/a",
                                              pct(q["hp_lost"]).strip())
                else:
                    foes, inrun = "optional", "- | - | -"
                w("| %s | %s | %s | %s | %s | %.1f | %s | %s |" % (
                    label, foes, pct(row["win"]).strip(), pct(row["win_scouted"]).strip(), pct(row["hp_lost"]).strip(),
                    row["faints"], inrun, classify(row)))
            fld, boss = _budget(sm)
            w("")
            w("HP budget at cap %d (rested cost of each required fight, as a share of the whole team's health; 100%% is the "
              "whole team): fights before the safe room's heal %s, after it %s, the boss chain %s." % (
                  lo["cap"], fld[0], fld[1], boss))
            w("")
        w("")
    w("## Fight time against the clock")
    w("")
    w("Planning figures, UNMEASURED (XT1 timed no fight): %d s to set a fight up, %d s a round, %d s a faint. required = walk + "
      "fights + fixed (tools/dungeon_clock.py); the sim replaces the planning fight seconds with its own and re-derives the clock "
      "as ceil(required x slack_factor) to the minute. `ratio` = authored clock / sim-required; the design asks for the "
      "engine's slack_factor, so under it is TIGHT and over 1.5x it is loose." % (FIGHT_SETUP_S, TURN_S, FAINT_S))
    w("")
    w("`break-even s/round`: the round length at which the sim's fights would take exactly the planning pace (DUNGEONS.md 4.1: "
      "2.0 min for a 2-member fight + 0.5 min a member). If a real round takes longer than this, the planning pace is the "
      "realistic one and the clock is not loose; XT1 (EXP-079) is what measures it. The sim's own rounds are %d s." % TURN_S)
    w("")
    w("| dungeon | band | authored | planned fight min | sim fight min | required min (sim) | implied clock min | ratio | break-even s/round | verdict |")
    w("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for did, rows in clocks.items():
        slack = rows["slack"]
        for band, r in rows["bands"].items():
            if "ratio" not in r:
                w("| %s | %d | %d min | %.1f | n/a | n/a | n/a | n/a | n/a | no data |" % (
                    did, band, r["authored"] // 60, r["planned_fight"] / 60))
                continue
            w("| %s | %d | %d min | %.1f | %.1f | %.1f | %d | %.2f | %.0f | %s |" % (
                did, band, r["authored"] // 60, r["planned_fight"] / 60, r["sim_fight"] / 60, r["required_sim"] / 60,
                r["implied"] // 60, r["ratio"], r.get("breakeven_round_s", float("nan")), clock_verdict(r["ratio"], slack)))
    w("")
    w("## Recommendations for the balance designer (rule-based; the data is not edited)")
    w("")
    any_note = False
    for did, bnotes in sorted(opts["_notes"].items()):
        for n in bnotes:
            any_note = True
            w("- **%s**, %s" % (did, n))
    if not any_note:
        w("- no cell breached a rule.")
    w("")
    w("Rules: a cell with a typical win rate under 35% is hard at its named fight; over 90% with over 60% health at the boss "
      "is easy; a fight no sampled team wins is impossible. These cut-offs are reading aids, not design targets.")
    w("")
    w("## What the simulation cannot model")
    w("")
    for line in __doc__.split("WHAT IT CANNOT MODEL")[1].split("OPTIONAL fights")[0].strip().splitlines()[1:]:
        w(line)
    w("")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


# ------------------------------------------------------------------------------------------------- the CLI

def _job(args):
    doc, did, band_entry, cap, opts = args
    d = next(x for x in doc["dungeons"] if x["id"] == did)
    res = run_cell(doc, d, band_entry, cap, opts)
    res["summary"] = summarise(res)
    for k in ("runs", "iso"):
        res.pop(k)
    return res


def _walk_job(args):
    """The walked rooms of a dungeon (tools/dungeon_clock.walked builds every room's grid: about 25 s a dungeon, so it runs
    beside the cells and not after them)."""
    doc, did = args
    d = next(x for x in doc["dungeons"] if x["id"] == did)
    return DC.walked(doc, d)[0]


class _Inline:
    """Executor.submit for --jobs 1: runs now, returns a finished Future."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def submit(self, fn, *args):
        from concurrent.futures import Future
        f = Future()
        f.set_result(fn(*args))
        return f


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dungeon")
    ap.add_argument("--band", type=int)
    ap.add_argument("--samples", type=int, default=10, help="random teams per archetype (balanced, casual)")
    ap.add_argument("--reps", type=int, default=2, help="repeats per team with fresh IVs and rolls")
    ap.add_argument("--under", type=int, default=0, help="player levels below the cap")
    ap.add_argument("--bag", type=int, default=0,
                    help="healing/revive uses a player carries into the run (0 = the design as written)")
    ap.add_argument("--advise", action="store_true",
                    help="for each cell under 50%% at its lower cap, measure single changes (fewer boss members, a heal ...)")
    ap.add_argument("--sensitivity", action="store_true", help="also rerun with a bag, under-levelled players, no TMs, latest-four foes")
    ap.add_argument("--moves", choices=("tm", "levelup"), default="tm")
    ap.add_argument("--foe-moves", choices=("smart", "latest"), default="smart")
    ap.add_argument("--seed", default="dg-sim-1")
    ap.add_argument("--jobs", type=int, default=0, help="worker processes (0 = half the cores, at most 8)")
    ap.add_argument("--no-clock", action="store_true")
    ap.add_argument("--out", default=str(OUT_DIR / "report.md"))
    a = ap.parse_args(argv)
    doc = DG.load()
    if a.jobs <= 0:
        import os
        a.jobs = max(1, min(8, (os.cpu_count() or 2) // 2))
    opts = {"samples": a.samples, "reps": a.reps, "under": a.under, "moves": a.moves, "foe_moves": a.foe_moves, "seed": a.seed,
            "bag": a.bag}
    jobs, dungeons = [], []
    for d in doc["dungeons"]:
        if a.dungeon and d["id"] != a.dungeon:
            continue
        if not R.has_rooms(d):
            continue
        dungeons.append(d["id"])
        for b in doc["engine"]["bands"]:
            if a.band and b["band"] != a.band:
                continue
            for cap in sorted(set(b["caps"])):
                jobs.append((doc, d["id"], b, cap, opts))
    if not jobs:
        raise SimError("nothing to simulate: no dungeon/band matches")
    variants = [("bag 4", {"bag": 4}), ("bag 8", {"bag": 8}), ("under 3", {"under": 3}),
                ("levelup", {"moves": "levelup"}), ("latest4", {"foe_moves": "latest"})] if a.sensitivity else []
    from concurrent.futures import ProcessPoolExecutor
    with (ProcessPoolExecutor(a.jobs) if a.jobs > 1 else _Inline()) as ex:
        walk_f = {} if a.no_clock else {did: ex.submit(_walk_job, (doc, did)) for did in dungeons}
        base_f = [ex.submit(_job, j) for j in jobs]
        sens_f = [(name, [ex.submit(_job, (doc, did, b, cap, dict(o, lean=True, **over))) for (doc, did, b, cap, o) in jobs])
                  for name, over in variants]
        results = [f.result() for f in base_f]
        print(compact_table(results, doc))
        whatifs = {}
        if a.advise:
            for r in results:
                cap_lo = min(next(b["caps"] for b in doc["engine"]["bands"] if b["band"] == r["band"]))
                if r["cap"] == cap_lo and r["summary"]["win"] < 0.5:
                    whatifs[(r["dungeon"], r["band"])] = {}
            todo = [(doc, did, b, cap, dict(opts, lean=True, whatif=name)) for (did, band) in whatifs
                    for b in doc["engine"]["bands"] if b["band"] == band for cap in [min(b["caps"])] for name in WHATIFS]
            for j, f in [(j, ex.submit(_job, j)) for j in todo]:
                r = f.result()
                whatifs[(r["dungeon"], r["band"])][j[4]["whatif"]] = r["summary"]["win"]
        opts["_whatifs"] = whatifs
        opts["_sens"] = [(name, {(r["dungeon"], r["band"], r["cap"]): r["summary"]["win"] for r in (f.result() for f in fs)})
                         for name, fs in sens_f]
        clocks, notes = {}, {}
        for did in dungeons:
            d = next(x for x in doc["dungeons"] if x["id"] == did)
            mine = [r for r in results if r["dungeon"] == did]
            notes[did] = []
            for b in doc["engine"]["bands"]:
                cells = {r["cap"]: r["summary"] for r in mine if r["band"] == b["band"]}
                if cells:
                    notes[did] += recommend(doc, d, b["band"], cells, whatifs.get((did, b["band"])))
            if not a.no_clock:
                sums, totals = {}, {}
                for b in doc["engine"]["bands"]:
                    cs = [r["summary"] for r in mine if r["band"] == b["band"] and r["cap"] == min(b["caps"])]
                    if cs:
                        sums[b["band"]] = cs[0]["fight_s_rested"]
                        totals[b["band"]] = cs[0]["fight_totals"]
                rows, slack = clock_rows(doc, d, sums, walk_f[did].result(), totals)
                clocks[did] = {"bands": {k: v for k, v in rows.items() if k in sums}, "slack": slack}
    opts["_notes"] = notes
    write_report(results, doc, clocks, opts, a.out)
    print("wrote %s (derived output, gitignored)" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
