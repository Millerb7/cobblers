# The world tree: what it should hold

**Status: PROPOSED (content-architect, 2026-10-12). Nothing here is built, generated, placed or seen in game.** The
owner, 2026-10-12: "I don't know what's planned for the world tree, but it needs something more than just a few
saplings full of birds at its feet. Originally I was going to make a city you had to fly to, but I don't know anymore.
It has so many branches and ability. Something should be there."

Labels: *derived* = computed here from the generator's constants (`tools/tree_grove.py`), **not** measured from its
block list (this unit has no shell; U1 measures it); *relayed* = from a document, not re-measured; *read* = read at the
cited line today; *ASSUMED* = no source, an experiment in section 8.

---

## 1. The tree as built

The source of truth is code, not data: `tools/world_tree.py:26-27` (centre (2016, 2280), ground y116) and
`tools/tree_grove.py:65-68` (tier `world`). Origin y = ground + 1 = 117 (`world_tree.py:48`). **The tree has no record
in `data/landmarks.json`** (*read*: no match); its centre is copied by hand into `data/world.json:237`,
`data/routes.json:3486` and `data/long_count.json:44`.

| Part | Value | Basis |
|---|---|---|
| Trunk | rounded, radius 17 at the base (35 x 35 box), tapering to 9.35 at y457 | `tree_grove.py:115-127`, *derived* |
| Roots | 32, one block wide, 18-29 long from the centre, 20 high at the axis falling to 0 | `landmark_trees.py:73-82`, `tree_grove.py:66` |
| Storeys | 8 near-level limb tiers, 9-11 limbs each, limb radius 5 tapering to 2.75 | `tree_grove.py:117, 130-139` |
| Crown | dome base y457 (record), top y535; build limit y575, so 40 blocks of headroom | `data/world.json:235-240`, *read* |
| Blocks | 1,264,724 in 4 fill functions | `docs/world-building/BUILT.md:106`, *relayed* |

**The storeys** (world y = 117 + 56 + 38i; reach = 58 x U(0.82, 1.05) x (1 - 0.12i); all *derived*):

| Storey | Limb base y | Reach from centre | Trunk radius there | Clear of the trunk face |
|---|---|---|---|---|
| 1 | 173 | 48-61 | 17.0 | 31-44 |
| 2 | 211 | 42-54 | 16.0 | 26-38 |
| 3 | 249 | 36-46 | 15.0 | 21-31 |
| 4 | 287 | 30-39 | 13.9 | 17-25 |
| 5 | 325 | 25-32 | 12.9 | 12-19 |
| 6 | 363 | 19-24 | 11.9 | 7-12 |
| 7 | 401 | 13-17 | 10.9 | 2-6 |
| 8 | 439 | 8-10 | 9.8 | **none: buried in the trunk** |

A limb rises 1-3 blocks over its length, so its top is walkable: a rounded log ridge about 3 wide near the trunk
narrowing toward the tip (*derived*). **Seven storeys are usable; the eighth is a knot.** BUILT.md:92 says "8, at +56
to +322", which is true of the generator's tiers and not of what a player can stand on.

**The crown has floors already** (*derived* from `tree_grove.py:140-153`). Fifty hanging limbs leave the trunk axis at
y449 (crown_base - 8) and run to four rings of leaf balls:

| Ring | Balls | Ring radius | Ball centre y | Limb from y449 to | Grade |
|---|---|---|---|---|---|
| 1 | 13 | 67-83 | ~461 | ~452 | **near level: 13 radial spokes, ~3 blocks over ~75** |
| 2 | 15 | 60-74 | ~483 | ~475 | about 1 in 2.7: walkable ramps |
| 3 | 13 | 47-58 | ~505 | ~497 | about 1 in 1.1: a jumping climb |
| 4 | 9 | 26-32 | ~523 | ~517 | too steep |

The core dome (radius 38, half-depth 23) spans y466-512. **Between y~449 and y466, out to about 55 from the axis, is
open air under a leaf roof**: the trunk top (to y459), the 13 spokes and the rising ramps. That vault, roughly 110
across and 15 high, is the one large ready-made space in the tree. The outer balls reach about 87-108 from the centre
(ring radius plus ball radius). Leaves are persistent (`landmark_trees.py:36`), so carving does not start decay.

**How high a player climbs today without flying:** about **7 blocks**. Outside the trunk face a root is at most
~7 high (*derived*); above that is sheer log, and storey 1 is 57 above the ground. **With blocks, anyone climbs
anything:** nothing protects the trunk from ladders or pillars. The only precedent for stopping that is the Gastly
mansion's "adventure mode inside" (`docs/STATE.md:359`).

## 2. What is around it

- **Route 3** (Misty to Surge, after gym 2) passes the trunk: nearest trunk edge 77.6, so the centre is ~95 from the
  centreline (`data/routes.json:3490-3496`, *relayed*). That record says "no trunk or crown reaches the road
  centreline" on a crown radius of 78. **78 is the ring radius, not the crown's edge.** With the balls added, the edge
  is 87-108 (*derived*), so some ring-1 balls may hang over the road at y444-475. Harmless 350 blocks up, but the
  record's claim may be false (U1).
- **The grove:** 7 giants and 4 elders. The elders carry 16 activated Habitat Blocks (Natu, Pikipek/Trumbeak,
  Pidgey/Pidgeotto, Swablu; `SAPLING_BIRDS.md:303-310`; `data/habitat_blocks.json:2291+`). They stand 53, 60, 65 and
  74 from the trunk centre (*derived* from those coordinates). Storey 1's limbs reach 48-61 at y173-183. Elder crowns
  are ground+63 to +81 (`habitat_blocks.json:2312`), about y180-199. **Whether a storey-1 limb runs into
  `elder_foothill_grove_2` (53 away) is unmeasured.** `tree_grove.augment`'s docstring (`:285-287`) still describes the
  old tree ("first limb storey ground+24 reaching 24"), so the clearance was never re-checked (U1).
- **At its foot:** the cache `r3_world_tree_roots` (Big Root, 2 Sitrus, `data/rewards.json:366-380`). The Long Count
  (C3, gym 2) is a line of trees aimed at it, and Perrin's errand is about its roots (`LONG_COUNT.md:12-16, 41`).
- **Distances from the trunk** (*derived* from WORLD_SWEEP_2026-10-09.md:65-73 coordinates): Agnes Merrow's carving
  325, Misty's town 664, Surge's town 930, the Displaced City 1,449. No town, Centre or waystone is within 300.
- **Its intended village:** BUILD_PREP.md:100-103 chose this grove for "a warden village that keeps the forest floor
  for the forest's Pokémon ... a town in the limbs leaves it wild underneath". The owner set that city aside on
  2026-09-21 (`docs/STATE.md:287`: cabins on all eight storeys, bridges between the giants, a stair to a crow's nest).
  An untested `tools/grove_city.py` exists only on local branch `world/league-rift-grove`.
- **Encounter pool already written for it:** `tree_town_canopy` (`data/spawns.json:22177-22331`): Sewaddle, Aipom,
  Pikipek/Trumbeak, Emolga, Pachirisu, Applin, Combee, Cutiefly at 25-40. It is placed nowhere
  (`data/nuzlocke_zones.json:1838-1840`). Oak leaves are already a native condition for the Applin line
  (`data/spawn_blocks.json:2337-2343`), and the crown is oak.

## 3. Flight, honestly

- **Flying riding works:** Charizard, in EXP-000 (`experiments/EXP-000-cobblemon-1.8-compat/README.md:122`).
- **Nothing gates it:** "nothing in the repo gates riding" (`docs/STATE.md:321`). Gating flight by badge is
  "Mechanism **not researched**" (`docs/world-building/NAVIGATION.md:225`). Which species fly, and from which badge
  they are catchable, is not recorded anywhere I found (U2).
- **So "a city you have to fly to" is not a gate today.** Whoever first catches a flyer gets there, at any badge, and
  so does anyone with ladders. Three honest ways to gate a high place:
  1. **A zone** keyed on a flag, as the Rift's, the gulch's and the relic hall's (built on staging). Whether it turns
     back a *mounted* player is still "To prove" (`docs/mechanics/RIFT_ZONES.md:141`).
  2. **A barrier partition** at the thing that matters (the legendary chambers' pattern,
     `LEGENDARY_HOMES.md:243-245`, *relayed*). Arrival by air does not matter if the door is the gate.
  3. **A roofed climb** that flight cannot skip, as Rayquaza's pillar (`KYOGRE_CAVE.md:445`).
- **The sky flag exists:** `cobblers.sky`, granted at `gym4_cleared` ("The high arches answer you now",
  `data/portals.json:37-44`). The owner kept sky portals east of x4000 because gyms 1-3 are the western strip and a
  western sky site "would sit unusable while the player walks past it for three gyms" (`portals.json:10`). The tree is
  at x2016. A gym-4 gate here repeats that objection, unless the point is to come back.

## 4. Directions

### A. The canopy city you fly to (the owner's original)

- **Experience.** From Route 3 at badge 2 the player sees lights in the crown at night. Later they fly up and land on
  the ring-1 spokes. A settlement fills the vault under the dome: decks on the 13 spokes, houses hung between them,
  a market, a Centre, a lookout on a ring-2 ramp. Its people are the sky's keepers, with a flying-type trainer circle.
  **Why return:** a waystone and Centre (a checkpoint), traders, rematches, a canopy pool.
- **Reuses:** the Deep's city pattern, buildings stood on a plan model rather than terrain (`tools/deep_city.py`,
  `docs/STATE.md:292`); the CobbleTowns Centre/Mart; residents and NPC seats; `ambient.py` workers; the zone system;
  the pocket island's fall-rescue sweep (`KYOGRE_CAVE.md:447`, `tools/portals.py:449-459`, *relayed*).
- **New:** a tree-surface model (the tree's own block list as a ground source); a deck/house kit for spokes; a
  landing-deck rule; the fall rescue at this height.
- **Gating:** a zone on `cobblers.sky` (gym 4), or ungated and accept first-flyer access. Either way, the flight gate
  itself is unproven (U2, U3).
- **Encounters:** `tree_town_canopy` on the decks; Noctowl and Toucannon for the outer balls; Tropius as a rare.
  Ids present in `docs/research/notes/drops-1.8.0.json`: noctowl :572, toucannon :853, tropius :862.
- **Cost:** about 4 builder units plus an audit, **~18-20M**.
- **Risks:**
  - A settlement 450 above the ground. Every fall is a death without the rescue sweep.
  - Under 15-45 blocks of leaves the vault is probably dark at noon (U5): lanterns on posts and floors throughout,
    never light blocks (`docs/STATE.md:211`), or Dark and Ghost types turn aggressive (`:210`).
  - A town's tick budget: the owner's proposed 2 carriers + 4 stationary workers (`:284`).
  - Everything above y319 depends on `cobblers_height` forever.
  - It is the Warden Grove the owner set aside, moved up.

### B. The warden hamlet: climbable, low storeys

- **Experience.** On Route 3 at badge 2, a root ramp leads to a stair cut round the trunk. About half a lap
  reaches storey 1 (y173, about 57 of rise). Rope bridges cross limb to limb. Three storeys (y173-249) hold 6-10 limb cabins,
  the wardens and a healer. A lookout on storey 3 looks down on the grove's nests and across to the Long Count's line.
  Below stays wild, the brief BUILD_PREP.md:100-103 set.
  **Why return:** the canopy pool's upper storeys at higher levels, a warden trainer circle with rematches, a trader
  for tree goods (Big Root, berries), and the stair continuing up (C).
- **Reuses:** residents/NPC seats and the Long Count's resident pieces; `tree_town_canopy` as activated Habitat Blocks
  in the trunk (the elders' pattern, `habitat_blocks.json:2312`); `ambient.py` (an Aipom carrier on a walkway); shrines'
  lantern-on-post style; the route trainer seats.
- **New:**
  - the tree-surface model;
  - a stair generator round a tapering cylinder (the circumference two blocks out is ~119 at the base and ~113 at storey 2, so a
    1:1 stair reaches storey 1 in half a lap and each storey after in about a third);
  - a bridge and cabin kit for limbs;
  - railings on every walkway edge;
  - the fall rescue.
- **Gating:** none, or gym 2 (the Long Count precedent). This is the badge-2 discovery, so its levels sit at the
  grove's: 21-23 now (`SAPLING_BIRDS.md:307-310`). Rather than 25-40, split `tree_town_canopy` by storey, for example
  22-26 on storeys 1-2 and 30-40 higher for return visits. That is trainer-balance-designer's call.
- **Cost:** 3 builder units plus an audit, **~14-16M**. The cheapest direction that puts people in the tree.
- **Risks:**
  - Ladders bypass the stair, which is harmless here.
  - Wild Pokemon wander off decks and fall: Cobblemon has no perching (`habitat_blocks.json:2312`); the perch
    behaviour is researched, not built (`docs/research/notes/habitat-nest-perching.md`).
  - Storey 1 may intersect elder 2 (U1).
  - The owner set the Warden Grove aside; this is a small version of it.

### C. A legendary in the crown, reached by the climb

- **Experience.** From the hamlet, the stair gives out at storey 4. Above it the way up is the tree itself: limbs
  that dead-end, a hollow carved through the trunk between storeys, a bridge only from one limb's tip to the next tier.
  It is a route puzzle over storeys 4-7 (y287-401), in adventure mode inside the tree's volume as the mansion does.
  It ends on the ring-1 spokes in the vault under the dome. A sanctum is carved into the core dome's underside.
  **Why return:** the climb is once; the crown's rare-spawn pool and the view are not.
- **Species.** None in the roster is unassigned (`data/dungeon_prize_roster.json:276-401`):
  - **Xerneas**, recommended: `to_dungeon` Patriarch, band 6, "Yveltal's pair, the life-tree" (`:325`). It renders
    from the jar model (`unhomed-legendaries-1.8.0.md:123`). Moving it here makes the pair geographic: Yveltal sleeps
    under the Patriarch, the death-tree over the Rift (`DUNGEON_3_PATRIARCH.md:40-45`), and Xerneas in the crown of
    the life-tree. The Patriarch keeps Zacian, Zamazenta, Suicune and the two UBs.
  - **Ho-Oh**: `to_dungeon` Ash Bell (`:286`). The research note itself proposed "a burnt tower climb to the roof"
    (`unhomed:99`), but the Ash Bell is its story.
  - **Shaymin**: `to_dungeon` jungle (`:310`); it "ships" only through MSD and MissingMons (`unhomed:81-82, 107`).
  - **Taken:** Celebi (placed, the Route 1 sapling, `:287`), Rayquaza (the owner chose the great cone's arch,
    `KYOGRE_CAVE.md:570`), Yveltal (the Patriarch boss, `:326`), Lugia (blocked, `:285`).
- **Reuses:** the sealed-chamber envelope and the barrier partition (`legendaries.py`; `LEGENDARY_HOMES.md:240-245`);
  the area-boss keeper (`hoopa_cradle.py`); the cave kit's `rare_spawn` occupant mode for the crown pool
  (`LEGENDARY_HOMES.md:259-264`).
- **New:** the climb's route (a puzzle a walk-audit can prove, as the relic hall's audit walks its way in); a chamber
  shell of wood (a leaf wall is not a seal); and the tree-surface model.
- **Gating:** the partition, on `champion_cleared` (Xerneas is restricted, band 6). Flight then does not matter:
  a flyer reaches the vault and finds the door shut.
- **Encounters at the crown:** Phantump/Trevenant at night, Noctowl, Hoppip/Jumpluff, Comfey and Swablu/Altaria
  (Swablu is grove_4's line, so a stage up). Ids present in drops-1.8.0.json: phantump :615, trevenant :861,
  hoppip :393, jumpluff :416, comfey :158, altaria :20.
- **Cost:** 2-3 builder units plus an audit, **~11-13M** (with B's model; ~15M without B).
- **Risks:**
  - A puzzle at 300-400 blocks with real falls needs the rescue, or it becomes a wipe machine.
  - The inherited Xerneas spawn (`unhomed:123` lists "65-75 ultra-rare, is_floral") must be off for "one home each"
    (U8).
  - Is Xerneas's 3D hitbox clear in a 15-high vault? (U8)

### D. A rip high in the tree

- **Experience.** On a deck at storey 4 or in the vault, a rip. Through it is whatever the draw gives at the player's
  band (`docs/mechanics/DUNGEON_DRAW.md:12-14, 52-65`). The tree becomes a door rather than a destination.
- **Reuses:** everything: the engine, its draw and lockout, and the proposed `data/dungeon_rips.json`, which already
  carries a "ground source" per rip (`DUNGEON_DRAW.md:87`).
- **New:** a tree ground source instead of `tools/ground.py` (`:89` requires heightmap ground). The rip's "outside"
  return point must be a wide deck, not a limb ridge.
- **Gating:** none; the draw's band is the gate. The click already refuses elytra (`:54`).
- **Cost:** **~3M** once the rips list exists. It depends on the owner approving DUNGEON_DRAW, which is design only.
- **Risks:**
  - A themed "up the tree" dungeon is not possible: the engine lays only level floors (`DUNGEON_3_PATRIARCH.md:33`).
  - No rip may sit inside a spawn-free town precinct (`DUNGEON_DRAW.md:93`), so with A or B the rip goes on a wild
    storey, not in the settlement.
  - Alone, it does not answer "something should be there".

## 5. Comparison

| | Who reaches it | When | Cost | Answers the owner |
|---|---|---|---|---|
| A canopy city | flyers (and ladders), gated only by a zone | gym 4 or ungated | ~18-20M | his original idea, the most |
| B warden hamlet | everyone on Route 3 | badge 2 | ~14-16M | people in the tree, now |
| C crown legendary | climbers; the door is the gate | Champion | ~11-13M with B | the top has a reason |
| D rip | everyone who gets up there | any band | ~3M | a door, not a place |

## 6. Recommendation: B, then C, with D as a garnish; A held until B is played

Climb up from the bottom. B makes the tree a badge-2 discovery the player can actually enter, and its stair is the
first leg of C's climb. C gives the top a reason that flight cannot cheapen, because the partition is the gate. The
crown's vault, which is where A would go, stays the destination either way. If the owner still wants a fly-to city
after walking B, A is built into that same vault on the ring-1 spokes, gated by a zone on `cobblers.sky`. Building A
first would build the biggest thing on the least-proven mechanism: flight gating is unresearched and the zone against a
rider is unproven.

**Phased plan** (each step one unit; agents per CLAUDE.md):

| # | Step | Agent | Cost |
|---|---|---|---|
| 0a | Measure the tree from its block list (U1): storey tops, walkable widths, the spokes, the vault's air, storey-1 limbs against the elders, ring-1 balls against Route 3's centreline. Write `data/world_tree.json` (centre, origin, seed, storeys as measured) so the tree stops living in a tool constant | datapack-content-dev | ~2M |
| 0b | U2: can Cobblemon 1.8.0 riding be restricted by config or condition; which species fly | cobblemon-researcher | ~0.6M |
| 0c | `tools/tree_surface.py`: the tree's blocks as a ground source (the ground rule's "measured plan data"), plus the fall-rescue function on the pocket island's pattern | minecraft-systems-dev | ~4M |
| 0d | In game on staging: U3, U4, U5 (zone vs a rider, spawning and wandering at y180/y450, light under the dome) | main session + owner | in-game |
| 1 | B: stair, bridges, cabins, railings, lanterns, on storeys 1-3 | datapack-content-dev (generator) + world-content-dev (data) | ~8M |
| 1b | B: canopy pool split by storey, warden trainers, residents | trainer-balance-designer, then datapack-content-dev | ~4M |
| 1c | Independent audit: walk from the root ramp to storey 3 on the tree model, every edge railed, every deck lit | test-author | ~3M |
| 2 | C: the climb (storeys 4-7) and the crown sanctum, partition on `champion_cleared`; the roster moves Xerneas | datapack-content-dev; trainer-balance-designer | ~8M |
| 2b | C audit: the climb walks only one way, the partition holds, the occupant is at or under the cap | test-author | ~3M |
| 3 | D: one rip on a wild storey, after DUNGEON_DRAW is approved | datapack-content-dev | ~3M |
| 4 | A, if still wanted: the vault city | (as A) | ~18M |

Phases 0-2 come to about **35M** with audits. Phase 1 alone is about 17M, and it is the place to stop and play.

## 7. Risks common to every direction

- **Falls.** Storey 1 is ~57 above the ground and the vault ~333. Every walkway is railed. A rescue sweep (a falling
  player inside the tree's column box is returned to their last deck) is functions-rung work. The owner decides whether
  a fall stays real death.
- **Lighting.** Lanterns on posts and floors, never light blocks (`STATE.md:211`). The night crown lit up becomes the
  beacon RIFT_FRACTURE.md:127 says the tree lacks ("it glows at night when the tree is dark").
- **Spawns.**
  - Whether Cobblemon's spawner samples y180 or y450 around a player is unknown (U4).
  - Activated blocks work by placement, but birds drift off and down (no perching).
  - Any natural `ReplaceSpawns` block high in the crown risks overlapping the elders, depending on its vertical shape,
    which is unmeasured (`STATE.md:221`; `SAPLING_BIRDS.md:526-527`).
- **Build height.** y575 is the ceiling (`world.json:239`). Nothing goes above the crown's 40 blocks of headroom, and
  `cobblers_height` becomes more world-critical with every block above y319.
- **Tick.** The tree's blocks cost nothing. A settlement's NPCs, workers and nests do, and only within range of a
  player; keep to the owner's per-town limit (`STATE.md:284`).
- **Our list is not the world.** The grove's 16 nests and the cache are already at the foot. Any new canopy Habitat
  Block is checked against them, not just against its own list.

## 8. Unknowns (experiment candidates)

- **U1** (offline): the tree's real geometry from its block list.
  - Every *derived* number in sections 1-2.
  - Storey 1 against `elder_foothill_grove_2`.
  - Ring-1 balls over Route 3.
  - Also: RIFT_FRACTURE.md:56 puts the crown at (2044, 2282), 28 off the trunk centre. Which is right?
- **U2** (research): whether Cobblemon 1.8.0 can restrict riding flight by config, permission or condition; which
  species fly; from which badge the first one is catchable.
- **U3** (in game): does a zone turn back a mounted flyer, with the mount (`RIFT_ZONES.md:141`)?
- **U4** (in game):
  - natural spawning on the decks at y180 and on the crown at y450;
  - an activated Habitat Block at y450;
  - wild Pokemon walking off decks and taking fall damage.
- **U5** (in game): sky light under the dome and on storeys 1-3 under the crown's shadow (F3). *ASSUMED* dark near
  the trunk, since leaves dim light per block in vanilla.
- **U6** (in game): the rescue sweep catches a player falling from y450 before impact, mounted or not.
- **U7** (in game): `lumymon:elevator` as a trunk lift. Riding it is NOT PROVEN even in the Deep (`DEEP_CITY.md:44`).
- **U8** (research): is Xerneas's inherited DP spawn live; its hitbox against a 15-high vault.

## 9. Questions for the owner

1. **Which direction?** *Default: B now, C next, D when the rips list is approved, A only after playing B.*
2. **Is the Warden Grove back?** B is a three-storey version of what you set aside on 2026-09-21. *Default: yes, small.*
3. **A city you fly to:** should "fly only" be enforced (a zone on the gym-4 sky flag, adventure mode against
   ladders) or left soft? *Default: soft for B, the partition for C, a zone only if A is built.*
4. **Xerneas into the crown**, out of the Patriarch's band-6 pool? Or Ho-Oh, or Shaymin? *Default: Xerneas.*
5. **Falls:** a rescue that returns you to the last deck, or real death? *Default: rescue on the climb and in the
   city, real elsewhere.*
6. **The way down:** a waystone at the hamlet, a leap into a pool at the foot, or walk? *Default: a waystone on
   storey 1; the pool is a vanilla trick worth an in-game look.*
7. **A gym-4 gate west of x4000:** you kept sky portals east so nothing sits unusable for three gyms. Does a crown you
   see at badge 2 and reach after gym 4 count as that, or as a reason to come back?
