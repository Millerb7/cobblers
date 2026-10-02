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
- **Naming an evolved species starts the family there**: Victory Road lists `crobat`, not `zubat`; a zone prize
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
families. Cobbleverse's bucket weights decide how often a bucket is drawn (common 88.5, uncommon 10, rare 1.2,
ultra-rare 0.3), so a find is about one land spawn in eighty there: findable by someone who looks, not by someone
passing through.

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

## 6. Off the path: every place has a find

Every off-path table carries at least one **find**: a family that appears in no on-path table at any tier, whose
final stage has a base-stat total of 480 or more (the pseudo-legendary lines, Lapras, Snorlax, Chansey, Riolu,
Togepi, Toedscool, Aerodactyl, Tauros, Miltank, Cyclizar...). A find is never the base of a Victory Road
family: the prizes and the cave belong to Victory Road. Finds sit in the rare bucket and the top half of
the band. **A route corridor never carries a find**, even where it crosses the find's sub-region: the reward belongs
to the player who leaves the path. The corridor otherwise takes a sub-region's anchor, common and uncommon families
(at most 20 species per route, `route_species_selection`), and keeps the water families where the route crosses water.

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
steel), and a small cave staple shared by the themed zones (Crobat, Steelix, Golem) that is never more than a third
of one. A zone has no anchor: three or four strong families at even weight, so no one species dominates. The owner's named misfits leave it: **Excadrill, Quagsire, Whiscash, Boldore and Graveler** belong to tiers 3-5
and now live there. The five prizes (Milotic, Garchomp, Tangrowth, Dragapult, Metagross) stay where the owner flew
them, the only rare-bucket species in their core tiles, at the top of the band like a find (57-60). Levels are 54-60, all under the Victory Road cap of 60: the
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

**Built 2026-10-02 (mechanism and content, valid data only, not seen in game). The four numbers below are proposed,
for the owner to confirm, before a test fixes them.**

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

### The numbers (proposed, for the owner to confirm)

| Number | Proposed | Derived from | Measured on the compiled pack |
|---|---|---|---|
| Most a heart may cover of its sub-region | **1/9 (0.111)** of the compiled area | The owner's three words for a place -- outskirts, middle, heart -- as three rings of equal width: the inner ring of a disc is (1/3)^2 = 1/9 of it, so 8/9 stays the base table ("most of a place is catchable"). A summit's line is the lowest whole Y at or above which at most 1/9 of the area lies; a focus radius is the largest multiple of 16 blocks at or under 1/9, or a feature's own radius if smaller (the crater bowl, 96). | 28 hearts, 4.8% (the Great Crater's bowl) to 11.1% |
| Most of a heart's spawn chance above the cap | **11.2%** | Above-cap spawns are presences, and a presence is never common (the owner: "the big, rarer presences"). Cobbleverse draws uncommon and rare together (10 + 1.2) / (88.5 + 10 + 1.2) = 11.2% of the time, so that is the ceiling by construction. | 0.9% (Lake Viltri's hollow, land) to 10.2% (the Lower Trough, water), over the heart contexts holding a presence; 0 in every base table and every corridor |
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

