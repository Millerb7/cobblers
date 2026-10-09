# The Merian Ice Lodge

The owner, 2026-10-09: *"MERIAN HUT becomes an ICE FISHING LODGE. It sits at the major river's source, and that is what
anyone living there would actually be doing. Holes cut in the ice, shelters, gear, someone who knows the water. Connect
it to fishing for prizes if that system exists by then."*

Record `data/ice_lodge.json`; builder `tools/ice_lodge.py`; independent audit `tools/ice_lodge_audit.py`; tests
`tests/test_ice_lodge.py`; pack `cobblers_ice_lodge`; re-apply step **R18IL** (after R18CW, before R14); presence
probes `data/world_probes.json` key `ice_lodge`. Status: **written and replayed offline; not built into any world, not
seen in game.** Everything below marked ASSUMED needs the experiment in section 7.

## 1. What the hut was, and what it still is

The Merian hut is an approved batch-2 outpost: the mountain-village Pokemon Center as "the hut", a woodshed, a stable and
a cobbled apron in a row at the north end of a swept-flat cirque floor (y107), the gravel path walking 180 blocks up to
it from Route 4. This unit **adds a second cluster south of the apron and changes nothing of the first**. Consumers of
the hut's ids, each found by grep and each left alone (the test `test_the_hut_keeps_what_other_systems_rely_on` pins the
first group; `test_nothing_written_is_near_the_huts_own_buildings` pins that nothing is written within 4 blocks of any
of them):

| Consumer | Id or place | Status |
|---|---|---|
| Town footprint, plan, streets | `data/towns.json` / `data/placements.json` `merian_hut` (centre (2813, 1102), 237 square) | unchanged; the new cluster is inside the footprint |
| Centre, woodshed, stable | `merian_hut_pokecenter` (2806, 1014), `merian_woodshed`, `merian_stable` | unchanged |
| Waystone | (2800, 1034) | unchanged |
| Blackout checkpoint | `data/blackout.json` `checkpoints.ids.merian_hut_pokecenter` = 10 | unchanged |
| Market | `merian_hut_larder`, the Hut Warden at (2790, 108, 1036) | unchanged (see 5.5: a bait or rod line is NOT added) |
| Ambient Pokemon | `data/ambient_towns/merian_hut.json`: 2 workers, 1 roof Spearow, 2 situations, 6 Pokemon | unchanged; composition test untouched |
| Plaza | `data/plaza_centres.json` `merian_hut`: well (2831, 1037), lamps (2816/2838, 1035) | unchanged |
| Shrine | `merian_path_cairn` at the cirque path's foot (2820, 1212) | unchanged |
| Spawns, region, Nuzlocke zone | `surface.merian_cirque.*`, subregion `merian_cirque`, tier 4 levels 25-31 | unchanged (see 6: water) |
| Landmark | `merian`, anchor (2754, 1055) | **the lodge stands on it** (west wall x 2756); a label, not a thing, so the clearance guard exempts it |
| Quests, docs | `SQ-MERIAN-01/02`, `EVT-R4-MERIAN-DELIBIRD`, TOWN_CHARACTER.md row `merian_hut`, SETTLEMENTS.md "river's source" | **not touched; see 8** |

## 2. The premise, measured

The brief says the hut "sits at the major river's source". Measured 2026-10-09 against `data/rivers.json` and the
heightmap:

- The major river's cut course `major_river_trunk` starts at **(3132, 1632), ground y106.3**; the hut Centre's middle
  (2813, 1020) is **690 blocks** from it, the tarn's middle (2762, 1084) 661. The first reach is a 3-6 block gravel creek.
- `data/landmarks.json` `merian`: "no basin holds water inside the outline". There is no water in the cirque today.
- The cirque is the glacier's head and the river's drainage, which is what the story docs mean ("the keeper knows where
  the river starts"; `SQ-MERIAN-01` compares the cirque with the river's anchor, because they are not the same place).

So the tarn is **authored here as the cirque's own meltwater**, not read from the water data, and the keeper says so:
the creek "comes up a good walk south and east". Nothing in `data/rivers.json` changed and none of it needs to.

## 3. The place (coordinates are blocks; y is the standing y; floor y107, ice y107, water top y106)

All 1,351 tarn columns and every other written column are on y107 (checked by the builder and the audit against
`tools/ground.py`); the cirque floor is y107 at 7,241 of 7,656 columns sampled over x 2700-2930, z 1030-1160 and y108 at
the other 415, none inside the footprint.

| Piece | Where | What |
|---|---|---|
| **Merian Tarn** | two joined ellipses, centre (2762, 1084) rx 24 rz 15 and (2784, 1092) rx 13 rz 9; x 2738-2797, z 1069-1101 | 1,351 columns; 5,607 water blocks, 2 deep at the edge to 5 in the middle on a gravel bed; a lid of clear ice (980 plain-ice columns), packed ice (189: random frost patches and the shelters' diamonds) and 15 blue-ice seams |
| **The Lead** | (2751-2759, 1079-1085) | 63 columns of unfrozen water, air over it, a spruce fence ring with a gap on the boardwalk side, a plank stub (2761-2763, 1081-1083), a post and a sign: THE LEAD / open water / big fish use / this, not holes |
| **Fishing holes** | 8 stations: (2767, 1071), (2762, 1073), (2767, 1079), (2762, 1088), (2767, 1085), (2762, 1096), (2772, 1089), (2778, 1091) | one air block in the ice over water, a spruce-slab stool beside it, three with a barrel or cauldron ("bucket") |
| **Shelters** | 5 by 5 huts at (2772, 1075), (2756, 1093), (2786, 1090) | packed-ice floor, a hole in the middle, spruce walls and door, panes, a seat and a barrel, a lantern hanging over the hole; trampled white frost out to 4 blocks (a diamond) round each |
| **Boardwalk** | spine (2764-2765, 1060-1096); spurs to the three doors; porch (2760-2769, 1060-1062) | spruce planks flush with the ice: 125 columns |
| **The lodge** | (2756-2774, 1051-1059), ridge z1055 | a 19 by 9 hall: cobble course, spruce log posts, gable roof 1:1 with a smoke hole over the hearth; four bunks (three red, one blue and made up: the `SQ-MERIAN-02` bunk), fletching table, loom, composter ("bait bin"), barrels, smoker, cauldron, hearth (a lit campfire on cobble in a slab ring), five lanterns on posts, the CATCH BOARD (three signs, blank), two signs over the door (one points to the Centre) |
| **Drying racks** | (2779-2785, 1052), (2779-2785, 1056), (2790-2796, 1054) | fence posts, a stripped-log beam, chains and dried-kelp bundles; a smoking pit with a campfire at (2788, 1058) |
| **Yard** | frame (2744-2748, 1053-1057); ice stack (2751, 1053); sled (2742, 1060) | next winter's shelter, framed; cut ice stacked in packed ice under snow; a sled with two barrels |
| **The holekeeper** | Ketil Aune at (2767, 108, 1056), yaw 0 (south, to the door) | a `cobblemon:npc` with a hub conversation (section 4) |

The cluster begins 14 blocks south of the apron and 16 from the path axis, 56 blocks from the Centre's door to the
lodge's door. 9,585 blocks in one function of 1,274 commands.

**Rung (CLAUDE.md principle 6).** Blocks: *functions/commands*, the repository's established way to build an authored
place (`tools/old_orchard.py`, `tools/shrines.py`, `tools/coldwater_station.py`). The earlier rungs do not serve: Cobblemon
native and the Cobbleverse pack have no ice-fishing structure; the donor `townkit` templates carry spawn-condition
blocks and none is a frozen tarn; a datapack structure template cannot express a water body that is data (two ellipses and
a depth profile). Keeper: *datapack* (`cobblemon:npc` class and dialogue compiled by `tools/compile_dialogue.py`, the
Coldwater Station pattern). No mod, no scripting, no companion.

**Why the ice rule exists.** Vanilla ice melts on a random tick when block light at it exceeds `11 - the light it filters`
(ASSUMED from the game's source, not read from the jar). The generator keeps a light of level L at least `L - 7` blocks
(Manhattan, walls ignored) from every plain-ice cell, one under the worst reading, and uses packed ice, which does not
melt, wherever a lantern is near (the shelter frost diamonds are exactly that distance, 4, by construction). The lodge's
lanterns are 14 or more from plain ice; the nearest level-15 light to any plain ice is 8. Both the builder and the audit
refuse a build that breaks it, and a mutation test proves the audit's copy bites.

## 4. The holekeeper

`dlg_ice_lodge_keeper`, NPC class `cobblers:npc_ice_lodge_keeper`, per-player cursor `quest.ice_lodge.keeper_cursor`
(declared in `data/progression.json`, initial `hub`). A hub with eight topics: the holes, the Lead, the huts, **where the
river starts** (the creek is a walk south-east: the measured fact of section 2), cutting your own hole (a pick will; it
skins over; keep a lantern off it), the board (blank "this winter"), the made-up bunk (kept; sleep in the other three),
and the Warden. **It promises nothing**: no prize, reward, contest or quest word appears in her text, and a test fails if
one does. It reads no state and writes only its own cursor.

## 5. Fishing for prizes: what exists, what does not, the hook

**Finding: no fishing prize system exists in this repository.** Grep over `data/`, `tools/`, `docs/` found: First Cast
gives one `cobblemon:poke_rod` per player (`data/quests.json`, STATE "Early fishing balance"); Pacifidlog's Fishing Guild
is proposed with the rod master unplaced (`data/sea_town.json`); `docs/world-building/LONG_ISLE.md` section 6 says how
fishing spawns would be authored and that none is. STATE: *"Still open: the actual catch pool, Habitat Block fishing
replacement ... not runtime/balance proven"*. So, as briefed, **the place is built and the prize is a hook, NOT BUILT.**

### 5.1 What Cobblemon 1.8.0 already does (read from the jar, 2026-10-09)

- `data/cobblemon/loot_table/fishing/pokerod.json`: junk (weight 66), `cobblemon:fishing/pokerod_treasure` (17) and
  vanilla `gameplay/fishing/treasure` (17); **both treasure entries are conditioned on `cobblemon:poke_bobber` with
  `in_open_water: true`.**
- `pokerod_treasure.json`: Deep Sea Scale, Deep Sea Tooth, Dragon Scale, King's Rock, Prism Scale. The injection
  `injection/gameplay/fishing/treasure.json` adds `cobblemon:pokerod_smithing_template` at 16.7%.
- Advancement triggers `cobblemon:reel_in_pokemon` (conditions: `player`, `baitId`, and a species field) and
  `cobblemon:cast_poke_rod` (`player`, `baitId`); `data/cobblemon/advancement/catching/use_poke_bait.json` uses the first.
  (The condition class strings name `player`, `baitId`, `species`; only `baitId` is seen in a shipped JSON, so `player`
  and `species` as JSON field names are ASSUMED.)
- Spawn side: `FishingSpawningCondition` and `FishingSpawnablePosition` exist, so `spawnable_position: "fishing"` entries
  in `data/spawns.json` are the route (LONG_ISLE 6: NOT VERIFIED that boxes are honoured); Habitat Blocks carry an
  `affectsFishing` flag (EXP-021: untested).
- The Kotlin event API (`BobberSpawnPokemonEvent`, `BaitSpawnPokemonEvent`, `PokerodReelEvent` ...) is a mod's
  interface, the last rung. It is not needed below and is not proposed.

### 5.2 Why the Lead

An ice hole is one block of water in a sheet of ice. Vanilla's open-water test (from the game's source as remembered, not read here) needs a 5 by 5 area of water or air-over-
water four layers deep around the bobber; Cobblemon's bobber has its own `isOpenOrWaterAround` and `inOpenWater` (class
strings only; that it mirrors vanilla is ASSUMED). So at a hole the treasure rolls cannot pass; at the **Lead**, a 9 by 7
unfrozen patch over a 5-deep bowl, a 5 by 3 core of columns have an all-open 5 by 5 neighbourhood (the audit counts it).
The keeper says it plainly: "The little ones come to the holes. Anything that wants room goes to the Lead." The design
gives the two kinds of water two different jobs without a line of new machinery:

| Water | Catches | Prize |
|---|---|---|
| Holes (8 + 3 shelters) | the small things: fish, Pokemon of the cirque's tier-4 band, junk | none; they are the everyday loop |
| The Lead | the same, **plus** the open-water treasure rolls | the native `pokerod_treasure` items, and a once-per-player first-catch prize (5.3) |

### 5.3 The hook, by rung

1. **Native (free, nothing to build):** a Poke Rod cast into the Lead rolls `pokerod_treasure` 17 times in 100 (if the
   open-water test holds there: experiment 7.4). These items are evolution-class goods: **an economy review is needed
   before the Lead is advertised** (`tools/economy_audit.py` already counts fishing loot as an AFK source; a Lead is a
   concentrated, repeatable one, and AFK fishing exists in vanilla).
2. **Datapack, per player, once:** an advancement in the `cobblers` namespace with trigger `cobblemon:reel_in_pokemon`,
   `conditions.player` a `minecraft:entity_properties` predicate whose `location.position` is the Lead's box (2751-2759,
   y 100-110, 1079-1085) and optionally `species` and `baitId`; `rewards.loot` or `rewards.function` for the prize. An
   advancement is per player and fires once, so it is multiplayer-safe (a late joiner, a death, a disconnect: nothing to
   reset; two players at the Lead each earn their own) and cannot be farmed. This is the repository's reward pattern
   (ADR-002, `tools/rewards_pack.py`: a per-player advancement find); it would be a new reward kind there or a hand
   advancement in its own pack.
3. **Datapack, the board:** the CATCH BOARD is a world sign, so it cannot show per-player state. Per-player state goes
   through Ketil: the reward function also runs `advancement grant @s only cobblers:flag/ice_lodge_first_catch`
   (`tools/progression_pack.py` flags), and a `{"kind": "flag", "flag": "ice_lodge_first_catch"}` condition on a topic
   (compile_dialogue supports it, first used by the ferry) makes her say "chalked" for that player only. Everything the
   compiler needs exists.
4. **Turn-in (optional, also existing):** `compile_dialogue` has `held_item`/`inventory_contains`, `consume_held_item`,
   `give_item` and `grant_reward_once` (once per claim field). A "bring me the first of each fish" prize ladder (cod,
   salmon, pufferfish, tropical fish) is a few reward records and claim fields. Once-only means no arbitrage with the
   Bank's fish prices (`data/bank.json`: 10-20 each, tagged AFK).

### 5.4 What a prize would be

STATE already decided the shape: *"better rods placed at other waters later as the natural source of each"*. The Lead is
the obvious source of **one** rod, as the first-catch prize in 5.3. Which rod is **blocked** by the unresearched question
"what a rod's ball changes when fishing" (STATE); the jar lists the rods (`lure_rod`, `net_rod`, `dive_rod` ... 30-odd) but
this note chooses none. Second-best, buildable now with no research: a keepsake with no power (a cosmetic, the
source-water keepsake `SQ-MERIAN-01` already promises).

### 5.5 What would have to exist first, and what this unit does not touch

- `fishing` spawn entries over the Lead and the holes in `data/spawns.json` (cirque tier 4, levels 25-31; the level-cap
  catch block applies to a fished Pokemon like any wild one, and nothing over the cap should sit at a hole); candidate cold-
  water species belong to `trainer-balance-designer`, not here.
- the catch-pool decision and the rod research (STATE), then the economy review in 5.3 (1).
- **Not added:** a rod, bait or line at the Hut Warden's larder (`merian_hut_larder`). Its stock is audited against the
  Bank and the budget curve (`tools/markets_audit.py`); the First Cast rod is every player's; nothing here needs to sell
  one.
- A per-catch tally ("the heaviest fish this winter") has no cheaper rung than the Kotlin events (a custom mod). No written
  failure of the cheaper rungs exists; none is proposed.

## 6. State model and multiplayer

- **World state:** blocks only. The tarn, shelters and lodge are world-global and identical for every player; nothing
  reads or writes a score, storage or tag. The Lead cannot be "used up".
- **Per-player state:** one dialogue cursor (`quest.ice_lodge.keeper_cursor`). It gates nothing and always opens at the hub.
  A player who joins late, dies, disconnects mid-conversation or arrives in any order sees the same hub; two players at
  the lodge read their own.
- **Players cutting ice:** a pick breaks an ice cell (ASSUMED: it becomes water over water and may freeze over again in
  a cold biome); nothing depends on any cell staying ice. A cell broken beside a lantern is the player's choice.
- **Re-export:** the pack is regenerated by `prepare`, installed, and R18IL rebuilds it and re-places Ketil over RCON
  (the step skips a keeper already standing there). Water and ice are plain blocks; no entity but the NPC is created.
- **Water spawns (the one place this can touch the encounter design):** `minecraft:water` is named by 84 spawn entries
  (`data/spawn_blocks.json`: Golduck, Poliwag, Politoed, Bidoof and others), so `data/spawn_block_policy.json` carries
  an entry scoped to `ice_lodge` allowing exactly water. Whether the cirque's cold biome admits any of them, and
  whether anything spawns under ice, is unknown; the tarn is 14+ blocks from the apron and 16 from the path, so a wrong
  guess costs a Golduck under the ice, not a crowd at the door.

## 7. Verified, not verified, and the experiment

**Verified offline (2026-10-09):** the builder's guards (flat floor, water containment, keep-clear boxes, palette,
spawn conditions, the melting rule, nothing within 6 of another file's x/z); the audit's replay of the written function
(its own parser, 9,585 blocks) clean, with 9 generator mutations caught by the intended check; `validate_data` 0 errors;
contract C4 (no unapproved spawn condition; no concrete) and `test_ground_rule`, `test_id_authorship`,
`test_progression_pack` green; the premise numbers in section 2.

**NOT verified, needs a server (a staging run of R18IL, no live world):**
1. the 29 presence probes (`presence_audit.py --only extra`, key `ice_lodge`) over RCON;
2. walking: the boardwalk is not slippery, the ice is; doors open; the lodge reads as a lodge from the path;
3. ice persistence: leave a test lantern 3 blocks from a plain-ice cell and the real ones alone for 20 minutes; this
   calibrates the melt threshold (ASSUMED `> 11 - filtered light`);
4. fishing with a Poke Rod: 100 casts at a hole and 100 at the Lead; record whether any treasure rolls at the holes and at
   the Lead (the open-water test), and that `cobblemon:reel_in_pokemon` fires (the datapack hook's trigger);
5. water spawns: stand at the tarn at night and by day for 20 minutes, count what spawns in or near the water;
6. Ketil: renders, faces the door, all eight topics, cursor per player, no double on a second R18IL run;
7. breaking an ice cell with a pick; whether it re-freezes.

## 8. Collisions and open questions

- **`SQ-MERIAN-01/02` and TOWN_CHARACTER / SETTLEMENTS.** They give "the hut keeper at (2813, 1102)" and "the river's
  source". The first is the town's centre point, not a seat, and no keeper exists; Ketil is the natural holder, but moving
  the quests is the owner's call. Two lines in TOWN_CHARACTER.md (row `merian_hut`) and SETTLEMENTS.md ("an alpine hut ...
  at the major river's source") now overstate the data and are left as written.
- **`docs/world-building/AMBIENT_TOWNS_A.md`** says Merian has no NPC the apply places. It now has one, outside
  `data/npc_seats.json` and `data/markets.json`; the ambient pet rule keys on those, so its counts do not move (read, not run).
- **The Hut Warden and Ketil** are two NPCs 40 blocks apart; the Warden has the Centre and the larder, Ketil the water.
- **Style:** the donor mountain set (Centre, woodshed, stable) and this cluster (spruce, cobble, packed ice) share a
  palette; whether the hut's "swept-flat snowfield" now reads as busy is a look-in-game question.
