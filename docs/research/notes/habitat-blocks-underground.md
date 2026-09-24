# Habitat Blocks underground: can Victory Road have wild encounters?

Answered for **Cobblemon 1.8.0 on MC 1.21.1** (the campaign target; the base pack still ships
Cobblemon 1.7.3, `base-pack/inventory/mod_inventory.md:15`). Researched 2026-09-23 for the Rift
Victory Road (666-block enclosed road, y1 → y89, `data/victory_road.json`).

Source of record for Cobblemon code and data is the GitLab tag `1.8.0`
(`https://gitlab.com/cable-mc/cobblemon/-/tree/1.8.0`). **The jar could not be opened in this
session** (the Bash tool is disabled here and the mod jars are gitignored, so
`base-pack/cobbleverse/mods/` and `experiments/EXP-000-*/runtime/` were not reachable). Everything
below rests on the tagged source, the tagged stock data files, the wiki, and local repository files.
Where a jar-level check is still wanted it is named as an experiment.

## Verdicts

| # | Question | Answer | Status |
|---|---|---|---|
| 1 | Does a Habitat Block spawn in a fully enclosed underground space? | Yes at mechanism level. Habitat spawn details carry **no** `canSeeSky`, biome or Y condition — the format has no such field — and Cobblemon's own habitat structures generate underground (y −33..50) | VERIFIED in source and stock data; NOT tested in game |
| 2 | Are the contained details' conditions still applied? | Yes, `injectSpawns` filters by `it.isSatisfiedBy(spawnablePosition)`. But the only conditions a habitat spawn can carry are `timeRange`, `minLight`, `maxLight` (plus `phases`) | VERIFIED in source |
| 3 | Can a habitat pool require darkness? | Yes: `maxLight`, per species. JSON key spelling is inferred, not seen in a stock file | VERIFIED (property exists) / ASSUMED (JSON key) |
| 4 | Range of influence shape | **Sphere**, 3D `distSqr` around the block; vertical reach equals horizontal reach; default 16, no clamp found | VERIFIED in source; vertical reach not measured in game |
| 5 | Do our compiled habitat files carry conditions? | No. `tools/compile_spawns.py` emits only species/bucket/positionType/weight/levelRange/phases, and drops the authored `conditions` object | VERIFIED, `tools/compile_spawns.py:254-257` |

---

## 1. Underground spawning through a Habitat Block

**VERIFIED — the detector is the only geometry gate, and it is 3D.**
`HabitatBlockDetector` (1.8.0) finds habitat blocks through the vanilla POI manager and builds one
influence per block:

```kotlin
override fun appliesTo(spawnablePosition: SpawnablePosition) =
    spawnablePosition.position.distSqr(it.blockPos) <= range pow 2
```

([HabitatBlockDetector.kt][hbd]). `const val RANGE = 128` is only the POI **search** radius
(`searchRange = maxOf(RANGE, input.length * 2, input.height * 2)`), not the influence radius.

**VERIFIED — the pool's details are filtered by their own conditions, and by nothing about the sky.**
In `HabitatBlockEntity` (1.8.0), `injectSpawns` filters `spawnDetails` by bucket, spawnable-position
type and `"it.isSatisfiedBy(spawnablePosition)"`; `affectSpawnable` decides replacement purely by
`"detail in spawnDetails"` ([HabitatBlockEntity.kt][hbe], quoted fragments). The details themselves
are built by `pool.createSpawnDetails(this)` → `HabitatSpawn.createSpawnDetail(...)`, which sets
only `"condition.timeRange = timeRange; condition.minLight = minLight; condition.maxLight = maxLight"`
plus a phase appendage ([HabitatSpawn.kt][hs]). No `canSeeSky`, no `minY`/`maxY`, no biome, no
sky-light is ever set on a habitat detail, because `HabitatSpawn` has no such property.

**VERIFIED — spawnable positions are generated underground.** `CobblemonSpawningZoneGenerator` walks
`"(baseY until baseY + height).reversed()"` and records `canSeeSky`, `light` and `skyLight` as data
about a position; it does not exclude enclosed positions ([CobblemonSpawningZoneGenerator.kt][zg]).
Zone geometry in this pack: `"spawningZoneDiameter": 8`, `"spawningZoneHeight": 16`,
`"minimumSpawningZoneDistanceFromPlayer": 16.0`, `"maximumSpawningZoneDistanceFromPlayer": 64.0`
(`base-pack/cobbleverse/config/cobblemon/main.json:23-27`) — an 8×16×8 box placed 16–64 blocks from a
player, so in a 3–5 block wide tunnel many candidate zones will sit inside solid rock and produce no
positions. That is a spawn-*rate* concern, not a possibility concern.

**VERIFIED — Cobblemon itself places habitats underground.** 1.8.0 ships 17 habitat placed features
([placed_feature/habitats][pfh]). `lost_ruins.json` uses `height_range` uniform **absolute y 7–50**
with an upward `environment_scan` through stone to air and a −7 y random offset;
`deep_roots.json` uses absolute **y −33..30** with a −15 y offset and a scan from
deepslate/stone/clay/moss. The changelog for 1.8.0 says "Added the Habitat Block, a spawner block for
servers and adventure maps that controls spawning in an area" and "Added 49 new habitat structures"
([CHANGELOG 1.8.0][cc]). A cave habitat pool (`lost_cave_ruins.json`) exists and is full of
Duskull/Dusclops/Dusknoir/Spiritomb/Golett/Honedge — i.e. the mod's own design intent is caves.

**Conclusion (VERIFIED at mechanism level, NOT runtime-proven):** a natural Habitat Block with
`ReplaceSpawns` on a fully enclosed road will spawn its pool. The road's `canSeeSky: false` is
irrelevant to a habitat pool. This is the opposite of the route mechanism, where every compiled box
carries `canSeeSky: true` (`tools/compile_spawns.py:64`) and therefore spawns nothing underground.

**Not traced, small residual risk:** `SpawnDetail.isSatisfiedBy` also calls
`"!spawnablePosition.preFilter(this)"` and a post-filter ([SpawnDetail.kt][sd]); `preFilter` runs the
influences (`affectSpawnable`) and the base `postFilter` returns true ([SpawnablePosition.kt][sp]).
Whether `PokemonSpawnDetail` overrides `postFilter` with anything position-dependent was not read.
EXP-021 already observed habitat pools spawning above ground, so the residual risk is specifically
"something in the position filter that only fails underground", which is unlikely but untested.

## 2. What a habitat pool's spawn entry accepts (1.8.0)

**VERIFIED — `HabitatPool` fields**: `id`, `name`, `spawns` ([HabitatPool.kt][hp]). Loaded from
datapack folder `habitat_pools`, `.json`, by **Gson with type adapters** (ResourceLocation,
SpawnablePositionType, Species, IntRange, TimeRange, IntRanges, PokemonProperties) —
no `@SerializedName`, so JSON keys are the Kotlin property names ([HabitatPools.kt][hps]).

**VERIFIED — `HabitatSpawn` properties** ([HabitatSpawn.kt][hs]):

| Kotlin property | Type | Default | Seen in a stock JSON as |
|---|---|---|---|
| `species` | Species | required | `"species": "Duskull"` |
| `spawnablePositionType` | String | required | `"spawnablePositionType": "grounded"` |
| `bucket` | String | `"common"` | `"bucket": "uncommon"` |
| `weight` | Float | `1F` | `"weight": 6.0` |
| `levelRange` | IntRange | `1..Int.MAX_VALUE` | `"levelRange": "15-41"` |
| `modifiers` | PokemonProperties? | null | `"modifiers": "galarian"` |
| `phases` | IntRanges? | null | `"phases": "1, 3-4"` |
| `timeRange` | TimeRange? | null | **not seen in any stock file read** |
| `minLight` | Int? | null | **not seen** |
| `maxLight` | Int? | null | **not seen** |

Stock examples read in full or in part: `lost_cave_ruins.json`, `fae_mounds.json`,
`earthen_hives.json`, `skeletal_fall.json` — none of them uses `minLight`, `maxLight` or `timeRange`
([habitat_pools][hpd]).

**There is no documented way to require darkness by sky access, a Y range, a biome or "no sky" in a
habitat pool.** Those fields exist only on the route/`spawn_pool_world` `SpawningCondition`
(`canSeeSky`, `minX/minY/minZ/maxX/maxY/maxZ`, `minLight/maxLight`, `minSkyLight/maxSkyLight`,
`structures`, …), already verified at 1.8.0 in `docs/research/notes/underground-biomes.md:103-117`.
For a Habitat Block the *block's position* is the geography, so a Y condition would be redundant;
darkness is the one real gate, and it is `maxLight`.

- ASSUMED (strong): the JSON keys are literally `"minLight"`, `"maxLight"`, `"timeRange"`. Evidence:
  Gson reflection with no rename annotations, and all seven observed stock keys equal their Kotlin
  property names. Not proven, because no stock file uses them. Settle it by loading a one-entry pool
  with `"maxLight": 7` and checking the reload log plus `/checkspawn`.
- VERIFIED: `maxLight` is compared against `SpawnablePosition.light`, documented in source as
  "The light level at this location", set from `"light = world.getMaxLocalRawBrightness"` ([zg], [sp]).
  In sealed rock at night-independent depth that is the block light only, which is the same quantity
  `fightorflight` reads for its aggression bonus (`base-pack/cobbleverse/config/fightorflight.json5`;
  see the session note in `data/victory_road.json:293-297`).
- VERIFIED and load-bearing for us: **our compiler cannot express any of this today.**
  `compile_habitat` emits exactly `species, bucket, spawnablePositionType, weight, levelRange, phases`
  and silently drops each entry's authored `conditions` object (`tools/compile_spawns.py:251-262`).
  Every `mechanism: habitat_block` entry in `data/spawns.json` currently has `"conditions": {}`, so
  nothing is lost yet — but a `maxLight` gate needs a generator change, not just a data change.

## 3. Radius, shape, vertical reach

- VERIFIED: the influence test is `position.distSqr(blockPos) <= range^2` — a **sphere** centred on
  the block, so **vertical reach equals horizontal reach** ([hbd]). `tools/habitat_blocks.py:24`
  measures overlaps horizontally "because vertical reach is untested"; the source says the correct
  test is 3D distance, which makes the horizontal-only overlap check *optimistic* for blocks stacked
  in a shaft (two blocks 30 apart vertically with range 24 each would overlap, and EXP-021 showed an
  overlap of two `ReplaceSpawns` blocks spawns nothing).
- VERIFIED: `NaturalHabitatSpawning` defaults `rangeOfInfluence = 16`, `replaceSpawns = false`, with
  transient `affectsFishing` / `affectsOverworld` flags deciding whether a given spawner type is
  influenced at all; no clamp or maximum was found ([NaturalHabitatSpawning.kt][nhs]). The wiki gives
  the same default: "Range of Influence (blocks) … default 16" ([wiki][hb]).
- VERIFIED (NBT keys, from `DataKeys.kt` 1.8.0): `SpawningStyle`, `PoolId`, `ReplaceSpawns`,
  `RangeOfInfluence`, `MimicId`, `PhaseOrder`, `LevelRange`, `Modifiers`, and for the activated style
  `Trigger`, `Chance`, `MaxSpawns`, `MaxSpawnsPerActivation`, `SpawnRange`, `CancelRange` ([dk]).
  These match the two commands EXP-021 proved (`experiments/EXP-021-habitat-block-influence/README.md:27-28`).
- VERIFIED in game (EXP-021, 2026-09-17, Cobblemon 1.8.0 + full COBBLEVERSE stack): with
  `RangeOfInfluence: 24`, `/checkspawn` gave the pool only out to 16, a mix at 24 and defaults at 32,
  measured east along one axis on level ground. Vertical was never measured.
- NOT VERIFIED: that a large range (e.g. 64) behaves the same, and that the sphere is what a player
  experiences (the spawning zone is a box up to 64 blocks from the player, so the *player* can stand
  outside the sphere while a spawn position inside it is scored).

**Consequence for Victory Road:** a sphere is a poor fit for a 666-block corridor. A single block
cannot cover it; a chain of non-overlapping spheres leaves gaps where the pool underneath shows
through, and the current overlap rule in `tools/habitat_blocks.py` is horizontal only, which a
climbing road breaks. Tiling a road that gains 88 blocks of height is an unsolved design problem, not
a solved one.

## 4. Dark and Ghost candidates for a level 50–59 enclosed-rock pool

Conventions actually in use (`data/spawns.json`): family weights anchor 24 / common 12 / uncommon 6 /
rare 2 / ultra-rare 1 (`data/spawns.json:10-31`); one family shares one budget with stage splits
1.0 / .75+.25 / .70+.23+.07; eligibility is *"level evolution only when every threshold is at or
below the local band minimum; special evolutions and highlighted families are authored-only"*
(`data/spawns.json:32-49`). `eligibility_reason` strings observed: `"base stage"`,
`"level evolution eligible"`, `"evolution requires level N; band begins at M"` (then
`ambient: false`, `bucket: "authored-only"`, `weight: 0`), `"player evolution (non-level method)"`
(same treatment — e.g. Gengar, Honchkrow, Mismagius at `data/spawns.json:18221-18308`).
`rift_depths` is band **50–59** (`data/spawns.json:24192-24200`), so an evolution threshold of **50 or
less** is eligible.

**This is a candidate list with evidence. No weights, no buckets, no roster edit is proposed.**

### Not used anywhere in the campaign yet

| Species id | Types | Evidence it exists / fits | Evolution note |
|---|---|---|---|
| `spiritomb` | dark/ghost | Stock 1.8.0 cave pool `lost_cave_ruins.json` (uncommon, weight 10, levels 24–49) | No level evolution; base-stage eligible. VERIFIED present in 1.8.0 data |
| `honedge`, `doublade`, `aegislash` | steel/ghost | Stock `lost_cave_ruins.json` (8–33 / 35–45 / 40–50) | Doublade level threshold ASSUMED 35 (≤50, eligible); Aegislash is item-based → authored-only under the policy |
| `deino`, `zweilous` | dark/dragon | `species/generation5/deino.json` 1.8.0: `"minLevel": 50` to `zweilous` — VERIFIED | Zweilous exactly at the band minimum, so eligible by the written rule; Hydreigon (ASSUMED 64) authored-only |
| `dreepy`, `drakloak` | dragon/ghost | `species/generation8/dreepy.json` 1.8.0: `"minLevel": 50` to `drakloak` — VERIFIED | Same edge case as Deino; Dragapult (ASSUMED 60) authored-only. Power level is a design question |
| `yamask` (galarian) | ground/ghost | Stock `lost_cave_ruins.json` uses `"species": "Yamask"` with `"modifiers": "galarian"` | Its evolution (Runerigus) is a special method → authored-only. Note the campaign already lists `runerigus` as `"base stage"` ambient ultra-rare in `rift_depths` (`data/spawns.json:11593-11603`, `24374`) — worth re-reading against the policy |
| `drifloon`, `drifblim` | ghost/flying | Not in `data/spawns.json` at all; EXP-021 saw a Drifloon herd in the *default* pool (`experiments/EXP-021-habitat-block-influence/README.md:64`) | Drifblim threshold ASSUMED 28 |
| `sandygast`, `palossand` | ghost/ground | Not in `data/spawns.json` | ASSUMED 42. Sand, not rock — weak thematic fit |
| `maschiff`, `mabosstiff` | dark | Not in `data/spawns.json` | ASSUMED 30 |
| `houndstone` | ghost | Greavard is used elsewhere (below), Houndstone is not | ASSUMED 30 |

### Already used elsewhere (repetition the owner should judge)

| Species id | Types | Where it already is | Eligibility at band min 50 |
|---|---|---|---|
| `duskull`, `dusclops`, `dusknoir` | ghost | `peak_pond_hollow` (`data/spawns.json:18477`, `18494`), Duskull also `route_1_ghost_mansion` (`22629`); stock `lost_cave_ruins` + `skeletal_fall` | Dusclops ASSUMED 37 → eligible; Dusknoir non-level → authored-only |
| `golett`, `golurk` | ground/ghost | `rift_depths` already has `golett` (`11515`, `24281`); `rift_south_east_arm` has both (`15786`, `15802`) | Golurk ASSUMED 43 → eligible |
| `sableye` | dark/ghost | `mining_town_fossil_levels` (`22907`), `displaced_city_cavern` (`23971`, ultra-rare) | No evolution |
| `mimikyu` | ghost/fairy | `displaced_city_cavern` (`23939`, ultra-rare) | No evolution |
| `greavard` | ghost | `displaced_city_cavern` (`23955`), `route_1_ghost_mansion` (`22691`) | see Houndstone above |
| `zorua`, `zoroark` | dark | `south_pine_isle` (`12299`, `12316`), Zorua in `route_1_ghost_mansion` (`22738`); stock `skeletal_fall` | Zoroark ASSUMED 30 → eligible |
| `gastly`, `haunter`, `gengar` | ghost/poison | `wedge_north` (`18187`–`18223`, night-gated), `route_1_ghost_mansion` (`22537`, `22553`) | Haunter ASSUMED 25 → eligible; Gengar trade → authored-only (already so authored) |
| `misdreavus`, `mismagius` | ghost | `wedge_north` (`18277`, `18293`) | Mismagius item → authored-only (already so authored) |
| `shuppet`, `banette` | ghost | `peak_pond_hollow` (`18443`, `18460`), Shuppet in `route_1_ghost_mansion` (`22599`) | Banette ASSUMED 37 → eligible |
| `litwick` (+ `lampent`) | ghost/fire | Litwick in `route_1_ghost_mansion` (`22644`) | Lampent ASSUMED 41 → eligible; Chandelure item → authored-only |
| `scraggy`, `scrafty` | dark/fighting | `rift_south_west_arm` (`15609`, `15625`) | Scrafty ASSUMED 39 → eligible |
| `pawniard`, `bisharp` | dark/steel | `rift_west_spur` (`15482`, `15498`) | Bisharp ASSUMED 52 → **not** eligible at band minimum 50 |
| `murkrow`, `honchkrow` | dark/flying | `wedge_north` (`18241`, `18259`) | Honchkrow item → authored-only |
| `houndour`, `houndoom` | dark/fire | `plateau_east` (`16770`, `16786`); stock `skeletal_fall` | Houndoom ASSUMED 24 → eligible |
| `absol` | dark | `the_tri_peaks` (`14803`), `frostpeak` (`17055`) | No evolution |
| `sneasel`, `weavile` | dark/ice | `north_pine_isle` (`12188`), `frostpeak` (`16977`, `16993`), `glacial_tear_deep_valley` (`23140`) | Weavile item+night → authored-only. Ice flavour is a poor fit for the Rift |
| `phantump`, `trevenant` | ghost/grass | four places (`11838`, `18151`, `18345`, `23092`) | Trevenant trade → authored-only |
| `sandile`/`krokorok`/`krookodile`, `drapion`, `vullaby`/`mandibuzz`, `cacturne` | dark mixes | `plateau_west` (`16421`–`16533`), dunes (`22190`–`22364`) | Desert identity already spent elsewhere |
| `runerigus` | ground/ghost | already in `rift_depths` (`11593`) and `rift_south_west_arm` (`15673`) | see Galarian Yamask above |

Repetition summary: every ghost line the campaign owns is already spent on the Route 1 mansion
(band 6–15), Wedge North (25–45), Peak Pond Hollow (30–32) or the Displaced City cavern (32–45).
The only Dark/Ghost material that is both unspent and level-appropriate for a 50–59 band is
**Spiritomb, the Honedge line, Galarian Yamask, the Deino line and the Dreepy line** — and the last
two are dragons, which is a different decision from "make the dark mean something".

Not verified for any species above: that the campaign has no separate reservation (gym leader ace,
legendary, reward) on it. `docs/story/AVAILABILITY.md` and `docs/story/TRAINERS.md` were not audited
for this note.

## 5. What else in the pack spawns Pokémon underground

- VERIFIED (upstream Cobblemon 1.8.0): stock world spawns already reach caves without a cave biome —
  `geodude-2` uses `maxSkyLight: 7` with `#cobblemon:is_overworld`, `zubat-4` uses `canSeeSky: false`
  (`docs/research/notes/underground-biomes.md:118-121`). Seventeen habitat placed features generate
  underground, `lost_ruins` at absolute y 7–50 and `deep_roots` at y −33..30 ([pfh]).
- VERIFIED (local plan): the world paints `dripstone_caves` as the dimension-wide underground biome
  and `lush_caves` / `deep_dark` / `sulfur_caves` in tunnel layers
  (`docs/world-building/BIOME_COVERAGE.md:237-238`). Combined with
  `"retain_defaults": [... "unauthored caves" ...]` (`data/spawn_suppression.json:28-36`), the
  inherited pack pools — not ours — are what spawns in Rift rock today. The claim "nothing wild
  spawns underground in the Rift" is exact only for *campaign-authored* pools.
- NOT ANSWERABLE from this session: whether the Cobbleverse datapacks add or change underground
  spawns. `COBBLEVERSE-DP-v31.zip`, `COBBLEVERSE-Loot-DP-v11.zip`, `COBBLEVERSE-RCT-DP-v20.zip`,
  `PokeCenterPCs-DP.zip`, `COBBLEVERSE - No Ender Dragon.zip`, `COBBLEVERSE - No Hunger.zip` and
  `extra/{Hoenn,Johto,Sinnoh,Terralith}-DP.zip` (`base-pack/inventory/pack_hashes.csv:139-148`) are
  zips outside the repository; they could not be opened here. `docs/mechanics/SPAWN_PHILOSOPHY.md:31-37`
  records that a previous measurement found 5,195 loaded spawn entries with the Cobbleverse datapack
  overriding **1,025 of 1,544** pool files by path — so Cobbleverse does rewrite most of the spawn
  table, underground included, but which files and with what conditions is not recorded anywhere in
  the repo.
- The tool that answers it already exists: `tools/spawn_biomes.py` reads jars, `datapacks/*.zip` and
  `datapacks/extra/` from a server directory (`tools/spawn_biomes.py:1-28`). Run it under the server
  lock and filter for `canSeeSky: false`, `maxSkyLight`, `maxY` and cave biome tags.
- `cobblemon-additions` "ships assets/cobblemon + spawn_pool data"
  (`docs/research/COBBLEVERSE_COMPATIBILITY.md:129`) and LumyMon adds worldgen + custom mechanics
  (`base-pack/inventory/mod_inventory.md:27`); neither was inspected. Repurposed Structures adds
  structures only — Cobblemon's `structures` spawn condition could key off them, but no evidence was
  found that anything in the pack does.

## Unknown / experiment candidates

1. **EXP-028 (proposed) — a Habitat Block in sealed rock.** Place one natural `ReplaceSpawns` block
   in a fully enclosed chamber with no sky access, force one chunk reload, then `/checkspawn` beside
   it *and* sample actual spawns for 8 minutes as EXP-012 did. Must show: the pool's species in the
   table, and at least one real spawn. This is the only thing that converts §1 from "mechanism
   verified" to "works".
2. **Vertical reach.** Two blocks in a shaft, 30 blocks apart vertically, range 24 each. The source
   predicts they overlap and therefore spawn nothing; if they instead work independently, the
   influence is not a sphere and `tools/habitat_blocks.py`'s horizontal-only overlap check is right.
3. **`maxLight` in a habitat pool.** Load a one-entry pool with `"maxLight": 7` (and a second with
   `"timeRange"`). A reload error, or a species that ignores the gate under a torch, settles the JSON
   key names. Cheap, and it is the whole basis of "the dark is a difficulty setting".
4. **Large range.** `RangeOfInfluence: 64` measured the same way as EXP-021, before any corridor
   tiling design is written.
5. **What the pack spawns in Rift rock today.** `tools/spawn_biomes.py` against the assembled server,
   filtered to underground conditions — the Q5 gap above.
6. **`postFilter` on `PokemonSpawnDetail`.** Read it in the 1.8.0 jar or source to close the last
   "could something reject an enclosed position" gap.

[hbd]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/influence/detector/HabitatBlockDetector.kt
[hbe]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/block/habitat/HabitatBlockEntity.kt
[hp]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/habitats/HabitatPool.kt
[hps]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/habitats/HabitatPools.kt
[hs]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/habitats/HabitatSpawn.kt
[nhs]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/habitats/spawningstyle/NaturalHabitatSpawning.kt
[sd]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/detail/SpawnDetail.kt
[sp]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/position/SpawnablePosition.kt
[zg]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/CobblemonSpawningZoneGenerator.kt
[dk]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/util/DataKeys.kt
[hpd]: https://gitlab.com/cable-mc/cobblemon/-/tree/1.8.0/common/src/main/resources/data/cobblemon/habitat_pools
[pfh]: https://gitlab.com/cable-mc/cobblemon/-/tree/1.8.0/common/src/main/resources/data/cobblemon/worldgen/placed_feature/habitats
[cc]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/CHANGELOG.md
[hb]: https://wiki.cobblemon.com/index.php/Habitat_Block
