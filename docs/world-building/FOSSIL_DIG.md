# The Scorchbone Dig

A fossil dig on the scorched plateau's west mesa (sub-region `plateau_west`, tier 8), built for the owner's request of
2026-10-06 ("its kind of empty") and for the obtainability sweep's P0 row: 14 of 15 Cobblemon fossils had no supply in
this pre-generated world. Record `data/fossil_dig.json`; generator `tools/fossil_dig.py`; pack
`build/datapacks/cobblers_fossil_dig`; builder's tests `tests/test_fossil_dig.py`. Every coordinate below is the
generator's output on the canonical heightmap (`python tools/fossil_dig.py report`, 2026-10-05). Nothing here has been
run in a world.

## What the jar says (read 2026-10-05, Cobblemon-fabric-1.8.0+1.21.1.jar)

- Fossils are archaeology loot. `data/cobblemon/loot_table/fossils/{common,uncommon,rare}/*.json` are all
  `"type": "minecraft:archaeology"`. `rare/<name>.json` is one pool, one roll, one entry: the one fossil.
  `uncommon/prehistoric_*.json` hold 4 fossils at weight 2 each among 39 to 57 total weight, plus held and evolution
  items (Razor Fang, Prism Scale, Deep Sea Tooth/Scale, King's Rock, Black Augurite, Never-Melt Ice ...). `common/`
  holds no fossil.
- `data/cobblemon/tags/item/fossils.json`: the 15 fossil items (helix, dome, old amber, root, claw, skull, armor,
  cover, plume, jaw, sail, and fossilized bird, fish, drake, dino).
- There is no item called a Resurrection Machine. `tags/item/fossil_machine_parts.json` names
  `cobblemon:fossil_analyzer`, `cobblemon:restoration_tank`, `cobblemon:monitor`. Recipes: the Analyzer takes cobbled
  deepslate, amethyst (`c:gems/amethyst`), iron, glass, redstone; the Tank takes iron, glass, `cobblemon:revive`, a
  composter; the Monitor takes iron, glass, copper, a redstone torch.
- Inputs: Sableye drops 0-2 amethyst shards and Glimmet 0-1 (species JSON `drops`), both in `data/spawns.json`. A
  Revive is in seven `data/rewards.json` grant lines, and cooks from heal powder plus a honey bottle in the campfire pot
  (`campfire_pot/revive.json`). Honey is sold at four stalls. The brush is vanilla-craftable and sold at
  `cinderlee_core_shed` and `dig_stores` (`data/markets.json`). **The machine is obtainable; no stall line was added.**
  If amethyst by drops proves too thin in play, the cheapest fix is one `minecraft:amethyst_shard` line at Redbrow
  (`tableland_stop`). It is not built.

## Choices

- **Seam block `minecraft:suspicious_gravel`, not sand.** `suspicious_sand`, `sand` and `red_sand` are Cobblemon spawn
  conditions (`data/spawn_blocks.json`: Sandygast, Palossand, herds). Gravel is not.
- **Rare tables only.** Each seam gives exactly one fossil and nothing else, so the dig opens no renewable source of
  evolution items. The two `galar_*_fossils` tables are left out because they only repeat the fossilized halves.
- **Shared, not per player.** A suspicious block is a world block, and the first player to brush it gets the fossil.
  Per-player supply would need per-player state that the block cannot hold. The period is the knob.
- **No Habitat Block.** Fossil Pokemon are restored here, not caught, and a nest would only add a leash to keep clear.
- **The foreman is seated by `data/npc_seats.json`** (R17N, the Arrow Creeks farmer's way), so he needs no reapply step
  of his own.

## What the build writes

Site centre (4183, 5623), ground y142. Local offsets are from the centre (lx east, lz south).

**Pit** (floors are the top solid block; air from floor + 1 up to each column's own ground):

| level | local rect | world rect (x, z) | floor y |
|---|---|---|---|
| upper | -12,-8 .. 12,8 | 4171,5615 .. 4195,5631 | 140 (lowest ground under the rect, 141, minus 1) |
| middle | -9,-5 .. 10,5 | 4174,5618 .. 4193,5628 | 138 |
| bed | -6,-2 .. 8,2 | 4177,5621 .. 4191,5625 | 136 (plus a strata course at y135 under it) |

- Floors: coarse dirt and terracotta (fixed by position). About one middle-floor cell in nine is a flush bone block.
- Risers: every upper cell within 2 (Chebyshev) of the middle rect is strata at y138..139, and every middle cell within
  2 of the bed rect is strata at y136..137. Strata block = `strata[(y // 2) % 7]` over terracotta, orange, yellow,
  brown, white, red and light grey terracotta.
- Outer skin: a ring one block wide round the upper rect, strata from y140 up to that column's ground.
- Stairs (spruce, facing west, ascending west, at z 5623): (4171,142), (4172,141), (4174,140), (4175,139), (4177,138),
  (4178,137), each with strata under it.
- Bones on the bed: spine `bone_block[axis=x]` at y137 for x 4180..4189, z 5623; ribs `[axis=z]` at y137 for x
  4182/4184/4186/4188, z 5622 and 5624; skull at (4190, 137, 5622..5624), (4191, 137, 5623) and (4190, 138, 5623);
  tail flush in the floor at (4179, 136, 5623).

**Seams** (`suspicious_gravel{LootTable:"cobblemon:fossils/rare/<name>"}`, armed by the build with the fossil shown):

| face | seams (x, y, z) and the fossil the build arms | restore box (face bounds) | offset |
|---|---|---|---|
| north_upper | (4180,139,5617) helix, (4184,139,5617) dome, (4188,139,5617) old amber | 4180,138,5616 .. 4188,139,5617 | 0 |
| east_upper | (4194,139,5620) root, (4194,139,5623) claw, (4194,139,5626) skull | 4194,138,5620 .. 4195,139,5626 | 6000 |
| north_lower | (4183,137,5620) armor, (4186,137,5620) cover, (4189,137,5620) plume | 4183,136,5619 .. 4189,137,5620 | 12000 |
| south_lower | (4182,137,5626) jaw, (4185,137,5626) sail, (4188,137,5626) bird | 4182,136,5626 .. 4188,137,5627 | 18000 |

Each seam sits one above the lower floor. It is open to the pit on its pit side, has its band's strata under it and
behind it, and has the upper floor over it.

**Camp, lanterns, signs** (each seated on its own ground + 1 unless stated):

- Tents (white wool A-frames, open both ends, ridge along z) at x 4159..4163, z 5612..5616 and z 5630..5634. Each
  stands on a coarse-dirt platform up to the highest ground under it (y141), canvas at y142..144, a barrel at
  (4160, 142, z1-1) and a hanging lantern at (4161, 143, mid z).
- Sieves are scaffolding at (4166, 5618) and (4166, 5620). The spoil is gravel at (4167, 5618) and (4167, 5619). The
  tub is a cauldron at (4166, 5619).
- The sorting table is three top spruce slabs at x 4166, z 5625..5627, at the highest ground + 1. A decorated pot
  stands on the first slab and a skeleton skull on the last.
- The finds board is spruce planks at x 4164, z 5622..5624, two high. Four spruce wall signs face east at x 4165 (three
  at y143 and one at y142).
- An entrance standing sign (rotation 4) is at (4169, 143, 5625).
- Lanterns (`hanging=false`) stand on two-high spruce fence posts. Four are at the rim corners (4169/4197, 5613/5633),
  four in the middle level's corners (4174/4193, 5618/5628), two on the bed ((4177, 5621), (4191, 5625)) and two at
  the camp ((4162, 5623), (4165, 5629)).
- The only entity is the foreman, Hollis Quarne, `cobblers:npc_fossil_dig_foreman`, at (4168, 143, 5621), yaw -90.
  R17N places him from `data/npc_seats.json`. The pack writes no entity.

**Clearing** (first in the build): `fill ... minecraft:air replace` over `#minecraft:logs`, `#minecraft:leaves`,
`#minecraft:replaceable`, `minecraft:cactus`, `minecraft:dead_bush` in the box x 4156..4200, y 142..150, z 5609..5637.

**Order in `build`**: the clearing, then every air write top down (so the mesa's red sand never falls into the cut),
then every solid block bottom up, then hung blocks (lanterns, signs) top down. Last, each face's clock is set (face
due at build time + offset), and then `#built fd.t = 1`. `function_limits.ensure_loaded` wraps the build in
forceloads. The reapply step (proposed **R9FD**, not wired: `tools/reapply.py` is not edited) is
`placement_steps()`: `forceload add 4156 5609 4200 5637`, wait 3, `function cobblers:fossil_dig/build`, then
`forceload remove`. The step's order against R9E does not matter (it writes no Habitat Block). The pack must also be
installed with the other world packs, because its `load` and `tick` tags run the restore.

## The restore rule

- The `tick` function counts `#clock fd.t` every tick. Every 100 ticks it runs `drive`, which returns unless
  `#built fd.t = 1`, reads game time into `#now`, and runs `site` only if a player is inside the approach box
  x 4132..4243, y 120..171, z 5568..5675 (the face bounds grown by 48 across, 16 down and 32 up).
- `faces/check_<face>` returns if `now - last < 24000` (1,200 s). It also returns unless all four corners of the face
  box grown by 1 are loaded, if any player stands in that box, or if any `cobblemon:pokemon` stands in it. Otherwise it
  runs `faces/restore_<face>`.
- `faces/restore_<face>` writes one `fill <cell> <cell> <band> replace #cobblers:fossil_dig_rearm` for each support,
  backing and between cell (10 to 12 per face). It then calls `faces/seam_<face>_<k>` for each seam and sets
  `last = now`.
- `faces/seam_<face>_<k>`: `execute unless block <seam> #cobblers:fossil_dig_rearm run return 0`, then
  `random value 0..14`, then 15 guarded `setblock <seam> minecraft:suspicious_gravel{LootTable:...}`, one per rare
  table.
- `#cobblers:fossil_dig_rearm` = air, cave air, gravel. An unbrushed seam is not in it, so it keeps its fossil. A
  player's own block is not in it either, and survives.
- Yield: 12 seams, at most 12 fossils per full cycle. After an idle spell longer than the period, all four faces come
  back on the first approach. There is no sibling rule.

## What an audit must check

Recompute everything from the heightmap (`tools/ground.py`) and the record's offsets. Do not import
`tools/fossil_dig.py` (CLAUDE.md, "How to prove an audit is independent"). Replay the built `build.mcfunction` and the
restore functions.

1. **Palette.** Every block written (build and restore) is in `blocks.ids`. None is a spawn condition in
   `data/spawn_blocks.json`. No chest, bed, light, water, bubble column or lava.
2. **Ground.** Floors are 140/138/136: the upper floor is the lowest rounded ground under the upper rect minus 1, and
   each inner floor is 2 below the one round it. Every pit column is air from its floor + 1 to its own ground. Camp
   pieces sit on their own ground + 1 (tents on their platform max).
3. **Gravity.** No air write comes after a lower air write. No gravity block (gravel, suspicious gravel) is written
   over air or over another gravity block. Each seam's support is non-gravity and solid.
4. **Seams.** There are exactly 12, at the coordinates above. Each is `suspicious_gravel` with a `LootTable` that
   resolves in the Cobblemon jar to an archaeology table whose only entry is one of the 15 tagged fossils. The 15
   restore tables cover all 15 fossils. Each seam is exposed on its pit side (air), one above the lower floor, with the
   upper floor over it.
5. **Restore safety.** Every restore write is either `fill ... replace #cobblers:fossil_dig_rearm` or a `setblock`
   behind `execute unless block ... #cobblers:fossil_dig_rearm run return 0`. The tag does not hold
   `suspicious_gravel`. Every restored cell lies inside the guard box (face bounds + 1) that the check function tests
   for `@a` and `@e[type=cobblemon:pokemon]`. The four loaded corners are that box's corners. The period is at least
   12,000 ticks. Each band the restore writes equals the block the build wrote there.
6. **Driver.** `load`/`tick` tags name `cobblers:fossil_dig/load` and `/tick`. `drive` is gated on `#built`. The
   approach box contains every face box. The build sets `#built` after its last write.
7. **Siting** (from other files' data, not the record's claims). Every column of the clear box must be:
   - at least 128 from every `data/route_paths.json` point (measured 259, `route_08_blaine_to_giovanni`);
   - at least 96 from every route corridor box (172);
   - at least 96 from any x/z another `data/*.json` authors, excluding region polygon vertices (167: the Mega farm
     keep-out box corner);
   - outside the Mega farm keep-out box, every town footprint + 96, and every Rift zone box;
   - beyond every activated Habitat Block's `spawn_range` (283).
   Neighbours measured from the clear box: Hornwall (`data/resident_encounters.json`, (4148, 5872), leash 34) is 235;
   the Mega field polygon (`data/gulch_mine.json`) is 212; Redbrow's centre is 682.
8. **Foreman.** The `data/npc_seats.json` seat `npc_fossil_dig_foreman` is (4168, 143, 5621), on ground y142, with two
   blocks of air in the plan. `dlg_fossil_dig_foreman` compiles, and its cursor's allowed values are its node ids.
9. **Mutate the generator, not the record.** Examples: a restore fill without `replace`, a seam guard dropped, air
   written bottom up, a seam one block higher, a guard box not grown by 1. Each must fail the audit while
   `data/fossil_dig.json` is untouched.

**Not verified, and needs a running server:**

- that `setblock ... suspicious_gravel{LootTable:"..."}` keeps its table in 1.21.1 and brushes out the fossil;
- that brushing leaves plain gravel;
- that the restore fires on approach and not while someone stands on a face;
- that the foreman appears and talks;
- that the mesa's surface there is red sand or terracotta (the brief's relayed "badlands paint" was not measured: no
  world was read).
