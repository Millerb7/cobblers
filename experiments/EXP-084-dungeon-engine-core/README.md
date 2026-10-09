# EXP-084: the dungeon engine core runs the Night Shift's placeholder spine end to end

**Status: NOT_EXECUTED.** Written 2026-10-08 with the build (`tools/dungeon.py`, `data/dungeons.json`, pack
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

NOT_EXECUTED.

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
