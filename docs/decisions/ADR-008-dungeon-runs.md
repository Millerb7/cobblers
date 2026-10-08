# ADR-008: Dungeons are authored runs on one engine, with rooms on fixed sockets and no run-time layout generation

- **Status:** Proposed
- **Date:** 2026-10-08
- **Evidence:**
  - `docs/mechanics/DUNGEONS.md`: the design, the costing (section 1.2) and the validator's defect list (1.3).
  - VERIFIED parts this rests on:
    - the pocket dimension (EXP-047; `docs/decisions/ADR-004-pocket-spaces.md`);
    - the per-player NPC loop: spawn at a level, start, win, loss and blackout, re-roll, remove. All PASS in game for
      one player (`docs/research/notes/arena-per-player-opponents.md:354-371`);
    - the pool party picks entries by NPC level and evaluates team size in MoLang with `q.level` and `q.player`. This
      is a source read, not a run (`:98-102`);
    - the macro spawn (EXP-046).
  - Built, NOT run:
    - the Entei slot, keeper and lockout (`data/entei_boss.json`; EXP-059 NOT_EXECUTED, three defects recorded in
      `docs/MORNING_REPORT_2026-10-11.md:18`);
    - the mining caves' restore (`data/mining_caves.json:3`).
  - **Pending, and this ADR should not be accepted before them:** EXP-059, and the XD1/XD2 proofs of
    `DUNGEONS.md` section 7.4 (rebuild on entry; level-picked pool parties).

## Context

The owner wants many repeatable dungeons. Each run is about 30 minutes and three legs (trainers, a resource farm, a
boss), scaling per gym, with area-specific rare rewards. The owner asked for two approaches to be costed before either
is built:
- **(a)** several hand-built runs per dungeon that rotate;
- **(b)** a generator that assembles runs from room templates.

The choice decides the shape of every dungeon after the first, the engine's data model and the validator. It is
expensive to reverse once a template library or a set of whole-run variants exists.

## Decision

**(a'): authored, socketed rooms on a shared run engine.**
- Each dungeon is a fixed hub with three sockets: trainer wing, resource wing and boss room. Each socket is a fixed
  box with fixed doors, and each has two authored rooms, chosen "other than last time" (8 layouts from 6 rooms).
- The variety a player feels comes from contents that re-roll on every run (pool teams, seam variants, boss pool,
  collection draws). It also comes from the run re-tiering to the player's level cap at entry.
- The legs are taken in either order from the hub; the boss door opens when both are done.
- Each run is a per-player slot in `cobblers:pocket`, rebuilt on entry.
- The mechanism rungs: Cobblemon native for the boss, the NPCs and the level-picked parties; datapack plus functions
  and commands for the slots, keeper, gate, lockout and rewards. No scripting layer, companion or mod (CLAUDE.md
  principle 6). Nothing in the pack ships an instanced dungeon (`data/entei_boss.json:6`).

**No run-time layout generation.** Within mcfunction nothing can prove a layout connected, reachable or free of
softlocks. So "dynamic" generation could only pick among pre-validated templates; done safely, that is fixed sockets.

## Alternatives considered

- **(a) literal, three whole hand-built runs per dungeon.** The cheapest first dungeon after (a'), at ~30M against
  ~27M to the first playable run. But the marginal cost is the highest of the three, ~9.6M a dungeon, and it buys 3
  layouts where (a') buys 8. (b) becomes cheaper than it from about four dungeons.
- **(b) a generator from a template library.** ~41M before the first playable run: the generator, a validator that
  must close 14 defect classes (`DUNGEONS.md` 1.3), its Opus audit, run-time assembly experiments and a library.
  Its marginal cost of ~5.5M a theme beats (a')'s ~6M only past about 28 themes. Its worst defect, a softlock in a
  pocket slot, is the escalation case that can trap a player.
- **One dungeon with rotating bosses** (`NETHER_DUNGEON_SCOPE.md` section 9). It is subsumed: a boss pool per dungeon
  is part of (a').

All figures are estimates from the repository's measured agent rates (CLAUDE.md), not measurements of this work.

## Consequences

- **Easier:**
  - each new dungeon is a data record plus six rooms against socket contracts, validated per room;
  - one engine serves the Nether pair, and Entei becomes a record on it;
  - per-gym scaling is mostly Cobblemon's own pool party.
- **Harder:**
  - the engine is about two Entei units of code (`DUNGEONS.md` 1.1) and must be proven before any dungeon content;
  - every dungeon's trainer wins must be clawed back to $0 net (CobbleDollars pays NPC wins automatically);
  - the seam's yield must enter the economy audit as a renewable supply.
- **Revisit when:**
  - XD2 fails (the fallback is one class per band, generated);
  - the owner wants more than about 20 themes (re-cost (b));
  - a two-player shared slot is wanted (it needs XD8 and the scope's X5).
