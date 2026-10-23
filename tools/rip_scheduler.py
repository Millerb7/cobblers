#!/usr/bin/env python
"""The rip scheduler: dungeon rips that OPEN at random candidate places and CLOSE again, as a runtime datapack.

The owner, 2026-10-14: "i thought we were placing possible spawn locations and then randomly having them appear all over?"
data/dungeon_rips.json 'rips' is therefore a POOL of candidate places, and this tool emits the pack (cobblers_rips) that keeps
a few of them open at a time. Settings: data/rip_scheduler.json (proposed defaults, none confirmed by the owner).

  python tools/rip_scheduler.py                       # write build/datapacks/cobblers_rips
  python tools/rip_scheduler.py --out <dir>
  python tools/rip_scheduler.py --measure             # function/file/line counts of the pack, nothing written
  python tools/rip_scheduler.py --check               # the build's own fail-closed checks, nothing written

MECHANISM (principle 6: datapack functions and scoreboard timers; no mod, no scripting layer, no companion process)

  clock      cobblers:rips/pass reschedules itself every pass_seconds (`schedule function ... replace`), started by the
             minecraft:load tag and by R16DR's call of cobblers:rips/init. A schedule is saved in the world, so it survives a
             stop; the load function arms it again anyway. With nobody online the pass does nothing: play time is what ages a rip.
  state      objective rp.s, holder #r<i> (i = the rip's index in data/dungeon_rips.json 'rips', 1-based: the SAME number as
             dg.rip, which is how the dungeon engine names the rip a run was entered by): 0 closed, 1 open, 2 closing.
             rp.t the open rip's remaining play ticks; rp.l the closing rip's remaining kill polls; rp.v the variables.
  cap, pick  each pass counts the open rips (a recount, so a crash cannot leave a wrong count). Below open_min it opens one;
             below open_max it opens one with a 1-in-K chance (K from extra_open_every_minutes). "Opens one" = a uniform random
             candidate (`random value 1..M`); if that candidate is not eligible this pass, nothing opens and the next pass draws again.
  near       one opening in near_player_share is drawn near a player instead (the owner, 2026-10-21: "focus some closer to
             players, not all though"): a random online overworld player, then a uniform random candidate within
             near_player_radius of them that is closed and whose region has none open; none such, the uniform pick.
  open       cobblers:rips/o<i>, all in one tick: the checks (below), forceload the footprint's chunks, SAVE (rip.under), write the
             rip (tools/dungeon.py rip_lines: the plane cleared to rip.restore, the themed patch), stand the click and the oval
             (rip_entity_lines), set the state and the timer, tell every player, release the chunks.
  close      cobblers:rips/c<i>: when the timer has run out, or a run has begun by this rip (close_when_entered): the checks, forceload,
             kill the click and the oval, give the ground back (rip_close_lines), state 2; cobblers:rips/x<i> then kills the entities
             again every 20 ticks for chunk_look.POLLS looks (a chunk's saved entities arrive some ticks after a forceload:
             tools/chunk_look.py) and only then sets the state to 0 and releases the chunks.
  rip.under  the SKY HOLD. Before an open writes anything, every cell it will write is `clone`d up to hold_y in the same chunks
             (the same x and z, y moved), and the close clones them back and clears the hold. Why this and not the alternatives:
             the heightmap holds heights, not the surface block, and a recorded list of block names loses block states,
             vegetation and block entities; `clone` copies a cell exactly and is the one vanilla command that does. No
             data/dungeon_rips.json record changes: the snapshot lives in the world, in the rip's own chunks, between open
             and close, and 'exact' is a property of the world after the close (tests/test_rip_scheduler.py replays it).

SAFETY (each is a property of the emitted text, asserted in tests/test_rip_scheduler.py)

  not on a player      open and close both stop (`return 0`, nothing written) while any player in the overworld is inside the rip's
                       9 x 7 siting window (x0-2..x1+2, z-1..z+5, a block under the ground to six over it). The check runs in the
                       function that writes, in the same tick, after the chunks are loaded. A close that finds someone there leaves
                       the state at open with the timer at 0 and tries again next pass.
  not a return point   open stops while any player in a run (dg.st >= 1) has this rip's number in dg.rip: the engine sends that
                       player out at this rip's exit point (m/out), which must not be in the middle of a freshly opened rip.
  the way out          a run's exit goes to the rip it was entered by (dg.rip, tools/dungeon.py m/out). If that rip is closed, the
                       exit point is on the ground the close gave back: the SAFE FALLBACK is the closed rip's own exit point, and it
                       lies outside every cell the scheduler writes (checked for every candidate). Nobody is sent to another rip.
  forceload            a site's chunks are held from before the first command that writes until the last, in the same function for
                       an open; a close holds them until its last kill poll. Both then `forceload remove`.
  one per region       with one_open_per_region, a candidate whose region has another rip open does not open.

WHAT THIS DOES NOT COVER (CLAUDE.md "Our list is not the world"): the exit cell and the column above it are not written, so they are
whatever the world holds there (the siting rules check flat, dry, clear of authored points, not a tree); a player who is offline
mid-run is not seen by the return-point check (he comes back to the exit point on the closed ground); a Pokemon or mob standing in the
footprint is not looked for (only players); nothing here reads the world at build time (the ground is the heightmap's, in the records).
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

import chunk_look  # noqa: E402
import dungeon as D  # noqa: E402
import dungeon_rips as DRP  # noqa: E402
import function_limits  # noqa: E402

DATA = ROOT / "data" / "rip_scheduler.json"
HEIGHT_PACK = ROOT / "modpack" / "datapacks" / "cobblers_height" / "data" / "minecraft" / "dimension_type" / "overworld.json"
SCHEMA = "cobblers.rip_scheduler/1"
NS = "cobblers"
FOLDER = "rips"
PACK = "cobblers_rips"
PACK_FORMAT = 48          # Minecraft 1.21.1
DEFAULT_OUT = ROOT / "build" / "datapacks" / PACK
HEAD = "# Generated by tools/rip_scheduler.py from data/rip_scheduler.json and data/dungeon_rips.json; never edit (build/ is regenerated)."
OBJ = {"s": "rp.s", "t": "rp.t", "l": "rp.l", "v": "rp.v"}       # 16 characters at most
HOLDER = "#r%d"
KNOWN = ("enabled", "open_min", "open_max", "lifetime_minutes", "lifetime_jitter_minutes", "close_when_entered",
         "close_after_entry_seconds", "sites", "gated_sites", "announce", "one_open_per_region", "extra_open_every_minutes",
         "pass_seconds", "hold_y", "near_player_share", "near_player_radius")
TARGET_TAG = "rp.target"               # the one player pick_near draws near, tagged for the length of that function
STORE = "%s:rips" % NS                 # the storage pick_near hands its count to near_draw through
OVERWORLD = "minecraft:overworld"
CHECK_BELOW, CHECK_ABOVE = 1, 6        # blocks under the ground and over it that count as "on" the rip
DX_AIR = 8                             # the siting window's 9 columns (dx is the span from the first block)


def F(name):
    return "%s:%s/%s" % (NS, FOLDER, name)


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def values(doc):
    return {k: v["value"] for k, v in doc["settings"].items()}


def settings_problems(doc):
    """[problem] in data/rip_scheduler.json: the shape, and every value in range. Fail closed: a setting nobody validated is a
    number the pass would run on."""
    bad = []
    if doc.get("schema") != SCHEMA:
        bad.append("schema must be %s" % SCHEMA)
    s = doc.get("settings") or {}
    if sorted(s) != sorted(KNOWN):
        bad.append("settings must be exactly %s, found %s" % (sorted(KNOWN), sorted(s)))
        return bad
    for k, rec in s.items():
        if not isinstance(rec.get("owner_confirmed"), bool) or not rec.get("origin") or "value" not in rec:
            bad.append("%s: needs value, owner_confirmed (a bool) and origin" % k)
    if bad:
        return bad
    v = values(doc)

    def integer(k, lo, hi=None):
        if not isinstance(v[k], int) or isinstance(v[k], bool) or v[k] < lo or (hi is not None and v[k] > hi):
            bad.append("%s must be an integer >= %d%s, found %r" % (k, lo, "" if hi is None else " and <= %d" % hi, v[k]))
    for k in ("enabled", "close_when_entered", "one_open_per_region"):
        if not isinstance(v[k], bool):
            bad.append("%s must be true or false" % k)
    integer("open_min", 0)
    integer("open_max", 1)
    integer("lifetime_minutes", 1)
    integer("lifetime_jitter_minutes", 0)
    integer("close_after_entry_seconds", 0, 3600)
    integer("extra_open_every_minutes", 1)
    integer("pass_seconds", 1, 600)
    integer("hold_y", 0)
    integer("near_player_share", 0)
    integer("near_player_radius", 16, 4096)
    if not bad:
        if v["open_min"] > v["open_max"]:
            bad.append("open_min %d is above open_max %d" % (v["open_min"], v["open_max"]))
        if v["lifetime_jitter_minutes"] >= v["lifetime_minutes"]:
            bad.append("lifetime_jitter_minutes must be under lifetime_minutes (a rip would open already expired)")
    if v["sites"] != "anywhere":
        bad.append("sites: only 'anywhere' is built (the owner's proposal); found %r" % (v["sites"],))
    if v["gated_sites"] not in ("allow", "exclude"):
        bad.append("gated_sites must be 'allow' or 'exclude'")
    if not isinstance(v["announce"], str) or "{region}" not in v["announce"]:
        bad.append("announce must be a string with {region} in it")
    return bad


def overworld_top():
    """The highest block the overworld holds: min_y + height - 1 of the dimension type the world runs (cobblers_height)."""
    d = json.loads(HEIGHT_PACK.read_text(encoding="utf-8"))
    return d["min_y"] + d["height"] - 1


def pool(ddoc, rdoc):
    """[(index, rip)]: the candidates. index is the rip's 1-based place in data/dungeon_rips.json 'rips' (dg.rip's number).
    gated_sites 'exclude' drops a rip with reachable_after; it keeps its number."""
    v = values(rdoc)
    return [(i, r) for i, r in enumerate(D.rips(ddoc), 1) if not (v["gated_sites"] == "exclude" and r.get("reachable_after"))]


def region_names():
    doc = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    return {r["id"]: r["display_name"] for r in doc["regions"]}


def region_phrase(name):
    return "the " + name[4:] if name.startswith("The ") else name


def window_of(r):
    return DRP.window(r["frame"])               # (x0, z0, x1, z1), the 9 x 7 siting window


def check_selector(r):
    """(positioned x, y, z, selector): the box in which a player counts as ON the rip."""
    wx0, wz0, wx1, wz1 = window_of(r)
    gy = r["frame"]["y"] - 1
    return (wx0, gy - CHECK_BELOW, wz0, "@a[dx=%d,dy=%d,dz=%d]" % (wx1 - wx0, CHECK_BELOW + CHECK_ABOVE, wz1 - wz0))


def forceload_box(r):
    """(x0, z0, x1, z1): the blocks whose chunks are held while the rip is written: the write boxes, the hold (the same x and z) and
    the entities all stand inside it."""
    bs = D.rip_write_boxes(r)
    return (min(b[0] for b in bs), min(b[2] for b in bs), max(b[3] for b in bs), max(b[5] for b in bs))


def chunk_count(box):
    return (box[2] // 16 - box[0] // 16 + 1) * (box[3] // 16 - box[1] // 16 + 1)


def build_problems(ddoc, rdoc):
    """[problem] the generator refuses to build over: the settings; the pool; and, for every candidate, the geometry the safety
    properties rest on (disjoint windows, the hold inside the world, the exit point clear of every written cell)."""
    bad = settings_problems(rdoc)
    if bad:
        return bad
    v = values(rdoc)
    cands = pool(ddoc, rdoc)
    if not cands:
        return ["the pool is empty: no rip in data/dungeon_rips.json can open"]
    if v["open_min"] > len(cands):
        bad.append("open_min %d is above the pool (%d candidates)" % (v["open_min"], len(cands)))
    top = overworld_top()
    hy = v["hold_y"]
    wins = []
    for i, r in cands:
        f = r["frame"]
        if hy - 1 <= f["y"] + f["height"]:
            bad.append("%s: the plane reaches y%d, too near the hold at y%d" % (r["id"], f["y"] + f["height"] - 1, hy))
        if hy + f["height"] > top:
            bad.append("%s: the hold's top y%d is above the overworld's top y%d" % (r["id"], hy + f["height"], top))
        if chunk_count(forceload_box(r)) > 4:
            bad.append("%s: its footprint spans %d chunks (a rip is held in at most four)" % (r["id"], chunk_count(forceload_box(r))))
        ox, oy, oz, _yaw = r["outside"]
        cell = (int(ox // 1), int(oy // 1), int(oz // 1))
        for b in D.rip_write_boxes(r):
            if b[0] <= cell[0] <= b[3] and b[1] <= cell[1] <= b[4] and b[2] <= cell[2] <= b[5]:
                bad.append("%s: the exit point %s is inside a cell the scheduler writes %s" % (r["id"], cell, b))
        if not (hy < 2 ** 31):
            bad.append("hold_y out of range")
        wins.append((i, r["id"], window_of(r)))
    for a in range(len(wins)):
        for b in range(a + 1, len(wins)):
            wa, wb = wins[a][2], wins[b][2]
            if wa[0] <= wb[2] and wb[0] <= wa[2] and wa[1] <= wb[3] and wb[1] <= wa[3]:
                bad.append("%s and %s: their 9 x 7 windows overlap, so their holds and their checks would too" % (wins[a][1], wins[b][1]))
    if len(cands) > 400:
        bad.append("%d candidates: the pass walks every candidate several times per pass and the chain limit (%d) is near"
                   % (len(cands), function_limits.CHAIN_LIMIT))
    return bad


# ------------------------------------------------------------------------------------------------ the pass


def ticks(minutes):
    return minutes * 60 * 20


def life_range(v):
    return ticks(v["lifetime_minutes"] - v["lifetime_jitter_minutes"]), ticks(v["lifetime_minutes"] + v["lifetime_jitter_minutes"])


def tellraw(text, colour="light_purple"):
    return "tellraw @a " + json.dumps({"text": text, "color": colour}, ensure_ascii=False)


def functions(ddoc, rdoc):
    """{function name under cobblers:rips/: [lines]}."""
    bad = build_problems(ddoc, rdoc)
    if bad:
        raise SystemExit("rip_scheduler: %d problem(s), nothing built:\n  %s" % (len(bad), "\n  ".join(bad)))
    v = values(rdoc)
    cands = pool(ddoc, rdoc)
    names = region_names()
    S, T, L, V = OBJ["s"], OBJ["t"], OBJ["l"], OBJ["v"]
    pass_ticks = v["pass_seconds"] * 20
    lo, hi = life_range(v)
    grace = v["close_after_entry_seconds"] * 20
    out = {}
    polls = chunk_look.POLLS

    for i, r in cands:
        h = HOLDER % i
        tag = D.rip_tag(r)
        fl = forceload_box(r)
        fls = "%d %d %d %d" % fl
        px, py, pz, sel = check_selector(r)
        guard = "execute in %s positioned %d %d %d if entity %s run return 0" % (OVERWORLD, px, py, pz, sel)
        gate = r.get("reachable_after")
        region = names[r["region"]]
        why = "%s (%s), region %s" % (r["id"], r["name"], r["region"])
        if gate:
            why += "; GATED (reachable_after %s): opens like any other candidate" % gate.get("zone")
        # ---- open -------------------------------------------------------------------------------------------------
        o = [HEAD, "# OPEN rip %d: %s. Runs in the overworld, in ONE tick: checks, forceload, save, write, entities, state, chat, release." % (i, why),
             "# 1 not already open or closing; 2 (one_open_per_region) no other rip of its region open; 3 not a return point; 4 nobody on it"]
        o.append("execute if score %s %s matches 1.. run return 0" % (h, S))
        if v["one_open_per_region"]:
            for j, q in cands:
                if j != i and q["region"] == r["region"]:
                    o.append("execute if score %s %s matches 1.. run return 0" % (HOLDER % j, S))
        o += ["execute if entity @a[scores={%s=%d,%s=1..}] run return 0" % (D.OBJ["rip"], i, D.OBJ["st"]), guard,
              "# the chunks are held from here to the last line, so every write below lands",
              "forceload add %s" % fls,
              "# the save (rip.under) BEFORE any write, then the rip itself: plane cleared to rip.restore, the themed patch",
              "# (tools/dungeon.py rip_open_lines), then the click and the oval (rip_entity_lines)"]
        o += D.rip_open_lines(r, v["hold_y"])
        o += D.rip_entity_lines(ddoc, r)
        o += ["scoreboard players set %s %s 1" % (h, S),
              "execute store result score %s %s run random value %d..%d" % (h, T, lo, hi),
              tellraw(v["announce"].replace("{region}", region_phrase(region))),
              "forceload remove %s" % fls]
        out["o%d" % i] = o
        # ---- close ------------------------------------------------------------------------------------------------
        c = [HEAD, "# CLOSE rip %d: %s. Runs in the overworld in one tick; the entity polls follow in x%d." % (i, why, i),
             "execute unless score %s %s matches 1 run return 0" % (h, S),
             "# a player on the rip: leave it open (the timer stays at 0, so the next pass asks again)",
             guard,
             "forceload add %s" % fls,
             "scoreboard players set %s %s 2" % (h, S),
             "scoreboard players reset %s %s" % (h, T),
             "# the click and the oval out, the ground back from the hold, the hold cleared (tools/dungeon.py rip_close_lines)"]
        c += D.rip_close_lines(r, v["hold_y"])
        c += ["scoreboard players set %s %s %d" % (h, L, polls),
              "schedule function %s %dt replace" % (F("x%d" % i), chunk_look.LOAD_WAIT)]
        out["c%d" % i] = c
        # ---- the kill polls ---------------------------------------------------------------------------------------
        out["x%d" % i] = [HEAD, "# rip %d closing: kill the click and the oval again as the chunk's saved entities arrive (every %dt, %d looks), then done"
                          % (i, chunk_look.POLL_EVERY, polls),
                          "kill @e[tag=%s]" % tag,
                          "scoreboard players remove %s %s 1" % (h, L),
                          "execute if score %s %s matches 1.. run schedule function %s %dt replace" % (h, L, F("x%d" % i), chunk_look.POLL_EVERY),
                          "execute if score %s %s matches ..0 run scoreboard players set %s %s 0" % (h, L, h, S),
                          "execute if score %s %s matches ..0 run forceload remove %s" % (h, L, fls)]

    # ---- the pick: a uniform random candidate -------------------------------------------------------------------
    pick = [HEAD, "# a uniform random candidate among the %d eligible rips; if it cannot open now (open, its region has one, a player is on it) nothing opens this pass" % len(cands),
            "execute store result score #pick %s run random value 1..%d" % (V, len(cands))]
    pick += ["execute if score #pick %s matches %d run function %s" % (V, k, F("o%d" % i)) for k, (i, _r) in enumerate(cands, 1)]
    out["pick"] = pick

    # ---- the near pick (the owner, 2026-10-21: "focus some closer to players, not all though") ---------------------
    # one online overworld player at random; every candidate that is closed, whose region has none open, and whose
    # check point is within near_player_radius of that player (a horizontal square, every height) is flagged #n<i>;
    # a uniform random one of the flagged opens. None flagged: the ordinary pick
    R = v["near_player_radius"]
    top = overworld_top()
    near = [HEAD, "# a candidate near one random player (near_player_radius %d, horizontal); none near: the uniform pick" % R,
            "tag @a remove %s" % TARGET_TAG,
            "execute in %s positioned 0 0 0 run tag @r[distance=0..] add %s" % (OVERWORLD, TARGET_TAG),
            "execute unless entity @a[tag=%s] run return run function %s" % (TARGET_TAG, F("pick")),
            "scoreboard players set #nc %s 0" % V]
    for i, r in cands:
        px, _py, pz, _sel = check_selector(r)
        n = "#n%d" % i
        near.append("scoreboard players set %s %s 0" % (n, V))
        near.append("execute if score %s %s matches 0 in %s if entity @a[tag=%s,x=%d,y=-64,z=%d,dx=%d,dy=%d,dz=%d] run scoreboard players set %s %s 1"
                    % (HOLDER % i, S, OVERWORLD, TARGET_TAG, px - R, pz - R, 2 * R, top + 64, 2 * R, n, V))
        if v["one_open_per_region"]:
            near += ["execute if score %s %s matches 1.. run scoreboard players set %s %s 0" % (HOLDER % j, S, n, V)
                     for j, q in cands if j != i and q["region"] == r["region"]]
        near.append("execute if score %s %s matches 1 run scoreboard players add #nc %s 1" % (n, V, V))
    near += ["tag @a remove %s" % TARGET_TAG,
             "execute if score #nc %s matches 0 run return run function %s" % (V, F("pick")),
             "# random value needs a range of two or more, so one flagged candidate is drawn without it",
             "execute if score #nc %s matches 1 run scoreboard players set #pick %s 1" % (V, V),
             "execute store result storage %s n int 1 run scoreboard players get #nc %s" % (STORE, V),
             "execute if score #nc %s matches 2.. run function %s with storage %s" % (V, F("near_roll"), STORE),
             "function %s" % F("near_open")]
    out["pick_near"] = near
    out["near_roll"] = [HEAD, "# macro: a uniform draw over pick_near's count of flagged candidates",
                        "$execute store result score #pick %s run random value 1..$(n)" % V]
    nopen = [HEAD, "# opens the #pick-th flagged candidate, in candidate order", "scoreboard players set #k %s 0" % V]
    for i, _r in cands:
        nopen += ["execute if score #n%d %s matches 1 run scoreboard players add #k %s 1" % (i, V, V),
                  "execute if score #n%d %s matches 1 if score #k %s = #pick %s in %s run return run function %s"
                  % (i, V, V, V, OVERWORLD, F("o%d" % i))]
    out["near_open"] = nopen
    # which pick an opening uses: near one time in near_player_share, else uniform (0: never near; 1: always)
    share = v["near_player_share"]
    choose = [HEAD, "# an opening: near a player one time in %d (data/rip_scheduler.json near_player_share), else uniform" % share
              if share else "# an opening: near_player_share is 0, so always the uniform pick"]
    if share == 1:
        choose.append("function %s" % F("pick_near"))
    elif share >= 2:
        choose += ["execute store result score #near %s run random value 1..%d" % (V, share),
                   "execute if score #near %s matches 1 run return run function %s" % (V, F("pick_near")),
                   "function %s" % F("pick")]
    else:
        choose.append("function %s" % F("pick"))
    out["choose"] = choose

    # ---- the pass -------------------------------------------------------------------------------------------------
    K = max(1, v["extra_open_every_minutes"] * 60 // v["pass_seconds"])
    p = [HEAD, "# the pass, every %d s of server time. Re-arms itself first so an error below cannot stop the clock." % v["pass_seconds"],
         "schedule function %s %dt replace" % (F("pass"), pass_ticks),
         "execute unless score #on %s matches 1 run return 0" % V,
         "# nobody online: nothing opens, nothing ages (a closing rip's polls are scheduled apart and finish)",
         "execute unless entity @a run return 0"]
    if v["close_when_entered"]:
        p.append("# a run begun by an open rip (dg.rip = its number, dg.st >= 1): its timer is cut to %d tick(s)" % grace)
        p += ["execute if score %s %s matches 1 if score %s %s matches %d.. if entity @a[scores={%s=%d,%s=1..}] run scoreboard players set %s %s %d"
              % (HOLDER % i, S, HOLDER % i, T, grace + 1, D.OBJ["rip"], i, D.OBJ["st"], HOLDER % i, T, grace) for i, _r in cands]
    p.append("# play time: every open rip ages one pass")
    p += ["execute if score %s %s matches 1 run scoreboard players remove %s %s %d" % (HOLDER % i, S, HOLDER % i, T, pass_ticks) for i, _r in cands]
    p.append("# an open rip whose time is up closes (c<i> asks again next pass if a player is on it)")
    p += ["execute if score %s %s matches 1 if score %s %s matches ..0 in %s run function %s" % (HOLDER % i, S, HOLDER % i, T, OVERWORLD, F("c%d" % i))
          for i, _r in cands]
    p.append("# a closed rip's click or oval that arrived late from an unloaded chunk (a ghost) is killed")
    p += ["execute if score %s %s matches 0 run kill @e[tag=%s]" % (HOLDER % i, S, D.rip_tag(r)) for i, r in cands]
    p += ["# the recount", "scoreboard players set #open %s 0" % V]
    p += ["execute if score %s %s matches 1..2 run scoreboard players add #open %s 1" % (HOLDER % i, S, V) for i, _r in cands]
    p += ["# the cap, then the pick",
          "execute if score #open %s >= #max %s run return 0" % (V, V),
          "execute if score #open %s < #min %s run return run function %s" % (V, V, F("choose")),
          "execute store result score #roll %s run random value 1..%d" % (V, K),
          "execute if score #roll %s matches 1 run function %s" % (V, F("choose"))]
    out["pass"] = p

    # ---- init, load, and the operator's three ---------------------------------------------------------------------
    init = [HEAD, "# Arms the scheduler. Idempotent and safe over open rips: it creates objectives, sets the three constants from",
            "# data/rip_scheduler.json, gives a candidate with no state the state 0, resumes a close the server stopped in, and schedules",
            "# the pass. It never opens or closes a rip. Run by minecraft:load and by tools/reapply.py step R16DR.",
            "# Operator: %s (pause), %s (resume), %s (pause and close every open rip)" % (F("stop"), F("start"), F("close_all"))]
    init += ["scoreboard objectives add %s dummy" % o for o in OBJ.values()]
    # #on is set from the data only the first time: a /reload runs init again, and resetting it there un-paused a
    # scheduler an operator had stopped (the independent audit's pause_survives_reload, 2026-10-14). Later changes go
    # through stop/start.
    init += ["execute unless score #on %s matches 0..1 run scoreboard players set #on %s %d" % (V, V, 1 if v["enabled"] else 0),
             "scoreboard players set #min %s %d" % (V, v["open_min"]),
             "scoreboard players set #max %s %d" % (V, v["open_max"])]
    init += ["execute unless score %s %s matches -2147483648..2147483647 run scoreboard players set %s %s 0" % (HOLDER % i, S, HOLDER % i, S) for i, _r in cands]
    init += ["execute if score %s %s matches 2 run schedule function %s %dt replace" % (HOLDER % i, S, F("x%d" % i), chunk_look.POLL_EVERY) for i, _r in cands]
    init.append("schedule function %s %dt replace" % (F("pass"), pass_ticks))
    out["init"] = init
    out["load"] = [HEAD, "# minecraft:load (a boot and every /reload)", "function %s" % F("init")]
    out["start"] = [HEAD, "scoreboard players set #on %s 1" % V]
    out["stop"] = [HEAD, "# no rip opens and none ages or closes by its timer; the open ones stay (close_all closes them)", "scoreboard players set #on %s 0" % V]
    out["close_all"] = [HEAD, "# pause, then close every open rip now (one a player is on stays open: run it again)", "scoreboard players set #on %s 0" % V]
    out["close_all"] += ["execute if score %s %s matches 1 in %s run function %s" % (HOLDER % i, S, OVERWORLD, F("c%d" % i)) for i, _r in cands]
    return out


def pack_files(ddoc, rdoc):
    """{path in the pack: text}."""
    files = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: dungeon rips that open and close at random candidate places (tools/rip_scheduler.py)"}},
                                  indent=2) + "\n",
        "data/minecraft/tags/function/load.json": json.dumps({"values": [F("load")]}, indent=2) + "\n",
    }
    for name, lines in functions(ddoc, rdoc).items():
        rel = "data/%s/function/%s/%s.mcfunction" % (NS, FOLDER, name)
        refused = function_limits.check_lines(lines, rel)
        if refused:
            raise SystemExit("%s: %d command(s) the server would refuse; nothing written\n  %s" % (rel, len(refused), "\n  ".join(str(x) for x in refused[:3])))
        files[rel] = "\n".join(lines) + "\n"
    return files


def measure(files):
    """(files, functions, command lines, bytes) of a built pack."""
    fn = {k: t for k, t in files.items() if k.endswith(".mcfunction")}
    cmds = sum(1 for t in fn.values() for ln in t.splitlines() if ln.strip() and not ln.lstrip().startswith("#"))
    return len(files), len(fn), cmds, sum(len(t.encode("utf-8")) for t in files.values())


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, body in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--measure", action="store_true", help="counts only; write nothing")
    ap.add_argument("--check", action="store_true", help="the fail-closed checks only; write nothing")
    a = ap.parse_args(argv)
    ddoc, rdoc = D.load(), load()
    if a.check:
        bad = build_problems(ddoc, rdoc)
        print("\n".join("PROBLEM " + b for b in bad) + ("\n" if bad else "") + "%d candidate(s), %d problem(s)" % (len(pool(ddoc, rdoc)) if not settings_problems(rdoc) else 0, len(bad)))
        return 1 if bad else 0
    files = pack_files(ddoc, rdoc)
    nf, nfn, cmds, size = measure(files)
    if a.measure:
        print("%s: %d files, %d functions, %d command lines, %d bytes (%d candidate rips)" % (PACK, nf, nfn, cmds, size, len(pool(ddoc, rdoc))))
        return 0
    write(files, a.out)
    print("%s: %d files, %d functions, %d command lines, %d bytes -> %s" % (PACK, nf, nfn, cmds, size, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
