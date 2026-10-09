# EXP-084: the dungeon engine core runs the Night Shift's placeholder spine end to end

**Status: RCON PART PASSED 2026-10-09 (16 of 16 readable steps; owner part OPEN).** Written 2026-10-08 with the build (`tools/dungeon.py`, `data/dungeons.json`, pack
`cobblers_dungeons`). Nothing below has run on a server. The builder does not grade it.

## Objective

Prove on staging that the engine core does what DUNGEONS.md sections 1, 2, 3.2, 3.4, 5, 6, 7 and 11.3 ask: the
per-player clock and its bar, the return margin, sudden death, the logout rule, the greed ladder's counter, the slots'
shells and reset, the staged boss's chain, the recall sweep, E1's engine half, entry and exit, the sigils and the rip.
The spine is a PLACEHOLDER (`data/dungeons.json` `spine.placeholder`), so the clock's length and V3 are not tested.

## Implementation

- `tools/dungeon.py` generates `build/datapacks/cobblers_dungeons` (world-local) from `data/dungeons.json`.
- `tools/reapply.py` R16DG places the four slot shells (`cobblers:dungeons/place`; 28,145 blocks written per slot,
  `python tools/dungeon.py --report`) and their 12 entities through a look-then-act chain
  (`cobblers:dungeons/shells/entities`, `tools/chunk_look.py` with its new `dim` argument). R16DR places the Night
  Shift's placeholder rip in the old mine's notch (`cobblers:dungeons/rips/place`) and its interaction
  (`cobblers:dungeons/rips/entities`).
- `data/world_probes.json` `dungeon_night_shift`: 33 presence probes (28 in `cobblers:pocket`, read through the new
  `dim` key of `tools/presence_audit.py` extra).
- Slot k of the Night Shift: strip z `1024 + (k-1)*128 .. +63`, spine along x 0..123 at the strip's centre line
  (`cz` = 1056, 1184, 1312, 1440). Slot 4: box x 0..123, y 95..106, z 1427..1453; arrival (3.5, 96, 1440.5); the
  no-deploy box x 64..79, y 95..101, z 1437..1443; the boss spot (100, 96, 1440); the gate x 111..112, z 1439..1441.

## Test instructions

Staging only, with the lock held, after `prepare` and `install` of this branch and a plain restart (NPC classes and the
callback load only at a boot). Read every verdict from the world.

### (a) RCON, no player

| # | Command(s) | PASS | FAIL |
|---|---|---|---|
| 1 | grep the boot log for `cobblers:dungeons/` and `dg_ns_boss` | no `Failed to load` | any function, recipe, advancement or NPC class failed |
| 2 | `scoreboard players get #up dg.up`; again 10 s later | rises by about 200 (20 a pass) | unchanged: the keeper is not scheduled |
| 3 | `function cobblers:dungeons/place`; `tick query` before and after | returns; record the stall | an error, or a stall above I2's 2.64 s |
| 4 | for slot 1 and slot 4: `execute in cobblers:pocket if block 3 95 1056 minecraft:deepslate_tiles`, `... if block 3 96 1056 minecraft:air`, `... if block 0 97 1056 minecraft:black_concrete`, `... if block 111 97 1056 minecraft:iron_bars`, `... if block 123 97 1056 minecraft:black_concrete` (z 1440 for slot 4; force-load first: `execute in cobblers:pocket run forceload add 0 1040 127 1071`) | all pass | any fails |
| 5 | `function cobblers:dungeons/shells/entities`; 21 s later `scoreboard players get #dg_shells cobblers_chunk_look` | `12` | `-1` (chain not done) or another count |
| 6 | `function cobblers:dungeons/rips/place`; `function cobblers:dungeons/rips/entities`; 21 s later `scoreboard players get #dg_rips cobblers_chunk_look`; `execute if block 1350 130 4117 minecraft:crying_obsidian`; `execute if block 1352 131 4117 minecraft:black_concrete`; `execute if block 1352 130 4118 minecraft:air` | `1`; three passes | otherwise |
| 7 | `python tools/presence_audit.py --only extra` (the `dungeon_night_shift` place) | 33 / 33 | any failure, named |
| 8 | the greed ladder on a marker: `forceload add 0 0`; `summon minecraft:marker 0.5 70 0.5 {Tags:["dgt"]}`; for n in 0, 4, 5, 9, 10, 15, 20, 25: `execute as @e[type=minecraft:marker,tag=dgt] run function cobblers:dungeons/greed/test_set {n:<n>}` then `scoreboard players get @e[type=minecraft:marker,tag=dgt,limit=1] dg.rate` | 4, 4, 5, 5, 6, 8, 12, 12 | any other |
| 9 | the charge: `scoreboard players set @e[tag=dgt] dg.rate 5`; `scoreboard players set @e[tag=dgt] dg.clock 10000`; `execute as @e[tag=dgt] run function cobblers:dungeons/m/charge`; get `dg.clock` | `9900` | otherwise |
| 10 | the absence gap: `scoreboard players set @e[tag=dgt] dg.st 3`; `scoreboard players set @e[tag=dgt] dg.clock 10000`; `scoreboard players operation @e[tag=dgt] dg.seen = #up dg.up`; `scoreboard players remove @e[tag=dgt] dg.seen 220`; `execute as @e[tag=dgt] run function cobblers:dungeons/m/gap`; get `#gap dg.t` and the marker's `dg.clock` | clock = 10000 - 5 x #gap, #gap 200 or 220 (a pass may fall between the RCON calls) | otherwise |
| 11 | the digits: `scoreboard players set @e[tag=dgt] dg.rate 4`; `... dg.clock 139200`; `execute as @e[tag=dgt] run function cobblers:dungeons/m/digits`; get `dg.mm dg.s10 dg.s1 dg.lm dg.l10 dg.l1`; then rate 12 and again | 29 0 0 29 0 0; at rate 12: 29 0 0 9 4 0 | otherwise |
| 12 | a fake held slot 4: `scoreboard players set #s4 dg.own 99`; `scoreboard players set #s4 dg.run 99999`; `scoreboard players operation #s4 dg.dead = #up dg.up`; `scoreboard players add #s4 dg.dead 2000`; force-load slot 4 (`execute in cobblers:pocket run forceload add 0 1424 127 1455`); `execute in cobblers:pocket run function cobblers:dungeons/npc_at {x:"95.5",y:"96",z:"1440.5",cls:"cobblers:dg_ns_boss_b1_s1",level:"18"}`; 3 s later `execute in cobblers:pocket run data get entity @e[type=cobblemon:npc,x=95.5,y=96,z=1440.5,distance=..2,limit=1] Tags` | the NPC stands (C1's macro spawn) and its Tags hold `dg.npc`, `dg.s4` and `cobblers.gm` (the bind backstop, a pass after the spawn) | no NPC, or untagged |
| 13 | stale NPCs: `scoreboard players set #s4 dg.run 99998`; 3 s later count `@e[type=cobblemon:npc,tag=dg.s4]` | `0` (another run's NPC is killed) | `1` |
| 14 | the recall sweep on a WILD Pokemon (P1's proven half): `execute in cobblers:pocket run spawnpokemonat 70.5 96 1440.5 magikarp level=5`; 3 s later `execute in cobblers:pocket if entity @e[type=cobblemon:pokemon,x=64,y=95,z=1437,dx=15,dy=6,dz=6]` | `Test failed` (discarded) | it stands |
| 15 | the deadline: `scoreboard players operation #s4 dg.dead = #up dg.up`; `scoreboard players add #s4 dg.dead 60`; get `#s4 dg.own` at once and 6 s later | 99, then 0 (freed: no member is present) | still 99 |
| 16 | cleanup: `kill @e[tag=dgt]`; `forceload remove 0 0`; `execute in cobblers:pocket run forceload remove 0 1424 127 1455`; `execute in cobblers:pocket run forceload remove 0 1040 127 1071` | | |

### (b) The owner, in game (one account; co-op waits on XD8)

Before: `scoreboard players reset <you> dg.lk_ns` between runs that need no lockout. Each step: what you do, what you see.

| # | You do | PASS |
|---|---|---|
| 1 | open the recipe book at cap 20 (wait 10 s after joining) | the Soot Sigil is in it, the five others are not (band mode, Q23 OPEN staging value); craft one. **SG1's owner half** |
| 2 | at the notch (1352, 130, 4120): click the rip with no sigil; then wearing an elytra | "The rift wants a sigil of your band: the Soot Sigil (or stronger)."; "The rift will not take wings." Nothing taken |
| 3 | click with the sigil | the enter line; the sigil gone; 2-3 s later you stand in the entry room in adventure mode with the Rift Pick; the board is readable on the north wall |
| 4 | walk back west and click the back rip | out at the notch, survival, pick gone, the Soot Sigil back in your inventory (**the crafted one must be matched: the byte form**); clicking the rip again is not refused for the lockout |
| 5 | enter again; walk east through the doorway | the bar "Rift 29:00 · x1", white, falling one second a second |
| 6 | `execute as @s run function cobblers:dungeons/greed/test_set {n:5}`; then `{n:20}` | "The rift tightens. Time runs x1.25." with a sound; the bar reads x1.25, "~mm:ss left", "taken 5", yellow; at 20: x3, red, the clock falls 3 s a second |
| 7 | at the arena's mouth: `function cobblers:dungeons/test/clock {s:120}` | the bar turns purple; "The way back is closing" once |
| 8 | walk into the arena (reset `{s:1500}` first) | stage 1 appears and the battle starts about a second later. Win it: "He gets up again." with "II of III", stage 2 three to four seconds later; then III; after the third win "The way out is open." and the bars are gone. **C1's owner half** |
| 9 | walk out by the far rip | out at the notch facing east, survival, pick gone, bar gone; 6-7 s later `tag @s list` no longer shows `cobblers.dg_run` |
| 10 | click the rip again | refused: "... Try again in about 60 minutes." |
| 11 | new run (reset the lockout); past the board `function cobblers:dungeons/test/clock {s:12}` | titles each second; at 0 "The rift closes." and you die; you wake at your checkpoint: "The rift closed / You were still inside.", the five lines, every item kept, $600 (or your balance) gone, and NO claim line (**DX1**) |
| 12 | new run; start a boss stage, then `test/clock {s:3}` mid-battle | no death while the battle lasts; dead the second it ends (sudden death, **B3's owner half**) |
| 13 | new run; past the board log out for 30 s and back | "The rift did not wait."; the bar about 30 s lower |
| 14 | `test/clock {s:20}`, log out for 60 s and back | killed on arrival: "The rift closed while you were away." then "The rift closed without you" (**LO1**) |
| 15 | new run; in the cracked-lamp box send out a Pokemon | it is recalled within a second, its HP as it was, "The rift will not hold them here." (**P1's owner half**) |

## Results

### RCON, no player (2026-10-09 02:13-02:25, main session)

staging-2026-10-01 (restored from `snapshot-2026-10-09-before-arenas` after the OOM below), prepare 203/203 at
0b3a8b2, installed, then `reapply.py run --only R16GA,R16DG,R16DR --no-reload` after a boot with the tick watchdog off
(0 problems, PARTIAL by design: 3 of 98 steps). Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1,
rctmod 0.19.0-beta / rctapi 0.16.1-beta, Mega Showdown 1.0.2, the server's full mod set, Java 21, -Xmx16G. No player
online. The run built the shells and the rip; steps 3, 5 and 6's PLACEMENT were therefore the apply's, and their
READINGS below are from the world.

| Step | Reading |
|---|---|
| 1 | boot log: no `Failed to load` naming `cobblers:dungeons/` or `dg_ns_boss` (the only failure is the probe pack's known `cobblers_dg_probes:c1/spawn_plain`) |
| 2 | `#up dg.up` 6560, then 6760 ten seconds later: **+200, the keeper runs** |
| 3 | the placement ran inside R16DG (22 s for the step, its waits included); the single-call stall was not timed separately |
| 4 | slots 1 and 4: deepslate floor, air over it, the entry wall, the iron bars, the far wall: **10 of 10 pass**. The wall block is `minecraft:black_terracotta` (2026-10-09: concrete is a spawn-condition block contract C4 refuses; the README's `black_concrete` in this step and in 6 reads terracotta now) |
| 5 | `#dg_shells cobblers_chunk_look` = **12** |
| 6 | `#dg_rips` = **1**; the rip at (1350, 130, 4117) crying obsidian, (1352, 131, 4117) black terracotta, (1352, 130, 4118) air: **3 of 3** |
| 7 | `presence_audit --only extra`: every `dungeon_night_shift` probe present, after the nine probe lines that still named `black_concrete` were corrected to terracotta (the world was read as terracotta in steps 4 and 6). Whole extra set: **386 of 393**, the 7 absent the known stale ones (Copperway Khan x2, Orchard Sleeper x2, two residents' air, the relic platform's gravel) |
| 8 | greed `test_set` n = 0, 4, 5, 9, 10, 15, 20, 25 -> `dg.rate` **4, 4, 5, 5, 6, 8, 12, 12: PASS**. (A first batch read nothing: the marker was summoned in the same RCON burst as `forceload add 0 0` and did not exist yet, the N155 shape; re-run once it stood) |
| 9 | the charge at rate 5 from 10000: **9900: PASS** |
| 10 | the absence gap: `#gap` 200, clock 9000 = 10000 - 5 x 200: **PASS** |
| 11 | digits at rate 4, clock 139200: 29 0 0 / 29 0 0; at rate 12: 29 0 0 / 9 4 0: **PASS** |
| 12 | `npc_at` macro, class `cobblers:dg_ns_boss_b1_s1`, level 18: **"The Night Foreman"** stands with Tags `dg.npc`, `cobblers.gm`, `dg.s4`: **PASS** (C1's macro spawn, and the bind backstop a pass later) |
| 13 | `#s4 dg.run` changed: the NPC tagged `dg.s4` gone 3 s later: **PASS** |
| 14 | the recall sweep on a WILD Magikarp, with controls: inside the no-deploy box it read present at once (`count: 1`) and **gone 3 s later**; a second one outside the box (30.5, 96, 1440.5) still stood 3 s later: **PASS** (P1's proven half; an OWNED Pokemon is the owner's) |
| 15 | the deadline: `#s4 dg.own` 99, then **0** six seconds later with no member present: **PASS** |
| 16 | cleanup done; the stray Magikarp killed; slot 4's fake ownership reset to 0 |

**The OOM (before these readings, recorded because it cost a restore).** At 02:00 the main session ran
`datapack enable "file/cobblers_gym_arenas"` over RCON on a pack it had copied into the world after the boot had
discovered packs. An enable is a full data reload; at -Xmx16G it ran out of heap (Distant Horizons threads first) and the
server was killed. The world was set aside as `cobblers-staging/staging-2026-10-01.oom-2026-10-09`,
`snapshot-2026-10-09-before-arenas` restored, the install re-run (clean) and the arena pack copied BEFORE the next boot.
Review N111's "a 12G server cannot /reload this build" holds at 16G too: never enable a pack by command on staging.


## Limitations

- The spine, the boss's teams and the rip are placeholders (data/dungeons.json); the clocks are DUNGEONS.md 4.2's
  planning values (XT1 timed no fight).
- Not built (step 6): the stands and their clawback, the seam (its call is `cobblers:dungeons/greed/take`), the
  parkour's catch bands, the lake and the den. A won boss stage pays CobbleDollars' NPC payout today.
- Gated on owner halves not yet run: C1 (the victory chain), P1 (an owned Pokemon's discard), SG1 (`recipe give`
  under doLimitedCrafting; the crafted sigil's byte form), B3 (sudden death in a battle), LO1 (a battle at logout),
  V1 (the rip seen from its approach), F1 (not used: no catch band yet).
- One account: co-op (members_max 1) waits on XD8.

## Decision

Pending the run.
