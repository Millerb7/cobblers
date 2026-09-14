# Biome and biome-tag coverage

> **Superseded 2026-09-14.** Biome coverage is no longer a region-design constraint; spawns will be curated per sub-region. The current plan and its unused-biome list are in [`REGIONS.md`](REGIONS.md).

**Status: draft, part of the region plan awaiting approval.** No biome has been painted.

Every number here comes from `tools/spawn_biomes.py`, which reads the jars and datapacks
in the live server directory instead of any remembered list. The full reference-by-reference
table is generated into [`BIOME_COVERAGE_MATRIX.md`](BIOME_COVERAGE_MATRIX.md). This page is
the analysis around it.

## What was read

| Source | Read |
| --- | --- |
| Vanilla 1.21.1 | `versions/1.21.1/server-1.21.1.jar`: biome registry and biome tags |
| Mods | every jar in `mods/`, including nested jars. Fabric's convention tags (`#c:`) come from the jars nested in Fabric API and Distant Horizons |
| Datapacks | `datapacks/*.zip` and folders. `datapacks/extra/` (Terralith, the Hoenn, Johto and Sinnoh packs) is **not** loaded by the server, so it is not read unless asked |
| Spawn pools | `data/*/spawn_pool_world/**`, later packs overriding earlier ones by path. Every biome ID and `#tag` in a spawn's `condition.biomes` or `anticondition.biomes` counts |

It reports two scopes:

- **default:** Cobblemon's jar alone. This is "Cobblemon's default spawn files".
- **pack:** after Cobbleverse's datapack overrides 1,025 of Cobblemon's 1,544 pool files.
  This is what the server runs. The pack is the primary scope below.

| | default | pack |
| --- | --- | --- |
| Spawn entries | 4,892 | 5,195 |
| Biome and tag references | 83 | 150 |
| References that resolve to overworld biomes | 49 | 73 |
| Loaded biomes | 70 | 70 |
| Loaded overworld biomes | 55 | 55 |

The 55 loaded overworld biomes include two that are not vanilla 1.21.1, `pale_garden` and
`sulfur_caves`. VanillaBackport, already on the world-critical list, supplies them.

### Corrections to the previous pass

- **The earlier counts double-counted.** "58 overworld tags", "324 entries for
  `is_tropical_island`" and similar figures counted Cobblemon's pool files and Cobbleverse's
  overriding copies as separate entries. The tool now applies the override. The
  `is_tropical_island` figure is 201 entries in the pack.
- **`#cobblemon:is_lush` does have a loaded member:** `lush_caves`. The previous plan said no
  vanilla biome carried it. It is a cave tag, not a missing one.
- **`#cobblemon:is_sky` and `#cobblemon:is_shrubland`** have no loaded member at all. They
  need overlays like the other four, not cave placement.
- **The cave tag's membership depends on scope.**
  - The research note says `#cobblemon:is_cave` does not include `deep_dark`. Cobblemon's own
    tag file lists dripstone and lush caves, plus optional convention and modded entries.
  - In the running pack it pulls in `#c:is_cave` from Fabric's convention tags, which adds
    `deep_dark` and `sulfur_caves`.

## Coverage of the revised plan

A reference is covered when at least one planned biome resolves into it. A species is
reachable when at least one of its entries has a planned biome in its condition and none in
its anticondition. Light, Y level, sky, structures and nearby blocks are **not** evaluated,
so reachable means "possible by biome", not "will spawn".

| Plan layer | pack: references | pack: species | default: references | default: species |
| --- | --- | --- | --- | --- |
| Painted surface biomes only | 66 / 73 | 934 / 963 | 46 / 49 | 840 / 861 |
| + identity overlays (tropical island, snowy forest, volcanic, thermal) | 66 / 73 | 935 / 964 | 46 / 49 | 841 / 862 |
| + `is_lush` fallback overlay, no underground biomes | 67 / 73 | 958 / 964 | 47 / 49 | 862 / 862 |
| Identity overlays + underground biomes, no fallback | 73 / 73 | 964 / 964 | 49 / 49 | 862 / 862 |
| **Full plan** (all overlays and underground biomes) | **73 / 73** | **964 / 964** | **49 / 49** | **862 / 862** |

- **One species name is malformed upstream.** The "964" includes it:
  `herds/0675_pangoro_alpha.json` spells its Pokémon `pangoroheld_item=...`. The real count
  is 963.
- **All 55 loaded overworld biomes now have a home.** The previous plan, measured with the
  same tool, covered 64 of 73 references. With the rift's biomes withdrawn it would have
  covered 62.
- **Underground biomes carry the most risk.** Without them, 29 species are unreachable on
  the painted surface.
  - The `is_lush` fallback brings back the 23 fossil and cave species that depend on lush
    caves, including Ogerpon and Iron Crown.
  - Six still depend on underground biomes: Diancie, Genesect, Marshadow, Stakataka,
    Terapagos and Zygarde.

## Every loaded overworld biome, and where it goes

"Paint" means painting a biome onto existing ground is enough. "Carve" means the terrain
has to change first.

| Biome | Region | Rule | Paint or carve |
| --- | --- | --- | --- |
| windswept_forest | Northern Range | below y128 | paint |
| grove | Northern Range | y128-148 | paint |
| snowy_slopes | Northern Range | y148-165 | paint |
| frozen_peaks | Northern Range | y ≥ 165, windward | paint |
| jagged_peaks | Northern Range | y ≥ 165, lee | paint |
| dark_forest | Windward Coast | base | paint |
| old_growth_spruce_taiga | Windward Coast | y ≥ 112 | paint |
| pale_garden | Windward Coast | flattest hollows y96-112 | paint (VanillaBackport) |
| stony_shore | Windward Coast, Eastern Downs, Stillwater Basin | within 48 of the sea | paint |
| savanna_plateau | Leeward Plateau | base | paint |
| savanna | Leeward Plateau | below y128 | paint |
| desert | Leeward Plateau | y ≥ 138 | paint |
| windswept_savanna | Leeward Plateau | rim, slope ≥ 8° | paint |
| windswept_hills | Rim Uplands | base | paint |
| old_growth_pine_taiga | Rim Uplands | y ≥ 132 | paint |
| frozen_river | Glacier Valley | floor within 90 of the axis, head to d3100 | **carve** (the trough) |
| snowy_taiga | Glacier Valley | walls y ≥ 96 | paint, better after carve |
| taiga | Glacier Valley | lower walls | paint |
| river | Glacier Valley | lake and meltwater river | **carve** (the river channel) |
| windswept_gravelly_hills | Glacier Valley | moraine | **carve** (build the moraine) |
| cherry_grove | Stillwater Basin | base | paint |
| swamp | Stillwater Basin | y ≤ 84 | paint |
| plains | Eastern Downs | base | paint |
| meadow | Eastern Downs | y ≥ 112 | paint |
| birch_forest | Eastern Downs | slope ≥ 7° | paint |
| eroded_badlands | Ember Highlands | broken tableland and cone flanks | paint |
| badlands | Ember Highlands | below y142 | paint |
| wooded_badlands | Ember Highlands | flat tableland y142-165 | paint |
| stony_peaks | Ember Highlands | y ≥ 165 | paint |
| forest | Lakeshore Vale | base | paint |
| flower_forest | Lakeshore Vale | slope < 4° | paint |
| old_growth_birch_forest | Lakeshore Vale | y ≥ 130 | paint |
| beach | Lakeshore Vale, Strand Flats, Jungle Isle, Southern Isles | near the sea | paint |
| sunflower_plains | Strand Flats | base | paint |
| mangrove_swamp | Strand Flats | y ≤ 82 behind the beach | **carve** (the flattening pass) |
| snowy_plains | Northern Isles | base | paint |
| snowy_beach | Northern Isles | within 48 of the sea | paint |
| ice_spikes | Northern Isles | flat interior | paint |
| jungle | Jungle Isle | base | paint |
| bamboo_jungle | Jungle Isle | y ≥ 125 | paint |
| sparse_jungle | Southern Isles | base | paint |
| mushroom_fields | Southern Isles | the F1 islet | paint |
| dripstone_caves | underground, all regions but the rift | WorldPainter underground biome | underground; see below |
| lush_caves | underground, Lakeshore Vale and Jungle Isle | cave layer biome | underground |
| deep_dark | underground, Northern Range | cave layer biome | underground |
| sulfur_caves | underground, Ember Highlands | cave layer biome | underground, optional (VanillaBackport) |
| ocean, deep_ocean, cold_ocean, deep_cold_ocean, frozen_ocean, deep_frozen_ocean, lukewarm_ocean, deep_lukewarm_ocean, warm_ocean | sea | latitude, depth, distance from land | paint |

Per-region band shares are in `data/regions.json`.

### The biomes the brief expected to need new terrain

Each biome's terrain need is described as a design requirement for looking right. It
is not a claim about how vanilla world generation places it.

**jungle, bamboo_jungle, sparse_jungle**
- *Needs:* warm, wet, dense-canopy ground; rolling to steep is fine.
- *On this map:* the Jungle Isle ridge (y104 median) and the Southern Isles, both warm and
  maritime.
- *Verdict:* **paint** onto existing landform.

**mangrove_swamp**
- *Needs:* near-sea-level, very flat, wet ground with shallow water pockets, at a coast.
- *On this map:* no such ground exists. The Strand Flats' lowest ground is y77-82 and only
  38% of it is under 5°.
- *Verdict:* **carve**. The flattening pass the Strand Flats already need must bring a
  coastal strip down to y62-64, with pools cut below y62.

**mushroom_fields**
- *Needs:* an isolated island, cut off by sea.
- *On this map:* the F1 islet already is one.
- *Verdict:* **paint**.

**cherry_grove**
- *Needs:* rolling mid-elevation hills with open understorey.
- *On this map:* Stillwater Basin's rolling ground at y98-101.
- *Verdict:* **paint**. Pink canopy reads at any elevation, so the lower height is a matter
  of look, not function.

**savanna, savanna_plateau, windswept_savanna**
- *Needs:* dry, warm, flat to tabular ground, with broken rims for the windswept variant.
- *On this map:* the Leeward Plateau, which is the flattest region (72% under 5°) and in the
  rain shadow.
- *Verdict:* **paint**.

**badlands, eroded_badlands, wooded_badlands**
- *Needs:* hot, dry ground with mesa or tableland form, eroded flanks, and flat tops for
  the wooded variant.
- *On this map:* the Ember Highlands tableland at y142-165 with its clipped cones.
- *Verdict:* **paint**. The terracotta banding that makes badlands read is a surface
  palette, not a landform. The clipped cone tops are a separate, known gap.

Three more biomes need the glacier carve, because the landform they describe is under-carved
today:

- `frozen_river` on the ice tongue;
- `river` in the meltwater channel;
- `windswept_gravelly_hills` on the moraine.

Painting them before the carve would put river spawns on dry valley sides.

## Tag overlays

Six `#cobblemon:` tags have no loaded member biome, so a painted vanilla biome must be added
to them. `is_lush` gets a seventh, temporary overlay.

**The overlay mechanism is one file per tag in our overlay datapack:**

- **Path:** `modpack/datapacks/<our pack>/data/cobblemon/tags/worldgen/biome/<tag>.json`
- **Body:** `{"replace": false, "values": ["minecraft:<biome>"]}`

**Caveats:**

- `"replace": false` adds to the tag, the same merge rule `spawn_biomes.py` applies. That
  rule is file evidence from how Cobbleverse extends Cobblemon's tags. The effect on spawning
  is **not tested**.
- A tag overlay is global. It is region-scoped only because each overlay biome is painted
  in one region and nowhere else. The script that built this plan asserted that exclusivity;
  once the schema is approved, `tools/validate_data.py` should check it.

| Tag | Adds | Region | Kind | Entries lost without it (pack) | Species lost |
| --- | --- | --- | --- | --- | --- |
| `#cobblemon:is_tropical_island` | jungle, bamboo_jungle, sparse_jungle | Jungle Isle, Southern Isles | identity | 12 | 0 |
| `#cobblemon:is_snowy_forest` | grove, snowy_taiga | Northern Range, Glacier Valley | identity | 1 | 0 |
| `#cobblemon:is_volcanic` | eroded_badlands | Ember Highlands | identity | 31 | 0 |
| `#cobblemon:is_thermal` | eroded_badlands | Ember Highlands | identity | 7 | 0 |
| `#cobblemon:is_lush` | flower_forest | Lakeshore Vale | fallback | 0 while underground lush_caves exist | 0 while they exist; 23 without them |
| `#cobblemon:is_sky` | jagged_peaks | Northern Range | optional | 39 | 0 |
| `#cobblemon:is_shrubland` | savanna | Leeward Plateau | optional | 0 | 0 |

**No overlay is needed to reach any species.** Every species those tags carry is reachable
through some other entry. The overlays matter for regional identity: without `is_volcanic`,
the Ember Highlands would never spawn the 31 entries written for volcanoes.

- **Identity overlays** make a region spawn what its landform promises.
- **Optional overlays** add sky or scrub spawns where the map has nothing closer.
- **The fallback** keeps the previous plan's `is_lush` overlay until an export proves the
  underground `lush_caves` works. Withdraw it then; otherwise fossils also spawn in a flower
  forest.

## Cave tags: can WorldPainter paint underground biomes?

**Yes, in two ways, for WorldPainter 2.27.1, the version installed here.** This was
verified in its source at tag `v2.27.1` but **not tested in an export**. Details and sources
are in `docs/research/notes/underground-biomes.md`.

| Method | What it does | Plan use |
| --- | --- | --- |
| Dimension Properties > General > **Underground biome** (applied since 2.25.0) | Every 4x4 column below its own lowest surface point, less the top-layer depth. One biome per dimension | `dripstone_caves` everywhere |
| Custom Cave/Tunnel layer > **Biome** (since 2.10.0) | Every 4x4x4 cell the carved cave touches | `lush_caves` under Lakeshore Vale and Jungle Isle; `deep_dark` under the Northern Range; `sulfur_caves` under the Ember Highlands |

**Limits and unknowns:**

- The painted Biomes layer is one biome per column. The built-in Caves, Caverns and Chasms
  layers set no biome.
- Whether a tunnel biome overrides the underground biome where both apply is **not
  verified**.
- The lowest terrain in `data/world.json` is y40, so underground biomes occupy at most the
  rock between y40 and the surface. Whether the export extends lower is not recorded.

**Alternatives if the export fails:**

1. **`/fillbiome`** in game, per 4x4x4 cell, capped by `commandModificationBlockLimit`
   (default 32,768; whether that counts blocks or cells is unknown). Later WorldPainter
   Merges can keep those cells with underground biome replacement switched off.
2. **Skip the biome and use spawn conditions.** Cobblemon 1.8.0 conditions include
   `canSeeSky`, `minY`/`maxY` and sky light, and stock cave spawns such as Geodude and Zubat
   already use `maxSkyLight: 7` instead of a cave biome. This only works for spawn files we
   write, which ties it to the spawn philosophy decision in
   `docs/mechanics/SPAWN_PHILOSOPHY.md`.
3. **Habitat Blocks** (Cobblemon 1.8) for fixed cave encounters. Their data format for
   pre-placement is undocumented.

**The first experiment should be a small export** with the underground biome set to
dripstone and one lush tunnel, checked with F3 at several heights. It is listed in
`docs/research/EXPERIMENT_BACKLOG.md`.

## Single homes: species that depend on one planned biome

If one of these biomes shrinks or is dropped, its species leave the map. Pack scope:

| Biome | Only home of |
| --- | --- |
| desert (Leeward Plateau, 18%) | Fennekin, Braixen, Delphox, Trapinch, Vibrava, Flygon, Hippopotas, Hippowdon, Sandile, Krokorok, Krookodile, Silicobra, Sandaconda, Iron Hands |
| lush_caves (underground) | Diancie, and all 23 fossil and cave species if the `is_lush` fallback is withdrawn |
| dark_forest (Windward Coast) | Morgrem, Grimmsnarl, Zacian, Zamazenta, Iron Boulder |
| beach (four regions) | Sandygast, Palossand, Koraidon, Miraidon |
| cherry_grove (Stillwater Basin) | Kubfu, Urshifu, Kartana |
| bamboo_jungle (Jungle Isle) | Stufful, Bewear, and the malformed Pangoro alpha entry |
| deep_dark (underground) | Marshadow, Stakataka |
| dripstone_caves (underground) | Genesect |
| ice_spikes (Northern Isles) | Kyurem |
| jungle (Jungle Isle) | Zarude |
| eroded_badlands (Ember Highlands) | Turtonator |
| sunflower_plains (Strand Flats) | Meloetta |
| windswept_forest (Northern Range) | Cobalion |

## Pack findings outside the plan

- **Unresolvable references.** 61 references resolve to no loaded biome: 1,428 entries in all.
  - The largest groups are mods that are not installed: Aether (599 entries) and The Bumblezone
    (178).
  - Thirteen are Cobblemon tags whose only members are modded biomes (594 entries). Six of
    those are the overworld tags overlaid above; the rest are Nether tags.
  - The remainder are the Cobbleverse IDs below and single references to Terralith, Biomes
    O' Plenty and BYG biomes.
- **Cobbleverse structure spawns.** Cobbleverse's datapack references 30 `cobbleverse:custom_spawn/...`
  biome IDs (43 entries: Articuno Tower, Bell Tower, Kyogre Temple and others). No loaded pack
  defines them, including with `datapacks/extra` loaded. Those spawns cannot fire as written.
  **Not verified in game.**
- **A malformed tag reference.** One entry references `is_warm_ocean` without a `#` or
  namespace.
- **`datapacks/extra`.** Loading it (Terralith and the Hoenn, Johto and Sinnoh packs) would
  raise the loaded biome count from 70 to 165 and the overworld references from 73 to 83. The
  plan covers 78 of those 83; the other five resolve only to biomes it does not paint.

## Reproducing

```bash
python tools/spawn_biomes.py --server-dir <server dir> --scope pack --regions data/regions.json \
    --markdown docs/world-building/BIOME_COVERAGE_MATRIX.md
python tools/spawn_biomes.py --server-dir <server dir> --scope default --regions data/regions.json
```

The coverage-by-layer table and the per-overlay and single-home analyses were produced by
calling the same tool on variants of `data/regions.json` with layers removed. That script is
not committed.
