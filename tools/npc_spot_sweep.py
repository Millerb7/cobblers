#!/usr/bin/env python
"""Where every placed NPC, trainer and gym leader actually stands, read from the commands the apply runs.

The owner, 2026-10-04, flying staging: "the gym leader on a rock, the researcher in a wall, the mason on a roof, the
professor in a chimney -- those share a cause ... sweep every placed NPC and trainer for the same fault." This is
that sweep. It never reads a world (the ground rule): it replays, in tools/reapply.py's step order, every fill,
setblock and `place template` the built packs (build/datapacks) run, over a small box round each spot, on top of
the canonical heightmap (tools/ground.py, rounded), with each template read from its .nbt and turned exactly as
`/place template` turns it (mirror, then rotation about the command position). Then each spot is classified:

  indoors        floor under the feet, two cells of room, a written roof over it
  outside        on the ground, a street, a deck or a plaza, open above
  on_roof        standing on a written surface with a room under it and open sky over it
  pedestal       standing on a lone block one above the floor round it (a leader on its spawner)
  enclosed       feet and head in a 1x1 hollow: every neighbour solid (a chimney, a flue, a niche)
  in_block       feet or head inside a solid block
  no_floor       nothing under the feet

The spots: every `npc` and `trainer` item of tools/reapply.py's steps (the 165 the apply places by RCON) plus every
rctmod:trainer_spawner a replayed command leaves standing (the gym leaders, the Elite Four, the Champion and any
spawner a donor template carries): a spawner spawns its trainer at pos.above() (docs/research/notes/
hand-placed-structures.md section 6, RCT's TrainerSpawnerBlockEntity), so its trainer's feet are spawner + 1.

What it does NOT see: entities a template carries, blocks a function writes with relative coordinates (`~`, counted
and reported), trees and plants of the export (the heightmap is bare stone under air), anything a player built, and
-- the one that matters for "an NPC is not where its record says" -- NPCs an EARLIER apply left at a seat the data has
since moved: tools/reapply.py's npc step spawns at the current seat unless an NPC stands within 2 blocks of it and
never removes one from a superseded seat. A spot this sweep calls clean and a player sees wrong is either that, or a
world that is not the build (a step that did not run, a partial `--from`): both are read in the world, not here.

  python tools/npc_spot_sweep.py [--packs build/datapacks] [--out derived/npc_spot_sweep.json] [--only ID ...]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import nbt  # noqa: E402

# The ground rule (tools/ground_rule.py): nothing here reads a world.
WORLD_READS: set = set()

PACKS = ROOT / "build" / "datapacks"
OUT = ROOT / "derived" / "npc_spot_sweep.json"
SPAWNER = "rctmod:trainer_spawner"
BOX_XZ, BOX_DOWN, BOX_UP = 4, 12, 28

# blocks an NPC's feet or head may be in: no collision, or none that would hold a body
PASSABLE_EXACT = {"air", "cave_air", "void_air", "structure_void", "light", "water", "short_grass", "tall_grass", "fern",
                  "large_fern", "dead_bush", "snow", "vine", "glow_lichen", "torch", "wall_torch", "soul_torch",
                  "soul_wall_torch", "redstone_torch", "redstone_wall_torch", "rail", "powered_rail", "detector_rail",
                  "activator_rail", "redstone_wire", "tripwire", "tripwire_hook", "lever", "ladder", "cobweb",
                  "seagrass", "tall_seagrass", "kelp", "kelp_plant", "sugar_cane", "pink_petals", "leaf_litter", "bush",
                  "wheat", "carrots", "potatoes", "beetroots", "sweet_berry_bush", "hanging_roots", "spore_blossom",
                  "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet", "red_tulip", "orange_tulip",
                  "white_tulip", "pink_tulip", "oxeye_daisy", "cornflower", "lily_of_the_valley", "torchflower",
                  "sunflower", "lilac", "rose_bush", "peony", "nether_sprouts", "crimson_roots", "warped_roots",
                  "string", "fire", "soul_fire", "jigsaw_air"}
PASSABLE_SUFFIX = ("_carpet", "_sapling", "_button", "_pressure_plate", "_sign", "_banner", "_wall_banner", "_coral",
                   "_coral_fan", "_wall_fan", "_mushroom", "_candle", "candle", "_tulip", "_head", "_skull")


def short(state):
    s = state.split("[")[0].split("{")[0]
    return s.split(":", 1)[1] if s.startswith("minecraft:") else s


def passable(state):
    n = short(state)
    if ":" in n:                                    # a modded block: solid unless it says it is a plant
        return False
    return n in PASSABLE_EXACT or n.endswith(PASSABLE_SUFFIX)


def tokens(line):
    """Split a command on spaces outside brackets, braces and quotes."""
    out, cur, depth, q = [], [], 0, None
    for ch in line:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch in "[{(":
            depth += 1
        elif ch in "]})":
            depth -= 1
        if ch == " " and depth == 0:
            if cur:
                out.append("".join(cur))
                cur = []
            continue
        cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def transform(x, z, rot, mirror="none"):
    """StructureTemplate.transform with the pivot at the origin, as /place template uses it: mirror, then rotate."""
    if mirror == "left_right":
        z = -z
    elif mirror == "front_back":
        x = -x
    return {"none": (x, z), "clockwise_90": (-z, x), "180": (-x, -z), "counterclockwise_90": (z, -x)}[rot]


class Templates:
    """Structure templates by resource id: the built packs first (what the server loads from them), then the pack's
    own archives and the vanilla jar (tools/town_character.py's resolution)."""

    def __init__(self, packs):
        self.packs = Path(packs)
        self._cache = {}
        self._arch = None

    def get(self, tid):
        if tid in self._cache:
            return self._cache[tid]
        ns, path = tid.split(":", 1)
        doc = None
        for f in sorted(self.packs.glob("*/data/%s/structure/%s.nbt" % (ns, path))):
            doc = nbt.load(f)[1]
            break
        if doc is None:
            if self._arch is None:
                import town_character as TC
                self._arch = TC.Templates(TC.default_pack_dir(), TC.default_vanilla_jar())
            doc = self._arch.from_archives("data/%s/structure/%s.nbt" % (ns, path))[0]
        if doc is not None:
            pal = doc["palette"] if "palette" in doc else doc["palettes"][0]
            names = []
            for p in pal:
                props = p.get("Properties") or {}
                names.append(p["Name"] + ("[%s]" % ",".join("%s=%s" % kv for kv in sorted(props.items())) if props else ""))
            blocks = [(tuple(b["pos"]), names[b["state"]], b.get("nbt") or {}) for b in doc["blocks"]]
            doc = {"size": list(doc["size"]), "blocks": blocks,
                   "spawners": [b for b in blocks if b[1].startswith(SPAWNER)]}
        self._cache[tid] = doc
        return doc


class Function:
    """Every replayable line of a function and of the functions it calls, in run order."""

    def __init__(self, packs):
        self.packs = Path(packs)
        self.skipped = Counter()

    def path(self, fid):
        if not hasattr(self, "_index"):
            self._index = {}
            for f in sorted(self.packs.glob("*/data/*/function/**/*.mcfunction")):
                rel = f.relative_to(self.packs).parts
                key = "%s:%s" % (rel[2], "/".join(rel[4:])[:-len(".mcfunction")])
                self._index.setdefault(key, f)
        return self._index.get(fid)

    def lines(self, fid, depth=0, seen=None):
        f = self.path(fid)
        if f is None or depth > 12:
            self.skipped["missing function %s" % fid] += 1
            return
        for raw in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line[0] in "#$":
                continue
            if line.startswith("execute "):
                i = line.rfind(" run ")
                if i < 0:
                    continue
                line = line[i + 5:]
            head = line.split(" ", 1)[0]
            if head == "function":
                t = line.split()
                if len(t) == 2:
                    yield from self.lines(t[1], depth + 1, seen)
                else:
                    self.skipped["function with arguments"] += 1
            elif head == "schedule":
                # a scheduled function runs a moment later, inside the step's own wait (a donor places itself 20
                # ticks after its forceload): replayed in place, once per top-level call
                t = line.split()
                seen = set() if seen is None else seen
                if len(t) >= 3 and t[1] == "function" and t[2] not in seen:
                    seen.add(t[2])
                    yield from self.lines(t[2], depth + 1, seen)
            elif head in ("fill", "setblock", "place"):
                if "~" in line or "^" in line:
                    self.skipped["relative coordinates"] += 1
                    continue
                yield fid, line


class Model:
    """The cells inside the boxes of interest, as the replay leaves them; a cell nothing wrote is the heightmap's
    (stone at and under the ground, water up to the sea, air over it)."""

    def __init__(self, ground, boxes, sea=62):
        self.ground = ground
        self.sea = sea
        self.cells = {}                     # (x, y, z) -> (state, writer)
        self.boxes = boxes                  # [(x0, y0, z0, x1, y1, z1)]
        self.index = defaultdict(list)
        for i, b in enumerate(boxes):
            for cx in range(b[0] >> 4, (b[3] >> 4) + 1):
                for cz in range(b[2] >> 4, (b[5] >> 4) + 1):
                    self.index[(cx, cz)].append(i)
        self._g = {}

    def g(self, x, z):
        k = (x, z)
        if k not in self._g:
            self._g[k] = self.ground(x, z)
        return self._g[k]

    def natural(self, x, y, z):
        gy = self.g(x, z)
        if y <= gy:
            return "minecraft:stone"
        return "minecraft:water" if y <= self.sea else "minecraft:air"

    def at(self, x, y, z):
        c = self.cells.get((x, y, z))
        return c[0] if c else self.natural(x, y, z)

    def who(self, x, y, z):
        c = self.cells.get((x, y, z))
        return c[1] if c else "terrain"

    def hits(self, x0, y0, z0, x1, y1, z1):
        """The parts of the box inside each box of interest."""
        out, seen = [], set()
        for cx in range(x0 >> 4, (x1 >> 4) + 1):
            for cz in range(z0 >> 4, (z1 >> 4) + 1):
                for i in self.index.get((cx, cz), ()):
                    if i in seen:
                        continue
                    seen.add(i)
                    b = self.boxes[i]
                    lo = (max(x0, b[0]), max(y0, b[1]), max(z0, b[2]))
                    hi = (min(x1, b[3]), min(y1, b[4]), min(z1, b[5]))
                    if lo[0] <= hi[0] and lo[1] <= hi[1] and lo[2] <= hi[2]:
                        out.append((lo, hi))
        return out

    def matches(self, cur, filt):
        n = short(cur)
        if filt.startswith("#"):
            tag = filt.split("[")[0]
            if tag in ("#minecraft:replaceable", "#minecraft:air"):
                return passable(cur)
            return False                    # logs, leaves, flowers: the bare heightmap has none
        return n == short(filt)

    def write(self, x, y, z, state, writer, mode=None, filt=None):
        if mode == "keep" and not short(self.at(x, y, z)).endswith("air"):
            return
        if mode == "replace" and filt and not self.matches(self.at(x, y, z), filt):
            return
        self.cells[(x, y, z)] = (state, writer)


FILL = re.compile(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (.*)$")
SETBLOCK = re.compile(r"setblock (-?\d+) (-?\d+) (-?\d+) (.*)$")


def replay(model, fn, templates, steps, spawners=None):
    """Run every `fn` item of the steps in order into the model. With spawners (a dict) also record every trainer
    spawner any replayed command writes, wherever it is, with the function that wrote it."""
    def program():
        for sid, _desc, items in steps:
            for it in items:
                if it[0] == "fn":
                    for fid, line in fn.lines(it[1]):
                        yield "%s %s" % (sid, fid), line
    return replay_lines(model, program(), templates, fn.skipped, spawners)


def replay_lines(model, program, templates=None, skipped=None, spawners=None):
    """Apply (writer, command) pairs in order: fill (with keep, replace <filter>, hollow, outline), setblock, and
    `place template` turned as the command turns it. Anything else is not a block write and is passed over."""
    skipped = Counter() if skipped is None else skipped
    templates = templates or Templates(PACKS)
    n = 0
    for writer, line in program:
        line = line.strip()
        if line.startswith("execute ") and " run " in line:
            line = line[line.rfind(" run ") + 5:]
        if not line or line.split(" ", 1)[0] not in ("fill", "setblock", "place"):
            continue
        n += 1
        if line[0] == "f":
            mf = FILL.match(line)
            if not mf:
                skipped["unparsed line"] += 1
                continue
            a = [int(v) for v in mf.groups()[:6]]
            x0, x1 = sorted((a[0], a[3]))
            y0, y1 = sorted((a[1], a[4]))
            z0, z1 = sorted((a[2], a[5]))
            near = model.hits(x0, y0, z0, x1, y1, z1)
            if not near:
                continue
            t = ["fill"] + list(mf.groups()[:6]) + tokens(mf.group(7))
        elif line[0] == "s":
            ms = SETBLOCK.match(line)
            if not ms:
                skipped["unparsed line"] += 1
                continue
            x, y, z = (int(v) for v in ms.groups()[:3])
            if spawners is not None and SPAWNER in line:
                spawners[(x, y, z)] = (ms.group(4), writer)
            if not model.hits(x, y, z, x, y, z):
                continue
            t = ["setblock"] + list(ms.groups()[:3]) + tokens(ms.group(4))
        else:
            t = tokens(line)
        try:
            if t[0] == "fill" and len(t) >= 8:
                state, mode = t[7], (t[8] if len(t) > 8 else None)
                filt = t[9] if len(t) > 9 else None
                for lo, hi in near:
                    for x in range(lo[0], hi[0] + 1):
                        for y in range(lo[1], hi[1] + 1):
                            for z in range(lo[2], hi[2] + 1):
                                if mode in ("hollow", "outline") and not (x in (x0, x1) or y in (y0, y1) or z in (z0, z1)):
                                    if mode == "hollow":
                                        model.write(x, y, z, "minecraft:air", writer)
                                    continue
                                model.write(x, y, z, state, writer, mode, filt)
            elif t[0] == "setblock" and len(t) >= 5:
                x, y, z = (int(v) for v in t[1:4])
                model.write(x, y, z, t[4], writer, t[5] if len(t) > 5 else None)
            elif t[0] == "place" and len(t) >= 6 and t[1] == "template":
                tid = t[2]
                px, py, pz = (int(v) for v in t[3:6])
                rot = t[6] if len(t) > 6 else "none"
                mir = t[7] if len(t) > 7 else "none"
                doc = templates.get(tid)
                if doc is None:
                    skipped["template not found %s" % tid] += 1
                    continue
                sx, sy, sz = doc["size"]
                cs = [transform(cx, cz, rot, mir) for cx in (0, sx - 1) for cz in (0, sz - 1)]
                bx0, bz0 = px + min(c[0] for c in cs), pz + min(c[1] for c in cs)
                bx1, bz1 = px + max(c[0] for c in cs), pz + max(c[1] for c in cs)
                near = model.hits(bx0, py, bz0, bx1, py + sy - 1, bz1)
                tw = "%s template %s" % (writer, tid)
                if spawners is not None:
                    for (bx, by, bz), state, tag in doc["spawners"]:
                        dx, dz = transform(bx, bz, rot, mir)
                        spawners[(px + dx, py + by, pz + dz)] = (state + json.dumps(tag.get("TrainerIds") or []), tw)
                if not near:
                    continue
                for (bx, by, bz), state, tag in doc["blocks"]:
                    if state.startswith("minecraft:structure_void"):
                        continue
                    dx, dz = transform(bx, bz, rot, mir)
                    wx, wy, wz = px + dx, py + by, pz + dz
                    if any(lo[0] <= wx <= hi[0] and lo[1] <= wy <= hi[1] and lo[2] <= wz <= hi[2] for lo, hi in near):
                        model.write(wx, wy, wz, state, tw)
        except (ValueError, IndexError, KeyError):
            skipped["unparsed line"] += 1
    return n


# --------------------------------------------------------------------------------------------- classification
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))


def solid(state):
    return not passable(state)


def spawner_stand(pos):
    """Where a trainer spawner's trainer stands: RCT spawns it at pos.above() (TrainerSpawnerBlockEntity ->
    TrainerSpawner.attemptSpawnFor(player, id, pos.above(), ...), docs/research/notes/hand-placed-structures.md 6)."""
    return (pos[0], pos[1] + 1, pos[2])


def spawner_problem(at, pos):
    """None when a trainer spawner at `pos` is set INTO its floor, as every Cobbleverse gym template and the League set
    theirs (cobbleverse:brock: redstone [6,0,12] under the floor layer, the spawner [6,1,12] in it, smooth stone either
    side); else why not. `at(x, y, z)` -> block state, from the generator's own model of what it built.

    A spawner standing ON the floor is a one-block plinth: its trainer, spawned at pos.above(), stands one above the
    floor round it -- "the gym leader on a rock" (the owner, 2026-10-04). All seven authored gym halls did this: their
    records set the redstone INTO the floor and the spawner on top, reading the donor's layer 0 as its floor."""
    x, y, z = pos
    out = []
    open_sides = [(dx, dz) for dx, dz in SIDES if passable(at(x + dx, y, z + dz))]
    if open_sides:
        out.append("the spawner at %s stands proud of its floor (open on %d side(s): %s), so its trainer, spawned at "
                   "%s, stands on it one above the floor: set the spawner INTO the floor and its power under it"
                   % (list(pos), len(open_sides), ", ".join("%+d,%+d" % s for s in open_sides), list(spawner_stand(pos))))
    sx, sy, sz = spawner_stand(pos)
    for dy in (0, 1):
        if solid(at(sx, sy + dy, sz)):
            out.append("no room for the trainer over the spawner at %s: %s" % ([sx, sy + dy, sz], at(sx, sy + dy, sz)))
    return "; ".join(out) or None


def classify(m, x, y, z):
    """(class, detail) for an NPC whose feet are in cell (x, y, z)."""
    feet, head, below = m.at(x, y, z), m.at(x, y + 1, z), m.at(x, y - 1, z)
    if solid(feet) or solid(head):
        return "in_block", "feet %s, head %s" % (short(feet), short(head))
    if passable(below) and short(below) != "water":
        return "no_floor", "under the feet: %s" % short(below)
    who = getattr(m, "who", lambda *_a: "written")
    walls = sum(1 for dx, dz in SIDES if solid(m.at(x + dx, y, z + dz)) and solid(m.at(x + dx, y + 1, z + dz)))
    if walls == 4:
        return "enclosed", "every neighbour solid at feet and head"
    # a lone block under the feet: the floor round it is a block lower (a leader on a spawner set on the floor)
    lower = sum(1 for dx, dz in SIDES if passable(m.at(x + dx, y - 1, z + dz)) and solid(m.at(x + dx, y - 2, z + dz)))
    if lower >= 3 and solid(below):
        return "pedestal", "standing on %s, one above the floor round it" % short(below)
    roofed = None
    for dy in range(2, BOX_UP):
        s = m.at(x, y + dy, z)
        if solid(s) and who(x, y + dy, z) != "terrain":
            roofed = y + dy
            break
    # a room under the surface stood on: two or more cells of air, then something solid that is not the sea (a pier's
    # deck has air and then water under it, and is not a roof)
    room_under = False
    if who(x, y - 1, z) != "terrain":
        gap = 0
        for dy in range(2, BOX_DOWN):
            s = m.at(x, y - dy, z)
            if passable(s) and short(s) != "water":
                gap += 1
            else:
                # a written floor at the bottom: a deck over a gully has the bare ground under it, not a room
                room_under = gap >= 2 and short(s) != "water" and who(x, y - dy, z) != "terrain"
                break
    if roofed is None and room_under:
        return "on_roof", "on %s (%s) with a room under it and open sky over it" % (short(below), who(x, y - 1, z))
    if roofed is not None:
        return "indoors", "floor %s, roof at y%d (%s)" % (short(below), roofed, who(x, roofed, z))
    return "outside", "on %s (%s)" % (short(below), who(x, y - 1, z))


def spots_from_steps(steps):
    out = []
    for sid, _d, items in steps:
        for it in items:
            if it[0] == "npc":
                v = it[1]
                out.append({"id": v[0], "kind": "npc", "step": sid, "at": [int(c) for c in v[1]], "class_id": v[2]})
            elif it[0] == "trainer":
                v = it[1]
                out.append({"id": v[0], "kind": "trainer", "step": sid, "at": [int(c) for c in v[1]]})
    return out


def load_steps(packs):
    import reapply
    if Path(packs).resolve() != reapply.PACKS.resolve():
        reapply.PACKS = Path(packs)
        reapply.BUILD = reapply.PACKS.parent
        reapply.REAPPLY = reapply.PACKS / "cobblers_reapply"
    out = []
    for sid, desc, items in reapply.steps():
        out.append((sid, desc, [list(i) for i in items]))
    return out


def sweep(packs=PACKS, only=None, ground=None):
    import ground as G
    steps = load_steps(packs)
    spots = spots_from_steps(steps)
    ground = ground or G.load()
    templates = Templates(packs)
    fn = Function(packs)
    # pass 1: every spawner the apply leaves standing, wherever it is
    spawners = {}
    probe = Model(ground, [])
    replay(probe, fn, templates, steps, spawners)
    boxes = [(s["at"][0] - BOX_XZ, s["at"][1] - BOX_DOWN, s["at"][2] - BOX_XZ,
              s["at"][0] + BOX_XZ, s["at"][1] + BOX_UP, s["at"][2] + BOX_XZ) for s in spots]
    sp_spots = []
    for (x, y, z), (state, writer) in sorted(spawners.items()):
        ids = re.findall(r'"([a-z0-9_:]+)"', state)
        sp_spots.append({"id": "spawner %s" % (",".join(ids) or "?"), "kind": "spawner", "step": writer.split(" ")[0],
                         "spawner": [x, y, z], "at": [x, y + 1, z], "writer": writer})
        boxes.append((x - BOX_XZ, y + 1 - BOX_DOWN, z - BOX_XZ, x + BOX_XZ, y + 1 + BOX_UP, z + BOX_XZ))
    spots += sp_spots
    if only:
        keep = [i for i, s in enumerate(spots) if s["id"] in only]
        spots = [spots[i] for i in keep]
        boxes = [boxes[i] for i in keep]
    m = Model(ground, boxes)
    fn.skipped.clear()
    n = replay(m, fn, templates, steps)
    for s in spots:
        x, y, z = s["at"]
        if s["kind"] == "spawner" and not m.at(*s["spawner"]).startswith(SPAWNER):
            s["class"], s["detail"] = "gone", "a later command replaced the spawner with %s (%s)" % (
                m.at(*s["spawner"]), m.who(*s["spawner"]))
            continue
        s["class"], s["detail"] = classify(m, x, y, z)
        if s["kind"] == "spawner":
            why = spawner_problem(m.at, tuple(s["spawner"]))
            if why:
                s["class"], s["detail"] = "pedestal", why
        s["floor_by"] = m.who(x, y - 1, z)
        s["column"] = {str(y + dy): short(m.at(x, y + dy, z)) for dy in range(-2, 4)}
    return {"lines_replayed": n, "skipped": dict(fn.skipped), "spots": spots,
            "counts": dict(Counter(s["class"] for s in spots))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--packs", default=str(PACKS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    res = sweep(Path(a.packs), a.only)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    bad = [s for s in res["spots"] if s["class"] not in ("indoors", "outside", "gone")]
    print("replayed %d lines; spots %d: %s" % (res["lines_replayed"], len(res["spots"]),
                                              ", ".join("%s %d" % kv for kv in sorted(res["counts"].items()))))
    for s in bad:
        print("  %-9s %-48s %-18s %s" % (s["class"], s["id"][:48], s["at"], s["detail"][:110]))
    print("skipped: %s" % ", ".join("%s %d" % kv for kv in sorted(res["skipped"].items())[:12]))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
