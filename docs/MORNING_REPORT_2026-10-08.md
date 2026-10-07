# Morning report, 2026-10-08 (Wave A)

Branch `build/2026-10-06-next` (head in `docs/HANDOVER_SESSION.md`), built from worktree
`wave-a-builds-integration-98eb36`. Staging world `C:/Users/wnd/Documents/cobblers-staging/staging-2026-10-01`; snapshot
before Wave A at `cobblers-staging/snapshot-2026-10-07-before-wave-a` (11,023 files, the same count as the world). The
review list is `docs/OVERNIGHT_REVIEW_2026-10-06.md` N95-N113. (The machine clock read 2026-10-06 throughout; the
dates here follow the owner's timeline.)

## What is IN THE WORLD (staging), read back from the world

Applied by `reapply.py run --only R14,R17,R17L,R18DT --no-reload` (0 problems; a PARTIAL run by design, 4 of 91
steps), then read back over RCON, then **read back again after a plain restart**. Nobody has seen any of it in game.

| What | Where (x, y, z) | Read back |
|---|---|---|
| Brock as ONE leader (A1) | spawner (1832, 155, 3696); the second spawner at (1830, 155, 3696) retired | second spawner gone, floor polished_andesite over stone_bricks, the one spawner reads `kanto_brock` with nobody near; `single_leader_verify` 0 problems; same after the restart |
| Five new gym juniors (A2) | gym 1 Coal Hauler (1826, 153, 3695); gym 3 Cable Rigger (1730, 183, 1412); gym 4 Bough Climber (4316, 120, 1499); gym 6 Stack Warden (6185, 105, 3325); gym 7 Stair Stoker (6180, 116, 4987) | `trainer_world_audit`: all 89 seated trainers present (26 juniors), none missing or doubled, 8 of 8 gym spawners; failures are live head rotation read as facing (known) and the two known blocked seats |
| Early-town Mart prices (A3) | Sunset West and Pacifidlog Marts | `traders verify`: 26 traders, 0 problems |
| The direct-trade experiment villager (A4, EXP-055) | (3634.5, 102, 6462.5), a buried booth under the Holdfast counter (`/tp` only) | one villager, armorer level 5, NoAI 1b, both fixed offers as written (maxUses 9999, the control's priceMultiplier 0.2), breach score 0; **same after the restart and a chunk unload/reload** (EXP-055 part a) |
| The finale badge gate (A3) | the Rift surveyor, the `rift_crisis_pending` setter, the HQ guard (3444, 67, 3283) | installed in `cobblers_dialogue` and `cobblers_relic_underground` (`install_check` 0); read at runtime, not exercised |

**Measured in staging: rctmod saves `InBattle` as a byte, `0b`, on a standing trainer** (Hall Mason,
`gym1_junior_01`). That was the one assumption under which Brock's swap could have locked Challenge players out of
gym 1 (N96); the form matches the swap's guard. `1b` during a battle is not yet seen.

## What was built, by unit

| # | Unit | Result | Lives in |
|---|---|---|---|
| A1 | One leader per gym | Brock only (`single_leader.rollout`); swap by the nearest player's mode within 17, never in a battle; R17L retires the second spawner. The opus audit found three retire defects; I fixed them and edited the auditor's test to match (N95). The other 12 wait on the owner's in-game check of Brock, and Misty and the League need floor data first (N97) | `tools/challenge_mode.py`, `docs/mechanics/ONE_LEADER_SWAP.md` |
| A2 | 3+ juniors per gym | 26 (3,2,3,3,3,4,4,4). **Gym 2 cannot take a third** (N99). Opus audit: safe; added all-at-once softlock, walled-in and line-of-sight checks | `data/gym_junior_trainers.json` |
| A3 | Finale gate + early pricing | gate on `gym8_cleared`; tier prices 9,500 / 17,100 / 28,700 / 45,700 / 61,000 / 82,300 / 109,100 at both towns (N101-N102) | `data/quests.json`, `data/traders.json` |
| A4 | Direct trades | experiment villager placed; 8 barter lines built and HELD (`approved: false`). Opus audit: no arbitrage loop; found the one-chunk forceload (fixed) | `tools/direct_trades.py`, `experiments/EXP-055-*` |
| A5 | Lootr | ADR-007 (Proposed), EXP-056 designed; blocked on your permission to download the jar | `docs/decisions/ADR-007-*` |
| A6 | Every item attainable | a route per blocker; 12 questions | `docs/mechanics/ITEM_ROUTES.md` |
| A7 | EV/IV and the Marts | recommends a Training shelf on the Marts, not moving items out; 9 questions | `docs/mechanics/EV_IV_TRAINING.md` |
| A8 | Minecraft play worth it | five loops, barter rules B1-B4; 8 questions | `docs/mechanics/MINECRAFT_PLAY_LOOPS.md` |
| A9 | Campaign outline | chapter skeleton, 16 contradictions; 12 Codex and 8 owner questions | `docs/story/CAMPAIGN_OUTLINE.md` |
| A10 | Side islands | no gym move; Sabrina's student at Northlight instead; 11 questions | `docs/world-building/SIDE_ISLANDS.md` |

## Wave B reads these first (A6-A10)

The five design files above. Premises they corrected: spawn-condition blocks draw nothing inside the sub-region
polygons (A8, N108); Challenge mode skips no story, the badge carry does in both modes (A9); Shrew Station's issuing is
ON in data (A6, N106; STATE corrected); Pacifidlog has no working ferry and all four charters are shut (A10, N109);
the Dubious Disc already has a route (A6).

## Waiting on you

Decisions:
- **A1** Walk Brock with a Normal and a Challenge character (b-steps in `ONE_LEADER_SWAP.md`); on a pass, roll out the 12.
- **A2** Gym 2: change the hall (a second chokepoint) or accept two juniors.
- **A3** All eight badges or one for the finale; Pacifidlog reachable at 0 or 6; tier-1 status heals at 9,500?
- **A4** The eight barter lines (approve, price, cut); the $27,000 Master Ball on Northlight's counter beside a
  barter 5.8x cheaper; where players actually trade (the booth is `/tp` only).
- **A5** Permission to download Lootr; mark ADR-007 Accepted.
- **A6-A10** their numbered questions (above files).
- Still open from before: the sources of "THE NURSE: 30 minutes", "237 ambient across 26 settlements" and "the four
  P2s" (nothing in Wave A used them).

In-game checks (staging):
- **Brock** at (1832, 155, 3696): a Normal player gets Brock's Normal team; a Challenge player standing near gets
  `kanto_brock_challenge`; a mixed pair: the farther one is refused until nearest.
- **The barterer** (`/tp 3634 102 6462`): trade 20+ times, across a day/night and a restart; the price never moves;
  the control (priceMultiplier 0.2) shows what drift would look like.
- **The new juniors**, e.g. gym 7's Stair Stoker (6180, 116, 4987): do they start the battle on sight?
- **The finale gate**: a badgeless character at the surveyor and the HQ guard is refused; an eight-badge one is not.
- **Sunset West's Mart**: the repriced shelf.

## How the run went

- Prepare ran four times: my missing `--server-dir`; then my `derived/` copy had nested into `derived/derived`
  (an earlier "derived copied" was false); then the whole-build function check caught A1's retire function without
  its chunk marker (fixed); the fourth completed, 187 of 187 jobs, every Wave A audit inside it.
- **The first staging boot at 12G ran out of memory in reapply's `/reload`** (16 minutes, the RCON listener died,
  OutOfMemoryError). Nothing was applied, but the server had autosaved during it, so that world is set aside at
  `cobblers-staging/staging-2026-10-01.oom-2026-10-07` and the snapshot restored and reinstalled (N111). The second boot at
  16G ran with `--no-reload` (a fresh boot has the packs loaded).
- A Ctrl-C stop logged no save (N112); the run's own save came first, so nothing was lost. Stop staging with RCON
  `stop` from now on.
- Integrator edits to an auditor's test (A1) are recorded (N95), not hidden.
