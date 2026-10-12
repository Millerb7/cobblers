# EXP-091: Do the Haven Compact's story fights (CP-04, CP-12, CP-14) run in game, and do their unproven forms?

**Status: STUB, NOT RUN (2026-10-11).** Built offline by unit CP-CORE: `tools/compact_points.py`,
`data/compact_points.json`, `data/compact_trainers.json`, the records it splices into `data/`, the pack
`cobblers_compact` and reapply step R18CP. Nothing here has been in a server. Grade it with `qa-reviewer`, not the
builder.

## Objective

Part A proves what is BUILT: sixteen Cobblemon NPCs on the overworld (four above Highwire, seven on Cinderlee's
crater flat, five on Holdfast's southern shelf), ten of which talk and then fight through the dialogue's
`npc_battle` (`q.npc.start_battle(q.player, 'singles')`), each win written into the winner's data by the
`cobblers_compact` battle_victory callback, and CP-12's Field Commander granting `crater_operation_stopped`.

Part B is the stub for the design's UNPROVEN forms, built as fallbacks (`docs/story/HAVEN_COMPACT_PASS.md` section 4):

- **X2, a squad spawned per player** (M3): CP-04's four and CP-12's four existing only for a player at the stage, the
  next leg spawned on a win (`tools/arena_runtime.py`'s spawn-start-callback chain, triggered from a story zone). The
  fallback built is static shared NPCs gated per player.
- **X3, doubles and multi**: CP-14 as the player and a watch officer against two loyalists (multi); CP-11's and
  CP-03's doubles (not this unit's). The fallback built is two singles with the sergeant's line between.
- **No heal between fights**: not enforced by anything; the X2 chain (the next opponent spawned by the win's
  callback) is the only route to it that does not need a mod (EXP-078's chain part is still OPEN).

## Success criteria

Part A, each a PASS or FAIL with what was seen:

1. After R18CP: `python tools/compact_points.py verify` reports 16 of 16 (one NPC per seat, on a solid block,
   facing its yaw), and `python tools/presence_audit.py --only extra` finds every `compact_*` probe.
2. Each NPC renders as a person and shows its name (`cobblemon:standard`).
3. A player at `pallet_complete` hears every NPC's `before` line and is offered no battle.
4. CP-04 at `misty_reveal_complete`: courier 1's choice starts a battle; a WIN writes
   `quest.evt_compact_records_run.courier_1_defeated` (read back with `runmolang` or the next conversation opening
   on its `after` state) and shows the actionbar line; courier 2 then offers its battle. Varga's post-win talk sets
   `records_recovered`.
5. A LOSS blacks the player out as any battle does, writes nothing, and the next talk reopens on the choice.
6. Two players: one wins against courier 1, the other (also at the stage) is still offered the battle; and what
   happens when the second starts a battle while the first is still in one against the same NPC (record it).
7. The over-cap refusal: a party over the RCT cap is shown the `*_over_cap` line, not a battle.
8. CP-12 at `sabrina_reveal_complete`: Tomas, then Oren, then the three guards in any order (each post-win talk
   shuts its anchor), then the Commander; after his win, `crater_operation_stopped` is held
   (`/advancement` or the analyst's `blaine_repeat`). A second player who first heard the crater analyst finds CP-12
   closed (`*_closed_1`).
9. CP-14 at `blaine_reveal_complete`: Nia, loyalist 1, the sergeant's line, loyalist 2, the sergeant keeps the packet.

Part B: none run; each needs its own probe pack first (X2 by `minecraft-systems-dev`, X3 by `cobblemon-researcher`
then the main session).

## Dependencies

`cobblers_dialogue` (compiled with the 16 classes, fighters carrying their parties) and `cobblers_compact` installed,
a restart so the classes load, R18CP run. The staging world only, never the live one. X1 (Brann's `npc_battle` in
the HQ) tests the same dialogue route on a fight that already exists.

## Implementation

`tools/compact_points.py` (its docstring), `data/compact_points.json` (`mechanism`, `fallbacks_built`,
`open_questions_defaults`, `multiplayer`).

## Test instructions

Staging, after `install` and a restart: `python tools/reapply.py run --only R18CP`, then the probes above with two
accounts. Set a stage with `runmolang` on `q.player.data()` (the key is `cobblers__quest__main_worldshift_reveal__stage`).

## Results

Not run.

## Limitations

The seats were chosen on the heightmap and a sweep of every coordinate in `data/`; a mod's or a donor's entity
near a seat would only be seen in the world (criterion 1).

## Decision

None yet.

## Follow-up

Owner questions O1-O10 (`docs/story/HAVEN_COMPACT_PASS.md` section 5); the defaults used are in
`data/compact_points.json` `open_questions_defaults`.
