# Spawn philosophy: curated routes, full dex, or a hybrid

**Status: analysis for a decision you have not made.** This document recommends nothing
as settled. It rests on no experiment yet: EXP-001 has not proven spawn control on a
route, and EXP-003 (level cap) is planned, not run. Anything below about behaviour in a
running server is marked as assumed.

All counts come from `tools/spawn_biomes.py` run against the live server directory
(Cobblemon 1.8.0 plus the mods and required datapacks the server loads), and from the
region plan in `data/regions.json`.

## Two facts that frame the choice

**1. The vision document has already chosen.** `docs/vision/GAME_VISION.md` says "Every
area has an authored encounter table of roughly 10 to 20 deliberate species" and
"The generic Cobblemon 'everything spawns everywhere' feel is the thing we are
replacing." Pillar 3 is titled "Curated encounters". Option B contradicts the design
source of truth. Choosing it means changing the vision document, through an ADR.

**2. This brief pulls the other way.** Making "hit every biome Cobblemon attaches spawns
to" a primary constraint only matters if Cobblemon's default spawn files stay in charge.
Under a fully curated model those files are replaced, so their biome coverage is
irrelevant. The region plan now satisfies that constraint completely, so it is shaped for
B even though the vision asks for A. The hybrid below is the one reading in which both
are right.

## What the pack does today, measured

| Measure | Value |
| --- | --- |
| Spawn entries the server loads (Cobblemon jar after Cobbleverse overrides) | 5,195 |
| Entries that can occur in the overworld | 4,416; 4,455 once the `is_sky` overlay puts sky spawns on the range summits |
| Distinct species among them | 963, plus one malformed entry (below) |
| Buckets | common 2,277, boss 1,082, uncommon 1,004, ultra-rare 540, rare 292 |
| Level span per entry (max minus min) | median 25, 90th percentile 77 |
| Entry minimum level | median 20; 37% of entries start at level 10 or below |
| Pool files the Cobbleverse datapack overrides by path | 1,025 of 1,544 |

Under those default files, with the planned biomes painted, each region can spawn:

| Region | Species reachable | Species reachable in no other region |
| --- | --- | --- |
| Stillwater Basin | 643 | 3 |
| Eastern Downs | 646 | 0 |
| Northern Range | 582 | 1 |
| Lakeshore Vale | 562 | 23 |
| Strand Flats | 560 | 1 |
| Leeward Plateau | 559 | 36 |
| Glacier Valley | 536 | 0 |
| Jungle Isle | 523 | 4 |
| Southern Isles | 522 | 0 |
| Windward Coast | 509 | 16 |
| Ember Highlands | 484 | 16 |
| Rim Uplands | 482 | 0 |
| Northern Isles | 382 | 4 |
| The Rift | deferred | |

Neighbouring regions share most of their roster. The share of species two regions have in
common (Jaccard index):

| Pair | Overlap |
| --- | --- |
| Eastern Downs / Stillwater Basin | 0.89 |
| Glacier Valley / Northern Range | 0.82 |
| Lakeshore Vale / Windward Coast | 0.77 |
| Leeward Plateau / Ember Highlands | 0.74 |
| Rim Uplands / Eastern Downs | 0.72 |

The main cause is `#cobblemon:is_overworld`: 1,213 entries covering 325 species that match
every overworld biome.

Two details matter for either option:

- The server's own data already shows how spawns get replaced. Cobbleverse overrides
  Cobblemon's pool files by path, and pool files carry an `enabled` flag. That override
  behaviour is file evidence, not an in-game test.
- One malformed upstream entry: `herds/0675_pangoro_alpha.json` in the Cobblemon 1.8.0 jar
  has `"pokemon": "pangoroheld_item=cobblemon:fighting_gem alpha=true"`, with a missing
  space. That spawn probably fails to resolve. **Not verified in game.**

## Option A: curated per route

Every region, or every route within it, has a hand-authored table. Default pools are
disabled by path.

**What it demands of the region plan**

- Regions have to be separable at spawn time. Biome alone is not enough: `beach` appears in
  four regions, `stony_shore` in three, and dripstone caves under every region. A curated
  table needs one of the following. None is proven here, so each would be an experiment.
  - Region-exclusive biomes. The plan already enforces this for overlay biomes only.
  - Coordinate bounds. `minX`, `maxX`, `minZ` and `maxZ` exist in the 1.8.0 spawn
    conditions (`docs/research/notes/underground-biomes.md`), but they describe
    rectangles, and region polygons are not rectangles.
  - A custom biome per route.
  - Habitat Blocks.
- Biome coverage stops mattering. A curated table can put any species anywhere.
- Terrain character starts to matter more. The table has to be believable on the ground
  it covers.
- Routes need to be drawn inside regions before tables can be written. No routes exist yet,
  by instruction.

**Generated versus hand-written**

| Part | Generated | Hand-written |
| --- | --- | --- |
| Disable every default pool | Yes: one file per pool path with `enabled: false`, or an empty override | |
| Species candidates for a route | Yes: filter the pack's own entries by the route's biomes, giving a shortlist of 380 to 650 species per region | |
| Final 10 to 20 species per route, buckets, weights | | Yes |
| Level ranges | Partly: derive from the route's chapter cap | Yes: adjust per species |
| Type-coverage check against the next gym | Yes: a validator | |
| Legendary and fossil placement | | Yes: dungeon rewards, per the vision |

At about 15 species per route over roughly 20 to 30 routes, that is 300 to 450 hand-placed
species slots. Each needs a bucket, weight, level range and conditions.

**Level caps and gym progression**

This is A's strongest point. Each table's levels sit just under its chapter's cap, and the
table before a gym is audited for counterplay: "every difficult boss must have plausible
tools available somewhere in the accessible region" (vision, pillar 1). The team-building
arc is designed, not rolled.

**Costs and risks**

- The authoring load above.
- Narrowness. With 15 species per route, some types or roles may never appear before a
  given gym unless the tables are audited.
- Every species needs a home, or is deliberately absent. The pack reaches 963 species. A
  curated region will likely host 250 to 400. The rest are postgame, trade-only, or gone,
  and that is a decision to make explicitly.
- It stands or falls on EXP-001's missing spawn proof: the default spawner has to be fully
  suppressible. **Not verified.**

## Option B: full dex with scaling levels

Default pools stay. Most species spawn wherever their biome is. Levels scale by region or by
progression.

**What it demands of the region plan**

- Complete biome coverage, which the plan now has.
  - With the painted surface, the identity overlays, the `is_lush` fallback and the
    underground biomes: 73 of 73 overworld references and all 963 species.
  - Without the underground biomes, 6 legendaries and mythicals are unreachable: Diancie,
    Genesect, Marshadow, Stakataka, Terapagos and Zygarde.
- Band sizes become spawn weights. A species reachable only through a 1% band is
  effectively absent.
  - The single homes that matter most: `desert` on the Leeward Plateau (14 species),
    `lush_caves` underground (Diancie, and every fossil once the fallback is withdrawn) and
    `dark_forest` on the Windward Coast (5).
  - Also single homes: `cherry_grove` in Stillwater Basin (Kubfu, Urshifu, Kartana),
    `ice_spikes` on the Northern Isles (Kyurem) and `sunflower_plains` on the Strand Flats
    (Meloetta).
- Regional identity has to come from something other than the roster. At 72 to 89% overlap
  between neighbours, the roster will not provide it.

**Generated versus hand-written**

Almost everything is inherited or generated:

- The pools stay.
- Level scaling is a transform over 5,168 level ranges.
- Region scoping is the biome plan itself.

The hand-written part is exceptions: legendaries moved behind content, and a few signature
spawns per region.

**Level caps and gym progression**

This is B's weakest point.

- The default ranges are wide (median span 25 levels) and are not tied to any progression.
- Scaling by region needs a mechanism, and none has been identified or tested:
  - rewritten ranges per region (generated, but then biome-shared species need per-region
    copies);
  - a mod or config feature (**not researched**);
  - capping at catch time (EXP-003 territory).
- A level cap stops over-levelling, but it does not make species availability line up with
  gym design. Players reach the whole dex early, so no boss can assume the players lack an
  answer. Difficulty tuning therefore shifts entirely onto trainer design.
- There is less reason to travel. Most regions offer most species.

## A hybrid: curated spine, open wilderness and postgame

**Is it coherent?** Yes, if the scoping mechanism exists. The region tiers already separate
the two kinds of ground.

| Tier | Regions | Hybrid role |
| --- | --- | --- |
| hub | Leeward Plateau, Rim Uplands, Stillwater Basin, Eastern Downs | Curated. On the mandatory spine; tables tuned to the chapter cap |
| route | Windward Coast, Glacier Valley, Lakeshore Vale, Strand Flats | Curated where the spine passes; could open once their chapter is cleared |
| wilderness | Northern Range, Ember Highlands, Northern, Jungle and Southern Isles | Open. Default pools, level-shifted, optional |
| destination | The Rift | Deferred, with its own custom biome and table |

This table maps tiers to roles. It assigns no routes, gyms or events.

**Rules that keep it coherent**

1. **One scoping mechanism for both sides.** For example, suppress the defaults in
   curated regions by coordinate bounds and leave them active elsewhere. Mixing "biome
   decides" and "table decides" at a shared border produces leaks.
2. **Wilderness must not undercut the spine.** An open wilderness reachable in chapter 1
   hands out the answers the chapter 3 gym was designed to deny. Either the wilderness is
   physically gated until its chapter, or its levels and buckets scale so the strong
   answers arrive late.
3. **Postgame opening is a switch, not a second world.** Re-enabling default pools in
   curated regions after the league is a datapack toggle if the suppression is done by
   override. **Assumed; not tested.**
4. **Coverage still matters, but only for the open tiers.** The wilderness regions together
   reach 780 species today. The curated spine does not need coverage at all.

**Costs.** Both authoring loads, at smaller scale. The tiers need gating, so wilderness
access becomes part of progression design. The suppression mechanism has to work per
region, which is more demanding than an all-or-nothing switch.

## Which option the current plan suits

**Structurally, the hybrid. By its constraints, B.**

- The biome plan serves B. It is driven to complete default-spawn coverage, overlays
  included. That work is necessary for B and for the open tiers of a hybrid, and wasted
  under pure A.
- The region structure serves A and the hybrid. The plan has tiers, terrain-bounded
  regions, exclusive overlay biomes, and landmarks with extents. Those are what route-scoped
  tables need, and B has no use for tiers.

**To support pure A, change:**

- Demote biome coverage from a primary constraint to a believability check. Biome choice
  would then follow terrain and look alone.
- Give every curated region an exclusive spawn-scoping handle: a unique biome, a custom
  biome, or tested coordinate bounds.
- Draw routes, since tables attach to routes.
- Decide the fate of the roughly 550 species that will not fit in curated tables.
- Run EXP-001's spawn-suppression proof before any table is written.

**To support pure B, change:**

- Rewrite `GAME_VISION.md` pillar 3 and its "10 to 20 deliberate species" line, through an
  ADR.
- Identify and test a level-scaling mechanism. None is known.
- Give regions identity beyond their roster: at 72 to 89% overlap the roster cannot carry
  it.
- Rebalance band sizes, so single-home species get enough ground to actually spawn.
- Move legendaries out of default pools and behind content, which the vision still asks for.

## Open questions this raises

1. Can default spawning be suppressed in part of the world and left on elsewhere?
   (Extends EXP-001.)
2. Do `minX`/`maxX`/`minZ`/`maxZ` conditions behave as bounds on a live 1.8.0 server?
3. Is there any level-scaling mechanism for wild spawns short of rewriting ranges?
4. What happens to the malformed Pangoro alpha entry in game?

---

## The rosters carry families this world cannot finish

**Status: a measured gap, recorded 2026-09-23. It decides nothing.** It came out of the
Victory Road reward inventory (`docs/research/notes/reward-item-inventory.md` section 2) and
is larger than Victory Road: it touches every roster in `data/spawns.json`. It belongs here
because the encounter design is what depends on it — `evolution_policy` in
`data/spawns.json:32-49` budgets weight across a family's stages on the assumption that a
player who catches the base stage can reach the rest.

Throughout, *placed* means "authored into a roster that `tools/compile_spawns.py` compiles",
not "in the live world": **VERIFIED** 0 pools, blocks or suppression are installed in the
live world (`docs/STATE.md` "Encounter data").

### 1. No evolution-stone ore generates anywhere in this world

- **VERIFIED** a WorldPainter export writes every chunk as already generated, so no placed
  feature runs inside it: no ores, apricorn trees, berries, mints, fossils or wild waystones
  (`docs/world-building/WORLDGEN_FEATURES.md:5-9`).
- **VERIFIED** Cobblemon 1.8.0 contributes 103 placed features, **42 of them
  evolution-stone ore features** (`WORLDGEN_FEATURES.md:25`). All 42 are absent from the
  export.
- **VERIFIED** the Nether and End generate normally and keep their features
  (`WORLDGEN_FEATURES.md:7-8`), so `cobblemon:nether_fire_stone_ore` is the single
  surviving stone ore in the game. It is the one stone with **no consumer at all** in the
  rosters (below), which is the whole gap in one line.
- **VERIFIED** the 23 blocks exist and are registered — `cobblemon:fire_stone_ore`,
  `deepslate_*`, `dripstone_moon_stone_ore`, `terracotta_sun_stone_ore` and the rest
  (`base-pack/cobbleverse/config/roughlyenoughitems/collapsible.json5:139-161`). Nothing
  places them.

### 2. The scatter pass that would put them back is specified and unwritten

`WORLDGEN_FEATURES.md:115-171` specifies `tools/scatter.py` and a `data/scatter_rules.json`
schema (`cobblers.scatter_rules/1`) with an `ore` rule kind that replaces by host-rock tag.

**VERIFIED it does not exist:** there is no `tools/scatter.py` and no
`data/scatter_rules.json` in the repository; the only matches for "scatter" under `tools/`
are in `elder_trees.py` and `maze_forest.py`, which are unrelated. `WORLDGEN_FEATURES.md:99-113`
also assigns ores to WorldPainter's Underground Pockets layer (**VERIFIED** to work in
EXP-014, 202,287 fire-stone ore blocks placed), so there are two unbuilt routes, not one.

Two things have changed since that specification was written and neither is recorded there:

- Its stated blocker — *"it needs an NBT **writer**, and `tools/nbt.py` is read-only"*
  (`WORLDGEN_FEATURES.md:125-126`) — no longer decides the question. Every large block pass
  in this project is now generated `mcfunction` and re-run by `tools/reapply.py`
  (`tools/reapply.py:267-311`, steps R1-R16), at a scale of 1,647,987 commands in 1,005
  functions for the Rift skin alone (`docs/STATE.md` "The Rift overhaul"). An ore pass could
  be functions, not NBT.
- Anything written by hand into the world is erased by a re-export, so an ore pass has to be
  a `data/` record with a `reapply.py` step, exactly like Habitat Blocks and traders, or it
  will be lost on the next export. `reapply.py prepare` now fails closed on a pack with no
  step (`docs/STATE.md`, 2026-09-23), so this cannot be added quietly.

**This is a sequencing dependency, not just a gap.** If the scatter pass lands, stones stop
being reward-worthy and become a mining chore; if reward caches land first, they are the
economy. The two cannot be designed independently.

### 3. How much of the roster this touches, measured

Measured against `data/spawns.json` on 2026-09-23 (1,468 `species` rows across the `entries`
and `subregions` blocks):

| Measure | Value |
| --- | ---: |
| Roster rows carrying `"eligibility_reason": "player evolution (non-level method)"`, all at `weight: 0` | **168** (84 in `entries`, 84 mirrored in `subregions`) |
| Distinct species behind those rows | **60** |
| Distinct families behind those rows | **54** |
| Of those families, gated on one of the ten **evolution stones** | **20** |
| Gated on some other **item** (Link Cable, held item, apple, teacup) | **10** |
| Gated on friendship, a move, time, gender, nature or walking — *unaffected by this gap* | **24** |

So **30 of the 54 families whose last stage the wild will never produce are waiting on an
item, and 20 of those on a stone that does not exist in this world.**

**The stone-gated twenty** (grouped by the stone; the family id is the roster's `family`
field, the blocked form in brackets):

| Stone | Families |
| --- | --- |
| Water Stone | `poliwag` [poliwrath], `staryu` [starmie], `shellder` [cloyster], `lotad` [ludicolo] |
| Sun Stone | `oddish` [bellossom], `petilil` [lilligant], `cottonee` [whimsicott], `helioptile` [heliolisk] |
| Shiny Stone | `minccino` [cinccino], `budew` [roserade], `togepi` [togekiss] |
| Ice Stone | `vulpix` (Alolan) [ninetales alolan], `crabrawler` [crabominable] |
| Dusk Stone | `murkrow` [honchkrow], `misdreavus` [mismagius] |
| Moon Stone | `nidoranf` [nidoqueen], `nidoranm` [nidoking] |
| Leaf Stone | `seedot` [shiftry] |
| Dawn Stone | `snorunt` [froslass] |
| Thunder Stone | `pichu` [raichu] |
| **Fire Stone** | **none** |

**The other ten:** `roggenrola` [gigalith], `gastly` [gengar], `phantump` [trevenant],
`karrablast` [escavalier], `shelmet` [accelgor] — all Link Cable; `magby` [magmortar] —
Magmarizer plus Link Cable; `sneasel` [weavile] — Razor Claw; `gligar` [gliscor] — Razor
Fang; `applin` [flapple, appletun] — Tart and Sweet Apple; `poltchageist` [sinistcha] — a
teacup item.

Three qualifications, all of which matter:

1. **The count of rows and families is VERIFIED from `data/spawns.json`. The mapping from a
   family to the item that gates it is ASSUMED** — it is mainline-Pokémon knowledge, not
   read out of Cobblemon 1.8.0's own `data/cobblemon/species/**.json` `evolutions` blocks.
   The reward inventory raised the same caveat and it is still open. `bergmite` [avalugg]
   and `rowlet` [decidueye] carry the label for reasons this note cannot explain and are the
   clearest test cases for the jar read.
2. **54 is a floor, not a total.** The roster's own label is inconsistent for three-stage
   families whose *last* step is item-gated: `machamp` is labelled
   `"evolution requires level 28; band begins at 22"` (`data/spawns.json:3293-3301`) and
   `gallade` `"evolution requires level 20; band begins at 10"` (`data/spawns.json:8519-8527`),
   although the blocking step is a trade and a Dawn Stone respectively. The generator appears
   to classify on a level threshold found somewhere in the chain rather than on the final
   step. Both are already `weight: 0`, so nothing spawns wrongly — but the *diagnosis* in the
   data is wrong, and any tool that counts item-gated families off `eligibility_reason` will
   undercount.
3. **`eevee` does not appear in `data/spawns.json` at all** (reward inventory section 2), so
   the eeveelution stone economy has no consumer either. Together with the empty Fire Stone
   row above, two of the stones that *would* be the easiest to justify placing have nothing
   to evolve.

### 4. What the stones' other sources do and do not settle

The blunt claim "these families cannot be completed at all" is **not** established, and the
repo's own jar scan is why:

- **VERIFIED (this repo's scan of the installed jars and datapacks)** every one of the ten
  stones is classified `loot and crafting`, with **6 recipes** and 3 to 8 loot tables each
  (`docs/world-building/WORLDGEN_FEATURES_TABLE.md:16, 30, 32, 42, 44, 49, 66, 68, 71, 73`).
  The recipe figure is a **floor**: `tools/worldgen_features.py:186` truncates both lists
  (`[:6]` and `[:8]`).
- **UNKNOWN** what those recipes take as input. If a stone is craftable from materials that
  exist in this world, there is no gap at all, only an inconvenience; if the input is the ore
  or a shard the ore drops, the gap is total. **This single question decides whether GAP 1 is
  a blocker or a note**, and it is one `zipfile` read of
  `Cobblemon-fabric-1.8.0+1.21.1.jar` `data/cobblemon/recipe/**`.
- **The loot-table column is weaker than it looks.** `WORLDGEN_FEATURES.md:50-53` already
  records that the loot tables carrying stones are *"mostly structure chests, trainer rewards
  (`rctmod:generic/*/nature`) and raid dens"*. **VERIFIED** structures do not generate in a
  WorldPainter export any more than features do, so structure chests are absent unless
  placed; **VERIFIED** raid dens are removed from the 1.8 overlay as incompatible
  (`modpack/manifest/overlay.json:527-535`). That leaves rctmod trainer rewards as the only
  plausible live source — and **VERIFIED** 0 trainers are placed (`docs/STATE.md` "Campaign
  content"). So on today's world the chain is: ore absent, structures absent, raids removed,
  trainers unplaced.
- **VERIFIED** the campaign is actively removing the remaining circulation: every donor
  building is placed with `clear_loot: true` (`data/placements.json:8607-8609`) and the
  trader stock policy withholds whole categories (`data/traders.json:227-245`).

### 5. What has to be read or run before this is designed around

Experiment candidates, in the order that collapses the most uncertainty per unit of work:

1. **Read the jar.** For each of the 54 families, read `evolutions` out of
   `data/cobblemon/species/**.json` in `Cobblemon-fabric-1.8.0+1.21.1.jar` and record the
   `variant` and `requirements` of the blocking step. `tools/battle_sim.py:116-148` already
   opens the jar and normalises species names; `tools/battle_sim.py:274-300` already walks
   the `evolutions` block and distinguishes `level_up` from `item_interact` and `trade`.
   This turns every ASSUMED mapping above into VERIFIED and fixes the two mislabelled rows.
2. **Read the recipes.** `data/cobblemon/recipe/**` for the ten stones, plus Link Cable,
   Razor Claw, Razor Fang, Magmarizer, Tart/Sweet Apple. Decides section 4.
3. **Read the loot tables.** Which of the 3-8 tables per stone belong to a structure that is
   placed, a trainer that could be placed, or a mob that exists in this pack.
4. **Only then** decide the mechanism: scatter pass, placed caches, trainer reward tables,
   trader stock, or a mix. That decision is entangled with the reward-delivery decision in
   `docs/decisions/ADR-002-reward-delivery-mechanism.md` and should not be taken before it.

Nothing above should be turned into content. No stone has been given to a player in a
running game, and no id in this section has been resolved with `/give`.
