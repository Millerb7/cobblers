# EXP-046: Can a town hold a working Pokemon through restarts, unloads and players, doing visible work?

**Status:** run headless on staging (`cobblers-dryrun11`, 2026-09-28). The walk as a player sees it, a click, and a
sword are the owner's in-game look.

## Objective

The owner, 2026-09-28: every town gets Pokemon doing the town's work where a player can watch it, some to click;
they must survive restart, chunk unload and re-export, and must not wander off or be killed. Prove the mechanism on
one worker before generating a set (principle 15).

## Set-up

Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, the staging pack stack. A proof pack in the staging
world's folder (removed after): a Timburr at Brock's mason yard carrying a block of stone bricks (an `item_display`
riding along by `tp`) from the cut-stone pile to the wall in progress, 32 blocks, and back. Then the generated pack
`cobblers_ambient` (`tools/ambient.py`, `data/ambient.json`): 13 workers in 7 towns.

## Results

| # | Question | Result |
|---|---|---|
| 1 | Does `spawnpokemonat ... uncatchable no_ai` spawn from a function? | **Only after a `/reload`.** At a fresh boot the same function line spawned nothing (twice: the proof pack and the generated pack); after one `/reload` the same function spawned every time, in four forms (integer or decimal coordinates, with or without the flags, under `execute positioned`). A **macro** line (`$spawnpokemonat $(x) ...`) spawned at a fresh boot with no reload. This reconciles `tools/sapling_celebi.py` ("does nothing from a function", 2026-09-25) with EXP-042 ("works", 2026-09-26): EXP-042's runs followed the driver's `/reload`. The blackout rebuild is already a macro; the gulch Megas' keeper (`tools/gulch_mine.py megas/spawn_*`) is not |
| 2 | Does an unclaimed one stay? | **No.** A Pokemon spawned over RCON without `PersistenceRequired` was gone within a minute with no player near (the despawner); four test spawns likewise. The generated spawn claims it in the same function |
| 3 | Can it be hurt? | `Invulnerable:1b` refused every damage type `/damage` offers: generic, player_attack, mob_attack (with an attacker), arrow, in_fire (health unchanged). A player's sword is NOT tested (the Celebi died to one, EXP-023); the interaction box on each worker takes a hit in the Pokemon's place, and Resistance V and Regeneration are on it too |
| 4 | Do effects persist? | **No, not through a restart** (measured); the keeper gives them again every pass |
| 5 | Does it move smoothly by `tp` without AI? | Headless: positions advance 0.18 blocks a tick along the route, facing along each leg (yaw 55.4 out, -124.6 back on Brock's route, both correct for the route's direction), the carried block shown from pickup to 4 ticks after arrival, the interaction box on it throughout. **Whether Cobblemon plays its walk animation for a `tp`-moved NoAI Pokemon is not seen** |
| 6 | Chunk unload and restart | The worker, its display, tags, flags, position and the loop's clock survived a full stop and boot; all 13 generated workers were present with their flags after a restart (verify: 0 problems) |
| 7 | The generated set | 13 workers built and placed on staging, `tools/ambient.py verify --rcon`: one of each, `PersistenceRequired`, `Invulnerable`, `Unbattleable`, `NoAI` and a box each, 0 problems; a worker killed at a fresh boot was put back by its keeper through the macro |

## Cost (measured 2026-09-28, staging, the server's own `/tick query`)

A benchmark pack ran 40 worker steps every tick; readings alternated with idle, medians of 5-10 each: idle 5.70 ms,
+40 carrier steps 6.70 ms, +40 station steps 5.80 ms. So a carrier costs about 25 us a tick and a station worker
about 3 us (inside the noise), only while a player is within 48 of it; with nobody near a worker costs one keeper
check every 2 s. The first figure given (0.41 ms a carrier) was timed over RCON and was round-trip noise: the same
method gave negative costs on a rerun. The carrier's step reads its route from storage by one macro lookup a tick;
the first build tested every point of the route every tick (about 1,200 score tests for Brock's).

## The owner's flight (2026-09-28)

Both of Brock's workers work in game and the Timburr showed its block. Changed after it: Brock's carrier is a Graveler
(the owner); Northlight's Timburr stood inside the export's snow (the heightmap's ground is stone at y116, the paint
lays snow at y117 deep enough to hide it), so a worker can `clear` blocks from its cells (`tread`, run by R16C before
the station is held) and Northlight's route is 25 blocks from a woodpile moved north. Sabrina's Abra seen and liked.

## Not verified (the owner's flight)

- The walk animation of a `tp`-moved worker; the carried block's look over each species.
- A click on a worker (the line, the hearts).
- A sword on a worker: the box should take it.
- Two players at once; a worker's sounds and particles at the right distance.

## Decision

Build the set with the macro spawn, the claim in the same function, a keeper that re-asserts flags and effects, and
a box on every worker (`tools/ambient.py`). Fix the gulch Megas' keeper to spawn through a macro.
