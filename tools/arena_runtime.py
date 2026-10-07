#!/usr/bin/env python
"""Heaven's Arena's runtime: per-player opponents spawned in front of the challenger, as build/datapacks/cobblers_arena.

The owner, 2026-10-03: "a battle zone where a player can go in and always find a cool battle or gauntlet ... early
levels single battles then more back to back ... each player will have their own progress and their opponent will be
spawned in front of them."

Inputs, all data:
  data/arena_fights.json    the ladder: nine ranks, formats, bands, set_pool, rank_up_fights, prizes
  data/arena_trainers.json  the seven champions' teams (the rank-up exams); unseated since 2026-10-03
  data/arena_dome.json      the venues: `venues[]` with `id`, `ranks`, `challenger_mark` [x,y,z,yaw],
                            `opponent_spot` [x,y,z,yaw], `post` [x,y,z] (written by the dome's own builder;
                            --dome points elsewhere, which the tests do with tests/fixtures/arena_dome.json)
  data/blackout.json        arena_exempt.player_tag: the tag the blackout pack reads to leave an arena loss alone
  data/league_trainers.json which upstream advancement records "Lance beaten" (band champion_door)

THE MECHANISM (rung 1, Cobblemon native, docs/research/notes/arena-per-player-opponents.md section 8, run in game
2026-10-03): a cobblemon:npc class whose `pool` party has "isStatic": false re-rolls its team at every challenge;
`spawnnpcat X Y Z <class> <level>` with ABSOLUTE coordinates spawns it (the relative form spawned nothing, and the
command prints nothing, so the NPC is found by position and tagged); `runmolang "q.npc.start_battle(q.player,
'singles');" <player> <npc>` opens the battle with no click and returns 0 when refused; a battle_victory callback
reads the result. Classes load only at server start (EXP-022), so a change here needs a RESTART, never a /reload.

What the pack writes:
  npcs        cobblers:arena_rank_<1-8>   pool bouts: `members` drawn from set_pool (min_rank <= rank), each a
                                          properties string (species, moves, ability, held_item, nature); spawned
                                          at level top-(members-1) with levelVariation members-1, so every member
                                          is between that and the rank's top and NEVER above it (the band's cap)
              cobblers:arena_streak_m<3-6> rank 9's endless streak, one class per team size (the size rises with
                                          the streak; the level is the spawn level)
              cobblers:arena_exam_<id>    a champion's authored team, `simple`, levels as authored
  functions   cobblers:arena/...          posts, challenge, bout start/begin, won/lost, timers, sweep
  callback    data/cobblemon/callbacks/battle_victory/cobblers_arena.molang
  advancement cobblers:arena/post_<venue> a click on a venue's post runs its challenge AS THE CLICKING PLAYER
              cobblers:arena/npc_click    a click on any arena opponent: tells a non-owner it is not theirs

STATE (all per player, scoreboard; nothing server-wide but the id counter and the sweep clock):
  ar.id     the player's arena id (from #next ar.id). The same score on an NPC is its OWNER: names and UUIDs are
            never written into a file, and an NPC is matched to its player by `if score @s ar.id = #me ar.id`
  ar.rank   rank held, 1..9 (unset reads as 1);  ar.wins  wins (or gauntlet clears) at that rank
  ar.cur    the rank of the bout in progress;    ar.kind  1 pool bout, 2 rank-up exam, 3 streak
  ar.leg    legs won in the current run;          ar.streak / ar.best  rank 9's current and best streak
  ar.venue  the venue index of the run;           ar.exh   1 when the bout is two or more ranks below the player's
  ar.live   1 while the player has a bout or run in progress (tag cobblers.arena_bout is held with it)
  ar.go / ar.end  per-player countdowns: battle start after the spawn, and clear-up after a result
  ar.next   1 when the clear-up should spawn the next leg;  ar.idle  sweeps that found the bout not in battle
  ar.left   minecraft.custom:minecraft.leave_game: a player who left mid-run loses the run when they return

MULTIPLAYER. One opponent per player, owned by score; a venue holds one live run at a time (a second player is told
it is in use); battles are built for the one named player. A player who leaves the venue between legs, logs out,
flees or forfeits loses the RUN (never the rank); the opponent is cleared by the result, by `arena/abandon`, or by the
sweep (an arena NPC with no live owner within 48 blocks is killed while its chunk is loaded). An NPC that unloaded
with its chunk is killed by the sweep the next time anyone loads it.

NOT COVERED here, on purpose: the legality of every set against the jar (mechanism_needs N11), the draw constraints
a pool provider cannot express (see draw_dropped() and data/arena_fights.json decisions_pending), and battle rules
(start_battle with no rules argument runs an empty rule set, so `maxItemUses: 0` is NOT applied). Nothing here was
run in a server; see the report and tests/test_arena_runtime_build.py for what is checked offline.
"""
import argparse
import itertools
import json
import math
import re
import shutil
from pathlib import Path

import levelcap_pack as LC  # the NPC-battle level-cap check (battle_check) and its tag

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "build" / "datapacks" / "cobblers_arena"
DOME = DATA / "arena_dome.json"
NS = "cobblers"
F = "%s:arena" % NS                       # function prefix

ARENA_TAG = "cobblers_arena"              # every arena opponent
DONE_TAG = "cobblers_arena_done"          # its result has been seen
PICK = "cobblers.arena_pick"              # transient: the one NPC a command is about to act on
ME = "cobblers.arena_me"                  # transient: the player an NPC is turned to face
POST = "cobblers_arena_post"
STORE = "%s:arena" % NS
NPC = "@e[type=cobblemon:npc,tag=%s]" % ARENA_TAG


def npc(extra):
    """The arena-opponent selector with more arguments inside the same brackets."""
    return "@e[type=cobblemon:npc,tag=%s,%s]" % (ARENA_TAG, extra)
GO_TICKS = 10                             # spawn, then start the battle half a second later
END_TICKS = 40                            # the result, then clear the opponent two seconds later
SWEEP_TICKS = 20
OWNER_RANGE = 48                          # an opponent with no live owner this near is an orphan
VENUE_RANGE = 24                          # a player farther than this from the challenger mark has left the venue
IDLE_SWEEPS = 2                           # sweeps out of battle before a live bout counts as abandoned
# Cobblemon's NPC `skill` (0-5, battler_test.json uses 5): rising with the ladder. A default, not designed data.
SKILL = {1: 3, 2: 3, 3: 4, 4: 4, 5: 5, 6: 5, 7: 5, 8: 5, 9: 5}
EXAM_SKILL = 5
SLUG = re.compile(r"[a-z0-9_]+")
OBJECTIVES = ["ar.id", "ar.rank", "ar.wins", "ar.cur", "ar.kind", "ar.leg", "ar.streak", "ar.best", "ar.venue",
              "ar.exh", "ar.live", "ar.go", "ar.end", "ar.next", "ar.idle", "ar.t"]


class ArenaError(SystemExit):
    pass


def doc(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def text(s, color="gold", italic=False):
    d = {"text": s, "color": color}
    if italic:
        d["italic"] = True
    return json.dumps(d)


def say(s, color="gold"):
    return "tellraw @s %s" % text(s, color)


# ------------------------------------------------------------------ the ladder, read from data

def purse_rule(fights):
    """(round_to, coefficient) from prizes.purse_formula's own words ("nearest 50 of 13 x ...")."""
    m = re.search(r"nearest (\d+) of (\d+) x", fights["prizes"]["purse_formula"])
    if not m:
        raise ArenaError("data/arena_fights.json prizes.purse_formula no longer reads 'nearest N of K x': "
                         "the purse cannot be derived")
    return int(m.group(1)), int(m.group(2))


def purse(levels, rule):
    """To the nearest `step`, an exact half rounding DOWN: the designer's figures do (rank 8's leg is 13 x 225 = 2925,
    typed as 2900, and its 'about 22,000' clear is 5 x 2900 + 7500). The streak's scoreboard arithmetic uses the
    same half (#half = step/2 - 1)."""
    step, k = rule
    return (k * sum(levels) + step // 2 - 1) // step * step


def drawn_levels(members, top):
    """The draw's levels: the ace at `top`, each earlier member one lower (data/arena_fights.json draw.levels)."""
    return [top - (members - 1 - i) for i in range(members)]


def advancement_terms(requires, league):
    """A band's `requires` as OR-of-AND advancement sets: [[adv, ...], ...]; every token must be known."""
    lance = next((e for e in league if e.get("upstream_trainer_id") == "kanto_league_lance"), None)

    def one(tok):
        tok = tok.strip()
        if tok in ("gym8_cleared", "champion_cleared") or re.fullmatch(r"gym\d_cleared", tok):
            return "%s:flag/%s" % (NS, tok)
        if tok == "rct_defeated:kanto_league_lance" and lance is not None:
            # the upstream advancement the League's own elevator requires (data/league_trainers.json
            # order_enforced_by); route_trainers derives the same name for its hold-off
            return lance.get("beaten_advancement") or "cobbleverse:trainer/kanto/defeat_elite_lance"
        raise ArenaError("data/arena_fights.json band requirement %r maps to no known advancement" % tok)
    alts = [[one(t) for t in req.split(" OR ")] for req in requires]
    return [sorted(set(c)) for c in itertools.product(*alts)]


def adv_selector(advs):
    return "@s[advancements={%s}]" % ",".join("%s=true" % a for a in advs)


def ladder(fights, trainers, league):
    """{rank: dict} with everything the functions need, derived from data/arena_fights.json only."""
    rule = purse_rule(fights)
    bands = {b["id"]: b for b in fights["bands"]}
    champs = {t["id"]: t for t in trainers}
    exams = {e["rank"]: e for e in fights["rank_up_fights"]}
    prizes = {p["id"]: p for p in fights["prizes"]["items"]}
    out = {}
    for r in fights["ranks"]:
        n = r["rank"]
        band = bands[r["band"]]
        e = {"rank": n, "name": r["name"], "format": r["format"], "band": band["id"],
             "terms": advancement_terms(band.get("requires", []), league),
             "title": fights["identities"]["titles_by_rank"][str(n)]}
        if r["format"] == "streak":
            s = r["streak"]
            m = re.fullmatch(r"members \+1 every (\d+) wins, to (\d+)", s["at_level_max"])
            if not m:
                raise ArenaError("rank %d streak.at_level_max %r is not 'members +1 every N wins, to M'"
                                 % (n, s["at_level_max"]))
            steps = -(-(s["level_max"] - s["level_start"]) // s["level_step"])
            e.update(streak=dict(s, members_every=int(m.group(1)), members_max=int(m.group(2)),
                                 full_at=steps * s["level_step_every_wins"],
                                 bonus=r["purse"]["every_5th_win_bonus"]),
                     milestones=[(x["streak"], x["prize"]) for x in r.get("milestones", [])])
        else:
            members, top = r["members"], r["levels"]["top"]
            legs = r.get("legs", 1) if r["format"] == "gauntlet" else 1
            p = purse(drawn_levels(members, top), rule)
            adv = r["advance"]
            ex = exams[n]
            leg_ids = ex["legs"] if "legs" in ex else [ex["trainer"]]
            for t in leg_ids:
                if t not in champs:
                    raise ArenaError("rank %d's exam names %s, which data/arena_trainers.json does not have" % (n, t))
            e.update(members=members, top=top, floor=r["levels"]["floor"], legs=legs,
                     heal_before_leg=r.get("intermission_after_leg"),
                     need=adv.get("wins_at_rank", adv.get("clears_at_rank")),
                     waived=["%s:flag/%s" % (NS, w) for w in adv.get("wins_waived_by", [])],
                     purse=p, exhibition=(p // 4 + rule[0] // 2 - 1) // rule[0] * rule[0],
                     clear_bonus=r["purse"].get("clear_bonus", 0),
                     exam=[(t, purse([m["level"] for m in champs[t]["team"]], rule)) for t in leg_ids],
                     prize=r.get("first_clear_prize"))
            if e["top"] > band["cap"]:
                raise ArenaError("rank %d tops out at %d, over its band's cap %d" % (n, e["top"], band["cap"]))
        out[n] = e
    for e in out.values():
        for pid in [e.get("prize")] + [p for _s, p in e.get("milestones", [])]:
            if pid and pid not in prizes:
                raise ArenaError("rank %d names prize %s, which prizes.items does not have" % (e["rank"], pid))
    return out, prizes


def draw_dropped(fights):
    """The draw constraints a Cobblemon pool party cannot express, quoted from the data so the list cannot drift."""
    keep = ("no species twice in one opponent",)       # selectableTimes 1 is the pool's own default
    return [c for c in fights["draw"]["constraints"] if not c.startswith(keep)]


# ------------------------------------------------------------------ the NPC classes

def held(item):
    return item if ":" in item else "cobblemon:%s" % item


def properties(member, level=None):
    """A Cobblemon properties string. Keys read from the 1.8.0 jar's PokemonProperties parser (`moves` split on ",",
    `held_item`, `ability`, `nature`, `level`); `held_item=` is proven in game (EXP-041)."""
    for k in ("species", "moveset"):
        if not member.get(k):
            raise ArenaError("a set member has no %s: %s" % (k, member))
    if "mega_showdown" in (member.get("heldItem") or ""):
        raise ArenaError("%s holds %s: no Megas in arena sets (decisions_pending)" % (member["species"], member["heldItem"]))
    for v in [member["species"]] + [member[k] for k in ("ability", "nature") if member.get(k)] + list(member["moveset"]):
        if not SLUG.fullmatch(v):
            raise ArenaError("%r is not a plain lowercase id" % v)
    # an absent ability, item or nature is left to Cobblemon (the species' own ability; one champion member,
    # Marro's Ferrothorn, is authored with no ability)
    parts = [member["species"]] + (["level=%d" % level] if level is not None else []) + [
        "moves=%s" % ",".join(member["moveset"])]
    parts += ["ability=%s" % member["ability"]] if member.get("ability") else []
    parts += ["held_item=%s" % held(member["heldItem"])] if member.get("heldItem") else []
    parts += ["nature=%s" % member["nature"]] if member.get("nature") else []
    return " ".join(parts)


def npc_class(names, skill, party):
    # every field below is one docs/research/notes/arena-per-player-opponents.md section 1 lists from NPCClass.kt
    # @1.8.0, and the shape of the probe class that passed in game on 2026-10-03
    return {"hitbox": "player", "names": names, "canDespawn": False, "isInvulnerable": True, "isMovable": False,
            "isLeashable": False, "allowProjectileHits": False, "autoHealParty": True,
            "battleConfiguration": {"canChallenge": False}, "skill": skill,
            "ai": [{"type": "apply_behaviours", "presets": ["cobblemon:battler", "cobblemon:looks_at_players"]}],
            "party": party}


def pool_party(sets, members):
    return {"type": "pool", "minPokemon": str(members), "maxPokemon": str(members), "isStatic": False,
            "pool": [{"pokemon": properties(s["member"]), "levelVariation": members - 1} for s in sets]}


def classes(fights, lad, champs):
    names = fights["identities"]["names"]
    sets = fights["set_pool"]["sets"]
    out = {}
    for n, e in sorted(lad.items()):
        title = e["title"]
        open_sets = [s for s in sets if s["min_rank"] <= n]
        if e["format"] == "streak":
            st = e["streak"]
            for m in range(st["members_start"], st["members_max"] + 1):
                if len(open_sets) < m:
                    raise ArenaError("rank %d needs %d sets, the pool has %d" % (n, m, len(open_sets)))
                out["arena_streak_m%d" % m] = npc_class(["%s %s" % (title, x) for x in names], SKILL[n],
                                                        pool_party(open_sets, m))
            continue
        if len(open_sets) < e["members"]:
            raise ArenaError("rank %d needs %d sets, the pool has %d" % (n, e["members"], len(open_sets)))
        out["arena_rank_%d" % n] = npc_class(["%s %s" % (title, x) for x in names], SKILL[n],
                                             pool_party(open_sets, e["members"]))
    for tid, t in sorted(champs.items()):
        out["arena_exam_%s" % tid] = npc_class([t["display_name"]], EXAM_SKILL, {
            "type": "simple", "pokemon": [properties(m, m["level"]) for m in t["team"]]})
    return out


# ------------------------------------------------------------------ venues

def venues(dome):
    vs = dome.get("venues") or []
    if not vs:
        raise ArenaError("the dome has no venues[]: nowhere to fight")
    seen = set()
    for v in vs:
        if not SLUG.fullmatch(v.get("id", "")) or v["id"] in seen:
            raise ArenaError("venue id %r is not a unique lowercase slug" % v.get("id"))
        seen.add(v["id"])
        for k, n in (("challenger_mark", 4), ("opponent_spot", 4), ("post", 3)):
            if len(v.get(k) or []) != n:
                raise ArenaError("venue %s: %s must have %d numbers" % (v["id"], k, n))
        if not v.get("ranks") or any(r not in range(1, 10) for r in v["ranks"]):
            raise ArenaError("venue %s: ranks must be within 1..9" % v["id"])
    return vs


def snbt_string(s):
    """A double-quoted SNBT string (a text component's JSON inside an entity's NBT)."""
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def fmt(v):
    return ("%d" % v) if float(v).is_integer() else ("%s" % v)


# ------------------------------------------------------------------ the pack

def files(dome_path=DOME):
    fights = doc(DATA / "arena_fights.json")
    trainers = doc(DATA / "arena_trainers.json")["trainers"]
    league = doc(DATA / "league_trainers.json")["trainers"]
    bout_tag = doc(DATA / "blackout.json")["arena_exempt"]["player_tag"]
    if not Path(dome_path).is_file():
        raise ArenaError("%s does not exist: the venues come from the dome's builder (arena_dome.json venues[])"
                         % dome_path)
    vs = venues(doc(dome_path))
    lad, prizes = ladder(fights, trainers, league)
    covered = {r for v in vs for r in v["ranks"]}
    if set(lad) - covered:
        raise ArenaError("no venue offers rank(s) %s: a player there could never fight at their own rank"
                         % sorted(set(lad) - covered))
    champs = {t["id"]: t for t in trainers}
    used = {t for e in lad.values() for t, _p in e.get("exam", [])}
    champs = {k: v for k, v in champs.items() if k in used}
    rule = purse_rule(fights)

    out = {"pack.mcmeta": {"pack": {"pack_format": 48, "description":
                                    "Cobblers: Heaven's Arena per-player opponents (tools/arena_runtime.py)"}}}
    for cid, c in classes(fights, lad, champs).items():
        out["data/%s/npcs/%s.json" % (NS, cid)] = c
    fn = {}

    def F_(name):
        return "%s/%s" % (F, name)

    # ---- load and tick
    fn["load"] = (["scoreboard objectives add %s dummy" % o for o in OBJECTIVES]
                  + ["scoreboard objectives add ar.left minecraft.custom:minecraft.leave_game",
                     "scoreboard players add #next ar.id 0",
                     "scoreboard players set #c13 ar.t %d" % rule[1],
                     "scoreboard players set #c50 ar.t %d" % rule[0],
                     "scoreboard players set #half ar.t %d" % (rule[0] // 2 - 1),
                     "scoreboard players set #c2 ar.t 2",
                     "scoreboard players set #c5 ar.t 5"])
    fn["tick"] = [
        "execute as @a[scores={ar.left=1..}] run function %s" % F_("rejoined"),
        "execute as @a[scores={ar.go=1..}] run function %s" % F_("go_tick"),
        "execute as @a[scores={ar.end=1..}] run function %s" % F_("end_tick"),
        "scoreboard players add #clock ar.t 1",
        "execute if score #clock ar.t matches %d.. run function %s" % (SWEEP_TICKS, F_("sweep"))]
    fn["go_tick"] = ["scoreboard players remove @s ar.go 1",
                     "execute if score @s ar.go matches 0 run function %s" % F_("bout/begin")]
    fn["end_tick"] = ["scoreboard players remove @s ar.end 1",
                      "execute if score @s ar.end matches 0 run function %s" % F_("after")]
    fn["new_id"] = ["scoreboard players add #next ar.id 1", "scoreboard players operation @s ar.id = #next ar.id"]
    fn["mine"] = [
        "# as a player: #me is their arena id, and their own opponent(s) carry the same ar.id",
        "scoreboard players operation #me ar.id = @s ar.id"]
    fn["end_run"] = [
        "# as a player: no bout, no run. The blackout exemption tag goes with it",
        "scoreboard players set @s ar.live 0", "scoreboard players set @s ar.leg 0",
        "scoreboard players set @s ar.next 0", "scoreboard players set @s ar.go 0",
        "scoreboard players set @s ar.idle 0", "tag @s remove %s" % bout_tag]
    fn["kill_mine"] = ["function %s" % F_("mine"),
                       "execute as %s if score @s ar.id = #me ar.id run kill @s" % NPC]
    fn["lose_run"] = [
        "# as a player whose run ended without a result: the run (and a streak) is lost, the rank never is",
        "function %s" % F_("kill_mine"), "scoreboard players set @s ar.streak 0", "scoreboard players set @s ar.end 0",
        "function %s" % F_("end_run")]
    fn["rejoined"] = [
        "scoreboard players reset @s ar.left",
        "execute unless score @s ar.live matches 1 run return 0",
        say("You left Heaven's Arena mid-run: that run is over. Your rank is kept.", "gray"),
        "function %s" % F_("lose_run")]

    # ---- posts (R17A runs place, inside a forceload of every venue)
    place = ["# every venue's post: an interaction box a player clicks (advancement %s/post_<venue>) and a label" % F,
             "kill @e[type=minecraft:interaction,tag=%s]" % POST,
             "kill @e[type=minecraft:text_display,tag=%s]" % POST]
    for i, v in enumerate(vs, 1):
        px, py, pz = v["post"]
        rs = sorted(v["ranks"])
        label = v.get("label") or ("Ranks %d-%d" % (rs[0], rs[-1]) if len(rs) > 1 else "Rank %d" % rs[0])
        # a post is a block CENTRE in data/arena_dome.json (n + 0.5) or a block corner in older fixtures: the
        # summon goes to the centre of the block it names either way (qa audit b5e570a: "%s.5" of 3567.5 wrote 3567.5.5)
        cx, cz = "%g" % (math.floor(px) + 0.5), "%g" % (math.floor(pz) + 0.5)
        place += ['summon minecraft:interaction %s %s %s {width:1.0f,height:2.0f,response:1b,Tags:["%s","%s_%s"]}'
                  % (cx, fmt(py), cz, POST, POST, v["id"]),
                  "summon minecraft:text_display %s %s %s {Tags:[\"%s\"],billboard:\"center\",text:%s}"
                  % (cx, fmt(py + 2.4), cz, POST,
                     snbt_string(json.dumps({"text": "Heaven's Arena - %s - click to challenge" % label,
                                             "color": "gold"})))]
    fn["posts/place"] = place
    # the champions who stood in the spire until 2026-10-03 (summon_persistent by R17): killed where they stood, so a
    # world that had them loses them. Their rctmod data is no longer emitted, so they would stand there inert
    retire = ["# the seven spire champions R17 used to summon (data/arena_trainers.json superseded_seat): the owner, "
              "2026-10-03, 'have the middle just be hubs'"]
    for t in trainers:
        old = t.get("superseded_seat")
        if t.get("seated") is False and old:
            x, y, z = old["seat"]
            retire.append('kill @e[type=rctmod:trainer,x=%d.5,y=%d,z=%d.5,distance=..24,nbt={TrainerId:"%s"}]'
                          % (x, y, z, t["id"]))
    fn["retire_spire"] = retire

    # ---- the click on a post, and on an opponent
    for i, v in enumerate(vs, 1):
        tag = "%s_%s" % (POST, v["id"])
        fn["post/%s" % v["id"]] = [
            "advancement revoke @s only %s/post_%s" % (F, v["id"]),
            "execute as @e[type=minecraft:interaction,tag=%s] run data remove entity @s interaction" % tag,
            "function %s" % F_("challenge/%s" % v["id"])]
        out["data/%s/advancement/arena/post_%s.json" % (NS, v["id"])] = {
            "criteria": {"click": {"trigger": "minecraft:player_interacted_with_entity", "conditions": {"entity": [
                {"condition": "minecraft:entity_properties", "entity": "this",
                 "predicate": {"type": "minecraft:interaction", "nbt": "{Tags:[\"%s\"]}" % tag}}]}}},
            "rewards": {"function": F_("post/%s" % v["id"])}}
    out["data/%s/advancement/arena/npc_click.json" % NS] = {
        "criteria": {"click": {"trigger": "minecraft:player_interacted_with_entity", "conditions": {"entity": [
            {"condition": "minecraft:entity_properties", "entity": "this",
             "predicate": {"type": "cobblemon:npc", "nbt": "{Tags:[\"%s\"]}" % ARENA_TAG}}]}}},
        "rewards": {"function": F_("npc_click")}}
    fn["npc_click"] = [
        "# canChallenge false is what refuses the battle (the class); this only says why to a player who is not the owner",
        "advancement revoke @s only %s/npc_click" % F,
        "function %s" % F_("mine"),
        "scoreboard players set #own ar.t 0",
        "execute as %s if score @s ar.id = #me ar.id run scoreboard players set #own ar.t 1" % npc("distance=..8"),
        "execute if score #own ar.t matches 0 run %s" % say(
            "That challenger is waiting for someone else. Click a venue's post to call your own.", "gray")]

    # ---- the challenge, per venue
    for i, v in enumerate(vs, 1):
        ox, oy, oz, _oyaw = v["opponent_spot"]
        rs = sorted(set(v["ranks"]))
        c = ["# as the clicking player, at venue %s (ranks %s)" % (v["id"], rs),
             "execute unless score @s ar.id matches 1.. run function %s" % F_("new_id"),
             "execute unless score @s ar.rank matches 1.. run scoreboard players set @s ar.rank 1",
             "function %s" % F_("mine"),
             "function %s" % F_("validate"),
             "execute if score @s ar.live matches 1 run return run %s" % say(
                 "Your opponent is already on the floor. Finish that bout first.", "gray"),
             "# the level cap (review N57, sweep U54): an arena opponent is a cobblemon:npc, which rctmod's over-cap",
             "# refusal never reaches, so a party strictly over the player's RCT cap is refused here, before anything",
             "# spawns (tools/levelcap_pack.py battle_check; a cap that did not read lets the challenge through)",
             "function %s {x:\"\"}" % LC.BATTLE_CHECK,
             "execute if entity @s[tag=%s] run return run tellraw @s [%s,{\"score\":{\"name\":\"@s\",\"objective\":"
             "\"%s\"},\"color\":\"gold\"},%s]"
             % (LC.PARTY_OVER, text("The Arena will not match you: a Pokemon in your party is above your level cap of "),
                LC.CAP, text(". Put every Pokemon above it in the PC and challenge again.")),
             "# the venue holds one run at a time",
             "scoreboard players set #busy ar.t 0",
             "execute as @a[scores={ar.live=1,ar.venue=%d}] unless score @s ar.id = #me ar.id run "
             "scoreboard players set #busy ar.t 1" % i,
             "execute positioned %s %s %s if entity %s run scoreboard players set #busy ar.t 1"
             % (fmt(ox), fmt(oy), fmt(oz), npc("distance=..4")),
             "execute if score #busy ar.t matches 1 run return run %s" % say(
                 "Someone is fighting at this venue. Try another, or wait.", "gray"),
             "# the highest rank this venue offers that the player holds and whose band they meet; below their own "
             "rank is playing down"]
        c.append("scoreboard players set #fight ar.t 0")
        for r in rs:
            for term in lad[r]["terms"] or [[]]:
                cond = (" if entity %s" % adv_selector(term)) if term else ""
                c.append("execute if score @s ar.rank matches %d..%s run scoreboard players set #fight ar.t %d"
                         % (r, cond, r))
        c += ["execute if score #fight ar.t matches 0 run return run tellraw @s [%s,{\"score\":{\"name\":\"@s\","
              "\"objective\":\"ar.rank\"},\"color\":\"white\"},%s]"
              % (text("Nothing here is open to you yet. You hold rank ", "gray"),
                 text(" -- this venue offers ranks %s." % ", ".join(map(str, rs)), "gray")),
              "scoreboard players operation @s ar.cur = #fight ar.t",
              "scoreboard players set @s ar.venue %d" % i,
              "scoreboard players set @s ar.leg 0",
              "scoreboard players set @s ar.streak 0",
              "function %s" % F_("bout/kind"),
              "function %s" % F_("bout/start")]
        fn["challenge/%s" % v["id"]] = c
        cx, cy, cz, cyaw = v["challenger_mark"]
        fn["venue/%s/spawn" % v["id"]] = [
            "# as the challenger: onto the challenger's mark, then the opponent at the opponent's spot (ABSOLUTE",
            "# coordinates: the relative form spawned nothing in game, 2026-10-03); the class is a macro argument",
            "tp @s %s %s %s %s 0" % (fmt(cx + 0.5 if float(cx).is_integer() else cx), fmt(cy),
                                     fmt(cz + 0.5 if float(cz).is_integer() else cz), fmt(cyaw)),
            "$spawnnpcat %s %s %s $(cls) $(level)" % (fmt(ox), fmt(oy), fmt(oz)),
            "execute positioned %s %s %s as @e[type=cobblemon:npc,tag=!%s,distance=..1.5,sort=nearest,limit=1] "
            "run function %s" % (fmt(ox), fmt(oy), fmt(oz), ARENA_TAG, F_("claim"))]
    fn["claim"] = ["# as the NPC just spawned: an arena opponent, owned by #me",
                   "tag @s add %s" % ARENA_TAG, "tag @s add %s" % PICK,
                   "scoreboard players operation @s ar.id = #me ar.id"]
    fn["validate"] = [
        "# as a player: repair a run whose opponent is gone (a sweep, an unload, a crash). Timers mean it is fine",
        "execute unless score @s ar.live matches 1 run return 0",
        "execute if score @s ar.end matches 1.. run return 0",
        "execute if score @s ar.go matches 1.. run return 0",
        "scoreboard players set #mine ar.t 0",
        "execute as %s if score @s ar.id = #me ar.id run scoreboard players set #mine ar.t 1" % NPC,
        "execute if score #mine ar.t matches 1 run return 0",
        say("Your last bout ended without a result, so that run is over.", "gray"),
        "function %s" % F_("lose_run")]

    # ---- which bout: kind, exhibition
    k = ["# as a player with ar.cur set: 1 a pool bout, 2 the rank-up exam, 3 the streak; ar.exh when 2+ below",
         "scoreboard players set @s ar.kind 1",
         "scoreboard players set @s ar.exh 0",
         "scoreboard players operation #gap ar.t = @s ar.rank",
         "scoreboard players operation #gap ar.t -= @s ar.cur",
         "execute if score #gap ar.t matches 2.. run scoreboard players set @s ar.exh 1"]
    for n, e in sorted(lad.items()):
        if e["format"] == "streak":
            k.append("execute if score @s ar.cur matches %d run scoreboard players set @s ar.kind 3" % n)
            continue
        k.append("execute if score @s ar.cur matches %d if score @s ar.rank matches %d if score @s ar.wins matches "
                 "%d.. run scoreboard players set @s ar.kind 2" % (n, n, e["need"]))
        for w in e["waived"]:
            k.append("execute if score @s ar.cur matches %d if score @s ar.rank matches %d if entity %s run "
                     "scoreboard players set @s ar.kind 2" % (n, n, adv_selector([w])))
    fn["bout/kind"] = k

    # ---- start a bout (the first, or the next leg)
    s = ["# as the challenger: heal per the format, pick the class and level, spawn at the venue, start shortly",
         "function %s" % F_("mine"),
         "data remove storage %s args" % STORE]
    for n, e in sorted(lad.items()):
        if e["format"] == "streak":
            continue
        if e["legs"] == 1:
            s.append("execute if score @s ar.kind matches 1 if score @s ar.cur matches %d run healpokemon @s" % n)
        else:
            s.append("execute if score @s ar.kind matches 1 if score @s ar.cur matches %d if score @s ar.leg matches 0 "
                     "run healpokemon @s" % n)
            if e["heal_before_leg"]:
                s.append("execute if score @s ar.kind matches 1 if score @s ar.cur matches %d if score @s ar.leg "
                         "matches %d run healpokemon @s" % (n, e["heal_before_leg"]))
        s += ['execute if score @s ar.kind matches 1 if score @s ar.cur matches %d run data modify storage %s args '
              'set value {cls:"%s:arena_rank_%d",level:%d}' % (n, STORE, NS, n, e["top"] - (e["members"] - 1))]
        for leg, (tid, _p) in enumerate(e["exam"]):
            ace = max(m["level"] for m in champs[tid]["team"])
            s.append('execute if score @s ar.kind matches 2 if score @s ar.cur matches %d if score @s ar.leg matches %d '
                     'run data modify storage %s args set value {cls:"%s:arena_exam_%s",level:%d}'
                     % (n, leg, STORE, NS, tid, ace))
    s.append("execute if score @s ar.kind matches 2 if score @s ar.leg matches 0 run healpokemon @s")
    s.append("execute if score @s ar.kind matches 3 run function %s" % F_("streak/start"))
    s.append("execute unless data storage %s args.cls run return run function %s" % (STORE, F_("spawn_failed")))
    for i, v in enumerate(vs, 1):
        s.append("execute if score @s ar.venue matches %d run function %s with storage %s args"
                 % (i, F_("venue/%s/spawn" % v["id"]), STORE))
    s += ["execute unless entity @e[type=cobblemon:npc,tag=%s] run return run function %s" % (PICK, F_("spawn_failed")),
          "tag @s add %s" % ME,
          "execute as @e[type=cobblemon:npc,tag=%s] at @s run tp @s ~ ~ ~ facing entity @p[tag=%s] eyes" % (PICK, ME),
          "tag @s remove %s" % ME,
          "tag @e[tag=%s] remove %s" % (PICK, PICK),
          "tag @s add %s" % bout_tag,
          "scoreboard players set @s ar.live 1",
          "scoreboard players set @s ar.idle 0",
          "scoreboard players set @s ar.go %d" % GO_TICKS,
          "function %s" % F_("announce")]
    fn["bout/start"] = s
    ann = []
    for n, e in sorted(lad.items()):
        if e["format"] == "streak":
            ann.append("execute if score @s ar.cur matches %d run tellraw @s [%s,{\"score\":{\"name\":\"@s\","
                       "\"objective\":\"ar.streak\"},\"color\":\"white\"}]"
                       % (n, text("%s, %s: streak " % (e["name"], e["title"]))))
            continue
        ann.append("execute if score @s ar.kind matches 1 if score @s ar.cur matches %d run %s"
                   % (n, say("%s (rank %d): %s" % (e["name"], n, "a single battle" if e["legs"] == 1 else
                                                   "a gauntlet of %d, leg by leg" % e["legs"]))))
        for leg, (tid, _p) in enumerate(e["exam"]):
            ann.append("execute if score @s ar.kind matches 2 if score @s ar.cur matches %d if score @s ar.leg matches "
                       "%d run %s" % (n, leg, say("Rank-up fight: %s" % champs[tid]["display_name"])))
    ann.append("execute if score @s ar.exh matches 1 run %s" % say(
        "An exhibition: two or more ranks below your own pays a quarter purse and no bonus.", "gray"))
    fn["announce"] = ann
    fn["spawn_failed"] = [
        "# no opponent appeared: the class is not loaded (NPC classes load at server START; restart after install)",
        "tag @e[tag=%s] remove %s" % (PICK, PICK),
        say("No opponent could be called. (Server: Heaven's Arena's classes load only at a restart.)", "red"),
        "function %s" % F_("lose_run")]
    fn["bout/begin"] = [
        "# as the challenger, %d ticks after the spawn: start the battle with no click (proven in game 2026-10-03)"
        % GO_TICKS,
        "function %s" % F_("mine"),
        "execute as %s if score @s ar.id = #me ar.id run tag @s add %s" % (npc("tag=!%s" % DONE_TAG), PICK),
        "execute unless entity @e[type=cobblemon:npc,tag=%s] run return run function %s" % (PICK, F_("lose_run")),
        "runmolang \"t.b = q.npc.start_battle(q.player, 'singles'); (t.b == 0) ? { q.run_command('execute as ' + "
        "q.player.uuid + ' run function %s'); };\" @s @e[type=cobblemon:npc,tag=%s,limit=1]" % (F_("refused"), PICK),
        "tag @e[tag=%s] remove %s" % (PICK, PICK)]
    fn["refused"] = [
        "# start_battle returned 0: no Pokemon able to battle, or already in a battle (BattleBuilder.pvn's refusals)",
        say("The bout could not start: your party has no Pokemon able to battle, or you are already in a battle.",
            "red"),
        "function %s" % F_("lose_run")]

    # ---- the result
    fn["mark_done"] = ["function %s" % F_("mine"),
                       "execute as %s if score @s ar.id = #me ar.id run tag @s add %s"
                       % (npc("tag=!%s" % DONE_TAG), DONE_TAG)]
    fn["won"] = [
        "# as the winning player (callbacks/battle_victory/cobblers_arena.molang), over their own opponent",
        "function %s" % F_("mark_done"),
        "scoreboard players set @s ar.idle 0",
        "scoreboard players set @s ar.next 0",
        "function %s" % F_("purse"),
        "execute if score @s ar.kind matches 1 run function %s" % F_("won_pool"),
        "execute if score @s ar.kind matches 2 run function %s" % F_("won_exam"),
        "execute if score @s ar.kind matches 3 run function %s" % F_("won_streak"),
        "scoreboard players set @s ar.end %d" % END_TICKS]
    wp = ["scoreboard players add @s ar.leg 1"]
    for n, e in sorted(lad.items()):
        if e["format"] != "streak" and e["legs"] > 1:
            wp.append("execute if score @s ar.cur matches %d if score @s ar.leg matches ..%d run scoreboard players set "
                      "@s ar.next 1" % (n, e["legs"] - 1))
    wp += ["execute if score @s ar.next matches 1 run return run tellraw @s [%s,{\"score\":{\"name\":\"@s\","
           "\"objective\":\"ar.leg\"},\"color\":\"white\"},%s]" % (text("Leg "), text(" won. The next one is coming.")),
           "scoreboard players set @s ar.leg 0"]
    for n, e in sorted(lad.items()):
        if e["format"] != "streak" and e["legs"] > 1 and e["clear_bonus"]:
            wp.append("execute if score @s ar.cur matches %d if score @s ar.exh matches 0 run function %s {amount:%d}"
                      % (n, F_("pay"), e["clear_bonus"]))
            wp.append("execute if score @s ar.cur matches %d run %s" % (n, say("Gauntlet cleared.")))
    wp.append("execute if score @s ar.cur = @s ar.rank run function %s" % F_("progress"))
    fn["won_pool"] = wp
    pr = ["# a pool bout (or a whole gauntlet) won at the player's own rank", "scoreboard players add @s ar.wins 1"]
    for n, e in sorted(lad.items()):
        if e["format"] == "streak":
            continue
        name = " then ".join(champs[t]["display_name"] for t, _p in e["exam"])
        pr.append("execute if score @s ar.rank matches %d if score @s ar.wins matches %d.. run %s"
                  % (n, e["need"], say("Your rank-up fight is open: %s. Challenge again at a rank %d venue." % (name, n))))
        pr.append("execute if score @s ar.rank matches %d if score @s ar.wins matches ..%d run tellraw @s [%s,"
                  "{\"score\":{\"name\":\"@s\",\"objective\":\"ar.wins\"},\"color\":\"white\"},%s]"
                  % (n, e["need"] - 1, text("Wins at this rank: "), text(" of %d." % e["need"])))
    fn["progress"] = pr
    we = ["scoreboard players add @s ar.leg 1"]
    for n, e in sorted(lad.items()):
        if e["format"] != "streak" and len(e["exam"]) > 1:
            we.append("execute if score @s ar.cur matches %d if score @s ar.leg matches ..%d run scoreboard players set "
                      "@s ar.next 1" % (n, len(e["exam"]) - 1))
    we += ["execute if score @s ar.next matches 1 run return run %s" % say("One down. The next comes with no heal."),
           "scoreboard players set @s ar.leg 0",
           "execute if score @s ar.cur = @s ar.rank run function %s" % F_("rank_up")]
    fn["won_exam"] = we
    ru = ["# as the player: the exam of their own rank beaten. First-clear prize once, then up a rank"]
    for n, e in sorted(lad.items()):
        if e.get("prize"):
            ru.append("execute if score @s ar.rank matches %d unless entity @s[tag=cobblers.%s] run function %s"
                      % (n, e["prize"], F_("prize/%s" % e["prize"])))
    top_rank = max(lad)
    ru += ["execute if score @s ar.rank matches ..%d run scoreboard players add @s ar.rank 1" % (top_rank - 1),
           "scoreboard players set @s ar.wins 0"]
    for n, e in sorted(lad.items()):
        ru.append("execute if score @s ar.rank matches %d run title @s title %s" % (n, text("Rank %d" % n)))
        ru.append("execute if score @s ar.rank matches %d run title @s subtitle %s" % (n, text(e["name"], "white")))
    fn["rank_up"] = ru

    # ---- rank 9, the streak
    (sn, se), = [(n, e) for n, e in lad.items() if e["format"] == "streak"]
    st = se["streak"]
    fn["streak/levels"] = [
        "# as the player: #L the streak's level, #m its team size, from ar.streak (wins so far in this run)",
        "scoreboard players operation #L ar.t = @s ar.streak",
        "scoreboard players set #k ar.t %d" % st["level_step_every_wins"],
        "scoreboard players operation #L ar.t /= #k ar.t",
        "scoreboard players set #k ar.t %d" % st["level_step"],
        "scoreboard players operation #L ar.t *= #k ar.t",
        "scoreboard players add #L ar.t %d" % st["level_start"],
        "execute if score #L ar.t matches %d.. run scoreboard players set #L ar.t %d" % (st["level_max"], st["level_max"]),
        "scoreboard players operation #m ar.t = @s ar.streak",
        "scoreboard players remove #m ar.t %d" % st["full_at"],
        "execute if score #m ar.t matches ..-1 run scoreboard players set #m ar.t 0",
        "scoreboard players set #k ar.t %d" % st["members_every"],
        "scoreboard players operation #m ar.t /= #k ar.t",
        "scoreboard players add #m ar.t %d" % st["members_start"],
        "execute if score #m ar.t matches %d.. run scoreboard players set #m ar.t %d"
        % (st["members_max"], st["members_max"])]
    ss = ["function %s" % F_("streak/levels"),
          "# healed at the start of a run and every %d wins" % st["heal_every"],
          "scoreboard players operation #h ar.t = @s ar.streak",
          "scoreboard players set #k ar.t %d" % st["heal_every"],
          "scoreboard players operation #h ar.t %= #k ar.t",
          "execute if score #h ar.t matches 0 run healpokemon @s",
          "# spawned at L - (m - 1): levelVariation m - 1 then puts every member at or under L",
          "scoreboard players operation #sl ar.t = #L ar.t",
          "scoreboard players operation #sl ar.t -= #m ar.t",
          "scoreboard players add #sl ar.t 1"]
    for m in range(st["members_start"], st["members_max"] + 1):
        ss.append('execute if score #m ar.t matches %d run data modify storage %s args.cls set value "%s:arena_streak_m%d"'
                  % (m, STORE, NS, m))
    ss.append("execute store result storage %s args.level int 1 run scoreboard players get #sl ar.t" % STORE)
    fn["streak/start"] = ss
    ws = ["scoreboard players add @s ar.streak 1",
          "execute unless score @s ar.best >= @s ar.streak run scoreboard players operation @s ar.best = @s ar.streak",
          "scoreboard players operation #r ar.t = @s ar.streak",
          "scoreboard players operation #r ar.t %= #c5 ar.t",
          "execute if score #r ar.t matches 0 run function %s {amount:%d}" % (F_("pay"), st["bonus"])]
    for at, pid in se["milestones"]:
        ws.append("execute if score @s ar.streak matches %d.. unless entity @s[tag=cobblers.%s] run function %s"
                  % (at, pid, F_("prize/%s" % pid)))
    ws += ["tellraw @s [%s,{\"score\":{\"name\":\"@s\",\"objective\":\"ar.streak\"},\"color\":\"white\"},%s,"
           "{\"score\":{\"name\":\"@s\",\"objective\":\"ar.best\"},\"color\":\"white\"}]"
           % (text("Streak "), text(". Best ")),
           "scoreboard players set @s ar.next 1"]
    fn["won_streak"] = ws

    # ---- money: the purse of the bout just won, before any score moves
    pu = ["# as the winner: 13 x the opponent's level sum, to the nearest 50 (prizes.purse_formula); a quarter when an",
          "# exhibition. Pool bouts use the draw's levels (ace at the top, each earlier one lower), exams the authored"]
    for n, e in sorted(lad.items()):
        if e["format"] == "streak":
            continue
        pu.append("execute if score @s ar.kind matches 1 if score @s ar.cur matches %d if score @s ar.exh matches 0 run "
                  "function %s {amount:%d}" % (n, F_("pay"), e["purse"]))
        pu.append("execute if score @s ar.kind matches 1 if score @s ar.cur matches %d if score @s ar.exh matches 1 run "
                  "function %s {amount:%d}" % (n, F_("pay"), e["exhibition"]))
        for leg, (_t, p) in enumerate(e["exam"]):
            pu.append("execute if score @s ar.kind matches 2 if score @s ar.cur matches %d if score @s ar.leg matches %d "
                      "run function %s {amount:%d}" % (n, leg, F_("pay"), p))
    pu.append("execute if score @s ar.kind matches 3 run function %s" % F_("streak/purse"))
    fn["purse"] = pu
    fn["streak/purse"] = [
        "function %s" % F_("streak/levels"),
        "# the level sum of m members ending at L: m*L - m(m-1)/2",
        "scoreboard players operation #s ar.t = #m ar.t",
        "scoreboard players operation #s ar.t *= #L ar.t",
        "scoreboard players operation #tri ar.t = #m ar.t",
        "scoreboard players remove #tri ar.t 1",
        "scoreboard players operation #tri ar.t *= #m ar.t",
        "scoreboard players operation #tri ar.t /= #c2 ar.t",
        "scoreboard players operation #s ar.t -= #tri ar.t",
        "scoreboard players operation #s ar.t *= #c13 ar.t",
        "scoreboard players operation #s ar.t += #half ar.t",
        "scoreboard players operation #s ar.t /= #c50 ar.t",
        "scoreboard players operation #s ar.t *= #c50 ar.t",
        "execute store result storage %s pay.amount int 1 run scoreboard players get #s ar.t" % STORE,
        "function %s with storage %s pay" % (F_("pay"), STORE)]
    fn["pay"] = [
        "# CobbleDollars' own command: `give` is VERIFIED from the jar (EXP-040); `remove` is the form proven in game",
        "$cobbledollars give @s $(amount)",
        '$tellraw @s {"text":"+$(amount) CobbleDollars","color":"green"}']
    for pid, p in sorted(prizes.items()):
        fn["prize/%s" % pid] = (["tag @s add cobblers.%s" % pid]
                                + ["give @s %s %d" % (c["item"], c["count"]) for c in p["contents"]]
                                + [say("First-clear prize: %s." % ", ".join(
                                    "%d x %s" % (c["count"], c["item"].split(":")[1].replace("_", " "))
                                    for c in p["contents"]), "aqua")])

    fn["lost"] = [
        "# as the losing player. No charge and no return: cobblers_blackout leaves a loss alone while the player holds",
        "# %s (data/blackout.json arena_exempt). The run and any streak end; the rank is kept" % bout_tag,
        "function %s" % F_("mark_done"),
        "execute if score @s ar.kind matches 3 run tellraw @s [%s,{\"score\":{\"name\":\"@s\",\"objective\":"
        "\"ar.streak\"},\"color\":\"white\"},%s,{\"score\":{\"name\":\"@s\",\"objective\":\"ar.best\"},"
        "\"color\":\"white\"}]" % (text("The streak ends at ", "gray"), text(". Best ", "gray")),
        "execute unless score @s ar.kind matches 3 run %s" % say("Beaten. Your rank is kept; click a post to go again.",
                                                                  "gray"),
        "scoreboard players set @s ar.streak 0",
        "scoreboard players set @s ar.leg 0",
        "scoreboard players set @s ar.next 0",
        "scoreboard players set @s ar.idle 0",
        "scoreboard players set @s ar.end %d" % END_TICKS]
    nxt = ["# as the player, the clear-up after a result: the beaten (or winning) opponent goes; then the next leg, or "
           "the end",
           "function %s" % F_("kill_mine"),
           "execute unless score @s ar.next matches 1 run return run function %s" % F_("end_run"),
           "scoreboard players set @s ar.next 0",
           "scoreboard players set #here ar.t 0"]
    for i, v in enumerate(vs, 1):
        cx, cy, cz, _y = v["challenger_mark"]
        nxt.append("execute if score @s ar.venue matches %d positioned %s %s %s if entity @s[distance=..%d] run "
                   "scoreboard players set #here ar.t 1" % (i, fmt(cx), fmt(cy), fmt(cz), VENUE_RANGE))
    nxt += ["execute if score #here ar.t matches 0 run %s" % say("You left the venue, so the run is over.", "gray"),
            "execute if score #here ar.t matches 0 run scoreboard players set @s ar.streak 0",
            "execute if score #here ar.t matches 0 run return run function %s" % F_("end_run"),
            "function %s" % F_("bout/start")]
    fn["after"] = nxt

    # ---- the sweep: orphans and abandoned bouts
    fn["sweep"] = [
        "scoreboard players set #clock ar.t 0",
        "execute as %s at @s run function %s" % (NPC, F_("sweep_one")),
        "# a tag left on a player whose run is over (a crash between the result and the clear-up)",
        "execute as @a[tag=%s] unless score @s ar.live matches 1 run tag @s remove %s" % (bout_tag, bout_tag)]
    fn["sweep_one"] = [
        "# as an arena opponent: no live owner within %d blocks makes it an orphan" % OWNER_RANGE,
        "scoreboard players operation #o ar.t = @s ar.id",
        "scoreboard players set #near ar.t 0",
        "execute as @a[distance=..%d,scores={ar.live=1}] if score @s ar.id = #o ar.t run scoreboard players set "
        "#near ar.t 1" % OWNER_RANGE,
        "execute if score #near ar.t matches 0 run return run kill @s",
        "execute if entity @s[tag=%s] run return 0" % DONE_TAG,
        "# owner near, no result yet: ask the NPC whether it is in a battle (a flee or forfeit sends no result)",
        "tag @s add %s" % PICK,
        "execute as @a[distance=..%d,scores={ar.live=1}] if score @s ar.id = #o ar.t unless score @s ar.go matches 1.. "
        "run runmolang \"(q.npc.in_battle == 0 && q.player.in_battle == 0) ? { q.run_command('execute as ' + "
        "q.player.uuid + ' run function %s'); };\" @s @e[type=cobblemon:npc,tag=%s,limit=1]"
        % (OWNER_RANGE, F_("idle"), PICK),
        "tag @s remove %s" % PICK]
    fn["idle"] = [
        "# as a player whose opponent stands out of battle with no result: %d sweeps in a row is an abandoned bout"
        % IDLE_SWEEPS,
        "execute if score @s ar.go matches 1.. run return 0",
        "execute if score @s ar.end matches 1.. run return 0",
        "scoreboard players add @s ar.idle 1",
        "execute if score @s ar.idle matches %d.. run function %s" % (IDLE_SWEEPS, F_("abandon"))]
    fn["abandon"] = [
        say("Your bout ended without a result (a run or a forfeit), so that run is over. Your rank is kept.", "gray"),
        "function %s" % F_("lose_run")]

    for name, lines in fn.items():
        out["data/%s/function/arena/%s.mcfunction" % (NS, name)] = lines
    out["data/minecraft/tags/function/load.json"] = {"values": [F_("load")]}
    out["data/minecraft/tags/function/tick.json"] = {"values": [F_("tick")]}
    out["data/cobblemon/callbacks/battle_victory/cobblers_arena.molang"] = callback()
    return out


def callback():
    """The result. Cobblemon fires only callbacks under its own namespace (EXP-042), so it sits beside
    cobblers_blackout. Every name below is one the in-game probe or the blackout callback already used
    (c.scriptable_losers/winners, c.player_winners/losers, .is_npc, .uuid, .player.uuid, q.run_command).
    The NPC must carry the arena tag, have no result yet, and be OWNED by that player (its ar.id equals theirs);
    every other NPC battle in the world falls through."""
    # three commands, in order: forget the last owner, read this NPC's owner (only if it is a live arena opponent),
    # then run the result as the player whose id it is. No UUID is ever used as a score holder
    def lines(npc, plr, result):
        return ["      q.run_command('scoreboard players set #o ar.t -1');",
                "      q.run_command('execute as ' + %s + ' if entity @s[tag=%s,tag=!%s] run scoreboard players "
                "operation #o ar.t = @s ar.id');" % (npc, ARENA_TAG, DONE_TAG),
                "      q.run_command('execute as ' + %s + ' if score @s ar.id = #o ar.t run function %s/%s');"
                % (plr, F, result)]
    return "\n".join([
        "'Generated by tools/arena_runtime.py. Heavens Arena: a player who beat (or lost to) their own arena opponent';",
        "'runs cobblers:arena/won (or lost) as themselves.';",
        "for_each(t.l, c.scriptable_losers, {",
        "  t.l.is_npc ? {",
        "    for_each(t.w, c.player_winners, {"]
        + lines("t.l.uuid", "t.w.player.uuid", "won") + [
        "    });",
        "  };",
        "});",
        "for_each(t.v, c.scriptable_winners, {",
        "  t.v.is_npc ? {",
        "    for_each(t.p, c.player_losers, {"]
        + lines("t.v.uuid", "t.p.player.uuid", "lost") + [
        "    });",
        "  };",
        "});",
        ""])


def forceload_boxes(dome_path=DOME):
    """[(x0, z0, x1, z1)] the R17A step holds while it places the posts: every venue, and the retired spire seats."""
    boxes = []
    if Path(dome_path).is_file():
        pts = []
        for v in doc(dome_path).get("venues") or []:
            pts += [v["post"], v["opponent_spot"], v["challenger_mark"]]
        if pts:
            xs, zs = [int(p[0] // 1) for p in pts], [int(p[2] // 1) for p in pts]
            boxes.append((min(xs), min(zs), max(xs), max(zs)))
    seats = [t["superseded_seat"]["seat"] for t in doc(DATA / "arena_trainers.json")["trainers"]
             if t.get("superseded_seat")]
    if seats:
        boxes.append((min(s[0] for s in seats) - 24, min(s[2] for s in seats) - 24,
                      max(s[0] for s in seats) + 24, max(s[2] for s in seats) + 24))
    return boxes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--dome", default=str(DOME), help="the venues (default data/arena_dome.json)")
    a = p.parse_args(argv)
    fs = files(Path(a.dome))
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, content in fs.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, list):
            body = "\n".join(content) + "\n"
        elif isinstance(content, str):
            body = content
        else:
            body = json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        f.write_text(body, encoding="utf-8", newline="\n")
    n_cls = sum(1 for k in fs if "/npcs/" in k)
    n_fn = sum(1 for k in fs if k.endswith(".mcfunction"))
    print("wrote %d files to %s: %d NPC classes, %d functions; classes load at server START (restart after install)"
          % (len(fs), out, n_cls, n_fn))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
