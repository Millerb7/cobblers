# EXP-041: Can a wild guardian be kept from despawning?

**Spec questions** (`docs/mechanics/DEATH_AND_WIPE.md`, open technical questions 4 and 5): can a wild guardian be
excluded from Cobblemon's despawner and reconstructed exactly once after chunk unload, restart and a forced removal?
Does a real held item survive?

Versions: Cobblemon 1.8.0, Minecraft 1.21.1 Fabric. Config: `savePokemonToWorld: true`, `despawnerMinAgeTicks` 600,
`despawnerMaxAgeTicks` 3600, `despawnerNearDistance` 32, `despawnerFarDistance` 96.

## Findings from the bytecode (VERIFIED)

- **The despawn gate.** `PokemonEntity.checkDespawn` discards a Pokemon only if it has no owner, **and** it is not
  `isPersistenceRequired()`, **and** `CobblemonAgingDespawner.shouldDespawn`. The aging despawner looks only at age,
  distance to the nearest player, and `isBusy`.
- **What counts as persistence required** (`PokemonEntity.isPersistenceRequired` override), any of:
  - vanilla `PersistenceRequired`;
  - holding an item **while `HeldItemDroppableByAI` (`canDropHeldItem`) is true**, which Cobblemon sets when a wild
    Pokemon picks an item up off the ground (`PickUpItemTask`, `PokemonItemSensor`);
  - hive memories (bees).
- **A held item by itself protects nothing.** A command-given item leaves `HeldItemDroppableByAI: 0b`.

## Run on staging, 2026-09-26

`cobblers-dryrun11`, three wild Rattata (level 10), each alone in a sealed barrier pen, in a force-loaded chunk at
(6300, 6300) with no player within the far distance.

| Pokemon | Set up with | t+0 | t+30 s | t+60 s | t+90 s | t+120 s |
|---|---|---|---|---|---|---|
| A | `held_item=minecraft:gold_ingot` (saved `HeldItemDroppableByAI: 0b`) | present | **gone** | gone | gone | gone |
| B | `data merge entity ... {PersistenceRequired:1b}` (read back `1b`) | present | present | present | present | present, and still present at t+270 s, past the 180 s maximum age |
| C | control | present | **gone** | gone | gone | gone |

Two earlier runs lost everything. The first let the Rattata wander out of the loaded chunks; the second held an item
by command only. Both confirm A's result.

**Result:** vanilla `PersistenceRequired`, set by a command, keeps a wild Pokemon from the despawner. A command-given
held item does not. So a guardian is made persistent with `data merge entity <guardian> {PersistenceRequired:1b}`. That
the Pokemon also holds the recovery item is presentation only, as the spec already says.

## Run 4: reload, restart, forced kill (staging, 2026-09-26)

Setup: one penned wild Rattata holding a gold ingot, with `PersistenceRequired:1b`. Recorded: entity UUID
`[I; 1285683118, 1753696006, -1823980490, 861757462]` and Pokemon UUID
`[I; 246801328, 1819231654, -1646090066, -330068238]`.

| Step | Result |
|---|---|
| Force-load removed and the chunk left unloaded for 15 s. `@e` cannot find it while unloaded | expected |
| Chunk force-loaded again | **present**: same entity UUID and Pokemon UUID, still holding `minecraft:gold_ingot`, `PersistenceRequired: 1b` |
| Chunk left unloaded, then a full server stop and start (the reapply-install restart) | **present** after the restart: same UUIDs, the same item, the same flag |
| `/kill` | gone. **No item dropped** at the pen: the held gold ingot vanished with it |

**Result:**
- A persistent guardian survives chunk unload and reload, and a server restart, with its identity and held item
  intact (`savePokemonToWorld: true`).
- A forced removal destroys it and the item it holds.
- So the design must hold both of these:
  - the claim ledger, not the entity, is the record of the player's items (as the spec says);
  - the handler must detect a guardian that is gone (for example: the ledger names a UUID that no longer answers
    when its chunk is loaded) and rebuild it exactly once.

## Still to run

1. Rebuild after a forced removal, exactly once, from a ledger entry (needs the handler).
2. Capture of a persistent guardian: does `PersistenceRequired` carry into the party and need clearing?
3. Cobblemon issue #1686's despawn path, if it still exists in 1.8.0.

The full run log is `exp_guardian2.py` output, 2026-09-26, 14:4x.
