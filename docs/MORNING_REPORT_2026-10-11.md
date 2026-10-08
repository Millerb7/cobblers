# Morning report, 2026-10-11 (overnight brief of 2026-10-10)

Branch `build/2026-10-06-next` (head in `docs/HANDOVER_SESSION.md`). Review list `docs/OVERNIGHT_REVIEW_2026-10-06.md`
N140-N150.

## IN THE WORLD: nothing new

**A server was running all night** (port 25565 listening, a server Java process, no coordination lock held). By the
live-server rule no server work ran: no throwaway proof, no prepare, no install, no staging apply. Staging still holds
what the 2026-10-09 report lists (`docs/REPORT_2026-10-09.md`). Everything below is built, independently audited,
merged and committed — and not in any world.

## Built and audited tonight (staging-ready unless noted)

| # | Item | State | Where |
|---|---|---|---|
| 1 | **Nether/End override** (the live defect) | 7 structure sets zeroed (`frequency 0.0`; the audit read the 1.21.1 jar: 0.0 = never); re-measured Blaine 641.8 / Moltres 16-22 / End League 26.2 expected placement attempts; Ruinous shrines kept. **Live world: yours to install** (N141). Proof EXP-058 waits for a free server | `data/dimension_overrides.json`, `tools/dimension_overrides.py` |
| 2 | **Entei boss** | Ember Sigil (2 netherite ingots), private pocket slot, L100 catchable once, item drops, 24,000-tick lockout, blackout on loss. Three defects recorded (a second catch after a logout; the lockout after a clock reset; first-24,000-ticks refusal). EXP-059 needs you | `tools/entei_boss.py`, step R16Q |
| 3 | **Arena payout hole** | Settled: it paid TWICE (our purse + CobbleDollars' automatic NPC payout, up to ~$128k on a streak). Now: the auto-payout is clawed back; full purse once per rank (~$47k ranks 1-4), then $200 x3 per 20 min. Two leaks recorded (a teammate's pay in the window) | `tools/arena_runtime.py`, EXP-060 |
| 4a | **Income model** | Measured from the real rosters with CobbleDollars' quadratic payout: $4,033 by badge 1, $202,835 by badge 8 (the old model said $9,475 / $145,078) | `tools/income_model.py` |
| 4b | **Bank + Produce Buyer** | 81 farmable entries out (122 -> 41); Produce Buyer Odile Furrow (2065, 135, 5563) with a per-leg allowance (max ~$3,600). Install only after EXP-061 confirms the `clear 0` count | `data/bank.json`, `tools/produce_buyer.py` |
| 4c | **Refillable mining caves** | Shared, 20-minute refill under the stone-face guard: Route 1 old mine (1347, 4080), 3 galleries; Fossick (6767, 5804), 8 galleries. Sites are yours to confirm | `tools/mining_caves.py`, step R9OC |
| 4d | **Paid services** | $500 raise to cap, $2,000 EV spread, $1,000/IV stat; keepers at the 8 training grounds (gym 1's at (1835, 140, 3620)). EV/IV do not read back (N147). EXP-062 needs you | `tools/training_services.py`, step R17TS |
| 4e | **Prices** | Income-gated lines follow the new income (Brock's TMs $4,100 ... Giovanni's $202,900); convenience lines re-priced so the curve sits at 0.67-0.68 at every badge | `data/markets.json` |
| 5 | **Queue** | The eight units the brief listed landed on 2026-10-09. The P1s: Victory Road skippable and z4 are yours (N132); the Champion's floor trigger is in-game only. The four blocked seats: one false alarm (a carpet), the "signpost" explanation wrong, the other three most likely export foliage (N149) | |

Every audit passes in the full checkout (challenge, economy, markets, bank, produce buyer, legendaries, sweep, mines,
arena, the Entei/caves/services/override audits), `validate_data` and `validate` 0 errors, `id_authorship` 0 faults;
the markets audit's 32 payment faults are stale `build/` output that the next prepare regenerates.

## Your decisions (each in the review list)

1. **Wild-battle pay** (~$700 per level-50 wild battle, uncapped) — every economy number assumes it OFF (N144).
2. **The Challenge voucher**: the ladder says $4,000 cash + per-gym answer-kit materials (~$14,750 of value), not $100k
   (N148). Its form.
3. **`ranch_ore`**: a 16-Pokemon pasture makes ~$13,030/h in emeralds; keep "ore stays flat" or exclude (N145).
4. **Vitamins**: brewed cheaply now that the bank does not buy them; Northlight's $3,500 shelf (N145).
5. **The Nether override on the live world**: copy the pack in (world datapacks or the global folder), server stopped (N141).
6. **Poipole** loses its only natural spawn (N141).
7. Answer kits by barter, a barterer per gym town, the Master Ball floor (R4), the cave sites, and the economy design's
   questions (`docs/mechanics/ECONOMY_OVERHAUL.md` section 10).

## Blocked on you

- Stop the running server (or tell me it is yours to keep) so the night's work can be proved and applied.
- Brock in Normal and Challenge (holds the other 12); Lootr's two-player cases; the in-game checks (EXP-059 Entei,
  EXP-060 arena payout, EXP-061 produce buyer, EXP-062 services, EXP-058 needs no player).

## Cost

`tools/session_cost.py`: this session 35.2M weighted (context 964k — it could not be restarted from inside); agents
73.3M across the session.
