"""The southern Rift's mega site, prototype slice: tools/gulch_mine.py's pack, tools/mega_recipes.py and step R9S.

Written by the test author, not by the session that built the slice (9339ec2..2f1ed19), whose offline audit is
tools/gulch_mine_audit.py. The gate, Cutter, keeper and face functions read only the spec, so most of this runs
without the heightmap, on tests/gulch_sim.py's world model (executors, selectors, blocks, game time).

Independent sources:
  - docs/world-building/SOUTHERN_RIFT_MEGA.md: 7.1 (the jars' stones; ZAMegas' eleven), 7.3 (the sixty stones the
    Cutters offer and the thirty-two left out, by name), 7.2 and decision 5A (4 raw + 1 diamond, unlimited, nothing
    bought back; crafting kept at 4 raw), 7.6 (faces restored on approach, filtered, both corners loaded, nobody and
    no Pokemon in the box, faces in a hall offset by 15 minutes), 6.2 (the Megas uncatchable, tagged, leashed, back
    with the material), decisions 3 (the gulch at six badges), 9 (no claim for a Mega) and 12 (step R9S);
  - data/gulch_mine.json: the flag, the gate's boxes and points, the zone polygon (tested here by its own words: a
    column is in when its centre is inside, even-odd), the offer, the benches, the faces, the Megas, the period;
  - the pinned jars (read with zipfile, skipped without them): Mega Showdown 1.0.2 and ZAMegas 1.7.7, their mega
    definitions and recipes;
  - vanilla 1.21.1: the villager's MerchantOffer codec fields; a location predicate tests the feet; an effect's level
    is its amplifier + 1; a player's eyes are 1.62 above the feet and block reach is 4.5.

With the heightmap (slow, skipped without COBBLERS_SOURCE_ROOT): the built pack writes no meteorid ore, spawn
condition, fluid or light block; every write is inside the grid and the zone but the rockfall, road and lamps the data
allows outside; the ward keeps the plug and the grille out of reach; each Mega's anchor is a floor cell with its head
room, in its hall.

Not covered, and it needs a running server (SOUTHERN_RIFT_MEGA.md section 10): M-1 the bracelet, M-2 a Mega spawned,
tagged and leashed from a function, M-3 the enrage, M-4 a ball refused, M-5 a face restored in game (`fill ... replace
#tag`, P-3) and mined with a diamond pickaxe, M-6 a Cutter trading as written (the offer format is the codec's; the
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
# with demand or reputation, or buys stones back (decision 5A: "4 raw mega stones + 1 diamond -> one keyed stone,
# unlimited uses ... Nothing is bought back"). Every offer, read as vanilla's MerchantOffer fields.
def test_every_cutter_offer_is_four_raw_and_a_diamond_for_one_stone_unlimited_without_xp():
    _fns, cut = _cutters()
    assert len(cut) == 3, sorted(cut)
    for bench, (_at, nbt) in cut.items():
        recipes = nbt["Offers"]["Recipes"]
        assert len(recipes) == 20, (bench, len(recipes))
        for r in recipes:
            assert r["buy"] == {"id": "mega_showdown:mega_stone", "count": 4}, r
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

TAG = "#%s:%s" % (NS, SPEC["faces"]["resettable_tag"])
FACES = {f["id"]: f for f in SPEC["mine"]["faces"]}
METEORID = {SPEC["palette"]["meteorid"], SPEC["palette"]["meteorid_radiated"]}
CRYSTAL = SPEC["palette"]["mega_stone_crystal"]


def keeper(anchors=None):
    return GM.keeper_files(spec_model(anchors=anchors))


def _mine_world(fns=None, near=True, gt=10_000_000, seed=7):
    fns = fns or keeper()
    w = world(fns, tags={TAG: set(SPEC["faces"]["resettable"])}, seed=seed)
    w.gt = gt
    w.call("%s/load" % F)
    if near:
        w.player((4300.5, 89, 4850.5))                   # in the town square: inside the approach box
    return w



def _run(w, ticks):
    """Tick, recording (game time, face) for every restore."""
    out = []
    for _ in range(ticks):
        w.calls.clear()
        w.tick()
        out += [(w.gt, c[0].split("restore_")[1]) for c in w.calls if "/faces/restore_" in c[0]]
    return out


PERIOD = SPEC["faces"]["period_ticks"]


# Without it a face restores more often than decision 6's 30 minutes (a farm), never, or while nobody is near (STONE_
# ECONOMY.md 5.3: a fixed timer fails silently on unloaded chunks): with a player in the approach box for three periods,
# each face restores at the first pass and then exactly once per period; with nobody near, nothing runs at all.
def test_a_face_restores_once_per_period_and_only_on_approach():
    w = _mine_world()
    got = _run(w, 3 * PERIOD + 200)
    for fid in FACES:
        times = [t for t, f in got if f == fid]
        assert len(times) == 4, (fid, times)
        gaps = [b - a for a, b in zip(times, times[1:])]
        assert all(g >= PERIOD for g in gaps) and all(g <= PERIOD + 100 for g in gaps), (fid, gaps)
    far = _mine_world(near=False)
    far.calls.clear()
    assert _run(far, 2 * PERIOD) == []
    assert not [c for c in far.calls if c[0] not in ("%s/tick" % F, "%s/drive" % F, "%s/leash" % F)], far.calls[-3:]


# Without it a restart repeats a restore (the scores reset at load) or loses one: load leaves a restore time it finds.
def test_a_restart_neither_repeats_nor_loses_a_restore():
    w = _mine_world()
    first = _run(w, 200)
    assert {f for _t, f in first} == set(FACES)
    w.call("%s/load" % F)                                  # a restart: minecraft:load runs again
    again = _run(w, PERIOD - 300)
    assert again == [], again


# Without it a face is rewritten with a player or a Pokemon standing in it (a player buried in meteorid), or its fill
# runs into an unloaded chunk and fails silently: a player or a Pokemon in the box or one block round it, or either
# corner unloaded, holds the restore back; it runs at the first pass after they leave.
@pytest.mark.parametrize("what", ["a player in the box", "a player one block outside", "a Pokemon in the box",
                                  "the far corner unloaded", "the near corner unloaded"])
def test_a_face_does_not_restore_while_occupied_or_unloaded(what):
    f = FACES["face_a"]
    x0, y0, z0, x1, y1, z1 = f["box"]
    w = _mine_world()
    if what == "a player in the box":
        e = w.player((x0 + 3.5, y0, z0 + 3.5))
    elif what == "a player one block outside":
        e = w.player((x1 + 1.5, y0, z0 + 3.5))
    elif what == "a Pokemon in the box":
        e = w.pokemon((x0 + 1.5, y0, z0 + 1.5))
    else:
        far = what == "the far corner unloaded"
        w.loaded = lambda x, y, z: not ((x, y, z) == ((x1 + 1, y1 + 1, z1 + 1) if far else (x0 - 1, y0 - 1, z0 - 1)))
        e = None
    got = _run(w, 400)
    assert not [t for t, fid in got if fid == "face_a"], got
    assert [t for t, fid in got if fid == "face_b"], "the other face, free, must still restore"
    if e is not None:
        w.entities = [x for x in w.entities if x is not e]
    else:
        w.loaded = lambda x, y, z: True
    assert [t for t, fid in _run(w, 200) if fid == "face_a"]


def _variant(fns, fid, k):
    return [l for l in fns["faces/%s_v%d" % (fid, k)] if not l.startswith("#")]


# Without it a restore overwrites what a player left in the box (STONE_ECONOMY.md 5.4: a chest survives with its
# contents), writes the wrong number of crystals, hides every one (a face nobody can start), or buries none: every
# variant is one fill filtered to the tag and setblocks each guarded by it; three crystals, one on the front plane's
# bottom row facing out, two at least two deep (data faces.crystal_rule); the tag is the data's list, with no container.
@pytest.mark.parametrize("fid", sorted(FACES))
def test_every_variant_is_a_filtered_fill_with_three_crystals_one_showing(fid):
    fns = keeper()
    f = FACES[fid]
    x0, y0, z0, x1, y1, z1 = f["box"]
    front = f["front"]

    def depth(c):
        return {"west": c[0] - x0, "east": x1 - c[0], "north": c[2] - z0, "south": z1 - c[2]}[front]
    shown = set()
    for k in range(SPEC["faces"]["variants"]):
        body = _variant(fns, fid, k)
        assert body[0] == "fill %d %d %d %d %d %d %s replace %s" % (x0, y0, z0, x1, y1, z1, SPEC["palette"]["meteorid"], TAG)
        crys = []
        for l in body[1:]:
            m = re.fullmatch(r"execute if block (-?\d+) (-?\d+) (-?\d+) (\S+) run setblock (-?\d+) (-?\d+) (-?\d+) (\S+)", l)
            assert m and m.group(4) == TAG and m.groups()[:3] == m.groups()[4:7], l
            c = tuple(int(v) for v in m.groups()[:3])
            assert x0 <= c[0] <= x1 and y0 <= c[1] <= y1 and z0 <= c[2] <= z1, l
            if m.group(8).startswith(CRYSTAL):
                crys.append((c, m.group(8)))
            else:
                assert m.group(8) in METEORID, l
        assert len(crys) == f["crystals"] == 3, (k, crys)
        showing = [c for c, b in crys if depth(c) == 0]
        (s,) = showing
        assert s[1] == y0 and "facing=%s" % front in dict(crys)[s], crys
        assert all(depth(c) >= 2 for c, _b in crys if c != s), crys
        shown.add(s)
    assert len(shown) > 1, "every variant shows its crystal in the same place"
    tagfile = [v for v in SPEC["faces"]["resettable"]]
    assert not [b for b in tagfile if any(k in b for k in ("chest", "barrel", "shulker", "hopper", "furnace"))]


# Without it the filter does not spare a player's chest after all (the fill's replace or a crystal's guard missing in
# what runs): a chest left on a crystal's cell stays a chest through a restore, and the rest of the box is fresh.
def test_a_restore_spares_a_players_chest_in_the_box():
    fns = keeper()
    w = _mine_world(fns)
    f = FACES["face_a"]
    x0, y0, z0, x1, y1, z1 = f["box"]
    cells = [(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)]
    for c in cells:
        w.blocks[c] = "minecraft:cobblestone"             # dug out and back-filled with cobble
    chests = set()
    for k in range(SPEC["faces"]["variants"]):
        for l in _variant(fns, "face_a", k)[1:]:
            if CRYSTAL in l:
                chests.add(tuple(int(v) for v in l.split()[3:6]))
    for c in chests:
        w.blocks[c] = "minecraft:chest[facing=north]"
    _run(w, 200)
    assert all(w.blocks[c] == "minecraft:chest[facing=north]" for c in chests)
    assert all(w.blocks[c].split("[")[0] in METEORID | {CRYSTAL} for c in cells if c not in chests)


# Without it the variant repeats (a face that comes back the same every time is learnt by heart), or runs no variant at
# all when the random value lands on the last one used.
def test_a_restore_never_repeats_the_last_variant():
    for seed in range(6):
        w = _mine_world(seed=seed)
        seq = []
        for _ in range(12):
            w.calls.clear()
            w.gt += PERIOD
            w.call("%s/drive" % F)
            vs = [int(c[0][-1]) for c in w.calls if re.fullmatch(r"%s/faces/face_a_v\d" % F, c[0])]
            assert len(vs) == 1, w.calls
            seq.append(vs[0])
        assert all(a != b for a, b in zip(seq, seq[1:])), (seed, seq)


# Without it the two faces of a hall come back together, not 15 minutes apart (SOUTHERN_RIFT_MEGA.md 7.6: "faces in a
# hall offset by 15"; data face_b offset_ticks 18000). The offset is taken from game time 0 (load sets face_b's last
# restore to -18000), and a restore happens only when a player is near: on any world older than 30 minutes of game time
# when the pack is installed (the staging world), and after any absence longer than a period, both faces are overdue at
# the same pass and restore together from then on. Found by this suite.
@pytest.mark.xfail(strict=True, reason="the faces' offset is from game time 0, not kept: on a world past 36000 ticks, or "
                                       "after an absence of a period, face_a and face_b restore at the same pass")
def test_the_faces_of_a_hall_restore_offset_by_their_offset_ticks():
    w = _mine_world(gt=10_000_000)
    got = _run(w, 2 * PERIOD + 200)
    a = [t for t, f in got if f == "face_a"]
    b = [t for t, f in got if f == "face_b"]
    off = FACES["face_b"]["offset_ticks"] - FACES["face_a"]["offset_ticks"]
    assert all(abs(((tb - ta) % PERIOD) - off) <= 100 for ta, tb in zip(a, b)), (a, b)


# ================================================================================================= the Megas

SLOTS = {s["id"]: s for s in SPEC["megas"]["slots"]}
MTAG = SPEC["megas"]["tag"]


def _spawned(w, sid):
    return [e for e in w.entities if e["kind"] == "pokemon" and "%s.%s" % (MTAG, sid) in e["tags"]]


# Without it a Mega is catchable, comes out as the plain species, at another level, or without the tags the leash, the
# keeper and the blackout's exemption find it by (decision 9: data/blackout.json claims.exempt_tag is this tag), or
# despawns: after a face restores with the Megas gone, the keeper spawns each once, uncatchable, in Mega form, tagged,
# persistent, at its anchor.
def test_each_mega_is_spawned_once_uncatchable_tagged_and_persistent_at_its_anchor():
    assert BLACKOUT["claims"]["exempt_tag"] == MTAG
    w = _mine_world()
    _run(w, 500)
    for sid, s in SLOTS.items():
        got = _spawned(w, sid)
        assert len(got) == 1, (sid, got)
        (e,) = got
        assert e["props"] == [s["species"], s["aspect"], "uncatchable", "level=%d" % s["level"]], e["props"]
        assert e["tags"] == {MTAG, "%s.%s" % (MTAG, sid)}, e["tags"]
        assert e.get("nbt") == ["{PersistenceRequired:1b}"], e
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


# Without it a Mega pops into being beside a player (spawn_clear), or never comes back after it fainted (6.2: "they come
# back with the material"): a Mega gone when its hall's face restores is owed, and spawned once nobody is within
# spawn_clear of its anchor.
def test_a_fainted_mega_comes_back_with_the_next_restore_when_nobody_is_near_its_anchor():
    w = _mine_world()
    _run(w, 500)
    for e in _spawned(w, "steelix"):
        w.entities.remove(e)
    s = SLOTS["steelix"]
    watcher = w.player((s["anchor"][0] + 5.5, 47, s["anchor"][1] + 0.5))
    _run(w, 1000)
    assert not _spawned(w, "steelix"), "back before the face restored"
    _run(w, PERIOD)
    assert not _spawned(w, "steelix"), "spawned beside a player"
    w.entities.remove(watcher)
    _run(w, 400)
    assert len(_spawned(w, "steelix")) == 1


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


# Without it crafting stays at one raw stone (decision 5A: "a crafted stone takes 4 raw stones, the species item, iron
# and a diamond"), a recipe loses its species item or its diamond on the way, or its result changes: every one of the
# 92 recipes, written at the jar's own path, holds the raw stone 4 times and everything else exactly as the jar has it.
# And the generator writes nothing outside build/datapacks/cobblers_mega_recipes (the jar's content is not
# MIT-style: never committed), which git ignores.
def test_the_recipe_generator_raises_every_stone_to_four_raw_and_writes_only_under_build(jar_dir, monkeypatch):
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
        want["mega_showdown:mega_stone"] = 4
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
    listed = {"cobblers_gulch_mine": ["1earth_68_73", "2shell_68_73", "6faces_69_75"], "cobblers_rift_mines": ["1shell_48_48"]}
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
    def dist(eye, b):
        return math.sqrt(sum(max(b[i] - eye[i], 0.0, eye[i] - (b[i] + 1)) ** 2 for i in range(3)))
    lattice = {a: [pos[a]["min"] + k for k in range(int(pos[a]["max"] - pos[a]["min"]) + 1)] for a in "xyz"}
    near = sorted(blocks)
    out = []
    for a in "xyz":
        for o in (pos[a]["min"] - 1e-3, pos[a]["max"] + 1e-3):
            for p in itertools.product(*[lattice[b] if b != a else [o] for b in "xyz"]):
                eye = (p[0], p[1] + EYE, p[2])
                if min(dist(eye, b) for b in near) <= REACH:
                    out.append(p)
    return out


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
        assert "spawnpokemonat %d %d %d %s" % (x, y, z, s["species"]) in "\n".join(fns["megas/spawn_%s" % s["id"]])
