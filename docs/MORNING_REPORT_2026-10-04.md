# Morning report, 2026-10-04 (the overnight build)

Everything below is in **staging-2026-10-01** and was read back from the world after a restart, unless it is marked
otherwise. "Read back" means block and entity probes over RCON. None of it has been seen in game by a player.
- **Snapshot before the night:** `C:/Users/wnd/Documents/cobblers-staging/snapshot-2026-10-04-before-night`.
- **World checks after the restart:**
  - `install_check`: 0 problems.
  - `presence_audit`: 273 of 282. The 9 absent are the same 9 known stale or open probes as before.
  - `npc_seats verify`: 20 of 20.
  - `reapply.py stale`: 0 steps changed, 0 never run.

## 1. Giovanni: waiting for you

1. Join staging.
2. Optional: give yourself a level-55 team (Gyarados, Venusaur, Starmie, Weavile, Breloom, Garchomp) with
   `/function cobblers_test:giovanni_team`.
3. Run `/function cobblers_test:giovanni_ready`. It records every leader up to Blaine as beaten in rctmod and puts you
   at **(3564, 121, 6416)**, beside his spawner at (3565, 120, 6416). Feet and head are clear and the floor is solid
   (checked).
4. He spawns when you come near. A party at level 55 or under is accepted.
5. After the win, check the Earth Badge, the level cap moving to 60, and the first-win items.
6. If his lead is around level 68-70, the override failed and his stock team is fighting.

`cobblers_test` is a staging-only pack installed by hand. The repository does not build it.

## 2. What is in the world, with coordinates

| What | Where | Read back |
|---|---|---|
| Compact HQ tower: eleven storeys, seven fights, caches; Brann, Elara and Oren inside; the release at `cradle_open` sets `rift_crisis_resolved` | box x3428-3438, z3303-3313, y67-132; door (3438, 67-69, 3306), reached through the ring-0 guard (3443, 67, 3282); Brann (3431, 74, 3305), Elara (3433, 122, 3309), Oren (3433, 128, 3307) | 40 of 40 sampled block writes; door open; all three NPCs present |
| Mega field: 27 dens in 8 farms, each den with its own id, overlapping ranges; borders with scarred ground, broken rock and kills | the southern Rift; den list in data/gulch_mine.json `mega_field.farms` | dens 30 of 30, borders 40 of 40 sampled writes |
| Sea floor: kelp forests and seagrass meadows on every marine shelf | all marine regions | 28 of 30 sampled (the two misses are kelp that has grown since) |
| The far south's five places | Kraal Number Three (2808, 5760); the Four Chimneys (5176, 5968); the Glass Garden (5976, 6544); the Watcher's Ring (7056, 6200); the Lady's Folly (2904, 7632) | 40 of 40 sampled writes |
| Town squares, rebuilt as Slateport-style tents | Pallet (1474, 5271), Stoneford (1740, 3609), Viltri Quay (1633, 2807), Highwire (1689, 1397), Greenhollow (4320, 1538), Fenhide (4668, 2434), Tilpey Cross (6206, 3388), Cinderlee (6081, 5004), Holdfast (3602, 6456), Sunset West (2652, 6494), Pacifidlog (5158, 7375), Steepside (2618, 3583) | 40 of 40 sampled writes |
| Stall keepers as Cobbleverse merchants, each with its own shop | at each tent | 31 of 31 merchants; the 12 badge-gated counters stay dialogue clerks, 12 of 12 |
| 281 idle Pokemon in 16 towns (sitters, loafers, sleepers that wake at 16 blocks, followers) | the towns | every idler present once; the AI kinds have AI on |
| Buneary round the snow house | (6950, 1360) | 9 Buneary within 40 blocks |
| Brock's spawner lowered to the hall floor | Stoneford gym (1832, 155, 3696) | all seven gym spawners are spawners at their data height |
| Wrong-country spawns fixed in the design (Crabominable and others) | compiled spawn pack | audit: 0 misfits, 0 known; the pack is installed and current |
| Victory Road's last third reachable (zones admit on entry) | z5 | in data and tests; not walked in game |

## 3. Recorded and not chased

`docs/REVIEW_2026-10-02.md` items 53-72. Tonight's are 64-72:

- **64. Megas on the road.** The north stem and the south-west lobe hold no den: the 128-block rule from Victory Road
  leaves no room. 18.4% of the field is covered now; about 21% is the ceiling under that rule.
- **65. Far-south levels.** Three residents fight at levels 56-58, above the gym-7 cap of 55.
- **66. Sea floor.**
  - The kelp and seagrass policy entry waits for your confirmation.
  - Coral reefs and river beds are not built (docs/world-building/WATER_LIFE_GAP.md).
- **67-68. Critical-path walks** (docs/world-building/CRITICAL_PATH_WALK_1.md and `_2.md`).
  - The starter screen is unproven.
  - Co-op second-player state is unproven.
  - No gym interior has been walked.
  - The finale's chain of conversations has not been played.
  - Victory Road's z5 blocker is fixed.
- **69. Obtainability.** In a pre-generated world with no Nether, these have no route:
  - type gems, which gate every TMCraft TM;
  - Dynamax;
  - the Tera Orb (Nether glowstone);
  - the Red Orb;
  - Silvally's memories;
  - 14 of 15 fossils;
  - mints;
  - blaze rods, so no brewing;
  - Link Cable quartz.

  Two more:
  - The Z-ring is capped at two per server.
  - The mob blacklist removes passive animals.
- **70. Badge counters.** They stay dialogue clerks, the default taken.
- **71. Two audits I edited as the integrator.** I changed `deep_walk_audit` and `hq_tower_audit`; another reader should
  check them.
- **72. A tower reporting STOPPED.** `deep_walk_audit` reports tower (3544, 3241) as STOPPED, yet its check is clean.

Also new tonight: the idle Pokemon verify read an absent `NoAI` (AI on) as a failure, which produced 76 false problems.
It is fixed in bda1fbb.

## 4. Blocked on you

1. **The Nether question**, and with it most of item 69.
2. **"The three extra starters".** The config and data offer five. What does the screen show you?
3. **Z2's gate.** The 1,316-block distance is not reproduced (review 44).
4. **Megas on the road** (64).
5. **Far-south levels** (65): lower them, or gate the places after gym 7?
6. **Kelp and seagrass** as spawn-condition blocks (66).
7. **NPC skins route** (review 60).
8. **Heaven's Arena** `decisions_pending`. Defaults are taken.
9. **Frostpeak heart** (53-54): none of the seven heart species spawned in either sample, above or below the y180
   line.
10. **The Pidgey swarm** at the Route 1 sapling (61).
11. **HQ loss.** Should a loss inside the HQ count as a blackout?
12. **Shrew Station.** It is now 2,777 blocks from the Zapdos it studies. Should it move too?
