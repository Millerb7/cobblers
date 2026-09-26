# ADR-005: How death, wipe and water are built: datapack and MoLang first, a server-side module only where proven

- **Status:** Proposed (the owner, 2026-09-26: "keep it a last resort, but if the experiments say it is genuinely
  needed, say so plainly rather than contorting four systems around something the game will not do. Server-side
  only, that my friends never install, is much less invasive than the alternative.")
- **Date:** 2026-09-26
- **Evidence:**
  - EXP-038 riding capability
  - EXP-039 battle attribution
  - EXP-040 CobbleDollars transaction
  - EXP-041 guardian persistence

  All four are on this branch, and so far they are all static reads or partly run.

## Context

`docs/mechanics/DEATH_AND_WIPE.md` (Codex, approved direction) argues for "one small server-side companion module",
because commands and datapacks alone are not a safe escrow system. CLAUDE.md principle 6 puts a custom mod last, after
native features, addons, configuration, datapacks, functions and scripting. This ADR records which parts the
installed pack can already do, and where a module is genuinely needed.

## What the evidence says so far

| Part of the spec | Mechanism available | Status |
|---|---|---|
| Water ladder: Surf and Dive capability in the party | Riding is per-species data: 45 Surf riders (boat or dolphin), 10 Dive riders (submarine). MoLang reads a party member's `species` and `form`. A `player_tick_pre` MoLang callback plus vanilla `oxygen_bonus`, `water_breathing` and `damage ... drown` cover the ladder | Verified from the data and the jar; not run |
| Full-party loss, with the victor | `battle_victory` callback: losers and winners, `is_wild`/`is_npc`/`is_player` actors, entity access | Verified from the jar; RCT trainers not checked |
| Direct wild knockout, with the victor | vanilla `entity_killed_player` detects a Pokemon killer but does not pass *which* one to a function | **The gap.** Without the killer's UUID the spec's safe default applies (environmental outcome, no item claim) |
| 10% CobbleDollars charge | `execute store result ... run cobbledollars query` works (verified), and a macro performs the charge | Read verified; charge not run |
| Atomicity | one function runs to completion on the server thread; there is no rollback, so steps are ordered and verified | Reasoned |
| Guardian persistence | vanilla `PersistenceRequired:1b`, set by `data merge`, exempts a wild Pokemon from Cobblemon's despawner. A held item exempts it only when the Pokemon picked the item up itself (`HeldItemDroppableByAI`), not when the item was given by a command. The guardian survives a chunk unload and a restart with the same UUIDs and held item. `/kill` destroys it and its item | **Verified on staging** (EXP-041, runs 3 and 4). The rebuild after a forced removal needs the ledger |
| Claim ledger | datapack `storage`: per-player and per-claim records holding item stacks with components | Assumed |
| Nested containers (backpacks) | whole stacks move with their components; scanning inside one needs component paths per backpack mod | Assumed; the riskiest datapack part |
| Offline owner delivery, one-time resolution | storage keyed by owner, delivered on the next login (an advancement or a tick check) | Assumed |

## Decision (proposed)

- Build the water ladder, the blackout charge and the checkpoint return as **datapack functions and MoLang
  callbacks**. Each rests on a verified primitive.
- Make the item claim datapack-first too, with the ordered, verified transaction, **unless** EXP-039 or EXP-041, run
  in game, show one of the following:
  - the wild victor's identity cannot be captured for a battle loss;
  - a guardian cannot be kept or rebuilt exactly once;
  - nested inventories cannot be moved without loss.

  If so, those parts, and only those, become a **small server-side Fabric module** that players never install. This
  ADR would then be amended to say so plainly.
- The direct-wild-knockout gap is **not** a reason for a module on its own. The spec already defines the safe
  default. Only a battle loss attributes items.

## Consequences

- No client installs, whichever way the claim part lands.
- The datapack path means MoLang callbacks run every player tick, throttled. Their cost must be measured (EXP-038
  step 3).
- If a module is needed, it gets its own repository folder, build and test, and the owner's sign-off. Its scope is
  limited to the proven gap.
- To revisit when EXP-038 to EXP-041 are run in game.
