"""tools/ambient_idle_audit.py: the idle Pokemon's independent audit.

Three layers:
  1. the audit's own checks on hand-built inputs with hand-computable answers (always run);
  2. the audit on the built pack and town (NOT_EXECUTED without a full build/, the heightmap and the jar);
  3. independence: tools/ambient_idle.py MUTATED (its source text changed in memory, data/ambient.json untouched) --
     the wake radius, the awake list, the claim's flags, the spread rule -- and the audit must catch each.

Not covered: anything in a running game (whether a sleeper sleeps, wakes or stands; whether a follower follows; whether
a tp holds). A skip is not a pass.
"""
from __future__ import annotations

import json
import math
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ambient_idle_audit as A  # noqa: E402

GEN = ROOT / "tools" / "ambient_idle.py"
SLEEPER = ["cobblemon:core", "cobblemon:looks_around", "cobblemon:pokemon_sleeps"]
AWAKE = ["cobblemon:core", "cobblemon:looks_around"]


def snbt(ids):
    return "[%s]" % ",".join('"%s"' % b for b in ids)


def fake_pack(wake_r=16, rest_r=24, awake=AWAKE, doze=SLEEPER, extra=None):
    """A two-idler pack in the emitted shape: one sitter, one sleeper."""
    F = "cobblers:ambient_idle"
    fns = {
        "tick": ["scoreboard players add #clock cobblers_ambi 1",
                 "execute if score #clock cobblers_ambi matches 40.. run function %s/keep_all" % F,
                 "scoreboard players add #wake cobblers_ambi 1",
                 "execute if score #wake cobblers_ambi matches 10.. run function %s/wakes" % F],
        "keep_all": ["scoreboard players set #clock cobblers_ambi 0",
                     "execute positioned 0 64 0 if entity @a[distance=..70] run function %s/t/town/keep" % F],
        "wakes": ["scoreboard players set #wake cobblers_ambi 0",
                  "execute as @e[type=cobblemon:pokemon,tag=cobblers.amb.dozer] at @s if entity @a[distance=..%d] "
                  "run function %s/wake" % (wake_r, F),
                  "execute as @e[type=cobblemon:pokemon,tag=cobblers.amb.woken] at @s unless entity @a[distance=..%d] "
                  "run function %s/doze" % (rest_r, F)],
        "wake": ["data merge entity @s {BehavioursAreCustom:1b,Behaviours:%s}" % snbt(awake),
                 "tag @s remove cobblers.amb.dozer", "tag @s add cobblers.amb.woken"],
        "doze": ["data merge entity @s {BehavioursAreCustom:1b,Behaviours:%s}" % snbt(doze),
                 "tag @s remove cobblers.amb.woken", "tag @s add cobblers.amb.dozer"],
        "spawn_at": ["$spawnpokemonat $(x) $(y) $(z) $(species) level=$(level) uncatchable no_ai"],
        "t/town/keep": [],
    }
    flags = 'PersistenceRequired:1b,Invulnerable:1b,Unbattleable:1b,DeathLootTable:"minecraft:empty"'
    for iid, (x, z), sp, kind in (("idle_town_01", (1, 1), "geodude", "still"), ("idle_town_02", (9, 1), "snorlax",
                                                                                   "sleeper")):
        sel = "@e[type=cobblemon:pokemon,tag=cobblers.amb.%s]" % iid
        fns["t/town/keep"] += ["execute store result score #n cobblers_ambi if entity %s" % sel,
                               "execute as %s run tp @s %d.5 65 %d.5 0 0" % (sel, x, z)]
        fns["i/%s/spawn" % iid] = [
            'function %s/spawn_at {x:"%d.5",y:"65",z:"%d.5",species:"%s",level:10}' % (F, x, z, sp),
            "execute positioned %d.5 65 %d.5 as @e[type=cobblemon:pokemon,tag=!cobblers.amb,nbt={NoAI:1b},"
            "distance=..2,limit=1,sort=nearest] run function %s/i/%s/claim" % (x, z, F, iid)]
        claim = ["tag @s add cobblers.amb", "tag @s add cobblers.amb.idle", "tag @s add cobblers.amb.%s" % iid]
        if kind == "still":
            claim.append("data merge entity @s {NoAI:1b,%s}" % flags)
        else:
            claim += ["data merge entity @s {NoAI:0b,%s,BehavioursAreCustom:1b,Behaviours:%s}" % (flags, snbt(SLEEPER)),
                      "tag @s add cobblers.amb.dozer"]
        fns["i/%s/claim" % iid] = claim
    fns.update(extra or {})
    return fns


# ------------------------------------------------------------------------------------------------ 1. the checks

# The groups rule: without it a ring of Pokemon (the layout that bent the frame rate) would pass as spread.
def test_four_pokemon_two_blocks_apart_are_one_group_too_many():
    line = [(0, 0, "a"), (2, 0, "b"), (4, 0, "c"), (6, 0, "d")]
    assert [len(c) for c in A.clusters(line)] == [4]
    assert len(A.check_groups({"t": line})) == 1
    split = [(0, 0, "a"), (2, 0, "b"), (4, 0, "c"), (10, 0, "d")]          # d is 6 from c: its own group
    assert sorted(len(c) for c in A.clusters(split)) == [1, 3]
    assert A.check_groups({"t": split}) == []


# The link distance is the frame test's ring spacing, inclusive: without this the boundary could drift silently.
def test_the_group_link_is_three_blocks_inclusive():
    assert len(A.clusters([(0, 0, "a"), (3, 0, "b")])) == 1
    assert len(A.clusters([(0, 0, "a"), (3.01, 0, "b")])) == 2
    assert len(A.clusters([(0, 0, "a"), (2.1, 2.1, "b")])) == 1                  # 2.97 apart, diagonally


# The owner's cap: without it a 31st Pokemon in a town would pass.
def test_the_cap_is_thirty_a_town():
    assert A.check_cap({"t": (30, "")}) == []
    assert [p[0] for p in A.check_cap({"t": (31, "")})] == ["cap"]


# The wake rule read from the emitted lines: without it a pack waking at 15 or re-sleeping at 16 would pass.
def test_the_wake_radius_is_sixteen_and_the_rest_radius_larger():
    fns = fake_pack()
    assert A.check_wake(A.keeper(fns), A.parse(fns)["idlers"]) == []
    for bad, why in ((fake_pack(wake_r=15), "wake"), (fake_pack(rest_r=16), "doze"),
                     (fake_pack(awake=SLEEPER), "awake_list"), (fake_pack(doze=AWAKE), "doze_list")):
        assert why in {p[1] for p in A.check_wake(A.keeper(bad), A.parse(bad)["idlers"])}, why


# Brain remakes: without this a keep line merging into a sleeper (which drops its sleep) would pass.
def test_a_merge_outside_claim_wake_and_doze_is_caught(tmp_path):
    fns = fake_pack(extra={"t/town/keep": fake_pack()["t/town/keep"] + ["execute as @e[tag=cobblers.amb.dozer] run "
                                                                         "data merge entity @s {Silent:1b}"]})
    assert ("merge", "idle:t/town/keep") in {p[:2] for p in A.check_merges(tmp_path, fns)}
    d = tmp_path / "other" / "data" / "x" / "function"
    d.mkdir(parents=True)
    (d / "a.mcfunction").write_text("execute as @e[type=cobblemon:pokemon,tag=cobblers.amb.brock_carrier] run data "
                                    "merge entity @s {NoAI:1b}\n", encoding="utf-8")
    assert A.check_merges(tmp_path, fake_pack()) == []                            # a worker's own tag: not a sleeper
    (d / "b.mcfunction").write_text("execute as @e[type=cobblemon:pokemon] run data merge entity @s {NoAI:1b}\n"
                                    "data modify entity @e[tag=cobblers.amb.woken,limit=1] Silent set value 1b\n",
                                    encoding="utf-8")
    assert len(A.check_merges(tmp_path, fake_pack())) == 2


# The flags: without this an idler missing Unbattleable (a wild battle in the square) would pass.
def test_every_idler_carries_the_workers_flags():
    fns = fake_pack()
    idl = A.parse(fns)["idlers"]
    wf = {"PersistenceRequired", "Invulnerable", "Unbattleable", "DeathLootTable:empty"}
    assert A.check_flags(idl, wf, "$spawnpokemonat ... uncatchable no_ai", fns["spawn_at"][0]) == []
    assert idl["idle_town_01"]["kind"] == "still" and idl["idle_town_02"]["kind"] == "sleeper"
    assert idl["idle_town_02"]["at"] == (9.5, 65.0, 1.5)
    bad = A.check_flags(idl, wf | {"Silent"}, "uncatchable", "$spawnpokemonat $(x) no_ai")
    assert {p[1] for p in bad} == {"spawn_at", "idle_town_01", "idle_town_02"}


# The sleeper gate: without it a night sleeper, or one the day's light excludes, would be put in a town by day.
def test_sleepers_are_judged_from_the_species_resting_data():
    def rest(lo, hi, times):
        return {"canSleep": True, "times": set(times), "light": (lo, hi), "width": 1, "height": 1}
    R = {"snorlax": rest(0, 15, ["any"]), "slakoth": rest(0, 14, ["any"]), "litwick": rest(12, 15, ["day"]),
         "pidgey": rest(0, 4, ["night"]), "buneary": rest(0, 4, ["night"])}
    idl = {i: {"id": i, "kind": "sleeper", "species": s, "town": t} for i, s, t in (
        ("a", "snorlax", "x"), ("b", "slakoth", "x"), ("c", "litwick", "x"), ("d", "pidgey", "x"),
        ("e", "buneary", "lopunny_house"), ("f", "buneary", "lopunny_house"))}
    keys = {p[1] for p in A.check_sleepers(idl, R, {"e": 3, "f": 5})}
    assert keys == {"slakoth:brightness", "litwick:emission", "pidgey", "pidgey:brightness", "f:brightness"}


# "Following a kid around": without this a follower homed on an empty square would pass.
def test_a_follower_needs_an_npc_within_its_home_radius_plus_one():
    f = {"id": "f", "kind": "follower", "town": "x", "at": (0.5, 65.0, 0.5), "home": (0.5, 65.0, 0.5), "home_radius": 3.0}
    assert A.check_followers({"f": f}, [("kid", 4.5, 65.0, 0.5)]) == []            # exactly 4
    assert len(A.check_followers({"f": f}, [("kid", 4.6, 65.0, 0.5)])) == 1
    moved = dict(f, home=(2.5, 65.0, 0.5))
    assert "not its spot" in A.check_followers({"f": moved}, [("kid", 1.5, 65.0, 0.5)])[0][2]


class FakeModel:
    def __init__(self, cells):
        self.cells = {k: (v, "test") for k, v in cells.items()}

    def at(self, x, y, z):
        c = self.cells.get((x, y, z))
        return c[0] if c else "minecraft:air"


# The night-light estimate: without it a sleeper beside the snow house's lanterns would be judged dark.
def test_block_light_floods_from_emitters_and_stops_at_walls():
    import npc_spot_sweep as SW
    assert A.block_light(FakeModel({(0, 0, 0): "minecraft:lantern[hanging=false]"}), SW, 5, 0, 0) == 10
    assert A.block_light(FakeModel({(0, 0, 0): "minecraft:soul_lantern"}), SW, 0, 3, 4) == 3
    wall = {(2, y, z): "minecraft:stone" for y in range(-20, 21) for z in range(-20, 21)}
    wall[(0, 0, 0)] = "minecraft:lantern"
    assert A.block_light(FakeModel(wall), SW, 5, 0, 0) == 0
    wall[(2, 0, 0)] = "minecraft:glass"                                            # light passes glass
    assert A.block_light(FakeModel(wall), SW, 5, 0, 0) == 10


# The cost is counted from the lines: without it a keeper that grew per idler on every tick would go unnoticed.
def test_the_cost_counts_command_lines_not_comments():
    fns = fake_pack(extra={"wakes": ["# a comment"] + fake_pack()["wakes"]})
    c = A.cost(A.keeper(fns), fns)
    assert (c["tick"], c["keep_all"], c["wakes"]) == (4, 2, 3)
    assert c["always_per_tick"] == round(4 + 2 / 40 + 3 / 10, 3)
    assert c["towns"]["town"] == round(4 / 40, 3)


# ------------------------------------------------------------------------------------------------ 2. the real pack

def built():
    if not (A.PACKS / A.IDLE_PACK / A.FN / "ambient_idle" / "tick.mcfunction").is_file():
        pytest.skip("NOT_EXECUTED: the idle pack is not built (python tools/ambient_idle.py build)")
    if not (A.PACKS / "cobblers_reapply").is_dir():
        pytest.skip("NOT_EXECUTED: no full build/ to replay the town from (reapply.py prepare)")


def jar():
    import battle_sim
    try:
        return battle_sim.find_jar()
    except SystemExit:
        pytest.skip("NOT_EXECUTED: no Cobblemon 1.8 jar on this machine")


def heightmap():
    import ground as G
    try:
        G.load()
    except (SystemExit, OSError, FileNotFoundError) as e:
        pytest.skip("NOT_EXECUTED: no canonical heightmap here (%s)" % e)


# The whole audit on what prepare built: without it the checks above would only ever see fixtures.
def test_the_built_idle_pokemon_have_no_unrecorded_defect():
    built()
    jar()
    heightmap()
    res = A.audit()
    assert res["idlers"] >= 1
    assert not res["problems"], "\n".join(p[2] for p in res["problems"][:20])
    assert not res["known_fixed"], "KNOWN entries no longer found (remove them): %s" % res["known_fixed"]


# ------------------------------------------------------------------------------------------------ 3. independence

def mutated(old, new):
    """tools/ambient_idle.py with one substring replaced, as a fresh module. data/ambient.json is not touched."""
    src = GEN.read_text(encoding="utf-8")
    assert src.count(old) == 1, "the mutation's target moved in tools/ambient_idle.py: %r" % old
    mod = types.ModuleType("ambient_idle_mutant")
    mod.__file__ = str(GEN)
    exec(compile(src.replace(old, new), str(GEN), "exec"), mod.__dict__)
    return mod


def plan_doc():
    p = ROOT / "derived" / "ambient" / "idle_plan.json"
    if not p.is_file():
        pytest.skip("NOT_EXECUTED: no derived/ambient/idle_plan.json (python tools/ambient_idle.py build)")
    return json.loads(p.read_text(encoding="utf-8"))


def judge(fns):
    d = A.parse(fns)
    return A.check_wake(A.keeper(fns), d["idlers"]), d["idlers"]


# Mutating the generator's wake radius must fail the audit: without this the wake check could share the
# generator's number and pass whatever it emits.
def test_a_generator_waking_at_seventeen_is_caught():
    pl = plan_doc()
    import ambient_idle
    assert judge(ambient_idle.functions(pl))[0] == []                            # the unmutated generator passes
    mod = mutated('% (DOZER, rules["wake_radius"], F)', '% (DOZER, rules["wake_radius"] + 1, F)')
    assert "wake" in {p[1] for p in judge(mod.functions(pl))[0]}


# Mutating the awake list into the sleeper list must fail: a "woken" sleeper that keeps pokemon_sleeps never wakes.
def test_a_generator_that_wakes_into_the_sleeper_list_is_caught():
    pl = plan_doc()
    mod = mutated('snbt_list(beh["awake"])', 'snbt_list(beh["sleeper"])')
    assert "awake_list" in {p[1] for p in judge(mod.functions(pl))[0]}


# Mutating the claim's flags must fail: the flags are judged against the WORKERS' pack, not the generator's string.
def test_a_generator_dropping_unbattleable_is_caught():
    pl = plan_doc()
    pos, wflags, wmacro = A.worker_pack(A.PACKS)
    if not wflags:
        pytest.skip("NOT_EXECUTED: the workers' pack is not built (python tools/ambient.py build)")
    import ambient_idle
    fns = ambient_idle.functions(pl)
    assert A.check_flags(A.parse(fns)["idlers"], wflags, wmacro, fns["spawn_at"][0]) == []
    mod = mutated("Invulnerable:1b,Unbattleable:1b,", "Invulnerable:1b,")
    fns = mod.functions(pl)
    bad = A.check_flags(A.parse(fns)["idlers"], wflags, wmacro, fns["spawn_at"][0])
    assert len(bad) == sum(len(v) for v in pl["towns"].values())


# Disabling the spread rule inside place_town must fail the groups check: without this the groups check could pass
# any layout the generator makes (it is measured on positions, not on the generator's own group bookkeeping).
def test_a_generator_without_its_spread_rule_is_caught():
    heightmap()
    plan_doc()
    import ground as G
    mod = mutated("if any(math.dist((ax, az), u) < gap for u in used_anchor):", "if False:")
    town = "gym1_town"
    data = mod.load()
    rules = dict(data["idle"]["rules"], water_changed_margin=data["rules"]["water_changed_margin"])
    kinds_on = [k for k in rules["enabled_kinds"] if k in mod.KINDS]
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    dressing = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))
    import ambient
    water = None
    if ambient.WATER_CHANGED.is_file():
        import numpy as np
        water = np.load(ambient.WATER_CHANGED)
    site = mod.TownSite(town, G.Ground(), doc, dressing, water, rules, mod.worker_cells(), mod.npc_spots(),
                        mod.shrine_spots())
    idlers, _short = mod.place_town(town, data["idle"]["towns"][town], site, rules, kinds_on)
    pts = [(i["at"][0], i["at"][2], i["id"]) for i in idlers]
    assert A.check_groups({town: pts}), "the spread rule removed and still no group over %d" % A.GROUP_MAX
    clean = [(i["at"][0], i["at"][2], i["id"]) for i in plan_doc()["towns"][town]]
    assert A.check_groups({town: clean}) == []
    assert math.isclose(A.LINK, 3.0)
