#!/usr/bin/env python
"""Score every TMCraft TM by what its move does, and band the scores into badges 1-8: the gate's score table.

docs/mechanics/TM_POWER_GATE.md is the rule in plain terms; docs/mechanics/TM_POWER_GATE.json is this tool's output,
COMMITTED, and tools/tm_gate.py reads it (the owner, 2026-10-08: "TAKE THE POWER RULE"). The gate places a TM by its
shelf line, else by an outlier group in data/tm_gate.json, else by the band of the score written here. The bands are
data/tm_gate.json badge_rule.power.bands (tm_gate.band), so this tool and the gate band with one definition.

Why a committed table and not a call from the gate: moves.js is a JavaScript module and reading it needs node, which
prepare does not otherwise need. The table records the sha256 of the moves.js it was scored from, and tools/tm_gate.py
fails closed when the server's moves.js differs, so a pack update cannot leave the gate on stale scores.

  python tools/tm_power_score.py --server-dir <snapshot>           # rewrite docs/mechanics/TM_POWER_GATE.json
  python tools/tm_power_score.py --server-dir <snapshot> --check   # exit 1 if the committed table is not current

INPUTS, all read only:
  --server-dir  a server snapshot (never the live server). tools/tm_gate.py reads its mods for the TM items and their
                recipes (disc grade); the moves come from Mega Showdown's moves.js in the same mods folder, because
                Mega Showdown's ShowdownPatcher copies it over Cobblemon's data/moves.js at startup
                (docs/research/notes/sketch-cap-1.8.0.md section 2), so it is the copy battles run.
  --moves-json  instead of running node on the jar's moves.js: a dump of it (the node step below, done once). The
                sha256 is still taken from the jar's own file.

The move dump needs node: moves.js is a JavaScript module. Its data fields are kept; every callback becomes "<fn>"
so that a move whose effect lives only in code is visible as such.

THE SCORE is in power points, one scale for every move:
  damaging  A x (P x H x M + S) + flat
            P base power (NOMINAL for a move whose power is 0 or computed), A accuracy (true = 1), H hits,
            M the multipliers (charge, recharge, recoil, self-drops, crash, faint, conditional, crit), S the side
            effects (status, flinch, confusion, stat changes, drain), flat priority and pivoting
  status    A x V, V from the move's mechanic fields (status, boosts, sideCondition, weather, terrain, pseudoWeather,
            volatileStatus, heal, stallingMove, forceSwitch, selfSwitch, slotCondition, selfdestruct); a status move
            whose effect is only code is valued from STATUS_HAND, and its record says so
Every constant below is the valuation; docs/mechanics/TM_POWER_GATE.md says why each is what it is.
"""
import argparse
import collections
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import tm_gate  # noqa: E402

MSD_JAR_GLOB = tm_gate.MSD_JAR_GLOB
MSD_MOVES = tm_gate.MSD_MOVES
SCHEMA = tm_gate.SCORES_SCHEMA
DEFAULT_OUT = ROOT / "docs" / "mechanics" / "TM_POWER_GATE.json"
NODE_DUMP = ("const m=require(process.argv[1]);const mv=m.Moves||m.BattleMovedex;const o={};"
             "for(const [k,v] of Object.entries(mv)){o[k]=JSON.parse(JSON.stringify(v,(a,b)=>typeof b==='function'?'<fn>':b));}"
             "require('fs').writeFileSync(process.argv[2],JSON.stringify(o));")

# ------------------------------------------------------------------ the bands (score -> badge)
# data/tm_gate.json badge_rule.power.bands, banded by tm_gate.band: badge 1 below 35; then each badge is one step of
# ten base power plus up to four points of side effects (badge 3 holds the 60-power moves, 54 < score <= 64, badge 5 the
# 80s, 6 the 90s, 7 the 100s); badge 8 is above 104. Why the tops sit four above the round numbers is the bands' own
# `why` there and docs/mechanics/TM_POWER_GATE.md 3.

# ------------------------------------------------------------------ damaging moves
# power for a move whose basePower is 0 or is computed from the battle; stated power is used for every other move,
# and a stated power that only DOUBLES under a condition (Hex, Venoshock, Acrobatics, Knock Off ...) is left as stated
NOMINAL = {
    "beatup": (50, "one hit per healthy party member, typically 4-6 hits of 5-15"),
    "bide": (50, "returns double the damage taken over two turns; the user must survive them"),
    "comeuppance": (70, "1.5x the damage just taken; fails if not hit"),
    "counter": (70, "2x physical damage just taken; fails otherwise"),
    "mirrorcoat": (70, "2x special damage just taken; fails otherwise"),
    "metalburst": (70, "1.5x damage just taken; fails otherwise"),
    "crushgrip": (80, "up to 120 at the target's full HP, falling with it"),
    "wringout": (80, "up to 120 at the target's full HP, falling with it"),
    "dragonrage": (40, "always 40 HP"),
    "sonicboom": (20, "always 20 HP"),
    "electroball": (80, "40-150 by speed ratio"),
    "endeavor": (60, "brings the target to the user's HP; good only when low"),
    "finalgambit": (100, "damage equal to the user's HP; the user faints (selfdestruct below)"),
    "fissure": (200, "a one-hit KO; 200 stands for a KO and accuracy 30 does the rest"),
    "horndrill": (200, "a one-hit KO"),
    "sheercold": (200, "a one-hit KO"),
    "flail": (70, "20-200 by the user's missing HP"),
    "reversal": (70, "20-200 by the user's missing HP"),
    "fling": (50, "by held item, consumed"),
    "frustration": (100, "102 at zero friendship"),
    "return": (100, "102 at full friendship"),
    "grassknot": (80, "20-120 by the target's weight"),
    "lowkick": (80, "20-120 by the target's weight"),
    "heatcrash": (80, "40-120 by weight ratio"),
    "heavyslam": (80, "40-120 by weight ratio"),
    "gyroball": (80, "1-150 by speed ratio, slow users"),
    "hardpress": (70, "up to 100 at the target's full HP"),
    "magnitude": (71, "10-150, weighted mean of Showdown's table (5/10/20/30/20/10/5 %)"),
    "naturalgift": (40, "by berry, consumed"),
    "nightshade": (65, "damage equal to the user's level, 50-55 HP at the late caps, ignores stats"),
    "seismictoss": (65, "damage equal to the user's level"),
    "psywave": (60, "level x 0.5-1.5, mean = level"),
    "punishment": (60, "60 + 20 per target boost"),
    "superfang": (70, "half the target's HP"),
    "ruination": (70, "half the target's HP"),
    "populationbomb": (130, "10 hits of 20, each 90%: about 117 expected, so 130 before the accuracy factor"),
    "triplekick": (52, "10/20/30, each hit 90%: about 47 expected"),
    "tripleaxel": (105, "20/40/60, each hit 90%: about 94 expected"),
    "rollout": (60, "30 doubling over five locked turns"),
    "iceball": (60, "30 doubling over five locked turns"),
    "furycutter": (60, "40 doubling while it hits"),
    "echoedvoice": (55, "40 rising each turn it is used"),
    "storedpower": (60, "20 + 20 per user boost"),
    "powertrip": (60, "20 + 20 per user boost"),
    "lastrespects": (75, "50 + 50 per fainted ally"),
    "ragefist": (75, "50 + 50 per hit taken"),
    "eruption": (100, "150 at full HP, falling with it"),
    "waterspout": (100, "150 at full HP, falling with it"),
    "dragonenergy": (100, "150 at full HP, falling with it"),
}
# a move that fails, waits or only works in a circumstance: its power is real only some of the time
CONDITIONAL = {
    "focuspunch": (0.6, "fails if hit first"),
    "lastresort": (0.4, "fails until every other move has been used"),
    "steelroller": (0.5, "fails without a terrain"),
    "poltergeist": (0.9, "fails against a target with no item"),
    "fakeout": (0.6, "the first turn on the field only"),
    "firstimpression": (0.6, "the first turn on the field only"),
    "suckerpunch": (0.8, "fails if the target does not attack"),
    "thunderclap": (0.8, "fails if the target does not attack"),
    "doomdesire": (0.75, "lands two turns later"),
    "futuresight": (0.75, "lands two turns later"),
    "snore": (0.3, "only while asleep"),
    "dreameater": (0.3, "only against a sleeping target"),
    "belch": (0.5, "only after eating a berry"),
    "synchronoise": (0.5, "hits only a target sharing a type"),
    "skydrop": (0.6, "two turns, cannot lift heavy targets"),
    "aurawheel": (0.0, "fails for any user but Morpeko"),
    "hyperspacefury": (0.0, "fails for any user but Hoopa Unbound"),
    "counter": (0.8, "fails if not hit by a physical move"),
    "mirrorcoat": (0.8, "fails if not hit by a special move"),
    "metalburst": (0.8, "fails if not hit, and moves last"),
    "comeuppance": (0.8, "fails if not hit"),
    "bide": (0.7, "two turns idle, then fails if not hit"),
    "upperhand": (0.3, "fails unless the target is using a priority move"),
    "shelltrap": (0.4, "fails unless the user is hit by a contact move first"),
    "burnup": (0.85, "the user loses its Fire type"),
    "doubleshock": (0.85, "the user loses its Electric type"),
    "chloroblast": (0.6, "half the user's HP as recoil, coded in battle-actions.js, not in the move's fields"),
}
# a secondary whose effect is only code: what that effect is worth, before its chance
SEC_CODE = {
    "triattack": (30, "paralyse, burn or freeze"), "direclaw": (28, "poison, paralyse or sleep"),
    "anchorshot": (10, "traps"), "spiritshackle": (10, "traps"), "throatchop": (5, "blocks sound moves"),
    "eeriespell": (5, "-3 PP"), "alluringvoice": (5, "confuses a boosted target"),
    "burningjealousy": (5, "burns a boosted target"),
}
LOCKED = 0.85          # Outrage, Thrash, Petal Dance, Raging Fury: locked in 2-3 turns, then confused
CANT_TWICE = 0.75      # Gigaton Hammer, Blood Moon: flag cantusetwice
SEC_STATUS = {"par": 30, "brn": 30, "frz": 30, "slp": 40, "psn": 15, "tox": 25}
SEC_VOLATILE = {"flinch": 15, "confusion": 12}
SEC_TARGET_STAGE = {"spe": 10}  # any other stat: 8 per stage lowered
SEC_SELF_STAGE = {"atk": 12, "spa": 12, "spe": 12, "def": 8, "spd": 8, "accuracy": 4, "evasion": 12}
SELF_DROP_COST = {"atk": 0.075, "spa": 0.075, "def": 0.05, "spd": 0.05, "spe": 0.05}
PRIORITY_PLUS, PRIORITY_MINUS = 15, -10
PIVOT_DAMAGING, PHAZE_DAMAGING = 20, 10
DRAIN_WORTH = 0.4      # a point healed is worth 0.4 of a point dealt
CHARGE = RECHARGE = 0.5
SELFDESTRUCT_DAMAGING = 0.35
CRASH = 0.9
HALF_HP_RECOIL = 0.6   # Mind Blown, Steel Beam, Chloroblast: half the user's HP
MULTIHIT_2_5 = 3.1     # Showdown 2-5 hits: 35/35/15/15 %
LOW_PP = (5, 0.95)     # 5 PP or fewer (8 with PP Ups): runs dry in a gauntlet or a long fight; more PP is not scored

# ------------------------------------------------------------------ status moves
STATUS_INFLICT = {"par": 100, "slp": 110, "brn": 85, "tox": 95, "psn": 50}
TARGET_DROP_STAGE = {"evasion": 5}  # any other stat: 15 per stage lowered
SELF_STAGE = {"spe": 30, "def": 20, "spd": 20, "accuracy": 10, "evasion": 30}
OFFENSE_STAGE = 35     # the better of atk/spa; the other at half (a Pokemon uses one)
SIDE = {"stealthrock": 85, "spikes": 65, "toxicspikes": 60, "stickyweb": 70, "reflect": 65, "lightscreen": 65,
        "auroraveil": 90, "tailwind": 60, "safeguard": 25, "mist": 15, "luckychant": 10, "matblock": 10,
        "quickguard": 10, "wideguard": 10, "craftyshield": 5}
WEATHER = {"raindance": 50, "sunnyday": 50, "sandstorm": 35, "snow": 35, "hail": 30}
TERRAIN = 45
PSEUDO = {"trickroom": 80, "gravity": 25, "magicroom": 15, "wonderroom": 15, "fairylock": 15, "iondeluge": 5,
          "mudsport": 10, "watersport": 10}
VOLATILE = {"confusion": 40, "leechseed": 60, "substitute": 50, "taunt": 55, "encore": 55, "yawn": 70,
            "destinybond": 45, "disable": 35, "octolock": 40, "stockpile": 40, "gastroacid": 35, "attract": 30,
            "aquaring": 30, "ingrain": 30, "magiccoat": 30, "endure": 25, "focusenergy": 25, "magnetrise": 25,
            "torment": 20, "healblock": 20, "charge": 20, "laserfocus": 15, "snatch": 15, "tarshot": 15,
            "powertrick": 15, "embargo": 10, "imprison": 10, "grudge": 10, "nightmare": 10, "powder": 10,
            "powershift": 10, "telekinesis": 10, "electrify": 5, "foresight": 5, "miracleeye": 5,
            "followme": 5, "ragepowder": 5, "helpinghand": 5, "dragoncheer": 5,
            # set by the move but valued elsewhere (stallingMove, boosts, heal)
            "protect": 0, "kingsshield": 0, "spikyshield": 0, "banefulbunker": 0, "burningbulwark": 0,
            "obstruct": 0, "silktrap": 0, "defensecurl": 0, "noretreat": -10, "curse": 0}
PROTECT, PROTECT_PLUS = 45, 55  # Protect/Detect; the shields that also punish contact
HEAL = {0.5: 75, 0.25: 40}
FORCE_SWITCH = 45
SELF_SWITCH = {True: 25, "copyvolatile": 40}
SLOT = {"wish": 60, "healingwish": 90, "lunardance": 90, "revivalblessing": 100}
SELFDESTRUCT_STATUS = -30
ALLY_ONLY = 0.15       # a boost given only to an ally: doubles only, and every fight here is GEN_9_SINGLES
STATUS_HAND = {
    "acupressure": (35, "+2 to a random stat"), "afteryou": (5, "doubles only"), "allyswitch": (5, "doubles only"),
    "aromatherapy": (35, "cures the party's status"), "healbell": (35, "cures the party's status"),
    "assist": (20, "a random party move"), "batonpass": (40, "pivot passing boosts"),
    "bellydrum": (90, "+6 atk for half the user's HP"), "bestow": (5, "gives the held item away"),
    "block": (25, "traps"), "meanlook": (25, "traps"), "spiderweb": (25, "traps"), "camouflage": (10, "type change"),
    "celebrate": (0, "nothing"), "splash": (0, "nothing"), "holdhands": (0, "nothing"), "happyhour": (0, "nothing"),
    "conversion": (10, "type change"), "conversion2": (15, "resisting type change"), "copycat": (20, "copies"),
    "mirrormove": (15, "copies"), "mefirst": (20, "copies first"), "mimic": (20, "copies a move"),
    "metronome": (30, "a random move"), "sleeptalk": (40, "a random move while asleep, the Rest partner"),
    "corrosivegas": (15, "removes items around"), "courtchange": (30, "swaps hazards and screens"),
    "curse": (45, "ghost: a heavy curse at half HP; others: +1 atk def, -1 spe"),
    "defog": (45, "clears hazards and screens"), "doodle": (15, "copies an ability"),
    "entrainment": (15, "gives an ability"), "roleplay": (20, "copies an ability"),
    "simplebeam": (30, "sets Simple"), "worryseed": (30, "sets Insomnia"), "skillswap": (30, "swaps abilities"),
    "flowershield": (5, "grass allies only"), "floralhealing": (10, "heals the target, doubles"),
    "healpulse": (10, "heals the target, doubles"), "forestscurse": (10, "adds grass type"),
    "trickortreat": (10, "adds ghost type"), "soak": (30, "makes the target water"), "gearup": (5, "plus/minus allies"),
    "magneticflux": (5, "plus/minus allies"), "guardsplit": (20, "averages defences"),
    "powersplit": (20, "averages attacks"), "guardswap": (20, "swaps defence boosts"),
    "powerswap": (20, "swaps attack boosts"), "heartswap": (25, "swaps all boosts"),
    "speedswap": (20, "swaps speed"), "psychup": (30, "copies boosts"), "topsyturvy": (25, "inverts boosts"),
    "haze": (35, "clears every boost"), "instruct": (5, "doubles only"), "quash": (5, "doubles only"),
    "junglehealing": (30, "a quarter HP and cures, self and ally"),
    "lunarblessing": (50, "a quarter HP and cures, self and ally"), "magicpowder": (10, "makes the target psychic"),
    "mindreader": (15, "next move cannot miss"), "moonlight": (65, "half HP, weather dependent"),
    "morningsun": (65, "half HP, weather dependent"), "synthesis": (65, "half HP, weather dependent"),
    "shoreup": (75, "half HP, more in sand"), "naturepower": (70, "calls a move by terrain (Tri Attack, 80)"),
    "painsplit": (50, "averages HP"), "partingshot": (55, "-1 atk spa and a pivot"),
    "perishsong": (35, "both faint in three turns"), "psychoshift": (40, "passes the user's status"),
    "purify": (10, "cures the target"), "recycle": (15, "restores a used item"),
    "reflecttype": (10, "copies type"), "refresh": (20, "cures the user's status"),
    "rest": (60, "full HP and status cure, two turns asleep"), "rototiller": (5, "grass allies only"),
    "sketch": (0, "Smeargle only, capped by the Sketch cap"), "stockpile": (40, "+1 def spd, up to three"),
    "strengthsap": (85, "heals by the target's attack and lowers it"), "stuffcheeks": (40, "eats a berry, +2 def"),
    "swallow": (30, "heals by stockpiles"), "switcheroo": (55, "swaps items: a Choice item cripples"),
    "trick": (55, "swaps items: a Choice item cripples"), "takeheart": (55, "+1 spa spd and a status cure"),
    "teatime": (5, "everyone eats berries"), "transform": (30, "copies the target"),
    "venomdrench": (30, "-1 atk spa spe against a poisoned target"), "shedtail": (60, "a substitute passed on a pivot"),
    "spite": (15, "-4 PP"), "decorate": (5, "+2 atk spa to an ally: doubles only"),
    "spicyextract": (15, "+2 atk -2 def to the target: an ally's set-up or a foe's softening"),
}
HP_COST = {"clangoroussoul": (-30, "a third of HP"), "filletaway": (-45, "half HP"),
           "noretreat": (0, "traps the user, in VOLATILE")}


def load_moves(server_dir, moves_json):
    """(moves, source label, sha256 of the jar's moves.js). The sha256 is always the jar's file: it is what
    tools/tm_gate.py compares with the server it builds for."""
    jars = sorted((Path(server_dir) / "mods").glob(MSD_JAR_GLOB))
    if len(jars) != 1:
        raise SystemExit("tm_power_score: expected one %s in %s/mods, found %d" % (MSD_JAR_GLOB, server_dir, len(jars)))
    raw = zipfile.ZipFile(jars[0]).read(MSD_MOVES)
    sha = hashlib.sha256(raw).hexdigest()
    label = "%s!%s" % (jars[0].name, MSD_MOVES)
    if moves_json:
        return json.loads(Path(moves_json).read_text(encoding="utf-8")), label, sha
    with tempfile.TemporaryDirectory() as td:
        src, out = Path(td) / "moves.js", Path(td) / "moves.json"
        src.write_bytes(raw)
        subprocess.run(["node", "-e", NODE_DUMP, str(src), str(out)], check=True)
        return json.loads(out.read_text(encoding="utf-8")), label, sha


def _stage_list(boosts):
    return [(s, n) for s, n in (boosts or {}).items() if isinstance(n, (int, float))]


def score_damaging(mid, mv):
    why = []
    p = mv.get("basePower") or 0
    if mid in NOMINAL:
        p, r = NOMINAL[mid]
        why.append("nominal power %d (%s)" % (p, r))
    a = 1.0 if mv.get("accuracy") is True else mv.get("accuracy", 100) / 100.0
    hits = mv.get("multihit")
    h = 1.0
    if isinstance(hits, list):
        h = MULTIHIT_2_5 if hits == [2, 5] else sum(hits) / 2.0
    elif isinstance(hits, (int, float)) and mid not in NOMINAL:
        h = float(hits)
    if h != 1.0:
        why.append("x%.2g hits" % h)
    m = 1.0
    flags = mv.get("flags", {})
    if mv.get("ohko"):
        p = NOMINAL.get(mid, (200,))[0]
    if "charge" in flags:
        m *= CHARGE; why.append("charge turn x%.2g" % CHARGE)
    if "recharge" in flags:
        m *= RECHARGE; why.append("recharge turn x%.2g" % RECHARGE)
    rec = mv.get("recoil")
    if isinstance(rec, list):
        f = 1 - 0.5 * rec[0] / rec[1]; m *= f; why.append("recoil %d/%d x%.3g" % (rec[0], rec[1], f))
    if mv.get("mindBlownRecoil") or mv.get("struggleRecoil"):
        m *= HALF_HP_RECOIL; why.append("half-HP recoil x%.2g" % HALF_HP_RECOIL)
    if mv.get("hasCrashDamage"):
        m *= CRASH; why.append("crash on miss x%.2g" % CRASH)
    if mv.get("selfdestruct"):
        m *= SELFDESTRUCT_DAMAGING; why.append("user faints x%.2g" % SELFDESTRUCT_DAMAGING)
    if mv.get("willCrit"):
        m *= 1.5; why.append("always crits x1.5")
    elif (mv.get("critRatio") or 1) >= 2:
        f = 1.04 if mv["critRatio"] == 2 else 1.25; m *= f; why.append("high crit x%.3g" % f)
    if "cantusetwice" in flags:
        m *= CANT_TWICE; why.append("not twice in a row x%.2g" % CANT_TWICE)
    if isinstance(mv.get("self"), dict) and mv["self"].get("volatileStatus") == "lockedmove":
        m *= LOCKED; why.append("locked in, then confused x%.2g" % LOCKED)
    if mid in CONDITIONAL:
        f, r = CONDITIONAL[mid]; m *= f; why.append("conditional x%.2g (%s)" % (f, r))
    if (mv.get("pp") or 99) <= LOW_PP[0]:
        m *= LOW_PP[1]; why.append("%d PP x%.2g" % (mv["pp"], LOW_PP[1]))
    s = 0.0
    selfb = []
    for key in ("self", "selfBoost"):
        blk = mv.get(key)
        if isinstance(blk, dict):
            selfb += _stage_list(blk.get("boosts"))
    for st, n in selfb:
        if n < 0:
            f = 1 - SELF_DROP_COST.get(st, 0.05) * -n; m *= f; why.append("self %s %d x%.3g" % (st, n, f))
        else:
            s += SEC_SELF_STAGE.get(st, 8) * n; why.append("self %s +%d" % (st, n))
    secs = mv.get("secondaries") or ([mv["secondary"]] if isinstance(mv.get("secondary"), dict) else [])
    for sec in secs:
        c = (sec.get("chance") or 100) / 100.0
        v = 0.0
        if sec.get("status") in SEC_STATUS:
            v += SEC_STATUS[sec["status"]]
        if sec.get("volatileStatus") in SEC_VOLATILE:
            v += SEC_VOLATILE[sec["volatileStatus"]]
        for st, n in _stage_list(sec.get("boosts")):
            if n < 0:
                v += SEC_TARGET_STAGE.get(st, 8) * -n
        sb = (sec.get("self") or {}).get("boosts") if isinstance(sec.get("self"), dict) else None
        for st, n in _stage_list(sb):
            v += SEC_SELF_STAGE.get(st, 8) * n if n > 0 else -SEC_SELF_STAGE.get(st, 8) * -n * 0.5
        if sec.get("onHit") == "<fn>" and v == 0:
            if mid in SEC_CODE:
                v = SEC_CODE[mid][0]; why.append("effect by hand %d (%s)" % SEC_CODE[mid])
            else:
                why.append("a %d%% effect only code describes: not valued" % round(c * 100))
        if v:
            s += c * v; why.append("%d%% effect +%.3g" % (round(c * 100), c * v))
    dr = mv.get("drain")
    if isinstance(dr, list):
        d = DRAIN_WORTH * dr[0] / dr[1] * p * h; s += d; why.append("drain %d/%d +%.3g" % (dr[0], dr[1], d))
    flat = 0.0
    pr = mv.get("priority", 0)
    if pr > 0:
        flat += PRIORITY_PLUS * min(pr, 2); why.append("priority +%d" % pr)
    elif pr < 0:
        flat += PRIORITY_MINUS; why.append("priority %d" % pr)
    if mv.get("selfSwitch"):
        flat += PIVOT_DAMAGING; why.append("pivots")
    if mv.get("forceSwitch"):
        flat += PHAZE_DAMAGING; why.append("forces a switch")
    code = [k for k in ("onHit", "onAfterHit", "onBasePower", "basePowerCallback", "onAfterMove", "onTryMove")
            if mv.get(k) == "<fn>" and mid not in NOMINAL]
    if code:
        why.append("also code (%s): not valued" % ", ".join(code))
    return a * (p * h * m + s) + flat * (a if flat > 0 else 1), a, why


def score_status(mid, mv):
    why = []
    a = 1.0 if mv.get("accuracy") is True else mv.get("accuracy", 100) / 100.0
    tgt = mv.get("target")
    v = 0.0
    hand = mid in STATUS_HAND
    if hand:
        v, r = STATUS_HAND[mid]
        why.append("by hand %d (%s)" % (v, r))
    else:
        if mv.get("status") in STATUS_INFLICT:
            v += STATUS_INFLICT[mv["status"]]; why.append("inflicts %s %d" % (mv["status"], STATUS_INFLICT[mv["status"]]))
        boosts = _stage_list(mv.get("boosts"))
        if tgt in ("self", "allies", "adjacentAllyOrSelf", "allySide"):
            off = sorted((n for st, n in boosts if st in ("atk", "spa") and n > 0), reverse=True)
            stage = lambda n, per: per * min(n, 2) + per * 0.5 * max(n - 2, 0)
            if off:
                v += stage(off[0], OFFENSE_STAGE)
                if len(off) > 1:
                    v += 0.5 * stage(off[1], OFFENSE_STAGE)
            for st, n in boosts:
                if st in ("atk", "spa"):
                    continue
                if n > 0:
                    v += stage(n, SELF_STAGE.get(st, 20))
                else:
                    v -= SELF_STAGE.get(st, 20) * -n
            if boosts:
                why.append("self boosts %s" % dict(boosts))
        elif tgt in ("adjacentAlly",):
            v += ALLY_ONLY * sum(OFFENSE_STAGE * n for _, n in boosts if n > 0)
            if boosts:
                why.append("ally-only boosts x%.2g" % ALLY_ONLY)
        else:
            for st, n in boosts:
                if n < 0:
                    v += TARGET_DROP_STAGE.get(st, 15) * -n
                else:
                    v -= 15 * n  # Swagger, Flatter: the target gains
            if boosts:
                why.append("target stages %s" % dict(boosts))
        sc = mv.get("sideCondition")
        if sc:
            v += SIDE.get(sc.lower(), 10); why.append("side %s" % sc)
        if mv.get("weather"):
            v += WEATHER.get(mv["weather"].lower(), 30); why.append("weather %s" % mv["weather"])
        if mv.get("terrain"):
            v += TERRAIN; why.append("terrain")
        if mv.get("pseudoWeather"):
            v += PSEUDO.get(mv["pseudoWeather"], 10); why.append("field %s" % mv["pseudoWeather"])
        vs = mv.get("volatileStatus")
        if vs and vs != "<fn>":
            v += VOLATILE.get(vs, 10); why.append("volatile %s" % vs)
        if mv.get("stallingMove"):
            pv = PROTECT if mv.get("volatileStatus") in ("protect", None) or mid == "matblock" else PROTECT_PLUS
            if mid in ("endure", "matblock"):
                pv = 0
            v += pv; why.append("protects %d" % pv)
        hl = mv.get("heal")
        if isinstance(hl, list):
            v += HEAL.get(round(hl[0] / hl[1], 2), 75 * hl[0] / hl[1] * 2); why.append("heals %d/%d" % tuple(hl))
        if mv.get("forceSwitch"):
            v += FORCE_SWITCH; why.append("forces a switch")
        ss = mv.get("selfSwitch")
        if ss and ss in SELF_SWITCH:
            v += SELF_SWITCH[ss]; why.append("pivots")
        sl = mv.get("slotCondition")
        if sl:
            v += SLOT.get(sl.lower(), 30); why.append("slot %s" % sl)
        if mv.get("selfdestruct"):
            v += SELFDESTRUCT_STATUS; why.append("user faints %d" % SELFDESTRUCT_STATUS)
        if mid in HP_COST:
            v += HP_COST[mid][0]; why.append("costs %s" % HP_COST[mid][1])
        if "charge" in mv.get("flags", {}):
            v *= CHARGE; why.append("charge turn x%.2g" % CHARGE)
    if v > 0 and (mv.get("pp") or 99) <= LOW_PP[0]:
        v *= LOW_PP[1]; why.append("%d PP x%.2g" % (mv["pp"], LOW_PP[1]))
    if not hand:
        if not why:
            why.append("no field the rule values and no hand value: 0")
    return a * v, a, why, hand


def run(server_dir, moves_json):
    """({tm item: row}, [TMs with no move], moves source, moves.js sha256, bands)."""
    moves, moves_src, sha = load_moves(server_dir, moves_json)
    doc = tm_gate.load()
    bands = doc["badge_rule"]["power"]["bands"]
    resolved = tm_gate.resolve(tm_gate.read_server(server_dir))
    tm_recipes, problems = tm_gate.tm_recipe_table(doc, resolved)
    if problems:
        raise SystemExit("tm_power_score: %s" % "; ".join(problems[:5]))
    order = doc["badge_rule"]["grade_order"]
    rows = {}
    missing = []
    for item in sorted(tm_recipes):
        mid = item[len("tmcraft:tm_"):]
        mv = moves.get(mid)
        if mv is None:
            missing.append(item)
            continue
        grades = [grade for _, _, grade, _ in tm_recipes[item] if grade is not None]
        if mv["category"] == "Status":
            sc, acc, why, hand = score_status(mid, mv)
        else:
            sc, acc, why = score_damaging(mid, mv)
            hand = mid in NOMINAL
        rows[item] = {"move": mv.get("name"), "type": mv.get("type"), "category": mv["category"],
                      "base_power": mv.get("basePower"), "accuracy": mv.get("accuracy"), "pp": mv.get("pp"),
                      "priority": mv.get("priority"), "score": round(sc, 1), "power_badge": tm_gate.band(sc, bands),
                      "valued_by_hand": hand, "terms": why,
                      "disc_grade": order[max(grades)] if grades else None}
    return rows, missing, moves_src, sha, bands


def render(rows, src, sha, bands):
    """The table's text: one TM per line, one JSON document."""
    dist = collections.Counter(r["power_badge"] for r in rows.values())
    out = {"schema": SCHEMA, "generated_by": "tools/tm_power_score.py",
           "status": "the gate's score table: tools/tm_gate.py places every TM with no shelf line and no outlier "
                     "placement by the band of its score (data/tm_gate.json badge_rule.power)",
           "moves_source": src, "moves_sha256": sha,
           "bands": {"1": "score < %s" % bands["badge_1_below"],
                     **{k: "score <= %s" % v for k, v in sorted(bands["top"].items())},
                     str(bands["above_top"]): "score > %s" % max(bands["top"].values())},
           "counts": {"power_rule": {str(k): v for k, v in sorted(dist.items())}},
           "tms": {}}
    head = json.dumps(out, indent=1)[:-len('{}\n}')].rstrip()  # everything up to the empty "tms" object
    body = ",\n".join("  %s: %s" % (json.dumps(k), json.dumps(v)) for k, v in sorted(rows.items()))
    text = head + " {\n" + body + "\n }\n}\n"
    json.loads(text)  # one TM per line, and still one JSON document
    return text, dist


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--server-dir", required=True)
    ap.add_argument("--moves-json")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--check", action="store_true", help="compare with the committed table; write nothing")
    a = ap.parse_args(argv)
    rows, missing, src, sha, bands = run(a.server_dir, a.moves_json)
    if missing:
        print("tm_power_score: %d TM(s) with no move in %s: %s" % (len(missing), src, missing[:10]))
        return 1
    text, dist = render(rows, src, sha, bands)
    out = Path(a.out)
    if a.check:
        old = out.read_text(encoding="utf-8") if out.is_file() else ""
        if old == text:
            print("tm_power_score --check: %s is current (%d TMs, moves.js %s)" % (out, len(rows), sha[:12]))
            return 0
        a_lines, b_lines = old.splitlines(), text.splitlines()
        diff = [n for n in range(max(len(a_lines), len(b_lines)))
                if (a_lines[n] if n < len(a_lines) else None) != (b_lines[n] if n < len(b_lines) else None)]
        print("tm_power_score --check: %s is NOT current: %d line(s) differ, first at line %d; re-run without --check"
              % (out, len(diff), diff[0] + 1))
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print("tm_power_score: %d TMs; power rule %s; moves.js %s; written %s" % (
        len(rows), dict(sorted(dist.items())), sha[:12], out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
