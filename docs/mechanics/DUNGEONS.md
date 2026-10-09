# Dungeons: timed rift runs, one engine, authored spines

**Status: DESIGN AND COSTING ONLY (content-architect, 2026-10-08).** Nothing here is built, placed, generated or run.
The owner's answers of 2026-10-08 to section 15 are applied (0.1), and the dungeon death rule is added (2.5).
The owner's sigil direction (D21) is designed in 7.4, and the run tag's requirements (D22) are written into the
engine (11.3), both the same day. **2026-10-09:** the owner's catches-on-the-clock rule (catches count on the greed
ladder and are lost on a failed run, fail-safe; the dungeon legendary anchored) is designed in
`docs/mechanics/DUNGEON_CATCHES.md`, which changes 2.5's "kept", escrow and chat line 4 and 2.6's "kept", each marked
in place.
This rewrite answers the owner's timed-dungeon brief of 2026-10-08 (relayed close to verbatim by the brief): "an
instanced run with a TIMER. Finish it or get out before the clock runs down. If you are still inside when it does, you
die. They are visible rips in the world, torn from the Rift." The architectural choice is
`docs/decisions/ADR-008-dungeon-runs.md`, rewritten to this shape and still **Proposed**.

**What this replaces.** The earlier version of this file (same day) was a hub with three socketed wings, about 30
minutes, no clock, rebuilt on entry. The owner's new shape supersedes its run structure (old 2.1-2.4), its costing
(old 1.1-1.3), its hub data model (old 7.1) and its time budget. **What still stands** is kept below and marked
*stands*: the reward rules and the progression bundles (section 9), per-gym band scaling (section 5.3), the cap read
at entry, NPCs as `cobblemon:npc` and never rctmod trainers, the CobbleDollars clawback, the dens, and the homes
(section 10).

**The mechanisms come from** `docs/research/DUNGEON_MECHANISMS.md` (cited as **DM**), whose verdicts and limits this
design follows exactly. Where the owner has decided against a DM recommendation (the in-battle pause, DM 1.4), the
owner's decision governs and DM's analysis is used only for its limits.

Labels: **VERIFIED** = read in source, a jar read recorded in `docs/research/`, or a run, with the citation;
**ASSUMED** = inferred, not checked; ***relayed*** = a number taken from another document and not re-measured by this
unit, with its source; ***measured*** = counted by this unit (line counts by Grep, 2026-10-08); ***planning*** = a
value this design chooses so the arithmetic can be done, to be replaced by a timing (probe XT1).

---

## 0. Owner decisions this design builds on (not reopened)

| # | Decision (the owner, 2026-10-08, relayed by the brief) | Where it lands |
|---|---|---|
| D1 | **No pause in battle.** "The clock budgets for fights; a pause that can be held open by idling in a menu is worse than no pause." | 2.1; the budget in 4 is fights plus movement |
| D2 | **Boss stages are separate fights chained by the victory hook**, not one battle where the AI picks the order | 3.2 |
| D3 | **No-deploy is the recall sweep**; a player gets a moment before it pulls back | 3.4 |
| D4 | **Our own rip** (frame, particles, an interaction to enter), not LegendaryMonuments' portal; no new dependency | 7 |
| D5 | **Fixed rips first**; a random scheduler later | 7.3 |
| D6 | **Resource tracking is new work**; the mining caves never counted mined blocks (DM premise 1, `tools/mining_caves.py:15-18`) | 3.3 |
| D7 | Beast Ball key: dungeon bosses refuse every ball but the Beast Ball, x5 (`data/key_ball.json`) | 8 |
| D8 | **Catches only after the Champion** (cap 100); pre-League bosses are fight-only set pieces | 3.2, 8 |
| D9 | Level caps 20-55 by gym, 60 after gym 8, 62 after Lance, 100 after Blue | 5.3 |
| D10 | Progression items (Exp. Candies, IV candies, Rare Candy, Lucky Egg) are dungeon-exclusive | 9 |
| D11 | The dens are approved: the Night Shift's Electirizer den, the Last Cistern's armour den | 3.6, 11 |
| D12 | Paradoxes are dungeon content (`docs/STATE.md:152`); Entei is a boss, Heatran after | 8, 10 |

### 0.1 The owner's answers to this design's questions (2026-10-08, relayed by the brief)

| # | Decision | Where it lands |
|---|---|---|
| D13 | **Greed ladder:** x1.25 at 5, x1.5 at 10, x2.0 at 15, x3 at 20, holding for the rest of the run: "smoother, and it keeps the decision live at every step" (Q1) | 3.3 |
| D14 | **Slack 1.25** (Q2) | 4.2 |
| D15 | **Logging out mid-run: the clock keeps running.** "A run you can pause by quitting is not timed" (Q4) | 2.6, 6 |
| D16 | **Solo first** (Q6); **separate clocks in co-op**, each player with their own greed (Q7) | 6 |
| D17 | **The one-hour lockout** (Q9) | 2.5 |
| D18 | **The legendary picks, approved as proposed** (Q13): section 8's table | 8 |
| D19 | **Order: EXP-059 first, then the probes, the data, the engine. The Night Shift only** (Q14, and Q15's first half) | 13 |
| D20 | **Death in a dungeon:** the guardian system does not apply inside dungeons. A death costs the blackout's money, the run's held rewards, and the sigil and lockout to try again. Nothing else: items are kept and nothing holds them, whatever killed the player (Q3) | 2.5 |
| D21 | **Sigils: most rips take one.** "I want an entry fee. Most rips take a sigil, as Entei's room does. But the fee has to SCALE WITH TIER." Netherite exists only from badge 8 (the Nether gate), so "one sigil per tier, priced in what a player can actually have at that point: early materials for early rips, netherite only for the late ones." And: "SIGILS DO NOT MAKE RIPS STATIC. A sigil decides who can enter, not where the rip is." (Q10 superseded) | 7.4, 7.3 |
| D22 | **The run tag goes in the dungeon engine build.** "'A death soon after a wild hit may be credited to that Pokemon' would have made the timer take items, the opposite of what I decided. Make sure the run tag covers that case and the claim delivery gap." | 2.5, 11.3 |

**Findings against other documents:**
- **F1 and F2 are resolved.** `DUNGEON_PLACEMENT.md` now records Q11 ("every catch after the Champion") as decided
  (D8). The vision's "Progress persists" (`docs/vision/GAME_VISION.md:138`) now says what persists: the player's
  progress always, and a dungeon's own state only for puzzle dungeons. A rift run's rooms reset on every entry (Q17).
- **F3. Heaven's Arena proved the fight loop one step at a time, never as a chain.** The in-game result shows spawn,
  start, win, loss, re-roll and remove each PASS for one player (`docs/research/notes/arena-per-player-opponents.md:357-371`).
  **No fight has ever been chained into the next**: no victory's follow-up has started a second battle. And
  `docs/STATE.md:225` lists "the in-function spawn" as NOT proven. The stands (3.1) and the staged boss (D2, 3.2) rest
  on both. **Probe C1 (section 14) proves both before anything is built on them.**
- **F4. The Entei unit is 2,926 lines** (*measured* by Grep, 2026-10-08): `data/entei_boss.json` 183,
  `tools/entei_boss.py` 752, `tests/test_entei_boss.py` 370, `tests/test_entei_boss_audit.py` 779,
  `tests/test_entei_boss_fixes_independent.py` 630, `experiments/EXP-059-entei-boss/README.md` 212.
  `tools/arena_runtime.py` is 1,217 (*measured*).
- **F5 is resolved by D21.** D20's "sigil" assumed a key while Q10 recommended free overworld entry. The owner chose
  the key: every rip takes its band's sigil (7.4), with one free entry, the Night Shift's first run per player (7.4,
  Q20). The hedge "the sigil, where the dungeon takes one" is gone; 2.5 now says what a retry costs.
- **F6. The bank's Nether tier opens a leg early.** `data/bank.json:262` (`effort_model.tiers.nether.opens_leg: 7`,
  "the gym-7 Nether trip") predates the Nether gate at `cobblers:flag/gym8_cleared` (`data/nether_gate.json:7`). So the
  effort model credits Nether wages one leg before a player can earn them. 7.4 prices netherite from badge 8, the
  gate's answer. The bank's field is the economy unit's to correct, not this design's.
- **F7. The Entei recipe has no recipe-book give.** The server runs `doLimitedCrafting` for the TM gate
  (`data/tm_gate.json:10`), under which a grid recipe missing from a player's book cannot be crafted. The gate's
  sync gives `recipe give @s *` but keys its re-sync on a plan hash built from the global `datapacks/` folder only
  (`tools/tm_gate.py:31`). `tools/entei_boss.py` emits the Tower Ash recipe (`:711-712`) and no `recipe give`
  (Grep, 2026-10-08). If its pack is not covered by that hash, a player synced before the pack was installed cannot
  craft a Tower Ash. This is ASSUMED, not run: the rip sigils (7.4) carry their own give for this reason, and EXP-059
  should craft a Tower Ash as a player who synced before the pack went in.
- **F8. The death-rule code check has reported** (`docs/research/DUNGEON_DEATH.md`, against `88bf98b`): the rule is
  NOT met today. 2.5 and 11.3 now carry its findings. `docs/STATE.md:157` still says "code check in progress".

---

## 1. The run's shape

**A run is a straight line through a pocket slot, with a rip at each end.** The player enters through a rip in the
overworld and arrives in the **entry room**, where the back rip is always open. A **spine** of 1,000-2,000 blocks runs
from there through the legs to the **exit room**, whose far rip is the clean way out. Leaving by either rip is a clean
exit. Being inside when the clock reaches zero is death.

```
 overworld rip --> [entry room | back rip] -- drift -- stand -- drift -- stand -- seam (+den) -- drift --
                   gantry (lake below, optional) -- parkour -- drift -- stand -- drift -- boss -- [exit room | far rip]
```

- **Linear, one spine, legs in a fixed authored order.** A hub (the old design) fights the owner's "backtracking
  spends the same clock": a hub has no "back". A line makes the clock legible as distance. Every leg's distance from
  both rips is known, and the entry room's run board shows it (2.4).
- **Required legs** block the spine: three trainer stands, the parkour and the boss. A stand's or the boss's gate
  opens on the win and stays open for the rest of the run, so turning back never meets a closed gate.
- **Optional legs** hang off the spine and cost only clock: the resource seam's greed beyond the free tier, the den,
  and the legendary lake. **The slack is what a player spends on them** (section 4).
- **Turning back is always possible.** The parkour is traversable in both directions (3.5, validation V6), and no
  segment has a one-way drop. The softlock rule: the back rip is reachable from every walkable cell, at every gate
  state.
- **Length and clock agree by construction.** The clock for each band is computed from the spine's own measured
  length and the band's fight budget (4.1), and the validator recomputes it from the BUILT shell (V3). Length is the
  cheapest knob: 100 blocks of drift is 25 seconds at the planning pace.

**Instancing (DM 8, the recommended approach).** Each slot is a **persistent shell** placed by a re-apply step, and
only the mutable parts are reset on entry: seam blocks and their markers, gates, the lake's membrane, NPC and boss
entities, and the run's scores. The pocket's contents do not survive a re-export (EXP-047, `docs/STATE.md:240`), so the
shell is a re-apply step and never hand-built. Rebuild-on-entry (the old 2.4) is dropped. It is around a million blocks
per entry at full dressing and is unmeasured (DM 8 table).

**Slots.** 4 slots per dungeon, one strip each: 2,048 long in x, at most 64 wide in z, at 128-block row spacing, in the
pocket's free rows from z 1,024 (DM 6: about 63 rows fit; the rescue box, x -512..1152 and z -512..768 at y 0..94,
and Entei's z -768 row are excluded; *relayed* from DM 5 and 6). The builder derives the origins from
`data/portals.json` and `data/entei_boss.json` and fails closed on any overlap, as Entei's origin does
(`data/entei_boss.json:63`).

---

## 2. The timer

### 2.1 Tracking: a per-player countdown score, never game-time arithmetic

- **One clock per player in the run**, `dg.clock` on the player, in **quarter-ticks** so 1.25x stays an integer (DM
  1.1). A minute is 1,200 ticks, or 4,800 units.
- Each keeper pass (20 ticks) subtracts `20 x rate`. The rates are 4 (x1), 5 (x1.25), 6 (x1.5), 8 (x2) and 12 (x3);
  section 3.3 gives the ladder. **There is no rate 0** (D1).
- **Why per player and not per slot.** DM 6 recommends one clock on the slot. The owner asks for a **per-player**
  multiplier, and a per-player multiplier on a shared clock is incoherent. In solo play the two are identical. In co-op
  (section 6) one partner's greed shortens only their own clock, and the shared gates still make a slow partner cost a
  fast one clock. The cost is one bossbar per member instead of per slot, which is trivial.
- **Immune to game-time jumps** (DM 1.1). Nothing compares against `gametime`, so a re-export, a `/time set` or a
  restart cannot move it. The keeper runs only while the server ticks, so a server crash or stop costs no clock. A
  player's own disconnect does cost clock (2.6). The keeper
  re-schedules from `load`, as Entei's does (`tools/entei_boss.py:381`, *relayed* via DM 1.1).
- **The clock starts when the player crosses the entry room's threshold**, not at the teleport. The entry room is a
  safe place to read the board. A player who idles there gains nothing, since the clock has not started and no leg is
  open behind it.
- **The clock stops at a clean exit.** The remaining value is the run's time record (9.4).
- **Fall penalty:** 15 s of clock, flat (1,200 units, 6.2).
- **The same counter pattern fixes the lockout** (2.5). This is the arithmetic class that produced Entei's two clock
  defects (`data/entei_boss.json:112`; review N142, *relayed*).

### 2.2 Display: one bossbar per member

DM 1.2 gives the reasons for each choice; its probe B1 is required before building.
- **Bar:** `cobblers:dg_<dungeon>_s<k>_m<m>`, with `players` set to that member only. `max` is set once, at the
  band's full clock; `value` is set every pass from the score.
- **Name, rebuilt every pass** (a score inside the name is resolved when the command runs, DM 1.2):
  `Rift 18:20 · x1.25 · ~14:40 left · taken 6`.
  - `18:20` is the clock's own time, which falls at the multiplier's speed: at x3 it drops three seconds a second.
  - `~14:40 left` is real time at the current rate, `clock / (20 x rate)` seconds. It is printed whenever the rate is
    above x1, so the cost of greed is a number the player reads, not a division they do.
  - `taken 6` is this member's seam count, once it is above 0.
- **Colour:** white at x1, yellow at x1.25 and x1.5, red at x2 and x3, purple during the return-margin warning (2.3).
  These are four of the seven bar colours (DM 1.2).
- **Moments go on the actionbar and titles, never the clock.** Other packs write to the actionbar (DM 1.2). The cues:
  - "The rift tightens. Time runs x1.5." with `block.respawn_anchor.deplete` on each threshold;
  - a title at 5:00, 1:00 and each of the last 10 seconds;
  - "The rift closes." at zero.
- **At every end of the run** the bar's `players` is emptied and the bar removed. The players set is a stored UUID
  list, so a bar left set shows again at reconnect (DM 1.2).

### 2.3 The return margin: "the way back is closing"

Backtracking spends the same clock, so the number a player needs is how long the way back takes, not just the clock.
The keeper computes it each pass, cheaply, because the run is linear:
- `back_s = (x - x_entry) x 10 / 56`, the distance to the back rip at sprint (5.6 blocks a second, *relayed*
  `docs/mechanics/GYM_INTERIORS.md:139`), plus a constant for re-crossing the parkour if the player is past it;
- the warning fires when real time left is under `back_s + 60`;
- it turns the bar purple and prints "The way back is closing" once.

It is advice, not a rule. The far rip may be nearer, and the warning says nothing about it.

### 2.4 The entry room's run board

The board is text displays on the wall, generated from the record and showing exactly what the clock assumes:
- the legs in order, with their distance from the board;
- this band's clock;
- the multiplier ladder;
- "falls cost 15 seconds";
- "no Pokemon past the cracked lamps", the parkour's no-deploy line;
- which legs are optional;
- "Dying here takes no items, only your money and what the run has earned", the death rule (2.5);
- "Leaving the game does not stop the rift", the logout rule (2.6);
- "The rift has taken your {sigil}. Go back now and it is returned; past this board it is spent", the sigil rule
  (7.4).

A player can plan greed before they reach the seam. Legibility is the owner's requirement for the multiplier, and the
clock needs the same.

### 2.5 What death means: the dungeon death rule (D20)

**The rule.** The recovery-claim ("guardian") system does not apply inside a dungeon. No Pokemon and no trainer takes
a player's items there. Outside a dungeon, a Pokemon or trainer that beats a player holds the lost items and the money
until it is beaten or caught (`docs/mechanics/DEATH_AND_WIPE.md:20-24` rule 5, `:54`, `:161-172`). In a dungeon that
holder would be an entity in an instance that resets, so it would stop existing, and the items would be gone for good.
Entei's room reached the same conclusion for one boss (`data/entei_boss.json:132`).

**A dungeon death costs exactly three things, and nothing else:**
1. **the money the blackout already takes**: $600 flat, never more than the balance (*relayed*, `data/blackout.json`
   `money`). Nothing holds it, so it is not recoverable. That is the gulch Megas' rule (contract C12: "still charges
   the money", `docs/mechanics/BLACKOUT_RECOVERY_COUPLING.md:17-30`);
2. **the run's held rewards** (the escrow, below);
3. **the price of a retry: another sigil and the lockout.** The sigil was spent when the player crossed the threshold
   (7.4), so the death does not take it; it took the run it paid for. To go again the player brings their band's
   sigil (or uses the Night Shift's one free entry, if unspent) and waits out the hour, which runs from the threshold
   (D17).

**What is kept:** every item in the inventory, including the seam ores and den drops already picked up. The rift pick
is taken back, because it was never the player's. **Changed 2026-10-09 (the owner: "Fail to extract and you lose
them"):** a Pokemon caught past the threshold is a *held* catch, forfeited by a death in the run and removed only if
every guard passes; the dungeon's legendary is anchored and kept. See `docs/mechanics/DUNGEON_CATCHES.md` sections 3,
7 and 9. *Was (2026-10-08): "...already picked up, and any Pokemon caught in the run."*

**It covers every way to die there:** the timer, a boss stage, a stand trainer, a den Pokemon, the lake legendary, a
fall, lava, drowning in the sump, and anything else. The blackout's other steps are unchanged: the player is sent to
their overworld checkpoint and healed (`DEATH_AND_WIPE.md:61-80`).

**Mechanism, two layers** (CLAUDE.md "Our list is not the world": a list of what we spawn misses what we did not):
- **Victor-side, the built pattern.** Every entity the engine spawns carries the blackout's `claims.exempt_tag`
  (`data/blackout.json:71`): stand NPCs, every boss stage, den Pokemon and the lake legendary. Entei does this today
  (`data/entei_boss.json:132`), and the blackout tests the victor for the tag (`BLACKOUT_RECOVERY_COUPLING.md:17-22`).
- **Player-side, new: the run tag** (D22). A player carrying the run tag makes no claim, whatever the victor. This
  covers a victor the engine did not spawn, and vanilla's kill credit (below). It is a change to
  `tools/blackout_pack.py`, for `minecraft-systems-dev`, and its full requirement is engine item **E1** (11.3).
- **What the code check found** (`docs/research/DUNGEON_DEATH.md`, against `88bf98b`; VERIFIED (code) and (sim)
  there, nothing run in game). **The rule is NOT met today**:
  - a trainer (`cobblemon:npc`) loss goes through `battle_loss_npc`, which takes no items (its section 3, row 3). It
    needs no exemption and must not gain one (its section 4, rule 3);
  - the exempt test reads the **victor** only, in `blackout/battle_loss_wild` (`tools/blackout_pack.py:229`). A wild
    battle loss (M3) and a kill outside battle (M4) both pass through it, so a wild Pokemon the keeper did not tag
    still claims items and holds the $600 (`hold_money`, `:626-631`). **The den as designed (3.6) spawns exactly
    such Pokemon** (its section 2, item 2);
  - the player-side check fits beside the victor test as one line (its section 4, rule 2);
  - two further gaps, both closed by E1: **the kill-credit window** (vanilla credits a death to the last mob that
    hurt the player within 100 ticks, ASSUMED there, so the timer's `kill @s` within five seconds of a wild hit
    becomes a wild kill and a claim) and **the delivery gap** (a claim resolved while its owner is in a run is
    summoned at the owner's feet, inside the slot, `as @a at @s`; its section 2, items 3-4);
  - what the exempt branch prints is not reported there. The 2.5 lines below do not depend on it.

  Until E1 is built, the rule above is the design and not a property of the code. The in-game check is DX1 (section
  14).

**The timer's kill.**
- **`kill @s`**, never `damage ... outside_border` alone, because a totem can stop that (DM 1.3, probe B2). The
  blackout counts it through `deathCount` (DM 1.3, VERIFIED (repo) `tools/blackout_pack.py:12`, `:55`).
- `keepInventory` is set at load (`tools/blackout_pack.py:174`, *relayed* via DM). **A command death is environmental
  only if no wild Pokemon hit the player in the last 100 ticks.** Within that window vanilla's kill credit names the
  hitter (ASSUMED, `DUNGEON_DEATH.md` section 2 item 4), the advancement path M4 runs, and the timer, lava or a fall
  would make a claim: the timer taking items, the opposite of D20. Fight-or-Flight attacks unprovoked from level 25
  (`base-pack/cobbleverse/config/fightorflight.json5:3-17`, *relayed* there), so this is a live case, not a corner. E1
  (11.3) closes it by reading the player's run tag, not the killer.

**Escrow, the stake.** Every reward the run pays is held **in escrow**, except the real items the player picks up (seam
ores, den drops). The escrow is scores on the player, paid by `loot give` only at a clean exit
(9.1). **Changed 2026-10-09:** a caught Pokemon is now part of the stake too, but it cannot be escrowed (it is in the
party before any callback sees it), so it is held by a **mark and a ledger with the default inverted**: escrow is lost
unless paid, a held catch is kept unless a named failure forfeits it and every guard passes
(`docs/mechanics/DUNGEON_CATCHES.md` F1-F2, section 7). *Was (2026-10-08): "...(seam ores, den drops) and a caught
Pokemon."* Any death clears it. A logout does not, unless the clock runs out while the player is away (2.6). Rule 5 is
untouched, because escrowed loot was never an item the player held (DM 1.3 C).

**What the player is told** (draft lines for `trainer-balance-designer` to tone; `messages.death` in 11.2). The
blackout's own line stands as it is: "You blacked out and returned to {place}. Lost {money}." Its item line must never be
a claim line. Then, on arrival:
- **A title, by cause:**
  - timer: "The rift closed" / "You were still inside.";
  - a boss, trainer or Pokemon: "Beaten in the rift" / "The rift lets you go.";
  - a fall, lava, drowning or anything else: "The rift threw you out";
  - a run that died while the player was away: "The rift closed without you" (2.6).
- **Chat, in this order:**
  1. "Your items are all still yours. Nothing in a rift keeps them."
  2. "The {money} is gone for good. No one in the rift is holding it." (only if money was taken)
  3. "Lost with the run: {held_summary}." or "The run had earned nothing yet."
  4. "Kept: everything you mined and picked up." then, if the run held catches, "The rift is taking back {n}
     catches." and the reaper's per-catch lines (**changed 2026-10-09**, `docs/mechanics/DUNGEON_CATCHES.md` section 8;
     the built text, `data/dungeons.json:102`, already has no catch clause). *Was (2026-10-08): "Kept: everything you
     mined and picked up{, and {caught}}."*
  5. "{dungeon} opens to you again in about {minutes} minutes, for another {sigil}." The band's sigil name (7.4), or
     "for a {sigil}" if the run was the free first entry.

Line 1 is the difference a player must not miss. A normal loss says "{victor} took {summary}. Beat it, catch it or kill
it to recover everything." (`data/blackout.json` `messages.claim`), and nothing in a rift is waiting to be beaten.
- **Timeout during a battle: sudden death** (DM 1.3, recommended there). The clock holds at 0 and the player is killed
  the moment `q.player.in_battle` reads 0, whatever the result. This is not a pause: nothing is earned, the escrow is
  already forfeit, and the battle only delays the death. A player is never killed mid-battle, because what Cobblemon
  does with the battle and the NPC is unread (DM B3).
- **Lockout: our own uptime counter, not game time.** `#up dg.up` adds 20 every keeper pass, and a player's entry stamp
  is `dg.last_<dungeon> = #up`, written at the threshold, the same moment the clock starts and the sigil is spent
  (7.4; "entry" in D17 is read as the threshold, Q21). The scoreboard carries both across a re-export (`tools/carry_players.py:84`, *relayed*
  via `data/entei_boss.json:110`), so they cannot disagree the way Entei's game-time stamp and a reset `Time` do. The
  lockout is **72,000 ticks (one hour of uptime) per dungeon per player, counted from entry** (D17). It must be at
  least the longest clock, 39 minutes (46,800 ticks), or it never binds. That is the old P3 finding, which *stands*.

### 2.6 Logging out mid-run: the clock keeps running (D15)

"A run you can pause by quitting is not timed." A disconnect, a crash of the player's client and a rage-quit are
treated alike: **the run goes on without the player, and their clock keeps falling at the rate it had.**

**Mechanism: an absence gap measured on the uptime counter.** The keeper cannot change an offline player's score by
selector (`data/entei_boss.json:109`). So it charges the absence when the player comes back:
- every pass, each member present in the run is stamped `dg.seen = #up`;
- on the first pass that finds a run-tagged player again, `gap = #up - dg.seen - 20`. If the gap is above 0, the
  keeper subtracts `gap x rate` from `dg.clock` before anything else;
- the slot carries the member's deadline, `#s<k> dg.dead = #up + dg.clock / rate`, rewritten every pass the member is
  present. When `#up` passes it with the member absent, the run is dead. The keeper then resets and frees the slot
  without waiting for the player, so an absent player never holds one of the 4 slots past their clock;
- uptime stops when the server stops, so a server stop costs no one clock (2.1). This is ASSUMED vanilla until LO1.

This replaces Entei's "the owner is not in the slot, so free it" (`data/entei_boss.json:104`), which would end a run on
any disconnect.

**Coming back before the clock runs out.** The player appears where they logged out, with the run live and the clock
lower by the time they were away, at their rate. Escrow, gates already opened and the seam count are as they left
them. The actionbar says "The rift did not wait. {mm:ss} left." What Cobblemon does with a battle open at a disconnect
is ASSUMED to be "it ends with no result" (LO1). If so, it is the forfeit case of 3.1: the gate stays shut and stepping
back on the line restarts the fight.

**Coming back to a dead run.** The dead-run check runs before the eject and before anything else on the player's first
keeper pass. It fires when their own clock is at or below 0 after the gap, or when their slot's run id is not theirs
(the slot was reset, and may hold someone else's run).
- **Where they appear:** at their logout point inside the slot, for at most one keeper pass (about a second). They are
  then killed into the blackout, as the timer would have killed them had they been there, and they wake at their
  overworld checkpoint, healed. A respawn screen comes between. This is the owner's rule as written: "If you are
  still inside when it does, you die."
- **What they are told:** the title "The rift closed without you", then the blackout's line and the 2.5 chat lines.
  The first chat line is preceded by "The rift closed {minutes} minutes ago while you were away."
- **What they lost:** the blackout's money and the run's held rewards. The sigil was already spent at the threshold;
  the retry costs another and waits out the lockout (2.5, 7.4).
- **What they kept:** every item, including what they mined and picked up. **Changed 2026-10-09:** the run's held
  catches are forfeit (cause 4) and reaped on the first pass back, after the respawn, outside the pocket, behind every
  guard; until they return, the catches stay with them (`docs/mechanics/DUNGEON_CATCHES.md` 7.2). *Was (2026-10-08):
  "...and any catch."*
- **Why the kill, and not a quiet teleport out:** if logging out avoided the $600, quitting would be the way to dodge
  a timeout. A crash is unlucky, but its cost is the same as dying, no more.

---

## 3. The leg kinds: mechanism and what the player sees

### 3.1 Trainer stands

- **Mechanism.** The arena's loop, PASS in game for one player (`arena-per-player-opponents.md:357-368`):
  1. When the player enters the stand's approach box, `spawnnpcat` with **absolute** coordinates and the band's level
     spawns the trainer. The relative form spawns nothing (`:358-359`). The spawn runs from a **macro line**, because
     a parsed command spawns nothing after a plain restart (`.claude/rules/datapacks.md`, EXP-046) and the in-function
     spawn is unproven (F3).
  2. On the challenge line, `runmolang "q.npc.start_battle(q.player, 'singles');" @s <npc>` starts it. It returns 0
     when refused (`:360-363`).
  3. The `battle_victory` callback, under `data/cobblemon/callbacks/battle_victory/` with a `cobblers_` filename, flags
     the stand won.
  4. The keeper opens the gate when `q.player.in_battle` reads 0.
- **Rules** *stand* from the arena's gauntlet. HP, PP and faints carry between fights. No bag items in battle
  (`data/arena_fights.json:27`, `:30`, *relayed*). Between fights a player may use their own potions; the clock prices
  it (Q5).
- **NPCs are `cobblemon:npc`, never rctmod trainers**, so they sit in no series and cannot move a level cap (the cap
  trap, `docs/STATE.md:222`). *Stands.*
- **The CobbleDollars automatic payout is clawed back** to $0 net, as the arena's is (EXP-060 not run; *relayed*,
  the old P5). *Stands.*
- **A forfeit sends no result** (DM 1.4, `tools/arena_runtime.py:1112`, *relayed*). The gate stays shut and stepping
  back onto the challenge line restarts the fight. The clock ran the whole time.
- **A loss is a normal NPC loss, so the blackout fires** (VERIFIED in game, `arena-per-player-opponents.md:365-366`).
  The run is over, and the death rule applies (2.5): the money and the escrow are lost, no claim is made, and the items
  are kept.
- **What the player sees.** A lit hall with a person standing at its far third. A line of dialogue on the approach,
  the battle at the line, and a timber gate behind the trainer that swings open on the win.

### 3.2 The staged boss (D2)

- **Mechanism: chained battles** (DM 3.2 b).
  1. On entering the boss arena, stage 1's NPC class is spawned (macro `spawnnpcat`) and the battle started, as a
     stand's is.
  2. The `battle_victory` callback recognises the boss by tag and stage and tags the player `dg.next`.
  3. On the next keeper pass with `in_battle` at 0, the keeper kills the stage NPC and plays the cue: title "He gets up
     again.", particles and a sound.
  4. After 60 ticks it spawns stage k+1's class at the same spot and starts the next battle.
  5. After the last stage the exit gate opens and the boss's escrow flag is set.
- **A loss at any stage** is a stand loss (3.1): the death rule (2.5), and every stage NPC carries the exempt tag.
- **The chain is unproven.** No fight has ever started from a victory's follow-up (F3). Probe C1 runs this exact chain
  three times before the boss is built.
- **Order is guaranteed**, because the function picks the next stage. One staged party is rejected (D2; DM 3.2 a: the
  AI may switch stages out of order).
- **A stage** is the boss's ace alone, at a rising level: stage 1 at cap-2, stage 2 at cap-1, stage 3 at cap. Each has
  a different moveset and held item. From band 4, stage 3 brings one escort. The boss is "beat it, it heals, it
  returns a level higher with a different moveset", and never above the band's cap (the arena rule,
  `tools/arena_runtime.py:25-28`, *relayed*).
- **Classes:** 3 stages x 6 bands = 18 per boss, generated, or fewer if XD2's level-picked pools work (5.3). Classes load
  only at a restart (`arena-per-player-opponents.md:63`, *relayed*).
- **Between stages the player's party carries everything**, and the gap is 60 ticks plus the cue. There is no time to
  heal, unless a player spends clock in their bag before stepping back to the line. Stage k+1 starts automatically, so
  idling does not hold it off.
- **Pre-League bosses are fight-only** (D8). The boss is an NPC, and an NPC's Pokemon cannot be caught
  (`beast-ball-key-1.8.0.md:151-152`, *relayed*). **A band-6 catch is a separate wild encounter** after the chain,
  where a dungeon wants one (Entei's pattern, 8 and 12).
- **What the player sees.** One figure in a large room. It falls, and the room goes dark and loud. It rises with a new
  light about it. The title names the stage ("II of III"), and the third stage is visibly the strongest.

### 3.3 The resource seam and the multiplier (new work, D6)

- **What it is.** A room whose face holds **24 seam blocks**, the band's ores (9.3), refilled on entry. Everything a
  player mines is a real drop and theirs.
- **Keeping the take to the seam: adventure mode for the whole run, plus the rift pick** (DM 2.3).
  - At entry the player is put in adventure mode and given an **iron pickaxe** with `minecraft:custom_data`
    `{cobblers_dg:"pick"}`, `minecraft:unbreakable`, and `minecraft:can_break` listing the seam's ore ids only (the
    1.21 component, ASSUMED until probe R2).
  - Their own tools break nothing. Nothing outside the seam can be mined, bridged or placed against.
  - **Every exit path restores survival and takes the pick back:** a clean exit, the respawn after death, the
    eject, and a relog to a dead run (a relog to a live run keeps both, 2.6). In survival the pick would be a free unbreakable iron pickaxe, so the backstop matters. The
    backstop is an overworld sweep over every player carrying the run tag or the pick: survival, `clear` the pick (DM
    2.3's warning).
- **Counting: marker entities, the world's truth** (DM 2.1, recommended).
  1. When the seam is refilled, one `marker` is summoned in each seam block, tagged with the slot.
  2. Each keeper pass, a marker whose block is no longer a seam ore is counted once and killed.
  3. In solo play the count is exact and goes to the player. It counts what is gone, by any means.
  4. **In co-op** a take is credited to the nearest member (approximate, DM 2.1). The exact per-player count is the
     `minecraft.mined` stat, one objective per ore id. The rift pick is the right tool by construction, so the stat
     should count, but whether it counts in adventure mode under `can_break` is ASSUMED until **R1**. The stat is
     added when co-op is enabled.
- **The ladder** (the owner's, D13: "smoother, and it keeps the decision live at every step"):

  | Taken (this player, this run) | 0-4 | 5-9 | 10-14 | 15-19 | 20-24 |
  |---|---|---|---|---|---|
  | Rate (units per tick) | 4 | 5 | 6 | 8 | 12 |
  | Clock speed | x1 | **x1.25** | x1.5 | x2 | **x3** |

- **The multiplier only rises, and holds for the rest of the run** (DM 2.2: "a one-way commitment, and that is the
  point"; D13). Leaving the seam does not cool it.
- **What the player sees.**
  - The seam's ores in a lit face, and a board beside it with the ladder.
  - On the 5th, 10th, 15th and 20th block: the actionbar line "The rift tightens. Time runs x1.25." and the sound.
    The face's remaining markers flare with particles, and the bar turns colour.
  - The bar's name always shows `taken N` and the real time left (2.2).
- **The price of greed, worked** (band 1, section 4.3): 5 blocks costs about 3.8 of the run's 6.4 spare minutes. 10 is
  a gamble that needs sprinting. 15 or 20 means take it and run back out, giving up the third stand, the boss and the
  bundle.
- **Economy.** The seam's ores enter `tools/economy_audit.py` as a renewable supply on the lockout clock, capped per
  run at the matching cave's per-reset yield (`data/mining_caves.json:66-71`, *relayed*). *Stands* from the old design.
  Diamonds are band 5+ only (9.3).

### 3.4 Parkour, no Pokemon deployable (D3)

- **No refusal exists at datapack level.** No 1.8.0 callback can cancel anything (VERIFIED, all 81, DM 4.1). **The
  recall sweep** (DM 4.2) works as follows:
  1. **Every keeper pass** (20 ticks), every `cobblemon:pokemon` in the parkour's box without our tags is removed with
     `runmolang "q.pokemon.discard;" <player> <entity>`. **Removal returns it to the party with its HP kept**
     (VERIFIED, `PokemonEntity.remove`, DM 4.2). The query name and the zero-argument `discard` are ASSUMED until
     **P1**.
  2. **Never `kill`** a player's Pokemon: that would very likely faint it (DM 4.2, P2).
  3. **Players in the box are dismounted**, with the Nether gate's bounce (`tools/nether_gate.py:192-193`, *relayed*).
  4. **The 20-tick period is the owner's "moment".** A player sees the send-out, then within a second the Pokemon
     blinks out. The actionbar says "The rift will not hold them here."
- **The geometry closes what the sweep cannot** (DM 4.2's edge cases):
  - a **gate box on solid ground** before the first jump sweeps and dismounts on entry, so nobody is unseated over a
    gap;
  - the box encloses the whole air volume to a **ceiling 3-4 above the route**, so there is no room to fly above it;
  - **ender pearls** in the box are killed;
  - **elytra** are refused at the rip (`execute if items entity @s armor.chest minecraft:elytra`, vanilla 1.20.5+,
    DM 4.2), so none ever enters a run;
  - **adventure mode** stops block placing.
- **Riding elsewhere in the run is allowed** (Q8). The sweep runs only in parkour boxes, which hold no battles. A
  run-wide sweep would remove battle send-outs too, and no flag to tell them apart is read. The clock's budget assumes
  a player on foot, so a mount in the drifts buys slack, which a player has earned.
- **What the player sees.** A line of cracked, unlit lamps across the floor marks the box's edge, and the run board
  names it (2.4). Past it, the Pokemon will not stay.

### 3.5 Parkour and death: what a fall costs (DM 5)

- **A catch band under every gap**, 6 blocks below the route. A player in it is teleported to their **last
  checkpoint**, the section end they last stood on in either direction, so turning back works. They get
  `resistance 5` for 2 seconds (probe F1: whether a teleport keeps fall distance) and lose **15 s of clock**.
- **A fall therefore costs about 35 seconds:** 15 of penalty and about 20 to re-run the section (*planning*). Too many
  falls cost the run, which is the owner's model. **No fall can kill.** The validator proves a catch band under every
  gap column (V6). The pocket's bedrock floor is at y0, so nothing reaches the void (DM 5).
- **Rejected:** `gamerule fallDamage false`, which is server-wide (DM 5), and slow falling, which removes the challenge.
- **The rescue box** of the portals pack is outside every slot by construction (1, Slots).

### 3.6 The den (optional; D11; the mechanism *stands* from the old 2.3)

The den is a side room of four wild Pokemon at the band's level (cap-2 to cap-1). They are `uncatchable` and never
alpha, carry the claims exempt tag (2.5), and are spawned by macro on entering the den box (Entei's farm pattern,
`data/entei_boss.json:19`). Their drops are the **species' own tables**: real items, so death keeps them. The den costs clock, about 4 wild fights (*planning*: 1.5
minutes each, 6 in all), and it is the second-largest spend of slack after the lake. The two approved dens and their
expected yields *stand* (old 2.3, *relayed* from `docs/mechanics/DROPS_PROGRESSION_SPLIT.md` section 5).
**Not a nest (2026-10-09):** the den stays `uncatchable`. A catchable **nest** is a separate optional leg, spawned at or
under the band's lower cap so the level cap never refuses its balls, whose catches are held by the run
(`docs/mechanics/DUNGEON_CATCHES.md` section 11).

### 3.7 The legendary lake (optional; band 6 catches it, every band sees it)

- **Shape.** From a gantry on the spine, a flooded shaft drops 40 blocks.
  - **A cache on a ledge at 30 deep.** One escrowed item (9.2), taken by clicking an interaction entity. It is within
    a Surf player's reach: Surf gives about 61 s of air, and a sprint-swim is 5 blocks a second (both *relayed*,
    `docs/mechanics/WATER_MAP.md:28`, `:40`, measured in EXP-042). A player without Surf can touch 30 deep "with
    nothing to spare" (`:27`, `:32`), and drowning there is a blackout.
  - **At the bottom, behind a membrane, the legendary rests on the bed.**
- **Make it OBVIOUS**, so it rewards noticing, not searching (DM 9; `unhomed-legendaries-1.8.0.md` "Make it OBVIOUS").
  All are vanilla, ASSUMED until L1:
  - the legendary is dressed **sleeping** (`PoseType: SLEEP`, `NoAI`, `PersistenceRequired`, proven across a restart,
    EXP-023/046, *relayed*) and given **`glowing`**, so its outline draws through water and the membrane for anyone
    on the gantry;
  - lanterns on the bed (the repository's rule is lanterns, never light blocks);
  - a bubble column rising from the membrane to the surface;
  - keeper particles above the water (steam, for the Night Shift's species, 11.2).
- **The membrane is the gate.** It is a curtain of barrier blocks across the chamber mouth at the bottom, dressed with
  particles, opened per slot by the keeper:
  - **Bands 1-5: always closed.** The line is "It does not stir for you yet." This is D8, and it is a promise a player
    can see.
  - **Band 6: open only while the member at it is Dive-qualified** by the water system: Dive training plus a
    Dive-capable party member, `docs/mechanics/DEATH_AND_WIPE.md:32-38` rules 9-10, *relayed* via DM 9. The water
    system has no dimension filter, so it runs in the pocket (`tools/blackout_pack.py:191`, *relayed* via DM 5). The
    builder reads its state name from `tools/blackout_pack.py`. **This is what makes it a Dive encounter**, not depth
    alone. A Surf player could otherwise reach the bed, start a battle and drown mid-battle, the B3 risk.
- **The encounter (band 6), Entei's pattern** (DM 9):
  1. When the membrane opens, `spawnpokemonat` by macro spawns the legendary at level 100 (cap 100), catchable.
  2. It is bound by tag, `PersistenceRequired` and a leash.
  3. It is tagged `cobblers.key_boss` and listed in `data/key_ball.json` `bosses`, so only a Beast Ball catches it, at
     x5 (D7).
  4. It carries the blackout's `claims.exempt_tag` (`data/blackout.json:71`).
  5. The catch is **once per player**, an advancement granted by the `pokemon_captured` callback. After it, that
     player's sump holds only the cache.
- **The battle is underwater.** That a battle starts and runs there is ASSUMED (**L2**). **Fallback** if L2 fails: a
  dry chamber behind the membrane, the built and audited `lake_grotto` archetype (`tools/legendaries.py`,
  `docs/mechanics/LEGENDARIES.md` section 2, *relayed*). The Dive gate stays on the membrane either way.
- **In co-op**, a slot shares its lake, so the cradle's ball check comes back. A player's ball at another member's
  legendary is refused, as `tools/hoopa_cradle.py:233-247` does, which `data/entei_boss.json:25` says must return "if
  slots are ever shared".
- **What it costs in clock:** the cache about 1 minute; the band-6 legendary about 6 minutes: dive, battle, Beast Ball
  throws, back (*planning*).

---

## 4. The numbers worked

### 4.1 Paces (every one replaced by XT1's timings before the clock ships)

| Quantity | Value | Basis |
|---|---|---|
| Walk on foot, drifts with turns, stairs and doors | **4.0 blocks/s** | *planning*. Vanilla walk about 4.3 and sprint about 5.6 (sprint *relayed*, `GYM_INTERIORS.md:139`; walk is vanilla, ASSUMED) |
| Sprint (the return margin) | 5.6 blocks/s | *relayed*, as above |
| Swim / Dive | 5 / about 10 blocks/s | *relayed*, `WATER_MAP.md:40-42` (EXP-042) |
| Parkour | 1.5 blocks/s of route, plus 2 falls a run at about 35 s each | *planning* |
| Seam, free tier (4 blocks) | 0.5 min | *planning*; vanilla break time with an iron pick, ASSUMED |
| Spawns, cues and gates over a run | 0.5 min | 3 stand spawns, 2 stage gaps of 60 ticks, arrival |
| A small fight, band 1 (2 opposing members) | **2.0 min** | **the owner's number**; no fight has ever been timed (old 2.2) |
| Each further opposing member | +0.5 min | *planning* |
| Boss, 3 stages | 6-9 min by band | inside the owner's 5-10 |

### 4.2 The owner's case: 1,500 blocks of walking, three small fights, a boss, parkour

The first dungeon's spine (11.1) is **1,464 blocks of walking plus 200 of parkour**, so it is the owner's case.

| Band (cap at entry) | Stand members | Per stand | 3 stands | Boss | Walk | Parkour | Seam + cues | **Required** | **Clock** | **Slack** |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 (20, 25) | 2 | 2.0 | 6.0 | 6.0 | 6.1 | 3.5 | 1.0 | **22.6** | **29** | 6.4 (22%) |
| 2 (30, 35) | 3 | 2.5 | 7.5 | 6.5 | 6.1 | 3.5 | 1.0 | **24.6** | **31** | 6.4 (21%) |
| 3 (40, 45) | 3 | 2.5 | 7.5 | 7.0 | 6.1 | 3.5 | 1.0 | **25.1** | **32** | 6.9 (22%) |
| 4 (50, 55) | 4 | 3.0 | 9.0 | 7.5 | 6.1 | 3.5 | 1.0 | **27.1** | **34** | 6.9 (20%) |
| 5 (60, 62) | 5 | 3.5 | 10.5 | 8.0 | 6.1 | 3.5 | 1.0 | **29.1** | **37** | 7.9 (21%) |
| 6 (100) | 6 | 4.0 | 12.0 | 9.0 | 6.1 | 3.5 | 1.0 | **31.1** | **39** | 7.9 (20%) |

Minutes throughout. **Clock = ceil(required x 1.25)**; the factor is the owner's (D14). The stand sizes are the old band table's
(*stands*, 5.3). Walk = 1,464 / 4.0 = 366 s.

**What the table says:**
- **The clock is mostly a fight budget.** Walking is 6 of 23-31 minutes. 1,000 blocks of spine is 4.2 minutes at the
  planning pace and 2,000 is 8.3. "Longer if the run earns it" is cheap in clock: each extra 400 blocks is about 1.7
  minutes, and the clock follows by formula.
- **The honest slack is about 6-8 minutes**, roughly a fifth of the clock. It is what pays for falls beyond two, a
  forfeit and re-fight, potions between fights, the den, the cache, greed beyond the free tier and, at band 6, the
  legendary.
- **At band 6 the legendary (about 6 minutes) eats nearly all the slack** (7.9). A band-6 player chooses: the
  legendary or greed, rarely both. That is designed in: the sump comes after the seam (11.1) and the board says so.

### 4.3 Greed, worked (band 1, clock 29)

Reaching the seam and digging its free tier takes about 7.4 minutes: about 630 blocks of walking (2.6), two stands
(4.0), cues (0.3) and the dig (0.5). That leaves **21.6 minutes** on the clock. What remains after the seam is about
834 blocks (3.5), the parkour (3.5), one stand (2.0), the boss (6.0) and cues (0.2): **15.2 minutes of real time.**

| Taken | Speed | Clock the rest needs | Outcome |
|---|---|---|---|
| 0-4 | x1 | 15.2 | finishes with 6.4 to spare (the whole slack) |
| 5-9 | x1.25 | 19.0 | **finishes, 2.6 to spare** (the affordable greed) |
| 10-14 | x1.5 | 22.8 | **1.2 short**: sprinting the remaining drifts saves 1.0 real minute, 1.5 of clock, so it finishes with about 0.3 and no falls beyond the budgeted two |
| 15-19 | x2 | 30.4 | cannot finish. **Turn back:** about 630 blocks at sprint is 1.9 real minutes, 3.8 of clock |
| 20-24 | x3 | 45.6 | cannot finish. **Turn back:** 1.9 real minutes is 5.6 of clock, out with about 16 to spare |

So **5 is affordable, 10 is a gamble, and 15 or more is "take it and run".** A player who turns back keeps the ore and
the first two stands' escrow, paid at the back rip, and gives up the third stand, the boss and the progression bundle.
That is the owner's "greed is the trade" as a legible decision. At band 6 (clock 39, 27.6 left at the seam, 20.2
needed after): x1.25 finishes with 2.4 to spare, x1.5 is 2.7 short, and greed and the legendary exclude each other.

---

## 5. Per-band rules

### 5.1 The band is frozen at entry

The band is read from the player's level cap at entry: `rctmod player get level_cap @s` on a macro line, the read
`tools/levelcap_pack.py:58`, `:93` makes (*stands*). It is stored on the player for the run. The clock, the NPC levels,
the boss stages, the escrow tables and the lake's state all key on it.

### 5.2 A party over the cap is refused at the rip

This is the arena's check (`tools/arena_runtime.py:536`, *relayed*; *stands*).

### 5.3 Scaling (*stands* from the old section 5)

The bands are 1 (cap 20, 25), 2 (30, 35), 3 (40, 45), 4 (50, 55), 5 (60, 62) and 6 (100). Trainer members are
2/3/3/4/5/6, at cap-2 to cap-1, and 95-99 at band 6. Challenge mode adds one member and holds items one band early
(`docs/mechanics/OAK_AND_CHALLENGE.md:55`, *relayed*). Rung 1 is one class per trainer whose pool entries carry
`npcLevels`, with MoLang team size (VERIFIED from source, not run: probe XD2). The fallback is generated classes per
band.

---

## 6. Multiplayer

**Solo first** (D16). The data model carries `members[]` from day one, so co-op is a switch, not a rewrite.

| Question (the vision's four, `GAME_VISION.md:149-150`) | Answer |
|---|---|
| Two players at once | **Solo:** separate slots, 4 per dungeon. **Co-op (later):** up to 4 members in one slot. Everyone within 4 blocks of the rip who clicks within 10 seconds of the first click joins. Each passes the gate, lockout, cap and sigil checks, and each is refused alone. Each pays their own sigil, of their own band (7.4) |
| One player ahead | Each member's NPCs spawn at **their own band** (the arena's per-player spawn). Clocks are per player, each sized to that member's band. The gates wait for every member present (below) |
| A player joins late | Never into a run in progress. They take another slot or wait |
| A player leaves mid-dungeon | **Logout:** that member's clock keeps running while they are away (D15, 2.6). Back in time, they resume where they stood. Back too late, they are killed into the blackout on return, with the death rule's costs (2.5). **Clean exit by either rip:** their escrow is paid and the others carry on |

- **Fights:** each member fights their own NPC at each stand and their own boss chain. Two players against one NPC is
  OPEN (`NETHER_DUNGEON_SCOPE.md` X5, *relayed*) and not needed.
- **Gates:** a stand's or the boss's gate opens when **every member present in the slot** has won their own fight
  there. An offline member holds no gate, so a logout cannot stall a partner. A returning member still owes their own
  fight at any stand they have not won, and is paid no escrow for it. A fast member waits on their own clock, which is
  co-op's tension, and nothing else is shared that way.
- **Clocks:** separate, one per member, each with its own greed (D16).
- **Seam:** per-player counts and per-player multipliers (3.3). In co-op the markers credit the nearest member until
  R1 makes the stat exact. One partner's greed costs only them.
- **Death and timeout** end the member they happen to, with the death rule (2.5). The slot frees when its last member
  is gone, or when the last absent member's deadline passes (2.6).
- **The lake:** one legendary per member who has not caught it, each tagged with that member's id, and the cradle's
  ball check (3.7).
- **The keeper's ownership sweep** (Entei's, `data/entei_boss.json:104`) generalises to "is a member of slot k";
  non-members are ejected.
- **Co-op needs the second account** for its proofs (`docs/STATE.md:182`, *relayed*), so it waits on XD8.

---

## 7. The rips (D4, D5)

### 7.1 What a rip is (DM 7.3, the vanilla-built rip)

A rip is built from these parts, none of which teleports by itself, so nothing can misroute:
- a **frame** in the Rift's palette (`world-content-dev` chooses, against `docs/world-building/BUILD_PALETTE.md`);
- **`block_display` entities for a torn edge**;
- **a dark opening** of non-teleporting blocks;
- **keeper particles**: `minecraft:reverse_portal` drawn inward, and `minecraft:portal`. They are re-emitted every 10
  ticks while a player is within 48 blocks, so an unvisited rip costs one distance check;
- **an interaction entity** filling the opening. A click runs `dg/door_click`, the proven arch click (EXP-034).

**Never** a `nether_portal` or `end_portal` block (DM 7.3: they teleport on their own), and never LegendaryMonuments'
distortion portal (D4; DM 7.2: its destination is hard-coded, and one gap in a seal sends a player into a world-critical
mod's dimension).

**Seen from a distance.** Particles render only near the viewer by default, and the `force` mode's reach is ASSUMED.
Probe **V1** settles whether a rip is visible from its approach path. If it is not, the rip gets a tall plume, which V1
also tests.

### 7.2 Entry and exit

**`door_click`** checks, in order, and refuses each with a line:
- the gate flag;
- the lockout (2.5);
- not already in a run;
- no elytra;
- a party over the cap;
- a free slot;
- **the sigil, last** (7.4): the player's free first entry, else a sigil of their band or higher in the inventory.
  It is last so that a refusal for any other reason never touches a sigil.

Then it:
1. reserves the slot, freezes the band, takes the sigil (or marks the free entry used) and adds the run tag (E1);
2. resets the slot's mutables (1, Instancing). The mutable chunks are force-loaded first: every write function
   carries `# chunks-loaded-by:` or `function_limits` refuses it (`tools/function_limits.py:9-18`, *relayed* via DM
   8). The occupancy guard holds: never reset under a player (DM 8);
3. after 40 ticks (Entei's `arrive_delay_ticks`, `data/entei_boss.json:101`) teleports the player to the entry room,
   sets adventure, gives the pick and shows the bar.

**The back rip and the far rip** run `dg/exit`:
1. pay the escrow (9.1); if the player never crossed the threshold, return the sigil instead (7.4);
2. set survival and `clear` the pick;
3. empty and remove the bar;
4. teleport to the overworld rip's outside point, a fixed coordinate in the record, so no return point needs storing
   (unlike Entei's eaten key);
5. free the slot once its last member is out;
6. start the run tag's 100-tick tail; when it ends the keeper removes the tag and runs the claim delivery as the
   player (E1).

### 7.3 Fixed now, random later

- **Fixed:** each rip is a `data/placements.json` record seated on the heightmap (CLAUDE.md "Ground comes from the
  heightmap"), built by a re-apply step, as Entei's room is (R16Q).
- **Random, later** (D5; DM 7.4): a scheduler over authored, validated candidate sites with `random value`, a
  forceload, an expiry countdown, and an announcement. Nothing in this design blocks it. The rip is already an entity
  set plus a frame that a function places and removes. Its cost is section 12's.
- **Sigils work with either** (D21: "A sigil decides who can enter, not where the rip is"). The sigil is checked by
  `door_click` against the clicker's band, not against the rip's place, so a moving rip takes the same sigil as a
  fixed one and nothing in 7.4 names a coordinate.

### 7.4 Sigils: the entry fee, one per band (D21)

**The rule.** Every rip takes a sigil at entry, of the entrant's band (5.1), with one exception (the free first run,
below). The ladder is **per band, not per dungeon**: the Night Shift at band 1 and the Last Cistern at band 1 take the
same sigil, and the Night Shift entered at band 6 takes the band-6 one. That is what makes the fee scale with what the
player can have. The band is the only progress measure the engine already freezes at the rip, and a dungeon's place
says nothing about its entrant (the Night Shift opens at 0 badges and serves every band, 10).

**The ladder.** Made at any crafting table (shapeless), never bought. Values are bank prices; times are the
gathering the inputs take at `data/bank.json`'s declared `rate_per_hour` (raw iron 30, coal 60, raw gold 10, redstone
25, diamond 4, ancient debris 10 by pickaxe and 30 by bed or TNT, `:172-181`). Those rates are the economy's planning
values, not timings, so every time below is ***planning*** too.

| Band (caps) | Badges | Sigil | Recipe | Bank value | Gathering | Why it is affordable then |
|---|---|---|---|---|---|---|
| 1 (20, 25) | 0-1 | **Soot Sigil** | 3 iron ingots + 3 coal | $39 | ~9 min | A stone pickaxe opens the early tier at leg 1 (`data/bank.json:260`). The Old Mine's Lower Galleries are the Night Shift's neighbours, cut at the same adit (`data/mining_caves.json:218-227`), and one reset yields about 8 iron and 10 coal (`:70`, *relayed* there), two sigils' worth |
| 2 (30, 35) | 2-3 | **Gilt Sigil** | 1 gold ingot + 4 iron ingots + 2 redstone | $62 | ~19 min | Gold and redstone are the deep tier: an iron pickaxe below y32 (`data/bank.json:178-179`), which opens at leg 3, the leg played holding 2 badges (`:261`) and so the first band-2 leg |
| 3 (40, 45) | 4-5 | **Glint Sigil** | 1 diamond + 1 gold ingot + 2 iron ingots | $160 | ~25 min | The first diamond: the deep tier's prize, four an hour (`:180`) |
| 4 (50, 55) | 6-7 | **Deepstone Sigil** | 2 diamonds + 1 gold ingot | $262 | ~36 min | Still overworld materials; the Nether is closed until badge 8 (`data/nether_gate.json:7`) |
| 5 (60, 62) | 8 | **Cinder Sigil** | 1 netherite ingot | $900 | ~48 min (32 by bed mining) | The Nether opens with badge 8. A netherite ingot is 4 scrap + 4 gold (`data/bank.json:183`); debris needs the diamond pickaxe a band-3 player already has |
| 6 (100) | Champion | **Rift-Black Sigil** | 1 netherite ingot + 4 netherite scrap | $1,708 | ~72 min (48) | The Tower Ash's tier and nearly its price (2 netherite ingots, $1,800, `data/entei_boss.json:44-46`), less four gold. It is not 2 ingots because two shapeless recipes with one ingredient list make the grid ambiguous (ASSUMED vanilla behaviour; the validator forbids it either way) |

- **Monotone by construction:** each rung costs more value and more gathering than the one below, and netherite
  appears only at bands 5 and 6. Netherite is unpayable before badge 8 because the gate keeps players out
  (`data/nether_gate.json:7`), though "the gate keeps players out, not things" (`:56`): a badge-8 friend can gift
  netherite, and so a band-6 sigil, to a band-1 player, who may then overpay. Nothing is gained by it.
- **Against income** (`data/markets.json:26-27`, measured from the file: $4,033 in leg 1 rising to $68,505 in leg 8),
  every sigil's bank value is under 2% of its band's leg. **The fee is time, not money:** about a third of the band-1 clock
  (9 of 29 minutes, 4.1's planning clock), rising to nearly two clocks at band 6 (72 of 39), where the lockout and the bundles are largest.
- **Challenge mode pays the same** (the Tower Ash's rule, `data/entei_boss.json:46`).
- **No evolution stone, type gem, progression id or spawn-condition block is an input.** Stones and gems are contested
  progression materials (`data/bank.json:141-150`; gems feed 805 TM recipes, `docs/research/DROPS_AUDIT.md:303`).
- **The seam can pay only the band-1 fee, and only at greed.** The band-1 seam yields coal and iron (9.3), so a
  Soot Sigil's six ores can be mined in a run, but only by taking at least 6 seam blocks, past the free tier of 4
  (3.3): a self-funded retry always costs clock. No higher sigil can be mined in its own band's seam: band 2 has no
  gold, bands 3-4 no diamond, and no band any netherite (9.3). The validator holds this (V16).
- **The item.** Each sigil is a distinct pottery sherd with no other use, as the Tower Ash is (`data/entei_boss.json:31`
  gives the reasoning): band 1 `minecraft:miner_pottery_sherd`, 2 `prize`, 3 `explorer`, 4 `danger`, 5 `burn`, 6
  `skull`. Each carries `minecraft:custom_data {cobblers_dg_sigil:<band>}`, an `item_name` in the band's colour, the
  rarity `rare`, and two lore lines: "The rift lets you in for this." and "For a trainer at level cap {caps}." The
  ids are ASSUMED to exist in 1.21.1 (only the mourner sherd is VERIFIED, by the Entei unit). The validator confirms
  each in the vanilla jar and repeats the Entei sweep for any other recipe naming it. A plain sherd found by a player
  has no `custom_data` and is never taken.
- **The recipe book.** The server runs `doLimitedCrafting` (F7), so the dungeon pack gives its six recipes itself,
  with an advancement on `minecraft:tick` that runs `recipe give @s` for each, and does not rely on the TM gate's
  sync. **The recipes are not badge-gated:** the rip already checks the band, so crafting a higher sigil early only
  overpays, and a player who can read the whole ladder in the book can plan for it (Q23). The TM gate's mechanism
  (`data/tm_gate.json:6-12`) could gate them per badge if the owner prefers.

**Consumed at the threshold, returned before it.** `door_click` takes the sigil when it reserves the slot, so a run
in progress has always been paid for. **If the player leaves by the back rip before crossing the threshold, the clock
never started, and `dg/exit` gives the sigil back** (by a loot table that rebuilds it with its components), and the
lockout is not stamped. Past the threshold it is spent, whatever happens next: a clean exit, a death, a timeout or a
dead run on relog.
- **Why on entry, not only on failure.** The owner asked for "an entry fee". A fee taken only on failure is a
  deposit: success would be free, and the fee would stack on a failure already costing $600, the escrow and the
  lockout (2.5). A deposit also has to be held across a death, a logout and a dead run and given back on a clean exit,
  which is three more exit paths to get right. A fee at entry has one point of consumption and nothing to hold.
- **Why the threshold refund.** The entry room is the place to read the board, and "nothing is lost by eating it at
  the wrong time" is already the Tower Ash's rule (`data/entei_boss.json:48`). The board says the sigil is returned
  until the threshold. **No spam cost:** a slot whose last run never crossed the threshold is still clean, so the next
  `door_click` there skips the reset. The lockout is stamped at the threshold (2.5).

**Free rips: one free entry, not a free rip.** **The Night Shift's first run is free, once per player**, a waiver
marked by an advancement at `door_click`, and no sigil is given. It is the tutorial dungeon at 0 badges: a player
arriving from the starter has never seen a sigil, and the first run teaches the clock, the board, the seam and the
death rule. A fee before the first look is a wall, not a decision. Every later entry pays. **No rip is free for
good.** A free band-1 Night Shift would leave the lockout alone gating the band-1 bundle; the Soot Sigil is nine
minutes' mining next door, and "most rips take one" is the owner's rule. The only other candidate is the future
moving rip (7.3), whose scarcity could be its fee. That is the scheduler's question, not this one's (Q19). The Entei
room keeps its Tower Ash (12).

**Lockout, escrow and co-op.**
- **Lockout:** checked before the sigil, so a locked-out player never spends one. A sigil buys one run; the lockout
  caps runs at one an hour per dungeon, so a player spends at most one sigil per dungeon per hour of uptime.
- **Escrow:** the sigil is never escrow. It is never paid back at a clean exit and never forfeit at a death: it was
  spent at the threshold. No reward table may pay a sigil (V16), so a run cannot refund its own fee.
- **Co-op:** each member pays their own sigil, for their own band, because band, clock and lockout are already per
  member (5.1, 6). A member without one is refused alone and the others go in. A partner can hand over a sigil
  item, and the receiver's own band decides whether it counts.
- **Which sigil is taken:** one of the player's own band if held, else the lowest higher band held. A lower band's
  sigil is refused: "This sigil is too weak for you now." Its lore says which caps it serves, so a stale one is
  legible.

**Out of the bank's reach** (a sigil must not be sellable for more than its inputs; here it is not sellable at all):
1. no sell point buys a sigil's base item: each of the six sherds joins `data/bank.json` `never_buy`, and the
   Produce Buyer, every trader buy line and every `exchange_for` price are checked;
2. no counter sells a sigil, a sigil's base item, or anything priced in sigils; the only source is the recipe;
3. no recipe takes a sigil's base item except the decorated pot (the Entei sweep), so a sigil cannot be turned
   into anything, and no recipe turns it back into its inputs;
4. a refund returns the sigil itself, never money or inputs;
5. no dungeon reward table, first-clear prize or escrow table pays a sigil or a sigil's base item;
6. no sigil base item is in the blackout's claim lists, so a recovery claim never takes or returns one.
`tools/economy_audit.py`'s Entei checks are the pattern; V16 generalises them.

---

## 8. Which legendaries

**Rule.** A dungeon's legendary is **unhomed and usable today** (`docs/research/notes/unhomed-legendaries-1.8.0.md`,
group A, 53 species; *relayed*). It is caught only at band 6 (D8), only with a Beast Ball (D7), once per player. The 28
AllTheMons-only species (group C, including Manaphy, Phione and Nihilego) are **unusable** until the client pack ships
(ADR-006). No dungeon takes one. Every pick below is "implemented by" MSD or the jar, so **Mega Showdown is
world-critical for this system**, as it is for Entei (`data/entei_boss.json:10`).

| Dungeon | Lake (Dive) legendary | Why it fits | Boss (NPC chain; band-6 catch, if any) |
|---|---|---|---|
| 1 Night Shift | **Volcanion** (fire/water, MSD, catch 3) | The mine broke into hot water: steam over the sump is the "something is down there" (note's Dive item 4) | the Foreman (NPC); no catch |
| 2 The Street That Ends at Nothing | **Palkia** (water/dragon, MSD) | space folded under a drowned plaza (note item 5) | the city's last warden (NPC) |
| 3 Under the Patriarch | **Suicune** (water, MSD) | the purifier in the pool the roots drink from (note item 1) | Yveltal's chain, catch at band 6 (note item 10) |
| 4 The Last Cistern | **Walking Wake** (paradox, jar model, catch 5) | the reservoir the pumps still fill; paradoxes are dungeon content (D12) | the waterworks keeper (NPC) |
| 5 The Temple Calendar | **Tapu Fini** (water/fairy, MSD) | a misted temple pool (note item 2) | Dialga's chain, catch at band 6 (note item 9) |
| 6 The Tower After the Fire | none | the built room has no lake | **Entei**, built, catchable once (12) |

**Keldeo** is held for a Swords of Justice set, which is not a dungeon (note item 14). **The owner approved these
picks as proposed (D18, 2026-10-08).** The "Boss" column's NPC characters remain a proposal for
`trainer-balance-designer`. Yveltal and Dialga as band-6 bosses are among the approved picks.

---

## 9. Rewards per band

### 9.1 Escrow and payment

Each leg sets an escrow flag on the player. `dg/exit` pays each flag with
`loot give @s loot cobblers:dungeons/<id>/b<band>/<leg>`, the portals pedestal's command (`data/entei_boss.json:126`,
*relayed*). Any death clears the flags (2.5). A logout does not, unless the run dies while the player is away (2.6).

### 9.2 What each leg pays

| Leg | Pays | Paid how |
|---|---|---|
| Each stand | the band's area gems: 1 at bands 1-2, 2 at 3-4, 3 at 5-6, plus a minor battle item at random | escrow |
| Seam | its ores (9.3) | **real drops** |
| Den | the species' own drops | **real drops** |
| Lake cache (bands 2-5; band 1 can reach it only at risk) | one progression item from the band's list | escrow |
| Boss | **the band's progression bundle** (table below) and one roll on the dungeon's battle-item table | escrow |
| Band-6 legendary | the catch | the Pokemon |
| First clear per band | the one-time prize (decided ones below) | advancement plus escrow |

**The rules *stand*** from the old section 4:
- items, never CobbleDollars;
- the generator fails closed on a bankable item, an item any counter sells, an evolution stone, a `*_plate`, an arena
  trophy or the Ability Patch;
- progression ids appear in no generated table but a dungeon's, and the alpha tier tables are overridden empty.

**The progression bundle by band** (*relayed* from the old section 4, itself from `DROPS_PROGRESSION_SPLIT.md`
section 4):

| Band | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Candies | 1 M + 2 S | 3 M | 1 L + 2 M | 2 L + 1 M | 1 XL | 2 XL |
| IV candies | none | none | none | 1-2 | 2-3 | 3-4 |
| Rare Candy | none | none | none | none | 1 | 1-2 |

The cap clamps every candy, so no bundle can overshoot (*relayed*, X3 not run).

**Decided first clears *stand*** (the owner, 2026-10-08, *relayed*): the Night Shift's band 1 is the **Lucky Egg** and
its band 3 an **Electirizer**; the Last Cistern's band 4 is one **Auspicious Armor** and one **Malicious Armor**; every
home's band 5 is one **Rare Candy**. The exact items and weights are `trainer-balance-designer`'s.

### 9.3 The seam by band (Night Shift)

| Bands | Ores |
|---|---|
| 1-2 | coal, iron, copper |
| 3-4 | add gold, redstone, lapis |
| 5-6 | add diamond |

The old cave-yield table *stands*. Every bankable ore is capped per run at the matching cave's per-reset yield, and the
24-block face is sized so that 20 or more is reachable: greed must be possible to be a trade. Whether coal or iron ore
in the pocket draws a spawn-condition Pokemon is moot while the pocket's `the_void` biome spawns nothing, which is
untested (DM 1.4; `data/portals.json` `pocket.generator.biome_why`, *relayed*). The owner allows spawn-condition
blocks (`docs/STATE.md:147`).

### 9.4 Records, not bonuses (Q16)

Best clock left and a flawless clear (no faint) are kept per player, per dungeon, per band, as the arena's best streak
is. **No item pays for time left.** A time bonus would make greed's trade two-sided and harder to read.

---

## 10. How many dungeons, and where

**Decided: the Night Shift only (D19).** The rest are decided after the owner has played it. The target list
is **six**, and each scales to every band from its gate. The count is about places and themes, not band coverage.

| # | Dungeon | Rip home (evidence) | Gate | Legendary |
|---|---|---|---|---|
| 1 | **The Night Shift** | the old mine west of Route 1; the rip in the notch before the adit portal (x 1347, z 4120), on the carts' trail toward Route 1 (`tools/route1_old_mine.py:49-61`, *read*) | none (0 badges) | Volcanion |
| 2 | The Street That Ends at Nothing | the Scar, the road's end (centre 2110, 950; `data/towns.json:2059-2073`, *relayed*) | none; first reachable about gym 2-3 | Palkia |
| 3 | Under the Patriarch | the Patriarch's foot (4272, 3600; `data/towns.json:2570-2606`, *relayed*) | none; about gym 6-7 | Suicune; Yveltal as the boss |
| 4 | The Last Cistern | the Dry Cistern (4530, 5850; `data/dry_cistern.json:16-28`, *relayed*; authored, not applied) | none; about gym 7 | Walking Wake |
| 5 | The Temple Calendar | a long-isle jungle temple, e.g. (7200, 7528) (`data/jungle_temples.json:85-89`, *relayed*; ground NOT measured) | `gym8_cleared` proposed (`DUNGEON_PLACEMENT.md` Q13, OPEN) | Tapu Fini; Dialga as the boss |
| 6 | The Tower After the Fire | the Nether; the key is eaten anywhere there (12) | `champion_cleared` | Entei |
| later | The Crucible (Heatran) | the Nether | `champion_cleared` | Heatran |

- **The gap *stands*:** nothing is first reachable between gym 3 and gym 6 in the north and centre. The Merian Hut or
  the Sentinel would fill it (old section 3, *relayed*).
- **Rejected *stands*:** the Sunken Court, whose centre is under water (old P-finding; CLAUDE.md "Measure before
  relaying").
- **Coordinates in this table are the homes' records, not rip cells.** Each rip cell is chosen by `world-content-dev`
  on `tools/ground.py` ground and validated before it enters `data/` (`.claude/rules/datapacks.md` "Coordinates").

---

## 11. The first dungeon, specified for a builder: The Night Shift

**Why it is first.** Open at 0 badges, so one staging run repeats at caps 20, 45, 60 and 100 by granting flags. It
exercises **every leg kind**: three stands, the staged boss, the seam, parkour, the den, and the lake, which is closed
at bands 1-5 and a Dive catch at band 6. Entei cannot be first: it is gated at the Champion, so it tests one band and no
legs (12).

**Theme** (*stands*, old section 3): the old mine's last shift broke into a lower level the night the south drift fell,
and came up without their foreman. The lamps down there are still lit. In the new fiction the lower level is a piece of
the Rift, and the rip in the notch is where it shows. Rosters come from the shift's own families (old section 3,
*relayed*: Timburr, Machop, Geodude, Roggenrola, Onix, Diglett, Drilbur); `trainer-balance-designer` chooses.

### 11.1 The spine (segment by segment; x increases from the entry)

| # | Segment | Kind | Spine blocks | Contents |
|---|---|---|---|---|
| 0 | The Lamp Room | `rip_room` (entry) | 16 | arrival; the back rip; the run board (2.4); the threshold box starts the clock |
| 1 | The Main Drift | `drift` | 300 | 5 wide, 4 high, timber sets every 4, lanterns; falls 8 |
| 2 | The Hand's stand | `stand` | 24 | hall 13 x 24 x 8; trainer at the far third; timber gate (barrier-backed) |
| 3 | The Old Incline | `drift` | 250 | stairs down 20 |
| 4 | The Shotfirer's stand | `stand` | 24 | as 2 |
| 5 | The Lower Face | `seam` | 30 | 24 seam blocks in a 9 x 4 face; the ladder board |
| 5a | The Powerhouse | `den`, a side room off 5 | 0 (20 deep, off-spine) | the Electirizer den (D11) |
| 6 | The Wet Drift | `drift` | 300 | dripping; ends on the gantry |
| 7 | The Sump | `lake`, below the gantry | 0 (off-spine) | shaft 24 x 24, water 40 deep; cache at 30; membrane and bed (3.7); steam |
| 8 | The Collapse | `parkour` | 200 | 4 sections of 50: broken trestles, hung cages, ore carts over a hall 20 deep; catch floor 6 below the route; ceiling 3-4 above it; checkpoints at both ends of each section; the cracked-lamp line and the gate box at entry |
| 9 | The Haulage | `drift` | 250 | rails taken up (no rail blocks: they draw spawns, `tools/route1_old_mine.py:30-31`) |
| 10 | The Timberman's stand | `stand` | 24 | as 2 |
| 11 | The Shift Road | `drift` | 200 | rising to the stope |
| 12 | The Stope | `boss_arena` | 30 | 27 x 27 x 14; the Foreman, three stages (3.2) |
| 13 | The Shift Bell | `rip_room` (exit) | 16 | the far rip; escrow paid |
| | **Total** | | **1,664** | 1,464 walking + 200 parkour, inside a 2,048 strip |

Drifts may bend in z inside the 64-wide strip. The spine length is measured along the walked path, never along x.
Every size is a proposal the builder settles against the validator.

**Segment kinds are parametrised and shared by every later dungeon:** `rip_room`, `drift`, `stand`, `seam`, `den`,
`lake`, `parkour` and `boss_arena`. Each joins the next at one **door contract**: 3 wide and 4 high, on the spine
centreline, at the segment's floor y. The kinds are what a second dungeon reuses with a new palette and order, and
what a generator would sequence (12).

### 11.2 Data: `data/dungeons.json` (schema `cobblers.dungeons/2`, `generated_by: "hand"`)

- **`engine`** (shared):
  - `pocket` (read from `data/portals.json`, failing closed on disagreement, as Entei does);
  - `clock` with:
    - `units_per_tick: 4`;
    - `period_ticks: 20`;
    - `ladder` (3.3);
    - `fall_penalty_s: 15`;
    - `slack_factor: 1.25`;
    - `paces` (4.1), each with a `basis` naming its probe;
  - `bands` (5.3, each with its progression bundle);
  - `lockout_ticks: 72000`;
  - `uptime_objective`;
  - `escrow`, `adventure`, `rift_pick` (components), `sweep` (no-deploy box rules);
  - `battle_rules` (the arena's), `payout: "clawback"`;
  - `claims_exempt_tag` (read from `data/blackout.json`), and `death` (2.5): the player-side no-claim rule keyed on
    the run tag, which is `data/blackout.json` `dungeon_exempt.player_tag` (proposed `cobblers.dungeon_run`,
    `DUNGEON_DEATH.md` section 4 rule 1; read, never copied), its `tail_ticks: 100` (E1), and `messages.death`
    (titles by cause, the five chat lines);
  - `sigils` (7.4): per band the id, sherd item, name, colour, lore and recipe; `accept: "own_or_higher"`;
    `refund_before_threshold: true`; `free_first_entry: ["night_shift"]`; and each recipe's `why`;
  - `absence` (2.6): the `dg.seen` stamp, the per-slot deadline, and the dead-run check's order (before the eject);
  - `slots_per_dungeon: 4`, `members_max: 1` (co-op raises it).
- **`dungeons[]`.** The `night_shift` record:
  - `rip`: the placement id, the outside point, facing, the plume flag;
  - `gate_flag: null`;
  - `slot_rows`: derived;
  - `spine[]`: segment kind, length and params, as 11.1;
  - `stands[]`: name, families by band, the dialogue key;
  - `boss`: `stages_by_band` (3 x 6: level offset, moves, held item, escort from band 4);
  - `seam`: `blocks: 24`, `ores_by_band`, `yield_cap_by_band`;
  - `den` (*stands*, old 2.3);
  - `lake`:
    - `species: cobblemon:volcanion`, `catch_band: 6`, `props`;
    - `depth: 40`, `cache_depth: 30`, `cache_by_band`;
    - `membrane: "dive_qualified"`, `obvious` (pose, glow, lanterns, bubbles, steam);
    - `key_boss: true`;
  - `rewards`: escrow tables by band and leg, first clears;
  - `messages`;
  - `does_not_cover`, stating what the run's lists miss, per CLAUDE.md "Our list is not the world". For example: Pokemon
    a player sends out outside parkour boxes; items dropped in the slot.
- `data/key_ball.json` `bosses` gains the Night Shift's Volcanion; it carries the tag, and the validator checks the two
  agree. `data/placements.json` gains the rip.

### 11.3 Generator, runtime, re-apply (`tools/dungeon.py`, generalising `tools/entei_boss.py`)

- **Pack:** `build/datapacks/cobblers_dungeons`, world-local; NPC classes inside it, so a change needs a restart.
- **Re-apply step (new): the shells.** The step places each slot's shell from the spine:
  - fills of at most 32,768 blocks;
  - forceloads of at most 256 chunks per add. A 2,048 x 64 strip is about 512 chunks, so two batches;
  - every write function declares `chunks-loaded-by`;
  - a second step places the rip.

  The shell's block count is the builder's to report; the step's run time is probe I2.
- **Functions:**
  - `door_click`, `enter`, `exit`;
  - `keeper` (per pass, per live member):
    - the clock and the bar;
    - the return margin;
    - the ownership sweep and eject;
    - the seam markers and the rate;
    - the parkour sweep and the catch bands;
    - the gates;
    - the stand and boss spawns;
    - the membrane;
    - timeout and sudden death;
    - the absence gap, the slot deadline and the dead-run check (2.6), run first;
    - the death handling on respawn: escrow cleared, survival, pick, bar, slot, the 2.5 messages, the run tag's tail
      started (never the tag removed, E1);
    - the tail countdown, then the tag removed and the claim delivery run (E1);
    - the survival, pick and stale-tag backstop over the overworld;
  - `stand`, `boss_stage`, `seam_reset`, `lake`, `den`, `pay`.
- **Callbacks** (`data/cobblemon/callbacks/<event>/cobblers_dg_*.molang`): `battle_victory`, `battle_fainted` (the
  den) and `pokemon_captured` (the lake). The key ball's callbacks already exist (`tools/key_ball.py`).
- **The keeper's cost** is per live member. An idle dungeon costs one check per pass, measured against
  `docs/mechanics/TOWN_TICK_BUDGET.md`'s idle floor.
- **Sigils** (7.4): the six recipes and their `recipe give` advancement; the sigil step in `door_click` (count, take
  one of the right band, or the free entry); the threshold refund loot tables.

**E1. The run tag: a required part of the engine build (D22), not a later fix.** It is what makes D20 true in the
code. The blackout half is `minecraft-systems-dev`'s change to `tools/blackout_pack.py`, built and audited with the
engine, never after it. From `docs/research/DUNGEON_DEATH.md` section 4, with the two gaps the owner named made
explicit:
1. **One player tag for the run**, read from `data/blackout.json` `dungeon_exempt.player_tag`. It is **added by
   `door_click` in the function that reserves the slot, before the 40-tick arrival delay**, so a wild hit taken at
   the rip's mouth just before the teleport is already covered.
2. **The blackout exempts a player holding it** in `blackout/battle_loss_wild`, beside the victor test
   (`tools/blackout_pack.py:229`), and again as the first line of `recovery/make`. It sets no `bo.clm 2`, so no money
   is held. The charge and the return run unchanged. It is **not** added to `battle_loss_npc`, which takes no items.
3. **The kill-credit window (the owner's case).** Vanilla credits a death to the last mob that hurt the player within
   100 ticks, whatever finally killed them (ASSUMED, vanilla `getKillCredit`; `DUNGEON_DEATH.md` section 2 item 4).
   So the timer's `kill @s`, a fall, lava or the dead-run kill on relog, within five seconds of a wild hit, arrives
   at the blackout as a wild kill (M4) and would make a claim. **Rule 2 covers it, because the exemption reads the
   player, never the killer: a run-tagged player makes no claim, however the death is credited.** Three timing
   requirements keep it covering every case:
   - **the engine never clears the tag before the blackout has read it.** The run's death handling runs on respawn,
     after the blackout's death path, and the tag is removed only at the end of the tail below;
   - **the tag outlives the run by a tail of 100 ticks** (`tail_ticks`, equal to the credit window) after every way
     out: a clean exit, the eject, the respawn after a death and the dead-run kill. A hit taken in the slot cannot
     then credit an overworld death a second later. The cost is a leniency, never a loss: an overworld wild Pokemon
     that kills the player inside those five seconds makes no claim either;
   - **the tag cannot go stale.** The overworld backstop sweep (3.3) removes it from any player outside
     `cobblers:pocket` with no live run and no tail left, including after a logout during the tail. A stale tag would
     exempt a player in the overworld for good.
4. **The claim delivery gap.** A claim settled while its owner is in a run (a friend beats the guardian of an older
   loss) is summoned `as @a at @s`, at the owner's feet: inside the slot, where a full inventory, a death or the
   eject loses it to the reset (`DUNGEON_DEATH.md` section 2 item 3, M9). So:
   - `recovery/deliver` and the login delivery **return for a player holding the run tag**, leaving the claim as
     settled-and-waiting;
   - **when the tail ends, the keeper removes the tag and runs `function cobblers:recovery/deliver` as the player**,
     who is then in the overworld. A player who logs out during a run gets their delivery at the end of the tail
     after they return, not at login inside the slot.
5. **Every keeper-spawned wild Pokemon still carries `claims.exempt_tag`** (den, boss stages, the lake). The den must
   gain it (`DUNGEON_DEATH.md` section 2 item 2). This is the second layer, not the rule.
6. **The clawback and sudden death are ordered.** After a won stand battle at clock 0 the $600 charge would land
   inside the NPC payout clawback's measuring window (`DUNGEON_DEATH.md` section 2 item 5). The engine runs the
   clawback to completion before the sudden-death kill.
7. **The rift pick is taken by its component**, never by item id (`DUNGEON_DEATH.md` section 4 rule 6).

`tests/test_dungeon_death.py` already holds the generated pack to rules 2 and 4 as **xfail(strict)** until
`dungeon_exempt` exists (`DUNGEON_DEATH.md` section 5). E1 is done when those pass unmarked, V15 passes against the
generated functions, and DX1 is seen in game.

### 11.4 Validation (`tools/validate_data.py` and an independent audit; `test-author`, not the builder)

| # | Check | Independent of the builder how |
|---|---|---|
| V1 | Slots are inside the border margin and disjoint from the rescue box, Entei's row and each other | computed from `data/portals.json` and `data/entei_boss.json`, not from `tools/dungeon.py` |
| V2 | The rip cell traces to `tools/ground.py` ground, and its outside point is clear and walkable | the heightmap |
| V3 | **The clock per band equals ceil(required x slack)**, with walking measured as **the BFS path length over the GENERATED shell** from the entry threshold to the far rip | the shell's blocks, not the spine list. The mutation that proves it: lengthen a drift inside the generator only, and V3 must fail |
| V4 | Softlock: the back rip is reachable from every walkable cell with every gate in every state it can hold (closed ahead, open behind) | BFS over the shell |
| V5 | Every NPC, boss and legendary spot is on floor with 2 air, inside the keeper box, and inside a room of at least the boss arena's clear area | the shell |
| V6 | **Parkour:** every gap column has a catch band under it; every jump is feasible **in both directions** (flat gap at most 3, a rise at most 1 with a gap at most 2); the ceiling is 3-4 above the route; the no-deploy box covers the section's whole air volume | the shell |
| V7 | **Lake:** the cache is at most 30 deep (Surf reach); the membrane sits at the bottom; no water leaks outside the sump | the shell and `data/blackout.json` |
| V8 | No lava, magma, campfire, fluid leak or fall without a catch band; nothing walkable at block light 0 (`tools/light_plan.py`) | the shell |
| V9 | The seam's 24 blocks are seam ores; every seam block has a marker in the reset; the seam box is disjoint from every other box | the reset function's output against the shell |
| V10 | Rewards: the old fail-closed list; progression is exclusive (the mutation: `exp_candy_xs` back in the tier-1 alpha override must fail); escrow ids exist as loot tables | the data and the pack |
| V11 | The lake legendary is in `data/key_ball.json` `bosses`, at level at most the cap of band 6 (100), gated at band 6 only; no dungeon Pokemon is an alpha | the two data files |
| V12 | `lockout_ticks` is at least the longest clock in ticks | the data |
| V13 | Every exit path (`exit`, the respawn, eject, a dead run on relog) restores survival and clears the pick; a live run on relog keeps adventure and the pick | the generated functions, path by path |
| V15 | **No claim in a dungeon:** every `spawnnpcat` and `spawnpokemonat` the engine emits tags the entity with `claims.exempt_tag` in the same function; the blackout's claim step has the player-side run-tag exemption; the tag is added in `door_click` before the arrival delay; no function removes it except the tail's end and the backstop; the tail is at least the credit window (100 ticks); `recovery/deliver` and the login delivery return for a tagged player, and the tail's end runs the delivery (E1) | the generated functions of both packs and `data/blackout.json`, not `tools/dungeon.py`'s own spawn list. Mutations, each inside a generator: drop the tag from one stand's spawn; remove the tag in the respawn handler; drop the deliver guard. V15 must fail on each. A simulated case: a wild hit, then the timer's kill 60 ticks later, makes no claim |
| V16 | **Sigils:** one per band 1-6; bank value and planning gathering time strictly rise with band; netherite (ingot, scrap, debris) only in bands 5-6; no input is an evolution stone, gem, progression id or spawn-condition block; no two crafting recipes on the server share an ingredient list with a sigil's (the Tower Ash's included); each base item exists in the 1.21.1 jar, is named by no other recipe but the decorated pot, is on `never_buy`, and is in no sell point, counter stock, `exchange_for`, reward, escrow or claim list; the band-1 sigil's ore count exceeds the seam's free tier (4) and no higher sigil's inputs are all in its own band's seam table | `data/bank.json`, `data/markets.json`, `data/produce_buyer.json`, `data/traders.json`, `data/blackout.json`, the server's recipe sweep (as `tools/tm_gate.py` sweeps), not `tools/dungeon.py`. The recipes and seam ores are read from the GENERATED pack. Mutations, each inside the generator with the data untouched: emit the band-2 recipe with a diamond, and the generated-against-data check must fail; emit gold ore in the band-2 seam reset, and the self-funding check must fail |
| V14 | `python tools/id_authorship.py` stays at 0 faults; ids are prefixed `dg_` | the tool |

**New contracts** in `data/system_contracts.json`:
- "dungeon NPCs carry no rctmod series" (consumer: the level cap; *stands*);
- "dungeon wins pay $0 net" (consumer: the economy; *stands*);
- "a dungeon death is a blackout death with no recovery claim: the money taken and not held, the checkpoint,
  keepInventory, whatever the cause, however vanilla credits the kill; and no claim is delivered into a slot" (owner:
  `recovery_claims`; consumer: the dungeons; beside C12; E1);
- "a sigil is never bought and never sold" (owner: the dungeons; consumers: the bank, the Produce Buyer, the markets;
  7.4, V16);
- "the water ladder qualifies Dive in the pocket" (consumer: the lake; beside C15).

### 11.5 Runtime proof (a new EXP; the builder designs it, the main session runs it, `qa-reviewer` grades it)

A whole run is played at caps 20, 45, 60 and 100 (flags granted on staging), and timed per leg (XT1's second pass).
Each of the following is seen once:
- greed at 5 and at 20;
- a fall;
- a forfeit;
- a loss to a stand and to a boss stage, each with a claim-eligible item carried (balls, medicine): the item kept, no
  guardian, the money taken and not held, the 2.5 lines shown (DX1 in a full run);
- a timeout outside a battle and inside one (sudden death), and a timeout within five seconds of a wild hit: no
  claim (E1);
- the sigil: the free first entry, a sigil taken at each band, a locked-out click that keeps it, a lower band's
  sigil refused, and a sigil returned on leaving before the threshold (SG1 in a full run);
- a turn-back at x3;
- a logout shorter than the clock (resumed, the gap charged) and one longer (killed on return, the 2.6 lines);
- the band-6 Volcanion caught with a Beast Ball, and a Great Ball refused and handed back.

Probes present / probes total are reported, per CLAUDE.md "A success report is not the work".

---

## 12. The Entei room's fit

**Verdict: keep it as built, run it first, and fold it into this shape later. Do not rebuild it first.**

**What does not fit:**
- It is one 17 x 17 room with no spine and no legs (`data/entei_boss.json:96`).
- It has no clock. Its lockout is a game-time delta, the defect class of 2.1 (`:112`).
- Its boss is single-stage and wild.
- It is entered by a key eaten in the Nether, not a rip.

**What fits, and is half this engine:**
- per-player slots in the pocket, the keeper, the ownership sweep and eject (`:104`);
- the arrival delay, the logout rule, catch-once by advancement and the claims exemption (`:132`);
- the key-ball tag;
- the macro spawn and bind.

**EXP-059 is the cheapest real test of all of it**, and it is NOT_EXECUTED with three recorded defects (the old P1,
*relayed*). Running it first proves or breaks the machinery the timed engine copies, before two builders copy it.

**Later**, as dungeon 6, on the engine:
- the room becomes the Tower's boss arena at the end of a spine;
- Entei becomes the band-6 catch after an NPC chain: the tower's last mourner, whose ace is Entei's grief;
- the game-time lockout is replaced by the uptime counter (2.5);
- **the eaten Tower Ash stays as the Nether's rip.** No Nether ground can be measured (`:52`), so the key opens a
  short-lived visual rip at the player for the 40-tick delay, and the player carries the rip.
- **The Tower Ash is already the band-6 fee in another form** (D21: "as Entei's room does"): 2 netherite ingots,
  $1,800 (`:44-46`), beside the Rift-Black Sigil's $1,708 (7.4). It keeps its own item, recipe and eat-to-enter
  mechanism, and nothing in 7.4 touches the built Entei unit. At the re-home the owner can merge the two, so that one
  band-6 item opens both; until then the validator only forbids their recipes from colliding (V16).

That re-home is a "further dungeon" unit (13), about 7M.

---

## 13. Build order and cost

**Rates** (CLAUDE.md "What a builder actually costs", measured 2026-10-02; the audit and prepare figures are the brief's,
*relayed*):
- an end-to-end builder 3.4-4.6M (4M used, 4.5M for the engine, which is larger than Entei's 2,926 lines, F4);
- a narrow follow-up 2.6M;
- an independent audit about 3M (Opus, escalation case 1: the timer kills players and the run can trap one);
- research about 0.6M;
- a prepare 30-50 minutes.

**None of the costs below is a measurement of this work.**

| # | Step | Agent | Cost |
|---|---|---|---|
| 0 | Run EXP-059 on staging; fix its three recorded defects | main session + the owner | 2.5M (*relayed* estimate, old 1.2) |
| 1 | The probe pack (section 14: P1, B1, B2, B3, R1, R2, F1, L1, L2, C1, XT1, V1, I2, LO1, SG1; DX1 waits for E1 in step 5) | `minecraft-systems-dev`, narrow | 2.6M |
| 2 | Run the probes; time a fight per band (XT1) | main session + the owner | 2M |
| 3 | Night Shift rosters, boss stages, escrow tables, the clock per band re-derived from XT1 | `trainer-balance-designer` (opus) | 1.5M |
| 4 | Night Shift spine, palettes, dressing, the rip cell on `ground.py` | `world-content-dev` (data only) | 2M |
| 5 | Engine core: rip, slots, clock, bar, return margin, timeout and sudden death, the death rule with the run tag (E1, both packs), escrow, the absence gap and dead-run check, lockout, sigils (7.4), adventure and pick, sweeps | `minecraft-systems-dev` | 4.5M (the sigils and E1 are inside this estimate, ASSUMED, not re-costed) |
| 6 | Legs: stands and clawback, the boss chain, seam markers and rate, parkour sweep and catch bands, the lake with membrane and catch, the den | `minecraft-systems-dev` | 4.5M |
| 7 | The shell generator from segment kinds; the re-apply steps | `minecraft-systems-dev` | 4M |
| 8 | Independent audit A: engine and legs (timer deaths, escrow, exits, economy) | `test-author`, opus | 3M |
| 9 | Independent audit B: geometry (V3-V9 over the built shell; mutate the generator) | `test-author`, opus | 3M |
| 10 | Integration: 2-3 prepares, the full suite, install, the 11.5 run at four caps | main session | 3M |
| 11 | Retune the clock and fix from the owner's play | narrow follow-up | 2.6M |
| | **To the first complete dungeon** | | **about 35M (range 30-40M)** |

**Ordering (the owner's, D19: EXP-059 first, then the probes, the data, the engine; the Night Shift only):**
- 0-2 before anything is built: principle 15, and they can kill a mechanism cheaply;
- 3 and 4 fix the data the generator reads;
- 5 before 6 and 7, which can then run in parallel (two builders, one wave);
- 8 and 9 in parallel;
- each audit sees a different builder's work.

**What follows the first dungeon:**

| | Cost each |
|---|---|
| Further dungeon, authored, one variant (design 1M, world data 2M, balance 1.5M, audit runs and look 1.5M, integration 1M) | **about 7M** |
| ... with a new leg mechanic, such as a parkour-guarded shrine | +2.6M |
| Second variant of an existing dungeon (spine data 1.5M, audit run 0.5M, staging 0.5M; its slot shells re-applied) | **about 2.5M** |
| Six dungeons, one variant each (35 + 5 x 7) | **about 70M** |
| ... plus a second variant each (+6 x 2.5) | **about 85M** |

### 13.1 Authored vs generated, costed

**What changes from the hub design.** In a linear run the expensive parts are shared by both options: the engine, the
segment kinds, and both audits. Audit B already walks any shell, so it checks a generated one as readily as an
authored one. Connectivity is by construction, since segments join end to end at one door contract. The old design's
14-class generator validator (old 1.3) is therefore mostly gone. **A "generator" here is a sequencer:** a tool that
picks segment kinds, order and lengths from a seed to meet a band budget, and emits a spine that audit B then
validates. It runs at build time in Python, never at run time. ADR-008's rule that mcfunction cannot prove a layout
stands.

**Rotation costs nothing at run time either way.** Each dungeon's 4 slot shells can hold up to 4 variants, and entry
assigns a free slot whose variant differs from the player's last.

| | Authored | Generated (sequencer) |
|---|---|---|
| Up front | nothing | sequencer builder 4M + its independent audit 3M = **7M** |
| Per variant | about 2.5M (hand-written spine data, audit run, look) | **about 0.5M** (a seed, audit run, the owner's look) |
| Break-even | | at about 3.5 extra variants in all (7 / 2.0) |
| Six dungeons, one extra variant each | +15M | +7M + 3M = **+10M** (saves about 5M) |
| Six dungeons, three variants each | +30M | +7M + 6M = **+13M** (saves about 17M) |
| Quality | set pieces placed for the theme: the lake after the seam on purpose, sightlines, the board's story | rhythm from a rule; set pieces must still be authored and inserted, so the lake and the boss arena are fixed templates either way |

**Recommendation: authored**, as the owner leans. Below about four extra variants in all, the sequencer does not pay.
The things a player remembers (the steam over the sump seen from the gantry, the order that makes greed and the
legendary exclude each other) are authorial. **Revisit at dungeon 3** if the owner wants three or more variants per
dungeon. The segment kinds are built so the sequencer can be added then without rework.

---

## 14. Unknowns, as probes (before step 5; DM section 10 unless marked new)

| Id | Probe | Settles |
|---|---|---|
| P1 | `runmolang "q.pokemon.discard;"` on an own sent-out Pokemon, by keeper and from `pokemon_sent_post`: it vanishes, the party Pokemon keeps its HP and can be recalled | 3.4, the no-deploy leg |
| B1 | A per-player bossbar with its name re-set each second from scores; log out and in; clear | 2.2 |
| B2 | `kill @s` with a totem in the off hand; the blackout fires once | 2.5 |
| B3 | Sudden death: the clock at 0 mid-battle, the kill when `in_battle` reads 0 | 2.5 |
| R1 | `minecraft.mined` counts in adventure mode with the rift pick under `can_break` | 3.3, co-op credit |
| R2 | `minecraft:can_break` on a pick in adventure mode breaks the seam ores and nothing else | 3.3 |
| F1 | A teleport mid-fall, with and without `resistance 5` | 3.5 |
| L1 | Glow, lanterns, a bubble column and a beacon read from a gantry 40 above the bed | 3.7, "obvious" |
| L2 | A wild battle started and finished underwater, with Dive | 3.7 (fallback: dry chamber) |
| **C1 (new)** | **The first chained fight.** Heaven's Arena proved spawn, start, win, loss, re-roll and remove one at a time and never chained one fight into the next; `docs/STATE.md:225` lists the in-function spawn as NOT proven. C1 proves both: `spawnnpcat` from a **macro line in a function** after a plain restart, then a victory's follow-up starting the next battle 60 ticks later, three times in a row | 3.1, 3.2 (F3) |
| **LO1 (new)** | Log out mid-run for less than the clock left and for more. Read the clock on return against `gap x rate`, the slot freed at its deadline while the player is away, and the dead-run kill on the first pass back. Also log out mid-battle: what Cobblemon does with the battle and the NPC. And stop the server for a minute mid-run: no clock lost | 2.6 |
| **DX1 (new)** | Inside a run, carrying claim-eligible items: lose to a stand NPC, to a boss stage, to a tagged wild Pokemon and to an UNTAGGED one, and die by `kill` and in lava, each also within five seconds of a wild hit. Each must charge the money, make no claim (no guardian, nothing held), keep every item, and show the 2.5 lines. And: a claim settled by a second player while the owner is in a run is delivered in the overworld at the tail's end, not in the slot. Runs after E1 is built | 2.5, E1 |
| **SG1 (new)** | `clear @s minecraft:miner_pottery_sherd[minecraft:custom_data~{cobblers_dg_sigil:1}] 1` takes one sigil and leaves a plain sherd and a band-2 sigil (syntax ASSUMED, the R2 class); the recipe result carries its components (EXP-059 X3 covers the Tower Ash's); the `recipe give` advancement makes the recipe craftable under `doLimitedCrafting` for a player synced before the pack went in (F7) | 7.4 |
| **XT1 (new)** | Time an NPC fight at 2, 4 and 6 opposing members at caps 20, 45 and 100, and a 3-stage chain | the clock (4.1) |
| **V1 (new)** | A rip's particles and display seen from 32, 64 and 128 blocks; `force` mode and a plume | 7.1 |
| **I2 (new)** | The time and block count of one slot's shell re-apply | 11.3, the re-apply budget |
| XD2 | Pool classes by `npcLevels` and MoLang team size (old 7.4) | 5.3 (fallback: classes per band) |
| XD3 | The clawback leaves $0 net (old 7.4; EXP-060) | 3.1 |
| XD8 | Two players in two slots, then one co-op slot (needs the second account) | 6 |
| EXP-064 | The Beast Ball key on a tagged boss (NOT_EXECUTED) | 3.7 |

Dropped from DM's list, with the reason:
- **B4**: no pause, so idling buys nothing;
- **G1 and G2**: no LegendaryMonuments portal, and fixed rips;
- **S1-S4**: a chain of classes, not a staged party or `set_npc_party`;
- **I1**: the shells are fills, not templates;
- **XD1**: no rebuild on entry; I2 replaces it.

---

## 15. Questions for the owner (numbered; the decided ones point at section 0.1)

1. **DECIDED (D13).** The greed ladder: x1.25 at 5, x1.5 at 10, x2.0 at 15, x3 at 20, holding for the rest of the run.
2. **DECIDED (D14).** Slack 1.25 x the planning budget (29-39 minutes by band), re-derived from XT1's timings before
   it ships.
3. **DECIDED (D20, D22).** Death, by the timer or anything else, is the blackout ($600, checkpoint, inventory kept)
   plus the escrow forfeit; the retry costs another sigil and the lockout. No claim is made in a dungeon (2.5). The
   code check has reported that the rule is not met today (F8); the run tag (E1) is built with the engine.
4. **DECIDED (D15).** A logout does not stop the clock. Back in time, the run resumes. Back too late, the player is
   killed into the blackout on return (2.6). This replaces the recommendation to end the run without a kill.
5. **OPEN. Healing in a run: none provided; your own potions between fights, priced in clock; no bag items in
   battle?** *Recommend yes.* The clock is the healing restriction the vision asks of gauntlets
   (`GAME_VISION.md:143-145`).
6. **DECIDED (D16).** Solo first; co-op (up to 4 in a slot) after XD8.
7. **DECIDED (D16).** Separate clocks in co-op, each with its own greed. The gates wait for every member present (6).
8. **OPEN. Riding allowed outside the parkour?** *Recommend yes.* The budget assumes foot, so a mount is earned slack.
   A run-wide sweep would remove battle send-outs.
9. **DECIDED (D17).** Lockout one hour of server uptime per dungeon per player, counted from entry.
10. **DECIDED (D21), against this question's recommendation.** Most rips take a sigil, scaled by band (7.4). The
    recommendation of free overworld entry is withdrawn.
11. **OPEN. A fall costs 15 seconds and a return to the last checkpoint?** *Recommend yes.* About 35 seconds a fall
    in all.
12. **OPEN. Before the Champion, the lake legendary is visible, asleep and sealed ("It does not stir for you yet"),
    with a Surf-depth cache from band 2?** *Recommend yes.* It rewards noticing at every band and keeps D8.
13. **DECIDED (D18).** The legendaries of section 8, as proposed.
14. **DECIDED (D19).** Build only the Night Shift until you have played it; six stays the target.
15. **Half DECIDED (D19): EXP-059 runs first. OPEN: keep the Entei room as built and re-home it on the engine as
    dungeon 6 later, with the Tower Ash as its rip?** *Recommend yes.*
16. **OPEN. Records for time left, never items?** *Recommend yes.* A time bonus muddies greed's trade.
17. **RESOLVED in the vision (the owner asked that the disagreement not sit, 2026-10-08).** `GAME_VISION.md:138`
    "Progress persists" now names the player's progress: catches, items, flags, first clears, badges and money. It
    keeps a dungeon's own state persistent only for puzzle dungeons; a timed rift run resets its rooms on every entry.
    Persistent puzzle dungeons stay a separate future kind. The owner can reverse this.
18. **OPEN. Authored dungeons; reconsider a sequencer at dungeon 3 if you want three or more variants per dungeon?**
    *Recommend yes* (13.1).
19. **OPEN. A random rip scheduler only after two fixed dungeons are played?** *Recommend yes* (D5). It adds a
    scheduler, an expiry and a candidate validator, about one narrow unit (2.6M) plus an audit. A moving rip takes
    the same sigil (7.3); whether its scarcity should make it free is decided with the scheduler.
20. **OPEN, the recommendation NOT accepted (the owner, 2026-10-08, asked with Q21-Q23 and left unticked; their
    alternative not yet given). The Night Shift's first run free, once per player, as a waiver (no sigil given); no
    rip free for good?** *Recommended yes* (7.4). Until the owner says otherwise, build nothing that depends on the
    waiver.
21. **DECIDED (the owner, 2026-10-08): yes. "Entry" in D17 read as the threshold: the sigil is returned and no
    lockout is stamped for a player who leaves by the back rip without crossing it** (7.4, 2.5).
22. **DECIDED (the owner, 2026-10-08): yes, as priced; retuned when gathering is timed. The ladder of 7.4: Soot (3 iron, 3 coal), Gilt (1 gold, 4 iron, 2 redstone), Glint (1 diamond,
    1 gold, 2 iron), Deepstone (2 diamonds, 1 gold), Cinder (1 netherite ingot), Rift-Black (1 netherite ingot, 4
    scrap).** A higher band's sigil is accepted for a lower band; a lower one is refused.
23. **OPEN, the recommendation NOT accepted (the owner, 2026-10-08, as Q20). Sigil recipes visible from the start,
    not badge-gated?** *Recommended yes*: the rip checks the band, so the gate would only hide the ladder (7.4). The
    alternative 7.4 names is the TM gate's per-badge recipe-book mechanism (`data/tm_gate.json`); not chosen yet.

**Still open from other documents**, untouched by this design: `DUNGEON_PLACEMENT.md` Q12-Q15 (its Q11 is decided, D8), and its band-4 paradox
threats; `DROPS_PROGRESSION_SPLIT.md` Q2, Q4 and Q5 (old 8.11-8.14).
