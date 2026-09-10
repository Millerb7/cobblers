# EXP-001: Can F4 Route 1 feel deliberately authored?

**Status: donor structure and server placement passed; client visual review and encounter proof pending.**

## Objective

Prove that the 1,000-block F4 Pallet coast can feel like a real Pokémon place,
with a readable main route, curated Pokémon availability, and a memorable
optional discovery. The first vertical slice is Relic Island: a fragment of
Pallet Town containing a stranded starter home associated with Ash.

## Success criteria

- The house is visible from one useful Pallet shoreline approach at the current
  server view distance without dominating the town.
- The island is immediately optional and reachable by swimming or ordinary boat.
- Players identify the build as a displaced Pallet/Ash-style home without being
  told in a long text explanation.
- The house has a furnished interior, environmental story cues, and one reward
  point of interest.
- The event survives save/restart and places without unknown block, function, or
  loot-table IDs.
- The surrounding test route contains only an authored roster of roughly 10–20
  Pokémon, with biome/area, height, time, weather, and progression conditions
  tested where Cobblemon 1.8 actually supports them.
- A player describes both the route and optional island as authored rather than
  generic survival terrain.

## Dependencies

- EXP-000 100-jar Cobblemon 1.8 server overlay and matching client.
- Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0.
- CobblemonCityTowns 1.0 is the Pallet donor library. Its selected `large2`
  house is copied under the campaign namespace; the donor's natural worldgen is
  not enabled. The template uses vanilla geometry and the placeholder loot uses
  verified Cobblemon items.
- EXP-006 and EXP-007 are required for the final Pichu reward, but do not block
  terrain, structure, or placeholder-cache testing.

## Implementation

- Event source: `world/source/events/f4-relic-island.json`.
- Design/build spec: `docs/world-building/events/F4_RELIC_ISLAND_ASH_HOUSE.md`.
- Reward spec: `campaign/rewards/f4-relic-island.md`.
- Generator: `tools/generate_f4_relic_island.py`.
- Donor manifest: `world/structures/manifests/pokemon-town-donors.json`.
- Copied donor template: `cobblers:f4/pallet_house_large2`.
- Executable prototype: `cobblers:exp_001/f4_relic_island/place` in the
  `cobblers_campaign` datapack.
- Placeholder loot: `cobblers:chests/f4_relic_island_placeholder`.

Mechanism rung: verified donor NBT + source configuration → generated datapack
function. No custom mod or scripting dependency is introduced.

## Test instructions

1. Run `python tools/generate_f4_relic_island.py` twice and confirm identical
   hashes.
2. Run `python tools/validate.py` and the repository tests.
3. Copy `modpack/datapacks/cobblers_campaign` into the disposable complete-overlay
   runtime's global `datapacks/` directory.
4. Start a disposable ocean/coastal world or the next F4 terrain prototype.
5. At a clear ocean location with the executor positioned at sea level, run
   `function cobblers:exp_001/f4_relic_island/place`.
6. Confirm the function and loot table resolve without errors. Inspect the island
   from the planned 145-block shore sightline, swim/boat to it, enter the house,
   reach the upstairs cache, and inspect the scar/debris alignment.
7. Run `save-all flush`, restart, and inspect the same blocks and barrel.
8. Separately implement and sample the verified Cobblemon 1.8 spawn pools for the
   F4 mainland/coast/island roster; record all observed species for ten minutes.

## Results

- **Donor inspection (2026-09-10):** CobblemonCityTowns 1.0 contains five
  Pallet houses, Oak's Lab, roads, fences, lamps, vegetation, and a town sign.
  The selected `large2` house is 12×9×10, uses only `minecraft` block IDs, and
  contains three jigsaws plus one loot-table chest. It traces to LastGreenseer's
  MIT CobbleTowns 1.0.2; parsed content is identical after namespace normalization.
- **Generation:** two consecutive runs produced identical SHA-256 values:
  function `f558cba29db90d132c91fe8a57d77ff44d9e39a335bf91ddaa76246a8f05079b`,
  preview `001e2c5aca787d33479b94841896fa9abf899323aeb4cea237923ac62fe16a75`,
  donor NBT `0ad3b2e13d85c836f14255bd1e3510ea5a401d45b4a0ac4ecb332e05e9e50cd7`.
- **Validation:** `python tools/validate.py -v` completed with 0 errors and 0
  warnings; the final full pytest run passed 34 tests, including independent
  checks of deterministic output, resource IDs, donor hashes, and NBT contents.
- **Boot:** the existing 100-jar complete-overlay server reached `Done (1.309s)`
  with the campaign datapack installed. Capture:
  `runs/20260910-160050/` (runtime evidence is gitignored).
- **Functional placement:** server console resolved
  `cobblers:exp_001/f4_relic_island/place` at F4-local `(420,62,790)`. The
  expected chest existed at `(419,68,792)` with one Relic Coin Pouch, three
  Poké Balls, and one map. All three donor jigsaw positions contained their
  intended final blocks after the function.
- **Persistence:** after `save-all flush`, clean stop, and restart to a second
  normal `Done (...)`, the house blocks, resolved jigsaw positions, and chest
  contents remained present.
- **Client visual review:** not run. Sightline, interior readability, shoreline
  quality, and resemblance to Pallet architecture remain unverified.

## Limitations

- The donor building is real structure NBT; island terrain and scene damage remain
  an art prototype pending visual review.
- The final Pallet terrain and global F4 coordinates do not exist yet; coordinates
  are in a 1,000-block F4-local frame.
- The Pichu reward is intentionally unimplemented until multiplayer-safe static
  encounter and claim state are proven.
- Encounter spawn data remains pending verification against Cobblemon 1.8 formats.

## Decision

The donor-first placement mechanism is accepted for continued EXP-001 work.
Do not promote the island composition or 1,000-block F4 plan into the campaign
world until client visual review and the curated encounter proof are complete.

## Follow-up

1. Place and inspect the generated island in the disposable server.
2. Revise island terrain and the minimal donor modifications from screenshots.
3. Keep the approved donor NBT and placement offsets as campaign assets.
4. Complete the curated spawn-pool portion of EXP-001.
5. Use EXP-006/007 findings to replace the placeholder cache with the final reward.
