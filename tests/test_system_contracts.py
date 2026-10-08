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
    the ferry crossings, by swimming (C3) and by boat (C11: the pack main() writes, with its boat rows from
    tools/open_water.py), skipped, with the reason, when the heightmap is unavailable.
  - tests/gulch_sim.py's world model (executors, selectors, blocks, game time) for the gulch keeper's Megas (C12), and
    the gulch's generated zone advancement and block lines against Victory Road's data (C13).

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
import inspect
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
    """Every block a fill or setblock places, bare or under `execute ... run` (a guarded write still places it: the
    caves' ore variants and the lake life's plants are all `execute if block ... run setblock|fill`)."""
    out = set()
    for c in cmds:
        if c.startswith("execute ") and " run " in c:
            c = c.rsplit(" run ", 1)[1]
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
    gm = _load("gulch_mine.json")
    # a face's `resettable` list is the restore's filter (what `fill ... replace #tag` may overwrite), never a block
    # placed; the Cutters' offers and the floor's gift are items
    out = {
        "town_dressing": (set(td["blocks"]["ids"]), []),
        "rift_mines": (_named_ids(rm, ("minecraft", "mega_showdown"), skip=("flag", "resettable")), []),
        "gulch_mine": (_named_ids(gm, ("minecraft", "mega_showdown"), skip=("flag", "resettable", "cutters", "floor")), []),
        "rift_deep": ({rd[sec][k] for sec in ("tread", "light", "shell", "restore", "lifts")
                       for k in ("block", "fallback", "edge", "edge_fallback") if k in rd.get(sec, {})}, []),
        "deep_city": (_named_ids([dc["materials"], dc["lights"]["emitters"], dc["districts"], dc["plaza"]]), []),
        "vr_caves": ({_base(b) for z in vr["zones"] for b in list(z["palette"].values())
                      + list((z.get("fallbacks") or {}).values())}, ["vr_caves"]),
        "rematerial": ({_base(b) for s in rem["house_sets"].values() for b in s["map"].values()}, []),
    }
    # the three wayside places of 2026-10-03: each generator refuses any block outside its record's blocks.ids, so the
    # list is the place's whole palette; a policy entry must name the place itself to cover one of them
    # the Scorchbone Dig (tools/fossil_dig.py, 2026-10-05) loads its record the same way (wayside_kit.load_record)
    for place in ("challengers_cairn", "dry_cistern", "survey_benchmark", "fossil_dig"):
        out[place] = (set(_load("%s.json" % place)["blocks"]["ids"]), [place])
    # the refillable mining caves (tools/mining_caves.py, 2026-10-10): every block the record names that a cave
    # places (its yields' ores and hosts, each cave's wall, shell, floor, stair and timber); `restore` is the refill's
    # filter (what `fill ... replace #tag` may overwrite), never a block placed. A policy entry must name mining_caves
    mc = _load("mining_caves.json")
    out["mining_caves"] = (_named_ids([mc["yields"], [{k: c[k] for k in ("wall", "shell", "floor", "stair", "timber")}
                                                      for c in mc["caves"]]], ("minecraft",)), ["mining_caves"])
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


# the built packs judged: build/datapacks, or COBBLERS_BUILT_DATAPACKS (another checkout's build/datapacks, read only)
BUILT_PACKS = Path(os.environ.get("COBBLERS_BUILT_DATAPACKS") or ROOT / "build" / "datapacks")


def _built_pack_cases():
    """One case per pack under BUILT_PACKS that ships functions (a pack with none places nothing this way), plus every
    pack C4's fails_today names (so its strict mark exists in a checkout that has not built it; that case skips)."""
    present = {p.name for p in BUILT_PACKS.iterdir()
               if p.is_dir() and next(p.glob("data/*/function/**/*.mcfunction"), None)} if BUILT_PACKS.is_dir() else set()
    recorded = {pat.split(":", 1)[1] for pat in (C4.get("fails_today") or {}).get("cases", {}) if pat.startswith("built:")}
    return [("built:%s" % p, (p,)) for p in sorted(present | recorded)] or [("built:none", (None,))]


# Without it a built pack (whatever tool wrote it) places a spawn condition no policy entry names at all. One case per
# pack present under build/datapacks; a fresh checkout has none, and the test says so. A pack recorded in C4's
# fails_today is strict xfail: the day its block gets a policy entry or leaves the pack, the case passes and fails.
@pytest.mark.parametrize("pack", _params("C4", _built_pack_cases()))
def test_contract_c4_built_world_packs_place_no_spawn_condition_the_policy_never_allows(pack):
    fns = sorted((BUILT_PACKS / pack).glob("data/*/function/**/*.mcfunction")) if pack else []
    if not fns:
        pytest.skip("NOT_EXECUTED: %s has no built functions under %s (run the generators or reapply.py prepare)"
                    % (pack or "no pack", BUILT_PACKS))
    allowed = {b for w in POLICY["whitelist"] for b in w["blocks"]}
    bad = {}
    for f in fns:
        placed = _command_blocks(f.read_text(encoding="utf-8", errors="replace").splitlines())
        for b in sorted((placed & SPAWN_BLOCKS) - allowed):
            bad.setdefault(b, []).append(f.relative_to(BUILT_PACKS / pack).as_posix())
    assert not bad, {b: (len(v), v[0]) for b, v in bad.items()}


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
# C6. Every built ward keeps what it guards out of a survival player's reach
# =================================================================================================================

def _wards():
    """("file:path", the object) for every object in data/*.json with a ward_margin, outside a retired section."""
    out = []

    def walk(o, f, path):
        if isinstance(o, dict):
            if "ward_margin" in o:
                out.append(("%s:%s" % (f, ".".join(path)), o))
            for k, v in o.items():
                if k != "retired_gated_section":
                    walk(v, f, path + [k])
        elif isinstance(o, list):
            for v in o:
                walk(v, f, path)
    for p in sorted((ROOT / "data").glob("*.json")):
        walk(json.loads(p.read_text(encoding="utf-8")), p.name, [])
    return out


def _position(adv):
    (crit,) = adv["criteria"].values()
    (cond,) = crit["conditions"]["player"]
    return cond["predicate"]["location"]["position"]


def _tease_ward(tease):
    """(the generated ward's position ranges, the cells it guards: the grille and the crystal's face box)."""
    import rift_mines as RM
    spec = _load("rift_mines.json")
    spec["mine"]["tease"] = tease
    files, _fn = RM.tease_files(types.SimpleNamespace(spec=spec))
    g = tease["grille"]
    guard = [(x, y, g["z"]) for x in range(g["x"][0], g["x"][1] + 1) for y in range(g["y"][0], g["y"][1] + 1)]
    return _position(files["advancement/%s/tease_ward.json" % RM.FOLDER]), guard + _cells(tease["face"]["box"])


_GULCH_MODEL = []


def _gulch_ward(gate):
    """The gulch gate's generated ward, and the plug as the model builds it (every rockfall block in the plug's columns
    up to its top) with the grille. Needs the heightmap (the plug stands on the ground)."""
    import gulch_mine as GM
    import terrain as T
    if not _GULCH_MODEL:
        try:
            _GULCH_MODEL.append(GM.model()[0])
        except (T.TerrainUnavailable, FileNotFoundError, OSError) as e:
            pytest.skip("NOT_EXECUTED: the gulch's plug stands on the canonical heightmap, unavailable (%s)" % e)
    m = _GULCH_MODEL[0]
    spec = copy.deepcopy(m.spec)
    spec["gate"] = gate
    files, _fn = GM.gate_files(types.SimpleNamespace(spec=spec), [(0, 0, 0, 0)])
    pl, g = gate["plug"], gate["grille"]
    cols = {c for c, j in GM.band_columns(gate["band"]).items() if abs(j) <= pl["half_j"]
            and not (c[0] > pl["max_x"] and pl["trim_z"][0] <= c[1] <= pl["trim_z"][1])}
    rubble = set(spec["palette"]["rubble"])
    plug = [c for c, b in m.surf.items() if (c[0], c[2]) in cols and b.split("[")[0] in rubble and c[1] <= pl["top_y"]]
    assert len(plug) > 100, len(plug)
    grille = [(g["x"], y, z) for y in range(g["y"][0], g["y"][1] + 1) for z in range(g["z"][0], g["z"][1] + 1)]
    return _position(files["advancement/gulch_mine/gate_ward.json"]), plug + grille


def _gulch_faces_ward(faces):
    """[(each face's generated ward, its box)]: the per-tick Mining Fatigue selector of the keeper's tick (SOUTHERN_RIFT_
    MEGA.md 13: the faces are scenery, warded for good), read as the block cuboid the player's feet are tested in."""
    import gulch_mine as GM
    spec = _load("gulch_mine.json")
    spec["faces"] = faces
    for s in spec["megas"]["slots"]:
        s["_anchor"] = [s["anchor"][0], 47, s["anchor"][1]]
    tick = GM.keeper_files(types.SimpleNamespace(spec=spec))["tick"]
    out = []
    for f in spec["mine"]["faces"]:
        b = f["box"]
        hits = []
        for ln in tick:
            m = re.match(r"execute as @a\[x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+),.*mining_fatigue", ln)
            if m:
                x, y, z, dx, dy, dz = (int(v) for v in m.groups())
                if x <= b[0] and b[3] <= x + dx and y <= b[1] and b[4] <= y + dy and z <= b[2] and b[5] <= z + dz:
                    hits.append({"x": {"min": x, "max": x + dx + 1}, "y": {"min": y, "max": y + dy + 1},
                                 "z": {"min": z, "max": z + dz + 1}})
        assert hits, "face %s has no ward in the tick" % f["id"]
        out.append((min(hits, key=lambda p: p["x"]["max"] - p["x"]["min"]), _cells(b)))
    return out


WARD_BUILDERS = {"rift_mines.json:mine.tease": _tease_ward, "gulch_mine.json:gate": _gulch_ward,
                 "gulch_mine.json:faces": _gulch_faces_ward}


def _cells(b):
    return [(x, y, z) for x in range(b[0], b[3] + 1) for y in range(b[1], b[4] + 1) for z in range(b[2], b[5] + 1)]


# Without it a guarded block can be dug by a survival player standing just outside its ward (the owner, 2026-09-27: "i
# can mine around the door"): the ward is tested at the feet, but the eyes are 1.62 higher and reach 4.5 blocks. Every
# built ward the data holds (any object with a ward_margin outside a retired section) must have a builder here, and from
# every feet position just outside the generated ward nothing it guards is in reach.
@pytest.mark.parametrize("where,ward", _params("C6", [(w, (w, o)) for w, o in _wards()]))
def test_contract_c6_no_player_outside_a_ward_can_reach_what_it_guards(where, ward):
    assert where in WARD_BUILDERS, "a ward at data/%s has no builder in this contract" % where
    built = WARD_BUILDERS[where](ward)
    for pos, guard in (built if isinstance(built, list) else [built]):
        reached = _reach_from_outside(pos, guard)
        assert not reached, sorted(reached)[:3]


# Without it the reach check could pass whatever the ward: the margin of 4 the spur's gate first shipped with (c9cb850)
# must be reported as reachable on the seam's ward too.
def test_harness_the_reach_check_catches_the_first_ward_margin():
    (tease,) = [o for w, o in _wards() if w == "rift_mines.json:mine.tease"]
    assert not _reach_from_outside(*_tease_ward(tease))
    assert _reach_from_outside(*_tease_ward(dict(tease, ward_margin=4)))


def _reach_from_outside(pos, protect):
    """(distance, feet) for every feet position just outside the generated ward that reaches a guarded block
    (tests/reach.py, shared with tests/test_gulch_mine.py; identical to the loop it replaced on every ward, 120 s -> 4 s)."""
    from reach import reach_from_outside
    return [(round(d, 2), p) for d, p in reach_from_outside(pos, protect, EYE, REACH)]


# Without it the contract above passes on nothing when a ward's keys are renamed, or still tests a retired one: the
# built wards are the gulch gate's, the gulch's crystal faces' (scenery warded for good, SOUTHERN_RIFT_MEGA.md 13) and
# the seam's (the spur's company gate is retired, 72f8ddb).
def test_contract_c6_the_ward_list_is_the_built_wards():
    assert sorted(w for w, _o in _wards()) == ["gulch_mine.json:faces", "gulch_mine.json:gate",
                                               "rift_mines.json:mine.tease"], _wards()


# =================================================================================================================
# C8. Every gate and ward opens on a flag the progression pack actually grants
# =================================================================================================================

# Without it the gulch's gate and zone check, or the seam's ward, wait on an advancement nothing grants (a renamed flag,
# a flag the progression pack no longer writes, or one only an impossible trigger sets), so the gulch never opens and
# the crystal never lifts; or the flag is not the badge its data names (the sixth, decisions 2 and 3).
def test_contract_c8_every_gate_and_ward_opens_on_an_advancement_the_progression_pack_grants():
    import gulch_mine as GM
    import progression_pack as PP
    import rift_mines as RM
    prog = PP.files(PP.plan(PP.load(ROOT / "data" / "progression.json"), None, PLACEMENTS))
    for name, fns in (("gulch_mine.json", GM.gate_files(types.SimpleNamespace(spec=_load("gulch_mine.json")),
                                                        [(0, 0, 0, 0)])[1]),
                      ("rift_mines.json", RM.tease_files(types.SimpleNamespace(spec=_load("rift_mines.json")))[1])):
        spec = _load(name)
        named = set()
        for lines in fns.values():
            for l in lines:
                named |= set(re.findall(r"advancements=\{([a-z0-9_]+:[a-z0-9_/]+)=", l))
        assert named == {spec["flag"]["advancement"]}, (name, named)
        for adv in named:
            ns, path = adv.split(":", 1)
            key = "data/%s/advancement/%s.json" % (ns, path)
            assert key in prog, "%s is not an advancement tools/progression_pack.py writes" % adv
            crit = json.loads(prog[key])["criteria"]
            assert all(c["trigger"] != "minecraft:impossible" for c in crit.values()), crit
        assert spec["flag"]["advancement"] == "cobblers:flag/gym%d_cleared" % spec["flag"]["badge"] == \
            "cobblers:flag/gym6_cleared", (name, spec["flag"])


# =================================================================================================================
# C11. Boats as shallows craft do not reopen a strait the ferry gates
# =================================================================================================================

C11 = CONTRACTS["C11"]


@pytest.fixture(scope="module")
def boat_pack(sea_ground, tmp_path_factory):
    """The blackout pack main() writes on the canonical heightmap (its boat rows), as {name: lines}, and its files."""
    import blackout_pack as BP
    out = tmp_path_factory.mktemp("boats") / "cobblers_blackout"
    assert BP.main(["--out", str(out)]) == 0
    files = {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8") for p in out.rglob("*") if p.is_file()}
    return files, TB.functions(files)


def _boat_walk(g, crossing, files, fns):
    """Walk the crossing's line at SPEED: in a boat wherever the generated boat/check lets a rider stay (the player
    carries boats and places one again at once, the worst case for the gate), swimming wherever it tips them, with the
    generated surface/tick for the fatigue. The hits, in blocks along the line."""
    import test_surface_exhaustion as TSE
    sea = int(_load("world.json")["vertical"]["sea_level"])
    cells, step = _line(tuple(crossing["from"]), tuple(crossing["to"]))
    depth = [sea - g(x, z) for x, z in cells]
    wet = [i for i, d in enumerate(depth) if d > 1]
    cells, depth = cells[wet[0]:wet[-1] + 1], depth[wet[0]:wet[-1] + 1]
    probe = TSE._sim(fns=fns, pack=files)
    s = TSE._sim(fns=fns, pack=files)
    for k, v in (("bo.sub", 0), ("bo.deep", 0), ("bo.qual", 0), ("bo.fat", 0), ("bo.fwarn", 0)):
        s.set("@s", k, v)
    per = SURFACE["sample_ticks"]
    pos, hits, total, tipped_at = 0.0, [], len(depth) * step, []
    while pos < total:
        pos += SPEED * per / 20
        i = min(len(depth) - 1, int(pos / step))
        (x, z), d = cells[i], depth[i]
        probe.log.clear()
        probe.state.update(x=x + 0.5, z=z + 0.5, riding=True, vehicle="minecraft:boat")
        probe.call("boat/check")
        rough = "ride @s dismount" in probe.log
        if rough:
            tipped_at.append(round(pos))
        boat = d > 1 and not rough
        s.state.update(x=x + 0.5, z=z + 0.5, water=TSE.LAND if d <= 0 else TSE.column(d), ground=d <= 1,
                       riding=boat, vehicle="minecraft:boat" if boat else None)
        s.calls.clear()
        s.call("surface/tick")
        if any(c[0] == "water/pulse" for c in s.calls):
            hits.append(round(pos))
    assert not s.missing and not probe.missing, (s.missing, probe.missing)
    return hits, tipped_at


# Without it option C does not do what the owner chose it for ("A boat should not defeat swimming, exhaustion and the
# ferry from day one", WATER_BUILD_PLAN.md:791): a player who boats every stretch the rule allows and swims only where it
# tips them crosses a strait the ferry gates. Walked on the canonical heightmap with the generated boat rows and the
# generated swim: the Sunset strait and the Northlight packet knock that player out; the Relic row (all shallows) and
# the Sound ferry (the Sound is sheltered water, WATER_PROPOSAL.md:276) are crossed. The line is the ferry contract's
# (C3); a coast-hugging detour is not walked.
@pytest.mark.slow
@pytest.mark.parametrize("crossing", _params("C11", [(c["id"], (c,)) for c in C11["crossings"]]))
def test_contract_c11_boats_do_not_reopen_a_strait_the_ferry_gates(crossing, sea_ground, boat_pack):
    line = next(c for c in C3["crossings"] if c["id"] == crossing["id"])
    hits, tipped = _boat_walk(sea_ground, line, *boat_pack)
    got = "knocked out" if len(hits) >= 2 else "crosses"
    assert got == crossing["boat"], "%s: the plan says a boater %s; the packs give %s (tipped at %s, hit at %s)" % (
        crossing["id"], crossing["boat"], got, tipped[:3], hits[:3])


# Without it the walk above could hold a gate shut whatever the boat rule says: with no rough water anywhere (every boat
# row emptied) a boater crosses the Northlight packet, the longest gated line.
@pytest.mark.slow
def test_harness_a_pack_without_boat_rows_lets_a_boat_cross_northlight(sea_ground, boat_pack):
    files, fns = boat_pack
    open_ = {k: v for k, v in fns.items()}
    for k in open_:
        if k.startswith("boat/r/"):
            open_[k] = []
    line = next(c for c in C3["crossings"] if c["id"] == "northlight_packet")
    hits, tipped = _boat_walk(sea_ground, line, files, open_)
    assert not tipped and not hits
    assert len(_boat_walk(sea_ground, line, *boat_pack)[1]) > 0


# =================================================================================================================
# C12. A gulch Mega that blacks a player out makes no claim
# =================================================================================================================

# Without it a player blacked out by a gulch Mega loses items into a claim and the Mega becomes a guardian (decision 9:
# "the blackout skips tagged Megas ... the mine's danger is the Megas, not a lost item"), because the tag the gulch's
# keeper gives its Megas and the tag the blackout exempts drift apart. The keeper's generated functions spawn a Mega on
# the gulch model; the blackout's generated loss runs with that Mega as the victor: no claim, the money still charged.
# An untagged wild victor still claims (the control).
#
# Since the open-air farms (data farms[], 2026-10-01) a gulch Mega can also PAY, so the same decision has a second
# half: a Mega that wins must not hand its raw stone to the player it beat. Three legs, all run rather than read:
#   1. the battle_fainted callback itself (the generated MoLang, on tests/nbt_sim.py's interpreter) calls the roll
#      only when the Pokemon that fainted is wild, so a player whose own Pokemon fainted never reaches it;
#   2. on the gulch world model, in each farm's approach box: a player who hurts a den's Mega and is then beaten by
#      it (they leave, the Mega lives on) is paid nothing, then or when the Mega dies later -- their hit has gone
#      stale against the keeper's gm.alive, and the Mega's UUID is still unspent;
#   3. a roll that does pay leaves one item whose Owner is the victor's own UUID (vanilla 1.21.1 ItemEntity: only
#      the owner picks it up), at the victor's feet, and nothing for the bystander standing beside them.
def test_contract_c12_a_gulch_mega_makes_no_claim_on_the_player_it_blacks_out():
    import gulch_mine as GM
    import gulch_sim as GS
    import test_blackout_recovery_pid as RP
    import test_gulch_mine as TG
    spec = _load("gulch_mine.json")
    w = TG._mine_world()
    TG._run(w, 500)
    megas = [e for e in w.entities if e["kind"] == "pokemon"]
    assert len(megas) == len(spec["megas"]["slots"]), megas
    for e in megas:
        s = RP._wild_loss({0: ("cobblemon:ultra_ball", 20)}, balance=1000, victor_tags=tuple(e["tags"]))
        assert not RP.fn_calls(s, "recovery/make") and not (RP.ledger(s).get("claims") or []), (e["tags"], s.calls)
        assert s.get("@s", "bo.lost") > 0, "the loss must still cost money"
    control = RP._wild_loss({0: ("cobblemon:ultra_ball", 20)}, balance=1000, victor_tags=())
    assert RP.fn_calls(control, "recovery/make") and len(RP.ledger(control)["claims"]) == 1

    # 1. the callback: only a wild fainter rolls
    callback = GM.callback_files(spec)
    if not callback:
        assert not spec.get("farms"), "farms are in the data but no battle_fainted callback was generated"
        pytest.skip("NOT_EXECUTED: no farm den in data/gulch_mine.json, so there is no drop roll to pay anyone")
    (src,) = callback.values()
    mol = N.Molang(src)
    beaten = mol.run(context={"pokemon": {"actor": {"is_wild": 0}, "pokemon": {"id": "PID"}},
                              "players": [{"player": {"uuid": "LOSER"}}]})
    assert beaten == [], ("a player's own Pokemon fainting reached the roll", beaten)
    won = mol.run(context={"pokemon": {"actor": {"is_wild": 1}, "pokemon": {"id": "PID"}},
                           "players": [{"player": {"uuid": "WINNER"}}, {"player": {"uuid": "SECOND"}}]})
    assert won == ['function cobblers:gulch_mine/drops/fainted {pid:"PID",who:"WINNER"}'], won

    for site, den_id in TG.FARM_DENS:
        # 2. hurt it, lose to it, walk away: no drop, then or later
        fspec, den, fw, (victim, bystander) = TG._farm_world(site, den_id)
        # the Mega field's ranges overlap (the owner, 2026-10-04), so a player in one den's approach box is in its
        # neighbours' too and their Megas come up as well: the den under test is the ONE Mega carrying its den tag, and
        # every other Mega in the world is another live den's own
        (mega,) = TG.den_megas(fw, den_id)
        pid = fw.sget(TG.STORE, 'dens[{id:"%s"}].pid' % den_id)
        assert pid, (site, "the den's Mega was never claimed: nothing to spend")
        mega["attacker"] = victim
        fw.tick(2)
        mega["attacker"] = None
        assert fw.sget(TG.STORE, 'dens[{id:"%s"}].who' % den_id) == [victim["nbt"]["UUID"]], site
        # beaten: the blackout puts them back at a Center. They are still ONLINE, which is what makes this a real
        # check -- drops/hitter_<den> runs `as @a`, so the only thing between them and the drop is that their hit
        # went stale against the keeper's gm.alive while the Mega lived on
        victim["pos"] = (4300.5, 89.0, 4850.5)
        TG._run(fw, 3 * TG.PASS)                         # the Mega lives: every pass refreshes gm.alive
        fw.rolls = [1] * 8                               # and every roll would pay, if one were taken
        fw.entities.remove(mega)                          # something else finishes it off
        TG._run(fw, 4 * TG.PASS)
        assert fw.alive(victim), site                     # they must still be selectable, or this proves nothing
        assert fw.sget(TG.STORE, 'dens[{id:"%s"}].pid' % den_id) == pid, (site, "the roll was taken")
        assert not [e for e in fw.entities if e["kind"] == "item"], (site, "the Mega paid the player it beat")

        # 3. a roll that pays, pays the victor and only the victor
        _s2, _d2, vw, (victor, onlooker) = TG._farm_world(site, den_id)
        vpid = vw.sget(TG.STORE, 'dens[{id:"%s"}].pid' % den_id)[0]
        vw.rolls = [1]
        vw.call("gulch_mine/drops/fainted", {"pid": vpid, "who": GS.uuid_text(victor["nbt"]["UUID"])})
        items = [e for e in vw.entities if e["kind"] == "item"]
        assert len(items) == 1, (site, items)
        assert items[0]["nbt"]["Owner"] == victor["nbt"]["UUID"], (site, items[0]["nbt"])
        assert items[0]["nbt"]["Owner"] != onlooker["nbt"]["UUID"] and items[0]["pos"] == victor["pos"], site


def entei_c12(files):
    """C12 for the Entei boss (a consumer since 2026-10-08): every Entei its generated keeper binds carries tags the
    generated blackout treats as exempt -- no item claim, no guardian (a guardian in a pocket slot freed the moment its
    victim leaves would hold their items where nobody can return), and the loss still costs money. The tags are read
    from the boss pack's GENERATED bind functions; the verdict is the generated blackout's, run on its simulator."""
    import test_blackout_recovery_pid as RP
    binds = {p: t for p, t in files.items() if re.search(r"/function/entei_boss/slot/s\d+/bind\.mcfunction$", p)}
    assert binds, "no bind function generated: nothing to check"
    for path, text in sorted(binds.items()):
        tags = tuple(m.group(1) for m in re.finditer(r"^tag @s add (\S+)$", text, re.M))
        s = RP._wild_loss({0: ("cobblemon:ultra_ball", 20)}, balance=1000, victor_tags=tags)
        assert not RP.fn_calls(s, "recovery/make") and not (RP.ledger(s).get("claims") or []), \
            ("a loss to the Entei makes a claim", path, tags)
        assert s.get("@s", "bo.lost") > 0, "the loss must still cost money"


# Without it the Entei boss's loss path breaks silently: a player beaten in their pocket slot would leave a claim and a
# guardian in a room that is freed (and its Entei killed) the moment they are sent out, so their items would be lost.
def test_contract_c12_the_entei_boss_makes_no_claim_on_the_player_it_blacks_out():
    import entei_boss as EB
    import test_blackout_recovery_pid as RP
    entei_c12(EB.build(EB.load()))
    control = RP._wild_loss({0: ("cobblemon:ultra_ball", 20)}, balance=1000, victor_tags=("cobblers.eb",))
    assert RP.fn_calls(control, "recovery/make"), "an Entei without the exempt tag must claim, or this proves nothing"


# =================================================================================================================
# C13. The gulch's zone and build stay off Victory Road
# =================================================================================================================

def _seg_dist(p, a, b):
    (px, pz), (ax, az), (bx, bz) = p, a, b
    L2 = (bx - ax) ** 2 + (bz - az) ** 2
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * (bx - ax) + (pz - az) * (bz - az)) / L2))
    return math.hypot(px - (ax + t * (bx - ax)), pz - (az + t * (bz - az)))


def _victory_road():
    """[(a, b, half width)] of Victory Road's corridor (data/routes.json), and [(a, b, reach)] of its caves' guide
    (data/vr_caves.json: the network grows within guide.band of the line; caverns add up to their largest radius)."""
    vr = next(r for r in _load("routes.json")["routes"] if r["id"] == "victory_road")
    pts = vr["corridor"]["polyline"]
    corridor = [((a["x"], a["z"]), (b["x"], b["z"]), max(a.get("corridor_width_blocks", vr["corridor"]["width_blocks"]),
                                                        b.get("corridor_width_blocks", vr["corridor"]["width_blocks"])) / 2)
                for a, b in zip(pts, pts[1:])]
    caves = _load("vr_caves.json")
    reach = caves["guide"]["band"] + max(caves["caverns"]["radius"])
    g = caves["guide"]["points"]
    return corridor, [(tuple(a), tuple(b), reach) for a, b in zip(g, g[1:])]


def _near_victory_road(cols):
    corridor, caves = _victory_road()
    bad = []
    x0, x1 = min(c[0] for c in cols), max(c[0] for c in cols)
    z0, z1 = min(c[1] for c in cols), max(c[1] for c in cols)
    for what, segs in (("corridor", corridor), ("caves", caves)):
        # only a segment whose box, grown by its reach, meets the columns' box can be near any of them
        near = [s for s in segs if min(s[0][0], s[1][0]) - s[2] <= x1 and max(s[0][0], s[1][0]) + s[2] >= x0
                and min(s[0][1], s[1][1]) - s[2] <= z1 and max(s[0][1], s[1][1]) + s[2] >= z0]
        for c in cols:
            if any(_seg_dist(c, a, b) <= r for a, b, r in near):
                bad.append((what, c))
                break
    return bad


# Without it the gulch's zone check turns back players on Victory Road (a box over its corridor, the old branch-mouth
# line's fault, SOUTHERN_RIFT.md finding 1), or the gulch's build writes into the road's corridor or its caves: the
# generated zone boxes' columns and every column the built pack writes lie outside Victory Road's corridor (half its
# width from its polyline) and its caves' band.
def test_contract_c13_the_gulch_zone_stays_off_victory_road():
    import gulch_mine as GM
    spec = _load("gulch_mine.json")
    files, _fn = GM.gate_files(types.SimpleNamespace(spec=spec), GM.zone_boxes(spec["zone"]["polygon"]))
    (crit,) = files["advancement/gulch_mine/zone.json"]["criteria"].values()
    (cond,) = crit["conditions"]["player"]
    cols = set()
    for t in cond["terms"]:
        p = t["predicate"]["location"]["position"]
        for x in range(int(p["x"]["min"]), int(p["x"]["max"])):
            for z in range(int(p["z"]["min"]), int(p["z"]["max"])):
                cols.add((x + 0.5, z + 0.5))
    assert len(cols) > 70000
    # the zone's edge only matters: a column inside the ring is further from the road than one on it
    edge = {c for c in cols if not all((c[0] + dx, c[1] + dz) in cols for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    assert not _near_victory_road(edge), _near_victory_road(edge)[:3]


@pytest.mark.slow
def test_contract_c13_the_gulch_build_writes_nothing_on_victory_road(tmp_path):
    import gulch_mine as GM
    import terrain as T
    try:
        m, _near, _tops = GM.model()
    except (T.TerrainUnavailable, FileNotFoundError, OSError) as e:
        pytest.skip("NOT_EXECUTED: the canonical heightmap is unavailable (%s)" % e)
    lns = GM.lines(m)
    cols = set()
    for body in lns.values():
        for l in body:
            t = l.split()
            cols.add((int(t[1]) + 0.5, int(t[3]) + 0.5))
    assert len(cols) > 10000
    assert not _near_victory_road(cols), _near_victory_road(cols)[:3]


# Without it the Victory Road checks above pass on nothing: the road's own corridor points are near it.
def test_harness_victory_roads_own_points_are_near_it():
    vr = next(r for r in _load("routes.json")["routes"] if r["id"] == "victory_road")
    p = vr["corridor"]["polyline"][len(vr["corridor"]["polyline"]) // 2]
    corridor, caves = _victory_road()
    assert any(_seg_dist((p["x"] + 40, p["z"]), a, b) <= r for a, b, r in corridor)
    g = _load("vr_caves.json")["guide"]["points"][3]
    assert any(_seg_dist((g[0] + 60, g[1]), a, b) <= r for a, b, r in caves)


# =================================================================================================================
# C14. No repeatable player action resets an accumulating gate clock
# =================================================================================================================

import test_gate_clocks as GC  # noqa: E402


# Without it a small timing detail defeats a whole gate again (the owner, 2026-09-27, after the tipped-rider finding:
# "anywhere a repeatable action resets a timer that is supposed to accumulate"): each clock a gate relies on, with each
# action a player can repeat at will, run on the generated packs by tests/test_gate_clocks.py's scenarios; the clock
# keeps accumulating (or stays put) through the repeats.
@pytest.mark.parametrize("case", _params("C14", [(k, (k,)) for k in sorted(GC.SCENARIOS)]))
def test_contract_c14_no_repeatable_player_action_resets_an_accumulating_gate_clock(case):
    GC.SCENARIOS[case]()


# =================================================================================================================
# C15. A blackout's money charge is flat, so saving is never punished
# =================================================================================================================

# the spread the registry's note_for_the_test_author asks for: under the charge, at it, just over it, the cap, two
# balances a saver might hold while planning a ladder rung, and the largest number a scoreboard score can hold
C15_BALANCES = (1, 199, 599, 600, 601, 3_000, 20_000, 250_000, 2 ** 31 - 1)
C15_PATH = ("blackout/charge", "blackout/charge_calc", "blackout/charge_apply")


def _c15_flat():
    """ceil(cap * percent / 100) re-derived from data/blackout.json with a different expression than the generator's
    (math.ceil of a true division, not its negated floor-divide), so the expectation is the data's, not the tool's."""
    m = BLACKOUT["money"]
    return math.ceil(m["cap"] * m["percent"] / 100)


def _c15_charge(fns, balance):
    """One blackout at `balance`, run on a generated pack: (bo.lost, the CobbleDollars removals, the functions the
    charge entry point reached)."""
    s = TB.Sim(fns=fns, query=lambda cmd, b=balance: b if cmd.startswith("cobbledollars query") else 0)
    for f in TB.load_functions():
        s.call(f)
    reached_from = len(s.calls)
    s.call("blackout/charge")
    return (s.get("@s", "bo.lost"), [l for l in s.log if l.startswith("cobbledollars remove")],
            [c[0] for c in s.calls[reached_from:]])


def _c15_const(fns):
    """The #charge constant the pack sets at load."""
    s = TB.Sim(fns=fns)
    for f in TB.load_functions():
        s.call(f)
    return s.get("#charge", "bo.cfg")


def _c15_contract(fns):
    """C15's owner half, asserted on whatever generator produced `fns`: the real pack, and a mutant's (below)."""
    flat = _c15_flat()
    for bal in C15_BALANCES:
        lost, removed, _ = _c15_charge(fns, bal)
        assert lost == min(bal, flat), "balance %d charged %d, not min(%d, %d)" % (bal, lost, bal, flat)
        assert 0 <= lost <= bal, (bal, lost)
        assert removed == ["cobbledollars remove @s %d" % lost], (bal, removed)
    # strictly flat: identical at any two balances above the charge, however far apart
    charged = {b: _c15_charge(fns, b)[0] for b in C15_BALANCES if b > flat}
    assert set(charged.values()) == {flat}, charged
    # 0 charges nothing and never reaches the calc; 1 charges exactly 1
    lost0, removed0, reached0 = _c15_charge(fns, 0)
    assert (lost0, removed0) == (0, []) and "blackout/charge_calc" not in reached0, (lost0, removed0, reached0)
    assert _c15_charge(fns, 1)[0] == 1, _c15_charge(fns, 1)
    # the hazard the 20%-of-balance rule carried: 2**31-1 times a percent wraps a 32-bit score negative, and
    # `cobbledollars remove @s -N` pays the player. The flat charge is positive and is the flat amount.
    big, removed_big, _ = _c15_charge(fns, 2 ** 31 - 1)
    assert big == flat > 0 and removed_big == ["cobbledollars remove @s %d" % flat], (big, removed_big)


def _c15_mutant(*subs):
    """charge_amount() and build() with the GENERATOR's own source rewritten in memory (CLAUDE.md "How to prove an
    audit is independent": mutate the generator, never the record). data/blackout.json is not touched."""
    src = inspect.getsource(TB.BP.charge_amount) + "\n\n" + inspect.getsource(TB.BP.build)
    for old, new in subs:
        assert old in src, "mutation target %r is no longer in the generator's source; re-aim it" % old
        src = src.replace(old, new, 1)
    ns = dict(TB.BP.__dict__)
    exec(compile(src, "<mutant blackout_pack>", "exec"), ns)  # noqa: S102 - deliberate, in-memory, test-only
    return TB.functions(ns["build"](copy.deepcopy(BLACKOUT), copy.deepcopy(TB.MOUNTS),
                                    copy.deepcopy(TB.PLACEMENTS), copy.deepcopy(TB.PROGRESSION), None))


# Without it decision B10's guarantee is unenforced in either direction: the charge could go back to scaling with the
# balance (so every rung the ladder or a trader prices raises the expected cost of saving for it, the conflict
# INCOME_MEASUREMENT.md 4.3.3 measured), or the clamp could go (a charge larger than the balance, or a negative one
# from a 32-bit overflow, which `cobbledollars remove @s -N` pays to the player instead of taking).
def test_contract_c15_a_blackouts_money_charge_is_flat_and_never_exceeds_the_balance():
    flat = _c15_flat()
    _c15_contract(TB.FNS)
    # the amount is the data's, set once at load, not recomputed per player
    assert _c15_const(TB.FNS) == flat, (_c15_const(TB.FNS), flat)

    # ---- the consumer half: the charge path reads no price and no balance-derived scale, so no rung in
    # docs/mechanics/PROGRESSION_LADDER.md and no entry in data/traders.json can change what a death costs.
    _, _, reached = _c15_charge(TB.FNS, 20_000)
    assert set(reached) == {"blackout/charge_calc", "blackout/charge_apply"}, reached
    body = [l.strip() for name in C15_PATH for l in TB.FNS[name] if l.strip() and not l.lstrip().startswith("#")]
    assert [l for l in body if l.startswith("scoreboard players operation")] == [
        "scoreboard players operation @s bo.lost = #charge bo.cfg",       # the constant
        "scoreboard players operation @s bo.lost < @s bo.bal"], body      # min(charge, balance): the only balance read
    assert not [l for l in body if re.search(r"(\*=|/=|%=|\+=|-=)", l)], body
    assert {o for l in body for o in re.findall(r"bo\.\w+", l)} == {"bo.lost", "bo.bal", "bo.cfg"}, body
    assert [l for l in body if "cobbledollars" in l] == [
        "execute store result score @s bo.bal run cobbledollars query @s",
        "$cobbledollars remove @s $(amount)"], body
    # no progress is read either, so the charge is the same at badge 0 and after the Champion
    assert not [l for l in body if "advancement" in l or "tag=" in l], body
    # the only numbers written into the path are 0 (the reset) and 1 (the `matches 1..` guard and the storage scale):
    # no price and no amount is inlined, and the amount can only come from #charge
    assert {int(n) for l in body for n in re.findall(r"(?<![\w.])-?\d+", l)} <= {0, 1}, body
    # and no price is even an input to the generator
    src = (ROOT / "tools" / "blackout_pack.py").read_text(encoding="utf-8")
    reads = set(re.findall(r'load\("([\w.]+\.json)"\)', src))
    assert reads and reads <= {"blackout.json", "water_mounts.json", "placements.json", "progression.json",
                               "towns.json"}, reads
    assert "traders.json" not in src and "PROGRESSION_LADDER" not in src
    assert set(inspect.signature(TB.BP.build).parameters) == {"cfg", "mounts", "placements", "progression",
                                                              "boat_rows"}


# Without it C15's check above could share the generator's own arithmetic and would then pass on whatever amount the
# generator emits. Each mutation changes tools/blackout_pack.py's source in memory and leaves data/blackout.json alone.
def test_harness_the_c15_charge_check_bites_when_the_generator_is_mutated():
    # (1) the balance term back: the pre-B10 rule, floored percent of the balance, still clamped
    old_rule = _c15_mutant(('        "scoreboard players operation @s bo.lost = #charge bo.cfg",',
                            '        "scoreboard players operation @s bo.lost = @s bo.bal",\n'
                            '        "scoreboard players operation @s bo.lost *= #pct bo.cfg",\n'
                            '        "scoreboard players operation @s bo.lost /= #100 bo.cfg",'))
    with pytest.raises(AssertionError):
        _c15_contract(old_rule)
    assert _c15_charge(old_rule, 20_000)[0] == 20_000 * BLACKOUT["money"]["percent"] // 100
    # and it brings back the overflow: at 2**31-1 the old rule charges a negative amount, which the check catches
    assert _c15_charge(old_rule, 2 ** 31 - 1)[0] < 0

    # (2) the constant off by one. (A pure floor instead of the ceiling is NOT observable at the authored values --
    # 3000 * 20% is exactly 600 -- so the ceiling is held by re-deriving it with math.ceil from cap and percent, which
    # bites the day either changes to a value the two disagree on, not by this mutation.)
    off_by_one = _c15_mutant(('    return -((-money["cap"] * money["percent"]) // 100)',
                              '    return -((-money["cap"] * money["percent"]) // 100) + 1'))
    assert _c15_const(off_by_one) == _c15_flat() + 1
    with pytest.raises(AssertionError):
        _c15_contract(off_by_one)


# =================================================================================================================
# C19: the suppression strips every inherited Nether spawn and leaves our compiled pools alone
# (written by the builder of the Nether tables on the brief's instruction, 2026-10-08, not by test-author)
# ==========================================================================================================


def _c19_holds(c, dim, x, z):
    """A spawn condition or anticondition holds at (dim, x, z): absent bounds restrict nothing, a non-empty
    dimensions list must contain dim (Cobblemon 1.8.0, docs/research/notes/spawn-dimension-condition-1.8.0.md)."""
    for lo, hi, v in (("minX", "maxX", x), ("minZ", "maxZ", z)):
        if (lo in c and v < c[lo]) or (hi in c and v > c[hi]):
            return False
    return not c.get("dimensions") or dim in c["dimensions"]


def test_contract_c19_the_nether_holds_only_our_compiled_tables(tmp_path):
    import zipfile
    import compile_spawns as CS
    import suppress_inherited_spawns as SIS
    spawns = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    ours, _ = CS.build_nether(spawns)
    assert ours, "no compiled Nether tables"
    server, world, out = tmp_path / "server", tmp_path / "world", tmp_path / "out"
    (server / "mods").mkdir(parents=True)
    inherited = "data/cobblemon/spawn_pool_world/fake_nether_heatmor.json"
    with zipfile.ZipFile(server / "mods" / "fake.jar", "w") as z:
        z.writestr(inherited, json.dumps({"enabled": True, "spawns": [
            {"id": "h", "pokemon": "heatmor", "type": "pokemon", "spawnablePositionType": "grounded", "bucket": "common",
             "level": "30-40", "weight": 5.0, "condition": {"biomes": ["#minecraft:is_nether"]}}]}))
    for rel, text in ours.items():
        f = world / "datapacks" / "cobblers_spawns" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    assert SIS.main(["--server", str(server), "--world", str(world), "--out", str(out), "--subregions"]) == 0
    # (1) our pools are never re-emitted, so nothing the suppression writes can shadow or strip them
    assert not [p for p in out.rglob("*.json") if "/cobblers/" in p.as_posix()]
    (detail,) = json.loads((out / inherited).read_text(encoding="utf-8"))["spawns"]
    anti = detail["anticonditions"]
    # (2) the inherited detail is gone at every point of every Nether table's boxes, and kept on the overworld far from
    # every box
    for rec in spawns["nether_tables"]:
        for b in rec["boxes"]:
            for x, z in ((b[0], b[2]), (b[1], b[3]), ((b[0] + b[1]) // 2, (b[2] + b[3]) // 2)):
                assert any(_c19_holds(c, "minecraft:the_nether", x, z) for c in anti), (rec["id"], x, z)
    assert not any(_c19_holds(c, "minecraft:overworld", -10 ** 6, -10 ** 6) for c in anti)
    # (3) every compiled Nether detail can only ever hold in the Nether
    for rel, text in ours.items():
        for s in json.loads(text)["spawns"]:
            c = s["condition"]
            x, z = (c["minX"] + c["maxX"]) // 2, (c["minZ"] + c["maxZ"]) // 2
            assert _c19_holds(c, "minecraft:the_nether", x, z), s["id"]
            assert not _c19_holds(c, "minecraft:overworld", x, z), s["id"]
# C21. The Nether admits exactly the holders of the eighth badge's flag
# C20. A player the Nether gate turns back lands where a blackout would put them
# =================================================================================================================

def _gate_files():
    import nether_gate as NG
    return {rel: text for rel, text in NG.build(NG.load()).items() if rel.endswith(".mcfunction")}


# Without it the Nether gate tests an advancement nothing grants (a renamed flag: every player bounced for ever, the
# Nether shut), or the wrong badge, or it searches a dimension other than the Nether (the Entei's pocket rooms gated,
# its champions bounced out of their own fight); or a champion the Entei sends back into the Nether is not, by the
# campaign's own chapter order, a holder of the eighth badge.
def test_contract_c21_the_nether_gate_admits_only_the_flag_the_progression_pack_grants_for_badge_8():
    import progression_pack as PP
    prog_doc = _load("progression.json")
    prog = PP.files(PP.plan(PP.load(ROOT / "data" / "progression.json"), None, PLACEMENTS))
    gate = _gate_files()
    named = set()
    for text in gate.values():
        named |= set(re.findall(r"advancements=\{([a-z0-9_]+:[a-z0-9_/]+)=", text))
    assert named == {"cobblers:flag/gym8_cleared"}, named
    key = "data/cobblers/advancement/flag/gym8_cleared.json"
    assert key in prog, "cobblers:flag/gym8_cleared is not an advancement tools/progression_pack.py writes"
    crit = json.loads(prog[key])["criteria"]
    assert crit and all(c["trigger"] != "minecraft:impossible" for c in crit.values()), crit
    flag = next(f for f in prog_doc["flags"] if f["id"] == "gym8_cleared")
    assert flag["set_by"]["kind"] == "trainer_defeat", flag["set_by"]
    # every player selector the gate runs is in the Nether, and positional (so it searches that dimension only)
    pocket = {_load("portals.json")["pocket"]["dimension"], _load("entei_boss.json")["pocket"]["dimension"]}
    for rel, text in gate.items():
        for line in text.splitlines():
            if "@a[" in line and not line.startswith("#"):
                m = re.match(r"execute in (\S+) .*@a\[([^\]]*)\]", line)
                assert m and m.group(1) == "minecraft:the_nether", (rel, line)
                assert re.search(r"\b(x|dx|distance)=", m.group(2)), ("a selector without a position", rel, line)
            assert line.startswith("#") or not any(d in line for d in pocket), ("the gate acts in the pocket", rel, line)
    # the Entei returns its champions into the Nether: champion_cleared must follow gym8_cleared in the chapters
    assert _load("entei_boss.json")["gate_flag"] == "cobblers:flag/champion_cleared"
    unlocking = {u: c for c in prog_doc["chapters"] for u in c["unlocks"]}
    seen, todo = set(), ["champion_cleared"]
    while todo:
        f = todo.pop()
        for g in unlocking.get(f, {}).get("unlocked_by", []):
            if g not in seen:
                seen.add(g)
                todo.append(g)
    assert "gym8_cleared" in seen, seen


# Without it the TM gate tests an advancement nothing grants (a renamed flag: every crafted TM locked for ever), a flag
# granted by nothing real, or a badge number the shelf does not mean (markets' gate_badge B priced on another leader).
def test_contract_c23_the_tm_gate_unlocks_on_the_flags_the_progression_pack_grants(tmp_path):
    import progression_pack as PP
    import tm_gate as TG
    import tm_gate_fixture as TF
    prog_doc = _load("progression.json")
    markets = _load("markets.json")
    prog = PP.files(PP.plan(PP.load(ROOT / "data" / "progression.json"), None, PLACEMENTS))
    server, vanilla, _ = TF.build_server(tmp_path)
    plan = TG.plan(TG.load(), TG.resolve(TG.read_server(server, vanilla)), copy.deepcopy(markets),
                   copy.deepcopy(prog_doc), scores=TF.score_table())
    files = TG.build(TG.load(), plan)
    named = set()
    for rel, text in files.items():
        named |= set(re.findall(r"advancements=\{([a-z0-9_]+:[a-z0-9_/]+)=", text))
        if rel.startswith("data/cobblers/advancement/tm_gate/earn/"):
            for cond in json.loads(text)["criteria"]["held"]["conditions"]["player"]:
                named |= set(cond["predicate"]["type_specific"]["advancements"])
    badges = sorted({g["badge"] for g in plan["gated"].values()})
    assert named == {"cobblers:flag/gym%d_cleared" % b for b in badges}, named
    for b in badges:
        fid = "gym%d_cleared" % b
        key = "data/cobblers/advancement/flag/%s.json" % fid
        assert key in prog, "cobblers:flag/%s is not an advancement tools/progression_pack.py writes" % fid
        crit = json.loads(prog[key])["criteria"]
        assert crit and all(c["trigger"] != "minecraft:impossible" for c in crit.values()), crit
        flag = next(f for f in prog_doc["flags"] if f["id"] == fid)
        assert flag["set_by"]["kind"] == "trainer_defeat", flag["set_by"]
        assert fid in markets["badges"], fid
    # the shelf's B is the B-th leader's: a shelf TM in a leader's first-win pool carries that leader's flag number
    pools = {}
    fwr = next(v for v in _walk_values(prog_doc, "first_win_rewards"))
    for tr in fwr["trainers"].values():
        m = re.fullmatch(r"gym([1-8])_cleared", tr.get("flag", ""))
        for item in tr.get("one_of", []):
            if m:
                pools.setdefault(item, int(m.group(1)))
    shelf = {}
    for counter in markets["counters"]:
        for k in ("stock", "held_stock"):
            for line in counter.get(k) or []:
                if str(line.get("item", "")).startswith("tmcraft:tm_") and isinstance(line.get("gate_badge"), int):
                    shelf[line["item"]] = line["gate_badge"]
    assert shelf and all(item in pools and pools[item] == b for item, b in shelf.items()), \
        {i: (b, pools.get(i)) for i, b in shelf.items() if pools.get(i) != b}


def _walk_values(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            yield obj[key]
        for v in obj.values():
            yield from _walk_values(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_values(v, key)


# Without it the gate calls a blackout function that was renamed (the checkpoint path fails and everyone lands at the
# pallet: safe, but not where the design sends them), reads a score the blackout no longer keeps, writes into the
# blackout's own state, or falls back to a pallet that is not standing on the ground.
def test_contract_c20_the_nether_gate_returns_through_the_blackouts_own_checkpoint():
    import blackout_pack as BP
    bo = BP.build(_load("blackout.json"), _load("water_mounts.json"), PLACEMENTS, _load("progression.json"))
    bo_fns = {re.sub(r"^data/cobblers/function/(.+)\.mcfunction$", r"cobblers:\1", rel): text.splitlines()
              for rel, text in bo.items() if rel.startswith("data/cobblers/function/")}
    gate = _gate_files()
    body = [l for text in gate.values() for l in text.splitlines() if l.strip() and not l.startswith("#")]
    called = {r for l in body for r in re.findall(r"\bfunction (cobblers:blackout/\S+)", l)}
    assert called == {"cobblers:blackout/checkpoint/validate", "cobblers:blackout/checkpoint/tp",
                      "cobblers:blackout/checkpoint/name"}, called
    assert all(c in bo_fns for c in called), called - set(bo_fns)
    tp = [l for l in bo_fns["cobblers:blackout/checkpoint/tp"] if l.strip() and not l.startswith("#")]
    assert len(tp) == 1 and tp[0].startswith("$execute in minecraft:overworld run tp @s "), tp
    assert set(re.findall(r"\$\((\w+)\)", tp[0])) == {"x", "y", "z"}, tp
    stored = {m for l in body for m in re.findall(r"store result storage cobblers:nether_gate go\.(\w+) ", l)}
    assert stored == {"x", "y", "z"}, stored
    validate = [l for l in bo_fns["cobblers:blackout/checkpoint/validate"] if l.strip() and not l.startswith("#")]
    assert validate[0] == "scoreboard players set @s bo.ok 0" and all(
        l.endswith("run scoreboard players set @s bo.ok 1") for l in validate[1:]), validate[:3]
    assert any("data modify storage cobblers:blackout place set value" in l
               for l in bo_fns["cobblers:blackout/checkpoint/name"])
    made = set(re.findall(r"^scoreboard objectives add (\S+)", "\n".join(bo_fns["cobblers:blackout/load"]), re.M))
    read = {o for l in body for o in re.findall(r"\b(bo\.\w+)\b", l)}
    assert read and read <= made, read - made
    for l in body:
        assert not re.search(r"scoreboard players (set|add|remove|reset|operation) @s bo\.", l), l
        assert not re.search(r"store result score @s bo\.", l), l
        assert "data modify storage cobblers:blackout" not in l, l
    try:
        import ground as G
        g = G.load()
    except Exception as e:  # noqa: BLE001
        pytest.skip("the canonical heightmap is not available: %s" % e)
    x, y, z = _load("blackout.json")["pallet"]["position"]
    assert y == g(x, z) + 1, (x, y, z, g(x, z))
    assert "execute in minecraft:overworld run tp @s %d.5 %d %d.5" % (x, y, z) in body


# =================================================================================================================
# The registry itself
# =================================================================================================================

def _defs(path):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


# Without it a contract points at a test that was renamed or deleted, and the registry claims a guarantee nothing checks.
# Without it maxDynamaxLevel could be lowered (Pokemon.setDmaxLevel clamps the Sketch count to it, so the count stops
# short of the cap and Sketch never fails), or the cap could be raised past Showdown's 0..10 clamp, or the generated
# override and callbacks could drift from the record's cap. The 10 is Showdown's own clamp (sim/pokemon.js:118, read
# from the 1.8.0 jar: clampIntRange(set.dynamaxLevel, 0, 10)), not the record's number.
def test_contract_c22_the_sketch_cap_fits_under_the_dynamax_level_the_config_allows():
    import battle_sim
    import mythical_starters as MS
    showdown_clamp = 10
    config = json.loads((ROOT / "modpack" / "config" / "cobblemon" / "main.json").read_text(encoding="utf-8"))
    assert config["maxDynamaxLevel"] == showdown_clamp, config["maxDynamaxLevel"]
    doc = json.loads(MS.DATA.read_text(encoding="utf-8"))
    capped = [ln for ln in doc["lines"] if "sketch_cap" in ln]
    assert len(capped) == 1, [ln["id"] for ln in capped]
    cap = capped[0]["sketch_cap"]["uses"]
    assert 1 <= cap <= min(showdown_clamp, config["maxDynamaxLevel"]), cap
    try:
        out = MS.files(doc)
    except battle_sim.SimError as exc:
        pytest.skip("no Cobblemon 1.8.0 jar: %s" % exc)
    js = out["data/cobblers/moves/sketch.js"]
    guards = re.findall(r"if \(source\.dynamaxLevel >= (\d+)\) return false;", js)
    assert guards == [str(cap)], guards
    for event in ("battle_started_post", "battle_victory", "battle_fled"):
        text = out["data/cobblemon/callbacks/%s/cobblers_sketch_cap.molang" % event]
        written = [int(n) for n in re.findall(r"apply\('dmax_level=(\d+)'\)", text)]
        assert max(written) == cap and min(written) == 1, (event, written)


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


# Without it a citation rots: the document moves on and no longer says what the registry quotes. The quote is the
# citation; the line number is a hint. A quote at its hinted line, or on exactly one line of the file, stands; a quote
# gone from the file, or found on several lines none of which is the hint, fails. Matching the line exactly broke the
# suite on every edit above a cited line (16 commits of re-pointing, 2026-09-26 to 09-28) without catching anything.
def test_every_citation_still_says_what_the_registry_quotes():
    bad = []
    for c in REGISTRY["contracts"]:
        for cite in c["stated_in"]:
            path, _, line = cite["at"].rpartition(":")
            lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
            n = int(line)
            if 1 <= n <= len(lines) and cite["quote"] in lines[n - 1]:
                continue
            hits = [i + 1 for i, text in enumerate(lines) if cite["quote"] in text]
            if len(hits) != 1:
                bad.append((c["id"], cite["at"], cite["quote"], "found on lines %s" % hits if hits else "not in the file"))
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
