# EXP-021: Habitat Blocks: replace or add, radius, persistence, stacking

## Objective
Decide whether Cobblemon 1.8's natural Habitat Block can carry a place's encounter identity, or only an
event site. Four questions: does `ReplaceSpawns` filter the ambient pool or add to it; what is the influence
radius as measured; does a placed block survive a chunk reload, a restart and a re-export; and do two blocks
with different rosters combine where their ranges overlap.

## Success criteria
- `/checkspawn` beside a block lists the block's roster and nothing else (replace), and at the same spot with
  the block removed lists the default pool.
- The distance where the roster leaves the table is observed, not taken from configuration.
- After a chunk unload, a full restart and a re-export, the block's NBT and blockstate read back unchanged and
  the table beside it is still the roster.
- The overlap between two blocks is observed and described.

## Dependencies
Cobblemon 1.8.0+1.21.1 (jar sha256 `a6228f32…`), the full COBBLEVERSE server stack, the compiled Habitat pools
from `tools/compile_spawns.py` installed as the world datapack `cobblers_spawns` (`cobblers:great_crater_bowls`,
`cobblers:route_1_ghost_mansion`). Disposable world `cobblers-runtime-proof/spawnproof`, seeded from the
offline snapshot `2026-09-17-pre-grass`; never the live world. One player in creative (an operator account).

## Implementation
Blocks are placed from data by two commands, with no GUI:

```
setblock <x> <y> <z> cobblemon:habitat_block[cancels_regular_spawns=true,activated_style=false] replace
data merge block <x> <y> <z> {SpawningStyle:"cobblemon:natural",ReplaceSpawns:1b,RangeOfInfluence:24,PoolId:"cobblers:great_crater_bowls"}
```

Reading the block back gives `SpawningStyle`, `RangeOfInfluence`, `ReplaceSpawns`, `PoolId`, `MimicId`, `Modifiers`,
`PhaseOrder` and, once the pool has been resolved, `DisplaySpecies`. In the bytecode, `HabitatBlockDetector`
finds blocks through the vanilla POI manager (`CobblemonPoiTypes.HABITAT_BLOCK`). No world-level saved data is
involved: the world `data/` directory has no Cobblemon habitat file.

Site: open forest at (1746, 109, 4815), outside every route box, where an earlier 8-minute sample
(`spawns_outside_route01`) recorded only default spawns. The second block is at (1776, 109, 4815), 30 blocks east.

## Test instructions
1. Boot the disposable world. Place block A (crater, range 24) with the two commands above.
2. **Activate it:** move the player far enough away that the chunk unloads (`execute if loaded` fails), then back.
   Check that `data get block … DisplaySpecies` is non-empty.
3. With the player 2 blocks from A, run `/checkspawn common` and `/checkspawn uncommon`. Replace A with
   `grass_block`, and at the same spot run both again.
4. Re-place A, repeat step 2, then run `/checkspawn common` at 16, 24 and 32 blocks east.
5. **Persistence:**
   - `save-all flush`, `stop`, boot, then read the block back.
   - **Re-export:** with the server stopped, copy the block's region file `r.3.9.mca` from the export snapshot,
     move `poi/r.3.9.mca` aside, boot and read the block back. Stop, run
     `tools/transplant_chunks.py --from <saved copy of the chunk> --to <world> --blocks 1744 4800 1759 4815`,
     boot, then read back and run `/checkspawn` beside the block.
6. **Stacking:** place block B (ghost mansion, range 24) 30 blocks from A and activate it as in step 2. Run
   `/checkspawn` at the midpoint (15 from each), then 6 blocks from A and 6 from B, each on the far side from
   the other block.

## Results
Run 2026-09-17, player screenshots of `/checkspawn` output.

**Replace, not add.** `/checkspawn` 2 blocks from block A:

| Bucket | Block on | Block replaced with grass (same spot) |
| --- | --- | --- |
| common | Slugma 30%, Numel 30%, Torkoal 20%, Salandit 20% | the full default pool (herds, Meowth, Zigzagoon, Glameow, Rattata …), no crater species |
| uncommon | Magcargo 26.67%, Camerupt 26.67%, Sizzlipede 26.67%, Rolycoly 20% | the full default pool (Electrike herd, Drifloon herd, Plusle-Minun herd …) |

These are the pool's authored weights. With the block on, no default species appears in either bucket.

**Radius, measured with `RangeOfInfluence` 24.** At each distance east of the block:

| Distance | `/checkspawn common` |
| --- | --- |
| 2 | crater only |
| 16 | crater only |
| 24 | mixed: crater 2.72/2.72/1.81/1.81% plus the default pool |
| 32 | default only, no crater species |

The effective edge is the configured value. `/checkspawn` scores spawn positions around the player, which
blurs the edge by a few blocks either side, so the mix at 24 is expected.

**A block placed by command is inert until its chunk reloads.** Straight after `setblock` and `data merge`, the NBT
reads back correctly but `DisplaySpecies` is empty and the table beside the block is the default pool. After
one unload and reload (the player moved 4,000 blocks away, and the chunk unloaded within 5 s),
`DisplaySpecies` is filled and the block replaces the pool. A block that loads from disk (restart,
transplant) is active at once.

**Persistence.**

| Event | Block |
| --- | --- |
| Chunk unload and reload | survives, active |
| Full restart (`save-all flush`, `stop`, boot) | survives: NBT and blockstate identical, `DisplaySpecies` resolved |
| Re-export, simulated: the chunk's region file replaced by the export snapshot's, POI moved aside | **gone** (`data get block`: "not a block entity") |
| Carried with `tools/transplant_chunks.py` (region + POI, 1 chunk) | **restored**: NBT and blockstate identical, and the table beside it is crater only (the step 3 "block on" rows were read on this transplanted block) |

A WorldPainter export regenerates region files from the `.world` project, which never contains blocks placed in
game. That makes the loss certain, not a test artefact. A block survives a re-export only if it is carried
(transplanted chunk) or re-placed from data (the two commands plus one chunk reload).

**Stacking: overlapping ranges cancel.**

| Position | common | uncommon |
| --- | --- | --- |
| Midpoint, 15 from A and 15 from B | "Nothing can spawn here right now" | "Nothing can spawn here right now" |
| 6 from A, 36 from B | crater (Slugma 30, Numel 30, Torkoal 20, Salandit 20) | crater (Magcargo, Camerupt, Sizzlipede 26.67, Rolycoly 20) |
| 6 from B, 36 from A | Gastly 33.33, Misdreavus 33.33, Shuppet 16.67, Duskull 16.67 | Litwick 50, Phantump 50 |

It was daytime for all three checks (the midpoint was checked first, and the two single-block checks followed
within minutes). Neither pool has a time condition, and both blocks work alone, so the empty midpoint comes from
the overlap. Each `ReplaceSpawns` block appears to cancel the other block's pool as well as the default one.

## Limitations
- Measured with `/checkspawn` only, not a count of actual spawns; the spawn sample in EXP-012 is the
  actual-spawn check for route pools.
- One range value (24) along one axis, on roughly level ground. Vertical reach, other ranges and a spherical
  versus horizontal edge are not measured.
- Fishing (`affectsFishing`) and the activated style are not tested.
- The re-export is simulated at one chunk. A real WorldPainter export was not run: its output cannot contain the
  block.
- The overlap was tested with two natural `ReplaceSpawns` blocks only. Overlaps with `ReplaceSpawns` off, and with
  an unequal range, are not tested.
- Single player.

## Decision
**Adopt Habitat Blocks as place identity, with rules:**
- A block replaces the ambient pool inside its range, so a set of blocks can carry a whole place (a cavern
  district, a crater bowl, a haunted grounds), not just an event.
- **Ranges must not overlap.** Tile a place with non-overlapping ranges, leaving no gap that shows the pool underneath,
  or use one block with a larger range.
- **Placement is data, not world state.** Record every block in `data/` (position, pool, range), place it with
  the two commands, then force one chunk reload. Re-apply after every re-export unless the chunk is transplanted.
- A place that must also sit on a route corridor still needs the EXP-012 route exclusion for the corridor
  outside the block's range.

## Follow-up
- A generated function that places every recorded block, with a check that no two ranges overlap.
- Measure vertical reach and a large range (for example 64) before designing cavern-scale tiling.
- Test fishing inside a block's range.
