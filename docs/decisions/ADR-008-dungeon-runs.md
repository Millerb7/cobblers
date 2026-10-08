# ADR-008: Dungeons are timed linear rift runs on one engine: authored spines, persistent slot shells, our own rips

- **Status:** Proposed
- **Date:** 2026-10-08 (rewritten the same day for the owner's timed-dungeon shape; the hub-and-sockets version it
  replaces is summarised under Alternatives; amended the same day with the owner's answers and the death rule, and
  again with the sigil ladder and the run tag's engine requirement)
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
    - the run tag built and passing (`DUNGEONS.md` 11.3 E1). The code check of the death rule has reported
      (`docs/research/DUNGEON_DEATH.md`): **the rule is NOT met today**. An untagged wild Pokemon still claims items
      and holds the $600; vanilla's kill credit can turn the timer's kill into a wild kill; a claim can be delivered
      into a slot. `tests/test_dungeon_death.py` holds the pack to the fix as xfail(strict);
    - probes P1 (the discard returns a Pokemon with its HP), B1 (the per-player bar), B2/B3 (the kill and sudden
      death), R2 (`can_break`), C1 (an in-function macro `spawnnpcat`, and the first fight ever chained from a
      victory's follow-up into the next battle: Heaven's Arena proved its steps only one at a time), XT1 (fight
      timings, which set the clock), L2 (a battle underwater), LO1 (the clock across a logout), SG1 (a sigil taken by its
      component, and its recipe craftable under `doLimitedCrafting`) and DX1 (no claim on a dungeon death, including
      within five seconds of a wild hit, and no delivery into a slot);
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
- every dungeon catch after the Champion, with the Beast Ball as the key;
- and, answering the design's questions (`DUNGEONS.md` 0.1): the greed ladder x1.25/x1.5/x2/x3 at 5/10/15/20; slack
  1.25; the clock keeps running through a logout; solo first, with separate clocks in co-op; the one-hour lockout;
  the legendary picks as proposed; the order EXP-059, probes, data, engine, building the Night Shift only;
- **no guardian inside a dungeon:** a dungeon death costs the blackout's money, the run's held rewards, and the sigil
  and lockout, and nothing else. Items are kept and nothing holds them;
- **the run tag goes in the engine build**, covering a death credited to a wild Pokemon that hit the player shortly
  before, and the claim delivery gap;
- **sigils: most rips take one**, as Entei's room does, scaled by tier: early materials for early rips, netherite only
  from badge 8, when the Nether opens. Sigils decide who enters, not where a rip is; fixed rips first still stands.

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
  - **A logout does not stop it.** The absence is charged on return from our uptime counter (`gap x rate`). A run
    whose clock ran out while its player was away is dead: its slot is freed at the deadline, and the player is killed
    into the blackout on their first pass back. A server stop costs no clock.
  - The clock per band is `ceil(required x 1.25)`. "Required" is computed from the walked length of the BUILT shell
    and the band's fight budget: 29-39 minutes on the first dungeon's 1,664-block spine at planning paces, retuned
    from timings.
  - The bossbar shows the clock, the multiplier, the real time left, the seam count and a return-margin warning.
  - Timeout is `kill @s` into the existing blackout, with sudden death if in battle. Rewards are paid only at a clean
    exit by either rip.
  - **The death rule: no recovery claim inside a dungeon**, whatever the cause: the timer, a boss, a trainer, a fall,
    lava. An instance resets, so a guardian holding items would stop existing and the items would be lost for good.
    A death costs the blackout's money (taken, not held) and the run's escrow; a retry costs another sigil and the
    lockout. It is built in two layers. Every entity the engine spawns carries `claims.exempt_tag`, Entei's pattern.
    And **a run-tagged player makes no claim whatever the victor**, a change to `tools/blackout_pack.py` built with
    the engine (`DUNGEONS.md` E1). The tag is added at the click, before the arrival delay; it outlives every exit by a
    100-tick tail equal to vanilla's kill-credit window, so the timer, a fall or lava shortly after a wild hit stays
    claim-free; the engine never clears it before the blackout has read it; and the claim delivery returns for a
    tagged player and runs as the player when the tail ends, in the overworld, never into a slot.
  - The lockout counts on our own uptime score, never on game time, and is stamped at the entry room's threshold.
- **Sigils, the entry fee** (`DUNGEONS.md` 7.4). One per band, accepted at every rip, of the entrant's frozen band or
  higher: Soot (3 iron ingots, 3 coal), Gilt (1 gold ingot, 4 iron ingots, 2 redstone), Glint (1 diamond, 1 gold
  ingot, 2 iron ingots), Deepstone (2 diamonds, 1 gold ingot), Cinder (1 netherite ingot), Rift-Black (1 netherite
  ingot, 4 netherite scrap). Crafted, never bought, bank value $39 to $1,708, about 9 to 72 minutes of gathering at the
  bank's declared rates (planning). Each is a distinct pottery sherd with custom data, as the Tower Ash is.
  - **Taken at the click, spent at the threshold**: leaving by the back rip before the threshold returns it. A fee on
    entry, not a deposit on failure, because the owner asked for an entry fee and a deposit makes success free while
    adding three exit paths that must hold and return it.
  - **One free entry**, the Night Shift's first run per player, a waiver; no rip is free for good.
  - **Co-op:** each member pays their own, for their own band.
  - **Never bought or sold:** each base item joins the bank's `never_buy`; no counter, exchange, reward, escrow or
    claim list names one; no recipe uses one. The pack gives its own recipes, because `doLimitedCrafting` (the TM
    gate) blocks a recipe a player's book lacks.
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
- **One dungeon complete first, and only one until it is played** (the owner): the Night Shift (0 badges, every band,
  every leg kind). Order: EXP-059, the probes, the data, the engine. The Entei room is kept as built and re-homed on
  the engine later (still the owner's call, `DUNGEONS.md` Q15).

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
- **Free overworld entry, keys only in the Nether** (this design's earlier Q10). Superseded by the owner: most rips
  take a sigil.
- **One sigil price for every rip** (the Tower Ash's 2 netherite ingots everywhere). Rejected by the owner: netherite
  exists only from badge 8, so the Night Shift at 0 badges could not be paid for.
- **A sigil per dungeon rather than per band.** Rejected: the Night Shift serves every band from 0 badges, so a
  dungeon's sigil cannot match its entrant's means. The band is what the engine already freezes at the rip.
- **The sigil as a deposit, taken only on failure.** Rejected: it makes success free, stacks on a failure that already
  costs $600, the escrow and the lockout, and must be held across a death, a logout and a dead run.
- **Sigils sold at a counter.** Rejected: the fee becomes money (under 2% of a leg's income at every band), and a
  price would have to clear the income gate and the bank's buy-low-sell-high rule.
- **The victor tag alone, without the run tag.** Rejected by the code check: it misses untagged wild Pokemon, vanilla's
  kill credit and the delivery into a slot (`docs/research/DUNGEON_DEATH.md` sections 2-3).

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
  - every entity a dungeon spawns must carry the claims exempt tag, and the blackout gains a player-side exemption
    with a tail and a delivery guard. Audit V15 checks all of it by mutating the generators;
  - six sigil base items join the bank's `never_buy` and every sell-point check, and the server's recipe sweep must
    show no recipe collides with a sigil's (V16);
  - the seam enters the economy audit as a renewable supply;
  - the shells add a re-apply step whose time (probe I2) joins every re-apply;
  - the clock is honest only after XT1 times real fights. Until then every budget figure is a planning value.
- **Revisit when:**
  - XT1's fight times are far from the planning paces (re-derive the clocks);
  - P1 fails (the no-deploy leg has no mechanism; parkour would need geometry alone);
  - L2 fails (the lake falls back to a dry chamber behind the membrane);
  - DX1 shows that the claim cannot be suppressed for a run-tagged player in game (the code check found it can, by
    one line beside the victor test) (then every
    victor must carry the tag, and "our list is not the world" is an accepted gap, stated in `does_not_cover`);
  - C1 fails (no fight chains from a victory's follow-up: the stands and the staged boss need another trigger);
  - the owner wants three or more variants per dungeon (cost the sequencer);
  - co-op is wanted (XD8, the second account, and the `minecraft.mined` probe R1);
  - gathering is timed and a sigil's real cost is far from its planning time (retune the ladder);
  - the Entei room is re-homed on the engine (merge the Tower Ash with the band-6 sigil, or keep both).
