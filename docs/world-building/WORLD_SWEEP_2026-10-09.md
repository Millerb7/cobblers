# World sweep, 2026-10-09: what a player can find, where, and where the map is empty

The owner, 2026-10-09: *"Go through every event, encounter and place a player can find. What is built, what is
broken, what is thin, and where the gaps are on the map. Then fill the biggest gaps."* This document is the sweep and
the gap map; builders fill the gaps from section 7.

## 1. Method, and what it is not

- **Enumerated from `data/`, not from prose.** Every coordinate below was read from the named data file; the cell is
  `col = floor(x / 1024) + 1`, `row = "ABCDEFGH"[floor(z / 1024)]` (`data/cells.json` bounds). Status comes from
  `docs/STATE.md` (line numbers given), `docs/HANDOVER_SESSION.md` and `docs/OVERNIGHT_REVIEW_2026-10-06.md` (N-numbers).
- **Hand count, no tool run.** This unit had no shell, so nothing was computed by `tools/south_density.py` or
  `tools/ground.py`. The counts are one per *site* a player walks to (a town, a place, a resident's ground, a
  legendary site, a den, a portal, a shrine, a dungeon), not the tool's per-32-block points, so they are not comparable
  with `SOUTH_DENSITY.md`'s 945. Land fraction per cell is `data/cells.json` `terrain.land_fraction` (measured on the
  canonical heightmap `d1bc68d3...` by `tools/cell_stats.py`). Straight-line distances are computed by hand from data
  coordinates. **No ground height in this document is measured**; every builder brief says what to measure first.
- **Not counted** (CLAUDE.md "Our list is not the world"): route trainers (counted per route in section 2 instead),
  gym juniors and training grounds (inside gym towns), the 48 elder trees and their nests (listed per cell as
  "elders"), signposts, town NPCs, traders, ambient Pokemon, caches inside places, the wild spawn tables and their
  28 hearts (a table, not a point), what donor templates and mods place.
- **Coming tonight** (relayed from the brief, nothing measured): a swamp den, a Lake Tilpey monster and cave, Tilpey
  spawns, Mushroom Island (Fungal Isle) life, a reason for Sunset Island, a Frostpeak Strand castle, the Merian ice
  fishing lodge. Counted as coming in section 5, not as built.

## 2. The critical path and its badge bands

Route endpoints and transitions are `data/routes.json` (`computed_walked_blocks`, transition `at` points); caps are
gym N's ace (`docs/mechanics/ENCOUNTER_DESIGN.md:22`). Trainers: Routes 1-3 from STATE:104 (relayed), Routes 4-8 counted
from `data/late_route_trainers.json` ids, Victory Road from STATE:104. Route events: STATE:98 and `data/quests.json`
`evt_route*` ids; no `route_04`-`route_08` id appears in `data/scenes.json`, `quests.json`, `rewards.json` or
`dialogue.json` (grep, 0 matches).

| Band (badges) | Cap | Leg | Walked blocks | Cells crossed | Trainers | Route events |
| --- | --- | --- | ---: | --- | ---: | ---: |
| 0 | 20 | Route 1, Pallet (1462, 5293) to Brock (1743, 3628) | 1,978 | F2, E2, D2 | 13 over R1-3 | 4 + the Gastly escort |
| 1 | 25 | Route 2, Brock to Misty (1605, 2801) | 944 | D2, C2 | (above) | 3 |
| 2 | 30 | Route 3, Misty to Surge (1688, 1410) | 2,120 | C2, B2 | (above) | 3 |
| 3 | 35 | Route 4, Surge to Erika (4309, 1555) | **3,453** | B2, B3, B4, B5 | 6 | **0** |
| 4 | 40 | Route 5, Erika to Koga (4646, 2446) | 1,051 | B5, C5 | 4 | 0 |
| 5 | 45 | Route 6, Koga to Sabrina (6196, 3398) | 1,944 | C5, C6, D6, D7 | 5 | 0 |
| 6 | 50 | Route 7, Sabrina to Blaine (6074, 4995) | 2,061 | D7, E7, E6 | 6 | 0 |
| 7 | 55 | Route 8, Blaine to Giovanni (3647, 6497) | 3,050 | E6, F6, F5, (F4), G4 | 7 | 0 |
| 8 | 60 | Victory Road, Giovanni to the League (3694, 2430) | 4,363 | G4, F4, E4, D5, D4, C4 | 10 | the Abandoned Cut |

Route 4 is the longest leg before Victory Road and carries one trainer per 575 blocks and nothing else. The route
event pattern (`tools/route_events.py`, R12) stops at Route 3: **11,559 walked blocks of Routes 4-8 have trainers and
signposts and no event.**

## 3. Everything findable, by cell

Gate = the flag that opens the catch or the fight (data file named). Status codes: **A** built and applied to staging
(STATE says so); **B** built, not applied; **D** designed only; **X** broken (a recorded defect); **T** thin (stands,
little to do). Cells with land under 40% and nothing on them are left out (sea).

| Cell | Land | On path | What is there (x, z), gate, status |
| --- | ---: | --- | --- |
| A1 | 0.79 | no | Frostpeak camp (688, 688) A; Articuno's summit tower (672, 369) A, feather from Shrew Station at gym8 (STATE:240). *Coming: Frostpeak Strand castle* |
| **A2** | 0.69 | no | **nothing.** The Tri Peaks landmark (1310, 882) (`data/landmarks.json`) stands here, 0 sites |
| A3 | 0.56 | near R4 | The Scar, ruined city (2110, 950) A, T (story change open, STATE:280) |
| A4 | 0.52 | no | dive portal `dive_tarn_bottom` (3388, 916) A, T (a chest or nothing by rule) |
| A6 | 0.70 | no | Crown Spire, hidden Glastrier (5368, 505): scheduled (`adopted_legendary_sites.json:673`), not confirmed in staging. 3 elders |
| A7 | 0.24 | no | Whiteback (7050, 308), ungated, uncatchable A |
| A8 | 0.69 | no | Dawn tower (7480, 316), champion A |
| B2 | 1.00 | yes | Surge's town (1688, 1410) A; Ursaluna den (1504, 1414) A, fight ungated, catch gym6 (`ursaluna_cave.json:127`); shrine (1699, 1501) A; Seaward Drift (1455, 1795) A |
| **B3** | 1.00 | **R4** | Merian hut (2813, 1102) A, **T** (its written purpose, SQ-MERIAN-01/02, is not built: STATE:279); shrine (2820, 1212) A. 1 elder. *Coming: Merian ice fishing lodge* |
| B4 | 1.00 | R4 | Displaced City (3366, 1755) A, T (no Centre or Mart, two stalls; interiors bare: STATE:345, N26); Ridgejaw (3520, 1552) gym4 A; Regigigas portal (3560, 1760) gym8 A; `dive_peak_pond_floor` (4068, 1480) A, T |
| B5 | 0.96 | yes | Erika's town (4309, 1555) A; Crown Cemetery + Spectrier cap (4118, 1982) A; Pip's gym (4608, 1728) A (inferred, see 4.4); `sky_downs_crag` (4530, 1951) gym4 A, T |
| B6 | 0.51 | no | Red Rail (5541, 1703) gym5 A; Coldwater Station (6050, 1843) A, **T by design** (a Kyogre lead to a sealed arch with a stub destination, `coldwater_station.json:17,54`). *Coming: the swamp den may land here or in C6* |
| B7 | 0.52 | no | the Lopunny superfan's house (6950, 1360) A |
| B8 | 0.46 | ferry | Northlight (7265, 1556) A |
| C1 | 0.53 | no | Shrew Station (about 456, 2812) A, four events; the Eon shrine's dews are held (STATE:240) T |
| C2 | 1.00 | yes | Misty's town (1605, 2801) A, **X** (N82: the gym-2 island floats ~20 blocks, the only way in the exposed well; may be closed by this branch's gym-arena work, not checked); `dive_viltri_floor` (1652, 2996) A; Agnes Merrow's carving (1696, 2224) A; shrine (1700, 2877) A; the world tree (2016, 2280), one Route 3 cache at its roots (`rewards.json` `r3_world_tree_roots`) and nothing up it (the Warden Grove set aside, STATE:269). 2 elders |
| **C3** | **1.00** | beside R3 | **nothing.** 3 elders. Route 3 runs at x1809-2014 (`routes.json` transitions), the cell starts at x2048 |
| C4 | 1.00 | VR end | the League (3694, 2430) A; Regice portal (3900, 2050) gym6 A; the Abandoned Cut's Digger (3638, 2643) A |
| C5 | 1.00 | yes | Koga's town (4646, 2446) A; Giratina's shrine (4374, 2862) champion A; shrine (4509, 2303) A |
| C6 | 1.00 | R6 | Azelf grotto (5158, 2166) gym5 A; the Wandering Stone + Heave (5264, 2690) gym5 A; `sky_marsh_horn` (5450, 2661) A, T. *Coming: swamp den (Marshy Marsh is here)* |
| **C7** | 0.59 | no | **nothing** |
| D1 | 0.60 | no | the sea cave walked into at S0, mouth (376, 3503) A. 1 elder |
| D2 | 1.00 | yes | Brock's town (1743, 3628) A; Wiremother (1138, 3610) gym3 A; Hesketh Fell and Old Knot (1600, 3280) gym1 A; shrine (1609, 3767) A |
| D3 | 0.98 | no | the tea town (2654, 3605) A; `dive_shrew_pit` (2856, 3960) A |
| D4 | 1.00 | VR | the dig camp (3106, 3314) A; the rim post (3734, 3951) A; the Deep's city with the HQ tower (about 3386, 3300) A, **T** (196 buildings, interiors empty and labelled for Codex, STATE:274); Heaven's Arena (3586, 3164) A; Hoopa's relic hall (3390, 3262) and cradle (3357, 3306) A; Abomasnow Mega den (3944, 3904) A |
| **D5** | 1.00 | **VR** | Registeel's portal (4195, 3896) gym7 A. The Rift trunk; "the empty Rift floor" (N121 item 7) |
| D6 | 0.75 | R6 | Uxie grotto (5714, 4079) gym7 A; Cassius Rook's high seat + the Tilpey Hart (5480, 3196) gym6 A. *Coming: Lake Tilpey monster and cave, Tilpey spawns* |
| D7 | 0.90 | R6/R7 | Sabrina's town (6196, 3398) A; Tam's home base (6700, 3710) and Lettie's hollow (6752, 3660) A; River Grip (6970, 3970) gym7 A; the Route 7 bridge (6632, 3904) A |
| E1 | 0.39 | no | Viltri Light (550, 4518) A; Old Jaw (613, 4306) gym1 A; the Windward Sink (318, 4580) A |
| E2 | 1.00 | R1 | the Route 1 mansion and Gastly escort (1630, 5034) A; the old mine (1332, 4120) A; **the Night Shift dungeon rip (1350, 4117)**, a placeholder spine on this branch (`dungeons.json:175-202`) B; the sapling Celebi (1375, 4625) A, wake gym8 D; Route 1's events A |
| E3 | 0.98 | no | Mesprit grotto (2790, 4606) gym3 A. Otherwise empty |
| E4 | 1.00 | VR | the Mega field (27 dens, x3632-4166 z4588-5358, into F4) A, **X** (18 dens short of members, STATE:19); Tyranitar den (4080, 4168) A; Victory Road's caves A |
| E5 | 1.00 | near VR | the gulch mine (about 4362, 4800) gym6 A, **X** (three cove probes disagree with the build's z, STATE:51); Aggron (4528, 4416), Pinsir (4576, 4680), Manectric (4608, 4944) dens A |
| E6 | 0.68 | yes | Blaine's town (6074, 4995) A; `dive_tilpey_gate` vault (6076, 4296) A |
| E7 | 0.89 | R7 | the gorge hamlet (6814, 4367) A, T; `sky_gorge_shoulder` (6630, 4667) A, T |
| E8 | 0.33 | no | Post Fourteen + Ash (7856, 4704) gym7 A |
| F1 | 0.77 | no | Grandmother Cap's ring (608, 5888) gym3 A; Zapdos tower (881, 5569) A; Newmoon Island, Darkrai (24, 5582) champion A. *Coming: Mushroom Island life* |
| F2 | 0.65 | yes | Pallet (1462, 5293) A (Hank and Lena not seated, STATE:106); Relic Island (1092, 5532) A |
| F3 | 1.00 | no | the apricorn farm (2068, 5570) A; the prospector camp (2432, 5696) A; Kraal Number Three (2808, 5760) A; `dive_watering_hole_floor` (2958, 5235) A |
| F4 | 1.00 | VR | the Pokemon farm (3149, 5714) A; the Challengers' Cairn (3556, 6113), the Surveyors' Benchmark (3706, 5700) (applied, inferred: 4.4); the Drovers' Hollow (3990, 6030) A; the Rift surveyor (3552, 5334) A |
| F5 | 1.00 | R8 | the Tableland stop (4876, 5729) A; the fossil dig (4183, 5623) A; the Dry Cistern (4524, 5846) (inferred A); shrine (4765, 5622) A; Regirock portal (4800, 5200) gym4 A; Hornwall (4148, 5872) gym8 A; Houndoom (4488, 5216) and Garchomp (4248, 5328) dens A |
| F6 | 1.00 | R8 | the Four Chimneys (5176, 5968) A; `sky_tableland_head` vault (5601, 5632) gym4 A |
| F7 | 1.00 | no | the Mining Town (6633, 5716) A; Groudon portal (6672, 5508) gym8 A; Moltres tower (6252, 5344) A; Dustback (6244, 6112) gym8 A; `sky_assay_tor` (7007, 5834) A |
| **F8** | **0.81** | no | **nothing.** 2 elders |
| G2 | 0.42 | no | Corran Vey's survey line (1740, 6800) A |
| G3 | 0.56 | ferry | Sunset West (2660, 6490) A; the Old Orchard and Orchard Sleeper (2768, 7076) gym8 A. *Coming: Sunset Island's reason* |
| G4 | 0.63 | yes | Giovanni's town (3647, 6497) A; the beached wreck (4070, 6584) A |
| G5 | 0.44 | near R8 | the gate watcher (4136, 6336) A |
| G6 | 0.51 | no | the Glass Garden (5976, 6544) A |
| G7 | 0.66 | no | the Copperway Khan (6744, 6224) A, **X** (2 probes absent, STATE:19); the Watcher's Ring (7056, 6200) A; the desert wreck (6488, 6772) gym7 A |
| G8 | 0.85 | no | Mew's temple (7604, 7082) A; a jungle temple (7712, 6824) **B** (R9JT never run clean, HANDOVER:19-20; not audited, `jungle_temples.json:3`). 3 elders |
| H2 | 0.76 | no | Dusk tower (1156, 7216) champion A |
| H3 | 0.72 | no | the Lady's Folly (2904, 7632) A; Tobiah Rusk's half-house (2528, 7472) A |
| H6 | 0.00 | ferry | Pacifidlog (5160, 7380) A, **X** (92 floor gaps, contracts C3/C14, STATE:62) |
| H8 | 0.62 | no | Split-Bark (7380, 7376) champion A; two jungle temples (7200, 7528), (7560, 7328) **B**; `sky_far_reach` (7613, 7498) A, T. 3 elders |

Off the map: the Entei boss room (a Nether pocket, `entei_boss.json`, R16Q, champion; EXP-059 steps 7-17 unrun) B;
the nether gate (self-driving, EXP-063 NOT_EXECUTED) B. Lugia is **blocked** (`legendaries.json:545`: the Maelstrom
Trench does not exist).

## 4. Status lists

### 4.1 Broken (a recorded defect)

| Where | Defect | Source |
| --- | --- | --- |
| Misty's gym (C2) | template island floats ~20 blocks; only way in the exposed well (P1). Check whether the gym-arena commits on this branch closed it | N82 |
| `route_03_trainer_05` (1980, 134, 1602) | stands inside a signpost | STATE:105 |
| `route_06_trainer_04` (5756, 106, 3078) | inside a block, feet and head | STATE:105, N121 |
| Gulch coves (E5) | `heart_lapidary_1`, `workers_dwelling_5`, `miners_dwelling_6` probes disagree with the build's z | STATE:51 |
| Victory Road spawn boxes | 1 hole in 281 boxes at x3567-3580 z5282-5527 | STATE:98 |
| `victory_road_transition_10` (3618, 83, 3256) | signpost inside the Deep's pit: floats or erased | N62 |
| Pacifidlog (H6) | 92 floor gaps, its verify exits 1 | STATE:62 |
| Mega field (E4/F4) | 18 dens short of members | STATE:19 |
| Copperway Khan (G7) | 2 probes absent | STATE:19 |
| Heaven's Arena crown | one ring point air at y127 round (3609, 3249); may be designed | STATE:49 |
| Wiremother (D2) | L30 at its tier-2 place's ceiling: a catch-gate leak (owner's call); Split-Bark L63 over its tier ceiling | STATE:332 |

### 4.2 Built, not applied

The jungle temples (G8, H8; R9JT never run clean); R1S; the steps changed since their last run, R9SX, R9SF, R9MD, R9MB,
R16C, R17A, R17L (HANDOVER_SESSION.md:19); the chunk-race fix (STATE:219); the Entei boss and the nether gate (unrun);
the Night Shift dungeon and the gym arenas (this branch, in progress).

### 4.3 Designed only

The Kyogre cave (`docs/world-building/KYOGRE_CAVE.md`; gate gym8 + Dive, STATE:139); the Celebi wake (gate only,
`legendaries.json:610`); the Warden Grove city in the world tree (set aside by the owner, STATE:269); the gym overhaul
(STATE:218); the Route 8 landmark tree candidate (5216, 5024) (STATE:340); the Route 1 middle feature, unsited
(STATE:256); the Merian hut's quests (STATE:279).

### 4.4 Records that disagree with STATE (findings, not fixed here)

1. `data/resident_encounters.json` marks every resident `"status": "built_not_placed"` (lines 85, 364, 582, 733, 854,
   1083, 1238, 1365, 1458, 1836); STATE:332 says all ten applied by R18R.
2. `dune_ruin.json:3`, `frostpeak_camp.json:3`, `frostpeak_summit.json:3`, `lopunny_house.json:3`,
   `fossil_dig.json:5`, `training_grounds.json:4`, `sea_drift.json:3` and `coldwater_station.json:3` say "not applied";
   STATE:32-42, 131 and 18 say applied.
3. `adopted_legendary_sites.json:336` says the station's feather issuing is false; STATE:240 measured it true.
4. STATE:333 says the Cairn, the Cistern and the Benchmark are "not applied"; `reapply.py stale` as relayed by
   HANDOVER_SESSION.md:19-20 lists only R1S and R9JT as never run clean, so R9CN, R9CI, R9BM (and R9NR, R9SR, the
   residents' sites) have run. **Inference, not measured:** read `derived/reapply/` run records in a full checkout.
5. STATE:99 says the location titles are "not installed"; STATE:131 says installed, not yet seen running.
6. For the C4 sweep tonight: `mega_dens.json` (39 strings), `mega_borders.json:61-62` and `entei_boss.json:86-93`
   carry `minecraft:*_concrete_powder`; `data/spawn_blocks.json` names no concrete powder. Whether "no concrete
   anywhere" covers powder is the orchestrator's call.

## 5. Density

Sites per cell (section 3's count, one per site; elders, trainers and signposts excluded):

```
      1  2  3  4  5  6  7  8
  A   2  0  1  1  0  1  1  1
  B   0  4  2  4  4  2  1  1
  C   1  5  0  3  3  3  0  -
  D   1  4  2  6  1  2  4  -
  E   3  4  1  3  4  2  2  1
  F   3  2  4  5  8  2  5  0
  G   -  1  2  2  1  1  3  2
  H   0  1  2  0  -  1  0  4
```

(`-` = under 10% land.) 129 sites in all. **Empty land cells** (40%+ land, 0 sites): **A2** (0.69), **C3** (1.00),
**C7** (0.59), **F8** (0.81). **Thin land cells** (1 site, 40%+ land): A3, A4, A6, A8, B7, B8, C1, D1, **D5**, **E3**
(0.98 land, Mesprit only), G2, G5, G6, H2.

**Empty or thin cells the critical path crosses or touches:** C3 (beside Route 3, band 2), B3 (Route 4, band 3: a hut
with no purpose built and a shrine), B4 (Route 4: a town without services; its two named sites gated 4 and 8), D5
(Victory Road in the Rift trunk, band 8: one site, gated 7), E7 (Route 7, band 6: an outpost and an empty portal), F6
(Route 8: one place and a vault portal), A2 and A3 (within 300-650 blocks of Route 4's start).

**Badge bands with nothing optional to do at their own level, on or near their own leg:**

- **Band 3 (cap 35, Route 4).** Gated-at-3 content: Mesprit (E3), Wiremother (D2), Grandmother Cap (F1), straight-line
  3,361, 2,695 and 4,984 blocks from Route 4's B3 transition (2460, 1261): all behind the player. On the leg itself:
  six trainers, no event, no named Pokemon, no nest. The Merian lodge (coming) is the only band-3 content arriving.
- **Band 6 (cap 50, Route 7).** Gated-at-6 content: Regice (C4, 3,197 from Route 7's middle (6298, 4165)), the
  Tilpey Hart (D6, 1,268), the gulch (E5, 2,037), the Ursaluna catch (B2). Nothing gated 6 stands on Route 7. The
  Tilpey monster (coming) is the candidate if its gate is 6.
- **Band 4 (cap 40, Route 5).** Ridgejaw (B4, 1,262 back) and Regirock (F5, 2,902 south). Short leg; thin, not empty.
- **Band 2 (cap 30).** No resident, legendary or nest anywhere is gated at gym 2 (grep of `gate` fields in
  `resident_encounters.json`, `northern_residents.json`, `southern_residents.json`, `legendaries.json`). Ungated
  content on Route 3 (its three events, the Ursaluna fight, the Seaward Drift) carries it.
- **Champion.** Everything gated at the Champion is a legendary site except Split-Bark and Entei.

**What tonight's arrivals change:** the Merian lodge gives B3 its first band-3 reason; the Lake Tilpey monster and
spawns fill D6 (band 6 if so gated); the Frostpeak Strand castle (A1), Mushroom Island (F1) and Sunset Island (G2/G3/H2/
H3) enrich off-path cells that already have 1-3 sites; the swamp den lands in C6 or B6, which already have 2-3. **None
of them reaches A2, C3, C7, F8, D5 or Routes 4-8's lack of events.** If the swamp "den" is a dungeon den, STATE:156
blocks it until the dungeon run tag exists; if it is an overworld nest on the Ursaluna model, that line does not apply.

## 6. Rules every brief below carries

From the shared rules and STATE: each place different (no second "strong thing in a cave"; the model is the Ursaluna
den); wild Pokemon above the cap welcome where they make a place, the path and most of the place catchable (STATE:159);
spawns through `data/spawns.json`, `tools/compile_spawns.py` and `data/habitat_blocks.json`, never a `data merge` on a
placed Habitat Block; ground from `tools/ground.py` only; a generator, a re-apply step in `tools/reapply.py`, an
`EXCLUDED`-free pack, presence probes in `data/world_probes.json`, own tests, an independent audit by another agent;
residents at least 128 from every route path and clear of every activated Habitat Block's range plus leash
(`tests/test_resident_siting.py`); no concrete; check `data/spawn_blocks.json` for any unusual block.

## 7. The ten biggest gaps

**1. Route 4's middle, B3-B4, band 3 (cap 35): events on the longest early leg.** 3,453 walked blocks from Surge's
town to Erika's with six trainers and nothing else; the route-event pattern stopped at Route 3. Put an event chain like
Routes 1-3's (`tools/route_events.py`, `docs/world-building/EARLY_ROUTES.md`) along the transitions (1979, 1522),
(2460, 1261), (3113, 1424), (3265, 1636), (3868, 1844): three or four events and one find off the path, at least one
tying the leg to the Displaced City (about 160 blocks from (3265, 1636)) so the town without services gets a reason to
be visited. Different from Routes 1-3's events: this is the first leg past the mountains, so mountain things (a
stranded climber, a rockslide, a lost pack animal). Measure the ground at each event site first and keep clear of
the Merian lodge's footprint (coming tonight).

**2. The Tri Peaks massif, A2, band 3: a high, open place.** A2 is 69% land with 0 sites; the Tri Peaks landmark
(1310, 882) is about 530 blocks north of Surge's town (1688, 1410), and Route 4 starts there. Band 3 has nothing at
its own level ahead of the player (section 5). Fit: a summit or scree-field creature gated `gym3_cleared`, strong
enough that a band-2 visitor regrets it, in the open (not a cave: the Ursaluna den (1504, 1414) is the Tri Peaks' cave),
with the climb as the approach. Measure the summit relief and the walk from Surge's town on the heightmap; keep 128
from Route 3 and Route 4's paths.

**3. Route 7, D7-E7, band 6 (cap 50): something on the lakeside leg.** Route 7 runs from (6298, 3596) to (6299, 4735)
and over the outlet bridge (6632, 3904); nothing gated at 6 stands on it (nearest: the Tilpey Hart, 1,268 blocks). The
Lake Tilpey monster arriving tonight may close this; **the builder of this gap first reads where that monster stands
and what its gate is**, and builds only if it is not on Route 7 at band 6. Fit if needed: an event at the bridge
(a toll-keeper, a flood-wrecked cart) and one at the gorge hamlet (6814, 4367), an outpost that stands with little to
do.

**4. C3, beside Route 3, band 2: the empty full-land cell next to the world tree.** C3 is 100% land with 0 sites; Route
3 runs within 34-240 blocks of its west edge (transitions x1809-2014), and the world tree (2016, 2280), the tallest
thing in the world (crown y457-535, `BUILT.md:97`), stands on the edge with one cache at its roots. No content
anywhere is gated at gym 2. Fit: a place with a character in the residents format (`northern_residents.json`'s
shape) and a named Pokemon gated `gym2_cleared`, of the woodland the 3 elders there say this is. **Not the Warden
Grove**: the owner set that aside (STATE:269). Measure the cell's ground and paint before choosing a site.

**5. The Merian hut's written purpose, B3, band 3.** The hut (2813, 1102) has a keeper, two quests (`SQ-MERIAN-01`
First Water, `SQ-MERIAN-02` A Bed Kept Ready) and a Delibird parcel written in EXP-035 row 27, and the build shows none
of it (STATE:279). Tonight's ice fishing lodge is beside it; this is the cheapest band-3 content there is (dialogue,
a parcel, one cache), and it shares the lodge's ground. Coordinate with the lodge's builder; give the hut's quests to
Codex for the words if they are not final.

**6. Routes 5, 6 and 8: no events, bands 4, 5 and 7.** 6,045 walked blocks with 16 trainers between them. Route 6
already passes Azelf, Heave and the Tilpey Hart; Route 8 has the wayside places and the far south; Route 5 (1,051
blocks, B5-C5) has a shrine and `sky_downs_crag` beside it and nothing at band 4. One event chain per leg, Route 5's
first (band 4 has only Ridgejaw behind and Regirock far south). Transitions to site them: Route 5 (4528, 2311);
Route 6 (5436, 2935), (5644, 2981), (5750, 3076); Route 8 (5631, 5190), (5171, 5369), (4231, 5972).

**7. Victory Road's Rift floor, D5-E4, band 8.** D5 holds one site (Registeel, gated 7) though Victory Road crosses it
between (4076, 4653) and (4110, 3807); review N121 item 7 names "the empty Rift floor". The road has ten fights and six
caves; what it lacks is a place on the floor between them that is not a cave: a Compact survey wreck, a displaced
farmstead fallen in with the Rift, a wayside camp before the second rest. **Needs the Victory Road cave plan
(`derived/vr_caves/`), which an agent worktree lacks: site it in the main session, or recompute from
`tools/vr_caves.py`'s model.** Keep out of the Rift zones' barriers (`data/rift_zones.json`).

**8. F8, the east coast dunes, bands 7-8.** 81% land, 0 sites; the Mining Town (6633, 5716) is the nearest town and
the Copperway Khan (6744, 6224), the Watcher's Ring (7056, 6200) and `sky_assay_tor` (7007, 5834) are the nearest
places, 750+ blocks west. Fit: a coastal place unlike the Khan's desert caravanserai and the Glass Garden, for
example a wrecker's lookout over the eastern sea, with a named Pokemon gated `gym7_cleared` or `gym8_cleared`. Measure
the coast on the water-shaped heightmap first (the water export moved coasts 10-16 blocks, N2).

**9. C7, the north-east coast between Northlight and Sabrina, bands 5-6.** 59% land, 0 sites (SOUTH_DENSITY.md:53 had
it at 0.0 too). It lies between Northlight's ferry (B8) and Sabrina's town (D7), east of the marsh country. Fit: a
small place for bands 5-6 that gives a player a reason to walk from Sabrina's town north-east rather than take the
ferry; not a nest if the swamp den lands in C6 next door. Measure what the land is (paint, relief) first: only the
land fraction is known.

**10. Kyogre's cave, the lead that points at nothing, band 8 + Dive.** Coldwater Station (6050, 1843) studies a sealed
dive arch whose destination is a stub (`coldwater_station.json:17, 54`); `KYOGRE_CAVE.md` designs the cave (gate
`gym8_cleared` + Dive, STATE:139). It is the only built lead in the game with no payoff. Build the cave behind the arch
as a legendary site (`data/legendaries.json` record, chamber builder, spawn-free zone, its own audit), on the
pocket-dimension or carved-chamber route the station's record already names. Different from the lake trio's grottoes:
an open-sea chamber reached only by Dive.

**Runners-up:** E3 (0.98 land, Mesprit only, between Route 1 and the Rift, bands 0-3); the Deep's 196 empty interiors
(D4, Codex's labelled rooms); the south's trainers off the roads (SOUTH_DENSITY.md:79, relayed: 12 against 92); the
jungle temples' apply (an integration step, not a builder's gap); G5 and G6 (one site each, along Route 8's south).
