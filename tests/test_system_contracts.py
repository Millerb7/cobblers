"""Cross-system contracts: one system's guarantee that another system relies on (data/system_contracts.json).

Written by the test author, not by any session that wrote the systems under test. The owner's request of 2026-09-27:
"a change made to fix the surface broke the underwater rules, and nothing caught it except reading the consequences
through. Worth a check that flags when one system's change invalidates another's assumptions." Each test here runs two
or more systems TOGETHER, as generated, and asserts the guarantee the registry states, with the expectation taken from
the documents and the authored data, never from the generated output being checked.

The registry (data/system_contracts.json) is data a human reviews: each contract names its owner (the system whose data
or code provides the guarantee), the consumers that rely on it, the documents that state it (path:line and a quote that
must still be on that line), and the tests that enforce it. The meta-tests at the end keep the registry and the tests in
step: every contract names an existing test, every contract test here is registered, every contract has a consumer
other than its owner, every citation still says what the registry quotes, and a contract that fails today is marked
strict xfail here and "fails_today" there (so the mark flips to a failure the moment the fix lands, and is removed).

Models used, all test-side and independent of the generators:
  - tests/test_blackout_pack.py's command simulator and tests/nbt_sim.py's NbtSim (command storage as NBT) and MoLang
    subset, driven here by a player model: a water column, the eye and feet blocks, vanilla air (Minecraft 1.21.1
    LivingEntity: under water a tick keeps its air with chance bonus/(bonus + 1) where bonus is the oxygen_bonus
    attribute, else loses 1; at -20 the air resets to 0 and the player takes 2 drowning damage; out of water it
    regains 4 a tick up to 300), health (20, no regeneration: conservative, a knock-out only comes sooner), the
    minecraft:tick tag running before the player's own tick (MinecraftServer.tickServer runs functions first), and
    Cobblemon's player_tick_pre callback in the player's tick.
  - tools/ground.py's heightmap (rounded), with Relic Island's islet and the sea town's decks laid over as ground, for
    the ferry crossings (skipped, with the reason, when the heightmap is unavailable).

What none of this covers (runtime, EXP-042 and EXP-044): the real swim speed and eye height while swimming, natural
regeneration and the damage cooldown, that Cobblemon fires the callbacks and exposes the fields they read, and that a
player on the server meets these rules as the models say. A green run proves the systems agree on paper. Also not
covered here: a Dive or Surf player whose eyes are above the ladder's depth (vanilla air there, by DEATH_AND_WIPE.md
rule 8); Slowness on the ferry crossings (the plan's own reading is that it does not slow an unaided swimmer, and not
counting it is the conservative case for a gate); ferry lines the plan gives no line for (the charters); wild levels
against the level cap (the plan calls the level-cap trap open, so there is no agreed rule to hold yet).
"""
from __future__ import annotations

import ast
import copy
import fnmatch
import itertools
import json
import math
import os
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import nbt_sim as N  # noqa: E402
import test_blackout_pack as TB  # noqa: E402

REGISTRY_PATH = ROOT / "data" / "system_contracts.json"
REGISTRY = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
CONTRACTS = {c["id"]: c for c in REGISTRY["contracts"]}
THIS = "tests/test_system_contracts.py"


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


BLACKOUT = TB.CFG
WATER = BLACKOUT["water"]
SURFACE = BLACKOUT["surface"]
MOUNTS = TB.MOUNTS
NS = TB.NS
VANILLA_AIR = 300                      # Minecraft 1.21.1 Player max air supply
EYE, REACH = 1.62, 4.5                 # vanilla 1.21.1: standing eye height, survival block interaction range


def _params(cid, cases):
    """One pytest.param per (id, values); strict xfail, with the registry's reason, for each case the registry's
    fails_today.cases patterns match. Strict: when the fix lands the case passes, the run fails, and the entry goes."""
    failing = CONTRACTS[cid].get("fails_today", {}).get("cases", {})
    out = []
    for pid, values in cases:
        reasons = [r for pat, r in failing.items() if fnmatch.fnmatch(pid, pat)]
        marks = [pytest.mark.xfail(strict=True, reason="%s fails today: %s" % (cid, reasons[0]))] if reasons else []
        out.append(pytest.param(*values, id=pid, marks=marks))
    return out


# =================================================================================================================
# The swimmer: the blackout pack's tick, the water-mounts callback and a player in a water column, together
# =================================================================================================================

SEA_TOP = 61                            # the top water block's y; only positions relative to it matter
FEATURES = ("surface/tick",)            # the swim-fatigue entry point, removable for a ladder-only control run


def _split_filters(body):
    out, depth, cur = [], 0, ""
    for ch in body:
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return [f.split("=", 1) for f in out]


class Swimmer(N.NbtSim):
    """One survival player, in a column of water `floor_depth` blocks deep whose top block is SEA_TOP.

    `eye_y` and `feet_y` are the blocks the eyes and feet are in. Block tests are answered from the column, relative
    to the eyes after `anchored eyes positioned ^ ^ ^` and to the feet otherwise. Selectors are evaluated against this
    player (a Pokemon or item selector selects nothing). Anything the model does not know fails the test."""

    def __init__(self, fns, floor_depth, party, training):
        self.state = {"floor_depth": floor_depth, "eye_y": SEA_TOP + 2, "feet_y": SEA_TOP + 1, "ground": True}
        self.gt, self.air, self.oxygen, self.health = 0, float(VANILLA_AIR), 0.0, 20.0
        self.tags, self.damage = set(), []
        self._eyes = False
        self.party = party
        super().__init__(fns=fns, query=self._query, world=self._world)
        for f in TB.load_functions():
            self.call(f)
        self.set("@s", "bo.leave", 1)                 # a player who has just joined: blackout/login runs first
        if training:
            self.call("water/grant_%s" % training)
        self.mol = N.Molang(TB.PACK[TB.WATER_MOL])

    # ---- the world the pack's tests ask about
    def water(self, y):
        return SEA_TOP - self.state["floor_depth"] < y <= SEA_TOP

    def select(self, sel):
        if sel == "@s":
            return True
        m = re.fullmatch(r"@([aesp])(?:\[(.*)\])?", sel)
        assert m, "the swimmer model does not know the selector %s" % sel
        filters = _split_filters(m.group(2) or "")
        for k, v in filters:
            if k == "type":
                if v != "player":
                    return False
            elif k == "gamemode":
                if (v[1:] == "survival") if v.startswith("!") else (v != "survival"):
                    return False
            elif k == "tag":
                if (v[1:] in self.tags) if v.startswith("!") else (v not in self.tags):
                    return False
            elif k == "scores":
                for obj, rng in re.findall(r"([\w.]+)=([-\d.]+)", v):
                    if ("@s", obj) not in self.score or not TB.in_range(self.get("@s", obj), rng):
                        return False
            elif k == "nbt":
                assert v == "{OnGround:1b}", sel
                if not self.state["ground"]:
                    return False
            elif k in ("limit", "sort"):
                pass
            else:
                raise AssertionError("the swimmer model does not know the selector filter %s in %s" % (k, sel))
        return True

    def _world(self, kind, toks):
        if kind == "block":
            x, y, z, what = toks
            assert x == "~" and z == "~" and y.startswith("~") and what == "#%s:water" % NS, toks
            base = self.state["eye_y"] if self._eyes else self.state["feet_y"]
            return self.water(base + int(y[1:] or 0))
        if kind == "entity":
            return self.select(toks[0])
        if kind == "on":
            return False                                  # riding nothing; no attacker, no owner
        raise AssertionError("the swimmer model does not know `%s %s`" % (kind, toks))

    def _query(self, cmd):
        table = {"time query gametime": self.gt, "data get entity @s Air": int(math.floor(self.air)),
                 "data get entity @s Pos[0]": 0, "data get entity @s Pos[2]": 0,
                 "attribute @s minecraft:generic.max_health get 1": 20,
                 "data get entity @s Health 1": int(self.health)}
        if cmd in table:
            return table[cmd]
        if cmd.startswith("effect clear @s "):
            return 0                                      # nothing to clear: no potion, no conduit
        raise AssertionError("the swimmer model does not know the query %s" % cmd)

    def execute(self, t):
        for i, w in enumerate(t[:-1]):
            if w == "as" and not self.select(t[i + 1]):
                return None                               # no executor: nothing runs, nothing is stored
        self._eyes = "anchored" in t and t[t.index("anchored") + 1] == "eyes"
        try:
            return super().execute(t)
        finally:
            self._eyes = False

    def command(self, cmd):
        m = re.fullmatch(r"damage @s (\d+) minecraft:drown", cmd)
        if m:
            src = next((c[0] for c in reversed(self.calls) if c[0] in ("surface/collapse", "water/out")), "?")
            self.health -= int(m.group(1))
            self.damage.append((self.gt, int(m.group(1)), {"surface/collapse": "swim fatigue",
                                                           "water/out": "the air ladder"}.get(src, src)))
            return None
        m = re.fullmatch(r"attribute @s minecraft:generic\.oxygen_bonus modifier (add|remove) cobblers:ladder(?: (\S+) add_value)?", cmd)
        if m:
            self.oxygen = float(m.group(2)) if m.group(1) == "add" else 0.0
            return None
        m = re.fullmatch(r"tag @s (add|remove) (\S+)", cmd)
        if m:
            (self.tags.add if m.group(1) == "add" else self.tags.discard)(m.group(2))
            return None
        return super().command(cmd)

    # ---- one server tick: the function tick tag, then the player's own tick (callback, air)
    def tick(self):
        self.gt += 1
        self.calls.clear()
        self.log.clear()
        self.call("blackout/tick")
        # Cobblemon's player_tick_pre callback (data/water_mounts.json through the generated MoLang)
        q = {"player": {"world": {"game_time": float(self.gt)}, "username": "Diver",
                        "party": {"pokemon": [{"current_hp": 30.0, "species": {"identifier": "cobblemon:%s" % s}}
                                              for s in self.party]}}}
        for c in self.mol.run({}, q):
            self.command(c.replace(" Diver ", " @s "))
        # vanilla air, after the functions
        if self.water(self.state["eye_y"]):
            self.air -= 1.0 / (self.oxygen + 1.0) if self.oxygen > 0 else 1.0
            if self.air <= -20:
                self.air = 0.0
                self.health -= 2
                self.damage.append((self.gt, 2, "vanilla drowning"))
        else:
            self.air = min(float(VANILLA_AIR), self.air + 4)
        assert not self.missing, self.missing

    def place(self, eye_depth, on_floor=False):
        """Eyes `eye_depth` blocks under the top water block (0: in the top block), feet one block lower."""
        eye_y = SEA_TOP - eye_depth
        self.state.update(eye_y=eye_y, feet_y=eye_y - 1, ground=on_floor)


def _party(rung):
    dive = sorted(MOUNTS["dive"])
    surf_only = sorted(set(MOUNTS["surf"]) - set(MOUNTS["dive"]))
    return {"dive": [dive[0]], "surf": [surf_only[0]], "none": ["pikachu"]}[rung]


def dive_run(rung, eye_depth, floor_depth, ticks, fatigue=True, warmup=60, history="fresh"):
    """A player trained for `rung` (dive, surf or none) with a matching partner, rested on land for `warmup` ticks,
    then held with the eyes `eye_depth` under the surface for up to `ticks` ticks or until knocked out. `history`
    "fresh" is a player who has never blacked out; "blacked out" one who has, and has been returned (blackout/arrive
    run once, as the pack runs it on the first living tick after a blackout)."""
    fns = dict(TB.FNS)
    if not fatigue:
        for f in FEATURES:
            fns[f] = []
    s = Swimmer(fns, floor_depth, _party(rung), {"dive": "dive", "surf": "surf", "none": None}[rung])
    if history == "blacked out":
        s.call("blackout/arrive")
    else:
        assert history == "fresh", history
    for _ in range(warmup):
        s.tick()
    on_floor = eye_depth + 2 >= floor_depth              # the feet in the lowest water block
    s.place(eye_depth, on_floor=on_floor)
    start, ko, air_min = s.gt, None, VANILLA_AIR
    for _ in range(ticks):
        s.tick()
        air_min = min(air_min, s.air)
        if s.health <= 0:
            ko = s.gt - start
            break
    first = (s.damage[0][0] - start) if s.damage else None
    return {"ko": ko, "first_damage": first, "sources": [(t - start, a, why) for t, a, why in s.damage],
            "air_min": air_min, "qual": s.get("@s", "bo.qual"), "sim": s}


# Without it the harness could pass the contracts below by modelling nothing: an untrained player at depth must run out
# of vanilla air and be knocked out by the ladder's two half-health hits (DEATH_AND_WIPE.md rule 9) within a few seconds
# of the 300 ticks, and a trained diver must actually be qualified (bo.qual 2) by the party the callback read.
def test_harness_an_untrained_player_at_depth_is_knocked_out_by_the_ladder_after_vanilla_air():
    r = dive_run("none", eye_depth=WATER["deep_blocks"] + 3, floor_depth=40, ticks=VANILLA_AIR + 200, fatigue=False)
    assert r["ko"] is not None and VANILLA_AIR - 5 <= r["ko"] <= VANILLA_AIR + 2 * WATER["pulse_ticks"] + 5, r["ko"]
    ladder = [why for _t, amount, why in r["sources"] if amount != 2]
    assert ladder[:2] == ["the air ladder", "the air ladder"], r["sources"]
    # and the control switch removes only fatigue: with it on, fatigue hits an untrained deep swimmer too
    both = dive_run("none", eye_depth=WATER["deep_blocks"] + 3, floor_depth=40, ticks=VANILLA_AIR + 200)
    assert "swim fatigue" in [why for _t, _a, why in both["sources"]], both["sources"]
    d = dive_run("dive", eye_depth=WATER["deep_blocks"] + 3, floor_depth=40, ticks=40)
    assert d["qual"] == 2 and d["sim"].oxygen == WATER["ladder_oxygen_bonus"], (d["qual"], d["sim"].oxygen)
    s = dive_run("surf", eye_depth=WATER["deep_blocks"] + 3, floor_depth=40, ticks=40)
    assert s["qual"] == 1, s["qual"]



DIVE_SPOTS = [("eyes-at-the-ladders-depth", WATER["deep_blocks"], 40),
              ("mid-water-over-a-trench", 20, 60),
              ("standing-on-the-floor-50-deep", 48, 50)]
TEN_MINUTES = 10 * 60 * 20


# C1. Without it a change to one water rule (the surface fatigue of 2026-09-27) silently caps Dive, which the ladder
# promises is unlimited: a Dive-trained player with a Dive partner was knocked out after about 33 s underwater, and every
# Dive site in WATER_MAP.md and WATER_BUILD_PLAN.md is sized on unlimited air.
@pytest.mark.parametrize("eye_depth,floor_depth", _params("C1", [(i, (e, f)) for i, e, f in DIVE_SPOTS]))
def test_contract_c1_a_dive_player_at_depth_is_never_knocked_out_by_any_system(eye_depth, floor_depth):
    r = dive_run("dive", eye_depth, floor_depth, TEN_MINUTES)
    assert r["qual"] == 2
    assert r["ko"] is None and not r["sources"], (
        "a Dive player at depth was hurt: %s (knocked out at %s ticks)" % (r["sources"][:3], r["ko"]))


# C2. Without it the Surf rung's promise (DEATH_AND_WIPE.md: surf_bonus_ticks held full, then vanilla's 300 ticks, then
# the pulses; "about 60 seconds total") is cut short by another system, or never given: under the 2026-09-27 fatigue
# rule a Surf player at depth was hit at 30 s, before the bonus ran out. The ladder alone is the control (the same pack
# with surface/tick emptied): nothing may hurt the player sooner than it does, and it may not hurt them before the bonus
# plus vanilla air. Both a player who has never blacked out and one who has (blackout/arrive run once) are checked.
@pytest.mark.parametrize("history,eye_depth,floor_depth", _params(
    "C2", [("%s-%s" % (h.replace(" ", "-"), i), (h, e, f)) for h in ("fresh", "blacked out") for i, e, f in DIVE_SPOTS]))
def test_contract_c2_a_surf_player_at_depth_gets_the_whole_bonus_and_nothing_hurts_them_sooner(history, eye_depth,
                                                                                            floor_depth):
    budget = WATER["surf_bonus_ticks"] + VANILLA_AIR
    alone = dive_run("surf", eye_depth, floor_depth, budget + 400, fatigue=False, history=history)
    assert alone["qual"] == 1
    assert alone["first_damage"] is not None and alone["first_damage"] >= budget - 2, (
        "the Surf rung gave %s ticks before the first hit, not surf_bonus_ticks + %d: %s"
        % (alone["first_damage"], VANILLA_AIR, alone["sources"][:2]))
    both = dive_run("surf", eye_depth, floor_depth, budget + 400, history=history)
    assert both["first_damage"] is not None and both["first_damage"] >= alone["first_damage"], (
        "another system hurt a Surf player at depth first: %s, the ladder alone at %s ticks"
        % (both["sources"][:2], alone["first_damage"]))
    assert both["ko"] is not None and both["ko"] >= alone["ko"], (both["ko"], alone["ko"])


# =================================================================================================================
# C3. The ferry's gates, re-walked on the heightmap with the pack's own swim fatigue
# =================================================================================================================

C3 = CONTRACTS["C3"]
SPEED = 5.0                             # blocks per second, the measured sprint-swim (WATER_MAP.md section 0)


@pytest.fixture(scope="module")
def sea_ground():
    import ground as G
    import terrain as T
    try:
        g = G.Ground()
    except (T.TerrainUnavailable, FileNotFoundError, OSError) as e:
        pytest.skip("NOT_EXECUTED: the canonical heightmap is unavailable (%s); set COBBLERS_SOURCE_ROOT" % e)
    for settlement in C3["ground_overlays"]:
        g = G.for_settlement(settlement, base=g)
    return g


def _line(a, b):
    (x0, z0), (x1, z1) = a, b
    n = int(max(abs(x1 - x0), abs(z1 - z0)))
    out = []
    for i in range(n + 1):
        c = (int(round(x0 + (x1 - x0) * i / n)), int(round(z0 + (z1 - z0) * i / n)))
        if not out or out[-1] != c:
            out.append(c)
    return out, math.dist(a, b) / max(1, len(out) - 1)


def _crossing(g, a, b, sea):
    """The water depth of every cell from shore to shore (the rest cells at either end trimmed), the step, and whether
    each end stands on land or wading water."""
    cells, step = _line(a, b)
    depth = [sea - g(x, z) for x, z in cells]
    wet = [i for i, d in enumerate(depth) if d > 1]
    assert wet, "no swimming on the line %s -> %s" % (a, b)
    return depth[wet[0]:wet[-1] + 1], step, {"from": depth[0] <= 1, "to": depth[-1] <= 1}


def _swim_walk(depths, step, qual, fns=None):
    """Walk the depths at SPEED with the generated surface/tick (tests/test_surface_exhaustion.py's model: one sample
    every sample_ticks, the water column under the feet from the depth, head above water); the hits, in blocks."""
    import test_surface_exhaustion as TSE
    s = TSE._sim(fns=fns)
    for k, v in (("bo.sub", 0), ("bo.deep", 0), ("bo.qual", qual), ("bo.fat", 0), ("bo.fwarn", 0)):
        s.set("@s", k, v)
    pos, hits, total = 0.0, [], len(depths) * step
    per = SURFACE["sample_ticks"]
    while pos < total:
        pos += SPEED * per / 20
        d = depths[min(len(depths) - 1, int(pos / step))]
        # land; one block of water is wading (on the bottom, head out); else swimming over d blocks of water
        s.state.update(water=TSE.LAND if d <= 0 else TSE.column(d), ground=d <= 1, riding=False)
        s.calls.clear()
        s.call("surface/tick")
        if any(c[0] == "water/pulse" for c in s.calls):
            hits.append(round(pos))
    assert not s.missing, s.missing
    return hits


def _outcome(hits):
    return "no hit" if not hits else ("hit" if len(hits) < 2 else "knocked out")


# Without it a change to the swim-fatigue constants (or to surface/tick) opens a strait the ferry is the only way across
# (WATER_BUILD_PLAN.md 11.2: the ferry is a gate on every line but the Relic row, at every stage, by swimming), or
# closes the Relic row the plan keeps swimmable from Pallet's beach, and nobody notices until a player swims it.
@pytest.mark.slow
@pytest.mark.parametrize("crossing", _params("C3", [(c["id"], (c,)) for c in C3["crossings"]]))
def test_contract_c3_the_ferrys_gated_straits_stay_unswimmable_and_the_relic_row_stays_swimmable(crossing, sea_ground):
    sea = int(_load("world.json")["vertical"]["sea_level"])
    depths, step, dry = _crossing(sea_ground, tuple(crossing["from"]), tuple(crossing["to"]), sea)
    for end in crossing["dry_ends"]:
        assert dry[end], "%s: its %s end is no longer land or wading water: re-measure it" % (crossing["id"], end)
    runs, cur = [], 0
    for d in depths:
        cur = 0 if d <= 1 else cur + 1
        runs.append(cur)
    swim = max(runs) * step
    # the line is still the one the plan measured (its "Swim" column), within a tenth
    assert abs(swim - crossing["doc_swim"]) <= 0.1 * crossing["doc_swim"], (crossing["id"], round(swim))
    for who, qual in (("unaided", 0), ("trained", 1)):
        if who not in crossing:
            continue
        got = _outcome(_swim_walk(depths, step, qual))
        want = crossing[who]
        ok = got == "knocked out" if want == "knocked out" else got in ("no hit",)
        assert ok, "%s, %s: the plan says %s, the pack now gives %s" % (crossing["id"], who, want, got)


# Without it the walk above could hold a gate shut whatever the constants say: a pack built with deep water tiring no
# faster than shallow (gain_deep_per_tick = gain_shallow_per_tick) must let an unaided swimmer across the Sunset strait,
# so a gentler constant is exactly what the contract catches.
@pytest.mark.slow
def test_harness_a_gentler_deep_rate_opens_the_sunset_strait(sea_ground):
    line = next(c for c in C3["crossings"] if c["id"] == "sunset_strait")
    sea = int(_load("world.json")["vertical"]["sea_level"])
    depths, step, _dry = _crossing(sea_ground, tuple(line["from"]), tuple(line["to"]), sea)
    assert _outcome(_swim_walk(depths, step, 0)) == "knocked out"
    cfg = copy.deepcopy(BLACKOUT)
    cfg["surface"]["gain_deep_per_tick"] = cfg["surface"]["gain_shallow_per_tick"]
    gentle = TB.functions(TB.build(cfg))
    assert _outcome(_swim_walk(depths, step, 0, fns=gentle)) == "no hit"


# =================================================================================================================
# C4. No world pack places a spawn condition its place is not whitelisted for
# =================================================================================================================

C4 = CONTRACTS["C4"]
SPAWN_BLOCKS = set(_load("spawn_blocks.json")["blocks"])
POLICY = _load("spawn_block_policy.json")
PLACEMENTS = _load("placements.json")


def _base(block):
    return block.split("[")[0].split("{")[0]


def _command_blocks(cmds):
    out = set()
    for c in cmds:
        t = c.split()
        if t and t[0] == "setblock" and len(t) > 4:
            out.add(_base(t[4]))
        elif t and t[0] == "fill" and len(t) > 7:
            out.add(_base(t[7]))
    return out


def _named_ids(obj, namespaces=None, skip=()):
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in skip:
                out |= _named_ids(v, namespaces, skip)
    elif isinstance(obj, list):
        for v in obj:
            out |= _named_ids(v, namespaces, skip)
    elif isinstance(obj, str) and re.fullmatch(r"[a-z0-9_]+:[a-z0-9_/]+(\[.*\])?", obj):
        if namespaces is None or obj.split(":")[0] in namespaces:
            out.add(_base(obj))
    return out


def _source_blocks():
    """{source id: (the blocks it may place, the place ids a policy entry's scope must name to cover it)}: each block
    generator's allowed or named list, as its own tests and audits read it."""
    td = _load("town_dressing.json")
    rm = _load("rift_mines.json")
    rd = _load("rift_deep.json")
    dc = _load("deep_city.json")
    vr = _load("vr_caves.json")
    rem = _load("rematerial.json")
    out = {
        "town_dressing": (set(td["blocks"]["ids"]), []),
        "rift_mines": (_named_ids(rm, ("minecraft", "mega_showdown"), skip=("flag",)), []),
        "rift_deep": ({rd[sec][k] for sec in ("tread", "light", "shell", "restore", "lifts")
                       for k in ("block", "fallback", "edge", "edge_fallback") if k in rd.get(sec, {})}, []),
        "deep_city": (_named_ids([dc["materials"], dc["lights"]["emitters"], dc["districts"], dc["plaza"]]), []),
        "vr_caves": ({_base(b) for z in vr["zones"] for b in list(z["palette"].values())
                      + list((z.get("fallbacks") or {}).values())}, ["vr_caves"]),
        "rematerial": ({_base(b) for s in rem["house_sets"].values() for b in s["map"].values()}, []),
    }
    for p in PLACEMENTS["placements"]:
        if p.get("kind") == "earthwork" and p.get("commands"):
            key = "earthworks:%s" % p["settlement"]
            blocks, ids = out.get(key, (set(), [p["settlement"]]))
            out[key] = (blocks | _command_blocks(p["commands"]), ids + [p["id"]])
    return out


SOURCES = _source_blocks()


def _whitelisted(block, ids):
    return any(block in w["blocks"] and any(i in (w.get("scope") or "") for i in ids) for w in POLICY["whitelist"])


# Without it a world pack decides encounters wherever it builds with nobody deciding it (TOWN_CENTERS.md rule 7:
# spawn-neutral by default; data/spawn_blocks.json): each generator checks its own list, differently, and a block
# allowed in one place under a whitelist written for another passes. One rule over every generator's list: a spawn
# condition is placed only where a data/spawn_block_policy.json entry whose scope names that place allows it.
@pytest.mark.parametrize("source", _params("C4", [(k, (k,)) for k in sorted(SOURCES)]))
def test_contract_c4_no_generated_world_pack_places_a_spawn_condition_its_place_is_not_whitelisted_for(source):
    blocks, ids = SOURCES[source]
    assert blocks, "%s names no block: the check would pass on nothing" % source
    bad = sorted(b for b in blocks & SPAWN_BLOCKS if not _whitelisted(b, ids))
    assert not bad, "%s places %s, each a spawn condition (data/spawn_blocks.json), and no policy entry is scoped to %s" % (
        source, bad, ids)


# Without it the scope rule could pass anything: the bell whitelisted for "Brock's town meeting point" covers no
# generator here, and water is allowed to the sea town and Victory Road's caves (their ids are in the scopes) but not
# to the town dressing or the Deep's city.
def test_harness_a_whitelist_covers_only_the_place_its_scope_names():
    assert "minecraft:bell" in SPAWN_BLOCKS and "minecraft:water" in SPAWN_BLOCKS
    assert not _whitelisted("minecraft:bell", ["town_dressing"]) and not _whitelisted("minecraft:bell", [])
    assert _whitelisted("minecraft:water", ["sea_town"]) and _whitelisted("minecraft:water", ["vr_caves"])
    assert not _whitelisted("minecraft:water", ["town_dressing", "deep_city"])


# Without it the contract above goes blind to a new block generator: every tool that reads data/spawn_blocks.json is
# either one of the contract's sources, a checker of one, or listed as not covered with the reason (C4 "tools").
def test_contract_c4_every_tool_that_reads_the_spawn_conditions_is_accounted_for():
    def reads(text):
        return "spawn_blocks.json" in text or re.search(r"^\s*(import spawn_blocks|from spawn_blocks import)", text, re.M)
    readers = sorted(p.name for p in (ROOT / "tools").glob("*.py") if reads(p.read_text(encoding="utf-8", errors="replace")))
    listed = C4["tools"]
    assert sorted(listed) == readers, sorted(set(listed) ^ set(readers))
    for tool, what in listed.items():
        kind, _, rest = what.partition(":")
        assert kind in ("source", "checker", "not covered") and rest.strip(), (tool, what)
        if kind == "source":
            sid = rest.split()[0]
            assert any(s == sid or s.startswith(sid + ":") for s in SOURCES), (tool, what)


# Without it a built pack (whatever tool wrote it) places a spawn condition no policy entry names at all. Runs on the
# packs present under build/datapacks; a fresh checkout has none, and the test says so.
def test_contract_c4_built_world_packs_place_no_spawn_condition_the_policy_never_allows():
    packs = ROOT / "build" / "datapacks"
    fns = sorted(packs.glob("*/data/*/function/**/*.mcfunction")) if packs.is_dir() else []
    if not fns:
        pytest.skip("NOT_EXECUTED: no built packs under build/datapacks (run the generators or reapply.py prepare)")
    allowed = {b for w in POLICY["whitelist"] for b in w["blocks"]}
    bad = {}
    for f in fns:
        placed = _command_blocks(f.read_text(encoding="utf-8", errors="replace").splitlines())
        for b in sorted((placed & SPAWN_BLOCKS) - allowed):
            bad.setdefault(f.relative_to(packs).parts[0], set()).add(b)
    assert not bad, {k: sorted(v) for k, v in bad.items()}


# =================================================================================================================
# C5. Recovery claims live only in the ledger storage, and the carry takes exactly that
# =================================================================================================================

def _carried_storage_namespaces():
    import fnmatch
    import carry_players as C
    globs = [g for _c, g, _r in C.WORLD_WIDE]
    return globs, lambda ns: any(fnmatch.fnmatch("data/command_storage_%s.dat" % ns, g) for g in globs)


# Without it an open claim is lost at a re-export (DEATH_AND_WIPE.md "Persistence, restart and re-export": the recovery
# store is in the carry manifest; claims are recreated when their chunks load): claim state written to a storage the
# carry does not take (the shared cobblers storage, which holds the re-apply's own progress and must never be carried),
# or a claim that no longer resolves in the carried world. A claim is made with the pack, the world is "re-exported"
# keeping only what tools/carry_players.py carries (its command storage files and the scoreboard), the new world loads
# the pack, maintenance rebuilds the guardian from the ledger, and beating it pays the owner back.
def test_contract_c5_a_claim_made_before_a_reexport_is_rebuilt_and_paid_after_it():
    import test_blackout_recovery_pid as RP
    globs, carried = _carried_storage_namespaces()
    ledger_ns = TB.LEDGER.split(":", 1)[0]
    assert carried(ledger_ns) and not carried(NS), globs
    assert "data/scoreboard.dat" in globs
    # every storage path that holds claim state is the ledger's
    stray = []
    for name, lines in TB.FNS.items():
        for l in lines:
            if l.startswith("#"):
                continue
            for m in re.finditer(r"\bstorage ([a-z0-9_.-]+):([a-z0-9_/.-]+) (\S+)", TB.MACRO_REF.sub("1", l.lstrip("$"))):
                root = re.split(r"[.\[{]", m.group(3))[0]
                if root in ("claims", "names", "pending") and "%s:%s" % (m.group(1), m.group(2)) != TB.LEDGER:
                    stray.append((name, m.group(0)))
    assert not stray, stray[:5]

    old = RP._commit()
    assert len(RP.ledger(old)["claims"]) == 1
    new = N.NbtSim(query=RP.strict_query(), world=lambda kind, toks: kind == "loaded",
                   entity=lambda sel, path: RP.P1 if (sel, path) == ("@s", "UUID") else None)
    old.nbt.setdefault("%s:reapply" % NS, {})["progress"] = "R9"      # a stand-in for the shared cobblers storage: never carried
    new.nbt = {sid: copy.deepcopy(v) for sid, v in old.nbt.items() if carried(sid.split(":", 1)[0])}
    assert sorted(new.nbt) == [TB.LEDGER], sorted(new.nbt)
    new.score = dict(old.score)                           # data/scoreboard.dat is carried
    for f in TB.load_functions():
        new.call(f)
    assert [c["state"] for c in RP.ledger(new)["claims"]] == ["open"], RP.ledger(new).get("claims")
    new.call("recovery/maintain")
    new.call("recovery/maintain")
    assert [c[0] for c in new.calls].count("recovery/rebuild") == 1, [c[0] for c in new.calls][-8:]
    assert "spawnpokemonat ~ ~ ~ cobblemon:ursaring level=60" in " ".join(new.log), new.log[-5:]
    new.calls.clear()
    new.log.clear()
    new.command('function %s:recovery/resolve_pid {pid:"%s",resolver:"%s"}' % (NS, RP.GUARD_ID, RP.P1_ID))
    assert sorted((i, n) for i, n, _o in RP._drops(new)) == sorted((i["id"], i["count"]) for i in RP.ITEMS), new.log


# =================================================================================================================
# C6. Every gate's ward keeps its plug out of a survival player's reach
# =================================================================================================================

def _gates():
    """(data file, the gate object) for every object in data/*.json with a plug and a ward margin."""
    out = []

    def walk(o, f):
        if isinstance(o, dict):
            if "plug" in o and "ward_margin" in o:
                out.append((f, o))
            for v in o.values():
                walk(v, f)
        elif isinstance(o, list):
            for v in o:
                walk(v, f)
    for p in sorted((ROOT / "data").glob("*.json")):
        walk(json.loads(p.read_text(encoding="utf-8")), p.name)
    return out


def _rift_mines_ward(gate):
    import rift_mines as RM
    spec = _load("rift_mines.json")
    spec["mine"]["gate"] = gate
    files, _fn = RM.gate_files(types.SimpleNamespace(spec=spec), [{"min": [0, 0, 0], "max": [1, 1, 1]}])
    adv = files["advancement/%s/gate_ward.json" % RM.FOLDER]
    (crit,) = adv["criteria"].values()
    (cond,) = crit["conditions"]["player"]
    return cond["predicate"]["location"]["position"]


WARD_BUILDERS = {"rift_mines.json": _rift_mines_ward}


def _cells(b):
    return [(x, y, z) for x in range(b[0], b[3] + 1) for y in range(b[1], b[4] + 1) for z in range(b[2], b[5] + 1)]


# Without it a gate can be dug round or broken by a survival player standing just outside its ward (the owner,
# 2026-09-27: "i can mine around the door"): the ward is tested at the feet, but the eyes are 1.62 higher and reach 4.5
# blocks. Every gate the data holds (any object with a plug and a ward_margin) must have a ward builder here, and from
# every feet position just outside the generated ward no block of its plug or grille is in reach.
@pytest.mark.parametrize("where,gate", _params("C6", [(f, (f, g)) for f, g in _gates()]))
def test_contract_c6_no_player_outside_a_gates_ward_can_reach_its_plug(where, gate):
    assert where in WARD_BUILDERS, "a gate in data/%s has no ward builder in this contract" % where
    reached = _reach_from_outside(where, gate)
    assert not reached, sorted(reached)[:3]


# Without it the reach check could pass whatever the ward: the margin of 4 the gate first shipped with (c9cb850) must be
# reported as reachable, as the test author found it.
def test_harness_the_reach_check_catches_the_first_ward_margin():
    (where, gate), = _gates()
    old = dict(gate, ward_margin=4)
    assert _reach_from_outside(where, old)


def _reach_from_outside(where, gate):
    """(distance, feet) for every feet position just outside the generated ward that reaches the plug or grille."""
    pos = WARD_BUILDERS[where](gate)
    protect = _cells(gate["plug"])
    if "grille" in gate:
        g = gate["grille"]
        protect += [(g["x"], y, z) for y in range(g["y"][0], g["y"][1] + 1) for z in range(g["z"][0], g["z"][1] + 1)]

    def dist(eye, b):
        return math.sqrt(sum(max(b[i] - eye[i], 0.0, eye[i] - (b[i] + 1)) ** 2 for i in range(3)))

    lattice = {a: [pos[a]["min"] + k for k in range(int(pos[a]["max"] - pos[a]["min"]) + 1)] for a in "xyz"}
    reached = []
    for a in "xyz":
        for out in (pos[a]["min"] - 1e-3, pos[a]["max"] + 1e-3):
            for p in itertools.product(*[lattice[b] if b != a else [out] for b in "xyz"]):
                eye = (p[0], p[1] + EYE, p[2])
                d = min(dist(eye, b) for b in protect)
                if d <= REACH:
                    reached.append((round(d, 2), p))
    return reached


# Without it the contract above passes on nothing if the gate's keys are renamed.
def test_contract_c6_the_gate_list_is_not_empty():
    assert [f for f, _g in _gates()] == ["rift_mines.json"], [f for f, _g in _gates()]


# =================================================================================================================
# C8. A gate opens on a flag the progression pack actually grants
# =================================================================================================================

# Without it the Rift mine's gate waits on an advancement nothing grants (a renamed flag, a flag the progression pack
# no longer writes, or one only an impossible trigger sets), so the deep galleries never open; or its message names a
# badge the flag is not (RIFT_ZONES.md and data/rift_mines.json flag: "the fifth badge, Koga's").
def test_contract_c8_the_rift_mine_gate_opens_on_an_advancement_the_progression_pack_grants():
    import progression_pack as PP
    import rift_mines as RM
    spec = _load("rift_mines.json")
    files, fn = RM.gate_files(types.SimpleNamespace(spec=spec), [{"min": [0, 0, 0], "max": [1, 1, 1]}])
    named = set()
    for lines in fn.values():
        for l in lines:
            named |= set(re.findall(r"advancements=\{([a-z0-9_]+:[a-z0-9_/]+)=", l))
    assert named == {spec["flag"]["advancement"]}, named
    prog = PP.files(PP.plan(PP.load(ROOT / "data" / "progression.json"), None, PLACEMENTS))
    for adv in named:
        ns, path = adv.split(":", 1)
        key = "data/%s/advancement/%s.json" % (ns, path)
        assert key in prog, "%s is not an advancement tools/progression_pack.py writes" % adv
        crit = json.loads(prog[key])["criteria"]
        assert all(c["trigger"] != "minecraft:impossible" for c in crit.values()), crit
    assert spec["flag"]["advancement"] == "cobblers:flag/gym%d_cleared" % spec["flag"]["badge"]


# =================================================================================================================
# The registry itself
# =================================================================================================================

def _defs(path):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


# Without it a contract points at a test that was renamed or deleted, and the registry claims a guarantee nothing checks.
def test_every_contract_names_existing_tests():
    for c in REGISTRY["contracts"]:
        assert c["tests"], c["id"]
        for t in c["tests"]:
            path, _, name = t.partition("::")
            assert (ROOT / path).is_file(), (c["id"], t)
            assert name in _defs(path), (c["id"], t)


# Without it a contract test is written here and never registered (no owner, no consumer, no citation), or registered
# under a name that does not say it is one.
def test_every_contract_test_here_is_registered():
    here = {n for n in _defs(THIS) if n.startswith("test_contract_")}
    registered = {t.split("::")[1] for c in REGISTRY["contracts"] for t in c["tests"] if t.startswith(THIS + "::")}
    assert here == registered, sorted(here ^ registered)


# Without it a "contract" is one system's internal rule, which its own suite already owns: a contract crosses a
# boundary, so it names at least one consuming system other than its owner, and every system it names is declared.
def test_every_contract_has_a_consumer_other_than_its_owner():
    systems = REGISTRY["systems"]
    ids = [c["id"] for c in REGISTRY["contracts"]]
    assert len(ids) == len(set(ids)), ids
    for c in REGISTRY["contracts"]:
        assert c["owner"] in systems, (c["id"], c["owner"])
        assert all(s in systems for s in c["consumers"]), (c["id"], c["consumers"])
        assert set(c["consumers"]) - {c["owner"]}, c["id"]
        assert c["statement"].strip() and c["stated_in"], c["id"]
    for sid, s in systems.items():
        for p in s["paths"]:
            assert (ROOT / p).exists(), (sid, p)


# Without it a citation rots: the document moves on, the registry still points at a line that no longer says it.
def test_every_citation_still_says_what_the_registry_quotes():
    bad = []
    for c in REGISTRY["contracts"]:
        for cite in c["stated_in"]:
            path, _, line = cite["at"].rpartition(":")
            lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
            n = int(line)
            if not (1 <= n <= len(lines)) or cite["quote"] not in lines[n - 1]:
                bad.append((c["id"], cite["at"], cite["quote"]))
    assert not bad, bad


# Without it a contract recorded as failing today is not marked (the suite goes red and stays red, and people learn to
# ignore it), or a mark outlives its registry entry: every fails_today pattern matches a case of the contract's tests
# here, and every marked case is one the registry records.
def test_every_failing_contract_is_recorded_and_marked_strict():
    marked = {}
    for name, fn in [(n, globals()[n]) for n in _defs(THIS) if n.startswith("test_contract_")]:
        for mark in getattr(fn, "pytestmark", []):
            if mark.name == "xfail":
                raise AssertionError("%s: mark failing cases through the registry (_params), not the function" % name)
            if mark.name == "parametrize":
                for ps in mark.args[1]:
                    if any(m.name == "xfail" for m in getattr(ps, "marks", ())):
                        assert all(m.kwargs.get("strict") for m in ps.marks if m.name == "xfail"), (name, ps.id)
                        marked.setdefault(name, set()).add(ps.id)
    for c in REGISTRY["contracts"]:
        here = [t.split("::")[1] for t in c["tests"] if t.startswith(THIS + "::")]
        cases = set().union(*[marked.get(n, set()) for n in here]) if here else set()
        for pattern in c.get("fails_today", {}).get("cases", {}):
            assert any(fnmatch.fnmatch(i, pattern) for i in cases), (c["id"], pattern, sorted(cases))
        if cases:
            assert c.get("fails_today"), (c["id"], sorted(cases))
