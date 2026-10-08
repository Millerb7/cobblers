#!/usr/bin/env python
"""Arrow Creeks Farm's independent audit: the BUILT packs read back and judged against data, the heightmap and the
Cobblemon jar -- never against tools/pokemon_farm.py, which this file does not import.

Written 2026-10-05 by an agent that built none of the farm (CLAUDE.md principle 16). The builder's list of WHAT to check
is data/pokemon_farm.json audit_checklist; HOW, and every expectation, is derived here:

  writes    build/datapacks/cobblers_pokemon_farm's build function parsed by this file's own reader and replayed over a
            world made of the canonical heightmap alone (round(h): stone at and under it, air over). Every write inside
            the record's bbox and the forceload the function says holds it; every id in blocks.ids and a vanilla 1.21.1
            block (the vanilla jar's blockstates); no chest or bed; no block data/spawn_blocks.json names unless a
            data/spawn_block_policy.json entry whose scope names this farm whitelists it; nothing under its column's
            ground; nothing on a wet column (tools/water_mask.py and the rivers, through
            southern_residents_audit.Water); the plant clears are air-replace of logs, leaves and replaceables only.
  floors    a building's floor at the HIGHEST round(ground) under its footprint (the record's ground_rule), solid from
            each column's ground up to it; a fence on its own column's ground + 1; a field's farmland at its ground.
  links     every fence and pane state's four connections against its replayed neighbours, by vanilla's rule
            (FenceBlock.connectsTo: another fence of its kind, a gate whose span crosses it, or a sturdy full face that
            is not a leaf, pumpkin or jack o'lantern); every gate across its line.
  pens      every fence piece closed: a walker's flood (tools/ambient_idle_audit.enclosure, vanilla's movement: one
            block up, three down, never over a fence) from inside never leaves the rectangle; every column of the outer
            wall a fence or gate; and with the gates opened it does get out (a pen is a pen, not a box).
  doors     lower and upper halves paired; side-by-side doors hinged opposite. ROOFS: on every gabled piece the stairs
            face the ridge and rise one a row toward it, and a ridge (slab, or two stair rows back to back) closes it.
  animals   from data/pokemon_farm.json animals: each id once; its spot ("ground": round(ground) + 1; a building's name:
            that building's floor + 1); its body (the JAR's hitbox x baseScale, and data's species table must say the
            same) clear of every replayed collision cell, something under its feet; every AI-on one penned with its
            home disc (data/ambient.json idle.rules.follower_home_radius) inside and rules.follower_pen_margin from the
            fence; an extra behaviour only where the species' own jar file lists it in ai[].behaviours (so eats-grass
            for Mareep/Wooloo/Dubwool, the bee behaviour for Combee: Miltank gets neither) and never on a still one;
            every AI-on species with the jar feature `sheared` carries cobblemon:pokemon_eats_grass and grazes on
            written grass_block (EatGrassTask eats minecraft:grass_block); Pokemon + the two NPCs <= cap_per_town.
  claims    (--animals, after ambient_idle:build) build/datapacks/cobblers_ambient_idle read back: every record animal
            spawned by exactly one idler, matched by POSITION and species (not by id), all in the keep group named by
            the data/markets.json place whose source is this record, no other idler inside the bbox; the still ones
            NoAI 1b and tp'd to their spot, the AI ones NoAI 0b with home = spot, the home walk, and penned; the extra
            behaviours as above, read from the CLAIM; the workers' flags (Persistence, Invulnerable, Unbattleable,
            empty DeathLootTable, and cobblers_ambient's own when built) and `uncatchable`; keep_all's gate reaches
            every one; the count with the farm's NPCs and any other pack's literal spawn inside the bbox <= the cap.
  seats     data/npc_seats.json's farmer and data/markets.json's stand keeper at round(ground) + 1, the record's feet,
            feet and head free of collision in the replay with something under, rules.npc_gap apart, not on an animal;
            the farmer's conversation and quest exist and tools/compile_dialogue.py builds the conversation.
  siting    re-derived from the other data files, not from the generator: every written column at least
            rules.authored_clearance from every x/z another data file authors (southern_residents_audit.authored, this
            record and its own seat, stall, conversation and quest skipped) and every data/routes.json box as a filled
            rectangle; outside every town footprint + clearance, every Rift zone box, data/far_south.json's keep-out,
            data/southern_residents.json's Mega farm keep-out, data/gulch_mine.json's Mega field and gulch polygons
            (and clearance from them), rules.keep_out (which must hold data/apricorn_farm.json's site centre); every
            Habitat Block (natural range_of_influence, activated spawn_range, planned or placed) farther than its range
            from every column; the centre and both NPCs rules.path_clearance (= encounter_design hearts
            clear_of_path_blocks) from data/route_paths.json; site.measured's "yN at the centre"; cell and sub-region.
  stand     data/markets.json's stall: its place in places_beyond_towns and no_counter, tools/markets.py's stall rules
            (stall_problems) clean for it, and here: every line ungated, minecraft:, dividing by its count, its unit
            above the bank's sell-back, no spawn-condition block; the critical-path curve identical with and without it.
  wiring    tools/reapply.py: prepare jobs pokemon_farm -> pokemon_farm_audit, pokemon_farm -> ambient_idle:build ->
            pokemon_farm_audit:animals; R9FS < R9PF < R9E, R9PF = pokemon_farm.placement_steps(); the pack in
            SERVER_PACKS, not WORLD_LOCAL, and it carries no tick or load tag.

Independence is proved by MUTATING THE GENERATOR, data/pokemon_farm.json untouched (tests/test_pokemon_farm_audit.py).

Not covered (needs a running game): that the blocks land; that shears work on the farm's unowned flock and the
fleece regrows (read from the jar: PokemonEntity.method_5992's shears branch runs when the owner UUID is the player's
OR null, then method_27072 reads the `sheared` flag; EatGrassTask reads `sheared`, eats minecraft:grass_block, calls
method_5983 -- javap 2026-10-05); that a bucket on a farm Miltank does nothing (OwnerQueryRequirement.check returns
false when getOwnerEntity() is null); the honey; that followers stay in their pens under Cobblemon's pathing; the frame
rate. Foliage the export grows is not in the replay (the clears are judged, not their effect).

  python tools/pokemon_farm_audit.py [--source-root R] [--pack DIR] [--jar JAR]            the blocks (after pokemon_farm)
  python tools/pokemon_farm_audit.py --animals [--idle-pack DIR] ...                       + the claims (after ambient_idle:build)
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ambient_idle_audit as AIA  # noqa: E402  (an audit: the enclosure rule is shared with it)
import southern_residents_audit as SA  # noqa: E402  (an audit, not a generator)

# The ground rule (tools/ground_rule.py): nothing here reads a world.
WORLD_READS: set = set()

DATA = ROOT / "data"
PACKS = ROOT / "build" / "datapacks"
RECORD = "pokemon_farm.json"
SCHEMA = "cobblers.pokemon-farm/1"
GENERATOR = "pokemon_farm"
IDLE_JOB = "ambient_idle:build"
ANIMALS_JOB = "pokemon_farm_audit:animals"
STEP_AFTER, STEP_BEFORE = "R9FS", "R9E"        # the brief and audit_checklist: after the far south, before the Habitat Blocks
CLEAR_TAGS = ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable")
NEVER = ("minecraft:chest", "minecraft:trapped_chest", "minecraft:ender_chest")
EATS_GRASS = "cobblemon:pokemon_eats_grass"
HOME_WALK = "cobblemon:stationary"
SHEARED = "sheared"
WORKER_FLAGS = {"PersistenceRequired", "Invulnerable", "Unbattleable", "DeathLootTable:empty"}
# FenceBlock.isExceptionForConnection (vanilla 1.21.1): never joined though full
NO_JOIN = ("leaves", "barrier", "pumpkin", "carved_pumpkin", "jack_o_lantern", "melon", "shulker_box")
# shapes whose side face is not a full sturdy square: a fence does not join them (by suffix, then by name; a block
# with no collision at all is never full -- ambient_idle_audit.collides)
NOT_FULL_SUFFIX = ("_stairs", "_slab", "_fence", "_fence_gate", "_wall", "_pane", "_door", "_trapdoor", "_sign",
                   "_carpet", "_button", "_pressure_plate", "_bed", "_candle", "_head", "_skull", "_banner", "_cauldron",
                   "_lantern", "_campfire", "_chain", "_anvil", "_rod", "_bars")
NOT_FULL_NAME = {"lantern", "farmland", "dirt_path", "cauldron", "campfire", "azalea", "flowering_azalea", "flower_pot",
                 "grindstone", "anvil", "ladder", "bell", "chest", "trapped_chest", "ender_chest", "scaffolding", "cake",
                 "lectern", "enchanting_table", "stonecutter", "hopper", "brewing_stand", "end_rod", "lightning_rod",
                 "iron_bars", "glass_pane", "chain", "candle", "snow", "water", "lava", "conduit",
                 "bamboo", "cactus", "dragon_egg", "sea_pickle", "turtle_egg", "big_dripleaf", "pointed_dripstone"}
FACES = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}

# Defects this audit found in the committed build, reported and NOT fixed here (the farm is not this agent's). Each is
# printed as KNOWN and does not fail the run; a KNOWN entry that no longer fires is STALE and does fail, so the list
# cannot outlive its defect. (check, text the error contains, ruling)
KNOWN = [
    ("links", "the gate at (3165, 90, 5688) (facing south) is not across its line",
     "2026-10-05, first run: the cow pasture's north gate [14..16, -26] stands on ground y89, the post east of it "
     "[17, -26] on y88, so the post's rail tops out at y89 and its lantern stands at y90 beside the gate. "
     "tools/pokemon_farm.py piece_fence raises a post to a higher NEIGHBOUR's rail but skips gate neighbours "
     "(`(nx, nz) not in gates`), so a gate one above its post is left beside a lantern. The pen still holds (the "
     "flood finds no way out); the line is visibly broken. Builder: raise a post beside a higher gate too"),
]

jload = SA.jload
Report = SA.Report


def base(state):
    return state.split("[")[0].split("{")[0]


def short(state):
    b = base(state)
    return b.split(":", 1)[1] if ":" in b else b


def props(state):
    m = re.match(r"^[^\[{]*\[([^\]]*)\]", state)
    return dict(kv.split("=", 1) for kv in m.group(1).split(",") if "=" in kv) if m else {}


def classify(errors, known=None):
    """(real, known_hits, stale)."""
    known = KNOWN if known is None else known
    real, hits = [], []
    for e in errors:
        (hits if any(e.startswith(c + ":") and t in e for c, t, _w in known) else real).append(e)
    stale = [k for k in known if not any(e.startswith(k[0] + ":") and k[1] in e for e in errors)]
    return real, hits, stale


# ------------------------------------------------------------------ the pack, read by this file


SET = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S.*)$")
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: (replace) (\S+)| (keep|destroy|hollow|outline))?$")
HOLD = re.compile(r"forceload add (-?\d+) (-?\d+) (-?\d+) (-?\d+)")


class Replay:
    """The build function's writes in order: blocks {(x, y, z): state}, clears [(x0, y0, z0, x1, y1, z1, state,
    filter)], lines it cannot read, and the forceload its header says holds it."""

    def __init__(self, text):
        self.blocks, self.clears, self.bad, self.hold = {}, [], [], None
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                h = HOLD.search(line)
                if h and self.hold is None:
                    self.hold = tuple(int(v) for v in h.groups())
                continue
            s, f = SET.match(line), FILL.match(line)
            if s:
                self.blocks[(int(s.group(1)), int(s.group(2)), int(s.group(3)))] = s.group(4)
            elif f:
                c = [int(v) for v in f.groups()[:6]]
                st = f.group(7)
                lo = (min(c[0], c[3]), min(c[1], c[4]), min(c[2], c[5]))
                hi = (max(c[0], c[3]), max(c[1], c[4]), max(c[2], c[5]))
                if f.group(8):
                    self.clears.append(lo + hi + (st, f.group(9)))
                    continue
                if f.group(10):
                    self.bad.append(line)
                    continue
                for x in range(lo[0], hi[0] + 1):
                    for y in range(lo[1], hi[1] + 1):
                        for z in range(lo[2], hi[2] + 1):
                            self.blocks[(x, y, z)] = st
            else:
                self.bad.append(line)

    def columns(self):
        cols = {(x, z) for x, _y, z in self.blocks}
        for c in self.clears:
            cols |= {(x, z) for x in range(c[0], c[3] + 1) for z in range(c[2], c[5] + 1)}
        return cols


class World:
    """The replay over the heightmap: a written cell is its state; else stone at and under round(ground), water up to
    a wet column's surface, air over. The clears change nothing here: the bare heightmap grows no log, leaf or plant."""

    def __init__(self, replay, g, water=None, override=None):
        self.R, self.g, self.water = replay, g, water
        self.override = override or {}

    def at(self, x, y, z):
        v = self.override.get((x, y, z)) or self.R.blocks.get((x, y, z))
        if v is not None:
            return v
        if y <= self.g(x, z):
            return "minecraft:stone"
        lv = self.water(x, z) if self.water else None
        return "minecraft:water" if lv is not None and y <= lv else "minecraft:air"


def read_build(pack, doc):
    b = doc["build"]
    f = Path(pack) / "data" / b["namespace"] / "function" / b["folder"] / "build.mcfunction"
    if not f.is_file():
        raise SystemExit("pokemon_farm_audit: no %s (run python tools/pokemon_farm.py)" % f)
    return f.read_text(encoding="utf-8")


# ------------------------------------------------------------------ the jar


class Jar:
    """The Cobblemon jar's species: hitbox x baseScale, features, ai[].behaviours."""

    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.path = str(path)
        self.index = {n.rsplit("/", 1)[1][:-5]: n for n in self.z.namelist()
                      if n.startswith("data/cobblemon/species/") and n.endswith(".json")}

    def species(self, name):
        n = self.index.get(name)
        if n is None:
            return None
        d = json.loads(self.z.read(n))
        hb, sc = d.get("hitbox") or {"width": 1, "height": 1}, float(d.get("baseScale", 1))
        ai = set()
        for a in d.get("ai") or []:
            ai |= set(a.get("behaviours") or [])
        return {"width": float(hb["width"]) * sc, "height": float(hb["height"]) * sc,
                "features": set(d.get("features") or []), "ai": ai, "file": n}


def find_jar():
    """The Cobblemon jar on this machine, or None (the caller reports a missing jar as a problem)."""
    import battle_sim
    for p in battle_sim.JAR_CANDIDATES:
        if Path(p).is_file():
            return Path(p)
    home = Path(r"C:\Users\wnd\Documents\github\cobblers")
    hits = sorted(home.rglob("Cobblemon-fabric-1.8*.jar")) if home.is_dir() else []
    return hits[0] if hits else None


def vanilla_blocks():
    """The vanilla 1.21.1 block ids from the client jar's blockstates, or None (the audit then notes it is unchecked)."""
    import town_character as TC
    jar = TC.default_vanilla_jar()
    if jar is None or not Path(jar).is_file():
        return None
    with zipfile.ZipFile(jar) as z:
        return {"minecraft:" + n.rsplit("/", 1)[1][:-5] for n in z.namelist()
                if n.startswith("assets/minecraft/blockstates/") and n.endswith(".json")}


# ------------------------------------------------------------------ shapes


def is_fence(b):
    return b.endswith("_fence")


def is_gate(b):
    return b.endswith("_fence_gate")


def is_pane(b):
    return b.endswith(("glass_pane", "iron_bars"))


def full_face(state):
    n = short(state)
    if any(n == x or n.endswith("_" + x) for x in NO_JOIN):
        return False
    return AIA.collides(state) and not n.endswith(NOT_FULL_SUFFIX) and n not in NOT_FULL_NAME


def joins(me, other_state, direction):
    """Vanilla's connection for a fence or pane `me` (a base id) toward a neighbour state lying in `direction`."""
    o = base(other_state)
    if is_fence(me):
        if is_fence(o):
            return o.endswith("nether_brick_fence") == me.endswith("nether_brick_fence")
        if is_gate(o):
            f = props(other_state).get("facing", "north")
            # FenceGateBlock.connectsToDirection: the gate's facing axis is the direction's clockwise axis
            return (f in ("north", "south")) == (direction in ("east", "west"))
        return full_face(other_state)
    if is_pane(o) or o.endswith("_wall"):
        return True
    return full_face(other_state)


# ------------------------------------------------------------------ the checks


def floors_of(doc, g):
    """{building or silo name: (floor y, [columns])}: the highest round(ground) under its footprint (ground_rule)."""
    cx, cz = doc["site"]["centre"]
    out = {}
    for p in doc["pieces"]:
        if p["kind"] == "building":
            x0, z0, x1, z1 = p["footprint"]
        elif p["kind"] == "silo":
            (sx, sz), r = p["centre"], p["r"]
            x0, z0, x1, z1 = sx - r, sz - r, sx + r, sz + r
        else:
            continue
        cols = [(cx + x, cz + z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
        out[p["name"]] = (max(g(x, z) for x, z in cols), cols)
    return out


def check_writes(doc, R, g, water, rep, spawn, white, vanilla):
    x0, z0, x1, z1 = doc["bbox"]
    ids = set(doc["blocks"]["ids"])
    for line in R.bad[:3]:
        rep.err("writes", "a build line that is neither a setblock, a fill nor a plant clear: %s" % line[:100])
    seen = {}

    def bad(why, st, pos):
        seen[why] = seen.get(why, 0) + 1
        if seen[why] <= 3:
            rep.err("writes", "%s at %s %s" % (st[:70], pos, why))

    for pos, st in sorted(R.blocks.items()):
        b = base(st)
        x, y, z = pos
        if not (x0 <= x <= x1 and z0 <= z <= z1):
            bad("is outside the record's bbox %s" % doc["bbox"], st, pos)
        if b not in ids:
            bad("is not in blocks.ids", st, pos)
        if vanilla is not None and b not in vanilla:
            bad("is not a vanilla 1.21.1 block", st, pos)
        if b in spawn and b not in white:
            bad("is a spawn condition (data/spawn_blocks.json) no data/spawn_block_policy.json entry scoped to this "
                "farm whitelists", st, pos)
        if b in NEVER or b.endswith("_bed"):
            bad("is a chest or a bed", st, pos)
        if y < g(x, z):
            bad("is under its column's ground y%d" % g(x, z), st, pos)
        lv = water(x, z)
        if lv is not None:
            bad("is on a wet column (water y%d)" % lv, st, pos)
    wet = 0
    for c in R.clears:
        if c[6] != "minecraft:air" or c[7] not in CLEAR_TAGS:
            rep.err("writes", "a fill with a filter that is not an air clear of logs, leaves or plants: %s" % (c,))
        if not (x0 <= c[0] and c[3] <= x1 and z0 <= c[2] and c[5] <= z1):
            rep.err("writes", "a clear outside the bbox: %s" % (c[:6],))
        for x in range(c[0], c[3] + 1):
            for z in range(c[2], c[5] + 1):
                lv = water(x, z)
                if lv is not None and c[1] <= lv and wet < 3:
                    wet += 1
                    rep.err("writes", "the clear %s reaches the water y%d at (%d, %d): #minecraft:replaceable holds "
                            "water" % (c[:6], lv, x, z))
    if R.hold is None:
        rep.err("writes", "the build function names no forceload that holds it")
    elif list(R.hold) != list(doc["bbox"]):
        rep.err("writes", "the build's forceload %s is not the record's bbox %s" % (list(R.hold), doc["bbox"]))
    if not R.blocks:
        rep.err("writes", "the build writes nothing")
    rep.note("writes: %d blocks, %d clears" % (len(R.blocks), len(R.clears)))


def check_floors(doc, R, W, g, rep):
    cx, cz = doc["site"]["centre"]
    floors = floors_of(doc, g)
    for p in doc["pieces"]:
        if p["kind"] not in ("building", "silo"):
            continue
        B, cols = floors[p["name"]]
        want = base(p["floor"])
        if p["kind"] == "building":
            x0, z0, x1, z1 = p["footprint"]
            inner = [(cx + x, cz + z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1)]
        else:
            inner = [(cx + p["centre"][0], cz + p["centre"][1])]
        off = [c for c in inner if base(R.blocks.get((c[0], B, c[1]), "")) != want]
        if off:
            rep.err("floors", "%s: the floor (%s) is not at y%d, the highest ground under its footprint, at %d of %d "
                    "inner column(s), e.g. %s holds %s" % (p["name"], want, B, len(off), len(inner), off[0],
                                                          R.blocks.get((off[0][0], B, off[0][1]))))
        under = [c for c in (cols if p["kind"] == "building" else inner)
                 if any(not AIA.collides(W.at(c[0], y, c[1])) for y in range(g(*c) + 1, B))]
        if under:
            rep.err("floors", "%s: %d column(s) with a gap between the ground and the floor y%d, e.g. %s"
                    % (p["name"], len(under), B, under[0]))
    for p in doc["pieces"]:
        if p["kind"] == "fence":
            x0, z0, x1, z1 = p["rect"]
            line = [(x, z) for x in range(x0, x1 + 1) for z in (z0, z1)] + \
                   [(x, z) for z in range(z0 + 1, z1) for x in (x0, x1)]
            miss = [(cx + x, cz + z) for x, z in line
                    if not (is_fence(base(W.at(cx + x, g(cx + x, cz + z) + 1, cz + z)))
                            or is_gate(base(W.at(cx + x, g(cx + x, cz + z) + 1, cz + z))))]
            if miss:
                rep.err("floors", "%s: %d fence-line column(s) without a fence or gate on ground + 1, e.g. %s"
                        % (p["name"], len(miss), miss[0]))
        elif p["kind"] == "field":
            x0, z0, x1, z1 = p["rect"]
            miss = [(cx + x, cz + z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
                    if base(W.at(cx + x, g(cx + x, cz + z), cz + z)) not in (base(p["farmland"]), base(p["path"]))]
            if miss:
                rep.err("floors", "%s: %d column(s) whose ground block is not farmland or path, e.g. %s"
                        % (p["name"], len(miss), miss[0]))
    return floors


def check_links(R, W, rep):
    wrong = []
    for (x, y, z), st in sorted(R.blocks.items()):
        b = base(st)
        if is_fence(b) or is_pane(b):
            pr = props(st)
            for side, (dx, dz) in FACES.items():
                want = joins(b, W.at(x + dx, y, z + dz), side)
                if pr.get(side) != ("true" if want else "false"):
                    wrong.append(((x, y, z), side, pr.get(side), want, short(W.at(x + dx, y, z + dz))))
        elif is_gate(b):
            f = props(st).get("facing", "north")
            span = ((1, 0), (-1, 0)) if f in ("north", "south") else ((0, 1), (0, -1))
            ends = [base(W.at(x + dx, y, z + dz)) for dx, dz in span]
            if not all(is_fence(e) or is_gate(e) or full_face(W.at(x + dx, y, z + dz))
                       for e, (dx, dz) in zip(ends, span)):
                rep.err("links", "the gate at %s (facing %s) is not across its line: its span ends in %s"
                        % ((x, y, z), f, ends))
    for w in wrong[:5]:
        rep.err("links", "%s's %s is %s, but its neighbour %s %s" % (w[0], w[1], w[2], w[4],
                                                                    "joins" if w[3] else "does not join"))
    if len(wrong) > 5:
        rep.err("links", "%d fence or pane connections wrong in all" % len(wrong))


def stand_y(W, x, z, g):
    gy = g(x, z)
    for y in range(gy + 1, gy + 8):
        if AIA._standable(W.at, x, y, z):
            return y
    return None


def check_pens(doc, W, g, rep, homes):
    """homes: {pen name: [(x, y, z)]} the record's AI-on animals' feet in that pen."""
    cx, cz = doc["site"]["centre"]
    out = {}
    for p in doc["pieces"]:
        if p["kind"] != "fence":
            continue
        x0, z0, x1, z1 = (cx + p["rect"][0], cz + p["rect"][1], cx + p["rect"][2], cz + p["rect"][3])
        starts = list(homes.get(p["name"]) or [])
        if not starts:
            mx, mz = (x0 + x1) // 2, (z0 + z1) // 2
            cand = sorted(((x, z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1)),
                          key=lambda c: (abs(c[0] - mx) + abs(c[1] - mz), c))
            for x, z in cand:
                y = stand_y(W, x, z, g)
                if y is not None:
                    starts = [(x, y, z)]
                    break
        if not starts:
            rep.err("pens", "%s: nowhere inside it to stand" % p["name"])
            continue
        inside = (lambda a, b, c, d: (lambda x, z: a < x < c and b < z < d))(x0, z0, x1, z1)
        for s in starts:
            region, esc = AIA.enclosure(W.at, s, inside)
            if not region:
                rep.err("pens", "%s: nothing to stand on at %s" % (p["name"], s))
                continue
            if esc is not None:
                rep.err("pens", "%s is open: a walker from %s gets out at %s" % (p["name"], s, esc))
                continue
            box = (x0 - 2, z0 - 2, x1 + 2, z1 + 2)
            unf = sorted(c for c, sts in AIA.walls_of(W.at, region, box).items() if not any(AIA.is_tall(t) for t in sts))
            if unf:
                rep.err("pens", "%s: %d column(s) of its outer wall are not fence or gate, e.g. %s"
                        % (p["name"], len(unf), unf[0]))
            out.setdefault(p["name"], region)
        # the gates opened: a pen nobody can enter or leave is a box
        opened = {k: v.replace("open=false", "open=true") for k, v in W.R.blocks.items() if is_gate(base(v))}
        Wo = World(W.R, W.g, W.water, opened)
        _r, esc = AIA.enclosure(Wo.at, starts[0], inside)
        if esc is None:
            rep.err("pens", "%s: with its gates open a walker from %s still cannot get out" % (p["name"], starts[0]))
    return out


def check_doors(R, rep):
    for (x, y, z), st in sorted(R.blocks.items()):
        b = base(st)
        if not b.endswith("_door"):
            continue
        pr = props(st)
        if pr.get("half") == "lower":
            up = R.blocks.get((x, y + 1, z))
            pu = props(up) if up else {}
            if not up or base(up) != b or pu.get("half") != "upper" or pu.get("facing") != pr.get("facing") \
                    or pu.get("hinge") != pr.get("hinge"):
                rep.err("doors", "the door at %s has no matching upper half (above: %s)" % ((x, y, z), up))
            for dx, dz in ((1, 0), (0, 1)):
                n = R.blocks.get((x + dx, y, z + dz))
                if n and base(n) == b and props(n).get("half") == "lower" and props(n).get("facing") == pr.get("facing") \
                        and props(n).get("hinge") == pr.get("hinge"):
                    rep.err("doors", "the double door at %s and %s hinges both %s" % ((x, y, z), (x + dx, y, z + dz),
                                                                                      pr.get("hinge")))
        elif pr.get("half") == "upper":
            lo = R.blocks.get((x, y - 1, z))
            if not lo or base(lo) != b or props(lo).get("half") != "lower":
                rep.err("doors", "the door's upper half at %s has no lower half" % ((x, y, z),))
        else:
            rep.err("doors", "the door at %s has no half" % ((x, y, z),))


def check_roofs(doc, R, floors, rep):
    cx, cz = doc["site"]["centre"]
    for p in doc["pieces"]:
        rf = p.get("roof")
        if p["kind"] != "building" or not isinstance(rf, dict) or "axis" not in rf:
            continue
        x0, z0, x1, z1 = (cx + p["footprint"][0], cz + p["footprint"][1], cx + p["footprint"][2], cz + p["footprint"][3])
        B = floors[p["name"]][0]
        top_wall = B + int(p["walls"]["height"])
        ov = int(rf.get("overhang", 1))
        stairs, ridge = base(rf["stairs"]), base(rf["ridge"])
        ax = rf["axis"]
        # along the ridge: a; across it: c (the slope runs along c)
        a_lo, a_hi, c_lo, c_hi = (x0 - ov, x1 + ov, z0 - ov, z1 + ov) if ax == "x" else (z0 - ov, z1 + ov, x0 - ov, x1 + ov)
        up_lo, up_hi = ("south", "north") if ax == "x" else ("east", "west")
        mid = (c_lo + c_hi) / 2.0
        probs = []
        for a in range(a_lo, a_hi + 1):
            row = {}
            for c in range(c_lo, c_hi + 1):
                x, z = (a, c) if ax == "x" else (c, a)
                ys = [y for y in range(top_wall + 1, top_wall + 2 + (c_hi - c_lo)) if base(R.blocks.get((x, y, z), "")) in (stairs, ridge)]
                if ys:
                    row[c] = (max(ys), R.blocks[(x, max(ys), z)])
            for c, (y, st) in row.items():
                if base(st) == stairs:
                    want = up_lo if c < mid else up_hi if c > mid else None
                    if props(st).get("facing") != want:
                        probs.append("%s at %s faces %s, not up-slope %s" % (short(st), (a, y, c), props(st).get("facing"), want))
                    k = (c - c_lo) if c < mid else (c_hi - c)
                    if y != top_wall + 1 + k:
                        probs.append("the stair row %d from the eave at %s is at y%d, not y%d" % (k, (a, c), y, top_wall + 1 + k))
            if mid == int(mid):
                m = int(mid)
                if m not in row or base(row[m][1]) != ridge:
                    probs.append("no ridge (%s) on the middle row at %s" % (short(ridge), (a, m)))
            else:
                lo_m, hi_m = int(math.floor(mid)), int(math.ceil(mid))
                if not (lo_m in row and hi_m in row and row[lo_m][0] == row[hi_m][0]):
                    probs.append("the two middle stair rows at %s do not meet" % ((a, lo_m, hi_m),))
        for pr in probs[:2]:
            rep.err("roofs", "%s: %s" % (p["name"], pr))
        if len(probs) > 2:
            rep.err("roofs", "%s: %d roof problems in all" % (p["name"], len(probs)))


def animal_spots(doc, g, floors):
    cx, cz = doc["site"]["centre"]
    out = {}
    for a in doc["animals"]:
        dx, dz, on = a["at"]
        x, z = cx + dx, cz + dz
        y = g(x, z) + 1 if on == "ground" else (floors[on][0] + 1 if on in floors else None)
        out[a["id"]] = (x, y, z)
    return out


def body_hit(W, xyz, size):
    """The first collision cell inside the body's box (centred on the block), or None."""
    x, y, z = xyz
    hw = size["width"] / 2.0
    for bx in range(math.floor(x + .5 - hw + 1e-6), math.floor(x + .5 + hw - 1e-6) + 1):
        for bz in range(math.floor(z + .5 - hw + 1e-6), math.floor(z + .5 + hw - 1e-6) + 1):
            for by in range(y, math.floor(y + size["height"] - 1e-6) + 1):
                if AIA.collides(W.at(bx, by, bz)):
                    return (bx, by, bz), short(W.at(bx, by, bz))
    return None


def pen_margin(region, home, box):
    return min(max(abs(c[0] - home[0]), abs(c[1] - home[2])) for c in AIA.walls_of(lambda *_: "minecraft:air", region, box))


def check_animal(rep, who, a, xyz, W, jar, idle_rules, behaviours, ai_on, margin):
    """One animal against the replay and the jar: body, floor, pen, behaviours. Used for the record (data) and for the
    claim (--animals), so both are judged by the same rule. `behaviours` is the extra list (beyond idle's own)."""
    sp = jar.species(a["species"]) if jar else None
    if sp is None:
        rep.err("animals", "%s: species %s is not in the jar" % (who, a["species"]))
        return
    hit = body_hit(W, xyz, sp)
    if hit:
        rep.err("animals", "%s (%s, %.2f x %.2f) at %s: its body meets %s at %s" % (
            who, a["species"], sp["width"], sp["height"], xyz, hit[1], hit[0]))
    x, y, z = xyz
    if not AIA.collides(W.at(x, y - 1, z)) or AIA.is_tall(W.at(x, y - 1, z)):
        rep.err("animals", "%s at %s has nothing to stand on (%s)" % (who, xyz, short(W.at(x, y - 1, z))))
    for b in behaviours:
        if not ai_on:
            rep.err("animals", "%s is still (NoAI) and carries the behaviour %s, which never runs" % (who, b))
        elif b not in sp["ai"]:
            rep.err("animals", "%s: %s is not one of %s's own behaviours in the jar (%s ai: %s)" % (
                who, b, a["species"], sp["file"], sorted(sp["ai"])))
    if ai_on and SHEARED in sp["features"] and EATS_GRASS not in behaviours:
        rep.err("animals", "%s: an AI-on %s (jar feature `sheared`) without %s: shorn, its fleece never grows back" % (
            who, a["species"], EATS_GRASS))
    if not ai_on:
        return
    r = float(idle_rules["follower_home_radius"])
    ok, why = AIA.penned(W.at, xyz, r)
    if not ok:
        rep.err("animals", "%s at %s walks with its AI on and is not penned: %s" % (who, xyz, why))
        return
    box = (x - AIA.PEN_REACH, z - AIA.PEN_REACH, x + AIA.PEN_REACH, z + AIA.PEN_REACH)
    region, _e = AIA.enclosure(W.at, xyz, lambda *_: True)
    m = pen_margin(region, xyz, box)
    if m < margin:
        rep.err("animals", "%s: its home %s is %d from its pen's fence, under rules.follower_pen_margin %d" % (who, xyz, m, margin))
    if EATS_GRASS in behaviours:
        ri = int(math.floor(r))
        bare = [(x + dx, z + dz) for dx in range(-ri, ri + 1) for dz in range(-ri, ri + 1)
                if dx * dx + dz * dz <= r * r and (x + dx, z + dz) in region
                and not any(base(W.at(x + dx, yy - 1, z + dz)) == "minecraft:grass_block" for yy in region[(x + dx, z + dz)])]
        if bare:
            rep.err("animals", "%s eats grass, but %d column(s) of its home disc are not grass_block, e.g. %s" % (who, len(bare), bare[0]))


def check_animals(doc, W, g, floors, jar, idle, rep):
    rules = idle["rules"]
    spots = animal_spots(doc, g, floors)
    ids = [a["id"] for a in doc["animals"]]
    for d in sorted({i for i in ids if ids.count(i) > 1}):
        rep.err("animals", "%s is in the record %d times" % (d, ids.count(d)))
    pens = {p["name"]: p for p in doc["pieces"] if p["kind"] == "fence"}
    cx, cz = doc["site"]["centre"]
    homes = {}
    for a in doc["animals"]:
        xyz = spots[a["id"]]
        if xyz[1] is None:
            rep.err("animals", "%s stands on %r, which is neither ground nor a building of the record" % (a["id"], a["at"][2]))
            continue
        sp = jar.species(a["species"]) if jar else None
        tab = (doc.get("species") or {}).get(a["species"])
        if sp and tab and (abs(tab["width"] - sp["width"]) > 0.01 or abs(tab["height"] - sp["height"]) > 0.01):
            rep.err("animals", "data species.%s says %s x %s; the jar's hitbox x baseScale is %.2f x %.2f" % (
                a["species"], tab["width"], tab["height"], sp["width"], sp["height"]))
        ai_on = a["kind"] != "loafer"
        check_animal(rep, a["id"], a, xyz, W, jar, rules, a.get("extra_behaviours") or [], ai_on,
                     int(doc["rules"]["follower_pen_margin"]))
        if ai_on and a.get("pen"):
            p = pens.get(a["pen"])
            if p is None:
                rep.err("animals", "%s: its pen %r is not a fence piece" % (a["id"], a["pen"]))
            else:
                x0, z0, x1, z1 = p["rect"]
                if not (cx + x0 < xyz[0] < cx + x1 and cz + z0 < xyz[2] < cz + z1):
                    rep.err("animals", "%s at %s is outside the pen it names, %s" % (a["id"], xyz, a["pen"]))
                homes.setdefault(a["pen"], []).append(xyz)
    n = len(doc["animals"]) + 2
    if n > rules["cap_per_town"]:
        rep.err("animals", "%d Pokemon and 2 NPCs, over data/ambient.json idle.rules.cap_per_town %d" % (n, rules["cap_per_town"]))
    return spots, homes


# ------------------------------------------------------------------ the claims (the idle pack)


RE_SPAWN = re.compile(r'spawn_at \{x:"?(-?[\d.]+)"?,y:"?(-?[\d.]+)"?,z:"?(-?[\d.]+)"?,species:"([a-z0-9_]+)",level:(\d+)\}')
RE_KEEP = re.compile(r"positioned (-?[\d.]+) (-?\d+) (-?[\d.]+) if entity @a\[distance=\.\.(\d+)\] run function [a-z_]+:ambient_idle/t/([a-z0-9_]+)/keep")


def read_idle(pack):
    base_ = Path(pack) / "data" / "cobblers" / "function" / "ambient_idle"
    if not base_.is_dir():
        return None
    return {p.relative_to(base_).with_suffix("").as_posix(): [l.strip() for l in p.read_text(encoding="utf-8").splitlines()
                                                             if l.strip() and not l.strip().startswith("#")]
            for p in base_.rglob("*.mcfunction")}


def idlers_of(fns):
    out = {}
    for name, lines in fns.items():
        m = re.fullmatch(r"t/([a-z0-9_]+)/keep", name)
        if not m:
            continue
        for l in lines:
            for iid in re.findall(r"tag=cobblers\.amb\.([a-z0-9_]+)\]", l):
                if iid in out:
                    out[iid]["groups"].add(m.group(1))
                    continue
                rec = {"id": iid, "groups": {m.group(1)}}
                sp = RE_SPAWN.search(" ".join(fns.get("i/%s/spawn" % iid, [])))
                if sp:
                    rec["at"] = (float(sp.group(1)), float(sp.group(2)), float(sp.group(3)))
                    rec["species"] = sp.group(4)
                claim = fns.get("i/%s/claim" % iid, [])
                merge = " ".join(c for c in claim if c.startswith("data merge entity @s"))
                rec["noai"] = (re.search(r"NoAI:(\d)b", merge) or [None, None])[1]
                bl = re.search(r"Behaviours:\[([^\]]*)\]", merge)
                rec["behaviours"] = [b.strip().strip('"') for b in bl.group(1).split(",") if b.strip()] if bl else []
                rec["flags"] = set(re.findall(r"([A-Za-z]+):1b", merge)) | (
                    {"DeathLootTable:empty"} if 'DeathLootTable:"minecraft:empty"' in merge else set())
                hm = re.search(r"home_x:(-?[\d.]+)d,home_y:(-?[\d.]+)d,home_z:(-?[\d.]+)d,home_radius:(-?[\d.]+)d", merge)
                rec["home"] = tuple(float(hm.group(i)) for i in (1, 2, 3)) if hm else None
                rec["home_radius"] = float(hm.group(4)) if hm else None
                rec["tp"] = [c for c in claim if c.startswith("tp @s ")]
                out[iid] = rec
    return out


def worker_flags(packs):
    flags = set()
    for p in sorted((Path(packs) / "cobblers_ambient").rglob("*.mcfunction")) if (Path(packs) / "cobblers_ambient").is_dir() else []:
        for l in p.read_text(encoding="utf-8").splitlines():
            if l.startswith("data merge entity @s {") and "Persistence" in l:
                flags |= set(re.findall(r"([A-Za-z]+):1b", l))
                if 'DeathLootTable:"minecraft:empty"' in l:
                    flags.add("DeathLootTable:empty")
    return flags


def other_spawns_in(packs, box, skip):
    out = []
    lit = re.compile(r"spawnpokemonat (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) ([a-z0-9_]+)")
    for p in sorted(Path(packs).glob("*/data/*/function/**/*.mcfunction")):
        if p.relative_to(packs).parts[0] in skip:
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        if "spawnpokemonat" not in t:
            continue
        for m in lit.finditer(t):
            x, z = float(m.group(1)), float(m.group(3))
            if box[0] <= x <= box[2] + 1 and box[1] <= z <= box[3] + 1:
                out.append((x, z, m.group(4), p.relative_to(packs).parts[0]))
    return out


def place_name(data):
    for b in jload("markets.json", data).get("places_beyond_towns") or []:
        if (b.get("source") or "").replace("\\", "/").endswith("data/" + RECORD):
            return b["town"]
    return None


def check_claims(doc, fns, spots, W, jar, idle, rep, packs, data):
    rules = idle["rules"]
    base_follow = list(rules["behaviours"]["follower"])
    every = idlers_of(fns)
    x0, z0, x1, z1 = doc["bbox"]
    mine = {k: v for k, v in every.items() if "at" in v and x0 <= v["at"][0] <= x1 + 1 and z0 <= v["at"][2] <= z1 + 1}
    used = set()
    want_group = place_name(data)
    if want_group is None:
        rep.err("claims", "no data/markets.json places_beyond_towns entry has data/%s as its source" % RECORD)
    groups = set()
    margin = int(doc["rules"]["follower_pen_margin"])
    for a in doc["animals"]:
        x, y, z = spots[a["id"]]
        hit = [v for v in mine.values() if v.get("species") == a["species"]
               and abs(v["at"][0] - (x + .5)) < 1e-6 and abs(v["at"][1] - y) < 1e-6 and abs(v["at"][2] - (z + .5)) < 1e-6]
        if len(hit) != 1:
            rep.err("claims", "%s (%s) at %s is spawned by %d idlers, not 1" % (a["id"], a["species"], (x + .5, y, z + .5), len(hit)))
            continue
        v = hit[0]
        used.add(v["id"])
        groups |= v["groups"]
        ai_on = v["noai"] == "0"
        if (a["kind"] == "loafer") == ai_on:
            rep.err("claims", "%s is a %s in the record and NoAI %sb in its claim" % (a["id"], a["kind"], v["noai"]))
        if not ai_on and not v["tp"]:
            rep.err("claims", "%s: a still animal its claim never puts on its spot" % a["id"])
        if ai_on:
            if v["home"] is None or math.dist(v["home"], v["at"]) > 1e-6:
                rep.err("claims", "%s: its home %s is not its spot %s" % (a["id"], v["home"], v["at"]))
            if HOME_WALK not in v["behaviours"]:
                rep.err("claims", "%s: AI on without %s, so nothing walks it home" % (a["id"], HOME_WALK))
            idle_r = dict(rules, follower_home_radius=v["home_radius"] or rules["follower_home_radius"])
        else:
            idle_r = rules
        extra = [b for b in v["behaviours"] if b not in base_follow] if ai_on else []
        check_animal(rep, "%s (claim %s)" % (a["id"], v["id"]), a, (x, y, z), W, jar, idle_r, extra, ai_on, margin)
        miss = sorted(WORKER_FLAGS - v["flags"])
        if miss:
            rep.err("claims", "%s lacks the workers' flags %s" % (v["id"], miss))
    for k in sorted(set(mine) - used):
        rep.err("claims", "the idler %s (%s) at %s inside the farm's bbox is none of the record's animals" % (
            k, mine[k].get("species"), mine[k]["at"]))
    if want_group and groups and groups != {want_group}:
        rep.err("claims", "the farm's animals are kept by %s, not by %s alone" % (sorted(groups), want_group))
    if "uncatchable" not in " ".join(fns.get("spawn_at", [])):
        rep.err("claims", "the idle spawn macro lacks `uncatchable`")
    wf = worker_flags(packs) - WORKER_FLAGS
    for v in (mine[k] for k in used):
        if wf - v["flags"]:
            rep.err("claims", "%s lacks cobblers_ambient's worker flags %s" % (v["id"], sorted(wf - v["flags"])))
    gate = [m for m in (RE_KEEP.search(l) for l in fns.get("keep_all", [])) if m and m.group(5) in groups]
    for v in (mine[k] for k in used):
        if not any(math.dist((float(m.group(1)), float(m.group(3))), (v["at"][0], v["at"][2])) <= int(m.group(4)) for m in gate):
            rep.err("claims", "%s at %s is outside every keep_all gate of its group: its keeper never runs near it" % (v["id"], v["at"]))
    oth = other_spawns_in(packs, doc["bbox"], {"cobblers_ambient_idle"})
    n = len(used) + len(oth) + 2
    if n > rules["cap_per_town"]:
        rep.err("claims", "%d idle + %d other Pokemon + 2 NPCs in the farm, over cap_per_town %d" % (len(used), len(oth), rules["cap_per_town"]))
    rep.note("claims: %d of the record's %d animals claimed; %d other pack spawn(s) inside the bbox" % (
        len(used), len(doc["animals"]), len(oth)))


# ------------------------------------------------------------------ seats, siting, stand, wiring


def check_seats(doc, W, g, spots, rep, data, compile_fn=None):
    rec = doc["records"]
    seats = {s["id"]: s for s in jload("npc_seats.json", data).get("seats") or []}
    stalls = {s["id"]: s for s in jload("markets.json", data).get("stalls") or []}
    who = []
    s = seats.get(rec["npc_seat"])
    if s is None:
        rep.err("seats", "data/npc_seats.json has no %s" % rec["npc_seat"])
    else:
        who.append(("the farmer", tuple(s["at"]), tuple(doc["farmer"]["feet"])))
        if s.get("conversation") != rec["conversation"]:
            rep.err("seats", "%s speaks %s, not %s" % (rec["npc_seat"], s.get("conversation"), rec["conversation"]))
    st = stalls.get(rec["stall"])
    if st is None:
        rep.err("seats", "data/markets.json has no stall %s" % rec["stall"])
    else:
        who.append(("the stand keeper", tuple(st["at"]), tuple(doc["stand_keeper"]["feet"])))
    for name, at, feet in who:
        x, y, z = (int(v) for v in at)
        if tuple(at) != feet:
            rep.err("seats", "%s stands at %s, the record's feet are %s" % (name, list(at), list(feet)))
        if y != g(x, z) + 1:
            rep.err("seats", "%s at %s is not at round(ground) + 1 = y%d" % (name, list(at), g(x, z) + 1))
        for yy in (y, y + 1):
            if AIA.collides(W.at(x, yy, z)):
                rep.err("seats", "%s at %s: the replay puts %s at y%d" % (name, list(at), short(W.at(x, yy, z)), yy))
        if not AIA.collides(W.at(x, y - 1, z)):
            rep.err("seats", "%s at %s has nothing under it" % (name, list(at)))
        for aid, (ax, ay, az) in spots.items():
            if ay is not None and max(abs(ax - x), abs(az - z)) <= 1 and abs(ay - y) <= 1:
                rep.err("seats", "%s at %s is on or beside the animal %s" % (name, list(at), aid))
    if len(who) == 2:
        d = math.dist((who[0][1][0], who[0][1][2]), (who[1][1][0], who[1][1][2]))
        if d < doc["rules"]["npc_gap"]:
            rep.err("seats", "the farmer and the stand keeper are %.1f apart, under rules.npc_gap %d" % (d, doc["rules"]["npc_gap"]))
    convs = json.dumps(jload("dialogue.json", data))
    if '"%s"' % rec["conversation"] not in convs:
        rep.err("seats", "data/dialogue.json has no conversation %s" % rec["conversation"])
    if '"%s"' % rec["quest"] not in json.dumps(jload("quests.json", data)):
        rep.err("seats", "data/quests.json has no quest %s" % rec["quest"])
    if compile_fn is not None:
        try:
            if not compile_fn(rec["conversation"], data):
                rep.err("seats", "tools/compile_dialogue.py builds nothing for %s" % rec["conversation"])
        except (Exception, SystemExit) as e:  # noqa: BLE001 - the compiler's refusal is the finding
            rep.err("seats", "tools/compile_dialogue.py refuses %s: %s" % (rec["conversation"], str(e)[:160]))


def corridor_rects(data):
    out = []

    def walk(o):
        if isinstance(o, dict):
            if all(isinstance(o.get(k), (int, float)) for k in ("min_x", "max_x", "min_z", "max_z")):
                out.append((o["min_x"], o["min_z"], o["max_x"], o["max_z"], "routes.json corridor %s" % o.get("id")))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(jload("routes.json", data).get("routes"))
    return out


def in_poly(x, z, poly):
    inside, n = False, len(poly)
    for k in range(n):
        (xa, za), (xb, zb) = poly[k][:2], poly[(k + 1) % n][:2]
        if (za > z) != (zb > z) and x < xa + (z - za) * (xb - xa) / (zb - za):
            inside = not inside
    return inside


def check_siting(doc, cols, g, water, rep, data):
    import numpy as np
    rules = doc["rules"]
    m = rules["authored_clearance"]
    cx, cz = doc["site"]["centre"]
    C = np.array(sorted(cols), float)
    mm = re.search(r"\by(\d+) at the centre", doc["site"].get("measured") or "")
    if not mm or int(mm.group(1)) != g(cx, cz):
        rep.err("siting", "site.measured says %s at the centre, the heightmap gives y%d" % (mm.group(0) if mm else "nothing", g(cx, cz)))
    if water(cx, cz) is not None:
        rep.err("siting", "the centre is wet")
    pts, rects = SA.authored({"residents": [{"records": doc["records"]}]}, data, record=RECORD)
    best = (1e18, None, None)
    if pts:
        P = np.array([(a, b) for a, b, _f in pts], float)
        for k in range(0, len(C), 128):
            blk = C[k:k + 128]
            d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
            j = np.unravel_index(np.argmin(d), d.shape)
            if d[j] < best[0]:
                best = (float(d[j]), tuple(int(v) for v in blk[j[0]]), pts[j[1]][2])
    for x0, z0, x1, z1, f in list(rects) + corridor_rects(data):
        dx = np.maximum(np.maximum(x0 - C[:, 0], C[:, 0] - x1), 0)
        dz = np.maximum(np.maximum(z0 - C[:, 1], C[:, 1] - z1), 0)
        d = np.hypot(dx, dz)
        j = int(np.argmin(d))
        if d[j] < best[0]:
            best = (float(d[j]), tuple(int(v) for v in C[j]), "%s (box %s)" % (f, [x0, z0, x1, z1]))
    if best[0] < m:
        rep.err("siting", "(%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)" % (best[1] + (best[0], best[2], m)))
    rep.note("siting: nearest authored x/z %.0f, our column %s, in data/%s" % best)
    for t in jload("towns.json", data)["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            rep.err("siting", "within %d of town %s's footprint" % (m, t["id"]))
    for k, zone in jload("rift_zones.json", data)["zones"].items():
        if any(any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for x, z in cols) for b in zone.get("boxes") or []):
            rep.err("siting", "inside Rift zone %s" % k)
    boxes = [("data/far_south.json keep_out_box", jload("far_south.json", data)["rules"]["keep_out_box"]["box"]),
             ("data/southern_residents.json keep_out_box", jload("southern_residents.json", data)["rules"]["keep_out_box"]["box"])]
    boxes += [("rules.keep_out %s" % k["box"], k["box"]) for k in rules.get("keep_out") or []]
    for name, b in boxes:
        if any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for x, z in cols):
            rep.err("siting", "writes inside %s %s" % (name, b))
    ac = jload("apricorn_farm.json", data)["site"]["centre"]
    if not any(k["box"][0] <= ac[0] <= k["box"][2] and k["box"][1] <= ac[1] <= k["box"][3] for k in rules.get("keep_out") or []):
        rep.err("siting", "rules.keep_out holds no box round the apricorn farm's site centre %s (data/apricorn_farm.json)" % ac)
    gm = jload("gulch_mine.json", data)
    for name, poly in (("the Mega field", gm["mega_field"]["polygon"]), ("the gulch", gm["zone"]["polygon"])):
        if in_poly(cx, cz, poly) or any(in_poly(x, z, poly) for x, z in cols):
            rep.err("siting", "writes inside %s (data/gulch_mine.json)" % name)
            continue
        Pp = np.array([p[:2] for p in poly], float)
        A, B = Pp, np.roll(Pp, -1, axis=0)
        best_d = np.inf
        for k in range(len(A)):
            ab = B[k] - A[k]
            L2 = max(float((ab ** 2).sum()), 1e-9)
            t = np.clip(((C - A[k]) * ab).sum(1) / L2, 0, 1)
            q = A[k] + t[:, None] * ab
            best_d = min(best_d, float(np.min(np.hypot(C[:, 0] - q[:, 0], C[:, 1] - q[:, 1]))))
        if best_d < m:
            rep.err("siting", "%.0f blocks from %s (needs %d)" % (best_d, name, m))
        rep.note("siting: %s %.0f blocks away" % (name, best_d))
    hb = jload("habitat_blocks.json", data)
    hpts = []
    for b in hb.get("blocks") or []:
        r = b.get("range_of_influence") or ((b.get("activated") or {}).get("spawn_range")) or 0
        p = b.get("position") or {}
        if "x" in p:
            hpts.append((p["x"], p["z"], float(r), b["id"]))
    if hpts:
        H = np.array([h[:3] for h in hpts], float)
        d = np.hypot(C[:, None, 0] - H[None, :, 0], C[:, None, 1] - H[None, :, 1]) - H[None, :, 2]
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] <= 0:
            rep.err("siting", "column %s is inside Habitat Block %s's range" % (tuple(int(v) for v in C[j[0]]), hpts[j[1]][3]))
        rep.note("siting: nearest Habitat Block range edge %.0f (%s)" % (float(d[j]), hpts[j[1]][3]))
    clear = jload("encounter_design.json", data)["rules"]["hearts"]["clear_of_path_blocks"]
    if rules.get("path_clearance") != clear:
        rep.err("siting", "rules.path_clearance %s is not encounter_design rules.hearts.clear_of_path_blocks %s" % (rules.get("path_clearance"), clear))
    paths = np.array([p[:2] for pl in jload("route_paths.json", data)["paths"].values() for p in pl], float)
    for name, (x, z) in (("the centre", (cx, cz)), ("the farmer", tuple(doc["farmer"]["feet"][::2])),
                         ("the stand keeper", tuple(doc["stand_keeper"]["feet"][::2]))):
        d = float(np.min(np.hypot(paths[:, 0] - x, paths[:, 1] - z)))
        if d < clear:
            rep.err("siting", "%s (%d, %d) is %.0f from a route path (needs %d)" % (name, x, z, d, clear))
    import northern_residents_audit as NA
    if NA._cell(cx, cz, data) != doc.get("cell"):
        rep.err("siting", "the centre is in cell %s, the record says %s" % (NA._cell(cx, cz, data), doc.get("cell")))
    sub = SA._subregion(cx, cz, data)[0]
    if sub != doc.get("subregion"):
        rep.err("siting", "the centre is in sub-region %s, the record says %s" % (sub, doc.get("subregion")))


def bank_prices():
    out = {}
    for p in (ROOT / "base-pack/cobbleverse/config/cobbledollars/bank.json", ROOT / "modpack/config/cobbledollars/bank.json"):
        if p.is_file():
            for e in json.loads(p.read_text(encoding="utf-8")).get("bank") or []:
                out[e["item"]] = int(e["price"])
    return out


def check_stand(doc, rep, data, spawn):
    import markets as M
    mk = jload("markets.json", data)
    sid = doc["records"]["stall"]
    st = next((s for s in mk.get("stalls") or [] if s.get("id") == sid), None)
    if st is None:
        rep.err("stand", "data/markets.json has no stall %s" % sid)
        return
    place = place_name(data)
    if st.get("town") != place:
        rep.err("stand", "%s's town is %r; the place whose source is data/%s is %r" % (sid, st.get("town"), RECORD, place))
    if place not in {n.get("town") for n in mk.get("no_counter") or []}:
        rep.err("stand", "%s is not in no_counter: the coverage rule asks it for a counter" % place)
    towns = jload("towns.json", data)["towns"]
    for p in M.stall_problems(mk, towns, {}):
        if ("stall %s" % sid) in p:
            rep.err("stand", "tools/markets.py: %s" % p)
    bank = bank_prices()
    for it in st.get("stock") or []:
        w = "%s line %s" % (sid, it.get("id"))
        item, cnt, price = it.get("item") or "", it.get("count"), it.get("price")
        if it.get("gate") is not None:
            rep.err("stand", "%s is gated (%s): a stall shows every line to every player" % (w, it.get("gate")))
        if not item.startswith("minecraft:"):
            rep.err("stand", "%s: %s is not vanilla" % (w, item))
        if item in spawn:
            rep.err("stand", "%s: %s is a spawn-condition block" % (w, item))
        if not (isinstance(cnt, int) and isinstance(price, int) and cnt > 0 and price > 0):
            rep.err("stand", "%s: count %r, price %r" % (w, cnt, price))
            continue
        if price % cnt:
            rep.err("stand", "%s: $%d for %d does not divide" % (w, price, cnt))
        if item in bank and price / cnt <= bank[item]:
            rep.err("stand", "%s: $%s each is not above the bank's sell-back $%d" % (w, price / cnt, bank[item]))
    without = dict(mk, stalls=[s for s in mk.get("stalls") or [] if s.get("id") != sid])
    if M.curve(mk) != M.curve(without):
        rep.err("stand", "the critical-path curve moves with %s in it" % sid)


def check_wiring(doc, rep, text=None, pack=None):
    text = text if text is not None else (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    jobs = [m.group(1) for m in re.finditer(r'add\("([^"]+)",\s*"[^"]+\.py"', text)]
    me = Path(__file__).name
    for j in (GENERATOR, GENERATOR + "_audit", IDLE_JOB, ANIMALS_JOB):
        if jobs.count(j) != 1:
            rep.err("wiring", "tools/reapply.py has %d prepare job(s) %s, not 1" % (jobs.count(j), j))
    order = [(GENERATOR, GENERATOR + "_audit"), (GENERATOR, IDLE_JOB), (IDLE_JOB, ANIMALS_JOB)]
    for a, b in order:
        if a in jobs and b in jobs and jobs.index(a) > jobs.index(b):
            rep.err("wiring", "the prepare job %s runs before %s" % (b, a))
    for j, need in ((GENERATOR + "_audit", None), (ANIMALS_JOB, "--animals")):
        mm = re.search(r'add\("%s",\s*"([^"]+)"([^\n]*)\)' % re.escape(j), text)
        if mm and mm.group(1) != me:
            rep.err("wiring", "the prepare job %s runs %s, not %s" % (j, mm.group(1), me))
        if mm and need and need not in mm.group(2):
            rep.err("wiring", "the prepare job %s does not pass %s" % (j, need))
    step = doc["build"]["step"]
    steps = [m.group(1) for m in re.finditer(r'out\.append\(\("(R[0-9A-Z]+)"', text)]
    calls = {m.group(1): m.group(2) for m in re.finditer(
        r'out\.append\(\("(R[0-9A-Z]+)",\s*"[^"]*",\s*\n?\s*([A-Za-z_]+\.[A-Za-z_]+)\(\)\)\)', text)}
    if steps.count(step) != 1:
        rep.err("wiring", "tools/reapply.py appends step %s %d times" % (step, steps.count(step)))
    else:
        k = steps.index(step)
        if calls.get(step) != "%s.placement_steps" % GENERATOR:
            rep.err("wiring", "step %s is %s, not %s.placement_steps()" % (step, calls.get(step), GENERATOR))
        if STEP_AFTER not in steps or steps.index(STEP_AFTER) > k:
            rep.err("wiring", "step %s runs before %s" % (step, STEP_AFTER))
        if STEP_BEFORE not in steps or steps.index(STEP_BEFORE) < k:
            rep.err("wiring", "step %s runs after %s" % (step, STEP_BEFORE))
    tree = ast.parse(text)
    vals = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if getattr(t, "id", None) in ("SERVER_PACKS", "WORLD_LOCAL"):
                    try:
                        vals[t.id] = ast.literal_eval(node.value)
                    except ValueError:
                        pass
    pk = doc["build"]["pack"]
    if pk not in (vals.get("SERVER_PACKS") or ()):
        rep.err("wiring", "%s is not in tools/reapply.py SERVER_PACKS" % pk)
    if pk in (vals.get("WORLD_LOCAL") or ()):
        rep.err("wiring", "%s is WORLD_LOCAL, but it has no tick or load" % pk)
    if pack is not None:
        for tag in ("tick", "load"):
            if (Path(pack) / "data" / "minecraft" / "tags" / "function" / ("%s.json" % tag)).is_file():
                rep.err("wiring", "the pack carries a %s tag: it would run on the live server every %s" % (tag, tag))


# ------------------------------------------------------------------ the whole audit


def policy_white(data, doc):
    pol = jload("spawn_block_policy.json", data)
    names = (GENERATOR, doc["id"], doc["build"]["pack"])
    return {b for w in pol.get("whitelist") or [] if any(n in (w.get("scope") or "") for n in names) for b in w.get("blocks") or []}


def audit(doc, g, water, pack, data=DATA, jar=None, vanilla=None, reapply_text=None, idle_pack=None, packs=None,
          compile_fn=None):
    """`water(x, z)` -> the surface y or None. `idle_pack`: also judge the idle pack's claims (--animals)."""
    rep = Report()
    if doc.get("schema") != SCHEMA:
        rep.err("spec", "schema %s, expected %s" % (doc.get("schema"), SCHEMA))
    R = Replay(read_build(pack, doc))
    W = World(R, g, water)
    spawn = set(jload("spawn_blocks.json", data)["blocks"])
    white = policy_white(data, doc)
    if vanilla is None:
        rep.note("writes: NOT CHECKED that every id is a vanilla 1.21.1 block (no client jar here)")
    check_writes(doc, R, g, water, rep, spawn, white, vanilla)
    floors = check_floors(doc, R, W, g, rep)
    check_links(R, W, rep)
    check_doors(R, rep)
    check_roofs(doc, R, floors, rep)
    idle = jload("ambient.json", data)["idle"]
    if jar is None:
        rep.err("animals", "no Cobblemon jar: the bodies and the behaviour rule cannot be judged")
    spots, homes = check_animals(doc, W, g, floors, jar, idle, rep)
    check_pens(doc, W, g, rep, homes)
    check_seats(doc, W, g, spots, rep, data, compile_fn)
    cols = R.columns()
    check_siting(doc, cols, g, water, rep, data)
    check_stand(doc, rep, data, spawn)
    check_wiring(doc, rep, reapply_text, pack)
    if idle_pack is not None:
        fns = read_idle(idle_pack)
        if not fns:
            rep.err("claims", "no idle pack at %s (python tools/ambient_idle.py build)" % idle_pack)
        else:
            check_claims(doc, fns, spots, W, jar, idle, rep, packs or Path(idle_pack).parent, data)
    return rep


def main(argv=None):
    from terrain import env_source_root
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root", default=env_source_root())
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--pack", default=str(PACKS / "cobblers_pokemon_farm"))
    ap.add_argument("--animals", action="store_true", help="also judge the idle pack's claims (after ambient_idle:build)")
    ap.add_argument("--idle-pack", default=str(PACKS / "cobblers_ambient_idle"))
    ap.add_argument("--jar")
    a = ap.parse_args(argv)
    import ground as G
    doc = jload(RECORD, a.data)
    g = G.load(a.source_root)
    water = SA.Water(g, [tuple(doc["site"]["centre"])], a.data)
    jp = a.jar or find_jar()
    jar = Jar(jp) if jp and Path(jp).is_file() else None
    rep = audit(doc, g, water, Path(a.pack), Path(a.data), jar, vanilla_blocks(),
                idle_pack=Path(a.idle_pack) if a.animals else None, compile_fn=SA._compile)
    real, hits, stale = classify(rep.errors)
    for n in rep.notes:
        print("  " + n)
    for e in hits:
        print("KNOWN   " + e)
    for k in stale:
        print("STALE   a KNOWN entry no longer fires (remove it): %s: %s" % (k[0], k[1]))
    for e in real:
        print("PROBLEM " + e)
    print("pokemon_farm_audit%s: %d problem(s), %d known, %d stale (jar %s)" % (
        " --animals" if a.animals else "", len(real), len(hits), len(stale), jar.path if jar else "NONE"))
    return 1 if real or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
