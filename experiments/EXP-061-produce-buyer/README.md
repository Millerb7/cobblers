# EXP-061: Does the Produce Buyer count, take, pay and cap per leg, and does the bank refuse farm goods?

**Status: NOT_EXECUTED.** Written 2026-10-10 by the builder of `tools/produce_buyer.py` and the bank's AFK exclusion
(`tools/bank.py`, `data/bank.json` `afk_rule`), docs/mechanics/ECONOMY_OVERHAUL.md U1 and U2. Run and graded by
someone else (CLAUDE.md principle 16).

Number: EXP-058 is the highest in this checkout; the brief named EXP-061, which keeps clear of concurrent units that
may take 059 and 060.

## Objective

The bank no longer buys what an unattended farm makes (53 entries left it: `data/bank.json` `base_removed` and
`buys_removed`). Those goods now sell to one dialogue NPC, the Produce Buyer, at Hollin's farm, by the crate, at
$40 a crate with no badges falling to $0 at eight, under a per-player allowance that resets each leg
(`data/produce_buyer.json` `schedule`). The offline checks prove the generated files are well formed and ordered; this
experiment answers what only the game can:

1. Does `clear @s <item> 0` count the matching items **without removing any**? (ASSUMED vanilla behaviour. If it
   removes them, every sale takes the goods at the count step with no payment: **this must pass before install**.)
2. Does a sale take exactly the crate, and only then pay exactly the schedule's price?
3. Does the allowance stop sales at the leg's crate count, and reset when a badge flag is granted?
4. Does the bank, after the new `bank.json`, refuse the removed goods and still buy ore?
5. Does Pasture Loot drop ore from a pastured Pokemon (the `ranch_ore` owner question's premise)?

## Where it runs

- **The staging server and a staging world only**, never `cobblers-10240`. The live-server safety gate (CLAUDE.md)
  applies: port 25565 and the shared lock first; start detached; check the process, not one RCON answer.
- Install: `python tools/reapply.py install` (carries `modpack/config/cobbledollars/bank.json` and
  `build/datapacks/cobblers_produce_buyer`), boot (the NPC class loads only at start), then
  `python tools/reapply.py run --only R18PB` (a partial run: say so in the record). R9AF and R18AF must already have
  run on the staging world (the farm and its stall keeper).
- One player `<p>`, opped for the setup commands only. Every balance read is `cobbledollars query <p>`.

## Steps

0. `cobbledollars reload`. Stand at Hollin's farm: one NPC named "Odile Furrow, Produce Buyer" at **(2065, 135, 5563)**,
   south-east of the stall, facing east. Record whether she stands on the ground with air at feet and head.
1. **Bank (U1).** `give <p> minecraft:melon_slice 10`, `give <p> cobblemon:red_apricorn 5`,
   `give <p> minecraft:raw_iron 10`. Shift + right-click the stall keeper: the Bank lists raw iron at $8 and lists
   neither melon slices nor apricorns. Sell everything it takes: balance B0 -> B0 + 80; the melon and apricorns stay
   in the inventory.
2. Badges: `advancement revoke <p> from cobblers:flag/gym1_cleared` ... through gym8 (or confirm none is held).
   `scoreboard players reset <p> cob_pb_leg`, `scoreboard players reset <p> cob_pb_sold`.
3. **Count without taking.** `give <p> minecraft:wheat 20`. Talk to the buyer, choose the crops crate: the reply
   names 20 of 32; **the inventory still holds 20 wheat**; the balance is unchanged. (Question 1.)
4. **A sale.** `give <p> minecraft:wheat 20` (40 held). Choose the crops crate: 32 wheat leave, 8 stay; the balance
   rises by exactly **$40**; the reply says 39 crates left. `scoreboard players get <p> cob_pb_sold` = 1.
5. **Double submit.** Click the same option twice quickly with 64 wheat held: at most one crate is taken per click
   inside half a second (cooldown 10 ticks).
6. **The cap.** `scoreboard players set <p> cob_pb_sold 40`; with 32 wheat held, choose crops: refused ("That's all
   I can take ..."), nothing taken, balance unchanged.
7. **The reset.** `advancement grant <p> only cobblers:flag/gym1_cleared`. With 32 wheat, choose crops: taken, paid
   **$30**, 29 left. `cob_pb_sold` = 1, `cob_pb_leg` = 1.
8. **Closed.** Grant gym2..gym8 flags. With 32 wheat, choose crops: refused ("Eight badges? ..."), nothing taken.
   Repeat one sale each for a tag crate at badge 0 after a reset: 32 mixed apricorns and 16 mixed berries.
9. **Pasture Loot ore (owner question `ranch_ore`).** In a pasture block, pasture one Steelix (or Aggron) and one
   Sableye with no player near (chunk loaded); after 20 minutes record what dropped. 15% a minute predicts about 3
   drops per Pokemon; whether a drop is a whole roll of the species table is the question.

## Pass

1-8 as stated, with every balance delta exact; any step that takes items without paying, or pays without taking,
FAILS the experiment and blocks install. Step 9 is a measurement, not a pass condition: record the drops for the
owner's `ranch_ore` decision.

## Record

Per step: the command, what the chat said, the balance before and after, the inventory delta. Write it to
`experiments/EXP-061-produce-buyer/results.md`.
