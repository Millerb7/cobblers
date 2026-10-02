# The Old Orchard (Sunset Isle)

A place to find in the empty south: an abandoned cider orchard on Sunset Isle's north shore, gone wild round
the resident Slaking that came for the windfall and never left. Rows of fruit trees, a stone press-house whose
roof the storm took, a walled kitchen garden, hives and drying racks, a keeper back on the ferry, and the press
cellar under the floor holding the find.

- Data: `data/old_orchard.json` (hand-authored). Generator: `tools/old_orchard.py` -> `build/datapacks/cobblers_old_orchard`
  (`plan` / `--report` write nothing). Independent audit: `tools/old_orchard_audit.py`. Tests: `tests/test_old_orchard.py`.
- Re-apply: **R9SO** (block pass, before R9E: the Applin Habitat Block sits in a trunk this pack writes), **R18SO** (the
  keeper, after R17N). Pack `cobblers_old_orchard`, world-local (`tools/reapply.py`).
- Status: authored and audited offline, **not applied to any world, nothing seen in game.**

## The resident it is built round

`data/resident_encounters.json` `orchard_sleeper`: a level 60 Slaking at **(2816, 7080)**, catchable after
`gym8_cleared`, trigger 18, leash 26. **Placed by another builder; this pack writes nothing within 4 blocks of the
anchor and never its ground.** Its nearest write is the end of the cart track at (2805, 7080), 11 blocks west.

Measured 2026-10-02 on the canonical heightmap (the water export): the anchor reads **y66, dry**, 4 above sea level
y62; the sea is about 40 blocks north-east. The anchor stands **inside the template box of the giant palm sapling**
`sapling_palm_sunset_east` (box x2814-2862, z7055-7105; the palm's trunk at (2840, 7080)), but none of the palm's
or its companions' blocks lie within 4 of the anchor below y115: the Slaking lies under the palm's crown. A young
companion palm's box (x2809-2822, z7083-7097) is 3 blocks south of it. For the builder placing the Slaking.

## Site

| What | Where |
|---|---|
| Sub-region | `sunset_east` (tier 8, band 43-53), cell G3 |
| Whole footprint (every write and clear) | x2734-2805, z7036-7110 (`old_orchard_all`) |
| Press-house | x2783-2797, z7041-7056 |
| Rows | x2734-2805, z7060-7110 |
| Kitchen garden | x2755-2769, z7039-7049 |
| Yard (hives, racks, posts, spur) | x2740-2794, z7043-7059 |
| Keep out | the palm sapling, its five young palms and its sand dressing, each box + 3 (`keep_out`) |

Nothing in `placements.json`, `towns.json`, `landmarks.json`, `route_paths.json`, `rivers.json` or any other site
file lies within 450 blocks except the palm sapling (24 east of the anchor) and the isle's ferry landing (300 north-west).
The nearest route leg is 997 blocks away (the audit measures it): off the critical path.

**Getting there.** The Sunset strait ferry (`data/ferries.json` `sunset_strait`, $100) from Sunset West's south pier to
the isle's landing at **(2575, 63, 6899)**, then about 230 blocks east-south-east along the shore bench (y63-70, no
climb). The mark is the giant palm (crown to about y134) at the rows' east end; from the landing at eye height the
line to its crown clears the heightmap by 3.1 blocks over 321 (trees not counted). **No jetty is added**: the isle has
its landing.

## Features (fly-to coordinates)

| Feature | Coordinates |
|---|---|
| Press-house floor (centre) | (2790, 66, 7048); floor y66 = max ground under the walls (y65) + 1 |
| Press-house door (south wall) | (2790, 67, 7054), oak door; cobblestone step at (2790, 66, 7055) |
| Ridge (west half only) | y79; lantern on a chain at (2787, 75, 7048) |
| The press (open half) | posts at (2791, 67-69, 7045) and (2794, 67-69, 7045), beam y70, screw over the cauldron (2792, 67, 7045) |
| Collapse | roof gone east of x2791; rafters at x2793 (whole) and x2795 (broken); rubble and a fallen rafter on the floor |
| Trapdoor to the cellar | (2787, 66, 7045), oak trapdoor; ladder (2787, 62-65, 7045) |
| Cellar | room x2787-2793, z7045-7051, floor y61, air y62-64, ceiling y65; lantern (2790, 64, 7048) |
| **The find's barrel** | **(2793, 62, 7051)**; trigger box (2791-2793, 62-63, 7049-7051) |
| Keeper, Wenna Marlow | (2786, 67, 7058), beside the track's spur |
| Cart track | z7080 from x2736 to x2805; spur x2790 from z7056 to z7079 |
| Rows | z7064, 7072, 7088, 7096, 7104; trees at x2738, 2746, ... 2794 (8 a row, 40) |
| Storm-bent (8) | (2786, 7064), (2794, 7064), (2786, 7072), (2786, 7088), (2786, 7096), (2794, 7096), (2786, 7104), (2794, 7104) |
| Fallen, the windfall (2) | (2794, 7072) and (2794, 7088), trunks lying east to x2799 |
| Dead (3) / stumps (3) | dead (2738, 7104), (2754, 7064), (2762, 7096); stumps (2746, 7072), (2770, 7088), (2754, 7104) |
| Applin Habitat Block | (2754, 72, 7088), the second log of a living tree |
| Beehives | (2742, 71, 7058), (2750, 70, 7058), (2758, 69, 7058), (2766, 69, 7058) |
| Kitchen garden gate | (2769, 66, 7044), oak fence gate |
| Drying racks | x2775-2778 at z7044 and z7048 |
| Lantern posts (30) | `data/old_orchard.json` `lantern_posts.at`; each lantern at ground + 3 |

Trees: a 3-log oak trunk on its own ground + 1 and a crown of **persistent** oak leaves. Lighting: lanterns on posts
(30), in the press-house and in the cellar, never light blocks; 4,642 of 5,012 ground columns in the feature boxes
are within lantern light (15 less Manhattan distance, leaves not counted).

## Encounters

- **The pool** (`data/spawns.json` habitat `old_orchard_rows`, Habitat Block `old_orchard_rows_ward`, activated,
  spawn_range 12, up to 6): Applin 43-53 (common 24), Tropius 43-53 (uncommon 6), Flapple and Appletun 48-53 (rare 2
  each). The spawn box (x2742-2766, z7076-7100) is 50 blocks from the resident, outside its leash.
- **Slakoth and Vigoroth were proposed and cannot spawn here.** sunset_east is tier 8, band 43-53; the evolution policy
  (`data/spawns.json` `evolution_policy`) lets a stage spawn only up to four past its next level evolution, and in the
  Cobblemon 1.8.0 jar Slakoth evolves at 18 and Vigoroth at 36: ranges 43-22 and 43-40, both empty. A wild Slaking pool
  would make the resident one of many. The audit reads the jar and enforces the rule.
- Oak leaves are a `neededNearbyBlocks` condition of Cobblemon's own default Applin, Flapple and Appletun spawns (1-26,
  21-49). The wilderness keeps default pools, so the rows may also draw low-level default Applin, as any oak wood does.

## The find

`data/rewards.json` `old_orchard_cellar` (a cache, ADR-002): reaching the cellar's south-east corner grants, once per
player, **Leftovers, a Tart Apple and a Sweet Apple** (the apples evolve the orchard's Applin into Flapple and
Appletun). The barrel is scenery. The cellar lies outside the Slaking's leash, so the find is taken without the fight.

## The keeper

`dlg_old_orchard_keeper` (quest `ambient_old_orchard`, cursor `quest.ambient_old_orchard.keeper_cursor`): seven lines,
the last repeating. Who she is, the sleeper at the end of the track and that walking the last trees wakes him, the
Applin, and **the cellar: "trapdoor in the far corner"**. Placed by R18SO with `spawnnpcat` after a restart.

## World probes

For the session that holds the server, after R9SO (and, for the Habitat Block line, R9E and the restart). Each
`execute if block` line should return **1** (test passes) unless marked 0.

```
execute if block 2790 66 7048 minecraft:oak_planks
execute if block 2790 67 7054 minecraft:oak_door[half=lower]
execute if block 2790 68 7054 minecraft:oak_door[half=upper]
execute if block 2787 66 7045 minecraft:oak_trapdoor[open=false]
execute if block 2787 65 7045 minecraft:ladder
execute if block 2787 62 7045 minecraft:ladder
execute if block 2790 61 7048 minecraft:stone_bricks
execute if block 2790 63 7048 minecraft:air
execute if block 2790 64 7048 minecraft:lantern[hanging=true]
execute if block 2793 62 7051 minecraft:barrel
execute if block 2787 75 7048 minecraft:lantern[hanging=true]
execute if block 2793 72 7048 minecraft:stripped_oak_log
execute if block 2794 67 7072 minecraft:oak_log
execute if block 2796 67 7072 minecraft:oak_log[axis=x]
execute if block 2742 71 7058 minecraft:beehive
execute if block 2769 66 7044 minecraft:oak_fence_gate
execute if block 2793 68 7058 minecraft:lantern
execute if block 2792 75 7108 minecraft:lantern
execute if block 2754 72 7088 minecraft:oak_log            (after R9SO, BEFORE R9E)
execute if block 2754 72 7088 cobblemon:habitat_block      (after R9E)
execute if block 2816 67 7080 minecraft:air                (the sleeper's feet: nothing of ours; expect 1)
```

Entities, after R18SO:

```
execute if entity @e[type=cobblemon:npc,x=2786,y=67,z=7058,distance=..2]                     -> 1 (the keeper)
execute if entity @e[type=cobblemon:pokemon,x=2754,y=72,z=7088,distance=..14]                -> 1 or more (Applin pool, after R9E and the restart, with a player near)
```

The cache (advancement `cobblers:reward/old_orchard_cellar`, from `cobblers_rewards`): stand in the cellar's
south-east corner and expect one Leftovers, one Tart Apple and one Sweet Apple, once.

## Not verified

Everything in game: that the fills land, the press-house reads as a ruin, the leaves hold, the trapdoor and ladder
work, Applin spawn round the tree, the cache grants, the keeper renders and talks. Sightlines count no trees. The
Slaking, its trigger and its leash are another builder's.
