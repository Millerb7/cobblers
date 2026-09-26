# ADR-004: Hidden spaces are carved in place, or live in a pocket dimension that is really elsewhere

- **Status:** Accepted (the owner, 2026-09-26)
- **Date:** 2026-09-26
- **Evidence:** `docs/research/notes/xaero-map-effects.md`, including the in-game cache test on staging, 2026-09-26

## Context

Codex's gated-interactions spec asks, as open question 1, whether Xaero's map status effects can hide spaces that a
gated interaction leads into. The spec is not in this repository. The working idea was to build those spaces as
"pockets", chambers far away in the overworld's western ocean, and to hide them from the maps with the effects.

What was found:
- **The effects hide the maps; they do not stop the cache.** All six effects (`no_minimap`, `no_entity_radar`,
  `no_waypoints`, both `no_cave_maps`, `no_world_map`) are read only by rendering and GUI code. The map writer never
  reads them.
- **Tested.** With all six effects on the owner, a marker at (-640, 4096) still appeared on the world map afterwards,
  and the client wrote that region's cache file on logout.
- **The cache can be scoped per dimension, never per area.** Changing the world id wipes everyone's whole map, and the
  server cannot clear a client's cache.
- **Distant Horizons is a second, independent leak.** The server pregenerates LODs over the whole border and clients
  sync them. Chambers built on the overworld far away would be visible from the coast at distance, with no map
  involved. That alone rules out far-overworld pockets. It is inferred from the pregen (`REEXPORT.md`) and has not been
  tested with chambers built.

## Decision

A hybrid:
- **Carve in place** anything the fiction says is right there: the cave behind the boulder, anything under a floor.
  The space really exists where it appears. The map shows what is there, multiplayer shares it naturally, and nothing
  leaks.
- **A pocket dimension** only for spaces that must be bigger than their entrance, or instanced per player. The fiction
  is that these spaces **are** elsewhere, so the loading screen on crossing and the dimension's separate map belong to
  the story rather than giving it away.
- **The western-ocean grid of chambers is dropped entirely.**

## Alternatives considered

- **Far-overworld pockets hidden by the Xaero effects** (the original idea). The effects do not stop the cache, and
  Distant Horizons would show the chambers anyway.
- **Pocket dimension for everything.** The 1-2 s loading screen and the jump in coordinates break anything meant to be
  "just behind the boulder".
- **Accept the map knows, with no mechanism change.** Fine as fiction only where the spaces really are elsewhere,
  which is the pocket-dimension half of the decision.
- **Scope the cache from the server.** The jars do not allow it per area. A world-id change or a server-enforced
  config would be global.

## Consequences

- **Carved spaces are terrain work.** They need re-applying after every re-export, as the cavern does, through a step
  in `tools/reapply.py`. They cannot be bigger inside than out. Xaero's cave mode can show them to a player standing
  nearby underground, which is honest.
- **The pocket dimension is vanilla.** It is a datapack `dimension` and `dimension_type`, added with one server
  restart. It needs its own spawn rules, a re-application step, and dimension settings chosen so its sky, light, time
  and weather match. It is untouched by WorldPainter re-exports, but its contents must still be reproducible from
  data. Per-player instancing needs per-player coordinates inside it.
- **What a player notices when crossing into the pocket dimension:**
  - a short loading screen;
  - the dimension name in F3 and a jump in coordinates;
  - a separate entry in the world map's dimension list;
  - no overworld horizon (irrelevant for enclosed rooms);
  - sent-out Pokemon recalled;
  - players outside no longer visible.
- **To revisit** when Codex's spec lands: which of its spaces are "right there" and which are "elsewhere", and whether
  any must be per-player instances.
