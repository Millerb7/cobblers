#!/usr/bin/env python
"""Arrow Creeks Farm (data/pokemon_farm.json): a working farm whose livestock are Pokemon.

The owner, 2026-10-05: "at 3149 5714 [there] should have a pokemon based farm that is like a normal farm, milk,
leather, yadda yadda." Measured first (data/pokemon_farm.json site.measured): flat savanna in Arrow Creeks, cell F4,
ground y86-y92 over the 97-block square, dry, 457 blocks from the nearest walked route line.

Nothing here is new machinery. Every part is an existing, proven piece, CALLED, not copied:

  the blocks    tools/southern_residents.py's Site and primitives (a structure on a levelled floor, surface work,
                blocks on their own column's ground, posts), tools/northern_residents.py's clearing, and its
                build_lines/merged_clears writer. Four farm pieces are written here and EXPAND into those: a
                `building` (walls, posts, openings, doors, windows, a gable roof, tie beams and lamps) and a `silo`
                become a `structure` piece; a `fence` and a `field` are blocks on their own column's ground, the way
                ground_blocks seats them. Every Y is the canonical heightmap's rounded ground (tools/ground.py), never a
                world's. A last pass sets every fence's and pane's connections from the planned neighbours and the
                heightmap, so no line depends on the order the server updates shapes in.
  the animals   the idle Pokemon of tools/ambient_idle.py (R16C), not a keeper of our own: idlers() hands it this
                farm's animals as one more group (the snow house's Buneary are the precedent), spawned `uncatchable
                no_ai` through its macro and claimed with the workers' flags. Stalled and penned animals that do not
                move are its `loafer` (NoAI, put back on the spot each keep); grazing ones are its `follower` (AI on,
                cobblemon:wanders + cobblemon:stationary round a home), each in a fenced pen. The wool flock's list adds
                cobblemon:pokemon_eats_grass (jar data/cobblemon/behaviours/pokemon/pokemon_eats_grass.json): its
                EatGrassTask starts only on a `sheared` Pokemon and clears the flag when it eats a grass block, so a
                sheared Mareep, Wooloo or Dubwool grows its fleece back (read from the 1.8.0 jar, NOT seen in game).
  the farmer    a dialogue NPC: data/dialogue.json dlg_pokemon_farm_farmer, data/quests.json ambient_pokemon_farm,
                seated by data/npc_seats.json (R17N). This tool checks the seat is the spot its plan leaves open.
  the stand     a CobbleDollars merchant (data/markets.json stall arrow_creeks_farm_stand, place pokemon_farm in
                places_beyond_towns), summoned by tools/markets.py at R17M. This tool checks its seat likewise.

What Cobblemon 1.8.0 does natively here (read from Cobblemon-fabric-1.8.0+1.21.1.jar, not seen in game):
  shearing   PokemonEntity is vanilla Shearable; its interact runs the shears branch when the Pokemon's owner is the
             player OR it has no owner, and isShearable needs the species' `sheared` feature off. Mareep, Wooloo and
             Dubwool carry `sheared`, so a player's shears work on the farm's unowned flock.
  milking    NOT for these animals. data/cobblemon/pokemon_interactions/miltank.json (bucket -> milk_bucket, bottle ->
             moomoo_milk), gogoat.json / skiddo.json / bouffalant.json (female, bucket) all require
             `owner_held_item`, whose OwnerQueryRequirement returns false when getOwnerEntity is null. A player milks
             their OWN Miltank; the farm's are dressing, and the farmer says so.
  honey      native refill (the owner, 2026-10-05, "yeah combee refills"): the hives start at honey_level=5 and the
             four apiary Combee are followers whose list adds cobblemon:pokemon_bee (combee.json's own `ai` applies
             it; behaviours/pokemon/pokemon_bee.json: pollinate a flower, path to a hive, place honey in it when
             is_wild, i.e. no owner). The Pokemon enters the hive as a vanilla occupant and its release raises
             honey_level. Dandelions and cornflowers within FlowerSensor's 5-block box feed them (policy entry scoped
             to pokemon_farm). Vespiquen has no bee behaviour in the jar and stays a loafer; her own honey
             interaction is owner-only like the milk. NOT seen in game.
  wheat      the wheat field (the owner, 2026-10-05, "make wheat field"): mature and late-sown wheat on farmland
             with no water (a spawn condition); a crop on every farmland block keeps it farmland.
  eggs, leather, feathers  dressing and the stand's stock: nothing native gives them from an unowned Pokemon
             (Torchic's brush -> feather interaction is owner-only; drops need a death the claim's flags prevent).

The siting rules fail the build (data/pokemon_farm.json rules): every written column and spot at least
rules.authored_clearance from every x/z another data file authors (this farm's own records there skipped by id) and
from every route corridor box; outside every town footprint (+ the same clearance), every Rift zone box and every
keep-out box (the far south's Mega field box, read from data/far_south.json, and the apricorn orchard's); the centre
and both NPCs at least rules.path_clearance from a route path; a follower's leash clear of every activated Habitat
Block's spawn_range; no block a spawn condition names (data/spawn_blocks.json). These are the builder's guards, not an
audit: the independent audit is another agent's (data/pokemon_farm.json audit_checklist).

  python tools/pokemon_farm.py [--source-root R] [--out DIR]    write build/datapacks/cobblers_pokemon_farm
  python tools/pokemon_farm.py --report                          the site as measured, the checks, the step

The re-application (tools/reapply.py): placement_steps() is R9PF, after R9FS and BEFORE R9E with the other block
passes. The animals are R16C's (tools/ambient_idle.py), the farmer R17N's, the stand's merchant R17M's.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402
import northern_residents as NR  # noqa: E402
import southern_residents as SR  # noqa: E402

DATA = ROOT / "data" / "pokemon_farm.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_pokemon_farm"
SCHEMA = "cobblers.pokemon-farm/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
TOWN = "pokemon_farm"            # the group name tools/ambient_idle.py files the animals under, and markets.json's place
KINDS = SR.KINDS + ("clearing", "building", "silo", "fence", "field", "scatter")
ANIMAL_KINDS = ("loafer", "follower")
FACES = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class FarmError(SystemExit):
    pass


base = SR.base
jload = SR.jload


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise FarmError("%s: schema must be %s" % (path, SCHEMA))
    for p in doc["pieces"]:
        if p["kind"] not in KINDS:
            raise FarmError("piece %s: unknown kind %s" % (p.get("name"), p["kind"]))
    names = [p["name"] for p in doc["pieces"]]
    if len(names) != len(set(names)):
        raise FarmError("piece names must be unique (an animal names the building it stands in)")
    ids = [a["id"] for a in doc["animals"]]
    if len(ids) != len(set(ids)):
        raise FarmError("animal ids must be unique")
    for a in doc["animals"]:
        if a["kind"] not in ANIMAL_KINDS:
            raise FarmError("%s: kind %s is not one of %s" % (a["id"], a["kind"], ANIMAL_KINDS))
        if a["species"] not in doc["species"]:
            raise FarmError("%s: species %s has no size record in species" % (a["id"], a["species"]))
        if a["kind"] == "follower" and not a.get("pen"):
            raise FarmError("%s: a follower walks; it needs the pen (a fence piece) that holds it" % a["id"])
    return doc


def _rec(doc):
    """The record shape tools/southern_residents.py's Site takes."""
    return {"id": doc["id"], "name": doc["name"], "site": doc["site"], "pieces": doc["pieces"]}


# ------------------------------------------------------------------ the farm pieces, expanded into structure pieces


def _stairs(st, facing):
    return "%s[facing=%s,half=bottom,shape=straight,waterlogged=false]" % (st, facing)


def _roof(p, blocks):
    """A gable roof over the footprint: stairs rising from both eaves, a ridge where they meet, gable ends filled.
    Returns the top dy."""
    x0, z0, x1, z1 = p["footprint"]
    rf = p["roof"]
    h = int(p["walls"]["height"])
    ov = int(rf.get("overhang", 1))
    gable = rf.get("gable")
    k = 0
    while True:
        dy = h + 1 + k
        if rf["axis"] == "x":
            lo, hi = z0 - ov + k, z1 + ov - k
            if lo > hi:
                break
            for x in range(x0 - ov, x1 + ov + 1):
                if lo == hi:
                    blocks.append([x, dy, lo, rf["ridge"]])
                else:
                    blocks.append([x, dy, lo, _stairs(rf["stairs"], "south")])
                    blocks.append([x, dy, hi, _stairs(rf["stairs"], "north")])
            if gable:
                for z in range(max(z0, lo + 1), min(z1, hi - 1) + 1):
                    blocks.append([x0, dy, z, gable])
                    blocks.append([x1, dy, z, gable])
        else:
            lo, hi = x0 - ov + k, x1 + ov - k
            if lo > hi:
                break
            for z in range(z0 - ov, z1 + ov + 1):
                if lo == hi:
                    blocks.append([lo, dy, z, rf["ridge"]])
                else:
                    blocks.append([lo, dy, z, _stairs(rf["stairs"], "east")])
                    blocks.append([hi, dy, z, _stairs(rf["stairs"], "west")])
            if gable:
                for x in range(max(x0, lo + 1), min(x1, hi - 1) + 1):
                    blocks.append([x, dy, z0, gable])
                    blocks.append([x, dy, z1, gable])
        if lo >= hi:
            return dy
        k += 1
    return h + k


def _face_cols(p, face):
    x0, z0, x1, z1 = p["footprint"]
    if face == "north":
        return [(x, z0) for x in range(x0, x1 + 1)]
    if face == "south":
        return [(x, z1) for x in range(x0, x1 + 1)]
    if face == "west":
        return [(x0, z) for z in range(z0, z1 + 1)]
    return [(x1, z) for z in range(z0, z1 + 1)]


def _opening_cols(p, o):
    """The wall columns an opening or window takes: `at` is its first dx (north/south faces) or dz (east/west)."""
    cols = _face_cols(p, o["face"])
    i = 0 if o["face"] in ("north", "south") else 1
    want = range(int(o["at"]), int(o["at"]) + int(o.get("width", 1)))
    got = [c for c in cols if c[i] in want]
    if len(got) != len(want):
        raise FarmError("%s: opening %s runs off the %s wall" % (p["name"], o, o["face"]))
    return got


def expand_building(p):
    """A `building` -> the `structure` piece tools/southern_residents.py builds (floor at dy 0 = the highest ground
    under the footprint, foundation below it). Later entries override earlier ones, so the order is: floor, walls or
    posts, roof, openings, windows, beams, interior."""
    x0, z0, x1, z1 = p["footprint"]
    w = p["walls"]
    h = int(w["height"])
    blocks = []
    fills = [[x0, 0, z0, x1, 0, z1, p["floor"]]]
    perim = set(_face_cols(p, "north") + _face_cols(p, "south") + _face_cols(p, "west") + _face_cols(p, "east"))
    corners = {(x0, z0), (x0, z1), (x1, z0), (x1, z1)}
    if w.get("open"):
        sp = int(w.get("post_spacing", 4))
        posts = {c for c in perim if c in corners or ((c[0] - x0) % sp == 0 and c[1] in (z0, z1))
                 or ((c[1] - z0) % sp == 0 and c[0] in (x0, x1))}
        for x, z in sorted(posts):
            for dy in range(1, h + 1):
                blocks.append([x, dy, z, w["post"]])
        for x, z in sorted(perim - posts):         # a plate along the top of the open sides, on which the roof sits
            blocks.append([x, h, z, w.get("plate", w["post"])])
    else:
        for x, z in sorted(perim):
            for dy in range(1, h + 1):
                if (x, z) in corners and w.get("corners"):
                    st = w["corners"]
                elif dy == 1 and w.get("base"):
                    st = w["base"]
                elif dy == h and w.get("plate"):
                    st = w["plate"]
                else:
                    st = w["block"]
                blocks.append([x, dy, z, st])
    top = _roof(p, blocks)
    for o in p.get("openings") or []:
        cols = _opening_cols(p, o)
        oh = int(o.get("height", 3))
        for x, z in cols:
            for dy in range(1, oh + 1):
                blocks.append([x, dy, z, "minecraft:air"])
        if o.get("door"):
            for j, (x, z) in enumerate(cols):
                hinge = "left" if j % 2 == 0 else "right"
                for dy, half in ((1, "lower"), (2, "upper")):
                    blocks.append([x, dy, z, "%s[facing=%s,half=%s,hinge=%s,open=false,powered=false]"
                                   % (o["door"], o["face"], half, hinge)])
    for o in p.get("windows") or []:
        for x, z in _opening_cols(p, o):
            for dy in range(int(o.get("dy", 2)), int(o.get("dy", 2)) + int(o.get("height", 1))):
                blocks.append([x, dy, z, o.get("block", "minecraft:glass_pane")])
    hung = []
    bm = p.get("beams")
    if bm:
        along_x = p["roof"]["axis"] == "x"          # beams cross the short span, under the ridge's direction
        rng = range(x0 + 1, x1) if along_x else range(z0 + 1, z1)
        for i in rng:
            if (i - (x0 if along_x else z0)) % int(bm["every"]):
                continue
            if along_x:
                for z in range(z0 + 1, z1):
                    blocks.append([i, h, z, "%s[axis=z]" % bm["block"]])
                if bm.get("lamp"):
                    hung.append([i, h - 1, (z0 + z1) // 2, "minecraft:lantern[hanging=true,waterlogged=false]"])
            else:
                for x in range(x0 + 1, x1):
                    blocks.append([x, h, i, "%s[axis=x]" % bm["block"]])
                if bm.get("lamp"):
                    hung.append([(x0 + x1) // 2, h - 1, i, "minecraft:lantern[hanging=true,waterlogged=false]"])
    blocks += [list(b) for b in p.get("interior") or []]
    hung += [list(b) for b in p.get("hung") or []]
    return {"kind": "structure", "name": p["name"], "footprint": [x0, z0, x1, z1], "foundation": p["foundation"],
            "clear_up": max(int(p.get("clear_up", 0)), top + 2), "fills": fills + [list(f) for f in p.get("fills") or []],
            "blocks": blocks, "hung": hung}


def expand_silo(p):
    """A `silo` -> a structure piece: a round wall `r` from its centre, banded, a door gap, a stepped cone roof."""
    cx, cz = p["centre"]
    r, h = int(p["r"]), int(p["height"])
    fp = [cx - r, cz - r, cx + r, cz + r]
    blocks, fills = [], []
    ring = [(dx, dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1) if abs(math.hypot(dx, dz) - r) < 0.5]
    disc = [(dx, dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1) if math.hypot(dx, dz) <= r + 0.25]
    for dx, dz in disc:
        blocks.append([cx + dx, 0, cz + dz, p["floor"]])
    for dy in range(1, h + 1):
        st = p["band"] if dy == 1 or dy % int(p["band_every"]) == 0 else p["wall"]
        for dx, dz in ring:
            blocks.append([cx + dx, dy, cz + dz, st])
    k = 0
    while r - k >= 0:
        rr = r - k
        for dx in range(-rr, rr + 1):
            for dz in range(-rr, rr + 1):
                if math.hypot(dx, dz) <= rr + 0.25:
                    blocks.append([cx + dx, h + 1 + k, cz + dz, p["roof"]])
        k += 1
    top = h + k
    fx, fz = FACES[p["door"]]
    for dy in (1, 2):
        blocks.append([cx + fx * r, dy, cz + fz * r, "minecraft:air"])
    blocks += [list(b) for b in p.get("interior") or []]
    return {"kind": "structure", "name": p["name"], "footprint": fp, "foundation": p["foundation"],
            "clear_up": top + 2, "fills": fills, "blocks": blocks, "hung": [list(b) for b in p.get("hung") or []]}


def piece_fence(s, p):
    """A rectangle of fence on each column's own ground, gates where named, lanterns on named posts."""
    x0, z0, x1, z1 = p["rect"]
    gates = {tuple(g) for g in p.get("gates") or []}
    skip = {tuple(c) for c in p.get("skip") or []}
    lamps = {tuple(c) for c in p.get("lanterns") or []}
    cols = []
    for x in range(x0, x1 + 1):
        cols += [(x, z0), (x, z1)]
    for z in range(z0 + 1, z1):
        cols += [(x0, z), (x1, z)]
    line = set(cols) - skip
    for dx, dz in cols:
        if (dx, dz) in skip:
            continue
        x, z = s.cx + dx, s.cz + dz
        if not s.dry(x, z):
            raise FarmError("%s %s: (%d, %d) is wet" % (s.r["id"], p["name"], x, z))
        gy = s.g(x, z)
        if (dx, dz) in gates:
            facing = "south" if dz in (z0, z1) else "east"
            s.put(x, gy + 1, z, "%s[facing=%s,in_wall=false,open=false,powered=false]" % (p["gate"], facing))
            top = gy + 1
        else:
            # where the line steps UP to a neighbour, this post rises to the neighbour's rail, so the two rails meet
            # (a one-block step otherwise leaves the upper post with no arm toward the lower: a gap in the line)
            top = max([gy + 1] + [s.g(s.cx + nx, s.cz + nz) + 1 for nx, nz in
                                  ((dx + 1, dz), (dx - 1, dz), (dx, dz + 1), (dx, dz - 1))
                                  if (nx, nz) in line and (nx, nz) not in gates])
            for y in range(gy + 1, top + 1):
                s.put(x, y, z, p["block"])
            if (dx, dz) in lamps:
                s.put(x, top + 1, z, "minecraft:lantern[hanging=false,waterlogged=false]")
        s.clear_col(x, z, gy + 1, top + 2)
    if not gates <= set(cols):
        raise FarmError("%s %s: a gate %s is not on the fence line" % (s.r["id"], p["name"], sorted(gates - set(cols))))


def piece_field(s, p):
    """Crop rows on farmland, on each column's own ground (the ground's top block becomes farmland, the crop stands
    on it): row i (along `rows`) takes pattern[i % len], a crop state or "path" (a walk between beds)."""
    x0, z0, x1, z1 = p["rect"]
    pat = p["pattern"]
    for dx in range(x0, x1 + 1):
        for dz in range(z0, z1 + 1):
            i = (dz - z0) if p["rows"] == "x" else (dx - x0)
            what = pat[i % len(pat)]
            x, z = s.cx + dx, s.cz + dz
            if not s.dry(x, z):
                raise FarmError("%s %s: (%d, %d) is wet" % (s.r["id"], p["name"], x, z))
            gy = s.g(x, z)
            if what == "path":
                s.put(x, gy, z, p["path"])
            else:
                s.put(x, gy, z, p["farmland"])
                s.put(x, gy + 1, z, what)
            s.clear_col(x, z, gy + 1, gy + 2)


def piece_scatter(s, p):
    """One small object (blocks on their own column's ground) at each of `ats`."""
    for at in p["ats"]:
        SR.piece_ground_blocks(s, {"name": p["name"], "blocks": p.get("blocks"), "hung": p.get("hung")}, at=tuple(at))


# ------------------------------------------------------------------ connections


FENCE_LIKE = ("_fence",)
PANE_LIKE = ("glass_pane", "iron_bars")
NOT_FULL = ("stairs", "slab", "fence", "wall", "pane", "bars", "door", "sign", "lantern", "carpet", "farmland",
            "dirt_path", "torch", "button", "pressure_plate", "chain", "cauldron", "air", "carrots", "potatoes",
            "beetroots", "campfire", "azalea", "moss_carpet", "flower_pot", "grindstone", "anvil", "ladder", "wheat",
            "dandelion", "cornflower")


def _is_fence(b):
    return b.endswith("_fence") and not b.endswith("nether_brick_fence")


def _is_pane(b):
    return b.endswith(PANE_LIKE)


def _full(b):
    return not any(t in b for t in NOT_FULL)


def connect(s):
    """Every fence and pane gets its four connections from what the plan puts beside it (or the heightmap's ground,
    where the plan puts nothing): a fence joins a fence, a gate across its line, or a full block; a pane joins a pane
    or a full block. Written into the state, so the line does not depend on the server's shape updates."""
    allb = dict(s.solid)
    allb.update(s.hung)

    def at(x, y, z):
        v = allb.get((x, y, z))
        if v is not None:
            return v
        return "minecraft:dirt" if s.g(x, z) >= y else None

    for store in (s.solid, s.hung):
        for (x, y, z), st in list(store.items()):
            b = base(st)
            fence, pane = _is_fence(b), _is_pane(b)
            if not (fence or pane):
                continue
            side = {}
            for name, (dx, dz) in FACES.items():
                n = at(x + dx, y, z + dz)
                nb = base(n) if n else None
                ok = False
                if nb:
                    if fence:
                        if _is_fence(nb):
                            ok = True
                        elif nb.endswith("_fence_gate"):
                            f = n.split("facing=")[1].split(",")[0].split("]")[0] if "facing=" in n else "south"
                            ok = (f in ("north", "south")) == (name in ("east", "west"))
                        else:
                            ok = _full(nb)
                    else:
                        ok = _is_pane(nb) or nb.endswith("glass") or _full(nb)
                side[name] = "true" if ok else "false"
            store[(x, y, z)] = "%s[east=%s,north=%s,south=%s,waterlogged=false,west=%s]" % (
                b, side["east"], side["north"], side["south"], side["west"])


# ------------------------------------------------------------------ the plan


def plan(doc, g, wet):
    r = _rec(doc)
    s = SR.Site(doc, r, g, wet)
    for i, p in enumerate(doc["pieces"]):
        k = p["kind"]
        if k == "building":
            SR.piece_structure(s, expand_building(p))
        elif k == "silo":
            SR.piece_structure(s, expand_silo(p))
        elif k == "fence":
            piece_fence(s, p)
        elif k == "field":
            piece_field(s, p)
        elif k == "scatter":
            piece_scatter(s, p)
        elif k == "clearing":
            NR.piece_clearing(s, p)
        elif k == "structure":
            SR.piece_structure(s, p)
        elif k == "surface":
            SR.piece_surface(s, p, i + 1)
        elif k == "ground_blocks":
            SR.piece_ground_blocks(s, p)
        elif k == "ring":
            SR.piece_ring(s, p)
        elif k == "posts":
            SR.piece_posts(s, p)
    connect(s)
    return s


def spot(s, at):
    """[dx, dz, on] -> (x, y, z) feet: on a structure's floor (its piece name) or on the ground ("ground")."""
    return SR.spot(s, at)


def _solid_at(s, x, y, z):
    v = s.hung.get((x, y, z)) or s.solid.get((x, y, z))
    if v is None:
        return s.g(x, z) >= y
    b = base(v)
    return b != "minecraft:air" and not b.endswith(("_carpet", "_sign", "_wall_sign")) and "lantern" not in b


def check_body(s, xyz, size, who):
    """A still animal's body (the jar's hitbox x baseScale) is clear of every solid planned cell: its own column to
    its height, and the eight round it when it is wider than one block. A walking one gets the same at its home."""
    x, y, z = xyz
    w, hgt = float(size["width"]), float(size["height"])
    ring = [(0, 0)] if w <= 1.0 else [(dx, dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)]
    for dx, dz in ring:
        for dy in range(0, max(1, int(math.ceil(hgt)))):
            if _solid_at(s, x + dx, y + dy, z + dz):
                raise FarmError("%s: %s's body (%.2f x %.2f) meets a solid block at %s"
                                % (s.r["id"], who, w, hgt, (x + dx, y + dy, z + dz)))
    under = s.solid.get((x, y - 1, z))
    if (under is None or base(under) == "minecraft:air") and s.g(x, z) != y - 1:
        raise FarmError("%s: %s at %s has nothing under it" % (s.r["id"], who, xyz))


def built(doc, g, wet=None):
    """(site, extra spots (x, y, z), box, {animal id: (x, y, z)}): the whole plan with the NPC and animal checks."""
    import resident_encounters as RE
    wet = wet or RE.Wet(g, [tuple(doc["site"]["centre"])])
    s = plan(doc, g, wet)
    extra = []
    for key in ("farmer", "stand_keeper"):
        n = doc[key]
        xyz = spot(s, n["at"])
        if n["at"][2] == "ground":
            SR.stand_clears(s, xyz)
        SR.check_standing(s, xyz, n["name"])
        extra.append(xyz)
    animals = {}
    pens = {p["name"]: p for p in doc["pieces"] if p["kind"] == "fence"}
    for a in doc["animals"]:
        xyz = spot(s, a["at"])
        if a["at"][2] == "ground":
            SR.stand_clears(s, xyz)
        check_body(s, xyz, doc["species"][a["species"]], a["id"])
        if a["kind"] == "follower":
            pen = pens.get(a["pen"])
            if pen is None:
                raise FarmError("%s: pen %r is not a fence piece" % (a["id"], a["pen"]))
            x0, z0, x1, z1 = pen["rect"]
            m = int(doc["rules"]["follower_pen_margin"])
            dx, dz = a["at"][0], a["at"][1]
            if not (x0 + m <= dx <= x1 - m and z0 + m <= dz <= z1 - m):
                raise FarmError("%s: its home (%d, %d) is not %d inside its pen %s" % (a["id"], dx, dz, m, pen["rect"]))
        animals[a["id"]] = xyz
        extra.append(xyz)
    return s, extra, SR.box_of(s, extra), animals


# ------------------------------------------------------------------ the siting rules (the builder's guards)


def own_ids(doc):
    rec = doc["records"]
    return {rec["npc_seat"], rec["stall"], rec["conversation"], rec["quest"]}


def authored_points(doc):
    """Every x/z another data file authors (tools/southern_residents.py authored_points, called), this file skipped
    whole and this farm's own records in the shared files (the seat, the stall) skipped by id."""
    shim = {"residents": [{"records": {"quest": i}} for i in sorted(own_ids(doc))]}
    return SR.authored_points(shim, own_file=DATA)


def keep_out_boxes(doc):
    out = []
    fs = jload("far_south.json")["rules"]["keep_out_box"]
    out.append((fs["box"], "data/far_south.json rules.keep_out_box (the Rift's southern arms and the Mega field)"))
    for k in doc["rules"]["keep_out"]:
        out.append((k["box"], k["why"]))
    return out


def written_cols(s, extra):
    cols = set(s.cols) | {(e[0], e[2]) for e in extra}
    for c in s.clears:
        cols |= {(x, z) for x in range(c[0], c[3] + 1) for z in (c[2], c[5])}
        cols |= {(x, z) for z in range(c[2], c[5] + 1) for x in (c[0], c[3])}
    return cols


def siting(doc, s, extra, animals, pts=None):
    import numpy as np
    rules = doc["rules"]
    probs = []
    pts = authored_points(doc) if pts is None else pts
    cols = written_cols(s, extra)
    P = np.array([(a, b) for a, b, _f in pts], float)
    F = [f for _a, _b, f in pts]
    C = np.array(sorted(cols), float)
    best = (1e9, None, None)
    for i in range(0, len(C), 256):
        blk = C[i:i + 256]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] < best[0]:
            best = (float(d[j]), tuple(blk[j[0]]), F[j[1]])
    m = rules["authored_clearance"]
    if best[0] < m:
        probs.append("(%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                     % (best[1][0], best[1][1], best[0], best[2], m))
    cprobs, cbest = SR.corridor_check(doc["id"], cols, m)
    probs += cprobs
    for t in jload("towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            probs.append("within %d of town %s's footprint" % (m, t["id"]))
    for k, zone in jload("rift_zones.json")["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                probs.append("inside Rift zone %s" % k)
                break
    for (kx0, kz0, kx1, kz1), why in keep_out_boxes(doc):
        if any(kx0 <= x <= kx1 and kz0 <= z <= kz1 for x, z in cols):
            probs.append("writes inside the keep-out box %s (%s)" % ([kx0, kz0, kx1, kz1], why))
    paths = np.array([p for pl in jload("route_paths.json")["paths"].values() for p in pl], float)
    cx, cz = doc["site"]["centre"]
    dp = float(np.min(np.hypot(paths[:, 0] - cx, paths[:, 1] - cz)))
    for label, (x, z) in [("the centre", (cx, cz))] + [(doc[k]["name"], (e[0], e[2])) for k, e in
                                                       zip(("farmer", "stand_keeper"), extra[:2])]:
        d = float(np.min(np.hypot(paths[:, 0] - x, paths[:, 1] - z)))
        if d < rules["path_clearance"]:
            probs.append("%s is %.0f blocks from a route path (needs %d)" % (label, d, rules["path_clearance"]))
    leash = int(jload("ambient.json")["idle"]["rules"]["follower_leash"])   # the idle keeper's own leash
    for a in doc["animals"]:
        x, _y, z = animals[a["id"]]
        for b in jload("habitat_blocks.json")["blocks"]:
            if b.get("style") != "activated":
                continue
            d = math.hypot(b["position"]["x"] - x, b["position"]["z"] - z)
            if d < b["activated"]["spawn_range"] + leash:
                probs.append("%s: its leash overlaps Habitat Block %s (%.0f, needs %d)"
                             % (a["id"], b["id"], d, b["activated"]["spawn_range"] + leash))
    sub = SR._sub_of(cx, cz)[0]
    if sub != doc["subregion"]:
        probs.append("the centre is in %s, the record says %s" % (sub, doc["subregion"]))
    grid = jload("world.json")["grid"]
    cs = grid["cell_size"]
    cell = grid["row_labels"][int(cz - grid["origin_z"]) // cs] + grid["column_labels"][int(cx - grid["origin_x"]) // cs]
    if cell != doc["cell"]:
        probs.append("the centre is in cell %s, the record says %s" % (cell, doc["cell"]))
    return probs, {"nearest_authored": best, "corridor": cbest, "path": dp}


def check_records(doc, s, extra, box):
    """The seats other files carry are the ones this plan leaves open: data/npc_seats.json's farmer and
    data/markets.json's stand keeper, and the box the record states."""
    probs = []
    rec = doc["records"]
    far, stand = list(extra[0]), list(extra[1])
    if doc["farmer"].get("feet") != far:
        probs.append("the heightmap puts the farmer at %s, the record says %s" % (far, doc["farmer"].get("feet")))
    if doc["stand_keeper"].get("feet") != stand:
        probs.append("the heightmap puts the stand keeper at %s, the record says %s" % (stand, doc["stand_keeper"].get("feet")))
    seats = {x["id"]: x for x in jload("npc_seats.json")["seats"]}
    seat = seats.get(rec["npc_seat"])
    if seat is None:
        probs.append("data/npc_seats.json has no seat %s" % rec["npc_seat"])
    else:
        if seat.get("at") != far:
            probs.append("data/npc_seats.json %s stands at %s, the plan gives %s" % (rec["npc_seat"], seat.get("at"), far))
        if seat.get("yaw") != doc["farmer"]["yaw"] or seat.get("conversation") != rec["conversation"]:
            probs.append("data/npc_seats.json %s: yaw or conversation differ from this record" % rec["npc_seat"])
    stalls = {x["id"]: x for x in jload("markets.json").get("stalls") or []}
    st = stalls.get(rec["stall"])
    if st is None:
        probs.append("data/markets.json has no stall %s" % rec["stall"])
    else:
        if st.get("at") != stand or st.get("yaw") != doc["stand_keeper"]["yaw"] or st.get("town") != TOWN:
            probs.append("data/markets.json %s: at %s yaw %s town %s, the plan gives %s yaw %s town %s"
                         % (rec["stall"], st.get("at"), st.get("yaw"), st.get("town"), stand,
                            doc["stand_keeper"]["yaw"], TOWN))
    if math.dist(far, stand) < float(doc["rules"]["npc_gap"]):
        probs.append("the farmer and the stand keeper are %.1f apart (needs %s)" % (math.dist(far, stand), doc["rules"]["npc_gap"]))
    if list(box) != doc.get("bbox"):
        probs.append("the writes' box is %s, the record's bbox %s" % (list(box), doc.get("bbox")))
    return probs


def check_blocks(doc, s):
    """No spawn condition (data/spawn_blocks.json) unless the record allows it (blocks.spawn_conditions_allowed) AND a
    data/spawn_block_policy.json whitelist entry whose scope names this place lists it (the scope rule,
    tests/test_system_contracts.py C4; tools/apricorn_farm.py's form)."""
    spawn = set(jload("spawn_blocks.json")["blocks"])
    written = {base(v) for v in list(s.solid.values()) + list(s.hung.values())}
    allowed = set(doc["blocks"].get("spawn_conditions_allowed") or [])
    probs = []
    bad = sorted((written & spawn) - allowed)
    if bad:
        probs.append("writes spawn-condition blocks %s (data/spawn_blocks.json)" % bad)
    white = {b for w in jload("spawn_block_policy.json")["whitelist"] if TOWN in (w.get("scope") or "")
             for b in w.get("blocks") or []}
    unscoped = sorted((written & spawn & allowed) - white)
    if unscoped:
        probs.append("%s: no data/spawn_block_policy.json entry scoped to %s whitelists them" % (unscoped, TOWN))
    for bad_id in ("minecraft:water", "minecraft:chest"):
        if bad_id in written:
            probs.append("writes %s" % bad_id)
    return probs


def check_all(doc, s, extra, box, animals):
    return siting(doc, s, extra, animals)[0] + check_records(doc, s, extra, box) + check_blocks(doc, s)


# ------------------------------------------------------------------ the pack


def files(doc, g, wet=None, check=True):
    s, extra, box, animals = built(doc, g, wet)
    if check:
        probs = check_all(doc, s, extra, box, animals)
        if probs:
            raise FarmError("pokemon_farm: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = doc["build"]
    lines = SR.build_lines(doc, _rec(doc), s, box)
    lines[0] = "# Generated by tools/pokemon_farm.py from data/pokemon_farm.json: %s" % doc["name"]
    lines[1] = lines[1].replace("R9SR", b["step"])
    bad = function_limits.check_lines(lines, "pokemon_farm/build")
    if bad:
        raise FarmError("pokemon_farm/build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    out = {"data/%s/function/%s/build.mcfunction" % (b["namespace"], b["folder"]): "\n".join(lines) + "\n",
           "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                               "Cobblers: Arrow Creeks Farm (tools/pokemon_farm.py)"}}, indent=2) + "\n"}
    return out, (s, extra, box, animals)


# ------------------------------------------------------------------ the re-application and the animals


def _built(doc=None, g=None):
    import ground as G
    doc = doc or load()
    g = g or G.load()
    return doc, g, built(doc, g)


def placement_steps(doc=None, g=None):
    """R9PF, after R9FS and BEFORE R9E: the farm's box held, its build run, released."""
    doc, g, (s, extra, box, animals) = _built(doc, g)
    b = doc["build"]
    hold = "%d %d %d %d" % tuple(box)
    return [("cmd", "forceload add " + hold), ("wait", 3),
            ("fn", "%s:%s/build" % (b["namespace"], b["folder"])), ("cmd", "forceload remove " + hold)]


def yaw_to(ax, az, bx, bz):
    """tools/ambient_idle.py yaw_to's convention: 0 south (+z), 90 west (-x), in 0..360."""
    return round((math.degrees(math.atan2(-(bx - ax), bz - az)) + 360.0) % 360.0, 1)


def idlers(g, rules, kinds_on, doc=None):
    """The farm's animals in tools/ambient_idle.py's idler shape (its place_buneary's): spot centred on the block,
    a still one turned to its `face`, a follower's behaviour list the idle rules' follower list plus its `extra`
    behaviours. A follower with followers switched off (rules.enabled_kinds) is written as a loafer on its home,
    the idle rules' own fallback for a follower with no room."""
    doc = doc or load()
    _doc, _g, (s, extra, box, animals) = _built(doc, g)
    base_follow = list(rules["behaviours"]["follower"])
    out = []
    for a in doc["animals"]:
        kind = a["kind"]
        if kind not in kinds_on:
            if kind == "follower" and "loafer" in kinds_on:
                kind = "loafer"
            else:
                continue
        x, y, z = animals[a["id"]]
        f = a.get("face")
        yaw = yaw_to(x + .5, z + .5, s.cx + f[0] + .5, s.cz + f[1] + .5) if f else 0.0
        rec = {"id": "idle_farm_%s" % a["id"], "town": TOWN, "kind": kind, "species": a["species"],
               "at": [x + 0.5, float(y), z + 0.5], "yaw": yaw, "where": a.get("pen") or a["at"][2],
               "anchor": TOWN, "role": a["role"]}
        if kind == "follower" and a.get("extra_behaviours"):
            rec["behaviours"] = base_follow + [b for b in a["extra_behaviours"] if b not in base_follow]
        out.append(rec)
    return out


# ------------------------------------------------------------------ CLI


def report(doc, g):
    s, extra, box, animals = built(doc, g)
    probs, m = siting(doc, s, extra, animals)
    probs += check_records(doc, s, extra, box) + check_blocks(doc, s)
    na = m["nearest_authored"]
    cx, cz = doc["site"]["centre"]
    sub = SR._sub_of(cx, cz)
    lines = ["%s (%s) centre %s ground y%d, %s tier %s, cell %s; %d blocks, bbox %s"
             % (doc["name"], doc["id"], doc["site"]["centre"], g(cx, cz), sub[0], sub[1], doc["cell"],
                len(s.solid) + len(s.hung), box),
             "nearest authored x/z %.0f (our column %s to data/%s); corridor box %.0f; route path %.0f"
             % (na[0], tuple(int(v) for v in na[1]), na[2], m["corridor"][0], m["path"])]
    for k, v in s.floors.items():
        lines.append("    floor %s: y%s" % (k, v))
    lines.append("    farmer %s, stand keeper %s" % (list(extra[0]), list(extra[1])))
    for a in doc["animals"]:
        lines.append("    %-22s %-10s %-8s %s (%s)" % (a["id"], a["species"], a["kind"], list(animals[a["id"]]), a["role"]))
    for p in probs:
        lines.append("PROBLEM %s" % p)
    lines.append("step %s: %d actions" % (doc["build"]["step"], len(placement_steps(doc, g))))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print the site, the checks and the step; write nothing")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.report:
        print("\n".join(report(doc, g)))
        return 0
    written, (s, extra, box, animals) = files(doc, g)
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in written.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    n = sum(1 for rel, t in written.items() if rel.endswith("/build.mcfunction")
            for l in t.splitlines() if l and not l.startswith("#"))
    print("pokemon_farm: %d files -> %s (%d blocks, %d animals, build: %d commands)"
          % (len(written), out, len(s.solid) + len(s.hung), len(animals), n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
