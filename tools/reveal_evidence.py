#!/usr/bin/env python
"""The mainline reveal's physical evidence: one display beside each beat's teller (data/reveal_evidence.json).

Each display is a prop (one or two blocks, stacked) two blocks to one side of the NPC who tells the beat, on the
NPC's own line, and a standing sign one block in front of the prop facing the way the NPC faces. data/quests.json
main_worldshift_reveal physical_evidence says what each must show and that it is corroboration only: nothing reads
it, the conversation carries the beat.

Where it stands comes from the teller's seat (data/npc_seats.json) and nothing else: the seat's facing, snapped to the
nearest cardinal, gives the frame; each column's ground is the seat's own ground kind -- the canonical heightmap
(tools/ground.py, rounded) for a heightmap seat, the plan's paved y on a plaza, the seat's lot level for a lot seat.
Never a world. A column whose heightmap ground is more than one block off the seat's, that lies within MIN_ROUTE of
a walked route line, on a plan street (its half-width + 1) or inside a building footprint (+ 1) is refused, and the
other side is tried; a display with neither side clear stops the build.

Every write is guarded in the function itself: a block is placed only into a replaceable block (air, grass, snow)
over a non-replaceable one, so a build never overwrites a wall, a bench or a lamp that another pack put there first.
A re-run first removes this display's own blocks (each matched by its exact block id at its own position), so a
changed sign text is rewritten and nothing else is touched.

  python tools/reveal_evidence.py plan     print each display's columns, ground and checks; write nothing
  python tools/reveal_evidence.py build    write build/datapacks/cobblers_reveal_evidence

Reapply (tools/reapply.py, not edited here): prepare job `reveal_evidence` runs `build`; step R17NE, after R17N (the
seats), runs placement_steps(): per display, hold its chunk, run cobblers:reveal_evidence/<beat>, release.

What it does NOT cover: whatever town dressing or a template later places on the same column (the guard keeps this
build from overwriting it, but a later build may overwrite this one); and the evidence that is terrain or another
system's (data/reveal_evidence.json not_covered).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

DATA = ROOT / "data" / "reveal_evidence.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_reveal_evidence"
NS = "cobblers"
FN = "reveal_evidence"
PACK_FORMAT = 48  # Minecraft 1.21.1
MIN_ROUTE = 3.0          # tools/npc_seats.py's own: closer than this to a walked line stands in the road
LATERAL = 2              # blocks from the teller to the prop, sideways
SIGN_ROTATION = {"south": 0, "west": 4, "north": 8, "east": 12}
STEP = {"south": (0, 1), "north": (0, -1), "east": (1, 0), "west": (-1, 0)}
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py or plan data.
WORLD_READS: set = set()


class EvidenceError(SystemExit):
    pass


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def facing_of(yaw):
    """The cardinal a Minecraft yaw faces (0 south, 90 west, 180 north, -90 east); a diagonal goes to the z axis."""
    fx, fz = -math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    if abs(fx) > abs(fz) + 1e-9:
        return "east" if fx > 0 else "west"
    return "south" if fz > 0 else "north"


def side_step(facing, side):
    """The unit step to the teller's left or right, looking the way it faces."""
    fx, fz = STEP[facing]
    right = (-fz, fx)
    return right if side == "right" else (-right[0], -right[1])


def sign_state(wood, facing, lines):
    q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])
    return "minecraft:%s_sign[rotation=%d,waterlogged=false]{front_text:{messages:[%s]}}" % (
        wood, SIGN_ROTATION[facing], q)


def _base(state):
    return state.split("[")[0].split("{")[0]


def _seg_dist(px, pz, a, b):
    (ax, az), (bx, bz) = a, b
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz))


def route_distance(x, z, paths=None):
    paths = paths if paths is not None else _json("route_paths.json")["paths"]
    best = float("inf")
    for pts in paths.values():
        for a, b in zip(pts, pts[1:]):
            best = min(best, _seg_dist(x, z, a, b))
        if len(pts) == 1:
            best = min(best, math.hypot(x - pts[0][0], z - pts[0][1]))
    return best


class Site:
    """What one settlement's plan says about a column: street, plaza, footprint."""

    def __init__(self, settlement, placements, footprints):
        st = placements["settlements"].get(settlement or "", {})
        self.plan = st.get("plan") or {}
        self.footprints = footprints

    def street(self, x, z):
        for s in self.plan.get("streets") or []:
            pts = s.get("polyline") or []
            half = (s.get("width") or 0) / 2.0 + 1.0
            for a, b in zip(pts, pts[1:]):
                if _seg_dist(x, z, a, b) <= half:
                    return s.get("id")
        return None

    def plaza(self, x, z):
        pz = self.plan.get("plaza") or {}
        r = pz.get("rect")
        if r and r[0] <= x <= r[2] and r[1] <= z <= r[3]:
            return pz.get("y")
        return None

    def building(self, x, z):
        for pid, (x0, z0, x1, z1) in self.footprints.items():
            if x0 - 1 <= x <= x1 + 1 and z0 - 1 <= z <= z1 + 1:
                return pid
        return None


def footprints_for(settlement, placements):
    if not settlement:
        return {}
    import town_dressing as TD
    return TD.building_footprints(settlement, placements)


def column_ground(seat, site, g, x, z):
    """(y of the ground block, source) for a display column, by the seat's own ground kind."""
    kind, sy = seat["ground"]["kind"], seat["ground"]["y"]
    if kind == "plaza":
        py = site.plaza(x, z)
        if py is not None:
            return py, "plaza"
        return g(x, z), "heightmap"
    if kind == "heightmap":
        py = site.plaza(x, z)
        if py is not None:
            return py, "plaza"
        return g(x, z), "heightmap"
    if kind == "lot_level":
        return sy, "lot_level"
    raise EvidenceError("%s: ground kind %s has no rule here (an indoor seat needs its template's floor)"
                        % (seat["id"], kind))


def plan(doc=None, g=None, placements=None, seats=None, paths=None, footprints=None):
    """[display plan dict] for every display; raises EvidenceError when one cannot stand."""
    doc = doc or load()
    placements = placements or _json("placements.json")
    seats = seats or {s["id"]: s for s in _json("npc_seats.json")["seats"]}
    paths = paths if paths is not None else _json("route_paths.json")["paths"]
    if g is None:
        import ground as G
        g = G.load()
    others = [tuple(s["at"]) for s in seats.values()]
    out = []
    for d in doc["displays"]:
        seat = seats.get(d["teller"])
        if seat is None:
            raise EvidenceError("%s: its teller %s has no seat in data/npc_seats.json" % (d["beat"], d["teller"]))
        sx, sy, sz = seat["at"]
        facing = facing_of(seat["yaw"])
        fp = footprints.get(seat.get("settlement")) if footprints is not None else None
        site = Site(seat.get("settlement"), placements,
                    fp if fp is not None else footprints_for(seat.get("settlement"), placements))
        tried = []
        sides = [d.get("side", "left")] + [s for s in ("left", "right") if s != d.get("side", "left")]
        chosen = None
        for side, layout in [(s, l) for s in sides for l in ("front", "beside")]:
            lx, lz = side_step(facing, side)
            fx, fz = STEP[facing]
            prop = (sx + LATERAL * lx, sz + LATERAL * lz)
            # front: the sign one block in front of the prop; beside: one block further out on the teller's line
            sign = (prop[0] + fx, prop[1] + fz) if layout == "front" else (prop[0] + lx, prop[1] + lz)
            why, cols = [], {}
            for name, (x, z) in (("prop", prop), ("sign", sign)):
                gy, src = column_ground(seat, site, g, x, z)
                cols[name] = (x, gy + 1, z, src)
                if src == "heightmap" and abs(gy - seat["ground"]["y"]) > 1:
                    why.append("%s column (%d, %d) ground y%d is %+d from the teller's y%d"
                               % (name, x, z, gy, gy - seat["ground"]["y"], seat["ground"]["y"]))
                rd = route_distance(x, z, paths)
                if rd < MIN_ROUTE:
                    why.append("%s column (%d, %d) is %.1f from a walked route line" % (name, x, z, rd))
                st = site.street(x, z)
                if st:
                    why.append("%s column (%d, %d) is on street %s" % (name, x, z, st))
                b = site.building(x, z)
                if b:
                    why.append("%s column (%d, %d) is inside %s's footprint + 1" % (name, x, z, b))
                for ox, oy, oz in others:
                    if (ox, oz) == (x, z):
                        why.append("%s column (%d, %d) is an NPC's seat" % (name, x, z))
            if not why:
                chosen = (side, layout, cols)
                break
            tried.append("%s/%s: %s" % (side, layout, "; ".join(why)))
        if chosen is None:
            raise EvidenceError("%s: no side of %s is clear -- %s" % (d["beat"], d["teller"], " | ".join(tried)))
        side, layout, cols = chosen
        prop_states = [s.replace("$facing", facing) for s in d["prop"]]
        if not 1 <= len(prop_states) <= 2:
            raise EvidenceError("%s: a prop is one or two blocks" % d["beat"])
        if len(d["sign"]) > 4 or any(len(l) > 16 for l in d["sign"]):
            raise EvidenceError("%s: a sign has at most 4 lines of 16 characters" % d["beat"])
        out.append({"beat": d["beat"], "evidence": d["evidence"], "teller": d["teller"], "seat": seat["at"],
                    "facing": facing, "side": side, "layout": layout, "tried": tried, "prop_at": cols["prop"][:3],
                    "prop_ground": cols["prop"][3], "sign_at": cols["sign"][:3], "sign_ground": cols["sign"][3],
                    "prop": prop_states, "sign": sign_state(doc.get("sign_wood", "spruce"), facing, d["sign"])})
    return out


def lines_for(p):
    """The display's function: remove its own earlier blocks, then place each block only where the ground allows."""
    (px, py, pz), (sx, sy, sz) = p["prop_at"], p["sign_at"]
    out = ["# Generated by tools/reveal_evidence.py from data/reveal_evidence.json. Re-run to rebuild; do not edit.",
           "# %s: %s beside %s (%s, faces %s)" % (p["beat"], p["evidence"], p["teller"], p["side"], p["facing"]),
           "# chunks-loaded-by: tools/reveal_evidence.py placement_steps (reapply step R17NE holds this display's chunk)",
           "# 1. this display's own earlier blocks: the prop only while this display's sign stands (so a natural block of",
           "#    the same id is never taken), each by its exact id at its own position; then the sign"]
    sign_id = _base(p["sign"])
    for i, st in reversed(list(enumerate(p["prop"]))):
        out.append("execute if block %d %d %d %s if block %d %d %d %s run setblock %d %d %d minecraft:air"
                   % (sx, sy, sz, sign_id, px, py + i, pz, _base(st), px, py + i, pz))
    out.append("execute if block %d %d %d %s run setblock %d %d %d minecraft:air" % (sx, sy, sz, sign_id, sx, sy, sz))
    out.append("# 2. the prop, bottom up, into replaceable blocks over solid ground; then the sign in front of it")
    out.append("execute if block %d %d %d #minecraft:replaceable unless block %d %d %d #minecraft:replaceable run setblock %d %d %d %s"
               % (px, py, pz, px, py - 1, pz, px, py, pz, p["prop"][0]))
    if len(p["prop"]) == 2:
        out.append("execute if block %d %d %d #minecraft:replaceable if block %d %d %d %s run setblock %d %d %d %s"
                   % (px, py + 1, pz, px, py, pz, _base(p["prop"][0]), px, py + 1, pz, p["prop"][1]))
    out.append("execute if block %d %d %d #minecraft:replaceable unless block %d %d %d #minecraft:replaceable run setblock %d %d %d %s"
               % (sx, sy, sz, sx, sy - 1, sz, sx, sy, sz, p["sign"]))
    return out


def files(plans):
    out = {"pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                               "Cobblers: the mainline reveal's evidence displays (tools/reveal_evidence.py)"}},
                                     indent=2) + "\n"}
    for p in plans:
        out["data/%s/function/%s/%s.mcfunction" % (NS, FN, p["beat"])] = "\n".join(lines_for(p)) + "\n"
    return out


def placement_steps(doc=None, g=None, plans=None):
    """For tools/reapply.py, step R17NE after R17N: per display, hold its chunk, build it, release (R9SO's shape)."""
    steps = []
    for p in plans if plans is not None else plan(doc, g):
        x, _y, z = p["prop_at"]
        sx, _sy, sz = p["sign_at"]
        hold = "%d %d %d %d" % (min(x, sx), min(z, sz), max(x, sx), max(z, sz))
        steps += [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/%s" % (NS, FN, p["beat"])),
                  ("cmd", "forceload remove " + hold)]
    return steps


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("plan", "build"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args(argv)
    plans = plan()
    for p in plans:
        print("%-9s %-34s prop %s (%s) sign %s (%s) %s of %s, faces %s%s"
              % (p["beat"], p["evidence"], tuple(p["prop_at"]), p["prop_ground"], tuple(p["sign_at"]), p["sign_ground"],
                 p["side"], p["teller"], p["facing"], (" [refused: %s]" % " | ".join(p["tried"])) if p["tried"] else ""))
    if a.cmd == "build":
        write(files(plans), a.out)
        print("wrote %d displays to %s" % (len(plans), a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
