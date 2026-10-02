# The Copperway Khan (south-east dunes)

A half-buried caravanserai in the south-east dunes: the last stop of Fossick's dead freight road. Authored
2026-10-02 for the owner's "the south needs places, not just creatures. Somewhere to find, something in it."

| | |
|---|---|
| Record | `data/dune_ruin.json` (hand) |
| Generator | `tools/dune_ruin.py build` writes `build/datapacks/cobblers_dune_ruin`; `report` prints the numbers, writes nothing |
| Audit | `tools/dune_ruin_audit.py`: independent, replays the build over the heightmap |
| Tests | `tests/test_dune_ruin.py`: generator mutations, records untouched |
| Re-apply | **R9DU** (block pass, BEFORE R9E) and **R18DU** (the salvager, after R17N) |
| Shared records | `data/habitat_blocks.json` `dune_ruin_undercroft_ward`; `data/spawns.json` habitat `dune_ruin_undercroft` and entry `habitat.dune_ruin_undercroft.cofagrigus`; `data/rewards.json` `dune_ruin_strongroom`; `data/dialogue.json` `dlg_dune_ruin_salvager`; `data/quests.json` `ambient_dune_ruin`; `data/progression.json` `quest.ambient_dune_ruin.salvager_cursor`; `data/system_contracts.json` C4 `dune_ruin_audit.py` |
| Status | not applied to any world |

## The place

The Copperway carried ore south from Fossick to the coast. Copperajah pulled its wagons; when the road closed they were
turned loose (Dustback, `data/resident_encounters.json`, is the last of them, 540 blocks west). The Khan was abandoned
with its master's store bricked up, and the dunes drowned it to the lintels. A salvager from Fossick has dug out one
hall. Nobody has opened the store.

## Site (measured 2026-10-02 from `tools/ground.py`)

- Centre **(6744, 6224)**, cell G7, sub-region `south_east_dunes` (region `eastern_dunes`).
- The ground is y148 at every column from x6725 to x6763 and z6202 to z6243 (heightmap 148.07 at the centre). The
  sand line is **S = y148** and the Khan's original floor is **F = y144** (S minus `khan.bury` 4).
- Dry: `tools/water_mask.py level_at`, sea level 62, no lake basin.
- Off the critical path. The nearest point of `data/route_paths.json` is route 8 at (6002, 5067), 1374 blocks away.
- It is clear of every footprint. Fossick's footprint edge is 395 blocks north. Dustback's anchor is 540 blocks away:
  I measured the relayed coordinate (6216, 6112), and the audit forbids any write within 4 blocks of an anchor. The
  desert sapling is 563 blocks away and `sky_assay_tor` 470. The Rift (x 4330 and below) and the gulch are far.
- **Seen and signposted from Fossick.** The Copperway's first milestone stands 16 blocks outside Fossick's south
  footprint edge and carries the road's sign. Each milestone after it is 36 blocks from the one before. The tower's
  lantern (y167, 19 blocks over the sand) comes within view distance from the seventh milestone onward.

## Bounding boxes (everything the pack writes)

| Part | min (x, y, z) | max (x, y, z) |
|---|---|---|
| The Khan (walls, gatehouse, tower, vault, posts) | (6728, 135, 6205) | (6760, 167, 6240) |
| The Copperway milestones | (6700, 143, 5844) | (6740, 153, 6169) |

The re-application force-loads x6699..6763, z5844..6243 (130 chunks) for R9DU.

## Features and where to fly

| Feature | Coordinates | Notes |
|---|---|---|
| Gate (outer face) | (6744, 149, 6207) | a 2-high passage at the sand line through the gatehouse; copper keystone (6744, 151, 6207) |
| Gatehouse | x6741..6747, z6207..6211, to y157 | solid, copper course at y156, merlons y157 |
| Gate lantern posts | (6741, 149, 6205), (6747, 149, 6205) | fence + lantern |
| Outer wall | 33 by 33, x6728..6760, z6208..6240 | footing y143, two courses over the sand (y149, y150), merlons y151 (one in five fallen) |
| Arcade | ring at 10 from the centre | 3-wide arches F+1..F+3 buried; lintels at y148 flush with the sand, chiseled keystones; roof y149 |
| Buried ranges | between the arcade and the outer wall | the dune's own sand, never written; roofs y149, one in seven gone |
| NW tower | x6728..6732, z6208..6212, to y164 | solid; copper cap y165-166; **lantern (6730, 167, 6210)** |
| Choked well-head | (6744, 149, 6224) ring | sandstone walls round the courtyard's middle |
| Salvager's trench | x6743..6745, z6230..6233 | steps y147, y146, y145, paving y144; lantern posts (6742, 149, 6229), (6746, 149, 6229); sign (6747, 149, 6229) |
| Trench arch into the hall | (6744, 145, 6234) | the only open arch |
| The hall (dug out) | x6735..6753, z6235..6239, floor y144, air y145-148 | three hanging lanterns (6738/6744/6750, 148, 6237); camp east, copper pile, smithing table |
| **Dessa Varn, salvager** | **(6749, 145, 6237)** | `dlg_dune_ruin_salvager`, R18DU |
| Company plate | (6735, 147, 6236) | "COPPERWAY CO. / MASTER'S STORE / no admittance" |
| **Bricked doorway** | (6734, 145..146, 6237) | plain sandstone in a chiseled frame: break it |
| Stair-head room | x6729..6733, z6235..6239, y145-148 | sealed; soul lantern (6732, 145, 6236) |
| Trapdoor + ladder | trapdoor (6730, 144, 6238); ladder (6730, 140..143, 6238) | down the vault's west wall |
| **The master's store (vault)** | x6730..6738, z6230..6238, floor y139, air y140-143, ceiling y144 | sealed; soul lanterns (6732/6736, 143, 6234); four pillars; under_fill y135-138 |
| Habitat Block (Cofagrigus) | (6734, 139, 6234) | activated, mimic smooth sandstone, spawn_range 4, max 4, cancel 7 |
| **Strongbox (the find)** | barrel (6738, 140, 6234) | cache `dune_ruin_strongroom`: trigger (6736..6738, 140..141, 6233..6235): Metal Coat, Reaper Cloth, 3 Dusk Balls |
| Master's plate | (6734, 141, 6230) | "J. ORME / master, Copperway / the last ledger / is closed" |
| Copperway milestones | (6700, 5845) (6704, 5881) (6709, 5917) (6713, 5953) (6718, 5989) (6722, 6025) (6726, 6061) (6731, 6097) (6735, 6133) (6740, 6169) | each on its own ground + 1, + 2; lanterns on the 1st, 3rd, 5th, 7th, 9th; sign on the first, (6700, 144, 5844) |

## How the player finds it

1. They leave Fossick southward and see the signed first stone: "THE COPPERWAY / to the Khan: / follow the / stones
   south". At night the lanterns on every second stone mark the road.
2. Along the road the copper-capped tower, with its lantern, comes into view. Then the low walls, two blocks over the
   sand, and a gatehouse.
3. The player crouches through the half-buried gate into a courtyard of sand. Lintels and the arcade roof show at the
   sand line. Lantern posts mark a trench.
4. The trench leads down into the dug-out hall and Dessa Varn. She talks about the Khan, the haulers ("One didn't.
   You'll know him if you meet him."), the master's store ("somewhere cool and down"), and the west wall: "bricked up
   by somebody in a hurry ... At night, something on the other side knocks back."
5. The company plate hangs over the bricked doorway. The player breaks it, finds the trapdoor in the sealed room and
   goes down the ladder into a vault lit by soul lanterns. Cofagrigus are there, and so is the strongbox.

## Design decisions

- **The generator writes no sand.** Sand is a spawn condition (Sandygast and Palossand, `data/spawn_blocks.json`).
  The ground here is the desert's sand already, so the buried rooms, the courtyard and the gate's lower half are left
  as the dune's own ground. The build writes only masonry, carved air and dressing. Where the dune lay under the sand
  line inside a roofed room or an arch, it would write sandstone "packed drift" so that no dark gap is left. On this
  site that case is empty, because the ground is flat at S.
- **Lighting.** The place is lit as a town, with lanterns on posts and lanterns from the roof. The two sealed rooms are
  lit with soul lanterns: dark by their story, but with block light of at least 1 everywhere. The audit computes this
  light, so no hostile mob spawns there.
- **The tower is solid.** A hollow, dark tower would breed monsters.
- **No chest and no bed.** A chest is a Gimmighoul condition and a bed would set a respawn point. The strongbox is a
  barrel, used as scenery. The reward is the ADR-002 cache.
- **Cofagrigus at levels 43-53.** This is the band of the sub-region (tier 8). Ghost is one of the desert theme's
  types. Yamask evolves at 34, so every Cofagrigus in the band is past its evolution. The 2.1-block hitbox fits the
  4 blocks of air.
- **Vanilla 1.21.1 blocks only.** No mod dependency is added. The copper is waxed and oxidized.

## World probes

Run these over RCON on a server holding the applied world, after R9DU, R9E and R18DU. Each `execute if` line should
succeed. If it reports "Test failed", the expectation is wrong for that cell. The Habitat Block line assumes R9E ran.

```
execute if block 6744 149 6207 minecraft:air
execute if block 6744 150 6207 minecraft:air
execute if block 6744 151 6207 minecraft:waxed_oxidized_cut_copper
execute if block 6741 156 6207 minecraft:waxed_oxidized_cut_copper
execute if block 6741 150 6205 minecraft:lantern
execute if block 6736 148 6214 minecraft:chiseled_sandstone
execute if block 6737 148 6214 minecraft:cut_sandstone
execute if block 6737 149 6214 minecraft:smooth_sandstone
execute if block 6728 150 6224 minecraft:cut_sandstone
execute if block 6730 160 6210 minecraft:cut_sandstone
execute if block 6730 166 6210 minecraft:waxed_oxidized_cut_copper
execute if block 6730 167 6210 minecraft:lantern
execute if block 6744 147 6230 minecraft:sandstone_stairs
execute if block 6744 145 6232 minecraft:sandstone_stairs
execute if block 6744 144 6233 minecraft:smooth_sandstone
execute if block 6744 145 6234 minecraft:air
execute if block 6742 150 6229 minecraft:lantern
execute if block 6747 149 6229 minecraft:acacia_sign
execute if block 6744 144 6237 minecraft:smooth_sandstone
execute if block 6744 146 6237 minecraft:air
execute if block 6750 148 6237 minecraft:lantern
execute if block 6744 149 6237 minecraft:smooth_sandstone
execute if block 6749 145 6237 minecraft:air
execute if block 6749 146 6237 minecraft:air
execute if block 6734 145 6237 minecraft:sandstone
execute if block 6734 146 6237 minecraft:sandstone
execute if block 6734 147 6236 minecraft:chiseled_sandstone
execute if block 6735 147 6236 minecraft:acacia_wall_sign
execute if block 6732 145 6236 minecraft:soul_lantern
execute if block 6730 144 6238 minecraft:acacia_trapdoor
execute if block 6730 141 6238 minecraft:ladder
execute if block 6734 141 6234 minecraft:air
execute if block 6732 143 6234 minecraft:soul_lantern
execute if block 6738 140 6234 minecraft:barrel
execute if block 6734 144 6234 minecraft:smooth_sandstone
execute if block 6734 141 6230 minecraft:acacia_wall_sign
execute if block 6734 135 6234 minecraft:sandstone
execute if block 6734 139 6234 cobblemon:habitat_block
execute if block 6700 143 5845 minecraft:chiseled_sandstone
execute if block 6700 144 5845 minecraft:cut_sandstone
execute if block 6700 145 5845 minecraft:lantern
execute if block 6700 144 5844 minecraft:acacia_wall_sign
execute if block 6740 148 6169 minecraft:chiseled_sandstone
```

The Habitat Block line uses `cobblemon:habitat_block`, the block id `tools/habitat_blocks.py` writes.

Entity checks (with a player within simulation distance, so the chunks tick):

| Selector | Expect |
|---|---|
| `execute if entity @e[type=cobblemon:npc,x=6749,y=145,z=6237,distance=..1.5]` | 1 (Dessa Varn, after R18DU) |
| `execute if entity @e[type=cobblemon:pokemon,x=6730,y=140,z=6230,dx=8,dy=3,dz=8]` | 1 to 4 Cofagrigus (after R9E, a player nearby; refills on TICK) |
| `execute if entity @e[type=cobblemon:pokemon,x=6735,y=145,z=6235,dx=18,dy=3,dz=4]` | 0 before the door is broken (nothing leaks into the hall) |

## Not verified

- No server ran any of it. Not verified: that the fills land, that the world's ground under the Khan is sand (the
  heightmap gives the height of the ground, not its block), that Cofagrigus spawn in the vault and stay, that the cache
  grants, and that the salvager appears and talks.
- The step order comes from the source: the test checks that R9DU comes before R9E and R18DU after R17N. In a
  worktree `tools/reapply.py plan` and `steps()` cannot run, because they need `derived/` and a prepared `build/`. The
  integrating session should run `python tools/reapply.py plan | grep -E "R9DU|R18DU"`.
- `tools/encounter_audit.py` needs `derived/availability.json` and was not run. `build_encounters --check` is
  identical, and `compile_spawns` emits `habitat_pools/dune_ruin_undercroft.json`.
