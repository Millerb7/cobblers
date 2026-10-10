#!/usr/bin/env python
"""A rooms dungeon's walked length and its clock per band, derived from the built rooms and the record's fights.

Unit DG-NS (2026-10-09). The bands' `clock_s` (29-39 minutes, data/dungeons.json engine.bands) were set for the short
spine of DUNGEONS.md 11.1 and its planning table 4.2. A full-length dungeon of rooms carries its own
`clock_s_by_band` ({"1": seconds, ...}); this module is the formula that fills it, and tools/dungeon.py refuses a clock
under it. It reads the room kit's built grids (tools/dungeon_rooms.py), never a world.

THE WALK. Per room, the shortest walk from the cell inside its door in to the cell inside its door out, on the walk
check's own edges (tools/dungeon_grid.py: a step of one block, and in a `jumps` room a jump of up to 3 flat or 2 with
a rise; a jump costs its length). Plus 3 steps through each shared door (the two wall columns and the next room's
first cell). The entry room starts at the arrival (xa + 3), the exit room ends at the far rip (xb - 1). The search is
4-connected, so a diagonal across an open room counts as its Manhattan length: the walk is an UPPER bound on the
straight-line path and about what a player who keeps to the trail walks.

THE CLOCK. required = walk + fights + fixed costs, clock = ceil(required x engine.clock.slack_factor) to the minute
(DUNGEONS.md 4.2, the owner's D14). Every pace is DUNGEONS.md 4.1's PLANNING figure; XT1 (EXP-079) timed no fight
(its owner half is open), so no number here is measured. When XT1 runs, change FIGHT_* and re-derive.

  walk          walked blocks / 4.0 blocks/s (4.1 planning walk); a maze x MAZE_FACTOR (the player does not know the
                way: dead ends), a dark room x DARK_FACTOR
  parkour       its walked blocks / 1.5 blocks/s (4.1), plus FALLS_PER_PIT falls of fall_penalty_s + FALL_REDO_S
  bridge        walked at the walk pace, plus one fall
  a trainer     FIGHT_BASE_S (2.0 min, the owner's small fight, 2 members) + FIGHT_PER_MEMBER_S (0.5 min) per member
                over 2: stands, gauntlets, every boss stage (its team's size for the band), each boss stage gap
  miniboss      one fight of one member (90 s); a nest with a gate: count_by_band wild fights of one member each;
                a nest with clear "pass" and an open habitat cost nothing (optional: the slack pays for them)
  habitat       HABITAT_S (4.2: "the legendary, about 6 minutes") when its gate is `cleared`, else 0 (optional)
  puzzle        PUZZLE_S; resources SEAM_S (the free tier, 4.1); safe room SAFE_S; the run's cues CUES_S (4.1)
  vault         0: optional, and its price is its own clock_cost_s, chosen by the player

CLI: python tools/dungeon_clock.py [dungeon_id] [--rooms]   prints the walked length and the derived clocks.
"""
from __future__ import annotations

import heapq
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_grid as G  # noqa: E402
import dungeon_rooms as R  # noqa: E402

DATA = ROOT / "data" / "dungeons.json"

WALK_BPS = 4.0                # DUNGEONS.md 4.1, planning
PARKOUR_BPS = 1.5             # 4.1, planning
MAZE_FACTOR = 2.0             # planning: a maze is walked about twice its solution (dead ends, turning back)
DARK_FACTOR = 1.5             # planning: a dark room is walked at two thirds of the pace
FALLS_PER_PIT = 2             # 4.1: two falls a run (now per parkour room, a bridge one)
FALL_REDO_S = 10              # planning: the seconds to set off again from the checkpoint (the clock charge is the engine's)
FIGHT_BASE_S = 120            # 4.1: the owner's 2.0 minutes for a small fight of 2 members
FIGHT_PER_MEMBER_S = 30       # 4.1: +0.5 min per further member (a one-member fight is 90 s)
HABITAT_S = 360               # 4.2: the legendary, about 6 minutes
PUZZLE_S = 90                 # planning
SEAM_S = 30                   # 4.1: the free tier, 0.5 min
SAFE_S = 20                   # planning: a click and a heal
CUES_S = 30                   # 4.1: spawns, cues and gates over a run
DOOR_STEPS = 3                # the door's two wall columns and the next room's first cell

TRAINER_KINDS = ("stand", "gauntlet", "ambush")


def fight_s(members):
    return FIGHT_BASE_S + FIGHT_PER_MEMBER_S * (members - 2)


def _first_slot(doc, d):
    return next(s for s in R._slots_for(doc) if s["dungeon"]["id"] == d["id"])


def walk_distance(grid, start, goal, jumps=False, cls=None):
    """Blocks walked from local cell start to local cell goal on the walk check's edges (None when unreachable)."""
    cls = grid.cls() if cls is None else cls
    st, p = G.standable(cls)
    nx, ny, nz = st.shape
    if not (st[start] and st[goal]):
        return None
    dist = {start: 0}
    q = [(0, start)]
    while q:
        dcur, (x, y, z) = heapq.heappop(q)
        if (x, y, z) == goal:
            return dcur
        if dcur > dist.get((x, y, z), 1 << 30):
            continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ax, az = x + dx, z + dz
            if not (0 <= ax < nx and 0 <= az < nz):
                continue
            for dy in (0, 1, -1):
                by = y + dy
                if not (0 < by < ny - 2) or not st[ax, by, az]:
                    continue
                if dy == 1 and not p[x, y + 2, z]:
                    continue
                if dy == -1 and not p[ax, y + 1, az]:
                    continue
                c, nd = (ax, by, az), dcur + 1
                if nd < dist.get(c, 1 << 30):
                    dist[c] = nd
                    heapq.heappush(q, (nd, c))
                break
            if not jumps:
                continue
            for n in range(2, G.JUMP_FLAT_MAX + 1):
                tx, tz = x + dx * n, z + dz * n
                if not (0 <= tx < nx and 0 <= tz < nz):
                    break
                for dy in (0, 1, -1):
                    if dy != 0 and n > G.JUMP_RISE_MAX:
                        continue
                    by = y + dy
                    if not (0 < by < ny - 3) or not st[tx, by, tz]:
                        continue
                    top = max(y, by)
                    clear = all(p[x + dx * k, top + 1, z + dz * k] and p[x + dx * k, top + 2, z + dz * k] for k in range(1, n))
                    if dy == 1:
                        clear = clear and p[x, y + 2, z] and p[x, y + 3, z]
                    if clear:
                        c, nd = (tx, by, tz), dcur + n
                        if nd < dist.get(c, 1 << 30):
                            dist[c] = nd
                            heapq.heappush(q, (nd, c))
    return None


def walked(doc, d):
    """[{id, kind, walk, x_len}] per room and the total: the door-to-door walk measured on the built grids (slot 1)."""
    slot = _first_slot(doc, d)
    out = []
    for b in R.slot_build(doc, d, slot):
        r = b.room
        g = b.grid
        sx = r["xa"] + 3 if r["kind"] == "entry_room" else r["ix0"]
        if r["door_out"]:
            ex, ey, ez = r["ix1"], r["floor_out"], r["z_out"]
        else:
            ex, ey, ez = r["xb"] - 1, r["floor_in"], r["z_in"]
        dist = walk_distance(g, g.local(sx, r["floor_in"], r["z_in"]), g.local(ex, ey, ez), jumps=R.flags_of(r["kind"])["jumps"])
        if dist is None:
            raise R.RoomError("%s room %s: no walk from its door in to its door out (the walk check names why)" % (d["id"], r["id"]))
        out.append({"id": r["id"], "kind": r["kind"], "walk": dist + (DOOR_STEPS if r["door_out"] else 0),
                    "x_len": r["length"], "width": r["width"], "gate": r["gate"], "params": r["params"]})
    return out, sum(x["walk"] for x in out)


def _members(team_by_band, band, doc):
    t = (team_by_band or {}).get(str(band))
    return len(t) if t else int(doc["engine"]["stands"]["members_by_band"][str(band)])


def _trainers(doc, room):
    p = room["params"] or {}
    if isinstance(p.get("trainers"), list):
        return p["trainers"]
    if "pool" in p:
        return doc["engine"]["stands"].get("pools", {}).get(p["pool"], [])
    return [{} for _ in range(int(p.get("trainers", 3)))]     # a bare count (the demo rooms): members by band


def required(doc, d, band, rooms=None):
    """{part: seconds} for one band: what a run without greed, falls beyond the budget or optional rooms takes."""
    rooms = rooms if rooms is not None else walked(doc, d)[0]
    c = doc["engine"]["clock"]
    fall_s = int(c["fall_penalty_s"]) + FALL_REDO_S
    parts = {"walk": 0.0, "parkour": 0.0, "falls": 0.0, "trainers": 0.0, "wild": 0.0, "boss": 0.0, "fixed": float(CUES_S)}
    for r in rooms:
        k, p = r["kind"], r["params"] or {}
        if k == "parkour":
            parts["parkour"] += r["walk"] / PARKOUR_BPS
            parts["falls"] += FALLS_PER_PIT * fall_s
            continue
        f = MAZE_FACTOR if k == "maze" else DARK_FACTOR if k == "dark_room" else 1.0
        parts["walk"] += r["walk"] * f / WALK_BPS
        if k == "collapse_bridge":
            parts["falls"] += fall_s
        elif k in TRAINER_KINDS:
            parts["trainers"] += sum(fight_s(_members(t.get("team_by_band"), band, doc)) for t in _trainers(doc, r))
        elif k == "miniboss":
            parts["wild"] += fight_s(1)
        elif k == "nest" and p.get("clear") != "pass" and r["gate"] == "cleared":
            parts["wild"] += int((p.get("count_by_band") or {}).get(str(band), 0)) * fight_s(1)
        elif k == "habitat" and r["gate"] == "cleared":
            parts["wild"] += HABITAT_S
        elif k == "puzzle":
            parts["fixed"] += PUZZLE_S
        elif k == "resources":
            parts["fixed"] += SEAM_S
        elif k == "safe_room":
            parts["fixed"] += SAFE_S
    boss = d.get("boss") or {}
    stages = (boss.get("teams") or {}).get(str(band))
    if stages:
        parts["boss"] = sum(fight_s(len(s)) for s in stages) + (len(stages) - 1) * int(boss.get("gap_ticks", 0)) / 20.0
    return parts


def derive(doc, d):
    """{"<band>": clock seconds}: ceil(required x slack_factor) to the whole minute, per band."""
    rooms, _total = walked(doc, d)
    slack = float(doc["engine"]["clock"]["slack_factor"])
    out = {}
    for b in doc["engine"]["bands"]:
        req = sum(required(doc, d, b["band"], rooms).values())
        out[str(b["band"])] = int(math.ceil(req * slack / 60.0)) * 60
    return out


def clock_problems(doc, d):
    """A rooms dungeon's clock (its clock_s_by_band, else the band's) must be at least the derived one, per band."""
    bad = []
    try:
        want = derive(doc, d)
    except R.RoomError as e:
        return ["%s: the clock cannot be derived: %s" % (d["id"], e)]
    own = d.get("clock_s_by_band") or {}
    for b in doc["engine"]["bands"]:
        k = str(b["band"])
        have = int(own.get(k, b["clock_s"]))
        if have < want[k]:
            bad.append("%s band %s: clock %d s is under the derived %d s (tools/dungeon_clock.py: the walk and the fights "
                       "x slack_factor)%s" % (d["id"], k, have, want[k], "" if k in own else "; set clock_s_by_band"))
    return bad


def main(argv):
    doc = json.loads(DATA.read_text(encoding="utf-8"))
    ids = [a for a in argv if not a.startswith("--")]
    for d in doc["dungeons"]:
        if not R.has_rooms(d) or (ids and d["id"] not in ids):
            continue
        rooms, total = walked(doc, d)
        print("%s: walked %d blocks door to door (x length %d) over %d rooms" % (d["id"], total, sum(r["x_len"] for r in rooms), len(rooms)))
        if "--rooms" in argv:
            run = 0
            for r in rooms:
                run += r["walk"]
                print("  %-18s %-16s %3d x %2d  walk %4d  at %4d" % (r["id"], r["kind"], r["x_len"], r["width"], r["walk"], run))
        want = derive(doc, d)
        own = d.get("clock_s_by_band") or {}
        for b in doc["engine"]["bands"]:
            parts = required(doc, d, b["band"], rooms)
            print("  band %d: required %.1f min (%s) -> clock %d s (%d min); authored %s"
                  % (b["band"], sum(parts.values()) / 60, ", ".join("%s %.1f" % (k, v / 60) for k, v in parts.items() if v),
                     want[str(b["band"])], want[str(b["band"])] // 60, own.get(str(b["band"]), "none")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
