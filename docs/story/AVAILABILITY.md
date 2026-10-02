# Critical-path Pokemon availability

**Generated** by `python tools/availability.py --write` from the compiled pools in
`build/datapacks/cobblers_spawns/`, with types read from the Cobblemon 1.8 jar. Do not hand-edit it.

This replaces the hand-written version, which covered the curated ROUTE compilation only. That omission
hid the waterway pool that crosses Route 3, and so produced the conclusion that Gym 3 had one Ground
answer and was structurally thin. It has three.

A species is listed under the first gym a player could have caught it before, and the level band shown is
the band where it first appears. A species available earlier stays catchable later.

Reachability rule: route N is walked to reach gym N. A sub-region or waterway is placed at the earliest
gym whose route its spawn boxes come within **128 blocks** of, which is Minecraft's own simulation
distance: inside it the Pokemon are loaded and ticking in front of a player who never leaves the route.
The `Off corridor` column gives each species' actual gap, so a stricter reading is available without
re-running anything. Pools further than that are listed under *Pools off the route corridor* with their
nearest route. Habitat pools are not placed by geography at all and are listed separately again.

## Gym 1: kanto_brock (Rock)

31 species catchable before this gym; 31 of them are new since the last.

Types available at the cap (L20), on the form a player would have evolved to: bug (3), dragon (1), electric (4), fairy (1), fighting (1), flying (5), grass (10), ground (1), normal (9), poison (3), water (10).
Reached only by evolving, invisible if you read the caught form: fighting, ground.
Absent: dark, fire, ghost, ice, psychic, rock, steel.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bulbasaur | grass/poison | 4-8 | uncommon | pallet_meadows | subregion | on it | yes |
| lechonk | normal | 4-8 | uncommon | pallet_meadows | subregion | on it | yes |
| mareep | electric | 4-8 | common | route_01_pallet_to_brock | route | on it | yes |
| pidgey | normal/flying | 4-8 | common | route_01_pallet_to_brock | route | on it | yes |
| wooloo | normal | 4-8 | common | route_01_pallet_to_brock | route | on it | yes |
| applin | grass/dragon | 6-11 | common | route_01_pallet_to_brock | route | on it | yes |
| combee | bug/flying | 6-11 | uncommon | route_01_pallet_to_brock | route | on it | yes |
| hoothoot | normal/flying | 6-11 | common | route_01_pallet_to_brock | route | on it | yes |
| krabby | water | 6-12 | common | west_shore | subregion | 33 blocks | yes |
| pawmi | electric | 6-11 | uncommon | route_01_pallet_to_brock | route | on it | yes |
| popplio | water | 6-12 | uncommon | west_shore | subregion | 33 blocks | yes |
| sewaddle | bug/grass | 6-11 | common | route_01_pallet_to_brock | route | on it | yes |
| shellder | water | 6-12 | common | west_shore | subregion | 33 blocks | yes |
| skwovet | normal | 6-11 | common | route_01_pallet_to_brock | route | on it | yes |
| staryu | water | 6-12 | common | west_shore | subregion | 33 blocks | yes |
| tentacool | water/poison | 6-12 | uncommon | west_shore | subregion | 33 blocks | yes |
| treecko | grass | 6-11 | uncommon | route_01_pallet_to_brock | route | on it | yes |
| wattrel | electric/flying | 6-12 | uncommon | west_shore | subregion | 33 blocks | yes |
| wingull | water/flying | 6-12 | common | west_shore | subregion | 33 blocks | yes |
| bidoof | normal | 8-13 | uncommon | route_01_pallet_to_brock | route | on it | yes |
| deerling | normal/grass | 8-13 | common | route_01_pallet_to_brock | route | on it | yes |
| goldeen | water | 8-13 | common | route_01_pallet_to_brock | route | on it | yes |
| marill | water/fairy | 8-13 | common | route_01_pallet_to_brock | route | on it | yes |
| shinx | electric | 8-13 | common | route_01_pallet_to_brock | route | on it | yes |
| surskit | bug/water | 8-13 | uncommon | route_01_pallet_to_brock | route | on it | yes |
| budew | grass/poison | 9-14 | uncommon | route_01_pallet_to_brock | route | on it | yes |
| bunnelby | normal | 9-14 | common | route_01_pallet_to_brock | route | on it | yes |
| fomantis | grass | 9-14 | uncommon | viltri_plateau | subregion | on it | yes |
| gossifleur | grass | 9-14 | common | route_01_pallet_to_brock | route | on it | yes |
| smoliv | grass/normal | 9-14 | common | route_01_pallet_to_brock | route | on it | yes |
| snivy | grass | 9-14 | uncommon | viltri_plateau | subregion | on it | yes |

## Gym 2: kanto_misty (Water)

46 species catchable before this gym; 15 of them are new since the last.

Types available at the cap (L25), on the form a player would have evolved to: bug (8), dragon (1), electric (5), fairy (1), fighting (1), flying (8), grass (12), ground (1), normal (9), poison (5), water (14).
Reached only by evolving, invisible if you read the caught form: fighting.
Absent: dark, fire, ghost, ice, psychic, rock, steel.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bulbasaur | grass/poison | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| lechonk | normal | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| mareep | electric | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| pawmi | electric | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| popplio | water | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| sewaddle | bug/grass | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| skwovet | normal | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| tentacool | water/poison | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| treecko | grass | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| wingull | water/flying | 6-12 | common | west_shore | subregion | 33 blocks |  |
| bidoof | normal | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| goldeen | water | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| marill | water/fairy | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| shinx | electric | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| budew | grass/poison | 9-14 | uncommon | route_01_pallet_to_brock | route | on it |  |
| bunnelby | normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| gossifleur | grass | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| smoliv | grass/normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| snivy | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| chikorita | grass | 13-19 | uncommon | route_02_brock_to_misty | route | on it | yes |
| chinchou | water/electric | 13-19 | rare | lake_viltri_hollow | subregion | on it | yes |
| corphish | water | 13-19 | common | route_02_brock_to_misty | route | on it | yes |
| illumise | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it | yes |
| lotad | water/grass | 13-18 | common | route_02_brock_to_misty | route | on it | yes |
| magikarp | water | 13-19 | common | route_02_brock_to_misty | route | on it | yes |
| nincada | bug/ground | 13-19 | common | route_02_brock_to_misty | route | on it | yes |
| squirtle | water | 13-19 | uncommon | route_02_brock_to_misty | route | on it | yes |
| venonat | bug/poison | 13-19 | common | route_02_brock_to_misty | route | on it | yes |
| volbeat | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it | yes |
| lombre | water/grass | 14-19 | common | route_02_brock_to_misty | route | on it | yes |
| bayleef | grass | 16-19 | uncommon | route_02_brock_to_misty | route | on it | yes |
| wartortle | water | 16-19 | uncommon | route_02_brock_to_misty | route | on it | yes |
| beedrill | bug/poison | 19-30 | uncommon | lake_viltri_hollow | subregion | on it | yes |
| ninjask | bug/flying | 20-30 | uncommon | lake_viltri_hollow | subregion | on it | yes |

## Gym 3: kanto_ltsurge (Electric)

87 species catchable before this gym; 41 of them are new since the last.

Types available at the cap (L30), on the form a player would have evolved to: bug (12), dark (2), dragon (3), electric (6), fairy (1), fighting (5), flying (17), grass (15), ground (5), normal (13), poison (7), psychic (6), rock (5), steel (1), water (17).
Absent: fire, ghost, ice.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bulbasaur | grass/poison | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| lechonk | normal | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| mareep | electric | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| pawmi | electric | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| popplio | water | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| sewaddle | bug/grass | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| skwovet | normal | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| tentacool | water/poison | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| treecko | grass | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| wingull | water/flying | 6-12 | common | west_shore | subregion | 33 blocks |  |
| bidoof | normal | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| goldeen | water | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| marill | water/fairy | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| shinx | electric | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| budew | grass/poison | 9-14 | uncommon | route_01_pallet_to_brock | route | on it |  |
| bunnelby | normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| gossifleur | grass | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| smoliv | grass/normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| snivy | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| chikorita | grass | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| chinchou | water/electric | 13-19 | rare | lake_viltri_hollow | subregion | on it |  |
| corphish | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 13-18 | common | route_02_brock_to_misty | route | on it |  |
| magikarp | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| nincada | bug/ground | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| squirtle | water | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| venonat | bug/poison | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 14-19 | common | route_02_brock_to_misty | route | on it |  |
| bayleef | grass | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| wartortle | water | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| beedrill | bug/poison | 19-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| ninjask | bug/flying | 20-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| beautifly | bug/flying | 19-26 | common | route_03_misty_to_surge | route | on it | yes |
| diglett | ground | 19-26 | common | route_03_misty_to_surge | route | on it | yes |
| dustox | bug/poison | 19-26 | common | route_03_misty_to_surge | route | on it | yes |
| feebas | water | 19-26 | rare | foothill_woods | subregion | on it | yes |
| grotle | grass | 19-26 | uncommon | foothill_woods | subregion | on it | yes |
| heracross | bug/fighting | 19-26 | uncommon | route_03_misty_to_surge | route | on it | yes |
| pachirisu | electric | 19-26 | common | route_03_misty_to_surge | route | on it | yes |
| poliwag | water | 19-26 | common | route_03_misty_to_surge | route | on it | yes |
| scyther | bug/flying | 19-26 | uncommon | foothill_woods | subregion | on it | yes |
| turtwig | grass | 19-22 | uncommon | foothill_woods | subregion | on it | yes |
| absol | dark | 20-28 | rare | the_tri_peaks | subregion | 9 blocks | yes |
| corvisquire | flying | 20-28 | common | the_tri_peaks | subregion | 9 blocks | yes |
| machop | fighting | 20-26 | common | route_03_misty_to_surge | route | on it | yes |
| makuhita | fighting | 20-26 | common | mt_clay | subregion | 9 blocks | yes |
| rockruff | rock | 20-26 | common | mt_clay | subregion | 9 blocks | yes |
| rookidee | flying | 20-22 | common | route_03_misty_to_surge | route | on it | yes |
| rufflet | normal/flying | 20-26 | uncommon | mt_clay | subregion | 9 blocks | yes |
| sandshrew | ground | 20-26 | uncommon | mt_clay | subregion | 9 blocks | yes |
| skiddo | grass | 20-28 | common | route_03_misty_to_surge | route | on it | yes |
| swablu | normal/flying | 20-28 | common | route_03_misty_to_surge | route | on it | yes |
| drampa | normal/dragon | 22-28 | rare | mt_vessu | subregion | 1 blocks | yes |
| meditite | fighting/psychic | 22-28 | common | mt_vessu | subregion | 1 blocks | yes |
| nosepass | rock | 22-28 | common | mt_vessu | subregion | 1 blocks | yes |
| sandslash | ground | 22-26 | uncommon | mt_clay | subregion | 9 blocks | yes |
| spoink | psychic | 22-28 | common | mt_vessu | subregion | 1 blocks | yes |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks | yes |
| hariyama | fighting | 24-26 | common | mt_clay | subregion | 9 blocks | yes |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks | yes |
| skarmory | steel/flying | 24-28 | common | the_tri_peaks | subregion | 9 blocks | yes |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks | yes |
| lunatone | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks | yes |
| lycanroc | rock | 25-26 | common | mt_clay | subregion | 9 blocks | yes |
| poliwhirl | water | 25-26 | common | route_03_misty_to_surge | route | on it | yes |
| solrock | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks | yes |
| dugtrio | ground | 26-26 | common | route_03_misty_to_surge | route | on it | yes |
| machoke | fighting | 28-35 | uncommon | mt_clay | subregion | 9 blocks | yes |
| xatu | psychic/flying | 28-35 | uncommon | mt_vessu | subregion | 1 blocks | yes |
| gogoat | grass | 32-35 | uncommon | the_tri_peaks | subregion | 9 blocks | yes |
| grumpig | psychic | 32-35 | uncommon | mt_vessu | subregion | 1 blocks | yes |
| staraptor | normal/flying | 34-35 | uncommon | the_tri_peaks | subregion | 9 blocks | yes |
| altaria | dragon/flying | 35-35 | uncommon | the_tri_peaks | subregion | 9 blocks | yes |

## Gym 4: kanto_erika (Grass)

133 species catchable before this gym; 46 of them are new since the last.

Types available at the cap (L35), on the form a player would have evolved to: bug (14), dark (6), dragon (3), electric (7), fairy (3), fighting (6), fire (6), flying (19), grass (15), ground (10), ice (10), normal (16), poison (8), psychic (6), rock (11), steel (2), water (23).
Absent: ghost.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bulbasaur | grass/poison | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| lechonk | normal | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| mareep | electric | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| pawmi | electric | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| popplio | water | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| sewaddle | bug/grass | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| skwovet | normal | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| tentacool | water/poison | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| treecko | grass | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| wingull | water/flying | 6-12 | common | west_shore | subregion | 33 blocks |  |
| bidoof | normal | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| goldeen | water | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| marill | water/fairy | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| shinx | electric | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| budew | grass/poison | 9-14 | uncommon | route_01_pallet_to_brock | route | on it |  |
| bunnelby | normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| gossifleur | grass | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| smoliv | grass/normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| snivy | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| chikorita | grass | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| chinchou | water/electric | 13-19 | rare | lake_viltri_hollow | subregion | on it |  |
| corphish | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 13-18 | common | route_02_brock_to_misty | route | on it |  |
| magikarp | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| nincada | bug/ground | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| squirtle | water | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| venonat | bug/poison | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 14-19 | common | route_02_brock_to_misty | route | on it |  |
| bayleef | grass | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| wartortle | water | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| beedrill | bug/poison | 19-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| ninjask | bug/flying | 20-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| beautifly | bug/flying | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| diglett | ground | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| dustox | bug/poison | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| feebas | water | 19-26 | rare | foothill_woods | subregion | on it |  |
| grotle | grass | 19-26 | uncommon | foothill_woods | subregion | on it |  |
| heracross | bug/fighting | 19-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| pachirisu | electric | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| poliwag | water | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| scyther | bug/flying | 19-26 | uncommon | foothill_woods | subregion | on it |  |
| turtwig | grass | 19-22 | uncommon | foothill_woods | subregion | on it |  |
| absol | dark | 20-28 | rare | the_tri_peaks | subregion | 9 blocks |  |
| corvisquire | flying | 20-28 | common | the_tri_peaks | subregion | 9 blocks |  |
| machop | fighting | 20-26 | common | route_03_misty_to_surge | route | on it |  |
| makuhita | fighting | 20-26 | common | mt_clay | subregion | 9 blocks |  |
| rockruff | rock | 20-26 | common | mt_clay | subregion | 9 blocks |  |
| rookidee | flying | 20-22 | common | route_03_misty_to_surge | route | on it |  |
| rufflet | normal/flying | 20-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| sandshrew | ground | 20-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| skiddo | grass | 20-28 | common | route_03_misty_to_surge | route | on it |  |
| swablu | normal/flying | 20-28 | common | route_03_misty_to_surge | route | on it |  |
| drampa | normal/dragon | 22-28 | rare | mt_vessu | subregion | 1 blocks |  |
| meditite | fighting/psychic | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| nosepass | rock | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| sandslash | ground | 22-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| spoink | psychic | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks |  |
| hariyama | fighting | 24-26 | common | mt_clay | subregion | 9 blocks |  |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks |  |
| skarmory | steel/flying | 24-28 | common | the_tri_peaks | subregion | 9 blocks |  |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks |  |
| lunatone | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks |  |
| lycanroc | rock | 25-26 | common | mt_clay | subregion | 9 blocks |  |
| poliwhirl | water | 25-26 | common | route_03_misty_to_surge | route | on it |  |
| solrock | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks |  |
| dugtrio | ground | 26-26 | common | route_03_misty_to_surge | route | on it |  |
| machoke | fighting | 28-35 | uncommon | mt_clay | subregion | 9 blocks |  |
| xatu | psychic/flying | 28-35 | uncommon | mt_vessu | subregion | 1 blocks |  |
| gogoat | grass | 32-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| grumpig | psychic | 32-35 | uncommon | mt_vessu | subregion | 1 blocks |  |
| staraptor | normal/flying | 34-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| altaria | dragon/flying | 35-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| fletchinder | fire/flying | 23-33 | common | north_shore_downs | subregion | 65 blocks | yes |
| litleo | fire/normal | 23-33 | uncommon | north_shore_downs | subregion | 65 blocks | yes |
| minccino | normal | 23-33 | common | north_shore_downs | subregion | 65 blocks | yes |
| pignite | fire/fighting | 23-33 | uncommon | north_shore_downs | subregion | 65 blocks | yes |
| skiploom | grass/flying | 23-31 | common | north_shore_downs | subregion | 65 blocks | yes |
| aron | steel/rock | 25-32 | common | route_04_surge_to_erika | route | on it | yes |
| barboach | water/ground | 25-32 | common | route_04_surge_to_erika | route | on it | yes |
| bergmite | ice | 25-31 | common | route_04_surge_to_erika | route | on it | yes |
| carbink | rock/fairy | 25-32 | rare | the_crags | subregion | on it | yes |
| carvanha | water/dark | 25-32 | common | route_04_surge_to_erika | route | on it | yes |
| cryogonal | ice | 25-31 | rare | merian_cirque | subregion | on it | yes |
| geodude | rock/ground | 25-29 | common | the_crags | subregion | on it | yes |
| graveler | rock/ground | 25-32 | common | the_crags | subregion | on it | yes |
| smoochum | ice/psychic | 25-31 | common | route_04_surge_to_erika | route | on it | yes |
| swinub | ice/ground | 25-31 | common | route_04_surge_to_erika | route | on it | yes |
| basculin | water | 26-33 | common | route_04_surge_to_erika | route | on it | yes |
| buizel | water | 26-30 | common | route_04_surge_to_erika | route | on it | yes |
| cubchoo | ice | 26-33 | common | route_04_surge_to_erika | route | on it | yes |
| dewott | water | 26-33 | uncommon | route_04_surge_to_erika | route | on it | yes |
| emolga | electric/flying | 26-33 | uncommon | peak_pond_hollow | subregion | on it | yes |
| floatzel | water | 26-33 | common | route_04_surge_to_erika | route | on it | yes |
| growlithe | fire | 26-33 | common | route_04_surge_to_erika | route | on it | yes |
| snom | ice/bug | 26-33 | uncommon | upper_trough | subregion | on it | yes |
| snorunt | ice | 26-33 | common | route_04_surge_to_erika | route | on it | yes |
| stantler | normal | 26-33 | common | route_04_surge_to_erika | route | on it | yes |
| teddiursa | normal | 26-33 | common | route_04_surge_to_erika | route | on it | yes |
| vanillite | ice | 26-33 | common | route_04_surge_to_erika | route | on it | yes |
| houndoom | dark/fire | 27-33 | uncommon | north_east_downs | subregion | 97 blocks | yes |
| houndour | dark/fire | 27-28 | uncommon | north_east_downs | subregion | 97 blocks | yes |
| jumpluff | grass/flying | 27-33 | common | north_shore_downs | subregion | 65 blocks | yes |
| quilava | fire | 27-33 | uncommon | north_east_downs | subregion | 97 blocks | yes |
| staravia | normal/flying | 27-33 | common | north_east_downs | subregion | 97 blocks | yes |
| stunky | poison/dark | 27-33 | common | north_east_downs | subregion | 97 blocks | yes |
| thievul | dark | 27-33 | common | north_east_downs | subregion | 97 blocks | yes |
| onix | rock/ground | 29-32 | uncommon | the_crags | subregion | on it | yes |
| jynx | ice/psychic | 30-31 | common | merian_cirque | subregion | on it | yes |
| sharpedo | water/dark | 30-32 | common | route_04_surge_to_erika | route | on it | yes |
| ursaring | normal | 30-33 | common | peak_pond_hollow | subregion | on it | yes |
| whiscash | water/ground | 30-32 | common | route_04_surge_to_erika | route | on it | yes |
| boldore | rock | 32-40 | uncommon | the_crags | subregion | on it | yes |
| lairon | steel/rock | 32-32 | common | the_crags | subregion | on it | yes |
| piloswine | ice/ground | 33-40 | uncommon | merian_cirque | subregion | on it | yes |
| crustle | bug/rock | 34-40 | uncommon | the_crags | subregion | on it | yes |
| samurott | water | 36-40 | uncommon | peak_pond_hollow | subregion | on it | yes |
| avalugg | ice | 37-40 | uncommon | merian_cirque | subregion | on it | yes |
| beartic | ice | 37-40 | uncommon | merian_cirque | subregion | on it | yes |

## Gym 5: kanto_koga (Poison)

164 species catchable before this gym; 31 of them are new since the last.

Types available at the cap (L40), on the form a player would have evolved to: bug (15), dark (6), dragon (4), electric (10), fairy (3), fighting (7), fire (7), flying (19), grass (17), ground (14), ice (13), normal (16), poison (11), psychic (8), rock (11), steel (5), water (28).
Absent: ghost.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bulbasaur | grass/poison | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| lechonk | normal | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| mareep | electric | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| pawmi | electric | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| popplio | water | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| sewaddle | bug/grass | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| skwovet | normal | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| tentacool | water/poison | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| treecko | grass | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| wingull | water/flying | 6-12 | common | west_shore | subregion | 33 blocks |  |
| bidoof | normal | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| goldeen | water | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| marill | water/fairy | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| shinx | electric | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| budew | grass/poison | 9-14 | uncommon | route_01_pallet_to_brock | route | on it |  |
| bunnelby | normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| gossifleur | grass | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| smoliv | grass/normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| snivy | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| chikorita | grass | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| chinchou | water/electric | 13-19 | rare | lake_viltri_hollow | subregion | on it |  |
| corphish | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 13-18 | common | route_02_brock_to_misty | route | on it |  |
| magikarp | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| nincada | bug/ground | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| squirtle | water | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| venonat | bug/poison | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 14-19 | common | route_02_brock_to_misty | route | on it |  |
| bayleef | grass | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| wartortle | water | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| beedrill | bug/poison | 19-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| ninjask | bug/flying | 20-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| beautifly | bug/flying | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| diglett | ground | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| dustox | bug/poison | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| feebas | water | 19-26 | rare | foothill_woods | subregion | on it |  |
| grotle | grass | 19-26 | uncommon | foothill_woods | subregion | on it |  |
| heracross | bug/fighting | 19-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| pachirisu | electric | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| poliwag | water | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| scyther | bug/flying | 19-26 | uncommon | foothill_woods | subregion | on it |  |
| turtwig | grass | 19-22 | uncommon | foothill_woods | subregion | on it |  |
| absol | dark | 20-28 | rare | the_tri_peaks | subregion | 9 blocks |  |
| corvisquire | flying | 20-28 | common | the_tri_peaks | subregion | 9 blocks |  |
| machop | fighting | 20-26 | common | route_03_misty_to_surge | route | on it |  |
| makuhita | fighting | 20-26 | common | mt_clay | subregion | 9 blocks |  |
| rockruff | rock | 20-26 | common | mt_clay | subregion | 9 blocks |  |
| rookidee | flying | 20-22 | common | route_03_misty_to_surge | route | on it |  |
| rufflet | normal/flying | 20-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| sandshrew | ground | 20-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| skiddo | grass | 20-28 | common | route_03_misty_to_surge | route | on it |  |
| swablu | normal/flying | 20-28 | common | route_03_misty_to_surge | route | on it |  |
| drampa | normal/dragon | 22-28 | rare | mt_vessu | subregion | 1 blocks |  |
| meditite | fighting/psychic | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| nosepass | rock | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| sandslash | ground | 22-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| spoink | psychic | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks |  |
| hariyama | fighting | 24-26 | common | mt_clay | subregion | 9 blocks |  |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks |  |
| skarmory | steel/flying | 24-28 | common | the_tri_peaks | subregion | 9 blocks |  |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks |  |
| lunatone | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks |  |
| lycanroc | rock | 25-26 | common | mt_clay | subregion | 9 blocks |  |
| poliwhirl | water | 25-26 | common | route_03_misty_to_surge | route | on it |  |
| solrock | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks |  |
| dugtrio | ground | 26-26 | common | route_03_misty_to_surge | route | on it |  |
| machoke | fighting | 28-35 | uncommon | mt_clay | subregion | 9 blocks |  |
| xatu | psychic/flying | 28-35 | uncommon | mt_vessu | subregion | 1 blocks |  |
| gogoat | grass | 32-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| grumpig | psychic | 32-35 | uncommon | mt_vessu | subregion | 1 blocks |  |
| staraptor | normal/flying | 34-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| altaria | dragon/flying | 35-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| fletchinder | fire/flying | 23-33 | common | north_shore_downs | subregion | 65 blocks |  |
| litleo | fire/normal | 23-33 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| minccino | normal | 23-33 | common | north_shore_downs | subregion | 65 blocks |  |
| pignite | fire/fighting | 23-33 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| skiploom | grass/flying | 23-31 | common | north_shore_downs | subregion | 65 blocks |  |
| aron | steel/rock | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| barboach | water/ground | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| bergmite | ice | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| carbink | rock/fairy | 25-32 | rare | the_crags | subregion | on it |  |
| carvanha | water/dark | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| cryogonal | ice | 25-31 | rare | merian_cirque | subregion | on it |  |
| geodude | rock/ground | 25-29 | common | the_crags | subregion | on it |  |
| graveler | rock/ground | 25-32 | common | the_crags | subregion | on it |  |
| smoochum | ice/psychic | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| swinub | ice/ground | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| basculin | water | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| buizel | water | 26-30 | common | route_04_surge_to_erika | route | on it |  |
| cubchoo | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| dewott | water | 26-33 | uncommon | route_04_surge_to_erika | route | on it |  |
| emolga | electric/flying | 26-33 | uncommon | peak_pond_hollow | subregion | on it |  |
| floatzel | water | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| growlithe | fire | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| snom | ice/bug | 26-33 | uncommon | upper_trough | subregion | on it |  |
| snorunt | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| stantler | normal | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| teddiursa | normal | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| vanillite | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| houndoom | dark/fire | 27-33 | uncommon | north_east_downs | subregion | 97 blocks |  |
| houndour | dark/fire | 27-28 | uncommon | north_east_downs | subregion | 97 blocks |  |
| jumpluff | grass/flying | 27-33 | common | north_shore_downs | subregion | 65 blocks |  |
| quilava | fire | 27-33 | uncommon | north_east_downs | subregion | 97 blocks |  |
| staravia | normal/flying | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| stunky | poison/dark | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| thievul | dark | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| onix | rock/ground | 29-32 | uncommon | the_crags | subregion | on it |  |
| jynx | ice/psychic | 30-31 | common | merian_cirque | subregion | on it |  |
| sharpedo | water/dark | 30-32 | common | route_04_surge_to_erika | route | on it |  |
| ursaring | normal | 30-33 | common | peak_pond_hollow | subregion | on it |  |
| whiscash | water/ground | 30-32 | common | route_04_surge_to_erika | route | on it |  |
| boldore | rock | 32-40 | uncommon | the_crags | subregion | on it |  |
| lairon | steel/rock | 32-32 | common | the_crags | subregion | on it |  |
| piloswine | ice/ground | 33-40 | uncommon | merian_cirque | subregion | on it |  |
| crustle | bug/rock | 34-40 | uncommon | the_crags | subregion | on it |  |
| samurott | water | 36-40 | uncommon | peak_pond_hollow | subregion | on it |  |
| avalugg | ice | 37-40 | uncommon | merian_cirque | subregion | on it |  |
| beartic | ice | 37-40 | uncommon | merian_cirque | subregion | on it |  |
| carnivine | grass | 28-38 | uncommon | marshy_marsh | subregion | 121 blocks | yes |
| cetoddle | ice | 28-38 | common | lower_trough | subregion | 81 blocks | yes |
| croagunk | poison/fighting | 28-38 | common | marshy_marsh | subregion | 121 blocks | yes |
| croconaw | water | 28-34 | common | marshy_marsh | subregion | 121 blocks | yes |
| goomy | dragon | 28-38 | rare | marshy_marsh | subregion | 121 blocks | yes |
| marshtomp | water/ground | 28-38 | uncommon | marshy_marsh | subregion | 121 blocks | yes |
| palpitoad | water/ground | 28-38 | common | marshy_marsh | subregion | 121 blocks | yes |
| prinplup | water | 28-38 | common | lower_trough | subregion | 81 blocks | yes |
| snover | grass/ice | 28-38 | uncommon | lower_trough | subregion | 81 blocks | yes |
| spheal | ice/water | 28-36 | common | lower_trough | subregion | 81 blocks | yes |
| stunfisk | ground/electric | 28-38 | common | marshy_marsh | subregion | 121 blocks | yes |
| tympole | water | 28-29 | common | marshy_marsh | subregion | 121 blocks | yes |
| braixen | fire | 30-38 | uncommon | route_05_erika_to_koga | route | on it | yes |
| drilbur | ground | 30-35 | common | route_05_erika_to_koga | route | on it | yes |
| feraligatr | water | 30-38 | common | marshy_marsh | subregion | 121 blocks | yes |
| hatenna | psychic | 30-36 | common | route_05_erika_to_koga | route | on it | yes |
| spidops | bug | 30-38 | common | route_05_erika_to_koga | route | on it | yes |
| toxel | electric/poison | 30-34 | uncommon | glacier_foot_fields | subregion | on it | yes |
| toxtricity | electric/poison | 30-38 | uncommon | glacier_foot_fields | subregion | on it | yes |
| excadrill | ground/steel | 31-38 | common | route_05_erika_to_koga | route | on it | yes |
| hattrem | psychic | 32-38 | common | route_05_erika_to_koga | route | on it | yes |
| sealeo | ice/water | 32-38 | common | lower_trough | subregion | 81 blocks | yes |
| delphox | fire/psychic | 36-38 | uncommon | glacier_foot_fields | subregion | on it | yes |
| empoleon | water/steel | 36-38 | common | lower_trough | subregion | 81 blocks | yes |
| seismitoad | water/ground | 36-38 | common | marshy_marsh | subregion | 121 blocks | yes |
| swampert | water/ground | 36-38 | uncommon | marshy_marsh | subregion | 121 blocks | yes |
| toxicroak | poison/fighting | 37-38 | common | marshy_marsh | subregion | 121 blocks | yes |
| cetitan | ice | 38-45 | uncommon | lower_trough | subregion | 81 blocks | yes |
| abomasnow | grass/ice | 40-45 | uncommon | lower_trough | subregion | 81 blocks | yes |
| sliggoo | dragon | 40-45 | uncommon | marshy_marsh | subregion | 121 blocks | yes |
| walrein | ice/water | 44-45 | uncommon | lower_trough | subregion | 81 blocks | yes |

## Gym 6: kanto_sabrina (Psychic)

190 species catchable before this gym; 26 of them are new since the last.

Types available at the cap (L45), on the form a player would have evolved to: bug (20), dark (10), dragon (4), electric (10), fairy (4), fighting (10), fire (8), flying (24), ghost (1), grass (22), ground (14), ice (12), normal (18), poison (14), psychic (8), rock (11), steel (5), water (30).
Absent: none.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bulbasaur | grass/poison | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| lechonk | normal | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| mareep | electric | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| pawmi | electric | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| popplio | water | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| sewaddle | bug/grass | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| skwovet | normal | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| tentacool | water/poison | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| treecko | grass | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| wingull | water/flying | 6-12 | common | west_shore | subregion | 33 blocks |  |
| bidoof | normal | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| goldeen | water | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| marill | water/fairy | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| shinx | electric | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| budew | grass/poison | 9-14 | uncommon | route_01_pallet_to_brock | route | on it |  |
| bunnelby | normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| gossifleur | grass | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| smoliv | grass/normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| snivy | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| chikorita | grass | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| chinchou | water/electric | 13-19 | rare | lake_viltri_hollow | subregion | on it |  |
| corphish | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 13-18 | common | route_02_brock_to_misty | route | on it |  |
| magikarp | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| nincada | bug/ground | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| squirtle | water | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| venonat | bug/poison | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 14-19 | common | route_02_brock_to_misty | route | on it |  |
| bayleef | grass | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| wartortle | water | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| beedrill | bug/poison | 19-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| ninjask | bug/flying | 20-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| beautifly | bug/flying | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| diglett | ground | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| dustox | bug/poison | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| feebas | water | 19-26 | rare | foothill_woods | subregion | on it |  |
| grotle | grass | 19-26 | uncommon | foothill_woods | subregion | on it |  |
| heracross | bug/fighting | 19-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| pachirisu | electric | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| poliwag | water | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| scyther | bug/flying | 19-26 | uncommon | foothill_woods | subregion | on it |  |
| turtwig | grass | 19-22 | uncommon | foothill_woods | subregion | on it |  |
| absol | dark | 20-28 | rare | the_tri_peaks | subregion | 9 blocks |  |
| corvisquire | flying | 20-28 | common | the_tri_peaks | subregion | 9 blocks |  |
| machop | fighting | 20-26 | common | route_03_misty_to_surge | route | on it |  |
| makuhita | fighting | 20-26 | common | mt_clay | subregion | 9 blocks |  |
| rockruff | rock | 20-26 | common | mt_clay | subregion | 9 blocks |  |
| rookidee | flying | 20-22 | common | route_03_misty_to_surge | route | on it |  |
| rufflet | normal/flying | 20-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| sandshrew | ground | 20-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| skiddo | grass | 20-28 | common | route_03_misty_to_surge | route | on it |  |
| swablu | normal/flying | 20-28 | common | route_03_misty_to_surge | route | on it |  |
| drampa | normal/dragon | 22-28 | rare | mt_vessu | subregion | 1 blocks |  |
| meditite | fighting/psychic | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| nosepass | rock | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| sandslash | ground | 22-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| spoink | psychic | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks |  |
| hariyama | fighting | 24-26 | common | mt_clay | subregion | 9 blocks |  |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks |  |
| skarmory | steel/flying | 24-28 | common | the_tri_peaks | subregion | 9 blocks |  |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks |  |
| lunatone | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks |  |
| lycanroc | rock | 25-26 | common | mt_clay | subregion | 9 blocks |  |
| poliwhirl | water | 25-26 | common | route_03_misty_to_surge | route | on it |  |
| solrock | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks |  |
| dugtrio | ground | 26-26 | common | route_03_misty_to_surge | route | on it |  |
| machoke | fighting | 28-35 | uncommon | mt_clay | subregion | 9 blocks |  |
| xatu | psychic/flying | 28-35 | uncommon | mt_vessu | subregion | 1 blocks |  |
| gogoat | grass | 32-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| grumpig | psychic | 32-35 | uncommon | mt_vessu | subregion | 1 blocks |  |
| staraptor | normal/flying | 34-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| altaria | dragon/flying | 35-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| fletchinder | fire/flying | 23-33 | common | north_shore_downs | subregion | 65 blocks |  |
| litleo | fire/normal | 23-33 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| minccino | normal | 23-33 | common | north_shore_downs | subregion | 65 blocks |  |
| pignite | fire/fighting | 23-33 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| skiploom | grass/flying | 23-31 | common | north_shore_downs | subregion | 65 blocks |  |
| aron | steel/rock | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| barboach | water/ground | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| bergmite | ice | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| carbink | rock/fairy | 25-32 | rare | the_crags | subregion | on it |  |
| carvanha | water/dark | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| cryogonal | ice | 25-31 | rare | merian_cirque | subregion | on it |  |
| geodude | rock/ground | 25-29 | common | the_crags | subregion | on it |  |
| graveler | rock/ground | 25-32 | common | the_crags | subregion | on it |  |
| smoochum | ice/psychic | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| swinub | ice/ground | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| basculin | water | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| buizel | water | 26-30 | common | route_04_surge_to_erika | route | on it |  |
| cubchoo | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| dewott | water | 26-33 | uncommon | route_04_surge_to_erika | route | on it |  |
| emolga | electric/flying | 26-33 | uncommon | peak_pond_hollow | subregion | on it |  |
| floatzel | water | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| growlithe | fire | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| snom | ice/bug | 26-33 | uncommon | upper_trough | subregion | on it |  |
| snorunt | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| stantler | normal | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| teddiursa | normal | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| vanillite | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| houndoom | dark/fire | 27-33 | uncommon | north_east_downs | subregion | 97 blocks |  |
| houndour | dark/fire | 27-28 | uncommon | north_east_downs | subregion | 97 blocks |  |
| jumpluff | grass/flying | 27-33 | common | north_shore_downs | subregion | 65 blocks |  |
| quilava | fire | 27-33 | uncommon | north_east_downs | subregion | 97 blocks |  |
| staravia | normal/flying | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| stunky | poison/dark | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| thievul | dark | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| onix | rock/ground | 29-32 | uncommon | the_crags | subregion | on it |  |
| jynx | ice/psychic | 30-31 | common | merian_cirque | subregion | on it |  |
| sharpedo | water/dark | 30-32 | common | route_04_surge_to_erika | route | on it |  |
| ursaring | normal | 30-33 | common | peak_pond_hollow | subregion | on it |  |
| whiscash | water/ground | 30-32 | common | route_04_surge_to_erika | route | on it |  |
| boldore | rock | 32-40 | uncommon | the_crags | subregion | on it |  |
| lairon | steel/rock | 32-32 | common | the_crags | subregion | on it |  |
| piloswine | ice/ground | 33-40 | uncommon | merian_cirque | subregion | on it |  |
| crustle | bug/rock | 34-40 | uncommon | the_crags | subregion | on it |  |
| samurott | water | 36-40 | uncommon | peak_pond_hollow | subregion | on it |  |
| avalugg | ice | 37-40 | uncommon | merian_cirque | subregion | on it |  |
| beartic | ice | 37-40 | uncommon | merian_cirque | subregion | on it |  |
| carnivine | grass | 28-38 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| cetoddle | ice | 28-38 | common | lower_trough | subregion | 81 blocks |  |
| croagunk | poison/fighting | 28-38 | common | marshy_marsh | subregion | 121 blocks |  |
| croconaw | water | 28-34 | common | marshy_marsh | subregion | 121 blocks |  |
| goomy | dragon | 28-38 | rare | marshy_marsh | subregion | 121 blocks |  |
| marshtomp | water/ground | 28-38 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| palpitoad | water/ground | 28-38 | common | marshy_marsh | subregion | 121 blocks |  |
| prinplup | water | 28-38 | common | lower_trough | subregion | 81 blocks |  |
| snover | grass/ice | 28-38 | uncommon | lower_trough | subregion | 81 blocks |  |
| spheal | ice/water | 28-36 | common | lower_trough | subregion | 81 blocks |  |
| stunfisk | ground/electric | 28-38 | common | marshy_marsh | subregion | 121 blocks |  |
| tympole | water | 28-29 | common | marshy_marsh | subregion | 121 blocks |  |
| braixen | fire | 30-38 | uncommon | route_05_erika_to_koga | route | on it |  |
| drilbur | ground | 30-35 | common | route_05_erika_to_koga | route | on it |  |
| feraligatr | water | 30-38 | common | marshy_marsh | subregion | 121 blocks |  |
| hatenna | psychic | 30-36 | common | route_05_erika_to_koga | route | on it |  |
| spidops | bug | 30-38 | common | route_05_erika_to_koga | route | on it |  |
| toxel | electric/poison | 30-34 | uncommon | glacier_foot_fields | subregion | on it |  |
| toxtricity | electric/poison | 30-38 | uncommon | glacier_foot_fields | subregion | on it |  |
| excadrill | ground/steel | 31-38 | common | route_05_erika_to_koga | route | on it |  |
| hattrem | psychic | 32-38 | common | route_05_erika_to_koga | route | on it |  |
| sealeo | ice/water | 32-38 | common | lower_trough | subregion | 81 blocks |  |
| delphox | fire/psychic | 36-38 | uncommon | glacier_foot_fields | subregion | on it |  |
| empoleon | water/steel | 36-38 | common | lower_trough | subregion | 81 blocks |  |
| seismitoad | water/ground | 36-38 | common | marshy_marsh | subregion | 121 blocks |  |
| swampert | water/ground | 36-38 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| toxicroak | poison/fighting | 37-38 | common | marshy_marsh | subregion | 121 blocks |  |
| cetitan | ice | 38-45 | uncommon | lower_trough | subregion | 81 blocks |  |
| abomasnow | grass/ice | 40-45 | uncommon | lower_trough | subregion | 81 blocks |  |
| sliggoo | dragon | 40-45 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| walrein | ice/water | 44-45 | uncommon | lower_trough | subregion | 81 blocks |  |
| arbok | poison | 33-43 | common | route_06_koga_to_sabrina | route | on it | yes |
| ducklett | water/flying | 33-39 | common | route_06_koga_to_sabrina | route | on it | yes |
| dunsparce | normal | 33-43 | common | route_06_koga_to_sabrina | route | on it | yes |
| koffing | poison | 33-39 | common | route_06_koga_to_sabrina | route | on it | yes |
| monferno | fire/fighting | 33-40 | uncommon | tilpey_north_shore | subregion | on it | yes |
| murkrow | dark/flying | 33-43 | uncommon | tilpey_north_shore | subregion | on it | yes |
| nuzleaf | grass/dark | 33-43 | common | tilpey_east_shore | subregion | 73 blocks | yes |
| pinsir | bug | 33-43 | uncommon | tilpey_east_shore | subregion | 73 blocks | yes |
| quilladin | grass | 33-40 | uncommon | tilpey_east_shore | subregion | 73 blocks | yes |
| scolipede | bug/poison | 33-43 | common | route_06_koga_to_sabrina | route | on it | yes |
| shuppet | ghost | 33-41 | uncommon | marsh_creek | subregion | on it | yes |
| swadloon | bug/grass | 33-43 | common | tilpey_east_shore | subregion | 73 blocks | yes |
| whirlipede | bug/poison | 33-34 | common | route_06_koga_to_sabrina | route | on it | yes |
| yanma | bug/flying | 33-43 | common | route_06_koga_to_sabrina | route | on it | yes |
| swanna | water/flying | 35-43 | common | route_06_koga_to_sabrina | route | on it | yes |
| weezing | poison | 35-43 | common | route_06_koga_to_sabrina | route | on it | yes |
| chesnaught | grass/fighting | 36-43 | uncommon | tilpey_east_shore | subregion | 73 blocks | yes |
| infernape | fire/fighting | 36-43 | uncommon | tilpey_north_shore | subregion | on it | yes |
| banette | ghost | 37-43 | uncommon | marsh_creek | subregion | on it | yes |
| dudunsparce | normal | 38-43 | common | route_06_koga_to_sabrina | route | on it | yes |
| honchkrow | dark/flying | 38-43 | uncommon | tilpey_north_shore | subregion | on it | yes |
| leavanny | bug/grass | 38-43 | common | tilpey_east_shore | subregion | 73 blocks | yes |
| ludicolo | water/grass | 38-43 | common | tilpey_east_shore | subregion | 73 blocks | yes |
| poliwrath | water/fighting | 38-43 | common | route_06_koga_to_sabrina | route | on it | yes |
| shiftry | grass/dark | 38-43 | common | tilpey_east_shore | subregion | 73 blocks | yes |
| yanmega | bug/flying | 38-43 | common | route_06_koga_to_sabrina | route | on it | yes |

## Gym 7: kanto_blaine (Fire)

233 species catchable before this gym; 43 of them are new since the last.

Types available at the cap (L50), on the form a player would have evolved to: bug (27), dark (11), dragon (6), electric (10), fairy (4), fighting (11), fire (16), flying (26), ghost (1), grass (23), ground (22), ice (12), normal (18), poison (17), psychic (9), rock (15), steel (6), water (35).
Absent: none.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bulbasaur | grass/poison | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| lechonk | normal | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| mareep | electric | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| pawmi | electric | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| popplio | water | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| sewaddle | bug/grass | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| skwovet | normal | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| tentacool | water/poison | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| treecko | grass | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| wingull | water/flying | 6-12 | common | west_shore | subregion | 33 blocks |  |
| bidoof | normal | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| goldeen | water | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| marill | water/fairy | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| shinx | electric | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| budew | grass/poison | 9-14 | uncommon | route_01_pallet_to_brock | route | on it |  |
| bunnelby | normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| gossifleur | grass | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| smoliv | grass/normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| snivy | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| chikorita | grass | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| chinchou | water/electric | 13-19 | rare | lake_viltri_hollow | subregion | on it |  |
| corphish | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 13-18 | common | route_02_brock_to_misty | route | on it |  |
| magikarp | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| nincada | bug/ground | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| squirtle | water | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| venonat | bug/poison | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 14-19 | common | route_02_brock_to_misty | route | on it |  |
| bayleef | grass | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| wartortle | water | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| beedrill | bug/poison | 19-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| ninjask | bug/flying | 20-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| beautifly | bug/flying | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| diglett | ground | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| dustox | bug/poison | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| feebas | water | 19-26 | rare | foothill_woods | subregion | on it |  |
| grotle | grass | 19-26 | uncommon | foothill_woods | subregion | on it |  |
| heracross | bug/fighting | 19-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| pachirisu | electric | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| poliwag | water | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| scyther | bug/flying | 19-26 | uncommon | foothill_woods | subregion | on it |  |
| turtwig | grass | 19-22 | uncommon | foothill_woods | subregion | on it |  |
| absol | dark | 20-28 | rare | the_tri_peaks | subregion | 9 blocks |  |
| corvisquire | flying | 20-28 | common | the_tri_peaks | subregion | 9 blocks |  |
| machop | fighting | 20-26 | common | route_03_misty_to_surge | route | on it |  |
| makuhita | fighting | 20-26 | common | mt_clay | subregion | 9 blocks |  |
| rockruff | rock | 20-26 | common | mt_clay | subregion | 9 blocks |  |
| rookidee | flying | 20-22 | common | route_03_misty_to_surge | route | on it |  |
| rufflet | normal/flying | 20-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| sandshrew | ground | 20-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| skiddo | grass | 20-28 | common | route_03_misty_to_surge | route | on it |  |
| swablu | normal/flying | 20-28 | common | route_03_misty_to_surge | route | on it |  |
| drampa | normal/dragon | 22-28 | rare | mt_vessu | subregion | 1 blocks |  |
| meditite | fighting/psychic | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| nosepass | rock | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| sandslash | ground | 22-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| spoink | psychic | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks |  |
| hariyama | fighting | 24-26 | common | mt_clay | subregion | 9 blocks |  |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks |  |
| skarmory | steel/flying | 24-28 | common | the_tri_peaks | subregion | 9 blocks |  |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks |  |
| lunatone | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks |  |
| lycanroc | rock | 25-26 | common | mt_clay | subregion | 9 blocks |  |
| poliwhirl | water | 25-26 | common | route_03_misty_to_surge | route | on it |  |
| solrock | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks |  |
| dugtrio | ground | 26-26 | common | route_03_misty_to_surge | route | on it |  |
| machoke | fighting | 28-35 | uncommon | mt_clay | subregion | 9 blocks |  |
| xatu | psychic/flying | 28-35 | uncommon | mt_vessu | subregion | 1 blocks |  |
| gogoat | grass | 32-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| grumpig | psychic | 32-35 | uncommon | mt_vessu | subregion | 1 blocks |  |
| staraptor | normal/flying | 34-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| altaria | dragon/flying | 35-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| fletchinder | fire/flying | 23-33 | common | north_shore_downs | subregion | 65 blocks |  |
| litleo | fire/normal | 23-33 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| minccino | normal | 23-33 | common | north_shore_downs | subregion | 65 blocks |  |
| pignite | fire/fighting | 23-33 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| skiploom | grass/flying | 23-31 | common | north_shore_downs | subregion | 65 blocks |  |
| aron | steel/rock | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| barboach | water/ground | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| bergmite | ice | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| carbink | rock/fairy | 25-32 | rare | the_crags | subregion | on it |  |
| carvanha | water/dark | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| cryogonal | ice | 25-31 | rare | merian_cirque | subregion | on it |  |
| geodude | rock/ground | 25-29 | common | the_crags | subregion | on it |  |
| graveler | rock/ground | 25-32 | common | the_crags | subregion | on it |  |
| smoochum | ice/psychic | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| swinub | ice/ground | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| basculin | water | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| buizel | water | 26-30 | common | route_04_surge_to_erika | route | on it |  |
| cubchoo | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| dewott | water | 26-33 | uncommon | route_04_surge_to_erika | route | on it |  |
| emolga | electric/flying | 26-33 | uncommon | peak_pond_hollow | subregion | on it |  |
| floatzel | water | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| growlithe | fire | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| snom | ice/bug | 26-33 | uncommon | upper_trough | subregion | on it |  |
| snorunt | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| stantler | normal | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| teddiursa | normal | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| vanillite | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| houndoom | dark/fire | 27-33 | uncommon | north_east_downs | subregion | 97 blocks |  |
| houndour | dark/fire | 27-28 | uncommon | north_east_downs | subregion | 97 blocks |  |
| jumpluff | grass/flying | 27-33 | common | north_shore_downs | subregion | 65 blocks |  |
| quilava | fire | 27-33 | uncommon | north_east_downs | subregion | 97 blocks |  |
| staravia | normal/flying | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| stunky | poison/dark | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| thievul | dark | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| onix | rock/ground | 29-32 | uncommon | the_crags | subregion | on it |  |
| jynx | ice/psychic | 30-31 | common | merian_cirque | subregion | on it |  |
| sharpedo | water/dark | 30-32 | common | route_04_surge_to_erika | route | on it |  |
| ursaring | normal | 30-33 | common | peak_pond_hollow | subregion | on it |  |
| whiscash | water/ground | 30-32 | common | route_04_surge_to_erika | route | on it |  |
| boldore | rock | 32-40 | uncommon | the_crags | subregion | on it |  |
| lairon | steel/rock | 32-32 | common | the_crags | subregion | on it |  |
| piloswine | ice/ground | 33-40 | uncommon | merian_cirque | subregion | on it |  |
| crustle | bug/rock | 34-40 | uncommon | the_crags | subregion | on it |  |
| samurott | water | 36-40 | uncommon | peak_pond_hollow | subregion | on it |  |
| avalugg | ice | 37-40 | uncommon | merian_cirque | subregion | on it |  |
| beartic | ice | 37-40 | uncommon | merian_cirque | subregion | on it |  |
| carnivine | grass | 28-38 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| cetoddle | ice | 28-38 | common | lower_trough | subregion | 81 blocks |  |
| croagunk | poison/fighting | 28-38 | common | marshy_marsh | subregion | 121 blocks |  |
| croconaw | water | 28-34 | common | marshy_marsh | subregion | 121 blocks |  |
| goomy | dragon | 28-38 | rare | marshy_marsh | subregion | 121 blocks |  |
| marshtomp | water/ground | 28-38 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| palpitoad | water/ground | 28-38 | common | marshy_marsh | subregion | 121 blocks |  |
| prinplup | water | 28-38 | common | lower_trough | subregion | 81 blocks |  |
| snover | grass/ice | 28-38 | uncommon | lower_trough | subregion | 81 blocks |  |
| spheal | ice/water | 28-36 | common | lower_trough | subregion | 81 blocks |  |
| stunfisk | ground/electric | 28-38 | common | marshy_marsh | subregion | 121 blocks |  |
| tympole | water | 28-29 | common | marshy_marsh | subregion | 121 blocks |  |
| braixen | fire | 30-38 | uncommon | route_05_erika_to_koga | route | on it |  |
| drilbur | ground | 30-35 | common | route_05_erika_to_koga | route | on it |  |
| feraligatr | water | 30-38 | common | marshy_marsh | subregion | 121 blocks |  |
| hatenna | psychic | 30-36 | common | route_05_erika_to_koga | route | on it |  |
| spidops | bug | 30-38 | common | route_05_erika_to_koga | route | on it |  |
| toxel | electric/poison | 30-34 | uncommon | glacier_foot_fields | subregion | on it |  |
| toxtricity | electric/poison | 30-38 | uncommon | glacier_foot_fields | subregion | on it |  |
| excadrill | ground/steel | 31-38 | common | route_05_erika_to_koga | route | on it |  |
| hattrem | psychic | 32-38 | common | route_05_erika_to_koga | route | on it |  |
| sealeo | ice/water | 32-38 | common | lower_trough | subregion | 81 blocks |  |
| delphox | fire/psychic | 36-38 | uncommon | glacier_foot_fields | subregion | on it |  |
| empoleon | water/steel | 36-38 | common | lower_trough | subregion | 81 blocks |  |
| seismitoad | water/ground | 36-38 | common | marshy_marsh | subregion | 121 blocks |  |
| swampert | water/ground | 36-38 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| toxicroak | poison/fighting | 37-38 | common | marshy_marsh | subregion | 121 blocks |  |
| cetitan | ice | 38-45 | uncommon | lower_trough | subregion | 81 blocks |  |
| abomasnow | grass/ice | 40-45 | uncommon | lower_trough | subregion | 81 blocks |  |
| sliggoo | dragon | 40-45 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| walrein | ice/water | 44-45 | uncommon | lower_trough | subregion | 81 blocks |  |
| arbok | poison | 33-43 | common | route_06_koga_to_sabrina | route | on it |  |
| ducklett | water/flying | 33-39 | common | route_06_koga_to_sabrina | route | on it |  |
| dunsparce | normal | 33-43 | common | route_06_koga_to_sabrina | route | on it |  |
| koffing | poison | 33-39 | common | route_06_koga_to_sabrina | route | on it |  |
| monferno | fire/fighting | 33-40 | uncommon | tilpey_north_shore | subregion | on it |  |
| murkrow | dark/flying | 33-43 | uncommon | tilpey_north_shore | subregion | on it |  |
| nuzleaf | grass/dark | 33-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| pinsir | bug | 33-43 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| quilladin | grass | 33-40 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| scolipede | bug/poison | 33-43 | common | route_06_koga_to_sabrina | route | on it |  |
| shuppet | ghost | 33-41 | uncommon | marsh_creek | subregion | on it |  |
| swadloon | bug/grass | 33-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| whirlipede | bug/poison | 33-34 | common | route_06_koga_to_sabrina | route | on it |  |
| yanma | bug/flying | 33-43 | common | route_06_koga_to_sabrina | route | on it |  |
| swanna | water/flying | 35-43 | common | route_06_koga_to_sabrina | route | on it |  |
| weezing | poison | 35-43 | common | route_06_koga_to_sabrina | route | on it |  |
| chesnaught | grass/fighting | 36-43 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| infernape | fire/fighting | 36-43 | uncommon | tilpey_north_shore | subregion | on it |  |
| banette | ghost | 37-43 | uncommon | marsh_creek | subregion | on it |  |
| dudunsparce | normal | 38-43 | common | route_06_koga_to_sabrina | route | on it |  |
| honchkrow | dark/flying | 38-43 | uncommon | tilpey_north_shore | subregion | on it |  |
| leavanny | bug/grass | 38-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| ludicolo | water/grass | 38-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| poliwrath | water/fighting | 38-43 | common | route_06_koga_to_sabrina | route | on it |  |
| shiftry | grass/dark | 38-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| yanmega | bug/flying | 38-43 | common | route_06_koga_to_sabrina | route | on it |  |
| blaziken | fire/fighting | 38-48 | uncommon | crater_rim_north_west | subregion | 9 blocks | yes |
| butterfree | bug/flying | 38-48 | common | route_07_sabrina_to_blaine | route | on it | yes |
| camerupt | fire/ground | 38-48 | common | east_cones | subregion | 97 blocks | yes |
| carkol | rock/fire | 38-38 | common | east_cones | subregion | 97 blocks | yes |
| centiskorch | fire/bug | 38-48 | common | crater_rim_north_west | subregion | 9 blocks | yes |
| coalossal | rock/fire | 38-48 | common | east_cones | subregion | 97 blocks | yes |
| combusken | fire/fighting | 38-40 | uncommon | crater_rim_north_west | subregion | 9 blocks | yes |
| drizzile | water | 38-39 | uncommon | route_07_sabrina_to_blaine | route | on it | yes |
| foongus | grass/poison | 38-43 | common | eastern_moor | subregion | 105 blocks | yes |
| gastrodon | water/ground | 38-48 | common | route_07_sabrina_to_blaine | route | on it | yes |
| golduck | water | 38-48 | uncommon | tilpey_waters | subregion | 1 blocks | yes |
| grimer | poison | 38-42 | common | eastern_moor | subregion | 105 blocks | yes |
| gyarados | water/flying | 38-48 | common | tilpey_waters | subregion | 1 blocks | yes |
| hippopotas | ground | 38-38 | uncommon | east_coast_dunes | subregion | 33 blocks | yes |
| hippowdon | ground | 38-48 | uncommon | east_coast_dunes | subregion | 33 blocks | yes |
| inteleon | water | 38-48 | uncommon | route_07_sabrina_to_blaine | route | on it | yes |
| karrablast | bug | 38-48 | common | eastern_moor | subregion | 105 blocks | yes |
| krokorok | ground/dark | 38-44 | common | east_coast_dunes | subregion | 33 blocks | yes |
| magcargo | fire/rock | 38-48 | common | east_cones | subregion | 97 blocks | yes |
| muk | poison | 38-48 | common | eastern_moor | subregion | 105 blocks | yes |
| pelipper | water/flying | 38-48 | common | tilpey_waters | subregion | 1 blocks | yes |
| pidgeot | normal/flying | 38-48 | common | tilpey_south_shore | subregion | on it | yes |
| pidgeotto | normal/flying | 38-40 | common | tilpey_south_shore | subregion | on it | yes |
| rhyhorn | ground/rock | 38-46 | common | crater_rim_north_west | subregion | 9 blocks | yes |
| salazzle | poison/fire | 38-48 | common | crater_rim_north_west | subregion | 9 blocks | yes |
| sandaconda | ground | 38-48 | common | east_coast_dunes | subregion | 33 blocks | yes |
| shelmet | bug | 38-48 | common | eastern_moor | subregion | 105 blocks | yes |
| silicobra | ground | 38-40 | common | east_coast_dunes | subregion | 33 blocks | yes |
| slugma | fire | 38-42 | common | east_cones | subregion | 97 blocks | yes |
| torkoal | fire | 38-48 | uncommon | crater_rim_north_west | subregion | 9 blocks | yes |
| trapinch | ground | 38-39 | common | east_coast_dunes | subregion | 33 blocks | yes |
| turtonator | fire/dragon | 38-48 | rare | crater_rim_north_west | subregion | 9 blocks | yes |
| veluza | water/psychic | 38-48 | common | tilpey_waters | subregion | 1 blocks | yes |
| vespiquen | bug/flying | 38-48 | uncommon | tilpey_south_shore | subregion | on it | yes |
| vibrava | ground/dragon | 38-48 | common | east_coast_dunes | subregion | 33 blocks | yes |
| amoonguss | grass/poison | 39-48 | common | eastern_moor | subregion | 105 blocks | yes |
| krookodile | ground/dark | 40-48 | common | east_coast_dunes | subregion | 33 blocks | yes |
| rhydon | ground/rock | 42-48 | common | crater_rim_north_west | subregion | 9 blocks | yes |
| accelgor | bug | 43-48 | common | eastern_moor | subregion | 105 blocks | yes |
| escavalier | bug/steel | 43-48 | common | eastern_moor | subregion | 105 blocks | yes |
| rhyperior | ground/rock | 43-48 | common | crater_rim_north_west | subregion | 9 blocks | yes |
| flygon | ground/dragon | 45-48 | common | east_coast_dunes | subregion | 33 blocks | yes |
| wailord | water | 48-55 | uncommon | tilpey_waters | subregion | 1 blocks | yes |

## Gym 8: kanto_giovanni (Ground)

267 species catchable before this gym; 34 of them are new since the last.

Types available at the cap (L55), on the form a player would have evolved to: bug (29), dark (16), dragon (6), electric (12), fairy (4), fighting (14), fire (24), flying (27), ghost (5), grass (27), ground (26), ice (13), normal (18), poison (23), psychic (9), rock (16), steel (8), water (37).
Absent: none.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bulbasaur | grass/poison | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| lechonk | normal | 4-8 | uncommon | pallet_meadows | subregion | on it |  |
| mareep | electric | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 4-8 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| pawmi | electric | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| popplio | water | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| sewaddle | bug/grass | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| skwovet | normal | 6-11 | common | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 6-12 | common | west_shore | subregion | 33 blocks |  |
| tentacool | water/poison | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| treecko | grass | 6-11 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 6-12 | uncommon | west_shore | subregion | 33 blocks |  |
| wingull | water/flying | 6-12 | common | west_shore | subregion | 33 blocks |  |
| bidoof | normal | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| goldeen | water | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| marill | water/fairy | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| shinx | electric | 8-13 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 8-13 | uncommon | route_01_pallet_to_brock | route | on it |  |
| budew | grass/poison | 9-14 | uncommon | route_01_pallet_to_brock | route | on it |  |
| bunnelby | normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| gossifleur | grass | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| smoliv | grass/normal | 9-14 | common | route_01_pallet_to_brock | route | on it |  |
| snivy | grass | 9-14 | uncommon | viltri_plateau | subregion | on it |  |
| chikorita | grass | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| chinchou | water/electric | 13-19 | rare | lake_viltri_hollow | subregion | on it |  |
| corphish | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 13-18 | common | route_02_brock_to_misty | route | on it |  |
| magikarp | water | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| nincada | bug/ground | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| squirtle | water | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| venonat | bug/poison | 13-19 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 13-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 14-19 | common | route_02_brock_to_misty | route | on it |  |
| bayleef | grass | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| wartortle | water | 16-19 | uncommon | route_02_brock_to_misty | route | on it |  |
| beedrill | bug/poison | 19-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| ninjask | bug/flying | 20-30 | uncommon | lake_viltri_hollow | subregion | on it |  |
| beautifly | bug/flying | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| diglett | ground | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| dustox | bug/poison | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| feebas | water | 19-26 | rare | foothill_woods | subregion | on it |  |
| grotle | grass | 19-26 | uncommon | foothill_woods | subregion | on it |  |
| heracross | bug/fighting | 19-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| pachirisu | electric | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| poliwag | water | 19-26 | common | route_03_misty_to_surge | route | on it |  |
| scyther | bug/flying | 19-26 | uncommon | foothill_woods | subregion | on it |  |
| turtwig | grass | 19-22 | uncommon | foothill_woods | subregion | on it |  |
| absol | dark | 20-28 | rare | the_tri_peaks | subregion | 9 blocks |  |
| corvisquire | flying | 20-28 | common | the_tri_peaks | subregion | 9 blocks |  |
| machop | fighting | 20-26 | common | route_03_misty_to_surge | route | on it |  |
| makuhita | fighting | 20-26 | common | mt_clay | subregion | 9 blocks |  |
| rockruff | rock | 20-26 | common | mt_clay | subregion | 9 blocks |  |
| rookidee | flying | 20-22 | common | route_03_misty_to_surge | route | on it |  |
| rufflet | normal/flying | 20-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| sandshrew | ground | 20-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| skiddo | grass | 20-28 | common | route_03_misty_to_surge | route | on it |  |
| swablu | normal/flying | 20-28 | common | route_03_misty_to_surge | route | on it |  |
| drampa | normal/dragon | 22-28 | rare | mt_vessu | subregion | 1 blocks |  |
| meditite | fighting/psychic | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| nosepass | rock | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| sandslash | ground | 22-26 | uncommon | mt_clay | subregion | 9 blocks |  |
| spoink | psychic | 22-28 | common | mt_vessu | subregion | 1 blocks |  |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks |  |
| hariyama | fighting | 24-26 | common | mt_clay | subregion | 9 blocks |  |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks |  |
| skarmory | steel/flying | 24-28 | common | the_tri_peaks | subregion | 9 blocks |  |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks |  |
| lunatone | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks |  |
| lycanroc | rock | 25-26 | common | mt_clay | subregion | 9 blocks |  |
| poliwhirl | water | 25-26 | common | route_03_misty_to_surge | route | on it |  |
| solrock | rock/psychic | 25-28 | common | mt_vessu | subregion | 1 blocks |  |
| dugtrio | ground | 26-26 | common | route_03_misty_to_surge | route | on it |  |
| machoke | fighting | 28-35 | uncommon | mt_clay | subregion | 9 blocks |  |
| xatu | psychic/flying | 28-35 | uncommon | mt_vessu | subregion | 1 blocks |  |
| gogoat | grass | 32-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| grumpig | psychic | 32-35 | uncommon | mt_vessu | subregion | 1 blocks |  |
| staraptor | normal/flying | 34-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| altaria | dragon/flying | 35-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| fletchinder | fire/flying | 23-33 | common | north_shore_downs | subregion | 65 blocks |  |
| litleo | fire/normal | 23-33 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| minccino | normal | 23-33 | common | north_shore_downs | subregion | 65 blocks |  |
| pignite | fire/fighting | 23-33 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| skiploom | grass/flying | 23-31 | common | north_shore_downs | subregion | 65 blocks |  |
| aron | steel/rock | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| barboach | water/ground | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| bergmite | ice | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| carbink | rock/fairy | 25-32 | rare | the_crags | subregion | on it |  |
| carvanha | water/dark | 25-32 | common | route_04_surge_to_erika | route | on it |  |
| cryogonal | ice | 25-31 | rare | merian_cirque | subregion | on it |  |
| geodude | rock/ground | 25-29 | common | the_crags | subregion | on it |  |
| graveler | rock/ground | 25-32 | common | the_crags | subregion | on it |  |
| smoochum | ice/psychic | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| swinub | ice/ground | 25-31 | common | route_04_surge_to_erika | route | on it |  |
| basculin | water | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| buizel | water | 26-30 | common | route_04_surge_to_erika | route | on it |  |
| cubchoo | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| dewott | water | 26-33 | uncommon | route_04_surge_to_erika | route | on it |  |
| emolga | electric/flying | 26-33 | uncommon | peak_pond_hollow | subregion | on it |  |
| floatzel | water | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| growlithe | fire | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| snom | ice/bug | 26-33 | uncommon | upper_trough | subregion | on it |  |
| snorunt | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| stantler | normal | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| teddiursa | normal | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| vanillite | ice | 26-33 | common | route_04_surge_to_erika | route | on it |  |
| houndoom | dark/fire | 27-33 | uncommon | north_east_downs | subregion | 97 blocks |  |
| houndour | dark/fire | 27-28 | uncommon | north_east_downs | subregion | 97 blocks |  |
| jumpluff | grass/flying | 27-33 | common | north_shore_downs | subregion | 65 blocks |  |
| quilava | fire | 27-33 | uncommon | north_east_downs | subregion | 97 blocks |  |
| staravia | normal/flying | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| stunky | poison/dark | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| thievul | dark | 27-33 | common | north_east_downs | subregion | 97 blocks |  |
| onix | rock/ground | 29-32 | uncommon | the_crags | subregion | on it |  |
| jynx | ice/psychic | 30-31 | common | merian_cirque | subregion | on it |  |
| sharpedo | water/dark | 30-32 | common | route_04_surge_to_erika | route | on it |  |
| ursaring | normal | 30-33 | common | peak_pond_hollow | subregion | on it |  |
| whiscash | water/ground | 30-32 | common | route_04_surge_to_erika | route | on it |  |
| boldore | rock | 32-40 | uncommon | the_crags | subregion | on it |  |
| lairon | steel/rock | 32-32 | common | the_crags | subregion | on it |  |
| piloswine | ice/ground | 33-40 | uncommon | merian_cirque | subregion | on it |  |
| crustle | bug/rock | 34-40 | uncommon | the_crags | subregion | on it |  |
| samurott | water | 36-40 | uncommon | peak_pond_hollow | subregion | on it |  |
| avalugg | ice | 37-40 | uncommon | merian_cirque | subregion | on it |  |
| beartic | ice | 37-40 | uncommon | merian_cirque | subregion | on it |  |
| carnivine | grass | 28-38 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| cetoddle | ice | 28-38 | common | lower_trough | subregion | 81 blocks |  |
| croagunk | poison/fighting | 28-38 | common | marshy_marsh | subregion | 121 blocks |  |
| croconaw | water | 28-34 | common | marshy_marsh | subregion | 121 blocks |  |
| goomy | dragon | 28-38 | rare | marshy_marsh | subregion | 121 blocks |  |
| marshtomp | water/ground | 28-38 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| palpitoad | water/ground | 28-38 | common | marshy_marsh | subregion | 121 blocks |  |
| prinplup | water | 28-38 | common | lower_trough | subregion | 81 blocks |  |
| snover | grass/ice | 28-38 | uncommon | lower_trough | subregion | 81 blocks |  |
| spheal | ice/water | 28-36 | common | lower_trough | subregion | 81 blocks |  |
| stunfisk | ground/electric | 28-38 | common | marshy_marsh | subregion | 121 blocks |  |
| tympole | water | 28-29 | common | marshy_marsh | subregion | 121 blocks |  |
| braixen | fire | 30-38 | uncommon | route_05_erika_to_koga | route | on it |  |
| drilbur | ground | 30-35 | common | route_05_erika_to_koga | route | on it |  |
| feraligatr | water | 30-38 | common | marshy_marsh | subregion | 121 blocks |  |
| hatenna | psychic | 30-36 | common | route_05_erika_to_koga | route | on it |  |
| spidops | bug | 30-38 | common | route_05_erika_to_koga | route | on it |  |
| toxel | electric/poison | 30-34 | uncommon | glacier_foot_fields | subregion | on it |  |
| toxtricity | electric/poison | 30-38 | uncommon | glacier_foot_fields | subregion | on it |  |
| excadrill | ground/steel | 31-38 | common | route_05_erika_to_koga | route | on it |  |
| hattrem | psychic | 32-38 | common | route_05_erika_to_koga | route | on it |  |
| sealeo | ice/water | 32-38 | common | lower_trough | subregion | 81 blocks |  |
| delphox | fire/psychic | 36-38 | uncommon | glacier_foot_fields | subregion | on it |  |
| empoleon | water/steel | 36-38 | common | lower_trough | subregion | 81 blocks |  |
| seismitoad | water/ground | 36-38 | common | marshy_marsh | subregion | 121 blocks |  |
| swampert | water/ground | 36-38 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| toxicroak | poison/fighting | 37-38 | common | marshy_marsh | subregion | 121 blocks |  |
| cetitan | ice | 38-45 | uncommon | lower_trough | subregion | 81 blocks |  |
| abomasnow | grass/ice | 40-45 | uncommon | lower_trough | subregion | 81 blocks |  |
| sliggoo | dragon | 40-45 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| walrein | ice/water | 44-45 | uncommon | lower_trough | subregion | 81 blocks |  |
| arbok | poison | 33-43 | common | route_06_koga_to_sabrina | route | on it |  |
| ducklett | water/flying | 33-39 | common | route_06_koga_to_sabrina | route | on it |  |
| dunsparce | normal | 33-43 | common | route_06_koga_to_sabrina | route | on it |  |
| koffing | poison | 33-39 | common | route_06_koga_to_sabrina | route | on it |  |
| monferno | fire/fighting | 33-40 | uncommon | tilpey_north_shore | subregion | on it |  |
| murkrow | dark/flying | 33-43 | uncommon | tilpey_north_shore | subregion | on it |  |
| nuzleaf | grass/dark | 33-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| pinsir | bug | 33-43 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| quilladin | grass | 33-40 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| scolipede | bug/poison | 33-43 | common | route_06_koga_to_sabrina | route | on it |  |
| shuppet | ghost | 33-41 | uncommon | marsh_creek | subregion | on it |  |
| swadloon | bug/grass | 33-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| whirlipede | bug/poison | 33-34 | common | route_06_koga_to_sabrina | route | on it |  |
| yanma | bug/flying | 33-43 | common | route_06_koga_to_sabrina | route | on it |  |
| swanna | water/flying | 35-43 | common | route_06_koga_to_sabrina | route | on it |  |
| weezing | poison | 35-43 | common | route_06_koga_to_sabrina | route | on it |  |
| chesnaught | grass/fighting | 36-43 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| infernape | fire/fighting | 36-43 | uncommon | tilpey_north_shore | subregion | on it |  |
| banette | ghost | 37-43 | uncommon | marsh_creek | subregion | on it |  |
| dudunsparce | normal | 38-43 | common | route_06_koga_to_sabrina | route | on it |  |
| honchkrow | dark/flying | 38-43 | uncommon | tilpey_north_shore | subregion | on it |  |
| leavanny | bug/grass | 38-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| ludicolo | water/grass | 38-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| poliwrath | water/fighting | 38-43 | common | route_06_koga_to_sabrina | route | on it |  |
| shiftry | grass/dark | 38-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| yanmega | bug/flying | 38-43 | common | route_06_koga_to_sabrina | route | on it |  |
| blaziken | fire/fighting | 38-48 | uncommon | crater_rim_north_west | subregion | 9 blocks |  |
| butterfree | bug/flying | 38-48 | common | route_07_sabrina_to_blaine | route | on it |  |
| camerupt | fire/ground | 38-48 | common | east_cones | subregion | 97 blocks |  |
| carkol | rock/fire | 38-38 | common | east_cones | subregion | 97 blocks |  |
| centiskorch | fire/bug | 38-48 | common | crater_rim_north_west | subregion | 9 blocks |  |
| coalossal | rock/fire | 38-48 | common | east_cones | subregion | 97 blocks |  |
| combusken | fire/fighting | 38-40 | uncommon | crater_rim_north_west | subregion | 9 blocks |  |
| drizzile | water | 38-39 | uncommon | route_07_sabrina_to_blaine | route | on it |  |
| foongus | grass/poison | 38-43 | common | eastern_moor | subregion | 105 blocks |  |
| gastrodon | water/ground | 38-48 | common | route_07_sabrina_to_blaine | route | on it |  |
| golduck | water | 38-48 | uncommon | tilpey_waters | subregion | 1 blocks |  |
| grimer | poison | 38-42 | common | eastern_moor | subregion | 105 blocks |  |
| gyarados | water/flying | 38-48 | common | tilpey_waters | subregion | 1 blocks |  |
| hippopotas | ground | 38-38 | uncommon | east_coast_dunes | subregion | 33 blocks |  |
| hippowdon | ground | 38-48 | uncommon | east_coast_dunes | subregion | 33 blocks |  |
| inteleon | water | 38-48 | uncommon | route_07_sabrina_to_blaine | route | on it |  |
| karrablast | bug | 38-48 | common | eastern_moor | subregion | 105 blocks |  |
| krokorok | ground/dark | 38-44 | common | east_coast_dunes | subregion | 33 blocks |  |
| magcargo | fire/rock | 38-48 | common | east_cones | subregion | 97 blocks |  |
| muk | poison | 38-48 | common | eastern_moor | subregion | 105 blocks |  |
| pelipper | water/flying | 38-48 | common | tilpey_waters | subregion | 1 blocks |  |
| pidgeot | normal/flying | 38-48 | common | tilpey_south_shore | subregion | on it |  |
| pidgeotto | normal/flying | 38-40 | common | tilpey_south_shore | subregion | on it |  |
| rhyhorn | ground/rock | 38-46 | common | crater_rim_north_west | subregion | 9 blocks |  |
| salazzle | poison/fire | 38-48 | common | crater_rim_north_west | subregion | 9 blocks |  |
| sandaconda | ground | 38-48 | common | east_coast_dunes | subregion | 33 blocks |  |
| shelmet | bug | 38-48 | common | eastern_moor | subregion | 105 blocks |  |
| silicobra | ground | 38-40 | common | east_coast_dunes | subregion | 33 blocks |  |
| slugma | fire | 38-42 | common | east_cones | subregion | 97 blocks |  |
| torkoal | fire | 38-48 | uncommon | crater_rim_north_west | subregion | 9 blocks |  |
| trapinch | ground | 38-39 | common | east_coast_dunes | subregion | 33 blocks |  |
| turtonator | fire/dragon | 38-48 | rare | crater_rim_north_west | subregion | 9 blocks |  |
| veluza | water/psychic | 38-48 | common | tilpey_waters | subregion | 1 blocks |  |
| vespiquen | bug/flying | 38-48 | uncommon | tilpey_south_shore | subregion | on it |  |
| vibrava | ground/dragon | 38-48 | common | east_coast_dunes | subregion | 33 blocks |  |
| amoonguss | grass/poison | 39-48 | common | eastern_moor | subregion | 105 blocks |  |
| krookodile | ground/dark | 40-48 | common | east_coast_dunes | subregion | 33 blocks |  |
| rhydon | ground/rock | 42-48 | common | crater_rim_north_west | subregion | 9 blocks |  |
| accelgor | bug | 43-48 | common | eastern_moor | subregion | 105 blocks |  |
| escavalier | bug/steel | 43-48 | common | eastern_moor | subregion | 105 blocks |  |
| rhyperior | ground/rock | 43-48 | common | crater_rim_north_west | subregion | 9 blocks |  |
| flygon | ground/dragon | 45-48 | common | east_coast_dunes | subregion | 33 blocks |  |
| wailord | water | 48-55 | uncommon | tilpey_waters | subregion | 1 blocks |  |
| bramblin | grass/ghost | 43-53 | uncommon | plateau_south | subregion | on it | yes |
| cacturne | grass/dark | 43-53 | common | route_08_blaine_to_giovanni | route | on it | yes |
| charizard | fire/flying | 43-53 | uncommon | great_crater | subregion | 65 blocks | yes |
| cinderace | fire | 43-53 | uncommon | rift_foot | subregion | on it | yes |
| clawitzer | water | 43-53 | common | route_08_blaine_to_giovanni | route | on it | yes |
| crabrawler | fighting | 43-53 | common | south_strand | subregion | on it | yes |
| donphan | ground | 43-53 | common | plateau_south | subregion | on it | yes |
| drapion | poison/dark | 43-53 | common | route_08_blaine_to_giovanni | route | on it | yes |
| kilowattrel | electric/flying | 43-53 | common | route_08_blaine_to_giovanni | route | on it | yes |
| klawf | rock | 43-53 | common | plateau_south | subregion | on it | yes |
| lampent | ghost/fire | 43-53 | common | great_crater | subregion | 65 blocks | yes |
| larvesta | bug/fire | 43-53 | rare | great_crater | subregion | 65 blocks | yes |
| litwick | ghost/fire | 43-45 | common | great_crater | subregion | 65 blocks | yes |
| magmar | fire | 43-53 | common | great_crater | subregion | 65 blocks | yes |
| maractus | grass | 43-53 | common | route_08_blaine_to_giovanni | route | on it | yes |
| mudsdale | ground | 43-53 | common | plateau_south | subregion | on it | yes |
| nidorina | poison | 43-53 | common | rift_foot | subregion | on it | yes |
| nidorino | poison | 43-53 | common | rift_foot | subregion | on it | yes |
| pawniard | dark/steel | 43-53 | uncommon | plateau_west | subregion | on it | yes |
| pincurchin | electric | 43-53 | uncommon | south_strand | subregion | on it | yes |
| scrafty | dark/fighting | 43-53 | common | route_08_blaine_to_giovanni | route | on it | yes |
| scraggy | dark/fighting | 43-43 | common | rift_foot | subregion | on it | yes |
| skorupi | poison/bug | 43-44 | common | route_08_blaine_to_giovanni | route | on it | yes |
| toxapex | poison/water | 43-53 | common | route_08_blaine_to_giovanni | route | on it | yes |
| zebstrika | electric | 43-53 | uncommon | rift_foot | subregion | on it | yes |
| brambleghast | grass/ghost | 48-53 | uncommon | plateau_south | subregion | on it | yes |
| chandelure | ghost/fire | 48-53 | common | great_crater | subregion | 65 blocks | yes |
| crabominable | fighting/ice | 48-53 | common | route_08_blaine_to_giovanni | route | on it | yes |
| kingambit | dark/steel | 48-53 | uncommon | plateau_west | subregion | on it | yes |
| magmortar | fire | 48-53 | common | great_crater | subregion | 65 blocks | yes |
| nidoking | poison/ground | 48-53 | common | route_08_blaine_to_giovanni | route | on it | yes |
| nidoqueen | poison/ground | 48-53 | common | route_08_blaine_to_giovanni | route | on it | yes |
| bisharp | dark/steel | 52-53 | uncommon | plateau_west | subregion | on it | yes |
| volcarona | bug/fire | 59-60 | uncommon | great_crater | subregion | 65 blocks | yes |

## Pools off the route corridor

Reachable by walking, but nothing gates when, so they are not assigned to a gym.

| Pool | Kind | Nearest route | Gap (blocks) | Species |
| --- | --- | --- | --- | --- |
| viltris_path_valley | subregion | route_01_pallet_to_brock | 153 | exeggcute, fearow, fletchinder, fletchling, floragato, patrat, riolu, spearow, sprigatito, watchog |
| rift_south_east_arm | subregion | route_08_blaine_to_giovanni | 209 | claydol, druddigon, flygon, gligar, gliscor, golurk, haxorus, salamence |
| rift_south_west_arm | subregion | route_08_blaine_to_giovanni | 225 | cubone, glimmora, hippowdon, marowak, pupitar, sableye, tyranitar |
| north_west_coast | subregion | route_03_misty_to_surge | 281 | corsola, finneon, frogadier, horsea, inkay, skrelp, slowpoke |
| rift_trunk | subregion | route_04_surge_to_erika | 313 | aggron, boldore, garganacl, gigalith, orthworm, probopass, rhyperior, tinkaton |
| south_west_fields | subregion | route_01_pallet_to_brock | 337 | cottonee, eevee, growlithe, nidoranf, nidoranm, nidorina, nidorino, pikachu |
| arrow_creeks | subregion | route_08_blaine_to_giovanni | 377 | dodrio, dondozo, farigiraf, flamigo, girafarig, tatsugiri |
| shrew_lake_shores | subregion | route_02_brock_to_misty | 385 | azumarill, cherrim, cherubi, dragonair, dratini, granbull, poltchageist, psyduck, snubbull, togepi |
| plateau_east | subregion | route_08_blaine_to_giovanni | 401 | armarouge, ceruledge, charcadet, durant, heatmor, orthworm, pyroar |
| fungal_north | subregion | route_01_pallet_to_brock | 425 | breloom, foongus, morelull, paras, parasect, shiinotic, shroomish, toedscool |
| frostpeak_strand | subregion | route_04_surge_to_erika | 433 | dewgong, lapras, sandshrew, seel, vulpix |
| fungal_south | subregion | route_01_pallet_to_brock | 433 | deino, pumpkaboo, tadbulb, tangela, venonat |
| south_east_dunes | subregion | route_08_blaine_to_giovanni | 441 | cyclizar, espathra, rabsca, rellor, sigilyph |
| wedge_south | subregion | route_08_blaine_to_giovanni | 449 | aegislash, banette, crobat, doublade, drifblim, dusclops, dusknoir, golbat, trevenant |
| wedge_north | subregion | route_06_koga_to_sabrina | 457 | crocalor, drifblim, dusknoir, gengar, haunter, misdreavus, mismagius, polteageist, sinistea, skeledirge, spiritomb |
| tilpey_west_meadows | subregion | route_06_koga_to_sabrina | 561 | bellossom, blissey, chansey, gloom, lilligant, masquerain, petilil, ribombee, vileplume |
| rift_west_spur | subregion | route_04_surge_to_erika | 569 | bastiodon, bisharp, bronzong, kingambit, klang, klinklang, pawniard, revavroom |
| sunset_east | subregion | route_08_blaine_to_giovanni | 601 | arboliva, comfey, lurantis, miltank |
| frostpeak | subregion | route_04_surge_to_erika | 665 | abomasnow, absol, avalugg, beartic, delibird, eiscue, glalie, larvitar, mamoswine, piloswine, pupitar, sneasel, snorunt |
| jungle_west | subregion | route_08_blaine_to_giovanni | 689 | aipom, ambipom, slaking, toucannon, tropius |
| arrow_lake_shores | subregion | route_02_brock_to_misty | 721 | ampharos, arrokuda, audino, barraskewda, chewtle, drednaw, flabebe, floette, quaxwell, relicanth, togedemaru |
| northgate_west | subregion | route_05_erika_to_koga | 753 | annihilape, forretress, heracross, noctowl, pineco, primeape, rillaboom, thwackey, ursaluna |
| northgate_east | subregion | route_05_erika_to_koga | 793 | axew, deerling, fraxure, furret, herdier, sawsbuck, stoutland |
| jungle_east | subregion | route_08_blaine_to_giovanni | 857 | chatot, grafaiai, hawlucha, komala |
| long_isle_north | subregion | route_07_sabrina_to_blaine | 913 | cofagrigus, gholdengo, gimmighoul, palossand, sandygast, seviper, yamask, zangoose |
| long_isle_middle | subregion | route_07_sabrina_to_blaine | 1049 | aerodactyl, heliolisk, helioptile, krookodile, sandaconda, sigilyph, silicobra |
| south_pine_isle | subregion | route_06_koga_to_sabrina | 1057 | buneary, dartrix, decidueye, lopunny, vanillish, vanillite, vanilluxe, zoroark, zorua |
| sunset_west | subregion | route_01_pallet_to_brock | 1361 | farigiraf, girafarig, incineroar, oricorio, ponyta, rapidash, tauros, torracat |
| long_isle_south | subregion | route_08_blaine_to_giovanni | 1465 | araquanid, golisopod, hakamoo, kommoo, lurantis, squawkabilly, steenee, tsareena |
| north_pine_isle | subregion | route_06_koga_to_sabrina | 1929 | abomasnow, sneasel, snorlax, snover, stantler, weavile, wyrdeer |

## Habitat pools: none of them reach a player

A habitat pool only spawns where a Cobblemon Habitat Block stands. `data/habitat_blocks.json` places
**no blocks anywhere**, so every pool below is authored and inert.

| Pool | Blocks placed | Species |
| --- | --- | --- |
| displaced_city_cavern | 0 |  |
| driftmouth_isle_waters | 10 |  |
| elder_foothill_grove_1 | 4 |  |
| elder_foothill_grove_2 | 4 |  |
| elder_foothill_grove_3 | 4 |  |
| elder_foothill_grove_4 | 4 |  |
| elder_foothill_woods_1 | 4 |  |
| elder_foothill_woods_2 | 4 |  |
| elder_foothill_woods_3 | 4 |  |
| elder_foothill_woods_4 | 4 |  |
| elder_jungle_east_1 | 4 |  |
| elder_jungle_east_2 | 4 |  |
| elder_jungle_west_1 | 4 |  |
| elder_jungle_west_2 | 4 |  |
| elder_lake_viltri_hollow_1 | 4 |  |
| elder_lake_viltri_hollow_2 | 4 |  |
| elder_long_isle_middle_1 | 4 |  |
| elder_long_isle_middle_2 | 4 |  |
| elder_long_isle_north_1 | 4 |  |
| elder_long_isle_north_2 | 4 |  |
| elder_long_isle_south_1 | 4 |  |
| elder_long_isle_south_2 | 4 |  |
| elder_long_isle_south_3 | 4 |  |
| elder_marshy_marsh_1 | 4 |  |
| elder_marshy_marsh_2 | 4 |  |
| elder_marshy_marsh_3 | 4 |  |
| elder_north_pine_isle_1 | 4 |  |
| elder_north_pine_isle_2 | 4 |  |
| elder_northgate_east_1 | 4 |  |
| elder_northgate_east_2 | 4 |  |
| elder_northgate_west_1 | 4 |  |
| elder_northgate_west_2 | 4 |  |
| elder_peak_pond_hollow_1 | 4 |  |
| elder_peak_pond_hollow_2 | 4 |  |
| elder_peak_pond_hollow_3 | 4 |  |
| elder_shrew_lake_shores_1 | 4 |  |
| elder_shrew_lake_shores_2 | 4 |  |
| elder_shrew_lake_shores_3 | 4 |  |
| elder_south_pine_isle_1 | 4 |  |
| elder_south_pine_isle_2 | 4 |  |
| elder_south_pine_isle_3 | 4 |  |
| elder_tilpey_east_shore_1 | 4 |  |
| elder_tilpey_east_shore_2 | 4 |  |
| elder_tilpey_north_shore_1 | 4 |  |
| elder_tilpey_north_shore_2 | 4 |  |
| elder_viltri_plateau_1 | 4 |  |
| elder_viltri_plateau_2 | 4 |  |
| elder_viltri_plateau_3 | 4 |  |
| elder_viltris_path_valley_1 | 4 |  |
| elder_viltris_path_valley_2 | 4 |  |
| elder_wedge_north_1 | 4 |  |
| elder_wedge_north_2 | 4 |  |
| elder_wedge_south_1 | 4 |  |
| elder_wedge_south_2 | 4 |  |
| glacial_tear_deep_valley | 0 |  |
| great_crater_bowls | 0 |  |
| marshy_marsh_basin | 0 |  |
| mining_town_fossil_levels | 0 |  |
| northgate_old_growth_grove | 0 |  |
| rift_depths | 0 |  |
| route_1_ghost_mansion | 1 |  |
| route_1_sapling_crown | 2 |  |
| sapling_crag_mt_vessu | 3 |  |
| sapling_crag_the_crags | 3 |  |
| sapling_desert_long_isle_north | 3 |  |
| sapling_desert_south_east_dunes | 3 |  |
| sapling_frost_frostpeak | 3 |  |
| sapling_frost_glacier_foot_fields | 3 |  |
| sapling_lakeshore_arrow_lake_shores | 3 |  |
| sapling_lakeshore_tilpey_south_shore | 3 |  |
| sapling_palm_east_coast_dunes | 3 |  |
| sapling_palm_sunset_east | 3 |  |
| sapling_palm_sunset_west | 3 |  |
| sapling_scorched_great_crater | 3 |  |
| sapling_storm_rift_foot | 3 |  |
| sapling_storm_rift_trunk | 3 |  |
| tree_town_canopy | 0 |  |
| ursaluna_den_outskirts | 1 |  |
| vrc_abandoned_cut | 2 |  |
| vrc_abandoned_cut_core | 4 |  |
| vrc_bloom | 5 |  |
| vrc_bloom_core | 7 |  |
| vrc_cave | 31 |  |
| vrc_drowned | 4 |  |
| vrc_drowned_core | 3 |  |
| vrc_raw_tear | 6 |  |
| vrc_raw_tear_core | 4 |  |
| vrc_slagworks | 6 |  |
| vrc_slagworks_core | 8 |  |

## What this document still does not cover

The pack's own inherited pools. `data/spawn_suppression.json` retains upstream defaults in "unauthored
caves", off-route wilderness, open ocean and the Nether and End, and the bounded-suppression override
pack is not installed on the staging server. Measured 2026-09-23 over the server's mods and datapacks:
**2,662 readable spawn pool files carrying 5,850 underground-only spawn details** (Cobblemon 3,657,
COBBLEVERSE-DP-v31 2,037, three addons the rest), naming 855 distinct species.

Those are not ordered by route and cannot be placed on this progression, but they are live. Any
conclusion of the form "a player cannot get an X before gym N" is unsafe until they are accounted for.

