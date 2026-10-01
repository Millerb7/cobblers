# EXP-047: does a pocket dimension work with this stack?

- **Status:** run 2026-09-29 on staging (`cobblers-dryrun11`), under the coordination lock, server restarted for it.
- **Question:** ADR-004 chose a pocket dimension for spaces that must be elsewhere. It had never been built. The dive
  caves and sky islands are the first real use, so before designing portals: does a custom dimension work at all here,
  do our systems reach it, and do its contents survive a re-export?
- **Objective:** answer the four unknowns ADR-004 left, minus the water arrival (closed by reasoning, below).

## What was built

A throwaway datapack `cobblers_pocket_test` in the staging world's own `datapacks/`: a vanilla
`dimension_type` and a `dimension` with a flat generator (bedrock, stone, grass; no features, no lakes; fixed
time, `has_skylight` true, `min_y` 0, height 256). The server was saved twice, stopped cleanly, and restarted,
because a dimension registers only at boot.

## Results

| # | Question | Result | Evidence |
|---|---|---|---|
| 1 | Does a custom dimension register and load? | **YES** | `Found new data pack file/cobblers_pocket_test, loading it automatically`, then `Done (1.174s)`. No new error line; the boot errors are the known pre-existing set (raid-den loot tables, two Cobblemon advancements) |
| 2 | Can we act in it? | **YES** | `forceload add` → "Marked 4 chunks in cobblers_pocket:pocket"; `setblock` → "Changed the block at 8, 10, 8" |
| 3 | Do entities live there? | **YES** | an armor stand summoned with `execute in` and read back |
| 4 | **Do our per-tick systems reach it?** | **YES, for free** | see below — this is the important one |
| 5 | Can a Habitat Block exist there? | **YES, block entity present**, but the placement needs care | see below |
| 6 | **Do its contents survive a re-export?** | **NO — and the reason matters** | see below |

### 4. Our systems reach a pocket dimension without modification

A selector with **no positional constraint is not dimension-scoped here**. Decisive test: an entity was summoned in
`cobblers_pocket:pocket`, and `execute in minecraft:overworld run kill @e[type=armor_stand,tag=pocket_probe]`
**destroyed it**; the pocket-dimension count then read 0 (`Test failed`, `PK2 has 0`).

Consequences, and they are good ones:

- Our per-tick drivers select globally (`@a`, `@e[type=...,tag=...]`), so **the blackout tick, the water ladder, the
  ambient keeper, the trainer cycle and the progression checks all apply to a player in a pocket dimension with no
  change**. A pocket dimension is not a dead zone for our systems.
- Anything **positional** — `@a[distance=..N]`, a habitat block's range, a trainer seat, an ambient worker's step —
  is naturally confined to its own dimension, because a position is meaningless across dimensions. So the confinement
  we want is free too.
- **The flip side, which the portal design must respect:** a global selector will also *reach into* the pocket
  dimension when we do not want it to. Anything meant to be overworld-only needs an explicit dimension predicate.

### 5. The Habitat Block placement

A block entity with `SpawningStyle` was created, so habitat blocks can exist there. But the `setblock` carrying the
whole NBT answered "An unexpected error occurred trying to execute that command" while still leaving a block whose
read-back shows `SpawningStyle: "cobblemon:activated"` when `cobblemon:natural` was asked for — the half-loaded
failure `docs/STATE.md` already warns about. **Use `tools/habitat_blocks.py`'s proven two-setblock recipe, not a
hand-written command.** Whether the pool then resolves and spawns is **not tested: it needs a player.**

### 6. Contents do NOT survive a re-export, but they can be carried

The dimension's blocks live at `<world>/dimensions/cobblers_pocket/pocket/` — **inside the world folder**. A
re-export creates a **new** world folder from WorldPainter, and `REEXPORT.md`'s step 4a carries **players only**;
nothing carries `dimensions/`. So the owner's hypothesis — that habitat blocks would survive a re-export in a
dimension WorldPainter never touches — is **disproved as things stand**.

The refinement is worth more than the negative:

- The pocket dimension is **generated flat and deterministically**, so re-applying it is exact and cheap, unlike
  overworld terrain.
- More useful: **it is the only part of the world that could be carried verbatim across a re-export by a folder
  copy**, precisely because nothing regenerates it. The overworld can never be carried that way. Extending
  `reapply.py carry` to copy `dimensions/` is a small, sound change and would make the hypothesis true.
- So the honest verdict: a pocket dimension is **not automatically** the better home for legendary encounters, but it
  is the **cheapest to make durable**, and the one place where "survives a re-export" is achievable at all.

## Closed by reasoning, not tested: arrival in water

The owner's call, recorded so nobody reopens it: **portals are right-click interactions, so the player is already
dismounted when they cross.** ADR-004's recall-on-crossing therefore has nothing to recall, and the collision this
session found (the water fatigue clock has no dimension filter, so an unmounted arrival under water would start
drowning) **cannot arise**. If a portal is ever changed to trigger by walking into it, this reopens immediately.

## Not tested — all need a player

Spawning from a pool in the dimension; whether a Habitat Block's pool resolves there; whether the Cobblemon
callbacks (`cobblers_blackout`, `cobblers_levelcap`) fire there; the portal crossing itself. Cobblemon spawning is
player-driven, so with nobody online these are structurally unobservable.

## Cleanup

The throwaway pack is left in place for the follow-up with a player; it is world-local to staging and in no build.
Remove `<staging world>/datapacks/cobblers_pocket_test` when done.
