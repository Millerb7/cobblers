# Gym trainers: the juniors inside the eight gyms

The owner, 2026-10-06: *"Each gym should have its own trainers inside it, placed so a player must pass them, with
teams that fit the leader's type and the level band -- attrition before the leader, as the mainline does. Every
gym, both modes, audited against its own real geometry."*

This is the builder's record: what is placed, how each seat was proved, what the proof does not cover, and what an
independent audit must check. The audit is somebody else's (CLAUDE.md principle 16).

## Who owns what

| Half | File | Written by |
|---|---|---|
| The stand: seat, yaw, sight distance, skin, eye contact, why | `data/gym_junior_trainers.json` | hand, from `tools/gym_trainers.py propose`; proved by `tools/gym_trainers.py check` |
| The roster: Normal and Challenge teams, AI, lines | `data/trainers.json` (class `gym_trainer`) | `docs/story/generate_trainers.py --write-active` from `docs/story/TRAINER_RULES.json` `gym_trainers` |
| The defeat field `quest.<id>.defeated` | `data/progression.json` `quest_fields` | hand (21 entries) |
| The rctmod files, eye contact, the rematch hold-off | `build/datapacks/cobblers_trainers` | `tools/route_trainers.py` (the gym seat file is one more source in `load()`) |
| The summon | `tools/reapply.py` R17 | unchanged: R17 summons every `route_trainers.placements()` entry, which now includes the 21 |

The seat file declares only stand fields; the roster declares none (`tools/route_trainers.py` `ownership()`), and
`data/id_authorship.json` lists `data/gym_junior_trainers.json` as a satellite of the `trainers` space.

## What is placed

26 juniors: 3, 2, 3, 3, 3, 4, 4, 4. Section 4 of docs/mechanics/GYM_INTERIORS.md set 2, 2, 2, 2, 3, 3, 3, 4; the
owner asked on 2026-10-07 for at least three a gym, some more, so gyms 1, 3 and 4 gained one each and gyms 6 and 7
one more each (their galleries and stairs had the most room between proven seats; gym 5's only spare seats crowd the
reed stair beside two juniors, and gym 8 already had four). **Gym 2 cannot take a third** under the proof below: with
a rider able to set down anywhere open to the sky, the only must-pass ground is the porch, door and vestibule, and of
the 123 proven (seat, sight) pairs there no three have disjoint `seen()` sets (`apart`). A third gym 2 junior needs a
change to the hall (a gate or a roofed approach) or the owner relaxing `apart` there. Every one has `eye_contact` true (rctmod `forceBattleOnSight` at its `sight_distance`, `forceBattleLookTicks` 30, `forceBattleMaxLevelDiff` 10), `maxTrainerDefeats` 1, the rematch hold-off and its per-player field `quest.<id>.defeated`, exactly as a route trainer. `first` is the GENEROUS move count at which a walker first enters its sight; juniors are listed in that order, which is the order their levels rise in. Normal is the team; Challenge is the same top level plus the member shown and a held item on the top member.

### gym1 (Brock, Rock; ace 20; leader stand [1832, 156, 3696])

| id | name | seat | yaw | sight | first | Normal | Challenge adds | where |
|---|---|---|---|---|---|---|---|---|
| `gym1_junior_01` | Hall Mason | [1819, 147, 3681] | 135 | 2.5 | 12 | roggenrola 16, nacli 17 | rockruff 16; sitrus_berry | the_gantry: on the south gantry where it leaves the loft's east edge: the stair is the only way onto the loft and the gantries the only way off it, and every walk east passes inside her sight. (The loft's own edge, at the stair head, is the stair's only landing: a junior there would wall it.) |
| `gym1_junior_02` | Loft Foreman | [1828, 153, 3684] | -135 | 3.0 | 20 | rockruff 17, larvitar 18 | binacle 17; sitrus_berry | the_wall: at the head of the unfinished wall, where the climb tops out onto the beams: nobody reaches the lit slot without coming over the wall beside him |
| `gym1_junior_03` | Coal Hauler | [1826, 153, 3695] | -135 | 2.5 | 22 | rolycoly 18, carkol 19 | nosepass 18; sitrus_berry | the_beams: the south end of the beam walk where it meets the climb to Brock (added 2026-10-07) |

A rider setting down anywhere open to the sky still has to pass every junior here (a roofed hall).

### gym2 (Misty, Water; ace 25; leader stand [1605, 133, 2874])

| id | name | seat | yaw | sight | first | Normal | Challenge adds | where |
|---|---|---|---|---|---|---|---|---|
| `gym2_junior_01` | Quay Swimmer | [1611, 131, 2884] | 90 | 4.0 | 0 | buizel 21, shellder 22 | wingull 21; sitrus_berry | porch_path: on the island's path below the porch steps: the one-wide door at (1612, 133, 2881) is the hall's only way in once the well is sleeved (D1), and every way up the steps to it is in her sight |
| `gym2_junior_02` | Lifeguard | [1612, 133, 2878] | 0 | 3.0 | 1 | staryu 22, corphish 23 | krabby 22; sitrus_berry | vestibule: just inside the door, on the vestibule floor between the door and the pool: whoever comes through the door is in his sight before the hall opens out |

Proved for a player who arrives by air (see D1 and the island below). A rider setting down anywhere open to the sky still has to pass every junior here (a roofed hall).

### gym3 (Lt. Surge, Electric; ace 30; leader stand [1747, 191, 1414])

| id | name | seat | yaw | sight | first | Normal | Challenge adds | where |
|---|---|---|---|---|---|---|---|---|
| `gym3_junior_01` | Line Engineer | [1732, 175, 1424] | 135 | 3.0 | 9 | magnemite 26, pachirisu 27 | flaaffy 26; cheri_berry | tower_foot: on the hall floor at the foot of the transformer tower's stair, the only climb off the floor |
| `gym3_junior_02` | Relay Technician | [1731, 182, 1417] | 45 | 2.5 | 16 | voltorb 27, flaaffy 28 | emolga 27; cheri_berry | the_catwalk: on the catwalk between the tower cap and the downlead: the record's own seat for one (trainers_why: the catwalk, x1730-1733 z1402-1418) |
| `gym3_junior_03` | Cable Rigger | [1730, 183, 1412] | 0 | 3.0 | 17 | plusle 28, luxio 29 | minun 28; cheri_berry | the_catwalk: the raised west step near the north end, beside the climb onto the cable run (added 2026-10-07) |

A rider setting down anywhere open to the sky still has to pass every junior here (a roofed hall).

### gym4 (Erika, Grass; ace 35; leader stand [4308, 111, 1480])

| id | name | seat | yaw | sight | first | Normal | Challenge adds | where |
|---|---|---|---|---|---|---|---|---|
| `gym4_junior_01` | Glasshouse Gardener | [4314, 116, 1502] | 90 | 3.0 | 10 | skiploom 31, gloom 32 | nuzleaf 31; lum_berry | low_canopy: on the low canopy's deck where the bench run arrives and the living bough leaves (trainers_why: the low canopy's deck) |
| `gym4_junior_02` | Canopy Botanist | [4302, 120, 1494] | -27 | 3.5 | 24 | weepinbell 32, tangela 33 | cacturne 32; lum_berry | high_canopy: on the high canopy's north edge, above the west line of piers, the only crossing to the court (trainers_why: the high canopy's north edge) |
| `gym4_junior_03` | Bough Climber | [4316, 120, 1499] | 0 | 3.0 | 13 | sunflora 32, breloom 33 | lombre 32; lum_berry | living_bough: the head of the living bough, between the two above in pass order (added 2026-10-07) |

A rider setting down anywhere open to the sky still has to pass every junior here (a roofed hall).

### gym5 (Koga, Poison; ace 40; leader stand [4594, 132, 2487])

| id | name | seat | yaw | sight | first | Normal | Challenge adds | where |
|---|---|---|---|---|---|---|---|---|
| `gym5_junior_01` | Fen Tracker | [4585, 117, 2478] | -90 | 2.5 | 5 | croagunk 36, skorupi 37 | grimer 36; black_sludge | the_flood: on the landing bale in the flood, the reed stair's first step: every way to the loft climbs past her |
| `gym5_junior_02` | Reed Watcher | [4584, 122, 2473] | 180 | 2.5 | 10 | golbat 37, arbok 38 | qwilfish 37; black_sludge | loft: on the loft's deck at the head of the reed stair, where the plank walks begin (trainers_why: the loft) |
| `gym5_junior_03` | Watch Floor Sentry | [4580, 132, 2488] | -90 | 2.5 | 35 | nidorina 38, skuntank 39 | toxapex 38; black_sludge | watch_floor: on the watch floor at the head of the flue ladder, the only way up to it, fourteen blocks short of Koga |

A rider setting down anywhere open to the sky still has to pass every junior here (a roofed hall).

### gym6 (Sabrina, Psychic; ace 45; leader stand [6196, 112, 3312])

| id | name | seat | yaw | sight | first | Normal | Challenge adds | where |
|---|---|---|---|---|---|---|---|---|
| `gym6_junior_01` | Archive Reader | [6199, 98, 3324] | 63 | 3.5 | 2 | kadabra 41, hattrem 42 | kirlia 41; lum_berry | hall: on the hall floor at the foot of the finished stack, the only climb to the gallery (trainers_why: the hall floor by the door) |
| `gym6_junior_02` | Gallery Medium | [6194, 105, 3328] | -135 | 3.0 | 10 | xatu 42, bronzong 43 | girafarig 42; lum_berry | gallery: on the gallery's south strip, which every way from the stacks to the turret crosses (trainers_why: the gallery's south strip) |
| `gym6_junior_03` | Lens Keeper | [6195, 105, 3308] | 45 | 2.5 | 16 | hypno 43, grumpig 44 | slowpoke 43; lum_berry | gallery: on the gallery's north arm beside the foot of the turret ladder. The record named the chamber's threshold at the ladder's head; that cell is within reach of Sabrina, and the arm's middle lane is the only way along it, so the seat is the ladder foot's north side |
| `gym6_junior_04` | Stack Warden | [6185, 105, 3325] | 0 | 3.5 | 12 | chimecho 43, medicham 44 | beheeyem 43; lum_berry | gallery: the south-west corner where the south strip turns north, between Gallery Medium and Lens Keeper in pass order (added 2026-10-07) |

A rider setting down anywhere open to the sky still has to pass every junior here (a roofed hall).

### gym7 (Blaine, Fire; ace 50; leader stand [6178, 107, 5001])

| id | name | seat | yaw | sight | first | Normal | Challenge adds | where |
|---|---|---|---|---|---|---|---|---|
| `gym7_junior_01` | Assay Hand | [6161, 111, 4992] | 0 | 2.5 | 4 | rapidash 46, camerupt 47 | magmar 46; sitrus_berry | the_spoil_steps: beside the head of the spoil steps where they meet the assay deck: the one climb off the drill floor that leads anywhere (trainers_why: the drill floor) |
| `gym7_junior_02` | Rim Researcher | [6177, 113, 4985] | 90 | 2.5 | 10 | houndoom 47, pyroar 48 | salazzle 47; sitrus_berry | assay_deck: at the east end of the assay deck, at the foot of the gantry stair |
| `gym7_junior_03` | Flue Keeper | [6179, 120, 4991] | 90 | 2.5 | 16 | ninetales 48, centiskorch 49 | torkoal 48; sitrus_berry | gallery: on the gallery at the head of the gantry stair, before the four hoods (trainers_why: the gallery) |
| `gym7_junior_04` | Stair Stoker | [6180, 116, 4987] | 135 | 2.5 | 12 | heatmor 48, talonflame 49 | darmanitan 48; sitrus_berry | gantry_stair: the stair's east lane three steps up, facing the west lane, between Rim Researcher and Flue Keeper in pass order (added 2026-10-07) |

A rider setting down anywhere open to the sky still has to pass every junior here (a roofed hall).

### gym8 (Giovanni, Ground; ace 55; leader stand [3565, 121, 6416])

| id | name | seat | yaw | sight | first | Normal | Challenge adds | where |
|---|---|---|---|---|---|---|---|---|
| `gym8_junior_01` | Sapper | [3576, 107, 6408] | 180 | 2.5 | 4 | sandslash 51, donphan 52 | marowak 51; leftovers | drift: at the sap's foot where the drift begins (trainers_why: the drift's mouth at the sap's foot) |
| `gym8_junior_02` | Heading Guard | [3569, 107, 6423] | 180 | 2.5 | 20 | dugtrio 52, gliscor 53 | claydol 52; leftovers | drift: at the far end of the shored heading, where it turns west for the undercroft: the heading is one wide and every walk to the tower stair comes along it |
| `gym8_junior_03` | Undercroft Sentry | [3562, 108, 6421] | 0 | 2.5 | 22 | rhydon 52, whiscash 53 | golem 52; leftovers | undercroft: in the undercroft at the foot of the tower stair (trainers_why: the undercroft) |
| `gym8_junior_04` | Wall Captain | [3562, 121, 6408] | 0 | 2.5 | 35 | seismitoad 53, nidoking 54 | gastrodon 53; leftovers | gate_walk: on the walk at the stair's head (trainers_why), the last stand before the gate walk to Giovanni |

**A rider on a flying mount gets past every junior here** (gym8_junior_01, gym8_junior_02, gym8_junior_03, gym8_junior_04): the hall is open to the sky (D3).

## How a seat is proved (`tools/gym_trainers.py`)

**The geometry is the hall's own build, never a world.** Gyms 1 and 3-8: `tools/gym_buildings.py` `build_one()`,
whose `Emit.at` is the voxel model of exactly what the function writes, over the lot's pad at its declared level.
Gym 2: the donor template `cobbleverse:misty` read from `COBBLEVERSE-DP-v31.zip` (found through
`COBBLERS_DONOR_ZIP`, `build/cobbleverse/`, or the local server snapshot; never copied into the repository), placed
at `data/placements.json` `gym2_misty_gym`, then `tools/place_donor.py`'s commands for that record (substitutions,
the prismarine quay plinth y100-106), then `tools/gym_interiors.py`'s healer sweep and gym 2 dig, replayed. Around
every hall, the ring of columns just outside the lot (gym 2: the shell box plus 3) takes its ground from
`tools/ground.py`, rounded; a ring column below the pad is raised to the pad.

**Every block is classified** solid, open, ladder, scaffolding or water by name; an unknown name fails closed.
Partial blocks (stairs, slabs, fences, walls, a stonecutter) count as full ones to stand on and to be stopped by;
thin ones (chains, lanterns, flowers, carpets) count as open.

**Two movement models over the same voxels.** A position is a feet cell with a passable head cell and solid footing
or scaffolding under it, or a feet cell that is water, a ladder or scaffolding.

- **GENEROUS**, for the cut: walk, step up one, fall any distance (no damage), climb, swim in six directions, and
  sprint-jump to any position within `REACH` (centre to centre: +1 up 4.0, level 5.0, -1 5.4, -2 5.8, deeper
  6.5) whose flight is clear for a body 0.58 wide. More than vanilla on purpose: a cut this player cannot cross
  holds for a real one.
- **MODEST**, for the softlock check: the same, with jumps only within `MODEST_REACH` (2.0 / 3.0 / 3.2 / 3.6).

**Arrival.** Gyms 1 and 3-8: on foot, from the ring. Gym 2: from the ring and from every position open to the sky,
because Misty's island floats (below).

**The leader is engaged** from a position within 3.5 of his stand (spawner + 1) in clear line of sight. A wall
between them is not an engagement.

**The sight, two ways.** rctmod's check passes through walls (docs/mechanics/GYM_INTERIORS.md section 3), and a
position is a cell the player's feet can be anywhere in (0.71 horizontally, half a block up on a slab): `SLACK`
0.87.

- `seen()` -- the least the sight can reach: positions within `sight_distance - SLACK` of the seat in clear line
  of sight. A player there is within sight wherever in the cell they stand.
- `sphere()` -- the most it can reach: positions within `sight_distance + SLACK`, through walls.

The cut uses the least, everything that must NOT be caught uses the most. A jump or fall is refused by the cut when
the player is surely within sight at some moment of it (any height of the arc, 0.3 off the line), so a sprint jump
cannot fly over a junior; and the softlock check refuses any jump or fall through the junior's two body cells.

**Per seat (`check_seat`), each a code:**

| Code | Holds when |
|---|---|
| `stand` | the seat is a dry position on solid footing with two open cells, inside the hall's footprint |
| `softlock` | with the junior's two body cells blocked, MODEST still reaches the leader (a junior pinned at speed 0 and sent home every ten ticks never walls anybody in) |
| `cut` | with `seen()` blocked, GENEROUS can no longer reach the leader from the arrival set |
| `leader` | `sphere()` holds no position that engages the leader |
| `street` | `sphere()` holds no position outside the hall's footprint |

**Per gym (`check_gym`):** `apart` (no position in two juniors' `sphere()`), `order` (top levels rise in the order a
player first enters each junior's `seen()`, GENEROUS distance, and stay below the leader's ace), `facing` (yaw
within 90 degrees of where a player first enters its sight), `roster` (a record in `data/trainers.json`). Written to
`derived/gym_trainers/report.json` with, per junior, `cut_holds_for_a_flyer` and, for gym 2,
`cut_holds_with_defects_open` -- information, not pass/fail.

`python tools/gym_trainers.py check` takes about two and a half minutes for the eight. `propose --gym gymN` prints
every seat near the shortest walk that passes all five per-seat checks, by the move at which a player first
enters its sight; the seats here were chosen from it.

## Misty's island, and the defects this work found

**The island floats.** `cobbleverse:misty`'s edges hold solid blocks only from about y118 to y128; the island's dirt
path ends at its south lip at y128, twenty blocks over the lot's ground (y104-108, `tools/ground.py`). With the well
blocked, a walker in the GENEROUS model cannot climb above y110 (measured: `tests/test_gym_trainers.py`
`test_gym2_the_proof_needs_defect_d1_closed_and_says_so`). So gym 2 is proved for a player who sets down anywhere
open to the sky. How a player is meant to reach Misty's door is not written anywhere this work found.

Findings, recorded and not chased:

- **D1, gym 2's well breaks out under the island.** `data/gym_interiors.json` gym2 `shaft` (scaffolding x1620
  z2867, y92-133) passes through open air between y108 and y114, where the island's underside is above the ground:
  its `shell_penetration_why` assumes 25 courses of template rock, and at that column there are not. A walker steps
  into the scaffolding from the lot and climbs straight into Misty's hall through the healer's cell -- **as built,
  that is the only way to Misty on foot, and it passes both gym 2 juniors** (`cut_holds_with_defects_open` false
  for both). The 21 open cells beside the column are listed under `assume_closed` in
  `data/gym_junior_trainers.json`; the proof runs with them closed and says so in the report. The fix belongs to
  `tools/gym_interiors.py` (sleeve the column, or start the well below the island) together with the owner's answer
  to how players reach the island.
- **D1b, gym 2's two dig trainers cannot be must-pass.** `data/gym_interiors.json` seats `gym2_swimmer_01` and
  `gym2_lifeguard_01` in the dig as unavoidable, but the dig is a loop out of and back into the hall where Misty
  stands, and her spawner is not gated, so the dig is optional. They have no roster and are not placed; the two
  gym 2 juniors here stand on the way to Misty instead.
- **D2, the leaders force battles on sight from 16 blocks.** The upstream leader mob files (COBBLEVERSE-RCT-DP-v20
  `data/rctmod/mobs/trainers/single/kanto_*.json`) set no `forceBattle*` field, so the server config applies:
  `forceBattleOnSight = true`, `forceBattleMaxDistance = 16.0` (`modpack/config/rctmod-server.toml` 117-122). If
  rctmod's sight passes walls for a leader as it did for a mansion guardian, a player who stares at a leader for
  1.5 s from a lower floor of the hall starts the leader's battle without walking the route or passing a junior.
  NOT VERIFIED for leaders. A fix is an override of the eight leader mob files with `forceBattleOnSight: false`
  (copying upstream's other fields, since our file replaces theirs whole); not done here.
- **D3, flight.** Cobblemon 1.8 riding sets a rider down anywhere open to the sky. Gyms 1 and 3-7 are roofed and
  every junior holds for a rider. Gym 8's yard and gate walk are open: a rider lands beside Giovanni and passes all
  four juniors and the puzzle. Whether riding is allowed inside a gym is the owner's call.
- **D4, eye contact is not a gate.** A forced battle needs player and trainer to stare at each other for 30 ticks
  (`experiments/EXP-034-scene-runtime`). "Must pass" here is geometric: every route enters the sight. A player who
  looks away and keeps moving can cross it. Nothing gates a leader on its juniors' defeat fields; doing so is the
  owner's call, because the hold-off (a beaten partner near a junior puts it on Cooldown, which refuses the unbeaten
  player even on interaction) would then hold the unbeaten player in place.
- **D5, no gym's `no_build` is wired** (every record says so): in survival a player can pillar or bridge round any
  seat.
- **D6, gym 1's loft has one landing.** The stair's top step lands on exactly one cell, (1815, 147, 3676); anything
  standing there walls the loft. The first seat chosen there was caught by the softlock check once body-through
  jumps were refused.
- **D7, gym 6's suggested threshold seat** (its `trainers_why`: "the chamber's threshold at the head of the ladder")
  is within reach of Sabrina, so it cannot hold a junior; the seat is the ladder's foot.

## Re-apply

Nothing in `tools/reapply.py` was edited. The steps that carry this work:

1. `prepare`: the existing `route_trainers` job rebuilds `cobblers_trainers` with the 26 (89 seated trainers, measured
   from `python tools/route_trainers.py` on 2026-10-07; 84 with the first 21). **Proposed, for the main session to add:** `add("gym_trainers:check", "gym_trainers.py", "check")` after
   `gym_buildings:build`, so a moved hall or seat stops the prepare. It needs the heightmap and, for gym 2, the
   donor zip, and takes about 2.5 minutes.
2. `install`, then a **restart**: rctmod's trainer, mob and dialog files and the advancements load at boot.
3. **R17**, which already summons every `tools/route_trainers.py` `placements()` entry with
   `rctmod trainer summon_persistent`; the 21 are appended after the HQ tower's seven. R17 runs after R16G, so the
   halls stand before the juniors arrive.
4. Probes: 26 `rctmod:trainer` entities with `TrainerId` `gym*_junior_*`, each within 0.75 of its seat.

## What an audit must check

The audit must not import `tools/gym_trainers.py`'s `Voxels`, `Graph`, `seen`, `sphere`, `sight_block` or
`body_block`: those are the derivation under test (CLAUDE.md, "How to prove an audit is independent").

1. **The geometry, independently.** Replay the emitted function text in `build/datapacks/cobblers_gym_buildings`
   (as `tools/gym_buildings_independent.py` does), not `gym_buildings.build_one`. For gym 2, place `misty.nbt`
   from the zip yourself, then the `cobblers_gym_interiors` `gym2` and `healers` function text and the donor
   function's substitutions and plinth. Confirm D1's 21 cells are open as built (or that the defect has since been
   fixed and the `assume_closed` entry is stale).
2. **A movement model of your own**, seeded from the lot perimeter (gyms 1, 3-8) and, for gym 2, from positions open
   to the sky. State its reach table and how it treats partial blocks, ladders, scaffolding and water.
3. **Per seat, all 21:** dry footing inside the hall's footprint; the junior's two cells do not wall off the leader
   for a cautious player (and no jump passes through them); every walk to the leader enters the junior's sight,
   counting a jump or fall that passes within sight; the sight cannot reach a position that engages the leader, or a
   position outside the footprint; no position is surely in two juniors' sight. Carry the player's position
   uncertainty explicitly (this builder used 0.87) and say what number you used and why.
4. **Mutate the generator, not the record.** At least: set `SLACK` to 0 in `tools/gym_trainers.py`, or drop the edge
   rule from `sight_block`, and show your audit and the builder now disagree about a named seat; move one seat three
   blocks off its chokepoint in a copy and show your audit fails it.
5. **Rosters.** Every member below `difficulty.gym_ace_levels[gym-1]`; Challenge top equal to Normal top; tops rising
   in the order a player first reaches each junior, computed by your own model; each member carries the gym's type
   (jar species data); every move in the species' learnset; every `heldItem` an item that exists; every skin in the
   rctmod jar.
6. **The emitted pack** (`build/datapacks/cobblers_trainers`): for each junior the trainer, mob (with
   `forceBattleOnSight` true and `forceBattleMaxDistance` equal to the seat's `sight_distance`), dialog and
   advancement files, and exactly one home, tag and cooldown line in `cycle.mcfunction`.
7. **Our list is not the world.** What else stands or is written inside the halls after R16G (town dressing, NPC
   seats, ambient Pokemon, later passes) that changes the geometry this proof used, or puts another trainer or NPC
   inside a junior's sight.
8. **In game (an experiment, not pytest):** each junior summoned at its seat and facing its yaw; eye contact firing
   at each; the hold-off; a walk of each hall counting the fights before the leader; D2 (a leader started from
   below).
