# Critical path walk, part 2: leaving Erika's town to the Champion

The owner, 2026-10-04: *"WALK THE WHOLE GAME ... Name every point where a player would stop, get stuck, or find
nothing."* This is the second half, gym 4's town to the Champion. The first half (Oak's lab to gym 4) is a separate
document.

**How this was walked.** I read the data a player meets, in order: `data/progression.json`, `data/quests.json`,
`data/dialogue.json`, `data/routes.json`, the trainer files, `data/gym_buildings/`, `data/rift_zones.json`,
`data/vr_caves.json`, `data/deep_city.json`, `data/relic_underground.json`, `data/placements.json` and the
generators that build them. Ground comes from `tools/ground.py` (the canonical heightmap). Walks were checked with a
breadth-first search on that heightmap: a step may climb at most 1 block and drop at most 3, a column at or below
sea level y62 is not walkable, and enforced zone boxes are excluded. The script is in the session scratchpad and is
not committed.

**Not read:** the staging world, the server, or any world save. Every "in staging" below is relayed from
`docs/STATE.md` or `docs/HANDOVER_SESSION.md`. Nothing here has been seen in game. The canonical heightmap does not
include the Rift sculpt's block pass, so every walk result needs an in-game check at the coordinate given.

**Re-run here:** `python tools/gym_buildings.py build`, then `python tools/gym_buildings_independent.py` found
1 problem over 7 buildings, gym1's seat overlap. Gyms 5-8 are clean.

Classes: **BLOCKER** (the player cannot go on), **STALL** (the player can go on, but would stop, get lost or be
misled), **GAP** (the player finds nothing where something is designed, or the design leaks), **OK**.

## 1. Leg by leg

| # | Leg / place | Coordinates | Path, and does it read as the way? | Trainers | Gym / gate | Badge and cap | Catch | Next town knows? | Class |
|---|---|---|---|---|---|---|---|---|---|
| L5 | Route 5, Erika to Koga | (4309, 1555) to (4646, 2446), 1,051 walked | No road is built on any critical route (STATE "Routes: 0 of 9"); the only guides are signposts at town exits, sub-region changes and junctions | 4 seated (L32-36); none forces a battle; no route events after Route 3 | - | cap 40 (Koga's ace) | tier 5 tables, band 28-38 | - | STALL (no road) |
| G5 | Koga, The Reed House | lot x4574-4606 z2463-2495; spawner (4594, 131, 2487); Koga stands at y132 | Seven-step puzzle (reed stair, plank walks, breathing tank, flue swim, ladder) | no gym trainers (`trainers: []`, by design) | open; RCT refuses the fight until Erika is beaten | ace venomoth 40 is ours; Soul Badge and a TM from `first_win`; cap moves to 45 | - | Koga's tracker (4643, 118, 2449) is gated on the story stage, not the badge; the Fenhide counter (4697, 119, 2491) is badge-gated | OK in data |
| L6 | Route 6, Koga to Sabrina | to (6196, 3398), 1,944 walked | Signposts only | 5 (L37-43); `route_06_trainer_04` has its feet and head inside a block at (5756, 106, 3078) | - | cap 45 | tier 6 | - | STALL (no road, one trainer stuck) |
| G6 | Sabrina, Hall of Lenses | lot x6180-6212 z3302-3334; spawner (6196, 111, 3312) | five steps: stacks, the eye arch, turret ladder, lens, drop shaft | none | open | ace alakazam 45; cap moves to 50 | - | Sabrina's pattern actor (6191, 95, 3394) is stage-gated | OK in data |
| L7 | Route 7, Sabrina to Blaine | to (6074, 4995), 2,061 walked | Signposts; the Tilpey outlet bridge (6632, 3904) is in staging | 6 (L41-48) | - | cap 50 | tier 7 | - | STALL (no road) |
| G7 | Blaine, The Assay House | lot x6154-6186 z4980-5010; spawner (6178, 106, 5001) | nine steps, including the leap and the geyser ride out | none | open | ace charizard 50; cap moves to 55 | - | Blaine's analyst (6071, 108, 4992) is stage-gated | OK in data |
| L8 | Route 8, Blaine to Giovanni | to (3647, 6497), 3,050 walked (the longest leg) | Signposts only, round the crater skirt | 7 (L45-53); the gate watcher (4135, 110, 6336) reacts to `gym8_cleared` | - | cap 55 | tier 8 | - | STALL (no road) |
| G8 | Giovanni, Gate of the South | lot x3556-3588 z6400-6432; spawner (3565, 120, 6416) | yard gate, then the sap, the shored heading, the tower stair and the gate walk | none | open | ace rhyperior 55, never fought; cap moves to 60 | - | Giovanni's watch (3643, 114, 6497) is stage-gated | OK in data, unproven (section 3) |
| V0 | Holdfast to the trailhead | 1,174 walked to (3548, 112, 5322) | Signposts; the Challengers' Cairn (3556, 6112) and the Benchmark (3708, 5716) sit beside it | none | the Rift surveyor (3552, 112, 5334) sets `rift_crisis_pending`; G2's gatehouse is the z2 gate (8 badges) | - | `rift_foot` (tier 8) | Holdfast is the last shop | OK |
| V1 | The Rift floor, G2 to the Deep | about 2,700 walked: the south-west arm, the fork (4174, 3882), the trunk to about (3610, 3243) | a canyon, so it reads as the way | none | z2 enforced | cap 60 | tier 9 (52-60) | - | STALL (item 7) |
| V2 | The Deep, the HQ door | Sink Gate stair; HQ door (3443, 67, 3282), guard (3444, 67, 3283), sign (3444, 68, 3281) | the stair towers were fixed 2026-10-03 (one twin stays roofed, at (3544, 3241)) | none | the guard admits at `rift_crisis_pending` or later | - | - | the Deep's Mart clerk and stalls are not built | STALL (items 6 and 9) |
| V3 | Relic underground, hall and cradle | knock box (3422-3424, 1-3, 3305-3307); hall (3390, 8, 3262); cradle (3357, 12, 3306); binder (3363, 13, 3312) | a lit stair, passage and gallery | none | zone `relic`: 8 badges plus the guard's admit | the choice "Release Hoopa." sets `rift_crisis_resolved` | spawn-free | - | in staging per the 12:43 apply on 2026-10-03; never walked; GAP (item 10) |
| V4 | Victory Road's caves | mouth (3560, 1, 3064); rest station (3606, 23, 2835); exit ravine (3656, 64, 2566) to (3656, 89, 2486) | "there is no path": a braided cave | 10 (L56-60) | **fights 8-10 and the ravine are inside z5** | - | Habitat tiles 54-60 | - | **BLOCKER (item 1), GAP (item 3)** |
| V5 | G5, the League's precinct | guard (3573, 85, 2680); knock box x3571-3576 y85-86 z2680-2682; arrival (3573.5, 85, 2677.5) | a surface walk from the Deep's north rim (3576, 83, 3000), 318 steps; on to the League lot, 255 steps | none | z5: `rift_crisis_resolved` | - | - | the steward (3647, 89, 2490) is stage-gated | OK if the finale fired; else item 2 |
| V6 | The League and the Champion | lot x3635-3754 z2375-2485, y88 | the template's own rooms; the elevator to the Champion needs `cobbleverse:trainer/kanto/defeat_elite_lance` | E4 57-60, Blue 58-62; spawners inside the template, positions not in data | the RCT chain (Giovanni, then Lorelei ... Blue) | cap 60, then 62 before Blue, then 100 | - | the League sells nothing (by design) | unproven (items 5 and 12); **the lot is in z4 (item 4)** |

## 2. Every stop, stuck or nothing point, ranked

### Blockers

1. **BLOCKER: Victory Road's last three fights and its exit lie inside z5, and the zone check cannot tell a passed
   player from a passless one underground.**
   - Victory Road's fights 8, 9 and 10 stand inside z5's boxes: (3642, 48, 2673), (3641, 55, 2614) and
     (3655, 65, 2564). So does the exit ravine's foot at (3656, 64, 2566). See `data/vr_trainers.json:147,185` and
     `data/vr_caves.json:95`.
   - z5's boxes run from y-64 to y575 (`data/rift_zones.json` `y`). At x3584-3743 their south edge is z2687.
   - The zone check tests the SCORE `cob_pass_z5` (`tools/rift_zones.py:1839`), and only the knock box at G5's
     surface gatehouse sets that score (`grant`, called by `qualify`).
   - So a player walking the caves north after fight 7 at (3621, 42, 2716) crosses about z2687, 40 blocks
     underground, and is teleported to the turn-back point (3573.5, 86, 2688.5). That happens **even if they hold
     `rift_crisis_resolved`**. They never meet fights 8-10 or see the ravine onto the League's apron.
   - They recover by knocking at G5, a few steps north of where they land. So this blocks Victory Road as designed,
     not the Champion.
   - Fix: for a `flag` or `badges` pass, test the advancement inside the zone function as well as the score. Or put a
     knock box where the cave crosses z2687.
   - In-game check: walk from fight 7 north holding the flag, with `cob_pass_z5` unset.

2. **BLOCKER (conditional): the finale, and with it G5, depends on 13 conversations in strict order, and none of
   them depends on a badge.**
   - Every transition in `main_worldshift_reveal` is `progression_equals` on the stage before it
     (`data/quests.json:1601-1689`). The chain is Pallet, then Brock, Misty, Surge, Erika, Koga, Sabrina, Blaine,
     Giovanni's watch and the Rift surveyor.
   - Only after that does the HQ guard admit the player (`relic_hq_admit`, `:1750`). The binder sets
     `rift_crisis_resolved`, and z5 needs it.
   - If any one actor is skipped, every later actor loops its `*_locked` line. The Rift surveyor's locked line reads
     *"Victory Road remains sealed until Giovanni clears the regional approach"* (`data/dialogue.json:2631`). That
     line shows to a player who holds the Earth Badge, and it names the wrong cause.
   - Nothing in game tells the player which actor they missed. Nothing in this chain has ever been talked to in game
     (STATE "Mainline reveal runtime").
   - Fix: let each actor accept any earlier stage, or have each badge flag carry the stage forward. Make the locked
     lines say what is missing.

### Stalls

3. **STALL/GAP: Victory Road can be skipped on the surface.**
   - The traced region `entrance_to_e4` (bbox 3462-3613 x 2661-3025, `data/rift_regions.json`) is open Rift floor at
     y83-86.
   - On the heightmap, a walk from the Deep's north rim (3576, 83, 3000) straight up x3576 reaches G5's knock box in
     318 steps.
   - So none of the ten "unavoidable" fights (`data/vr_trainers.json`) is unavoidable. A player who follows the
     obvious ground never enters the caves.
   - Combined with item 1, the caves are optional and cannot be finished. The owner should decide which is meant.
4. **GAP (a latent BLOCKER): the League stands in z4, the apex zone gated on 120 species, not in z5.**
   - The `behind_league` cut at z2560 was drawn "31 blocks north of the League's lot" (`data/rift_zones.json:1039`).
     That lot is the pre-move one, x3517-3636 z2591-2701 (z5's `area_why`, `:3009`). The League moved to x3635-3754
     z2375-2485 on 2026-09-23 (`data/placements.json:7849`), which is north of the cut, inside z4's boxes.
   - z4 is held today: no zone check and no wall. So the League pocket is unzoned.
   - On the day z4 ships, the Elite Four sit behind 120 species. That is a blocker for every normal or Nuzlocke
     player, and `docs/mechanics/RIFT_ZONES.md` section 2a forbids it.
   - The audit does not catch it: `tools/rift_zones.py:1147-1154` checks only the cradle. `RIFT_ZONES.md:55` and
     `GATEHOUSE_CHANGES.md:23` ("opens on the League's side") repeat the old geometry.
   - Fix: move `behind_league` north of the lot (z < 2375), or give the League lot to z5.
5. **STALL (in game): the Champion's floor is reached only by the template's lumymon elevator, gated on Cobbleverse's
   `cobbleverse:trainer/kanto/defeat_elite_lance`** (`data/league_trainers.json` `order_enforced_by`).
   - That this advancement still fires for our override of `kanto_league_lance` has never been seen.
   - Neither has the order of the four rooms (`order_not_verified`).
   - If it does not fire, Blue is unreachable.
   - In-game check at the League (3694, 88, 2430): beat Lance, then `/advancement` test for that id.
6. **STALL: nothing points to the HQ.**
   - Giovanni's watch says *"the trunk toward the head ... the final operation lies above the containment cradle"*
     (`data/dialogue.json:2586`). The surveyor says *"Reach the cradle"* (`:2673`).
   - Neither line names the Deep, the Compact HQ or its door. The door, among 196 buildings, is found only by the sign
     at (3444, 68, 3281) and the HQ tower's ring symbol.
   - One line pointing to the HQ door would fix it.
7. **STALL: from G2 to the Deep, about 2,700 walked blocks of Rift floor hold no trainer, no event and no shop.**
   - The only Centres are the rim post at (3814, 3791), up on the rim, and the Deep's Rimside.
   - Holdfast is the last shop until the League, which sells nothing. The Deep's Mart clerk and its two stalls are
     not built (REVIEW 57, `data/markets.json` `no_counter`).
8. **STALL: Routes 5-8 have no road.**
   - 8,106 walked blocks have only signposts (STATE "Routes"). Route 8 alone is 3,050.
   - The badge's Xaero waypoint offer and the waystones are unproven in game (EXP-020 part F).
   - `route_06_trainer_04` stands with its feet and head in a block at (5756, 106, 3078) (REVIEW 62).
9. **STALL (staging only): the 2026-10-04 spawner fix (`281c0c9`) is not applied.** In staging every hall's leader
   still spawns one block proud of his floor. Re-run R16G.
   - When it re-runs, look for a leftover persistent leader entity at the old height. Giovanni's old spawner was at
     (3565, 121, 6416).

### Gaps

10. **GAP: the finale is a conversation.**
    - There is no Hoopa entity: the cradle has only a marker at (3357, 13, 3306), in `composition.cradle`.
    - There is no fight and no Compact trainer anywhere.
    - The HQ's interior is empty and its tower has no door (`data/relic_underground.json` `geometry.hq`). Codex's
      Scenes 1-4 are unbuilt (`data/quests.json` `generation_blockers`).
    - This is handover plan item 6.
11. **GAP: with z4 unenforced, the League can be entered by tunnelling.**
    - The rim north of the lot is a ridge about 10 blocks thick: y93 outside at (3694, 2305), rising to y152 at
      z2311-2317, and y87 inside at z2320.
    - It cannot be walked: the search above found no path from Koga's town. A short dig gets through.
    - That skips G2, the finale and z5, but not Giovanni: the RCT chain still requires him before Lorelei.
    - Item 4's fix closes this too, once z4 or z5 covers the lot.
12. **GAP: the League's rematch hold-off may not reach the E4 and Blue.**
    - It is a sphere of radius 71 round (3694, 88, 2430) (`tools/route_trainers.py:466-485`). The template is
      159 tall, and its spawners' heights are not in data.
    - A Blue above about y159 escapes it, which would make him an XP farm.
    - In-game check: read each spawner's y.
13. **GAP: towns 5-8 do not react to the badge.**
    - Only the market counters do. Each town's story actor is gated on story order (item 2).
    - The four beats' physical evidence (Koga's anchor, Sabrina's table, Blaine's model, Giovanni's packet) is
      unbuilt (`data/quests.json` `physical_evidence`).
14. **GAP: the Mega field is open at 6 badges with Megas at 70/77** against a cap of 50 (REVIEW 33). It is off the
    critical path.
15. **GAP: Giovanni's first-win TM pool lists `tmcraft:tm_fireblast` twice** (`data/progression.json:3130-3131`), so
    Fire Blast comes up 2 times in 4, in the Ground gym.
16. **GAP: Victory Road's spawns.**
    - There is 1 spawn hole at the trailhead (`data/routes.json` `subregion_holes`).
    - Upstream cave pools live in the seams between Victory Road's Habitat tiles (EXP-033 unrun).

### OK (in data; none played)

- **The cap ladder:** 40, 45, 50, 55 after each gym, then 60 through the Elite Four, 62 before Blue and 100 after
  him. It is verified in rctmod source (`docs/mechanics/LEAGUE_LEVEL_CAP.md`).
- **Teams:** the leaders' aces equal the contract. Route trainers stay under each leg's cap: 32-36, 37-43, 41-48,
  45-53, and Victory Road 56-60.
- **Wild levels:** encounter tiers 5-9 stay under their caps (`data/encounter_design.json` `rules.tiers`).
- **Rewards:** the badge items and TMs come once, through `first_win`.
- **Gates:** G5's grant chain works, and the surface walk from G5 to the League lot is 255 steps.

## 3. Giovanni: where to stand and what is needed

**How the fight is set up**
- **The spawner.** `data/gym_buildings/gym8.json:45` puts `rctmod:trainer_spawner{TrainerIds:["kanto_giovanni"]}`
  at (3565, 120, 6416), on a redstone block at (3565, 119, 6416), built by R16G.
  - In staging it is still one block higher: the spawner at y121 on redstone at y120, because `281c0c9` is not
    applied. He stands on it, a block above the walk.
  - The donor shell's own spawner is taken down by the same function. STATE's trainer audit reads 8 of 8 gym
    spawners, so this is the only `kanto_giovanni`.
- **The team.** `tools/route_trainers.py` overrides the upstream id at `data/rctmod/trainers/kanto_giovanni.json`
  (`:381`), in the world-local pack `cobblers_trainers`.
  - The team is Hippowdon, Persian, Mudsdale, Nidoqueen, Krookodile and Rhyperior, at levels 52-55, `GEN_9_SINGLES`
    (`data/gym_trainers.json`, `held: false`).
  - The badge flag is bound to this id (`data/progression.json` `gym8_cleared`), and so is the first-win table: the
    Earth Badge, `lumymon:ancient_dna`, a Master Ball and one TM.
- **The proof he gives.** No leader override has been fought since the overrides landed: Brock's fight in EXP-035
  used Cobbleverse's own team. So his fight is the first test that a world-local override beats the global
  COBBLEVERSE-RCT-DP file.
  - **What to watch:** our lead is Hippowdon at 52-55. Upstream's Giovanni is about 68-70
    (`docs/story/GYM_SUFFICIENCY_AUDIT.md:13`). A 68-70 lead means the override failed.
  - The loot-table overrides at the same precedence already work, which is good evidence the team will too.

**What a player must hold**
1. **Blaine beaten in rctmod's own record.** Giovanni's upstream mob file has `requiredDefeats` in the Kanto chain.
   The chain is relayed from `LEAGUE_LEVEL_CAP.md`; his exact entry was not read, because the zip is not in the
   repo.
   - For the owner on staging, as an op: `/rctmod player set progress after kanto_blaine <name>`. The syntax is
     documented, but the argument order is ASSUMED.
   - Setting defeats by command does not grant the badge flags (EXP-027). It does not need to: only RCT's record
     gates the fight.
2. **A party of level 55 or under.** The cap after Blaine is 55: `/rctmod player get level_cap` should read 55. One
   member above it, and every RCT trainer refuses, silently (EXP-035 row 13).
3. **Not already holding `cobblers:flag/gym8_cleared`.** The no-rematch hold-off sets `Cooldown:40` on him while a
   badge holder is within 9.
4. The Kanto series, which is the default (`initialSeries = "kanto"`).

**Where to stand**
- **On the gate walk beside him: (3564, 121, 6416).** This is route step 4's standing cell
  (`data/gym_buildings/gym8.json:177`).
- **On foot:**
  1. Enter by the yard gate, x3584 y113-115 z6415-6417, off the gate square by the waystone (3594, 114, 6444).
  2. Climb down the sap, the well head with the spruce headframe, to (3577, 107, 6408).
  3. Take the shored west heading to the undercroft (3569, 107, 6420).
  4. Climb the tower stair from (3565, 107, 6423) to (3562, 121, 6408).
  5. Walk eight cells south.
- **Or** `/tp @s 3564 121 6416`.
- **Afterwards,** check the flag, the four first-win items, `level_cap` reading 60, and the drop into the yard at
  (3567, 121, 6416).

## 4. Where documents and the repository disagree

| Document says | The repository says |
|---|---|
| `docs/STATE.md:243`: Hoopa's cradle is "reserved and unbuilt" | `data/relic_underground.json` `geometry.cradle.carve: true`; the handover's 12:43 apply re-seated the binder in it |
| `docs/STATE.md:347` and `data/quests.json` `generation_blockers`: "advancement-backed gym flags cannot gate dialogue" | `tools/compile_dialogue.py:27,165` compiles `{"kind": "flag"}` conditions, and gym 5-8 and Champion conversations use them (`dlg_pips_gym`, `dlg_station_director`, `dlg_gate_watcher` and others) |
| `docs/STATE.md:89`: overrides at `data/rctmod/trainer/` | `tools/route_trainers.py:325,381` writes `data/rctmod/trainers/` |
| `data/gym_trainers.json:148,196`: Sabrina's and Giovanni's "gym building is not built yet" | `data/gym_buildings/gym6.json` and `gym8.json` exist |
| `data/gym_buildings/gym6.json` and `gym8.json` `supersedes_why`: "NO record in data/gym_interiors.json with superseded_by" | `data/gym_interiors.json:2438,2952` carry `superseded_by` |
| `data/routes.json` victory_road `rift_apex` (3576, 2762): "the League stands in the trench" | the League has stood on the apex oval since 2026-09-23 |
| `data/rift_zones.json:1039,3009`, `RIFT_ZONES.md:55`, `GATEHOUSE_CHANGES.md:23`: the League lies south of `behind_league` | the lot is north of it (item 4) |
| `docs/research/notes/legendary-catalogue-reopened.md:115`: Giovanni's `ancient_dna` is emptied | `data/progression.json` `first_win` gives it back |
| `docs/story/AVAILABILITY.md:1290`: "places no blocks anywhere" | its own table lists 10 blocks; STATE counts 81 natural |
