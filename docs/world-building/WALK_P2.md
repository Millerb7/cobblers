# The walk's "four P2s": an interpretation, and what was done

Written 2026-10-08 (overnight) by unit WAY. The owner asked for "the four P2s from the walk".

## 0. The premise does not hold as worded

**No list called "P2" exists in the repository.** The walk documents (`CRITICAL_PATH_WALK_1.md`, `_2.md`) rank items
BLOCKER / STALL / GAP and number them. `POST_GYM8_DIRECTION.md` section 0 took the owner's "six P1s" to be items 1-6 of
`CRITICAL_PATH_WALK_2.md` section 2. **This document takes the four P2s to be the next four, items 7-10.** That is an
interpretation. If the owner meant another four, the status column still holds for these.

## 1. The four, with their status measured today

| # | Item (`CRITICAL_PATH_WALK_2.md`) | Status 2026-10-08 | Done here |
|---|---|---|---|
| 7 | **STALL: from G2 to the Deep, about 2,700 walked blocks of Rift floor hold no trainer, no event and no shop** (line 113) | **OPEN.** The Deep's two Rimside stalls (`data/markets.json` `deep_rimside_chandler`, `deep_rimside_cook`) are still `status: unsited`. Siting them is data work, but it needs `derived/deep_city/plan.json` `front_row`, which this worktree does not have. The Deep's Mart clerk needs `tools/deep_city.py` to record the shopkeeper jigsaw (`markets.json` `no_counter` deep_city). Rimwatch now has its rangers' kit stall (2026-10-05) | Nothing. **Next step:** in a full checkout, site both stalls from `front_row` and set them to `sited` |
| 8 | **STALL: Routes 5-8 have no road** (line 117) | **OPEN.** The road is world-building, not data. The badge waypoints and waystones are still unproven in game (EXP-020 part F). `route_06_trainer_04` is still seated at (5756, 106, 3078). The heightmap gives ground y105 there (`data/late_route_trainers.json` shoulder, relief 0), so the block round its feet and head is something in the world, not in the seat data. Naming it needs a read of a stopped staging copy | Nothing. **Next step:** read the block at (5756, 106-107, 3078) on a staging copy, then move the seat or clear the block |
| 9 | **STALL (staging only): the 2026-10-04 spawner fix is not applied** (line 121) | **CLOSED.** R16G ran on 2026-10-04 with 0 problems (`docs/STATE.md` "Latest applies", `--only R16G,R15,R17,...`). STATE line 90 reads "all seven gym spawners read back at their data height". Not re-checked here | Nothing |
| 10 | **GAP: the finale is a conversation** (line 128) | **MOSTLY CLOSED.** The HQ tower interior is built and applied, with seven fights, Brann and Elara among them (`data/hq_tower.json`, `data/finale_trainers.json`, STATE line 90). **Still open:** there is no Hoopa entity at the cradle. `data/relic_underground.json` `why_no_hoopa` says Hoopa's client model is not verified, and Codex gates its actor on that check. That is an in-game check, not a data change | Nothing |

**Fixed here: none of the four.** None has a data, dialogue or sign fix that can be made offline in a worktree. Item 7
needs `derived/`; items 8 and 10 need the world or the client.

## 2. Direction gaps (A9) checked by the same unit

- **After Koga (U47): closed.** The marsh tracker (`dlg_main_koga_marsh_tracker` `koga_mega`, seat (4643, 118, 2449))
  now points at the Mega field and the Cutters' Gulch. Measured: every one of the 61 Mega dens anchors inside z2's
  boxes (8 badges), and the gulch admits `gym6_cleared`. **Walk 2 item 14's "open at 6 badges" does not reproduce.**
- **After gym 8, Victory Road and the finale: already closed** by `POST_GYM8_DIRECTION.md`: the badge's waypoint and
  hint to the surveyor, the surveyor's `rift_way_1..3`, the notice before the Sink Gate, z5's turn-back hint, the
  wall sign at the caves' mouth, and the binder's `release_way`. Nothing more was added. Still open: items 3-5 there,
  and its recorded defect that `victory_road_transition_10` (3618, 83, 3256) stands over the Deep's pit.
- **Pallet to gym 1: held, not landed.** A waypoint offer was built and then reverted:
  - `data/progression.json`: a marker `gym1_town` on `gym1_brock_gym`, whose point is (1825, 140, 3678), 1,672 blocks
    from Oak's seat. Also a flag `oak_sendoff` (`set_by` quest_transition `record_oak_sendoff`) that offers it.
  - `data/quests.json`: `record_oak_sendoff` gets a first effect, `function cobblers:flag/oak_sendoff/grant`.

  `progression_pack` built it and the offer read correctly. But `tests/test_oak_lab_scene.py` interprets Oak's
  compiled commands with a strict model, and six of its tests failed with "an execute this model does not interpret:
  'at @s run function cobblers:flag/oak_sendoff/grant'". That test is not the builder's to change. **To land it:**
  `test-author` teaches that model a grant (`function cobblers:flag/<id>/grant` adds the flag), then the three edits
  above go back in. Until then, Oak's own lines and the Route 1 signs are the only way a player finds gym 1.
