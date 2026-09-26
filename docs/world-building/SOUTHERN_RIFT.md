# The southern Rift: its town, the mega stone mine, and the approach to the Deep

**Status: design proposal, 2026-09-25. Nothing here is built, measured in a world, or decided.** It answers EXP-035
row 22. Sources: `data/rift_regions.json`, `data/rift_sculpt.json`, `data/routes.json` (`victory_road`),
`data/spawns.json` (the Rift sub-regions), `docs/mechanics/RIFT_ZONES.md`, `docs/mechanics/RIFT_FRACTURE.md`
sections 3-4, `docs/world-building/WORLDGEN_FEATURES.md` (the Mega Showdown 1.0.2 item chain, read from the jar),
`docs/mechanics/EVOLUTION_STONES.md` and ADR-002/ADR-003 (reward and reset-face patterns), `docs/story/ARC.md`,
`docs/story/FACTION.md`. The Deep, Hoopa's relic area and the dig camp are in `DEEP_CITY.md`.

**The wild-Mega question is open.** Another agent is researching whether a wild Pokemon can be in Mega form,
uncatchable and aggressive. This design works either way (section 4); every place that depends on the answer is
marked **[MEGA-DEP]**.

## 1. What the southern Rift is for

- **Position:** the first stretch of the Rift on the critical path. After `gym8_cleared`, Victory Road drops into
  the south-west arm at G2 (the warden, 8 badges) and walks about 2,670 blocks inside the Rift to the Deep.
- **Level band:** the cap after gym 8 is 60 (cap offset 0; the first Elite Four ace). The rosters on the way are
  `rift_south_west_arm` 53-55, `rift_south_east_arm` 54-56, `rift_trunk` 55-57 (`data/spawns.json`).
- **Story:** after Giovanni the Compact's split is public; the dissenters "provide the route and shutdown knowledge
  needed at the Rift" (`FACTION.md`). The southern town is where the player meets them inside the Rift. The gulch's
  crystal is what fuels the Deep ("a city fuelled by the Rift"), hauled north along the approach.
- **What the player gets:** the last Centre and Mart for 1,800 blocks; the mega stone mine (raw mega stones, the
  Key Stone if placed here, one mega stone per chamber); a hard optional dungeon at the end of the game.

## 2. The ground as it stands (read from data, not measured in a world)

| Part | Where | Ground |
| --- | --- | --- |
| Hidden rift cavern (the south-west arm) | x3658-4125, z4574-5079 | 83-114 |
| Mega stone mine / the gulch (the south-east branch) | x4039-4454, z4513-4958 | 83-110 |
| Rift wilds | x4064-4360, z4140-4547 | 83-112 |
| Upper rift | x3971-4368, z3672-4155 | 85-121 |
| The sink (drains into the Deep) | x3509-4132, z3351-3755 | 82-120 |
| SW arm tip / SE branch tip / the split | (3738, 5082) / (4390, 4894) / about (4180, 4745) | floor y82-89 |

| Entrance (`rift_sculpt.json`) | Near | Kind | Guard (placeholder) |
| --- | --- | --- | --- |
| `victory_road_descent` | (3738, 5082) | switchback, 4 legs | Victory Road warden (G2, 8 badges) |
| `gulch_mouth` | (4240, 4740) | canyon, gap 44, 7 wide | Gulch lookout |
| `wilds_slip` | (4200, 4300) | landslide, 5 wide | Wilds ranger |
| `rim_post_descent` | (3877, 3824) | switchback, 5 legs | Rim post guard |

**Victory Road's corridor** (`data/routes.json`): enters `rift_south_west_arm` at (3577, 5339) at 1,146 blocks,
crosses into `rift_south_east_arm` at (4076, 4653) at 2,039, into `rift_trunk` at (4110, 3807) at 3,051, and
reaches the Deep at about 3,816.

**Findings a builder must settle first:**
1. **`gulch_mouth` opens into Victory Road's zone, not the gulch's.** RIFT_ZONES' branch-mouth line runs
   (4373, 4691)-(4196, 4927). By the sign of the cross product, (4240, 4740) and the split lie on the same side
   of it, and the branch tip is on the other side. This is arithmetic on the two records, not measured on terrain.
   So as the data stands, the Gulch lookout guards a second way into Z2, and the gulch region straddles Z2 and Z3.
2. **Z2 has four entrances in the sculpt and one guard in RIFT_ZONES.** The rim post descent, wilds slip and gulch
   mouth all come down into the stem or trunk (Z2). Each needs an 8-badge guard, or the zone check alone turns
   players back.
3. **Z3's gate and its roster disagree.** Z3 (60 species caught) is "a mid-game reward for collecting", reached
   about the fifth gym, but `rift_south_east_arm` spawns at 54-56. With enraged Megas added, it is late-game content.
4. The rim wall and the cross-walls of RIFT_ZONES section 5 are superseded and unbuilt; only the sculpt's scarps and
   the zone check (section 4) separate the zones.

## 3. The southern town (working name: Gulch Junction)

**Site window (recommended): the junction.** Where Victory Road passes from the arm into the stem, (4076, 4653),
to the split, about (4180, 4745). The town stands on the critical path, the mine opens from its back street, and
the long walk north starts at its gate. No square has been searched yet: run the search that wrote the
`data/towns.json` footprints (largest square under 10 degrees, 24 clear of water) over that window, for a
121-square (outpost scale) and a 181-square (major). If nothing flat enough exists, the pad pattern
(`tools/press_pads.py`) is the fallback. Alternatives: at the descent's foot inside (3738, 5082) (the first thing
past G2, but 900 blocks from the mine), or the owner's "hidden" reading: a town inside a cavern in the arm's wall
(`tools/cavern_plan.py`, the Displaced City's precedent; the most expensive).

```
                 north: the stem -> wilds -> upper rift -> the sink -> the Deep's Sink Gate
                               ^
                               | haul road (crystal carts, Compact survey posts)
   descent G2                  |
 (3738,5082) ==VR==> [ hidden cavern / SW arm ] ==> GULCH JUNCTION ==mine gate==> THE GULCH (SE branch)
                                                  (4076,4653)..(4180,4745)         garden on the floor,
                                                                                   the mine beneath it
                                                                                   tip (4390,4894): G3
```

| Quarter | What | Notes |
| --- | --- | --- |
| The Gate | Centre, Mart, the waystone if any, a notice wall | the plaza on Victory Road |
| Crystal Yard | the company's sorting sheds; displayed crystal behind glass | display with `mega_showdown:dormant_crystal` (placed on staging in the skin), never a mineable face |
| Rock Row | bunkhouses and a canteen cut into the arm's wall | deepslate, tuff, Distortion stone and copper; no timber houses (the owner's Craters note); donors re-materialed as the Displaced City's were |
| The Dissenters' camp | Nia's tents and a field clinic | the story beat's place; dialogue is Codex's |
| The Mine Gate | the company office and the gate into the gulch | where the mine's own gate check stands (section 4) |
| The Haul Road | rail-less cart road leaving north | rails decide spawns (Carkol, Coalossal): carts as entities on a stone road |

## 4. The mega stone mine (the gulch)

The south-east branch, about 290 long below the split, floor about 80 wide, 27-32 deep: "the crystal garden:
Distortion trees and crystal outcrops" (`RIFT_FRACTURE.md`); "Mega Showdown's meteorite blocks belong here" (owner).

**Surface: the Crystal Garden.** Distortion trees (`legendarymonuments:distortion_log` and `distortion_leaves`,
named in RIFT_FRACTURE, not yet placed anywhere: ids NOT READ from the jar), crystal outcrops, and a
**megaroid impact** (`mega_showdown:megaroid`, 13 x 14 x 13, placed by resource id, holding `keystone_ore`) if the
owner puts the Key Stone here rather than at the dig camp.

**Underground: the Mine.** A cave network under the branch floor, modelled like Victory Road's
(`tools/vr_caves.py`: ragged caverns, wandering galleries, cover of at least 4, every face sealed, fluids bounded,
a walk-out search from the gate that reaches every chamber with no traps), falling 40-60 below the floor.

| Zone | What | Encounters |
| --- | --- | --- |
| Adit Hall | the company's works: timber-free supports in copper and basalt, carts, the tally office | Habitat tiles of the arm's band |
| The Galleries | loops and side drifts; **crystal faces** of `mega_showdown:mega_stone_crystal` (raw mega stones) on ADR-003's reset pattern | the band 56-60, darker toward the chambers |
| Mega Chambers (5-6) | dead-end chambers, each a crystal heart and one **Enraged Mega** | one guardian each, [MEGA-DEP] |
| The Heart | the deepest chamber, the strongest guardian | optional postgame (`champion_cleared`), owner's call |

```
 section along the branch (not to scale)
 floor y83-89   Mine Gate__ Crystal Garden ~~~ megaroid ~~~ outcrops ~~~ ___ tip (G3)
                   |
 y60-70            Adit Hall ==== galleries ==== galleries ==== galleries
                                 |        |          |          |
 y40-50                        [ch 1]   [ch 2]     [ch 3]    [ch 4]..[ch 6]
 y25-35                                                  [ The Heart ]
```

**The Enraged Megas: one geometry, three mechanisms.** Every chamber record carries
`guardian: {species, level, mode}`, with `mode` one of the three below; the rock, light and rewards do not change
when the mode does. Species and levels are trainer-balance-designer's.

| Mode | How | Uncatchable | Enraged | Depends on |
| --- | --- | --- | --- | --- |
| `wild_mega` | a chamber Habitat Block whose one-entry pool carries the Mega form and an uncatchable property; respawns naturally | by a property | fightorflight: aggressive wild Pokemon attack unprovoked in the dark; chamber kept at light 7 or less | **[MEGA-DEP]** a spawnable Mega form in Mega Showdown 1.0.2; an uncatchable property in Cobblemon 1.8.0; the species being aggressive in `fightorflight.json5`: all NOT VERIFIED |
| `trainer_echo` | a persistent RCT trainer styled as a crystal-bound husk, one Pokemon holding its stone; battles on sight with a sight radius tuned to the chamber (the mansion Channelers' method) | by construction: a trainer battle | battles on sight, cannot be avoided in the chamber | that an rctapi trainer Mega Evolves in battle with Mega Showdown 1.0.2: NOT VERIFIED, one experiment |
| `outlier` | the species at the top of the band as a `data/sizes.json` notable individual, not in Mega form; the Mega is only the reward | no | darkness, as above | nothing new (floor) |

- **Why enraged, in the fiction:** the gulch's crystal forces Mega Evolution on the Pokemon that live near it, as
  the Compact forces Hoopa. It stays a place's condition, not a required fact (ARC rule 7).
- **Level above the cap** is allowed for a wild guardian (the cap stops experience only); rctmod refuses a battle
  when the *player's* party is over the cap, which does not constrain a trainer echo's own level.

**Rewards and the per-player rule.**
- `trainer_echo` gives a per-player win (rctmod's defeat count -> our flag advancement), so each chamber can give
  that species' mega stone **once per player** through ADR-002's advancement spine.
- `wild_mega` cannot: "there is no per-player way to know one wild Pokemon was beaten" (`STATE.md`). There the
  guardian *guards* the reward: the crystal heart behind it is a location advancement (reaching it, not winning).
- Raw stones come from the crystal faces: raw `mega_stone` + a type item + iron + a diamond crafts a specific stone
  (`WORLDGEN_FEATURES.md`, read from the jar). Drop count, tool tier and Fortune behaviour of
  `mega_stone_crystal` are NOT VERIFIED.
- The Key Stone (`keystone_ore`, megaroid) + white apricorns + a diamond + iron crafts the Mega Bracelet. Every
  Cobblemon item needs a natural source too (owner, 2026-09-24): the town's clerk or a reward must carry the
  bracelet and the stones for a no-crafting run.

**Multiplayer.** A wild guardian is one shared entity: when one player beats it, it is gone for everyone until the
pool spawns another. A trainer echo battles one player at a time; the others wait at the chamber mouth, and the
sight radius must not reach the gallery. Crystal faces are shared world state: ADR-003's reset with its mandatory
occupancy guard, never while a player stands in the face box. A per-player "calm after the finale" is possible only
with trainer echoes; wild guardians could only calm for everyone at once.

**The gate into the mine (owner decision).** Recommended: the mine is entered only from the town's Mine Gate, in
Z2 (8 badges), and G3's tip entrance leads only into the surface Crystal Garden (Z3, 60 species) with the mine's
lower adits sealed from that side. That keeps the garden as the collectors' mid-game pocket RIFT_ZONES wanted and
puts the Megas at the end of the game. Z3's roster (54-56) would then need a mid-game re-band.

## 5. The approach north (hidden cavern -> wilds -> upper rift -> sink -> the Deep)

"The walk ... becomes the approach, with wild encounters and no trainers" (`RIFT_FRACTURE.md` section 4). Light
touches only, because it is 1,800 blocks and principle 20 applies:
- **The haul road** from the Junction north to the Deep's Sink Gate: a stone cart road, the physical thread that
  says where the crystal goes. Graded on the heightmap, never on a world.
- **Compact survey posts** every 300-400 blocks: an `end_rod` on a tinted-glass post with a `text_display` notice,
  the Deep's light language arriving before the Deep does.
- **One shelter** in the upper rift; the rim post (3814, 3791), with its Centre, sits above the fork.
- The approach stays dark: fightorflight's night is the danger here, as decided.

## 6. Spawns

- The corridor's pools are compiled (`tools/compile_spawns.py`) and the Rift biome tag carries them. The mine adds
  Habitat tiles (ranges at most 28, never overlapping, active after a restart; `data/habitat_blocks.json`).
- **Blocks that decide spawns and are kept out:** rails (Carkol, Coalossal), coal and iron ore (Rolycoly line;
  Aron line, Alolan Geodude), `redstone_*` and repeaters (Rotom), `lightning_rod`, `iron_block` (Meltan), vanilla
  concrete, amethyst, magma, and water outside a designed pool. `mega_stone_crystal`, `dormant_crystal` and
  `keystone_ore` are named by no spawn condition in `data/spawn_blocks.json`.
- Seams between Habitat tiles fall back to the pack's own cave pools (Victory Road's lesson): cover the floors.

## 7. How it gets built in this repository

- **Town:** a `data/towns.json` record (new id, measured by `tools/measure_towns.py`), a plan in
  `data/placements.json` (`tools/town_plan.py`, `tools/place_town.py`, audited by `tools/town_audit.py`), re-applied
  at R8 and its donors at R9, lights at R16, NPCs at R17.
- **Mine:** `data/gulch_mine.json` + `tools/gulch_mine.py` (new, on `tools/vr_caves.py`'s model and checks), ground
  from `tools/ground.py`; a new `tools/reapply.py` step (`prepare` fails closed without one); crystal faces in
  `data/mines.json` (ADR-003's `cobblers.mines/1`, unwritten); guardians as `data/spawns.json` pools (wild) or
  `tools/route_trainers.py` trainers (echo); rewards in `data/rewards.json` (ADR-002).
- **Kits:** donors by resource id only (megaroid, Repurposed Structures houses), never copied; generated modules
  under licence `generated`; owner prefabs under `original`; every template in `kits/PROVENANCE.json`.
- **Dependency flag (`.claude/rules/world-critical.md`):** Mega Showdown's blocks are already in the world (the
  skin's vein cores, the dig camp's archaeological sites) and this mine adds crystal faces and a megaroid, but
  `CLAUDE.md` does not list Mega Showdown as world-critical (the inventory says gameplay-critical; the overlay pins
  1.0.2+1.8 pending a functional test of its persistent blocks). Before the mine is built, dependency-auditor should
  record it as world-critical, with an ADR note.

## 8. Phases

1. **Answers first:** the wild-Mega research; one experiment on a disposable world for a trainer echo that Mega
   Evolves; what a `mega_stone_crystal` drops and at what tier; a player rides a gated `lumymon:elevator` (the
   Deep's dependency too).
2. **Prototype slice: one chamber.** The Mine Gate, 60-80 blocks of gallery with one crystal face, and one Mega
   chamber whose guardian can be switched between modes by data. Audit, then the owner plays it.
3. The Junction: search, plan, place, audit; the four Z2 guards and the zone line.
4. The full mine; the Crystal Garden; the megaroid.
5. The approach dressing, last.

## 9. Owner decisions

1. The town's site: the junction (recommended), the descent's foot, or inside a hidden cavern.
2. The mine's gate: Z2 via the town (recommended), Z3 at the tip, or the split (garden Z3, mine Z2).
3. The guardian mode once the research lands, and whether guardians sit above the cap of 60.
4. Mega stones as chamber rewards (per player, echo mode only) or from crafting only.
5. Where the Key Stone lives: here or the dig camp (`DEEP_CITY.md`).
6. Guards for the rim post descent, the wilds slip and the gulch mouth (8 badges), or zone check only.
7. The Heart as postgame (`champion_cleared`) or part of the main mine.
8. Names for the town and the regions (`HANDOVER_CODEX.md` item 26 asks too).

**Not verified anywhere in this document:** any wild Mega mechanism; an uncatchable property; fightorflight's
aggressive list; an RCT trainer Mega Evolving; `mega_stone_crystal` drops; the Distortion tree ids; any flat site
at the junction; the cross-product finding on real terrain; every distance not quoted from a data file.
