#!/usr/bin/env python
"""Independent audit of the Scorchbone Dig's BUILT pack (build/datapacks/cobblers_fossil_dig).

Written by an agent that built none of the place (CLAUDE.md principle 16). It never imports tools/fossil_dig.py:
it replays the emitted mcfunctions into a voxel model over the canonical heightmap (tools/ground.py, rounded) and
derives every expectation from data/fossil_dig.json's offsets, the heightmap, other files' data and the Cobblemon jar:

  palette     every block the build and the restore write is in blocks.ids, none is a spawn condition
              (data/spawn_blocks.json, unless data/spawn_block_policy.json scopes one to fossil_dig), and nothing
              is light, water, lava, a bubble column, a chest, a bed or waterlogged
  footprint   every write lies in the build's own clearing box, which lies in its force-loaded chunks, and inside
              the extent of the record's own features (pit + skin, tents, posts, camp, signs, foreman)
  pit         floors recomputed from the heightmap: upper = lowest rounded ground under the upper rect minus
              depth_below_lowest_ground, each inner one `step` lower; every pit column is solid at its floor and
              cut (written, never left as ground) from floor + 1 to its own ground
  walk        an independent walk (2-high passable, a standable block under each step, |dy| <= 1, 3-high to jump):
              every pit floor cell, every seam's brushing cell and the foreman's seat in one component with the
              ground round the clearing box
  gravity     in each column no air write follows a lower one; no gravity block written over air or another
              gravity block; each seam's support solid and not a gravity block
  seams       exactly one suspicious_gravel per face cell, at (centre + cell, inner floor + 1), open on its pit
              side, the outer floor over it; its LootTable a cobblemon:fossils/rare/* table in the jar that is
              archaeology, one pool, one entry, one item of #cobblemon:fossils; the restore's tables cover all 15
  restore     restore_<face> holds only `fill ... replace #<tag>` over cells of the face (seams, the cell under and
              behind each, the riser between) with the band the build wrote there; the tag is air/cave_air/gravel
              only; seam_<face>_<k> returns unless the seam is in the tag before any setblock, and sets only it;
              check_<face> tests the period, four loaded corners at its guard box's corners, @a and
              @e[type=cobblemon:pokemon] in a guard box that holds the face grown by 1, before it calls restore;
              the period is at least MIN_PERIOD; restore is called only from its check, check only from site,
              site only from drive, which returns unless #built
  support     every lantern on a post or under a block; every wall sign on its block; nothing floating
              (18-connected to the ground)
  siting      every column of the clearing box: >= clear_of_path_blocks from every route path point and segment;
              >= southern_residents rules.authored_clearance from every x/z (or filled box) another data/*.json
              authors; outside the keep-out box, every town footprint + that clearance, every Rift zone box and
              the Mega field polygon; beyond every activated Habitat Block's spawn_range, every resident's leash
              and every Mega den's leash
  foreman     data/npc_seats.json npc_fossil_dig_foreman stands on the heightmap ground + 1 with feet and head
              clear in the build, is reached by the walk, and its conversation and cursor agree

Not covered (needs a running server): that the LootTable NBT survives setblock and brushes out a fossil, that the
restore fires on approach, that the foreman appears, what the mesa's surface blocks really are, that red sand in the
real ground does not fall (the ground's material is not in the heightmap).

  python tools/fossil_dig_audit.py [--pack DIR] [--jar-dir DIR] [--source-root R] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import zipfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_fossil_dig"
LOCAL_JARS = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods")
FN = "data/cobblers/function/fossil_dig/"
FNREF = "cobblers:fossil_dig/"

# the brief (the orchestrator, 2026-10-05): a face is restored at most once every 24,000 ticks (one Minecraft day)
MIN_PERIOD = 24000

AIRS = {"minecraft:air", "minecraft:cave_air"}
# a player's feet and head pass through these
PASS = AIRS | {"minecraft:spruce_sign", "minecraft:spruce_wall_sign"}
# these block a player and cannot be stood on (a fence is 1.5 high, a lantern and a skull are small)
NOSTAND = {"minecraft:spruce_fence", "minecraft:lantern", "minecraft:skeleton_skull"}
HUNG = {"minecraft:lantern", "minecraft:spruce_sign", "minecraft:spruce_wall_sign"}
GRAVITY_EXACT = {"minecraft:gravel", "minecraft:suspicious_gravel", "minecraft:sand", "minecraft:red_sand",
                 "minecraft:suspicious_sand", "minecraft:anvil", "minecraft:chipped_anvil", "minecraft:damaged_anvil",
                 "minecraft:dragon_egg", "minecraft:pointed_dripstone"}
FORBIDDEN = {"minecraft:light", "minecraft:water", "minecraft:lava", "minecraft:bubble_column", "minecraft:chest",
             "minecraft:trapped_chest", "minecraft:water_cauldron", "minecraft:lava_cauldron"}
SIDES = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
GROUND = "<ground>"


def is_gravity(name):
    return name in GRAVITY_EXACT or name.endswith("_concrete_powder")


def name_of(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def jload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ command parsing
def _token(s, i):
    """One whitespace-delimited token from s[i:], brackets, braces and quotes kept whole."""
    depth, q, j = 0, None, i
    while j < len(s):
        c = s[j]
        if q:
            if c == "\\":
                j += 2
                continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        elif c == " " and depth == 0:
            break
        j += 1
    return s[i:j], j + 1


def parse(line):
    """('fill'|'setblock', (x0,y0,z0,x1,y1,z1), state, filter or None) or None for any other command."""
    s = line.strip()
    m = re.match(r"^(fill|setblock) ", s)
    if not m:
        return None
    nums = 6 if m.group(1) == "fill" else 3
    parts = s.split(" ", nums + 1)
    if len(parts) < nums + 2:
        return None
    try:
        c = [int(v) for v in parts[1:nums + 1]]
    except ValueError:
        return None
    rest = parts[nums + 1]
    state, k = _token(rest, 0)
    tail = rest[k:].strip() if k <= len(rest) else ""
    filt = None
    if tail.startswith("replace"):
        filt = tail[len("replace"):].strip() or None
    if nums == 3:
        c = c + c
    box = (min(c[0], c[3]), min(c[1], c[4]), min(c[2], c[5]), max(c[0], c[3]), max(c[1], c[4]), max(c[2], c[5]))
    return m.group(1), box, state, filt


def cells(box):
    x0, y0, z0, x1, y1, z1 = box
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                yield (x, y, z)


def selector_box(sel):
    """The block box [x..x+dx] etc. of an @a[...]/@e[...] volume, or None."""
    kv = dict(re.findall(r"(\w+)=([^,\]]+)", sel))
    try:
        x, y, z = int(kv["x"]), int(kv["y"]), int(kv["z"])
        dx, dy, dz = int(kv["dx"]), int(kv["dy"]), int(kv["dz"])
    except (KeyError, ValueError):
        return None
    return (x, y, z, x + dx, y + dy, z + dz)


def contains(outer, inner):
    return all(outer[i] <= inner[i] for i in range(3)) and all(outer[i] >= inner[i] for i in range(3, 6))


def grow(b, n):
    return (b[0] - n, b[1] - n, b[2] - n, b[3] + n, b[4] + n, b[5] + n)


def bbox(cs):
    xs, ys, zs = zip(*cs)
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def lines_of(text):
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]


# ------------------------------------------------------------------------------------------------ the jar
def find_jar(jar_dir):
    if not jar_dir:
        return None
    d = Path(jar_dir)
    if not d.is_dir():
        return None
    js = sorted(d.glob("Cobblemon-fabric-1.8.*.jar"))
    return js[0] if js else None


class Jar:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.names = set(self.z.namelist())
        self.fossils = set(json.loads(self.z.read("data/cobblemon/tags/item/fossils.json"))["values"])

    def rare_table(self, ref):
        """(item, None) when `ref` is a cobblemon:fossils/rare/* archaeology table of one fossil, else (None, why)."""
        if ":" not in ref:
            return None, "%s has no namespace" % ref
        ns, path = ref.split(":", 1)
        if ns != "cobblemon" or not path.startswith("fossils/rare/"):
            return None, "%s is not a cobblemon:fossils/rare/* table" % ref
        entry = "data/%s/loot_table/%s.json" % (ns, path)
        if entry not in self.names:
            return None, "%s is not in the jar (%s)" % (ref, entry)
        t = json.loads(self.z.read(entry))
        if t.get("type") != "minecraft:archaeology":
            return None, "%s is type %s, not minecraft:archaeology" % (ref, t.get("type"))
        pools = t.get("pools") or []
        if len(pools) != 1 or len(pools[0].get("entries") or []) != 1:
            return None, "%s is not one pool of one entry" % ref
        e = pools[0]["entries"][0]
        if e.get("type") != "minecraft:item" or e.get("name") not in self.fossils:
            return None, "%s's entry %s is not a #cobblemon:fossils item" % (ref, e.get("name"))
        return e["name"], None


# ------------------------------------------------------------------------------------------------ the model
class World:
    """The build replayed over the heightmap: a written cell holds its state, an unwritten one is ground at or under
    the rounded heightmap and air above it."""

    def __init__(self, ground):
        self.g = ground
        self.cache = {}
        self.w = {}

    def gy(self, x, z):
        k = (x, z)
        if k not in self.cache:
            self.cache[k] = int(self.g(x, z))
        return self.cache[k]

    def at(self, c):
        s = self.w.get(c)
        if s is not None:
            return s
        return GROUND if c[1] <= self.gy(c[0], c[2]) else "minecraft:air"

    def name(self, c):
        s = self.at(c)
        return s if s == GROUND else name_of(s)


class Report:
    def __init__(self):
        self.problems = []
        self.checks = {}
        self.facts = {}

    def check(self, kind, ok, msg):
        self.checks[kind] = self.checks.get(kind, 0) + 1
        if not ok:
            self.problems.append((kind, msg))
        return ok

    def kinds(self):
        return {k for k, _m in self.problems}


# ------------------------------------------------------------------------------------------------ the audit
def audit(files, ground, doc=None, data_dir=DATA, jar=None):
    """`files`: {relative path: text} of the pack. `ground`: (x, z) -> rounded ground y. `jar`: a Jar or None (the
    loot checks then report NOT_EXECUTED as a problem: a seam's table unverified is not a pass)."""
    data_dir = Path(data_dir)
    doc = doc or jload(data_dir / "fossil_dig.json")
    R = Report()
    fnames = {k[len(FN):-len(".mcfunction")]: v for k, v in files.items()
              if k.startswith(FN) and k.endswith(".mcfunction")}
    if not R.check("pack", "build" in fnames, "no build function in the pack"):
        return R
    W = World(ground)
    cx, cz = doc["site"]["centre"]

    # ---- replay the build
    order = []                      # (index, kind, box, state)
    clear_boxes, forceloads, forceremoves = [], [], []
    build_lines = lines_of(fnames["build"])
    last_write = -1
    built_at = None
    for i, ln in enumerate(build_lines):
        fl = re.match(r"^forceload (add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)$", ln)
        if fl:
            b = tuple(int(v) for v in fl.groups()[1:])
            (forceloads if fl.group(1) == "add" else forceremoves).append(b)
            continue
        if ln == "scoreboard players set #built fd.t 1":
            built_at = i
        p = parse(ln)
        if p is None:
            continue
        kind, box, state, filt = p
        last_write = i
        if kind == "fill" and filt is not None:
            # the clearing: plants and trees to air. The heightmap model holds none, so it changes nothing here
            clear_boxes.append(box)
            continue
        order.append((i, kind, box, state))
    gravity_events = {}
    for i, kind, box, state in order:
        nm = name_of(state)
        for c in cells(box):
            if nm in AIRS:
                col = (c[0], c[2])
                lo = gravity_events.get(col)
                if lo is not None and c[1] > lo:
                    R.check("gravity", False, "air written at %s after a lower air write at y%d in its column" % (c, lo))
            elif is_gravity(nm):
                below = (c[0], c[1] - 1, c[2])
                bn = W.name(below)
                if bn in AIRS or (bn != GROUND and is_gravity(bn)):
                    R.check("gravity", False, "%s written at %s over %s" % (nm, c, bn))
        if nm in AIRS:
            for c in cells(box):
                col = (c[0], c[2])
                gravity_events[col] = min(gravity_events.get(col, c[1]), box[1])
        for c in cells(box):
            W.w[c] = state
    R.check("gravity", True, "")
    written = {c for c in W.w}
    nonair = {c: s for c, s in W.w.items() if name_of(s) not in AIRS}
    R.facts["writes"] = len(written)
    R.check("pack", bool(nonair), "the build writes no block")
    if not nonair:
        return R

    # ---- palette (build + every restore/seam function)
    ids = set(doc["blocks"]["ids"])
    spawn = set(jload(data_dir / "spawn_blocks.json")["blocks"])
    pol = jload(data_dir / "spawn_block_policy.json")
    allowed_spawn = {b for e in pol.get("whitelist") or [] if "fossil_dig" in json.dumps(e.get("scope", ""))
                     for b in e.get("blocks") or []}
    states = [s for _i, _k, _b, s in order]
    for fname, text in fnames.items():
        if fname == "build":
            continue
        for ln in lines_of(text):
            p = parse(ln.split(" run ", 1)[1] if ln.startswith("execute ") and " run " in ln else ln)
            if p:
                states.append(p[2])
    alltext = "\n".join(files.values())
    for st in sorted(set(states)):
        nm = name_of(st)
        R.check("palette", nm in ids, "%s is not in blocks.ids" % nm)
        R.check("palette", nm not in spawn or nm in allowed_spawn, "%s is a spawn condition (data/spawn_blocks.json)" % nm)
        R.check("palette", nm not in FORBIDDEN and not nm.endswith("_bed"), "%s is forbidden here" % nm)
        R.check("palette", "waterlogged=true" not in st, "%s is waterlogged" % st)
    for bad in ("minecraft:light", "minecraft:water", "minecraft:bubble_column", "minecraft:lava"):
        R.check("palette", not re.search(re.escape(bad) + r"(?![_a-z])", alltext), "the pack names %s" % bad)

    # ---- footprint
    R.check("footprint", len(clear_boxes) >= 1, "the build declares no clearing box")
    if clear_boxes:
        cb = clear_boxes[0]
        R.check("footprint", all(b[0] == cb[0] and b[2] == cb[2] and b[3] == cb[3] and b[5] == cb[5]
                                 for b in clear_boxes), "the clearing fills do not share one box")
        out = [c for c in written if not (cb[0] <= c[0] <= cb[3] and cb[2] <= c[2] <= cb[5])]
        R.check("footprint", not out, "%d writes outside the clearing box %s, e.g. %s" % (len(out), cb, out[:3]))
    else:
        cb = bbox(written)
    R.facts["clear_box"] = cb
    chunks = set()
    for x0, z0, x1, z1 in forceloads:
        for a in range(x0 >> 4, (x1 >> 4) + 1):
            for b in range(z0 >> 4, (z1 >> 4) + 1):
                chunks.add((a, b))
    unl = [c for c in written if (c[0] >> 4, c[2] >> 4) not in chunks]
    R.check("footprint", bool(forceloads) and not unl, "%d writes in chunks the build does not force-load" % len(unl))
    R.check("footprint", sorted(forceloads) == sorted(forceremoves), "forceload add and remove disagree")
    # the record's own features, with the margins the record itself names
    pit = {l["id"]: l for l in doc["pit"]["levels"]}
    lvl_order = [l["id"] for l in doc["pit"]["levels"]]
    ux0, uz0, ux1, uz1 = pit[lvl_order[0]]["rect"]
    sk = doc["pit"]["outer_skin_depth"]
    feats = [(ux0 - sk, uz0 - sk), (ux1 + sk, uz1 + sk)]
    camp = doc["camp"]
    for t in camp["tents"]:
        feats += [tuple(t["rect"][:2]), tuple(t["rect"][2:])]
    feats += [tuple(p["at"]) for p in doc["lanterns"]["posts"]]
    feats += [tuple(v) for k in ("sieves", "spoil", "sorting_table") for v in camp[k]]
    feats += [tuple(camp["tub"]), tuple(camp["entrance_sign"]), tuple(doc["npc"]["at_local"])]
    fb = camp["finds_board"]
    feats += [(fb["x"], fb["lz"][0]), (fb["x"] + 1, fb["lz"][1])]   # the board and the signs on its face
    fx0, fz0 = cx + min(a for a, _b in feats), cz + min(b for _a, b in feats)
    fx1, fz1 = cx + max(a for a, _b in feats), cz + max(b for _a, b in feats)
    stray = [c for c in written if not (fx0 <= c[0] <= fx1 and fz0 <= c[2] <= fz1)]
    R.check("footprint", not stray, "%d writes outside the record's features (%d..%d, %d..%d), e.g. %s"
            % (len(stray), fx0, fx1, fz0, fz1, stray[:3]))
    R.check("footprint", cb[0] <= fx0 and cb[2] <= fz0 and cb[3] >= fx1 and cb[5] >= fz1,
            "the clearing box %s does not cover the record's features" % (cb,))

    # ---- pit: floors from the heightmap
    rects = {k: pit[k]["rect"] for k in lvl_order}
    low = min(W.gy(cx + a, cz + b) for a in range(ux0, ux1 + 1) for b in range(uz0, uz1 + 1))
    floors = {lvl_order[0]: low - pit[lvl_order[0]]["depth_below_lowest_ground"]}
    for a, b in zip(lvl_order, lvl_order[1:]):
        floors[b] = floors[a] - pit[b]["step"]
    R.facts["floors"] = floors

    def inside(rect, lx, lz):
        return rect[0] <= lx <= rect[2] and rect[1] <= lz <= rect[3]

    def level_of(lx, lz):
        out = None
        for k in lvl_order:
            if inside(rects[k], lx, lz):
                out = k
        return out

    floor_feet = []
    standing_ok = {"minecraft:spruce_stairs", "minecraft:bone_block", "minecraft:spruce_fence", "minecraft:lantern"}
    for a in range(ux0, ux1 + 1):
        for b in range(uz0, uz1 + 1):
            k = level_of(a, b)
            x, z = cx + a, cz + b
            F = floors[k]
            fn_ = W.name((x, F, z))
            if not R.check("pit", fn_ not in AIRS and fn_ not in PASS,
                           "(%d, %d, %d): the %s floor is %s" % (x, F, z, k, fn_)):
                continue
            for y in range(F + 1, max(W.gy(x, z), F) + 1):
                nm = W.name((x, y, z))
                if nm == GROUND:
                    R.check("pit", False, "(%d, %d, %d) is uncut ground over the %s floor y%d" % (x, y, z, k, F))
                    break
                if nm not in AIRS and nm not in standing_ok:
                    above = W.name((x, y + 1, z))
                    if not (above == "minecraft:spruce_stairs" or W.name((x, y + 2, z)) == "minecraft:spruce_stairs"):
                        R.check("pit", False, "(%d, %d, %d): %s stands in the %s cut" % (x, y, z, nm, k))
                        break
            R.check("pit", True, "")
            floor_feet.append((x, F + 1, z))

    # ---- seams, from the record's faces and the floors above
    jar_ok = jar is not None
    R.check("loot", jar_ok, "NOT_EXECUTED: no Cobblemon 1.8 jar (set COBBLERS_JAR_DIR); seam tables unverified")
    face_cells, seams_expected = {}, {}
    for f in doc["faces"]:
        L = f["level"]
        outer = lvl_order[lvl_order.index(L) - 1]
        dx, dz = SIDES[f["side"]]
        y = floors[L] + 1
        seams, support, backing = [], [], []
        for a, b in f["cells"]:
            R.check("seams", level_of(a, b) == outer and level_of(a - dx, b - dz) == L,
                    "face %s cell (%d, %d) is not an %s cell with %s on its pit side" % (f["id"], a, b, outer, L))
            s = (cx + a, y, cz + b)
            seams.append(s)
            support.append((s[0], y - 1, s[2]))
            backing.append((s[0] + dx, y, s[2] + dz))
        xs = sorted({s[0] for s in seams})
        zs = sorted({s[2] for s in seams})
        if dx == 0:
            between = [(x, y, zs[0]) for x in range(xs[0], xs[-1] + 1)]
        else:
            between = [(xs[0], y, z) for z in range(zs[0], zs[-1] + 1)]
        between = [c for c in between if c not in seams]
        face_cells[f["id"]] = set(seams) | set(support) | set(backing) | set(between)
        seams_expected[f["id"]] = seams
        for s in seams:
            seams_expected.setdefault("_all", []).append(s)
            st = W.at(s)
            R.check("seams", name_of(st) == doc["fossils"]["seam_block"] == "minecraft:suspicious_gravel",
                    "face %s: %s is %s, not suspicious_gravel" % (f["id"], s, st))
            m = re.search(r'LootTable:"([^"]+)"', st if st != GROUND else "")
            R.check("seams", m is not None, "face %s: the seam at %s has no LootTable" % (f["id"], s))
            if m and jar_ok:
                item, why = jar.rare_table(m.group(1))
                R.check("loot", item is not None, "face %s: seam %s: %s" % (f["id"], s, why))
            pit_side = (s[0] - dx, s[1], s[2] - dz)
            R.check("seams", W.name(pit_side) in AIRS, "face %s: the seam %s is not open on its pit side %s (%s)"
                    % (f["id"], s, pit_side, W.name(pit_side)))
            over = (s[0], s[1] + 1, s[2])
            R.check("seams", s[1] + 1 == floors[outer] and W.name(over) not in AIRS and not is_gravity(W.name(over)),
                    "face %s: no %s floor over the seam %s (%s)" % (f["id"], outer, s, W.name(over)))
            under = (s[0], s[1] - 1, s[2])
            R.check("gravity", W.name(under) not in AIRS and W.name(under) not in PASS and W.name(under) != GROUND
                    and not is_gravity(W.name(under)),
                    "face %s: the seam %s stands on %s" % (f["id"], s, W.name(under)))
            behind = (s[0] + dx, s[1], s[2] + dz)
            R.check("seams", W.name(behind) not in AIRS and not is_gravity(W.name(behind)),
                    "face %s: the seam %s has %s behind it" % (f["id"], s, W.name(behind)))
    allseams = set(seams_expected.pop("_all", []))
    sg = {c for c, s in W.w.items() if name_of(s) == "minecraft:suspicious_gravel"}
    R.check("seams", sg == allseams and len(allseams) == sum(len(f["cells"]) for f in doc["faces"]),
            "suspicious gravel at %d cells, %d seams expected; extra %s missing %s"
            % (len(sg), len(allseams), sorted(sg - allseams)[:3], sorted(allseams - sg)[:3]))
    R.facts["seams"] = len(allseams)

    # ---- restore
    tags = {"#cobblers:" + k[len("data/cobblers/tags/block/"):-5]: jload_text(v)
            for k, v in files.items() if k.startswith("data/cobblers/tags/block/") and k.endswith(".json")}
    for t, v in tags.items():
        vals = set(v.get("values") or [])
        R.check("restore", vals and vals <= {"minecraft:air", "minecraft:cave_air", "minecraft:gravel"},
                "the rearm tag %s holds %s (only air, cave_air and gravel may be overwritten)" % (t, sorted(vals)))
    calls = {}
    for fname, text in fnames.items():
        for ln in lines_of(text):
            for m in re.finditer(r"function (\S+)", ln):
                calls.setdefault(m.group(1), set()).add(fname)
    load_ = lines_of(fnames.get("load", ""))
    per = [int(m.group(1)) for ln in load_ for m in [re.match(r"^scoreboard players set #period fd\.t (\d+)$", ln)] if m]
    R.check("restore", len(per) == 1 and per[0] >= MIN_PERIOD,
            "the restore period is %s ticks (at least %d: at most once a Minecraft day)" % (per, MIN_PERIOD))
    period = per[0] if per else 0
    fossil_items = set()
    for f in doc["faces"]:
        fid = f["id"]
        expect = face_cells[fid]
        guard = grow(bbox(expect), 1)
        rname, cname = "faces/restore_" + fid, "faces/check_" + fid
        R.check("restore", rname in fnames and cname in fnames, "face %s has no restore/check function" % fid)
        if rname not in fnames or cname not in fnames:
            continue
        R.check("restore", calls.get(FNREF + rname, set()) == {cname},
                "%s is called from %s, not only from %s" % (rname, sorted(calls.get(FNREF + rname, ())), cname))
        R.check("restore", calls.get(FNREF + cname, set()) == {"site"},
                "%s is called from %s, not only from site" % (cname, sorted(calls.get(FNREF + cname, ()))))
        # check_<face>
        cl = lines_of(fnames[cname])
        callix = next((i for i, ln in enumerate(cl) if ln == "function %s%s" % (FNREF, rname)), None)
        R.check("restore", callix is not None and callix == len(cl) - 1,
                "%s does not end by calling %s" % (cname, rname))
        pre = cl[:callix] if callix is not None else cl
        R.check("restore", "scoreboard players operation #d fd.t = #now fd.t" in pre
                and "scoreboard players operation #d fd.t -= #%s fd.last" % fid in pre
                and "execute if score #d fd.t < #period fd.t run return 0" in pre,
                "%s does not return before its period has passed" % cname)
        corners = [tuple(int(v) for v in m.groups()) for ln in pre
                   for m in [re.match(r"^execute unless loaded (-?\d+) (-?\d+) (-?\d+) run return 0$", ln)] if m]
        want = {(guard[0], guard[2]), (guard[3], guard[2]), (guard[0], guard[5]), (guard[3], guard[5])}
        R.check("restore", {(a, c) for a, _b, c in corners} == want,
                "%s's loaded corners %s are not its guard box's corners %s" % (cname, corners, sorted(want)))
        span = {(x >> 4, z >> 4) for x in range(guard[0], guard[3] + 1) for z in range(guard[2], guard[5] + 1)}
        R.check("restore", span <= {(a >> 4, c >> 4) for a, _b, c in corners},
                "%s's corners do not cover every chunk its box spans" % cname)
        pl_ = [selector_box(m.group(1)) for ln in pre
               for m in [re.match(r"^execute if entity @a\[([^\]]*)\] run return 0$", ln)] if m]
        pk_ = [selector_box(m.group(1)) for ln in pre
               for m in [re.match(r"^execute if entity @e\[type=cobblemon:pokemon,([^\]]*)\] run return 0$", ln)] if m]
        R.check("restore", any(b and contains(b, guard) for b in pl_),
                "%s does not return while a player stands in the face grown by 1 %s (got %s)" % (cname, guard, pl_))
        R.check("restore", any(b and contains(b, guard) for b in pk_),
                "%s does not return while a Pokemon stands in the face grown by 1 %s (got %s)" % (cname, guard, pk_))
        R.facts.setdefault("guards", {})[fid] = pl_[0] if pl_ else None
        # restore_<face>
        k_seen = set()
        for ln in lines_of(fnames[rname]):
            p = parse(ln)
            if p:
                kind, box, state, filt = p
                if not R.check("restore", kind == "fill" and filt in tags,
                               "%s writes without `replace <rearm tag>`: %s" % (rname, ln[:90])):
                    continue
                for c in cells(box):
                    R.check("restore", c in expect, "%s writes %s, outside the face's cells" % (rname, c))
                    R.check("restore", W.at(c) == state, "%s writes %s at %s; the build wrote %s"
                            % (rname, state, c, W.at(c)))
                continue
            m = re.match(r"^function %sfaces/seam_%s_(\d+)$" % (re.escape(FNREF), re.escape(fid)), ln)
            if m:
                k_seen.add(int(m.group(1)))
                continue
            if ln == "scoreboard players operation #%s fd.last = #now fd.t" % fid:
                continue
            R.check("restore", False, "%s runs an unexpected command: %s" % (rname, ln[:90]))
        R.check("restore", len(k_seen) == len(f["cells"]), "%s calls %d seam functions for %d seams"
                % (rname, len(k_seen), len(f["cells"])))
        # seam_<face>_<k>
        guarded = set()
        for k in sorted(k_seen):
            sname = "faces/seam_%s_%d" % (fid, k)
            sl = lines_of(fnames.get(sname, ""))
            R.check("restore", bool(sl), "%s is missing or empty" % sname)
            gpos, vals, rng = None, set(), None
            for ln in sl:
                m = re.match(r"^execute unless block (-?\d+) (-?\d+) (-?\d+) (\S+) run return 0$", ln)
                if m and gpos is None:
                    gpos = tuple(int(v) for v in m.groups()[:3])
                    R.check("restore", m.group(4) in tags, "%s guards on %s, not the rearm tag" % (sname, m.group(4)))
                    continue
                m = re.match(r"^execute store result score #v fd\.t run random value 0\.\.(\d+)$", ln)
                if m:
                    rng = int(m.group(1))
                    continue
                m = re.match(r"^execute if score #v fd\.t matches (\d+) run (setblock .*)$", ln)
                if m:
                    p = parse(m.group(2))
                    pos = p[1][:3]
                    if not R.check("restore", gpos is not None and pos == gpos,
                                   "%s sets %s before or without `unless block %s <rearm>`" % (sname, pos, pos)):
                        continue
                    R.check("restore", pos in seams_expected[fid], "%s re-arms %s, not a seam of the face" % (sname, pos))
                    R.check("restore", name_of(p[2]) == "minecraft:suspicious_gravel", "%s sets %s" % (sname, p[2]))
                    vals.add(int(m.group(1)))
                    lt = re.search(r'LootTable:"([^"]+)"', p[2])
                    if lt and jar_ok:
                        item, why = jar.rare_table(lt.group(1))
                        if R.check("loot", item is not None, "%s: %s" % (sname, why)):
                            fossil_items.add(item)
                    continue
                R.check("restore", False, "%s runs an unexpected command: %s" % (sname, ln[:90]))
            R.check("restore", rng is not None and vals == set(range(rng + 1)),
                    "%s: random 0..%s against cases %s" % (sname, rng, sorted(vals)))
            if gpos:
                guarded.add(gpos)
        R.check("restore", guarded == set(seams_expected[fid]),
                "face %s's seam functions guard %s, the seams are %s" % (fid, sorted(guarded), seams_expected[fid]))
    if jar_ok:
        R.check("loot", fossil_items == jar.fossils, "the restore's tables give %d of the %d fossils; missing %s"
                % (len(fossil_items), len(jar.fossils), sorted(jar.fossils - fossil_items)))

    # ---- driver
    tagj = {k: jload_text(v) for k, v in files.items() if k.startswith("data/minecraft/tags/function/")}
    R.check("driver", FNREF + "load" in (tagj.get("data/minecraft/tags/function/load.json") or {}).get("values", []),
            "the load tag does not name %sload" % FNREF)
    R.check("driver", FNREF + "tick" in (tagj.get("data/minecraft/tags/function/tick.json") or {}).get("values", []),
            "the tick tag does not name %stick" % FNREF)
    dl = lines_of(fnames.get("drive", ""))
    gate = next((i for i, ln in enumerate(dl) if ln == "execute unless score #built fd.t matches 1 run return 0"), None)
    site_ix = next((i for i, ln in enumerate(dl) if ln.endswith("run function %ssite" % FNREF)), None)
    now_ix = next((i for i, ln in enumerate(dl) if ln == "execute store result score #now fd.t run time query gametime"), None)
    R.check("driver", gate is not None and site_ix is not None and now_ix is not None and gate < now_ix < site_ix,
            "drive does not return unless #built, then read the time, before it runs site")
    R.check("driver", calls.get(FNREF + "site", set()) == {"drive"}, "site is called from %s"
            % sorted(calls.get(FNREF + "site", ())))
    R.check("driver", calls.get(FNREF + "drive", set()) == {"tick"}, "drive is called from %s"
            % sorted(calls.get(FNREF + "drive", ())))
    appr = None
    if site_ix is not None:
        m = re.search(r"@a\[([^\]]*)\]", dl[site_ix])
        appr = selector_box(m.group(1)) if m else None
    for fid, g_ in (R.facts.get("guards") or {}).items():
        R.check("driver", bool(appr and g_ and contains(appr, g_)),
                "the approach box %s does not hold face %s's guard box %s" % (appr, fid, g_))
    R.check("driver", built_at is not None and built_at > last_write,
            "the build does not set #built after its last write")
    stag = {m.group(1): int(m.group(2)) for ln in build_lines
            for m in [re.match(r"^scoreboard players remove #(\w+) fd\.last (-?\d+)$", ln)] if m}
    for f in doc["faces"]:
        back = stag.get(f["id"])
        R.check("driver", back is not None and 0 < back <= max(period, 1),
                "the build sets face %s's clock back %s ticks (0 < x <= the period %d)" % (f["id"], back, period))

    # ---- support and floating
    for c, s in W.w.items():
        nm = name_of(s)
        if nm == "minecraft:lantern":
            hang = "hanging=true" in s
            sup = (c[0], c[1] + 1, c[2]) if hang else (c[0], c[1] - 1, c[2])
            sn = W.name(sup)
            R.check("support", sn not in PASS and sn not in ("minecraft:lantern",),
                    "the lantern at %s (%s) has %s %s it" % (c, "hanging" if hang else "standing", sn,
                                                              "over" if hang else "under"))
        elif nm == "minecraft:spruce_wall_sign":
            m = re.search(r"facing=(\w+)", s)
            dx, dz = SIDES.get(m.group(1) if m else "", (0, 0))
            sup = (c[0] - dx, c[1], c[2] - dz)
            R.check("support", W.name(sup) not in PASS and (dx, dz) != (0, 0), "the wall sign at %s hangs on %s"
                    % (c, W.name(sup)))
        elif nm == "minecraft:spruce_sign":
            R.check("support", W.name((c[0], c[1] - 1, c[2])) not in PASS, "the sign at %s stands on air" % (c,))
    solid = {c for c, s in nonair.items() if name_of(s) not in HUNG}
    nb18 = [(a, b, d) for a in (-1, 0, 1) for b in (-1, 0, 1) for d in (-1, 0, 1)
            if (a, b, d) != (0, 0, 0) and abs(a) + abs(b) + abs(d) <= 2]
    seen, q = set(), deque()
    for c in solid:
        if any(W.at((c[0] + a, c[1] + b, c[2] + d)) == GROUND for a, b, d in nb18):
            seen.add(c)
            q.append(c)
    while q:
        c = q.popleft()
        for a, b, d in nb18:
            n = (c[0] + a, c[1] + b, c[2] + d)
            if n in solid and n not in seen:
                seen.add(n)
                q.append(n)
    floating = sorted(solid - seen)
    R.check("support", not floating, "%d blocks float (touch nothing grounded), e.g. %s" % (len(floating), floating[:3]))

    # ---- walk
    seat = _seat(data_dir)
    gys = [W.gy(x, z) for x in range(cb[0] - 2, cb[3] + 3) for z in range(cb[2] - 2, cb[5] + 3)]
    ylo, yhi = min(floors.values()), max(gys + [c[1] for c in nonair]) + 3

    def passable(c):
        return W.name(c) in PASS

    def standable(c):
        n = W.name(c)
        return n not in PASS and n not in NOSTAND

    def feet_ok(c):
        return passable(c) and passable((c[0], c[1] + 1, c[2])) and standable((c[0], c[1] - 1, c[2]))

    X0, X1, Z0, Z1 = cb[0] - 2, cb[3] + 2, cb[2] - 2, cb[5] + 2
    border = [(x, y, z) for x in range(X0, X1 + 1) for z in (Z0, Z1) for y in range(ylo, yhi + 1)] + \
             [(x, y, z) for x in (X0, X1) for z in range(Z0 + 1, Z1) for y in range(ylo, yhi + 1)]
    border = [c for c in border if feet_ok(c)]
    seen, q = set(border), deque(border)
    while q:
        x, y, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (X0 <= nx <= X1 and Z0 <= nz <= Z1):
                continue
            for dy in (-1, 0, 1):
                n = (nx, y + dy, nz)
                if n in seen or not (ylo <= n[1] <= yhi) or not feet_ok(n):
                    continue
                if dy == 1 and not passable((x, y + 2, z)):
                    continue
                if dy == -1 and not passable((nx, y + 1, nz)):
                    continue
                seen.add(n)
                q.append(n)
    R.check("walk", bool(border), "no standable ground round the clearing box")
    targets = [c for c in floor_feet if feet_ok(c)]
    lost = [c for c in targets if c not in seen]
    R.check("walk", not lost, "%d of %d pit floor cells cannot be walked to from the surrounding ground, e.g. %s"
            % (len(lost), len(targets), lost[:4]))
    R.facts["walk"] = {"floor_cells": len(targets), "reached": len(targets) - len(lost)}
    for f in doc["faces"]:
        dx, dz = SIDES[f["side"]]
        for s in seams_expected.get(f["id"], []):
            spot = (s[0] - dx, s[1], s[2] - dz)
            R.check("walk", spot in seen, "the seam %s's brushing cell %s cannot be walked to" % (s, spot))

    # ---- foreman
    if R.check("foreman", seat is not None, "data/npc_seats.json has no npc_fossil_dig_foreman"):
        x, y, z = seat["at"]
        gy = W.gy(x, z)
        R.check("foreman", y == gy + 1 and seat["ground"]["y"] == gy,
                "the foreman's seat %s is not on the heightmap ground y%d + 1 (recorded ground %s)"
                % (seat["at"], gy, seat["ground"]["y"]))
        R.check("foreman", feet_ok((x, y, z)), "the foreman's seat %s has %s/%s at feet/head over %s"
                % (seat["at"], W.name((x, y, z)), W.name((x, y + 1, z)), W.name((x, y - 1, z))))
        R.check("foreman", (x, y, z) in seen, "the foreman's seat %s cannot be walked to" % (seat["at"],))
        R.check("foreman", cb[0] <= x <= cb[3] and cb[2] <= z <= cb[5], "the foreman stands outside the dig")
        dlg = jload(data_dir / "dialogue.json")
        conv = next((c for c in dlg["conversations"] if c["id"] == seat["conversation"]), None)
        if R.check("foreman", conv is not None and conv.get("npc_id") == seat["id"],
                   "the seat's conversation %s is not the foreman's" % seat["conversation"]):
            nodes = [n["id"] for n in conv["nodes"]]
            prog = json.dumps(jload(data_dir / "progression.json"))
            cur = re.search(r'\{[^{}]*"quest_id": "%s"[^{}]*"field": "foreman_cursor"[^{}]*\}' % conv["quest_id"], prog)
            curd = json.loads(cur.group(0)) if cur else {}
            R.check("foreman", curd and set(curd.get("allowed_values") or []) == set(nodes)
                    and curd.get("initial") in nodes,
                    "the foreman's cursor allows %s; the nodes are %s" % (curd.get("allowed_values"), nodes))

    # ---- siting
    siting(R, cb, written, data_dir)
    return R


def jload_text(v):
    try:
        return json.loads(v)
    except ValueError:
        return {}


def _seat(data_dir):
    s = jload(Path(data_dir) / "npc_seats.json")["seats"]
    return next((x for x in s if x["id"] == "npc_fossil_dig_foreman"), None)


# ------------------------------------------------------------------------------------------------ siting
def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def authored(data_dir):
    """(points [(x, z, file)], boxes [(x0, z0, x1, z1, file)]) every other data/*.json authors. Skipped: this record,
    any dict whose id names the dig, and data/regions.json's polygon vertices (sub-region boundaries, not places)."""
    pts, boxes = [], []

    def walk(o, f, key=None):
        if isinstance(o, dict):
            if "fossil_dig" in str(o.get("id", "")):
                return
            if _num(o.get("x")) and _num(o.get("z")):
                pts.append((o["x"], o["z"], f))
            if all(_num(o.get(k)) for k in ("min_x", "min_z", "max_x", "max_z")):
                boxes.append((o["min_x"], o["min_z"], o["max_x"], o["max_z"], f))
            for k, v in o.items():
                if f == "regions.json" and k in ("polygons", "polygon"):
                    continue
                walk(v, f, k)
        elif isinstance(o, list):
            if o and all(_num(v) for v in o):
                n = len(o)
                if n == 2:
                    pts.append((o[0], o[1], f))
                elif n == 3:
                    pts.append((o[0], o[2], f) if -64 <= o[1] <= 320 else (o[0], o[1], f))
                elif n == 4 and o[2] >= o[0] and o[3] >= o[1]:
                    boxes.append((o[0], o[1], o[2], o[3], f))
                elif n == 6 and o[3] >= o[0] and o[5] >= o[2]:
                    boxes.append((o[0], o[2], o[3], o[5], f))
                return
            for v in o:
                walk(v, f, key)
    for p in sorted(Path(data_dir).glob("*.json")):
        if p.name in ("fossil_dig.json", "cells.json"):   # cells: the 1024-block planning grid, a label not a place
            continue
        walk(jload(p), p.name)
    # a box counts FILLED (a column inside it is 0 from it) when it is a place: at most PLACE_BOX a side, or a route's
    # spawn corridor (data/routes.json, which is what a road's encounters cover). A larger box is a scope, a cell
    # (CLAUDE.md: a cell indexes location only), a region or the world, and contains everything: its corners and
    # centre count as authored points, as the rule's text reads a box
    filled = []
    for b in boxes:
        if b[4] == "regions.json":      # a sub-region's bounding box: its boundary, as its polygon is
            continue
        if b[4] == "routes.json" or max(b[2] - b[0], b[3] - b[1]) <= PLACE_BOX:
            filled.append(b)
        else:
            for xx in (b[0], (b[0] + b[2]) / 2.0, b[2]):
                for zz in (b[1], (b[1] + b[3]) / 2.0, b[3]):
                    pts.append((xx, zz, b[4]))
    return pts, filled


PLACE_BOX = 512


def keep_outs(data_dir):
    """[(x0, z0, x1, z1), file]: every box any other data/*.json declares under a keep_out* key ({"box": [..]},
    {"min": [x, z], "max": [x, z]} or a bare [x0, z0, x1, z1]). The record's own copy is not read: the rule is
    whatever the declaring file says today."""
    out = []

    def take(v, f):
        if isinstance(v, dict):
            if isinstance(v.get("box"), list) and len(v["box"]) == 4:
                out.append((tuple(v["box"]), f))
            elif isinstance(v.get("min"), list) and isinstance(v.get("max"), list):
                out.append(((v["min"][0], v["min"][1], v["max"][0], v["max"][1]), f))
            for w in v.values():
                if isinstance(w, (list, dict)):
                    take(w, f)
        elif isinstance(v, list):
            if len(v) == 4 and all(_num(a) for a in v):
                out.append((tuple(v), f))
            else:
                for w in v:
                    take(w, f)

    def walk(o, f):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.startswith("keep_out"):
                    take(v, f)
                else:
                    walk(v, f)
        elif isinstance(o, list):
            for v in o:
                walk(v, f)
    for p in sorted(Path(data_dir).glob("*.json")):
        if p.name != "fossil_dig.json":
            walk(jload(p), p.name)
    return list(dict.fromkeys(out))


def _rect_d(cols, r):
    import numpy as np
    dx = np.maximum(np.maximum(r[0] - cols[:, 0], cols[:, 0] - r[2]), 0)
    dz = np.maximum(np.maximum(r[1] - cols[:, 1], cols[:, 1] - r[3]), 0)
    return np.hypot(dx, dz)


def _seg_d(cols, a, b):
    import numpy as np
    ax, az = a
    bx, bz = b
    vx, vz = bx - ax, bz - az
    L = vx * vx + vz * vz
    t = np.zeros(len(cols)) if L == 0 else np.clip(((cols[:, 0] - ax) * vx + (cols[:, 1] - az) * vz) / L, 0, 1)
    return np.hypot(cols[:, 0] - (ax + t * vx), cols[:, 1] - (az + t * vz))


def _in_poly(x, z, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, z1 = poly[i][:2]
        x2, z2 = poly[(i + 1) % n][:2]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            inside = not inside
    return inside


_AUTHORED = {}


def siting(R, cb, written, data_dir):
    import numpy as np
    data_dir = Path(data_dir)
    cols = {(x, z) for x in range(cb[0], cb[3] + 1) for z in range(cb[2], cb[5] + 1)} | {(c[0], c[2]) for c in written}
    C = np.array(sorted(cols), float)
    # box corners and the mid points stand for the whole box in the nearest checks below: the clearing box is convex,
    # so its nearest column to any point or segment outside it is on its boundary
    near = {}
    clear = jload(data_dir / "encounter_design.json")["rules"]["hearts"]["clear_of_path_blocks"]
    rules = jload(data_dir / "southern_residents.json")["rules"]
    ac = rules["authored_clearance"]
    best = (1e9, None)
    for name, pts in jload(data_dir / "route_paths.json")["paths"].items():
        P = [tuple(p[:2]) for p in pts]
        for a, b in zip(P, P[1:] or P):
            d = float(np.min(_seg_d(C, a, b)))
            if d < best[0]:
                best = (d, name)
    near["route_path"] = best
    R.check("siting", best[0] >= clear, "%.0f blocks from route path %s (needs %d)" % (best[0], best[1], clear))
    key = str(data_dir.resolve())
    if key not in _AUTHORED:          # one scan per data folder per process (the tests audit many builds)
        _AUTHORED[key] = authored(data_dir)
    pts, boxes = _AUTHORED[key]
    P = np.array([(a, b) for a, b, _f in pts], float)
    dmin, who = 1e9, None
    for i in range(0, len(P), 4096):
        blk = P[i:i + 4096]
        d = np.hypot(C[:, None, 0] - blk[None, :, 0], C[:, None, 1] - blk[None, :, 1]).min(axis=0)
        j = int(np.argmin(d))
        if d[j] < dmin:
            dmin, who = float(d[j]), pts[i + j]
    near["authored_point"] = (dmin, who)
    R.check("siting", dmin >= ac, "%.0f blocks from %s authored in data/%s (needs %d)" % (dmin, who[:2], who[2], ac))
    bmin, bwho = 1e9, None
    for b in boxes:
        d = float(np.min(_rect_d(C, b)))
        if d < bmin:
            bmin, bwho = d, b
    near["authored_box"] = (bmin, bwho)
    R.check("siting", bmin >= ac, "%.0f blocks from the box %s in data/%s (needs %d)" % (bmin, bwho[:4], bwho[4], ac))
    # an owner's siting decision recorded in data/fossil_dig.json keep_out_overrides ({file, box, decided}) waives the
    # overlap with exactly that box and nothing else; it is reported, never silently passed
    waived = {(o["file"], tuple(o["box"])) for o in (jload(data_dir / "fossil_dig.json").get("keep_out_overrides") or [])}
    for kb, f in keep_outs(data_dir):
        inside = float(np.min(_rect_d(C, kb))) <= 0
        if inside and (f, tuple(kb)) in waived:
            print("WAIVED siting: the dig overlaps the keep-out box %s in data/%s, by the owner's decision recorded in "
                  "data/fossil_dig.json keep_out_overrides" % (list(kb), f))
            continue
        R.check("siting", not inside, "the dig overlaps the keep-out box %s declared in data/%s" % (list(kb), f))
    for t in jload(data_dir / "towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        d = float(np.min(_rect_d(C, (f["min_x"], f["min_z"], f["max_x"], f["max_z"]))))
        near.setdefault("town", (1e9, None))
        if d < near["town"][0]:
            near["town"] = (d, t.get("display_name") or t["id"])
        R.check("siting", d >= ac, "%.0f blocks from town %s's footprint (needs %d)" % (d, t["id"], ac))
    for k, z in jload(data_dir / "rift_zones.json")["zones"].items():
        for bx in z.get("boxes") or []:
            R.check("siting", float(np.min(_rect_d(C, bx[:4]))) > 0, "inside Rift zone %s %s" % (k, bx[:4]))
    for b in jload(data_dir / "habitat_blocks.json")["blocks"]:
        if b.get("style") != "activated":
            continue
        d = float(np.min(np.hypot(C[:, 0] - b["position"]["x"], C[:, 1] - b["position"]["z"])))
        R.check("siting", d > b["activated"]["spawn_range"], "Habitat Block %s's spawn range %d reaches the dig (%.0f)"
                % (b["id"], b["activated"]["spawn_range"], d))
    for e in jload(data_dir / "resident_encounters.json")["encounters"]:
        loc = e.get("location") or {}
        if not (_num(loc.get("x")) and _num(loc.get("z"))):
            continue
        leash = (e.get("build") or {}).get("leash") or 28
        d = float(np.min(np.hypot(C[:, 0] - loc["x"], C[:, 1] - loc["z"])))
        if e["id"] == "hornwall":
            near["hornwall"] = (d, leash)
        R.check("siting", d > leash and d >= ac, "%.0f blocks from resident %s (leash %d, clearance %d)"
                % (d, e["id"], leash, ac))
    gm = jload(data_dir / "gulch_mine.json")
    poly = gm["mega_field"]["polygon"]
    pin = [c for c in cols if _in_poly(c[0], c[1], poly)]
    R.check("siting", not pin, "%d columns inside the Mega field polygon" % len(pin))
    pd = min(float(np.min(_seg_d(C, tuple(poly[i][:2]), tuple(poly[(i + 1) % len(poly)][:2]))))
             for i in range(len(poly)))
    near["mega_field"] = pd
    R.check("siting", pd >= ac, "%.0f blocks from the Mega field polygon (needs %d)" % (pd, ac))
    for farm in gm.get("farms") or []:
        for den in farm.get("dens") or []:
            ax, _ay, az = den["anchor"]
            d = float(np.min(np.hypot(C[:, 0] - ax, C[:, 1] - az)))
            R.check("siting", d > den["leash"] and d >= ac, "%.0f blocks from Mega den %s (leash %d)"
                    % (d, den["id"], den["leash"]))
    R.facts["nearest"] = near


# ------------------------------------------------------------------------------------------------ CLI
def read_pack(pack):
    pack = Path(pack)
    return {p.relative_to(pack).as_posix(): p.read_text(encoding="utf-8") for p in pack.rglob("*") if p.is_file()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--jar-dir", default=os.environ.get("COBBLERS_JAR_DIR") or str(LOCAL_JARS))
    ap.add_argument("--source-root")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT / "tools"))
    import ground as G
    if not Path(a.pack).is_dir():
        print("fossil_dig_audit: FAIL: no pack at %s (run python tools/fossil_dig.py build)" % a.pack)
        return 1
    jp = find_jar(a.jar_dir)
    rep = audit(read_pack(a.pack), G.load(a.source_root), jar=Jar(jp) if jp else None)
    body = ["%s: %s" % k for k in rep.problems]
    body.append("facts: %s" % json.dumps(rep.facts, default=str))
    body.append("checks: %s" % json.dumps(rep.checks))
    if a.out:
        Path(a.out).write_text("\n".join(body) + "\n", encoding="utf-8")
    else:
        for ln in body[:40]:
            print(ln)
    n = sum(rep.checks.values())
    print("fossil_dig_audit: %s: %d problem(s) over %d checks in %d groups (jar %s)"
          % ("PASS" if not rep.problems else "FAIL", len(rep.problems), n, len(rep.checks), jp or "MISSING"))
    return 1 if rep.problems else 0


if __name__ == "__main__":
    sys.exit(main())
