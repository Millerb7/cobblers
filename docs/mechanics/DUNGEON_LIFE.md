# Dungeon life: what lives in a room, and what it tells

Status: built and simulated, **not run in Minecraft**. Pass 2, unit LIFE, 2026-10-10. Mechanism rung: datapack plus
generator (`tools/dungeon_life.py`, theme key `life` in `data/dungeon_themes.json`); nothing needed a mod, a scripting
layer or a new dependency. The owner, after walking pass 1: "It feels arbitrarily long right now. A lot of the sequences
are good, we just need more life in each room" and "puzzles should have less explanation".

## 1. What a room gets

| Layer | What | Where it is decided |
|---|---|---|
| Animals | 1-2 groups of wild Pokemon living in the room, wandering, spawned on the member's first pass in it | theme `life.ambient` |
| Scenes | up to 3 small set pieces that say what happened: a camp with a cold fire, a cave-in with a beam and bones, a nest of bones, a cairn/shrine with candles, a fallen log, a stack of crates, a waxed sign with a note | theme `life.scenes`, shapes in `dungeon_life.SCENES` |
| Sound, particles | a sound at a scene now and then, a particle puff at a scene, both only while the member is in the room | theme `life.ambience` |
| Light | a scene's candles are placed unlit and lit when the member walks in; the reset puts them out | `life.candle_*`, scene role `candle` |

Per theme: the mine has bats, rock Pokemon, diggers, miners, a mourning Cubone line and a sleeping Geodude in the safe
room; the jungle has bugs, grass/flower Pokemon, snake lines, mushrooms, Tropius and a sleeping Bulbasaur line; the ruin
has pond Pokemon, crabs, ghosts and lamps, two old golem lines and a sleeping Slowpoke line. The scenes use each theme's
own blocks (roles resolved per theme) and the notes are the theme's voice ("Do not follow the rails. They go down.").

Rooms with their own wild Pokemon, trainers or a drop get **no animals** (`nest`, `habitat`, `miniboss`, `stand`,
`gauntlet`/`ambush`, `boss_arena`, `parkour`, `collapse_bridge`, `setpiece`, `entry_room`, `exit_room`): ambient life must
never be mistaken for the room's fight, and a wild room clears on its own tagged Pokemon only. The scenes skip the same
set except `nest`, `habitat`, `miniboss`, `stand`, `gauntlet`, which take scenes (a fight room with a camp in it is the
point). Counts for the pass-2 dungeons (slot 1, from `python tools/dungeon_life.py report`, DG2-INTEGRATE 2026-10-10):
night_shift 9 of 18 rooms have animals (35 spots in each room's largest set, summed), 24 scenes, 4 candles; jungle 14 of
22, 57 spots, 28 scenes, 8 candles; flooded_ruin 9 of 17, 34 spots, 12 scenes, 8 candles. Every spot keeps 3 cells (x
and z) off every cell of every door of its room -- in, out, a side room's, a fork's, a shortcut's -- and the row just
inside it (`DOOR_KEEP`, `door_cells`); a room with no such cell has no animals.

## 2. The animals

- **Not a fight, not catchable, not the sweep's.** They are `uncatchable` (D8: catches only after the Champion; a
  catchable ambient Pokemon would be a *held catch* under `DUNGEON_CATCHES.md`, an owner decision, see 6), at a level
  below the band's **lower** cap (`below` 4-9 levels; band 6 floors at `engine.stands.band6_levels[0]`), the species chosen
  by band from an evolution line (`stage = (band-1)*len // 6`: a three-stage line is stage 0 at bands 1-2, 1 at 3-4, 2 at
  5-6). A player may start a battle with one; nothing in a run depends on it.
- **Spawned and claimed as the fight rooms do** (`spawnpokemonat` by MACRO, then the nearest unclaimed Pokemon within
  2.5 blocks of the spot is claimed): the sweep's keep tag, the slot's tag `dg.s<g>`, the blackout's exempt tag, the run
  id, `PersistenceRequired`, plus `dg.lf` (life) and the room's index in `dg.rs` **on the entity**. A plain
  `summon cobblemon:pokemon` is refused by the server (`.claude/rules/datapacks.md`).
- **Two variants per room**, other animals and other spots; the member's run id picks one (even / odd), so the next run
  of a slot meets different animals. No `random` is used (a room's own `random` rolls, the puzzles', stay theirs).
- **Cleanup.** The room's `reset` discards its own (selector `scores={dg.rs=<i>}`); the slot's free and tend discard
  everything tagged `dg.s<g>` (the same two lines `tools/dungeon_fights.py patch_functions` writes, written again so a
  slot with no wild room is covered); entering room `i` discards the life of rooms `i-3` and earlier (a 26-room run would
  otherwise carry about 50 wandering Pokemon).
- **Where.** On standable, dry, reachable cells of the finished room (after every dressing op), off the trail where
  there is room, at least 10 blocks (horizontal) from the door the member came in by where the room allows; `cluster` or
  `scatter` per group; a `sleep` group (`no_ai`) sits near the room's `rest` anchor (the safe room).

### 2.1 The animals are DATA (why)

A first version wrote a spawn and a claim per animal per band per variant into each room's `enter`: 11,664 commands, and
`tools/dungeon_independent_audit.py` failed with `LIMIT` on the keeper chain (**29,332 static commands without life,
90,136 with**; the audit counts every branch of every slot's rooms in one chain, limit 65,536). So the table lives in
command storage, written at every load by `cobblers:dungeons/life/load` (one `data modify storage cobblers:dungeons
life.s<g>.r<room>v<variant>b<band> set value [...]` line per key, 192 keys per slot), and a room's `enter` is two lines:

```
data modify storage cobblers:dungeons life.arg set value {room:"5"}
function cobblers:dungeons/life/s<g>/go
```

`go` reads the member's band and run parity into `life.arg`, `pick` (macro) copies the room's list into `life.cur`,
`loop` walks it (`mon` per element, `data remove storage ... life.cur[0]`, recurse), `mon` (macro) calls the macro
spawn `at` and in the same function claims the nearest unclaimed Pokemon with `bind` (V15: the exempt tag in the
function that spawns). The static keeper chain is now **35,084** (+5,752). Because the table is written at load, a changed
table ships with the pack and needs no re-apply step (the SHELL is still a re-apply step).

## 3. The scenes

A scene is an ASCII map (`dungeon_life.SCENES`) of cells, each a stack of **roles** (`bedroll crate lamp ring scorch
rubble beam bone skull nest plinth pillar cap candle log cover note`), resolved to blocks by the theme
(`life.scenes.list[].roles`; a role the theme leaves out is skipped). `{axis}` becomes x or z by the rotation, `{rot}` a
random 0-15 for skulls. A scene is rotated and mirrored by the room's rng, seated on a **standable cell off the trail
and keep cells** (`DressCtx.reserved`), on ground that varies by at most one block, and with its stack cut at dy 1
(dy 0 in a room taller than 8): the light check counts every standable cell, and a tall room is lit from its floor.

**A scene is built only if it passes the walk check's own BFS** (`G.walk` from the room's start and its door anchors):
every cell and every point anchor that was reachable before must be reachable after, less the footprint's columns. A scene
that would cut a room is dropped, not built. The footprint and a one-block margin go into `ctx.trail` (not `ctx.keep`: the
glow vines skip `keep` cells and would leave the scene dark), so the later ops (trunks, columns, piles, cover) work round it.
In a theme with `hull.tall_lights` the cells round the floor-light lattice are never used (a heap there took the light and
the walk check found cells at light 0, 2026-10-10). The op `life_scenes` sits after `stream` in each theme's `dress` list
(water is carved first and a scene avoids it) and before the obstacle ops; the op `life` is last.

Signs: `<wood>_sign[rotation=n]{is_waxed:1b,front_text:{messages:[...]}}`, four lines of at most 15 characters, no quotes
(waxed: adventure mode cannot edit them). Candles: `<colour>_candle[candles=3,lit=false]`; the lit state is set by
`setblock` in `enter` (the light only goes up) and restored in `reset`. A dark room gets neither lamp nor candle roles.

## 4. The puzzle text

`data/dungeon_puzzles.json` `messages` holds every on-screen line of the puzzle and vault kinds; `tools/dungeon_puzzles.py`
`say(key)` reads them and sends nothing for an empty text. Now: levers "Match the lamps.", sequence and plates nothing
(read off the console), a wrong attempt "-{s} s.", the vault "Each chest: {s} s." and "-{s} s." per chest. Was: "Set each
lever to its lamp, then press the gold seal." / "Press the buttons in the order the row above shows." / "Step on the
plates in the order the wall shows. Not off it." / "The seal rejects it. -{s} s." / "Wrong button. The sequence starts
over. -{s} s." / "The wrong plate. Back to the door. -{s} s." / "Each chest you open costs 20 s of the clock." / "The chest
costs 20 s of the clock." The clock costs stay: a player must be able to see what a mistake or a chest takes.

## 5. What this module reads of the kit (for the merge with KIT2)

`DressCtx` (`room, theme, grid, trail, keep, level, rng, built, doc, d, slot, standable_cells(), reserved(), air()`),
`built.anchors / meta / functions / ops`, `R.room_start`, `R.flags_of`, `R.BOX_ANCHORS`, `R.NO_STAND`, `R._point_list`,
`R._spread`, `R.LEVELS`, `R.rng`, `R.F`, `R.EXTRA_CHECKS`, `R.register_dress`, `G.walk / classify / PASS / SOLID / WATER`,
and the room fields `i id kind height ix0 ix1 iz0 iz1 floor_in floor_out ceil_y`. If outlines change `ix0..ix1` from a
box to a mask, `plan_ambient`/`_place` already work from `standable_cells()` and the grid, not the box. The floor-light
zone (`floor_light_zone`) restates `floor_lights`' lattice; if the kit changes it, the walk check names the rooms.
The hooks: life lines are **prepended** to a room's `enter`, `tick` and `reset` (a kind's `tick` often starts with
`return 0` on its own state, which would swallow lines after it).

## 6. Not done, unproven, and open

- **In game, nothing.** Unproven: that the macro-spawned, bound animals wander and stay in a loaded room; that
  `uncatchable` Pokemon accept a battle; that a Pokemon holds `dg.rs` and `scores={dg.rs=..N}` selects it; that
  `function ... with storage <list element>` and `$` lines with nested `{...}` arguments run as the simulator models them
  (vanilla 1.20.2+ features, used nowhere else in this pack before); that a candle's `lit` set by `setblock` holds; the
  waxed sign's SNBT; the loudness of the sounds. An experiment: enter the Night Shift's second room on staging and count
  the tagged Pokemon (`/execute as @e[tag=dg.lf] run ...`), then leave, die, time out and re-enter.
- **Open for the owner:** may an ambient Pokemon be catchable? Today no (D8). If yes, they are held catches
  (`DUNGEON_CATCHES.md` 3, 7) and must sit at or under the band's lower cap, which they do.
- **Entities cost.** At most about 12 wandering Pokemon at once per member (4 rooms x 2-3). The prune keeps it there.
- A wandering Pokemon can leave through an open door; the slot's free and tend discard every one, and the prune takes
  the room's own when the member is three rooms on.
- **Tests:** the generator has no test file of its own in this commit (the LIFE brief forbids writing tests for its own
  content); what exists are the changes below to the existing tests and sims (section 7). A test author should cover: every species id against the Cobblemon jar, every sound and
  particle against the asset index, the notes' length and quotes, the scene shapes (a mutation of `_place`'s BFS gate must
  fail a room), the cleanup lines, and the static chain budget.

## 7. Changes outside the LIFE files (needed by the above; decide whether to keep them)

- `tools/dungeon.py` build(): `import dungeon_life`, `fns.update(DL.functions(doc))`, `DL.patch_functions(doc, fns)` and
  `DL.load_entries(doc)` in load.json. `tools/dungeon_rooms.py`: `"dungeon_life"` added to `EXTENSION_MODULES`.
- `tools/dungeon_audit.py` V15: the "tags the entity in the same function" check read only lines starting `execute `; a macro
  claim line starts `$execute `, so the check now strips a leading `$`. (`mon` is a macro function; its claim is the
  proper same-function tag.)
- `tests/pocket_sim.py` (and `tests/rift_audit_sim.py`): command storage was half-modelled (`function ... with storage`,
  `execute store result storage`); added `data modify storage ... set value|from storage`, `data remove storage`,
  `execute if|unless data storage` and list-index paths, so the packs that load the table still run in the sims.
- `tests/test_dungeon_audit.py`: the spawn-site test knew three kinds of site (boss, trainer, wild room); it now knows the
  life walker (`life/s<g>/mon`, expected once per slot of a dungeon with a room of an allowed kind) and drives it from the
  pack's own table for every band.
