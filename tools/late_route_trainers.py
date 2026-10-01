#!/usr/bin/env python
"""Routes 4-8: where each of the twenty-eight late route trainers stands (data/late_route_trainers.json).

THE SAME RULE AS ROUTES 1-3, THE SAME CODE. Routes 1-3's thirteen were seated by tools/route_events.py:
Codex's listed point when it is already off the walked line, else `offset` blocks onto the flatter
shoulder, facing the road. That rule is route_events.seat()'s, and this tool reuses route_events' own
Road, frame and yaw_to rather than reimplementing any of it, so a change to the geometry moves both
sets or neither. What this adds is the part routes 1-3 did not need, because their thirteen listed
points happened to land on flat shelves: a seat is only accepted when it is a cell a player can stand
on and fight on, and the search widens (further out along the normal, then a few cells along the
route) until one is.

  the 28        data/trainers.json route_04_* .. route_08_*, class "route" (generated from
                docs/story/TRAINER_RULES.json; never hand-edited). All 28 listed points lie exactly
                ON the walked line (measured: distance 0.0 for every one), so all 28 are shouldered.
  spacing       NOT ours. Each record carries placement.at_distance_blocks, the authored distance
                along the route, and the seat keeps it: the shoulder moves a trainer 3 to 6 blocks
                sideways and at most a few cells along, so the authored progression (route 4: six at
                348/942/1772/2029/2551/3017 of 3,453; route 5: four at 288/448/622/734 of 1,051) is
                what a player walks into. Re-spacing them would be re-authoring TRAINER_RULES.json,
                which is another unit's file.
  ground        tools/ground.py, rounded -- the canonical heightmap. No world save is read to decide
                any position (CLAUDE.md, "Ground comes from the heightmap, never from a world").
                The walked lines (data/route_paths.json) must have been routed on the current
                heightmap or this fails closed: routes 4-8 did not move in the 2026-09-30 re-route,
                so the two agree today.
  standable     flat3 (the 3x3 the trainer and the player stand in) at most 1 block of relief, flat5
                at most 2, and the seat within 2 blocks of the walked line's own ground at that
                point, so the fight happens at eye level with the road and not on a ledge above it.
                Measured against routes 1-3's thirteen, which came out flat3 <= 1 and flat5 <= 2:
                the threshold is the precedent's own result, not a new number.
  off, but seen 2.2 blocks at least from every cell of every walked line (routes 1-3's seats measured
                2.2 to 4.0) and at most 7.0 from its own, so it is off the line a player walks and
                still inside the 8-block reach rctmod's forceBattleOnSight uses. None of these 28
                forces a battle: routes 1-3 force exactly one, the first, as the eye-contact lesson,
                and whether a route's gym_prep trainer should be unavoidable is the owner's design
                call, not this tool's.
  nowhere else  a seat is refused inside a town's ground (tools/town_audit.py town_bounds), a
                placement's footprint + 4 (data/placements.json), a spawn-free zone
                (data/spawn_suppression.json), a Routes 1-3 scene area (data/scenes.json), 16 blocks
                of a ferry dock or its shore column (data/ferry_docks.json), or 8 blocks of another
                placed trainer's seat (routes 1-3, Victory Road's ten, the mansion's five and the
                other 27). Every candidate is checked and --refusals prints why each was rejected.

  OUR LIST IS NOT THE WORLD (CLAUDE.md). What this does NOT exclude: anything in the world that is
  not in data/placements.json, data/scenes.json or data/ferry_docks.json -- a donor template's own
  outbuildings beyond its recorded size, a mod-placed structure, Repurposed Structures' villages, and
  the gym and League trainer spawners that live inside somebody else's template. A seat 3 blocks off
  a walked line is unlikely to land in one, and nothing here proves it did not.

  NOT COVERED EITHER, and it is why the probe list in docs/story/LATE_ROUTE_TRAINER_SEATS.md exists:
  painted water. The heightmap gives land height, and whether a column holds lake or river water is
  in the water-shape pass's own data, not here. Every seat sits level with the dry walked line, which
  is the best this can do offline; the only proof is a block read in the exported world.

  python tools/late_route_trainers.py [--source-root R]            seat them; fail if the committed file disagrees
  python tools/late_route_trainers.py --write [--source-root R]    write data/late_route_trainers.json
  python tools/late_route_trainers.py --refusals                   also print every rejected candidate
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ground as G          # noqa: E402
import route_events as RE   # noqa: E402

OUT = ROOT / "data" / "late_route_trainers.json"
ROUTES = {4: "route_04_surge_to_erika", 5: "route_05_erika_to_koga", 6: "route_06_koga_to_sabrina",
          7: "route_07_sabrina_to_blaine", 8: "route_08_blaine_to_giovanni"}
MIN_OFF_LINE = 2.2      # routes 1-3's seats measured 2.2 to 4.0 blocks from the nearest walked cell
MAX_OFF_LINE = 7.0      # and inside rctmod's 8-block sight reach
FLAT3, FLAT5 = 1, 2     # routes 1-3's seats: relief <= 1 over the 3x3, <= 2 over the 5x5
MAX_STEP = 2            # how far above or below the road's own ground a seat may sit
SEAT_APART = 8          # from any other placed trainer's seat
PLACEMENT_MARGIN = 4
DOCK_MARGIN = 16

# id: (skin, the line it opens with, what it says when the player wins, what it says when the player loses)
# The skins are the ten rctmod single-trainer textures already proven in this pack -- routes 1-3 and
# Victory Road's ten use the same ten names -- picked for the ground each one stands on. No other
# texture name is known to exist without reading the rctmod jar, which is not in this checkout.
VOICE = {
 "route_04_trainer_01": ("hiker_brice_00ba",
    "Snowline starts here. One Pokemon, one lesson: Ice chips through what Erika grows.",
    "Chipped straight through. Keep that thought for the greenhouse.",
    "Cold beats green. Come back when you have something that can land it."),
 "route_04_trainer_02": ("pokemon_ranger_taylor_0335",
    "Ranger's count: two on the ridge. Ice above, wings over. Both at once, or neither.",
    "You covered both. The ridge is yours.",
    "One answer for two angles is no answer. Try again."),
 "route_04_trainer_03": ("camper_jeff_0092",
    "Fire is the only warm thing up here. Erika hates it. Want to see why?",
    "That is the lesson, and you had it already. Mind the embers.",
    "Keep the fire. You will want it in her greenhouse."),
 "route_04_trainer_04": ("engineer_bernie_00de",
    "Three of mine, and the floor is not friendly. Switch carelessly and the hazards bill you.",
    "You switched like someone who counts. Good.",
    "The hazards did half of that. Count before you switch."),
 "route_04_trainer_05": ("aroma_lady_violet_022e",
    "Watch the sky, not me. Flying puts a hole in a garden.",
    "You saw it coming. Most do not.",
    "Look up next time. That is where a garden loses."),
 "route_04_trainer_06": ("scientist_ted_014f",
    "Last stop before Celadon. Her sun makes her faster than she looks. Mine will show you.",
    "Then you are ready for the greenhouse. Go on.",
    "The sun did that, not me. Learn it here, not in her gym."),
 "route_05_trainer_01": ("worker_braden_0460",
    "One Pokemon. Poison is patient, and so am I.",
    "Faster than the poison. Fine.",
    "Patience wins. Ask the one lying down."),
 "route_05_trainer_02": ("fisherman_andrew_00e9",
    "Field medic. I keep mine standing, and you will hate how long that takes.",
    "You closed it before I could heal through. That is the trick.",
    "Status and recovery. That is the whole fight on this road."),
 "route_05_trainer_03": ("aroma_lady_violet_022e",
    "Koga's poison has one clean answer, and it is in your head. Psychic. Show me.",
    "Clean. Carry it into the dojo.",
    "The answer was Psychic. Now you know, and you lost anyway."),
 "route_05_trainer_04": ("pokemon_ranger_jeffrey_0336",
    "Warden of this trail. Do not come at Koga with one Ground move: Levitate laughs at it.",
    "Mixed answers, mixed typings. You listened.",
    "One button is not a plan. Levitate just proved it."),
 "route_06_trainer_01": ("camper_liam_008e",
    "The marsh is quiet. Dark is quieter. Sabrina will like neither.",
    "Quiet and quick. Go.",
    "Dark undoes Psychic. Remember that in Saffron."),
 "route_06_trainer_02": ("pokemon_ranger_taylor_0335",
    "Two of mine: one shrugs off Psychic, one swallows it. Find the angle.",
    "Found it. Most swing and hope.",
    "A resistance is a wall, not a bluff. Bring a key."),
 "route_06_trainer_03": ("camper_jeff_0092",
    "Night courier. I hit first and I hit dark. Keep up.",
    "You were faster. Take the road.",
    "Priority is not a trick, it is a schedule. Mine."),
 "route_06_trainer_04": ("scientist_ted_014f",
    "Let me invert your afternoon. Slow is fast in here.",
    "You read the room backwards and still won. Good.",
    "Trick Room. Your speed was your problem, not your answer."),
 "route_06_trainer_05": ("engineer_bernie_00de",
    "Archivist, displaced, like everything else on this shore. Her team has this shape. Rehearse.",
    "That is her shape, and you beat it here. Saffron next.",
    "Psychic and Fairy together. Go and build an answer."),
 "route_07_trainer_01": ("fisherman_andrew_00e9",
    "One Water attacker. Blaine is a long way off and already losing.",
    "Water wins there. You knew.",
    "Water. Just water. Bring one."),
 "route_07_trainer_02": ("worker_braden_0460",
    "Bridge hand. Water and Ground, paired, because the ash gets into everything.",
    "Paired answers. The bridge is clear.",
    "Two pressures, one at a time. That is how you lose slowly."),
 "route_07_trainer_03": ("camper_liam_008e",
    "Fast Water. Not clever Water. See if clever helps you.",
    "Clever helped. Noted.",
    "Speed is a type all its own."),
 "route_07_trainer_04": ("hiker_nob_00b7",
    "Geologist. The crater is rock, and so is the thing Blaine closes with.",
    "Rock pressure, handled. He will not surprise you.",
    "Rock hurts the one with wings. Work it out before Cinnabar."),
 "route_07_trainer_05": ("pokemon_ranger_jeffrey_0336",
    "Ash-path ranger. One Water answer and a sunny sky, and your plan is ash.",
    "You brought more than one answer. Good.",
    "Sun burns off a single answer. Bring two."),
 "route_07_trainer_06": ("hiker_brice_00ba",
    "Prospector, and the last of this road. Weather, then priority, the way he finishes you.",
    "Then Cinnabar is only a boat ride.",
    "That is his closing turn. You have just seen it for free."),
 "route_08_trainer_01": ("hiker_nob_00b7",
    "Last leg. One Ground attacker, and the ground belongs to him.",
    "Through me, then. Mind the crater.",
    "Ground is the whole road ahead. Start there."),
 "route_08_trainer_02": ("camper_jeff_0092",
    "Scout. The terrain changes twice between here and his floor. One type will not do.",
    "You are carrying answers, not a favourite. Good.",
    "A monotype dies out here, slowly."),
 "route_08_trainer_03": ("aroma_lady_violet_022e",
    "Grass, out here. It answers rock and it answers ground, and nobody expects it.",
    "You expected it. Fine.",
    "Grass. Against stone. Think about it."),
 "route_08_trainer_04": ("worker_braden_0460",
    "Sand runner. Weather, immunity, position. Three things, and you are standing in all of them.",
    "Position taken. You move well.",
    "You stood still. Out here that is a decision."),
 "route_08_trainer_05": ("pokemon_ranger_taylor_0335",
    "Plateau ranger. Fighting and Dark, both, because he carries both answers to you.",
    "Broad enough. Go on up.",
    "Narrow beats nothing. Widen it."),
 "route_08_trainer_06": ("scientist_ted_014f",
    "Surveying the Rift, while it surveys me. Tailwind, split offence. Keep your footing.",
    "You kept it. Few do, this close.",
    "Tailwind took your turn order and then your fight."),
 "route_08_trainer_07": ("engineer_bernie_00de",
    "Final warden. Three, balanced, no gimmick. If this stops you, he will.",
    "Nothing stops you here. The last gym is yours to lose.",
    "A balanced three stopped you. Prepare; do not hurry."),
}
COMPASS = [(0, "south"), (45, "south-east"), (90, "west"), (135, "north-west"), (180, "north"),
           (-135, "north-east"), (-90, "east"), (-45, "south-west")]


def doc(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def facing(yaw):
    """The compass word for a yaw, for the report: 0 south, 90 west, 180 north, -90 east."""
    return min(COMPASS, key=lambda c: abs((yaw - c[0] + 180) % 360 - 180))[1]


def heightmap_guard():
    """The walked lines must have been routed on the heightmap these seats stand on."""
    world = doc("world.json")
    have = doc("route_paths.json")["heightmap_sha256"]
    if have != world["heightmap"]["sha256"]:
        raise SystemExit("data/route_paths.json was routed on heightmap %s, not the current %s: route again "
                         "(tools/build_routes.py) or widen tools/route_events.py check_paths_heightmap over "
                         "routes 4-8 before seating here" % (have[:8], world["heightmap"]["sha256"][:8]))
    return "routed on the current heightmap (%s)" % have[:8]


def exclusions():
    """[(why, (x0, z0, x1, z1))]: every rectangle a seat may not fall in."""
    import placement_ground_audit as PGA
    import town_audit
    import reapply
    pl = doc("placements.json")
    out = []
    for sid in ["hometown"] + reapply.places(pl):
        out.append(("town %s" % sid, tuple(town_audit.town_bounds(sid, pl))))
    m = PLACEMENT_MARGIN
    for p in pl["placements"]:
        if not p.get("position"):
            continue
        x0, z0, x1, z1 = PGA.footprint(p)
        out.append(("placement %s" % p["id"], (x0 - m, z0 - m, x1 + m, z1 + m)))
    for z in doc("spawn_suppression.json")["spawn_free_zones"]:
        out.append(("spawn-free zone %s" % z["id"], tuple(z["box"])))
    for s in doc("scenes.json")["scenes"]:
        a = s.get("area")
        if a:
            out.append(("scene %s" % s["id"], (a["from"][0], a["from"][2], a["to"][0], a["to"][2])))
    for d in doc("ferry_docks.json")["docks"]:
        for tag, pt in (("", d.get("near")), (" shore", (d.get("shore") or {}).get("at"))):
            if pt:
                out.append(("ferry dock %s%s" % (d["id"], tag),
                            (pt[0] - DOCK_MARGIN, pt[1] - DOCK_MARGIN, pt[0] + DOCK_MARGIN, pt[1] + DOCK_MARGIN)))
    return out


def other_seats():
    """[(id, x, z)] of every trainer already seated: routes 1-3, Victory Road's ten, the mansion's five."""
    out = []
    for f in ("route_trainers.json", "vr_trainers.json", "mansion_guardians.json"):
        for t in doc(f)["trainers"]:
            s = t.get("seat")
            if s:
                out.append((t["id"], s[0], s[2]))
    return out


class Judge:
    """Whether a cell can be stood on and fought on, measured on the heightmap alone."""

    def __init__(self, g, road, excl, taken):
        self.g, self.road, self.excl, self.taken = g, road, excl, taken

    def relief(self, x, z, r):
        h = [self.g(x + dx, z + dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1)]
        return max(h) - min(h)

    def off_line(self, x, z):
        """Distance to the nearest cell of ANY walked line (a shoulder can be another route's road)."""
        best = 1e9
        for cells in self.road.paths.values():
            for px, pz in cells:
                if abs(px - x) <= 8 and abs(pz - z) <= 8:
                    best = min(best, math.hypot(px - x, pz - z))
        return best

    def refuse(self, x, z, route, road_y):
        """Why this cell cannot be a seat, or None."""
        d_own = min(math.hypot(px - x, pz - z) for px, pz in self.road.paths[route])
        if d_own > MAX_OFF_LINE:
            return "%.1f blocks from its own walked line, out of sight" % d_own
        d = self.off_line(x, z)
        if d < MIN_OFF_LINE:
            return "%.1f blocks from a walked line: on the road" % d
        f3, f5 = self.relief(x, z, 1), self.relief(x, z, 2)
        if f3 > FLAT3:
            return "ground relief %d over the 3x3 it stands in" % f3
        if f5 > FLAT5:
            return "ground relief %d over the 5x5 around it" % f5
        step = self.g(x, z) - road_y
        if abs(step) > MAX_STEP:
            return "%d blocks %s the road" % (abs(step), "above" if step > 0 else "below")
        for why, (x0, z0, x1, z1) in self.excl:
            if x0 <= x <= x1 and z0 <= z <= z1:
                return "inside %s" % why
        for tid, tx, tz in self.taken:
            if math.hypot(tx - x, tz - z) < SEAT_APART:
                return "%.1f blocks from %s's seat" % (math.hypot(tx - x, tz - z), tid)
        return None


# How far along the route the search may step, in path cells, NEAREST FIRST: the shoulder at the authored
# cell is always tried before anywhere else, so a standable shoulder there is always the answer, and the
# search only walks away from the authored point when every shoulder nearer it was refused. The reach is
# 120 cells because one trainer needs most of it: route_07_trainer_01's authored point is 170 blocks along
# route 7 and Saffron's recorded ground (tools/town_audit.py town_bounds, a bounding box) reaches 253.
ALONG = (0,) + tuple(s * k for k in range(2, 122, 2) for s in (1, -1))


def seats(g, road):
    """([seat], [refused candidate], [id that could not be seated])."""
    recs = [r for r in doc("trainers.json")["trainers"] if r["id"] in VOICE]
    if len(recs) != len(VOICE):
        raise SystemExit("data/trainers.json holds %d of the %d route 4-8 trainers this tool seats"
                         % (len(recs), len(VOICE)))
    excl, taken = exclusions(), other_seats()
    judge = Judge(g, road, excl, taken)
    out, refused, unseated = [], [], []
    for r in recs:
        route = ROUTES[int(r["id"][6:8])]
        p = r["placement"]
        lx, lz = p["x"], p["z"]
        i0, d_listed, _w = road.nearest(route, lx, lz)
        best = None
        for along in ALONG:
            i = max(0, min(len(road.paths[route]) - 1, i0 + along))
            px, pz = road.paths[route][i]
            _tan, (nx, nz) = road.frame(route, i)
            road_y = g(px, pz)
            for off in (3, 4, 5, 6):
                cands = []
                for s in (1, -1):
                    cx, cz = int(round(px + s * nx * off)), int(round(pz + s * nz * off))
                    cands.append((abs(g(cx, cz) - road_y), cx, cz, s))
                cands.sort()                                 # the flatter shoulder first, as routes 1-3 do
                for _score, cx, cz, s in cands:
                    why = judge.refuse(cx, cz, route, road_y)
                    if why:
                        refused.append((r["id"], (cx, cz), off, along, why))
                        continue
                    cost = (off - 3) * 4 + abs(along) + judge.relief(cx, cz, 1) * 2
                    if best is None or cost < best[0]:
                        best = (cost, cx, cz, off, along, s, px, pz, road_y)
                if best is not None:
                    break
            if best is not None:
                break
        if best is None:
            unseated.append(r["id"])
            continue
        _cost, sx, sz, off, along, side, px, pz, road_y = best
        _i, _d, walked = road.nearest(route, sx, sz)
        yaw = RE.yaw_to(px - sx, pz - sz)
        skin, pre, win, loss = VOICE[r["id"]]
        taken.append((r["id"], sx, sz))
        out.append({
            "id": r["id"], "name": r["display_name"], "route": route, "trainer_order": r["trainer_order"],
            "listed": [lx, lz], "seat": [sx, g(sx, sz) + 1, sz], "yaw": yaw,
            "faces": "the walked line, looking %s" % facing(yaw),
            "listed_off_walked_line": round(d_listed, 1),
            "walked_distance": round(walked, 1), "authored_distance": p["at_distance_blocks"],
            "moved_blocks": round(math.hypot(sx - lx, sz - lz), 1),
            "shoulder": {"offset": off, "along_path_cells": along, "side": "right" if side > 0 else "left",
                         "road_ground": road_y, "seat_ground": g(sx, sz),
                         "relief_3x3": judge.relief(sx, sz, 1), "relief_5x5": judge.relief(sx, sz, 2),
                         "off_any_walked_line": round(judge.off_line(sx, sz), 1)},
            "skin": "rctmod:textures/trainers/single/%s.png" % skin,
            "eye_contact": False,
            "lesson": r["lesson"],
            "dialogue_text": {"pre": pre, "player_win": win, "player_loss": loss},
            "why": "the authored point is on the walked line; %d blocks onto the %s shoulder, %s"
                   % (off, "right" if side > 0 else "left",
                      "at the authored cell" if along == 0
                      else "%d cells %s along the route" % (abs(along), "on" if along > 0 else "back")),
        })
    return out, refused, unseated


def document(ss):
    seen = {}
    for s in ss:
        prev = seen.get(s["route"])
        s["gap_from_previous_blocks"] = round(s["walked_distance"] - prev, 1) if prev is not None \
            else round(s["walked_distance"], 1)
        seen[s["route"]] = s["walked_distance"]
    return {
        "schema": "cobblers.route-trainers/1",
        "status": "seated 2026-09-30 from the heightmap and the walked lines; placed in no world yet",
        "generated_by": "tools/late_route_trainers.py --write",
        "consumed_by": "tools/route_trainers.py (the rctmod data and the cycle) and its placements(), which "
                       "tools/reapply.py R17 summons each seat from over RCON",
        "rule": "tools/route_events.py's seating rule, reusing its Road, frame and yaw_to: the authored point when "
                "it is already off the walked line, else onto the flatter shoulder facing the road. All 28 authored "
                "points lie exactly on the walked line, so all 28 are shouldered. A seat must also be standable: "
                "relief at most 1 over its 3x3 and 2 over its 5x5 (which is what routes 1-3's thirteen measured), "
                "within 2 blocks of the road's own ground, 2.2 to 7.0 blocks off every walked line, and outside "
                "every town, placement footprint, spawn-free zone, scene area, ferry dock and other trainer's seat.",
        "spacing_rule": "Not ours. The distance along each route is data/trainers.json placement.at_distance_blocks, "
                        "authored from docs/story/TRAINER_RULES.json; the shoulder moves a trainer sideways, and "
                        "along the route only where the authored cell has no standable shoulder. Route 4 spaces six "
                        "over 3,453 blocks (one about every 500); route 5 four over 1,051 (one every 160 to 290). "
                        "Re-spacing them would be re-authoring TRAINER_RULES.json, which is another unit's file.",
        "ground": "tools/ground.py, the canonical heightmap rounded. No world save was read to decide any position "
                  "(CLAUDE.md, 'Ground comes from the heightmap, never from a world').",
        "not_verified": "Painted lake and river water is not testable offline from the heightmap, and no world was "
                        "read: whether a seat's feet are dry, and whether anything a donor template or a mod put "
                        "there is already standing in the cell, is a block read in the exported world. The probe "
                        "list in docs/story/LATE_ROUTE_TRAINER_SEATS.md is what settles it.",
        "eye_contact": "None of the 28 forces a battle on sight. Routes 1-3 force exactly one (the first, as the "
                       "eye-contact lesson) and Victory Road's ten all do; whether each route's gym_prep trainer "
                       "should be unavoidable is a design call for the owner, not this tool's to take.",
        "fields_needed": "Each of the 28 sets quest.<id>.defeated, and tools/route_trainers.py refuses to emit a "
                         "trainer whose fields are not declared in data/progression.json quest_fields. None of the "
                         "28 are declared there (2026-09-30); the list is in docs/story/LATE_ROUTE_TRAINER_SEATS.md.",
        "trainers": ss,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=None)
    p.add_argument("--write", action="store_true")
    p.add_argument("--refusals", action="store_true", help="print why each rejected candidate was rejected")
    a = p.parse_args(argv)
    print("walked lines:", heightmap_guard())
    g = G.Ground(a.source_root)
    road = RE.Road()
    ss, refused, unseated = seats(g, road)
    d = document(ss)
    if a.refusals:
        for tid, c, off, along, why in refused:
            print("  refused %-22s %-14s off %d along %+d: %s" % (tid, c, off, along, why))
    for s in ss:
        print("  %-22s seat %-20s yaw %4d  moved %4.1f  gap %6.1f  off %d along %+d  relief %d/%d  faces %s"
              % (s["id"], s["seat"], s["yaw"], s["moved_blocks"], s["gap_from_previous_blocks"],
                 s["shoulder"]["offset"], s["shoulder"]["along_path_cells"], s["shoulder"]["relief_3x3"],
                 s["shoulder"]["relief_5x5"], facing(s["yaw"])))
    text = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
    if a.write:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print("wrote %d seats to %s" % (len(ss), OUT))
    elif OUT.is_file():
        if json.loads(OUT.read_text(encoding="utf-8"))["trainers"] != ss:
            raise SystemExit("DRIFT: %s disagrees with the seats computed now (run --write)" % OUT)
        print("%s agrees with the seats computed now" % OUT)
    else:
        print("%s does not exist yet (run --write)" % OUT)
    if unseated:
        raise SystemExit("%d of the 28 could not be seated: %s" % (len(unseated), ", ".join(unseated)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
