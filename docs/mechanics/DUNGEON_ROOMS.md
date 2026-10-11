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

## 1b. The pass-3 record (KIT3, 2026-10-10): crossroads, wings, long parkour, the hidden prize, the vault budget

The owner, playing pass 2: "I see no diverging paths ... the optional paths didn't feel immense. And the parkour room
should be longer, or just have more of them." Every field below is OPTIONAL and a record without them builds exactly as
1a. Code: `tools/dungeon_crossroads.py` (crossroads, looks, wings' checks), `tools/dungeon_prize.py` (the prize),
`tools/dungeon_greed.py` (the vault budget).

**Crossroads.** A room of `"kind": "crossroads"` is a fork's HOST: the entry right after it in `rooms` must be a `fork` of
2 or 3 routes, and every route of that fork carries a `look`. Any fork may carry looks; after a crossroads they are
required and pairwise different.
```
{"id": "x1", "kind": "crossroads", "length": 40, "width": 41, "height": 10, "shape": "ring",
 "params": {"hub": [0.5, 0.5]}}
{"id": "f1", "kind": "fork", "routes": [
    {"id": "fast", "look": "lit", "sign": "GANTRY", "rooms": [...]},
    {"id": "deep", "look": "dark", "sign": ["OLD DRIFT", "KEEP OUT"], "from": {"side": "north", "at": 20}, "rooms": [...]},
    {"id": "wet", "look": "flooded", "from": {"side": "south", "at": 20}, "rooms": [...]}]}
```
- `look`: an id from the theme's `crossroads.looks`; every theme has `lit`, `dark` and `flooded` (the mine's lit gantry,
  dark tunnel and flooded stair; the jungle's sunlit way, dark hollow and flooded stair; the ruin's lit colonnade, dark
  crypt and flooded stair). A look restyles the door on BOTH sides (the host's wall and the route's first room's): frame
  and lintel blocks, light blocks set into a lit frame, the 3 x 3 approach's floor (`deck`), a one-deep wading trench
  across the approach for a `water` look (only where the door has no landing), and a WINDOW each side of the door (the
  look's `window` block, 2 wide and 2 high at `c +- 3..4`, `y + 1..2`, each room in its own wall column, only where both
  rooms' walls meet there). `sign`: a string or up to 3 lines, at most 15 characters each, printable ASCII; a wall sign
  over the door on the host's side.
- `params.hub`: `[fx, fz]` fractions of the box (default the centre): where the chooser stands. The anchor `hub` stands there
  (2 in from the walls at least; the kit keeps 5 x 5 open round every anchor); from it every exit's opening must be in sight (`problems()` casts a ray from eye height to each
  door's opening through the built grid).
- `problems()` refuses: a crossroads not followed by a fork; a fork of more than 3 routes; a route after a crossroads
  without a look, an unknown look, two routes with one look; two exits of one host on the same wall closer than 10
  (centre to centre: the "two near-identical doors on one wall" of pass 2); an exit the hub cannot see. A dungeon may hold
  any number of forks (crossroads or not); forks and wings still nest one level only (no fork or side inside a route).

**Wings.** A `side` entry of 2 to 4 rooms is a WING (1 room is the pass-2 side room; more than 4 is refused). A wing
ends in a dead end. A wing that REJOINS is a fork route marked `"optional": true`: it rejoins at the room after the fork
like any route. Every fork keeps at least one route that is not optional.
- The clock (`tools/dungeon_clock.py`) never counts a side entry or an optional route: it pays the slowest NON-optional
  route of each fork. The walk check walks every room of every route and wing in and back (the pass-2 checks, unchanged),
  and the independent audit walks each route alone, optional ones included.
- A wing's first room is entered through the host's side wall, so it cannot be a box-only kind (`maze`, `parkour`,
  `collapse_bridge`, `setpiece`: west in, east out); put a connector first (`"in": {"side": "south"}`, out east), then
  the parkour. `problems()` names it.

**Parkour, longer.** `params.sections` 2..6 (PARKOUR2's own planner; a room of S sections needs an interior at least
`30 S - 10` long: 140 for 5, 170 for 6). `params.hard: true` makes every section tier 3 (jumps of 4 cells with a run-up,
3 with a rise) and turns the easy fork off: the parkour that guards a wing's payoff. PARKOUR2's jump limits are unchanged.

**The hidden prize** (`habitat` rooms only, see below):
```
{"id": "lair", "kind": "habitat", "length": 30, "width": 21, "height": 10, "params": {
  "prize": {"rare_by_band": {"1": "gabite", "2": "gabite", "3": "shelgon"},
            "legendary_by_band": {"4": "nihilego", "5": "buzzwole", "6": "kartana"},
            "chance_by_band": {"1": 15, "6": 40},
            "rumour": "A pitman swears something glitters in the old pay office."}}}
```
- `rare_by_band` names a band below `engine.prize.legendary_from_band` (4: gym 6's cap, the Beast Ball stage), a
  NON-legendary species (the jar's labels: no `legendary`, `mythical` or `ultra_beast`); `legendary_by_band` a band from
  it on, a legendary, mythical or Ultra Beast. A band named by neither has no prize. `chance_by_band` (percent, 0-100)
  overrides `engine.prize.chance_by_band`; `rumour` (printable ASCII, at most 120) overrides `engine.prize.rumour`.
  **Pools** (`rare_pool_by_band`, `legendary_pool_by_band`, `roster`; one species rolled a run): section 14.
- **Per run.** At the threshold (`slot/s<g>/start`, after the sigil is spent, so leaving and re-entering cannot re-roll
  it for free) the room rolls `random value 1..100` against the entrant's band's chance; `#s<g>r<i>p dg.rs` 1 means
  present. Present: the run board shows the rumour as its last line and the member is told it in chat; the arrival puts the
  board back. The room's `enter` spawns the band's prize at the anchor `prize` (the `legendary` anchor when the habitat
  has no `species` of its own, else its own open spot); the room's reset and the slot's free discard it.
- **The Pokemon.** Level: the band's LOWER cap (`engine.prize.level`), so no entrant of the band is ever over-capped by
  it and the level cap's ball refusal (`tools/levelcap_pack.py`) never fires (below). Fixed, `no_ai`, catchable. From
  `legendary_from_band` on it carries `data/key_ball.json`'s tag: only a Beast Ball catches it (EXP-064, unrun), x5.
  Below, any ball. The catch is weighed by GREED as a habitat's (`catches.habitat`: rare 8 points, legendary 20).
- `habitat` only: GREED weighs a catch by the kind of room the catcher stands in, so a prize in a nest or a mini-boss
  room would be weighed as a nest catch. A habitat may carry a `species` of its own as well (its resident, as 4a).
- A prize habitat's `gate` is `open` (an optional wing's payoff; `problems()` refuses `cleared`).

**The vault budget** (`data/dungeon_greed.json` `vault_budget`): a vault chest's expected value (GREED's `chest_cp`)
at band b is at most `dollar_factor` x the gathering tier open at the band's lowest badge count x the shortest dungeon's
required hours, divided by the vault's chests: a vault never pays more than the same run's time spent gathering, the
limit RESOURCES2 set for a resources room. With the kit's four chests and the two-stage-boss clocks (2026-10-11): **band 1 80 cp, 2 184, 3 180, 4 198, 5 346, 6 367
(0.8 to 3.7 points) a chest; a whole vault 322, 738, 720, 792, 1,385, 1,469 (floored).** The figures move with the shortest
dungeon's clock. Enforced by `problems()` (`vault_budget.enforce` true since DG3-INTEGRATE: the pass-3 authors rebalanced
every vault, and `python tools/dungeon_greed.py` names no chest over; the pass-2 vaults were 7 to 150 points a chest).

**As built (KIT3, 2026-10-10; simulated and audited, not run in Minecraft).**
- Kit hooks: `R.LAYOUT_FNS` (a last pass over a laid slot: routes' `optional`, looks, signs, windows on both doors) and
  `R.POST_DRESS_FNS` (after the theme's dressing, before pits are plugged and the hull lit: the looks' blocks; a lit
  look's lamps count as lights). The fixture `tests/fixtures/dungeon_kit3_demo.json` (25 rooms, four variants): 0 problems
  in the mine and the jungle; in the ruin one LIFE finding in `d1` (variant d), LIFE's own; the independent audit 0
  findings on all four slots (band 1).
- **A long parkour wants width 25** (measured with PARKOUR2's planner, four seeds each: 21 wide never plans 5 or 6
  sections, 23 plans the hard one only, 25 plans both 3-4 times in 4). A door into it must stand at least 6 from its
  north and south walls (its first ledge is 7 wide), so a wing's parkour is centred on the connector's door: plan the
  strip's z bands (the fixture's wing runs along the north, the main route south).
- **The clock walks every route's own way** (`tools/dungeon_clock.py route_extras`): a host's walk is to its main door
  and the join's from its main door in; a route that leaves by another wall or arrives by another door adds the
  difference to its first and last rooms (never below 0). Without it the fixture's band-3 clock was a minute short of
  the independent audit's. The three pass-2 dungeons still pass with their clocks.
- The independent audit (AUDIT2's) was extended in two places only, both reading the record as 1b states it: a `hard`
  parkour asks for no fork; a choice of routes that takes an `optional` one is walked alone but never priced.
- The board's rumour is a `data merge` of the board's text_display at the threshold; the arrival writes the plain text
  back. A wild prize uses the fight rooms' macro spawn and the slot's claim (`wild/s<g>/bind`), so the slot's free and
  the keeper's stale-run pass discard it as any wild Pokemon of the slot.
- `data/dungeon_prize.json` is the prize's record for `data/key_ball.json` (`bosses`): its `species` is the REFERENCE
  prize whose bind key_ball's check builds while no dungeon authors a legendary prize. Since pass 3 all three do, so the
  check reads their twelve binds (one per slot).
- **DG3-INTEGRATE (2026-10-10), the fork's two ways.** In the 25-wide rooms recommended above, the safe way's detour had a
  bulge of 6, so its two z legs were 4 cells, which tier 1's hops (2-3 over 3-long platforms) cannot cover; the planner fell
  back to a 4-cell hop there in every seed and every dungeon: the "safe" way jumped as far as the fast one. Now the two ways
  leave the fork ledge 5 either side of its centre when 6 would leave the safe way less than its full bulge of 8, and tier
  1's fallback adds short platforms but never a longer hop; and the fast way must hold at least one 4-cell jump (the Night
  Shift's slot 4 rolled one of 3s only). Measured on the three dungeons' twelve main parkours: the safe way's longest jump
  3, 10 hops; the fast way's 4, 4-6 hops.

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
  the band's from `dg.band` (the mix per band is `data/dungeon_resources.json` `seam`; the jungle's face is logs,
  melon, bamboo, honeycomb, pumpkin). There is no `tick` for the seam or the piles: what the member mines is weighed by the
  engine's mined stats wherever they mine it (`tools/dungeon_greed.py`, the owner 2026-10-10; a per-block hook would count a
  block twice). **Since RESOURCES2 (section 10) the room also holds heaps, wall veins and, at bands 5 and 6, a cache chest**,
  all by band; the pick of such a dungeon may break exactly the seam, the table's ore blocks and the cracked secrets' faces
  (`pick_give(doc, d)`).
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
| night_shift | 1,243 main + 410 on the paid fork routes (2,208 all routes, the wing included) | **40** | **42** | **42** | **44** | **49** | **52** |
| jungle | 1,929 all routes, wing and side room included (1,180 main, the slower way of each fork; pass 3, DG3-JUNGLE) | **39** | **42** | **40** | **44** | **51** | **54** |
| flooded_ruin | 1,950 all routes and the wing (1,045 main; 1,290-1,499 paid at band 1) | **39** | **41** | **44** | **45** | **49** | **52** |
| ash_bell | 2,134 all routes, the wing and the side rooms included (NEW-ASHBELL, 2026-10-11; band 4 raised to the others' 44, its clock_why) | **41** | **44** | **43** | **44** | **50** | **53** |
| soul_ossuary | 2,153 all routes, the wing and the side rooms included (NEW-OSSUARY, 2026-10-11) | **39** | **44** | **43** | **45** | **52** | **55** |
| moth_cathedral | 2,142-2,299 all routes, wing and side rooms included (1,519 paid at band 1, variant b; NEW-MOTH, 2026-10-11) | **40** | **43** | **41** | **44** | **51** | **54** |
| dragonspiral | 2,244 all routes, the wing and the side rooms (1,095 main; 1,236 main in variant b; NEW-DRAGONSPIRAL, 2026-10-11; band 4 derived 41, authored 44 so it is not the shortest band-4 clock the vault budget reads) | **40** | **43** | **43** | **44** | **49** | **52** |

BOSS2 (2026-10-10): the boss is two stages and the stands of the tuned bands are a member or two smaller (sections `DUNGEONS.md` 3.2; `members_eased_by_band`), so every clock was re-derived with `tools/dungeon_clock.py` and the table above is the new one: every band is under an hour (the longest, the jungle's band 6, is 54 minutes), where the three-stage table ran to 59. Each is the tool's required time plus the set piece's 25 s, x 1.25, up to the minute (the tests pin the formula). The boss row of the part table now counts two stages and one gap.

DG3-INTEGRATE (2026-10-10): the parkour planner's safe-way fix (section 1b) moved the walks a little: all routes in slot 1
now 2,212 (the Night Shift), 1,919 (the jungle) and 1,948 (the ruin), by `tools/dungeon_clock.py` as the independent
audit reports it; every clock above still covers its derived one (`problems()` clean), so the clocks are unchanged.

KIT3 (2026-10-10): "all routes" now walks each fork route's own way through its host and its join (`route_extras`,
section 1b). The night shift's and the jungle's clocks still cover it; the ruin's, pinned to the tool plus its set piece's
25 s, were re-derived (bands 1, 3, 6 one minute more: its catacomb route leaves and rejoins by side doors).

DG3-RUIN (pass 3, 2026-10-10): the ruin re-authored with two crossroads (three ways out of the bell rotunda, two out of
the nave crossing), a six-section aqueduct and a four-room wing (the seal, a shaft stair, a hard parkour, the prize) that
the clock never pays. Its required time on the main route, each fork at its slowest way, the largest over the four
variants: 1,955 / 2,075 / 2,195 / 2,315 / 2,525 / 2,675 s (32.6 minutes at band 1), plus the set piece's 25 s, x 1.25.

## 8. Not done, and unproven

- **In game, nothing.** The owner's look decides the jungle; whether vines hold on the trunks and leaves do not decay
  (`persistent=true`), water stays in its channels, and the one-block step and jump limits feel right are all unrun.
- **`can_place_on` on a torch** in adventure mode is UNPROVEN (the shape is R2's `can_break`, EXP-074). The candles are the
  fallback; the dark room is walkable without the torches.
- **The collapse** is per keeper pass (1 s), so its granularity is a few blocks at sprint; and shared by co-op members
  (`members_max` is 1).
- **Pass 2, unproven or not done (KIT2):** nothing of 1a has run in Minecraft. The independent audit
  (`tools/dungeon_independent_audit.py`, AUDIT2) walks EVERY slot on its own graph built from that slot's generated
  pack -- each variant, each fork route alone, side rooms, secrets and relics with and without their trick, shortcuts,
  the set pieces' states, LIFE's spots and cleanup -- and maps rooms by their own boxes, never by x. Before AUDIT2 it
  walked slot 1 only and reused that graph for slots 2-4; on the way it found four real faults, all fixed: a shaped
  streak writing past its room, a dripleaf nook, a floating 2 x 2 trunk, and a room touching the exit whose far rip's
  click box reached through the wall (now `RIP_CLEAR`). **The return margin** (`m/margin`) priced the way back by the x
  offset to the back rip, which a route that turns, doubles back and climbs makes too short (the audit measured the
  warning up to 70 s late, the Night Shift). Since DG2-INTEGRATE a rooms dungeon prices it per room: `slot/s<g>/rooms`
  sets `dg.wb` from the hull the member stands in to `tools/dungeon_clock.py` `walk_back` -- the longest walk back to
  the arrival from any cell of that room, measured on the slot's built grids room to room through shared doors, no
  shortcut, a parkour block counted at sprint / 1.5 -- and `m/margin` reads it (a spine dungeon keeps x). The audit's
  margin check still samples `m/margin` at two x positions with no room state, so it cannot read the per-room margin
  (its MARGIN findings after this change are its own model, not the pack's: an integrator's call). The board's leg
  distances are still x offsets. Relics, lore and the set across runs: section 9. Windows onto earlier rooms are not built. `can_break` on the secret block in
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

## 10. Resource piles: ore by band, heaps, wall veins and the cache (RESOURCES2, 2026-10-10; built and simulated, not run in Minecraft)

The owner, playing pass 2 on staging: "The resource rooms should have piles of ore, based on location in game as well: early
game don't give them great stuff, but late in game a mega stone or two, diamonds, maybe a netherite." And ore in the walls
counts as a resource too. Rung: **datapack plus generator** (`tools/dungeon_resources.py`, `data/dungeon_resources.json`, one
`deposits` dress op in each theme's `dress`, `kinds: ["resources"]`, before `life`); the pick, the refill and the cache's chest
and loot table are the seam's and the vault's own mechanisms, so nothing needed a mod, a scripting layer or a companion.

**What a `resources` room holds.** The seam (kept: 24 blocks) plus:
- **Heaps**: free-standing mounds of the theme's rubble on the room's real outline, 2-3 high, stepped by one block (a
  euclidean dome: neighbouring columns differ by at most one, so they climb), 3-8 of them, 1 block of free floor between. A
  heap whose footprint meets a wall is clipped by it and is a bank against the wall (the room alternates banks and free heaps).
  The top cell of every heap column is an ore candidate; the crests of the tallest heaps take the rare ores. Heaps stand only
  where the walk check's own reach says a player can stand, on no reserved cell (an anchor, the trail, a door's approach), and
  clear any ground cover (the jungle's ferns and grass) above them.
- **Veins**: ore in the rock of a shaped room's walls (cavern, L, broken hall), runs of up to 5 along a wall, two rows high
  from the floor (feet and eye level), the EXPOSED layer of rock only and only where the other five neighbours are solid (so a
  vein never touches the hull wall column, a door, a secret's chamber or the ceiling and floor courses). The two rows of a
  column are always one ore, so a mined column is a pocket a player can step into (the independent audit reads a face that opens
  no standing cell as a secret that opens nothing: the first version, single cells, drew 21 findings in the Night Shift), and at
  most 40% of a band's bulk ore sits in veins; the rare ores sit on heap crests only. A box or oval room has no rock, so its
  wall ore is the banks; the mine's cavern and L rooms get both (24 vein cells, 12 columns, in each of the Night Shift's four
  variants). The jungle has no veins (its rock is a bank of moss).
- **The cache** (bands 5 and 6): a chest at the foot of the biggest heap with a loot table, the vault's form (the kit's
  proven-in-code way to hand over items; `LootTable` on a chest placed from air at the slot reset). It holds the **raw Mega
  stone** and **ancient debris** (below). Band 4 and under: no chest.
Candidate cells per room: 51-93 against a need of 33 (the richest band's count) times 1.5; the room's geometry is the same in
every band and every run, and `dg.band` only decides which candidates are ore.

**The table** (`data/dungeon_resources.json` `table`, one row per resource: `min_band`, `max_band`, counts per band, a why).
Blocks of ore in the heaps and veins, on top of the seam's 24:

| Band (caps) | coal | iron | copper | lapis | redstone | gold | emerald | diamond | cache |
|---|---|---|---|---|---|---|---|---|---|
| 1 (20-25) | 8 | 6 | 6 | | | | | | |
| 2 (30-35) | 8 | 8 | 6 | | | | | | |
| 3 (40-45) | 6 | 8 | 6 | 4 | 4 | 2 | | | |
| 4 (50-55) | 6 | 8 | 4 | 4 | 6 | 4 | | | |
| 5 (60-62) | | 6 | 4 | 4 | 6 | 6 | 1 | 2 | 1 raw Mega stone, 1 ancient debris |
| 6 (100) | | 4 | | 4 | 6 | 8 | 2 | 3 | 1 raw Mega stone, 2 ancient debris |

DUNGEONS.md 9.3's ladder is kept (1-2 coal/iron/copper; 3-4 add gold, redstone, lapis; 5-6 diamond). Additions: emerald from
band 5 (worth nothing to the bank, the owner took it off on 2026-10-08; GREED prices it 400 cp), and the cache at bands 5 and 6. The seam's mix per
band is now authored in the same file and equals `tools/economy_sim.py` `World.seam_face(band)` exactly (the sim's
assumption; the old round robin over every ore the band allowed put 3 diamonds in the band-5 face where the sim and ECONOMY_SIM
assume 1): 1-2 coal 11 / iron 9 / copper 4; 3-4 coal 9 / iron 9 / lapis 3 / gold 1 / redstone 2; 5-6 coal 9 / iron 9 /
lapis 2 / gold 1 / redstone 2 / diamond 1.

**The Mega stone and the debris, and why they are in a chest.** Read from `mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar`:
`mega_showdown:mega_stone` is the RAW stone, the only thing every keyed stone is crafted from (`data/mega_showdown/recipe/aggronite.json`
and 80 more: one raw stone, a species item, iron, a diamond; this pack raises it to 2 raw at the Cutters, `tools/mega_recipes.py`).
It drops only from the block `mega_showdown:mega_stone_crystal` (`loot_table/blocks/mega_stone_crystal.json`, no Fortune), which is
in `minecraft:needs_diamond_tool`; the ten `mega_meteorid_*_ore` blocks drop evolution stones, not Mega stones. The rift pick is
an iron pickaxe, and whether a crystal broken in adventure under `can_break` drops its stone is the unrun half of
SOUTHERN_RIFT_MEGA.md M-5, so the stone is FOUND in a chest, not mined: no new pick, no tool-tier assumption. Ancient debris is
in the same vanilla tag (ASSUMED, not read from a jar), so it goes in the chest too. Which Mega: none. The cache holds the
raw stone, never a keyed one ("I don't want mega stones being free", SOUTHERN_RIFT_MEGA.md 13): it still takes a species item,
a diamond, the Cutters' counter behind the sixth badge and a bracelet, so it trivialises no gym and leaves the choice of Mega
to the player.

**How it was checked not to out-earn the game** (`tools/dungeon_resources.py budget()`, run by `tests/test_dungeon_resources.py`;
every price, rate and tier is read from `tools/economy_sim.py` `World`, i.e. `data/bank.json`, not typed in): per band, for the
shortest of the three dungeons (required hours = `clock_s_by_band` / the 1.25 slack):
1. the bank value of the seam, the heaps and veins and the cache (average vanilla drops, bank buys) is at most `dollar_factor` (1.0)
   x the gathering tier open at the band's lowest badge count x the required hours. Measured: band 1 $266 of $331 (early $620/h
   x 0.533 h), 2 $282 of $774, 3 $534 of $792, 4 $578 of $864 (deep $1,350/h), 5 $1,112 of $1,442, 6 $1,428 of $1,526 (Nether
   $2,120/h). So a dungeon hour of mining is never a better wage than the same hour in the caves, which cost no sigil, no clock
   and no death. Band 6 has 6% to spare: it is the budget's binding band;
2. every rare ore and cache item the bank buys is at most `item_rate_factor` (1.5) x its `rate_per_hour` x required hours:
   diamond 3 of 4 (band 5) and 4 of 4 (band 6, seam's 1 included), gold 7 of 10 and 9 of 10, debris 1 and 2 of 10;
3. the raw Mega stone is at most the Rift farm's rate (1.8 an hour, SOUTHERN_RIFT_MEGA.md 13: RELAYED and an assumption there)
   x required hours: 1 of 1 at both bands (1.22 and 1.30 floored). A second raw stone at band 6 is OVER; "a mega stone or two" is
   one a run until the owner says otherwise (one number, `cache.items.mega.count_by_band`). Tests mutate the table (a second
   stone, doubled diamonds, 60 gold) and the budget fails each.
Emeralds have no price, so only the table's count limits them. Not checked: the boss bundle and gems (items the sim does not
price), co-op, and what a player makes selling to a Produce Buyer (the jungle's produce face is unpriced here and was before).

**The reset and the take.** The shell writes band 1's ore; the room's `reset` (as the entrant, `dg.band`) writes every candidate cell
back to its band-1 block, then each higher band's difference (`execute if score @s dg.band matches N.. run setblock`), and puts the
cache chest back from air with the band's loot table (`cobblers:dungeons/cache/b5`, `/b6`, in the pack) and arms `#s<g>r<i>k`.
**No block has a hook**: GREED (`tools/dungeon_greed.py`) weighs every block the pick breaks by the `minecraft.mined:<block>` stats,
wherever the member mines it, at the block's cp in `data/dungeon_greed.json` (all eight ores of both families, in the table
already), so a pile or a vein counts exactly as the seam does and nothing is counted twice. The one hook is the cache's: its `tick`
line sees the `LootTable` tag go (opened, as the vault does) and runs `cache_open`, which credits the chest's value for the
entrant's band through GREED's own chest entry (`dungeon_greed.chest_lines`, then `greed/add`), once.

**Priced in GREED's points** (cp; 1 point = 100 cp = $100; +0.1x per 200 cp; cap x3 at 4,000 cp; `python tools/dungeon_resources.py`
prints it): the cache is the raw Mega stone at 625 cp and a debris at 200 cp, so **825 cp at band 5 and 1,025 at band 6** (+0.4x
and +0.5x), a little under a vault chest at its dearest. Taking EVERYTHING in one resources room (the seam, the piles, the
veins and the cache) weighs 2,086 cp at band 5 (x2.0) and 2,782 at band 6 (x2.4); bands 1-4 weigh 285, 301, 549 and 993 cp (x1.1 to
x1.4); the jungle, whose seam is produce, 130 to 2,875 less its emerald. So a full take at band 6 does not by itself reach the cap, but
with a vault chest or a catch it will, which is the trade GREED builds. The emerald is the dearest ore at 400 cp (its last bank
price), which is why there are 1 and 2 of it.

**What the pick may break** (`R.pick_blocks`, via `R.PICK_EXTRA_FNS`): the seam's blocks, the table's ore block for the theme's
family (deepslate ores in the mine; plain ores in the jungle's outcrop and the ruin's treasury), and the cracked secrets' faces.
`walk_problems` counts the cells in the built grid and expects the seam, the faces and `meta.breakable_extra` (the band-1 ore
cells this module wrote); the module's own check (`problems`, in `EXTRA_CHECKS`) breaks EVERY candidate of EVERY band and the seam
in a copy of the grid and demands that nothing closed becomes reachable. Every cell is inside the interior with every neighbour
solid or the room's own air, so a taken block opens a pocket in the room and never the hull or the void.

**Items a pile, a vein, the seam or the cache can yield** (for the greed value table): `minecraft:coal`, `minecraft:raw_iron`,
`minecraft:raw_copper` (2-5 a block), `minecraft:lapis_lazuli` (4-9), `minecraft:redstone` (4-5), `minecraft:raw_gold`,
`minecraft:emerald`, `minecraft:diamond`, `mega_showdown:mega_stone` (cache, bands 5-6), `minecraft:ancient_debris` (cache, bands
5-6); the jungle's produce face still yields stripped jungle logs, melon slices (3-7 a block), bamboo blocks, honeycomb blocks and
pumpkins. `python tools/dungeon_resources.py` prints the list, the table and the budget.

**Unproven in game:** that a chest placed with a `LootTable` hands over its items when opened in adventure mode in the pocket (the
vault's own assumption); that heaps of stepped one-block rubble climb as the walk check says; the mining times (a heap of 30-50
blocks is a minute or two with an iron pick, and every block mined weighs on the clock by GREED's mined stats, which are themselves unrun in adventure mode, EXP-073); that
the cache chest reads as a find at a heap's foot. The walk check proves a player reaches every heap, vein row and the cache's
standing cell; it has not been seen. Where it collides with another system: GREED's table must hold a row for every block the piles can hold (it does: the eight ores of both families) and an item cp for the cache's two items (it does), the independent audit's
"the pick breaks nothing but seams and cracked faces" (it reads the generated `can_break`, which now holds the table's ore blocks;
`tools/dungeon_independent_audit.py` is AUDIT2's, not touched here), and `life` (heap and cache ground is kept from its spots).

## 11. The nether themes (NETHER-THEMES, 2026-10-10; built, simulated and audited, not run in Minecraft)

Five themes in `data/dungeon_themes.json`, one per vanilla nether biome: `nether_wastes` (netherrack, glowstone, nether brick,
blackstone; the fire-and-coal one), `crimson_forest` (crimson stems and nether wart on a nylium floor, shroomlights),
`warped_forest` (the same in teal, with the ghosts and imps), `soul_sand_valley` (soul soil, bone fossils, soul torches and
lanterns), `basalt_deltas` (basalt and blackstone columns, ochre froglight seams). Rung: **datapack plus generator**, no kit
code beyond two small hooks below. The rips for these dungeons stand in the Nether: `docs/research/notes/nether-rip-siting.md`
(research only; the engine places rips in the overworld only today). Demo dungeon per theme, 25 rooms with a three-way
crossroads: `tests/fixtures/dungeon_nether_demo.json`; tests: `tests/test_dungeon_nether_themes.py`.

What an author of a nether dungeon must know (each learned the hard way while building these):
- **No lava, fire, soul fire, magma, campfire, wither rose or bubble column anywhere in a theme.** The kit's walk check
  classes them HAZARD and `tests/test_dungeon_rooms.py` refuses them in any theme's data. The heat is told by glow
  (glowstone, shroomlight, froglight veins), colour and the Pokemon. A deliberate hazard would be a kit decision.
- **No vines.** The `trunks` op hangs `minecraft:vine` (`vines_p` 0 in every nether theme) and `canopy` hangs vines beside its
  curtains (`curtain_p` 0). The nether's weeping vines are not in the walk check's passable set.
- **Roots and sprouts** (`crimson_roots`, `warped_roots`, `nether_sprouts`) are in `dungeon_grid.PASSABLE`; the fungi are not,
  because the independent audit's table has them solid. They survive only on nylium or soul soil: the ground cover names
  `on`, a `fallen` scene's `cover` is a wart block, and `floor_lights` never sets a light under a block in
  `dungeon_rooms.NEEDS_SOIL` (roots, sprouts, fungi, soul torch, torch), or the plant would pop off its soil.
- **The seam is the nether's quartz and gold ore, never ancient debris.** The 1.21.1 jar's `needs_diamond_tool` tag holds
  debris and the rift pick is an iron pickaxe, so a mined debris yields nothing while GREED would weigh the block at 200 cp. A
  nether resources room therefore has the seam alone: no `data/dungeon_resources.json` entry exists for these themes, so the
  `deposits` op does nothing (heaps, veins and the Mega-stone cache need a nether ore family and a budget: an owner and
  trainer-balance call). `nether_gold_ore` is priced in `data/dungeon_greed.json` (2-6 nuggets, read from the jar).
- **Soul sand drags a walker to 40 percent in vanilla** and the kit does not model it. It is in the soul valley's floor
  patches (small) and nowhere else a trail is laid on purpose.
- **Species.** Every ambient line is an evolution chain of the jar, belongs to its biome by the jar's nether spawn pools or
  by `NETHER_ENCOUNTERS.md` section 2, and keeps that document's rules: no Fire type outside the wastes and the crimson forest,
  no doll or mis-assembled-model species (`COBBLEVERSE_COMPATIBILITY.md`: talonflame, arbok and turtonator were dropped for it),
  no starter lines (kept for the rare prizes), no legendary.
- **Water is legal** (the pocket is not ultrawarm), so the `flooded` look keeps its one-deep trench; it is never over soul sand.
- Puzzle buttons `crimson_button`, `warped_button` and `polished_blackstone_button` were added to `dungeon_puzzles.py`'s
  passable set (no collision box); the five themes have rows in `data/dungeon_puzzles.json` and `data/dungeon_relics.json`.

## 12. Bank vault, wishing well, bait room (RT-A, 2026-10-10; built and simulated, not run in Minecraft)

The owner's "next phase" room types (DUNGEON_PASS2.md). Rung: **datapack plus generator** (`tools/dungeon_extras.py`, `data/dungeon_extras.json`,
registered through `EXTENSION_MODULES`; three lines in `tools/dungeon.py` build()); nothing needed a scripting layer, a companion or a mod. Fixture:
`tests/fixtures/dungeon_extras_rooms.json` (one of each; the authored dungeons place them later). Tests: `tests/test_dungeon_extras.py`.

- **`bank_vault`** (a `side` entry or an `optional` fork route only, gate `open`; at least 30 x 21 x 8). `params`: `clue_rooms` (room ids of the same
  dungeon, not the entry, exit, boss arena or another vault), `digits` 3..5 (4), `chests` 1..6 (4), `penalty_s` (20), `max_tries` (5), `clock_cost_s`
  (20 a chest), `loot_by_band` (the vault's form; default in the data). The code is rolled at the threshold (`random value 0..9` a digit) and written
  to a wall sign (the theme's `crossroads.sign`, at floor + 2, off the trail) in each clue room by that room's `enter`; digits are dealt round robin, at
  most 3 a sign; the reset writes `?` back. A keypad of ten wooden buttons, a sign over each, a lamp per digit; the code is compared on the last press;
  wrong costs `penalty_s`, `max_tries` wrong codes jam it for the run. The chamber's gate (the theme's gate block, 3 x 4) is shut in the shell and open in
  the walk check's grid; `clear` opens it. Chests are the vault's mechanism (LootTable placed from air, `DG.chest_lines`), held to KIT3's vault budget.
- **`wishing_well`** (at least 20 x 15 x 7, `params.throws` 2, `min_cp` 20). An item entity resting in the pool is read by `Item.id` against GREED's table
  (placeholder `unpriced` rows and anything under `min_cp` refused and thrown back out), value cp x count; `random value 1..100` picks a share of it
  (data `shares_by_band`: nothing 35-38 %, up to 500 %), paid in the dearest item of the band's ladder the pay reaches, rounded down, at most 64.
  Expected share under 0.9 whatever is thrown. GREED is charged the gain, `pay - value`, only when positive. Why that cannot be gamed: data `gaming_why`.
- **`bait_room`** (at least 20 x 15 x 7, `params.lure_room` a living room). A bait from the data table is taken one at a time onto the PLAYER's `dg.bait`
  (survives logout and death); the next run's threshold in a dungeon with a bait room moves it into the run and zeroes it; the lure room's first pass
  spawns the bait's species for the band at the band's lower cap, catchable and wandering, tagged `dg.lure`, a wild Pokemon of the slot. Cobblemon's
  bait items exist in the 1.8.0 jar (`cobblemon:poke_bait`, `poke_snack`, the berries) but its `spawn_bait_effects` are fishing-rod effects, not used.
- **Unproven in game:** a keypad press read once a keeper pass (two in one pass are taken in ascending order); `data modify block` on a waxed sign;
  item entities resting in the pool and read as `@e[type=item]` in the pocket; `data get entity @s Item.count`; the `give @s $(item) $(n)` macro for a
  Cobblemon item; a lure staying in its room; the sound ids. A bait stays stored while the next run is in a dungeon without a bait room.

## 13. Three optional rooms: fishing, eggs, fossils (RT-B, 2026-10-10; built and simulated, not run in Minecraft)

The owner's "next phase" (`DUNGEON_PASS2.md`): rooms that tell whole dungeons apart. Rung: **datapack plus generator**
(`tools/dungeon_extras2.py`, `data/dungeon_extras2.json`, registered in `EXTENSION_MODULES`); the research
(`docs/research/notes/dungeon-room-mechanisms.md` 1-3) found each possible with nothing above that rung. Every room is
optional (`gate` open, no clock in `required`), never closes a way on, resets with the slot and is one dungeon in all four
slots. The in-game halves are `experiments/EXP-090-dungeon-fish-egg-fossil`.

**`fishing_room`** (width at least 25: the pool keeps 4 blocks from the doors' line; length at least 17; height 7; `params.pool_length` odd 5-9, `pool_width` 3-9, `species` a key of
`fishing.species`). A pool of one-deep water (the walk check's wading depth; a deeper one is a pit) on the side of the room away
from the doors, over a bed one under the floor course (`BED_UNDER`), a plank pier, lantern posts, seagrass and sea pickles.
The fish: a boxed `spawn_pool_world` file in the dungeon pack (`data/cobblemon/spawn_pool_world/cobblers_dg_<short>_fishing.json`,
`spawnablePositionType: fishing`, `dimensions: [cobblers:pocket]`, the dungeon's slot rows as `minX..maxZ`) whose entries
require the entrant's BAND MARKER in `neededNearbyBlocks`. Why not the research's first choice, a Habitat Block: a spawn entry
and a Habitat Block both fail to see the entrant's band, the pool must differ by band (stage of the line, levels at or under
the band's lower cap so the level-cap catch block never refuses), and a command-placed Habitat Block activates only after a
chunk reload (EXP-021) with fishing influence untested; the marker is set by the slot reset from `dg.band`, as the seam's
blocks are. Three cells of the pool bed under the pier hold it (white, magenta, light blue, pink, gray, cyan terracotta for
bands 1-6; no theme or puzzle uses them: tested); a bobber anywhere in the 9 x 7 pool is within 4 blocks of one. All 591 stock
fishing entries name a biome, a structure or a dimension and the pocket's biome is `the_void`, so only these fire (tested
against the jar). The wanted species (the starters of each line at the band's stage) are in the `common` bucket (83% of
rolls); each band has a species in each bucket so no rolled bucket is empty. The room lends a marked Poke Rod at the first
step in and takes it back wherever the engine takes the rift pick back (`patch_functions` adds one line after each
`clear @s <pick>`). A fished catch is weighed by GREED as a nest catch (`CATCH_ALIAS`; equal to an ambient catch today).
State: nothing per run but the marker (reset).

**`egg_room`** (at least 19 x 13 x 5). A counter and a vendor, a non-battling NPC class (`interaction: dialogue`, no party)
per slot and band, spawned at the first step in by the macro `npc_at`, bound to the slot (`slot/s<g>/bind`, so the slot's
free and the keeper's stale pass kill it) and killed by the room's reset. The dialogue lists the band's three offers with
a one-line description each; a button runs `take_b<band>_<k>` as the player: refused outside a live run, for another
band's vendor, after the run's one egg (`#s<g>r<i>e` 1) and when fewer than `eggs.price.min_left_s` (60) of the clock would
remain; otherwise it takes the band's price in CLOCK seconds (90-150, about one small fight: the engine's own currency, the
vault's; no CobbleDollars, no item), credits the egg as a nest catch through `greed/add`, and runs
`givepokemonegg @s <species>` (Cobbreeding 2.3.0 registers the literal; the jar read, not run). Eggs: starters at bands 1-4,
Larvitar/Bagon/Gible at 5, Dratini/Beldum/Deino at 6. No legendary, no Jangmo-o line.

**`fossil_chamber`** (at least 21 x 11 x 6). No brushing (impossible in adventure mode, research 3). A bay against the north
wall: a frame and lintel of the theme's wall block around 5 x 3 x 3 dig cells (terracotta, clay, sandstone: used by no
theme), the back layer on the hull wall. ONE fossil block (`minecraft:calcite`) hides in the middle layer; `enter` rolls
its spot among 8 (`random value 0..7`, `#s<g>r<i>f`); dust drifts in front of the face above it. The rift pick may break the
dig block and calcite (`PICK_EXTRA_FNS`, counted by the kit's per-room breakable total, `meta.breakable_extra`). GREED weighs
the mined calcite at 300 cp (`blocks` row; the `fossils` group is the 15 ids of `cobblemon:fossils`, 3 points: a DESIGN
number, one block a run); the room's tick sees the cell turn to air and gives one fossil from the band's loot table
(`cobblers:dungeons/fossil/<dungeon>/<room>/b<band>`: bands 1-2 Omanyte/Kabuto first, the Galar fossils only at band 6).
State: `#s<g>r<i>` 1 armed, 2 given (the kit's `clear`); the reset refills the bay with the fossil at spot 0.

**Collisions to know:** the independent audit's SECRET rule skips a `fossil_chamber` as it skips `resources`; the kit's
walk check still counts the breakable cells per room against `meta.breakable_extra` and the bay's own check demands a solid
frame, lintel and wall. `dungeon.py` build() gains two lines (`DX2.pack_files`, `DX2.patch_functions`). A lent rod survives
only a route out of the pocket that does not run a pick-clearing line.

## 14. Prize pools, per-run rotation, Ultra Beast bosses (PRIZE-POOLS, 2026-10-11; built and simulated, not run in Minecraft)

The owner (2026-10-11): "finish all dungeon work and make sure we have a lot of variety"; every legendary, mythical,
early power mon and Ultra Beast gets a home. Rung: datapack plus generator (`random value` at the threshold, score
conditions, the existing macro spawns and NPC classes). Nothing needs a mod or a scripting layer.

**The Ultra Beast double x5 (fixed first).** The jar's Beast Ball is `LabelModifier(5.0, true, "ultra_beast")` applied
as `ballBonus` (`docs/research/notes/beast-ball-key-1.8.0.md` sections 1-2); the key callback multiplied the catch rate by
5 again, so a tagged Ultra Beast was x25. **The intended effective multiplier is x5 for every key boss.** A boss tool takes
its tags from `key_ball.bind_tag_lines(species)`: the key tag, plus `native_tag` (`cobblers.key_native`) when the jar labels
the species `ultra_beast` (11 species; `data/key_ball.json` `native_species_snapshot` where the jar is absent). The rate
callback skips its x5 at a `native_tag` boss; the refusal callback is unchanged. `key_ball.boss_problems` sweeps every
spawn line of every boss tool (`dungeon_prize.key_sweep_files`): an Ultra Beast bound without the native tag, or a
non-Ultra-Beast bound with it, is a problem. Not run in game (probe UB3).

**Prize pools.** `params.prize` may carry, beside or instead of the single form:
```
"prize": {"roster": "night_shift",
          "rare_by_band": {"1": "pupitar"}, "rare_pool_by_band": {"1": ["gabite", "fraxure"]},
          "legendary_pool_by_band": {"4": ["volcanion", "kartana"], "6": ["kartana", "celesteela"]}}
```
- A band's pool is, in order and without repeats: the single form, the room's `*_pool_by_band` list, then the roster's.
  Same rules per member as the single form (side of `legendary_from_band`, jar species, legend labels), at most 16.
- **The roster.** `roster` names an entry of `data/dungeon_prize_roster.json` (unit COVERAGE); the three dungeons' prize
  habitats name their own dungeon id. Read shapes: `{"dungeons": {id: entry}}`, `{"dungeons": [{"id": id, ...}]}`, or
  `{id: entry}`; an entry's `rare_pool_by_band` / `legendary_pool_by_band` join the room's pools. File absent: the room's
  own pools stand alone (so the record builds before COVERAGE lands). File present but no entry, or an entry naming
  neither pool: a problem. The roster's proposed UB bosses are not read (bosses are `boss.teams_alt_by_band`, below).
- **Per run.** After the presence roll, `#s<g>r<i>ps dg.rs` is set to 1 and, when present and the band's pool has n > 1,
  rolled `1..n`. `enter` runs `prize/spawn_b<b>` (member 1, also any other value) or `prize/spawn_b<b>_<k>`. Level: the
  band's lower cap. Binds: `prize/rare_bind` (any ball), `prize/bind` (the key), `prize/bind_native` (the key, an Ultra Beast).
- **The rumour names no species** (the owner's "not as easily found"; a co-op partner reads the same board).
- **Labels (COVERAGE's F1).** A legendary-pool member is labelled `legendary`, `mythical`, `ultra_beast` or `paradox` by
  the jar (20 paradoxes carry only `paradox`); a rare one carries none of the four. A `restricted` species (the jar's 27
  box legendaries) sits in band 6 only.
- **Model gate (COVERAGE's F3).** A species whose roster record `species.<id>.model_gate` names a gate (`atm_subset`) is
  dropped from every pool until `engine.prize.models_delivered` lists that gate (empty today), so no prize spawns as the
  doll. Without the roster file nothing is gated.

**Rotation of trainers, minibosses and the boss.** One index a room per run, rolled at the threshold into
`#s<g>r<i>x dg.rs` (the boss: the member's `dg.bv`); pool member `((index-1) mod n)+1` fights. Member 1 is also every
value outside `2..N`, so exactly one spawn line fires whatever the score holds (a playtest teleport with no threshold
still gets its fight).
- A trainer's `team_pool_by_band` `{band: [team, ...]}` (1-6 teams, each the band's member count) replaces its
  `team_by_band` for that band; naming both for one band is a problem. Classes: `..._t<n>_b<b>` (team 1), `..._v<k>`.
- A miniboss's `species_pool_by_band` `{band: [species, ...]}` (1-6) replaces `species_by_band` for that band. Spawns:
  `spawn_b<b>` (member 1), `spawn_b<b>_v<k>`. **A catchable miniboss is never a legendary, mythical or Ultra Beast**
  (new check: it carries no key tag, so any ball would take it past the Beast Ball gate).
- The boss's `teams_alt_by_band` `{band: [stages, ...]}` (1-5 alternates, each one crew per stage) adds crew lists after
  `teams[band]`. Classes `dg_<short>_boss_b<b>_s<k>_v<v>`; `claw/boss_begin_<short>` picks the bounds by `dg.bv` too.

**Ultra Beast bosses (ULTRA_BEAST_BOSSES.md section 3).** A UB can be a boss stage's ace today as data: bands 1-5 are
the NPC chain (an NPC's Pokemon is refused at the hit as `not_wild`, F4, ASSUMED U4), so no key tag is involved. A rotating
pair (the Patriarch's Kartana/Celesteela) is `teams_alt_by_band`, rolled at random, not the design's day parity or
first-uncaught pick. **Not built:** the band-6 WILD last stage (E-P6: spawn, both key tags through `bind_tag_lines`,
catch-once advancement, farm mode); the wormhole leg kind; model delivery (F1: seven of the nine render as the doll, and
no check here refuses one, V-UB5). A UB catch today is only a band-4+ habitat prize.

**The simulator** (`tools/dungeon_sim.py`) walks a rotating dungeon once per variant v = 1..V (V the largest pool at the
band), paths labelled `<route>~v<k>`, so every member is walked and fought on its own; the table's `pool min-max lo`
and the per-cell rotation line give the spread. Pools are walked in lock-step, not in every combination.

**Collisions to know:** `tests/test_dungeon_kit3.py`'s key-ball test expects only `prize/bind.mcfunction` files from
`dungeon_prize.build`; a roster that puts an Ultra Beast in a legendary pool adds `prize/bind_native.mcfunction` and that
test's set equality fails until it allows the new name. `tools/dungeon_audit.py`'s boss payout reads `_s<k>.json` only, so
alternates' classes are not in its per-band payout (the first crew list's are).
