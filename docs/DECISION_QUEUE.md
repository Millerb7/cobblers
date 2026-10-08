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
| **B3** | **CLOSED (2026-10-06 sweep): `data/gym_trainers.json` now carries `held: false` for Giovanni (STATE "The leaders' teams are ours"), so all eight leaders' teams reach a player.** Was: Giovanni's hold: one stale field. `data/trainers.json` has him authored, six Pokemon at 52–55 (top = his contract's 55), singles, `blocked_by: None`. Only `data/gym_trainers.json`'s `held: true` skips him, and its reason quotes an empty team that no longer exists. | Clearing it makes **eight** leaders' teams reach a player instead of seven. It changes what a player fights, so it was left. |
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

### B12. All six gatehouse walkways are impassable on foot — pre-existing, found moving G2

`tools/rift_zones.py`'s `cmd_build` snaps each wall perpendicular to the dominant axis, so **every
sideways shift seals its own diagonal**. G2's standable columns come out as **four disconnected pieces**
and only one of those breaks is the barrier that is supposed to stop you. **Passing still works, because
passing is a teleport. Leaving on foot does not** — the exit box is one sealed diagonal from the
walkway's inner mouth.

Proved not to be the mover's doing: the post it left at the old site reproduces the old G2 shell block
for block and splits identically, 1 of 8 before and 1 of 8 after. Recorded in `data/rift_zones.json`
`measured_defects`.

**It is inert today** — `cobblers_rift_zones` is still in `reapply.py`'s `EXCLUDED`, nothing is installed,
and the guards are armour-stand placeholders. So this is not urgent, but **it is what would have shipped**
the day the zone system was switched on, in all six gatehouses at once. It wants the shell geometry fixed
and a flood-fill test over the *emitted function*, independent of the geometry that writes it. **No test
anywhere references `rift_zones`.**

### B13. The old gate was not merely late — it was unreachable

Worse than the report that prompted B11b. **Z2's boxes begin 53 blocks along the road from the
trailhead**, while the gate sat 318.70 blocks further on. So an unqualified player crossed into the zone,
was teleported to the old turn-back at (3591.5, 90, 5032.5) — 144 blocks away on the Rift floor — and
**could never reach the warden at all**. The gate is now at the trailhead (3548, 5322) with its turn-back
8 blocks back down the road at the gatehouse door.

### B14. Stale (3738, 5082) references left outside the mover's scope

This coordinate has propagated before — it is how the retired cradle coordinate reached the League
steward. Fixed in scope: `tools/rift_zones.py`'s comments and `routes.json`'s waypoint basis (the
waypoint itself deliberately **not** moved, because that would re-run the A*). **Still stale and listed
rather than silently changed:** `data/rift_sculpt.json:49,51`; **`data/quests.json:1105`**
(`npc_main_rift_surveyor`, anchor `victory_road_entry`) and **`:1215`**
(`rift_victory_road_damage`) — both story-side; `docs/DECISION_QUEUE.md:76`; `RIFT_ZONES.md:17,22,45`;
`RIFT_STATUS.md:111`; `SOUTHERN_RIFT.md:54,58,91,100`. Benign and left alone: `landmarks.json`'s
south-west arm geography, `placements.json:2276`, and `routes.json`'s corridor points.

### B15. The Jungle Isle drowned and four systems never heard about it — found from the air, 2026-10-01

**Measured, not relayed.** The water pass put the whole Jungle Isle under the sea: every column inside its
polygon is at or below y61 against a sea level of **62** (`data/regions.json`'s own measured block says
`max: 61.0`, and the canonical heightmap agrees). Four things still stand on it as if it were land.

**(a) Four world trees hang in the air.** `data/elder_trees.json` is a pinned file, and
`tools/elder_trees.py` takes each trunk's `ground_y` straight out of it — skipping both the heightmap and
the `wet = heights <= sea_level` guard its own siting path applies, because the pinned branch sets
`included = []`. The four jungle elders kept their pre-water heights:

| Elder | At | Records | Heightmap | Hanging by |
|---|---|---|---|---|
| `elder_jungle_west_2` | (4968, 7416) | 126 | 58 | **68 blocks** |
| `elder_jungle_east_1` | (5216, 7904) | 81 | 53 | 28 |
| `elder_jungle_east_2` | (5248, 6976) | 77 | 54 | 23 |
| `elder_jungle_west_1` | (4464, 7312) | 70 | 53 | 17 |

**Exactly 4 of the 48 pinned elders are wrong, and all four are on the drowned isle** — the other 44 match
the heightmap exactly. Their **16 bird Habitat Blocks** ride inside the trunks. Your options are the two you
named: **extend the trunks down to the seabed** (they become drowned world-trees, and the birds — currently
at trunk +12/+35/+58/+74 — move up or drown with them), or **re-site all four onto land**, which means
editing `data/elder_trees.json` and `data/habitat_blocks.json` together, as the file's own note requires.

**Why nothing caught it:** `tests/test_elder_birds.py` checks the doc table, the pinned file and the site
file **against each other**. All three carry the same stale number, so three sources agreed and only the
terrain disagreed — exactly the closed-loop audit CLAUDE.md warns about.
`tests/test_pinned_ground_is_the_heightmap.py` now asks the terrain instead; the four are a **strict xfail**
pointing here, so answering this turns it green. The same sweep cleared every other `ground_y` in `data/`.

**(b) The drowned ruin and the raft town are built on the same water.** `jungle_ruins` was already re-seated
on 2026-09-30 for *this very bug* (it had been hanging 60–64 blocks up) and correctly became
`minecraft:underwater_ruin/*` at seabed+1. Nobody then checked what else was there. Measured over the
rotated 16x16 footprints against `data/sea_town.json`'s 59 rectangles:

| Ruin | Overlaps | Columns |
|---|---|---|
| `ruin_east_court` (5170, 7387) | raft 1 | **192** |
| `ruin_great_hall` (5152, 7503) | a building + a walk | 120 |
| `ruin_west_wall` (5145, 7412) | raft 13 + a building | 104 |
| `ruin_north_gate` (5147, 7351) | raft 3 + a building | 80 |
| `ruin_court_east`, `ruin_court_west` | nothing | 0 |

**Four of six ruins, 496 columns, inside the raft town** — one of them 192 columns inside a single raft.
That is the stone ruin standing in the middle of Pacifidlog in your third screenshot. **Options:** move the
ruin set clear of the town (it is the newer arrival on the owner's reading, but the *town* is the thing with
services); drop `jungle_ruins` entirely and let the sunken isle be bare seabed; or keep the collision
deliberately and rebuild the town square *around* the ruin, which is the only one that costs real work but is
also the only one that makes the overlap read as intended. `tools/sea_town.py` refuses overlaps **inside its
own plan** and cannot see another settlement's, which is why this was silent.

**(c) Two names still announce a place that no longer exists.** `regions.json` keeps `jungle_isle` ("Jungle
Isle", jungle and sparse-jungle paint over open water) and `towns.json` keeps `jungle_ruins`' display name
**"Sunken Court"**. Both fire over the sea, which is the title in your second screenshot. "Sunken Court" is
arguably *better* now than when it was written; "Jungle Isle" over 1.2 km2 of ocean is not.

### B16. Articuno — TAKEN, on the summit, (672, 369)

The owner, 2026-10-02, once the ceiling premise was corrected: *"Paste the real Cobbleverse Articuno tower on the
summit; its crown shows over the crest from the research camp, so the camp's telescope sees what the researchers
study. The shoulder copy is removed."* Corner (672, 369), seat y310, top occupied layer y383; the tower's centre is
the summit outpost's centre (682, 380); all 440 footprint columns are ground y310, so **zero cut, zero fill**. The
ceiling is this runtime's **y575** (`cobblers_height`: min_y -64, height 640), so the margin is **192**; `max_y`
310 caps terrain, not built blocks. From the research camp's telescope the crown shows over the false crest from
y370 to y383 (14 layers, measured by the camp audit's exact column walk), bearing 354, ~313 blocks.

**What this corrects.** The 2026-10-01 refusal held the summit against "the 1.21.1 build ceiling of 320"; that is
vanilla's, not ours. The owner's earlier answer, *"take (904, 320)"* on the east shoulder (seat y151, top y224), was
built on that premise and is kept in the record under `superseded_shoulder_site`. Its staging copy, pasted by hand
for EXP-048, is removed by the staging-only `cobblers:articuno_cleanup/shoulder` (`tools/articuno_tower.py`). The
two measured alternatives stay in the file as measurements, not options. Recorded in
`data/adopted_legendary_sites.json` as `adopted_articuno_shrine`; the re-apply step is
`tools/articuno_tower.py placement_steps()`, not yet in `tools/reapply.py`.

**Still gated by EXP-LEG-ALTAR**, like the other three: all four carry LumyMon altars and nothing has yet shown a
pasted altar responds to anything. Placing is not the question; functioning is.

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
| **D1** | **ANSWERED (the owner, 2026-10-01, CLAUDE.md "A guard that names its own remedy is not a refusal"): following the guard's remedy is compliance.** Was: does the worktree guard's "split it into plain commands" count as a refusal? Three agents hit it and then used the `Write` tool for the same in-worktree path. Strictly CLAUDE.md's rule is "a different tool reaching the same outcome", and that is what happened — three times. | It will keep happening. Either the rule gets an explicit exception for a guard that names its own remedy, or agents must stop and hand back. |
| **D2** | **`.worktreeinclude` did nothing.** It existed, listed the right paths, was tested, copied none of the 338 files, and was removed (`19838cc`). | A harness question, not a repo one. Worth raising upstream if fan-out needs those files — though tonight showed the heightmap is readable without it. |
| **D3** | **Seven doc/data/code disagreements** are recorded and deliberately not silently fixed (`docs/HANDOVER_SESSION.md` section 5): stair towers 8 vs 9, `rift_deep.json`'s dead `"banks": 10`, DEEP_CITY's "about 130 buildings" against 196 built, its stale status header, the cradle coordinate, `GYM_INTERIORS.md`'s stale cooldown rule, and `gulch_mine.json`'s `megas.why` referencing a key that was missing. | Each wants an owner's "fix it" or "leave it". |
