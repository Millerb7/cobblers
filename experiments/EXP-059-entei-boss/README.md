# EXP-059: does the repeatable Entei work, one copy per player, in the pocket dimension?

**Status: NOT_EXECUTED.** Designed 2026-10-08 by unit ENTEI with the pack it tests (`tools/entei_boss.py`,
`data/entei_boss.json`, step R16Q). Nothing has been run on a server. The builder wrote this procedure and the
builder's own tests (`tests/test_entei_boss.py`). **The builder does not grade it.** A different agent or the main
session reviews the results.

The number: EXP-057 and EXP-058 are not in this repository. The coordinator assigned 059 because units working in
parallel the same night may take 057 and 058.

## Objective

Option B of `docs/mechanics/NETHER_DUNGEON_SCOPE.md` is built. This experiment runs the scope's experiments that gate it:

- **X2**: a per-player wild boss. It is catchable until the player's first catch, then uncatchable with an item roll.
- **X3**: entry by a key eaten in the Nether, into `cobblers:pocket`.
- **X4**: loss, flee, forfeit and logout.

**Yes** means the boss is playable, and each mechanism option A needs has been seen working once.

## Success criteria

Each criterion is observable in game or over RCON.

- **X3-a.** The recipe loads. Crafting 2 netherite ingots gives one "Tower Ash" (lore "Eat it in the Nether, and the
  tower remembers you."). That price is the economy design's, `ECONOMY_OVERHAUL.md` section 8 / U9. The key is a
  `minecraft:mourner_pottery_sherd` that carries the components in `data/entei_boss.json` `key.components`, and can
  be eaten. (Until 2026-10-08 it was a blaze powder "Ember Sigil"; `key.item_why` says why it changed.)
- **X3-look.** The room reads as "The Tower After the Fire" (`docs/mechanics/NETHER_ENCOUNTERS.md` section 3.1):
  stripped dark oak walls and ceiling, a cracked stone brick floor, four sea lanterns, a dark-oak log arch with a
  pale grey sheet, a floor bell sunk under the Entei's spot inside a 3 x 3 ring of light grey concrete powder. The
  owner judges the look; the ids are this unit's choice (`room.palette_why`).
- **X3-b.** Eaten in the Nether by a player holding `cobblers:flag/champion_cleared`, it teleports them to slot 1's
  arrival point (-768, 96, -773) in `cobblers:pocket`, facing the room.
- **X3-c.** Each refusal gives the sigil back with its line:
  - eaten in the overworld;
  - eaten without the flag;
  - eaten again inside the lockout, where the line shows the minutes left;
  - eaten while in a run.
- **X2-a.** About 2 s after arrival (40 ticks), a level-100 Entei stands on the slot's spot (-768, 96, -764). It is
  tagged `cobblers.eb`, `cobblers.eb.s1` and `cobblers.gm`, and carries `eb.run` equal to `#s1 eb.run`. Its model
  renders (Mega Showdown's).
- **X2-b.** Before the first catch the Entei can be caught. The catch grants `cobblers:entei_boss/caught` and adds 1
  to `eb.clears`.
- **X2-c.** On the next run the Entei refuses the ball ("cannot be caught"). Fainting it in battle puts exactly one
  item from `cobblers:entei_boss/drops` into the inventory, adds 1 to `eb.clears`, and only once per run.
- **X2-d.** The arch's click returns the player to the Nether block they ate the sigil in, at its centre, and frees
  slot 1: `#s1 eb.own` 0, and the Entei is gone.
- **X4-a.** Losing the battle charges the flat blackout ($600, or the whole balance if less). It returns the player to
  their overworld checkpoint, healed, with **no** item claim and no guardian. Slot 1 is free within 1 s.
- **X4-b.** Fleeing the battle leaves the Entei on its spot. It can be fought again, and the run continues.
- **X4-c.** Logging out mid-battle frees the slot. Logging back in, within 1 s the player is sent back to their
  Nether block with `eb.slot` 0, and any Entei left standing in the room is killed on that same pass. If they catch
  it before the pass (a catch-mode run), `cobblers:entei_boss/caught` is granted, so their next run is uncatchable
  (review N142: never a second catch).
- **X4-d.** The lockout survives the clock: a player who has never entered is let in on a world whose
  `time query gametime` is under 24,000; and a player whose `eb.last` is above the current game time (a re-export
  restarts the clock) is let in, not locked out (review N142).

## Dependencies

- **Packs:**
  - `cobblers_portals`: it defines `cobblers:pocket`, and the dimension registers only at a boot (EXP-047).
  - `cobblers_entei_boss` (this pack).
  - `cobblers_blackout`: the loss path and the exempt tag.
  - `cobblers_progression`: the `champion_cleared` flag.
  - `cobblers_levelcap`: the catch block. At level 100 against cap 100 it should allow the catch.
- **Mods:**
  - Cobblemon 1.8.0.
  - **Mega Showdown 1.0.2**, which ships Entei's model. The research note says Entei is implemented by Mega Showdown
    plus the COBBLEVERSE datapack, not by Cobblemon alone (`docs/research/notes/legendary-species-1.8.0.md` on the
    integration branch). Remove Mega Showdown and Entei is unimplemented.
- **Experiments:**
  - EXP-023: `uncatchable` refuses the ball.
  - EXP-034: the interaction click.
  - EXP-042: the blackout.
  - EXP-046: the macro spawn.
  - EXP-047: positional selectors are confined to their dimension.

## Implementation

| Part | Where |
|---|---|
| Record | `data/entei_boss.json`: decision, rung, species evidence, level and why, props, key, rooms, lockout, drops, loss path, does_not_cover |
| Generator | `tools/entei_boss.py` → `build/datapacks/cobblers_entei_boss`, world-local (`tools/reapply.py` WORLD_LOCAL) |
| Rooms | step **R16Q** runs `cobblers:entei_boss/place` after the portals' R16P. Four sealed slots, 128 apart, at z -768, x -768/-640/-512/-384, feet y96 |
| Keeper | `entei_boss/keeper` every 20 ticks: tend each owned slot, then send out anyone in the band who is not in their own slot |
| Callbacks | `battle_fainted` and `pokemon_captured` (`cobblers_entei_boss.molang`) |

## Test instructions

**Safety.** Staging only, never the live world. Before any step:

1. Run the process and port check.
2. Take the coordination lock.
3. Run `tools/install_check.py --server-dir <staging> --world-dir <staging world>`.

Then `python tools/reapply.py install` with the world-local packs. **Restart the server** if `cobblers_portals` was
newly installed: the dimension registers only at boot. Then run step R16Q.

### RCON only, no player needed

1. `datapack list enabled` names `file/cobblers_entei_boss` and `file/cobblers_portals`. The boot log has no error
   naming `entei_boss`. The recipe, the advancements and the loot table parse at load, so an unknown component field
   or a bad food shape (X3-a's ASSUMED parts) shows up here.
2. `recipe give @a cobblers:entei_boss/ember_sigil` with nobody online answers "no player". With a player online it
   unlocks the recipe. The real check of the recipe's components is the in-game craft.
3. `execute in cobblers:pocket run forceload add -784 -784 -352 -752`, then
   `execute in cobblers:pocket if block -768 94 -764 minecraft:bedrock`. Expect "Test passed": the bedrock course
   sits under the floor at y95. Also check `... if block -768 95 -764 minecraft:bell` (the sunk bell under the
   spot), `... if block -767 95 -764 minecraft:light_gray_concrete_powder` (the ash ring),
   `... if block -768 95 -768 minecraft:cracked_stone_bricks` (the floor at the centre),
   `... if block -777 96 -768 minecraft:stripped_dark_oak_wood` (the west wall) and
   `... if block -768 96 -764 minecraft:air`. Then `forceload remove` the same box. A bell that popped off as an
   item (`execute in cobblers:pocket if entity @e[type=minecraft:item,x=-768,y=95,z=-764,distance=..3]`) means the
   floor bell does not survive the rebuild's order: record it, and drop the bell from `room.decor`.
4. `execute in cobblers:pocket if entity @e[type=minecraft:interaction,tag=cobblers_eb_exit_s1]`: the arch's box
   exists.
5. `scoreboard players get #s1 eb.own` returns 0 after load. `function cobblers:entei_boss/keeper` runs without error.
6. **Spawn, with no player.** Run
   `execute in cobblers:pocket run function cobblers:entei_boss/spawn_at {x:"-767.5",y:96,z:"-763.5",props:"entei level=100 uncatchable"}`
   (with the chunk forceloaded as in step 3). Then
   `execute in cobblers:pocket run data get entity @e[type=cobblemon:pokemon,limit=1,x=-768,y=96,z=-764,distance=..3] Pokemon.Species`
   returns `cobblemon:entei`. This checks that `spawnpokemonat` under `execute in` lands in the pocket, which is
   ASSUMED. Read `Pokemon.Level` (100) and the moves too. **ASSUMED: whether `moves=` accepts the TM moves
   `stompingtantrum` and `stoneedge`.** Repeat with `data/entei_boss.json` `props.farm` verbatim and read
   `Pokemon.MoveSet` (path ASSUMED; adjust to what `data get` shows). Kill it afterwards.

### Needs the owner in game: one player, with `champion_cleared`

7. **X3-a.** Craft the Tower Ash from the recipe's materials. Read the item's tooltip and
   `data get entity @s Inventory`. Shift-click a second one at a brewing stand (it does not go into the fuel slot)
   and open the recipe book (no recipe offers it as an ingredient): the reason the base item changed.
8. **X3-c**, the overworld: eat it in the overworld. It comes back, with "The tower remembers only the Nether. You
   keep the ash."
9. **X3-b, X2-a and X3-look.** Go to the Nether and eat it. You arrive at slot 1 with "The ash is cold on your
   tongue ...". After about 2 s Entei appears with "Something rises from the ash ring. It has been waiting." Over RCON,
   `data get entity <Entei> Tags` should show `cobblers.eb`, `cobblers.eb.s1` and `cobblers.gm`. Note whether it is
   aggressive outside a battle (Fight or Flight). The model must render.
10. **X2-b.** Battle it and catch it. Check that `advancement grant`, the "goes into the ball" line, and
    `eb.clears` = 1 happened.
11. **X2-d.** Click the arch. You are back in the Nether at the block's centre, with "The rain lets you go."
    `#s1 eb.own` is 0.
12. **X3-c**, the lockout: eat a second one at once. It comes back with "The vigil is not over. Try again in about
    this many minutes: 20". To skip the wait without editing data, run
    `scoreboard players reset <player> eb.last` over RCON (a never-entrant is outside the lockout). Setting it to 0
    works only once the world's game time is past 24,000.
12a. **X4-d**, the clock: `scoreboard players set <player> eb.last 2000000000` (above any game time this world has),
    then eat one in the Nether. You are let in, not refused.
13. **X2-c.** Eat one. The Entei should refuse a ball. Faint it in battle. Exactly one drop arrives with "Something
    of the tower's is left in the ash.", and `eb.clears` = 2. It is one of Charcoal, Smoke Ball, Damp Rock, Spell
    Tag, Cleanse Tag or Life Orb (`drops.entries`). Faint nothing else and nothing more arrives.
14. **X4-b.** Next run (reset `eb.last` as in step 12): start the battle and flee. The Entei stays, and you can
    battle again.
15. **X4-a.** Lose to it on purpose. Check:
    - the $600 charge (`cobbledollars query`);
    - you are back at the checkpoint, healed;
    - no recovery claim (`data get storage cobblers_recovery:ledger claims` gains nothing);
    - `#s1 eb.own` is 0 within 1 s.
16. **X4-c.** Next run: start the battle and disconnect. Note whether Cobblemon ends the battle (unknown,
    `docs/research/notes/arena-per-player-opponents.md:371`). Over RCON `#s1 eb.own` should be 0 within 1 s. Log
    back in: you are sent back to the Nether block, with `eb.slot` 0, and over RCON
    `execute if entity @e[type=cobblemon:pokemon,tag=cobblers.eb.s1]` fails (no Entei left in the room).
16a. **X4-c, the relog catch** (needs a player who does not hold `cobblers:entei_boss/caught`, or
    `advancement revoke <player> only cobblers:entei_boss/caught` first): enter, wait for the Entei, log out, log
    back in and throw a ball at once, before the keeper's next pass (20 ticks; a ball already in hand). If the catch
    lands, `cobblers:entei_boss/caught` is granted; the next run's Entei refuses the ball. If the pass kills it
    first, record that the window is too short to matter.
17. **Death in the room**, if step 9 found it aggressive: let it kill you outside a battle. The blackout's death
    path runs, and the slot frees.

### Waits for a second account: never simulated, never reported as passed

18. **Two players at once.** Two players eat Tower Ash in the Nether within a second of each other. They should land in
    slots 1 and 2, each with their own Entei. Neither can see the other. A third and a fourth fill slots 3 and 4, and
    a fifth is refunded with "Every room of the tower is kept by someone else." One player catching does not change the other's mode.
19. **Shared wild battle** (the scope's X5). Not built here: each player fights their own copy, by the owner's
    decision.

## What RCON can verify with no player, and what it cannot

| Can (steps 1-6) | Cannot |
|---|---|
| The pack loads; the rooms' blocks; the arch entity; the macro spawn lands in the pocket at the right level; the property string parses | The recipe's crafted components, eating, the consume trigger, the teleport, the keeper's per-player spawn (it needs a player in the slot), the catch and faint callbacks, the blackout, logout behaviour, the model rendering |

## Results

None. NOT_EXECUTED.

## Limitations

- Balance is untested and is the open problem the scope names (section 4): one level-100 legendary against six.
  Level, moves, lockout and drop weights are placeholders for `trainer-balance-designer` and the owner. The entry
  price is not a placeholder: it is the economy design's.
- `tests/test_entei_boss.py` is the builder's. The independent audit is `tests/test_entei_boss_audit.py` (the test
  author's, on `tests/pocket_sim.py`). Its three defects (review N142: a second catch after a relog, the lockout
  under a clock that went back, a never-entrant refused on a young world) were fixed 2026-10-08 and their strict
  xfails removed; that is a simulator result, not a run.
- `tools/economy_audit.py` runs the Entei checks on the generated pack (`entei_checks`): 0 problems on 2026-10-08,
  "$1800 of Bank value destroyed per sigil eaten; no cash path".
- Game-time lockout stops while the server is down (ASSUMED vanilla).

## Decision

Pending the run.

## Follow-up

- If X2 and X3 pass: Heatran on the same pack, as a second record (option A's rotation), after the owner plays B.
- If `moves=` refuses TM moves: drop to level-up moves in `props`.
- If the components or the food shape fail at load: correct the record from the boot error. Do not guess a second
  shape.
