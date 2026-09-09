# world/

Reproducible world-building assets. The live Minecraft save is a build product and
is **not** committed; what is committed is whatever can rebuild or modify it.

| Folder | Holds |
| --- | --- |
| `source/` | WorldPainter `.world` files, terrain masks, height maps (Git LFS if large; see `.gitattributes`) |
| `schematics/` | WorldEdit / Litematica schematics of reusable builds |
| `structures/` | Minecraft structure NBT used by datapack worldgen or `/place` |
| `templates/` | Town, gym, route-segment, and dungeon-room templates |

Rules:

- Nothing is built here until EXP-000 passes and the world-critical dependency set
  (blocks, furniture, worldgen, terrain mods) is frozen. Removing a block mod after
  building deletes those blocks from the map.
- Dungeon and gauntlet layouts are specified in `campaign/dungeons/` first; the
  geometry here implements the spec.
- If a world save is ever committed, an ADR in `docs/decisions/` explains why.

Empty until then.
