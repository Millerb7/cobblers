# The Rift finale, end to end: from the HQ door to `rift_crisis_resolved`

Written 2026-10-05 by the finale builder (overnight, worktree branch off `0cc5b7e`). The job was "the HQ interior,
Hoopa's cradle, the confrontation with Elara and Brann, the release, and `rift_crisis_resolved` set at the stage
that ends the crisis". **Most of it was already built.** This file is the chain as it stands, what was missing, what
this build changed (two dialogue lines; no blocks, entities or functions), and what is still unproven.

## 1. Premises the brief carried that are wrong

| Relayed | Measured |
|---|---|
| "Hoopa's cradle is reserved and unbuilt" (`docs/STATE.md`, the relic site line) | Carved since 2026-10-03: `data/relic_underground.json` `geometry.cradle.carve: true`, centre (3357, 3306), floor y12, radius 16, dome y24-28, 300 dressing blocks (dais, four copper pylons, restraint ring y21, chains, five consoles, eight pillars, floor lights). `tools/relic_underground.py build` reports it; `relic_underground_audit` CLEAN this session |
| "`rift_crisis_resolved` has a setter nothing invokes until the release scene exists" (STATE "Mainline reveal runtime"; `data/relic_underground.json` `zone.pass.why_not_the_finale_flag`) | Invoked: `dlg_main_relic_hall_release` `release_001` runs `unlock_league_after_rift_resolution`, whose first effect is `function cobblers:flag/rift_crisis_resolved/grant` |
| "the confrontation" is to build | Built 2026-10-04/05: Brann and Elara are Cobblemon NPCs who talk and fight (`data/hq_tower.json` `npcs`, `fights`; teams `data/finale_trainers.json`) |

## 2. The chain (every coordinate from the data files named; stages are `quest.main_worldshift_reveal.stage`)

The mainline beats leave the player at **`rift_crisis_pending`**: written by the Rift surveyor's `rift_007`
(`record_rift_crisis_pending`, from `giovanni_reveal_complete`) at (3552, 112, 5334), or by
`carry_by_gym8_cleared_to_rift_crisis_pending` when an Earth Badge holder opens Nia's conversation.

| # | Where | Who / what | Reads | Writes | Mechanism | Built by | Offline proof |
|---|---|---|---|---|---|---|---|
| 1 | HQ ring-0 iron door (3443, 67, 3282) | Compact guard (3444, 67, 3283), `dlg_main_relic_hq_guard` | `rift_crisis_pending` or later | `cob_admit_relic` = 1 | "Go through." -> `relic_hq_admit` -> tp (3440, 67, 3282) | `relic_underground.py`, R18RU | `deep_walk_audit` (guard edge) |
| 2 | Clinic, ring 2 (3536, 33, 3344) | Nia Calder, `dlg_main_finale_nia` | `rift_crisis_pending` | `deep_handoff_received` | `nia_006` -> `record_deep_handoff_received` | `hq_tower.py` R18HQ | `finale_audit`; on foot from the HQ's front step (this session, below) |
| 3 | Tower door (3439, 67, 3306) | Director Elara Venn, `dlg_main_finale_elara` (door keeper) | `deep_handoff_received` or later | nothing | "Let me through." -> `elara_door_admit` -> tp (3436.5, 67, 3306.5) | `hq_tower.py` R9HQ/R18HQ | `finale_audit` door keeper, `hq_tower_audit` |
| 4 | Briefing hall hq_s1 (3431, 74, 3305) | Captain Brann Saye, `dlg_main_finale_brann` | `deep_handoff_received` | `brann_defeated` then `hq_crossed` | "I'm not leaving." starts his battle; the win runs `won_brann` (battle_victory callback); `brann_005` -> `record_hq_crossed` | `hq_tower.py` | `finale_audit` |
| 5 | Climb gate, box x3429-3437 y79-133 z3304-3312 | gate cycle | `hq_crossed` or later | - | set back to (3430.5, 74, 3305.5) | `hq_tower.py` | `finale_audit` gates (126 players) |
| 6 | Anchor control hq_s10 (3433, 128, 3307) | Oren Pell, `dlg_main_finale_oren` | `hq_crossed` | `anchor_shutdown` | "Run the marked sequence." -> `record_anchor_shutdown` | `hq_tower.py` R18HQ | `finale_audit` |
| 7 | Tower door (3439, 67, 3306) | Elara | `anchor_shutdown` | `elara_defeated` then `cradle_open` | "Then I'll take it." starts her battle; the win runs `won_elara`; `elara_006` -> `record_cradle_open` | `hq_tower.py` | `finale_audit` |
| 8 | Out of the tower | doorway hole (3438, 67, 3306) | - | - | tp to (3441.5, 67, 3306.5), the corridor | `hq_tower.py` | `hq_tower_audit` |
| 9 | Corridor -> room -> stair head (3429, 66, 3299) -> records room x3422-3428 y1-4 z3301-3310 | lit switchback stair | - | - | on foot | `relic_underground.py` R9RU | walked from (3441, 67, 3306), this session |
| 10 | Knock box x3422-3424 y1-3 z3305-3307 | relic zone | eight gym flags AND `cob_admit_relic` | `cob_pass_relic` | zone check | `relic_underground.py` | `relic_underground_audit` |
| 11 | Passage -> hall (3390, 8, 3262) -> cradle (3357, 12, 3306) | - | - | - | on foot | R9RU | `relic_underground_audit`; `finale_audit` (932 of 985 cradle cells) |
| 12 | Cradle, fifth stand (3363, 13, 3312) | Compact binder, `dlg_main_relic_hall_release` | `cradle_open` AND `brann_defeated` AND `elara_defeated` | **`rift_crisis_resolved`** (advancement, this player), `rift_released`, `league_cursor` = `league_001` | "Release Hoopa." -> `release_001` -> `unlock_league_after_rift_resolution`; last effect `release_fx` (particles and sound at (3357.5, 17, 3306.5), for the releasing player only) | `relic_underground.py` R18RU | `finale_audit` |
| 13 | z5, the League's precinct; G5 (3573, 85, 2680), knock box x3571-3576 y85-86 z2680-2682 | zone check | `cobblers:flag/rift_crisis_resolved` | `cob_pass_z5` | `z5/zone`: a flag holder is admitted on entry, no teleport (`qualify on entry`); the knock box also grants | `rift_zones.py` R9Z | `finale_audit` (z5 executed) |

The stage that ends the crisis is `rift_released`, written by the same transition that grants the flag, after the
grant. Nothing else writes `rift_released` or grants the flag (`finale_audit`'s sweep of every built pack).

## 3. What was missing, and what this build changed

Gaps found walking the chain as a player who has not read the data:

1. **Nothing at the HQ named Nia.** At `rift_crisis_pending` the guard admits the player (step 1) and Elara turns
   them back (`door_001`/`door_002`, Codex's lines, unchanged). Nia's handoff is the next stage and no line a
   `rift_crisis_pending` player hears at the HQ said where she is; the surveyor's lines (another agent's beat, not
   edited) do not name her either.
2. **The binder sent a player to the wrong room.** `confront_003` said the Director "keeps the shaft interlock in
   her office"; Elara moved to the tower's door on 2026-10-05.

This build writes **only `data/dialogue.json`**:

| Conversation | Node | Change |
|---|---|---|
| `dlg_main_relic_hq_guard` | `admit_pending` (new) | entry rule priority 5, `stage == rift_crisis_pending`; a line naming Nia's clinic "two rings down, south-east of here", then `next: admit` (the unchanged choice) |
| `dlg_main_relic_hq_guard` | `turned_away_2` | "Nia Calder at the clinic" -> "... at the clinic two rings down" |
| `dlg_main_relic_hall_release` | `confront_003` | the Director "holds the tower's door herself ... only Nia Calder's packet gets you past her" |

Both new texts carry a `placeholder` key naming them as Claude's, for Codex to replace. Directions measured: the
guard (3444, 67, 3283) to Nia (3536, 33, 3344) is +92 x, +61 z (south-east), ring 0 (tread y66) to ring 2 (y32)
(`data/rift_deep.json` `rings.treads`).

**Compiled into:** `build/datapacks/cobblers_dialogue/data/cobblers/dialogues/dlg_main_relic_hq_guard.json` and
`.../dlg_main_relic_hall_release.json` (`python tools/compile_dialogue.py --all`: 107 conversations). **No block,
entity, function, advancement or NPC placement changes.** The NPC ids and conversation ids are unchanged, so no
placement step re-runs.

**Tests:** `tests/test_finale_wayfinding.py` (10): at each stage, the person met names the next stop (guard -> Nia;
binder -> door and Nia; Nia -> HQ door; Elara -> briefing hall; Brann -> anchor control and the door; Oren -> Elara at
the door; Elara at `cradle_open` -> the passage), no finale line places Elara "in her office", and the pointer leads
into the guard's admit choice. `tests/test_hq_tower.py::test_the_relic_door_guard_still_admits_from_rift_crisis_pending_on`
now picks the admit rule by node, not by list position.

## 4. Offline verification run this session (worktree, packs built here)

Built: `cobblers_dialogue`, `cobblers_progression`, `cobblers_hq_tower`, `cobblers_rift` (R1),
`cobblers_relic_underground`, `cobblers_rift_zones`, `cobblers_deep_city`, `cobblers_deep`, `cobblers_vr_caves`,
`cobblers_arena_dome`, `cobblers_trainers`.

- `tools/finale_audit.py`: **0 problems** (6,426 conversation start states; story walk reaches every stage
  `rift_crisis_pending` -> `rift_released`; Elara's door 1,449 actions; cradle 932 of 985 cells reached; jar checked).
- `tools/hq_tower_audit.py`: **0 problems**. `tools/relic_underground_audit.py`: **CLEAN**.
- `tools/deep_walk_audit.py`: 2 problems, both "no built pack" (`cobblers_habitats`, `cobblers_signs`), not built here.
- A walk with `deep_walk_audit`'s Walker over the same replayed packs: from the HQ's front step (3444, 67, 3282) the
  player reaches Nia's cell (3536, 33, 3344) **on foot** (310,865 cells walked; nothing else checks her stand: she is
  not in a tower storey, so `hq_tower_audit` H4 skips her); from Elara's out cell (3441, 67, 3306) they reach the stair
  head, the records room, the knock box, the hall and the binder's cell (3,583 cells). A scratch script, not committed.
- Tests: `test_finale_wayfinding` 10, and 209 passed over `test_compile_dialogue`, `test_compile_dialogue_all`,
  `test_finale_confrontation`, `test_hq_tower`, `test_finale_audit`, `test_hq_tower_audit`, `test_progression_pack`;
  `test_relic_underground` 29 passed.

## 5. Hoopa: no actor, and why (measured)

Codex's Scene 5 wants a restrained Hoopa actor that disappears on release, gated by Codex itself on "model/form must
be verified in the installed pack". **Measured 2026-10-05 in `Cobblemon-fabric-1.8.0+1.21.1.jar`:** Hoopa has species
data (`data/cobblemon/species/generation6/hoopa.json`, form Unbound), a dex entry and two sounds, and **no model and
no texture**; its species file has no `implemented` key, where Bulbasaur's reads `true` beside its two `.geo.json`
models (the jar holds 1,284 models, none Hoopa's). So in Cobblemon 1.8.0 Hoopa is unimplemented and a spawned one
draws as a placeholder. **No actor was built** (no `data/scenes.json` scene): a placeholder doll at the climax is worse
than the restraint's light and sound (`release_fx`). Not checked: whether another mod or resource pack in our set adds
a Hoopa model (only the Cobblemon jar was available); one `/pokespawn hoopa` glance settles it.

## 6. To put it in the world

This build only: prepare's dialogue compile, `install` of `cobblers_dialogue`, a restart. If staging lacks any of the
finale (not read from the world by this build): R9B, R9DC, R9RU, R9HQ (blocks, in that order), R17
(tower trainers), the restart that loads `cobblers_dialogue`'s NPC classes, then R17N, R18RU, R18HQ, and R9Z for z5.
Then `install_check`, `presence_audit`, `npc_seats.py verify`.

## 7. In-game checks (none of this has been seen)

1. At `rift_crisis_pending`, talk to the guard (3444, 67, 3283): the Nia line, then "Go through."; Elara at
   (3439, 67, 3306) turns you back.
2. Walk to Nia (3536, 33, 3344): her handoff; back to Elara: "Let me through." puts you at (3436.5, 67, 3306.5).
3. Beat Brann (3431, 74, 3305), talk again: the stair above y79 opens. Oren (3433, 128, 3307): "Run the marked sequence."
4. Down and out through the doorway; beat Elara; talk again: `cradle_open`.
5. The stair at (3429, 66, 3299) to the records room, the passage, the hall, the cradle; the binder (3363, 13, 3312):
   "Release Hoopa." Then `/advancement test @s cobblers:flag/rift_crisis_resolved` and the particles at the ring.
6. Walk north into z5 without knocking at G5: no turn-back.
7. A second player at an earlier stage at each step: nothing of the first player's moves them.

## 8. Recorded, not chased

- `docs/STATE.md`: the relic site line ("Hoopa's cradle ... reserved and unbuilt") and "Mainline reveal runtime"
  ("a setter that nothing invokes") are stale; so are `docs/world-building/CRITICAL_PATH_WALK_2.md` item 10, REVIEW 16,
  and `data/relic_underground.json` `zone.pass.why_not_the_finale_flag` ("NO SETTER ON ANY BRANCH"). Its
  `needs.upgrade_path` ("when a setter exists") is now actionable: the relic zone could also accept the flag.
- `tools/rift_skin.py` (`build`, line 489) and `tools/rift_deep.py` crash with `TypeError` on `Path(None)` when
  `--source-root` is omitted: neither resolves the root through `terrain.env_source_root()`, and
  `tests/test_source_root_fallback.py` does not catch them.
- Codex's "one release advances every eligible player" is not built: each player confronts and releases for
  themselves (`geometry.release.not_built`). Review 78 (Elara's re-entry at `anchor_shutdown`) and "HQ loss as a
  blackout?" wait on the owner.
