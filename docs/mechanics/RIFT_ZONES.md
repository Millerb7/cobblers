# The Rift: zones, gates, wall and biome (design, not built)

**Status: proposed 2026-09-21, for the owner's review. Nothing here is built.** The League move it depends on is
built on the staging export (`cobblers-dryrun4`); everything below is a design with costs.

Sources: the Rift's axes and extent (`data/landmarks.json` `rift`), its sub-regions (`data/regions.json`), the
League's new site (`data/placements.json` `league`), Cobblemon 1.8.0's per-player data
(`docs/research/CAUGHT_COUNT_AND_NPC_GUARDS.md`), the location titles (`tools/location_titles.py`), and the
proven dialogue system (EXP-022, `tools/compile_dialogue.py`). Measurements are on the canonical heightmap.

## 1. The geometry

| Part | From | To | Length | Floor width (median) |
| --- | --- | --- | --- | --- |
| Trunk | apex (3686, 2442) | fork (4174, 3882) | 1,690 | 113 |
| West spur | trunk at (3598, 3294) | spur end (3022, 3254) | 590 | 78 |
| South-west arm | fork | tip (3738, 5082) | 1,424 | 85 |
| South-east arm | fork | tip (4390, 4894) | 1,124 | 80 |

Floor y82-89, walls about 37 blocks deep, outline 8,245 blocks round, rim y87-149 (median y121). The League stands
on the trunk's floor 250 blocks below the apex. Victory Road enters at the south-west arm's tip (3738, 5082), runs up
the arm to the fork and up the trunk to the League. The dig camp is on the west spur at (3106, 3314), 84 blocks
from its end; Brock's and Misty's towns are 1,400-1,600 blocks west of it.

## 2. Zones and their gates

| Zone | Area | Gate | Why | Weak point |
| --- | --- | --- | --- | --- |
| **Z1 West Spur (dig camp)** | the west spur from its end to 200 blocks short of the trunk | **2 badges** | the early weak point: the first place a young player gets into the Rift, a taste of it | the spur end (3022, 3254): the wall broken down to rubble for 40 blocks, one walkway, one guard |
| **Z2 The spur's throat** | the last 200 blocks of the spur, to the trunk | **8 badges** | the spur must not be a back door onto Victory Road | none: the wall is full height across the throat, no walkway |
| **Z3 South-west arm** | the arm, tip to fork | **8 badges** | Victory Road's own entry | the arm's tip (3738, 5082): the Victory Road gate, one walkway, one guard |
| **Z4 Fork and trunk** | the fork and the trunk up to the League's forecourt | **8 badges** | Victory Road | inside Z3's gate: no separate guard |
| **Z5 League precinct** | the League's lot, forecourt, approach | **8 badges** | the League | inside Z3's gate |
| **Z6 South-east arm** | the arm, fork to tip | **caught 60 species** | a side pocket for collectors, not on the critical path; its Pokemon are the reward | the arm's tip (4390, 4894): the wall thinned, one walkway, one guard |
| **Z7 The apex** | the trunk head beyond the League to the Glacial Tear | **caught 120 species** | the deepest pocket, past the League, over Hoopa's cradle (Codex item 22) | none from outside: reached only through Z4/Z5, a guard on the trunk behind the League |

The badge counts, the two caught thresholds (60 and 120) and which zone is which pocket are proposals for the
owner. Every threshold is one number in data.

## 3. Can caught-count gates exist? Yes, without a mod

From `docs/research/CAUGHT_COUNT_AND_NPC_GUARDS.md` (Cobblemon 1.8.0 source, not yet tested in game):

- **Species caught**: the Molang query `q.player.pokedex.caught_count` counts distinct species the player owns
  (starters, trades, gifts and eggs included, not only ball captures). Readable in NPC dialogue.
- **Ball captures**: the stat `cobblemon:captured` (Molang `q.player.get_custom_stat('cobblemon:captured')`; as a
  scoreboard criterion `minecraft.custom:cobblemon.captured`, the name assumed) and the advancement trigger
  `cobblemon:catch_pokemon` with `{"count": N}`.
- **Recommended**: gate on species with `caught_count`, read by the guard when the player talks to it. It reads the
  stored Pokedex, so catches made before the gate existed count, and nothing has to watch in the background.

Three experiments stand before any caught gate is built: which acquisitions move `caught_count` (a duplicate, a
trade, an evolution); whether `catch_pokemon` fires only on ball captures; and the scoreboard criterion's name.

## 4. The gate is a per-player zone check

The guard (section 6) is where a player earns passage; the zone check is what enforces it. They meet in one
per-player record: **a pass score per zone** (objective `cob_pass`, one bit per zone, or one objective per zone),
set by the guard's dialogue when the player qualifies and read by the zone check. The guard can read badge flags
and the Pokedex through Molang (proven: EXP-022 reads and writes player data from dialogue); a vanilla
advancement cannot, but it can read a score (`minecraft:entity_scores`), cheaply. So:

- **Earn**: the player talks to the guard; the dialogue checks `q.player.data` badge flags or
  `q.player.pokedex.caught_count`, and if the player qualifies runs, as the server,
  `scoreboard players set <player> cob_pass_<zone> 1` and teleports them through (section 6).
- **Enforce**: per zone, the location-title pair of hidden advancements, reused: `in_zone_<z>` is true in the
  overworld inside the zone's boxes (the zone's polygon rasterised by `tools/subregion_boxes.py`, full height, y-64
  to y575) **and** the player's `cob_pass_<z>` is below 1. Its reward function turns the player back and revokes the
  advancement, so it is tested again a second later.

**Turned back** means: teleported to the zone's turn-back point (the near side of its guard, facing away), with
the guard's line on screen (`tellraw` in the guard's name and colour, and a short `title` subtitle), and a sound.

It handles, by being a position test once a second and nothing else:

| Case | How |
| --- | --- |
| walking, flying, digging, ender pearls | all end with the player inside the boxes; the test fires within a second of arrival, whatever the route |
| riding a flying Pokemon | the reward runs `execute on vehicle run tp @s <point>` before teleporting the player, so the mount comes too. **To prove**: whether a teleported vehicle keeps its rider in 1.21.1 (if not: dismount, move both, remount is not possible by command, so the mount is teleported beside the player) |
| logging in inside | the location trigger tests on the first second after login |
| respawning inside | the same; and a bed inside a forbidden zone is broken as the player is turned back (`execute at @s run fill ... air replace #minecraft:beds`) so it cannot loop |
| multiplayer | advancements and scores are per player: each is judged on their own pass |

Cost: one location test per zone per player per second for players without the pass, `entity_scores` plus a box
list (the Rift's zones rasterise to a few hundred boxes at the 32-block grid the titles use). Negligible for a small
group.

**Dependencies, unbuilt:** the badge flags (`gymN_cleared`, `data/progression.json`) are set by nothing yet
(STATE: flag-driven waystones are blocked on an in-game proof). The guard's badge check reads them, so the badge
gates wait on that; the caught gates do not.

## 5. The wall: the look, not the gate

Obsidian, crying obsidian and blackstone rising from the rim, the portal vibe climbing into the sky, visibly thinner
and broken at the weak points. No `nether_portal` block anywhere (they teleport players).

Blocks: obsidian, crying obsidian, blackstone, gilded blackstone, purple and magenta stained glass (and panes),
tinted glass. None is named by a spawn condition in `data/spawn_blocks.json`. Amethyst and purple concrete are, and
are not used. Every block goes through the spawn-block policy check like any template.

| Option | Blocks |
| --- | --- |
| a continuous wall 24 above the rim, 1 thick | 198,000 |
| continuous, 48 above, 2 thick | 792,000 |
| continuous, 96 above, 2 thick | 1,583,000 |
| **a 16-high, 2-thick base wall on the rim plus a 3x3 spire every 32 blocks to y320** | **264,000 + 452,000 = 716,000** |
| the same with spires every 48 to y400 | 264,000 + 424,000 = 688,000 |

**Recommendation: the base wall and spires to y320.** A continuous wall reads as a wall at any height; what reads
as "reaching the sky" is height, and height is cheap in spires, not in wall. 257 spires of obsidian banded with
crying obsidian, the top third purple glass, with Distant Horizons showing them across the map, over a 16-block
wall that actually closes the rim. Spires lean and taper at random, so they read as grown, not built. At the weak
points the base wall drops to rubble and the spires stop, which is how a player reads "this is where you can get
in". About 716,000 blocks, the size of the world tree's crown, as generated fill functions like the cavern.

## 6. The guards

At each weak point (Z1, Z3, Z6, and Z7 behind the League) the only walkable way in is a one-wide walkway, roofed so
nobody hops it, with a Cobblemon NPC standing in it.

- **Talking is passing.** A shared entity cannot step aside for one player, so a qualified player talks to the
  guard and the dialogue sends them through: sets their pass and teleports them to the walkway's far side
  (`q.run_command`, run as the server, proven in EXP-022). An unqualified player is told what they lack.
- **The NPC does not block on its own.** The research finds Cobblemon NPCs can be made invulnerable, unpushable
  and stationary (the class `tools/compile_dialogue.py` writes already is), but the code does not give them a solid
  collision box: a player may squeeze past in a one-wide walkway. So the walkway is closed behind the guard by a
  real block (iron bars, or a door with no handle), and the guard stands in front of it. **To prove before
  building**: walk, sprint, sprint-jump, crouch, a piston, and a ridden flying Pokemon against a guard.
- **The zone check sits behind every guard**, and speaks in the guard's voice when it turns someone back: the same
  wall.
- **Characters and lines are Codex's** (who each guard is, why they stand there): `docs/HANDOVER_CODEX.md` item 23.

## 7. The Rift biome

A custom biome, `cobblers:the_rift`, painted with `/fillbiome` over the Rift's extent from the floor to the sky.

| Wanted | Possible in a vanilla biome definition | How |
| --- | --- | --- |
| portal particles | yes | `effects.particle`: `minecraft:portal`, probability about 0.02 |
| fog colour | yes | `effects.fog_color`, `sky_color`, `water_fog_color`: violet-grey |
| **heavy fog** | **no** | fog distance is the client's; a datapack biome sets its colour, not its density. Needs a client mod or a shader; not proposed |
| light from below | not from the biome | from blocks: crying obsidian (light 10) scattered in the floor, and in the wall's base |
| mood sounds | yes | `effects.ambient_sound` / `mood_sound` |

**What the biome does to spawns, and why it cannot go in alone.** Every Rift entry in the compiled pools carries
`"biomes": ["minecraft:windswept_gravelly_hills"]` (checked in `build/datapacks/cobblers_spawns`, the Victory
Road and `rift_trunk` pools). Repainted to `cobblers:the_rift`, every one of them stops matching: the Rift would
spawn nothing we authored. Cobbleverse's inherited pools key on biome tags (`#cobblemon:is_hills` and the like),
which a new biome is in only if we put it there: those would stop too. So the biome ships with:

- `cobblers:the_rift` added to the biomes of every `data/spawns.json` entry scoped to the Rift's sub-regions and
  to Victory Road's corridor, and recompiled;
- the biome added to the biome tags the Rift's current biome is in, through the tag pack
  (`tools/spawn_tag_pack.py`), so the inherited pools see it as they saw the gravelly hills;
- a check that fails if any Rift-scoped entry does not name it.

Cost: `/fillbiome` over about 2.2 km² and y64-y320 (in 4x4x4 cells), split under its volume limit into generated
functions: a new re-export step after the cavern's own `60_biome`. It survives the world only as long as the world;
every re-export re-runs it.

## 8. Build order, once approved

1. the three spawn experiments (section 3) and the guard walk-past test (section 6);
2. the badge flags (the dependency in section 4), or the caught gates alone first;
3. the biome with its spawn and tag changes and its check;
4. the zone check and passes, with a fail-closed audit (every zone has boxes and a turn-back point; every guard has a
   dialogue that grants its zone's pass);
5. the wall and spires, then the guards' walkways;
6. staging rehearsal, audit, and a flight.
