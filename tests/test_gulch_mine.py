"""The southern Rift's mega site, prototype slice: tools/gulch_mine.py's pack, tools/mega_recipes.py and step R9S.

Written by the test author, not by the session that built the slice (9339ec2..2f1ed19), whose offline audit is
tools/gulch_mine_audit.py. The gate, Cutter, keeper and face functions read only the spec, so most of this runs
without the heightmap, on tests/gulch_sim.py's world model (executors, selectors, blocks, game time).

Independent sources:
  - docs/world-building/SOUTHERN_RIFT_MEGA.md: 7.1 (the jars' stones; ZAMegas' eleven), 7.3 (the sixty stones the
    Cutters offer and the thirty-two left out, by name), 7.2 and decision 5A (raw + 1 diamond, unlimited, nothing
    bought back), 6.2 (the Megas uncatchable, tagged, leashed), decisions 3 (the gulch at six badges), 9 (no claim for
    a Mega) and 12 (step R9S); section 13, the owner's redesign (2 raw stones a keyed stone, crafting too; the faces
    unmineable scenery, warded for good, the restore retired; Megas back in their dens on a respawn timer no
    repeatable action resets);
  - data/gulch_mine.json: the flag, the gate's boxes and points, the zone polygon (tested here by its own words: a
    column is in when its centre is inside, even-odd), the offer, the benches, the faces' ward, the Megas, the clock;
  - the pinned jars (read with zipfile, skipped without them): Mega Showdown 1.0.2 and ZAMegas 1.7.7, their mega
    definitions and recipes;
  - vanilla 1.21.1: the villager's MerchantOffer codec fields; a location predicate tests the feet; an effect's level
    is its amplifier + 1; a player's eyes are 1.62 above the feet and block reach is 4.5.

With the heightmap (slow, skipped without COBBLERS_SOURCE_ROOT): the built pack writes no meteorid ore, spawn
condition, fluid or light block; every write is inside the grid and the zone but the rockfall, road and lamps the data
allows outside; the ward keeps the plug and the grille out of reach; each Mega's anchor is a floor cell with its head
room, in its hall.

Not covered, and it needs a running server (SOUTHERN_RIFT_MEGA.md section 10): M-1 the bracelet, M-2 a Mega spawned,
tagged and leashed from a function, M-3 the enrage, M-4 a ball refused, M-5 a face's ward holding in game, M-6 a Cutter trading as written (the offer format is the codec's; the
trade is not run), M-7 the client models; that the location advancements fire; that a villager keeps its trades.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import gulch_mine as GM  # noqa: E402
import gulch_sim as GS  # noqa: E402
import nbt_sim as N  # noqa: E402

SPEC = json.loads((ROOT / "data" / "gulch_mine.json").read_text(encoding="utf-8"))
BLACKOUT = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))
FLAG = "cobblers:flag/gym6_cleared"
GATE = SPEC["gate"]
NS, F = "cobblers", "gulch_mine"
EYE, REACH = 1.62, 4.5

# ---- SOUTHERN_RIFT_MEGA.md 7.3, by name (the Cutters' sixty) and 7.1 (which eleven are ZAMegas')
WILD_73 = ["Abomasite", "Absolite", "Absolite Z", "Aggronite", "Altarianite", "Ampharosite", "Audinite", "Banettite",
           "Barbaracite", "Beedrillite", "Cameruptite", "Chandelurite", "Charizardite X", "Charizardite Y", "Crabominite",
           "Dragoninite", "Drampanite", "Excadrite", "Feraligite", "Froslassite", "Glalitite", "Galladite", "Gardevoirite",
           "Garchompite", "Garchompite Z", "Gengarite", "Glimmoranite", "Golisopite", "Golurkite", "Gyaradosite",
           "Hawluchanite", "Heracronite", "Houndoominite", "Lopunnite", "Malamarite", "Medichamite", "Meowsticite",
           "Metagrossite", "Pidgeotite", "Pyroarite", "Raichunite X", "Raichunite Y", "Sablenite", "Scizorite",
           "Scraftinite", "Sharpedonite", "Skarmorite", "Staraptite", "Starminite", "Steelixite"]
STARTERS_73 = ["Venusaurite", "Blastoisinite", "Meganiumite", "Sceptilite", "Blazikenite", "Swampertite", "Chesnaughtite",
               "Delphoxite", "Greninjite", "Emboarite"]
LEFT_OUT_73 = ["Aerodactylite", "Alakazite", "Chimechite", "Clefablite", "Diancite", "Dragalgite", "Eelektrossite",
               "Falinksite", "Floettite", "Kangaskhanite", "Latiasite", "Latiosite", "Lucarionite", "Manectite", "Mawilite",
               "Mewtwonite X", "Mewtwonite Y", "Pinsirite", "Salamencite", "Scolipite", "Scovillainite", "Slowbronite",
               "Tyranitarite", "Victreebelite", "Baxcalibrite", "Darkranite", "Heatranite", "Lucarionite Z", "Magearnite",
               "Tatsugirinite", "Zeraorite", "Zygardite"]
ZAMEGAS_71 = {"Absolite Z", "Garchompite Z", "Golisopite", "Baxcalibrite", "Darkranite", "Heatranite", "Lucarionite Z",
              "Magearnite", "Tatsugirinite", "Zeraorite", "Zygardite"}


def stone_id(name):
    """A stone's item id from its name: lower case, ' X'/' Y' as _x/_y, ' Z' run on (Absolite Z: absolitez); the
    namespace is zamega for ZAMegas' eleven (7.1), mega_showdown for the rest. Checked against the jars below."""
    ns = "zamega" if name in ZAMEGAS_71 else "mega_showdown"
    base = name.lower()
    if base.endswith(" z"):
        base = base[:-2] + "z"
    return "%s:%s" % (ns, base.replace(" ", "_"))


def spec_model(spec=None, anchors=None):
    """A stand-in for GM.Model for the functions that read only the spec (the Megas' anchor y given here)."""
    spec = copy.deepcopy(spec or SPEC)
    for s in spec["megas"]["slots"]:
        s["_anchor"] = list(anchors[s["id"]]) if anchors else [s["anchor"][0], 47, s["anchor"][1]]
    return types.SimpleNamespace(spec=spec)


def zone_boxes():
    return GM.zone_boxes(SPEC["zone"]["polygon"])


def gate(spec=None):
    return GM.gate_files(spec_model(spec), zone_boxes())


def world(fns, **kw):
    w = GS.World({"%s/%s" % (F, k): v for k, v in fns.items()}, **kw)
    return w


def position(adv):
    (crit,) = adv["criteria"].values()
    assert crit["trigger"] == "minecraft:location", crit
    return crit["conditions"]["player"]


# ============================================================================================ the world model itself

# Without it every conclusion the drop roll's tests draw rests on a storage model nobody checked, and a model that
# quietly guesses hands back a PASS for a contract it never simulated. The gulch's roll is built on five NBT
# behaviours and on what vanilla ANSWERS, so each is pinned here on functions written for this test alone:
# `set value` and `append value`; a filtered element `dens[{id:"..."}]` found, created by a filtered set, and removed;
# `set from entity <sel> UUID`; `set from storage`; `execute if data storage` on a filtered path; a macro call taking
# its arguments from storage; and the two answers the roll's hitter comparison turns on -- a `set` that changes
# nothing succeeds 0, and a source path with no element fails and changes nothing. An entity may be named by its
# UUID's text, as `$execute as $(who)` does. A `data` form the gulch does not write raises NotModelled rather than
# being guessed at.
def test_the_gulch_model_follows_minecraft_nbt_storage_and_refuses_what_it_does_not_know():
    S = "t:s"
    w = GS.World({"t/a": [
        'data modify storage t:s dens set value []',
        'data modify storage t:s dens append value {id:"one"}',
        'data modify storage t:s dens[{id:"one"}].pid set from entity @s UUID',
        'data modify storage t:s me set from storage t:s dens[{id:"one"}].pid',
        'execute store success score #same t.x run data modify storage t:s me set from storage t:s dens[{id:"one"}].pid',
        'execute store success score #miss t.x run data modify storage t:s me set from storage t:s dens[{id:"two"}].pid',
        'execute store success score #there t.x if data storage t:s dens[{id:"one"}]',
        'execute store success score #absent t.x if data storage t:s dens[{id:"two"}]',
        'data modify storage t:s dens[{id:"two"}].pid set value "made"',
        'data remove storage t:s dens[{id:"one"}].pid',
    ], "t/macro": ['$data modify storage t:s out set value "$(id)-$(pid)"'],
        "t/call": ['function cobblers:t/macro with storage t:s dens[{id:"two"}]']})
    me = w.player((0.5, 64, 0.5))
    w.me = me
    w.call("t/a")
    # append then a filtered read; a filtered set that matches nothing appends the pattern it looked for (vanilla)
    assert [d["id"] for d in w.sget(S, "dens")[0]] == ["one", "two"], w.nbt
    assert w.sget(S, 'dens[{id:"two"}].pid') == ["made"]
    assert w.sget(S, 'dens[{id:"one"}].pid') == [], "data remove left the tag behind"
    # the hitter comparison: the same value succeeds 0, a source with no element fails and changes nothing
    assert (w.get("#same", "t.x"), w.get("#miss", "t.x")) == (0, 0)
    assert (w.get("#there", "t.x"), w.get("#absent", "t.x")) == (1, 0)
    assert w.sget(S, "me") == [me["nbt"]["UUID"]], "a failed set overwrote the target"
    w.me = None
    w.call("t/call")
    assert w.sget(S, "out") == ["two-made"], w.nbt          # macro arguments render a string as its own text
    # an entity may be named by its UUID's text, as the roll's `$execute as $(who)` does
    named = GS.World({"t/u": ["execute as %s run tag @s add hit" % GS.uuid_text(me["nbt"]["UUID"])]}, seed=11)
    other = named.player((9.5, 64, 9.5))
    named.entities.append(me)
    assert GS.uuid_text(other["nbt"]["UUID"]) != GS.uuid_text(me["nbt"]["UUID"])
    named.call("t/u")
    assert "hit" in me["tags"] and not other["tags"], (me["tags"], other["tags"])
    # and a form the gulch does not write is refused, not guessed
    with pytest.raises(GS.NotModelled):
        GS.World({"t/n": ["data modify storage t:s a prepend value 1"]}).call("t/n")


# ================================================================================================= the gate, both ways

FILES, FNS = gate()


def _as_player(fn, flags=(), mode="survival", at=(0.0, 0.0, 0.0), vehicle=False):
    w = world(FNS)
    p = w.player(at, flags=flags, mode=mode)
    if vehicle:
        p["vehicle"] = w.pokemon(at)
    w.me = p
    w.call("%s/%s" % (F, fn))
    return w, p


# Without it the gate lets through a player without the sixth badge, or keeps out one who has it (decision 3: "its own
# zone at 6 badges"), or the knock sends the player somewhere other than the data's arrival, facing down the road.
@pytest.mark.parametrize("has", [True, False], ids=["with gym6", "without"])
def test_the_knock_puts_only_a_gym6_holder_through_to_the_arrival(has):
    w, p = _as_player("gate/knock", flags=[FLAG] if has else [], at=(4364.5, 116, 4706.5))
    ax, ay, az, yaw = GATE["arrive"]
    if has:
        assert p["pos"] == (ax, ay, az) and p["yaw"] == yaw, p
    else:
        assert p["pos"] == (4364.5, 116, 4706.5), p
        assert any("sixth badge" in c for _e, c in w.titles), w.titles
    assert w.log[0] == "advancement revoke @s only %s:%s/gate_knock" % (NS, F), "the knock would fire only once"


# Without it the zone check turns back a player who holds the flag, lets one without it stay (over the rockfall, down a
# cliff, up the stem from Victory Road), turns back builders in creative, or leaves a mount inside while its rider is
# turned back. Anyone else is put at the turn-back point, the mount first.
@pytest.mark.parametrize("has,mode,back", [(False, "survival", True), (False, "adventure", True), (True, "survival", False),
                                           (True, "adventure", False), (False, "creative", False),
                                           (False, "spectator", False)])
def test_the_zone_turns_back_exactly_the_players_without_gym6(has, mode, back):
    start = (4300.5, 90, 4850.5)
    w, p = _as_player("gate/zone", flags=[FLAG] if has else [], mode=mode, at=start, vehicle=True)
    tx, ty, tz, yaw = GATE["turn_back"]
    assert (p["pos"] == (tx, ty, tz)) == back, p
    assert (p["vehicle"]["pos"] == (tx, ty, tz)) == back
    assert w.log[0] == "advancement revoke @s only %s:%s/zone" % (NS, F)


# Without it the way out from behind the gate is shut to someone (a flag holder who wants to leave, or a player who got
# in some other way and must be let out), or leads somewhere other than the front of the gate.
@pytest.mark.parametrize("has", [True, False])
def test_the_exit_lets_anyone_out_to_the_front_of_the_gate(has):
    _w, p = _as_player("gate/exit", flags=[FLAG] if has else [], at=(4353.5, 112, 4706.5))
    assert p["pos"] == tuple(GATE["turn_back"][:3]) and p["yaw"] == GATE["turn_back"][3]


# Without it the plug can be dug through by a player with the flag (who has the knock) or without it (who would be in
# the zone anyway): the data's ward is for "anyone in survival or adventure inside it" (gate.ward_why); builders in
# creative and spectators are left alone; the effect is Mining Fatigue IV and outlasts the one-second trigger.
@pytest.mark.parametrize("has", [True, False])
@pytest.mark.parametrize("mode", ["survival", "adventure", "creative", "spectator"])
def test_the_ward_fatigues_every_survival_and_adventure_player(has, mode):
    w, p = _as_player("gate/ward", flags=[FLAG] if has else [], mode=mode)
    eff = [c for e, c in w.effects if e is p]
    if mode in ("survival", "adventure"):
        (line,) = eff
        m = re.fullmatch(r"effect give @s minecraft:mining_fatigue (\d+) (\d+) true", line)
        assert m and int(m.group(2)) + 1 == 4 and int(m.group(1)) * 20 > 20, line
    else:
        assert eff == []


# Without it the gate waits on a flag nothing grants (a renamed flag, one the progression pack no longer writes, or
# only an impossible trigger sets), or the gulch opens on another badge than the sixth, whose leader gives the bracelet.
def test_the_gate_opens_on_the_sixth_badges_flag_the_progression_pack_grants():
    import progression_pack as PP
    assert SPEC["flag"] == dict(SPEC["flag"], advancement=FLAG, badge=6)
    named = set()
    for lines in FNS.values():
        for l in lines:
            named |= set(re.findall(r"advancements=\{([a-z0-9_]+:[a-z0-9_/]+)=", l))
    assert named == {FLAG}, named
    prog = PP.files(PP.plan(PP.load(ROOT / "data" / "progression.json"), None,
                            json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))))
    crit = json.loads(prog["data/cobblers/advancement/flag/gym6_cleared.json"])["criteria"]
    assert all(c["trigger"] != "minecraft:impossible" for c in crit.values()), crit


# ================================================================================================= the zone

def _inside_polygon(px, pz):
    """Even-odd, in this file's own words (data geometry.zone: a column is in when its centre is inside)."""
    poly, c = SPEC["zone"]["polygon"], False
    for (x0, z0), (x1, z1) in zip(poly, poly[1:] + poly[:1]):
        if (z0 > pz) != (z1 > pz) and px < x0 + (pz - z0) * (x1 - x0) / (z1 - z0):
            c = not c
    return c


def _zone_ranges():
    (cond,) = position(FILES["advancement/%s/zone.json" % F])
    assert cond["condition"] == "minecraft:any_of", cond
    return [t["predicate"]["location"]["position"] for t in cond["terms"]]


def _in_zone(ranges, p):
    return any(all(r[a]["min"] <= v <= r[a]["max"] for a, v in zip("xyz", p)) for r in ranges)


# Without it the zone check misses part of the gulch (a player without the badge walks round the gate into an uncovered
# column) or reaches outside it (a player is turned back where they are allowed to be). Every column whose centre is
# inside the data's polygon is inside a generated box, and no other column is; every box runs the full height.
def test_the_zone_boxes_cover_exactly_the_polygons_columns_full_height():
    ranges = _zone_ranges()
    ymin, ymax = SPEC["zone"]["y"]
    assert all((r["y"]["min"], r["y"]["max"]) == (ymin, ymax + 1) for r in ranges)
    xs = [p[0] for p in SPEC["zone"]["polygon"]]
    zs = [p[1] for p in SPEC["zone"]["polygon"]]
    rows = {}
    for r in ranges:
        for z in range(int(r["z"]["min"]), int(r["z"]["max"])):
            rows.setdefault(z, []).append((int(r["x"]["min"]), int(r["x"]["max"]) - 1))
    bad = []
    for z in range(int(min(zs)) - 2, int(max(zs)) + 3):
        for x in range(int(min(xs)) - 2, int(max(xs)) + 3):
            covered = any(a <= x <= b for a, b in rows.get(z, []))
            if covered != _inside_polygon(x + 0.5, z + 0.5):
                bad.append((x, z, covered))
    assert not bad, (len(bad), bad[:5])
    assert sum(b - a + 1 for v in rows.values() for a, b in v) > 70000


# Without it the gate loops: the knock alcove or the turn-back point inside the zone (a player without the badge is
# turned back onto the turn-back point, inside the zone, again), or the arrival and the exit box outside it. Tested at
# the feet, as the predicates test them, over each box's whole extent.
def test_the_knock_and_turn_back_are_outside_the_zone_and_the_arrival_and_exit_inside():
    ranges = _zone_ranges()

    def feet(box):
        x0, y0, z0, x1, y1, z1 = box
        return [(x, y0, z) for x in (x0, x0 + 0.5, x1 + 0.99) for z in (z0, z0 + 0.5, z1 + 0.99)]
    assert not [p for p in feet(GATE["knock"]) if _in_zone(ranges, p)]
    assert not _in_zone(ranges, GATE["turn_back"][:3])
    assert all(_in_zone(ranges, p) for p in feet(GATE["exit"]))
    assert _in_zone(ranges, GATE["arrive"][:3])
    # and the knock's own predicate is the data's box, feet anywhere in its blocks
    (k,) = position(FILES["advancement/%s/gate_knock.json" % F])
    x0, y0, z0, x1, y1, z1 = GATE["knock"]
    pos = k["predicate"]["location"]["position"]
    assert (pos["x"], pos["y"], pos["z"]) == ({"min": x0, "max": x1 + 1}, {"min": y0, "max": y1 + 1}, {"min": z0, "max": z1 + 1})


# ================================================================================================= the Cutters

def _cutters():
    fns = GM.cutter_files(spec_model())
    out = {}
    for l in fns["cutters_place"]:
        m = re.fullmatch(r"summon minecraft:villager (\S+) (\S+) (\S+) (\{.*\})", l)
        if m:
            nbt = N.parse_snbt(m.group(4))
            out[[t for t in nbt["Tags"] if t.startswith("cobblers_cutter_bench")][0]] = (tuple(float(v) for v in m.groups()[:3]), nbt)
    return fns, out


# Without it a Cutter asks for something else (a species item, one raw stone, no diamond), sells more than one stone,
# pays experience or levels (and so changes), locks after some uses (a NoAI villager never restocks), drifts in price
# with demand or reputation, or buys stones back (decision 5A: "raw mega stones + 1 diamond -> one keyed stone,
# unlimited uses ... Nothing is bought back"; the count is SOUTHERN_RIFT_MEGA.md 13's: "The keyed-stone recipe therefore
# takes 2 raw stones", 4 before the owner's redesign). Every offer, read as vanilla's MerchantOffer fields.
def test_every_cutter_offer_is_two_raw_and_a_diamond_for_one_stone_unlimited_without_xp():
    _fns, cut = _cutters()
    assert len(cut) == 3, sorted(cut)
    for bench, (_at, nbt) in cut.items():
        recipes = nbt["Offers"]["Recipes"]
        assert len(recipes) == 20, (bench, len(recipes))
        for r in recipes:
            assert r["buy"] == {"id": "mega_showdown:mega_stone", "count": 2}, r
            assert r["buyB"] == {"id": "minecraft:diamond", "count": 1}, r
            assert r["sell"]["count"] == 1 and r["sell"]["id"] != "mega_showdown:mega_stone", r
            assert r["maxUses"] == 2 ** 31 - 1 and r["uses"] == 0, r
            assert r["rewardExp"] == 0 and isinstance(r["rewardExp"], N.Byte) and r["xp"] == 0, r
            assert r["priceMultiplier"] == 0.0 and r["specialPrice"] == 0 and r["demand"] == 0, r
            assert set(r) == {"buy", "buyB", "sell", "uses", "maxUses", "rewardExp", "xp", "priceMultiplier",
                              "specialPrice", "demand"}, sorted(r)


# Without it the Cutters offer a stone for a Pokemon nobody can catch here, miss one whose Pokemon can be had, or offer
# one twice (decision 11: "the 60 whose Pokemon can be had here"): the stones offered, over the three benches, are
# section 7.3's sixty by name, and none of its thirty-two left out.
def test_the_stones_offered_are_section_7_3s_sixty_exactly():
    _fns, cut = _cutters()
    sold = [r["sell"]["id"] for _at, nbt in cut.values() for r in nbt["Offers"]["Recipes"]]
    assert len(WILD_73) == 50 and len(STARTERS_73) == 10 and len(LEFT_OUT_73) == 32
    want = {stone_id(n) for n in WILD_73 + STARTERS_73}
    assert len(sold) == len(set(sold)) == 60, len(sold)
    assert set(sold) == want, (sorted(set(sold) - want), sorted(want - set(sold)))
    assert not set(sold) & {stone_id(n) for n in LEFT_OUT_73}


# Without it a Cutter wanders, dies, despawns, trades as a novice (and levels, changing nothing but its title) or loses
# its trades, or a re-apply leaves two villagers at a bench: each is a NoAI, invulnerable, persistent master mason at
# its bench, and the placement keeps the new one and kills older ones at the same bench only.
def test_each_cutter_is_a_fixed_master_mason_at_its_bench_and_the_reapply_keeps_one():
    fns, cut = _cutters()
    benches = {b["id"]: b for b in SPEC["cutters"]["benches"]}
    for tag, (at, nbt) in cut.items():
        b = benches[tag[len("cobblers_cutter_"):]]
        assert at == (b["at"][0] + 0.5, b["at"][1], b["at"][2] + 0.5), (tag, at)
        assert nbt["NoAI"] == 1 and nbt["Invulnerable"] == 1 and nbt["PersistenceRequired"] == 1, tag
        assert nbt["VillagerData"] == {"profession": "minecraft:mason", "level": 5, "type": "minecraft:plains"}
        assert {"cobblers_cutter", "cobblers_cutter_new", tag} == set(nbt["Tags"])
        assert [r["sell"]["id"] for r in nbt["Offers"]["Recipes"]] == b["stones"]
    w = world({k: v for k, v in fns.items()})
    for tag, (at, _nbt) in cut.items():
        w.villager(at, tags={"cobblers_cutter", tag})          # the one an earlier re-apply left
        w.villager(at, tags={"cobblers_cutter", "cobblers_cutter_new", tag})
    stray = w.villager((4300.5, 88, 4850.5))                   # somebody's own villager in the square
    w.call("%s/cutters_done" % F)
    left = [e for e in w.entities if e is not stray]
    assert w.alive(stray) and len(left) == 3, w.entities
    assert sorted(t for e in left for t in e["tags"] if "bench" in t) == sorted(cut)
    assert all("cobblers_cutter_new" not in e["tags"] for e in left), left


# ================================================================================================= the faces

# SOUTHERN_RIFT_MEGA.md 13 (the owner's redesign, 2026-09-27): "The crystal faces are unmineable scenery. They keep
# their look; the ward holds them permanently and the restore cycle is retired." The prototype slice's restore tests
# (period, offset, restart, occupancy, variants, the chest filter) were retired with it; the ward test replaces them.
FACES = {f["id"]: f for f in SPEC["mine"]["faces"]}
CRYSTAL = SPEC["palette"]["mega_stone_crystal"]


def keeper(anchors=None):
    return GM.keeper_files(spec_model(anchors=anchors))


def _mine_world(fns=None, near=True, gt=10_000_000, seed=7):
    fns = fns or keeper()
    w = world(fns, seed=seed)
    w.gt = gt
    w.call("%s/load" % F)
    if near:
        w.player((4300.5, 89, 4850.5))                   # in the town square: inside the mine's approach box
    return w


# ---- the open-air Mega farms (data farms[]): a world inside one farm's approach box, used here, by
# tests/test_gate_clocks.py's farm clock scenarios and by contract C12
FARM_DENS = [(f["id"], d["id"]) for f in SPEC.get("farms", []) for d in f["dens"]]
STORE = "cobblers:gulch_mine"               # the dens' storage, as data/gulch_mine.json's drop roll uses it


def farm_spec(respawn=None):
    """The data, with every farm tier's respawn_ticks cut to `respawn` so a den's clock runs inside a test."""
    spec = copy.deepcopy(SPEC)
    if respawn:
        for tier in spec["farm_tiers"].values():
            if isinstance(tier, dict):
                tier["respawn_ticks"] = respawn
    return spec


def farm_keeper(respawn=None):
    """The keeper built on the data, with every farm tier's respawn_ticks cut to `respawn` (None: the data's own)."""
    return GM.keeper_files(spec_model(farm_spec(respawn)))


def farm_spots(spec, site, den_id):
    """Two standing places inside `site`'s approach box and clear of the den's anchor, so its Mega can still spawn."""
    farm = next(f for f in spec["farms"] if f["id"] == site)
    den = next(d for d in farm["dens"] if d["id"] == den_id)
    ax, ay, az = den["anchor"]
    x0, y0, z0, x1, y1, z1 = farm["approach"]
    clear = spec["megas"]["spawn_clear"]
    # east and south of the anchor, else west and north where the approach box (clipped to farms_grid, the field's own
    # extent) stops short of a den near the field's edge: the same distance out either way
    r = clear + 32
    ways = [(ax + r + 0.5, ay, az + 0.5), (ax + 0.5, ay, az + r + 0.5), (ax - r + 0.5, ay, az + 0.5),
            (ax + 0.5, ay, az - r + 0.5)]
    spots = [s for s in ways if x0 <= s[0] < x1 + 1 and z0 <= s[2] < z1 + 1][:2]
    assert len(spots) == 2, (site, "no two standing places inside the approach box", farm["approach"])
    for s in spots:
        assert x0 <= s[0] < x1 + 1 and y0 <= s[1] < y1 + 1 and z0 <= s[2] < z1 + 1, (site, s, farm["approach"])
        assert math.dist(s, (ax + 0.5, ay, az + 0.5)) > clear, (site, s)
    return den, spots


def _farm_world(site, den_id, fns=None, respawn=1200, gt=10_000_000, seed=7, players=2):
    """(spec, den, world, players): one farm den's Mega up and claimed, with `players` standing in its approach box."""
    spec = farm_spec(respawn)
    den, spots = farm_spots(spec, site, den_id)
    w = world(fns or GM.keeper_files(spec_model(spec)), seed=seed)
    w.gt = gt
    w.call("%s/load" % F)
    who = [w.player(s) for s in spots[:players]]
    _run(w, 4 * PASS + 5)
    return spec, den, w, who


def den_megas(w, den_id):
    """The Pokemon in `w` carrying den `den_id`'s tag. Every OTHER Pokemon in the world must carry exactly one other
    live den's tag (a neighbour whose approach box the players also stand in: the Mega field's ranges overlap), so a
    stray or a doubly-claimed Mega still fails here rather than being ignored."""
    tag = SPEC["megas"]["tag"]
    live = {"%s.%s" % (tag, d["id"]) for _s, d in GM.dens(SPEC)}
    mine = "%s.%s" % (tag, den_id)
    out, seen = [], {}
    for e in w.entities:
        if e["kind"] != "pokemon":
            continue
        own = {t for t in e["tags"] if t in live}
        assert len(own) == 1, ("a Mega carrying %d den tags" % len(own), e)
        # (test owner, 2026-10-04) and no den has two Megas up at once, neighbour or not: before the field's ranges
        # overlapped the world held one Mega and the caller's single unpack said so; with neighbours present only the
        # den under test was unpacked, so a keeper double-spawning a NEIGHBOUR would have passed
        (t,) = own
        assert t not in seen, ("two live Megas carry %s" % t, seen[t], e)
        seen[t] = e
        if mine in own:
            out.append(e)
    return out


def _run(w, ticks):
    """Tick, recording (game time, den) for every Mega spawn."""
    out = []
    for _ in range(ticks):
        w.calls.clear()
        w.tick()
        out += [(w.gt, c[0].split("/megas/spawn_")[1]) for c in w.calls
                if "/megas/spawn_" in c[0] and not c[0].endswith("/megas/spawn_at")]
    return out


PASS = SPEC["driver"]["every_ticks"]              # the keeper runs only on a driver pass
RESPAWN = SPEC["megas"]["respawn_ticks"]


# Without it a face can be mined after all (a survival or adventure player beside it with no Mining Fatigue), or the
# retired restore still rewrites it: every tick anyone in survival or adventure within ward_margin of a face's box
# gets Mining Fatigue IV (amplifier 3), creative and spectator are left alone, and no generated keeper function
# writes a block inside a face's box.
@pytest.mark.parametrize("fid", sorted(FACES))
@pytest.mark.parametrize("mode", ["survival", "adventure", "creative", "spectator"])
def test_a_face_is_warded_every_tick_for_good(fid, mode):
    f = FACES[fid]
    x0, y0, z0, x1, y1, z1 = f["box"]
    m = SPEC["faces"]["ward_margin"]
    fns = keeper()
    for at, inside in (((x0 - m + 0.5, y0, z0 + 0.5), True), ((x1 + 0.5, y0, z1 + m + 0.5), True),
                       ((x0 - m - 1.5, y0, z0 + 0.5), False)):
        w = world(fns)
        p = w.player(at, mode=mode)
        w.gt = 5
        w.call("%s/tick" % F)
        got = [c for e, c in w.effects if e is p]
        want = inside and mode in ("survival", "adventure")
        assert bool(got) == want, (fid, mode, at, got)
        if got:
            assert got[0].endswith("minecraft:mining_fatigue 3 3 true"), got
    for name, body in fns.items():
        for ln in body:
            mm = re.search(r"\b(?:fill|setblock) (-?\d+) (-?\d+) (-?\d+)", ln)
            if mm:
                c = tuple(int(v) for v in mm.groups())
                assert not (x0 <= c[0] <= x1 and y0 <= c[1] <= y1 and z0 <= c[2] <= z1), (name, ln)


# ================================================================================================= the Megas

SLOTS = {s["id"]: s for s in SPEC["megas"]["slots"]}
MTAG = SPEC["megas"]["tag"]


def _spawned(w, sid):
    return [e for e in w.entities if e["kind"] == "pokemon" and "%s.%s" % (MTAG, sid) in e["tags"]]


# Without it a Mega is catchable, comes out as the plain species, at another level, or without the tags the leash, the
# keeper and the blackout's exemption find it by (decision 9: data/blackout.json claims.exempt_tag is this tag), or
# despawns, or spawns through a plain spawnpokemonat line (parsed at server start, it spawns nothing until a /reload:
# EXP-046, .claude/rules/datapacks.md): on a fresh install the keeper spawns each once, through the macro spawn_at,
# uncatchable, in Mega form, tagged, persistent, at its anchor.
def test_each_mega_is_spawned_once_uncatchable_tagged_and_persistent_at_its_anchor():
    assert BLACKOUT["claims"]["exempt_tag"] == MTAG
    fns = keeper()
    assert [l for l in fns["megas/spawn_at"] if not l.startswith("#")] == \
        ["$spawnpokemonat $(x) $(y) $(z) $(species) $(aspect) uncatchable level=$(level)"]
    assert not [(n, l) for n, b in fns.items() for l in b if l.startswith("spawnpokemonat") or " run spawnpokemonat" in l]
    w = _mine_world(fns)
    _run(w, 500)
    for sid, s in SLOTS.items():
        assert "%s:%s/megas/spawn_at {" % (NS, F) in "\n".join(fns["megas/spawn_%s" % sid])
        got = _spawned(w, sid)
        assert len(got) == 1, (sid, got)
        (e,) = got
        assert e["props"] == [s["species"], s["aspect"], "uncatchable", "level=%d" % s["level"]], e["props"]
        assert e["tags"] == {MTAG, "%s.%s" % (MTAG, sid)}, e["tags"]
        # the mine's slots are not farm dens: they carry neither the farm tag nor its drop roll
        assert SPEC["megas"]["farm_tag"] not in e["tags"], e["tags"]
        assert e["nbt"].get("PersistenceRequired") == 1, e["nbt"]
        assert (e["pos"][0] - 0.5, e["pos"][2] - 0.5) == tuple(s["anchor"]), e["pos"]
    before = len(w.entities)
    _run(w, 1000)
    assert len(w.entities) == before, "a Mega was spawned again while its twin is alive"


# Without it a Mega wanders off through the halls (or out of the mine) and the Cutting Floor is empty, or the leash
# yanks it back while it is close: past its leash radius it is put back at its anchor, within it it is left alone.
@pytest.mark.parametrize("dist,back", [(10, False), (23.5, False), (30, True), (80, True)])
def test_the_leash_walks_a_mega_back_only_past_its_radius(dist, back):
    w = _mine_world()
    _run(w, 500)
    s = SLOTS["steelix"]
    (e,) = _spawned(w, "steelix")
    x, y, z = s["anchor"][0], e["pos"][1], s["anchor"][1]           # the leash's anchor block corner, at the Mega's y
    e["pos"] = (x + dist, y, z)
    _run(w, SPEC["megas"]["leash_every_ticks"] + 1)
    assert (e["pos"] == (float(x), float(y), float(z))) == back, e["pos"]


# Without it a gone Mega comes back at once (the farm's rate limit gone), never, beside a player (spawn_clear), or while
# nobody is near (SOUTHERN_RIFT_MEGA.md 13: "respawn in their dens on a timer"; the clock is the game time it was first
# seen gone, and it spawns respawn_ticks later): gone, it stays gone for respawn_ticks, then waits for nobody within
# spawn_clear of its anchor; with nobody in the approach box nothing runs but the tick, the drive and the leash.
def test_a_gone_mega_comes_back_respawn_ticks_after_it_was_first_seen_gone_when_nobody_is_near():
    w = _mine_world()
    _run(w, 500)
    for e in _spawned(w, "steelix"):
        w.entities.remove(e)
    t_gone = w.gt
    s = SLOTS["steelix"]
    watcher = w.player((s["anchor"][0] + 5.5, 47, s["anchor"][1] + 0.5))
    got = _run(w, RESPAWN - 3 * PASS)
    assert not _spawned(w, "steelix") and not got, "back before its respawn time"
    _run(w, 6 * PASS)
    assert not _spawned(w, "steelix"), "spawned beside a player"
    w.entities.remove(watcher)
    got = _run(w, 3 * PASS)
    assert [d for _t, d in got] == ["steelix"], got
    assert RESPAWN <= got[0][0] - t_gone <= RESPAWN + 12 * PASS, (got, t_gone)
    far = _mine_world(near=False)
    far.calls.clear()
    _run(far, 3 * PASS)
    assert not [c for c in far.calls if c[0] not in ("%s/tick" % F, "%s/drive" % F, "%s/leash" % F)], far.calls[-3:]


# Without it the respawn clock is a farm after all: a restart, or leaving the approach box and coming back, brings a gone
# Mega back early (contract C14: no action a player can repeat moves a clock a gate relies on). Load sets a den's clock
# only when it has never been set; only the keeper starts it and only a spawn or a Mega seen in the den clears it.
def test_neither_a_restart_nor_a_reapproach_brings_a_gone_mega_back_early():
    w = _mine_world()
    _run(w, 500)
    for e in _spawned(w, "excadrill"):
        w.entities.remove(e)
    visitor = w.entities[0]
    t_gone = w.gt
    got = _run(w, 3 * PASS)
    for _ in range(10):
        w.call("%s/load" % F)                                     # a restart: minecraft:load runs again
        w.entities.remove(visitor)
        got += _run(w, PASS)
        w.entities.append(visitor)
        got += _run(w, PASS)
    got += _run(w, RESPAWN - (w.gt - t_gone) - 3 * PASS)
    assert not [d for _t, d in got if d == "excadrill"], got
    got = _run(w, 8 * PASS)
    assert [d for _t, d in got] == ["excadrill"], got


# Without it two copies of a Mega roam at once (a spawn that raced a slow entity load): the keeper kills the extra.
def test_a_duplicate_mega_is_removed():
    w = _mine_world()
    _run(w, 500)
    (e,) = _spawned(w, "excadrill")
    twin = w.pokemon((e["pos"][0] + 3, e["pos"][1], e["pos"][2]), tags=set(e["tags"]))
    _run(w, 200)
    assert len(_spawned(w, "excadrill")) == 1


# ================================================================================================= meteorid ore

# Without it the gulch becomes an unplanned eighth evolution-stone site: a mega_meteorid_*_ore block drops Cobblemon
# evolution stones (SOUTHERN_RIFT_MEGA.md 4). No data file of the mega site or the spur names one to place, and no
# function the spec-only builders write places one (the block passes are checked on the built pack, slow, below).
def test_no_meteorid_ore_is_named_or_placed():
    ore = re.compile(r"mega_showdown:mega_meteorid_\w*_ore")
    for name in ("gulch_mine.json", "rift_mines.json"):
        doc = json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))

        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k not in ("never",):                      # the data's own warning names the ore to forbid it
                        walk(v, path + "." + k)
            elif isinstance(o, list):
                for v in o:
                    walk(v, path)
            elif isinstance(o, str):
                assert not ore.search(o), (name, path, o)
        walk(doc)
    text = json.dumps([gate()[1], GM.cutter_files(spec_model()), keeper()])
    assert not ore.search(text)


# ================================================================================================= the recipes

JAR_CANDIDATES = [os.environ.get("COBBLERS_JAR_DIR") or "",
                  r"C:\Users\wnd\AppData\Roaming\ModrinthApp\profiles\Fabric 1.21.10\mods"]


@pytest.fixture(scope="module")
def jar_dir():
    import mega_recipes as MR
    pins = MR.pins()
    for d in JAR_CANDIDATES:
        if d and all((Path(d) / name).is_file() for name, _sha in pins.values()):
            if all(hashlib.sha1((Path(d) / name).read_bytes()).hexdigest() == sha for name, sha in pins.values()):
                return Path(d)
    pytest.skip("NOT_EXECUTED: no folder with the pinned Mega Showdown and ZAMegas jars (set COBBLERS_JAR_DIR)")


def _jar_stones(d):
    import mega_recipes as MR
    out = {}
    for ns, (name, _sha) in MR.pins().items():
        with zipfile.ZipFile(d / name) as z:
            for n in z.namelist():
                m = re.fullmatch(r"data/(\w+)/mega_showdown/mega/(\w+)\.json", n)
                if m:
                    out["%s:%s" % (m.group(1), m.group(2))] = json.loads(z.read("data/%s/recipe/%s.json" % m.groups()),
                                                                         strict=False)
    return out


# Without it a Cutter sells an item that is not a Mega Stone on this stack (a typo, a stone renamed in a mod update),
# or section 7.3's names do not map onto the jars' stones one for one: the sixty offered and the thirty-two left out are
# every stone in the pinned jars, 92, each once.
def test_the_offered_and_left_out_stones_are_the_jars_ninety_two(jar_dir):
    stones = _jar_stones(jar_dir)
    assert len(stones) == 92, len(stones)
    named = [stone_id(n) for n in WILD_73 + STARTERS_73 + LEFT_OUT_73]
    assert sorted(named) == sorted(stones), (sorted(set(named) - set(stones)), sorted(set(stones) - set(named)))
    offered = {r for b in SPEC["cutters"]["benches"] for r in b["stones"]}
    assert offered <= set(stones)


# Without it crafting stays at one raw stone (decision 5A: "a crafted stone takes [the Cutters' count of] raw stones,
# the species item, iron and a diamond"; SOUTHERN_RIFT_MEGA.md 13: "The keyed-stone recipe therefore takes 2 raw
# stones"), a recipe loses its species item or its diamond on the way, or its result changes: every one of the 92
# recipes, written at the jar's own path, holds the raw stone twice and everything else exactly as the jar has it.
# And the generator writes nothing outside build/datapacks/cobblers_mega_recipes (the jar's content is not
# MIT-style: never committed), which git ignores.
def test_the_recipe_generator_raises_every_stone_to_two_raw_and_writes_only_under_build(jar_dir, monkeypatch):
    import mega_recipes as MR
    written = []
    real_write, real_mkdir, real_rmtree = Path.write_text, Path.mkdir, shutil.rmtree

    def write_text(self, *a, **k):
        written.append(Path(self).resolve())
        return real_write(self, *a, **k)

    def mkdir(self, *a, **k):
        written.append(Path(self).resolve())
        return real_mkdir(self, *a, **k)

    def rmtree(p, *a, **k):
        written.append(Path(p).resolve())
        return real_rmtree(p, *a, **k)
    monkeypatch.setattr(Path, "write_text", write_text)
    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(shutil, "rmtree", rmtree)
    assert MR.main(["--jar-dir", str(jar_dir)]) == 0
    monkeypatch.undo()
    out = (ROOT / "build" / "datapacks" / "cobblers_mega_recipes").resolve()
    assert written and all(p == out or out in p.parents for p in written), [p for p in written if out not in p.parents][:3]
    ignored = subprocess.run(["git", "check-ignore", "-q", str(out / "pack.mcmeta")], cwd=ROOT).returncode
    assert ignored == 0, "the recipe pack is not gitignored"
    stones = _jar_stones(jar_dir)
    files = sorted(p for p in out.rglob("*.json"))
    assert len(files) == 92
    for sid, jar in stones.items():
        ns, stone = sid.split(":")
        got = json.loads((out / "data" / ns / "recipe" / (stone + ".json")).read_text(encoding="utf-8"))

        def counts(r):
            out_ = {}
            for row in r["pattern"]:
                for ch in row:
                    if ch != " ":
                        v = r["key"][ch]
                        out_[v.get("item") or v.get("tag")] = out_.get(v.get("item") or v.get("tag"), 0) + 1
            return out_
        want = counts(jar)
        assert want.get("mega_showdown:mega_stone") == 1, (sid, want)
        want["mega_showdown:mega_stone"] = 2
        assert counts(got) == want, (sid, counts(got), want)
        assert got["result"] == jar["result"] and got["type"] == jar["type"] == "minecraft:crafting_shaped", sid
        assert len(got["pattern"]) == 3 and all(len(r) == 3 for r in got["pattern"]), sid


# Without it the recipes are generated from some other jar than the one the server runs (a stone missing, a recipe
# shaped differently) and nobody notices: a jar whose SHA-1 is not the overlay's pin is refused and nothing is written.
def test_the_recipe_generator_refuses_an_unpinned_jar(tmp_path):
    import mega_recipes as MR
    for name, _sha in MR.pins().values():
        with zipfile.ZipFile(tmp_path / name, "w") as z:
            z.writestr("data/x/y.json", "{}")
    with pytest.raises(SystemExit) as e:
        MR.main(["--jar-dir", str(tmp_path)])
    assert "nothing written" in str(e.value)


# ================================================================================================= step R9S

# Without it a re-apply builds the gulch in the wrong order (its faces before the halls they stand in, the Cutters
# before the workshop), before the Rift skin it paves over, after the lights, or not at all; or the Cutters' step does
# not wait out their placement (summoned 40 ticks after the force-load, de-duplicated 100 ticks later); or the pack is
# installed where every world loads it (it drives itself), or the staging-only refill is run. Decision 12 names R9S.
def test_reapply_runs_r9s_after_r9m_and_the_cutters_wait_out_their_placement(monkeypatch):
    import reapply
    # cobblers_rift_zones' index is checked name by name against data/rift_zones.json (reapply.rift_zone_steps, since
    # 21d938f), so the placeholder "x" every other pack gets is refused there; an empty index runs no zone function
    listed = {"cobblers_gulch_mine": ["1earth_68_73", "2shell_68_73", "6faces_69_75"], "cobblers_rift_mines": ["1shell_48_48"],
              "cobblers_rift_zones": []}
    monkeypatch.setattr(reapply, "indexed", lambda pack, folder: listed.get(pack, ["x"]))
    steps = reapply.steps()
    ids = [s[0] for s in steps]
    assert ids.index("R1") < ids.index("R9M") < ids.index("R9S") < ids.index("R9E") < ids.index("R16"), ids
    acts = next(s for s in steps if s[0] == "R9S")[2]
    assert acts[:-2] == [("fn", "cobblers:gulch_mine/%s" % f) for f in listed["cobblers_gulch_mine"]]
    assert acts[-2] == ("fn", "cobblers:gulch_mine/cutters") and acts[-1][0] == "wait"
    fns = GM.cutter_files(spec_model())
    delay = sum(int(m) for l in fns["cutters"] + fns["cutters_place"] for m in re.findall(r"schedule function \S+ (\d+)t", l))
    assert acts[-1][1] * 20 >= delay, (acts[-1], delay)
    for pack in ("cobblers_gulch_mine", "cobblers_mega_recipes"):
        assert pack in reapply.SERVER_PACKS and pack in reapply.WORLD_LOCAL and pack not in reapply.EXCLUDED
    assert not [a for s in steps for a in s[2] if a[0] == "fn" and "refill" in a[1]]


# ================================================================================================= with the heightmap

def _root():
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT is not set: the heightmap is outside the repo")
    if not GM.SCULPT_PLAN.is_file():
        pytest.skip("no derived/rift_sculpt/plan.json (tools/rift_heightmap.py's plan): the gate's band is checked on it")
    return root


CMD = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = _root()
    assert GM.main(["build", "--source-root", root]) == 0
    pack = tmp_path_factory.mktemp("gulch") / "cobblers_gulch_mine"
    shutil.copytree(GM.OUT, pack)
    fdir = pack / "data" / "cobblers" / "function" / "gulch_mine"
    names = [n for n in (fdir / "index.txt").read_text(encoding="utf-8").split("\n") if n.strip()]
    w = []
    for n in names:
        for ln in (fdir / (n + ".mcfunction")).read_text(encoding="utf-8").splitlines():
            m = CMD.match(ln.strip())
            if not m:
                continue
            a = [int(v) for v in m.groups()[1:4]]
            b = [int(v) for v in m.groups()[4:7]] if m.group(5) else a
            for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                    for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1):
                        w.append((x, y, z, m.group(8)))
    fin = {}
    for x, y, z, b in w:
        fin[(x, y, z)] = b
    import ground as G
    return pack, w, fin, G.Ground(root), root


# Without it the build decides spawns, floods itself, lights itself with invisible light, or drops evolution stones
# from a meteorid ore: no block in any write (not only the last) is any of these.
@pytest.mark.slow
def test_no_written_block_is_a_spawn_condition_fluid_light_or_meteorid_ore(built):
    _pack, w, _fin, _g, _root_ = built
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    used = {b.split("[")[0] for _x, _y, _z, b in w}
    assert len(used) > 20
    assert not used & spawn, sorted(used & spawn)
    assert not used & {"minecraft:water", "minecraft:lava", "minecraft:flowing_water", "minecraft:flowing_lava",
                       "minecraft:light"}
    assert not [b for b in used if re.fullmatch(r"mega_showdown:mega_meteorid_\w*_ore", b)]


# Without it the gulch's build spills past its grid or out of its zone (where the zone check does not guard it, onto
# Victory Road's side): every write is in the grid, and every written column is in the zone (by the polygon's own
# words) or in the data's outside_ok box (the rockfall, the plug's face, the grille, the road above the gate, its lamps).
@pytest.mark.slow
def test_every_write_is_in_the_grid_and_the_zone_or_the_gates_outside_box(built):
    _pack, w, _fin, _g, _r = built
    gx, gz, gy = SPEC["grid"]["x"], SPEC["grid"]["z"], SPEC["grid"]["y"]
    assert not [(x, y, z) for x, y, z, _b in w if not (gx[0] <= x <= gx[1] and gz[0] <= z <= gz[1] and gy[0] <= y <= gy[1])]
    ok = GATE["outside_ok"]
    cols = {(x, z) for x, _y, z, _b in w}
    out = sorted(c for c in cols if not _inside_polygon(c[0] + 0.5, c[1] + 0.5)
                 and not (ok[0] <= c[0] <= ok[2] and ok[1] <= c[1] <= ok[3]))
    assert not out, (len(out), out[:5])


def _band_columns():
    """data geometry.band, in this file's words: each point [j, x, z, nx, nz] claims the columns within 1 (Chebyshev) of
    (floor(x + nx d + 0.5), floor(z + nz d + 0.5)) for d = -1, 0, 1; the first point in the list keeps a column."""
    out = {}
    for j, x, z, nx, nz in GATE["band"]["points"]:
        for d in (-1, 0, 1):
            cx, cz = int(math.floor(x + nx * d + 0.5)), int(math.floor(z + nz * d + 0.5))
            for a, b in itertools.product((-1, 0, 1), repeat=2):
                out.setdefault((cx + a, cz + b), j)
    return out


# Without it the plug or the grille can be dug by a player standing just outside the ward (the owner: "i can mine
# around the door"; the reach finding that set margin 7 at the spur's gate): the plug is every rockfall block the build
# writes in the plug's columns (|j| <= half_j, trimmed by the grille), the grille the data's iron bars; from every feet
# position just outside the generated ward, none is within 4.5 of the eyes.
@pytest.mark.slow
def test_no_player_outside_the_ward_can_reach_the_plug_or_the_grille(built):
    _pack, _w, fin, _g, _r = built
    pl, gr = GATE["plug"], GATE["grille"]
    cols = {c for c, j in _band_columns().items() if abs(j) <= pl["half_j"]
            and not (c[0] > pl["max_x"] and pl["trim_z"][0] <= c[1] <= pl["trim_z"][1])}
    rubble = set(SPEC["palette"]["rubble"])
    plug = {(x, y, z) for (x, y, z), b in fin.items() if (x, z) in cols and b.split("[")[0] in rubble and y <= pl["top_y"]}
    grille = {(gr["x"], y, z) for y in range(gr["y"][0], gr["y"][1] + 1) for z in range(gr["z"][0], gr["z"][1] + 1)}
    assert len(plug) > 100 and all(fin.get(c) == "minecraft:iron_bars" for c in grille), (len(plug),)
    (cond,) = position(FILES["advancement/%s/gate_ward.json" % F])
    pos = cond["predicate"]["location"]["position"]
    reached = _reach(pos, plug | grille)
    assert not reached, (len(reached), sorted(reached)[:3])
    # and the check is not blind: the spur gate's first margin (4) is reachable here too
    spec = copy.deepcopy(SPEC)
    spec["gate"]["ward"] = [v + (-3 if i >= 3 else 3) for i, v in enumerate(GATE["ward"])]   # margin 7 -> 4
    (small,) = position(gate(spec)[0]["advancement/%s/gate_ward.json" % F])
    assert _reach(small["predicate"]["location"]["position"], plug | grille)


def _reach(pos, blocks):
    """Every feet position just outside the ward whose eyes reach a block (tests/reach.py, shared with contract C6;
    identical to the loop it replaced on the real ward and on margin 4, 75 s -> 2 s)."""
    from reach import reach_from_outside
    return [p for _d, p in reach_from_outside(pos, blocks, EYE, REACH)]


def _hall_feet(h, x, z):
    """data geometry.hall at one column: (feet, top) or None. The phases' hash is tools/rift_mines.py's h32, as the data
    says; everything else is the data's formula."""
    import rift_mines as RM
    cx, cz = h["centre"]
    key = sum(ord(c) for c in h["id"])
    ph = [RM.h32(SPEC["seed"], len(h["id"]), key, k) / 2 ** 32 * 2 * math.pi for k in range(3)]
    dx, dz = x - cx, z - cz
    d, th = math.hypot(dx, dz), math.atan2(dz, dx)
    n = 0.5 * math.sin(3 * th + ph[0]) + 0.3 * math.sin(5 * th + ph[1]) + 0.2 * math.sin(7 * th + ph[2])
    rt = h["radius"] * (1 + h["ragged"] * n) + 0.5
    if d > rt:
        return None
    q = d / rt
    feet = h["feet"] + int(math.floor(h["bowl"] * q * q + 0.5))
    return feet, max(feet + 3, h["feet"] + int(math.floor(h["height"] * math.sqrt(max(0.0, 1 - q * q)) + 0.5)))


# Without it a Mega spawns inside rock, in the air over the bowl, without room for its size (Mega Steelix is tall), or
# outside its hall: each slot's anchor is its hall's floor at that column (the hall's own formula), the built pack leaves
# air from the feet up head_room blocks and a solid block under, and the keeper spawns and leashes it there.
@pytest.mark.slow
def test_each_megas_anchor_is_a_floor_cell_with_its_head_room_in_its_hall(built):
    _pack, _w, fin, _g, root = built
    m, _near, _tops = GM.model(root)
    halls = {h["id"]: h for h in SPEC["mine"]["halls"]}
    fns = GM.keeper_files(m)
    for s in m.spec["megas"]["slots"]:
        x, y, z = s["_anchor"]
        hf = _hall_feet(halls[s["hall"]], x, z)
        assert hf is not None and hf[0] == y, (s["id"], hf, y)
        assert all(fin.get((x, yy, z)) == "minecraft:air" for yy in range(y, y + s["head_room"])), s["id"]
        under = fin.get((x, y - 1, z))
        assert under is not None and under != "minecraft:air", (s["id"], under)
        assert "megas/spawn_at {x:%d,y:%d,z:%d,species:\"%s\"," % (x, y, z, s["species"]) in "\n".join(fns["megas/spawn_%s" % s["id"]])
