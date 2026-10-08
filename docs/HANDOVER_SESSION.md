# Handover: session bacb34ed, 2026-10-08 (day after the 2026-10-10 overnight brief)

A cold session reads CLAUDE.md, `docs/STATE.md`, this file and `docs/MORNING_REPORT_2026-10-11.md`, and nothing else,
before it starts. The review list is `docs/OVERNIGHT_REVIEW_2026-10-06.md` (N140-N161 are the last two days').

## 1. The branches
- **`build/2026-10-06-next`** at `d56057d` on origin, no PR yet (memory: one big PR per batch, against main). Worked
  from worktree `wave-a-builds-integration-98eb36` (local `claude/wave-a-builds-integration-98eb36`), pushed with
  `git push origin HEAD:build/2026-10-06-next`. Re-read the head first: `git fetch --prune; git rev-parse
  origin/build/2026-10-06-next`.
- **Player site:** [Millerb7/cobblers#120](https://github.com/Millerb7/cobblers/pull/120) MERGED (head `f1d6c10`,
  merge `a00b9c4`); [Millerb7/cobblers#121](https://github.com/Millerb7/cobblers/pull/121) open draft, head `a94f869`,
  branch `site/player-guides-2-2026-10-08` (FROZEN: reported). Merge with
  `gh pr merge 121 --match-head-commit a94f8690032600843dcf9447d11e294c8489ba50`. Main holds only the static
  `docs/player/`; the generators (`tools/player_site.py` and the three guides) reach main with the batch. The site
  worktree `../site-pr-2026-10-08` can be removed.

## 2. Where it stopped
- **Staging is RUNNING** (process 33216, terminal tab "staging readback", 16G, `max-tick-time` back at 60000) for the
  owner's in-game checks. **The coordination lock is released** at hand-over; a session that needs the server checks
  the PROCESS, then asks the owner whether the running server is theirs.
- In staging (STATE "Latest install"): the 2026-10-10 overnight's work, applied and read back. EXP-058 passed.
- **Merged after that install, NOT in staging:** the Entei fixes + re-theme, the arena narrowing, Poipole at the towers,
  services/crafting prices + voucher, the Nether tables + badge-8 gate (`cobblers_nether_gate`, self-driving), the
  Victory Road closure (R9Z) and the z4 re-cut (R9Z), the iron-gear blacklist. Next, when the owner's checks are done:
  prepare (~50 min; `--server-dir`, `COBBLERS_SERVER_ROOT`, lock env), snapshot, install, boot 16G with tick -1,
  `run --only R9Z,R16Q,R17TS --no-reload`, restart, read back with probes. **EXP-059 (Entei) and EXP-062 (services)
  need that install first**: run now they test the old code.
- Owed independent audits: the Victory Road closure (its audit is the implementer's), the Nether tables and gate
  (builders wrote their own tests), the services' crafting rule beyond ed8c773, the apricorn/buyer exemption (N151).

## 3. Waiting on the owner
- Decisions:
  - the arena's remaining leak (N156: emptying the balance to a teammate keeps the payout; an exact fix needs a
    permissions mod or a mixin, an ADR);
  - Entei's two new relog cases and the farmable Life Orb (N157);
  - netherite scrap at gym 1 and services cheaper than a Challenge fight hour (N158);
  - the dungeon design's nine questions (`docs/mechanics/DUNGEONS.md`, ADR-008 Proposed; The Night Shift first;
    Ultra Beasts are available as bosses, `docs/research/notes/ultra-beasts-1.8.0.md`);
  - when the bank config goes server-wide (it stays old until the Produce Buyer is seen working, EXP-061).
- The live Nether override: copy `build/datapacks/cobblers_dimension_overrides` into the live world's
  `datapacks/` with the server stopped, before anyone enters the Nether or runs `/locate` there. Install the
  Nether gate with or before it once it is in a build.
- In-game: Brock (Normal and Challenge), EXP-060 arena, EXP-061 Produce Buyer, Lootr's two-player cases; EXP-059 and
  EXP-062 after the next install.

## 4. Do not rediscover
- `reapply.py prepare` needs `--server-dir`, `COBBLERS_SERVER_ROOT` and the lock env (`COBBLERS_SERVER_LOCK`,
  `COBBLERS_LOCK_OWNER` = the lock's `owner:` line). Any edit to `data/` or `tools/` after a partial prepare makes
  every earlier job stale: run prepare whole once the data is final.
- `/locate` reaches STRUCTURE_STARTS and saves a start; the override cannot remove a saved one (N152). Test worldgen on
  fresh chunks of a same-seed control world, never on chunks a control run touched.
- A forceloaded chunk's entities arrive a few seconds later: a kill in the same function misses them (N155, R17M).
- Agents brief "start from <sha>" often find HEAD already past it (`worktree.baseRef: head`): they merged or reset;
  three agents also misreported their branch name. Verify every merge by sha, never by the reported branch.
- Two units can each add contract "C19": a clean text merge hides it (the gate's became C21).
- `data/towns.json` lags a town's re-site; `data/placements.json` settlement centres are what is built (Pacifidlog).
- A 12G server cannot `/reload` this build; boot 16G, `--no-reload`; stop with RCON `stop`.

## 5. Cost
`python tools/session_cost.py`: this session 44.2M weighted over 825 turns (context 446k at hand-over); agents across
the session per `tools/session_cost.py` (today's 20 units: designs, builders, audits, the site).
