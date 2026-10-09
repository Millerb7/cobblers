# Undertow Basin: a creature under the east coast dunes (cell F8, bands 7-8)

**Status:** built as data, a generator, two re-apply steps, ten presence probes and 34 offline tests, 2026-10-09. Not applied
to any world, not seen in game. Source: `data/buried_dune.json`; generator `tools/buried_dune.py`; tests
`tests/test_buried_dune.py`. This is gap 8 of `WORLD_SWEEP_2026-10-09.md`.

## What the player meets

On the shoulder 100 blocks inland from the east strand, at (7282, 5592), the ground is scored by long double-width grooves
(sinuous, a V two blocks deep at the centre) that come up out of the strand, down the high dune on the south-west, in from the
north, and one that leaves the basin to the south and ends in a pit with a heap of bone block at its lip. Ribs of bone block
stand out of the slope east of the basin and one older arch south of it. The grooves all run into a bowl scooped out of the
foot of the ramp: a flat floor ringed by a cut wall on the high west side (the slip face) and open to the east. While a
player is within 48 blocks and it sleeps, sand runs down the wall at random points and plays the soft step of sand; within 24
a slow heartbeat sounds, pitched down.

Stepping onto the bowl's floor (within 14 blocks in 3D of the sleeper's bed, so the floor and nothing above the rim) wakes it:
the floor bursts into sand, the warden's emerge sound plays, and **the Undertow**, a level-55 Sandaconda at twice normal size,
stands where the player was walking. A player who fights it at six badges (cap 50) cannot hold it with any ball; at seven
(cap 55) the level-cap pack lets the ball hold. Nobody else has to see it: it settles back under the dune when no player is
within 52 blocks, and a new one comes asleep an hour of server time after the last was beaten or caught.

## Why this creature, and this site

Sandaconda over Krookodile, Flygon, Hippowdon, Garchomp and the Gligar line: the place needs a body that **leaves a trail**,
and a snake scores a groove where nothing else on that list does. Krookodile, Flygon and Hippowdon are ordinary wild
Pokemon in this very sub-region (`data/spawns.json` east_coast_dunes), so a buried one would only be a bigger copy of a common
thing; Garchomp belongs to the gulch's Mega farm. Sandaconda is in the table too, small, at 38-48: the Undertow is what they
are the young of.

Level 55: the band is 38-48 (tier 7), the cap is 50 with six badges and 55 with seven (`tools/legendaries_audit.py`
`rct_caps`, computed from `data/trainers.json`), and 55 is the tier's ceiling (`next_cap['7']`). The catch gate is therefore
`gym7_cleared` with **no new mechanism**: `data/level_cap.json` already makes every ball break free from a Pokemon over the
thrower's cap. It is not a presence gate: it is there from day one and a player who wakes it early learns the lesson.

The site is a measurement, not the sweep's hand coordinate. On the canonical heightmap the dunes are **paint, not landforms**:
over the cell's part of the sub-region the largest concavity is 5.5 blocks; the shoulder is a smooth ramp (1 in 4) from y108 at
x7258 down to the strand at x~7390, and the sea stands from x7420. So the bowl and the trails are made, by cutting, never by
building up; no sand is written at all (sand is a spawn-condition block, `data/spawn_blocks.json`), only air, sandstone for the
sleeper's bed, bone block and four invisible light blocks.

## Which rung of CLAUDE.md principle 6, and why the earlier ones do not suffice

- **Cobblemon native / a Habitat Block.** An activated block keeps a pool alive within a radius at random surface
  positions on its tick. It cannot hide a creature under blocks, cannot make one named creature rise at the first step into a
  basin, and cannot keep it at one level and size (`data/habitat_blocks.json`, STATE "Wild Pokemon above the cap"). Used for
  nothing here; no Habitat Block is added (and none is ever switched with `data merge`).
- **Configuration / datapack.** No config key exists for it. Native pieces are used: `spawnpokemonat` with `level=` and
  `scale_modifier=` (the Ursaluna den's property, `data/ursaluna_cave.json`), Cobblemon's own NoAI.
- **Functions and commands: used.** The residents' keeper (`tools/resident_encounters.py`, called through
  `resident_files()` as `tools/far_south.py` does), with this pack's own `hold`, `wake`, `settle` and `spawn`, a `signs` function
  of particles and sounds, and `tools/chunk_look.py`'s look-then-act chain for the summon. No scripting layer, companion or mod.

## State model

- **The creature** is one entity per world, tagged `cobblers.res` / `cobblers.res.undertow`, dormant (tag
  `cobblers.res_dormant`, NoAI) in a sealed sandstone bed at (7282, 85, 5592), awake (tag removed, NoAI off) at the basin's floor.
- **The clock** is the objective `cobblers.dune`: `#undertow.gone` (the game time it was first missed on two keeper passes
  running) and `#undertow.abs`. A fresh world starts it READY, so the keeper brings it in the first time a player is within 96
  and nobody within 48; after it is beaten, caught or killed it returns after `respawn_ticks` (72,000, one hour, the Ursaluna
  den's) with nobody within 48.
- **Per player there is no state.** Stepping in wakes it for everyone near; a late joiner meets whatever stands; the gate is the
  thrower's own cap. A player who dies in the fight is the blackout's: a resident that beats a player becomes the claim's guardian
  (tag `cobblers.guardian`), which this pack's `hold`, `wake`, `settle` and summon all leave alone (`keep` selects
  `tag=!cobblers.guardian`). One who disconnects mid-fight leaves the creature awake and leashed to the basin; it settles when no
  player is within 52, with whatever health the fight left (no command that heals a wild Pokemon is proven).
- **Someone who digs 10 blocks down from the basin's floor** finds the bed. It is empty if it has risen and holds the sleeper
  otherwise; it opens on the same trigger, from inside.

## Steps and probes

`R9BD` (before `R9E`): hold the box (`forceload add`), run `cobblers:buried_dune/build`, release. `R18BD` (after `R18FS`): the
look-then-act chain `cobblers:buried_dune/summon`, count read back 1. Pack `cobblers_buried_dune` is a server pack and
world-local (it has a load and a tick). Probes: `data/world_probes.json` key `buried_dune` (nine blocks, one entity).

## Not verified (everything), and what would verify it

Run in a staging server, one session: (1) apply R9BD, R18BD; `presence_audit --only extra` should read 10 of 10. (2) Walk the
sea trail up from the strand; the slip face and heartbeat should show at 48 and 24. (3) Step onto the floor: the creature
should rise within a second, and be roughly 7 blocks long (`scale_modifier=2.0` is unproven: the Ursaluna den shares the
unknown). (4) Leave: it should settle. (5) A six-badge throw should break free; a seven-badge one should hold (the level-cap
hook has never been seen to run). (6) Whether the particle form `minecraft:block{block_state:{Name:"minecraft:sand"}}` shows
(the ambient pack's form, same unproven status). The wake is the same unproven act as the Celebi's and the Ursaluna's (clearing a
dormant flag on a live entity), but needs no battle-start command: a player sends out a Pokemon at it as at any wild Pokemon.
