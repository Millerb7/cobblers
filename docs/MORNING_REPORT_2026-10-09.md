# Morning report, 2026-10-09 (overnight brief of 2026-10-08)

Branch `build/2026-10-06-next` (head in `docs/HANDOVER_SESSION.md`). Staging world
`C:/Users/wnd/Documents/cobblers-staging/staging-2026-10-01`; snapshot before tonight's apply
`cobblers-staging/snapshot-2026-10-08-before-overnight` (11,077 files, the same count as the world). Review list:
`docs/OVERNIGHT_REVIEW_2026-10-06.md` N114-N127 are tonight's. **Your Brock check had not happened** (no player
joined staging), so the other 12 bosses stay held.

## What is IN THE WORLD (staging), read back from the world after a plain restart

Applied by `reapply.py run --only R14,R16C,R17F,R17M,R18DT --no-reload` (0 problems; partial by design, 5 of 91),
then a restart, then read back over RCON. Nobody has seen any of it in game.

| What | Where (x, y, z) | Read back |
|---|---|---|
| Northlight's barterer, 8 approved re-priced lines | (7277.5, 116, 1525.5), inside the Northlight Mart, in front of the counter | one villager, cartographer level 5, 8 offers as written (e.g. netherite block + 21 netherite ingots -> Master Ball) |
| The EXP-055 experiment barterer | (3634.5, 102, 6462.5), the booth under Holdfast's counter | one villager, its 2 offers as written |
| Mart re-pricing and the Training shelf (R14) | every Mart; Sunset West and Pacifidlog repriced | `traders verify`: 26 traders, 0 problems |
| Town Pokemon, 8 situations rewritten and 61 unique to their town (R16C) | 22 settlements | 532 idle in 22 settlements ok, 194 working ok; one farm Combee (`idle_farm_combee_4`) wandered (same as N94) |
| Brock, one leader | spawner (1832, 155, 3696) | `single_leader_verify` 0 problems |
| Trainers | all 89 seats, 8 gym spawners | all present; failures are live head rotation and the four known blocked seats |
| Installed with the packs (no step): the bird-nest hint (Oak (1493, 118, 5317), the Route 1 picnicker), the after-Koga Mega field line (marsh tracker (4643, 118, 2449)), the Relic charter ungated of its dead quest, the Red Orb cache at Groudon's pedestal (6672, 68, 5542, `champion_cleared`), the Prison Bottle at the cradle dais (3357, 12, 3306, `rift_crisis_resolved`) | | `install_check` 0 problems; read at runtime, not exercised |

## The brief, item by item

| # | Ask | Result |
|---|---|---|
| 1a | Fresh A1 audit | Done by a new agent: **my test edit had weakened the tests** (N115); fixed in the audit; two rollout traps recorded as strict xfails |
| 1b | Misty and League floors | Measured, rollout still Brock only. **Agatha's and Lance's spawners are 10.8 apart, inside reach 17** (N116) |
| 1c | Pacifidlog at 6; heals a convenience | Done: Sunset West status cures 9,500 -> 400, super potion 1,400; Pacifidlog at template prices |
| 1d | Barter re-priced, at Northlight | Done: every line 1.00-1.05 of the counter; all approved; at Northlight's Mart |
| 1e | Lootr | Downloaded (sha512 = Modrinth), EXP-056 console pass on a disposable copy, removed from `mods/`. **A re-apply resets opened state; our loot strip may not keep a container vanilla** (N123). ADR-007 stays Proposed |
| 2 | Wave B | Built: the Training shelf (A7), the Northlight barter (A8 loops 1+3), two A6 caches, the bird hint and Koga direction (A9), the charters (A10). Calls recorded at the end of each design file. **Held**: 41 counter lines (TMs, memories, Sachet), N127 |
| 3 | Ambient 350-400 | **The premise was wrong: the data and the world already hold 726.** None added; uniqueness fixed instead (copied ideas rewritten) |
| 4 | Sapling hint; P2s; P1s; E4 test; 11 items | Hint built (6 tree-only species measured, not 13; Hoothoot and Starly are not tree-only). P2s read as walk 2 items 7-10 (N121). The post-gym-8 direction was built 2026-10-06. E4 over-cap test added (N117). The 11 items: `docs/mechanics/ITEM_ROUTES.md` section 0 says which block something |
| 5 | The three figures | In no measurement and not in STATE; first seen in 12c730e as questions quoting your brief. Deleted from every open list (N114) |

## Waiting on you

- **Brock in game** (b-steps, `docs/mechanics/ONE_LEADER_SWAP.md`), then the 12; before them: Agatha/Lance (N116) and
  the two traps (N115).
- **TMs at the counters** (N126/N127): price them above the income gate, or sell them later; the 41 lines wait.
- **Arena trophies sold by barter** (N125): five barter outputs are the arena's once-per-player prizes.
- Gym 2 kept at two juniors (you accepted); the Pallet -> gym 1 waypoint needs a marker record (N120).
- Lootr's two-player cases (A, D1) and C2/B4.
- Owner questions left in each design file's "Decisions taken 2026-10-08 (overnight)" section.

In-game checks (staging; boot at 12G with your client open):
- Brock at (1832, 155, 3696), Normal then Challenge.
- The Northlight barterer at (7277, 116, 1525): a Master Ball for a netherite block + 21 ingots.
- Sunset West's Mart: a Paralyze Heal at 400.
- The Training shelf at any Mart (a power item, 1,500).
- Oak's bird line after the send-off.

## Process

- Prepare ran twice: the first stopped at the town squares audit, which failed the 41 new counter lines (held,
  N127); the second passed 187 of 187.
- I booted once without setting `max-tick-time` -1 and had to restart; the run itself was clean.
- Cost (`tools/session_cost.py`): this session 14.7M weighted to date (context 558k); agents 27.0M across both nights
  of this session.
