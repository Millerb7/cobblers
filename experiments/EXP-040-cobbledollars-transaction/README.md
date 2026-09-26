# EXP-040: Can the 10% blackout charge be read, computed and taken in the same transaction as the item claim?

**Spec question** (`docs/mechanics/DEATH_AND_WIPE.md`, open technical question 2): can the CobbleDollars balance
read and the percentage deduction commit in the same server-thread transaction as claim persistence and inventory
removal? Rule 4 says every blackout loses 10% of current CobbleDollars.

Versions: CobbleDollars 2.0.0 Beta 5.1 (`CobbleDollars-fabric-2.0.0+Beta-5.1+1.21.1.jar`), Minecraft 1.21.1.

## Findings

- **The command tree** (VERIFIED from the jar, `CobbleDollarsCommand`): `/cobbledollars` (alias `/cd`) `query`,
  `give`/`add`, `remove`/`subtract`, `set`, `pay` and `leaderboard`, each on `target(s)`. Every handler returns `int`.
- **A function can read the balance** (VERIFIED on staging, 2026-09-26):
  `execute store result storage cobblers:exp cd_balance int 1 run cobbledollars query <player>` stored **712**, which
  equals the player's balance ("has $ 712"). The scratch key was removed afterwards.
- **So a datapack can charge 10%.** Read the balance into a score or storage, compute a tenth with scoreboard
  arithmetic, and pass it to `cobbledollars remove` through a 1.21 function macro (`$cobbledollars remove @s
  $(amount)`). This is ASSUMED until run. Open detail: how the command reports a BigInteger balance above 2^31, and
  what rounding the charge uses.
- **Transaction.** One function runs to completion within a server tick on the server thread. Nothing else, no other
  player's function and no save, interleaves with it, so the read, compute, claim write, item removal and charge
  cannot be torn by concurrency. There is **no rollback**: if a command fails part-way, earlier commands stand. The
  handler must order its steps and verify, the spec's "remove only after claim persistence succeeds":
  1. write the claim to storage;
  2. re-read it;
  3. remove the items;
  4. charge;
  5. re-query the balance.

## Test (a player online)

1. Macro charge: 10% of a known balance, with rounding checked at 0, 5, 9, 10 and 11.
2. The whole blackout function against a balance, inventory and claim: the charge is once only, even when a
   battle-loss callback and a death arrive in the same incident (spec: one incident ID).
3. Failure injection: make the claim write fail (for example storage path conflict) and confirm nothing is removed
   or charged.

## Result

Balance read: **verified**. Charge by macro and the ordered transaction: not run.
