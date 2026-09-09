# ADR-001: Modpack base strategy

- **Status:** Proposed (becomes Accepted when EXP-000 boots and a client connects)
- **Date:** 2026-09-08
- **Evidence:** `base-pack/inventory/mod_inventory.json` (fabric.mod.json of all
  138 jars), `docs/research/notes/cobbleverse-pack-content-audit.md`, Modrinth API
  queries on 2026-09-08 (Cobblemon 1.8.0, RCT 0.19.0-beta, Mega Showdown 1.0.2+1.8,
  TMCraft 1.4.19+1.8.0, Capture XP 1.8.0-fabric-1.3.0, Tim Core
  1.8.0-fabric-1.32.0, and the other version IDs pinned in
  `modpack/manifest/overlay.json`)

## Context

One player strongly prefers the Cobbleverse modpack. Our target is Cobblemon 1.8.x,
which shipped on 2026-09-06 for the same Minecraft version (1.21.1, Fabric) that
Cobbleverse 1.7.42 uses. Cobbleverse has no 1.8 release yet. We need a pack that
keeps the Cobbleverse feel, runs on Cobblemon 1.8, and can adopt a future Cobbleverse
1.8 release without a rebuild.

Facts that shaped the decision:

- The Minecraft version does not change, so 106 of 138 jars have no Cobblemon
  dependency and need only a boot test.
- 28 jars integrate with Cobblemon. Four hard-pin 1.7.3 and block loading; three of
  those have 1.8 builds already, one (Better Pokedex Scanner) does not.
- The core systems we want (RCT trainers and level caps, Mega Showdown, raid dens,
  breeding, economy) have the highest API coupling and need functional tests even
  when they load.
- Cobbleverse's own progression depends on closed-source Lumyverse glue (LumyMon,
  LegendaryMonuments-Cobbleverse, CobbleverseBadges) with no independent update
  channel and no-redistribution licensing.

## Decision

1. **Cobbleverse 1.7.42 is the upstream reference, kept unmodified** under
   `base-pack/`. Jars, resource packs, shaders, and Lumyverse datapacks are not
   committed; they are described by hash manifests.
2. **We build an overlay, not a fork.** `modpack/manifest/overlay.json` records every
   replacement, removal, and addition with a reason. The effective pack is computed
   from base plus overlay.
3. **Target is Cobblemon 1.8.x on Minecraft 1.21.1 Fabric.** The current overlay
   has 13 replacements: Cobblemon, TMCraft, Capture XP, Tim Core, RCT/API, Mega
   Showdown, ZAMegas, Cobbreeding, Only Bottle Caps, PlayerXP, CobbleNav, and
   Fight or Flight. It removes Better Pokédex Scanner and the disabled duplicate
   Particular jar, and flags 27 retained addons/libraries for functional testing.
4. **Cobbleverse's story content is not our story.** We inherit its models, blocks,
   trainer system, badge items, raids, and quality-of-life. We replace its spawn
   pools, trainer placement, series and level-cap configuration, advancements, and
   world with our own. This also limits our dependence on the closed-source glue.
5. **The upgrade path is a re-base.** When Cobbleverse releases for Cobblemon 1.8,
   the new release becomes the base, the compatibility entries in the overlay are
   deleted where upstream now matches, and the campaign overlay is unchanged.

## Alternatives considered

- **Wait for Cobbleverse 1.8.** Rejected: no date, and the campaign systems need
  months of experiments that can start now.
- **Fork the pack and edit it in place.** Rejected: every upstream update becomes a
  manual merge of hundreds of files and the provenance of each change is lost.
- **Start from vanilla Cobblemon 1.8 and add mods one by one.** Rejected as the
  default: loses the Cobbleverse feel the player wants; kept as the fallback if
  EXP-000 shows the Cobbleverse mod set cannot be made to boot on 1.8.
- **Stay on Cobblemon 1.7.3.** Rejected: 1.8 adds native TMs, Alpha Pokémon, habitat
  structures, a Habitat Block for spawn control, and NPC party pools, all directly
  useful for authored encounters.

## Consequences

- EXP-000 (boot test) gates everything else; nothing world-critical is chosen until
  it passes.
- Every removed or replaced dependency must carry a reason in the overlay.
- If the closed-source Lumyverse jars break on 1.8 with no update, we lose the
  legendary monuments and gym-map features and must decide replacements per feature.
- This ADR is re-evaluated when Cobbleverse publishes a 1.8 release.
