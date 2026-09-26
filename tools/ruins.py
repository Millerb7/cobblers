#!/usr/bin/env python
"""Ruined copies of donor houses, from data/ruins.json: the Scar's thirty-three houses.

The owner chose a ruined city for the Scar (2026-09-25): the footprint the Displaced City left when it went
underground, drawn as a town and standing in ruin. A ruin is a donor house placed from a ruined copy of its template,
the way a re-materialed house is placed from a re-materialed copy (tools/place_town.py rewrite_template). The copy is
written into the build pack, never into kits/ (Repurposed Structures' houses are not ours to commit), and it is
byte-identical on every rebuild: every random draw is seeded by sha256(seed/ruin id/step).

The transform, in the order data/ruins.json gives it:
  strip       waystones; every jigsaw becomes its final state inside the copy (place_town then sets no jigsaw
              blocks after placing a ruin, which would put back what the decay took)
  remove      light, the two spawn-deciding blocks, and everything that was the people's (containers, beds, doors,
              workstations, glass, water): the containers take their loot tables with them
  decay       each column cut to grade + max(1, round(wall height x f)), f from the ruin's decay class by seeded 2D
              value noise, so neighbouring columns fall together; the roof (every layer over the eaves) goes
  breaches    gaps 2 to 4 wide in the outer walls, never in the doorway
  weather     cobble to mossy, stone brick to cracked or mossy, rotten spruce dropped
  rubble      on the first layer over the floor, near a breach or a cut wall, never in the doorway
  overgrowth  snow and moss carpet on open tops and floors, moss in the floor, vines inside the north walls

The ground layer (the entrance jigsaw's layer) and everything below it is never cut or swapped, except the moss
block swap, so place_town seats the ruin and its verify tests the corners exactly as for the whole house. A removed
block is dropped from the copy, never written as air: whatever the world holds there stays.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import random
from pathlib import Path

import level_dat as L

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "ruins.json"
AIRS = {"minecraft:air", "minecraft:cave_air", "minecraft:structure_void"}
NOT_FULL = ("_stairs", "_slab", "_fence", "_wall", "_pane", "_bars", "_trapdoor", "_door", "_carpet", "torch",
            "_button", "_pressure_plate", "_sign", "lantern", "_bed", "ladder", "vine", "snow", "_gate", "chain", "rod")
CROPS = {"minecraft:wheat", "minecraft:carrots", "minecraft:potatoes", "minecraft:beetroots", "minecraft:melon_stem",
         "minecraft:pumpkin_stem", "minecraft:attached_melon_stem", "minecraft:attached_pumpkin_stem",
         "minecraft:torchflower_crop", "minecraft:pitcher_crop"}
WOOL = ("white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray", "light_gray", "cyan", "purple",
        "blue", "brown", "green", "red", "black")


def load(path=DATA):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("schema") != "cobblers.ruins/1":
        raise SystemExit("%s: schema must be cobblers.ruins/1" % path)
    return d


def ruin_of(site, ruin_id):
    for r in site["ruins"]:
        if r["id"] == ruin_id:
            return r
    raise SystemExit("data/ruins.json has no ruin %r" % ruin_id)


def _rng(seed, rid, step):
    return random.Random(int(hashlib.sha256(("%s/%s/%s" % (seed, rid, step)).encode()).hexdigest()[:16], 16))


def _in_tag(name, entry):
    if not entry.startswith("#"):
        return name == entry
    tag = entry[len("#minecraft:"):]
    short = name.split(":", 1)[1] if ":" in name else name
    if tag == "beds":
        return short.endswith("_bed")
    if tag == "doors":
        return short.endswith("_door")
    if tag == "wool_carpets":
        return short.endswith("_carpet") and short[:-len("_carpet")] in WOOL
    if tag == "banners":
        return short.endswith("_banner")
    if tag == "flower_pots":
        return short == "flower_pot" or short.startswith("potted_")
    if tag == "crops":
        return name in CROPS
    raise SystemExit("data/ruins.json names a tag this tool does not know: %s" % entry)


def _full(name):
    return name not in AIRS and not any(k in name for k in NOT_FULL)


def _parse_state(s):
    """'minecraft:x[a=b,c=d]' -> (name, {a: b, c: d})."""
    if "[" not in s:
        return s.split("{")[0], {}
    name, rest = s.split("[", 1)
    props = {}
    for kv in rest.rstrip("]").split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            props[k.strip()] = v.strip()
    return name, props


class Copy:
    """A template as cells: {(x, y, z): (name, props, nbt or None)}."""

    def __init__(self, src):
        raw = Path(src).read_bytes()
        self.name, self.root = L.loads(raw)
        if gzip.decompress(L.dumps(self.name, self.root)) != gzip.decompress(raw):
            raise SystemExit("%s does not round-trip through the NBT writer; refusing to rewrite it" % src)
        pal = self.root["palette"][1][1]
        self.pal = [(L.plain(e["Name"]), L.plain(e["Properties"]) if "Properties" in e else {}) for e in pal]
        self.cells = {}
        for b in self.root["blocks"][1][1]:
            pos = tuple(L.plain(b["pos"]))
            n, pr = self.pal[L.plain(b["state"])]
            self.cells[pos] = (n, dict(pr), b.get("nbt"))
        self.size = L.plain(self.root["size"])

    def name_at(self, p):
        c = self.cells.get(p)
        return c[0] if c else None

    def write(self, dest):
        palette, index, blocks = [], {}, []
        for pos in sorted(self.cells, key=lambda q: (q[1], q[2], q[0])):
            n, pr, nbt = self.cells[pos]
            key = (n, tuple(sorted(pr.items())))
            if key not in index:
                index[key] = len(palette)
                e = {"Name": (L.STRING, n)}
                if pr:
                    e["Properties"] = (L.COMPOUND, {k: (L.STRING, str(v)) for k, v in sorted(pr.items())})
                palette.append(e)
            b = {"pos": (L.LIST, (L.INT, list(pos))), "state": (L.INT, index[key])}
            if nbt is not None:
                b["nbt"] = nbt
            blocks.append(b)
        self.root["palette"] = (L.LIST, (L.COMPOUND, palette))
        self.root["blocks"] = (L.LIST, (L.COMPOUND, blocks))
        self.root["entities"] = (L.LIST, (L.COMPOUND, []))
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(L.dumps(self.name, self.root))


def _noise(rng, sx, sz, lo, hi, step=3):
    """Bilinear value noise over the template's columns, lattice every `step` blocks, values in [lo, hi]."""
    nx, nz = sx // step + 2, sz // step + 2
    lat = [[lo + (hi - lo) * rng.random() for _ in range(nz)] for _ in range(nx)]

    def f(x, z):
        gx, gz = x / step, z / step
        i, j = int(gx), int(gz)
        tx, tz = gx - i, gz - j
        a = lat[i][j] * (1 - tx) + lat[i + 1][j] * tx
        b = lat[i][j + 1] * (1 - tx) + lat[i + 1][j + 1] * tx
        return a * (1 - tz) + b * tz
    return f


def ruin_template(src, dest, info, rec, site):
    """Write dest, the ruined copy of src for ruin record `rec`. info is tools/place_town.template_info(src).
    -> counts of what the transform did."""
    seed, rid = site["seed"], rec["id"]
    T = site["transform"]
    cls = site["decay_classes"][rec["decay"]]
    c = Copy(src)
    grade = info["grade_layer"]
    ent = tuple(info["entrance_pos"]) if info["entrance_pos"] else None
    sx, sy, sz = c.size
    st = {"removed": 0, "decayed": 0, "breached": 0, "weathered": 0, "rubble": 0, "snow": 0, "moss": 0, "vines": 0}

    # strip: waystones out, jigsaws to their final state
    for pos, (n, pr, nbt) in list(c.cells.items()):
        if n.startswith("waystones:"):
            del c.cells[pos]
        elif n == "minecraft:jigsaw":
            fs = ((L.plain(nbt) if nbt else {}) or {}).get("final_state") or "minecraft:air"
            fn, fp = _parse_state(fs)
            if fn == "minecraft:structure_void":
                del c.cells[pos]
            else:
                c.cells[pos] = (fn, fp, None)

    # the doorway: the entrance column and one each side, three deep into the house, never breached or rubbled
    door = set()
    if ent:
        ex, _, ez = ent
        for a in (-1, 0, 1):
            for d in range(0, 4):
                door |= {(ex + a, ez + d), (ex + a, ez - d), (ex + d, ez + a), (ex - d, ez + a)}

    # the walls and the eaves, measured on the whole house before anything is taken out (windows, doors and
    # torches are part of a wall: measured after them, a window row reads as a gap and the eaves come out at 2-3)
    wall = {(x, z) for (x, y, z), (n, _, _) in c.cells.items() if y == grade + 1 and n not in AIRS}
    wall &= {(x, z) for (x, y, z), (n, _, _) in c.cells.items() if y == grade + 2 and n not in AIRS}
    if not wall:
        wall = {(x, z) for (x, y, z), (n, _, _) in c.cells.items() if y == grade + 1 and n not in AIRS}
    eaves = grade + 1
    for y in range(grade + 1, sy):
        up = sum(1 for (x, z) in wall if c.name_at((x, y, z)) is not None and c.name_at((x, y, z)) not in AIRS)
        if wall and up >= 0.6 * len(wall):
            eaves = y
    height = max(1, eaves - grade)

    # remove: light, spawn blocks, belongings, at every layer. In many of these houses the entrance layer is also the
    # room's layer, so its beds (a respawn point), doors, chests (with loot tables) stand on it, and one keeps a well's
    # water below it; the floor blocks themselves are never in these lists, so the house's floor is untouched
    rb = T["remove_blocks"]
    gone = [e for k in ("light", "spawn_blocks", "belongings") for e in rb[k]]
    for pos, (n, pr, nbt) in list(c.cells.items()):
        if any(_in_tag(n, e) for e in gone):
            del c.cells[pos]
            st["removed"] += 1

    # decay: each column to its height; the roof above the eaves always goes
    f = _noise(_rng(seed, rid, "decay"), sx, sz, *cls["wall_top_fraction"])
    top = {}
    for x in range(sx):
        for z in range(sz):
            top[(x, z)] = grade + max(1, int(round(height * f(x, z))))
    cut = {}
    for pos in list(c.cells):
        x, y, z = pos
        if y > top[(x, z)]:
            if c.cells[pos][0] not in AIRS:
                st["decayed"] += 1
                if (x, z) in wall:
                    cut[(x, z)] = cut.get((x, z), 0) + 1
            del c.cells[pos]

    # breaches: gaps 2-4 wide in each outer face, from 1-3 above the floor up
    rng = _rng(seed, rid, "breaches")
    lo, hi = cls["breaches_per_face"]
    breach = set()
    if wall:
        xs, zs = [x for x, _ in wall], [z for _, z in wall]
        faces = {"north": sorted((x, z) for x, z in wall if z == min(zs)), "south": sorted((x, z) for x, z in wall if z == max(zs)),
                 "west": sorted((x, z) for x, z in wall if x == min(xs)), "east": sorted((x, z) for x, z in wall if x == max(xs))}
        for fname in sorted(faces):
            cells = [q for q in faces[fname] if q not in door]
            for _ in range(rng.randint(lo, hi)):
                if len(cells) < 3:
                    break
                w = rng.randint(2, 4)
                i = rng.randrange(0, max(1, len(cells) - w + 1))
                y0 = grade + 1 + rng.randint(0, 2)
                for (x, z) in cells[i:i + w]:
                    for y in range(y0, top[(x, z)] + 1):
                        if (x, y, z) in c.cells and c.cells[(x, y, z)][0] not in AIRS:
                            del c.cells[(x, y, z)]
                            st["breached"] += 1
                            cut[(x, z)] = cut.get((x, z), 0) + 1
                    breach.add((x, z))

    # weather what is left, above the floor
    rng = _rng(seed, rid, "weather")
    swaps = {}
    for s in T["weathering"]["swaps"]:
        swaps.setdefault(s["from"], []).append((s["to"], s["chance"]))
    for pos in sorted(c.cells):
        n, pr, nbt = c.cells[pos]
        if pos[1] <= grade or n not in swaps:
            continue
        r, acc = rng.random(), 0.0
        for to, ch in swaps[n]:
            acc += ch
            if r < acc:
                if to is None:
                    del c.cells[pos]
                else:
                    c.cells[pos] = (to, pr, nbt)
                st["weathered"] += 1
                break

    floor = set(info["grade_cols"])

    def empty(p):
        return c.name_at(p) is None or c.name_at(p) in AIRS

    # rubble: inside, on the first layer over the floor, near a breach or a wall cut by more than two courses
    rng = _rng(seed, rid, "rubble")
    near = {q for q, k in cut.items() if k > 2} | breach
    spots = sorted((x, z) for (x, z) in floor if (x, z) not in door and (x, z) not in wall
                   and any(abs(x - a) <= 2 and abs(z - b) <= 2 for a, b in near) and empty((x, grade + 1, z)))
    rng.shuffle(spots)
    pal = [(p["block"], p["weight"]) for p in T["rubble"]["palette"]]
    want = int(round(0.15 * (st["decayed"] + st["breached"])))
    for (x, z) in spots[:want]:
        blk = rng.choices([b for b, _ in pal], weights=[w for _, w in pal])[0]
        n, pr = _parse_state(blk)
        if n == "minecraft:spruce_log":
            pr = {"axis": rng.choice(["x", "z"])}
        c.cells[(x, grade + 1, z)] = (n, pr, None)
        st["rubble"] += 1

    # overgrowth: snow on open tops, moss on open floor, vines inside the north walls
    rng = _rng(seed, rid, "overgrowth")
    tops = []
    for x in range(sx):
        for z in range(sz):
            ys = [y for (a, y, b) in c.cells if a == x and b == z and c.cells[(a, y, b)][0] not in AIRS]
            if ys:
                y = max(ys)
                # only on the floor or above: a column whose top is below the ground layer (a foundation step, the
                # entrance jigsaw's void) would put snow into the layer the ruin keeps
                if grade <= y and y + 1 < sy and _full(c.cells[(x, y, z)][0]):
                    tops.append((x, y, z))
    snowed = set()
    for (x, y, z) in tops:
        r = rng.random()
        if r < 0.10:
            c.cells[(x, y + 1, z)] = ("minecraft:snow", {"layers": "2"}, None)
        elif r < 0.45:
            c.cells[(x, y + 1, z)] = ("minecraft:snow", {"layers": "1"}, None)
        else:
            continue
        snowed.add((x, z))
        st["snow"] += 1
    for (x, z) in sorted(floor):
        p = (x, grade, z)
        if (x, z) in snowed or not empty((x, grade + 1, z)) or p not in c.cells:
            continue
        n = c.cells[p][0]
        r = rng.random()
        if n in ("minecraft:stone", "minecraft:cobblestone", "minecraft:stone_bricks") and r < 0.10:
            c.cells[p] = ("minecraft:moss_block", {}, None)
            st["moss"] += 1
        elif r < 0.25 and _full(n):
            c.cells[(x, grade + 1, z)] = ("minecraft:moss_carpet", {}, None)
            st["moss"] += 1
    if wall:
        nz = min(z for _, z in wall)
        for (x, z) in sorted(q for q in wall if q[1] == nz):
            for y in range(grade + 2, top[(x, z)] + 1):
                inner = (x, y, z + 1)
                if (x, y, z) in c.cells and _full(c.cells[(x, y, z)][0]) and empty(inner) and z + 1 < sz and rng.random() < 0.12:
                    c.cells[inner] = ("minecraft:vine", {"north": "true", "east": "false", "south": "false", "west": "false", "up": "false"}, None)
                    st["vines"] += 1
    c.write(dest)
    st["wall_height"], st["eaves"] = height, eaves
    return st
