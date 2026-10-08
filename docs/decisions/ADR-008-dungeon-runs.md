# ADR-008: Dungeons are timed linear rift runs on one engine: authored spines, persistent slot shells, our own rips

- **Status:** Proposed
- **Date:** 2026-10-08 (rewritten the same day for the owner's timed-dungeon shape; the hub-and-sockets version it
  replaces is summarised under Alternatives)
- **Evidence:**
  - `docs/mechanics/DUNGEONS.md`, which holds the design, the worked numbers (section 4), the costing (13) and the
    validator (11.4).
  - `docs/research/DUNGEON_MECHANISMS.md`, which gives the mechanism verdicts this rests on:
    - a countdown score and a per-player bossbar for the clock;
    - `kill` into the existing blackout for death;
    - chained battles by the victory callback for boss stages;
    - the recall sweep for no-deploy (no datapack refusal exists: VERIFIED, all 81 callbacks pass no Cancelable);
    - marker entities for the seam count;
    - a vanilla-built rip;
    - persistent shells with mutable resets for instancing.
  - Parts that are VERIFIED:
    - the pocket dimension (EXP-047; `docs/decisions/ADR-004-pocket-spaces.md`);
    - the NPC spawn, start, win, loss, re-roll and remove, each PASS in game for one player
      (`docs/research/notes/arena-per-player-opponents.md:354-371`);
    - the macro spawn (EXP-046).
  - Built, NOT run: the Entei slot, keeper and lockout (`data/entei_boss.json`; EXP-059 NOT_EXECUTED); the Beast Ball
    key (`data/key_ball.json`; EXP-064 NOT_EXECUTED).
  - **Pending, and this ADR should not be accepted before them:**
    - EXP-059;
    - probes P1 (the discard returns a Pokemon with its HP), B1 (the per-player bar), B2/B3 (the kill and sudden
      death), R2 (`can_break`), C1 (an in-function macro `spawnnpcat`, and a victory's follow-up starting the next
      battle), XT1 (fight timings, which set the clock) and L2 (a battle underwater);
    - all are `DUNGEONS.md` section 14.

## Context

The owner's brief of 2026-10-08, relayed close to verbatim: "an instanced run with a TIMER. Finish it or get out
before the clock runs down. If you are still inside when it does, you die." The entrances are visible rips torn from
the Rift. The run:
- is 1,000-2,000 blocks long, and its length and timer must agree;
- budgets about 2 minutes for a small fight and 5-10 for a boss;
- can always be turned back on, but backtracking spends the same clock.

Its legs are trainer fights, a staged boss, resource areas whose take speeds the clock (5 taken is x1.25, 20 taken is
x3), parkour with no Pokemon deployable, and legendary encounters such as a Dive lake with something obvious at the
bottom.

**The owner has decided:**
- no pause in battle;
- boss stages as separate fights chained by the victory hook;
- no-deploy by the recall sweep;
- our own rip, with no new dependency;
- fixed rips first;
- resource tracking as new work;
- every dungeon catch after the Champion, with the Beast Ball as the key.

The earlier version of this ADR chose a hub with socketed wings and no clock, which this shape supersedes. The choice
here fixes:
- the engine's data model (`data/dungeons.json` schema 2);
- the instancing approach, which drives the re-apply budget;
- the death rule, which couples to the blackout;
- whether variety comes from authored or generated spines.

These are expensive to reverse once a dungeon's shells and content exist.

## Decision

**A dungeon is a straight spine through a per-party slot in `cobblers:pocket`, entered and left by our own rips, and
run against a per-player clock.**

- **Shape.** Entry room (the back rip, always open), a spine of 1,000-2,000 blocks, exit room (the far rip).
  - **Required legs** block the spine and open forward on a win: three stands, the parkour and the staged boss.
  - **Optional legs** cost only clock: greed at the seam, the den and the legendary lake.
  - The back rip is reachable from every walkable cell at every gate state. The parkour is traversable both ways.
- **Clock.** A per-player countdown score in quarter-ticks, decremented each 20-tick pass at 4/5/6/8/12 units a tick
  (x1 to x3). There is no rate 0.
  - The clock per band is `ceil(required x 1.25)`. "Required" is computed from the walked length of the BUILT shell
    and the band's fight budget: 29-39 minutes on the first dungeon's 1,664-block spine at planning paces, retuned
    from timings.
  - The bossbar shows the clock, the multiplier, the real time left, the seam count and a return-margin warning.
  - Timeout is `kill @s` into the existing blackout, with sudden death if in battle, and forfeits the run's escrow.
    Rewards are paid only at a clean exit by either rip.
  - The lockout counts on our own uptime score, never on game time.
- **Legs**, by mechanism:
  - stands and the boss are `cobblemon:npc` battles (never rctmod), spawned by macro `spawnnpcat` at absolute
    coordinates and started by `runmolang start_battle`;
  - boss stages are separate classes chained by `battle_victory`;
  - the seam is 24 blocks counted by markers, in a run-wide adventure mode, with an unbreakable `can_break` pick taken
    back on every exit path;
  - parkour has a recall sweep, dismount, a ceiling, catch bands, and a 15-second fall penalty to the last checkpoint;
  - the lake legendary is Entei's spawn-and-bind pattern behind a membrane opened only at band 6 for a Dive-qualified
    player, Beast-Ball-keyed and caught once per player.
- **Instancing.** A persistent shell per slot, placed by a re-apply step from parametrised segment kinds (`rip_room`,
  `drift`, `stand`, `seam`, `den`, `lake`, `parkour`, `boss_arena`) that join at one door contract. Only the mutables
  are reset on entry. 4 slots per dungeon.
- **Authored spines, no run-time generation.** Each dungeon's spine is hand-written data. Variants rotate by slot (a
  slot's shell is a variant), chosen "other than last time" at entry. Nothing is generated at run time: mcfunction
  cannot prove a layout. A build-time sequencer stays possible later, because the segment kinds and audit B already
  serve it.
- **Mechanism rungs.**
  - Cobblemon native: NPCs, pool parties, callbacks, `runmolang`, the spawn commands.
  - Datapack, functions and commands: the clock, rips, sweeps, escrow and shells.
  - No scripting layer, companion or mod (CLAUDE.md principle 6). No new dependency.
  - Mega Showdown is world-critical for every legendary chosen, as for Entei.
- **One dungeon complete first:** the Night Shift (0 badges, every band, every leg kind). The Entei room is kept as
  built, its EXP-059 run first, and re-homed on the engine later.

## Alternatives considered

- **The hub with three socketed wings, untimed (this ADR's earlier version).** Superseded. A hub has no "back", so the
  owner's "backtracking spends the same clock" has nothing to measure, and its rebuild-on-entry was around a million
  blocks per entry, unmeasured.
- **Generated spines (a build-time sequencer).** It costs 7M up front (builder plus independent audit) and about 0.5M a
  variant, against authored at about 2.5M a variant. It breaks even at about 3.5 extra variants in all. With six
  dungeons at one extra variant each it saves about 5M, at the cost of the authored set pieces' placement. Deferred to
  dungeon 3, and only if three or more variants per dungeon are wanted. Run-time generation is rejected outright.
- **One clock per slot** (the research note's recommendation). Equivalent in solo play. Rejected for co-op because the
  owner asked for a per-player multiplier, which a shared clock cannot carry.
- **Pausing the clock in battle.** The research says it works with a cap. Rejected by the owner (decision D1).
- **One battle with a staged same-species party.** Rejected by the owner: the AI picks the stage order (research 3.2
  a).
- **LegendaryMonuments' distortion portal as the rip.** Rejected by the owner. Its destination is hard-coded to its
  own dimension, and an unsealed gap is a trap.
- **The uninstalled Ultra Beast or Wormhole mods.** Each is a new dependency with its own dimension rules. Not
  proposed.
- **Rebuild the whole run on entry.** Rejected for its cost per entry (research 8).

All costs are estimates from the repository's measured agent rates (CLAUDE.md "What a builder actually costs"), not
measurements of this work.

## Consequences

- **Easier:**
  - each further dungeon is a spine of known segment kinds, a palette, rosters and a legendary: about 7M;
  - a second variant is about 2.5M;
  - the clock is derived, not tuned by hand, so length and time agree by construction and the validator recomputes
    them from the built shell;
  - fixed rips become random rips by adding a scheduler, with no change to the engine.
- **Harder:**
  - the engine is larger than the Entei unit (2,926 lines, measured), and the first complete dungeon is about 35M;
  - every exit path must restore survival and take the rift pick back, or a player leaves with adventure mode or a
    free unbreakable pickaxe;
  - every dungeon's NPC wins must be clawed back to $0 net;
  - the seam enters the economy audit as a renewable supply;
  - the shells add a re-apply step whose time (probe I2) joins every re-apply;
  - the clock is honest only after XT1 times real fights. Until then every budget figure is a planning value.
- **Revisit when:**
  - XT1's fight times are far from the planning paces (re-derive the clocks);
  - P1 fails (the no-deploy leg has no mechanism; parkour would need geometry alone);
  - L2 fails (the lake falls back to a dry chamber behind the membrane);
  - the owner wants three or more variants per dungeon (cost the sequencer);
  - co-op is wanted (XD8, the second account, and the `minecraft.mined` probe R1).
