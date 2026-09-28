"""The evolution-stone faces (e694436): data/mines.json, tools/mines.py, tools/mines_audit.py, the Exchange and R9O.

Written by the test author, not by the session that built the faces. The generator is used only to produce lines and
cells; every expectation here comes from docs/mechanics/STONE_ECONOMY.md, the data's own rule words, other files'
data, vanilla command semantics, or a hand computation.

Parts:
  1. Data against the design: seven places, ten stones, 22 faces of 9 x 5 x 6, Cobblemon's own ores in their own host
     rock, yields, no spawn-condition or filler block, the resettable tag, the timing, the ore variants.
  2. The driver, run by a command simulator (tests/mcfunction_sim.py extended below with volume selectors, block
     predicates, filtered fill, `time query`, `random value` and the arithmetic score operations) over simulated game
     time: the 600 s period, the approach box, the player and Pokemon guard, the four loaded corners, the filtered
     restore (a chest survives), no repeated variant, the sibling stagger, and a restart without a double restore.
  3. The cut on a hand-computed flat fixture: three apron rows then a six-row ramp; thin cover and a deep fill refused;
     the build writes only host, ore, floor, air, and the site's bedrock and lanterns.
  4. tools/mines_audit.py on a synthetic root (the generator poisoned while it runs): a clean face passes, and each of
     many planted faults is named.
  5. The Exchange (data/traders.json, tools/traders.py) and step R9O (tools/reapply.py).
  6. With the canonical heightmap (SKIPS without COBBLERS_SOURCE_ROOT): cover, a walk into and out of every surface
     cut, and every surface face's written columns clear of route legs, streets, buildings, event sites, dressing and
     working Pokemon, inside the town's reach. With local-only inputs (the built pack, derived/water_shape/changed.npy,
     derived/cavern) the water rule, the Displaced City and the full audit run; without them they SKIP.

A skip is not a pass. Not covered (runtime, proofs P-1..P-8): that Cobblemon's ores drop their stone, that the restore
runs in a live server without a hitch, that a restart keeps the scoreboard, that the Assayer's authored shop sells and
buys nothing in game, that R9O rebuilds on a fresh export, and how any cut looks.
"""
from __future__ import annotations

import inspect
import json
import math
import os
import random
import re
import sys
import types
from collections import deque
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import mcfunction_sim as SIM  # noqa: E402
import mines as M  # noqa: E402  (the generator: produces lines and cells, never the oracle)
import mines_audit as MA  # noqa: E402

SPEC = json.loads((ROOT / "data" / "mines.json").read_text(encoding="utf-8"))
GEO = SPEC["geometry"]
RS = SPEC["restore"]
SITES = SPEC["sites"]
FACES = [(s, f) for s in SITES for f in s["faces"]]
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
TRADERS = json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))
TOWNS = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}
PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
AIRS = ("minecraft:air", "minecraft:cave_air")
TAG = "#cobblers:" + RS["resettable_tag"]

# STONE_ECONOMY.md section 3 ("Stone by stone"): the place of each stone, two faces per stone per place, and the rate
# per face per reset. Thunder is at two places. Typed from the design's table, not read from data/mines.json.
DESIGN = {
    "viltri_light": {"water": 2},
    "tea_town": {"leaf": 2, "shiny": 2},
    "the_scar": {"sun": 2},
    "displaced_city": {"moon": 2, "thunder": 2},
    "northlight": {"ice": 2},
    "gorge_hamlet": {"dusk": 2, "dawn": 2},
    "mining_town": {"fire": 2, "thunder": 2},
}
DESIGN_RATE = {"thunder": (3, 5), "fire": (1, 3)}          # every other stone 2-4
TEN_STONES = ["water", "leaf", "shiny", "sun", "moon", "thunder", "ice", "dusk", "dawn", "fire"]
# the natural host of a Cobblemon stone ore, by its id's prefix (WORLDGEN_FEATURES_TABLE.md lists the ids)
HOST_OF_PREFIX = {"deepslate_": "minecraft:deepslate", "terracotta_": "minecraft:terracotta",
                  "dripstone_": "minecraft:dripstone_block", "": "minecraft:stone"}


def name_of(state):
    return re.split(r"[\[{]", state, 1)[0]


def table_ores():
    text = (ROOT / "docs" / "world-building" / "WORLDGEN_FEATURES_TABLE.md").read_text(encoding="utf-8")
    return set(re.findall(r"`(cobblemon:[a-z_]+_stone_ore)`", text))


def front_frame(box, front):
    """(cells of the front plane, cell-in-front(u, y, n)) computed here from the box and the design's words."""
    x0, y0, z0, x1, y1, z1 = box
    if front == "north":
        return lambda u, d: (x0 + u, z0 + d)
    if front == "south":
        return lambda u, d: (x0 + u, z1 - d)
    if front == "west":
        return lambda u, d: (x0 + d, z0 + u)
    return lambda u, d: (x1 - d, z0 + u)


def along_and_deep(box, front):
    x0, y0, z0, x1, y1, z1 = box
    ns = (x1 - x0 + 1, z1 - z0 + 1)
    return ns if front in ("north", "south") else (ns[1], ns[0])


# ================================================================================ 1. data against the design

def test_the_seven_places_carry_the_design_stones_two_faces_a_stone():
    # Without it a stone could lose its place, or a place gain a stone the design put elsewhere, unnoticed.
    have = {}
    for s, f in FACES:
        have.setdefault(s["settlement"], {}).setdefault(f["stone"], 0)
        have[s["settlement"]][f["stone"]] += 1
    assert have == DESIGN
    assert sorted(SPEC["stones"]) == sorted(TEN_STONES)
    assert len(FACES) == 22 and len({f["id"] for _s, f in FACES}) == 22


def test_every_face_is_nine_along_six_deep_and_five_high_from_its_front():
    # Without it a face could be turned (6 along, 9 deep) and the restore box would not be what the player works.
    assert (GEO["width"], GEO["depth"], GEO["height"]) == (9, 6, 5)
    for _s, f in FACES:
        x0, y0, z0, x1, y1, z1 = f["box"]
        assert f["front"] in ("north", "south", "west", "east"), f["id"]
        assert along_and_deep(f["box"], f["front"]) == (9, 6), f["id"]
        assert y1 - y0 + 1 == 5, f["id"]


def test_every_ore_is_cobblemons_own_ore_of_its_stone_set_in_its_own_host_rock():
    # Without it a face could hold an ore that drops the wrong stone, a modded id, or ore floating in the wrong rock.
    ores = table_ores()
    assert len(ores) >= 20, "the worldgen table lists too few stone ores to be the one read"
    for _s, f in FACES:
        assert f["ore"] in ores, "%s: %s is not in WORLDGEN_FEATURES_TABLE.md" % (f["id"], f["ore"])
        assert f["ore"] in SPEC["stones"][f["stone"]]["ores"], f["id"]
        stem = f["ore"].split(":", 1)[1]
        assert stem.endswith("%s_stone_ore" % f["stone"]), f["id"]
        prefix = next(p for p in HOST_OF_PREFIX if p and stem.startswith(p)) if any(
            stem.startswith(p) for p in HOST_OF_PREFIX if p) else ""
        assert f["host"] == HOST_OF_PREFIX[prefix], "%s: %s set in %s" % (f["id"], f["ore"], f["host"])
    for st, rec in SPEC["stones"].items():
        assert rec["item"] == "cobblemon:%s_stone" % st
        assert set(rec["ores"]) <= ores


def test_yields_are_the_designs_rate_with_one_visible_ore():
    # Without it Thunder (six families) or Fire (none) could drift from the rate STONE_ECONOMY.md section 3 sets.
    for _s, f in FACES:
        y = f["yield"]
        assert (y["ore_min"], y["ore_max"]) == DESIGN_RATE.get(f["stone"], (2, 4)), f["id"]
        assert y.get("visible_min") == 1, f["id"]


def test_no_block_a_face_uses_is_a_spawn_condition_and_there_is_no_filler():
    # Without it a face would decide encounters (a coal ore is a spawn condition), which O-7 left open.
    used = {f["host"] for _s, f in FACES} | {f["ore"] for _s, f in FACES} | {f.get("floor") or "" for _s, f in FACES}
    used |= {"minecraft:bedrock", name_of(M.LANTERN), *(s.get("floor_block", "") for s in SITES)}
    # (the resettable tag names water and lava, which are spawn conditions, but only as what a restore replaces)
    assert not (used - {""}) & SPAWN
    assert str(SPEC.get("filler", "")).startswith("none")
    for _s, f in FACES:
        assert set(f) >= {"id", "stone", "ore", "host", "yield", "box", "front", "offset_ticks"}
        assert not [k for k in f if "filler" in k], f["id"]


CONTAINER_WORDS = ("chest", "barrel", "shulker", "hopper", "dispenser", "dropper", "furnace", "smoker", "crafter",
                   "brewing", "lectern", "pot", "bookshelf", "jukebox", "campfire", "sign", "bed", "banner", "spawner",
                   "beehive", "nest", "vault", "trial", "anvil", "table", "cobblemon:pc", "healing", "sapling")


def test_the_resettable_tag_holds_the_air_every_host_and_ore_and_no_block_entity():
    # Without it a restore could leave a hole it cannot refill, or delete a player's chest and its contents (5.4).
    tag = set(RS["resettable"])
    assert set(AIRS) <= tag
    assert {f["host"] for _s, f in FACES} | {f["ore"] for _s, f in FACES} <= tag
    for b in tag:
        assert not any(w in b for w in CONTAINER_WORDS), b
    assert {b for b in tag if b.endswith("_stone_ore")} <= table_ores()


def test_the_restore_is_600_s_or_more_and_the_two_faces_of_a_stone_half_a_period_apart():
    # Without it a face could refill faster than the design's 600 s, or both faces of a stone refill together.
    assert RS["period_ticks"] >= 12000 and RS["every_ticks"] <= RS["period_ticks"]
    assert RS["variants"] == 8 and RS["stagger_ticks"] == RS["period_ticks"] // 2
    for s in SITES:
        by = {}
        for f in s["faces"]:
            by.setdefault(f["stone"], []).append(int(f["offset_ticks"]))
        for st, offs in by.items():
            assert len(offs) == 2 and abs(offs[0] - offs[1]) % RS["period_ticks"] == RS["stagger_ticks"], (s["id"], st)


def test_every_surface_face_stands_inside_its_towns_reach():
    # Without it a face could be sited off in the wilds, far from the place the design names.
    for s, f in FACES:
        if s.get("ground") == "cavern_floor":
            continue
        fp = TOWNS[s["settlement"]]["footprint"]
        x0, _y0, z0, x1, _y1, z1 = f["box"]
        assert fp["min_x"] - 24 <= x0 and x1 <= fp["max_x"] + 24, f["id"]
        assert fp["min_z"] - 24 <= z0 and z1 <= fp["max_z"] + 24, f["id"]


def test_every_ore_variant_holds_the_yield_one_visible_tell_and_the_rest_two_deep():
    # Without it a variant could hide every ore (no tell on the face), leave the box, or break the yield.
    for _s, f in FACES:
        x0, y0, z0, x1, y1, z1 = f["box"]
        xz = front_frame(f["box"], f["front"])
        W, D = along_and_deep(f["box"], f["front"])
        deep = {xz(u, d): d for u in range(W) for d in range(D)}
        tell = {(xz(u, 0)[0], y0, xz(u, 0)[1]) for u in range(1, W - 1)}
        seen = set()
        for k in range(RS["variants"]):
            cells = M.ore_cells(f, k, SPEC["seed"], GEO, f["yield"])
            assert len(set(cells)) == len(cells), f["id"]
            assert f["yield"]["ore_min"] <= len(cells) <= f["yield"]["ore_max"], (f["id"], k)
            assert all(x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1 for x, y, z in cells), (f["id"], k)
            vis = [c for c in cells if c in tell]
            assert len(vis) == 1, (f["id"], k, cells)
            rest = [c for c in cells if c not in tell]
            assert all(deep[(x, z)] >= 2 and y < y1 for x, y, z in rest), (f["id"], k, rest)
            seen.add(tuple(sorted(cells)))
        assert len(seen) >= RS["variants"] - 1, "%s: the variants are nearly all the same" % f["id"]


# ================================================================================ 2. the driver, simulated

HITBOX = {"minecraft:player": (0.3, 1.8), "cobblemon:pokemon": (0.4, 1.0)}


class MinesWorld(SIM.World):
    """mcfunction_sim.World plus what the mines pack uses, from vanilla 1.21.1 semantics:

    volume selectors (x/y/z with dx/dy/dz select an entity whose bounding box intersects the box from (x, y, z) to
    (x + dx + 1, ...)); `execute if|unless block P <block|#tag>` (fails on an unloaded chunk); `setblock`; `fill ... [replace
    <filter>]` (fails whole when any chunk of the box is unloaded); `time query gametime`; `random value a..b`;
    `scoreboard players operation` with += -= *= /= %= (floor division and positive modulo) < > ><."""

    def __init__(self, functions, block_tags, **kw):
        super().__init__(functions, **kw)
        self.blocks = {}
        self.block_tags = block_tags
        self.gametime = 0
        self.rng = random.Random(5)
        self.draw = None

    def tick(self, n=1):
        for _ in range(n):
            self.gametime += 1
            super().tick(1)

    def select(self, sel, ctx, single=False):
        m = re.match(r"@([aepsr])\[(.*)\]$", sel)
        if not m:
            return super().select(sel, ctx, single)
        args = SIM._args(m.group(2))
        vol = {k: float(v) for k, v in args if k in ("dx", "dy", "dz")}
        if not vol:
            return super().select(sel, ctx, single)
        rest = ",".join("%s=%s" % kv for kv in args if kv[0] not in ("dx", "dy", "dz"))
        pool = super().select("@%s[%s]" % (m.group(1), rest), ctx, single)
        d = dict(args)
        o = [float(d[k]) if k in d else ctx.pos[i] for i, k in enumerate("xyz")]
        lo = [o[i] + min(0.0, vol.get(k, 0.0)) for i, k in enumerate(("dx", "dy", "dz"))]
        hi = [o[i] + max(0.0, vol.get(k, 0.0)) + 1 for i, k in enumerate(("dx", "dy", "dz"))]

        def hit(e):
            hw, h = HITBOX.get(e.type, (0.3, 1.0))
            blo = (e.pos[0] - hw, e.pos[1], e.pos[2] - hw)
            bhi = (e.pos[0] + hw, e.pos[1] + h, e.pos[2] + hw)
            return all(blo[i] < hi[i] and bhi[i] > lo[i] for i in range(3))
        return [e for e in pool if hit(e)]

    def matches(self, c, pred):
        b = name_of(self.blocks.get(c, "minecraft:air"))
        if pred.startswith("#"):
            return b in self.block_tags[pred]
        return b == name_of(pred)

    def c_time(self, rest, ctx):
        if rest.split() != ["query", "gametime"]:
            raise SIM.Unsupported("time %s" % rest)
        return self.gametime % 2147483647

    def c_random(self, rest, ctx):
        m = re.fullmatch(r"value (-?\d+)\.\.(-?\d+)", rest.strip())
        if not m:
            raise SIM.Unsupported("random %s" % rest)
        a, b = int(m.group(1)), int(m.group(2))
        return self.draw(a, b) if self.draw else self.rng.randint(a, b)

    def c_scoreboard(self, rest, ctx):
        t = rest.split()
        if t[:2] == ["players", "operation"] and t[4] != "=":
            a, ao, op, b, bo = t[2:7]
            bv = self.get_score(b, bo, ctx)
            if ao not in self.objectives:
                raise SIM.Failed("no objective")
            key = (self.holder(a, ctx), ao)
            av = self.scores.get(key, 0)
            if op in ("/=", "%=") and bv == 0:
                raise SIM.Failed("divide by zero")
            r = {"+=": lambda: av + bv, "-=": lambda: av - bv, "*=": lambda: av * bv, "/=": lambda: av // bv,
                 "%=": lambda: av % bv, "<": lambda: min(av, bv), ">": lambda: max(av, bv)}.get(op)
            if r is None:
                raise SIM.Unsupported("operation %s" % op)
            self.scores[key] = r()
            return self.scores[key]
        return super().c_scoreboard(rest, ctx)

    def c_setblock(self, rest, ctx):
        t = rest.split()
        x, y, z = (int(math.floor(v)) for v in self.coords(t[0:3], ctx))
        if not self.loaded(x, z):
            raise SIM.Failed("unloaded")
        self.blocks[(x, y, z)] = t[3]
        self._log((self.tick_no, "setblock", ((x, y, z), t[3])))
        return 1

    def c_fill(self, rest, ctx):
        t = rest.split()
        a = [int(math.floor(v)) for v in self.coords(t[0:3], ctx)]
        b = [int(math.floor(v)) for v in self.coords(t[3:6], ctx)]
        lo, hi = [min(p, q) for p, q in zip(a, b)], [max(p, q) for p, q in zip(a, b)]
        if (hi[0] - lo[0] + 1) * (hi[1] - lo[1] + 1) * (hi[2] - lo[2] + 1) > 32768:
            raise SIM.Failed("too big")
        for cx in range(lo[0] // 16, hi[0] // 16 + 1):
            for cz in range(lo[2] // 16, hi[2] // 16 + 1):
                if not self.loaded(cx * 16, cz * 16):
                    self.errors.append("fill into an unloaded chunk: %s" % rest)
                    raise SIM.Failed("unloaded")
        block, mode = t[6], (t[7] if len(t) > 7 else "replace")
        flt = t[8] if len(t) > 8 else None
        if mode != "replace":
            raise SIM.Unsupported("fill mode %s" % mode)
        n = 0
        for x in range(lo[0], hi[0] + 1):
            for y in range(lo[1], hi[1] + 1):
                for z in range(lo[2], hi[2] + 1):
                    if flt and not self.matches((x, y, z), flt):
                        continue
                    self.blocks[(x, y, z)] = block
                    n += 1
        self._log((self.tick_no, "fill", (tuple(lo), tuple(hi), block, flt)))
        return n

    def _execute(self, toks, i, ctx, stores):
        if i + 1 < len(toks) and toks[i] in ("if", "unless") and toks[i + 1] == "block":
            x, y, z = (int(math.floor(v)) for v in self.coords(toks[i + 2:i + 5], ctx))
            if not self.loaded(x, z):
                return 0
            passed = self.matches((x, y, z), toks[i + 5]) == (toks[i] == "if")
            if i + 6 >= len(toks):
                self._store(stores, ctx, 1 if passed else 0, passed)
                return 1 if passed else 0
            if not passed:
                return 0
            return self._execute(toks, i + 6, ctx, stores)
        return super()._execute(toks, i, ctx, stores)


def approach_of(site):
    """The site's approach box from the data's words: the faces' bounds grown by approach_margin across,
    approach_down below and approach_up above."""
    bs = [f["box"] for f in site["faces"]]
    m = RS["approach_margin"]
    return (min(b[0] for b in bs) - m, min(b[1] for b in bs) - RS["approach_down"], min(b[2] for b in bs) - m,
            max(b[3] for b in bs) + m, max(b[4] for b in bs) + RS["approach_up"], max(b[5] for b in bs) + m)


def driver_plan():
    return [{"site": s, "approach": list(approach_of(s)),
             "faces": [{"face": f, "variants": [M.ore_cells(f, k, SPEC["seed"], GEO, f["yield"])
                                                for k in range(RS["variants"])]} for f in s["faces"]]} for s in SITES]


def built_pack():
    p = ROOT / "build" / "datapacks" / "cobblers_mines"
    return p if (p / "data" / "cobblers" / "function" / "mines" / "tick.mcfunction").is_file() else None


@pytest.fixture(params=["generated", "built"])
def mworld(request):
    """A fresh world running the mines driver: generated here from the data, or the built pack when it exists."""
    def make(loaded=None, gametime=1_000_000):
        if request.param == "built":
            pack = built_pack()
            if pack is None:
                pytest.skip("NOT_EXECUTED: no built build/datapacks/cobblers_mines here (python tools/mines.py build)")
            base = SIM.World.from_pack(pack)
            tagp = pack / "data" / "cobblers" / "tags" / "block" / ("%s.json" % RS["resettable_tag"])
            tag = set(json.loads(tagp.read_text(encoding="utf-8"))["values"])
            w = MinesWorld(base.functions, {TAG: tag}, loaded=loaded)
            w.tags = base.tags
        else:
            fns = {"cobblers:mines/" + k: v for k, v in M.driver_files(SPEC, driver_plan()).items()}
            w = MinesWorld(fns, {TAG: set(RS["resettable"])}, loaded=loaded)
            w.tags = {"load": ["cobblers:mines/load"], "tick": ["cobblers:mines/tick"]}
        w.gametime = gametime
        for _s, f in FACES:                               # as the build leaves it: host rock at variant 0
            x0, y0, z0, x1, y1, z1 = f["box"]
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    for z in range(z0, z1 + 1):
                        w.blocks[(x, y, z)] = f["host"]
            for c in M.ore_cells(f, 0, SPEC["seed"], GEO, f["yield"]):
                w.blocks[c] = f["ore"]
        w.run_load()
        return w
    return make


def watcher_spot(site):
    """A point inside the site's approach box and far from every face's box."""
    a = approach_of(site)
    return (a[0] + 2.5, a[1] + 40.0, a[2] + 2.5)


def before(face, n):
    """The centre of the cell n in front of the face's front plane, at the box's bottom."""
    x0, y0, z0, x1, y1, z1 = face["box"]
    cx, cz = (x0 + x1) // 2 + 0.5, (z0 + z1) // 2 + 0.5
    return {"north": (cx, y0, z0 - n + 0.5), "south": (cx, y0, z1 + n + 0.5),
            "west": (x0 - n + 0.5, y0, cz), "east": (x1 + n + 0.5, y0, cz)}[face["front"]]


def restores(w, fid):
    return [t for t, name in w.calls if name == "cobblers:mines/faces/restore_%s" % fid]


def variants_run(w, fid):
    pre = "cobblers:mines/faces/%s_v" % fid
    return [(t, int(name[len(pre):])) for t, name in w.calls if name.startswith(pre)]


def site(sid):
    return next(s for s in SITES if s["id"] == sid)


def test_a_watched_face_restores_every_period_and_never_sooner_and_siblings_stay_half_a_period_apart(mworld):
    # Without it a face could refill faster than 600 s, never refill while watched, or both bays of a stone together.
    w = mworld()
    for s in SITES:
        w.add_player(watcher_spot(s))
    w.tick(40000)
    P, E = RS["period_ticks"], RS["every_ticks"]
    for s in SITES:
        by_stone = {}
        for f in s["faces"]:
            r = restores(w, f["id"])
            assert len(r) >= 3, "%s restored %d times in 40,000 watched ticks" % (f["id"], len(r))
            gaps = [b - a for a, b in zip(r, r[1:])]
            assert all(P <= g <= P + E for g in gaps), (f["id"], gaps)
            by_stone.setdefault(f["stone"], []).append(r)
        for st, (ra, rb) in by_stone.items():
            assert min(abs(a - b) for a in ra for b in rb) >= RS["stagger_ticks"], (s["id"], st)


def test_no_face_restores_without_a_player_in_its_sites_approach_box(mworld):
    # Without it the driver would fill faces nobody is near (fill fails on unloaded chunks: the design's reason 5.3).
    w = mworld()
    s = site("gorge_hamlet")
    a = approach_of(s)
    p = w.add_player((a[0] - 1.0, a[1] + 40.0, a[2] + 10.5))        # one block west of the box, hitbox and all
    w.tick(30000)
    assert not [c for c in w.calls if "/faces/restore_" in c[1]]
    p.pos = [a[0] + 0.5, a[1] + 40.0, a[2] + 10.5]
    t0 = w.tick_no
    w.tick(RS["every_ticks"] + 1)
    assert all(any(t > t0 for t in restores(w, f["id"])) for f in s["faces"] if f["offset_ticks"] == 0)


def test_a_player_standing_at_a_face_holds_its_restore_off(mworld):
    # Without it the mandatory guard fails: rock fills round a player working the face (suffocation, lost ore).
    w = mworld()
    s = site("gorge_hamlet")
    f = s["faces"][0]
    w.add_player(watcher_spot(s))
    w.add_player(before(f, 1))
    w.tick(30000)
    assert restores(w, f["id"]) == []
    assert all(restores(w, g["id"]) for g in s["faces"][1:])


def test_a_sent_out_pokemon_in_a_face_holds_its_restore_off(mworld):
    # Without it a player's Pokemon standing in the rock would be buried by the fill.
    w = mworld()
    s = site("tea_town")
    f = s["faces"][2]
    w.add_player(watcher_spot(s))
    x0, y0, z0, x1, y1, z1 = f["box"]
    w.add(SIM.Entity("cobblemon:pokemon", ((x0 + x1) / 2 + 0.5, y0 + 1, (z0 + z1) / 2 + 0.5)))
    w.tick(30000)
    assert restores(w, f["id"]) == []
    assert all(restores(w, g["id"]) for g in s["faces"] if g is not f)


def test_a_player_one_block_outside_the_grown_box_does_not_hold_the_restore(mworld):
    # Without it a guard grown too far would stop a face whenever someone waits in front of it.
    w = mworld()
    s = site("northlight")
    f = s["faces"][0]
    w.add_player(watcher_spot(s))
    w.add_player(before(f, 3))
    w.tick(RS["period_ticks"] + 2 * RS["every_ticks"])
    assert restores(w, f["id"])


def test_a_face_with_a_corner_chunk_unloaded_is_not_restored_and_no_fill_is_tried(mworld):
    # Without it a fill would run into an unloaded chunk and fail silently, leaving a half-restored face.
    s = site("mining_town")
    f = s["faces"][0]
    x0, _y0, z0, x1, _y1, z1 = f["box"]
    dark = {((x1 + 1) // 16, (z1 + 1) // 16)}
    assert dark != {((x0 - 1) // 16, (z0 - 1) // 16)}, "pick a face whose grown box spans two chunks"
    w = mworld(loaded=lambda x, z: (math.floor(x) // 16, math.floor(z) // 16) not in dark)
    w.add_player(watcher_spot(s))
    w.tick(30000)
    assert restores(w, f["id"]) == [] and not w.errors


def test_the_restore_refills_rock_but_leaves_a_players_chest_and_planks(mworld):
    # Without it the restore would delete what a player built or stored in a worked-out face (5.4).
    w = mworld()
    s = site("viltri_light")
    f = s["faces"][0]
    x0, y0, z0, x1, y1, z1 = f["box"]
    box = [(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)]
    for c in box:
        w.blocks[c] = "minecraft:air"                     # mined out
    chest, planks = box[0], box[-1]
    w.blocks[chest] = "minecraft:chest[facing=north,type=single,waterlogged=false]"
    w.blocks[planks] = "minecraft:oak_planks"
    w.add_player(watcher_spot(s))
    w.tick(RS["period_ticks"] + RS["every_ticks"])
    runs = variants_run(w, f["id"])
    assert runs, "the face never restored"
    k = runs[-1][1]
    assert w.blocks[chest].startswith("minecraft:chest") and w.blocks[planks] == "minecraft:oak_planks"
    ore = [c for c in box if w.blocks[c] == f["ore"]]
    want = [c for c in M.ore_cells(f, k, SPEC["seed"], GEO, f["yield"]) if c not in (chest, planks)]
    assert sorted(ore) == sorted(want)
    assert all(w.blocks[c] == f["host"] for c in box if c not in (chest, planks) and c not in ore)


def test_a_restore_never_draws_the_variant_it_drew_last(mworld):
    # Without it a player could meet the same ore layout twice running (and the build's variant 0 first).
    w = mworld()
    s = site("gorge_hamlet")
    w.add_player(watcher_spot(s))

    def last_again(a, b):
        # the worst draw: whatever this face drew last time (the face is the restore function on the stack)
        fid = w.stack[-1].rsplit("restore_", 1)[1]
        return w.scores[("#%s" % fid, "mn.var")]
    w.draw = last_again
    w.tick(6 * RS["period_ticks"])
    for f in s["faces"]:
        seq = [0] + [v for _t, v in variants_run(w, f["id"])]          # the build leaves variant 0
        assert len(seq) >= 5 and all(a != b for a, b in zip(seq, seq[1:])), (f["id"], seq)
    w2 = mworld()
    w2.add_player(watcher_spot(s))
    w2.tick(60 * RS["period_ticks"])
    for f in s["faces"]:
        seq = [0] + [v for _t, v in variants_run(w2, f["id"])]
        assert all(a != b for a, b in zip(seq, seq[1:])), (f["id"], seq)
        assert set(seq) == set(range(RS["variants"])), (f["id"], sorted(set(seq)))


def test_a_restart_neither_repeats_a_restore_nor_loses_one(mworld):
    # Without it a server restart (the load running again) would refill every face at once (P-4) or forget them.
    w = mworld()
    s = site("the_scar")
    w.add_player(watcher_spot(s))
    w.tick(RS["period_ticks"] + RS["every_ticks"])
    first = {f["id"]: restores(w, f["id"]) for f in s["faces"]}
    assert all(first.values())
    # restart: the scoreboard and the game time are saved with the world; the load runs again, twice for good measure
    t0 = w.tick_no
    w.run_load()
    w.run_load()
    w.tick(RS["period_ticks"] - 3 * RS["every_ticks"])
    for f in s["faces"]:
        after = [t for t in restores(w, f["id"]) if t > t0]
        assert all(t - first[f["id"]][-1] >= RS["period_ticks"] for t in after), (f["id"], after)
    w.tick(RS["period_ticks"])
    assert all([t for t in restores(w, f["id"]) if t > t0] for f in s["faces"])


def test_the_driver_does_its_work_only_every_every_ticks(mworld):
    # Without it the check of every face would run every tick (the cost 5.3 budgets against).
    w = mworld()
    w.add_player(watcher_spot(site("tea_town")))
    w.tick(1000)
    drives = [t for t, n in w.calls if n == "cobblers:mines/drive"]
    assert len(drives) == 1000 // RS["every_ticks"]
    assert all(b - a == RS["every_ticks"] for a, b in zip(drives, drives[1:]))


# ================================================================================ 3. the cut, hand-computed

FLAT = 100


def flat(x, z):
    return FLAT


def north_face(y0=94, fid="t"):
    # a north face on flat ground at y100: the box top y98 has exactly the 2 blocks of backing over it
    return {"id": fid, "box": [0, y0, 0, 8, y0 + 4, 5], "front": "north", "host": "minecraft:stone",
            "ore": "cobblemon:water_stone_ore", "stone": "water", "floor": "minecraft:cobblestone",
            "yield": {"ore_min": 2, "ore_max": 4, "visible_min": 1}, "offset_ticks": 0}


def test_the_cut_on_flat_ground_is_three_level_apron_rows_then_a_ramp_of_six_that_meets_the_ground():
    # Without it the rule words in data/mines.json and the cut the build writes could part (a pit with no way out).
    # By hand: the floor starts at y0 - 1 = 93 for the three apron rows; rows 4..9 climb one a row to 99, where the
    # ground (100) is within one of it; row 10 is natural ground and not written.
    gm = M.geometry(north_face(), flat, GEO)
    assert gm["problems"] == []
    assert gm["rows"] == [(1, 93), (2, 93), (3, 93), (4, 94), (5, 95), (6, 96), (7, 97), (8, 98), (9, 99)]
    cells = gm["cells"]
    for x in range(-1, 10):                            # width 9 plus the margin of 1 each side
        for r, t in gm["rows"]:
            z = -r
            assert cells[(x, t, z)] == "floor"
            top = 102 if r > 3 else max(102, 98 + 1)
            assert all(cells[(x, y, z)] == "air" for y in range(t + 1, top + 1)), (x, r)
        assert (x, 99, -10) not in cells and (x, 100, -10) in cells   # the skin under the last row's air only
    assert sum(1 for r in cells.values() if r == "box") == 9 * 5 * 6
    assert all(cells[(x, y, -1)] == "air" for x in range(9) for y in range(94, 99))


def test_the_cut_refuses_thin_cover_over_the_box_and_a_built_up_apron_over_a_drop():
    # Without it a face could stand with its box showing through the ground, or on a tower of fill over a cliff.
    thin = M.geometry(north_face(y0=95), flat, GEO)["problems"]
    assert any("box column" in p and "backing" in p for p in thin)
    cliff = M.geometry(north_face(), lambda x, z: FLAT if z >= 0 else 85, GEO)["problems"]
    assert any("built up" in p for p in cliff)


def _replay(lines):
    out = {}
    for ln in lines:
        m = re.match(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)$", ln)
        if not m:
            continue
        a = [int(v) for v in m.group(2, 3, 4)]
        b = [int(v) for v in m.group(5, 6, 7)] if m.group(5) else a
        for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
            for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1):
                    out[(x, y, z)] = m.group(8)
    return out


@pytest.mark.parametrize("bedrock", [False, True])
def test_the_build_writes_only_host_ore_floor_and_air_plus_hidden_bedrock_and_lanterns_where_the_site_says(bedrock):
    # Without it a build could slip in filler ore or another block, or show bedrock in the cut (6.4).
    f = north_face(y0=90 if bedrock else 94)          # a bedrock shell needs a block more cover than its backing
    s = {"id": "fx", "settlement": "fx", "floor_block": "minecraft:cobblestone", "bedrock_skin": bedrock,
         "lanterns": bedrock, "faces": [f]}
    gm = M.geometry(f, flat, GEO, bedrock)
    assert gm["problems"] == []
    entry = {"site": s, "faces": [{"face": f, "geometry": gm,
                                   "variants": [M.ore_cells(f, 0, 1, GEO, f["yield"])]}]}
    world = _replay(M.build_lines({"geometry": GEO}, entry))
    names = {name_of(b) for b in world.values()}
    allowed = {f["host"], f["ore"], f["floor"], "minecraft:air"} | ({"minecraft:bedrock", "minecraft:lantern"} if bedrock else set())
    assert names <= allowed and {f["host"], f["ore"], "minecraft:air"} <= names
    assert ("minecraft:bedrock" in names) == bedrock
    for c, b in world.items():
        if b == "minecraft:bedrock":
            assert not any(world.get((c[0] + dx, c[1] + dy, c[2] + dz)) in AIRS
                           for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))), c
            assert c[1] < FLAT, c


# ================================================================================ 4. the audit on a synthetic root

N = 128
FX_FACE = {"id": "fa", "stone": "water", "ore": "cobblemon:water_stone_ore", "host": "minecraft:stone",
           "floor": "minecraft:cobblestone", "yield": {"ore_min": 2, "ore_max": 4, "visible_min": 1},
           "offset_ticks": 0, "box": [40, 94, 50, 48, 98, 55], "front": "north"}


class FakeGround:
    def __init__(self, source_root=None, world_path=None):
        self.heights = np.full((N, N), FLAT + 0.4)
        self.world = {}
        self.ox = self.oz = 0

    def __call__(self, x, z):
        return int(np.round(self.heights[int(z), int(x)]))


def fx_spec():
    spec = {k: v for k, v in SPEC.items() if k not in ("sites", "stones")}
    spec["seed"] = 11
    spec["stones"] = {"water": {"item": "cobblemon:water_stone", "ores": ["cobblemon:water_stone_ore"]}}
    spec["sites"] = [{"id": "site_a", "settlement": "town_a", "floor_block": "minecraft:cobblestone",
                      "faces": [json.loads(json.dumps(FX_FACE))]}]
    return spec


def fx_root(root, monkeypatch):
    """A root holding one clean face on flat ground at y100, with near misses: a pending water change 9 from the cut,
    a lot 3 from it, the Exchange far away. Returns the pack's function folder."""
    def dump(rel, obj):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj), encoding="utf-8")
    spec = fx_spec()
    dump("data/mines.json", spec)
    dump("data/spawn_blocks.json", {"blocks": {"minecraft:coal_ore": ["x"], "minecraft:grass_block": ["x"]}})
    dump("data/placements.json", {"settlements": {"town_a": {"plan": {}}}, "placements": []})
    dump("data/scenes.json", {"scenes": []})
    dump("data/town_dressing.json", {"towns": {}})
    dump("data/traders.json", {"traders": [{"id": "ex", "settlement": "mining_town", "stock": "stones",
                                            "position": {"x": 120, "y": 100, "z": 120}}],
                               "stock_policy": {"stones": {"items": ["cobblemon:water_stone"], "buys": False}}})
    dump("derived/towns/town_a_plan.json", {"lots": [{"id": "L1", "rect": [52, 40, 60, 48]}]})
    dump("derived/signposts.json", {"posts": []})
    dump("derived/ambient/plan.json", {"workers": []})
    # near misses of the routed legs (LEG_MARGIN 3): the written columns run x 38..50 and z 40..57
    dump("derived/routes/critical_legs.json", {"legs": [{"polyline": [[54, 0], [54, 127]]}]})
    dump("data/routes.json", {"routes": [{"id": "r", "corridor": {"polyline": [{"x": 0, "z": 61}, {"x": 127, "z": 61}]}}]})
    ch = np.zeros((N, N), dtype=bool)
    ch[31, 44] = True                                  # 9 north of the cut's last written row (z 40)
    (root / "derived" / "water_shape").mkdir(parents=True, exist_ok=True)
    np.save(root / "derived" / "water_shape" / "changed.npy", ch)
    gm = M.geometry(spec["sites"][0]["faces"][0], FakeGround(), GEO)
    assert gm["problems"] == []
    plan = [{"site": spec["sites"][0], "approach": list(_fx_approach(spec)),
             "faces": [{"face": spec["sites"][0]["faces"][0], "geometry": gm,
                        "variants": [M.ore_cells(spec["sites"][0]["faces"][0], k, spec["seed"], GEO, FX_FACE["yield"])
                                     for k in range(RS["variants"])]}]}]
    out = root / "build" / "datapacks" / "cobblers_mines"
    monkeypatch.setattr(M, "OUT", out)
    M.write(spec, plan)
    return out / "data" / "cobblers" / "function" / "mines"


def _fx_approach(spec):
    return approach_of(spec["sites"][0])


@pytest.fixture
def audit_root(tmp_path, monkeypatch):
    import elder_trees
    import ground as GR
    import reapply
    import town_character as TC
    import town_dressing_audit as TDA
    root = tmp_path / "root"
    fn = fx_root(root, monkeypatch)
    state = {"steps": [("R9O", "t", [("fn", "cobblers:mines/build_site_a")])],
             "server": ("cobblers_mines",), "local": ("cobblers_mines",)}
    monkeypatch.setattr(MA, "ROOT", root)
    monkeypatch.setattr(MA, "SPEC", root / "data" / "mines.json")
    monkeypatch.setattr(MA, "PACK", root / "build" / "datapacks" / "cobblers_mines")
    monkeypatch.setattr(MA, "FN", fn)
    monkeypatch.setattr(MA, "OUT", root / "derived" / "mines" / "audit.json")
    monkeypatch.setattr(TDA, "ROOT", root)
    monkeypatch.setattr(GR, "Ground", FakeGround)
    monkeypatch.setattr(TC, "default_pack_dir", lambda: None)
    monkeypatch.setattr(TC, "default_vanilla_jar", lambda: None)
    monkeypatch.setattr(elder_trees, "painted_water", lambda h, w: np.zeros(h.shape, bool))

    def run():
        with monkeypatch.context() as m:
            poison = types.ModuleType("mines")
            poison.__getattr__ = lambda n: (_ for _ in ()).throw(AssertionError("the audit used the generator: " + n))
            m.setitem(sys.modules, "mines", poison)
            m.setattr(reapply, "steps", lambda *a, **k: state["steps"])
            m.setattr(reapply, "SERVER_PACKS", state["server"])
            m.setattr(reapply, "WORLD_LOCAL", state["local"])
            return MA.audit(None)
    return types.SimpleNamespace(root=root, fn=fn, run=run, state=state)


def _edit(path, old, new):
    lines = path.read_text(encoding="utf-8").splitlines()
    hit = [i for i, l in enumerate(lines) if (old(l) if callable(old) else l == old)]
    assert hit, "the fixture has no such line in %s" % path.name
    i = hit[0]
    lines[i:i + 1] = [] if new is None else [new(lines[i]) if callable(new) else new]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_the_audit_passes_the_clean_face_beside_its_near_misses(audit_root):
    # Without it an audit that refuses everything would look like one that works.
    probs, notes = audit_root.run()
    assert probs == []
    assert notes["faces"] == 1 and notes["cells written by the build functions"] > 270


def _j(root, rel):
    return json.loads((root / rel).read_text(encoding="utf-8"))


def _put(root, rel, obj):
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(json.dumps(obj), encoding="utf-8")


def f_unfiltered_fill(a):
    _edit(a.fn / "faces" / "fa_v3.mcfunction", lambda l: l.startswith("fill "), lambda l: l.split(" replace ")[0])


def f_no_pokemon_guard(a):
    _edit(a.fn / "faces" / "check_fa.mcfunction", lambda l: "cobblemon:pokemon" in l, None)


def f_no_player_guard(a):
    _edit(a.fn / "faces" / "check_fa.mcfunction", lambda l: l.startswith("execute if entity @a["), None)


def f_guard_after_the_restore(a):
    p = a.fn / "faces" / "check_fa.mcfunction"
    lines = p.read_text(encoding="utf-8").splitlines()
    g = next(l for l in lines if "cobblemon:pokemon" in l)
    lines.remove(g)
    lines.append(g)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def f_one_corner_unchecked(a):
    _edit(a.fn / "faces" / "check_fa.mcfunction", lambda l: l.startswith("execute unless loaded"), None)


def f_no_period_check(a):
    _edit(a.fn / "faces" / "check_fa.mcfunction", lambda l: "< #period" in l, None)


def f_short_period(a):
    _edit(a.fn / "load.mcfunction", lambda l: l.startswith("scoreboard players set #period"),
          lambda l: "scoreboard players set #period mn.t 1200")


def f_unguarded_ore(a):
    _edit(a.fn / "faces" / "fa_v2.mcfunction", lambda l: l.startswith("execute if block"),
          lambda l: l.split(" run ", 1)[1])


def f_ore_outside_the_box(a):
    _edit(a.fn / "faces" / "fa_v1.mcfunction", lambda l: l.startswith("execute if block"),
          lambda l: "execute if block 44 99 52 %s run setblock 44 99 52 cobblemon:water_stone_ore" % TAG)


def f_foreign_block_in_a_variant(a):
    _edit(a.fn / "faces" / "fa_v1.mcfunction", lambda l: l.startswith("execute if block"),
          lambda l: l.rsplit(" ", 1)[0] + " minecraft:coal_ore")


def f_repeats_its_last_variant(a):
    _edit(a.fn / "faces" / "restore_fa.mcfunction", lambda l: "scoreboard players add #v" in l, None)


def f_no_time_stamp(a):
    _edit(a.fn / "faces" / "restore_fa.mcfunction", lambda l: l.endswith("mn.last = #now mn.t"), None)


def f_filler_ore_in_the_build(a):
    p = a.fn / "build_site_a.mcfunction"
    p.write_text(p.read_text(encoding="utf-8") + "setblock 44 90 53 minecraft:coal_ore\n", encoding="utf-8")


def f_stray_bedrock(a):
    p = a.fn / "build_site_a.mcfunction"
    p.write_text(p.read_text(encoding="utf-8") + "setblock 44 90 58 minecraft:bedrock\n", encoding="utf-8")


def f_wall_across_the_cut(a):
    p = a.fn / "build_site_a.mcfunction"
    p.write_text(p.read_text(encoding="utf-8") + "fill 39 94 45 49 102 45 minecraft:stone\n", encoding="utf-8")


def f_rock_before_the_face(a):
    p = a.fn / "build_site_a.mcfunction"
    p.write_text(p.read_text(encoding="utf-8") + "setblock 44 96 49 minecraft:stone\n", encoding="utf-8")


def f_lot_on_the_cut(a):
    _put(a.root, "derived/towns/town_a_plan.json", {"lots": [{"id": "L1", "rect": [48, 40, 60, 48]}]})


def f_street_on_the_cut(a):
    d = _j(a.root, "data/placements.json")
    d["settlements"]["town_a"]["plan"]["streets"] = [{"id": "s", "polyline": [[20, 44], [30, 44], [39, 44]], "width": 1}]
    _put(a.root, "data/placements.json", d)


def f_event_site_on_the_cut(a):
    _put(a.root, "data/scenes.json", {"scenes": [{"id": "ev", "area": {"from": [30, 90, 45], "to": [39, 110, 46]}}]})


def f_water_change_within_8(a):
    ch = np.load(a.root / "derived" / "water_shape" / "changed.npy")
    ch[32, 44] = True
    np.save(a.root / "derived" / "water_shape" / "changed.npy", ch)


def f_water_map_missing(a):
    (a.root / "derived" / "water_shape" / "changed.npy").unlink()


def f_trader_on_the_cut(a):
    d = _j(a.root, "data/traders.json")
    d["traders"].append({"id": "t2", "settlement": "town_a", "stock": "regional", "position": {"x": 44, "y": 94, "z": 45}})
    _put(a.root, "data/traders.json", d)


def f_container_in_the_tag(a):
    p = a.root / "build" / "datapacks" / "cobblers_mines" / "data" / "cobblers" / "tags" / "block" / "face_resettable.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["values"].append("minecraft:barrel")
    p.write_text(json.dumps(d), encoding="utf-8")


def f_exchange_buys(a):
    d = _j(a.root, "data/traders.json")
    d["stock_policy"]["stones"]["buys"] = True
    _put(a.root, "data/traders.json", d)


def f_exchange_short_a_stone(a):
    d = _j(a.root, "data/traders.json")
    d["stock_policy"]["stones"]["items"] = []
    _put(a.root, "data/traders.json", d)


def f_exchange_elsewhere(a):
    d = _j(a.root, "data/traders.json")
    d["traders"][0]["settlement"] = "town_a"
    _put(a.root, "data/traders.json", d)


def f_bank_buys_a_stone(a):
    _put(a.root, "modpack/config/cobbledollars/bank.json", {"bank": [{"item": "cobblemon:water_stone", "price": 1}]})


def f_no_r9o(a):
    a.state["steps"] = []


def f_r9o_misses_the_site(a):
    a.state["steps"] = [("R9O", "t", [])]


def f_not_world_local(a):
    a.state["local"] = ()


def f_site_never_driven(a):
    _edit(a.fn / "drive.mcfunction", lambda l: "site_site_a" in l, None)


def f_face_never_checked(a):
    _edit(a.fn / "site_site_a.mcfunction", lambda l: "check_fa" in l, None)


def f_no_pack(a):
    import shutil
    shutil.rmtree(a.fn)


def f_empty_build(a):
    (a.fn / "build_site_a.mcfunction").write_text("# nothing\n", encoding="utf-8")


def f_no_face_in_the_data(a):
    d = _j(a.root, "data/mines.json")
    d["sites"][0]["faces"] = []
    _put(a.root, "data/mines.json", d)


FAULTS = [
    (f_unfiltered_fill, "the first command is not the filtered fill"),
    (f_no_pokemon_guard, "@e[type=cobblemon:pokemon"),
    (f_no_player_guard, "the check lacks, before the restore: execute if entity @a["),
    (f_guard_after_the_restore, "@e[type=cobblemon:pokemon"),
    (f_one_corner_unchecked, "execute unless loaded"),
    (f_no_period_check, "< #period mn.t"),
    (f_short_period, "driver: the load sets the period"),
    (f_unguarded_ore, "an unguarded or foreign command"),
    (f_ore_outside_the_box, "ore outside the box"),
    (f_foreign_block_in_a_variant, "an unguarded or foreign command"),
    (f_repeats_its_last_variant, "may repeat the last variant"),
    (f_no_time_stamp, "does not stamp its time"),
    (f_filler_ore_in_the_build, "is a spawn condition"),
    (f_stray_bedrock, "no bedrock skin"),
    (f_wall_across_the_cut, "no walk from"),
    (f_rock_before_the_face, "cells before the face are not written air"),
    (f_lot_on_the_cut, "on lot L1"),
    (f_street_on_the_cut, "street"),
    (f_event_site_on_the_cut, "event site ev"),
    (f_water_change_within_8, "within 8 of a column the water export changes"),
    (f_water_map_missing, "no derived/water_shape/changed.npy"),
    (f_trader_on_the_cut, "within 1 of trader t2"),
    (f_container_in_the_tag, "is a container"),
    (f_exchange_buys, "buys: false"),
    (f_exchange_short_a_stone, "exchange: sells"),
    (f_exchange_elsewhere, "the design has one, in the Mining Town"),
    (f_bank_buys_a_stone, "buys ['cobblemon:water_stone'] back"),
    (f_no_r9o, "has no R9O"),
    (f_r9o_misses_the_site, "R9O runs"),
    (f_not_world_local, "not a world-local server pack"),
    (f_site_never_driven, "the drive never runs this site"),
    (f_face_never_checked, "its site never checks it"),
    (f_no_pack, "no pack"),
    (f_empty_build, "the build function writes nothing"),
    (f_no_face_in_the_data, "no site with a face"),
]


@pytest.mark.parametrize("fault,words", FAULTS, ids=[f.__name__[2:] for f, _w in FAULTS])
def test_the_audit_names_each_planted_fault(audit_root, fault, words):
    # Without it the audit could pass a pack that buries a player, deletes a chest, drops filler or loses a site.
    fault(audit_root)
    probs, _notes = audit_root.run()
    assert any(words in p for p in probs), probs


def f_critical_leg_through_the_cut(a):
    _put(a.root, "derived/routes/critical_legs.json", {"legs": [{"polyline": [[44, 0], [44, 47]]}]})


def f_critical_leg_3_from_the_backing(a):
    # the backing's east edge is x 50; the clean root's leg is at x 54 (4 away), this one at x 53 (3 away)
    _put(a.root, "derived/routes/critical_legs.json", {"legs": [{"polyline": [[53, 0], [53, 127]]}]})


def f_data_corridor_through_the_cut(a):
    _put(a.root, "data/routes.json", {"routes": [{"id": "r", "corridor": {"polyline": [{"x": 0, "z": 45},
                                                                                        {"x": 127, "z": 45}]}}]})


def f_legs_file_missing(a):
    (a.root / "derived" / "routes" / "critical_legs.json").unlink()


LEG_FAULTS = [
    (f_critical_leg_through_the_cut, "of a routed leg"),
    pytest.param(f_critical_leg_3_from_the_backing, "within 3 of a routed leg", marks=pytest.mark.xfail(
        strict=True, reason="tools/mines_audit.py:300: `seg_distance(...) < LEG_MARGIN` passes a column exactly 3 from "
        "a leg, which its own message calls 'within 3' and the generator's Mask forbids (tools/town_dressing.py:84-92 "
        "grow(): every cell with |dx|, |dz| <= 3); the audit is one block looser than the rule it checks")),
    (f_data_corridor_through_the_cut, "of a routed leg"),
    (f_legs_file_missing, "no derived/routes/critical_legs.json"),
]


@pytest.mark.parametrize("fault,words", LEG_FAULTS, ids=["through_the_cut", "3_from_the_backing", "data_corridor",
                                                         "legs_file_missing"])
def test_the_audit_names_a_route_leg_near_a_cut_and_a_missing_legs_file(audit_root, fault, words):
    # Without it a face cut across a road players must walk would pass the audit (the design: none on a route leg),
    # and a checkout without the legs file would pass it unchecked.
    fault(audit_root)
    probs, _notes = audit_root.run()
    assert any(words in p for p in probs), probs


# ================================================================================ 5. the Exchange and R9O

def test_the_exchange_sells_exactly_the_ten_stones_at_a_price_and_buys_none():
    # Without it the Assayer could miss a stone (no catch-up), sell something else, or buy stones back (a money printer).
    import traders as TR
    ex = [t for t in TRADERS["traders"] if t.get("stock") == "stones"]
    assert [t["id"] for t in ex] == ["mining_assayer"] and ex[0]["settlement"] == "mining_town"
    fp = TOWNS["mining_town"]["footprint"]
    p = ex[0]["position"]
    assert fp["min_x"] <= p["x"] <= fp["max_x"] and fp["min_z"] <= p["z"] <= fp["max_z"]
    pol = TRADERS["stock_policy"]["stones"]
    assert pol["buys"] is False and sorted(pol["items"]) == sorted("cobblemon:%s_stone" % s for s in TEN_STONES)
    template = {"CobbleMerchantShop": [{"Category": "Balls", "Offers": [{"Item": {"count": 1, "id": "cobblemon:poke_ball"},
                                                                          "Price": "200"}]}], "NoAI": 1}
    out, kept, _held = TR.apply_stock_policy(template, TRADERS["stock_policy"], "stones")
    offers = [o for cat in out["CobbleMerchantShop"] for o in cat["Offers"]]
    assert sorted(o["Item"]["id"] for o in offers) == sorted(pol["items"]) and sorted(kept) == sorted(pol["items"])
    assert all(o["Item"]["count"] == 1 and re.fullmatch(r"[1-9]\d*", o["Price"]) for o in offers)
    assert out["NoAI"] == 1
    assert not [pr for rid, pr in TR.static_problems(TRADERS) if rid == "mining_assayer"]
    for bank in list((ROOT / "base-pack").rglob("bank.json")) + list((ROOT / "modpack").rglob("bank.json")) + \
            list((ROOT / "server").rglob("bank.json")):
        items = {e.get("item") for e in json.loads(bank.read_text(encoding="utf-8")).get("bank") or []}
        assert not items & set(pol["items"]), bank


def _steps(monkeypatch):
    import ambient
    import reapply
    monkeypatch.setattr(reapply, "indexed", lambda pack, folder: [])
    monkeypatch.setattr(ambient, "placement_steps", lambda *a, **k: [])
    try:
        return reapply.steps()
    except SystemExit as e:
        pytest.skip("NOT_EXECUTED: reapply.steps() needs a local-only input here: %s" % e)


def test_r9o_runs_every_sites_build_once_after_r9s_and_before_r9dc_and_r9e(monkeypatch):
    # Without it an export would erase a place's faces for good, or build them before the cavern they cut into.
    steps = _steps(monkeypatch)
    ids = [s for s, _t, _a in steps]
    assert ids.count("R9O") == 1
    (acts,) = [a for s, _t, a in steps if s == "R9O"]
    assert acts == [("fn", "cobblers:mines/build_%s" % s["id"]) for s in SITES]
    assert ids.index("R2") < ids.index("R8") < ids.index("R9S") < ids.index("R9O") < ids.index("R9DC") < ids.index("R9E")
    assert all(s.get("reapply_step") == "R9O" for s in SITES)


def test_the_mines_pack_is_world_local_and_prepare_builds_it_then_audits_it():
    # Without it the tick driver would run in every world the server loads, or an unaudited pack could be installed.
    import reapply
    assert "cobblers_mines" in reapply.SERVER_PACKS and "cobblers_mines" in reapply.WORLD_LOCAL
    assert "cobblers_mines" not in reapply.EXCLUDED
    calls = re.findall(r'py\(TOOLS / "([a-z_]+\.py)"(?:, "([a-z]+)")?', inspect.getsource(reapply.prepare))
    order = [c[0] for c in calls]
    assert ("mines.py", "build") in calls
    assert order.index("mines.py") < order.index("mines_audit.py")
    for before_ in ("town_dressing.py", "ambient.py", "cavern_plan.py"):
        assert order.index(before_) < order.index("mines.py"), before_


# ================================================================================ 6. heightmap and local-only inputs

def _ground():
    if not os.environ.get("COBBLERS_SOURCE_ROOT"):
        pytest.skip("NOT_EXECUTED: COBBLERS_SOURCE_ROOT is not set: the canonical heightmap is outside the repo")
    import ground as GR
    try:
        return GR.Ground()
    except (SystemExit, FileNotFoundError, OSError) as e:
        pytest.skip("NOT_EXECUTED: the canonical heightmap did not load: %s" % e)


SURFACE = [(s, f) for s, f in FACES if s.get("ground") != "cavern_floor"]


@pytest.fixture(scope="module")
def surface_writes():
    """{face id: (cells, geometry)} of every surface face's build, on the canonical heightmap."""
    g = _ground()
    out = {}
    for s, f in SURFACE:
        gm = M.geometry(f, g, GEO, s.get("bedrock_skin", False))
        entry = {"site": s, "faces": [{"face": f, "geometry": gm,
                                       "variants": [M.ore_cells(f, 0, SPEC["seed"], GEO, f["yield"])]}]}
        out[f["id"]] = (_replay(M.build_lines(SPEC, entry)), gm)
    return g, out


def test_every_box_has_two_blocks_of_rock_over_it_and_the_city_faces_are_deep_underground():
    # Without it a face's top would show through the ground, or a cavern face be open to the sky.
    g = _ground()
    for s, f in FACES:
        x0, _y0, z0, x1, y1, z1 = f["box"]
        low = int(g.box(x0, z0, x1, z1).min())
        if s.get("ground") == "cavern_floor":
            assert low >= y1 + 40, (f["id"], low, y1)
        else:
            assert low >= y1 + GEO["backing"], (f["id"], low, y1)


def _walk_out(start, world, ground):
    cols = {(x, z) for x, _y, z in world}

    def solid(x, y, z):
        b = world.get((x, y, z))
        return name_of(b) not in AIRS if b is not None else y <= ground(x, z)
    seen, dq = {start}, deque([start])
    while dq:
        x, y, z = dq.popleft()
        if (x, z) not in cols:
            return True
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy, z + dz)
                if n in seen or solid(*n) or solid(n[0], n[1] + 1, n[2]) or not solid(n[0], n[1] - 1, n[2]):
                    continue
                if dy == 1 and solid(x, y + 2, z):
                    continue
                seen.add(n)
                dq.append(n)
    return False


def test_every_surface_face_can_be_walked_up_to_and_out_of(surface_writes):
    # Without it a cut could leave a player in a pit with no way out, or the face behind a wall of rock.
    g, out = surface_writes
    for s, f in SURFACE:
        world, gm = out[f["id"]]
        assert gm["problems"] == [], (f["id"], gm["problems"][:2])
        x0, y0, z0, x1, y1, z1 = f["box"]
        xz = front_frame(f["box"], f["front"])
        W, _D = along_and_deep(f["box"], f["front"])
        for u in range(W):
            x, z = xz(u, -1)
            assert all(world.get((x, y, z)) in AIRS for y in range(y0, y1 + 1)), (f["id"], u)
            assert name_of(world.get((x, y0 - 1, z), "minecraft:air")) not in AIRS, (f["id"], u)
        x, z = xz(W // 2, -1)
        assert _walk_out((x, y0, z), world, g), f["id"]


def _seg(px, pz, a, b):
    (ax, az), (bx, bz) = a, b
    vx, vz = bx - ax, bz - az
    L2 = vx * vx + vz * vz
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * vx + (pz - az) * vz) / L2))
    return math.hypot(px - (ax + t * vx), pz - (az + t * vz))


def test_no_surface_face_writes_on_a_leg_street_building_event_site_dressing_or_worker(surface_writes):
    # Without it a cut could open across a road, a street, a house, an event's stage or another system's piece.
    import nbt
    _g, out = surface_writes
    legs = [[(q["x"], q["z"]) for q in (r.get("corridor") or {}).get("polyline") or []]
            for r in json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))["routes"]]
    crit = ROOT / "derived" / "routes" / "critical_legs.json"
    if crit.is_file():
        legs += [[tuple(p) for p in leg.get("polyline") or []] for leg in json.loads(crit.read_text())["legs"]]
    scenes = [sc for sc in json.loads((ROOT / "data" / "scenes.json").read_text(encoding="utf-8"))["scenes"] if sc.get("area")]
    dress = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))["towns"]
    workers = json.loads((ROOT / "data" / "ambient.json").read_text(encoding="utf-8"))["workers"]
    kc = SPEC["keep_clear"]
    for s, f in SURFACE:
        cols = {(x, z) for x, _y, z in out[f["id"]][0]}
        fp = TOWNS[s["settlement"]]["footprint"]
        assert all(fp["min_x"] - 24 <= x <= fp["max_x"] + 24 and fp["min_z"] - 24 <= z <= fp["max_z"] + 24 for x, z in cols)
        near = [c for c in cols for leg in legs for a, b in zip(leg, leg[1:]) if _seg(c[0], c[1], a, b) <= 3]
        assert not near, (f["id"], "route leg", near[:1])
        for st in (PLACEMENTS["settlements"].get(s["settlement"], {}).get("plan") or {}).get("streets") or []:
            pts = [tuple(p) for p in st.get("polyline") or []]
            half = int(st.get("width", 1)) // 2
            on = [c for c in cols if min((_seg(c[0], c[1], a, b) for a, b in zip(pts, pts[1:])), default=1e9) <= half + 0.5]
            assert not on, (f["id"], "street", st.get("id"), on[:1])
        for q in PLACEMENTS["placements"]:
            if q.get("kind") == "earthwork" or not q.get("position"):
                continue
            size = q.get("size")
            if not size and q.get("file") and (ROOT / q["file"]).is_file():
                size = nbt.load(ROOT / q["file"])[1]["size"]
            if not size:
                continue
            w_, d_ = (size[2], size[0]) if (q.get("rotation") or "none") in ("clockwise_90", "counterclockwise_90") else (size[0], size[2])
            bx, bz = q["position"]["x"], q["position"]["z"]
            on = [c for c in cols if bx - 3 <= c[0] <= bx + w_ + 2 and bz - 3 <= c[1] <= bz + d_ + 2]
            assert not on, (f["id"], "building", q["id"], on[:1])
        for sc in scenes:
            a, b = sc["area"]["from"], sc["area"]["to"]
            on = [c for c in cols if min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[2], b[2]) <= c[1] <= max(a[2], b[2])]
            assert not on, (f["id"], "event site", sc["id"])
        rec = dress.get(s["settlement"]) or {}
        for p in ([rec["landmark"]] if rec.get("landmark") else []) + list(rec.get("pieces") or []):
            px, pz = p["at"][:2]
            on = [c for c in cols if max(abs(c[0] - px), abs(c[1] - pz)) <= kc["dressing_reach"]]
            assert not on, (f["id"], "dressing", p.get("id"))
        for wk in workers:
            if wk["settlement"] != s["settlement"]:
                continue
            pts = [tuple(p) for p in wk.get("route") or []] or [tuple(wk["at"][:2])]
            pts = pts * 2 if len(pts) == 1 else pts
            on = [c for c in cols if min(_seg(c[0], c[1], a, b) for a, b in zip(pts, pts[1:])) <= kc["ambient_reach"]]
            assert not on, (f["id"], "worker", wk["id"])


def test_no_written_column_is_within_8_of_a_column_the_water_export_changes(surface_writes):
    # Without it a face could be cut into a shore the pending water export moves, and the export would undo it.
    p = ROOT / "derived" / "water_shape" / "changed.npy"
    if not p.is_file():
        pytest.skip("NOT_EXECUTED: no derived/water_shape/changed.npy here (python tools/water_shape.py)")
    ch = np.load(p, mmap_mode="r")
    _g, out = surface_writes
    n = SPEC["keep_clear"]["water_changed_reach"]
    assert n >= 8
    for _s, f in SURFACE:
        for x, _y, z in out[f["id"]][0]:
            assert not np.asarray(ch[z - n:z + n + 1, x - n:x + n + 1]).any(), (f["id"], x, z)


def test_the_built_pack_drives_each_site_over_the_approach_box_the_data_describes():
    # Without it the built driver could watch a box that misses a face, so it never restores.
    pack = built_pack()
    if pack is None:
        pytest.skip("NOT_EXECUTED: no built build/datapacks/cobblers_mines here (python tools/mines.py build)")
    drive = (pack / "data" / "cobblers" / "function" / "mines" / "drive.mcfunction").read_text(encoding="utf-8")
    for s in SITES:
        a = approach_of(s)
        line = "execute if entity @a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d] run function cobblers:mines/site_%s" % (
            a[0], a[1], a[2], a[3] - a[0], a[4] - a[1], a[5] - a[2], s["id"])
        assert line in drive.splitlines(), s["id"]


def test_the_full_audit_is_clean_on_the_real_inputs():
    # Without it a real face on a lot, a street or a changing shore could go unnoticed where only the main session looks.
    need = [ROOT / "build" / "datapacks" / "cobblers_mines", ROOT / "derived" / "water_shape" / "changed.npy",
            ROOT / "derived" / "cavern" / "plan.json", ROOT / "derived" / "ambient" / "plan.json"]
    missing = [str(p.relative_to(ROOT)) for p in need if not p.exists()]
    if missing or not os.environ.get("COBBLERS_SOURCE_ROOT"):
        pytest.skip("NOT_EXECUTED: local-only inputs missing: %s" % (missing or "COBBLERS_SOURCE_ROOT"))
    probs, notes = MA.audit(None)
    assert probs == [] and notes["faces"] == 22
