# Morning report, 2026-10-12

Staging is up for you: **20G** (12G no longer fits, below), terminal tab "staging server 20G", installed from prepare 236/236 at 09ff917 (branch
`build/2026-10-12-overnight`, local, no PR yet). Snapshot before the install, verified file by file:
`D:\cobblers-snapshots\staging-2026-10-12-before-overnight-install`. Nothing below has been seen in game.

## In the world now (applied and read back)

| What | Read back |
|---|---|
| Dungeons: the vault rework (themed unsold balls, weighted held items, budget doubled), the bait rework (71 baits, every berry, separate shiny and alpha rolls), the Rift Guide book on your first rift arrival | shells written; shell entities 156 of 156 |
| Themed ground under the 13 rips | rips 13 of 13 |
| The Rift gatehouses rebuilt: open 6-wide passage, guard beside it, the zone's line turns you back; the obsidian corridor and its 2-high roof restored to terrain | 6 of 6 guards |
| Seven new legendary chambers: Tornadus (Tri Peaks summit, gym 4, L40), Thundurus (Mt Vessu's SE shoulder, gym 5, L45), Landorus (Mt Clay, gym 6, L50), Enamorus (the Tri Peaks col, gym 7 after meeting the three, L55), Tapu Koko (Sunset West, gym 5, L45), Tapu Lele (Sunset East, gym 7, L55), Tapu Bulu (Long Isle south hill, gym 6, L50: the Jungle Isle is drowned) | all 15 chambers' legendaries 1 of 1 (the 8 old ones untouched) |
| Six caves (the new cave kit): K1 Stoneford Cut (Gible, open), K2 Singing Hollow by Viltri (Meloetta, door at gym 6, L50), K3 Relay Fault (Miraidon alpha boss after the Champion), K4 Strait Grotto (Tapu Fini and Nihilego, gym 8, L60), K5 Clock Cellar near Tilpey Cross (Dialga alpha boss after the Champion), K6 Sunscar in the east dunes (Koraidon alpha boss after the Champion) | built (R9CK), Habitat Blocks written (R9E) |
| Six shrines in Route 1's maze-forest glades: Mesprit, Azelf, Uxie steles (true hints, a berry or Potion find each); the Bulu, Celebi ("Not yet.") and Tornadus old shrines in the secret glades | applied (R12MS) |
| Five fishermen giving rods once each: Great (Viltri, gym 1), Net (river off Route 4, gym 3), Ultra (Peak Pond, gym 4), Lure (Northlight beach, gym 5), Dive (Sunset West harbour, gym 7) | seated (R17N) |
| Rare wild spawns: Buzzwole and Pheromosa on the Long Isle south (ultra-rare, L55, catchable after gym 7; need the AllTheMons pack) | installed with the spawn pools |
| Spawn fixes: overworld pools no longer spawn in the dungeon dimension or the Nether; the five uncatchable inherited spawns (Meloetta, Tapu Fini, Nihilego, Buzzwole, Pheromosa) switched off | installed |

## What happened on the way (all fixed)
- Prepare caught three integration faults: the Nuzlocke zones went stale after the caves; the caves' own Habitat
  Blocks counted as "another pack's writes" in both the cave builder and its audit (fixed independently in each).
- **12G no longer fits this build, even idle.** Measured after a forced GC with nobody online: a 12.4 GB live set.
  Three 12G boots ran out of memory (two under the shells' entity chain, one idle within the hour); each was my own
  server, killed after its save was checked (0 bad chunks; the last one had written nothing since the apply). Staging
  now runs at 20G (8 GB of room) and applies at 24G. What grew the heap is not measured yet. The LIVE server will need
  the same when it gets this build.
- The full dungeon independent audit: 0 findings on all of tonight's dungeon work.

## Decisions waiting on you
1. **Heatran and Yveltal:** the dungeon engine has no legendary boss stage, so they are not placed. Option: the
   roster's fallback, a band-6 prize in the Crucible and the Patriarch. Or a boss-stage engine (a build).
2. **The paradoxes** are placed in built dungeons' prize pools (one per dungeon, by theme), merged on the branch
   AFTER the install: not in the world yet.
3. **Defaults I took for "every mon placed":** Koraidon and Miraidon as post-Champion bosses; Dialga out of the
   Temple Calendar into K5; Tapu Fini and Nihilego as repeatable chamber spawns. Gates on the seven chambers are
   marked "proposed". Tapu Bulu's new site (Long Isle south) is mine: please look.
4. **Still unplaced, by your earlier decisions:** Eternatus (out), Lugia (blocked); Kyogre and Rayquaza (their own
   designed cave, KYOGRE_CAVE.md, a large build).
5. **The world tree:** `docs/world-building/WORLD_TREE_PLAN.md`: recommendation B (a climbable hamlet on the lower
   storeys) then C (Xerneas in the crown behind a Champion door); nothing gates flight today, so a fly-only city is
   not a real gate yet. Seven questions at the end.
6. **Contract C4** still forbids spawn-condition blocks your 2026-10-05 decision allowed (the dungeon rooms use them).
7. **The gulch gate** (an iron grille in a rock plug) was left alone; say if you meant it too.

## Where to look (coordinates)
- Gatehouses: z1 (3100, 88, 3267), z2 (3545, 112, 5322).
- Caves: K1 mouth (1535, 128, 3628); K2 (1501, 104, 2825).
- Chambers: Tornadus (1850, 287, 1350); Tapu Bulu (7508, 143, 7662).
- Shrines: Mesprit stele (1465, 121, 4890); Celebi's old shrine (1260, 127, 4805).
- Fishermen: Wick Doran (1632, 104, 2895).
