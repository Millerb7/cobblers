# Handover: session 2312d085, 2026-10-13 night (stopped at the 300k context line)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branches
- **#137** `build/2026-10-13-weather-trio` (draft, FROZEN: reported) head `77bf707dd2e92fd7900cab7c197d00c1deacd73c`:
  the 10-13 batch (Rayquaza/Kyogre, the seas, Hank and Lena, the dungeon draw, economy B1/B3-B5) with main merged in.
- **`build/2026-10-14-mods-1.8.2`** (worktree `.claude/worktrees/mods-182`, pushed): stacked on #137; the 1.8.2 manifest,
  economy E7 records, the Trading Post (B2) and its independent audit (B4/A4), the Challenge boss redesign, guide
  fixes. Draft PR against main (it contains #137; merge #137 first, or merge this one alone: it supersedes it).
  `git fetch --prune` and re-read heads before quoting.
- The mods-182 worktree holds a copy of `derived/` and `build/` (from the night-shift worktree, ~1 GB) and hydrated kits.

## 2. Where it stopped
- **Job A (Cobblemon 1.8.2 and every mod): blocked on the owner.** Downloaded and sha512-verified: the 7 lockstep jars
  and the owner's 4 HOLD picks in `C:/Users/wnd/Documents/cobblers-local/mod-updates-2026-10-14-lockstep/` (all 51 new jars
  also in `mods-182-extra/`). The 101-jar server set is assembled at `cobblers-local/server-mods-1.8.2`; dependency
  closure clean. **Swapping it into `cobblers-server/mods` was REFUSED by the permission check ("Production Deploy": the
  folder serves the live world too). Do not route around it.** The owner was given the commands (move the old folder to
  `cobblers-server-retired/mods-1.8.0-20261014`, then COPY, not move, the new set in: `economy_audit` reads it).
  After the swap: a throwaway generated-world boot (`--universe C:/Users/wnd/Documents/cobblers-staging --world <new name>`)
  to read load errors and CobbleDollars Beta-6.1's migrated `config/cobbledollars/default_bank.json` (the new format
  is unread; `tools/bank.py` and `install_check` still use `bank.json`), then the full cycle on staging: prepare, hold
  the bank, install, boot 24G watchdog off, `reapply.py run` (new: R14R, R18KC, R16CH, R18CH, R16DR re-apply, R9F,
  R18PB), stop, watchdog 60000, strip, boot 12G, read back. Then the client pack and the friends' zip.
- **Lock: released** at the session's end. The server is DOWN. Take the lock afresh (process/port check first) before the swap's boot.
- Snapshot anchor: `D:\cobblers-snapshots\staging-2026-10-14-before-1.8.2` (world, mods, config; verified).
- Verified on the integration branch: economy_audit 0 problems; economy + sim + Trading Post tests 159 passed;
  contracts C4/C24/C28/C29 11 passed; trainer tests 116; gym_arenas_audit clean; voucher current. The full contracts
  suite ran once before the audit merge (69 passed; C4 fixed since, C24 fixed by the audit's sim change). NOT run since
  the last merge: the full suite, prepare.

## 3. Waiting on the owner
- The mods swap (above).
- Challenge: eight leaders changed ace; acceptable? Redesign the 77 route/junior Challenge fights (needs the route
  generator field in CHALLENGE_MODE_TEAMS.md section 6)?
- Trading Post: kitchen/pharmacy prices; the 14-option one-page dialogue; squares for Fossick and Northlight; the
  pasture income (~$3,808/h a pasture under no cap); W as typical hour (used) or fight hour.
- Older and unchanged: dungeon gates, Nether as a Nuzlocke zone, crushed-house lot, sealed-chamber markers,
  Hoarfrost Hollow's mouth block (6722, 100, 1348), Scar Tarn water wards.

## 4. Do not rediscover
- The local `main` checkout was 363 commits behind; `docs/HANDOVER_SESSION.md` on main was a day stale. Fetch first.
- Cobblemon 1.8.2's data change against 1.8.0 (species learnsets, both jars): Venonat/Venomoth lose `tm:megadrain`,
  Spinda `tm:teeterdance`; nothing else. TMCraft 1.8.2 still ships tm_megadrain.
- CobbleDollars payout (bytecode, both 5.1 and 6.1): base = (sum of the loser's levels)^2 / 10 (6.1 rounds, 5.1
  truncates), plus nextBetween(base/2, 2*base), times the 1.25 multiplier; wild Pokemon never pay (config).
- Only three installed jars pin Cobblemon exactly: tim_core, tmcraft, capture_xp.
- Python on Windows writes CRLF to a pipe: strip `\r` before comparing hashes read from its output.
- `tools/produce_buyer.py seats` skips `status: unsited` sites; Sunset Harbour needed `build/paint/manifest.json`.

## 5. Cost
`python tools/session_cost.py`: this session 4.0M weighted at 302k context; agents: E7 0.55M, audit 2.75M, plus the
Trading Post builder and the Challenge designer (Opus) — read their figures with the tool.
