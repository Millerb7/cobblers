#!/usr/bin/env python
"""Generate the dungeon engine pack from data/dungeons.json: timed rift runs in cobblers:pocket (DUNGEONS.md, ADR-008).

THE RUN (docs/mechanics/DUNGEONS.md sections 1-2). A player clicks a rip in the overworld (door_click). If the checks
pass (the gate flag, the lockout, not already in a run, no elytra, a party within the cap, a free slot, and LAST the
sigil, so a refusal never touches one) the slot is reserved, the band frozen from the RCT cap, the sigil taken, the
run tag added (E1) and the slot's mutable blocks reset. At least arrive_delay_ticks later the keeper puts them in the
slot's entry room in adventure mode with the rift pick. Crossing the entry room's east doorway (the threshold) starts
their clock, stamps the lockout and spends the sigil. The back rip and the far rip are clean exits (a refund before the
threshold, the escrow after it). At zero the player is killed when their battle ends (sudden death); a logout charges
the absence on return, and a run that died while they were away kills them on return.

THE KEEPER, every period_ticks (one schedule, re-scheduled from load like tools/entei_boss.py's):
  #up         the uptime counter: the lockout, the absence gap and the slot deadlines count on it, never gametime
  dg.pk       every player in cobblers:pocket is tagged, so every later box test on @s is dimension-safe (a box test
              on @s is coordinate-only: tests/pocket_sim.py; the slots' coordinates are real overworld coordinates)
  members     as each LIVING player in a run: the absence gap, then the dead-run check (both first, 2.6); the
              arrival; the threshold; the clock, its titles, the return margin and the bar; the staged boss
  deaths      as each living player whose dg.dc (deathCount) moved while in a run: the 2.5 messages, then the end
  slots       each owned slot: its deadline (an absent member's run dies with their clock), stale NPCs, the bind
              backstop, the recall sweep in its no-deploy boxes, the rips' particles
  sweep       anyone in a dungeon's slots who is not a member standing in their own slot is put out
  tails       E1: the tail counts down; at its end, OUTSIDE the pocket, cobblers:recovery/run_tail_end as the player
  backstops   over the overworld: the run tag's stale sweep (cobblers:recovery/run_tag_stale), survival and the pick

What it emits (namespace cobblers, folder dungeons/), each named where it is built below. The shells and the rip are
built by tools/reapply.py steps R16DG and R16DR (R16DR also stands each rip's animated oval: an item_display of
engine.rip_art's carrier item, which tools/rip_pack.py's CLIENT resource pack gives its model); the keeper, the clicks, the recipes and the callback drive
themselves. Every NPC class and the battle_victory callback load only at a boot.

  python tools/dungeon.py                 # write build/datapacks/cobblers_dungeons
  python tools/dungeon.py --out <dir>
  python tools/dungeon.py --report        # the slot shells' block counts and boxes, nothing written

Ownership: data/dungeons.json is the source (generated_by hand); the output is generated into build/ (gitignored).
What the run's lists do NOT cover is data/dungeons.json dungeons[].does_not_cover. The tests are tests/test_dungeon.py
(the builder's); the independent audit is another agent's.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import chunk_look  # noqa: E402  (entity work after a forceload: look, then act)
import dungeon_clock as DC  # noqa: E402  (a rooms dungeon's walked length and derived clock, clock_s_by_band)
import dungeon_rooms as DR  # noqa: E402  (a dungeon with `rooms`: the room kit, docs/mechanics/DUNGEON_ROOMS.md)
import function_limits  # noqa: E402
import levelcap_pack as LC  # noqa: E402  (the NPC-battle cap check and its tag, as Heaven's Arena uses them)
import portals  # noqa: E402  (the click advancement, EXP-034)

DATA = ROOT / "data" / "dungeons.json"
PORTALS = ROOT / "data" / "portals.json"
ENTEI = ROOT / "data" / "entei_boss.json"
PROBES = ROOT / "data" / "dungeon_probes.json"
BLACKOUT = ROOT / "data" / "blackout.json"
PROGRESSION = ROOT / "data" / "progression.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_dungeons"
SCHEMA = "cobblers.dungeons/2"
PACK_FORMAT = 48  # Minecraft 1.21.1
NS = "cobblers"
FOLDER = "dungeons"
CALLBACK = "data/cobblemon/callbacks/battle_victory/cobblers_dungeons.molang"
NPC_RESOURCE = "cobblemon:standard"   # tools/compile_dialogue.py NPC_RESOURCE, as the probes' classes
ENTEI_SWEEP_MARGIN = 64               # tools/entei_boss.py band_box(margin=64): Entei's keeper ejects anyone in it
SHELL_HOLDER = "dg_shells"            # #<holder> cobblers_chunk_look: the shell entities counted by R16DG
RIP_HOLDER = "dg_rips"                # ... and the overworld rips' by R16DR
HEAD = "# Generated by tools/dungeon.py from data/dungeons.json; never edit (build/ is regenerated)."

# objectives (16 characters at most). On a player unless marked; temporaries on #holders of dg.t
# STAGING PLAYTEST (the owner, 2026-10-09): a hand-set tag that skips the over-cap refusal and lets dg.ptband pick the band
PLAYTEST_TAG = "cobblers.dg_playtest"

OBJ = {
    "id": "dg.id",        # the player's dungeon number (#next holds the last given)
    "st": "dg.st",        # 0 none, 1 paid and arriving, 2 in the entry room, 3 clock running, 4 sudden death
    "slot": "dg.slot",    # the global slot number (1..), 0 none
    "run": "dg.run",      # the run's number; #s<g> dg.run is the slot's, #runs dg.run the last given
    "dun": "dg.dun",      # the dungeon's index (1..); kept after a run, for the tail's way out
    "band": "dg.band",    # frozen at door_click
    "ptband": "dg.ptband",  # STAGING PLAYTEST: the band a player tagged PLAYTEST_TAG is given (the owner, 2026-10-09)
    "rb": "dg.rb",        # the recipe sync's band (never the run's)
    "cap": "dg.cap",      # the recipe sync's cap read
    "clock": "dg.clock",  # tenth-ticks (engine.clock.units_per_tick 10)
    "clk0": "dg.clk0",    # the band's full clock, the bar's max
    "rate": "dg.rate",    # 10 (x1) .. 30 (x3), from the points taken (tools/dungeon_greed.py; its own objectives)
    "seen": "dg.seen",    # #up when last seen alive in the run
    "tail": "dg.tail",    # E1: ticks of tail left (>= 1 counting)
    "wait": "dg.wait",    # arrival countdown
    "stage": "dg.stage",  # the boss stage reached (0 not begun)
    "bw": "dg.bw",        # ticks until the next stage spawns
    "bgo": "dg.bgo",      # 1: start the stage's battle on the next pass (L1: a tick after the macro spawn)
    "idle": "dg.idle",    # passes out of battle with a stage standing and no result
    "esc": "dg.esc",      # escrow (the extension point)
    "bossd": "dg.bossd",  # 1 when the last stage fell
    "cause": "dg.cause",  # 1 timer, 2 beaten, 3 other, 4 away
    "claw": "dg.claw",    # >= 1 while a clawback measures (the extension point; sudden death waits)
    "paid": "dg.paid",    # the band of the sigil taken (refunded before the threshold), 0 none
    "x": "dg.x",          # Pos[0], floored
    "wb": "dg.wb",        # a rooms dungeon: the walk back to the back rip from the room the member stands in, blocks
    "dc": "dg.dc",        # deathCount
    "mm": "dg.mm", "s10": "dg.s10", "s1": "dg.s1",    # the clock's own time
    "lm": "dg.lm", "l10": "dg.l10", "l1": "dg.l1",    # real time left at the rate
    "t": "dg.t",          # temporaries and constants (#20, #10, ...)
    "up": "dg.up",        # #up
    "own": "dg.own",      # #s<g>: the owner's dg.id, 0 free
    "dead": "dg.dead",    # #s<g>: the uptime at which an absent member's run is dead
    "bdone": "dg.bdone",  # #s<g>: the boss has fallen this run (the gate is open)
}
OBJ_RE = re.compile(r"^[a-z0-9_.]{1,16}$")
XAERO_EFFECTS = ("xaerominimap:no_minimap", "xaerominimap:no_entity_radar", "xaerominimap:no_waypoints",
                 "xaerominimap:no_cave_maps", "xaeroworldmap:no_world_map", "xaeroworldmap:no_cave_maps")
XAERO_S = 3   # seconds: over one keeper pass (20 ticks), so the effects never lapse in the pocket
TAGS = {"pk": "dg.pk", "adv": "dg.adv", "lost": "dg.lost", "next": "dg.next", "warn": "dg.warn",
        "warned": "dg.warned", "away": "dg.away", "npc": "dg.npc", "boss": "dg.boss", "shell": "dg.shell",
        "shell_new": "dg.shell_new", "rip": "dg.rip", "rip_new": "dg.rip_new", "back": "dg.rip_back",
        "far": "dg.rip_far", "board": "dg.board"}


class DungeonError(ValueError):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise DungeonError("%s: schema must be %s" % (path, SCHEMA))
    return doc


def _j(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def F(name):
    return "%s:%s/%s" % (NS, FOLDER, name)


def fmt(v):
    return ("%.1f" % v) if isinstance(v, float) else str(v)


def text(msg, colour="gray", italic=False):
    return json.dumps({"text": msg, "color": colour, "italic": italic}, ensure_ascii=False)


def say(msg, colour="gray"):
    return "tellraw @s %s" % text(msg, colour)


def actionbar(msg, colour="gray"):
    return "title @s actionbar %s" % text(msg, colour)


def snbt_str(s):
    """A string as an SNBT single-quoted literal (for a JSON text inside NBT)."""
    return "'%s'" % s.replace("\\", "\\\\").replace("'", "\\'")


# ------------------------------------------------------------------------------------------------- the record


def dungeons(doc):
    return doc["dungeons"]


def lockout_of(doc, d):
    """A dungeon's re-entry lockout: the engine's (D17, one hour), or a TEST dungeon's own, which a run longer than the
    hour needs (the jungle and the ruin, 2026-10-09: a lockout under the clock never binds, V12)."""
    return d.get("lockout_ticks", doc["engine"]["lockout_ticks"])


def bands(doc):
    return doc["engine"]["bands"]


def clock_s(d, band_entry):
    """The dungeon's clock for a band, in seconds: its own clock_s_by_band (a full-length rooms dungeon, derived by
    tools/dungeon_clock.py), else the band's clock_s (set for the short spine of DUNGEONS.md 4.2)."""
    return int((d.get("clock_s_by_band") or {}).get(str(band_entry["band"]), band_entry["clock_s"]))


def sigils(doc):
    return doc["engine"]["sigils"]["ladder"]


def blackout_terms(blackout=None):
    """The run tag, its tail and the two functions, read from data/blackout.json (never copied: C24)."""
    b = blackout if blackout is not None else _j(BLACKOUT)
    ex = b.get("dungeon_exempt") or {}
    return {"tag": ex.get("player_tag"), "tail": ex.get("tail_ticks"), "tail_end": ex.get("tail_end_function"),
            "backstop": ex.get("backstop_function"), "exempt": (b.get("claims") or {}).get("exempt_tag")}


# ------------------------------------------------------------------------------------------------- geometry


def slots(doc):
    """[{g, di, k, dungeon, x0, z0, cz}] for every slot of every dungeon, in global order."""
    s = doc["engine"]["slots"]
    out, g = [], 0
    for di, d in enumerate(dungeons(doc), 1):
        for k in range(1, s["per_dungeon"] + 1):
            g += 1
            z0 = s["rows_from_z"] + (g - 1) * s["row_spacing"]
            out.append({"g": g, "di": di, "k": k, "dungeon": d, "x0": s["origin_x"], "z0": z0,
                        "cz": z0 + s["strip_width_max"] // 2})
    return out


def layout(doc, slot):
    """The slot's spine laid out along +x: [{kind, xa, xb, za, zb, h, ...}] with outer walls included (xa..xb,
    za..zb), the interior z cz - w//2 .. cz + w//2, y floor_y .. floor_y + h - 1, the floor course at floor_y - 1
    and the ceiling at floor_y + h. Segments are contiguous: each has its own end walls."""
    cz, x = slot["cz"], slot["x0"]
    out = []
    for i, seg in enumerate(slot["dungeon"]["spine"]["segments"]):
        w, h, n = seg["width"], seg["height"], seg["length"]
        out.append(dict(seg, i=i, xa=x, xb=x + n - 1, za=cz - w // 2 - 1, zb=cz + w // 2 + 1, h=h))
        x += n
    return out


def wb_lines(doc, slot):
    """slot/s<g>/rooms' tail: the member's walk back (dg.wb, blocks at the margin's sprint) from the room whose box they
    stand in (its hull), room by room in build order (hulls never overlap, so at most one holds them; out of every hull,
    the last room's value stands). The blocks are tools/dungeon_clock.py walk_back: the longest walk back to the
    arrival from any cell of the room, measured on the built grids of this slot's variant (DG2-INTEGRATE: the x offset
    the margin used warned up to 70 s late on routes that double back and climb)."""
    d = slot["dungeon"]
    wb = DC.walk_back(doc, d, slot)
    out = ["# the return margin's walk back from this room (m/margin reads it): tools/dungeon_clock.py walk_back"]
    for b in DR.slot_build(doc, d, slot):
        r = b.room
        # the hull, walls to roof: the interior box (`box`, what entry tests) starts at y_lo and misses a sunken trench's
        # feet and the door columns; hulls never overlap (problems() refuses it), so one box at most holds the member
        hull = (r["xa"], r["hull_lo"], r["za"], r["xb"], r["ceil_y"], r["zb"])
        out.append("execute if entity @s[%s] run scoreboard players set @s %s %d" % (DR.sel_box(hull), OBJ["wb"], wb[r["id"]]))
    return out


def first(segs, kind):
    return next(s for s in segs if s["kind"] == kind)


def points(doc, slot):
    """The slot's named points and boxes, all derived from the layout (or, for a dungeon with `rooms`, the room plan)."""
    if DR.has_rooms(slot["dungeon"]):
        return DR.points(doc, slot)
    fy = doc["engine"]["pocket"]["floor_y"]
    cz = slot["cz"]
    segs = layout(doc, slot)
    entry, arena, exit_ = first(segs, "entry_room"), first(segs, "boss_arena"), first(segs, "exit_room")
    gi = arena["i"]
    nxt = segs[gi + 1]
    hmax = max(s["h"] for s in segs)
    x1 = segs[-1]["xb"]
    za, zb = min(s["za"] for s in segs), max(s["zb"] for s in segs)
    return {
        "segs": segs,
        "arrive": (entry["xa"] + 3.5, fy, cz + 0.5, -90),
        "back": (entry["xa"] + 1, fy, cz),                   # the back rip's interaction column, inside the west wall
        "back_wall_x": entry["xa"],
        "board": (entry["xa"] + (entry["xb"] - entry["xa"]) / 2.0 + 0.5, fy + 1.5, entry["za"] + 1.5),
        "threshold_x": entry["xb"],                           # the east doorway's first block
        "arena_x": arena["xa"] + 2,                           # past the arena's west doorway
        "arena_box": (arena["xa"] + 1, fy, arena["za"] + 1, arena["xb"] - arena["xa"] - 2, arena["h"] - 1,
                      arena["zb"] - arena["za"] - 2),
        "spot": (arena["xa"] + (2 * (arena["xb"] - arena["xa"])) // 3, fy, cz),
        "gate": (arena["xb"], fy, cz - 1, nxt["xa"], fy + 2, cz + 1),
        "far": (exit_["xb"] - 1, fy, cz),
        "far_wall_x": exit_["xb"],
        "box": (slot["x0"], fy - 1, za, x1 - slot["x0"], hmax + 1, zb - za),     # x y z dx dy dz: the presence box
        "no_deploy": [(s["xa"], fy - 1, s["za"], s["xb"] - s["xa"], s["h"] + 1, s["zb"] - s["za"])
                      for s in segs if s.get("no_deploy")],
        "length": x1 - slot["x0"] + 1,
    }


def band_box(doc, d_index, margin=16):
    """(x, y, z, dx, dy, dz) over every slot of dungeon d_index with a margin, floor to the dimension's top."""
    ss = [s for s in slots(doc) if s["di"] == d_index]
    bx = [points(doc, s)["box"] for s in ss]
    x0, z0 = min(b[0] for b in bx) - margin, min(b[2] for b in bx) - margin
    x1, z1 = max(b[0] + b[3] for b in bx) + margin, max(b[2] + b[5] for b in bx) + margin
    return (x0, 0, z0, x1 - x0, 255, z1 - z0)


def sel_box(box, extra=""):
    x, y, z, dx, dy, dz = box
    return "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d%s" % (x, y, z, dx, dy, dz, ("," + extra) if extra else "")


def bar_id(slot):
    return "%s:dg_%s_s%d_m1" % (NS, slot["dungeon"]["id"], slot["k"])


def lk_obj(d):
    return "dg.lk_%s" % d["short"]


def lv_obj(d):
    """The variant (1-based) of this dungeon the player last entered (DUNGEON_ROOMS.md 1a): entry prefers another."""
    return "dg.lv_%s" % d["short"]


# ------------------------------------------------------------------------------------------------- checks


def foreign_boxes(portals_doc=None, entei_doc=None, probes_doc=None):
    """{name: (x0, z0, x1, z1)} of what the slots must stay out of, each from its own data file."""
    portals_doc = portals_doc if portals_doc is not None else _j(PORTALS)
    entei_doc = entei_doc if entei_doc is not None else _j(ENTEI)
    probes_doc = probes_doc if probes_doc is not None else _j(PROBES)
    pp = portals_doc["pocket"]
    rescue = (-10 ** 6, min(pp["bands"].values()) - pp["rescue_margin"],
              10 ** 6, max(pp["bands"].values()) + pp["rescue_margin"])
    ep, half = entei_doc["pocket"], entei_doc["room"]["half"]
    xs = [ep["origin"][0] + k * ep["spacing"] for k in range(ep["slots"])]
    m = ENTEI_SWEEP_MARGIN
    entei = (min(xs) - half - m, ep["origin"][1] - half - m, max(xs) + half + m, ep["origin"][1] + half + m)
    r = probes_doc["row"]
    probes = (-10 ** 6, r["z_min"], 10 ** 6, r["z_max"])
    return {"the portals' rescue box": rescue, "Entei's band": entei, "the probe pack's row": probes}


def _meets(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def problems(doc, portals_doc=None, entei_doc=None, probes_doc=None, blackout=None, progression=None):
    """[problem] in the record, held against the pocket, the other pocket users, the blackout and the waystones."""
    portals_doc = portals_doc if portals_doc is not None else _j(PORTALS)
    entei_doc = entei_doc if entei_doc is not None else _j(ENTEI)
    progression = progression if progression is not None else _j(PROGRESSION)
    bad = []
    e = doc["engine"]
    p, s = e["pocket"], e["slots"]
    pp, ep = portals_doc["pocket"], entei_doc["pocket"]
    if p["dimension"] != pp["dimension"]:
        bad.append("engine.pocket.dimension %s is not data/portals.json's %s" % (p["dimension"], pp["dimension"]))
    if p["floor_y"] != pp["floor_y"]:
        bad.append("engine.pocket.floor_y %d is not data/portals.json's %d" % (p["floor_y"], pp["floor_y"]))
    if list(p["border"]) != list(ep["border"]) or p["border_margin"] != ep["border_margin"]:
        bad.append("engine.pocket.border differs from data/entei_boss.json's")
    gen = pp["generator"]
    lo, hi = p["border"]
    mg = p["border_margin"]
    foreign = foreign_boxes(portals_doc, entei_doc, probes_doc)
    boxes = []
    for sl in slots(doc):
        pt = points(doc, sl)
        x, y, z, dx, dy, dz = pt["box"]
        label = "%s slot %d" % (sl["dungeon"]["id"], sl["k"])
        strip = (sl["x0"], sl["z0"], sl["x0"] + s["strip_length"] - 1, sl["z0"] + s["strip_width_max"] - 1)
        if pt["length"] > s["strip_length"]:
            bad.append("%s: the spine is %d long, over the strip's %d" % (label, pt["length"], s["strip_length"]))
        if z < strip[1] or z + dz > strip[3]:
            bad.append("%s: the shell's z %d..%d leaves its strip %d..%d" % (label, z, z + dz, strip[1], strip[3]))
        if strip[0] < lo + mg or strip[1] < lo + mg or strip[2] > hi - mg or strip[3] > hi - mg:
            bad.append("%s: the strip %s leaves the world border %d..%d less %d" % (label, strip, lo, hi, mg))
        if not (gen["min_y"] < y and y + dy < gen["min_y"] + gen["height"]):
            bad.append("%s: the shell does not fit the dimension's height" % label)
        for name, fb in foreign.items():
            if _meets(strip, fb):
                bad.append("%s: its strip meets %s %s" % (label, name, fb))
        for other_label, ob in boxes:
            if _meets(strip, ob):
                bad.append("%s: its strip meets %s's" % (label, other_label))
        boxes.append((label, strip))
        # the blackout's waystone arrival test compares coordinates, not dimensions (data/blackout.json checkpoints)
        cp = (blackout if blackout is not None else _j(BLACKOUT))["checkpoints"]
        r = cp["waystone_arrival_radius"] + 1
        ax, ay, az, _yaw = pt["arrive"]
        for f in progression.get("flags", []):
            w = f.get("waystone")
            if w:
                wx, wy, wz = w["position"]
                if abs(wx - ax) <= r and abs(wy - ay) <= r and abs(wz - az) <= r:
                    bad.append("%s: its arrival %s is within %d of the %s waystone %s" % (label, pt["arrive"][:3], r,
                                                                                         w["town"], w["position"]))
        segs = pt["segs"]
        kinds = [g["kind"] for g in segs]
        if DR.has_rooms(sl["dungeon"]):
            continue        # a dungeon with rooms: the room kit's own checks run once below (DR.problems)
        for need in ("entry_room", "boss_arena", "exit_room"):
            if kinds.count(need) != 1:
                bad.append("%s: the spine needs exactly one %s (has %d)" % (label, need, kinds.count(need)))
        if kinds and (kinds[0] != "entry_room" or kinds[-1] != "exit_room"):
            bad.append("%s: the spine must start with the entry room and end with the exit room" % label)
        for g in segs:
            if g["width"] % 2 == 0 or g["width"] < 3 or g["height"] < 3 or g["length"] < 4:
                bad.append("%s: segment %d (%s): width odd and >= 3, height >= 3, length >= 4" % (label, g["i"], g["kind"]))
            if g["width"] + 2 > s["strip_width_max"]:
                bad.append("%s: segment %d is wider than the strip" % (label, g["i"]))
    bad += DR.problems(doc)
    # the clock's greed: the value table and the rate (tools/dungeon_greed.py; replaced D13's ladder, 2026-10-10)
    import dungeon_greed as DG    # lazy, as dungeon_fights is
    bad += DG.problems(doc)
    bad += DG.vault_problems(doc)     # KIT3: a vault chest within the economy's budget (when vault_budget.enforce)
    import dungeon_prize as DPz       # lazy (KIT3): the hidden prize's engine defaults and its key_ball record
    bad += DPz.engine_problems(doc) + DPz.problems_record(doc)
    caps = []
    for i, b in enumerate(bands(doc), 1):
        if b["band"] != i:
            bad.append("bands: band %d out of order" % b["band"])
        caps.append(max(b["caps"]))
        if b["clock_s"] < 60:
            bad.append("band %d: clock %d s" % (b["band"], b["clock_s"]))
    if caps != sorted(caps):
        bad.append("bands: caps must rise with the band")
    for d in dungeons(doc):
        own = d.get("clock_s_by_band")
        if own is None:
            continue
        if set(own) != {str(b["band"]) for b in bands(doc)}:
            bad.append("%s: clock_s_by_band must name every band (%s)" % (d["id"], sorted(own)))
            continue
        if any(not isinstance(v, int) or v < 60 for v in own.values()):
            bad.append("%s: clock_s_by_band: whole seconds, at least 60" % d["id"])
        if DR.has_rooms(d) and not any(d["id"] in p and "rooms do not build" in p for p in bad):
            bad += DC.clock_problems(doc, d)
    for d in dungeons(doc):
        if "lockout_ticks" in d and not d.get("test"):
            bad.append("%s: a lockout of its own is for a test dungeon only (D17: one hour per dungeon)" % d["id"])
        longest = max(clock_s(d, b) for b in bands(doc)) * 20
        if lockout_of(doc, d) < longest:
            bad.append("%slockout_ticks %d is under the longest clock %d ticks: the lockout would never bind (V12)"
                       % ("%s: " % d["id"] if "lockout_ticks" in d else "", lockout_of(doc, d), longest))
    k = e["keeper"]
    if k["period_ticks"] < 1 or k["arrive_delay_ticks"] < k["period_ticks"]:
        bad.append("keeper period %d / arrive delay %d" % (k["period_ticks"], k["arrive_delay_ticks"]))
    # the sigils
    sg = sigils(doc)
    if [x["band"] for x in sg] != [b["band"] for b in bands(doc)]:
        bad.append("sigils: one per band, in band order")
    items = [x["item"] for x in sg]
    if len(set(items)) != len(items):
        bad.append("sigils: two bands share a base item")
    for x in sg:
        if not x["item"].endswith("_pottery_sherd"):
            bad.append("sigil %s: the base item is a pottery sherd with no other use (7.4)" % x["id"])
        if sum(n for _i, n in x["recipe"]) > 9:
            bad.append("sigil %s: the recipe does not fit a crafting grid" % x["id"])
        if x["item"] in [i for i, _n in x["recipe"]]:
            bad.append("sigil %s: its base item is one of its own inputs" % x["id"])
        if x["band"] < 5 and any("netherite" in i or "ancient_debris" in i for i, _n in x["recipe"]):
            bad.append("sigil %s: netherite before band 5 (the Nether opens at badge 8, 7.4)" % x["id"])
    ff = e["sigils"]["free_first_entry"]
    if ff.get("owner_decision") != "Q20 OPEN" and "decided" not in str(ff.get("owner_decision")):
        bad.append("sigils.free_first_entry: owner_decision must say Q20 OPEN until the owner decides")
    if not set(ff["dungeons"]) <= {d["id"] for d in dungeons(doc)}:
        bad.append("sigils.free_first_entry names an unknown dungeon")
    rg = e["sigils"]["recipe_gate"]
    if rg["mode"] not in rg["modes"]:
        bad.append("sigils.recipe_gate.mode %r is not one of %s" % (rg["mode"], sorted(rg["modes"])))
    # E1 and the exempt tag: read, never copied
    bt = blackout_terms(blackout)
    for key in ("tag", "tail", "tail_end", "backstop", "exempt"):
        if not bt[key]:
            bad.append("data/blackout.json has no %s for the run tag (dungeon_exempt / claims.exempt_tag)" % key)
    for name in list(OBJ.values()) + [lk_obj(d) for d in dungeons(doc)]:
        if not OBJ_RE.match(name):
            bad.append("objective %r" % name)
    # the boss
    for d in dungeons(doc):
        bo = d["boss"]
        if len(bo["stage_level_offsets"]) < 1:
            bad.append("%s: the boss has no stage" % d["id"])
        for b in bands(doc):
            lvl = min(b["caps"]) + max(bo["stage_level_offsets"])
            if lvl > min(b["caps"]):
                bad.append("%s band %d: a stage above the band's lower cap" % (d["id"], b["band"]))
            st = bo["teams"].get(str(b["band"]))
            if not st or len(st) != len(bo["stage_level_offsets"]):
                bad.append("%s band %d: not one crew per stage" % (d["id"], b["band"]))
            elif any(not 1 <= len(t) <= 6 for t in st):
                bad.append("%s band %d: a crew of 0 or more than 6" % (d["id"], b["band"]))
            if bo["member_level_offset"] > 0:
                bad.append("%s: a crew member above its stage's level" % d["id"])
        rip = d["rip"]
        if rip["frame"]["x1"] - rip["frame"]["x0"] != 4:
            bad.append("%s: the rip's frame is two posts and a 3-wide opening" % d["id"])
        for blk in rip["palette"].values():
            if "portal" in blk:
                bad.append("%s: a portal block in the rip (7.1: they teleport on their own)" % d["id"])
        ov = rip.get("oval")
        art = e.get("rip_art")
        if not ov or not art:
            bad.append("%s: no rip.oval / engine.rip_art (the rip's animated oval)" % d["id"])
        else:
            if not (0 < ov["in_front"] <= 0.5):
                bad.append("%s: the oval must stand in front of the opening's face (0 < in_front <= 0.5), not in the block" % d["id"])
            if ov["width"] <= 0 or ov["height"] <= 0:
                bad.append("%s: the oval has no size" % d["id"])
            fw, fh = art["frame"]["width"], art["frame"]["height"]
            if abs(fw * ov["height"] - fh * ov["width"]) > 1e-6:
                bad.append("%s: the oval is %sx%s but the texture frame is %dx%d (a stretched art)" % (d["id"], ov["width"], ov["height"], fw, fh))
    art = e.get("rip_art")
    if art:
        if not isinstance(art["custom_model_data"], int) or isinstance(art["custom_model_data"], bool):
            bad.append("rip_art.custom_model_data must be an int (1.21.1's component is a plain int)")
        if "portal" in art["item"]:
            bad.append("rip_art.item is a portal item")
        if not re.match(r"^[a-z0-9_.]+$", art["tag"]):
            bad.append("rip_art.tag %r" % art["tag"])
    ids = [d["id"] for d in dungeons(doc)]
    shorts = [d["short"] for d in dungeons(doc)]
    if len(set(ids)) != len(ids) or len(set(shorts)) != len(shorts):
        bad.append("two dungeons share an id or a short name")
    return bad


# ------------------------------------------------------------------------------------------------- items


def sigil_components_snbt(x, doc):
    lore = [l.replace("{caps}", x["caps"]) for l in doc["engine"]["sigils"]["lore"]]
    parts = ["minecraft:custom_data={%s:%db}" % (doc["engine"]["sigils"]["custom_data_key"], x["band"]),
             "minecraft:item_name=%s" % snbt_str(text(x["name"], x["colour"])),
             "minecraft:lore=[%s]" % ",".join(snbt_str(text(l, "dark_gray", True)) for l in lore),
             'minecraft:rarity="%s"' % doc["engine"]["sigils"]["rarity"]]
    return "%s[%s]" % (x["item"], ",".join(parts))


def sigil_match(x, doc):
    """The predicate that finds this band's sigil and nothing else: the byte form (sigils.custom_data_type_why)."""
    return "%s[minecraft:custom_data~{%s:%db}]" % (x["item"], doc["engine"]["sigils"]["custom_data_key"], x["band"])


def sigil_recipe(x, doc):
    lore = [l.replace("{caps}", x["caps"]) for l in doc["engine"]["sigils"]["lore"]]
    ings = []
    for item, n in x["recipe"]:
        ings += [{"item": item}] * int(n)
    return {"type": "minecraft:crafting_shapeless", "category": "misc", "ingredients": ings,
            "result": {"id": x["item"], "count": 1, "components": {
                "minecraft:custom_data": {doc["engine"]["sigils"]["custom_data_key"]: x["band"]},
                "minecraft:item_name": text(x["name"], x["colour"]),
                "minecraft:lore": [text(l, "dark_gray", True) for l in lore],
                "minecraft:rarity": doc["engine"]["sigils"]["rarity"]}}}


def recipe_id(x):
    return "%s:dg_sigil_b%d" % (NS, x["band"])


def pick_give(doc, d=None):
    """The rift pick. For a dungeon with `rooms` its can_break also names the blocks its resources rooms ask for."""
    p = doc["engine"]["rift_pick"]
    breaks = list(p["can_break"])
    if d is not None and DR.has_rooms(d):
        breaks += [b for b in DR.pick_blocks(d) if b not in breaks]
    return ("%s[minecraft:custom_data={%s:1b},minecraft:item_name=%s,minecraft:can_break={predicates:[{blocks:[%s]}]}]"
            % (p["item"], p["custom_data_key"], snbt_str(text(p["name"], p["colour"])),
               ",".join('"%s"' % b for b in breaks)))


def pick_match(doc):
    p = doc["engine"]["rift_pick"]
    return "%s[minecraft:custom_data~{%s:1b}]" % (p["item"], p["custom_data_key"])


# ------------------------------------------------------------------------------------------------- NPC classes


def boss_classes(doc, d):
    """{class name: (class json, level)} for every band x stage of the dungeon's boss."""
    bo = d["boss"]
    out = {}
    for b in bands(doc):
        base = min(b["caps"])
        for k, off in enumerate(bo["stage_level_offsets"], 1):
            lvl = base + off
            crew = bo["teams"][str(b["band"])][k - 1]
            # the ace is the crew's LAST entry, at the stage's level; the others one level under (member_level_offset)
            team = ["%s level=%d" % (sp, lvl + (0 if i == len(crew) - 1 else bo["member_level_offset"]))
                    for i, sp in enumerate(crew)]
            name = "dg_%s_boss_b%d_s%d" % (d["short"], b["band"], k)
            # the shape of Heaven's Arena's classes (tools/arena_runtime.py npc_class) and the probes' (C1, EXP-078)
            out[name] = ({"hitbox": "player", "names": [bo["name"]], "resourceIdentifier": NPC_RESOURCE,
                          "canDespawn": False, "isInvulnerable": True, "isMovable": False, "isLeashable": False,
                          "allowProjectileHits": False, "autoHealParty": True,
                          "battleConfiguration": {"canChallenge": False}, "skill": bo["skill"],
                          "ai": [{"type": "apply_behaviours", "presets": ["cobblemon:battler", "cobblemon:looks_at_players"]}],
                          "party": {"type": "simple", "pokemon": team}}, lvl)
    return out


# ------------------------------------------------------------------------------------------------- the shell


def shell_lines(doc, slot):
    """The slot's shell as block commands in the pocket's context (the caller carries `execute in`). A dungeon with
    `rooms` builds its shell room by room (DR.shell_functions): this is then the concatenation, for counts and tests."""
    if DR.has_rooms(slot["dungeon"]):
        return [ln for b in DR.slot_build(doc, slot["dungeon"], slot) for ln in DR.shell_lines(b)]
    fy = doc["engine"]["pocket"]["floor_y"]
    pt = points(doc, slot)
    pal = slot["dungeon"]["spine"]["palette"]
    every = slot["dungeon"]["spine"]["light_every"]
    cz = slot["cz"]
    out = []
    s = doc["engine"]["slots"]
    if s.get("clear_strip"):
        out.append("fill %d %d %d %d %d %d minecraft:air" % (slot["x0"], fy - 1, slot["z0"], slot["x0"] + s["strip_length"] - 1,
                                                         fy - 2 + s["clear_strip_height"], slot["z0"] + s["strip_width_max"] - 1))
    for g in pt["segs"]:
        xa, xb, za, zb, h = g["xa"], g["xb"], g["za"], g["zb"], g["h"]
        out.append("fill %d %d %d %d %d %d %s" % (xa, fy - 1, za, xb, fy + h, zb, pal["wall"]))
        out.append("fill %d %d %d %d %d %d minecraft:air" % (xa + 1, fy, za + 1, xb - 1, fy + h - 1, zb - 1))
        out.append("fill %d %d %d %d %d %d %s" % (xa + 1, fy - 1, za + 1, xb - 1, fy - 1, zb - 1, pal["floor"]))
        lanes = [cz] if g["width"] < 9 else [cz - g["width"] // 4, cz + g["width"] // 4]
        for x in range(xa + 2, xb - 1, every):
            for z in lanes:
                out.append("setblock %d %d %d %s" % (x, fy + h, z, pal["light"]))
        if g.get("no_deploy"):
            out.append("fill %d %d %d %d %d %d %s" % (xa + 1, fy - 1, za + 1, xa + 1, fy - 1, zb - 1, pal["lamp"]))
    segs = pt["segs"]
    for a, b in zip(segs, segs[1:]):
        blk = pal["gate"] if a.get("gate_east") else "minecraft:air"
        out.append("fill %d %d %d %d %d %d %s" % (a["xb"], fy, cz - 1, b["xa"], fy + 2, cz + 1, blk))
    for wx in (pt["back_wall_x"], pt["far_wall_x"]):
        out.append("fill %d %d %d %d %d %d %s" % (wx, fy, cz - 2, wx, fy + 3, cz + 2, pal["rip_frame"]))
        out.append("fill %d %d %d %d %d %d %s" % (wx, fy, cz - 1, wx, fy + 2, cz + 1, pal["rip_opening"]))
    return out


def shell_blocks(doc, slot):
    """Blocks written by the slot's shell function (the sum of every fill's and setblock's volume, after the split)."""
    n = 0
    if DR.has_rooms(slot["dungeon"]):
        return DR.total_blocks(doc, slot)
    for line in function_limits.split_fills(shell_lines(doc, slot)):
        m = function_limits.FILL.search(line)
        if m:
            n += function_limits._volume(*m.groups())
        elif line.startswith("setblock"):
            n += 1
    return n


def gate_lines(doc, slot, block):
    x0, y0, z0, x1, y1, z1 = points(doc, slot)["gate"]
    return ["fill %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, block)]


def board_text(doc, d, slot):
    """The entry room's run board (DUNGEONS.md 2.4): generated from the record, showing what the clock assumes."""
    pt = points(doc, slot)
    bx = pt["board"][0]
    legs = []
    names = {"drift": "drift", "boss_arena": "the boss", "exit_room": "the far rip"}
    for g in pt["segs"][1:]:
        label = "cracked lamps" if g.get("no_deploy") else names.get(g["kind"], g["kind"])
        legs.append("%s %d" % (label, int(g["xa"] - bx)))
    import dungeon_greed as DG    # lazy (unit GREED): the board states the rule from the table
    grt = DG.load()["rate"]
    clocks = " ".join("%d:%d:%02d" % (b["band"], clock_s(d, b) // 60, clock_s(d, b) % 60) for b in bands(doc))
    if DR.has_rooms(d):
        legs = []
        for g in pt["segs"][1:]:
            if g["kind"] in ("drift", "stairs"):
                continue
            label = "cracked lamps" if g.get("no_deploy") else names.get(g["kind"], g["kind"].replace("_", " "))
            legs.append("%s %d" % (label, int(g["xa"] - bx)))
    optional = [k.replace("_", " ") for k in ("resources", "nest", "habitat", "vault") if any(r["kind"] == k for r in d.get("rooms", []))]
    lines = [d["name"].upper() + (" (placeholder spine)" if d.get("spine", {}).get("placeholder") else ""),
             "Legs (blocks from here): " + ", ".join(legs),
             "Clock by band: " + clocks,
             "Ore mined, chests opened, Pokemon caught: every %d points taken is +0.1x on the clock, to x%d."
             % (grt["per_step_cp"] // 100, grt["cap"] // grt["base"]),
             "Falls cost %d seconds." % doc["engine"]["clock"]["fall_penalty_s"],
             "No Pokemon past the cracked lamps.",
             ("Optional legs: " + ", ".join(optional) + ".") if optional else "Optional legs: none in this spine.",
             "Dying here takes no items, only your money and what the run has earned.",
             "Leaving the game does not stop the rift.",
             "The rift has taken your sigil. Go back now and it is returned; past this board it is spent."]
    if DR.has_rooms(d):
        import dungeon_relics as DRel   # lazy (DG2-RELICS): one static line when the dungeon hides relics
        line = DRel.board_line(doc, d)
        if line:
            lines.append(line)
    return "\n".join(lines)


def shell_entities(doc, slot):
    """[(summon line in the pocket, kind tag)] for the slot's back rip, far rip and board."""
    dim = doc["engine"]["pocket"]["dimension"]
    pt = points(doc, slot)
    st = "%s.%s%d" % (TAGS["shell"], slot["dungeon"]["short"], slot["k"])
    out = []
    for key, pos in (("back", pt["back"]), ("far", pt["far"])):
        x, y, z = pos
        tags = '"%s","%s","%s","%s","%s"' % (TAGS["shell"], st, TAGS[key], TAGS["rip"], TAGS["shell_new"])
        out.append(("execute in %s run summon minecraft:interaction %.1f %d %.1f {width:3.0f,height:3.0f,response:1b,"
                    "Tags:[%s]}" % (dim, x + 0.5, y, z + 0.5, tags), TAGS[key]))
    bx, by, bz = pt["board"]
    body = text(board_text(doc, slot["dungeon"], slot), "white")
    tags = '"%s","%s","%s","%s"' % (TAGS["shell"], st, TAGS["board"], TAGS["shell_new"])
    out.append(("execute in %s run summon minecraft:text_display %.1f %.1f %.1f {Tags:[%s],billboard:\"vertical\","
                "line_width:320,text:%s}" % (dim, bx, by, bz, tags, snbt_str(body)), TAGS["board"]))
    return out


def rip_lines(d):
    """The overworld rip's blocks (DUNGEONS.md 7.1): two posts, a lintel and a dark opening, in the frame's plane."""
    r = d["rip"]
    f, pal = r["frame"], r["palette"]
    y0, y1, z = f["y"], f["y"] + f["height"] - 1, f["z"]
    return ["fill %d %d %d %d %d %d %s" % (f["x0"], y0, z, f["x0"], y1 - 1, z, pal["frame"]),
            "fill %d %d %d %d %d %d %s" % (f["x1"], y0, z, f["x1"], y1 - 1, z, pal["frame"]),
            "fill %d %d %d %d %d %d %s" % (f["x0"], y1, z, f["x1"], y1, z, pal["lintel"]),
            "fill %d %d %d %d %d %d %s" % (f["x0"] + 1, y0, z, f["x1"] - 1, y1 - 1, z, pal["opening"])]


def rip_tag(d):
    return "%s_%s" % (TAGS["rip"], d["short"])


def oval_pos(d):
    """(x, y, z) of the rip's oval display, its CENTRE: on the frame's column, its foot at the frame's y, in front of
    the opening's face (data/dungeons.json rip.oval). All three are derived from the frame, never typed twice."""
    r = d["rip"]
    f, o = r["frame"], r["oval"]
    return ((f["x0"] + f["x1"]) / 2.0 + 0.5, f["y"] + o["height"] / 2.0, f["z"] + 1 + o["in_front"])


def oval_tag(doc):
    return doc["engine"]["rip_art"]["tag"]


def oval_summon(doc, d):
    """The R16DR summon of one rip's oval: an item_display of the carrier item (engine.rip_art; tools/rip_pack.py
    gives that item+custom_model_data its model in the client pack). Fixed in the frame's plane, facing south onto the
    trail, full-bright. `scale` is the oval's width x height x 1 over the model's one-block quad."""
    art, o = doc["engine"]["rip_art"], d["rip"]["oval"]
    x, y, z = oval_pos(d)
    br = art["brightness"]
    return ("summon minecraft:item_display %.2f %.2f %.2f {Tags:[\"%s\",\"%s\",\"%s\"],"
            "item:{id:\"%s\",count:1,components:{\"minecraft:custom_model_data\":%d}},item_display:\"none\","
            "brightness:{sky:%d,block:%d},view_range:%.1ff,"
            "transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],"
            "scale:[%.2ff,%.2ff,1f]}}"
            % (x, y, z, rip_tag(d), oval_tag(doc), TAGS["rip_new"], art["item"], art["custom_model_data"],
               br["sky"], br["block"], art["view_range"], o["width"], o["height"]))


# ------------------------------------------------------------------------------------------------- functions


def functions(doc, blackout=None):
    e = doc["engine"]
    O = OBJ
    T = TAGS
    bt = blackout_terms(blackout)
    RUN_TAG, TAIL, TAIL_END, BACKSTOP, EXEMPT = bt["tag"], bt["tail"], bt["tail_end"], bt["backstop"], bt["exempt"]
    dim = e["pocket"]["dimension"]
    k = e["keeper"]
    P = k["period_ticks"]
    import dungeon_greed as DG    # lazy (unit GREED): the value table, the mined objectives, the rate
    gtab = DG.load()
    GO = DG.OBJ_G
    sl = slots(doc)
    ds = dungeons(doc)
    hold = k["entry_hold_ticks"]
    tail_start = TAIL + P
    fy = e["pocket"]["floor_y"]
    out = {}

    def dsel(d_index):
        return [s for s in sl if s["di"] == d_index]

    def H(s):
        return "#s%d" % s["g"]

    # ---- load ------------------------------------------------------------------------------------------------
    objs = ["scoreboard objectives add %s dummy" % v for kk, v in O.items() if kk != "dc"]
    objs += ["scoreboard objectives add %s deathCount" % O["dc"]]
    objs += DG.objective_lines(doc, gtab)
    objs += ["scoreboard objectives add %s dummy" % lk_obj(d) for d in ds]
    objs += ["scoreboard objectives add %s dummy" % lv_obj(d) for d in ds if d.get("variants")]
    if any(DR.has_rooms(d) for d in ds):
        objs += DR.objective_lines()
    out["load"] = [HEAD,
                   "# DUNGEONS.md 11.3. Objectives, constants, every slot free unless already held, and the loops: the keeper",
                   "# re-schedules from here (a /reload or a boot restarts it), as tools/entei_boss.py's does"] + objs + [
        "scoreboard players set #10 %s 10" % O["t"],
        "scoreboard players set #20 %s 20" % O["t"],
        "scoreboard players set #56 %s %d" % (O["t"], e["return_margin"]["sprint_x10"]),
        "scoreboard players set #60 %s 60" % O["t"],
        "scoreboard players set #80 %s %d" % (O["t"], e["clock"]["units_per_tick"] * 20),
        "scoreboard players set #1200 %s 1200" % O["t"]] + DG.load_lines(doc, gtab) + [
        "execute unless score #up %s matches -2147483648.. run scoreboard players set #up %s 0" % (O["up"], O["up"]),
        "execute unless score #next %s matches -2147483648.. run scoreboard players set #next %s 0" % (O["id"], O["id"]),
        "execute unless score #runs %s matches -2147483648.. run scoreboard players set #runs %s 0" % (O["run"], O["run"])] + [
        "execute unless score %s %s matches -2147483648.. run scoreboard players set %s %s 0" % (H(s), O["own"], H(s), O["own"])
        for s in sl] + [
        "schedule function %s %dt replace" % (F("keeper"), P),
        "schedule function %s %dt replace" % (F("rips/emit"), k["rip_particle_period_ticks"]),
        "schedule function %s %dt replace" % (F("recipes/sync"), k["recipe_sync_period_ticks"]),
        "# hand-run hooks (EXP-084, staging): %s {p:<cp>} sets a member's points taken and its rate; %s {s:<seconds>}"
        % (F("greed/test_set"), F("test/clock")),
        "# sets a member's clock; %s and %s run the arithmetic on any entity (a marker)." % (F("m/gap"), F("m/digits")),
        "# GREED (tools/dungeon_greed.py): %s credits #gv cp, as a member; mined blocks, chests and catches call it." % F("greed/add")]

    # ---- the keeper ------------------------------------------------------------------------------------------
    keeper = [HEAD,
              "# Every %d ticks (DUNGEONS.md 11.3). Scheduled, so it runs in the overworld: every pocket test carries" % P,
              "# `in %s` or the dg.pk tag, never a bare box test on @s." % dim,
              "scoreboard players add #up %s %d" % (O["up"], P),
              "tag @a remove %s" % T["pk"],
              "execute in %s run tag @a[distance=0..] add %s" % (dim, T["pk"]),
              "# no map in the pocket (the owner, 2026-10-10): Xaero's own effects, refreshed each pass, so leaving ends",
              "# them within %d s (docs/research/notes/xaero-disable.md: nothing in Xaero is keyed on a dimension)" % XAERO_S] + [
              "effect give @a[tag=%s] %s %d 0 true" % (T["pk"], eff, XAERO_S) for eff in XAERO_EFFECTS] + [
              "# a death in a run FIRST, handled once the player is alive again (after the blackout's own death path,",
              "# E1); a dead player is in @a, not in @e, so nothing here touches them until they respawn",
              "execute as @e[type=minecraft:player,scores={%s=1..,%s=1..}] at @s run function %s" % (O["dc"], O["st"], F("m/died")),
              "scoreboard players set @e[type=minecraft:player,scores={%s=1..}] %s 0" % (O["dc"], O["dc"]),
              "# then the living members",
              "execute as @e[type=minecraft:player,scores={%s=1..}] at @s run function %s" % (O["st"], F("m/member"))]
    keeper += ["execute if score %s %s matches 1.. run function %s" % (H(s), O["own"], F("slot/s%d/tend" % s["g"])) for s in sl]
    for di, d in enumerate(ds, 1):
        keeper.append("execute in %s as @e[type=minecraft:player,%s] at @s run function %s"
                      % (dim, sel_box(band_box(doc, di)), F("check_%s" % d["short"])))
    keeper += [
        "# E1: the tails, then the backstops over the overworld (never in the pocket)",
        "execute as @e[type=minecraft:player,scores={%s=1..}] run function %s" % (O["tail"], F("m/tail")),
        "execute as @e[type=minecraft:player,tag=%s,tag=!%s] unless score @s %s matches 1.. unless score @s %s matches 1.. "
        "at @s run function %s" % (RUN_TAG, T["pk"], O["st"], O["tail"], BACKSTOP),
        "execute as @e[type=minecraft:player,tag=%s,tag=!%s] unless score @s %s matches 1.. run function %s"
        % (T["adv"], T["pk"], O["st"], F("m/restore")),
        "execute as @e[type=minecraft:player,tag=!%s] unless score @s %s matches 2.. if items entity @s container.* %s "
        "run clear @s %s" % (T["pk"], O["st"], pick_match(doc), pick_match(doc)),
        "schedule function %s %dt replace" % (F("keeper"), P)]
    out["keeper"] = keeper

    # ---- a member, alive, each pass --------------------------------------------------------------------------
    member = [HEAD,
              "# As and at a living player in a run (dg.st 1..4). DUNGEONS.md 2.6: the absence gap and the dead-run check",
              "# run first, before anything else of the pass.",
              "scoreboard players set #stop %s 0" % O["t"],
              "function %s" % F("m/gap")]
    member += ["execute if score @s %s matches %d unless score @s %s = %s %s run function %s"
               % (O["slot"], s["g"], O["run"], H(s), O["run"], F("m/void")) for s in sl]
    member += [
        "execute if score #stop %s matches 0 if score @s %s matches 3..4 if score #gap %s matches 1.. if score @s %s matches ..0 "
        "run function %s" % (O["t"], O["st"], O["t"], O["clock"], F("m/void")),
        "execute if score #stop %s matches 1 run return 0" % O["t"],
        "scoreboard players operation @s %s = #up %s" % (O["seen"], O["up"]),
        "execute if score @s %s matches 1 run return run function %s" % (O["st"], F("m/arriving")),
        "# a member in the entry room or later must stand in their own slot, in the pocket (dg.pk: dimension-safe)",
        "execute unless entity @s[tag=%s] run return run function %s" % (T["pk"], F("m/left"))]
    member += ["execute if score @s %s matches %d unless entity @s[%s] run return run function %s"
               % (O["slot"], s["g"], sel_box(points(doc, s)["box"]), F("m/left")) for s in sl]
    member += [
        "execute if score @s %s matches 2 run return run function %s" % (O["st"], F("m/lobby")),
        "execute if score @s %s matches 3 run function %s" % (O["st"], F("m/clock")),
        "execute if score @s %s matches 4 run function %s" % (O["st"], F("m/sudden"))]
    out["m/member"] = member

    out["m/gap"] = [
        HEAD, "# DUNGEONS.md 2.6: the time away, charged at the member's rate. Runs on any entity (a marker, EXP-084).",
        "# #gap = #up - dg.seen - period: 0 on a pass that follows a pass that saw them",
        "scoreboard players operation #gap %s = #up %s" % (O["t"], O["up"]),
        "scoreboard players operation #gap %s -= @s %s" % (O["t"], O["seen"]),
        "scoreboard players remove #gap %s %d" % (O["t"], P),
        "execute unless score #gap %s matches 1.. run return 0" % O["t"],
        "execute unless score @s %s matches 3..4 run return 0" % O["st"],
        "scoreboard players operation #c %s = #gap %s" % (O["t"], O["t"]),
        "scoreboard players operation #c %s *= @s %s" % (O["t"], O["rate"]),
        "scoreboard players operation @s %s -= #c %s" % (O["clock"], O["t"]),
        "execute if score @s %s matches 1.. run %s" % (O["clock"], actionbar(ds[0]["messages"]["away"], "red")),
        "return 1"]

    out["m/void"] = [
        HEAD, "# As a member whose run is dead: their slot's run is not theirs (reset or reused while they were away), or",
        "# their clock is at or below 0 after the gap (2.6). Past the threshold: killed into the blackout. Before it: the",
        "# run is void, the sigil returned (the threshold refund, 7.4)",
        "scoreboard players set #stop %s 1" % O["t"],
        "execute if score @s %s matches 3..4 run return run function %s" % (O["st"], F("m/deadkill")),
        "function %s" % F("m/refund"),
        "function %s" % F("m/end"),
        "execute if entity @s[tag=%s] run function %s" % (T["pk"], F("m/out"))]
    out["m/deadkill"] = [
        HEAD, "# 2.6: the dead-run kill on return, before anything else of the pass; the death handling runs on respawn",
        "scoreboard players set @s %s 4" % O["cause"],
        say(e["death"]["away_line"], "red"),
        "kill @s"]

    # ---- arriving (state 1) ----------------------------------------------------------------------------------
    arr = [HEAD, "# As a member who has paid and not yet arrived: the arrival delay, counted on them",
           "scoreboard players remove @s %s %d" % (O["wait"], P),
           "execute if score @s %s matches 1.. run return 0" % O["wait"]]
    arr += ["execute if score @s %s matches %d run return run function %s" % (O["slot"], s["g"], F("slot/s%d/arrive" % s["g"]))
            for s in sl]
    out["m/arriving"] = arr

    # ---- the entry room (state 2) ----------------------------------------------------------------------------
    lobby = [HEAD, "# As a member in the entry room: the clock has not started. Their slot holds for entry_hold_ticks of absence"]
    lobby += ["execute if score @s %s matches %d run scoreboard players operation %s %s = #up %s"
              % (O["slot"], s["g"], H(s), O["dead"], O["up"]) for s in sl]
    lobby += ["execute if score @s %s matches %d run scoreboard players add %s %s %d"
              % (O["slot"], s["g"], H(s), O["dead"], hold) for s in sl]
    lobby += ["execute store result score @s %s run data get entity @s Pos[0]" % O["x"]]
    for s in sl:
        lobby.append("execute if score @s %s matches %d if score @s %s matches %d.. run function %s"
                     % (O["slot"], s["g"], O["x"], points(doc, s)["threshold_x"], F("slot/s%d/start" % s["g"])))
    out["m/lobby"] = lobby

    # ---- the clock (state 3) ---------------------------------------------------------------------------------
    U = e["clock"]["units_per_tick"] * 20       # units per second at x1
    clock = [HEAD, "# As a member whose clock runs (DUNGEONS.md 2.1-2.3): the charge, the titles, zero, the deadline, the",
             "# return margin, the bar and the boss",
             "function %s" % F("greed/mined"),
             "scoreboard players operation #b %s = @s %s" % (O["t"], O["clock"]),
             "function %s" % F("m/charge")]
    for secs in e["clock"]["titles_at_s"]:
        clock.append("execute if score #b %s matches %d.. if score @s %s matches 1..%d run title @s title %s"
                     % (O["t"], secs * U + 1, O["clock"], secs * U, text("%d:%02d" % (secs // 60, secs % 60), "gold")))
    clock += [
        "execute if score @s %s matches ..0 run return run function %s" % (O["clock"], F("m/zero")),
        "execute if score @s %s matches 1..%d run function %s" % (O["clock"], e["clock"]["countdown_last_s"] * U, F("m/countdown")),
        "function %s" % F("m/deadline"),
        "function %s" % F("m/margin"),
        "function %s" % F("m/digits")]
    clock += ["execute if score @s %s matches %d run function %s" % (O["slot"], s["g"], F("slot/s%d/bar" % s["g"])) for s in sl]
    clock += ["execute if score @s %s matches %d run function %s" % (O["slot"], s["g"], F("slot/s%d/rooms" % s["g"]))
              for s in sl if DR.has_rooms(s["dungeon"])]
    clock += ["execute if score @s %s matches %d run function %s" % (O["slot"], s["g"], F("slot/s%d/boss" % s["g"])) for s in sl]
    out["m/clock"] = clock

    out["m/charge"] = [
        HEAD, "# One pass of the clock: period x rate quarter-ticks (2.1). Runs on any entity (EXP-084).",
        "scoreboard players operation #d %s = @s %s" % (O["t"], O["rate"]),
        "scoreboard players operation #d %s *= #20 %s" % (O["t"], O["t"]),
        "scoreboard players operation @s %s -= #d %s" % (O["clock"], O["t"]),
        "return 1"]
    out["m/deadline"] = [
        HEAD, "# 2.6: the slot's deadline, #up + clock / rate, rewritten every pass the member is present",
        "scoreboard players operation #dl %s = @s %s" % (O["t"], O["clock"]),
        "scoreboard players operation #dl %s /= @s %s" % (O["t"], O["rate"]),
        "scoreboard players operation #dl %s += #up %s" % (O["t"], O["up"])] + [
        "execute if score @s %s matches %d run scoreboard players operation %s %s = #dl %s"
        % (O["slot"], s["g"], H(s), O["dead"], O["t"]) for s in sl]
    out["m/countdown"] = [
        HEAD, "# a title for each of the last seconds (2.2)",
        "scoreboard players operation #cs %s = @s %s" % (O["t"], O["clock"]),
        "scoreboard players operation #cs %s /= #80 %s" % (O["t"], O["t"]),
        "scoreboard players add #cs %s 1" % O["t"],
        'title @s title {"score":{"name":"#cs","objective":"%s"},"color":"red"}' % O["t"]]
    out["m/zero"] = [
        HEAD, "# The clock reached 0 (2.5): sudden death. Nothing is earned from here; the kill waits for the battle's end",
        "scoreboard players set @s %s 0" % O["clock"],
        "scoreboard players set @s %s 4" % O["st"],
        "title @s title %s" % text(ds[0]["messages"]["closes"], "dark_red"),
        "playsound minecraft:block.respawn_anchor.deplete master @s ~ ~ ~ 1 0.6",
        "function %s" % F("m/digits")] + [
        "execute if score @s %s matches %d run function %s" % (O["slot"], s["g"], F("slot/s%d/bar" % s["g"])) for s in sl] + [
        "function %s" % F("m/sudden")]
    out["m/sudden"] = [
        HEAD, "# 2.5 sudden death: the clock holds at 0, the slot's deadline is now (a logout frees it), and the player is",
        "# killed the first pass q.player.in_battle reads 0. runmolang's nested command is queued (EXP-022), so the",
        "# kill is its own function, which checks again",
        "scoreboard players set @s %s 0" % O["clock"]] + [
        "execute if score @s %s matches %d run scoreboard players operation %s %s = #up %s"
        % (O["slot"], s["g"], H(s), O["dead"], O["up"]) for s in sl] + [
        "runmolang \"(q.player.in_battle == 0) ? { q.run_command('execute as ' + q.player.uuid + ' at @s run function "
        "%s'); };\" @s" % F("m/timeout")]
    out["m/timeout"] = [
        HEAD, "# As a member at 0 and out of battle. E1 rule 6: a clawback still measuring (dg.claw) runs to completion",
        "# first; the next pass asks again. The kill is `kill`, which goes through a totem (B2, EXP-071)",
        "execute unless score @s %s matches 4 run return 0" % O["st"],
        "execute if score @s %s matches 1.. run return 0" % O["claw"],
        "scoreboard players set @s %s 1" % O["cause"],
        "kill @s"]

    # ---- the margin, digits ----------------------------------------------------------------------------------
    rm = e["return_margin"]
    margin = [HEAD, "# 2.3 the return margin: real seconds left at the rate against the sprint back to the back rip + %d"
              % rm["warn_extra_s"],
              "# A spine dungeon walks back in x. A rooms dungeon walks back the way its route went (it turns, doubles back",
              "# and climbs): the blocks are the room's own (dg.wb, set each pass by slot/s<g>/rooms from the walk measured",
              "# on the built rooms, tools/dungeon_clock.py walk_back); none yet (the first pass), no warning yet",
              "execute store result score @s %s run data get entity @s Pos[0]" % O["x"],
              "scoreboard players operation #bk %s = @s %s" % (O["t"], O["x"])]
    for di, d in enumerate(ds, 1):
        if DR.has_rooms(d):
            margin += ["execute if score @s %s matches %d unless score @s %s matches 0.. run return 0" % (O["dun"], di, O["wb"]),
                       "execute if score @s %s matches %d run scoreboard players operation #bk %s = @s %s"
                       % (O["dun"], di, O["t"], O["wb"])]
        else:
            margin.append("execute if score @s %s matches %d run scoreboard players remove #bk %s %d"
                          % (O["dun"], di, O["t"], points(doc, dsel(di)[0])["back"][0]))
    margin += [
        "scoreboard players operation #bk %s *= #10 %s" % (O["t"], O["t"]),
        "scoreboard players operation #bk %s /= #56 %s" % (O["t"], O["t"]),
        "scoreboard players add #bk %s %d" % (O["t"], rm["warn_extra_s"] + rm["parkour_recross_s"]),
        "scoreboard players operation #rs %s = @s %s" % (O["t"], O["clock"]),
        "scoreboard players operation #rd %s = @s %s" % (O["t"], O["rate"]),
        "scoreboard players operation #rd %s *= #20 %s" % (O["t"], O["t"]),
        "scoreboard players operation #rs %s /= #rd %s" % (O["t"], O["t"]),
        "tag @s remove %s" % T["warn"],
        "execute if score #rs %s < #bk %s run tag @s add %s" % (O["t"], O["t"], T["warn"]),
        "execute if entity @s[tag=%s,tag=!%s] run %s" % (T["warn"], T["warned"], actionbar(ds[0]["messages"]["way_back"], "light_purple")),
        "tag @s[tag=%s] add %s" % (T["warn"], T["warned"])]
    out["m/margin"] = margin
    out["m/digits"] = [
        HEAD, "# the bar's numbers (2.2): the clock's own m:ss, and the real m:ss left at the rate. Runs on any entity",
        "scoreboard players operation #cs %s = @s %s" % (O["t"], O["clock"]),
        "scoreboard players operation #cs %s /= #80 %s" % (O["t"], O["t"]),
        "scoreboard players operation @s %s = #cs %s" % (O["mm"], O["t"]),
        "scoreboard players operation @s %s /= #60 %s" % (O["mm"], O["t"]),
        "scoreboard players operation #ss %s = #cs %s" % (O["t"], O["t"]),
        "scoreboard players operation #ss %s %%= #60 %s" % (O["t"], O["t"]),
        "scoreboard players operation @s %s = #ss %s" % (O["s10"], O["t"]),
        "scoreboard players operation @s %s /= #10 %s" % (O["s10"], O["t"]),
        "scoreboard players operation @s %s = #ss %s" % (O["s1"], O["t"]),
        "scoreboard players operation @s %s %%= #10 %s" % (O["s1"], O["t"]),
        "scoreboard players operation #rd %s = @s %s" % (O["t"], O["rate"]),
        "scoreboard players operation #rd %s *= #20 %s" % (O["t"], O["t"]),
        "scoreboard players operation #rs %s = @s %s" % (O["t"], O["clock"]),
        "scoreboard players operation #rs %s /= #rd %s" % (O["t"], O["t"]),
        "scoreboard players operation @s %s = #rs %s" % (O["lm"], O["t"]),
        "scoreboard players operation @s %s /= #60 %s" % (O["lm"], O["t"]),
        "scoreboard players operation #ss %s = #rs %s" % (O["t"], O["t"]),
        "scoreboard players operation #ss %s %%= #60 %s" % (O["t"], O["t"]),
        "scoreboard players operation @s %s = #ss %s" % (O["l10"], O["t"]),
        "scoreboard players operation @s %s /= #10 %s" % (O["l10"], O["t"]),
        "scoreboard players operation @s %s = #ss %s" % (O["l1"], O["t"]),
        "scoreboard players operation @s %s %%= #10 %s" % (O["l1"], O["t"]),
        "return 1"]

    # ---- greed (tools/dungeon_greed.py, the owner 2026-10-10): points taken -> the rate, and its test hook ----------
    out.update(DG.functions(doc, gtab))
    out["test/clock"] = [
        HEAD, "# TEST HOOK (EXP-084): set this member's clock to $(s) seconds of clock",
        "$scoreboard players set @s %s $(s)" % O["clock"],
        "scoreboard players operation @s %s *= #80 %s" % (O["clock"], O["t"])]

    # ---- deaths, leaving, the end ----------------------------------------------------------------------------
    titles = e["death"]["titles"]
    died = [HEAD, "# As a member alive again after a death in a run (DUNGEONS.md 2.5). The blackout has charged, returned",
            "# and healed them; the run tag kept them from any claim (E1). The 2.5 messages, then the end.",
            "scoreboard players set @s %s 0" % O["dc"],
            "execute unless score @s %s matches 1.. if entity @s[tag=%s] run scoreboard players set @s %s 2"
            % (O["cause"], T["lost"], O["cause"]),
            "execute unless score @s %s matches 1.. run scoreboard players set @s %s 3" % (O["cause"], O["cause"])]
    for c, tt in sorted(titles.items()):
        died.append("execute if score @s %s matches %s run title @s title %s" % (O["cause"], c, text(tt["title"], "dark_red")))
        if tt["subtitle"]:
            died.append("execute if score @s %s matches %s run title @s subtitle %s" % (O["cause"], c, text(tt["subtitle"], "gray")))
    died += ["function %s" % F("m/lines"), "function %s" % F("m/end")]
    out["m/died"] = died

    lines = [HEAD, "# DUNGEONS.md 2.5's chat lines, in order"]
    ch = e["death"]["chat"]
    lines += [say(ch[0], "green"), say(ch[1], "gray"),
              "execute if score @s %s matches 1.. run %s" % (O["esc"], say("Lost with the run: what it had earned.", "gray")),
              "execute unless score @s %s matches 1.. run %s" % (O["esc"], say("The run had earned nothing yet.", "gray")),
              say(ch[2], "gray")]
    for di, d in enumerate(ds, 1):
        lines += ["# the lockout left: lockout + the threshold stamp - #up (0 if they never crossed it)",
                  "scoreboard players set #rem %s 0" % O["t"],
                  "execute if score @s %s matches -2147483648.. run scoreboard players set #rem %s %d" % (lk_obj(d), O["t"], lockout_of(doc, d)),
                  "execute if score @s %s matches -2147483648.. run scoreboard players operation #rem %s += @s %s"
                  % (lk_obj(d), O["t"], lk_obj(d)),
                  "execute if score @s %s matches -2147483648.. run scoreboard players operation #rem %s -= #up %s"
                  % (lk_obj(d), O["t"], O["up"]),
                  "execute if score #rem %s matches ..-1 run scoreboard players set #rem %s 0" % (O["t"], O["t"]),
                  "scoreboard players add #rem %s 1199" % O["t"],
                  "scoreboard players operation #rem %s /= #1200 %s" % (O["t"], O["t"])]
        for x in sigils(doc):
            lines.append("execute if score @s %s matches %d if score @s %s matches %d run tellraw @s %s"
                         % (O["dun"], di, O["band"], x["band"], json.dumps(
                             ["", {"text": "%s opens to you again in about " % d["name"], "color": "gray"},
                              {"score": {"name": "#rem", "objective": O["t"]}, "color": "gold"},
                              {"text": " minutes, for another %s." % x["name"], "color": "gray"}], ensure_ascii=False)))
    out["m/lines"] = lines

    out["m/left"] = [
        HEAD, "# As a member who is alive and online but not standing in their own slot in the pocket: the blackout's",
        "# return after a loss (dg.lost from the victory callback), or anything else that moved them. The run ends",
        "# with the death rule's costs (2.5); the blackout has charged for a loss. No kill",
        "execute if entity @s[tag=%s] run scoreboard players set @s %s 2" % (T["lost"], O["cause"]),
        "execute unless score @s %s matches 1.. run scoreboard players set @s %s 3" % (O["cause"], O["cause"])] + [
        "execute if score @s %s matches %s run title @s title %s" % (O["cause"], c, text(tt["title"], "dark_red"))
        for c, tt in sorted(titles.items()) if c in ("2", "3")] + [
        "function %s" % F("m/lines"),
        "function %s" % F("m/end"),
        "execute if entity @s[tag=%s] run function %s" % (T["pk"], F("m/out"))]

    end = [HEAD, "# EVERY way out of a run ends here (V13, E1): escrow cleared (a clean exit has paid first), survival if WE set",
           "# adventure, the pick taken by its component, the slot freed if it is still this run's (its bar with it), and",
           "# the run tag's TAIL started. The tag itself is never removed here: only %s does, at the tail's end" % TAIL_END,
           "scoreboard players set @s %s 0" % O["esc"],
           "execute if entity @s[tag=%s] run gamemode survival @s" % T["adv"],
           "tag @s remove %s" % T["adv"],
           "clear @s %s" % pick_match(doc)]
    end += ["execute if score @s %s matches %d if score @s %s = %s %s run function %s"
            % (O["slot"], s["g"], O["run"], H(s), O["run"], F("slot/s%d/free" % s["g"])) for s in sl]
    end += ["tag @s remove %s" % t for t in (T["lost"], T["next"], T["warn"], T["warned"])] + [
        "scoreboard players set @s %s 0" % O["st"],
        "scoreboard players set @s %s 0" % O["slot"],
        "scoreboard players set @s %s 0" % O["cause"],
        "scoreboard players set @s %s 0" % O["stage"],
        "scoreboard players set @s %s 0" % O["bgo"],
        "scoreboard players set @s %s 0" % O["bw"],
        "# E1 rule 3: at least tail_ticks (%d) of tail, counted %d a pass from the next pass" % (TAIL, P),
        "scoreboard players set @s %s %d" % (O["tail"], tail_start)]
    out["m/end"] = end

    tail = [HEAD, "# E1: the tail. At its end, OUTSIDE the pocket, the blackout's tail end runs as the player: it removes the",
            "# run tag and delivers any claim held while they were in the run. In the pocket it waits (in a slot band,",
            "# the player is put out first, so the next pass ends it in the overworld)",
            "scoreboard players remove @s %s %d" % (O["tail"], P),
            "execute if score @s %s matches 1.. run return 0" % O["tail"],
            "execute if entity @s[tag=%s] run scoreboard players set @s %s 1" % (T["pk"], O["tail"])]
    for di, d in enumerate(ds, 1):
        tail.append("execute if entity @s[tag=%s] in %s if entity @s[%s] run function %s"
                    % (T["pk"], dim, sel_box(band_box(doc, di)), F("m/out_%s" % d["short"])))
    tail += ["execute if entity @s[tag=%s] run return 0" % T["pk"],
             "scoreboard players set @s %s 0" % O["tail"],
             "execute at @s run function %s" % TAIL_END]
    out["m/tail"] = tail

    out["m/restore"] = [HEAD, "# the backstop: a player we put in adventure, outside the pocket with no live run (V13)",
                        "gamemode survival @s", "tag @s remove %s" % T["adv"], "clear @s %s" % pick_match(doc)]

    outl = [HEAD, "# out to the overworld rip's outside point of the player's dungeon (a fixed point: nothing stored)"]
    for di, d in enumerate(ds, 1):
        x, y, z, yaw = d["rip"]["outside"]
        outl.append("execute if score @s %s matches %d in minecraft:overworld run tp @s %s %s %s %s 0"
                    % (O["dun"], di, fmt(float(x)), y, fmt(float(z)), yaw))
        out["m/out_%s" % d["short"]] = [HEAD, "execute in minecraft:overworld run tp @s %s %s %s %s 0"
                                        % (fmt(float(x)), y, fmt(float(z)), yaw)]
    out["m/out"] = outl

    refund = [HEAD, "# The threshold refund (7.4): the sigil taken at door_click comes back, rebuilt with its components"]
    for x in sigils(doc):
        refund.append("execute if score @s %s matches %d run give @s %s 1" % (O["paid"], x["band"], sigil_components_snbt(x, doc)))
    refund += ["execute if score @s %s matches 1.. run %s" % (O["paid"], say(ds[0]["messages"]["refund"], "gold")),
               "scoreboard players set @s %s 0" % O["paid"]]
    out["m/refund"] = refund
    out["pay"] = [HEAD, "# THE ESCROW'S PAYOUT (section 9, step 6): run at a clean exit past the threshold, before m/end.",
                  "# No reward table is built tonight; the escrow score is the extension point",
                  "scoreboard players set @s %s 0" % O["esc"]]

    # ---- the clicks ------------------------------------------------------------------------------------------
    def exit_fn(kind, adv, states):
        lines = [HEAD, "# The %s rip, clicked (the proven click, EXP-034): a clean exit (7.2)" % kind,
                 "advancement revoke @s only %s:%s" % (NS, adv),
                 "execute as @e[type=minecraft:interaction,tag=%s,distance=..8] run data remove entity @s interaction" % T[kind],
                 "execute unless score @s %s matches %s run return 0" % (O["st"], states),
                 "execute if score @s %s matches 3 unless score @s %s matches 1.. run return 0" % (O["st"], O["clock"]),
                 "execute if score @s %s matches 2 run function %s" % (O["st"], F("m/refund")),
                 "execute if score @s %s matches 3 run function %s" % (O["st"], F("pay")),
                 say(ds[0]["messages"]["exit"], "gold"),
                 "function %s" % F("m/end"),
                 "function %s" % F("m/out")]
        return lines
    out["back"] = exit_fn("back", "dungeons/back", "2..3")
    out["far"] = exit_fn("far", "dungeons/far", "3")

    # ---- door_click, per dungeon -----------------------------------------------------------------------------
    for di, d in enumerate(ds, 1):
        m = d["messages"]
        sh = d["short"]
        LK = lk_obj(d)
        free = d["id"] in e["sigils"]["free_first_entry"]["dungeons"]
        dc = [HEAD,
              "# The %s rip, clicked: DUNGEONS.md 7.2's checks in order, the sigil LAST so a refusal never touches one." % d["name"],
              "# #why: 0 go, 1 gate, 2 lockout, 3 in a run, 4 elytra, 5 cap unread, 6 party over cap, 7 no free slot,",
              "# 8 no sigil of their band or higher, 9 only a lower band's",
              "advancement revoke @s only %s:dungeons/rip_%s" % (NS, sh),
              "execute as @e[type=minecraft:interaction,tag=%s,distance=..8] run data remove entity @s interaction" % rip_tag(d),
              "execute unless score @s %s matches 1.. run scoreboard players add #next %s 1" % (O["id"], O["id"]),
              "execute unless score @s %s matches 1.. run scoreboard players operation @s %s = #next %s" % (O["id"], O["id"], O["id"]),
              "scoreboard players set #why %s 0" % O["t"]]
        if d["gate_flag"]:
            dc.append("execute unless entity @s[advancements={%s=true}] run scoreboard players set #why %s 1" % (d["gate_flag"], O["t"]))
        dc += [
            "# 2: the lockout, on the uptime counter, from the threshold (2.5); a never-entrant is outside it",
            "scoreboard players set #d %s %d" % (O["t"], lockout_of(doc, d)),
            "execute if score @s %s matches -2147483648.. run scoreboard players operation #d %s = #up %s" % (LK, O["t"], O["up"]),
            "execute if score @s %s matches -2147483648.. run scoreboard players operation #d %s -= @s %s" % (LK, O["t"], LK),
            "execute if score #why %s matches 0 if score #d %s matches 0..%d run scoreboard players set #why %s 2"
            % (O["t"], O["t"], lockout_of(doc, d) - 1, O["t"]),
            "execute if score #why %s matches 0 if score @s %s matches 1.. run scoreboard players set #why %s 3" % (O["t"], O["st"], O["t"]),
            "execute if score #why %s matches 0 if items entity @s armor.chest minecraft:elytra run scoreboard players set #why %s 4"
            % (O["t"], O["t"]),
            "# 5, 6: the cap (5.1, 5.2), read and compared as Heaven's Arena does (tools/levelcap_pack.py battle_check)",
            "execute if score #why %s matches 0 run function %s {x:\"\"}" % (O["t"], LC.BATTLE_CHECK),
            "execute if score #why %s matches 0 unless score @s %s matches 1.. run scoreboard players set #why %s 5" % (O["t"], LC.CAP, O["t"]),
            "# a playtester (tag %s, set by hand on staging) is never refused for a party over the cap" % PLAYTEST_TAG,
            "execute if score #why %s matches 0 if entity @s[tag=%s,tag=!%s] run scoreboard players set #why %s 6" % (O["t"], LC.PARTY_OVER, PLAYTEST_TAG, O["t"]),
            "execute if score #why %s matches 0 run function %s" % (O["t"], F("m/band")),
            "# 7: a free slot of this dungeon",
            "scoreboard players set #pick %s 0" % O["t"]]
        if d.get("variants"):
            # DUNGEON_ROOMS.md 1a: a free slot whose layout variant is not the one this player last ran, else any free one
            dc += ["execute if score #pick %s matches 0 if score %s %s matches 0 unless score @s %s matches %d run "
                   "scoreboard players set #pick %s %d" % (O["t"], H(s), O["own"], lv_obj(d), DR.variant_of(doc, d, s)["index"] + 1,
                                                            O["t"], s["g"]) for s in dsel(di)]
        dc += ["execute if score #pick %s matches 0 if score %s %s matches 0 run scoreboard players set #pick %s %d"
               % (O["t"], H(s), O["own"], O["t"], s["g"]) for s in dsel(di)]
        dc += ["execute if score #why %s matches 0 if score #pick %s matches 0 run scoreboard players set #why %s 7" % (O["t"], O["t"], O["t"]),
               "# 8, 9: the sigil, last (7.4)",
               "scoreboard players set #sig %s 0" % O["t"],
               "scoreboard players set #weak %s 0" % O["t"]]
        if free:
            dc.append("execute if score #why %s matches 0 unless entity @s[advancements={%s:dungeons/free/%s=true}] run "
                      "scoreboard players set #sig %s -1" % (O["t"], NS, sh, O["t"]))
        dc += ["execute if score #why %s matches 0 if score #sig %s matches 0 if score @s %s matches %d run function %s"
               % (O["t"], O["t"], O["band"], x["band"], F("sigil/find_b%d" % x["band"])) for x in sigils(doc)]
        dc += ["execute if score #why %s matches 0 if score #sig %s matches 0 run scoreboard players set #why %s 8" % (O["t"], O["t"], O["t"]),
               "execute if score #why %s matches 8 if score #weak %s matches 1 run scoreboard players set #why %s 9" % (O["t"], O["t"], O["t"]),
               "execute unless score #why %s matches 0 run return run function %s" % (O["t"], F("door/refuse_%s" % sh)),
               "function %s" % F("door/go_%s" % sh)]
        out["door/%s" % sh] = dc

        rem_tail = {"score": {"name": "#rem", "objective": O["t"]}, "color": "gold"}
        ref = [HEAD, "# a refusal, with its reason; nothing was taken",
               "execute if score #why %s matches 1 run %s" % (O["t"], say(m["refuse_gate"])),
               "scoreboard players set #rem %s %d" % (O["t"], lockout_of(doc, d)),
               "scoreboard players operation #rem %s -= #d %s" % (O["t"], O["t"]),
               "scoreboard players add #rem %s 1199" % O["t"],
               "scoreboard players operation #rem %s /= #1200 %s" % (O["t"], O["t"]),
               "execute if score #why %s matches 2 run tellraw @s %s" % (O["t"], json.dumps(
                   ["", {"text": m["refuse_lockout"], "color": "gray"}, rem_tail, {"text": " minutes.", "color": "gray"}])),
               "execute if score #why %s matches 3 run %s" % (O["t"], say(m["refuse_run"])),
               "execute if score #why %s matches 4 run %s" % (O["t"], say(m["refuse_elytra"])),
               "execute if score #why %s matches 5 run %s" % (O["t"], say(m["refuse_cap"])),
               "execute if score #why %s matches 6 run %s" % (O["t"], say(m["refuse_over"])),
               "execute if score #why %s matches 7 run %s" % (O["t"], say(m["refuse_busy"]))]
        for x in sigils(doc):
            ref.append("execute if score #why %s matches 8 if score @s %s matches %d run %s"
                       % (O["t"], O["band"], x["band"], say(m["refuse_sigil"] + "the %s (or stronger)." % x["name"])))
        ref.append("execute if score #why %s matches 9 run %s" % (O["t"], say(m["refuse_weak"])))
        out["door/refuse_%s" % sh] = ref

        go = [HEAD, "# The %s rip opens: the slot reserved, the band already frozen (m/band), the sigil taken, the run tag" % d["name"],
              "# added (E1 rule 1: HERE, before the arrival delay), any earlier tail cancelled, the slot's mutables reset",
              "scoreboard players operation @s %s = #pick %s" % (O["slot"], O["t"]),
              "scoreboard players add #runs %s 1" % O["run"],
              "scoreboard players operation @s %s = #runs %s" % (O["run"], O["run"])]
        go += ["execute if score #pick %s matches %d run function %s" % (O["t"], s["g"], F("slot/s%d/reserve" % s["g"])) for s in dsel(di)]
        if d.get("variants"):
            go += ["execute if score #pick %s matches %d run scoreboard players set @s %s %d"
                   % (O["t"], s["g"], lv_obj(d), DR.variant_of(doc, d, s)["index"] + 1) for s in dsel(di)]
        go += ["scoreboard players set @s %s %d" % (O["dun"], di),
               "scoreboard players set @s %s 1" % O["st"],
               "scoreboard players set @s %s %d" % (O["wait"], k["arrive_delay_ticks"] + P),
               "scoreboard players operation @s %s = #up %s" % (O["seen"], O["up"]),
               "scoreboard players set @s %s 0" % GO["gp"],
               "scoreboard players set @s %s %d" % (O["rate"], gtab["rate"]["base"]),
               "scoreboard players set @s %s 0" % O["clock"],
               "scoreboard players set @s %s 0" % O["stage"],
               "scoreboard players set @s %s 0" % O["bw"],
               "scoreboard players set @s %s 0" % O["bgo"],
               "scoreboard players set @s %s 0" % O["idle"],
               "scoreboard players set @s %s 0" % O["esc"],
               "scoreboard players set @s %s 0" % O["bossd"],
               "scoreboard players set @s %s 0" % O["cause"],
               "scoreboard players set @s %s 0" % O["claw"],
               "tag @s remove %s" % T["lost"],
               "tag @s remove %s" % T["next"],
               "tag @s remove %s" % T["warned"],
               "# the sigil: one of the band found by sigil/find_b<band>, taken by its component; remembered for the refund",
               "scoreboard players operation @s %s = #sig %s" % (O["paid"], O["t"])]
        go += ["execute if score #sig %s matches %d run clear @s %s 1" % (O["t"], x["band"], sigil_match(x, doc)) for x in sigils(doc)]
        if free:
            go += ["execute if score #sig %s matches -1 run advancement grant @s only %s:dungeons/free/%s" % (O["t"], NS, sh),
                   "execute if score #sig %s matches -1 run scoreboard players set @s %s 0" % (O["t"], O["paid"])]
        go += ["# E1 rule 1 and engine_must 2: the run tag now, and any tail from an earlier run cancelled",
               "tag @s add %s" % RUN_TAG,
               "scoreboard players set @s %s 0" % O["tail"]]
        for x in sigils(doc):
            go.append("execute if score #sig %s matches %d run %s" % (O["t"], x["band"], say(m["enter"].replace("{sigil}", x["name"]), "dark_purple")))
        if free:
            go.append("execute if score #sig %s matches -1 run %s" % (O["t"], say("The rift lets you in this once.", "dark_purple")))
        go.append("playsound minecraft:block.respawn_anchor.charge master @s ~ ~ ~ 1 0.8")
        out["door/go_%s" % sh] = go

    band = [HEAD, "# 5.1: the band from the RCT cap battle_check just read (%s), frozen for the run" % LC.CAP,
            "scoreboard players set @s %s 0" % O["band"]]
    prev = 0
    for b in bands(doc):
        hi = max(b["caps"])
        band.append("execute if score @s %s matches %d..%d run scoreboard players set @s %s %d"
                    % (LC.CAP, prev + 1, hi, O["band"], b["band"]))
        prev = hi
    band.append("execute if score @s %s matches %d.. run scoreboard players set @s %s %d" % (LC.CAP, prev + 1, O["band"], bands(doc)[-1]["band"]))
    band += ["# STAGING PLAYTEST (the owner, 2026-10-09: \"level 100 against 15s\"): a player tagged %s with %s 1..%d"
             % (PLAYTEST_TAG, O["ptband"], bands(doc)[-1]["band"]),
             "# runs at that band, whatever their cap. Never set for a real player: set by hand over RCON",
             "execute if entity @s[tag=%s] if score @s %s matches 1..%d run scoreboard players operation @s %s = @s %s"
             % (PLAYTEST_TAG, O["ptband"], bands(doc)[-1]["band"], O["band"], O["ptband"])]
    out["m/band"] = band

    for x in sigils(doc):
        f = [HEAD, "# 7.4: a band-%d entrant's sigil: their own band's, else the lowest higher band held" % x["band"]]
        f += ["execute if score #sig %s matches 0 if items entity @s container.* %s run scoreboard players set #sig %s %d"
              % (O["t"], sigil_match(y, doc), O["t"], y["band"]) for y in sigils(doc) if y["band"] >= x["band"]]
        f += ["execute if score #sig %s matches 0 if items entity @s container.* %s run scoreboard players set #weak %s 1"
              % (O["t"], sigil_match(y, doc), O["t"]) for y in sigils(doc) if y["band"] < x["band"]]
        out["sigil/find_b%d" % x["band"]] = f

    # ---- the slots -------------------------------------------------------------------------------------------
    for s in sl:
        d = s["dungeon"]
        g = s["g"]
        pt = points(doc, s)
        S = H(s)
        BAR = bar_id(s)
        box = sel_box(pt["box"])
        stag = "dg.s%d" % g
        ax, ay, az, ayaw = pt["arrive"]
        out["slot/s%d/reserve" % g] = [
            HEAD, "# Slot %d (%s %d) is this player's run now" % (g, d["id"], s["k"]),
            "scoreboard players operation %s %s = @s %s" % (S, O["own"], O["id"]),
            "scoreboard players operation %s %s = @s %s" % (S, O["run"], O["run"]),
            "scoreboard players operation %s %s = #up %s" % (S, O["dead"], O["up"]),
            "scoreboard players add %s %s %d" % (S, O["dead"], hold + k["arrive_delay_ticks"] + P),
            "scoreboard players set %s %s 0" % (S, O["bdone"]),
            "# the mutables (1, Instancing): the exit gate shut. Never under a player: the slot was free, and the keeper",
            "# puts out anyone who is not its member",
            "execute in %s run function %s" % (dim, F("slot/s%d/reset" % g))]
        if DR.has_rooms(d):
            out["slot/s%d/reset" % g] = ["# slot %d's mutable blocks, room by room, in %s (reserve carries the dimension in)" % (g, dim)] + DR.reset_lines(doc, s)
            out["slot/s%d/rooms" % g] = DR.rooms_lines(doc, s) + wb_lines(doc, s)
        else:
            out["slot/s%d/reset" % g] = function_limits.ensure_loaded(
                ["# slot %d's mutable blocks, in %s (reserve carries the dimension in)" % (g, dim)]
                + gate_lines(doc, s, d["spine"]["palette"]["gate"]))
        out["slot/s%d/arrive" % g] = [
            HEAD, "# As slot %d's member, the arrival delay over: into the entry room, adventure, the pick, the board" % g,
            "execute in %s run tp @s %s %d %s %d 0" % (dim, fmt(ax), ay, fmt(az), ayaw),
            "gamemode adventure @s",
            "tag @s add %s" % T["adv"],
            "give @s %s 1" % pick_give(doc, d),
            "scoreboard players set @s %s 2" % O["st"],
            "scoreboard players operation @s %s = #up %s" % (O["seen"], O["up"]),
            "title @s actionbar %s" % text(d["messages"]["arrive"], "light_purple")]
        start = [HEAD, "# As slot %d's member, crossing the threshold (x >= %d): the clock starts, the lockout is stamped and the"
                 % (g, pt["threshold_x"]),
                 "# sigil is spent (2.1, 2.5, 7.4)",
                 "scoreboard players set @s %s 3" % O["st"],
                 "scoreboard players reset @s %s" % O["wb"]]
        start += ["execute if score @s %s matches %d run scoreboard players set @s %s %d"
                  % (O["band"], b["band"], O["clock"], clock_s(d, b) * U) for b in bands(doc)]
        start += ["scoreboard players operation @s %s = @s %s" % (O["clk0"], O["clock"]),
                  "scoreboard players operation @s %s = #up %s" % (lk_obj(d), O["up"]),
                  "scoreboard players set @s %s 0" % O["paid"],
                  "function %s" % F("greed/zero"),
                  "bossbar add %s \"\"" % BAR,
                  "bossbar set %s players @s" % BAR,
                  "execute store result bossbar %s max run scoreboard players get @s %s" % (BAR, O["clk0"]),
                  "bossbar set %s visible true" % BAR,
                  "title @s actionbar %s" % text(d["messages"]["start"], "light_purple"),
                  "function %s" % F("m/digits"),
                  "function %s" % F("slot/s%d/bar" % g)]
        out["slot/s%d/start" % g] = start

        bar = [HEAD, "# As slot %d's member: the bar (2.2), its name rebuilt from scores resolved against @s (B1, EXP-070)" % g]

        def sc(obj):
            return {"score": {"name": "@s", "objective": obj}}
        base = gtab["rate"]["base"]
        for fast in (False, True):
            for taken in (False, True):
                parts = ["", {"text": "Rift "}, sc(O["mm"]), {"text": ":"}, sc(O["s10"]), sc(O["s1"]),
                         {"text": " · x"}, sc(GO["rx"]), {"text": "."}, sc(GO["ry"])]
                if fast:
                    parts += [{"text": " · ~"}, sc(O["lm"]), {"text": ":"}, sc(O["l10"]), sc(O["l1"]), {"text": " left"}]
                if taken:
                    parts += [{"text": " · taken "}, sc(GO["gw"]), {"text": "."}, sc(GO["gt"])]
                bar.append("execute if score @s %s matches %s if score @s %s matches %s run bossbar set %s name %s"
                           % (O["rate"], ("%d.." % (base + 1)) if fast else ("..%d" % base), GO["gp"], "1.." if taken else "..0",
                              BAR, json.dumps(parts, ensure_ascii=False)))
        bar += ["execute store result bossbar %s value run scoreboard players get @s %s" % (BAR, O["clock"])]
        cols = gtab["rate"]["colours"]
        for ci, (lo, col) in enumerate(cols):
            hi = cols[ci + 1][0] - 1 if ci + 1 < len(cols) else None
            bar.append("execute if score @s %s matches %d..%s run bossbar set %s color %s"
                       % (O["rate"], lo, "" if hi is None else hi, BAR, col))
        bar += ["execute if entity @s[tag=%s] run bossbar set %s color %s" % (T["warn"], BAR, e["clock"]["warn_colour"])]
        out["slot/s%d/bar" % g] = bar

        out["slot/s%d/free" % g] = [
            HEAD, "# Slot %d's run is over: the slot free, its bar emptied and removed (a stored UUID list shows again at" % g,
            "# reconnect, DM 1.2), its NPCs killed where loaded (a stale one elsewhere dies when its chunk loads: tend)",
            "scoreboard players set %s %s 0" % (S, O["own"]),
            "scoreboard players set %s %s 0" % (S, O["bdone"]),
            "# the slot forgets its run id (no run is numbered 0: #runs counts from 1), so a member who was away when it",
            "# freed matches nothing on return and m/member voids the run (data/dungeons.json absence; the audit's finding)",
            "scoreboard players set %s %s 0" % (S, O["run"]),
            "bossbar set %s players" % BAR,
            "bossbar remove %s" % BAR,
            "execute in %s run kill @e[type=cobblemon:npc,tag=%s]" % (dim, stag)]

        tend = [HEAD, "# Slot %d, owned, each pass. Is a member of this run alive and online? (2.6: an absent member's run dies" % g,
                "# with their clock, at the slot's deadline, and the slot is freed without waiting for them)",
                "scoreboard players set #here %s 0" % O["t"],
                "execute as @e[type=minecraft:player,scores={%s=1..,%s=%d}] if score @s %s = %s %s run scoreboard players set #here %s 1"
                % (O["st"], O["slot"], g, O["run"], S, O["run"], O["t"]),
                "execute if score #here %s matches 0 if score #up %s > %s %s run return run function %s"
                % (O["t"], O["up"], S, O["dead"], F("slot/s%d/free" % g)),
                "# stale NPCs (another run's, loaded again), and the bind backstop: any NPC in the slot unbound a pass after",
                "# its spawn is bound now, so every NPC here carries the exempt tag (V15; L1: a tick after a macro spawn)",
                "execute in %s as @e[type=cobblemon:npc,tag=%s] unless score @s %s = %s %s run kill @s" % (dim, stag, O["run"], S, O["run"]),
                "execute in %s as @e[type=cobblemon:npc,tag=!%s,%s] run function %s" % (dim, T["npc"], box, F("slot/s%d/bind" % g))]
        for nb in pt["no_deploy"]:
            nsel = sel_box(nb)
            tend += ["# the recall sweep (3.4), gated on P1's owner half: discard, never kill",
                     "execute in %s store result score #rc %s if entity @e[type=cobblemon:pokemon,%s,tag=!%s]"
                     % (dim, O["t"], nsel, e["sweep"]["keep_tag"]),
                     "execute in %s as @e[type=cobblemon:pokemon,%s,tag=!%s] run runmolang \"q.entity.discard;\""
                     % (dim, nsel, e["sweep"]["keep_tag"]),
                     "execute if score #rc %s matches 1.. in %s as @a[%s] run %s"
                     % (O["t"], dim, nsel, actionbar(e["sweep"]["message"], "light_purple")),
                     "execute in %s as @a[%s] run ride @s dismount" % (dim, nsel),
                     "execute in %s run kill @e[type=minecraft:ender_pearl,%s]" % (dim, nsel)]
        for rx, ry, rz in (pt["back"], pt["far"]):
            tend.append("execute in %s positioned %.1f %d %.1f if entity @a[distance=..%d] run particle minecraft:reverse_portal "
                        "~ ~1.5 ~ 0.3 1 1 0.02 12" % (dim, rx + 0.5, ry, rz + 0.5, k["rip_particle_range"]))
        out["slot/s%d/tend" % g] = tend

        out["slot/s%d/bind" % g] = [
            HEAD, "# As an NPC in slot %d: ours, this run's, and the blackout's exempt tag (2.5; E1 rule 5)" % g,
            "tag @s add %s" % T["npc"],
            "tag @s add %s" % stag,
            "tag @s add %s" % EXEMPT,
            "scoreboard players operation @s %s = %s %s" % (O["run"], S, O["run"])]

        # the staged boss (3.2): as the member
        sx, sy, sz = pt["spot"]
        classes = boss_classes(doc, d)
        spawn = [HEAD, "# As slot %d's member: stage dg.stage of their band's boss, spawned at the spot by a MACRO line (C1," % g,
                 "# EXP-078: a plain line naming our class fails to parse at load), bound in the same function and again by",
                 "# tend; the battle starts on the next pass (dg.bgo), a tick after the spawn (L1)",
                 "execute in %s run kill @e[type=cobblemon:npc,tag=%s,tag=%s]" % (dim, T["boss"], stag)]
        for b in bands(doc):
            for st in range(1, len(d["boss"]["stage_level_offsets"]) + 1):
                cname = "dg_%s_boss_b%d_s%d" % (d["short"], b["band"], st)
                spawn.append("execute if score @s %s matches %d if score @s %s matches %d in %s run function %s "
                             "{x:\"%.1f\",y:\"%d\",z:\"%.1f\",cls:\"%s:%s\",level:\"%d\"}"
                             % (O["band"], b["band"], O["stage"], st, dim, F("npc_at"), sx + 0.5, sy, sz + 0.5, NS, cname,
                                classes[cname][1]))
        spawn += ["execute in %s positioned %.1f %d %.1f as @e[type=cobblemon:npc,tag=!%s,distance=..1.5,sort=nearest,limit=1] "
                  "run function %s" % (dim, sx + 0.5, sy, sz + 0.5, T["npc"], F("slot/s%d/bind_boss" % g)),
                  "scoreboard players set @s %s 1" % O["bgo"],
                  "scoreboard players set @s %s 0" % O["idle"]]
        out["slot/s%d/spawn" % g] = spawn
        out["slot/s%d/bind_boss" % g] = [HEAD, "function %s" % F("slot/s%d/bind" % g), "tag @s add %s" % T["boss"]]
        nstages = len(d["boss"]["stage_level_offsets"])
        bsel = "@e[type=cobblemon:npc,tag=%s,tag=%s,limit=1]" % (T["boss"], stag)
        boss = [HEAD, "# As slot %d's member whose clock runs: the staged boss (3.2), separate fights chained by the victory" % g,
                "# callback (D2). Gated on C1's owner half: the chain itself is unproven",
                "execute if score @s %s matches 0 if score %s %s matches 0 if entity @s[%s] run scoreboard players set @s %s 1"
                % (O["stage"], S, O["bdone"], sel_box(pt["arena_box"]), O["stage"]),
                "# the gap between stages, counted down on the member (next sets gap_ticks + period)",
                "execute if score @s %s matches 1.. run scoreboard players remove @s %s %d" % (O["bw"], O["bw"], P),
                "execute if score @s %s matches 1.. run return 0" % O["bw"],
                "execute if score @s %s matches ..-1 run scoreboard players set @s %s 0" % (O["bw"], O["bw"]),
                "execute if score @s %s matches 1..%d if score %s %s matches 0 unless entity %s run return run function %s"
                % (O["stage"], nstages, S, O["bdone"], bsel, F("slot/s%d/spawn" % g)),
                "execute if score @s %s matches 1 run return run function %s" % (O["bgo"], F("slot/s%d/go" % g)),
                "execute if entity @s[tag=%s] run return run runmolang \"(q.player.in_battle == 0) ? { q.run_command('execute as ' "
                "+ q.player.uuid + ' at @s run function %s'); };\" @s" % (T["next"], F("slot/s%d/next" % g)),
                "# a stage standing with no result while the member is out of battle (a forfeit or flee): start it again",
                "execute if score @s %s matches 1..%d if score %s %s matches 0 run runmolang \"(q.player.in_battle == 0) ? { "
                "q.run_command('execute as ' + q.player.uuid + ' run scoreboard players add @s %s 1'); };\" @s"
                % (O["stage"], nstages, S, O["bdone"], O["idle"]),
                "execute if score @s %s matches %d.. run scoreboard players set @s %s 1"
                % (O["idle"], k["boss_restart_idle_passes"], O["bgo"])]
        out["slot/s%d/boss" % g] = boss
        out["slot/s%d/go" % g] = [
            HEAD, "# The stage's battle, started with no click (arena note section 8; the probes' start): runmolang as the",
            "# member, the NPC as the npc argument. start_battle returns 0 when refused: then dg.bgo is set again",
            "scoreboard players set @s %s 0" % O["bgo"],
            "scoreboard players set @s %s 0" % O["idle"],
            "# the clawback's bounds for this stage and the balance baseline (tools/dungeon_fights.py), before the battle",
            "function %s" % F("claw/boss_begin_%s" % d["short"]),
            "execute in %s run runmolang \"t.b = q.npc.start_battle(q.player, 'singles'); (t.b == 0) ? { "
            "q.run_command('execute as ' + q.player.uuid + ' run scoreboard players set @s %s 1'); };\" @s %s"
            % (dim, O["bgo"], bsel)]
        nxt = [HEAD, "# As slot %d's member, out of battle after beating stage dg.stage (queued by runmolang): the stage is" % g,
               "# killed, the cue, and stage k+1 after gap_ticks; after the last, the gate opens (3.2)",
               "execute unless entity @s[tag=%s] run return 0" % T["next"],
               "tag @s remove %s" % T["next"],
               "execute in %s run kill @e[type=cobblemon:npc,tag=%s,tag=%s]" % (dim, T["boss"], stag),
               "scoreboard players add @s %s 1" % O["stage"],
               "scoreboard players set @s %s 0" % O["idle"],
               "execute if score @s %s matches ..%d run title @s title %s" % (O["stage"], nstages, text(d["boss"]["cue"]["title"], "dark_red"))]
        roman = ["I", "II", "III", "IV", "V"]
        for st in range(2, nstages + 1):
            nxt.append("execute if score @s %s matches %d run title @s subtitle %s"
                       % (O["stage"], st, text("%s of %s" % (roman[st - 1], roman[nstages - 1]), "gray")))
        nxt += ["execute if score @s %s matches ..%d run playsound minecraft:entity.warden.emerge master @s ~ ~ ~ 1 0.8"
                % (O["stage"], nstages),
                "execute if score @s %s matches ..%d run scoreboard players set @s %s %d"
                % (O["stage"], nstages, O["bw"], d["boss"]["gap_ticks"] + P),
                "execute if score @s %s matches %d.. run function %s" % (O["stage"], nstages + 1, F("slot/s%d/boss_done" % g))]
        out["slot/s%d/next" % g] = nxt
        out["slot/s%d/boss_done" % g] = [
            HEAD, "# chunks-loaded-by: the member standing in the arena beside the gate (this runs as them, in slot %d)" % g,
            "# The last stage fell: the exit gate opens and the boss's escrow flag is set (3.2 step 5)",
            "scoreboard players set %s %s 1" % (S, O["bdone"]),
            "scoreboard players set @s %s 1" % O["bossd"]] + (
            [DR.arena_clear_line(doc, s)] if DR.has_rooms(d) else
            ["execute in %s run %s" % (dim, l) for l in gate_lines(doc, s, "minecraft:air")]) + [
            "title @s title %s" % text(d["boss"]["cue"]["done"], "gold")]

    for di, d in enumerate(ds, 1):
        chk = [HEAD, "# As a living player in %s's slots (in %s, dimension-safe): a member standing in their own slot is" % (d["id"], dim),
               "# fine; one whose run has ended keeps the tail's grace; anyone else is put out (6: the ownership sweep)",
               "scoreboard players set #ok %s 0" % O["t"]]
        chk += ["execute if score @s %s matches 2.. if score @s %s matches %d if score @s %s = %s %s if entity @s[%s] "
                "run scoreboard players set #ok %s 1" % (O["st"], O["slot"], s["g"], O["run"], H(s), O["run"],
                                                          sel_box(points(doc, s)["box"]), O["t"]) for s in dsel(di)]
        chk += ["execute if score @s %s matches 1.. run scoreboard players set #ok %s 1" % (O["tail"], O["t"]),
                "execute if score #ok %s matches 1 run return 0" % O["t"],
                say(d["messages"]["eject"], "gray"),
                "execute if entity @s[tag=%s] run gamemode survival @s" % T["adv"],
                "tag @s remove %s" % T["adv"],
                "clear @s %s" % pick_match(doc),
                "function %s" % F("m/out_%s" % d["short"])]
        out["check_%s" % d["short"]] = chk

    out["npc_at"] = ["# the macro spawn (C1, EXP-078): parsed when it runs, not at load; run `in` the pocket",
                     "$spawnnpcat $(x) $(y) $(z) $(cls) $(level)"]

    # ---- the rips' particles (7.1) ---------------------------------------------------------------------------
    emit = [HEAD, "# every %d ticks: each overworld rip's particles while a player is within %d blocks (7.1)"
            % (k["rip_particle_period_ticks"], k["rip_particle_range"])]
    for d in ds:
        f = d["rip"]["frame"]
        cx = (f["x0"] + f["x1"]) / 2.0 + 0.5
        emit += ["execute in minecraft:overworld positioned %.1f %d %.1f if entity @a[distance=..%d] run particle "
                 "minecraft:reverse_portal ~ ~1.5 ~ 0.8 1 0.2 0.02 16" % (cx, f["y"], f["z"] + 0.5, k["rip_particle_range"]),
                 "execute in minecraft:overworld positioned %.1f %d %.1f if entity @a[distance=..%d] run particle "
                 "minecraft:portal ~ ~1.5 ~ 0.8 1 0.4 0.4 8" % (cx, f["y"], f["z"] + 0.5, k["rip_particle_range"])]
    emit.append("schedule function %s %dt replace" % (F("rips/emit"), k["rip_particle_period_ticks"]))
    out["rips/emit"] = emit

    # ---- the recipe book (7.4; Q23 OPEN: the gate's mode is data) --------------------------------------------
    rg = e["sigils"]["recipe_gate"]
    out["recipes/sync"] = [HEAD, "# every %d ticks: each online player's sigil recipes (mode %s, Q23 OPEN; gated on SG1's owner half)"
                           % (k["recipe_sync_period_ticks"], rg["mode"]),
                           "execute as @a run function %s {x:\"\"}" % F("recipes/one"),
                           "schedule function %s %dt replace" % (F("recipes/sync"), k["recipe_sync_period_ticks"])]
    one = [HEAD, "# as a player: their sigil recipes"]
    if rg["mode"] == "all":
        one += ["recipe give @s %s" % recipe_id(x) for x in sigils(doc)]
    else:
        one += ["scoreboard players set @s %s 0" % O["cap"],
                "# the cap on a MACRO line (EXP-046; tools/levelcap_pack.py battle_check reads it the same way)",
                "$execute store result score @s %s run rctmod player get level_cap @s$(x)" % O["cap"],
                "execute unless score @s %s matches 1.. run return 0" % O["cap"],
                "scoreboard players set @s %s 0" % O["rb"]]
        prev = 0
        for b in bands(doc):
            hi = max(b["caps"])
            one.append("execute if score @s %s matches %d..%d run scoreboard players set @s %s %d" % (O["cap"], prev + 1, hi, O["rb"], b["band"]))
            prev = hi
        one.append("execute if score @s %s matches %d.. run scoreboard players set @s %s %d" % (O["cap"], prev + 1, O["rb"], bands(doc)[-1]["band"]))
        for x in sigils(doc):
            one += ["execute if score @s %s matches %d.. run recipe give @s %s" % (O["rb"], x["band"], recipe_id(x)),
                    "execute unless score @s %s matches %d.. run recipe take @s %s" % (O["rb"], x["band"], recipe_id(x))]
    out["recipes/one"] = one

    # ---- the re-apply steps' functions -----------------------------------------------------------------------
    if not any(DR.has_rooms(x) for x in ds):
        # the short spine's one call; a full-length build re-applies per slot (place/s<g>, reapply_steps) and never calls
        # these: emitted, they are orphans no step runs, and 296,949 commands past the chain limit (DG-AUDIT finding 5)
        out["place"] = [HEAD, "# tools/reapply.py step R16DG: every slot's shell, in %s. The pocket's contents do not survive a" % dim,
                        "# re-export (EXP-047), so the shells are re-applied, never hand-built. The entities follow (shells/entities)",
                        "execute in %s run function %s" % (dim, F("shells/build"))]
        out["shells/build"] = ["# runs with %s as its execution dimension (place carries it in)" % dim] + [
            "function %s" % F("shells/s%d" % s["g"]) for s in sl]
    for s in sl:
        if any(DR.has_rooms(x) for x in ds):
            out["place/s%d" % s["g"]] = ["# one slot's shell, in %s: a re-apply step of its own, so no call holds the tick for long (EXP-081)" % dim,
                                         "execute in %s run function %s" % (dim, F("shells/s%d" % s["g"]))]
        if DR.has_rooms(s["dungeon"]):
            out.update(DR.shell_functions(doc, s))
            continue
        out["shells/s%d" % s["g"]] = function_limits.ensure_loaded(
            ["# slot %d's shell (%s %d), %d blocks written; place carries the dimension in"
             % (s["g"], s["dungeon"]["id"], s["k"], shell_blocks(doc, s))] + shell_lines(doc, s))
    for di, d in enumerate(ds, 1):
        if DR.has_rooms(d):
            out.update(DR.runtime_functions(doc, d, dsel(di)))
    out["rips/place"] = [HEAD, "# tools/reapply.py step R16DR: every overworld rip's blocks (its entity follows: rips/entities)"] + [
        "execute in minecraft:overworld run function %s" % F("rips/blocks_%s" % d["short"]) for d in ds]
    for d in ds:
        out["rips/blocks_%s" % d["short"]] = function_limits.ensure_loaded(
            ["# %s's rip (data/dungeons.json rip: a PLACEHOLDER in the old mine's notch)" % d["name"]] + rip_lines(d))
    return out


def chains(doc):
    """{function id: lines} for the two look-then-act chains (tools/chunk_look.py): the shells' entities in the pocket
    and the rips' interactions in the overworld."""
    dim = doc["engine"]["pocket"]["dimension"]
    sl = slots(doc)
    acts, shown, scopes, boxes = [], [], [], []
    for s in sl:
        st = "%s.%s%d" % (TAGS["shell"], s["dungeon"]["short"], s["k"])
        acts.append("execute in %s run kill @e[tag=%s]" % (dim, st))
        ents = shell_entities(doc, s)
        acts += [line for line, _kind in ents]
        shown.append("@e[tag=%s]" % st)
        scopes += ["tag=%s,tag=%s" % (st, kind) for _line, kind in ents]
        # a small box round each entity, never the slot's: a full-length slot is 292-348 chunks and `forceload add`
        # refuses more than 256 in one area, so nothing loaded and the chain never saw its entities (staging,
        # 2026-10-09: "0 of 36 standing ... it never finished")
        for line, _kind in ents:
            m = re.search(r"summon \S+ (-?[\d.]+) -?[\d.]+ (-?[\d.]+)", line)
            ex, ez = int(float(m.group(1))), int(float(m.group(2)))
            boxes.append((ex - 4, ez - 4, ex + 4, ez + 4))
    want_shell = sum(len(shell_entities(doc, s)) for s in sl)
    out = chunk_look.chain(F("shells/entities"), boxes, shown, acts, scopes, TAGS["shell_new"], "tag=%s" % TAGS["shell"],
                           SHELL_HOLDER, note="tools/dungeon.py", all_shown=True, dim=dim)
    racts, rshown, rscopes, rboxes = [], [], [], []
    for d in dungeons(doc):
        tag = rip_tag(d)
        x, y, z = d["rip"]["click"]
        racts += ["kill @e[type=minecraft:interaction,tag=%s]" % tag,
                  "summon minecraft:interaction %.1f %d %.1f {width:3.0f,height:3.0f,response:1b,Tags:[\"%s\",\"%s\",\"%s\"]}"
                  % (x + 0.5, y, z + 0.5, TAGS["rip"], tag, TAGS["rip_new"]),
                  # the oval (engine.rip_art): killed and summoned with the interaction, in the same chain and de-duplicated
                  # by its own scope; the chain's count (interactions) and `shown` (an interaction) are unchanged
                  "kill @e[type=minecraft:item_display,tag=%s,tag=%s]" % (tag, oval_tag(doc)),
                  oval_summon(doc, d)]
        rshown.append("@e[type=minecraft:interaction,tag=%s]" % tag)
        rscopes.append("type=minecraft:interaction,tag=%s" % tag)
        rscopes.append("type=minecraft:item_display,tag=%s,tag=%s" % (tag, oval_tag(doc)))
        rboxes.append((x - 4, z - 4, x + 4, z + 4))
    out.update(chunk_look.chain(F("rips/entities"), rboxes, rshown, racts, rscopes, TAGS["rip_new"],
                                "type=minecraft:interaction,tag=%s" % TAGS["rip"], RIP_HOLDER, note="tools/dungeon.py",
                                all_shown=True))
    return out, want_shell, len(dungeons(doc))


def reapply_steps(doc=None):
    """tools/reapply.py's two steps: R16DG the shells and their entities, R16DR the overworld rips."""
    doc = doc if doc is not None else load()
    _c, want_shell, want_rips = chains(doc)
    if any(DR.has_rooms(d) for d in dungeons(doc)):
        # full-length shells: one re-apply call per slot, so no single call holds the tick (EXP-081: ~0.5M blocks is 1-2.6 s)
        place = [("fn", F("place/s%d" % s["g"])) for s in slots(doc)]
    else:
        place = [("fn", F("place"))]
    return [("R16DG", "the dungeon slots' shells in cobblers:pocket (data/dungeons.json)",
             place + chunk_look.steps(F("shells/entities"), SHELL_HOLDER, want_shell, "dungeon shell entities")),
            ("R16DR", "the dungeon rips in the overworld (data/dungeons.json; the Night Shift's is a placeholder)",
             [("fn", F("rips/place"))] + chunk_look.steps(F("rips/entities"), RIP_HOLDER, want_rips, "dungeon rips"))]


def callback(doc):
    """battle_victory: a stage of OUR boss beaten tags the player dg.next; a stage that beat them tags dg.lost. The
    probes' callback shape (tools/dungeon_probes.py victory_callback, C1), keyed on our boss tag."""
    import dungeon_fights as DF     # lazy: tools/dungeon_fights.py imports this module
    nt, lt, bt = TAGS["next"], TAGS["lost"], TAGS["boss"]
    return "\n".join([
        "'Generated by tools/dungeon.py from data/dungeons.json. Acts only on an NPC tagged %s (the boss chain) or dg.npc (the clawback) or dg.stand (the clear of a stand).';" % bt,
        "for_each(t.l, c.scriptable_losers, { t.l.is_npc ? { for_each(t.w, c.player_winners, {",
        "  q.run_command('execute as ' + t.l.uuid + ' if entity @s[tag=%s] run tag ' + t.w.player.username + ' add %s');" % (bt, nt)] +
        DF.victory_commands() + [
        "}); }; });",
        "for_each(t.w, c.scriptable_winners, { t.w.is_npc ? { for_each(t.p, c.player_losers, {",
        "  q.run_command('execute as ' + t.w.uuid + ' if entity @s[tag=%s] run tag ' + t.p.player.username + ' add %s');" % (bt, lt),
        "}); }; });", ""])


def impossible():
    return {"criteria": {"granted": {"trigger": "minecraft:impossible"}}, "requirements": [["granted"]]}


def build(doc, **kw):
    bad = problems(doc, **{k: v for k, v in kw.items() if k in ("portals_doc", "entei_doc", "probes_doc", "blackout", "progression")})
    if bad:
        raise DungeonError("data/dungeons.json: " + "; ".join(bad))
    files = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the dungeon engine, timed rift runs in cobblers:pocket (tools/dungeon.py)"}},
                                  indent=2) + "\n",
        "data/minecraft/tags/function/load.json": json.dumps({"values": [F("load")]}, indent=2) + "\n",
    }
    for kind in ("back", "far"):
        files["data/%s/advancement/dungeons/%s.json" % (NS, kind)] = json.dumps(
            portals.click_advancement(TAGS[kind], F(kind)), indent=2) + "\n"
    for d in dungeons(doc):
        files["data/%s/advancement/dungeons/rip_%s.json" % (NS, d["short"])] = json.dumps(
            portals.click_advancement(rip_tag(d), F("door/%s" % d["short"])), indent=2) + "\n"
        if d["id"] in doc["engine"]["sigils"]["free_first_entry"]["dungeons"]:
            files["data/%s/advancement/dungeons/free/%s.json" % (NS, d["short"])] = json.dumps(impossible(), indent=2) + "\n"
        for name, (cls, _lvl) in boss_classes(doc, d).items():
            files["data/%s/npcs/%s.json" % (NS, name)] = json.dumps(cls, indent=2) + "\n"
    for x in sigils(doc):
        files["data/%s/recipe/dg_sigil_b%d.json" % (NS, x["band"])] = json.dumps(sigil_recipe(x, doc), indent=2) + "\n"
    import dungeon_puzzles as DP    # lazy, as dungeon_fights is: the vault rooms' loot tables (unit DG-PUZZLES)
    files.update(DP.pack_files(doc))
    fns = functions(doc, kw.get("blackout"))
    import dungeon_fights as DF     # lazy: tools/dungeon_fights.py imports this module
    fns.update(DF.functions(doc))   # the clawback (DG-CLAW), and the fight rooms' stands, wild Pokemon and healer (DG-FIGHTS)
    DF.patch_functions(doc, fns)    # a run's end and the keeper's pass discard the slot's wild Pokemon
    import dungeon_life as DL       # lazy, as dungeon_fights is (unit LIFE): the ambient Pokemon's macro and per-slot claim
    fns.update(DL.functions(doc))
    DL.patch_functions(doc, fns)    # and a slot whose only animals are ambient discards them at its free and tend too
    import dungeon_relics as DRel   # lazy, as dungeon_life is (unit DG2-RELICS): the secrets' relics and each dungeon's collection
    fns.update(DRel.functions(doc))
    DRel.patch_functions(doc, fns)  # the arrival line and the lobby's action bar
    import dungeon_prize as DPz     # lazy (KIT3): the hidden prize's roll at the threshold and the board put back at arrival
    DPz.patch_functions(doc, fns)
    files.update(DRel.pack_files(doc))  # a dungeon's collection advancement
    files.update(DF.pack_files(doc))    # the stands' NPC classes and the healer's advancement
    import dungeon_resources as DRS     # lazy (RESOURCES2): the resources rooms' cache loot tables
    files.update(DRS.pack_files(doc))
    files["data/minecraft/tags/function/load.json"] = json.dumps(
        {"values": [F("load")] + DF.load_entries() + DL.load_entries(doc) + DRel.load_entries(doc)}, indent=2) + "\n"
    files["data/minecraft/tags/function/tick.json"] = json.dumps({"values": DF.tick_entries()}, indent=2) + "\n"
    ch, _ws, _wr = chains(doc)
    for ref, lines in ch.items():
        fns[ref.split(":", 1)[1][len(FOLDER) + 1:]] = lines
    for name, lines in fns.items():
        rel = "data/%s/function/%s/%s.mcfunction" % (NS, FOLDER, name)
        refused = function_limits.check_lines(lines, rel)
        if refused:
            for ln, cmd, why in refused:
                print("REFUSED %s line %d: %s\n   %s" % (rel, ln, why, cmd))
            raise SystemExit("%s: %d command(s) the server would refuse; nothing written" % (rel, len(refused)))
        files[rel] = "\n".join(lines) + "\n"
    files[CALLBACK] = callback(doc)
    import dungeon_greed as DG      # lazy (unit GREED): a catch in a live run weighs on the clock
    files[DG.CALLBACK_PATH] = DG.callback(doc)
    # a room's s<g>/clear that nothing calls (a room whose door is open from the start: a drift, the exit) is a function
    # no step or pack runs, which prepare refuses; the kit emits one per room so every kind can call it, and the pack
    # keeps only the ones that are called (2026-10-09)
    # Only an OPEN room's: a `cleared` room's clear is kept even uncalled, so the orphan check names a door nothing opens
    # (a softlock) instead of the build hiding it.
    rx = re.compile(r"^data/%s/function/%s/room/([^/]+)/([^/]+)/s\d+/clear\.mcfunction$" % (NS, FOLDER))
    held = {(d["id"], r["id"]) for d in dungeons(doc) if DR.has_rooms(d)
            for r in DR.layout(doc, d, [s for s in slots(doc) if s["dungeon"] is d][0]) if r.get("gate") == "cleared"}
    for rel in [k for k in files if rx.match(k)]:
        if rx.match(rel).groups() in held:
            continue
        ref = F(rel.split("/function/%s/" % FOLDER)[1][:-len(".mcfunction")])
        if not any(ref in v for k, v in files.items() if k != rel and isinstance(v, str)):
            del files[rel]
    return files


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, body in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")


def warnings(doc):
    """Things that build but are not finished: kinds declared in a dungeon's rooms with no implementation yet, and a
    rooms dungeon still on the bands' clocks (set for the short spine; tools/dungeon_clock.py derives its own)."""
    import dungeon_fights as DF     # lazy: tools/dungeon_fights.py imports this module
    import dungeon_relics as DRel   # lazy (DG2-RELICS)
    import dungeon_greed as DG      # lazy (KIT3): vault chests over the budget while it is not enforced
    return DR.warnings(doc) + DF.warnings(doc) + DRel.warnings(doc) + DG.vault_warnings(doc) + [
        "%s: no clock_s_by_band, so its clock is the bands' (the short spine's): run python tools/dungeon_clock.py %s"
        % (d["id"], d["id"]) for d in dungeons(doc) if DR.has_rooms(d) and "clock_s_by_band" not in d]


def report(doc):
    lines = []
    for s in slots(doc):
        pt = points(doc, s)
        lines.append("%s slot %d (#s%d): z %d..%d, spine %d long, box %s, %d blocks written by its shell"
                     % (s["dungeon"]["id"], s["k"], s["g"], s["z0"], s["z0"] + doc["engine"]["slots"]["strip_width_max"] - 1,
                        pt["length"], pt["box"], shell_blocks(doc, s)))
    return lines


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", default=str(DATA))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--report", action="store_true", help="the shells' block counts and boxes; write nothing")
    a = p.parse_args(argv)
    doc = load(a.data)
    if a.report:
        print("\n".join(report(doc) + ["WARNING: " + w for w in warnings(doc)]))
        return 0
    files = build(doc)
    write(files, a.out)
    for w in warnings(doc):
        print("WARNING: " + w)
    print("cobblers_dungeons: %d files -> %s" % (len(files), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
