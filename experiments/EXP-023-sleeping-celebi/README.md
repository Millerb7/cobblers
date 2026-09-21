# EXP-023: A sleeping Celebi in the world-tree sapling

## Objective
Route 1's maze forest has a world-tree sapling at (1380, 4628). A Celebi is to sleep in it: visible from early game,
not catchable, battleable, killable or movable, woken only by right-clicking with a specific item once a progression
flag is set. The species is decided; this experiment tests **mechanisms**, and is deliberately stopped before building.

## Success criteria
A candidate passes only if, on the disposable world:
- it survives a chunk reload, a server restart and a re-export (or has a recorded re-application);
- a level-8 player cannot battle, catch, damage or displace it;
- the wrong item does nothing, with no hint and no error text;
- the right item triggers reliably and can be gated on a progression flag;
- it is visible from the ground below.

## Dependencies
Cobblemon 1.8.0+1.21.1, COBBLEVERSE stack, disposable world `cobblers-runtime-proof/spawnproof` (the live world is
never touched). The sapling is not in the snapshot (it was built after `2026-09-17-pre-grass`), so it was placed for the
test from the committed prefab: `place template cobblers:kits/trees/tree_town/sapling_oak_a 1365 123 4612` (ground y124,
crown top y164). One operator account in survival with a level-8 Charmander, Poké Balls, a stick, an amethyst shard
(stand-in "right item") and a diamond sword.

## Candidates and what happened

### A. A Pokémon entity (tested)
`spawnpokemonat <pos> celebi level=70 uncatchable no_ai`, then `data merge entity` with the flags below. Every key is
saved and reloaded; the NBT names come from `DataKeys` in the jar.

| Property | Key | Result |
| --- | --- | --- |
| Not catchable | `uncatchable` (spawn property, stored in `Pokemon.PokemonData`) | **works**: the Poké Ball is refused, "it cannot be caught" |
| Not battleable | `Unbattleable: 1b` | **works**: the player can no longer send a Pokémon at it. `canBattle` in `PokemonEntity` returns false on this flag |
| Immobile | `no_ai` (`NoAI: 1b`) plus `NoGravity: 1b` | **works**: it stays on the branch and does not wander |
| Sleeping | `PoseType: "SLEEP"`, `RecalculatePose: 0b` | accepted and kept across a restart. The Celebi poser (from the client pack **MissingMons RP**) has a `sleeping` pose and a `sleep` animation. **Not yet confirmed visually in game** |
| No name tag | `HideLabel: 1b` | accepted |
| No despawn | `PersistenceRequired: 1b` | **works**: an unflagged Celebi was gone within about 3 minutes (`despawnerMaxAgeTicks` 3600); the flagged one was still in place after 8 minutes of polling with no player nearby |
| Not damageable | `Invulnerable: 1b` | **fails** |

**The failure that matters: a player can kill it.** Three diamond-sword hits took it from full health to 4.2, and an
earlier one died the same way. `Invulnerable` is never consulted: `PokemonEntity.isInvulnerableTo` only returns true
while the entity holds a busy lock or is mid-beam, neither of which is settable from data. The server config
`playerDamagePokemon` is already `false` in `<server>/config/cobblemon/main.json` and did **not** prevent it, which I
cannot yet explain and have not designed around. Inflating health does not help either: 1,024 health was re-synced to
the Pokémon's own HP within seconds (it healed back to 52 after the restart), so damage is chip damage against a
54-point pool.

Also observed: **the crown hides it.** Spawned at the very top (y165) it could not be read from the ground; on a branch
at (1383.5, 144, 4630.5) it is visible. The player picked that branch.

**Persistence.** Full restart: survives with position, `Unbattleable`, `PoseType` and `uncatchable` intact.
Chunk reload and re-export: not yet tested. A re-export erases it for the same reason as a Habitat Block, and the entity
lives in the `entities/` region files, which `tools/transplant_chunks.py` already copies.

### B. Right-click with an item: Cobblemon's own `pokemon_interactions` (tested, fails)
A datapack interaction set targeting `celebi` with a `script` effect, loaded on the disposable world. Right-clicking the
sleeping Celebi with the wrong item **and** with the right item did nothing, and the script never ran. The reason is in
the jar: the `owner_held_item` requirement is an `OwnerQueryRequirement`, so it tests the **owner's** held item, and a
wild Pokémon has no owner. Data-driven interactions are for owned Pokémon.

### C. An NPC with a Celebi model (rejected for now, not tested)
NPCs have exactly the protections that are missing: `isInvulnerable`, `isMovable: false`, `allowProjectileHits: false`,
no battle without a party, and a proven script interaction (EXP-022). But an NPC renders from its **own** model
repository (`bedrock/npcs/...`); Celebi's model lives in the Pokémon repository and comes from a client resource pack.
Making an NPC look like Celebi means copying that model into our own resource pack, which is a redistribution question
and a local-only asset, the same class of problem as Brock's gym.

### D. A Habitat Block with a gated pool (rejected)
EXP-021 proved Habitat Blocks replace the ambient pool inside their range, but they produce ordinary wild spawns:
catchable, battleable, wandering, despawning. A specific sleeping individual is not what they express.

### E. The generic Bedrock entity (rejected)
`cobblemon:generic_bedrock` is a display entity with no battle, catch or damage logic, which would be ideal, but its
renderer resolves models from its own `bedrock/generic` repository, so it cannot show the Celebi model either.

## Where this leaves the mechanism
The Pokémon entity gives everything except **damage immunity** and a **wake trigger**. Both have candidate answers
that are not yet tested:
- **Damage:** either shield it behind an invulnerable NPC hitbox, or accept chip damage and have the placement
  function restore it (the manifest needs that function anyway).
- **Wake:** a vanilla `minecraft:item_used_on_block` advancement on the branch block, with an item predicate and our
  progression flag, granting a function. That is committed data, needs no owner, and stays silent on the wrong item.

## Limitations
- Chunk reload, re-export and the two-player case are untested.
- The sleeping pose is confirmed only in NBT, not on screen.
- Visibility was judged from one position; no render-distance measurement was taken.
- Displacement (pushing) was not tested.
- The wake sequence itself (what waking looks like) is not designed or tested.

## Decision
None yet: this is a mechanism test and the user asked for a report before building.

## Follow-up
1. Test the advancement trigger and the NPC shield on the disposable world.
2. Confirm the sleeping pose renders, and measure at what distance the entity stops rendering.
3. Decide the wake sequence, then record the Celebi in a placement manifest with its re-application.
