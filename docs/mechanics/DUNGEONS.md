# Dungeons: many runs, one engine, authored rooms on fixed sockets

**Status: DESIGN AND COSTING ONLY (content-architect, 2026-10-08).** Nothing here is built, placed, generated or run.
It answers the owner's brief of 2026-10-08 ("MANY DUNGEONS ... cost two approaches before building either ... build one
completely before building six partially"). The architectural choice is proposed as
`docs/decisions/ADR-008-dungeon-runs.md` (Proposed; it stays Proposed).

**Revised 2026-10-08** with what the owner approved that day (relayed by the update brief): changes D1-D9 of
`docs/mechanics/DROPS_PROGRESSION_SPLIT.md` section 4 (progression items become dungeon rewards; the den), and from
`docs/mechanics/DUNGEON_PLACEMENT.md` section 5 only the level cap as the governing constraint and the Beast Ball rule.
The rest of that list is marked OPEN where it would land (section 0.1).

Labels: **VERIFIED** = seen in source, a jar read recorded in `docs/research/`, or a run, with the citation;
**ASSUMED** = inferred, not checked; *relayed* = a number taken from another document and not re-measured here;
*measured* = counted by this unit (line counts by Grep over the named files).

---

## 0. Premises checked

| # | Premise (from the brief) | Finding |
|---|---|---|
| P1 | "The one built dungeon slice, the Entei boss" | **Built, never run, with three recorded defects.** `data/entei_boss.json:4` says "NOT RUN in any world"; `experiments/EXP-059-entei-boss/README.md:3` is NOT_EXECUTED; the morning report lists "a second catch after a logout; the lockout after a clock reset; first-24,000-ticks refusal" (`docs/MORNING_REPORT_2026-10-11.md:18`). Every dungeon below rests on this machinery, so **EXP-059 runs before anything is generalised** (section 7.5, step 0). |
| P2 | "The refillable mining caves are the built precedent" for a resource leg | **Built offline, never installed or seen** (`data/mining_caves.json:3`). And they are SHARED by design (`:6`), which is why their reset needs an occupancy guard (`:51`). A dungeon's seam is in a private slot, so it needs no guard; what it needs instead is a way to let the player mine the seam while the walls stay unbreakable, which the Entei room's Mining Fatigue ward (`data/entei_boss.json:80`) forbids everywhere. Section 2.3 resolves it. |
| P3 | Entei's lockout as the model | **A 24,000-tick lockout is shorter than a 30-minute run.** It is 20 minutes of uptime counted from entry (`data/entei_boss.json:91-93`), so on a 30-minute run it has expired before the player is out: it would never bind. A dungeon lockout must be at least the run's own length (section 8, Q5). |
| P4 | "Each leg is one of trainer battles, a resource farm, a boss fight" | Read as: every run holds all three kinds, boss last. A run of three trainer legs would be a gauntlet, which Heaven's Arena already is (`data/arena_fights.json:27`). Q1 asks the owner to confirm. |
| P5 | Trainer legs earn nothing extra | **Wrong by default.** CobbleDollars pays automatically on an NPC win; the arena "paid TWICE (our purse + CobbleDollars' automatic NPC payout)" and now claws the automatic one back (`docs/MORNING_REPORT_2026-10-11.md:19`, *relayed*; EXP-060 not run). Every dungeon trainer leg is a cash faucet unless the engine claws back the same way. |
| P6 | Real cost numbers: "an independent audit around 3M, one prepare run about 30 minutes" | Audit: the repository's recorded range is 0.59-2.99M (`docs/mechanics/NETHER_DUNGEON_SCOPE.md:256-259`, *relayed*); this document uses 2M, 3M for an Opus audit. Prepare: **three documents disagree**: CLAUDE.md "679 s" (about 11 min), the scope "~35 min (*relayed*)" (`NETHER_DUNGEON_SCOPE.md:259`), the brief "about 30 minutes". Not measured here; section 1 uses 30 min as the brief says, and notes the time cost is small next to the token cost either way. |

Two findings outside the brief, recorded and not chased:
- **The Sunken Court's centre is under water.** `data/towns.json:2359-2363` puts the jungle ruins outpost at
  (5160, 7463), the coordinate CLAUDE.md ("Measure before relaying") records as ground y61 against sea level y62 after
  the water export. It is disqualified as a dungeon home here; the jungle temples (`data/jungle_temples.json:89`,
  `:187`, `:253`) are used instead, with their ground **not measured by this unit**.
- **The scaling the brief asks for is largely native.** Cobblemon 1.8.0's pool party picks entries by the NPC's
  level (`npcLevels`) and evaluates team size as MoLang with `q.level` and `q.player` visible
  (`docs/research/notes/arena-per-player-opponents.md:98-102`, VERIFIED from `PoolPartyProvider` source; the
  `npcLevels` filter is not yet run). Section 5 builds on it.

### 0.1 Owner decisions of 2026-10-08 (relayed by the update brief) and what stays open

Decided, and applied in the sections named:
- **Progression items are dungeon-exclusive rewards:** Exp. Candies, the six IV candies, Rare Candy and the Lucky Egg
  (`DROPS_PROGRESSION_SPLIT.md` 1.3-1.4). That document's Q1 is answered: the Lucky Egg moves. Materials stay as
  drops. Section 4.
- **The den**, a fourth, optional leg kind, in two dungeons: the Night Shift (the Electirizer) and the Last Cistern (the
  two armours). That document's Q3 is answered: the Last Cistern, not the Temple Calendar. Section 2.3.
- **The Beast Ball is the key to every dungeon boss, and only dungeon bosses.** Overworld legendaries stay catchable
  with any ball. Built as `data/key_ball.json` (tag `cobblers.key_boss`; boss list Entei only), NOT RUN:
  `experiments/EXP-064-beast-ball-key` is NOT_EXECUTED (`data/key_ball.json:4`, *read*). Section 2.3.
- **The level cap is the governing constraint on any catchable dungeon boss:** its level is at or under the lowest
  cap its gate admits, because the cap pack refuses a catch strictly over the thrower's cap with every ball
  (`DUNGEON_PLACEMENT.md` Q8). The window's cap is **60, and 62 after Lance; not 80** (`DUNGEON_PLACEMENT.md` Q1,
  *relayed* from `LEAGUE_LEVEL_CAP.md:3-6`, `:50-56`). Sections 2.3, 7.2.

**OPEN** (the owner has not answered; `DUNGEON_PLACEMENT.md` section 6): every dungeon catch after the Champion (Q11),
so pre-League wild bosses fight-only; the Temple Calendar as the window's dungeon at `gym8_cleared` (Q13); the paradox
columns, threats and band-6 paradox catches (C2-C8); Koraidon and Miraidon (Q14); which sites count as dungeon bosses
(Q15). Nothing below assumes an answer to any of them.

---

## 1. Recommendation, against the owner's instinct

**Recommendation: neither (a) nor (b) as written. Build a hybrid, (a'): every dungeon is AUTHORED, but its variety
comes from three cheap sources instead of whole hand-built variant runs:**

1. **Contents re-roll on every run, by machinery that is already proven or built.** Trainer teams re-roll at every
   challenge (VERIFIED in game, `arena-per-player-opponents.md:367-368`). The seam's ore pattern is one of eight
   variants, never the last one (the mining caves' rule, `data/mining_caves.json:27`, `:51`). The boss is drawn from a
   small pool; the reward roll draws without repeats until a set is complete.
2. **Rooms rotate on fixed sockets.** Each dungeon has a fixed hub with three sockets (trainer wing, seam wing, boss
   room), each a fixed box with a fixed door. Each socket has two authored rooms, chosen "other than last time". Two
   rooms per socket give 2 x 2 x 2 = **8 layouts for 6 rooms**, where the owner's (a), three whole runs, gives **3
   layouts for 9 rooms**.
3. **The run re-tiers to the player's level cap at entry** (section 5), so one dungeon is a different fight at every
   badge.

**Where the owner is right.** (b) is a different project. Its validator, its runtime experiments and its template
library all come before the first playable run, and it brings a defect class (rooms that do not connect, bosses in
corridors, unreachable loot) whose worst case, a softlock in a pocket dimension, is the CLAUDE.md escalation case 1.
In this stack "dynamic" can only mean picking pre-validated templates with `random value` at run time, because no
connectivity proof can run inside mcfunction. Done safely, (b) therefore collapses into fixed sockets, which is (a').

**Where the owner is wrong.** The literal (a), several hand-built whole runs per home, is **not** "a fraction of the
cost" once there are many dungeons. Each extra variant is a whole run of rooms. On the measured rates its marginal cost
per dungeon (about 9.6M) is the highest of the three, and (b) overtakes it at about **four dungeons** (section 1.2). The
"different each time" feeling comes mostly from who you fight and what you dig, not from corridor order. That is
cheap in every option, and it is what (a') spends on.

### 1.1 Rates used (measured unless marked)

| Rate | Value | Source |
|---|---|---|
| Builder authoring a place end to end | 3.4-4.6M, 130-160 turns; **4M** used | CLAUDE.md "What a builder actually costs" (measured 2026-10-02) |
| Narrow follow-up on an existing tool | **2.6M**, ~90 turns | same |
| Research question settled | 0.57-0.66M; **0.6M** used | CLAUDE.md cost rules |
| Independent audit | 0.59-2.99M (*relayed*); **2M**, **3M** on Opus | `NETHER_DUNGEON_SCOPE.md:256-259` |
| Design unit (opus) | ~1M (*relayed*, the scope's own estimate) | `NETHER_DUNGEON_SCOPE.md:273` |
| Prepare | 11-35 min (sources disagree, P6) | CLAUDE.md; `NETHER_DUNGEON_SCOPE.md:259` |

**The per-dungeon baseline, measured.** The Entei unit is **2,169 lines**: `data/entei_boss.json` 163,
`tools/entei_boss.py` 702, `tests/test_entei_boss.py` 336, `tests/test_entei_boss_audit.py` 786,
`experiments/EXP-059-entei-boss/README.md` 182. It is one room, one boss and no legs. Its two donors for the legs:
the arena runtime is **3,258** (`tools/arena_runtime.py` 1,113, `tools/arena_runtime_audit.py` 1,806,
`data/arena_fights.json` 339); the mining caves are **2,785** (`tools/mining_caves.py` 983,
`tools/mining_caves_audit.py` 946, `data/mining_caves.json` 350, tests 162 + 344). A dungeon engine that takes the
slot and keeper from Entei, the gauntlet loop from the arena and the restore from the caves is about **two Entei
units of code**, so two builders, not one. The Entei unit's own token spend is **not recorded anywhere** (no report
names it); the builder rate above stands in for it.

### 1.2 Costing table

The **shared foundation** is needed by every option: the run engine (slots, entry, keeper, run state, hub gate,
lockout, rebuild-on-entry reset, loss and blackout exemption, payout clawback, cap read, reward rolls) and the three
leg kinds.

| Item | Who | Cost |
|---|---|---|
| EXP-059 on staging, the three Entei defects fixed | main session + the owner in game | 2-3M |
| Research R-D1..R-D4 (section 9) | `cobblemon-researcher` | 4 x 0.6 = 2.4M |
| Engine core builder | `minecraft-systems-dev` | 4M |
| Legs builder (gauntlet, seam, boss) | `minecraft-systems-dev` | 4M |
| Engine audit: softlock, isolation, economy (Opus, rule 1) | `test-author` | 3M |
| Integration: 2 prepares, full suite, staging proof XD1-XD7 | main session | 2-3M |
| **Foundation** | | **~17-19M, ~18M used below** |

| | **(a) literal: 3 whole runs per home** | **(a') recommended: sockets** | **(b) generator** |
|---|---|---|---|
| Option-specific up-front | none | none | generator, 2 builders 8M; validator 4M; its Opus audit (mutate the generator) 3M; runtime-assembly experiments (`place template` in the pocket, load order) 2.5M: **17.5M** |
| First dungeon, complete | design 1.5M; builder 4M + 2 variants x 2M; audit 2M; staging 1M = **12.5M** | design 1M; builder 4M (6 rooms); audit 2M; staging 1M = **8M** (+1M for the second room per socket = **9M**) | library of ~14 templates 3.5M; design 1M; audit 1M = **5.5M** |
| **To the first playable run** | 18 + 12.5 = **~30M** | 18 + 9 = **~27M** | 18 + 17.5 + 5.5 = **~41M** |
| Each further dungeon | design 1.5 + builder 2.6 + 2 x 1.5 + audit 1.5 + 1 = **~9.6M** | design 1 + builder 2.6 + 1 + audit 1 + 0.5 = **~6M** | library 3.5 + design 1 + audit 1 = **~5.5M** |
| 6 dungeons | ~78M | **~57M** | ~68M |
| 8 dungeons | ~97M | **~69M** | ~79M |
| Layouts per dungeon | 3 | 8 | dozens (unbounded only if unvalidated) |
| Prepares (30 min each) | 2 + 1 per dungeon | 2 + 1 per dungeon | 4 + 1 per theme (the generator's own iteration) |
| Its defect class | geometry per variant; audited per variant | geometry per ROOM against its socket; combinations valid by construction | every combination; must be enumerated or proved by construction (section 1.3) |
| Break-even | (b) is cheaper from about 4 dungeons | cheapest at every count up to about 28 | beats (a') only past about 28 themes, (41 - 27) / (6 - 5.5) |

Every figure is an estimate built from the measured rates; none is a measurement of this work.

### 1.3 What (b)'s validator would have to close

A generator is only as safe as its validator, and this list is why (b) costs what it does. Each is a check over every
layout the generator can emit; at run time nothing can check:

1. **Connectivity:** a walkable path (2 air over a solid floor, steps of at most 1, no drop over 3) from the arrival to
   every leg, to the boss, and back to the exit.
2. **Softlock:** the exit reachable from every walkable cell, including after a gate closes behind the player.
3. **Boss in a corridor:** the boss and NPC spots stand in a room of at least a minimum clear battle area. The area a
   Cobblemon battle needs is ASSUMED (no research note gives it).
4. **Unreachable loot:** every chest, marker, alcove and seam face reachable from walkable floor.
5. **Overlap and bounds:** no two templates intersect; none breaks the bedrock shell or leaves the slot; slots never
   touch.
6. **Door alignment:** socket faces, widths and heights match on both sides.
7. **Keeper coverage:** every walkable cell is inside the keeper's sweep box, or a player escapes the eject.
8. **Load radius:** every NPC spot is loaded while the player is at its trigger. An NPC unloads with its chunk
   (VERIFIED, `arena-per-player-opponents.md:369-370`).
9. **Hazards:** no fluid leak, lava, magma (`data/entei_boss.json:81`) or fall; every spot on solid floor with 2 air.
10. **Reset filter:** the seam's refill volume never overlaps decoration; ward boxes and seam boxes are disjoint.
11. **Spawn-condition blocks:** none in a template unless whitelisted (`tools/validate_data.py:2583-2637`, *relayed*
    via `ADR-003:18`).
12. **Light:** nothing walkable at block light 0 (`tools/light_plan.py`, as `tools/route1_old_mine.py:28-29`).
13. **Provenance:** every NBT template has a `kits/PROVENANCE.json` record (`tools/validate.py --only
    template_provenance`).
14. **Combinatorics:** the run-time choice ranges over exactly the validated set.

(a') keeps every one of these checks, but **per room against its socket's contract**, and items 1, 2, 5, 6 and 14 then
hold for every combination by construction. That is the saving.

---

## 2. Run structure

### 2.1 Legs: neither fixed nor shuffled, but chosen, with the boss always last

The hub has two open wings and one sealed door. The player takes the trainer wing and the seam wing **in either
order**, and the boss door opens only when both legs are flagged done. This is the vision's own shape, "Final Chamber:
opens only when every required dungeon flag is set" (`docs/vision/GAME_VISION.md:134`).
Where a dungeon has a **den** (2.3), it is a further room off the hub, optional: the boss door never waits on it.
- Why not fixed: the order is the cheapest variety there is, and fixing it throws that away.
- Why not shuffled: a shuffle needs the rooms re-seated per run. A hub gives the same variety with one geometry, and
  gives the player the choice. Seam first is a breather; trainers first means carrying damage into the dig.
- The boss is last because it is the climax and the reward. A boss mid-run would leave a leg that pays nothing after it.

### 2.2 Time budget, about 30 minutes (ASSUMED until XD7 times one)

| Part | Minutes | Basis |
|---|---|---|
| Arrive, hub, walking between wings | 3 | three short rooms off one hub |
| Trainer wing: 3 trainers, gauntlet | 10-12 | ~3-4 min a fight, ASSUMED: no fight has been timed (EXP-059 X2 times the first) |
| Seam wing: dig through to the alcove | 6-8 | the seam's depth is the tuning knob (2.3) |
| Boss | 6-8 | a 3-6 member NPC at the cap |
| **Run** | **25-31** | |
| Den, optional, where a dungeon has one | 5-6 more | four wild battles, ASSUMED: none timed |

### 2.3 The leg kinds: three required, one optional (every one reuses a built or proven part)

- **Trainer wing: a gauntlet of three NPC trainers.** The arena's loop: `spawnnpcat` at absolute coordinates with a
  level, `q.npc.start_battle`, and the `battle_victory` callback. All PASS in game for one player
  (`arena-per-player-opponents.md:357-368`). The format is the arena's gauntlet: healed at the start of the run only,
  HP, PP and faints carry (`data/arena_fights.json:27`), with no bag items (`:30`). The NPCs are `cobblemon:npc`,
  never rctmod trainers, so they sit in no series and cannot move anyone's level cap (the cap trap, `docs/STATE.md:218`).
  The automatic CobbleDollars payout is clawed back as the arena's is (P5).
- **Seam wing: dig to the alcove.** The seam is a face of `#cobblers:cave_resettable` blocks, refilled from one of eight
  variants on every run (`data/mining_caves.json:24-51`). The leg is done when the player stands in a sealed alcove
  behind the face. The keeper tests position, as Entei's tests slot ownership (`data/entei_boss.json:88`), so no block
  break has to be detected. Everything mined on the way is the player's.
  - **The ward conflict (P2):** the seam wing's walls, floor and ceiling are bedrock. Only the face is breakable, and
    Mining Fatigue is applied in every other room's box, never in the seam's.
  - **The yield is income.** Ores the bank buys are capped per run at the matching cave's per-reset yield
    (`data/mining_caves.json:66-71`), and the dungeon is declared to `tools/economy_audit.py` as a renewable supply
    on its lockout clock, as R10 asks for the caves (`docs/mechanics/ECONOMY_OVERHAUL.md:520`).
  - **The area's type-gem clusters in the face, if R-D1 confirms them.** Cobblemon registers each gem with a
    `TYPE_GEM_CLUSTER_<type>` block (`docs/research/ITEMS_ABILITY_EV_HELD_MEGA.md:139`, VERIFIED as a registration;
    the drop, the tool and the growth are not read).
- **Boss: an NPC by default, a wild legendary in the Nether.** One wild Pokemon against six is too easy
  (`NETHER_DUNGEON_SCOPE.md:130-139`). An NPC boss with a scaled team uses the proven per-player loop and is a real
  fight at every band. The Nether dungeons keep the built Entei keeper (wild, catchable once, then `uncatchable` with
  an item roll, `data/entei_boss.json:22-26`).
  - **An NPC boss is never catchable by any ball**: a ball thrown at an NPC's Pokemon is refused as `not_wild`
    (`docs/research/notes/beast-ball-key-1.8.0.md:151-152`, *relayed*; that an NPC's battle Pokemon takes that path
    is ASSUMED, not thrown at). It carries no key tag.
  - **A wild catch-mode boss is a key boss** (the owner's Beast Ball rule, 0.1). Its own tool adds the tag
    `cobblers.key_boss` in the function that binds it, and it is listed in `data/key_ball.json` `bosses`; the key
    pack's two callbacks raise a Beast Ball's rate x5 on a tagged boss and refuse every other ball, the Master Ball
    included, handing it back (`data/key_ball.json:8-17`, *read*). Built for Entei only, NOT RUN (EXP-064).
  - **The cap binds every key boss:** its level is at or under the lowest cap its gate admits. A Beast Ball refused by
    the level cap, not the key, is consumed (`data/key_ball.json:35`, *read*). Entei is level 100 behind the
    Champion, at cap 100, so it never meets this. Whether every wild catch-mode boss is gated at `champion_cleared`
    is OPEN (`DUNGEON_PLACEMENT.md` Q11).
  - **No dungeon Pokemon is an alpha**: not a boss, not a den Pokemon. An alpha is re-levelled above the party, pays
    alpha gems and breaks the cap's catch block (`DUNGEON_PLACEMENT.md` section 3, P3 of `DROPS_PROGRESSION_SPLIT.md`).
- **Den (optional): a room of wild Pokemon for one evolution key** (`DROPS_PROGRESSION_SPLIT.md` section 5; the owner
  approved both dens, 2026-10-08). Only the Night Shift and the Last Cistern have one.
  - Four wild Pokemon, spawned at the band's level (cap-2 to cap-1, the arena rule) when the slot is built, and
    knocked out in battle. They are `uncatchable` (Entei's farm-mode pattern, `data/entei_boss.json:22-26`) and
    never alpha. They are not key bosses and carry no tag.
  - Drops are the **species' own tables** at entity death; no generated loot. They land in the player's own slot.
  - The boss door does not wait on the den (2.1).
  - **Night Shift, the powerhouse (the Electirizer):** 4 Elekid at bands 1-2 (an Electirizer that early has no
    Electabuzz to use it on); 3 Electabuzz and 1 Electivire at band 3; 2 and 2 at bands 4-6. Expected Electirizers a
    run 0.198 / 0.772 / 0.973, at least one in 18% / 59% / 68% of runs (*relayed*, `DROPS_PROGRESSION_SPLIT.md`
    section 5, computed there from `drops-1.8.0.json`). Side drop: redstone, bought by the bank (about 5 a run,
    *relayed*), so the den is declared to `tools/economy_audit.py` on the lockout clock, as the seam is.
  - **Last Cistern, the two sentries (the Auspicious and Malicious Armor):** 2 Armarouge and 2 Ceruledge at bands 4-6,
    the band where Charcadet becomes catchable. Each armour 0.355 a run expected, both in 10.5% of runs (*relayed*,
    the same section). Charcoal, the side drop, is not bought.
  - **Every player can evolve once:** the band's first clear guarantees one of each key (section 4).

### 2.4 Reset, instancing, failure

- **Instancing:** a slot per concurrent run in `cobblers:pocket`. There are 4 per dungeon, as Entei has
  (`data/entei_boss.json:56-60`). Each player runs their own copy, the owner's Entei rule (`:5`).
- **Reset by rebuild.** Entering a slot replays its place function (rooms, seam variant, gate closed), then teleports
  the player. Nothing a player did in a previous run survives, and no block-by-block restore has to be right. The
  chunk has to be loaded before the fill. This is experiment XD1: forceload, a delay, place, then teleport, as Entei
  delays its spawn by 40 ticks (`:85-86`).
- **Loss:** a trainer or boss loss blacks out (it already fires for an NPC loss, VERIFIED,
  `arena-per-player-opponents.md:365-366`). There is no item claim (the blackout's `claims.exempt_tag`, as Entei's,
  `data/entei_boss.json:113`). The run is over and the slot frees.
- **Logout or leaving:** the slot frees on the next keeper pass, the run is lost and the lockout runs (Entei's rule,
  `:157`).

---

## 3. The dungeon list: seven homes, themes not types

Every home is a real place with a record. The door is an arch with a click (the portals pattern, `data/portals.json:4`;
the click is EXP-034), seated in the place, and the run is in the pocket: the fiction is that the space is elsewhere,
as ADR-004 reserves the pocket for (`docs/decisions/ADR-004-pocket-spaces.md:32-34`). **Overworld doors avoid the
Nether's problem** (no ground to measure, `data/entei_boss.json:49`), because the overworld has the heightmap. **No
home already has a boss** (the Ursaluna cave, Frostpeak's Articuno, the Hoopa cradle and the legendary sites are left
alone), and no dungeon drops an evolution stone, which has its seven sites already (`ADR-003:64-71`).

**Dungeon 1 is reachable at 0 badges and scales to every cap**, so a run is always available at whatever badge count a
player has. The others add places and areas, not coverage.

| # | Dungeon (theme) | Home and door | Evidence the place exists | First reachable |
|---|---|---|---|---|
| 1 | **The Night Shift.** The old mine's last shift broke into a lower level the night the south drift fell, and came up without their foreman. The lamps down there are still lit. | The old mine west of Route 1; the door in the south branch's "fall of ground", its last point (1252, 4129) | `tools/route1_old_mine.py:2`, `:21-26`, `:67` (SOUTH); the old mine's cave beside it, `data/mining_caves.json:218-227` | **0 badges** (Route 1, tier 1, `data/encounter_design.json:114-147`) |
| 2 | **The Street That Ends at Nothing.** The Worldshift took a city off Mt Vessu and left its road. Walk the road past its end and you are in the city as it was the hour before. | The Scar, the road's end (centre 2110, 950) | `data/towns.json:2059-2073` ("foundations and a road that ends at nothing"); the city itself, `:1435-1448` | ~gym 2-3 (Mt Vessu tier 3, `encounter_design.json:180`) |
| 3 | **Under the Patriarch.** The great dark oak over the Rift drinks from something below the Wedge, and its roots have grown round what they found. | The Patriarch's foot (4272, 3600) | `data/towns.json:2570-2606` | ~gym 6-7 (the Wedge, tiers 6 and 8, `encounter_design.json:320`, `:398`) |
| 4 | **The Last Cistern.** The waterworks of a plateau town that died of thirst; the pumps still run, on nothing. | The Dry Cistern (4530, 5850) | `data/dry_cistern.json:16-28` (authored, not applied, not audited) | ~gym 7 (plateau_west tier 8, `:414`) |
| 5 | **The Temple Calendar.** Three jungle temples are one instrument; the run is inside the day it measures. | One of the long-isle jungle temples, e.g. (7200, 7528) | `data/jungle_temples.json:85-89` (ground NOT measured by this unit) | ~gym 7-8 (long_isle_south tier 8, `:392`); a door at `gym8_cleared` as the window's dungeon is OPEN (`DUNGEON_PLACEMENT.md` Q13) |
| 6 | **The Tower After the Fire** (Entei) | anywhere in the Nether (the key) | built: `data/entei_boss.json`; theme `docs/mechanics/NETHER_ENCOUNTERS.md` 3.1 | Champion (`entei_boss.json:13`) |
| 7 | **The Crucible** (Heatran) | anywhere in the Nether (the key) | designed: `NETHER_ENCOUNTERS.md` 3.2 | Champion |

**Gap, said plainly:** nothing between gym 3 and gym 6 in the north and centre. The Merian Hut (`data/towns.json:
1679-1714`, tier 4) or the Sentinel (`:2496-2532`, tier 4) would fill it. Q3.

**Dens** (2.3): the Night Shift (the Electirizer) and the Last Cistern (the two armours). They drop evolution keys
the counters do not sell, never a stone.

**Rosters follow the theme, drawn from families with evidence** (E1, in a compiled table, as
`NETHER_ENCOUNTERS.md` section 2 defines it). For dungeon 1, the shift's own Pokemon:
- haulers: Timburr's line (E1, `NETHER_ENCOUNTERS.md:441`) and Machop's line (`encounter_design.json:190`);
- what lives in rock: Geodude's line (Graveler, `encounter_design.json:190`, `:222`), Roggenrola's (Boldore, `:222`),
  Onix (`:222`);
- what digs: Diglett's line (`:173`);
- the lower level's own: Drilbur to Excadrill (`:280`).

The balance designer chooses; this is the shape.

---

## 4. Rewards per area

**Rule.** The rewards are items, never CobbleDollars. The generator fails closed on any drop that is:
- bought by the bank (Entei's `not_bankable` check, `data/entei_boss.json:109`);
- **sold at any counter** (new: the type boosters a counter sells, `data/bank.json:269`, `data/markets.json:160`,
  `:228`);
- an evolution stone (ADR-003 owns them);
- a `*_plate` or an arena trophy (`docs/STATE.md:143` item 3);
- the Ability Patch (the arena's, `docs/mechanics/ITEM_ROUTES.md` section 3, row 5).

**Progression is the dungeons' exclusive** (the owner, 2026-10-08). A progression item is a dungeon reward and appears
in no other generated table: the twelve ids of `DROPS_PROGRESSION_SPLIT.md` 1.3 (`exp_candy_xs` to `_xl`,
`rare_candy`, the six IV candies `health_`, `mighty_`, `tough_`, `smart_`, `courage_` and `quick_candy`) and the
`lucky_egg`. The generator and the validator fail closed on one anywhere else: the alpha tables, `data/rewards.json`,
`data/markets.json`, `data/traders.json` and the arena. Two changes outside this file make that true, neither built:
- the four `cobblemon:alpha/alpha_rewards_tier1..4` loot tables overridden empty at their own path (option C,
  `DROPS_PROGRESSION_SPLIT.md` 3.5); until then every wild alpha KO still pays candies;
- the Lucky Egg stripped from Blissey, Chansey and Togepi with `species_additions` at their paths (1.4 there).

The counters' priced vitamins and Ability Capsule (`data/markets.json:388-394`, *relayed*) are outside the owner's
direction, which is about free drops; whether they stay is OPEN (section 8).

Candidates come from the registered list (VERIFIED, `docs/research/ITEMS_ABILITY_EV_HELD_MEGA.md:136-142`). The 18
`<type>_gem` ids are read in the jar's alpha type tables (`DROPS_PROGRESSION_SPLIT.md` 1.3, *relayed*).

**Gems are the dungeons' volume; progression is their exclusive.** Gems are TM crafting material (the changelog quote
at `ITEMS_ABILITY_EV_HELD_MEGA.md:139`), and every one of TMCraft's 805 native TM recipes names one
(`docs/research/DROP_RATE_CONSUMERS.md` 3.1, *relayed*). They are **not** scarce, so they are not the reason to run a
dungeon:
- **alpha battles drop them in every type** (`docs/research/DROPS_AUDIT.md` 2.4, *relayed*): about 1.125 gems per KO
  below level 51 today, and under option C, which grows the pay with the alpha's level and pays its second type,
  2.25 / 3.75 / 5.625 from levels 31 / 51 / 66 (`DROPS_PROGRESSION_SPLIT.md` 3.4-3.5, *relayed*; designed, not built;
  the roll counts are that document's Q2, OPEN);
- **no blank disc gates a TM's grade.** No counter sells a blank (no `blank_disc` id anywhere in `data/`, *measured*
  by grep), and every TMCraft blank is craftable: copper from one ingot, the higher grades by smithing upgrade
  (`DROP_RATE_CONSUMERS.md` 3.2, *relayed*). With alpha gems, 603 of the 802 TMCraft TMs are craftable (3.1 there,
  *relayed*). The blank lines `PROGRESSION_LADDER.md:177-184` designs were never authored.

So the old case that gems are "no power bypass" is gone: crafted TMs undercut the income-gated TM shelf from leg 1
whoever supplies the gems (`DROP_RATE_CONSUMERS.md` 3.3 and its section 4 item 1, an owner decision, OPEN). A
dungeon's gems add to a supply the alphas already provide, and a run is worth doing for what only it gives: the
progression bundle and the first clears below.

| # | Gems (area) | Battle items (registered ids) | Seam |
|---|---|---|---|
| 1 Night Shift | rock, ground, steel | `smooth_rock`, `float_stone`, `iron_ball`; `rocky_helmet` from band 4 | coal, iron, copper; gold, redstone, lapis from band 3; diamond from band 5 (the cave yields) |
| 2 The Street | psychic, fairy, ghost | `psychic_seed`, `misty_seed`, `light_clay`, `eject_button`, `eject_pack`, `room_service` (things that were moved) | the city's stone; which blocks is open, checked against `data/spawn_blocks.json` |
| 3 Patriarch | grass, dark, bug | `grassy_seed`, `leftovers` (a tree's fruit), `black_sludge` | wood and the area's ores |
| 4 Last Cistern | water, ground | `damp_rock`, `utility_umbrella`, `absorb_bulb`, `shell_bell` | the plateau's ores |
| 5 Temple Calendar | grass, rock, electric | `electric_seed`, `scope_lens`, `wide_lens`, `zoom_lens`, `quick_claw`, `loaded_dice` | the island's ores |
| 6 Tower | fire, ghost | `NETHER_ENCOUNTERS.md:363`'s candidates; `life_orb` VERIFIED | none (boss only, as built) or Nether materials |
| 7 Crucible | steel, fire | `heat_rock`, `iron_ball`, `metal_powder`, `assault_vest` | ancient debris, if the economy wants it |

**Progression, every home, by band.** Candies are type-neutral, so they scale by band, not by home. The sizing rule:
**one run's candies are about half a cap step for one medium-fast Pokemon at that band**, so a run helps one Pokemon
catch up and never levels a party. The table is *relayed* from `DROPS_PROGRESSION_SPLIT.md` section 4 (candy EXP
there is itself *relayed* from `LEVEL_CATCHUP.md:31`); the exact bundles are `trainer-balance-designer`'s.

| Band (cap at entry) | Cap step (EXP, n³) | Candies per run | EXP | IV candies | Rare Candy |
|---|---:|---|---:|---|---|
| 1 (20, 25) | 7,625-11,375 | 1 M + 2 S | 4,600 | none | none |
| 2 (30, 35) | 15,875-21,125 | 3 M | 9,000 | none | none |
| 3 (40, 45) | 27,125-33,875 | 1 L + 2 M | 16,000 | none | none |
| 4 (50, 55) | 41,375-49,625 | 2 L + 1 M | 23,000 | 1-2 of one random stat | none |
| 5 (60, 62) | 49,625 (55 to 60) | 1 XL | 30,000 | 2-3 | 1 |
| 6 (100) | 784,000 (60 to 100) | 2 XL | 60,000 | 3-4 | 1-2 |

The cap clamps every candy: one used at the cap adds nothing and is not consumed, one below it stops at the cap
(`DROPS_PROGRESSION_SPLIT.md` 2.2, VERIFIED there in rctmod bytecode; not run in game, X3). So no bundle can overshoot,
and the band-5 bundle in the window levels to 60 at most.

**Scaling of rewards.** Each band (section 5) has its own table. Bands 1-2 pay one gem and a minor item, bands 3-4 two
gems and a weather rock or seed, and bands 5-6 three gems and the competitive items, each with the band's progression
bundle above. Choice items are postgame band only.
**Each band's first clear** grants a one-time, per-player prize (an advancement, the Spectrier pattern,
`tools/spectrier_cap.py`). A dungeon open from badge 0 therefore has six first clears to give. Decided first clears
(the owner, 2026-10-08):
- Night Shift, band 1: the **Lucky Egg** (drop-only today, `DROPS_AUDIT.md` 4.5, *relayed*; so once stripped from the three species,
  this is its route);
- Night Shift, band 3: one **Electirizer**;
- Last Cistern, band 4: one **Auspicious Armor** and one **Malicious Armor**;
- band 5 of every home: one **Rare Candy**.

The other first clears, and all exact items and weights, are `trainer-balance-designer`'s.

---

## 5. Per-gym scaling

**The run's band is fixed at entry from the player's level cap**: `rctmod player get level_cap @s` on a macro line,
the read `tools/levelcap_pack.py:58`, `:93` already makes. It is frozen on the slot for the run. A gym-1 run done at gym
8 is not the same run: every NPC is spawned at the gym-8 band. It is never trivial, and never impossible.

| Band | Player's cap at entry | Badges | Trainer members | Boss members | Trainer level | Boss ace | Stage |
|---|---|---|---|---|---|---|---|
| 1 | 20, 25 | 0-1 | 2 | 3 | cap-2 to cap-1 | cap | first stages |
| 2 | 30, 35 | 2-3 | 3 | 4 | same | cap | middle stages |
| 3 | 40, 45 | 4-5 | 3 | 5 | same | cap | middle and final |
| 4 | 50, 55 | 6-7 | 4 | 6 | same | cap | finals; held items appear |
| 5 | 60, 62 | 8, the League | 5 | 6 | same | cap | finals with sets |
| 6 | 100 | after the Champion | 6 | 6 | 95-99 | 100 | competitive sets |

The caps are those of `docs/mechanics/NETHER_ENCOUNTERS.md:50-56`, *relayed* from `data/trainers.json:14-23` and
`LEAGUE_LEVEL_CAP.md:50-56`. The levels follow the arena's rule: no member above the band's cap
(`tools/arena_runtime.py:25-28`).

**How, at rung 1 (Cobblemon native).** One NPC class per trainer covers every band:
- each pool entry carries `npcLevels`, so the spawn level picks the stage (`arena-per-player-opponents.md:101`);
- `minPokemon` and `maxPokemon` are MoLang with `q.level` visible, so team size follows the level (`:98`, `:102`);
- `q.player` is visible too, so **Challenge mode** can add one member and hold items one band earlier, keyed on the
  `cobblers_mode_challenge` tag (`docs/mechanics/OAK_AND_CHALLENGE.md:55`). Its rules mirror "every Gym Leader brings
  six" (`:42`).

All of this is VERIFIED from source and not run: XD2 proves it. If the MoLang team size fails, the fallback is one
class per band, 6 x 4 = 24 classes per dungeon. That is generated, so it costs nothing in authoring. Classes load
only at a restart (`arena-per-player-opponents.md:63`).

**What keeps it "doable":** every fight is at or under the cap and a party over the cap is refused at the door (the
arena's check, `tools/arena_runtime.py:536`). Each band's boss is checked by `tools/battle_sim.py` against a walked
and an informed team, as the gyms were (`docs/STATE.md:344`). The main session runs it, since the designer has no shell.

---

## 6. Replay: what makes the tenth run worth doing

1. **The run changes under you.** Teams re-roll on every run, one of 8 layouts comes up (never the last), the seam
   pattern is never the last one, and the boss comes from a pool.
2. **The band changes as you badge up**: new stages, team sizes and tables. A dungeon first run at badge 0 is a
   different fight at badge 4, 8 and after the Champion.
3. **Gems and progression never stop being wanted** (section 4): every crafted TM consumes a gem, and the candies,
   IV candies and Rare Candy are found nowhere else.
4. **A collection per band**, drawn without repeats until it is complete, then a flat consolation (the scope's lever,
   `NETHER_DUNGEON_SCOPE.md:99-100`).
5. **Six first clears per dungeon**, one per band.
6. **Records:** a flawless clear (no faint) and a best time per dungeon, per player, as the arena's best streak is
   (`data/arena_fights.json:117`, *relayed* via the scope).
7. **Rotation across homes.** The per-dungeon lockout (Q5) means the next run is naturally somewhere else, which is the
   owner's "not the same one twice running" for free.
8. **Not used, and why:** cash (the arena is the faucet, P5); raising payouts with repetition (it makes one activity
   dominant, `NETHER_DUNGEON_SCOPE.md:103-104`). A shiny chance per run is ASSUMED to be a spawn property and is
   unread (R-D3).

---

## 7. The first dungeon to build completely: The Night Shift

The first dungeon is **dungeon 1, not Entei.** Entei is gated at the Champion (`data/entei_boss.json:13`), so every
player who can enter it has cap 100 and it can never test per-gym scaling. The Night Shift is open at 0 badges, so one
staging run can be repeated at caps 20, 45 and 60 by granting flags.

### 7.1 Data: `data/dungeons.json` (schema `cobblers.dungeons/1`, `generated_by: "hand"`)

- **`engine`:**
  - `pocket` (read from `data/portals.json`, failing closed on disagreement, as Entei does,
    `data/entei_boss.json:55`);
  - `bands` (the section 5 table), each with `progression`: a list of `{item, count}` (section 4's bundle);
  - `lockout_ticks`;
  - `battle_rules` (the arena's, `data/arena_fights.json:30`);
  - `hub_heal` (Q4);
  - `payout: "clawback"`;
  - `claims_exempt_tag` (read from `data/blackout.json`);
  - `ward_amplifier`.
- **`dungeons[]`.** The record for `night_shift`:
  - `home`: place `route1_old_mine`; the door seated at the SOUTH branch's last point. Its y and facing are
    **derived from `tools/route1_old_mine.py`'s own geometry** (the drift floor), never read from a world (CLAUDE.md,
    "Ground comes from the heightmap").
  - `gate_flag`: none.
  - `slots: 4`, `slot_origin`: a new band in the pocket. The builder derives it from `data/portals.json` (bands,
    rescue margin) and `data/entei_boss.json:58-62` (Entei's z -768 row). It must sit inside the border margin and be
    disjoint from both.
  - `sockets`:
    - `hub`: about 15 x 15 x 7, three doors;
    - `west`: the trainer wing, about 13 x 41, three stands 12 apart;
    - `east`: the seam wing, about 13 x 21, a face about 9 wide x 6 deep x 5 high, the alcove behind it;
    - `north`: the stope, about 21 x 21 x 10.

    Each is a box with door positions; every size here is a proposal for the builder to settle. The slot footprint is
    about 64 x 64, under the 128 spacing.
  - `rooms[]`: two per socket (`variant` a or b), palette and dressing ids from `world-content-dev`. The hub is "the
    Lamp Room": a lamp rack, a tally board showing one lit lamp per leg done, and the timber gate to the stope.
  - `legs`:
    - `trainer`: three stands, "Night Shift Hand", "Shotfirer" and "Timberman" (placeholder names), each with
      families by band;
    - `seam`: yield by band, the variant count (8) and the alcove box;
    - `boss`: an NPC, "the Foreman", with a team by band. He stayed down to keep the lamps lit. Every boss record
      carries `key_boss` (bool) and `gate_flag`; the Foreman's `key_boss` is false (an NPC, 2.3). A `key_boss: true`
      record must be listed in `data/key_ball.json` `bosses`.
  - `den` (optional): `{species_by_band, count, uncatchable: true}`. The Night Shift's is the powerhouse (2.3).
  - `rewards`: `collection_by_band`, `first_clear_by_band` (section 4).
  - `messages`, `does_not_cover`.

### 7.2 Validation (`tools/validate_data.py`, written by `test-author`, not the builder)

1. The door is inside the old mine's drift, and its coordinate traces to the host tool's plan.
2. Slots are inside the border margin and disjoint from the portals' rescue box, Entei's band and each other.
3. Every room fits its socket box; its doors are the socket's doors; every spot is on floor with 2 air, inside the
   keeper box; the seam box is disjoint from every ward box.
4. The bands cover every cap value the game can produce: 20 to 55, 60, 62 and 100.
5. No band's top level is above its cap, and no family is a doll or a mis-modelled final form
   (`docs/research/COBBLEVERSE_COMPATIBILITY.md:108-148`, *relayed*).
6. Drops: the section 4 rule. Seam: bankable output per run at most the cave's per-reset yield of the same tier.
   - **Progression is exclusive:** no file in our packs other than a dungeon reward table names a progression id
     (section 4's list), and the four alpha tier tables are empty. The mutation that proves it: put `exp_candy_xs`
     back in the tier-1 override and the check must fail (`DROPS_PROGRESSION_SPLIT.md` 3.5).
   - **Dens:** every den species has a drop entry for its declared item; no den Pokemon is an alpha; the den's
     expected yield per run is computed from the species file with `DROPS_AUDIT.md` 2.1's roll model, never stated
     by hand.
   - **Key bosses:** a `key_boss` record's level is at or under the lowest cap its `gate_flag` admits; no key boss
     and no dungeon Pokemon is an alpha; every `key_boss` is in `data/key_ball.json` `bosses`, and no other boss is.
     A gate below `champion_cleared` is not a failure while Q11 is OPEN.
7. `lockout_ticks` is at least the run's target length (P3).
8. Ids are prefixed `dg_`. `python tools/id_authorship.py` stays at 0 faults.
9. `python -m pytest tests/test_system_contracts.py`: new contracts "dungeon NPCs carry no rctmod series" (consumer:
   the level cap) and "dungeon wins pay $0 net" (consumer: the economy).

### 7.3 Generator and runtime (`tools/dungeon.py`, generalising `tools/entei_boss.py`)

- **Pack:** `build/datapacks/cobblers_dungeons`, world-local.
- **NPC classes:** in the pack. A change needs a restart (`arena-per-player-opponents.md:63`).
- **Functions:**
  - `door_click`: checks the gate, the lockout, a free slot and a party over the cap;
  - `enter`: reads and freezes the cap, forceloads, places the slot, then teleports after a delay;
  - `keeper`: ownership sweep, eject, ward outside the seam, leg flags, gate open;
  - `leg_trainer`: the arena's spawn, start and victory loop, with the clawback;
  - `seam`: the variant, and the alcove test;
  - `boss`;
  - `reward`: the roll, the collection and the first clear;
  - `exit`.
- **Callbacks:** `battle_victory` and `battle_fainted`, under `data/cobblemon/callbacks/<event>/` (the runtime fact in
  `.claude/rules/datapacks.md`).
- **Re-apply:** one new step places the door, after R8, the step that builds the old mine with the towns
  (`tools/route1_old_mine.py:6-8`). The slots need no step: they are placed on entry.
- **Entei** becomes `dungeons[]` record 6 on the same engine later, its keeper kept as the `wild` boss kind.

### 7.4 Runtime proof (a new EXP, staging, designed by the builder, graded by `qa-reviewer`)

1. **XD1:** the rebuild on entry.
2. **XD2:** classes by `npcLevels` and the MoLang team size at three spawn levels.
3. **XD3:** the clawback leaves $0 net.
4. **XD4:** the seam: mined and refilled; the alcove; no ward in the seam; bedrock walls.
5. **XD5:** the cap is read and frozen.
6. **XD6:** a loss blacks out with no claim.
7. **XD7:** a whole run timed at caps 20, 45 and 60.
8. **XD8:** two players in two slots (waits for the second account, `docs/STATE.md:177`).

### 7.5 Plan (ordered; each step one experiment or one unit)

| # | Step | Agent |
|---|---|---|
| 0 | Run EXP-059 (X2-X4) and fix the three recorded Entei defects | main session + the owner |
| 1 | R-D1..R-D4 (section 9) | `cobblemon-researcher` |
| 2 | Engine core with grey-box rooms | `minecraft-systems-dev` |
| 3 | Legs: gauntlet, seam, NPC boss | `minecraft-systems-dev` |
| 4 | Night Shift rosters, boss teams, tables by band | `trainer-balance-designer` (opus) |
| 5 | Rooms, palettes, dressing; the door's seat | `world-content-dev` (data only) |
| 6 | Engine audit and dungeon validation (Opus) | `test-author` |
| 7 | Prepare, full suite, install, XD1-XD7; `battle_sim` per band | main session |
| 8 | The owner plays it at three caps; decide dungeon 2 | the owner |

---

## 8. Open questions for the owner

1. **Every run has all three leg kinds, boss last?** *Recommend yes* (P4). Three trainer legs is the arena.
2. **Legs chosen at a hub rather than fixed or shuffled?** *Recommend the hub*: the same variety with one geometry, and
   it is the vision's sealed final chamber.
3. **How many homes, and which?** *Recommend building only dungeon 1, then deciding.* The list sites seven. The
   north and centre gap (gyms 3-6) wants Merian Hut or the Sentinel if the owner wants an eighth.
4. **Healing inside a run?** *Recommend one hub heal per run*, with no bag items in battle (the arena's rules). "Limited
   healing" is the vision's gauntlet rule (`GAME_VISION.md:143-145`).
5. **The lockout per dungeon per player?** *Recommend 72,000 ticks (one hour of uptime) from entry.* That is twice a
   run (P3), and with several homes a player can always run somewhere.
6. **Entry cost for the overworld dungeons?** *Recommend free, lockout-limited.* The rewards are non-cash items and
   the seam is capped at a cave's yield. The Nether pair keep their material keys (`data/entei_boss.json:43`).
   **Challenge players:** the seam is the only Minecraft play in a run. *Recommend leaving it in*: it is short, and it
   is a dig, not a farm.
7. **Solo instances only, or friends in one slot?** *Recommend solo first.* It is the Entei decision, and a shared slot
   needs XD8 and the two-player battle question (`NETHER_DUNGEON_SCOPE.md` X5).
8. **Gems as the reward spine?** **Superseded** by the owner's 2026-10-08 direction: progression is the dungeons'
   exclusive and gems their volume (section 4). The blank gate it leaned on does not exist.
9. **The Nether pair after the overworld ones, on the same engine?** *Recommend yes*, with Entei's room re-themed as
   `NETHER_ENCOUNTERS.md` Q5 proposes.

From `DROPS_PROGRESSION_SPLIT.md` section 8:
10. **The Lucky Egg** (its Q1): **decided, moved** (0.1, section 4).
11. **Option C's roll counts**, 2.25 / 3.75 / 5.625 gems by tier (its Q2): **OPEN.** *Recommend keep them.*
12. **The armour den's home** (its Q3): **decided, the Last Cistern** (2.3).
13. **The counters' priced progression**, vitamins and the Ability Capsule (its Q4): **OPEN.** *Recommend it stays*:
    priced, and the direction is about free drops.
14. **Dragon's breath on the Pasture Loot blacklist** (its Q5; the Ability Capsule's brewing input): **OPEN.**
    *Recommend yes.*

From `DUNGEON_PLACEMENT.md` section 6, all **OPEN**: Q11 (every catch after the Champion), Q12 (the Beast Ball idle
from Cinderlee to the Champion), Q13 (the Temple Calendar as the window's dungeon), Q14 (Koraidon and Miraidon), Q15
(which sites are dungeon bosses; `data/key_ball.json` `bosses_why` already treats the shrines, the lake trio, the
Regis, Lugia, Hoopa, Ursaluna, the Gulch Megas and the raid dens as not), and paradox threats at band 4.

## 9. Unknowns, as experiments or research

| Id | Question | Who |
|---|---|---|
| R-D1 | Cobblemon 1.8.0 type gem clusters: the 18 gem and cluster block ids, what breaking one drops, the tool, whether they grow | `cobblemon-researcher`, jar |
| R-D2 | CobbleDollars' automatic NPC payout: its config key, and the arena's clawback (EXP-060's shape) as a reusable pattern | `cobblemon-researcher` |
| R-D3 | Whether `shiny` is a parsed property for `spawnpokemonat`, and the NPC pool | `cobblemon-researcher` |
| R-D4 | Whether a forfeit, a flee or a logout mid NPC battle ends it (open since `arena-per-player-opponents.md:371`) | staging, with XD6 |
| XD1-XD8 | Section 7.4 | builder designs, main session runs, `qa-reviewer` grades |
| X3, X5, X6 | A candy at the cap is refused and kept; a dual-type alpha's gem types; option C's callback loads (`DROPS_PROGRESSION_SPLIT.md` section 6) | staging, main session |
| EXP-064 | The Beast Ball key on a tagged boss (NOT_EXECUTED) | staging, main session |
