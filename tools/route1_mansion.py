#!/usr/bin/env python
"""The Route 1 mansion: an abandoned manor in its clearing at (1630, 5034), for the Gastly escort.

It is written as an earthwork (authored commands) on a settlement of its own, `route1_mansion`, in
data/placements.json, so the re-application builds it with the towns (R8) and tools/town_audit.py replays and checks
every block it writes. It is not the vanilla woodland mansion: a manor house that was lived in and left.

  28 x 20, front to the south, towards Pallet and Route 1's mouth; the forest's mansion spur arrives from the west
  and the drive walks round to the front door. Two floors and a steep gable roof whose chimneys clear the canopy:
  from just north of Pallet it is on the skyline at 220-240 blocks (Distant Horizons range), but from Route 1's
  mouth and the spur junction the forest hides it at any height (measured, settlement `seen_from`).

  ground floor  foyer (centre), open, its worn runner leading to the dining room door, and a hiding place among
                the crates at its back;
                dining room (west wing), its long table still laid; library (east wing), three aisles between two rows
                of shelves, and the servants' stair up its east wall; the service corridor along the rear, joining all
  upper floor   reached only by the servants' stair (the owner, 2026-09-24: no grand stair, so the house is walked
                room by room in the escort's order); the bedroom hall, west to east through the landing, a sitting
                nook off the landing to the south, five doors (four south, one north-west) and
                a candle stand by each; the sealed ballroom across the rear, its barred doors bent apart, its cold
                hearth at the west end and an inlaid path across the floor through three broken ward marks

The furnishing (furnish()) is an abandoned house rather than labelled rooms: a stopped clock, dust sheets, a table
laid for a meal nobody ate, half-emptied shelves, leaf litter under the broken windows, pale moss where the damp got
in. The Gastly escort's props and actor markers (data/scenes.json, scene route1_gastly_family) sit on and between
these; tests check each marker is standable and each prop is on something this tool builds.

The house's old ward is the Habitat Block in the landing floor (WARD_STONE): one natural ReplaceSpawns block with
the ghost pool, its range reaching every floor of the house and ending inside the clearing, so no seam inside the
house falls back to the forest's pool and the ghosts do not leak into the forest.

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


HC = "handcrafted:"
TABLE = HC + "dark_oak_table[color=red,shape=%s,waterlogged=false]"
CHAIR = HC + "dark_oak_chair[color=%s,facing=%s,waterlogged=false]"      # facing: where the sitter looks
BED = HC + "dark_oak_fancy_bed[color=%s,facing=%s,occupied=false,part=%s,shape=single]"   # facing: toward the headboard
PLATE = HC + "white_plate[facing=%s,pieces=1,waterlogged=false]"
CUP = HC + "white_cup[facing=%s,pieces=1,waterlogged=false]"
CANDLE = "minecraft:candle[candles=%d,lit=false,waterlogged=false]"
MOSS = "minecraft:pale_moss_carpet[bottom=true,east=none,north=none,south=none,west=none]"
LITTER = "minecraft:leaf_litter[facing=%s,segment_amount=%d]"
HANGING_MOSS = "minecraft:pale_hanging_moss[tip=true]"
FRAME = "beautify:dark_oak_picture_frame[facing=%s,frame_motive=%d]"
CANDELABRA = "beautify:lamp_candelabra[facing=%s,hanging=false,on=false]"
BOOKSTACK = "beautify:bookstack[bookstack_model=%d,facing=%s]"
CHISELED = "minecraft:chiseled_bookshelf[facing=%s,slot_0_occupied=%s,slot_1_occupied=%s,slot_2_occupied=%s,slot_3_occupied=%s,slot_4_occupied=%s,slot_5_occupied=%s]"
WARD_STONE = (1629, 120, 5033)                   # the Habitat Block, set in the landing floor (data/habitat_blocks.json)
WARD_MARKS = [(1626, 5026), (1630, 5029), (1634, 5026)]   # the ballroom's three broken marks, in the inlay's order
CANDLE_STANDS = [(1619, 5034), (1624, 5034), (1635, 5034), (1641, 5034), (1619, 5032)]   # doors A B C D and north


def back_stair(fill, sb):
    """The servants' stair: up the library's east wall into the south-east bedroom, one wide, rising north."""
    for i in range(6):
        z = 5041 - i
        if i:
            fill((1642, F + 1, z), (1642, F + i, z), "minecraft:dark_oak_planks")
        sb(1642, F + 1 + i, z, "minecraft:dark_oak_stairs[facing=north]")
    fill((1642, U, 5037), (1642, U, 5041), "minecraft:air")                     # its well through the bedroom floor
    fill((1642, U + 1, 5037), (1642, U + 2, 5041), "minecraft:air")
    fill((1641, U + 1, 5038), (1641, U + 1, 5041), "minecraft:dark_oak_fence")   # the well's rail (a lantern closes 5037)


def chiseled(facing, h):
    return CHISELED % ((facing,) + tuple("true" if (h >> k) & 1 else "false" for k in range(6)))


def furnish(fill, sb):
    """An abandoned house, not rooms: what the family left, where they left it, and what the years did to it.

    Nothing here is a spawn condition that matters: the ward stone's ReplaceSpawns covers every floor of the house
    (tools/route1_mansion.py WARD_STONE, range in data/habitat_blocks.json). Cobweb is still kept out: pale hanging
    moss stands in for it."""
    y = F + 1                                                                     # ground floor, feet
    # ---------------------------------------------------------------- foyer
    sb(1625, y, 5042, "cozyhome:dark_oak_grandfather_clock")                     # stopped
    sb(1632, y, 5042, HC + "dark_oak_side_table[color=none,facing=west,waterlogged=false]")
    sb(1632, y + 1, 5042, CANDELABRA % "west")
    sb(1628, U - 1, 5042, "minecraft:chain[axis=y,waterlogged=false]")
    sb(1628, U - 2, 5042, "beautify:lamp_candelabra[facing=north,hanging=true,on=false]")
    sb(1627, y, 5042, LITTER % ("north", 3))                                     # blown in under the door
    sb(1630, y, 5042, LITTER % ("east", 2))
    sb(1631, y, 5041, LITTER % ("south", 1))
    for z, m in ((5040, 3), (5033, 7)):
        sb(1625, y + 2, z, FRAME % ("east", m))
    for z, m in ((5040, 5), (5033, 9)):
        sb(1632, y + 2, z, FRAME % ("west", m))
    sb(1632, y + 1, 5036, "cozyhome:dark_oak_wall_mirror[facing=west,vertical_connection=single]")
    # the back of the foyer, where Pip hides: crates, dust-sheeted chairs, a loose board
    sb(1625, y, 5029, "minecraft:barrel[facing=up,open=false]")
    sb(1625, y + 1, 5029, "minecraft:barrel[facing=north,open=false]")
    sb(1626, y, 5029, "minecraft:barrel[facing=up,open=false]")
    sb(1625, y, 5031, HC + "dark_oak_cupboard[facing=east,type=1]")
    for z in (5030, 5032):                                                        # chairs under dust sheets
        sb(1632, y, z, "minecraft:light_gray_wool")
        sb(1632, y + 1, z, "minecraft:light_gray_carpet")
    sb(1627, y, 5031, "minecraft:dark_oak_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]")
    sb(1626, y, 5034, MOSS)
    sb(1631, y, 5029, MOSS)
    for x, z in ((1626, 5031), (1631, 5034), (1625, 5041)):
        sb(x, U - 1, z, HANGING_MOSS)
    # ---------------------------------------------------------------- dining room: the table still laid
    for z in range(5031, 5041):
        end = "north" if z == 5031 else "south" if z == 5040 else None
        sb(1619, y, z, TABLE % ("%s_west_corner" % end if end else "west_center"))
        sb(1620, y, z, TABLE % ("%s_east_corner" % end if end else "east_center"))
    for z in (5032, 5034, 5036, 5038):
        sb(1618, y, z, CHAIR % ("red", "east"))
        if z != 5036:
            sb(1621, y, z, CHAIR % ("red", "west"))
    sb(1622, y, 5037, CHAIR % ("red", "east"))                                    # pushed back, turned to the wall
    sb(1619, y, 5030, CHAIR % ("red", "south"))                                   # the head of the table
    sb(1620, y, 5041, CHAIR % ("red", "north"))
    for z in range(5032, 5040):                                                   # a place laid at every seat
        sb(1619, y + 1, z, (PLATE if z % 2 == 0 else CUP) % "west")
        sb(1620, y + 1, z, (PLATE if z % 2 == 0 else CUP) % "east")
    sb(1619, y + 1, 5031, PLATE % "north")
    sb(1620, y + 1, 5031, HC + "blue_cup[facing=north,pieces=1,waterlogged=false]")   # the marked cup (scene prop "cup")
    sb(1619, y + 1, 5040, CANDELABRA % "north")
    sb(1620, y + 1, 5040, CANDELABRA % "south")
    sb(1619, U - 1, 5035, "minecraft:chain[axis=y,waterlogged=false]")
    sb(1619, U - 2, 5035, "beautify:lamp_candelabra[facing=north,hanging=true,on=false]")
    for z in range(5033, 5038):                                                   # the sideboard
        sb(1617, y, z, HC + "dark_oak_counter[counter=dark_oak_planks,facing=east,type=1]")
    sb(1617, y + 1, 5033, CANDLE % 2)
    sb(1617, y + 1, 5034, HC + "berry_jam_jar[facing=east,jars=2]")
    sb(1617, y + 1, 5036, HC + "white_bowl[facing=east,pieces=2,waterlogged=false]")
    sb(1617, y + 2, 5035, FRAME % ("east", 1))
    for z in (5031, 5032):
        sb(1623, y, z, HC + "dark_oak_cupboard[facing=west,type=1]")
    sb(1617, y, 5040, LITTER % ("west", 2))
    sb(1622, y, 5029, LITTER % ("south", 1))
    sb(1617, y, 5029, MOSS)
    sb(1623, y, 5042, MOSS)
    sb(1622, U - 1, 5041, HANGING_MOSS)
    # ---------------------------------------------------------------- service corridor
    for x in (1617, 1618):
        sb(x, y, 5025, "minecraft:barrel[facing=up,open=false]")
    for x in range(1621, 1626):
        sb(x, y, 5025, HC + "dark_oak_counter[counter=smooth_stone,facing=south,type=1]")
    sb(1622, y + 1, 5025, HC + "terracotta_thick_pot")
    sb(1624, y + 1, 5025, HC + "wood_bowl[facing=south,pieces=3,waterlogged=false]")
    sb(1642, y, 5025, "minecraft:cauldron")
    sb(1642, y, 5027, "minecraft:smoker[facing=west,lit=false]")
    sb(1641, y, 5025, "minecraft:barrel[facing=up,open=false]")
    sb(1630, y, 5025, MOSS)
    sb(1619, U - 1, 5026, HANGING_MOSS)
    # ---------------------------------------------------------------- library: actually shelved
    for x, face in ((1636, "west"), (1639, "east")):                             # half-emptied chiseled shelves
        for z, h in ((5032, 0b101101), (5033, 0b011010), (5038, 0b110011), (5040, 0b000111)):
            sb(x, y + 2, z, chiseled(face, h))
    for x, face in ((1636, "east"), (1639, "west")):
        for z, h in ((5037, 0b111000), (5041, 0b010101)):
            sb(x, y, z, chiseled(face, h))
    sb(1640, y, 5029, HC + "dark_oak_desk[color=green,facing=south,waterlogged=false]")
    sb(1640, y, 5030, CHAIR % ("green", "north"))
    sb(1640, y + 1, 5029, HC + "stackable_book[books=3,facing=south,seed=17]")
    sb(1635, y, 5029, "minecraft:lectern[facing=south,has_book=false,powered=false]")
    sb(1637, y, 5029, BOOKSTACK % (2, "north"))
    sb(1642, y, 5030, BOOKSTACK % (5, "west"))
    for x, m in ((1634, 1), (1637, 4), (1640, 6)):                               # the aisles' far ends (scene props)
        sb(x, y, 5042, BOOKSTACK % (m, "north"))
    sb(1634, y + 2, 5036, FRAME % ("east", 11))
    sb(1638, U - 1, 5033, HANGING_MOSS)
    sb(1634, U - 1, 5040, HANGING_MOSS)
    sb(1641, y, 5033, LITTER % ("north", 2))
    # ---------------------------------------------------------------- the bedroom hall
    u = U + 1
    for x in range(X0 + 1, X1):
        if x not in (1629,):                                                      # the ward stone shows through
            sb(x, u, 5033, "minecraft:red_carpet")
    for x, z in CANDLE_STANDS:                                                    # Litwick candles by each door
        sb(x, u, z, "minecraft:dark_oak_fence")
        sb(x, u + 1, z, CANDLE % 3)
    for x, m in ((1620, 2), (1625, 8), (1633, 10), (1637, 12)):
        sb(x, u + 2, 5032, FRAME % ("south", m))
    # bedroom A: the parents'
    sb(1617, u, 5042, BED % ("red", "south", "head"))
    sb(1617, u, 5041, BED % ("red", "south", "foot"))
    sb(1618, u, 5042, HC + "dark_oak_nightstand[color=none,facing=north,waterlogged=false]")
    sb(1619, u, 5039, HC + "dark_oak_cupboard[facing=west,type=1]")
    sb(1617, u + 1, 5038, "cozyhome:dark_oak_wall_mirror[facing=east,vertical_connection=single]")
    # bedroom B: a child's
    sb(1621, u, 5042, BED % ("blue", "south", "head"))
    sb(1621, u, 5041, BED % ("blue", "south", "foot"))
    sb(1625, u, 5042, HC + "dark_oak_side_table[color=none,facing=west,waterlogged=false]")
    sb(1625, u + 1, 5042, BOOKSTACK % (0, "west"))
    sb(1625, u, 5039, CHAIR % ("blue", "west"))
    sb(1622, u, 5038, MOSS)
    # bedroom C: a study
    sb(1632, u, 5042, HC + "dark_oak_desk[color=none,facing=north,waterlogged=false]")
    sb(1632, u, 5041, CHAIR % ("none", "south"))
    sb(1632, u + 1, 5042, HC + "stackable_book[books=2,facing=north,seed=88]")
    sb(1635, u, 5042, BOOKSTACK % (3, "north"))
    # the sitting nook off the landing, over the foyer: two chairs at the front window, a table between
    sb(1627, u, 5041, CHAIR % ("purple", "east"))
    sb(1630, u, 5041, CHAIR % ("purple", "west"))
    sb(1628, u, 5042, HC + "dark_oak_side_table[color=none,facing=north,waterlogged=false]")
    sb(1628, u + 1, 5042, BOOKSTACK % (1, "north"))
    sb(1629, u, 5042, "minecraft:soul_lantern[hanging=false]")
    sb(1627, u + 2, 5038, FRAME % ("east", 3))
    sb(1629, u, 5037, MOSS)
    # bedroom D: the back stair comes up here
    sb(1637, u, 5042, BED % ("gray", "south", "head"))
    sb(1637, u, 5041, BED % ("gray", "south", "foot"))
    sb(1638, u, 5042, HC + "dark_oak_nightstand[color=none,facing=north,waterlogged=false]")
    sb(1639, u, 5038, MOSS)
    # the north-west room: the family's, where they are found together afterwards
    sb(1617, u, 5025, BED % ("purple", "north", "head"))
    sb(1617, u, 5026, BED % ("purple", "north", "foot"))
    sb(1620, u, 5025, CHAIR % ("purple", "south"))
    for x in (1618, 1619):
        for z in (5027, 5028):
            sb(x, u, z, "minecraft:purple_carpet")
    # ---------------------------------------------------------------- the ballroom
    for z in (5027, 5029):                                                        # the hearth, cold
        for yy in (u, u + 1, u + 2):
            sb(1622, yy, z, "minecraft:bricks")
    sb(1622, u + 1, 5028, "minecraft:bricks")
    sb(1622, u + 2, 5028, "minecraft:bricks")
    sb(1622, u, 5028, "minecraft:soul_campfire[facing=east,lit=false,signal_fire=false,waterlogged=false]")
    inlay = [(1623, 5028), (1624, 5027), (1625, 5026), (1627, 5027), (1628, 5028), (1629, 5029), (1631, 5028),
             (1632, 5027), (1633, 5026), (1635, 5027), (1636, 5028)]
    for x, z in inlay:                                                            # hearth, A, B, C, to the barrier
        sb(x, U, z, "minecraft:gilded_blackstone")
    for x, z in WARD_MARKS:
        sb(x, U, z, "minecraft:chiseled_polished_blackstone")
        sb(x, u, z, CANDLE % 1)
    for x in range(1624, 1636, 2):                                                # chairs along the north wall
        sb(x, u, 5025, CHAIR % ("purple", "south"))
    sb(1624, u, 5030, MOSS)
    sb(1631, u, 5030, MOSS)
    sb(1641, u, 5025, MOSS)
    # the house's old ward, cracked in the landing floor: the Habitat Block that makes this a ghost house. The same
    # block and state tools/habitat_blocks.py sets (R9E), which then gives it its pool and range
    sb(*WARD_STONE, "cobblemon:habitat_block[cancels_regular_spawns=true,activated_style=false]")


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
    fill((1625, F + 1, 5036), (1632, F + 1, 5042), "minecraft:red_carpet")                 # a runner, worn down the middle
    # library (east wing): two rows of shelves, three aisles
    for x in (1636, 1639):
        fill((x, F + 1, 5031), (x, F + 3, 5041), "minecraft:bookshelf")
        fill((x, F + 1, 5035), (x, F + 3, 5035), "minecraft:air")                     # a gap through each row

    # ---- upper floor
    HALL0, HALL1 = 5032, 5034                      # the bedroom hall, z; the landing is its middle
    for y in range(U + 1, EAVE - 1):
        fill((X0 + 1, y, HALL0 - 1), (X1 - 1, y, HALL0 - 1), "minecraft:dark_oak_planks")   # hall's north wall
        fill((X0 + 1, y, HALL1 + 1), (1625, y, HALL1 + 1), "minecraft:dark_oak_planks")     # its south wall, west
        fill((1632, y, HALL1 + 1), (X1 - 1, y, HALL1 + 1), "minecraft:dark_oak_planks")     # and east of the nook
        for x in (1620, 1636):                                                             # bedroom partitions
            fill((x, y, HALL1 + 2), (x, y, Z1 - 1), "minecraft:dark_oak_planks")
        fill((1621, y, Z0 + 1), (1621, y, HALL0 - 2), "minecraft:dark_oak_planks")          # NW bedroom / ballroom
    doors = [(1618, HALL1 + 1, "south"), (1623, HALL1 + 1, "south"), (1634, HALL1 + 1, "south"),
             (1640, HALL1 + 1, "south"), (1618, HALL0 - 1, "north")]
    for x, z, face in doors:
        sb(x, U + 1, z, "minecraft:dark_oak_door[facing=%s,half=lower]" % face)
        sb(x, U + 2, z, "minecraft:dark_oak_door[facing=%s,half=upper]" % face)
    for y in range(U + 1, EAVE - 1):                               # the nook's sides close off bedrooms B and C
        fill((1626, y, 5036), (1626, y, Z1 - 1), "minecraft:dark_oak_planks")
        fill((1631, y, 5036), (1631, y, Z1 - 1), "minecraft:dark_oak_planks")
    # the sealed ballroom, across the rear from x 1622, open to the roof. Its barred doors off the landing have been
    # bent apart: one bar is gone, so the way in is a squeeze, not a door
    fill((1622, U, Z0 + 1), (X1 - 1, U, HALL0 - 2), "minecraft:polished_blackstone")
    for x in range(1622, X1, 2):
        for z in range(Z0 + 1 + (x % 4 == 0), HALL0 - 1, 2):
            sb(x, U, z, "minecraft:calcite")
    fill((1628, U + 1, HALL0 - 1), (1628, U + 3, HALL0 - 1), "minecraft:iron_bars")
    fill((1629, U + 1, HALL0 - 1), (1629, U + 2, HALL0 - 1), "minecraft:air")
    sb(1629, U + 3, HALL0 - 1, "minecraft:iron_bars")
    fill((1628, U + 4, HALL0 - 1), (1629, U + 4, HALL0 - 1), "minecraft:dark_oak_planks")
    back_stair(fill, sb)
    furnish(fill, sb)
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
    for x, z in ((1619, 5037), (1624, 5037), (1633, 5037), (1641, 5037), (1620, 5029), (1623, 5033), (1640, 5033)):
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
            "reading": "Leaving Pallet, the forest's side path turns off Route 1's mouth to the east and opens into a clearing, and the house fills it: a manor two storeys high, stone below and dark timber above, its roof broken and its chimneys over the trees. The drive walks round to the front, which faces south. Inside, the foyer is open, its runner worn to the dining room door; the dining room is to the west, the library to the east, the service corridor behind, and the only stair is the servants' stair up the library's east wall. Upstairs, five doors off the bedroom hall, a sitting nook off the landing, and at the back, behind barred doors off the landing, the ballroom.",
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
    house = {"id": "route1_mansion_house", "settlement": SID, "kind": "earthwork", "cell": "E2",       # z 4096-5119
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
