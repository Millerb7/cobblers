# EXP-069: P1, does `q.pokemon.discard` recall an own sent-out Pokemon with its HP kept?

**Status: designed 2026-10-08, NOT_EXECUTED.** Probe P1 of `docs/mechanics/DUNGEONS.md` section 14, in the staging-only
pack `cobblers_dg_probes` (`tools/dungeon_probes.py`, `data/dungeon_probes.json`). Never the live world.

## Objective
The parkour's no-deploy leg (DUNGEONS.md 3.4) removes every Pokemon a player sends out inside the parkour box, with
`runmolang "q.pokemon.discard;"`, from a keeper sweep and from the `pokemon_sent_post` callback. DM 4.2 VERIFIED that
removing an owned `PokemonEntity` returns it to the party with its HP kept; the query name `q.pokemon` and the
zero-argument `discard` were ASSUMED. P1 settles both, and whether the party Pokemon can then be sent out again.

**A premise in the design is wrong, found while building this** (javap of `RunMolangCommand` in
`Cobblemon-fabric-1.8.0+1.21.1.jar`, 2026-10-08): the command tree is `runmolang <molang> [player [npc [pokemon]] |
[pokemon]] | [npc [pokemon]] | [pokemon: string]`. Under `<player>`, `npc` and `pokemon` are SIBLING entity
arguments that parse the same selector, so the design's `runmolang "q.pokemon.discard;" <player> <entity>` may bind the
Pokemon as the `npc` argument (then ignored: `execute` binds `q.npc` only for an `NPCEntity`), leaving `q.pokemon`
unbound. Which sibling brigadier takes is not settled by reading (ASSUMED: the first registered, `npc`). Two forms avoid
the question and are tested first: the four-argument form `<player> <entity> <entity>` (the Pokemon as both), and
`execute as <entity> run runmolang "q.entity.discard;"` (the command binds `q.entity` to the source entity, javap
offsets 175-190). The command always returns 1 (offset 241), so `execute store` cannot read whether it worked.

## Success criteria
- A wild stand-in vanishes under the four-argument form and under the `q.entity` form (RCON, no player).
- The owner's sent-out Pokemon vanishes under each form, its party HP (`current_hp`) is the same before and after, and
  it can be sent out again at once.
- Armed keeper: a send-out in the box is gone within one pass (20 ticks). Armed callback: gone in the send-out's tick.

## Dependencies
Cobblemon 1.8.0 (`runmolang`, `spawnpokemonat`, `pokemon_sent_post`); `cobblers:pocket` registered by
`cobblers_portals`; this pack installed and the server restarted.

## Implementation
`cobblers_dg_probes:p1/*`, objectives `dpp1.st`, `dpp1.r`; area x 1024..1279, z -704..-577; a 17 x 17 glass pen at
(1056, 96, -640); the sweep box `x=1048,y=96,z=-648,dx=16,dy=10,dz=16`.
- `wild`: a macro `spawnpokemonat` of `magikarp level=5 uncatchable` at (1059.5, 96, -637.5), tagged `dpp1.e dpp1.w`,
  `PersistenceRequired`. Returns how many stand.
- `form_entity` / `form_args` choose the keeper's form (`#form` 1 or 2); `arm_keeper`, `arm_callback`, `disarm`.
- `keeper` (20 ticks, armed only): every `cobblemon:pokemon` in the box without `dpp1.keep` is discarded.
- `data/cobblemon/callbacks/pokemon_sent_post/cobblers_dg_probes_p1.molang`: for every send-out on the server, one
  command `execute as <uuid> at @s if dimension cobblers:pocket if entity @s[<box>] run function p1/sent`; `sent` does
  nothing unless `#mode` is 2.

## Test instructions
Install (main session): `python tools/dungeon_probes.py`, copy `build/datapacks/cobblers_dg_probes` into the STAGING
world's `datapacks/`, plain restart (no `/reload`, review N111). `logs/latest.log` must name no
`cobblers_dg_probes` function as failing to load.

### (a) RCON, no player
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:p1/setup` | `Function ... returned 1` | `Unknown function` (pack not loaded) |
| 2 | wait 15 s, then `scoreboard players get #ready dpp1.st` | `#ready has 1 [dpp1.st]` | 0: `ready` never ran |
| 3 | `function cobblers_dg_probes:p1/wild` | `returned 1` | `returned 0`: the macro spawn or the bind failed |
| 4 | `runmolang "q.pokemon.discard;" @e[tag=dpp1.w,limit=1] @e[tag=dpp1.w,limit=1]` then `execute in cobblers:pocket if entity @e[tag=dpp1.w,x=1048,y=96,z=-648,dx=16,dy=10,dz=16]` | `Test failed` (gone: `q.pokemon` bound, zero-arg `discard` runs) | `Test passed, count: 1`; note the runmolang output line |
| 5 | `function cobblers_dg_probes:p1/wild`, then `execute as @e[tag=dpp1.w,limit=1] run runmolang "q.entity.discard;"`, then step 4's test | `Test failed` | `Test passed` |
| 6 | `function cobblers_dg_probes:p1/wild`, `function cobblers_dg_probes:p1/form_entity`, `function cobblers_dg_probes:p1/arm_keeper`, wait 2 s, step 4's test, then `scoreboard players get #seen dpp1.r` | `Test failed`; `#seen` 1 | `Test passed` |
| 7 | `function cobblers_dg_probes:p1/disarm` | `returned 1` | |

Step 4 runs without a player: under the root, `@e[...]` cannot parse as the `player` argument (players only), so the
`npc` branch takes it and its child `pokemon` binds the Pokemon. These steps prove the names on a WILD Pokemon only;
that removal recalls an OWNED one with its HP is the owner's half.

### (b) The owner in game
Before: the owner's first party slot holds a Pokemon able to battle. The session runs everything in the right column.

| # | The owner does | The session runs | PASS |
|---|---|---|---|
| 1 | stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:p1/enter` | owner in the glass pen; `returned 1` |
| 2 | sends out slot 1 inside the pen | `damage @e[type=cobblemon:pokemon,x=1048,y=96,z=-648,dx=16,dy=10,dz=16,limit=1] 4 minecraft:generic` then `runmolang "t.pt = q.player.party; t.p = t.pt.get_pokemon(0); return t.p.current_hp;" <owner>` | the output shows an HP value H, below full |
| 3 | watches it | `runmolang "q.pokemon.discard;" <owner> @e[type=cobblemon:pokemon,x=1048,y=96,z=-648,dx=16,dy=10,dz=16,limit=1] @e[type=cobblemon:pokemon,x=1048,y=96,z=-648,dx=16,dy=10,dz=16,limit=1]` | it blinks out with no recall beam |
| 4 | opens the party screen | step 2's `runmolang ... current_hp` | HP still H; not fainted |
| 5 | sends it out again at once | | it comes out (no "already out" refusal) |
| 6 | (it is out) | `execute as @e[type=cobblemon:pokemon,x=1048,y=96,z=-648,dx=16,dy=10,dz=16,limit=1] run runmolang "q.entity.discard;"`, then step 2's HP read | gone; HP unchanged |
| 7 | sends it out | the THREE-argument form `runmolang "q.pokemon.discard;" <owner> @e[type=cobblemon:pokemon,x=1048,y=96,z=-648,dx=16,dy=10,dz=16,limit=1]` | record: gone (brigadier took `pokemon`) or still out (took `npc`). Either is a result, not a failure |
| 8 | recalls it | `function cobblers_dg_probes:p1/form_args` then `function cobblers_dg_probes:p1/arm_keeper` | |
| 9 | sends it out in the pen | after 2 s: `scoreboard players get #seen dpp1.r`, step 2's HP read | gone within a second; HP unchanged |
| 10 | sends it out once more | `function cobblers_dg_probes:p1/arm_callback`; after it: `scoreboard players get #cb dpp1.r` | gone in the send-out (barely seen); `#cb` 1 |
| 11 | tries Ride or a mount, if the Pokemon rides, inside the pen | | note what happens (no design depends on it) |
| 12 | | `function cobblers_dg_probes:p1/disarm`, `execute as <owner> run function cobblers_dg_probes:p1/leave`, `function cobblers_dg_probes:p1/cleanup` | owner home; `returned 1` |

## Results
NOT_EXECUTED.

## Limitations
- One player. The keeper's four-argument form takes the NEAREST player within 64 as `q.player`; in co-op that may be
  another member. The `q.entity` form needs no player.
- Step 2's `damage` costs the owner's Pokemon 4 HP on staging (an owned Pokemon's hurt writes back to the party).
- What a discard does mid-battle is not tested (the parkour holds no battles).
- The callback fires on every send-out on the server; its one command matches only inside P1's box in the pocket.

## Decision
Gates the no-deploy leg (3.4, engine item: the parkour sweep). If a form passes, the engine uses it: `q.entity`
(no player argument) is preferred if it passes, else the four-argument form; never the three-argument form unless step
7 shows brigadier takes `pokemon`. If no form recalls with HP kept, the parkour cannot refuse Pokemon: the engine drops
the no-deploy rule and gates the parkour by geometry alone (DM 4.2's edge cases), and the owner is asked.

## Follow-up
P2 (a `kill` faints it) stays unrun: the design forbids `kill` anyway.
