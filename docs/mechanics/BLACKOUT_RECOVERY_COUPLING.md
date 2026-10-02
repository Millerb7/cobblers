# The blackout charge and the recovery claim: is anything coupled wrongly?

**Diagnosed 2026-10-01. Verdict: no behaviour is wrong.** Four tests are red because they restate the
pre-B10 charge formula, not because the pack misbehaves. This is a design reading, not a test fix: the
assertions should be re-pointed as *relations*, and one guarantee that is currently held by nothing but
those broken tests deserves a contract of its own.

Transcribed by the main session from the diagnosing agent's report. The agent could not write this file
itself: its worktree's complexity guard refused its write twice, it stopped there, and it handed the
finding back. Line numbers are its, against `90b1222`; the conclusions were re-checked against the
suite run that followed (`tests/test_blackout_recovery_pid.py`: 4 failed, all `600 == 200`).

## There is no blackout-to-Mega money coupling

Two separate couplings meet in one test file, and neither is the one the test name suggests.

**1. Blackout and the gulch share one entity tag, and no money.** `tools/blackout_pack.py` exempts a loss
to a victor carrying `cobblers.gm` from making a claim:

```
$execute as $(victor) if entity @s[tag=cobblers.gm] run scoreboard players set #exempt bo.tmp 1
```

The tag's value comes from `data/blackout.json` `claims.exempt_tag`. `tools/gulch_mine.py` contains no
`cobbledollars`, no `bo.lost` and no money arithmetic; its only money-shaped output is its item-drop roll,
and it keeps its own `cobblers.gm_slayer` tag and `gm.*` objectives. The exemption kills the CLAIM - and,
because `hold_money` is gated on `bo.clm matches 2`, which only `recovery/make` sets, it kills the held
money with it - while `blackout/charge` still runs unconditionally. **A player who loses to a gulch Mega
is charged and has nothing held to recover.** That is contract C12, owner `recovery_claims`, consumer
`gulch_mine`, which states it in so many words ("...and still charges the money").

**2. The charge and the claim share one scoreboard, money both ways.** `bo.lost` is the only runtime home
of the amount. `blackout/charge` sets `bo.lost = #charge bo.cfg`, clamps it with `< bo.bal`, and
`charge_apply` removes it. `recovery/hold_money_at` stamps that same `bo.lost` into the pending claim's
`money` by the claim's own id, and `recovery/deliver_one` gives back that **stored integer** - never
recomputed. So taken == held == repaid **by construction**.

## Both are deliberate, and both are written down

C12 in `data/system_contracts.json` states the gulch exemption and that it still charges. The held money is
`money.held_by_wild_victor` and its `_why`, and the generator makes the call site conditional on the flag.
**What is accidental is a third copy of the charge formula inside a claim test.**

## Is any behaviour wrong? No.

`tests/test_blackout_recovery_pid.py` computes its expectation with a local `_ceil_pct`, which is the
**pre-B10 rule**, `ceil(balance x 20%)`: at a balance of 1,000 that is 200. B10 made the charge flat off a
cap - `min(balance, ceil(3000 x 20%))` = 600 - and the pack charges 600. The failing message is
`(600, 200)`: the claim **does** hold 600, equal to `bo.lost`. **The invariant the test exists for - a
claim repays exactly what the charge took - holds.** The gulch exemption branch is not what failed.

Corroboration: contract C12's own test runs the same wild loss over the keeper's real Megas and
**passes**, because it asserts `bo.lost > 0` rather than an amount.

## What to do

1. **Re-point the four as relations**: `claim["money"] == bo.lost`, and `bo.lost > 0`. Delete `_ceil_pct`.
   The AMOUNT is then checked in exactly one place - C15's test, which now exists and pins
   `bo.lost == min(balance, ceil(cap x pct / 100))` across the balance range, independence proved by
   mutating the generator.
2. **Add one contract**: *a wild victor's claim holds exactly what the charge took, and repays it once.* It
   is the guarantee these four tests were really about, and today nothing else holds it.
3. **Reject** separating charge and claim by storing a constant: a charge clamped to a $400 balance would
   then "repay" $600.

This is test-author work, and it is not B10's implementer's to grade. Breaks nothing at runtime. The new
contract adds one `test_every_contract_names_existing_tests` failure until its test is written, as C15 did.

## Not verified

Anything server-side: that a death removes $600 in game (EXP-042), and that CobbleDollars answers the
balance query (EXP-040 covers only the query's result). That no fourth copy of the formula exists outside
the two modules the agent read.
