"""Dungeon deaths take no items and make no guardian (the owner, 2026-10-08; docs/research/DUNGEON_DEATH.md).

The owner's rule: "No Pokemon or trainer takes a player's items in a dungeon ... A dungeon death costs the money the
blackout already takes, the run's held rewards, and the sigil and lockout to try again. Nothing else." That covers
every way to die in there: the timer, a boss, a trainer, a fall, lava.

Written by the auditor of the death paths, not by the session that wrote tools/blackout_pack.py. What it runs is the
generated pack, on the command simulators in tests/test_blackout_pack.py (TB.Sim) and tests/nbt_sim.py (NbtSim), the
same model every blackout test uses.

What the pack does today (VERIFIED by reading tools/blackout_pack.py, and by the tests below that pass):
  - the timer's `kill @s`, a fall, lava, drowning, suffocation and /kill reach only blackout/death: money and the
    return, never recovery/make (the static reachability test);
  - an NPC trainer loss reaches only blackout/battle_loss_npc: money and the return, no items;
  - a loss to a wild Pokemon, in battle (battle_victory) or killed outside one (the killed_by_pokemon advancement),
    reaches recovery/make unless the VICTOR carries data/blackout.json claims.exempt_tag (the Entei, the gulch Megas).
    Nothing reads a tag on the PLAYER there. A dungeon's den Pokemon, an untagged boss, or anything else wild in a pocket
    slot therefore still takes items and becomes a guardian.

So the dungeon exemption the rule needs is NOT in the pack. The tests that hold the generated pack to it are marked
xfail(strict=True) until data/blackout.json carries `dungeon_exempt` (the builder's switch: once the key exists they
run for real and must pass, and an xfail that starts passing fails the run). The rule itself is proved meanwhile on a
REFERENCE patch of the generated text (`with_reference_exemption`: the two lines a builder must add), and the mutation
test strips every line that reads the dungeon tag (from the real pack once implemented, from the reference until then)
and must see items taken again. Mutating the generated functions, never data/blackout.json, is what tests the code.
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import nbt_sim as N  # noqa: E402
import test_blackout_pack as TB  # noqa: E402
import test_blackout_recovery_pid as RP  # noqa: E402

NS = TB.NS
CFG = TB.CFG
FNS = TB.FNS
LEDGER = TB.LEDGER

# the switch the builder adds to data/blackout.json; the tag's name is theirs to choose (PROPOSED until then)
PROPOSED_TAG = "cobblers.dungeon_run"
IMPLEMENTED = bool(CFG.get("dungeon_exempt"))
DUNGEON_TAG = (CFG.get("dungeon_exempt") or {}).get("player_tag", PROPOSED_TAG)
NOT_BUILT = "data/blackout.json has no dungeon_exempt: the pack exempts a tagged VICTOR only, never a tagged player"

GM_TAG = CFG["claims"]["exempt_tag"]
WILD = RP.WILD_UUID                       # a wild victor's entity UUID, as battle_victory passes it
VICTOR_SEL = RP.VICTOR_SEL               # the kill path's victor, a selector (recovery/killed)
P1, P1_ID = RP.P1, RP.P1_ID
GUARD = RP.GUARD
CHARGE = TB.BP.charge_amount(CFG["money"])
HELD = {0: ("cobblemon:ultra_ball", 20), 1: ("cobblemon:potion", 5)}     # balls and medicine: both are claimable


def with_reference_exemption(fns, tag=DUNGEON_TAG):
    """The generated functions plus the two lines the rule needs (docs/research/DUNGEON_DEATH.md 'The rule'):
    battle_loss_wild treats a player holding the dungeon tag as exempt, exactly as it treats a tagged victor, so no
    claim is made and the money and the return are untouched; and a resolved claim is not dropped at the feet of a
    player inside a dungeon (the exit delivers it). Both are what a builder adds to tools/blackout_pack.py."""
    out = {k: list(v) for k, v in fns.items()}
    loss = out["blackout/battle_loss_wild"]
    i = next(i for i, l in enumerate(loss) if l.startswith("$execute as $(victor)") and "#exempt bo.tmp 1" in l)
    loss.insert(i + 1, "execute if entity @s[tag=%s] run scoreboard players set #exempt bo.tmp 1" % tag)
    out["recovery/deliver"] = ["execute if entity @s[tag=%s] run return 0" % tag] + out["recovery/deliver"]
    return out


def without_dungeon_tag(fns, tag=DUNGEON_TAG):
    """The mutation: every command line that reads the dungeon tag removed, wherever it is."""
    return {k: [l for l in v if l.lstrip().startswith("#") or tag not in l] for k, v in fns.items()}


RULE_FNS = FNS if IMPLEMENTED else with_reference_exemption(FNS)


# ------------------------------------------------------------------------------------------------ the scenarios

def _category(item):
    return next(c for c in ("balls", "medicine", "consumables") if item in CFG["claims"][c])


def _death(fns, path, player_tags=(), victor_tags=(), slots=None, balance=1000):
    """Run one dungeon death as P1 on `fns`. path: 'battle' (a lost battle to a wild Pokemon, from battle_victory) or
    'kill' (a wild Pokemon killed P1 outside a battle: the killed_by_pokemon advancement's reward, then the tick's
    death). Returns the NbtSim afterwards."""
    slots = dict(HELD if slots is None else slots)
    state, box = {"victor": path == "battle"}, []
    victors = (WILD, VICTOR_SEL)

    def query(cmd):
        m = re.fullmatch(r"clear @s #%s:claim/(\w+) 0" % NS, cmd)
        if m:
            return sum(n for i, n in slots.values() if _category(i) == m.group(1))
        m = re.fullmatch(r"data get entity @s Inventory\[\{Slot:(-?\d+)b\}\]\.count", cmd)
        if m:
            return slots[int(m.group(1))][1]
        m = re.fullmatch(r"data get entity @s Pokemon\.UUID\[(\d)\]", cmd)
        if m:
            return GUARD[int(m.group(1))]
        if any(cmd.startswith("data get entity %s Pos[" % v) for v in victors):
            return 100
        return RP.strict_query({"cobbledollars query @s": balance})(cmd)

    def world(kind, toks):
        s = box[0]
        if kind == "on":
            assert toks == ["attacker"], toks
            return path == "kill"
        if kind == "entity" and toks[0] in victors + ("@e[type=cobblemon:pokemon,tag=cobblers.victor]",):
            return state["victor"]
        if kind == "entity" and toks[0].startswith("@s[type=cobblemon:pokemon,nbt="):
            return True                                  # the killer is wild
        if kind == "entity" and toks[0] == "@s[tag=cobblers.named]":
            return False
        m = re.fullmatch(r"@s\[tag=([^,\]]+)\]", toks[0]) if kind == "entity" else None
        if m:
            # whose @s: the chain's last `as` (TB.Sim.as_sel); a victor's tags, else the player's own
            if s.as_sel in victors:
                return state["victor"] and m.group(1) in victor_tags
            assert s.as_sel in (None, "@a"), s.as_sel
            return m.group(1) in player_tags
        if kind == "items":
            n = -106 if toks[2] == "weapon.offhand" else int(toks[2].split(".")[1])
            return n in slots and "#%s:claim/%s" % (NS, _category(slots[n][0])) == toks[3]
        raise AssertionError("unmodelled test %s %s" % (kind, toks))

    def entity(sel, epath):
        if (sel, epath) == ("@s", "UUID"):
            return P1
        if sel in victors and epath == "Pokemon":
            return {"Species": "cobblemon:ursaring", "Level": 60, "UUID": N.IntArray(GUARD)}
        m = re.fullmatch(r"Inventory\[\{Slot:(-?\d+)b\}\]", epath)
        if sel == "@s" and m:
            i, n = slots[int(m.group(1))]
            return {"Slot": N.Byte(int(m.group(1))), "id": i, "count": n}
        raise AssertionError("unmodelled entity read %s %s" % (sel, epath))

    s = N.NbtSim(fns=fns, query=query, world=world, entity=entity)
    box.append(s)
    for f in TB.load_functions():
        s.call(f)
    RP._remember(s, P1, "Ash")                          # the name record the kill path needs (player_tick_pre)
    s.entity = entity
    s.calls.clear()
    s.log.clear()
    orig = s.command

    def command(cmd):
        if cmd == "tag @s add cobblers.victor":
            state["victor"] = True
        elif cmd == "tag @e[type=cobblemon:pokemon,tag=cobblers.victor] remove cobblers.victor":
            state["victor"] = False
        return orig(cmd)
    s.command = command
    if path == "battle":
        s.command('execute as %s run function %s:blackout/battle_loss_wild {victor:"%s",name:"Ash",id:"%s"}'
                  % (P1_ID, NS, WILD, P1_ID))
    else:
        s.call("blackout/killed")
        s.set("@s", "bo.deaths", 1)
        s.call("blackout/death")
    return s


def seizure(s):
    """Everything in this run that took, planned to take or held a player's item, or bound a guardian."""
    out = ["called %s" % c[0] for c in s.calls if c[0] in ("recovery/make", "recovery/commit", "recovery/apply_one",
                                                          "recovery/bind", "recovery/hold_money")]
    out += ["ran %r" % l for l in s.log if l.startswith("item modify entity @s")
            or l == "tag @s add cobblers.guardian" or "PersistenceRequired:1b" in l]
    claims = (s.nbt.get(LEDGER) or {}).get("claims") or []
    out += ["ledger holds claim %s" % c.get("id") for c in claims]
    return out


def blackout_cost(s):
    """The money and the return still happen: the flat charge removed once, and the return queued."""
    removes = [l for l in s.log if l.startswith("cobbledollars remove ")]
    return removes == ["cobbledollars remove @s %d" % CHARGE] and "tag @s add cobblers.bo_pending" in s.log \
        and s.get("@s", "bo.clm") == 0


PATHS = ["battle", "kill"]


# Without it the scenarios below could pass because they never reach the claim at all: the same death with no dungeon
# tag must take items and bind a guardian, in battle and outside it. It also pins that the reference patch leaves an
# ordinary overworld loss alone (the exemption must not leak to a player who is not in a dungeon).
@pytest.mark.parametrize("path", PATHS)
def test_the_same_death_outside_a_dungeon_still_takes_items(path):
    s = _death(RULE_FNS, path)
    took = seizure(s)
    assert "called recovery/make" in took and "called recovery/bind" in took, took
    assert len(s.nbt[LEDGER]["claims"]) == 1, s.nbt[LEDGER]["claims"]


# The rule, on the reference patch (or the real pack once data/blackout.json has dungeon_exempt): a player holding the
# dungeon tag who loses to a wild Pokemon, in battle or killed outside one, loses nothing to a claim and makes no
# guardian, and still pays the flat charge and goes back to the checkpoint. bo.clm 0 is what makes blackout/arrive say
# "No items were lost."
@pytest.mark.parametrize("path", PATHS)
def test_a_dungeon_death_takes_no_items_and_makes_no_guardian(path):
    s = _death(RULE_FNS, path, player_tags=(DUNGEON_TAG,))
    assert seizure(s) == [], seizure(s)
    assert blackout_cost(s), (s.log, s.get("@s", "bo.clm"))


# The same, held against the GENERATED pack. Expected to fail until the builder adds the exemption (strict: the day it
# passes without the data key, or fails with it, the run says so).
@pytest.mark.xfail(not IMPLEMENTED, reason=NOT_BUILT, strict=True)
@pytest.mark.parametrize("path", PATHS)
def test_the_generated_pack_takes_no_items_in_a_dungeon(path):
    s = _death(FNS, path, player_tags=(DUNGEON_TAG,))
    assert seizure(s) == [], seizure(s)
    assert blackout_cost(s)


# The mutation: strip every line that reads the dungeon tag and the same dungeon death takes items again, in both paths.
# Run on the functions the rule test passes on, so this proves that test is held up by the exemption and nothing else.
@pytest.mark.parametrize("path", PATHS)
def test_removing_the_dungeon_exemption_is_caught(path):
    assert any(DUNGEON_TAG in l for v in RULE_FNS.values() for l in v), "nothing reads the dungeon tag to remove"
    mutant = without_dungeon_tag(RULE_FNS)
    s = _death(mutant, path, player_tags=(DUNGEON_TAG,))
    took = seizure(s)
    assert "called recovery/make" in took and "called recovery/bind" in took, took


# The precedent the rule copies: a victor carrying claims.exempt_tag (the Entei, data/entei_boss.json; the gulch Megas)
# takes nothing from a player who holds no dungeon tag, in both paths, on the real pack. Today this is the ONLY thing
# that keeps a pocket-slot death item-free, and it covers only the Pokemon a keeper tagged.
@pytest.mark.parametrize("path", PATHS)
def test_a_tagged_victor_takes_nothing_on_the_generated_pack(path):
    s = _death(FNS, path, victor_tags=(GM_TAG,))
    assert seizure(s) == [] and blackout_cost(s), seizure(s)


# ------------------------------------------------------------------------------------------------ the other deaths

ENTRY = {
    "blackout/death": "a death the tick sees: the timer's kill @s, a fall, lava, drowning, suffocation, /kill",
    "blackout/battle_loss_npc": "a lost battle to an NPC trainer or boss (cobblemon:npc or rctmod)",
    "blackout/battle_loss_other": "a lost battle with no scriptable victor",
}
TAKERS = ("recovery/make", "recovery/apply_one", "recovery/bind")


def reachable(fns, start):
    """Every function `start` can call, through any chain of function commands (macro names left unresolved)."""
    seen, todo = set(), [start]
    while todo:
        f = todo.pop()
        for l in fns.get(f, []):
            if l.lstrip().startswith("#"):
                continue
            for m in TB.CALL.finditer(l):
                if m.group(1) == NS and m.group(2) not in seen:
                    seen.add(m.group(2))
                    todo.append(m.group(2))
    return seen


def _item_paths(fns):
    return {e: sorted(set(TAKERS) & reachable(fns, e)) for e in ENTRY}


# Without it a timer death, a fall, lava or a trainer loss could start taking items through a call added later (the
# spec's rule 5 promises trainer claims "bind to the route trainers"; in a dungeon they must never apply). On the real
# pack none of the three entry points reaches a function that takes or holds an item.
def test_no_environmental_or_trainer_death_reaches_an_item_claim():
    assert _item_paths(FNS) == {e: [] for e in ENTRY}, _item_paths(FNS)


# The mutation for the test above: a trainer loss given a claim call (as a route-trainer claim would add) is caught.
def test_a_trainer_loss_given_a_claim_is_caught():
    mutant = copy.deepcopy(FNS)
    mutant["blackout/battle_loss_npc"] = mutant["blackout/battle_loss_npc"] + [
        '$function %s:recovery/make {victor:"$(victor)",name:"$(name)",id:"$(id)"}' % NS]
    assert _item_paths(mutant)["blackout/battle_loss_npc"] == sorted(TAKERS), _item_paths(mutant)


# Without it Lenient Death (modpack/config/lenientdeath.json5: preserveItemsOnDeath yes, but it only filters what
# vanilla's Inventory.dropAll drops) and vanilla's own death drop decide what a dungeon death keeps. keepInventory true,
# set by the pack at every load, means dropAll never runs (Lenient Death's only item hook wraps dropAll; read from its
# jar, docs/research/DUNGEON_DEATH.md).
def test_keep_inventory_is_set_at_every_load():
    assert "gamerule keepInventory true" in TB.commands("blackout/load")
    mutant = {k: [l for l in v if "keepInventory" not in l] for k, v in FNS.items()}
    assert "gamerule keepInventory true" not in [l for l in mutant["blackout/load"]]


# ------------------------------------------------------------------------------------------------ delivery

def _delivery(fns, player_tags):
    """A helper resolves P1's open claim while P1 is online: the drops recovery/deliver makes at P1's feet."""
    def world(kind, toks):
        m = re.fullmatch(r"@s\[tag=([^,\]]+)\]", toks[0]) if kind == "entity" else None
        if m:
            return m.group(1) in player_tags
        return False
    s = N.NbtSim(fns=fns, query=RP.strict_query(), world=world,
                 entity=lambda sel, path: P1 if (sel, path) == ("@s", "UUID") else None)
    for f in TB.load_functions():
        s.call(f)
    s.nbt[LEDGER]["claims"] = [RP._claim(1, 1, RP.GUARD_ID, P1, P1_ID)]
    s.calls.clear()
    s.log.clear()
    s.call("recovery/resolve_pid", {"pid": RP.GUARD_ID, "resolver": RP.P2_ID})
    return RP._drops(s), s


# Without it a claim resolved elsewhere drops its items at the feet of a player who is inside a dungeon (resolve_pid
# runs recovery/deliver `as @a at @s`, wherever each player is): items summoned in a pocket slot that is swept, reset
# or left by the next tick's eject are gone. The rule keeps the claim at "deliver" until the player is out; the exit
# runs recovery/deliver (DUNGEON_DEATH.md, rule 4). Reference patch first, then the mutation, then the real pack.
def test_a_resolved_claim_waits_for_a_player_inside_a_dungeon():
    drops, s = _delivery(RULE_FNS, (DUNGEON_TAG,))
    assert drops == [], drops
    assert [c["state"] for c in s.nbt[LEDGER]["claims"]] == ["deliver"], s.nbt[LEDGER]["claims"]
    drops, _ = _delivery(RULE_FNS, ())
    assert drops == [("cobblemon:ultra_ball", 3, tuple(P1))], drops
    drops, _ = _delivery(without_dungeon_tag(RULE_FNS), (DUNGEON_TAG,))
    assert drops, "the mutation (no dungeon check in recovery/deliver) must drop the items in the dungeon"


@pytest.mark.xfail(not IMPLEMENTED, reason=NOT_BUILT, strict=True)
def test_the_generated_pack_holds_delivery_for_a_player_inside_a_dungeon():
    drops, _ = _delivery(FNS, (DUNGEON_TAG,))
    assert drops == [], drops
