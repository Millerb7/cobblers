# Rift-zone gatehouses: ready to apply (2026-10-02)

Owner of the work: `minecraft-systems-dev`, branch `build/2026-10-02-consolidation` (worktree agent). Nothing
here ran in Minecraft. Everything below was measured from the emitted `.mcfunction` text and the canonical
heightmap (`tools/ground.py`), or read from the code.

## Which premise was true on this branch

`docs/STATE.md` ("What is open", the Rift Z1-Z5 item) is **stale**. It says `cobblers_rift_zones` is in
`tools/reapply.py` EXCLUDED and R9Z is withdrawn. On `dcb9f67` neither is true and has not been since
`5680f8c` (2026-09-30): the EXCLUDED entry was renamed `_cobblers_rift_zones_was` (a dead key), the pack is in
SERVER_PACKS and WORLD_LOCAL, and R9Z runs the zones that declare nothing owed (z1, z2), holding z4 and z5 by
their `needs_*` fields. `docs/HANDOVER_SOUTH.md`'s batched apply listing R9Z is the correct one.

## Rung

Rungs 5-6 only (datapack data and functions; `minecraft:location` advancements and their reward functions),
exactly as before. Nothing new: no tick driver, no scripting, no companion.

## What was wrong, and what changed

1. **The held zones' zone checks shipped anyway** (`measured_defects[held_zone_checks_shut_the_league]`).
   R9Z held z4/z5's walls and gatehouses, but `build` still wrote `z4_zone`, `z5_zone` and their knock and
   exit advancements, and `install` copies the whole pack. A zone check acts on its own, so installing the
   pack turned every survival player back from **the League's precinct** (z5), whose pass nothing can grant.
   Now `build` emits no advancement for a zone `held_zones()` names; its functions stay (dialogue can call
   `grant`), and `reapply.held_functions()` holds them as deliberately unreferenced. `build` also empties the
   pack directory first: its clean-up loop was a no-op, so stale files survived in `build/` and were installed.
2. **The boxes were crossed, not stood in** (`measured_defects[gate_boxes_are_crossed_not_stood_in]`). Knock
   box now covers t = -2..0 (the guard's own column, where a walker rests against the barrier); exit box is the
   walkway column directly behind the barrier (2 in, was 5 in, between the arrival and the zone). The walkway
   keeps its inner end (`gatehouse.walkway_in` = 6). `report` now requires the knock box to cover the guard.
3. **The mouths did not meet the ground** (`measured_defects[gatehouse_mouths_do_not_meet_the_ground]`).
   Each gate record carries `approach`, measured by `trace` from the heightmap: from each mouth, one block up
   or down per column, cut or bridged, until the ground is within a block; the mouth column always laid (it
   clears the stale pre-B12 obsidian at the rim post's inner mouth on staging). Before: Victory Road descent
   post and G5 inner mouth +1 (passed player trapped under the roof), wilds slip outer +5 (knock box
   unreachable) and inner +2 over a six-deep crack.
4. **Placeholders**: moved into `rift_zones/guards` (force-load, 40 t, summon `_new`, 100 t, kill every other
   guard stand on the block), run by R9Z after the shells. A kill in the gatehouse function could not see saved
   entities. Clears G2's old stand at the descent post.

`trace` was re-run; apart from the new/moved places and `approach` it reproduced the file byte for byte.

## Tests

- `tests/test_rift_zones_apply.py` (new, 8: 7 pass, 1 strict xfail): no advancement for a zone that cannot
  grant (grantability read from `data/progression.json`, not from the generator), with a mutation proof;
  held zones == zones that cannot grant; R9Z runs no wall or gatehouse of such a zone; one placeholder per
  built gate; **every gatehouse R9Z builds walks** (outside to knock and back, arrival into the zone, zone to
  exit) over the heightmap with the throat wall up, with a mutation proof (dropping the approach from `build`
  breaks the descent post and the wilds slip by name); the held zones with their walls up as a strict xfail.
- `tests/test_rift_zones.py`: 72 pass. Edited by the implementer, flagged for review: a `shell_voxels()` helper
  drops the data-declared approach columns before the shell checks, which read one level and expect a roof.
- Also run: `rift_zones.py report` (0 problems, 3 owed), `walkable` 7/7, `tools/b12_independent_check.py` 7/7,
  `function_limits` 50 files 0 problems, `reapply.unreferenced/uncovered` empty for the pack.
- Scratch, not a test: the 2026-10-01 pack rebuilt from `92da469` with the new R9Z laid over it: all five
  built gates walk.

## The apply

`prepare` (rebuilds the pack), `install` (replaces `cobblers_rift_zones` in the world's datapacks: this is what
removes z4/z5's zone checks), then `run --only R9Z`. R9Z = `wall_throat`, `gatehouse_z1`, `gatehouse_z2`,
`gatehouse_z2_victory_road_descent`, `gatehouse_z2_rim_post_descent`, `gatehouse_z2_wilds_slip`, then
`guards` + wait 8. Held, must stay held: `wall_behind_league`, `wall_league_gate`, `gatehouse_z4`,
`gatehouse_z5` and every z4/z5 function.

## Owed, and owner calls

- z5 needs `rift_crisis_resolved` declared in `data/progression.json` with a setter (another agent); z4 needs
  Codex's caught_count dialogue. When either lands, remove that zone's `needs_*` field;
  `test_the_held_zones_are_exactly_the_zones_that_cannot_grant` fails until you do.
- **Before releasing either:** `measured_defects[held_walls_do_not_meet_their_gatehouses]`. behind_league runs
  4-5 blocks outside G4's outer mouth, so G4 stands behind its own wall; league_gate runs lengthwise along G5's
  walkway. A siting decision (move a guard or re-cut a wall).
- The throat wall has no gate in it by design (z1 and z2 each have their own); nobody crosses the throat.
- The wilds slip sits on broken ground (a 3-column cut out, a 4-column cut/bridge in). Re-siting it is the
  owner's call.
- In game: walk each built gate both ways; check one placeholder per guard; check z5 does not turn you back.
