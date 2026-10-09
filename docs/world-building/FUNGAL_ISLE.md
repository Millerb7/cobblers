# The Fungal Isle grown over ("Mushroom Island")

Built 2026-10-09 by `tools/fungal_isle.py` from `data/fungal_isle.json`. **Not applied to any world, not audited, not seen
in game.** Everything below is what the generator writes, as `python tools/fungal_isle.py report` prints it against the
canonical heightmap (`tools/ground.py`, rounded). The independent audit is another agent's; its checklist is the last
section.

The owner's brief: *"MUSHROOM ISLAND: foliage and life. It is empty."* Mushroom Island is the **Fungal Isle**
(`data/regions.json` `fungal_isle`: `fungal_north` and `fungal_south`, cell F1, bounds x0-983 z5216-6247).

## What was there (measured 2026-10-09)

- **Ground:** 0.77 km2 of `minecraft:mushroom_fields` painted `MYCELIUM`, a plateau at y133-147 in the middle with a
  coast that falls to the sea at y62 on slopes of up to 26 degrees (`regions.json` `fungal_isle.measured`). Dry: **0 of
  12,061** columns on an 8-block grid are water by `tools/water_mask.py`/`resident_encounters.Wet`.
- **Growth:** the plant layer is `mushrooms` at 4% coverage (single red and brown mushrooms) and nothing else.
  `data/foliage.json` has no entry for the island and its `preset_defaults` have no `mushroom` key: no cap, tree, stump,
  log, or podzol anywhere.
- **Standing things:** Grandmother Cap's ring (`data/southern_residents.json` `fairy_ring`, (608, 5888), R9SR/R18SR); the
  Zapdos tower on the east shelf (`data/placements.json` `legendary_zapdos_tower`, corner (881, 67, 5569), 31 x 29); the
  planned Newmoon island hung over the west end (`legendary_newmoon_island`, corner (24, 141, 5582), 101 x 100, its
  bottom 24 over the highest ground, y117). Nothing else.
- **Life:** the rosters exist and are mushroom-themed (`data/spawns.json` `fungal_north`: Paras anchor, Shroomish,
  Morelull, Foongus, Toedscool find, heart Parasect/Breloom/Shiinotic; `fungal_south`: Pumpkaboo, Venonat, Budew, Joltik,
  Tangela, Croagunk, heart Venomoth/Morgrem/Araquanid), 18-28, tier 3. `data/regions.json` still says
  `"encounters": {"status": "empty", "note": "spawn philosophy open; not populated"}` for both: **that label is stale**
  (the tables were generated 2026-10-02 to 05). What is *not* there is a place for a natural spawn to be seen: natural
  spawns are sparse in 77 hectares (the owner's own note on the Ursaluna's slope), and `fungal_south`'s **water table**
  (Tadbulb anchor, Dewpider, Araquanid) has `water_body: fungal_pools` that **no landmark or water mask defines**, so its
  anchor species had nowhere to spawn.
- Vanilla mooshrooms (the biome's native animal) are deleted by MobsBeGone (`base-pack/cobbleverse/config/mobsbegone-blacklist.json`
  line 38); nothing here relies on a mooshroom.

## The rungs (CLAUDE.md principle 6), and why each lower one was not enough

| System | Rung | Why the earlier rungs do not do it |
|---|---|---|
| Island-wide growth, glades | **functions/commands** (a re-apply block pass, R9FI) | `data/foliage.json` feeds the WorldPainter export (`tools/paint_maps.py`); the world is already exported and a pre-exported world never regenerates, so a `fungal_wood` type there would reach only a future re-export and would move the canopy hash `data/visibility.json` was measured on (STATE, "Visibility claims are stale"). The pass reuses `tools/foliage.py`'s `noise()` and `Spacing` (imported, not copied). |
| Cobblemon's own Fungal Dwelling | **declined** (the native rung exists) | The jar ships `cobblemon:habitats/fungal_dwelling` (a jigsaw, `start_pool` `fungal_dwelling_connector_start`, `size` 2, `max_distance_from_center` 116, biome `#cobblemon:is_mushroom`; `data/cobblemon/worldgen/structure/habitats/fungal_dwelling.json`) with its own natural pool `cobblemon:fungal_dwelling` (Paras 4-29, Parasect 24-41, Venomoth 31-45, Umbreon 28-53 ...; `habitat_pools/fungal_dwelling.json`). Its footprint is random (up to 232 wide) so it cannot be measured against the heightmap before it is placed, and its pool bypasses tier 3's 18-28 band. Offered to the owner below as an option, not built. |
| The nests (life you can see) | **datapack + Habitat Block** (activated) | The rosters are natural spawns (`spawn_json_coordinate_boxes`); an **activated** block keeps up to `max_spawns` of its pool alive within `spawn_range` (`docs/mechanics/`, `tools/habitat_blocks.py`), which is the Ursaluna outskirts' and the Old Orchard's mechanism. Records written by `records --write` like `tools/desert_wreck.py`. |
| Idle Pokemon, scenery | **not built** | `tools/ambient_idle.py` is a town model (a town plan, `derived/` plans, `cap_per_town`); its one wild-site seam is a place module exposing `idlers()` (`tools/pokemon_farm.py`), which cannot be exercised in a checkout without `derived/`. The nests above are the island's visible life. |
| The pool | **commands** (water in a carved bowl) | Fixes the dangling `fungal_pools`. 84 spawn files name water as a nearby block (`data/spawn_blocks.json`); `minecraft:water` is the one whitelisted spawn-condition block (`data/spawn_block_policy.json` whitelist entry scoped to `fungal_isle`, with the risk stated; the builder registers as a C4 checker in `data/system_contracts.json`). |

No custom mod, scripting layer or companion process.

## What the pack writes (`cobblers_fungal_isle`, 53 functions, step R9FI)

Measured by `report`: **1,309 objects, 70,192 blocks, 24,276 commands**; 67.8 ha of the island's 77.8 pass the terrain
rules. No function is over 5,000 commands or 90 chunks.

- **The scatter** (`t_<x>_<z>`, one function per 128-block tile): **101 giants** (a red spotted dome, a brown umbrella or
  a three-tier pagoda, stem 10-22, cap 9-16 across), **242 mediums** (stem 4-8, cap 4-7), **82 stumps** (dark oak, 1-3
  tall, 30% 2x2, with brown or red shelf fungi on the sides), **37 fallen logs** (4-7 long, moss on top, a bracket
  on the side) and **776 tufts** (3-6 small mushrooms on a podzol patch, the only place a small mushroom is written, so
  each has podzol under it). Density is the foliage tools' method: clumping noise at 72 blocks, glades at 220, a ramp from
  nothing at 22 blocks to full at 90, minimum spacing between every pair of stems (24 for giants), big classes
  first. A giant also gets podzol to its cap radius + 1 and moss on the next 2.5 blocks.
- **Paint** is `fill ... <block> replace minecraft:mycelium` over a slab (one command a row, whatever the slope), so it
  changes no column's height.
- **Rules** (fail the build): inside the island by the region polygon; ground >= 68; 18 blocks from any column at or under
  y64; slope <= 34 degrees; 12 blocks from the world's west edge; no block a spawn condition names (water excepted); no
  concrete; every block in `blocks.ids`; one writer per block; keep-clear regions derived from the files that place the
  things (ring: radius 16 + 22; Zapdos tower: footprint + 16; Newmoon island: footprint + 16, giants out entirely and nothing
  above y139 inside); every authored x/z in any other `data/*.json` (ignored files named in the data, with reasons) at
  least 10 blocks away.

### The three glades (each a different place)

| Glade | Centre (ground) | What stands there | The reason to remember it |
|---|---|---|---|
| **The Cap Wood** (`fungal_north`) | (392, 5572), y138, relief 0.7 over 49 blocks, 90 blocks from the north heart (432, 5488) | the **beacon**: a 3x3 stem 30 high under a 12-radius red dome (plate y168, top y177), a ring of 12 shroomlight hung under it; seven elder caps at 34 blocks, 11 more in a wood to 68, ten mediums under the beacon; podzol to 30, moss thinning to 74 | the tallest thing on the island, lit from below at night; the heart's own description ("where the caps grow tallest") made literal |
| **The Stump Court** (`fungal_north`) | (560, 5712), y145, relief 1.0 over 49 blocks, 176 from the ring | a bare trodden floor (coarse dirt, podzol, rooted dirt, small mushrooms cleared) 34 across; a **Great Stump** 3.7 radius, 5 tall, its stripped top showing rings, ten brackets round the cut; fourteen stumps with shelf fungi at 11.5; six brown umbrellas leaning in from 29 | a sparring floor: the court is the Shroomish/Breloom/Croagunk nest |
| **The Glowcap Hollow** (`fungal_south`) | (560, 5952), y142, 48 from the south heart (592, 6000), 80 from the ring | a bowl 40 across and 9 deep (flat out to a radius of 8, smoothstep to the rim at 20), a pool at the bottom (197 columns, 392 water blocks, 4 deep at the middle, surface y133), 10 stems with 3x3 froglight caps (pearlescent and verdant) on the slopes, 23 froglight buds (113 froglight blocks in all), a rim of nine ordinary caps hiding it | a cold purple-and-green light coming up out of the ground: 113 level-15 blocks in a hole. **The island's fungal pools** |

Stump Court and Cap Wood are 218 blocks apart, the hollow 240 from the court; Grandmother Cap's ring (the island's one
mushroom ring) is untouched at 30+ blocks.

## State model

- **No runtime state.** Nothing in the pack runs on its own (no load or tick function; a server pack, not world-local).
  It is blocks, and re-running R9FI rewrites the same blocks (the function text is byte-deterministic: seeds are
  `data/fungal_isle.json` `scatter.seed` and per-object hashes of it).
- **The nests** are three activated Habitat Blocks (`data/habitat_blocks.json` `fungal_cap_wood_ward`,
  `fungal_stump_court_ward`, `fungal_glowcap_hollow_ward`; `style: activated`, `cancel_range: -1`, so the island's own
  rosters continue round them; positions (392, 140, 5572), (560, 147, 5712), (569, 133, 5952)), each hidden in a block
  this pack writes (stem, log, moss) and placed by R9E, so **R9FI runs first**. They are world-global: every player
  within range sees the same pool refill.
- **Multiplayer / order / death:** no per-player state exists, so a late joiner, a death, a disconnect and a different
  order all see the same island. The only player-visible rule is the level cap: Toedscruel (31-34) and night Shiinotic are
  above the band, and the existing level-cap trap (`cobblers_levelcap`) decides what a player can catch.

### The nests (`records --write` into `data/spawns.json` `habitats` + `entries`, `data/habitat_blocks.json`)

| Pool | Species and levels (role, weight) | Why |
|---|---|---|
| `fungal_cap_wood` (5 alive in 20) | Paras 18-26 (anchor 24), Foongus 18-28 (common 12), Shroomish 18-22 (common 12), Parasect 24-28 (uncommon 6) | the wood's own small fungi, all catchable; Amoonguss needs 39 and is Grandmother Cap's |
| `fungal_stump_court` (5 in 16) | Shroomish 18-22 (anchor 24), Croagunk 18-26 (common 12), Breloom 24-28 (uncommon 6) | fighters on a sparring floor |
| `fungal_glowcap_hollow` (4 in 16) | Morelull 18-27 (anchor 24), Toedscool 20-28 (common 12), Tadbulb 18-26 submerged (common 12), Shiinotic 24-30 night (uncommon 6), **Toedscruel 31-34 night (rare 2)** | bioluminescent fungi round a pool; the creature of the place is a Toedscruel that comes out after dark, 3-6 over the band's 28 and under tier 3's cap of 35 |

Balance, checked by the tests: no stage is younger than its evolution level or past it by more than 4 (read from the
Cobblemon 1.8.0 jar); each band is the island's 18-28 except the hollow's 18-34; the weight of entries whose *lowest*
level is over 28 is 3.6% of the hollow (rule: at most 11.2%, `encounter_design.json rules.hearts.above_cap_max_share`).
The three pools are `MICRO_SITE` names in `tools/nuzlocke_zones.py` (`^fungal_`), so once placed they count as sites inside
their sub-region, not as new catch zones that would need a settlement title.

## Verified / not verified

- **Ran:** `python tools/fungal_isle.py report|build|records|probes`; `pytest tests/test_fungal_isle.py` (33 tests);
  `python tools/validate_data.py` and `python tools/validate.py` (0 errors); `tools/id_authorship.py` (0 faults);
  `tools/compile_spawns.py` then `tools/spawn_habitat_audit.py` ("no unjudged misfit"); `tests/test_habitat_blocks*.py`,
  `test_compile_spawns.py`, `test_encounter_design.py`, `test_nuzlocke_map.py`, `test_ground_rule.py`.
- **Cannot run here (no `derived/`):** `reapply.py prepare`/`steps()` (needs the built Rift index), so R9FI's position and
  the pack's coverage by a step were checked by reading `tools/reapply.py` and by the tests on its text, not by
  `uncovered()`/`unreferenced()`; `tests/test_nuzlocke_zones.py::test_the_file_is_what_the_generator_writes_today` (reads
  `derived/cavern/plan.json`; by reading the tool the pools are skipped as micro sites, so `data/nuzlocke_zones.json`
  should be unchanged: run it in the main checkout).
- **Already failing before this unit** (`training_grounds_audit` sits between `compile_spawns` and `spawn_habitat_audit` in
  `tools/reapply.py`): `tests/test_spawn_habitat_audit.py::test_prepare_runs_the_audit_right_after_the_spawns_compile` and
  `tests/test_spawn_tiers_audit.py::test_prepare_runs_the_audit_after_the_compile_and_the_habitat_audit`.
- **Assumed, not verified in a running Minecraft:** that the fills land and the pool holds water; that an activated block
  keeps its pool visible (EXP-021's shape, the Ursaluna's den and the Old Orchard use it); that Tadbulb spawns `submerged`
  in a 4-deep, 197-column pool; that no water-nearby species with no biome limit appears at the hollow; that the
  night-only entries spawn only at night; that mushroom blocks with default (all faces) states look right; that the
  froglights read as a glow; how any of it looks from the ferry or the Zapdos shelf.

## What an audit must check (independently of `tools/fungal_isle.py`)

1. Re-derive the island mask from `data/regions.json` and the heightmap and confirm no written column is outside it, under
   y68, within 18 blocks of the coast, or (scatter) steeper than 34 degrees.
2. Replay the pack's commands over a heightmap-built column array: every stem stands on its own column's ground, no cap
   floats (the builder's test walks face adjacency; the audit should walk the *commands*, not the plan).
3. Replay the bowl and flood from the pool: the water stays inside, never reaches a column whose ground is under y133.
4. The three Habitat Block positions are the blocks the pack writes there, their mimics are those blocks, and the
   pools' species are legal in the jar with no stage under its evolution level.
5. No concrete, nothing in `data/spawn_blocks.json` but the whitelisted water, nothing in the keep-clear regions (the
   ring, the tower, the Newmoon island), the Newmoon ceiling holds.
6. Mutate the **generator** (shift `sample()` 40 blocks east; raise `hollow_profile`'s rim), not the record, and expect
   the shore, keep-clear or leak rule to fail.

## Collisions and decisions for the owner

- **R9FI shares the island with** R9SR (Grandmother Cap, kept 22 blocks clear), the Zapdos tower donor (16 clear) and the
  planned Newmoon donor (its air from y141; this pack stays at or under y139 inside its footprint, and writes no giant
  there, which leaves the "empty west end" under it with mediums and tufts only).
- **Option, not built:** Cobblemon's native Fungal Dwelling (above). Placing it would give the island a house with the
  jar's own pool; it needs its pool re-leveled to tier 3 and a measured site.
- **Option, not built:** idle scenery Pokemon on the glades (an `idlers()` seam like the farm's).
- **Stale:** `data/regions.json` `fungal_north/south` `encounters.status: "empty"`; `encounter_design.json`'s
  `water_body: fungal_pools` now has a pool, but nothing reads the field.
- After the apply: `python tools/presence_audit.py --only extra` (the `fungal_isle` key, 67 probes: stems, caps, logs,
  froglights, the pool's water, and a dry negative), then walk the hollow at night.

## Commands

```
python tools/fungal_isle.py report           # counts, boxes, checks, steps; nothing written
python tools/fungal_isle.py build            # -> build/datapacks/cobblers_fungal_isle
python tools/fungal_isle.py records --write  # habitat blocks and pools into data/habitat_blocks.json, data/spawns.json
python tools/fungal_isle.py probes --write   # presence probes into data/world_probes.json
```
