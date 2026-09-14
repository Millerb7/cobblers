# Structure data fallout: spawns, gym guidance, villagers, and what a town is

**Status: Part 2 of the blocker work, for review.** It builds on EXP-013:
- **D** (player session, 2026-09-13): a pasted village square does not satisfy
  `#minecraft:village`; a natural village does.
- **E:** trainer spawners work in pasted and command-set builds.

Nothing here is built. Spawn changes, blocks and villagers are proposals, and the town-spawn
mechanism has one experiment to run (EXP-016, section 1.3).

## 1. The 318 village-gated spawn entries (89 species)

### 1.1 Test first: can the species live in region and route tables instead?

**Mostly, yes, and most of them already do.** For every species with a village-gated entry,
`rehome.py` checked whether it also has spawn entries that need no structure at all, and
whether those entries' biomes are painted anywhere in the region plan (`data/regions.json`).

| Result | Species | What it means |
| --- | ---: | --- |
| Already spawns somewhere in the plan without a village | **85** | The village entries only add density inside villages. Losing them loses nothing that the route and region tables do not already offer. 72 of them spawn in all 13 land regions that have biomes |
| No home without a village, but their village entries' biomes are painted in the plan | **4** | Sinistea, Polteageist, Poltchageist, Sinistcha (section 2) |
| No plausible home in the current plan | **0** | |

**Nothing needs a system replacement to keep a species obtainable.** What needs a mechanism
is town *character*: which Pokémon appear in towns and which stay out.

**Counting notes:**
- The 318 unique entries appear 501 times per species, because herd and alpha files name
  several species.
- The Hatenna line is caught by the name match through `bca:village/witch_hut`, which is a
  swamp hut, not a village. It already spawns in one planned region.

### 1.2 What the entries actually require

Beyond the structure:
- 84 of the 89 species' village entries also set sky-light bounds;
- a few add `timeRange`, `isRaining`, `isPokeSnack`, `canSeeSky`, `minY` or `dimensions`;
- nearly all are grounded, with 2 fishing and 2 surface.

None needs anything a town could not provide except the structure itself.

### 1.3 The cheap mechanism: gate town Pokémon on town ground, not on structure data

Cobblemon spawn conditions can require blocks. The spawn files the server loads use two such
conditions:
- `neededBaseBlocks`: the block the Pokémon spawns on. Cobblemon's own `natural` preset
  requires `#cobblemon:natural` and excludes farmland.
- `neededNearbyBlocks`: blocks near the spawn point. Corsola needs `#minecraft:corals`, and the
  server's `config/cobblemon/main.json` sets the search range to `maxNearbyBlocksHorizontalRange
  4`, `maxNearbyBlocksVerticalRange 2`.

**That gives towns a spawn identity without structure data:**

| Need | Mechanism |
| --- | --- |
| Town Pokémon appear in towns | A campaign datapack copies each village entry with its structure condition replaced by `neededBaseBlocks: ["#cobblers:town_ground"]`. That is a block tag of the paving and floor blocks towns are built from and wild terrain never uses (a Rechiseled or Moar Concrete path set, chosen when the town kit is) |
| Wild Pokémon stay out of towns | Already mostly true. Every entry with the `natural` preset needs `#cobblemon:natural` underfoot, and town paving is not natural. The 788 entries that exclude villages (`wild`, `urban` presets) get `anticondition: {neededBaseBlocks: ["#cobblers:town_ground"]}` in the same datapack, where they do not already use `natural` |
| Indoor Pokémon (the tea lines, section 2) | the same gate, with `canSeeSky: false`, which the originals already use |
| A hand-set spot for one special Pokémon | a Habitat Block inside a building, if EXP-016 shows the base-block gate is too coarse |

**Why this is the cheap option:**
- It is one datapack of spawn overrides.
- It needs no custom biome, no painting, and no per-town Habitat Blocks.
- It keeps working when a town grows, because the gate follows the blocks.

**EXP-016 (proposed, one player, about 10 minutes, same pattern as EXP-013 D):**
- **Build:** a probe entry gated on `neededBaseBlocks: ["#cobblers:town_ground"]` and a second
  probe with the matching anticondition. Place a 20×20 patch of the chosen paving next to grass.
- **Pass:** `/checkspawn` lists the first probe only on the paving and the second only on the
  grass.
- **Also check:** whether a `natural`-preset species disappears from the paving list.

## 2. Sinistea and Poltchageist: where they go

**What the pack intends, read from their entries:**

| Line | Village entries allow | Village entries exclude | Other conditions |
| --- | --- | --- | --- |
| Sinistea → Polteageist | floral, magical, mountain, plains, snowy, spooky, taiga, tundra biomes | arid, bamboo, **cherry blossom**, island, jungle, ocean, swamp, thermal, volcanic | day: `canSeeSky false` (indoors); night: outdoors; `minY 62`; Polteageist also uses the `mansion_dining` preset |
| Poltchageist → Sinistcha | arid, bamboo, **cherry blossom**, forest, island, jungle, ocean, swamp, thermal, volcanic | magical, spooky | the same day-indoors, night-outdoors split; the rare "artisan" and "masterpiece" forms carry about 1% of the weight |

**Cobbleverse splits them on purpose:** Sinistea is the western teapot of old houses, and
Poltchageist the matcha of cherry and bamboo country.

**Proposal:**

| Line | Home | Why | How |
| --- | --- | --- | --- |
| **Poltchageist → Sinistcha** | **Stillwater Basin** (hub; primary biome cherry grove) | the only cherry-blossom region in the plan, and a hub that will hold a town. A tea house there is the natural set piece | the town-ground gate from 1.3, keeping `canSeeSky false` by day, biome-limited to the basin's cherry grove. The rare authenticity forms keep their original weights |
| **Sinistea → Polteageist** | **Eastern Downs** (hub; plains), the older houses of its town | plains is in its allowed set and cherry is excluded. A hub town with old buildings matches the teapot's story and keeps it off the cherry basin | the same gate by day indoors, biome-limited to plains |

**Two things are not settled here:**
- Which town in each region: that needs the town list.
- The exact block tag: that waits for the town kit.

**Both lines stay uncommon** as in the source, with no extra rarity.

## 3. Finding gyms without an exploration map

**What is broken:**
- Cobbleverse's `gym_map` and LumyMon's Kanto cartographer trades use
  `minecraft:exploration_map`, which finds nothing at a pasted gym (EXP-013 F).
- LumyMon's gym-locator and legendary-radar items are closed source. Assume they fail the same
  way.

**Proposal: point at fixed coordinates, which data can do in 1.21.1**

| Item | How | Where it comes from |
| --- | --- | --- |
| **Gym compass** | a `minecraft:compass` with the `minecraft:lodestone_tracker` component: `{target: {dimension: "minecraft:overworld", pos: [x, y, z]}, tracked: false}`. It points at the stored position without a lodestone block | a datapack override of `cobbleverse:gym_map` (same loot table id, so every drop and trade that rolls it gives the compass), with `minecraft:set_components` and a per-gym `minecraft:set_name` |
| **Gym map** (optional) | a `minecraft:filled_map` with a `minecraft:map_decorations` component marking the gym, added the same way | same loot tables |
| **Cartographer trades** | LumyMon's `data/lumymon/trades/kanto_cartographer.json` is datapack JSON. Override it so each gym's trade gives that gym's compass | datapack override |
| **Travel** | a Waystone at each gym town; Waystones is already in the pack | placed with the town |

**Coordinates stay in one place:** they come from the placement data (`placements.json`,
Step 3), and a small generator writes the loot tables. Nobody types a coordinate twice.

**Not verified:**
- that a loot table can set `lodestone_tracker` and `map_decorations` with
  `set_components` in 1.21.1;
- that the decorations draw on a map whose area was never explored.

**EXP-018 (proposed, headless):**
1. `loot give` the overridden table.
2. `data get` the item's components.
3. One look in-game that the needle points at the gym.

**Gyms in the Nether and End** (Blaine, the League) generate normally, so Cobbleverse's own
maps and locators can keep working there. EXP-013 F's natural controls support that; it was
not tested in those dimensions.

## 4. Villagers in built towns (rolled trades)

Vanilla village life reads **points of interest**: beds, job-site blocks, bells. It does not
read structure data. Rows marked **verified** were run on this server (EXP-019, headless, in a
plot built by command with no village structure). The rest is vanilla 1.21 behaviour, not tested
here.

| Mechanic | In a built town | Needs |
| --- | --- | --- |
| Villagers exist | **no, never on their own.** Only generation, breeding, curing zombie villagers or spawn eggs create them | **hand placement** |
| Picking a profession | **verified:** three unemployed villagers became librarian, farmer and toolsmith, one per job-site block, within minutes | job-site blocks in buildings |
| Trades | **verified rolled offers** (for example, 20 wheat → 1 emerald). Rolled by the game per villager and level, per the decision on record: no authored trade tables. Cartographers roll explorer-map trades; with no structure to find, vanilla drops those offers, so a cartographer has fewer trades (not tested) | leave cartography tables out of towns, or accept thin cartographers |
| Home and meeting point | **verified:** the villager's memory held its bed as `home` and the bell as `meeting_point` | beds and a bell |
| Levelling trades | works through trading | players |
| Breeding and repopulation | **verified:** a baby was born beside the spare beds within minutes (villagers carried bread) | 1–2 spare beds per town |
| Iron golems | works: villagers under threat summon them | nothing extra |
| Raids | works: Raid Omen triggers inside the POI "village" area. A town can be raided. Note that pasted pillager outposts have no structure data, so they spawn no pillagers; patrols still spawn naturally | nothing extra |
| Wandering trader | works: spawns near players, prefers the bell | a bell |
| RCT trainer association NPC | works: RCT's config spawns it near "at least 3 occupied beds and a village center", or near any player with a trainer card | beds and a bell |

**How many villagers:**

| Settlement | Villagers placed | Why |
| --- | ---: | --- |
| Gym town (assumed 8) | 4–6 each | enough rolled professions for a useful market; breeding fills the rest |
| Route settlement | 0–2 | flavour |
| **Total** | **about 40–50** | |

**How to place them:**
- **Place them unemployed.** Summon villagers or use eggs, next to the job sites. Rolled
  professions then follow the blocks the builder placed, so the builder chooses what a town
  sells without writing any trade.
- **Protect them without making them invulnerable:** `PersistenceRequired`, and villagers kept
  inside buildings.

**Still needs a player:**
- a raid in a built town;
- iron golem spawning;
- the RCT trainer-association NPC near beds and a bell.

None of these blocks the town model.

## 5. What a town is in the data model

**A town is a placement group: an authored record that owns a set of placements and a set of
rules.** It is not a Minecraft structure, and it is not a region.

| It is not… | Because |
| --- | --- |
| a structure | pasted builds carry no structure data (EXP-013 A), and nothing may depend on structure data (D, F) |
| a region | regions are terrain and climate areas with biome bands. A town sits inside one region and must not change its biomes |
| a biome | a custom town biome would work for spawns but means painting biomes per town. The town-ground gate (1.3) gets the same result without it |

**What a town record owns** (proposed `data/towns.json`, not written until the town list is
authored):

| Field | Holds |
| --- | --- |
| `id`, `name`, `region` | identity and host region |
| `extent` | polygon or bounds, for the validator and the concealment and sightline checks |
| `placements` | ids into `placements.json`: the builds pasted as templates at an explicit Y |
| `ground_tag` | the block tag that makes a spawn a town spawn (`#cobblers:town_ground`, or a per-town tag if towns need different Pokémon) |
| `spawn_overrides` | which town-gated entries apply here, e.g. the tea lines in their two towns |
| `gym` | trainer id(s) and spawner position. A spawner works with its `TrainerIds` and redstone power (EXP-013 E) |
| `villagers` | count and job-site blocks placed (rolled trades) |
| `beds_spare`, `bell` | village-life requirements |
| `waystone` | position |
| `guidance` | the gym compass and map loot entries generated from the gym position |

**What the game knows about a town:**
- the blocks: paving (spawns), beds, bells and job sites (villagers), spawner blocks
  (trainers);
- the datapack rules we write.

Nothing else. Every later town decision is about those blocks and rules.

## Appendix: the 89 species

Generated from the loaded spawn files by `rehome.py` against `data/regions.json`.
"Other spawn entries" counts entries with no structure condition.

| Species | Village-gated entries (buckets) | Other spawn entries | Planned regions where it already spawns without a village | Action |
|---|---|---:|---|---|
| Poltchageist | 16 (boss 4, uncommon 12) | 0 | **none** | **re-home (section 2)** |
| Polteageist | 18 (boss 8, uncommon 10) | 0 | **none** | **re-home (section 2)** |
| Sinistcha | 20 (boss 8, uncommon 12) | 0 | **none** | **re-home (section 2)** |
| Sinistea | 14 (boss 4, uncommon 10) | 0 | **none** | **re-home (section 2)** |
| Arcanine | 5 (boss 2, uncommon 3) | 4 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Audino | 3 (boss 2, rare 1) | 9 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Banette | 4 (boss 2, uncommon 2) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Blissey | 5 (boss 2, rare 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Boltund | 5 (boss 2, common 3) | 4 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Burmy | 1 (common 1) | 6 | Eastern Downs, Lakeshore Vale, Leeward Plateau, Northern Range, Stillwater Basin, Windward Coast | keep; town-ground gate optional |
| Chansey | 4 (boss 1, rare 3) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Cinccino | 5 (boss 2, common 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Conkeldurr | 5 (boss 2, common 3) | 4 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Dachsbun | 5 (boss 2, common 3) | 4 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Delcatty | 8 (boss 4, common 4) | 12 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Drowzee | 3 (boss 1, common 2) | 2 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Eevee | 4 (boss 1, uncommon 3) | 24 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Electrode | 5 (boss 2, common 3) | 12 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Espeon | 5 (boss 2, uncommon 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Espurr | 8 (boss 2, common 6) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Fidough | 4 (boss 1, common 3) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Flareon | 5 (boss 2, uncommon 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Furfrou | 4 (boss 2, common 2) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Gallade | 5 (boss 2, rare 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Garbodor | 5 (boss 2, common 3) | 4 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Gardevoir | 5 (boss 2, rare 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Glaceon | 5 (boss 2, uncommon 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Glameow | 6 (boss 2, common 4) | 4 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Granbull | 5 (boss 2, common 3) | 4 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Grimer | 12 (boss 2, common 4, uncommon 6) | 16 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Growlithe | 4 (boss 1, uncommon 3) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Gurdurr | 4 (boss 1, common 3) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Happiny | 4 (boss 1, rare 3) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Hatenna | 1 (common 1) | 3 | Windward Coast | keep; town-ground gate optional; gated entry is the witch hut |
| Hatterene | 1 (common 1) | 3 | Windward Coast | keep; town-ground gate optional; gated entry is the witch hut |
| Hattrem | 1 (common 1) | 3 | Windward Coast | keep; town-ground gate optional; gated entry is the witch hut |
| Herdier | 4 (boss 1, common 3) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Hypno | 4 (boss 2, common 2) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Indeedee | 3 (boss 2, uncommon 1) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Jolteon | 5 (boss 2, uncommon 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Jynx | 5 (boss 2, uncommon 3) | 4 | Glacier Valley, Northern Isles, Northern Range, sea | keep; town-ground gate optional |
| Kirlia | 4 (boss 1, rare 3) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Klefki | 4 (boss 2, uncommon 2) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Koffing | 4 (boss 1, common 3) | 12 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Leafeon | 5 (boss 2, uncommon 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Liepard | 9 (boss 4, common 5) | 12 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Lillipup | 4 (boss 1, common 3) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Mabosstiff | 5 (boss 2, common 3) | 4 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Maschiff | 4 (boss 1, common 3) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Maushold | 9 (boss 4, common 5) | 21 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Meowstic | 12 (boss 4, common 8) | 10 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Meowth | 11 (boss 3, common 8) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Mimejr | 8 (boss 2, uncommon 6) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Minccino | 4 (boss 1, common 3) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Mothim | 1 (common 1) | 2 | Eastern Downs, Lakeshore Vale, Leeward Plateau, Northern Range, Stillwater Basin, Windward Coast | keep; town-ground gate optional |
| Mrmime | 9 (boss 3, uncommon 6) | 7 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Mrrime | 5 (boss 2, uncommon 3) | 4 | Glacier Valley, Northern Isles, Northern Range, sea | keep; town-ground gate optional |
| Muk | 14 (boss 4, common 4, uncommon 6) | 20 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Munna | 3 (boss 1, common 2) | 2 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Musharna | 4 (boss 2, common 2) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Perrserker | 4 (boss 2, common 2) | 3 | Glacier Valley, Northern Isles, Northern Range, Rim Uplands, sea, Windward Coast | keep; town-ground gate optional |
| Persian | 10 (boss 4, common 6) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Pidove | 4 (boss 1, common 3) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Pikachu | 2 (uncommon 2) | 6 | Eastern Downs, Jungle Isle, Lakeshore Vale, Northern Isles, Northern Range, Southern Isles, Stillwater Basin, Strand Flats, Windward Coast | keep; town-ground gate optional |
| Purrloin | 7 (boss 2, common 5) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Purugly | 8 (boss 4, common 4) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Ralts | 4 (boss 1, rare 3) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Scrafty | 5 (boss 2, common 3) | 8 | Ember Highlands, Leeward Plateau | keep; town-ground gate optional |
| Scraggy | 4 (boss 1, common 3) | 6 | Ember Highlands, Leeward Plateau | keep; town-ground gate optional |
| Shuppet | 4 (boss 1, uncommon 3) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Skitty | 6 (boss 2, common 4) | 9 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Smeargle | 4 (boss 2, rare 2) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Smoochum | 4 (boss 1, uncommon 3) | 3 | Glacier Valley, Northern Isles, Northern Range, sea | keep; town-ground gate optional |
| Snubbull | 4 (boss 1, common 3) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Squawkabilly | 17 (boss 8, common 9) | 48 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Stoutland | 5 (boss 2, common 3) | 4 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Sylveon | 5 (boss 2, uncommon 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Tandemaus | 4 (boss 1, common 3) | 9 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Timburr | 4 (boss 1, common 3) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Tranquill | 4 (boss 1, common 3) | 6 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Trubbish | 4 (boss 1, common 3) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Umbreon | 5 (boss 2, uncommon 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Unfezant | 5 (boss 2, common 3) | 8 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Vaporeon | 5 (boss 2, uncommon 3) | 12 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Vivillon | 5 (boss 2, common 3) | 84 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Voltorb | 4 (boss 1, common 3) | 9 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Weezing | 5 (boss 2, common 3) | 16 | all 13 biome regions and the sea | keep; town-ground gate optional |
| Wormadam | 1 (common 1) | 6 | Eastern Downs, Lakeshore Vale, Leeward Plateau, Northern Range, Stillwater Basin, Windward Coast | keep; town-ground gate optional |
| Yamper | 4 (boss 1, common 3) | 3 | all 13 biome regions and the sea | keep; town-ground gate optional |
