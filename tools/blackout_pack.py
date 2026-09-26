#!/usr/bin/env python
"""Blackout, recovery claims and the water ladder as one datapack (docs/mechanics/DEATH_AND_WIPE.md, ADR-005).

  python tools/blackout_pack.py [--out build/datapacks/cobblers_blackout]

Inputs, all authored data: data/blackout.json (the rules' numbers, checkpoint ids, claim categories, messages),
data/water_mounts.json (EXP-038's Surf and Dive riders), data/placements.json (the Pokemon Centers) and
data/progression.json (the town waystones).

What the pack does, and what each part rests on:

  blackout     A death (vanilla deathCount, charged the tick it happens) and a full-party battle loss (Cobblemon's
               battle_victory callback, EXP-039) run one pipeline: a 10% CobbleDollars charge (EXP-040's query, and a
               macro remove), then on the next living tick a teleport to the player's checkpoint, a party heal and
               the result message. A second report of the same incident within dedupe_ticks is dropped.
  checkpoints  A Center becomes the checkpoint when the player uses its healing machine (vanilla any_block_use on
               cobblemon:healing_machine); a town waystone when the player lands next to it after a jump (travel,
               not proximity). The saved point is where the player stood; it is re-validated against the data at
               every use and falls back to Hometown. The checkpoint is also the player's spawnpoint.
  claims       Only a battle lost to a wild Pokemon takes items (spec rule 5): the category quotas across the whole
               inventory, written to the claim ledger (storage cobblers:recovery) before anything is removed. The
               victor becomes the guardian: vanilla PersistenceRequired (EXP-041), a tag and a guardian number.
               Beating or catching it delivers every stack to the claim's owner as owner-only item entities at
               their feet, or on their next login. A guardian that is gone while its site is loaded, twice running,
               is rebuilt from the ledger's snapshot (a placeholder from spawnpokemonat with the snapshot written
               over its Pokemon data, tested on staging 2026-09-26). Trainer (NPC) losses take no items yet: they
               bind to the route trainers, which are not built.
  water        Eyes at least deep_blocks under water is depth. There, with no qualifying partner: vanilla air, then
               a drown hit of half maximum health every pulse_ticks. Surf training plus a Surf- or Dive-capable
               party member: water breathing for surf_bonus_ticks per submersion, then vanilla. Dive training plus
               a Dive-capable member: water breathing while it lasts. The party is read by a player_tick_pre MoLang
               callback every second (EXP-038).

Nothing here is proven in game until experiments/EXP-042-blackout-and-water-ladder says so.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_blackout"
NS = "cobblers"

# every scoreboard objective the pack owns; one prefix, so nothing collides with the other packs
OBJECTIVES = {
    "bo.deaths": "deathCount", "bo.leave": "minecraft.custom:minecraft.leave_game",
    "bo.cfg": "dummy", "bo.tmp": "dummy",
    "bo.cp": "dummy", "bo.cpx": "dummy", "bo.cpy": "dummy", "bo.cpz": "dummy", "bo.ok": "dummy",
    "bo.last": "dummy", "bo.bal": "dummy", "bo.lost": "dummy", "bo.clm": "dummy",
    "bo.nb": "dummy", "bo.nm": "dummy", "bo.nc": "dummy", "bo.tb": "dummy", "bo.tm": "dummy", "bo.tc": "dummy",
    "bo.mb": "dummy", "bo.mm": "dummy", "bo.mc": "dummy",
    "bo.px": "dummy", "bo.pz": "dummy", "bo.ox": "dummy", "bo.oz": "dummy",
    "bo.mount": "dummy", "bo.raw": "dummy", "bo.qual": "dummy", "bo.grace": "dummy",
    "bo.deep": "dummy", "bo.sub": "dummy", "bo.air": "dummy", "bo.surf": "dummy", "bo.breath": "dummy",
    "bo.pulse": "dummy", "bo.warn": "dummy", "bo.mh": "dummy", "bo.g": "dummy",
}

# the inventory slots a claim may take from: the hotbar and main inventory, and the offhand. Armour never.
SLOTS = [("container.%d" % i, i) for i in range(36)] + [("weapon.offhand", -106)]


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def text(s, color="gray"):
    return json.dumps({"text": s, "color": color}, ensure_ascii=False)


def checkpoints(cfg, placements, progression):
    """[(id, kind, name, anchor x, anchor y or None, anchor z, radius)] for every Center and town waystone."""
    ids = cfg["checkpoints"]["ids"]
    towns = {t["id"]: t for t in load("towns.json").get("towns", [])} if (ROOT / "data" / "towns.json").is_file() else {}

    def town_name(tid):
        w = (towns.get(tid) or {}).get("working_name") or tid
        return w.split(" (")[0]

    out = []
    for q in placements["placements"]:
        if q.get("kind") == "service" and q["id"].endswith("_pokecenter"):
            if q["id"] not in ids:
                raise SystemExit("Center %s has no checkpoint id in data/blackout.json checkpoints.ids" % q["id"])
            p = q["position"]
            out.append((ids[q["id"]], "center", "the %s Pokemon Center" % town_name(q["settlement"]),
                        p["x"], None, p["z"], cfg["checkpoints"]["center_radius"]))
    for f in progression.get("flags", []):
        w = f.get("waystone")
        if not w:
            continue
        key = "waystone_%s" % w["town"]
        if key not in ids:
            raise SystemExit("waystone %s has no checkpoint id in data/blackout.json checkpoints.ids" % key)
        x, y, z = w["position"]
        out.append((ids[key], "waystone", "the %s waystone" % town_name(w["town"]), x, y, z,
                    cfg["checkpoints"]["waystone_arrival_radius"]))
    seen = {}
    for c in out:
        if c[0] in seen:
            raise SystemExit("checkpoint id %d is used twice" % c[0])
        seen[c[0]] = c
    return sorted(out)


def molang_or(ids):
    return " || ".join("t.id == 'cobblemon:%s'" % s for s in ids)


def build(cfg, mounts, placements, progression):
    """{relative path: file text} for the whole pack."""
    files = {}
    fn = lambda path, lines: files.__setitem__("data/%s/function/%s.mcfunction" % (NS, path), "\n".join(lines) + "\n")
    msg = cfg["messages"]
    money, water, claims = cfg["money"], cfg["water"], cfg["claims"]
    cats = claims["categories"]
    pallet = cfg["pallet"]["position"]
    cps = checkpoints(cfg, placements, progression)

    files["pack.mcmeta"] = json.dumps({"pack": {"pack_format": 48, "description": "Cobblers blackout, recovery and water ladder (generated by tools/blackout_pack.py)"}}, indent=2) + "\n"
    files["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:blackout/load" % NS]}, indent=2) + "\n"
    files["data/minecraft/tags/function/tick.json"] = json.dumps({"values": ["%s:blackout/tick" % NS]}, indent=2) + "\n"
    for cat in ("balls", "medicine", "consumables"):
        files["data/%s/tags/item/claim/%s.json" % (NS, cat)] = json.dumps({"values": sorted(claims[cat])}, indent=2) + "\n"
    files["data/%s/tags/block/water.json" % NS] = json.dumps({"values": [
        "minecraft:water", "minecraft:bubble_column", "minecraft:kelp", "minecraft:kelp_plant",
        "minecraft:seagrass", "minecraft:tall_seagrass"]}, indent=2) + "\n"
    files["data/%s/advancement/blackout/healer_use.json" % NS] = json.dumps({
        "criteria": {"use": {"trigger": "minecraft:any_block_use", "conditions": {"location": [
            {"condition": "minecraft:location_check", "predicate": {"block": {"blocks": "cobblemon:healing_machine"}}}]}}},
        "rewards": {"function": "%s:blackout/checkpoint/healer_used" % NS}}, indent=2) + "\n"

    # ---- load and tick -------------------------------------------------------------------------------------------
    consts = {"#pct": money["percent"], "#100": 100, "#2": 2, "#5": 5, "#10": 10, "#-1": -1,
              "#dedupe": cfg["dedupe_ticks"], "#jump": cfg["checkpoints"]["waystone_jump"],
              "#bpct": cats["balls"]["percent"], "#bmax": cats["balls"]["max"],
              "#mpct": cats["medicine"]["percent"], "#mmax": cats["medicine"]["max"],
              "#cchance": cats["consumables"]["chance_percent"], "#maint": claims["maintenance_ticks"],
              "#leash": claims["guardian_leash"], "#surf": water["surf_bonus_ticks"],
              "#grace": water["partner_grace_ticks"], "#breath": water["breath_reset_ticks"],
              "#pulse": water["pulse_ticks"], "#airwarn": water["air_warning"], "#regen": water["pulse_regen_margin"]}
    fn("blackout/load", ["# generated by tools/blackout_pack.py from data/blackout.json"]
       + ["scoreboard objectives add %s %s" % (k, v) for k, v in OBJECTIVES.items()]
       + ["scoreboard players set %s bo.cfg %d" % (k, v) for k, v in consts.items()]
       + ["# the ordinary inventory is always kept (spec rule 3); a claim takes only what it selects",
          "gamerule keepInventory true",
          "execute unless data storage %s:recovery claims run data modify storage %s:recovery claims set value []" % (NS, NS)])
    fn("blackout/tick", [
        "execute store result score #gt bo.tmp run time query gametime",
        "scoreboard players operation #m10 bo.tmp = #gt bo.tmp",
        "scoreboard players operation #m10 bo.tmp %= #10 bo.cfg",
        "# a death is charged the tick it happens, while the player may still be on the death screen",
        "execute as @a[scores={bo.deaths=1..}] run function %s:blackout/death" % NS,
        "# the return runs on the first living tick after a blackout",
        "execute as @e[type=player,tag=cobblers.bo_pending] at @s run function %s:blackout/arrive" % NS,
        "execute as @a[scores={bo.leave=1..}] at @s run function %s:blackout/login" % NS,
        "execute as @e[type=player,gamemode=!creative,gamemode=!spectator] at @s run function %s:water/tick" % NS,
        "scoreboard players operation #m bo.tmp = #gt bo.tmp",
        "scoreboard players operation #m bo.tmp %= #5 bo.cfg",
        "execute if score #m bo.tmp matches 0 as @e[type=player] at @s run function %s:blackout/checkpoint/sample" % NS,
        "scoreboard players operation #m bo.tmp = #gt bo.tmp",
        "scoreboard players operation #m bo.tmp %= #maint bo.cfg",
        "execute if score #m bo.tmp matches 0 run function %s:recovery/maintain" % NS])

    # ---- the blackout pipeline -----------------------------------------------------------------------------------
    fn("blackout/dedupe", [
        "# #dup 1: this player already blacked out within dedupe_ticks (one incident, one charge)",
        "execute store result score #gt bo.tmp run time query gametime",
        "scoreboard players set #dup bo.tmp 0",
        "scoreboard players operation #d bo.tmp = #gt bo.tmp",
        "scoreboard players operation #d bo.tmp -= @s bo.last",
        "execute if score @s bo.last matches 1.. if score #d bo.tmp < #dedupe bo.cfg run scoreboard players set #dup bo.tmp 1",
        "execute if score #dup bo.tmp matches 0 run scoreboard players operation @s bo.last = #gt bo.tmp"])
    fn("blackout/death", [
        "# as a player who has just died: environmental unless a battle already claimed this incident",
        "scoreboard players reset @s bo.deaths",
        "function %s:blackout/dedupe" % NS,
        "execute if score #dup bo.tmp matches 1 run return 0",
        "scoreboard players set @s bo.clm 0",
        "function %s:blackout/charge" % NS,
        "tag @s add cobblers.bo_pending"])
    fn("blackout/battle_loss_wild", [
        "# as a player who has just lost a battle to a wild Pokemon (callbacks/battle_victory); $(victor) is its entity UUID",
        "function %s:blackout/dedupe" % NS,
        "execute if score #dup bo.tmp matches 1 run return 0",
        "scoreboard players set @s bo.clm 0",
        "# an item claim needs the exact victor; if it cannot be found, the environmental outcome (spec: never guess)",
        '$execute if entity $(victor) run function %s:recovery/make {victor:"$(victor)",name:"$(name)",id:"$(id)"}' % NS,
        "function %s:blackout/charge" % NS,
        "tag @s add cobblers.bo_pending"])
    fn("blackout/battle_loss_npc", [
        "# as a player who has just lost to an NPC trainer: trainer claims bind to the route trainers, not built yet,",
        "# so this is money and the return only",
        "function %s:blackout/dedupe" % NS,
        "execute if score #dup bo.tmp matches 1 run return 0",
        "scoreboard players set @s bo.clm 3",
        "function %s:blackout/charge" % NS,
        "tag @s add cobblers.bo_pending"])
    fn("blackout/battle_loss_other", [
        "# a loss with no scriptable victor (another player, or none): money and the return, no items",
        "function %s:blackout/dedupe" % NS,
        "execute if score #dup bo.tmp matches 1 run return 0",
        "scoreboard players set @s bo.clm 0",
        "function %s:blackout/charge" % NS,
        "tag @s add cobblers.bo_pending"])
    fn("blackout/charge", [
        "# %d%% of the balance, rounded up, so any balance above zero loses at least 1 (EXP-040: the query's result is the balance)" % money["percent"],
        "scoreboard players set @s bo.lost 0",
        "execute store result score @s bo.bal run cobbledollars query @s",
        "execute if score @s bo.bal matches 1.. run function %s:blackout/charge_calc" % NS])
    fn("blackout/charge_calc", [
        "scoreboard players operation @s bo.lost = @s bo.bal",
        "scoreboard players operation @s bo.lost *= #pct bo.cfg",
        "scoreboard players add @s bo.lost 99",
        "scoreboard players operation @s bo.lost /= #100 bo.cfg",
        "execute store result storage %s:blackout charge.amount int 1 run scoreboard players get @s bo.lost" % NS,
        "function %s:blackout/charge_apply with storage %s:blackout charge" % (NS, NS)])
    fn("blackout/charge_apply", ["$cobbledollars remove @s $(amount)"])
    fn("blackout/arrive", [
        "# as a living player after a blackout, at them",
        "tag @s remove cobblers.bo_pending",
        "function %s:blackout/checkpoint/validate" % NS,
        "execute if score @s bo.ok matches 0 run function %s:blackout/checkpoint/to_pallet" % NS,
        "execute store result storage %s:blackout go.x int 1 run scoreboard players get @s bo.cpx" % NS,
        "execute store result storage %s:blackout go.y int 1 run scoreboard players get @s bo.cpy" % NS,
        "execute store result storage %s:blackout go.z int 1 run scoreboard players get @s bo.cpz" % NS,
        "function %s:blackout/checkpoint/tp with storage %s:blackout go" % (NS, NS),
        "healpokemon @s",
        "effect give @s minecraft:resistance %d 4 true" % cfg["arrival_protection_seconds"],
        "scoreboard players set @s bo.pulse 0",
        "scoreboard players set @s bo.warn 0",
        "scoreboard players set @s bo.surf 0",
        "function %s:blackout/checkpoint/name" % NS,
        'tellraw @s [%s,{"storage":"%s:blackout","nbt":"place","color":"white"},%s,{"score":{"name":"@s","objective":"bo.lost"},"color":"white"},%s]'
        % (text(msg["blackout"].split("{place}")[0]), NS,
           text(msg["blackout"].split("{place}")[1].split("{money}")[0] + money["currency_symbol"]),
           text(msg["blackout"].split("{money}")[1])),
        "execute if score @s bo.clm matches 0 run tellraw @s %s" % text(msg["no_items"]),
        "execute if score @s bo.clm matches 3 run tellraw @s %s" % text(msg["npc_no_items"])])

    # ---- checkpoints -----------------------------------------------------------------------------------------------
    validate = ["# bo.ok 1 if the saved checkpoint is still in the data and the saved point is still at it",
                "scoreboard players set @s bo.ok 0"]
    names = ['data modify storage %s:blackout place set value "%s"' % (NS, cfg["pallet"]["name"])]
    healer = ["# as a player who has just used a healing machine: the Center it stands in becomes the checkpoint",
              "advancement revoke @s only %s:blackout/healer_use" % NS]
    ways = ["# as a player who has just jumped a long way: travel through a town waystone lands beside it"]
    for cid, kind, name, x, y, z, r in cps:
        vr = r if kind == "center" else r * 2
        validate.append("execute if score @s bo.cp matches %d if score @s bo.cpx matches %d..%d if score @s bo.cpz matches %d..%d run scoreboard players set @s bo.ok 1"
                        % (cid, x - vr, x + vr, z - vr, z + vr))
        names.append('execute if score @s bo.cp matches %d run data modify storage %s:blackout place set value "%s"' % (cid, NS, name))
        if kind == "center":
            healer.append("execute if entity @s[x=%d,y=-64,z=%d,dx=%d,dy=640,dz=%d] run return run function %s:blackout/checkpoint/set {id:%d}"
                          % (x - r, z - r, 2 * r, 2 * r, NS, cid))
        else:
            ways.append("execute if entity @s[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d] run return run function %s:blackout/checkpoint/set {id:%d}"
                        % (x - r, y - r, z - r, 2 * r, 2 * r, 2 * r, NS, cid))
    fn("blackout/checkpoint/validate", validate)
    fn("blackout/checkpoint/name", names)
    fn("blackout/checkpoint/healer_used", healer)
    fn("blackout/checkpoint/waystones", ways)
    fn("blackout/checkpoint/set", [
        "# as and at the player: the checkpoint is where they stand now",
        "$execute if score @s bo.cp matches $(id) run scoreboard players set #same bo.tmp 1",
        "$execute unless score @s bo.cp matches $(id) run scoreboard players set #same bo.tmp 0",
        "$scoreboard players set @s bo.cp $(id)",
        "execute store result score @s bo.cpx run data get entity @s Pos[0]",
        "execute store result score @s bo.cpy run data get entity @s Pos[1]",
        "execute store result score @s bo.cpz run data get entity @s Pos[2]",
        "spawnpoint @s ~ ~ ~",
        "execute if score #same bo.tmp matches 0 run function %s:blackout/checkpoint/name" % NS,
        'execute if score #same bo.tmp matches 0 run title @s actionbar [%s,{"storage":"%s:blackout","nbt":"place"},%s]'
        % (text(msg["checkpoint_center"].split("{place}")[0], "white"), NS, text(msg["checkpoint_center"].split("{place}")[1], "white"))])
    fn("blackout/checkpoint/to_pallet", [
        "scoreboard players set @s bo.cp 0",
        "scoreboard players set @s bo.cpx %d" % pallet[0],
        "scoreboard players set @s bo.cpy %d" % pallet[1],
        "scoreboard players set @s bo.cpz %d" % pallet[2],
        "spawnpoint @s %d %d %d" % tuple(pallet)])
    fn("blackout/checkpoint/tp", ["$execute in minecraft:overworld run tp @s $(x).5 $(y) $(z).5"])
    fn("blackout/checkpoint/sample", [
        "# every 5 ticks: how far the player moved since the last sample (|dx| + |dz|)",
        "execute store result score @s bo.px run data get entity @s Pos[0]",
        "execute store result score @s bo.pz run data get entity @s Pos[2]",
        "scoreboard players operation #dx bo.tmp = @s bo.px",
        "scoreboard players operation #dx bo.tmp -= @s bo.ox",
        "scoreboard players operation #dz bo.tmp = @s bo.pz",
        "scoreboard players operation #dz bo.tmp -= @s bo.oz",
        "execute if score #dx bo.tmp matches ..-1 run scoreboard players operation #dx bo.tmp *= #-1 bo.cfg",
        "execute if score #dz bo.tmp matches ..-1 run scoreboard players operation #dz bo.tmp *= #-1 bo.cfg",
        "scoreboard players operation #dx bo.tmp += #dz bo.tmp",
        "scoreboard players operation @s bo.ox = @s bo.px",
        "scoreboard players operation @s bo.oz = @s bo.pz",
        "execute if score #dx bo.tmp >= #jump bo.cfg run function %s:blackout/checkpoint/waystones" % NS])
    fn("blackout/login", [
        "# as a player who has just joined: the party is re-read before any water benefit returns (spec)",
        "scoreboard players reset @s bo.leave",
        "scoreboard players set @s bo.mount 0",
        "scoreboard players set @s bo.qual 0",
        "execute store result score @s bo.ox run data get entity @s Pos[0]",
        "execute store result score @s bo.oz run data get entity @s Pos[2]",
        "function %s:recovery/deliver" % NS])

    # ---- claims ----------------------------------------------------------------------------------------------------
    R = "%s:recovery" % NS

    def quota(n, t, pct, mx):
        return ["scoreboard players operation @s %s = @s %s" % (t, n),
                "scoreboard players operation @s %s *= %s bo.cfg" % (t, pct),
                "scoreboard players add @s %s 99" % t,
                "scoreboard players operation @s %s /= #100 bo.cfg" % t,
                "scoreboard players operation @s %s < %s bo.cfg" % (t, mx)]

    fn("recovery/make", [
        "# as the player who lost; $(victor) is the wild victor's entity UUID, $(name) and $(id) the player's name and UUID",
        "scoreboard players set @s bo.clm 2",
        "execute store result score @s bo.nb run clear @s #%s:claim/balls 0" % NS,
        "execute store result score @s bo.nm run clear @s #%s:claim/medicine 0" % NS,
        "execute store result score @s bo.nc run clear @s #%s:claim/consumables 0" % NS]
       + quota("bo.nb", "bo.tb", "#bpct", "#bmax") + quota("bo.nm", "bo.tm", "#mpct", "#mmax")
       + ["scoreboard players set @s bo.tc 0",
          "execute if score @s bo.nc matches 1.. store result score #r bo.tmp run random value 0..99",
          "execute if score @s bo.nc matches 1.. if score #r bo.tmp < #cchance bo.cfg run scoreboard players set @s bo.tc 1",
          "execute if score @s bo.tc matches 1 run function %s/pick" % R,
          "scoreboard players operation @s bo.mb = @s bo.tb",
          "scoreboard players operation @s bo.mm = @s bo.tm",
          "scoreboard players operation @s bo.mc = @s bo.tc",
          "scoreboard players operation #tot bo.tmp = @s bo.tb",
          "scoreboard players operation #tot bo.tmp += @s bo.tm",
          "scoreboard players operation #tot bo.tmp += @s bo.tc",
          '$execute if score #tot bo.tmp matches 0 run return run tellraw @s [{"selector":"$(victor)"},%s]' % text(msg["claim_nothing"].split("{victor}")[1]),
          "# plan every take from one inventory snapshot, then persist the claim, then take",
          "data modify storage %s pending set value {items:[],plan:[]}" % R,
          "function %s/scan" % R,
          '$function %s/commit {victor:"$(victor)",name:"$(name)",id:"$(id)"}' % R])
    fn("recovery/pick", [
        "# which one of the carried consumables: a random unit among bo.nc",
        "execute store result storage %s pickmax.max int 1 run scoreboard players get @s bo.nc" % R,
        "function %s/pick_roll with storage %s pickmax" % (R, R)])
    fn("recovery/pick_roll", ["$execute store result score #pick bo.tmp run random value 1..$(max)",
                              "scoreboard players remove #pick bo.tmp 1"])
    scan = ["# generated: every slot a claim may take from, category by category"]
    for slot, nbt in SLOTS:
        scan.append('execute if score @s bo.tb matches 1.. if items entity @s %s #%s:claim/balls run function %s/take {slot:"%s",nbt:%d,q:"bo.tb"}' % (slot, NS, R, slot, nbt))
        scan.append('execute if score @s bo.tm matches 1.. if items entity @s %s #%s:claim/medicine run function %s/take {slot:"%s",nbt:%d,q:"bo.tm"}' % (slot, NS, R, slot, nbt))
        scan.append('execute if score @s bo.tc matches 1.. if items entity @s %s #%s:claim/consumables run function %s/take_pick {slot:"%s",nbt:%d}' % (slot, NS, R, slot, nbt))
    fn("recovery/scan", scan)
    fn("recovery/take", [
        "# plan to take min(the stack, the quota left) from one slot: the stack goes into the claim, the reduction into the plan",
        "$execute store result score #cnt bo.tmp run data get entity @s Inventory[{Slot:$(nbt)b}].count",
        "scoreboard players operation #t bo.tmp = #cnt bo.tmp",
        "$scoreboard players operation #t bo.tmp < @s $(q)",
        "$data modify storage %s pending.items append from entity @s Inventory[{Slot:$(nbt)b}]" % R,
        "execute store result storage %s pending.items[-1].count int 1 run scoreboard players get #t bo.tmp" % R,
        "data remove storage %s pending.items[-1].Slot" % R,
        '$data modify storage %s pending.plan append value {slot:"$(slot)",n:0}' % R,
        "execute store result storage %s pending.plan[-1].n int -1 run scoreboard players get #t bo.tmp" % R,
        "$scoreboard players operation @s $(q) -= #t bo.tmp"])
    fn("recovery/take_pick", [
        "$execute store result score #cnt bo.tmp run data get entity @s Inventory[{Slot:$(nbt)b}].count",
        "execute if score #pick bo.tmp >= #cnt bo.tmp run return run scoreboard players operation #pick bo.tmp -= #cnt bo.tmp",
        '$function %s/take {slot:"$(slot)",nbt:$(nbt),q:"bo.tc"}' % R])
    fn("recovery/commit", [
        "# the victor's guardian number: its own if it already guards a claim, else this claim's id",
        "scoreboard players set #g bo.tmp 0",
        "$execute as $(victor) run scoreboard players operation #g bo.tmp = @s bo.g",
        "scoreboard players add #next bo.tmp 1",
        "execute if score #g bo.tmp matches ..0 run scoreboard players operation #g bo.tmp = #next bo.tmp",
        "execute store result storage %s pending.id int 1 run scoreboard players get #next bo.tmp" % R,
        "execute store result storage %s pending.g int 1 run scoreboard players get #g bo.tmp" % R,
        'data modify storage %s pending.state set value "open"' % R,
        "data modify storage %s pending.seen set value 0" % R,
        "data modify storage %s pending.owner set from entity @s UUID" % R,
        '$data modify storage %s pending.owner_id set value "$(id)"' % R,
        '$data modify storage %s pending.owner_name set value "$(name)"' % R,
        "execute store result storage %s pending.created int 1 run time query gametime" % R,
        "$execute store result storage %s pending.x int 1 run data get entity $(victor) Pos[0]" % R,
        "$execute store result storage %s pending.y int 1 run data get entity $(victor) Pos[1]" % R,
        "$execute store result storage %s pending.z int 1 run data get entity $(victor) Pos[2]" % R,
        "$data modify storage %s pending.snapshot set from entity $(victor) Pokemon" % R,
        "# persist first (spec: the claim is written before anything is removed); abort if it did not land",
        "data modify storage %s claims append from storage %s pending" % (R, R),
        "data remove storage %s claims[-1].plan" % R,
        "execute unless data storage %s claims[-1].items[0] run return fail" % R,
        "function %s/apply" % R,
        "$execute as $(victor) run function %s/bind" % R,
        "function %s/summary" % R,
        '$tellraw @s [{"selector":"$(victor)","color":"white"},%s,{"storage":"%s","nbt":"summary[]","interpret":true,"separator":", "},%s]'
        % (text(msg["claim"].split("{victor}")[1].split("{summary}")[0]), R, text(msg["claim"].split("{summary}")[1]))])
    fn("recovery/apply", [
        "execute unless data storage %s pending.plan[0] run return 0" % R,
        "function %s/apply_one with storage %s pending.plan[0]" % (R, R),
        "data remove storage %s pending.plan[0]" % R,
        "function %s/apply" % R])
    fn("recovery/apply_one", ['$item modify entity @s $(slot) {function:"minecraft:set_count",count:$(n),add:true}'])
    fn("recovery/bind", [
        "# as the victor: kept from the despawner by vanilla PersistenceRequired (EXP-041), and numbered",
        "data merge entity @s {PersistenceRequired:1b}",
        "tag @s add cobblers.guardian",
        "scoreboard players operation @s bo.g = #g bo.tmp",
        "function %s/bind_tag with storage %s pending" % (R, R)])
    fn("recovery/bind_tag", ["$tag @s add cobblers.g$(g)"])
    fn("recovery/summary", [
        "data modify storage %s summary set value []" % R,
        'execute if score @s bo.mb matches 1.. run data modify storage %s summary append value \'[{"score":{"name":"@s","objective":"bo.mb"}},{"text":" Poke Ball(s)"}]\'' % R,
        'execute if score @s bo.mm matches 1.. run data modify storage %s summary append value \'[{"score":{"name":"@s","objective":"bo.mm"}},{"text":" medicine"}]\'' % R,
        'execute if score @s bo.mc matches 1.. run data modify storage %s summary append value \'{"text":"a battle or evolution item"}\'' % R])

    # resolution: beating or catching the guardian resolves every open claim it holds, for their owners
    fn("recovery/defeated", [
        "# as the guardian, beaten or caught; $(resolver) is the winning player's UUID. The claims resolve first; the",
        "# guardian is released only after, so a failure part-way leaves it guarding (never loses a claim)",
        "execute unless score @s bo.g matches 1.. run return fail",
        "data modify storage %s r set value {}" % R,
        "execute store result storage %s r.g int 1 run scoreboard players get @s bo.g" % R,
        '$data modify storage %s r.resolver set value "$(resolver)"' % R,
        "data modify storage %s scan set from storage %s claims" % (R, R),
        "function %s/resolve_next" % R,
        "tag @s remove cobblers.guardian",
        "function %s/unbind_tag with storage %s r" % (R, R),
        "scoreboard players reset @s bo.g",
        "data merge entity @s {PersistenceRequired:0b}",
        "execute as @a at @s run function %s/deliver" % R])
    fn("recovery/unbind_tag", ["$tag @s remove cobblers.g$(g)"])
    fn("recovery/resolve_next", [
        "execute unless data storage %s scan[0] run return 0" % R,
        "data modify storage %s cur set from storage %s scan[0]" % (R, R),
        "data modify storage %s cur.resolver set from storage %s r.resolver" % (R, R),
        "data modify storage %s cur.rg set from storage %s r.g" % (R, R),
        'execute if data storage %s cur{state:"open"} run function %s/resolve_one with storage %s cur' % (R, R, R),
        "data remove storage %s scan[0]" % R,
        "function %s/resolve_next" % R])
    fn("recovery/resolve_one", [
        "$execute unless data storage %s claims[{id:$(id),g:$(rg)}] run return 0" % R,
        '$data modify storage %s claims[{id:$(id)}].resolver set value "$(resolver)"' % R,
        '$data modify storage %s claims[{id:$(id)}].state set value "deliver"' % R,
        '$execute unless data storage %s claims[{id:$(id),owner_id:"$(resolver)"}] as $(resolver) run tellraw @s %s'
        % (R, json.dumps({"text": msg["recovered_helper"].replace("{owner}", "$(owner_name)"), "color": "gray"}))])
    fn("recovery/deliver", [
        "# as and at a player: every resolved claim of theirs is dropped at their feet, only they can pick it up",
        "data modify storage %s me set value {}" % R,
        "data modify storage %s me.UUID set from entity @s UUID" % R,
        "data modify storage %s scan set from storage %s claims" % (R, R),
        "function %s/deliver_next" % R])
    fn("recovery/deliver_next", [
        "execute unless data storage %s scan[0] run return 0" % R,
        "data modify storage %s cur set from storage %s scan[0]" % (R, R),
        "data modify storage %s cur.me set from storage %s me.UUID" % (R, R),
        'execute if data storage %s cur{state:"deliver"} run function %s/deliver_one with storage %s cur' % (R, R, R),
        "data remove storage %s scan[0]" % R,
        "function %s/deliver_next" % R])
    fn("recovery/deliver_one", [
        "$execute unless data storage %s cur{owner:$(me)} run return 0" % R,
        "data modify storage %s drop set from storage %s cur.items" % (R, R),
        "function %s/drop_next" % R,
        '$data modify storage %s claims[{id:$(id)}].state set value "resolved"' % R,
        '$execute if data storage %s cur{owner_id:"$(resolver)"} run tellraw @s %s' % (R, text(msg["recovered_owner"])),
        '$execute unless data storage %s cur{owner_id:"$(resolver)"} run tellraw @s [{"selector":"$(resolver)"},%s]'
        % (R, text(msg["recovered_by_helper_owner"].split("{helper}")[1]))])
    fn("recovery/drop_next", [
        "execute unless data storage %s drop[0] run return 0" % R,
        "data modify storage %s one set value {}" % R,
        "data modify storage %s one.item set from storage %s drop[0]" % (R, R),
        "data modify storage %s one.owner set from storage %s me.UUID" % (R, R),
        "function %s/drop_one with storage %s one" % (R, R),
        "data remove storage %s drop[0]" % R,
        "function %s/drop_next" % R])
    fn("recovery/drop_one", ["$summon item ~ ~0.5 ~ {Item:$(item),PickupDelay:0,Age:-32768,Owner:$(owner)}"])

    # maintenance: keep each open claim's guardian present, single and near its site
    fn("recovery/maintain", [
        "data modify storage %s mscan set from storage %s claims" % (R, R),
        "function %s/maintain_next" % R])
    fn("recovery/maintain_next", [
        "execute unless data storage %s mscan[0] run return 0" % R,
        "data modify storage %s mcur set from storage %s mscan[0]" % (R, R),
        'execute if data storage %s mcur{state:"open"} run function %s/check with storage %s mcur' % (R, R, R),
        "data remove storage %s mscan[0]" % R,
        "function %s/maintain_next" % R])
    fn("recovery/check", [
        "$execute if entity @e[type=cobblemon:pokemon,tag=cobblers.g$(g)] run return run function %s/present {g:$(g),x:$(x),y:$(y),z:$(z),id:$(id)}" % R,
        "$execute unless loaded $(x) $(y) $(z) run return run data modify storage %s claims[{id:$(id)}].seen set value 0" % R,
        "# loaded and absent: rebuilt only on the second pass in a row (entities load a moment after their chunk)",
        "$execute if data storage %s claims[{id:$(id),seen:0}] run return run data modify storage %s claims[{id:$(id)}].seen set value 1" % (R, R),
        "$function %s/rebuild {g:$(g),x:$(x),y:$(y),z:$(z),id:$(id)}" % R])
    fn("recovery/present", [
        "$data modify storage %s claims[{id:$(id)}].seen set value 0" % R,
        "$execute store result score #n bo.tmp if entity @e[type=cobblemon:pokemon,tag=cobblers.g$(g)]",
        "# a duplicate (a rebuild that raced the original's load): the rebuilt one goes",
        "$execute if score #n bo.tmp matches 2.. run kill @e[type=cobblemon:pokemon,tag=cobblers.g$(g),tag=cobblers.rebuilt,limit=1]",
        "$execute as @e[type=cobblemon:pokemon,tag=cobblers.g$(g)] positioned $(x) $(y) $(z) unless entity @s[distance=..%d] run tp @s $(x) $(y) $(z)" % claims["guardian_leash"]])
    fn("recovery/rebuild", [
        "# a placeholder from Cobblemon's own spawn command, then the ledger's snapshot written over it (tested 2026-09-26)",
        "$execute positioned $(x) $(y) $(z) run spawnpokemonat ~ ~ ~ magikarp level=1",
        "$execute positioned $(x) $(y) $(z) as @e[type=cobblemon:pokemon,tag=!cobblers.guardian,distance=..1,limit=1,sort=nearest] run function %s/rebuild_as {g:$(g),id:$(id)}" % R])
    fn("recovery/rebuild_as", [
        "$data modify entity @s Pokemon set from storage %s claims[{id:$(id)}].snapshot" % R,
        "data merge entity @s {PersistenceRequired:1b}",
        "tag @s add cobblers.guardian",
        "tag @s add cobblers.rebuilt",
        "$tag @s add cobblers.g$(g)",
        "$scoreboard players set @s bo.g $(g)",
        "$data modify storage %s claims[{id:$(id)}].rebuilt set value 1b" % R,
        "$data modify storage %s claims[{id:$(id)}].seen set value 0" % R])

    # ---- the water ladder ------------------------------------------------------------------------------------------
    deep_chain = " ".join("if block ~ ~%d ~ #%s:water" % (i, NS) for i in range(1, water["deep_blocks"] + 1))
    fn("water/tick", [
        "# as and at a player in survival or adventure, every tick",
        "scoreboard players set @s bo.sub 0",
        "scoreboard players set @s bo.deep 0",
        "execute anchored eyes positioned ^ ^ ^ if block ~ ~ ~ #%s:water run scoreboard players set @s bo.sub 1" % NS,
        "execute if score @s bo.sub matches 1 anchored eyes positioned ^ ^ ^ %s run scoreboard players set @s bo.deep 1" % deep_chain,
        "function %s:water/qualify" % NS,
        "execute if score @s bo.sub matches 0 run return run function %s:water/surfaced" % NS,
        "execute store result score @s bo.air run data get entity @s Air",
        "execute if score @s bo.deep matches 1 run function %s:water/deep" % NS])
    fn("water/qualify", [
        "# bo.raw: what the training and the party support now; bo.qual: what applies, lowered only after a grace",
        "scoreboard players set @s bo.raw 0",
        "execute if entity @s[tag=cobblers.surf] if score @s bo.mount matches 1.. run scoreboard players set @s bo.raw 1",
        "execute if entity @s[tag=cobblers.dive] if score @s bo.mount matches 1 run scoreboard players set @s bo.raw 1",
        "execute if entity @s[tag=cobblers.dive] if score @s bo.mount matches 2 run scoreboard players set @s bo.raw 2",
        "execute if score @s bo.raw >= @s bo.qual run scoreboard players set @s bo.grace 0",
        "execute if score @s bo.raw >= @s bo.qual run return run scoreboard players operation @s bo.qual = @s bo.raw",
        "execute if score @s bo.grace matches 0 if score @s bo.deep matches 1 run tellraw @s %s" % text(msg["partner_gone"], "yellow"),
        "scoreboard players add @s bo.grace 1",
        "execute if score @s bo.grace >= #grace bo.cfg run scoreboard players operation @s bo.qual = @s bo.raw",
        "execute if score @s bo.grace >= #grace bo.cfg run scoreboard players set @s bo.grace 0"])
    fn("water/surfaced", [
        "scoreboard players set @s bo.pulse 0",
        "scoreboard players set @s bo.warn 0",
        "execute if score @s bo.surf matches 1.. run function %s:water/breathe" % NS])
    fn("water/breathe", [
        "# the Surf bonus resets only after the eyes stay in air, with full vanilla air, for breath_reset_ticks",
        "execute store result score @s bo.air run data get entity @s Air",
        "execute if score @s bo.air matches 300.. run scoreboard players add @s bo.breath 1",
        "execute if score @s bo.air matches ..299 run scoreboard players set @s bo.breath 0",
        "execute if score @s bo.breath >= #breath bo.cfg run scoreboard players set @s bo.surf 0",
        "execute if score @s bo.breath >= #breath bo.cfg run scoreboard players set @s bo.breath 0"])
    fn("water/deep", [
        "# eyes at least %d blocks under: Dive is unlimited, Surf a bonus per submersion, otherwise the harsh rule" % water["deep_blocks"],
        "execute if score @s bo.qual matches 2 run return run function %s:water/breathing" % NS,
        "execute if score @s bo.qual matches 1 if score @s bo.surf < #surf bo.cfg run scoreboard players add @s bo.surf 1",
        "execute if score @s bo.qual matches 1 if score @s bo.surf < #surf bo.cfg run return run function %s:water/breathing" % NS,
        "execute if score @s bo.air <= #airwarn bo.cfg if score @s bo.warn matches 0 run function %s:water/warn_low" % NS,
        "execute if score @s bo.air matches ..0 run function %s:water/out" % NS])
    fn("water/breathing", [
        "scoreboard players set @s bo.pulse 0",
        "scoreboard players set @s bo.warn 0",
        "execute if score #m10 bo.tmp matches 0 run effect give @s minecraft:water_breathing 2 0 true"])
    fn("water/warn_low", ["tellraw @s %s" % text(msg["air_low"], "yellow"), "scoreboard players set @s bo.warn 1"])
    fn("water/out", [
        "execute if score @s bo.warn matches ..1 run tellraw @s %s" % text(msg["air_out"], "red"),
        "execute if score @s bo.warn matches ..1 run scoreboard players set @s bo.warn 2",
        "scoreboard players operation #p bo.tmp = @s bo.pulse",
        "scoreboard players operation #p bo.tmp %= #pulse bo.cfg",
        "execute if score #p bo.tmp matches 0 run function %s:water/pulse" % NS,
        "scoreboard players add @s bo.pulse 1"])
    fn("water/pulse", [
        "# half of maximum health as drown damage (bypasses armour); two from full health knock the player out",
        "execute store result score @s bo.mh run attribute @s minecraft:generic.max_health get 1",
        "scoreboard players operation @s bo.mh /= #2 bo.cfg",
        "# from half health (plus what natural regeneration adds between hits) the hit is lethal: EXP-042 run 1 saw a",
        "# full-health player regenerate to 11 between hits and survive the second at 2",
        "execute store result score #hp bo.tmp run data get entity @s Health 1",
        "scoreboard players operation #lim bo.tmp = @s bo.mh",
        "scoreboard players operation #lim bo.tmp += #regen bo.cfg",
        "execute if score #hp bo.tmp <= #lim bo.tmp run scoreboard players set @s bo.mh 1000",
        "execute store result storage %s:blackout pulse.amount int 1 run scoreboard players get @s bo.mh" % NS,
        "function %s:water/pulse_apply with storage %s:blackout pulse" % (NS, NS),
        "execute if score @s bo.warn matches 2 run tellraw @s %s" % text(msg["one_more"], "red"),
        "execute if score @s bo.warn matches 2 run scoreboard players set @s bo.warn 3"])
    fn("water/pulse_apply", ["$damage @s $(amount) minecraft:drown"])
    fn("water/grant_surf", ["# Misty's training (DEATH_AND_WIPE.md 'Where Surf and Dive come from'); the story event calls this",
                            "tag @s add cobblers.surf"])
    fn("water/grant_dive", ["# the survey diver's training; Dive includes Surf", "tag @s add cobblers.surf", "tag @s add cobblers.dive"])
    fn("water/revoke", ["tag @s remove cobblers.surf", "tag @s remove cobblers.dive"])

    # ---- MoLang callbacks ------------------------------------------------------------------------------------------
    # Cobblemon fires only callbacks under its own namespace: a file in data/cobblers/callbacks/<event>/ registers
    # (the load count rises) but never runs (EXP-042, staging 2026-09-26). Ours sit beside Cobblemon's, cobblers_*.
    files["data/cobblemon/callbacks/player_tick_pre/cobblers_water_mounts.molang"] = "\n".join([
        "'Generated by tools/blackout_pack.py from data/water_mounts.json. Once a second: the best water support in the';",
        "'active party (2 Dive, 1 Surf, 0 none), fainted Pokemon excluded, into the bo.mount score.';",
        "math.mod(q.player.world.game_time, 20) != 0 ? { return 0; };",
        "t.best = 0;",
        "for_each(t.p, q.player.party.pokemon, {",
        "  t.p.current_hp > 0 ? {",
        "    t.id = t.p.species.identifier;",
        "    (%s) ? { t.best = 2; };" % molang_or(mounts["dive"]),
        "    (t.best < 1 && (%s)) ? { t.best = 1; };" % molang_or(mounts["surf"]),
        "  };",
        "});",
        "t.best == 2 ? { q.run_command('scoreboard players set ' + q.player.username + ' bo.mount 2'); };",
        "t.best == 1 ? { q.run_command('scoreboard players set ' + q.player.username + ' bo.mount 1'); };",
        "t.best == 0 ? { q.run_command('scoreboard players set ' + q.player.username + ' bo.mount 0'); };",
        ""])
    files["data/cobblemon/callbacks/battle_victory/cobblers_blackout.molang"] = "\n".join([
        "'Generated by tools/blackout_pack.py. A player who lost runs the blackout; a guardian that lost resolves its claims.';",
        "t.kind = 'other';",
        "t.victor = '';",
        "for_each(t.w, c.scriptable_winners, {",
        "  t.kind == 'other' ? {",
        "    t.w.is_pokemon ? { t.kind = 'wild'; t.victor = t.w.uuid; };",
        "    t.w.is_npc ? { t.kind = 'npc'; t.victor = t.w.uuid; };",
        "  };",
        "});",
        "for_each(t.pl, c.player_losers, {",
        "  q.run_command('execute as ' + t.pl.player.uuid + ' run function %s:blackout/battle_loss_' + t.kind + ' {victor:\"' + t.victor + '\",name:\"' + t.pl.player.username + '\",id:\"' + t.pl.player.uuid + '\"}');" % NS,
        "});",
        "for_each(t.l, c.scriptable_losers, {",
        "  t.l.is_pokemon ? {",
        "    for_each(t.pw, c.player_winners, {",
        "      q.run_command('execute as ' + t.l.uuid + ' if entity @s[tag=cobblers.guardian] run function %s:recovery/defeated {resolver:\"' + t.pw.player.uuid + '\"}');" % NS,
        "    });",
        "  };",
        "});",
        ""])
    files["data/cobblemon/callbacks/pokemon_captured/cobblers_recovery.molang"] = "\n".join([
        "'Generated by tools/blackout_pack.py. Catching a guardian resolves its claims for their owners (spec: rescue without theft).';",
        "t.e = q.pokemon.entity;",
        "q.run_command('execute as ' + t.e.uuid + ' if entity @s[tag=cobblers.guardian] run function %s:recovery/defeated {resolver:\"' + q.player.uuid + '\"}');" % NS,
        ""])
    return files


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    files = build(load("blackout.json"), load("water_mounts.json"), load("placements.json"), load("progression.json"))
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, body in sorted(files.items()):
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8", newline="\n")
    n_fn = sum(1 for k in files if k.endswith(".mcfunction"))
    print("wrote %s: %d files, %d functions" % (out, len(files), n_fn))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
