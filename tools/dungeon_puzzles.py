#!/usr/bin/env python
"""The dungeon's PUZZLE and VAULT room kinds (unit DG-PUZZLES, 2026-10-09), registered into the room kit.

Mechanism rung: **datapack plus generator** (functions and a few loot tables). The rungs above it have no say over
blocks in a custom dimension, and nothing here needed a scripting layer or a mod. Every control is a plain vanilla
block a player in adventure mode can USE (adventure forbids breaking and placing, not using) and every state is read
with `execute if block` / `execute if data block` by the keeper's per-room `tick` hook.

  kind `puzzle`   params.variant   levers | sequence | plates     (`blocks` is refused, below)
                  params.size      levers: 3..6 (default params.controls, else 3)
                  params.length    sequence: 3..6 presses (default 4)
                  params.count     plates: 3..6 (default 4)
                  params.penalty_s clock charged for a wrong attempt (default engine.clock.fall_penalty_s)
  kind `vault`    params.chests 1..8 (default 4), params.clock_cost_s per chest opened (default 20),
                  params.loot_by_band {band: loot-table id | [{"item", "count" | [lo, hi], "chance"?}]} (absent: the
                  data file's placeholder default_loot_by_band),
                  each chest opened also weighs its loot on the clock (expected cp for the band, data/dungeon_greed.json;
                  params.ladder is refused: the greed table replaced it)

THE THREE VARIANTS (each solves by `clear`, which opens the gate like any room's; each wrong attempt costs
`penalty_s` of the member's clock, shows it, and visibly resets the controls):
  levers    a console on the north wall: N levers, a lamp over each (lit or dark: the pattern to match), a seal
            button. Set every lever to its lamp and press the seal. A wrong seal flips every lever back.
  sequence  N wooden buttons, each under a coloured block, and a row of coloured blocks above: the order to press
            them in. Each right press lights a progress lamp; a wrong press puts everything back.
  plates    N stone pressure plates on coloured floor tiles spread over the room, and the colour order on the north
            wall: step on them in that order (a plate stepped on is lit and removed); the wrong plate charges the
            clock and sends the member back to the entry, every plate restored.
`blocks` (push or carry a block) is not workable in adventure mode: nothing can be pushed without a piston and
redstone, and a carried block is a placed block. It is omitted, and a record asking for it is refused by problems().

RANDOM PER RUN. The target of each variant is chosen on `enter` among up to 8 precomputed ones with
`random value 0..K-1` (the commands are written into the functions v0..v<K-1>), so a second run is not the first. The
shell writes variant 0, so a bare shell shows a target. Which variants exist is the generator's, from
R.rng(dungeon, room): the four slots of a dungeon are one dungeon.

THE VAULT (greed). Chests stand against the south wall, each on a plinth; each is placed with a LOOT TABLE for the
entrant's band (reset, as the seam is: `dg.band`). Opening a chest unpacks its loot table, which removes the block
entity's `LootTable` tag; the keeper sees `unless data block x y z LootTable` once and charges the clock
(`scoreboard players remove @s dg.clock`) and weighs the loot (greed/add, tools/dungeon_greed.py). Item-stack loot becomes a generated loot table
(`pack_files(doc)`, one per room and band, tools/dungeon.py build() writes them); a string is any existing table id.
A chest is always re-placed from air (a setblock onto an identical chest state fails and never loads its NBT).

UNPROVEN IN GAME (an experiment, not a fact): that a lever, button, plate and chest are usable in adventure mode in
cobblers:pocket (vanilla says yes); that `LootTable` leaves a chest's data when it is opened; that `random value` works
in a datapack function as written (vanilla 1.20.2+; blackout_pack.py uses the same form); the 20/30-tick press timings
(vanilla values); a plate's powered state surviving a keeper pass (a stone plate stays pressed 20 ticks after the last
entity leaves). The offline model is tests/test_dungeon_puzzles.py.

Every function that writes a block carries `# chunks-loaded-by:` (the member is in the room); state lives in the
objective `dg.rs` on fake holders `#s<g>r<i>` + p (the pick), g (progress), x (a scratch flag), c<j> (chest j).
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_grid as G  # noqa: E402
import dungeon_rooms as R  # noqa: E402
from dungeon_rooms import fill, setb  # noqa: E402

PUZZLES_PATH = ROOT / "data" / "dungeon_puzzles.json"
SCHEMA = "cobblers.dungeon_puzzles/1"
LOADED = "# chunks-loaded-by: the member standing in the room (its chunks are loaded)"
VARIANT_NAMES = ("levers", "sequence", "plates")
LOOT_DIR = "dungeons/vault"

# wall-mounted buttons and levers have no collision: the walk check must see through them
G.PASSABLE.update({"minecraft:jungle_button", "minecraft:mangrove_button", "minecraft:birch_button", "minecraft:spruce_button",
                   "minecraft:acacia_button", "minecraft:dark_oak_button", "minecraft:cherry_button", "minecraft:bamboo_button",
                   "minecraft:lever", "minecraft:oak_button", "minecraft:stone_pressure_plate", "minecraft:oak_pressure_plate"})


# ------------------------------------------------------------------------------------------------- data


_DATA = {}


def load(path=PUZZLES_PATH):
    key = str(path)
    if key not in _DATA:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema") != SCHEMA:
            raise R.RoomError("%s: schema must be %s" % (path, SCHEMA))
        _DATA[key] = doc
    return _DATA[key]


def blocks_of(theme_id):
    t = load()["themes"].get(theme_id)
    if t is None:
        raise R.RoomError("data/dungeon_puzzles.json has no blocks for theme %r" % theme_id)
    return t


def lever(on=False):
    return "minecraft:lever[face=wall,facing=south,powered=%s]" % ("true" if on else "false")


def button(B, on=False):
    return "%s[face=wall,facing=south,powered=%s]" % (B["button"], "true" if on else "false")


def U(doc):
    c = doc["engine"]["clock"]
    return c["units_per_tick"] * 20


class Ctl:
    """What one built room needs to write its blocks and functions."""

    def __init__(self, doc, d, slot, room):
        self.doc, self.d, self.slot, self.room = doc, d, slot, room
        self.B = blocks_of(d.get("theme"))
        self.H = R.state_holder(slot, room)
        self.dim = doc["engine"]["pocket"]["dimension"]
        self.p = room["params"]
        self.fy = room["floor_in"]
        pen = self.p.get("penalty_s", doc["engine"]["clock"]["fall_penalty_s"])
        self.pen_s = int(pen)
        self.pen = self.pen_s * U(doc)
        self.lab = "%s room %s (%s)" % (d["id"], room["id"], room["kind"])

    def fn(self, name):
        return R.room_fn(self.d, self.room, self.slot, name)

    def holder(self, tag):
        return self.H + tag

    def inn(self, line):
        return "execute in %s run %s" % (self.dim, line)

    def fail(self, msg):
        raise R.RoomError("%s: %s" % (self.lab, msg))

    def bounds(self, name, lo, hi):
        v = int(self.p.get(name, lo))
        if not (lo <= v <= hi):
            self.fail("params.%s must be %d..%d (is %d)" % (name, lo, hi, v))
        return v


def sb_set(holder, v):
    return "scoreboard players set %s dg.rs %d" % (holder, v)


def bar(msg, colour):
    return "title @s actionbar %s" % R.text(msg, colour)


def say(key, colour="gray", **fmt):
    """The on-screen line `data/dungeon_puzzles.json` messages.<key> as an actionbar command, or NOTHING when the text is
    empty (the owner, 2026-10-10: 'puzzles should have less explanation'): the lines are a short hint, and a puzzle is
    meant to be read off its console. Returned as a list so a caller can add it with `+`."""
    msg = load().get("messages", {}).get(key, "")
    for k, v in fmt.items():
        msg = msg.replace("{%s}" % k, str(v))
    return [bar(msg, colour)] if msg else []


def sound(name, vol=1, pitch=1):
    return "playsound %s master @s ~ ~ ~ %s %s" % (name, vol, pitch)


def at(pos):
    return "%d %d %d" % tuple(pos)


def panel_xs(room, n):
    cx = (room["ix0"] + room["ix1"]) // 2
    return cx, [cx - (n - 1) + 2 * k for k in range(n)]


def need_inside(c, x_lo, x_hi):
    r = c.room
    if x_lo < r["ix0"] + 2 or x_hi > r["ix1"] - 2:
        c.fail("the console needs x %d..%d and the room's interior is %d..%d: lengthen the room" % (x_lo, x_hi, r["ix0"], r["ix1"]))
    if r["iz1"] - r["iz0"] < 6:
        c.fail("the room is too narrow for a console (width %d)" % r["width"])


# ------------------------------------------------------------------------------------------------- variants of a target


def variant_count(n_possible):
    return max(1, min(int(load()["limits"]["variants_max"]), n_possible))


def lever_patterns(d, room, n):
    """Up to 8 distinct lever patterns (lit = True), each with at least one lamp lit: the all-dark pattern is the
    levers' own starting state and would solve itself."""
    rg = R.rng(d, room, "lever_patterns")
    allp = list(range(1, 2 ** n))
    rg.shuffle(allp)
    k = variant_count(len(allp))
    return [[bool((v >> b) & 1) for b in range(n)] for v in allp[:k]]


def order_perms(d, room, n, salt):
    """Up to 8 distinct permutations of the n controls other than the controls' own left-to-right order."""
    rg = R.rng(d, room, salt)
    allp = [list(p) for p in itertools.permutations(range(n)) if list(p) != list(range(n))]
    rg.shuffle(allp)
    return allp[:variant_count(len(allp))]


def enter_pick(c, k, extra=()):
    """The `enter` lines: pick one of the k variant functions at random for this run."""
    h = c.holder("p")
    out = list(extra) + [LOADED, "execute store result score %s dg.rs run random value 0..%d" % (h, k - 1)]
    out += ["execute if score %s dg.rs matches %d run function %s" % (h, j, c.fn("v%d" % j)) for j in range(k)]
    return out


def penalty_lines(c, key):
    return (["scoreboard players remove @s dg.clock %d" % c.pen, sound("minecraft:block.anvil.land", 0.6, 1.4)]
            + say(key, "red", s=c.pen_s))


# ------------------------------------------------------------------------------------------------- levers


def build_levers(c):
    r, B = c.room, c.B
    n = c.bounds("size", 3, 6) if "size" in c.p else c.bounds("controls", 3, 6)
    cx, xs = panel_xs(r, n)
    sx = xs[-1] + 3
    fy, iz0, z = c.fy, r["iz0"], r["iz0"] + 1
    need_inside(c, xs[0] - 1, sx + 1)
    if r["height"] < 5:
        c.fail("a lever console needs a height of at least 5")
    pats = lever_patterns(c.d, r, n)
    ops = [fill((xs[0] - 1, fy, iz0, sx + 1, fy + 3, iz0), B["console"]), fill((xs[0] - 1, fy + 3, iz0, sx + 1, fy + 3, iz0), B["trim"])]
    lev = [(x, fy + 1, z) for x in xs]
    lamp = [(x, fy + 2, iz0) for x in xs]
    seal = (sx, fy + 1, z)
    for k in range(n):
        ops += [setb(lamp[k], B["lamp_on"] if pats[0][k] else B["lamp_off"]), setb(lev[k], lever())]
    ops += [setb((sx, fy + 2, iz0), B["seal"]), setb(seal, button(B))]
    H, hx = c.H, c.holder("x")
    btn_on = "%s[powered=true]" % B["button"]
    f = {}
    for j, pat in enumerate(pats):
        f["v%d" % j] = [LOADED] + ["setblock %s %s" % (at(lamp[k]), B["lamp_on"] if pat[k] else B["lamp_off"]) for k in range(n)]
    enter = enter_pick(c, len(pats), say("hint_levers"))
    tick = [LOADED, "execute unless score %s dg.rs matches 1 run return 0" % H,
            "execute if block %s %s run function %s" % (at(seal), btn_on, c.fn("confirm"))]
    confirm = [LOADED, "setblock %s %s" % (at(seal), button(B)), sb_set(hx, 0)]
    for k in range(n):
        confirm.append("execute if block %s %s unless block %s minecraft:lever[powered=true] run %s"
                       % (at(lamp[k]), B["lamp_on"], at(lev[k]), sb_set(hx, 1)))
        confirm.append("execute unless block %s %s if block %s minecraft:lever[powered=true] run %s"
                       % (at(lamp[k]), B["lamp_on"], at(lev[k]), sb_set(hx, 1)))
    confirm += ["execute if score %s dg.rs matches 0 run function %s" % (hx, c.fn("clear")),
                "execute if score %s dg.rs matches 1 run function %s" % (hx, c.fn("wrong"))]
    wrong = [LOADED] + penalty_lines(c, "wrong_levers") + ["setblock %s %s" % (at(p), lever()) for p in lev]
    wrong += ["particle minecraft:angry_villager %s 0.8 0.4 0.4 0 8" % at((cx, fy + 2, z))]
    reset = ["# the console: levers down, the seal up, variant 0 on the lamps (the next entry rolls again)"]
    reset += [c.inn("setblock %s %s" % (at(p), lever())) for p in lev] + [c.inn("setblock %s %s" % (at(seal), button(B)))]
    reset += [c.inn("function %s" % c.fn("v0"))]
    clear = [LOADED] + [c.inn("setblock %s %s" % (at(p), B["lamp_on"])) for p in lamp]
    clear += [c.inn("particle minecraft:happy_villager %s 1.5 0.5 0.5 0 12 force" % at((cx, fy + 2, z)))]
    anchors = {"controls": [[x, fy + 1, z, 0] for x in xs], "seal": [[sx, fy + 1, z, 0]], "display": [[cx, fy + 2, z, 0]]}
    expect = ([(p, B["lamp_on"] if pats[0][k] else B["lamp_off"]) for k, p in enumerate(lamp)] + [(p, "minecraft:lever") for p in lev]
              + [(seal, B["button"]), ((sx, fy + 2, iz0), B["seal"])])
    attached = [(p, (p[0], p[1], iz0)) for p in lev + [seal]]
    return {"blocks": ops, "anchors": anchors, "reserve": [(xs[0] - 1, fy, iz0, sx + 1, fy + 2, z + 1)],
            "functions": dict(f, enter=enter, tick=tick, confirm=confirm, wrong=wrong, reset=reset, clear=clear),
            "meta": {"puzzle": "levers", "variants": pats, "expect": expect, "attached": attached, "n": n}}


# ------------------------------------------------------------------------------------------------- sequence


def build_sequence(c):
    r, B = c.room, c.B
    n = c.bounds("length", 3, 6)
    cx, xs = panel_xs(r, n)
    fy, iz0, z = c.fy, r["iz0"], r["iz0"] + 1
    need_inside(c, xs[0] - 1, xs[-1] + 1)
    if r["height"] < 6:
        c.fail("a sequence console needs a height of at least 6")
    marks = B["marks"]
    perms = order_perms(c.d, r, n, "sequence_perms")
    ops = [fill((xs[0] - 1, fy, iz0, xs[-1] + 1, fy + 4, iz0), B["console"]), fill((xs[0] - 1, fy, iz0, xs[-1] + 1, fy, iz0), B["trim"])]
    btn = [(x, fy + 1, z) for x in xs]
    prog = [(x, fy + 3, iz0) for x in xs]
    disp = [(x, fy + 4, iz0) for x in xs]
    for i in range(n):
        ops += [setb(btn[i], button(B)), setb((xs[i], fy + 2, iz0), marks[i]), setb(prog[i], B["lamp_off"]), setb(disp[i], marks[perms[0][i]])]
    H, hg = c.H, c.holder("g")
    btn_on = "%s[powered=true]" % B["button"]
    f = {}
    for j, pm in enumerate(perms):
        f["v%d" % j] = [LOADED] + ["setblock %s %s" % (at(disp[p]), marks[pm[p]]) for p in range(n)]
    chain = [LOADED, "# every correct press, in the order the row shows, even if two fell in one keeper pass"]
    for p in range(n):
        for i in range(n):
            chain.append("execute if score %s dg.rs matches %d if block %s %s if block %s %s run function %s"
                         % (hg, p, at(btn[i]), btn_on, at(disp[p]), marks[i], c.fn("adv%d" % i)))
    for i in range(n):
        f["adv%d" % i] = ([LOADED, "setblock %s %s" % (at(btn[i]), button(B)), "scoreboard players add %s dg.rs 1" % hg]
                          + ["execute if score %s dg.rs matches %d run setblock %s %s" % (hg, p + 1, at(prog[p]), B["lamp_on"]) for p in range(n)]
                          + [sound("minecraft:block.note_block.chime", 1, 1.2),
                             "execute if score %s dg.rs matches %d run function %s" % (hg, n, c.fn("clear"))])
    tick = [LOADED, "execute unless score %s dg.rs matches 1 run return 0" % H, "function %s" % c.fn("chain"),
            "execute unless score %s dg.rs matches 1 run return 0" % H]
    tick += ["execute if block %s %s run function %s" % (at(btn[i]), btn_on, c.fn("wrong")) for i in range(n)]
    wrong = [LOADED] + penalty_lines(c, "wrong_sequence") + [sb_set(hg, 0)]
    wrong += ["setblock %s %s" % (at(p), B["lamp_off"]) for p in prog] + ["setblock %s %s" % (at(p), button(B)) for p in btn]
    reset = ["# the console: buttons up, progress dark, variant 0 on the row"]
    reset += [c.inn("setblock %s %s" % (at(p), button(B))) for p in btn] + [c.inn("setblock %s %s" % (at(p), B["lamp_off"])) for p in prog]
    reset += [sb_set(hg, 0), c.inn("function %s" % c.fn("v0"))]
    clear = [LOADED] + [c.inn("setblock %s %s" % (at(p), B["lamp_on"])) for p in prog]
    clear += [c.inn("particle minecraft:happy_villager %s 1.5 0.5 0.5 0 12 force" % at((cx, fy + 2, z)))]
    enter = enter_pick(c, len(perms), say("hint_sequence") + [sb_set(hg, 0)])
    anchors = {"controls": [[x, fy + 1, z, 0] for x in xs], "display": [[cx, fy + 2, z, 0]]}
    expect = ([(p, B["button"]) for p in btn] + [((xs[i], fy + 2, iz0), marks[i]) for i in range(n)]
              + [(disp[p], marks[perms[0][p]]) for p in range(n)])
    return {"blocks": ops, "anchors": anchors, "reserve": [(xs[0] - 1, fy, iz0, xs[-1] + 1, fy + 2, z + 1)],
            "functions": dict(f, enter=enter, tick=tick, chain=chain, wrong=wrong, reset=reset, clear=clear),
            "meta": {"puzzle": "sequence", "variants": perms, "expect": expect, "attached": [(p, (p[0], p[1], iz0)) for p in btn], "n": n}}


# ------------------------------------------------------------------------------------------------- plates


def plate_cells(c, n):
    """Plate positions spread over the room, alternating north and south of the line between the doors, 5 or more
    apart, and kept 4 clear of the line itself so a player walking door to door never steps on one."""
    r = c.room
    rg = R.rng(c.d, r, "plates")
    ix0, ix1, iz0, iz1 = r["ix0"], r["ix1"], r["iz0"], r["iz1"]
    x_lo, x_hi = ix0 + 8, ix1 - 8
    if x_hi - x_lo < 4 * (n - 1) or iz1 - iz0 < 14:
        c.fail("a plate field of %d needs a room of about %d x 15 (this is %d x %d)" % (n, 4 * (n - 1) + 17, r["length"], r["width"]))
    cells = []
    for i in range(n):
        x0 = x_lo + (x_hi - x_lo) * i // max(n - 1, 1)
        for attempt in range(400):
            x = min(max(x0 + rg.randint(-1, 1), x_lo), x_hi)
            line = r["z_in"] + (r["z_out"] - r["z_in"]) * (x - ix0) / max(ix1 - ix0, 1)
            side = 1 if (i + attempt // 200) % 2 == 0 else -1
            if side > 0:
                lo, hi = int(line) + 5, iz1 - 3
            else:
                lo, hi = iz0 + 5, int(line) - 5
            if hi < lo:
                continue
            zc = rg.randint(lo, hi)
            if all((x - a) ** 2 + (zc - b) ** 2 >= 25 for a, b in cells):
                cells.append((x, zc))
                break
        else:
            c.fail("no place for plate %d of %d" % (i + 1, n))
    return cells


def build_plates(c):
    r, B = c.room, c.B
    n = c.bounds("count", 3, 6)
    cx, xs = panel_xs(r, n)
    fy, iz0, z = c.fy, r["iz0"], r["iz0"] + 1
    need_inside(c, xs[0] - 1, xs[-1] + 1)
    if r["height"] < 5:
        c.fail("a plate puzzle's wall needs a height of at least 5")
    marks, plate = B["marks"], B["plate"]
    cells = plate_cells(c, n)
    perms = order_perms(c.d, r, n, "plates_perms")
    ops = [fill((xs[0] - 1, fy, iz0, xs[-1] + 1, fy + 3, iz0), B["console"])]
    prog = [(x, fy + 1, iz0) for x in xs]
    disp = [(x, fy + 2, iz0) for x in xs]
    pl = [(x, fy, zc) for x, zc in cells]
    tile = [(x, fy - 1, zc) for x, zc in cells]
    for i in range(n):
        ops += [setb(prog[i], B["lamp_off"]), setb(disp[i], marks[perms[0][i]]), setb(tile[i], marks[i]), setb(pl[i], plate)]
    start = [r["ix0"] + 2, fy, r["z_in"], -90]
    H, hg = c.H, c.holder("g")
    on = "%s[powered=true]" % plate
    f = {}
    for j, pm in enumerate(perms):
        f["v%d" % j] = [LOADED] + ["setblock %s %s" % (at(disp[p]), marks[pm[p]]) for p in range(n)]
    chain = [LOADED, "# every correct plate, in the order the wall shows"]
    for p in range(n):
        for i in range(n):
            chain.append("execute if score %s dg.rs matches %d if block %s %s if block %s %s run function %s"
                         % (hg, p, at(pl[i]), on, at(disp[p]), marks[i], c.fn("adv%d" % i)))
    for i in range(n):
        f["adv%d" % i] = ([LOADED, "setblock %s minecraft:air" % at(pl[i]), "setblock %s %s" % (at(tile[i]), B["lamp_on"]),
                           "scoreboard players add %s dg.rs 1" % hg]
                          + ["execute if score %s dg.rs matches %d run setblock %s %s" % (hg, p + 1, at(prog[p]), B["lamp_on"]) for p in range(n)]
                          + [sound("minecraft:block.note_block.chime", 1, 1.2),
                             "execute if score %s dg.rs matches %d run function %s" % (hg, n, c.fn("clear"))])
    tick = [LOADED, "execute unless score %s dg.rs matches 1 run return 0" % H, "function %s" % c.fn("chain"),
            "execute unless score %s dg.rs matches 1 run return 0" % H]
    tick += ["execute if block %s %s run function %s" % (at(p), on, c.fn("wrong")) for p in pl]
    restore = ["setblock %s %s" % (at(pl[i]), plate) for i in range(n)] + ["setblock %s %s" % (at(tile[i]), marks[i]) for i in range(n)]
    restore += ["setblock %s %s" % (at(p), B["lamp_off"]) for p in prog]
    wrong = [LOADED] + penalty_lines(c, "wrong_plates")
    wrong += ["tp @s %d.5 %d %d.5 %d 0" % tuple(start), sb_set(hg, 0)] + restore
    reset = ["# the field: every plate and tile restored, progress dark, variant 0 on the wall"]
    reset += [c.inn(x) for x in restore] + [sb_set(hg, 0), c.inn("function %s" % c.fn("v0"))]
    clear = [LOADED] + [c.inn("setblock %s %s" % (at(p), B["lamp_on"])) for p in prog]
    clear += [c.inn("particle minecraft:happy_villager %s 1.5 0.5 0.5 0 12 force" % at((cx, fy + 2, z)))]
    enter = enter_pick(c, len(perms), say("hint_plates") + [sb_set(hg, 0)])
    anchors = {"controls": [[x, fy, zc, 0] for x, zc in cells], "display": [[cx, fy + 2, z, 0]], "start": [start]}
    expect = ([(pl[i], plate) for i in range(n)] + [(tile[i], marks[i]) for i in range(n)] + [(disp[p], marks[perms[0][p]]) for p in range(n)])
    return {"blocks": ops, "anchors": anchors, "reserve": [(x - 1, fy - 1, zc - 1, x + 1, fy, zc + 1) for x, zc in cells],
            "functions": dict(f, enter=enter, tick=tick, chain=chain, wrong=wrong, reset=reset, clear=clear),
            "meta": {"puzzle": "plates", "variants": perms, "expect": expect, "attached": [], "n": n}}


BUILDERS = {"levers": build_levers, "sequence": build_sequence, "plates": build_plates}


def kind_puzzle(doc, d, slot, room, theme):
    c = Ctl(doc, d, slot, room)
    var = c.p.get("variant", "levers")
    if var == "blocks":
        c.fail("variant `blocks` is not workable in adventure mode (nothing can be pushed or carried); use levers, sequence or plates")
    if var not in BUILDERS:
        c.fail("unknown puzzle variant %r (levers, sequence, plates)" % (var,))
    return BUILDERS[var](c)


# ------------------------------------------------------------------------------------------------- the vault


def chest_xs(room, n):
    lo, hi = room["ix0"] + 5, room["ix1"] - 5
    return [(lo + hi) // 2] if n == 1 else [lo + round(i * (hi - lo) / (n - 1)) for i in range(n)]


def loot_of(params):
    """The room's loot_by_band, or the data file's placeholder when the record names none."""
    return params.get("loot_by_band") or load()["default_loot_by_band"]


def loot_for(room_params, bands, band):
    """The loot spec of the highest authored band at or below `band`, or None."""
    lb = loot_of(room_params)
    keys = sorted(int(k) for k in lb)
    ok = [k for k in keys if k <= band]
    return (ok[-1], lb[str(ok[-1])]) if ok else (None, None)


def table_id(d, room, key, value):
    return value if isinstance(value, str) else "cobblers:%s/%s/%s/b%d" % (LOOT_DIR, d["id"], room["id"], key)


def loot_table(stacks):
    pools = []
    for s in stacks:
        entry = {"type": "minecraft:item", "name": s["item"]}
        cnt = s.get("count", 1)
        entry["functions"] = [{"function": "minecraft:set_count",
                               "count": cnt if isinstance(cnt, int) else {"type": "minecraft:uniform", "min": cnt[0], "max": cnt[1]}}]
        pool = {"rolls": 1, "entries": [entry]}
        if "chance" in s:
            pool["conditions"] = [{"condition": "minecraft:random_chance", "chance": s["chance"]}]
        pools.append(pool)
    return {"type": "minecraft:chest", "pools": pools}


def build_vault(doc, d, slot, room, theme):
    c = Ctl(doc, d, slot, room)
    B = c.B
    n = c.bounds("chests", 1, 8) if "chests" in c.p else int(load()["defaults"]["vault_chests"])
    cost_s = int(c.p.get("clock_cost_s", load()["defaults"]["vault_clock_cost_s"]))
    if cost_s < 1:
        c.fail("clock_cost_s must be at least 1")
    if "ladder" in c.p:
        c.fail("params.ladder is gone: every chest is weighed by its loot (data/dungeon_greed.json, tools/dungeon_greed.py)")
    r = room
    fy, iz1 = c.fy, r["iz1"]
    xs = chest_xs(r, n)
    if n > 1 and (xs[-1] - xs[0]) < 4 * (n - 1):
        c.fail("%d chests need a room at least %d long (this is %d)" % (n, 4 * (n - 1) + 12, r["length"]))
    if r["iz1"] - r["iz0"] < 6:
        c.fail("the vault is too narrow (width %d)" % r["width"])
    bands = [b["band"] for b in doc["engine"]["bands"]]
    bad_loot = check_loot(c.lab, c.p, bands)
    if bad_loot:
        c.fail("; ".join(bad_loot))
    chest = [(x, fy, iz1) for x in xs]
    stand = [[x, fy, iz1 - 1, 0] for x in xs]

    def block_for(band):
        key, val = loot_for(c.p, bands, band)
        if key is None:
            c.fail("loot_by_band has nothing at or below band %d (author a \"1\" entry)" % band)
        return "%s[facing=north]{LootTable:\"%s\"}" % (B["chest"], table_id(d, room, key, val))
    ops = []
    for x, y, z in chest:
        ops += [fill((x - 1, fy - 1, iz1 - 2, x + 1, fy - 1, iz1), B["plinth"]), setb((x, y, z), block_for(bands[0]))]
    H = c.H
    hc = [c.holder("c%d" % j) for j in range(n)]
    f = {}
    cost_u = cost_s * U(doc)
    all_open = " ".join("if score %s dg.rs matches 2" % h for h in hc)
    # GREED (unit GREED, 2026-10-10): each chest opened also weighs its loot, the chest's expected value for the
    # entrant's band, once (the open state goes 1 -> 2 and only the reset puts it back)
    import dungeon_greed as DG
    gt = DG.load()
    band_cp = {}
    for b in bands:
        _k, val = loot_for(c.p, bands, b)
        v = DG.chest_cp(gt, val) if val is not None else None
        if v is None:
            c.fail("the loot at band %d is not priced by data/dungeon_greed.json (add its items or its table)" % b)
        band_cp[b] = v
    for j in range(n):
        f["open%d" % j] = ([sb_set(hc[j], 2), "scoreboard players remove @s dg.clock %d" % cost_u,
                            *say("chest_taken", "gold", s=cost_s), sound("minecraft:entity.item.pickup", 1, 0.8)]
                           + DG.chest_lines(doc, band_cp)
                           + ["execute %s run function %s" % (all_open, c.fn("clear"))])
    tick = [LOADED] + ["execute if score %s dg.rs matches 1 unless data block %s LootTable run function %s"
                       % (hc[j], at(chest[j]), c.fn("open%d" % j)) for j in range(n)]
    enter = say("hint_vault", "gold", s=cost_s) + [sb_set(h, 1) for h in hc]
    reset = ["# the chests: from air, with the entrant's band's loot table (a setblock onto the same chest state would fail and load nothing)"]
    reset += [c.inn("setblock %s minecraft:air" % at(p)) for p in chest]
    for j, p in enumerate(chest):
        for b in bands:
            reset.append("execute in %s if score @s dg.band matches %d run setblock %s %s" % (c.dim, b, at(p), block_for(b)))
    reset += [sb_set(h, 1) for h in hc]
    return {"blocks": ops, "anchors": {"chests": stand},
            "functions": dict(f, enter=enter, tick=tick, reset=reset),
            "meta": {"vault": True, "chest_cells": [list(p) for p in chest], "n": n, "cost_s": cost_s, "greed_cp": band_cp,
                     "expect": [(p, B["chest"]) for p in chest], "attached": []}}


def kind_vault(doc, d, slot, room, theme):
    return build_vault(doc, d, slot, room, theme)


# ------------------------------------------------------------------------------------------------- loot tables (pack files)


def vault_rooms(doc):
    for d in doc["dungeons"]:
        for r in d.get("rooms", []):
            if r["kind"] == "vault":
                yield d, r


def pack_files(doc):
    """{path: text} for the loot tables of every vault room with item-stack loot (tools/dungeon.py build() writes them)."""
    out = {}
    for d, r in vault_rooms(doc):
        for k, v in sorted(loot_of(r.get("params", {})).items(), key=lambda kv: int(kv[0])):
            if isinstance(v, list):
                out["data/cobblers/loot_table/%s/%s/%s/b%d.json" % (LOOT_DIR, d["id"], r["id"], int(k))] = \
                    json.dumps(loot_table(v), indent=2) + "\n"
    return out


# ------------------------------------------------------------------------------------------------- checks


def check_loot(c_label, params, bands):
    bad = []
    lb = loot_of(params)
    if not isinstance(lb, dict) or not lb:
        return ["%s: params.loot_by_band must be an object {band: loot table id | [stacks]}" % c_label]
    for k, v in lb.items():
        if not str(k).isdigit():
            bad.append("%s: loot_by_band key %r is not a band number" % (c_label, k))
            continue
        if isinstance(v, str):
            if ":" not in v:
                bad.append("%s: loot_by_band[%s] %r is not a loot table id (namespace:path)" % (c_label, k, v))
        elif isinstance(v, list) and v:
            for s in v:
                if not isinstance(s, dict) or ":" not in str(s.get("item", "")):
                    bad.append("%s: loot_by_band[%s] stack %r needs an item id" % (c_label, k, s))
                    continue
                cnt = s.get("count", 1)
                if not ((isinstance(cnt, int) and 1 <= cnt <= 64) or (isinstance(cnt, list) and len(cnt) == 2 and 1 <= cnt[0] <= cnt[1] <= 64)):
                    bad.append("%s: loot_by_band[%s] %s count %r must be 1..64 or [lo, hi]" % (c_label, k, s["item"], cnt))
        else:
            bad.append("%s: loot_by_band[%s] must be a loot table id or a non-empty list of stacks" % (c_label, k))
    if not bad and min(int(k) for k in lb) > min(bands):
        bad.append("%s: loot_by_band has nothing for band %d (author a \"%d\" entry)" % (c_label, min(bands), min(bands)))
    return bad


def check(doc, d, slot):
    """EXTRA_CHECKS: params, the variants, that every control survived the theme's dressing with something solid to
    hang on, and that the clock cost is sane."""
    bad = []
    bands = [b["band"] for b in doc["engine"]["bands"]]
    for r in R.layout(doc, d, slot):
        if r["kind"] == "puzzle":
            if r["params"].get("variant", "levers") == "blocks":
                bad.append("%s room %s: variant `blocks` is not workable in adventure mode" % (d["id"], r["id"]))
            if int(r["params"].get("penalty_s", 0)) < 0:
                bad.append("%s room %s: penalty_s must not be negative" % (d["id"], r["id"]))
        if r["kind"] == "vault":
            bad += check_loot("%s room %s" % (d["id"], r["id"]), r["params"], bands)
    for b in R.slot_build(doc, d, slot):
        r = b.room
        if r["kind"] not in ("puzzle", "vault"):
            continue
        lab = "%s room %s (%s)" % (d["id"], r["id"], r["kind"])
        g = b.grid
        for pos, want in b.meta.get("expect", []):
            got = G.base(g.block_at(*pos))
            if got != G.base(want):
                bad.append("%s: %s at %s is %s (dressing or a bug overwrote it)" % (lab, G.base(want), list(pos), got))
        for pos, to in b.meta.get("attached", []):
            if G.classify(g.block_at(*to)) != G.SOLID:
                bad.append("%s: the control at %s hangs on %s, which is not solid" % (lab, list(pos), g.block_at(*to)))
        if b.meta.get("puzzle") == "plates":
            for a in b.anchors["controls"]:
                line = r["z_in"] + (r["z_out"] - r["z_in"]) * (a[0] - r["ix0"]) / max(r["ix1"] - r["ix0"], 1)
                if abs(a[2] - line) < 3 or abs(a[2] - r["z_in"]) < 3 or abs(a[2] - r["z_out"]) < 3:
                    bad.append("%s: the plate at %s is on the walk between the doors: a player passing through would trip it" % (lab, a[:3]))
        n = b.meta.get("n")
        vs = b.meta.get("variants")
        kind = b.meta.get("puzzle")
        if vs is not None:
            if kind == "levers":
                good = all(len(v) == n and any(v) for v in vs)
            else:
                good = all(sorted(v) == list(range(n)) and v != list(range(n)) for v in vs)
            if not vs or len({json.dumps(v) for v in vs}) != len(vs) or not good:
                bad.append("%s: a variant is not a solvable target (levers: some lamp lit; order: a permutation, not the identity)" % lab)
    return bad


R.EXTRA_CHECKS.append(check)

R.register("puzzle", kind_puzzle, dress="light")
R.register("vault", kind_vault, dress="full")
