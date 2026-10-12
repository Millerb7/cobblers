#!/usr/bin/env python
"""Shrines in the Route 1 maze forest's glades: a legendary touch for a first route, as datapack functions.

The owner (2026-10-12): "We need to add some shrines or legendary stuff to the starter forest in those clearings."
Route 1's maze forest (tools/maze_forest.py) opens into the sapling clearing and the mansion clearing, both left alone
(the sleeping Celebi, data/sapling_celebi.json; the Gastly mansion), three glades where the braids rejoin (r10-11) and
three secret glades at the ends of the hidden squeeze paths (r8-9). Each of those six gets one small shrine, authored in
data/maze_shrines.json and written as one function, `cobblers:maze_shrines/<id>`, in the pack `cobblers_maze_shrines`:

  stele         the three glades. A mossy stone-brick stele, three wide, with two carved tablets (wall signs), an offering
                bowl (a cauldron), a potted fern and flower, a lantern on a post, vines up its back; and a barrel at its
                foot that is the find's scenery (data/rewards.json r1_glade_*: three early consumables, once per
                player, by the same advancement mechanism as the old mine's finds, ADR-002). Each tablet names one of
                the lake spirits and says, in a line or two, where it sleeps in this world
  old_shrine    the three secret glades. The same idea, older: five wide, cracked and mossed, candles for light, vines
                over everything, one corner fallen. Their tablets speak of Celebi (the forest's own guardian, asleep in
                the sapling), Tapu Bulu and Tornadus. The find in each is the barrel tools/route_events.py already puts at
                the glade's heart (r1_fern_glade, r1_west_hollow, r1_north_ring); this adds no second reward

Every hint is true: a tablet's `legendary` names an encounter of data/legendaries.json, whose species, site and status
tools/maze_shrines_audit.py reads back, and a direction word is checked against the bearing from the glade to that
encounter's mouth or portal.

Where a shrine stands (refused, naming the shrine and the reason, when any written column):
  - lies outside the glade's disc less half a block (the glades are the openings tools/maze_forest.py CLEARINGS cuts);
  - is within `path_clearance` of a corridor's walkable edge (every NETWORK corridor, the hidden squeeze paths and the
    3-wide dead ends included): the path and the walk line stay open;
  - is within `post_clearance` of a lantern post the forest sets at a fork (maze_forest.path_dressing);
  - lies in the trigger box of a find route_events.py already placed in the glade;
  - stands on ground that varies by more than the piece allows (the heightmap, rounded: tools/ground.py, never a world).
  The pieces write only air-clearing of their own columns and their own blocks, and nothing is a spawn-condition block
  (data/spawn_blocks.json). Lighting is a lantern on a post or lit candles, never a light block.

  python tools/maze_shrines.py build   [--source-root <root>] [--out DIR]     # the pack, into build/datapacks
  python tools/maze_shrines.py records [--write] [--source-root <root>]       # data/rewards.json r1_glade_* vs the build
  python tools/maze_shrines.py probes  [--write] [--source-root <root>]       # presence probes in data/world_probes.json
  python tools/maze_shrines.py fit <glade> [--size 3|5] [--source-root <root>] # candidate sites (writes nothing)
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)

import function_limits  # noqa: E402
import maze_forest as MF  # noqa: E402
from town_dressing import _runs, block_name, h32, turn_state, turn_xz  # noqa: E402

DATA = ROOT / "data" / "maze_shrines.json"
REWARDS = ROOT / "data" / "rewards.json"
PACK_NAME = "cobblers_maze_shrines"
FOLDER = "maze_shrines"
ID = re.compile(r"^[a-z0-9_]+$")
DIRS = ("north", "east", "south", "west")

STONE = "minecraft:stone_bricks"
MOSSY = "minecraft:mossy_stone_bricks"
CRACKED = "minecraft:cracked_stone_bricks"
CHISELED = "minecraft:chiseled_stone_bricks"
MCOB = "minecraft:mossy_cobblestone"
SLAB = "minecraft:stone_brick_slab[type=bottom]"
MSLAB = "minecraft:mossy_stone_brick_slab[type=bottom]"
CARPET = "minecraft:moss_carpet"
SIGN = "minecraft:spruce_wall_sign[facing=north,waterlogged=false]"
BARREL = "minecraft:barrel[facing=up,open=false]"
VINE = "minecraft:vine[north=true]"
RELIEF = 1                                   # the ground under a piece may differ by this much


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------------ the pieces
def sign_nbt(lines):
    """The block-entity part of a waxed wall sign: four lines, each a JSON text component in a single-quoted string."""
    q = ",".join("'%s'" % json.dumps(t, ensure_ascii=False).replace("'", "\\'") for t in (list(lines) + [""] * 4)[:4])
    return "{front_text:{messages:[%s]},is_waxed:1b}" % q


def stele(spec, h):
    """The glade stele: [(x, dy, z, state, nbt)], local x lateral, z depth (front at z 0), dy from the floor."""
    p = []
    put = lambda x, dy, z, s, n="": p.append((x, dy, z, s, n))  # noqa: E731
    put(-1, 0, 2, MCOB)
    put(0, 0, 2, MOSSY)
    put(1, 0, 2, MCOB)
    put(0, 1, 2, STONE if h(1) % 3 else MOSSY)
    put(0, 2, 2, CHISELED)                                  # the glyph the upper tablet hangs on
    put(0, 3, 2, SLAB)
    put(-1, 1, 2, SLAB)
    put(1, 1, 2, "minecraft:oak_fence")                     # the post: the forest's own lantern-on-a-post
    put(1, 2, 2, "minecraft:lantern[hanging=false]")
    put(0, 1, 1, SIGN, sign_nbt(spec["signs"]["lower"]))
    put(0, 2, 1, SIGN, sign_nbt(spec["signs"]["upper"]))
    put(0, 0, 1, "minecraft:cauldron")                      # the offering bowl
    put(-1, 0, 1, "minecraft:mossy_cobblestone_slab[type=bottom]")
    put(1, 0, 1, "minecraft:potted_fern")
    put(-1, 0, 0, "minecraft:potted_azure_bluet")
    put(0, 0, 0, CARPET)
    put(1, 0, 0, BARREL)                                    # the find's scenery (data/rewards.json r1_glade_*)
    for dy in range(0, 3):                                  # vines up the back, from the ground
        put(0, dy, 3, VINE)
    if h(5) % 2:
        put(-1, 0, 3, VINE)
    return p


def old_shrine(spec, h):
    """The secret glades' older shrine, five wide: cracked and mossed, candles for light, vines, a fallen corner."""
    p = []
    put = lambda x, dy, z, s, n="": p.append((x, dy, z, s, n))  # noqa: E731
    wall = {}                                               # (x, dy) of the back wall's blocks, for the vines

    def wput(x, dy, state):
        wall[(x, dy)] = state
        put(x, dy, 2, state)

    for x in range(-2, 3):
        wput(x, 0, MOSSY if x == 0 or h(x, 0) % 2 else MCOB)
    wput(-2, 1, CRACKED if h(1) % 2 else MOSSY)
    wput(-1, 1, MOSSY if h(2) % 2 else STONE)
    wput(0, 1, CHISELED)
    wput(1, 1, STONE if h(3) % 2 else MOSSY)
    wput(2, 1, CRACKED)
    wput(0, 2, MOSSY)
    wput(1, 2, MSLAB)
    wput(2, 2, MOSSY)
    wput(0, 3, SLAB)                                        # x -2 and -1 above the second course: fallen
    put(-1, 0, 1, MOSSY)                                    # the plinths the tablets hang above
    put(1, 0, 1, MOSSY)
    put(-1, 1, 1, SIGN, sign_nbt(spec["signs"]["upper"]))
    put(1, 1, 1, SIGN, sign_nbt(spec["signs"]["lower"]))
    put(0, 0, 1, "minecraft:cauldron")                      # the offering bowl
    put(0, 0, 0, CARPET)
    put(-2, 0, 0, MCOB)
    put(-2, 1, 0, "minecraft:candle[candles=3,lit=true]")
    put(2, 0, 0, MCOB)
    put(2, 1, 0, "minecraft:candle[candles=2,lit=true]")
    for x in (-1, 1):
        if h(x, 7) % 2:
            put(x, 0, 0, CARPET)
    put(-2, 0, 1, "minecraft:potted_fern" if h(8) % 2 else CARPET)
    put(2, 0, 1, CARPET)
    for x in range(-2, 3):                                  # vines over the back, from the ground up as far as it stands
        top = 1 + h(x, 9) % 3
        for dy in range(0, top):
            if (x, dy) in wall:
                put(x, dy, 3, VINE)
    return p


KINDS = {"stele": (stele, 3), "old_shrine": (old_shrine, 5)}


# -------------------------------------------------------------------------------------------------------- the plan
def glades():
    return {c["id"]: c for c in MF.CLEARINGS}


def corridor_clearance(x, z):
    """Blocks from (x, z) to the nearest corridor's walkable edge (negative inside one): the plan's NETWORK."""
    best = 1e9
    for c in MF.NETWORK:
        d = MF.polyline_distance((1, 1), (x, z, x, z), c["nodes"])[0, 0] - c["width"] / 2.0
        best = min(best, d)
    return best


def fork_posts(ground_box):
    """(x, z) of every lantern post the forest sets (maze_forest.path_dressing): the fork markers and the mouth's."""
    tiles, _ = MF.path_dressing(ground_box, MF.BOX)
    out = []
    pat = re.compile(r"^setblock (-?\d+) -?\d+ (-?\d+) minecraft:oak_fence")
    for cmds in tiles.values():
        for c in cmds:
            m = pat.match(c)
            if m:
                out.append((int(m.group(1)), int(m.group(2))))
    return out


def find_boxes(rewards):
    """{record id: (x0, z0, x1, z1)} the trigger boxes of the finds in the maze forest's glades that already exist."""
    out = {}
    for r in rewards["rewards"]:
        if r.get("kind") == "cache" and r["id"] in ("r1_fern_glade", "r1_west_hollow", "r1_north_ring"):
            lo, hi = r["trigger"]["min"], r["trigger"]["max"]
            out[r["id"]] = (lo[0], lo[2], hi[0], hi[2])
    return out


def world_blocks(spec, ground):
    """[(x, y, z, state, nbt)] for one shrine seated on the heightmap's ground, plus its floor y."""
    kind = spec["kind"]
    if kind not in KINDS:
        raise SystemExit("%s: unknown shrine kind %r (known: %s)" % (spec["id"], kind, ", ".join(sorted(KINDS))))
    ox, oz = spec["at"]
    facing = spec["facing"]
    if facing not in DIRS:
        raise SystemExit("%s: facing %r is not one of %s" % (spec["id"], facing, DIRS))
    build, _width = KINDS[kind]
    local = build(spec, lambda *v: h32(ox, oz, *v))
    last = {}
    for x, dy, z, s, n in local:
        last[(x, dy, z)] = (s, n)
    world = []
    for (x, dy, z), (s, n) in last.items():
        tx, tz = turn_xz(x, z, facing)
        world.append((ox + tx, dy, oz + tz, turn_state(s, facing), n))
    cols = sorted({(x, z) for x, _dy, z, _s, _n in world})
    g = {c: ground(*c) for c in cols}
    relief = max(g.values()) - min(g.values())
    if relief > RELIEF:
        raise SystemExit("%s: the ground under it varies by %d blocks (a piece allows %d): move it"
                         % (spec["id"], relief, RELIEF))
    floor = max(g.values()) + 1
    out = [(x, floor + dy, z, s, n) for x, dy, z, s, n in world]
    # a column that stands lower than the highest ground gets a foundation course of its base block up to the floor
    foot = {}
    for x, dy, z, _s, _n in world:
        foot[(x, z)] = min(foot.get((x, z), dy), dy)
    for (x, z), low in foot.items():
        if low <= 0:
            for y in range(g[(x, z)] + 1, floor + low):
                out.append((x, y, z, MCOB, ""))
    return out, floor


def check_site(spec, blocks, rules, glade, posts, boxes):
    """Reasons the site is not free: [] when it is."""
    why = []
    cx, cz = glade["at"]
    cols = sorted({(x, z) for x, _y, z, _s, _n in blocks})
    for x, z in cols:
        d = math.hypot(x - cx, z - cz)
        if d > glade["r"] - rules["disc_margin"]:
            why.append("(%d, %d) is %.1f from the glade's centre; the glade is r%d" % (x, z, d, glade["r"]))
        c = corridor_clearance(x, z)
        if c < rules["path_clearance"]:
            why.append("(%d, %d) is %.1f from a corridor's walkable edge (needs %s)" % (x, z, c, rules["path_clearance"]))
        for px, pz in posts:
            if max(abs(x - px), abs(z - pz)) <= rules["post_clearance"]:
                why.append("(%d, %d) is beside the lantern post at (%d, %d)" % (x, z, px, pz))
        for rid, (bx0, bz0, bx1, bz1) in boxes.items():
            if bx0 <= x <= bx1 and bz0 <= z <= bz1:
                why.append("(%d, %d) is inside the trigger box of %s" % (x, z, rid))
    return why


def reward_geometry(spec, blocks):
    """(container [x, y, z], trigger {min, max}) for a glade stele's own find: the barrel and a 3 by 3 box round it."""
    bar = [(x, y, z) for x, y, z, s, _n in blocks if block_name(s) == "minecraft:barrel"]
    if len(bar) != 1:
        raise SystemExit("%s: a stele has exactly one barrel, this has %d" % (spec["id"], len(bar)))
    x, y, z = bar[0]
    return [x, y, z], {"min": [x - 1, y - 1, z - 1], "max": [x + 1, y + 2, z + 1]}


def commands_for(spec, blocks, floor):
    cmds = ["# Generated by tools/maze_shrines.py from data/maze_shrines.json (%s). Re-run to rebuild." % spec["id"],
            "# %s: %s in the %s glade (%s)" % (spec["id"], spec["kind"], spec["glade"], spec["name"])]
    cols = sorted({(x, z) for x, _y, z, _s, _n in blocks})
    ys = [y for _x, y, _z, _s, _n in blocks]
    for x0, x1, z in _runs(cols):
        cmds.append("fill %d %d %d %d %d %d minecraft:air replace #minecraft:replaceable" % (x0, floor - 1, z, x1, max(ys) + 1, z))
        for tag in ("#minecraft:logs", "#minecraft:leaves"):
            cmds.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, floor, z, x1, max(ys) + 4, z, tag))
    for x, y, z, s, n in sorted(blocks, key=lambda b: (b[1], b[0], b[2])):
        cmds.append("setblock %d %d %d %s%s" % (x, y, z, s, n))
    return cmds


def validate_data(data, legendaries=None):
    problems, seen = [], set()
    for s in data.get("shrines") or []:
        sid = s.get("id", "?")
        if not ID.match(sid) or sid in seen:
            problems.append("%s: id must be unique lowercase [a-z0-9_]" % sid)
        seen.add(sid)
        for k in ("name", "glade", "kind", "at", "facing", "legendary", "signs", "why"):
            if k not in s:
                problems.append("%s: missing %r" % (sid, k))
        if s.get("glade") not in glades() or s.get("glade") in ("sapling", "mansion"):
            problems.append("%s: glade %r is not one of the forest's glades or secret glades" % (sid, s.get("glade")))
        if s.get("kind") == "stele" and not s.get("reward"):
            problems.append("%s: a stele carries its own find: name its data/rewards.json record" % sid)
        if s.get("kind") == "old_shrine" and not s.get("existing_find"):
            problems.append("%s: an old shrine stands over the find route_events.py placed: name it" % sid)
    if not data.get("shrines"):
        problems.append("data/maze_shrines.json lists no shrine")
    return problems


def sites(a):
    import ground as G
    data = load(DATA)
    problems = validate_data(data)
    if problems:
        raise SystemExit("data/maze_shrines.json: " + "; ".join(problems))
    g = G.Ground(a.source_root)
    glade_map = glades()
    posts = fork_posts(G.load(a.source_root).box(*MF.BOX))
    boxes = find_boxes(load(REWARDS))
    allowed = set(data["blocks"]["ids"])
    out, taken = [], {}
    for spec in data["shrines"]:
        blocks, floor = world_blocks(spec, g)
        bad = sorted({block_name(s) for _x, _y, _z, s, _n in blocks} - allowed)
        if bad:
            raise SystemExit("%s: blocks not in data/maze_shrines.json `blocks`: %s" % (spec["id"], bad))
        why = check_site(spec, blocks, data["rules"], glade_map[spec["glade"]], posts, boxes)
        if why:
            raise SystemExit("%s: not free: %s" % (spec["id"], "; ".join(why[:4])))
        for c in {(x, z) for x, _y, z, _s, _n in blocks}:
            if c in taken:
                raise SystemExit("%s overlaps %s at %s" % (spec["id"], taken[c], c))
            taken[c] = spec["id"]
        out.append((spec, blocks, floor))
    return data, out


# --------------------------------------------------------------------------------------------------------- commands
def build(a):
    data, built = sites(a)
    pack = Path(a.out) if a.out else ROOT / "build" / "datapacks" / PACK_NAME
    funcs = pack / "data" / "cobblers" / "function" / FOLDER
    if pack.exists():
        shutil.rmtree(pack)
    funcs.mkdir(parents=True)
    (pack / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                      "Cobblers: shrines in the Route 1 maze forest's glades (tools/maze_shrines.py)"}},
                                      indent=2) + "\n", encoding="utf-8")
    drift = record_drift(data, built)
    if drift:
        raise SystemExit("data/rewards.json disagrees with the build (run: python tools/maze_shrines.py records --write): "
                         + "; ".join(drift))
    names = []
    for spec, blocks, floor in built:
        cmds = function_limits.ensure_loaded(commands_for(spec, blocks, floor))
        refused = function_limits.check_lines(cmds, spec["id"])
        if refused:
            raise SystemExit("%s: %d command(s) the server would refuse: %s" % (spec["id"], len(refused), refused[:3]))
        (funcs / ("%s.mcfunction" % spec["id"])).write_text("\n".join(cmds) + "\n", encoding="utf-8")
        names.append(spec["id"])
        xs, zs = [b[0] for b in blocks], [b[2] for b in blocks]
        print("%-16s %-10s %-14s at %5d %5d y%d  %3d blocks, %3d commands"
              % (spec["id"], spec["kind"], spec["glade"], spec["at"][0], spec["at"][1], floor, len(blocks), len(cmds)))
    (funcs / "index.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    print("wrote", pack)
    return 0


def record_drift(data, built):
    """How data/rewards.json's r1_glade_* records differ from the barrels and boxes this build puts down."""
    recs = {r["id"]: r for r in load(REWARDS)["rewards"]}
    out = []
    for spec, blocks, _floor in built:
        rid = spec.get("reward")
        if not rid:
            continue
        r = recs.get(rid)
        if r is None:
            out.append("%s: no record %s" % (spec["id"], rid))
            continue
        container, trigger = reward_geometry(spec, blocks)
        if r.get("container", {}).get("at") != container or r.get("trigger") != trigger:
            out.append("%s: container/trigger differ from the build's %s %s" % (rid, container, trigger))
    return out


def records(a):
    data, built = sites(a)
    drift = record_drift(data, built)
    if not a.write:
        for m in drift:
            print("DRIFT", m)
        print("rewards records: %s" % ("in step with the build" if not drift else "%d differ (--write patches them)" % len(drift)))
        return 1 if drift else 0
    doc = load(REWARDS)
    by = {r["id"]: r for r in doc["rewards"]}
    for spec, blocks, _floor in built:
        rid = spec.get("reward")
        if not rid or rid not in by:
            continue
        container, trigger = reward_geometry(spec, blocks)
        by[rid]["container"] = {"block": "minecraft:barrel", "at": container}
        by[rid]["trigger"] = trigger
    REWARDS.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("patched the container and trigger of %d records" % sum(1 for s, _b, _f in built if s.get("reward")))
    return 0


PROBES = ROOT / "data" / "world_probes.json"


def probes(a):
    """{"maze_shrines": [probe]} in data/world_probes.json's shape (tools/presence_audit.py --only extra): per shrine its
    offering bowl and its glyph block, and for a stele its barrel, each at the position this build writes."""
    _data, built = sites(a)
    out = []
    for spec, blocks, _floor in built:
        for name in ("minecraft:cauldron", "minecraft:chiseled_stone_bricks", "minecraft:barrel"):
            for x, y, z, s, _n in blocks:
                if block_name(s) == name:
                    out.append({"what": "%s: %s" % (spec["id"], name), "block": [x, y, z, name], "expect": True})
                    break
    doc = load(PROBES)
    have = doc["places"].get("maze_shrines")
    if not a.write:
        print("probes: %d for %d shrines; data/world_probes.json %s" % (
            len(out), len(built), "is in step" if have == out else "differs (--write patches it)"))
        return 0 if have == out else 1
    doc["places"]["maze_shrines"] = out
    PROBES.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("wrote %d probes into data/world_probes.json places.maze_shrines" % len(out))
    return 0


def fit(a):
    import ground as G
    data = load(DATA)
    g = G.Ground(a.source_root)
    glade = glades()[a.glade]
    posts = fork_posts(G.load(a.source_root).box(*MF.BOX))
    boxes = find_boxes(load(REWARDS))
    kind = "stele" if a.size == 3 else "old_shrine"
    cx, cz = glade["at"]
    stub = {"signs": {"upper": [""], "lower": [""]}}
    found = []
    for ox in range(cx - glade["r"], cx + glade["r"] + 1):
        for oz in range(cz - glade["r"], cz + glade["r"] + 1):
            for f in DIRS:
                spec = dict(stub, id="fit", kind=kind, at=[ox, oz], facing=f, glade=a.glade)
                try:
                    blocks, _floor = world_blocks(spec, g)
                except SystemExit:
                    continue
                if check_site(spec, blocks, data["rules"], glade, posts, boxes):
                    continue
                clr = min(corridor_clearance(x, z) for x, _y, z, _s, _n in blocks)
                fx, fz = turn_xz(0, -3, f)               # three in front of the shrine
                toward = math.hypot(ox + fx - cx, oz + fz - cz) < math.hypot(ox - cx, oz - cz)
                found.append((not toward, -round(clr, 1), math.hypot(ox - cx, oz - cz), ox, oz, f))
    found.sort()
    for away, nclr, d, ox, oz, f in found[:a.count]:
        print("at [%d, %d] facing %s: %.1f from the centre, %.1f clear of a corridor, front %s the centre"
              % (ox, oz, f, d, -nclr, "away from" if away else "towards"))
    if not found:
        print("nothing fits in %s" % a.glade)
        return 1
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("build")
    q.add_argument("--out", default=None)
    q.add_argument("--source-root", default=env_source_root())
    q = sub.add_parser("records")
    q.add_argument("--write", action="store_true")
    q.add_argument("--source-root", default=env_source_root())
    q = sub.add_parser("probes")
    q.add_argument("--write", action="store_true")
    q.add_argument("--source-root", default=env_source_root())
    q = sub.add_parser("fit")
    q.add_argument("glade")
    q.add_argument("--size", type=int, default=3, choices=(3, 5))
    q.add_argument("--count", type=int, default=8)
    q.add_argument("--source-root", default=env_source_root())
    a = p.parse_args(argv)
    return {"build": build, "records": records, "fit": fit, "probes": probes}[a.cmd](a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
