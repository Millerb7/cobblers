# Sub-region roster audit

Every sub-region, what spawns there, and whether it belongs. Evidence: Cobblemon 1.8.0's own
spawn data for where each species lives upstream (biome tags resolved against every jar this
server loads), `data/spawns.json` for what we authored, and the compiled datapack for whether
an entry reaches the world at all. Terrain heights sampled from the staging export.

## Before any roster judgement: reach

| | scopes | note |
|---|---|---|
| Reaching the world | 27 | a route corridor passes through them |
| Habitat pools | 9 | compiled, waiting on a habitat block |
| **Unreachable** | **35** | authored with coordinate boxes, but no route passes through: `compile_spawns.py` emits nothing |

The 35 unreachable rosters are 350 authored entries that no player can ever meet.

Unreachable: `arrow_creeks`, `arrow_lake_shores`, `east_coast_dunes`, `east_cones`, `eastern_moor`, `frostpeak`, `frostpeak_strand`, `fungal_north`, `fungal_south`, `great_crater`, `jungle_east`, `jungle_west`, `long_isle_middle`, `long_isle_north`, `long_isle_south`, `lower_trough`, `marshy_marsh`, `north_pine_isle`, `north_shore_downs`, `north_west_coast`, `northgate_east`, `northgate_west`, `plateau_east`, `plateau_south`, `shrew_lake_shores`, `south_east_dunes`, `south_pine_isle`, `south_west_fields`, `sunset_east`, `sunset_west`, `tilpey_waters`, `tilpey_west_meadows`, `viltris_path_valley`, `wedge_north`, `wedge_south`

## Flagged: species that do not belong

A flag is a prompt, not a verdict — our own `biomes` list is what Cobblemon honours at runtime,
so none of these are broken, they are wrong *for the place*.

### Wrong country (23)

| sub-region | species | why |
|---|---|---|
| `arrow_creeks` | wattrel | shore/water species; no terrain sampled (scope does not reach the world) |
| `arrow_lake_shores` | azurill | shore/water species; no terrain sampled (scope does not reach the world) |
| `frostpeak` | crabrawler | shore/water species; no terrain sampled (scope does not reach the world) |
| `long_isle_south` | deerling | snow species in jungle country |
| `long_isle_south` | wimpod | shore/water species; no terrain sampled (scope does not reach the world) |
| `north_west_coast` | krabby | shore/water species; no terrain sampled (scope does not reach the world) |
| `north_west_coast` | wingull | shore/water species; no terrain sampled (scope does not reach the world) |
| `north_west_coast` | binacle | shore/water species; no terrain sampled (scope does not reach the world) |
| `north_west_coast` | inkay | shore/water species; no terrain sampled (scope does not reach the world) |
| `rift_foot` | wattrel | shore/water species; this ground is 0.0% water |
| `south_strand` | mareanie | shore/water species; this ground is 0.0% water |
| `south_strand` | wattrel | shore/water species; this ground is 0.0% water |
| `south_strand` | wimpod | shore/water species; this ground is 0.0% water |
| `south_strand` | crabrawler | shore/water species; this ground is 0.0% water |
| `south_strand` | kilowattrel | shore/water species; this ground is 0.0% water |
| `south_strand` | toxapex | shore/water species; this ground is 0.0% water |
| `south_strand` | golisopod | shore/water species; this ground is 0.0% water |
| `sunset_east` | comfey | shore/water species; no terrain sampled (scope does not reach the world) |
| `the_crags` | skarmory | desert species in snow country |
| `west_shore` | wingull | shore/water species; this ground is 0.0% water |
| `west_shore` | krabby | shore/water species; this ground is 0.0% water |
| `west_shore` | staryu | shore/water species; this ground is 0.0% water |
| `west_shore` | wattrel | shore/water species; this ground is 0.0% water |

### Needs water and has none declared (28)

| sub-region | species | why |
|---|---|---|
| `arrow_creeks` | flamigo | never spawns on dry land upstream |
| `arrow_lake_shores` | surskit | never spawns on dry land upstream |
| `glacial_tear_deep_valley` | piplup | never spawns on dry land upstream |
| `lake_viltri_hollow` | surskit | never spawns on dry land upstream |
| `lower_trough` | piplup | never spawns on dry land upstream |
| `lower_trough` | bidoof | never spawns on dry land upstream |
| `marsh_creek` | barboach | never spawns on dry land upstream |
| `marsh_creek` | whiscash | never spawns on dry land upstream |
| `marshy_marsh_basin` | barboach | never spawns on dry land upstream |
| `north_west_coast` | shellder | never spawns on dry land upstream |
| `river_of_shrews_vale` | surskit | never spawns on dry land upstream |
| `river_of_shrews_vale` | bidoof | never spawns on dry land upstream |
| `shrew_lake_shores` | surskit | never spawns on dry land upstream |
| `south_strand` | clauncher | never spawns on dry land upstream |
| `south_strand` | pincurchin | never spawns on dry land upstream |
| `south_strand` | clawitzer | never spawns on dry land upstream |
| `tilpey_east_shore` | bidoof | never spawns on dry land upstream |
| `tilpey_north_shore` | bibarel | never spawns on dry land upstream |
| `tilpey_north_shore` | yanma | never spawns on dry land upstream |
| `tilpey_waters` | goldeen | never spawns on dry land upstream |
| `tilpey_waters` | basculin | never spawns on dry land upstream |
| `tilpey_waters` | magikarp | never spawns on dry land upstream |
| `tilpey_waters` | basculegion | never spawns on dry land upstream |
| `tilpey_waters` | seaking | never spawns on dry land upstream |
| `tilpey_waters` | arrokuda | never spawns on dry land upstream |
| `tilpey_waters` | gyarados | never spawns on dry land upstream |
| `tilpey_waters` | barraskewda | never spawns on dry land upstream |
| `west_shore` | shellder | never spawns on dry land upstream |

### Milder mismatch: fits the idea of the place, not the biome we declared (42)

| sub-region | species | upstream vs here |
|---|---|---|
| `crater_rim_north_west` | sizzlipede | upstream: desert/volcanic; here: plains |
| `crater_rim_north_west` | heatmor | upstream: desert/mountain/volcanic; here: plains |
| `crater_rim_north_west` | salandit | upstream: desert/mountain/volcanic; here: plains |
| `crater_rim_north_west` | centiskorch | upstream: desert/volcanic; here: plains |
| `crater_rim_north_west` | turtonator | upstream: volcanic; here: plains |
| `eastern_moor` | foongus | upstream: mushroom; here: plains |
| `eastern_moor` | karrablast | upstream: swamp; here: plains |
| `eastern_moor` | shelmet | upstream: swamp; here: plains |
| `frostpeak_strand` | delibird | upstream: mountain; here: forest/snow |
| `glacier_foot_fields` | tarountula | upstream: forest/swamp; here: plains |
| `glacier_foot_fields` | spidops | upstream: forest/swamp; here: plains |
| `great_crater` | magby | upstream: volcanic; here: mountain |
| `great_crater` | numel | upstream: desert/volcanic; here: mountain |
| `great_crater` | charmander | upstream: volcanic; here: mountain |
| `great_crater` | magmar | upstream: volcanic; here: mountain |
| `great_crater` | camerupt | upstream: desert/volcanic; here: mountain |
| `great_crater` | charmeleon | upstream: volcanic; here: mountain |
| `great_crater` | charizard | upstream: volcanic; here: mountain |
| `jungle_east` | komala | upstream: plains; here: jungle |
| `north_east_downs` | wooloo | upstream: mountain/plains; here: forest |
| `north_pine_isle` | delibird | upstream: mountain; here: forest/snow |
| `north_shore_downs` | fletchling | upstream: forest/volcanic; here: plains |
| `north_west_coast` | hoothoot | upstream: forest; here: plains |
| `peak_pond_hollow` | wooloo | upstream: mountain/plains; here: forest |
| `peak_pond_hollow` | mareep | upstream: mountain/plains; here: forest |
| `peak_pond_hollow` | flaaffy | upstream: mountain/plains; here: forest |
| `peak_pond_hollow` | ampharos | upstream: mountain/plains; here: forest |
| `plateau_east` | litleo | upstream: plains/volcanic; here: desert |
| `plateau_east` | pyroar | upstream: plains/volcanic; here: desert |
| `rift_south_west_arm` | cubone | upstream: desert/volcanic; here: mountain |
| `rift_south_west_arm` | dwebble | upstream: desert; here: mountain |
| `rift_south_west_arm` | scraggy | upstream: desert; here: mountain |
| `rift_south_west_arm` | crustle | upstream: desert; here: mountain |
| `rift_south_west_arm` | scrafty | upstream: desert; here: mountain |
| `rift_trunk` | nacli | upstream: desert/volcanic; here: mountain |
| `rift_trunk` | naclstack | upstream: desert/volcanic; here: mountain |
| `rift_trunk` | garganacl | upstream: desert/volcanic; here: mountain |
| `rift_west_spur` | pawniard | upstream: jungle/river; here: mountain |
| `rift_west_spur` | bisharp | upstream: jungle/river; here: mountain |
| `sunset_east` | smoliv | upstream: plains; here: forest |
| `viltri_plateau` | fomantis | upstream: coast/jungle; here: forest |
| `wedge_south` | duskull | upstream: desert/volcanic; here: forest |

## How to fix it

### A condition does the work

**Shore and water species inland** (23 wrong-country + 28 water entries). Adding
`neededNearbyBlocks: ["minecraft:water"]` to the entry confines the spawn to the water's edge
wherever the box happens to touch water, and makes it silently never fire where the box does not.
No species has to be removed, and the boxes do not have to be re-cut. This is the same change the
river Wooper needs, so the two land together.

**A structural bug underneath them.** `tools/compile_spawns.py:150` and `:167` hardcode
`"spawnablePositionType": "grounded"` for every compiled entry. **12 entries in live sub-regions
are species that never spawn on dry land upstream** — Magikarp, Gyarados, Basculin, Goldeen,
Barboach, Whiscash, Shellder, Surskit and friends are being asked to stand on the ground. They
almost certainly never spawn at all. 28 such entries exist across all sub-regions; `tilpey_waters`,
whose whole identity is fish, is 10-for-10 on it, though that one does not reach the world yet.
The fix is to carry a position type per entry from `data/spawns.json`
instead of hardcoding one, which is a generator change rather than a roster change.

**Species that fit the place but not the biome id we declared** (42). These are not bugs: our own
`biomes` list is what runs. Widening the declared list, or leaving it, are both defensible; no
species needs removing.

### Only a roster edit will do

- `the_crags` Skarmory — a desert/badlands species in snow country.
- `long_isle_south` Deerling — reads as snow against a jungle roster.
- Every **weak identity** sub-region below. A roster that could belong anywhere cannot be
  conditioned into belonging somewhere; it has to be rewritten around a few species that are
  only found there.

## Flagged separately: places with no identity

`similarity` is the share of species two rosters have in common; `shared` counts species that
appear in four or more sub-regions; `signature` counts species unique to this one.

| sub-region | status | similarity | nearest | shared | signature | reads as |
|---|---|---|---|---|---|---|
| `marshy_marsh` | unreachable | 0.57 | `marshy_marsh_basin` | 1 | 2 | water 5, poison 3, ground 2 |
| `marshy_marsh_basin` | habitat | 0.57 | `marshy_marsh` | 1 | 0 | water 5, poison 4, ground 3 |
| `northgate_old_growth_grove` | habitat | 0.57 | `northgate_west` | 5 | 0 | normal 4, flying 2, bug 1 |
| `northgate_west` | unreachable | 0.57 | `northgate_old_growth_grove` | 5 | 2 | normal 4, bug 3, flying 2 |
| `fungal_south` | unreachable | 0.54 | `marsh_creek` | 1 | 0 | water 6, ground 3, grass 1 |
| `marsh_creek` | route | 0.54 | `fungal_south` | 1 | 1 | water 8, ground 5 |
| `crater_rim_north_west` | route | 0.47 | `great_crater_bowls` | 1 | 3 | fire 7, bug 2, ground 2 |
| `great_crater_bowls` | habitat | 0.47 | `crater_rim_north_west` | 3 | 0 | fire 10, rock 3, ground 2 |
| `arrow_creeks` | unreachable | 0.43 | `sunset_west` | 1 | 1 | flying 4, electric 3, normal 3 |
| `north_west_coast` | unreachable | 0.43 | `west_shore` | 1 | 2 | water 4, flying 2, normal 1 |
| `sunset_west` | unreachable | 0.43 | `arrow_creeks` | 0 | 0 | normal 3, flying 2, fire 2 |
| `west_shore` | route | 0.43 | `north_west_coast` | 1 | 1 | water 4, flying 3, normal 1 |
| `glacial_tear_deep_valley` | habitat | 0.38 | `upper_trough` | 1 | 1 | ice 7, water 2, bug 1 |
| `upper_trough` | route | 0.38 | `glacial_tear_deep_valley` | 1 | 1 | ice 5, bug 1 |
| `east_coast_dunes` | unreachable | 0.33 | `plateau_west` | 1 | 2 | ground 3, dark 1, grass 1 |
| `frostpeak_strand` | unreachable | 0.33 | `north_pine_isle` | 1 | 1 | ice 2, ground 2, flying 1 |
| `north_pine_isle` | unreachable | 0.33 | `frostpeak_strand` | 1 | 0 | ice 4, bug 1, grass 1 |
| `plateau_west` | route | 0.33 | `east_coast_dunes` | 1 | 4 | dark 6, grass 3, ground 3 |
| `route_1_ghost_mansion` | habitat | 0.33 | `wedge_north` | 1 | 2 | ghost 9, dark 3, poison 1 |
| `wedge_north` | unreachable | 0.33 | `route_1_ghost_mansion` | 1 | 1 | ghost 4, poison 2, dark 2 |
| `foothill_woods` | route | 0.29 | `northgate_old_growth_grove` | 4 | 1 | normal 5, flying 3, bug 2 |
| `rift_depths` | habitat | 0.29 | `rift_south_west_arm` | 1 | 0 | rock 5, ground 4, steel 3 |
| `rift_south_west_arm` | route | 0.29 | `rift_depths` | 1 | 3 | rock 5, ground 2, bug 2 |
| `long_isle_north` | unreachable | 0.25 | `northgate_east` | 1 | 0 | normal 5, dark 2, flying 2 |
| `merian_cirque` | route | 0.25 | `mt_vessu` | 2 | 1 | ice 3, psychic 2, normal 2 |
| `mt_vessu` | route | 0.25 | `merian_cirque` | 1 | 0 | normal 2, flying 1, grass 1 |
| `north_east_downs` | route | 0.25 | `northgate_east` | 1 | 1 | normal 5, dark 3, flying 2 |
| `northgate_east` | unreachable | 0.25 | `long_isle_north` | 1 | 0 | normal 7, flying 2, bug 1 |
| `pallet_meadows` | route | 0.25 | `peak_pond_hollow` | 1 | 1 | normal 3, flying 1, electric 1 |
| `peak_pond_hollow` | route | 0.25 | `pallet_meadows` | 3 | 1 | electric 5, normal 3, flying 1 |
| `sunset_east` | unreachable | 0.25 | `tilpey_west_meadows` | 0 | 1 | fairy 3, grass 3, bug 2 |
| `tilpey_west_meadows` | unreachable | 0.25 | `sunset_east` | 1 | 2 | grass 5, poison 2, bug 2 |
| `east_cones` | unreachable | 0.22 | `mining_town_fossil_levels` | 3 | 0 | rock 6, fire 3, steel 3 |
| `great_crater` | unreachable | 0.22 | `great_crater_bowls` | 1 | 5 | fire 9, ground 2, rock 1 |
| `jungle_west` | unreachable | 0.22 | `tree_town_canopy` | 0 | 4 | normal 6, flying 3, bug 1 |
| `mining_town_fossil_levels` | habitat | 0.22 | `rift_trunk` | 2 | 3 | rock 10, steel 2, ground 2 |
| `rift_trunk` | route | 0.22 | `mining_town_fossil_levels` | 2 | 2 | rock 8, fire 2, steel 1 |
| `tree_town_canopy` | habitat | 0.22 | `jungle_west` | 0 | 0 | bug 4, flying 4, normal 3 |
| `wedge_south` | unreachable | 0.20 | `route_1_ghost_mansion` | 1 | 3 | ghost 3, poison 3, flying 2 |
| `frostpeak` | unreachable | 0.18 | `upper_trough` | 0 | 0 | ice 3, dark 2, fighting 1 |
| `lake_viltri_hollow` | route | 0.18 | `tilpey_north_shore` | 2 | 3 | water 4, bug 3, grass 2 |
| `long_isle_middle` | unreachable | 0.18 | `tilpey_east_shore` | 1 | 3 | grass 4, bug 3, normal 1 |
| `lower_trough` | unreachable | 0.18 | `frostpeak_strand` | 1 | 1 | water 5, ice 2, normal 1 |
| `north_shore_downs` | unreachable | 0.18 | `south_west_fields` | 1 | 1 | normal 5, flying 4, grass 3 |
| `river_of_shrews_vale` | route | 0.18 | `lower_trough` | 2 | 1 | water 2, normal 2, bug 1 |
| `south_west_fields` | unreachable | 0.18 | `tilpey_south_shore` | 0 | 1 | grass 3, normal 2, flying 2 |
| `the_crags` | route | 0.18 | `east_cones` | 1 | 1 | steel 3, rock 2, ice 1 |
| `tilpey_east_shore` | route | 0.18 | `long_isle_middle` | 1 | 0 | grass 4, normal 3, bug 2 |
| `tilpey_north_shore` | route | 0.18 | `lake_viltri_hollow` | 1 | 4 | water 7, flying 3, grass 2 |
| `tilpey_south_shore` | route | 0.18 | `south_west_fields` | 3 | 3 | bug 6, flying 3, poison 3 |
| `viltri_plateau` | route | 0.18 | `long_isle_middle` | 1 | 1 | grass 3, flying 2, bug 1 |
| `eastern_moor` | unreachable | 0.16 | `marshy_marsh_basin` | 1 | 2 | bug 2, water 1, ground 1 |
| `rift_south_east_arm` | route | 0.16 | `rift_depths` | 1 | 6 | ground 5, psychic 4, rock 3 |
| `rift_west_spur` | route | 0.16 | `rift_depths` | 1 | 5 | steel 9, psychic 2, poison 2 |
| `fungal_north` | unreachable | 0.11 | `eastern_moor` | 0 | 6 | grass 8, bug 2, fairy 2 |
| `glacier_foot_fields` | route | 0.11 | `fungal_south` | 1 | 5 | psychic 2, bug 2, normal 1 |
| `long_isle_south` | unreachable | 0.11 | `sunset_east` | 1 | 4 | grass 4, normal 3, flying 2 |
| `plateau_east` | unreachable | 0.11 | `sunset_west` | 1 | 4 | fire 6, dark 2, bug 2 |
| `plateau_south` | unreachable | 0.11 | `rift_south_west_arm` | 1 | 3 | ground 4, rock 3, grass 2 |
| `rift_foot` | route | 0.11 | `viltris_path_valley` | 1 | 4 | dark 2, poison 2, electric 1 |
| `shrew_lake_shores` | unreachable | 0.11 | `tilpey_west_meadows` | 1 | 3 | grass 2, fairy 2, bug 1 |
| `south_pine_isle` | unreachable | 0.11 | `north_pine_isle` | 0 | 2 | grass 3, flying 2, ice 1 |
| `south_strand` | route | 0.11 | `long_isle_south` | 1 | 6 | water 6, electric 3, poison 2 |
| `the_tri_peaks` | route | 0.11 | `long_isle_north` | 1 | 0 | flying 3, normal 1, grass 1 |
| `viltris_path_valley` | unreachable | 0.11 | `long_isle_north` | 1 | 1 | normal 5, flying 2, dark 1 |
| `displaced_city_cavern` | habitat | 0.09 | `rift_west_spur` | 0 | 9 | steel 4, ghost 4, electric 3 |
| `arrow_lake_shores` | unreachable | 0.05 | `lake_viltri_hollow` | 1 | 3 | normal 2, fairy 1, bug 1 |
| `jungle_east` | unreachable | 0.05 | `jungle_west` | 0 | 5 | normal 4, fighting 2, flying 2 |
| `mt_clay` | route | 0.05 | `merian_cirque` | 1 | 4 | normal 2, flying 2, fighting 2 |
| `south_east_dunes` | unreachable | 0.05 | `plateau_west` | 0 | 5 | ground 2, psychic 2, dark 1 |
| `tilpey_waters` | unreachable | 0.05 | `tilpey_north_shore` | 1 | 9 | water 9, ghost 1, flying 1 |

Weak identity (similarity 0.40 or higher, or two or fewer species of their own): **45**

## Every sub-region, as it would appear in game

### `arrow_creeks` — unreachable

*biomes: savanna*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| wattrel | electric/flying | common | 24.0 | 49-56 | **BIOME** never spawns in savanna upstream; upstream biomes are coast, island, ocean, sky |
| doduo | normal/flying | common | 18.0 | 49-56 |  |
| girafarig | normal/psychic | common | 12.0 | 49-56 |  |
| phanpy | ground | common | 9.0 | 49-56 |  |
| dodrio | normal/flying | uncommon | 6.0 | 49-56 |  |
| flamigo | flying/fighting | uncommon | 6.0 | 49-56 | **WATER** never spawns on dry land upstream (3/3 entries in water) |
| blitzle | electric | uncommon | 4.5 | 49-56 |  |
| donphan | ground | uncommon | 3.0 | 49-56 |  |
| zebstrika | electric | rare | 1.5 | 49-56 |  |
| farigiraf | normal/psychic | ultra-rare | — | 49-56 |  |

### `arrow_lake_shores` — unreachable

*biomes: flower_forest*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| azurill | normal/fairy | common | 24.0 | 10-22 |  |
| surskit | bug/water | common | 24.0 | 10-22 | **BIOME** never spawns in flower_forest upstream; upstream biomes are #the_bumblezone:the_bumblezone, freshwater; **WATER** never spawns on dry land upstream (2/2 entries in water) |
| budew | grass/poison | common | 12.0 | 10-22 |  |
| audino | normal | uncommon | 6.0 | 10-22 |  |
| azumarill | water/fairy | ultra-rare | — | 10-22 |  |
| marill | water/fairy | ultra-rare | — | 10-22 |  |
| roselia | grass/poison | ultra-rare | — | 10-22 |  |
| roserade | grass/poison | ultra-rare | — | 10-22 |  |
| togekiss | fairy/flying | ultra-rare | — | 10-22 |  |
| togetic | fairy/flying | ultra-rare | — | 10-22 |  |

### `crater_rim_north_west` — route

*biomes: savanna_plateau; ground y103–130 (median 109); 0.0% water; 129,664 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| slugma | fire | common | 24.0 | 44-46 |  |
| sizzlipede | fire/bug | common | 18.0 | 44-46 | **BIOME** never spawns in savanna_plateau upstream; upstream biomes are #cobblemon:nether/is_basalt, #cobblemon:nether/is_wasteland, badlands, volcanic |
| heatmor | fire | common | 12.0 | 44-46 | **BIOME** never spawns in savanna_plateau upstream; upstream biomes are #cobblemon:nether/is_mountain, badlands, hills |
| salandit | poison/fire | common | 12.0 | 44-46 | **BIOME** never spawns in savanna_plateau upstream; upstream biomes are #cobblemon:nether/is_basalt, #cobblemon:nether/is_desert, badlands, mountain, volcanic |
| centiskorch | fire/bug | uncommon | 6.0 | 44-46 | **BIOME** never spawns in savanna_plateau upstream; upstream biomes are #cobblemon:nether/is_basalt, #cobblemon:nether/is_wasteland, badlands, volcanic |
| torkoal | fire | uncommon | 6.0 | 44-46 |  |
| turtonator | fire/dragon | uncommon | 6.0 | 44-46 | **BIOME** never spawns in savanna_plateau upstream; upstream biomes are #cobblemon:nether/is_basalt, thermal, volcanic |
| rhyhorn | ground/rock | rare | 1.5 | 44-46 |  |
| rhydon | ground/rock | rare | 0.5 | 44-46 |  |
| salazzle | poison/fire | ultra-rare | — | 44-46 | **UNKNOWN** no stock spawn data for this species |

### `displaced_city_cavern` — habitat

*biomes: *

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| klink | steel | common | 24.0 | 32-45 |  |
| magnemite | electric/steel | common | 18.0 | 32-45 |  |
| porygon | normal | common | 12.0 | 32-45 |  |
| rotom | electric/ghost | common | 12.0 | 32-45 | **UNKNOWN** no stock spawn data for this species |
| gothita | psychic | uncommon | 6.0 | 32-45 |  |
| magneton | electric/steel | uncommon | 6.0 | 32-45 |  |
| trubbish | poison | uncommon | 6.0 | 32-45 |  |
| espurr | psychic | rare | 2.0 | 32-45 |  |
| klefki | steel/fairy | rare | 2.0 | 32-45 |  |
| greavard | ghost | ultra-rare | 1.0 | 32-45 | **UNKNOWN** no stock spawn data for this species |
| mimikyu | ghost/fairy | ultra-rare | 1.0 | 32-45 |  |
| sableye | dark/ghost | ultra-rare | 1.0 | 32-45 |  |
| garbodor | poison | ultra-rare | — | 32-45 |  |
| klang | steel | ultra-rare | — | 32-45 |  |

### `east_coast_dunes` — unreachable

*biomes: desert*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| sandile | ground/dark | common | 24.0 | 25-45 |  |
| trapinch | ground | common | 24.0 | 25-45 |  |
| cacnea | grass | common | 12.0 | 25-45 |  |
| silicobra | ground | common | 12.0 | 25-45 |  |
| cacturne | grass/dark | ultra-rare | — | 25-45 |  |
| flygon | ground/dragon | ultra-rare | — | 25-45 |  |
| krokorok | ground/dark | ultra-rare | — | 25-45 |  |
| krookodile | ground/dark | ultra-rare | — | 25-45 |  |
| sandaconda | ground | ultra-rare | — | 25-45 |  |
| vibrava | ground/dragon | ultra-rare | — | 25-45 |  |

### `east_cones` — unreachable

*biomes: stony_peaks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| slugma | fire | common | 24.0 | 44-52 |  |
| rolycoly | rock | common | 16.8 | 44-52 |  |
| aron | steel/rock | common | 8.4 | 44-52 |  |
| carkol | rock/fire | uncommon | 5.52 | 44-52 |  |
| lairon | steel/rock | uncommon | 2.76 | 44-52 |  |
| coalossal | rock/fire | ultra-rare | 1.68 | 44-52 |  |
| aggron | steel/rock | ultra-rare | 0.84 | 44-52 |  |
| gabite | dragon/ground | ultra-rare | — | 44-52 |  |
| garchomp | dragon/ground | ultra-rare | — | 44-52 |  |
| gible | dragon/ground | ultra-rare | — | 44-52 |  |

### `eastern_moor` — unreachable

*biomes: meadow*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| wooper | water/ground | common | 24.0 | 34-44 |  |
| foongus | grass/poison | common | 12.0 | 34-44 | **BIOME** never spawns in meadow upstream; upstream biomes are mushroom |
| karrablast | bug | common | 12.0 | 34-44 | **BIOME** never spawns in meadow upstream; upstream biomes are swamp |
| shelmet | bug | uncommon | 6.0 | 34-44 | **BIOME** never spawns in meadow upstream; upstream biomes are swamp |
| accelgor | bug | ultra-rare | — | 34-44 | **BIOME** never spawns in meadow upstream; upstream biomes are swamp |
| amoonguss | grass/poison | ultra-rare | — | 34-44 | **BIOME** never spawns in meadow upstream; upstream biomes are mushroom |
| escavalier | bug/steel | ultra-rare | — | 34-44 | **BIOME** never spawns in meadow upstream; upstream biomes are swamp |
| goodra | dragon | ultra-rare | — | 34-44 |  |
| goomy | dragon | ultra-rare | — | 34-44 |  |
| sliggoo | dragon | ultra-rare | — | 34-44 |  |

### `foothill_woods` — route

*biomes: windswept_forest; ground y99–144 (median 115); 0.4% water; 144,704 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| heracross | bug/fighting | common | 24.0 | 21-23 |  |
| hoothoot | normal/flying | common | 18.0 | 21-23 | **BIOME** never spawns in windswept_forest upstream; upstream biomes are forest, sky, spooky |
| bunnelby | normal | common | 12.0 | 21-23 |  |
| scyther | bug/flying | common | 12.0 | 21-23 |  |
| deerling | normal/grass | uncommon | 6.0 | 21-23 |  |
| noctowl | normal/flying | uncommon | 6.0 | 21-23 | **BIOME** never spawns in windswept_forest upstream; upstream biomes are forest, sky, spooky |
| teddiursa | normal | uncommon | 6.0 | 21-23 |  |
| pachirisu | electric | rare | 2.0 | 21-23 | **BIOME** never spawns in windswept_forest upstream; upstream biomes are aether:skyroot_forest, aether:skyroot_woodland, forest |
| sawsbuck | normal/grass | ultra-rare | — | 21-23 |  |
| ursaring | normal | ultra-rare | — | 21-23 |  |

### `frostpeak` — unreachable

*biomes: frozen_peaks, snowy_slopes, snowy_taiga*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| crabrawler | fighting | common | 24.0 | 25-45 | **BIOME** never spawns in frozen_peaks, snowy_slopes, snowy_taiga upstream; upstream biomes are coast |
| delibird | ice/flying | common | 24.0 | 25-45 |  |
| sneasel | dark/ice | common | 12.0 | 25-45 |  |
| snorunt | ice | common | 12.0 | 25-45 |  |
| absol | dark | uncommon | 6.0 | 25-45 |  |
| drampa | normal/dragon | uncommon | 6.0 | 25-45 |  |
| crabominable | fighting/ice | ultra-rare | — | 25-45 |  |
| froslass | ice/ghost | ultra-rare | — | 25-45 |  |
| glalie | ice | ultra-rare | — | 25-45 |  |
| weavile | dark/ice | ultra-rare | — | 25-45 |  |

### `frostpeak_strand` — unreachable

*biomes: snowy_taiga*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| delibird | ice/flying | common | 24.0 | 25-45 | **BIOME** never spawns in snowy_taiga upstream; upstream biomes are #aether:is_aether, peak |
| spheal | ice/water | common | 24.0 | 25-45 | **BIOME** never spawns in snowy_taiga upstream; upstream biomes are cold_ocean, frozen_ocean |
| vulpix alolan | fire | common | 12.0 | 25-45 |  |
| sandshrew alolan | ground | common | 9.0 | 25-45 |  |
| stantler | normal | uncommon | 6.0 | 25-45 |  |
| sandslash alolan | ground | uncommon | 3.0 | 25-45 |  |
| ninetales alolan | fire | ultra-rare | — | 25-45 |  |
| sealeo | ice/water | ultra-rare | — | 25-45 | **BIOME** never spawns in snowy_taiga upstream; upstream biomes are cold_ocean, frozen_ocean |
| walrein | ice/water | ultra-rare | — | 25-45 | **BIOME** never spawns in snowy_taiga upstream; upstream biomes are cold_ocean, frozen_ocean |
| wyrdeer | normal/psychic | ultra-rare | — | 25-45 |  |

### `fungal_north` — unreachable

*biomes: mushroom_fields*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| paras | bug/grass | common | 18.0 | 25-45 |  |
| shroomish | grass | common | 18.0 | 25-45 |  |
| foongus | grass/poison | common | 12.0 | 25-45 |  |
| morelull | grass/fairy | common | 9.0 | 25-45 |  |
| breloom | grass/fighting | uncommon | 6.0 | 25-45 |  |
| parasect | bug/grass | uncommon | 6.0 | 25-45 |  |
| toedscool | ground/grass | uncommon | 6.0 | 25-45 |  |
| shiinotic | grass/fairy | uncommon | 3.0 | 25-45 |  |
| amoonguss | grass/poison | ultra-rare | — | 25-45 |  |
| toedscruel | ground/grass | ultra-rare | — | 25-45 |  |

### `fungal_south` — unreachable

*biomes: mushroom_fields*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| shroomish | grass | common | 24.0 | 25-45 |  |
| poliwag | water | common | 18.0 | 25-45 |  |
| tympole | water | common | 9.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| wooper | water/ground | common | 9.0 | 25-45 |  |
| lechonk | normal | uncommon | 6.0 | 25-45 |  |
| poliwhirl | water | uncommon | 6.0 | 25-45 |  |
| palpitoad | water/ground | uncommon | 3.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| quagsire | water/ground | uncommon | 3.0 | 25-45 |  |
| politoed | water | ultra-rare | — | 25-45 |  |
| seismitoad | water/ground | ultra-rare | — | 25-45 | **UNKNOWN** no stock spawn data for this species |

### `glacial_tear_deep_valley` — habitat

*biomes: *

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| bergmite | ice | common | 24.0 | 27-36 |  |
| snom | ice/bug | common | 24.0 | 27-36 |  |
| cubchoo | ice | common | 12.0 | 27-36 |  |
| snorunt | ice | common | 12.0 | 27-36 |  |
| cryogonal | ice | uncommon | 6.0 | 27-36 |  |
| spheal | ice/water | uncommon | 6.0 | 27-36 |  |
| piplup | water | rare | 2.0 | 27-36 | **WATER** never spawns on dry land upstream (2/2 entries in water) |
| swinub | ice/ground | rare | 2.0 | 27-36 |  |
| avalugg | ice | ultra-rare | — | 27-36 |  |
| beartic | ice | ultra-rare | — | 27-36 |  |
| froslass | ice/ghost | ultra-rare | — | 27-36 |  |
| frosmoth | ice/bug | ultra-rare | — | 27-36 |  |

### `glacier_foot_fields` — route

*biomes: plains; ground y114–137 (median 118); 0.0% water; 185,984 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| lechonk | normal | common | 24.0 | 34-36 |  |
| wooper | water/ground | common | 24.0 | 34-36 | **YBAND** upstream maxY 62, this ground sits at y118 |
| hatenna | psychic | common | 9.0 | 34-36 |  |
| tarountula | bug | common | 9.0 | 34-36 | **BIOME** never spawns in plains upstream; upstream biomes are forest, spooky, swamp |
| toxel | electric/poison | uncommon | 6.0 | 34-36 |  |
| hattrem | psychic | uncommon | 3.0 | 34-36 |  |
| spidops | bug | uncommon | 3.0 | 34-36 | **BIOME** never spawns in plains upstream; upstream biomes are forest, spooky, swamp |
| hatterene | psychic/fairy | ultra-rare | — | 34-36 |  |
| oinkologne | normal | ultra-rare | — | 34-36 |  |
| toxtricity | electric/poison | ultra-rare | — | 34-36 |  |

### `great_crater` — unreachable

*biomes: stony_peaks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| magby | fire | common | 18.0 | 44-52 | **BIOME** never spawns in stony_peaks upstream; upstream biomes are #cobblemon:nether/is_basalt, #cobblemon:nether/is_wasteland, hills, volcanic |
| slugma | fire | common | 18.0 | 44-52 |  |
| numel | fire/ground | common | 9.0 | 44-52 | **BIOME** never spawns in stony_peaks upstream; upstream biomes are #cobblemon:nether/is_overgrowth, #cobblemon:nether/is_wasteland, badlands, volcanic |
| charmander | fire | common | 8.4 | 44-52 | **BIOME** never spawns in stony_peaks upstream; upstream biomes are #cobblemon:nether/is_basalt, hills, volcanic |
| magcargo | fire/rock | uncommon | 6.0 | 44-52 |  |
| magmar | fire | uncommon | 6.0 | 44-52 | **BIOME** never spawns in stony_peaks upstream; upstream biomes are #cobblemon:nether/is_basalt, #cobblemon:nether/is_wasteland, hills, volcanic |
| camerupt | fire/ground | uncommon | 3.0 | 44-52 | **BIOME** never spawns in stony_peaks upstream; upstream biomes are #cobblemon:nether/is_overgrowth, #cobblemon:nether/is_wasteland, badlands, volcanic |
| charmeleon | fire | uncommon | 2.76 | 44-52 | **BIOME** never spawns in stony_peaks upstream; upstream biomes are #cobblemon:nether/is_basalt, hills, volcanic |
| charizard | fire/flying | ultra-rare | 0.84 | 44-52 | **BIOME** never spawns in stony_peaks upstream; upstream biomes are #cobblemon:nether/is_basalt, hills, volcanic |
| magmortar | fire | ultra-rare | — | 44-52 | **BIOME** never spawns in stony_peaks upstream; upstream biomes are #cobblemon:nether/is_basalt, #cobblemon:nether/is_wasteland, hills, volcanic |

### `great_crater_bowls` — habitat

*biomes: *

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| numel | fire/ground | common | 18.0 | 44-50 |  |
| slugma | fire | common | 18.0 | 44-50 |  |
| salandit | poison/fire | common | 12.0 | 44-50 |  |
| torkoal | fire | common | 12.0 | 44-50 |  |
| camerupt | fire/ground | uncommon | 6.0 | 44-50 |  |
| magcargo | fire/rock | uncommon | 6.0 | 44-50 |  |
| sizzlipede | fire/bug | uncommon | 6.0 | 44-50 |  |
| rolycoly | rock | uncommon | 4.5 | 44-50 |  |
| heatmor | fire | rare | 2.0 | 44-50 |  |
| turtonator | fire/dragon | rare | 2.0 | 44-50 |  |
| carkol | rock/fire | rare | 1.5 | 44-50 |  |
| salazzle | poison/fire | ultra-rare | — | 44-50 | **UNKNOWN** no stock spawn data for this species |

### `jungle_east` — unreachable

*biomes: sparse_jungle*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| hawlucha | fighting/flying | common | 24.0 | 25-45 |  |
| pikipek | normal/flying | common | 24.0 | 25-45 |  |
| oranguru | normal/psychic | common | 12.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| passimian | fighting | common | 12.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| komala | normal | uncommon | 6.0 | 25-45 | **BIOME** never spawns in sparse_jungle upstream; upstream biomes are aether:skyroot_forest, aether:skyroot_woodland, savanna |
| shroodle | poison/normal | rare | 2.0 | 25-45 |  |
| grafaiai | poison/normal | ultra-rare | — | 25-45 |  |
| hakamoo | ? | ultra-rare | — | 25-45 |  |
| jangmoo | ? | ultra-rare | — | 25-45 |  |
| kommoo | ? | ultra-rare | — | 25-45 |  |

### `jungle_west` — unreachable

*biomes: jungle*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| aipom | normal | common | 24.0 | 25-45 |  |
| pikipek | normal/flying | common | 18.0 | 25-45 |  |
| kecleon | normal | common | 12.0 | 25-45 |  |
| slakoth | normal | common | 9.0 | 25-45 |  |
| heracross | bug/fighting | uncommon | 6.0 | 25-45 |  |
| tropius | grass/flying | uncommon | 6.0 | 25-45 |  |
| trumbeak | normal/flying | uncommon | 6.0 | 25-45 |  |
| vigoroth | normal | uncommon | 3.0 | 25-45 |  |
| ambipom | normal | ultra-rare | — | 25-45 |  |
| toucannon | normal/flying | ultra-rare | — | 25-45 |  |

### `lake_viltri_hollow` — route

*biomes: forest; ground y91–117 (median 106); 5.4% water; 98,496 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| hoothoot | normal/flying | common | 24.0 | 18-21 |  |
| lotad | water/grass | common | 18.0 | 18-21 |  |
| corphish | water | common | 12.0 | 18-21 |  |
| surskit | bug/water | common | 12.0 | 18-21 | **BIOME** never spawns in forest upstream; upstream biomes are #the_bumblezone:the_bumblezone, freshwater; **WATER** never spawns on dry land upstream (2/2 entries in water) |
| illumise | bug | uncommon | 6.0 | 18-21 | **BIOME** never spawns in forest upstream; upstream biomes are #the_bumblezone:the_bumblezone, freshwater, the_bumblezone:floral_meadow |
| lombre | water/grass | uncommon | 6.0 | 18-21 |  |
| volbeat | bug | uncommon | 6.0 | 18-21 | **BIOME** never spawns in forest upstream; upstream biomes are #the_bumblezone:the_bumblezone, freshwater, the_bumblezone:floral_meadow |
| crawdaunt | water/dark | ultra-rare | — | 18-21 |  |
| ludicolo | water/grass | ultra-rare | — | 18-21 |  |
| masquerain | bug/flying | ultra-rare | — | 18-21 | **BIOME** never spawns in forest upstream; upstream biomes are #the_bumblezone:the_bumblezone, freshwater; **WATER** never spawns on dry land upstream (2/2 entries in water) |

### `long_isle_middle` — unreachable

*biomes: forest*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| deerling | normal/grass | common | 24.0 | 25-45 |  |
| nincada | bug/ground | common | 18.0 | 25-45 |  |
| shedinja | bug/ghost | common | 12.0 | 25-45 |  |
| seedot | grass | common | 9.0 | 25-45 |  |
| applin | grass/dragon | uncommon | 6.0 | 25-45 |  |
| ninjask | bug/flying | uncommon | 6.0 | 25-45 |  |
| nuzleaf | grass/dark | uncommon | 3.0 | 25-45 |  |
| appletun | grass/dragon | ultra-rare | — | 25-45 |  |
| flapple | grass/dragon | ultra-rare | — | 25-45 |  |
| shiftry | grass/dark | ultra-rare | — | 25-45 |  |

### `long_isle_north` — unreachable

*biomes: taiga*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| deerling | normal/grass | common | 24.0 | 25-45 |  |
| zigzagoon | normal | common | 18.0 | 25-45 |  |
| nickit | dark | common | 9.0 | 25-45 |  |
| rookidee | flying | common | 9.0 | 25-45 |  |
| linoone | normal | uncommon | 6.0 | 25-45 |  |
| skwovet | normal | uncommon | 4.5 | 25-45 |  |
| corvisquire | flying | uncommon | 3.0 | 25-45 |  |
| thievul | dark | uncommon | 3.0 | 25-45 |  |
| greedent | normal | rare | 1.5 | 25-45 |  |
| sawsbuck | normal/grass | ultra-rare | — | 25-45 |  |

### `long_isle_south` — unreachable

*biomes: sparse_jungle*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| chatot | normal/flying | common | 24.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| deerling | normal/grass | common | 24.0 | 25-45 | **BIOME** never spawns in sparse_jungle upstream; upstream biomes are #aether:is_aether, floral, forest, hills, plains, snowy_forest |
| fomantis | grass | common | 12.0 | 25-45 |  |
| bounsweet | grass | common | 9.0 | 25-45 |  |
| squawkabilly | normal/flying | uncommon | 6.0 | 25-45 |  |
| wimpod | bug/water | uncommon | 6.0 | 25-45 |  |
| steenee | grass | uncommon | 3.0 | 25-45 |  |
| golisopod | bug/water | ultra-rare | — | 25-45 |  |
| lurantis | grass | ultra-rare | — | 25-45 |  |
| tsareena | grass | ultra-rare | — | 25-45 |  |

### `lower_trough` — unreachable

*biomes: snowy_plains*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| bergmite | ice | common | 24.0 | 27-38 | **BIOME** never spawns in snowy_plains upstream; upstream biomes are #cobblemon:nether/is_frozen, frozen_ocean, glacial |
| spheal | ice/water | common | 24.0 | 27-38 | **BIOME** never spawns in snowy_plains upstream; upstream biomes are cold_ocean, frozen_ocean |
| buizel | water | common | 9.0 | 27-38 | **BIOME** never spawns in snowy_plains upstream; upstream biomes are forest, freshwater, grassland, hills, jungle, taiga |
| piplup | water | common | 9.0 | 27-38 | **WATER** never spawns on dry land upstream (2/2 entries in water) |
| bidoof | normal | uncommon | 6.0 | 27-38 | **BIOME** never spawns in snowy_plains upstream; upstream biomes are forest, freshwater, snowy_forest, taiga; **WATER** never spawns on dry land upstream (2/2 entries in water) |
| floatzel | water | uncommon | 3.0 | 27-38 | **BIOME** never spawns in snowy_plains upstream; upstream biomes are forest, freshwater, grassland, hills, jungle, taiga |
| prinplup | water | uncommon | 3.0 | 27-38 |  |
| empoleon | water/steel | ultra-rare | — | 27-38 | **WATER** never spawns on dry land upstream (2/2 entries in water) |
| sealeo | ice/water | ultra-rare | — | 27-38 | **BIOME** never spawns in snowy_plains upstream; upstream biomes are cold_ocean, frozen_ocean |
| walrein | ice/water | ultra-rare | — | 27-38 | **BIOME** never spawns in snowy_plains upstream; upstream biomes are cold_ocean, frozen_ocean |

### `marsh_creek` — route

*biomes: swamp; ground y102–131 (median 118); 0.0% water; 59,648 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| wooper | water/ground | common | 24.0 | 37-39 | **YBAND** upstream maxY 62, this ground sits at y118 |
| poliwag | water | common | 18.0 | 37-39 | **YBAND** upstream maxY 9, this ground sits at y118 |
| barboach | water/ground | common | 9.0 | 37-39 | **WATER** never spawns on dry land upstream (6/6 entries in water) |
| tympole | water | common | 8.4 | 37-39 | **UNKNOWN** no stock spawn data for this species |
| poliwhirl | water | uncommon | 6.0 | 37-39 | **YBAND** upstream maxY 9, this ground sits at y118 |
| whiscash | water/ground | uncommon | 3.0 | 37-39 | **WATER** never spawns on dry land upstream (9/9 entries in water) |
| palpitoad | water/ground | uncommon | 2.76 | 37-39 | **UNKNOWN** no stock spawn data for this species |
| seismitoad | water/ground | ultra-rare | 0.84 | 37-39 | **UNKNOWN** no stock spawn data for this species |
| politoed | water | ultra-rare | — | 37-39 | **YBAND** upstream maxY 9, this ground sits at y118 |
| poliwrath | water/fighting | ultra-rare | — | 37-39 | **YBAND** upstream maxY 9, this ground sits at y118 |

### `marshy_marsh` — unreachable

*biomes: swamp*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| wooper | water/ground | common | 18.0 | 34-44 |  |
| totodile | water | common | 16.8 | 34-44 |  |
| croagunk | poison/fighting | common | 12.0 | 34-44 |  |
| gulpin | poison | common | 9.0 | 34-44 | **UNKNOWN** no stock spawn data for this species |
| carnivine | grass | uncommon | 6.0 | 34-44 |  |
| quagsire | water/ground | uncommon | 6.0 | 34-44 |  |
| croconaw | water | uncommon | 5.52 | 34-44 |  |
| swalot | poison | uncommon | 3.0 | 34-44 | **UNKNOWN** no stock spawn data for this species |
| feraligatr | water | ultra-rare | 1.68 | 34-44 |  |
| toxicroak | poison/fighting | ultra-rare | — | 34-44 |  |

### `marshy_marsh_basin` — habitat

*biomes: *

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| totodile | water | common | 24.0 | 35-43 |  |
| wooper | water/ground | common | 18.0 | 35-43 |  |
| croagunk | poison/fighting | common | 12.0 | 35-43 |  |
| gulpin | poison | common | 9.0 | 35-43 | **UNKNOWN** no stock spawn data for this species |
| carnivine | grass | uncommon | 6.0 | 35-43 |  |
| quagsire | water/ground | uncommon | 6.0 | 35-43 |  |
| tympole | water | uncommon | 6.0 | 35-43 | **UNKNOWN** no stock spawn data for this species |
| swalot | poison | uncommon | 3.0 | 35-43 | **UNKNOWN** no stock spawn data for this species |
| barboach | water/ground | rare | 2.0 | 35-43 | **WATER** never spawns on dry land upstream (6/6 entries in water) |
| foongus | grass/poison | ultra-rare | 1.0 | 35-43 |  |
| goomy | dragon | ultra-rare | — | 35-43 |  |
| toxicroak | poison/fighting | ultra-rare | — | 35-43 |  |

### `merian_cirque` — route

*biomes: snowy_plains; ground y107–182 (median 116); 0.0% water; 119,552 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| bergmite | ice | common | 24.0 | 27-29 | **BIOME** never spawns in snowy_plains upstream; upstream biomes are #cobblemon:nether/is_frozen, frozen_ocean, glacial |
| smoochum | ice/psychic | common | 24.0 | 27-29 | **UNKNOWN** no stock spawn data for this species |
| cryogonal | ice | common | 12.0 | 27-29 |  |
| swablu | normal/flying | common | 12.0 | 27-29 |  |
| drampa | normal/dragon | uncommon | 6.0 | 27-29 | **YBAND** upstream minY 192, this ground sits at y116 |
| meditite | fighting/psychic | uncommon | 6.0 | 27-29 |  |
| altaria | dragon/flying | ultra-rare | — | 27-29 |  |
| avalugg | ice | ultra-rare | — | 27-29 | **BIOME** never spawns in snowy_plains upstream; upstream biomes are #cobblemon:nether/is_frozen, frozen_ocean, glacial |
| jynx | ice/psychic | ultra-rare | — | 27-29 |  |
| medicham | fighting/psychic | ultra-rare | — | 27-29 |  |

### `mining_town_fossil_levels` — habitat

*biomes: *

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| aron | steel/rock | common | 18.0 | 42-50 |  |
| roggenrola | rock | common | 18.0 | 42-50 |  |
| drilbur | ground | common | 12.0 | 42-50 |  |
| rolycoly | rock | common | 9.0 | 42-50 |  |
| boldore | rock | uncommon | 6.0 | 42-50 |  |
| carbink | rock/fairy | uncommon | 6.0 | 42-50 |  |
| lairon | steel/rock | uncommon | 6.0 | 42-50 |  |
| onix | rock/ground | uncommon | 6.0 | 42-50 |  |
| carkol | rock/fire | uncommon | 3.0 | 42-50 |  |
| glimmet | rock/poison | rare | 2.0 | 42-50 |  |
| sableye | dark/ghost | rare | 2.0 | 42-50 |  |
| nosepass | rock | ultra-rare | 1.0 | 42-50 |  |

### `mt_clay` — route

*biomes: grove, jagged_peaks, snowy_slopes; ground y138–220 (median 166); 0.0% water; 118,336 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| rockruff | rock | common | 24.0 | 22-25 |  |
| swablu | normal/flying | common | 24.0 | 22-25 |  |
| machop | fighting | common | 12.0 | 22-25 |  |
| makuhita | fighting | common | 12.0 | 22-25 |  |
| rufflet | normal/flying | uncommon | 6.0 | 22-25 |  |
| braviary | normal/flying | ultra-rare | — | 22-25 |  |
| hariyama | fighting | ultra-rare | — | 22-25 |  |
| lycanroc | rock | ultra-rare | — | 22-25 |  |
| machamp | fighting | ultra-rare | — | 22-25 |  |
| machoke | fighting | ultra-rare | — | 22-25 |  |

### `mt_vessu` — route

*biomes: grove, jagged_peaks, snowy_slopes; ground y138–172 (median 148); 0.0% water; 32,384 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| swablu | normal/flying | common | 24.0 | 24-26 |  |
| skiddo | grass | common | 12.0 | 24-26 |  |
| drampa | normal/dragon | uncommon | 6.0 | 24-26 | **YBAND** upstream minY 192, this ground sits at y148 |
| meditite | fighting/psychic | uncommon | 6.0 | 24-26 |  |
| bagon | dragon | ultra-rare | — | 24-26 |  |
| larvitar | rock/ground | ultra-rare | — | 24-26 |  |
| medicham | fighting/psychic | ultra-rare | — | 24-26 |  |
| pupitar | rock/ground | ultra-rare | — | 24-26 |  |
| shelgon | dragon | ultra-rare | — | 24-26 | **BIOME** never spawns in grove, jagged_peaks, snowy_slopes upstream; upstream biomes are #aether:is_aether, dripstone |
| tyranitar | rock/dark | ultra-rare | — | 24-26 |  |

### `north_east_downs` — route

*biomes: taiga; ground y114–118 (median 116); 0.0% water; 17,984 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| wooloo | normal | common | 24.0 | 32-34 | **BIOME** never spawns in taiga upstream; upstream biomes are aether:skyroot_grove, aether:skyroot_meadow, mountain, plains |
| sentret | normal | common | 18.0 | 32-34 |  |
| stunky | poison/dark | common | 12.0 | 32-34 |  |
| starly | normal/flying | common | 9.0 | 32-34 | **UNKNOWN** no stock spawn data for this species |
| furret | normal | uncommon | 6.0 | 32-34 |  |
| nickit | dark | uncommon | 4.5 | 32-34 |  |
| staravia | normal/flying | uncommon | 3.0 | 32-34 | **UNKNOWN** no stock spawn data for this species |
| thievul | dark | rare | 1.5 | 32-34 |  |
| skuntank | poison/dark | ultra-rare | — | 32-34 |  |
| staraptor | normal/flying | ultra-rare | — | 32-34 |  |

### `north_pine_isle` — unreachable

*biomes: snowy_taiga*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| snom | ice/bug | common | 24.0 | 25-45 |  |
| snover | grass/ice | common | 24.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| sandshrew alolan | ground | common | 12.0 | 25-45 |  |
| vulpix alolan | fire | common | 12.0 | 25-45 |  |
| delibird | ice/flying | uncommon | 6.0 | 25-45 | **BIOME** never spawns in snowy_taiga upstream; upstream biomes are #aether:is_aether, peak |
| stantler | normal | uncommon | 6.0 | 25-45 |  |
| sneasel | dark/ice | rare | 2.0 | 25-45 |  |
| abomasnow | grass/ice | ultra-rare | — | 25-45 | **UNKNOWN** no stock spawn data for this species |
| frosmoth | ice/bug | ultra-rare | — | 25-45 |  |
| wyrdeer | normal/psychic | ultra-rare | — | 25-45 |  |

### `north_shore_downs` — unreachable

*biomes: meadow*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| wooloo | normal | common | 18.0 | 30-38 |  |
| hoppip | grass/flying | common | 16.8 | 30-38 |  |
| buneary | normal | common | 12.0 | 30-38 |  |
| minccino | normal | common | 12.0 | 30-38 |  |
| dubwool | normal | uncommon | 6.0 | 30-38 |  |
| fletchling | normal/flying | uncommon | 6.0 | 30-38 | **BIOME** never spawns in meadow upstream; upstream biomes are #cobblemon:nether/is_forest, #cobblemon:nether/is_fungus, aether:skyroot_forest, aether:skyroot_woodland, forest, sky |
| skiploom | grass/flying | uncommon | 5.52 | 30-38 |  |
| jumpluff | grass/flying | ultra-rare | 1.68 | 30-38 |  |
| cinccino | normal | ultra-rare | — | 30-38 |  |
| lopunny | normal | ultra-rare | — | 30-38 |  |

### `north_west_coast` — unreachable

*biomes: plains*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| hoothoot | normal/flying | common | 24.0 | 15-28 | **BIOME** never spawns in plains upstream; upstream biomes are forest, sky, spooky |
| shellder | water | common | 24.0 | 15-28 | **WATER** never spawns on dry land upstream (8/8 entries in water) |
| krabby | water | common | 12.0 | 15-28 |  |
| wingull | water/flying | common | 12.0 | 15-28 | **BIOME** never spawns in plains upstream; upstream biomes are coast, ocean, sky, tropical_island |
| binacle | rock/water | uncommon | 6.0 | 15-28 | **BIOME** never spawns in plains upstream; upstream biomes are coast, ocean |
| inkay | dark/psychic | uncommon | 6.0 | 15-28 |  |
| cloyster | water/ice | ultra-rare | — | 15-28 | **WATER** never spawns on dry land upstream (8/8 entries in water) |
| kingler | water | ultra-rare | — | 15-28 |  |
| malamar | dark/psychic | ultra-rare | — | 15-28 |  |
| pelipper | water/flying | ultra-rare | — | 15-28 | **BIOME** never spawns in plains upstream; upstream biomes are coast, ocean, sky, tropical_island |

### `northgate_east` — unreachable

*biomes: taiga*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| pineco | bug | common | 24.0 | 25-45 |  |
| sentret | normal | common | 18.0 | 25-45 |  |
| deerling | normal/grass | common | 12.0 | 25-45 |  |
| starly | normal/flying | common | 9.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| furret | normal | uncommon | 6.0 | 25-45 |  |
| pachirisu | electric | uncommon | 6.0 | 25-45 | **BIOME** never spawns in taiga upstream; upstream biomes are aether:skyroot_forest, aether:skyroot_woodland, forest |
| skwovet | normal | uncommon | 4.5 | 25-45 |  |
| staravia | normal/flying | uncommon | 3.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| greedent | normal | rare | 1.5 | 25-45 |  |
| sawsbuck | normal/grass | ultra-rare | — | 25-45 |  |

### `northgate_old_growth_grove` — habitat

*biomes: *

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| pineco | bug | common | 24.0 | 25-45 |  |
| teddiursa | normal | common | 24.0 | 25-45 |  |
| stantler | normal | common | 12.0 | 25-45 |  |
| hoothoot | normal/flying | common | 9.0 | 25-45 |  |
| phantump | ghost/grass | uncommon | 6.0 | 25-45 |  |
| noctowl | normal/flying | uncommon | 3.0 | 25-45 |  |
| sneasel | dark/ice | rare | 2.0 | 25-45 |  |
| forretress | bug/steel | ultra-rare | — | 25-45 |  |
| sawsbuck | normal/grass | ultra-rare | — | 25-45 |  |
| trevenant | ghost/grass | ultra-rare | — | 25-45 |  |
| ursaring | normal | ultra-rare | — | 25-45 |  |
| wyrdeer | normal/psychic | ultra-rare | — | 25-45 |  |

### `northgate_west` — unreachable

*biomes: old_growth_spruce_taiga*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| pineco | bug | common | 24.0 | 25-45 |  |
| teddiursa | normal | common | 24.0 | 25-45 |  |
| hoothoot | normal/flying | common | 9.0 | 25-45 | **BIOME** never spawns in old_growth_spruce_taiga upstream; upstream biomes are forest, sky, spooky |
| spinarak | bug/poison | common | 9.0 | 25-45 |  |
| phantump | ghost/grass | uncommon | 6.0 | 25-45 |  |
| stantler | normal | uncommon | 6.0 | 25-45 | **BIOME** never spawns in old_growth_spruce_taiga upstream; upstream biomes are #aether:is_aether, snowy_forest, snowy_taiga, tundra |
| ariados | bug/poison | uncommon | 3.0 | 25-45 |  |
| noctowl | normal/flying | uncommon | 3.0 | 25-45 | **BIOME** never spawns in old_growth_spruce_taiga upstream; upstream biomes are forest, sky, spooky |
| forretress | bug/steel | ultra-rare | — | 25-45 |  |
| ursaring | normal | ultra-rare | — | 25-45 |  |

### `pallet_meadows` — route

*biomes: plains; ground y113–128 (median 120); 0.0% water; 80,832 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| pidgey | normal/flying | common | 24.0 | 5-8 |  |
| rattata | normal | common | 24.0 | 5-8 | **YBAND** upstream maxY 0, this ground sits at y120 |
| mareep | electric | common | 12.0 | 5-8 |  |
| wooloo | normal | common | 12.0 | 5-8 |  |
| ampharos | electric | ultra-rare | — | 5-8 |  |
| dubwool | normal | ultra-rare | — | 5-8 |  |
| flaaffy | electric | ultra-rare | — | 5-8 |  |
| pidgeot | normal/flying | ultra-rare | — | 5-8 |  |
| pidgeotto | normal/flying | ultra-rare | — | 5-8 |  |
| raticate | normal | ultra-rare | — | 5-8 | **YBAND** upstream maxY 0, this ground sits at y120 |

### `peak_pond_hollow` — route

*biomes: old_growth_spruce_taiga; ground y96–128 (median 110); 0.4% water; 225,856 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| wooloo | normal | common | 24.0 | 30-32 | **BIOME** never spawns in old_growth_spruce_taiga upstream; upstream biomes are aether:skyroot_grove, aether:skyroot_meadow, mountain, plains |
| mareep | electric | common | 16.8 | 30-32 | **BIOME** never spawns in old_growth_spruce_taiga upstream; upstream biomes are highlands, plains |
| emolga | electric/flying | common | 12.0 | 30-32 |  |
| pichu | electric | common | 12.0 | 30-32 | **BIOME** never spawns in old_growth_spruce_taiga upstream; upstream biomes are aether:skyroot_forest, aether:skyroot_woodland, beach, forest, tropical_island |
| flaaffy | electric | uncommon | 5.52 | 30-32 | **BIOME** never spawns in old_growth_spruce_taiga upstream; upstream biomes are highlands, plains |
| teddiursa | normal | uncommon | 4.5 | 30-32 |  |
| ampharos | electric | ultra-rare | 1.68 | 30-32 | **BIOME** never spawns in old_growth_spruce_taiga upstream; upstream biomes are highlands, plains |
| ursaring | normal | rare | 1.5 | 30-32 |  |
| pikachu | electric | ultra-rare | — | 30-32 | **BIOME** never spawns in old_growth_spruce_taiga upstream; upstream biomes are aether:skyroot_forest, aether:skyroot_woodland, beach, forest, tropical_island |
| raichu | electric | ultra-rare | — | 30-32 | **BIOME** never spawns in old_growth_spruce_taiga upstream; upstream biomes are aether:skyroot_forest, aether:skyroot_woodland, beach, forest, tropical_island |

### `plateau_east` — unreachable

*biomes: eroded_badlands*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| cacnea | grass | common | 24.0 | 47-54 |  |
| houndour | dark/fire | common | 18.0 | 47-54 |  |
| larvesta | bug/fire | common | 12.0 | 47-54 | **BIOME** never spawns in eroded_badlands upstream; upstream biomes are #aether:is_aether, #cobblemon:nether/is_crimson, #cobblemon:nether/is_forest, desert, jungle |
| litleo | fire/normal | common | 9.0 | 47-54 | **BIOME** never spawns in eroded_badlands upstream; upstream biomes are #cobblemon:nether/is_overgrowth, #cobblemon:nether/is_wasteland, savanna |
| durant | bug/steel | uncommon | 6.0 | 47-54 |  |
| heatmor | fire | uncommon | 6.0 | 47-54 |  |
| houndoom | dark/fire | uncommon | 6.0 | 47-54 |  |
| pyroar | fire/normal | uncommon | 3.0 | 47-54 | **BIOME** never spawns in eroded_badlands upstream; upstream biomes are #cobblemon:nether/is_overgrowth, #cobblemon:nether/is_wasteland, savanna |
| orthworm | steel | rare | 2.0 | 47-54 |  |
| volcarona | bug/fire | ultra-rare | — | 47-54 | **BIOME** never spawns in eroded_badlands upstream; upstream biomes are #aether:is_aether, #cobblemon:nether/is_crimson, #cobblemon:nether/is_forest, desert, jungle |

### `plateau_south` — unreachable

*biomes: eroded_badlands*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| cacnea | grass | common | 24.0 | 47-54 |  |
| phanpy | ground | common | 18.0 | 47-54 |  |
| dwebble | bug/rock | common | 9.0 | 47-54 |  |
| mudbray | ground | common | 9.0 | 47-54 |  |
| bramblin | grass/ghost | uncommon | 6.0 | 47-54 |  |
| donphan | ground | uncommon | 6.0 | 47-54 |  |
| klawf | rock | uncommon | 6.0 | 47-54 |  |
| crustle | bug/rock | uncommon | 3.0 | 47-54 |  |
| mudsdale | ground | uncommon | 3.0 | 47-54 |  |
| brambleghast | grass/ghost | ultra-rare | — | 47-54 |  |

### `plateau_west` — route

*biomes: badlands, wooded_badlands; ground y123–157 (median 153); 0.0% water; 191,936 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| cacnea | grass | common | 18.0 | 47-49 |  |
| skorupi | poison/bug | common | 18.0 | 47-49 |  |
| vullaby | dark/flying | common | 12.0 | 47-49 | **UNKNOWN** no stock spawn data for this species |
| sandile | ground/dark | common | 8.4 | 47-49 | **BIOME** never spawns in badlands, wooded_badlands upstream; upstream biomes are desert |
| cacturne | grass/dark | uncommon | 6.0 | 47-49 |  |
| drapion | poison/dark | uncommon | 6.0 | 47-49 |  |
| maractus | grass | uncommon | 6.0 | 47-49 |  |
| krokorok | ground/dark | uncommon | 2.76 | 47-49 | **BIOME** never spawns in badlands, wooded_badlands upstream; upstream biomes are desert |
| krookodile | ground/dark | ultra-rare | 0.84 | 47-49 | **BIOME** never spawns in badlands, wooded_badlands upstream; upstream biomes are desert |
| mandibuzz | dark/flying | ultra-rare | — | 47-49 | **UNKNOWN** no stock spawn data for this species |

### `rift_depths` — habitat

*biomes: *

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| roggenrola | rock | common | 24.0 | 50-59 |  |
| rolycoly | rock | common | 24.0 | 50-59 |  |
| glimmet | rock/poison | common | 12.0 | 50-59 |  |
| nacli | rock | common | 12.0 | 50-59 |  |
| baltoy | ground/psychic | uncommon | 6.0 | 50-59 |  |
| golett | ground/ghost | uncommon | 6.0 | 50-59 |  |
| cubone | ground | rare | 2.0 | 50-59 |  |
| dwebble | bug/rock | rare | 2.0 | 50-59 |  |
| bronzor | steel/psychic | ultra-rare | 1.0 | 50-59 |  |
| klink | steel | ultra-rare | 1.0 | 50-59 |  |
| orthworm | steel | ultra-rare | 1.0 | 50-59 |  |
| runerigus | ground/ghost | ultra-rare | 1.0 | 50-59 |  |

### `rift_foot` — route

*biomes: savanna; ground y99–133 (median 106); 0.0% water; 171,648 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| wattrel | electric/flying | common | 24.0 | 49-51 | **BIOME** never spawns in savanna upstream; upstream biomes are coast, island, ocean, sky |
| nidoranf | ? | common | 18.0 | 49-51 |  |
| nidoranm | ? | common | 9.0 | 49-51 |  |
| poochyena | dark | common | 9.0 | 49-51 |  |
| mudbray | ground | uncommon | 6.0 | 49-51 |  |
| nidorina | poison | uncommon | 6.0 | 49-51 |  |
| mightyena | dark | uncommon | 3.0 | 49-51 |  |
| nidorino | poison | uncommon | 3.0 | 49-51 |  |
| nidoking | poison/ground | ultra-rare | — | 49-51 |  |
| nidoqueen | poison/ground | ultra-rare | — | 49-51 |  |

### `rift_south_east_arm` — route

*biomes: windswept_gravelly_hills; ground y83–101 (median 87); 0.0% water; 100,864 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| gligar | ground/flying | common | 24.0 | 54-56 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are #cobblemon:nether/is_mountain, badlands, taiga |
| rolycoly | rock | common | 24.0 | 54-56 |  |
| baltoy | ground/psychic | common | 9.0 | 54-56 |  |
| golett | ground/ghost | common | 9.0 | 54-56 |  |
| druddigon | dragon | uncommon | 6.0 | 54-56 |  |
| solrock | rock/psychic | uncommon | 6.0 | 54-56 |  |
| claydol | ground/psychic | uncommon | 3.0 | 54-56 |  |
| golurk | ground/ghost | uncommon | 3.0 | 54-56 |  |
| lunatone | rock/psychic | rare | 2.0 | 54-56 |  |
| gliscor | ground/flying | ultra-rare | — | 54-56 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are #cobblemon:nether/is_mountain, badlands, taiga |

### `rift_south_west_arm` — route

*biomes: windswept_gravelly_hills; ground y83–114 (median 88); 0.0% water; 92,032 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| cubone | ground | common | 24.0 | 53-55 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are #cobblemon:nether/is_desert, badlands, desert, volcanic |
| rolycoly | rock | common | 24.0 | 53-55 |  |
| dwebble | bug/rock | common | 9.0 | 53-55 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are badlands |
| scraggy | dark/fighting | common | 9.0 | 53-55 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are arid, badlands |
| runerigus | ground/ghost | uncommon | 6.0 | 53-55 | **YBAND** upstream maxY 10, this ground sits at y88 |
| glimmet | rock/poison | uncommon | 4.5 | 53-55 |  |
| crustle | bug/rock | uncommon | 3.0 | 53-55 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are badlands |
| scrafty | dark/fighting | uncommon | 3.0 | 53-55 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are arid, badlands |
| glimmora | rock/poison | rare | 1.5 | 53-55 |  |
| marowak | ground | ultra-rare | — | 53-55 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are #cobblemon:nether/is_desert, badlands, desert, volcanic |

### `rift_trunk` — route

*biomes: windswept_gravelly_hills; ground y82–120 (median 84); 0.0% water; 193,984 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| roggenrola | rock | common | 18.0 | 55-57 | **YBAND** upstream maxY 0, this ground sits at y84 |
| rolycoly | rock | common | 16.8 | 55-57 |  |
| orthworm | steel | common | 12.0 | 55-57 |  |
| nacli | rock | common | 8.4 | 55-57 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are #cobblemon:nether/is_quartz, badlands |
| boldore | rock | uncommon | 6.0 | 55-57 | **YBAND** upstream maxY 0, this ground sits at y84 |
| carkol | rock/fire | uncommon | 5.52 | 55-57 |  |
| naclstack | rock | uncommon | 2.76 | 55-57 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are #cobblemon:nether/is_quartz, badlands |
| coalossal | rock/fire | ultra-rare | 1.68 | 55-57 |  |
| garganacl | rock | ultra-rare | 0.84 | 55-57 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are #cobblemon:nether/is_quartz, badlands |
| gigalith | rock | ultra-rare | — | 55-57 | **YBAND** upstream maxY 0, this ground sits at y84 |

### `rift_west_spur` — route

*biomes: windswept_gravelly_hills; ground y82–120 (median 118); 0.0% water; 18,368 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| rolycoly | rock | common | 24.0 | 56-58 |  |
| klink | steel | common | 16.8 | 56-58 |  |
| bronzor | steel/psychic | common | 9.0 | 56-58 | **YBAND** upstream maxY 10, this ground sits at y118 |
| varoom | steel/poison | common | 9.0 | 56-58 |  |
| klang | steel | uncommon | 5.52 | 56-58 |  |
| pawniard | dark/steel | uncommon | 4.5 | 56-58 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are bamboo, river |
| bronzong | steel/psychic | uncommon | 3.0 | 56-58 | **YBAND** upstream maxY 10, this ground sits at y118 |
| revavroom | steel/poison | uncommon | 3.0 | 56-58 |  |
| klinklang | steel | ultra-rare | 1.68 | 56-58 |  |
| bisharp | dark/steel | rare | 1.5 | 56-58 | **BIOME** never spawns in windswept_gravelly_hills upstream; upstream biomes are bamboo, river |

### `river_of_shrews_vale` — route

*biomes: plains; ground y117–127 (median 123); 0.0% water; 86,912 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| buizel | water | common | 24.0 | 9-12 |  |
| surskit | bug/water | common | 24.0 | 9-12 | **BIOME** never spawns in plains upstream; upstream biomes are #the_bumblezone:the_bumblezone, freshwater; **WATER** never spawns on dry land upstream (2/2 entries in water) |
| bidoof | normal | common | 12.0 | 9-12 | **BIOME** never spawns in plains upstream; upstream biomes are forest, freshwater, snowy_forest, taiga; **WATER** never spawns on dry land upstream (2/2 entries in water) |
| pawmi | electric | common | 12.0 | 9-12 | **UNKNOWN** no stock spawn data for this species |
| deerling | normal/grass | uncommon | 6.0 | 9-12 |  |
| bibarel | normal/water | ultra-rare | — | 9-12 | **BIOME** never spawns in plains upstream; upstream biomes are forest, freshwater, snowy_forest, taiga; **WATER** never spawns on dry land upstream (2/2 entries in water) |
| floatzel | water | ultra-rare | — | 9-12 |  |
| pawmo | electric/fighting | ultra-rare | — | 9-12 | **UNKNOWN** no stock spawn data for this species |
| pawmot | electric/fighting | ultra-rare | — | 9-12 | **UNKNOWN** no stock spawn data for this species |
| sawsbuck | normal/grass | ultra-rare | — | 9-12 |  |

### `route_1_ghost_mansion` — habitat

*biomes: *

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| gastly | ghost/poison | common | 24.0 | 6-15 |  |
| misdreavus | ghost | common | 24.0 | 6-15 |  |
| duskull | ghost | common | 12.0 | 6-15 |  |
| shuppet | ghost | common | 12.0 | 6-15 |  |
| litwick | ghost/fire | uncommon | 6.0 | 6-15 |  |
| phantump | ghost/grass | uncommon | 6.0 | 6-15 |  |
| greavard | ghost | rare | 2.0 | 6-15 | **UNKNOWN** no stock spawn data for this species |
| sinistea | ghost | rare | 2.0 | 6-15 |  |
| murkrow | dark/flying | ultra-rare | 1.0 | 6-15 |  |
| sableye | dark/ghost | ultra-rare | 1.0 | 6-15 |  |
| zorua | dark | ultra-rare | 1.0 | 6-15 |  |
| banette | ghost | ultra-rare | — | 6-15 |  |
| haunter | ghost/poison | ultra-rare | — | 6-15 |  |
| mismagius | ghost | ultra-rare | — | 6-15 |  |

### `shrew_lake_shores` — unreachable

*biomes: cherry_grove*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| cherubi | grass | common | 24.0 | 10-22 |  |
| surskit | bug/water | common | 24.0 | 10-22 | **BIOME** never spawns in cherry_grove upstream; upstream biomes are #the_bumblezone:the_bumblezone, freshwater; **WATER** never spawns on dry land upstream (2/2 entries in water) |
| poltchageist | grass/ghost | common | 12.0 | 10-22 |  |
| ralts | psychic/fairy | common | 12.0 | 10-22 |  |
| togepi | fairy | uncommon | 6.0 | 10-22 |  |
| cherrim | grass | ultra-rare | — | 10-22 |  |
| gallade | psychic/fighting | ultra-rare | — | 10-22 |  |
| gardevoir | psychic/fairy | ultra-rare | — | 10-22 |  |
| kirlia | psychic/fairy | ultra-rare | — | 10-22 |  |
| sinistcha | grass/ghost | ultra-rare | — | 10-22 |  |

### `south_east_dunes` — unreachable

*biomes: desert*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| hippopotas | ground | common | 24.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| sandile | ground/dark | common | 24.0 | 25-45 |  |
| flittle | psychic | common | 12.0 | 25-45 |  |
| rellor | bug | common | 12.0 | 25-45 |  |
| helioptile | electric/normal | uncommon | 6.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| sigilyph | psychic/flying | uncommon | 6.0 | 25-45 |  |
| espathra | psychic | ultra-rare | — | 25-45 |  |
| heliolisk | electric/normal | ultra-rare | — | 25-45 | **UNKNOWN** no stock spawn data for this species |
| hippowdon | ground | ultra-rare | — | 25-45 | **UNKNOWN** no stock spawn data for this species |
| rabsca | bug/psychic | ultra-rare | — | 25-45 |  |

### `south_pine_isle` — unreachable

*biomes: snowy_taiga*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| snover | grass/ice | common | 24.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| vulpix alolan | fire | common | 24.0 | 25-45 |  |
| buneary | normal | common | 12.0 | 25-45 |  |
| zorua | dark | common | 12.0 | 25-45 |  |
| rowlet | grass/flying | uncommon | 4.5 | 25-45 |  |
| dartrix | grass/flying | rare | 1.5 | 25-45 |  |
| decidueye | grass/ghost | ultra-rare | — | 25-45 |  |
| lopunny | normal | ultra-rare | — | 25-45 |  |
| ninetales alolan | fire | ultra-rare | — | 25-45 |  |
| zoroark | dark | ultra-rare | — | 25-45 |  |

### `south_strand` — route

*biomes: plains; ground y99–115 (median 107); 0.0% water; 127,616 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| mareanie | poison/water | common | 18.0 | 50-52 | **BIOME** never spawns in plains upstream; upstream biomes are coast, warm_ocean |
| wattrel | electric/flying | common | 18.0 | 50-52 | **BIOME** never spawns in plains upstream; upstream biomes are coast, island, ocean, sky |
| clauncher | water | common | 9.0 | 50-52 | **BIOME** never spawns in plains upstream; upstream biomes are coast, ocean; **WATER** never spawns on dry land upstream (3/3 entries in water); **COAST** coast/ocean species; this scope is 0.0% water |
| wimpod | bug/water | common | 9.0 | 50-52 | **YBAND** upstream maxY 0, this ground sits at y107 |
| crabrawler | fighting | uncommon | 6.0 | 50-52 | **BIOME** never spawns in plains upstream; upstream biomes are coast; **COAST** coast/ocean species; this scope is 0.0% water |
| kilowattrel | electric/flying | uncommon | 6.0 | 50-52 | **BIOME** never spawns in plains upstream; upstream biomes are coast, island, ocean, sky |
| pincurchin | electric | uncommon | 6.0 | 50-52 | **WATER** never spawns on dry land upstream (8/8 entries in water); **YBAND** upstream maxY 13, this ground sits at y107 |
| toxapex | poison/water | uncommon | 6.0 | 50-52 | **BIOME** never spawns in plains upstream; upstream biomes are coast, warm_ocean |
| clawitzer | water | uncommon | 3.0 | 50-52 | **BIOME** never spawns in plains upstream; upstream biomes are coast, ocean; **WATER** never spawns on dry land upstream (4/4 entries in water); **COAST** coast/ocean species; this scope is 0.0% water |
| golisopod | bug/water | uncommon | 3.0 | 50-52 | **YBAND** upstream maxY 0, this ground sits at y107 |

### `south_west_fields` — unreachable

*biomes: sunflower_plains*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| caterpie | bug | common | 24.0 | 5-15 |  |
| pidgey | normal/flying | common | 24.0 | 5-15 |  |
| cottonee | grass/fairy | common | 12.0 | 5-15 |  |
| hoppip | grass/flying | common | 12.0 | 5-15 |  |
| smoliv | grass/normal | uncommon | 6.0 | 5-15 | **BIOME** never spawns in sunflower_plains upstream; upstream biomes are savanna |
| butterfree | bug/flying | ultra-rare | — | 5-15 |  |
| jumpluff | grass/flying | ultra-rare | — | 5-15 |  |
| metapod | bug | ultra-rare | — | 5-15 |  |
| skiploom | grass/flying | ultra-rare | — | 5-15 |  |
| whimsicott | grass/fairy | ultra-rare | — | 5-15 |  |

### `sunset_east` — unreachable

*biomes: flower_forest*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| oricorio | fire/flying | common | 24.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| cutiefly | bug/fairy | common | 18.0 | 25-45 |  |
| fomantis | grass | common | 12.0 | 25-45 |  |
| petilil | grass | common | 12.0 | 25-45 |  |
| comfey | fairy | uncommon | 6.0 | 25-45 |  |
| ribombee | bug/fairy | uncommon | 6.0 | 25-45 |  |
| smoliv | grass/normal | uncommon | 6.0 | 25-45 | **BIOME** never spawns in flower_forest upstream; upstream biomes are savanna |
| arboliva | grass/normal | ultra-rare | — | 25-45 | **BIOME** never spawns in flower_forest upstream; upstream biomes are savanna |
| lilligant | grass | ultra-rare | — | 25-45 |  |
| lurantis | grass | ultra-rare | — | 25-45 |  |

### `sunset_west` — unreachable

*biomes: savanna*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| doduo | normal/flying | common | 24.0 | 25-45 |  |
| oricorio | fire/flying | common | 24.0 | 25-45 | **UNKNOWN** no stock spawn data for this species |
| girafarig | normal/psychic | common | 12.0 | 25-45 |  |
| litleo | fire/normal | common | 12.0 | 25-45 |  |
| blitzle | electric | uncommon | 6.0 | 25-45 |  |
| mudbray | ground | uncommon | 6.0 | 25-45 |  |
| dodrio | normal/flying | ultra-rare | — | 25-45 |  |
| farigiraf | normal/psychic | ultra-rare | — | 25-45 |  |
| pyroar | fire/normal | ultra-rare | — | 25-45 |  |
| zebstrika | electric | ultra-rare | — | 25-45 |  |

### `the_crags` — route

*biomes: grove, jagged_peaks; ground y103–114 (median 105); 0.0% water; 41,728 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| aron | steel/rock | common | 24.0 | 28-30 |  |
| bergmite | ice | common | 24.0 | 28-30 | **BIOME** never spawns in grove, jagged_peaks upstream; upstream biomes are #cobblemon:nether/is_frozen, frozen_ocean, glacial |
| nosepass | rock | common | 12.0 | 28-30 |  |
| bronzor | steel/psychic | uncommon | 6.0 | 28-30 | **YBAND** upstream maxY 10, this ground sits at y105 |
| skarmory | steel/flying | uncommon | 6.0 | 28-30 | **BIOME** never spawns in grove, jagged_peaks upstream; upstream biomes are badlands, desert, sky |
| aggron | steel/rock | ultra-rare | — | 28-30 |  |
| beldum | steel/psychic | ultra-rare | — | 28-30 |  |
| bronzong | steel/psychic | ultra-rare | — | 28-30 | **YBAND** upstream maxY 10, this ground sits at y105 |
| lairon | steel/rock | ultra-rare | — | 28-30 |  |
| metang | steel/psychic | ultra-rare | — | 28-30 |  |

### `the_tri_peaks` — route

*biomes: grove, jagged_peaks, snowy_slopes; ground y123–198 (median 156); 0.0% water; 125,824 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| swablu | normal/flying | common | 24.0 | 24-35 |  |
| skiddo | grass | common | 12.0 | 24-35 |  |
| rookidee | flying | common | 9.0 | 24-35 |  |
| absol | dark | uncommon | 6.0 | 24-35 |  |
| corvisquire | flying | uncommon | 3.0 | 24-35 |  |
| altaria | dragon/flying | ultra-rare | — | 24-35 |  |
| corviknight | flying/steel | ultra-rare | — | 24-35 |  |
| gogoat | grass | ultra-rare | — | 24-35 |  |
| lucario | fighting/steel | ultra-rare | — | 24-35 | **UNKNOWN** no stock spawn data for this species |
| riolu | fighting | ultra-rare | — | 24-35 | **UNKNOWN** no stock spawn data for this species |

### `tilpey_east_shore` — route

*biomes: forest; ground y81–112 (median 103); 0.0% water; 167,808 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| psyduck | water | common | 24.0 | 41-43 |  |
| seedot | grass | common | 18.0 | 41-43 |  |
| sewaddle | bug/grass | common | 9.0 | 41-43 |  |
| skwovet | normal | common | 9.0 | 41-43 |  |
| bidoof | normal | uncommon | 6.0 | 41-43 | **WATER** never spawns on dry land upstream (2/2 entries in water) |
| nuzleaf | grass/dark | uncommon | 6.0 | 41-43 |  |
| greedent | normal | uncommon | 3.0 | 41-43 |  |
| swadloon | bug/grass | uncommon | 3.0 | 41-43 |  |
| leavanny | bug/grass | ultra-rare | — | 41-43 |  |
| shiftry | grass/dark | ultra-rare | — | 41-43 |  |

### `tilpey_north_shore` — route

*biomes: birch_forest; ground y88–121 (median 94); 0.0% water; 133,760 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| ducklett | water/flying | common | 18.0 | 39-41 | **BIOME** never spawns in birch_forest upstream; upstream biomes are #aether:is_aether, freshwater, sky |
| psyduck | water | common | 18.0 | 39-41 |  |
| bibarel | normal/water | common | 12.0 | 39-41 | **WATER** never spawns on dry land upstream (2/2 entries in water) |
| yanma | bug/flying | common | 12.0 | 39-41 | **WATER** never spawns on dry land upstream (5/5 entries in water); **YBAND** upstream maxY 9, this ground sits at y94 |
| golduck | water | uncommon | 6.0 | 39-41 |  |
| swanna | water/flying | uncommon | 6.0 | 39-41 | **BIOME** never spawns in birch_forest upstream; upstream biomes are #aether:is_aether, freshwater, sky |
| lotad | water/grass | uncommon | 4.5 | 39-41 |  |
| lombre | water/grass | rare | 1.5 | 39-41 |  |
| ludicolo | water/grass | ultra-rare | — | 39-41 |  |
| yanmega | bug/flying | ultra-rare | — | 39-41 | **WATER** never spawns on dry land upstream (5/5 entries in water); **YBAND** upstream maxY 9, this ground sits at y94 |

### `tilpey_south_shore` — route

*biomes: forest; ground y102–148 (median 129); 0.0% water; 124,160 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| psyduck | water | common | 24.0 | 42-44 |  |
| caterpie | bug | common | 16.8 | 42-44 |  |
| hoothoot | normal/flying | common | 9.0 | 42-44 |  |
| weedle | bug/poison | common | 8.4 | 42-44 |  |
| metapod | bug | uncommon | 5.52 | 42-44 |  |
| noctowl | normal/flying | uncommon | 3.0 | 42-44 |  |
| kakuna | bug/poison | uncommon | 2.76 | 42-44 |  |
| butterfree | bug/flying | ultra-rare | 1.68 | 42-44 |  |
| beedrill | bug/poison | ultra-rare | 0.84 | 42-44 |  |
| snorlax | normal | ultra-rare | — | 42-44 |  |

### `tilpey_waters` — unreachable

*biomes: river*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| psyduck | water | common | 24.0 | 39-48 |  |
| goldeen | water | common | 18.0 | 39-48 | **WATER** never spawns on dry land upstream (4/4 entries in water) |
| basculin | water | common | 12.0 | 39-48 | **WATER** never spawns on dry land upstream (24/24 entries in water) |
| magikarp | water | common | 9.0 | 39-48 | **WATER** never spawns on dry land upstream (46/46 entries in water) |
| basculegion | water/ghost | uncommon | 6.0 | 39-48 | **WATER** never spawns on dry land upstream (8/8 entries in water) |
| seaking | water | uncommon | 6.0 | 39-48 | **WATER** never spawns on dry land upstream (4/4 entries in water) |
| arrokuda | water | uncommon | 4.5 | 39-48 | **WATER** never spawns on dry land upstream (4/4 entries in water) |
| gyarados | water/flying | uncommon | 3.0 | 39-48 | **WATER** never spawns on dry land upstream (5/5 entries in water) |
| tadbulb | electric | rare | 2.0 | 39-48 |  |
| barraskewda | water | rare | 1.5 | 39-48 | **WATER** never spawns on dry land upstream (4/4 entries in water) |

### `tilpey_west_meadows` — unreachable

*biomes: flower_forest*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| psyduck | water | common | 24.0 | 39-48 |  |
| oddish | grass/poison | common | 18.0 | 39-48 |  |
| petilil | grass | common | 12.0 | 39-48 |  |
| cherubi | grass | common | 9.0 | 39-48 |  |
| gloom | grass/poison | uncommon | 6.0 | 39-48 |  |
| cutiefly | bug/fairy | uncommon | 4.5 | 39-48 |  |
| cherrim | grass | uncommon | 3.0 | 39-48 |  |
| ribombee | bug/fairy | rare | 1.5 | 39-48 |  |
| bellossom | grass | ultra-rare | — | 39-48 |  |
| lilligant | grass | ultra-rare | — | 39-48 |  |

### `tree_town_canopy` — habitat

*biomes: *

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| aipom | normal | common | 24.0 | 25-40 |  |
| sewaddle | bug/grass | common | 18.0 | 25-40 |  |
| emolga | electric/flying | common | 12.0 | 25-40 |  |
| pikipek | normal/flying | common | 9.0 | 25-40 |  |
| applin | grass/dragon | uncommon | 6.0 | 25-40 |  |
| pachirisu | electric | uncommon | 6.0 | 25-40 |  |
| swadloon | bug/grass | uncommon | 6.0 | 25-40 |  |
| trumbeak | normal/flying | uncommon | 3.0 | 25-40 |  |
| combee | bug/flying | rare | 2.0 | 25-40 |  |
| cutiefly | bug/fairy | rare | 2.0 | 25-40 |  |
| ambipom | normal | ultra-rare | — | 25-40 |  |
| leavanny | bug/grass | ultra-rare | — | 25-40 |  |

### `upper_trough` — route

*biomes: snowy_plains, snowy_slopes; ground y95–104 (median 101); 3.7% water; 121,984 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| bergmite | ice | common | 24.0 | 29-31 | **BIOME** never spawns in snowy_plains, snowy_slopes upstream; upstream biomes are #cobblemon:nether/is_frozen, frozen_ocean, glacial |
| vanillite | ice | common | 24.0 | 29-31 |  |
| snom | ice/bug | common | 12.0 | 29-31 |  |
| snorunt | ice | common | 12.0 | 29-31 |  |
| cubchoo | ice | uncommon | 6.0 | 29-31 | **BIOME** never spawns in snowy_plains, snowy_slopes upstream; upstream biomes are frozen_ocean |
| froslass | ice/ghost | ultra-rare | — | 29-31 |  |
| frosmoth | ice/bug | ultra-rare | — | 29-31 |  |
| glalie | ice | ultra-rare | — | 29-31 |  |
| vanillish | ice | ultra-rare | — | 29-31 |  |
| vanilluxe | ice | ultra-rare | — | 29-31 |  |

### `viltri_plateau` — route

*biomes: old_growth_birch_forest; ground y121–140 (median 132); 0.0% water; 151,296 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| combee | bug/flying | common | 24.0 | 12-15 |  |
| hoothoot | normal/flying | common | 24.0 | 12-15 |  |
| fomantis | grass | common | 12.0 | 12-15 | **BIOME** never spawns in old_growth_birch_forest upstream; upstream biomes are floral, jungle, the_bumblezone:floral_meadow, tropical_island |
| gossifleur | grass | common | 12.0 | 12-15 | **BIOME** never spawns in old_growth_birch_forest upstream; upstream biomes are aether:skyroot_grove, aether:skyroot_meadow, floral, the_bumblezone:floral_meadow |
| applin | grass/dragon | uncommon | 6.0 | 12-15 |  |
| appletun | grass/dragon | ultra-rare | — | 12-15 |  |
| eldegoss | grass | ultra-rare | — | 12-15 | **BIOME** never spawns in old_growth_birch_forest upstream; upstream biomes are aether:skyroot_grove, aether:skyroot_meadow, floral, the_bumblezone:floral_meadow |
| flapple | grass/dragon | ultra-rare | — | 12-15 |  |
| lurantis | grass | ultra-rare | — | 12-15 | **BIOME** never spawns in old_growth_birch_forest upstream; upstream biomes are floral, jungle, the_bumblezone:floral_meadow, tropical_island |
| vespiquen | bug/flying | ultra-rare | — | 12-15 | **UNKNOWN** no stock spawn data for this species |

### `viltris_path_valley` — unreachable

*biomes: forest*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| hoothoot | normal/flying | common | 24.0 | 15-28 |  |
| poochyena | dark | common | 24.0 | 15-28 |  |
| patrat | normal | common | 12.0 | 15-28 | **BIOME** never spawns in forest upstream; upstream biomes are grassland |
| zigzagoon | normal | common | 12.0 | 15-28 |  |
| bunnelby | normal | uncommon | 6.0 | 15-28 |  |
| fletchling | normal/flying | uncommon | 6.0 | 15-28 |  |
| diggersby | normal/ground | ultra-rare | — | 15-28 |  |
| linoone | normal | ultra-rare | — | 15-28 |  |
| mightyena | dark | ultra-rare | — | 15-28 |  |
| watchog | normal | ultra-rare | — | 15-28 | **BIOME** never spawns in forest upstream; upstream biomes are grassland |

### `wedge_north` — unreachable

*biomes: dark_forest*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| phantump | ghost/grass | common | 24.0 | 25-45 |  |
| gastly | ghost/poison | common | 18.0 | 25-45 |  |
| misdreavus | ghost | common | 12.0 | 25-45 |  |
| murkrow | dark/flying | common | 12.0 | 25-45 |  |
| haunter | ghost/poison | uncommon | 6.0 | 25-45 |  |
| impidimp | dark/fairy | uncommon | 6.0 | 25-45 |  |
| gengar | ghost/poison | ultra-rare | — | 25-45 |  |
| honchkrow | dark/flying | ultra-rare | — | 25-45 |  |
| mismagius | ghost | ultra-rare | — | 25-45 |  |
| trevenant | ghost/grass | ultra-rare | — | 25-45 |  |

### `wedge_south` — unreachable

*biomes: forest*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| phantump | ghost/grass | common | 24.0 | 25-45 |  |
| zubat | poison/flying | common | 18.0 | 25-45 |  |
| shuppet | ghost | common | 12.0 | 25-45 |  |
| venonat | bug/poison | common | 12.0 | 25-45 |  |
| duskull | ghost | uncommon | 6.0 | 25-45 | **BIOME** never spawns in forest upstream; upstream biomes are #cobblemon:nether/is_soul_sand, spooky |
| golbat | poison/flying | uncommon | 6.0 | 25-45 |  |
| banette | ghost | ultra-rare | — | 25-45 |  |
| crobat | poison/flying | ultra-rare | — | 25-45 |  |
| dusclops | ghost | ultra-rare | — | 25-45 | **BIOME** never spawns in forest upstream; upstream biomes are #cobblemon:nether/is_soul_sand, spooky |
| venomoth | bug/poison | ultra-rare | — | 25-45 |  |

### `west_shore` — route

*biomes: plains; ground y120–127 (median 124); 0.0% water; 42,176 blocks*

| species | types | bucket | weight | level | flags |
|---|---|---|---|---|---|
| pidgey | normal/flying | common | 24.0 | 7-10 |  |
| wingull | water/flying | common | 24.0 | 7-10 | **BIOME** never spawns in plains upstream; upstream biomes are coast, ocean, sky, tropical_island |
| krabby | water | common | 12.0 | 7-10 | **YBAND** upstream maxY 13, this ground sits at y124 |
| staryu | water | common | 12.0 | 7-10 | **YBAND** upstream maxY 13, this ground sits at y124 |
| shellder | water | uncommon | 6.0 | 7-10 | **WATER** never spawns on dry land upstream (8/8 entries in water); **YBAND** upstream maxY 13, this ground sits at y124 |
| wattrel | electric/flying | uncommon | 6.0 | 7-10 | **BIOME** never spawns in plains upstream; upstream biomes are coast, island, ocean, sky |
| cloyster | water/ice | ultra-rare | — | 7-10 | **WATER** never spawns on dry land upstream (8/8 entries in water); **YBAND** upstream maxY 13, this ground sits at y124 |
| kingler | water | ultra-rare | — | 7-10 | **YBAND** upstream maxY 13, this ground sits at y124 |
| pelipper | water/flying | ultra-rare | — | 7-10 | **BIOME** never spawns in plains upstream; upstream biomes are coast, ocean, sky, tropical_island |
| starmie | water/psychic | ultra-rare | — | 7-10 | **YBAND** upstream maxY 13, this ground sits at y124 |
