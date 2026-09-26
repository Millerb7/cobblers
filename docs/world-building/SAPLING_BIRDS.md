# Sapling birds: one bird per world-tree sapling (proposal)

Status: **PLACED ON STAGING 2026-09-26 as nests; the block placement below is superseded.** Each sapling is now a
nest of its one species: activated Habitat Blocks in its trunk (three per elder at ground + 12, + 35, + 58, up to 7
birds alive each within 16 blocks; two in the Route 1 sapling, up to 10 each), `data/habitat_blocks.json`. The owner:
a player should "see and feel like a sapling belongs to a species", with "at least 20 ... spread vertically along the
tree". One species per tree: Route 1 is Pidgey only, `elder_viltris_path_valley_2` Farfetch'd only,
`elder_long_isle_south_3` Oricorio only (so C6 and decisions 5 and 10 are settled that way: no co-residents, owls and
crows by day too). The "Block y", "Range" and "How it would be built" steps 2-4 describe the retired natural blocks.

Earlier status: AUTHORED 2026-09-26, not placed. The owner approved it ("i like those birds ... add the birds"), and every
open decision took this document's recommendation, except two. The 52 elders are habitats `elder_*` in
`data/spawns.json` and Habitat Blocks in `data/habitat_blocks.json` (status `planned`). **Block height:** the first
storey, ground + 21, not the crown's ground + 57, because Cobblemon spawns within about 16 blocks of the player's
height (the parent session's decision). **Long Isle levels:** 44-50, not 25-30, because `LONG_ISLE.md` D5 moved the
island's band there, and this document's own rule then gives the band. Evolution thresholds are read from the
Cobblemon 1.8.0 jar, and every ‡ value below matched it. The tables below are the proposal as written. Asked by the owner on
2026-09-25: "i want to make each sapling in the world have a bird attached to it. can we go through each and map
them". The Route 1 sapling already has one (`route1_sapling_crown`: Pidgey 24 + Hoothoot 9 at 5-8).

Sources read: `derived/sites/elder_trees.json`, `derived/sites/tree_grove_foothill_woods.json`,
`derived/sites/world_tree_foothill_woods.json`, `data/spawns.json` (sub-region rosters, `evolution_policy`,
habitats `route_1_sapling_crown` and `tree_town_canopy`, `route_species_selection`), `data/habitat_blocks.json`,
`data/routes.json` (sub-regions per leg), `tools/tree_grove.py` (`TIERS`, `big_tree`), `tools/elder_trees.py`,
`kits/structures/prefabs/trees/tree_town/elder_oak_a.json`, `modpack/config/cobblemon/main.json` and
`starters.json`, `docs/story/ENCOUNTER_GAPS.md`.

## What was counted: 53 saplings

`tools/tree_grove.py` says it in so many words: "An elder is a world tree's sapling". So a sapling here is every
tree of the `sapling` or `elder` tier.

| Set | Trees | Source |
|---|---|---|
| The Route 1 sapling (tier `sapling`) | 1 | `tools/maze_forest.py` `SAPLING`, `data/habitat_blocks.json` `route1_sapling_crown` |
| Elders across the woods (tier `elder`) | 48 in 20 sub-regions | `derived/sites/elder_trees.json` `regions[].sites[]` |
| Elders of the Foothill grove (tier `elder`) | 4 | `derived/sites/tree_grove_foothill_woods.json` `elders[]` |
| **Total** | **53** | 48 + 4 = the 52 elders `docs/STATE.md` counts |

**Not counted** (not saplings): the world tree itself (crown y457-535); the grove's 7 **giants** (tier `giant`,
the future Tree Town's habitat trees, which already have a reserved pool, `tree_town_canopy`); and the 5 painted
giants (4 landmark trees and the Weeping Elder).

## How to read the tables

- **id**: stable and proposed. Elders are `elder_<subregion>_<n>`, with n in `elder_trees.json` site order.
  Grove elders are `elder_foothill_grove_<n>`, so they never collide with `elder_foothill_woods_<n>`.
- **(x, z, ground)**: x and z are the trunk centre (`elder_trees.py` seats the template on it). ground is
  `ground_y`, and the trunk base sits at ground+1.
- **Block y** = ground + 57. That is prefab height h56, the crown base. See "How it is built".
- **Band** is the sub-region's roster `level_band`. **Pool** is the proposed pool level. A band 10 or more wide
  (10-22, 15-28, 25-45, 34-44) is narrowed to min..min+5, so a signature tree never hands out the top of a wide band.
  This is owner decision 4.
- **Source**:
  - **R**: in this sub-region's roster.
  - **RG**: in another roster of the same region.
  - **N**: new to the area. N says where the species lives in the repo, or "no home" if
    `ENCOUNTER_GAPS.md` lists it with no authored home.
- **Stages**: follows `data/spawns.json` `evolution_policy`. A level evolution is eligible only when its threshold
  is at or below the pool's minimum. Stage splits are 0.75/0.25 for two stages and 0.70/0.23/0.07 for three.
  Thresholds come from the repo's `eligibility_reason` where a row exists. Otherwise they are mainline numbers,
  marked ‡ (ASSUMED, not read out of the 1.8.0 jar).
- **Rare find** (★): the pool is a common co-resident at weight 24 plus the signature bird at weight 2 (the repo's
  `rare` family weight). A pool of one species would spawn it every time, so the co-resident is what keeps it rare.

## The map, by region

### Pallet Fields: the Route 1 sapling (exists)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages | why |
|---|---|---|---|---|---|---|---|---|
| route1_sapling_crown | (1380, 4628, trunk base 123) | 147 (recorded) | sapling oak, maze forest | 5-8 / 5-8 | **Pidgey** 24 + Hoothoot 9 | R | base only (Pidgeotto 18 > 5) | Kept as built. It is the one tree the map starts with. |

### Viltri Woods (Routes 1-3, before Brock / Misty / Surge)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages at pool | why |
|---|---|---|---|---|---|---|---|---|
| elder_viltri_plateau_1 | (1730, 3960, 121) | 178 | birch / birch_plateau | 12-15 / 12-15 | **Fletchling** | RG (viltris_path_valley) | base only (Fletchinder 17‡) | 134 off leg 1/2: the first elder most players see. A small robin in the birches. |
| elder_viltri_plateau_2 | (2332, 3560, 118) | 175 | birch / birch_plateau | 12-15 / 12-15 | **Taillow** | N (no home) | base only (Swellow 22‡) | A meadow swallow. Guts is a real early pick. |
| elder_viltri_plateau_3 | (2344, 3064, 108) | 165 | birch / birch_plateau | 12-15 / 12-15 | **Spearow** | N (no home) | base only (Fearow 20‡) | Kanto's field bird, which the map never had. |
| elder_lake_viltri_hollow_1 | (1280, 3184, 110) | 167 | oak / riparian_woods | 18-21 / 18-21 | **Ducklett** | N (tilpey_north_shore 39-41) | base only (Swanna 35‡) | A lake bird in the lake's wood. Earlier than its roster home (conflict C3). |
| elder_lake_viltri_hollow_2 | (1824, 3056, 121) | 178 | oak / riparian_woods | 18-21 / 18-21 | **Hoothoot** | R | base only (Noctowl 20 > 18) | 60 off legs 2/3, the most visible elder in the region. The hollow's own owl. |
| elder_viltris_path_valley_1 | (1016, 3864, 138) | 195 | oak / riparian_woods | 15-28 / 15-20 | **Pidove** | N (no home) | base only (Tranquill 21‡) | A common pigeon for the far valley. |
| elder_viltris_path_valley_2 ★ | (1094, 3496, 122) | 179 | oak / riparian_woods | 15-28 / 15-20 | **Farfetch'd** (rare) over Fletchling 24 | N (no home) / R | single stage (Kanto form) | A remote riverside tree with a leek bird in the reeds: the first "find". |
| elder_foothill_woods_1 | (1440, 2264, 100) | 157 | oak / foothill_mixed | 21-23 / 21-23 | **Hoothoot** + Noctowl | R | Noctowl eligible (20 ≤ 21) | The roster's own pair in the region's biggest wood. |
| elder_foothill_woods_2 | (2912, 2440, 107) | 164 | oak / foothill_mixed | 21-23 / 21-23 | **Pidove** + Tranquill | N | Tranquill eligible (21‡ ≤ 21) | The Pidove line's second tree, now one stage on. |
| elder_foothill_woods_3 | (2236, 1622, 124) | 181 | oak / foothill_mixed | 21-23 / 21-23 | **Rufflet** | N to region (mt_clay; in Route 3's selection) | base only (repo marks Braviary non-level) | 207 off leg 3, under the Tri Peaks. The mountain eagle come down to the woods' edge. |
| elder_foothill_woods_4 | (2136, 2624, 117) | 174 | oak / foothill_mixed | 21-23 / 21-23 | **Spearow** + Fearow | N | Fearow eligible (20‡ ≤ 21) | Spearow's line grows up along the road. |

### Viltri Woods: the Foothill grove round the world tree (Route 3, 29.5 blocks off the road)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages at pool | why |
|---|---|---|---|---|---|---|---|---|
| elder_foothill_grove_1 | (2078, 2262, 118) | 175 | oak elder a | 21-23 / 21-23 | **Natu** | N (no home) | base only (Xatu 25‡) | The bird that stares at the sun, sitting under the tree that holds it up. Also the Koga answer (A5). |
| elder_foothill_grove_2 | (2034, 2330, 117) | 174 | oak elder b | 21-23 / 21-23 | **Pikipek** + Trumbeak | N to region (`tree_town_canopy`, jungle isle) | Trumbeak eligible (14 ≤ 21) | Foreshadows the Tree Town canopy pool reserved for these giants. |
| elder_foothill_grove_3 | (1958, 2294, 116) | 173 | oak elder c | 21-23 / 21-23 | **Pidgey** + Pidgeotto | N to region (pallet_fields) | Pidgeotto eligible (18 ≤ 21) | The Route 1 sapling's bird, one stage older, at its parent tree. |
| elder_foothill_grove_4 | (1958, 2234, 115) | 172 | oak elder a | 21-23 / 21-23 | **Swablu** | N to region (Route 3 selection) | base only (Altaria 35) | Cloud-winged birds at the foot of a tree whose crown is in the clouds. |

Rowlet was considered for the grove and left out: it is a starter (`starters.json`), and STATE puts the
starter-spread fix in coverage, not in more Grass. It stays on the Pine Isles, where it is rostered.

### Shrew Lakes (cherry vale; no bird in any Shrew Lakes roster)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages at pool | why |
|---|---|---|---|---|---|---|---|---|
| elder_shrew_lake_shores_1 | (3928, 4272, 144) | 201 | cherry / cherry_vale | 10-22 / 10-15 | **Swablu** | N | base only | Cotton wings among the blossom. |
| elder_shrew_lake_shores_2 | (3760, 3932, 140) | 197 | cherry / cherry_vale | 10-22 / 10-15 | **Natu** | N | base only | Sits beside the roster's Psychic cherry things (Ralts, Poltchageist). |
| elder_shrew_lake_shores_3 | (3104, 3624, 117) | 174 | cherry / cherry_vale | 10-22 / 10-15 | **Taillow** | N | base only | The region's plainest bird, at its lowest band. |

`shrew_lake_shores` is on no leg's `subregions` list in `data/routes.json`. Its elders are 326-599 blocks off some
leg that this pass did not identify.

### Northern Downs (Routes 4-5, Surge to Erika to Koga)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages at pool | why |
|---|---|---|---|---|---|---|---|---|
| elder_peak_pond_hollow_1 | (3912, 1776, 111) | 168 | spruce / old_growth_spruce | 30-32 / 30-32 | **Starly** + Staravia | RG (north_east_downs) | Staravia eligible (14). Staraptor 34 > 30 | 68 off a leg: a visible elder before Erika. Intimidate is an Erika answer. |
| elder_peak_pond_hollow_2 | (4008, 1040, 112) | 169 | spruce / old_growth_spruce | 30-32 / 30-32 | **Fletchling** + Fletchinder | RG (north_shore_downs) | Fletchinder eligible (17‡). Talonflame 35‡ | The first wild Fire/Flying, placed on the leg into Erika's Grass gym. |
| elder_peak_pond_hollow_3 | (4346, 2296, 114) | 171 | spruce / old_growth_spruce | 30-32 / 30-32 | **Rookidee** + Corvisquire | N to region (tri_peaks) | Corvisquire eligible (18). Corviknight 38 | The Galar crow in the old-growth spruce, 119 off a leg. |

### Marsh Country (near Route 6, Koga to Sabrina; no bird in any marsh roster)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages at pool | why |
|---|---|---|---|---|---|---|---|---|
| elder_marshy_marsh_1 | (4906, 1850, 110) | 167 | mangrove / drowned_swamp | 34-44 / 34-39 | **Flamigo** | N (arrow_creeks 49-56) | single stage | A flamingo in the mangroves. Earlier than its roster home (C3). |
| elder_marshy_marsh_2 | (5434, 2414, 128) | 185 | mangrove / drowned_swamp | 34-44 / 34-39 | **Bombirdier** | N (no home) | single stage | A Dark/Flying bird before Sabrina's Psychic gym (A6). |
| elder_marshy_marsh_3 | (5014, 2272, 111) | 168 | mangrove / drowned_swamp | 34-44 / 34-39 | **Cramorant** | N (no home) | single stage | Fishes the drowned swamp. A Water/Flying for Blaine and Giovanni. |

### Tilpey Lakeland (Routes 6-8)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages at pool | why |
|---|---|---|---|---|---|---|---|---|
| elder_tilpey_north_shore_1 | (5880, 3248, 96) | 153 | birch / birch_shore | 39-41 / 39-41 | **Ducklett** + Swanna | R | Swanna eligible (repo) | 74 off a leg on the lake shore: the roster's swan, placed where it is seen. |
| elder_tilpey_north_shore_2 | (5224, 3040, 117) | 174 | birch / birch_shore | 39-41 / 39-41 | **Starly** + Staravia + Staraptor | N to region (northern_downs) | both eligible (14, 34 ≤ 39) | The first wild Staraptor (7%). A Ground-immune pick for Giovanni. |
| elder_tilpey_east_shore_1 | (6848, 3792, 95) | 152 | oak / lakeside_copses | 41-43 / 41-43 | **Hoothoot** + Noctowl | RG (tilpey_south_shore) | Noctowl eligible | The lakeland's owl on the quiet shore. |
| elder_tilpey_east_shore_2 | (6488, 4776, 117) | 174 | oak / lakeside_copses | 41-43 / 41-43 | **Pidgey** + Pidgeotto + Pidgeot | N (pallet_fields) | both eligible (18, 36‡ ≤ 41) | 277 off legs 7/8. The Route 1 bird fully grown, the first wild Pidgeot (7%). |

### The Wedge (dark woods; band 25-45, the unbanded-wilderness default)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages at pool | why |
|---|---|---|---|---|---|---|---|---|
| elder_wedge_north_1 | (3846, 2912, 134) | 191 | dark oak / dark_wood | 25-45 / 25-30 | **Murkrow** | R | Honchkrow needs a Dusk Stone (C1) | The roster's crow in the ghost wood. |
| elder_wedge_north_2 | (4160, 3184, 142) | 199 | dark oak / dark_wood | 25-45 / 25-30 | **Natu** + Xatu | N | Xatu eligible (25‡ ≤ 25) | A watcher in the dark wood. The only wild Xatu (Koga answer). |
| elder_wedge_south_1 | (4784, 4408, 112) | 169 | dark oak / broken_oakwood | 25-45 / 25-30 | **Vullaby** | N (plateau_west 47-49) | base only (Mandibuzz 54‡) | Vultures over a broken wood. Much earlier than its roster home (C3). |
| elder_wedge_south_2 | (4692, 3896, 91) | 148 | dark oak / broken_oakwood | 25-45 / 25-30 | **Murkrow** | RG (wedge_north) | as above (C1) | The roster has no bird. This carries the north wood's crow south. |

### Northgate Isle (spruce thicket; remote, 1372-1778 off any leg)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages at pool | why |
|---|---|---|---|---|---|---|---|---|
| elder_northgate_west_1 | (4792, 272, 77) | 134 | spruce / spruce_thicket | 25-45 / 25-30 | **Hoothoot** + Noctowl | R | Noctowl eligible | The roster's night owl, here by day as well (C6). |
| elder_northgate_west_2 | (5250, 62, 70) | 127 | spruce / spruce_thicket | 25-45 / 25-30 | **Rookidee** + Corvisquire | N to isle (long_isle_north) | Corvisquire eligible | Crows in the northern taiga. |
| elder_northgate_east_1 | (5472, 432, 127) | 184 | spruce / spruce_thicket | 25-45 / 25-30 | **Starly** + Staravia | R | Staravia eligible. Staraptor 34 > 25 | The roster's starlings. |
| elder_northgate_east_2 | (5936, 840, 82) | 139 | spruce / spruce_thicket | 25-45 / 25-30 | **Taillow** + Swellow | N | Swellow eligible (22‡ ≤ 25) | The only wild Swellow. |

### Pine Isles (snow pine; remote, 1745-3418 off any leg)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages at pool | why |
|---|---|---|---|---|---|---|---|---|
| elder_north_pine_isle_1 | (7986, 458, 73) | 130 | spruce / snow_pine | 25-45 / 25-30 | **Delibird** | R | single stage | The roster's only bird. |
| elder_north_pine_isle_2 | (6998, 312, 75) | 132 | spruce / snow_pine | 25-45 / 25-30 | **Delibird** | R | single stage | Same pool as _1. Alternative: Swablu (owner decision 8). |
| elder_south_pine_isle_1 | (7232, 1992, 76) | 133 | spruce / snow_pine | 25-45 / 25-30 | **Rowlet** + Dartrix | R | Dartrix eligible (17‡) | The owl isle. |
| elder_south_pine_isle_2 | (6768, 1208, 112) | 169 | spruce / snow_pine | 25-45 / 25-30 | **Rowlet** + Dartrix | R | as above | Same pool as _1. |
| elder_south_pine_isle_3 ★ | (7496, 1266, 73) | 130 | spruce / snow_pine | 25-45 / Rowlet 25-30, Decidueye 36-40 | **Decidueye** (rare) over Rowlet 24 | R (authored-only in the roster) | authored final stage | 2,481 off a leg, the isle's far tip: the owl isle's grown owl. |

### Jungle Isle (remote, 1154-2104 off any leg)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages at pool | why |
|---|---|---|---|---|---|---|---|---|
| elder_jungle_west_1 | (4464, 7312, 70) | 127 | jungle / emergent_jungle | 25-45 / 25-30 | **Pikipek** + Trumbeak | R | Trumbeak eligible. Toucannon 28 > 25 | The roster's woodpecker in the emergent canopy. |
| elder_jungle_west_2 ★ | (4968, 7416, 126) | 183 | jungle / emergent_jungle | 25-45 / Pikipek 25-30, Toucannon 30-34 | **Toucannon** (rare) over Pikipek 24 | R (authored-only in the roster) | authored final stage | The isle's high ground (y126): the toucan at the top. |
| elder_jungle_east_1 | (5216, 7904, 81) | 138 | jungle / jungle_edge | 25-45 / 25-30 | **Hawlucha** | R | single stage | The roster's anchor, a wrestler on the jungle edge. |
| elder_jungle_east_2 | (5248, 6976, 77) | 134 | jungle / jungle_edge | 25-45 / 25-30 | **Squawkabilly** | N to isle (long_isle_south) | single stage | Parrots on the jungle's edge. |

### Long Isle (remote, 1460-3107 off any leg)

| id | (x, z, ground) | block y | tree | band / pool | bird | src | stages at pool | why |
|---|---|---|---|---|---|---|---|---|
| elder_long_isle_north_1 | (7886, 4492, 70) | 127 | spruce / coastal_spruce | 25-45 / 25-30 | **Rookidee** + Corvisquire | R | Corvisquire eligible | The roster's crow. |
| elder_long_isle_north_2 ★ | (7778, 5264, 93) | 150 | spruce / coastal_spruce | 25-45 / Rookidee 25-30, Corviknight 38-40 | **Corviknight** (rare) over Rookidee 24 | N stage (authored-only on tri_peaks) | authored final stage | The Galar taxi bird, grown, on a far coast. |
| elder_long_isle_middle_1 | (8104, 5978, 76) | 133 | dark oak / mossy_broadleaf | 25-45 / 25-30 | **Pidove** + Tranquill | N | Tranquill eligible. Unfezant 32‡ | The roster has no bird. A woodland pigeon for the mossy wood. |
| elder_long_isle_middle_2 | (7376, 6790, 86) | 143 | dark oak / mossy_broadleaf | 25-45 / 25-30 | **Spearow** + Fearow | N | Fearow eligible | The Spearow line's third tree. |
| elder_long_isle_south_1 | (7128, 7936, 75) | 132 | jungle / jungle_edge | 25-45 / 25-30 | **Chatot** | R | single stage | The roster's anchor. |
| elder_long_isle_south_2 | (7920, 7512, 88) | 145 | jungle / jungle_edge | 25-45 / 25-30 | **Squawkabilly** | R | single stage | The roster's parrot. |
| elder_long_isle_south_3 ★ | (7336, 7376, 135) | 192 | jungle / jungle_edge | 25-45 / 25-30 | **Oricorio** (rare) over Chatot 24 | N to isle (sunset_isle) | single stage (style: C4) | The highest and most remote elder on the map (y135, 2,668 off a leg): a dancer on the summit. |

## Summary: families and how often

53 trees, 25 families, 5 rare finds (★).

| Family | Trees | Where |
|---|---|---|
| Hoothoot | 4 (+ Route 1 co-resident) | Lake Viltri, Foothill, Tilpey east, Northgate west |
| Rookidee | 4 (1 ★ Corviknight) | Peak Pond, Northgate west, Long Isle north ×2 |
| Pidgey | 3 (incl. Route 1) | Route 1, grove, Tilpey east |
| Spearow | 3 | Viltri plateau, Foothill, Long Isle middle |
| Taillow | 3 | Viltri plateau, Shrew Lakes, Northgate east |
| Pidove | 3 | Viltri's Path, Foothill, Long Isle middle |
| Natu | 3 | grove, Shrew Lakes, Wedge north |
| Starly | 3 | Peak Pond, Tilpey north, Northgate east |
| Pikipek | 3 (1 ★ Toucannon) | grove, Jungle west ×2 |
| Rowlet | 3 (1 ★ Decidueye) | South Pine Isle ×3 |
| Fletchling | 2 (+1 as co-resident) | Viltri plateau, Peak Pond |
| Ducklett | 2 | Lake Viltri, Tilpey north |
| Swablu | 2 | grove, Shrew Lakes |
| Murkrow | 2 | Wedge north, Wedge south |
| Delibird | 2 | North Pine Isle ×2 |
| Squawkabilly | 2 | Jungle east, Long Isle south |
| Farfetch'd ★, Rufflet, Flamigo, Bombirdier, Cramorant, Vullaby, Hawlucha, Chatot, Oricorio ★ | 1 each | see tables |

- **From the tree's own roster (R):** 18 trees. **From its region (RG):** 5. **New to the area (N):** 30.
- **Species with no authored home that get one:** Spearow/Fearow, Taillow/Swellow, Pidove/Tranquill, Farfetch'd,
  Natu/Xatu, Bombirdier and Cramorant (all on `ENCOUNTER_GAPS.md`'s list), plus Fletchinder as a wild stage.
- **First wild appearance of an evolved stage:** Fletchinder, Tranquill, Fearow, Xatu, Swellow, Staraptor and
  Pidgeot (by the policy's level rule). Decidueye, Toucannon and Corviknight appear only as authored rare finds.

## Answer check (what the birds add to each gym)

Caps follow the proposed leader curve 20/25/30/35/40/45/50/55 at offset 0 (`GYM_SUFFICIENCY_AUDIT.md`, still
an open decision).

| Gym | What the sapling birds add | Reachable before it |
|---|---|---|
| A1 Brock (Rock) | Nothing: Flying is weak to Rock. Route 1 is unchanged. | n/a |
| A2 Misty (Water) | Nothing decisive (Ducklett is neutral). | n/a |
| A3 Surge (Electric) | Nothing, and every bird is weak to Electric. The Gym 3 gap in `ENCOUNTER_GAPS.md` is unchanged: its answer is still Ground. | n/a |
| A4 Erika (Grass) | 1. Fletchinder at Peak Pond 2 (Fire/Flying, 30-32, on leg 4). 2. Staravia at Peak Pond 1 (68 off leg 4, Intimidate). 3. Noctowl, Fearow, Tranquill and Rufflet at Foothill (leg 3), and Swablu, Pidgeotto and Trumbeak in the grove. | yes, legs 3-4 |
| A5 Koga (Poison) | 1. Natu at grove 1 (21-23, leg 3) levels into Xatu at 25‡, under the 35 cap of leg 4. 2. Xatu wild in Wedge north 2. 3. Skarmory (already rostered on the_crags, leg 4) is unchanged. | yes |
| A6 Sabrina (Psychic) | 1. Bombirdier at Marsh 2 (Dark/Flying, 34-39, near leg 6). 2. Murkrow and Vullaby in the Wedge (Dark/Flying, 25-30). | yes, leg 6 |
| A7 Blaine (Fire) | 1. Swanna at Tilpey north 1 (Water/Flying, 39-41, 74 off legs 6-7). 2. Cramorant at Marsh 3. | yes, legs 6-7 |
| A8 Giovanni (Ground) | Every bird is immune to Ground. 1. Swanna and Cramorant (Water) hit back. 2. Staraptor at Tilpey north 2 and Pidgeot at Tilpey east 2 (277 off legs 7-8). | yes, legs 7-8 |

## Conflicts

- **C1. A family this world cannot finish.** Murkrow to Honchkrow needs a **Dusk Stone**, and STATE records that
  no evolution-stone ore generates. ADR-003 (Proposed) would put Dusk at the gorge hamlet on leg 7. Until then,
  both Murkrow trees give a family that stops at stage one. No other proposed bird needs an item.
  - The Kanto Farfetch'd does not evolve. The Galarian form, whose Sirfetch'd needs three critical hits, is not
    proposed.
  - Oricorio changes style with nectar items. Whether Cobblemon 1.8 ships nectars, and whether any are
    obtainable, is NOT VERIFIED.
- **C2. The level-cap trap** (STATE, "needs a fix"). All 16 isle trees use the 25-45 wilderness band, and the isles
  can be reached by boat at any time.
  - A 25-30 pool is safe from about leg 3 on, since the Surge cap is 30.
  - The three evolved rare finds are not: Decidueye 36-40, Toucannon 30-34 and Corviknight 38-40 are over the
    cap for any player who sails out before Erika or Koga.
  - The Wedge pools (25-30) are over cap only before Surge.
  - Every other tree's pool is at or under the cap of the leg it stands by.
- **C3. Earlier than the species' roster home.**
  - Ducklett: 18-21 at Lake Viltri, against 39-41 at Tilpey.
  - Flamigo: 34-39 in the marsh, against 49-56 at Arrow Creeks.
  - Vullaby: 25-30 in the Wedge, against 47-49 on the plateau.
  - Swablu: 10-15 at Shrew Lakes, against 22+ on Route 3.

  None of these breaks a cap, but each moves when the species first appears. Owner decision 6.
- **C4. Oricorio's style** is not chosen. Baile (Fire), Pom-Pom (Electric), Pa'u (Psychic) and Sensu (Ghost) are
  different Pokemon in battle. Whether a spawn entry can pin a style by aspect is NOT VERIFIED.
- **C5. The repo's evolution labels.** `data/spawns.json` marks Braviary and Decidueye "player evolution
  (non-level method)", but mainline gives level 54 and 34. The cause is probably the Hisuian branches.
  Nothing here depends on it: both are excluded, or authored only.
- **C6. No time conditions.** A habitat pool carries no time condition (`route_1_sapling_crown`'s own note,
  `tools/compile_spawns.py` `compile_habitat`). The Hoothoot and Murkrow trees are therefore active by day.
- **C7. The grove and the Tree Town canopy.**
  - The reserved `tree_town_canopy` pool is 25-40. The grove stands in `foothill_woods` (21-23), 29.5 blocks off
    Route 3, where the cap is 30, so a canopy block on the giants would put a 40 beside the road.
  - Grove elders stand only 31-43 blocks from the nearest giant trunk, so the canopy's ranges and these must be
    sized together (see Build).
- **C8. Record disagreement (found, not fixed).** `data/habitat_blocks.json` gives `route1_sapling_crown` the
  status `"planned"`. `docs/STATE.md` says it was placed on staging on 2026-09-25.

## How it would be built (the Route 1 pattern)

1. **Pools.** Add one `habitats[]` entry per tree to `data/spawns.json`, shaped like `route_1_sapling_crown`, with
   pool id `cobblers:<tree id>` and the level, stage split and rare-find weights from the tables.
   - One pool per tree keeps every tree tunable on its own.
   - Sharing pools is possible where trees match exactly, which saves only 3: the two north pine isle Delibirds,
     south pine isle 1 and 2, and the two Murkrows.
   - `tools/compile_spawns.py` compiles them to habitat pool files. Owner of `data/spawns.json`:
     `datapack-content-dev`.
2. **Blocks.** Add one natural `ReplaceSpawns` record per tree to `data/habitat_blocks.json` (owner:
   `world-content-dev`). Each block goes at the trunk centre `(x, z)`, at the **block y** in the tables.
   - `tools/habitat_blocks.py` writes `cobblers:habitats/place`. `reapply.py` runs **R5** (elders) before
     **R9E** (Habitat Blocks), so every trunk exists before its block goes in. The grove is placed by its own
     step, also before R9E.
3. **Height, from the prefab.** Read off `tools/tree_grove.py` `TIERS["elder"]` and `big_tree`. All heights are
   in prefab h, and world y = ground + 1 + h.

   | Part | h |
   |---|---|
   | Log trunk | -2..58, tapering above the first storey |
   | Storeys (limbs) | 20-24 and 38-42 |
   | Clear room | 43-55 |
   | Upper limbs | from 53 |
   | Crown | 56-81 (main ball centred at 68, radius 19; top ball 71-81) |

   - **Proposed h56, the crown base: world y = ground + 57.** At h56 the trunk's radius is 1.65, so the centre
     column is log on all four sides with 2 more logs above. That keeps the block hidden, and nobody walking the
     wood breaks it. This is the analogue of Route 1's block sitting just below its crown.
   - As a **sphere** of 19, it covers h37-75: the upper storey, the upper limbs and most of the crown, and not
     the forest floor (56 below), which keeps the wood's own pool.
   - As a **column**, it also covers the floor under the crown, the case Route 1 already accepted.
   - **Fallback** (owner decision 2): h20, the first storey, at world y = ground + 21. Birds would then sit at
     the tree's foot and on its lowest limbs.
4. **Range.**
   - **19** for the 48 standalone elders, matching the crown radius. They are 363 or more apart
     (`nearest_other`), so even the configured 24 cannot overlap.
   - Every elder is at least 60 from a leg centreline (`elder_trees.py` rule), so a 19 range leaves 41 or more.
   - The nearest existing blocks are Victory Road's tiles (x3439-3740, z2545-3045), about 207 from
     `elder_wedge_north_1` at the closest, and the mansion ward, 400 or more from Route 1.
   - **14 for the 4 grove elders.** They are 60-123 from each other, but a giant trunk stands 31-43 away. If
     the Tree Town later puts `tree_town_canopy` blocks in the giants, those must stay at 16 or less, so no pair
     sums past 31. Overlap spawns nothing (EXP-021).
   - The world tree needs no block for this. If it ever gets one high in its crown (y457+), a column-shaped
     reach would overlap all four grove elders.
5. **Checks.** The validator's `habitat-blocks` check covers overlap, pool and presence (`--world-save`, on a
   stopped copy). Placement is re-applied after every export, like the others.

## Assumptions and their status

| Capability relied on | Status |
|---|---|
| Natural `ReplaceSpawns` replaces the ambient pool within range; horizontal edge at the configured range; overlapping ranges spawn nothing; blocks survive restarts but not a re-export | VERIFIED (EXP-021) |
| Vertical shape of the reach (sphere or column), and replacement well above the ground | **NOT VERIFIED: EXP-033, unrun** (needs a player in game) |
| A grounded spawn stands on leaves or limbs in a crown | NOT VERIFIED (the same caveat as Route 1) |
| A player on the ground causes spawns 57-82 blocks overhead. `spawningZoneHeight` is 16 in `modpack/config/cobblemon/main.json`: if the zone follows the player's height, crown birds may appear only to a player who has climbed up | **NOT VERIFIED.** This decides owner decision 2 and belongs in EXP-033. |
| Every new species is `implemented` in the Cobblemon 1.8.0 jar (Spearow, Taillow, Pidove, Farfetch'd, Natu, Bombirdier, Cramorant, Flamigo) | NOT VERIFIED here. Check with `tools/battle_sim.py`'s loader, which drops `implemented: false`. |
| Evolution thresholds marked ‡ | ASSUMED (mainline), not read from the jar's `evolutions` blocks |
| Multiplayer | Wild spawns are shared world state and nothing is claimable, so there is no once-per-player or once-per-server question. Several players at one tree share its pool. |

## Owner decisions

1. **The count.** 53 saplings: Route 1 + 48 elders + 4 grove elders. This excludes the world tree, the 7 grove
   giants (left to `tree_town_canopy`) and the 5 landmark and painted giants. Should any of those get a bird too?
2. **Crown or foot.** Block at ground + 57 (birds in the crown) or ground + 21 (birds at the foot and lower
   limbs). Best decided after EXP-033 and the spawn-zone-height check.
3. **Range.** 19 for standalone elders and 14 in the grove, or something else.
4. **Levels.** Follow each sub-region's band as it is, or narrow the wide bands to min..min+5 as proposed.
5. **Rare finds.** Keep all five: Farfetch'd, Decidueye, Toucannon, Corviknight, Oricorio. Also settle weight 2
   against 24, and whether evolved finals on the isles may be over cap (C2).
6. **Early appearances.** Accept Ducklett, Flamigo, Vullaby and Swablu before their roster homes (C3), plus the
   first wild Staraptor and Pidgeot.
7. **Murkrow while no Dusk Stone exists.** Keep both Murkrow trees (C1), or swap one to Vullaby or Noctowl.
8. **Oricorio's style** (C4), and whether North Pine Isle 2 stays Delibird or becomes Swablu.
9. **Pool shape.** One pool per tree (proposed) or shared pools per bird.
10. **Night birds by day.** Accept owls and crows in the daytime (C6), or leave them out of tree pools.
11. **The Tree Town canopy.** Settle its band (25-40 beside a cap-30 road) and its ranges before the grove
    elders' blocks go in (C7).
12. **Rowlet** is kept out of the grove because it is a starter. The owner may want it there.
