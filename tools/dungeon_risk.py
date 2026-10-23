#!/usr/bin/env python
"""The dungeon risk: the Run Stash and its Run Satchel, the exit's Take it all / Sell it all, and the catch ledger.

Spec: docs/mechanics/DUNGEON_RISK.md. Data: data/dungeon_risk.json. Generated INTO the cobblers_dungeons pack by
tools/dungeon.py build() (functions under cobblers:dungeons/risk/..., a pokemon_captured callback, and a marker on every
dungeon loot table), like tools/dungeon_greed.py and the other dungeon_* units. NOTHING here has run in game
(experiments/EXP-098-dungeon-risk).

The rule (the owner, 2026-10-23): everything found in a run is at risk until a clean exit, except relics and cool
catches. Concretely:

  stash     Every item a run gains goes to the player's Run Stash in command storage (cobblers:dg_risk s.p<dg.id>),
            never into the inventory: each tick, (1) every item entity within stash.absorb_radius of a live member
            (dg.st 3..4, in cobblers:pocket) with no Thrower and no Owner and no skip key is copied into the stash and
            killed; (2) every inventory item carrying the gain key (every dungeon loot table sets it, so a chest's or a
            `loot give`'s items carry it) is copied into the stash and its slot emptied (item replace, slot by slot,
            never `clear`, which would also reach the cursor and the crafting grid).
  satchel   A carrot on a stick named Run Satchel, given at arrival with the pick, taken back wherever the pick is. A
            right-click (the minecraft.used stat) summons a wandering trader in front of the player whose offers ARE
            the stash, every one out of stock: the vanilla trade screen shows each item and nothing can be taken.
  exit      A clean exit (dungeon `pay`) keeps the stash and offers Take it all / Sell it all / List it by /trigger. The
            sale pays the bank's price (tools/markets.py bank_prices) plus a small bonus, verified on the balance; a
            failed pay delivers everything instead. No answer in exit.choice_ticks online: Take it all. Every delivery
            is an item entity at the player's feet with their Owner, PickupDelay 0 and Age -32768 (never despawns).
  death     Every other way out (risk/forfeit at the top of m/end and slot/s<g>/end): the stash is deleted and any
            marked item left in the inventory is cleared.
  catches   The pokemon_captured callback logs every catch made in a live run with its Pokemon UUID (q.pokemon.id),
            except a shiny and any species a dungeon's prize can be (never logged, so never removable). A clean exit
            keeps them. Any other end looks each one up BY UUID in the party and the PC: catches.mode dry_run (the
            default) LOGS what it would remove and removes nothing; remove takes it with remove_by_id only out of
            battle, holding no item, and never the party's last Pokemon. Not found: nothing, logged.

What this does NOT cover (say so; CLAUDE.md "Our list is not the world"): an item given straight into the inventory by
a command that carries no gain key (givepokemonegg's egg; a relic, deliberately); an item a player holds on the cursor
at the moment a run ends cleanly (it keeps its gain key, harmlessly); a wild Pokemon drop if Cobblemon gives it an
Owner or a Thrower (then it is kept, the safe side); an item entity further than absorb_radius when it is picked up.

  python tools/dungeon_risk.py --report     the counts and the mode; writes nothing
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "dungeon_risk.json"
SCHEMA = "cobblers.dungeon_risk/1"
CALLBACK_PATH = "data/cobblemon/callbacks/pokemon_captured/cobblers_dungeon_risk.molang"
POCKET = "cobblers:pocket"
ID = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_/.-]+$")
# objectives: 16 characters at most; on a player unless marked
OBJ = {
    "used": "dg.rku",    # minecraft.used:minecraft.carrot_on_a_stick (data satchel.use_objective)
    "choice": "dg.rkc",  # trigger: 1 take, 2 sell, 3 list (data exit.choice_objective)
    "wait": "dg.rkw",    # 1 a clean exit's satchel waits for its choice; 2 a clean exit with nothing to choose
    "left": "dg.rkt",    # ticks left to choose (counted only online)
    "bonus": "dg.rkb",   # the sale's bonus percent, fixed at the exit
    "owner": "dg.rkv",   # on a viewer: its player's dg.id
    "life": "dg.rkl",    # on a viewer: ticks left
}
SEEN_TAG = "dg.rkx"     # an item entity the sweep has looked at and left (a Thrower, an Owner, a skip key)
NEW_TAG = "dg.rk_new"
ME_TAG = "dg.rk_me"
OUTCOMES = {             # the catch reaper's results (log field o)
    0: "not_found", 1: "would_remove_party", 2: "would_remove_pc", 3: "removed_party", 4: "removed_pc",
    5: "kept_holds_item", 6: "kept_in_battle", 7: "kept_last_in_party", 8: "kept_remove_failed"}


class RiskError(ValueError):
    pass


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _D():
    import dungeon as D
    return D


# ------------------------------------------------------------------------------------------------- the data's values


def store(rk):
    return rk["storage"]


def gain_key(rk):
    return rk["stash"]["gain_key"]


def gain_pred(rk):
    return "*[minecraft:custom_data~{%s:1b}]" % gain_key(rk)


def satchel_match(rk):
    s = rk["satchel"]
    return "%s[minecraft:custom_data~{%s:1b}]" % (s["item"], s["custom_data_key"])


def satchel_give(rk):
    D = _D()
    s = rk["satchel"]
    lore = ",".join(D.snbt_str(D.text(x, "gray")) for x in s["lore"])
    return ("%s[minecraft:custom_data={%s:1b},minecraft:item_name=%s,minecraft:lore=[%s],minecraft:enchantment_glint_override=true]"
            % (s["item"], s["custom_data_key"], D.snbt_str(D.text(s["name"], s["colour"])), lore))


def use_criterion(rk):
    """`minecraft.used:minecraft.carrot_on_a_stick`: the stat type and the item id, each with a dot for its colon (the
    form EXP-073 step 2 proved for minecraft.mined)."""
    return "minecraft.used:" + rk["satchel"]["item"].replace(":", ".")


def bank_prices():
    """{item: the bank's unit price}: the list CobbleDollars' bank pays (tools/markets.py bank_prices)."""
    import markets
    return {k: int(v) for k, v in markets.bank_prices().items() if int(v) > 0}


def prize_species(doc):
    """{dungeon index (1..): sorted species ids} every prize of the dungeon can be at any band, rare or legendary
    (tools/dungeon_prize.pool_at), and the roster's spine boss: the dungeon's reward Pokemon, never at stake."""
    import dungeon_prize as DPz
    import dungeon_rooms as R
    D = _D()
    out = {}
    for di, d in enumerate(D.dungeons(doc), 1):
        sp = set()
        if R.has_rooms(d):
            for r in R.all_records(d):
                if not DPz.prize_of(r):
                    continue
                for b in DPz.band_rows(doc):
                    got = DPz.pool_at(doc, r, b["band"])
                    if got:
                        sp.update(got[0])
        e = DPz.roster_entry(d["id"])
        if isinstance(e, dict):
            for key in ("rare_pool_by_band", "legendary_pool_by_band"):
                for lst in (e.get(key) or {}).values():
                    sp.update(lst or [])
            boss = (e.get("ub_boss") or {}).get("species")
            sp.update([boss] if isinstance(boss, str) else [b for b in boss or [] if isinstance(b, str)])
        out[di] = sorted(s if ":" in s else "cobblemon:" + s for s in sp)
    return out


def skip_keys_expected():
    """The custom_data keys other units put on items that must never be stashed, read from those units."""
    import dungeon_extras2 as DX2
    import dungeon_relics as DRel
    D = _D()
    doc = D.load()
    return {DRel.CUSTOM_KEY, doc["engine"]["rift_pick"]["custom_data_key"], doc["engine"]["sigils"]["custom_data_key"],
            DX2.ROD_KEY}


def problems(rk, doc=None):
    """Fail closed on data the generator would misread."""
    bad = []
    if rk.get("schema") != SCHEMA:
        bad.append("schema is not %s" % SCHEMA)
    mode = (rk.get("catches") or {}).get("mode")
    if mode not in (rk.get("catches") or {}).get("modes", {}):
        bad.append("catches.mode %r is not one of catches.modes" % mode)
    st = rk.get("stash") or {}
    if not re.match(r"^[a-z0-9_]+$", st.get("gain_key") or ""):
        bad.append("stash.gain_key must be a plain lowercase key")
    pre = st.get("loot_table_prefix") or ""
    if not pre.startswith("data/cobblers/loot_table/dungeons/"):
        bad.append("stash.loot_table_prefix must stay under data/cobblers/loot_table/dungeons/ (never a global table)")
    for f in st.get("fungible") or []:
        if not ID.match(f):
            bad.append("stash.fungible %r is not an item id" % f)
    r = st.get("absorb_radius")
    if not isinstance(r, int) or not 2 <= r <= 16:
        bad.append("stash.absorb_radius must be an int 2..16")
    for tg in st.get("skip_item_tags_on_ground") or []:
        if not (isinstance(tg, str) and tg.startswith("#") and ID.match(tg[1:])):
            bad.append("stash.skip_item_tags_on_ground %r is not an item tag (#namespace:path)" % tg)
    if sorted(st.get("skip_item_entity_fields") or []) != ["Owner", "Thrower"]:
        bad.append("stash.skip_item_entity_fields must be exactly Thrower and Owner (a player's drop, a give's overflow)")
    try:
        want = skip_keys_expected()
    except Exception as e:  # noqa: BLE001 - a unit that cannot load is a problem to name, not a crash
        want = set()
        bad.append("could not read the other units' item keys: %s" % e)
    missing = sorted(want - set(st.get("skip_custom_data_keys") or []))
    if missing:
        bad.append("stash.skip_custom_data_keys lacks %s (a relic, the pick, a sigil or the lent rod would be stashed)" % missing)
    sa = rk.get("satchel") or {}
    if sa.get("custom_data_key") not in (st.get("skip_custom_data_keys") or []):
        bad.append("the satchel's own key must be in stash.skip_custom_data_keys")
    if sa.get("item") != "minecraft:carrot_on_a_stick":
        bad.append("satchel.item must be minecraft:carrot_on_a_stick: its use is the statistic the hook reads")
    ex = rk.get("exit") or {}
    if ex.get("choice_default") != "take":
        bad.append("exit.choice_default must be take: an unanswered exit never loses an item")
    if doc is not None:
        bands = [str(b["band"]) for b in doc["engine"]["bands"]]
        if sorted((ex.get("bonus_pct_by_band") or {}).keys()) != sorted(bands):
            bad.append("exit.bonus_pct_by_band must name every band %s" % bands)
    for k, v in list((ex.get("bonus_pct_by_band") or {}).items()) + [("boss", ex.get("boss_bonus_pct"))]:
        if not isinstance(v, int) or not 0 <= v <= 25:
            bad.append("exit bonus %s must be an int 0..25 percent (small on purpose)" % k)
    lm = (rk.get("catches") or {}).get("log_max")
    if not isinstance(lm, int) or lm < 16:
        bad.append("catches.log_max must be an int >= 16")
    return bad


# ------------------------------------------------------------------------------------------------- functions


def _tell(msg, colour="gray"):
    return "tellraw @s %s" % json.dumps({"text": msg, "color": colour}, ensure_ascii=False)


def _tell_parts(parts):
    return "tellraw @s %s" % json.dumps([""] + parts, ensure_ascii=False)


def functions(doc, rk=None, prices=None, prizes=None):
    """{name under cobblers:dungeons/: lines}."""
    rk = rk or load()
    bad = problems(rk, doc)
    if bad:
        raise RiskError("data/dungeon_risk.json: " + "; ".join(bad))
    D = _D()
    F, HEAD, O = D.F, D.HEAD, D.OBJ
    t = O["t"]
    R = store(rk)
    K = gain_key(rk)
    st, sa, ex, ca = rk["stash"], rk["satchel"], rk["exit"], rk["catches"]
    prices = bank_prices() if prices is None else prices
    prizes = prize_species(doc) if prizes is None else prizes
    run_tag = D.blackout_terms()["tag"]
    lines_x, lines_c = ex["lines"], ca["lines"]
    out = {}

    def fn(name, lines, note):
        out["risk/" + name] = [HEAD, "# DUNGEON RISK (tools/dungeon_risk.py, data/dungeon_risk.json): " + note] + lines

    def RF(name):
        return F("risk/" + name)

    price_list = ",".join('{id:"%s",p:%d}' % (k, v) for k, v in sorted(prices.items()))
    fung_list = ",".join('{id:"%s"}' % f for f in st["fungible"])
    fn("load", [
        "scoreboard objectives add %s %s" % (OBJ["used"], use_criterion(rk)),
        "scoreboard objectives add %s trigger" % OBJ["choice"],
        ] + ["scoreboard objectives add %s dummy" % OBJ[k] for k in ("wait", "left", "bonus", "owner", "life")] + [
        "scoreboard players set #64 %s 64" % t,
        "scoreboard players set #63 %s 63" % t,
        "scoreboard players set #100 %s 100" % t,
        "# the catch mode, from data (catches.mode %s): 1b removes, 0b only logs. Set at every load, so data is the" % ca["mode"],
        "# only switch",
        "data modify storage %s cfg set value {remove:%s}" % (R, "1b" if ca["mode"] == "remove" else "0b"),
        "# the bank's unit prices (tools/markets.py bank_prices: %d items) and the fungible ids" % len(prices),
        "data modify storage %s prices set value [%s]" % (R, price_list),
        "data modify storage %s fung set value [%s]" % (R, fung_list),
        "execute unless data storage %s s run data modify storage %s s set value {}" % (R, R),
        "execute unless data storage %s ledger run data modify storage %s ledger set value []" % (R, R),
        "execute unless data storage %s log run data modify storage %s log set value []" % (R, R),
        "execute unless data storage %s lw run data modify storage %s lw set value {}" % (R, R)],
        "objectives, the mode, the price list")

    fn("tick", [
        "# 1. the live members' gains into their stash (in the pocket only)",
        "execute as @a[scores={%s=3..4}] at @s if dimension %s run function %s" % (O["st"], POCKET, RF("sweep")),
        "# 2. a satchel used",
        "execute as @a[scores={%s=1..}] at @s run function %s" % (OBJ["used"], RF("satchel/use")),
        "# 3. the satchel's views age out",
        "execute as @e[type=%s,tag=%s] run function %s" % (sa["view"]["entity"], sa["view"]["tag"], RF("view/age")),
        "# 4. the exit's choice, and its wait",
        "execute as @a[scores={%s=1..}] at @s run function %s" % (OBJ["choice"], RF("exit/choose")),
        "execute as @a[scores={%s=1}] at @s run function %s" % (OBJ["wait"], RF("exit/wait"))],
        "every tick (tick.json)")

    # ---- the stash: absorbing ----------------------------------------------------------------------------------
    fn("sweep", [
        "execute store result storage %s a.id int 1 run scoreboard players get @s %s" % (R, O["id"]),
        "scoreboard players set #ab %s 0" % t,
        "# marked items in the inventory (a chest's, a loot give's): every slot the NBT shows",
        "execute if items entity @s container.* %s run function %s" % (gain_pred(rk), RF("absorb/inv")),
        "execute if items entity @s weapon.offhand %s run function %s" % (gain_pred(rk), RF("absorb/inv")),
        "execute if items entity @s armor.* %s run function %s" % (gain_pred(rk), RF("absorb/inv")),
        "# loose items near them: a block's drop, a wild Pokemon's drop, a fished item, a loot spawn",
        "execute as @e[type=minecraft:item,distance=..%d,tag=!%s] run function %s" % (st["absorb_radius"], SEEN_TAG, RF("absorb/entity")),
        "execute if score #ab %s matches 1.. run title @s actionbar %s" % (t, D.text(st["absorbed_line"], "light_purple")),
        "execute if score #ab %s matches 1.. run playsound minecraft:item.bundle.insert master @s ~ ~ ~ 0.8 1" % t],
        "as and at a live member in the pocket, every tick")
    ent = ["# as and at an item entity near a live member (whose dg.id is in a.id)"]
    for f in st["skip_item_entity_fields"]:
        ent.append("execute if data entity @s %s run return run tag @s add %s" % (f, SEEN_TAG))
    for tg in st.get("skip_item_tags_on_ground") or []:
        ent.append("execute if items entity @s contents %s run return run tag @s add %s" % (tg, SEEN_TAG))
    for k in st["skip_custom_data_keys"]:
        ent.append("execute if data entity @s Item.components.\"minecraft:custom_data\".%s run return run tag @s add %s" % (k, SEEN_TAG))
    ent += ["data modify storage %s one set value {}" % R,
            "data modify storage %s one.item set from entity @s Item" % R,
            "execute unless data storage %s one.item.id run return run tag @s add %s" % (R, SEEN_TAG),
            "function %s with storage %s a" % (RF("stash/add"), R),
            "scoreboard players add #ab %s 1" % t,
            "# only once it is in the stash",
            "kill @s"]
    fn("absorb/entity", ent, "an item entity into the stash")
    fn("absorb/inv", [
        "data modify storage %s inv set value []" % R,
        "data modify storage %s inv append from entity @s Inventory[{components:{\"minecraft:custom_data\":{%s:1b}}}]" % (R, K),
        "function %s" % RF("absorb/inv_next")],
        "as the member: every inventory entry carrying the gain key")
    armour = {100: "armor.feet", 101: "armor.legs", 102: "armor.chest", 103: "armor.head", -106: "weapon.offhand"}
    nxt = ["execute unless data storage %s inv[0] run return 0" % R,
           "data modify storage %s one set value {}" % R,
           "data modify storage %s one.item set from storage %s inv[0]" % (R, R),
           "execute store result score #sl %s run data get storage %s one.item.Slot" % (t, R),
           "execute store result storage %s sl.s int 1 run scoreboard players get #sl %s" % (R, t),
           "scoreboard players set #ok %s 0" % t,
           "# the exact slot emptied (never `clear`: it also reaches the cursor and the crafting grid, which the NBT does not show)",
           "execute if score #sl %s matches 0..35 run function %s with storage %s sl" % (t, RF("absorb/slot"), R)]
    nxt += ["execute if score #sl %s matches %d store success score #ok %s run item replace entity @s %s with minecraft:air"
            % (t, n, t, slot) for n, slot in sorted(armour.items())]
    nxt += ["execute if score #ok %s matches 1 run function %s with storage %s a" % (t, RF("stash/add"), R),
            "execute if score #ok %s matches 1 run scoreboard players add #ab %s 1" % (t, t),
            "data remove storage %s inv[0]" % R,
            "function %s" % RF("absorb/inv_next")]
    fn("absorb/inv_next", nxt, "one marked inventory entry: the slot emptied, then the stack stashed")
    fn("absorb/slot", ["$execute store success score #ok %s run item replace entity @s container.$(s) with minecraft:air" % t],
       "a macro: $(s) the slot")
    fn("stash/add", [
        "# R one.item -> the stash of the player whose dg.id is $(id): the gain key and the slot taken off, then a",
        "# fungible plain stack to its count, anything else as the exact stack",
        "$execute unless data storage %s s.p$(id) run data modify storage %s s.p$(id) set value {items:[],counts:[]}" % (R, R),
        "data remove storage %s one.item.Slot" % R,
        "data remove storage %s one.item.components.\"minecraft:custom_data\".%s" % (R, K),
        "scoreboard players set #k %s 1" % t,
        "execute store result score #k %s run data get storage %s one.item.components.\"minecraft:custom_data\"" % (t, R),
        "execute if score #k %s matches 0 run data remove storage %s one.item.components.\"minecraft:custom_data\"" % (t, R),
        "scoreboard players set #k %s 1" % t,
        "execute store result score #k %s run data get storage %s one.item.components" % (t, R),
        "execute if score #k %s matches 0 run data remove storage %s one.item.components" % (t, R),
        "execute unless data storage %s one.item.count run data modify storage %s one.item.count set value 1" % (R, R),
        "scoreboard players set #fg %s 0" % t,
        "execute unless data storage %s one.item.components run function %s with storage %s one.item" % (R, RF("stash/fung_test"), R),
        "data modify storage %s b set value {}" % R,
        "$data modify storage %s b.id set value $(id)" % R,
        "data modify storage %s b.iid set from storage %s one.item.id" % (R, R),
        "execute if score #fg %s matches 1 run return run function %s with storage %s b" % (t, RF("stash/count"), R),
        "$data modify storage %s s.p$(id).items append from storage %s one.item" % (R, R)],
        "a macro: one stack into a player's stash")
    fn("stash/fung_test", ["$execute if data storage %s fung[{id:\"$(id)\"}] run scoreboard players set #fg %s 1" % (R, t)],
       "a macro: is $(id) fungible")
    fn("stash/count", [
        "$execute unless data storage %s s.p$(id).counts[{id:\"$(iid)\"}] run data modify storage %s s.p$(id).counts append value {id:\"$(iid)\",n:0}" % (R, R),
        "$execute store result score #n %s run data get storage %s s.p$(id).counts[{id:\"$(iid)\"}].n" % (t, R),
        "execute store result score #c %s run data get storage %s one.item.count" % (t, R),
        "scoreboard players operation #n %s += #c %s" % (t, t),
        "$execute store result storage %s s.p$(id).counts[{id:\"$(iid)\"}].n int 1 run scoreboard players get #n %s" % (R, t)],
        "a macro: a fungible stack added to its count")

    # ---- the satchel and its view ------------------------------------------------------------------------------
    v = sa["view"]
    fn("satchel/use", [
        "scoreboard players set @s %s 0" % OBJ["used"],
        "scoreboard players set #hold %s 0" % t,
        "execute if items entity @s weapon.mainhand %s run scoreboard players set #hold %s 1" % (satchel_match(rk), t),
        "execute if items entity @s weapon.offhand %s run scoreboard players set #hold %s 1" % (satchel_match(rk), t),
        "execute unless score #hold %s matches 1 run return 0" % t,
        "execute unless score @s %s matches 2..4 run return run %s" % (O["st"], _tell("The Run Satchel only opens in a rift.")),
        "function %s" % RF("view/open")],
        "a carrot on a stick used (the stat); only the satchel, only in a run")
    viewer = ("{Tags:[\"%s\",\"%s\"],NoAI:1b,Invulnerable:1b,Silent:1b,PersistenceRequired:1b,DespawnDelay:0,"
              "DeathLootTable:\"minecraft:empty\",CustomName:%s,CustomNameVisible:1b,Offers:{Recipes:[]}}"
              % (v["tag"], NEW_TAG, D.snbt_str(D.text(v["name"], sa["colour"]))))
    fn("view/open", [
        "scoreboard players operation #me %s = @s %s" % (t, O["id"]),
        "execute as @e[type=%s,tag=%s] if score @s %s = #me %s run function %s" % (v["entity"], v["tag"], OBJ["owner"], t, RF("view/close")),
        "execute store result storage %s a.id int 1 run scoreboard players get @s %s" % (R, O["id"]),
        "data modify storage %s view set value []" % R,
        "function %s with storage %s a" % (RF("view/build"), R),
        "execute unless data storage %s view[0] run return run %s" % (R, _tell(v["empty_line"], "gray")),
        "execute at @s rotated ~ 0 positioned ^ ^ ^%s run summon %s ~ ~ ~ %s" % (v["distance"], v["entity"], viewer),
        "data modify entity @e[type=%s,tag=%s,limit=1] Offers.Recipes set from storage %s view" % (v["entity"], NEW_TAG, R),
        "scoreboard players operation @e[type=%s,tag=%s] %s = #me %s" % (v["entity"], NEW_TAG, OBJ["owner"], t),
        "scoreboard players set @e[type=%s,tag=%s] %s %d" % (v["entity"], NEW_TAG, OBJ["life"], v["life_ticks"]),
        "tag @s add %s" % ME_TAG,
        "execute as @e[type=%s,tag=%s] at @s run tp @s ~ ~ ~ facing entity @p[tag=%s] feet" % (v["entity"], NEW_TAG, ME_TAG),
        "tag @s remove %s" % ME_TAG,
        "tag @e[type=%s,tag=%s] remove %s" % (v["entity"], NEW_TAG, NEW_TAG),
        "playsound minecraft:item.bundle.drop_contents master @s ~ ~ ~ 0.8 1",
        _tell(v["open_line"], "light_purple")],
        "as the member: a viewer whose trade screen is the stash")
    fn("view/build", [
        "data modify storage %s work set value []" % R,
        "$data modify storage %s work set from storage %s s.p$(id).items" % (R, R),
        "function %s" % RF("view/items"),
        "data modify storage %s work set value []" % R,
        "$data modify storage %s work set from storage %s s.p$(id).counts" % (R, R),
        "function %s" % RF("view/counts")],
        "a macro: the stash of $(id) as trade offers in R view")
    buy = "{id:\"%s\",count:1,components:{\"minecraft:item_name\":%s}}" % (v["price_item"], D.snbt_str(D.text(v["price_name"], "gray")))
    offer_tail = "uses:1,maxUses:1,rewardExp:0b,xp:0,priceMultiplier:0.0f,specialPrice:0,demand:0"
    fn("view/items", [
        "execute unless data storage %s work[0] run return 0" % R,
        "data modify storage %s view append value {buy:%s,%s}" % (R, buy, offer_tail),
        "data modify storage %s view[-1].sell set from storage %s work[0]" % (R, R),
        "data remove storage %s work[0]" % R,
        "function %s" % RF("view/items")],
        "each exact stack as an out-of-stock offer (uses = maxUses: shown, never traded)")
    fn("view/counts", [
        "execute unless data storage %s work[0] run return 0" % R,
        "execute store result score #n %s run data get storage %s work[0].n" % (t, R),
        "scoreboard players operation #c %s = #n %s" % (t, t),
        "execute if score #c %s matches 65.. run scoreboard players set #c %s 64" % (t, t),
        "data modify storage %s vc set value {}" % R,
        "data modify storage %s vc.id set from storage %s work[0].id" % (R, R),
        "execute store result storage %s vc.n int 1 run scoreboard players get #n %s" % (R, t),
        "execute store result storage %s vc.c int 1 run scoreboard players get #c %s" % (R, t),
        "execute if score #c %s matches 1.. run function %s with storage %s vc" % (t, RF("view/count_one"), R),
        "data remove storage %s work[0]" % R,
        "function %s" % RF("view/counts")],
        "each fungible count as one offer of up to 64, its total in the lore")
    fn("view/count_one", [
        "$data modify storage %s view append value {buy:%s,sell:{id:\"$(id)\",count:$(c),components:{\"minecraft:lore\":['{\"text\":\"$(n) in the satchel\",\"color\":\"gray\",\"italic\":false}']}},%s}"
        % (R, buy, offer_tail)],
        "a macro: one count's offer")
    fn("view/age", [
        "scoreboard players remove @s %s 1" % OBJ["life"],
        "execute if score @s %s matches ..0 run function %s" % (OBJ["life"], RF("view/close"))],
        "as a viewer, every tick")
    fn("view/close", [
        "# the name off first, so the death is not a named entity's line in the server log; no loot (DeathLootTable)",
        "data remove entity @s CustomName",
        "kill @s"],
        "as a viewer: gone")

    # ---- the run's begin, clean exit and end ------------------------------------------------------------------
    fn("begin", [
        "# an unanswered satchel from the last run comes to the player first (with their Owner: never re-stashed)",
        "execute if score @s %s matches 1 run function %s" % (OBJ["wait"], RF("exit/take")),
        "scoreboard players set @s %s 0" % OBJ["wait"],
        "scoreboard players set @s %s 0" % OBJ["choice"],
        "execute store result storage %s a.id int 1 run scoreboard players get @s %s" % (R, O["id"]),
        "execute store result storage %s a.who int 1 run scoreboard players get @s %s" % (R, O["id"]),
        "function %s with storage %s a" % (RF("begin_m"), R)],
        "at the threshold (slot/s<g>/start), as the member: an empty stash; any unresolved catch entry is dropped (kept)")
    fn("begin_m", [
        "$data modify storage %s s.p$(id) set value {items:[],counts:[]}" % R,
        "$data remove storage %s ledger[{who:$(who)}]" % R],
        "a macro")
    bonus = ["execute if score @s %s matches %s run scoreboard players set @s %s %d" % (O["band"], b, OBJ["bonus"], p)
             for b, p in sorted(ex["bonus_pct_by_band"].items(), key=lambda kv: int(kv[0]))]
    fn("won", [
        "# from the dungeon's pay (a clean exit past the threshold), before m/end: the run's gains are the player's",
        "scoreboard players set @s %s 2" % OBJ["wait"],
        "execute store result storage %s a.id int 1 run scoreboard players get @s %s" % (R, O["id"]),
        "execute store result storage %s a.who int 1 run scoreboard players get @s %s" % (R, O["id"]),
        "execute store result storage %s a.run int 1 run scoreboard players get @s %s" % (R, O["run"]),
        "# the last marked items in the inventory first",
        "scoreboard players set #ab %s 0" % t,
        "execute if items entity @s container.* %s run function %s" % (gain_pred(rk), RF("absorb/inv")),
        "execute if items entity @s weapon.offhand %s run function %s" % (gain_pred(rk), RF("absorb/inv")),
        "execute if items entity @s armor.* %s run function %s" % (gain_pred(rk), RF("absorb/inv")),
        "function %s" % RF("catch/won"),
        "scoreboard players set @s %s 0" % OBJ["bonus"]] + bonus + [
        "execute if score @s %s matches 1.. run scoreboard players add @s %s %d" % (O["bossd"], OBJ["bonus"], ex["boss_bonus_pct"]),
        "function %s with storage %s a" % (RF("exit/value"), R),
        "execute if score #st %s matches ..0 run return run %s" % (t, _tell(lines_x["empty"], "gray")),
        "scoreboard players set @s %s 1" % OBJ["wait"],
        "scoreboard players set @s %s %d" % (OBJ["left"], ex["choice_ticks"]),
        "function %s" % RF("exit/offer")],
        "as the member at a clean exit")
    fn("forfeit", [
        "# EVERY way out reaches here (m/end, slot/s<g>/end). A clean exit already ran risk/won: 2 nothing to settle,",
        "# 1 a satchel waiting for its choice. Anything else is a run that ended without a clean exit",
        "execute if score @s %s matches 2 run return run scoreboard players set @s %s 0" % (OBJ["wait"], OBJ["wait"]),
        "execute if score @s %s matches 1 run return 0" % OBJ["wait"],
        "execute store result storage %s a.id int 1 run scoreboard players get @s %s" % (R, O["id"]),
        "execute store result storage %s a.who int 1 run scoreboard players get @s %s" % (R, O["id"]),
        "execute store result storage %s a.run int 1 run scoreboard players get @s %s" % (R, O["run"]),
        "function %s with storage %s a" % (RF("forfeit_m"), R),
        "# a marked item still in the inventory (on the cursor at the end, say) goes with the stash",
        "clear @s %s" % gain_pred(rk),
        "execute if score #st %s matches 1.. run %s" % (t, _tell(rk["death"]["lost_line"], "red")),
        "function %s with storage %s a" % (RF("catch/forfeit"), R)],
        "as the player, at every run's end that was not a clean exit: the stash is gone")
    fn("forfeit_m", [
        "scoreboard players set #st %s 0" % t,
        "scoreboard players set #sb %s 0" % t,
        "$execute store result score #st %s run data get storage %s s.p$(id).items" % (t, R),
        "$execute store result score #sb %s run data get storage %s s.p$(id).counts" % (t, R),
        "scoreboard players operation #st %s += #sb %s" % (t, t),
        "$data remove storage %s s.p$(id)" % R],
        "a macro: the stash deleted, its size in #st")

    # ---- the exit's offer, value, take and sell ----------------------------------------------------------------
    def btn(label, colour, n, hover):
        return {"text": label, "color": colour, "bold": True,
                "clickEvent": {"action": "run_command", "value": "/trigger %s set %d" % (OBJ["choice"], n)},
                "hoverEvent": {"action": "show_text", "contents": hover}}
    sm = lines_x["summary"].split("%d")
    wm = lines_x["worth"].split("%d")
    fn("exit/offer", [
        _tell_parts([{"text": sm[0], "color": "light_purple"}, {"score": {"name": "#st", "objective": t}, "color": "gold"},
                     {"text": sm[1], "color": "light_purple"}]),
        _tell_parts([{"text": wm[0], "color": "gray"}, {"score": {"name": "#worth", "objective": t}, "color": "gold"},
                     {"text": wm[1], "color": "gray"}]),
        "execute if score #un %s matches 1.. run %s" % (t, _tell(lines_x["unsold"], "gray")),
        _tell_parts([btn(lines_x["take"], "green", 1, "Everything comes to you as items."), {"text": "  "},
                     btn(lines_x["sell"], "gold", 2, "The bank buys what it can; the rest comes to you."), {"text": "  "},
                     btn(lines_x["look"], "aqua", 3, "List what is in the satchel.")]),
        "scoreboard players enable @s %s" % OBJ["choice"]],
        "as the player: the satchel's worth and the three buttons (/trigger, which any player may run once enabled)")
    fn("exit/value", [
        "scoreboard players set #worth %s 0" % t,
        "scoreboard players set #st %s 0" % t,
        "scoreboard players set #un %s 0" % t,
        "data modify storage %s work set value []" % R,
        "$data modify storage %s work set from storage %s s.p$(id).items" % (R, R),
        "function %s" % RF("exit/value_items"),
        "data modify storage %s work set value []" % R,
        "$data modify storage %s work set from storage %s s.p$(id).counts" % (R, R),
        "function %s" % RF("exit/value_counts"),
        "function %s" % RF("exit/bonus")],
        "a macro: #worth (with the bonus), #st stacks, #un stacks the bank does not buy")
    fn("exit/bonus", [
        "scoreboard players set #bp %s 100" % t,
        "scoreboard players operation #bp %s += @s %s" % (t, OBJ["bonus"]),
        "scoreboard players operation #worth %s *= #bp %s" % (t, t),
        "scoreboard players operation #worth %s /= #100 %s" % (t, t)],
        "#worth x (100 + dg.rkb) / 100, rounded down")
    fn("exit/price", [
        "scoreboard players set #p %s 0" % t,
        "$execute if data storage %s prices[{id:\"$(id)\"}] store result score #p %s run data get storage %s prices[{id:\"$(id)\"}].p" % (R, t, R)],
        "a macro: the bank's unit price of $(id) in #p, 0 when it does not buy it")
    fn("exit/value_items", [
        "execute unless data storage %s work[0] run return 0" % R,
        "function %s with storage %s work[0]" % (RF("exit/price"), R),
        "execute store result score #c %s run data get storage %s work[0].count" % (t, R),
        "scoreboard players add #st %s 1" % t,
        "execute if score #p %s matches ..0 run scoreboard players add #un %s 1" % (t, t),
        "scoreboard players operation #p %s *= #c %s" % (t, t),
        "scoreboard players operation #worth %s += #p %s" % (t, t),
        "data remove storage %s work[0]" % R,
        "function %s" % RF("exit/value_items")],
        "each exact stack")
    fn("exit/value_counts", [
        "execute unless data storage %s work[0] run return 0" % R,
        "function %s with storage %s work[0]" % (RF("exit/price"), R),
        "execute store result score #c %s run data get storage %s work[0].n" % (t, R),
        "scoreboard players operation #k %s = #c %s" % (t, t),
        "scoreboard players operation #k %s += #63 %s" % (t, t),
        "scoreboard players operation #k %s /= #64 %s" % (t, t),
        "scoreboard players operation #st %s += #k %s" % (t, t),
        "execute if score #p %s matches ..0 run scoreboard players operation #un %s += #k %s" % (t, t, t),
        "scoreboard players operation #p %s *= #c %s" % (t, t),
        "scoreboard players operation #worth %s += #p %s" % (t, t),
        "data remove storage %s work[0]" % R,
        "function %s" % RF("exit/value_counts")],
        "each fungible count (stacks of 64)")
    fn("exit/choose", [
        "scoreboard players operation #ch %s = @s %s" % (t, OBJ["choice"]),
        "scoreboard players set @s %s 0" % OBJ["choice"],
        "execute unless score @s %s matches 1 run return 0" % OBJ["wait"],
        "execute if score #ch %s matches 1 run return run function %s" % (t, RF("exit/take")),
        "execute if score #ch %s matches 2 run return run function %s" % (t, RF("exit/sell")),
        "execute if score #ch %s matches 3 run function %s" % (t, RF("exit/list")),
        "scoreboard players enable @s %s" % OBJ["choice"]],
        "as the player: a button clicked")
    fn("exit/wait", [
        "scoreboard players remove @s %s 1" % OBJ["left"],
        "execute if score @s %s matches 1.. run return 0" % OBJ["left"],
        _tell(lines_x["auto"], "gray"),
        "function %s" % RF("exit/take")],
        "as a player whose satchel waits (online only): unanswered, it is Take it all")
    fn("exit/list", [
        "execute store result storage %s a.id int 1 run scoreboard players get @s %s" % (R, O["id"]),
        "data modify storage %s work set value []" % R,
        "function %s with storage %s a" % (RF("exit/list_m"), R),
        "function %s" % RF("exit/list_items"),
        "data modify storage %s work set value []" % R,
        "function %s with storage %s a" % (RF("exit/list_c"), R),
        "function %s" % RF("exit/list_counts")],
        "as the player: the satchel in chat, each line hovering the item")
    fn("exit/list_m", ["$data modify storage %s work set from storage %s s.p$(id).items" % (R, R)], "a macro")
    fn("exit/list_c", ["$data modify storage %s work set from storage %s s.p$(id).counts" % (R, R)], "a macro")
    fn("exit/list_items", [
        "execute unless data storage %s work[0] run return 0" % R,
        "function %s with storage %s work[0]" % (RF("exit/list_one"), R),
        "data remove storage %s work[0]" % R,
        "function %s" % RF("exit/list_items")], "each exact stack")
    fn("exit/list_counts", [
        "execute unless data storage %s work[0] run return 0" % R,
        "function %s with storage %s work[0]" % (RF("exit/list_count"), R),
        "data remove storage %s work[0]" % R,
        "function %s" % RF("exit/list_counts")], "each count")
    fn("exit/list_one", ["$tellraw @s [{\"text\":\" $(count) x \",\"color\":\"gray\"},{\"text\":\"$(id)\",\"color\":\"white\",\"hoverEvent\":{\"action\":\"show_item\",\"contents\":{\"id\":\"$(id)\",\"count\":$(count)}}}]"],
       "a macro: one line")
    fn("exit/list_count", ["$tellraw @s [{\"text\":\" $(n) x \",\"color\":\"gray\"},{\"text\":\"$(id)\",\"color\":\"white\",\"hoverEvent\":{\"action\":\"show_item\",\"contents\":{\"id\":\"$(id)\",\"count\":1}}}]"],
       "a macro: one line")
    fn("exit/take", [
        "execute store result storage %s a.id int 1 run scoreboard players get @s %s" % (R, O["id"]),
        "data modify storage %s me set value {}" % R,
        "data modify storage %s me.o set from entity @s UUID" % R,
        "function %s with storage %s a" % (RF("deliver"), R),
        "scoreboard players set @s %s 0" % OBJ["wait"],
        "scoreboard players set @s %s 0" % OBJ["left"],
        "playsound minecraft:item.bundle.drop_contents master @s ~ ~ ~ 1 1",
        _tell(lines_x["taken"], "green")],
        "as and at the player: everything as items at their feet, then the stash deleted")
    sold = lines_x["sold"].split("%d")
    fn("exit/sell", [
        "execute store result storage %s a.id int 1 run scoreboard players get @s %s" % (R, O["id"]),
        "data modify storage %s me set value {}" % R,
        "data modify storage %s me.o set from entity @s UUID" % R,
        "# 1. split the stash: what the bank buys is priced into #worth, the rest kept in keepi/keepc. Nothing is",
        "#    changed yet",
        "scoreboard players set #worth %s 0" % t,
        "data modify storage %s keepi set value []" % R,
        "data modify storage %s keepc set value []" % R,
        "data modify storage %s work set value []" % R,
        "function %s with storage %s a" % (RF("exit/list_m"), R),
        "function %s" % RF("sell/items"),
        "data modify storage %s work set value []" % R,
        "function %s with storage %s a" % (RF("exit/list_c"), R),
        "function %s" % RF("sell/counts"),
        "function %s" % RF("exit/bonus"),
        "# 2. nothing the bank buys: it is a take",
        "execute if score #worth %s matches ..0 run return run function %s" % (t, RF("exit/take")),
        "# 3. PAY once, then the balance must have risen by exactly that (tools/produce_buyer.py pay_tail's check)",
        "execute store result score #before %s run cobbledollars query @s" % t,
        "execute store result storage %s pay.amount int 1 run scoreboard players get #worth %s" % (R, t),
        "function %s with storage %s pay" % (RF("sell/pay"), R),
        "execute store result score #after %s run cobbledollars query @s" % t,
        "scoreboard players operation #want %s = #before %s" % (t, t),
        "scoreboard players operation #want %s += #worth %s" % (t, t),
        "# 4. not paid as it should be: nothing is sold, everything comes to the player",
        "execute unless score #after %s = #want %s run %s" % (t, t, _tell(lines_x["pay_failed"], "red")),
        "execute unless score #after %s = #want %s run return run function %s" % (t, t, RF("exit/take")),
        "# 5. paid: the stash is only what the bank did not buy, and that comes to the player",
        "function %s with storage %s a" % (RF("sell/commit"), R),
        _tell_parts([{"text": sold[0], "color": "green"}, {"score": {"name": "#worth", "objective": t}, "color": "gold"},
                     {"text": sold[1], "color": "green"}]),
        "function %s" % RF("exit/take")],
        "as and at the player: the bank's price for what it buys (plus the bonus), the rest delivered")
    fn("sell/pay", ["$cobbledollars give @s $(amount)"], "CobbleDollars' own command (tools/produce_buyer.py pay)")
    fn("sell/commit", [
        "$data modify storage %s s.p$(id) set value {items:[],counts:[]}" % R,
        "$data modify storage %s s.p$(id).items set from storage %s keepi" % (R, R),
        "$data modify storage %s s.p$(id).counts set from storage %s keepc" % (R, R)],
        "a macro: the stash becomes what was not sold")
    fn("sell/items", [
        "execute unless data storage %s work[0] run return 0" % R,
        "function %s with storage %s work[0]" % (RF("exit/price"), R),
        "execute if score #p %s matches ..0 run data modify storage %s keepi append from storage %s work[0]" % (t, R, R),
        "execute store result score #c %s run data get storage %s work[0].count" % (t, R),
        "scoreboard players operation #p %s *= #c %s" % (t, t),
        "scoreboard players operation #worth %s += #p %s" % (t, t),
        "data remove storage %s work[0]" % R,
        "function %s" % RF("sell/items")], "each exact stack: priced, or kept")
    fn("sell/counts", [
        "execute unless data storage %s work[0] run return 0" % R,
        "function %s with storage %s work[0]" % (RF("exit/price"), R),
        "execute if score #p %s matches ..0 run data modify storage %s keepc append from storage %s work[0]" % (t, R, R),
        "execute store result score #c %s run data get storage %s work[0].n" % (t, R),
        "scoreboard players operation #p %s *= #c %s" % (t, t),
        "scoreboard players operation #worth %s += #p %s" % (t, t),
        "data remove storage %s work[0]" % R,
        "function %s" % RF("sell/counts")], "each count: priced, or kept")
    fn("deliver", [
        "data modify storage %s work set value []" % R,
        "$data modify storage %s work set from storage %s s.p$(id).items" % (R, R),
        "function %s" % RF("deliver/items"),
        "data modify storage %s work set value []" % R,
        "$data modify storage %s work set from storage %s s.p$(id).counts" % (R, R),
        "function %s" % RF("deliver/counts"),
        "$data remove storage %s s.p$(id)" % R],
        "a macro, as and at the player (their UUID in R me.o): every stack, then the stash deleted")
    fn("deliver/items", [
        "execute unless data storage %s work[0] run return 0" % R,
        "data modify storage %s d set value {}" % R,
        "data modify storage %s d.item set from storage %s work[0]" % (R, R),
        "data modify storage %s d.o set from storage %s me.o" % (R, R),
        "function %s with storage %s d" % (RF("deliver/drop"), R),
        "data remove storage %s work[0]" % R,
        "function %s" % RF("deliver/items")], "each exact stack")
    fn("deliver/drop", ["$summon minecraft:item ~ ~0.5 ~ {Item:$(item),PickupDelay:0,Age:-32768,Owner:$(o)}"],
       "a macro: the stack at their feet, theirs only, never despawning (tools/blackout_pack.py recovery/drop_one's form)")
    fn("deliver/counts", [
        "execute unless data storage %s work[0] run return 0" % R,
        "execute store result score #n %s run data get storage %s work[0].n" % (t, R),
        "data modify storage %s dc set value {}" % R,
        "data modify storage %s dc.id set from storage %s work[0].id" % (R, R),
        "data modify storage %s dc.o set from storage %s me.o" % (R, R),
        "function %s" % RF("deliver/count_loop"),
        "data remove storage %s work[0]" % R,
        "function %s" % RF("deliver/counts")], "each fungible count")
    fn("deliver/count_loop", [
        "execute if score #n %s matches ..0 run return 0" % t,
        "scoreboard players operation #c %s = #n %s" % (t, t),
        "execute if score #c %s matches 65.. run scoreboard players set #c %s 64" % (t, t),
        "execute store result storage %s dc.c int 1 run scoreboard players get #c %s" % (R, t),
        "function %s with storage %s dc" % (RF("deliver/count_drop"), R),
        "scoreboard players operation #n %s -= #c %s" % (t, t),
        "function %s" % RF("deliver/count_loop")], "stacks of 64 until the count is out")
    fn("deliver/count_drop", ["$summon minecraft:item ~ ~0.5 ~ {Item:{id:\"$(id)\",count:$(c)},PickupDelay:0,Age:-32768,Owner:$(o)}"],
       "a macro: one stack of a count")

    # ---- catches ----------------------------------------------------------------------------------------------
    catch = [
        "# the pokemon_captured callback (cobblers_dungeon_risk.molang), as the catcher at them: $(pid) the Pokemon's UUID,",
        "# $(sp) its species, $(sh) 1 when shiny. Logged only in a live run, and never a shiny or a dungeon's prize",
        "$data modify storage %s c set value {pid:\"$(pid)\",sp:\"$(sp)\",sh:$(sh)b}" % R,
        "execute unless score @s %s matches 3..4 run return 0" % O["st"]]
    if run_tag:
        catch.append("execute unless entity @s[tag=%s] run return 0" % run_tag)
    catch += ["scoreboard players set #ex %s 0" % t]
    if ca["exempt_shiny"]:
        catch.append("execute if data storage %s c{sh:1b} run scoreboard players set #ex %s 1" % (R, t))
    if ca["exempt_prize"]:
        for di, d in enumerate(D.dungeons(doc), 1):
            if prizes.get(di):
                catch.append("execute if score #ex %s matches 0 if score @s %s matches %d run function %s"
                             % (t, O["dun"], di, RF("prize/%s" % d["short"])))
                fn("prize/%s" % d["short"], ["execute if data storage %s c{sp:\"%s\"} run scoreboard players set #ex %s 2" % (R, sp, t)
                                             for sp in prizes[di]],
                   "%s's reward Pokemon (every prize pool, every band): never at stake" % d["name"])
    catch += ["execute if score #ex %s matches 1 run return run %s" % (t, _tell(lines_c["kept_shiny"], "gold")),
              "execute if score #ex %s matches 2 run return run %s" % (t, _tell(lines_c["kept_prize"], "gold")),
              "execute store result storage %s c.who int 1 run scoreboard players get @s %s" % (R, O["id"]),
              "execute store result storage %s c.run int 1 run scoreboard players get @s %s" % (R, O["run"]),
              "execute store result storage %s c.at int 1 run scoreboard players get #up %s" % (R, O["up"]),
              "data modify storage %s ledger append from storage %s c" % (R, R),
              _tell_parts([{"text": lines_c["at_stake"], "color": "light_purple"},
                           {"nbt": "c.sp", "storage": R, "color": "gold"}])]
    fn("catch", catch, "a catch logged by its UUID")
    fn("catch/won", ["function %s with storage %s a" % (RF("catch/won_m"), R),
                     "execute store result score #n %s run data get storage %s tmp" % (t, R),
                     "execute if score #n %s matches 1.. run %s" % (t, _tell(lines_c["kept_exit"], "green"))],
       "as the player at a clean exit (a.who, a.run set): the run's entries cleared, the catches kept")
    fn("catch/won_m", [
        "data modify storage %s tmp set value []" % R,
        "$data modify storage %s tmp append from storage %s ledger[{who:$(who),run:$(run)}]" % (R, R),
        "$data remove storage %s ledger[{who:$(who)}]" % R], "a macro")
    fn("catch/forfeit", [
        "# the run's entries to this player's work list, every entry of theirs out of the ledger (an older run's is",
        "# unresolved: dropped, so kept), then the reaper one entry at a time",
        "$data modify storage %s lw.p$(who) set value []" % R,
        "$data modify storage %s lw.p$(who) append from storage %s ledger[{who:$(who),run:$(run)}]" % (R, R),
        "$data remove storage %s ledger[{who:$(who)}]" % R,
        "function %s with storage %s a" % (RF("catch/next"), R)],
        "a macro, as the player (online: m/end runs as them)")
    fn("catch/next", [
        "$execute unless data storage %s lw.p$(who)[0] run return 0" % R,
        "data modify storage %s cur set value {}" % R,
        "$data modify storage %s cur set from storage %s lw.p$(who)[0]" % (R, R),
        "# removal only when data says catches.mode remove; otherwise the dry run, which removes nothing",
        "execute if data storage %s cfg{remove:1b} run return run function %s with storage %s cur" % (R, RF("catch/live"), R),
        "function %s with storage %s cur" % (RF("catch/dry"), R)],
        "a macro: the next entry. The MoLang reports by a queued command (EXP-022), which logs it and calls this again")

    def res(o):
        return "q.run_command('execute as ' + q.player.uuid + ' at @s run function %s');" % RF("catch/res_%d" % o)
    find = ("for_each(t.x, q.player.party.pokemon, { (t.x.id == '$(pid)') ? { t.f = 1; t.h = t.x.held_item; t.e = t.h.is_empty; }; }); "
            "(t.f == 0) ? { for_each(t.x, q.player.pc.pokemon, { (t.x.id == '$(pid)') ? { t.f = 2; t.h = t.x.held_item; t.e = t.h.is_empty; }; }); }; ")
    # the dry run reads nothing but the UUIDs: a script that dies (an unproven call) must not be able to stop the log
    find_dry = ("for_each(t.x, q.player.party.pokemon, { (t.x.id == '$(pid)') ? { t.f = 1; }; }); "
                "(t.f == 0) ? { for_each(t.x, q.player.pc.pokemon, { (t.x.id == '$(pid)') ? { t.f = 2; }; }); }; ")
    dry = ("t.f = 0; " + find_dry
           + "(t.f == 0) ? { %s }; (t.f == 1) ? { %s }; (t.f == 2) ? { %s };" % (res(0), res(1), res(2)))
    fn("catch/dry", ["$runmolang \"%s\" @s" % dry],
       "a macro: DRY RUN. Looks $(pid) up by UUID in the party, then the PC, and reports; removes nothing")
    live = ("t.f = 0; t.e = 1; t.o = 0; " + find
            + "(t.f > 0 && q.player.in_battle == 1) ? { t.o = 6; }; "
              "(t.f > 0 && t.o == 0 && t.e == 0) ? { t.o = 5; }; "
              "(t.f == 1 && t.o == 0 && q.player.party.count <= 1) ? { t.o = 7; }; "
              "(t.f == 1 && t.o == 0) ? { t.o = 8; t.r = q.player.party.remove_by_id('$(pid)'); (t.r == 1) ? { t.o = 3; }; }; "
              "(t.f == 2 && t.o == 0) ? { t.o = 8; t.r = q.player.pc.remove_by_id('$(pid)'); (t.r == 1) ? { t.o = 4; }; }; "
            + " ".join("(t.o == %d) ? { %s };" % (o, res(o)) for o in (3, 4, 5, 6, 7, 8))
            + " (t.f == 0) ? { %s };" % res(0))
    fn("catch/live", ["$runmolang \"%s\" @s" % live],
       "a macro: REMOVAL (catches.mode remove only). By UUID, out of battle, holding no item, never the party's last")
    for o in OUTCOMES:
        fn("catch/res_%d" % o, ["scoreboard players set #o %s %d" % (t, o), "function %s" % RF("catch/res")],
           "the reaper's result %d: %s" % (o, OUTCOMES[o]))
    say_o = {1: ("dry", "yellow"), 2: ("dry", "yellow"), 3: ("removed", "red"), 4: ("removed", "red"),
             5: ("kept_guard", "gray"), 6: ("kept_guard", "gray"), 7: ("kept_guard", "gray"), 8: ("kept_guard", "gray")}
    resl = ["execute store result storage %s a.who int 1 run scoreboard players get @s %s" % (R, O["id"]),
            "data modify storage %s cur set value {}" % R,
            "function %s with storage %s a" % (RF("catch/res_take"), R),
            "execute unless data storage %s cur.pid run return 0" % R,
            "execute store result storage %s cur.o int 1 run scoreboard players get #o %s" % (R, t),
            "execute store result storage %s cur.done int 1 run scoreboard players get #up %s" % (R, O["up"]),
            "data modify storage %s log append from storage %s cur" % (R, R),
            "execute store result score #ln %s run data get storage %s log" % (t, R),
            "execute if score #ln %s matches %d.. run data remove storage %s log[0]" % (t, ca["log_max"] + 1, R)]
    for o, (key, colour) in sorted(say_o.items()):
        resl.append("execute if score #o %s matches %d run %s" % (t, o, _tell_parts(
            [{"text": lines_c[key], "color": colour}, {"nbt": "cur.sp", "storage": R, "color": "gold"}])))
    resl.append("function %s with storage %s a" % (RF("catch/next"), R))
    fn("catch/res", resl, "as the player: the entry's result logged (R log, the newest %d), said, and the next entry" % ca["log_max"])
    fn("catch/res_take", ["$data modify storage %s cur set from storage %s lw.p$(who)[0]" % (R, R),
                          "$data remove storage %s lw.p$(who)[0]" % R], "a macro: the entry the result is for")
    return out


def callback(rk=None):
    """pokemon_captured: every catch to risk/catch as the catcher; that function decides (a live run, not exempt)."""
    D = _D()
    f = D.F("risk/catch")
    cmd = ("'execute as ' + q.player.uuid + ' at @s run function %s {pid:\"' + t.pid + '\",sp:\"' + t.sp + '\",sh:%d}'")
    return "\n".join([
        "'Generated by tools/dungeon_risk.py from data/dungeon_risk.json. Any catch: the dungeon risk logs it by its';",
        "'UUID only in a live run, and never a shiny or a dungeon prize (risk/catch decides).';",
        "t.pk = q.pokemon;",
        "t.pid = t.pk.id;",
        "t.sp = t.pk.species.identifier;",
        "t.sh = t.pk.is_shiny;",
        "(t.sh == 1) ? { q.run_command(%s); };" % (cmd % (f, 1)),
        "(t.sh == 0) ? { q.run_command(%s); };" % (cmd % (f, 0)),
        ""])


def mark_loot_table(text, rk):
    """A loot table's JSON with a table-level set_custom_data {<gain key>:1b} appended (every item it rolls)."""
    j = json.loads(text)
    fx = list(j.get("functions") or [])
    tag = "{%s:1b}" % gain_key(rk)
    if not any(f.get("function") == "minecraft:set_custom_data" and f.get("tag") == tag for f in fx):
        fx.append({"function": "minecraft:set_custom_data", "tag": tag})
    j["functions"] = fx
    return json.dumps(j, indent=2) + "\n"


def patch_files(doc, files, rk=None):
    """Every dungeon loot table marked; the callback added. In place on build()'s files."""
    rk = rk or load()
    pre = rk["stash"]["loot_table_prefix"]
    for k in list(files):
        if k.startswith(pre) and k.endswith(".json"):
            files[k] = mark_loot_table(files[k], rk)
    files[CALLBACK_PATH] = callback(rk)


def patch_functions(doc, fns, rk=None):
    """The engine's hooks: the satchel given with the pick and taken wherever the pick is; the stash begun at the
    threshold; the dungeon's pay calls risk/won; every run's end calls risk/forfeit first."""
    rk = rk or load()
    D = _D()
    p = doc["engine"]["rift_pick"]
    give = "give @s %s[minecraft:custom_data={%s:1b}" % (p["item"], p["custom_data_key"])   # the pick's give (pick_give)
    pick = D.pick_match(doc)
    sat_g, sat_m = "give @s %s 1" % satchel_give(rk), satchel_match(rk)
    begin, won, forfeit = (D.F("risk/" + x) for x in ("begin", "won", "forfeit"))
    end_rx = re.compile(r"^(m/end|slot/s\d+/end)$")
    start_rx = re.compile(r"^slot/s\d+/start$")
    arrive_rx = re.compile(r"^slot/s\d+/arrive$")
    found = {"give": 0, "clear": 0, "begin": 0, "pay": 0, "end": 0}
    for name, lines in list(fns.items()):
        if name.startswith("risk/"):
            continue
        new = []
        for ln in lines:
            new.append(ln)
            if arrive_rx.match(name) and ln.startswith(give):
                new.append(sat_g)
                found["give"] += 1
            if pick in ln and "clear @s" in ln:
                new.append(ln.replace(pick, sat_m))
                found["clear"] += 1
        if start_rx.match(name):
            new.append("function %s" % begin)
            found["begin"] += 1
        if name == "pay":
            new.append("function %s" % won)
            found["pay"] += 1
        if end_rx.match(name):
            new.insert(1, "function %s" % forfeit)
            found["end"] += 1
        fns[name] = new
    missing = [k for k, v in found.items() if not v]
    if missing:
        raise RiskError("tools/dungeon.py no longer has the hook(s) %s the dungeon risk patches" % missing)
    return found


def load_entries():
    return [_D().F("risk/load")]


def tick_entries():
    return [_D().F("risk/tick")]


# ------------------------------------------------------------------------------------------------- report


def report(doc, rk=None):
    rk = rk or load()
    pz = prize_species(doc)
    pr = bank_prices()
    return ["dungeon risk: catches.mode %s (%s)" % (rk["catches"]["mode"], rk["catches"]["modes"][rk["catches"]["mode"]][:60] + "..."),
            "  stash: absorb radius %d, %d fungible ids, %d skip keys" % (rk["stash"]["absorb_radius"], len(rk["stash"]["fungible"]),
                                                                          len(rk["stash"]["skip_custom_data_keys"])),
            "  sale: %d bank prices, bonus by band %s, boss +%d%%" % (len(pr), rk["exit"]["bonus_pct_by_band"], rk["exit"]["boss_bonus_pct"]),
            "  never at stake (prize species): " + ", ".join("%d:%d" % (k, len(v)) for k, v in sorted(pz.items()))]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--report", action="store_true")
    a = p.parse_args(argv)
    rk = load()
    D = _D()
    doc = D.load()
    bad = problems(rk, doc)
    if bad:
        print("\n".join("PROBLEM " + b for b in bad))
        return 1
    print("\n".join(report(doc, rk)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
