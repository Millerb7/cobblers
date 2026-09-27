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
               inventory, written to the claim ledger (storage cobblers_recovery:ledger) before anything is removed. The
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
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_blackout"
NS = "cobblers"
# the claim ledger's storage: its own namespace, so Minecraft keeps it in its own file
# (data/command_storage_cobblers_recovery.dat), which tools/carry_players.py carries into a re-exported world; the
# shared cobblers storage also holds the re-apply's own progress, which must never be carried
LEDGER = "cobblers_recovery:ledger"

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
    "bo.pulse": "dummy", "bo.warn": "dummy", "bo.mh": "dummy", "bo.g": "dummy", "bo.brth": "dummy", "bo.hasmod": "dummy", "bo.swim": "dummy", "bo.zone": "dummy", "bo.fat": "dummy", "bo.fwarn": "dummy", "bo.fpt": "dummy",
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


def build(cfg, mounts, placements, progression, boat_rows=None):
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
    # Respiration, neutralised (the owner, 2026-09-26): vanilla's own definition (server-1.21.1.jar) with no effect and
    # nothing it can be applied to, so no table offers it and no anvil applies it; an old book or helmet does nothing
    files["data/minecraft/enchantment/respiration.json"] = json.dumps({
        "anvil_cost": 4, "description": {"translate": "enchantment.minecraft.respiration"},
        "max_cost": {"base": 40, "per_level_above_first": 10}, "max_level": 3,
        "min_cost": {"base": 10, "per_level_above_first": 10}, "slots": ["head"],
        "supported_items": "#%s:enchantable/none" % NS, "weight": 2}, indent=2) + "\n"
    files["data/%s/tags/item/enchantable/none.json" % NS] = json.dumps({"values": []}, indent=2) + "\n"
    files["data/%s/tags/block/water.json" % NS] = json.dumps({"values": [
        "minecraft:water", "minecraft:bubble_column", "minecraft:kelp", "minecraft:kelp_plant",
        "minecraft:seagrass", "minecraft:tall_seagrass"]}, indent=2) + "\n"
    files["data/%s/advancement/blackout/healer_use.json" % NS] = json.dumps({
        "criteria": {"use": {"trigger": "minecraft:any_block_use", "conditions": {"location": [
            {"condition": "minecraft:location_check", "predicate": {"block": {"blocks": "cobblemon:healing_machine"}}}]}}},
        "rewards": {"function": "%s:blackout/checkpoint/healer_used" % NS}}, indent=2) + "\n"

    # ---- load and tick -------------------------------------------------------------------------------------------
    consts = {"#pct": money["percent"], "#100": 100, "#2": 2, "#5": 5, "#10": 10, "#16": 16, "#-1": -1, "#wmin": 1024,
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
          "execute unless data storage cobblers_recovery:ledger claims run data modify storage cobblers_recovery:ledger claims set value []",
          "# hex digits for recovery/pid, and each claimable item's translation key for the claim message",
          "data modify storage cobblers_recovery:ledger hex set value %s" % json.dumps(list("0123456789abcdef")),
          "data modify storage cobblers_recovery:ledger item_keys set value {%s}" % (",".join(
              '"%s":"item.%s"' % (i, i.replace(":", ".")) for i in sorted(set(claims["balls"] + claims["medicine"] + claims["consumables"])))),
          "# player names by UUID, for claims made or settled outside a battle (recovery/remember)",
          "execute unless data storage cobblers_recovery:ledger names run data modify storage cobblers_recovery:ledger names set value []"])
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
        "# who is hurting a guardian (recovery/watch; a kill outside battle is settled from it by maintenance)",
        "execute as @e[type=cobblemon:pokemon,tag=cobblers.guardian] run function %s:recovery/watch" % NS,
        "scoreboard players operation #m bo.tmp = #gt bo.tmp",
        "scoreboard players operation #m bo.tmp %= #5 bo.cfg",
        "execute if score #m bo.tmp matches 0 as @e[type=player] at @s run function %s:blackout/checkpoint/sample" % NS,
        "# surface exhaustion, every surface.sample_ticks, for swimmers in survival or adventure",
        "scoreboard players operation #ms bo.tmp = #gt bo.tmp",
        "scoreboard players operation #ms bo.tmp %= #fsample bo.cfg",
        "execute if score #ms bo.tmp matches 0 as @e[type=player,gamemode=!creative,gamemode=!spectator] at @s run function %s:surface/tick" % NS,
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
        "# a victor tagged %s (the gulch's Megas, data/blackout.json claims.exempt_why) makes no claim" % claims["exempt_tag"],
        "scoreboard players set #exempt bo.tmp 0",
        "$execute as $(victor) if entity @s[tag=%s] run scoreboard players set #exempt bo.tmp 1" % claims["exempt_tag"],
        "# an item claim needs the exact victor; if it cannot be found, the environmental outcome (spec: never guess)",
        '$execute if score #exempt bo.tmp matches 0 if entity $(victor) run function %s:recovery/make {victor:"$(victor)",name:"$(name)",id:"$(id)"}' % NS,
        "function %s:blackout/charge" % NS]
       + (["# the money goes into the claim too (data/blackout.json money.held_by_wild_victor)",
           "execute if score @s bo.clm matches 2 run function %s:recovery/hold_money" % NS] if money.get("held_by_wild_victor") else [])
       + ["tag @s add cobblers.bo_pending"])
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
    # killed outside a battle by a wild Pokemon (Fight or Flight): the same claim as losing a battle to it (the owner,
    # 2026-09-27: "if it kills the player through damage the same loss of items should happen"). Vanilla's
    # entity_killed_player trigger fires during the death, before the tick's death charge, and `on attacker` names the
    # killer; the battle path's dedupe then stops the death being charged twice. The claim needs the player's name and
    # UUID as text, which only MoLang gives: blackout/remember keeps them (callbacks/player_tick_pre/cobblers_names)
    files["data/%s/advancement/blackout/killed_by_pokemon.json" % NS] = json.dumps({
        "criteria": {"killed": {"trigger": "minecraft:entity_killed_player", "conditions": {"entity": [
            {"condition": "minecraft:entity_properties", "entity": "this", "predicate": {"type": "cobblemon:pokemon"}}]}}},
        "rewards": {"function": "%s:blackout/killed" % NS}}, indent=2) + "\n"
    fn("blackout/killed", [
        "# as a player a Pokemon has just killed, outside a battle",
        "advancement revoke @s only %s:blackout/killed_by_pokemon" % NS,
        "tag @e[type=cobblemon:pokemon,tag=cobblers.victor] remove cobblers.victor",
        "# a wild one only: an owned Pokemon's original trainer is a player",
        'execute on attacker if entity @s[type=cobblemon:pokemon,nbt={Pokemon:{PokemonOriginalTrainerType:"NONE"}}] run tag @s add cobblers.victor',
        "execute unless entity @e[type=cobblemon:pokemon,tag=cobblers.victor] run return 0",
        "function %s:recovery/killed" % NS,
        "tag @e[type=cobblemon:pokemon,tag=cobblers.victor] remove cobblers.victor"])
    fn("blackout/charge", [
        "# %d%% of the balance, rounded up, so any balance above zero loses at least 1 (EXP-040: the query's result is the balance)" % money["percent"],
        "scoreboard players set @s bo.lost 0",
        "execute store result score @s bo.bal run cobbledollars query @s",
        "execute if score @s bo.bal matches 1.. run function %s:blackout/charge_calc" % NS])
    fn("blackout/charge_calc", [
        "# ceil(b * p / 100) as (b / 100) * p + ceil((b mod 100) * p / 100), so no step overflows a 32-bit score (the",
        "# test author's finding: b * p overflowed from about 214 million)",
        "scoreboard players operation @s bo.lost = @s bo.bal",
        "scoreboard players operation @s bo.lost /= #100 bo.cfg",
        "scoreboard players operation @s bo.lost *= #pct bo.cfg",
        "scoreboard players operation #rem bo.tmp = @s bo.bal",
        "scoreboard players operation #rem bo.tmp %= #100 bo.cfg",
        "scoreboard players operation #rem bo.tmp *= #pct bo.cfg",
        "scoreboard players add #rem bo.tmp 99",
        "scoreboard players operation #rem bo.tmp /= #100 bo.cfg",
        "scoreboard players operation @s bo.lost += #rem bo.tmp",
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
        "execute if score @s bo.clm matches 2 run tellraw @s %s" % text(msg["claim_money"], "gold") if money.get("held_by_wild_victor") else "# (money is not held by the victor)",
        "execute if score @s bo.clm matches 3 run tellraw @s %s" % text(msg["npc_no_items"])])

    # ---- checkpoints -----------------------------------------------------------------------------------------------
    validate = ["# bo.ok 1 if the saved checkpoint is still in the data and the saved point is still at it",
                "scoreboard players set @s bo.ok 0"]
    names = ['data modify storage %s:blackout place set value "%s"' % (NS, cfg["pallet"]["name"])]
    healer = ["# as a player who has just used a healing machine: the Center it stands in becomes the checkpoint",
              "advancement revoke @s only %s:blackout/healer_use" % NS]
    ways = ["# as a player who has just jumped a long way: travel through a town waystone lands beside it"]
    for cid, kind, name, x, y, z, r in cps:
        vr = r + 2 if kind == "center" else r * 2     # + 2: the healer area matches a hitbox, not a block
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
        "tag @s remove cobblers.named",
        "tag @s remove cobblers.slayer",
        "scoreboard players set @s bo.mount 0",
        "scoreboard players set @s bo.qual 0",
        "execute store result score @s bo.ox run data get entity @s Pos[0]",
        "execute store result score @s bo.oz run data get entity @s Pos[2]",
        "function %s:recovery/deliver" % NS])

    # ---- claims ----------------------------------------------------------------------------------------------------
    # the claim ledger has a namespace of its own, so Minecraft keeps it in its own file
    # (data/command_storage_cobblers_recovery.dat), which tools/carry_players.py carries into a re-exported world;
    # the shared cobblers storage also holds the re-apply's own progress, which must never be carried
    R = "%s:recovery" % NS            # function paths; storage references are rewritten to LEDGER at the end of build()

    def quota(n, t, pct, mx):
        return ["scoreboard players operation @s %s = @s %s" % (t, n),
                "scoreboard players operation @s %s *= %s bo.cfg" % (t, pct),
                "scoreboard players add @s %s 99" % t,
                "scoreboard players operation @s %s /= #100 bo.cfg" % t,
                "scoreboard players operation @s %s < %s bo.cfg" % (t, mx)]

    fn("recovery/make", [
        "# as the player who lost; $(victor) is the wild victor's entity UUID, $(name) and $(id) the player's name and UUID.",
        "# bo.clm becomes 2 only once a claim is written (recovery/commit): with nothing claimable it stays 0, so no money",
        "# is held and no message says the victor holds it (the test author's finding)",
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
        "# the Pokemon's own UUID as text: what every resolution matches (it survives a faint, a catch and a rebuild;",
        "# the entity UUID does not)",
        "$execute as $(victor) run function %s/pid" % R,
        "data modify storage %s pending.pid set from storage %s pid.s" % (R, R),
        "# persist first (spec: the claim is written before anything is removed); abort if it did not land",
        "data modify storage %s claims append from storage %s pending" % (R, R),
        "data remove storage %s claims[-1].plan" % R,
        "execute store success score #ok bo.tmp run function %s/verify with storage %s pending" % (R, R),
        "$execute if score #ok bo.tmp matches 0 run return run tellraw @s [{\"selector\":\"$(victor)\",\"color\":\"white\"},%s]" % text(msg["claim_nothing"].split("{victor}")[1]),
        "scoreboard players set @s bo.clm 2",
        "function %s/apply" % R,
        "$execute as $(victor) run function %s/bind" % R,
        "function %s/summary" % R,
        '$tellraw @s [{"selector":"$(victor)","color":"white"},%s,{"storage":"%s","nbt":"summary[]","interpret":true,"separator":", "},%s]'
        % (text(msg["claim"].split("{victor}")[1].split("{summary}")[0]), R, text(msg["claim"].split("{summary}")[1]))])
    fn("recovery/verify", [
        "# the claim just written, by its own id: it must hold items, or it is removed so maintenance never rebuilds a",
        "# guardian for it (the test author's finding: clear also counts armour and crafting slots the scan skips)",
        "$execute if data storage %s claims[{id:$(id)}].items[0] run return 1" % R,
        "$data remove storage %s claims[{id:$(id)}]" % R,
        "return fail"])
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
    # the message names each item taken ("10 Ultra Ball"), not its category (the owner, 2026-09-27: "10 Poke Ball(s)"
    # sent them to count the wrong stack)
    fn("recovery/summary", [
        "data modify storage %s summary set value []" % R,
        "data modify storage %s sm set from storage %s pending.items" % (R, R),
        "function %s/summary_next" % R])
    fn("recovery/summary_next", [
        "execute unless data storage %s sm[0] run return 0" % R,
        "data modify storage %s si set value {}" % R,
        "data modify storage %s si.id set from storage %s sm[0].id" % (R, R),
        "data modify storage %s si.key set from storage %s sm[0].id" % (R, R),
        "data modify storage %s si.count set from storage %s sm[0].count" % (R, R),
        "function %s/summary_key with storage %s si" % (R, R),
        "function %s/summary_one with storage %s si" % (R, R),
        "data remove storage %s sm[0]" % R,
        "function %s/summary_next" % R])
    fn("recovery/summary_key", ['$data modify storage %s si.key set from storage %s item_keys."$(id)"' % (R, R)])
    fn("recovery/summary_one", ['$data modify storage %s summary append value \'[{"text":"$(count) "},{"translate":"$(key)"}]\'' % R])

    # a Pokemon's UUID as the text Cobblemon's MoLang `pokemon.id` gives (Java's UUID.toString of the int array):
    # each int's eight hex digits, least significant first (scoreboard %= and /= floor, so a negative int's two's
    # complement digits come out right), joined 8-4-4-4-12
    pid = ["# as a Pokemon entity: its Pokemon UUID as text, into the ledger's pid.s"]
    pid += ["execute store result score #u%d bo.tmp run data get entity @s Pokemon.UUID[%d]" % (w, w) for w in range(4)]
    for w in range(4):
        for p in range(7, -1, -1):
            pid += ["scoreboard players operation #n bo.tmp = #u%d bo.tmp" % w,
                    "scoreboard players operation #n bo.tmp %= #16 bo.cfg",
                    "execute store result storage %s hx.i int 1 run scoreboard players get #n bo.tmp" % R,
                    'data modify storage %s hx.k set value "c%d%d"' % (R, w, p),
                    "function %s/pid_hex with storage %s hx" % (R, R),
                    "scoreboard players operation #u%d bo.tmp /= #16 bo.cfg" % w]
    pid.append("function %s/pid_join with storage %s px" % (R, R))
    fn("recovery/pid", pid)
    fn("recovery/pid_hex", ["$data modify storage %s px.$(k) set from storage %s hex[$(i)]" % (R, R)])
    d = lambda w, ps: "".join("$(c%d%d)" % (w, p) for p in ps)
    fn("recovery/pid_join", ['$data modify storage %s pid.s set value "%s-%s-%s-%s-%s%s"' % (
        R, d(0, range(8)), d(1, range(4)), d(1, range(4, 8)), d(2, range(4)), d(2, range(4, 8)), d(3, range(8)))])

    # resolution by the Pokemon's UUID: a guardian fainting in battle (callbacks/battle_fainted), losing a battle, or
    # being caught (callbacks/pokemon_captured) resolves every open claim its guardian number holds. The first build
    # matched the entity instead, and it never fired in game: a fainted or caught Pokemon's entity is gone before
    # battle_victory and pokemon_captured run, and battle_victory's scriptable_losers leaves it out (2026-09-27)
    fn("recovery/resolve_pid", [
        "# $(pid) the beaten or caught Pokemon's UUID as text, $(resolver) the player's",
        '$data modify storage %s rp set value {pid:"$(pid)",resolver:"$(resolver)"}' % R,
        "data modify storage %s scan set from storage %s claims" % (R, R),
        "function %s/pid_find with storage %s rp" % (R, R),
        "execute unless data storage %s rp.g run return fail" % R,
        "data modify storage %s r set value {}" % R,
        "data modify storage %s r.g set from storage %s rp.g" % (R, R),
        "data modify storage %s r.resolver set from storage %s rp.resolver" % (R, R),
        "data modify storage %s scan set from storage %s claims" % (R, R),
        "function %s/resolve_next" % R,
        "function %s/release with storage %s r" % (R, R),
        "execute as @a at @s run function %s/deliver" % R])
    fn("recovery/pid_find", [
        "execute unless data storage %s scan[0] run return 0" % R,
        "# (a filter cannot follow a list index: the element is copied to a named compound first)",
        "data modify storage %s pcur set from storage %s scan[0]" % (R, R),
        '$execute if data storage %s pcur{pid:"$(pid)",state:"open"} run return run data modify storage %s rp.g set from storage %s pcur.g' % (R, R, R),
        "data remove storage %s scan[0]" % R,
        "function %s/pid_find with storage %s rp" % (R, R)])
    # killed outside a battle, by a player or a player's Pokemon: the same as beating it (the owner, 2026-09-27: "when i
    # killed it with a sword it did respawn though, it should work both ways whether i kill it or my mon does"). Any
    # other death (lava, a fall, another wild Pokemon) leaves the claim open and the guardian is rebuilt, as before
    # Cobblemon removes a killed Pokemon the moment it dies (no dying ticks: staging, 2026-09-27), so the kill cannot be
    # seen when it happens. Instead each guardian's claims note who last hurt it, every tick it has an attacker; when
    # maintenance finds the guardian gone, a note younger than slain_window_ticks settles the claims for that player
    fn("recovery/watch", [
        "# as a guardian, every tick: its attacker, if a player or a player's Pokemon, is noted on its open claims",
        "tag @a remove cobblers.slayer",
        "execute on attacker if entity @s[type=player] run tag @s add cobblers.slayer",
        "execute on attacker if entity @s[type=cobblemon:pokemon] on owner if entity @s[type=player] run tag @s add cobblers.slayer",
        "execute unless entity @a[tag=cobblers.slayer] run return 0",
        "data modify storage %s hit set value {}" % R,
        "execute store result storage %s hit.g int 1 run scoreboard players get @s bo.g" % R,
        "execute store result storage %s hit.t int 1 run time query gametime" % R,
        "execute as @a[tag=cobblers.slayer,limit=1] run function %s/hit_who" % R,
        "tag @a remove cobblers.slayer",
        "execute if data storage %s hit.who run function %s/hit_mark with storage %s hit" % (R, R, R)])
    fn("recovery/hit_who", [
        "data modify storage %s me set value {}" % R,
        "data modify storage %s me.UUID set from entity @s UUID" % R,
        "function %s/hit_who_id with storage %s me" % (R, R)])
    fn("recovery/hit_who_id", ["$data modify storage %s hit.who set from storage %s names[{UUID:$(UUID)}].id" % (R, R)])
    # (guarded: a filtered `set` that matches nothing appends a new element, so a stale guardian with no open claim
    # would add a malformed claim; the test author's finding)
    fn("recovery/hit_mark", ['$execute if data storage %s claims[{g:$(g),state:"open"}] run data modify storage %s claims[{g:$(g),state:"open"}].hit set value {who:"$(who)",t:$(t)}' % (R, R)])
    fn("recovery/vanished", [
        "# a guardian gone from its loaded site: if a player or their Pokemon was hurting it after it was last seen alive",
        "# (maintenance's alive_t), it was killed by them, and the claim is settled for them however long ago that was",
        "# or wherever they went since; otherwise (lava, a fall, another wild Pokemon) it is rebuilt. A note lasts 100",
        "# ticks past the last blow (vanilla's attacker memory), so an old fight never counts",
        "$execute store result score #ht bo.tmp run data get storage %s claims[{id:$(id)}].hit.t" % R,
        "$execute store result score #at bo.tmp run data get storage %s claims[{id:$(id)}].alive_t" % R,
        "$execute if data storage %s claims[{id:$(id)}].hit if score #ht bo.tmp >= #at bo.tmp run return run function %s/slain {id:$(id)}" % (R, R),
        "$function %s/rebuild {g:$(g),x:$(x),y:$(y),z:$(z),id:$(id)}" % R])
    fn("recovery/slain", [
        "data modify storage %s slain set value {}" % R,
        "$data modify storage %s slain.pid set from storage %s claims[{id:$(id)}].pid" % (R, R),
        "$data modify storage %s slain.resolver set from storage %s claims[{id:$(id)}].hit.who" % (R, R),
        "function %s/resolve_pid with storage %s slain" % (R, R)])
    # the kill path's lookup and the names registry (callbacks/player_tick_pre/cobblers_names)
    fn("recovery/killed", [
        "# as a player a wild Pokemon (tagged cobblers.victor) has just killed: the same claim as a battle loss to it",
        "data modify storage %s who set value {}" % R,
        "data modify storage %s me set value {}" % R,
        "data modify storage %s me.UUID set from entity @s UUID" % R,
        "function %s/killed_who with storage %s me" % (R, R),
        "# no name kept yet (they died within five seconds of joining): the death stays environmental",
        'execute if data storage %s who.name run data modify storage %s who.victor set value "@e[type=cobblemon:pokemon,tag=cobblers.victor,limit=1]"' % (R, R),
        "execute if data storage %s who.name run function %s:blackout/battle_loss_wild with storage %s who" % (R, NS, R)])
    fn("recovery/killed_who", ["$data modify storage %s who set from storage %s names[{UUID:$(UUID)}]" % (R, R)])
    fn("recovery/remember", [
        "# as a player: their name and UUID as text, by UUID (from the player_tick_pre callback, once per login)",
        '$data remove storage %s names[{id:"$(id)"}]' % R,
        "data modify storage %s rem set value {}" % R,
        "data modify storage %s rem.UUID set from entity @s UUID" % R,
        '$data modify storage %s rem.name set value "$(name)"' % R,
        '$data modify storage %s rem.id set value "$(id)"' % R,
        "data modify storage %s names append from storage %s rem" % (R, R),
        "tag @s add cobblers.named"])
    # the money a wild victor's win took is held in its claim and paid back with the items
    fn("recovery/hold_money", [
        "# as the player, just after the charge: into the claim this loss wrote, by its own id (never 'the last claim',",
        "# which may be another player's)",
        "function %s/hold_money_at with storage %s pending" % (R, R)])
    fn("recovery/hold_money_at", [
        "$execute if data storage %s claims[{id:$(id),state:\"open\"}] store result storage %s claims[{id:$(id)}].money int 1 run scoreboard players get @s bo.lost" % (R, R)])
    fn("recovery/pay_money", ["$cobbledollars give @s $(money)",
                              '$tellraw @s [%s,{"text":" %s$(money)","color":"white"}]' % (text(msg["recovered_money"]), money["currency_symbol"])])
    fn("recovery/release", [
        "# a guardian still standing for the settled claims (a rebuilt one) goes back to being an ordinary wild Pokemon",
        "$execute as @e[type=cobblemon:pokemon,tag=cobblers.g$(g)] run data merge entity @s {PersistenceRequired:0b}",
        "$scoreboard players reset @e[type=cobblemon:pokemon,tag=cobblers.g$(g)] bo.g",
        "$tag @e[type=cobblemon:pokemon,tag=cobblers.g$(g)] remove cobblers.guardian",
        "$tag @e[type=cobblemon:pokemon,tag=cobblers.g$(g)] remove cobblers.rebuilt",
        "$tag @e[type=cobblemon:pokemon,tag=cobblers.g$(g)] remove cobblers.g$(g)"])

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
        "execute if data storage %s cur.money run function %s/pay_money with storage %s cur" % (R, R, R),
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
        "$function %s/vanished {g:$(g),x:$(x),y:$(y),z:$(z),id:$(id)}" % R])
    fn("recovery/present", [
        "$data modify storage %s claims[{id:$(id)}].seen set value 0" % R,
        "# when it was last seen alive: a kill is a blow noted after this (recovery/vanished)",
        "$execute store result storage %s claims[{id:$(id)}].alive_t int 1 run time query gametime" % R,
        "$execute store result score #n bo.tmp if entity @e[type=cobblemon:pokemon,tag=cobblers.g$(g)]",
        "# a duplicate (a rebuild that raced the original's load): the rebuilt one goes",
        "$execute if score #n bo.tmp matches 2.. run kill @e[type=cobblemon:pokemon,tag=cobblers.g$(g),tag=cobblers.rebuilt,limit=1]",
        "$execute as @e[type=cobblemon:pokemon,tag=cobblers.g$(g)] positioned $(x) $(y) $(z) unless entity @s[distance=..%d] run tp @s $(x) $(y) $(z)" % claims["guardian_leash"]])
    fn("recovery/rebuild", [
        "# a placeholder from Cobblemon's own spawn command, then the ledger's snapshot written over it (tested 2026-09-26).",
        "# The placeholder is the snapshot's own species and level: the client keeps the model it was spawned with, so a",
        "# Magikarp placeholder showed as a Magikarp over a level-60 Ursaring (the owner, 2026-09-27)",
        "$data modify storage %s rb set value {x:$(x),y:$(y),z:$(z)}" % R,
        "$data modify storage %s rb.species set from storage %s claims[{id:$(id)}].snapshot.Species" % (R, R),
        "$data modify storage %s rb.level set from storage %s claims[{id:$(id)}].snapshot.Level" % (R, R),
        "function %s/rebuild_spawn with storage %s rb" % (R, R),
        "$execute positioned $(x) $(y) $(z) as @e[type=cobblemon:pokemon,tag=!cobblers.guardian,distance=..1,limit=1,sort=nearest] run function %s/rebuild_as {g:$(g),id:$(id)}" % R])
    fn("recovery/rebuild_spawn", ["$execute positioned $(x) $(y) $(z) run spawnpokemonat ~ ~ ~ $(species) level=$(level)"])
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
        "# the Surf bonus counter starts at 0: unset, water/deep's `bo.surf < #surf` test fails and a player who never",
        "# blacked out (blackout/arrive was its only setter) got no Surf bonus at all (the contract check C2's finding)",
        "execute unless score @s bo.surf matches -2147483648.. run scoreboard players set @s bo.surf 0",
        "scoreboard players set @s bo.sub 0",
        "scoreboard players set @s bo.deep 0",
        "execute anchored eyes positioned ^ ^ ^ if block ~ ~ ~ #%s:water run scoreboard players set @s bo.sub 1" % NS,
        "execute if score @s bo.sub matches 1 anchored eyes positioned ^ ^ ^ %s run scoreboard players set @s bo.deep 1" % deep_chain,
        "scoreboard players set @s bo.brth 0",
        "function %s:water/qualify" % NS,
        "# Dive's swim speed: in any water, with the Dive training and a Dive partner (the owner, 2026-09-26)",
        "scoreboard players set #swim bo.tmp 0",
        "execute if score @s bo.qual matches 2 if block ~ ~ ~ #%s:water run scoreboard players set #swim bo.tmp 1" % NS,
        "execute if score @s bo.qual matches 2 if score @s bo.sub matches 1 run scoreboard players set #swim bo.tmp 1",
        "execute if score #swim bo.tmp matches 1 unless score @s bo.swim matches 1 run function %s:water/swim_on" % NS,
        "execute if score #swim bo.tmp matches 0 if score @s bo.swim matches 1 run function %s:water/swim_off" % NS,
        "execute if score @s bo.sub matches 0 run function %s:water/surfaced" % NS,
        "execute if score @s bo.sub matches 1 store result score @s bo.air run data get entity @s Air",
        "execute if score @s bo.sub matches 1 if score @s bo.deep matches 1 run function %s:water/deep" % NS,
        "execute if score @s bo.brth matches 0 if score @s bo.hasmod matches 1 run function %s:water/unbreathe" % NS,
        "function %s:water/strip_vanilla" % NS])
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
        "# time under Dive counts against the Surf bonus too: it belongs to one submersion, so losing the Dive partner",
        "# underwater never hands out a fresh Surf timer (spec 'Entering, swapping and leaving depth')",
        "execute if score @s bo.qual matches 2 if score @s bo.surf < #surf bo.cfg run scoreboard players add @s bo.surf 1",
        "execute if score @s bo.qual matches 2 run return run function %s:water/breathing" % NS,
        "execute if score @s bo.qual matches 1 if score @s bo.surf < #surf bo.cfg run return run function %s:water/surf_breath" % NS,
        "execute if score @s bo.air <= #airwarn bo.cfg if score @s bo.warn matches 0 run function %s:water/warn_low" % NS,
        "execute if score @s bo.air matches ..0 run function %s:water/out" % NS])
    fn("water/breathing", [
        "# the ladder's air: a large oxygen_bonus (vanilla keeps air with chance bonus/(bonus+1) each tick), not the",
        "# Water Breathing effect, which the pack removes from everything else (the owner, 2026-09-26)",
        "scoreboard players set @s bo.pulse 0",
        "scoreboard players set @s bo.warn 0",
        "scoreboard players set @s bo.brth 1",
        "execute unless score @s bo.hasmod matches 1 run attribute @s minecraft:generic.oxygen_bonus modifier add cobblers:ladder %d add_value" % water["ladder_oxygen_bonus"],
        "scoreboard players set @s bo.hasmod 1"])
    fn("water/swim_on", [
        "attribute @s minecraft:generic.water_movement_efficiency modifier add cobblers:dive_swim %s add_value" % water["dive_swim_efficiency"],
        "# efficiency (Depth Strider's attribute) mostly helps walking in water and is halved while swimming; the swim",
        "# speed itself comes from movement_speed, which water movement scales by that efficiency (the owner felt no",
        "# difference with efficiency alone, 2026-09-26)",
        "attribute @s minecraft:generic.movement_speed modifier add cobblers:dive_swim %s add_multiplied_base" % water["dive_swim_speed"],
        "scoreboard players set @s bo.swim 1"])
    fn("water/swim_off", [
        "attribute @s minecraft:generic.water_movement_efficiency modifier remove cobblers:dive_swim",
        "attribute @s minecraft:generic.movement_speed modifier remove cobblers:dive_swim",
        "scoreboard players set @s bo.swim 0"])
    fn("water/surf_breath", [
        "# counted after the test, so the bonus lasts exactly surf_bonus_ticks",
        "scoreboard players add @s bo.surf 1",
        "function %s:water/breathing" % NS])
    fn("water/unbreathe", [
        "attribute @s minecraft:generic.oxygen_bonus modifier remove cobblers:ladder",
        "scoreboard players set @s bo.hasmod 0"])
    fn("water/strip_vanilla", [
        "# vanilla air is not a way round the ladder: Water Breathing (potions, turtle shells) and Conduit Power are",
        "# cleared the tick they land; Respiration is neutralised by the enchantment override in this pack",
        "execute store success score #wb bo.tmp run effect clear @s minecraft:water_breathing",
        "execute store success score #cp bo.tmp run effect clear @s minecraft:conduit_power",
        "scoreboard players operation #wb bo.tmp += #cp bo.tmp",
        "execute if score #wb bo.tmp matches 1.. unless entity @s[tag=cobblers.air_told] run tellraw @s %s" % text(msg["vanilla_air"], "yellow"),
        "execute if score #wb bo.tmp matches 1.. run tag @s add cobblers.air_told"])
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

    # ---- swim fatigue ----------------------------------------------------------------------------------------------
    # Every swim builds fatigue, in any water (the owner, 2026-09-27: "fatigue on every swim ... a new player should
    # struggle with water"); water deeper than deep_water_blocks under the swimmer builds it faster. Land, wading
    # (standing on the bottom, head out) and riding recover it. No map: the water under the player decides.
    surf = cfg["surface"]
    per = surf["sample_ticks"]
    consts_s = {"#fgain1": surf["gain_shallow_per_tick"] * per, "#fgain2": surf["gain_deep_per_tick"] * per,
                "#frec": surf["recover_per_tick"] * per, "#fwarn": surf["warn_ticks"], "#fslow": surf["slow_ticks"],
                "#fexh": surf["exhausted_ticks"], "#fcol": surf["collapse_ticks"], "#fpulse": surf["pulse_ticks"],
                "#fcap": surf["cap_ticks"], "#fsample": per}
    # the feet's block and the blocks under it: deep_water_blocks of water there is deep water
    # (the feet's own block too: the first line lets a player through on their eyes alone; the test author's finding)
    under = " ".join("if block ~ ~%d ~ #%s:water" % (-i, NS) for i in range(0, surf["deep_water_blocks"]))
    files["data/%s/function/surface/load.mcfunction" % NS] = "\n".join(
        ["scoreboard players set %s bo.cfg %d" % (k, v) for k, v in consts_s.items()]) + "\n"
    load_tag = json.loads(files["data/minecraft/tags/function/load.json"])
    load_tag["values"].append("%s:surface/load" % NS)
    files["data/minecraft/tags/function/load.json"] = json.dumps(load_tag, indent=2) + "\n"
    fn("surface/tick", [
        "# as and at a player every %d ticks: a swimmer (in water, riding nothing, not wading) builds fatigue" % per,
        "scoreboard players set #ride bo.tmp 0",
        "execute store success score #ride bo.tmp on vehicle if entity @s",
        "# a boat on rough sea water tips its rider out (data/blackout.json boats, option C); a ridden Pokemon is not a boat.",
        "# First, because a boat's rider sits with their feet above the water",
        "scoreboard players set #boat bo.tmp 0",
        "execute store success score #boat bo.tmp on vehicle if entity @s[type=#%s:boats]" % NS,
        "execute if score #boat bo.tmp matches 1 run function %s:boat/check" % NS,
        "# (reset first: `store success ... on vehicle` stores nothing when there is no vehicle, so a rider just tipped",
        "# out kept #ride 1 and recovered for one sample; the test author's finding)",
        "scoreboard players set #ride bo.tmp 0",
        "execute store success score #ride bo.tmp on vehicle if entity @s",
        "execute if score #ride bo.tmp matches 1 run return run function %s:surface/recover" % NS,
        "execute unless block ~ ~ ~ #%s:water unless score @s bo.sub matches 1 run return run function %s:surface/recover" % (NS, NS),
        "# wading: on the bottom with the head out of the water is walking, not swimming",
        "execute if score @s bo.sub matches 0 if entity @s[nbt={OnGround:1b}] run return run function %s:surface/recover" % NS,
        "# a trained player (Surf or Dive with a capable partner) under water neither tires nor recovers: air alone limits",
        "# dives (the owner, 2026-09-27: 'Fatigue is the surface gate, air is the underwater gate, and they should not",
        "# fight'). The first every-swim rule knocked a Dive player out after 33 s under water (WATER_BUILD_PLAN F1)",
        "execute if score @s bo.qual matches 1.. if score @s bo.sub matches 1 run return 0",
        "# 1 shallow water, 2 deep water (deep_water_blocks of water from the feet down, or the eyes at depth)",
        "scoreboard players set @s bo.zone 1",
        "execute %s run scoreboard players set @s bo.zone 2" % under if under else "scoreboard players set @s bo.zone 2",
        "execute if score @s bo.deep matches 1 run scoreboard players set @s bo.zone 2",
        "# a trained water partner in the party halves the strain (qualification from the water ladder)",
        "scoreboard players operation #g bo.tmp = #fgain1 bo.cfg",
        "execute if score @s bo.zone matches 2 run scoreboard players operation #g bo.tmp = #fgain2 bo.cfg",
        "execute if score @s bo.qual matches 1.. run scoreboard players operation #g bo.tmp /= #2 bo.cfg",
        "# the pulse clock stays primed below collapse, so the first hit lands the sample collapse is reached",
        "execute if score @s bo.fat < #fcol bo.cfg run scoreboard players operation @s bo.fpt = #fpulse bo.cfg",
        "scoreboard players operation @s bo.fat += #g bo.tmp",
        "scoreboard players operation @s bo.fat < #fcap bo.cfg",
        "execute if score @s bo.fat >= #fwarn bo.cfg if score @s bo.fwarn matches ..0 run function %s:surface/warn_tiring" % NS,
        "execute if score @s bo.fat >= #fslow bo.cfg run effect give @s minecraft:slowness 2 0 true",
        "execute if score @s bo.fat >= #fexh bo.cfg run effect give @s minecraft:slowness 2 1 true",
        "execute if score @s bo.fat >= #fexh bo.cfg run effect give @s minecraft:hunger 2 0 true",
        "execute if score @s bo.fat >= #fexh bo.cfg if score @s bo.fwarn matches ..1 run function %s:surface/warn_exhausted" % NS,
        "execute if score @s bo.fat >= #fcol bo.cfg run function %s:surface/collapse" % NS])
    # ---- boats: shallows craft (data/blackout.json boats, option C) ------------------------------------------------
    boats = cfg.get("boats") or {}
    files["data/%s/tags/entity_type/boats.json" % NS] = json.dumps({"values": ["minecraft:boat", "minecraft:chest_boat"]}, indent=2) + "\n"
    check = [
        "# as and at a player in a boat: 0 shallows or land, 1 open, 2 deep, from tools/open_water.py's bands at",
        "# boats.rough_blocks on the canonical heightmap, one function per 16-block cell row",
        "scoreboard players set @s bo.zone 0",
        "execute store result score #cx bo.tmp run data get entity @s Pos[0]",
        "execute store result score #cz bo.tmp run data get entity @s Pos[2]",
        "scoreboard players operation #cx bo.tmp += #wmin bo.cfg",
        "scoreboard players operation #cz bo.tmp += #wmin bo.cfg",
        "scoreboard players operation #cx bo.tmp /= #16 bo.cfg",
        "scoreboard players operation #cz bo.tmp /= #16 bo.cfg",
        "execute store result storage %s:blackout sea.z int 1 run scoreboard players get #cz bo.tmp" % NS,
        "function %s:boat/row with storage %s:blackout sea" % (NS, NS),
        "execute if score @s bo.zone matches 0 run return 0"]
    for s in boats.get("sheltered", []):
        x0, z0, x1, z1 = s["box"]
        check.append("# sheltered: %s" % s["id"])
        check.append("execute if entity @s[x=%d,y=-64,z=%d,dx=%d,dy=640,dz=%d] run return 0" % (x0, z0, x1 - x0, z1 - z0))
    check += ["ride @s dismount",
              "title @s actionbar %s" % text(boats.get("message", "Too rough for a boat."), "gold")]
    fn("boat/check", check)
    fn("boat/row", ["$function %s:boat/r/$(z)" % NS])
    for z, runs in sorted((boat_rows or {}).items()):
        fn("boat/r/%d" % z, ["execute if score #cx bo.tmp matches %d..%d run return run scoreboard players set @s bo.zone %d" % (a, b, v)
                             for a, b, v in runs])
    fn("surface/recover", [

        "execute if score @s bo.fat matches 1.. run scoreboard players operation @s bo.fat -= #frec bo.cfg",
        "execute if score @s bo.fat matches ..0 run scoreboard players set @s bo.fat 0",
        "execute if score @s bo.fat < #fwarn bo.cfg run scoreboard players set @s bo.fwarn 0",
        "# the pulse clock is primed again only below collapse: a touch of land past collapse must not bring the next",
        "# hit early (the test author's finding)",
        "execute if score @s bo.fat < #fcol bo.cfg run scoreboard players operation @s bo.fpt = #fpulse bo.cfg"])
    fn("surface/warn_tiring", ["tellraw @s %s" % text(msg["surface_tiring"], "yellow"), "scoreboard players set @s bo.fwarn 1"])
    fn("surface/warn_exhausted", ["tellraw @s %s" % text(msg["surface_exhausted"], "red"), "scoreboard players set @s bo.fwarn 2"])
    fn("surface/collapse", [
        "# past collapse, one hit every pulse_ticks of time (its own clock, bo.fpt, so the band and a partner change",
        "# how fast fatigue grows, never how often the hits land): the same half-health hit as drowning",
        "execute unless score @s bo.fpt matches -2147483648.. run scoreboard players operation @s bo.fpt = #fpulse bo.cfg",
        "scoreboard players operation @s bo.fpt += #fsample bo.cfg",
        "execute if score @s bo.fpt < #fpulse bo.cfg run return 0",
        "scoreboard players set @s bo.fpt 0",
        "execute if score @s bo.fwarn matches ..2 run tellraw @s %s" % text(msg["surface_collapse"], "red"),
        "execute if score @s bo.fwarn matches ..2 run scoreboard players set @s bo.fwarn 3",
        "function %s:water/pulse" % NS])

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
        "'Generated by tools/blackout_pack.py. A player who lost with the whole party fainted runs the blackout (running';",
        "'away is not a blackout: the owner lost $179 and a claim for fleeing, 2026-09-27); a guardian that lost resolves';",
        "'its claims by its Pokemon UUID (pokemon.id).';",
        "t.kind = 'other';",
        "t.victor = '';",
        "for_each(t.w, c.scriptable_winners, {",
        "  t.kind == 'other' ? {",
        "    t.w.is_pokemon ? { t.kind = 'wild'; t.victor = t.w.uuid; };",
        "    t.w.is_npc ? { t.kind = 'npc'; t.victor = t.w.uuid; };",
        "  };",
        "});",
        "for_each(t.pl, c.player_losers, {",
        "  t.plr = t.pl.player;",
        "  t.party = t.plr.party;",
        "  t.alive = 0;",
        "  for_each(t.p, t.party.pokemon, { t.p.current_hp > 0 ? { t.alive = t.alive + 1; }; });",
        "  t.alive == 0 ? {",
        "    q.run_command('execute as ' + t.plr.uuid + ' run function %s:blackout/battle_loss_' + t.kind + ' {victor:\"' + t.victor + '\",name:\"' + t.plr.username + '\",id:\"' + t.plr.uuid + '\"}');" % NS,
        "  };",
        "});",
        "for_each(t.l, c.scriptable_losers, {",
        "  t.l.is_pokemon ? {",
        "    t.lp = t.l.pokemon;",
        "    t.lpid = t.lp.id;",
        "    for_each(t.pw, c.player_winners, {",
        "      t.pwp = t.pw.player;",
        "      q.run_command('function %s:recovery/resolve_pid {pid:\"' + t.lpid + '\",resolver:\"' + t.pwp.uuid + '\"}');" % NS,
        "    });",
        "  };",
        "});",
        ""])
    files["data/cobblemon/callbacks/battle_fainted/cobblers_recovery.molang"] = "\n".join([
        "'Generated by tools/blackout_pack.py. A wild Pokemon fainting in battle resolves any claim it guards, credited to';",
        "'the first player in the battle. This is where defeat is seen: by battle_victory the entity is gone.';",
        "c.pokemon.actor.is_wild ? {",
        "  t.pk = c.pokemon.pokemon;",
        "  t.pid = t.pk.id;",
        "  t.done = 0;",
        "  for_each(t.a, c.players, {",
        "    t.done == 0 ? {",
        "      t.pl = t.a.player;",
        "      q.run_command('function %s:recovery/resolve_pid {pid:\"' + t.pid + '\",resolver:\"' + t.pl.uuid + '\"}');" % NS,
        "      t.done = 1;",
        "    };",
        "  });",
        "};",
        ""])
    files["data/cobblemon/callbacks/pokemon_captured/cobblers_recovery.molang"] = "\n".join([
        "'Generated by tools/blackout_pack.py. Catching a guardian resolves its claims for their owners (spec: rescue without';",
        "'theft), matched by its Pokemon UUID: the entity is gone by the time this runs.';",
        "t.pk = q.pokemon;",
        "t.pid = t.pk.id;",
        "q.run_command('function %s:recovery/resolve_pid {pid:\"' + t.pid + '\",resolver:\"' + q.player.uuid + '\"}');" % NS,
        ""])
    files["data/cobblemon/callbacks/player_tick_pre/cobblers_names.molang"] = "\n".join([
        "'Generated by tools/blackout_pack.py. Once per login (and every 5 s until done): the player name and UUID as text,';",
        "'for a claim made when a wild Pokemon kills them outside a battle (blackout/killed).';",
        "math.mod(q.player.world.game_time, 100) != 0 ? { return 0; };",
        "q.run_command('execute as ' + q.player.uuid + ' unless entity @s[tag=cobblers.named] run function %s:recovery/remember {name:\"' + q.player.username + '\",id:\"' + q.player.uuid + '\"}');" % NS,
        ""])
    # the claim ledger's storage has a namespace of its own (see LEDGER); function paths keep cobblers:recovery/...
    for k, v in files.items():
        v = re.sub(r"storage cobblers:recovery(?=[ \n])", "storage " + LEDGER, v)
        files[k] = v.replace('"storage":"cobblers:recovery"', '"storage":"%s"' % LEDGER)
    return files


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    cfg = load("blackout.json")
    # the boats' rough water: tools/open_water.py's bands on the canonical heightmap (never a world), as row runs
    import open_water
    if open_water.WORLD_MIN != -1024:
        raise SystemExit("boat/check's #wmin is 1024 but tools/open_water.py's WORLD_MIN is %d" % open_water.WORLD_MIN)
    b = open_water.bands(cfg["boats"]["rough_blocks"], cfg["boats"]["deep_blocks"])
    boat_rows = {}
    for code, key in ((1, "open"), (2, "deep")):
        m = b[key]
        for z in range(m.shape[0]):
            x = 0
            while x < m.shape[1]:
                if m[z, x]:
                    x0 = x
                    while x < m.shape[1] and m[z, x]:
                        x += 1
                    boat_rows.setdefault(z, []).append((x0, x - 1, code))
                else:
                    x += 1
    files = build(cfg, load("water_mounts.json"), load("placements.json"), load("progression.json"), boat_rows)
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
