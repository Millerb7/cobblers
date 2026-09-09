# EXP-009 — Automated 2×2 Hex World Prototype

## Objective

Prove a deterministic, mount-scale terrain pipeline for four 1,250-block
planning cells without creating the campaign mainland.

## Dependencies

- Python with Pillow and NumPy for deterministic source generation;
- the existing Cobblemon 1.8 complete-overlay server and structure providers;
- WorldPainter/`wpscript` for the export gate (currently absent);
- a matching client for visual, functional and mount-scale testing.

## Success criteria

The experiment is complete only when the generated 2,500 × 2,500 save boots,
shows all four terrain identities and gradual transitions, contains a wet river
and sightline-blocking ridge, accepts the generated individual-template town,
and completes the manual mount test. Source generation alone is partial.

## Implementation

`world/source/region.json` defines four cells, terrain parameters, 16 reserved
events, one town, structure placements and measured routes. `tools/generate_region.py`
creates the heightmap and full-resolution binary/category/planning masks,
preview, hashes, resolved Y coordinates and placement commands.

The four macro identities are D4 rolling lowlands/town, D5 old-growth edge,
E4 river valley, and E5 rocky foothills/ridge. All terrain is generated in one
master coordinate system, so planning-cell boundaries do not create geography.

## Test procedure

1. Run `python tools/generate_region.py` twice and compare the hashes in
   `world/source/exp-009/generation-summary.json`.
2. Run `python tools/validate.py --only region_source structure_manifest` and
   `python -m pytest tests -q`.
3. Install or extract WorldPainter 2.27.1 or later; run the two `wpscript`
   commands in `world/source/README.md`.
4. Copy the exported save into the disposable server runtime as the configured
   level, then run `world/source/exp-009/place-town.mcfunction` from the server
   console or copy it into a temporary datapack function.
5. Boot the existing complete-overlay server and record the log in `runtime/`.
6. Perform the client route/mount/sightline test in `docs/world-building/SCALE_TEST.md`.

## Results

- **PASS:** deterministic source generation; 2,500 × 2,500 block model; four
  macro terrain identities; continuous river valley; forest and forest-edge
  masks; ridge/elevation; event density; resolved structure placements; bounds,
  references and mask validation.
- **PARTIAL:** town placement is generated from individual templates, but the
  resulting town has not been visually inspected in this terrain.
- **BLOCKED:** WorldPainter/`wpscript` is not installed, so no Minecraft save was
  exported or booted. The source pipeline therefore does not yet prove biome
  rendering, trees, river water, structure foundations, or runtime sightlines.

## Limitations

The source masks are one block per pixel. BCA lodge, willow-house and well templates have jar-presence
evidence but still require the same client placement inspection as other pieces.
The WorldPainter adapter follows the published scripting API but has not run.

## Decision

**NOT READY FOR SCALE PLAYTEST.** Install/extract WorldPainter, export, boot, and
perform the prepared client test. Do not convert the full region map yet.

## Follow-up

Record WorldPainter version/export settings, boot evidence, screenshots and
travel observations here. Then decide among 1,000, 1,250 and 1,500 blocks per
planning hex; this experiment intentionally makes no final scale choice.
