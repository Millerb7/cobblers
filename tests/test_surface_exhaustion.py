"""Swim fatigue: the cobblers_blackout pack's surface/* functions, under the owner's rule of 2026-09-27 (2262aa3).

Written by the test author, not by the session that wrote the pack (commits 476c4e5..5bcecec, 2a70841, 2262aa3). The
collapse hits run on their own clock, bo.fpt, since 5bcecec (EXP-044 README): the first as collapse is reached, then one
every pulse_ticks of time, whatever the water or partner.

Independent sources: data/blackout.json "surface" (the "rule", "deep_water_blocks_basis" and "feel" strings, and every
number); the owner's rule as the coordinator relayed it: "i want fatigue on every swim, maybe it would increase once you
pass three blocks deep, but a new player should struggle with water", made precise as: a player in survival or
adventure, feet or eyes in water, riding nothing and not wading (eyes out of water, bo.sub 0, and on the ground) builds
fatigue every sample_ticks; deep (zone 2) when the feet's block and the deep_water_blocks - 1 blocks under it are all
water, or the water ladder's bo.deep is 1; otherwise shallow (zone 1); halved with bo.qual >= 1; land, wading and
riding recover. Vanilla command semantics as tests/test_blackout_pack.py's simulator runs them; here the simulator is
given a column of water (which block offsets under the feet are water), a vehicle and OnGround, and bo.sub / bo.deep are
set as the water ladder's water/tick sets them each tick before the sample (checked below against blackout/tick).

tools/open_water.py is tested on its own in tests/test_open_water.py; the swim no longer reads it, and since the owner's
water decision 2 (option C, d910046) only the boats' check does (tests/test_boats.py). Under water (decision 1): a
trained player (bo.qual >= 1) with the eyes in water neither tires nor recovers; water/tick starts an unset bo.surf at 0.

Not covered, and it needs a running server (EXP-044): that `on vehicle` sees a Cobblemon ride or a boat; that
`@s[nbt={OnGround:1b}]` is true for a player wading on the bottom and false for one treading water at the surface; that
the slowness and hunger feel as the data says; the measured swim speed of 5 blocks per second the "feel" note rests on;
that vanilla stores nothing when `on vehicle` finds no vehicle (the simulator assumes so; the pack resets #ride first
either way); how a waterlogged block or a kelp column reads in the #cobblers:water tag at the feet.
"""
from __future__ import annotations

import copy
import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import blackout_pack as BP  # noqa: E402
import test_blackout_pack as TB  # noqa: E402

CFG = TB.CFG
SURF = CFG["surface"]
NS = TB.NS
WATER_TAG = "#%s:water" % NS
PER = SURF["sample_ticks"]
GAIN_SHALLOW = SURF["gain_shallow_per_tick"] * PER
GAIN_DEEP = SURF["gain_deep_per_tick"] * PER
REC = SURF["recover_per_tick"] * PER
N_DEEP = SURF["deep_water_blocks"]
FCOL, FPULSE, FCAP = SURF["collapse_ticks"], SURF["pulse_ticks"], SURF["cap_ticks"]


def column(n, top=0):
    """The block offsets from the feet (0 the feet's block, -1 the one under it, ...) that are water: n blocks from
    `top` down, solid below."""
    return frozenset(range(top, top - n, -1))


LAND = frozenset()
SHALLOW = column(1)                # one block of water over the bottom
DEEP = column(64)                  # open water, any deep_water_blocks


BOATS = ("minecraft:boat", "minecraft:chest_boat")      # vanilla 1.21.1 entity types (a bamboo raft is a minecraft:boat)
PLAYER_HALF_WIDTH = 0.3                                 # vanilla: a player's hitbox is 0.6 wide, 1.8 tall
VOLUME = re.compile(r"@s\[x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)\]")


def _in_volume(state, m):
    """Vanilla: `@s[x=,y=,z=,dx=,dy=,dz=]` selects an entity whose hitbox meets [x, x + dx + 1) on each axis (strictly
    overlapping, AABB.intersects). The feet are at state x, y, z; y defaults to sea level."""
    x0, y0, z0, dx, dy, dz = (int(v) for v in m.groups())
    px, py, pz = state["x"], state.get("y", 62), state["z"]
    h = PLAYER_HALF_WIDTH
    return (px - h < x0 + dx + 1 and px + h > x0 and py < y0 + dy + 1 and py + 1.8 > y0
            and pz - h < z0 + dz + 1 and pz + h > z0)


def _sim(fns=None, pack=None, health=20, strict=True):
    """A loaded simulator whose world is `s.state`: water (a set of offsets), riding (anything), vehicle (its entity
    type; a ridden Pokemon is cobblemon:pokemon), ground (OnGround), x, z (the feet, floats; `data get ... Pos` floors
    them). `ride @s dismount` leaves the vehicle at once, as vanilla does. Every block offset the pack tests is recorded
    in `s.probed`, every query in `s.queried`. Once the load functions have run (they test storage the swim never
    touches), a test the simulator does not model fails when `strict`."""
    state = {"water": SHALLOW, "riding": False, "vehicle": None, "ground": False, "x": 0, "z": 0, "strict": False}
    probed, queried = [], []
    pack_files = pack or TB.PACK

    def query(cmd):
        queried.append(cmd)
        return {"data get entity @s Pos[0]": math.floor(state["x"]), "data get entity @s Pos[2]": math.floor(state["z"]),
                "attribute @s minecraft:generic.max_health get 1": 20, "data get entity @s Health 1": health}.get(cmd, 0)

    def cond(kind, toks):
        if kind == "block":
            x, y, z, what = toks
            assert x == "~" and z == "~" and y.startswith("~") and what == WATER_TAG, toks
            dy = int(y[1:] or 0)
            probed.append(dy)
            return dy in state["water"]
        if kind == "on":
            assert toks == ["vehicle"], toks
            return state["riding"]
        if kind == "entity" and toks[0] == "@s":
            return True
        if kind == "entity" and toks[0] == "@s[nbt={OnGround:1b}]":
            return state["ground"]
        if kind == "entity" and toks[0] == "@s[type=#%s:boats]" % NS:
            # after `on vehicle`: is the vehicle's type in the pack's own boats tag (read from the pack's file)
            tag = json.loads(pack_files["data/%s/tags/entity_type/boats.json" % NS])["values"]
            return state["riding"] and (state["vehicle"] or "cobblemon:pokemon") in tag
        if kind == "entity" and VOLUME.fullmatch(toks[0]):
            return _in_volume(state, VOLUME.fullmatch(toks[0]))
        if state["strict"]:
            raise AssertionError("the swim simulator does not know %s %s" % (kind, toks))
        return False

    s = TB.Sim(fns=fns or (TB.functions(pack) if pack else TB.FNS), query=query, cond=cond)
    orig = s.command

    def command(cmd):
        if cmd == "ride @s dismount":
            state["riding"], state["vehicle"] = False, None
        return orig(cmd)
    s.command = command
    s.state, s.probed, s.queried = state, probed, queried
    for f in TB.load_functions(pack):
        s.call(f)
    del probed[:], queried[:]
    state["strict"] = strict
    return s


def _swim(water=SHALLOW, sub=0, deep=0, riding=False, ground=False, qual=0, fat=0, samples=1, health=20, fns=None,
          fpt=None, x=0, z=0, vehicle=None, pack=None):
    """Run surface/tick `samples` times as one player. bo.sub (eyes in water) and bo.deep (eyes at the ladder's depth)
    are set as water/tick leaves them; bo.fwarn starts at 0, as surface/recover leaves it for anyone who has stood on
    land; bo.fpt (the collapse clock) is left unset unless given."""
    s = _sim(fns=fns, health=health, pack=pack)
    s.state.update(water=water, riding=riding or vehicle is not None, vehicle=vehicle, ground=ground, x=x, z=z)
    for k, v in (("bo.sub", sub), ("bo.deep", deep), ("bo.qual", qual), ("bo.fat", fat), ("bo.fwarn", 0)):
        s.set("@s", k, v)
    if fpt is not None:
        s.set("@s", "bo.fpt", fpt)
    for _ in range(samples):
        s.call("surface/tick")
    assert not s.missing, s.missing
    return s


def _pack_with(**surface):
    cfg = copy.deepcopy(CFG)
    cfg["surface"].update(surface)
    return TB.build(cfg)


# ------------------------------------------------------------------------------------------------ where fatigue builds

# Without it swimming is free somewhere: the first rule built fatigue only 96+ blocks from land, so the owner swam from
# Pallet to the landmass south-west of it without tiring, and Lake Tilpey (a lake, far from the sea) was free. The owner
# (2026-09-27): "fatigue on every swim". The pack must not consult a map: the same water tires the same anywhere.
@pytest.mark.parametrize("x,z", [(5964, 4135), (-900, 4000), (3700, 2400), (0, 0)],
                         ids=["Lake Tilpey", "the far west ocean", "the League's oval", "the origin"])
@pytest.mark.parametrize("water,gain", [(SHALLOW, GAIN_SHALLOW), (DEEP, GAIN_DEEP)], ids=["shallow", "deep"])
def test_every_swim_builds_fatigue_in_any_water_wherever_it_is(x, z, water, gain):
    assert GAIN_SHALLOW > 0, "shallow water must tire too"
    s = _swim(water=water, x=x, z=z, fat=0, samples=3)
    assert s.get("@s", "bo.fat") == 3 * gain, s.get("@s", "bo.fat")
    assert not [q for q in s.queried if "Pos" in q], "the swim sample reads the player's position: a map is back"


# Without it the deep rate starts at the wrong depth: a two-block pond counts as deep, or water must be deeper than the
# owner's "three blocks deep" before the rate rises. Deep is the feet's block and the deep_water_blocks - 1 under it all
# water (data "deep_water_blocks_basis"), so exactly deep_water_blocks blocks from the feet down are tested, and a
# column of k water blocks over solid ground is deep exactly when k >= deep_water_blocks.
@pytest.mark.parametrize("n", sorted({N_DEEP, 2, 1, 5}))
@pytest.mark.parametrize("sub", [0, 1], ids=["floating", "head under"])
def test_deep_is_exactly_deep_water_blocks_of_water_from_the_feet_down(n, sub):
    fns = TB.functions(_pack_with(deep_water_blocks=n))
    for k in range(1, n + 3):
        s = _swim(water=column(k), sub=sub, fns=fns)
        want = 2 if k >= n else 1
        assert s.get("@s", "bo.zone") == want, (n, k, s.get("@s", "bo.zone"))
        assert s.get("@s", "bo.fat") == (GAIN_DEEP if want == 2 else GAIN_SHALLOW), (n, k, s.get("@s", "bo.fat"))
        assert set(s.probed) == set(range(-(n - 1), 1)), (n, sorted(s.probed))
    if n >= 2:
        # a solid block under the feet ends the column, whatever water lies below it
        holed = column(1) | column(n + 3, top=-2)
        assert _swim(water=holed, sub=sub, fns=fns).get("@s", "bo.zone") == 1


# Without it the deep rate reads water under a swimmer whose feet are not in water: a swimmer whose feet are in a
# waterlogged block (a slab, a coral fan; the #cobblers:water tag lists only water, bubble columns, kelp and seagrass)
# and whose eyes are under water is counted deep over two water blocks under a non-water feet block, and with
# deep_water_blocks 1 every head-under swimmer is deep, though the rule is "the feet's block and the two under it all
# water". Low stakes (a rare position). Found by this suite at 2262aa3 (the deep line tested only ~-1..~-(n-1)); fixed
# in c9cb850, which tests the feet's block too.
@pytest.mark.parametrize("n", sorted({N_DEEP, 2, 1}))
def test_a_swimmer_whose_feet_block_is_not_water_is_not_deep_by_the_column(n):
    fns = TB.functions(_pack_with(deep_water_blocks=n))
    s = _swim(water=column(n + 5, top=-1), sub=1, deep=0, fns=fns)
    assert s.get("@s", "bo.zone") == 1, (n, s.get("@s", "bo.zone"))


# Without it a diver in a shallow-bottomed spot at depth, or one whose eyes are at the water ladder's depth over a ledge,
# tires at the shallow rate: the data's rule makes "the eyes at the water ladder's depth" deep, whatever the column.
@pytest.mark.parametrize("water", [SHALLOW, LAND], ids=["one block under the feet", "feet not in water"])
def test_eyes_at_the_ladders_depth_count_as_deep_water(water):
    s = _swim(water=water, sub=1, deep=1, samples=2)
    assert s.get("@s", "bo.zone") == 2
    assert s.get("@s", "bo.fat") == 2 * GAIN_DEEP, s.get("@s", "bo.fat")


# Without it a player walking through a stream or along a beach (feet in water, head out, on the bottom) tires as if
# swimming, or a swimmer who stands on the bottom with the head under water, or treads water at the surface, is let off.
@pytest.mark.parametrize("case,kw,builds", [
    ("wading in the shallows", dict(water=SHALLOW, sub=0, ground=True), False),
    ("wading at the edge of deep water", dict(water=column(N_DEEP), sub=0, ground=True), False),
    ("on the bottom, head under", dict(water=column(2), sub=1, ground=True), True),
    ("treading water at the surface", dict(water=SHALLOW, sub=0, ground=False), True),
    ("treading water over the deep", dict(water=DEEP, sub=0, ground=False), True),
])
def test_wading_recovers_and_swimming_does_not(case, kw, builds):
    s = _swim(fat=500, **kw)
    if builds:
        assert s.get("@s", "bo.fat") > 500, (case, s.get("@s", "bo.fat"))
    else:
        assert s.get("@s", "bo.fat") == 500 - REC, (case, s.get("@s", "bo.fat"))
        assert _swim(fat=REC // 2, **kw).get("@s", "bo.fat") == 0, "recovery stops at zero"


# Without it a swimmer who reaches land, or who rides a water Pokemon or a boat, stays tired (or tires further), and a
# ride across the sea exhausts its rider; or a player whose eyes are in water with the feet out of it is let off.
@pytest.mark.parametrize("where", ["land", "riding in the deep", "riding in the shallows", "feet dry, eyes in water"])
def test_land_and_riding_recover(where):
    kw = {"land": dict(water=LAND, sub=0), "riding in the deep": dict(water=DEEP, sub=1, deep=1, riding=True),
          "riding in the shallows": dict(water=SHALLOW, riding=True),
          "feet dry, eyes in water": dict(water=LAND, sub=1)}[where]
    s = _swim(fat=500, **kw)
    if where == "feet dry, eyes in water":
        assert s.get("@s", "bo.fat") == 500 + GAIN_SHALLOW, "eyes under water is swimming"
        return
    assert s.get("@s", "bo.fat") == 500 - REC, (where, s.get("@s", "bo.fat"))
    assert _swim(fat=REC // 2, **kw).get("@s", "bo.fat") == 0, "recovery stops at zero"


# Without it the ride flag (#ride, one fake-player score shared by every player) carries from a rider to the next
# player processed in the same tick: a swimmer handled after someone on a Lapras would recover instead of tiring.
# (Found by this suite at 5d522d7 as unverified: vanilla stores nothing when `on vehicle` finds none; fixed in 5bcecec.)
def test_a_swimmer_processed_after_a_rider_in_the_same_tick_still_tires():
    s = _swim(water=DEEP, riding=True, fat=500, samples=0)
    s.call("surface/tick")                                    # the rider
    assert s.get("@s", "bo.fat") == 500 - REC and s.get("#ride", "bo.tmp") == 1
    s.state["riding"] = False                                 # the next player: same fake player, no vehicle
    s.set("@s", "bo.fat", 500)
    s.call("surface/tick")
    assert s.get("@s", "bo.fat") == 500 + GAIN_DEEP, s.get("@s", "bo.fat")


# Without it deep water tires no faster than shallow, or a trained partner does not halve the strain (data
# "trained_partner"), in either depth.
@pytest.mark.parametrize("water,qual,gain", [(SHALLOW, 0, GAIN_SHALLOW), (DEEP, 0, GAIN_DEEP),
                                             (SHALLOW, 1, GAIN_SHALLOW // 2), (DEEP, 2, GAIN_DEEP // 2)])
def test_deep_water_uses_the_deep_rate_and_a_qualified_player_halves_it(water, qual, gain):
    assert GAIN_DEEP > GAIN_SHALLOW
    s = _swim(water=water, qual=qual, samples=7)
    assert s.get("@s", "bo.fat") == 7 * gain, (qual, s.get("@s", "bo.fat"))
    assert s.get("@s", "bo.zone") == (2 if water == DEEP else 1)


# ------------------------------------------------------------------------------------------------ what it runs on

# Without it the sample reads a stale bo.sub or bo.deep (last tick's, or a creative player's): a player who climbed out
# of the water keeps tiring on land, or the sample runs for creative and spectator players. water/tick must run before
# surface/tick in the same tick for the same players (survival and adventure), and reset both scores every tick.
def test_the_sample_reads_this_ticks_eye_state_for_survival_and_adventure_players_only():
    tick = TB.commands("blackout/tick")
    iw = next(i for i, l in enumerate(tick) if l.endswith("run function %s:water/tick" % NS))
    isf = next(i for i, l in enumerate(tick) if l.endswith("run function %s:surface/tick" % NS))
    assert iw < isf, (iw, isf)
    for i in (iw, isf):
        sel = re.search(r" as (@[ae]\[[^\]]*\])", tick[i]).group(1)
        assert "gamemode=!creative" in sel and "gamemode=!spectator" in sel, tick[i]
        assert sel.startswith("@a") or "type=player" in sel, tick[i]
    # a player on land with last tick's eyes-under-water scores: water/tick clears them and the sample recovers
    s = _sim(strict=False)
    s.state["water"] = LAND
    for k, v in (("bo.sub", 1), ("bo.deep", 1), ("bo.fat", 500), ("bo.fwarn", 1)):
        s.set("@s", k, v)
    s.call("water/tick")
    assert (s.get("@s", "bo.sub"), s.get("@s", "bo.deep")) == (0, 0)
    s.call("surface/tick")
    assert not s.missing, s.missing
    assert s.get("@s", "bo.fat") == 500 - REC


# Without it the swim sample consults the retired distance-from-land map again (640 surface/r/<z> row functions and the
# surface/row macro), or build() needs the canonical heightmap. Since the owner's water decision 2 (option C, d910046)
# the band map is back for boats only: main() reads tools/open_water.py's bands and writes the boat/r/<z> rows, and
# nothing else it writes differs from build() without them. The boats' own rows are tested in tests/test_boats.py.
def test_the_swim_has_no_sea_map_and_only_the_boat_rows_need_the_heightmap(tmp_path, monkeypatch):
    for mod in ("open_water", "ground", "terrain"):
        monkeypatch.setitem(sys.modules, mod, None)              # importing any of them now raises ImportError
    assert BP.build(copy.deepcopy(CFG), copy.deepcopy(TB.MOUNTS), copy.deepcopy(TB.PLACEMENTS),
                    copy.deepcopy(TB.PROGRESSION)) == TB.PACK
    with pytest.raises(ImportError):
        BP.main(["--out", str(tmp_path / "cobblers_blackout")])  # main() needs the band map for the boats
    surface = sorted(n for n in TB.FNS if n.startswith("surface/"))
    assert surface == ["surface/collapse", "surface/load", "surface/recover", "surface/tick", "surface/warn_exhausted",
                       "surface/warn_tiring"], surface
    assert not [k for k in TB.PACK if "/surface/r/" in k or k.endswith("surface/row.mcfunction")]
    assert not [l for n in surface for l in TB.FNS[n] if re.search(r"surface/r(/|ow\b)", l) or "$(" in l]
    # the one place the swim's tick reads a position is the boat check, reached only by a boat's rider
    tick = [l for l in TB.FNS["surface/tick"] if not l.startswith("#")]
    calls = [l for l in tick if "function %s:boat/" % NS in l]
    assert calls == ["execute if score #boat bo.tmp matches 1 run function %s:boat/check" % NS], calls
    assert not _swim(water=DEEP, samples=3).queried, "a swimmer's sample reads a position or a map"


# ------------------------------------------------------------------------------------------------ under water

# Without it swim fatigue cuts short what the water ladder promises under water (the owner, 2026-09-27: "Fatigue is the
# surface gate, air is the underwater gate, and they should not fight"; WATER_BUILD_PLAN F1: the every-swim rule knocked
# a Dive player out after 33 s): a trained player (bo.qual >= 1) with the eyes under water neither tires nor recovers,
# in any water, whatever the fatigue; an untrained one tires as on the surface; a trained one at the surface still
# tires, at half the rate.
@pytest.mark.parametrize("qual", [1, 2], ids=["surf", "dive"])
@pytest.mark.parametrize("water", [SHALLOW, DEEP, column(2)], ids=["shallow", "deep", "two blocks"])
@pytest.mark.parametrize("fat", [0, 500, FCOL + 40])
def test_a_trained_player_under_water_neither_tires_nor_recovers(qual, water, fat):
    s = _swim(water=water, sub=1, deep=int(water == DEEP), qual=qual, fat=fat, samples=5, fpt=0)
    assert s.get("@s", "bo.fat") == fat, (qual, fat, s.get("@s", "bo.fat"))
    assert not [c for c in s.calls if c[0].startswith("surface/")], s.calls
    assert not [l for l in s.log if l.startswith("effect give")], s.log


@pytest.mark.parametrize("water,gain", [(SHALLOW, GAIN_SHALLOW), (DEEP, GAIN_DEEP)], ids=["shallow", "deep"])
def test_an_untrained_player_under_water_tires_and_a_trained_one_at_the_surface_tires_at_half(water, gain):
    assert _swim(water=water, sub=1, qual=0, samples=3).get("@s", "bo.fat") == 3 * gain
    assert _swim(water=water, sub=0, qual=1, samples=3).get("@s", "bo.fat") == 3 * (gain // 2)


# Without it a player who never blacked out has no Surf bonus at all: water/deep tests `bo.surf < #surf`, which fails on
# an unset score, and blackout/arrive was its only setter (the contract check C2's finding). water/tick sets an unset
# bo.surf to 0 and leaves a set one alone (here: eyes under water above the ladder's depth, where nothing else moves it).
@pytest.mark.parametrize("water", [LAND, SHALLOW], ids=["on land", "eyes under shallow water"])
def test_the_surf_counter_starts_at_zero_when_unset(water):
    s = _sim(strict=False)
    s.state["water"] = water
    assert ("@s", "bo.surf") not in s.score
    s.call("water/tick")
    assert s.score.get(("@s", "bo.surf")) == 0
    if water == SHALLOW:
        assert s.get("@s", "bo.sub") == 1 and s.get("@s", "bo.deep") == 0
        s.set("@s", "bo.surf", 37)
        s.call("water/tick")
        assert s.get("@s", "bo.surf") == 37


# ------------------------------------------------------------------------------------------------ thresholds and hits

# Without it the warnings repeat every sample or never come, the slowness starts at the wrong fatigue, or fatigue grows
# without bound (a swimmer then needs hours on land to recover).
def test_warnings_come_once_effects_follow_the_thresholds_and_fatigue_is_capped():
    s = _swim(samples=SURF["exhausted_ticks"] // GAIN_SHALLOW + 2)
    tellraws = [l for l in s.log if l.startswith("tellraw")]
    assert len([l for l in tellraws if CFG["messages"]["surface_tiring"] in l]) == 1, tellraws
    assert len([l for l in tellraws if CFG["messages"]["surface_exhausted"] in l]) == 1, tellraws
    slow = _swim(fat=SURF["slow_ticks"] - GAIN_SHALLOW - 1)
    assert "effect give @s minecraft:slowness 2 0 true" not in slow.log
    slow = _swim(fat=SURF["slow_ticks"] - GAIN_SHALLOW)
    assert "effect give @s minecraft:slowness 2 0 true" in slow.log
    exh = _swim(fat=SURF["exhausted_ticks"] - GAIN_SHALLOW)
    assert {"effect give @s minecraft:slowness 2 1 true", "effect give @s minecraft:hunger 2 0 true"} <= set(exh.log)
    cap = _swim(water=DEEP, fat=FCAP - 1, samples=3)
    assert cap.get("@s", "bo.fat") == FCAP


# Without it a collapse deals some other damage than drowning's half-health hit (the ladder's lethal-from-half rule and
# its message would not apply), or never hits at all.
def test_a_collapse_pulse_reuses_the_drowning_hit():
    assert "function %s:water/pulse" % NS in TB.FNS["surface/collapse"]
    s = _swim(fat=FCOL - GAIN_SHALLOW)
    assert [c[0] for c in s.calls if c[0].startswith("water/")] == ["water/pulse", "water/pulse_apply"], s.calls
    assert "damage @s 10 minecraft:drown" in s.log, s.log
    s = _swim(fat=FCOL - GAIN_SHALLOW, health=10 + CFG["water"]["pulse_regen_margin"])
    assert "damage @s 1000 minecraft:drown" in s.log, s.log
    assert not [c for c in _swim(fat=FCOL - GAIN_SHALLOW - 1).calls if c[0] == "water/pulse"]


WHERE = {"shallow": SHALLOW, "deep": DEEP, None: LAND}


def _hits(plan, f0, fpt=None):
    """Run one sample per (water, qual) in `plan` from fatigue f0 (water "shallow", "deep" or None for a sample on land
    or a ledge); ([fatigue after each sample], [samples that hit])."""
    s = _swim(fat=f0, samples=0, fpt=fpt)
    fats, hits = [], []
    for i, (where, qual) in enumerate(plan):
        s.state["water"] = WHERE[where]
        s.set("@s", "bo.qual", qual)
        s.calls.clear()
        s.call("surface/tick")
        fats.append(s.get("@s", "bo.fat"))
        if any(c[0] == "water/pulse" for c in s.calls):
            hits.append(i)
    return fats, hits


N = 48
PLANS = {
    "shallow": [("shallow", 0)] * N,
    "deep": [("deep", 0)] * N,
    "shallow, trained": [("shallow", 1)] * N,
    "deep, trained": [("deep", 1)] * N,
    "shallow, then the deep after collapse": [("shallow", 0)] * 14 + [("deep", 0)] * (N - 14),
    "shallow trained, then the deep untrained after collapse": [("shallow", 1)] * 17 + [("deep", 0)] * (N - 17),
    "deep, then shallow, the partner coming and going": [("deep", 0), ("shallow", 1), ("deep", 1),
                                                         ("shallow", 0)] * (N // 4),
}


# Without it a collapsed swimmer is hit twice in half a second (and dies on the second) or never at all, depending on
# the depth, the partner and where the count started (found by this suite at 5d522d7; 5bcecec gave the hits a clock of
# their own, EXP-044): the first hit lands on the sample collapse is reached, then exactly one every pulse_ticks of
# TIME, in any water, trained or not, and across a change of depth or partner after collapse.
@pytest.mark.parametrize("plan", sorted(PLANS))
def test_past_collapse_a_hit_lands_once_per_pulse_ticks_of_time(plan):
    assert FPULSE % PER == 0, "the expectation below assumes pulse_ticks is a whole number of samples"
    every = FPULSE // PER
    bad = []
    for f0 in range(FCOL - 60, FCOL, 5):
        for fpt in (None, 0, FPULSE):                         # the clock unset, run down, or primed
            fats, hits = _hits(PLANS[plan], f0, fpt)
            first = next(i for i, f in enumerate(fats) if f >= FCOL)
            want = list(range(first, N, every))
            if hits != want:
                bad.append((f0, fpt, hits[:5], want[:5]))
    assert not bad, bad[:4]


# Without it a swimmer already past collapse whose clock was never set (a player from before the clock existed) is not
# hit until a whole pulse has passed, or a swimmer held at the fatigue cap is never hit again.
@pytest.mark.parametrize("f0", [FCOL, FCOL + 35, FCAP])
def test_a_swimmer_already_past_collapse_is_hit_at_once_and_then_on_the_clock(f0):
    every = FPULSE // PER
    _, hits = _hits([("deep", 0)] * N, f0)
    assert hits == list(range(0, N, every)), hits


# Without it a collapsed swimmer who touches land or a ledge for one sample, or dismounts a water Pokemon, and goes
# back in is hit at once, however recently the last hit landed: grabbing at the shore every other sample would bring a
# hit every 20 ticks instead of every pulse_ticks. (Found by this suite at 5bcecec; fixed in 2a70841.) One who recovers
# below collapse and comes back reaches it again, and is hit as they do.
def test_a_touch_of_land_past_collapse_does_not_bring_the_next_hit_early():
    every = FPULSE // PER
    fats, hits = _hits([("deep", 0), (None, 0)] * (N // 2), FCOL + 300)
    assert all(f >= FCOL for f in fats), "the swimmer stays past collapse throughout"
    gaps = [b - a for a, b in zip(hits, hits[1:])]
    assert hits and all(g >= every for g in gaps), (hits[:6], gaps[:6])
    # at collapse: one deep sample (hit), then enough samples on land to drop back under collapse, then the deep again;
    # the first deep sample after reaches collapse again and is hit as it does
    land = GAIN_DEEP // REC + 1
    plan = [("deep", 0)] + [(None, 0)] * land + [("deep", 0)] * (every + 3)
    fats, hits = _hits(plan, FCOL)
    assert fats[land] < FCOL <= fats[land + 1], fats
    assert hits == [0, land + 1, land + 1 + every], (hits, fats)


# Without it sample_ticks is half honoured: the gains and the collapse clock scale with it, but the tick that runs
# surface/tick stays every 10 ticks, so a sample_ticks of 20 would double every rate. (Found by this suite at 5d522d7;
# fixed in 5bcecec.)
@pytest.mark.parametrize("sample", [SURF["sample_ticks"], 20])
def test_the_surface_tick_runs_every_sample_ticks(sample):
    fns = TB.functions(_pack_with(sample_ticks=sample))
    tick = [l for l in fns["blackout/tick"] if not l.startswith("#")]
    i = next(i for i, l in enumerate(tick) if l.endswith("run function %s:surface/tick" % NS))
    holder = re.match(r"execute if score (#\w+) bo\.tmp matches 0 ", tick[i]).group(1)
    ops = [l for l in tick[:i] if l.startswith("scoreboard players operation %s bo.tmp " % holder)]
    assert ops[-2] == "scoreboard players operation %s bo.tmp = #gt bo.tmp" % holder, ops
    mod = ops[-1].split()[6]
    assert ops[-1].split()[5] == "%="
    consts = {l.split()[3]: int(l.split()[5]) for f in ("blackout/load", "surface/load") for l in fns[f]
              if l.startswith("scoreboard players set #")}
    assert consts[mod] == sample, (mod, consts[mod])


# ------------------------------------------------------------------------------------------------ the feel

def _timeline(water, qual=0, samples=60):
    """Seconds (at sample_ticks per sample, 20 ticks a second, the first sample one interval in) at which a fresh
    swimmer is first warned, slowed, exhausted and hit, and the second hit."""
    s = _swim(water=water, qual=qual, samples=0)
    seen = {}
    for i in range(samples):
        s.log.clear()
        s.calls.clear()
        s.call("surface/tick")
        t = (i + 1) * PER / 20
        marks = {"warned": any(CFG["messages"]["surface_tiring"] in l for l in s.log),
                 "slowed": "effect give @s minecraft:slowness 2 0 true" in s.log,
                 "exhausted": "effect give @s minecraft:slowness 2 1 true" in s.log,
                 "hit": any(c[0] == "water/pulse" for c in s.calls)}
        for k, v in marks.items():
            if v and k not in seen:
                seen[k] = t
            elif v and k == "hit" and "hit2" not in seen and t > seen["hit"]:
                seen["hit2"] = t
    return seen


# Without it the data's "feel" note (what the owner was told a swim is like) drifts from what the pack does: "in deep
# water an unaided swimmer is warned at 5 s, slowed at 7.5 s, exhausted at 11 s and hit from 15 s ... dead about 3 s
# later; in shallow water each step takes four times as long. A trained swimmer with a partner gets twice as far".
# Within one sample (the phase of the first sample is unknown in game).
def test_the_feel_note_matches_the_pack():
    tol = PER / 20
    deep = _timeline(DEEP)
    want = {"warned": 5, "slowed": 7.5, "exhausted": 11, "hit": 15, "hit2": 18}
    assert all(abs(deep[k] - v) <= tol for k, v in want.items()), (deep, want)
    shallow = _timeline(SHALLOW, samples=4 * 60)
    assert abs(shallow["warned"] - 4 * deep["warned"]) <= tol, (shallow, deep)
    trained = _timeline(DEEP, qual=1, samples=120)
    assert abs(trained["warned"] - 2 * deep["warned"]) <= tol and abs(trained["hit"] - 2 * deep["hit"]) <= tol


# Without it the owner's two named crossings flip: "Rivers (at most about 32 wide) stay crossable; the channel
# south-west of Pallet (over 100 blocks of deep water) ... do[es] not, unaided", at the note's 5 blocks per second.
# (Slowness only lengthens the channel; it is not modelled, so the channel case is the conservative one.)
def test_a_river_is_crossable_unaided_and_the_pallet_channel_is_not():
    speed = 5
    for width, crossable in ((32, True), (100, False)):
        samples = -(-width * 20 // (speed * PER))              # samples until across, rounded up
        s = _swim(water=DEEP, samples=samples)
        hit = any(c[0] == "water/pulse" for c in s.calls)
        assert hit != crossable, (width, s.get("@s", "bo.fat"))
