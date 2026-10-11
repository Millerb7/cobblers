#!/usr/bin/env python
"""The dungeon's NPC fights: the CobbleDollars clawback, and the trainer classes and battle start for stands.

Unit DG-CLAW (2026-10-09). A module of its own so the room framework (tools/dungeon.py's geometry) and this merge
cleanly; tools/dungeon.py reaches it through three hooks and nothing else (lazy imports there, because this module
imports tools/dungeon.py):

  build()      DF.functions(doc), DF.patch_functions(doc, fns), DF.pack_files(doc)
                                                       the claw/, stand/, wild and healer functions, the NPC classes,
                                                       tick.json, the load entry
  callback()   DF.victory_commands()                   what a won NPC battle runs (settle the clawback, stand hook)
  functions()  the boss's `go` calls claw/boss_begin_<short> before start_battle

THE CLAWBACK (docs/mechanics/DUNGEONS.md: stands and boss wins pay $0 net). CobbleDollars pays the winner of ANY NPC
battle by itself (CobbleDollarsEventsKt.battleVictory, docs/research/notes/paid-services-and-npc-payouts.md B2) and has
no per-battle exclusion, so the dungeon takes the payout BACK, by Heaven's Arena's design (tools/arena_runtime.py cd/*,
EXP-060, NOT_EXECUTED in game; the arena's docstring has the timing argument and it applies unchanged): the balance
(`cobbledollars query @s`) is read when the battle starts (claw/begin) and again at the start of every tick until the
result (claw/tick); on the win the gain, at most dg.cmax (the most CobbleDollars can credit for that class,
tools/arena_runtime.cd_bound), is removed with `cobbledollars remove`. CobbleDollars' handler and the callback answer
the same BATTLE_VICTORY in an order the jar does not fix: a gain below dg.cmin (the least it can credit) means its
handler has not run yet, so dg.claw is set to 1 and the start of the next tick looks again (sudden death's kill waits
on dg.claw, E1 rule 6). The dungeon pays no purse of its own, so the whole payout goes back.

  claw/begin               as the player, before the battle starts: dg.claw 0 and the baseline
  claw/bounds/<class>      as the player: dg.cmax / dg.cmin for that class's party (every class has one)
  claw/boss_begin_<short>  as the member: the bounds for their band and dg.stage, then claw/begin
  claw/settle              as the winner, from the battle_victory callback
  claw/tick                every tick (tick.json): the pending look, the cleanup, the baseline re-read

STANDS (seated by the room kinds `stand` and `gauntlet`/`ambush` below, unit DG-FIGHTS, which also holds the wild
rooms `miniboss`, `nest`, `habitat` and the `safe_room` healer; see the "wave 2: the rooms" section and
docs/mechanics/DUNGEON_ROOMS.md 4a). This module generates what the stands need). From a room's `params` -- `trainers`: a list of
{name, skin?, team_by_band: {band: [species...]}}, or `pool`: an id in data/dungeons.json engine.stands.pools -- one
NPC class per trainer per band (stand_classes), levels per engine.stands, and per (trainer, slot) the functions that
spawn the class by macro, start the battle a few ticks later and retry a refusal (stand_functions). The callback tells
a stand's win by the tag dg.stand and the stand's id (dg.sid, set on the NPC and copied to the winner): stand/won runs
stand/dispatch, which wave 2 builds with stand_dispatch([(sid, clear_function_id), ...]) so a won stand opens the
room's `clear`.

Nothing here has run in a server. The offline model is tests/test_dungeon_fights.py.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import arena_runtime as AR  # noqa: E402  (cd_bound, cd_least and the CobbleDollars config reads)
import dungeon as DG  # noqa: E402

STORE = "cobblers:dungeons"
TAG_STAND = "dg.stand"
TAG_KEY = "dg.stk."                    # + the stand's key: the NPC of that (room, trainer, slot)
TAG_PEND = "dg.sgo."                   # + the stand's key: the player whose battle is about to start
BAL, CMAX, CMIN, SID, TRIES = "dg.bal", "dg.cmax", "dg.cmin", "dg.sid", "dg.sgo"
FI = "dg.fi"                           # DG-FIGHTS: passes a member has stood out of battle with a stand's fight pending
OBJECTIVES = [BAL, CMAX, CMIN, SID, TRIES, FI]
MEMBER_ST_FIGHTING = "2..4"            # dg.st values in which a battle can be live (the run's states 2, 3 and 4)
SLUG = re.compile(r"[a-z0-9_]+")
SPECIES = re.compile(r"[a-z0-9_-]+")
INT_MIN = "-2147483648"


class FightError(DG.DungeonError):
    pass


def F(name):
    return DG.F(name)


def O(key):
    return DG.OBJ[key]


# ------------------------------------------------------------------------------------------------- the money


def money():
    """(pays, most multiplier in thousandths, least multiplier in thousandths) from CobbleDollars' own config."""
    pays = AR.cd_pays_npc_wins()
    if not pays:
        return False, 0, 0
    return True, AR.cd_multiplier_permille(), AR.cd_multiplier_permille(floor=True)


def party_levels(cls):
    """The levels of a generated class's party (`species level=N` entries)."""
    return [int(re.search(r"level=(\d+)", p).group(1)) for p in cls["party"]["pokemon"]]


def bounds(levels, mult=None):
    """(most, least) CobbleDollars a win over a party with exactly these levels can credit (tools/arena_runtime
    cd_bound / cd_least, the bytecode formula in paid-services-and-npc-payouts.md B2). (0, 0) when CobbleDollars pays
    no NPC win: then nothing is taken."""
    pays, hi_pm, lo_pm = mult if mult is not None else money()
    if not pays:
        return 0, 0
    s = sum(levels)
    return AR.cd_bound(s, hi_pm), AR.cd_least(s, lo_pm)


def bounds_function(name, cls, mult=None):
    hi, lo = bounds(party_levels(cls), mult)
    return [DG.HEAD,
            "# As the player whose battle is about to start against class %s: the most (dg.cmax) and the least (dg.cmin)"
            % name,
            "# CobbleDollars can credit for beating it (tools/dungeon_fights.bounds; 0 when CobbleDollars pays no NPC win)",
            "scoreboard players set @s %s %d" % (CMAX, hi),
            "scoreboard players set @s %s %d" % (CMIN, lo)]


def claw_functions():
    """{name: lines} for the engine-wide clawback."""
    T = O("t")
    claw, st = O("claw"), O("st")
    h = DG.HEAD
    out = {}
    out["claw/init"] = [
        h, "# Load (a second entry of load.json, after load): the clawback's objectives, and the handler order unlearned",
        "# (claw/last_take learns it again every boot: a mod update can change it)"] + [
        "scoreboard objectives add %s dummy" % o for o in OBJECTIVES] + [
        "scoreboard players set #cl_first %s 0" % T]
    out["claw/snap"] = [
        h, "# As a player: the balance now, the baseline a clawback measures from. A macro line, as the arena's and the",
        "# blackout's read is (EXP-046: a mod command on a plain line can be inert until a /reload)",
        "$execute store result score @s %s run cobbledollars query @s$(x)" % BAL]
    out["claw/now"] = ["$execute store result score #cl_now %s run cobbledollars query @s$(x)" % T]
    out["claw/begin"] = [
        h, "# As the player, just before a dungeon NPC battle starts (every start_battle in this pack is preceded by this):",
        "# no clawback pending, and the balance baseline. claw/bounds/<class> was called first (dg.cmax, dg.cmin)",
        "scoreboard players set @s %s 0" % claw,
        "function %s {x:\"\"}" % F("claw/snap")]
    out["claw/settle"] = [
        h, "# As the winning player, from the battle_victory callback (tools/dungeon_fights.victory_commands), over a",
        "# dungeon NPC (tag dg.npc). CobbleDollars paid this win by itself: take it back NOW when it has landed, else the",
        "# start of the next tick looks again (claw/tick -> claw/last). Nothing is kept after: no baseline, no pending look",
        "scoreboard players set @s %s 0" % claw,
        "function %s" % F("claw/first"),
        "execute unless score @s %s matches 1 run function %s" % (claw, F("claw/drop"))]
    out["claw/first"] = [
        h, "# As the winner, in the callback. No baseline or no allowance (CobbleDollars pays no NPC win): nothing is taken",
        "execute unless score @s %s matches %s.. run return 0" % (BAL, INT_MIN),
        "execute unless score @s %s matches 1.. run return 0" % CMAX,
        "function %s {x:\"\"}" % F("claw/now"),
        "scoreboard players operation #cl_now %s -= @s %s" % (T, BAL),
        "# less than the least CobbleDollars credits: its handler has not run yet. The next tick looks (claw/last)",
        "execute if score #cl_now %s < @s %s run return run scoreboard players set @s %s 1" % (T, CMIN, claw),
        "scoreboard players add #cl_nfirst %s 1" % T,
        "function %s" % F("claw/take")]
    out["claw/take"] = [
        h, "# #cl_now, the balance's gain over the baseline, at most dg.cmax, goes back (`cobbledollars remove` takes",
        "# min(amount, balance), amount >= 1). claw/first gets here with at least dg.cmin",
        "scoreboard players operation #cl_now %s < @s %s" % (T, CMAX),
        "execute if score #cl_now %s matches ..0 run return 0" % T,
        "execute store result storage %s claw.amount int 1 run scoreboard players get #cl_now %s" % (STORE, T),
        "function %s with storage %s claw" % (F("claw/claw"), STORE)]
    out["claw/claw"] = [
        h, "# CobbleDollars' own command, the form the arena and the blackout use (EXP-042 ran `remove`)",
        "$cobbledollars remove @s $(amount)",
        '$tellraw @s {"text":"(-$(amount): the rift keeps CobbleDollars\' payout for this win)","color":"gray"}']
    out["claw/last"] = [
        h, "# As the player, at the start of the tick after a deferred win (or on their return): the gain since the",
        "# baseline goes back, clamped; then nothing is pending",
        "execute if score @s %s matches %s.. if score @s %s matches 1.. run function %s"
        % (BAL, INT_MIN, CMAX, F("claw/last_take")),
        "function %s" % F("claw/drop")]
    out["claw/last_take"] = [
        h, "function %s {x:\"\"}" % F("claw/now"),
        "scoreboard players operation #cl_now %s -= @s %s" % (T, BAL),
        "# a gain of at least the least CobbleDollars credits: its handler ran after the callback. Learned for this boot",
        "# (init resets it): from then on a deferred win takes at least dg.cmin, because CobbleDollars certainly paid that",
        "# much, so a smaller gain means money was paid away in the window",
        "execute if score #cl_now %s >= @s %s run scoreboard players set #cl_first %s 1" % (T, CMIN, T),
        "execute if score #cl_first %s matches 1 run scoreboard players operation #cl_now %s > @s %s" % (T, T, CMIN),
        "scoreboard players add #cl_nlast %s 1" % T,
        "function %s" % F("claw/take")]
    out["claw/drop"] = [
        h, "# As a player: no clawback pending and no baseline kept",
        "scoreboard players set @s %s 0" % claw,
        "scoreboard players reset @s %s" % BAL]
    out["claw/tick"] = [
        h, "# Every tick (data/minecraft/tags/function/tick.json), FIRST in the tick: the second look at a win whose",
        "# callback ran before CobbleDollars' handler. Battles end in END_SERVER_TICK, so this is the next point a datapack",
        "# runs (tools/arena_runtime.py's docstring and EXP-060). A player who was offline then is looked at on return",
        "execute as @a[scores={%s=1}] run function %s" % (claw, F("claw/last")),
        "# a baseline held by a player no longer in a run (a lost fight, a death, a logout): dropped",
        "execute as @a[scores={%s=%s..}] unless score @s %s matches %s run function %s"
        % (BAL, INT_MIN, st, MEMBER_ST_FIGHTING, F("claw/drop")),
        "# a battle in progress: the baseline is re-read every tick, so money a player moves during it is never measured",
        "# as CobbleDollars' payout (player commands run between ticks; the victory and its callback run inside one)",
        "execute as @a[scores={%s=%s..}] unless score @s %s matches 1 run function %s {x:\"\"}"
        % (BAL, INT_MIN, claw, F("claw/snap"))]
    return out


def boss_functions(doc, mult=None):
    """claw/bounds/<class> for every boss class and claw/boss_begin_<short> per dungeon."""
    out = {}
    for d in DG.dungeons(doc):
        lines = [DG.HEAD, "# As %s's member, just before the boss stage dg.stage starts: the bounds of that stage's class for"
                 % d["id"], "# their band, then the baseline (dungeon.py's slot/s<g>/go calls this before start_battle)"]
        for name, (cls, _lvl) in DG.boss_classes(doc, d).items():
            out["claw/bounds/%s" % name] = bounds_function(name, cls, mult)
            m = re.fullmatch(r"dg_%s_boss_b(\d+)_s(\d+)(?:_v(\d+))?" % re.escape(d["short"]), name)
            cond = DG.boss_cond(d, int(m.group(1)), int(m.group(3) or 1))
            lines.append("execute if score @s %s matches %s if score @s %s matches %s %srun function %s"
                         % (O("band"), m.group(1), O("stage"), m.group(2), cond, F("claw/bounds/%s" % name)))
        lines.append("function %s" % F("claw/begin"))
        out["claw/boss_begin_%s" % d["short"]] = lines
    return out


def boss_begin_ref(d):
    """The function the boss's `go` calls before start_battle."""
    return F("claw/boss_begin_%s" % d["short"])


def victory_commands():
    """MoLang statements inside tools/dungeon.py callback()'s `for each NPC loser x player winner` (t.l, t.w):
    settle the clawback for any dungeon NPC (tag dg.npc), then a stand's win: its id copied to the winner, who runs
    stand/won (dispatch to the room's clear) at their own position."""
    npc = DG.TAGS["npc"]
    return [
        "  q.run_command('execute as ' + t.l.uuid + ' if entity @s[tag=%s] as ' + t.w.player.username + ' run function %s');"
        % (npc, F("claw/settle")),
        "  q.run_command('execute as ' + t.l.uuid + ' if entity @s[tag=%s] run scoreboard players operation ' + "
        "t.w.player.username + ' %s = @s %s');" % (TAG_STAND, SID, SID),
        "  q.run_command('execute as ' + t.w.player.username + ' at @s if score @s %s matches 1.. run function %s');"
        % (SID, F("stand/won"))]


# ------------------------------------------------------------------------------------------------- stands


def stand_settings(doc):
    return doc["engine"]["stands"]


def room_slug(room):
    rid = room.get("id")
    if not isinstance(rid, str) or not SLUG.fullmatch(rid):
        raise FightError("room id %r: lowercase letters, digits and underscores only (it names classes and tags)" % (rid,))
    return rid


def trainers_of(doc, room):
    """The room's trainers: params.trainers, else the pool params.pool names in engine.stands.pools."""
    p = room.get("params") or {}
    if "trainers" in p:
        return p["trainers"]
    if "pool" in p:
        pools = stand_settings(doc).get("pools", {})
        if p["pool"] not in pools:
            raise FightError("room %s: pool %r is not in engine.stands.pools" % (room.get("id"), p["pool"]))
        return pools[p["pool"]]
    raise FightError("room %s: params has neither `trainers` nor `pool`" % room.get("id"))


def stand_levels(doc, band_entry, members):
    """The party's levels, ascending, the ace last (DUNGEONS.md 5.3, engine.stands): from the band's lower cap less
    low_offset to the lower cap less high_offset; band 6 (a single cap of 100) spans band6_levels."""
    s = stand_settings(doc)
    lo_cap = min(band_entry["caps"])
    if band_entry["band"] == 6:
        low, high = s["band6_levels"]
    else:
        low, high = lo_cap - s["low_offset"], lo_cap - s["high_offset"]
    if members == 1:
        return [high]
    return [low + ((high - low) * i + (members - 1) // 2) // (members - 1) for i in range(members)]


def stand_problems(doc, room):
    bad = []
    s = stand_settings(doc)
    try:
        room_slug(room)
        ts = trainers_of(doc, room)
    except FightError as e:
        return [str(e)]
    if not ts:
        bad.append("room %s: no trainer" % room["id"])
    for n, t in enumerate(ts, 1):
        who = "room %s trainer %d" % (room["id"], n)
        if not isinstance(t.get("name"), str) or not t["name"]:
            bad.append("%s: no name" % who)
        tb = t.get("team_by_band") or {}
        tp = t.get("team_pool_by_band")
        if tp is not None:
            if not isinstance(tp, dict) or any(not isinstance(v, list) or not 1 <= len(v) <= POOL_MAX for v in tp.values()):
                bad.append("%s: team_pool_by_band is {band: [team, ...]}, 1..%d teams a band" % (who, POOL_MAX))
                tp = {}
            for k in sorted(set(tp) & set(tb)):
                bad.append("%s band %s: team_by_band and team_pool_by_band both name it (the pool is the band's teams)"
                           % (who, k))
            for k, v in tp.items():
                if len({json.dumps(x) for x in v}) != len(v):
                    bad.append("%s band %s: team_pool_by_band repeats a team" % (who, k))
        for b in DG.bands(doc):
            pool = team_pool(t, b["band"])
            team = pool[0] if pool else None
            want = s["members_by_band"][str(b["band"])]
            # a trainer may be eased below the band's size by a declared, explained number (the owner, 2026-10-10: tuned
            # by tools/dungeon_sim.py to a 60-90% win at the band's lower cap); never more than 2 under, never under 2
            eased = int((t.get("members_eased_by_band") or {}).get(str(b["band"]), 0))
            if eased and (not t.get("members_eased_why") or not 1 <= eased <= 2 or want - eased < 2):
                bad.append("%s band %d: members_eased_by_band needs a members_eased_why, 1-2 under and at least 2 members" % (who, b["band"]))
            want -= eased
            if not team:
                bad.append("%s: no team for band %d" % (who, b["band"]))
            for v, team in enumerate(pool, 1):
                tag = "" if len(pool) == 1 else " pool team %d" % v
                if not isinstance(team, list) or not team:
                    bad.append("%s band %d%s: a team is a non-empty list" % (who, b["band"], tag))
                elif len(team) != want:
                    bad.append("%s band %d%s: %d members, DUNGEONS.md 5.3 says %d" % (who, b["band"], tag, len(team), want))
                elif any(not isinstance(x, str) or not SPECIES.fullmatch(x) for x in team):
                    bad.append("%s band %d%s: a species is not a lowercase id" % (who, b["band"], tag))
        if set(tb) - {str(b["band"]) for b in DG.bands(doc)} or set(tp or {}) - {str(b["band"]) for b in DG.bands(doc)}:
            bad.append("%s: a team for a band that does not exist" % who)
    return bad


def npc_class(name, resource, skill, team):
    """The shape of boss_classes' classes (tools/dungeon.py) and Heaven's Arena's (arena_runtime.npc_class)."""
    return {"hitbox": "player", "names": [name], "resourceIdentifier": resource,
            "canDespawn": False, "isInvulnerable": True, "isMovable": False, "isLeashable": False,
            "allowProjectileHits": False, "autoHealParty": True,
            "battleConfiguration": {"canChallenge": False}, "skill": skill,
            "ai": [{"type": "apply_behaviours", "presets": ["cobblemon:battler", "cobblemon:looks_at_players"]}],
            "party": {"type": "simple", "pokemon": team}}


def stand_class_name(d, room, n, band, k=1):
    """Pool team k (1-based) of trainer n at `band`; team 1 keeps the name it had before rotation existed."""
    base = "dg_%s_st_%s_t%d_b%d" % (d["short"], room_slug(room), n, band)
    return base if k == 1 else "%s_v%d" % (base, k)


def stand_classes(doc, d, room):
    """{class name: (class json, the ace's level)} -- one class per trainer per band per pool team for the room's stand."""
    bad = stand_problems(doc, room)
    if bad:
        raise FightError("; ".join(bad))
    s = stand_settings(doc)
    out = {}
    for n, t in enumerate(trainers_of(doc, room), 1):
        for b in DG.bands(doc):
            for k, team in enumerate(team_pool(t, b["band"]), 1):
                lv = stand_levels(doc, b, len(team))
                out[stand_class_name(d, room, n, b["band"], k)] = (
                    npc_class(t["name"], t.get("skin") or DG.NPC_RESOURCE, s["skill"],
                              ["%s level=%d" % (sp, lv[i]) for i, sp in enumerate(team)]), lv[-1])
    return out


def stand_variants(doc, room, n, band, slot_g):
    """[(execute clause, pool team k)] for trainer n at `band`: one per room index, exactly one of which fires."""
    ts = trainers_of(doc, room)
    size = len(team_pool(ts[n - 1], band))
    N = max([len(team_pool(t, band)) for t in ts] + [1])      # rotation_size, for a room record with no kind (tests)
    if size <= 1 or N <= 1:
        return [("", 1)]
    H = rot_holder(slot_g, room)
    return [(rot_cond(H, v, N), pick(size, v)) for v in range(1, N + 1)]


def stand_key(d, room, n, slot_g):
    return "%s_%s_t%d_s%d" % (d["short"], room_slug(room), n, slot_g)


def stand_functions(doc, d, room, n, slot_g, spot, sid, mult=None):
    """{name: lines} for trainer `n` (1-based) of the room's stand in slot `slot_g`, standing at `spot` (x, y, z):

      stand/<key>/start    as the player: spawn the class of their band at the spot, then the battle go_ticks later
      stand/<key>/bind     as the new NPC: ours (the slot's bind), a stand (dg.stand), keyed, with id `sid`
      stand/<key>/go       the scheduled function (server): the pending player's go_p
      stand/<key>/go_p     as the player: claw/begin, then start_battle; a refusal calls refused
      stand/<key>/refused  as the player: try again, retry_ticks later, until dg.sgo runs out
      claw/bounds/<class>  for each of the trainer's classes

    `sid` is the stand's id (a positive int, unique among all stands; the caller owns that): the winner's dg.sid, which
    stand/dispatch (stand_dispatch) maps to the room's clear. The caller starts the fight by calling stand/<key>/start
    as the player; a won fight reaches the callback."""
    if not isinstance(sid, int) or isinstance(sid, bool) or sid < 1:
        raise FightError("stand id %r: a positive integer" % (sid,))
    classes = stand_classes(doc, d, room)
    s = stand_settings(doc)
    dim = doc["engine"]["pocket"]["dimension"]
    key = stand_key(d, room, n, slot_g)
    x, y, z = spot
    keytag, pendtag = TAG_KEY + key, TAG_PEND + key
    base = "stand/%s" % key
    npc_sel = "@e[type=cobblemon:npc,tag=%s,limit=1]" % keytag
    h = DG.HEAD
    out = {}
    start = [h, "# As the player in slot %d, to fight trainer %d of room %s: the class of their band (dg.band) is spawned at"
             % (slot_g, n, room["id"]),
             "# the spot by a MACRO line (EXP-078: a plain line naming our class fails to parse at load), bound at once, and",
             "# the battle starts go_ticks later (L1/C1: a tick after the spawn)",
             "execute in %s run kill @e[type=cobblemon:npc,tag=%s]" % (dim, keytag)]
    for b in DG.bands(doc):
        for cond, k in stand_variants(doc, room, n, b["band"], slot_g):
            cname = stand_class_name(d, room, n, b["band"], k)
            start.append("execute if score @s %s matches %d %sin %s run function %s {x:\"%.1f\",y:\"%d\",z:\"%.1f\",cls:\"%s:%s\","
                         "level:\"%d\"}" % (O("band"), b["band"], cond, dim, F("npc_at"), x + 0.5, y, z + 0.5, DG.NS, cname,
                                            classes[cname][1]))
            start.append("execute if score @s %s matches %d %srun function %s" % (O("band"), b["band"], cond,
                                                                                 F("claw/bounds/%s" % cname)))
    start += ["execute in %s positioned %.1f %d %.1f as @e[type=cobblemon:npc,tag=!%s,distance=..1.5,sort=nearest,limit=1] "
              "run function %s" % (dim, x + 0.5, y, z + 0.5, DG.TAGS["npc"], F("%s/bind" % base)),
              "tag @s add %s" % pendtag,
              "scoreboard players set @s %s %d" % (TRIES, s["retries"]),
              "schedule function %s %dt append" % (F("%s/go" % base), s["go_ticks"])]
    out[base + "/start"] = start
    out[base + "/bind"] = [h, "# As the new stand NPC: ours (slot %d's bind), a stand, this stand's, with its id" % slot_g,
                           "function %s" % F("slot/s%d/bind" % slot_g),
                           "tag @s add %s" % TAG_STAND, "tag @s add %s" % keytag,
                           "scoreboard players set @s %s %d" % (SID, sid)]
    out[base + "/go"] = [h, "# Scheduled (server context) go_ticks after the spawn: the player waiting on this stand",
                         "execute as @a[tag=%s] run function %s" % (pendtag, F("%s/go_p" % base))]
    out[base + "/go_p"] = [
        h, "# As the player: the stand's battle, started with no click (the boss's `go`; arena note section 8). The pending",
        "# tag goes BEFORE the call: a refusal puts it back. No NPC (killed by a reset): nothing starts",
        "tag @s remove %s" % pendtag,
        "execute in %s unless entity %s run return 0" % (dim, npc_sel),
        "function %s" % F("claw/begin"),
        "execute in %s run runmolang \"t.b = q.npc.start_battle(q.player, 'singles'); (t.b == 0) ? { "
        "q.run_command('execute as ' + q.player.uuid + ' run function %s'); };\" @s %s"
        % (dim, F("%s/refused" % base), npc_sel)]
    out[base + "/refused"] = [
        h, "# As the player: start_battle returned 0 (no Pokemon able to battle, or already in a battle). Try again",
        "# retry_ticks later while dg.sgo lasts; then say so and leave the NPC standing for the room to restart",
        "scoreboard players remove @s %s 1" % TRIES,
        "execute if score @s %s matches 1.. run tag @s add %s" % (TRIES, pendtag),
        "execute if score @s %s matches 1.. run schedule function %s %dt append"
        % (TRIES, F("%s/go" % base), s["retry_ticks"]),
        "execute if score @s %s matches ..0 run tellraw @s %s"
        % (TRIES, DG.text("The trainer waits. Your party has no Pokemon able to battle, or you are in another battle.",
                          "red"))]
    for name, (cls, _lvl) in classes.items():
        out["claw/bounds/%s" % name] = bounds_function(name, cls, mult)
    return out


def stand_files(doc, d, room):
    """{path: json text} for the room's stand classes (the datapack's npcs/ folder)."""
    import json
    return {"data/%s/npcs/%s.json" % (DG.NS, name): json.dumps(cls, indent=2) + "\n"
            for name, (cls, _lvl) in stand_classes(doc, d, room).items()}


def stand_dispatch(entries=()):
    """{name: lines} for stand/dispatch (as the winner, dg.sid their stand's id: run that stand's clear) and stand/won
    (what the callback calls). entries: [(sid, function id)]; wave 2 passes the rooms' clear functions."""
    seen = set()
    lines = [DG.HEAD, "# As the winner of a stand, at their position, dg.sid their stand's id: the room's clear."
             " Built by tools/dungeon_fights.stand_dispatch from the rooms' (id, clear) pairs; empty when no room has a stand"]
    for sid, fn in entries:
        if sid in seen:
            raise FightError("stand id %d is dispatched twice" % sid)
        seen.add(sid)
        lines.append("execute if score @s %s matches %d run function %s" % (SID, sid, fn))
    return {"stand/dispatch": lines,
            "stand/won": [DG.HEAD, "# As the winner of a stand (the callback), at their position: the room's clear, then the id goes",
                          "function %s" % F("stand/dispatch"),
                          "scoreboard players reset @s %s" % SID]}


# ------------------------------------------------------------------------------------------------- wave 2: the rooms
#
# Unit DG-FIGHTS (2026-10-09). The room kinds `stand`, `gauntlet` (alias `ambush`), `miniboss`, `nest` and `habitat`,
# and the `safe_room` healer, registered with tools/dungeon_rooms.py on import. Rung: datapack plus generator. Nothing
# here needed a mod: the NPC fights are DG-CLAW's (stand_functions, the clawback), the wild Pokemon are spawned by the
# `spawnpokemonat` MACRO the Hoopa cradle, the ambient workers and Entei already use (.claude/rules/datapacks.md:
# `summon cobblemon:pokemon` is refused), and the healer is a vanilla bell plus `healpokemon @s`, the command the
# blackout already runs.
#
# STATE. Per room and slot, in dg.rs: the room's own holder #s<g>r<i> (0 not entered, 1 entered, 2 cleared: the kit's),
# #s<g>r<i>t<n> for trainer n of a stand (0 waiting, 1 fighting, 2 won), #s<g>r<i>w for a wild room (0..4 spawned and
# not seen yet, 10 seen, 11 absent once, 20 done), #s<g>r<i>v (the habitat's view title shown), #s<g>r<i>h (heals used).
# Everything is per slot and per run: the kit's reset puts all of it back, and the slot's free discards the wild
# Pokemon (patch_functions). A member who logs out, dies or is put out loses nothing the next run needs.
#
# WHAT CLEARS A WILD ROOM. Absence of the room's tagged Pokemon on two keeper passes in a row (a faint removes the
# entity, a catch removes it, a despawn removes it): the rule the gulch Megas' and the residents' respawn already use
# (docs/world-building/RESIDENT_ENCOUNTERS.md 4.2; SOUTHERN_RIFT_MEGA.md "the Mega faints and is gone", ASSUMED there
# too). A room whose Pokemon is never seen at all (a spawn that failed) opens after NEVER_SEEN_PASSES, with a message:
# a bug in a species id must never trap a player. UNPROVEN in game: that a fainted wild Pokemon's entity is removed.

import dungeon_rooms as R  # noqa: E402
from dungeon_rooms import fill, setb  # noqa: E402

KINDS_STAND = ("stand", "gauntlet", "ambush")
KINDS_WILD = ("miniboss", "nest", "habitat")
SID_BASE = 100                      # stand ids are SID_BASE + 1 ...: DG-CLAW's tests use small ones
SIGHT = 8                           # a stand trainer's line: this many blocks before the trainer
AMBUSH_GAP, AMBUSH_STEP = 8, 4      # a gauntlet: the barrier this far past the trigger, the trainer this far past that
MIN_TRIGGER_GAP = 14                # a gauntlet: triggers at least this far apart
FORFEIT_PASSES = 4                  # passes out of battle with a fight pending before the trainer is offered again
NEVER_SEEN_PASSES = 5               # passes a wild room waits for its Pokemon to appear before it opens anyway
HOLD_SEEN, HOLD_GONE, HOLD_DONE = 10, 11, 20
BIND_RADIUS = 2.5                   # the spawned Pokemon is the nearest unclaimed one this close to its spot
ROOM_KINDS = KINDS_STAND + KINDS_WILD
PROP_ID = re.compile(r"[a-z0-9_]+")
SOUND_OR_PARTICLE = re.compile(r"[a-z0-9_.:/-]+")
MSG = {
    "stand": "Trainers stand between you and the way on. Cross a trainer's line and they will fight.",
    "ambush": "The undergrowth moves.",
    "miniboss": "Something guards this room. Send a Pokemon out at it to fight.",
    "nest": "Wild Pokemon nest here.",
    "habitat": "Something old watches from the far side. Send a Pokemon out at it to fight.",
    "healer": "Ring the bell on the counter to heal your party.",
    "healed": "The lamps steady. Your party is whole.",
    "healed_out": "The bell is quiet. It has rung for you already.",
    "nothing": "Nothing stirs here.",
    "ambush_hit": "Ambush!",
    "tired": "The trainer waits.",
}


def dim_of(doc):
    return doc["engine"]["pocket"]["dimension"]


def upper_cap(b):
    return max(b["caps"])


def lower_cap(b):
    return min(b["caps"])


def room_tag(room):
    return "dg.r.%s" % room_slug(room)


def slot_tag(g):
    return "dg.s%d" % g


def wild_sel(g, room):
    return "@e[type=cobblemon:pokemon,tag=%s,tag=%s]" % (slot_tag(g), room_tag(room))


def hold(slot, room, suffix=""):
    return R.state_holder(slot, room) + suffix


def keep_tag(doc):
    return doc["engine"]["sweep"]["keep_tag"]


# ------------------------------------------------------------------------------------------------- rotation (PRIZE-POOLS)
# The owner (2026-10-11): "a lot of variety". A trainer's `team_pool_by_band` {band: [team, ...]} or a miniboss's
# `species_pool_by_band` {band: [species, ...]} is the band's pool, replacing `team_by_band` / `species_by_band` for that
# band. ONE index a room per run is rolled at the threshold (slot/s<g>/start, beside the prize's roll: the sigil is
# spent, so re-entering cannot re-roll for free) into the room's holder #s<g>r<i>x in dg.rs; member k of a pool of n
# is taken when ((index - 1) mod n) + 1 == k, so two trainers of one room with pools of different sizes still each get
# one. An unset or stray index falls to member 1 (rot_cond: `unless ... matches 2..N`), so exactly one line fires
# whatever the score holds and a room entered without a threshold (a playtest teleport) still spawns its fight.
ROT = "x"
POOL_MAX = 6


def team_pool(t, band):
    """[team] a trainer fields at `band`: its rotation pool, else its one team ([] when it names neither)."""
    tp = (t.get("team_pool_by_band") or {}).get(str(band))
    if tp:
        return list(tp)
    tb = (t.get("team_by_band") or {}).get(str(band))
    return [tb] if tb else []


def miniboss_pool(p, band):
    """[species] a miniboss can be at `band`: its rotation pool, else its one species."""
    sp = (p.get("species_pool_by_band") or {}).get(str(band))
    if sp:
        return list(sp)
    one = (p.get("species_by_band") or {}).get(str(band))
    return [one] if one else []


def rotation_size(doc, room, band):
    """N, the room's rotation index range at `band` (1: no rotation)."""
    kind, p = room.get("kind"), room.get("params") or {}
    if kind in KINDS_STAND and is_stand_room(room):
        return max([len(team_pool(t, band)) for t in trainers_of(doc, room)] + [1])
    if kind == "miniboss" and is_wild_room(room):
        return max(len(miniboss_pool(p, band)), 1)
    return 1


def rotates(doc, room):
    return any(rotation_size(doc, room, b["band"]) > 1 for b in DG.bands(doc))


def pick(n, v):
    """The 1-based pool member a room index `v` takes from a pool of `n`."""
    return (v - 1) % n + 1


def rot_holder(slot_g, room):
    return R.state_holder({"g": slot_g}, room) + ROT


def rot_cond(H, v, N):
    """The execute clause (with a trailing space) for index v of N: v 1 is the fallback for any other value."""
    if N <= 1:
        return ""
    if v == 1:
        return "unless score %s dg.rs matches 2..%d " % (H, N)
    return "if score %s dg.rs matches %d " % (H, v)


def rotation_start_lines(doc, slot):
    """slot/s<g>/start (as the member, at the threshold): the run's index for every rotating room of the slot."""
    d = slot["dungeon"]
    if not R.has_rooms(d):
        return []
    out = []
    for room in R.layout(doc, d, slot):
        if room["kind"] not in ROOM_KINDS or not rotates(doc, room):
            continue
        H = rot_holder(slot["g"], room)
        out += ["# room %s's rotation (PRIZE-POOLS): which pool member each of its fights is this run" % room["id"],
                "scoreboard players set %s dg.rs 1" % H]
        for b in DG.bands(doc):
            N = rotation_size(doc, room, b["band"])
            if N > 1:
                out.append("execute if score @s %s matches %d store result score %s dg.rs run random value 1..%d"
                           % (O("band"), b["band"], H, N))
    return out


def legend_labels(species):
    """The legendary/mythical/Ultra Beast labels the jar gives `species` (empty when not one, or no jar here)."""
    import dungeon_prize as DP       # lazy: dungeon_prize imports this module
    labels = DP.jar_labels()
    if labels is None:
        return set()
    return set(labels.get(species, ())) & DP.LEGEND_LABELS


def is_stand_room(room):
    """A real stand or gauntlet: trainers listed, or a pool. An int `trainers` is the kit's placeholder."""
    p = room.get("params") or {}
    return room["kind"] in KINDS_STAND and ("pool" in p or isinstance(p.get("trainers"), list))


def is_wild_room(room):
    p = room.get("params") or {}
    k = room["kind"]
    if k == "miniboss":
        return "species_by_band" in p or "species_pool_by_band" in p
    if k == "habitat":
        return "species" in p and "level_by_band" in p
    if k == "nest":
        return isinstance(p.get("species"), list) and "count_by_band" in p
    return False


def mode_of(room):
    return "stand" if room["kind"] == "stand" else "gauntlet"


def macro_args(**kw):
    return "{" + ",".join('%s:"%s"' % (k, v) for k, v in kw.items()) + "}"


def props_of(level, uncatchable, fixed, aspects=(), scale=None):
    """The PokemonProperties string of `spawnpokemonat`: keys the jar and the live ambient workers use (`level=`,
    `uncatchable`, `no_ai`, EXP-046), `aspect=` (docs/research/notes/habitat-nest-perching.md) and `scale_modifier=`
    (a string in PokemonProperties.class; its float semantics are unproven)."""
    parts = ["level=%d" % level] + ["aspect=%s" % a for a in aspects]
    if scale is not None:
        parts.append("scale_modifier=%s" % ("%g" % scale))
    if uncatchable:
        parts.append("uncatchable")
    if fixed:
        parts.append("no_ai")
    return " ".join(parts)


# ------------------------------------------------------------------------------------------------- the checks


def room_problems(doc, room):
    """Problems with a fight room's params (an int `trainers` or a missing species is the kit's placeholder: none)."""
    kind, p = room["kind"], room.get("params") or {}
    who = "room %s (%s)" % (room.get("id"), kind)
    bad = []
    bands = DG.bands(doc)
    b6 = [b for b in bands if b["band"] == 6]
    if kind in KINDS_STAND:
        if not is_stand_room(room):
            return []
        bad += stand_problems(doc, room)
        if bad:
            return bad
        n = len(trainers_of(doc, room))
        fr = p.get("triggers")
        if mode_of(room) == "gauntlet":
            if fr is not None:
                if not (isinstance(fr, list) and len(fr) == n and all(isinstance(f, (int, float)) and 0 < f < 1 for f in fr)):
                    bad.append("%s: triggers must be %d fractions strictly between 0 and 1" % (who, n))
                elif fr != sorted(fr):
                    bad.append("%s: triggers must be in increasing order" % who)
        elif fr is not None:
            bad.append("%s: `triggers` belongs to a gauntlet" % who)
        if bad:
            return bad
        plan = fight_plan(doc, room)
        for k, (x, _z) in enumerate(plan["trainers"], 1):
            if not (room["ix0"] + 4 <= x <= room["ix1"] - 3):
                bad.append("%s: trainer %d would stand at x %d, outside the room's %d..%d (shorten the stride or lengthen "
                           "the room)" % (who, k, x, room["ix0"] + 4, room["ix1"] - 3))
        if mode_of(room) == "gauntlet":
            for a, b in zip(plan["trips"], plan["trips"][1:]):
                if b - a < MIN_TRIGGER_GAP:
                    bad.append("%s: two triggers %d apart; a gauntlet's are at least %d" % (who, b - a, MIN_TRIGGER_GAP))
        else:
            xs = [x for x, _ in plan["trainers"]]
            for a, b in zip(xs, xs[1:]):
                if b - a < 4:
                    bad.append("%s: two trainers %d apart" % (who, b - a))
        return bad
    if kind == "miniboss":
        if not is_wild_room(room):
            return []
        sb = p.get("species_by_band") or {}
        spp = p.get("species_pool_by_band")
        if not isinstance(sb, dict) or spp is not None and (
                not isinstance(spp, dict) or any(not isinstance(v, list) or not 1 <= len(v) <= POOL_MAX
                                                 or len(set(map(str, v))) != len(v) for v in spp.values())):
            bad.append("%s: species_by_band is {band: species}; species_pool_by_band {band: [species, ...]}, 1..%d distinct a band"
                       % (who, POOL_MAX))
            return bad
        for k in sorted(set(sb) & set(spp or {})):
            bad.append("%s band %s: species_by_band and species_pool_by_band both name it (the pool is the band's species)" % (who, k))
        for b in bands:
            pool = miniboss_pool(p, b["band"])
            if not pool:
                bad.append("%s: species_by_band needs a lowercase species id for band %d" % (who, b["band"]))
            for sp in pool:
                if not isinstance(sp, str) or not PROP_ID.fullmatch(sp):
                    bad.append("%s: species_by_band needs a lowercase species id for band %d" % (who, b["band"]))
                elif p.get("catchable", True) and legend_labels(sp):
                    # a catchable miniboss carries no key tag: a legendary or Ultra Beast there is caught by any ball, at
                    # ordinary values, past the Beast Ball gate (the owner, 2026-10-10: a legendary is a dungeon's PRIZE)
                    bad.append("%s band %d: %s is %s; a catchable miniboss is never one (a legendary or Ultra Beast is a "
                               "habitat's prize, or a boss)" % (who, b["band"], sp, "/".join(sorted(legend_labels(sp)))))
        off = p.get("level_offset", 0)
        if not isinstance(off, int) or isinstance(off, bool) or off > 0:
            bad.append("%s: level_offset is an integer <= 0 (from the band's upper cap: never above it)" % who)
        else:
            for b in bands:
                if upper_cap(b) + off < 1:
                    bad.append("%s: band %d would be level %d" % (who, b["band"], upper_cap(b) + off))
            if b6 and upper_cap(b6[0]) + off < doc["engine"]["stands"]["band6_levels"][0]:
                bad.append("%s: a band-6 run is levels %d-%d; level_offset %d puts it at %d" % (
                    who, doc["engine"]["stands"]["band6_levels"][0], upper_cap(b6[0]), off, upper_cap(b6[0]) + off))
        bad += _common_wild(who, p)
    elif kind == "habitat":
        if not is_wild_room(room):
            return []
        if not isinstance(p["species"], str) or not PROP_ID.fullmatch(p["species"]):
            bad.append("%s: species is a lowercase species id" % who)
        lv = p["level_by_band"]
        for b in bands:
            v = lv.get(str(b["band"])) if isinstance(lv, dict) else None
            if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= upper_cap(b):
                bad.append("%s: level_by_band for band %d must be 1..%d (never above the band's upper cap)"
                           % (who, b["band"], upper_cap(b)))
        if "fight_only" in p and not isinstance(p["fight_only"], bool):
            bad.append("%s: fight_only is true or false" % who)
        for a in p.get("ambience", []):
            if not isinstance(a, str) or not SOUND_OR_PARTICLE.fullmatch(a):
                bad.append("%s: ambience entry %r is not a particle or sound id" % (who, a))
        bad += _common_wild(who, p)
    elif kind == "nest":
        if not is_wild_room(room):
            return []
        sp = p["species"]
        if not sp or any(not isinstance(x, str) or not PROP_ID.fullmatch(x) for x in sp):
            bad.append("%s: species is a non-empty list of lowercase species ids" % who)
        cb = p["count_by_band"]
        for b in bands:
            v = cb.get(str(b["band"])) if isinstance(cb, dict) else None
            if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 12:
                bad.append("%s: count_by_band for band %d must be 1..12" % (who, b["band"]))
        ls = p.get("level_spread", [0, 0])
        if not (isinstance(ls, list) and len(ls) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in ls)
                and 0 <= ls[0] <= ls[1]):
            bad.append("%s: level_spread is [lo, hi] offsets below the band's upper cap, 0 <= lo <= hi" % who)
        elif p.get("catchable", True):
            for b in bands:
                if upper_cap(b) - ls[0] > lower_cap(b):
                    bad.append("%s: a catchable nest at band %d would reach level %d, over the band's lower cap %d (the level "
                               "cap would refuse the ball)" % (who, b["band"], upper_cap(b) - ls[0], lower_cap(b)))
        if p.get("clear", "all") not in ("all", "pass"):
            bad.append("%s: clear is \"all\" or \"pass\"" % who)
        if "spawns" in p and not (isinstance(p["spawns"], int) and 1 <= p["spawns"] <= 24):
            bad.append("%s: spawns is 1..24" % who)
        bad += _common_wild(who, p)
    return bad


def _common_wild(who, p):
    bad = []
    if "catchable" in p and not isinstance(p["catchable"], bool):
        bad.append("%s: catchable is true or false" % who)
    for a in p.get("aspects", []):
        if not isinstance(a, str) or not PROP_ID.fullmatch(a):
            bad.append("%s: aspect %r is not a lowercase id" % (who, a))
    sc = p.get("scale")
    if sc is not None and not (isinstance(sc, (int, float)) and not isinstance(sc, bool) and 0.25 <= sc <= 4):
        bad.append("%s: scale is a number from 0.25 to 4" % who)
    return bad


def safe_problems(doc, room):
    p = room.get("params") or {}
    bad = []
    if "healer" in p and not isinstance(p["healer"], bool):
        bad.append("room %s: healer is true or false" % room.get("id"))
    if "uses" in p and not (isinstance(p["uses"], int) and not isinstance(p["uses"], bool) and 1 <= p["uses"] <= 9):
        bad.append("room %s: uses is 1..9" % room.get("id"))
    return bad


def fight_problems(doc, d, slot):
    """EXTRA_CHECKS: every fight room's params, plus an id used by no other room of the dungeon."""
    bad = []
    for room in R.layout(doc, d, slot):
        if room["kind"] in ROOM_KINDS:
            bad += ["%s: %s" % (d["id"], m) for m in room_problems(doc, room)]
        elif room["kind"] == "safe_room":
            bad += ["%s: %s" % (d["id"], m) for m in safe_problems(doc, room)]
    return bad


# ------------------------------------------------------------------------------------------------- stands and gauntlets


def fight_plan(doc, room):
    """The geometry of a stand or gauntlet, from the room's layout and params alone (the kind, the checks and the
    tests all read this): the trainers' (x, z), each trainer's trip x and, for a gauntlet, each barrier's x."""
    p = room.get("params") or {}
    n = len(trainers_of(doc, room))
    ix0, ix1, iz0, iz1 = room["ix0"], room["ix1"], room["iz0"], room["iz1"]
    L = ix1 - ix0 + 1
    zc = (iz0 + iz1) // 2
    off = max(2, (iz1 - iz0 + 1) // 4)

    def zk(k):
        if n == 1:
            return zc
        return min(max(zc + (off if k % 2 == 0 else -off), iz0 + 2), iz1 - 2)
    out = {"mode": mode_of(room), "n": n, "trainers": [], "trips": [], "barriers": [None] * n}
    if out["mode"] == "stand":
        sight = int(p.get("sight", SIGHT))
        for k in range(n):
            frac = 0.62 if n == 1 else 0.40 + 0.45 * k / (n - 1)
            x = ix0 + int(L * frac)
            out["trainers"].append((x, zk(k)))
            out["trips"].append(max(ix0 + 3, x - sight))
        return out
    fr = p.get("triggers")
    if fr is None:
        fr = [0.4] if n == 1 else [0.18 + 0.5 * k / (n - 1) for k in range(n)]
    for k in range(n):
        t = ix0 + int(L * fr[k])
        b = t + AMBUSH_GAP
        out["trips"].append(t)
        out["barriers"][k] = b
        out["trainers"].append((b + AMBUSH_STEP, zk(k)))
    return out


def _after(room, x):
    """The room's interior box from x east: the test `the member is at or past x`."""
    b = room["box"]
    return [x, b[1], b[2], b[3], b[4], b[5]]


def stand_show_functions(doc, d, room, n, slot_g, spot):
    """{name: lines} for trainer `n` standing visible before the fight (a stand, not an ambush), beside the functions
    stand_functions makes:

      stand/<key>/show   as the member, at the room's entry: the trainer's class for their band at the spot, bound, no battle
      stand/<key>/fight  as the member at the trainer's line: start the battle with the standing trainer (the same
                         pending tag, retries and go as `start`); no trainer standing: `start` spawns and fights"""
    classes = stand_classes(doc, d, room)
    s = stand_settings(doc)
    dim = dim_of(doc)
    key = stand_key(d, room, n, slot_g)
    x, y, z = spot
    keytag, pendtag = TAG_KEY + key, TAG_PEND + key
    base = "stand/%s" % key
    h = DG.HEAD
    npc_sel = "@e[type=cobblemon:npc,tag=%s,limit=1]" % keytag
    show = [h, "# As slot %d's member, the first pass in room %s: trainer %d stands at the spot (MACRO spawn, EXP-078), bound" % (
        slot_g, room["id"], n), "# at once; no battle until the member reaches the trainer's line (room tick -> fight)",
        "execute in %s run kill @e[type=cobblemon:npc,tag=%s]" % (dim, keytag)]
    for b in DG.bands(doc):
        for cond, k in stand_variants(doc, room, n, b["band"], slot_g):
            cname = stand_class_name(d, room, n, b["band"], k)
            show.append("execute if score @s %s matches %d %sin %s run function %s {x:\"%.1f\",y:\"%d\",z:\"%.1f\",cls:\"%s:%s\","
                        "level:\"%d\"}" % (O("band"), b["band"], cond, dim, F("npc_at"), x + 0.5, y, z + 0.5, DG.NS, cname,
                                           classes[cname][1]))
    show.append("execute in %s positioned %.1f %d %.1f as @e[type=cobblemon:npc,tag=!%s,distance=..1.5,sort=nearest,limit=1] "
                "run function %s" % (dim, x + 0.5, y, z + 0.5, DG.TAGS["npc"], F("%s/bind" % base)))
    fight = [h, "# As the member at trainer %d's line: the battle with the trainer who is standing there. They are bound already," % n,
             "# so this is the second half of `start` (bounds for the clawback, the pending tag, go_ticks later the battle)",
             "execute in %s unless entity %s run return run function %s" % (dim, npc_sel, F("%s/start" % base))]
    for b in DG.bands(doc):
        for cond, k in stand_variants(doc, room, n, b["band"], slot_g):
            fight.append("execute if score @s %s matches %d %srun function %s"
                         % (O("band"), b["band"], cond, F("claw/bounds/%s" % stand_class_name(d, room, n, b["band"], k))))
    fight += ["tag @s add %s" % pendtag,
              "scoreboard players set @s %s %d" % (TRIES, s["retries"]),
              "schedule function %s %dt append" % (F("%s/go" % base), s["go_ticks"])]
    return {base + "/show": show, base + "/fight": fight}


def kind_fight(doc, d, slot, room, theme):
    """A stand (trainers stand visible, fight at their lines) or a gauntlet/ambush (hidden; each steps out when the
    member crosses its trigger and a barrier holds the way until the fight is won)."""
    if not is_stand_room(room):
        return _placeholder(d, slot, room, "params.trainers is a count, not a list: the kit's placeholder")
    bad = room_problems(doc, room)
    if bad:
        raise R.RoomError("; ".join(bad))
    g = slot["g"]
    plan = fight_plan(doc, room)
    mode, n = plan["mode"], plan["n"]
    dim = dim_of(doc)
    gate = R.gate_block(theme)
    fy, ceil = room["floor_in"], room["ceil_y"]
    iz0, iz1 = room["iz0"], room["iz1"]
    b = room["box"]
    fn = lambda name: R.room_fn(d, room, slot, name)  # noqa: E731
    T = lambda k: hold(slot, room, "t%d" % k)  # noqa: E731
    rs = "dg.rs"
    key = lambda k: stand_key(d, room, k, g)  # noqa: E731
    trainers = [[x, fy, z, 90] for x, z in plan["trainers"]]
    anchors = {"trainers": trainers, "line": [plan["trips"][0], fy, iz0, plan["trips"][0], fy + 2, iz1]}
    reserve = []
    ops = []
    fn_ = {}
    # the barrier is 4 high (no jump clears 4; the reserve keeps dressing out of its columns) and fills AIR only: to the
    # ceiling and over every block, it overwrote the hull's lanterns and the canopy, and its removal left air for good
    # (DG-AUDIT finding 3)
    btop = min(fy + 3, ceil - 1)
    barrier_fill = lambda k: "fill %d %d %d %d %d %d %s replace minecraft:air" % (plan["barriers"][k - 1], fy, iz0, plan["barriers"][k - 1], btop, iz1, gate)  # noqa: E731
    barrier_off = lambda k: "fill %d %d %d %d %d %d minecraft:air replace %s" % (plan["barriers"][k - 1], fy, iz0, plan["barriers"][k - 1], btop, iz1, gate)  # noqa: E731
    if mode == "gauntlet":
        for k in range(1, n + 1):
            bx = plan["barriers"][k - 1]
            reserve.append((bx - 1, fy, iz0, bx + 1, fy + 1, iz1))
    tick = []
    # the forfeit watch: a fight pending while the member stands out of battle (a flee or a forfeit sends no result)
    for k in range(1, n + 1):
        tick.append("execute if score %s %s matches 1 run runmolang \"(q.player.in_battle == 0) ? { q.run_command('execute as ' "
                    "+ q.player.uuid + ' run function %s'); };\" @s" % (T(k), rs, fn("idle%d" % k)))
        fn_["idle%d" % k] = [
            DG.HEAD, "# As the member (queued by runmolang), out of battle with trainer %d's fight pending: after %d such passes" % (k, FORFEIT_PASSES),
            "# the trainer is offered again (state back to 0; the tick starts the fight at once while the member stands past the line)",
            "execute unless score %s %s matches 1 run return 0" % (T(k), rs),
            "scoreboard players add @s %s 1" % FI,
            "execute if score @s %s matches %d.. run scoreboard players set %s %s 0" % (FI, FORFEIT_PASSES, T(k), rs),
            "execute if score @s %s matches %d.. run scoreboard players set @s %s 0" % (FI, FORFEIT_PASSES, FI)]
    if mode == "gauntlet":
        # the barrier is a fence in the way, not a wall the member is trusted to respect: past it while it stands, back
        for k in range(1, n + 1):
            bx = plan["barriers"][k - 1]
            # into the column just before the barrier, at the floor: the reserve keeps that column clear of dressing, so
            # the put-back never lands inside a block (keeping the member's own y and z did: DG-AUDIT finding 4)
            tick.append("execute if score %s %s matches 1 if entity @s[%s] run tp @s %.1f %d ~"
                        % (T(k), rs, R.sel_box(_after(room, bx + 1)), bx - 0.5, fy))
    for k in range(1, n + 1):
        conds = ["if score %s %s matches 0" % (T(k), rs)] + ["if score %s %s matches 2" % (T(j), rs) for j in range(1, k)]
        tick.append("execute %s if entity @s[%s] run function %s" % (" ".join(conds), R.sel_box(_after(room, plan["trips"][k - 1])), fn("go%d" % k)))
        go = [DG.HEAD, R.LOADED, "# As the member who reached trainer %d's %s: the fight begins" % (k, "line" if mode == "stand" else "trigger"),
              "scoreboard players set %s %s 1" % (T(k), rs),
              "scoreboard players set @s %s 0" % FI]
        if mode == "stand":
            go.append("function %s" % F("stand/%s/fight" % key(k)))
        else:
            go += ["execute in %s run %s" % (dim, barrier_fill(k)),
                   "title @s actionbar %s" % DG.text(MSG["ambush_hit"], "dark_red"),
                   "playsound minecraft:entity.evoker.prepare_summon master @s ~ ~ ~ 1 0.8",
                   "function %s" % F("stand/%s/start" % key(k))]
        fn_["go%d" % k] = go
        won = [DG.HEAD, R.LOADED, "# As the winner of trainer %d (stand/dispatch, by the stand id on the NPC): this trainer is done" % k,
               "scoreboard players set %s %s 2" % (T(k), rs),
               "scoreboard players set @s %s 0" % FI]
        if mode == "gauntlet":
            won.append("execute in %s run %s" % (dim, barrier_off(k)))
        won += ["title @s actionbar %s" % DG.text("Trainer %d of %d beaten." % (k, n), "gray"),
                "execute %s run function %s" % (" ".join("if score %s %s matches 2" % (T(j), rs) for j in range(1, n + 1)), fn("clear"))]
        fn_["won%d" % k] = won
    enter = ["title @s actionbar %s" % DG.text(MSG["stand" if mode == "stand" else "ambush"], "gray")]
    if mode == "stand":
        enter += ["function %s" % F("stand/%s/show" % key(k)) for k in range(1, n + 1)]
    clear = ["scoreboard players set %s %s 2" % (T(k), rs) for k in range(1, n + 1)]
    if mode == "gauntlet":
        clear += ["execute in %s run %s" % (dim, barrier_off(k)) for k in range(1, n + 1)]
    cx, cz = (room["ix0"] + room["ix1"]) // 2, (iz0 + iz1) // 2
    reset = ["forceload add %d %d" % (cx, cz)]
    reset += ["scoreboard players set %s %s 0" % (T(k), rs) for k in range(1, n + 1)]
    reset += ["kill @e[type=cobblemon:npc,tag=%s]" % (TAG_KEY + key(k)) for k in range(1, n + 1)]
    if mode == "gauntlet":
        reset += [barrier_off(k) for k in range(1, n + 1)]
    return {"anchors": anchors, "reserve": reserve, "blocks": ops,
            "functions": dict(fn_, enter=enter, tick=tick, clear=clear, reset=reset),
            "meta": {"fight_plan": plan, "stand": True, "assumed": "the battle starts, the callback and the clawback: DG-CLAW's "
                     "(C1, EXP-060 unrun); a fight's forfeit is detected by q.player.in_battle, as the boss's"}}


def _placeholder(d, slot, room, why):
    """The kit's declared-kind behaviour kept exactly: a themed room with its default anchors and nothing else (warnings()
    names it). A `gate: cleared` placeholder therefore stays shut, as it did before the kind existed; a real dungeon
    writes real params and never meets this."""
    return {"meta": {"placeholder": why}}


# ------------------------------------------------------------------------------------------------- wild rooms


def _pos4(a):
    a = tuple(a)
    return a + (0,) * (4 - len(a))


def wild_spawns(doc, room, anchors, variant=1):
    """{band: [(species, level, props, (x, y, z, yaw))]} for a miniboss, nest or habitat room. `variant` is the room's
    rotation index: a miniboss takes member pick(len(pool), variant) of the band's species pool."""
    p = room.get("params") or {}
    kind = room["kind"]
    out = {}
    for b in DG.bands(doc):
        bn, up = b["band"], upper_cap(b)
        if kind == "miniboss":
            lv = up + int(p.get("level_offset", 0))
            # catchable at every band unless the record says not (the owner, 2026-10-10: every dungeon Pokemon is
            # catchable). The level cap still refuses a ball at a level over the thrower's cap (data/level_cap.json)
            unc = not p.get("catchable", True)
            a = anchors["boss"]
            pool = miniboss_pool(p, bn)
            out[bn] = [(pool[pick(len(pool), variant) - 1], lv, props_of(lv, unc, True, p.get("aspects", ()), p.get("scale")),
                        _pos4(a))]
        elif kind == "habitat":
            lv = int(p["level_by_band"][str(bn)])
            # a legendary or Ultra Beast is a dungeon's prize (the owner, 2026-10-10): catchable from the Beast Ball stage
            # (engine.prize.legendary_from_band) unless the record is fight_only. Below it the habitat's Pokemon stays
            # uncatchable: pass 3 puts a rare non-legendary there instead
            unc = bool(p.get("fight_only", False)) or bn < int(doc["engine"]["prize"]["legendary_from_band"])
            a = anchors["legendary"]
            out[bn] = [(p["species"], lv, props_of(lv, unc, True, p.get("aspects", ()), p.get("scale")), _pos4(a))]
        else:
            lo, hi = p.get("level_spread", [0, 0])
            spawns = anchors["spawns"]
            lst = []
            for j in range(int(p["count_by_band"][str(bn)])):
                lv = max(1, up - (lo + (j * 7) % (hi - lo + 1)))
                if bn == 6:
                    lv = max(lv, doc["engine"]["stands"]["band6_levels"][0])     # a band-6 run is levels 95-100
                sp = p["species"][j % len(p["species"])]
                lst.append((sp, lv, props_of(lv, not p.get("catchable", True), False, p.get("aspects", ()), p.get("scale")),
                            _pos4(spawns[j % len(spawns)])))
            out[bn] = lst
    return out


def presence_lines(W, sel, clear_fn, fail_fn):
    """The tick's state machine for a wild room (holder W in dg.rs): see the module comment."""
    rs = "dg.rs"
    return [
        "execute if score %s %s matches %d.. run return 0" % (W, rs, HOLD_DONE),
        "execute if entity %s run scoreboard players set %s %s %d" % (sel, W, rs, HOLD_SEEN),
        "execute if entity %s run return 0" % sel,
        "execute if score %s %s matches %d run return run function %s" % (W, rs, HOLD_GONE, clear_fn),
        "execute if score %s %s matches %d run return run scoreboard players set %s %s %d" % (W, rs, HOLD_SEEN, W, rs, HOLD_GONE),
        "scoreboard players add %s %s 1" % (W, rs),
        "execute if score %s %s matches %d run function %s" % (W, rs, NEVER_SEEN_PASSES, fail_fn)]


def kind_wild(doc, d, slot, room, theme):
    p = room.get("params") or {}
    kind = room["kind"]
    if not is_wild_room(room):
        return _placeholder(d, slot, room, "no species in params: the kit's placeholder")
    bad = room_problems(doc, room)
    if bad:
        raise R.RoomError("; ".join(bad))
    g = slot["g"]
    dim = dim_of(doc)
    kp = keep_tag(doc)
    rs = "dg.rs"
    fn = lambda name: R.room_fn(d, room, slot, name)  # noqa: E731
    W, V = hold(slot, room, "w"), hold(slot, room, "v")
    sel = wild_sel(g, room)
    anchors = {}
    params = dict(p)
    if kind == "nest":
        n_anch = int(p.get("spawns", max(int(v) for v in p["count_by_band"].values())))
        params["spawns"] = max(n_anch, 1)
        anchors["spawns"] = R.default_anchors(room, params)["spawns"]
        defaults = {"spawns": anchors["spawns"]}
    else:
        defaults = R.default_anchors(room, params)
    spawns = wild_spawns(doc, room, defaults)
    fixed = kind != "nest"
    fn_ = {}
    # the room's bind: as the new Pokemon
    bind = [DG.HEAD, "# As the Pokemon the room has just spawned: the slot's claim (tags, exempt, run, persistence), then the room's",
            "function %s" % F("wild/s%d/bind" % g), "tag @s add %s" % room_tag(room)]
    if fixed:
        sx, sy, sz, yaw = next(iter(spawns.values()))[0][3]
        bind += ["data merge entity @s {NoAI:1b}", "tp @s %.1f %d %.1f %d 0" % (sx + 0.5, sy, sz + 0.5, yaw)]
    fn_["bind"] = bind
    # one spawn function per band (per band and pool member for a rotating miniboss: spawn_b<b> is member 1)
    by_variant = {1: spawns}
    if kind == "miniboss":
        for k in range(2, max(len(miniboss_pool(p, b["band"])) for b in DG.bands(doc)) + 1):
            by_variant[k] = wild_spawns(doc, room, defaults, k)

    def spawn_name(bn, k):
        return "spawn_b%d" % bn if k == 1 else "spawn_b%d_v%d" % (bn, k)
    enter_spawn = []
    for bn in spawns:
        size = len(miniboss_pool(p, bn)) if kind == "miniboss" else 1
        for k in range(1, size + 1):
            lines = [DG.HEAD, "# As the member, the room's first pass: band %d's Pokemon%s, spawned by the MACRO wild_at (EXP-046: a plain"
                     % (bn, "" if size == 1 else " (pool member %d of %d)" % (k, size)),
                     "# spawnpokemonat parsed at boot does nothing), each bound the same function (an unclaimed one is despawned)"]
            for sp, lv, props, (x, y, z, _yaw) in by_variant[k][bn]:
                lines.append("execute in %s run function %s %s" % (dim, F("wild_at"), macro_args(
                    x="%.1f" % (x + 0.5), y=str(y), z="%.1f" % (z + 0.5), species=sp, props=props)))
                lines.append("execute in %s positioned %.1f %d %.1f as @e[type=cobblemon:pokemon,tag=!%s,distance=..%g,sort=nearest,limit=1] "
                             "run function %s" % (dim, x + 0.5, y, z + 0.5, kp, BIND_RADIUS, fn("bind")))
            fn_[spawn_name(bn, k)] = lines
        N = rotation_size(doc, room, bn)
        for v in range(1, N + 1):
            cond = rot_cond(hold(slot, room, ROT), v, N) if size > 1 else ""
            enter_spawn.append("execute if score @s %s matches %d %srun function %s" % (O("band"), bn, cond, fn(spawn_name(bn, pick(size, v)))))
            if size == 1:
                break
    enter = ["title @s actionbar %s" % DG.text(MSG[kind], "gray"),
             "scoreboard players set %s %s 0" % (W, rs), "scoreboard players set %s %s 0" % (V, rs)]
    enter += enter_spawn
    pass_mode = kind == "nest" and p.get("clear", "all") == "pass"
    if pass_mode:
        enter.append("function %s" % fn("clear"))
    tick = []
    if kind == "nest":
        cx, cz = (room["ix0"] + room["ix1"]) // 2, (room["iz0"] + room["iz1"]) // 2
        tick.append("execute as %s unless entity @s[%s] run tp @s %.1f %d %.1f" % (sel, R.sel_box(room["box"]), cx + 0.5, room["floor_in"], cz + 0.5))
    if kind == "habitat":
        vx, vy, vz = defaults["viewpoint"][:3]
        title = p.get("title") or "A %s." % p["species"].replace("_", " ").title()
        tick.append("execute if score %s %s matches 0 if entity @s[x=%d,y=%d,z=%d,distance=..4] run function %s"
                    % (V, rs, vx, vy, vz, fn("view")))
        fn_["view"] = [DG.HEAD, "# As the member who has reached the viewpoint: the creature, once",
                       "scoreboard players set %s %s 1" % (V, rs),
                       "title @s title %s" % DG.text(title, "light_purple"),
                       "title @s subtitle %s" % DG.text(p.get("subtitle", "It has not noticed you yet."), "gray")]
        lx, ly, lz = defaults["legendary"][:3]
        for a in p.get("ambience", []):
            if "." in a.split(":")[-1]:
                tick.append("execute positioned %.1f %d %.1f run playsound %s ambient @s ~ ~ ~ 0.6 1" % (lx + 0.5, ly, lz + 0.5, a))
            else:
                tick.append("execute positioned %.1f %d %.1f run particle %s ~ ~1 ~ 1.5 1.5 1.5 0.02 6" % (lx + 0.5, ly, lz + 0.5, a))
    if not pass_mode:
        # only a room whose door waits on its Pokemon watches for them: a "pass" nest's door is open already, and its
        # fallback would be a function no step or pack calls (prepare's orphan check, 2026-10-09)
        tick += presence_lines(W, sel, fn("clear"), fn("nothing"))
        fn_["nothing"] = [DG.HEAD, R.LOADED, "# The room's Pokemon never appeared (a failed spawn): open anyway, say so. A bad species id",
                          "# must not trap a player",
                          "title @s actionbar %s" % DG.text(MSG["nothing"], "gray"),
                          "function %s" % fn("clear")]
    clear = ["scoreboard players set %s %s %d" % (W, rs, HOLD_DONE)]
    cx, cz = (room["ix0"] + room["ix1"]) // 2, (room["iz0"] + room["iz1"]) // 2
    reset = ["forceload add %d %d" % (cx, cz),
             "execute as %s run runmolang \"q.entity.discard;\"" % sel,
             "scoreboard players set %s %s 0" % (W, rs), "scoreboard players set %s %s 0" % (V, rs)]
    res = {"functions": dict(fn_, enter=enter, tick=tick, clear=clear, reset=reset),
           "meta": {"wild": True, "spawns": {bn: [(s, lv, pr) for s, lv, pr, _ in lst] for bn, lst in spawns.items()},
                    "pools": {bn: (miniboss_pool(p, bn) if kind == "miniboss" else [lst[0][0]] if lst else []) for bn, lst in spawns.items()},
                    "assumed": "a fainted, caught or despawned wild Pokemon's entity is gone (the gulch Megas' and residents' rule); "
                               "spawnpokemonat props level/aspect/scale_modifier/uncatchable/no_ai"}}
    if kind == "nest":
        res["anchors"] = anchors
    return res


# ------------------------------------------------------------------------------------------------- the healer


def _wrap_safe_room():
    """The kit's `safe_room` (tools/dungeon_kinds.py) gains a healer when params.healer is true: a vanilla bell on the
    counter (any_block_use in the pocket) and the blackout's own `healpokemon @s`. NOT a cobblemon:healing_machine: its
    use fires the blackout's checkpoint advancement (tools/blackout_pack.py healer_use), which would make a point in a
    slot the player's respawn (DUNGEON_3_PATRIARCH.md 5.1 item 5)."""
    import dungeon_kinds  # noqa: F401  (registers safe_room)
    base = R.KINDS.get("safe_room")
    if base is None or getattr(base, "_dg_fights", False):
        return
    flags = dict(R.FLAGS["safe_room"])

    def kind_safe_healer(doc, d, slot, room, theme):
        res = base(doc, d, slot, room, theme)
        p = room.get("params") or {}
        if not p.get("healer"):
            return res
        bad = safe_problems(doc, room)
        if bad:
            raise R.RoomError("; ".join(bad))
        fy = room["floor_in"]
        zc = (room["iz0"] + room["iz1"]) // 2
        cx = (room["ix0"] + room["ix1"]) // 2
        hz = room["iz0"] + 1
        bell = (cx, fy + 1, hz + 1)
        res = dict(res)
        res["blocks"] = list(res.get("blocks", [])) + [setb(bell, "minecraft:bell[attachment=floor,facing=north]")]
        H = hold(slot, room, "h")
        uses = int(p.get("uses", 1))
        fn = lambda name: R.room_fn(d, room, slot, name)  # noqa: E731
        fns = {k: list(v) for k, v in res.get("functions", {}).items()}
        fns["enter"] = fns.get("enter", []) + ["title @s actionbar %s" % DG.text(MSG["healer"], "gold")]
        fns["reset"] = fns.get("reset", []) + ["scoreboard players set %s dg.rs 0" % H]
        fns["heal"] = [DG.HEAD, R.LOADED, "# As the member who rang this room's bell (healer/use): a heal if one is left and they are not in battle",
                       "execute if score %s dg.rs matches %d.. run return run title @s actionbar %s" % (H, uses, DG.text(MSG["healed_out"], "gray")),
                       "runmolang \"(q.player.in_battle == 0) ? { q.run_command('execute as ' + q.player.uuid + ' run function %s'); };\" @s"
                       % fn("heal_do")]
        fns["heal_do"] = [DG.HEAD, "# As the member (queued by runmolang), out of battle: the party healed, once more used",
                          "scoreboard players add %s dg.rs 1" % H,
                          "healpokemon @s",
                          "particle minecraft:happy_villager ~ ~1 ~ 0.5 0.5 0.5 0.1 14",
                          "playsound minecraft:block.bell.use master @s ~ ~ ~ 1 1",
                          "title @s actionbar %s" % DG.text(MSG["healed"], "gold")]
        res["functions"] = fns
        meta = dict(res.get("meta", {}))
        meta["healer"] = {"uses": uses, "bell": list(bell),
                          "assumed": "any_block_use fires for a bell in adventure mode; healpokemon heals PP and status in the pocket (SP1)"}
        res["meta"] = meta
        return res
    kind_safe_healer._dg_fights = True
    R.register("safe_room", kind_safe_healer, **flags)


def healer_rooms(doc):
    return [(d, slot, b) for d, slot, b in fight_rooms(doc) if b.room["kind"] == "safe_room" and (b.room.get("params") or {}).get("healer")]


def healer_advancement(doc):
    return {"criteria": {"use": {"trigger": "minecraft:any_block_use", "conditions": {"location": [
        {"condition": "minecraft:location_check",
         "predicate": {"block": {"blocks": "minecraft:bell"}, "dimension": dim_of(doc)}}]}}},
            "rewards": {"function": F("healer/use")}}


def healer_use(doc):
    lines = [DG.HEAD, "# As a player who used a bell in the pocket (cobblers:dungeons/healer advancement): re-armed, then the room's",
             "# heal if they are a member with the clock running and stand in a healer room of their slot",
             "advancement revoke @s only %s:dungeons/healer" % DG.NS,
             "execute unless score @s %s matches 3 run return 0" % O("st")]
    for d, slot, b in healer_rooms(doc):
        lines.append("execute if score @s %s matches %d if entity @s[%s] run function %s"
                     % (O("slot"), slot["g"], R.sel_box(b.room["box"]), R.room_fn(d, b.room, slot, "heal")))
    return lines


# ------------------------------------------------------------------------------------------------- the pack


def fight_rooms(doc):
    """[(dungeon, slot, Built)] for every room of every dungeon built by the room kit (all four slots of each)."""
    out = []
    for slot in DG.slots(doc):
        d = slot["dungeon"]
        if R.has_rooms(d):
            for b in R.slot_build(doc, d, slot):
                out.append((d, slot, b))
    return out


def stand_ids(doc):
    """{(dungeon id, room id, slot g, trainer n): stand id}, in the pack's order, for every real stand and gauntlet."""
    out, sid = {}, SID_BASE
    for d, slot, b in fight_rooms(doc):
        if b.room["kind"] in KINDS_STAND and b.meta.get("stand"):
            for n in range(1, len(b.anchors["trainers"]) + 1):
                sid += 1
                out[(d["id"], b.room["id"], slot["g"], n)] = sid
    return out


def room_dispatch(doc):
    """[(stand id, the room's won<n> function)] for stand_dispatch: a won stand opens the room's clear."""
    ids = stand_ids(doc)
    out = []
    for d, slot, b in fight_rooms(doc):
        if b.room["kind"] in KINDS_STAND and b.meta.get("stand"):
            for n in range(1, len(b.anchors["trainers"]) + 1):
                out.append((ids[(d["id"], b.room["id"], slot["g"], n)], R.room_fn(d, b.room, slot, "won%d" % n)))
    return out


def room_functions(doc, mult=None):
    """Everything the fight rooms need under cobblers:dungeons/ besides their own room functions: the stands' spawn and
    battle functions, the wild Pokemon's macro and per-slot bind, the healer's click."""
    out = {}
    ids = stand_ids(doc)
    wild_slots = set()
    for d, slot, b in fight_rooms(doc):
        room, g = b.room, slot["g"]
        if room["kind"] in KINDS_STAND and b.meta.get("stand"):
            for n, a in enumerate(b.anchors["trainers"], 1):
                spot = (a[0], a[1], a[2])
                out.update(stand_functions(doc, d, room, n, g, spot, ids[(d["id"], room["id"], g, n)], mult))
                if room["kind"] == "stand":
                    out.update(stand_show_functions(doc, d, room, n, g, spot))
        elif room["kind"] in KINDS_WILD and b.meta.get("wild"):
            wild_slots.add(g)
    if wild_slots:
        out["wild_at"] = ["# the macro spawn of a wild Pokemon (EXP-046: a plain `spawnpokemonat` parsed at boot does nothing); run `in` the",
                          "# pocket by the room's spawn function, which binds the result in the same function",
                          "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]
        exempt = DG.blackout_terms()["exempt"]
        for g in sorted(wild_slots):
            out["wild/s%d/bind" % g] = [
                DG.HEAD, "# As a wild Pokemon a room of slot %d has just spawned: kept from the sweep (the recall sweep removes untagged" % g,
                "# ones in a no-deploy box), the slot's, the blackout's exempt tag (a dungeon Pokemon claims nothing: DUNGEONS.md 2.5),",
                "# this run's, and kept from the despawner (EXP-041)",
                "tag @s add %s" % keep_tag(doc), "tag @s add %s" % slot_tag(g), "tag @s add %s" % exempt,
                "scoreboard players operation @s %s = #s%d %s" % (O("run"), g, O("run")),
                "data merge entity @s {PersistenceRequired:1b}"]
    if healer_rooms(doc):
        out["healer/use"] = healer_use(doc)
    return out


def pack_files(doc):
    """{path: text} the fight rooms add to the datapack beside their functions: the stands' NPC classes and the healer's
    advancement."""
    import json
    files = {}
    for d, slot, b in fight_rooms(doc):
        if b.room["kind"] in KINDS_STAND and b.meta.get("stand"):
            files.update(stand_files(doc, d, b.room))
    if healer_rooms(doc):
        files["data/%s/advancement/dungeons/healer.json" % DG.NS] = json.dumps(healer_advancement(doc), indent=2) + "\n"
    return files


def patch_functions(doc, fns):
    """Edits to the engine's per-slot functions (tools/dungeon.py build() calls this): a run that ends discards the slot's
    wild Pokemon (the free function kills its NPCs the same way), and the keeper's pass discards one left by an earlier run
    of the slot (a chunk that was unloaded when the run ended; the bind stamped its run id)."""
    dim = dim_of(doc)
    for d, slot, b in fight_rooms(doc):
        if b.meta.get("wild") and b.room["kind"] in KINDS_WILD:
            g = slot["g"]
            line_free = "execute in %s as @e[type=cobblemon:pokemon,tag=%s] run runmolang \"q.entity.discard;\"" % (dim, slot_tag(g))
            line_tend = ("execute in %s as @e[type=cobblemon:pokemon,tag=%s] unless score @s %s = #s%d %s run runmolang "
                         "\"q.entity.discard;\"" % (dim, slot_tag(g), O("run"), g, O("run")))
            for name, line in (("slot/s%d/free" % g, line_free), ("slot/s%d/tend" % g, line_tend)):
                if line not in fns[name]:
                    fns[name].append(line)
    # the rotation's roll at each slot's threshold (PRIZE-POOLS): the rooms', then the boss's crew list
    for slot in DG.slots(doc):
        st = rotation_start_lines(doc, slot) + DG.boss_start_lines(doc, slot["dungeon"])
        if st:
            name = "slot/s%d/start" % slot["g"]
            fns[name] = list(fns[name]) + st


def warnings(doc):
    """Fight rooms that build as the kit's placeholders (an int `trainers`, no species): themed, empty, cleared on entry."""
    out, seen = [], set()
    for d, slot, b in fight_rooms(doc):
        why = b.meta.get("placeholder")
        if why and (d["id"], b.room["id"]) not in seen:
            seen.add((d["id"], b.room["id"]))
            out.append("%s room %s (%s) is a placeholder: %s" % (d["id"], b.room["id"], b.room["kind"], why))
    return out


def register_kinds():
    if __name__ != "dungeon_fights":
        return       # a mutant copy exec'd by a test (tests/test_dungeon_fights.py mutated()) must not take the kinds over
    for k in KINDS_STAND:
        R.register(k, kind_fight, dress="full")
    for k in KINDS_WILD:
        R.register(k, kind_wild, dress="full")
    _wrap_safe_room()
    if fight_problems not in R.EXTRA_CHECKS:
        R.EXTRA_CHECKS.append(fight_problems)


register_kinds()


# ------------------------------------------------------------------------------------------------- the pack, whole


def functions(doc, dispatch=None, mult=None):
    """Everything tools/dungeon.py build() adds from here: {function name under cobblers:dungeons/: lines}. `dispatch`
    defaults to the rooms' own (room_dispatch): a won stand opens its room's clear."""
    out = claw_functions()
    out.update(boss_functions(doc, mult))
    out.update(room_functions(doc, mult))
    out.update(stand_dispatch(room_dispatch(doc) if dispatch is None else dispatch))
    return out


def load_entries():
    """Function ids appended to load.json after dungeons/load (which creates dg.t and dg.claw)."""
    return [F("claw/init")]


def tick_entries():
    return [F("claw/tick")]
