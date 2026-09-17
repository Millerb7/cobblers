# Critical-path Pokémon availability

**Status:** compiled design audit; generated spawn pools are not installed or runtime-proven.

**Re-derived 2026-09-16** from the regenerated pools: `tools/compile_spawns.py` output in `build/datapacks/cobblers_spawns/`, 1,408 route boxes and 7,066 route entries. The earlier pools had 1,269 boxes and 6,526 entries. Every table and assessment below came out identical to the previous derivation. The regeneration temporarily lost the River of Shrews vale on Route 1 and the mountain species on Route 3, and has restored both, so no species' first appearance, level band or source corridor changed. The shelf's `the_tri_peaks` boxes are new on Route 3, but their ambient species (Swablu, Skiddo) already appear earlier on that leg.

This table works outward from what players can actually encounter before each gym. It includes only ambient species emitted by the curated critical-route compilation. Authored rewards, optional Habitat sites, player-only evolutions and open wilderness defaults do not carry a required matchup.

Wild level bands are static and spatial. A species listed on an earlier leg remains plausibly catchable and trainable for later gyms; the displayed range is where it first becomes available.

The assessment lines below measure type availability only. They do not account for evolution gates, learned moves, coverage, held items, level gaps, mixed rosters, or battle format. `GYM_SUFFICIENCY_AUDIT.md` performs that second check and supersedes the sufficiency labels for Gyms 3, 5, 6, and 8.

## Gym 1: kanto_brock (Rock)

| Species | First wild levels | Types | First/source corridor |
| --- | --- | --- | --- |
| Pidgey | 5-8 | Normal, Flying | route_01_pallet_to_brock / pallet_meadows |
| Rattata | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Mareep | 5-8 | Electric | route_01_pallet_to_brock / pallet_meadows |
| Wooloo | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Wingull | 7-10 | Water, Flying | route_01_pallet_to_brock / west_shore |
| Krabby | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Staryu | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Shellder | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Wattrel | 7-10 | Electric, Flying | route_01_pallet_to_brock / west_shore |
| Surskit | 9-12 | Bug, Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Buizel | 9-12 | Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Bidoof | 9-12 | Normal | route_01_pallet_to_brock / river_of_shrews_vale |
| Pawmi | 9-12 | Electric | route_01_pallet_to_brock / river_of_shrews_vale |
| Deerling | 9-12 | Normal, Grass | route_01_pallet_to_brock / river_of_shrews_vale |
| Hoothoot | 12-15 | Normal, Flying | route_01_pallet_to_brock / viltri_plateau |
| Combee | 12-15 | Bug, Flying | route_01_pallet_to_brock / viltri_plateau |
| Fomantis | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Gossifleur | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Applin | 12-15 | Grass, Dragon | route_01_pallet_to_brock / viltri_plateau |

**Assessment:** VIABLE: Wingull, Krabby, Staryu, Surskit, Buizel, Fomantis, Gossifleur are common, ungated type answers.

## Gym 2: kanto_misty (Water)

| Species | First wild levels | Types | First/source corridor |
| --- | --- | --- | --- |
| Pidgey | 5-8 | Normal, Flying | route_01_pallet_to_brock / pallet_meadows |
| Rattata | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Mareep | 5-8 | Electric | route_01_pallet_to_brock / pallet_meadows |
| Wooloo | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Wingull | 7-10 | Water, Flying | route_01_pallet_to_brock / west_shore |
| Krabby | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Staryu | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Shellder | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Wattrel | 7-10 | Electric, Flying | route_01_pallet_to_brock / west_shore |
| Surskit | 9-12 | Bug, Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Buizel | 9-12 | Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Bidoof | 9-12 | Normal | route_01_pallet_to_brock / river_of_shrews_vale |
| Pawmi | 9-12 | Electric | route_01_pallet_to_brock / river_of_shrews_vale |
| Deerling | 9-12 | Normal, Grass | route_01_pallet_to_brock / river_of_shrews_vale |
| Hoothoot | 12-15 | Normal, Flying | route_01_pallet_to_brock / viltri_plateau |
| Combee | 12-15 | Bug, Flying | route_01_pallet_to_brock / viltri_plateau |
| Fomantis | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Gossifleur | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Applin | 12-15 | Grass, Dragon | route_01_pallet_to_brock / viltri_plateau |
| Lotad | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Lombre | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Corphish | 18-21 | Water | route_02_brock_to_misty / lake_viltri_hollow |
| Volbeat | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Illumise | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |

**Assessment:** VIABLE: Mareep, Pawmi, Fomantis, Gossifleur, Lotad are common, ungated type answers.

## Gym 3: kanto_ltsurge (Electric)

| Species | First wild levels | Types | First/source corridor |
| --- | --- | --- | --- |
| Pidgey | 5-8 | Normal, Flying | route_01_pallet_to_brock / pallet_meadows |
| Rattata | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Mareep | 5-8 | Electric | route_01_pallet_to_brock / pallet_meadows |
| Wooloo | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Wingull | 7-10 | Water, Flying | route_01_pallet_to_brock / west_shore |
| Krabby | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Staryu | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Shellder | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Wattrel | 7-10 | Electric, Flying | route_01_pallet_to_brock / west_shore |
| Surskit | 9-12 | Bug, Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Buizel | 9-12 | Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Bidoof | 9-12 | Normal | route_01_pallet_to_brock / river_of_shrews_vale |
| Pawmi | 9-12 | Electric | route_01_pallet_to_brock / river_of_shrews_vale |
| Deerling | 9-12 | Normal, Grass | route_01_pallet_to_brock / river_of_shrews_vale |
| Hoothoot | 12-15 | Normal, Flying | route_01_pallet_to_brock / viltri_plateau |
| Combee | 12-15 | Bug, Flying | route_01_pallet_to_brock / viltri_plateau |
| Fomantis | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Gossifleur | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Applin | 12-15 | Grass, Dragon | route_01_pallet_to_brock / viltri_plateau |
| Lotad | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Lombre | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Corphish | 18-21 | Water | route_02_brock_to_misty / lake_viltri_hollow |
| Volbeat | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Illumise | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Noctowl | 21-23 | Normal, Flying | route_03_misty_to_surge / foothill_woods |
| Heracross | 21-23 | Bug, Fighting | route_03_misty_to_surge / foothill_woods |
| Scyther | 21-23 | Bug, Flying | route_03_misty_to_surge / foothill_woods |
| Bunnelby | 21-23 | Normal | route_03_misty_to_surge / foothill_woods |
| Swablu | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Rockruff | 22-25 | Rock | route_03_misty_to_surge / mt_clay |
| Makuhita | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Machop | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Rufflet | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Skiddo | 24-26 | Grass | route_03_misty_to_surge / mt_vessu |
| Meditite | 24-26 | Fighting, Psychic | route_03_misty_to_surge / mt_vessu |
| Drampa | 24-26 | Normal, Dragon | route_03_misty_to_surge / mt_vessu |

**Assessment:** VIABLE BUT THIN: Bunnelby is the single dependable Ground family. Keep it common and ungated; the fallback Grass resistances do not replace immunity.

## Gym 4: kanto_erika (Grass)

| Species | First wild levels | Types | First/source corridor |
| --- | --- | --- | --- |
| Pidgey | 5-8 | Normal, Flying | route_01_pallet_to_brock / pallet_meadows |
| Rattata | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Mareep | 5-8 | Electric | route_01_pallet_to_brock / pallet_meadows |
| Wooloo | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Wingull | 7-10 | Water, Flying | route_01_pallet_to_brock / west_shore |
| Krabby | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Staryu | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Shellder | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Wattrel | 7-10 | Electric, Flying | route_01_pallet_to_brock / west_shore |
| Surskit | 9-12 | Bug, Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Buizel | 9-12 | Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Bidoof | 9-12 | Normal | route_01_pallet_to_brock / river_of_shrews_vale |
| Pawmi | 9-12 | Electric | route_01_pallet_to_brock / river_of_shrews_vale |
| Deerling | 9-12 | Normal, Grass | route_01_pallet_to_brock / river_of_shrews_vale |
| Hoothoot | 12-15 | Normal, Flying | route_01_pallet_to_brock / viltri_plateau |
| Combee | 12-15 | Bug, Flying | route_01_pallet_to_brock / viltri_plateau |
| Fomantis | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Gossifleur | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Applin | 12-15 | Grass, Dragon | route_01_pallet_to_brock / viltri_plateau |
| Lotad | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Lombre | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Corphish | 18-21 | Water | route_02_brock_to_misty / lake_viltri_hollow |
| Volbeat | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Illumise | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Noctowl | 21-23 | Normal, Flying | route_03_misty_to_surge / foothill_woods |
| Heracross | 21-23 | Bug, Fighting | route_03_misty_to_surge / foothill_woods |
| Scyther | 21-23 | Bug, Flying | route_03_misty_to_surge / foothill_woods |
| Bunnelby | 21-23 | Normal | route_03_misty_to_surge / foothill_woods |
| Swablu | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Rockruff | 22-25 | Rock | route_03_misty_to_surge / mt_clay |
| Makuhita | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Machop | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Rufflet | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Skiddo | 24-26 | Grass | route_03_misty_to_surge / mt_vessu |
| Meditite | 24-26 | Fighting, Psychic | route_03_misty_to_surge / mt_vessu |
| Drampa | 24-26 | Normal, Dragon | route_03_misty_to_surge / mt_vessu |
| Bergmite | 27-29 | Ice | route_04_surge_to_erika / merian_cirque |
| Smoochum | 27-29 | Ice, Psychic | route_04_surge_to_erika / merian_cirque |
| Cryogonal | 27-29 | Ice | route_04_surge_to_erika / merian_cirque |
| Aron | 28-30 | Steel, Rock | route_04_surge_to_erika / the_crags |
| Nosepass | 28-30 | Rock | route_04_surge_to_erika / the_crags |
| Bronzor | 28-30 | Steel, Psychic | route_04_surge_to_erika / the_crags |
| Vanillite | 29-31 | Ice | route_04_surge_to_erika / upper_trough |
| Snom | 29-31 | Ice, Bug | route_04_surge_to_erika / upper_trough |
| Snorunt | 29-31 | Ice | route_04_surge_to_erika / upper_trough |
| Flaaffy | 30-32 | Electric | route_04_surge_to_erika / peak_pond_hollow |
| Ampharos | 30-32 | Electric | route_04_surge_to_erika / peak_pond_hollow |

**Assessment:** VIABLE: Pidgey, Wingull, Surskit, Combee, Heracross, Scyther, Swablu, Bergmite are common, ungated type answers.

## Gym 5: kanto_koga (Poison)

| Species | First wild levels | Types | First/source corridor |
| --- | --- | --- | --- |
| Pidgey | 5-8 | Normal, Flying | route_01_pallet_to_brock / pallet_meadows |
| Rattata | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Mareep | 5-8 | Electric | route_01_pallet_to_brock / pallet_meadows |
| Wooloo | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Wingull | 7-10 | Water, Flying | route_01_pallet_to_brock / west_shore |
| Krabby | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Staryu | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Shellder | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Wattrel | 7-10 | Electric, Flying | route_01_pallet_to_brock / west_shore |
| Surskit | 9-12 | Bug, Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Buizel | 9-12 | Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Bidoof | 9-12 | Normal | route_01_pallet_to_brock / river_of_shrews_vale |
| Pawmi | 9-12 | Electric | route_01_pallet_to_brock / river_of_shrews_vale |
| Deerling | 9-12 | Normal, Grass | route_01_pallet_to_brock / river_of_shrews_vale |
| Hoothoot | 12-15 | Normal, Flying | route_01_pallet_to_brock / viltri_plateau |
| Combee | 12-15 | Bug, Flying | route_01_pallet_to_brock / viltri_plateau |
| Fomantis | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Gossifleur | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Applin | 12-15 | Grass, Dragon | route_01_pallet_to_brock / viltri_plateau |
| Lotad | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Lombre | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Corphish | 18-21 | Water | route_02_brock_to_misty / lake_viltri_hollow |
| Volbeat | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Illumise | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Noctowl | 21-23 | Normal, Flying | route_03_misty_to_surge / foothill_woods |
| Heracross | 21-23 | Bug, Fighting | route_03_misty_to_surge / foothill_woods |
| Scyther | 21-23 | Bug, Flying | route_03_misty_to_surge / foothill_woods |
| Bunnelby | 21-23 | Normal | route_03_misty_to_surge / foothill_woods |
| Swablu | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Rockruff | 22-25 | Rock | route_03_misty_to_surge / mt_clay |
| Makuhita | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Machop | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Rufflet | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Skiddo | 24-26 | Grass | route_03_misty_to_surge / mt_vessu |
| Meditite | 24-26 | Fighting, Psychic | route_03_misty_to_surge / mt_vessu |
| Drampa | 24-26 | Normal, Dragon | route_03_misty_to_surge / mt_vessu |
| Bergmite | 27-29 | Ice | route_04_surge_to_erika / merian_cirque |
| Smoochum | 27-29 | Ice, Psychic | route_04_surge_to_erika / merian_cirque |
| Cryogonal | 27-29 | Ice | route_04_surge_to_erika / merian_cirque |
| Aron | 28-30 | Steel, Rock | route_04_surge_to_erika / the_crags |
| Nosepass | 28-30 | Rock | route_04_surge_to_erika / the_crags |
| Bronzor | 28-30 | Steel, Psychic | route_04_surge_to_erika / the_crags |
| Vanillite | 29-31 | Ice | route_04_surge_to_erika / upper_trough |
| Snom | 29-31 | Ice, Bug | route_04_surge_to_erika / upper_trough |
| Snorunt | 29-31 | Ice | route_04_surge_to_erika / upper_trough |
| Flaaffy | 30-32 | Electric | route_04_surge_to_erika / peak_pond_hollow |
| Ampharos | 30-32 | Electric | route_04_surge_to_erika / peak_pond_hollow |
| Pichu | 30-32 | Electric | route_05_erika_to_koga / peak_pond_hollow |
| Emolga | 30-32 | Electric, Flying | route_05_erika_to_koga / peak_pond_hollow |
| Teddiursa | 30-32 | Normal | route_05_erika_to_koga / peak_pond_hollow |
| Sentret | 32-34 | Normal | route_05_erika_to_koga / north_east_downs |
| Furret | 32-34 | Normal | route_05_erika_to_koga / north_east_downs |
| Starly | 32-34 | Normal, Flying | route_05_erika_to_koga / north_east_downs |
| Staravia | 32-34 | Normal, Flying | route_05_erika_to_koga / north_east_downs |
| Stunky | 32-34 | Poison, Dark | route_05_erika_to_koga / north_east_downs |
| Nickit | 32-34 | Dark | route_05_erika_to_koga / north_east_downs |
| Wooper | 34-36 | Water, Ground | route_05_erika_to_koga / glacier_foot_fields |
| Lechonk | 34-36 | Normal | route_05_erika_to_koga / glacier_foot_fields |
| Tarountula | 34-36 | Bug | route_05_erika_to_koga / glacier_foot_fields |
| Spidops | 34-36 | Bug | route_05_erika_to_koga / glacier_foot_fields |
| Hatenna | 34-36 | Psychic | route_05_erika_to_koga / glacier_foot_fields |
| Hattrem | 34-36 | Psychic | route_05_erika_to_koga / glacier_foot_fields |
| Toxel | 34-36 | Electric, Poison | route_05_erika_to_koga / glacier_foot_fields |

**Assessment:** VIABLE: Smoochum, Wooper, Hatenna are common, ungated type answers.

## Gym 6: kanto_sabrina (Psychic)

| Species | First wild levels | Types | First/source corridor |
| --- | --- | --- | --- |
| Pidgey | 5-8 | Normal, Flying | route_01_pallet_to_brock / pallet_meadows |
| Rattata | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Mareep | 5-8 | Electric | route_01_pallet_to_brock / pallet_meadows |
| Wooloo | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Wingull | 7-10 | Water, Flying | route_01_pallet_to_brock / west_shore |
| Krabby | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Staryu | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Shellder | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Wattrel | 7-10 | Electric, Flying | route_01_pallet_to_brock / west_shore |
| Surskit | 9-12 | Bug, Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Buizel | 9-12 | Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Bidoof | 9-12 | Normal | route_01_pallet_to_brock / river_of_shrews_vale |
| Pawmi | 9-12 | Electric | route_01_pallet_to_brock / river_of_shrews_vale |
| Deerling | 9-12 | Normal, Grass | route_01_pallet_to_brock / river_of_shrews_vale |
| Hoothoot | 12-15 | Normal, Flying | route_01_pallet_to_brock / viltri_plateau |
| Combee | 12-15 | Bug, Flying | route_01_pallet_to_brock / viltri_plateau |
| Fomantis | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Gossifleur | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Applin | 12-15 | Grass, Dragon | route_01_pallet_to_brock / viltri_plateau |
| Lotad | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Lombre | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Corphish | 18-21 | Water | route_02_brock_to_misty / lake_viltri_hollow |
| Volbeat | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Illumise | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Noctowl | 21-23 | Normal, Flying | route_03_misty_to_surge / foothill_woods |
| Heracross | 21-23 | Bug, Fighting | route_03_misty_to_surge / foothill_woods |
| Scyther | 21-23 | Bug, Flying | route_03_misty_to_surge / foothill_woods |
| Bunnelby | 21-23 | Normal | route_03_misty_to_surge / foothill_woods |
| Swablu | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Rockruff | 22-25 | Rock | route_03_misty_to_surge / mt_clay |
| Makuhita | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Machop | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Rufflet | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Skiddo | 24-26 | Grass | route_03_misty_to_surge / mt_vessu |
| Meditite | 24-26 | Fighting, Psychic | route_03_misty_to_surge / mt_vessu |
| Drampa | 24-26 | Normal, Dragon | route_03_misty_to_surge / mt_vessu |
| Bergmite | 27-29 | Ice | route_04_surge_to_erika / merian_cirque |
| Smoochum | 27-29 | Ice, Psychic | route_04_surge_to_erika / merian_cirque |
| Cryogonal | 27-29 | Ice | route_04_surge_to_erika / merian_cirque |
| Aron | 28-30 | Steel, Rock | route_04_surge_to_erika / the_crags |
| Nosepass | 28-30 | Rock | route_04_surge_to_erika / the_crags |
| Bronzor | 28-30 | Steel, Psychic | route_04_surge_to_erika / the_crags |
| Vanillite | 29-31 | Ice | route_04_surge_to_erika / upper_trough |
| Snom | 29-31 | Ice, Bug | route_04_surge_to_erika / upper_trough |
| Snorunt | 29-31 | Ice | route_04_surge_to_erika / upper_trough |
| Flaaffy | 30-32 | Electric | route_04_surge_to_erika / peak_pond_hollow |
| Ampharos | 30-32 | Electric | route_04_surge_to_erika / peak_pond_hollow |
| Pichu | 30-32 | Electric | route_05_erika_to_koga / peak_pond_hollow |
| Emolga | 30-32 | Electric, Flying | route_05_erika_to_koga / peak_pond_hollow |
| Teddiursa | 30-32 | Normal | route_05_erika_to_koga / peak_pond_hollow |
| Sentret | 32-34 | Normal | route_05_erika_to_koga / north_east_downs |
| Furret | 32-34 | Normal | route_05_erika_to_koga / north_east_downs |
| Starly | 32-34 | Normal, Flying | route_05_erika_to_koga / north_east_downs |
| Staravia | 32-34 | Normal, Flying | route_05_erika_to_koga / north_east_downs |
| Stunky | 32-34 | Poison, Dark | route_05_erika_to_koga / north_east_downs |
| Nickit | 32-34 | Dark | route_05_erika_to_koga / north_east_downs |
| Wooper | 34-36 | Water, Ground | route_05_erika_to_koga / glacier_foot_fields |
| Lechonk | 34-36 | Normal | route_05_erika_to_koga / glacier_foot_fields |
| Tarountula | 34-36 | Bug | route_05_erika_to_koga / glacier_foot_fields |
| Spidops | 34-36 | Bug | route_05_erika_to_koga / glacier_foot_fields |
| Hatenna | 34-36 | Psychic | route_05_erika_to_koga / glacier_foot_fields |
| Hattrem | 34-36 | Psychic | route_05_erika_to_koga / glacier_foot_fields |
| Toxel | 34-36 | Electric, Poison | route_05_erika_to_koga / glacier_foot_fields |
| Poliwag | 37-39 | Water | route_06_koga_to_sabrina / marsh_creek |
| Poliwhirl | 37-39 | Water | route_06_koga_to_sabrina / marsh_creek |
| Tympole | 37-39 | Water | route_06_koga_to_sabrina / marsh_creek |
| Palpitoad | 37-39 | Water, Ground | route_06_koga_to_sabrina / marsh_creek |
| Seismitoad | 37-39 | Water, Ground | route_06_koga_to_sabrina / marsh_creek |
| Barboach | 37-39 | Water, Ground | route_06_koga_to_sabrina / marsh_creek |
| Psyduck | 39-41 | Water | route_06_koga_to_sabrina / tilpey_north_shore |
| Golduck | 39-41 | Water | route_06_koga_to_sabrina / tilpey_north_shore |
| Ducklett | 39-41 | Water, Flying | route_06_koga_to_sabrina / tilpey_north_shore |
| Swanna | 39-41 | Water, Flying | route_06_koga_to_sabrina / tilpey_north_shore |
| Yanma | 39-41 | Bug, Flying | route_06_koga_to_sabrina / tilpey_north_shore |
| Bibarel | 39-41 | Normal, Water | route_06_koga_to_sabrina / tilpey_north_shore |

**Assessment:** VIABLE: Surskit, Combee, Heracross, Scyther, Snom, Stunky, Tarountula, Yanma are common, ungated type answers.

## Gym 7: kanto_blaine (Fire)

| Species | First wild levels | Types | First/source corridor |
| --- | --- | --- | --- |
| Pidgey | 5-8 | Normal, Flying | route_01_pallet_to_brock / pallet_meadows |
| Rattata | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Mareep | 5-8 | Electric | route_01_pallet_to_brock / pallet_meadows |
| Wooloo | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Wingull | 7-10 | Water, Flying | route_01_pallet_to_brock / west_shore |
| Krabby | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Staryu | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Shellder | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Wattrel | 7-10 | Electric, Flying | route_01_pallet_to_brock / west_shore |
| Surskit | 9-12 | Bug, Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Buizel | 9-12 | Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Bidoof | 9-12 | Normal | route_01_pallet_to_brock / river_of_shrews_vale |
| Pawmi | 9-12 | Electric | route_01_pallet_to_brock / river_of_shrews_vale |
| Deerling | 9-12 | Normal, Grass | route_01_pallet_to_brock / river_of_shrews_vale |
| Hoothoot | 12-15 | Normal, Flying | route_01_pallet_to_brock / viltri_plateau |
| Combee | 12-15 | Bug, Flying | route_01_pallet_to_brock / viltri_plateau |
| Fomantis | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Gossifleur | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Applin | 12-15 | Grass, Dragon | route_01_pallet_to_brock / viltri_plateau |
| Lotad | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Lombre | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Corphish | 18-21 | Water | route_02_brock_to_misty / lake_viltri_hollow |
| Volbeat | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Illumise | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Noctowl | 21-23 | Normal, Flying | route_03_misty_to_surge / foothill_woods |
| Heracross | 21-23 | Bug, Fighting | route_03_misty_to_surge / foothill_woods |
| Scyther | 21-23 | Bug, Flying | route_03_misty_to_surge / foothill_woods |
| Bunnelby | 21-23 | Normal | route_03_misty_to_surge / foothill_woods |
| Swablu | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Rockruff | 22-25 | Rock | route_03_misty_to_surge / mt_clay |
| Makuhita | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Machop | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Rufflet | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Skiddo | 24-26 | Grass | route_03_misty_to_surge / mt_vessu |
| Meditite | 24-26 | Fighting, Psychic | route_03_misty_to_surge / mt_vessu |
| Drampa | 24-26 | Normal, Dragon | route_03_misty_to_surge / mt_vessu |
| Bergmite | 27-29 | Ice | route_04_surge_to_erika / merian_cirque |
| Smoochum | 27-29 | Ice, Psychic | route_04_surge_to_erika / merian_cirque |
| Cryogonal | 27-29 | Ice | route_04_surge_to_erika / merian_cirque |
| Aron | 28-30 | Steel, Rock | route_04_surge_to_erika / the_crags |
| Nosepass | 28-30 | Rock | route_04_surge_to_erika / the_crags |
| Bronzor | 28-30 | Steel, Psychic | route_04_surge_to_erika / the_crags |
| Vanillite | 29-31 | Ice | route_04_surge_to_erika / upper_trough |
| Snom | 29-31 | Ice, Bug | route_04_surge_to_erika / upper_trough |
| Snorunt | 29-31 | Ice | route_04_surge_to_erika / upper_trough |
| Flaaffy | 30-32 | Electric | route_04_surge_to_erika / peak_pond_hollow |
| Ampharos | 30-32 | Electric | route_04_surge_to_erika / peak_pond_hollow |
| Pichu | 30-32 | Electric | route_05_erika_to_koga / peak_pond_hollow |
| Emolga | 30-32 | Electric, Flying | route_05_erika_to_koga / peak_pond_hollow |
| Teddiursa | 30-32 | Normal | route_05_erika_to_koga / peak_pond_hollow |
| Sentret | 32-34 | Normal | route_05_erika_to_koga / north_east_downs |
| Furret | 32-34 | Normal | route_05_erika_to_koga / north_east_downs |
| Starly | 32-34 | Normal, Flying | route_05_erika_to_koga / north_east_downs |
| Staravia | 32-34 | Normal, Flying | route_05_erika_to_koga / north_east_downs |
| Stunky | 32-34 | Poison, Dark | route_05_erika_to_koga / north_east_downs |
| Nickit | 32-34 | Dark | route_05_erika_to_koga / north_east_downs |
| Wooper | 34-36 | Water, Ground | route_05_erika_to_koga / glacier_foot_fields |
| Lechonk | 34-36 | Normal | route_05_erika_to_koga / glacier_foot_fields |
| Tarountula | 34-36 | Bug | route_05_erika_to_koga / glacier_foot_fields |
| Spidops | 34-36 | Bug | route_05_erika_to_koga / glacier_foot_fields |
| Hatenna | 34-36 | Psychic | route_05_erika_to_koga / glacier_foot_fields |
| Hattrem | 34-36 | Psychic | route_05_erika_to_koga / glacier_foot_fields |
| Toxel | 34-36 | Electric, Poison | route_05_erika_to_koga / glacier_foot_fields |
| Poliwag | 37-39 | Water | route_06_koga_to_sabrina / marsh_creek |
| Poliwhirl | 37-39 | Water | route_06_koga_to_sabrina / marsh_creek |
| Tympole | 37-39 | Water | route_06_koga_to_sabrina / marsh_creek |
| Palpitoad | 37-39 | Water, Ground | route_06_koga_to_sabrina / marsh_creek |
| Seismitoad | 37-39 | Water, Ground | route_06_koga_to_sabrina / marsh_creek |
| Barboach | 37-39 | Water, Ground | route_06_koga_to_sabrina / marsh_creek |
| Psyduck | 39-41 | Water | route_06_koga_to_sabrina / tilpey_north_shore |
| Golduck | 39-41 | Water | route_06_koga_to_sabrina / tilpey_north_shore |
| Ducklett | 39-41 | Water, Flying | route_06_koga_to_sabrina / tilpey_north_shore |
| Swanna | 39-41 | Water, Flying | route_06_koga_to_sabrina / tilpey_north_shore |
| Yanma | 39-41 | Bug, Flying | route_06_koga_to_sabrina / tilpey_north_shore |
| Bibarel | 39-41 | Normal, Water | route_06_koga_to_sabrina / tilpey_north_shore |
| Seedot | 41-43 | Grass | route_07_sabrina_to_blaine / tilpey_east_shore |
| Nuzleaf | 41-43 | Grass, Dark | route_07_sabrina_to_blaine / tilpey_east_shore |
| Sewaddle | 41-43 | Bug, Grass | route_07_sabrina_to_blaine / tilpey_east_shore |
| Skwovet | 41-43 | Normal | route_07_sabrina_to_blaine / tilpey_east_shore |
| Greedent | 41-43 | Normal | route_07_sabrina_to_blaine / tilpey_east_shore |
| Caterpie | 42-44 | Bug | route_07_sabrina_to_blaine / tilpey_south_shore |
| Metapod | 42-44 | Bug | route_07_sabrina_to_blaine / tilpey_south_shore |
| Butterfree | 42-44 | Bug, Flying | route_07_sabrina_to_blaine / tilpey_south_shore |
| Slugma | 44-46 | Fire | route_07_sabrina_to_blaine / crater_rim_north_west |
| Sizzlipede | 44-46 | Fire, Bug | route_07_sabrina_to_blaine / crater_rim_north_west |
| Centiskorch | 44-46 | Fire, Bug | route_07_sabrina_to_blaine / crater_rim_north_west |
| Heatmor | 44-46 | Fire | route_07_sabrina_to_blaine / crater_rim_north_west |
| Salandit | 44-46 | Poison, Fire | route_07_sabrina_to_blaine / crater_rim_north_west |

**Assessment:** VIABLE: Wingull, Krabby, Staryu, Surskit, Buizel, Lotad, Corphish, Rockruff are common, ungated type answers.

## Gym 8: kanto_giovanni (Ground)

| Species | First wild levels | Types | First/source corridor |
| --- | --- | --- | --- |
| Pidgey | 5-8 | Normal, Flying | route_01_pallet_to_brock / pallet_meadows |
| Rattata | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Mareep | 5-8 | Electric | route_01_pallet_to_brock / pallet_meadows |
| Wooloo | 5-8 | Normal | route_01_pallet_to_brock / pallet_meadows |
| Wingull | 7-10 | Water, Flying | route_01_pallet_to_brock / west_shore |
| Krabby | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Staryu | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Shellder | 7-10 | Water | route_01_pallet_to_brock / west_shore |
| Wattrel | 7-10 | Electric, Flying | route_01_pallet_to_brock / west_shore |
| Surskit | 9-12 | Bug, Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Buizel | 9-12 | Water | route_01_pallet_to_brock / river_of_shrews_vale |
| Bidoof | 9-12 | Normal | route_01_pallet_to_brock / river_of_shrews_vale |
| Pawmi | 9-12 | Electric | route_01_pallet_to_brock / river_of_shrews_vale |
| Deerling | 9-12 | Normal, Grass | route_01_pallet_to_brock / river_of_shrews_vale |
| Hoothoot | 12-15 | Normal, Flying | route_01_pallet_to_brock / viltri_plateau |
| Combee | 12-15 | Bug, Flying | route_01_pallet_to_brock / viltri_plateau |
| Fomantis | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Gossifleur | 12-15 | Grass | route_01_pallet_to_brock / viltri_plateau |
| Applin | 12-15 | Grass, Dragon | route_01_pallet_to_brock / viltri_plateau |
| Lotad | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Lombre | 18-21 | Water, Grass | route_02_brock_to_misty / lake_viltri_hollow |
| Corphish | 18-21 | Water | route_02_brock_to_misty / lake_viltri_hollow |
| Volbeat | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Illumise | 18-21 | Bug | route_02_brock_to_misty / lake_viltri_hollow |
| Noctowl | 21-23 | Normal, Flying | route_03_misty_to_surge / foothill_woods |
| Heracross | 21-23 | Bug, Fighting | route_03_misty_to_surge / foothill_woods |
| Scyther | 21-23 | Bug, Flying | route_03_misty_to_surge / foothill_woods |
| Bunnelby | 21-23 | Normal | route_03_misty_to_surge / foothill_woods |
| Swablu | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Rockruff | 22-25 | Rock | route_03_misty_to_surge / mt_clay |
| Makuhita | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Machop | 22-25 | Fighting | route_03_misty_to_surge / mt_clay |
| Rufflet | 22-25 | Normal, Flying | route_03_misty_to_surge / mt_clay |
| Skiddo | 24-26 | Grass | route_03_misty_to_surge / mt_vessu |
| Meditite | 24-26 | Fighting, Psychic | route_03_misty_to_surge / mt_vessu |
| Drampa | 24-26 | Normal, Dragon | route_03_misty_to_surge / mt_vessu |
| Bergmite | 27-29 | Ice | route_04_surge_to_erika / merian_cirque |
| Smoochum | 27-29 | Ice, Psychic | route_04_surge_to_erika / merian_cirque |
| Cryogonal | 27-29 | Ice | route_04_surge_to_erika / merian_cirque |
| Aron | 28-30 | Steel, Rock | route_04_surge_to_erika / the_crags |
| Nosepass | 28-30 | Rock | route_04_surge_to_erika / the_crags |
| Bronzor | 28-30 | Steel, Psychic | route_04_surge_to_erika / the_crags |
| Vanillite | 29-31 | Ice | route_04_surge_to_erika / upper_trough |
| Snom | 29-31 | Ice, Bug | route_04_surge_to_erika / upper_trough |
| Snorunt | 29-31 | Ice | route_04_surge_to_erika / upper_trough |
| Flaaffy | 30-32 | Electric | route_04_surge_to_erika / peak_pond_hollow |
| Ampharos | 30-32 | Electric | route_04_surge_to_erika / peak_pond_hollow |
| Pichu | 30-32 | Electric | route_05_erika_to_koga / peak_pond_hollow |
| Emolga | 30-32 | Electric, Flying | route_05_erika_to_koga / peak_pond_hollow |
| Teddiursa | 30-32 | Normal | route_05_erika_to_koga / peak_pond_hollow |
| Sentret | 32-34 | Normal | route_05_erika_to_koga / north_east_downs |
| Furret | 32-34 | Normal | route_05_erika_to_koga / north_east_downs |
| Starly | 32-34 | Normal, Flying | route_05_erika_to_koga / north_east_downs |
| Staravia | 32-34 | Normal, Flying | route_05_erika_to_koga / north_east_downs |
| Stunky | 32-34 | Poison, Dark | route_05_erika_to_koga / north_east_downs |
| Nickit | 32-34 | Dark | route_05_erika_to_koga / north_east_downs |
| Wooper | 34-36 | Water, Ground | route_05_erika_to_koga / glacier_foot_fields |
| Lechonk | 34-36 | Normal | route_05_erika_to_koga / glacier_foot_fields |
| Tarountula | 34-36 | Bug | route_05_erika_to_koga / glacier_foot_fields |
| Spidops | 34-36 | Bug | route_05_erika_to_koga / glacier_foot_fields |
| Hatenna | 34-36 | Psychic | route_05_erika_to_koga / glacier_foot_fields |
| Hattrem | 34-36 | Psychic | route_05_erika_to_koga / glacier_foot_fields |
| Toxel | 34-36 | Electric, Poison | route_05_erika_to_koga / glacier_foot_fields |
| Poliwag | 37-39 | Water | route_06_koga_to_sabrina / marsh_creek |
| Poliwhirl | 37-39 | Water | route_06_koga_to_sabrina / marsh_creek |
| Tympole | 37-39 | Water | route_06_koga_to_sabrina / marsh_creek |
| Palpitoad | 37-39 | Water, Ground | route_06_koga_to_sabrina / marsh_creek |
| Seismitoad | 37-39 | Water, Ground | route_06_koga_to_sabrina / marsh_creek |
| Barboach | 37-39 | Water, Ground | route_06_koga_to_sabrina / marsh_creek |
| Psyduck | 39-41 | Water | route_06_koga_to_sabrina / tilpey_north_shore |
| Golduck | 39-41 | Water | route_06_koga_to_sabrina / tilpey_north_shore |
| Ducklett | 39-41 | Water, Flying | route_06_koga_to_sabrina / tilpey_north_shore |
| Swanna | 39-41 | Water, Flying | route_06_koga_to_sabrina / tilpey_north_shore |
| Yanma | 39-41 | Bug, Flying | route_06_koga_to_sabrina / tilpey_north_shore |
| Bibarel | 39-41 | Normal, Water | route_06_koga_to_sabrina / tilpey_north_shore |
| Seedot | 41-43 | Grass | route_07_sabrina_to_blaine / tilpey_east_shore |
| Nuzleaf | 41-43 | Grass, Dark | route_07_sabrina_to_blaine / tilpey_east_shore |
| Sewaddle | 41-43 | Bug, Grass | route_07_sabrina_to_blaine / tilpey_east_shore |
| Skwovet | 41-43 | Normal | route_07_sabrina_to_blaine / tilpey_east_shore |
| Greedent | 41-43 | Normal | route_07_sabrina_to_blaine / tilpey_east_shore |
| Caterpie | 42-44 | Bug | route_07_sabrina_to_blaine / tilpey_south_shore |
| Metapod | 42-44 | Bug | route_07_sabrina_to_blaine / tilpey_south_shore |
| Butterfree | 42-44 | Bug, Flying | route_07_sabrina_to_blaine / tilpey_south_shore |
| Slugma | 44-46 | Fire | route_07_sabrina_to_blaine / crater_rim_north_west |
| Sizzlipede | 44-46 | Fire, Bug | route_07_sabrina_to_blaine / crater_rim_north_west |
| Centiskorch | 44-46 | Fire, Bug | route_07_sabrina_to_blaine / crater_rim_north_west |
| Heatmor | 44-46 | Fire | route_07_sabrina_to_blaine / crater_rim_north_west |
| Salandit | 44-46 | Poison, Fire | route_07_sabrina_to_blaine / crater_rim_north_west |
| Cacnea | 47-49 | Grass | route_08_blaine_to_giovanni / plateau_west |
| Cacturne | 47-49 | Grass, Dark | route_08_blaine_to_giovanni / plateau_west |
| Skorupi | 47-49 | Poison, Bug | route_08_blaine_to_giovanni / plateau_west |
| Drapion | 47-49 | Poison, Dark | route_08_blaine_to_giovanni / plateau_west |
| Nidoran♀ | 49-51 | Poison | route_08_blaine_to_giovanni / rift_foot |
| Nidorina | 49-51 | Poison | route_08_blaine_to_giovanni / rift_foot |
| Nidoran♂ | 49-51 | Poison | route_08_blaine_to_giovanni / rift_foot |
| Kilowattrel | 50-52 | Electric, Flying | route_08_blaine_to_giovanni / south_strand |
| Mareanie | 50-52 | Poison, Water | route_08_blaine_to_giovanni / south_strand |
| Toxapex | 50-52 | Poison, Water | route_08_blaine_to_giovanni / south_strand |

**Assessment:** VIABLE: Wingull, Krabby, Staryu, Surskit, Buizel, Fomantis, Gossifleur, Lotad are common, ungated type answers.

## Answer summary

| Gym | Type | Result |
| ---: | --- | --- |
| 1 | Rock | VIABLE: Wingull, Krabby, Staryu, Surskit, Buizel, Fomantis, Gossifleur are common, ungated type answers. |
| 2 | Water | VIABLE: Mareep, Pawmi, Fomantis, Gossifleur, Lotad are common, ungated type answers. |
| 3 | Electric | VIABLE BUT THIN: Bunnelby is the single dependable Ground family. Keep it common and ungated; the fallback Grass resistances do not replace immunity. |
| 4 | Grass | VIABLE: Pidgey, Wingull, Surskit, Combee, Heracross, Scyther, Swablu, Bergmite are common, ungated type answers. |
| 5 | Poison | VIABLE: Smoochum, Wooper, Hatenna are common, ungated type answers. |
| 6 | Psychic | VIABLE: Surskit, Combee, Heracross, Scyther, Snom, Stunky, Tarountula, Yanma are common, ungated type answers. |
| 7 | Fire | VIABLE: Wingull, Krabby, Staryu, Surskit, Buizel, Lotad, Corphish, Rockruff are common, ungated type answers. |
| 8 | Ground | VIABLE: Wingull, Krabby, Staryu, Surskit, Buizel, Fomantis, Gossifleur, Lotad are common, ungated type answers. |

Gym 1 specifically has Wingull, Krabby, Staryu, Shellder, Surskit, Buizel, Fomantis and Gossifleur on the Pallet-to-Brock corridor. These provide Water and Grass answers without requiring a rare roll, a weather window or an optional dungeon.
