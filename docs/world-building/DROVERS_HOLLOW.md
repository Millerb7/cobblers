# The Drovers' Hollow

A place to find in the Rift Foot (cell F4, sub-region `rift_foot`, region `southern_coast`): a stone-footed longbarn
in the dry ravine's hollow, its fold of Miltank, Tauros and Mudsdale, a spring trough at the back of the barn, a well
behind the spring, and an old working under the east bank that holds the find. The last drover, Owen Cray, stands
in the lane by the fold and his talk points at the well.

- Record: `data/drovers_hollow.json` (hand-authored; every Y is derived from the heightmap)
- Generator: `tools/drovers_hollow.py` -> `build/datapacks/cobblers_drovers_hollow` (`--report` writes nothing)
- Independent audit: `tools/drovers_hollow_audit.py` (never imports the generator's geometry)
- Tests: `tests/test_drovers_hollow.py` (the clean pack, and eight generator mutations each caught)
- Re-apply: **R9HF** (the block pass, after R9LH and before R9E) and **R18HF** (the drover, after R17N)
- Shared records: the herd's Habitat Block `drovers_hollow_fold_ward` (`data/habitat_blocks.json`), its pool
  `drovers_hollow_fold` (`data/spawns.json`), the cache `drovers_hollow_store` (`data/rewards.json`), the conversation
  `dlg_drovers_hollow_drover` (`data/dialogue.json`), the quest `ambient_drovers_hollow` (`data/quests.json`) and its
  cursor field (`data/progression.json`)

Status: generated and audited offline, 2026-10-02. **Not applied to any world and not seen in game.**

## Why it is built, not cut into the Rift's south wall

The brief proposed a cave-barn cut into the foot of the Rift's south wall. Measured on the canonical heightmap, there is
no such wall to cut into:

- Outside the Rift's polygon (`data/regions.json` `the_rift`, which ends at z5392-5408) the southern country is a gentle
  savanna slope, about 1 in 25. A search of every mouth on a 2-block grid over x2900-5200, z5450-6900, in each cardinal
  direction, for a 21 by 28 footprint with 8 or more blocks of ground over a 3-high room found one site, 980 blocks from
  the Rift; with 11 blocks (a 6-high barn under the Ursaluna den's 4-block shell plus one) it found none.
- Every site with that cover lies inside the Rift polygon, where `tools/rift_sculpt.py` has cut and re-walled the rim in
  the world (the heightmap is not the ground there), and inside or beside the Rift's zones, which the brief forbids.

So the barn is built in the dry ravine's hollow (`data/landmarks.json` `arrow_lake_south_east_branch`, "water never"),
the Lopunny house's pattern, and only the working under it is carved, the Ursaluna den's shell-then-void way.

## Features and coordinates

All Y values from `tools/drovers_hollow.py --report` on 2026-10-02 (heightmap ground y98-99 under the barn and fold).

| Feature | Where |
|---|---|
| Longbarn, outer walls | x3960-3986, z6016-6030; floor y100 (max ground 99 + 1), walls y101-105, ridge y114 along z6023 |
| Cattle doorway (open, west gable) | x3960, z6022-6024, y101-104; ramp stairs at (3959, 100) and (3958, 99), z6022-6024 |
| Man's doorway (south wall, to the fold) | (3972, 101-102, 6030); ramp stairs at (3972, 100, 6031) and (3972, 99, 6032) |
| Stalls | partitions at x3963, 3967, 3971, 3975 (z6017-6020 and z6026-6029); hay mangers at the back walls |
| Hay loft | floor y104 over x3977-3985, z6017-6029; ladder at (3976, 101-105, 6017) on the north wall |
| The spring | three water cauldrons at (3982, 101, 6022-6024), under the loft |
| The well | trapdoor at (3984, 100, 6023) in a ring of mossy stone-brick slabs; ladder down (3984, 92-99, 6023) |
| The old working: drift | x3984-4012, z6022-6024, gravel floor y91, air y92-94; props every 5 blocks from x3988 |
| The old working: store | x4013-4021, z6019-6027, cobblestone floor y91, air y92-95; beams at x4015 and x4019 |
| The find (barrel, scenery) | (4021, 92, 6023); sign over it at (4021, 93, 6023); trigger box (4017-4021, 92-94, 6021-6025) |
| The fold | fence ring x3962-3980, z6034-6048 on the ground (y98-99); gate (3972, 99, 6034); corner lanterns |
| Herd Habitat Block | (3971, 98, 6041), activated, mimic coarse dirt; spawn box x3965-3977, z6035-6047 |
| Owen Cray (NPC) | feet (3975, 99, 6032) on a dirt path at (3975, 98, 6032) |
| Lanterns | four over the aisle on ridge chains at y105 (x3963, 3969, 3974) and y110 (x3982); three under the loft; one on the loft; two on posts west of the cattle doorway; four on the fold's corners; four in the drift (x3990, 3997, 4004, 4011, y94); two in the store |
| Write box (for collisions) | x3958-4025, z6015-6048, y88-114; above the ground x3958-3987, z6015-6048; R9HF forceload 3955 6012 4025 6051 |

**Cover over the working.** The shell is 4 blocks (the den's margin), never in the top 2 blocks of a column. The least
ground over a void block outside the barn's footprint is 5 at (3988, 94, 6022), exactly margin + 1, where the drift
leaves the barn's east gable under the toe of the bank; it deepens east to 12 or more over the store.

**Findable.** Route 8 crosses the ravine about 150 blocks south of the barn and runs along its east bank: the ridge
is in clear sight of a standing eye from 74 of Route 8's walked points (sampled every 4th) within 250 blocks. **Off the
path:** the whole write box is 93 blocks from the nearest walked point of Route 8 or Victory Road, 199 from Hornwall's
anchor (4200, 5920), 461 from Giovanni's town.

**The find.** A cache (`data/rewards.json` `drovers_hollow_store`): a Choice Band and three Moomoo Milk, once per player,
granted by reaching the store's east end (`tools/rewards_pack.py`). Both items verified as
`assets/cobblemon/models/item/<id>.json` in the Cobblemon 1.8.0 jar (the EXP-000 copy).

**The herd.** Miltank (anchor), Tauros (common), Mudsdale (uncommon), levels 43-53: the Rift Foot band (tier 8, cap 55).
Up to 6 alive, refilled 2 at a time; the spawn box is inside the fence, so every place a Pokemon can be put is in the
pen. Bouffalant is left out so Hornwall stays the only one.

## What is not verified

- Nothing has been applied to a world. The fills, the herd spawning and staying in the fold, the cache being granted
  and the drover's conversation are all unproven in game.
- `reapply.py plan` could not be run in this worktree (it needs `prepare`'s built packs); the step order is checked by
  `tests/test_drovers_hollow.py` from the text of `tools/reapply.py`.
- Light is checked by distance to a lantern (12 blocks, Manhattan), not by Minecraft's light engine.
- The dry ravine's world surface block (grass, gravel or dirt) is unknown offline; the fold floor and the drover's path
  are written over it, and the rest of the hollow is left as exported.
- The drover mentions Hornwall by name; if Hornwall is moved or renamed, his `hornwall` line must change.

## World probes

For the session that holds the server, after R9HF, R9E, the restart and R18HF. Each `execute if block` should answer
"Test passed"; force-load first (`forceload add 3955 6012 4025 6051`), release after.

```
execute if block 3960 100 6023 minecraft:cobblestone          # the barn floor ring at the cattle doorway
execute if block 3960 102 6023 minecraft:air                  # the cattle doorway is open
execute if block 3959 100 6023 minecraft:spruce_stairs        # the ramp's top step
execute if block 3972 101 6030 minecraft:air                  # the man's doorway
execute if block 3982 101 6023 minecraft:water_cauldron       # the spring trough
execute if block 3984 100 6023 minecraft:spruce_trapdoor      # the well's trapdoor
execute if block 3984 101 6022 minecraft:mossy_stone_brick_slab   # the well-head ring
execute if block 3984 95 6023 minecraft:ladder                # the well's ladder
execute if block 3976 103 6017 minecraft:ladder               # the loft ladder
execute if block 3980 104 6023 minecraft:spruce_planks        # the loft floor
execute if block 3998 93 6023 minecraft:air                   # the drift
execute if block 3998 91 6023 minecraft:gravel                # the drift's floor
execute if block 3998 97 6023 minecraft:stone                 # the shell over the drift
execute if block 3988 95 6023 minecraft:stripped_spruce_log   # a roof beam at the drift's first prop
execute if block 3990 94 6023 minecraft:lantern               # the drift's first lantern
execute if block 4017 93 6023 minecraft:air                   # the store
execute if block 4017 91 6023 minecraft:cobblestone           # the store's floor
execute if block 4021 92 6023 minecraft:barrel                # the find's barrel
execute if block 4021 93 6023 minecraft:spruce_wall_sign      # THE STORE sign
execute if block 3972 99 6034 minecraft:spruce_fence_gate     # the fold's gate
execute if block 3962 100 6034 minecraft:spruce_fence         # the fold's north-west corner post (ground y99 there)
execute if block 3975 98 6032 minecraft:dirt_path             # where the drover stands
execute if block 3964 114 6023 minecraft:spruce_planks        # the ridge
execute if block 3963 105 6023 minecraft:lantern              # an aisle lantern
execute unless block 3971 98 6041 minecraft:coarse_dirt       # after R9E the Habitat Block replaces the floor block
```

The Habitat Block itself: `python tools/habitat_blocks.py verify --rcon` (it knows the block's id and state).

Entities (with the chunk loaded):

```
execute if entity @e[type=cobblemon:npc,x=3975,y=99,z=6032,distance=..2]          # expect 1: Owen Cray
execute if entity @e[type=cobblemon:pokemon,x=3971,y=99,z=6041,distance=..10]     # expect 1 to 6 after a few minutes loaded
execute if entity @e[type=cobblemon:pokemon,x=3971,y=99,z=6041,distance=10..20]   # expect 0 from the herd (a wild one
                                                                                   # outside the fence is a leak)
```

A walk-through: stand at (3972, 99, 6052) south of the fold, go round to the cattle doorway at (3958, 100, 6023), along
the aisle to the trough, open the trapdoor at (3984, 100, 6023), climb down, follow the drift east to the store; the
reward message should appear on reaching x4017-4021 by the barrel.
