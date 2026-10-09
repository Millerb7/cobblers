# The Long Count: a woman, an old Grotle and thirteen trees pointed at the world tree (C3, band 2)

Built 2026-10-09 for the world sweep's gap 4 (`docs/world-building/WORLD_SWEEP_2026-10-09.md` section 7): C3 is 100% land
beside Route 3, empty, and nothing anywhere was gated at gym 2. Data `data/long_count.json` (hand-authored), generator
`tools/long_count.py` -> `build/datapacks/cobblers_long_count` (world-local: its keeper spawns a Pokemon), re-apply steps
**R9LC** (blocks, after R9FS, before R9E) and **R18LC** (the Grotle, after R18FS); Perrin is seated by the existing **R9F**
from the `npc_grant` record `long_count_thanks`. Builder's tests `tests/test_long_count.py`. **Not audited, not applied, not
seen in game.**

## The place

Perrin Hale counts. Thirteen springs ago a Grotle got up from a hollow and began to walk toward the world tree, eight paces
a year; every spring it sits down and a seedling is where it sat. Perrin keeps the count: a post and a sign at each
seedling (YEAR 13 down to YEAR 0, with what she made of the year and a cold camp), a lane kept open through the wood so the
young trees get light, a fire, and a spruce pole forty-two blocks high with a lantern on top that she lights every dusk
"so the tree can see her coming". The line points at the world tree: it runs at bearing 45.0 from the Grotle and the
tree's centre is at 225.0 from it (the build refuses more than 2 degrees off). At the present pace the Grotle reaches the trunk
in 22 years; Perrin will be ninety-odd.

| What | Where (x, z), y | Measured 2026-10-09 (`tools/ground.py`, never a world) |
| --- | --- | --- |
| Perrin's lean-to, fire, tally board | centre (2136, 2160), floor y123 | ground y123; dry; Foothill Woods, tier 3 |
| The count pole | (2128, 2168), floor y122, lantern y164 | 42 blocks above its floor; ladder on the west face, platform at +35 |
| Old Pace, the Grotle (L29) | (2147, 2149), feet y124 | ground y123; 168.3 blocks from the trunk's near face |
| The lane | 104 paces from (2147, 2149) to the far end | ground rises y123 -> y129 over it; 11 wide, 1,267 columns cleared |
| 14 stakes, trees (1 to 8 high), 13 cold camps | every 8 paces along the lane | one oak log + azalea-leaf tree and one sign post per year |
| The tin (Miracle Seed, 2 Oran Berries) | (2223, 2073), barrel set at y129 | under the YEAR 0 stake, 108 paces down the lane |
| Perrin Hale (NPC) | (2140, 2159), feet y124 | 12.2 blocks from the Grotle, outside its trigger of 7 |

Distances from Route 3 (nearest path point): camp 163, Perrin 165, Grotle 165, tin 204 (all over the 128 a named resident
needs). From the world tree's centre: camp 170, Grotle 185. Nearest authored point 102 (the Habitat Block of
`elder_foothill_grove_1`); nearest route corridor box 96. Whole bbox (2125, 2066)-(2230, 2171) is inside cell C3.

## What a band-2 player does

- **Walk the line.** Each stake is a line of Perrin's diary; the trees grow from a sprig at the Grotle to eight blocks at the
  far end. Nothing here needs a fight.
- **Talk to Perrin** (R9F-seated NPC, a conversation of 18 nodes): what she counts, the Grotle, why the trees point at the
  tree, the pole, the far end. Her one fact about Pokemon is Cobblemon 1.8.0's, read in the jar: a level-32 Grotle becomes
  a Torterra, and holding a sapling it wears that tree (`species/generation4/grotle.json`, `grotle_torterraoak` etc.).
- **The request.** She has not been under the world tree's roots in nine years (her knee) and asks to see a Sitrus Berry off
  them. The roots' cache (`r3_world_tree_roots`, 95 blocks off Route 3) gives two. The berry is SHOWN, never taken
  (`held_item` is a condition only; `consume_held_item` would empty the stack): she gives 2 Growth Mulch, once per player.
- **The find.** The tin at the oldest tree: a Miracle Seed (held, Grass moves) and 2 Oran Berries, once per player, by the
  existing cache mechanism (`long_count_first_oak`).
- **The Pokemon.** Old Pace is a Grotle L29, a Pokemon the sub-region already spawns (`turtwig`, tier 3). Gate gym 2: the
  level-cap refusal is the catch gate (cap 25 with one badge, 30 with two; `gym_ace_levels[1]`, `[2]`). It has no presence
  gate, so a first-time visitor can meet it, wake it and lose to it; they cannot catch it until Misty is beaten.

## Why it is not like the others

A creature that WALKS and a person who COUNTS: the place is a line in time, readable as a gradient of tree heights, not a
den, a cave, a summit or a hideout. The other tonight-builds are a swamp den, a lake monster and its cave, Tilpey's spawns,
Mushroom Island, a reason to sail to Sunset Island, a snow castle, an ice-fishing lodge, an open-summit creature, a buried
dune creature and a sea-stack rookery. It also answers the world tree without copying the Warden Grove (a city IN the
tree, set aside by the owner): this is the ground-level, human-scale reply, and it points at the tree rather than
climbing it. The nearest Pokemon neighbours are Hesketh Fell's Sudowoodo (D2, a tree that will not move) and this
Grotle (a tree that will not stop).

## Mechanism rung (CLAUDE.md principle 6)

Datapack functions and commands only: the block pass (`fill`/`setblock` functions, forceloaded by a re-apply step), the
existing residents' keeper (`tools/resident_encounters.py`: scoreboard clock, tags, schedule loop, the EXP-046 macro
spawn), a compiled Cobblemon NPC dialogue (`tools/compile_dialogue.py`) and the rewards pack's advancement. Nothing
above that rung was needed, so nothing is proposed: no config key, no mod, no script. The previous rungs (native,
addon, dependency, config) cannot place blocks or seat a keeper.

## State model

- **Perrin**: a shared static NPC; her state is per player (`quest.evt_long_count.started / reward_claimed /
  dialogue_cursor`, in `q.player.data`). A player who joins late, dies or disconnects loses nothing: the cursor persists
  after each node; the reward is claimed once per player by `grant_reward_once` on `reward_claimed`.
- **The tin**: a per-player advancement (`cobblers:reward/long_count_first_oak`); the barrel is scenery.
- **Old Pace**: one shared world entity (tags `cobblers.res`, `cobblers.res.old_pace`, `cobblers.res_dormant`), scoreboard
  objective `cobblers.lcres` (its respawn clock survives restarts). Dormant (NoAI) until the first player within 7 blocks;
  awake, leashed to 16 of its rest and settled back when everyone leaves; comes back 36,000 ticks after it faints, dies or is
  caught, only with a player within 96 and none within 48. Once the blackout makes a loser's Pokemon its guardian
  (`cobblers.guardian`) this pack counts it and never moves it.
- **Order**: none required. Tin, Perrin and Grotle are independent; only the Sitrus Berry ties Perrin to the roots' cache
  and the catch ties the Grotle to Misty's badge.

## The site search, and what "seen from Route 3" means here

Every rule for a named resident held: inside C3; 96 from every x/z another data file authors and from every route
corridor box; 128 from every route path for the centre, NPC, Grotle and tin; outside towns and Rift zones; a level inside the
tier ceiling; a leash clear of every activated Habitat Block; the line pointing at the tree. Searched on the heightmap
(centres on a 6-12 block grid, lane built for each), those rules leave the north-west corner of C3 only: the road lies
west of the tree and the line has to run away from it. Findings:

- **The corridor-box rule (96) keeps a compliant site far from the Route 3 path: the nearest the search found was 163.**
  (Route 3's spawn-corridor boxes reach 47-57 blocks from the path at their corners, measured on `r03_b0065`-`r03_b0072`,
  so a column 96 from a box is roughly 145-160 from the path; measured as 163 for the camp and the pole.) the server's `view-distance=10` (`server/config/server.properties.example`) loads chunks within 10 of
  the player's chunk and vanilla fog ends near 160. The pole is therefore **at the edge**: 99 path points (from
  (1968, 2098) to (2028, 2000), 163-196 blocks from the pole) have the lantern in their loaded chunk window and in line of
  sight over the terrain, the world tree's trunk and the grove's elders; the rest of the road does not. Distant Horizons
  (in the pack, for everything past about 160) may draw a 1-block pole; that is not tested. **The canopy is not
  modelled**, so "seen" is an upper bound; a gap in the trees at the roadside is what makes it so.
- **A reduced clearance (an owner decision, not made here)** would show it fully: a pole 100 from the path is inside the
  160-block fog. Not done, because the 96 rule is the residents' and the audits'.
- **One exception, declared in the data** (`rules.superseded_points`): the nine points sampled from the superseded town
  footprint [2224, 1833, 2470, 2079] in `data/towns.json` (`gym3_town` `site_history`, "superseded 2026-09-16 ... kept as
  the fallback") are not counted as authored, because the lane's far end runs within 96 of them and nothing stands
  there. Only those nine points, only that file; `tests/test_long_count.py` proves the exception is doing work and is
  that record.

## The builder's guards and tests

The build fails closed on: cell C3; authored clearance; corridor boxes; towns and Rift zones; path clearance for the
centre, NPC, Grotle and tin; Habitat Block leash overlap; tier ceiling; sub-region equal to the record's; any block
`data/spawn_blocks.json` names (an oak leaf is one, so the young trees' leaves are azalea leaves; no concrete); a block
outside `blocks.ids`; a sign naming a number the generator does not compute; the line off the tree by more than 2
degrees; a record (anchor, NPC feet, cache container and trigger, bbox) the heightmap disagrees with. Sign numbers
(`{years}`, `{line_paces}`, `{stakes}`, `{years_to_tree}`) are computed from the layout, never typed.
`tests/test_long_count.py` (41 tests) mutates a copy of the record for each guard, re-derives the stakes' bearing and
spacing from the emitted function, and checks the quest, rewards, progression fields, probes and `tools/reapply.py` wiring.
`world_probes.json` key `long_count` holds 20 presence probes (pole, fire, three trees, three stakes, the tin, three lane
gaps, the Grotle).

## Owed

- **The independent audit** (`tools/long_count_audit.py`, another agent) to `data/long_count.json` `audit_checklist`; then its
  prepare job after `long_count` in `tools/reapply.py`.
- **Apply on staging** (`prepare`, install, R9LC, R18LC, R9F with `cobblers_dialogue` loaded) and `presence_audit --only
  extra`: present / 20 total. Not run.
- **In game**: that the pole stands and its lantern shows from the road stretch above; that Perrin seats, the berry check
  fires and grants once; that the tin grants once; that the Grotle appears, wakes at 7 blocks, can be battled while
  NoAI is lifted and cannot be caught at one badge. Whether the 11-wide lane reads as a lane or as a clearcut is a look.
- **Findability beyond the pole**: nothing else points to it. A signpost or rumour line is a separate decision.
