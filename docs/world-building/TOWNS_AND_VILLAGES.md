# Towns replace villages: what it costs

**Status: cost report, for review.** Authored towns replace every generated village in the
overworld.

EXP-013 showed that a hand-placed build carries no structure data. A town is therefore
invisible to anything keyed to `#minecraft:village`, to the `bca:` Pokémon villages, or to
the Repurposed Structures villages. Vanilla village *behaviour*, however, is keyed to blocks
(beds, job sites, bells), and that survives.

Counts are from the spawn files the server loads, weight above 0, with presets resolved. The
script is in the session scratchpad; the figures are reproducible with `tools/spawn_biomes.py`
discovery.

## 1. Cobblemon spawns

| Measure | Count |
| --- | ---: |
| Spawn entries that **require** a village structure | **318**: Cobblemon 199, Cobblemon Additions 113, Mega Showdown 5, Cobbleverse 1 |
| … by bucket | common 156, uncommon 93, rare 19, boss 50 |
| Species with at least one village-gated entry | 89 |
| Species whose **only** spawns are village-gated | **2: Poltchageist, Sinistcha** |
| Species whose only spawns need a village **or** a mansion (both hand-placed, so both fail) | 2 more: **Sinistea, Polteageist** |
| Spawn entries that **exclude** villages, through the `wild` and `urban` presets' anticondition | **788**: Cobblemon 764, Mega Showdown 14, Cobbleverse 10 |

**Three effects in authored towns:**
1. **Town Pokémon never appear.** The 318 entries that make a village feel inhabited (the
   Meowth, Growlithe, Chansey, Eevee and Ralts lines, 89 species in all) never fire.
2. **Four species lose their home completely:** the Sinistea and Poltchageist lines.
3. **Towns are not quiet.** The 788 entries written to stay *out* of villages will spawn
   inside towns, because nothing tells them a town is there.

**The replacement is spawn work, not structure work.** It belongs to the spawn plan
(`docs/mechanics/SPAWN_PHILOSOPHY.md`):
- **Town Pokémon:** Cobblemon 1.8's Habitat Block, placed inside each town, carrying the
  town pools.
- **Suppression:** the Habitat Block's `ReplaceSpawns` and `RangeOfInfluence` fields
  (visible in Cobblemon's own templates, per EXP-014) look like the tool for keeping wild
  spawns out of a town. **Not verified.** Proposed EXP-016: does one Habitat Block with
  `ReplaceSpawns` suppress wild entries across a town-sized radius?
- **Sinistea and Poltchageist lines:** a datapack override that gives them a non-structure
  condition, or a Habitat Block in a specific town (a tea house is the obvious home).

## 2. Villagers: spawning, trading, raids

Vanilla village mechanics read **points of interest** (beds, job-site blocks, bells), not
structure data. So a built town with those blocks behaves as a village for villager AI.
This is the vanilla design, stated from how 1.21 works; **not tested on this server**.

| Mechanic | Keyed to | In an authored town |
| --- | --- | --- |
| Villagers existing at all | only generated villages, breeding, cured zombie villagers, spawn eggs | **none exist until placed.** Nothing spawns them |
| Breeding | beds and food | works, once villagers are placed and beds are free |
| Profession and trades | job-site block POIs (LumyMon adds professions through `acquirable_job_site`) | works |
| Trades that are explorer maps | cartographers (vanilla) and LumyMon's Kanto cartographer | **broken in the overworld.** They target structure tags, and exploration maps skip generated chunks without starts (EXP-013 F) |
| Iron golems | villager count and POIs | works |
| Raids (Bad Omen, then Raid Omen, on entering a village) | POI "village sections" | works; a town can be raided |
| Zombie sieges, cats | POIs, beds | works |
| Wandering traders | spawn near players, prefer the bell | works |
| RCT trainer-association NPC | "at least 3 occupied beds and a village center", or any player carrying a trainer card (RCT config) | works on beds and bell; also independent of towns |

### Must villagers be hand-placed? Yes. At what scale?

**Proposal:**

| Settlement | Villagers | Why |
| --- | ---: | --- |
| Gym town (assumed 8, one per gym; the town list is not authored yet, and the region plan has 4 hub regions) | 4–6 each | a cleric, a librarian, a farmer, one smith and one regional profession |
| Route settlement or outpost | 0–2 | flavour, and one trade of local character |
| **Total** | **about 40–50** | |

**Placement rules:**
- Place villagers with their job site and bed **inside buildings**.
- Give them `PersistenceRequired`, so they are protected from accidental loss but not made
  invulnerable. Raids stay meaningful.
- Leave one or two spare beds per town, so breeding can replace losses without a script.

**A decision for you: rolled trades or authored trades.**
- **Rolled** vanilla trades vary per villager and include the broken map trades.
- **Authored** offers are set in the villager's `Offers` NBT at placement: a fixed,
  balanced economy alongside CobbleDollars. Villagers still level, but trades never roll
  maps.
- **Recommendation: authored offers in hub towns**, and no cartographers unless their map
  trades are replaced.

## 3. Does any progression depend on village structures?

**No progression depends on village structures. Guidance does.**
- **Radical Cobblemon Trainers:** the Kanto series has no village requirement. Trainers
  come from spawner blocks, which work pasted (EXP-013 E: the block data survives), or from
  trainer-card natural spawning.
- **No advancement on the critical path names a village.** Repurposed Structures has a
  "visit villages" advancement, which is not progression.
- **Cobbleverse's Brock gym template summons the "Kanto Map Guide" villager** when its
  pressure plate is pressed, not on placement. It only runs with `enable-command-block=true`
  (EXP-013 C). Its purpose is selling gym-locating maps, which fail on a hand-placed map.
  So the one progression-adjacent villager exists to do something that no longer works.
- **Cobblemon Additions villages** carried PokéCenter healing, fossil machines and gilded
  chests. Those move into authored towns as blocks and keep working, because none of them
  reads structure data.
- **Repurposed Structures village waystones** (placed by RS village pieces) do not appear.
  Towns get authored waystones instead (`WORLDGEN_FEATURES.md`).

## 4. The bill

| Cost | Size | Owner |
| --- | --- | --- |
| Replace 318 town-Pokémon entries with town Habitat Blocks or overrides | one datapack plus a Habitat Block per town | spawn plan |
| Keep 788 wild entries out of towns | EXP-016 first | spawn plan |
| Re-home the Sinistea and Poltchageist lines | 4 species | spawn plan |
| Place about 40–50 villagers with beds and job sites | per town build | Step 2/3 town builds |
| Authored trade offers, no map trades | hub towns | economy |
| Remove or replace map-selling villagers and trades (Brock's map guide, cartographers) | datapack override or not placing them | guidance design |
