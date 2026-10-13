#!/usr/bin/env python
"""Three more dungeon room kinds (dungeons next phase, unit RT-A, 2026-10-10): bank_vault, wishing_well, bait_room.

The owner (2026-10-10, DUNGEON_PASS2.md 'Next phase'): "more room types, to tell whole dungeons apart": a bank vault whose
code is hidden through the dungeon in separate rooms (signs on walls), a gamble room ("sacrifice an item for a chance at
more, a wishing-well vibe"), and a bait room ("leave an item to lure a Pokemon, which then appears in the NEXT dungeon").

Mechanism rung (CLAUDE.md principle 6): **datapack plus generator**, inside the room kit. The rungs above it have no say
over blocks and item entities in a custom dimension; vanilla commands, scoreboards and block entities are enough, so no
scripting layer, companion or mod is proposed. The kinds register through `dungeon_rooms.EXTENSION_MODULES`; tables are
`data/dungeon_extras.json`; the three call sites in tools/dungeon.py build() are this module's own lines.

  kind `bank_vault`  A vault chamber behind a code-locked gate. The 4 digits (params.digits 3..5) are ROLLED PER RUN at the
                     threshold (`slot/s<g>/start`, `random value 0..9` each) and written to wall signs only when the
                     member walks into one of the `params.clue_rooms` (those rooms' `enter` hook rewrites the sign the kit
                     placed there; the reset writes `?` back so a stale digit never shows). The keypad is ten wooden
                     buttons with a sign for each digit (the puzzles' own controls, tools/dungeon_puzzles.py), a lamp per
                     digit entered. The code is compared when the last digit is pressed; a wrong code charges
                     `params.penalty_s` and starts over, `max_tries` wrong codes jam the lock for the run. Inside:
                     `params.chests` chests with loot tables per band, each weighed by GREED as a vault chest and held to
                     the KIT3 vault budget. Optional by construction: the room must sit on a side entry or an optional fork
                     route, gate `open`; the gate in the chamber is shut in the shell and opened by `clear`.
  kind `wishing_well` A ring of stone round a one-deep pool. A member throws an item in (Q): the room takes an item entity
                     resting in the pool, prices it from GREED's table (cp x count), rolls `random value 1..100` against the
                     band's table of shares and pays that share of the value back, rounded DOWN into the dearest currency
                     item the pay reaches (a ladder per band). Up to `params.throws` (default 2) a run.
  kind `bait_room`   An altar. A bait item (data table: berries, a poke snack, poke bait) left on it is taken and stored on
                     the PLAYER (`dg.bait`, a scoreboard objective: it survives a logout, a death and a restart). At the
                     threshold of the player's NEXT run in a dungeon that has a bait room the score moves into the run and
                     is zeroed (consumed once); the room named by `params.lure_room` (a living room: any room that may hold
                     ambient life) spawns the bait's Pokemon for the band on its first pass, catchable, at the band's lower
                     level cap, a wild Pokemon of the slot (discarded at the slot's free and the keeper's stale pass).
                     TIERS (the owner, 2026-10-12): when data/dungeon_extras.json `bait_room.tiers` exists each bait names a
                     tier, and the lure gets two SEPARATE rolls (random value 1..10000 each): shiny, then alpha, at the tier's
                     `shiny_chance` / `alpha_chance`; the spawn's props gain `shiny=true` and/or `alpha=true`. A lure may be
                     shiny only, alpha only, both or neither; it stays at the band's lower cap. No `tiers`: no rolls, the
                     generated text is unchanged.

SELLING, GAMING AND THE CLOCK. GREED (tools/dungeon_greed.py) only ever ADDS points and the clock rate only ever rises; a
credit makes the clock FASTER, so loot is a cost to the run's time. The well therefore credits the NET GAIN of a throw,
`pay - thrown value`, only when positive (`greed/add` refuses anything under 1): a loss is never refunded, so a chain of throws
is charged at least the net gain it makes. Worthless items are refused (the value table is GREED's items and groups minus
the 'unpriced' placeholder rows; under `min_cp` too) and thrown back out; the reward is paid at a share of the value with an
expected share under `ev_cap`, so re-throwing it loses on average, and at most `throws` throws a run. The table is checked,
and a test mutates it. See data/dungeon_extras.json `gaming_why`.

Where the kinds reach into OTHER rooms (a clue sign in each clue room, the lure in its room) the kit's `POST_DRESS_FNS` hook
adds a block and merges the room's own `enter` / `reset` hooks; no other module is edited.

What it does NOT cover (all UNPROVEN in game): a button read per keeper pass (two presses inside one pass are taken in
ascending digit order, so a fast typist can transpose; the lock forgives 5 wrong codes); that `data modify block` rewrites a
waxed sign's `front_text.messages[n]`; that a thrown item rests inside the pool's selector box and `execute ... as @e[type=
item]` sees it in the pocket; `data get entity @s Item.count`; the macro `give @s $(item) $(n)` for a Cobblemon item; that a
spawned lure stays in its room; that `spawnpokemonat` honours `shiny=true` / `alpha=true` (an alpha's level and size are the
jar's to decide); the sound ids other than the ones the kit already uses. The simulator
(tests/test_dungeon_extras.py) proves the functions, not the game. Nothing here holds a coordination lock or touches a server.

  python tools/dungeon_extras.py       # the tables' checks, the well's expected shares, the bank's chest budget
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_grid as G  # noqa: E402
import dungeon_rooms as R  # noqa: E402
from dungeon_rooms import fill, setb  # noqa: E402

DATA = ROOT / "data" / "dungeon_extras.json"
SCHEMA = "cobblers.dungeon_extras/1"
BANK, WELL, BAIT = "bank_vault", "wishing_well", "bait_room"
OWN_KINDS = (BANK, WELL, BAIT)
LOADED = "# chunks-loaded-by: the member standing in the room (its chunks are loaded)"
OBJ_BAIT = "dg.bait"                  # the player's stored bait: 0 none, else the 1-based index into the bait table
OBJ_RS, OBJ_T = "dg.rs", "dg.t"
STORE = "cobblers:dungeons"           # command storage: well.item / well.n (the macro give)
DEPTH = 7                             # the bank's chamber: rows from the partition to the south wall
PANEL_HALF = 5                        # the keypad's console runs cx +- 5
KEYPAD_ROW = {1: (0, 1), 2: (1, 1), 3: (2, 1), 4: (3, 1), 5: (4, 1), 6: (0, 0), 7: (1, 0), 8: (2, 0), 9: (3, 0), 0: (4, 0)}
LEGEND = {"legendary", "mythical", "ultra_beast", "paradox"}      # paradox joined 2026-10-12 (the owner: no prize-class lure)
# The lure's property tokens (PokemonProperties, Cobblemon 1.8.0 jar, com/cobblemon/mod/common/api/pokemon/
# PokemonProperties$Companion.class, constant pool read 2026-10-12): the parser's keys include `shiny` -> setShiny(Boolean) and
# `alpha` (alias `is_alpha`) -> setAlpha(Boolean); the class holds the boolean words "yes", "true", "no", "false". `alpha=true`
# is also what the repo's habitat spawn entries already carry (tools/spawn_tiers_audit.py, tools/scar_tarn.py). UNPROVEN in
# game: that `spawnpokemonat` honours them (it parses the same PokemonProperties) -- see the module docstring's list.
PROP_SHINY, PROP_ALPHA = "shiny=true", "alpha=true"
ROLL_N = 10000                        # each roll is `random value 1..ROLL_N`; a chance is stored as a count out of it
ROLL_S, ROLL_A, FLAG_S, FLAG_A = "#lrs", "#lra", "#lfs", "#lfa"      # dg.t temporaries: the two rolls and the two outcomes
COBBLEMON_JAR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")
ID = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_/.-]+$")
SPECIES = re.compile(r"^[a-z0-9_]+$")

_DATA = {}


def load(path=DATA):
    key = str(path)
    if key not in _DATA:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("schema") != SCHEMA:
            raise R.RoomError("%s: schema must be %s" % (path, SCHEMA))
        _DATA[key] = doc
    return _DATA[key]


def _D():
    import dungeon as D       # lazy: tools/dungeon.py imports the kit, which imports this module
    return D


def _DG():
    import dungeon_greed as DG
    return DG


def _XR():
    import dungeon_crossroads as XR
    return XR


import dungeon_puzzles as DP  # noqa: E402  (the controls' blocks, the loot machinery)


def _wall_sign_ids():
    ids = {"minecraft:oak_wall_sign"}
    try:
        for t in R.load_themes()["themes"].values():
            ids.add((t.get("crossroads") or {}).get("sign", "minecraft:oak_wall_sign"))
    except (OSError, ValueError, KeyError):
        pass
    return ids


# a wall sign has no collision: the walk check must see through the keypad's digit signs
G.PASSABLE.update(_wall_sign_ids())


# ------------------------------------------------------------------------------------------------- small helpers


def at(pos):
    return "%d %d %d" % tuple(pos[:3])


def msg(section, key, **fmt):
    s = load()[section]["messages"][key]
    for k, v in fmt.items():
        s = s.replace("{%s}" % k, str(v))
    return s


def bar(text_, colour="gray"):
    return "title @s actionbar %s" % R.text(text_, colour)


def tell(text_, colour="gray"):
    return "tellraw @s %s" % R.text(text_, colour)


def sound(name, vol=1, pitch=1):
    return "playsound %s master @s ~ ~ ~ %s %s" % (name, vol, pitch)


def inn(doc, line):
    return "execute in %s run %s" % (doc["engine"]["pocket"]["dimension"], line)


def records(d):
    """[(item index i, record)] over the dungeon as flatten() lays it (the room index of a state holder is i)."""
    return [(i, it["rec"]) for i, it in enumerate(R.flatten(d))]


def holder(slot, i):
    return "#s%dr%d" % (slot["g"], i)


def sign_lines_sbt(lines):
    return [json.dumps(t) for t in lines]


class Ctl(DP.Ctl):
    """The puzzles' per-room context with this module's penalty default."""

    def __init__(self, doc, d, slot, room):
        super().__init__(doc, d, slot, room)
        df = load().get(room["kind"], {}).get("defaults", {})
        pen = self.p.get("penalty_s", df.get("penalty_s", doc["engine"]["clock"]["fall_penalty_s"]))
        self.pen_s = int(pen)
        self.pen = self.pen_s * DP.U(doc)

    def tag(self, name):
        return self.H + "_" + name


def bounded(c, name, default, lo, hi):
    v = c.p.get(name, default)
    if isinstance(v, bool) or not isinstance(v, int) or not (lo <= v <= hi):
        c.fail("params.%s must be an integer %d..%d (is %r)" % (name, lo, hi, v))
    return v


# ------------------------------------------------------------------------------------------------- the bank vault


def bank_cfg(c):
    D = load()["bank_vault"]
    df, lim = D["defaults"], D["limits"]
    r = c.room
    cfg = {"digits": bounded(c, "digits", df["digits"], *lim["digits"]),
           "chests": bounded(c, "chests", df["chests"], *lim["chests"]),
           "max_tries": bounded(c, "max_tries", df["max_tries"], *lim["max_tries"]),
           "cost_s": bounded(c, "clock_cost_s", df["clock_cost_s"], 1, 600),
           "clue_rooms": list(c.p.get("clue_rooms") or [])}
    if c.pen_s < 1:
        c.fail("penalty_s must be at least 1")
    if r["length"] < lim["min_length"] or r["width"] < lim["min_width"] or r["height"] < lim["min_height"]:
        c.fail("a bank vault needs a room of at least %d x %d x %d (this is %d x %d x %d)" % (
            lim["min_length"], lim["min_width"], lim["min_height"], r["length"], r["width"], r["height"]))
    return cfg


def bank_geom(room, n):
    cx = (room["ix0"] + room["ix1"]) // 2
    fy = room["floor_in"]
    h = 2 * n + 1
    pz = room["iz1"] - DEPTH
    return {"cx": cx, "fy": fy, "top": room["box"][4], "h": h, "pz": pz, "x0": cx - h - 1, "x1": cx + h + 1,
            "gate": (cx - 1, fy, pz, cx + 1, fy + 3, pz)}


def _rects(room, n):
    g = bank_geom(room, n)
    return [(g["cx"] - PANEL_HALF, room["iz0"], g["cx"] + PANEL_HALF, room["iz0"] + 2), (g["x0"], g["pz"], g["x1"], room["iz1"])]


def door_clashes(room, rects, margin=2):
    bad = []
    for door in R.room_doors(room):
        x, _y, z = R.inner_cell(room, door)
        for (x0, z0, x1, z1) in rects:
            if x0 - margin <= x <= x1 + margin and z0 - margin <= z <= z1 + margin:
                bad.append("a %s door at (%d, %d) is within %d of a fitting the kind builds in x %d..%d, z %d..%d"
                           % (door["dir"], x, z, margin, x0, x1, z0, z1))
                break
    return bad


def bank_loot_of(params):
    return params.get("loot_by_band") or load()["bank_vault"]["default_loot_by_band"]


def bank_table_id(d, room, key, value):
    return value if isinstance(value, str) else "cobblers:dungeons/bank/%s/%s/b%d" % (d["id"], room["id"], key)


def clue_assignment(cfg):
    """{clue room id: [digit index]}: digits dealt round robin over the named rooms, in order."""
    out = {}
    for j in range(cfg["digits"]):
        out.setdefault(cfg["clue_rooms"][j % len(cfg["clue_rooms"])], []).append(j)
    return out


def build_bank(doc, d, slot, room, theme):
    c = Ctl(doc, d, slot, room)
    cfg = bank_cfg(c)
    B = c.B
    n, digits = cfg["chests"], cfg["digits"]
    g = bank_geom(room, n)
    clash = door_clashes(room, _rects(room, n))
    if clash:
        c.fail("; ".join(clash))
    bands = [b["band"] for b in doc["engine"]["bands"]]
    bad_loot = check_loot(c.lab, bank_loot_of(c.p), bands)
    if bad_loot:
        c.fail("; ".join(bad_loot))
    cx, fy, top, h, pz = g["cx"], g["fy"], g["top"], g["h"], g["pz"]
    iz0, iz1 = room["iz0"], room["iz1"]
    wall = B["console"]
    XR = _XR()
    ops = [fill((cx - PANEL_HALF, fy, iz0, cx + PANEL_HALF, fy + 5, iz0), wall),
           fill((cx - PANEL_HALF, fy, iz0, cx + PANEL_HALF, fy, iz0), B["trim"])]
    lamps = [(cx - (digits - 1) + 2 * j, fy + 5, iz0) for j in range(digits)]
    for p in lamps:
        ops.append(setb(p, B["lamp_off"]))
    btn, sign_at = {}, {}
    for k, (col, row) in KEYPAD_ROW.items():
        x, y = cx - 4 + 2 * col, fy + 1 + 2 * row
        btn[k] = (x, y, iz0 + 1)
        sign_at[k] = (x, y + 1, iz0 + 1)
        ops.append(setb(btn[k], DP.button(B)))
        ops.append(setb(sign_at[k], XR.sign_block(theme, "north", ["", str(k)])))
    # the chamber: a partition across the south end with a 3 x 4 opening (the gate: shut in the shell, see gate_closing),
    # end walls, a plinth and a chest per place, and a sign over the gate
    ops += [fill((g["x0"], fy, pz, g["x1"], top, pz), wall), fill((g["x0"], fy, pz, g["x0"], top, iz1), wall),
            fill((g["x1"], fy, pz, g["x1"], top, iz1), wall), fill(g["gate"], "minecraft:air")]
    ops.append(setb((cx, fy + 4, pz - 1), XR.sign_block(theme, "south", load()["bank_vault"]["messages"]["sign_vault"])))
    xs = [cx - 2 * (n - 1) + 4 * k for k in range(n)]
    chest = [(x, fy, iz1) for x in xs]
    for x, y, z in chest:
        ops.append(fill((x - 1, fy - 1, iz1 - 2, x + 1, fy - 1, iz1), B["plinth"]))

    def block_for(band):
        key, val = DP.loot_for(dict(c.p, loot_by_band=bank_loot_of(c.p)), bands, band)
        if key is None:
            c.fail("loot_by_band has nothing at or below band %d (author a \"1\" entry)" % band)
        return "%s[facing=north]{LootTable:\"%s\"}" % (B["chest"], bank_table_id(d, room, key, val))
    for x, y, z in chest:
        ops.append(setb((x, y, z), block_for(bands[0])))
    H = c.H
    t = c.tag
    # GREED: each chest opened weighs its expected loot, as the vault's (the same entry point)
    DG = _DG()
    gt = DG.load()
    band_cp = {}
    for b in bands:
        _k, val = DP.loot_for(dict(c.p, loot_by_band=bank_loot_of(c.p)), bands, b)
        v = DG.chest_cp(gt, val) if val is not None else None
        if v is None:
            c.fail("the loot at band %d is not priced by data/dungeon_greed.json" % b)
        band_cp[b] = v
    btn_on = "%s[powered=true]" % B["button"]
    f = {}
    for k in range(10):
        lines = [LOADED, "setblock %s %s" % (at(btn[k]), DP.button(B)),
                 "execute unless score %s dg.rs matches 1 run return 0" % H,
                 "execute if score %s dg.rs matches 1 run return 0" % t("j"),
                 "scoreboard players operation %s dg.rs *= #10 dg.t" % t("v"),
                 "scoreboard players add %s dg.rs %d" % (t("v"), k),
                 "scoreboard players add %s dg.rs 1" % t("e")]
        lines += ["execute if score %s dg.rs matches %d run setblock %s %s" % (t("e"), j + 1, at(lamps[j]), B["lamp_on"])
                  for j in range(digits)]
        lines += [DP.sound("minecraft:block.note_block.chime", 1, 0.8 + 0.1 * k),
                  "execute if score %s dg.rs matches %d run function %s" % (t("e"), digits, c.fn("check"))]
        f["press%d" % k] = lines
    f["keys"] = [LOADED] + ["execute if block %s %s run function %s" % (at(btn[k]), btn_on, c.fn("press%d" % k)) for k in range(10)]
    f["check"] = [LOADED, "scoreboard players set %s dg.rs 0" % t("x"),
                  "execute if score %s dg.rs = %s dg.rs run scoreboard players set %s dg.rs 1" % (t("v"), t("c"), t("x")),
                  "scoreboard players set %s dg.rs 0" % t("v"), "scoreboard players set %s dg.rs 0" % t("e"),
                  "execute if score %s dg.rs matches 1 run function %s" % (t("x"), c.fn("unlock")),
                  "execute if score %s dg.rs matches 0 run function %s" % (t("x"), c.fn("wrong"))]
    f["wrong"] = [LOADED, "scoreboard players remove @s dg.clock %d" % c.pen, DP.sound("minecraft:block.anvil.land", 0.6, 1.4),
                  bar(msg(BANK, "wrong", s=c.pen_s), "red"),
                  "scoreboard players add %s dg.rs 1" % t("w")]
    f["wrong"] += ["setblock %s %s" % (at(p), B["lamp_off"]) for p in lamps]
    f["wrong"] += ["execute if score %s dg.rs matches %d.. run function %s" % (t("w"), cfg["max_tries"], c.fn("jam"))]
    f["jam"] = [LOADED, "scoreboard players set %s dg.rs 1" % t("j"), bar(load()["bank_vault"]["messages"]["jam"], "red"),
                DP.sound("minecraft:block.anvil.land", 1, 0.5)]
    cost_u = cfg["cost_s"] * DP.U(doc)
    hc = [t("k%d" % j) for j in range(n)]
    all_open = " ".join("if score %s dg.rs matches 2" % x for x in hc)
    for j in range(n):
        f["open%d" % j] = ([DP.sb_set(hc[j], 2), "scoreboard players remove @s dg.clock %d" % cost_u,
                            bar(msg(BANK, "chest_taken", s=cfg["cost_s"]), "gold"),
                            DP.sound("minecraft:entity.item.pickup", 1, 0.8)] + DG.chest_lines(doc, band_cp))
    tick = [LOADED, "execute if score %s dg.rs matches 1 unless score %s dg.rs matches 1 run function %s" % (H, t("j"), c.fn("keys"))]
    tick += ["execute if score %s dg.rs matches 1 unless data block %s LootTable run function %s" % (hc[j], at(chest[j]), c.fn("open%d" % j))
             for j in range(n)]
    enter = [bar(load()["bank_vault"]["messages"]["hint"], "gold")] + [DP.sb_set(x, 1) for x in hc]
    # the kit's `clear` only flips the room's state (a gate-open room whose clear opens cells reads, to the independent audit,
    # as a progression gate); the vault's own gate is opened by `unlock`, which calls it
    f["unlock"] = [LOADED, inn(doc, "fill %d %d %d %d %d %d minecraft:air" % g["gate"])]
    f["unlock"] += [inn(doc, "setblock %s %s" % (at(p), B["lamp_on"])) for p in lamps]
    f["unlock"] += [DP.sound("minecraft:block.iron_door.open", 1, 0.8), bar(load()["bank_vault"]["messages"]["open"], "gold"),
                    "function %s" % c.fn("clear")]
    reset = ["# the keypad up, the lamps out, the gate shut, the chests from air with the entrant's band's loot, the run's code gone"]
    reset += [inn(doc, "fill %d %d %d %d %d %d %s" % (g["gate"] + (R.gate_block(theme),)))]
    reset += [inn(doc, "setblock %s %s" % (at(btn[k]), DP.button(B))) for k in range(10)]
    reset += [inn(doc, "setblock %s %s" % (at(p), B["lamp_off"])) for p in lamps]
    reset += [inn(doc, "setblock %s minecraft:air" % at(p)) for p in chest]
    for p in chest:
        for b in bands:
            reset.append("execute in %s if score @s dg.band matches %d run setblock %s %s" % (doc["engine"]["pocket"]["dimension"], b, at(p), block_for(b)))
    reset += [DP.sb_set(x, 1) for x in hc]
    reset += [DP.sb_set(t(s), 0) for s in ("e", "v", "w", "j", "x", "c")] + [DP.sb_set(t("d%d" % j), 0) for j in range(digits)]
    expect = [(p, B["lamp_off"]) for p in lamps] + [(btn[k], B["button"]) for k in range(10)] + [(p, B["chest"]) for p in chest]
    attached = [(btn[k], (btn[k][0], btn[k][1], iz0)) for k in range(10)] + [(sign_at[k], (sign_at[k][0], sign_at[k][1], iz0)) for k in range(10)]
    anchors = {"keypad": [[cx, fy, iz0 + 2, 180]], "vault_door": [[cx, fy, pz - 1, 0]], "inside": [[cx, fy, pz + 2, 0]],
               "chests": [[x, fy, iz1 - 1, 0] for x in xs]}
    return {"blocks": ops, "anchors": anchors,
            "reserve": [(cx - PANEL_HALF, fy, iz0, cx + PANEL_HALF, fy + 5, iz0 + 2), (g["x0"], fy - 1, pz - 2, g["x1"], top, iz1)],
            "functions": dict(f, enter=enter, tick=tick, reset=reset),
            "meta": {"extras": BANK, "H": H, "digits": digits, "chests": n, "chest_cells": [list(p) for p in chest], "gate": list(g["gate"]),
                     "buttons": {str(k): list(v) for k, v in btn.items()}, "lamps": [list(p) for p in lamps], "greed_cp": band_cp,
                     "cfg": cfg, "expect": expect, "attached": attached}}


def check_loot(label, lb, bands):
    """The vault's loot-table checks (DP.check_loot) on a given loot_by_band."""
    return DP.check_loot(label, {"loot_by_band": lb}, bands)


# ------------------------------------------------------------------------------------------------- the wishing well

WELL_RING = 2          # the ring is 5 x 5; the pool 3 x 3
EJECT_DZ = 3.5         # a refused item is thrown back this far south of the well's centre (outside the ring)


def well_cfg(c):
    D = load()["wishing_well"]
    df, lim = D["defaults"], D["limits"]
    r = c.room
    cfg = {"throws": bounded(c, "throws", df["throws"], *lim["throws"]), "min_cp": bounded(c, "min_cp", df["min_cp"], 1, 100000)}
    if r["length"] < lim["min_length"] or r["width"] < lim["min_width"] or r["height"] < lim["min_height"]:
        c.fail("a wishing well needs a room of at least %d x %d x %d (this is %d x %d x %d)" % (
            lim["min_length"], lim["min_width"], lim["min_height"], r["length"], r["width"], r["height"]))
    return cfg


def centre(room):
    return (room["ix0"] + room["ix1"]) // 2, (room["iz0"] + room["iz1"]) // 2


def build_well(doc, d, slot, room, theme):
    c = Ctl(doc, d, slot, room)
    cfg = well_cfg(c)
    B = c.B
    cx, cz = centre(room)
    fy = room["floor_in"]
    ops = [fill((cx - 2, fy, cz - 2, cx + 2, fy, cz + 2), B["plinth"]), fill((cx - 1, fy, cz - 1, cx + 1, fy, cz + 1), "minecraft:water")]
    for sx in (-2, 2):
        for sz in (-2, 2):
            ops.append(fill((cx + sx, fy + 1, cz + sz, cx + sx, fy + 3, cz + sz), B["console"]))
    for a, b in (((-2, -2), (2, -2)), ((-2, 2), (2, 2)), ((-2, -2), (-2, 2)), ((2, -2), (2, 2))):
        ops.append(fill((cx + a[0], fy + 4, cz + a[1], cx + b[0], fy + 4, cz + b[1]), B["trim"]))
    H, t = c.H, c.tag
    box = "x=%d,y=%d,z=%d,dx=2,dy=2,dz=2" % (cx - 1, fy, cz - 1)
    eject = "tp @s %.1f %d %.1f" % (cx + 0.5, fy + 1, cz + EJECT_DZ)
    f = {}
    f["take"] = [LOADED, "execute if score #wn %s matches 1.. run return 0" % OBJ_T,
                 "execute if score %s dg.rs matches %d.. run return run function %s" % (t("t"), cfg["throws"], c.fn("eject_dry")),
                 "function %s" % _D().F("well/value"),
                 "execute unless score #iv %s matches %d.. run return run function %s" % (OBJ_T, cfg["min_cp"], c.fn("eject_cheap")),
                 "kill @s", "scoreboard players set #wn %s 1" % OBJ_T]
    f["eject_dry"] = [eject, "scoreboard players set #wn %s 3" % OBJ_T]
    f["eject_cheap"] = [eject, "scoreboard players set #wn %s 2" % OBJ_T]
    f["wish"] = [LOADED, "execute if score #wn %s matches 2 run %s" % (OBJ_T, bar(msg(WELL, "cheap"), "gray")),
                 "execute if score #wn %s matches 3 run %s" % (OBJ_T, bar(msg(WELL, "dry"), "gray")),
                 "execute unless score #wn %s matches 1 run return 0" % OBJ_T,
                 "scoreboard players add %s dg.rs 1" % t("t"),
                 DP.sound("minecraft:entity.player.splash", 1, 1.0),
                 "execute store result score #wr %s run random value 1..100" % OBJ_T,
                 "function %s" % _D().F("well/pay")]
    tick = [LOADED, "scoreboard players set #wn %s 0" % OBJ_T, "scoreboard players set #iv %s 0" % OBJ_T,
            "execute in %s as @e[type=minecraft:item,%s] run function %s" % (doc["engine"]["pocket"]["dimension"], box, c.fn("take")),
            "execute if score #wn %s matches 1.. run function %s" % (OBJ_T, c.fn("wish"))]
    enter = [bar(msg(WELL, "hint"), "aqua"), DP.sb_set(t("t"), 0)]
    reset = [DP.sb_set(t("t"), 0)]
    expect = [((cx + a, fy, cz + b), B["plinth"]) for a, b in ((-2, -2), (2, 2), (-2, 2), (2, -2), (0, -2), (0, 2))]
    expect += [((cx, fy, cz), "minecraft:water")]
    return {"blocks": ops, "anchors": {"well": [[cx, fy, cz]], "throw": [[cx, fy, cz + 3, 180]]},
            "reserve": [(cx - 3, fy, cz - 3, cx + 3, fy + 4, cz + 4)],
            "functions": dict(f, enter=enter, tick=tick, reset=reset),
            "meta": {"extras": WELL, "H": H, "cfg": cfg, "box": box, "expect": expect}}


# ------------------------------------------------------------------------------------------------- the bait room


def bait_cfg(c):
    D = load()["bait_room"]
    lim = D["limits"]
    r = c.room
    if r["length"] < lim["min_length"] or r["width"] < lim["min_width"] or r["height"] < lim["min_height"]:
        c.fail("a bait room needs a room of at least %d x %d x %d (this is %d x %d x %d)" % (
            lim["min_length"], lim["min_width"], lim["min_height"], r["length"], r["width"], r["height"]))
    lure = c.p.get("lure_room")
    if not isinstance(lure, str) or not lure:
        c.fail("params.lure_room must name the living room the lured Pokemon appears in")
    return {"lure_room": lure}


def build_bait(doc, d, slot, room, theme):
    c = Ctl(doc, d, slot, room)
    cfg = bait_cfg(c)
    B = c.B
    cx, cz = centre(room)
    fy = room["floor_in"]
    ops = [fill((cx - 1, fy, cz - 1, cx + 1, fy, cz + 1), B["plinth"]), setb((cx, fy, cz), B["lamp_on"])]
    for sx in (-2, 2):
        for sz in (-2, 2):
            ops.append(fill((cx + sx, fy, cz + sz, cx + sx, fy + 2, cz + sz), B["console"]))
    H, t = c.H, c.tag
    box = "x=%d,y=%d,z=%d,dx=2,dy=1,dz=2" % (cx - 1, fy + 1, cz - 1)
    eject = "tp @s %.1f %d %.1f" % (cx + 0.5, fy + 1, cz + EJECT_DZ)
    F = _D().F
    f = {}
    f["take"] = [LOADED, "execute if score #wn %s matches 1.. run return 0" % OBJ_T,
                 "scoreboard players set #bi %s 0" % OBJ_T, "function %s" % F("bait/id"),
                 "execute if score #bi %s matches 0 run return run function %s" % (OBJ_T, c.fn("eject_cheap")),
                 "execute if score #bk %s matches 1.. run return run function %s" % (OBJ_T, c.fn("eject_full")),
                 "execute store result score #in %s run data get entity @s Item.count" % OBJ_T,
                 "execute if score #in %s matches 2.. run function %s" % (OBJ_T, c.fn("lessen")),
                 "execute if score #in %s matches ..1 run kill @s" % OBJ_T,
                 "scoreboard players set #wn %s 1" % OBJ_T]
    f["lessen"] = ["scoreboard players remove #in %s 1" % OBJ_T, "execute store result entity @s Item.count int 1 run scoreboard players get #in %s" % OBJ_T]
    f["eject_cheap"] = [eject, "scoreboard players set #wn %s 2" % OBJ_T]
    f["eject_full"] = [eject, "scoreboard players set #wn %s 3" % OBJ_T]
    f["lay"] = [LOADED, "execute if score #wn %s matches 2 run %s" % (OBJ_T, bar(msg(BAIT, "cheap"), "gray")),
                "execute if score #wn %s matches 3 run %s" % (OBJ_T, bar(msg(BAIT, "full"), "gray")),
                "execute unless score #wn %s matches 1 run return 0" % OBJ_T,
                "scoreboard players operation @s %s = #bi %s" % (OBJ_BAIT, OBJ_T),
                bar(msg(BAIT, "laid"), "green"), DP.sound("minecraft:block.note_block.chime", 1, 0.6)]
    tick = [LOADED, "scoreboard players set #wn %s 0" % OBJ_T,
            "scoreboard players operation #bk %s = @s %s" % (OBJ_T, OBJ_BAIT),
            "execute in %s as @e[type=minecraft:item,%s] run function %s" % (doc["engine"]["pocket"]["dimension"], box, c.fn("take")),
            "execute if score #wn %s matches 1.. run function %s" % (OBJ_T, c.fn("lay"))]
    enter = [bar(msg(BAIT, "hint"), "aqua")]
    reset = [DP.sb_set(t("z"), 0)]
    expect = [((cx + a, fy, cz + b), B["plinth"]) for a, b in ((-1, -1), (1, 1), (-1, 1), (1, -1))] + [((cx, fy, cz), B["lamp_on"])]
    return {"blocks": ops, "anchors": {"center": [cx, fy + 1, cz], "stand": [[cx, fy, cz + 3, 180]]},
            "reserve": [(cx - 3, fy, cz - 3, cx + 3, fy + 3, cz + 4)],
            "functions": dict(f, enter=enter, tick=tick, reset=reset),
            "meta": {"extras": BAIT, "H": H, "cfg": cfg, "box": box, "expect": expect}}


R.register(BANK, build_bank, dress="light", outline=False)
R.register(WELL, build_well, dress="light", outline=False)
R.register(BAIT, build_bait, dress="light", outline=False)


# ------------------------------------------------------------------------------------------------- the gate, shut in the shell


def _wrap_gate_closing():
    base = R.gate_closing_ops
    if getattr(base, "_dg_extras", False):
        return

    def gate_closing_ops(room, theme):
        out = base(room, theme)
        if room.get("kind") == BANK:
            n = int((room.get("params") or {}).get("chests", load()["bank_vault"]["defaults"]["chests"]))
            out = out + [fill(bank_geom(room, n)["gate"], R.gate_block(theme))]
        return out
    gate_closing_ops._dg_extras = True
    R.gate_closing_ops = gate_closing_ops


_wrap_gate_closing()


# ------------------------------------------------------------------------------------------------- reaching into other rooms


def _targets(d):
    """The bank vaults and bait rooms of the (resolved) dungeon: [(index, record)]."""
    return [(i, r) for i, r in records(d) if r["kind"] in (BANK, BAIT)]


def _wall_cells(ctx, seed_salt):
    """Open floor cells beside a wall whose sign cell (floor + 2) is air and whose wall block there is solid, off the
    trail and the kept cells, best first (a seeded shuffle, so the four slots agree)."""
    room, grid = ctx.room, ctx.grid
    out = []
    for x in range(room["ix0"], room["ix1"] + 1):
        for z in range(room["iz0"], room["iz1"] + 1):
            if not ctx.open(x, z) or ctx.reserved(x, z):
                continue
            y = ctx.floor(x, z)
            if y is None or y + 2 > room["box"][4]:
                continue
            for face, (dx, dz) in (("north", (0, -1)), ("south", (0, 1)), ("west", (-1, 0)), ("east", (1, 0))):
                if ctx.open(x + dx, z + dz):
                    continue
                if G.base(grid.block_at(x, y + 2, z)) != "minecraft:air" or G.classify(grid.block_at(x + dx, y + 2, z + dz)) != G.SOLID:
                    continue
                out.append((x, y + 2, z, face))
    out.sort()
    ctx.rng.shuffle(out)
    return out


def post_dress(ctx):
    """POST_DRESS_FNS: the clue sign of every bank vault that names this room, and the lure of a bait room that does."""
    room, d, doc = ctx.room, ctx.d, ctx.doc
    if not any(r["kind"] in (BANK, BAIT) for r in R._walk_records(d.get("rooms", []))):
        return
    targets = _targets(d)
    if not targets:
        return
    dim = doc["engine"]["pocket"]["dimension"]
    b = ctx.built
    XR = _XR()
    for i, rec in targets:
        p = rec.get("params") or {}
        if rec["kind"] == BANK and room["id"] in (p.get("clue_rooms") or []) and rec["id"] != room["id"]:
            digits = int(p.get("digits", load()["bank_vault"]["defaults"]["digits"]))
            cfg = {"digits": digits, "clue_rooms": list(p.get("clue_rooms") or [])}
            js = clue_assignment(cfg).get(room["id"], [])
            if not js:
                continue
            cells = _wall_cells(ctx, rec["id"])
            if not cells:
                continue
            x, y, z, face = cells[0]
            header = load()["bank_vault"]["clue_header"].get(d.get("theme"), "SLIP")
            lines = [header] + ["NO.%d: ?" % (j + 1) for j in js]
            ctx.add(setb((x, y, z), XR.sign_block(ctx.theme, face, lines)))
            Hb = holder(ctx.slot, i)
            enter, reset = [], []
            for line_no, j in enumerate(js, 1):
                for v in range(10):
                    enter.append("execute if score %s_d%d dg.rs matches %d in %s run data modify block %s front_text.messages[%d] set value '%s'"
                                 % (Hb, j, v, dim, at((x, y, z)), line_no, json.dumps("NO.%d: %d" % (j + 1, v))))
                reset.append("execute in %s run data modify block %s front_text.messages[%d] set value '%s'"
                             % (dim, at((x, y, z)), line_no, json.dumps("NO.%d: ?" % (j + 1))))
            b.functions["enter"] = b.functions.get("enter", []) + ["# clue sign for vault %s: the run's digits %s" % (rec["id"], [j + 1 for j in js])] + enter
            b.functions["reset"] = b.functions.get("reset", []) + reset
            b.meta.setdefault("clue_signs", []).append({"vault": rec["id"], "pos": [x, y, z], "face": face, "digits": js, "lines": lines})
        if rec["kind"] == BAIT and room["id"] == p.get("lure_room") and rec["id"] != room["id"]:
            lure_hook(ctx, i, rec)


def tier_of(bait_room, bait):
    """The bait's tier record ({shiny_chance, alpha_chance, why}), or None while the table has no `tiers` (no rolls)."""
    tiers = bait_room.get("tiers")
    if not tiers:
        return None
    return tiers.get(bait.get("tier"))


def threshold(p):
    """A chance as a count out of ROLL_N: the roll `random value 1..ROLL_N` succeeds when it is 1..threshold."""
    return int(round(float(p) * ROLL_N))


def lure_roll_lines(bait_room, holder_z):
    """The lure's two SEPARATE rolls, as function lines: one `random value` for shiny (#lrs) and a second for alpha (#lra),
    then the flags #lfs / #lfa set to 1 by the bait's tier (a chance of 0 writes no line: it can never set the flag). A
    lure may therefore be shiny only, alpha only, both or neither. [] when the table has no `tiers` (behaviour unchanged)."""
    if not bait_room.get("tiers"):
        return []
    out = ["# the lure's two SEPARATE rolls (random value 1..%d each): shiny, then alpha; the bait's tier sets each chance" % ROLL_N,
           "execute store result score %s %s run random value 1..%d" % (ROLL_S, OBJ_T, ROLL_N),
           "execute store result score %s %s run random value 1..%d" % (ROLL_A, OBJ_T, ROLL_N),
           "scoreboard players set %s %s 0" % (FLAG_S, OBJ_T), "scoreboard players set %s %s 0" % (FLAG_A, OBJ_T)]
    for bi, bait in enumerate(bait_room["baits"], 1):
        t = tier_of(bait_room, bait)
        if t is None:
            continue
        for roll, flag, key in ((ROLL_S, FLAG_S, "shiny_chance"), (ROLL_A, FLAG_A, "alpha_chance")):
            n = threshold(t[key])
            if n > 0:
                out.append("execute if score %s dg.rs matches %d if score %s %s matches 1..%d run scoreboard players set %s %s 1"
                           % (holder_z, bi, roll, OBJ_T, n, flag, OBJ_T))
    return out


def lure_variants(bait_room, bait):
    """[(extra execute condition, extra props)] of the spawn lines one bait and band need: one plain line while the table has
    no tiers (the text this module always wrote), else one per (shiny, alpha) outcome its tier can produce. Property syntax:
    PROP_SHINY / PROP_ALPHA (see there)."""
    t = tier_of(bait_room, bait)
    if t is None:
        return [("", "")]
    out = []
    ns, na = threshold(t["shiny_chance"]), threshold(t["alpha_chance"])
    for s in (0, 1):
        if (s == 1 and ns == 0) or (s == 0 and ns >= ROLL_N):
            continue
        for a in (0, 1):
            if (a == 1 and na == 0) or (a == 0 and na >= ROLL_N):
                continue
            out.append((" if score %s %s matches %d if score %s %s matches %d" % (FLAG_S, OBJ_T, s, FLAG_A, OBJ_T, a),
                        (" " + PROP_SHINY if s else "") + (" " + PROP_ALPHA if a else "")))
    return out


def lure_lines(BR, band_props, Hz, dim, at_fn, bind_fn, keep, pos, bind_radius):
    """The lure function's body: the rolls (none while the table has no `tiers`), then per bait and band the spawn line(s)
    (the macro `spawnpokemonat`, one per shiny/alpha outcome the bait's tier can produce) and the bind line.
    `band_props` is {band: the base props string (level=...)}."""
    from dungeon_fights import macro_args
    x, y, z = pos
    lines = lure_roll_lines(BR, Hz)
    for bi, bait in enumerate(BR["baits"], 1):
        for bn, props in band_props.items():
            sp = bait["species_by_band"].get(str(bn))
            if not sp:
                continue
            cond = "if score %s dg.rs matches %d if score @s dg.band matches %d" % (Hz, bi, bn)
            for flag_cond, extra in lure_variants(BR, bait):
                lines.append("execute %s%s in %s run function %s %s" % (cond, flag_cond, dim, at_fn, macro_args(
                    x="%.1f" % (x + 0.5), y=str(y), z="%.1f" % (z + 0.5), species=sp, props=props + extra)))
            lines.append("execute %s in %s positioned %.1f %d %.1f as @e[type=cobblemon:pokemon,tag=!%s,distance=..%g,sort=nearest,limit=1] run function %s"
                         % (cond, dim, x + 0.5, y, z + 0.5, keep, bind_radius, bind_fn))
    return lines


def lure_hook(ctx, i, rec):
    doc, room = ctx.doc, ctx.room
    import dungeon_prize as DPz
    import dungeon_fights as DF
    D = _D()
    dim = doc["engine"]["pocket"]["dimension"]
    g = ctx.slot["g"]
    Hz = holder(ctx.slot, i) + "_z"
    fl = R.flags_of(room["kind"])
    grid = ctx.grid
    reach = G.walk(grid, [grid.local(*R.room_start(room))], jumps=fl["jumps"])
    cx, cz = centre(room)
    want = (cx, cz + 3)
    best = None
    for (x, y, z) in ctx.standable_cells():
        if grid.local(x, y, z) not in reach or G.classify(grid.block_at(x, y, z)) == G.WATER or G.classify(grid.block_at(x, y - 1, z)) != G.SOLID:
            continue
        key = (abs(x - want[0]) + abs(z - want[1]), x, z)
        if best is None or key < best[0]:
            best = (key, (x, y, z))
    if best is None:
        raise R.RoomError("%s room %s: no reachable floor to lure a Pokemon onto" % (ctx.d["id"], room["id"]))
    x, y, z = best[1]
    keep = doc["engine"]["sweep"]["keep_tag"]
    BR = load()["bait_room"]
    band_props = {b["band"]: DF.props_of(DPz.level_at(doc, b["band"]), False, False) for b in doc["engine"]["bands"]}
    lines = lure_lines(BR, band_props, Hz, dim, D.F("extras/s%d/at" % g), D.F("extras/s%d/bind" % g), keep, (x, y, z), DF.BIND_RADIUS)
    b_ = ctx.built
    b_.functions["lure"] = [LOADED, "# As the member, the room's first pass: the Pokemon the run's bait brings (the bait room's lure score, by band)"] + lines + [
        bar(msg(BAIT, "lure"), "light_purple")]
    b_.functions["enter"] = b_.functions.get("enter", []) + ["execute if score %s dg.rs matches 1.. run function %s" % (Hz, R.room_fn(ctx.d, room, ctx.slot, "lure"))]
    b_.functions["reset"] = b_.functions.get("reset", []) + [
        "execute in %s as @e[type=cobblemon:pokemon,tag=dg.s%d,tag=%s] run runmolang \"q.entity.discard;\"" % (dim, g, LURE_TAG)]
    b_.meta["lure"] = {"pos": [x, y, z], "holder": Hz, "bait_room": rec["id"]}


LURE_TAG = "dg.lure"
R.POST_DRESS_FNS.append(post_dress)


# ------------------------------------------------------------------------------------------------- the slot's lines


def start_lines(doc, slot):
    d = slot["dungeon"]
    out = []
    if not R.has_rooms(d) or not any(r["kind"] in (BANK, BAIT) for r in R.all_records(d)):
        return out
    for b in R.slot_build(doc, d, slot):
        m = b.meta
        H = m.get("H")
        if m.get("extras") == BANK:
            n = m["digits"]
            out.append("# bank vault %s: this run's code, rolled here (the sigil is spent: no free re-roll)" % b.room["id"])
            out += ["scoreboard players set %s_%s dg.rs 0" % (H, s) for s in ("e", "v", "w", "j", "x")]
            out += ["execute store result score %s_d%d dg.rs run random value 0..9" % (H, j) for j in range(n)]
            out.append("scoreboard players set %s_c dg.rs 0" % H)
            for j in range(n):
                out += ["scoreboard players operation %s_c dg.rs *= #10 dg.t" % H, "scoreboard players operation %s_c dg.rs += %s_d%d dg.rs" % (H, H, j)]
        if m.get("extras") == BAIT:
            out += ["# bait room %s: the player's stored bait becomes this run's lure, once" % b.room["id"],
                    "scoreboard players set %s_z dg.rs 0" % H,
                    "execute if score @s %s matches 1.. run scoreboard players operation %s_z dg.rs = @s %s" % (OBJ_BAIT, H, OBJ_BAIT),
                    "execute if score @s %s matches 1.. run scoreboard players set @s %s 0" % (OBJ_BAIT, OBJ_BAIT)]
    return out


def any_rooms(doc, kinds):
    for d in doc["dungeons"]:
        if R.has_rooms(d) and any(r["kind"] in kinds for r in R.all_records(d)):
            return True
    return False


def patch_functions(doc, fns):
    """tools/dungeon.py build(): objectives at load, the code and the lure at each slot's threshold, the lure's cleanup."""
    D = _D()
    if any_rooms(doc, (BAIT,)):
        line = "scoreboard objectives add %s dummy" % OBJ_BAIT
        if line not in fns["load"]:
            fns["load"] = list(fns["load"]) + [line]
    import dungeon_life as DL
    for s in D.slots(doc):
        st = start_lines(doc, s)
        if st:
            fns["slot/s%d/start" % s["g"]] = list(fns["slot/s%d/start" % s["g"]]) + st
        if lure_slot(doc, s):
            free, tend = DL.discard_lines(doc, s["g"])
            for name, line in (("slot/s%d/free" % s["g"], free), ("slot/s%d/tend" % s["g"], tend)):
                if line not in fns[name]:
                    fns[name] = list(fns[name]) + [line]


def lure_slot(doc, slot):
    d = slot["dungeon"]
    return R.has_rooms(d) and any(r["kind"] == BAIT for r in R.all_records(d))


def priced_ids(table):
    """[(item id, cp)] GREED prices that count for the well: every item row not a placeholder, every group's ids."""
    out = []
    for it, row in table["items"].items():
        if row.get("source") != "unpriced" and int(row["cp"]) > 0:
            out.append((it, int(row["cp"])))
    for g in table.get("groups", {}).values():
        out += [(i, int(g["cp"])) for i in g["ids"] if int(g["cp"]) > 0]
    return out


def band_rows(doc):
    return [b["band"] for b in doc["engine"]["bands"]]


def functions(doc):
    """{function name under cobblers:dungeons/: lines}: the well's value, give and pay, the bait table, and per slot with a
    bait room the macro spawn and the claim. Nothing at all while no dungeon authors one of the kinds."""
    D = _D()
    F, HEAD = D.F, D.HEAD
    out = {}
    X = load()
    if any_rooms(doc, (WELL,)):
        DG = _DG()
        gt = DG.load()
        W = X["wishing_well"]
        val = [HEAD, "# As a thrown item entity: its value in cp (GREED's table, placeholders excluded) times its count, in #iv",
               "scoreboard players set #ic %s 0" % OBJ_T]
        val += ["execute if data entity @s {Item:{id:\"%s\"}} run scoreboard players set #ic %s %d" % (i, OBJ_T, cp) for i, cp in priced_ids(gt)]
        val += ["execute store result score #in %s run data get entity @s Item.count" % OBJ_T,
                "scoreboard players operation #iv %s = #ic %s" % (OBJ_T, OBJ_T),
                "scoreboard players operation #iv %s *= #in %s" % (OBJ_T, OBJ_T)]
        out["well/value"] = val
        out["well/give"] = [HEAD, "# (macro: item, n) the reward", "$give @s $(item) $(n)"]
        pay = [HEAD, "# As the member: the pay for the thrown value #iv at the roll #wr, by the band's table"]
        pay += ["execute if score @s %s matches %d run return run function %s" % (D.OBJ["band"], b, F("well/b%d" % b)) for b in band_rows(doc)]
        out["well/pay"] = pay
        out["well/nothing"] = [HEAD, "# As the member: the well keeps the gift", tell(msg(WELL, "nothing"), "gray"),
                               sound("minecraft:block.note_block.bass", 1, 0.6)]
        for b in band_rows(doc):
            shares = W["shares_by_band"][str(b)]
            ladder = W["ladders_by_band"][str(b)]
            ln = [HEAD, "# As the member, band %d: the share of the thrown value paid (random value 1..100), then the dearest currency it reaches" % b,
                  "scoreboard players set #wm %s 0" % OBJ_T]
            lo = 1
            for w, share in shares:
                if share:
                    ln.append("execute if score #wr %s matches %d..%d run scoreboard players set #wm %s %d" % (OBJ_T, lo, lo + w - 1, OBJ_T, share))
                lo += w
            ln += ["scoreboard players operation #amt %s = #iv %s" % (OBJ_T, OBJ_T), "scoreboard players operation #amt %s *= #wm %s" % (OBJ_T, OBJ_T),
                   "scoreboard players operation #amt %s /= #100 %s" % (OBJ_T, OBJ_T)]
            prices = [(DG.item_cp(gt, it), it, nm) for it, nm in ladder]
            for k in range(len(prices) - 1, -1, -1):
                ln.append("execute if score #amt %s matches %d.. run return run function %s" % (OBJ_T, prices[k][0], F("well/b%d/p%d" % (b, k))))
            ln.append("function %s" % F("well/nothing"))
            out["well/b%d" % b] = ln
            for k, (cp, it, nm) in enumerate(prices):
                out["well/b%d/p%d" % (b, k)] = [
                    HEAD, "# As the member: pay #amt in %s at %d cp each (floor), at most %d, and charge the gain over the thrown value" % (it, cp, W["limits"]["max_count"]),
                    "scoreboard players operation #q %s = #amt %s" % (OBJ_T, OBJ_T), "scoreboard players set #cc %s %d" % (OBJ_T, cp),
                    "scoreboard players operation #q %s /= #cc %s" % (OBJ_T, OBJ_T),
                    "execute if score #q %s matches %d.. run scoreboard players set #q %s %d" % (OBJ_T, W["limits"]["max_count"] + 1, OBJ_T, W["limits"]["max_count"]),
                    "execute store result storage %s well.n int 1 run scoreboard players get #q %s" % (STORE, OBJ_T),
                    "data modify storage %s well.item set value \"%s\"" % (STORE, it),
                    "function %s with storage %s well" % (F("well/give"), STORE),
                    "tellraw @s [{\"text\":\"%s \",\"color\":\"gold\"},{\"score\":{\"name\":\"#q\",\"objective\":\"%s\"},\"color\":\"gold\"},{\"text\":\" %s.\",\"color\":\"gold\"}]"
                    % (msg(WELL, "returns"), OBJ_T, nm),
                    sound("minecraft:entity.experience_orb.pickup", 1, 1.0),
                    "scoreboard players operation #gv %s = #q %s" % (OBJ_T, OBJ_T), "scoreboard players operation #gv %s *= #cc %s" % (OBJ_T, OBJ_T),
                    "scoreboard players operation #gv %s -= #iv %s" % (OBJ_T, OBJ_T),
                    "function %s" % F("greed/add")]
    if any_rooms(doc, (BAIT,)):
        ids = [HEAD, "# As a thrown item entity: which bait it is, in #bi (the table's 1-based index), else untouched"]
        ids += ["execute if data entity @s {Item:{id:\"%s\"}} run scoreboard players set #bi %s %d" % (b["id"], OBJ_T, i)
                for i, b in enumerate(X["bait_room"]["baits"], 1)]
        out["bait/id"] = ids
        keep = doc["engine"]["sweep"]["keep_tag"]
        exempt = D.blackout_terms()["exempt"]
        for s in D.slots(doc):
            if not lure_slot(doc, s):
                continue
            g = s["g"]
            out["extras/s%d/at" % g] = [HEAD, "# (macro: x, y, z, species, props) the MACRO spawn (EXP-046: a plain `spawnpokemonat` parsed at boot does nothing)",
                                        "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]
            out["extras/s%d/bind" % g] = [
                HEAD, "# As the Pokemon a bait has just brought into slot %d: kept from the sweep, the slot's, the blackout's exempt tag, this run's," % g,
                "# kept from the despawner; the lure tag lets its room's reset find it (a catch weighs as an ambient one: GREED)",
                "tag @s add %s" % keep, "tag @s add dg.s%d" % g, "tag @s add %s" % exempt, "tag @s add %s" % LURE_TAG,
                "scoreboard players operation @s %s = #s%d %s" % (D.OBJ["run"], g, D.OBJ["run"]),
                "data merge entity @s {PersistenceRequired:1b}"]
    return out


def pack_files(doc):
    """{path: text}: the loot tables of every bank vault with item-stack loot."""
    out = {}
    for d in doc["dungeons"]:
        if not R.has_rooms(d):
            continue
        for r in R.all_records(d):
            if r["kind"] != BANK:
                continue
            for k, v in sorted(bank_loot_of(r.get("params") or {}).items(), key=lambda kv: int(kv[0])):
                if isinstance(v, list):
                    out["data/cobblers/loot_table/dungeons/bank/%s/%s/b%d.json" % (d["id"], r["id"], int(k))] = json.dumps(DP.loot_table(v), indent=2) + "\n"
    return out


# ------------------------------------------------------------------------------------------------- the checks

_JAR = {}


def jar_names(path):
    if str(path) not in _JAR:
        _JAR[str(path)] = None
        if Path(path).is_file():
            with zipfile.ZipFile(path) as z:
                _JAR[str(path)] = set(z.namelist())
    return _JAR[str(path)]


def item_known(item):
    """True/False when a jar on this machine can tell, None when it cannot (the check then does not guess)."""
    ns, name = item.split(":", 1)
    if ns == "cobblemon":
        names = jar_names(COBBLEMON_JAR)
        return None if names is None else ("assets/cobblemon/models/item/%s.json" % name) in names
    if ns == "minecraft":
        try:
            import town_character as TC
            jar = TC.default_vanilla_jar()
        except Exception:      # noqa: BLE001
            return None
        names = jar_names(jar) if jar else None
        if names is None:
            return None
        return ("assets/minecraft/models/item/%s.json" % name) in names or ("assets/minecraft/items/%s.json" % name) in names
    return None


def species_labels():
    import dungeon_prize as DPz
    return DPz.jar_labels()


def table_problems(doc, force=False):
    """The well's and the bait table's checks, once per dungeon check (force: even when no dungeon authors the kind)."""
    bad = []
    X = load()
    bands = band_rows(doc)
    if force or any_rooms(doc, (WELL,)):
        W = X["wishing_well"]
        DG = _DG()
        gt = DG.load()
        ev_cap = float(W["ev_cap"])
        for b in bands:
            sh = W["shares_by_band"].get(str(b))
            if not (isinstance(sh, list) and sh and all(isinstance(x, list) and len(x) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in x) for x in sh)):
                bad.append("wishing_well shares_by_band[%d] is a list of [weight, share percent] integers" % b)
                continue
            if sum(w for w, _s in sh) != 100 or any(w < 1 for w, _s in sh):
                bad.append("wishing_well band %d: the weights must be positive and sum to 100 (the well rolls 1..100)" % b)
            if any(not (0 <= s <= 500) for _w, s in sh):
                bad.append("wishing_well band %d: a share is 0..500 percent" % b)
            ev = sum(w * s for w, s in sh) / 10000.0
            if ev > ev_cap:
                bad.append("wishing_well band %d: the expected share of the thrown value is %.3f, over ev_cap %.2f (the well would beat the bank)" % (b, ev, ev_cap))
            if not any(s == 0 for _w, s in sh):
                bad.append("wishing_well band %d: a gamble has a chance of nothing" % b)
            if not any(s > 100 for _w, s in sh):
                bad.append("wishing_well band %d: a gamble has a chance of more than was thrown" % b)
            lad = W["ladders_by_band"].get(str(b))
            if not (isinstance(lad, list) and lad):
                bad.append("wishing_well ladders_by_band[%d] is a list of [item, plural name]" % b)
                continue
            prev = 0
            for it, nm in lad:
                cp = DG.item_cp(gt, it)
                row = gt["items"].get(it)
                if not ID.match(it) or cp is None or cp <= 0 or (row or {}).get("source") == "unpriced":
                    bad.append("wishing_well band %d: ladder item %r has no GREED price (or only a placeholder)" % (b, it))
                    continue
                if cp <= prev:
                    bad.append("wishing_well band %d: ladder item %s (%d cp) is not dearer than the one before" % (b, it, cp))
                prev = cp
                if item_known(it) is False:
                    bad.append("wishing_well band %d: ladder item %s is not an item in the jar" % (b, it))
            first = DG.item_cp(gt, lad[0][0]) or 10 ** 9
            smallest = min((s for _w, s in sh if s > 0), default=0)
            floor_cp = W["defaults"]["min_cp"] * smallest / 100.0
            if first > floor_cp:
                bad.append("wishing_well band %d: the first ladder item costs %d cp but the smallest pay at min_cp %d is %.0f: a small win would pay nothing"
                           % (b, first, W["defaults"]["min_cp"], floor_cp))
    if force or any_rooms(doc, (BAIT,)):
        labels = species_labels()
        seen = set()
        for i, bait in enumerate(X["bait_room"]["baits"], 1):
            who = "bait_room bait %d (%s)" % (i, bait.get("id"))
            if not ID.match(bait.get("id", "")) or bait["id"] in seen:
                bad.append("%s: an item id, once" % who)
            seen.add(bait.get("id"))
            if item_known(bait["id"]) is False:
                bad.append("%s: not an item in the jar" % who)
            sb = bait.get("species_by_band") or {}
            for b in bands:
                sp = sb.get(str(b))
                if not (isinstance(sp, str) and SPECIES.match(sp)):
                    bad.append("%s: band %d needs a lowercase species" % (who, b))
                elif labels is not None:
                    if sp not in labels:
                        bad.append("%s: %s is not a species in the Cobblemon 1.8.0 jar" % (who, sp))
                    elif labels[sp] & LEGEND:
                        bad.append("%s: %s is a legendary, mythical, Ultra Beast or paradox: a lure is an ordinary catch (those are the prize)" % (who, sp))
        bad += tier_problems(X["bait_room"])
    return bad


def tier_problems(bait_room):
    """The bait tiers' checks (data shape: bait_room.tiers {id: {shiny_chance, alpha_chance, why}}, each bait's `tier` and `source`).
    No `tiers` key: a bait may not name a tier (nothing would roll it); with it: every bait names one that exists."""
    bad = []
    tiers = bait_room.get("tiers")
    baits = bait_room["baits"]
    if tiers is None:
        return ["bait_room bait %d (%s): names tier %r but the table has no `tiers`" % (i, b.get("id"), b["tier"])
                for i, b in enumerate(baits, 1) if "tier" in b]
    if not (isinstance(tiers, dict) and tiers):
        return ["bait_room.tiers is an object of tier id -> {shiny_chance, alpha_chance, why}"]
    for tid, t in tiers.items():
        who = "bait_room tier %r" % tid
        if not isinstance(t, dict):
            bad.append("%s: an object" % who)
            continue
        for key in ("shiny_chance", "alpha_chance"):
            v = t.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not (0 <= v <= 1):
                bad.append("%s: %s must be a number in [0, 1] (is %r)" % (who, key, v))
            elif abs(v * ROLL_N - round(v * ROLL_N)) > 1e-6:
                bad.append("%s: %s %r is finer than the roll's 1 in %d" % (who, key, v, ROLL_N))
        if not (isinstance(t.get("why"), str) and t["why"].strip()):
            bad.append("%s: needs a non-empty `why`" % who)
    for i, b in enumerate(baits, 1):
        who = "bait_room bait %d (%s)" % (i, b.get("id"))
        if not isinstance(b.get("tier"), str) or b["tier"] not in tiers:
            bad.append("%s: tier %r is not one of tiers %s" % (who, b.get("tier"), sorted(tiers)))
        if "source" in b and not (isinstance(b["source"], str) and b["source"].strip()):
            bad.append("%s: `source` is a non-empty text" % who)
    return bad


def _on_optional_route(room):
    r = room.get("route", "main")
    return r != "main" and ("/" not in r or bool(room.get("optional")))


def check(doc, d, slot):
    """EXTRA_CHECKS: params, geometry, the code's reach, the tables."""
    rooms = [r for r in R.layout(doc, d, slot)]
    mine = [r for r in rooms if r["kind"] in OWN_KINDS]
    if not mine:
        return []
    bad = list(table_problems(doc))
    by_id = {r["id"]: r for r in rooms}
    bands = band_rows(doc)
    banned = {"entry_room", "exit_room", "boss_arena"}
    if sum(1 for r in mine if r["kind"] == BAIT) > 1:
        bad.append("%s: more than one bait_room (one lure a run)" % d["id"])
    for r in mine:
        lab = "%s room %s (%s)" % (d["id"], r["id"], r["kind"])
        p = r.get("params") or {}
        if r.get("gate", "open") != "open":
            bad.append("%s: gate must be open (an optional room: nothing waits on it)" % lab)
        if r["kind"] == BANK:
            if not _on_optional_route(r):
                bad.append("%s: a bank vault sits on a side entry or an optional fork route, never on the required path (route %s)" % (lab, r.get("route")))
            cl = p.get("clue_rooms")
            digits = p.get("digits", load()["bank_vault"]["defaults"]["digits"])
            if not (isinstance(cl, list) and cl and all(isinstance(x, str) for x in cl)) or len(set(cl)) != len(cl):
                bad.append("%s: params.clue_rooms is a list of distinct room ids (the rooms whose walls carry the code)" % lab)
                continue
            if isinstance(digits, int) and not isinstance(digits, bool) and len(cl) > digits:
                bad.append("%s: %d clue rooms for %d digits" % (lab, len(cl), digits))
            per = load()["bank_vault"]["limits"]["per_clue_room"]
            if isinstance(digits, int) and cl and -(-digits // len(cl)) > per:
                bad.append("%s: %d digits over %d clue rooms is more than %d to a sign" % (lab, digits, len(cl), per))
            for cid in cl:
                cr = by_id.get(cid)
                if cr is None:
                    bad.append("%s: clue room %r is not a room of this dungeon" % (lab, cid))
                elif cid == r["id"] or cr["kind"] in banned or cr["kind"] == BANK:
                    bad.append("%s: clue room %s cannot be this vault, the entry, the exit, the boss arena or another vault" % (lab, cid))
            bad += _bank_loot_problems(doc, d, r, lab, bands)
        if r["kind"] == BAIT:
            lr = by_id.get(p.get("lure_room"))
            if lr is None:
                bad.append("%s: lure_room %r is not a room of this dungeon" % (lab, p.get("lure_room")))
            else:
                import dungeon_life as DL
                if lr["id"] == r["id"] or lr["kind"] in DL.KINDS_NO_AMBIENT or lr["kind"] in banned or lr["kind"] in OWN_KINDS:
                    bad.append("%s: lure_room %s is not a living room (not this room, the entry, exit, boss, a fight, a parkour or one of these kinds)"
                               % (lab, lr["id"]))
    for b in R.slot_build(doc, d, slot):
        r = b.room
        if r["kind"] not in OWN_KINDS:
            continue
        lab = "%s room %s (%s)" % (d["id"], r["id"], r["kind"])
        g = b.grid
        for pos, want in b.meta.get("expect", []):
            if G.base(g.block_at(*pos)) != G.base(want):
                bad.append("%s: %s at %s is %s (dressing or a bug overwrote it)" % (lab, G.base(want), list(pos), G.base(g.block_at(*pos))))
        for pos, to in b.meta.get("attached", []):
            if G.classify(g.block_at(*to)) != G.SOLID:
                bad.append("%s: the fitting at %s hangs on %s, which is not solid" % (lab, list(pos), g.block_at(*to)))
    # every clue room carries its sign, in the grid
    for r in mine:
        if r["kind"] != BANK:
            continue
        p = r.get("params") or {}
        cfg = {"digits": int(p.get("digits", load()["bank_vault"]["defaults"]["digits"])), "clue_rooms": list(p.get("clue_rooms") or [])}
        if not cfg["clue_rooms"]:
            continue
        need = clue_assignment(cfg)
        built = {b.room["id"]: b for b in R.slot_build(doc, d, slot)}
        for cid, js in need.items():
            b = built.get(cid)
            signs = [s for s in (b.meta.get("clue_signs") if b else []) or [] if s["vault"] == r["id"]]
            if not signs:
                bad.append("%s room %s: no wall in clue room %s could take its sign (digits %s)" % (d["id"], r["id"], cid, [j + 1 for j in js]))
                continue
            x, y, z = signs[0]["pos"]
            if "wall_sign" not in G.base(b.grid.block_at(x, y, z)):
                bad.append("%s room %s: the clue sign in %s at %s was overwritten by %s" % (d["id"], r["id"], cid, [x, y, z], G.base(b.grid.block_at(x, y, z))))
    for r in mine:
        if r["kind"] == BAIT:
            lr = (r.get("params") or {}).get("lure_room")
            lb = next((b for b in R.slot_build(doc, d, slot) if b.room["id"] == lr), None)
            if lb is not None and not lb.meta.get("lure"):
                bad.append("%s room %s: the lure room %s holds no lure (the hook found no floor)" % (d["id"], r["id"], lr))
    return bad


_BUDGET = {}


def _bank_loot_problems(doc, d, room, lab, bands):
    p = room.get("params") or {}
    bad = check_loot(lab, bank_loot_of(p), bands)
    if bad:
        return bad
    DG = _DG()
    gt = DG.load()
    n = int(p.get("chests", load()["bank_vault"]["defaults"]["chests"]))
    key = (id(doc), d.get("id"))     # each dungeon's vaults on its own clock (tools/dungeon_greed.py vault_budget)
    try:
        if key not in _BUDGET:
            if any(k[0] != key[0] for k in _BUDGET):
                _BUDGET.clear()
            _BUDGET[key] = (doc, DG.vault_budget(doc, gt, d))
        budget = _BUDGET[key][1]
    except Exception as e:      # noqa: BLE001  (the economy simulator or a clock a fixture does not carry)
        return ["%s: the vault budget could not be derived (%s: %s)" % (lab, type(e).__name__, e)]
    for b in bands:
        k, spec = DP.loot_for(dict(p, loot_by_band=bank_loot_of(p)), bands, b)
        if spec is None:
            continue
        v = DG.chest_cp(gt, spec)
        if v is None:
            bad.append("%s band %d: the loot is not priced by data/dungeon_greed.json" % (lab, b))
        elif load()["bank_vault"].get("enforce_budget") and v > budget[b] // n:
            bad.append("%s band %d: a chest is worth %d cp, over the vault budget of %d a chest (%d chests)" % (lab, b, v, budget[b] // n, n))
    return bad


R.EXTRA_CHECKS.append(check)


# ------------------------------------------------------------------------------------------------- report


def report(doc=None):
    D = _D()
    doc = doc or D.load()
    X = load()
    lines = []
    for b in band_rows(doc):
        sh = X["wishing_well"]["shares_by_band"][str(b)]
        lines.append("well band %d: expected share %.3f of the thrown value (cap %.2f), nothing %d%%, more than thrown %d%%" % (
            b, sum(w * s for w, s in sh) / 10000.0, X["wishing_well"]["ev_cap"], sum(w for w, s in sh if s == 0), sum(w for w, s in sh if s > 100)))
    bad = table_problems(doc, force=True)
    lines += ["PROBLEM " + x for x in bad] or ["tables: no problem"]
    return lines


def main(argv=None):
    D = _D()
    doc = D.load(D.DATA)
    print("\n".join(report(doc)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
