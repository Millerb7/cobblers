# EXP-034: the scene runtime: per-player actors, props, zones and effects; the Gastly escort; the Route 1-3 events

## Objective
Every mainline beat needs more than dialogue: things in the world a player clicks, Pokemon that stand where that
player's progress says, rooms that notice where the player is, and effects only that player sees. The scene runtime
(`tools/scenes_pack.py`, `data/scenes.json`) is that layer, built on the dialogue runtime EXP-022 proved. This
experiment tests it on the Gastly mansion (the hardest case: five checkpoints, three per-player actors, a per-player
barrier) and on the eight Route 1-3 events, and tests the thirteen route trainers built as Radical Cobblemon
Trainers data (`tools/route_trainers.py`).

If per-player actors fail (a player's actor is lost, doubled, or moved by another player), the escort needs a
different actor mechanism before any mainline beat is built on it.

## Success criteria
1. **Checkpoint restore.** Pip stands where the player's saved checkpoint says, after walking out of the area and
   back, after a disconnect, and after a server restart.
2. **Movement on the click.** Each checkpoint transition moves Pip within the same click (sync_scene), with a puff of
   smoke at both ends; nothing else in the house moves.
3. **Per-player.** With two players: each has their own Pip, Haunter and Gengar at their own checkpoints; clicking the
   other's says it is not yours and opens nothing; one player's wards, candles, cup and barrier never change the
   other's. (Needs a second account.)
4. **Per-player effects.** The ballroom barrier (soul-fire curtain) and its push-back apply only while that player's
   ward is up; the Litwick lights run only while that player is at the candles.
5. **Rewards once.** The Spell Tag and the Dusk Balls, the picnic, First Cast, Geodude, sounding, north bank,
   Nosepass, Wooper and Swablu rewards each arrive once per player and never again; a full inventory keeps the claim
   open (EXP-022's retry).
6. **Ghost house.** Inside the mansion `/checkspawn common` lists only the `route_1_ghost_mansion` pool; in the forest
   past the clearing it does not.
7. **Trainers.** Each of the thirteen stands at its seat; each battle starts; a win writes `quest.<id>.defeated` for the
   winner only (and the North Bank Angler's also writes `quest.evt_viltri_north_bank.trainer_defeated`); a loss writes
   nothing; talking after a win gives the win line and no second battle; the Trail Novice starts a battle on sight;
   no trainer drops an item.
8. **Finds.** The four route caches grant once each, on reaching them.

## Setup
Staging world `cobblers-runtime-proof/dryrun9/cobblers-dryrun9` (never the live world), Minecraft 1.21.1, Fabric
Loader 0.19.5, Cobblemon 1.8.0+1.21.1, rctmod 0.19.0-beta, rctapi 0.16.0-beta, the full server stack. Built with
`tools/reapply.py prepare`, then the Route 1-3 steps: R6 (forest), R7 (hometown), R8/R9/R16 for the mansion and the
towns of gyms 1-3 only (R8 over every place would re-level ground under the League lot the Rift steps built), R15,
R12 (the event sites), R9E (Habitat Blocks), a restart, and R17 (props, NPCs, trainers).

`cobblers_scenes`, `cobblers_trainers` and `cobblers_route_events` are installed in the **staging world's own
datapacks folder**, not the server-global one: the scene runtime has a tick function, and the global folder is also
loaded by the live world.

## Runtime facts established before the build (headless, 2026-09-24)
| Question | Probe | Result |
| --- | --- | --- |
| A Pokemon that cannot be caught, battled or hurt, and does not move | `spawnpokemonat ... gastly uncatchable no_ai`, then `data merge entity ... {Unbattleable:1b,Invulnerable:1b,Tags:[...]}` | NoAI 1b from the property; Unbattleable, Invulnerable and tags held (read back) |
| `/summon cobblemon:pokemon {Pokemon:{...}}` | direct summon with NBT | "Unable to summon entity": spawn by command, then adopt |
| Commands a function may run | a probe pack with `runmolang`, `opendialogue`, `spawnpokemonat`, `rctmod trainer summon_persistent` | all four load and run inside a function; `q.run_command` from `runmolang` ran |
| Do those functions parse at **boot**? | boot with the real packs | yes: no load error for any scene, trainer or event-site function (the one failure was an unregistered furniture block, since replaced) |
| rctmod trainer entity | `summon rctmod:trainer` | the type exists and cannot be summoned directly: placement is `rctmod trainer summon_persistent <id> <x> <y> <z>` |
| rctapi trainer keys | constant pool of `TrainerModel` in rctapi 0.16 | name, ai, bag, team, battleTheme; AI keys moveBias, switchBias, statusMoveBias, itemBias, maxSelectMargin |

## What is standing on staging (checked 2026-09-24, the server running, nobody on it)
- The mansion: `town_audit route1_mansion` clean (6,346 of 6,346 blocks, plan clean). The ward stone at
  (1629, 120, 5033) resolved its pool after a restart: `DisplaySpecies` lists the 11 `route_1_ghost_mansion` species.
  `habitat_blocks.py verify --rcon`: 81 of 81 blocks, 0 problems.
- The event sites: `route_events.py --verify-world`: 2,237 of 2,237 planned blocks, no tree left in a clearing.
- Props, NPCs, trainers (R17): 41 of 41 props in 9 scenes, 8 NPCs, 13 trainers, one at each place.
- Brock's, Misty's and Surge's towns clean; the Route 1 forest 46,007 of 46,015 trunks (the eight missing are inside
  the mansion's footprint and under the forest's own lantern posts: the audit's allowance).
- Not seen: any actor (they need a player in the area), any click, any battle.

## Procedure (the owner, in game)
Survival, a starter team around level 15-25 for the trainers. Teleports use feet coordinates.

**A. The mansion** (`/tp @s 1628 115 5046`, outside the front door)
1. Walk in. Behind the grand stair a Gastly named Pip should be waiting (and Haunter pacing in the ballroom upstairs,
   Gengar behind a shimmer at its east end). Click Pip: accept.
2. Choose the worn middle of the runner. Pip should vanish in a puff and reappear at the foot of the stair.
3. Leave the house past the clearing's edge (about 25 blocks) and come back: Pip should be at the stair again.
   Disconnect, reconnect: the same.
4. Dining room: click the blue cup, take it, walk through the rear door into the corridor: Pip must not follow.
   Put the cup back, walk into the corridor again: Pip appears by the library door.
5. Click Pip (three notes). In the library, try the west aisle (a scare, nothing changes), then the middle one.
6. Upstairs, watch the candle stands: blue flames light over three of them in turn. Touch them in that order (a wrong
   one puts them out). Pip moves to the ballroom's bent bars.
7. Walk toward Gengar's end of the ballroom: the shimmer should push you back. Touch the three ward marks along the
   inlaid path from the hearth; the shimmer goes, Gengar comes out. Click Pip: the reunion, then a Spell Tag.
8. Pip, Haunter and Gengar move to the north-west bedroom. The loose board behind the stair gives three Dusk Balls.
   Neither reward comes a second time.
9. `/checkspawn common` in the foyer and the ballroom: only the ghost pool. In the forest past the clearing: not it.
10. Restart the server while standing in the house and rejoin: the family is in the bedroom.

**B. Route 1** (from Pallet north)
- The Trail Novice (`/tp @s 1465 120 5025`): walk into view; the battle should start on sight.
- The mansion junction sign (`/tp @s 1469 119 5041`).
- The picnic (`/tp @s 1448 123 4833`): the picnicker, crumbs (green specks) toward the hollow log, the lunch, back,
  then a berry at the stump (hold any berry). A Rattata should sit by the stump afterwards.
- The Meadow Apiarist (`/tp @s 1384 126 4714`), the thirsty stranger's hut (`/tp @s 1514 123 4462`), the Vale
  Naturalist (`/tp @s 1586 123 4292`), the Plateau Guide (`/tp @s 1599 124 3867`).
- First Cast (`/tp @s 1060 65 5349`): the fisher gives one fishing rod, once.
- Finds: the fern glade (`/tp @s 1602 118 4938`), the west hollow (`/tp @s 1258 127 4798`), the north ring
  (`/tp @s 1662 120 4378`): standing by each barrel grants its contents once.

**C. Route 2**
- The Geodude (`/tp @s 1750 139 3528`): the miner, the rut, the sack, the boulder, the brake at the cart; Geodude
  moves to the miner. Ravine Scrapper (`/tp @s 1767 134 3371`), Glowbug Keeper (`/tp @s 1778 132 3159`).
- The sounding (`/tp @s 1771 113 3010`): the keeper; down the path to the platform; the staffs shallow, middle,
  deep (a wrong one first gives the Lotad hint); the gauge; back to the keeper.
- The north bank (`/tp @s 1604 106 3066`): the tackle box, then beat the North Bank Angler; the tackle box again
  gives one Lure Ball. Lose once first: nothing should change.
- Lake Surveyor (`/tp @s 1779 112 2925`).

**D. Route 3**
- Climbing Novice (`/tp @s 1752 105 2614`), Grove Ranger (`/tp @s 1881 114 2307`), Groundkeeper
  (`/tp @s 2039 125 1951`), the world tree's roots find (`/tp @s 1991 116 2276`).
- The Nosepass stop (`/tp @s 2186 125 1608`): the keeper; wedge signs A and B; watch the mast (a flash north-west,
  high over the trees, a sound, Nosepass turns); sign C; back. The Signal Watcher stands on the road there.
- The Wooper shore (`/tp @s 2190 121 1622`): the courier; the three approaches (only the dry stones work); the crate;
  back; stay with the Wooper: one wild Wooper appears by the muddy pool, once.
- The Swablu nest (`/tp @s 2014 133 1604`): the guide; three fiber piles; the nest twice; back. The Vessu Ranger
  at the bench (`/tp @s 1982 134 1602`).

After each trainer win, `/runmolang "q.player.data().cobblers__quest__<id>__defeated" @s` should read 1.

## Result
Pending the owner's run.
