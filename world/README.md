# world/

Reproducible world-building assets. The live Minecraft save is a build product and
is **not** committed; what is committed is whatever can rebuild or modify it.

| Folder | Holds |
| --- | --- |
| `source/` | WorldPainter `.world` files, terrain masks, height maps (Git LFS if large; see `.gitattributes`) |
| `schematics/` | WorldEdit / Litematica schematics of reusable builds |
| `structures/` | Campaign-owned NBT plus manifests that reference reusable upstream structures |
| `templates/` | Town, gym, route-segment, and dungeon-room templates |

Rules:

- Catalogs and disposable prototypes may be built while EXP-000 remains open.
  Persistent campaign construction waits until the world-critical dependency set
  (blocks, furniture, worldgen, terrain mods) is frozen. Removing a block mod after
  building deletes those blocks from the map.
- Dungeon and gauntlet layouts are specified in `campaign/dungeons/` first; the
  geometry here implements the spec.
- If a world save is ever committed, an ADR in `docs/decisions/` explains why.

See `docs/world-building/STRUCTURE_WORKFLOW.md` before importing or modifying an
upstream structure.
