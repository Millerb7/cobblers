# EXP-074: R2, does `minecraft:can_break` on a pick in adventure mode break the seam ores and nothing else?

**Status: designed 2026-10-08, NOT_EXECUTED.** Probe R2 of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
The run is in adventure mode with the rift pick, whose `minecraft:can_break` lists the seam's ores (3.3), so the take is
kept to the seam: the player's own tools break nothing and nothing but the seam can be mined. The 1.21 component's
syntax is ASSUMED (no repository file uses it; the vanilla jar is only on the server, which this unit may not read).
R2 settles the syntax over RCON and the behaviour in game.

## Success criteria
- The pick, written into a chest with the full form `can_break={predicates:[{blocks:[...]}]}`, keeps the component
  (`data get` shows it). The short form is recorded either way.
- In adventure: the pick breaks coal and iron ore; it breaks no stone, glass or dirt; the owner's own pickaxe breaks
  nothing; `r2/read` returns 0 controls gone.

## Dependencies
Vanilla 1.21.1 data components; adventure mode.

## Implementation
`cobblers_dg_probes:r2/*`; objectives `dpr2.st`, `dpr2.r`. Area x 2304..2559; pen at (2336, 96, -640); the face as R1's
at z -635, x 2332..2340 (coal, iron, coal, iron, coal, iron, stone, glass, dirt; y 96 and 97); a chest at
(2341, 96, -643) for the parse step. `kit`, `pick`, `unkit`, `take_pick` as R1's; `read` returns the number of CONTROL
blocks gone and leaves per-kind counts in `#gone_<id> dpr2.r`.

## Test instructions
### (a) RCON, no player (the syntax)
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:r2/setup`; wait 15 s | `returned 1` | |
| 2 | `execute in cobblers:pocket run item replace block 2341 96 -643 container.0 with minecraft:iron_pickaxe[minecraft:custom_data={cobblers_dg:"pick"},minecraft:unbreakable={},minecraft:can_break={predicates:[{blocks:["minecraft:coal_ore","minecraft:iron_ore"]}]}]` | a success line | a parse error (copy its text into Results: it names what the component wants) |
| 3 | `execute in cobblers:pocket run item replace block 2341 96 -643 container.1 with minecraft:iron_pickaxe[minecraft:can_break={blocks:["minecraft:coal_ore","minecraft:iron_ore"]}]` | record: success or error (the single-predicate short form) | |
| 4 | `execute in cobblers:pocket run data get block 2341 96 -643 Items` | slot 0 shows `"minecraft:can_break"` with both ore ids, `"minecraft:unbreakable"` and `custom_data` | the component is missing |
| 5 | grep the boot log: `Failed to load function cobblers_dg_probes:r2/pick` | absent | present: the pick's syntax failed at load (step 2 says why) |
| 6 | `function cobblers_dg_probes:r2/read` | `returned 0` | |

### (b) The owner in game
| # | The owner does | The session runs | PASS |
|---|---|---|---|
| 1 | stands in the overworld holding his own pickaxe | `execute as <owner> at @s run function cobblers_dg_probes:r2/enter`, `execute as <owner> run function cobblers_dg_probes:r2/kit` | adventure; the rift pick in the inventory; its tooltip lists what it can break |
| 2 | with HIS OWN pickaxe tries a coal ore, the stone, the glass | `function cobblers_dg_probes:r2/read` | nothing breaks; `returned 0`; `#gone_coal_ore dpr2.r` 0 |
| 3 | with the rift pick tries the stone, glass and dirt, both courses | `function cobblers_dg_probes:r2/read` | nothing breaks; `returned 0` |
| 4 | with the rift pick breaks 2 coal and 2 iron ore | `function cobblers_dg_probes:r2/read`, `scoreboard players get #gone_coal_ore dpr2.r`, `... #gone_iron_ore dpr2.r` | they break and drop ore items into his inventory; `returned 0`; 2 and 2 |
| 5 | tries to place a block against the face | | refused (adventure) |
| 6 | | `execute as <owner> run function cobblers_dg_probes:r2/unkit`, `execute if items entity <owner> container.* minecraft:iron_pickaxe[minecraft:custom_data~{cobblers_dg:"pick"}]` | survival; `Test failed` (the pick is gone) |
| 7 | | `execute as <owner> run function cobblers_dg_probes:r2/leave`, `function cobblers_dg_probes:r2/cleanup` | home |

## Results
NOT_EXECUTED.

## Limitations
The behaviour half needs the owner; the RCON half proves the parse and the stored component only. Breaking speed with
an unbreakable iron pick on each band's ores is not measured.

## Decision
Gates the seam's containment (3.3, engine: `door_click` gives the pick). If the full form fails and the short form
parses, the engine uses the short form (one predicate listing every ore id). If neither keeps the take to the seam,
adventure mode alone still stops every other break, and the seam becomes a click-to-mine block (interaction entities
over the seam, `setblock air` and `loot give` per click): a larger engine piece, owed to the owner as a choice.

## Follow-up
R1 (the stat under this pick).
