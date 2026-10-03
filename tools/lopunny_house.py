#!/usr/bin/env python
"""The Lopunny superfan's house on the South Pine Isle, from data/lopunny_house.json: a cottage, its Buneary cellar, and
the party check his quest reads.

The owner, 2026-10-02: "add a house at 6950 1360 that is a man who has a dungeon of buneary, hes obsessed with lopunny
and wants one of his own". Every part is an existing, proven piece; nothing here is new machinery:

  the house     vanilla 1.21.1 blocks, seated the repository's way (tools/frostpeak_camp.py, tools/shrines.py): the
                floor on max(ground under the walls) + 1, the statue on max(ground under it) + 1, ground from
                tools/ground.py (the canonical heightmap, rounded), never a world. The columns round it are cleared of
                logs, leaves and replaceable plants first. Lopunny's ears on the ridge, a Lopunny statue in the yard, a
                shrine of banners and candles inside: the obsession is visible from the snowfield.
  the cellar    a 9 by 9 room, 3 high, under the house floor, reached only by a ladder from a trapdoor. Every block of
                it is written, solid or air, including `under_fill` rows of stone beneath its floor, so the Habitat
                Block's spawn box (a cube of spawn_range round the block) holds no air but the room's.
  Buneary       NOT in this pack: an ACTIVATED Habitat Block in data/habitat_blocks.json (placed by
                tools/habitat_blocks.py with every other block, R9E) in the middle of the cellar floor, disguised as
                the floor, and a Habitat pool in data/spawns.json (compiled by tools/compile_spawns.py). The den's
                pattern (tools/ursaluna_cave.py). This pack writes the floor block it sits in, so it must run BEFORE
                R9E: run after, it would write stone bricks over the block.
  Hopgood       NOT in this pack: a conversation in data/dialogue.json and a quest in data/quests.json, compiled with
                every other one into cobblers_dialogue by tools/compile_dialogue.py --all, and placed by R9F from
                data/rewards.json lopunny_superfan (npc_grant), as the Abandoned Cut's digger is.
  the check     a Cobblemon player_tick_pre callback, the water ladder's (tools/blackout_pack.py, EXP-042): once a
                second it tags the player cobblers_lopunny_in_party while a Lopunny is in the party and untags them
                otherwise. The conversation reads the tag (compile_dialogue's player_tag). The two together are
                experiments/EXP-052-lopunny-show.

  python tools/lopunny_house.py build [--source-root R] [--out DIR]   write the pack
  python tools/lopunny_house.py plan  [--source-root R]               print the numbers and the steps; writes nothing

The re-application (tools/reapply.py is not edited here): placement_steps() is the step, to run BEFORE R9E.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "lopunny_house.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_lopunny_house"
SCHEMA = "cobblers.lopunny-house/1"
NS = "cobblers"
FN = "lopunny_house"
PACK_FORMAT = 48  # Minecraft 1.21.1
CALLBACK = "data/cobblemon/callbacks/player_tick_pre/cobblers_lopunny_house.molang"
# how far the clearing reaches over the house floor: the ridge (dy 11), the ears (dy 16) and a tree crown over them
CLEAR_UP = 20
CLEAR_MARGIN = 2
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class HouseError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise HouseError("%s: schema must be %s" % (path, SCHEMA))
    h, c = doc["house"], doc["cellar"]
    if c["interior_half"] != h["half"] - 1:
        raise HouseError("the cellar's walls stand under the house's: interior_half must be house.half - 1")
    if c["air_height"] < 2:
        raise HouseError("a Buneary needs two blocks of air to stand in")
    return doc


def _base(state):
    return state.split("[")[0].split("{")[0]


def wall_sign(facing, lines):
    q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])
    return "minecraft:spruce_wall_sign[facing=%s]{front_text:{messages:[%s]}}" % (facing, q)


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan:
    """Two passes of blocks, {(x, y, z): state}: the structure, then what hangs on it (a sign, a ladder, a lantern, a
    door), so nothing attached is placed before what it is attached to. Doors are their own ordered pairs."""

    def __init__(self, doc, g):
        self.doc, self.g = doc, g
        self.cx, self.cz = doc["site"]["centre"]
        self.solid, self.hung, self.doors = {}, {}, []
        h = doc["house"]["half"]
        self.walls = [(self.cx + lx, self.cz + lz) for lx in range(-h, h + 1) for lz in range(-h, h + 1)]
        self.hf = max(g(x, z) for x, z in self.walls) + 1
        self.allowed = set(doc["blocks"]["ids"])

    def _put(self, into, lx, y, lz, state):
        if _base(state) not in self.allowed:
            raise HouseError("%s is not in data/lopunny_house.json blocks.ids" % _base(state))
        into[(self.cx + lx, y, self.cz + lz)] = state

    def put(self, lx, dy, lz, state):
        self._put(self.solid, lx, self.hf + dy, lz, state)

    def hang(self, lx, dy, lz, state):
        self._put(self.hung, lx, self.hf + dy, lz, state)

    def door(self, lx, dy, lz, facing, hinge="left"):
        for half, d in (("lower", 0), ("upper", 1)):
            st = "minecraft:spruce_door[facing=%s,half=%s,hinge=%s,open=false,powered=false]" % (facing, half, hinge)
            if _base(st) not in self.allowed:
                raise HouseError("spruce_door is not in blocks.ids")
            self.doors.append(((self.cx + lx, self.hf + dy + d, self.cz + lz), st))

    def blocks(self):
        out = dict(self.solid)
        out.update(self.hung)
        out.update(dict(self.doors))
        return out


def cellar(p):
    """The Buneary cellar under the floor: walls, floor, ceiling, air, the stone under it, and its fit-out."""
    doc = p.doc
    n = doc["cellar"]["interior_half"]
    air = doc["cellar"]["air_height"]
    floor = -(air + 2)                      # dy of the floor block: the ceiling is dy -1, the air under it
    b = doc["blocks"]
    for lx in range(-n - 1, n + 2):
        for lz in range(-n - 1, n + 2):
            edge = max(abs(lx), abs(lz)) == n + 1
            for dy in range(floor, 0):
                if edge:
                    p.put(lx, dy, lz, b["cellar_wall"])
                elif dy == floor:
                    p.put(lx, dy, lz, b["cellar_floor"])
                elif dy == -1:
                    p.put(lx, dy, lz, "minecraft:stripped_spruce_log[axis=x]" if lz in (-3, 0, 3)
                          else "minecraft:spruce_planks")
                else:
                    p.put(lx, dy, lz, "minecraft:air")
            if not edge:
                for dy in range(floor - doc["cellar"]["under_fill"], floor):
                    p.put(lx, dy, lz, "minecraft:stone")
    feet = floor + 1
    # bedding along the north wall and the west wall, the carrot stores, a trough
    for lx in (1, 2, 3):
        p.put(lx, feet, -n, "minecraft:hay_block[axis=y]")
    p.put(2, feet + 1, -n, "minecraft:hay_block[axis=y]")
    for lz in (2, 3):
        p.put(-n, feet, lz, "minecraft:hay_block[axis=y]")
    p.put(n, feet, -n, "minecraft:barrel[facing=up,open=false]")
    p.put(n, feet, -n + 1, "minecraft:barrel[facing=west,open=false]")
    p.put(n, feet, n, "minecraft:cauldron")
    # the way down: a ladder on the west wall in the north-west corner, through the ceiling, under the trapdoor
    for dy in range(feet, 0):
        p.hang(-n, dy, -n, "minecraft:ladder[facing=east,waterlogged=false]")
    p.hang(-n, 0, -n, "minecraft:spruce_trapdoor[facing=east,half=top,open=false,powered=false,waterlogged=false]")
    # light: two lanterns hanging from the ceiling (lanterns, never light blocks: docs/STATE.md 'Places are lit as towns')
    for lx, lz in ((-2, -2), (2, 2)):
        p.hang(lx, -2, lz, "minecraft:lantern[hanging=true,waterlogged=false]")
    p.hang(0, feet + 1, n, wall_sign("north", doc["obsession"]["signs"]["cellar"]))
    return floor


def house(p):
    doc = p.doc
    h = doc["house"]["half"]
    top = doc["house"]["wall_height"]
    over = doc["house"]["roof_overhang"]
    n = h - 1
    # the floor: a cobblestone ring under the walls, spruce planks inside
    for lx in range(-h, h + 1):
        for lz in range(-h, h + 1):
            ring = max(abs(lx), abs(lz)) == h
            p.put(lx, 0, lz, "minecraft:cobblestone" if ring else "minecraft:spruce_planks")
    # the walls, and the air of the room
    for lx in range(-h, h + 1):
        for lz in range(-h, h + 1):
            ring = max(abs(lx), abs(lz)) == h
            for dy in range(1, top + 1):
                if not ring:
                    p.put(lx, dy, lz, "minecraft:air")
                elif abs(lx) == h and abs(lz) == h:
                    p.put(lx, dy, lz, "minecraft:stripped_spruce_log[axis=y]")
                elif dy == top:
                    p.put(lx, dy, lz, "minecraft:stripped_spruce_log[axis=%s]" % ("x" if abs(lz) == h else "z"))
                else:
                    p.put(lx, dy, lz, "minecraft:spruce_planks")
    # windows (explicit connections: a pane set by command keeps the state it is given)
    for lx in (-3, 3):
        for lz in (-h, h):
            for dy in (2, 3):
                p.put(lx, dy, lz, "minecraft:glass_pane[east=true,west=true,north=false,south=false,waterlogged=false]")
    for lz in (-2, 2):
        for lx in (-h, h):
            for dy in (2, 3):
                p.put(lx, dy, lz, "minecraft:glass_pane[north=true,south=true,east=false,west=false,waterlogged=false]")
    # the door in the south wall, and its step
    p.put(0, 1, h, "minecraft:air")
    p.put(0, 2, h, "minecraft:air")
    p.door(0, 1, h, "north")
    p.put(0, 0, h + 1, "minecraft:spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]")
    # the roof: a gable whose ridge runs east-west, one stair a row up and in, from the overhang to the ridge
    rise = h + over
    for k in range(0, rise + 1):
        dy = top + 1 + k
        r = rise - k
        for lx in range(-h - over, h + over + 1):
            if r == 0:
                p.put(lx, dy, 0, "minecraft:spruce_planks")
            else:
                p.put(lx, dy, -r, "minecraft:spruce_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]")
                p.put(lx, dy, r, "minecraft:spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]")
        for lz in range(-(r - 1), r):
            for lx in range(-h, h + 1):
                if abs(lx) == h:
                    p.put(lx, dy, lz, "minecraft:spruce_planks")           # the gable ends
                else:
                    p.put(lx, dy, lz, "minecraft:air")
    ridge = top + 1 + rise
    # Lopunny's ears on the ridge: cream at the base, brown, splayed at the tips
    b = doc["blocks"]
    for side in (-1, 1):
        p.put(3 * side, ridge + 1, 0, b["lopunny_cream"])
        p.put(3 * side, ridge + 2, 0, b["lopunny_brown"])
        p.put(3 * side, ridge + 3, 0, b["lopunny_brown"])
        p.put(4 * side, ridge + 4, 0, b["lopunny_brown"])
        p.put(4 * side, ridge + 5, 0, b["lopunny_brown"])
    # a chain from the ridge and a lantern over the room
    for dy in range(ridge - 3, ridge):
        p.hang(0, dy, 0, "minecraft:chain[axis=y,waterlogged=false]")
    p.hang(0, ridge - 4, 0, "minecraft:lantern[hanging=true,waterlogged=false]")
    # --- the room
    # the shrine on the north wall: banners brown, white, brown over a sign, an idol block and two candles
    for lx, colour in ((-2, "brown"), (0, "white"), (2, "brown")):
        p.hang(lx, 3, -n, "minecraft:%s_wall_banner[facing=south]" % colour)
    p.put(0, 1, -n, b["lopunny_brown"])
    p.hang(0, 2, -n, wall_sign("south", doc["obsession"]["signs"]["shrine"]))
    for lx in (-1, 1):
        p.hang(lx, 1, -n, "minecraft:brown_candle[candles=3,lit=true,waterlogged=false]")
    # the bedroll and its nightstand in the north-east corner
    for lz in (-n, -n + 1):
        p.hang(n, 1, lz, "minecraft:red_carpet")
    p.put(n, 1, -n + 2, "minecraft:barrel[facing=up,open=false]")
    p.hang(n, 2, -n + 2, "minecraft:lantern[hanging=false,waterlogged=false]")
    # the east wall: shelves, a bench, a stove, stores
    p.put(n, 1, 0, "minecraft:bookshelf")
    p.put(n, 2, 0, "minecraft:bookshelf")
    p.put(n, 1, 1, "minecraft:crafting_table")
    p.put(n, 1, 2, "minecraft:smoker[facing=west,lit=false]")
    p.put(n, 1, 3, "minecraft:barrel[facing=west,open=false]")
    p.put(n, 1, 4, "minecraft:barrel[facing=up,open=false]")
    # the table and its two chairs, a lantern on it
    p.put(0, 1, 1, "minecraft:spruce_fence[east=false,west=false,north=false,south=false,waterlogged=false]")
    p.hang(0, 2, 1, "minecraft:lantern[hanging=false,waterlogged=false]")
    p.put(-1, 1, 1, "minecraft:spruce_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]")
    p.put(1, 1, 1, "minecraft:spruce_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]")
    # a brown rug before the shrine
    for lx in range(-2, 3):
        for lz in (-2, -1):
            p.hang(lx, 1, lz, "minecraft:brown_carpet")
    # spare bedding by the west wall
    p.put(-n, 1, 1, "minecraft:hay_block[axis=y]")
    p.put(-n, 1, 2, "minecraft:hay_block[axis=y]")
    p.put(-n, 2, 1, "minecraft:hay_block[axis=y]")
    # the door sign outside
    p.hang(-2, 2, h + 1, wall_sign("south", doc["obsession"]["signs"]["door"]))
    return ridge


def yard(p):
    """The path from the step, and the statue: a Lopunny ten blocks tall on a plinth, seated on its own ground."""
    doc = p.doc
    h = doc["house"]["half"]
    b = doc["blocks"]
    for lz in range(h + 2, h + 6):
        x, z = p.cx, p.cz + lz
        p.solid[(x, p.g(x, z), z)] = "minecraft:dirt_path"
    sx, sz = doc["obsession"]["statue"]["at_local"]
    cols = [(p.cx + sx + dx, p.cz + sz + dz) for dx in range(-2, 3) for dz in range(-1, 2)]
    floor = max(p.g(x, z) for x, z in cols) + 1
    brown, cream = b["lopunny_brown"], b["lopunny_cream"]
    shape = []
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            shape.append((dx, 0, dz, "minecraft:polished_andesite"))
    shape += [(-1, 1, 0, cream), (1, 1, 0, cream), (-1, 2, 0, brown), (1, 2, 0, brown)]       # ankles, legs
    shape += [(dx, dy, 0, brown) for dx in (-1, 0, 1) for dy in (3, 4)]                       # hips, body
    shape += [(-2, 3, 0, cream), (2, 3, 0, cream), (-2, 4, 0, brown), (2, 4, 0, brown)]       # wrists, arms
    shape += [(0, 5, 0, brown)]                                                               # the head
    shape += [(-1, 6, 0, cream), (1, 6, 0, cream)]                                            # the ears' fluff
    shape += [(dx, dy, 0, brown) for dx in (-1, 1) for dy in (7, 8)]
    shape += [(-2, 9, 0, brown), (2, 9, 0, brown)]                                            # splayed tips
    for dx, dy, dz, st in shape:
        if _base(st) not in p.allowed:
            raise HouseError("%s is not in blocks.ids" % _base(st))
        p.solid[(p.cx + sx + dx, floor + dy, p.cz + sz + dz)] = st
    # a foundation under the plinth where the ground is lower than its floor
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            x, z = p.cx + sx + dx, p.cz + sz + dz
            for y in range(p.g(x, z) + 1, floor):
                p.solid[(x, y, z)] = "minecraft:cobblestone"
    sign = (p.cx + sx, floor, p.cz + sz + 2)
    p.hung[sign] = wall_sign("south", doc["obsession"]["signs"]["statue"])
    return floor


def plan(doc, g):
    p = Plan(doc, g)
    floor_dy = cellar(p)
    ridge = house(p)
    statue_floor = yard(p)
    h = doc["house"]["half"]
    nx, nz = doc["npc"]["at_local"]
    npc = (p.cx + nx, p.hf + 1, p.cz + nz)
    blocks = p.blocks()
    if blocks.get(npc, "minecraft:air") != "minecraft:air" or blocks.get((npc[0], npc[1] + 1, npc[2]), "minecraft:air") != "minecraft:air":
        raise HouseError("Hopgood's spot %s is not two blocks of air" % (npc,))
    xs = [k[0] for k in blocks]
    zs = [k[2] for k in blocks]
    sx, sz = doc["obsession"]["statue"]["at_local"]
    clear = (min(xs) - CLEAR_MARGIN, min(zs) - CLEAR_MARGIN, max(xs) + CLEAR_MARGIN, max(zs) + CLEAR_MARGIN)
    low = min(g(x, z) for x in range(clear[0], clear[2] + 1) for z in range(clear[1], clear[3] + 1))
    return {"plan": p, "hf": p.hf, "floor_y": p.hf + floor_dy, "ridge_y": p.hf + ridge, "statue_floor": statue_floor,
            "npc": npc, "habitat_block": (p.cx, p.hf + floor_dy, p.cz), "clear": clear,
            "clear_y": (low + 1, p.hf + CLEAR_UP), "blocks": blocks, "half": h}


# ---------------------------------------------------------------------------------------------------------- the pack
def _runs(blocks, top_down=False):
    """setblock and fill lines for {(x, y, z): state}, one fill per run of one state along x, bottom up (or top down:
    a lantern hangs from a chain that is hung itself, so what hangs is written from the top)."""
    out = []
    keys = sorted(blocks, key=lambda k: (-k[1] if top_down else k[1], k[2], k[0]))
    i = 0
    while i < len(keys):
        x, y, z = keys[i]
        st = blocks[keys[i]]
        j = i
        while (j + 1 < len(keys) and keys[j + 1] == (keys[j][0] + 1, y, z) and blocks[keys[j + 1]] == st
               and "{" not in st):
            j += 1
        if j == i:
            out.append("setblock %d %d %d %s" % (x, y, z, st))
        else:
            out.append("fill %d %d %d %d %d %d %s" % (x, y, z, keys[j][0], y, z, st))
        i = j + 1
    return out


def build_lines(doc, pl):
    p = pl["plan"]
    x0, z0, x1, z1 = pl["clear"]
    y0, y1 = pl["clear_y"]
    out = ["# Generated by tools/lopunny_house.py from data/lopunny_house.json. Re-run to rebuild; do not edit.",
           "# The Lopunny superfan's house (E. Hopgood), its Buneary cellar, the yard and the statue.",
           "# Run BEFORE R9E: the Habitat Block lopunny_superfan_cellar_ward sits in the cellar floor this writes.",
           "# 1. clear the trees, plants and snow layers over everything this writes"]
    for tag in ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable"):
        out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out.append("# 2. the structure, the cellar first (bottom up)")
    over = set(p.hung) | {k for k, _st in p.doors}
    out += _runs({k: st for k, st in p.solid.items() if k not in over})
    out.append("# 3. what hangs on it, from the top: chain, lanterns, banners, signs, ladder, trapdoor, candles, carpets")
    out += _runs(p.hung, top_down=True)
    out.append("# 4. the door, lower half then upper")
    out += ["setblock %d %d %d %s" % (k + (st,)) for k, st in p.doors]
    return out


def callback_text(doc):
    c = doc["lopunny_check"]
    return "\n".join([
        "'Generated by tools/lopunny_house.py from data/lopunny_house.json lopunny_check. Once a second: tag the player';",
        "'%s while a Lopunny is in the party, untag them otherwise. The conversation of Hopgood reads the tag';" % c["tag"],
        "'(compile_dialogue player_tag). The party read of the water ladder (tools/blackout_pack.py, EXP-042); EXP-052.';",
        "math.mod(q.player.world.game_time, %d) != 0 ? { return 0; };" % int(c["period_ticks"]),
        "t.has = 0;",
        "for_each(t.p, q.player.party.pokemon, {",
        "  t.id = t.p.species.identifier;",
        "  t.id == '%s' ? { t.has = 1; };" % c["species"],
        "});",
        "t.has == 1 ? { q.run_command('tag ' + q.player.username + ' add %s'); } : "
        "{ q.run_command('tag ' + q.player.username + ' remove %s'); };" % (c["tag"], c["tag"]),
        ""])


def files(doc, g):
    pl = plan(doc, g)
    lines = function_limits.ensure_loaded(build_lines(doc, pl))
    bad = function_limits.check_lines(lines, "build")
    if bad:
        raise HouseError("build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    out = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the Lopunny superfan's house (tools/lopunny_house.py)"}}, indent=2) + "\n",
        "data/%s/function/%s/build.mcfunction" % (NS, FN): "\n".join(lines) + "\n",
        CALLBACK: callback_text(doc),
    }
    return out, pl


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, as a step BEFORE R9E: hold the chunks, build, release (R18F's shape)."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    pl = plan(doc, g)
    x0, z0, x1, z1 = pl["clear"]
    hold = "%d %d %d %d" % (x0, z0, x1, z1)
    return [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (NS, FN)),
            ("cmd", "forceload remove " + hold)]


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def report(doc, pl):
    b = pl["blocks"]
    lines = ["site %s: house floor y%d (max ground under the walls + 1), cellar floor y%d, ridge y%d, statue floor y%d"
             % (doc["site"]["centre"], pl["hf"], pl["floor_y"], pl["ridge_y"], pl["statue_floor"]),
             "blocks written: %d (air %d); clear box x%d..%d z%d..%d y%d..%d"
             % (len(b), sum(1 for s in b.values() if s == "minecraft:air"), pl["clear"][0], pl["clear"][2],
                pl["clear"][1], pl["clear"][3], pl["clear_y"][0], pl["clear_y"][1]),
             "habitat block (cellar floor centre): %s; Hopgood stands at %s" % (pl["habitat_block"], pl["npc"]),
             "steps (before R9E): %s" % json.dumps([list(s) for s in placement_steps(doc, pl["plan"].g)])]
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "plan"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    out_files, pl = files(doc, g)
    if a.cmd == "plan":
        print("\n".join(report(doc, pl)))
        return 0
    write(out_files, a.out)
    n = sum(1 for l in out_files["data/%s/function/%s/build.mcfunction" % (NS, FN)].splitlines()
            if l and not l.startswith("#"))
    print("lopunny_house: %d files -> %s (build: %d commands)" % (len(out_files), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
