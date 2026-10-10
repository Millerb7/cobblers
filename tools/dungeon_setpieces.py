#!/usr/bin/env python
"""Set pieces (dungeons pass 2, unit SETPIECES): kind `setpiece`, `params.piece` one of collapse | flood | lights_out.

The owner chose "one set piece per dungeon" (docs/mechanics/DUNGEON_PASS2.md, replayability 6): the mine's floor
collapsing behind you, the ruin's water rising in a chamber, the jungle's lights dying (the canopy closing). Rung: datapack
plus generator (a room kind on the kit's interface, tools/dungeon_rooms.py), driven by the keeper's per-pass room tick;
no mod, no scripting layer. Palettes and cues: data/dungeon_setpieces.json.

THE TICK. A room's `tick` runs once per keeper pass (1 s, engine.keeper.period_ticks 20) as the member standing in the
room's box with the clock running. Every piece is a counter in the room's state holder `#s<g>r<i>m0` on `dg.rs` (the
seam's `m<j>` convention; the kit leaves `m<j>` of a room that is not a `resources` room to its kind) that the tick
advances while the member is in the room: it does not run when the member is out of the box, so a piece FREEZES when the
member leaves and resumes when they return. State is slot-wide (members_max is 1). The slot reset puts every piece
back (`reset`), and the shell writes every room whole, so a piece is reset with the slot like everything else.

NEVER A TRAP, and why each piece is one:
  collapse   falls only onto a catch floor (a pit of `pit` blocks, lit, every column), which teleports to the last ledge
             stood on with the clock charged (the parkour's protocol, which the independent audit already reads), and
             the span is WHOLE AGAIN whenever the member stands on either ledge, so the way back is never cut.
  flood      the water's top block is the one under the ledges' top blocks (TOP_BELOW_LEDGE), so its surface is one under the
             ledge a swimmer climbs onto and the doors and exits stay dry; the steps stay
             standable under water (the walk graph is the same in every water state); the member has water breathing
             and resistance while in the room (drowning and the drop are not damage sources); a member under the surface
             by `deep` blocks is swept back to the last ledge (the same penalty) and the hall drains.
  lights_out only OPAQUE blocks laid in one layer `sheet_y` that is at least 4 above every standable cell (nothing the
             player stands on or walks through changes), faint guide lights stay, the effect is cosmetic.
The tests replay each piece's functions state by state onto the room's block grid and walk it.

Record: {"kind": "setpiece", "length", "width", "height", "params": {"piece": ..., ...}}. A piece needs a `pit` the kit reads
from the record (default 8, which suits collapse): flood says {"pit": 10}, lights_out {"pit": 0, "no_deploy": false};
check_setpieces names the exact params when they are wrong.
The room is a BOX (a non-box `shape` is refused): its catch floor, basin and sheet are rectangular.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_rooms as R  # noqa: E402
from dungeon_rooms import fill, setb, rng  # noqa: E402

DATA = ROOT / "data" / "dungeon_setpieces.json"
SCHEMA = "cobblers.dungeon_setpieces/1"
PIECES = ("collapse", "flood", "lights_out")
DEFAULT_SEG, DEFAULT_LEAD, DEFAULT_WARN = 4, 2, 1     # collapse: segment length, head start and warning, in blocks and passes
TOP_BELOW_LEDGE = 2                                    # flood: the top water block is at fy - 2, so the ledge's top (block fy - 1) is dry
LOADED = "# chunks-loaded-by: the member standing in the room (its chunks are loaded)"
REPLACE_AIR = "replace minecraft:air"
REPLACE_WATER = "replace minecraft:water"

_DATA = {}


def data():
    if "d" not in _DATA:
        d = json.loads(DATA.read_text(encoding="utf-8"))
        if d.get("schema") != SCHEMA:
            raise R.RoomError("%s: schema must be %s" % (DATA, SCHEMA))
        _DATA["d"] = d
    return _DATA["d"]


def U(doc):
    c = doc["engine"]["clock"]
    return c["units_per_tick"] * 20


def palette(piece, theme_id, theme):
    """The piece's blocks and cues: the theme's entry over `default` over the theme's own parkour and hull blocks."""
    t, h = theme["parkour"], theme["hull"]
    base = {
        "collapse": {"span": t["platform"], "cracked": "minecraft:cracked_stone_bricks", "track": t["ledge_top"],
                     "sleeper": None, "post": None, "beam": None},
        "flood": {"step": t["platform"], "step_edge": t["ledge_top"], "support": t["pillar"], "pillar": t["pillar"],
                  "pillar_cap": t["ledge_top"], "rubble": t["platform"], "lantern": h["light"]},
        "lights_out": {"sheet": h["ceiling"]},
    }[piece]
    out = dict(base)
    d = data()[piece]
    out.update({k: v for k, v in d.get("default", {}).items() if v is not None})
    out.update({k: v for k, v in d.get(theme_id, {}).items() if v is not None})
    out["ledge"], out["ledge_top"], out["support_ledge"] = t["ledge"], t["ledge_top"], t["pillar"]
    out["catch_floor"] = t["catch_floor"]
    out["light"] = h["light"]
    return out


def holder0(slot, room):
    return R.state_holder(slot, room) + "m0"


def ck_tail(doc, theme, ck, pen):
    """The lines every catch-style teleport shares (the kit's parkour protocol): the clock charged, resistance, the stale
    `dg.ck` guard and a teleport per checkpoint, then the sound and the actionbar."""
    out = ["scoreboard players remove @s dg.clock %d" % pen,
           "effect give @s minecraft:resistance 3 4 true",
           "execute unless score @s dg.ck matches 0..%d run scoreboard players set @s dg.ck 0" % (len(ck) - 1)]
    for i, c in enumerate(ck):
        out.append("execute if score @s dg.ck matches %d run tp @s %d.5 %d %d.5 %d 0" % (i, c[0], c[1], c[2], c[3]))
    out += ["playsound minecraft:entity.player.hurt master @s ~ ~ ~ 0.6 1",
            "title @s actionbar %s" % R.text(theme["messages"]["fall"].replace("{s}", str(doc["engine"]["clock"]["fall_penalty_s"])), "red")]
    return out


# ------------------------------------------------------------------------------------------------- collapse


def collapse(doc, d, slot, room, theme):
    p = room["params"]
    pal = palette("collapse", room["theme"], theme)
    fy, y_lo = room["floor_in"], room["y_lo"]
    ix0, ix1, iz0, iz1 = room["ix0"], room["ix1"], room["iz0"], room["iz1"]
    z_in, z_out = room["z_in"], room["z_out"]
    ledge = int(p.get("ledge", 8))
    seg = int(p.get("seg", DEFAULT_SEG))
    lead = int(p.get("lead", DEFAULT_LEAD))
    warn = int(p.get("warn", DEFAULT_WARN))
    west, east = (ix0, ix0 + ledge - 1), (ix1 - ledge + 1, ix1)
    sx0, sx1 = west[1] + 1, east[0] - 1
    segs = []
    x = sx0
    while x <= sx1:
        segs.append((x, min(x + seg - 1, sx1)))
        x += seg
    n = len(segs)
    zt = (iz0 + iz1) // 2
    zs0, zs1 = iz0 + 2, iz1 - 2        # the span leaves a 2-wide strip of pit along each wall: a fall is possible (and seen by the audit)
    H = holder0(slot, room)
    END = n + lead + warn
    light = pal["light"]
    ops, lights = [], []
    for a, b in (west, east):
        ops.append(fill((a, y_lo, iz0, b, fy - 2, iz1), pal["support_ledge"]))
        ops.append(fill((a, fy - 1, iz0, b, fy - 1, iz1), pal["ledge"]))
        ops.append(fill((a + 1, fy - 1, iz0 + 1, b - 1, fy - 1, iz1 - 1), pal["ledge_top"]))
    span_ops = [fill((sx0, fy - 1, zs0, sx1, fy - 1, zs1), pal["span"]),
                fill((sx0, fy - 1, zt - 1, sx1, fy - 1, zt + 1), pal["track"])]
    if pal.get("sleeper"):
        for sx in range(sx0 + 1, sx1, 3):
            span_ops.append(fill((sx, fy - 1, zt - 1, sx, fy - 1, zt + 1), pal["sleeper"]))
    ops += span_ops
    if pal.get("post") and pal.get("beam") and room["height"] >= 8:
        for ax in range(sx0 + 3, sx1 - 1, 8):
            for zz in (iz0, iz1):
                ops.append(fill((ax, fy, zz, ax, fy + 4, zz), pal["post"]))
            ops.append(fill((ax, fy + 5, iz0, ax, fy + 5, iz1), pal["beam"]))
    ops.append(fill((ix0, y_lo - 1, iz0, ix1, y_lo - 1, iz1), pal["catch_floor"]))
    for lx in range(ix0 + 4, ix1, 8):
        for lz in range(iz0 + 4, iz1, 8):
            ops.append(setb((lx, y_lo - 1, lz), light))
            lights.append((lx, y_lo - 1, lz))
    for a, b in (west, east):
        for lx in (a + 1, b - 1):
            for lz in (iz0 + 1, iz1 - 1):
                ops.append(setb((lx, fy - 1, lz), light))
                lights.append((lx, fy - 1, lz))
    pen = int(doc["engine"]["clock"]["fall_penalty_s"]) * U(doc)
    catch = [ix0, y_lo, iz0, ix1, y_lo + 1, iz1]
    wbox = [west[0], fy, iz0, west[1], fy + 2, iz1]
    ebox = [east[0], fy, iz0, east[1], fy + 2, iz1]
    trip = [sx0, fy, iz0, sx0, fy + 2, iz1]
    ck = [[west[0] + 2, fy, z_in, -90], [east[1] - 2, fy, z_out, 90]]
    fn = lambda name: R.room_fn(d, room, slot, name)    # noqa: E731
    restore_lines = [R.op_line(op) for op in span_ops] + ["scoreboard players set %s dg.rs -1" % H]
    tick = [LOADED, "effect give @s minecraft:resistance 2 4 true",
            "execute if entity @s[%s] run scoreboard players set @s dg.ck 0" % R.sel_box(wbox),
            "execute if entity @s[%s] run scoreboard players set @s dg.ck 1" % R.sel_box(ebox),
            # on either ledge the span is whole again: the way back is never cut
            "execute if entity @s[%s] if score %s dg.rs matches 0.. run function %s" % (R.sel_box(wbox), H, fn("restore")),
            "execute if entity @s[%s] if score %s dg.rs matches 0.. run function %s" % (R.sel_box(ebox), H, fn("restore")),
            "execute if entity @s[%s] unless score %s dg.rs matches 0..%d run function %s" % (R.sel_box(trip), H, END, fn("arm")),
            "execute if score %s dg.rs matches 0..%d run scoreboard players add %s dg.rs 1" % (H, END - 1, H)]
    for k, (a, b) in enumerate(segs):
        c_crack, c_fall = k + lead, k + lead + warn
        cx, cz = (a + b) / 2 + 0.5, (iz0 + iz1) / 2 + 0.5
        dz = min(6, (iz1 - iz0) / 2)
        crack = fill((a, fy - 1, zs0, b, fy - 1, zs1), pal["cracked"])
        gone = fill((a, fy - 1, zs0, b, fy - 1, zs1), "minecraft:air")
        tick += ["execute if score %s dg.rs matches %d run %s" % (H, c_crack, R.op_line(crack)),
                 "execute if score %s dg.rs matches %d run playsound %s master @s ~ ~ ~ 1 0.7" % (H, c_crack, pal["sound_crack"]),
                 "execute if score %s dg.rs matches %d run particle %s %.1f %d %.1f 1.5 0.2 %.1f 0.02 20 normal"
                 % (H, c_crack, pal["particle"], cx, fy, cz, dz),
                 "execute if score %s dg.rs matches %d run %s" % (H, c_fall, R.op_line(gone)),
                 "execute if score %s dg.rs matches %d run playsound %s master @s ~ ~ ~ 0.5 0.6" % (H, c_fall, pal["sound_fall"]),
                 "execute if score %s dg.rs matches %d run particle %s %.1f %d %.1f 1.5 0.5 %.1f 0.02 30 normal"
                 % (H, c_fall, pal["particle"], cx, fy - 1, cz, dz)]
    tick.append("execute if entity @s[%s] run function %s" % (R.sel_box(catch), fn("fall")))
    fall = [R.HEAD, LOADED, "# a fall onto the catch floor: the span whole again, back to the last ledge stood on, the clock charged, no damage (F1: resistance)",
            "function %s" % fn("restore")] + ck_tail(doc, theme, ck, pen)
    arm = [R.HEAD, LOADED, "# the member stepped onto the span: the countdown starts (H = passes since)",
           "scoreboard players set %s dg.rs 0" % H,
           "playsound minecraft:block.deepslate.break master @s ~ ~ ~ 1 0.5",
           "title @s actionbar %s" % R.text(pal["cue"], "gold")]
    meta = {"light_ref_y": fy, "extra_drop": 0, "piece": "collapse", "segments": segs, "lead": lead, "warn": warn, "end": END,
            "holder": H, "ledges": [list(west), list(east)], "span": [sx0, sx1], "trip": trip, "pen": pen,
            "state_fills": {"restore": restore_lines}}
    return {"blocks": ops, "lights": lights,
            "anchors": {"span": [sx0, fy - 1, zs0, sx1, fy, zs1], "checkpoints": ck, "catch": catch,
                        "center": [(sx0 + sx1) // 2, fy, (z_in + z_out) // 2]},
            "functions": {"enter": ["scoreboard players set @s dg.ck 0", "scoreboard players set %s dg.rs -1" % H],
                          "tick": tick, "fall": fall, "arm": arm, "restore": [R.HEAD, LOADED] + restore_lines,
                          "reset": restore_lines},
            "meta": meta}


# ------------------------------------------------------------------------------------------------- flood


def flood(doc, d, slot, room, theme):
    p = room["params"]
    pal = palette("flood", room["theme"], theme)
    fy, y_lo, P = room["floor_in"], room["y_lo"], room["pit"]
    ix0, ix1, iz0, iz1 = room["ix0"], room["ix1"], room["iz0"], room["iz1"]
    z_in, z_out = room["z_in"], room["z_out"]
    rg = rng(d, room, "flood")
    ledge = int(p.get("ledge", 6))
    step = int(p.get("step", 2))                  # passes (seconds) per layer of water
    delay = int(p.get("delay", 3))                # passes after the trigger before the first layer
    deep = int(p.get("deep", 5))                  # blocks under the surface (feet) before the member is swept
    M = P - TOP_BELOW_LEDGE + 1                   # layers y_lo .. fy - TOP_BELOW_LEDGE (the top water block): the ledge top is dry
    H = holder0(slot, room)
    light = pal["lantern"]
    ops, lights = [], []
    # the ledges: solid masses full width to the basin floor, so the doors are dry and nothing flows out through them
    for a, b in ((ix0, ix0 + ledge - 1), (ix1 - ledge + 1, ix1)):
        ops.append(fill((a, y_lo, iz0, b, fy - 2, iz1), pal["support_ledge"]))
        ops.append(fill((a, fy - 1, iz0, b, fy - 1, iz1), pal["ledge"]))
        ops.append(fill((a + 1, fy - 1, iz0 + 1, b - 1, fy - 1, iz1 - 1), pal["ledge_top"]))
        for lx in (a + 1, b - 1):
            for lz in (iz0 + 1, iz1 - 1):
                ops.append(setb((lx, fy - 1, lz), light))
                lights.append((lx, fy - 1, lz))
    ops.append(fill((ix0 + ledge, y_lo - 1, iz0, ix1 - ledge, y_lo - 1, iz1), pal["catch_floor"]))
    # the steps down from the entry ledge and up to the exit ledge: full-block steps, one lower each, 7 wide on the door row
    stairs = []
    for side, zc, x_of in (("in", z_in, lambda k: ix0 + ledge - 1 + k), ("out", z_out, lambda k: ix1 - ledge + 1 - k)):
        z0, z1 = max(iz0, zc - 3), min(iz1, zc + 3)
        for k in range(1, P):
            x = x_of(k)
            level = fy - k                        # standing level of step k
            if level - 2 >= y_lo:
                ops.append(fill((x, y_lo, z0, x, level - 2, z1), pal["support"]))
            ops.append(fill((x, level - 1, z0, x, level - 1, z1), pal["step"]))
            ops.append(fill((x, level - 1, z0, x, level - 1, z0), pal["step_edge"]))
            ops.append(fill((x, level - 1, z1, x, level - 1, z1), pal["step_edge"]))
            if k % 3 == 1:
                for zz in (z0, z1):
                    ops.append(setb((x, level - 1, zz), light))
                    lights.append((x, level - 1, zz))
        stairs.append((side, min(x_of(1), x_of(P - 1)), max(x_of(1), x_of(P - 1)), z0, z1))
    # the basin: floor lights, full-height pillars, one-block rubble, kept off the steps and the walls and apart
    basin_x0 = ix0 + ledge + P - 1
    basin_x1 = ix1 - ledge - P + 1
    taken = []

    def free(x, z, r):
        if not (basin_x0 + 2 <= x <= basin_x1 - 2 and iz0 + 3 <= z <= iz1 - 3):
            return False
        return all(max(abs(x - tx), abs(z - tz)) >= r for tx, tz in taken)
    n_pillar = max(2, ((basin_x1 - basin_x0) * (iz1 - iz0)) // 140)
    for _ in range(n_pillar * 12):
        if len(taken) >= n_pillar:
            break
        x, z = rg.randint(basin_x0, basin_x1), rg.randint(iz0, iz1)
        if free(x, z, 6):
            taken.append((x, z))
            ops.append(fill((x, y_lo, z, x + 1, room["ceil_y"] - 1, z + 1), pal["pillar"]))
            ops.append(fill((x, y_lo + 5, z, x + 1, y_lo + 5, z + 1), pal["pillar_cap"]))
    pillars = list(taken)
    for _ in range(40):
        x, z = rg.randint(basin_x0, basin_x1), rg.randint(iz0, iz1)
        if free(x, z, 3) and len(taken) < len(pillars) + n_pillar:
            taken.append((x, z))
            ops.append(setb((x, y_lo, z), pal["rubble"]))
    for lx in range(basin_x0 + 1, basin_x1, 7):
        for lz in range(iz0 + 3, iz1, 8):
            if all(max(abs(lx - tx), abs(lz - tz)) >= 3 for tx, tz in pillars):
                ops.append(setb((lx, y_lo - 1, lz), light))
                lights.append((lx, y_lo - 1, lz))
    pen = int(doc["engine"]["clock"]["fall_penalty_s"]) * U(doc)
    ck = [[ix0 + 2, fy, z_in, -90], [ix1 - 2, fy, z_out, 90]]
    wbox = [ix0, fy, iz0, ix0 + ledge - 1, fy + 2, iz1]
    ebox = [ix1 - ledge + 1, fy, iz0, ix1, fy + 2, iz1]
    trip = [ix0, y_lo, iz0, ix1, y_lo + 2, iz1]
    when = [delay + step * (j + 1) for j in range(M)]       # the pass count at which layer j fills
    END = when[-1] + 1
    fn = lambda name: R.room_fn(d, room, slot, name)        # noqa: E731
    layer = lambda j, block, mode: R.op_line(fill((ix0, y_lo + j, iz0, ix1, y_lo + j, iz1), block, mode))     # noqa: E731
    drain = [layer(j, "minecraft:air", REPLACE_WATER) for j in range(M - 1, -1, -1)] + ["scoreboard players set %s dg.rs -1" % H]
    tick = [LOADED, "effect give @s minecraft:resistance 2 4 true", "effect give @s minecraft:water_breathing 2 0 true",
            "execute if entity @s[%s] run scoreboard players set @s dg.ck 0" % R.sel_box(wbox),
            "execute if entity @s[%s] run scoreboard players set @s dg.ck 1" % R.sel_box(ebox),
            "execute if entity @s[%s] if score %s dg.rs matches 0.. run function %s" % (R.sel_box(wbox), H, fn("drain")),
            "execute if entity @s[%s] if score %s dg.rs matches 0.. run function %s" % (R.sel_box(ebox), H, fn("drain")),
            "execute if entity @s[%s] unless score %s dg.rs matches 0..%d run function %s" % (R.sel_box(trip), H, END, fn("arm")),
            "execute if score %s dg.rs matches 0..%d run scoreboard players add %s dg.rs 1" % (H, END - 1, H)]
    for j in range(M):
        tick += ["execute if score %s dg.rs matches %d run %s" % (H, when[j], layer(j, pal["water"], REPLACE_AIR)),
                 "execute if score %s dg.rs matches %d run playsound %s master @s ~ ~ ~ 0.7 %.1f"
                 % (H, when[j], pal["sound_rise"], 0.6 + 0.05 * j)]
    # swept: the member's feet at least `deep` under the surface (f layers filled -> surface at y_lo + f)
    iw, wid = ix1 - ix0, iz1 - iz0
    for f in range(deep + 1, M + 1):
        lo = when[f - 1]
        hi = when[f] - 1 if f < M else END
        tick.append("execute if score %s dg.rs matches %d..%d if entity @s[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d] run function %s"
                    % (H, lo, hi, ix0, y_lo, iz0, iw, f - deep - 1, wid, fn("sweep")))
    sweep = [R.HEAD, LOADED, "# the water has the member (their feet %d or more under the surface): the hall drains, back to the last ledge, the clock charged" % deep,
             "function %s" % fn("drain")] + ck_tail(doc, theme, ck, pen)
    arm = [R.HEAD, LOADED, "# the member went down into the hall: the water starts (H = passes since)",
           "scoreboard players set %s dg.rs 0" % H,
           "playsound %s master @s ~ ~ ~ 1 0.6" % pal["sound_start"],
           "title @s actionbar %s" % R.text(pal["cue"], "aqua")]
    meta = {"light_ref_y": fy, "extra_drop": 0, "piece": "flood", "layers": M, "when": when, "end": END, "deep": deep,
            "holder": H, "basin": [ix0, y_lo, iz0, ix1, y_lo + M - 1, iz1], "trip": trip, "pen": pen,
            "water_top": y_lo + M - 1, "ledge_top": fy - 1, "stairs": stairs, "pillars": pillars,
            "state_fills": {"drain": drain}}
    return {"blocks": ops, "lights": lights,
            "anchors": {"checkpoints": ck, "center": [(basin_x0 + basin_x1) // 2, y_lo, (iz0 + iz1) // 2]},
            "functions": {"enter": ["scoreboard players set @s dg.ck 0", "scoreboard players set %s dg.rs -1" % H],
                          "tick": tick, "sweep": sweep, "arm": arm, "drain": [R.HEAD, LOADED] + drain, "reset": drain},
            "meta": meta}


# ------------------------------------------------------------------------------------------------- lights_out


def lights_out(doc, d, slot, room, theme):
    p = room["params"]
    pal = palette("lights_out", room["theme"], theme)
    fy = room["floor_in"]
    ix0, ix1, iz0, iz1 = room["ix0"], room["ix1"], room["iz0"], room["iz1"]
    z_in, z_out = room["z_in"], room["z_out"]
    rg = rng(d, room, "lights_out")
    L = ix1 - ix0 + 1
    K = int(p.get("zones", max(2, L // 22)))
    lag = int(p.get("lag", 14))
    sheet_y = room["ceil_y"] - 3
    base = R.state_holder(slot, room)
    bounds = [ix0 + (L * k) // K for k in range(K + 1)]
    zones = [(bounds[k], bounds[k + 1] - 1) for k in range(K)]
    ops = []
    # the trail: a straight line door to door, 7 wide, kept clear; trunks and plants everywhere else
    def on_trail(x, z, r):
        t = (x - ix0) / max(1, ix1 - ix0)
        zl = z_in + (z_out - z_in) * t
        return abs(z - zl) <= r
    trunks = []
    for _ in range(400):
        if len(trunks) >= int(p.get("trunks", (L * (iz1 - iz0)) // 90)):
            break
        x, z = rg.randint(ix0 + 3, ix1 - 3), rg.randint(iz0 + 2, iz1 - 2)
        if on_trail(x, z, 4) or any(max(abs(x - a), abs(z - b)) < 3 for a, b in trunks):
            continue
        trunks.append((x, z))
        thick = rg.random() < 0.3 and z + 1 <= iz1 - 2 and x + 1 <= ix1 - 3
        ops.append(fill((x, fy, z, x + (1 if thick else 0), room["ceil_y"] - 1, z + (1 if thick else 0)), pal["trunk"]))
        if thick:
            trunks.append((x + 1, z + 1))
    for x in range(ix0 + 1, ix1):
        for z in range(iz0 + 1, iz1):
            if any(abs(x - a) <= 1 and abs(z - b) <= 1 for a, b in trunks) or rg.random() > 0.2:
                continue
            ops.append(setb((x, fy, z), rg.choice((pal["floor_plant"], pal["floor_plant2"], pal["carpet"]))))
    guides = []
    for x in range(ix0 + 2, ix1, 5):
        t = (x - ix0) / max(1, ix1 - ix0)
        z = round(z_in + (z_out - z_in) * t)
        ops.append(setb((x, fy + 1, z), pal["guide_light"]))
        guides.append((x, fy + 1, z))
    fn = lambda name: R.room_fn(d, room, slot, name)    # noqa: E731
    sheet = lambda a, b, block, mode: R.op_line(fill((a, sheet_y, iz0, b, sheet_y, iz1), block, mode))    # noqa: E731
    tick = [LOADED, "execute store result score @s dg.x run data get entity @s Pos[0]"]
    reset, close_fns = [], {}
    for k, (a, b) in enumerate(zones[:-1]):
        Hk = "%sm%d" % (base, k)
        tick.append("execute if score @s dg.x matches %d.. unless score %s dg.rs matches 1 run function %s" % (b + lag, Hk, fn("close%d" % k)))
        tick.append("execute if score %s dg.rs matches 1 if entity @s[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d] run effect give @s %s 3 0 true"
                    % (Hk, a, fy, iz0, b - a, sheet_y - fy, iz1 - iz0, pal["effect"]))
        cx, cz = (a + b) / 2 + 0.5, (iz0 + iz1) / 2 + 0.5
        close_fns["close%d" % k] = [
            R.HEAD, LOADED, "# the canopy closes over zone %d (x %d..%d): one opaque sheet under the ceiling lights" % (k, a, b),
            sheet(a, b, pal["sheet"], REPLACE_AIR),
            "scoreboard players set %s dg.rs 1" % Hk,
            "playsound %s master @s ~ ~ ~ 1 0.5" % pal["sound_close"],
            "playsound %s master @s ~ ~ ~ 0.6 0.8" % pal["sound_ambient"],
            "particle %s %.1f %d %.1f 6 2 %.1f 0.02 40 normal" % (pal["particle"], cx, sheet_y - 2, cz, min(6, (iz1 - iz0) / 2))]
        reset += [sheet(a, b, "minecraft:air", "replace " + pal["sheet"]), "scoreboard players set %s dg.rs 0" % Hk]
    meta = {"light_ref_y": fy, "extra_drop": 0, "piece": "lights_out", "zones": zones, "lag": lag, "sheet_y": sheet_y,
            "holders": ["%sm%d" % (base, k) for k in range(K - 1)], "guides": guides, "trunks": trunks,
            "state_fills": {k: [ln for ln in v if ln.startswith("fill")] for k, v in close_fns.items()}}
    functions = {"enter": ["scoreboard players set %s%s dg.rs 0" % (base, "m%d" % k) for k in range(K - 1)],
                 "tick": tick, "reset": reset}
    functions.update(close_fns)
    return {"blocks": ops, "anchors": {"center": [(ix0 + ix1) // 2, fy, (z_in + z_out) // 2]}, "functions": functions, "meta": meta}


# ------------------------------------------------------------------------------------------------- the kind


def kind_setpiece(doc, d, slot, room, theme):
    piece = room["params"].get("piece")
    fns = {"collapse": collapse, "flood": flood, "lights_out": lights_out}
    if piece not in fns:
        raise R.RoomError("%s room %s: setpiece `piece` must be one of %s (it is %r)" % (d["id"], room["id"], "/".join(PIECES), piece))
    return fns[piece](doc, d, slot, room, theme)


def check_setpieces(doc, d, slot):
    bad = []
    for r in R.layout(doc, d, slot):
        if r["kind"] != "setpiece":
            continue
        lab = "%s room %s (setpiece %s)" % (d["id"], r["id"], r["params"].get("piece"))
        piece = r["params"].get("piece")
        if piece not in PIECES:
            bad.append("%s: params.piece must be one of %s" % (lab, "/".join(PIECES)))
            continue
        if r.get("shape") not in (None, "box"):
            bad.append("%s: a set piece is a box (shape %r)" % (lab, r.get("shape")))
        if piece == "lights_out" and r["pit"] != 0:
            bad.append("%s: the record must say params.pit 0 (the kit reads the pit from the record; it is %d)" % (lab, r["pit"]))
        if r["rise"]:
            bad.append("%s: a set piece is level (rise %d)" % (lab, r["rise"]))
        L, W = r["ix1"] - r["ix0"] + 1, r["iz1"] - r["iz0"] + 1
        pr = r["params"]
        if piece == "collapse":
            if r["pit"] < 6:
                bad.append("%s: the pit is at least 6 deep" % lab)
            if r["height"] < 9:
                bad.append("%s: height at least 9" % lab)
            ledge, seg = int(pr.get("ledge", 8)), int(pr.get("seg", DEFAULT_SEG))
            if L - 2 * ledge < 5 * seg:
                bad.append("%s: the span is %d long, under five segments of %d" % (lab, L - 2 * ledge, seg))
            if W < 9:
                bad.append("%s: at least 9 wide" % lab)
            if int(pr.get("lead", DEFAULT_LEAD)) < 2:
                bad.append("%s: `lead` is at least 2 passes (the player's head start)" % lab)
        elif piece == "flood":
            P = r["pit"]
            ledge = int(pr.get("ledge", 6))
            if P < 6:
                bad.append("%s: the basin is at least 6 deep" % lab)
            if L < 2 * ledge + 2 * (P - 1) + 8:
                bad.append("%s: length %d is under %d (two ledges, two flights of %d steps and an 8-long floor)" % (lab, L, 2 * ledge + 2 * (P - 1) + 8, P - 1))
            if W < 15:
                bad.append("%s: at least 15 wide" % lab)
            if r["height"] < 8:
                bad.append("%s: height at least 8" % lab)
            if int(pr.get("deep", 5)) < 3:
                bad.append("%s: `deep` is at least 3 (a swimmer's feet are one under)" % lab)
            if P < int(pr.get("deep", 5)) + TOP_BELOW_LEDGE:
                bad.append("%s: the pit (%d) is under deep + %d: the water would never be deep enough to sweep anyone, and the sweep "
                           "function would be an orphan that prepare refuses" % (lab, P, TOP_BELOW_LEDGE))
            if abs(r["z_out"] - r["z_in"]) > W - 9:
                bad.append("%s: the stairs (7 wide) must fit on both door rows" % lab)
        else:
            if r["height"] < 9:
                bad.append("%s: height at least 9 (the sheet is 3 under the ceiling, 4 over the highest floor)" % lab)
            if L < 2 * 22:
                bad.append("%s: at least 44 long (two zones)" % lab)
    return bad


R.register("setpiece", kind_setpiece, dress="none", pit=8, no_deploy=True)
R.EXTRA_CHECKS.append(check_setpieces)
