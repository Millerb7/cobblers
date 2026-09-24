# EXP-033: a Habitat Block in sealed rock: replace, level band, vertical reach

## Objective
Victory Road's five regions each carry their roster on a `ReplaceSpawns` Habitat Block in a sealed room at depth.
EXP-021 proved replace-not-add and that the measured horizontal edge is the configured `RangeOfInfluence`, but on
roughly level ground in a crater bowl, along one axis, and it never looked at levels. Three things the regions rest
on are therefore unmeasured:

1. **Sealed rock.** Does the block replace the ambient pool in a room with no sky, deep underground, where the
   ambient pool is the upstream cave pools?
2. **Level band.** Do spawns take the pool's `levelRange` (50-59 here), or something else?
3. **Vertical reach.** Is the influence a sphere (as the source suggests) or a column? A region stacked over or under
   another space needs to know.

If replace fails in sealed rock, the regions need a different roster mechanism, and the build stops there.

## Success criteria
- At S1 and S2 `/checkspawn common` and `/checkspawn uncommon` list only `cobblers:rift_depths` species (Rolycoly,
  Roggenrola, Nacli, Glimmet / Baltoy, Golett), and at S3 none of them.
- `/spawnpokemonfrompool 5` at S1 spawns Pokemon of levels 50-59 only.
- V1, V2, V3 each show either the pool or not, so the shape of the influence can be read off (sphere: V1 yes, V2 no,
  V3 no; column: V1 yes, V2 yes, V3 no).

## Setup
Staging server, world `cobblers-runtime-proof/dryrun9/cobblers-dryrun9`, Cobblemon 1.8.0+1.21.1, the full server
stack. The pool is the installed global pack `cobblers_spawns`, whose `habitat_pools/rift_depths.json` is
byte-identical (sha256 `048864402d328c01...`) to a fresh `tools/compile_spawns.py` run on 2026-09-23. Never the live
world.

`rig.py` prints the commands; they were sent over RCON on 2026-09-23 under the coordination lock. The rig is:

- a room 41 x 41 x 11 (air y20-30) centred on (3470, 20, 2880), floor y19, inside a shell of
  `legendarymonuments:distortion_deepslate` 2 blocks thick on every face, including the roof (y31-33);
- 52 blocks of rock over the shell (heightmap), and at least 33 blocks of rock between the shell and Victory Road's
  corridor, its rooms, all five planned region sites and the Windward Deep's pit;
- one Habitat Block at (3470, 20, 2880): natural, `ReplaceSpawns:1b`, `RangeOfInfluence:16`,
  `PoolId:"cobblers:rift_depths"` (band 50-59, unlike the upstream cave pools around it: Gastly 6-31, Gible 24-30);
- three sealed 3 x 3 x 3 pockets stacked 5 blocks south of the block, feet at 13, 17 and 23 above it;
- crying obsidian under every stand, shroomlight so the rooms can be seen.

The rig is not campaign content: it is not in `data/habitat_blocks.json`, has no reapply step, and a re-export erases
it.

## Procedure (the owner, in game; about five minutes)

Every spawn test needs a player: `/checkspawn` is refused from the RCON console in every argument form, because the
bucket argument needs a player context.

```
python experiments/EXP-033-habitat-sealed-chamber/rig.py --stands
```

| Stand | Teleport | Where | Expect |
|---|---|---|---|
| S1 | `/tp @s 3470 20 2883` | 3 from the block, room floor | the pool, alone |
| S2 | `/tp @s 3470 20 2893` | 13 out, room floor | the pool, alone |
| S3 | `/tp @s 3470 20 2899` | 19 out, past the range | the ambient cave pool, no `rift_depths` species |
| V1 | `/tp @s 3470 33 2885` | 13 above, 5 south, sealed pocket | inside a sphere (13.9) and a column |
| V2 | `/tp @s 3470 37 2885` | 17 above, 5 south, sealed pocket | outside a sphere (17.7), inside a column |
| V3 | `/tp @s 3470 43 2885` | 23 above, 5 south, sealed pocket | outside both |

At each stand: `/checkspawn common`, then `/checkspawn uncommon`, and note the species. At S1 only, also run
`/spawnpokemonfrompool 5` (alias `/forcespawn`; both are in the 1.8.0 jar) and read the five levels. Then
`/kill @e[type=cobblemon:pokemon,distance=..30]`.

## Observed so far (headless, 2026-09-23)

- The carve applied in full (every `fill` and `setblock` reported success). The shell fills changed 7,200 of 18,225
  and 6,400 of 16,200 blocks, and the pocket column none: the rock there was already `distortion_deepslate`, which
  is the Rift's own skin, so the shell sits in the material it replaced.
- After the forceload was released and the chunk loaded again, `data get block` returned `DisplaySpecies` with all 12
  `rift_depths` species. EXP-021 found `DisplaySpecies` empty on a command-placed block until its chunk reloads and
  filled once the block is active, so **the block is placed and has resolved its pool**.
- The blockstate reads `facing=north, activated_style=false, cancels_regular_spawns=true`. The first
  `execute if block ...[cancels_regular_spawns=true]`, sent in the same RCON batch that reloaded the chunk, returned
  `Test failed`; every probe after it (true passes, false fails, unless-true fails) agrees on `true`. Recorded as a
  transient at load, not explained.

**Not verified:** all three questions. Replace in sealed rock, the level band and the vertical shape need the owner at
the stands above.

## Result
Pending the owner's run.
