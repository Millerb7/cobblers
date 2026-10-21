# Groudon's quake cavern

**RETIRED 2026-10-21.** R14L applied the cavern to the live world at 01:16 that day and the quake opened it; the owner
then asked "undo groudon cave" and chose "Old chamber back". Groudon's record is the sealed chamber at (6672, 5508) again
(its pre-2026-10-20 numbers), and the cavern is its retired site `quake_cavern_v1`: `tools/groudon_cavern.py` emits a
look-then-act cleanup into `cobblers_legendaries` that R14L runs before any summon (refuses with a player in the ravine,
plug, tunnel or hall; kills the cavern's Groudon; puts every cell the carve and the cuts wrote at or under the ground back to
terrain, clears the rim's walls, clears `#groudon cobblers.leg` so the chamber is carved again, and sets `#built` and
`#quake` to 0 last), holding the 88 chunks of the model box for the chain's life. The runtime and build packs are WITHDRAWN
(`tools/reapply.py`). The independent audit is now `tools/groudon_revert_audit.py` (tests `tests/test_groudon_revert.py`);
`tools/groudon_cavern_audit.py` and `tests/test_groudon_cavern.py` are deleted. Everything below describes the cavern as it
was built, which the cleanup must undo.

**Status before retirement: built offline, never applied, never seen in a game.** 2026-10-21. Data `data/groudon_cavern.json`, generator
`tools/groudon_cavern.py`, independent audit `tools/groudon_cavern_audit.py`, tests `tests/test_groudon_cavern.py`. The
encounter stays `groudon` in `data/legendaries.json` (kind `quake_cavern`, run by R14L).

## What the owner asked, and chose

2026-10-20, after playing it: Groudon "feels very lame" beside Kyogre's cave. "This crater should just have a large cave mouth
that opens up after gym 8 is beaten, call it an earthquake or something." Chosen: (1) the FIRST player on the server to hold
`gym8_cleared` sets the quake off for the whole world, and it stays open; anyone may walk in, a keeper turns away anyone in the
hall without the flag; (2) a grand magma cavern roughly the size of Kyogre's basin.

## What was built

A ravine in the eastern bowl, a lit descending tunnel, a hall 56 across with a lava lake, Groudon on a basalt dais.

| Part | Where (measured on `tools/ground.py`) | Made |
|---|---|---|
| The lip | (6706, 5510), ground y108; the keeper's stand is (6706, 5504) | the walk starts here |
| The ravine | south from the lip, z5510-5556, 14 to 20 wide (a 17 mean, walls wobbling per side), floor y108 down to y85 at one block per two blocks of path, open to the sky; its end wall is 48 high | cut AT PLAY TIME, in two stages |
| The plug | z5557-5566 at the ravine's foot, a 9-wide arched mouth in the cliff | cut at play time, the last stage |
| The tunnel | bends 37 degrees to the south-east, 62 long, 9 wide, 4 high at the walls and 7 on the axis, a block lower every 3 blocks, to y64 | carved at apply time inside a stone envelope |
| The hall | centre (6764, 5624), radius 28 (+-1.5), floor y64, dome to y88; 2,162 walkable columns near the dais against Kyogre's basin ellipse of 1,590; 41 blocks of rock over the thinnest roof | carved at apply time |
| The lake | centre (6764, 5614), radius 10, lava y62-64 (its top is the floor's level), a one-block `blackstone_wall` ring round it | placed last |
| The dais | centre (6764, 5638): a ring of radius 7 one block over the floor, a step of radius 4.5 two over, the `smooth_basalt` pedestal at (6764, 66, 5638) | Groudon at (6764, 67, 5638) |

Lights are shroomlights in walls and roofs (1.5 percent of wall cells) and the lake; magma blocks (6 percent) only in walls and
roofs, never a floor. Blocks otherwise: blackstone, basalt, deepslate, polished blackstone in 3-block patches so the runs merge.
Counts: 45,702 cells of interior air, 22,163 of ravine and 446 of plug, 951 of lava, 65,767 solid cells written, about 7,900 carve
commands in 2 parts; the runtime pack is 130 lines.

## Ladder rung (CLAUDE.md principle 6)

**Functions and commands.** Cobblemon native, an addon, the Cobbleverse dependencies, configuration and a datapack have nothing
that opens a hole in the world on an event; a scoreboard, advancement selectors, `fill` and a self-scheduled function do, and
that is all this is. No script layer, no companion, no Fabric mod. The cheaper rungs failed on the one thing that matters:
no data-only mechanism cuts blocks when a flag is first held (Cobblemon's Habitat Block, `party_pools` and the rest are spawn and
battle data).

**New `kind`, not a new tool** (two sentences). R14L's look-then-act summon, the dormant NBT, `met` (Rayquaza's gate reads it),
the Red Orb's pedestal and the retired site's fail-closed cleanup are all keyed on the `data/legendaries.json` record, and
copying them into a second tool would copy their re-run-safety tests too; but a box chain cannot draw a ravine, so the
geometry, carve and quake are `tools/groudon_cavern.py` and the record only says `kind: quake_cavern` and names its data file.

## State model

World state, in the scoreboard; per-player state only where it already was (`cobblers:legendary/groudon/met`, unchanged).

| Holder | Objective | Meaning |
|---|---|---|
| `#built` | `cobblers.gq` | 1 once the carve has finished (its LAST command); nothing acts on an unbuilt world |
| `#quake` | `cobblers.gq` | 0 sealed; 1 rumbled; 2 tremor played; 3 upper ravine cut; 4 lower ravine cut; 5 open for good |
| `#groudon` | `cobblers.leg` | the legendary's open score; set to 1 once, by `opened`, after the plug is cut; `carve_once` and `keep` read it |
| (player) | `cobblers.gq.left` | `leave_game` count, to give a returning player slow falling |

Edge cases:

- **First win.** `cobblers:groudon_cavern/tick` (every 20 ticks) polls `@a[advancements={cobblers:flag/gym8_cleared=true}]` while
  `#quake` is 0 and the cavern is built; the first moment it finds anyone, `rumble` sets `#quake` 1 (so it fires once, however
  many win at once), tells everybody who it was and plays a low rumble to every player wherever they are. No block is written.
  A poll and not a hook in `flag/gym8_cleared/granted` because the hook needs a new field in `data/progression.json` and a branch in
  `tools/progression_pack.py`, runs only when the advancement is first granted (never for a player who already holds it, the owner
  among them) and misses a flag set by a command; the poll costs one `execute if score` a second and at most a second's delay.
- **Joins late, plays in another order.** Nothing is per player: the cavern is open or not. A late joiner finds it open.
- **Disconnects mid-quake.** The stage state is the scoreboard; stages are idempotent and run again when somebody is near. A player
  who logged out over the ravine and rejoins after the cut gets slow falling for 30 s on the first tick they are back
  (`cobblers:groudon_cavern/rejoin`, a function that schedules itself every tick; the 20-tick keeper was up to a second late).
- **A player over the cut when it happens.** Each cutting stage gives slow falling to everyone standing over its box, so the new
  floor is a walk (the audit holds each stage's box to its own cut). The ravine's floor is walkable back to the lip (audited).
- **One state a pass.** `tick` tests `#quake`'s states last first (4, 3, 2, 1, 0), so a line that moves the state on is never
  followed, in the same pass, by the line testing the next one: the tremor and the three cuts fall on four separate passes, a
  second apart at least. (The first draft tested them in ascending order, and all four ran in one tick.)
- **The rim.** The ravine's walls are vertical cuts, so its side rims and its end wall are cliffs of up to **50 blocks** (measured
  with `tools/ground.py`: ground y135 at (6714, 5553) over a floor at y85) on the plateau players cross from the Mining Town. Every
  column the cut leaves standing, with any of its eight neighbours lowered more than 3 under its ground, carries
  `minecraft:blackstone_wall` (the lake parapet's block, `palette.rim_guard`) from one over its ground to one over the highest
  ground of its uncut neighbours, with joined side states, written by the stage that makes the drop: **65 columns after stage 2,
  116 after stage 3** (18 of stage 2's are cut away by stage 3 and cleared; 134 columns walled at one time or another). The mouth's
  walk-in entrance at the lip, where the floor is within 3 of the ground, has no drop to guard and is left open.
- **No flag.** `eject` (once a second, for anyone in the keeper's box without `gym8_cleared`, creative and spectator left alone)
  tells them why and teleports them to the stand at (6706, 5504), ground y107 plus one. The box (x6724-6796, y62-100, z5588-5656)
  holds the hall and the last 20 or so blocks of tunnel before it; the ravine and the upper tunnel stay open to everyone.
- **Dies.** Nothing per player; they respawn where they respawn.
- **Never sealed in.** The whole way is walked in both directions in single-block steps (audit); the opening is never closed again.

## How the opening never runs with its chunks unloaded

The brief's premise is right that a fill at the moment of the win would be useless: Giovanni's gym is 900 blocks from the bowl and
a fill into a chunk nobody holds writes nothing. (Not "silently does nothing" in every case: the game answers "That position is
not loaded", and what is dangerous is a state flag set after it. Here no flag moves on a failed write.) Four layers:

1. **The win writes nothing.** `rumble` is sound, text and a score.
2. **A stage runs only when a player is near it.** Each stage's line in `tick` selects a box: the stage's own write box grown by
   48 blocks. `chunk_gap` takes the stage's extent into account (not only the pad): with a pad of 64 the lower ravine stage came to
   6 chunks, so the pad is 48, and the worst player-to-written-chunk distance is 4, 5 and 4 chunks (audited from the emitted
   lines) against a simulation distance of 6 (`server/config/server.properties.example`; the live `server.properties` was not read).
3. **The stage holds its own chunks.** It begins with `forceload add` over every chunk it writes and ends with `forceload remove`
   (`tools/function_limits.py ensure_loaded`); a write after an add in the same function lands, measured in this repository
   (function_limits docstring, 2026-09-21).
4. **A read-back moves the state.** `#quake` goes from k to k+1 only if a probe cell reads `air`; the audit proves each probe was
   rock before the stage and air after it. A stage that wrote nothing is run again a second later.

The look-then-act chain in `tools/chunk_look.py` is for ENTITIES arriving after a load; the one entity here, Groudon, is
summoned by R14L's existing chain at the dais. (If forceloading alone is enough, as layer 3 says, the opening could run at the
win; it waits for a player so that somebody sees it, and for the read-back.)

## Dormant until the quake

Cobblemon ignores Invulnerable (EXP-023), so the block seal is the protection, as before: Groudon stands in a room whose every
void has a stone envelope four thick (the audit demands that the CARVE WROTE those blocks, since a terrain model that is solid
everywhere cannot see a missing envelope), and a flood from its cell through air and lava never reaches the sky before the plug is
cut. After the quake Groudon is as killable as any placed Pokemon (the open question the data already records). It is woken, once,
by `legendary/groudon/wake` (a tag on the entity, so a Groudon summoned again after a re-export is woken too).

## Retiring the old chamber, and the order in the owner's world

`data/legendaries.json` groudon `retired_sites[sealed_chamber_v1]` freezes the numbers the old chamber was carved from. R14L runs,
in order: the cleanup (refuses while a player stands in the old shaft, adit or room, and the run stops; restores the voids and the
3x3 plug to terrain, clears `#groudon`, kills Groudon in the old room), `cobblers:groudon_cavern/load`, the hold, `carve_once`
(skipped if `#groudon` is 1 or `#quake` is 2 or more), **the read-back of `#built`** (`cobblers:groudon_cavern/built_read` copies it
to `#groudon_cavern_built cobblers_chunk_look`, and the step reads `1 of 1`, so a skipped or unfinished carve stops the run), the
release, and the summon chain (`1 of 1` read back at the dais), whose summon is itself held to `#built cobblers.gq` = 1, so a skipped
carve never puts Groudon into rock.

**The old plug opened by a player** (the live world: `#groudon cobblers.leg` is 1, the plug is air, the owner stood inside). The
restore is gated on the old pedestal standing, and it clears `#groudon` first, so while the pedestal stands the live world is
restored and the new carve runs. If a player also took the pedestal, the restore now runs on a second gate: the pedestal's cell, the
cell over it and the passage's middle at its floor all read air (three cells natural rock does not hollow together, so a world
that never had the chamber is still left alone). The restore puts rock in all three, so neither gate fires twice. A player standing
in the old voids still refuses the cleanup and stops the run, as before.
`tools/legendaries_audit.py`'s existing cleanup audit, which derives the old chamber itself, passes for it; the new box starts at
x6690 and the old hull ends at x6686. The surface block of the 3x3 patch is a guess (`basalt`, the subregion `east_cones` preset
`volcanic`; `surface_verified: false`, as for Regigigas).

Consequence for the live world: the owner already holds `gym8_cleared`, so the rumble sounds within a second of the carve's end,
and the opening runs when anyone first comes within about 50 blocks of the bowl's south end. The `met` advancement the owner
already has, and Rayquaza's gate that reads it, are untouched. The Red Orb cache (`groudon_red_orb`) moved with the pedestal:
container (6764, 66, 5638), trigger box (6760,66,5634)-(6768,69,5640), item, flag and message unchanged.

## Measured clearances

(`tools/groudon_cavern_audit.py`, to the cells themselves, against every authored coordinate in the Mining Town's and Fossick's
data.) Nearest authored position to the ravine's cut: **81 blocks** (a Mining Town street point, (6636, 5612)); to the tunnel and
hall, horizontally: **78 blocks** (a worker's face, (6680, 5690)), with 41 or more blocks of rock over the cavern; to Fossick's hill
rect (6755-6795, 5786-5823): **134 blocks**; the Mining Town's square (6600-6640, 5688-5711): **67 blocks** from the cavern's
bounding box. The spawn-free zone: `data/spawn_suppression.json` `groudon_cavern` [6728,5592,6799,5655], the hall (a zone is x and
z for every y, so it also takes the plateau over it out of the wild spawns, 72 by 64 columns); the ravine and tunnel are not zoned.

## Proofs run, and what they do not prove

Review 2026-10-21 (an independent Opus read of the code) found six defects; fixed: the rim (above), one state a pass, the stage's
slow falling unaudited, the skipped carve (the read-back and the summon's hold, the cleanup's second gate), the late rejoin. The
sixth, Kyogre's blackout exempt tag, was not applied: Kyogre carries it because its keeper re-sleeps and moves its Pokemon, which
would fight a blackout guardian's leash (`docs/world-building/KYOGRE_CAVE.md`); nothing moves Groudon once the cavern is open (`keep`
runs only while sealed, when nobody can reach it), every other legendary in `tools/legendaries.py` goes without it, and the tag
also takes the item claim out of a loss, which is a gameplay rule for the owner to choose, not a defect fix. The fixes were made by
one agent that also extended the audit and the tests (the brief asked for both).

Run (offline): `tools/groudon_cavern_audit.py` (375 checks, 0 failures: envelope, seal, plug thickness, the walk in both
directions with headroom 4 at its least over 193 steps and a 41-block descent, no hurting block / lava within a block / drop of more
than 3 on any reachable cavern cell, lava walled on four sides and under, no water, the keeper's box and stand, the stages' chunks
and probes, the rejoin line, the cleanup, clearances, the spawn zone, the hall's size). `tests/test_groudon_cavern.py` mutates the
GENERATOR (never the data) in sixteen ways and the audit names each fault: two-block steps, a one-block tunnel, no lake wall, lava
above the floor, a hall wider than the keeper's box, a thin envelope, magma in floors, a trigger wider than the simulation distance,
an always-air probe, a cleanup that writes nothing, an unguarded rim, a rim guard one block high beside higher ground, a stage
with no slow falling, the states tested in ascending order, a summon not held to `#built`, and a read-back that copies nothing. **The same session wrote generator, audit and tests** (the brief asked for
all three), so an independent reader should read the mutation table before trusting it.

NOT verified: anything in a game. The rumble's sound and text, the tremor, the cut, slow falling, the keeper's teleport, the
dormant Groudon's sleep and wake, the Red Orb trigger, R14L's real run (carve of 88 chunks, `forceload add` loading them in the same
tick), the lava's behaviour, what the natural terrain is made of (the heightmap has heights only; the ravine's walls and floor are
whatever is there), the live simulation distance, whether a player can squeeze between two wall posts (the states are written
joined; the audit treats a wall as a cell nobody stands in), what the rim's natural surface is made of (the walls stand on it), and
how long slow falling must last (the audit holds it to more than 0 s; no descent speed is sourced). A short `effect nausea` plays during
the tremor stage for players within 40 blocks as the only camera shake the game has; delete that one line if it is unwelcome.

## Needs

- EXP: apply to the disposable world with the owner's flag held, `reapply.py run --only R14L` (about 30 s), read back
  `presence_audit` for `groudon_cavern` (10 probes), stand at (6706, 108, 5504) and watch the four stages; walk down; hold the
  flag back with `advancement revoke` to see `eject` at the keeper box's edge near (6733, 76, 5600).
- `python tools/compile_spawns.py` and the spawn tests, because `spawn_suppression.json` gained a zone.
- STATE.md lines for this (the orchestrator's: this agent does not edit it).
