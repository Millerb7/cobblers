# EXP-075: F1, does a teleport mid-fall keep the fall distance, with and without `resistance 5`?

**Status: designed 2026-10-08, NOT_EXECUTED.** Probe F1 of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
A parkour fall lands in a catch band 6 below the route and is teleported to the last checkpoint with `resistance 5`
for 2 seconds (3.5). "No fall can kill." Whether a teleport keeps the fall distance, so the player takes the fall's
damage on the checkpoint, is ASSUMED. F1 measures it on mobs over RCON (a PROXY) and on the owner.

## Success criteria
- Mob B (teleport, no resistance): Health 20 after landing on the pad means the teleport reset the fall; anything
  lower is the carried fall, about `fall - 3`.
- Mob C (teleport + resistance 5): Health 20.
- Mob A (no catch, the control, a 13-block fall onto stone): about 10, proving the fall hurts.
- The owner, shaft PC (resistance): no damage. Shaft PB (none): the reading the engine needs, either way.

## Dependencies
Vanilla `tp`, `effect`, `FallDistance` and `Health` NBT.

## Implementation
`cobblers_dg_probes:f1/*`; objectives `dpf1.st`, `dpf1.r`. Area x 2560..2815; a 25 x 25 pen at (2592, 96, -640).
- Three 1 x 1 glass tubes at z -640: A x 2584 (stone at y 112: the husk falls 126 to 113), B x 2587 and C x 2590 (open
  to the floor); B's and C's pads at y 120, two south, in glass cells.
- Two 3 x 3 player shafts: PB centre x 2596, PC x 2601, from y 126 to a 2-deep water bottom (a missed catch lands in
  water); pads 3 x 3 at y 120 south of each, railed.
- Catch bands y 108..113. `tick` runs every tick while armed (at most 400 ticks): anything tagged in a band is
  teleported to its pad (`catch_*` stamps `FallDistance x 100` first, and C/PC give `resistance 2 4`, level 5).
- `mobs`: three husks at y 126 (`dpf1.a/b/c`; persistent, silent; not NoAI, because a NoAI mob does not fall).
- `drop_pb`, `drop_pc` (as the owner): Health x 100 stamped, then teleported into the top of the shaft at y 126.

## Test instructions
### (a) RCON, no player (a PROXY: a player's fall is reported by the client; a mob's is the server's)
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:f1/setup`; wait 15 s; `function cobblers_dg_probes:f1/mobs` | `returned 1` | |
| 2 | wait 5 s; `scoreboard players get #caught_b dpf1.r`, `... #caught_c dpf1.r` | 1 and 1 | 0: the catch missed (then B's and C's Health mean nothing) |
| 3 | `data get entity @e[tag=dpf1.a,limit=1] Health` | about 10.0 (the control hurts) | 20.0: no fall damage at all here; the rest is void |
| 4 | `data get entity @e[tag=dpf1.b,limit=1] Health`; `scoreboard players get #fd_b dpf1.r` | record both: 20.0 = reset by the teleport; lower = carried (`#fd_b` / 100 is the fall at the catch) | |
| 5 | `data get entity @e[tag=dpf1.c,limit=1] Health` | 20.0 | lower: resistance 5 did not cover the landing |

### (b) The owner in game (survival, full health)
| # | The owner does | The session runs | PASS |
|---|---|---|---|
| 1 | stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:f1/enter` | in the pen |
| 2 | lets himself fall | `execute as <owner> run function cobblers_dg_probes:f1/drop_pc` | he falls, is caught at about y 110 and lands on the PC pad; no damage, resistance shown |
| 3 | | `scoreboard players get #caught_pc dpf1.r`, `... #fd_pc dpf1.r`, `... #hp_pc_before dpf1.r`, `... #hp_pc_after dpf1.r` | 1; a fall above 300 (3 blocks); after = before |
| 4 | walks off the pad, waits for full health | | |
| 5 | lets himself fall | `execute as <owner> run function cobblers_dg_probes:f1/drop_pb` | caught onto the PB pad |
| 6 | reads his hearts | `scoreboard players get #caught_pb dpf1.r`, `... #fd_pb dpf1.r`, `... #fd_pb_after dpf1.r`, `... #hp_pb_before dpf1.r`, `... #hp_pb_after dpf1.r` | record: after = before means the teleport resets a player's fall; lower is the carried fall |
| 7 | | `execute as <owner> run function cobblers_dg_probes:f1/leave`, `function cobblers_dg_probes:f1/cleanup` | |

## Results
NOT_EXECUTED.

## Limitations
- The mob half is a proxy. A player's fall distance is accumulated from the client's movement packets and its landing
  is judged from the client's on-ground flag; only the owner's half reads the real case.
- `#hp_*_after` is read 2 ticks after the teleport; damage that lands later is seen in the owner's hearts only.

## Decision
Gates the catch band's safety (3.5, V6). Either PB result is usable: the engine always gives `resistance 5` as designed,
so PC is the case that must pass. If PC shows damage, the engine teleports to the checkpoint one block ABOVE the pad
and gives `slow_falling` for 1 second instead (no fall can kill either way), and F1 is re-run on that.

## Follow-up
None.
