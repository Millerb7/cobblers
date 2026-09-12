# Reusable structure catalog

This catalog records useful structure families available in the Cobblemon 1.8
server plan. IDs and dimensions come from shipped registry JSON or parsed NBT;
`UNKNOWN` means no cheap proof was available. Most upstream assets remain in
their original jars/datapacks; explicitly licensed donor copies are recorded in
`kits/structures/manifests/pokemon-town-donors.json`. Machine-readable runtime
provenance is in `kits/structures/manifests/structure-dependencies.json`.

## Inventory summary

- 15 relevant provider/injection families inspected; 22 representative assets
  promoted into the verified catalog.
- Pokémon Centers: 19 Cobblemon/PokeCenterPCs village variants plus larger BCA
  Center pieces.
- Poké Marts: one dedicated BCA template plus store/market pool pieces.
- Gyms: 32 named Cobbleverse gym structures across Kanto, Hoenn, Johto and Sinnoh;
  these are references rather than campaign defaults.
- Villages: 9 BCA generators, 248 BCA templates, themed pools and road pieces;
  Cobblemon and several mods also inject pieces into vanilla/Repurposed villages.
- Ancient/legendary: 13 Legendary Monuments registered families, regional
  legendary sites, LumyMon's two large templates, and Cobblemon habitats/ruins.
- Towers and facilities: Rocket/Galactic towers and HQ, dawn/dusk/bell/burned
  towers, leagues, academy, department store, observatory and archaeological site.
- No standalone trade-tower ID was found. External CobblemonCityTowns 1.0 adds a
  verified Pallet Town Oak's Lab donor.

## Pokémon infrastructure

| Catalog ID | Name | Source and structure ID | Implementation | Dimensions | Placement / transforms | Editable | Recommended use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CBM-CENTER-PLAINS-01 | Plains village PokéCenter | PokeCenterPCs datapack for Cobblemon · `cobblemon:village_plains/village_plains_pokecenter` | NBT with 2 jigsaws | 10×11×14 | `/place template`: PASS; rotation+mirror accepted | WITH CARE | Tier 1 rural Center; preserve PC/healer and jigsaws |
| BCA-CENTER-01 | BCA standalone PokéCenter | Cobblemon Additions · `bca:default/one_off/pokecenter` | NBT, 15 jigsaws | 22×15×23 | command-placeable; transform untested | WITH CARE | Tier 2 regional Center; includes PC, 2 healers, 2 Waystones |
| BCA-MART-01 | BCA Poké Mart | Cobblemon Additions · `bca:default/one_off/structure_pokemart` | NBT | UNKNOWN | `/place template` with 90° rotation: PASS | WITH CARE | Tier 1/2 town Mart; shop behavior untested |
| BCA-BATTLEPAD-01 | Small battle pad | Cobblemon Additions · `bca:default/one_off/small_battlepad` | NBT | UNKNOWN | placement+rotation+mirror: PASS | YES | Reusable outdoor trainer or gym-arena shell |

## Settlements

| Catalog ID | Name | Source and structure ID | Implementation | Dimensions | Placement | Editable | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BCA-VILLAGE-DEFAULT-S | Default small village | Cobblemon Additions · `bca:village/default_small` | size-2 jigsaw | procedural | `/place structure`: PASS after 15×15 chunks loaded | component edits only | Missing `bca:paths`, `store_workers`, and `feature/decor` pool warnings make composition PARTIAL |
| BCA-VILLAGE-FIGHTING-S | Fighting small village | Cobblemon Additions · `bca:village/fighting_small` | size-4 jigsaw | procedural | `/place structure`: PASS after 15×15 chunks loaded | component edits only | Two centers plus themed paths/houses/markets; use as vocabulary, not a final town |
| BCA-ACADEMY-01 | The Academy | Cobblemon Additions · `bca:default/centers/center_the_academy` | NBT, 10 jigsaws, 38 entities | 49×60×73 | manual placement not run | WITH CARE | Large civic/school reference; 185 signs and 285 chiseled bookshelves |
| BCA-DEPARTMENT-STORE-01 | Department store | Cobblemon Additions · `bca:default/centers/center_department_store` | NBT | UNKNOWN | manual placement not run | WITH CARE | Medium/major city commercial anchor |
| CBL-F4-PALLET-HOUSE-01 | Pallet family house `large2` | CobblemonCityTowns 1.0 donor · copied as `cobblers:f4/pallet_house_large2` | MIT donor NBT; vanilla blocks; 3 jigsaws | 12×9×10 | placed on Relic Island; server/restart verified | YES, retain attribution | Relic Island house; placement resolves jigsaws and replaces loot |
| CCT-PALLET-KIT-01 | Five Pallet houses and town sign | CobblemonCityTowns 1.0 · copied under `cobblers:f4/pallet/` | MIT donor NBT; vanilla blocks | 9–13 wide, 8–11 tall | all mainland placements server/restart verified | YES, retain attribution | Core EXP-001 Pallet settlement vocabulary |
| CCT-PALLET-LAB-01 | Professor Oak's Lab | CobblemonCityTowns 1.0 · copied as `cobblers:f4/pallet/rare_structures/lab` | donor NBT; vanilla + Cobblemon; 5 jigsaws/5 entities | 19×20×20 | server/restart verified | YES, retain attribution | Canonical mainland Pallet laboratory |
| CCT-SERVICE-01 | Pokémon Center and Poké Mart | CobblemonCityTowns 1.0 · copied under `cobblers:f4/services/` | donor NBT; complete-overlay service blocks | 22×15×23 and 23×12×22 | both server/restart verified | YES, retain attribution | Keeps Pallet close to the Cobbleverse service loop |

### Pallet reference

CobblemonCityTowns 1.0 is the primary external donor. Its MIT-licensed Minecraft
1.21.1 archive contains five Pallet houses, a 19×20×20 Oak's Lab, roads, fences,
lamps, trees, flowers, a pool, and a town sign. EXP-001 copies the five houses,
lab, sign, Pokémon Center and Poké Mart into the campaign namespace. The
standalone `large2` copy remains the Relic Island house. The donor's structure
sets and natural worldgen files are not enabled.

The local Cobbleverse datapack also contains `cobbleverse:ash` (43×22×44),
including the Pallet Ash/Delia NPC setup, a PC, RCT spawners, furniture, and
berries. Use it only as an in-game visual reference for F4. The datapack is
nonredistributable, and extracting it would bake unrelated behavior into the
event.

Cobblemon Additions contains 248 BCA NBT pieces, 33 pools, and nine village
generators. Its route kit includes straight, curved, T-junction, and cross-road
pieces. Theme pools exist for electric, fire, flying, grass, ground, ice, and water.

## Gyms and leagues

| Catalog ID | Name | Source and ID | Implementation | Placement / transforms | Embedded behavior | Recommended use |
| --- | --- | --- | --- | --- | --- | --- |
| CBV-GYM-BROCK | Brock Gym | core Cobbleverse · `cobbleverse:brock` | NBT + jigsaw/worldgen registration | `/place template` with 180° rotation: PASS | RCT trainer-spawner blocks present; behavior untested | REFERENCE ONLY; palette and compatibility fixture |
| CBV-LEAGUE-KANTO | Kanto League | core Cobbleverse · `cobbleverse:kanto_league` | NBT + jigsaw | UNKNOWN | RCT trainer spawners and association | REFERENCE ONLY; campaign League remains custom |

The core and regional packs contain 8 named gyms per region plus league assets.
They prove reusable technology and palette choices, but copying their authored
encounters would conflict with this campaign and their redistribution terms.

## Towers and industrial landmarks

| Catalog ID | Name | Source and ID | Technology | Recommended use |
| --- | --- | --- | --- | --- |
| CBV-ROCKET-TOWER | Team Rocket tower | core Cobbleverse · `cobbleverse:team_rocket_tower` | NBT + jigsaw | REFERENCE ONLY for villain architecture |
| CBV-DAWN-TOWER | Dawn Tower | core Cobbleverse · `cobbleverse:dawn_tower` | NBT + jigsaw | REFERENCE ONLY |
| CBV-HOENN-SKY-PILLAR | Sky Pillar | optional Hoenn pack · `cobbleverse:sky_pillar` | NBT + jigsaw | REFERENCE ONLY; optional non-redistributable source |
| CBV-JOHTO-BELL-TOWER | Bell Tower | optional Johto pack · `cobbleverse:bell_tower` | NBT + jigsaw | REFERENCE ONLY; optional non-redistributable source |
| CBV-SINNOH-GALACTIC-HQ | Team Galactic HQ | optional Sinnoh pack · `cobbleverse:team_galactic_hq` | NBT + jigsaw | REFERENCE ONLY for villain/lab vocabulary |
| MSD-MEGA-SITE | Mega Site | Mega Showdown · `mega_showdown:mega_site` | NBT + jigsaw with processor | Test before use | Processor substitutes meteorid ores; depends on the exact 1.8 overlay build |

No standalone trade-tower structure ID was found. The external donor manifest
records CobblemonCityTowns' Oak's Lab for future Pallet work. Department stores,
academies, Rocket/Galactic towers, and Mega Showdown's observatory and
archaeological site remain useful facility references.

## Ancient, legendary, and natural

| Catalog ID | Name | Source and ID | Implementation | Dimensions | Placement | Recommended use |
| --- | --- | --- | --- | --- | --- | --- |
| LM-FIRESCOURGE-SHRINE | Firescourge Shrine | Legendary Monuments · `legendarymonuments:firescourge_shrine` | raw NBT + mod-registered terrain validation | 21×15×27 | raw template+rotation+mirror: PASS; `/place structure` terrain validation failed on flat world | REFERENCE ONLY pending license/function review |
| LM-TURNBACK-CAVE | Turnback Cave | Legendary Monuments · `legendarymonuments:turnback_cave` | multi-pool jigsaw with processors | procedural | UNKNOWN | REFERENCE ONLY; substantial puzzle-layout vocabulary |
| LUMY-TEMPLE-SINNOH | Temple of Sinnoh | LumyMon · `lumymon:temple_of_sinnoh` | NBT | 35×38×103 | structure-block/template placement available; untested | REFERENCE ONLY; contains pedestals, statues and 2 RCT spawners |
| CBM-HABITAT-METEORITE | Meteorite impact | Cobblemon · `cobblemon:habitats/meteorite_impact` | jigsaw/worldgen | procedural | UNKNOWN | Candidate route landmark after functional test |
| CBM-HABITAT-ZEN-GARDEN | Zen garden | Cobblemon · `cobblemon:habitats/zen_garden` | jigsaw/worldgen | procedural | UNKNOWN | Candidate shrine/rest landmark |
| CBM-RUIN-GIMMI-TOWER | Deserted Gimmi tower | Cobblemon · `cobblemon:ruins/deserted_gimmi_tower` | jigsaw/worldgen | procedural | UNKNOWN | Candidate optional ruin/reference |

Cobblemon 1.8 also ships 32 habitat, 29 ruin, 3 fishing-boat, and 3 shipwreck-cove
structure definitions. Legendary Monuments ships 13 registered families and 146
templates. Repurposed Structures (107 structures, 1,099 pools, 3,162 templates)
and Terralith (28 structures, 49 pools, 173 templates) are broad worldgen
libraries; catalog their pieces only when a campaign location needs one.

## Evidence limits

The headless test proves command resolution, placement completion, save, and
server restart. It does not prove visual completeness, entity orientation,
jigsaw seam quality, NPC behavior, PCs, loot, or multiplayer synchronization.
Those columns remain `UNKNOWN` or `PARTIAL` until a client inspection.
