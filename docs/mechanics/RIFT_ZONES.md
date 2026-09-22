# The Rift: zones, guards, wall and biome (design; built on staging only)

**Status: approved in structure 2026-09-21. Built on the staging export `cobblers-dryrun4` only, for a flyover (2026-09-22: `tools/rift_build.py` from `data/rift.json`, audited clean by `rift_build.py verify`); nothing in the live world, and no zone check, guard or spawn change is built.** The League move
it depends on is built on the staging export (`cobblers-dryrun4`, PR #37); everything below is a design with costs.

Sources: the Rift's axes, anchors and extent (`data/landmarks.json` `rift`), the League's site (`data/placements.json`
`league`), Victory Road (`data/routes.json` `victory_road`), Cobblemon 1.8.0's per-player data and NPC fields
(`docs/research/CAUGHT_COUNT_AND_NPC_GUARDS.md`), the location titles (`tools/location_titles.py`), and the proven
dialogue system (EXP-022, `tools/compile_dialogue.py`). Measurements are on the canonical heightmap (`tools/ground.py`).

## 1. The geometry

| Part | From | To | Length | Floor width (median) |
| --- | --- | --- | --- | --- |
| Trunk | apex (3660, 2400) | fork (4174, 3882) | 1,690 | 113 |
| West spur | trunk at (3598, 3294) | spur end (3022, 3254) | 590 | 78 |
| South-west arm | fork | tip (3738, 5082) | 1,424 | 85 |
| South-east arm | fork | tip (4390, 4894) | 1,124 | 80 |

**The two arms share their first 850 blocks.** The landmark's fork anchor is not where the floor divides: from
(4174, 3882) one trench runs south along x≈4200 to about **(4180, 4745)**, where it splits into the south-west arm
(to 3738, 5082) and a short south-east branch (to 4390, 4894), about 290 blocks long (heightmap, sampled every 40
blocks; the arms' lengths above are measured from the anchor, so both include the shared stem). Victory Road runs
the whole stem. So the south-east pocket is only the branch below the split, and its wall stands at the split, not
at the anchor: a wall at the anchor would cut Victory Road.

Floor y82-89, walls about 37 blocks deep at about 17 degrees, rim to rim 300-380 blocks, outline 8,245 blocks
round, rim y87-149 (median y121). **The walls are walkable**: at 17 degrees anyone can walk down into the Rift
anywhere, so the rim wall (section 5) is what makes the guarded walkways the only walkable entrances.

**The League** stands on the trunk's floor at its head, lot x3517-3636 z2591-2701, floor y85, about 250 blocks
down the trunk from the apex (the apex itself is too broken to seat it: y86-105, 46% flat). Victory Road enters at
the south-west arm's tip, runs up the arm to the fork and up the trunk to the League's forecourt (3576, 2762).
North of the League the trunk runs on 250 blocks to the apex at the Glacial Tear, over Hoopa's cradle
(`docs/HANDOVER_CODEX.md` item 22). The dig camp is on the west spur at (3106, 3314), 84 blocks from its end.

## 2. Zones and their guards

Four zones, one guard each. Every threshold is one number in data; the numbers and which pocket is which are
proposals for the owner.

| Zone | Area | Pass | Guard | Why |
| --- | --- | --- | --- | --- |
| **Z1 Dig camp** | the west spur, its end to the throat wall | **2 badges** | **G1** at the spur end (3022, 3254) | the early weak point: a young player's first taste of the Rift |
| **Z2 Victory Road** | the south-west arm, the shared stem, the trunk, the League's precinct, and Hoopa's cradle | **8 badges** | **G2** where Victory Road crosses the rim at the south-west tip (3738, 5082) | Victory Road, the finale and the League |
| **Z3 South-east branch** | the branch below the split, its mouth wall to its tip | **60 species caught** | **G3** at the branch's tip (4390, 4894) | a collectors' side pocket off the critical path; its Pokemon are the reward |
| **Z4 The apex** | the trunk north of the League to the Glacial Tear | **120 species caught** | **G4** in the wall behind the League | the deepest pocket, a postgame reward reached only through Z2 |

Three walls cross the floor inside the Rift, rim to rim, where two zones meet (section 5):

| Wall | Where | Walkway |
| --- | --- | --- |
| the throat | the west spur 200 blocks short of the trunk, (3384, 3502) to (3406, 3182) | none: the dig camp must not be a back door onto Victory Road |
| the branch mouth | across the south-east branch just below the split, (4373, 4691) to (4196, 4927) | none: Z3 is entered from its own tip. (A second guard here is the option if the owner wants Victory Road players to reach it without walking round.) |
| behind the League | east-west across the trunk at z2560, 31 blocks north of the lot (as built on staging; the first line, (3466, 2544) to (3768, 2629), came within a block of the League's north-east corner) | G4's walkway |

## 2a. Caught-count gates and Nuzlocke: optional content only

A Nuzlocke player catches about one Pokemon per route, 10 to 20 over the whole game, and never reaches 60 or 120
species. So **Z3 and Z4 hold nothing the story or the League needs**, and the design keeps them that way:

- **Hoopa's cradle and the final operation stand in Z2.** The finale is story-required: the dialogue sends the
  player "the trunk toward the head" to the cradle, and releasing Hoopa (`rift_crisis_resolved`) is what opens the
  League. The cradle must therefore be under the League's lot or on the trunk's floor south of the wall behind the
  League, never north of it (Z4) and never in the south-east branch (Z3). Codex places it
  (`docs/HANDOVER_CODEX.md` item 22, with this constraint).
- **What is in Z3 and Z4 now:** no settlement, quest site or dialogue location in the data. One stale record: Victory
  Road's ninth trainer, the "League Examiner" (`data/trainers.json` `route_09_trainer_09`), sits at (3598, 2575),
  north of the League, because its placement predates the re-route (it is at 4,623 blocks on a road now 4,340
  long; the eighth, at 4,408, is past the end too). Victory Road's trainers are re-placed on the new road, south of
  the League, before any wall is built (item 25).
- **A check when it is built:** the zone audit fails if any story-required site (a quest location, a mainline beat's
  actor, a gym or League trainer) lies inside a caught-count zone.

**Where the thresholds come from.** Distinct species a player can meet before each point of the critical path, from
`data/spawns.json` (the route rosters, plus the sub-regions whose level band is based on that route; evolutions are
counted in the second column because `caught_count` counts every species owned, and an evolution is assumed to add
one, not yet tested):

| Before | Catchable, cumulative | With their evolutions | A normal player at about half |
| --- | --- | --- | --- |
| gym 3 | 38 | 73 | 37 |
| gym 4 | 54 | 101 | 50 |
| gym 5 | 68 | 120 | 60 |
| gym 6 | 81 | 135 | 67 |
| gym 7 | 102 | 160 | 80 |
| gym 8 | 127 | 188 | 94 |
| the League | 160 | 223 | 111 |

(300 species are catchable anywhere, 140 of them only in wilderness sub-regions off the routes.) "About half" is an
assumption, not a measurement: a player who catches one of each family they meet and evolves what they use.

**Proposed: Z3 at 60 species**, which a normal player reaches around the fifth gym, so the south-east branch is a
mid-game reward for collecting; **Z4 at 120**, which a normal player reaches just after the League, so the apex is
postgame. Both remain single numbers in data, and both stay off the critical path whatever they are set to.

## 3. What Cobblemon 1.8.0 exposes for caught count

From `docs/research/CAUGHT_COUNT_AND_NPC_GUARDS.md`, read in the Cobblemon 1.8.0 source; **none of it is run in game
yet**:

- **Species owned**: `q.player.pokedex.caught_count` (`PokedexMoLangFunctions.kt`, VERIFIED key) counts species
  whose Pokedex entry is `OWNED`: starters, trades, gifts and eggs as well as ball captures. The call form is ASSUMED.
- **Ball captures**: the stat `cobblemon:captured` (`q.player.get_custom_stat('cobblemon:captured')`, VERIFIED) and
  the advancement trigger `cobblemon:catch_pokemon` `{"count": N}`, compared with the running capture total and
  checked only when a capture happens (VERIFIED). No condition for "N of species X" exists.
- **Advancements**: `q.player.has_advancement('<id>')` (VERIFIED).
- **Recommended**: G3 and G4 read `caught_count` when the player talks. It reads the stored Pokedex, so catches made
  before the gate existed count and nothing ticks in the background.

To prove before a caught gate is built: which acquisitions move `caught_count` (a new species, a duplicate, a trade,
an evolution); the call form; and that the dialogue sees the same number `/runmolang` does.

**Badges**: G1 and G2 read the gym flags (`gymN_cleared`, `data/progression.json`): one advancement per leader,
`cobblers:flag/gymN_cleared`, set by rctmod when the player wins that leader's battle (`tools/progression_pack.py`,
EXP-027). A guard reads it with `q.player.has_advancement('cobblers:flag/gym8_cleared')` (in the 1.8.0 source,
not yet run from dialogue) and counts badges by summing the eight.

## 4. The zone check, behind every guard

The guard is where a player earns passage; the zone check enforces it for anyone who flies over, digs under or
pearls past. They meet in one per-player record: **a pass score per zone** (`cob_pass_z1` .. `cob_pass_z4`), set by
the guard's dialogue when the player qualifies, read by the zone check. It never unsets.

- **Earn**: the dialogue checks the flags or `caught_count`; if the player qualifies it runs, as the server
  (`q.run_command`, proven in EXP-022), `scoreboard players set <uuid> cob_pass_<z> 1` and the teleport (section 6).
- **Enforce**: per zone, the location-title mechanism reused: a hidden advancement `in_zone_<z>` whose
  `minecraft:location` condition is the overworld inside the zone's boxes (its polygon rasterised by
  `tools/subregion_boxes.py`, full height y-64 to y575) **and** `minecraft:entity_scores` `cob_pass_<z>` below 1.
  Its reward function turns the player back and revokes the advancement, so it is tested again a second later.
- **Turned back**: teleported to the zone's turn-back point, in front of its guard facing away, with the guard's
  turn-back line (`tellraw` in the guard's name and colour, a short `title` subtitle) and a sound. The zone check
  speaks only in the guard's voice.
- **Leaving**: each walkway has an exit box on its inner side, the same kind of hidden advancement with no score
  condition: stepping into it sends the player out to the front of the guard with the guard's farewell line.
  Waystones also work.

| Case | How |
| --- | --- |
| walking, flying, digging, ender pearls, chorus fruit | every route ends with the player inside the boxes; the test fires within a second of arrival |
| riding a flying Pokemon | the reward teleports the mount first (`execute on vehicle run tp @s <point>`), then the player, then remounts them (`ride <player> mount <mount>`, vanilla since 1.19.4). **To prove**: that Cobblemon's riding accepts `/ride`; if not, the mount lands beside the player |
| logging in inside | the location test runs within a second of login |
| respawning inside | the same; and a bed or respawn anchor inside a zone is removed as the player is turned back, so it cannot loop |
| a waystone inside a zone | the same test: a teleport is one more route in |
| multiplayer | advancements and scores are per player; each is judged on their own pass. A qualified player cannot bring an unqualified one through: G's teleport moves only the player who talked |

Cost: for players without the pass, one location test per zone per second against a few hundred boxes (the 32-block
grid the titles use). Negligible for a small group.

## 5. The wall: the look, and the closure

Obsidian, crying obsidian and blackstone rising from the rim, the portal look climbing into the sky, visibly
broken at the four guard sites. No `nether_portal` block anywhere (they teleport players). Blocks: obsidian, crying
obsidian, blackstone, gilded blackstone, purple and magenta stained glass and panes, tinted glass. None is named by a
spawn condition in `data/spawn_blocks.json` (amethyst and purple concrete are, and are not used); every block goes
through the spawn-block policy check like any template. Obsidian also cannot be moved by pistons.

| Part | Height | Blocks |
| --- | --- | --- |
| rim wall, 2 thick, round the whole outline | 16 above the rim | 264,000 |
| spires, 3x3, every 32 blocks along the rim (257) | to y320, the top third purple glass | 452,000 |
| the throat wall, 2 thick, rim to rim across 322 blocks | floor y86 to y136 (rim y120 + 16) | 24,000 |
| the branch mouth wall, 296 across | floor y88 to y141 (rim y125 + 16) | 23,000 |
| the wall behind the League, 314 across | floor y85 to y136 (rim y120 + 16) | 24,000 |
| four gatehouses (section 6), about 9 x 7 x 8 each | | 2,000 |
| **Total** | | **about 789,000** |

Options measured for the rim wall alone: continuous 24 high, 1 thick 198,000; 48 high, 2 thick 792,000; 96 high,
2 thick 1,583,000; spires every 48 to y400 instead of every 32 to y320 saves 28,000. **Recommendation: the 16-high
wall with spires to y320.** Sixteen blocks cannot be walked or jumped, so the wall closes the rim; what reads as
"reaching the sky" is height, and height is cheap in spires. Spires lean and taper at random so they read as grown,
and Distant Horizons shows them across the map. At each guard site the wall drops to rubble either side of the
gatehouse and the spires stop, which is how a player reads "this is the way in". Built as generated fill functions,
like the cavern.

## 6. The guards

At each guard site the only walkable way in is a one-wide walkway through a gatehouse in the wall, and a Cobblemon
NPC stands in it.

```
section along the walkway, outside on the left      plan
  y+2   O O O O O O O O     roof over the guard      O O O O O O O O
  y+1   . . . G B . . .                              . . . G B . x .
  y     . . . G B . . .                              O O O O O O O O
  y-1   O O O O O O O O     floor
  G  the guard (Cobblemon NPC, 0.6 x 1.8)   B  barrier, 2 high, directly behind the guard
  O  obsidian   x  the exit box   the passed player arrives 3 blocks in, facing in
```

- **It blocks everyone physically.** The walkway is one wide between obsidian, roofed at y+2 so nothing jumps over
  the guard, and closed by a two-high barrier column directly behind the guard. The barrier is what actually stops a
  player; it is invisible and unbreakable in survival, so the guard reads as what blocks the way.
- **Talking is passing.** A shared entity cannot step aside for one player, so a qualified player talks to the guard
  and the dialogue sets their pass and sends them through with
  `q.run_command('execute as ' + q.player.uuid + ' run tp @s X Y Z yaw 0')`: exact, where `q.player.teleport` uses
  `randomTeleport` and may adjust the spot. An unqualified player is told what they lack, with the numbers.
- **Can the guard be pushed, damaged or jumped?** From the 1.8.0 source (VERIFIED unless marked):
  - *Pushed*: `isPushable()` returns the class's `isMovable`, which our class sets `false`. Pistons ignore that
    (ASSUMED: `getPistonPushReaction` is not overridden), but a piston can only stand in front of the guard, and it
    pushes the guard into the barrier, where it cannot go; the sides and roof are obsidian, which a piston cannot
    move.
  - *Damaged*: `isInvulnerableTo` honours the class's `isInvulnerable`, which our class sets `true`: everything but
    `/kill` and the void. Our class also sets `allowProjectileHits: false`, `isLeashable: false` and
    `canDespawn: false`, and has no wander behaviour.
  - *Jumped*: the roof makes it impossible regardless. The NPC has no solid collision box (`canBeCollidedWith` is
    not overridden, ASSUMED false from vanilla), so it cannot be stood on, and could be squeezed past, which is why
    the barrier stands behind it and the design does not depend on the NPC's own collision.
- **The zone check sits behind every guard** (section 4) and turns back, in the guard's voice, anyone who went over,
  under or round.
- **To prove before building** (one experiment on a disposable world): the guard can be talked to from the front with
  the barrier behind it; walk, sprint, sprint-jump, crouch, a piston, an ender pearl and a ridden flying Pokemon do
  not get an unqualified player through; the dialogue's teleport lands exactly.

**Guards for Codex to write** (`docs/HANDOVER_CODEX.md` item 23): who each is and why they stand there; a greeting;
a pass line; a refusal for each thing a player can lack (badges short by N, species short by N); a turn-back line
for the zone check; and a farewell for the exit box. Claude writes no dialogue.

| Guard | Site | Checks |
| --- | --- | --- |
| G1 | the west spur's end, before the dig camp | 2 badges |
| G2 | Victory Road's gate at the south-west tip | 8 badges |
| G3 | the south-east branch's tip | 60 species caught |
| G4 | the wall behind the League, before the apex | 120 species caught |

## 7. The Rift biome

A custom biome, `cobblers:the_rift`, painted with `/fillbiome` over the Rift's extent from the floor to the sky.

| Wanted | Possible in a vanilla biome definition | How |
| --- | --- | --- |
| portal particles | yes | `effects.particle`: `minecraft:portal`, probability about 0.02 |
| fog colour | yes | `effects.fog_color`, `sky_color`, `water_fog_color`: violet-grey |
| **heavy fog** | **no** | fog distance is the client's; a datapack biome sets its colour, not its density. Needs a client mod or a shader; not proposed |
| light from below | not from the biome | from blocks: crying obsidian (light 10) scattered in the floor and the wall's base |
| mood sounds | yes | `effects.ambient_sound` / `mood_sound` |

**What the biome does to spawns, and why it cannot go in alone.** Every Rift entry in the compiled pools carries
`"biomes": ["minecraft:windswept_gravelly_hills"]` (the Victory Road and `rift_trunk` pools in
`build/datapacks/cobblers_spawns`). Repainted, every one of them stops matching and the Rift spawns nothing we
authored; Cobbleverse's inherited pools key on biome tags (`#cobblemon:is_hills` and the like) and would stop too.
So the biome ships with:

- `cobblers:the_rift` added to every `data/spawns.json` entry scoped to the Rift's sub-regions and Victory Road's
  corridor, and recompiled;
- the biome added to the tags the gravelly hills are in, through the tag pack (`tools/spawn_tag_pack.py`);
- a check that fails if any Rift-scoped entry does not name it.

Cost: `/fillbiome` over about 2.2 km² and y64-y320 (4x4x4 cells), split under its volume limit into generated
functions: a new re-export step after the cavern's own `60_biome`, re-run on every re-export.

## 8. Build order, once approved

1. the caught-count experiments (section 3) and the guard experiment (section 6);
2. the badge flags (section 3), or the caught gates alone first;
3. the biome with its spawn and tag changes and its check;
4. the zone check and passes, with a fail-closed audit: every zone has boxes, a turn-back point and an exit box;
   every guard has a dialogue that grants its zone's pass; the expected counts come from this design's data, not
   from what was placed;
5. the wall, spires and cross-walls, then the gatehouses and guards;
6. staging rehearsal, audit, and a flight.
