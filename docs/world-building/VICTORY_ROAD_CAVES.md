# Victory Road — one cave network

**Status:** built on staging (`cobblers-dryrun9`) on 2026-09-23, from `data/vr_caves.json` by `tools/vr_caves.py`.
It replaces the schema 2 spine (`data/victory_road.json`, retired) and its five regions
(`VICTORY_ROAD_REGIONS.md`, superseded; `tools/vr_regions.py` and `data/vr_regions.json`, removed).

## Why it changed

The owner flew the spine and its regions. The regions were cool; the road still felt "way too pathy"; the tall stair
at the end felt off; and seeing nothing but strong species in the regions felt forced. Asked for "colliding zones and
a deep cave feel". Chosen the same day, from three options each:

| Question | Chosen |
|---|---|
| Structure | A full cave network: no spine, no forks; the five themes become zones that touch and bleed into each other |
| Spawns | Cave life everywhere; each zone adds its flavour; the headline species rare, deep in their own zone |
| The climb | Spread over the whole cave; the last stretch a ravine open to the sky onto the League's apron |

## What it is

- **40 caverns** scattered through a band round the old spine's line, ragged enough and close enough that neighbours
  merge into halls, joined by **66 galleries** that bend every 22 blocks and swell into pockets, with loops so there is
  never one way through. The first cut (smaller, rounder caverns, near-straight tunnels) mapped as a metro diagram of
  beads on strings and was redone before anything was built.
- **Six zones fight over every column.** Each core's hold falls off with distance, noise pushes the borders about,
  and the strongest wins; within a margin the blocks mix. The Dark (plain deep cave, dripstone, unlit) fills the
  ground between the Drowned Gallery (lakes, pillars), the Slagworks (lava pools with lips, falls, a burning floor),
  the Bloom (moss, giant mushrooms, glow berries, puddles), the Raw Tear (the Rift's own material, crystal, veins of
  light) and the Abandoned Cut (props, rails, spoil, lanterns, the Digger).
- **The floor climbs** from the Deep's mouth (y1) to the ravine's foot (y64) by progress, and no floor column is more
  than one block from its neighbour: the whole cave is walkable, and the drama is in ceilings up to 30 high and in the
  lakes. The ravine then climbs to the apron (y89) between the two forecourt terraces, its walls stopping at y87 on
  the lot.
- **One rest station**, in the cavern the walked route crosses nearest its middle, and **ten fights** spread evenly
  along that route, at least 40 apart, lit to calm; the rest of the cave is dark by default.
- **Five finds**, one in each zone's core cavern: four ADR-002 caches (`data/rewards.json`) and the Digger, who gives
  the Cut's through dialogue.

## Spawns

Eleven Habitat pools in `data/spawns.json`, on **80 Habitat Blocks** laid greedily over the floor at four scales
(ranges 28, 16, 10 and 6), never overlapping, covering **89%** of the floor and **100% of the lake water**. The other
11% is seams between circles on dry rock, where the pack's own cave pools still spawn at their own levels. One tile
size alone never covered more than about three quarters, whatever the size. Water counts three times when the tiles
are laid, because it is what summons the pack's 42 water species, and a tile may sit on a lake bed; a tile takes
the pool of the zone holding most of what it covers. Whiscash and Lanturn are `submerged` (from Cobblemon's own
data) and Milotic `submerged` by an authored override, since it has no upstream entry and would otherwise have stood
on the shore.

| Pool | Where | What |
|---|---|---|
| `vrc_cave` | the Dark | Golbat, Excadrill, Boldore, Graveler; Onix, Marowak, Swoobat, Durant; rare: Steelix, Crobat, Golem, Gigalith |
| `vrc_<zone>` | a zone's edge | the zone's own species over half-weight cave life |
| `vrc_<zone>_core` | deep in a zone | the same, with the zone's prize as the **only** rare-bucket species |

Levels 58-64; prizes 60-64 (Dragapult is reached at 60). The natural rare bucket is 0.5% of spawns (the server's own
`best-spawner-config.json`), so a prize is about one spawn in two hundred in its core, and nowhere else: Milotic
(Drowned), Garchomp (Slagworks), Tangrowth (Bloom), Dragapult (Raw Tear), Metagross (Cut). No Dark or Ghost species in
the Slagworks: its lava calms them.

## What the build proves before writing anything

Cover of at least 4 over every roof's shell; rock between the network and the Deep's pit and the EXP-033 rig; every
spawn-conditioning block whitelisted for Victory Road with a reason; every open cell's six faces inside the model (or
open to the sky over the ravine, or to the pit at the mouth); every water and lava cell bounded; and from the mouth,
a walk, swim and fall search that starts on the Deep's floor in front of the face, reaches the apron, and finds **0
traps**, every one of 65,661 floor cells reachable, and no floor beside lava without a lip; and **no cell of the cave
inside the Deep's pit** but the mouth tunnel.

## What was run on staging

The retired spine and regions and the earlier cuts of the cave put back to rock by a staging-only clear pack (41
functions); the cave carved (177 functions, 223,997 commands); **all 1,936,430 model cells match the saved world**
(`vr_caves.py verify`); the 80 Habitat Blocks present (`habitat_blocks.py verify --rcon`) and all 11 pools resolved
after a restart; the Digger in the Cut's core cavern, exactly one; the mouth probed open from the pit floor.

**A defect found and repaired on 2026-09-24.** The first cut let a cavern be scattered into the mouth strip, and its
ragged outline spilled 35 blocks out into the open pit in front of the Deep's north face: 15,473 blocks of cave rock
inside the pit (x3484-3588, z3065-3100, y-4 to 29). Every check passed, because each looked only at the cave, and the
walk-out began inside the tunnel. It was found by checking the spawns. The tool now keeps every cavern 6 or more from
the pit and checks it, and the walk-out begins on the pit floor. The pit was restored by re-running the Deep's own
functions for the damaged tiles: replayed from those functions, the box's 122,800 cells now differ from them in 0.

## Not verified

That the Habitat Blocks spawn their pools in sealed rock at their bands (EXP-033; the owner's report of strong
species in the regions is the first evidence they do); what spawns in the seams; that the finds are granted, the TM
teaches Overheat and the Digger's grant runs once; two players; how the lava falls behave once ticked; and that a
real player can walk out, which the search models but does not prove.

Re-applied after an export by `tools/reapply.py` R9C (the cave), R9E (the Habitat Blocks) and R9F (the Digger).
