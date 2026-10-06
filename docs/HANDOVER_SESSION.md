# Handover: the 2026-10-06/07 overnight build (session 595493c5, brief #2)

A cold session reads CLAUDE.md, `docs/STATE.md`, this file, `docs/MORNING_REPORT_2026-10-07.md` and
`docs/OVERNIGHT_REVIEW_2026-10-06.md` (N60-N94 are this night's), and nothing else, before it starts.

## 1. The branch
- **`build/2026-10-06-next`** on origin, no PR yet, stacked on `build/2026-10-05-p0` (draft PR
  [Millerb7/cobblers#119](https://github.com/Millerb7/cobblers/pull/119), frozen). Worked from worktree
  `wave-1-launch-prep-3d2fa0`, local branch `wave1-2026-10-06`, pushed with `git push origin HEAD:build/2026-10-06-next`.
  Re-read the head before quoting: `git fetch --prune; git rev-parse origin/build/2026-10-06-next`.
- Next: ONE draft PR for it against main (memory: one big PR per batch) after #119 merges, or stacked on #119.

## 2. Where it stopped
- **Staging is UP for the owner** (terminal tab "staging (for the owner)", -Xmx12G, max-tick-time 60000, process
  checked after boot). **The lock is released.** Everything in the brief that was built is applied and read back
  from the world (the morning report's table: 33 of 33 probes, 22/22 NPCs, 26/26 traders, 530/532 idlers).
- Snapshot before tonight's apply: `C:/Users/wnd/Documents/cobblers-staging/snapshot-2026-10-07-before-apply`.
- **`build/` is stale** against the last commits (`economy_audit` wired into prepare, the docs). Any install needs a
  full prepare (~32 min) first, with `COBBLERS_SERVER_ROOT=C:/Users/wnd/Documents/github/cobblers-server` and the lock env.
- `reapply.py run` refuses unless max-tick-time is -1: stop, set -1, boot, run, stop, restore 60000, boot.
- Nothing half-done. Merged agent branches: every `worktree-agent-*` of the night (juniors audit, economy audit).

## 2b. The next job (the owner's answers, 2026-10-07; STATE "What is decided")
1. Gate the finale behind badges (N8): no badgeless walk through the tellers to the HQ door.
2. Early-reachable towns (Sunset West, Pacifidlog) keep late-tier Mart stock, priced out of reach early.
3. Late-game items by DIRECT trade, no money: a vanilla villager with `Offers` (e.g. 4 netherite ingots for a Master
   Ball). Experiment first: a summoned villager with a modded `sell` item, no restock or price drift, trades as set.
4. The leader question: one Challenge-aware leader instead of two (swap the spawner's `TrainerIds` by the nearest
   player's mode, like the route trainers' swap, itself unproven E7), or the second spawner only while a Challenge
   player is near. The owner has not chosen.
6. **One leader per gym** (the owner, 2026-10-07: "i saw two brock and a brock outside the gym, remove excess
   stuff"). This answers item 4's question: one visible leader. Recommended: swap the spawner's `TrainerIds` by the
   nearest player's mode; test it on staging first.
7. **The Brock OUTSIDE gym 1** is not explained. With no player near, the world holds only the two juniors (rctmod
   trainers) and no `cobblemon:npc` within 150 of Brock's spawner (1832, 155, 3696); our packs place exactly two
   spawners there (Normal (1832, 155, 3696), Challenge (1830, 155, 3696)). Candidates: a donor template's own spawner
   ("Our list is not the world"), or a spawner-spawned Brock that walked out. Look with a player near.
8. **At least 3 juniors per gym, some gyms more** (today 2/2/2/2/3/3/3/4): gyms 1-4 need one more each, plus more
   in some later gyms; same builder + `gym_trainers_audit` path as the 21.
9. **Double battles: supported.** rctmod trainer files take `"battleFormat": "GEN_9_DOUBLES"` (read from
   `rctmod-fabric-1.21.1-0.19.0-beta.jar`: 50 bundled trainers use it, e.g. `boss_giovanni_0045.json`); rctapi also
   has `GEN_9_TRIPLES`; Cobblemon 1.8.0's own PvP request GUI offers doubles and triples. None of our trainers uses it;
   not seen in game in this pack.
10. **The owner's character on staging is WIPED** (2026-10-07, at their request): the 19 per-player files of
   `b8e115d8-...` moved to `C:/Users/wnd/Documents/cobblers-staging/player-wipe-2026-10-07/` (restore = move them
   back with the server stopped), scores reset. Their next join is a fresh player: Oak's lab scene and the mode choice
   get their first in-game test.
5. Waiting on the owner: the source of "THE NURSE: 30 minutes", "237 ambient across 26 settlements" (the world holds
   530 idle in 22) and "the four P2s"; none is in the repository. The sapling hint: N32 measured 6 tree-only species,
   not 13.

## 3. Waits on the owner
The morning report's "Waiting on you": decisions N8, N39/N54, N64, N67/N93, N71, N74, N77, N82, N83, N89, the four
item blockers, Kyogre Q1/Q8, summit loot, waystones, the two legendary rumour lines; and the in-game checks with
coordinates (Elite Four refusal, Hoopa at the cradle, juniors' facing, a training ground, Oak's lab, the exchange,
Giratina and Darkrai).

## 4. Do not rediscover
- The brief's premises "Hoopa spawns after the release" (it was my hand-spawned display) and "the fossil site is in"
  (not then; now applied) were false: the morning report says so.
- The Mart tiers live on the CLERKS, which only R14 (town traders) writes; R17M is the counter merchants. A batch
  that changes `data/traders.json` needs R14 (I missed it once; `traders verify` caught it).
- `pytest.xfail()` called imperatively is never strict: a "strict" known list must assert the problem is present
  first (fixed in tests/test_gym_trainers_audit.py).
- Any `tools/` edit stales every prepare job: fix all audits first, then one full prepare.
- The bank is a config file: it goes live at install and boot, before any run step. Audit it before install (N92).
- `run_in_terminal` refuses a `cwd` outside the session; `Set-Location <server>; java ...` in the command works.
- `say` returns nothing over RCON; probe with a bare `execute if block/entity`, which answers "Test passed".
- Two Combees at the Pokemon farm (`idle_farm_combee_2/3`) wander off: R16C's verify fails on them (N94).

## 5. Cost
`python tools/session_cost.py`: 827 turns, 47.4M weighted for the main session (context 259k at hand-over, average
469k); agents together 96.4M weighted across both nights. Tonight's agents: 10 builders, 5 independent auditors (training grounds, legendary sweep, Challenge, juniors, economy).
