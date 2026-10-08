# EXP-060: Does an arena win pay only the arena's own purse, once?

**Status: NOT_EXECUTED.** Written by unit ARENACAP (2026-10-10), the builder; to be run by the owner or the
integrator on STAGING, and graded by someone other than the builder.

## Question

Heaven's Arena (`tools/arena_runtime.py`, pack `cobblers_arena`) pays its own purse with `cobbledollars give`.
CobbleDollars also pays every NPC-battle win by itself (`CobbleDollarsEventsKt.battleVictory`, any loser whose
`BattleActor.getType()` is `ActorType.NPC`; `NPCBattleActor` is one; read from the jar,
`docs/research/notes/paid-services-and-npc-payouts.md` B2). The pack now takes that automatic credit back:

1. `bout/begin` stores the balance (`cobbledollars query @s`, its command result) in `ar.bal` just before
   `start_battle`, and the tick function stores it again at the start of every tick until the result (revised
   2026-10-08, review N143).
2. `won` (`cd/first`) reads the gain over that baseline. If it is at least `ar.cmin`, the least CobbleDollars can
   credit for that opponent, CobbleDollars has already paid: the gain, at most `ar.cmax`, is removed
   (`cobbledollars remove`) and `#cd_first ar.t` counts it. If it is smaller, CobbleDollars has not paid yet, and
   `ar.claw` is set to 1. Then the arena's purse is paid under `prizes.purse_policy`.
3. When the payout was not there yet, the first line of the NEXT tick (`cd/last`), or `rejoined`, removes the gain
   since the callback. `#cd_last ar.t` counts these. Once one of them has seen a full payout, `#cb_first ar.t` is 1
   for the rest of the boot, and from then on such a look takes at least `ar.cmin`.

Why this timing (javap of `Cobblemon-fabric-1.8.0+1.21.1.jar`, 2026-10-08): the victory fires inside
`PokemonBattle.tick`, which runs from Fabric's END_SERVER_TICK. Both handlers subscribe at the default priority, so
they run back to back. A datapack tick function runs at the START of a tick. The assumption this experiment tests:
player commands and packets are handled BETWEEN ticks, never inside one. If it holds, then:

- with CobbleDollars first, nothing a player does can fall inside the measured window;
- with our callback first, one inter-tick phase falls inside it (the residual, see `known_edges`).

The purse rule (`data/arena_fights.json` `prizes.purse_policy`, numbers from `docs/mechanics/ECONOMY_OVERHAUL.md`
section 6):

- A win at the player's own rank that was never paid before pays in full, once.
- Every other win pays a flat $200, at most 3 paid wins per player per 24,000 ticks of game time.

Does all of that happen in a running server?

## What is already known

- `cobbledollars query @s` read into a score through `execute store result` is how `cobblers_blackout` reads the
  balance (`tools/blackout_pack.py:280`). EXP-040 and EXP-042 record that balance read as verified in game.
- `cobbledollars remove @s $(amount)` is the blackout's charge (`tools/blackout_pack.py:290`), verified in game
  (EXP-042).
- Offline, `tests/test_arena_payout.py` (31 tests) walks the generated functions in a command model, with the
  automatic credit landing either before or after the callback.

## Setup

- Staging only, never the live world. Follow CLAUDE.md "Live server safety": process and port check, then the
  shared lock.
- Install `cobblers_arena` from this build, then **restart**, because NPC classes load only at start.
- One player with `cobblers:flag/gym8_cleared`, arena rank 1 (`scoreboard players set <p> ar.rank 1`) and no
  `cobblers.arena_paid_*` tags (`tag <p> list`).
- A party at or under the level cap that can beat a rank 1 opponent (levels 55-57). Hold the cap check aside if
  needed.
- The CobbleDollars config as shipped: `earnCobbleDollarsFromNPC: true`, multiplier 1.25.
- Enable command feedback for the observer: `/gamerule sendCommandFeedback true`.

## Steps and what to record

Read the balance with `/cobbledollars query <p>` at every point marked **B**.

1. **B0.** Click the floor ring post and win the rank 1 bout. Watch chat during the win.
   - Record every `+N CobbleDollars` line (green, ours) and every `(-N: CobbleDollars' own payout ...)` line (gray).
   - Record which of the two chat lines comes first. A gray line BEFORE the green one means CobbleDollars paid
     before our callback. A gray line AFTER it, one tick later, means CobbleDollars paid after.
   - Record `scoreboard players get #cd_first ar.t`, `#cd_last ar.t` and `#cb_first ar.t`. **This is the
     handler order on this server.** It decides which residual in `known_edges` applies. Repeat it after a restart:
     the order is mod init order.
   - Record any CobbleDollars message of its own.
2. **B1**, about 3 s after the win. Expect **B1 - B0 = 2200** (rank 1's purse). Record `scoreboard players get <p>
   ar.bal` and `ar.cmax`.
3. Win a second rank 1 bout (it is the player's second `advance` win, so still a first). **B2**: expect **B2 - B1 =
   2200**. Record that the tag `cobblers.arena_paid_1_p0_w1` is now held.
4. Set the player to a cleared rank: `scoreboard players set <p> ar.rank 4`, without the Lance advancement. Click
   the floor ring, which offers rank 3. Win one leg. **B3**: expect **B3 - B2 = 200** and a gray clawback line.
5. Win three more legs, starting new runs as needed. **B4**: expect **B4 - B3 = 400**, because only two more repeat
   wins are paid today. Then the gray "used up" line.
6. **Control.** Lose one bout. Expect no gray line and no change to the balance.
7. **Control, outside the arena.** Beat any rctmod route trainer. Expect CobbleDollars' normal payout to arrive and
   stay, because the arena pack touches no other battle.
8. **The windows (needs a second player, Q).** During a rank 1 battle, Q runs `/cobbledollars pay <p> 1000` a few
   seconds before the win. Then P runs `/cobbledollars pay <Q> 1000` during another battle. Expect each win to leave
   B moved by exactly the purse plus or minus 1000: the per-tick baseline has absorbed the transfer. Then, if the
   order is callback-first, Q sends repeated pays across a win (a macro, if one is available). Record how much was
   taken. It must stay within `[ar.cmin, ar.cmax]`.

## Success criteria

- Every arena win changes the balance by exactly the arena's figure: 2200 for a first, 200 for a repeat, 0 once
  the cap is reached. CobbleDollars' random credit is fully removed.
- The route trainer still pays.
- `ar.bal` is reset and `ar.claw` is 0 after each clear-up.
- Step 8: a transfer made before the win's tick is never taken, and what is taken stays within its bounds.

## Failure readings

- **B1 - B0 = 2200 + roughly 5,300-11,000.** The clawback never ran. Check `ar.bal` after step 1:
  - If it is unset, the snapshot macro line failed. Try the blackout's plain-line form.
  - If it is set, `cobbledollars remove` failed.
- **B1 - B0 = 2200 minus something.** Something else credited or took money during the battle.
- **No gray line ever, and B1 - B0 = 2200.** CobbleDollars does not pay a `cobblemon:npc` win. The clawback is then
  harmless, and research note B2 needs correcting.

## Not covered

- Two players at once.
- A disconnect in the tick after a win. Offline, `test_leaving_right_after_a_win_still_takes_a_late_payout_back`
  covers it.
- A server crash in that tick. The second look is then dropped, and this is accepted in `known_edges`.
- The cost of one `cobbledollars query` per player in battle per tick. Watch `/tick query` during step 8.
