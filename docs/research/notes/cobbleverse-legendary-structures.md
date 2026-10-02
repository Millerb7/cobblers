# Cobbleverse's legendary structures: what ships, what travels when pasted, and what we would author instead

**Answered for:** Cobblemon **1.8.0**+1.21.1 Fabric (the server's runtime) against the
**Cobbleverse snapshot consistent with release 1.7.42**, 2026-10-01.

**Purpose.** The main session is pasting **one** Cobbleverse legendary structure onto a
disposable world to see whether the altar, the command blocks and the summoning still work.
This note is the inventory to act on either outcome.

## 0. Method, and what could not be read

- **No Bash tool in this session.** The attempt was refused verbatim: *"Error: No such tool
  available: Bash. Bash is disabled for this session, in subagents as well as here."* Nothing
  was run; everything below is Read/Grep/WebFetch. `git rev-parse HEAD` could not be executed.
- **NOT READ — the mod jars.** `base-pack/cobbleverse/mods/` does not exist on this machine, so
  Legendary Monuments' and LumyMon's code and registered structure JSON were not read here.
- **NOT READ — the datapack zips.** `COBBLEVERSE-DP-v31.zip` and the Lumyverse datapacks are
  gitignored (no-redistribution), so no `.nbt` was opened in this session.
- **NOT READ — the `.nbt` paths.** No tracked file in this repo records the zip-internal or
  jar-internal path of any legendary template. What is recorded is the **structure id** and the
  **source archive** (`data/structures.json` `source`). That the id resolves to
  `data/<namespace>/structure/<path>.nbt` is Minecraft 1.21 convention, **ASSUMED**, not read.
- **LumyMon is closed source** (VERIFIED: `docs/research/COBBLEVERSE_COMPATIBILITY.md:244`,
  `docs/world-building/STRUCTURE_DATA_FALLOUT.md:104`). Every claim about what a
  `lumymon:*_altar` block *does* is therefore inference or an unversioned wiki, never source.
- Everything below with a `path:line` was read in this session from the tracked repo; the
  earlier audits it quotes did read the jars and zips, and they are cited as such.

## 1. What Cobbleverse actually ships (installed, loaded)

**20 LEGENDARY-class structures** are installed. VERIFIED from `data/structures.json` (the
per-structure classification record, one entry each) and the summary tables in
`docs/world-building/STRUCTURE_INVENTORY.md:121-144` and
`docs/world-building/STRUCTURE_INVENTORY_TABLE.md:208-260`. Class counts:
`STRUCTURE_INVENTORY.md:311` — 5 overworld, 5 Nether/End, 7 that never generate, plus the
towers and cocoon.

| # | Structure id | Origin archive | Legendary | Generates in | Footprint | Functional blocks recorded in `data/structures.json` `carries` |
|---|---|---|---|---|---|---|
| 1 | `cobbleverse:legendary/articuno` | COBBLEVERSE-DP-v31.zip | Articuno | overworld `snowy_plains` | 20·74·22 | `lumymon:articuno_altar` (`:5633`) |
| 2 | `cobbleverse:legendary/zapdos` | COBBLEVERSE-DP-v31.zip | Zapdos | overworld `stony_shore` | 31·66·29 | `lumymon:zapdos_altar` (`:5719`) |
| 3 | `cobbleverse:legendary/moltres` | COBBLEVERSE-DP-v31.zip | Moltres | **Nether** | 31·64·34 | `lumymon:moltres_altar` (`:5675`) |
| 4 | `cobbleverse:mythical/mew` | COBBLEVERSE-DP-v31.zip | Mew | overworld `jungle` | 37·25·39 | `lumymon:mew_shrine`, `cobblefurnies:statue_ancient`, `cobblemon:gilded_chest`, `cobblemon:gimmighoul_chest`; signals `advancement_gate`, `command_blocks`, `treasure`; commands `execute`, `fill`, `tellraw` (`:5866-5887`) |
| 5 | `cobbleverse:crown_spire` | COBBLEVERSE-DP-v31.zip | Glastrier, Calyrex | overworld `snowy_plains` | 41·38·49 | `lumymon:summon_trigger` (`:5260`) |
| 6 | `cobbleverse:crown_cemetery` | COBBLEVERSE-DP-v31.zip | Spectrier, Calyrex | overworld `old_growth_pine_taiga` | 45·24·47 | `lumymon:summon_trigger`, `lumymon:calyrex_statue`, `lumymon:summon_anchor` (`:5208-5210`) |
| 7 | `cobbleverse:dawn_tower` | COBBLEVERSE-DP-v31.zip | Necrozma (Dawn Wings) | **End** | 46·90·45 | signal `command_blocks`, command `pokespawnat` (`:5301`, `:5311`) |
| 8 | `cobbleverse:dusk_tower` | COBBLEVERSE-DP-v31.zip | Necrozma (Dusk Mane) | **End** | 46·90·45 | signal `command_blocks`, command `pokespawnat` (`:5353`, `:5363`) |
| 9 | `legendarymonuments:eternatus_cocoon` | LegendaryMonuments-Cobbleverse.jar | Eternatus | **End** | 47·30·47 | `legendarymonuments:eternatus_cocoon` block (`:6074-6076`) |
| 10 | `legendarymonuments:firescourge_shrine` | same jar | Chi-Yu | **Nether** `nether_wastes` | 21·15·27 | `legendarymonuments:firescourge_shrine` block (`:6114-6116`) |
| 11 | `legendarymonuments:grasswither_shrine` | same jar | Wo-Chien | **Nether** `warped_forest` | 21·22·27 | its own shrine block |
| 12 | `legendarymonuments:groundblight_shrine` | same jar | Ting-Lu | **Nether** `soul_sand_valley` | 21·18·27 | its own shrine block |
| 13 | `legendarymonuments:icerend_shrine` | same jar | Chien-Pao | **Nether** `basalt_deltas` | 21·16·33 | its own shrine block |
| 14 | `legendarymonuments:giratina_island` | same jar | Giratina | **Distortion World** dimension only | jigsaw, 42·43·38 start, depth 7 | `lumymon:giratina_altar`, `lumymon:summon_anchor` (`:6157-6158`) |
| 15 | `legendarymonuments:lake_acuity` | same jar | Uxie | **never** (biome tag only in the disabled Sinnoh pack) | jigsaw, 37·48·37 start | `lumymon:uxie_altar`, `lumymon:summon_anchor`, `legendarymonuments:pokemon_trial_spawner` (`:6318-6320`) |
| 16 | `legendarymonuments:lake_valor` | same jar | Azelf | **never** | jigsaw, 37·48·37 start | `lumymon:azelf_altar`, `summon_anchor`, `pokemon_trial_spawner` (`:6360-6362`) |
| 17 | `legendarymonuments:lake_verity` | same jar | Mesprit | **never** | jigsaw, 37·48·37 start | `lumymon:mesprit_altar`, `summon_anchor`, `pokemon_trial_spawner` (`:6402-6404`) |
| 18 | `legendarymonuments:stark_mountain` | same jar | Heatran | **never** | 120·90·137 | `cobblemon:gilded_chest`, loot `legendarymonuments:chests/stark_mountain`, RCT trainers `sinnoh_buck`, `team_galactic_charon` (`:6473-6491`) |
| 19 | `legendarymonuments:turnback_cave` | same jar | Giratina (the route to it) | **never** | jigsaw, 41·13·41 start, depth 7, up to 232 wide | 16 `legendarymonuments:pokemon_trial_spawner`, 28 vaults, loot `legendarymonuments:chests/turnback_cave_chest`, a distortion portal (`:6521-6536`; `STRUCTURE_INVENTORY.md:137`) |
| 20 | `legendarymonuments:distortion_portal` | same jar | — (portal to the Distortion World) | **never** | 5·2·5 | portal entity (`STRUCTURE_INVENTORY.md:138`) |

Not structures, but part of the same surface:

- **`cobbleverse:spawn_rayquaza`** — a loaded *function* that spawns a shiny level-100 Rayquaza
  at 0,70,0 in the End, scheduled by `end_dimension` (VERIFIED: `STRUCTURE_INVENTORY.md:362-363`).
- **`legendarymonuments:outskirt_stand`** — a merchant, classified NAMED not LEGENDARY
  (`STRUCTURE_INVENTORY.md:168`).
- **Disabled-pack structures, present in `datapacks/extra` but not loaded**: Johto's
  `cobbleverse:celebi_shrine` (Ilex, `lumymon:ilex_shrine` + a GS Ball), `bell_tower`,
  `whirl_island`; Hoenn's `*_temple`, `secret_garden`, `kyogre_temple`, `groudon_vulcano`,
  `sky_pillar`, `jirachi_structure`, `deoxys_meteorite`; Sinnoh's `newmoon_island`,
  `flower_paradise`, `split_decision_temple` and the rest (VERIFIED:
  `STRUCTURE_INVENTORY.md:354-356`). Three Sinnoh ones additionally need **Terralith** biomes,
  also disabled (`:358-360`). These are **donor template candidates only**; licence is the
  gate, not availability.
- **LumyMon's own templates**: `lumymon:temple_of_sinnoh`, 35·38·103, "contains pedestals,
  statues and 2 RCT spawners", marked REFERENCE ONLY (`STRUCTURE_CATALOG.md:102`).

**The 42 zero-weight spawn labels.** Cobbleverse's datapack has 42 spawn entries using 30
`cobbleverse:custom_spawn/<site>` biome ids, **every one with `"weight": 0`**, so none can ever
fire; they are labels for "where this legendary is found", not spawns (VERIFIED:
`STRUCTURE_INVENTORY.md:328-333`; the gap table in
`docs/world-building/BIOME_COVERAGE_MATRIX.md:134-140` lists the four shrine ones). **Nothing
tonight's test does can turn one of these into a spawn,** and nothing we paste needs to.

## 2. Blocks versus data: what travels when you paste one

### The precedent, stated exactly

- **Cobblemon reads structure starts to evaluate a `structures` spawn condition** — VERIFIED
  in source by the earlier audit: "Cobblemon 1.8.0 reads the structure starts of the spawn
  position's chunk", and on a hand-placed map those conditions **"never pass in exported chunks
  unless placement writes starts"** (`docs/world-building/STRUCTURE_INVENTORY.md:264`; mechanism
  verified in source, outcome inferred).
- **No paste method writes structure data.** VERIFIED by EXP-013 on a disposable world:
  `/place structure`, `/place jigsaw` and `/place template` "all left every chunk with empty
  `starts` and `References`"; `/locate`, `location_check` and the gym map ignored the builds,
  while natural controls passed (`STRUCTURE_INVENTORY.md:271-274`).
- **That is the mansion case.** The authored Gastly mansion is a hand-placed build
  (`data/placements.json:14672`, `docs/story/events/ROUTE1_GASTLY_MANSION.md`), and Cobblemon's
  ~110 mansion/illager-preset spawn entries are structure-gated (`STRUCTURE_INVENTORY.md:156`),
  so they do not apply inside it. "Explicit mansion spawn control" is still listed as an open
  need (`ROUTE1_GASTLY_MANSION.md:140`).

### Applied to the legendary sites, structure by structure

**The good news, and it is specific.** For every legendary structure, `data/structures.json`
records `depends_on_it.spawn_entries: 0` and `advancements: []` (checked at `:5616-5623` for
Articuno, `:6058-6065` for the cocoon, `:6465-6472` for Stark Mountain; the records are
uniform). **These structures carry no spawn presets to lose.** The mansion's loss does not
repeat here — what a paste loses at a shrine is *findability* and *terrain validation*, not
spawns.

| Part | Blocks (travels with any paste that copies block entities) | Data attached to the structure (does NOT travel) |
|---|---|---|
| `lumymon:*_altar` / `*_shrine` / `calyrex_statue` / `summon_trigger` / `summon_anchor` | **blocks** (and, if they are block entities, their NBT). Risk: whether an altar needs state written at *worldgen* time rather than at placement is **UNKNOWN** — LumyMon is closed source | the mod's own registered-structure JSON, its biome tag, its terrain validator, its spacing/separation set |
| `legendarymonuments:*_shrine`, `eternatus_cocoon` | **blocks** | as above |
| `legendarymonuments:pokemon_trial_spawner` (lakes 15-17, turnback 19) | **block + block entity**; vanilla trial-spawner config lives in the block entity, so it travels — **ASSUMED** by analogy with vanilla, not tested for this mod's subclass | nothing structure-side |
| Command blocks (Mew 4, the Necrozma towers 7-8) | **blocks**, with their command strings. They need `enable-command-block=true`, and they "run only from their own trigger, never on placement" (VERIFIED for Brock, EXP-013 C, `STRUCTURE_INVENTORY.md:269`) | — but Mew's chain **gates on Cobbleverse's own `defeat_champion_blue` advancement, which our progression never grants** (VERIFIED: `STRUCTURE_INVENTORY.md:128`, `STRUCTURE_DECISIONS.md:222`). The advancement is pack data, present; the *grant* is the thing we do not produce |
| Chests and loot (Mew 4, Stark 18, Turnback 19) | the **chest block entity with its `LootTable` NBT**, so it rolls on first open. **ASSUMED** (vanilla behaviour; not tested for these templates) | the loot table itself is datapack data and is loaded, so it resolves |
| RCT trainer spawners (Stark 18) | **block entity + `TrainerIds` is enough**, no structure start needed — VERIFIED in source, and EXP-013 E observed spawners working in pasted and command-set builds (`STRUCTURE_INVENTORY.md:265`, `STRUCTURE_DATA_FALLOUT.md:6`) | nothing |
| Jigsaw structures (14-17, 19) | only the **start piece** of a raw `/place template`; the assembly is worldgen (depth 7, up to 232 wide). `/place structure` assembles but **misplaces jigsaws on painted terrain — 20-54 blocks below the painted surface** (VERIFIED: `STRUCTURE_INVENTORY.md:277-279`) | the template pools, processors and jigsaw resolution |
| Finding it: LumyMon radars, `gym_map`, exploration maps, `/locate`, `location_check` | — | **all of it.** Radars are closed source and "probably do not find hand-placed builds", not verified (`STRUCTURE_INVENTORY.md:267`); exploration maps and `/locate` verifiably will not match (`:266`, `:268`). Decision already taken: no replacement finder item; navigation is waystones plus Xaero markers (`STRUCTURE_DATA_FALLOUT.md:107-110`) |

### The one placement result we already have

`legendarymonuments:firescourge_shrine` was **already pasted successfully on this runtime**:
Minecraft 1.21.1, Fabric 0.19.5, **Cobblemon 1.8.0**, disposable flat world, 2026-09-09 —
"PASS via raw `/place template`", rotation 90° PASS, mirror `front_back` PASS, "Functional
elements UNKNOWN", editable "WITH CARE" (VERIFIED: `docs/world-building/STRUCTURE_WORKFLOW.md:81`,
`:90`). And, load-bearing for tonight: *"The registered Firescourge placement resolved but
rejected the flat test site in its terrain validator, while direct raw-template placement
passed. This demonstrates why registered and raw placement must be tested separately."*
(`:95-98`).

**So the test's unknown is narrow and worth running:** blocks and rotation already pass; what
has never been seen is whether an altar/shrine block **functions** after a raw paste.

## 3. How the summoning is triggered, as the pack ships it

**VERIFIED (repo, read from the templates by the earlier audit):**

- Mew's temple runs **command blocks** that `execute`/`fill`/`tellraw`, gated on
  `defeat_champion_blue` (`data/structures.json:5866-5887`, `STRUCTURE_INVENTORY.md:128`).
- The Necrozma towers run `pokespawnat … necrozma … level=80` from command blocks at the top of
  a 90-block tower (`STRUCTURE_INVENTORY.md:131`, `data/structures.json:5311`).
- The lakes and Giratina's island pair an altar with a **`lumymon:summon_anchor`**, and the
  lakes add a `legendarymonuments:pokemon_trial_spawner` (`data/structures.json:6157-6158`,
  `:6318-6320`).
- The crown sites pair a **`lumymon:summon_trigger`** with a statue and an anchor
  (`:5208-5210`, `:5260`).

**ASSUMED (no source; this is the shape, not the schema):**

- `docs/world-building/STRUCTURE_DECISIONS.md:216-217`: "the block consumes an activation item,
  checks a summon anchor nearby and spawns the Pokémon at level 70-90. The gate is therefore
  the item, not the place." **This sentence carries no citation in the repo** and LumyMon is
  closed source, so it is an inference about a closed-source block.
- The pack's own wiki, **unversioned**, corroborates the shape item-by-item
  (https://www.lumyverse.com/cobbleverse/how-to-catch-all-legendary-mythical-pokemon/, read
  2026-10-01): Mew — *"Place it in Mew's Altar to summon Mew"* with an **Origin Fossil**;
  Celebi — *"Press the button while holding the GS Ball near the shrine to summon Celebi"*;
  Ho-Oh — *"Use the Rainbow Wing there to summon Ho-oh"*; the Regis — craft a relic from the
  matching LumyMon type ore (Lvl 40-50); Regigigas — a Titan Relic and **all five Titans in the
  party** (Lvl 80+); the lake trio — *"Use the dropped reward item at the cave's altar to summon
  the Guardian"* (Lvl 70+); Giratina — a Red Chain at the altar (Lvl 75+); Heatran — a Magma
  Stone via the Stark Forge (Lvl 70+); Arceus — the Azure Flute with all 18 plates.
  It is unversioned and names **Terralith-style biomes we have disabled**, so it is evidence of
  intent, not of our install.
- **The same page does not mention Articuno, Zapdos, Moltres, the four Ruinous Pokémon,
  Calyrex/Glastrier/Spectrier, Necrozma or Eternatus at all** (checked 2026-10-01); it points
  those at a "spawn locations" page instead. So **how the Kanto birds' altars are triggered is
  UNKNOWN**, which matters because they are three of the five that generate in the overworld.
- Right-click as the interaction verb is **ASSUMED** everywhere except Celebi, where the wiki
  says a **button**. Never write an altar's interaction into our data until it is seen.

## 4. Which would suit this map, and where

Ranked. One line of reasoning each. Sites are from `data/landmarks.json` (ids read 2026-10-01)
and `docs/world-building/SETTLEMENTS.md:190-195`.

**Worth adopting**

1. **`cobbleverse:mythical/mew` → Jungle Isle ruins, (5160, 7463), 301², y120-134.** The
   landmark already exists for exactly this job — "overgrown ruins and a cache that reward the
   boat trip without adding a town" (`SETTLEMENTS.md:195`) — and the template's biome is
   `jungle`, which that isle is. The sea crossing makes finding it an event. **Cost:** its
   command-block chain gates on `defeat_champion_blue`, so the gate must be re-authored as ours
   (section 5), and 37·25·39 fits the site with room.
2. **`cobbleverse:crown_cemetery` → the Peak Pond old-growth spruce.** Biome match
   (`old_growth_pine_taiga`) against a stand described as "a cathedral of giant 2x2 spruce and
   pine over a dark mossy floor" (`docs/world-building/FOLIAGE.md:86`), and its brushable gravel
   loot (`STRUCTURE_DECISIONS.md:223`) makes the discovery itself the reward rather than a
   checklist tick. 45·24·47 needs a clearing; that is the one real cost.
3. **`cobbleverse:legendary/zapdos` → the windward cliffs / skerries band.** `stony_shore`, and
   at 66 blocks tall it is a silhouette seen from the sea long before it is reached — the
   "distance cue" the LEGENDARY placement rule already asks for (`STRUCTURE_INVENTORY.md:317`).
   Site not chosen; `WATER_SHAPE.md:43` describes the rock-and-stack coast it belongs on.
4. **`legendarymonuments:turnback_cave` → the Rift, as a vocabulary, not a paste.** Catalogued
   as "REFERENCE ONLY; substantial puzzle-layout vocabulary" (`STRUCTURE_CATALOG.md:101`), and
   its 16 trial spawners and 28 vaults are the shape the Rift wants. But it is a depth-7 jigsaw,
   so a raw paste yields one 41·13·41 start piece — adopt the ideas, not the file.

**Clutter, or blocked — do not adopt**

5. **`cobbleverse:legendary/articuno` at the Frostpeak shrine — blocked by arithmetic.** The
   story fit is perfect: "A shrine on the lone summit of the most remote corner of the
   mainland", 1,440 blocks from anything (`SETTLEMENTS.md:194`). But its pad is **y310**
   (`SETTLEMENTS.md:194`, `REEXPORT.md:18`) and the tower is **74 blocks tall**
   (`data/structures.json:5606`): 310 + 74 = 384, far above the 1.21.1 build ceiling. Either a
   lower site (the Glacial Tear trough, Regice's portal is y101 per
   `docs/mechanics/LEGENDARIES.md:23`) or not this template.
6. **`lake_acuity` / `lake_valor` / `lake_verity` — refuse.** We already author Uxie, Mesprit
   and Azelf ourselves as lake grottos (`docs/mechanics/LEGENDARIES.md:19-21`). Pasting these
   would give the same three legendaries two authors in two files, which is precisely the
   invisible collision `CLAUDE.md` and `data/id_authorship.json` exist to stop.
7. **`stark_mountain` — refuse.** 120·90·137 is a region, not a structure, and it ships two
   **Sinnoh** RCT trainers (`sinnoh_buck`, `team_galactic_charon`, `data/structures.json:6480-6483`)
   that have no place in a Kanto-series campaign.
8. **`giratina_island` + `distortion_portal` — refuse.** The island generates only in Legendary
   Monuments' own Distortion World dimension (`STRUCTURE_INVENTORY.md:144`); adopting it means
   adopting a dimension.
9. **`crown_spire` — skip if `crown_cemetery` is taken.** Both end at Calyrex; two sites for one
   legendary is the checklist feeling the owner wants to avoid.
10. **Moltres, the four Ruinous shrines, the cocoon, both Necrozma towers — leave where they
    are.** Already decided: the Nether and End are vanilla-generated and audited after pregen,
    so these keep their structure data and their finders
    (`STRUCTURE_INVENTORY.md:140-141`, `:320-321`; `DIMENSIONS_AND_BORDERS.md:317`).

## 5. What our own systems could carry instead

| Vessel the owner named | The existing mechanism that would place it | The existing mechanism that would gate it | State |
|---|---|---|---|
| **Dive caves** | `tools/legendaries.py`'s `lake_grotto` archetype: mouth in the lake bed, stone sleeve, flooded shaft and passage, a pool cut into the chamber floor, a dry air chamber (`docs/mechanics/LEGENDARIES.md:62-98`). Ground from `tools/ground.py`, never a world. Requires a `keep` zone in `data/water_shape.json` so the water export does not rewrite the bed (`:37-47`) | **blocks, not entity state**: a barrier partition opened by one advancement predicate on every line that can open a chamber, driven by one scheduled function every 20 ticks; per-player state is the advancement `cobblers:legendary/<id>/met`, declared in `data/progression.json` `quest_fields` (`LEGENDARIES.md:101-143`) | **built as data, run nowhere.** Three grottos emitted; Uxie blocked on one line of `data/water_shape.json` (`:37-47`, `:274`) |
| **Sky islands** | **No mechanism exists.** The nearest precedents are a donor paste at an explicit Y (`/place template` "lands where asked", VERIFIED `STRUCTURE_INVENTORY.md:279`) through `data/placements.json`, and Misty's gym, which Cobbleverse itself puts "on a floating island" (`STRUCTURE_INVENTORY.md:575`). But `tools/ground.py` is a **heightmap**: a floating island has no column ground, so every placement and audit tool's ground rule would have to be given an explicit Y instead | the same advancement gate would work; access (how a player gets up) has no mechanism in this repo | **research question** |
| **Strength caves** | `sealed_chamber`: a stone plug at a surface portal, a dry ladder shaft, a short adit, the chamber (`LEGENDARIES.md:79-82`) — four are emitted today | **No Strength mechanism exists.** VERIFIED: "None found. No record in `docs/research/` or `base-pack/inventory/`" (`docs/mechanics/WATER_MAP.md:272`); MoLang `has_learned` is listed there as an **ASSUMED** possibility only. The working substitute is the plug: rock until a qualified player stands on the portal, then open for ever (`LEGENDARIES.md:113-115`) | **the gate exists, the Strength verb does not** |
| **New shrines** | `tools/shrines.py` builds wayside shrines as one function each into `cobblers_shrines`, with a refusal-based clearance check against towns, legs, other packs' writes and the pending water export (`tools/shrines.py:1-37`). But the owner's brief for it was explicit: *"Small, local, believable, **not legendary shrines**"* (`data/shrines.json:3`). A **legendary** shrine is therefore a `data/placements.json` record plus a `data/legendaries.json` encounter, not a `shrines.json` kind | `data/progression.json` `quest_fields` + the advancement gate above; `tools/portals.py` already protects them (`min_from_legendary_mouth` = 120, `docs/world-building/PORTALS.md:95`) | **both halves exist; no legendary shrine is authored** |
| (also available) **a named local spawn** | `data/habitat_blocks.json` + Cobblemon's Habitat Block — 1.8's spawn-control block, and it needs no structure data | its own block placement | in use elsewhere |
| (also available) **placing the Pokémon itself** | **RCON, never a pack**: `reapply.py` **R14L** force-loads, carves, summons if none is tagged there, dresses it dormant and shuts the gate. A datapack `spawnpokemonat` spawns nothing until a `/reload` (EXP-046 q1), and an entity does not survive a re-export (`LEGENDARIES.md:147-164`) | dormant NBT proven across a restart: `Unbattleable`, `NoAI`, `NoGravity`, `PoseType: "SLEEP"`, `RecalculatePose 0b`, `HideLabel`, `PersistenceRequired`, `Silent` (EXP-023, EXP-046 q2) | **proven in experiment, never run for a legendary** |

**The honest comparison.** Our own chamber system is further along than an adopted Cobbleverse
shrine would be: it has a gate that is blocks (so a sword and a thrown ball cannot cheat it —
EXP-023 killed a sleeping Celebi in three hits, `LEGENDARIES.md:126-130`), an audit of 376
checks proved to fail on six tampered inputs (`:236`), and a summon path. An adopted shrine
brings art and a ritual we cannot build cheaply, and brings an **unknown block** whose gate is
an item rather than a badge. Those are complements, not rivals: adopt the *place*, keep our
*gate*.

## 6. Hoopa in Cobblemon 1.8.0

`docs/world-building/DEEP_CITY.md:262` lists "Hoopa in Cobblemon 1.8.0" as NOT VERIFIED, and the
Deep's relic area, Hoopa's cradle at (3357, 3306) floor y12, and the finale depend on it
(`data/deep_city.json:206`, `tools/rift_zones.py:863-917`).

**VERIFIED**

- **1.8.0 did not add Hoopa.** The official wiki's 1.8.0 page lists every new Pokémon and
  regional form added in that release — Wurmple through Hydrapple, four regional forms — and
  **Hoopa is not among them. No "Prison Bottle" is mentioned anywhere on that page.**
  (https://wiki.cobblemon.com/index.php/1.8.0, read 2026-10-01.)
- **The wiki has no Hoopa article**: `https://wiki.cobblemon.com/index.php/Hoopa` returns
  **HTTP 404** (read 2026-10-01).
- **Nothing in this repository names a Cobblemon Hoopa, an Unbound form or a Prison Bottle.**
  Every `hoopa` hit is our own naming: the cradle, the relic ring's `hoopa_gold` palette entry
  and one line of dialogue (`data/deep_city.json:58`, `:206`, `data/dialogue.json:2271`).

**ASSUMED**

- **Species data for Hoopa exists in the 1.8 dataset, with an Unbound form, but no model.**
  cobbledex.info's Hoopa entry renders under a **1.8.1** marker and offers a "Base form /
  Unbound" toggle, while saying it has no listed natural spawn entry and is in no habitat pool
  (read 2026-10-01). A community tool (poketools.com) states plainly that **Hoopa "does not have
  a model yet in Cobblemon 1.7.3, so it appears as a placeholder until a later release adds
  one"**, and that no mythical spawns in the wild. Both are community sites, neither is the
  mod's source or its wiki, and neither was read for 1.8.0 specifically.
- **No Prison Bottle item and no form-change mechanism could be found in any Cobblemon source
  or wiki page.** The Prison Bottle appears only on Bulbapedia, i.e. as main-series lore.

**The plain answer.** **There is a Hoopa in the 1.8 species data and it is not usable as a
character.** Treat it as: species registered (ASSUMED), **no model — a placeholder** (ASSUMED,
community source), **no Unbound form change mechanism and no Prison Bottle item in Cobblemon**
(VERIFIED absence from the 1.8.0 release notes and the wiki; ASSUMED that the absence is
complete). Addon summons exist for some legendaries (Legendary Monuments, Myths and Legends) and
**whether either covers Hoopa was not checked here.** The Deep's relic area must not be built on
the assumption of a visible Hoopa until someone runs `/pokespawn hoopa` on the server and looks
at it — one command, ten seconds, and it settles the whole relic area.

## 7. Candidate experiments (the unknowns tonight's test could close)

These belong in `docs/research/EXPERIMENT_BACKLOG.md`; this brief restricted writing to this
file, so they are recorded here for the main session to lift across.

1. **Does a pasted altar function?** Paste one overworld legendary template (recommend
   `cobbleverse:crown_cemetery` or `cobbleverse:mythical/mew`) with raw `/place template` at an
   explicit Y on a disposable world, `enable-command-block=true`. **Must show:** the altar /
   `summon_trigger` / `summon_anchor` blocks are present and interactable; whether right-click
   with an empty hand gives any response at all; whether the chest loot tables roll; and for Mew
   whether the command chain fires and what it demands. **A pass is not "it placed"** — placing
   already passed on 1.8.0 for the Firescourge shrine (`STRUCTURE_WORKFLOW.md:90`).
2. **What item does an altar want?** Unknown and unreadable (LumyMon closed source). A test
   would have to try the wiki's named item (Origin Fossil for Mew, craftable per
   `lumymon:recipe/origin_fossil`, `STRUCTURE_DECISIONS.md:222`) and observe.
3. **How are the Kanto birds' altars triggered?** The pack's own wiki does not cover them, and
   they are three of the five overworld sites.
4. **Does `legendarymonuments:pokemon_trial_spawner` work in a pasted build?** Vanilla trial
   spawners keep their config in the block entity; this is a mod subclass and untested.
5. **Hoopa:** `/pokespawn hoopa` on the server — model or placeholder; and whether any form
   named Unbound can be produced at all.
6. **A woken legendary is killable** and a shared gate takes the encounter for the whole server
   (`LEGENDARIES.md:246-249`). Adopting a shrine inherits both problems; neither is solved.
