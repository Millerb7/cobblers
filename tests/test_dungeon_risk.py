"""The dungeon risk (tools/dungeon_risk.py): the Run Stash, the Run Satchel, the exit's Take it all / Sell it all, death,
and the catch ledger with its dry-run reaper.

WRITTEN BY THE IMPLEMENTER (the 2026-10-23 brief asked the builder for its tests; testing.md allows it when said so):
not an independent audit. The behaviour runs the GENERATED functions on tests/risk_sim.py, a separate interpreter of
vanilla semantics; every expected number below is hand-computed from data/dungeon_risk.json's rule (a price times a
count, the band's bonus), never from the generator. The mutations edit the GENERATOR's source in memory and leave
every data file alone (CLAUDE.md "How to prove an audit is independent").

Not covered (it needs a server, experiments/EXP-098-dungeon-risk): that Cobblemon's callback and MoLang calls behave as
named, that the merchant screen shows out-of-stock offers, NBT types (1b against 1), and real pickup timing.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_risk as K  # noqa: E402
import risk_sim as S  # noqa: E402

DOC = D.load()
RK = K.load()
R = RK["storage"]
NS = "cobblers:dungeons/"
PRICES = {"minecraft:coal": 4, "minecraft:diamond": 100, "minecraft:emerald": 400}
GAIN = RK["stash"]["gain_key"]
POCKET = "cobblers:pocket"


def build(module=K, rk=None):
    rk = rk or RK
    fns = module.functions(DOC, rk, prices=PRICES)
    return {NS + k: v for k, v in fns.items()}, fns


FUNCS, RAW = build()
PRIZES = K.prize_species(DOC)


def world(funcs=None):
    w = S.World(funcs or FUNCS)
    w.call(NS + "risk/load", S.Ctx(None, "minecraft:overworld", [0, 0, 0]))
    return w


def member(w, st=3, pid=7, run=3, dun=1, band=2):
    p = w.player()
    for o, v in (("dg.id", pid), ("dg.st", st), ("dg.run", run), ("dg.dun", dun), ("dg.band", band)):
        w.setv(p.name, o, v)
    p.tags.add(D.blackout_terms()["tag"])
    p.dim, p.pos = POCKET, [100.0, 96.0, 1056.0]
    return p


def drop(w, p, item, dx=2.0, **nbt):
    e = S.Ent("minecraft:item", p.dim, [p.pos[0] + dx, p.pos[1], p.pos[2]], dict(Item=item, PickupDelay=10, Age=0, **nbt))
    w.ents.append(e)
    return e


def stash(w, pid=7):
    return w.storage.get(R, {}).get("s", {}).get("p%d" % pid)


def delivered(w):
    return [e for e in w.ents if e.alive and e.type == "minecraft:item" and e.nbt.get("Age") == -32768]


def coal(n):
    return {"id": "minecraft:coal", "count": n}


SWORD = {"id": "minecraft:iron_sword", "count": 1, "components": {"minecraft:damage": 12}}


# ------------------------------------------------------------------------------------------------ the stash

# Without it a block's drop or a mob's drop reaches the inventory and survives a death: nothing found is at risk.
def test_the_stash_receives_a_pickup_not_the_inventory():
    w = world()
    p = member(w)
    e1, e2 = drop(w, p, coal(3)), drop(w, p, SWORD, dx=-3)
    w.tick()
    assert not e1.alive and not e2.alive
    s = stash(w)
    assert s["counts"] == [{"id": "minecraft:coal", "n": 3}], s
    assert s["items"] == [SWORD], s
    assert p.inv == {}


# A fungible stack is a count, so sixty seam pickups are one line, and two pickups add up.
def test_fungible_pickups_add_into_one_count():
    w = world()
    p = member(w)
    drop(w, p, coal(3))
    drop(w, p, coal(5), dx=1)
    w.tick()
    assert stash(w)["counts"] == [{"id": "minecraft:coal", "n": 8}]


# Without the skip, a player who drops their own item (it has a Thrower) or receives a give's overflow, a relic or our
# own delivery (an Owner) would lose it into the stash.
@pytest.mark.parametrize("extra", [{"Thrower": [1, 2, 3, 4]}, {"Owner": [1, 2, 3, 4]}])
def test_a_players_own_or_owned_item_is_never_stashed(extra):
    w = world()
    p = member(w)
    e = drop(w, p, coal(2), **extra)
    w.tick()
    assert e.alive and "dg.rkx" in e.tags
    assert not (stash(w) or {}).get("counts")


# The owner, 2026-10-23: "keep relics". A relic on the ground (a full inventory) is never stashed.
def test_a_relic_is_kept():
    w = world()
    p = member(w)
    relic = {"id": "minecraft:echo_shard", "count": 1, "components": {"minecraft:custom_data": {"cobblers_relic": "ns_lamp"}}}
    e = drop(w, p, relic)
    p.inv[4] = json.loads(json.dumps(relic))
    w.tick()
    assert e.alive and p.inv[4] == relic


# A Poke Ball on the ground is the player's own ball handed back by a throw that could not catch: never a find.
def test_a_handed_back_ball_is_kept():
    w = world()
    p = member(w)
    e = drop(w, p, {"id": "cobblemon:great_ball", "count": 1})
    w.tick()
    assert e.alive and not (stash(w) or {}).get("items")


# A chest's or a loot give's item carries the gain key; the sweep moves exactly that slot, strips the key, and leaves
# the player's own stacks alone.
def test_a_marked_inventory_stack_moves_to_the_stash_and_loses_its_key():
    w = world()
    p = member(w)
    p.inv[5] = {"id": "minecraft:diamond", "count": 2, "components": {"minecraft:custom_data": {GAIN: 1}}}
    p.inv[6] = {"id": "minecraft:emerald", "count": 9, "components": {"minecraft:custom_data": {GAIN: 1, "other": 1}}}
    p.inv[7] = {"id": "minecraft:diamond", "count": 30}
    w.tick()
    assert 5 not in p.inv and 6 not in p.inv and p.inv[7]["count"] == 30
    s = stash(w)
    assert {"id": "minecraft:diamond", "n": 2} in s["counts"]
    assert {"id": "minecraft:emerald", "count": 9, "components": {"minecraft:custom_data": {"other": 1}}} in s["items"]


# Outside the pocket or outside a live run nothing is swept.
@pytest.mark.parametrize("where", ["overworld", "entry_room"])
def test_nothing_is_swept_outside_a_live_run_in_the_pocket(where):
    w = world()
    p = member(w, st=2 if where == "entry_room" else 3)
    if where == "overworld":
        p.dim = "minecraft:overworld"
    e = drop(w, p, coal(1))
    w.tick()
    assert e.alive


# ------------------------------------------------------------------------------------------------ the exit

def won_with(w, p, items=(), counts=(), bossd=0):
    w.storage.setdefault(R, {}).setdefault("s", {})["p7"] = {"items": list(items), "counts": list(counts)}
    w.setv(p.name, "dg.bossd", bossd)
    w.as_player(p, "risk/won")
    w.as_player(p, "risk/forfeit")     # m/end follows pay on every clean exit


# Take it all: every stack comes back as an item entity the player owns, never despawning; the stash is gone.
def test_exit_take_delivers_everything():
    w = world()
    p = member(w)
    won_with(w, p, items=[SWORD], counts=[{"id": "minecraft:coal", "n": 70}])
    assert w.score(p, "dg.rkw") == 1
    w.setv(p.name, "dg.rkc", 1)
    w.tick()
    got = delivered(w)
    assert sorted((e.nbt["Item"]["id"], e.nbt["Item"]["count"]) for e in got) == \
        [("minecraft:coal", 6), ("minecraft:coal", 64), ("minecraft:iron_sword", 1)]
    assert all(e.nbt["Owner"] == p.uuid and e.nbt["PickupDelay"] == 0 for e in got)
    assert stash(w) is None and w.score(p, "dg.rkw") == 0


# Sell it all: the bank's unit price times the count, plus the band's bonus (band 2: 2%), paid once; what the bank does
# not buy (the sword) is delivered; nothing sold is delivered too.
def test_exit_sell_pays_the_bank_price_and_delivers_the_rest():
    w = world()
    p = member(w, band=2)
    won_with(w, p, items=[SWORD, {"id": "minecraft:emerald", "count": 2}], counts=[{"id": "minecraft:coal", "n": 70}])
    w.setv(p.name, "dg.rkc", 2)
    w.tick()
    want = (70 * 4 + 2 * 400) * (100 + RK["exit"]["bonus_pct_by_band"]["2"]) // 100
    assert w.money[p.name] == want
    assert [(e.nbt["Item"]["id"]) for e in delivered(w)] == ["minecraft:iron_sword"]
    assert stash(w) is None


# The boss bonus adds on top of the band's.
def test_the_boss_bonus_adds():
    w = world()
    p = member(w, band=1)
    won_with(w, p, counts=[{"id": "minecraft:diamond", "n": 10}], bossd=1)
    w.setv(p.name, "dg.rkc", 2)
    w.tick()
    assert w.money[p.name] == 1000 * (100 + RK["exit"]["bonus_pct_by_band"]["1"] + RK["exit"]["boss_bonus_pct"]) // 100


# A pay the balance does not show sells nothing: every stack comes to the player instead (never lost).
def test_a_failed_pay_delivers_everything():
    w = world()
    p = member(w)
    w.pay_fails = True
    won_with(w, p, counts=[{"id": "minecraft:coal", "n": 10}])
    w.setv(p.name, "dg.rkc", 2)
    w.tick()
    assert w.money[p.name] == 0
    assert [(e.nbt["Item"]["id"], e.nbt["Item"]["count"]) for e in delivered(w)] == [("minecraft:coal", 10)]


# Unanswered, the exit takes it all: an exit never loses an item.
def test_an_unanswered_exit_takes_it_all():
    w = world()
    p = member(w)
    won_with(w, p, counts=[{"id": "minecraft:coal", "n": 3}])
    w.tick(RK["exit"]["choice_ticks"] - 1)
    assert not delivered(w)
    w.tick(1)
    assert len(delivered(w)) == 1 and w.score(p, "dg.rkw") == 0


# An empty satchel at a clean exit asks nothing and the following m/end does not treat it as a loss.
def test_an_empty_clean_exit_is_not_a_loss():
    w = world()
    p = member(w)
    won_with(w, p)
    assert w.score(p, "dg.rkw") == 0
    assert not any("Lost with the run" in m[1] for m in p.messages)


# ------------------------------------------------------------------------------------------------ death

# Any end that is not a clean exit deletes the stash, and a marked stack still in the inventory goes with it.
def test_death_clears_the_stash():
    w = world()
    p = member(w)
    drop(w, p, coal(4))
    w.tick()
    assert stash(w)["counts"]
    p.inv[3] = {"id": "minecraft:coal", "count": 1, "components": {"minecraft:custom_data": {GAIN: 1}}}
    p.inv[8] = {"id": "minecraft:coal", "count": 16}
    w.as_player(p, "risk/forfeit")
    assert stash(w) is None
    assert 3 not in p.inv and p.inv[8]["count"] == 16
    assert any("Lost with the run" in m[1] for m in p.messages)


# A satchel waiting for its choice is not forfeited by the run's end or a later death: it is the player's.
def test_a_waiting_satchel_survives_the_end():
    w = world()
    p = member(w)
    won_with(w, p, counts=[{"id": "minecraft:coal", "n": 3}])
    w.as_player(p, "risk/forfeit")
    assert stash(w)["counts"]


# A new run's threshold delivers an unanswered satchel first, owned by the player so it is never re-stashed.
def test_the_next_threshold_delivers_a_waiting_satchel():
    w = world()
    p = member(w)
    won_with(w, p, counts=[{"id": "minecraft:coal", "n": 3}])
    w.as_player(p, "risk/begin")
    got = delivered(w)
    assert len(got) == 1 and got[0].nbt["Owner"] == p.uuid
    w.tick()
    assert got[0].alive
    assert stash(w) == {"items": [], "counts": []}


# ------------------------------------------------------------------------------------------------ the satchel's view

# The satchel shows the stash as offers, every one out of stock, so the screen shows and nothing can be taken.
def test_the_satchel_view_lists_the_stash_and_sells_nothing():
    w = world()
    p = member(w)
    w.storage.setdefault(R, {}).setdefault("s", {})["p7"] = {"items": [SWORD], "counts": [{"id": "minecraft:coal", "n": 70}]}
    p.inv[0] = {"id": "minecraft:carrot_on_a_stick", "count": 1,
                "components": {"minecraft:custom_data": {RK["satchel"]["custom_data_key"]: 1}}}
    w.setv(p.name, "dg.rku", 1)
    w.tick()
    viewers = [e for e in w.ents if e.alive and e.type == RK["satchel"]["view"]["entity"]]
    assert len(viewers) == 1
    offers = viewers[0].nbt["Offers"]["Recipes"]
    assert [o["sell"]["id"] for o in offers] == ["minecraft:iron_sword", "minecraft:coal"]
    assert offers[1]["sell"]["count"] == 64
    assert all(o["uses"] >= o["maxUses"] for o in offers)
    w.tick(RK["satchel"]["view"]["life_ticks"])
    assert not viewers[0].alive


# ------------------------------------------------------------------------------------------------ catches

def catch(w, p, pid, sp="cobblemon:rattata", sh=0):
    w.call(NS + "risk/catch", S.Ctx(p, p.dim, p.pos), {"pid": pid, "sp": sp, "sh": sh})


def ledger(w):
    return w.storage.get(R, {}).get("ledger", [])


# Each catch in a live run is logged by its UUID with the run's number.
def test_a_catch_is_logged_by_uuid():
    w = world()
    p = member(w)
    catch(w, p, "aaaa-1")
    assert [(e["pid"], e["who"], e["run"]) for e in ledger(w)] == [("aaaa-1", 7, 3)]


# Outside a live run a catch is nobody's business.
def test_a_catch_outside_a_run_is_not_logged():
    w = world()
    p = member(w, st=0)
    catch(w, p, "aaaa-1")
    assert ledger(w) == []


# "everything you get should be risked, except cool catches": a shiny and the dungeon's own prize are never logged.
def test_shiny_and_prize_are_exempt():
    w = world()
    p = member(w, dun=1)
    catch(w, p, "s-1", sh=1)
    catch(w, p, "p-1", sp=PRIZES[1][0])
    assert ledger(w) == []


def failed_run_with(w, p, party, pc=()):
    p.party = [dict(x) for x in party]
    p.pc = [dict(x) for x in pc]
    w.as_player(p, "risk/forfeit")
    w.drain()


# The dry run (the default tonight) looks each UUID up and logs; it removes nothing.
def test_the_dry_run_removes_nothing_and_logs_what_it_would():
    assert RK["catches"]["mode"] == "dry_run"
    w = world()
    p = member(w)
    catch(w, p, "a-1")
    catch(w, p, "a-2")
    catch(w, p, "a-3")
    failed_run_with(w, p, party=[{"id": "a-1"}, {"id": "mine"}], pc=[{"id": "a-2"}])
    assert [x["id"] for x in p.party] == ["a-1", "mine"] and [x["id"] for x in p.pc] == ["a-2"]
    log = w.storage[R]["log"]
    assert [(x["pid"], K.OUTCOMES[x["o"]]) for x in log] == [
        ("a-1", "would_remove_party"), ("a-2", "would_remove_pc"), ("a-3", "not_found")]
    assert ledger(w) == []


def live_world():
    rk = json.loads(json.dumps(RK))
    rk["catches"]["mode"] = "remove"
    funcs, _ = build(rk=rk)
    return world(funcs)


# With removal on, exactly the logged UUIDs go, from the party or the PC, never another Pokemon; and every guard keeps.
def test_removal_takes_exactly_the_logged_uuids():
    w = live_world()
    p = member(w)
    for pid in ("a-1", "a-2", "held", "gone"):
        catch(w, p, pid)
    failed_run_with(w, p, party=[{"id": "a-1"}, {"id": "mine"}, {"id": "held", "held": True}],
                    pc=[{"id": "a-2"}, {"id": "old"}])
    assert [x["id"] for x in p.party] == ["mine", "held"] and [x["id"] for x in p.pc] == ["old"]
    outcomes = {x["pid"]: K.OUTCOMES[x["o"]] for x in w.storage[R]["log"]}
    assert outcomes == {"a-1": "removed_party", "a-2": "removed_pc", "held": "kept_holds_item", "gone": "not_found"}


@pytest.mark.parametrize("case", ["in_battle", "last_in_party"])
def test_removal_guards_keep(case):
    w = live_world()
    p = member(w)
    catch(w, p, "a-1")
    p.in_battle = case == "in_battle"
    party = [{"id": "a-1"}] + ([] if case == "last_in_party" else [{"id": "mine"}])
    failed_run_with(w, p, party=party)
    assert any(x["id"] == "a-1" for x in p.party)


# A clean exit keeps the catches: the ledger is cleared and nothing is looked up.
def test_a_clean_exit_keeps_the_catches():
    w = live_world()
    p = member(w)
    catch(w, p, "a-1")
    p.party = [{"id": "a-1"}, {"id": "mine"}]
    won_with(w, p)
    w.drain()
    assert [x["id"] for x in p.party] == ["a-1", "mine"] and ledger(w) == []


# An entry of an older run is never acted on (a crash left it): the reaper takes only this run's.
def test_an_older_runs_entry_is_never_removed():
    w = live_world()
    p = member(w, run=2)
    catch(w, p, "old-1")
    w.setv(p.name, "dg.run", 3)
    failed_run_with(w, p, party=[{"id": "old-1"}, {"id": "mine"}])
    assert [x["id"] for x in p.party] == ["old-1", "mine"]


# ------------------------------------------------------------------------------------------------ the generated text

def test_the_dry_script_cannot_remove_and_the_live_one_carries_every_guard():
    dry, live = " ".join(RAW["risk/catch/dry"]), " ".join(RAW["risk/catch/live"])
    assert "remove_by_id" not in dry
    for guard in ("q.player.in_battle == 1", "t.e == 0", "q.player.party.count <= 1"):
        assert guard in live, guard
    assert "q.pokemon.id" not in dry
    cb = K.callback(RK)
    assert "t.pid = t.pk.id;" in cb and "t.pk.is_shiny" in cb


def test_load_sets_removal_from_data_only():
    assert "data modify storage %s cfg set value {remove:0b}" % R in RAW["risk/load"]


def test_loot_tables_are_marked_but_never_the_global_fishing_table():
    table = json.dumps({"type": "minecraft:chest", "pools": []})
    files = {RK["stash"]["loot_table_prefix"] + "vault/x/b1.json": table,
             "data/cobblemon/loot_table/fishing/pokerod.json": table}
    K.patch_files(DOC, files, RK)
    marked = json.loads(files[RK["stash"]["loot_table_prefix"] + "vault/x/b1.json"])
    assert {"function": "minecraft:set_custom_data", "tag": "{%s:1b}" % GAIN} in marked["functions"]
    assert files["data/cobblemon/loot_table/fishing/pokerod.json"] == table
    assert K.CALLBACK_PATH in files


def engine_fns():
    pick = D.pick_give(DOC, None)
    return {"slot/s1/arrive": [D.HEAD, "give @s %s 1" % pick], "slot/s1/start": [D.HEAD, "scoreboard players set @s dg.st 3"],
            "slot/s1/end": [D.HEAD, "clear @s %s" % D.pick_match(DOC)], "m/end": [D.HEAD, "clear @s %s" % D.pick_match(DOC)],
            "pay": [D.HEAD, "scoreboard players set @s dg.esc 0"], "m/restore": [D.HEAD, "clear @s %s" % D.pick_match(DOC)]}


# The engine's hooks: the satchel with the pick and taken where the pick is, the stash begun at the threshold, the sale
# offered from pay, and forfeit FIRST in every end (before anything resets the run's scores).
def test_the_engine_hooks():
    fns = engine_fns()
    K.patch_functions(DOC, fns, RK)
    assert any("cobblers_dg_satchel:1b" in l and l.startswith("give") for l in fns["slot/s1/arrive"])
    assert fns["m/end"][1] == "function %srisk/forfeit" % NS and fns["slot/s1/end"][1] == "function %srisk/forfeit" % NS
    assert fns["pay"][-1] == "function %srisk/won" % NS and fns["slot/s1/start"][-1] == "function %srisk/begin" % NS
    assert any(K.satchel_match(RK) in l for l in fns["m/restore"])


def test_a_missing_engine_hook_fails_closed():
    fns = engine_fns()
    del fns["pay"]
    with pytest.raises(K.RiskError):
        K.patch_functions(DOC, fns, RK)


def test_the_data_names_every_key_that_must_never_be_stashed():
    assert K.problems(RK, DOC) == []
    bad = json.loads(json.dumps(RK))
    bad["stash"]["skip_custom_data_keys"].remove("cobblers_relic")
    assert any("cobblers_relic" in b for b in K.problems(bad, DOC))


# ------------------------------------------------------------------------------------------------ mutations

def mutant(old, new):
    src = (ROOT / "tools" / "dungeon_risk.py").read_text(encoding="utf-8")
    assert src.count(old) == 1, old
    m = types.ModuleType("dungeon_risk_mutant")
    m.__file__ = str(ROOT / "tools" / "dungeon_risk.py")
    exec(compile(src.replace(old, new), m.__file__, "exec"), m.__dict__)
    return m


MUTATIONS = {
    "no_thrower_skip": ('ent.append("execute if data entity @s %s run return run tag @s add %s" % (f, SEEN_TAG))', "pass",
                        test_a_players_own_or_owned_item_is_never_stashed, ({"Thrower": [1, 2, 3, 4]},)),
    "death_keeps_stash": ('"$data remove storage %s s.p$(id)" % R],\n        "a macro: the stash deleted', '"$scoreboard players set #k dg.t $(id)"],\n        "a macro: the stash deleted',
                          test_death_clears_the_stash, ()),
    "dry_run_removes": ('"execute if data storage %s cfg{remove:1b} run return run function %s with storage %s cur" % (R, RF("catch/live"), R)',
                        '"return run function %s with storage %s cur" % (RF("catch/live"), R)',
                        test_the_dry_run_removes_nothing_and_logs_what_it_would, ()),
    "shiny_at_stake": ('catch.append("execute if data storage %s c{sh:1b} run scoreboard players set #ex %s 1" % (R, t))', "pass",
                       test_shiny_and_prize_are_exempt, ()),
    "sell_unverified": ('"execute unless score #after %s = #want %s run return run function %s" % (t, t, RF("exit/take")),', "",
                        test_a_failed_pay_delivers_everything, ()),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_each_generator_mutation_is_caught(name, monkeypatch):
    old, new, test, args = MUTATIONS[name]
    m = mutant(old, new)
    funcs, raw = build(module=m)
    monkeypatch.setitem(globals(), "FUNCS", funcs)
    monkeypatch.setitem(globals(), "RAW", raw)
    real_build = build

    def mutated_build(module=K, rk=None):
        return real_build(module=m, rk=rk)
    monkeypatch.setitem(globals(), "build", mutated_build)
    with pytest.raises(AssertionError):
        test(*args)
