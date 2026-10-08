#!/usr/bin/env python
"""How far apart the League's one-leader spawners must stand, measured on the kanto_league template as placed.

The one-leader swap (tools/challenge_mode.py single_lines) gives a boss the mode of the nearest player within REACH
of its spawner (rctmod's forceBattleMaxDistance + 1, challenge_mode.reach()), measured in 3-D from
(x + .5, y, z + .5). The League stacks its storeys about ten blocks apart, so a spawner can reach through a ceiling.
The owner's decision of 2026-10-09: keep the reach, move a spawner.

THE RULE, for two bosses A and B: no standable cell of A's floor whose player can be within REACH of A's spawner
can also be within REACH of B's, and the same with A and B exchanged. Then a player standing where the swap reads
them for their own boss is never read for the other one.

  standable  a block that is not passable with two passable cells over it (passable: air, light, signs, plates,
             torches, candles, carpets, buttons, levers, rails, banners, plants, vines, ladders, end rods, wire)
  floor      the standable cells joined to the boss's own spawner cell by four-way steps of up one or down up to
             three, within FLOOR_BAND of the spawner's y (the storeys are ten apart, so no floor reaches another)
  a player   feet anywhere over the cell: x and z across it, y from cell + 0.5 (a slab) to cell + 2.25 (a jump);
             a cell is within REACH of a spawner when the NEAREST such point is, on both sides of the rule, so the
             rule is judged against the most generous reading of each reach

Positions come from the template (COBBLEVERSE-DP-v31.zip, read with tools/gym_trainers.py template_cells, never
copied) placed through data/placements.json league_building with tools/gym_interiors.py to_world; a structure void
is the levelled lot (stone to the lot's level, air above). Never from a world. A boss with
data/challenge_mode.json bosses.<id>.single_leader.move stands at move.to; every other at its template spawner.

  python tools/league_separation.py                 every pair as the data stands; exit 1 if a moved boss
                                                    still shares a cell with any other League boss
  python tools/league_separation.py --template      every pair at the template's own spawners
  python tools/league_separation.py --candidates kanto_league_lance
                                                    the cells that boss's spawner could move to, nearest first:
                                                    its own floor, its spawner's height, a full block (no slab,
                                                    light or block entity) with air over it, clear of every other
                                                    League boss
  python tools/league_separation.py --margin kanto_league_lance 3676,148,2445
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

SPAWNER = "rctmod:trainer_spawner"
TEMPLATE = "cobbleverse:kanto_league"
PLACEMENT = "league_building"
FLOOR_BAND = 4
FEET_LOW, FEET_HIGH = 0.5, 2.25
PASSABLE = ("sign", "pressure_plate", "torch", "candle", "carpet", "button", "lever", "rail", "banner", "flower",
            "grass", "fern", "vine", "ladder", "end_rod", "redstone_wire", "tulip", "poppy", "dandelion")
NOT_A_FLOOR_FOR_A_SPAWNER = ("slab", "stairs", "froglight", "lantern", "glass", "barrel", "chest", "shulker",
                             "bookshelf", "sophisticatedstorage")


def bname(state):
    return (state or "minecraft:air").split("[", 1)[0].split("{", 1)[0]


class League:
    def __init__(self):
        import gym_interiors as GI
        import gym_trainers as GT
        zp = GT.donor_zip()
        if not zp:
            raise SystemExit("the kanto_league template is not here: set COBBLERS_DONOR_ZIP to COBBLEVERSE-DP-v31.zip")
        cells, _size = GT.template_cells(zp, TEMPLATE)
        pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
        rec = [p for p in pl["placements"] if isinstance(p, dict) and p.get("id") == PLACEMENT][0]
        if rec.get("mirror", "none") != "none":
            raise SystemExit("%s is mirrored: not modelled" % PLACEMENT)
        self.level = None
        for a in ((pl.get("settlements") or {}).get(rec.get("settlement")) or {}).get("plan", {}).get("anchors") or []:
            if a.get("id") == rec.get("lot", PLACEMENT):
                self.level = a.get("level")
        if self.level is None:
            raise SystemExit("no lot level for %s: a structure void cannot be resolved" % PLACEMENT)
        self.cells = {GI.to_world(rec, c): s for c, s in cells.items()}
        # template_cells keeps block states only; a spawner's TrainerIds is its block entity's NBT
        import zipfile
        import nbt
        ns, path = TEMPLATE.split(":", 1)
        with zipfile.ZipFile(zp) as z:
            _n, root = nbt.loads(z.read("data/%s/structure/%s.nbt" % (ns, path)))
        self.spawners = {}
        for b in root["blocks"]:
            if root["palette"][b["state"]]["Name"] == SPAWNER:
                for i in (b.get("nbt") or {}).get("TrainerIds") or []:
                    self.spawners[i] = GI.to_world(rec, tuple(b["pos"]))
        self._floors = {}

    def name(self, c):
        s = self.cells.get(c)
        if s is None:
            return "minecraft:stone" if c[1] <= self.level else "minecraft:air"
        return bname(s)

    def passable(self, c):
        n = self.name(c).split(":", 1)[-1]
        return n in ("air", "cave_air", "light") or any(p in n for p in PASSABLE)

    def standable(self, c):
        x, y, z = c
        return not self.passable(c) and self.passable((x, y + 1, z)) and self.passable((x, y + 2, z))

    def floor(self, boss):
        if boss not in self._floors:
            sp = self.spawners[boss]
            seen, q = {sp}, deque([sp])
            while q:
                x, y, z = q.popleft()
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    for ny in range(y + 1, y - 4, -1):
                        c = (x + dx, ny, z + dz)
                        if abs(ny - sp[1]) <= FLOOR_BAND and c not in seen and self.standable(c):
                            seen.add(c)
                            q.append(c)
                            break
            self._floors[boss] = seen
        return self._floors[boss]


def nearest(cell, spawner):
    """The least distance from the swap's point over `spawner` to a player's feet over `cell`."""
    x, y, z = cell
    px, py, pz = spawner[0] + 0.5, spawner[1], spawner[2] + 0.5
    cx, cy, cz = min(max(px, x), x + 1), min(max(py, y + FEET_LOW), y + FEET_HIGH), min(max(pz, z), z + 1)
    return ((px - cx) ** 2 + (py - cy) ** 2 + (pz - cz) ** 2) ** 0.5


def shared(L, a, sa, b, sb, reach):
    """Cells of a's floor within reach of a's spawner `sa` and of b's `sb`."""
    return [k for k in L.floor(a) if nearest(k, sa) <= reach and nearest(k, sb) <= reach]


def margins(L, a, sa, b, sb, reach):
    """(the nearest a-floor cell in a's reach to sb, the nearest b-floor cell in b's reach to sa): both must exceed
    reach."""
    ma = min(nearest(k, sb) for k in L.floor(a) if nearest(k, sa) <= reach)
    mb = min(nearest(k, sa) for k in L.floor(b) if nearest(k, sb) <= reach)
    return ma, mb


def seats(L, template=False):
    """{boss: spawner cell as it will stand}: move.to where the data moves it, else the template's."""
    import challenge_mode as CM
    bosses = CM.doc()["bosses"]
    out = dict(L.spawners)
    if not template:
        for b in out:
            mv = ((bosses.get(b) or {}).get("single_leader") or {}).get("move")
            if mv:
                if tuple(mv["from"]) != L.spawners[b]:
                    raise SystemExit("%s: move.from %s is not the template's spawner %s" % (b, mv["from"], L.spawners[b]))
                out[b] = tuple(mv["to"])
    return out


def pairs(L, at, reach):
    out = []
    names = sorted(at)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            n = len(shared(L, a, at[a], b, at[b], reach)) + len(shared(L, b, at[b], a, at[a], reach))
            out.append((a, b, n))
    return out


def candidates(L, boss, reach):
    s0 = L.spawners[boss]
    at = seats(L, template=True)
    others = [o for o in at if o != boss]
    out = []
    for k in L.floor(boss):
        x, y, z = k
        n = L.name(k)
        if y != s0[1] or any(w in n for w in NOT_A_FLOOR_FOR_A_SPAWNER) or n == "minecraft:air":
            continue
        if L.name((x, y + 1, z)) != "minecraft:air" or L.name((x, y + 2, z)) != "minecraft:air":
            continue
        if any(shared(L, boss, k, o, at[o], reach) or shared(L, o, at[o], boss, k, reach) for o in others):
            continue
        d = sum((p - q) ** 2 for p, q in zip(k, s0)) ** 0.5
        out.append((round(d, 1), k, n, L.name((x, y - 1, z))))
    return sorted(out)


def main(argv=None):
    import challenge_mode as CM
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--template", action="store_true", help="judge the template's own spawners")
    p.add_argument("--candidates", metavar="BOSS")
    p.add_argument("--margin", nargs=2, metavar=("BOSS", "X,Y,Z"))
    a = p.parse_args(argv)
    L, reach = League(), CM.reach()
    if a.candidates:
        for c in candidates(L, a.candidates, reach)[:20]:
            print("  %.1f %s %s over %s" % c)
        return 0
    if a.margin:
        boss, cell = a.margin[0], tuple(int(v) for v in a.margin[1].split(","))
        at = seats(L, template=True)
        for o in sorted(at):
            if o != boss:
                ma, mb = margins(L, boss, cell, o, at[o], reach)
                print("%s at %s vs %s: %.2f, %.2f (both must exceed %g)" % (boss, cell, o, ma, mb, reach))
        return 0
    at = seats(L, template=a.template)
    moved = {b for b in at if at[b] != L.spawners[b]}
    bad = 0
    for x, y, n in pairs(L, at, reach):
        flag = "OK" if n == 0 else ("FAIL (a moved boss)" if {x, y} & moved else "SHARED (not moved: the owner's)")
        bad += bool(n and {x, y} & moved)
        print("%-22s %-22s shared cells %4d  %s" % (x, y, n, flag))
    print("reach %g; moved: %s; %s" % (reach, ", ".join("%s %s -> %s" % (b, L.spawners[b], at[b]) for b in sorted(moved))
                                      or "none", "FAIL" if bad else "every moved boss clear"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
