# After gym 8: where to go, and Victory Road and the Rift finale explained in the world

Written 2026-10-06 by the direction builder (overnight, worktree branch off `4811ebc`). The owner: *"the six P1s from
the walk, especially no in-world explanation of Victory Road or the Rift finale. A player who beats gym 8 needs to
know where to go."*

## 0. A premise that does not hold as worded

**No list called "the six P1s" exists in the repository.** `docs/HANDOVER_SESSION.md` section 3b names it; neither
walk document labels anything P1 (they rank BLOCKER / STALL / GAP). This build takes the six **top-ranked items of
`CRITICAL_PATH_WALK_2.md` section 2** (items 1-6, the post-gym-8 half the owner's sentence is about) plus the owner's
own headline, and says so. If the owner meant a different six, the table below still states each item's status.

## 1. Each item: status before tonight, what was built, where

| # | Item (CRITICAL_PATH_WALK_2) | Before tonight | Built tonight |
|---|---|---|---|
| H | **The owner's headline: after gym 8 nothing says where to go** | **OPEN, and worse than silent**: the Earth Badge's reward offered a Xaero waypoint to the *League* (`data/progression.json` gym8_cleared `offers_marker: league`), which turns the player back at G5 until the finale. Giovanni speaks Cobbleverse's lines (ours not emitted); the watch's last line names the Rift's arms, not a person or a place | (a) **The badge now points at the Rift surveyor**: `gym_markers.rift_surveyor`, read from his seat in `data/npc_seats.json` (3552, 112, 5334), with a one-sentence hint naming the trailhead ~1,000 blocks north of Holdfast up the Victory Road signs. (b) **The League's waypoint moved to `rift_crisis_resolved`**, offered at the release with both ways up named. (c) **The southern watch** (3643, 114, 6497): `giovanni_way` after the account, and a rule that gives it to every Earth Badge holder who comes back. `tools/progression_pack.py` (markers may name `npc_seat`, may carry `hint`) |
| 1 | VR fights 8-10 and the exit inside z5; underground turn-back | **CLOSED 2026-10-04**: "qualify on entry" (`tools/rift_zones.py`, the z5 zone function admits a flag holder anywhere in the zone) | nothing |
| 2 | The finale hangs on 13 conversations in strict order; locked lines name the wrong cause | **CLOSED 2026-10-05**: the badge carry (`dddcdf63`: every gym flag carries the stage; `carry_by_*` dialogue rules); the surveyor's locked line now asks for the Earth Badge | nothing |
| 3 | Victory Road can be skipped on the surface (Deep's north rim to G5, 318 steps) | **OPEN, the owner's decision** (which is meant); nothing in the repo decides it | nothing decided. Every new line names **Victory Road's caves** as the way and the League's gate as opening; none calls either the only way |
| 4 | The League stands in z4 (the 120-species apex zone), not z5 | **OPEN, latent** (z4 held; the walk warns every run, review N30) | nothing: a zone-geometry change (move `behind_league` north of z2375, or give the lot to z5) is the owner's and `rift_zones`' call, not way-finding |
| 5 | The Champion's floor depends on `cobbleverse:trainer/kanto/defeat_elite_lance` firing for our override | **OPEN, in-game only** (handover Queue 2) | nothing buildable offline |
| 6 | Nothing points to the HQ | **PARTIAL**: inside the HQ, fixed 2026-10-05 (guard -> Nia, Nia -> tower, `RIFT_FINALE_CHAIN.md`); on the way there, nothing named the Deep, the HQ or its door | (a) **The surveyor** (3552, 112, 5334): `rift_way_1` (Rift floor -> the Deep -> the Sink Gate stair), `rift_way_2` (the black tower on the top ring's west side, its iron-door guard, the cradle beneath), `rift_way_3` (Victory Road's caves climb north from the Deep's floor; the League shuts until Hoopa is free); a returning mid-crisis player hears 2 and 3; after the release, `rift_after`. (b) **A notice on the Rift floor** before the Sink Gate, at (3748, 84, 3423): *THE DEEP / Compact HQ: / Sink Gate, then / top ring, west*. (c) **z5's turn-back** now prints, once, where its pass is earned: Hoopa's cradle under the Compact's HQ in the Deep, and the surveyor |
| VR | Victory Road explained where it starts | nothing at the caves' mouth | **A wall sign on the Deep's north face beside the mouth**, (3566, 2, 3064) facing south: *VICTORY ROAD / north, through / the caves, to / the League*. **The binder**: `release_way` after the release (and to anyone who comes back) says go up, and that Victory Road's caves climb from the Deep's floor to the League |

All six new dialogue lines are **placeholders for Codex**, each with a `placeholder` key naming this build; Codex's
own lines are unchanged (a test pins five of them). Only `next` pointers and entry rules were added round them;
`complete_giovanni_reveal` and `record_rift_crisis_pending` still fire on the same lines.

## 2. Files

| File | Change |
|---|---|
| `data/progression.json` | `gym_markers.rift_surveyor` (npc_seat, hint); `league` hint; gym8_cleared offers `rift_surveyor`; rift_crisis_resolved offers `league` |
| `tools/progression_pack.py` | a marker names exactly one of `placement` / `npc_seat`; optional `hint` printed in the offer |
| `data/dialogue.json` | `dlg_main_giovanni_watch` (giovanni_way, rule 7); `dlg_main_rift_surveyor` (rift_way_1..3, rift_after, rules 7 and 8); `dlg_main_relic_hall_release` (release_way, rule 20's node) |
| `data/signposts.json`, `tools/signposts.py` | `notices`: a route notice (seated like a junction post, kept 3 off every post) and a wall notice (measured position, no fence); `verify` reads both |
| `data/rift_zones.json`, `tools/rift_zones.py` | `zones.z5.turn_back_hint`, a chat line in the turn-back only (the knock box re-fires every second) |
| `tools/new_player_walk.py` | **added** `told_where_next` to `victory_road` (the badge's waypoint stands on the seat of whoever moves the reveal to `rift_crisis_pending`, found from the data) and to `league` (the release's waypoint inside the League's footprint). Against the build before tonight both FAIL; against this branch's packs both PASS |

**Tests** (all pass in this worktree): `tests/test_post_gym8_direction.py` (20), `tests/test_signposts_notices.py`
(9), `tests/test_new_player_walk_told.py` (7), four new in `tests/test_progression_pack.py`, which also changed one
assertion on purpose: gym 8's offer is now "Rift Surveyor". Also run green: `test_progression_pack`,
`test_badge_carry`, `test_finale_wayfinding`, `test_compile_dialogue`, `test_finale_audit`, `test_reveal_chain`,
`test_rift_crisis_resolved`, `test_signposts`, `test_signposts_keep_clear`, `test_rift_zones`, `test_new_player_walk`.

## 3. To put it in the world

Prepare (it runs `progression_pack`, `compile_dialogue`, `signposts function`, `rift_zones:build`, the walk), then
install `cobblers_progression`, `cobblers_dialogue`, `cobblers_signs`, `cobblers_rift_zones` and restart. Then:

- **R15** (route signposts) places the two notices; it re-places every post, which is idempotent.
- **No block step for the zones**: only `z5/turn_back`'s text changed (R9Z need not re-run).
- The progression pack is self-driving. **A player who already holds `gym8_cleared` never sees the new offer**
  (a reward runs once); the watch's and the surveyor's lines cover them.

Then `install_check`, and `python tools/signposts.py verify --world <stopped staging copy>` (52 posts).

## 4. In-game checks (none of this has been seen)

1. Beat Giovanni (3564, 121, 6416): the chat offer reads "Next: Rift Surveyor" with the trailhead sentence; [Add].
2. The watch (3643, 114, 6497) with the badge: the surveyor line, then the repeat.
3. The surveyor (3552, 112, 5334): the account ends with rift_way_1..3; talk again: rift_way_2, rift_way_3, repeat.
4. The notice at (3748, 84, 3423) stands on the Rift floor and reads from the trunk side. The canonical heightmap
   has no Rift sculpt pass: if the floor there was cut lower, the post floats.
5. The Deep's floor at the mouth: the wall sign at (3566, 2, 3064) hangs on the face, readable from the plaza.
6. Without the flag, walk north into z5: turned back at (3573.5, 86, 2688.5) with the chat hint, once.
7. Release Hoopa: "Next: Pokemon League" with both ways named; the binder's release_way.

## 5. Defects recorded, not chased

- **`victory_road_transition_10` (3618, 83, 3256) stands inside the Deep's pit**: `rift_deep.model()` puts that
  column in ring 4 (floor y0). `tools/signposts.py` seats every post on the heightmap, which has no pit, so the post
  is built 83 blocks above the floor (or erased by `cobblers_deep`'s air fill, depending on order). Victory Road's
  line (`data/routes.json`) runs through the pit from (3689, 3370) to the mouth (3560, 3064); any post seated on that
  stretch has the same fault. Not fixed: moving or dropping a route post changes `expected_post_ids`.
- **`tests/test_system_contracts.py::test_contract_c4_every_tool_that_reads_the_spawn_conditions_is_accounted_for`
  fails at this branch's base**: `tools/bank.py` is not in contract C4's list. Nothing tonight touched it.
- `python tools/validate_data.py` reports 1 error in this worktree: 263 local-only templates unhydrated (an
  environment fact; kits were not needed here).
- `data/progression.json gym_markers.why` still says gym 1's marker is "Oak's to offer at the start (not built)";
  another agent owns Oak's intro tonight, so it was left alone.
- Items 3, 4 and 5 above stay open; item 3 is the owner's decision.
