#!/usr/bin/env python
"""The mine crews: trainers seated INSIDE the three long mine networks (the owner, 2026-10-22: "for the economy we are
diving back into the same mistake adding trainers people may never see... i like the mines idea thats good add trainers
there"). So: trainers where players go to mine, none on routes.

  data/mine_crews.json          the AUTHORED table: per network a level band, and per crew member the place it stands
                                (a level and a walk distance from the adit on the main line, or the stope of a level), its
                                skin, its Normal team, its Challenge team, its three lines, and why. Hand-authored.
  data/mine_networks.json       the mines themselves (tools/mine_networks.py): the heightmap decides where a drift is
  data/mine_crew_trainers.json  GENERATED here: each member's record and seat together (the shape of
                                data/compact_route_trainers.json), read by tools/route_trainers.py, which emits the rctmod
                                files, the defeat advancement, the Challenge copy and the cycle lines, and by tools/reapply.py
                                R17 through route_trainers.placements() (R9MN carves the mines before R17 runs)
  data/progression.json         the per-player defeat field quest.<id>.defeated of each member, spliced into quest_fields

THE SEAT is chosen from the networks' own geometry, tools/mine_networks.py's Layout and Model, which are grown from the
canonical heightmap (tools/ground.py, rounded) and never from a world:

  main line   a cell of an adit or main run on the slot's level whose 7 x 7 neighbourhood at floor height holds no air outside
              the run's own three-wide band (a straight tube: no junction, incline, shaft or stope mouth within 3), at least 6
              cells from either end of the run, on a SIDE lane (the rail and its bed run down the middle lane), nearest to
              the slot's walk distance from the adit. It faces toward the adit, the way a player comes in, and sees 7 blocks.
  stope       a free cell of the level's stope with all eight neighbours open (not against a pillar or a wall), nearest the
              slot's depth and lateral offset, facing the stope's entry, seeing 10 blocks.
  both        air at the feet and the head, a floor that is not carved, no fitting (rail, ladder, stair, lantern) in the
              cells, and at least 20 blocks from every other seat.

WHAT THE MONEY IS. Nothing is authored. CobbleDollars pays every NPC win 0.28125 * S^2 on average, S the losing team's level
sum (data/markets.json, docs/mechanics/ECONOMY_V2.md); the Challenge team has the same levels. `python tools/mine_crews.py
purses` prints the sums. These trainers are NOT in tools/income_model.py's progression legs, which is the model the
markets and the economy audit read: a mine crew is optional income beside mining, outside the model on purpose, the way the
Compact's route fighters are.

WHAT THIS DOES NOT COVER (CLAUDE.md "Our list is not the world"). It seats the members its table lists, in the three networks
of data/mine_networks.json. It does not read a world: whether a seat's cells are air in the running game, whether a natural
cave, a donor structure or another mod's block shares the cell, and whether rctmod accepts a summon underground are untested
(the build is replayed from the generated functions by `check`, not from a world). It authors no first-win prize: the
design's Shift Boss prize (docs/mechanics/ECONOMY_V3.md B4, "4 diamonds or a tier TM") needs the once-per-player give B2
describes, which does not exist; the Boss pays money only. Move legality is checked against the Cobblemon 1.8 jar's learnset
when the jar is on this machine (tools/battle_sim.py find_jar) and reported as not checked when it is not.

  python tools/mine_crews.py write     regenerate data/mine_crew_trainers.json and the progression fields
  python tools/mine_crews.py check     the independent seat audit: replays the BUILT functions (build/datapacks/
                                       cobblers_mine_networks), not the generator's geometry. Run `python tools/mine_networks.py
                                       build` first
  python tools/mine_crews.py purses    each crew member's level sum and expected purse
  python tools/mine_crews.py moves <species> <level>   the jar's types and learnset, for authoring a moveset
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "tools"))

TABLE = DATA / "mine_crews.json"
OUT = DATA / "mine_crew_trainers.json"
RULES = ROOT / "docs" / "story" / "TRAINER_RULES.json"
PROGRESSION = DATA / "progression.json"
FIELD_AFTER = "quest.evt_compact_split.completed"
LANE_OFFSETS = (1, -1)       # a main line's SIDE lanes; the middle lane (0) carries the rail
MIN_APART = 20.0
MAIN_SIGHT, STOPE_SIGHT = 7.0, 10.0
TYPES = {"rock", "ground", "steel", "fire"}
MOVE_FREE = {"minecraft:air"}


class CrewError(Exception):
    pass


def jload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def table():
    return jload(TABLE)


def yaw_of(f):
    """Minecraft yaw for a facing (dx, dz): 0 is south (+z), 90 west, 180 north, -90 east."""
    return int(round(math.degrees(math.atan2(-f[0], f[1]))))


def lane_of(tid):
    return LANE_OFFSETS[zlib.crc32(tid.encode()) % len(LANE_OFFSETS)]


# ------------------------------------------------------------------ the seat, from the generator's geometry

class Geometry:
    """One network's Layout and Model (tools/mine_networks.py), built once."""

    def __init__(self, L, m):
        self.L, self.m = L, m

    def open_cell(self, x, y, z):
        return (x, y, z) in self.m.air and (x, y, z) not in self.m.fix

    def standable(self, x, F, z):
        """Air at the feet and head, nothing fitted there, and a floor that was not carved."""
        return (self.open_cell(x, F + 1, z) and self.open_cell(x, F + 2, z)
                and (x, F, z) not in self.m.air)

    def main_candidates(self, k):
        """Every seat a main-line slot on level index k may take: [(dist, (x, y, z), facing, run id, index, lane)]."""
        import mine_networks as MN
        L, m = self.L, self.m
        F = L.levels[k]
        out = []
        for r in L.runs:
            if r["level"] != k or r["kind"] not in MN.MAIN_KINDS:
                continue
            d = r["d"]
            perp = (-d[1], d[0])
            for i in range(6, r["n"] - 5):
                if i == r["root_i"]:
                    continue
                cx, cz = r["x0"] + d[0] * i, r["z0"] + d[1] * i
                # a straight tube: no air at floor height in the 7 x 7 outside this run's band of three
                tube = True
                for a in range(-3, 4):
                    for b in range(-3, 4):
                        if abs(b) > 1:
                            x, z = cx + d[0] * a + perp[0] * b, cz + d[1] * a + perp[1] * b
                            if (x, F + 1, z) in m.air or (x, F, z) in m.air:
                                tube = False
                if not tube:
                    continue
                dist = r["d0"] + abs(i - r["root_i"])
                toward = -1 if i > r["root_i"] else 1
                facing = (toward * d[0], toward * d[1])
                for lane in LANE_OFFSETS:
                    x, z = cx + perp[0] * lane, cz + perp[1] * lane
                    if self.standable(x, F, z):
                        out.append((dist, (x, F + 1, z), facing, r["id"], i, lane))
        return out

    def stope_candidates(self, k):
        """[(f, l, (x, y, z), facing)] for the stope of level index k: cells with all eight neighbours open."""
        L = self.L
        F = L.levels[k]
        out = []
        for st in L.stopes:
            if st["level"] != k:
                continue
            dd, E = st["d"], st["E"]
            ep = (-dd[1], dd[0])
            half = st["width"] // 2
            for f in range(3, st["len"] + 1):
                for l in range(-half, half + 1):
                    x, z = E[0] + dd[0] * f + ep[0] * l, E[1] + dd[1] * f + ep[1] * l
                    # five clear cells toward the entry, so the trainer has something to look down (a pillar in the line of
                    # sight would hide the player until the last step)
                    ahead = all(self.open_cell(x - dd[0] * i, F + 1, z - dd[1] * i) and self.open_cell(x - dd[0] * i, F + 2, z - dd[1] * i)
                                for i in range(1, 6))
                    if ahead and all(self.standable(x + a, F, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1)):
                        out.append((f, l, (x, F + 1, z), (-dd[0], -dd[1]), st["len"], half))
        return out


def geometries():
    import mine_networks as MN
    return {L.net["id"]: Geometry(L, m) for L, m in MN.all_networks()}


def far_enough(seat, taken):
    return all(math.dist(seat, t) >= MIN_APART for t in taken)


def pick_main(geo, slot, taken):
    k = slot["level"] - 1
    want = slot["walk"]
    cands = geo.main_candidates(k)
    cands.sort(key=lambda c: (abs(c[0] - want), c[3], c[4], c[5]))
    lane = lane_of(slot["id"])
    for pref in (lane, -lane):
        for dist, seat, facing, rid, i, ln in cands:
            if ln == pref and abs(dist - want) <= slot.get("tolerance", 60) and far_enough(seat, taken):
                return {"seat": list(seat), "facing": facing, "sight": MAIN_SIGHT, "walk": dist, "run": rid,
                        "index": i, "lane": ln, "where": "main line, level %d, %d blocks from the adit by the drift"
                        % (slot["level"], dist)}
    raise CrewError("%s: no clean main-line cell on level %d within %s of walk %s"
                    % (slot["id"], slot["level"], slot.get("tolerance", 60), want))


def pick_stope(geo, slot, taken):
    k = slot["level"] - 1
    cands = geo.stope_candidates(k)
    if not cands:
        raise CrewError("%s: level %d has no stope with open ground" % (slot["id"], slot["level"]))
    frac, lat = slot.get("depth", 0.5), slot.get("lateral", 3)

    def score(c):
        f, l, _s, _fc, ln, half = c
        return (abs(f - frac * ln) + 0.5 * abs(abs(l) - lat), f, l)
    for c in sorted(cands, key=score):
        if far_enough(c[2], taken):
            f, l, seat, facing, ln, half = c
            return {"seat": list(seat), "facing": facing, "sight": STOPE_SIGHT, "walk": None, "stope": True,
                    "where": "the stope of level %d, %d cells in of %d, %d to one side of its axis"
                    % (slot["level"], f, ln, l)}
    raise CrewError("%s: every open cell of the level %d stope is within %d of another seat" % (slot["id"], slot["level"], MIN_APART))


# ------------------------------------------------------------------ the records

def presets():
    prof = jload(RULES)["ai_profiles"]
    return prof


def rct_of(entry, name, team, preset, ident, battle_format="GEN_9_SINGLES"):
    return {"identity": ident, "name": {"literal": name}, "battleFormat": battle_format,
            "battleRules": {"maxItemUses": 0, "healPlayers": False, "adjustPlayerLevels": False, "adjustNPCLevels": False},
            "ai": {"type": "rct", "data": dict(preset)}, "bag": [], "team": json.loads(json.dumps(team))}


def challenge_team(slot):
    """The Challenge team the table describes: Normal's members at Normal's levels, each with its held item, and the
    table's `extra` member after the last. A translation of data/mine_crews.json challenge_rule, nothing more."""
    items = slot["challenge"]["items"]
    if len(items) != len(slot["normal"]):
        raise CrewError("%s: %d held items for %d Normal members" % (slot["id"], len(items), len(slot["normal"])))
    team = json.loads(json.dumps(slot["normal"]))
    for m, it in zip(team, items):
        m["heldItem"] = it
    if slot["challenge"].get("extra"):
        team.append(json.loads(json.dumps(slot["challenge"]["extra"])))
    return team


def field_of(tid):
    return {"id": "quest.%s.defeated" % tid, "quest_id": tid, "field": "defeated", "type": "boolean", "scope": "player",
            "initial": False,
            "why": "%s, set by its rctmod defeat_count advancement (tools/route_trainers.py); data/mine_crew_trainers.json"
                   % tid}


def build(tb=None, geos=None):
    import challenge_mode as CM
    tb = tb or table()
    geos = geos or geometries()
    ai = presets()
    entries, fields = [], []
    for net in tb["networks"]:
        geo = geos[net["id"]]
        taken = []
        for slot in net["crew"]:
            p = (pick_main if slot["place"] == "main" else pick_stope)(geo, slot, taken)
            taken.append(tuple(p["seat"]))
            tid = slot["id"]
            ident_c = CM.challenge_id(tid)
            ace = max(m["level"] for m in slot["normal"])
            e = {"id": tid, "display_name": slot["name"], "network": net["id"], "role": slot["role"],
                 "seat": p["seat"], "yaw": yaw_of(p["facing"]),
                 "faces": "%s: toward the adit, the way a player comes in" % p["where"] if not p.get("stope")
                 else "%s: toward the stope's entry" % p["where"],
                 "skin": tb["skins"][slot["skin"]], "eye_contact": True, "sight_distance": p["sight"]}
            e["ground"] = {"kind": "mine plan", "floor_y": p["seat"][1] - 1,
                           "source": "tools/mine_networks.py Layout and Model, grown on tools/ground.py (the canonical "
                                     "heightmap, rounded); no world save was read"}
            if not p.get("stope"):
                e["anchor"] = {"run": p["run"], "index": p["index"], "lane": p["lane"], "walk_blocks": p["walk"]}
            e["why"] = slot["why"]
            e["lesson"] = slot["lesson"]
            e["ace_level"] = ace
            e["team"] = json.loads(json.dumps(slot["normal"]))
            e["dialogue_text"] = dict(slot["lines"])
            n_prof, c_prof = slot.get("ai", ["route_normal", "route_challenge"])
            e["rct"] = rct_of(e, slot["name"], slot["normal"], ai[n_prof], tid)
            chal = challenge_team(slot)
            e["modes"] = {
                "normal": {"team": json.loads(json.dumps(slot["normal"])), "ai_profile": n_prof, "rct": e["rct"]},
                "challenge": {"team": chal, "ai_profile": c_prof,
                              "rct": rct_of(e, slot["name"], chal, ai[c_prof], ident_c)}}
            entries.append(e)
            fields.append(field_of(tid))
    doc = {
        "schema": "cobblers.mine-crew-trainers/1",
        "status": "seated %s from the mine networks' geometry; placed in no world yet" % tb["status"][:10],
        "generated_by": "python tools/mine_crews.py write, from data/mine_crews.json (the table owns the teams, lines and slots; "
                        "tools/mine_networks.py's geometry, grown on the heightmap, owns the seat)",
        "consumed_by": "tools/route_trainers.py (the team, the mob, the lines, the defeat advancement, the Challenge copy and "
                       "the cycle) and tools/reapply.py R17 (the summon, after R9MN carves the mines)",
        "design": "docs/world-building/MINE_CREWS.md",
        "ground": "tools/ground.py, the canonical heightmap rounded, through tools/mine_networks.py. No world save was read",
        "not_verified": "that the cells are air in a running game, and anything a donor, a mod or a natural cave put in them; "
                        "that rctmod summons and pins a trainer underground. `python tools/mine_crews.py check` replays the "
                        "built functions, not a world",
        "trainers": entries,
    }
    return doc, fields


def splice_fields(ids, new):
    doc = jload(PROGRESSION)
    lst = [r for r in doc["quest_fields"] if r.get("id") not in ids]
    at = next((i for i, r in enumerate(lst) if r.get("id") == FIELD_AFTER), None)
    if at is None:
        raise CrewError("data/progression.json has no %s to splice after" % FIELD_AFTER)
    doc["quest_fields"] = lst[:at + 1] + new + lst[at + 1:]
    text = dump(doc)
    if text != PROGRESSION.read_text(encoding="utf-8"):
        PROGRESSION.write_text(text, encoding="utf-8", newline="\n")
        return True
    return False


def write():
    doc, fields = build()
    ids = {f["id"] for f in fields}
    text = dump(doc)
    changed = not OUT.is_file() or OUT.read_text(encoding="utf-8") != text
    if changed:
        OUT.write_text(text, encoding="utf-8", newline="\n")
    pc = splice_fields(ids, fields)
    by = {}
    for e in doc["trainers"]:
        by.setdefault(e["network"], []).append(e)
    for n, es in by.items():
        lv = [m["level"] for e in es for m in e["team"]]
        print("%s: %d trainers, levels %d-%d" % (n, len(es), min(lv), max(lv)))
    print("%s %s; progression quest_fields %s" % (OUT.name, "rewritten" if changed else "unchanged",
                                                  "spliced" if pc else "unchanged"))
    return 0


# ------------------------------------------------------------------ the independent seat audit

def jar_species():
    try:
        import battle_sim as B
        species, _mv, _ch = B.load_pack(B.find_jar())
        return species, B.key
    except Exception as exc:       # no jar on this machine: reported by the caller as not checked
        return None, str(exc)


def legal(sp, move, level):
    """The jar's learnset holds the move: level-up at or below `level`, or any tm/egg/tutor/legacy/special entry."""
    for entry in sp.get("moves") or []:
        if ":" not in entry:
            continue
        kind, mv = entry.split(":", 1)
        if mv != move:
            continue
        if kind.isdigit():
            if int(kind) <= level:
                return True
        else:
            return True
    return False


def check(pack=None, doc=None, tb=None):
    """Problems (a list of strings) from the BUILT functions and the data. Imports no geometry from tools/mine_networks.py."""
    import mine_networks_audit as AU
    import challenge_mode as CM
    tb = tb or table()
    doc = doc if doc is not None else jload(OUT)
    pack = Path(pack) if pack else AU.PACK
    problems = []
    by = {}
    for e in doc["trainers"]:
        by.setdefault(e["network"], []).append(e)
    slots = {s["id"]: (n, s) for n in tb["networks"] for s in n["crew"]}
    declared = {f["id"] for f in jload(PROGRESSION)["quest_fields"]}
    skins = set(tb["skins"].values())
    species, key = jar_species()
    seen = {}
    for net in tb["networks"]:
        es = by.get(net["id"], [])
        lo, hi = net["crew_size"]
        if not lo <= len(es) <= hi:
            problems.append("%s: %d trainers, the table asks %d to %d" % (net["id"], len(es), lo, hi))
        if sum(1 for e in es if e["role"] == "shift_boss") != 1:
            problems.append("%s: needs exactly one shift_boss" % net["id"])
        tiles, probs = AU.read_pack(pack, net["id"])
        problems += ["%s: %s" % (net["id"], p) for p in probs]
        if not tiles:
            problems.append("%s: no built functions in %s (run tools/mine_networks.py build)" % (net["id"], pack))
            continue
        state, carved = AU.replay(tiles)

        def air(c):
            return c in carved and AU.base(state.get(c, "minecraft:air")) in MOVE_FREE

        def walk(x, y, z):
            """A cell a player can walk through: open air or a rail, with open air above and a floor that is not carved
            (the bed under a rail is cobblestone)."""
            feet = AU.base(state.get((x, y, z), "minecraft:stone")) if (x, y, z) in carved else "solid"
            head = (x, y + 1, z) in carved and AU.base(state.get((x, y + 1, z), "minecraft:air")) in MOVE_FREE
            fl = AU.base(state.get((x, y - 1, z), "minecraft:stone"))
            return feet in ("minecraft:air", "minecraft:rail") and head and fl not in (
                "minecraft:air", "minecraft:ladder", "minecraft:cobblestone_stairs")

        def stand(x, y, z):
            f = (x, y - 1, z)
            floor_ok = f not in carved or AU.base(state.get(f, "")) == "minecraft:cobblestone"
            return air((x, y, z)) and air((x, y + 1, z)) and floor_ok and AU.base(state.get(f, "minecraft:stone")) not in (
                "minecraft:air", "minecraft:rail", "minecraft:ladder", "minecraft:lantern", "minecraft:cobblestone_stairs")

        deepest = max(s["level"] for _n, s in (slots[e["id"]] for e in es if e["id"] in slots)) if es else 0
        for e in es:
            tid, (x, y, z) = e["id"], e["seat"]
            who = "%s (%s)" % (tid, net["id"])
            if tid in seen:
                problems.append("%s: id seated twice" % who)
            seen[tid] = tuple(e["seat"])
            if not (air((x, y, z)) and air((x, y + 1, z))):
                problems.append("%s: seat (%d,%d,%d) is not open air at the feet and head in the built functions" % ((who, x, y, z)))
                continue
            if not stand(x, y, z):
                problems.append("%s: no floor under, or a fitting at, (%d,%d,%d)" % (who, x, y, z))
            fb = AU.base(state.get((x, y - 1, z), "minecraft:stone"))
            if fb in ("minecraft:rail",):
                problems.append("%s: stands on a rail" % who)
            # facing: the yaw's cardinal direction, and open air for at least 5 cells ahead
            fx, fz = {0: (0, 1), 90: (-1, 0), 180: (0, -1), -180: (0, -1), -90: (1, 0)}.get(e["yaw"], (None, None))
            if fx is None:
                problems.append("%s: yaw %s is not a cardinal direction" % (who, e["yaw"]))
                continue
            ahead = sum(1 for i in range(1, 6) if air((x + fx * i, y, z + fz * i)) and air((x + fx * i, y + 1, z + fz * i)))
            if ahead < 5:
                problems.append("%s: faces a wall: only %d of 5 cells ahead are open" % (who, ahead))
            # one side of a three-wide drift: the line across the facing holds three or more standing cells, and the seat is at
            # an end of that line unless the room is five or more wide; and at least two others stand free
            px, pz = -fz, fx
            run = [0]
            for sgn in (1, -1):
                i = 1
                while walk(x + px * i * sgn, y, z + pz * i * sgn):
                    run.append(i * sgn)
                    i += 1
            width = len(run)
            if width < 3:
                problems.append("%s: only %d walkable cells across the way: the trainer blocks it" % (who, width))
            elif max(run) < 2 and -min(run) < 2:
                problems.append("%s: stands in the MIDDLE of a %d-wide way: no 2-wide passage is left on either side" % (who, width))
            if e["eye_contact"] is not True or not 6.0 <= e["sight_distance"] <= 12.0:
                problems.append("%s: eye contact / sight distance %s" % (who, e["sight_distance"]))
            if e["skin"] not in skins:
                problems.append("%s: skin %s is not one the table names" % (who, e["skin"]))
            if "quest.%s.defeated" % tid not in declared:
                problems.append("%s: quest.%s.defeated is not declared in data/progression.json" % (who, tid))
            slot = slots.get(tid)
            if slot is None:
                problems.append("%s: not in data/mine_crews.json" % who)
                continue
            _n, s = slot
            # levels: inside the network's band, no member over the band's top, the boss at the top
            band = net["band"]
            nt, ct = e["modes"]["normal"]["team"], e["modes"]["challenge"]["team"]
            for m in nt + ct:
                if not band[0] <= m["level"] <= band[1]:
                    problems.append("%s: %s level %d outside the band %s" % (who, m["species"], m["level"], band))
            if len(ct) not in (len(nt), len(nt) + 1):
                problems.append("%s: Challenge team has %d, Normal has %d (must be the same or one more)" % (who, len(ct), len(nt)))
            if [m["level"] for m in ct[:len(nt)]] != [m["level"] for m in nt]:
                problems.append("%s: Challenge levels %s are not Normal's %s" % (who, [m["level"] for m in ct], [m["level"] for m in nt]))
            if max(m["level"] for m in ct) != max(m["level"] for m in nt):
                problems.append("%s: Challenge tops out at %d, Normal at %d" % (who, max(m["level"] for m in ct), max(m["level"] for m in nt)))
            try:
                CM.challenge_rct({"id": tid, "ace_level": e["ace_level"], "modes": e["modes"]})
            except Exception as exc:
                problems.append("%s: %s" % (who, exc))
            if e["role"] == "shift_boss":
                if s["level"] != deepest:
                    problems.append("%s: the Shift Boss is on level %d, the deepest slot is %d" % (who, s["level"], deepest))
                if not e["seat"] or "stope" not in e["faces"]:
                    problems.append("%s: the Shift Boss should stand in the stope" % who)
            if species is not None:
                for m in nt + ct:
                    sp = species.get(key(m["species"]))
                    if sp is None:
                        problems.append("%s: species %s is not in the Cobblemon jar" % (who, m["species"]))
                        continue
                    ty = {t.lower() for t in (sp.get("primaryType"), sp.get("secondaryType")) if t}
                    if not ty & TYPES:
                        problems.append("%s: %s is %s, none of rock/ground/steel/fire" % (who, m["species"], "/".join(sorted(ty))))
                    for mv in m["moveset"]:
                        if not legal(sp, mv, m["level"]):
                            problems.append("%s: %s cannot learn %s at level %d (the jar's learnset)" % (who, m["species"], mv, m["level"]))
    # spacing across everything seated
    ids = sorted(seen)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if math.dist(seen[a], seen[b]) < MIN_APART:
                problems.append("%s and %s are %.1f apart (min %d)" % (a, b, math.dist(seen[a], seen[b]), MIN_APART))
    return problems


def run_check(pack=None):
    species, why = jar_species()
    if species is None:
        print("NOT CHECKED: move legality and species types (%s)" % why)
    problems = check(pack)
    for p in problems[:60]:
        print("PROBLEM:", p)
    d = jload(OUT)
    print("%d trainer(s) checked, %d problem(s)" % (len(d["trainers"]), len(problems)))
    return 1 if problems else 0


def purses():
    d = jload(OUT)
    total = {}
    for e in d["trainers"]:
        s = sum(m["level"] for m in e["team"])
        total.setdefault(e["network"], []).append((e["id"], e["role"], s, 0.28125 * s * s))
    for n, rows in total.items():
        print(n)
        for tid, role, s, p in rows:
            print("  %-34s %-10s S=%3d  expected %6.0f" % (tid, role, s, p))
        print("  all %d: %.0f once per player" % (len(rows), sum(r[3] for r in rows)))
    return 0


def moves(sp_name, level):
    species, key = jar_species()
    if species is None:
        print("no jar:", key)
        return 1
    sp = species.get(key(sp_name))
    if sp is None:
        print("no such species", sp_name)
        return 1
    lv = [e for e in sp["moves"] if e.split(":")[0].isdigit() and int(e.split(":")[0]) <= level]
    other = sorted({e.split(":", 1)[1] for e in sp["moves"] if not e.split(":")[0].isdigit()})
    print(sp_name, sp.get("primaryType"), sp.get("secondaryType"))
    print(" level-up <= %d: %s" % (level, " ".join(e.replace(":", "=") for e in lv)))
    print(" other sources (%d): %s" % (len(other), " ".join(other)))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", choices=["write", "check", "purses", "moves"])
    p.add_argument("args", nargs="*")
    p.add_argument("--pack")
    a = p.parse_args(argv)
    if a.cmd == "write":
        return write()
    if a.cmd == "check":
        return run_check(a.pack)
    if a.cmd == "purses":
        return purses()
    return moves(a.args[0], int(a.args[1]))


if __name__ == "__main__":
    raise SystemExit(main())
