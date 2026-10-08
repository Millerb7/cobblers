#!/usr/bin/env python
"""Independent audit of Heaven's Arena's runtime pack, as EMITTED (build/datapacks/cobblers_arena).

Written by an agent that did not build tools/arena_runtime.py. Nothing here imports arena_runtime or calls any of its
helpers: every expectation is derived from the data the design owns --

  data/arena_fights.json    ranks, bands (the level caps), formats, set_pool + min_rank, rank_up_fights, prizes,
                            advancement_rule, purse_formula and the designer's own `typical` purses
  data/arena_trainers.json  the champions' authored teams (the exams) and the retired spire seats
  data/arena_dome.json      the venues: ranks, challenger_mark, opponent_spot, post
  data/progression.json     the flag namespace (one flag is one advancement `<ns>:flag/<id>`)
  data/league_trainers.json the upstream advancement that records "Lance beaten"
  data/blackout.json        arena_exempt.player_tag

-- and every behaviour is checked by EXECUTING the emitted .mcfunction files in this file's own small command model
(World below): scoreboards, tags, storage, macros, execute chains, selectors with distance/scores/advancements, the
emitted battle_victory callback's own run_command lines, and the two runmolang shapes the pack uses. A command the
model does not know is a failure, not a skip. The challenge calls the level-cap pack's battle_check (sweep U54), so the
flows run that pack too (emitted by tools/levelcap_pack.py for data/level_cap.json, or --levelcap-pack): `execute
store result score`, `rctmod player get level_cap` (each model player has a cap, or none: the command fails and 0 is
stored) and party_compare's runmolang on the party's highest level. Its expectation is rctmod's own rule (strictly
over the cap refuses), not anything the generator computes.

The purse rounding is taken from the data, not from the builder: prizes.purse_formula says "nearest 50 of 13 x
(level sum)", and rank 8's typical_per_leg (13 x (74+75+76) = 2925, typed as 2900) fixes an exact half as rounding
DOWN. Every `typical` figure in the data is re-derived with that rule (check `data`) before it is used as an
expectation, so a data slip is named as one rather than blamed on the pack.

NOT COVERED (validity is not runtime behaviour):
  - whether Cobblemon 1.8.0 accepts each properties string, move or held item (no jar here; mechanism_needs N11);
  - whether the battle_victory event's lists really hold the NPC and the player as the callback assumes (the 2026-10-03
    probe proved a win and a loss reach a callback; the exact collections are read from the emitted text, not proven);
  - levelVariation's semantics: taken as VERIFIED "NPC level + 0..levelVariation" from
    docs/research/notes/arena-per-player-opponents.md section 2 (PoolPartyProvider.formulateParty @1.8.0);
  - the draw constraints a pool cannot express (decisions_pending "draw") and battle rules (`maxItemUses` not applied,
    decisions_pending "battle_rules");
  - CobbleDollars' own NPC-win payout (unit ARENACAP, flows 10-11) is MODELLED from the jar's bytecode, not seen: which
    of its handler and Cobblemon's callback runs first (both orders are walked), whether `/cobbledollars pay` can be
    typed with the battle screen open, and that `execute store result ... run cobbledollars query` stores the balance
    are experiments/EXP-060-arena-payout. Money moved by ANOTHER source inside a clawback window is measured and
    printed as EDGE lines, not failed: the balance-delta mechanism cannot tell it from the payout (owner decision);
  - two players, a forfeit, a flee and canChallenge against a click have never been run in a game.
"""
import argparse
import itertools
import json
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_arena"
DOME = DATA / "arena_dome.json"
FN = "cobblers:arena/"

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
NUM = re.compile(r"-?\d+(?:\.\d+)?")

# Legendary, mythical and Ultra Beast species (Showdown ids), typed here from the games, not from any repo file, so the
# pool cannot pass by agreeing with a list the builder also reads. Q6: no legendaries in drawn sets or exams.
LEGENDARY = set("""
articuno zapdos moltres mewtwo mew raikou entei suicune lugia hooh celebi regirock regice registeel latias latios
kyogre groudon rayquaza jirachi deoxys uxie mesprit azelf dialga palkia heatran regigigas giratina cresselia phione
manaphy darkrai shaymin arceus victini cobalion terrakion virizion tornadus thundurus reshiram zekrom landorus kyurem
keldeo meloetta genesect xerneas yveltal zygarde diancie hoopa volcanion typenull silvally tapukoko tapulele tapubulu
tapufini cosmog cosmoem solgaleo lunala necrozma magearna marshadow zeraora meltan melmetal nihilego buzzwole
pheromosa xurkitree celesteela kartana guzzlord poipole naganadel stakataka blacephalon zacian zamazenta eternatus
kubfu urshifu zarude regieleki regidrago glastrier spectrier calyrex enamorus wochien chienpao tinglu chiyu koraidon
miraidon walkingwake ironleaves okidogi munkidori fezandipiti ogerpon terapagos pecharunt gougingfire ragingbolt
ironboulder ironcrown
""".split())
# a held item that is a Mega Stone: Mega Showdown's namespace, or a stone's own name shape (eviolite is not one)
MEGA_ITEM = re.compile(r"(mega_showdown|ite(_[xy])?$)")
NOT_MEGA = {"eviolite"}

# Defects this audit found in the builder's output on 2026-10-03 and reported, NOT fixed (the auditor does not edit
# the builder). They still FAIL the audit -- a post that cannot be summoned is an arena nobody can enter -- and are
# labelled so the reader knows they are reported. tests/test_arena_runtime_audit.py fails when one stops reproducing,
# so this list is pruned when the builder is fixed.
KNOWN = {    # post_coords: fixed in tools/arena_runtime.py posts/place (2026-10-03, the integrating session)
    # claw_margin: fixed by e839de0 (CLAW_MARGIN 0); pruned 2026-10-08 (review N143 audit), when the stale entry was
    # failing tests/test_arena_runtime_audit.py at 3d7237b as well as at 3aaa71e. What is left of it -- cd_bound's
    # S*S//10 is $4 over the jar's top credit for the rank 3 pool, where the double sum rounds below S*S/10 -- is a
    # strict xfail in tests/test_arena_clawback_timing.py (this audit's rank 1 check cannot see it: 171 is tight)
}


class AuditError(Exception):
    pass


def i32(v):
    """A Java int: what a scoreboard score and BigInteger.intValue() hold (two's complement, 32 bits)."""
    return (v + 2 ** 31) % 2 ** 32 - 2 ** 31


def doc(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ======================================================================================== expectations, from data only

def nearest(v, step):
    """To the nearest `step`, an exact half DOWN (the data's own rank 8 figure; see the module docstring)."""
    q, r = divmod(v, step)
    return q * step + (step if r * 2 > step else 0)


class Expect:
    def __init__(self, dome_path=DOME, data=DATA):
        self.fights = doc(data / "arena_fights.json")
        self.trainers = {t["id"]: t for t in doc(data / "arena_trainers.json")["trainers"]}
        self.dome = doc(dome_path)
        self.prog = doc(data / "progression.json")
        self.bout_tag = doc(data / "blackout.json")["arena_exempt"]["player_tag"]
        f = self.fights
        m = re.search(r"nearest (\d+) of (\d+) x", f["prizes"]["purse_formula"])
        if not m:
            raise AuditError("prizes.purse_formula no longer states 'nearest N of K x': no purse can be expected")
        self.step, self.k = int(m.group(1)), int(m.group(2))
        self.ranks = {r["rank"]: r for r in f["ranks"]}
        self.bands = {b["id"]: b for b in f["bands"]}
        self.sets = f["set_pool"]["sets"]
        self.exams = {e["rank"]: e for e in f["rank_up_fights"]}
        self.venues = {v["id"]: v for v in self.dome["venues"]}
        self.venue_index = {v["id"]: i for i, v in enumerate(self.dome["venues"], 1)}
        ns = self.prog["namespace"]
        flags = {x["id"] for x in self.prog["flags"]}
        self.flag = {}
        for fid in ("gym8_cleared", "champion_cleared"):
            if fid not in flags:
                raise AuditError("data/progression.json has no flag %s" % fid)
            self.flag[fid] = "%s:flag/%s" % (ns, fid)
        lt = json.dumps(doc(data / "league_trainers.json"))
        lance = sorted(set(re.findall(r"[a-z_]+:trainer/[a-z_/]*lance", lt)))
        if len(lance) != 1:
            raise AuditError("data/league_trainers.json names %d 'Lance beaten' advancements: %s" % (len(lance), lance))
        self.flag["rct_defeated:kanto_league_lance"] = lance[0]
        self.prizes = {p["id"]: p for p in f["prizes"]["items"]}
        # prizes.purse_policy (docs/mechanics/ECONOMY_OVERHAUL.md section 6): a flat repeat purse, at most
        # daily_cap_wins paid repeats per player per day_ticks of GAME time; CobbleDollars' own payout keeps nothing
        pol = f["prizes"].get("purse_policy")
        if not isinstance(pol, dict):
            raise AuditError("data/arena_fights.json prizes.purse_policy is missing: no repeat purse can be expected")
        knobs = [pol.get(k) for k in ("repeat_purse", "daily_cap_wins", "day_ticks")]
        if not all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in knobs) or not knobs[2]:
            raise AuditError("prizes.purse_policy knobs are not integers >= 0 (day_ticks >= 1): %r" % knobs)
        self.rep, self.rep_cap, self.day = knobs
        self.kept_cap = (pol.get("cobbledollars_auto_payout") or {}).get("kept_cap")
        cd = doc(ROOT / "modpack" / "config" / "cobbledollars" / "common.json")
        self.cd_mult, self.cd_npc = cd["cobbleDollarsIncomeMultiplier"], cd["earnCobbleDollarsFromNPC"]

    # -- per rank
    def band(self, n):
        b = self.bands[self.ranks[n]["band"]]
        if n not in b["ranks"]:
            raise AuditError("rank %d names band %s, whose ranks %s do not list it" % (n, b["id"], b["ranks"]))
        return b

    def cap(self, n):
        return self.band(n)["cap"]

    def is_streak(self, n):
        return self.ranks[n]["format"] == "streak"

    def legs(self, n):
        r = self.ranks[n]
        return r.get("legs", 1) if r["format"] == "gauntlet" else 1

    def need(self, n):
        a = self.ranks[n]["advance"]
        return a.get("wins_at_rank", a.get("clears_at_rank"))

    def open_species(self, n):
        return {s["member"]["species"] for s in self.sets if s["min_rank"] <= n}

    def set_of(self, species):
        (s,) = [x for x in self.sets if x["member"]["species"] == species]
        return s["member"]

    def pool_leg_purse(self, n):
        """The designer's figure per bout (single) or per leg (gauntlet), checked against the formula in `data`."""
        p = self.ranks[n]["purse"]
        return p.get("typical", p.get("typical_per_leg"))

    def clear_bonus(self, n):
        return self.ranks[n]["purse"].get("clear_bonus", 0)

    def exam_legs(self, n):
        e = self.exams[n]
        return list(e["legs"]) if "legs" in e else [e["trainer"]]

    def exam_leg_purse(self, tid):
        return nearest(self.k * sum(m["level"] for m in self.trainers[tid]["team"]), self.step)

    def requires_met(self, n, advs):
        """band.requires: every entry must hold; an entry is tokens joined by ' OR '."""
        for req in self.band(n).get("requires", []):
            if not any(self.flag[t.strip()] in advs for t in req.split(" OR ")):
                return False
        return True

    def venues_offering(self, n):
        return sorted(v for v, d in self.venues.items() if n in d["ranks"])

    def offered(self, venue, rank, advs):
        """What a click at `venue` gives a player holding `rank` and `advs`: the highest of the venue's ranks at or
        below theirs whose band they meet (advancement_rule playing_down + band_gate; decisions_pending exam_rematch:
        'a venue post always offers the pool bout of the highest open rank'). None when nothing is open."""
        ok = [r for r in self.venues[venue]["ranks"] if r <= rank and self.requires_met(r, advs)]
        return max(ok) if ok else None

    def prize_for(self, on):
        """The prize items whose `on` names this event (first win over <trainer> / first clear of <id> /
        first streak of N)."""
        return [p for p in self.prizes.values() if p["on"] == on]

    def exam_prize(self, n):
        e = self.exams[n]
        on = ("first clear of %s" % e["id"]) if "legs" in e else ("first win over %s" % e["trainer"])
        got = self.prize_for(on)
        if len(got) != 1:
            raise AuditError("rank %d: %d prizes.items say %r" % (n, len(got), on))
        return got[0]

    def heal_before(self, n, leg):
        """Q3 default + formats: a single bout heals at its start; a gauntlet at its start and before the leg after
        `intermission_after_leg`; legs are counted from 0."""
        if leg == 0:
            return True
        k = self.ranks[n].get("intermission_after_leg")
        return k is not None and leg == k

    # -- the streak
    def streak(self):
        (n,) = [n for n in self.ranks if self.is_streak(n)]
        s = self.ranks[n]["streak"]
        m = re.fullmatch(r"members \+1 every (\d+) wins, to (\d+)", s["at_level_max"])
        if not m:
            raise AuditError("streak.at_level_max %r cannot be read" % s["at_level_max"])
        return n, s, int(m.group(1)), int(m.group(2))

    def streak_bout(self, wins):
        """(level of the ace, team size) for the bout fought with `wins` wins already in the run."""
        _n, s, every_m, mmax = self.streak()

        def level(w):
            return min(s["level_max"], s["level_start"] + s["level_step"] * (w // s["level_step_every_wins"]))
        full = next(w for w in itertools.count() if level(w) >= s["level_max"])
        m = min(mmax, s["members_start"] + max(0, wins - full) // every_m)
        return level(wins), m

    def streak_purse(self, wins):
        L, m = self.streak_bout(wins)
        return nearest(self.k * sum(L - i for i in range(m)), self.step)


def check_data(E, problems):
    """The data's own figures against its own formula: a slip here is the data's, named before the pack is judged."""
    for n, r in sorted(E.ranks.items()):
        if E.is_streak(n):
            continue
        top, m = r["levels"]["top"], r["members"]
        if top > E.cap(n):
            problems.append("data: rank %d's top %d is over its band cap %d" % (n, top, E.cap(n)))
        want = nearest(E.k * sum(top - i for i in range(m)), E.step)
        if E.pool_leg_purse(n) != want:
            problems.append("data: rank %d's typical purse %s != %d x levels %d..%d to the nearest %d = %d"
                            % (n, E.pool_leg_purse(n), E.k, top - m + 1, top, E.step, want))
    for n, e in sorted(E.exams.items()):
        tot = sum(E.exam_leg_purse(t) for t in E.exam_legs(n))
        if e.get("purse_typical") != tot:
            problems.append("data: rank_up_fights rank %d purse_typical %s != %d from the authored levels"
                            % (n, e.get("purse_typical"), tot))
    covered = {r for v in E.venues.values() for r in v["ranks"]}
    if covered != set(E.ranks):
        problems.append("data: venues offer ranks %s, the ladder has %s" % (sorted(covered), sorted(E.ranks)))


# ================================================================================================ the emitted pack

class Pack:
    def __init__(self, root):
        self.root = Path(root)
        if not (self.root / "pack.mcmeta").is_file():
            raise AuditError("%s is not a pack (no pack.mcmeta): run python tools/arena_runtime.py first" % root)
        self.text = {}
        for p in sorted(self.root.rglob("*")):
            if p.is_file():
                self.text[p.relative_to(self.root).as_posix()] = p.read_text(encoding="utf-8")
        self.functions, self.classes, self.advancements, self.callbacks = {}, {}, {}, {}
        for rel, t in self.text.items():
            m = re.fullmatch(r"data/([a-z0-9_]+)/function/(.+)\.mcfunction", rel)
            if m:
                self.functions["%s:%s" % m.groups()] = t.splitlines()
            m = re.fullmatch(r"data/([a-z0-9_]+)/npcs/(.+)\.json", rel)
            if m:
                self.classes["%s:%s" % m.groups()] = json.loads(t)
            m = re.fullmatch(r"data/([a-z0-9_]+)/advancement/(.+)\.json", rel)
            if m:
                self.advancements["%s:%s" % m.groups()] = json.loads(t)
            if rel.startswith("data/cobblemon/callbacks/"):
                self.callbacks[rel] = t
        self.load_tag = json.loads(self.text.get("data/minecraft/tags/function/load.json", '{"values":[]}'))["values"]
        self.tick_tag = json.loads(self.text.get("data/minecraft/tags/function/tick.json", '{"values":[]}'))["values"]


def parse_props(s):
    """A Cobblemon properties string -> {species, level, moves, ability, held_item, nature, other}."""
    toks = s.split()
    out = {"species": toks[0], "other": []}
    for t in toks[1:]:
        if "=" not in t:
            out["other"].append(t)
            continue
        k, v = t.split("=", 1)
        if k == "moves":
            out["moves"] = v.split(",")
        elif k == "level":
            out["level"] = int(v)
        elif k in ("ability", "held_item", "nature"):
            out[k] = v
        else:
            out["other"].append(t)
    return out


def want_props(member, level=None):
    item = member.get("heldItem")
    return {"species": member["species"], "moves": list(member["moveset"]), "ability": member.get("ability"),
            "held_item": (item if ":" in item else "cobblemon:" + item) if item else None,
            "nature": member.get("nature"), "level": level}


def got_props(p):
    return {"species": p["species"], "moves": p.get("moves"), "ability": p.get("ability"),
            "held_item": p.get("held_item"), "nature": p.get("nature"), "level": p.get("level")}


def no_legend_no_mega(where, p, problems):
    if p["species"] in LEGENDARY:
        problems.append("%s: %s is legendary/mythical (Q6: none in the arena)" % (where, p["species"]))
    item = (p.get("held_item") or "").split(":")[-1]
    if (item and MEGA_ITEM.search(p.get("held_item") or "") and item not in NOT_MEGA) or "mega" in " ".join(p["other"]):
        problems.append("%s: %s holds or is a Mega (%s %s)" % (where, p["species"], p.get("held_item"), p["other"]))


def check_classes(E, P, problems):
    sn, s, _e, mmax = E.streak()
    want = {"cobblers:arena_rank_%d" % n for n in E.ranks if not E.is_streak(n)}
    want |= {"cobblers:arena_streak_m%d" % m for m in range(s["members_start"], mmax + 1)}
    want |= {"cobblers:arena_exam_%s" % t for n in E.exams for t in E.exam_legs(n)}
    if set(P.classes) != want:
        problems.append("classes: emitted %s, the data needs %s (extra %s, missing %s)"
                        % (len(P.classes), len(want), sorted(set(P.classes) - want), sorted(want - set(P.classes))))
    for cid, c in sorted(P.classes.items()):
        for k, v in (("isInvulnerable", True), ("isMovable", False), ("canDespawn", False)):
            if c.get(k) is not v:
                problems.append("class %s: %s is %r, must be %r" % (cid, k, c.get(k), v))
        if (c.get("battleConfiguration") or {}).get("canChallenge") is not False:
            problems.append("class %s: battleConfiguration.canChallenge must be false (no one else may click in)" % cid)
        party = c.get("party") or {}
        m = re.fullmatch(r"cobblers:arena_(rank_(\d+)|streak_m(\d+)|exam_(.+))", cid)
        if not m:
            continue
        if m.group(4):                                            # an exam: the champion's authored team, exactly
            tid = m.group(4)
            if party.get("type") != "simple":
                problems.append("class %s: an exam must be a simple (fixed) party, is %r" % (cid, party.get("type")))
                continue
            got = [parse_props(x) for x in party.get("pokemon", [])]
            team = E.trainers[tid]["team"]
            if [got_props(g) for g in got] != [want_props(t, t["level"]) for t in team]:
                problems.append("class %s: team %s != data/arena_trainers.json %s's authored team %s"
                                % (cid, [got_props(g) for g in got], tid, [want_props(t, t["level"]) for t in team]))
            for g in got:
                no_legend_no_mega("class " + cid, g, problems)
            continue
        n = int(m.group(2)) if m.group(2) else sn
        size = E.ranks[n]["members"] if m.group(2) else int(m.group(3))
        if party.get("type") != "pool" or party.get("isStatic") is not False:
            problems.append("class %s: must be a pool party with isStatic false (re-rolled per challenge), is %s/%r"
                            % (cid, party.get("type"), party.get("isStatic")))
        if str(party.get("minPokemon")) != str(size) or str(party.get("maxPokemon")) != str(size):
            problems.append("class %s: min/maxPokemon %s/%s, the rank fields %d"
                            % (cid, party.get("minPokemon"), party.get("maxPokemon"), size))
        entries = party.get("pool", [])
        got = [parse_props(e["pokemon"]) for e in entries]
        species = [g["species"] for g in got]
        if sorted(species) != sorted(E.open_species(n)):
            problems.append("class %s: pool species %s != set_pool entries with min_rank <= %d %s (extra %s, missing %s)"
                            % (cid, len(species), n, len(E.open_species(n)), sorted(set(species) - E.open_species(n)),
                               sorted(E.open_species(n) - set(species))))
        for e, g in zip(entries, got):
            no_legend_no_mega("class " + cid, g, problems)
            if g["species"] in E.open_species(n) and got_props(g) != want_props(E.set_of(g["species"])):
                problems.append("class %s: %s's set %s != set_pool %s"
                                % (cid, g["species"], got_props(g), want_props(E.set_of(g["species"]))))
            if e.get("levelVariation") != size - 1:
                problems.append("class %s: %s levelVariation %r; the draw spans `members` levels (%d)"
                                % (cid, g["species"], e.get("levelVariation"), size - 1))
            for k in ("level", "npcLevels"):
                if k in e:
                    problems.append("class %s: pool entry %s sets %s, which overrides the spawn level"
                                    % (cid, g["species"], k))


def check_static(E, P, problems):
    # no player identity anywhere: names and UUIDs are never written into a file
    for rel, t in sorted(P.text.items()):
        if UUID_RE.search(t):
            problems.append("%s: a UUID literal %s" % (rel, UUID_RE.search(t).group(0)))
        for m in re.finditer(r"@[aeprs]\[[^\]\s]*\bname=", t):
            problems.append("%s: a selector by player name: %s" % (rel, m.group(0)))
        for m in re.finditer(r"\bscoreboard players (?:set|add|remove|reset|get|operation) (\S+)", t):
            if not m.group(1).startswith(("@", "#", "$(")):
                problems.append("%s: a named score holder %r (a player's name in a file)" % (rel, m.group(1)))
        for m in re.finditer(r'"name"\s*:\s*"([^"]*)"', t):
            if m.group(1) != "@s":
                problems.append("%s: a text score component for %r" % (rel, m.group(1)))
    # each venue: spawn at its opponent_spot, absolute; battle started by runmolang start_battle
    for vid, v in E.venues.items():
        fn = P.functions.get(FN + "venue/%s/spawn" % vid)
        if fn is None:
            problems.append("venue %s: no venue/%s/spawn function" % (vid, vid))
            continue
        sp = [ln for ln in fn if re.match(r"\$?spawnnpcat ", ln)]
        if len(sp) != 1:
            problems.append("venue %s: %d spawnnpcat lines" % (vid, len(sp)))
            continue
        toks = sp[0].split()
        if not sp[0].startswith("$") or toks[4:6] != ["$(cls)", "$(level)"]:
            problems.append("venue %s: spawnnpcat is not a macro of the class and level: %s" % (vid, sp[0]))
        if not all(NUM.fullmatch(x) for x in toks[1:4]):
            problems.append("venue %s: spawnnpcat at %s, not ABSOLUTE coordinates (the relative form spawned "
                            "nothing in game, note section 8)" % (vid, toks[1:4]))
        elif [float(x) for x in toks[1:4]] != [float(x) for x in v["opponent_spot"][:3]]:
            problems.append("venue %s: spawnnpcat at %s, its opponent_spot is %s" % (vid, toks[1:4], v["opponent_spot"][:3]))
    begin = "\n".join(P.functions.get(FN + "bout/begin", []))
    if not re.search(r"^runmolang \"[^\"]*q\.npc\.start_battle\(q\.player, 'singles'\)", begin, re.M):
        problems.append("bout/begin: no `runmolang ... q.npc.start_battle(q.player, 'singles')` (the proven start)")
    if "t.b == 0" not in begin:
        problems.append("bout/begin: start_battle's 0 (refused) is not handled")
    # the posts: an interaction at each venue's post, clickable into that venue's challenge
    place = P.functions.get(FN + "posts/place", [])
    for vid, v in E.venues.items():
        adv = P.advancements.get("cobblers:arena/post_%s" % vid)
        if adv is None:
            problems.append("venue %s: no advancement arena/post_%s" % (vid, vid))
            continue
        try:
            nbt = adv["criteria"]["click"]["conditions"]["entity"][0]["predicate"]["nbt"]
        except (KeyError, IndexError, TypeError):
            nbt = ""
        m = re.fullmatch(r'\{Tags:\["([a-z0-9_]+)"\]\}', nbt)
        tag = m.group(1) if m else None
        lines = [ln for ln in place if ln.startswith("summon minecraft:interaction ") and tag and '"%s"' % tag in ln]
        if len(lines) != 1:
            problems.append("venue %s: %d interaction summons carry the advancement's tag %s" % (vid, len(lines), tag))
            continue
        xyz = lines[0].split()[2:5]
        if not all(NUM.fullmatch(x) for x in xyz):
            problems.append("KNOWN post_coords: venue %s: the post is summoned at %s, not a coordinate (post %s)"
                            % (vid, " ".join(xyz), v["post"]))
        elif [float(x) for x in xyz] != [float(x) for x in v["post"][:3]]:
            problems.append("venue %s: the post is summoned at %s, data says %s" % (vid, xyz, v["post"]))
        rw = adv.get("rewards", {}).get("function")
        if FN + "challenge/%s" % vid not in "\n".join(P.functions.get(rw, [])):
            problems.append("venue %s: the post's reward %s does not run challenge/%s" % (vid, rw, vid))
        trig = adv.get("criteria", {}).get("click", {}).get("trigger")
        if trig != "minecraft:player_interacted_with_entity":
            problems.append("venue %s: the post's trigger is %r" % (vid, trig))
    for ln in place:
        if ln.startswith("summon minecraft:text_display "):
            xyz = ln.split()[2:5]
            if not all(NUM.fullmatch(x) for x in xyz):
                problems.append("KNOWN post_coords: a post label is summoned at %s" % " ".join(xyz))
    # the retired spire champions: killed where they stood, and only those
    retire = [ln for ln in P.functions.get(FN + "retire_spire", []) if ln.startswith("kill ")]
    want = {}
    for tid, t in E.trainers.items():
        if t.get("seated") is False and t.get("superseded_seat"):
            x, y, z = t["superseded_seat"]["seat"]
            want[tid] = (x + 0.5, y, z + 0.5)
    got = {}
    for ln in retire:
        m = re.search(r'x=([-\d.]+),y=([-\d.]+),z=([-\d.]+),.*TrainerId:"([a-z0-9_]+)"', ln)
        if m and "type=rctmod:trainer" in ln:
            got[m.group(4)] = tuple(float(m.group(i)) for i in (1, 2, 3))
        else:
            problems.append("retire_spire: a kill that is not one retired champion: %s" % ln)
    if got != want:
        problems.append("retire_spire kills %s, the retired seats are %s" % (got, want))


def check_route_trainers(E, problems):
    """The seven retired champions get no seat, no rctmod record and no gate; everyone else seated still is."""
    sys.path.insert(0, str(ROOT / "tools"))
    import route_trainers                                        # the generator's OUTPUT is what is read here
    retired = {t for t, r in E.trainers.items() if r.get("seated") is False}
    seats = [p[0] for p in route_trainers.placements()]
    expected = 0
    # hq_trainers: the Compact HQ tower's seven (2026-10-04), the sixth seat file route_trainers reads. Brann and Elara
    # (data/finale_trainers.json) are NOT seats since the integration of 2026-10-04: they fight as Cobblemon NPCs in
    # the tower (tools/compile_dialogue.py, tools/hq_tower.py), so that file is not read here
    # and the gym juniors (data/gym_junior_trainers.json, 2026-10-06), seated by the same tool
    for f in ("route_trainers", "late_route_trainers", "mansion_guardians", "vr_trainers", "arena_trainers",
              "hq_trainers", "gym_junior_trainers"):
        expected += sum(1 for e in doc(DATA / ("%s.json" % f))["trainers"] if "seat" in e and e.get("seated") is not False)
    if len(seats) != expected:
        problems.append("route_trainers: %d seats placed, the seat files carry %d" % (len(seats), expected))
    if retired & set(seats):
        problems.append("route_trainers: retired champions still seated: %s" % sorted(retired & set(seats)))
    fs = route_trainers.files()
    for rel, content in fs.items():
        t = content if isinstance(content, str) else ("\n".join(content) if isinstance(content, list) else json.dumps(content))
        hit = sorted(r for r in retired if r in rel or r in t)
        if hit:
            problems.append("route_trainers: %s still names retired %s" % (rel, hit))
        if "to climb" in t or re.search(r"title @a\[x=", t):
            problems.append("route_trainers: %s still carries a spire stair gate line" % rel)


def blackout_files(pack_dir=None):
    """The blackout pack's files as its generator emits them for today's data (in memory unless a built pack is named)."""
    if pack_dir:
        root = Path(pack_dir)
        return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}
    sys.path.insert(0, str(ROOT / "tools"))
    import blackout_pack as B
    return B.build(B.load("blackout.json"), B.load("water_mounts.json"), B.load("placements.json"),
                   B.load("progression.json"), None)


def levelcap_pack(pack_dir=None, files=None):
    """The level-cap pack as its generator emits it for data/level_cap.json (in memory unless a built pack or a files
    dict is given): its functions ({"ns:path": [lines]}) and its load tag. The arena's challenge calls its battle_check
    (sweep U54, review N57), so the flows run it; nothing here is an expectation."""
    if files is None and pack_dir:
        root = Path(pack_dir)
        files = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}
    if files is None:
        sys.path.insert(0, str(ROOT / "tools"))
        import levelcap_pack as LC
        files = LC.files(doc(DATA / "level_cap.json"))
    fns = {}
    for rel, t in files.items():
        m = re.fullmatch(r"data/([a-z0-9_]+)/function/(.+)\.mcfunction", rel)
        if m:
            fns["%s:%s" % m.groups()] = t.splitlines()
    load = json.loads(files.get("data/minecraft/tags/function/load.json", '{"values":[]}'))["values"]
    return types.SimpleNamespace(functions=fns, load_tag=load)


def check_blackout(E, bfiles, problems):
    """Only a player holding the bout tag is exempt, only from the NPC-loss path, and before anything is charged."""
    tag = E.bout_tag
    holders = sorted(rel for rel, t in bfiles.items()
                     if tag in "\n".join(ln for ln in t.splitlines() if not ln.lstrip().startswith("#")))
    if holders != ["data/cobblers/function/blackout/battle_loss_npc.mcfunction"]:
        problems.append("blackout: the arena tag %s is read in %s; it must exempt the NPC-loss path only" % (tag, holders))
    npc = [ln for ln in bfiles.get("data/cobblers/function/blackout/battle_loss_npc.mcfunction", "").splitlines()
           if ln.strip() and not ln.startswith("#")]
    if not npc or npc[0] != "execute if entity @s[tag=%s] run return 0" % tag:
        problems.append("blackout: battle_loss_npc's first command is %r, not the arena early return" % (npc[:1],))
    for ln in npc:
        m = re.search(r"tag=([^,\]]+)", ln)
        if m and "return" in ln and m.group(1) != tag:
            problems.append("blackout: battle_loss_npc also exempts %s" % m.group(1))


# ======================================================================================= the command model

class Ent:
    _n = 0

    def __init__(self, kind, pos, **kw):
        Ent._n += 1
        self.id = Ent._n
        self.uuid = "00000000-0000-4000-8000-%012d" % self.id
        self.type = kind
        self.pos = tuple(float(x) for x in pos)
        self.tags = set()
        self.alive = True
        self.in_battle = False
        self.advs = set(kw.pop("advs", ()))
        self.cls = kw.pop("cls", None)
        self.level = kw.pop("level", None)
        # a player's RCT level cap (None: `rctmod player get level_cap` fails) and the party's highest level; the
        # default sits AT the cap, so every flow also walks the strictly-over boundary (sweep U54)
        self.cap = kw.pop("cap", 50)
        self.party = kw.pop("party", 50)
        self.money, self.items, self.heals, self.said = [], [], 0, []
        # bal: the CobbleDollars balance `cobbledollars query` answers; money (above) lists only the arena's own
        # `cobbledollars give` amounts; removed every amount `cobbledollars remove` actually took
        self.bal, self.removed = 0, []
        self.__dict__.update(kw)


def split_top(s):
    out, depth, cur, q = [], 0, "", False
    for ch in s:
        if ch == '"':
            q = not q
        if not q and ch in "{[":
            depth += 1
        if not q and ch in "}]":
            depth -= 1
        if ch == "," and depth == 0 and not q:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def in_range(v, spec, cast=int):
    if v is None:
        return False
    if ".." in spec:
        a, b = spec.split("..")
        return (a == "" or v >= cast(a)) and (b == "" or v <= cast(b))
    return v == cast(spec)


def snbt(s):
    s = s.strip()
    if s.startswith('"'):
        return json.loads(s)
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if not (s.startswith("{") and s.endswith("}")):
        raise AuditError("SNBT the model does not read: %s" % s)
    out = {}
    for part in split_top(s[1:-1]):
        k, v = part.split(":", 1)
        out[k.strip()] = snbt(v)
    return out


class Return(Exception):
    pass


class World:
    """Just enough of a server to run the emitted functions: players, NPCs, scores, tags, storage, a battle each."""

    def __init__(self, pack, extra_functions=None, refuse=False, levelcap=None):
        self.P = pack
        self.functions = dict(pack.functions)
        self.functions.update(extra_functions or {})
        # the level-cap pack (levelcap_pack()): the challenge calls its battle_check (sweep U54); its load tag runs too
        self.functions.update(levelcap.functions if levelcap else {})
        self.ents = []
        self.scores = {}
        self.objectives = set()
        self.storage = {}
        self.spawns = []            # (owner uuid, class, level, pos)
        self.stubbed = []           # calls into functions outside the arena that the model does not run
        self.refuse = refuse
        self.gametime = self.daytime = 0       # the world's clocks: one tick each per tick()
        self.failed_gets = []                  # `scoreboard players get` of an unset score (a failed command)
        self.callback = self._parse_callback()
        self.depth = 0
        for f in pack.load_tag + (levelcap.load_tag if levelcap else []):
            self.run_function(f, None, None)

    # -------- entities
    def player(self, pos, advs=(), cap=50, party=50):
        e = Ent("minecraft:player", pos, advs=advs, cap=cap, party=party)
        self.ents.append(e)
        return e

    def alive(self):
        return [e for e in self.ents if e.alive]

    def npcs(self):
        return [e for e in self.alive() if e.type == "cobblemon:npc"]

    def score(self, holder, obj):
        key = holder.id if isinstance(holder, Ent) else holder
        return self.scores.get(obj, {}).get(key)

    def set_score(self, holder, obj, v):
        key = holder.id if isinstance(holder, Ent) else holder
        self.scores.setdefault(obj, {})[key] = v

    # -------- selectors
    def select(self, tok, ent, pos):
        if UUID_RE.fullmatch(tok):
            return [e for e in self.alive() if e.uuid == tok]
        m = re.fullmatch(r"@([aeps])(?:\[(.*)\])?", tok)
        if not m:
            raise AuditError("selector the model does not read: %s" % tok)
        kind, args = m.group(1), split_top(m.group(2) or "")
        if kind == "s":
            c = [ent] if ent is not None and ent.alive else []
        elif kind in "ap":
            c = [e for e in self.alive() if e.type == "minecraft:player"]
        else:
            c = self.alive()
        origin = pos
        kv = [a.split("=", 1) for a in args]
        for k, v in kv:
            if k in ("x", "y", "z"):
                o = list(origin or (0.0, 0.0, 0.0))
                o["xyz".index(k)] = float(v)
                origin = tuple(o)
        sort, limit = ("nearest", 1) if kind == "p" else (None, None)
        for k, v in kv:
            neg = v.startswith("!")
            val = v[1:] if neg else v
            if k == "type":
                c = [e for e in c if (e.type == val) != neg]
            elif k == "tag":
                c = [e for e in c if (val in e.tags) != neg]
            elif k == "distance":
                if origin is None:
                    raise AuditError("distance with no position: %s" % tok)
                c = [e for e in c if in_range(dist(e.pos, origin), val, float)]
            elif k == "scores":
                for part in split_top(val[1:-1]):
                    o, r = part.split("=")
                    self._obj(o)
                    c = [e for e in c if in_range(self.score(e, o), r)]
            elif k == "advancements":
                for part in split_top(val[1:-1]):
                    a, b = part.split("=")
                    c = [e for e in c if (a in e.advs) == (b == "true")]
            elif k == "nbt":
                want = snbt(val)
                c = [e for e in c if all(getattr(e, "nbt", {}).get(a) == b for a, b in want.items())]
            elif k == "sort":
                sort = val
            elif k == "limit":
                limit = int(val)
            elif k in ("x", "y", "z"):
                pass
            else:
                raise AuditError("selector argument the model does not read: %s in %s" % (k, tok))
        if sort == "nearest":
            c = sorted(c, key=lambda e: dist(e.pos, origin))
        return c[:limit] if limit else c

    def holders(self, tok, ent, pos):
        if tok.startswith("#"):
            return [tok]
        return self.select(tok, ent, pos)

    def _obj(self, o):
        if o not in self.objectives:
            raise AuditError("objective %s used but never created by the load function" % o)

    # -------- functions and commands
    def run_function(self, name, ent, pos, macro=None):
        if name not in self.functions:
            if not name.startswith(FN):
                self.stubbed.append((name, ent.uuid if ent else None))
                raise Return()                     # a call out of the arena: recorded, and the caller stops there
            raise AuditError("function %s is called but not emitted" % name)
        self.depth += 1
        if self.depth > 64:
            raise AuditError("function recursion past 64 at %s" % name)
        try:
            for raw in self.functions[name]:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("$"):
                    if macro is None:
                        raise AuditError("%s: a macro line run without arguments: %s" % (name, line))
                    line = re.sub(r"\$\((\w+)\)", lambda m: str(macro[m.group(1)]), line[1:])
                try:
                    if self.command(line, ent, pos)[0]:
                        return
                except Return:
                    return
        finally:
            self.depth -= 1

    def command(self, line, ent, pos):
        t = line.split(" ")
        h = t[0]
        if h == "execute":
            return self.execute(t[1:], ent, pos)
        if h == "return":
            if t[1] == "run":
                r = self.command(" ".join(t[2:]), ent, pos)
                return (True, r[1])
            return (True, int(t[1]))
        if h == "function":
            macro = None
            if len(t) > 2 and t[2] == "with":
                if t[3] != "storage":
                    raise AuditError("function with %s" % t[3])
                macro = self.storage_get(t[4], t[5] if len(t) > 5 else "")
                if not isinstance(macro, dict):
                    raise AuditError("function %s with storage %s %s: no compound there" % (t[1], t[4], t[5:]))
            elif len(t) > 2:
                macro = snbt(" ".join(t[2:]))
            self.run_function(t[1], ent, pos, macro)
            return (False, 1)
        if h == "scoreboard":
            return self.scoreboard(t, ent, pos)
        if h == "tag":
            for e in self.select(t[1], ent, pos):
                (e.tags.add if t[2] == "add" else e.tags.discard)(t[3])
            return (False, 1)
        if h in ("tellraw", "title"):
            for e in self.select(t[1], ent, pos):
                e.said.append(" ".join(t[2:]))
            return (False, 1)
        if h == "healpokemon":
            for e in self.select(t[1], ent, pos):
                e.heals += 1
            return (False, 1)
        if h == "give":
            for e in self.select(t[1], ent, pos):
                e.items.append((t[2], int(t[3])))
            return (False, 1)
        if h == "cobbledollars":
            # CobbleDollars-fabric-2.0.0+Beta-5.1+1.21.1 CobbleDollarsCommand (javap 2026-10-10): `query <player>`
            # returns getCobbleDollars(player).intValue(); `give` adds; `remove` subtracts coerceAtMost(amount,
            # balance) and so never goes below 0; give/remove take BigIntegerArgumentType.bigInt(1)
            if t[1] == "query" and len(t) == 3:
                (e,) = self.select(t[2], ent, pos)
                return (False, i32(e.bal))
            if t[1] not in ("give", "remove") or len(t) != 4:
                raise AuditError("cobbledollars %s" % " ".join(t[1:]))
            n = int(t[3])
            if n < 1:
                raise AuditError("cobbledollars %s %d: the jar refuses an amount under 1" % (t[1], n))
            for e in self.select(t[2], ent, pos):
                if t[1] == "give":
                    e.money.append(n)
                    e.bal += n
                else:
                    take = min(n, e.bal)
                    e.bal -= take
                    e.removed.append(take)
            return (False, 1)
        if h == "time":
            # vanilla 1.21.1 TimeCommand: `query gametime` answers getGameTime() % Integer.MAX_VALUE, `query daytime`
            # getDayTime() % 24000; `set` / `add` change only the day time (ServerLevel.setDayTime), never game time
            if t[1] == "query" and t[2] == "gametime":
                return (False, self.gametime % 2147483647)
            if t[1] == "query" and t[2] == "daytime":
                return (False, self.daytime % 24000)
            if t[1] in ("set", "add"):
                self.daytime = int(t[2]) if t[1] == "set" else self.daytime + int(t[2])
                return (False, 1)
            raise AuditError("time %s" % " ".join(t[1:]))
        if h == "data":
            return self.data(t, ent, pos)
        if h == "spawnnpcat":
            if not all(NUM.fullmatch(x) for x in t[1:4]):
                raise AuditError("spawnnpcat with relative coordinates: %s" % line)
            cls = t[4]
            if cls not in self.P.classes:
                return (False, 0)                 # a class the server never loaded spawns nothing
            n = Ent("cobblemon:npc", [float(x) for x in t[1:4]], cls=cls, level=int(t[5]))
            self.ents.append(n)
            self.spawns.append((ent.uuid if ent else None, cls, int(t[5]), n.pos))
            return (False, 1)
        if h == "tp":
            for e in self.select(t[1], ent, pos):
                if t[2].startswith(("~", "^")):
                    continue
                e.pos = tuple(float(x) for x in t[2:5])
            return (False, 1)
        if h == "kill":
            for e in self.select(t[1], ent, pos):
                e.alive = False
            return (False, 1)
        if h == "runmolang":
            return self.molang(line, ent, pos)
        if h == "advancement":
            return (False, 1)
        if h == "rctmod":
            # rctmod's `player get level_cap <player>`: its result is the cap; a cap that does not read is a failed
            # command, and a failed command stores 0 through `execute store result` (vanilla 1.20.3+)
            if t[1:4] != ["player", "get", "level_cap"] or len(t) != 5:
                raise AuditError("rctmod command the model does not know: %s" % line)
            (e,) = self.select(t[4], ent, pos)
            return (False, 0 if e.cap is None else int(e.cap))
        raise AuditError("a command the model does not know: %s" % line)

    def scoreboard(self, t, ent, pos):
        if t[1] == "objectives":
            if t[2] == "add":
                self.objectives.add(t[3])
            return (False, 1)
        op = t[2]
        if op == "reset":
            for hd in self.holders(t[3], ent, pos):
                for o in ([t[4]] if len(t) > 4 else list(self.scores)):
                    self.scores.get(o, {}).pop(hd.id if isinstance(hd, Ent) else hd, None)
            return (False, 1)
        obj = t[4]
        self._obj(obj)
        if op in ("set", "add", "remove"):
            for hd in self.holders(t[3], ent, pos):
                v = int(t[5])
                cur = self.score(hd, obj) or 0
                self.set_score(hd, obj, v if op == "set" else cur + v if op == "add" else cur - v)
            return (False, 1)
        if op == "get":
            (hd,) = self.holders(t[3], ent, pos)
            v = self.score(hd, obj)
            if v is None:
                # vanilla: "Can't get value of <obj> for <holder>; none is set" -- the command FAILS, and since
                # 1.20.3 a failed command stores 0 through `execute store result` (the rule the rctmod read above
                # also follows). first_t keys a player's first win at a rank this way (ar.wins not yet set -> w0)
                self.failed_gets.append((t[3], obj))
                return (False, 0)
            return (False, v)
        if op == "operation":
            o, src, sobj = t[5], t[6], t[7]
            self._obj(sobj)
            for hd in self.holders(t[3], ent, pos):
                for s in self.holders(src, ent, pos):
                    a, b = self.score(hd, obj) or 0, self.score(s, sobj) or 0
                    if o == "=":
                        a = b
                    elif o == "+=":
                        a += b
                    elif o == "-=":
                        a -= b
                    elif o == "*=":
                        a *= b
                    elif o == "/=":
                        a = a // b if b else a
                    elif o == "%=":
                        a = a % b if b else a
                    elif o == "<":
                        a = min(a, b)
                    elif o == ">":
                        a = max(a, b)
                    else:
                        raise AuditError("operation %s" % o)
                    self.set_score(hd, obj, i32(a))       # a score is a Java int: + - * wrap at 32 bits
            return (False, 1)
        raise AuditError("scoreboard players %s" % op)

    def storage_get(self, name, path):
        cur = self.storage.get(name, {})
        for p in [x for x in path.split(".") if x]:
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
        return cur

    def storage_set(self, name, path, value):
        cur = self.storage.setdefault(name, {})
        ps = path.split(".")
        for p in ps[:-1]:
            cur = cur.setdefault(p, {})
        cur[ps[-1]] = value

    def data(self, t, ent, pos):
        if t[1] == "remove" and t[2] == "storage":
            ps = t[4].split(".")
            parent = self.storage_get(t[3], ".".join(ps[:-1])) if len(ps) > 1 else self.storage.get(t[3], {})
            if isinstance(parent, dict):
                parent.pop(ps[-1], None)
            return (False, 1)
        if t[1] == "remove" and t[2] == "entity":
            return (False, 1)
        if t[1] == "modify" and t[2] == "storage" and t[5:7] == ["set", "value"]:
            self.storage_set(t[3], t[4], snbt(" ".join(t[7:])))
            return (False, 1)
        raise AuditError("data command the model does not know: %s" % " ".join(t))

    def execute(self, toks, ent, pos):
        ctxs = [(ent, pos)]
        store = None
        i = 0
        while i < len(toks):
            w = toks[i]
            if w == "run":
                cmd = " ".join(toks[i + 1:])
                res = (False, 0)
                for e, p in ctxs:
                    r = self.command(cmd, e, p)
                    if store and store[0] == "storage":
                        self.storage_set(store[1], store[2], r[1])
                    elif store:
                        self._obj(store[2])
                        for hd in self.holders(store[1], e, p):
                            self.set_score(hd, store[2], r[1])
                    if r[0]:
                        return r
                    res = r
                return res
            if w == "as":
                ctxs = [(x, p) for e, p in ctxs for x in self.select(toks[i + 1], e, p)]
                i += 2
            elif w == "at":
                ctxs = [(e, x.pos) for e, p in ctxs for x in self.select(toks[i + 1], e, p)]
                i += 2
            elif w == "positioned":
                xyz = toks[i + 1:i + 4]
                if not all(NUM.fullmatch(x) for x in xyz):
                    raise AuditError("positioned %s" % xyz)
                ctxs = [(e, tuple(float(x) for x in xyz)) for e, p in ctxs]
                i += 4
            elif w in ("if", "unless"):
                k = toks[i + 1]
                if k == "score":
                    a, ao = toks[i + 2], toks[i + 3]
                    self._obj(ao)
                    if toks[i + 4] == "matches":
                        rng = toks[i + 5]
                        test = lambda e, p, a=a, ao=ao, rng=rng: all(
                            in_range(self.score(h, ao), rng) for h in self.holders(a, e, p)) and \
                            bool(self.holders(a, e, p))
                        i += 6
                    else:
                        op, b, bo = toks[i + 4], toks[i + 5], toks[i + 6]
                        self._obj(bo)

                        def test(e, p, a=a, ao=ao, op=op, b=b, bo=bo):
                            (ha,), hb = self.holders(a, e, p), self.holders(b, e, p)
                            if len(hb) != 1:
                                return False
                            x, y = self.score(ha, ao), self.score(hb[0], bo)
                            if x is None or y is None:
                                return False
                            return {"=": x == y, "<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[op]
                        i += 7
                elif k == "entity":
                    sel = toks[i + 2]
                    test = lambda e, p, sel=sel: bool(self.select(sel, e, p))
                    i += 3
                elif k == "data" and toks[i + 2] == "storage":
                    st, path = toks[i + 3], toks[i + 4]
                    test = lambda e, p, st=st, path=path: self.storage_get(st, path) is not None
                    i += 5
                else:
                    raise AuditError("execute %s %s" % (w, k))
                ctxs = [(e, p) for e, p in ctxs if test(e, p) == (w == "if")]
            elif w == "store":
                if toks[i + 1:i + 3] == ["result", "score"]:
                    store = ("score", toks[i + 3], toks[i + 4])
                    i += 5
                    continue
                if toks[i + 1:i + 3] != ["result", "storage"] or toks[i + 5:i + 7] != ["int", "1"]:
                    raise AuditError("execute store %s" % toks[i:i + 7])
                store = ("storage", toks[i + 3], toks[i + 4])
                i += 7
            else:
                raise AuditError("execute subcommand the model does not know: %s" % w)
        return (False, len(ctxs))

    def molang(self, line, ent, pos):
        one = re.fullmatch(r'runmolang "([^"]*)" (\S+)', line)
        if one:
            return self.party_molang(one.group(1), one.group(2), ent, pos)
        m = re.fullmatch(r'runmolang "([^"]*)" (\S+) (\S+)', line)
        if not m:
            raise AuditError("runmolang the model does not read: %s" % line)
        code, ps, ns = m.groups()
        tpl = re.search(r"q\.run_command\('([^']*)' \+ q\.player\.uuid \+ '([^']*)'\)", code)
        for p in self.select(ps, ent, pos):
            for n in self.select(ns, ent, pos)[:1]:
                if re.search(r"t\.b = q\.npc\.start_battle\(q\.player, 'singles'\); \(t\.b == 0\) \?", code):
                    if self.refuse or p.in_battle or n.in_battle:
                        if tpl:
                            self.command(tpl.group(1) + p.uuid + tpl.group(2), None, None)
                    else:
                        p.in_battle = n.in_battle = True
                        p.foe = n
                elif "(q.npc.in_battle == 0 && q.player.in_battle == 0) ?" in code:
                    if not n.in_battle and not p.in_battle and tpl:
                        self.command(tpl.group(1) + p.uuid + tpl.group(2), None, None)
                else:
                    raise AuditError("molang the model does not read: %s" % code)
        return (False, 1)

    def party_molang(self, code, ps, ent, pos):
        """The one single-target shape the level-cap pack uses (party_compare): `(q.player.party.highest_level <op> N)
        ? { q.run_command(...); } : { q.run_command(...); };` -- a number compare on the party's highest level, then
        one branch's commands, each a string concatenation with q.player.uuid, run as the server."""
        m = re.fullmatch(r"\(q\.player\.party\.highest_level (>=|>|<=|<|==) (-?\d+)\) \? \{ (.*) \} : \{ (.*) \};", code)
        if not m:
            raise AuditError("molang the model does not read: %s" % code)
        op, n = m.group(1), int(m.group(2))
        for p in self.select(ps, ent, pos):
            hit = {">": p.party > n, ">=": p.party >= n, "<": p.party < n, "<=": p.party <= n, "==": p.party == n}[op]
            for expr in re.findall(r"q\.run_command\((.*?)\);", m.group(3) if hit else m.group(4)):
                self.command(self._eval(expr, {"q.player.uuid": p.uuid}), None, None)
        return (False, 1)

    # -------- the callback, read from the emitted .molang
    def _parse_callback(self):
        cbs = [t for rel, t in self.P.callbacks.items() if "/battle_victory/" in rel]
        if len(cbs) != 1:
            raise AuditError("%d battle_victory callbacks in the pack" % len(cbs))
        blocks = re.findall(r"for_each\((t\.\w+), c\.(\w+), \{\s*\1\.is_npc \? \{\s*for_each\((t\.\w+), c\.(\w+), \{"
                            r"(.*?)\}\);", cbs[0], re.S)
        if len(blocks) != 2:
            raise AuditError("the battle_victory callback has %d npc/player blocks, the model reads 2" % len(blocks))
        out = []
        for nv, ncoll, pv, pcoll, body in blocks:
            out.append((nv, ncoll, pv, pcoll, re.findall(r"q\.run_command\((.*?)\);\n", body)))
        return out

    def _eval(self, expr, env):
        s = ""
        for part in expr.split(" + "):
            part = part.strip()
            if part.startswith("'") and part.endswith("'"):
                s += part[1:-1]
            elif part in env:
                s += env[part]
            else:
                raise AuditError("callback expression the model does not read: %s" % part)
        return s

    def result(self, player, won, blackout=None, auto=0, order="before"):
        """The battle ends: Cobblemon's battle_victory event, as the emitted callback reads it. `auto` is
        CobbleDollars' own credit to the winner (CobbleDollarsEventsKt.battleVictory, subscribed to the same
        BATTLE_VICTORY at the same Priority.NORMAL as Cobblemon's CallbackHandler, so which runs first is the mods'
        init order, not fixed by either jar): `order` "before" credits it ahead of the callback, "after" behind it."""
        n = player.foe
        if won and auto and order == "before":
            player.bal += auto
        player.in_battle = n.in_battle = False
        STATS["wins" if won else "losses"] += 1
        lists = {"scriptable_losers": [n] if won else [], "player_winners": [player] if won else [],
                 "scriptable_winners": [] if won else [n], "player_losers": [] if won else [player]}
        if blackout and not won:
            self.run_blackout(player, blackout)
        for nv, ncoll, pv, pcoll, cmds in self.callback:
            for a in lists[ncoll]:
                for b in lists[pcoll]:
                    env = {nv + ".uuid": a.uuid, pv + ".player.uuid": b.uuid}
                    for c in cmds:
                        self.command(self._eval(c, env), None, None)
        if blackout and not won:
            self.run_blackout(player, blackout)
        if won and auto and order == "after":
            player.bal += auto

    def run_blackout(self, player, fname):
        try:
            self.run_function(fname, player, player.pos)
        except Return:
            pass

    def tick(self, n=1):
        for _ in range(n):
            self.gametime += 1
            self.daytime += 1
            for f in self.P.tick_tag:
                self.run_function(f, None, None)


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


# ---- flows

STATS = {"clicks": 0, "wins": 0, "losses": 0}     # how much the flows actually ran: a flow that ran nothing passes


def click(W, player, venue):
    STATS["clicks"] += 1
    adv = W.P.advancements.get("cobblers:arena/post_%s" % venue)
    if not adv or not (adv.get("rewards") or {}).get("function"):
        raise AuditError("venue %s has no post advancement with a reward function" % venue)
    W.run_function(adv["rewards"]["function"], player, player.pos)


def until(W, pred, limit=400):
    for _ in range(limit):
        if pred():
            return True
        W.tick()
    return pred()


def settle(W, player):
    """After a result: tick until the next leg's battle has started or the run is over."""
    return until(W, lambda: player.in_battle or (W.score(player, "ar.live") or 0) == 0)


def fresh(E, P, rank, advs, wins=0, venue=None, bfn=None, refuse=False, levelcap=None, cap=50, party=50):
    W = World(P, extra_functions=bfn, refuse=refuse, levelcap=levelcap)
    v = E.venues[venue]
    p = W.player(v["post"][:3], advs, cap=cap, party=party)
    if rank is not None:
        W.set_score(p, "ar.rank", rank)
        W.set_score(p, "ar.wins", wins)
    return W, p


def check_flows(E, P, bfiles, problems, lc=None):
    gym8, champ, lance = (E.flag["gym8_cleared"], E.flag["champion_cleared"],
                          E.flag["rct_defeated:kanto_league_lance"])
    bfn_name = "cobblers:blackout/battle_loss_npc"
    bfn = {bfn_name: bfiles["data/cobblers/function/blackout/battle_loss_npc.mcfunction"].splitlines()}
    lc = lc if lc is not None else levelcap_pack()
    module_fresh = fresh

    def fresh_(*a, **kw):                   # every flow's world carries the level-cap pack
        return module_fresh(*a, levelcap=lc, **kw)

    def fail(msg):
        problems.append("flow: " + msg)

    def spawned(W, before):
        return W.spawns[before:]

    def expect_spawn(W, p, before, cls, venue, what):
        s = spawned(W, before)
        if len(s) != 1:
            fail("%s: %d spawns, expected one %s" % (what, len(s), cls))
            return None
        owner, c, lvl, pos = s[0]
        if c != cls:
            fail("%s: spawned %s, expected %s" % (what, c, cls))
        if list(pos) != [float(x) for x in E.venues[venue]["opponent_spot"][:3]]:
            fail("%s: spawned at %s, venue %s's opponent_spot is %s" % (what, pos, venue, E.venues[venue]["opponent_spot"]))
        if owner != p.uuid:
            fail("%s: spawned by %s, not the challenger" % (what, owner))
        (npc,) = [e for e in W.npcs() if e.pos == pos and e.alive][-1:] or [None]
        if npc is not None and W.score(npc, "ar.id") != W.score(p, "ar.id"):
            fail("%s: the opponent's owner marker %s != the player's ar.id %s" % (what, W.score(npc, "ar.id"),
                                                                                 W.score(p, "ar.id")))
        return lvl

    # 1. every rank, every venue, every subset of the three band advancements: what a click offers
    for venue in E.venues:
        for rank in sorted(E.ranks):
            for k in range(8):
                advs = {a for i, a in enumerate((gym8, lance, champ)) if k >> i & 1}
                W, p = fresh_(E, P, rank, advs, venue=venue)
                b = len(W.spawns)
                click(W, p, venue)
                want = E.offered(venue, rank, advs)
                got = spawned(W, b)
                if want is None:
                    if got:
                        fail("rank %d %s at %s: nothing should open, spawned %s" % (rank, sorted(advs), venue, got))
                    continue
                if E.is_streak(want):
                    _L, m = E.streak_bout(0)
                    cls = "cobblers:arena_streak_m%d" % m
                elif want == rank and champ in advs and champ.split("/")[-1] in [
                        w for w in E.ranks[want]["advance"].get("wins_waived_by", [])]:
                    cls = "cobblers:arena_exam_%s" % E.exam_legs(want)[0]
                else:
                    cls = "cobblers:arena_rank_%d" % want
                expect_spawn(W, p, b, cls, venue, "rank %d %s at %s" % (rank, sorted(advs), venue))

    full = {gym8, lance, champ}

    def venue_of(n):
        return E.venues_offering(n)[0]

    # 2. a pool bout at every non-streak rank: class, level span within the band cap, heal, purse, progress
    for n in sorted(E.ranks):
        if E.is_streak(n):
            continue
        venue = venue_of(n)
        # the least a player at this rank holds, and never champion_cleared below rank 5 (it waives the pool)
        advs = {gym8} | ({lance} if n == 4 else set()) | ({champ} if n >= 5 else set())
        W, p = fresh_(E, P, n, advs, venue=venue)
        r = E.ranks[n]
        legs = E.legs(n)
        for run in range(E.need(n)):
            b, heals = len(W.spawns), p.heals
            click(W, p, venue)
            for leg in range(legs):
                lvl = expect_spawn(W, p, b, "cobblers:arena_rank_%d" % n, venue,
                                   "rank %d run %d leg %d" % (n, run, leg))
                if lvl is None:
                    return
                var = P.classes["cobblers:arena_rank_%d" % n]["party"]["pool"][0].get("levelVariation", 0)
                if lvl + var > E.cap(n) or lvl + var != r["levels"]["top"] or lvl < r["levels"]["floor"]:
                    fail("rank %d: members span %d..%d; data floor %d, top %d, band cap %d"
                         % (n, lvl, lvl + var, r["levels"]["floor"], r["levels"]["top"], E.cap(n)))
                if (p.heals - heals) != (1 if E.heal_before(n, leg) else 0):
                    fail("rank %d leg %d: %d heals, the format says %d"
                         % (n, leg, p.heals - heals, 1 if E.heal_before(n, leg) else 0))
                if not until(W, lambda: p.in_battle, 100):
                    fail("rank %d leg %d: the battle never started" % (n, leg))
                    return
                money = len(p.money)
                b, heals = len(W.spawns), p.heals
                W.result(p, True)
                last = leg == legs - 1
                want = [E.pool_leg_purse(n)] + ([E.clear_bonus(n)] if last and legs > 1 and E.clear_bonus(n) else [])
                if p.money[money:] != want:
                    fail("rank %d leg %d: paid %s, the data's purse (and clear bonus) %s" % (n, leg, p.money[money:], want))
                settle(W, p)
            if W.score(p, "ar.wins") != run + 1 or W.score(p, "ar.rank") != n:
                fail("rank %d after %d clear(s): wins %s rank %s" % (n, run + 1, W.score(p, "ar.wins"), W.score(p, "ar.rank")))
            if W.npcs():
                fail("rank %d: %d opponent(s) left standing after the run" % (n, len(W.npcs())))
            if E.bout_tag in p.tags:
                fail("rank %d: the blackout exemption tag outlives the run" % n)
        # 3. the rank-up exam it opened: each leg, its heal, its purse, the prize once, up a rank
        b, heals = len(W.spawns), p.heals
        click(W, p, venue)
        legs_t = E.exam_legs(n)
        for leg, tid in enumerate(legs_t):
            expect_spawn(W, p, b, "cobblers:arena_exam_%s" % tid, venue, "rank %d exam leg %d" % (n, leg))
            want_h = 1 if leg == 0 else (0 if E.exams[n].get("heal_between") is False else 1)
            if (p.heals - heals) != want_h:
                fail("rank %d exam leg %d: %d heals, Q3 / heal_between say %d" % (n, leg, p.heals - heals, want_h))
            if not until(W, lambda: p.in_battle, 100):
                fail("rank %d exam leg %d never started" % (n, leg))
                break
            money, items = len(p.money), len(p.items)
            b, heals = len(W.spawns), p.heals
            W.result(p, True)
            if p.money[money:] != [E.exam_leg_purse(tid)]:
                fail("rank %d exam leg %d: paid %s, %s's authored levels pay %d"
                     % (n, leg, p.money[money:], tid, E.exam_leg_purse(tid)))
            last = leg == len(legs_t) - 1
            prize = [(c["item"], c["count"]) for c in E.exam_prize(n)["contents"]] if last else []
            if p.items[items:] != prize:
                fail("rank %d exam leg %d: gave %s, the prize table says %s" % (n, leg, p.items[items:], prize))
            settle(W, p)
        if W.score(p, "ar.rank") != n + 1 or W.score(p, "ar.wins") != 0:
            fail("rank %d exam won: rank %s wins %s, expected rank %d wins 0"
                 % (n, W.score(p, "ar.rank"), W.score(p, "ar.wins"), n + 1))
        # the prize is once per player: the same rank-up run again by hand gives nothing
        W.set_score(p, "ar.rank", n)
        items = len(p.items)
        W.run_function(FN + "rank_up", p, p.pos)
        if p.items[items:]:
            fail("rank %d: a second rank-up gave the first-clear prize again: %s" % (n, p.items[items:]))

    # 4. a gauntlet lost on leg 2: the run ends, the rank is kept, no clear bonus, the blackout leaves it alone
    gl = [n for n in sorted(E.ranks) if E.legs(n) == 3]
    if not gl:
        fail("no 3-leg gauntlet in the data to run")
    else:
        n = gl[0]
        venue = venue_of(n)
        W, p = fresh_(E, P, n, full, venue=venue, bfn=bfn)
        click(W, p, venue)
        until(W, lambda: p.in_battle, 100)
        W.result(p, True, blackout=bfn_name)
        settle(W, p)
        if not p.in_battle:
            fail("rank %d: leg 2 never started after leg 1 was won" % n)
        else:
            W.result(p, False, blackout=bfn_name)
            if W.stubbed:
                fail("rank %d: an arena loss reached the blackout (%s)" % (n, W.stubbed))
            if E.bout_tag not in p.tags:
                fail("rank %d: the exemption tag is gone at the loss itself" % n)
            settle(W, p)
            if p.money != [E.pool_leg_purse(n)]:
                fail("rank %d leg-2 loss: paid %s, expected leg 1's %d and no bonus" % (n, p.money, E.pool_leg_purse(n)))
            if (W.score(p, "ar.rank"), W.score(p, "ar.wins"), W.score(p, "ar.live")) != (n, 0, 0):
                fail("rank %d leg-2 loss: rank/wins/live %s" % (n, (W.score(p, "ar.rank"), W.score(p, "ar.wins"),
                                                                    W.score(p, "ar.live"))))
            if W.npcs() or E.bout_tag in p.tags:
                fail("rank %d leg-2 loss: opponent left %d, tag held %s" % (n, len(W.npcs()), E.bout_tag in p.tags))
            # now outside a bout, the same blackout function must charge: only the tag exempts
            W.run_blackout(p, bfn_name)
            if not W.stubbed:
                fail("a loss outside a bout was exempted from the blackout too")

    # 5. two players at once: separate owner markers, a result touches its own player only
    va, vb = venue_of(1), venue_of(5)
    if va == vb:
        fail("two players: ranks 1 and 5 share venue %s, no second venue to test with" % va)
        return
    W = World(P, levelcap=lc)
    a = W.player(E.venues[va]["post"][:3], {gym8})
    b = W.player(E.venues[vb]["post"][:3], full)
    W.set_score(b, "ar.rank", 5)
    click(W, a, va)
    click(W, b, vb)
    until(W, lambda: a.in_battle and b.in_battle, 100)
    ida, idb = W.score(a, "ar.id"), W.score(b, "ar.id")
    na, nb = a.foe if a.in_battle else None, b.foe if b.in_battle else None
    if not (na and nb) or ida == idb or None in (ida, idb):
        fail("two players: battles %s/%s, ids %s/%s" % (bool(na), bool(nb), ida, idb))
    else:
        if (W.score(na, "ar.id"), W.score(nb, "ar.id")) != (ida, idb):
            fail("two players: opponents marked %s/%s, players %s/%s"
                 % (W.score(na, "ar.id"), W.score(nb, "ar.id"), ida, idb))
        # a callback pairing B with A's opponent (never a real battle) must run nothing for anyone
        snap = (list(a.money), list(b.money), W.score(a, "ar.wins"), W.score(b, "ar.leg"))
        for nv, ncoll, pv, pcoll, cmds in W.callback:
            if ncoll == "scriptable_losers":
                for c in cmds:
                    W.command(W._eval(c, {nv + ".uuid": na.uuid, pv + ".player.uuid": b.uuid}), None, None)
        if (list(a.money), list(b.money), W.score(a, "ar.wins"), W.score(b, "ar.leg")) != snap:
            fail("two players: B paired with A's opponent changed someone's state")
        b2 = len(W.spawns)
        c = W.player(E.venues[va]["post"][:3], {gym8})
        click(W, c, va)
        if len(W.spawns) != b2:
            fail("two players: a third player was given a bout at %s while A fights there" % va)
        W.result(b, True)
        settle(W, b)
        if not na.alive or not a.in_battle or a.money:
            fail("two players: B's result touched A (A's opponent alive %s, A in battle %s, A paid %s)"
                 % (na.alive, a.in_battle, a.money))

    # 6. the streak: levels, size, purse, bonus, milestones once, heals, and a loss resets it
    sn, s, _e, _mm = E.streak()
    venue = venue_of(sn)
    W, p = fresh_(E, P, sn, full, venue=venue)
    ms = {x["streak"]: x["prize"] for x in E.ranks[sn].get("milestones", [])}
    every5 = E.ranks[sn]["purse"]["every_5th_win_bonus"]
    top_ms = max(ms) if ms else 10
    ledger = Repeats(E)
    best_paid = 0                       # the longest streak whose wins were paid in full (purse_policy: streak)
    for run_len in (top_ms + 1, min(ms) + 1 if ms else 2):
        b, heals0 = len(W.spawns), p.heals
        click(W, p, venue)
        if p.heals - heals0 != 1:
            fail("streak run start: %d heals, expected 1" % (p.heals - heals0))
        for w in range(run_len):
            got = spawned(W, b)
            if len(got) != 1:
                fail("streak bout %d: %d spawns" % (w, len(got)))
                break
            _o, cls, lvl, _pos = got[0]
            L, m = E.streak_bout(w)
            var = P.classes.get(cls, {}).get("party", {}).get("pool", [{}])[0].get("levelVariation", 0)
            if cls != "cobblers:arena_streak_m%d" % m or lvl + var != L or L > E.cap(sn):
                fail("streak bout %d: %s at %d..%d, the data says %d members, ace %d (cap %d)"
                     % (w, cls, lvl, lvl + var, m, L, E.cap(sn)))
            if not until(W, lambda: p.in_battle, 100):
                fail("streak bout %d never started" % w)
                break
            money, items, heals = len(p.money), len(p.items), p.heals
            W.result(p, True)
            if w + 1 > best_paid:
                want = [E.streak_purse(w)] + ([every5] if (w + 1) % 5 == 0 else [])
                best_paid = w + 1
            else:                       # a win short of the best paid streak: a repeat, never a bonus
                want = ledger.pay(W, p)
            if p.money[money:] != want:
                fail("streak win %d: paid %s, expected %s" % (w + 1, p.money[money:], want))
            pid = ms.get(w + 1)
            want_items = ([(c["item"], c["count"]) for c in E.prizes[pid]["contents"]]
                          if pid and run_len == top_ms + 1 else [])
            if p.items[items:] != want_items:
                fail("streak win %d (run of %d): gave %s, expected %s" % (w + 1, run_len, p.items[items:], want_items))
            b = len(W.spawns)
            settle(W, p)
            if (p.heals - heals) != (1 if (w + 1) % s["heal_every"] == 0 else 0):
                fail("streak bout %d: %d heals, heal_every %d" % (w + 1, p.heals - heals, s["heal_every"]))
        W.result(p, False)
        settle(W, p)
        if W.score(p, "ar.streak") != 0 or W.score(p, "ar.best") != top_ms + 1 or W.score(p, "ar.rank") != sn:
            fail("streak lost: streak %s best %s rank %s" % (W.score(p, "ar.streak"), W.score(p, "ar.best"),
                                                              W.score(p, "ar.rank")))

    # 7. playing down: a bout below the player's own rank pays the flat repeat purse under the daily cap, never a
    # bonus, and counts nothing (purse_policy; the quarter-purse exhibition was retired, ECONOMY_OVERHAUL section 6)
    down = []
    for n in sorted(E.ranks):
        if E.is_streak(n):
            continue
        venue = venue_of(n)
        rank = max(r for r in E.ranks if E.offered(venue, r, full) == n)
        if rank - n < 1:
            continue
        down.append((n, venue, rank))
        W, p = fresh_(E, P, rank, full, venue=venue)
        ledger = Repeats(E)
        click(W, p, venue)
        for leg in range(E.legs(n)):
            until(W, lambda: p.in_battle, 100)
            money = len(p.money)
            W.result(p, True)
            paid, want = p.money[money:], ledger.pay(W, p)
            if paid != want:
                fail("playing down rank %d (player %d) leg %d: paid %s, the repeat rule pays %s"
                     % (n, rank, leg, paid, want))
            settle(W, p)
        if W.score(p, "ar.wins") != 0:
            fail("playing down rank %d counted toward rank %d's wins" % (n, rank))
    if not down:
        fail("playing down: no venue offers a rank below one a player can hold, so the repeat rule never ran")

    # 8. a refused start: the run ends, no opponent, no tag
    W, p = fresh_(E, P, 1, {gym8}, venue=venue_of(1), refuse=True)
    click(W, p, venue_of(1))
    until(W, lambda: (W.score(p, "ar.live") or 0) == 0 and not W.npcs(), 100)
    if W.npcs() or E.bout_tag in p.tags or W.score(p, "ar.live"):
        fail("a refused start left opponent %d, tag %s, live %s" % (len(W.npcs()), E.bout_tag in p.tags,
                                                                   W.score(p, "ar.live")))

    # 9. the level cap (sweep U54, review N57). An arena opponent is a cobblemon:npc, outside rctmod's own over-cap
    # refusal, so the challenge must apply rctmod's rule itself: a party whose highest level is STRICTLY over the
    # player's RCT cap is refused (canBattleAgainst's test; data/level_cap.json's "decision" for a catch), at the cap
    # is matched (every flow above runs at 50/50), and before anything spawns or heals. A refused player whose party
    # is back under is matched on the next click (no trap); a stale refusal tag refuses nobody; a cap that does not
    # read lets the challenge through (the direction a catch takes: failing closed would shut every venue).
    def cap_click(venue, rank, cap, party, tags=(), W=None, p=None):
        if W is None:
            W, p = fresh_(E, P, rank, full, venue=venue, cap=cap, party=party)
        p.tags |= set(tags)
        b, heals = len(W.spawns), p.heals
        click(W, p, venue)
        started = until(W, lambda: p.in_battle, 100)
        return W, p, bool(spawned(W, b)) and started, p.heals - heals

    for venue in E.venues:
        rank = min((r for r in E.ranks if E.offered(venue, r, full) is not None), default=None)
        if rank is None:
            continue
        W, p, ok, heals = cap_click(venue, rank, 30, 31)
        if ok or W.npcs() or heals or W.score(p, "ar.live"):
            fail("cap: a party at 31 over a cap of 30 at %s: matched %s, %d opponent(s), %d heal(s), live %s"
                 % (venue, ok, len(W.npcs()), heals, W.score(p, "ar.live")))
        shown = [W.score(p, o) for s in p.said for o in re.findall(r'"objective":"([^"]+)"', s)]
        if 30 not in shown:
            fail("cap: the refusal at %s does not show the player's cap of 30 (scores shown %s)" % (venue, shown))
        refusal_tags = set(p.tags)
        p.party = 30
        W, p, ok, _h = cap_click(venue, rank, None, None, W=W, p=p)
        if not ok:
            fail("cap: a refused player back at the cap (30/30) is still refused at %s: a trap" % venue)
        for cap in (30, None):
            W, p, ok, _h = cap_click(venue, rank, cap, 20, tags=refusal_tags)
            if not ok:
                fail("cap: a stale refusal tag %s refuses an under-cap party at %s (cap %s)"
                     % (sorted(refusal_tags), venue, cap))
        W, p, ok, _h = cap_click(venue, rank, None, 100)
        if not ok:
            fail("cap: a cap that does not read refuses the challenge at %s (it must fail open, as a catch does)"
                 % venue)

    check_clawback(E, P, fresh_, fail, down, venue_of, full, problems)
    check_daily_cap(E, P, fresh_, fail, down, full)


# ---- money: the repeat ledger, CobbleDollars' own payout, the daily clock

EDGES = []      # measured, reported, NOT failed: behaviour the design accepts as a known edge or the owner must decide


class Repeats:
    """The repeat rule as the DATA states it (prizes.purse_policy.repeat_rule): a flat repeat_purse, at most
    daily_cap_wins paid per player per period, the period being game time // day_ticks. Kept here per player, from
    the model world's clock at the moment of the win -- never from the pack's scores."""

    def __init__(self, E):
        self.E, self.seen = E, {}

    def pay(self, W, p):
        per = W.gametime // self.E.day
        was, n = self.seen.get(p.id, (per, 0))
        n = n if was == per else 0
        if not self.E.rep or n >= self.E.rep_cap:
            self.seen[p.id] = (per, n)
            return []
        self.seen[p.id] = (per, n + 1)
        return [self.E.rep]


def cd_credit(E, P, npc, extreme):
    """CobbleDollars' own credit for beating `npc` (CobbleDollarsEventsKt.battleVictory, bytecode 370-567):
    B = max(1, int(5 * S * sum(L / 50.0))) over the loser's battle team, amount = B + nextIntBetweenInclusive(B / 2,
    B * 2), credit = BigDecimal(String.valueOf(amount * multiplier)).toBigInteger(). `extreme` "max" is the largest
    the class can make it (every member at level + levelVariation, the top random draw), "min" the smallest (every
    member at the spawn level, the bottom draw). From the CLASS FILE and the jar's formula, not the generator."""
    party = P.classes[npc.cls]["party"]
    if party["type"] == "pool":
        var = party["pool"][0].get("levelVariation", 0)
        lv = [npc.level + (var if extreme == "max" else 0)] * int(party["maxPokemon"])
    else:
        lv = [int(re.search(r"level=(\d+)", m).group(1)) for m in party["pokemon"]]
    b = max(1, int(5 * sum(lv) * sum(x / 50.0 for x in lv)))
    amount = b + (b * 2 if extreme == "max" else b // 2)
    from decimal import Decimal
    return int(Decimal(repr(amount * float(E.cd_mult))))


def least_advs(E, n):
    """The least a player at rank n holds, never champion_cleared below rank 5 (it waives the pool): flow 2's rule."""
    return ({E.flag["gym8_cleared"]} | ({E.flag["rct_defeated:kanto_league_lance"]} if n == 4 else set())
            | ({E.flag["champion_cleared"]} if n >= 5 else set()))


def check_clawback(E, P, fresh_, fail, down, venue_of, full, problems):
    """10. CobbleDollars pays every NPC win by itself; on an arena win the pack takes that back (kept_cap 0), whichever
    handler runs first, and pays only its own purse: the balance moves by exactly what the arena gave. Walked for a
    first win (rank 1), a gauntlet's chained legs, and a repeat (playing down), at both extremes of the credit."""
    if not E.cd_npc:
        return
    if E.kept_cap != 0:
        fail("clawback: purse_policy.cobbledollars_auto_payout.kept_cap is %r, the design's is 0" % E.kept_cap)
    gaunt = min((n for n in E.ranks if not E.is_streak(n) and E.legs(n) > 1), default=None)
    cases = [("first win, rank 1", 1, venue_of(1), 1, least_advs(E, 1))]
    if gaunt is not None:
        cases.append(("gauntlet rank %d" % gaunt, gaunt, venue_of(gaunt), gaunt, least_advs(E, gaunt)))
    if down:
        n, venue, rank = down[0]
        cases.append(("repeat, rank %d played at rank %d" % (n, rank), n, venue, rank, full))
    for what, n, venue, rank, advs in cases:
        for order in ("before", "after"):
            for extreme in ("max", "min"):
                W, p = fresh_(E, P, rank, advs, venue=venue)
                p.bal = 50000
                click(W, p, venue)
                for leg in range(E.legs(n)):
                    if not until(W, lambda: p.in_battle, 100):
                        fail("clawback %s leg %d: the bout never started" % (what, leg))
                        break
                    credit = cd_credit(E, P, p.foe, extreme)
                    bal, money, removed = p.bal, len(p.money), len(p.removed)
                    W.result(p, True, auto=credit, order=order)
                    settle(W, p)
                    gave, took = sum(p.money[money:]), sum(p.removed[removed:])
                    if p.bal - bal != gave or took != credit:
                        fail("clawback %s leg %d (CobbleDollars %s the callback, credit %d at its %s): balance moved "
                             "%+d, the arena gave %d; took back %d of CobbleDollars' %d"
                             % (what, leg, order, credit, extreme, p.bal - bal, gave, took, credit))
                if W.score(p, "ar.live"):
                    W.result(p, False)
                    settle(W, p)
    # never more than CobbleDollars could have paid: a large transfer from another source lands in the same window,
    # and what is taken may not exceed the jar's own maximum for that opponent (purse_policy's mechanism: "never more
    # than the most CobbleDollars could credit"). The maximum is cd_credit's, from the class and the jar, exact
    for order in ("before", "after"):
        W, p = fresh_(E, P, 1, least_advs(E, 1), venue=venue_of(1))
        p.bal = 50000
        click(W, p, venue_of(1))
        until(W, lambda: p.in_battle, 100)
        top = cd_credit(E, P, p.foe, "max")
        p.bal += 100000
        W.result(p, True, auto=top, order=order)
        settle(W, p)
        if sum(p.removed) > top:
            over = sum(p.removed) - top
            msg = ("clawback (CobbleDollars %s the callback): took %d, more than CobbleDollars could pay for that "
                   "opponent (%d, the jar's maximum)" % (order, sum(p.removed), top))
            if "claw_margin" in KNOWN and over <= 3:
                problems.append("KNOWN claw_margin: " + msg)
            else:
                fail(msg)

    # the first purse once: a gauntlet at the player's own rank lost after leg 1, then run again -- leg 1 is now a
    # repeat (the flat purse), leg 2 still a first (its full purse)
    if gaunt is not None:
        W, p = fresh_(E, P, gaunt, least_advs(E, gaunt), venue=venue_of(gaunt))
        ledger = Repeats(E)
        click(W, p, venue_of(gaunt))
        until(W, lambda: p.in_battle, 100)
        m0 = len(p.money)
        W.result(p, True)
        settle(W, p)
        W.result(p, False)
        settle(W, p)
        first = p.money[m0:]
        click(W, p, venue_of(gaunt))
        paid = []
        for leg in range(2):
            until(W, lambda: p.in_battle, 100)
            m = len(p.money)
            W.result(p, True)
            paid.append(p.money[m:])
            settle(W, p)
        last = E.legs(gaunt) == 2 and E.clear_bonus(gaunt)          # leg 2 ends the run: the first clear's bonus
        want = [ledger.pay(W, p), [E.pool_leg_purse(gaunt)] + ([E.clear_bonus(gaunt)] if last else [])]
        if first != [E.pool_leg_purse(gaunt)] or paid != want:
            fail("first purse once: rank %d leg 1 paid %s, then on a second run legs 1-2 paid %s; the policy %s then %s"
                 % (gaunt, first, paid, [E.pool_leg_purse(gaunt)], want))

    # a loss: CobbleDollars pays a loser nothing and the arena takes nothing
    W, p = fresh_(E, P, 1, least_advs(E, 1), venue=venue_of(1))
    p.bal = 50000
    click(W, p, venue_of(1))
    until(W, lambda: p.in_battle, 100)
    W.result(p, False)
    settle(W, p)
    if p.bal != 50000 or p.removed:
        fail("clawback: a LOSS moved the balance to %d (took %s)" % (p.bal, p.removed))

    # the edges: money from or to ANOTHER source while a clawback window is open. Measured and reported, not failed
    # (prizes.purse_policy.cobbledollars_auto_payout.known_edges names the first two; the owner decides)
    def walk(order, mid=0, post=0):
        W, p = fresh_(E, P, 1, least_advs(E, 1), venue=venue_of(1))
        p.bal = 50000
        click(W, p, venue_of(1))
        until(W, lambda: p.in_battle, 100)
        credit = cd_credit(E, P, p.foe, "min")
        p.bal += mid                    # a teammate's `cobbledollars pay` (+) or the player's own pay out (-)
        bal0, money = p.bal - mid, len(p.money)
        W.result(p, True, auto=credit, order=order)
        p.bal += post                   # the same inside the 2 s after the win, before the clear-up's second look
        settle(W, p)
        return p.bal - bal0 - sum(p.money[money:]) - mid - post, credit
    for order in ("before", "after"):
        kept, credit = walk(order, mid=1000)
        if kept < 0:
            EDGES.append("clawback (CobbleDollars %s the callback): a 1000 transfer TO the player during the battle "
                         "loses %d of the player's own money" % (order, -kept))
        kept, credit = walk(order, post=1000)
        if kept < 0:
            EDGES.append("clawback (CobbleDollars %s the callback): a 1000 transfer TO the player in the 2 s after the "
                         "win loses %d of the player's own money" % (order, -kept))
        for when in ("mid", "post"):
            kept, credit = walk(order, **{when: -credit})
            if kept > 0:
                EDGES.append("clawback (CobbleDollars %s the callback): the player paying %d away %s keeps %d of "
                             "CobbleDollars' %d credit (a partner can pay it back; repeat wins are not capped by this)"
                             % (order, credit, "during the battle" if when == "mid" else "in the 2 s after the win",
                                kept, credit))


def check_daily_cap(E, P, fresh_, fail, down, full):
    """11. The repeat cap's clock is GAME time (`time query gametime`, which only ticking advances): daily_cap_wins
    paid repeats a period, none after; `time set` / `time add` (day time only) never reset it; the next period does."""
    if not down or not E.rep or not E.rep_cap:
        return
    n, venue, rank = min(down, key=lambda d: E.legs(d[0]))
    W, p = fresh_(E, P, rank, full, venue=venue)

    def win():
        click(W, p, venue)
        until(W, lambda: p.in_battle, 100)
        money = len(p.money)
        W.result(p, True)
        settle(W, p)
        if W.score(p, "ar.live"):           # a gauntlet leg: end the run so the next click starts a new one
            W.result(p, False)
            settle(W, p)
        return sum(p.money[money:])
    W.gametime = E.day * 7 + 1              # inside one period, far from its end
    paid = [win() for _ in range(E.rep_cap + 1)]
    if paid != [E.rep] * E.rep_cap + [0]:
        fail("daily cap: %d repeats in one period paid %s, the policy %s" % (len(paid), paid,
                                                                          [E.rep] * E.rep_cap + [0]))
    W.command("time set 0", None, None)
    W.command("time add 24000", None, None)
    if win() != 0:
        fail("daily cap: `time set` / `time add` reset the repeat cap (it must follow game time)")
    W.gametime = E.day * 8 + 1
    if win() != E.rep:
        fail("daily cap: the next period (game time %d) pays no repeat" % W.gametime)


# ===================================================================================================== the report

def audit(pack_dir=PACK, dome_path=DOME, blackout_pack_dir=None, route=True, levelcap_pack_dir=None):
    problems = []
    for k in STATS:
        STATS[k] = 0
    del EDGES[:]
    E = Expect(dome_path)
    check_data(E, problems)
    P = Pack(pack_dir)
    check_classes(E, P, problems)
    check_static(E, P, problems)
    bfiles = blackout_files(blackout_pack_dir)
    check_blackout(E, bfiles, problems)
    if route:
        check_route_trainers(E, problems)
    try:
        check_flows(E, P, bfiles, problems, levelcap_pack(levelcap_pack_dir))
    except AuditError as e:
        problems.append("model: %s" % e)
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--dome", default=str(DOME))
    ap.add_argument("--blackout-pack", default=None, help="a built cobblers_blackout (default: emitted in memory)")
    ap.add_argument("--levelcap-pack", default=None, help="a built cobblers_levelcap (default: emitted in memory)")
    a = ap.parse_args(argv)
    try:
        problems = audit(Path(a.pack), Path(a.dome), a.blackout_pack, levelcap_pack_dir=a.levelcap_pack)
    except AuditError as e:
        print("arena_runtime_audit: FAIL -- %s" % e)
        return 1
    for pr in problems:
        print("  PROBLEM %s" % pr)
    for ed in EDGES:
        print("  EDGE %s" % ed)
    print("  ran: %(clicks)d post clicks, %(wins)d won and %(losses)d lost battles in the command model" % STATS)
    known = sum(1 for pr in problems if pr.startswith("KNOWN"))
    if problems:
        print("arena_runtime_audit: FAIL -- %d problem(s), %d of them KNOWN and reported (%s)"
              % (len(problems), known, "; ".join(sorted(KNOWN))))
        return 1
    print("arena_runtime_audit: ok -- classes, venues, posts, ladder, purses, prizes, gauntlets, streak, two players, "
          "blackout exemption, the level-cap refusal and the retired champions, all against the data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
