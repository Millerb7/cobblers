"""Gate clocks: no repeatable player action resets a clock or accumulator a gate relies on (contract C14).

Written by the test author at the owner's request of 2026-09-27: "the tipped-rider bug meant a free half-second of
recovery per tick, so boat-hopping would have crossed the whole ocean. That is the second time this week a small timing
detail defeated an entire gate ... look specifically for that shape: anywhere a repeatable action resets a timer that
is supposed to accumulate."

Each SCENARIO below takes one accumulating clock of a generated pack and one repeatable player action, runs the action
over and over with the pack's own functions, and checks the clock kept accumulating (or stayed where it was): it
returns nothing, or raises AssertionError with what was reset. tests/test_system_contracts.py runs every scenario as
contract C14 (a scenario that fails today is a strict xfail there, recorded in data/system_contracts.json). The
harness tests here show each scenario sees the reset it exists for, on a pack changed to make that reset.

The clocks, and the actions tried on each (the sweep's result is in the registry's C14 entry):
  swim fatigue bo.fat           relog, restart, a boat placed every sample on rough water, a touch of land each other
                                sample (it takes off recover_per_tick, never more)
  the collapse clock bo.fpt     relog past collapse (tests/test_surface_exhaustion.py holds the land-touch case)
  the Surf bonus bo.surf        bobbing the eyes up for less than breath_reset_ticks, relog mid-bonus
  the drowning pulses bo.pulse  relog out of air at depth
  the blackout dedupe bo.last   restart between two reports
  the gulch Megas gm.gone       restart, leaving and re-entering the approach box (the faces' gm.last was retired
                                with their restore, SOUTHERN_RIFT_MEGA.md 13)
  the ferry cooldown            relog and restart inside it
  the Ursaluna den #gone        restart, walking into the den and out past the return's clear radius (the den's
                                return clock, tests/test_ursaluna_cave.py; added by the den's builder, 2026-10-02)
  the mining caves' mcv.last    restart, leaving and re-entering the cave's approach box, the gallery mined out every
                                pass (tests/test_mining_caves_audit.py's command model; added 2026-10-10)
  the seam's ward               drinking milk (vanilla: clears every effect) between the ward's refreshes
  the gulch gate's ward         the same, with the zone check behind it
Not swept, and why: a gamemode change (only an operator can); dying (a blackout costs money and returns the player
to a checkpoint: not a cheap repeat); swapping the party mid-dive (Cobblemon's PC needs a PC block); riding a water
Pokemon (riding ends fatigue by design, WATER_BUILD_PLAN 11.2 item 3); the recovery claims' seen, alive_t and hit
notes (a repeat only delays the player's own rebuild or credit, never earns one).

Vanilla 1.21.1 facts used, not read from any jar here: a location advancement is tested every 20 ticks; drinking milk
takes 32 ticks and removes every effect; iron bars have hardness 5; a pickaxe's speed with Efficiency V is its tier
speed + 26 (diamond 8, netherite 9); a block breaks in ceil(30 * hardness / speed) ticks with the right tool.
Not covered, and it needs a running server: every one of those facts in play, and the scenarios' player timings.
"""
from __future__ import annotations

import copy
import itertools
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import test_blackout_pack as TB  # noqa: E402
import test_surface_exhaustion as TSE  # noqa: E402

CFG = TB.CFG
NS = TB.NS
N = 12


def _swimmer(fns=None, pack=None, fat=0, qual=0, water=TSE.DEEP):
    s = TSE._swim(water=water, fat=fat, qual=qual, samples=0, fns=fns, pack=pack)
    return s


def _outside_the_swim(s, *names):
    """Run functions the swim simulator does not model in full (login delivers claims, load sets storage) with its
    strict mode off: what they test about the ledger is not the point here, what they write to the scores is."""
    s.state["strict"] = False
    for n in names:
        s.call(n)
    s.state["strict"] = True


def _relog(s):
    _outside_the_swim(s, "blackout/login")


def _restart(s):
    _outside_the_swim(s, *TB.load_functions())


# ------------------------------------------------------------------------------------------------ swim fatigue

def fatigue_relog(fns=None):
    """Swim, relog (blackout/login), swim: the fatigue carries on from where it was."""
    s = _swimmer(fns)
    for _ in range(N):
        s.call("surface/tick")
    before = s.get("@s", "bo.fat")
    _relog(s)
    for _ in range(N):
        s.call("surface/tick")
    assert before == N * TSE.GAIN_DEEP and s.get("@s", "bo.fat") == 2 * N * TSE.GAIN_DEEP, (before, s.get("@s", "bo.fat"))


def fatigue_restart(fns=None):
    """Swim, restart (every load function runs again), swim."""
    s = _swimmer(fns)
    for _ in range(N):
        s.call("surface/tick")
    _restart(s)
    for _ in range(N):
        s.call("surface/tick")
    assert s.get("@s", "bo.fat") == 2 * N * TSE.GAIN_DEEP, s.get("@s", "bo.fat")


BOAT_PACK = None


def _boat_pack():
    global BOAT_PACK
    if BOAT_PACK is None:
        cx = cz = (0 + 1024) // 16                    # the cell of x, z 0.5: deep water in this row
        BOAT_PACK = TB.build(boat_rows={cz: [(cx, cx, 2)]})
    return BOAT_PACK


def fatigue_boat_hop(fns=None):
    """On rough water, a boat placed and boarded before every sample: each sample tips the rider out and counts as
    swimming, so the fatigue is what swimming the same samples gives (the tipped-rider finding, 0f190dd)."""
    pack = _boat_pack()
    s = _swimmer(fns or TB.functions(pack), pack=pack)
    for _ in range(N):
        s.state.update(x=0.5, z=0.5, riding=True, vehicle="minecraft:boat")
        s.call("surface/tick")
        assert "ride @s dismount" in s.log, "the rough-water row did not tip the rider"
        s.log.clear()
    assert s.get("@s", "bo.fat") == N * TSE.GAIN_DEEP, s.get("@s", "bo.fat")


def fatigue_land_touch(fns=None):
    """A touch of land every other sample takes off recover_per_tick for that sample, never more: over 2N samples
    the fatigue is N deep gains less N recoveries."""
    s = _swimmer(fns, fat=1000)
    for i in range(2 * N):
        s.state["water"] = TSE.DEEP if i % 2 == 0 else TSE.LAND
        s.call("surface/tick")
    assert s.get("@s", "bo.fat") == 1000 + N * (TSE.GAIN_DEEP - TSE.REC), s.get("@s", "bo.fat")


def collapse_clock_relog(fns=None):
    """Past collapse the hits come every pulse_ticks of time; a relog between hits brings the next neither sooner
    nor later."""
    every = TSE.FPULSE // TSE.PER
    s = _swimmer(fns, fat=TSE.FCOL + 100)
    hits = []
    for i in range(4 * every):
        if i == every + 1:
            _relog(s)
        s.calls.clear()
        s.call("surface/tick")
        if any(c[0] == "water/pulse" for c in s.calls):
            hits.append(i)
    assert hits == list(range(0, 4 * every, every)), hits


# ------------------------------------------------------------------------------------------------ the air ladder

def _surf_diver(fns=None):
    import test_system_contracts as TC
    s = TC.Swimmer(fns or TB.FNS, 40, TC._party("surf"), "surf")
    for _ in range(60):
        s.tick()
    s.place(CFG["water"]["deep_blocks"] + 3)
    for _ in range(300):
        s.tick()
    assert s.get("@s", "bo.qual") == 1 and s.get("@s", "bo.surf") >= 290, (s.get("@s", "bo.qual"), s.get("@s", "bo.surf"))
    return s


def surf_bonus_bobbing(fns=None):
    """The Surf bonus belongs to one submersion and resets only after the eyes stay in air, air full, for
    breath_reset_ticks (data/blackout.json water.breath_reset_why): bobbing the eyes up for less than that, again
    and again, never hands out a fresh bonus."""
    s = _surf_diver(fns)
    used = s.get("@s", "bo.surf")
    up = CFG["water"]["breath_reset_ticks"] // 2
    for _ in range(4):
        s.place(-1)
        for _ in range(up):
            s.tick()
        s.place(0)
        s.tick()
    assert s.get("@s", "bo.surf") >= used, ("the Surf bonus was reset by bobbing", used, s.get("@s", "bo.surf"))


def surf_bonus_relog(fns=None):
    """A relog at depth mid-bonus does not hand out a fresh bonus."""
    s = _surf_diver(fns)
    used = s.get("@s", "bo.surf")
    s.call("blackout/login")
    s.tick()
    assert s.get("@s", "bo.surf") >= used, (used, s.get("@s", "bo.surf"))


def drowning_pulse_relog(fns=None):
    """Out of air at depth the ladder hits every pulse_ticks; a relog between hits does not restart the count (the
    first hit of a fresh count lands at once, so a reset would bring hits sooner, never later: checked both ways)."""
    s = TB.Sim(fns=fns or TB.FNS)
    for f in TB.load_functions():
        s.call(f)
    s.set("@s", "bo.pulse", 7)
    s.set("@s", "bo.warn", 3)
    s.call("blackout/login")
    assert (s.get("@s", "bo.pulse"), s.get("@s", "bo.warn")) == (7, 3), (s.get("@s", "bo.pulse"), s.get("@s", "bo.warn"))


# ------------------------------------------------------------------------------------------------ the blackout, the ferry

def dedupe_restart(fns=None):
    """A second report inside dedupe_ticks is dropped across a restart (load runs again)."""
    now = {"t": 10_000}
    s = TB.Sim(fns=fns or TB.FNS, query=lambda cmd: now["t"] if cmd == "time query gametime" else 0)
    for f in TB.load_functions():
        s.call(f)
    s.call("blackout/dedupe")
    for f in TB.load_functions():
        s.call(f)
    now["t"] += CFG["dedupe_ticks"] - 1
    s.call("blackout/dedupe")
    assert s.get("#dup", "bo.tmp") == 1


def _ferry():
    import ferries as FR
    files, _npcs = FR.build(FR.load())
    fns = {}
    for k, v in files.items():
        if k.endswith(".mcfunction"):
            fns[k.split("/function/", 1)[1][:-len(".mcfunction")]] = v
    return FR, fns


def ferry_cooldown_relog_restart(fns=None):
    """A second click inside the cooldown pays nothing, even across a relog and a restart (data/ferries.json
    trip.cooldown_why: "must not pay twice")."""
    FR, ffns = _ferry()
    fns = fns or ffns
    trip = next(k for k in fns if k.startswith("ferries/sound_ferry/") and "_to_" in k)
    t = {"now": 50_000, "bal": 1000}

    def query(cmd):
        if cmd == "time query gametime":
            return t["now"]
        if cmd == "cobbledollars query @s":
            return t["bal"]
        raise AssertionError(cmd)

    import nbt_sim as NS_
    s = NS_.NbtSim(fns=fns, query=query, world=lambda kind, toks: False)
    orig = s.command

    def command(cmd):
        if cmd.startswith("cobbledollars remove @s "):
            t["bal"] -= int(cmd.split()[-1])
            return None
        return orig(cmd)
    s.command = command
    s.call("ferries/load")
    s.call(trip)
    paid = 1000 - t["bal"]
    assert paid > 0, "the first trip charged nothing"
    t["now"] += 10
    s.call("ferries/load")                              # a restart
    s.call(trip)
    t["now"] += 10
    s.call(trip)                                       # a relog changes no score: the same player clicks again
    assert 1000 - t["bal"] == paid, ("charged again inside the cooldown", 1000 - t["bal"], paid)


# ------------------------------------------------------------------------------------------------ the Megas' respawn clock

# SOUTHERN_RIFT_MEGA.md 13 retired the faces' restore (their clock gm.last is gone); the clock a gate now relies on is
# each den's respawn clock gm.gone, the farm's rate limit ("no repeatable action may reset it").

def _gone_mega_world(fns=None):
    import test_gulch_mine as TG
    w = TG._mine_world(fns)
    TG._run(w, 500)
    for e in TG._spawned(w, "excadrill"):
        w.entities.remove(e)
    return TG, w, w.gt


def gulch_megas_restart(fns=None):
    """A restart (minecraft:load again), every pass, never brings a gone Mega back before its respawn time."""
    TG, w, t_gone = _gone_mega_world(fns)
    got = []
    while w.gt - t_gone < TG.RESPAWN - 3 * TG.PASS:
        w.call("%s/load" % TG.F)
        got += TG._run(w, TG.PASS)
    assert not [d for _t, d in got if d == "excadrill"], got


def gulch_megas_reapproach(fns=None):
    """Leaving the approach box and coming back, again and again, never brings a gone Mega back before its time."""
    TG, w, t_gone = _gone_mega_world(fns)
    visitor = w.entities[0]
    got = TG._run(w, 2 * TG.PASS)
    while w.gt - t_gone < TG.RESPAWN - 3 * TG.PASS:
        w.entities.remove(visitor)
        got += TG._run(w, TG.PASS)
        w.entities.append(visitor)
        got += TG._run(w, TG.PASS)
    assert not [d for _t, d in got if d == "excadrill"], got


# ---- the open-air farms' dens (data farms[], 2026-10-01). The halls' two Megas sit inside one approach box the
# player is in for the whole visit; a farm den's box is its own 128-block square in open country, and the keeper runs
# only while a player is inside it. So walking out of the box and back is a cheaper, more obvious repeat than the
# mine's, and it is swept over every den the data declares rather than one.

FARM_RESP = 1200                     # each tier's respawn_ticks, cut so a den's clock runs inside a test


def _farm_dens():
    """Every farm den the data declares. None: the scenario is reported NOT_EXECUTED rather than passed, because a
    sweep over nothing is not a clock that held (.claude/rules/testing.md)."""
    import test_gulch_mine as TG
    if not TG.FARM_DENS:
        pytest.skip("NOT_EXECUTED: data/gulch_mine.json declares no farm den, so no farm clock was run")
    return TG.FARM_DENS


def _gone_farm_mega(site, den_id, fns=None):
    """One farm den whose Mega has just been taken, one player standing inside that farm's approach box."""
    import test_gulch_mine as TG
    spec, _den, w, who = TG._farm_world(site, den_id, fns=fns or TG.farm_keeper(FARM_RESP),
                                        respawn=FARM_RESP, players=1)
    # the den under test is the one Mega carrying its den tag (the Mega field's ranges overlap, 2026-10-04, so its
    # neighbours' Megas share the world; TG.den_megas checks each of them is another live den's own)
    megas = TG.den_megas(w, den_id)
    assert len(megas) == 1, (site, "the den's Mega never came up: the scenario would prove nothing", megas)
    w.entities.remove(megas[0])
    return TG, w, w.gt, who[0]


def _farm_back(TG, w, ticks, den_id):
    return [t for t, d in TG._run(w, ticks) if d == den_id]


def gulch_farm_megas_restart(fns=None):
    """A restart (minecraft:load again), every pass, never brings a farm den's Mega back before its respawn time,
    and it still comes back once the clock has run."""
    for site, den_id in _farm_dens():
        TG, w, t_gone, _p = _gone_farm_mega(site, den_id, fns)
        early = []
        while w.gt - t_gone < FARM_RESP - 3 * TG.PASS:
            w.call("%s/load" % TG.F)
            early += _farm_back(TG, w, TG.PASS, den_id)
        assert not early, (site, "back early after a restart", early, t_gone)
        back = _farm_back(TG, w, 8 * TG.PASS, den_id)
        assert back and back[0] - t_gone >= FARM_RESP, (site, "never came back, or came back early", back, t_gone)


def gulch_farm_megas_reapproach(fns=None):
    """Leaving a farm's approach box and coming back -- the keeper runs only while a player is inside it, so this is
    the cheapest repeat there is -- never brings its den's Mega back before its respawn time."""
    for site, den_id in _farm_dens():
        TG, w, t_gone, visitor = _gone_farm_mega(site, den_id, fns)
        early = _farm_back(TG, w, 2 * TG.PASS, den_id)
        while w.gt - t_gone < FARM_RESP - 3 * TG.PASS:
            w.entities.remove(visitor)
            early += _farm_back(TG, w, TG.PASS, den_id)
            w.entities.append(visitor)
            early += _farm_back(TG, w, TG.PASS, den_id)
        assert not early, (site, "back early after leaving and returning", early, t_gone)


# ------------------------------------------------------------------------------------------------ the wards

TRIGGER_TICKS = 20                    # vanilla: a location advancement is tested every 20 ticks
BEST_PICK_SPEED = 9 + 5 * 5 + 1       # a netherite pickaxe with Efficiency V
IRON_BARS_HARDNESS = 5.0


def ticks_to_break(hardness, speed=BEST_PICK_SPEED):
    return math.ceil(30 * hardness / speed)


def _position_box(adv):
    (crit,) = adv["criteria"].values()
    (cond,) = crit["conditions"]["player"]
    return cond["predicate"]["location"]["position"]


def milk_window(fns, folder, tick, ward_fn, adv, player_at, flags=()):
    """Run the pack for 60 ticks with one survival player at `player_at` (inside the ward): every tick the pack's tick
    function (minecraft:tick runs before the players), every 20 ticks the location advancement's reward if the feet
    are in its box. The player finishes drinking milk in their own tick right after the location refresh at tick 20
    (the worst phase for the guard: every effect cleared). Returns how many whole player ticks follow with no Mining
    Fatigue applied before them: the ticks a milk-drinker can mine at full speed."""
    import gulch_sim as GS
    w = GS.World({"%s/%s" % (folder, k): v for k, v in fns.items()})
    p = w.player(player_at, flags=flags)
    pos = _position_box(adv)
    inside = all(pos[a]["min"] <= v <= pos[a]["max"] for a, v in zip("xyz", player_at))
    applied = {}
    for t in range(1, 61):
        w.gt = t
        w.effects.clear()
        w.call("%s/%s" % (folder, tick))
        if t % TRIGGER_TICKS == 0 and inside:
            w.me = p
            w.call("%s/%s" % (folder, ward_fn))
            w.me = None
        applied[t] = any(e is p and "mining_fatigue" in c for e, c in w.effects)
    milk = TRIGGER_TICKS
    nxt = next((t for t in range(milk + 1, 61) if applied[t]), 61)
    return nxt - milk - 1


def _seam():
    import rift_mines as RM
    import types
    spec = json.loads((ROOT / "data" / "rift_mines.json").read_text(encoding="utf-8"))
    files, fn = RM.tease_files(types.SimpleNamespace(spec=spec))
    g = spec["mine"]["tease"]["grille"]
    at = ((g["x"][0] + g["x"][1]) / 2 + 0.5, g["y"][0], g["z"] + 1.5)      # in front of the grille, in the drift
    return files, fn, at


def seam_ward_milk(fns=None):
    """The seam's ward (data/rift_mines.json mine.tease) is its only guard: there is no zone check behind it. A player
    without gym6_cleared who drinks milk just after the ward's refresh must have fewer ticks at full speed than the
    grille's iron bars take to break with the best pickaxe, and the per-tick ward must cover the whole advancement box."""
    files, gen, at = _seam()
    fns = fns or gen
    adv = files["advancement/rift_mines/tease_ward.json"]
    free = milk_window(fns, "rift_mines", "tick", "tease/ward", adv, at)
    need = ticks_to_break(IRON_BARS_HARDNESS)
    assert free < need, ("milk clears the ward; the grille breaks in %d ticks, the ward is back after %d" % (need, free))
    # with the flag the ward lifts (decision 2: per player), whatever the tick does
    assert milk_window(fns, "rift_mines", "tick", "tease/ward", adv, at, flags=[json.loads(
        (ROOT / "data" / "rift_mines.json").read_text(encoding="utf-8"))["flag"]["advancement"]]) == 60 - TRIGGER_TICKS
    # every feet position the advancement's box holds is also held by the tick's (the corners and the centre)
    pos = _position_box(adv)
    for p in itertools.product(*[(pos[a]["min"], (pos[a]["min"] + pos[a]["max"]) / 2, pos[a]["max"] - 0.01) for a in "xyz"]):
        assert milk_window(fns, "rift_mines", "tick", "tease/ward", adv, p) < need, p


def gulch_ward_milk(fns=None):
    """The gulch gate's ward: the same milk, with the pack's tick re-applying the ward; and behind it the zone, whose
    check turns anyone without the flag back (the arrival and the exit box are in the zone; tests/test_gulch_mine.py
    checks every column of the zone)."""
    import test_gulch_mine as TG
    kf = fns or TG.keeper()
    adv = TG.FILES["advancement/gulch_mine/gate_ward.json"]
    g = TG.GATE["grille"]
    at = (g["x"] + 1.5, g["y"][0], (g["z"][0] + g["z"][1]) / 2 + 0.5)      # in the knock alcove, at the grille
    both = dict(kf, **{"gate/ward": TG.FNS["gate/ward"]})
    free = milk_window(both, "gulch_mine", "tick", "gate/ward", adv, at, flags=["cobblers:flag/gym6_cleared"])
    assert free < ticks_to_break(IRON_BARS_HARDNESS), free
    ranges = TG._zone_ranges()
    gt = TG.GATE
    assert TG._in_zone(ranges, gt["arrive"][:3])
    x0, y0, z0, x1, y1, z1 = gt["exit"]
    assert all(TG._in_zone(ranges, (x + 0.5, y0, z + 0.5)) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    (zone_fn,) = [l for l in TG.FNS["gate/zone"] if l.startswith("execute")]
    assert "turn_back" in zone_fn and TG.FNS["gate/zone"][2].startswith("advancement revoke"), TG.FNS["gate/zone"]


SCENARIOS = {
    "swim_fatigue-relog": fatigue_relog,
    "swim_fatigue-restart": fatigue_restart,
    "swim_fatigue-boat_hop_on_rough_water": fatigue_boat_hop,
    "swim_fatigue-land_touch": fatigue_land_touch,
    "collapse_clock-relog": collapse_clock_relog,
    "surf_bonus-bobbing": surf_bonus_bobbing,
    "surf_bonus-relog": surf_bonus_relog,
    "drowning_pulse-relog": drowning_pulse_relog,
    "blackout_dedupe-restart": dedupe_restart,
    "ferry_cooldown-relog_restart": ferry_cooldown_relog_restart,
    "gulch_megas-restart": gulch_megas_restart,
    "gulch_megas-reapproach": gulch_megas_reapproach,
    "gulch_farm_megas-restart": gulch_farm_megas_restart,
    "gulch_farm_megas-reapproach": gulch_farm_megas_reapproach,
    "seam_ward-milk": seam_ward_milk,
    "gulch_ward-milk": gulch_ward_milk,
    "ursaluna_den-restart": lambda fns=None: _den().den_restart(fns),
    "ursaluna_den-reapproach": lambda fns=None: _den().den_reapproach(fns),
    # the refillable mining caves' gallery restore clock mcv.last (ECONOMY_OVERHAUL.md 3.1: "the gallery restore's
    # clock must join contract C14's sweep"), run by tests/test_mining_caves_audit.py's command model on the pack the
    # builder emits for a flat synthetic fixture (no heightmap needed); added by the caves' auditor, 2026-10-10
    "mining_cave_gallery-restart": lambda fns=None: _caves().gallery_restart(fns),
    "mining_cave_gallery-reapproach": lambda fns=None: _caves().gallery_reapproach(fns),
}


def _caves():
    import test_mining_caves_audit as TC
    return TC


def _den():
    """The Ursaluna den's return clock (data/ursaluna_cave.json ursaluna.returns), run on its generated pack by
    tests/test_ursaluna_cave.py's world; it needs the canonical heightmap and skips without it."""
    import test_ursaluna_cave as TU
    return TU


# ================================================================================================= the harness

def _fails_on_its_clock(scenario, fns):
    """The scenario fails on the pack given, and by its own check, not because a model met something it does not know."""
    with pytest.raises(AssertionError) as e:
        scenario(fns)
    msg = str(e.value)
    assert not any(k in msg for k in ("does not know", "simulator", "unmodelled", "macro ")), msg


def _broken(name, line):
    """The blackout pack with one line appended to a function: a reset a scenario must see."""
    fns = copy.deepcopy(TB.FNS)
    fns[name] = fns[name] + [line]
    return fns


# Without it a scenario passes because it runs nothing: each blackout scenario, on a pack where the repeated action
# resets its clock, fails.
@pytest.mark.parametrize("scenario,name,line", [
    ("swim_fatigue-relog", "blackout/login", "scoreboard players set @s bo.fat 0"),
    ("swim_fatigue-restart", "surface/load", "scoreboard players set @s bo.fat 0"),
    ("swim_fatigue-land_touch", "surface/recover", "scoreboard players set @s bo.fat 0"),
    ("collapse_clock-relog", "blackout/login", "scoreboard players operation @s bo.fpt = #fpulse bo.cfg"),
    ("drowning_pulse-relog", "blackout/login", "scoreboard players set @s bo.pulse 0"),
    ("blackout_dedupe-restart", "blackout/load", "scoreboard players reset @s bo.last"),
    ("surf_bonus-relog", "blackout/login", "scoreboard players set @s bo.surf 0"),
    ("surf_bonus-bobbing", "water/surfaced", "scoreboard players set @s bo.surf 0"),
])
def test_harness_each_scenario_sees_the_reset_it_exists_for(scenario, name, line):
    _fails_on_its_clock(SCENARIOS[scenario], _broken(name, line))


# Without it the gulch Megas' scenarios pass on a keeper whose clock a restart or a re-approach resets: with load
# setting every den's clock to 0 (due at once), and with the keeper forgetting a gone Mega whenever its pass finds
# nobody, each fails.
def test_harness_the_mining_cave_scenarios_see_a_reset_gallery_clock():
    # Without it the two cave scenarios pass on a pack whose restart, or whose drive when nobody is near, re-arms a
    # gallery: with load setting fx_g1's clock to 0 (due at once), and with the drive doing so whenever the approach
    # box is empty, each scenario fails on its own check.
    TC = _caves()
    fns, tag = TC.pack(TC.fixture_spec())
    load = dict(fns, load=fns["load"] + ["scoreboard players set #fx_g1 mcv.last 0"])
    _fails_on_its_clock(SCENARIOS["mining_cave_gallery-restart"], (load, tag))
    (near,) = [l for l in fns["drive"] if l.endswith("near_fx_east")]
    nobody = near.split(" run ")[0].replace("execute if entity", "execute unless entity")
    drive = dict(fns, drive=fns["drive"] + [nobody + " run scoreboard players set #fx_g1 mcv.last 0"])
    _fails_on_its_clock(SCENARIOS["mining_cave_gallery-reapproach"], (drive, tag))


def test_harness_the_megas_scenarios_see_a_reset_respawn_clock():
    import test_gulch_mine as TG
    kf = TG.keeper()
    load = dict(kf, load=kf["load"] + ["scoreboard players set #excadrill gm.gone 0"])
    _fails_on_its_clock(gulch_megas_restart, load)
    drive = dict(kf, drive=kf["drive"] + ["execute unless entity %s run scoreboard players set #excadrill gm.gone 0"
                                          % kf["drive"][2].split(" ")[3]])
    _fails_on_its_clock(gulch_megas_reapproach, drive)


# Without it the Ursaluna den's scenarios pass on a pack whose clock a restart or a walk out of the den resets: with
# load setting the clock to 0 (due at once), and with the keeper forgetting the clock whenever nobody is within the
# return's clear radius, each fails.
def test_harness_the_ursaluna_den_scenarios_see_a_reset_return_clock():
    TU = _den()
    fns = TU.den_fns()
    load = dict(fns)
    load["ursaluna_cave/load"] = fns["ursaluna_cave/load"] + ["scoreboard players set #gone cobblers.ursaluna 0"]
    _fails_on_its_clock(SCENARIOS["ursaluna_den-restart"], load)
    _b, (x, y, z) = TU.spot()
    keeper = dict(fns)
    keeper["ursaluna_cave/keeper"] = ["execute positioned %s %s %s unless entity @a[distance=..%d] run scoreboard "
                                      "players set #gone cobblers.ursaluna 0" % (x, y, z, TU.CLEAR)] + fns["ursaluna_cave/keeper"]
    _fails_on_its_clock(SCENARIOS["ursaluna_den-reapproach"], keeper)


# Without it the FARM dens' scenarios pass on a keeper whose clock a restart or a walk out of the approach box
# resets -- the keeper runs only while a player is inside that box, so forgetting a gone Mega on an empty pass would
# make each den's Mega free. Both resets are injected on the same cut-respawn keeper the scenarios build, and the one
# den they name is the first the data declares, so a scenario that silently swept nothing cannot pass either.
def test_harness_the_farm_megas_scenarios_see_a_reset_respawn_clock():
    import test_gulch_mine as TG
    site, den_id = _farm_dens()[0]
    kf = TG.farm_keeper(FARM_RESP)
    load = dict(kf, load=kf["load"] + ["scoreboard players set #%s gm.gone 0" % den_id])
    _fails_on_its_clock(gulch_farm_megas_restart, load)
    (pass_line,) = [l for l in kf["drive"] if l.endswith("/drive_%s" % site)]
    drive = dict(kf, drive=kf["drive"] + ["execute unless entity %s run scoreboard players set #%s gm.gone 0"
                                          % (pass_line.split(" ")[3], den_id)])
    _fails_on_its_clock(gulch_farm_megas_reapproach, drive)


# Without it the boat-hop scenario passes on a pack that lets a tipped rider recover: the pre-0f190dd surface/tick,
# without its #ride reset, must fail it.
def test_harness_the_boat_hop_scenario_sees_the_tipped_rider_bug():
    pack = _boat_pack()
    fns = TB.functions(pack)
    tick = fns["surface/tick"]
    i = max(k for k, l in enumerate(tick) if l == "scoreboard players set #ride bo.tmp 0")
    assert i > 0
    fns["surface/tick"] = tick[:i] + tick[i + 1:]
    _fails_on_its_clock(fatigue_boat_hop, fns)


# Without it the ferry scenario passes on a trip that never sets its cooldown.
@pytest.mark.xfail(strict=True, reason=(
    "The ferry data is mid-migration and this scenario finds no live crossing to walk, so it raises "
    "StopIteration before it can test anything. Same root cause as contract C14 "
    "(ferry_cooldown-relog_restart), recorded in data/system_contracts.json `fails_today` on 2026-09-30 with "
    "the measurement: the sound_ferry line's two stops are both status 'retired', pacifidlog_ferry's second "
    "stop is retired too, and C3's `to` end (7210,6960) is ground y55 under a sea of y62 and not a deck cell "
    "- the sea town moved out from under the crossing. Strict on purpose: when the migration is finished this "
    "passes, the run fails, and this marker comes off with the registry entry. It fails identically at "
    "36eb267, so it predates the 2026-09-30 work."))
def test_harness_the_ferry_scenario_sees_a_missing_cooldown():
    _FR, fns = _ferry()
    fns = {k: [l for l in v if "cobblers_ferry_cd" not in l or "if score" in l] for k, v in fns.items()}
    _fails_on_its_clock(ferry_cooldown_relog_restart, fns)


# Without it the milk arithmetic is wrong in the other direction: an unenchanted diamond pickaxe (speed 8) needs 19
# ticks for iron bars; a block of obsidian (hardness 50) takes far longer than any window.
def test_harness_the_break_arithmetic():
    assert ticks_to_break(IRON_BARS_HARDNESS, 8) == 19 and ticks_to_break(50) > 40
    assert ticks_to_break(IRON_BARS_HARDNESS) == 5


# Without it the milk scenarios pass whatever the pack's tick does: with the per-tick ward line taken out of the
# seam's tick (the pack before 9a9a1fa), only the location trigger refreshes the ward, the window is 19 ticks and the
# grille falls; the same for the gulch gate's.
def test_harness_removing_the_per_tick_ward_brings_the_milk_exploit_back():
    _files, fn, _at = _seam()
    stripped = dict(fn, tick=[l for l in fn["tick"] if "mining_fatigue" not in l])
    assert len(stripped["tick"]) < len(fn["tick"])
    _fails_on_its_clock(seam_ward_milk, stripped)
    import test_gulch_mine as TG
    kf = TG.keeper()
    kf = dict(kf, tick=[l for l in kf["tick"] if "mining_fatigue" not in l])
    _fails_on_its_clock(gulch_ward_milk, kf)
