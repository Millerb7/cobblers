# The Drowned Quarry under Lake Tilpey

**Status (2026-10-09):** built offline, audited offline, **not applied to any world and not seen in game**. The record is
`data/drowned_quarry.json`, the generator `tools/drowned_quarry.py`, the independent audit
`tools/drowned_quarry_audit.py`, the tests `tests/test_drowned_quarry.py` (51), the re-apply step `R18DQ`, the pack
`cobblers_drowned_quarry`, the probes `data/world_probes.json` key `drowned_quarry`.

**The owner, 2026-10-09:** "a large lake monster in Lake Tilpey, with an underwater cave a player with Dive can reach."
The model is the Ursaluna den: a creature, a place that suits it, strong enough that meeting it early is a mistake.

Every number below was measured by this unit on the canonical heightmap, the replayed pack or the Cobblemon 1.8.0 jar
unless it says "relayed" and names its source.

## 1. What it is

East of Lake Tilpey's centre the lake bed climbs to a stone wall: at z4108 the ground is y58 at x6386 and y75 at x6398,
then a shelf at y75-76 (one or two blocks of water) to the shore at about x6430. The fiction is a quarry that was cut
into that wall before the water came up, and the lake kept it:

- **The haul road** (open cutting): a laid road of stone bricks, 7 wide, from (6340, 4108) at the foot of the lake, 25
  blocks under the surface (floor y52, lake level y77), east across the open bed. Lanterns stand on stone-brick posts
  either side every 12 blocks: from the shelf it is a line of lights going into the dark.
- **The portal** at x6392, where the wall closes over the road (the roof first has 5 blocks of ground over it for good;
  measured cover there 12, ground y70-75 over a roof at y58).
- **The adit**: 120 blocks of flooded haulage tunnel, 7 wide and 6 high, with a square dog-leg (east, south, east) and a
  timber set (two spruce posts, a beam and a hung lantern) every 8 blocks. It runs under 12 (at the portal) to 37
  blocks of ground.
- **The hall**: a pillar-and-room hall 53 by 37 and 16 high (x6488-6540, z4114-4150, y53-68) under 26 or more blocks of
  ground (measured least cover over its roof), with four 3 by 3 pillars, a crane whose last cut block still hangs on its
  chain, three stacks of dressed stone, the ribs of a skiff, and twelve hung lanterns.
- **The sump**: a round pit 17 across and 6 deep at the hall's east end, gravel floor, bone blocks on it. Everything else
  here is square; the one round thing is where the lake's oldest Gyarados lies. It is the drowned shape of the lake's
  own history, as asked: a working the water took, and a lair in its sump.

Everything is water. There is no air pocket anywhere, deliberately (section 4).

## 2. The creature: Gyarados, level 60, scale 2

Weighed (hitboxes and model bounds read from the Cobblemon 1.8.0 jar; roster and mount facts from the repo files named):

| Species | Why not (or why) |
|---|---|
| **Gyarados** | **Chosen.** The lake monster everyone already knows (the Lake of Rage's); serpentine, so a serpent's hall suits it; the lake already spawns it (`data/spawns.json` `tilpey_waters`, 38-48, and an alpha "heart" Gyarados 48-55 within 160 of the lake's centre), so this is the old one and the ordinary ones are its young. The jar's poser has an underwater SLEEP pose (`water-sleep`). A Surf species, not a Dive mount, so the lair hands the player no mount. |
| Milotic | Beauty, not monster; it is already Victory Road's Drowned Gallery's (STATE) and in `tilpey_waters` as an ordinary spawn. |
| Lapras | A gentle species and the Surf mount the region gives away; a boss Lapras fights its own gift. |
| Wailord | A Dive mount (`data/water_mounts.json`), so the boss would be the gate's own key; model 5.1 by 3.5 by 6.3 blocks before its species base scale of 2.5, so at 2.0 it would not fit any hall a wall can hold. |
| Dracovish | A fossil species: the lake has no fossil fiction. |
| Basculegion | In `tilpey_waters` already; a ghost, not a lake monster. |
| Kingdra, Barraskewda | Hitboxes 0.9 by 3.0 and 0.6 by 0.5: not large. |

- **Level 60**: the eight-badge cap. `data/legendaries.json` `level_caps.upper_bound_by_badges` gives 50, 55, 60 for six,
  seven and eight badges, and `data/level_cap.json` makes every ball break free for a Pokemon strictly over the
  thrower's cap. So it is 10 over a six-badge thrower (Dive is taught after `gym6_cleared`, `DEATH_AND_WIPE.md` line
  318, relayed: the NPC that grants it was not read) and 12 over the top of the lake's own band (38-48).
- **Catchable at `gym8_cleared`**, and by nobody with seven badges, by the level cap alone. This pack adds no capture
  hook, no flag check and no `uncatchable` property. It rests on the same unproven chain as every legendary at its gate
  (STATE "The level-cap trap": no throw has been seen).
- **Scale 2.0** (`scale_modifier`, read from the jar by the Ursaluna's record). Model cube bounds as built: 4.1 by 11.0
  by 3.2 blocks, so 8.2 by 22.0 by 6.4 at scale 2; hitbox 2.0 by 3.3, so 4.0 by 6.6. The hall (16) and the sump (6) give
  22 blocks of water over the sump's floor, the pit is 17 across: it fits, exactly in height. These are cube bounds
  ignoring bone rotation, so an over-estimate; the audit fails if either dimension stops fitting.

## 3. The state machine (the residents', with the den's boss rules)

Dormant (NoAI, NoGravity, Unbattleable, Invulnerable, PoseType SLEEP, the Celebi's and the den's flags) on its spot in the
sump, facing the door. A keeper loop every 40 ticks, only while the sump's chunk is loaded:

- **Wake**: a non-spectator within 24 of the spot. A state check on the keeper's own loop, never an advancement. 16,399
  of the hall's 31,982 water voxels are inside it; the road, the portal and the hall's door are not (the hall's west
  face is 40 away); the nearest ground a player can stand on is 51.5 blocks from the spot.
- **Awake**: Unbattleable 0b and RecalculatePose 1b, NoAI and NoGravity stay on; a message and a sound. The fight is the
  player sending out a Pokemon at it; Cobblemon 1.8.0 has no command that starts a wild battle (the den's finding).
- **Settles**: awake and nobody within 64, it goes home and sleeps (health is whatever the fight left).
- **Returns**: beaten, caught or killed are one thing, absent. Absent on two loaded passes in a row starts a clock
  (game time, the den's 72,000 ticks, one hour); after it, with nobody within 48 and a player within 96, it comes back
  asleep. No battle_fainted or pokemon_captured callbacks (the den's only start the clock 80 ticks sooner).
- **The blackout's guardian**: a wild victor becomes that claim's guardian (tag `cobblers.guardian`). From then on this
  pack never touches it and still counts it as present (the residents' rule, `data/resident_encounters.json`).

## 4. The Dive gate, from the rules, measured

Tilpey is 25 deep at this foot, so **depth alone cannot gate it**: `WATER_MAP.md` line 32 says a no-mount player "can
touch the floor and come back. They cannot search it", and it also says "A lake floor never needs Dive" (section 0). This
place contradicts that rule on purpose, on the owner's instruction, and the rule's own words give the way out: Dive
matters "where a place is longer or more enclosed than one 60-second breath". The gate here is the **length of the
flooded way**, and the room has no air so a Surf swimmer cannot rest in it.

Rules used (each with its source; none measured by this unit): a sprint-swim is 5 blocks per second and Dive adds a boost
to about 10 (`WATER_MAP.md` "Measured", STATE death-and-water line); no mount holds 15 s of vanilla air and a lethal second
hit a second after the first; Surf holds 45 s (`data/blackout.json` `water.surf_bonus_ticks` 900) plus 15 s; Dive holds air
flat ("held air flat for over two minutes", STATE, EXP-042).

Measured by the audit, a 26-neighbour shortest swim through the replayed water from the lake's top water voxel over any
painted column of the corridor (a swimmer breathes at the surface wherever it is):

| Target | Blocks | No mount (15 s) | Surf (60 s) | Dive (10 blocks/s, air flat) |
|---|---|---|---|---|
| The portal | 24 | there and back in 9.6 s: it can touch the mouth | yes | 2.4 s one way |
| The hall's door | 137 | one way 27.3 s: out of air 12.3 s before it | there and back 54.6 s of 60: 5 s to spare | 13.7 s |
| The Gyarados | 180 | no | arrives with 24.1 s left, needs 35.9 s to leave: it cannot fight | 18.0 s |

So a swimmer without training can see and touch the portal; a Surf swimmer can reach the hall's door and come back; only
Dive's flat air lets a player spend a battle in the sump. `tests/test_drowned_quarry.py` shortens the road and watches
the audit's `reach` check fail.

## 5. Why this site

The whole lake was scanned: 3,000 sampled foot points at depth 23 or more, each tried in 24 directions for a wall that
reaches y63 within 60 blocks and y100 within 180: 535 (foot point, direction) pairs qualified. The choice among them:

- The **east wall** keeps the way in off the path: the portal is 165 blocks and the road's first column 215 from the
  nearest route-path point (measured against `data/route_paths.json`), so the lake stays catchable and uneventful and the
  monster is a place you go to (STATE "Wild Pokemon above the cap are welcome").
- **Route 7** (Sabrina to Blaine) does pass over the lair: its nearest path point, (6552, 4155) at ground y104, is 33
  blocks from the sump horizontally and 66.5 in 3D, over 36 blocks of rock. Nothing wakes it (the trigger is 24), and a
  player on the road is walking over the thing.
- It is 816 blocks from Uxie's grotto (5714, 4079) and 481 from the Dive arch (6076, 4296): no two systems share a spot.
- The wall gives at least 12 blocks of ground over the road past the portal and 26 over the hall, with no shaft to the
  surface: nothing leaks water into dry space (audit `containment`).
- The west lobe (5192, 4024) qualified too and is more remote with no route within 260 blocks; the east one has a land
  route (the east shore) to the shelf. The north-west arm (the glacier's drowned trough) was not examined as a site, and
  both islands carry other places (the Weeping Elder and Uxie's grotto).

## 6. State model and multiplayer

| State | Where | Scope |
|---|---|---|
| The Gyarados | one entity, tags `cobblers.dq` and `cobblers.dq_dormant`, NBT dormant flags | **server-wide**: one for everyone |
| Return clock `#gone`, count `#abs`, length `#resp` | scoreboard objective `cobblers.dq` (world-local pack) | server-wide; `load` sets `#gone` only when never set, so a restart never moves it |
| The catch | the thrower's own level cap (`rctmod`) | **per thrower**: eight badges catch it, seven do not |
| A loss to it | the blackout's claim and guardian | per player (the blackout's) |

- **Late joiner**: nothing to initialise; the gate is the joiner's own cap and Dive training.
- **Two players**: the first within 24 wakes it for both; a second arriving mid-fight finds it awake; the fight is
  whoever sends a Pokemon out. A player at seven badges can fight it and cannot take it.
- **Death or disconnect mid-fight**: a loss makes the blackout claim and the guardian above; a disconnect leaves it awake
  until nobody is within 64, then it sleeps on its spot.
- **Out of order**: nothing in this pack orders players; Dive and the badge count are each player's own.
- **Caught**: it still returns after an hour (the den's rule, the owner 2026-10-02: "one that returns is a place").
  That makes a level-60 Gyarados farmable once an hour at eight badges; the same trade the den made. The owner may want
  the Quarry's returns to stop after a catch: one line in `keep`.

## 7. Not verified (needs a running server; the first experiment)

Nothing here ran in a server. In order: the fills land (15 by 4 chunks forceloaded, 127 shell fills, 25 void fills, 956
setblocks); `spawnpokemonat` through the macro at a fractional position with `scale_modifier=2.0` and `no_ai`, and that it
renders twice normal size; the underwater SLEEP pose shows; Unbattleable 0b lets a battle start on a NoAI Pokemon, under
water; the player's Pokemon can be sent out underwater and Dive's air holds through the battle (the ladder was measured
swimming, not in a battle); lantern light at 25 blocks down; and what ordinary lake spawns do in the hall (below). The
fills assume the rock under the bank is solid; the shell (4 blocks, filled before the void) is the proof for any cavity
within 4 blocks, and the audit proves that it was written, not what natural worldgen holds beyond it.

## 8. Collisions and follow-ups

- **`data/spawns.json`**: not edited. The lake's own Gyarados (38-48 and the alpha heart 48-55 within 160 of
  (5870, 3874)) are 700 blocks from the sump; the boss is above both. The other agent's Tilpey spawns may place
  Pokemon in the hall (the lake's boxes reach the east lobe); `data/spawn_block_policy.json` carries a `drowned_quarry`
  water entry saying so. If a playtest shows the hall full of ordinary spawns, add a Habitat Block there (not built).
- **`tools/lake_life.py`**: its skin writes 9 silt cells inside the void (measured by running its model); R9LL runs before
  R18DQ, which overwrites them.
- **`WATER_MAP.md`** ("a lake floor never needs Dive") is contradicted on purpose; the doc is not edited here.
- **Story**: nothing points a player at it. The Dive diver on Tilpey's north shore is the natural voice; that is Codex's.
- **Registrations**: `tools/reapply.py` (`SERVER_PACKS`, `WORLD_LOCAL`, two prepare jobs, step `R18DQ` after `R18U`),
  `data/world_probes.json`, `data/spawn_block_policy.json` (water, scoped to `drowned_quarry`),
  `data/system_contracts.json` C4 tools, `tests/test_system_contracts.py` `_source_blocks()`.
