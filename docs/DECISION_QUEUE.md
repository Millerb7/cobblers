# Decision queue

**Everything waiting on the owner, in one list, so it can be answered in a single pass.** The owner,
2026-10-01: *"That has cost more throughput than anything else."*

Each item: what is blocked, what the options are, and what a session will do with each answer. **Nothing
here is urgent in the sense of unsafe** — they are all "a session cannot choose this for you".

## A. Irreversible or world-shaping — these actually block work

| # | Decision | Why it is yours | Options |
|---|---|---|---|
| **A1** | **Taken (c), and the price it named need not be paid.** `tools/rift_heightmap.py --plan` now measures the applied sculpt. The cause was *not* the normals bug: `5c82e98`'s fix **was** re-applied (`data/world.json` records its `blocks_moved` 12,811,417, the figure that commit reports). All 10,867 drifted columns sat at **one entrance** — Victory Road was re-routed by `35f2a56` after the sculpt, so re-snapping its gap moved it 47 ring stations. `--plan` reads each gap off the applied rim instead, and the sculpt then reproduces the applied heightmap **pixel for pixel**, so the pixel-exact proof is kept, not traded away. | — | Done. |
| **A2** | **Resolved by A1.** `derived/rift_sculpt/plan.json` is regenerated, not repinned: its `sha256` is now the `0d9b5f1e…` `data/world.json` records for the sculpt, written by the tool. | — | Done. |
| **A3** | **The proper staging world.** An export from the pinned heightmap is running or queued, carrying the seed from `cobblers-10240.pre-rescale` (you approved this). | Already approved — recorded here so the chain is visible. | Done unless you say otherwise. |

## B. Design decisions a session should not take for you

| # | Decision | Context |
|---|---|---|
| **B1** | **Which tenth trainer stands at Victory Road's exit ravine.** Main's **League Examiner** (4 Pokemon, Tailwind Crobat, Focus Sash) is what emits today; our **Gate Warden** (3 Pokemon, holds a door) is kept in `data/vr_trainers.json`'s `superseded_roster`. | Two different characters, not two versions of one. Whichever loses stays in the file. |
| **B2** | **CORRECTED: 10, not 38, superseded seat-file dialogue sets.** The roster's lines are what a player hears; the seat files' hand-written lines are the fallback and currently dead (the generator prints the count every run). | Ten Victory Road + 28 late-route trainers. Nothing is lost either way — it is *which lines play*. |
| **B3** | **Giovanni's hold: one stale field.** `data/trainers.json` has him authored, six Pokemon at 52–55 (top = his contract's 55), singles, `blocked_by: None`. Only `data/gym_trainers.json`'s `held: true` skips him, and its reason quotes an empty team that no longer exists. | Clearing it makes **eight** leaders' teams reach a player instead of seven. It changes what a player fights, so it was left. |
| **B4** | **The open-air Mega dens' gate.** Each of the seven has a 41-block zone round its pad with the turn-back facing the den — *seen, not reached*. The alternative is no zone at all, letting the level band (60 outer / 67 deeper against a cap of 50) be the only gate. | You said "the gates stay as designed", which is why the zone is there — but a turn-back in open country is a different thing from one at a rockslide. |
| **B5** | **Unit 3, the Slip: cancelled on measurement, confirm it stays cancelled.** There is no spur and no walls: the floor between the camp and the relic area is **182–211 columns wide everywhere** and nothing rises above y110. | You cancelled it. Recorded so it is not reopened. Unit 2 (relic underground) was the reason. |
| **B6** | **The ladder's shape.** `docs/mechanics/PROGRESSION_LADDER.md` argues the backpack is **not** the spine: the convenience arc finishes at **badge 3 of 8**, because gold/diamond/netherite add ~12 slots each. It recommends two strands per counter, and the power strand if only one. | Nine numbered questions at the end of that file. An income measurement is in this wave and may re-price several rungs. |
| **B7** | **`crafting_upgrade`'s home.** The ladder's own test failed one rung: portable crafting at badge 6 is too late for "never build a house". Proposed move: Brock's, priced out of reach until badge 3 — **price as the gate**, needing no flag, datapack or restart. | A cheap, reversible call. |

### B8. The trainer card's price collides with the first town's income — found by two agents in one wave

The card is now sold at **Pallet's Poke Mart for 500** (`data/traders.json`), priced from Cobbleverse's
own `default_shop.json` rather than invented, and argued well: the card gates *natural* trainer spawns, so
it must precede the Pallet → Route 1 → Brock stretch where the ambient layer teaches what a trainer is.

In the same wave the income measurement found that **at badge 0 a player has no authored income at all**:
not one reward, quest or first-win grant in the whole repository pays a dollar (`data/rewards.json` is 11
items, all nine `first_win_rewards` are a badge plus a TM, and `grep` for currency in `data/quests.json`
returns nothing), and **no starting-balance key exists in any config**.

So the only money before Brock is **wild-Pokemon income**, which is `true` in config and **has never been
measured** — the measurement's own biggest hole. The card is therefore reachable or not depending on a
number nobody has.

**Options:** (a) leave it and measure wild income first (one experiment, ~10 minutes); (b) drop the price,
accepting two prices for one item if the `defaultShop` fallback turns out to exist; (c) grant the card
with the starter instead of selling it, which makes the ambient layer unconditional; (d) accept that a new
player catches a few wild Pokemon before buying it, which may simply be the intended shape.

### B9. Prices are off by a scale factor, not a shape

The income measurement's structural result, which is worth more than its list: **leg income rises 3.8x
across eight badges and the ladder's per-badge ask rises 3.5x — the slopes match, the intercept is about
2.5x off.** Full ladder including off-path is **$172,650** against $58,031 earned (model B).

So the cheapest fix is one of two single changes, not a re-design: divide the price column by ~2.5, or
raise `cobbleDollarsIncomeMultiplier` from 0.5 to about 1.25 (one key, but it also multiplies what the
bank's 82 unreviewed sell prices leak). **Worst offenders:** Pallet's $550 at badge 0 (impossible,
above), Brock's `crafting_upgrade` at 7,500 (2.0x of everything earned to badge 1), Giovanni's 45,000
shelf, and the mining town's 15,800 at `gym3_cleared` (1.4x of *total* income to that point). Nothing is
priced too low.

### B10. A 20%-of-balance blackout charge and a 20,000 purchase cannot coexist

`data/blackout.json` takes **20% of balance, rounded up**, on a blackout. The ladder asks up to 20,000 for
a single item. Saving for one means one blackout costs 4,000. That is a **cross-system contract**, not a
price — it belongs in `data/system_contracts.json` with a test, whichever way you resolve it.

### B11. Two things the trailhead move surfaced, neither of them the trailhead

**The route runs 1-2 blocks from an 18-block drop.** Between x3556 and x3565 around z5287-5302 the
ground falls from y111 to y93-95, right beside Victory Road's walked line. Verified from the heightmap.
The trailhead ramp itself refuses those columns (33 refused, by a 1-block step rule that is Minecraft's
own, not a fudge), so nothing is built over the edge — but a player walks past it. **A railing, or a
route review.** Your call which.

**`rift_entry` and the zone system's G2 gatehouse both sit at (3738, 5082)** — on the route, distance 0,
but **145 blocks inside the basin and 300+ from the descent**. So the warden's marker is now at the
trailhead (3548, 114, 5322) and the gate it belongs to is a long way in. Moving either is in
`data/routes.json` or `data/rift_zones.json`, both of which were out of the mover's scope, so it stopped
and said so. **Do the marker and the gate belong together, and if so which one moves?**

## C. In-game checks only you can make

| # | Check | Why a session cannot |
|---|---|---|
| **C1** | **Does Hoopa RENDER?** `pokespawn hoopa` spawns `cobblemon:hoopa` — the species exists in 1.8.0, measured tonight. Whether it draws a model or a placeholder is a **client** fact. | RCON sees entities, not models. `docs/world-building/DEEP_CITY.md`'s whole relic area rests on a visible Hoopa. One glance. |
| **C2** | **Does a gated counter fall back to `defaultShop`?** A plain merchant's shop NBT is empty, so nothing injects the global shop at summon — but the GUI's behaviour is unmeasured. | Needs a player to open a counter. Decides whether the trainer-card fix was even necessary. |
| **C2b** | **Does `cobbleDollarsIncomeMultiplier` scale BANK SELL-BACKS as well as battle income?** Sell one `minecraft:emerald_block` to the bank on the running staging server, which is still at **0.5**. Raw price is **3,750** (`base-pack/cobbleverse/config/cobbledollars/bank.json`). **3,750 means the multiplier does not touch sales and 1.25 is safe. 1,875 means it does — and raising it to 1.25 makes that block sell for 9,375, which turns the bank into a money printer and invalidates the whole re-price.** | 30 seconds, and it must happen before the multiplier reaches a server. Raised by the ladder agent, not by me, after I had already shipped the overlay. |
| **C3** | **Does Brock refuse a rematch with the badge in hand?** Long-standing: installed is not working. | Needs a fight. |
| **C4** | **Do two players share one NPC's dialogue?** EXP-022's two-player test is unrun, blocked on a second account. | Decides whether gated counters work in multiplayer. |

## D. Process questions

| # | Question | Context |
|---|---|---|
| **D1** | **Does the worktree guard's "split it into plain commands" count as a refusal?** Three agents hit it and then used the `Write` tool for the same in-worktree path. Strictly CLAUDE.md's rule is "a different tool reaching the same outcome", and that is what happened — three times. | It will keep happening. Either the rule gets an explicit exception for a guard that names its own remedy, or agents must stop and hand back. |
| **D2** | **`.worktreeinclude` did nothing.** It existed, listed the right paths, was tested, copied none of the 338 files, and was removed (`19838cc`). | A harness question, not a repo one. Worth raising upstream if fan-out needs those files — though tonight showed the heightmap is readable without it. |
| **D3** | **Seven doc/data/code disagreements** are recorded and deliberately not silently fixed (`docs/HANDOVER_SESSION.md` section 5): stair towers 8 vs 9, `rift_deep.json`'s dead `"banks": 10`, DEEP_CITY's "about 130 buildings" against 196 built, its stale status header, the cradle coordinate, `GYM_INTERIORS.md`'s stale cooldown rule, and `gulch_mine.json`'s `megas.why` referencing a key that was missing. | Each wants an owner's "fix it" or "leave it". |
