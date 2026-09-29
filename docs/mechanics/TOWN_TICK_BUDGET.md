# Town tick budget

What a Cobblers town costs the server per tick, what it would cost with trainers added, and the
measurements that would settle the parts nobody has measured.

**The budget.** A tick is 50 ms. 50 ms = 50,000 microseconds = **100%**. Every figure below is quoted
in microseconds (us) per tick and as a percentage of that.

**Every number in this document carries a label.** Use them; they are the point of the document.

| Label | Means |
| --- | --- |
| **MEASURED** | somebody ran it on a server and read a number off it. The source is named. |
| **CALIBRATED** | arithmetic on a measured number: a count from the repo multiplied by a measured unit cost. |
| **EXTRAPOLATED** | a bracket from general knowledge of how Minecraft ticks. **Not evidence.** It exists so the measurement has a prediction to falsify. |
| **UNKNOWN** | nobody knows, and no honest bracket is available. |

This document is the **offline half**: the inventory is read out of the repository, and the
measurement plan in part 3 is written for the main session to run. Nothing here was run against a
server. The staging server was up and the owner was playing on it while this was written.

---

## 1. The two calibration points

### 1a. The ambient workers (MEASURED)

`docs/STATE.md:134`, the main session's `/tick query` medians, 2026-09-28:

> a carrier about **25 us** a tick, a stationary worker about **3 us**, only while a player is within 48

That 48 is `data/ambient.json:6` `active_radius`, enforced at `tools/ambient.py:343`: the keeper sets
`#<id>_on` to 1 only when a player is inside it, and `tools/ambient.py:328` runs the worker's step
only when that score is 1. **An empty town's workers cost nothing.** Confirmed structurally, not just
by the note.

The owner's per-town limit follows from it (`data/ambient.json:9`): 2 carriers and 4 stationary, "the
limit is how busy a town looks and what a client draws, not the tick".

### 1b. The cost of a plain command line (CALIBRATED, weak)

`tools/ambient.py:434-435`, a second measurement recorded in the code:

> A carrier's route is not one line per point (a carrier cost **0.41 ms a tick** that way, measured on
> staging 2026-09-28, most of it failed score tests)

That implementation emitted `2n` `execute if score … run function` lines per tick, `n` = the carrier's
densified route points. The six carriers' `n` (computed here from `data/ambient.json` and
`tools/ambient.py:148` `densify` at `step_blocks` 0.18):

| carrier | town | route length | points `n` | old line count `2n` |
| --- | --- | ---: | ---: | ---: |
| `brock_stone_carrier` | gym1_town | 35.2 | 197 | 394 |
| `blaine_sample_carrier` | gym7_town | 35.9 | 201 | 402 |
| `northlight_log_carrier` | northlight | 25.5 | 143 | 286 |
| `giovanni_supply_carrier` | gym8_town | 17.0 | 96 | 192 |
| `mining_ore_carrier` | mining_town | 12.4 | 70 | 140 |
| `koga_reed_carrier` | gym5_town | 9.5 | 54 | 108 |

410 us spread over 108–402 lines is **1.0–3.8 us per line**, and that is an **upper** bound: the 0.41 ms
also paid for the tp macro, the item display and the particle work. The note does not say which
carrier, so the bracket cannot be narrowed offline.

**Working figure used below: 1 us per command line (optimistic), 4 us per command line (pessimistic).**
Label every use of it CALIBRATED, and treat the spread as the honest uncertainty. The first thing part
3 measures is this constant, because six of the predictions rest on it.

### 1c. What is already known not to cost anything (MEASURED)

`data/spawn_suppression.json:11`, EXP-012, 2026-09-17 on a disposable world:

> 1,729 files, 368 MB, +8 s boot, +1.5 GB heap, +8.5 s reload, **no measurable tick cost**

`cobblers_suppress` re-emits every inherited spawn file with coordinate anticonditions. Its cost is
boot time, reload time and heap — **not** ticks. It is off the per-tick budget and stays off it.

### 1d. The structural bound nothing can cross

`server/config/server.properties.example:69` sets `simulation-distance=6`. Entities tick only within
six chunks (96 blocks) of a player; `view-distance=10` only decides what a client is sent.
`max-players=8` (line 14).

So: **an unvisited town costs zero ticks.** The whole per-town budget is a per-*occupied*-town budget,
and the server-wide ceiling is at most eight towns' worth at once.

---

## 2. The offline inventory

### 2.1 Villagers

**There are no AI villagers anywhere in Cobblers today. Not one.** This is the single biggest
correction the inventory makes to the intuition behind the question.

| what | count | where it comes from |
| --- | ---: | --- |
| Real vanilla villagers, with AI, brains, POI search, gossip, breeding | **0** | Nothing places them. `docs/world-building/TOWNS_AND_VILLAGES.md:62-71` and `docs/world-building/STRUCTURE_DATA_FALLOUT.md:144-150` both record "about 40–50, 4–6 per gym town" as a **proposal**, and both say villagers never spawn on their own — only worldgen, breeding, curing, or eggs make them. No `data/` file places any. |
| `NoAI` trader clerks | **26**, in 14 settlements | `data/traders.json` (26 records). `tools/traders.py:259-262` gives each `PersistenceRequired` and `NoAI:1b`; the entity type comes from the donor shopkeeper template (`tools/traders.py:137`, default `minecraft:villager`, in practice also CobbleDollars merchants). Placed once by `vendors_<town>` / `_place` / `_done` (`tools/traders.py:242,288`), not per tick. |
| `NoAI` Cutter villagers | **3**, at the gulch (not a town) | `tools/gulch_mine.py:1262`, summoned `NoAI:1b,Invulnerable:1b`. |

Clerks per settlement: gym1_town **7**, gym2_town **6**, mining_town **2**, and **1** each in gym3–gym8,
hometown, northlight, sunset_west, tea_town, sea_town.

**Why the distinction is load-bearing.** A `NoAI` mob skips `serverAiStep`, so it runs no goal
selector, no brain, no sensors and no path search. A villager with AI runs the most expensive brain in
vanilla: POI lookups for bed, job site and meeting point, gossip, restock, panic and schedule. They are
not the same cost source and the 25/3 us calibration says nothing about either. Both are UNKNOWN below.

### 2.2 Trainers

**Today: a town holds zero.** All 18 placed trainers are on Routes 1–3 and inside the Route 1 mansion.

| group | count | file |
| --- | ---: | --- |
| Route 1 | 4 | `data/route_trainers.json` |
| Route 2 (incl. the North Bank Angler) | 4 | `data/route_trainers.json` |
| Route 3 | 5 | `data/route_trainers.json` |
| Route 1 mansion guardians | 5 | `data/mansion_guardians.json` |
| **In any town** | **0** | — |

Placement is not a function: `tools/reapply.py` R17 runs
`rctmod trainer summon_persistent <id> <x> <y> <z>` over RCON once
(`tools/route_trainers.py:47-48`).

There are **three separate trainer costs**, and they must not be conflated.

**(a) rctmod's on-sight scanning — UNKNOWN, and the likely dominant term.**
`modpack/config/rctmod-server.toml:117,122,129`: `forceBattleOnSight = true`,
`forceBattleMaxDistance = 16.0`, `forceBattleLookTicks = 30`. Our own mob records set the per-trainer
`forceBattleOnSight` only for the first Route 1 trainer and the five guardians
(`tools/route_trainers.py:101-104`); whether rctmod falls back to the global config for the twelve that
omit the key is **not readable from this repo** — it needs the jar or a measurement. A `rctmod:trainer`
is a live `PathfinderMob`: it runs goals, look control and sensing every tick even pinned at movement
speed 0 (the cycle at `tools/route_trainers.py:149` exists precisely because battle knockback still
moves it, i.e. it is a physical, ticking mob). **Nothing about the 25/3 us figures transfers to it.**

Natural rctmod spawning is separate and small here: `spawnIntervalTicks = 600`,
`maxTrainersPerPlayer = 6`, `maxTrainersTotal = 60`, `spawningRequiresTrainerCard = true`
(`rctmod-server.toml:21,60,66,87`), plus `despawnTicksIfUnseen = 6000` (line 35). One spawn attempt per
player per 30 seconds is not a tick cost worth modelling. **But** `spawnTrainerAssociation = true`
(line 93) spawns an association NPC near "at least 3 occupied beds and a village center" — so the
moment real villagers with beds go into a town, an extra AI mob appears there for free. Flagged, not
budgeted.

**(b) our `Cooldown` cycle — CALIBRATED, small.**
`tools/route_trainers.py:62` `PERIOD = 10`. `trainers/tick` is 2 lines every tick
(`tools/route_trainers.py:130-132`); every 10th tick it runs `trainers/cycle`, which is 2 header lines
plus exactly **4 lines per placed trainer** (`tools/route_trainers.py:139-152`):

1. `execute as @e[type=rctmod:trainer,x=…,y=…,z=…,distance=..24,nbt={TrainerId:"…"},InBattle:0b] … run tp @s …` — seat-keeping.
2. `execute positioned <seat> as @a[distance=..N] run runmolang "…"` — the beaten-tag sync. `N` = `max(sight_distance, 6) + 1`, so **9** for a route trainer (no `sight_distance` key → default 8.0) and **7** for a guardian (`sight_distance` 3.0–4.5). This is the only line with real work in it, and it only fires for a player standing within 7–9 blocks of that trainer.
3. same selector, plus two `@a` range tests, `run data merge entity @s {Cooldown:40}` — the rematch refusal.

Selector breadth: the `@e` terms are position-anchored (`distance=..24` around the seat) and
type-filtered, so they walk the `rctmod:trainer` type index, not all entities. The `@a` terms walk the
player list, which is at most 8.

Today, 18 trainers: `2 + 4x18 = 74` lines every 10 ticks = **7.4 lines/tick amortised**, plus the 2-line
driver = **9.4 lines/tick**. At 1–4 us/line that is **9–38 us/tick**, CALIBRATED, and it is paid
server-wide whether or not anyone is near a trainer.

**(c) the seat-keeping loop** is line 1 of (b) — it is not a separate loop. Cost is inside the 9.4
lines/tick above.

Per added town trainer: **+0.4 lines/tick = +0.4–1.6 us/tick** of datapack cost (CALIBRATED), plus one
`rctmod:trainer` entity's tick (UNKNOWN). Also `battleCooldownTicks: 240` and `maxTrainerDefeats: 1` in
the mob record (`tools/route_trainers.py:99`) — data, not a loop.

### 2.3 Habitat blocks and spawn checks in a settled area

**Habitat blocks in towns today: effectively zero.** `data/habitat_blocks.json` holds **333** blocks
(81 `natural` with `ReplaceSpawns: true`, 252 `activated`). Testing each position against every
`data/towns.json` footprint grown by 64 blocks gives **5** hits: 4 in `jungle_ruins` and 1 at the
`league`. **No settled, worker-bearing town has one.** So the habitat-block term in a town budget is
**0 us today** and only becomes a cost when one is placed.

**Cobblemon's spawn pass — a per-player cost, not a per-town cost.**
`modpack/config/cobblemon/main.json`: `ticksBetweenSpawnAttempts` 10.0 (line 26),
`minimumSpawningZoneDistanceFromPlayer` 16.0 / `maximumSpawningZoneDistanceFromPlayer` 64.0 (lines
27-28), `maximumSpawnsPerPass` 1 (line 29), `spawningZoneDiameter` 8 / `spawningZoneHeight` 16 (lines
23-24), `minimumDistanceBetweenEntities` 8.0 (line 20), `pokemonPerChunk` 0.25 (line 42),
`maxNearbyBlocksHorizontalRange` 4 / `maxNearbyBlocksVerticalRange` 2 (lines 21-22).

One pass per player every 10 ticks, one spawn at most per pass. The pass is a per-player cost that a
town does not change — **except** that in a settled area the pass mostly *fails* (buildings, paving,
light, `minimumDistanceBetweenEntities` against the workers and clerks), and a failed pass still walks
the roster. Cost: **UNKNOWN**; the measurement plan isolates it by standing in a town with the same
loaded-chunk profile as a control site.

`pokemonPerChunk` 0.25 is a *cap on standing population* shared across every loaded chunk
(`docs/HANDOVER_SESSION.md:198-201`). It bounds how many wild Pokemon entities a player's chunks can
hold, so it bounds the wild-entity term directly — the town does not get its own allowance.

**The suppression's own cost: MEASURED as none** (section 1c). It is a data-volume cost, not a tick
cost. Do not budget for it.

**Spawn-free zones.** `data/spawn_suppression.json` `spawn_free_zones` cuts the League precinct and
each gym's box out of every roster and every inherited pool. Inside a gym box, the spawn pass finds no
eligible detail at all — cheaper, not dearer.

### 2.4 Everything else that runs in a town

Rigorously separated into per-tick, periodic and event-driven. **A pack that only reacts to an
advancement, a callback or a zone entry is not a per-tick cost.**

| Pack / source | per tick? | period | selector breadth | count per town today | cost basis |
| --- | --- | --- | --- | ---: | --- |
| `cobblers_ambient` driver (`tools/ambient.py:309-313`) | **yes** | every tick | `@e[type=minecraft:interaction,tag=cobblers.amb.i]` **twice**, plus one `execute if score` per worker | server-wide: 4 + 20 = **24 lines/tick** | CALIBRATED 24–96 us/tick, always, even with nobody online |
| `cobblers_ambient` keeper (`tools/ambient.py:311,341-343`) | no | every **40** ticks (`keep_every`) | 1 + 2 lines per worker in `keep_all`; each worker's 5-line `keep` runs only where its station chunk is loaded, then returns immediately unless a player is within `keep_radius` 96 | 41 lines / 40 ticks ≈ **1.0 line/tick** | CALIBRATED 1–4 us/tick |
| `cobblers_ambient` worker step (`tools/ambient.py:328`, `:432`) | **yes**, while a player is within 48 | every tick | the worker's own tagged selector | 1 carrier + 1 stationary (gym1_town); cap 2 + 4 | **MEASURED** 25 us / 3 us each |
| `cobblers_blackout` driver (`tools/blackout_pack.py:170-191`) | **yes** | every tick | 17 lines, including `@e[type=cobblemon:pokemon,tag=cobblers.guardian]` — a **global Pokemon entity scan every tick** | server-wide **17 lines/tick** | CALIBRATED 17–68 us/tick |
| `cobblers_blackout` water ladder (`tools/blackout_pack.py:733-754` + `water/qualify`, `water/surfaced`, `water/strip_vanilla`) | **yes** | every tick, **per player**, in survival/adventure | `@e[type=player,gamemode=!creative,gamemode=!spectator]`, then ~39 lines as that player | **~39 lines per player per tick** | CALIBRATED **39–156 us per player**. The largest single datapack term in the game. **Superseded 2026-09-29** by the early exit below: 7 lines on the dry path. |
| `cobblers_blackout` checkpoint sample | no | every **5** ticks per player | ~12 lines | ≈ 2.4 lines/tick/player | CALIBRATED 2–10 us |
| `cobblers_blackout` surface tick | no | every `surface.sample_ticks` per swimmer | ~27 lines | 0 on land | CALIBRATED, 0 in a town |
| `cobblers_blackout` blackout/claims/recovery | **no — event** | a death, a `battle_victory` callback, an `any_block_use` on a healing machine or waystone | — | 0 | not a tick cost |
| `cobblers_trainers` (`tools/route_trainers.py:62,130-152`) | **yes** (driver) | cycle every **10** ticks | `@e[type=rctmod:trainer, …, distance=..24]` and `@a[distance=..7..9]` per trainer | 2 + 4x18 per 10 ticks = **9.4 lines/tick** server-wide; **0 trainers in a town** | CALIBRATED 9–38 us/tick |
| `cobblers_scenes` (`tools/scenes_pack.py:58,429-430,450`) | **yes** (driver) | cycle every **20** ticks (`PERIOD = 20`) | `@e[tag=cobblers_actor …]`, then one `@a[<scene box>]` beat per scene with actors/effects/zones | 5 header + 7 beats + no_build ≈ **14 lines / 20 ticks ≈ 0.7 line/tick**; **0 scenes in a town** (all 10 are on Routes 1–3) | CALIBRATED under 3 us/tick |
| `cobblers_titles` (`tools/location_titles.py:70,123`) | **no — advancement** | vanilla fires `minecraft:location` about **once a second**, per player, and only for advancements the player does not yet hold | 21 regions rasterised to **1,172** boxes on a 32-grid (counted here via `tools/subregion_boxes.py`), each an `any_of` of position-range predicates; plus ~30 settlements at 1 box each | ≈ **1,100–1,200 box tests per player per second** | EXTRAPOLATED: each test is a float range compare; order **1–10 us/tick amortised**. Real but negligible; scales with players, not with town population. |
| `cobblers_levelcap` (`tools/levelcap_pack.py:30`) | **no — callback** | only on `poke_ball_capture_calculated` | — | 0 | not a tick cost |
| `cobblers_progression` (`tools/progression_pack.py:302-310`) | **yes** | every tick | 2 lines: `@a[scores={cobblers.left=1..}]`. All 9 flags are `trainer_defeat`, **0 are `trigger`**, so the 3-lines-per-trigger term is empty | **2 lines/tick** | CALIBRATED 2–8 us/tick |
| `cobblers_sizes` (`tools/size_outliers.py:45-53`, `data/sizes.json`) | no | self-rescheduling every **20** ticks | `@e[type=cobblemon:pokemon]` filtered by two NBT tests — a **global Pokemon scan**; already-rolled entities are excluded by the marker | 1 scan / 20 ticks | UNKNOWN (scan cost scales with loaded Pokemon, not with the town) |
| `cobblers_mines` (`tools/mines.py:692-701`, `data/mines.json`) | **yes** (driver) | 2 lines/tick; `drive` every **100** ticks tests 7 `@a[<approach box>]` | boxes 64 blocks round each site | 6 of the 7 sites are at settlements (tea_town, northlight, gorge_hamlet, mining_town, the_scar, viltri_light, displaced_city) | CALIBRATED ≈ **2.1 lines/tick ≈ 2–8 us** |
| `cobblers_rewards` | **no — advancement** | each find is an advancement reward | — | 0 | not a tick cost |
| Lanterns and street lighting (`tools/light_plan.py`) | **no** | — | — | blocks only; block light is baked at placement | **0 us/tick**. It is a chunk-lighting and client cost, not a server tick cost. |
| Signposts (`tools/signposts.py`) | **no** | `cobblers:signs/place`, one shot | — | sign block entities; vanilla signs have no ticker | **0 us/tick** |
| Traders (`tools/traders.py:242,288`) | **no** | one shot, three steps 40/100 ticks apart at re-apply | — | 1–7 `NoAI` clerks | entity tick UNKNOWN; **no loop** |
| `rctmod:trainer_spawner` block entity | **yes**, a block-entity ticker | rctmod's own interval | needs a nearby player and rctmod's spawn checks; no structure lookup (`docs/research/notes/hand-placed-structures.md:41`, VERIFIED against three source files) | **1 per gym** — present in the Brock gym placement record, `data/placements.json:4622` ("20 block entities including `rctmod:trainer_spawner`, 9 command blocks") | UNKNOWN |
| Command blocks inside gym templates | **no**, unless `enable-command-block=true` | — | 9 in the Brock gym | `enable-command-block` defaults false on 1.21.1 (`hand-placed-structures.md:38`, VERIFIED) | 0 us/tick as configured |
| Interaction entities (ambient boxes, scene props) | yes, trivially | every tick | — | 20 ambient boxes + 40 scene props (Routes) | EXTRAPOLATED: sub-microsecond each; they have no AI. But the ambient driver scans them **twice every tick** (row 1). |
| Item displays (carriers' loads) | yes, trivially | every tick | — | 6 | EXTRAPOLATED: negligible server-side |

**The server-wide datapack floor, with nobody in any town** (CALIBRATED, summing the always-on rows):
ambient 24 + ambient keeper 1.0 + blackout 17 + trainers 9.4 + scenes 0.7 + progression 2 + mines 2.1
= **56 command lines per tick = 56–224 us/tick = 0.11%–0.45% of budget.**

**Add one online player anywhere:** + water ladder ~39 + checkpoint sample 2.4 = **~41 lines/tick/player
= 41–166 us = 0.08%–0.33% per player.**

Two things in that floor deserve the owner's attention before trainers do:

1. **The water ladder is ~39 command lines per player per tick, everywhere, forever** — four times the whole trainer cycle, and it runs on dry land in the middle of a town. `water/tick` sets three scores and runs `water/qualify` (12 lines), `water/surfaced`, `water/strip_vanilla` (7 lines) before it ever discovers the player is not in water (`tools/blackout_pack.py:737-754`). An early `return` on "not in water and no modifier held" would cut most of it. That is a finding, not a request; it is not this document's job to change it. **Done 2026-09-29** — see "The water ladder on dry land" below: the dry path is now 7 lines.
2. **`cobblers_ambient`'s driver costs 24 lines/tick with the server empty**, because the 20 per-worker score tests and the two global interaction scans are unconditional (`tools/ambient.py:309-313,328`). It is the one place where adding workers raises the *idle* cost, at +1 line/tick per worker forever.

---

## 3. The arithmetic: what a populated town should cost

### 3.1 Definition of "fully populated"

The owner's own ceiling plus what he is about to add:

| point of interest | count | basis |
| --- | ---: | --- |
| carriers | 2 | `data/ambient.json:9` per_town |
| stationary workers | 4 | `data/ambient.json:9` per_town |
| `NoAI` trader clerks | 7 | gym1_town today, the busiest |
| AI villagers | 5 | the midpoint of the 4–6 proposal, `TOWNS_AND_VILLAGES.md:66-71`. **None exist.** |
| placed trainers | 4 | the owner's intent; nothing authored yet |
| `rctmod:trainer_spawner` | 1 | the gym template |
| habitat blocks | 0 | none in a settled town |
| scenes | 0 | none in a town |

### 3.2 Prediction A — one player standing in a fully populated town

| term | us/tick | label |
| --- | ---: | --- |
| 2 carriers x 25 | 50 | **CALIBRATED** from a MEASURED unit |
| 4 stationary x 3 | 12 | **CALIBRATED** from a MEASURED unit |
| server-wide datapack floor (56 lines) | 56–224 | CALIBRATED |
| water ladder + checkpoint, 1 player (41 lines) | 41–166 | CALIBRATED |
| 4 trainers' share of the cycle (1.6 lines) | 2–7 | CALIBRATED |
| location titles, 1 player | 1–10 | EXTRAPOLATED |
| Cobblemon spawn pass, 1 player | 20–100 | EXTRAPOLATED |
| **subtotal, known + bracketed** | **182–569** | |
| 7 `NoAI` clerks | 7–70 (1–10 each) | **EXTRAPOLATED** |
| 1 `rctmod:trainer_spawner` | 0–20 | **UNKNOWN** |
| wild Pokemon standing in the loaded chunks | 0–500 | **UNKNOWN**, bounded by `pokemonPerChunk` 0.25 |
| **4 `rctmod:trainer` mobs** | **80–600** (20–150 each) | **EXTRAPOLATED — the number to measure** |
| **5 AI villagers** | **250–1,000** (50–200 each) | **EXTRAPOLATED — the number to measure** |
| **TOTAL** | **520–2,760 us** | |

**= 1.0% to 5.5% of a 50 ms tick.**

Of that total, the two EXTRAPOLATED entity terms (trainers and AI villagers) are **330–1,600 us**:
between a third and a half of the whole prediction rests on brackets, not evidence. **That is why the
measurement is needed before the content is built**, and it is exactly the owner's question.

**The prediction to falsify:** a fully populated town with one player in it costs **under 1 ms per
tick (2%)** if trainers and villagers behave like ordinary pinned mobs, and **2–3 ms (4–6%)** if they
behave like full-AI mobs. Anything above 5 ms means something in the list is wrong by an order of
magnitude, and the differencing procedure in part 4 will say which.

### 3.3 Prediction B — two players in two different towns

Split the terms into **shared** (paid once by the server) and **per-player**:

- shared: the 56-line datapack floor = 56–224 us.
- per town, per occupied town: the workers (62 us), clerks, trainers, villagers, spawner.
- per player: water ladder + checkpoint (41 lines), titles, spawn pass.

Two players, two towns = 1x floor + 2x town + 2x player.

Predicted **1.7x–1.9x** Prediction A. Not 2x, because the floor is paid once.

### 3.4 Prediction C — two players in the *same* town

The town's entities are **shared**: one set of workers, one set of trainers, one set of villagers, all
ticking once. What doubles is only the per-player terms, plus the two places where our own datapacks do
work per nearby player:

- `trainers/cycle` line 2, `@a[distance=..9]` `runmolang` — one per player near each trainer, every 10 ticks.
- `scenes/cycle` beats — `@a[<box>]` per scene; zero in a town.
- the workers' step does **not** double: `#<id>_on` is a single flag, not per player (`tools/ambient.py:328,343`).

Predicted **1.15x–1.30x** Prediction A.

**This is the sharpest falsifiable claim in the document.** If C measures at ~2x A, then something that
should be shared is being paid per player, and it must be found before four friends stand in one town.
If C measures at ~1.2x A, co-op play in one town is structurally cheap and the owner can stop worrying
about it.

### 3.5 Prediction D — where the ceiling is

Take 5 ms (10% of budget) as the line where a town "starts costing real tick time" — beyond it, one
town's worth of content can visibly interact with a lag spike.

With the **measured** figures alone:

| point of interest | unit cost | count for 5 ms | count for 50 ms (100%) |
| --- | ---: | ---: | ---: |
| carrier worker | 25 us (**MEASURED**) | **200** | 2,000 |
| stationary worker | 3 us (**MEASURED**) | **1,666** | 16,666 |
| a command line in a per-tick function | 1–4 us (CALIBRATED) | 1,250–5,000 | 12,500–50,000 |

The workers are not the problem and never will be: the owner's cap of 2 + 4 uses **0.12%** of the
budget, and even 30 towns all populated and all occupied at once — impossible at `max-players=8` — would
be 1,860 us, 3.7%.

With the **unmeasured** figures, the ceiling is a formula, not a number. For a town of `n_t` trainers
costing `T` us each and `n_v` AI villagers costing `V` us each:

```
5 ms line:   n_t * T  +  n_v * V  =  4,400 us     (5,000 minus the ~600 us everything else costs)
```

| if T is | 4 trainers cost | trainers alone reach 5 ms at |
| ---: | ---: | ---: |
| 20 us | 80 us | 220 |
| 50 us | 200 us | 88 |
| 100 us | 400 us | 44 |
| 150 us | 600 us | 29 |

| if V is | 5 villagers cost | villagers alone reach 5 ms at |
| ---: | ---: | ---: |
| 50 us | 250 us | 88 |
| 100 us | 500 us | 44 |
| 200 us | 1,000 us | 22 |

**So the whole answer to "where is the ceiling" reduces to measuring `T` and `V`.** Measure those two
numbers and every town-population question in the campaign is answered by arithmetic. That is what part
4 is for.

**One caution the arithmetic cannot express:** mob cost in Minecraft is not linear in count. Villager
POI contention, path-finder budget sharing and `minimumDistanceBetweenEntities` checks make crowds
superlinear. The sweep in part 4 step 6 goes to 32 precisely to catch the knee.

---

## 4. The measurement plan for the main session

Everything below runs on **staging**, under the coordination lock, with the owner's go. It is written
as an ordered procedure. Steps marked **DESTRUCTIVE** change world state and carry their undo.

### 4.0 Before anything

1. Take the lock as CLAUDE.md requires; do a port/process check first.
2. `python tools/install_check.py --server-dir <server>` and clear every problem it lists.
3. Confirm no other player is connected: `/list`.
4. Note the build: `/tick query` once, and record the server's `simulation-distance` and `view-distance`
   from its live `server.properties` (the example ships 6 and 10).

### 4.1 Step 0 — establish the instrument (do this first; six predictions depend on it)

**The resolution problem.** `/tick query` reports "Average time per tick: `X`ms (Percentiles: P50 … P95 …
P99 …, sample: `N`)" — believed **one decimal place**, i.e. a 0.1 ms = 100 us quantum. If so, a 3 us
stationary worker is **two orders of magnitude below the print resolution** and cannot be read directly.

1. Run `/tick query`. **Look at the number of decimal places.** Record it.
2. If it is one decimal: every single-source measurement below must use the **multiply-and-divide**
   method — put `k` copies of the thing in, difference the medians, divide by `k`. Choose `k` so the
   expected difference exceeds 0.5 ms (for a 25 us worker, `k >= 20`).
3. If a higher-resolution path is wanted, cross-check with the profiler:
   `/debug start`, wait 60 s, `/debug stop`, then read the report the server writes under its own
   `debug/` folder (a server-dir read, allowed under the lock; **not** the world folder). It breaks the
   tick down by section and lists datapack function timings in nanoseconds. Use it to separate
   *datapack* cost from *entity* cost without killing anything.

**Calibrate the per-line constant (section 1b), because six predictions rest on it.** With one player
standing still in an empty area:

- `/tick query` x 20 over 100 s, median the P50s. That is the control `C0`.
- `/datapack disable "file/cobblers_blackout"` — removes 17 server lines + ~41 per-player lines.
- `/tick query` x 20, median: `C1`.
- `/datapack enable "file/cobblers_blackout"`.
- **per-line cost = `(C0 - C1) / 58` us.** Compare with the 1–4 us bracket.

`/datapack disable` is reversible and touches no world state. It does force a data reload (a one-off
hitch of a few seconds on this pack set — `data/spawn_suppression.json:11` measured +8.5 s reload with
`cobblers_suppress` installed). **Wait 30 s after each enable/disable before sampling.**

### 4.2 Sampling discipline (applies to every run below)

- **20 samples** of `/tick query` at 5 s intervals per condition; take the **median of the P50s**. P95
  and P99 are chunk loading and autosave, not the thing being measured.
- **Never sample within 60 s of** a chunk-load burst, a `/reload`, a `/datapack` toggle, an autosave, or
  a teleport. Stand still.
- **Every condition gets a paired control** taken in the same session, within a few minutes — the
  baseline drifts with what else is loaded.
- **The control is an empty area at the same distance from the player**: stand on open ground with the
  same biome, the same simulation-distance chunk count, no structures, no town, no route. Pick one and
  keep it for the whole exercise. Suggested: open ground at least 300 blocks from any
  `data/towns.json` footprint and any `data/route_trainers.json` seat, at a similar y.
- **Record, for every sample:** the condition, the P50, the sample count, the time, and `/list`.

### 4.3 Step 1 — the control, and the empty-town baseline

1. Stand at the control site. 20 samples → `BASE`.
2. Teleport into the target town's plaza (gym1_town plaza, `data/placements.json` `settlements.gym1_town.plan.plaza`). Wait 60 s for chunks to settle. 20 samples → `TOWN_NOW`.
3. `TOWN_NOW - BASE` = **the cost of the town exactly as it stands today**: 1 carrier + 1 stationary + 7 clerks + the gym's spawner + whatever wild Pokemon the pass has put there.

Prediction to beat: from section 3.2's town-local terms with today's counts, **35–190 us**, i.e. most
likely **below the print resolution of `/tick query`**. Expect `TOWN_NOW - BASE` to read 0.0 or 0.1 ms.
If it reads more than 0.5 ms, something in the inventory is missing and it must be found before going on.

### 4.4 Step 2 — isolate datapack cost from entity cost (one source at a time)

Standing in the town, with 20 samples between each toggle and 30 s settle:

| run | condition | isolates |
| --- | --- | --- |
| 1 | everything on | — |
| 2 | `/datapack disable "file/cobblers_ambient"` | the ambient driver **and** the workers' steps. The worker entities stay (they are `PersistenceRequired`), so this is **pure datapack** cost. |
| 3 | also `/datapack disable "file/cobblers_trainers"` | the trainer cycle (9.4 lines/tick server-wide) |
| 4 | also `/datapack disable "file/cobblers_blackout"` | the water ladder and the guardian scan |
| 5 | also `/datapack disable "file/cobblers_scenes"` | the scene cycle |
| 6 | re-enable all four, one at a time, resampling between | confirms each difference is reproducible and additive |

Then, for entity cost with the datapacks off:

7. **DESTRUCTIVE.** With `cobblers_ambient` still disabled,
   `kill @e[type=cobblemon:pokemon,tag=cobblers.amb.<id>]` for the town's workers, and
   `kill @e[type=minecraft:interaction,tag=cobblers.amb.i.<id>]` for their boxes. 20 samples.
   **Undo:** `/datapack enable "file/cobblers_ambient"`; the keeper rebuilds each worker, box and item
   display within 40 ticks of a player being within `keep_radius` 96 (`tools/ambient.py:338-343` the
   keeper, `:345` onward its `hold`). Verify with `python tools/ambient.py verify --rcon --server-dir <server>` — it must report
   20 of 20.
8. Difference run 7 against run 2: **that is the ambient workers' entity cost with no datapack loop at
   all**, which the 25/3 us figures do not separate out.

Answer expected: the 25 us is mostly the step function (tp macro + storage lookup + particles), and the
entity itself is near zero because it is `NoAI`. If the entity cost is large, the design assumption
"NoAI is free" is wrong and the per-town cap needs revisiting.

### 4.5 Step 3 — the trader clerks (`V_noai`)

gym1_town has 7 and gym2_town has 6; every other town has 1 or 2. Use the two busiest.

1. In gym1_town: 20 samples with the 7 clerks standing.
2. **DESTRUCTIVE.** `kill @e[type=minecraft:villager,x=…,y=…,z=…,distance=..64]` — scoped by position,
   not by tag, because clerks carry the `cobblers.*` trader tags from `tools/traders.py` and there is
   nothing else in a town to hit. 20 samples.
3. Difference / 7 = **`V_noai`**, the cost of one `NoAI` clerk.
   **Undo:** `/function cobblers:towns/vendors_gym1_town`, then wait ~8 s
   (`tools/traders.py:16-17`); verify with
   `python tools/traders.py verify --rcon <server dir>`.
4. If the difference is under the print resolution, repeat by **summoning** 20 extra clerks at a marker
   spot instead (`summon minecraft:villager … {NoAI:1b,PersistenceRequired:1b}`), difference, divide by
   20, then `kill` the extras by a unique tag. This never touches the authored clerks and is the safer
   route; prefer it.

### 4.6 Step 4 — the AI villager (`V`) — the number the proposal depends on

None exist, so this is a pure summon-and-measure, and nothing authored is touched.

1. Clear a spot in the town. `BASE_T` = 20 samples.
2. Summon 1 villager with AI and no job site:
   `summon minecraft:villager <x> <y> <z> {PersistenceRequired:1b,Tags:["cobblers_probe"]}`. Wait 60 s
   (the brain has to settle). 20 samples.
3. Repeat at 2, 4, 8, 16, 32 (summon the difference each time). 20 samples at each count.
4. `kill @e[tag=cobblers_probe]`.
5. Plot cost against count. `V` = the slope. **Look for the knee**: the point where the line bends
   upward is the real cap, and it will be below any per-villager arithmetic.
6. **Repeat the whole sweep with job sites and beds present**, because an unemployed villager with no
   POI in range does far less work than one running a schedule between a bed, a composter and a bell.
   Place 4 beds, 4 job-site blocks and a bell, and re-run at 4, 8, 16. **This second sweep is the one
   that answers the proposal**, and the first is only its floor.
7. `kill @e[tag=cobblers_probe]`, then remove the probe beds/job sites/bell by `setblock … air` at the
   recorded coordinates.

Warning to record with the result: with beds and a village centre present, `spawnTrainerAssociation`
(`rctmod-server.toml:93`) will spawn an association NPC near the player. Check `/data get entity @e[…]`
or just count entities before attributing the cost.

### 4.7 Step 5 — the trainer (`T`) — the number the owner is about to spend

1. `BASE_T` = 20 samples in the town, nothing added.
2. `rctmod trainer summon_persistent <id> <x> <y> <z>` for one trainer, at the town plaza. Use a Route 3
   id temporarily, or a throwaway id, so nothing authored moves. Wait 60 s. 20 samples.
3. Repeat at 2, 4, 8, 16, 32 trainers, spread across the plaza at least 8 blocks apart
   (`minimumDistanceBetweenEntities` is 8 for spawns, and crowding changes the answer). 20 samples each.
4. `kill @e[type=rctmod:trainer,x=<plaza>,distance=..64]`, then confirm the Route 3 seats still hold
   their trainers if a real id was reused — safer to use a throwaway id and avoid the question.
5. `T` = the slope. **Look for the knee.**
6. **Then repeat the sweep with the player *facing* the trainers and within 16 blocks**, because
   `forceBattleOnSight = true` and `forceBattleMaxDistance = 16.0` (`rctmod-server.toml:117,122`) mean
   the sight scan only runs when a player is in range and looking. The difference between
   "facing, within 16" and "back turned, 30 blocks away" **is the on-sight scanning cost**, and it is
   the term section 2.2(a) could not resolve offline.
7. **Also resolve the config question offline-unanswerable in step 6's shadow:** whether a trainer whose
   mob JSON omits `forceBattleOnSight` inherits the global `true`. Stand in front of `route_01_trainer_02`
   (which omits the key, `data/route_trainers.json`) for 60 s without moving. If it forces a battle, it
   inherits. Record either way — it changes whether every town trainer scans every tick.

### 4.8 Step 6 — the four scenarios

**Scenario 1 — a fully populated town, one player.** Build up to the section 3.1 definition inside the
town, one source at a time, sampling at each addition, so the total is decomposed as it is assembled:

| add | running prediction (us) |
| --- | ---: |
| (town as it stands) | 35–190 |
| + 1 carrier, + 3 stationary (to the 2 + 4 cap) | +34 |
| + 4 trainers | +80–600 |
| + 5 AI villagers with beds and job sites | +250–1,000 |

Final reading against **520–2,760 us (1.0%–5.5%)**. Report the percentage, not just the ms.

Undo, in order: kill the probe villagers and trainers by tag; remove the probe beds and job sites;
re-place the cap workers with `reapply.py` R16C or leave them (the extra carrier/stationary would need
`data/ambient.json` records, so for the measurement use **throwaway summons**, not authored workers —
summon `NoAI` Pokemon with the same flags and tp them on a loop only if the entity term is wanted; do
not author new workers just to measure).

**Scenario 2 — two players in different towns. BLOCKED on a second account.**
The owner does not have one. Mark this step blocked and do not fake it.

> **A single player teleporting between two towns does not measure this.** Teleporting measures each
> town's cost *serially*, one at a time, while the other town's chunks unload and its entities stop
> ticking (`simulation-distance=6`). The whole question in the two-player case is **concurrency**: two
> sets of chunks loaded, two sets of entities ticking, two water-ladder passes, two spawn passes, in the
> *same* tick. Teleporting gives `max(A, B)`; the real answer is `floor + A_local + B_local + 2 x
> per-player`. A teleport test cannot distinguish them and must not be reported as if it could.

What *can* be done meanwhile, and is honest: measure each town alone, and **predict** the two-player
figure with section 3.3's decomposition (1.7x–1.9x A). Then falsify it the day a second account exists.

**Scenario 3 — two players in the same town. BLOCKED on a second account.**
Same reasoning. This is the scenario with the sharpest prediction (1.15x–1.30x, section 3.4) and it is
the one co-op play depends on. It is worth acquiring a second account for; a throwaway Microsoft account
on the same LAN is enough, and `online-mode` does not need changing if the account is legitimate.

**Scenario 4 — the practical cap per point of interest.** Already produced by the sweeps: steps 4.6 and
4.7 give `V`, `T` and the knee in each. Fill in section 3.5's table with the measured slopes and the
answer to "where is the ceiling" is arithmetic from then on.

### 4.9 What to write down

For each of the four scenarios and each sweep point: the condition, the paired control, the median P50,
the difference, the difference as a percentage of 50 ms, and the label (**MEASURED** for everything in
this part). Then:

1. Replace the EXTRAPOLATED rows of section 3.2 with the measured ones and re-total.
2. Record `V`, `V_noai`, `T` and the per-line constant in `docs/STATE.md` next to the 25/3 us line, so
   the next session does not re-derive them.
3. If the per-line constant lands near 4 us rather than 1, say so loudly: the 56-line idle floor and the
   39-line-per-player water ladder both quadruple, and they, not the trainers, become the thing to fix.

---

## 5. Summary for the owner

**What is measured:** a carrier costs 25 us, a stationary worker 3 us, both only within 48 blocks of a
player. The spawn-suppression pack costs no ticks at all. That is the entire measured basis.

**What the repository says a town holds today:** 1–2 ambient workers, 1–7 `NoAI` trader clerks, zero AI
villagers, zero trainers, zero habitat blocks, zero scenes, and one `rctmod:trainer_spawner` in the gym.
A town as it stands is very probably too cheap for `/tick query` to resolve at all.

**What is safe to say now:** the ambient workers are not the cost. The owner's cap of 2 carriers and 4
stationary is **0.12% of a tick**, and even 2,000 carriers would fit in a tick. The cap is a
looks-and-client-draw decision, exactly as `data/ambient.json:9` says, and the tick does not argue with it.

**What is not known and must not be guessed:** what one `rctmod:trainer` costs, and what one AI villager
with a bed and a job site costs. Between them they are a third to a half of the predicted budget for a
populated town. Both are cheap to measure — a summon, a sweep, a kill — and neither needs a second
account.

**What cannot be answered without a second account:** both two-player scenarios. A single player
teleporting between towns measures them one at a time and misses the whole point, which is concurrency.
The prediction stands on the record to be falsified later: two players in different towns ≈ 1.8x one
player in one town; two players in the **same** town ≈ 1.2x, because a town's entities are shared and
only the per-player loops double.

**The one thing found on the way that is worth a look regardless of trainers:** the water ladder runs
about 39 command lines per player per tick, on dry land, in the middle of a town, forever
(`tools/blackout_pack.py:733-754`). It is four times the whole trainer cycle and it is the largest
per-player datapack cost in the game today.

---

*Written offline from the repository at `1572fb0`. No command in this document was run. Nothing here
touched the running server, RCON, the coordination lock or any world.*

---

## The water ladder on dry land, traced line by line (2026-09-29)

The offline inventory flagged this as the largest per-player datapack cost in the game. Traced through the generated
functions, for a player **standing on grass in the middle of a town**:

| function | lines run before | lines run after (2026-09-29) | why it runs on dry land |
|---|---:|---:|---|
| `water/tick` | 17 | **5** | the driver; before, its water tests failed but the lines were still evaluated. Now it returns at line 5 |
| `water/qualify` | 10 | **0** | was **called unconditionally**, line 10 of `water/tick`; now on the wet path only |
| `water/surfaced` | 3 | **0** | was called *because* `bo.sub == 0`; its two resets moved into `water/left`, its Surf decay into `water/dry` |
| `water/strip_vanilla` | 5 | **0** | was **called unconditionally**, the last line of `water/tick`; now the wet path plus an advancement trigger |
| `water/dry` (new) | — | **2** | the whole dry path: settle-once on leaving the water, and the Surf bonus's decay clock |
| **total** | **35** | **7** | plus the tick-tag and driver overhead the inventory counted, giving its ~39 before |

Counted from the generated functions (`build/datapacks/cobblers_blackout/data/cobblers/function/water/`), non-comment
lines, for a player standing on grass with no Surf bonus left, no swim modifier and no air modifier. Two paths cost
more than 7 and both are bounded: the single tick a player leaves the water runs `water/left` (5 more), and while a
Surf bonus is decaying `water/breathe` runs (5 more) until `breath_reset_ticks` of full air have passed.

**Where the waste actually is** (`tools/blackout_pack.py`, generated into `cobblers_blackout`):

1. **`water/qualify` runs every tick for every player whether or not any water is involved.** It computes the Surf and
   Dive qualification from the party and the training tags. On dry land its only consumer is the swim-speed test at
   `water/tick:13-14`, and both of those are themselves gated on being in water. Its grace counter is a debounce
   against qualification flapping, and a player who walks out of water keeps their last `bo.qual` until they re-enter,
   so skipping it while dry costs nothing observable. Its one message (`water/qualify:8`) is gated on `bo.deep`, which
   is 0 on land.
2. **`water/strip_vanilla` issues two `effect clear` commands per player per tick, forever** (`:3-4`, via
   `execute store success`). It clears Water Breathing and Conduit Power unconditionally, so it pays the cost of both
   clears on every tick of every player who has never held either effect. An `effect clear` is very unlikely to cost
   the same as a scoreboard line, so this term is probably worth more than its line count suggests. **Unmeasured.**
3. `water/surfaced` is 3 lines and is the one part that legitimately belongs on the dry path.

**What it cost, and what it costs now.** The early exit sits after the eye test: no water at the eyes and none at the
feet, return into `water/dry`. `surface/tick`'s own guard is the same pair of block tests at the same position in the
same tick, so the two agree on which ticks are dry, and nothing downstream ever reads a `bo.qual` the exit skipped.

| | lines/player/tick | at 1.0-3.8 us a line (CALIBRATED, and the per-line constant is step 0 of the plan) |
|---|---|---|
| before, dry | 35 | 35-133 us |
| after, dry (idle) | **7** | 7-27 us |
| saved | **28** | **28-106 us per player per tick** |

At `max-players` 8 that is up to about **0.85 ms a tick, roughly 1.7% of the budget**, paid constantly by players doing
nothing near water. The two `effect clear` commands are gone from the dry path entirely, and they are the one term
likely to cost more than a scoreboard line, so the real saving is probably larger. **All of this is CALIBRATED from
the 1.0-3.8 us line constant; none of it has been measured on a server.** The measurement in section 4 should include
a before/after of this path.

**What the exit had to preserve**, because `cobblers_blackout` owns contracts C1 and C2
(`data/system_contracts.json`) and a swim-rule change broke the Dive ladder once before (2026-09-27, players knocked
out after 33 s):

- `bo.surf`'s initialiser stays the first line of `water/tick`, before the exit (C2's finding).
- The Surf bonus's decay still runs while dry (`water/dry` calls `water/breathe` whenever `bo.surf >= 1`).
- `bo.pulse` and `bo.warn` only ever change under water, so `water/left` resets them once on leaving instead of every
  dry tick. The swim-speed modifier and the ladder's `oxygen_bonus` modifier come off there too, and `blackout/login`
  sets `bo.wet` so a player who logged out swimming is settled on their first dry tick.
- Water Breathing and Conduit Power are still removed, and the player still told once via `cobblers.air_told`: the
  wet path clears unconditionally every tick as before, and off the water a `minecraft:effects_changed` advancement
  (`cobblers:blackout/vanilla_air`) clears them the tick they land. **Not verified in game** — the trigger's firing
  is EXP-042 work.

`tests/test_system_contracts.py` (82) and the blackout, surface, boat, gate-clock, open-water, water-mount and
recovery suites (255) are green after the change; none of them asserted the dry-path line count before, and a
test-author still owes one.
