# EXP-009 — Automated 2×2 Hex World Prototype

## Objective

Prove a deterministic, mount-scale terrain pipeline for four 1,250-block
planning cells without creating the campaign mainland.

## Dependencies

- Python with Pillow and NumPy for deterministic source generation;
- the existing Cobblemon 1.8 complete-overlay server and structure providers;
- WorldPainter/`wpscript` 2.27.1 for the export;
- a matching client for visual, functional and mount-scale testing.

## Success criteria

The experiment is complete only when the generated 2,500 × 2,500 save boots,
shows all four terrain identities and gradual transitions, contains a wet river
and sightline-blocking ridge, accepts the generated individual-template town,
and completes the manual mount test. Source generation alone is partial.

## Implementation

`world/source/region.json` defines four cells, terrain parameters, 16 reserved
events, one town, structure placements and measured routes. Reservations are
planning locations rather than authored encounters. `tools/generate_region.py`
creates the heightmap and full-resolution binary/category/planning masks,
preview, hashes, resolved Y coordinates and placement commands. It also emits
visible disposable markers for all 16 event reservations. The D4 meadow trial
uses an entity-free fenced arena; the other sites use small or medium marker plinths. These are
location markers, not authored berry groves, caverns, shrines, or encounters.

The four macro identities are D4 rolling lowlands/town, D5 old-growth edge,
E4 river valley, and E5 rocky foothills/ridge. All terrain is generated in one
master coordinate system, so planning-cell boundaries do not create geography.

## Test procedure

1. Run `python tools/generate_region.py` twice and compare the hashes in
   `world/source/exp-009/generation-summary.json`.
2. Run `python tools/validate.py --only region_source structure_manifest` and
   `python -m pytest tests -q`.
3. Run the two WorldPainter 2.27.1 `wpscript` commands in
   `world/source/README.md`.
4. Copy the exported save into the disposable server runtime as the configured
   level, then run `world/source/exp-009/place-town.mcfunction` from the server
   console or copy it into a temporary datapack function.
5. Boot the existing complete-overlay server and record the log in `runtime/`.
6. Perform the client route/mount/sightline test in `docs/world-building/SCALE_TEST.md`.

## Results

- **PASS — source/export:** `generate_region.py` reproduced the deterministic
  2,500 × 2,500 assets. WorldPainter 2.27.1 created the 1.96 MB editable
  `cobblers-exp-009.world` and exported an Anvil save with `level.dat`,
  `region/`, `entities/`, and 25 region files. The complete exported save is
  160,174,672 bytes; the region files account for 160,174,080 bytes.
- **PASS — first boot:** the untouched export, installed as the disposable
  `exp009-hex-prototype` level, reached `Done (1.737s)` with Java 21, Cobblemon
  1.8.0, and the 101-jar complete overlay (mod-set hash `D1483348BC2D`).
- **PASS — placement:** the first placement attempt exposed unloaded town
  chunks. The generator now wraps road, lot, structure, and landmark edits in
  17 bounded `forceload` windows. All eight template IDs loaded: the Pokémon
  Center, Poké Mart, two lodges, two willow houses, battle pad, and crossroads.
  The complete generated function then ran with no unloaded-position,
  unknown-structure, or failed-placement messages. A server-side block check
  confirmed the generated lodestone at `(750, 73, 720)`.
- **PASS — persistence:** `save-all flush` saved every dimension and a clean
  restart reached `Done (1.656s)` with the same 101 jars and mod-set hash. The
  captured restart is `runtime/runs/20260909-081753`.
- **PENDING CLIENT TEST:** visual terrain, foundations, doors, functional
  blocks, mount scale, and sightlines still require the prepared client test.
- **FAIL — first client density:** the D4 meadow reached severe visible crowding
  with Cobblemon's generated `pokemonPerChunk: 1.0`. The overlay now uses a
  provisional `0.25` cap for the next run; this still needs visual confirmation.
- **PASS AFTER SERVER FIX — client riding:** initially, Mudsdale and Charizard
  accepted movement input while the player remained detached. Disabling Better
  Third Person and Not Enough Animations separately did not change the failure.
  A vanilla boat attached normally, isolating the problem from Minecraft's base
  passenger handling. Krypton 0.2.8 was then removed from the server only; with
  the client copy still enabled, server queries showed Mudsdale and player at
  `(690.898, 75.0, 637.870)`, then Charizard and player at
  `(708.620, 78.900, 624.298)`. Krypton's server entity-tracker mixin is the
  runtime-proven conflict and Krypton is now client-optional/server-excluded.
- **PASS — corrected server boot:** the resulting 100-jar server reached
  `Done (1.314s)` and stopped cleanly. Capture `20260910-110333`, mod-set hash
  `62BEABD9398A`.
- **CORRECTED — event visibility:** the original red event mask reserved all 16
  event sites but did not place blocks. The generator now emits an explicitly
  disposable marker for every reservation, including a fenced arena for the D4
  meadow endpoint at `(930, 80, 790)`. The first client pass confirmed that the
  Berry Grove and cavern had also been invisible before this correction.
- **CORRECTED — repeat placement:** the marker function was run twice during the
  client test. Its first meadow marker reused a BCA battle pad containing NPCs,
  which duplicated Professor Saachi. The generated marker now removes those
  disposable NPCs and builds the arena from blocks, so rerunning it is stable.

## Limitations

The source masks are one block per pixel. Server success proves that the save and
structure IDs are usable; it does not prove visual quality. Structure
foundations, container warnings from repeated test placement, forest density,
river appearance, and sightlines need client inspection. WorldPainter emitted a
nonfatal missing `DragonFight` field warning for the imported `level.dat`.
BiomeReplacer also ignored its existing Terralith rules because those biome IDs
are absent from this imported vanilla-biome prototype; neither warning blocked
load, save, or restart. The reduced spawn cap is a test setting, not a final
campaign decision.

## Decision

**READY FOR SCALE PLAYTEST.** The disposable world is exported, placed, saved,
and restart-tested. Do not convert the full region map or choose a final hex
scale until the manual test is recorded.

## Follow-up

Record screenshots, measured travel times, and the scale classification here.
Only then compare 1,000, 1,250, and 1,500 blocks per planning hex; this
experiment intentionally makes no final scale choice.
