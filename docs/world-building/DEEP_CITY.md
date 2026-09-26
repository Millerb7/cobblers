# The Deep: a city across the rings, its lights, Hoopa's relic area, and the west door

**Status: design proposal, 2026-09-25. Nothing here is built, measured in a world, or decided.** It answers EXP-035
rows 19-21 (the owner's first playtest). Sources: `data/rift_deep.json` (schema 2), `tools/rift_deep.py`,
`data/rift_regions.json`, `data/rift_sculpt.json`, `data/rift_skin.json`, `docs/mechanics/RIFT_ZONES.md`,
`docs/mechanics/RIFT_FRACTURE.md` section 4, `docs/story/ARC.md`, `docs/story/FACTION.md`, `data/towns.json`,
`data/placements.json` (`rift_dig_camp`), `data/spawn_blocks.json`, `docs/world-building/WORLDGEN_FEATURES.md`.
Every coordinate is from those files; every count marked "est." is arithmetic on a circle, not a measurement.
The southern Rift (town, mega stone mine, the approach) is in `SOUTHERN_RIFT.md`.

## 1. What the Deep is for

- **Position:** after `gym8_cleared`. Players reach it from the south (G2 at the south-west tip, the approach
  through the hidden cavern, wilds, upper rift and sink) and leave it by Victory Road's caves from its floor (y1) to
  the League's apron (y89). It is the last town before the Elite Four and the stage for the finale.
- **Level band:** the level cap there is 60 (cap offset 0; the first Elite Four ace; `STATE.md`). Wild life around
  it is the Rift's 55-58 (`rift_trunk` 55-57, `rift_west_spur` 56-58); Victory Road's caves beyond are 58-64.
- **Story:** the Haven Compact's city: refugee families, the dissenters (Nia), the loyalists fortifying the HQ
  (Elara, Brann, Oren), and Hoopa held in the cradle under the relic area (`FACTION.md`; owner, 2026-09-22: the
  Compact is not evil). "A city fuelled by the Rift" (owner): the veins drain down the sink into it.
- **What the player gets:** the last Centre and Mart before the League; the finale (`rift_crisis_resolved`,
  proposed, not yet in `data/progression.json`); Hoopa's relic shrine as a postgame place; a place that shows the
  Compact as people, not a base.

## 2. The ground as it stands (read from data and code, not measured in a world)

| Part | Where | Level |
| --- | --- | --- |
| The Deep (region) | x3421-3786, z3015-3429; centre measured (3603, 3222), surface y83 | 114,180 columns |
| Rings (treads) | 36 wide each, 4-block bare-rock margin at the back, 4-block edge band at the front | y66 / y49 / y32 / y15 / y0 |
| North sector | 55 degrees either side of the line to `entrance_to_e4`: ring 0, then one 66-block face to the floor | tunnel mouth 9 x 7 at the floor |
| Lifts | `lumymon:elevator`, 2 banks per ring boundary = 8 pairs, 40 apart; ungated; none in the north sector | riding them is NOT PROVEN |
| Tread lights | `legendarymonuments:galar_particle_block` where x and z are both multiples of 13: 468 | light 15 |
| Relic area / shrine | x3285-3429, z3229-3384, the Deep's west lip | ground 86-100 |
| Hoopa's cradle (sited) | centre (3357, 3306), floor y12, 76 cover, 50 under sea level | needs a cavern shell |
| Compact HQ (sited) | (3427, 0, 3308); passage 70 blocks west, climbing 12, to the cradle | not built |
| The sink | x3509-4132, z3351-3755, south-east of the Deep: where the approach arrives | y82-120 |

**Four findings a builder must settle first:**
1. **There is no way from the Rift floor down to ring 0.** `tools/rift_deep.py` places lifts only between treads
   (lines 289-327); ring 0 lies 17 below the y83 floor round the whole pit. An arriving player drops 17. Section 4's
   lip buildings are the fix.
2. **The HQ's siting predates schema 2.** (3427, 0, 3308) was "on the floor deck" of schema 1's sealed chamber. In
   the terraced pit the column at x3427 is about 6 blocks inside the west wall (if the wall is at x3421 there; read
   it from the model), so y0 there is solid rock 66 under ring 0. It still works as the HQ's *basement* (section 6).
3. **The Deep straddles two spawn sub-regions.** Victory Road's corridor crosses `rift_west_spur` / `rift_trunk` at
   (3612, 3255) (`data/routes.json`), 34 blocks from the Deep's centre.
4. **Victory Road's surface polyline runs into the pit** at y82 over ground the pit removed. Harmless for walking
   (the approach ends in the Deep), but its spawn boxes over the pit are worth a look by the route owner.

## 3. Composition: one city, five streets, one core

The rings are the city's levels (`rift_deep.json`: "The rings ARE the city's levels"). Each tread becomes a street
between a front edge (the drop, railed and lit) and a wall of **riser buildings** 17 high standing against the next
riser up, whose roofs are the ring above. So every riser is a building face and the city reads as continuous
across all five elevations instead of five separate terraces.

```
 plan, north up (not to scale)                  z3015  entrance_to_e4 shelf (reached only by Victory Road)
            .------ R0 y66 street, then the sheer north face (66 down) ------.
           /   R0 y66                    [VR mouth y0-1]            R0 y66   \
 relic    |      R1 y49 (the Works)     .-------------.   R1 y49             |
 shrine = |  HQ    R2 y32 (the Quarter) |  CORE  y0   |   R2 y32             |
 x3285-   |  ###     R3 y15 (Relay Row) |  (spire)    |   R3 y15             |
 3429     |  ###  (west riser block)    '-------------'                      |
           \   R0 y66 (Rimside: Centre, Mart, market)          SINK GATE  <----- the approach from the sink
            '---------------------------------------------------------------'  z3429
                                                                        x3786
 section west-east through the centre (not to scale)
 y83 lip ##|RR  roof = floor                                          lip
 y66       |__R0 street__|RR                                     ...__|
 y49                     |__R1 street__|RR
 y32                                   |__R2 street__|RR
 y15                                                 |__R3__|  bridge to the spire at y15
 y0                                                         |__CORE__ [spire rising to about y100]
 RR = a riser building: ground floor on the lower street, roof on the upper one, a stair inside
```

| District | Ring | Character | Holds |
| --- | --- | --- | --- |
| **Rimside** | R0 y66, full circuit | arrival, trade, the view | Sink Gate (lip to R0), Centre, Mart, market arcades, the waystone if any, the north promenade over the 66 face |
| **The Works** | R1 y49 | the Rift's fuel made useful | vein conduits from the sink, crystal refinery halls, pylons; the city's power plant |
| **The Quarter** | R2 y32 | where the families live | dormitories, canteen, school, Nia's clinic, the Asters' home; warm light only |
| **Relay Row** | R3 y15 | the Compact's civic floor | anchor control, survey office (Tomas), signal room (Oren), the HQ's public front on the west |
| **The Core** | floor y0 | the heart and the exit | the spire, the plaza before Victory Road's mouth, the cordon round the HQ's lower door |
| **HQ block** | west sector, R0-R3 | one building down the west risers | public face on every ring; a secure shaft to the basement at y0 and the cradle passage |

**Scale, est.** (circle of radius about 190; the real outline is the owner's traced shape): street lengths R0 about
1,080, R1 590, R2 440, R3 280 (rings 1-4 cover about 250 of 360 degrees). At a 16-block frontage that is about 60
+ 33 + 24 + 15 lots, about **130 buildings** plus the spire and the HQ. A 36-wide tread leaves a 6-8 street, about
20 deep for the riser building and room for a front row of low stalls or gardens.

**The Core spire:** 15-21 across on the floor core (the core is est. 60 across), glass shell over a light column,
rising to about y100 so its top shows over the lip from the Rift floor. Bridges at y15 to Relay Row; optionally one
long glass span at y66 from the north promenade (est. 100-140 long; owner decision).

**Getting between rings:** riser buildings carry internal stairs (17 rise: a switchback in about 7 x 11), one
**stair tower** per sector beside each lift bank, and the existing lifts re-housed inside them. Stairs make the city
walkable even if the lift fails its test. Lip buildings (the Sink Gate first) take a player from y83 to R0.

## 4. The lighting system (the "futuristic" part)

The idea: **light is the Rift's energy made visible and routed.** Violet is raw Rift energy; cyan-white is the
Compact's machinery; warm is home. Looking down from the lip at night the city reads as five glowing contour
lines, vertical conduits, and one column of light at the core rising toward the sky tear 360-400 above.

| Layer | What | Block (id) | Light | Status of the id |
| --- | --- | --- | --- | --- |
| L1 street grid | existing tread lights, every 13 | `legendarymonuments:galar_particle_block` | 15 | placed on staging (R9B audit) |
| L2 contour lines | every third block of each tread's front edge | `minecraft:sea_lantern`, cap `minecraft:light_blue_stained_glass_pane` railing | 15 | vanilla 1.21.1 |
| L3 riser bands | a slot at mid-riser (y+8) along building faces | `minecraft:pearlescent_froglight` behind `minecraft:purple_stained_glass` | 15 | vanilla |
| L4 conduits | vertical channels down each stair tower, and the veins' channels from the sink across R1 | `minecraft:sea_lantern` core, `minecraft:tinted_glass` + `minecraft:cyan_stained_glass` casing | 15 | vanilla |
| L5 the core column | the spire's light column, crystal accents | `minecraft:sea_lantern`, `mega_showdown:dormant_crystal` | 15 | dormant crystal placed on staging (skin vein cores) |
| L6 beams | a beacon on the spire (and at most one per sector), coloured by glass above it | `minecraft:beacon` on a 3x3 `minecraft:gold_block` base | 15 | vanilla; beam in this pack's client NOT VERIFIED |
| L7 fixtures | building fronts, stalls, homes | `minecraft:end_rod` (14), `minecraft:lantern`, `minecraft:shroomlight`, `beautify:lamp_candelabra` | 14-15 | candelabra placed at the mansion; other Beautify lamp ids NOT READ |
| L8 holo-signs | district names, lift labels, Compact notices | `text_display` entities (background colour, billboard) | none | vanilla entity; needs a re-apply step |
| L9 motion (optional) | a pulse travelling along the R1 conduits into the core | a scheduled function swapping `sea_lantern` and `pearlescent_froglight` | 15 | tick cost unmeasured |

- **Rules it keeps:** no `minecraft:light` blocks (decided: "Places are lit as towns ... never light blocks").
  It *departs* from "lanterns on posts": the Deep's light is built into the fabric. That is an owner decision.
- **Spawn-clean check** against `data/spawn_blocks.json`: galar particle, sea lantern, froglights, end rod, glass,
  tinted glass, crying obsidian, gold block, beacon, lantern and shroomlight are named by no spawn condition.
  **Avoided:** `redstone_lamp`, `redstone_block`, `redstone_torch`, `repeater`, `comparator`, `daylight_detector`
  (Rotom); `lightning_rod` (Electrode, Galvantula); `iron_block` (Meltan, so no iron beacon bases); vanilla
  concrete (Varoom, Revavroom: use `moarconcrete:<colour>_concrete_texture`, already substituted pack-wide);
  amethyst, purple and magenta concrete, magma (the skin's own ban list).
- **Option, owner's call:** animate with redstone (copper bulbs on clocks) inside the Works only and accept Rotom
  there as the district's encounter, as the Centres' machines already do (`spawn_block_policy.json` whitelist).
- **Light targets:** 12 or more on every street and bridge cell (fightorflight calms Dark and Ghost at 12), 8 or
  more everywhere walkable; the approach outside the city stays dark on purpose. Measure with `tools/light_plan.py`,
  whose emitter table lacks `galar_particle_block` and the Mega Showdown crystals (a tool change, test-author's).
- **Materials for the buildings** (not light): `moarconcrete:white|black|gray|cyan|light_blue_concrete_texture`,
  `rechiseled:blackstone_polished_connecting`, `rechiseled:basalt_bordered_polished`, the Distortion stones, tinted
  and stained glass, waxed copper. Other Rechiseled and Mega Showdown "meteorite" ids are NOT READ from the jars.

## 5. Hoopa's relic area

**What it is:** an old native shrine on the Deep's west lip, older than the Compact. The Compact found Hoopa's
anchor here and built its cradle 76 blocks under it. The "relics" are ring fragments from Hoopa's earlier, free
visits. Rule 7 of `ARC.md` holds: the shrine adds depth; the only required way to Hoopa is through the HQ.

- **Surface (x3285-3429, z3229-3384, y86-100):** a stepped platform on the lip with six standing ring arches (7-9
  tall, Distortion stone with crying-obsidian and purple-glass inlay), a central plinth, and a terrace looking down
  over all five rings. Before the finale it is inside a Compact cordon (a fence of tinted glass and iron bars,
  lit with end rods): seen, not entered.
- **The cradle (floor y12 at (3357, 3306)):** a sealed cavern with the Displaced City's rock shell (every void
  within 24 blocks made rock; `tools/cavern_plan.py` precedent). A containment deck, a ring of anchor pylons
  (end rods, iron bars, tinted glass, sea lanterns) round Hoopa's cradle. The chamber's needs are Codex's to send
  (`HANDOVER_CODEX.md` item 26).
- **The way in:** HQ ring-0 front at x3427 -> a secure shaft down to the basement at y0 (a `lumymon:elevator` with
  `requiredAdvancement` set to an advancement the finale's dialogue grants, so the shaft is a per-player gate) ->
  the 70-block passage west, climbing 12 -> the cradle. The cradle's zone check opens on the quest stage
  (`rift_crisis_pending`), as the owner decided.
- **Hoopa itself:** a per-player actor (the scene runtime's per-player actors, proven to load on staging, not seen
  in game: EXP-034), so one player's release does not empty the cradle for another.
- **After `rift_crisis_resolved`:** the cordon stands down for that player; Hoopa appears at the shrine by choice.
  Options: (a) presence only; (b) a postgame battle or catch; (c) the shrine's ring becomes a waystone that opens on
  `rift_crisis_resolved`, Hoopa's rings used by consent. Recommendation: (a) with (c). Whether Cobblemon 1.8.0 has a
  usable Hoopa (model, Unbound form, Prison Bottle) is NOT VERIFIED.

## 6. The west door: the dig camp as a mining town, and the barrier

**The starter area.** The owner's map names the excavation site "the dig camp; a physical edge on its east side
stops new players", and the owner's intent adds "a physical edge between the excavation site and the relic area and
shrine stops new players" (`rift_regions.json`). It is the Rift's only early-game pocket (Z1, 2 badges, G1 at the
spur end (3022, 3254); `RIFT_ZONES.md`), entered by the `excavation_haul_road` landslide near (3100, 3270). The
edge was once the "throat" wall at (3384, 3502)-(3406, 3182), superseded with the rim wall and never rebuilt; it
also sat inside the relic area, which the owner's later map puts on the Deep's side.

**Findings:** the camp is a 121-square (x3046-3166, z3254-3374) with eight tents, a finds shed and two Mega
Showdown archaeological sites, in a site 358 x 114 (x2950-3308, z3213-3327); and `rift_west_spur`'s roster is at
**56-58** in a zone opened at **2 badges**. The roster is trainer-balance-designer's to re-band (about the Z1
player's cap), not this document's.

**The mining town:** the camp strung along the whole spur floor, one street about 300 long.
- **The Head (west):** the excavation, archaeological sites A and B, and the sealed steel chamber (Registeel,
  bespoke, not opened here).
- **Forge Row:** a workshop street for early crafting: crafting tables, furnaces, blast furnaces, smithing table,
  stonecutter, anvil; the finds shed's clerk. Stone and copper buildings, not timber (the owner's Craters note).
- **Ore piles and spoil heaps** along the street, built from blocks that decide nothing: `minecraft:raw_iron_block`,
  `coal_block`, `raw_copper_block`, `gravel`, `tuff`, `cobbled_deepslate`; carts as entities.
- **Five adits** into the spur walls, each a reset face on ADR-003's `cobblers_mines` pattern (fill + mandatory
  occupancy guard): coal (`coal_ore`: Rolycoly, Carkol, Coalossal), iron (`iron_ore`: Aron line, Alolan Geodude),
  the relic seam (LumyMon's type ores: features `lumymon:{dragon,electron,ice,rock,steel}_ore_placed`; block ids NOT
  READ), the particle drift (`legendarymonuments:galar_particle_ore`), and a fossil bed (suspicious gravel with
  Cobblemon's fossil loot). Real ore decides spawns: each adit needs a policy whitelist and a Habitat Block band.
- **"Rift items" an early player can make here** (chains from `WORLDGEN_FEATURES.md`, read from the Mega Showdown
  jar): the **Z-Ring** (sparkling stone from the archaeological sites + white apricorns + iron); the **Mega
  Bracelet** if the Key Stone (`mega_showdown:keystone_ore`) is placed here (owner decision; else the gulch);
  Galar particle recipes (5; outputs NOT READ); LumyMon relic uses (NOT READ); fossils. Each item also needs a
  natural source (owner, 2026-09-24): a clerk's stock or a find.

**The barrier (recommended): the Slip.** A landslide ridge across the spur floor on the excavation/relic boundary
(about x3290-3310; trace it from the two region masks, which overlap there), 24-30 above the floor, sheer on the
camp side, sculpted into the heightmap as a new stroke in `data/rift_sculpt.json` so it lands with the export and
needs no re-apply. On the relic side a down-lift (ungated) makes it **one-way**: a player who came through the Deep
can drop back to the camp. On the camp side an up-lift with `requiredAdvancement`
`cobblers:flag/rift_crisis_resolved` opens it after the finale as the postgame path to the shrine. A lift's
advancement check is per player (read from the bytecode), so the wall is physical and per-player with no teleport.
**Enforcement** is still RIFT_ZONES section 4's zone check: move the Z1/Z2 line to the ridge and put the relic area
in Z2; anyone who builds, pearls or flies over is turned back in front of the ridge.
Alternatives for what opens it: `gym8_cleared` (a western shortcut into the Deep that skips the southern approach)
or `champion_cleared`. Alternative look: a Compact checkpoint cut through the ridge, with a guard (G1b) on
`RIFT_ZONES.md` section 6's pattern.

## 7. Spawns and encounters

- The city: a spawn-free precinct over the streets (the League's pattern), or city Habitat pools per district
  (ranges of at most 28, no overlaps, active after a restart). Species are trainer-balance-designer's.
- The streets at light 12+ keep fightorflight's Dark and Ghost calm; the lip and approach stay dark.
- Water is a spawn condition for 84 species: no pools or fountains without a deliberate decision.
- The dig camp: see section 6 (ore faces decide spawns; the roster's band is wrong for its gate).

## 8. How it gets built in this repository

- **Data:** `data/deep_city.json` (new: districts, lots from the ring model, riser buildings, stair towers,
  bridges, the spire, the lighting layers), `data/towns.json` and `data/placements.json` records for the Deep and
  the enlarged dig camp, `data/rift_sculpt.json` for the Slip, `data/mines.json` for the adits,
  `data/habitat_blocks.json`, `data/progression.json` for `rift_crisis_resolved` (minecraft-systems-dev's file).
- **Tools:** `tools/deep_city.py` (new) takes the rings from `tools/rift_deep.py`'s model and ground from
  `tools/ground.py`, never from a world; emits functions into `build/`; a `verify` that compares the world with the
  plan. Riser buildings and stair towers are **generated modules** (licence `generated`); set pieces (spire, HQ,
  shrine) are owner prefabs (licence `original`) or generated; donors by resource id only, never copied. Every
  template gets a `kits/PROVENANCE.json` record.
- **Re-apply:** a new `tools/reapply.py` step after R9C (Victory Road's caves also write near the mouth) and before
  R9E (Habitat Blocks sit on finished floors): R9D is free. Entities (holo-signs) and NPCs follow the R1 and R17
  patterns. `prepare` fails closed until the step exists.

## 9. Phases

1. **Proofs first (principle 20):** a player rides a `lumymon:elevator`, gated and ungated; a `text_display`
   survives the re-apply; the beacon beam shows in this pack; the light model knows the modded emitters.
2. **Prototype slice: the Sink Gate wedge.** One sector about 60 wide where the approach arrives from the sink,
   from the lip to the floor: a lip building (y83 to R0), one riser building per riser, one stair tower around the
   existing lift bank, L1-L4 and L8 in that wedge, one Centre. Audit it, then the owner flies it at night.
3. The Core spire and its bridges; Rimside's Centre and Mart.
4. Districts ring by ring, generated modules first, set pieces as the owner builds them.
5. HQ, shaft, passage and cradle, once Codex sends the chamber's needs; then the shrine.
6. West door: the Slip (sculpt, re-measure cells and visibility) and the zone line; then the camp's expansion
   and its adits, after ADR-003's proof face.

## 10. Owner decisions

1. The lighting language: built-in light (this design) instead of lanterns on posts, for the Deep only.
2. Redstone animation in the Works with Rotom accepted, or static light plus the optional function pulse.
3. The long glass span from the north promenade to the spire: yes or no.
4. The HQ: keep (3427, 0, 3308) as its basement under a west riser block (recommended), or re-site.
5. Adventure mode inside the city (the mansion's precedent) against block theft (gold bases, glass).
6. A waystone in the Deep (a midpoint waystone, open question in `NAVIGATION.md`).
7. Hoopa after release: presence, battle or catch, and whether the shrine's ring is a waystone.
8. The barrier: the Slip with one-way lifts (recommended) or a checkpoint; and what opens it upward.
9. Where the Key Stone lives: the dig camp (early Mega Bracelet) or the gulch (`SOUTHERN_RIFT.md`).
10. The Z1/Z2 line moved to the ridge, with the relic area in Z2.

**Not verified anywhere in this document:** lift riding; a gated lift refusing a player; beacon beams; any Beautify,
Rechiseled, LumyMon ore or Mega Showdown "meteorite" id not named above as placed; Hoopa in Cobblemon 1.8.0; the
Galar particle and relic recipes; every "est." figure; the tick cost of a pulse.
