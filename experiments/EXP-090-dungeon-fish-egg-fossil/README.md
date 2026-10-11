# EXP-090: the fishing pool, the egg vendor and the fossil bay of the dungeon rooms (RT-B)

**Status: DESIGNED 2026-10-10, NOT EXECUTED.** Built and simulated offline (`tools/dungeon_extras2.py`,
`tests/test_dungeon_extras2.py`); nothing here has run in Minecraft. The number is RT-B's pick for a stub; renumber it if
another unit took it.

## Objective
`docs/research/notes/dungeon-room-mechanisms.md` sections 1-3 named the mechanisms for three of the owner's new rooms and
left their in-game halves open. The rooms are built from those verdicts (`docs/mechanics/DUNGEON_ROOMS.md` section 11):
a **fishing_room** whose fish come from a boxed `spawn_pool_world` file keyed to a band marker block, an **egg_room** whose
vendor gives eggs with `givepokemonegg` run as the player from a function, and a **fossil_chamber** dug with the rift pick
(no brushing). "Yes" lets the three dungeons carry them; "no" names which mechanism to swap (a Habitat Block for the pool,
a different vendor interaction, a `can_place_on` brush).

## Success criteria
F = fishing, E = eggs, D = dig. Each is observable in game or in the log.
- **F1 (the pool fires).** In a fishing room, 100 casts with a Poke Rod (the lent one) show ONLY the species of the
  entrant's band in `data/dungeon_extras2.json` `fishing.species.<theme>.<band>`, at levels `10..lower cap` of the band.
  Stock fishing species (Magikarp, Tentacool...) never appear (the pocket's biome is `the_void`).
- **F2 (the band marker).** The same room entered at two bands (use `PLAYTEST_TAG`) yields the two bands' tables; a
  bare band-1 shell (no slot reset) yields band 1's. `/execute in cobblers:pocket run data get block <marker cell>`
  confirms the marker the reset set (cells in `experiments/.../results.md` once run).
- **F3 (one-deep water).** A bobber cast onto the one-deep pool bites and spawns. If it does not, the fallback is a
  two-deep pool with a stair ramp (the walk check forbids a deeper pit today).
- **F4 (a land starter).** Is the wanted starter (Mudkip, Totodile, Squirtle, Froakie...) catchable and does it swim, or
  does it drown? (Research question 2: the pool holds only water starters and their lines.)
- **F5 (empty bucket).** Over 200 casts, how many produce nothing? (Research question 3; each band has a species in every
  bucket, so the expected answer is none.)
- **F6 (the box).** Does the pool fire when the spawn file's box and `dimensions` are present together with
  `neededNearbyBlocks`? If a box is ignored the marker alone still confines the pool; if `neededNearbyBlocks` is ignored by
  the fishing context the pool fires at EVERY bobber in the pocket (a failure: switch to a Habitat Block).
- **F7 (the pack reload).** `/reload` after installing the dungeon pack: does the pool start firing without a restart?
- **F8 (the lent rod).** The rod is in the pack after the first step in; it is gone after the far rip, the back rip, a
  death-exit and a logout-and-return.
- **F9 (a fished catch weighs).** A caught fish raises `dg.gp` by the nest value of the band (100-200 cp).
- **E1 (the command from a function).** The vendor's button gives an egg of the named species into the player's pack; the
  egg item shows the species and a timer. Console log has no permission error.
- **E2 (the dialogue).** A `cobblemon:npc` class with only an `interaction` dialogue opens it in the pocket, shows every
  offer's name and description, runs the button's function, and closes. `isInvulnerable` holds against a sword.
- **E3 (one a run; the clock).** A second click gives nothing and says so; the clock falls by the band's price once; the
  bar's "taken" figure rises by the nest value once; with less than price + 60 s left the sale is refused and nothing is
  charged.
- **E4 (hatching).** The egg hatches in the pack as the player walks (about ten minutes at the default multiplier is
  ASSUMED, not read), into the party at a sensible level; with a full party the egg does ... (record it).
- **E5 (the reset).** The slot reset removes the vendor; the next run's first step in spawns a vendor of that run's band.
- **D1 (the pick breaks it).** The rift pick breaks the dig block (terracotta / clay / sandstone) and calcite in the
  bay in adventure mode and nothing else in the room; `minecraft.mined:minecraft.calcite` rises (`/scoreboard players get`
  on `dg.m<index>` in the arrival function's objectives).
- **D2 (the dust).** The dust drifts in front of the face above the hidden fossil and is visible from 6 blocks.
- **D3 (the fossil).** Within a second of the calcite breaking the player holds one fossil of the band's table, the
  actionbar speaks, the room is cleared (`dg.rs` 2), and the bar's "taken" figure rises by 300 cp.
- **D4 (the re-arm).** After the slot reset the bay is whole and the next run rolls a spot again (eight runs show at least
  four different spots).
- **D5 (no hole).** Breaking every dig cell of the bay opens no way into the void or another room.
- **D6 (the brush control).** Not part of the build; the research's brush-with-`can_place_on` experiment (section
  "Unknown", item 4) remains open and independent: this room does not depend on it.

## Dependencies
Cobblemon 1.8.0 (spawn pools, NPC dialogues, fishing), Cobbreeding 2.3.0 (`givepokemonegg`, read from the jar: literal,
`player` and `properties` arguments, permission `command.cobbreeding.egg.give`), the dungeon engine (`tools/dungeon.py`) and
the room kit, GREED (`data/dungeon_greed.json`), staging with a dungeon pack installed (an install and a boot are the
integrator's, not this unit's).

## Implementation
- `tools/dungeon_extras2.py`, `data/dungeon_extras2.json`, `tests/fixtures/dungeon_extras2_rooms.json`,
  `tests/test_dungeon_extras2.py`; hooks: `tools/dungeon_rooms.py` EXTENSION_MODULES, `tools/dungeon.py` build()
  (`DX2.pack_files`, `DX2.patch_functions`), `tools/dungeon_greed.py` CATCH_ALIAS, `data/dungeon_greed.json` (the `fossils`
  group, calcite and the three dig blocks), `tools/dungeon_independent_audit.py` (a fossil bay is skipped like a seam).
- Room records: `{"kind": "fishing_room"|"egg_room"|"fossil_chamber", ...}`, width at least 25 / 13 / 11, length at least 17 / 19 / 21.

## Test instructions
1. Author the three kinds into a dungeon record (or use `tests/fixtures/dungeon_extras2_rooms.json` as a demo
   dungeon), `python tools/dungeon.py` build, install to staging, restart (NPC classes and the spawn pool load at boot).
2. As an OP player with a sigil of the band under test (or tagged `PLAYTEST_TAG`), enter, walk to each room, and do the
   criteria above. For F1 count casts with a small script reading the log of `/data get entity` of the spawned Pokemon, or
   watch and tally by hand.
3. For F7 install the pack while the server runs and run `/reload`; for F2 repeat at another band.

## Results
None yet.

## Limitations
One player (solo slots). The sim models blocks, `random value`, NPC spawning and `givepokemonegg` as a recorded call; it does
not know whether a bobber spawns, whether the command works from a function, or how a dialogue renders.

## Decision
Open.

## Follow-up
Per result: F3 fails -> a two-deep pool with a ramp (a kit change), F6 fails -> a Habitat Block with a pure-fishing pool
(`docs/research/notes/dungeon-room-mechanisms.md` section 1, option 1), E2 fails -> an interaction entity and an
advancement (the rips' form). The balance designer tunes the egg prices, the fossil's 300 cp and the species tables.
