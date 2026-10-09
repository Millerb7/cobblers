# EXP-071: B2, does `kill @s` go through a totem, and does the blackout fire once?

**Status: RCON PROXY PASSED (with villagers); owner part OPEN (2026-10-08).** Probe B2 of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
The timer's kill is `kill @s`, never `damage ... outside_border` alone, "because a totem can stop that" (2.5, DM 1.3).
B2 settles that a totem in the off hand does not save a player from `kill`, that it does save from `outside_border`
damage, and that the blackout runs exactly once for the kill.

## Success criteria
- A husk holding a totem dies to `kill`; another survives 1000 `outside_border` damage and its totem is used.
- The owner, totem in the off hand, killed by `kill`: dies once (`dpb2.d` 1), the totem is still held (not used), and
  the blackout's message, charge and teleport happen once.

## Dependencies
Vanilla `kill`, `damage`, `deathCount`; `cobblers_blackout` installed (its `keepInventory`, its death path).

## Implementation
`cobblers_dg_probes:b2/*`; objectives `dpb2.st`, `dpb2.r`, `dpb2.d` (`deathCount`, counted from setup). Area
x 1536..1791; pen at (1568, 96, -640), box `x=1561,y=95,z=-647,dx=14,dy=3,dz=14`.
- `mobs`: two husks (NoAI, Silent, persistent; husks do not burn), totem in the off hand, drop chance 0:
  `dpb2.kill` at (1571.5, 96, -636.5), `dpb2.dmg` at (1565.5, 96, -636.5).
- `kit` (as the owner): one totem, given (nothing overwritten), and `dpb2.d` set to 0.

## Test instructions
### (a) RCON, no player (a PROXY: a mob's totem, not a player's)
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:b2/setup`; wait 15 s; `function cobblers_dg_probes:b2/mobs` | `returned 2` | fewer |
| 2 | `execute in cobblers:pocket run kill @e[tag=dpb2.kill,x=1561,y=95,z=-647,dx=14,dy=3,dz=14]` | `Killed Husk` | |
| 3 | `execute in cobblers:pocket if entity @e[tag=dpb2.kill,x=1561,y=95,z=-647,dx=14,dy=3,dz=14]` | `Test failed` (dead: the totem did not save it) | `Test passed`: a totem stops `kill`, and the design's kill is wrong |
| 4 | `execute in cobblers:pocket run damage @e[tag=dpb2.dmg,x=1561,y=95,z=-647,dx=14,dy=3,dz=14,limit=1] 1000 minecraft:outside_border` | `Applied 1000.0 damage to Husk` | |
| 5 | `execute in cobblers:pocket if entity @e[tag=dpb2.dmg,x=1561,y=95,z=-647,dx=14,dy=3,dz=14]`, then `data get entity @e[tag=dpb2.dmg,limit=1] HandItems[1]` | `Test passed, count: 1` and `{}` (the totem saved it and was used) | dead: border damage is not stopped by a totem, so `damage` would also have done (not a failure of the design, a simplification) |

### (b) The owner in game
| # | The owner does | The session runs | PASS |
|---|---|---|---|
| 1 | stands in the overworld; knows his checkpoint | `execute as <owner> at @s run function cobblers_dg_probes:b2/enter`, `execute as <owner> run function cobblers_dg_probes:b2/kit` | in the pen; a totem in the inventory |
| 2 | puts the totem in the off hand | `execute if items entity <owner> weapon.offhand minecraft:totem_of_undying` | `Test passed` |
| 3 | stands still | `kill <owner>` | the owner dies: no totem animation |
| 4 | reads chat and where he wakes | `scoreboard players get <owner> dpb2.d`; `execute if items entity <owner> weapon.offhand minecraft:totem_of_undying` | `1`; `Test passed` (kept, unused); ONE blackout line, one charge, one teleport to the checkpoint |
| 5 | | `function cobblers_dg_probes:b2/cleanup` (he is already home) | `returned 1` |

The kill costs the owner the blackout's money on staging (`data/blackout.json` `money`).

## Results

### RCON, no player (2026-10-08, main session)

Run 2026-10-08 22:46-22:58 by the main session over RCON, staging-2026-10-01 (staging only), pack `cobblers_dg_probes` from `tools/dungeon_probes.py` (installed by hand, plain restart, no /reload), no player online. Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, rctmod 0.19.0-beta / rctapi 0.16.1-beta, Mega Showdown 1.0.2, the server's full mod set (MobsBeGone 0.0.7 among it), Java 21, -Xmx16G.

| Step | Reading |
|---|---|
| 1 (as built) | **FAILED, not on the mechanism:** `b2/mobs` returned 0. The server's MobsBeGone 0.0.7 (`config/mobsbegone-blacklist.json`) deletes every summoned vanilla mob except villagers and wandering traders, in every dimension (a summoned pig was gone at the next command, overworld and pocket alike). The generator now summons villagers. Re-run after a plain restart: |
| 1 | `b2/mobs` returned 2 |
| 2-3 | `kill` on the villager holding a totem: `Killed Villager`, then absent: **the totem does NOT stop `kill`: PASS** |
| 4-5 | 1000 `outside_border` damage on the other: alive, off hand `{}` (the totem was used) |

So the timer's `kill @s` goes through a totem, and `damage ... outside_border` would NOT (a totem stops it): keep `kill`.
A villager is a proxy; that the blackout fires ONCE for a player is the owner's half.

## Limitations
The kill-credit window (a wild hit within 100 ticks makes `kill` a wild kill) is DX1's and E1's, not B2's.

## Decision
Gates the timer's kill (2.5). If step (a) 3 or (b) 3 shows a totem stopping `kill`, the engine takes the totem first
(`clear @s minecraft:totem_of_undying` on the slot's death path, the item kept in escrow and returned on respawn) and
B2 is re-run. If the blackout fires twice, its dedupe is the defect, for `minecraft-systems-dev`.

## Follow-up
None.
