#!/usr/bin/env python
"""Independent audit of Hollin's Apricorn Farm: the BUILT pack replayed over the heightmap, checked against the data.

Written by an agent that built none of the farm (data/apricorn_farm.json audit_checklist). It never imports
tools/apricorn_farm.py to derive anything: it reads data/apricorn_farm.json, tools/ground.py's heightmap, tools/water_mask.py,
data/rivers.json, the other data files, the Cobblemon 1.8.0 jar, and the emitted pack
(build/datapacks/cobblers_apricorn_farm). The re-application steps are the generator's OUTPUT and are checked here
(placement_steps / entity_steps are called only in main(), never to compute an expectation), and tools/reapply.py is
read as text for the step order, the pack list and the prepare job.

THE REPLAY. build.mcfunction is run in order, following its `function` calls, cell by cell, over a world that is the
natural ground (round(ground(x, z)) and below solid, air above) wherever the pack has not written. `fill ... replace
<tag>` touches only cells holding a member of the tag (the tags are read from the jar; the vanilla members this pack can
write are listed in VANILLA_TAGS). Every write is applied in order, so "the final world" includes later writes.

THE FRUIT RULE, read from Cobblemon-fabric-1.8.0+1.21.1.jar, com/cobblemon/mod/common/block/ApricornBlock.class
(javap -c -p, 2026-10-04):
  canSurvive (method_9558): world.getBlockState(pos.relative(state.getValue(FACING)))           [offsets 21-46]
                            .is(CobblemonBlockTags.APRICORN_LEAVES)                               [offsets 51-61]
  updateShape (method_9559): if direction == state.FACING and !state.canSurvive(world, pos) -> minecraft:air
                            (Blocks.AIR.defaultBlockState(), offsets 45-86); otherwise the parent's.
  randomTick (method_9514): world.random.nextInt(5) (iconst_5, method_43048), then age + 1 while age < 3.
  data/cobblemon/tags/block/apricorn_leaves.json: ["cobblemon:apricorn_leaves"].
So a fruit lives while the block its `facing` names is apricorn leaves, and is destroyed (with its drop, at age 3) by
the first shape update from that side that leaves something else there. The replay therefore fails a fruit both when
its support is not leaves in the final world AND when any write after the fruit's own replaces its support with
anything but leaves (the fruit would have broken at that moment and stays broken). jar_rule() re-reads the tag file,
the blockstate's facing values, the loot table and the class's constant pool on every run where the jar is present.

LIGHT. A block-light model of this audit's own: lanterns and lit campfires emit 15; light drops 1 a step through air
and non-occluding blocks, 2 through leaves (LeavesBlock light block 1); every full block, slab, stair, composter and
the natural ground stop it (slabs and stairs are taken as full occluders, which can only make a cell darker than the
game would). Sky light is ignored. A walkable cell (on a path, a grove floor or a building floor) at block light 0
is where hostiles may spawn: a problem. Cells under 8 are counted in a note.

WALKING. A cell is standable when its feet and head are passable (air, an openable gate or door, a sign, a plate) and
the block under it is a floor (not a fence, gate, wall, leaf, fruit or lantern). Steps are 4-way, up or down one
block, so every reached cell can also be walked back from. The flood starts at the entry track's end.

WHAT THIS DOES NOT COVER. Runtime: the farm has never been applied to a world or seen in game. Natural trees and
plants outside the generator's clear boxes are not modelled (unknown from the heightmap). Light ignores sky light
and treats slabs/stairs as opaque. Picking reach ignores line of sight. The merchant's purchase screen and the
farmer's conversation are checked as data and compiled output, not as behaviour in game. Whether an inherited
Electrode spawns above the tier-1 level cap here is the spawn suppression's question (data/apricorn_farm.json
blocks.spawn_conditions_why), not this audit's.

  python tools/apricorn_farm_audit.py [--pack DIR] [--source-root R] [--jar JAR] [-v]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import statistics
import sys
import zipfile
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
DOC = DATA / "apricorn_farm.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_apricorn_farm"
NS = "cobblers"
FOLDER = "apricorn_farm"

SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S.*)$")
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+?)"
                  r"(?: (replace|keep|destroy|hollow|outline)(?: (\S+))?)?$")
FORCELOAD = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+))?$")
FUNCTION = re.compile(r"^function ([a-z0-9_]+):([a-z0-9_/]+)$")
OTHER_OK = ("summon ", "schedule ", "execute ", "tag ", "kill ")

AIR = "minecraft:air"
NAT_GROUND = "natural:ground"
NAT_AIR = "natural:air"
LEAVES = "cobblemon:apricorn_leaves"
FRUIT = re.compile(r"^cobblemon:([a-z]+)_apricorn$")
DIRS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
# The vanilla members of the tags the clear function names that this pack (or the natural model) can hold. The
# cobblemon members are read from the jar when it is present (JAR_TAG_FALLBACK otherwise, the 1.8.0 files' contents).
VANILLA_TAGS = {
    "#minecraft:logs": {"minecraft:spruce_log", "minecraft:stripped_spruce_log", "minecraft:spruce_wood",
                        "minecraft:stripped_spruce_wood", "minecraft:dark_oak_log", "minecraft:oak_log"},
    "#minecraft:leaves": {"minecraft:spruce_leaves", "minecraft:oak_leaves", "minecraft:dark_oak_leaves"},
    "#minecraft:replaceable": {AIR, NAT_AIR, "minecraft:water", "minecraft:short_grass", "minecraft:tall_grass"},
}
JAR_TAG_FALLBACK = {
    "#cobblemon:apricorns": {"cobblemon:%s_apricorn" % c for c in ("red", "blue", "yellow", "green", "pink", "white",
                                                                    "black")},
    "#minecraft:logs": {"cobblemon:apricorn_log", "cobblemon:apricorn_wood", "cobblemon:stripped_apricorn_log",
                        "cobblemon:stripped_apricorn_wood"},
    "#minecraft:leaves": {LEAVES},
}

PASSABLE_EXACT = {AIR, NAT_AIR, "minecraft:spruce_pressure_plate"}
PASSABLE_SUFFIX = ("_fence_gate", "_door", "_sign", "_wall_sign", "_pressure_plate")
NOT_A_FLOOR_SUFFIX = ("_fence", "_fence_gate", "_wall", "_sign", "_wall_sign", "_pressure_plate", "_door")
NOT_A_FLOOR = {LEAVES, "minecraft:lantern", "minecraft:campfire"}
# light: what lets light through (the rest stops it); leaves cost one extra
LIGHT_THROUGH_EXACT = {AIR, NAT_AIR, "minecraft:lantern", "minecraft:glass_pane", "minecraft:campfire",
                       "minecraft:cauldron", "minecraft:water_cauldron", "minecraft:grindstone", "minecraft:spruce_trapdoor",
                       LEAVES}
LIGHT_THROUGH_SUFFIX = ("_fence", "_fence_gate", "_door", "_sign", "_wall_sign", "_pressure_plate", "_sapling")
REACH = 4.5          # block_interaction_range, vanilla 1.21 default
EYE = 1.62

# Defects this audit found in the committed build, reported to the builder and NOT fixed here (the data and the
# generator are not this audit's). Each prints as KNOWN and does not fail the run; a KNOWN that no longer fires is
# STALE and does fail, so the list cannot outlive its defect (tools/far_south_audit.py's convention). (check, text, ruling)
KNOWN = [
    ("walk", "barn's interior cannot be walked into from the track",
     "2026-10-04: the barn's only door (west wall x2073, z5528-5530) has its step, cobblestone stairs, at y135 on a "
     "cobblestone block at y134, while the ground outside is y133 (barn floor y135 = max ground 134 + 1). Standing on "
     "the ground (feet y134) the stair's low half is at 135.5, a 1.5 rise; a player jumps 1.25. The step is one block "
     "too high (a stair at y134 on the ground would do). Builder: the step under a door two above its outside ground"),
    ("attached", "a standing lantern on cobblemon:apricorn_leaves (no centre support) at (2061, 138, 5558)",
     "2026-10-04: the stall's display-branch lantern stands on a leaf. LeavesBlock gives no support shape (no torch "
     "or lantern stands on leaves), so LanternBlock.canSurvive is false; setblock puts it there and it stays only "
     "until a shape update from the leaf below (the leaf broken or changing state) drops it. Builder: hang it from "
     "the awning (hanging=true under the slab) or stand it on the log"),
    ("light", "282 walkable cell(s) at block light 0",
     "2026-10-04: the entry track (166 cells, no lantern along it), the north lane's two middles (49, local x -18..-9 "
     "and 9..18 at z -55..-53) and 67 grove floor cells at the far edges (e.g. red (2003, 131, 5534), local (-19, 0) "
     "of its grove). data/apricorn_farm.json lantern_posts.why says no grove floor cell is over 14 from a lantern "
     "and none reads 0: that count is horizontal only, and each lantern stands on a 2-high post, 2 above the feet "
     "cell, so 13 across is 15 by light. Builder: lanterns along the track and the north lane, and the grove posts "
     "nearer the outer edges (or 1-high posts)"),
]


# --------------------------------------------------------------------------------------------- small helpers
def base(state):
    return state.split("[")[0].split("{")[0]


def props(state):
    m = re.match(r"^[^\[{]+\[([^\]]*)\]", state)
    if not m or not m.group(1):
        return {}
    return dict(kv.split("=", 1) for kv in m.group(1).split(","))


def jload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def is_fruit(b):
    return bool(FRUIT.match(b))


def passable(b):
    return b in PASSABLE_EXACT or b.endswith(PASSABLE_SUFFIX)


def floor_ok(b):
    return not passable(b) and b not in NOT_A_FLOOR and not b.endswith(NOT_A_FLOOR_SUFFIX) and not is_fruit(b) \
        and not b.startswith("cobblemon:potted_")


def light_through(b):
    return b in LIGHT_THROUGH_EXACT or b.endswith(LIGHT_THROUGH_SUFFIX) or is_fruit(b) or "potted" in b


class Report:
    def __init__(self):
        self.errors, self.notes, self.economy = [], [], []

    def err(self, check, msg):
        self.errors.append("%s: %s" % (check, msg))

    def note(self, msg):
        self.notes.append(msg)


def classify(errors, known=None):
    """(real, known_hits, stale)."""
    known = KNOWN if known is None else known
    real, hits = [], []
    for e in errors:
        (hits if any(e.startswith(c + ":") and t in e for c, t, _w in known) else real).append(e)
    stale = [k for k in known if not any(e.startswith(k[0] + ":") and k[1] in e for e in errors)]
    return real, hits, stale


# --------------------------------------------------------------------------------------------- the replay
class Replay:
    """build.mcfunction run in order: the final states, plus every fruit a later write broke."""

    def __init__(self, pack, entry="build", tags=None, ground=None):
        self.pack = Path(pack)
        self.state, self.loads, self.removes, self.bad, self.calls = {}, [], [], [], []
        self.breaks = []          # (fruit cell, support cell, the state written over the support, function)
        self.support = {}         # support cell -> fruit cell, for live fruit
        self.tags = tags or {}
        self.ground = ground
        self.lines = {}
        self.run(entry)

    def fn_path(self, name):
        return self.pack / "data" / NS / "function" / (name + ".mcfunction")

    def run(self, name, depth=0):
        f = self.fn_path(name)
        if not f.exists() or depth > 8:
            self.bad.append("function %s:%s is missing" % (NS, name))
            return
        self.calls.append(name)
        lines = f.read_text(encoding="utf-8").splitlines()
        self.lines[name] = lines
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = FUNCTION.match(line)
            if m:
                if m.group(1) != NS:
                    self.bad.append(line)
                else:
                    self.run(m.group(2), depth + 1)
                continue
            m = FORCELOAD.match(line)
            if m:
                box = tuple(int(v) for v in m.groups()[1:] if v is not None)
                (self.loads if m.group(1) == "add" else self.removes).append(box)
                continue
            m = FILL.match(line)
            if m:
                x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
                st, mode, filt = m.group(7), m.group(8), m.group(9)
                if mode not in (None, "replace") or (mode == "replace" and not filt):
                    self.bad.append(line)
                    continue
                self.fill(min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1), st, filt,
                          name)
                continue
            m = SETBLOCK.match(line)
            if m:
                self.set((int(m.group(1)), int(m.group(2)), int(m.group(3))), m.group(4), name)
                continue
            if line.startswith(OTHER_OK):
                continue
            self.bad.append(line)

    def current(self, k):
        s = self.state.get(k)
        if s is not None:
            return base(s)
        if self.ground is None:
            return NAT_AIR
        return NAT_GROUND if k[1] <= self.ground(k[0], k[2]) else NAT_AIR

    def member(self, b, filt):
        if filt.startswith("#"):
            return b in VANILLA_TAGS.get(filt, set()) | self.tags.get(filt, set())
        return b == base(filt)

    def fill(self, x0, y0, z0, x1, y1, z1, st, filt, fn):
        if filt:
            vol = (x1 - x0 + 1) * (y1 - y0 + 1) * (z1 - z0 + 1)
            if vol <= len(self.state):
                cells = [(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)
                         if (x, y, z) in self.state]
            else:
                cells = [k for k in self.state if x0 <= k[0] <= x1 and y0 <= k[1] <= y1 and z0 <= k[2] <= z1]
            for k in cells:
                if self.member(base(self.state[k]), filt):
                    self.set(k, st, fn)
            return
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    self.set((x, y, z), st, fn)

    def set(self, k, st, fn):
        old = self.state.get(k)
        if old is not None and old == st:
            return                                   # no change: no update
        b = base(st)
        # the old occupant: a fruit replaced is simply gone (no drop: the fill replaced it)
        if old is not None and is_fruit(base(old)):
            d = DIRS.get(props(old).get("facing"))
            if d:
                sup = (k[0] + d[0], k[1], k[2] + d[1])
                if self.support.get(sup) == k:
                    del self.support[sup]
        self.state[k] = st
        # a live fruit hanging on this cell: a shape update from its facing side, survive only on leaves
        hung = self.support.get(k)
        if hung is not None and b != LEAVES:
            self.breaks.append((hung, k, st, fn))
            del self.support[k]
            self.state[hung] = AIR
        if is_fruit(b):
            d = DIRS.get(props(st).get("facing"))
            if d:
                self.support[(k[0] + d[0], k[1], k[2] + d[1])] = k


class World:
    def __init__(self, rep, g):
        self.rep, self.g = rep, g
        self._gc = {}

    def ground(self, x, z):
        k = (x, z)
        if k not in self._gc:
            self._gc[k] = int(self.g(x, z))
        return self._gc[k]

    def full(self, k):
        s = self.rep.state.get(k)
        if s is not None:
            return s
        return NAT_GROUND if k[1] <= self.ground(k[0], k[2]) else NAT_AIR

    def at(self, k):
        return base(self.full(k))

    def standable(self, k):
        x, y, z = k
        return passable(self.at(k)) and passable(self.at((x, y + 1, z))) and floor_ok(self.at((x, y - 1, z)))


# --------------------------------------------------------------------------------------------- the design
class Design:
    """Everything this audit expects, from data/apricorn_farm.json alone."""

    def __init__(self, doc):
        self.doc = doc
        self.cx, self.cz = doc["site"]["centre"]
        self.colours = [c for c in doc["tree_designs"] if c != "about" and not c.endswith("_why")]
        L = doc["grove_layout"]
        self.L = L
        self.groves = []
        for gr in doc["groves"]:
            gx, gz = self.W(*gr["centre"])
            self.groves.append(dict(gr, box=(gx - L["half_x"], gz - L["half_z"], gx + L["half_x"], gz + L["half_z"]),
                                    wc=(gx, gz)))

    def W(self, lx, lz):
        return self.cx + lx, self.cz + lz

    def fp(self, f):
        x0, z0 = self.W(f[0], f[1])
        x1, z1 = self.W(f[2], f[3])
        return min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)

    def fruit_per_tree(self, colour):
        return sum(row.count("A") for layer in self.doc["tree_designs"][colour] for row in layer)

    def allowed_blocks(self):
        """{block id: why}: every id the design names, plus the pieces its prose describes without naming an id."""
        d = self.doc
        out = {}
        skip = {"blocks", "merchant", "apricorn_facts", "decisions_pending", "audit_checklist", "status", "built_by",
                "working_pokemon"}
        idre = re.compile(r"^((?:minecraft|cobblemon):[a-z0-9_]+)(\[[^\]]*\])?$")

        def walk(o, where):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, where + "." + k)
            elif isinstance(o, list):
                for v in o:
                    walk(v, where)
            elif isinstance(o, str):
                m = idre.match(o)
                if m:
                    out.setdefault(m.group(1), "named at " + where.lstrip("."))
        for k, v in d.items():
            if k not in skip:
                walk(v, k)
        woods = {"spruce"}
        for b in d["buildings"]:
            r = b.get("roof", "")
            if r.count(":") == 1:                    # a roof names a wood: its stairs and slabs
                ns, w = r.split(":")
                woods.add(w)
                out.pop(r, None)                     # the wood itself is not a block
                out.setdefault("%s:%s_stairs" % (ns, w), "buildings.%s.roof %s" % (b["id"], r))
                out.setdefault("%s:%s_slab" % (ns, w), "buildings.%s.roof %s" % (b["id"], r))
        implied = {
            AIR: "the cut above each terrace and the clears (ground_rule)",
            "cobblemon:apricorn_log": "tree_designs.about: L/X apricorn log",
            LEAVES: "tree_designs.about: # leaves (persistent)",
            "minecraft:glass_pane": "buildings[].windows (the design names windows but no block)",
            "minecraft:cobblestone": "farmhouse.why 'a cobblestone chimney'",
            "minecraft:campfire": "farmhouse.why 'a campfire's smoke'",
            "minecraft:spruce_log": "water_tower.why 'four spruce-log legs'",
            "minecraft:spruce_planks": "water_tower.why 'a plank deck, and a plank tank'; arch.why 'a spruce beam'",
            "minecraft:water_cauldron": "water_tower.why 'water cauldrons'; grove_layout troughs",
            "minecraft:stripped_spruce_log": "arch.why 'two stripped spruce posts'",
            "minecraft:lantern": "arch.why 'a lantern hung under each end'; lantern_posts.why",
            "minecraft:spruce_fence": "lantern_posts.block; stall.why 'corner posts'; sheds_why 'spruce posts'",
            "minecraft:spruce_slab": "sheds_why 'a slab roof'",
            "cobblemon:apricorn_slab": "stall.why 'an apricorn-slab awning'",
            "minecraft:barrel": "stall.why 'a counter of barrels'; sheds_why 'Barrels along the back wall'",
            "cobblemon:apricorn_planks": "stall.why 'apricorn planks'",
            # ground_rule puts a building's floor at max(ground) + 1 on a cobblestone foundation, so a door stands
            # above the ground outside it and needs a step of the foundation's stone
            "minecraft:cobblestone_stairs": "the door step a floor of max(ground) + 1 needs (ground_rule, buildings[].foundation)",
        }
        for c in self.colours:
            implied["cobblemon:%s_apricorn" % c] = "tree_designs.about: A fruit of its colour"
        for w in sorted(woods):
            implied["minecraft:%s_sign" % w] = "the signs (groves[].sign, arch.sign, track_sign, harvest_sign) in a wood the design builds with"
            implied["minecraft:%s_wall_sign" % w] = "buildings[].wall_signs in a wood the design builds with"
        for k, v in implied.items():
            out.setdefault(k, v)
        return out


# --------------------------------------------------------------------------------------------- the jar
def find_jar(given=None):
    if given:
        return Path(given) if Path(given).is_file() else None
    dirs = [ROOT / "experiments" / "EXP-000-cobblemon-1.8-compat" / "runtime" / "server" / "mods"]
    if ROOT.parent.name == "worktrees":
        dirs.append(ROOT.parent.parent.parent / "experiments" / "EXP-000-cobblemon-1.8-compat" / "runtime" / "server" / "mods")
        dirs += [Path(p) for p in sorted(glob.glob(str(ROOT.parent / "*" / "experiments" / "EXP-000-cobblemon-1.8-compat"
                                                       / "runtime" / "server" / "mods")))]
    for d in dirs:
        hits = sorted(d.glob("Cobblemon-fabric-1.8*.jar")) if d.is_dir() else []
        if hits:
            return hits[0]
    return None


class Jar:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.path = Path(path)
        self.names = set(self.z.namelist())

    def json(self, name):
        return json.loads(self.z.read(name))

    def has_block(self, bid):
        ns, n = bid.split(":")
        return "assets/%s/blockstates/%s.json" % (ns, n) in self.names

    def has_item(self, iid):
        ns, n = iid.split(":")
        return "assets/%s/models/item/%s.json" % (ns, n) in self.names

    def tag(self, ns, name, seen=None):
        seen = seen or set()
        f = "data/%s/tags/block/%s.json" % (ns, name)
        if f not in self.names or f in seen:
            return set()
        seen.add(f)
        out = set()
        for v in self.json(f).get("values", []):
            v = v if isinstance(v, str) else v.get("id", "")
            if v.startswith("#"):
                tns, tn = v[1:].split(":")
                out |= self.tag(tns, tn, seen)
            else:
                out.add(v)
        return out

    def tags(self):
        return {"#cobblemon:apricorns": self.tag("cobblemon", "apricorns"),
                "#minecraft:logs": self.tag("minecraft", "logs"),
                "#minecraft:leaves": self.tag("minecraft", "leaves")}


def jar_rule(R, jar, colours):
    """The attachment and harvest facts the farm rests on, re-read from the jar."""
    if "cobblemon:apricorn_leaves" not in jar.tag("cobblemon", "apricorn_leaves"):
        R.err("jar", "data/cobblemon/tags/block/apricorn_leaves.json does not hold cobblemon:apricorn_leaves")
    cls = "com/cobblemon/mod/common/block/ApricornBlock.class"
    if cls not in jar.names:
        R.err("jar", "no %s in %s" % (cls, jar.path.name))
    else:
        raw = jar.z.read(cls)
        for s in (b"method_9558", b"method_9559", b"method_10093", b"APRICORN_LEAVES", b"method_9514"):
            if s not in raw:
                R.err("jar", "%s no longer references %s: re-read canSurvive before trusting the facing rule"
                      % (cls, s.decode()))
    for c in colours:
        f = "assets/cobblemon/blockstates/%s_apricorn.json" % c
        if f not in jar.names:
            R.err("jar", "no blockstate %s" % f)
            continue
        keys = jar.json(f).get("variants", {}).keys()
        faces = {kv.split("=")[1] for k in keys for kv in k.split(",") if kv.startswith("facing=")}
        ages = {kv.split("=")[1] for k in keys for kv in k.split(",") if kv.startswith("age=")}
        if faces != set(DIRS) or ages != {"0", "1", "2", "3"}:
            R.err("jar", "%s: facing %s, age %s (expected the four sides and 0-3)" % (f, sorted(faces), sorted(ages)))
        lt = "data/cobblemon/loot_table/blocks/%s_apricorn.json" % c
        if lt in jar.names:
            first = jar.json(lt)["pools"][0]["entries"][0]
            cond = (first.get("conditions") or [{}])[0].get("properties", {})
            if first.get("name") != "cobblemon:%s_apricorn" % c or cond.get("age") != "3":
                R.err("jar", "%s no longer drops one %s apricorn at age 3" % (lt, c))


def recipes(jar):
    """{ball: ({apricorn: count}, tier tag, result count)} from the jar's shaped recipes."""
    out = {}
    for ball in ("poke_ball", "great_ball", "ultra_ball"):
        r = jar.json("data/cobblemon/recipe/%s.json" % ball)
        cnt, tier = Counter(), None
        for row in r["pattern"]:
            for ch in row:
                if ch == " ":
                    continue
                k = r["key"][ch]
                if "item" in k:
                    cnt[k["item"]] += 1
                else:
                    tier = k.get("tag")
        out[ball] = (dict(cnt), tier, r["result"]["count"])
    return out


# --------------------------------------------------------------------------------------------- the checks
def check_pack(R, rep, steps):
    if rep.bad:
        R.err("steps", "%d line(s) this audit cannot read: %s" % (len(rep.bad), rep.bad[:2]))
    if not rep.state:
        R.err("steps", "the build writes nothing")
        return
    holds = list(rep.loads)
    step_holds = []
    if steps is not None:
        st = [tuple(s) for s in steps]
        if ("fn", "%s:%s/build" % (NS, FOLDER)) not in st:
            R.err("steps", "R9AF does not run %s:%s/build" % (NS, FOLDER))
        step_holds = [tuple(int(v) for v in s[1].split()[2:]) for s in st if s[0] == "cmd" and s[1].startswith("forceload add")]
        if not step_holds or not (st[-1][0] == "cmd" and st[-1][1].startswith("forceload remove")):
            R.err("steps", "R9AF does not hold the farm's chunks round the build and release them after")
        holds += step_holds
    if rep.loads and sorted(rep.loads) != sorted(rep.removes):
        R.err("steps", "build.mcfunction adds forceloads %s and removes %s" % (rep.loads, rep.removes))
    outside = [k for k in rep.state if not any(h[0] <= k[0] <= h[2] and h[1] <= k[2] <= h[3] for h in holds if len(h) == 4)]
    if outside:
        R.err("steps", "%d cell(s) written outside every forceload, first %s" % (len(outside), sorted(outside)[0]))


def check_fruit(R, D, rep, W):
    """Every fruit hangs on a leaf it faces in the final world and was never orphaned on the way there; its colour is its
    grove's (sheds and the stall by box); each tree carries its design's count."""
    for fruit, sup, st, fn in rep.breaks:
        R.err("fruit", "the fruit at %s lost its leaf %s to %s in %s: it breaks there" % (fruit, sup, base(st), fn))
    sheds = {s["id"]: (D.fp(s["footprint"]), set(s["colours"])) for s in D.doc["sheds"]}
    stall = D.fp(D.doc["stall"]["footprint"])
    count = Counter()
    per_place = Counter()
    for k, st in rep.state.items():
        b = base(st)
        m = FRUIT.match(b)
        if not m:
            continue
        colour = m.group(1)
        count[colour] += 1
        p = props(st)
        if p.get("age") not in ("0", "1", "2", "3"):
            R.err("fruit", "%s at %s has age %s" % (b, k, p.get("age")))
        d = DIRS.get(p.get("facing"))
        if d is None:
            R.err("fruit", "%s at %s faces %s" % (b, k, p.get("facing")))
            continue
        sup = (k[0] + d[0], k[1], k[2] + d[1])
        if W.at(sup) != LEAVES:
            R.err("fruit", "%s at %s faces %s, where the final world holds %s, not apricorn leaves: it drops"
                  % (b, k, p["facing"], W.at(sup)))
        if colour not in D.colours:
            R.err("fruit", "%s at %s is not one of the seven colours" % (b, k))
        place = None
        for g in D.groves:
            x0, z0, x1, z1 = g["box"]
            if x0 <= k[0] <= x1 and z0 <= k[2] <= z1:
                place = "grove_" + g["colour"]
                if colour != g["colour"]:
                    R.err("fruit", "%s at %s hangs in the %s grove" % (b, k, g["colour"]))
        for sid, ((x0, z0, x1, z1), cols) in sheds.items():
            if x0 <= k[0] <= x1 and z0 <= k[2] <= z1:
                place = sid
                if colour not in cols:
                    R.err("fruit", "%s at %s is not one of %s's colours %s" % (b, k, sid, sorted(cols)))
        x0, z0, x1, z1 = stall
        if x0 <= k[0] <= x1 and z0 <= k[2] <= z1:
            place = "stall"
        if place is None:
            R.err("fruit", "%s at %s is in no grove, shed or stall" % (b, k))
        per_place[place] += 1
    if not count:
        R.err("fruit", "the build hangs no fruit")
    return count, per_place


def grove_floor(W, box):
    """The terrace floor the pack built: the y of the floor-top block most interior columns hold."""
    x0, z0, x1, z1 = box
    tops = Counter()
    for x in range(x0 + 1, x1):
        for z in range(z0 + 1, z1):
            g = W.ground(x, z)
            for y in range(g + 20, g - 20, -1):
                if W.at((x, y, z)) in ("minecraft:grass_block", "minecraft:coarse_dirt", "minecraft:dirt_path"):
                    tops[y] += 1
                    break
    return tops.most_common(1)[0][0] if tops else None


def expected_floor(D, g, gr, gate=None):
    """ground_rule: of the levels that leave a gate within one block of its outside ground, the least earthwork over
    the 41x29 box, then the nearest the median. East/west gates stand at the alley ends (grove_layout.why); for a
    north/south gate the data names no candidates, so the built gate is the only one (`gate`)."""
    x0, z0, x1, z1 = gr["box"]
    G = [g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    lo, hi, med = min(G), max(G), statistics.median(G)
    side = gr["gate_side"]
    cands = []
    if side in ("east", "west"):
        gx = x1 if side == "east" else x0
        ox = gx + (1 if side == "east" else -1)
        for pair in D.L["alleys_z"]:
            for az in pair:
                cands.append(((gx, gr["wc"][1] + az), (ox, gr["wc"][1] + az)))
    elif gate is not None:
        oz = gate[1] + (-1 if side == "north" else 1)
        cands.append((gate, (gate[0], oz)))
    best = None
    for F in range(lo, hi + 1):
        if not any(abs(g(*o) - F) <= 1 for _gt, o in cands):
            continue
        key = (sum(abs(v - F) for v in G), abs(F - med))
        if best is None or key < best[0]:
            best = (key, F)
    return (best[1] if best else None), cands


def check_terraces(R, D, W):
    facts = {}
    L = D.L
    walls = {L["wall"], L["wall_mossy"]}
    for gr in D.groves:
        c = gr["colour"]
        x0, z0, x1, z1 = gr["box"]
        Fb = grove_floor(W, gr["box"])
        if Fb is None:
            R.err("terrace", "%s: no terrace floor written" % c)
            continue
        gates = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
                 if (x in (x0, x1) or z in (z0, z1)) and W.at((x, Fb + 1, z)) == L["gate"]]
        side = gr["gate_side"]
        on_side = {"east": lambda x, z: x == x1, "west": lambda x, z: x == x0,
                   "north": lambda x, z: z == z0, "south": lambda x, z: z == z1}[side]
        if len(gates) != 1 or not on_side(*gates[0]):
            R.err("terrace", "%s: gates at floor+1 %s, expected one on the %s side" % (c, gates, side))
        gate = gates[0] if gates else None
        Fe, cands = expected_floor(D, W.ground, gr, gate)
        facts[c] = {"floor": Fb, "expected": Fe, "gate": gate}
        if Fe is None:
            R.err("terrace", "%s: no level leaves a gate within one block of its outside ground" % c)
        elif Fe != Fb:
            R.err("terrace", "%s: floor y%d, the ground rule gives y%d" % (c, Fb, Fe))
        if gate is not None:
            if side in ("east", "west") and gate not in [gt for gt, _o in cands]:
                R.err("terrace", "%s: the gate %s is not at an alley end" % (c, gate))
            d = DIRS[side]
            out = (gate[0] + d[0], gate[1] + d[1])
            diff = W.ground(*out) - Fb
            facts[c]["gate_outside_diff"] = diff
            if abs(diff) > 1:
                R.err("terrace", "%s: the gate's outside ground y%d is %d from the floor y%d: not walkable both ways"
                      % (c, W.ground(*out), diff, Fb))
            if not floor_ok(W.at((gate[0], Fb, gate[1]))) or W.at((gate[0], Fb + 2, gate[1])) not in (AIR, NAT_AIR):
                R.err("terrace", "%s: the gate %s has no sill under it or no headroom" % (c, gate))
        bad_top, natural_left, bad_fill, bad_wall, open_edge = [], [], [], [], []
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                gy = W.ground(x, z)
                edge = x in (x0, x1) or z in (z0, z1)
                if not edge:
                    if W.at((x, Fb, z)) not in (L["floor"], L["mulch"], "minecraft:dirt_path"):
                        bad_top.append((x, z))
                    if any(W.at((x, y, z)) == NAT_GROUND for y in range(Fb + 1, max(gy, Fb) + 2)):
                        natural_left.append((x, z))
                    if any(W.at((x, y, z)) != L["fill"] for y in range(gy + 1, Fb)):
                        bad_fill.append((x, z))
                    continue
                lo_, hi_ = (gy + 1, Fb) if gy < Fb else (Fb, gy)
                if (x, z) == gate:
                    continue
                if any(W.at((x, y, z)) not in walls for y in range(lo_, hi_ + 1)):
                    bad_wall.append((x, z))
                top = max(gy, Fb)
                if W.at((x, top + 1, z)) not in (L["fence"], "minecraft:spruce_fence"):
                    open_edge.append((x, z))
        for name, lst, what in (("floor top", bad_top, "interior column(s) whose top at the floor is not the floor, mulch or path"),
                                ("cut", natural_left, "interior column(s) with natural ground left above the floor"),
                                ("fill", bad_fill, "interior column(s) not filled with dirt from the ground to the floor"),
                                ("wall", bad_wall, "edge column(s) whose wall does not run from the ground to the floor"),
                                ("fence", open_edge, "edge column(s) with no fence on the wall top")):
            if lst:
                R.err("terrace", "%s: %d %s, first %s" % (c, len(lst), what, sorted(lst)[0]))
        # each tree: a trunk on the floor and its design's fruit
        lay = D.doc["tree_designs"][c]
        want = D.fruit_per_tree(c)
        if not 5 <= want <= 8:
            R.err("trees", "%s: the design carries %d fruit a tree, outside 5-8" % (c, want))
        for tz in L["tree_z"]:
            for tx in L["tree_x"]:
                X, Z = gr["wc"][0] + tx, gr["wc"][1] + tz
                if lay[0][3][3] in "LX" and W.at((X, Fb + 1, Z)) != "cobblemon:apricorn_log":
                    R.err("trees", "%s: no trunk at (%d, %d, %d)" % (c, X, Fb + 1, Z))
                n = sum(1 for dx in range(-3, 4) for dz in range(-3, 4) for y in range(Fb + 1, Fb + 1 + len(lay))
                        if is_fruit(W.at((X + dx, y, Z + dz))))
                if n != want:
                    R.err("trees", "%s: the tree at (%d, %d) carries %d fruit, its design %d" % (c, X, Z, n, want))
    return facts


def building_boxes(D):
    out = [(b["id"], D.fp(b["footprint"]), b) for b in D.doc["buildings"]]
    return out


def check_buildings(R, D, W):
    """floor = max ground under the footprint + 1 on the foundation; door cells open."""
    floors = {}
    for bid, (x0, z0, x1, z1), b in building_boxes(D):
        Fb = max(W.ground(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)) + 1
        floors[bid] = Fb
        bad_floor, bad_found = [], []
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                gy = W.ground(x, z)
                interior = x0 < x < x1 and z0 < z < z1
                if interior and W.at((x, Fb, z)) != base(b["floor"]):
                    bad_floor.append((x, z))
                for y in range(gy + 1, Fb):
                    if W.at((x, y, z)) in (AIR, NAT_AIR) or (interior and W.at((x, y, z)) != base(b["foundation"])):
                        bad_found.append((x, y, z))
        if bad_floor:
            R.err("building", "%s: %d interior column(s) with no %s at y%d (max ground + 1), first %s"
                  % (bid, len(bad_floor), b["floor"], Fb, sorted(bad_floor)[0]))
        if bad_found:
            R.err("building", "%s: %d foundation cell(s) missing under the floor, first %s" % (bid, len(bad_found), sorted(bad_found)[0]))
        door = b.get("door")
        if door:
            side, at = door["side"], door["at"]
            w, h = door.get("width", 1), door.get("height", 2)
            cells = []
            for i in range(w):
                off = at - (w // 2) + i
                if side in ("east", "west"):
                    x = x1 if side == "east" else x0
                    z = D.cz + off
                else:
                    z = z1 if side == "south" else z0
                    x = D.cx + off
                for dy in range(1, h + 1):
                    cells.append((x, Fb + dy, z))
            shut = [k for k in cells if not passable(W.at(k))]
            if shut:
                R.err("building", "%s: door cell(s) %s are not air or a door" % (bid, shut))
    return floors


def check_spots(R, D, W, farmer, merchant, reached):
    """The farmer and the keeper stand in two blocks of air on a floor, not on a path or a post; each can be reached."""
    paths = {(k[0], k[2]) for k, st in W.rep.state.items() if base(st) == "minecraft:dirt_path"}
    posts = {(k[0], k[2]) for k, st in W.rep.state.items() if base(st) == "minecraft:lantern"}
    for who, spot in (("the farmer", farmer), ("the stall keeper", merchant)):
        if spot is None:
            R.err("spots", "%s has no position in the steps/pack" % who)
            continue
        x, y, z = spot
        if not (passable(W.at(spot)) and passable(W.at((x, y + 1, z)))):
            R.err("spots", "%s at %s is not in two blocks of air (%s, %s)" % (who, spot, W.at(spot), W.at((x, y + 1, z))))
        if not floor_ok(W.at((x, y - 1, z))):
            R.err("spots", "%s at %s stands on %s" % (who, spot, W.at((x, y - 1, z))))
        if (x, z) in paths or W.at((x, y - 1, z)) == "minecraft:dirt_path":
            R.err("spots", "%s at %s stands on a path" % (who, spot))
        if (x, z) in posts:
            R.err("spots", "%s at %s stands in a lantern post's column" % (who, spot))
    if farmer is not None:
        if farmer[1] != W.ground(farmer[0], farmer[2]) + 1:
            R.err("spots", "the farmer's feet y%d are not her column's ground + 1 (y%d)" % (farmer[1], W.ground(farmer[0], farmer[2]) + 1))
        near = [k for k in reached if abs(k[0] - farmer[0]) + abs(k[2] - farmer[2]) == 1 and abs(k[1] - farmer[1]) <= 1]
        if not near:
            R.err("spots", "no reachable cell beside the farmer at %s" % (farmer,))
    if merchant is not None:
        st = D.doc["stall"]
        x0, z0, x1, z1 = D.fp(st["footprint"])
        cust = (x1 + 1, merchant[1], (z0 + z1) // 2)
        cells = [k for k in reached if (k[0], k[2]) == (cust[0], cust[2])]
        if not cells:
            R.err("spots", "the customer cell %s in front of the stall's counter is not reachable from the track" % (cust,))
        elif min(math.dist((c[0] + .5, c[1] + EYE, c[2] + .5), (merchant[0] + .5, merchant[1] + 1, merchant[2] + .5))
                 for c in cells) > 3.0:
            R.err("spots", "the customer cell %s is out of the 3-block entity reach of the keeper %s" % (cust, merchant))
        yaw = D.doc["merchant"]["yaw"]
        fx = -math.sin(math.radians(yaw))
        if (cust[0] - merchant[0]) * fx <= 0:
            R.err("spots", "the keeper's yaw %s faces away from the counter" % yaw)


JUMP = 1.25         # a player's jump clears 1.25 blocks; 0.6 is a plain step


def surfaces(W, k):
    """The heights a body can stand at in the feet cell k: the top of what is under it (a bottom slab half a block
    down; a bottom stair both its low half and its high half, orientation ignored, which can only be generous)."""
    x, y, z = k
    below = W.full((x, y - 1, z))
    b, p = base(below), props(below)
    if b.endswith("_stairs") and p.get("half", "bottom") == "bottom":
        return (y - 0.5, float(y))
    if b.endswith("_slab") and p.get("type") == "bottom":
        return (y - 0.5,)
    return (float(y),)


def flood(W, start, box):
    """Every standable cell reachable from start by 4-way moves whose rise or drop is at most JUMP (so every move can
    be walked back), with headroom for a jump."""
    x0, z0, x1, z1 = box
    if not W.standable(start):
        return set()
    seen = {start}
    q = deque([start])
    while q:
        x, y, z = q.popleft()
        here = surfaces(W, (x, y, z))
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (x0 <= nx <= x1 and z0 <= nz <= z1):
                continue
            for ny in (y, y + 1, y - 1, y + 2, y - 2):
                k = (nx, ny, nz)
                if k in seen or not W.standable(k):
                    continue
                there = surfaces(W, k)
                rise = min((abs(b - a), b - a) for a in here for b in there)[1]
                if abs(rise) > JUMP:
                    continue
                if rise > 0.6 and not passable(W.at((x, y + 2, z))):
                    continue                          # no headroom to jump
                seen.add(k)
                q.append(k)
    return seen


def hold(rep):
    xs = [k[0] for k in rep.state]
    zs = [k[2] for k in rep.state]
    return min(xs), min(zs), max(xs), max(zs)


def check_walk(R, D, W, fruit_count):
    hx0, hz0, hx1, hz1 = hold(W.rep)
    box = (hx0 - 3, hz0 - 3, hx1 + 3, hz1 + 3)
    seg = [s for s in D.doc["paths"]["segments"] if "entry" in s["name"]]
    sx, sz = D.W(*seg[0]["points"][-1]) if seg else D.W(*D.doc["track_sign"]["at"])
    start = None
    for y in range(W.ground(sx, sz) + 3, W.ground(sx, sz) - 3, -1):
        if W.standable((sx, y, sz)):
            start = (sx, y, sz)
            break
    if start is None:
        R.err("walk", "the entry track's end (%d, %d) has no standable cell" % (sx, sz))
        return set()
    reached = flood(W, start, box)
    # every grove's gate, the farmhouse and barn interiors
    for gr in D.groves:
        x0, z0, x1, z1 = gr["box"]
        if not any(x0 < k[0] < x1 and z0 < k[2] < z1 for k in reached):
            R.err("walk", "the %s grove's floor cannot be walked into from the track" % gr["colour"])
    for bid, (x0, z0, x1, z1), _b in building_boxes(D):
        if not any(x0 < k[0] < x1 and z0 < k[2] < z1 for k in reached):
            R.err("walk", "%s's interior cannot be walked into from the track" % bid)
    # every fruit within reach of a cell a player can walk to (line of sight not modelled)
    by_col = {}
    for k in reached:
        by_col.setdefault((k[0], k[2]), []).append(k[1])
    unpicked = []
    for k, st in W.rep.state.items():
        if not is_fruit(base(st)):
            continue
        ok = False
        for dx in range(-5, 6):
            for dz in range(-5, 6):
                for y in by_col.get((k[0] + dx, k[2] + dz), ()):
                    if math.dist((k[0] + dx + .5, y + EYE, k[2] + dz + .5), (k[0] + .5, k[1] + .5, k[2] + .5)) <= REACH:
                        ok = True
                        break
                if ok:
                    break
            if ok:
                break
        if not ok:
            unpicked.append(k)
    if unpicked:
        R.err("walk", "%d fruit out of reach (%.1f) of every walkable cell, first %s" % (len(unpicked), REACH, sorted(unpicked)[0]))
    return reached


def check_blocks(R, D, rep, jar, spawn_blocks, policy):
    allowed = D.allowed_blocks()
    listed = set(D.doc["blocks"]["ids"])
    written = Counter(base(s) for s in rep.state.values())
    for b in sorted(written):
        if b not in allowed:
            R.err("blocks", "%s (%d) is written but nothing in the design names it" % (b, written[b]))
        if b not in listed:
            R.err("blocks", "%s (%d) is written but not in blocks.ids" % (b, written[b]))
        if jar is not None and b.startswith("cobblemon:") and not jar.has_block(b):
            R.err("blocks", "%s is not a block in the Cobblemon jar" % b)
        if b in ("minecraft:water", "minecraft:lava") or b.endswith(("_bed", "chest")):
            R.err("blocks", "%s is written (no chest, bed or placed water)" % b)
    wl = [s for s in rep.state.values() if props(s).get("waterlogged") == "true"]
    if wl:
        R.err("blocks", "%d waterlogged block(s), e.g. %s" % (len(wl), wl[0]))
    nonpersist = [k for k, s in rep.state.items() if base(s) == LEAVES and props(s).get("persistent") != "true"]
    if nonpersist:
        R.err("blocks", "%d apricorn leaves not persistent (they decay, and their fruit with them), first %s"
              % (len(nonpersist), sorted(nonpersist)[0]))
    allowed_sc = set(D.doc["blocks"]["spawn_conditions_allowed"])
    for b in sorted(written):
        if b not in spawn_blocks:
            continue
        if b not in allowed_sc:
            R.err("blocks", "%s is a spawn condition (data/spawn_blocks.json) and not one of the seven fruits" % b)
        if not any(b in w.get("blocks", []) and "apricorn_farm" in (w.get("scope") or "") for w in policy["whitelist"]):
            R.err("blocks", "%s is a spawn condition and no data/spawn_block_policy.json entry scoped to apricorn_farm allows it" % b)
    unused = sorted(listed - set(written))
    if unused:
        R.note("blocks.ids never written: %s" % ", ".join(unused))
    return written


def river_wet(rivers, g, x, z):
    for c in rivers:
        half = max((c.get("character") or {}).get("width") or [32]) / 2.0 + 1
        pl = c.get("graded_polyline") or []
        for a, b in zip(pl, pl[1:]):
            ax, az, bx, bz = a[0], a[1], b[0], b[1]
            dx, dz = bx - ax, bz - az
            L2 = dx * dx + dz * dz
            t = 0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / L2))
            px, pz = ax + t * dx, az + t * dz
            if math.hypot(x - px, z - pz) <= half and g(x, z) < a[2] + t * (b[2] - a[2]):
                return True
    return False


class Wet:
    """(x, z) -> water over the column: tools/water_mask.py (lakes, sea) or a river corridor (segments, not vertices)."""

    def __init__(self, g, near, reach=600):
        import water_mask as WM
        self.WM, self.g, self.bodies = WM, g, WM.bodies()
        rv = jload(DATA / "rivers.json")
        self.rivers = [c for c in rv.get("courses") or []
                       if any(math.hypot(p[0] - near[0], p[1] - near[1]) < reach for p in c.get("graded_polyline") or [])]

    def __call__(self, x, z):
        if self.WM.level_at(x, z, self.g, self.bodies)[0] is not None:
            return True
        return river_wet(self.rivers, self.g, x, z)


def check_wet(R, rep, wet):
    cols = sorted({(k[0], k[2]) for k in rep.state})
    bad = [c for c in cols if wet(*c)]
    if bad:
        R.err("wet", "%d written column(s) under water, first %s" % (len(bad), bad[0]))
    return len(cols)


def authored_points(data_dir, skip):
    """[(x, z, file)] every x/z another data file authors: {x, z} dicts, [x, z] pairs, [x, y, z] / [x, z, y] triples,
    and min_x/max_x/min_z/max_z boxes (as their four corners and centre). Coordinates are inside the 8192 world."""
    out = []

    def w(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 8192

    def walk(o, f):
        if isinstance(o, dict):
            if w(o.get("x")) and w(o.get("z")):
                out.append((o["x"], o["z"], f))
            if all(w(o.get(k)) for k in ("min_x", "max_x", "min_z", "max_z")):
                for x in (o["min_x"], o["max_x"]):
                    for z in (o["min_z"], o["max_z"]):
                        out.append((x, z, f))
            for v in o.values():
                walk(v, f)
        elif isinstance(o, list):
            nums = [v for v in o if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if len(nums) == len(o) and len(o) in (2, 3, 4):
                if len(o) == 2 and w(o[0]) and w(o[1]):
                    out.append((o[0], o[1], f))
                elif len(o) == 3 and w(o[0]):
                    if -64 <= o[1] <= 320 and w(o[2]):
                        out.append((o[0], o[2], f))
                    if w(o[1]):
                        out.append((o[0], o[1], f))
                elif len(o) == 4 and all(w(v) for v in o):
                    out.append((o[0], o[1], f))
                    out.append((o[2], o[3], f))
            for v in o:
                walk(v, f)
    for p in sorted(Path(data_dir).glob("*.json")):
        if p.name in skip:
            continue
        try:
            walk(jload(p), p.name)
        except ValueError:
            continue
    return out


def rect_dist(r, x, z):
    x0, z0, x1, z1 = r
    dx = max(x0 - x, 0, x - x1)
    dz = max(z0 - z, 0, z - z1)
    return math.hypot(dx, dz)


def check_siting(R, D, rep, data_dir=DATA):
    rules = D.doc["rules"]
    cols = sorted({(k[0], k[2]) for k in rep.state})
    hx0, hz0, hx1, hz1 = hold(rep)
    near = {}

    def nearest(points, clear):
        best = (1e9, None)
        for (px, pz, f) in points:
            if not (hx0 - clear - 1 <= px <= hx1 + clear + 1 and hz0 - clear - 1 <= pz <= hz1 + clear + 1):
                d0 = rect_dist((hx0, hz0, hx1, hz1), px, pz)
                if d0 < best[0]:
                    best = (d0, (px, pz, f))
                continue
            d = min(math.hypot(px - x, pz - z) for x, z in cols)
            if d < best[0]:
                best = (d, (px, pz, f))
        return best
    pts = authored_points(data_dir, {"apricorn_farm.json", "regions.json", "routes.json", "route_paths.json", "towns.json"})
    # a site another file anchors ON this farm ("anchor": "apricorn_farm") is a resident of the farm, exempt at exactly
    # its expected_at column and nowhere else (2026-10-08: the Produce Buyer at Hollin's stall)
    pb = Path(data_dir) / "produce_buyer.json"
    own = {(s["expected_at"][0], s["expected_at"][2]) for s in (jload(pb).get("sites") or [] if pb.is_file() else [])
           if s.get("anchor") == "apricorn_farm" and s.get("expected_at")}
    pts = [p for p in pts if not (p[2] == "produce_buyer.json" and (p[0], p[1]) in own)]
    d, w = nearest(pts, rules["authored_clearance"])
    near["authored"] = (round(d), w)
    if d < rules["authored_clearance"]:
        R.err("siting", "(%s, %s) in data/%s is %.0f blocks from a written column (needs %d)" % (w[0], w[1], w[2], d, rules["authored_clearance"]))
    rp = jload(Path(data_dir) / "route_paths.json")["paths"]
    rpts = [(p[0], p[1], "route_paths.json " + rid) for rid, pl in rp.items() for p in pl]
    d, w = nearest(rpts, rules["route_clearance"])
    near["route_path"] = (round(d), w)
    if d < rules["route_clearance"]:
        R.err("siting", "the walked route %s passes %.0f blocks from the farm (needs %d)" % (w[2], d, rules["route_clearance"]))
    boxes = []
    for rt in jload(Path(data_dir) / "routes.json")["routes"]:
        for b in (rt.get("spawn_scope") or {}).get("boxes") or []:
            boxes.append(((b["min_x"], b["min_z"], b["max_x"], b["max_z"]), "%s %s" % (rt["id"], b.get("id"))))
    bd = min(((min(rect_dist(r, x, z) for x, z in cols), n) for r, n in boxes
              if rect_dist(r, (hx0 + hx1) / 2, (hz0 + hz1) / 2) < 2000), default=(1e9, None))
    near["corridor"] = (round(bd[0]), bd[1])
    if bd[0] < rules["route_clearance"]:
        R.err("siting", "the corridor box %s is %.0f blocks from the farm (needs %d)" % (bd[1], bd[0], rules["route_clearance"]))
    td = []
    for t in jload(Path(data_dir) / "towns.json")["towns"]:
        f = t.get("footprint") or {}
        if all(k in f for k in ("min_x", "max_x", "min_z", "max_z")):
            r = (f["min_x"], f["min_z"], f["max_x"], f["max_z"])
            if rect_dist(r, (hx0 + hx1) / 2, (hz0 + hz1) / 2) < 2000:
                td.append((min(rect_dist(r, x, z) for x, z in cols), t["id"]))
    tmin = min(td, default=(1e9, None))
    near["town"] = (round(tmin[0]), tmin[1])
    if tmin[0] < rules["town_clearance"]:
        R.err("siting", "the town %s's footprint is %.0f blocks from the farm (needs %d)" % (tmin[1], tmin[0], rules["town_clearance"]))
    rr = jload(Path(data_dir) / "rift_regions.json").get("regions", {})
    for rid, r in rr.items():
        bb = r.get("bbox")
        if bb and not (bb[2] < hx0 or bb[0] > hx1 or bb[3] < hz0 or bb[1] > hz1):
            R.err("siting", "the farm's box overlaps the Rift region %s %s" % (rid, bb))
    R.note("nearest: authored x/z %s; walked route %s; corridor box %s; town footprint %s"
           % (near["authored"], near["route_path"][0], near["corridor"], near["town"]))
    return near


def light_map(W, box, ylo, yhi):
    """{cell: block light} from lanterns and lit campfires inside box."""
    x0, z0, x1, z1 = box
    lvl = {}
    buckets = [[] for _ in range(16)]
    for k, st in W.rep.state.items():
        b = base(st)
        if b == "minecraft:lantern" or (b == "minecraft:campfire" and props(st).get("lit", "true") == "true"):
            lvl[k] = 15
            buckets[15].append(k)
    for L in range(15, 1, -1):
        for k in buckets[L]:
            if lvl.get(k, 0) != L:
                continue
            x, y, z = k
            for n in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)):
                if not (x0 <= n[0] <= x1 and z0 <= n[2] <= z1 and ylo <= n[1] <= yhi):
                    continue
                b = W.at(n)
                if not light_through(b):
                    continue
                nl = L - 1 - (1 if b == LEAVES else 0)
                if nl > lvl.get(n, 0):
                    lvl[n] = nl
                    if nl > 1:
                        buckets[nl].append(n)
    return lvl


def check_light(R, D, W, floors, terrace):
    hx0, hz0, hx1, hz1 = hold(W.rep)
    ys = [k[1] for k in W.rep.state]
    lvl = light_map(W, (hx0 - 16, hz0 - 16, hx1 + 16, hz1 + 16), min(ys) - 2, max(ys) + 2)
    cells = {}
    for k, st in W.rep.state.items():
        if base(st) == "minecraft:dirt_path":
            f = (k[0], k[1] + 1, k[2])
            if passable(W.at(f)):
                cells[f] = "path"
    for gr in D.groves:
        F = (terrace.get(gr["colour"]) or {}).get("floor")
        if F is None:
            continue
        x0, z0, x1, z1 = gr["box"]
        for x in range(x0 + 1, x1):
            for z in range(z0 + 1, z1):
                f = (x, F + 1, z)
                if W.standable(f):
                    cells.setdefault(f, "grove_" + gr["colour"])
    for bid, (x0, z0, x1, z1), _b in building_boxes(D):
        Fb = floors.get(bid)
        for x in range(x0 + 1, x1):
            for z in range(z0 + 1, z1):
                f = (x, Fb + 1, z)
                if W.standable(f):
                    cells.setdefault(f, bid)
    dark = sorted(k for k in cells if lvl.get(k, 0) == 0)
    dim = [k for k in cells if lvl.get(k, 0) < 8]
    if dark:
        where = Counter(cells[k] for k in dark)
        R.err("light", "%d walkable cell(s) at block light 0 (hostiles spawn there): %s; first %s"
              % (len(dark), dict(where), dark[0]))
    R.note("light: %d walkable cells checked, %d under block light 8, %d at 0" % (len(cells), len(dim), len(dark)))
    return lvl, cells


def check_attached(R, W):
    """Lanterns, signs and doors the game would drop at once or at their first update."""
    bad = []
    for k, st in W.rep.state.items():
        b = base(st)
        p = props(st)
        x, y, z = k
        if b == "minecraft:lantern":
            if p.get("hanging") == "true":
                s = W.at((x, y + 1, z))
                if s in (AIR, NAT_AIR, LEAVES) or is_fruit(s) or passable(s):
                    bad.append((k, "a hanging lantern under %s" % s))
            else:
                s = W.at((x, y - 1, z))
                if s in (AIR, NAT_AIR, LEAVES, "minecraft:lantern", "minecraft:campfire") or is_fruit(s) or passable(s):
                    bad.append((k, "a standing lantern on %s (no centre support)" % s))
        elif b.endswith("_wall_sign"):
            d = DIRS.get(p.get("facing"))
            if d:
                s = W.at((x - d[0], y, z - d[1]))
                if not floor_ok(s):
                    bad.append((k, "a wall sign on %s" % s))
        elif b.endswith("_sign"):
            s = W.at((x, y - 1, z))
            if s in (AIR, NAT_AIR) or passable(s):
                bad.append((k, "a sign on %s" % s))
        elif b.endswith("_door") and p.get("half") == "lower":
            if not floor_ok(W.at((x, y - 1, z))):
                bad.append((k, "a door on %s" % W.at((x, y - 1, z))))
    for k, why in sorted(bad):
        R.err("attached", "%s at %s: unsupported, it breaks at its first shape update from that side" % (why, k))


def check_paths(R, D, W):
    """A path is its own column's top block swapped for dirt path: outside the groves its y is the ground's."""
    boxes = [g["box"] for g in D.groves]
    off = []
    n = 0
    for k, st in W.rep.state.items():
        if base(st) != "minecraft:dirt_path":
            continue
        if any(b[0] <= k[0] <= b[2] and b[1] <= k[2] <= b[3] for b in boxes):
            continue
        n += 1
        if k[1] != W.ground(k[0], k[2]):
            off.append(k)
    if off:
        R.err("paths", "%d path cell(s) off their column's ground, first %s (ground y%d)"
              % (len(off), sorted(off)[0], W.ground(sorted(off)[0][0], sorted(off)[0][2])))
    if n == 0:
        R.err("paths", "the build lays no path")


def summon_merchant(lines):
    s = [l for l in lines if l.startswith("summon ")]
    return s


def check_merchant(R, D, mlines, dlines, jar, entity_steps):
    m = D.doc["merchant"]
    s = summon_merchant(mlines)
    spot = None
    if len(s) != 1:
        R.err("merchant", "merchant.mcfunction summons %d entities, not one" % len(s))
        return None
    mm = re.match(r"^summon (\S+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (\{.*\})$", s[0])
    if not mm:
        R.err("merchant", "the summon line does not parse: %s" % s[0][:80])
        return None
    spot = (math.floor(float(mm.group(2))), math.floor(float(mm.group(3))), math.floor(float(mm.group(4))))
    if (spot[0], spot[2]) != D.W(*m["at"]):
        R.err("merchant", "the keeper is summoned at %s, the data's spot is %s" % (spot, D.W(*m["at"])))
    nbt = mm.group(5)
    items = re.findall(r'id:"([^"]+)"', nbt)
    prices = re.findall(r'Price:"([^"]*)"', nbt)
    want = [(it["item"], it["price"]) for it in m["stock"]]
    if list(zip(items, prices)) != [(i, str(p)) for i, p in want]:
        R.err("merchant", "the shop sells %s, the data %s" % (list(zip(items, prices)), want))
    for p in prices:
        if not re.fullmatch(r"[1-9]\d*", p):
            R.err("merchant", "the price %r is not a positive integer" % p)
    for i in items:
        if re.search(r"_apricorn$|_apricorn_seed$|copper_ingot|_ball$", i):
            R.err("merchant", "%s is sold, and data/apricorn_farm.json merchant.left_out withholds it" % i)
        if jar is not None and i.startswith("cobblemon:") and not jar.has_item(i):
            R.err("merchant", "%s is not an item in the Cobblemon jar" % i)
    tag = m["tag"]
    if "Tags:[\"%s\",\"%s_new\"]" % (tag, tag) not in nbt:
        R.err("merchant", "the keeper is not summoned with tags %s and %s_new" % (tag, tag))
    if not any(l.startswith("schedule function %s:%s/merchant_done" % (NS, FOLDER)) for l in mlines):
        R.err("merchant", "the summon does not schedule merchant_done")
    if not any(("kill @e[tag=%s,tag=!%s_new]" % (tag, tag)) in l for l in dlines):
        R.err("merchant", "merchant_done does not kill the older copies by tag")
    if not any(l.startswith("tag @e[tag=%s,tag=%s_new] remove %s_new" % (tag, tag, tag)) for l in dlines):
        R.err("merchant", "merchant_done does not clear the new tag")
    if entity_steps is not None:
        es = [tuple(s) for s in entity_steps]
        fns = [s for s in es if s[0] == "fn"]
        if fns != [("fn", "%s:%s/merchant" % (NS, FOLDER))]:
            R.err("merchant", "R18AF runs %s, not the merchant function once" % fns)
        adds = [s[1] for s in es if s[0] == "cmd" and s[1].startswith("forceload add")]
        if not any(a.split()[2:4] == [str(spot[0]), str(spot[2])] for a in adds):
            R.err("merchant", "R18AF does not forceload the keeper's column %s" % ((spot[0], spot[2]),))
    return spot


def check_dialogue(R, D, entity_steps, data_dir=DATA):
    import compile_dialogue as CD
    cid = D.doc["npc"]["conversation"]
    try:
        files, done, refused = CD.build_all(Path(data_dir))
    except SystemExit as e:
        R.err("dialogue", "compile_dialogue --all refuses: %s" % e)
        return None
    if cid not in done:
        R.err("dialogue", "%s does not compile: %s" % (cid, refused.get(cid, "absent")))
        return None
    dl = jload(Path(data_dir) / "dialogue.json")
    conv = next(c for c in dl["conversations"] if c["id"] == cid)
    npc = conv.get("npc_id")
    if "data/%s/npcs/%s.json" % (NS, npc) not in files:
        R.err("dialogue", "%s compiles no NPC class %s" % (cid, npc))
    q = [x for x in jload(Path(data_dir) / "quests.json")["quests"] if x["id"] == conv.get("quest_id")]
    if not q or cid not in q[0].get("dialogue_ids", []):
        R.err("dialogue", "the quest %s does not list %s" % (conv.get("quest_id"), cid))
    farmer = None
    if entity_steps is not None:
        npcs = [s[1] for s in entity_steps if s[0] == "npc"]
        if len(npcs) != 1 or npcs[0][0] != cid or npcs[0][2] != "%s:%s" % (NS, npc):
            R.err("dialogue", "R18AF places %s, not the farmer %s:%s once" % (npcs, NS, npc))
        elif npcs:
            farmer = tuple(npcs[0][1])
            if npcs[0][3] != D.doc["npc"]["yaw"]:
                R.err("dialogue", "the farmer is turned to %s, the data says %s" % (npcs[0][3], D.doc["npc"]["yaw"]))
            if (farmer[0], farmer[2]) != D.W(*D.doc["npc"]["at"]):
                R.err("dialogue", "the farmer stands at %s, the data's spot is %s" % (farmer, D.W(*D.doc["npc"]["at"])))
    return farmer


def check_reapply(R, text):
    """Step order, the pack list and the prepare job, read from tools/reapply.py as text."""
    def at(s):
        return text.find(s)
    if '"cobblers_apricorn_farm"' not in text:
        R.err("reapply", "cobblers_apricorn_farm is not in tools/reapply.py's pack list")
    r9af, r9e = at('("R9AF"'), at('("R9E"')
    if r9af < 0 or r9e < 0 or r9af > r9e:
        R.err("reapply", "R9AF is not appended before R9E (%d, %d)" % (r9af, r9e))
    r17n, r18af = at('("R17N"'), at('("R18AF"')
    if r17n < 0 or r18af < 0 or r18af < r17n:
        R.err("reapply", "R18AF is not appended after R17N (%d, %d)" % (r17n, r18af))
    if "apricorn_farm.placement_steps()" not in text[r9af:r9e] if r9af >= 0 else True:
        R.err("reapply", "R9AF does not take its actions from apricorn_farm.placement_steps()")
    if "apricorn_farm.entity_steps()" not in text[r18af:r18af + 400] if r18af >= 0 else True:
        R.err("reapply", "R18AF does not take its actions from apricorn_farm.entity_steps()")
    b = at('add("apricorn_farm:build", "apricorn_farm.py", "build"')
    a = at('add("apricorn_farm_audit", "apricorn_farm_audit.py"')
    cd = at('J.append(("compile_dialogue"')
    if b < 0:
        R.err("reapply", "no prepare job runs apricorn_farm.py build")
    if a < 0 or a < b:
        R.err("reapply", "the prepare job apricorn_farm_audit is missing or runs before apricorn_farm:build")
    if cd >= 0 and a >= 0 and a < cd:
        R.err("reapply", "the audit runs before compile_dialogue")


# --------------------------------------------------------------------------------------------- the economy
def economy(R, D, fruit_count, jar, data_dir=DATA):
    """REPORTED, not failed: apricorns per regrowth cycle and the balls they make, against the markets' badge gates."""
    m = jload(Path(data_dir) / "markets.json")
    sold = {}
    for c in m["counters"]:
        for o in c.get("stock") or []:
            if str(o.get("item", "")).endswith("_ball"):
                sold.setdefault(o["item"], []).append((c.get("badge"), c["id"], o.get("price")))
    rec = recipes(jar) if jar is not None else {
        "poke_ball": ({"cobblemon:red_apricorn": 4}, "cobblemon:tier_1_poke_ball_materials", 4),
        "great_ball": ({"cobblemon:blue_apricorn": 2, "cobblemon:red_apricorn": 2}, "cobblemon:tier_2_poke_ball_materials", 4),
        "ultra_ball": ({"cobblemon:black_apricorn": 2, "cobblemon:yellow_apricorn": 2}, "cobblemon:tier_3_poke_ball_materials", 4)}
    # 1 in 5 random ticks advances a stage; randomTickSpeed 3 random ticks a 16^3 section a game tick
    per_stage_s = 5 * (4096 / 3.0) / 20.0
    cycle_min = 3 * per_stage_s / 60.0
    lines = ["per regrowth cycle (all 550 if every fruit is ripe and picked; a stage is 1 in 5 random ticks, "
             "%.1f min from picked to ripe at randomTickSpeed 3, only while a player is near): %s, %d in all"
             % (cycle_min, ", ".join("%s %d" % (c, fruit_count.get(c, 0)) for c in D.colours), sum(fruit_count.values()))]
    have = {"cobblemon:%s_apricorn" % c: n for c, n in fruit_count.items()}
    for ball, (need, tier, out) in rec.items():
        crafts = min(have.get(i, 0) // n for i, n in need.items())
        gate = sold.get("cobblemon:" + ball, [])
        lines.append("%s: %s + 1 #%s -> %d; %d crafts a cycle = %d balls (%d ingots); sold at %s"
                     % (ball, " + ".join("%d %s" % (n, i.split(":")[1]) for i, n in need.items()), tier, out, crafts,
                        crafts * out, crafts, ", ".join("%s badge %s at %s" % (cid, b, p) for b, cid, p in gate)
                        or "the Mart (data/traders.json mart, 200: relayed, its prose)"))
    red = have.get("cobblemon:red_apricorn", 0)
    pb = (red // 4) * 4
    inc = m.get("income_basis", {}).get("cumulative_by_badge", {})
    lines.append("red alone: %d Poke Balls a cycle = $%s at the Mart's 200, against $%s cumulative income by badge 1 "
                 "(data/markets.json income_basis, itself relayed)" % (pb, format(pb * 200, ","), format(inc.get("1", 0), ",")))
    gb = min(have.get("cobblemon:blue_apricorn", 0) // 2, red // 2) * 4
    ub = min(have.get("cobblemon:black_apricorn", 0) // 2, have.get("cobblemon:yellow_apricorn", 0) // 2) * 4
    gp = min((p for b, c, p in sold.get("cobblemon:great_ball", []) if p), default=0)
    up = min((p for b, c, p in sold.get("cobblemon:ultra_ball", []) if p), default=0)
    gbadge = min((b for b, c, p in sold.get("cobblemon:great_ball", []) if b is not None), default=None)
    ubadge = min((b for b, c, p in sold.get("cobblemon:ultra_ball", []) if b is not None), default=None)
    lines.append("ungated at the farm from badge 0: %d Great Balls a cycle (the counter sells them from badge %s at %d: "
                 "$%s) and %d Ultra Balls (from badge %s at %d: $%s); the binding gate becomes iron and gold ingots"
                 % (gb, gbadge, gp, format(gb * gp, ","), ub, ubadge, up, format(ub * up, ",")))
    R.economy = lines
    return {"cycle_min": cycle_min, "poke": pb, "great": gb, "ultra": ub}


# --------------------------------------------------------------------------------------------- the audit
def audit(doc, g, pack, wet=None, jar=None, steps=None, entity_steps=None, reapply_text=None, data_dir=DATA,
          siting=True, dialogue=True):
    R = Report()
    D = Design(doc)
    pack = Path(pack)
    if not (pack / "data" / NS / "function" / FOLDER / "build.mcfunction").exists():
        R.err("steps", "no build.mcfunction in %s: build the pack first" % pack)
        return R
    tags = jar.tags() if jar is not None else JAR_TAG_FALLBACK
    rep = Replay(pack, FOLDER + "/build", tags, ground=lambda x, z: int(g(x, z)))
    W = World(rep, g)
    check_pack(R, rep, steps)
    if not rep.state:
        return R
    if jar is not None:
        jar_rule(R, jar, D.colours)
    fruit_count, per_place = check_fruit(R, D, rep, W)
    terrace = check_terraces(R, D, W)
    floors = check_buildings(R, D, W)
    check_paths(R, D, W)
    check_blocks(R, D, rep, jar, jload(Path(data_dir) / "spawn_blocks.json")["blocks"],
                 jload(Path(data_dir) / "spawn_block_policy.json"))
    check_attached(R, W)
    if wet is not None:
        n = check_wet(R, rep, wet)
        R.note("wet: %d written columns checked dry" % n)
    else:
        R.note("wet: NOT checked (no water model given)")
    if siting:
        check_siting(R, D, rep, data_dir)
    reached = check_walk(R, D, W, fruit_count)
    fdir = pack / "data" / NS / "function" / FOLDER
    ml = (fdir / "merchant.mcfunction").read_text(encoding="utf-8").splitlines() if (fdir / "merchant.mcfunction").exists() else []
    dlx = (fdir / "merchant_done.mcfunction").read_text(encoding="utf-8").splitlines() if (fdir / "merchant_done.mcfunction").exists() else []
    merchant = check_merchant(R, D, ml, dlx, jar, entity_steps)
    farmer = check_dialogue(R, D, entity_steps, data_dir) if dialogue else None
    if farmer is None and entity_steps is None:
        x, z = D.W(*doc["npc"]["at"])
        farmer = (x, W.ground(x, z) + 1, z)
    check_spots(R, D, W, farmer, merchant, reached)
    check_light(R, D, W, floors, terrace)
    if reapply_text is not None:
        check_reapply(R, reapply_text)
    R.note("fruit: %s by place %s" % (dict(fruit_count), dict(per_place)))
    R.note("terraces: %s" % {c: (f["floor"], f.get("gate_outside_diff")) for c, f in terrace.items()})
    R.note("building floors: %s" % floors)
    R.note("cells written %d; walkable cells reached from the track %d" % (len(rep.state), len(reached)))
    economy(R, D, fruit_count, jar, data_dir)
    R.rep, R.world = rep, W
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--data", default=str(DOC))
    ap.add_argument("--source-root")
    ap.add_argument("--jar")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    import ground as G
    doc = jload(a.data)
    g = G.load(a.source_root)
    jar_path = find_jar(a.jar)
    jar = Jar(jar_path) if jar_path else None
    # the steps are the generator's OUTPUT, checked here; nothing in the audit's expectations comes from it
    import apricorn_farm
    steps = apricorn_farm.placement_steps(None, g)
    esteps = apricorn_farm.entity_steps(None, g)
    rtext = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    R = audit(doc, g, a.pack, wet=Wet(g, doc["site"]["centre"]), jar=jar, steps=steps, entity_steps=esteps,
              reapply_text=rtext)
    if a.verbose:
        for n in R.notes:
            print("note: %s" % n)
    for e in R.economy:
        print("ECONOMY %s" % e)
    real, hits, stale = classify(R.errors)
    for e in hits:
        print("KNOWN %s" % e)
    for e in real:
        print("PROBLEM %s" % e)
    for c, t, _w in stale:
        print("PROBLEM stale: the KNOWN fault '%s' no longer fires (fixed?): remove it from KNOWN" % t)
    if jar is None:
        print("NOT CHECKED the jar facts, the cobblemon block and item ids: no Cobblemon 1.8 jar found")
    bad = len(real) + len(stale)
    print("apricorn_farm_audit: %s, %d known defect(s)%s" % ("clean" if not bad else "%d problem(s)" % bad, len(hits),
                                                            " (jar checks NOT run)" if jar is None else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
