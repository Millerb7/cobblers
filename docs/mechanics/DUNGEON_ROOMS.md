# Dungeon rooms: the kit full-length dungeons are built from

Status: built and tested on the simulator, not yet run in Minecraft. Mechanism rung: **datapack plus generator**
(`tools/dungeon_rooms.py`, `tools/dungeon_kinds.py`, `tools/dungeon_grid.py`, `data/dungeon_themes.json`), on the
engine of `DUNGEONS.md`; nothing needed a scripting layer or a mod, and the earlier rungs (native, addon, config) have
no say over blocks in a custom dimension. Written 2026-10-09 after the owner played the placeholder Night Shift
("That was it?"): the engine was a skeleton, an entry room, 60 blocks of 5-wide drift, an arena and an exit.

## 1. The record

`data/dungeons.json`, `dungeons[]`: a dungeon with `"theme": "<id>"` and `"rooms": [...]` is built by the room kit. One
without `rooms` still builds from `spine.segments` exactly as before (`night_shift` moved to rooms in wave 2, DG-NS; its
old placeholder spine is kept as `tests/fixtures/dungeon_legacy_spine.json` so the spine path stays tested).

```
{"id": "d1", "kind": "drift", "length": 36, "width": 11, "height": 6, "rise": 0, "gate": "open",
 "params": {"exit_dz": 4}}
```
`length` counts both end walls and is along the walked path; `width` is the interior (at most 62, the strip's 64 less
two wall columns); `height` is clear height above the room's highest floor; `rise` is the floor change across the
room (only `drift` and `stairs` may have one; a staircase of one-block steps); `gate: "cleared"` keeps `door_out`
shut until `room/<dungeon>/<room>/clear` runs (default `open`; a `boss_arena` defaults to `cleared`). `params.exit_dz`
bends the walked line in z (the next room's door is that far over). Rooms are laid along +x with their own end walls;
consecutive rooms share a door: 3 wide, 4 high, two wall columns deep, exactly equal in `door_out` and the next
`door_in`. A connector (`drift`, `stairs`) is at most 40 long and at least 7 wide (`problems()` refuses otherwise).
First room `entry_room`, last `exit_room`, exactly one `boss_arena`; the engine reads the board, the threshold, the
boss spot and the far rip from them (`dungeon.points()` returns the same keys for a rooms dungeon).

## 2. Themes (`data/dungeon_themes.json`)

Three: `mine`, `jungle`, `flooded_ruin`. A theme names the hull (wall, floor, ceiling, light and its spacing), the door
(gate, frame, lintel), the rip, and a `dress` list of ops run in order over each room, plus the blocks the kinds need
(`maze`, `parkour`, `bridge`, `seam`, `safe`, `dark`). Rules the tests enforce: every hull block opaque (the pocket has
noon skylight), no gravity block, no concrete, no hazard, nothing the rift pick can break outside the seam, one-deep
water only, every id present in the 1.21.1 jar. A dress op has a `level` (`light` runs everywhere a theme dresses;
`full` places obstacles and only runs in rooms whose kind is dressed `full`, off a trail kept clear for the player), may
carry `kinds` / `not_kinds`, and `lit: true` if it emits light (a dark room skips it). Ops: `base_course`, `pillars`,
`timber`, `streak`, `floor_strip`, `floor_patches`, `ground_cover`, `trunks`, `canopy`, `wall_vines`, `stream`,
`columns`, `piles`, `glow_vines` (glow berries hung from the canopy to 4 over the floor: a room taller than about 11 cannot be lit from its ceiling; the jungle uses it). New ops register with `register_dress(name, fn, level)`. A theme may opt in to
`hull.tall_lights` (`block`, `every`, `under`; the ruin does): a room whose ceiling lattice would have to be closer than
`under` to reach its floor is lit from the floor course instead (`floor_lights`, a light block every `every`, moved to the
nearest open floor cell when covered), keeps a sparse ceiling lattice at `light_every`, and any standable cell neither
reaches gets the theme's own dressing block under it turned into the light, else a light in the ceiling over it
(`cap_dark_dressing`; never a kind's block). Without the key a theme lights exactly as before.

The jungle is dense on purpose (the owner's word): jungle and mangrove logs floor to ceiling off a zig-zagging trail
(one cell in five), two layers of leaves with holes, hanging curtains and froglights as the ceiling, vines on trunks
and walls, ferns, tall grass, moss and big dripleaf on a floor of grass, podzol, moss and mud, a stream to wade, and a
maze of azalea and leaf hedges. The mine is cobbled deepslate with a timber set and a chained lantern every eight
blocks, streaks of raw ore (never ore), rubble and a track laid in the floor as polished blocks and sleepers (not rail
blocks). The ruin is mossy and cracked brick over prismarine, dim, with wading channels and pools, kelp, seagrass and
sea pickles, columns standing, broken or lying down.

## 3. The interface (`tools/dungeon_rooms.py`)

| Call | Returns |
|---|---|
| `plan(doc, d, slot)` | rooms: the record's fields plus `xa..xb/za..zb` (walls included), `ix0..ix1/iz0..iz1` (interior), `box` `[x0,y0,z0,x1,y1,z1]` inclusive interior, `floor_y`, `floor_in/floor_out`, `z_in/z_out`, `door_in`/`door_out` boxes (`None` at the ends), `pit`, `y_lo`, `ceil_y`, `floors` and `anchors` |
| `layout(doc, d, slot)` | the same without anchors (geometry only) |
| `gate_lines(doc, room, open_)` | `fill` lines for `door_out`, pocket context (the caller adds `execute in`) |
| `register(name, fn, **flags)` | a kind: `fn(doc, d, slot, room, theme) -> {"blocks": [op], "anchors": {}, "functions": {}}`; optional `"lights"`, `"reserve"` (boxes kept clear), `"meta"` |
| `declare_kind(name)` | a kind named before it exists: builds as a themed room with its anchors, `warnings()` lists it |
| `EXTENSION_MODULES` | `dungeon_kinds`, `dungeon_fights`, `dungeon_puzzles`: imported at load, absent ones skipped. A wave-2 module registers its kinds on import and edits nothing here |
| `EXTRA_CHECKS` | append `fn(doc, d, slot) -> [problem]` to add kind checks to `problems()` |

An op is `("fill", box, block[, "keep" | "replace <block>"])` or `("set", pos, block)`; `fill(...)` and `setb(...)` build
them. Kind flags: `dress` (`none|light|full`), `rise`, `connector`, `pit` (blocks of drop to a catch floor), `no_deploy`,
`jumps` (the walk check may jump), `dark`, `length_snap`/`width_snap` (`(pitch, offset)`).
Kinds are deterministic: `rng(d, room, salt)` depends on dungeon and room ids, never the slot, so the four slots are one
dungeon (tested).

**Hooks.** A kind's `functions` keys `enter`, `clear`, `reset`, `tick` are merged into the generated room functions;
any other key becomes its own function. Names are `cobblers:dungeons/room/<dungeon>/<room>/s<g>/<name>` (`g` the global slot number, as in `shells/s<g>`: the audit reads `/s<g>/` as the slot):

| Function | Runs | Context |
|---|---|---|
| `enter` | once per run, the first keeper pass a member's box meets the room's | as the member, at them. Guard is `#s<g>r<i> dg.rs` 0 -> 1 |
| `tick` | every keeper pass the member is in the room, clock running | as the member |
| `clear` | when called; opens `door_out` (if `cleared`), cues, sets `dg.rs` 2; idempotent | any context; carries `execute in` for blocks |
| `room/<dungeon>/<room>/clear` | the same as a member, dispatching on `dg.slot` | as the member |
| `reset` | at the slot's reset (`reserve`), state back to 0, gate shut, mutables restored | as the entrant, in the pocket, force-loaded |

State is the objective `dg.rs`, holder `#s<g>r<i>` per room (0 not entered, 1 entered, 2 cleared) and `#s<g>r<i>m<j>`
per seam block; `dg.ck` is the member's last parkour ledge. The slot reset (`slot/s<g>/reset`) calls every room's reset.
A member's band is `dg.band`, their clock `dg.clock` (quarter-ticks, 80 a second at x1).

**Anchors** are block coordinates `[x, y, z]` or `[x, y, z, yaw]` (the thing stands at +0.5; yaw 0 faces south, 90
west, -90 east, 180 north), lists of those, or 6-int boxes (`line`, `arena`, `catch`, `seam_box`, `span`). Every point
anchor is checked reachable by the walk check (the cell, or the one or two below it, standable and reached), except
`seam`. Every room has `center`, `door_in_at`, `door_out_at`. By kind (declared defaults, placed on open floor; a
registered kind's own win): `stand`/`gauntlet`/`ambush` `trainers` (n = `params.trainers`, default 3, with yaw facing the
entrance) and `line` (a trip box across the room); `miniboss` `boss`, `line`; `nest` `spawns` (n = `params.spawns`, 6);
`habitat` `legendary`, `viewpoint`; `puzzle` `controls` (n = `params.controls`, 3; wall cells at y+1), `display`; `vault`
`chests` (`params.chests`, 4); `safe_room` `healer`, `rest`. Built kinds add: `entry_room` `arrive`, `back`, `threshold`;
`exit_room` `far`; `boss_arena` `spot`, `arena`; `maze` `entry`, `exit`, `dead_ends`; `parkour` `checkpoints`,
`platforms`, `catch`; `collapse_bridge` `span`, `checkpoints`, `catch`; `resources` `seam` (24), `seam_box`, `stand_at`;
`dark_room` `candles`.

## 4. The kinds that are built

- **Connectors** `drift`, `stairs`: dressed by the theme; a `rise` is a one-block staircase along the room.
- **`entry_room` / `exit_room` / `boss_arena`**: the engine's behaviour kept: rip frame on the west / east wall, the board
  on the north wall (an entity from `shell_entities`), the threshold at the entry's east door, the boss spot at two thirds
  of the arena on its centre line, the arena's `cleared` door opened by `boss_done` through the arena's `clear`.
- **`maze`**: a randomised depth-first spanning tree on a 4-pitch grid (corridors 3 wide, walls `params.wall_height` 4,
  1 thick, posts at the lattice), so it is solvable by construction; dead ends are anchors. Its length snaps down to
  `4n+3`, width to `4m+1`, and `exit_dz` must be a multiple of 4. `params.loops` opens extra walls; `params.seed` re-rolls.
- **`parkour`**: ledges 6 long and 7 wide, 3x3 platforms on pillars from a catch floor `pit` (6) below, gaps of 1 or 2,
  steps of at most one block up or down, `params.sections` ledges apart; every ledge is a checkpoint. The room is a
  `no_deploy` box with a line of cracked lamps across the entry ledge. `tick` gives `resistance` 2 s each pass (F1, EXP-075:
  fall distance survives a teleport), notes the ledge stood on, and on the catch floor `fall` teleports to that ledge and
  takes `clock.fall_penalty_s` x 80 from `dg.clock`. Height at least 7.
- **`collapse_bridge`**: a pit like the parkour's, a 5-wide span with rails between two ledges. A member stepping onto
  it from one end is tagged `dg.cbe` or `dg.cbw`; each pass every 3-block segment `params.lag` (6) or more behind them
  is filled with air; standing on either ledge restores the span and removes the tag. Falling charges and teleports as
  the parkour does. Reset restores it. Straight (no bend), at least 30 long and 9 wide.
- **`resources`**: the seam: 24 ores (`params.seam_blocks`, `face_w`) on the face of a slab three thick against the north
  wall, so mining one opens a pocket and never the void. The shell writes band 1's blocks; `reset` (as the entrant) sets
  the band's from `dg.band` (1-2 coal/iron/copper, 3-4 add gold/redstone/lapis, 5-6 diamond; the jungle's are logs,
  melon, bamboo, honeycomb, pumpkin). `tick` watches each cell and calls `greed/take` once per block gone (the
  ladder of D13 is then the engine's). The pick of such a dungeon may break exactly its seam blocks (`pick_give(doc, d)`).
- **`dark_room`**: no light of its own, lit candles found along the way, and `enter` gives 3 torches with
  `can_place_on` for the room's floor blocks; `reset` takes the placed ones back out. The torches are UNPROVEN (below).
- **`safe_room`**: a rug, benches, lantern posts and a counter with the `healer` anchor behind it (the NPC is wave 2's).

### 4a. The fight kinds (wave 2, `tools/dungeon_fights.py`, unit DG-FIGHTS; built and simulated, not run in Minecraft)

Rung: datapack plus generator. `stand`, `gauntlet` (alias `ambush`), `miniboss`, `nest`, `habitat` and the `safe_room`
healer register on import. Params (a room with the kit's placeholders, an int `trainers` or no species, still builds
as a themed empty room and `D.warnings()` names it):

- **`stand`**: `params.trainers` [{name, skin?, team_by_band}] or `params.pool`. All trainers stand visible from the first
  pass; each fights when the member reaches its line (`sight` blocks before it, default 8), one after another; the room
  clears after the last. A fight forfeited or fled is offered again after 4 passes out of battle.
- **`gauntlet` / `ambush`**: the same `trainers`, hidden. `params.triggers` (fractions, increasing, at least 14 blocks
  apart; default spread from 0.18) spring each: the trainer is spawned 12 blocks past the trigger, a barrier of the
  theme's gate block stands 8 past it, full width, until the win. A member found past a standing barrier is put back
  before it. The entry door is never touched.
- **`miniboss`**: `species_by_band`, `level_offset` (<= 0 from the band's upper cap; band 6 stays 95-100), `aspects`?,
  `scale`? (`scale_modifier=`), `catchable`? (honoured at band 6 only, D8).
- **`habitat`**: `species`, `level_by_band` (1..the band's upper cap), `fight_only` (default true; band 6 only when
  false), `ambience`? (particle ids; an id with a dot in its path is a sound), `title`?.
- **`nest`**: `species`, `count_by_band` (1-12), `level_spread` [lo, hi] below the upper cap (band 6 floors at 95),
  `spawns`?, `clear`? (`all` or `pass`), `catchable`? (default false; refused if a level could exceed the lower cap).
- **`safe_room` + `params.healer: true`** (`uses`, default 1 per run): a bell on the counter; ringing it heals the
  party with `healpokemon @s` when the member is out of battle. Not a `cobblemon:healing_machine`: its use fires the
  blackout's checkpoint advancement.

Wild Pokemon are spawned by the macro `spawnpokemonat` (vanilla `summon cobblemon:pokemon` is refused), bound at once
with the keep tag, the slot's tag, the blackout's exempt tag, the run id and `PersistenceRequired`, and discarded at the
room's reset, the slot's free and the keeper's pass (a stale run id). A wild room clears when its tagged Pokemon are
absent on two passes in a row; one never seen in 5 passes opens the room anyway. Every NPC battle goes through DG-CLAW's
clawback. Unproven in game: that a fainted or caught wild Pokemon's entity is gone, `no_ai` creatures accepting a
battle, `any_block_use` on a bell in adventure, `healpokemon` restoring PP in the pocket. Tests:
`tests/test_dungeon_fights_rooms.py`, fixture `tests/fixtures/dungeon_fights_rooms.json`.

## 5. The shell at full length

`shells/s<g>` calls `shells/s<g>/<room>`, one function per room, each force-loading what it writes. `place/s<g>` runs
one slot in the pocket, and `reapply_steps()` lists one `fn` step per slot when any dungeon has rooms, because EXP-081
measured one call of about 0.46-0.73M blocks at 1-2.6 s. A full-length test dungeon (the demo's middle twice,
about 1,460 blocks, `full_length_rooms()` in the tests) measured 0.50M blocks and 10,300 commands per slot in the mine,
0.51M and 11,700 in the ruin, 0.60M and 32,300 in the jungle (its dressing is setblocks); the biggest room function is 988
lines (mine), 1,949 (jungle). The whole chain `place/s<g>` must stay under the gamerule's 65,536 commands, so `problems()`
refuses a shell over 60,000 (the jungle uses about half). The *slot reset* does not rebuild the shell (the shell is re-applied, `DUNGEONS.md` 1 Instancing);
it restores the mutables: gates, the seam, the span, torches, the room states.

## 6. The walk check (`problems()`)

Per dungeon, on slot 1 (the slots are one dungeon), by replaying every room's ops onto a numpy grid with the gates open
and walking it with a 2-high, 1-wide player on reversible edges only (a step of one block, or a parkour jump of a flat
gap of at most 3 / a rise with a gap of at most 2, DUNGEONS.md V6): door in to door out and back, every point anchor, doors
open and clear, no hazard or gravity block, no column without floor, nothing the pick can break outside the seam, and
every standable cell lit (an optimistic Manhattan bound). Mutations that must fail, and do: a maze that loses a passage,
platforms with wider gaps, a kind that places lava or sand or punches the floor, hull lights off, a wall block added to the
pick's list.

## 7. The clock of a full-length dungeon (`tools/dungeon_clock.py`, unit DG-NS)

The bands' `clock_s` (29-39 minutes) were set for the short spine of `DUNGEONS.md` 4.2. A rooms dungeon carries its own
`"clock_s_by_band": {"1": s, ..., "6": s}`; `tools/dungeon.py` uses it (the threshold's start, the board) and falls back
to the band's when it is absent (`warnings()` names such a dungeon). `problems()` refuses one under the derived clock.
Fill it with `python tools/dungeon_clock.py <id> --rooms`, which prints the walk per room and the clocks.

**The walk** is measured, not declared: per room, the shortest walk from the cell inside its door in to the cell inside
its door out over the built grid, on the walk check's own edges (a jump costs its length), plus 3 steps per door; the
entry from the arrival, the exit to the far rip. It is 4-connected, so an open room's diagonal counts as its Manhattan
length. A maze's figure depends on its seed and `loops` (the Night Shift's 79 x 45 maze walks 217 at `loops` 8 and 441
at 1-3): measure, do not estimate.

**required** (seconds, per band) is the sum of, with every pace `DUNGEONS.md` 4.1's PLANNING figure (XT1, EXP-079, has
timed no fight; when it does, change the constants and re-derive):

| Part | Seconds |
|---|---|
| walking | walk / 4.0, a maze's x 2.0 (dead ends), a dark room's x 1.5 |
| a parkour room | walk / 1.5, plus 2 falls of (`fall_penalty_s` + 10) |
| a collapse bridge | walked at 4.0, plus 1 fall |
| each trainer (stand, gauntlet, every boss stage) | 120 + 30 x (members - 2): the owner's 2-minute small fight, +0.5 min a member; members are the team's size for the band (else `engine.stands.members_by_band`) |
| boss | its stages' fights for the band, plus the gaps (`gap_ticks`) |
| mini-boss | one fight of one member, 90 |
| nest | with gate `cleared` and no `clear: "pass"`: `count_by_band` x 90; else 0 |
| habitat | with gate `cleared`: 360 (4.2's "about 6 minutes"); else 0 |
| puzzle 90, resources (the free tier) 30, safe room 20, the run's cues 30 | |
| vault | 0: optional, priced by its own `clock_cost_s` |

**clock** = ceil(required x `engine.clock.slack_factor` (1.25) / 60) x 60: whole minutes, as 4.2. Optional rooms (an open
habitat, a nest that passes, the vault, greed past the free tier) are paid from the slack, as 4.2 intends.

Each dungeon's clocks, written here by hand from the tool's output (the audit's V12 compares every generated
threshold's clocks with this table or 4.2's):

| Dungeon | Walked | Band 1 | Band 2 | Band 3 | Band 4 | Band 5 | Band 6 |
|---|---|---|---|---|---|---|---|
| night_shift | 1,338 | **36** | **38** | **39** | **42** | **44** | **47** |

## 8. Not done, and unproven

- **In game, nothing.** The owner's look decides the jungle; whether vines hold on the trunks and leaves do not decay
  (`persistent=true`), water stays in its channels, and the one-block step and jump limits feel right are all unrun.
- **`can_place_on` on a torch** in adventure mode is UNPROVEN (the shape is R2's `can_break`, EXP-074). The candles are the
  fallback; the dark room is walkable without the torches.
- **The collapse** is per keeper pass (1 s), so its granularity is a few blocks at sprint; and shared by co-op members
  (`members_max` is 1).
- **Not here:** puzzles, vaults (DG-PUZZLES), the boss's
  crews and the three dungeons' room lists (wave 2).
