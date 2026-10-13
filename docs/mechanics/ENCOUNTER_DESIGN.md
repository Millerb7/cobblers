# Encounter design: escalation, distinct waters, rewards off the path (2026-10-02)

**Status: the design the encounter tables are rebuilt against.** It answers the owner's playtest of 2026-10-02:

> I should meet EVOLVED and interesting Pokemon as I get further in. By Victory Road the roster should feel like the
> end of a journey, not the middle. Lakes should differ from each other. Rare and remarkable things should be
> findable off the path. Keep the places legible -- a marsh reads as a marsh -- but a late marsh is not an early marsh.

What was wrong is measured in `docs/research/ENCOUNTER_AUDIT.md`. This document says what decides every table, so a
later session can add or change one without guessing. The tables themselves are authored in
`data/encounter_design.json`; `tools/build_encounters.py` expands them into `data/spawns.json`, which
`tools/compile_spawns.py` compiles as before. **`data/spawns.json`'s sub-region rosters, Victory Road's habitat
pools and `route_species_selection` are generated from now on: change the design file, never those sections.**

Section 8 lists the targets a test checks. They are written here before the tables were built, and they are the
independent side: the tests measure the compiled pack against these numbers, never against the generator.

## 1. The unit is a table, and every table has a tier

A table is one sub-region's roster (`data/regions.json` sub-regions, 63) or one Victory Road habitat pool (11). Its
**tier** is the leg on which a player first meets it: tier N means "on the way to gym N", tier 9 is Victory Road and
the Rift. The level cap a player carries on leg N is gym N's ace (20, 25, ... 55; 60 at Victory Road, the first Elite
Four ace, with `relativeLevelCap` 0), and since 2026-09-28 a wild Pokemon over the cap breaks free of any ball.

- **On or near the path** (a route's corridor, or a sub-region within 128 blocks of one; `tools/availability.py`):
  the tier is the leg `availability.py` places it on. A sub-region the corridor covers whole takes the route's leg.
- **Off the path** (over 128 blocks from every route): the tier is the leg of the nearest route, raised where a
  real barrier stands between the path and the place, and the reason is written on the table (`tier_why`).
  Islands are raised to the leg by which a player plausibly crosses the sea; the Rift is tier 9 because it is
  Victory Road's country and its levels are Victory Road's. A tier is never below the nearest route's leg.
  `availability.py` does not walk Victory Road, so all four Rift tables are off the path by this rule, and
  that is deliberate: the Rift floor beside Victory Road's tunnels is ground to explore, and each has a find.

## 2. Levels come from the tier, and stay catchable

| Tier | Cap | Band | | Tier | Cap | Band |
|---|---|---|---|---|---|---|
| 1 | 20 | 4-14 | | 6 | 45 | 33-43 |
| 2 | 25 | 13-22 | | 7 | 50 | 38-48 |
| 3 | 30 | 18-28 | | 8 | 55 | 43-53 |
| 4 | 35 | 23-33 | | 9 | 60 | 52-60 |
| 5 | 40 | 28-38 | | | | |

The top of every band is at or under its cap, so everything a player meets on a leg can be caught on that leg
(the old placeholder band of 25-45 on fifteen off-path places is gone). Bands overlap their neighbours by about five
levels so a leg's end meets the next leg's start.

**The owner, 2026-10-02 (after the rebuild): uncatchable spawns inside a band are welcome.** "It adds to revisiting
and makes a region feel more like it should." So the catchable ceiling above is the rule for the *base* of a band,
not a ceiling on everything in it: the heart of a place (a summit, a lake's centre, a crater bowl) may hold
Pokemon above the leg's cap, met first as a sight and caught on a return. Section 10 builds that; target 5 still
checks the uniform bands, and fails on the hearts until a test author rewrites it per heart. A table may narrow its band (`levels`) inside its tier's band --
Pallet's meadows are 4-8 -- but never leave it.

## 3. Escalation: a family's weight moves to its evolved stages as the tier rises

A table lists **families** by the species a player first meets there, never by stage. The generator walks the jar's
evolutions forward from that species and gives each stage a level range and a share of the family's weight:

- **Level ranges.** A stage spawns from the level it evolves at (or the band's floor) to four levels past the level
  at which it would evolve again (or the band's top). A stage whose range is empty is not spawned: Victory Road
  never shows a Zubat, and a level-44 marsh has no Wooper.
- **Maturity.** Of a family's weight, the share on its evolved stages is `maturity[tier]`: 0, 0.1, 0.2, 0.3, 0.4,
  0.5, 0.6, 0.7 for tiers 1-8 and 0.85 at tier 9. Among two evolved stages the final one's share of that is
  `(tier - 3) / 6`, held between 0.2 and 0.9. If only one stage survives its range, it takes the whole weight.
- **Evolutions not by level** (a stone, trade, friendship, a held item, a move) appear in the wild only from **tier 6
  (tier 7 for a trade)**, in the upper half of the band. This is the mainline shape -- a late cave holds Crobat and
  Golem -- and here it has a second reason: the world has almost no evolution stones (`docs/STATE.md`), so a late
  wild Vileplume or Ludicolo is the only way some players will ever have one.
- **Naming an evolved species starts the family there**: Victory Road lists `noivern`, not `noibat`; a zone prize
  lists `milotic`, not `feebas`.

## 4. Roles, buckets and how much a table holds

| Role | Bucket | Family weight | Use |
|---|---|---|---|
| anchor | common | 24 | the one or two families that define the place |
| common | common | 12 | the rest of what a player sees every few steps |
| uncommon | uncommon | 6 | the second look |
| rare | rare | 2 | worth a detour on the path |
| find | rare | 2 | **off-path only**: the reason to leave the path (section 6) |

A family's stages share its weight and its bucket. A table holds 3-6 land families and, where it has water, 2-4 water
families. The bucket weights decide how often a bucket is drawn. **The server runs the v2 file** (`version: 2`,
`C:/Users/wnd/Documents/github/cobblers-server/config/cobblemon/spawning/best-spawner-config.json`, read 2026-10-12):
world buckets **common 94, uncommon 5, rare 0.5, ultra-rare 0.2, boss 0.3**; fishing, snacks and activated Habitat Blocks
83.25 / 11.25 / 4.125 / 1.375 (common / uncommon / rare / ultra-rare). So a find (rare bucket) is about one land spawn
in two hundred (0.5 of 100 where every bucket has a candidate), findable by someone who looks, not by someone passing
through. *Corrected 2026-10-12: this section quoted 88.5 / 10 / 1.2 / 0.3, the base pack's v1 file
(`base-pack/cobbleverse/config/cobblemon/spawning/best-spawner-config.json`), which the server does not run; the
"one in eighty" followed from it.*

## 5. Waters: every lake and coast has its own fish

The audit found one water template pasted into eleven lakes. Each body of water now has its own families, chosen
from what lives in that kind of water and at that tier:

| Water | Tier | Families (the water half of the table) |
|---|---|---|
| River of Shrews | 1 | Goldeen, Marill, Surskit |
| Lake Viltri | 2 | Magikarp, Lotad, Corphish, Chinchou (deep, rare) |
| Shrew Lake | 2 | Psyduck; Dratini (rare) |
| Arrow Lake | 3 | Arrokuda, Chewtle; Relicanth (find) |
| Foothill pond | 3 | Poliwag; Feebas (rare) |
| North-west coast | 3 | Horsea, Tentacool; Skrelp (find) |
| The Crags tarn | 4 | Barboach, Carvanha |
| Peak Pond | 4 | Basculin, Buizel |
| Lower Trough | 5 | Spheal, Piplup |
| Marshy Marsh | 5 | Totodile, Tympole |
| Frostpeak strand | 5 | Seel; Lapras (find) |
| Marsh creek | 6 | Poliwag (now Poliwhirl and Poliwrath), Chewtle (now Drednaw) |
| Lake Tilpey's shores | 6-7 | Ducklett (north), Lotad (east), Surskit (west), Shellos (south) |
| Lake Tilpey's open water | 7 | Magikarp (only Gyarados at this tier), Veluza, Psyduck (now Golduck) |
| Arrow creeks | 8 | Tatsugiri; Dondozo (find) |
| South strand | 8 | Clauncher, Mareanie |

Rules a later session keeps: **a water family appears in at most two water tables, and when it does the later one
shows a different stage** (Goldeen at the River of Shrews, nothing else; Magikarp at Lake Viltri, Gyarados at
Tilpey). Two different bodies of water share at most 35% of their water spawns. The shores of one lake (Tilpey's
four) may share more, but each still has its own shallows family.

**Lake Tilpey's bank, night and rain (the owner, 2026-10-09: "more spawns, VARIED across species. It is the biggest
lake and it should feel like it").** Measured on the canonical heightmap: the basin holds 1,116,133 water columns (the
next lake, Shrew Lake, 176,416), mean depth 17.2, 235,136 columns 1-2 deep and 640,931 over 20 deep. Ten species were
added in five tables, every one native in the Cobblemon 1.8.0 jar to fresh water, a river or a forest, and none in a
second water table: the lake's WATER half was already as full as section 5's rules allow (every freshwater family left
is in two water tables, or would show no new stage in its second), so the additions stand on the bank
(`neededNearbyBlocks` water, grounded: a land context, outside the two-table rule, the way section 11 seats the water
starters) or fly over the water. Open water and isles (`tilpey_waters`): Illumise and Volbeat on the surface at night
(jar: is_freshwater, night), Cramorant on the rocks and Politoed in rain (is_freshwater, raining). North shore:
Drednaw, Poliwrath in rain, Vivillon. East shore: Bellibolt (is_freshwater). South shore: Floatzel (is_freshwater).
West meadows: Simipour (is_river, where the creek comes in). The deep has no new species: the water natives of a deep
freshwater lake in the jar are the ones already seated (Gyarados, Basculegion, Kabutops, Clobbopus) or are in two water
tables. Considered and left out for a stated reason: Dragonair (the jar has it in oceans and below y32, not on a
lake), Clamperl and its line (deep ocean), Wooper and its line (swamp), Overqwil (cold ocean), Marill and Vaporeon
(starter-family species).

### 5a. The seas: every water has a region (the owner, 2026-10-12)

> Is the Windward Sea the only defined ocean? All water should have regions as well.

It was: `data/spawns.json` `marine_zones` held only the Windward Sea, so the north coast and the Pine Isles' waters, the
strait, the east and south seas, the waters round the Sunset and Fungal isles and the border margin had no region, no
Nuzlocke zone, no location title, and fell back to Cobbleverse's inherited ocean spawns. **Measured on the canonical
heightmap** (ground below y62 on a 16-block raster, the border margin at -1024..9215 taken as sea): the sea is ONE
connected body of 58.85 km2 (plus Lake Tilpey's 0.72 km2 apart), so a "sea" is a division of it. The divisions follow
the planned marine regions of `data/regions.json` and the nearest leg of the critical path along each coast (the nearest
route-path leg of every 64-block sea cell within 400 blocks of land: 3 in the north-west, 4 to 5 along the north, 5 to 7
in the north-east, 6 to 7 down the east, 8 along the south, 1 to 3 in the south-west):

| Sea (zone) | Region | Where | Sea km2 in its clip | Bands (levels) |
|---|---|---|---|---|
| The Windward Sea (`windward_sea`, 2026-09-26) | `windward_deep` | x-1024..991, z2592..5215 | 4.07 | 16-20, 20-25, 25-30 |
| The Outer Deep (`outer_deep`) | `the_outer_deep` | the four 512-block strips of the border margin | 19.92 | one band, 45-55 (40-50 until the balance pass) |
| The Frostwater Shelf (`frostwater_shelf`) | `frostwater_shelf` | north of z2560-2591, x to 4607 | 11.38 | 26-30, 30-35, 35-40 |
| The Pine Strait (`pine_strait`) | `frostwater_shelf` | x4608.., north of z2560: the Northgate and Pine isles' waters | 11.49 | 36-40, 40-45, 45-50 |
| The Eastern Reach (`eastern_reach`) | `eastern_reach` | x6144.., z2560..9215 | 13.24 | 41-45, 45-50, 50-55 |
| The Southern Shallows (`southern_shallows`) | `southern_shallows` | x2048..6143, z5120..9215 | 9.25 | 46-50, 50-55, 55-60 |
| The Sunset Sea (`sunset_sea`) | `southern_shallows` | x-1024..2047, z5120/5216..9215: Fungal and Sunset isles | 9.42 | 21-25, 25-30, 30-35 |

(The clips overlap only at the margin, where `compile_spawns.marine_bands` hands a cell to the first zone to claim it:
Windward, then the Outer Deep.) **Levels** are the Windward Sea's scheme: one gym cap per band, starting at the coast's
own leg (`[cap(L) - 4, cap(L)]`, then up to cap(L+1), then cap(L+2); never over 60). A band's `tier` is the leg whose cap
tops it, and it sets the maturity of its families (section 3) and the next-leg cap its presences reach (section 10). The
shallows are 0-128 blocks from land, the open water 128-384, the deep beyond (the Windward Sea's own are 96/256). **Rosters**
are `data/marine_seas.json`, expanded by `tools/marine_seas.py` through `build_encounters.expand_family` and `build_heart`,
so they follow sections 3, 4 and 10: stages from the jar's evolutions inside the band, maturity by tier, a rare, an
ultra-rare and an alpha heart (the heart is the band cell farthest from every route corridor, a ninth of the band at most,
every heart holding an exact local). Themes: cold seals and shellfish (Frostwater), crabs, barnacles and gulls on the rocky
strait (Pine Strait), schooling fish and their sharks (Eastern Reach), coral, sand and warm-water reef-dwellers
(Southern Shallows), lantern fish and ink-fish (Sunset Sea), the great whales and the dark-water fauna (Outer Deep). No
legendary, mythical, Ultra Beast, paradox or dungeon prize (`tests/test_marine_seas.py`). **Balance pass done 2026-10-13**
(below); the `draft` flag is cleared. Nothing here is seen in game.

#### Balance pass (trainer-balance-designer, 2026-10-13)

What the draft got wrong, read from `data/marine_seas.json` as drafted:

- **Six seas read as one.** Nine filler families ran through most of them: Mantyke in 9 of the 16 bands, Alomomola in 8,
  Dhelmise and Lapras in 7 each, Wailmer and Frillish in 6. The Outer Deep had no family of its own.
- **Three section 5 finds were spent in the seas.** Skrelp, the north-west coast's find, was a rare in the Frostwater
  shallows beside that coast. Dondozo, the Arrow creeks' find, was in the Eastern Reach's deep. Lapras, the Frostpeak
  strand's find, was an ultra-rare in seven bands.
- **The Outer Deep's level logic was false.** It read "every shore's deep water is at or under it" (40-50), but the
  Eastern Reach's deep is 50-55 and the Southern Shallows' 55-60. Sailing out from either, the levels fell.

The rules the rosters now keep (written into the table's `balance_pass`):

1. A family is in at most two of the six seas. Bands of one sea count once, and the Windward Sea is not counted.
2. Each sea has families no other sea and not the Windward Sea carries.
3. Rosters escalate inside a sea: the same families, later stages, further out.
4. A heart is **three presences** (uncommon bucket, weight 3, alpha), one of them an exact local, and nothing else.
5. No legendary, mythical, Ultra Beast, paradox, dungeon prize, mainline starter line or line of the eight starters.

**Alphas.** No sea heart ever held a common-bucket alpha, so the seas were never "full of alphas"; the land and Nether
hearts are where that happens. Four presences became three. The share of a heart's spawns that are alphas is about
5/99.7 x 9/21 = 2.1%. That is computed here for the Pine Strait shallows heart from the table's weights and the v2
bucket weights section 4 relays; the draft's figure was 2.5%. Outside the heart, which is at most a ninth of a band,
the share is zero. This assumes every bucket has a candidate at the position.

Levels are unchanged except the Outer Deep. Per sea (signature species in **bold**):

| Sea | Bands | Theme and signatures | What changed and why |
|---|---|---|---|
| Sunset Sea | 21-25, 25-30, 30-35 (tiers 2-4) | Dusk lights. **Inkay/Malamar**, **Omanyte** (new, ultra-rare in the deep). Its stages are its own: the base Lanturn and Lumineon, which the Windward Sea never shows (its Lanturn and Lumineon carry weight 0). Finneon anchors the shallows, Chinchou the open water and the deep | Out: Horsea, Staryu, Corsola, Mantyke, Dhelmise, Relicanth, Wailmer, Lapras (all fillers or other seas' signatures). In: Bruxish, Omanyte; Clamperl and Alomomola reach the deep too. A rider still on leg 1 (cap 20) off Pallet's south shore meets 21-25. That is kept: mounts come at about the gym-1 cap (the Windward Sea's access note, relayed), and the Windward shallows at 16-20 lie beside it |
| Frostwater Shelf | 26-30, 30-35, 35-40 (tiers 3-5) | The cold north. **Spheal line**, **Seel**, **Shellder**, **Eiscue**, **Hisuian Qwilfish**. Finizen, then Wailmer, then Lapras show as ultra-rares, one band at a time | Out: Skrelp (the north-west coast's find, beside that coast), Clauncher (the South strand's family), Wattrel, Alomomola, Mantyke, Veluza, Dhelmise. Lapras is only in the deep, at 384 blocks or more from the Frostpeak strand's find. Hearts: Sealeo/Dewgong/Barraskewda, then Sealeo/Dewgong/Palafin, then Walrein/Wailord/Dewgong |
| Pine Strait | 36-40, 40-45, 45-50 (tiers 5-7) | The rocky narrows. **Krabby/Kingler**, **Binacle/Barbaracle**, **Wimpod/Golisopod**, **Cramorant**, **Clauncher/Clawitzer**, Tirtouga/Carracosta (ultra-rare), and Clamperl beds that grow Huntail and Gorebyss at tier 7 | Out: Chewtle (already in two water tables: Arrow Lake and Marsh creek), Corphish (Lake Viltri's), Pyukumuku (a warm-reef animal, now the Southern Shallows'), Staryu, Skrelp, Mareanie, Qwilfish, Remoraid, Horsea, Wailmer, Tentacool, Mantyke, Frillish, Relicanth, Veluza, Alomomola, Lapras. The deep's heart is the sea-floor's old guardians: Golisopod, Huntail, Gorebyss |
| Eastern Reach | 41-45, 45-50, 50-55 (tiers 6-8) | Schools and their hunters. **Wishiwashi**, **Wattrel/Kilowattrel**, **Pincurchin**, **Veluza**, with Barraskewda, Octillery, Sharpedo and Palafin | Out: Dondozo (the Arrow creeks' find), Corsola and Luvdisc (the reef's), Tentacool, Wailmer, Clamperl, Dhelmise, Lapras, Alomomola. Tirtouga is the deep's ultra-rare, its second sea. Hearts: Wishiwashi/Kilowattrel/Mantine, then Sharpedo/Palafin/Octillery, then Sharpedo/Veluza/Mantine |
| Southern Shallows | 46-50, 50-55, 55-60 (tiers 7-9) | The warm south. **Corsola**, **Mareanie/Toxapex**, **Pyukumuku**, **Skrelp/Dragalge** (Skrelp's only sea, far from its find), Wugtrio, Bruxish, Kingdra, Mantine | Out: Clauncher, Frillish/Jellicent, Relicanth, Dhelmise, Clamperl, Alomomola, Lapras. In: Wishiwashi (ultra-rare, the deep). Finneon moves from the open water's uncommon to its ultra-rare (Lumineon only, at that band) and stays the deep's uncommon. Hearts: Toxapex/Wugtrio/Starmie, then Kingdra/Dragalge/Tentacruel, then Mantine/Kingdra/Lumineon |
| The Outer Deep | **45-55** (tier 8; was 40-50, tier 7) | The edge of the world, every family full-grown. Wailord, Tentacruel, Jellicent and Lanturn (the Windward Sea's first stages, here last), Alomomola, Dhelmise, **Relicanth** (in no other of the six), Lapras | 45-55 meets the Pine Strait's deep (45-50) and the Eastern Reach's (50-55) with no step down. It falls one cap below the Southern deep only, and stands two to three caps over the Frostwater and Sunset deeps, which is a far edge's job. Out: Veluza, Mantyke, Clamperl. Heart: Wailord/Jellicent/Relicanth at 55-60 |

**Recommended, not done: split the Outer Deep in two.** The ring borders legs 1 to 8, so one band cannot follow the
nearest leg. Two zones would: the western margin, beside the Frostwater and Sunset seas, at 40-45; the eastern and
southern margin, beside the Pine Strait, the Eastern Reach and the Southern Shallows, at 55-60. That changes zone ids
named in `data/nuzlocke_zones.json` (generated) and `data/id_authorship.json` (an exact id set), and this pass edits
`data/marine_seas.json` only. A datapack-content-dev unit would do it with both.

**Numbers not measured here:**

- The coast legs per sea and the km2 are the drafter's 2026-10-12 measurements.
- The v2 bucket weights are section 4's reading of the server file.
- Species ids were checked against the keys of `docs/research/notes/drops-1.8.0.json`. Staryu, Starmie, Clauncher,
  Clawitzer, Wiglett, Wugtrio and Pincurchin are not keys there; that note seems to omit species with no drop table.
  They are taken as real only because the draft's compiled `data/spawns.json` carries them: the generator walked them
  from the jar.

**Boxes are the server's memory.** A box compiles to one spawn condition per roster entry, held in the server's heap, and
`tools/suppress_inherited_spawns.py --subregions` adds one anticondition per merged box to every inherited detail. On the
32-block grid the six seas' bands came to 1,798 to 2,262 boxes. A zone may now carry a coarse `grid` (128) and a
`max_land_share` (0.5): 419 base boxes for the six seas (550 with their hearts), the compiled total 4,364 to 4,914 boxes
(+12.6%) and 48,881 to 53,777 spawn details (+10.0%), and the suppression's merged boxes 926 to 869 (the seas fill the gaps
between the land boxes and the union merges). Of the 58.85 km2 of sea, 97.3% is in a marine box, 2.0% more only in a
sub-region's or a route's box, 0.7% (0.40 km2, slivers beside land) in none, where inherited spawns still live; and 0.1
km2 of water is in a marine box and a sub-region's both.

## 6. Off the path: every place has a find

Every off-path table carries at least one **find**: a family that appears in no on-path table at any tier, whose
final stage has a base-stat total of 480 or more (the pseudo-legendary lines, Lapras, Snorlax, Chansey, Riolu,
Togepi, Toedscool, Aerodactyl, Tauros, Miltank, Cyclizar...). A find is never the base of a Victory Road
family: the prizes and the cave belong to Victory Road. Finds sit in the rare bucket and the top half of
the band. **A route corridor never carries a find**, even where it crosses the find's sub-region: the reward belongs
to the player who leaves the path. The corridor otherwise takes a sub-region's anchor, common and uncommon families
(20 species per route filled by score, `route_species_selection`), and keeps the water families where the route crosses water. **Every crossed table keeps its three likeliest land families** (`rules.corridor_table_min`, play test 2026-10-05, review 85: a corridor box compiles only its own table's listed species, and Pallet's meadows had lost every slot but Caterpie to the route-wide ranking); the kept species may pass 20, up to `rules.corridor_species_ceiling` 40.

**A route has a rare and an ultra-rare table (the owner, 2026-10-05: "every area should have a rare, ultra rare, and
boss table"; ruled the same day that a corridor is an area for the rare and ultra-rare tables but carries no heart --
section 10, the path stays catchable).** Before the corridor is filled by score, `rules.corridor_rare_min` (2 rare, 1
ultra-rare) of the best-scoring rare- and ultra-role families of the crossed **on-path** tables are reserved. An
off-path table's rare families never reach a corridor: they may be its find. The `ultra` role (ultra-rare bucket,
weight 1, the upper half of the band like a find) is the place's rarest family; every table carries one.

A detour should also be *stronger*, not only rarer: at the same tier, the off-path tables' mean base-stat total is at
least the on-path tables'. So an off-path table is **matured one tier further** than its tier (`off_path_maturity_step`):
its families show the evolved share of the next leg, inside its own catchable band.

## 7. Legibility: a theme per place, read by type

Each table names its themes. A theme is a set of types the table's spawns are drawn from; at least 70% of each
context's spawns carry one of them. The late variant of a place keeps its theme and moves along it: the tier 5 marsh
is Croconaw, Palpitoad, Toxicroak and Stunfisk, where a tier 1 marsh would be Wooper and Tympole.

| Theme | Types |
|---|---|
| meadow, plains, heath | normal, grass, bug, fairy, flying, electric, fire, ground, poison, dark, psychic |
| forest, taiga, dark forest | bug, grass, normal, flying, poison, dark, ghost, fairy, steel, ice, fire, electric, fighting, dragon |
| mushroom | grass, bug, poison, fairy, ghost, dark, dragon, electric, water |
| water (any water half) | water, ice, dragon, bug, electric, poison, flying |
| coast | water, flying, rock, electric, poison, psychic, fighting, ice |
| alpine, crags | rock, fighting, flying, steel, dragon, dark, normal, ice, ground, psychic, fairy |
| snow, glacial | ice, water, steel, rock, dark, normal, fairy, dragon, psychic |
| marsh | water, ground, poison, grass, bug, dragon, electric |
| desert, badlands | ground, rock, dark, bug, psychic, dragon, normal, fire, grass, poison, steel, ghost |
| savanna | normal, ground, electric, fire, flying, psychic, fighting, poison, dark, water |
| volcanic | fire, rock, ground, bug, dragon, ghost, poison, steel |
| jungle | grass, bug, normal, flying, fighting, poison, dark, water, dragon |
| cave, rift | rock, ground, steel, poison, dark, ghost, fighting, dragon, flying, psychic, fire, fairy |

## 7a. Victory Road is the end of the journey

Its eleven pools are rebuilt on the same rules at tier 9: only final or single-stage families, a theme per zone (the
Drowned Gallery water, the Slagworks fire, the Bloom spores, the Raw Tear psychic and dragon, the Abandoned Cut
steel), and a small cave staple shared by the themed zones (Noivern, Archaludon, Glimmora) that is never more than a third
of one. A zone has no anchor: three or four strong families at even weight, so no one species dominates. The owner's named misfits leave it: **Excadrill, Quagsire, Whiscash, Boldore and Graveler** belong to tiers 3-5
and now live there. The prizes are the only rare-bucket species in their core tiles, at the top of the band like a
find (57-60): Milotic, Garchomp, Dragapult and Metagross where the owner flew them, and Goodra in the Bloom's core,
where Tangrowth was (Tangrowth stays in the Bloom as its uncommon).

**Hit after hit (the owner, 2026-10-06, after walking it): "some of the mons in victory road feel underwhelming, it
should be hit after hit. why is vileplume there? why is breloom? crobat? i think its final starter evos and pseudo
legendaries or bangers".** Measured from the Cobblemon 1.8.0 jar, the 27 mainline starters' final stages total
525-535 and the pseudo-legendaries 600, so one rule admits all three kinds: **every Victory Road species is a final
stage with a base-stat total of 500 or more**, not legendary, mythical, an ultra beast or paradox, never a client doll,
and never Crobat, Vileplume or Breloom, which the owner named (`rules.victory_road_roster`; Crobat's 535 passes the
number, so it is out by name). A find's family stays out as section 6 says: Dragonite, Tyranitar, Salamence,
Hydreigon, Kommo-o and the seven starter lines that are finds remain the off-path tables' rewards, so the fourteen
starters here are drawn from the twenty lines that are not finds, and the pseudo-legendaries are the four that are not
(Garchomp, Metagross, Dragapult, Goodra). `tools/build_encounters.py`
fails closed on a pool row that breaks any of it. The zones now: the plain cave Rhyperior, Swampert, Torterra,
Infernape, Krookodile, Gallade (rare); the Drowned Gallery Blastoise, Feraligatr, Samurott on land and Starmie,
Kingdra, Gyarados, Walrein, Dhelmise in the water; the Slagworks Charizard, Typhlosion, Cinderace, Arcanine,
Volcarona; the Bloom Venusaur, Meganium, Sceptile, Tangrowth; the Raw Tear Delphox, Chandelure, Gardevoir, Alakazam,
Dusknoir; the Abandoned Cut Aggron, Empoleon, Klinklang, Kingambit. Levels are 54-60, all under the Victory Road cap of 60: the
old 58-64 made a third of the cave's spawns uncatchable.

## 8. Targets a test checks (written before the build)

All measured on the compiled pack with `tools/encounter_audit.py`'s rule for chances (or the test's own), the leg from
`derived/availability.json`, stages and stats from the Cobblemon jar.

1. **Escalation.** The mean base-stat total of on- and near-path land tables does not fall from one tier to the next,
   and Victory Road's is at least 480. The evolved share of those tables is at least 0, 0, 0.10, 0.15, 0.25, 0.30,
   0.40, 0.45 on tiers 1-8 and 0.75 at tier 9.
2. **Victory Road.** In every pool, final or single-stage species are at least 85% of the spawns, no one species is
   over 30% of a context, the staple is at most a third of a themed zone, and Excadrill, Quagsire, Whiscash, Boldore and Graveler do not appear.
3. **Waters.** No water species is in more than two sub-region water tables; Magikarp and Goldeen are each in at most
   two; two water tables on different bodies of water share at most 35% of their probability.
4. **Off the path.** Every off-path sub-region table has a rare- or uncommon-bucket family that is in no on-path
   table, with a final-stage total of 480 or more; no corridor (route file) carries a species that is such a find.
   Per tier, the off-path tables' mean base-stat total is at least the on-path tables'.
5. **Catchable.** No spawn in a table is above its tier's cap.
6. **Legible.** In each table and context, at least 70% of the spawns have a type in the table's themes (section 7).
7. **Gym answers.** Each leg's on- and near-path tables hold at least two families with a type super-effective
   against that leg's gym (Rock, Water, Electric, Grass, Poison, Psychic, Fire, Ground).
8. **Renders.** No spawned species is one the client draws as the substitute doll
   (`modpack/manifest/client-pack-atm-subset.json` `species`).

## 9. What this does not change

- The bird nests in the 52 elders and 14 themed saplings, the Route 1 mansion's ghosts (the owner's designs), the
  Windward Sea's marine bands, the Mt Clay outflow waterway (Gym 3's Ground answers) and the unplaced habitat pools.
- The sub-region polygons, the suppression, the compiler and the Habitat Block placements.
- The spawn conditions vocabulary: only conditions already in the data (`timeRange`, `isRaining`, `maxY`,
  `neededNearbyBlocks` water, `neededBaseBlocks` sand) are used, so contract C4 is untouched. The one addition is
  `minY`, verified in the jar and set by the generator on a summit heart's entries only (section 10); it names no
  block.
- The Jungle Isle's two tables stand over open sea since the water export (decision B15); they are rebuilt on the
  rules but are inert until B15 is decided.

## 10. Small at the edges, big at the heart (the owner, 2026-10-02)

**Built 2026-10-02 (mechanism and content, valid data only, not seen in game). The four numbers below were proposed
here and are confirmed by the owner (2026-10-02): "a ninth, 11.2% above cap, next leg's cap as the ceiling, 128
blocks from a path. Those read right."**

The owner's direction: small Pokemon on a place's outskirts, big ones grouped round its focal points, and on a
mountain "big snowy creatures, anything you'd see on a mountain" -- Frostpeak, the mountain near (0, 0), first (its
highest column is y310 at (679, 313) and (679, 324) on the canonical heightmap). And the balance: **"a new player
should be able to find pockets and readily catchable mons without scouring a landscape."** So above-cap Pokemon are
the exception at a heart, never the texture of a place:

- **The path is always catchable.** A route corridor never carries heart content; everything a player meets on the
  road is at or under the leg's cap.
- **Most of a place is catchable.** The outskirts and middle -- most of a sub-region's area -- stay inside the leg's
  band; only the heart (a summit band, an inner circle) may exceed it.
- **Catchable pockets are near the path.** Every on- or near-path sub-region keeps catchable spawns within easy
  reach of the corridor, not only at its far edge.
- **A heart is mixed, not walled.** Even at a summit, the common bucket keeps catchable stages; the above-cap ones
  are the big, rarer presences that make the place, seen first and caught on a return.

### The mechanism

A design table may carry one `heart` (`data/encounter_design.json`). Its entries **add** to the base table inside
the heart; the base table is unchanged everywhere, so a heart is mixed by construction.

- **summit**: a height line. Every heart entry carries `minY`, and the heart covers the sub-region's cells (below).
  `minY` is a Cobblemon 1.8.0 spawn-condition key: the string is in `SpawningCondition.class` beside `maxY` and
  `canSeeSky`, and 504 spawns in the jar's own 1,544 `spawn_pool_world` files use `condition.minY`
  (Cobblemon-fabric-1.8.0+1.21.1.jar, sha256 a6228f32...dc9ec31). That verifies the key, not its behaviour.
- **focus**: a point (a `data/landmarks.json` landmark, or an x, z with a written reason) and a radius; the heart
  covers the sub-region's cells whose centre lies within the radius.

`tools/compile_spawns.py heart_boxes` takes the sub-region's own cells after the same exclusions as its roster
(corridor, waterway, spawn-free zone), drops every cell within 128 blocks of a corridor box, and for a focus keeps the
circle. Heart entries compile only there (ids `<sub>_h<n>_<species>`), never into a route file. A table without a
heart compiles byte for byte as before (checked: 164 of 164 files identical before any heart was authored).

What a heart holds (`tools/build_encounters.py build_heart`): its **families**, named by the bigger stage itself,
spawn on the upper half of the table's band, from the level they evolve at, matured one tier further than the
table (`hearts.maturity_step`); they stay under the cap. Its **presences** (role `presence`, uncommon bucket, weight
3) are single species from the band's top -- or the level they evolve at, if later -- to the next leg's cap. A heart
holds no find, a base table holds no presence, and a presence that evolves other than by level appears only if the
next leg's tier allows it (section 3). The generator fails closed on a presence in the common bucket, a presence
past the next cap, and a heart over the above-cap share below.

### The numbers (confirmed by the owner, 2026-10-02)

| Number | Proposed | Derived from | Measured on the compiled pack |
|---|---|---|---|
| Most a heart may cover of its sub-region | **1/9 (0.111)** of the compiled area | The owner's three words for a place -- outskirts, middle, heart -- as three rings of equal width: the inner ring of a disc is (1/3)^2 = 1/9 of it, so 8/9 stays the base table ("most of a place is catchable"). A summit's line is the lowest whole Y at or above which at most 1/9 of the area lies; a focus radius is the largest multiple of 16 blocks at or under 1/9, or a feature's own radius if smaller (the crater bowl, 96). | 28 hearts, 4.8% (the Great Crater's bowl) to 11.1% |
| Most of a heart's spawn chance above the cap | **11.2%** | Above-cap spawns are presences, and a presence is never common (the owner: "the big, rarer presences"). Cobbleverse draws uncommon and rare together (10 + 1.2) / (88.5 + 10 + 1.2) = 11.2% of the time, so that is the ceiling by construction. **Stale premise, 2026-10-12:** those are the base pack's v1 weights; the server's v2 file gives (5 + 0.5) / (94 + 5 + 0.5) = 5.5%, so the "by construction" ceiling is about half of 11.2%, and the measured shares in the next column (0.9% to 10.2%) were computed with the v1 weights (`tools/build_encounters.py` `BUCKET_P`, `tools/encounter_audit.py` `BUCKETS`, both still v1) and overstate the uncommon/rare shares the server draws by about 2x. The 11.2% number is unchanged pending the owner; the tools are not re-derived. | 0.9% (Lake Viltri's hollow, land) to 10.2% (the Lower Trough, water), over the heart contexts holding a presence; 0 in every base table and every corridor |
| How far above the cap a presence may go | **to the next leg's cap**: cap + 5 on tiers 1-8, and 62 at tier 9 | "Seen first and caught on a return": a presence is catchable on the next leg. Caps step 5 a leg (`data/trainers.json` gym aces 20-55, the Elite Four at 60); after the Elite Four the next level a player can carry is the champion's top, 62 (`champion_blue`, measured). | Top levels 25 (tier 1) to 62 (tier 9) |
| How "catchable pockets near the path" is measured | **No heart cell within 128 blocks of a route corridor box** (Chebyshev gap) | Section 1's own measure of "near the path" (128 blocks). So the whole band beside the path is the base table, catchable, in every sub-region. | Nearest heart box to any route box: 129 blocks (five hearts: Mt Clay, the Tri Peaks, the Crags, the Lower Trough, the east cones) |

Two assumptions sit under the shares, as under the audit: a bucket with no candidate at a position is renormalised
away, and every level in a range is equally likely. Neither is verified in game.

### Where the hearts are (28), and where there are none

Summits: **Frostpeak** (y180, 11.1%), the **Tri Peaks** (y195), **Mt Clay** (y212), the **Crags** (y171, land
only: the tarn is below the line), the **east cones** (y228, the Craters landmark's cone). **Mt Vessu** has a focus
instead: its top is a flat plateau at y280 (15.1% of the place at or above y280, 0.9% above it), so no height line
takes a ninth; the heart is a circle on the plateau.

Focal points: the lakes -- **Shrew Lake**, **Arrow Lake**, **Lake Tilpey's open water** (94.5% of its heart is lake
bed under y62), the **Ravine Head Tarn** in Peak Pond Hollow, the **Glacial Tear** in the Lower Trough; **Marshy
Marsh**'s middle; the **Great Crater**'s bowl (floor about y195-205 inside a rim up to y302, breached to the east, read from the
heightmap on a 20-block grid);
the **dark Wedge** (north and south); **Northgate's old growth** (the west half, `taiga_dense`); the four **Rift**
tables; the islands -- **Fungal North**, the **north** and **south Pine isles**, **Sunset west**, the **Long Isle**'s
uplands; and two early places, the **south-west fields** (tier 1) and **Lake Viltri's hollow** (tier 2). Where no
landmark marks a focus, it is the place's deepest interior: the cell farthest from every cell outside the place
or inside the path band.

Three focal points belong to the path and stay catchable: **Lake Viltri** (41 blocks from Route 2), **Peak Pond**
(113 blocks from Route 4) and the **Merian** landmark's anchor (65 blocks from Route 4). Their places' hearts are
the far woods, the Ravine Head Tarn and the cirque's interior away from Route 4 instead.

No heart: **Pallet's meadows, the Route 1 forest, the Viltri plateau, the River of Shrews and the west shore** (the
first leg on the path: a new player's ground stays wholly catchable); the **downs, the trough's upper pass, the
glacier-foot fields, the crater rim and the Rift's foot** (open country with no focal point of their own, or mostly
inside the path band: 60% of the glacier-foot fields' cells and 74% of the crater rim's have their centre within
128 blocks of a corridor box); the **Tilpey shores** (their lake's
heart is the open water); **Marsh creek, the eastern moor and the dunes and plateaus** (no focal point read from
the data); the **Frostpeak strand** (the shore under Frostpeak, whose heart is the summit); **Fungal south** and the
**Sunset east**, **Northgate east** and **Long Isle north and south** (one heart an island); the **north-west coast**
and **Viltri's Path valley** (each already holds two finds); the **foothill woods** and the **south strand** (Routes 3 and 8 run through them, so they are the path's); the
**Arrow creeks** (left without a heart in this pass, a candidate for the next: its Dondozo find already sits in the
deep pools); and the **Jungle Isle** (under the sea, decision B15).
Untouched as section 9 says: the bird nests, the mansion, the marine bands, the waterway, Victory Road's pools.

**Every area has a heart (the owner, 2026-10-05: "every area should have a rare, ultra rare, and boss table"; boss =
a heart, approved).** The "No heart" list above is superseded for map rows A-D: Viltri's plateau, Viltri's Path valley,
the foothill woods, the north-east and north-shore downs, the upper trough, the glacier-foot fields, the Frostpeak
strand, the north-west coast, Marsh creek, the eastern moor, the Tilpey north, east and west shores and Northgate east
now carry a focus heart at their deepest interior cell beyond 128 blocks of every corridor (each heart's `why` gives
its point, radius and nearest gap; 129 to 1,113 blocks). The 128-block and 1/9 rules stand for every one of them. The
Windward shallows and deep and the Mt Clay outflow carry a focus heart too (`tools/compile_spawns.py`
`focus_heart_boxes`). The count and list above, and `tests/test_encounter_hearts.py`, still name the 28; updating them
is a test author's change.

### The bosses are alphas, and every boss table holds a local (the owner, 2026-10-05)

**"For the pokemon species overhaul running, the boss pokemon are alphas, so it should sometimes be the pokemon in
the area as well right?"** Built 2026-10-05: valid data and a measured compiled pack only, not seen in game.

- **Every heart entry is a native alpha** (`rules.hearts.alpha`). The compiled spawn's `pokemon` string is
  `"<species> alpha=true"`. That is a PokemonProperties key in Cobblemon 1.8.0 (`PokemonProperties$Companion` registers
  `alpha` and `is_alpha`). It is also the form every one of the jar's own 1,082 alpha spawns uses: each is a herd
  leader in bucket `boss`, e.g. `spawn_pool_world/herds/0023_fearow_alpha.json`,
  `"fearow held_item=cobblemon:flying_gem alpha=true"`. `tools/build_encounters.py` stamps the flag on generated heart
  entries and fails closed on a copied-through one (marine band, waterway) that lacks it, and on a flag outside a
  heart. The other rules of this section are unchanged: focal site, 1/9 of the area, 128 blocks from a corridor,
  above-cap share and the level band, at spawn.
- **What the jar makes an alpha do** (read from Cobblemon-fabric-1.8.0+1.21.1.jar, not observed):
  - `behaviours/pokemon/auto/pokemon_non_party.json` makes a wild alpha retaliate.
  - It gains the `cobblemon:alpha_level_matching` sensor.
  - On faint, `callbacks/battle_fainted/pokemon_alpha_drops.molang` drops `loot_table/alpha/alpha_rewards_tier1-4`
    by level (31, 51 and 66 are the steps), plus type rewards.
  - Its size scales with its hitbox (`Pokemon.getAlphaScaleMultiplier`), and it carries the alpha mark.
  - A battle against it adds the Showdown rule "Wild Alpha" (`BattleBuilder`).
  - Catches count towards `cobblemon:catch_alpha_pokemon`.
- **The authored level is not the level fought.** `AlphaLevelMatchingSensor$Companion.getTargetLevel` works as
  follows. While a player is within 32 blocks and the alpha is not battling, it re-levels to that player's highest
  party level plus a step:
  - +4 below 21;
  - +8 for 21-30;
  - +12 for 31-45;
  - +16 for 46-65;
  - +20 above that.

  The result is held to at most 100 and at least the level its species evolves at. So in game every boss stands
  above the party, which overrides this section's band, its "under the cap" families and its next-cap ceiling for
  presences. Two ways forward, and the choice is **the owner's**:
  - keep the jar's behaviour, which suits a hard boss;
  - overlay `pokemon_non_party.json` at the same path without the sensor, which keeps the band but replaces a whole
    upstream behaviour file.

  **Decided (the owner, 2026-10-05): "keep the alpha scaling".** The jar's behaviour stays; nothing is overlaid. A boss
  is always fought above the party. The record is `rules.hearts.alpha_level_matching`.
- **Every heart holds one of its own place's Pokemon** (`rules.hearts.local_alpha`). Before this, 57 of 67 hearts named
  a species from their own compiled base table: 138 of 238 heart species, 58%. By family (a heart naming the evolved
  stage of a local), all 67 did: 202 of 238, 85%. The ten with no exact local each gain the place's strongest local
  stage, chosen as follows:
  - the highest base-stat total among its common and uncommon base species;
  - mainline starters excluded (section 11);
  - ties go to the higher weight, then the name;
  - role uncommon, at the presences' weight 3.

  The ten are:
  - Pallet's meadows: Fidough;
  - the Route 1 forest: Oddish;
  - Viltri's plateau: Pikachu;
  - the River of Shrews: Minun;
  - the west shore: Staryu (water);
  - the south-west fields: Growlithe;
  - the Windward depths, open sea and shallows: Alomomola, Qwilfish and Staryu;
  - the Mt Clay outflow: Basculin.

  The marine and waterway levels are the upper half of their base band. After the change all 83 hearts hold an exact
  local (67 until 2026-10-12, when the 16 bands of the six new seas, `data/marine_seas.json`, each took one: the
  Windward Sea's three, the waterway's and the 63 land tables are the 67; the 148 of 248 heart species, 60%, below
  counted those 67). The non-local signature bosses stay as authored (Frostpeak's Avalugg and
  Mamoswine, Arrow creeks' Braviary and the rest).

### What the tests make of it

`tests/test_encounter_design.py` reads a sub-region file as one table, so heart rows count as if they covered the
whole place. Three of its tests fail on the hearts, and none was edited (the builder does not write its own tests):

- `test_no_spawn_in_a_table_is_above_its_tiers_cap` (target 5): the 28 hearts' presences, as this section allows.
- `test_on_path_land_strength_never_falls_from_one_tier_to_the_next` (target 1): tier 3 reads 368 and tier 4 360 with
  hearts in; on the base rows alone, by the test's own rule, the tiers rise 277, 289, 326, 348, 375, 435, 438, 473, 512.
- `test_off_path_tables_are_no_weaker_than_on_path_at_the_same_tier` (target 4): tiers 2, 3 and 5 with hearts in; on
  base rows alone off-path is at least on-path at every tier (304/277, 303/289, 343/326, 382/375, 442/435, 441/438,
  484/473).

Target 5 and the per-table tests now become per heart and per base, rewritten by a test author from this section.
`tools/encounter_audit.py` already reports each heart as its own table (base roster plus the heart's own spawns),
with its area share, its gap to the nearest route and its above-cap share.

## 11. The mainline starters in the wild (the owner, 2026-10-02)

**Read with the mythical-starter decision (the owner, 2026-10-02):** with all 27 starter families wild, "traditional starters become something you find rather than something you are handed, which is what I wanted from idea 1"; so the mythical-starter choice (`docs/research/MYTHICAL_STARTERS.md`) and this section are one decision read together, and neither should be changed without the other.

"Bake normal starters from every region and their evolutions as spawns now." All 27 Gen 1-9 starter families are in
the tables, on the existing rules (the tier's band, maturity rising with the tier, finds exclusive and off the
corridors): an **uncommon** family on or near the path, a **find** off it, and a heart may hold the final form as a
presence. Grass on the first three legs (Bulbasaur, Treecko, Snivy, Chikorita, Turtwig), Fire on the Grass gym's leg
(Tepig, Cyndaquil), Water starters on shores (`neededNearbyBlocks` water, standing on land, so no starter placed here is a
water table's family). Two were already water families before this: Totodile at Marshy Marsh and Piplup at the
Lower Trough (section 5), and they stay so; those are the only starters in a water table.

| Leg | Family: table (how) |
|---|---|
| 1 | Bulbasaur: Pallet's meadows. Treecko: the Route 1 forest. Snivy: the Viltri plateau. Popplio: the west shore (shore) |
| 2 | Chikorita: Lake Viltri's hollow (Bayleef common in its heart). Squirtle: Lake Viltri's hollow (shore). Sprigatito: Viltri's Path valley (find) |
| 3 | Turtwig: the foothill woods. Froakie: the north-west coast (find, shore). Quaxly: Arrow Lake (find, shore) |
| 4 | Tepig: the north shore downs. Cyndaquil: the north-east downs. Oshawott: Peak Pond Hollow (shore; Samurott in the tarn heart) |
| 5 | Fennekin: the glacier-foot fields. Mudkip: Marshy Marsh (shore; Swampert in the heart). Litten: Sunset west (find; Incineroar in the heart). Totodile: Marshy Marsh (already; Feraligatr in the heart). Piplup: the Lower Trough (already; Empoleon in the heart) |
| 6 | Chimchar: Tilpey's north shore. Chespin: Tilpey's east shore. Fuecoco: the north Wedge (find). Grookey: Northgate's old growth (find; Rillaboom in the heart). Rowlet: the south Pine isle (already a find; Decidueye in the heart) |
| 7 | Sobble: Tilpey's south shore (shore). Torchic: the crater rim |
| 8 | Scorbunny: the Rift's foot. Charmander: the Great Crater (already; Charizard in the heart) |

`modpack/config/cobblemon/starters.json` was read, not changed: it still lists the 27 normal starters in nine region
categories plus a Hisui set, no mythical, with `useConfigStarters: false`. The owner's mythical starters are not in
that file.

