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
shut until `room/<dungeon>/<room>/s<g>/clear` runs (default `open`; a `boss_arena` defaults to `cleared`). `params.exit_dz`
bends the walked line in z (the next room's door is that far over). Rooms are laid along +x with their own end walls;
consecutive rooms share a door: 3 wide, 4 high, two wall columns deep, exactly equal in `door_out` and the next
`door_in`. A connector (`drift`, `stairs`) is at most 40 long and at least 7 wide (`problems()` refuses otherwise).
First room `entry_room`, last `exit_room`, exactly one `boss_arena`; the engine reads the board, the threshold, the
boss spot and the far rip from them (`dungeon.points()` returns the same keys for a rooms dungeon).

## 1a. The pass-2 record (KIT2, 2026-10-10): outlines, doors anywhere, forks, secrets, shortcuts, variants

Every field below is OPTIONAL; a record without them builds exactly as section 1 (a box room entered on its west wall,
left by its east wall). The three pass-1 dungeons use none of them until their authors re-author them.

**Shape.** `"shape"`: `box` | `oval` | `l` | `t` | `gallery` | `cavern` | `split` | `ring`, with `"shape_params"`:

| Shape | What it is | `shape_params` (all optional) |
|---|---|---|
| `box` | the pass-1 room | |
| `oval` | an ellipse in the room's box | `fill` 0.75-1.0 (how much of the box it fills) |
| `l` | two arms; one corner of the box is rock | `corner` `ne`/`nw`/`se`/`sw` (the one cut), `cut` [fx, fz] fractions of the box (default [0.5, 0.5]) |
| `t` | a bar along one long side and a stem | `bar` `north`/`south`, `stem` fraction of the length (0.4) |
| `gallery` | a band curving across the box in z | `band` fraction of the width (0.55), `waves` (1.5) |
| `cavern` | noise-carved: ragged walls, alcoves, rock pillars, an uneven floor | `pillars` per 100 cells (1.2), `alcoves` (4), `rough` max floor lift (1) |
| `split` | two levels: a terrace along one long wall `level` higher, a trench `depth` deep between, crossed by the trail, stairs up at one end | `level` (4), `depth` (2), `side` `north`/`south`, `frac` the terrace's share of the width (0.35) |
| `ring` | a plaza round a central feature (a raised ring of rock, a pool or columns) | `feature` `rock`/`pool`/`columns`, `radius` (fraction 0.3) |

A dungeon with `"shape_mix": true` gives every room without `shape` its theme's default (`themes.<id>.shapes.mix`,
by kind, weighted, deterministic per room). Kinds with their own geometry keep the box whatever the record says:
`maze`, `parkour`, `collapse_bridge` and any kind registered with `pit`, `jumps` or a snap (register flag `outline`,
default True otherwise; a kind may set it False). The outline only ever ADDS rock: the doors, every anchor (5 x 5 round
it), every `reserve` box, the bbox centre (5 x 5) and the 3-wide trail between them stay open and at the base floor,
so a kind built for a box still works inside any outline. The fill is `replace air`, so it never removes a kind's block.
`xa..xb/za..zb`, `ix0..ix1/iz0..iz1` and `box` stay the room's BOUNDING box (selectors, keeper boxes); what is open is
`room["outline"]`: `open(x, z)`, `lift(x, z)` (floor above the base floor; negative in a trench), `floor(x, z)`
(feet level), `cells()`. `default_anchors()` places on open, level cells of the outline.

**Doors.** `"in"` and `"out"` (the boxes in the built room keep their names `door_in` / `door_out`):
```
"in":  {"side": "west"|"north"|"south"|"east", "at": 3, "y": 0}
"out": {"side": "east"|"north"|"south"|"west", "at": 3, "dz": 4, "y": 4}
```
`side` is the wall the door is in. `at` places a door in a north or south wall: the door's centre is `at` blocks from
the interior's west edge (`ix0`), default 2 for `in` and `length - 5` for `out`. `dz` (east or west wall `out`) is
`params.exit_dz`. `y` is a LANDING: the door's floor is `y` above the room's base floor, with a 3 x 3 landing in front of
it and a one-block staircase down to the floor, built by the kit. The next room's `in` must be on the opposite wall
(`out` south -> `in` north); its base floor is the door's floor less its own `in.y`. So the route turns (a door in a
side wall puts the next room beside this one, across the strip) and climbs (landings, `rise`) anywhere.
`"dir": "east"` (default) | `"west"` (default `in` east, `out` west; the room is laid toward -x: the route doubles
back). `west` is allowed only for kinds registered `reversible` (`drift`, `stairs`). `"align": "center"|"north"|"south"`
places a room entered by an east or west wall across the strip (default `center`, pass 1's).
Rooms are placed door to door; `problems()` refuses two rooms whose boxes (walls, floor and ceiling courses included)
overlap, a room outside the strip (x, z) or the dimension (y), and a door whose two sides do not meet. Rooms may be
STACKED (one under another) when their boxes do not overlap.

**Forks and side rooms.** Two entries may stand in `rooms` beside ordinary rooms:
```
{"id": "f1", "kind": "fork", "routes": [
    {"id": "fast", "rooms": [ ... ]},
    {"id": "safe", "from": {"side": "south", "at": 20, "y": 0}, "rooms": [ ... ]}]}
{"id": "s1", "kind": "side", "from": {"side": "north", "at": 8}, "rooms": [ ... ]}
```
A fork's first route leaves by the previous room's `out`; every other route by its own `from` door on that room. All
routes rejoin at the room after the fork, through its `in` wall: route 0 by its `in`, the others by doors where they
arrive (the last room of a route may say `"length": "fit"` to be stretched to the join). A `side` entry is a dead end
off the previous room by its `from` door; its last room has no door out. Room ids are unique across all routes; the
room index `i` (state holder `#s<g>r<i>`) runs over the rooms in record order, routes included. `layout()` gives every
room `route` (`"main"`, `"<fork>/<route>"`, `"<side>"`) and `doors` (every door of the room: `{"box", "side", "y",
"to": <room i>, "dir": "in"|"out"}`); `door_in`/`door_out` remain the main ones. The entry, the boss arena and the exit
are on the main route. A room's `gate: cleared` closes all its doors out.

**Secrets.** `"secrets": [{"id": "s1", "type": "cracked"|"balcony", "side": "north"|"south", "at": 0.6}]` on a room.
`cracked`: a chamber in the rock beside the room (5 x 4, 4 high) behind a 1 x 2 face of the theme's
`shapes.secret_block`, the only block besides the seam the rift pick may break in that dungeon (`pick_blocks(d)`); the
room's reset puts it back. `balcony`: a ledge up a staircase, and from its end a gap of 2 to an alcove in the wall only
the ledge sees. Anchors: `secret` (the relic spot in each, walk-checked with the face broken / with jumps),
`secret_door` (the breakable cells), `balcony`. Nothing else may place `shapes.secret_block`.

**Shortcuts.** `"shortcuts": [{"id": "c1", "to": "<earlier room id>", "at": 10}]` on the FAR room: a door through both
walls where the two rooms touch, closed by the theme's gate block, opened from the far side only (the far room's tick:
the member stands on the `shortcut` anchor's cells) by `room/<d>/<far>/s<g>/shortcut_<id>`; the slot reset closes it.
The two rooms must share a wall plane with 7 or more blocks of overlap and the same floor there.

**Variants.** `"variants": [{"id": "a"}, {"id": "b", "mirror": true}, {"id": "c", "seed": "c"},
{"id": "d", "seed": "d", "mirror": true, "swap": {"<room id>": {...fields...}}, "order": ["<top-level ids>"]}]` on a
dungeon. Slot k builds `variants[(k - 1) % n]`: `mirror` swaps north and south (sides, `dz`, `align`, outlines), `seed`
re-rolls every room's randomness (`rng(d, room, salt)` then depends on it), `swap` overrides a room's fields (`params`
merged one level; an alternate kind), `order` permutes the top-level entries (entry first, exit last). `variant_of(doc,
slot)` gives `{"index", "id", ...}`; every call that takes a slot (`layout`, `plan`, `slot_build`, `points`) builds that
slot's variant; `problems()` walks every distinct variant. Entry (tools/dungeon.py) prefers a free slot whose variant is
not the one the player last ran (`dg.lv_<short>`, 1-based), else any free slot.

**For other units.** Place by the outline, never the box: `DressCtx.open(x, z)`, `.floor(x, z)`, `.walls()` (open cells
beside rock with their face), `.standable_cells()` (already the real grid). Never place `shapes.secret_block`; keep
off `ctx.reserved(x, z)` (now including landings, stairs, secrets, shortcuts).

**As built (KIT2, 2026-10-10; built and checked on the simulator and the independent audit, not run in Minecraft).**
- Code: `tools/dungeon_outline.py` (the shapes), `tools/dungeon_rooms.py` (placement door to door, forks, variants,
  landings, rails, secrets, shortcuts, the checks), `tools/dungeon_kinds.py` (wall dressing on the real faces),
  `tools/dungeon_grid.py` (`NOSUP`, `walk(strict=)`), `tools/dungeon_clock.py` (walk ends, routes, variants),
  `tools/dungeon.py` (`pick_blocks`, the variant pick at entry, `dg.lv_<short>`). Fixture using every field:
  `tests/fixtures/dungeon_kit2_demo.json` (21 rooms, a fork, a side room, both secrets, a shortcut, a hall entered 12
  up a grand stair, a return walked west UNDER the route, 4 variants): 0 problems in all three themes.
- `BOX_ONLY_KINDS` (`maze`, `parkour`, `collapse_bridge`, `setpiece`) never get a theme mix's outline and keep pass 1's
  doors (west in, east out, no landing, no extra door, no secret); a kind registered `outline=False` likewise.
- A landing or stair step `RAIL_FROM` (4) or more over the floor beside it gets a rail of the theme's gate block.
- A lantern theme's room more than 14 over its floor hangs its lanterns on long chains to 6 over the floor beneath; any
  standable cell a pass-2 room's lights leave dark gets the hull's light set into its floor (`light_dark_cells`).
- Stacked rooms keep one block apart (`BED_UNDER`: a stream writes its bed under the floor course).
- A gauntlet/ambush room refuses any floor lifted 3 or more and a balcony (its barrier is 4 high: V6 clears it).
- Pass-1 records still build (0 problems) but their dressing changes where it was unsafe: the jump-in pit test plugs
  2-5 nook cells in jungle `sanctum`, `tangle`, `undercroft`; `ground_cover` sets a big dripleaf only where all eight
  cells round it are open floor (beside a trunk or rock it sealed nooks: a TRAP twice, here and in LIFE's run); a 2 x 2
  trunk or column needs floor under all four feet (over a trench or a stream it floated and sealed a cell). The mine's
  shells are byte-identical; jungle and ruin shells differ in where trunks, columns and dripleaves stand.

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
| `variant_of(doc, d, slot)` / `resolve(doc, d, slot)` / `variant_slots(doc, d, slots)` | pass 2: the slot's variant, the record as that slot builds it, one slot per variant |
| `flatten(d)` / `all_records(d)` | pass 2: rooms in record order with their route and how they attach; every record in every variant |
| `room_doors(room)`, `main_door(room, "in"/"out")`, `inner_cell(room, door)`, `room_start(room)`, `room_end(room)` | pass 2: every door (`{side, c, y, box, dir, to, main, gate[, shortcut]}`), the cell inside one, the walk's ends |
| `floor_xz(room, x, z)`, `open_near(room, x, z, r)`, `pick_blocks(d)` | pass 2: the outline's floor, the nearest open column, what the rift pick may break |

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

Pass 2 (KIT2) adds, per variant: every door of a room reached from its door in and back; every gate box covers its
opening (a shut gate leaves no gap); no room writes outside its own box; no two rooms' boxes meet (stacked rooms one
apart); each secret reached WITH its trick (face broken / the jumps of V6) and NOT without it; the pick's count is the
seams plus the secrets' faces; pits gain (c) jump-ins (a flat jump of up to 3 and a fall onto a cell the strict jumping
walk cannot leave) and a big dripleaf (`G.NOSUP`) is asked both as an obstacle and as air. Generator mutations that
fail, run on the fixture (`mine`): the outline ignoring what it must keep (47), a cracked face of plain rock (4), the
balcony's gap widened to 4 (4), no landing under a raised door (12), door boxes one off centre (184), fork routes not
stretched (16), no spur to an extra door (4).

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

Pass 2: the walk runs from `room_start` to `room_end` (doors in any wall, at their landings); the clock counts the
main route and, of each fork, the route that takes longer at that band (side rooms are optional: the slack pays), and
takes the largest over the dungeon's variants.

**clock** = ceil(required x `engine.clock.slack_factor` (1.25) / 60) x 60: whole minutes, as 4.2. Optional rooms (an open
habitat, a nest that passes, the vault, greed past the free tier) are paid from the slack, as 4.2 intends.

Each dungeon's clocks, written here by hand from the tool's output (the audit's V12 compares every generated
threshold's clocks with this table or 4.2's):

| Dungeon | Walked | Band 1 | Band 2 | Band 3 | Band 4 | Band 5 | Band 6 |
|---|---|---|---|---|---|---|---|
| night_shift | 1,388 | **37** | **39** | **40** | **42** | **45** | **48** |
| jungle | 1,578 | **62** | **67** | **70** | **75** | **82** | **87** |
| flooded_ruin | 1,272 | **40** | **43** | **45** | **48** | **52** | **55** |

## 8. Not done, and unproven

- **In game, nothing.** The owner's look decides the jungle; whether vines hold on the trunks and leaves do not decay
  (`persistent=true`), water stays in its channels, and the one-block step and jump limits feel right are all unrun.
- **`can_place_on` on a torch** in adventure mode is UNPROVEN (the shape is R2's `can_break`, EXP-074). The candles are the
  fallback; the dark room is walkable without the torches.
- **The collapse** is per keeper pass (1 s), so its granularity is a few blocks at sprint; and shared by co-op members
  (`members_max` is 1).
- **Pass 2, unproven or not done (KIT2):** nothing of 1a has run in Minecraft. The independent audit walks slot 1
  only and reuses its graph for the others ("SLOT ... not slot 1's moved"), so with `variants` slots 2-4 report SLOT
  and SOFTLOCK findings that are its assumption, not the pack's; with each variant put first, all twelve (four
  variants x three themes) and the three authored dungeons with `shape_mix` report nothing else. On the way it found
  four real faults, all fixed: a shaped streak writing past its room, a dripleaf nook, a floating 2 x 2 trunk, and a
  room touching the exit whose far rip's click box reached through the wall (now `RIP_CLEAR`). AUDIT2 must walk each
  variant and route on its own graph, and not map rooms by x (`room_of_x`). `tools/dungeon.py`'s return-margin warning
  measures the way back to the back rip in x, which a route that turns and doubles back makes too short (the warning
  comes late); the board's leg distances are x offsets too. Relics, lore and the set across runs: section 9. Windows
  onto earlier rooms are not built. `can_break` on the secret block in
  adventure is R2's shape (EXP-074), unrun for these ids.
- **Not here:** puzzles, vaults (DG-PUZZLES), the boss's
  crews and the three dungeons' room lists (wave 2).

## 9. Relics: the rewards behind the secrets (DG2-RELICS, 2026-10-10; built and simulated, not run in Minecraft)

Rung: **datapack plus generator** (`tools/dungeon_relics.py`, `data/dungeon_relics.json`, one `relics` entry last in each
theme's `dress`); an advancement, a score and merged room hooks are enough, so no mod, scripting layer or companion
process is proposed. A room with a secret carries `params.relic` (id, `[a-z][a-z0-9_]{1,31}`, unique in the dungeon),
`params.lore` (printable ASCII, at most 160 characters) and optionally `params.relic_name` (at most 32; default the id in
title case). A room with two secrets puts `relic` / `lore` / `relic_name` inside each secret record instead.

- **Where.** A pedestal (the theme's `pedestal` block with its `armed` block on it) stands on the cell beside the secret's
  `secret` anchor, toward the chamber's wall (cracked) or the alcove's end (balcony); the anchor stays walkable, so the
  kit's walk check still reaches it WITH the trick and refuses it without.
- **Pickup.** The room's `tick` runs `room/<d>/<room>/s<g>/relic_<id>` for a member within 1.6 of the pedestal's centre.
  The function returns at once if the player holds the criterion `<id>` of `cobblers:dungeons/relics/<short>`. Otherwise it
  grants that criterion, adds 1 to the player's `dg.rl_<short>`, gives the relic item (the theme's `items`, named, lored,
  glinting, `custom_data` `cobblers_relic`), titles the name, tells the lore in chat, sounds a chime and sets the armed
  block to the `taken` block for the run. **Once per player, ever:** the guard is the player's advancement, so a death, a
  logout, the slot's reset and every later run leave it standing. A co-op member who has not taken it is given theirs by
  walking up, whatever the pedestal shows.
- **Reset.** The room's `reset` (the slot's) sets the state holder `#s<g>r<i>l<j>` to 0 and sets the armed block back:
  the display is re-armed. No function revokes an advancement or resets, sets or removes a count (tested over the whole
  generated pack).
- **The collection.** One advancement per dungeon, `cobblers:dungeons/relics/<short>`: a `minecraft:impossible` criterion
  per relic (the union over every variant), every one required, goal frame, toast and chat announcement. The last
  relic completes it. `dg.rl_<short>` is the player's count (created at load by `relic/load`).
- **The run board.** The board is one entity every member reads, so it carries a static line (how many are hidden). The
  per-player count is a chat line at arrival (`relic/<short>/show`, appended to `slot/s<g>/arrive`) and an action-bar line
  while the member stands within 5 of the board before the clock starts (`relic/<short>/bar`, appended to `m/lobby`).
- **No economy.** The base items (clock, echo shard, disc fragment, heart of the sea) are in no bank price, counter,
  buyer, trade or reward (tested against `modpack/config/cobbledollars/bank.json`, `data/markets.json`, `traders.json`,
  `produce_buyer.json`, `rewards.json`, `direct_trades.json`); no CobbleDollars.
- **Checks** (`D.problems()`): the record (id, lore, name, uniqueness across rooms and variants, a relic on a room with no
  secret, a secret without a relic once the dungeon has any); the pedestal exists in the grid; the trigger, read back from
  the GENERATED tick line, reaches no cell a player stands on without the secret's trick. A dungeon with secrets and no
  relics builds and `D.warnings()` says so.
- **Unproven in game:** the selector form `advancements={cobblers:dungeons/relics/ns={first_find=true}}`, `advancement
  grant @s only <adv> <criterion>` on an impossible criterion, the item components as written, the sound and particle
  ids (the particle is checked against the jar), and a goal-frame root advancement showing as a tab of its own. The pedestal
  is blocks, not an item frame: an item frame is an entity the shell's chunk-look chain would have to track.
