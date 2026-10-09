# Dungeon death: what a death inside a dungeon takes, read from the code

**Audit, 2026-10-08, against `88bf98b`. Verdict: the rule is NOT met today.** The owner's rule (2026-10-08): no
Pokemon or trainer takes a player's items in a dungeon; a dungeon death costs the blackout's money, the run's held
rewards and the sigil/lockout, nothing else. In the pack as generated, **a loss to any wild Pokemon in a pocket slot
that its keeper did not tag `cobblers.gm` still takes items, holds the $600 in the claim, and makes a guardian**, in
battle and when killed outside one. The design's den (`docs/mechanics/DUNGEONS.md` 3.6) spawns exactly such Pokemon.
The timer, falls, lava, drowning, `/kill` and trainer losses already take no items.

Labels: **VERIFIED (code)** read in the repository at the line given; **VERIFIED (jar)** read from
`cobblers-local/server-snapshot-2026-10-05/mods/` with zipfile/javap; **VERIFIED (sim)** shown by
`tests/test_dungeon_death.py` on the repository's command simulator (generated text, not a server);
**ASSUMED** not read or run. Nothing here was run in game.

## 1. Every mechanism that takes, holds or destroys items or money on death or blackout

`tools/blackout_pack.py` (the `cobblers_blackout` pack) is the only one that takes anything. VERIFIED (code):

| # | Mechanism | Where | Takes / holds |
|---|---|---|---|
| M1 | `gamerule keepInventory true`, set at every load | `:173-174` | keeps everything (no vanilla drop) |
| M2 | the charge: `cobbledollars remove @s <min(600, balance)>` | `charge` `:274-290` | money, every blackout |
| M3 | wild battle loss: `battle_loss_wild` -> `recovery/make` unless the **victor** has `claims.exempt_tag` | `:222-235` (exempt test `:229`, make `:231`); callback `:1038-1058` (`is_pokemon` -> `wild`, `:1046`) | balls 40% (max 30), medicine 40% (max 12), one consumable |
| M4 | killed outside battle by a wild Pokemon: advancement `entity_killed_player` -> `blackout/killed` -> `recovery/killed` -> **the same** `battle_loss_wild` | `:261-273`, `:606-614` | as M3 |
| M5 | the claim itself: count with `clear ... 0`, plan, write the ledger, then `item modify ... set_count add` | `recovery/make` `:400-422`, `take` `:435-449`, `commit` `:450-482`, `apply_one` `:494` | the items, into `cobblers_recovery:ledger` |
| M6 | the guardian: victor given `PersistenceRequired:1b`, `cobblers.guardian`, a number | `bind` `:495-500` | holds the claim |
| M7 | **the money held by the victor** (`money.held_by_wild_victor`): the charge's `bo.lost` stamped into the claim | `hold_money` `:626-631`, gated on `bo.clm 2` at `:234` | the $600, until the guardian is beaten |
| M8 | maintenance: a guardian absent from its loaded site twice is rebuilt there from the ledger | `maintain`/`check`/`vanished`/`rebuild` `:705-746` | keeps the holder at the site |
| M9 | delivery: a resolved claim is summoned as owner-only item entities **at the owner's feet**, `as @a at @s`, on resolution and at login | `resolve_pid` `:557`, `defeated` `:656`, `login` `:385`, `drop_one` `:702` | gives back, wherever the owner stands |
| M10 | the arena exemption: a player holding `cobblers.arena_bout` returns before anything in `battle_loss_npc` | `:236-243`; audited by `tools/arena_runtime_audit.py:557-571` | waives money and return |

Outside the pack:

- **Lenient Death** (`modpack/config/lenientdeath.json5`, `preserveItemsOnDeath: "yes"`): its only item hook,
  `InventoryMixin.onlyDropIfNotSafe`, wraps `Inventory.dropAll()` (VERIFIED (jar), `lenientdeath-1.2.5+1.21.1.jar`).
  Vanilla calls `dropAll` only when keepInventory is false (ASSUMED, vanilla source). So it never acts while M1 holds.
- **CobbleDollars**: its one battle handler, `CobbleDollarsEventsKt.battleVictory`, only **adds** to winners
  (`BigInteger.add`, one `setCobbleDollars`, no `subtract`); no config key for a loss penalty
  (`modpack/config/cobbledollars/common.json`). No loss penalty. VERIFIED (jar).
- **rctmod 0.19.0**: `Inventory` (`class_1661`) is referenced only by `MerchantResultSlotMixin` and `TrainerCard`
  (a constant-pool scan, not a decompile). No loss path touching items found. VERIFIED (jar, scan).
- **Cobblemon 1.8.0**: no native blackout; a full-party faint ends the battle and leaves the party fainted
  (`modpack/config/cobblemon/main.json` has only faint/heal keys). The pack heals on arrival (`arrive` `:300`).
  ASSUMED for the absence of any item effect.
- **The dungeon design** (`DUNGEONS.md`, not built): the run's escrow is scores, cleared on death (`:179-182`); the
  rift pick is taken back with `clear` on every exit (`:259-262`).

## 2. The shared routes (the overlaps)

1. **The charge and the claim share one score, `bo.lost`** (VERIFIED (code), and `BLACKOUT_RECOVERY_COUPLING.md`):
   M2 sets it, M7 stamps it into the claim, `deliver_one` pays it back (`:689`, `pay_money` `:632`). **In a dungeon
   today, a wild loss sends the $600 into a guardian standing in a pocket slot** (VERIFIED (sim):
   `recovery/hold_money` is called). That money is held by something in a room nobody can return to.
2. **The exemption keys on the VICTOR, never the player.** The gulch Megas and the Entei carry `cobblers.gm`
   (`tools/entei_boss.py:575-580`). That covers only Pokemon a keeper tagged. `DUNGEONS.md` 3.7's legendary
   carries it (`:367`); **3.6's den does not** (`:331-335`: four wild Pokemon, Entei's farm pattern, no exempt tag).
   Natural spawns in the pocket are "moot while ... `the_void` biome spawns nothing, which is untested" (`:621-622`).
3. **Delivery lands in the dungeon.** M9 runs `as @a at @s`: a claim settled by a helper while its owner is in a
   run is summoned at the owner's feet in the slot. Usually picked up at once (PickupDelay 0); not if the inventory
   is full, the owner is dead, standing in lava, or ejected in the same tick (tick-function order between packs,
   ASSUMED). Then it is lost to the slot's sweep or reset.
4. **The kill credit window.** M4's advancement fires on vanilla's kill credit, which names the last mob that hurt
   the player within 100 ticks, whatever finally killed them (ASSUMED, vanilla `getKillCredit`). So the timer's
   `kill @s`, lava or a fall within five seconds of a Fight-or-Flight hit (unprovoked attacks on from level 25,
   `base-pack/cobbleverse/config/fightorflight.json5:3-17`) becomes a wild "kill" and a claim.
   `DUNGEONS.md:177-178` ("A command death is environmental, so no item is lost") holds only without such a hit.
   This contradicts DEATH_AND_WIPE.md's "do not use a recently-attacked timeout" in the overworld too (a probe:
   be hit by a wild Pokemon, then `/kill` within 5 s; is a claim made?).
5. **The balance read by two systems.** The charge reads `cobbledollars query`, and so does the NPC-payout clawback
   the dungeon's stands adopt from the arena (`tools/arena_runtime.py:49-59`, `:219-228`). The design's sudden death
   kills "the moment `in_battle` reads 0" (`DUNGEONS.md:183-186`). After a WON stand battle at 0, the $600 then
   lands inside the clawback's measuring window. Not an item route; the engine builder must order the two
   (ASSUMED risk, unmeasured).
6. `data/entei_boss.json:135` says a death in the room "goes through the blackout's death path". An Entei kill goes
   through M4 (the wild-loss path), exempted by the victor tag. The outcome is right; the record names the wrong path.

## 3. Per death kind, inside a dungeon, today

The return in every row: `bo_pending`, then on the first living tick a teleport to the overworld checkpoint
(`:291-299`, `:358`), a party heal and 5 s of Resistance. Money in every row: the flat $600, clamped to the balance (M2).

| Death | Path | Items | Pokemon | Money | Held rewards / lockout | Position |
|---|---|---|---|---|---|---|
| timer `kill @s` | `blackout/death` | kept | healed | $600 lost | escrow cleared, lockout stands (design) | checkpoint |
| ... within 5 s of a wild hit | M4 (kill credit) | **claimed** unless the hitter has `cobblers.gm` | healed | **$600 held** by the guardian | as above | checkpoint |
| boss or trainer battle loss (`cobblemon:npc`, rctmod) | `battle_loss_npc` | kept | healed | $600 lost | as above | checkpoint |
| wild boss or legendary loss, tagged (Entei, lake) | M3, exempt | kept | healed | $600 lost | as above | checkpoint |
| **wild loss, untagged (den, stray spawn)** | M3 | **claimed, guardian in the slot** | healed | **$600 held** | as above | checkpoint |
| killed outside battle by a wild Pokemon | M4 | as the two rows above, by victor tag | healed | as above | as above | checkpoint |
| fall, lava, drowning, suffocation, `/kill` | `blackout/death` | kept (unless the 5 s window) | healed | $600 lost | as above | checkpoint |
| arena-tagged player, NPC loss | M10 | kept | **not healed** | **none** | n/a | **stays** |

Rows 1, 3, 4 and 7 VERIFIED (sim and code); rows 2 and 5 VERIFIED (sim) for the claim, ASSUMED for the kill credit.
`DUNGEONS.md` 3.5 says no fall can kill (catch bands).

## 4. The rule a builder must implement

1. **One player tag for the whole run**, `data/blackout.json` `dungeon_exempt.player_tag` (the tests read it there;
   proposed `cobblers.dungeon_run`). Added on entry before the first leg; removed on **every** exit: clean exit,
   eject, the respawn after any blackout, a relog, and the overworld backstop sweep `DUNGEONS.md:259-262` already
   needs. A stale tag would exempt a player in the overworld for good.
2. **`blackout/battle_loss_wild` exempts a player holding it**, beside the victor test (`:229`):
   `execute if entity @s[tag=<tag>] run scoreboard players set #exempt bo.tmp 1`. Both M3 and M4 pass through it, so
   one line covers battle losses, kills outside battle and kill-credit deaths. It sets no `bo.clm 2`, so M7 holds no
   money. The charge and the return run unchanged ("the money the blackout already takes"). Defence in depth:
   the same test as the first line of `recovery/make`.
3. **Not in `battle_loss_npc`.** It takes no items, and a dungeon trainer loss must still charge and return.
   `arena_runtime_audit.check_blackout` fails if a second early return appears there. Any future trainer claim
   (DEATH_AND_WIPE.md rule 5) must test the same tag.
4. **`recovery/deliver` returns for a player holding the tag**, leaving the claim at `deliver`. **The exit path runs
   `function cobblers:recovery/deliver` as the player** once they are out, or the items wait for the next login.
5. Keep tagging every keeper-spawned wild Pokemon with `claims.exempt_tag` (den, boss, lake) anyway. A second guard,
   and the den must gain it.
6. The rift pick is taken back by its component (`clear @s minecraft:iron_pickaxe[minecraft:custom_data~{cobblers_dg:"pick"}]`, syntax ASSUMED until the design's probe R2),
   never by item id: a bare `clear @s iron_pickaxe` takes the player's own.
7. Do not depend on keepInventory being re-set: it is set at load only, and an operator's `/gamerule` lasts until the
   next reload (M1).

**Nothing that cannot be told at the datapack level** has been found. Every taker is our own pack. Lenient Death,
CobbleDollars, rctmod and Cobblemon take nothing on a loss. The one thing outside our control is vanilla's kill
credit (overlap 4), and rule 2 makes it moot inside a dungeon, because the exemption reads the player, not the killer.

## 5. Tests

`tests/test_dungeon_death.py`, on `TB.Sim`/`NbtSim`:

- the rule on a **reference patch** of the generated text (rules 2 and 4 as lines): no make, commit, apply, bind,
  hold or ledger entry; the $600 removed once and the return queued; the control without the tag still claims;
- the **mutation**: every line reading the dungeon tag stripped, so items are taken and the guardian is bound again,
  in both paths, and delivery drops in the slot again;
- the generated pack held to the rule, **xfail(strict)** until `dungeon_exempt` exists. The failures show the claim,
  the bind and `hold_money` running for a tagged player;
- static: `blackout/death`, `battle_loss_npc` and `battle_loss_other` reach no item taker (mutation: a claim call
  added to `battle_loss_npc` is caught); keepInventory set at load; the victor-tag precedent on the real pack.

The four failures in `tests/test_blackout_recovery_pid.py` (`600 == 200`) predate this unit and are
`BLACKOUT_RECOVERY_COUPLING.md`'s, not touched here.

## Not verified

In game: everything. Rule 2's line on a server. The kill credit window (overlap 4). Whether Cobblemon spawns
anything in the pocket's `the_void`. The tick order between the blackout's login delivery and a dungeon eject. The
server's own Lenient Death and Fight-or-Flight configs (the live server is not read; the repository's copies are cited).

## E1 as built

The blackout half of E1 (`DUNGEONS.md` 11.3), built 2026-10-08 by `minecraft-systems-dev`. Rung: datapack functions
(principle 6), the same pack and the same victor-test pattern the gulch and the Entei already rely on; nothing new is
needed because the whole rule is "read one tag on the player", which a function line does. The engine half (adding the
tag, counting the tail, calling the two functions) does not exist yet.

**Data.** `data/blackout.json` `dungeon_exempt`: `player_tag` **`cobblers.dg_run`** (the proposed `cobblers.dungeon_run`,
renamed to the engine's `dg_` prefix), `tail_ticks` **100** (ASSUMED: vanilla's kill-credit window, not read from the
jar), the two function names, and the engine's obligations as `engine_must` / `engine_must_never`. With no
`dungeon_exempt` the generator emits the pack as before.

**The pack** (`tools/blackout_pack.py`):
- `blackout/battle_loss_wild`: `execute if entity @s[tag=cobblers.dg_run] run scoreboard players set #exempt bo.tmp 1`,
  directly after the victor test (rule 2). M3 and M4 both pass through it, so a battle loss, a kill outside battle and a
  kill-credited timer, lava or fall death are covered by the same line. No claim keeps `bo.clm` 0, so `hold_money`
  never runs; the charge and `bo_pending` are untouched.
- `recovery/make`: `execute if entity @s[tag=cobblers.dg_run] run return 0` as its first line (defence in depth).
- `recovery/deliver`: the same return as its first command (rule 4). The login delivery (`blackout/login`) and the
  two `execute as @a at @s run function .../deliver` calls (a guardian beaten, a pid resolved) all go through it, so a
  claim settled while its owner is in a run stays at `deliver`.
- `battle_loss_npc` and `battle_loss_other` are unchanged (rule 3).
- New, for the engine: `recovery/run_tail_end` (removes the tag, then runs `recovery/deliver`) and
  `recovery/run_tag_stale` (the backstop; runs `run_tail_end`). Only these remove the tag.

**The interface the engine must honour:**
1. Add `cobblers.dg_run` in `door_click`, in the function that reserves the slot, before the arrival delay; at the same
   time cancel any tail still counting from an earlier run (else it ends inside the new run and untags the player).
2. Never `tag ... remove cobblers.dg_run`. The death handling on respawn starts the tail; it never ends it.
3. After every way out (clean exit, eject, respawn after death, dead-run kill), count at least `tail_ticks` in its own
   per-player score, then `execute as <player> at @s run function cobblers:recovery/run_tail_end`, in the overworld.
4. In the overworld backstop sweep, for a tagged player outside `cobblers:pocket` with no live run and no tail left,
   `execute as <player> at @s run function cobblers:recovery/run_tag_stale`.
5. Never call either function while the player is in `cobblers:pocket`: both deliver at the player's feet. The pack does
   not test the dimension itself (neither command simulator models `execute if dimension`); this is the engine's.

**Contract** C24 in `data/system_contracts.json` (owner `recovery_claims`, consumer `dungeons`). Its blackout cases
pass on the generated pack; its engine cases are `fails_today` (strict xfail) until `tools/dungeon.py` exists.

**Not verified:** nothing has run on a server (DX1). The 100-tick window is ASSUMED. That `execute if entity @s[tag=..]`
with no `as` reads the player is how every other player test in this pack is written (`battle_loss_npc`'s arena tag),
not separately proved in game.
