#!/usr/bin/env python
"""The Route 1 mansion: an abandoned manor in its clearing at (1630, 5034), for the Gastly escort.

It is written as an earthwork (authored commands) on a settlement of its own, `route1_mansion`, in
data/placements.json, so the re-application builds it with the towns (R8) and tools/town_audit.py replays and checks
every block it writes. It is not the vanilla woodland mansion: a manor house that was lived in and left.

  28 x 20, front to the south, towards Pallet and Route 1's mouth; the forest's mansion spur arrives from the west
  and the drive walks round to the front door. Two floors and a steep gable roof whose chimneys clear the canopy:
  from just north of Pallet it is on the skyline at 220-240 blocks (Distant Horizons range), but from Route 1's
  mouth and the spur junction the forest hides it at any height (measured, settlement `seen_from`).

  ground floor  foyer (centre) with the grand stair rising north to the landing; dining room (west wing) with a long
                table; library (east wing), three aisles between two rows of shelves; the service corridor along the
                rear, joining all three
  upper floor   the bedroom hall, west to east through the landing, with five doors (four south, one north-west);
                the sealed ballroom across the rear, reached from the landing through barred doors

Every room has soul lanterns, so no floor inside is at block light 0 and no hostile mob spawns in the house; the
ghosts are the event's own. No block in it is a spawn condition (no cobweb, no white or yellow carpet or bed).

  python tools/route1_mansion.py --source-root <root>     # writes the settlement and its earthwork
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import ground as G

ROOT = Path(__file__).resolve().parent.parent
SID = "route1_mansion"
X0, Z0, X1, Z1 = 1616, 5024, 1643, 5043          # 28 x 20, outer walls included
F = 114                                          # ground floor surface
U = F + 6                                        # upper floor surface (120)
EAVE = U + 6                                     # 126


def weather(x, y, z):
    """A deterministic mix for an old wall: mostly stone brick, some mossy, some cracked."""
    h = (x * 73856093 ^ y * 19349663 ^ z * 83492791) & 0xFFFF
    return ("minecraft:mossy_stone_bricks" if h % 7 == 0 else "minecraft:cracked_stone_bricks" if h % 5 == 0
            else "minecraft:stone_bricks")


def build(g):
    c = ["# the Route 1 mansion: an abandoned manor for the Gastly escort (tools/route1_mansion.py)"]
    fill = lambda a, b, blk: c.append("fill %d %d %d %d %d %d %s" % (a[0], a[1], a[2], b[0], b[1], b[2], blk))
    sb = lambda x, y, z, blk: c.append("setblock %d %d %d %s" % (x, y, z, blk))
    low = min(g(x, z) for x in range(X0, X1 + 1) for z in range(Z0, Z1 + 1))
    # the site: clear, then a plinth down to the ground
    fill((X0 - 2, F, Z0 - 2), (X1 + 2, EAVE + 16, Z1 + 2), "minecraft:air")
    fill((X0, low - 2, Z0), (X1, F - 1, Z1), "minecraft:stone_bricks")
    fill((X0, F, Z0), (X1, F, Z1), "minecraft:dark_oak_planks")
    # ground floor walls, weathered stone
    for y in range(F + 1, U):
        for x in range(X0, X1 + 1):
            sb(x, y, Z0, weather(x, y, Z0)); sb(x, y, Z1, weather(x, y, Z1))
        for z in range(Z0 + 1, Z1):
            sb(X0, y, z, weather(X0, y, z)); sb(X1, y, z, weather(X1, y, z))
    # upper floor: half-timbered dark oak on the stone
    fill((X0, U, Z0), (X1, U, Z1), "minecraft:dark_oak_planks")
    for y in range(U + 1, EAVE):
        fill((X0, y, Z0), (X1, y, Z0), "minecraft:dark_oak_planks")
        fill((X0, y, Z1), (X1, y, Z1), "minecraft:dark_oak_planks")
        fill((X0, y, Z0), (X0, y, Z1), "minecraft:dark_oak_planks")
        fill((X1, y, Z0), (X1, y, Z1), "minecraft:dark_oak_planks")
    for x in list(range(X0, X1 + 1, 4)) + [X1]:
        fill((x, U + 1, Z0), (x, EAVE - 1, Z0), "minecraft:stripped_dark_oak_log")
        fill((x, U + 1, Z1), (x, EAVE - 1, Z1), "minecraft:stripped_dark_oak_log")
    for z in (Z0, Z0 + 5, Z0 + 10, Z0 + 15, Z1):
        fill((X0, U + 1, z), (X0, EAVE - 1, z), "minecraft:stripped_dark_oak_log")
        fill((X1, U + 1, z), (X1, EAVE - 1, z), "minecraft:stripped_dark_oak_log")
    fill((X0, EAVE - 1, Z0), (X1, EAVE - 1, Z0), "minecraft:stripped_dark_oak_log[axis=x]")
    fill((X0, EAVE - 1, Z1), (X1, EAVE - 1, Z1), "minecraft:stripped_dark_oak_log[axis=x]")
    # windows, some broken (left open)
    k = 0
    for x in range(X0 + 2, X1 - 1, 3):
        for y0, z in ((F + 2, Z1), (U + 2, Z1), (F + 2, Z0), (U + 2, Z0)):
            if abs(x - 1629) <= 1 and z == Z1 and y0 == F + 2:
                continue                                          # the front door
            blk = "minecraft:air" if k % 5 == 3 else "minecraft:glass_pane"
            fill((x, y0, z), (x, y0 + 1, z), blk)
            k += 1
    for z in range(Z0 + 3, Z1 - 1, 4):
        for y0, x in ((F + 2, X0), (U + 2, X0), (F + 2, X1), (U + 2, X1)):
            blk = "minecraft:air" if k % 5 == 3 else "minecraft:glass_pane"
            fill((x, y0, z), (x, y0 + 1, z), blk)
            k += 1
    # the front door: double dark oak under a stone lintel, steps down to the drive
    sb(1628, F + 1, Z1, "minecraft:dark_oak_door[facing=south,half=lower,hinge=left]")
    sb(1628, F + 2, Z1, "minecraft:dark_oak_door[facing=south,half=upper,hinge=left]")
    sb(1629, F + 1, Z1, "minecraft:dark_oak_door[facing=south,half=lower,hinge=right]")
    sb(1629, F + 2, Z1, "minecraft:dark_oak_door[facing=south,half=upper,hinge=right]")
    fill((1627, F + 3, Z1), (1630, F + 3, Z1), "minecraft:chiseled_stone_bricks")
    fill((1627, F, Z1 + 1), (1630, F, Z1 + 1), "minecraft:stone_brick_stairs[facing=north]")

    # ---- ground floor interior
    WEST, EAST, REAR = 1624, 1633, Z0 + 4          # wing walls, and the wall between the rooms and the corridor
    for y in range(F + 1, U):
        fill((WEST, y, REAR), (WEST, y, Z1 - 1), "minecraft:stone_bricks")
        fill((EAST, y, REAR), (EAST, y, Z1 - 1), "minecraft:stone_bricks")
        fill((X0 + 1, y, REAR), (X1 - 1, y, REAR), "minecraft:stone_bricks")
    for x, z in ((WEST, 5038), (EAST, 5038), (1620, REAR), (1629, REAR), (1638, REAR)):     # doorways
        fill((x, F + 1, z), (x, F + 2, z), "minecraft:air")
    fill((1625, F + 1, 5036), (1632, F + 1, 5042), "minecraft:red_carpet")                 # a runner, worn; the stair covers it
    # foyer: the grand stair, 4 wide, rising north from z 5040 to the landing at z 5034
    for i, z in enumerate(range(5040, 5034, -1)):
        fill((1627, F + 1 + i, z), (1630, F + 1 + i, z), "minecraft:dark_oak_stairs[facing=north]")
        fill((1627, F, z), (1630, F + i, z), "minecraft:dark_oak_planks")
    fill((1627, U, 5036), (1630, U, 5040), "minecraft:air")                          # the stairwell (the top step is the floor)
    fill((1627, U + 1, 5041), (1630, U + 1, 5041), "minecraft:dark_oak_fence")        # its railings
    fill((1626, U + 1, 5035), (1626, U + 1, 5041), "minecraft:dark_oak_fence")
    fill((1631, U + 1, 5035), (1631, U + 1, 5041), "minecraft:dark_oak_fence")
    sb(1625, F + 1, 5042, "minecraft:dark_oak_stairs[facing=east]")                  # broken furniture
    sb(1632, F + 1, 5037, "minecraft:dark_oak_slab")
    sb(1625, F + 1, 5037, "minecraft:barrel[facing=up]")
    # dining room (west wing): a long table and its chairs, cups on it
    fill((1620, F + 1, 5031), (1620, F + 1, 5041), "minecraft:dark_oak_fence")
    fill((1620, F + 2, 5031), (1620, F + 2, 5041), "minecraft:dark_oak_slab[type=bottom]")
    fill((1620, F + 1, 5032), (1620, F + 1, 5040), "minecraft:air")
    for z in range(5032, 5041, 2):
        sb(1619, F + 1, z, "minecraft:dark_oak_stairs[facing=east]")
        sb(1621, F + 1, z, "minecraft:dark_oak_stairs[facing=west]")
        sb(1620, F + 3, z, "minecraft:flower_pot")
    sb(1617, F + 1, 5041, "minecraft:dark_oak_stairs[facing=south]")                 # a chair knocked to the wall
    # library (east wing): two rows of shelves, three aisles
    for x in (1636, 1639):
        fill((x, F + 1, 5031), (x, F + 3, 5041), "minecraft:bookshelf")
        fill((x, F + 1, 5035), (x, F + 3, 5035), "minecraft:air")                     # a gap through each row
    fill((1639, F + 3, 5038), (1639, F + 3, 5040), "minecraft:chiseled_bookshelf[facing=east]")
    sb(1642, F + 1, 5041, "minecraft:lectern[facing=west]")
    # the service corridor, the length of the rear
    sb(X0 + 1, F + 1, Z0 + 1, "minecraft:barrel[facing=up]")
    sb(X0 + 2, F + 1, Z0 + 1, "minecraft:barrel[facing=up]")
    sb(X1 - 1, F + 1, Z0 + 1, "minecraft:cauldron")
    sb(X1 - 1, F + 1, Z0 + 3, "minecraft:smoker[facing=west]")

    # ---- upper floor
    HALL0, HALL1 = 5032, 5034                      # the bedroom hall, z; the landing is its middle
    for y in range(U + 1, EAVE - 1):
        fill((X0 + 1, y, HALL0 - 1), (X1 - 1, y, HALL0 - 1), "minecraft:dark_oak_planks")   # hall's north wall
        fill((X0 + 1, y, HALL1 + 1), (1625, y, HALL1 + 1), "minecraft:dark_oak_planks")     # its south wall, west
        fill((1632, y, HALL1 + 1), (X1 - 1, y, HALL1 + 1), "minecraft:dark_oak_planks")     # and east of the stairwell
        for x in (1620, 1636):                                                             # bedroom partitions
            fill((x, y, HALL1 + 2), (x, y, Z1 - 1), "minecraft:dark_oak_planks")
        fill((1621, y, Z0 + 1), (1621, y, HALL0 - 2), "minecraft:dark_oak_planks")          # NW bedroom / ballroom
    doors = [(1618, HALL1 + 1, "south"), (1623, HALL1 + 1, "south"), (1634, HALL1 + 1, "south"),
             (1640, HALL1 + 1, "south"), (1618, HALL0 - 1, "north")]
    for x, z, face in doors:
        sb(x, U + 1, z, "minecraft:dark_oak_door[facing=%s,half=lower]" % face)
        sb(x, U + 2, z, "minecraft:dark_oak_door[facing=%s,half=upper]" % face)
    beds = [(1617, 5041), (1623, 5041), (1634, 5041), (1641, 5041)]
    for x, z in beds:                                              # a bed's facing points from its foot to its head
        sb(x, U + 1, z + 1, "minecraft:red_bed[facing=north,part=foot]")
        sb(x, U + 1, z, "minecraft:red_bed[facing=north,part=head]")
    sb(1617, U + 1, Z0 + 1, "minecraft:brown_bed[facing=south,part=foot]")
    sb(1617, U + 1, Z0 + 2, "minecraft:brown_bed[facing=south,part=head]")
    # the sealed ballroom, across the rear from x 1622, open to the roof; its doors off the landing are barred
    fill((1622, U, Z0 + 1), (X1 - 1, U, HALL0 - 2), "minecraft:polished_blackstone")
    for x in range(1622, X1, 2):
        for z in range(Z0 + 1 + (x % 4 == 0), HALL0 - 1, 2):
            sb(x, U, z, "minecraft:calcite")
    fill((1628, U + 1, HALL0 - 1), (1629, U + 3, HALL0 - 1), "minecraft:iron_bars")
    fill((1628, U + 4, HALL0 - 1), (1629, U + 4, HALL0 - 1), "minecraft:dark_oak_planks")
    # ---- roof: a steep gable, ridge west to east, holes where it has fallen in
    for i in range(11):
        y = EAVE + i
        zs, zn = Z0 - 1 + i, Z1 + 1 - i
        if zs > zn:
            break
        for x in range(X0 - 1, X1 + 2):
            hs = (x * 31 + i * 17) % 23 == 0
            if not hs:
                sb(x, y, zs, "minecraft:dark_oak_stairs[facing=south]") if zs < zn else sb(x, y, zs, "minecraft:dark_oak_slab")
            if zn != zs and (x * 29 + i * 13) % 19:
                sb(x, y, zn, "minecraft:dark_oak_stairs[facing=north]")
        if zs + 1 <= zn - 1:
            fill((X0, y, zs + 1), (X0, y, zn - 1), "minecraft:dark_oak_planks")         # the gable ends
            fill((X1, y, zs + 1), (X1, y, zn - 1), "minecraft:dark_oak_planks")
    for x in (X0 - 2, X1 + 1):                                                         # chimneys, against the gable ends
        fill((x, low - 1, 5033), (x + 1, EAVE + 14, 5034), "minecraft:bricks")
    # ---- lights: soul lanterns hung from each ceiling, so no floor inside is dark enough to spawn a monster
    for x, z in ((1620, 5035), (1629, 5042), (1638, 5036), (1621, 5026), (1638, 5026), (1629, 5026)):
        sb(x, U - 1, z, "minecraft:soul_lantern[hanging=true]")
    # upstairs the rooms are open to the rafters, so their lanterns stand on the floor
    for x, z in ((1619, 5037), (1624, 5037), (1633, 5037), (1641, 5037), (1619, 5027), (1623, 5033), (1640, 5033)):
        sb(x, U + 1, z, "minecraft:soul_lantern[hanging=false]")
    for x in (1626, 1632, 1638):                                                       # the ballroom's chandeliers
        fill((x, U + 3, 5027), (x, EAVE + 4, 5027), "minecraft:chain")
        sb(x, U + 2, 5027, "minecraft:soul_lantern[hanging=true]")
    return c


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    a = p.parse_args(argv)
    g = G.Ground(a.source_root)
    path = ROOT / "data" / "placements.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["settlements"][SID] = {
        "centre": [1630, 5034], "status": "authored 2026-09-21 and laid out on the disposable world; not in the live world",
        "plan": {
            "reading": "Leaving Pallet, the forest's side path turns off Route 1's mouth to the east and opens into a clearing, and the house fills it: a manor two storeys high, stone below and dark timber above, its roof broken and its chimneys over the trees. The drive walks round to the front, which faces south. Inside, the foyer's stair climbs to the landing; the dining room is to the west, the library to the east, the service corridor behind. Upstairs, five doors off the bedroom hall, and at the back, behind barred doors off the landing, the ballroom.",
            "entries": [{"from": "Route 1's mansion spur (tools/maze_forest.py spur_mansion)", "at": [1604, 5032], "street": "drive"}],
            "exits": [],
            "footprint": {"rect": [1604, 5010, 1656, 5058], "why": "the forest's mansion clearing, radius 22, round (1630, 5034)"},
            "streets": [{"id": "drive", "polyline": [[1604, 5032], [1608, 5047], [1629, 5047]], "width": 3,
                         "surface": "minecraft:mossy_cobblestone", "max_grade": 0.12}],
            "anchors": [{"id": "mansion", "role": "landmark", "template": None, "rect": [X0, Z0, X1, Z1], "facing": "south",
                         "why": "the manor (earthwork route1_mansion_house)"}],
            "house_lots": {"along": [], "why": "one house"},
            "paving": {"main": "minecraft:mossy_cobblestone", "lamp": "none", "why": "an overgrown drive, unlit"},
            "no_services": "an abandoned house on a route, not a town",
        },
        "seen_from": {
            "measured": "2026-09-21, tools/sightlines.py cast over the heightmap, the painted canopy and every Route 1 "
                        "maze-forest tree rastered from its template's size (the painted canopy alone does not hold them); "
                        "targets the two chimney tops (y140) and the ridge (y136)",
            "pallet_exit": "seen: 15 of 15 points north of Pallet (1462-1470, 5191-5231) see both chimneys and the ridge, "
                           "at 219 to 241 blocks, past the 160 blocks a client draws itself: it reads through Distant "
                           "Horizons' LOD, not the vanilla view distance",
            "route1_mouth": "not seen: 0 of 15 points (1452-1468, 5052-5064); the forest between is taller than the line, "
                            "and a top raised to y208 is still not seen, so no tower or belfry fixes it",
            "spur_junction": "not seen: 0 of 9 points at (1466, 5036); the house is found by the spur's own clearing",
        },
    }
    # only the house, in its place: the settlement's other earthworks (its lights, tools/light_plan.py) are not this tool's
    house = {"id": "route1_mansion_house", "settlement": SID, "kind": "earthwork", "cell": "F2",
             "status": "planned", "chosen_because": "the Gastly escort's house (docs/story/events/ROUTE1_GASTLY_MANSION.md), "
             "authored because the vanilla woodland mansion is the wrong house; see tools/route1_mansion.py",
             "commands": build(g)}
    at = next((i for i, q in enumerate(doc["placements"]) if q["id"] == house["id"]), None)
    if at is None:
        doc["placements"].append(house)
    else:
        doc["placements"][at] = house
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote %s: %d commands" % (SID, len(house["commands"])))


if __name__ == "__main__":
    main()
