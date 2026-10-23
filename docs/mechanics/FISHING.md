# Fishing: a catch of its own in every area

The owner, 2026-10-16: *"do a sweep on fishing encounters per area, make them feel unique, so i have a reason to fish
everywhere. have it incorporate what you see in the water but have other mons as well. keep cobblemon's shiny and alpha
chances, i like those."*

**Status: authored and generated, compiled, not installed, not seen in game.** Rests on the Cobblemon 1.8.0 jar's
bytecode and stock data (below), not on an experiment. The runtime proof is listed at the end.

Sources of truth: the lists are `data/encounter_design.json` (a table's `fishing` half, `rules.fishing`, and
`marine_fishing` per sea band); `tools/build_encounters.py` expands them into `data/spawns.json` (mechanism
`fishing_coordinate_boxes`); `tools/compile_spawns.py` `build_fishing` compiles them. This document is the why.

## 1. What a cast caught before this

**Nothing, in every authored area (read from code, not observed).** `tools/suppress_inherited_spawns.py --subregions`
(run by `tools/reapply.py`) adds a coordinate anticondition per box to **every** inherited spawn detail, whatever its
`spawnablePositionType`, over every sub-region polygon raster, every route corridor and every sea band. Cobblemon's and
Cobbleverse's own fishing details are inherited details, so inside those boxes they were taken out, and until now
`data/spawns.json` held no fishing entry at all. A Poke Rod there hooked loot and no Pokemon. So the question "replace or
sit beside upstream fishing" was already answered by the suppression: the authored lists **replace** it, over exactly
the cells the suppression empties. ~~Outside them (`retain_defaults`: open ocean outside the sea bands, unauthored caves,
the Nether) the inherited fishing stands as before.~~ **Superseded 2026-10-22 (section 4b): no inherited fishing detail
is live anywhere.** That sentence is what let a Pyukumuku bite off Pallet's west shore.

## 2. The mechanism (verified from the 1.8.0 jar, 2026-10-16)

- `FishingSpawningCondition extends SpawningCondition<FishingSpawnablePosition>`; its `fits` calls `SpawningCondition.fits`
  first (`invokespecial`), which tests `minX/maxX/minY/maxY/minZ/maxZ` against the position, and
  `FishingSpawnablePosition` sets the position to the **bobber's** `BlockPos`. So a box is where the bobber lands.
  Its own fields are `rod`, `rodType`, `bait`, `minLureLevel`, `maxLureLevel` and a `neededNearbyBlocks` (a 10-block
  cube round the bobber, not the world spawner's). None of them is used here.
- Stock fishing is `spawn_pool_world` with `"spawnablePositionType": "fishing"` (`0129_magikarp.json`: `id`, `pokemon`,
  `type`, `spawnablePositionType`, `bucket`, `level`, `weight`, `condition`). Ours has the same keys; the condition is the
  box and `dimensions: ["minecraft:overworld"]` (`bind_dimension`), and **no forced `canSeeSky`**: the bobber's sky flag
  is `world.canSeeSky(pos)`, and a pond under a bridge or a tree should still fish.
- The server's `fishingBuckets` (`server/config/mods/cobblemon/spawning/best-spawner-config.json`): common 83.25,
  uncommon 11.25, rare 4.125, ultra-rare 1.375. Far kinder to the rare end than the world buckets (94 / 5 / 0.5 / 0.2):
  a rare on the rod is about eight times as likely as on foot. **That is the reason to fish**, and the lists use it:
  every area's rare and ultra-rare rows are its signature catches.
- **Shiny and alpha:** nothing is written. No `alpha` property, no shiny field; a fishing detail is a plain species, so
  Cobblemon's own shiny rate and its own alpha chance apply as on any wild spawn.

## 3. The rules every list keeps (`rules.fishing`, failing closed in `generate_fishing`)

1. **Every fishable area has one.** A sub-region table has a `fishing` half or is in `rules.fishing.dry` with the
   measurement that makes it dry; a table with swimmers is never dry. Every sea band of `data/spawns.json`
   `marine_zones` has a `marine_fishing` record.
2. **What you see is on the rod.** Every family that swims in the area (a sub-region's water-half families standing in
   the water; a sea band's roster) is on its list, or is omitted with a reason. The omissions: birds on the water
   (Wingull, Pelipper, Ducklett, Flamigo), a pond skater (Surskit), fireflies (Illumise, Volbeat), and two starters.
3. **And something the water does not show.** At least one family is the rod's alone.
4. **All four buckets filled.** What Cobblemon 1.8.0 does when a cast rolls an empty bucket was not read
   (`docs/research/notes/dungeon-room-mechanisms.md`, bucket warning), so no list leaves one empty.
5. **The area's band.** Families are expanded as the land and water halves are (`expand_family`: the table's band,
   its maturity tier, off-path a step further, no non-level evolution below tier 6 or trade below 7). Sea bands use the
   band's levels and tier; the hand-authored Windward bands take the lowest tier whose cap holds their top.
6. **Roles anchor, common, uncommon, rare, ultra.** No `find` (the reward for leaving the path on foot) and no
   `presence` (above the cap, a heart's only).
7. **No two areas alike.** No two lists name the same set of species, compared on the authored names.
8. **What is not on any rod.** No legendary, mythical, Ultra Beast or paradox. No starter (section 11 of
   `ENCOUNTER_DESIGN.md`: "standing on land, so no starter is any water table's family"): Squirtle, Quaxly, Oshawott,
   Sobble, Piplup and Totodile stay on their banks. No pseudo-legendary that `data/dungeon_prize_roster.json` keeps as a
   dungeon prize, except where it already swims: Dratini at Shrew Lake, Goomy in the Marsh.
9. **Conditions:** only `timeRange` and `isRaining` would be allowed; no list uses one.

## 4. Where it lies

- A **sub-region's** list covers its whole polygon raster (32-block cells), route corridors and the Wooper creek
  included, spawn-free zones cut: the same cells the suppression empties. A fishing detail competes only with
  fishing details, so covering a corridor doubles no world weight.
- A **sea band's** list covers the band's own boxes.
- Files: `spawn_pool_world/fishing/subregions/<sub>.json`, `spawn_pool_world/fishing/marine/<band>.json`, kept apart
  from each place's world roster so the readers of those files (the heart, rare-spawn and design tests) see only the
  world roster.
- **Gap:** measured 2026-10-22 on the canonical heightmap (`python tools/fishing_cover.py measure`): of 60,648,961
  columns of water (sea, painted lakes, river channels) 386,261 (0.64%) had no list and 30,371 had two (a coarse sea-band
  cell that took in a strip of a coast sub-region's raster). Section 4b closes both.
- **Cost:** 25,996 spawn details over 2,345 boxes (64 areas), measured from `compile_spawns.py` 2026-10-22; before the
  cover 20,122 over 1,847. The server holds every detail in memory.

## 4b. Nothing inherited, and every water has exactly one table (the owner, 2026-10-22)

The owner: *"go through the fishing spawns and sure that up, i dont want another moment of my friend getting a mon he
doesnt want in an area."* On 2026-10-21 a friend fishing off Pallet's west shore hooked a Pyukumuku that the guide lists
only for South Strand, Southern Reef and the South-east dunes.

- **What was inherited** (read from the snapshot `cobblers-local/server-snapshot-2026-10-05` with Cobblemon-additions
  4.1.6, and again with the 1.8.2 mod set: the counts are the same): 603 fishing details over 160 species, 599 in 160
  files of `COBBLEVERSE-DP-v31.zip` (`cobblemon:` paths; at the same path they win over the Cobblemon jar's own file, so no jar fishing detail is
  effective) and 4 in one `cobblemon-additions` file. None in a spawn-detail preset.
- **Why Pyukumuku:** `pyukumuku-4` is a fishing detail on `#cobblemon:is_beach` and `#cobblemon:is_ocean`, common bucket,
  weight 2 (x3 and x5 with a lure). 103 columns of sea in a 150 x 200 window off Pallet's west shore (x1000-1150,
  z5300-5500) were in no sub-region raster, no sea band and no suppression box, so that detail was live on the rod
  there. Overall 23,664 of 24,688 stride columns with no authored table were also unsuppressed. Read from data and the
  generators; not cast in game.
- **Fix, one:** `tools/suppress_inherited_spawns.py` drops every inherited detail whose `spawnablePositionType` is
  `fishing` from every inherited file, in every dimension, inside and outside every box (`remove_fishing`); a file left
  empty is re-emitted `"enabled": false`. It fails closed afterwards if any inherited path still carries one
  (`verify_no_fishing`, a raw-text scan). Non-fishing inherited spawns are untouched: `retain_defaults` still keeps them.
- **Fix, two:** `tools/fishing_cover.py plan` writes `data/fishing_fill.json`, and `build_fishing` applies it. Every
  32-block cell of the playable world holds exactly one fishing table, except cells a spawn-free zone touches (nothing
  spawns there). Two tables on a cell: the sea band keeps it if it holds open sea, else the sub-region (946 cells ceded).
  No table on a cell that holds water: the nearest sea band (open sea; 534 of the 596 filled cells) or the nearest
  sub-region with a fishing list (62), by chessboard distance. Dry land far from water is not filled: a pond there
  would catch nothing, not something wrong.
- **Result** (`python tools/fishing_cover.py measure`): water columns with no table 386,261 -> 0, with two 30,371 -> 0.
  `python tools/fishing_audit.py` re-derives it from the compiled details (not from the plan), checks each owning area
  is a section of the guide with the same species, and, given the built suppression pack, that nothing inherited is live.
- **Not covered:** water the heightmap and `landmarks.json` do not hold (a pool a town builds) in a cell no table
  reaches: it catches nothing. A dungeon's own fishing pools. What the game does with any of this; not cast.

## 5. Per region: what you fish and why

`*` uncommon, `**` rare, `***` ultra-rare; plain is common. Stages are what the band spawns (Magikarp shows as Gyarados
from tier 3 up, and so on). "Seen" is the area's own swimmers; "rod only" is what fishing alone gives there.

| Region | Area (tier) | Seen in the water | Rod only: the reason to cast here |
| --- | --- | --- | --- |
| Pallet Fields | Pallet Meadows (1) | none of its own | Magikarp, Poliwag; Goldeen*, Azurill*; Psyduck**; **Wooper\*\*\*** |
|  | West Shore (1) | Shellder, Staryu, Wiglett, Tentacool, Finizen, Luvdisc, Alomomola | Krabby; **Corsola\*\*** |
|  | South-West Fields (1) | none | Goldeen, Magikarp; Barboach*, Marill*; Buizel**; **Corphish\*\*\*** |
|  | Route 1 maze forest (1) | none | Poliwag, Magikarp; Lotad*, Dewpider*; Slowpoke**; **Basculin\*\*\*** |
| Shrew Lakes | River of Shrews vale (1) | Goldeen, Marill, Dewpider, Slowpoke, Buizel, Wimpod | Magikarp; Barboach**; **Chewtle\*\*\*** |
|  | Shrew Lake shores (2) | Psyduck, Marill, Bidoof, Cramorant, Dratini, Frillish | Magikarp; Wooper*; **Dratini at rare** (a find on foot) |
|  | Arrow Lake shores (3) | Arrokuda, Chewtle, Chinchou, Kabuto, Relicanth, Tirtouga | Magikarp; **Omanyte\*\*** (the fossil lake's missing fossil) |
| Viltri Woods | Lake Viltri hollow (2) | Magikarp, Lotad, Corphish, Wooper, Remoraid, Chinchou, Clamperl, Qwilfish | Goldeen*, Psyduck* |
|  | Viltri's Path valley (2) | none | Poliwag, Goldeen; Buizel*, Lotad*; Basculin**; **Feebas\*\*\*** |
|  | Foothill woods (3) | Poliwag, Feebas | Barboach, Bidoof*, Basculin*; Goldeen**; **Dewpider/Araquanid\*\*\*** |
|  | North-west coast (3) | Horsea, Finneon, Skrelp, Wailmer, Mantyke | Tentacool, Krabby*; **Inkay\*\*** |
| Glacial Tear | The Crags (4) | Barboach, Carvanha | Basculin*, Marill*; Goldeen**; **Feebas\*\*\*** in the tarn |
|  | Upper Trough (4) | none | Goldeen, Bidoof; Basculin*, Marill*; Barboach**; **Shuckle\*\*\*** clamped to a hooked stone |
|  | Lower Trough (5) | Goldeen (Piplup on the bank) | Basculin, Bidoof*, Marill*; Barboach**, Azurill**; **Feebas\*\*\*** |
| Tri Peaks | The Tri Peaks (3) | none | Goldeen, Basculin; Shellder*, Bidoof*; Seel**; **Hisuian Qwilfish\*\*\*** |
| Northern Downs | Peak Pond hollow (4) | Basculin, Buizel, Krabby, Remoraid, Clobbopus, Tynamo | Magikarp, Poliwag* |
|  | North shore downs (4) | none | Poliwag, Goldeen; Psyduck*, Krabby*; Shellos**, Wooper**; **Relicanth\*\*\*** |
|  | North-east downs (4) | none | Bidoof, Basculin; Barboach*, Marill*; Goldeen**, Lotad**; **Chewtle/Drednaw\*\*\*** |
| Marsh Country | Marshy Marsh (5) | Tympole (Totodile on the bank) | Wooper, Barboach; Lotad*, Grimer*; Stunfisk**, Poliwag**; **Goomy\*\*\*** |
|  | Marsh creek (6) | Poliwag, Wooper, Grimer, Goomy, Tynamo, Stunfisk | Magikarp, Tympole*; **Dewpider\*\*** |
|  | Eastern moor (7) | none | Poliwag line, Goldeen; Barboach*, Krabby*; Wishiwashi**, Skrelp**; **Dhelmise\*\*\*** |
| Frostpeak Point | Frostpeak (5) | none | Spheal, Shellder, Basculin; Bergmite*, Seel*; Hisuian Qwilfish**; **Eiscue\*\*\*** |
|  | Frostpeak strand (5) | Seel, Lapras, Spheal | Shellder; Bergmite*, Hisuian Qwilfish*; Eiscue**; **Lapras at ultra** (a find on foot) |
| Tilpey Lakeland | Tilpey north shore (6) | (Ducklett, Flamigo: birds) | Goldeen, Psyduck; Buizel*, Basculin*; Lotad**, Marill**; **Vaporeon\*\*\*** |
|  | Tilpey east shore (6) | Lotad, Wattrel | Magikarp; Arrokuda*, Finneon*, Krabby*; Wishiwashi**; **Bruxish\*\*\*** |
|  | Tilpey west meadows (6) | Inkay (Surskit on the surface) | Goldeen; Poliwag*, Marill*; Chewtle**; **Tatsugiri\*\*\*** |
|  | Tilpey waters (7) | Magikarp, Veluza, Psyduck, Kabuto, Clobbopus, Feebas | Goldeen, Barboach*; **Arrokuda\*\***; Milotic on the ultra row |
|  | Tilpey south shore (7) | Corphish (Sobble on the bank) | Poliwag line; Basculin*, Lotad*; Wooper**; **Wimpod/Golisopod\*\*\*** |
| Northgate Isle | Northgate west (6) | none | Krabby, Shellder; Finneon*, Remoraid*; Inkay**; **Relicanth\*\*\*** |
|  | Northgate east (6) | none | Shellder, Krabby, Tentacool; Horsea*, Qwilfish*; Binacle**; **Skrelp\*\*\*** |
| Pine Isles | North pine isle (6) | none | Shellder, Krabby, Seel; Binacle*, Bergmite*; Inkay**, Hisuian Qwilfish**; **Eiscue\*\*\*** |
|  | South pine isle (6) | none | Spheal, Basculin; Clauncher*, Bidoof*; Seel**, Arrokuda**; **Lapras\*\*\*** |
| Fungal Isle | Fungal north (3) | none | Slowpoke, Poliwag; Wooper*, Barboach*; Shellos**; **Tadbulb\*\*\*** strayed from the south |
|  | Fungal south (3) | Tadbulb, Dewpider | Slowpoke, Magikarp; Wooper*, Poliwag*; Shellos**; **Mareanie\*\*\*** |
| Sunset Isle | Sunset west (5) | none | Barboach, Corphish; Chewtle*, Krabby*; Wishiwashi**; **Paldean Wooper/Clodsire\*\*\*** |
|  | Sunset east (8) | none | Goldeen, Staryu; Poliwag*, Finizen*; Luvdisc**, Inkay**; **Lapras\*\*\*** |
| Jungle Isle (the Sound, drowned) | Jungle west (8) | none | Tentacool, Corsola, Luvdisc; Mareanie*, Pyukumuku*; Bruxish**, Clauncher**; **Mantyke\*\*\*** |
|  | Jungle east (8) | none | Wishiwashi, Finizen, Staryu; Pincurchin*, Clobbopus*; Mareanie**; **Skrelp/Dragalge\*\*\*** |
| Long Isle | Long Isle north (7) | none | Krabby, Wiglett; Staryu*, Binacle*; Clauncher**; **Corsola\*\*\*** |
|  | Long Isle middle (7) | none | Barboach, Krabby, Chewtle; Corphish*; Stunfisk**; **Lapras\*\*\*** |
|  | Long Isle south (8) | Dewpider, Wimpod | Carvanha, Magikarp; Corphish*, Lotad*; Chewtle**; **Tatsugiri\*\*\*** |
| Southern Coast | Arrow creeks (8) | Tatsugiri, Omastar, Seadra, Jellicent, Dondozo, Dracovish, Carracosta | Barboach, Chewtle*; **Dondozo at rare** (a find on foot) |
|  | South strand (8) | Clauncher, Mareanie, Tentacool, Staryu, Shellder, Wishiwashi, Bruxish | Krabby; Pyukumuku*; **Corsola\*\*** |
|  | Rift foot (8) | none | Barboach, Corphish, Carvanha; Chewtle*, Stunfisk*, Krabby*; Clauncher**; **Paldean Wooper/Clodsire\*\*\*** |
| Eastern Dunes | East coast dunes (7) | none | Krabby, Wiglett, Staryu; Finizen*; Pincurchin**; **Relicanth\*\*\*** |
|  | South-east dunes (8) | none | Tentacool, Krabby, Wiglett; Clauncher*, Skrelp*; Binacle**; **Pyukumuku\*\*\*** |

The seas (19 bands): each band's rod is its own roster plus one or two catches the band does not show.

| Sea | Bands: rod only |
| --- | --- |
| Windward Sea (16-30) | shallows: Magikarp, Shellder*, **Corsola\*\*\***; open: Inkay*; deep: Clamperl*, Skrelp** |
| Outer Deep (45-55) | Carvanha/Sharpedo; **Horsea: Seadra and Kingdra\*\*\*** |
| Frostwater Shelf (26-40) | shallows: Bergmite*; open: Magikarp (Gyarados*); deep: Bergmite/Avalugg* |
| Pine Strait (36-50) | shallows: Remoraid*, **Relicanth\*\*\***; open: Skrelp*, **Kabuto/Kabutops\*\*\***; deep: Relicanth**, **Omanyte/Omastar\*\*\*** |
| Eastern Reach (41-55) | shallows: Finizen*, **Bruxish\*\*\***; open: Tentacool*, **Lapras\*\*\***; deep: Wailmer, **Relicanth\*\*\*** |
| Southern Shallows (46-60) | reef: Clobbopus*, **Alomomola\*\*\***; open: Wishiwashi, **Lapras\*\*\***; deep: **Dhelmise\*\*\*** |
| Sunset Sea (21-35) | shallows: Magikarp, **Corsola\*\*\***; open: Tentacool, **Lapras\*\*\***; deep: Wailmer, **Relicanth\*\*\*** |

**Dry (17, `rules.fishing.dry`):** Merian Cirque, Mt Vessu, Mt Clay, the four Rift tables, the three Crater tables,
the three Plateau tables, both Wedge tables, Glacier-foot fields and Viltri Plateau. Measured on the canonical
heightmap: no column below sea level y62, no coast boundary, no `data/rivers.json` lake extent or course station inside,
and no water half. Water the heightmap does not hold (a painted pond, a pool in the Rift sculpt) is not measured; such
water there catches nothing (its inherited fishing is suppressed too).

## 6. Not verified, and the experiment that would

Nothing here has been cast in game. The proof, on staging, with a Poke Rod and no bait:

1. Cast 50 times in three areas (a lake: Lake Viltri; a coast: West Shore; a sea band: the Windward shallows), record
   every catch with `/checkspawn` or the hooked species: only the area's list should come up.
2. Cast at the Pallet west shore gap (x1024-1087, z5312-5375, bobber on the water): since 2026-10-22 the nearest band's
   list (Sunset Sea shallows) should come up and no Pyukumuku. Cast in open ocean past every band: the nearest band's list.
3. Cast in a dry area's puddle: nothing, as now.
4. Read whether an empty bucket retries or skips (rule 4 assumes the worst).

Format uncertainty worked around: none of the fishing-only fields (`rod`, `bait`, lure levels) is used, and no
condition beyond the box and the dimension is written.
