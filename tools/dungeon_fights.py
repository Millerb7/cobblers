#!/usr/bin/env python
"""The dungeon's NPC fights: the CobbleDollars clawback, and the trainer classes and battle start for stands.

Unit DG-CLAW (2026-10-09). A module of its own so the room framework (tools/dungeon.py's geometry) and this merge
cleanly; tools/dungeon.py reaches it through three hooks and nothing else (lazy imports there, because this module
imports tools/dungeon.py):

  build()      DF.functions(doc), DF.pack_files(doc)   the claw/ and stand/ functions, tick.json, the load entry
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

STANDS (wave 2 seats them; this module generates what they need). From a room's `params` -- `trainers`: a list of
{name, skin?, team_by_band: {band: [species...]}}, or `pool`: an id in data/dungeons.json engine.stands.pools -- one
NPC class per trainer per band (stand_classes), levels per engine.stands, and per (trainer, slot) the functions that
spawn the class by macro, start the battle a few ticks later and retry a refusal (stand_functions). The callback tells
a stand's win by the tag dg.stand and the stand's id (dg.sid, set on the NPC and copied to the winner): stand/won runs
stand/dispatch, which wave 2 builds with stand_dispatch([(sid, clear_function_id), ...]) so a won stand opens the
room's `clear`.

Nothing here has run in a server. The offline model is tests/test_dungeon_fights.py.
"""
from __future__ import annotations

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
OBJECTIVES = [BAL, CMAX, CMIN, SID, TRIES]
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
            m = re.fullmatch(r"dg_%s_boss_b(\d+)_s(\d+)" % re.escape(d["short"]), name)
            lines.append("execute if score @s %s matches %s if score @s %s matches %s run function %s"
                         % (O("band"), m.group(1), O("stage"), m.group(2), F("claw/bounds/%s" % name)))
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
        for b in DG.bands(doc):
            team = tb.get(str(b["band"]))
            want = s["members_by_band"][str(b["band"])]
            if not team:
                bad.append("%s: no team for band %d" % (who, b["band"]))
            elif len(team) != want:
                bad.append("%s band %d: %d members, DUNGEONS.md 5.3 says %d" % (who, b["band"], len(team), want))
            elif any(not isinstance(x, str) or not SPECIES.fullmatch(x) for x in team):
                bad.append("%s band %d: a species is not a lowercase id" % (who, b["band"]))
        if set(tb) - {str(b["band"]) for b in DG.bands(doc)}:
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


def stand_class_name(d, room, n, band):
    return "dg_%s_st_%s_t%d_b%d" % (d["short"], room_slug(room), n, band)


def stand_classes(doc, d, room):
    """{class name: (class json, the ace's level)} -- one class per trainer per band for the room's stand."""
    bad = stand_problems(doc, room)
    if bad:
        raise FightError("; ".join(bad))
    s = stand_settings(doc)
    out = {}
    for n, t in enumerate(trainers_of(doc, room), 1):
        for b in DG.bands(doc):
            team = t["team_by_band"][str(b["band"])]
            lv = stand_levels(doc, b, len(team))
            out[stand_class_name(d, room, n, b["band"])] = (
                npc_class(t["name"], t.get("skin") or DG.NPC_RESOURCE, s["skill"],
                          ["%s level=%d" % (sp, lv[i]) for i, sp in enumerate(team)]), lv[-1])
    return out


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
        cname = stand_class_name(d, room, n, b["band"])
        start.append("execute if score @s %s matches %d in %s run function %s {x:\"%.1f\",y:\"%d\",z:\"%.1f\",cls:\"%s:%s\","
                     "level:\"%d\"}" % (O("band"), b["band"], dim, F("npc_at"), x + 0.5, y, z + 0.5, DG.NS, cname,
                                        classes[cname][1]))
        start.append("execute if score @s %s matches %d run function %s" % (O("band"), b["band"],
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


# ------------------------------------------------------------------------------------------------- the pack


def functions(doc, dispatch=(), mult=None):
    """Everything tools/dungeon.py build() adds from here: {function name under cobblers:dungeons/: lines}."""
    out = claw_functions()
    out.update(boss_functions(doc, mult))
    out.update(stand_dispatch(dispatch))
    return out


def load_entries():
    """Function ids appended to load.json after dungeons/load (which creates dg.t and dg.claw)."""
    return [F("claw/init")]


def tick_entries():
    return [F("claw/tick")]
