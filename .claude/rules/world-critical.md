---
description: Extra scrutiny for block, biome, structure and worldgen dependencies referenced by world assets or the pack manifest
paths:
  - "world/**"
  - "modpack/manifest/**"
---

# World-critical dependencies

Owner of: the rules for adding, updating, or removing anything that puts
blocks or terrain into the world. Compatibility status lives in
`docs/research/COBBLEVERSE_COMPATIBILITY.md`; server packaging in `server.md`.

A mod is **world-critical** if it registers blocks, biomes, structures,
features, or changes terrain generation. Removing it later deletes or
corrupts every placed block and every generated chunk that used it. The
known set is listed in `CLAUDE.md` ("World-critical").

## Rules

- **Adding** a world-critical mod or datapack to `modpack/manifest/` needs:
  its status in `docs/research/COBBLEVERSE_COMPATIBILITY.md`, a boot test
  recorded in `experiments/`, and an ADR (or an amendment to one) if it will
  be built with. Not "it looked useful".
- **Updating** one: check the changelog for block-ID, blockstate or worldgen
  changes; anything that renames or removes blocks is treated as a removal.
- **Removing** one after serious map development has begun is a last resort
  (`CLAUDE.md` principle 11). It requires an ADR with an inventory of
  affected places in `world/` and a migration plan.
- Worldgen-affecting settings (`biome_replacer`, Terralith, region
  datapacks, Repurposed Structures, seed) are frozen once map building
  starts; changes alter every newly generated chunk. Record the frozen
  values in `modpack/manifest/` and treat them as world-critical.
- `world/` specs list the mods their palette relies on. A spec that uses a
  block from a mod not in the manifest is a defect, not a feature request.
- The live world save is never edited by hand or by script without an
  explicit request and a backup noted in the experiment or task log.
