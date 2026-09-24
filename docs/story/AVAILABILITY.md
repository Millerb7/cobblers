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

19 species catchable before this gym; 19 of them are new since the last.

Types available at the cap (L20), on the form a player would have evolved to: bug (2), dragon (1), electric (3), fighting (1), flying (5), grass (4), normal (6), water (7).
Reached only by evolving, invisible if you read the caught form: fighting.
Absent: dark, fairy, fire, ghost, ground, ice, poison, psychic, rock, steel.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mareep | electric | 5-8 | common | route_01_pallet_to_brock | route | on it | yes |
| pidgey | normal/flying | 5-8 | common | route_01_pallet_to_brock | route | on it | yes |
| rattata | normal | 5-8 | common | route_01_pallet_to_brock | route | on it | yes |
| wooloo | normal | 5-8 | common | route_01_pallet_to_brock | route | on it | yes |
| krabby | water | 7-10 | common | route_01_pallet_to_brock | route | on it | yes |
| shellder | water | 7-10 | uncommon | route_01_pallet_to_brock | route | on it | yes |
| staryu | water | 7-10 | common | route_01_pallet_to_brock | route | on it | yes |
| wattrel | electric/flying | 7-10 | uncommon | route_01_pallet_to_brock | route | on it | yes |
| wingull | water/flying | 7-10 | common | route_01_pallet_to_brock | route | on it | yes |
| bidoof | normal | 9-12 | common | route_01_pallet_to_brock | route | on it | yes |
| buizel | water | 9-12 | common | route_01_pallet_to_brock | route | on it | yes |
| deerling | normal/grass | 9-12 | uncommon | route_01_pallet_to_brock | route | on it | yes |
| pawmi | electric | 9-12 | common | route_01_pallet_to_brock | route | on it | yes |
| surskit | bug/water | 9-12 | common | route_01_pallet_to_brock | route | on it | yes |
| applin | grass/dragon | 12-15 | uncommon | route_01_pallet_to_brock | route | on it | yes |
| combee | bug/flying | 12-15 | common | route_01_pallet_to_brock | route | on it | yes |
| fomantis | grass | 12-15 | common | route_01_pallet_to_brock | route | on it | yes |
| gossifleur | grass | 12-15 | common | route_01_pallet_to_brock | route | on it | yes |
| hoothoot | normal/flying | 12-15 | common | route_01_pallet_to_brock | route | on it | yes |

## Gym 2: kanto_misty (Water)

24 species catchable before this gym; 5 of them are new since the last.

Types available at the cap (L25), on the form a player would have evolved to: bug (4), dragon (1), electric (3), fighting (1), flying (6), grass (5), normal (6), water (8).
Reached only by evolving, invisible if you read the caught form: fighting.
Absent: dark, fairy, fire, ghost, ground, ice, poison, psychic, rock, steel.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mareep | electric | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| rattata | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wingull | water/flying | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| bidoof | normal | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| buizel | water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 9-12 | uncommon | route_01_pallet_to_brock | route | on it |  |
| pawmi | electric | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 12-15 | uncommon | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| gossifleur | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| corphish | water | 18-21 | common | route_02_brock_to_misty | route | on it | yes |
| illumise | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it | yes |
| lombre | water/grass | 18-21 | uncommon | route_02_brock_to_misty | route | on it | yes |
| lotad | water/grass | 18-21 | common | route_02_brock_to_misty | route | on it | yes |
| volbeat | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it | yes |

## Gym 3: kanto_ltsurge (Electric)

44 species catchable before this gym; 20 of them are new since the last.

Types available at the cap (L30), on the form a player would have evolved to: bug (6), dark (2), dragon (2), electric (4), fighting (5), flying (10), grass (6), ground (3), normal (11), poison (1), psychic (1), rock (1), water (9).
Absent: fairy, fire, ghost, ice, steel.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mareep | electric | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| rattata | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wingull | water/flying | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| bidoof | normal | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| buizel | water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 9-12 | uncommon | route_01_pallet_to_brock | route | on it |  |
| pawmi | electric | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 12-15 | uncommon | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| gossifleur | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| corphish | water | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| bunnelby | normal | 21-23 | common | route_03_misty_to_surge | route | on it | yes |
| heracross | bug/fighting | 21-23 | common | route_03_misty_to_surge | route | on it | yes |
| noctowl | normal/flying | 21-23 | uncommon | route_03_misty_to_surge | route | on it | yes |
| pachirisu | electric | 21-23 | rare | foothill_woods | subregion | on it | yes |
| scyther | bug/flying | 21-23 | common | route_03_misty_to_surge | route | on it | yes |
| teddiursa | normal | 21-23 | uncommon | foothill_woods | subregion | on it | yes |
| machop | fighting | 22-25 | common | route_03_misty_to_surge | route | on it | yes |
| makuhita | fighting | 22-25 | common | route_03_misty_to_surge | route | on it | yes |
| rockruff | rock | 22-25 | common | route_03_misty_to_surge | route | on it | yes |
| rufflet | normal/flying | 22-25 | uncommon | route_03_misty_to_surge | route | on it | yes |
| swablu | normal/flying | 22-25 | common | route_03_misty_to_surge | route | on it | yes |
| absol | dark | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks | yes |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks | yes |
| corvisquire | flying | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks | yes |
| drampa | normal/dragon | 24-26 | uncommon | route_03_misty_to_surge | route | on it | yes |
| meditite | fighting/psychic | 24-26 | uncommon | route_03_misty_to_surge | route | on it | yes |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks | yes |
| rookidee | flying | 24-35 | common | the_tri_peaks | subregion | 9 blocks | yes |
| skiddo | grass | 24-35 | common | route_03_misty_to_surge | route | on it | yes |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks | yes |

## Gym 4: kanto_erika (Grass)

74 species catchable before this gym; 30 of them are new since the last.

Types available at the cap (L35), on the form a player would have evolved to: bug (7), dark (4), dragon (3), electric (6), fighting (5), fire (1), flying (15), grass (7), ground (3), ice (7), normal (14), poison (2), psychic (3), rock (3), steel (3), water (9).
Reached only by evolving, invisible if you read the caught form: fire.
Absent: fairy, ghost.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mareep | electric | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| rattata | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wingull | water/flying | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| bidoof | normal | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| buizel | water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 9-12 | uncommon | route_01_pallet_to_brock | route | on it |  |
| pawmi | electric | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 12-15 | uncommon | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| gossifleur | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| corphish | water | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| bunnelby | normal | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| heracross | bug/fighting | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| noctowl | normal/flying | 21-23 | uncommon | route_03_misty_to_surge | route | on it |  |
| pachirisu | electric | 21-23 | rare | foothill_woods | subregion | on it |  |
| scyther | bug/flying | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| teddiursa | normal | 21-23 | uncommon | foothill_woods | subregion | on it |  |
| machop | fighting | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| makuhita | fighting | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| rockruff | rock | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| rufflet | normal/flying | 22-25 | uncommon | route_03_misty_to_surge | route | on it |  |
| swablu | normal/flying | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| absol | dark | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks |  |
| corvisquire | flying | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| drampa | normal/dragon | 24-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| meditite | fighting/psychic | 24-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks |  |
| rookidee | flying | 24-35 | common | the_tri_peaks | subregion | 9 blocks |  |
| skiddo | grass | 24-35 | common | route_03_misty_to_surge | route | on it |  |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks |  |
| bergmite | ice | 27-29 | common | route_04_surge_to_erika | route | on it | yes |
| cryogonal | ice | 27-29 | common | route_04_surge_to_erika | route | on it | yes |
| smoochum | ice/psychic | 27-29 | common | route_04_surge_to_erika | route | on it | yes |
| aron | steel/rock | 28-30 | common | route_04_surge_to_erika | route | on it | yes |
| bronzor | steel/psychic | 28-30 | uncommon | route_04_surge_to_erika | route | on it | yes |
| nosepass | rock | 28-30 | common | route_04_surge_to_erika | route | on it | yes |
| skarmory | steel/flying | 28-30 | uncommon | the_crags | subregion | on it | yes |
| cubchoo | ice | 29-31 | uncommon | upper_trough | subregion | on it | yes |
| snom | ice/bug | 29-31 | common | route_04_surge_to_erika | route | on it | yes |
| snorunt | ice | 29-31 | common | route_04_surge_to_erika | route | on it | yes |
| vanillite | ice | 29-31 | common | route_04_surge_to_erika | route | on it | yes |
| ampharos | electric | 30-32 | ultra-rare | route_04_surge_to_erika | route | on it | yes |
| buneary | normal | 30-38 | common | north_shore_downs | subregion | 65 blocks | yes |
| dubwool | normal | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks | yes |
| emolga | electric/flying | 30-32 | common | peak_pond_hollow | subregion | on it | yes |
| flaaffy | electric | 30-32 | uncommon | route_04_surge_to_erika | route | on it | yes |
| fletchling | normal/flying | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks | yes |
| hoppip | grass/flying | 30-38 | common | north_shore_downs | subregion | 65 blocks | yes |
| jumpluff | grass/flying | 30-38 | ultra-rare | north_shore_downs | subregion | 65 blocks | yes |
| minccino | normal | 30-38 | common | north_shore_downs | subregion | 65 blocks | yes |
| pichu | electric | 30-32 | common | peak_pond_hollow | subregion | on it | yes |
| skiploom | grass/flying | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks | yes |
| ursaring | normal | 30-32 | rare | peak_pond_hollow | subregion | on it | yes |
| furret | normal | 32-34 | uncommon | north_east_downs | subregion | 97 blocks | yes |
| nickit | dark | 32-34 | uncommon | north_east_downs | subregion | 97 blocks | yes |
| sentret | normal | 32-34 | common | north_east_downs | subregion | 97 blocks | yes |
| staravia | normal/flying | 32-34 | uncommon | north_east_downs | subregion | 97 blocks | yes |
| starly | normal/flying | 32-34 | common | north_east_downs | subregion | 97 blocks | yes |
| stunky | poison/dark | 32-34 | common | north_east_downs | subregion | 97 blocks | yes |
| thievul | dark | 32-34 | rare | north_east_downs | subregion | 97 blocks | yes |

## Gym 5: kanto_koga (Poison)

91 species catchable before this gym; 17 of them are new since the last.

Types available at the cap (L40), on the form a player would have evolved to: bug (8), dark (4), dragon (3), electric (7), fighting (6), fire (1), flying (15), grass (8), ground (3), ice (8), normal (15), poison (5), psychic (4), rock (3), steel (5), water (12).
Reached only by evolving, invisible if you read the caught form: fire.
Absent: fairy, ghost.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mareep | electric | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| rattata | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wingull | water/flying | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| bidoof | normal | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| buizel | water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 9-12 | uncommon | route_01_pallet_to_brock | route | on it |  |
| pawmi | electric | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 12-15 | uncommon | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| gossifleur | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| corphish | water | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| bunnelby | normal | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| heracross | bug/fighting | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| noctowl | normal/flying | 21-23 | uncommon | route_03_misty_to_surge | route | on it |  |
| pachirisu | electric | 21-23 | rare | foothill_woods | subregion | on it |  |
| scyther | bug/flying | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| teddiursa | normal | 21-23 | uncommon | foothill_woods | subregion | on it |  |
| machop | fighting | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| makuhita | fighting | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| rockruff | rock | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| rufflet | normal/flying | 22-25 | uncommon | route_03_misty_to_surge | route | on it |  |
| swablu | normal/flying | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| absol | dark | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks |  |
| corvisquire | flying | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| drampa | normal/dragon | 24-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| meditite | fighting/psychic | 24-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks |  |
| rookidee | flying | 24-35 | common | the_tri_peaks | subregion | 9 blocks |  |
| skiddo | grass | 24-35 | common | route_03_misty_to_surge | route | on it |  |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks |  |
| bergmite | ice | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| cryogonal | ice | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| smoochum | ice/psychic | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| aron | steel/rock | 28-30 | common | route_04_surge_to_erika | route | on it |  |
| bronzor | steel/psychic | 28-30 | uncommon | route_04_surge_to_erika | route | on it |  |
| nosepass | rock | 28-30 | common | route_04_surge_to_erika | route | on it |  |
| skarmory | steel/flying | 28-30 | uncommon | the_crags | subregion | on it |  |
| cubchoo | ice | 29-31 | uncommon | upper_trough | subregion | on it |  |
| snom | ice/bug | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| snorunt | ice | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| vanillite | ice | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| ampharos | electric | 30-32 | ultra-rare | route_04_surge_to_erika | route | on it |  |
| buneary | normal | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| dubwool | normal | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| emolga | electric/flying | 30-32 | common | peak_pond_hollow | subregion | on it |  |
| flaaffy | electric | 30-32 | uncommon | route_04_surge_to_erika | route | on it |  |
| fletchling | normal/flying | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| hoppip | grass/flying | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| jumpluff | grass/flying | 30-38 | ultra-rare | north_shore_downs | subregion | 65 blocks |  |
| minccino | normal | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| pichu | electric | 30-32 | common | peak_pond_hollow | subregion | on it |  |
| skiploom | grass/flying | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| ursaring | normal | 30-32 | rare | peak_pond_hollow | subregion | on it |  |
| furret | normal | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| nickit | dark | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| sentret | normal | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| staravia | normal/flying | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| starly | normal/flying | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| stunky | poison/dark | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| thievul | dark | 32-34 | rare | north_east_downs | subregion | 97 blocks |  |
| floatzel | water | 27-38 | uncommon | lower_trough | subregion | 81 blocks | yes |
| piplup | water | 27-38 | common | lower_trough | subregion | 81 blocks | yes |
| prinplup | water | 27-38 | uncommon | lower_trough | subregion | 81 blocks | yes |
| spheal | ice/water | 27-38 | common | lower_trough | subregion | 81 blocks | yes |
| carnivine | grass | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks | yes |
| croagunk | poison/fighting | 34-44 | common | marshy_marsh | subregion | 121 blocks | yes |
| croconaw | water | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks | yes |
| feraligatr | water | 34-44 | ultra-rare | marshy_marsh | subregion | 121 blocks | yes |
| gulpin | poison | 34-44 | common | marshy_marsh | subregion | 121 blocks | yes |
| hatenna | psychic | 34-36 | common | route_05_erika_to_koga | route | on it | yes |
| hattrem | psychic | 34-36 | uncommon | route_05_erika_to_koga | route | on it | yes |
| lechonk | normal | 34-36 | common | route_05_erika_to_koga | route | on it | yes |
| spidops | bug | 34-36 | uncommon | route_05_erika_to_koga | route | on it | yes |
| swalot | poison | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks | yes |
| tarountula | bug | 34-36 | common | route_05_erika_to_koga | route | on it | yes |
| totodile | water | 34-44 | common | marshy_marsh | subregion | 121 blocks | yes |
| toxel | electric/poison | 34-36 | uncommon | route_05_erika_to_koga | route | on it | yes |

## Gym 6: kanto_sabrina (Psychic)

110 species catchable before this gym; 19 of them are new since the last.

Types available at the cap (L45), on the form a player would have evolved to: bug (10), dark (5), dragon (3), electric (7), fairy (1), fighting (6), fire (1), flying (17), grass (10), ground (5), ice (8), normal (16), poison (5), psychic (4), rock (3), steel (5), water (17).
Reached only by evolving, invisible if you read the caught form: fairy, fire.
Absent: ghost.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mareep | electric | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| rattata | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wingull | water/flying | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| bidoof | normal | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| buizel | water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 9-12 | uncommon | route_01_pallet_to_brock | route | on it |  |
| pawmi | electric | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 12-15 | uncommon | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| gossifleur | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| corphish | water | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| bunnelby | normal | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| heracross | bug/fighting | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| noctowl | normal/flying | 21-23 | uncommon | route_03_misty_to_surge | route | on it |  |
| pachirisu | electric | 21-23 | rare | foothill_woods | subregion | on it |  |
| scyther | bug/flying | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| teddiursa | normal | 21-23 | uncommon | foothill_woods | subregion | on it |  |
| machop | fighting | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| makuhita | fighting | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| rockruff | rock | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| rufflet | normal/flying | 22-25 | uncommon | route_03_misty_to_surge | route | on it |  |
| swablu | normal/flying | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| absol | dark | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks |  |
| corvisquire | flying | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| drampa | normal/dragon | 24-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| meditite | fighting/psychic | 24-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks |  |
| rookidee | flying | 24-35 | common | the_tri_peaks | subregion | 9 blocks |  |
| skiddo | grass | 24-35 | common | route_03_misty_to_surge | route | on it |  |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks |  |
| bergmite | ice | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| cryogonal | ice | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| smoochum | ice/psychic | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| aron | steel/rock | 28-30 | common | route_04_surge_to_erika | route | on it |  |
| bronzor | steel/psychic | 28-30 | uncommon | route_04_surge_to_erika | route | on it |  |
| nosepass | rock | 28-30 | common | route_04_surge_to_erika | route | on it |  |
| skarmory | steel/flying | 28-30 | uncommon | the_crags | subregion | on it |  |
| cubchoo | ice | 29-31 | uncommon | upper_trough | subregion | on it |  |
| snom | ice/bug | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| snorunt | ice | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| vanillite | ice | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| ampharos | electric | 30-32 | ultra-rare | route_04_surge_to_erika | route | on it |  |
| buneary | normal | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| dubwool | normal | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| emolga | electric/flying | 30-32 | common | peak_pond_hollow | subregion | on it |  |
| flaaffy | electric | 30-32 | uncommon | route_04_surge_to_erika | route | on it |  |
| fletchling | normal/flying | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| hoppip | grass/flying | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| jumpluff | grass/flying | 30-38 | ultra-rare | north_shore_downs | subregion | 65 blocks |  |
| minccino | normal | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| pichu | electric | 30-32 | common | peak_pond_hollow | subregion | on it |  |
| skiploom | grass/flying | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| ursaring | normal | 30-32 | rare | peak_pond_hollow | subregion | on it |  |
| furret | normal | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| nickit | dark | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| sentret | normal | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| staravia | normal/flying | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| starly | normal/flying | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| stunky | poison/dark | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| thievul | dark | 32-34 | rare | north_east_downs | subregion | 97 blocks |  |
| floatzel | water | 27-38 | uncommon | lower_trough | subregion | 81 blocks |  |
| piplup | water | 27-38 | common | lower_trough | subregion | 81 blocks |  |
| prinplup | water | 27-38 | uncommon | lower_trough | subregion | 81 blocks |  |
| spheal | ice/water | 27-38 | common | lower_trough | subregion | 81 blocks |  |
| carnivine | grass | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| croagunk | poison/fighting | 34-44 | common | marshy_marsh | subregion | 121 blocks |  |
| croconaw | water | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| feraligatr | water | 34-44 | ultra-rare | marshy_marsh | subregion | 121 blocks |  |
| gulpin | poison | 34-44 | common | marshy_marsh | subregion | 121 blocks |  |
| hatenna | psychic | 34-36 | common | route_05_erika_to_koga | route | on it |  |
| hattrem | psychic | 34-36 | uncommon | route_05_erika_to_koga | route | on it |  |
| lechonk | normal | 34-36 | common | route_05_erika_to_koga | route | on it |  |
| spidops | bug | 34-36 | uncommon | route_05_erika_to_koga | route | on it |  |
| swalot | poison | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| tarountula | bug | 34-36 | common | route_05_erika_to_koga | route | on it |  |
| totodile | water | 34-44 | common | marshy_marsh | subregion | 121 blocks |  |
| toxel | electric/poison | 34-36 | uncommon | route_05_erika_to_koga | route | on it |  |
| barboach | water/ground | 37-39 | common | route_06_koga_to_sabrina | route | on it | yes |
| palpitoad | water/ground | 37-39 | uncommon | route_06_koga_to_sabrina | route | on it | yes |
| poliwag | water | 37-39 | common | route_06_koga_to_sabrina | route | on it | yes |
| poliwhirl | water | 37-39 | uncommon | route_06_koga_to_sabrina | route | on it | yes |
| seismitoad | water/ground | 37-39 | ultra-rare | route_06_koga_to_sabrina | route | on it | yes |
| tympole | water | 37-39 | common | route_06_koga_to_sabrina | route | on it | yes |
| whiscash | water/ground | 37-39 | uncommon | marsh_creek | subregion | on it | yes |
| bibarel | normal/water | 39-41 | common | route_06_koga_to_sabrina | route | on it | yes |
| ducklett | water/flying | 39-41 | common | route_06_koga_to_sabrina | route | on it | yes |
| golduck | water | 39-41 | uncommon | route_06_koga_to_sabrina | route | on it | yes |
| psyduck | water | 39-41 | common | route_06_koga_to_sabrina | route | on it | yes |
| swanna | water/flying | 39-41 | uncommon | route_06_koga_to_sabrina | route | on it | yes |
| yanma | bug/flying | 39-41 | common | route_06_koga_to_sabrina | route | on it | yes |
| greedent | normal | 41-43 | uncommon | tilpey_east_shore | subregion | 73 blocks | yes |
| nuzleaf | grass/dark | 41-43 | uncommon | tilpey_east_shore | subregion | 73 blocks | yes |
| seedot | grass | 41-43 | common | tilpey_east_shore | subregion | 73 blocks | yes |
| sewaddle | bug/grass | 41-43 | common | tilpey_east_shore | subregion | 73 blocks | yes |
| skwovet | normal | 41-43 | common | tilpey_east_shore | subregion | 73 blocks | yes |
| swadloon | bug/grass | 41-43 | uncommon | tilpey_east_shore | subregion | 73 blocks | yes |

## Gym 7: kanto_blaine (Fire)

146 species catchable before this gym; 36 of them are new since the last.

Types available at the cap (L50), on the form a player would have evolved to: bug (15), dark (7), dragon (5), electric (8), fairy (1), fighting (6), fire (8), flying (19), ghost (1), grass (12), ground (9), ice (8), normal (16), poison (8), psychic (4), rock (6), steel (5), water (22).
Reached only by evolving, invisible if you read the caught form: fairy.
Absent: none.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mareep | electric | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| rattata | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wingull | water/flying | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| bidoof | normal | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| buizel | water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 9-12 | uncommon | route_01_pallet_to_brock | route | on it |  |
| pawmi | electric | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 12-15 | uncommon | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| gossifleur | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| corphish | water | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| bunnelby | normal | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| heracross | bug/fighting | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| noctowl | normal/flying | 21-23 | uncommon | route_03_misty_to_surge | route | on it |  |
| pachirisu | electric | 21-23 | rare | foothill_woods | subregion | on it |  |
| scyther | bug/flying | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| teddiursa | normal | 21-23 | uncommon | foothill_woods | subregion | on it |  |
| machop | fighting | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| makuhita | fighting | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| rockruff | rock | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| rufflet | normal/flying | 22-25 | uncommon | route_03_misty_to_surge | route | on it |  |
| swablu | normal/flying | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| absol | dark | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks |  |
| corvisquire | flying | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| drampa | normal/dragon | 24-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| meditite | fighting/psychic | 24-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks |  |
| rookidee | flying | 24-35 | common | the_tri_peaks | subregion | 9 blocks |  |
| skiddo | grass | 24-35 | common | route_03_misty_to_surge | route | on it |  |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks |  |
| bergmite | ice | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| cryogonal | ice | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| smoochum | ice/psychic | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| aron | steel/rock | 28-30 | common | route_04_surge_to_erika | route | on it |  |
| bronzor | steel/psychic | 28-30 | uncommon | route_04_surge_to_erika | route | on it |  |
| nosepass | rock | 28-30 | common | route_04_surge_to_erika | route | on it |  |
| skarmory | steel/flying | 28-30 | uncommon | the_crags | subregion | on it |  |
| cubchoo | ice | 29-31 | uncommon | upper_trough | subregion | on it |  |
| snom | ice/bug | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| snorunt | ice | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| vanillite | ice | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| ampharos | electric | 30-32 | ultra-rare | route_04_surge_to_erika | route | on it |  |
| buneary | normal | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| dubwool | normal | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| emolga | electric/flying | 30-32 | common | peak_pond_hollow | subregion | on it |  |
| flaaffy | electric | 30-32 | uncommon | route_04_surge_to_erika | route | on it |  |
| fletchling | normal/flying | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| hoppip | grass/flying | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| jumpluff | grass/flying | 30-38 | ultra-rare | north_shore_downs | subregion | 65 blocks |  |
| minccino | normal | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| pichu | electric | 30-32 | common | peak_pond_hollow | subregion | on it |  |
| skiploom | grass/flying | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| ursaring | normal | 30-32 | rare | peak_pond_hollow | subregion | on it |  |
| furret | normal | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| nickit | dark | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| sentret | normal | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| staravia | normal/flying | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| starly | normal/flying | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| stunky | poison/dark | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| thievul | dark | 32-34 | rare | north_east_downs | subregion | 97 blocks |  |
| floatzel | water | 27-38 | uncommon | lower_trough | subregion | 81 blocks |  |
| piplup | water | 27-38 | common | lower_trough | subregion | 81 blocks |  |
| prinplup | water | 27-38 | uncommon | lower_trough | subregion | 81 blocks |  |
| spheal | ice/water | 27-38 | common | lower_trough | subregion | 81 blocks |  |
| carnivine | grass | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| croagunk | poison/fighting | 34-44 | common | marshy_marsh | subregion | 121 blocks |  |
| croconaw | water | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| feraligatr | water | 34-44 | ultra-rare | marshy_marsh | subregion | 121 blocks |  |
| gulpin | poison | 34-44 | common | marshy_marsh | subregion | 121 blocks |  |
| hatenna | psychic | 34-36 | common | route_05_erika_to_koga | route | on it |  |
| hattrem | psychic | 34-36 | uncommon | route_05_erika_to_koga | route | on it |  |
| lechonk | normal | 34-36 | common | route_05_erika_to_koga | route | on it |  |
| spidops | bug | 34-36 | uncommon | route_05_erika_to_koga | route | on it |  |
| swalot | poison | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| tarountula | bug | 34-36 | common | route_05_erika_to_koga | route | on it |  |
| totodile | water | 34-44 | common | marshy_marsh | subregion | 121 blocks |  |
| toxel | electric/poison | 34-36 | uncommon | route_05_erika_to_koga | route | on it |  |
| barboach | water/ground | 37-39 | common | route_06_koga_to_sabrina | route | on it |  |
| palpitoad | water/ground | 37-39 | uncommon | route_06_koga_to_sabrina | route | on it |  |
| poliwag | water | 37-39 | common | route_06_koga_to_sabrina | route | on it |  |
| poliwhirl | water | 37-39 | uncommon | route_06_koga_to_sabrina | route | on it |  |
| seismitoad | water/ground | 37-39 | ultra-rare | route_06_koga_to_sabrina | route | on it |  |
| tympole | water | 37-39 | common | route_06_koga_to_sabrina | route | on it |  |
| whiscash | water/ground | 37-39 | uncommon | marsh_creek | subregion | on it |  |
| bibarel | normal/water | 39-41 | common | route_06_koga_to_sabrina | route | on it |  |
| ducklett | water/flying | 39-41 | common | route_06_koga_to_sabrina | route | on it |  |
| golduck | water | 39-41 | uncommon | route_06_koga_to_sabrina | route | on it |  |
| psyduck | water | 39-41 | common | route_06_koga_to_sabrina | route | on it |  |
| swanna | water/flying | 39-41 | uncommon | route_06_koga_to_sabrina | route | on it |  |
| yanma | bug/flying | 39-41 | common | route_06_koga_to_sabrina | route | on it |  |
| greedent | normal | 41-43 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| nuzleaf | grass/dark | 41-43 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| seedot | grass | 41-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| sewaddle | bug/grass | 41-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| skwovet | normal | 41-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| swadloon | bug/grass | 41-43 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| cacnea | grass | 25-45 | common | east_coast_dunes | subregion | 33 blocks | yes |
| sandile | ground/dark | 25-45 | common | east_coast_dunes | subregion | 33 blocks | yes |
| silicobra | ground | 25-45 | common | east_coast_dunes | subregion | 33 blocks | yes |
| trapinch | ground | 25-45 | common | east_coast_dunes | subregion | 33 blocks | yes |
| foongus | grass/poison | 34-44 | common | eastern_moor | subregion | 105 blocks | yes |
| karrablast | bug | 34-44 | common | eastern_moor | subregion | 105 blocks | yes |
| shelmet | bug | 34-44 | uncommon | eastern_moor | subregion | 105 blocks | yes |
| arrokuda | water | 39-48 | uncommon | tilpey_waters | subregion | 1 blocks | yes |
| barraskewda | water | 39-48 | rare | tilpey_waters | subregion | 1 blocks | yes |
| basculegion | water/ghost | 39-48 | uncommon | tilpey_waters | subregion | 1 blocks | yes |
| basculin | water | 39-48 | common | tilpey_waters | subregion | 1 blocks | yes |
| goldeen | water | 39-48 | common | tilpey_waters | subregion | 1 blocks | yes |
| gyarados | water/flying | 39-48 | uncommon | tilpey_waters | subregion | 1 blocks | yes |
| magikarp | water | 39-48 | common | tilpey_waters | subregion | 1 blocks | yes |
| seaking | water | 39-48 | uncommon | tilpey_waters | subregion | 1 blocks | yes |
| tadbulb | electric | 39-48 | rare | tilpey_waters | subregion | 1 blocks | yes |
| beedrill | bug/poison | 42-44 | ultra-rare | tilpey_south_shore | subregion | on it | yes |
| butterfree | bug/flying | 42-44 | ultra-rare | route_07_sabrina_to_blaine | route | on it | yes |
| caterpie | bug | 42-44 | common | route_07_sabrina_to_blaine | route | on it | yes |
| kakuna | bug/poison | 42-44 | uncommon | tilpey_south_shore | subregion | on it | yes |
| metapod | bug | 42-44 | uncommon | route_07_sabrina_to_blaine | route | on it | yes |
| weedle | bug/poison | 42-44 | common | tilpey_south_shore | subregion | on it | yes |
| aggron | steel/rock | 44-52 | ultra-rare | east_cones | subregion | 97 blocks | yes |
| carkol | rock/fire | 44-52 | uncommon | east_cones | subregion | 97 blocks | yes |
| centiskorch | fire/bug | 44-46 | uncommon | route_07_sabrina_to_blaine | route | on it | yes |
| coalossal | rock/fire | 44-52 | ultra-rare | east_cones | subregion | 97 blocks | yes |
| heatmor | fire | 44-46 | common | route_07_sabrina_to_blaine | route | on it | yes |
| lairon | steel/rock | 44-52 | uncommon | east_cones | subregion | 97 blocks | yes |
| rhydon | ground/rock | 44-46 | rare | crater_rim_north_west | subregion | on it | yes |
| rhyhorn | ground/rock | 44-46 | rare | crater_rim_north_west | subregion | on it | yes |
| rolycoly | rock | 44-52 | common | east_cones | subregion | 97 blocks | yes |
| salandit | poison/fire | 44-46 | common | route_07_sabrina_to_blaine | route | on it | yes |
| sizzlipede | fire/bug | 44-46 | common | route_07_sabrina_to_blaine | route | on it | yes |
| slugma | fire | 44-46 | common | route_07_sabrina_to_blaine | route | on it | yes |
| torkoal | fire | 44-46 | uncommon | crater_rim_north_west | subregion | on it | yes |
| turtonator | fire/dragon | 44-46 | uncommon | crater_rim_north_west | subregion | on it | yes |

## Gym 8: kanto_giovanni (Ground)

184 species catchable before this gym; 38 of them are new since the last.

Types available at the cap (L55), on the form a player would have evolved to: bug (17), dark (10), dragon (5), electric (9), fairy (1), fighting (7), fire (11), flying (21), ghost (2), grass (14), ground (12), ice (8), normal (16), poison (12), psychic (4), rock (8), steel (5), water (25).
Reached only by evolving, invisible if you read the caught form: fairy.
Absent: none.

| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mareep | electric | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| pidgey | normal/flying | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| rattata | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| wooloo | normal | 5-8 | common | route_01_pallet_to_brock | route | on it |  |
| krabby | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| shellder | water | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| staryu | water | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| wattrel | electric/flying | 7-10 | uncommon | route_01_pallet_to_brock | route | on it |  |
| wingull | water/flying | 7-10 | common | route_01_pallet_to_brock | route | on it |  |
| bidoof | normal | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| buizel | water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| deerling | normal/grass | 9-12 | uncommon | route_01_pallet_to_brock | route | on it |  |
| pawmi | electric | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| surskit | bug/water | 9-12 | common | route_01_pallet_to_brock | route | on it |  |
| applin | grass/dragon | 12-15 | uncommon | route_01_pallet_to_brock | route | on it |  |
| combee | bug/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| fomantis | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| gossifleur | grass | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| hoothoot | normal/flying | 12-15 | common | route_01_pallet_to_brock | route | on it |  |
| corphish | water | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| illumise | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lombre | water/grass | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| lotad | water/grass | 18-21 | common | route_02_brock_to_misty | route | on it |  |
| volbeat | bug | 18-21 | uncommon | route_02_brock_to_misty | route | on it |  |
| bunnelby | normal | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| heracross | bug/fighting | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| noctowl | normal/flying | 21-23 | uncommon | route_03_misty_to_surge | route | on it |  |
| pachirisu | electric | 21-23 | rare | foothill_woods | subregion | on it |  |
| scyther | bug/flying | 21-23 | common | route_03_misty_to_surge | route | on it |  |
| teddiursa | normal | 21-23 | uncommon | foothill_woods | subregion | on it |  |
| machop | fighting | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| makuhita | fighting | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| rockruff | rock | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| rufflet | normal/flying | 22-25 | uncommon | route_03_misty_to_surge | route | on it |  |
| swablu | normal/flying | 22-25 | common | route_03_misty_to_surge | route | on it |  |
| absol | dark | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| clodsire | poison/ground | 24-30 | rare | mt_clay_outflow | waterway | 57 blocks |  |
| corvisquire | flying | 24-35 | uncommon | the_tri_peaks | subregion | 9 blocks |  |
| drampa | normal/dragon | 24-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| meditite | fighting/psychic | 24-26 | uncommon | route_03_misty_to_surge | route | on it |  |
| quagsire | water/ground | 24-30 | uncommon | mt_clay_outflow | waterway | 57 blocks |  |
| rookidee | flying | 24-35 | common | the_tri_peaks | subregion | 9 blocks |  |
| skiddo | grass | 24-35 | common | route_03_misty_to_surge | route | on it |  |
| wooper | water/ground | 24-30 | common | mt_clay_outflow | waterway | 57 blocks |  |
| bergmite | ice | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| cryogonal | ice | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| smoochum | ice/psychic | 27-29 | common | route_04_surge_to_erika | route | on it |  |
| aron | steel/rock | 28-30 | common | route_04_surge_to_erika | route | on it |  |
| bronzor | steel/psychic | 28-30 | uncommon | route_04_surge_to_erika | route | on it |  |
| nosepass | rock | 28-30 | common | route_04_surge_to_erika | route | on it |  |
| skarmory | steel/flying | 28-30 | uncommon | the_crags | subregion | on it |  |
| cubchoo | ice | 29-31 | uncommon | upper_trough | subregion | on it |  |
| snom | ice/bug | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| snorunt | ice | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| vanillite | ice | 29-31 | common | route_04_surge_to_erika | route | on it |  |
| ampharos | electric | 30-32 | ultra-rare | route_04_surge_to_erika | route | on it |  |
| buneary | normal | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| dubwool | normal | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| emolga | electric/flying | 30-32 | common | peak_pond_hollow | subregion | on it |  |
| flaaffy | electric | 30-32 | uncommon | route_04_surge_to_erika | route | on it |  |
| fletchling | normal/flying | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| hoppip | grass/flying | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| jumpluff | grass/flying | 30-38 | ultra-rare | north_shore_downs | subregion | 65 blocks |  |
| minccino | normal | 30-38 | common | north_shore_downs | subregion | 65 blocks |  |
| pichu | electric | 30-32 | common | peak_pond_hollow | subregion | on it |  |
| skiploom | grass/flying | 30-38 | uncommon | north_shore_downs | subregion | 65 blocks |  |
| ursaring | normal | 30-32 | rare | peak_pond_hollow | subregion | on it |  |
| furret | normal | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| nickit | dark | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| sentret | normal | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| staravia | normal/flying | 32-34 | uncommon | north_east_downs | subregion | 97 blocks |  |
| starly | normal/flying | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| stunky | poison/dark | 32-34 | common | north_east_downs | subregion | 97 blocks |  |
| thievul | dark | 32-34 | rare | north_east_downs | subregion | 97 blocks |  |
| floatzel | water | 27-38 | uncommon | lower_trough | subregion | 81 blocks |  |
| piplup | water | 27-38 | common | lower_trough | subregion | 81 blocks |  |
| prinplup | water | 27-38 | uncommon | lower_trough | subregion | 81 blocks |  |
| spheal | ice/water | 27-38 | common | lower_trough | subregion | 81 blocks |  |
| carnivine | grass | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| croagunk | poison/fighting | 34-44 | common | marshy_marsh | subregion | 121 blocks |  |
| croconaw | water | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| feraligatr | water | 34-44 | ultra-rare | marshy_marsh | subregion | 121 blocks |  |
| gulpin | poison | 34-44 | common | marshy_marsh | subregion | 121 blocks |  |
| hatenna | psychic | 34-36 | common | route_05_erika_to_koga | route | on it |  |
| hattrem | psychic | 34-36 | uncommon | route_05_erika_to_koga | route | on it |  |
| lechonk | normal | 34-36 | common | route_05_erika_to_koga | route | on it |  |
| spidops | bug | 34-36 | uncommon | route_05_erika_to_koga | route | on it |  |
| swalot | poison | 34-44 | uncommon | marshy_marsh | subregion | 121 blocks |  |
| tarountula | bug | 34-36 | common | route_05_erika_to_koga | route | on it |  |
| totodile | water | 34-44 | common | marshy_marsh | subregion | 121 blocks |  |
| toxel | electric/poison | 34-36 | uncommon | route_05_erika_to_koga | route | on it |  |
| barboach | water/ground | 37-39 | common | route_06_koga_to_sabrina | route | on it |  |
| palpitoad | water/ground | 37-39 | uncommon | route_06_koga_to_sabrina | route | on it |  |
| poliwag | water | 37-39 | common | route_06_koga_to_sabrina | route | on it |  |
| poliwhirl | water | 37-39 | uncommon | route_06_koga_to_sabrina | route | on it |  |
| seismitoad | water/ground | 37-39 | ultra-rare | route_06_koga_to_sabrina | route | on it |  |
| tympole | water | 37-39 | common | route_06_koga_to_sabrina | route | on it |  |
| whiscash | water/ground | 37-39 | uncommon | marsh_creek | subregion | on it |  |
| bibarel | normal/water | 39-41 | common | route_06_koga_to_sabrina | route | on it |  |
| ducklett | water/flying | 39-41 | common | route_06_koga_to_sabrina | route | on it |  |
| golduck | water | 39-41 | uncommon | route_06_koga_to_sabrina | route | on it |  |
| psyduck | water | 39-41 | common | route_06_koga_to_sabrina | route | on it |  |
| swanna | water/flying | 39-41 | uncommon | route_06_koga_to_sabrina | route | on it |  |
| yanma | bug/flying | 39-41 | common | route_06_koga_to_sabrina | route | on it |  |
| greedent | normal | 41-43 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| nuzleaf | grass/dark | 41-43 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| seedot | grass | 41-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| sewaddle | bug/grass | 41-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| skwovet | normal | 41-43 | common | tilpey_east_shore | subregion | 73 blocks |  |
| swadloon | bug/grass | 41-43 | uncommon | tilpey_east_shore | subregion | 73 blocks |  |
| cacnea | grass | 25-45 | common | east_coast_dunes | subregion | 33 blocks |  |
| sandile | ground/dark | 25-45 | common | east_coast_dunes | subregion | 33 blocks |  |
| silicobra | ground | 25-45 | common | east_coast_dunes | subregion | 33 blocks |  |
| trapinch | ground | 25-45 | common | east_coast_dunes | subregion | 33 blocks |  |
| foongus | grass/poison | 34-44 | common | eastern_moor | subregion | 105 blocks |  |
| karrablast | bug | 34-44 | common | eastern_moor | subregion | 105 blocks |  |
| shelmet | bug | 34-44 | uncommon | eastern_moor | subregion | 105 blocks |  |
| arrokuda | water | 39-48 | uncommon | tilpey_waters | subregion | 1 blocks |  |
| barraskewda | water | 39-48 | rare | tilpey_waters | subregion | 1 blocks |  |
| basculegion | water/ghost | 39-48 | uncommon | tilpey_waters | subregion | 1 blocks |  |
| basculin | water | 39-48 | common | tilpey_waters | subregion | 1 blocks |  |
| goldeen | water | 39-48 | common | tilpey_waters | subregion | 1 blocks |  |
| gyarados | water/flying | 39-48 | uncommon | tilpey_waters | subregion | 1 blocks |  |
| magikarp | water | 39-48 | common | tilpey_waters | subregion | 1 blocks |  |
| seaking | water | 39-48 | uncommon | tilpey_waters | subregion | 1 blocks |  |
| tadbulb | electric | 39-48 | rare | tilpey_waters | subregion | 1 blocks |  |
| beedrill | bug/poison | 42-44 | ultra-rare | tilpey_south_shore | subregion | on it |  |
| butterfree | bug/flying | 42-44 | ultra-rare | route_07_sabrina_to_blaine | route | on it |  |
| caterpie | bug | 42-44 | common | route_07_sabrina_to_blaine | route | on it |  |
| kakuna | bug/poison | 42-44 | uncommon | tilpey_south_shore | subregion | on it |  |
| metapod | bug | 42-44 | uncommon | route_07_sabrina_to_blaine | route | on it |  |
| weedle | bug/poison | 42-44 | common | tilpey_south_shore | subregion | on it |  |
| aggron | steel/rock | 44-52 | ultra-rare | east_cones | subregion | 97 blocks |  |
| carkol | rock/fire | 44-52 | uncommon | east_cones | subregion | 97 blocks |  |
| centiskorch | fire/bug | 44-46 | uncommon | route_07_sabrina_to_blaine | route | on it |  |
| coalossal | rock/fire | 44-52 | ultra-rare | east_cones | subregion | 97 blocks |  |
| heatmor | fire | 44-46 | common | route_07_sabrina_to_blaine | route | on it |  |
| lairon | steel/rock | 44-52 | uncommon | east_cones | subregion | 97 blocks |  |
| rhydon | ground/rock | 44-46 | rare | crater_rim_north_west | subregion | on it |  |
| rhyhorn | ground/rock | 44-46 | rare | crater_rim_north_west | subregion | on it |  |
| rolycoly | rock | 44-52 | common | east_cones | subregion | 97 blocks |  |
| salandit | poison/fire | 44-46 | common | route_07_sabrina_to_blaine | route | on it |  |
| sizzlipede | fire/bug | 44-46 | common | route_07_sabrina_to_blaine | route | on it |  |
| slugma | fire | 44-46 | common | route_07_sabrina_to_blaine | route | on it |  |
| torkoal | fire | 44-46 | uncommon | crater_rim_north_west | subregion | on it |  |
| turtonator | fire/dragon | 44-46 | uncommon | crater_rim_north_west | subregion | on it |  |
| camerupt | fire/ground | 44-52 | uncommon | great_crater | subregion | 65 blocks | yes |
| charizard | fire/flying | 44-52 | ultra-rare | great_crater | subregion | 65 blocks | yes |
| charmander | fire | 44-52 | common | great_crater | subregion | 65 blocks | yes |
| charmeleon | fire | 44-52 | uncommon | great_crater | subregion | 65 blocks | yes |
| magby | fire | 44-52 | common | great_crater | subregion | 65 blocks | yes |
| magcargo | fire/rock | 44-52 | uncommon | great_crater | subregion | 65 blocks | yes |
| magmar | fire | 44-52 | uncommon | great_crater | subregion | 65 blocks | yes |
| numel | fire/ground | 44-52 | common | great_crater | subregion | 65 blocks | yes |
| bramblin | grass/ghost | 47-54 | uncommon | plateau_south | subregion | on it | yes |
| cacturne | grass/dark | 47-49 | uncommon | route_08_blaine_to_giovanni | route | on it | yes |
| crustle | bug/rock | 47-54 | uncommon | plateau_south | subregion | on it | yes |
| donphan | ground | 47-54 | uncommon | plateau_south | subregion | on it | yes |
| drapion | poison/dark | 47-49 | uncommon | route_08_blaine_to_giovanni | route | on it | yes |
| dwebble | bug/rock | 47-54 | common | plateau_south | subregion | on it | yes |
| klawf | rock | 47-54 | uncommon | plateau_south | subregion | on it | yes |
| krokorok | ground/dark | 47-49 | uncommon | plateau_west | subregion | on it | yes |
| krookodile | ground/dark | 47-49 | ultra-rare | plateau_west | subregion | on it | yes |
| maractus | grass | 47-49 | uncommon | plateau_west | subregion | on it | yes |
| mudbray | ground | 47-54 | common | plateau_south | subregion | on it | yes |
| mudsdale | ground | 47-54 | uncommon | plateau_south | subregion | on it | yes |
| phanpy | ground | 47-54 | common | plateau_south | subregion | on it | yes |
| skorupi | poison/bug | 47-49 | common | route_08_blaine_to_giovanni | route | on it | yes |
| vullaby | dark/flying | 47-49 | common | plateau_west | subregion | on it | yes |
| mightyena | dark | 49-51 | uncommon | rift_foot | subregion | on it | yes |
| nidoranf | poison | 49-51 | common | route_08_blaine_to_giovanni | route | on it | yes |
| nidoranm | poison | 49-51 | common | route_08_blaine_to_giovanni | route | on it | yes |
| nidorina | poison | 49-51 | uncommon | route_08_blaine_to_giovanni | route | on it | yes |
| nidorino | poison | 49-51 | uncommon | rift_foot | subregion | on it | yes |
| poochyena | dark | 49-51 | common | rift_foot | subregion | on it | yes |
| clauncher | water | 50-52 | common | south_strand | subregion | on it | yes |
| clawitzer | water | 50-52 | uncommon | south_strand | subregion | on it | yes |
| crabrawler | fighting | 50-52 | uncommon | south_strand | subregion | on it | yes |
| golisopod | bug/water | 50-52 | uncommon | south_strand | subregion | on it | yes |
| kilowattrel | electric/flying | 50-52 | uncommon | route_08_blaine_to_giovanni | route | on it | yes |
| mareanie | poison/water | 50-52 | common | route_08_blaine_to_giovanni | route | on it | yes |
| pincurchin | electric | 50-52 | uncommon | south_strand | subregion | on it | yes |
| toxapex | poison/water | 50-52 | uncommon | route_08_blaine_to_giovanni | route | on it | yes |
| wimpod | bug/water | 50-52 | common | south_strand | subregion | on it | yes |

## Pools off the route corridor

Reachable by walking, but nothing gates when, so they are not assigned to a gym.

| Pool | Kind | Nearest route | Gap (blocks) | Species |
| --- | --- | --- | --- | --- |
| viltris_path_valley | subregion | route_01_pallet_to_brock | 153 | bunnelby, fletchling, hoothoot, patrat, poochyena, zigzagoon |
| rift_south_east_arm | subregion | route_08_blaine_to_giovanni | 209 | baltoy, claydol, druddigon, gligar, golett, golurk, lunatone, rolycoly, solrock |
| rift_south_west_arm | subregion | route_08_blaine_to_giovanni | 225 | crustle, cubone, dwebble, glimmet, glimmora, rolycoly, runerigus, scrafty, scraggy |
| north_west_coast | subregion | route_03_misty_to_surge | 281 | binacle, hoothoot, inkay, krabby, shellder, wingull |
| rift_trunk | subregion | route_04_surge_to_erika | 313 | boldore, carkol, coalossal, garganacl, nacli, naclstack, orthworm, roggenrola, rolycoly |
| south_west_fields | subregion | route_01_pallet_to_brock | 337 | caterpie, cottonee, hoppip, pidgey, smoliv |
| arrow_creeks | subregion | route_08_blaine_to_giovanni | 377 | blitzle, dodrio, doduo, donphan, flamigo, girafarig, phanpy, wattrel, zebstrika |
| shrew_lake_shores | subregion | route_02_brock_to_misty | 385 | cherubi, poltchageist, ralts, surskit, togepi |
| plateau_east | subregion | route_08_blaine_to_giovanni | 401 | cacnea, durant, heatmor, houndoom, houndour, larvesta, litleo, orthworm, pyroar |
| fungal_north | subregion | route_01_pallet_to_brock | 425 | breloom, foongus, morelull, paras, parasect, shiinotic, shroomish, toedscool |
| frostpeak_strand | subregion | route_04_surge_to_erika | 433 | delibird, sandshrew, sandslash, spheal, stantler, vulpix |
| fungal_south | subregion | route_01_pallet_to_brock | 433 | lechonk, palpitoad, poliwag, poliwhirl, quagsire, shroomish, tympole, wooper |
| south_east_dunes | subregion | route_08_blaine_to_giovanni | 441 | flittle, helioptile, hippopotas, rellor, sandile, sigilyph |
| wedge_south | subregion | route_08_blaine_to_giovanni | 449 | duskull, golbat, phantump, shuppet, venonat, zubat |
| wedge_north | subregion | route_06_koga_to_sabrina | 457 | gastly, haunter, impidimp, misdreavus, murkrow, phantump |
| tilpey_west_meadows | subregion | route_06_koga_to_sabrina | 561 | cherrim, cherubi, cutiefly, gloom, oddish, petilil, psyduck, ribombee |
| rift_west_spur | subregion | route_04_surge_to_erika | 569 | bisharp, bronzong, bronzor, klang, klink, klinklang, pawniard, revavroom, rolycoly, varoom |
| sunset_east | subregion | route_08_blaine_to_giovanni | 601 | comfey, cutiefly, fomantis, oricorio, petilil, ribombee, smoliv |
| frostpeak | subregion | route_04_surge_to_erika | 665 | absol, crabrawler, delibird, drampa, sneasel, snorunt |
| jungle_west | subregion | route_08_blaine_to_giovanni | 689 | aipom, heracross, kecleon, pikipek, slakoth, tropius, trumbeak, vigoroth |
| arrow_lake_shores | subregion | route_02_brock_to_misty | 721 | audino, azurill, budew, surskit |
| northgate_west | subregion | route_05_erika_to_koga | 753 | ariados, hoothoot, noctowl, phantump, pineco, spinarak, stantler, teddiursa |
| northgate_east | subregion | route_05_erika_to_koga | 793 | deerling, furret, greedent, pachirisu, pineco, sentret, skwovet, staravia, starly |
| jungle_east | subregion | route_08_blaine_to_giovanni | 857 | hawlucha, komala, oranguru, passimian, pikipek, shroodle |
| long_isle_north | subregion | route_07_sabrina_to_blaine | 913 | corvisquire, deerling, greedent, linoone, nickit, rookidee, skwovet, thievul, zigzagoon |
| long_isle_middle | subregion | route_07_sabrina_to_blaine | 1049 | applin, deerling, nincada, ninjask, nuzleaf, seedot, shedinja |
| south_pine_isle | subregion | route_06_koga_to_sabrina | 1057 | buneary, dartrix, rowlet, snover, vulpix, zorua |
| sunset_west | subregion | route_01_pallet_to_brock | 1361 | blitzle, doduo, girafarig, litleo, mudbray, oricorio |
| long_isle_south | subregion | route_08_blaine_to_giovanni | 1585 | bounsweet, chatot, deerling, fomantis, squawkabilly, steenee, wimpod |
| north_pine_isle | subregion | route_06_koga_to_sabrina | 1929 | delibird, sandshrew, sneasel, snom, snover, stantler, vulpix |

## Habitat pools: none of them reach a player

A habitat pool only spawns where a Cobblemon Habitat Block stands. `data/habitat_blocks.json` places
**no blocks anywhere**, so every pool below is authored and inert.

| Pool | Blocks placed | Species |
| --- | --- | --- |
| displaced_city_cavern | 0 |  |
| glacial_tear_deep_valley | 0 |  |
| great_crater_bowls | 0 |  |
| marshy_marsh_basin | 0 |  |
| mining_town_fossil_levels | 0 |  |
| northgate_old_growth_grove | 0 |  |
| rift_depths | 0 |  |
| route_1_ghost_mansion | 0 |  |
| tree_town_canopy | 0 |  |

## What this document still does not cover

The pack's own inherited pools. `data/spawn_suppression.json` retains upstream defaults in "unauthored
caves", off-route wilderness, open ocean and the Nether and End, and the bounded-suppression override
pack is not installed on the staging server. Measured 2026-09-24 over the server's mods and datapacks:
**2,662 readable spawn pool files carrying 5,850 underground-only spawn details** (Cobblemon 3,657,
COBBLEVERSE-DP-v31 2,037, three addons the rest), naming 855 distinct species.

Those are not ordered by route and cannot be placed on this progression, but they are live. Any
conclusion of the form "a player cannot get an X before gym N" is unsafe until they are accounted for.

