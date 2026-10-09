# Dungeon catches on the clock: held catches, the fail-safe removal, the anchor, nests

**Status: DESIGN ONLY (content-architect, 2026-10-09).** Nothing here is built, generated or run. It builds onto the
dungeon engine (`tools/dungeon.py`, `data/dungeons.json`, `docs/mechanics/DUNGEONS.md`) **after the owner has played
the Night Shift**, and no removal of any Pokemon is built before every probe in section 12 has passed. It changes four
lines of `DUNGEONS.md` (2.5 and 2.6), each marked there with what changed and why (section 15).

**Evidence.** The mechanism comes from `docs/research/notes/dungeon-catches-on-the-clock.md` (cited as **DC**), which
read Cobblemon 1.8.0's source at the GitLab tag through a summarising fetch and **did not open the jar or run
anything**. Every Cobblemon capability below is therefore at most "VERIFIED name, NOT RUN" and carries DC's label;
section 12 turns each one into a probe. Engine facts are read from `tools/dungeon.py` at this branch's head.

Labels as in `DUNGEONS.md`: **VERIFIED** (source or file read, with citation), **ASSUMED**, ***relayed*** (taken from
another document, not re-measured here, with its source), ***measured*** (read or counted by this unit, 2026-10-09),
***planning*** (a value chosen so the arithmetic can be done; replaced by a timing before it ships).

---

## 1. The question

The owner (2026-10-09, from the brief): "Catching speeds the clock the same way taking resources does. Find a Larvitar
nest and catch ten, and the run gets urgent. Fail to extract and you lose them. Consistent with the existing rule: run
rewards are held until a clean exit, and catches become another held reward. BUT removing Pokemon from a player's
party or PC is the most destructive thing we could build. IT MUST FAIL SAFE. If the system is not certain a Pokemon was
caught in this run, it keeps it. Never delete on a guess." And: "a Beast Ball catch is ANCHORED, kept even on failure.
Every dungeon legendary needs a $5,000 Beast Ball, so the price is already paid. Argue it if you disagree."

So the design must settle: what counts and how it combines with blocks on the ladder; the removal path and every guard;
what the player is told; the anchor; whether a nest can be caught at all under the level cap; and the probes and build
order.

## 2. Findings

| # | Finding | Evidence |
|---|---|---|
| F1 | **A catch cannot be held.** It is in the party or PC before any callback sees it; there is no hold store and no give-from-NBT; a properties-string copy loses the uuid, marks, PP, exp-in-level and more, and makes the default outcome "deleted". Holding intact needs a mod | DC section 3 (VERIFIED absence, not run) |
| F2 | **So "held" must be built inverted**: the catch stays with the player, marked, and is removed only on a certain failure. An escrow's default is *lost* (paid only on a clean exit, `DUNGEONS.md` 9.1); a catch's default is *kept* (taken only on a named failure). This inversion IS the fail-safe property, and it is the one place this design departs from "consistent with escrow" | design consequence of F1 |
| F3 | **Four lines of `DUNGEONS.md` say a catch is kept on failure**, reversed by the owner's rule: `:224-225` ("and any Pokemon caught in the run"), `:266-267` (escrow excepts "a caught Pokemon"), `:283` (chat line 4, "and {caught}"), `:335` (a dead-run return keeps "any catch"). DC found three; `:224-225` is a fourth. Line numbers are as they were before this design's edits (section 15) | Grep, *measured* |
| F4 | `data/dungeons.json:102` (the built death chat) already reads "Kept: everything you mined and picked up." with no catch clause, so the built text needs no reversal | *measured* |
| F5 | **The engine's ends are named functions**, which is what lets failure be classified by cause rather than by absence: a clean exit is `back`/`far` -> `pay` -> `m/end` (`tools/dungeon.py:1021-1034`); a death is `m/died` with `dg.cause` 1 timer, 2 beaten, 3 other, 4 away (`:75-96`, `:914-925`); a move out of the slot is `m/left`, cause 2 if the loss tag is set, else 3 "anything else that moved them" (`:952-962`); a dead run on return is `m/void` -> `m/deadkill` -> death (`:736-749`); and every end passes through `m/end` (`:964-982`) | VERIFIED (read) |
| F6 | `greed/take` gates on `dg.st == 3`, adds 1 to `dg.greed`, calls `greed/rate`, which sets the rate from the ladder fresh each call and only rises because the count only rises (`tools/dungeon.py:884-902`). The bar prints `taken N` from `dg.greed` (`:1227`) | VERIFIED (read) |
| F7 | `dg.run` is the player's run number, `#runs` counts from 1 and is never reused within a scoreboard's life; a freed slot zeroes its run id (`:77`, `:1110-1111`, `:1241-1243`). Whether `#runs` survives a re-export is ASSUMED (DC point 8) | VERIFIED (read); carry ASSUMED |
| F8 | **The level cap refuses a ball at a target strictly over the thrower's cap**, a Master Ball included; one at the cap is caught (`data/level_cap.json:3-5`: built 2026-09-28, **not run in game**). So a nest above the cap cannot be caught at all | *relayed*, `data/level_cap.json` |
| F9 | **A band spans two caps** (band 1 = caps 20 and 25, `data/dungeons.json:74`), and the band is frozen at entry (`DUNGEONS.md` 5.1). A nest catchable by every band-1 entrant must sit at or under the band's lower cap | *measured* |
| F10 | **No rctmod trainer stands in a run** (stands and bosses are `cobblemon:npc`, `DUNGEONS.md` 3.1), so no in-run event raises a player's cap; a level that is catchable at the threshold stays catchable for the run | VERIFIED (design, `DUNGEONS.md:358-359`) |
| F11 | The Beast Ball costs **$5,000** and its counter gate was dropped (`data/markets.json:301`, `price 5000`, `gate null`, *measured*). Its "0.1x otherwise" tooltip is false in the jar, so it catches an ordinary Pokemon at the ordinary rate (`data/key_ball.json:38`, *relayed*) | *measured* / *relayed* |
| F12 | The lake legendary's catch grants a **once-per-player** advancement at `pokemon_captured` (`DUNGEONS.md` 3.7 item 5). Removing that Pokemon would lose a legendary the player can never catch again, unless the advancement were also revoked | VERIFIED (design) |
| F13 | D8 / Q11 "every catch after the Champion" (`DUNGEONS.md:41`, `DUNGEON_PLACEMENT.md:112-120`) was decided about **dungeon bosses and paradoxes** ("every catchable dungeon boss is postgame"). The owner's Larvitar nest at band 1 implies nest catches before the Champion. This design reads D8 as bosses and legendaries only; **owner to confirm** (Q-C1) | read; reading ASSUMED |
| F14 | No code enforces Nuzlocke (`docs/STATE.md:252` "Nuzlocke handling" open); a dungeon is not a Nuzlocke zone (DC section 4) | *relayed* |

---

## 3. The rule

1. **A catch in a live run is a held catch.** "Live" means past the threshold: `dg.st` 3 (clock running) or 4 (sudden
   death). DC recommended 3 only, mirroring `greed/take`; 4 is added because a ball thrown during sudden death is
   certainly this run's, and leaving it out would let a player catch a nest Pokemon in the battle the clock ran out in,
   die, and keep it. (It counts toward greed only at 3, where it can still matter.)
2. **A held catch is the player's, marked, in their party or PC as normal.** It can be used, levelled and fought with
   for the rest of the run.
3. **A clean exit by either rip** (`back`, `far`) makes every held catch of the run an ordinary catch: the mark comes
   off and the ledger forgets it.
4. **A named failure forfeits them**: any death in the run (timer, beaten, fall, lava, drowning, the dead-run kill on
   return) and a loss-return (`m/left` with the loss tag). Each forfeited catch is then removed **only if every guard
   in section 7 passes**. A catch that fails any guard is kept.
5. **Every other end keeps them.** An end the engine cannot name (`m/left` cause 3: moved out of the slot without
   dying or losing, and any end path added later) converts the run's held catches to ordinary ones and logs the end
   for the owner. Failure is classified by an enumerated list of causes, never by "not a clean exit", so a new or
   unexpected way out defaults to keep.
6. **Never at stake, by construction** (never marked, never ledgered, so no removal path can name them):
   - the **dungeon's legendaries** (section 9's anchor), by species;
   - anything not caught with a thrown ball: eggs, trades, gifts, `pokegive`, raid rewards (they never pass
     `pokemon_captured`, DC section 1);
   - catches before the threshold, in the tail, or outside a run.
7. **A catch only speeds the clock.** It counts on the ladder (section 4) and the multiplier holds once reached (D13),
   so releasing or losing a catch never refunds time.

---

## 4. Catches on the ladder

**One combined count:** `n = blocks taken + k x catches`, with **k = 1** proposed, and the ladder unchanged (D13:
x1.25 at 5, x1.5 at 10, x2 at 15, x3 at 20; `data/dungeons.json:49-56`).

- **Why k = 1.** The owner's own number: "catch ten, and the run gets urgent". Ten at k = 1 is x1.5, which `DUNGEONS.md`
  4.3 already calls "a gamble that needs sprinting". And a catch already costs far more clock than a block by its own
  time: the free tier is 4 blocks in 0.5 minutes (`DUNGEONS.md` 4.1, *planning*), about 7.5 s a block, against about a
  minute a catch (***planning***: find it, weaken or throw at full HP, one to three balls; to be timed). A heavier k
  would charge the same choice twice. The weight is `trainer-balance-designer`'s to set; the data carries it
  (`catches.weight`).
- **Scores.** `dg.catch` (this run's marked catches) is separate from `dg.greed` (blocks), and `greed/rate` reads the
  effective count `#eff = greed + weight x catch` instead of `dg.greed`. Both only rise, so the rate still only rises.
- **The bar** (`DUNGEONS.md` 2.2) gains a part: `Rift 18:20 · x1.25 · ~14:40 left · taken 4 · caught 3`. `taken` stays
  the seam's (`tools/dungeon.py:1227`), `caught` shows once above 0.

### Worked: band 1, the Night Shift's numbers, a nest beside the seam

All *relayed* from `DUNGEONS.md` 4.3 unless marked: at the seam after the free tier (4 blocks, n = 4) the clock holds
**21.6** minutes; the rest of the run needs **15.2** real minutes; turning back from there is **1.9** real minutes at
sprint; sprinting the remaining drifts saves **1.0** real minute. Band 1's clock is 29 minutes (`clock_s` 1740,
`data/dungeons.json:74`, *measured*). A catch takes **1.0** real minute (***planning***), charged at the rate in force
while it is made. The nest's place beside the seam is ***planning***: where a nest goes sets its return risk (11).

| Catches (after 4 blocks) | Clock spent catching | Left | Rate after | Finish needs | Outcome |
|---|---|---|---|---|---|
| 0 | 0 | 21.6 | x1 | 15.2 | finishes, 6.4 to spare (the whole slack) |
| 1 | 1.0 (x1) | 20.6 | x1.25 | 19.0 | **finishes, 1.6 to spare** |
| 2 | 1.0 + 1.25 = 2.25 | 19.35 | x1.25 | 19.0 | finishes, 0.35 to spare: no fall beyond the two budgeted |
| 3 | 3.5 | 18.1 | x1.25 | 19.0 | **0.9 short**; sprinting saves 1.25 of clock, so it finishes with about 0.35. A gamble |
| 6 | 1.0 + 5 x 1.25 = 7.25 | 14.35 | x1.5 | 22.8 | cannot finish. Turn back: 1.9 x 1.5 = 2.85, out with 11.5 |
| **10** | 1.0 + 6.25 + 4 x 1.5 = 13.25 | 8.35 | x1.5 | 22.8 | **cannot finish. Turn back: 2.85, out with 5.5.** "Catch ten and run" |
| 11 | 14.75 | 6.85 | x2 | 30.4 | turn back at x2: 3.8, out with about 3 |

**What it says.** One catch is affordable; two or three are the same gamble as ten blocks; **ten catches is "take them
and run"**: the player gives up the third stand, the boss and the bundle, and walks out with ten Larvitar and the first
two stands' escrow. That is the owner's "urgent": the run's shape changes at the nest. Most of a catch's cost is its own
time, and the multiplier is what makes the return a race rather than a stroll. At 0.5 minutes a catch (quick throws),
ten catches still cannot finish the boss (6.6 of clock spent, and x1.5 needs 22.8 of the 15.0 left). At band 6 (*relayed*
4.3: 27.6 left at the seam, 20.2 needed after), two catches leave about 0.1 to spare, so the nest, the legendary
(about 6 minutes) and greed exclude each other there too.

**The stake is the way back.** A ten-catch player beside the seam walks back past two open gates. If the nest sits past
the parkour or deep in the spine, the return crosses something that can kill or cost falls, and the stake is real. The
nest's place is the lever (11).

---

## 5. Marking a catch: the catch path

Mechanism rung: **Cobblemon native** (the `pokemon_captured` callback, datapack marks, the store MoLang functions) plus
**datapack functions**. No mod, no new dependency.

1. **Callback** `data/cobblemon/callbacks/pokemon_captured/cobblers_dungeon_catch.molang` (a `cobblers_` filename, the
   repository's convention). It reads the species identifier, as `tools/entei_boss.py:681-687` does, and **returns at
   once for an anchored species** (the generator emits the anchor list as string compares; section 9). Otherwise it
   runs `execute as <player uuid> at @s run function cobblers:dungeons/catch/note {pid, sp, lv}` with the Pokemon's
   uuid (`q.pokemon.id`), species and level, through a macro (the shape `tools/blackout_pack.py:548-562` uses for `pid`).
2. **`catch/note`** (mcfunction, as the player), every step a gate whose failure leaves the Pokemon unmarked and kept:
   1. the player carries the run tag `cobblers.dg_run` (`data/blackout.json:215`) and `dg.st` is 3 or 4;
   2. the pid is not already in the run's ledger (a second callback for one catch is a no-op);
   3. the run's held catches are under the data's per-run ceiling (`catches.max_per_run`, the nest's population); a
      catch past it is kept unmarked and logged, since a run cannot legitimately produce it;
   4. **append the ledger entry first** (section 6);
   5. if `dg.st` is 3: add 1 to `dg.catch` and call `greed/rate`;
   6. **then mark**: `runmolang` as the player finds the Pokemon by uuid in the party, else the PC, and calls
      `add_marks('cobblers:rift_held')`. Marking from the function by uuid means no answer has to be read back into
      MoLang (DC's tag read-back is not needed);
   7. the actionbar line (section 8).
3. **Order and failure.** Ledger first, mark second. A ledger entry with no mark is kept at removal (guard G5); a mark
   with no ledger entry is never named by removal. Every failure of this path (no callback, a MoLang error swallowed by
   `runmolang`, a macro that does not parse) leaves the Pokemon unmarked or unledgered, so **the catch path can only
   err toward keep**.
4. **The mark** is a datapack mark JSON, `chance` 0 so it is never rolled (DC section 1): name "Rift-held",
   description "Caught in a rift. Lost if you fall there; yours when you leave by a rip." Its being visible in the
   summary screen is the point (the player sees what is at stake) and is ASSUMED until CP1/CP14.

---

## 6. The ledger: data model

**Command storage `cobblers:dg_catch`**, one compound per player keyed by the engine's player number `dg.id`
(`tools/dungeon.py:74`), so no player name or uuid is written to our files:

```
p<id>: {
  held: [ {run: <int dg.run>, pid: "<uuid>", sp: "<species id>", lv: <int>} ... ],   # this run's, live
  owe:  [ {run, pid, sp, lv, cause: <1..4>} ... ]                                      # forfeited, awaiting the reaper
}
```

**Scores:** `dg.catch` (this run's held catches, for the ladder and the bar), `dg.owe` (entries in `owe`, so the keeper
selects players to reap by score, not by storage), and `#catch_live dg.cfg` (the runtime switch, section 7, G0).

**The log**, `cobblers:dg_catch_log`, bounded to the last 200 entries: `{who: <id>, run, pid, sp, lv, verdict, why}`
for every catch resolved by any path. This is the owner's audit trail and the dry run's output.

**Transitions** (each in exactly one generated function):

| From | To | Where | What happens to the Pokemon |
|---|---|---|---|
| (new) | `held` | `catch/note` | marked |
| `held` | cleared | clean exit (`catch/keep_all`, called by `back`/`far` after `pay`) | mark removed |
| `held` | `owe` | `catch/forfeit`, called only by the named failures (section 7) | nothing yet |
| `held` | cleared | `catch/settle`, called by `m/end` (any end not already resolved) **and at the threshold of the next run** (`slot/s<k>/start`) | mark removed: kept |
| `owe` | cleared | the reaper, per entry, after its guards | removed, or kept with a reason |

`catch/settle` at the next threshold is what makes a stale entry harmless: a `held` entry left by a crash or a lost
clear can never be swept into a later run's failure, because before any new catch can be ledgered, everything older
has been converted to kept. That closes DC's run-number-reuse risk (F7) without depending on `#runs` surviving a
re-export.

---

## 7. How a run ends for its catches, and the removal path

### 7.1 Which ends forfeit

| End (engine function, `tools/dungeon.py`) | `dg.cause` | Catches |
|---|---|---|
| `back` / `far` at `dg.st` 3, clock >= 1 (`:1021-1034`) | none | **kept** (`catch/keep_all`) |
| `m/died`, the timer's `kill @s` | 1 | **forfeit** |
| `m/died` after a loss (`dg.lost`) | 2 | **forfeit** |
| `m/died`, a fall, lava, drowning or any other death | 3 | **forfeit** (a death is a certain failure) |
| `m/died` after `m/deadkill` (the dead run on return, 2.6) | 4 | **forfeit** |
| `m/left` with the loss tag (the blackout's return after a lost battle) | 2 | **forfeit** |
| `m/left` without it: moved out of the slot alive, not beaten | 3 | **kept**, and logged `UNKNOWN_EXIT` for the owner; probe CP11 closes any route out at the door rather than here |
| `m/void` before the threshold (`dg.st` 1-2) | none | nothing to settle: no catch can be held before the threshold |
| any end added later that reaches `m/end` without calling `catch/forfeit` | any | **kept** (`catch/settle`) |

`catch/forfeit` is called in `m/died` and `m/left` **before** `m/lines`, so the death lines can say how many catches
are at stake, and before `m/end`, so `catch/settle` finds nothing left in `held`.

### 7.2 When the reaper runs

**Never in the pocket and never at the moment of death.** The reaper runs as the player, on a keeper pass where all of
these hold:
- `dg.owe >= 1`;
- the player is online and alive, outside `cobblers:pocket` (`dg.pk` tag absent), with `dg.st` 0 and the run tag's
  tail finished (`dg.tail` 0). In practice that is the end of E1's tail: 100 ticks after the respawn
  (`data/blackout.json:217`, *measured*), in the overworld. It is added to `m/tail` just before the blackout's
  `run_tail_end`, and repeated each pass for a player whose reap was deferred.

A player offline when their run failed (2.6) is reaped on their first pass back, after the dead-run kill and the
respawn. Until then, and forever if they never return, the catches are kept: **MoLang cannot reach an offline player's
stores** (DC section 4), so the waiting is not a choice but it is the right default.

`door_click` refuses a new run while `dg.owe >= 1` ("The rift is still settling your last run."), checked before the
sigil, so no entry from one run is ever pending while another is live. Since the reaper resolves every entry it can
reach on its first pass and defers only for a battle, the refusal lasts seconds.

### 7.3 The reaper, per entry, every guard in order

The reaper walks `owe` (the macro-recursion pattern the repo already uses for lists), **PC-held entries first, party
entries second** (so the last-Pokemon guard bites as rarely as possible). For each entry it runs one `runmolang` as the
player, whose verdict comes back by calling `catch/verdict {code}`. **Any guard that fails, errors or cannot be
evaluated ends in KEEP**: the mark comes off, the entry is cleared, the verdict is logged and told.

| Guard | Test | If it fails |
|---|---|---|
| **G0 switch** | the pack was built with `catches.removal: "live"` **and** `#catch_live dg.cfg` is 1 | REPORT: everything below runs, nothing is removed, the line says "would have" (section 8). In a `report` build the string `remove_by_id` **does not exist in the pack** (V-C5) |
| **G1 sanity ceiling** | the player's `owe` holds no more entries than `catches.max_per_run` for that run | ANOMALY: **all** of that player's `owe` kept, logged loudly, the owner told. A count no run can produce means a bug, and a bug must not delete |
| **G2 run** | the entry's `run` equals the failed run it was forfeited for (both written by `catch/forfeit`) | KEEP (`RUN_MISMATCH`) |
| **G3 found** | `q.player.party.find_by_id(pid)`, else `q.player.pc.find_by_id(pid)`, is not 0; the store it was found in is remembered | GONE: nothing to take (traded, released, or in a store we do not search, such as a pasture or a breeding mod's: "our list is not the world", and the unsearched ones fail toward keep). Cleared |
| **G4 owner** | it was found in **this player's** stores (G3 searches no other) | n/a, by construction |
| **G5 mark** | `t.p.has_mark('cobblers:rift_held')` | KEEP (`UNMARKED`): the second key is missing |
| **G6 species** | the species identifier equals the ledger's `sp` | KEEP (`CHANGED`): it evolved or was altered. See 7.4, evolution |
| **G7 battle** | `q.player.in_battle == 0` | DEFER: the entry stays in `owe` and the next pass retries |
| **G8 last Pokemon** | if found in the party, `party.count >= 2` | KEEP (`LAST`): **a party is never emptied** |
| **G9 held item** | if `held_item` is not empty: give it to the player, `remove_held_item`, then read `held_item` again | KEEP (`ITEM`) if it is not empty after, or if the give cannot be confirmed (CP3, CP12) |
| **G10 remove** | `remove_by_id(pid)` on the store G3 found it in, then `find_by_id(pid)` on **both** stores is 0 | FAILED: logged loudly, the owner told; the Pokemon is wherever the store left it and the entry is cleared, never retried |
| — | all passed | REMOVED: logged, and listed to the player |

What is deliberately **not** done:
- **No rescue move.** DC proposed moving an unmarked Pokemon from the PC into the party so a catch-only party can still
  lose its catches. That is a second write to the player's stores for a case that needs the player to have boxed their
  whole team, which the pocket's adventure mode and lack of a PC make hard (ASSUMED no portable PC in the pack, CP17).
  The design keeps the last party Pokemon instead: a bounded dodge (one Pokemon per failed run, after a failed run's
  full costs) is cheaper than a second destructive write.
- **No slot commands** (`takepokemon`, `pctake`): a slot is a guess (DC section 2). V-C6 forbids them in the pack.
- **No party diff**: it cannot tell a run catch from a gift, a hatch or a trade (DC section 4, approach C).
- **No change to OT, nickname or any field the player sees** as a key (DC section 1).

### 7.4 The cases the brief names

| Case | What happens | Safe side |
|---|---|---|
| **Held items** | Returned to the player first and verified gone (G9); otherwise kept. `remove` would otherwise delete the item with the Pokemon (DC section 2) | keep |
| **A party never emptied** | G8. The only party Pokemon is never removed | keep |
| **Full party at capture** | `party.add` overflows to the PC (DC section 4); G3 searches both | correct |
| **Party and PC both full at capture** | Cobblemon stores the Pokemon nowhere (DC section 2, a Cobblemon behaviour). G3 finds nothing: GONE. The callback still fired, so the ledger has an entry for a Pokemon that does not exist; nothing is removed | n/a |
| **The PC** | found by uuid in any box (G3) | correct |
| **Offline at failure** | `owe` waits; reaped on the first pass back; kept forever if they never return (7.2) | keep until certain |
| **A run that died while away** | `m/deadkill` -> death -> `m/died` cause 4 -> forfeit -> respawn -> tail -> reaper. The loss lines say the rift closed while they were away (section 8) | as designed |
| **Server crash** | The ledger (world storage) and the Pokemon (player data) save on different schedules. Entry without Pokemon: GONE. Mark without entry: never named. Entry still `held` after a crash: settled to kept at the next threshold (6). A crash between `forfeit` and the reaper: the `owe` entry is reaped on return, which is correct. No skew removes a Pokemon the run did not forfeit (CP7) | keep |
| **Evolution in the run** | The same object evolves in place and marks survive (DC section 4, NOT RUN). G6 keeps it (`CHANGED`). This is a deliberate **laundering by evolution**: it costs an evolution item or a level-up evolution under the cap, which a nest at cap-1 to cap-3 rarely allows. Lifting G6 so evolved catches are also removed is the owner's call (Q-C4) **after CP5 proves the uuid survives evolution**; until then a changed species is uncertainty and uncertainty keeps. Shedinja's `clone()` is marked but never ledgered: kept | keep |
| **Trade / laundering** | A traded catch is in the partner's party, where G3 never looks: GONE, the partner keeps it, still marked (the mark is cosmetic for them). Solo play (D16) cannot trade, and a trade needs the second account even to test (XD8). Accept it for solo; with co-op, decide between accepting "friends sharing" and `tradeable=false` while held (CP6 must first show it blocks a trade) (Q-C3) | keep |
| **Nuzlocke** | No code enforces it (F14); a forfeited dungeon catch is a removal, never a faint, so nothing touches a Nuzlocke player's dead box or any unledgered Pokemon. Whether a dungeon catch counts as a Nuzlocke catch is the owner's (Q-C5) | n/a |
| **Released in the run** | GONE at the reaper | n/a |
| **Sent out, ridden or on a shoulder at the reap** | `remove` recalls first (DC section 2); CP15 proves it for each | probe |
| **Pasture or a breeding mod's daycare** | not searched: GONE, kept (CP16) | keep |
| **A catch in the tail, before the threshold or outside a run** | never marked (rule 1) | keep |

---

## 8. What the player is told

**Before.** The entry room's board (`DUNGEONS.md` 2.4) gains:
- "What you catch past this board is held by the rift. Leave by a rip and it is yours. Die here and the rift takes it
  back."
- "Each catch counts as one block taken" (the weight, from the data).
- "A legendary you catch here is yours whatever happens." (only where the dungeon has one)

A nest's own board, beside it, repeats the ladder and "Every catch tightens the rift."

**During.**
- On a held catch, the actionbar: "Held by the rift: {species}. Get out to keep it." On a catch that tips a rung, the
  ladder's own line follows ("The rift tightens. Time runs x1.25.", `greed/rate`).
- The bar: `· caught N` (section 4).
- The summary screen shows the mark "Rift-held" (CP14).
- On an anchored catch: "{species} is yours. The rift cannot take it back."

**After a clean exit.** "Out of the rift. {n} catches are yours now." (only if n >= 1). The marks are gone.

**After a failure** (the `DUNGEONS.md` 2.5 chat lines, in order, line 4 changed by this design):
1. "Your items are all still yours. Nothing in a rift keeps them."
2. "The {money} is gone for good. No one in the rift is holding it."
3. "Lost with the run: {held_summary}." or "The run had earned nothing yet."
4. "Kept: everything you mined and picked up." then, if any catches were held: "The rift is taking back {n} catches."
5. the lockout line.

Then, from the reaper, one line per entry and a closing count. Draft (for `trainer-balance-designer` to tone):
- REMOVED: "Lost to the rift: {species} Lv{lv}." and, if G9 moved an item, "(its {item} is in your bag)".
- GONE: "Kept: {species}. It is not with you to take."
- CHANGED: "Kept: {species}. It is not what you caught any more."
- LAST: "Kept: {species}. The rift will not leave you with no one."
- ITEM, RUN_MISMATCH, UNMARKED, ANOMALY, FAILED: "Kept: {species}." with no reason given to the player; the log carries
  the reason and the owner is told for ANOMALY and FAILED.
- REPORT mode: "The rift would have taken back: {species} Lv{lv}. This time it let you keep it." The soft-launch
  wording (section 13, step 7).
- A dead run on return prefixes "The rift closed while you were away." (`data/dungeons.json:105`).

Species names in text use the species' translation key so the client renders its own name (the key format is ASSUMED,
CP13); the fallback is the identifier, capitalised.

---

## 9. The Beast Ball anchor: agreed, expressed as a species list rather than a ball check

**Agree with the owner: a dungeon legendary is kept on failure.** Three reasons, the third the strongest:
1. **The price is paid.** A Beast Ball is $5,000 (F11, *measured*), the key-ball refuses every other ball at a tagged
   boss (`data/key_ball.json`, D7), and the band-6 run already cost a Rift-Black Sigil ($1,708 bank value, about 72
   minutes' gathering, *relayed* `DUNGEONS.md` 7.4).
2. **It is the likeliest catch to die after.** The lake's battle is 40 blocks down a flooded shaft (`DUNGEONS.md` 3.7);
   drowning on the way up after the catch is a named risk (L2, B3). Deleting a legendary for a drowning is the
   outcome the owner most wants to avoid.
3. **It is once per player** (F12). Removing it loses a Pokemon the player can never catch again, unless the removal
   also revokes the advancement: a second destructive write tied to the first. Anchoring removes the question.

**Where I differ: anchor by species, not by ball.**
- **A ball anchor sells insurance.** A Beast Ball catches an ordinary Pokemon at the ordinary rate (F11) and its counter
  gate is gone. Under "any Beast Ball catch is kept", $5,000 anchors a Larvitar. At band 1 that is more than a whole
  leg's income ($4,033 in leg 1, `DUNGEONS.md` 7.4 from `data/markets.json:26-27`, *relayed*), so it is rare there,
  but by band 6 ($68,505 a leg, same source) a player could insure a nest's best catches. That dilutes the stake the
  owner asked for, and the owner's words were "dungeon legendary".
- **A species anchor is an absence.** The callback returns before `catch/note` for any species on the dungeon's anchor
  list, so the legendary is never marked and never ledgered and **no removal path can name it**. That is stronger than
  any check at removal. The ball adds nothing: a tagged boss can only be caught by a Beast Ball, and if the key-ball
  ever failed and a Master Ball caught it, it would still be anchored. Wrong, if at all, toward keep.
- **The anchor list** is generated, never hand-kept: each dungeon's lake species, every band-6 boss catch species
  (`DUNGEONS.md` 8: Yveltal, Dialga), and every species in `data/key_ball.json` `bosses`. V-C1 fails if a nest species
  is on it or a catchable dungeon legendary is not.
- **An anchored catch does not count on the ladder.** Its leg already costs about 6 minutes (`DUNGEONS.md` 3.7), and
  counting it would route it through the catch path the anchor exists to keep it out of.

**The abuse case: enter only to Beast-Ball the legendary, then die.** It gains nothing a clean exit would not.
- The lake is band 6 only, Dive-gated, once per player, mid-spine after the seam (`DUNGEONS.md` 3.7, 11.1).
- The player pays the sigil, the Beast Balls, the clock and, by dying, the $600 and the run's escrow, then the lockout.
- Walking back to the back rip after the catch gets them the same legendary without the $600, the lost escrow or the
  death. **Dying is strictly worse than leaving**, so the anchor creates no incentive to die. What it creates is the
  run shape "come for the legendary, skip the boss", which `DUNGEONS.md` 4.2 already designed ("the legendary or
  greed, rarely both").
- The only thing dying saves is the walk back. The death costs $600 and the escrow, which buys nothing.
- **Verdict: not an abuse.** No guard is needed.

---

## 10. Options considered

| Option | Rung | Blast radius | Multiplayer | World-critical | Verdict |
|---|---|---|---|---|---|
| **A. Mark + per-run ledger + remove by uuid on a named failure, behind G0-G10, report mode first** | native + datapack | One function can remove a Pokemon, behind 10 guards and two switches | Per player; trade launders (accepted solo) | none new | **Recommended** |
| B. Hold the catch and re-give on a clean exit | native (lossy) | Every catch deleted by default; a crash or a lost macro is a permanent loss; the copy loses uuid, marks, PP (F1) | stuck while away | none | Rejected: its default is "deleted" |
| C. Diff party and PC before and after | datapack | Deletes gifts, hatches, trades | worse in co-op | none | Rejected: deletes on a guess |
| D. `takepokemon` / `pctake` by slot | native command | Removes whatever is in the slot | n/a | none | Rejected: a slot is a guess |
| E. Catches count, nothing is ever removed | native + datapack | Nothing destructive | trivial | none | **The fallback if any removal probe fails**: the ladder half ships alone, and the board says catches are kept |
| F. A custom Fabric mod that holds catches intact | custom mod (last rung) | New code in the capture path | needs its own sync | a new dependency every client and the server carry | Not proposed: A is unproven, not disproven (principle 5) |

---

## 11. Nests in dungeons: catchable by construction

**What a nest is** (the owner's standard, 2026-10-09, and the Ursaluna den as the model): a creature, a place that suits
it, and a reason meeting it early is a mistake. In a run, it is a new **optional leg**, distinct from the den
(`DUNGEONS.md` 3.6):

| | Den (3.6, unchanged) | Nest (new) |
|---|---|---|
| Pokemon | 4, `uncatchable`, fought for drops | the young, **catchable**, the population is the run's ceiling (`catches.max_per_run`) |
| Pays | the species' own drops, real items, kept | the catches, **held** (section 3) |
| Level | cap-2 to cap-1 | **at or under the band's lower cap** (below) |
| Spawned | by macro on entering its box (Entei's farm pattern) | the same: by macro, per member, at the band's level, carrying the claims exempt tag |

**The catchable band.** The level cap refuses a ball at a target strictly over the thrower's cap (F8), the band spans
two caps (F9) and nothing in a run raises a cap (F10). So the nest's young spawn at **(band's lower cap - 3) to (band's
lower cap - 1)**: band 1 at 17-19 (caps 20, 25), band 2 at 27-29, band 3 at 37-39, band 4 at 47-49, band 5 at 57-59,
band 6 at the species' sensible top. Every entrant of the band can catch every one of them for the whole run, and a
nest above the cap, uncatchable by the cap's own rule, cannot be authored (V-C3).

**The species follows the band.** `spawnpokemonat` does not evolve a Pokemon to match its level (ASSUMED), so a
level-97 Larvitar is possible and wrong. A nest record names its species per band: Larvitar at bands 1-2 (cap 20-35),
Pupitar at 3-4, Tyranitar at 5-6, with the evolution levels taken from the species data by the balance designer (not
asserted here).

**Where the danger comes from.** Not from level, since a run scales. It comes from three things:
- **the clock**: section 4's arithmetic, so ten catches is "take them and run";
- **the place on the spine**: a nest past the parkour or deep in the spine makes the way out cross something;
- **optionally, the parent**: one adult over the cap, the "big ones at its focal points" the owner welcomes (STATE
  "Wild Pokemon above the cap are welcome"). The cap refuses a ball at it, and a fight with it can end the run and
  forfeit every catch, which is "meeting it early is a mistake" in a scaled place.

`trainer-balance-designer` owns the species, the count, the levels and whether a parent stands. `world-content-dev`
owns the nest's place on the spine.

**Spawning.** By macro, as the den's are, and not through `data/spawns.json`. A spawn table fixes its levels, not per
player, and the pocket's `the_void` biome is meant to spawn nothing (untested, `DUNGEONS.md` 9.3). This is a
deliberate exception to the wave rule that spawns go through the spawn system; the owner should confirm it (Q-C6).

**Pre-Champion catches.** This assumes D8 covers bosses and legendaries only (F13, Q-C1). If the owner meant every
dungeon catch, nests open at band 6 only and section 4's band-1 arithmetic is moot.

---

## 12. Probes: nothing that removes is built before all of these pass

All run on staging, never the live world, one player unless marked, from a **staging-only probe pack** EXCLUDED from
the build with its reason (the arena probe pack's precedent, commit `0428b2e`). Each is a row in one new experiment
(`EXP-NNN-dungeon-catches`, the next free number), designed by the builder, run by the main session, graded by
`qa-reviewer`. CP1-CP9 are DC's nine unverified points, in DC's numbering.

| Probe | Proves | Pass |
|---|---|---|
| **CP1** | `pokemon_captured` fires for a catch in battle and out; `add_marks('cobblers:rift_held')` returns 1 for our namespace's mark; the mark survives a relog, a PC move, a restart and an evolution | all four survivals observed with `has_mark` |
| **CP2** | `runmolang` as the player evaluates `party.find_by_id`, `pc.find_by_id`, `remove_by_id`, the `== 0` test on a struct and `!=`; the client's party and PC refresh after a removal. **Run on a throwaway Pokemon given by `pokegive` to a throwaway test account or a disposable staging world** | each returns as expected; the client shows the removal without a relog |
| **CP3** | The held-item chain: read `held_item`, give it, `remove_held_item`, read again empty | the item is in the inventory and the Pokemon holds nothing |
| **CP4** | `party.count` reads the party's size (the G8 test) | correct for 1, 2 and 6 |
| **CP5** | Evolution keeps the uuid and the mark; a Shedinja clone is marked but has a new uuid | uuid equal before and after |
| **CP6** | Whether `tradeable=false` blocks a trade, and the `trade_event_post` context. **Needs the second account (XD8)**: deferred to co-op | blocked or not, recorded |
| **CP7** | Crash skew: kill the server between a catch and a save, both orders; then fail the next run | nothing removed that the run did not forfeit |
| **CP8** | `#runs` and `dg.run` across a re-export (`tools/carry_players.py`) | the counter carries; if not, 6's threshold settle still holds, and the probe records it |
| **CP9** | The level cap and the nest band: a band-1 player at cap 20 catches a level-19 nest Pokemon; a level-21 one breaks free (the cap's own proof, `level-cap-catch-block.md` "Smallest proof", run first) | as stated |
| CP10 | A function called by `q.run_command` from a callback can itself run `runmolang` (the nested call in 5.2.6) | the mark is added |
| CP11 | Every way out of the pocket that is not a rip or a death: Waystones warp items, ender pearls across the slot edge, any `/home`-like command the pack has | each is listed; any that works is refused at `door_click` or swept, never handled by forfeiting |
| CP12 | `give_item` with a full inventory: does it drop, fail or vanish | recorded; G9 confirms the give or keeps |
| CP13 | A species translation key in a `tellraw` renders the name | rendered |
| CP14 | The mark's name and description render in the summary screen without a client pack, and adding it does not make it the Pokemon's displayed title | rendered; no title change |
| CP15 | `remove_by_id` on a Pokemon sent out, ridden, and on a shoulder: recalled, no ghost entity | clean in all three |
| CP16 | A Pokemon in a pasture (and the breeding mod's daycare, if it moves Pokemon) is or is not found by `pc.find_by_id` | recorded; if found, a pastured Pokemon is kept by a guard added then |
| CP17 | Can a player reach a PC in a run (a portable PC item or mod)? | recorded: this decides whether G8 needs DC's rescue |
| **CP-DRY** | **The removal dry run.** The full engine with `catches.removal: "report"`: fail runs by each cause in 7.1 (timer, beaten, fall, the dead run on return, loss-return), plus a clean exit, an `m/left` cause 3, a held item, a one-Pokemon party, an evolved catch, a released catch and a catch with both stores full. Before each, the probe's script writes its **expected verdict list independently** (from the scenario, not from the ledger) | the log's verdicts equal the expected list, entry for entry; **zero Pokemon removed** (party and PC uuids before and after are equal); every "would have" line is the one expected |

**CP-DRY is passed only with zero removals.** It is the gate to step 8 and is re-run after any change to the catch
functions.

---

## 13. Build steps (ordered; one experiment or task each)

Costs are ***estimates***, in the repository's measured terms (CLAUDE.md: a narrow follow-up 2.6M, a full builder about
4M; DC's own estimate 2.6M + 3M). None was measured for this unit.

| # | Step | Agent | Cost (estimate) |
|---|---|---|---|
| 0 | Owner decisions Q-C1 to Q-C6 (below) | the owner | none |
| 1 | The probe pack and EXP for CP1-CP5, CP7-CP17 and the CP-DRY harness (report mode only; the pack contains no `remove_by_id` except in CP2/CP15's own throwaway-account probe functions, which are EXCLUDED from every build) | `minecraft-systems-dev` | ~2.6M |
| 2 | Run the probes on staging; `qa-reviewer` grades. **Stop here and redesign if CP1, CP2, CP3 or CP4 fails** (option E ships instead) | main session; `qa-reviewer` | main-session time; ~0.6M review |
| 3 | `data/dungeons.json` `catches` block: `removal: "report"`, `weight`, `max_per_run` per nest, the mark's text, the messages, the anchor sources; the mark JSON | `minecraft-systems-dev` | in step 4 |
| 4 | The engine: the callback, `catch/note`, the combined ladder, the bar part, the board lines, `keep_all`, `forfeit`, `settle`, the reaper with G0-G9 and the REPORT branch, the log, the `door_click` refusal, a re-apply-free pack (functions only) | `minecraft-systems-dev` | ~2.6-4M |
| 5 | Validators V-C1 to V-C8 (below) and tests, including **generator mutations** (delete each guard line in the generator; the audit must fail) | `test-author` **on opus** (escalation rule 1: it can destroy a player's Pokemon) | ~3M |
| 6 | CP-DRY on staging | main session; `qa-reviewer` grades | main-session time; ~0.6M |
| 7 | **Soft launch in report mode** on the live server: the owner plays the Night Shift with catches counted and "would have" lines, nothing removed. The log is the evidence of what live removal would have done | main session (install); the owner plays | small |
| 8 | **The owner flips** `removal: "live"` in the data (a rebuild) and sets `#catch_live` to 1 (a command). V-C5 refuses `live` unless `catches.proofs` names the passed EXP rows | the owner; main session applies | small |
| 9 | Nests: species, counts and levels per band (`trainer-balance-designer`), the place on the spine (`world-content-dev`), the spawn macro and its probes (`minecraft-systems-dev`) | three agents | ~4M a builder; balance ~1M |

Before step 4: the four `DUNGEONS.md` lines are already pointed here (section 15). After step 8: `ADR-008` should
record the removal path as a constraint on future dungeon work (a proposal for the owner then, with CP-DRY and the
soft-launch log as its evidence; not proposed now, because the evidence does not exist yet).

### Validation (for `test-author`; `tools/validate_data.py` and an independent audit)

- **V-C1** the anchor list is exactly the union of each dungeon's lake species, every band-6 boss catch species and
  `data/key_ball.json` `bosses` species; no nest species is on it.
- **V-C2** `weight` is a positive integer; `max_per_run` equals the nest's spawned population per member per run.
- **V-C3** every nest level per band is at or under that band's **lower** cap (`data/dungeons.json` `bands[].caps`).
- **V-C4** the generated pack calls `catch/forfeit` only from `m/died` and `m/left`'s loss branch, and `catch/settle`
  from `m/end` and every slot's `start`; every function that reaches `m/end` is enumerated and none forfeits by
  absence.
- **V-C5** in a `report` build, `remove_by_id` occurs **zero** times in the pack; in a `live` build it occurs in
  exactly one function, `catches.proofs` is non-empty, and that function holds G1-G9's tests before the call, in order
  (audited from the generated text, and proven by mutating the generator: drop any guard, the audit fails).
- **V-C6** no `takepokemon`, `pctake`, `apply('ot=`, or party diff anywhere in the pack.
- **V-C7** `remove_by_id` is unreachable from any callback file (only the keeper's reaper calls it).
- **V-C8** the reaper never runs in the pocket: its only caller is gated on the `dg.pk` tag absent and `dg.st` 0.

A contract in `data/system_contracts.json`: the blackout's run tag and tail (E1) are what the reaper's timing relies
on; a change to `tail_ticks` or the tail's end must keep the reaper outside the pocket.

---

## 14. Questions for the owner

- **Q-C1. D8's reach.** Read as bosses and legendaries only, so nests are catchable at every band (recommended, F13).
  Or every dungeon catch after the Champion, so nests open at band 6 only.
- **Q-C2. The weight.** One catch counts as one block (recommended, section 4).
- **Q-C3. Trades in co-op.** Accept "friends sharing" (recommended for now: solo has no trades), or `tradeable=false`
  while held, if CP6 shows it blocks a trade.
- **Q-C4. Evolution.** Keep an evolved catch (recommended until CP5 passes), or remove it too once CP5 proves the uuid
  survives.
- **Q-C5. Nuzlocke.** Does a dungeon catch count as a Nuzlocke catch? (No code enforces Nuzlocke today.)
- **Q-C6. Nest spawns by macro, outside `data/spawns.json`** (recommended: per-player band levels need it), as the den
  and Entei's farm already do.
- **The anchor (section 9):** agreed. My one change is that the anchor is the dungeon's legendary species and not any
  Beast Ball catch; say if you meant the ball.

---

## 15. Changes made to `DUNGEONS.md` (2026-10-09)

Each changed line in `DUNGEONS.md` keeps its old wording, marked "Was (2026-10-08)", beside the new one, with a pointer
here:
- 2.5 "What is kept" (`:224-225`): a run catch is held, not kept; the dungeon's legendary is kept.
- 2.5 Escrow (`:266-267`): a caught Pokemon is no longer outside the stake; it is held by mark, with the default
  inverted (F2).
- 2.5 chat line 4 (`:283`): no catch clause; the catches line follows it (section 8).
- 2.6 "What they kept" (`:335`): forfeited, reaped on return.
- 3.6 (the den): a note that the den stays `uncatchable` and a nest is a separate leg (11).
- The header's status line: a pointer to this file.
