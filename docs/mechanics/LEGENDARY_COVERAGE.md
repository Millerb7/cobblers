# Legendary coverage: a home for every legendary, mythical, Ultra Beast, paradox and early power line

**Status: DESIGN ONLY (unit COVERAGE, 2026-10-11).** Nothing here is built, generated, placed or seen in game. The data
is `data/dungeon_prize_roster.json` (`generated_by: "hand"`); the tables below are rendered from it, so the file is the
source when they disagree. A parallel unit (PRIZE-POOLS) adds pools to `tools/dungeon_prize.py`; this design writes
only the data that unit consumes.

**The owner, 2026-10-11:** "Make sure all legendaries, mythicals, early power mons, and ultra beasts are placed in these
dungeons if not in the world normally. If we can squeeze someone into the world, we should." And: "finish all dungeon
work and make sure we have a lot of variety."

Builds on, and reopens none of: `DUNGEON_PASS2.md` (the prize by stage: a rare non-legendary before gym 6, the
legendary or Ultra Beast from gym 6 with Beast Balls); `DUNGEON_ROOMS.md` 1b (the prize contract); `DUNGEONS.md` 8 and 10
(D18: the approved picks and the six-dungeon list); `ULTRA_BEAST_BOSSES.md` (one boss per unused Ultra Beast);
`docs/research/notes/unhomed-legendaries-1.8.0.md` (the 125-species inventory and the model groups).

---

## 1. The answer in numbers

**125 species** carry a `legendary`, `mythical`, `ultra_beast` or `paradox` label in the Cobblemon 1.8.0 jar (71
legendary, 23 mythical, 11 Ultra Beasts, 20 paradoxes; VERIFIED, read with Python `zipfile` from
`Cobblemon-fabric-1.8.0+1.21.1.jar` in the 2026-10-05 server snapshot; it matches the unhomed note's count).

| Where | Count | Who |
|---|---|---|
| Already placed | **43** (44 with Registeel, 2026-10-12; Buzzwole and Pheromosa also left the Temple Calendar's pool for the world the same day, `data/dungeon_prize_roster.json`) | world sites (adopted, authored, the Nether shrines), the eight starter lines, Entei's built room, and the three prizes the built dungeons already carry (Volcanion, Zarude, Regidrago) |
| Placed by a design, not built | 5 | Kyogre and Rayquaza (`KYOGRE_CAVE.md`); Yveltal, Dialga and Heatran as D18 boss catches |
| Homed but blocked on the owner | 1 | Lugia (no trench), which gets a dungeon fallback. *Corrected 2026-10-12: Registeel is not blocked. `data/legendaries.json` has it `sited` (upper Rift, portal (4195, 3896), gate `gym7_cleared`) and R14L placed it (`docs/REPORT_2026-09-30_DAY.md:64`); it counts under "Already placed" below, and its Night Shift fallback is unused.* |
| **To the world** (proposals) | **7** | Tornadus, Thundurus, Landorus, Enamorus (the Tri Peaks); Tapu Koko, Tapu Lele, Tapu Bulu (the isles); each has a dungeon fallback |
| **To dungeons** | **67** | pool entries across 16 dungeons, every one in exactly one dungeon |
| Out by the owner | 1 | Eternatus: a dungeon home is proposed, NOT put in a pool (section 7) |

**Early power lines: 18** (the ten pseudo-legendary lines and eight chosen here, section 5). **Seven have no early
wild home** (Bagon, Beldum, Gible, Jangmo-o, Frigibax, Honedge, Munchlax); every one of the seven is in at least one
dungeon's rare pool from band 1 or 2, and two (Bagon, Frigibax) get a world spawn proposal as well.

**Dungeons: 16.** The three that exist; the four more `DUNGEONS.md` 10 lists (the Street, the Patriarch, the Cistern, the
Temple Calendar); the Crucible (`DUNGEONS.md` 10 "later"); four on the built nether themes; four new overworld ones. The
Tower After the Fire (Entei) is outside the 16: it is the single room of `data/entei_boss.json` in its own pocket band.

**Nothing is left without a home.** Two homes wait on the owner rather than on design: Eternatus (out by an earlier
decision) and the four planned or blocked world legendaries (which have fallbacks). Section 7.

## 2. Premises checked (three of the brief's were not quite right)

1. **"Read the band of gym 6 from `data/progression.json`."** It carries no caps ("chapters carry no level_cap here").
   The ladder is `generation_contract.gym_ace_levels` [20, 25, 30, 35, 40, 45, 50, 55] (read in `data/gym_trainers.json`
   and `data/rookery.json`), with the cap the next required leader's ace: six badges give cap 50, **band 4** (caps 50,
   55). That agrees with `engine.prize.legendary_from_band` 4.
2. **"Room for 16 dungeons."** Relayed; I found no limit in `engine.slots` or `tools/dungeon.py` (the slot formula has
   none). The design uses exactly 16.
3. **"Paradox if present."** Present, and it matters: the prize tool's label check (`tools/dungeon_prize.py`
   `LEGEND_LABELS = {"legendary", "mythical", "ultra_beast"}`) would **refuse every paradox in a legendary pool and accept
   one as a band-1 rare prize.** Section 6, finding F1.
4. Not a premise, a correction of an older one: `DUNGEONS.md` 8 says the AllTheMons-only species are "unusable until the
   client pack ships" and no dungeon takes one. **The owner has since decided the subset goes to players directly**
   (`docs/STATE.md:157`). Those species are placed here and marked "ATM subset": they render as the doll on any client
   without it. The subset manifest covers every one of them (`modpack/manifest/client-pack-atm-subset.json`, grep: 29 of
   the pool species, plus Flutter Mane and Baxcalibur).

## 3. The rules (each derived, none tuned)

- **One home each.** A legendary, mythical, Ultra Beast or paradox is a world site, a boss, or an entry in ONE dungeon's
  legendary pool (in one or more of its bands). Rare non-legendary lines may repeat across dungeons.
- **Band 4 on** for legendary pools (the Beast Ball stage, `DUNGEON_PASS2.md`). **Band 6 only** for every species the jar
  labels `restricted` (its own line between the box legendaries and the rest: Dialga, Palkia, Ho-Oh, the Tao trio,
  Xerneas, Yveltal, Zacian, Zamazenta, Zygarde, Terapagos, Koraidon, Miraidon). Arceus (mythical, unlabelled) is held to
  band 6 by hand as the capstone.
- **Rare prizes** spawn at the band's lower cap (20, 30, 40). A middle stage is offered only if its natural evolution
  level (jar) is at most 10 above that: Metang (20), Gabite (24), Pupitar, Dragonair, Shelgon (30) from band 1; Fraxure
  (38), Hakamo-o, Arctibax, Doublade (35), Sliggoo (40) from band 2; Zweilous, Drakloak (50), Lampent (41) at band 3.
  **Two existing entries break it and stay**: Hakamo-o and Sliggoo at band 1, both approved by the owner on 2026-10-10
  ("these dungeons are hard and getting through one would mean they deserve it").
- **Paradoxes** only in legendary pools: so none is met before gym 6 in any dungeon, which is how this design reads the
  owner's "late dungeons" (2026-10-08), and each is placed by its theme.
- **Boss legendaries stay bosses** (Yveltal, Dialga, Heatran, as D18; Entei, built). **Lake legendaries become pool
  entries** (Palkia, Suicune, Walking Wake, Tapu Fini), as the Night Shift's lake Volcanion became its pass-3 prize.
- **Ultra Beasts**: each of the nine unused ones is one dungeon's pool entry (the catch) and its proposed boss.
  **Recommended:** the boss stays NPC-held at every band (fight-only, the built chain) and the catch is the hidden prize.
  That retires `ULTRA_BEAST_BOSSES.md` 3.2's wild band-6 stage for Ultra Beasts (the owner's 2026-10-10 "the prize, not
  as easily found" came after that document).
- **Existing pools start with today's species**, so rolling from a pool still offers what the owner approved.

## 4. The sixteen dungeons

The four "proposed" from `DUNGEONS.md` 10 keep D18's picks. Bands below a dungeon's first band are never entered (the
band is frozen at entry from the player's cap: gym 6's badge gives band 4, gym 8's band 5, the Champion's band 6), so a
dungeon first entered at band 4 or later has no rare pool.

| Dungeon | Theme | Gate, first band | Rare pool by band (1 / 2 / 3) | Legendary pool by band (4 / 5 / 6) | UB boss |
|---|---|---|---|---|---|
| **The Night Shift** `night_shift` (existing) | mine | none, 1 | Pupitar, Metang, Gabite, Shelgon / Fraxure, Pupitar, Gabite, Metang / Shelgon, Pupitar, Gabite, Metang | Volcanion, Diancie, Xurkitree / Volcanion, Diancie, Xurkitree / Volcanion, Diancie, Xurkitree, Zygarde, Terapagos | Xurkitree (spine boss) |
| **The Overgrown Temple** `jungle` (existing) | jungle | none, 1 | Hakamo-o, Larvesta, Riolu, Jangmo-o / Hakamo-o, Larvesta, Dreepy / Hakamo-o, Drakloak, Larvesta | Zarude, Okidogi, Munkidori, Fezandipiti, Shaymin / Zarude, Okidogi, Munkidori, Fezandipiti, Shaymin, Ogerpon / Zarude, Ogerpon, Okidogi, Munkidori, Fezandipiti, Shaymin | - |
| **The Drowned Reliquary** `flooded_ruin` (existing) | flooded_ruin | none, 1 | Sliggoo, Dragonair, Deino / Sliggoo, Dragonair, Arctibax / Zweilous, Sliggoo, Dragonair, Arctibax | Regidrago, Regieleki, Phione / Regidrago, Regieleki, Phione, Manaphy / Regidrago, Regieleki, Manaphy | - |
| **The Street That Ends at Nothing** `street` (proposed) | city (new) | none, 1 | Beldum, Honedge, Deino, Litwick / Doublade, Metang, Dreepy / Zweilous, Drakloak, Doublade, Lampent | Zeraora, Magearna, Guzzlord / Zeraora, Magearna, Guzzlord / Palkia, Guzzlord, Zeraora, Magearna | Guzzlord (spine boss) |
| **Under the Patriarch** `patriarch` (proposed) | great tree (new) | none, 1 | Axew, Dreepy, Larvesta, Munchlax / Fraxure, Larvesta, Dreepy / Drakloak, Fraxure, Larvesta | Suicune, Kartana, Celesteela / Suicune, Kartana, Celesteela / Xerneas, Zacian, Zamazenta, Suicune, Kartana, Celesteela | Kartana, Celesteela (wormhole leg, the pair rotates); boss legendary Yveltal |
| **The Last Cistern** `cistern` (proposed) | flooded_ruin (reused) | none, 1 | Frigibax, Dratini, Goomy / Arctibax, Dragonair, Sliggoo / Arctibax, Dragonair, Zweilous | Walking Wake, Nihilego, Iron Bundle / Walking Wake, Nihilego, Iron Bundle / Walking Wake, Nihilego, Iron Bundle | Nihilego (spine boss) |
| **The Temple Calendar** `temple_calendar` (proposed) | jungle (reused) | gym8_cleared (proposed, DUNGEON_PLACEMENT.md Q13 OPEN), 5 | - / - / - | - / Tapu Fini, Buzzwole, Pheromosa, Brute Bonnet, Scream Tail / Tapu Fini, Buzzwole, Pheromosa, Brute Bonnet, Scream Tail | Buzzwole, Pheromosa (wormhole leg, the calendar picks which); boss legendary Dialga |
| **The Crucible** `crucible` (proposed) | basalt_deltas (built theme) | champion_cleared (DUNGEONS.md 10), 6 | - / - / - | - / - / Stakataka, Gouging Fire | Stakataka (wormhole leg); boss legendary Heatran |
| **The Ash Bell** `ash_bell` (proposed) | nether_wastes (built theme) | gym8_cleared (the Nether's gate, data/nether_gate.json), 5 | - / - / - | - / Raikou, Raging Bolt / Ho-Oh, Raikou, Raging Bolt | - |
| **The Moth Cathedral** `moth_cathedral` (proposed) | crimson_forest (built theme) | gym8_cleared, 5 | - / - / - | - / Victini, Slither Wing, Iron Moth / Victini, Slither Wing, Iron Moth | - |
| **The Warped Laboratory** `warped_lab` (proposed) | warped_forest (built theme) | gym8_cleared, 5 | - / - / - | - / Genesect, Iron Valiant, Iron Jugulis / Genesect, Iron Valiant, Iron Jugulis | - |
| **The Soul Ossuary** `soul_ossuary` (proposed) | soul_sand_valley (built theme) | gym8_cleared, 5 | - / - / - | - / Marshadow, Blacephalon, Pecharunt, Roaring Moon / Marshadow, Blacephalon, Pecharunt, Roaring Moon | Blacephalon (spine boss (an ossuary keeper holds it)) |
| **The Dragonspiral** `dragonspiral` (proposed) | ice spire (new) | champion_cleared (proposed), 6 | - / - / - | - / - / Kyurem, Reshiram, Zekrom | - |
| **The Field of Swords** `field_of_swords` (proposed) | hill keep (new) | gym6_cleared (proposed), 4 | - / - / - | Cobalion, Terrakion, Virizion, Iron Leaves, Iron Boulder, Iron Crown / Cobalion, Terrakion, Virizion, Iron Leaves, Iron Boulder, Iron Crown, Keldeo / Keldeo, Cobalion, Terrakion, Virizion, Iron Leaves, Iron Boulder, Iron Crown | - |
| **The Zero Dig** `zero_dig` (proposed; CUT from the install 2026-10-11, the owner: the built one copied the Night Shift, re-authoring waits on the owner's play) | desert excavation (new) | gym7_cleared (proposed), 4 | - / - / - | Great Tusk, Iron Treads, Sandy Shocks, Iron Hands, Iron Thorns / Great Tusk, Iron Treads, Sandy Shocks, Iron Hands, Iron Thorns / Koraidon, Great Tusk, Iron Treads, Sandy Shocks, Iron Hands, Iron Thorns | - |
| **The Starfall Crater** `starfall` (proposed) | night sky crater (new) | gym8_cleared (proposed), 5 | - / - / - | - / Jirachi, Deoxys, Cresselia / Arceus, Jirachi, Deoxys, Cresselia | - |

**New themes these need:** city (the Street), great tree (the Patriarch), ice spire (the Dragonspiral), hill keep (the
Field of Swords), desert excavation (the Zero Dig), night-sky crater (the Starfall Crater). The Cistern reuses
`flooded_ruin` and the Temple Calendar `jungle`; the five nether dungeons use the five built nether themes
(`DUNGEON_ROOMS.md` 11), whose rips stand in the Nether, which the engine does not place yet.

**Two moves from earlier designs, both for the same reason:** Stakataka and Blacephalon were the Tower After the Fire's
rotating pair (`ULTRA_BEAST_BOSSES.md` 4). The Tower is the single Entei room, not a rooms dungeon, so it has no habitat
room to hold a prize. Stakataka goes to the Crucible (a wormhole leg beside Heatran), Blacephalon to the Soul Ossuary (its
spine boss).

**A possible merge, the owner's call:** the jungle test dungeon (The Overgrown Temple) and the Temple Calendar share a
theme, and the flooded ruin and the Cistern another. Kept separate here, as D18 lists them; if merged, the second's pool
moves into the first's unchanged, and the 16 become 14 with room for more.

## 5. Early power lines

"Placed early" = a wild spawn in `data/spawns.json` (route entries, habitats and nether tables, read 2026-10-11) at or
under about level 35. The eight lines beyond the ten pseudo-legendaries were chosen for a strong final stage from a
rare or slow first stage; the why is in the table.

| Line | Kind | In the world now | Dungeon rare pools | World proposal |
|---|---|---|---|---|
| Dratini | pseudo | placed early: Shrew Lake shores 18-22, Driftmouth waters | flooded_ruin, cistern | - |
| Larvitar | pseudo | placed: Frostpeak 33-34 | night_shift | - |
| Bagon | pseudo | MISSING early: Salamence only (Rift 56-62); egg room band 5 | night_shift | Tri Peaks (proposal) |
| Beldum | pseudo | MISSING early: Mega field only (gulch_mine.json, band 4); egg room band 6 | night_shift, street | - |
| Gible | pseudo | MISSING early: Mega field only (band 4); egg room band 5 | night_shift | - |
| Deino | pseudo | placed early: Fungal Isle south 23-28 | flooded_ruin, street | - |
| Goomy | pseudo | placed early: Fungal Isle north, Marshy Marsh 23-43 | flooded_ruin, cistern | - |
| Jangmo-o | pseudo | MISSING early: Hakamo-o/Kommo-o on the Long Isle at 48-53 only | jungle | - |
| Dreepy | pseudo | placed: Sunset Watch 30-38 | jungle, street, patriarch | - |
| Frigibax | pseudo | MISSING: no wild home; implemented by COBBLEVERSE-DP only; model in the ATM subset only | flooded_ruin, cistern | the Crags (proposal) |
| Riolu | similar: Lucario: a strong early fighter, rare in the games | placed early: Viltri's Path 18-22 | jungle | - |
| Axew | similar: Haxorus: a three-stage dragon, 540 | placed: Northgate east 38-42 | night_shift, patriarch | - |
| Larvesta | similar: Volcarona 550; slow (59); a starter here | placed: starter; the Craters 38+ | jungle, patriarch | - |
| Honedge | similar: Aegislash | MISSING early: Doublade/Aegislash from 48 only | street | - |
| Litwick | similar: Chandelure, special attack 145 | placed early: Route 1 ghost mansion 6-15 | street | - |
| Togepi | similar: Togekiss | placed early: Shrew Lake shores 18-22; egg room band 2 | - | - |
| Munchlax | similar: Snorlax | MISSING: no wild Munchlax; Snorlax at North Pine Isle 38-43; bait room bands 5-6 | patriarch | - |
| Scyther | similar: 500 BST at its first stage | placed early: Route 1 maze forest 9-11 and six more | - | - |

The dungeon's other rooms already hand some of these out, which is why they are not counted as missing there: the egg
room offers Larvitar, Bagon and Gible at band 5 and Dratini, Beldum and Deino at band 6, Riolu at band 4, Togepi at band
2 (`data/dungeon_extras2.json` `eggs.offers`); the flooded ruin's fishing pool has the Dratini line; the bait room lures
Snorlax and Scyther (`data/dungeon_extras.json`).

**World proposals for two lines** (`data/encounter_design.json`, which `tools/build_encounters.py` expands into
`data/spawns.json`): **Frigibax**, ultra-rare in the Crags of the Glacial Tear (`the_crags`, band 25-32), the ice dragon
in a glacier cirque (it has no wild home at all, and renders only with the ATM subset); **Bagon** on the Tri Peaks (band
20-28), the dragon that leaps off cliffs. Bagon, Beldum, Gible and Jangmo-o otherwise first appear wild at band 4 or
later.

## 6. Findings for other units (cross-system)

| # | Finding | Who | Evidence |
|---|---|---|---|
| F1 | **The prize tool's label check knows no paradoxes.** `LEGEND_LABELS` is `{legendary, mythical, ultra_beast}`; the jar labels the 18 non-legendary paradoxes `paradox` only. As written, `room_problems()` refuses all 18 in a legendary pool and lets one through as a rare (pre-gym-6) prize. Add `paradox` to the legendary side and refuse it on the rare side | PRIZE-POOLS | `tools/dungeon_prize.py:54`, `:400-417`; jar labels (`walkingwake`: `gen9, paradox`) |
| F2 | **An Ultra Beast prize would be caught at x25.** From band 4 the prize carries the key-ball tag; the Beast Ball's own `ultra_beast` label modifier is x5 and the key-ball callback multiplies x5 again (`ULTRA_BEAST_BOSSES.md` F2, unrun probe UB3). `data/key_ball.json` has no `native_tag` guard today (grep). The nine UB pool entries need it, or the callback must skip UBs | PRIZE-POOLS, `key_ball` owner | `ULTRA_BEAST_BOSSES.md` 2 F2, 8; grep of `data/key_ball.json`, `tools/key_ball.py` |
| F3 | **29 pool species render as the doll without the ATM subset** (the seven ATM UBs, 14 paradoxes, Manaphy, Phione, Jirachi, Magearna, Zeraora, Pecharunt, Frigibax, Arctibax). Each is marked `model_gate: atm_subset` in `species`; a consumer can drop them until delivery | PRIZE-POOLS; the main session (delivery) | `modpack/manifest/client-pack-atm-subset.json` |
| F4 | **Inherited ultra-rare spawns are a second, untagged source** for most of the 67 (the live world has no suppression). Proposal: add every species given a dungeon home to `data/spawn_suppression.json` `removed_species`, as was done for the paradoxes (the UB document's U-Q3, widened) | owner; `datapack-content-dev` | `unhomed-legendaries-1.8.0.md` inventory |
| F5 | `tools/validate_data.py` exits 1 in this worktree on one error unrelated to this unit: 263 placements name local-only templates the worktree has not hydrated (`spawn-blocks`) | none (environment) | run 2026-10-11 |

## 7. What waits on the owner

1. **Eternatus.** OUT since 2026-10-02 "until a Galar Particle supply is authored" (the cocoon wants 500). A dungeon prize
   needs no particles. The 2026-10-11 instruction ("all legendaries") and the 2026-10-02 decision disagree; proposed:
   the Starfall Crater, band 6. Not in any pool until the owner says.
2. **The four world proposals** (the Forces of Nature on the Tri Peaks, three Tapus on the isles). Each needs a site on
   ground and a `sealed_chamber` record (`tools/legendaries.py` KINDS has `lake_grotto`, `sealed_chamber`, `sapling_wake`);
   the Tri Peaks carries no legendary today and the owner called it "too barren". If the owner prefers dungeons, each
   proposal's `fallback` puts it in a pool at once.
3. **Blocked and planned world homes:** Lugia (fallback: the Drowned Reliquary, band 6), Kyogre (the Cistern, band 6),
   Rayquaza (the Starfall Crater, band 6). Fallbacks only; the world homes stand. (Registeel was listed here with the
   Night Shift, bands 4-6; corrected 2026-10-12: it is sited in the upper Rift, so that fallback is unused.)
4. **Koraidon and Miraidon** (`DUNGEON_PLACEMENT.md` Q14, answered 2026-10-12): post-Champion area bosses in the world.
   Miraidon is built at The Relay Fault (K3, `data/caves.json`); Koraidon is K6 (Sunscar), not yet built, and stays in the
   Zero Dig's band-6 pool until then.
5. **Yveltal, Dialga, Heatran:** kept as D18 boss catches. The alternative is the prize form (a pool entry) with a
   fight-only boss.
6. **The UB bosses' form** (section 3, last bullet) and `ULTRA_BEAST_BOSSES.md`'s open U-Q1 to U-Q7.
7. **The merges** in section 4, and the gates proposed for the new dungeons (gym 6, 7, 8 and Champion flags).

## 8. Every species

`(ATM subset)` = renders only with the AllTheMons subset (F3). "Goes to" bands are the pool bands in that dungeon.

| # | Species | Kind | Where now | Goes to | Why |
|---|---|---|---|---|---|
| 144 | Articuno | legendary | placed: adopted shrine, Frostpeak summit (adopted_legendary_sites.json) | stays |  |
| 145 | Zapdos | legendary | placed: adopted tower, Fungal Isle east coast | stays |  |
| 146 | Moltres | legendary | placed: adopted tower, the Craters | stays |  |
| 150 | Mewtwo | legendary | placed: COBBLEVERSE-DP fossil revive; the owner: 'Mewtwo stays on the fossil route' (entei_boss.json). Reachability of the revive not verified | stays |  |
| 151 | Mew | mythical | placed: adopted temple (Champion door) | stays |  |
| 243 | Raikou | legendary | **dungeon**: nowhere authored | ash_bell, bands 5, 6 | Entei's sibling; the owner named it for the Nether |
| 244 | Entei | legendary | placed: the Tower After the Fire, built (entei_boss.json) | stays |  |
| 245 | Suicune | legendary | **dungeon**: nowhere authored | patriarch, bands 4, 5, 6 | D18's lake pick for the Patriarch |
| 249 | Lugia | legendary | blocked (owner decision): legendaries.json, blocked on the owner (no trench) | keeps its world home; fallback flooded_ruin band 6 |  |
| 250 | Ho-Oh | legendary | **dungeon**: nowhere authored | ash_bell, band 6 | the burned bell; restricted |
| 251 | Celebi | mythical | placed: Route 1 sapling (sapling_celebi.json) and celebi_wake | stays |  |
| 377 | Regirock | legendary | placed: legendaries.json sealed chamber, Scorched Plateau | stays |  |
| 378 | Regice | legendary | placed: legendaries.json sealed chamber, Glacial Tear | stays |  |
| 379 | Registeel | legendary | placed: legendaries.json sealed chamber (registeel), the upper Rift, portal (4195, 3896), gate gym7_cleared (sited; was listed as blocked, corrected 2026-10-12) | stays; the night_shift fallback is unused |  |
| 380 | Latias | legendary | placed: Shrew Station Eon shrine (research_station.json) | stays |  |
| 381 | Latios | legendary | placed: Shrew Station Eon shrine | stays |  |
| 382 | Kyogre | legendary | planned (designed, not built): KYOGRE_CAVE.md (designed, not built); Coldwater Station leads to it | keeps its world home; fallback cistern band 6 |  |
| 383 | Groudon | legendary | placed: legendaries.json, the Craters | stays |  |
| 384 | Rayquaza | legendary | planned (designed, not built): KYOGRE_CAVE.md sky island (designed, not built) | keeps its world home; fallback starfall band 6 |  |
| 385 | Jirachi (ATM subset) | mythical | **dungeon**: nowhere authored | starfall, bands 5, 6 | a wishing star |
| 386 | Deoxys | mythical | **dungeon**: nowhere authored | starfall, bands 5, 6 | a meteor |
| 480 | Uxie | legendary | placed: legendaries.json lake grotto, Lake Tilpey | stays |  |
| 481 | Mesprit | legendary | placed: legendaries.json lake grotto, Arrow Lake | stays |  |
| 482 | Azelf | legendary | placed: legendaries.json lake grotto, Marshy Marsh | stays |  |
| 483 | Dialga | legendary | planned (designed, not built): D18: the Temple Calendar's boss, band-6 catch (designed) | temple_calendar (boss) |  |
| 484 | Palkia | legendary | **dungeon**: nowhere authored | street, band 6 | D18's lake pick for the Street; restricted |
| 485 | Heatran | legendary | planned (designed, not built): DUNGEONS.md 10: the Crucible's boss after Entei (designed) | crucible (boss) |  |
| 486 | Regigigas | legendary | placed: legendaries.json, the North Pine Isle (moved 2026-10-12 from beside the Displaced City) | stays |  |
| 487 | Giratina | legendary | placed: Wardenhold (frostpeak_keep_quest.json) | stays |  |
| 488 | Cresselia | legendary | **dungeon**: nowhere authored | starfall, bands 5, 6 | the full moon, Darkrai's counterpart |
| 489 | Phione (ATM subset) | mythical | **dungeon**: nowhere authored | flooded_ruin, bands 4, 5 | the sunken sea temple |
| 490 | Manaphy (ATM subset) | mythical | **dungeon**: nowhere authored | flooded_ruin, bands 5, 6 | the sunken sea temple's prince |
| 491 | Darkrai | mythical | placed: Newmoon Island over the Fungal Isle (sweep_newmoon_island) | stays |  |
| 492 | Shaymin | mythical | **dungeon**: nowhere authored | jungle, bands 4, 5, 6 | the flowering canopy sanctum; no world archetype fits a meadow |
| 493 | Arceus | mythical | **dungeon**: nowhere authored | starfall, band 6 | the capstone, held to band 6 by hand |
| 494 | Victini | mythical | **dungeon**: nowhere authored | moth_cathedral, bands 5, 6 | its inherited spawn is the crimson forest |
| 638 | Cobalion | legendary | **dungeon**: nowhere authored | field_of_swords, bands 4, 5, 6 | a Sword of Justice |
| 639 | Terrakion | legendary | **dungeon**: nowhere authored | field_of_swords, bands 4, 5, 6 | a Sword of Justice |
| 640 | Virizion | legendary | **dungeon**: nowhere authored | field_of_swords, bands 4, 5, 6 | a Sword of Justice |
| 641 | Tornadus | legendary | **world** (proposal): nowhere authored | Tri Peaks summit (proposal); fallback dragonspiral band 6 |  |
| 642 | Thundurus | legendary | **world** (proposal): nowhere authored | Tri Peaks summit (proposal); fallback dragonspiral band 6 |  |
| 643 | Reshiram | legendary | **dungeon**: nowhere authored | dragonspiral, band 6 | the Tao trio; restricted |
| 644 | Zekrom | legendary | **dungeon**: nowhere authored | dragonspiral, band 6 | the Tao trio; restricted |
| 645 | Landorus | legendary | **world** (proposal): nowhere authored | Tri Peaks summit (proposal); fallback dragonspiral band 6 |  |
| 646 | Kyurem | legendary | **dungeon**: nowhere authored | dragonspiral, band 6 | the frozen one that holds the other two; restricted |
| 647 | Keldeo | mythical | **dungeon**: nowhere authored | field_of_swords, bands 5, 6 | the sword in the spring, after the three |
| 648 | Meloetta | mythical | **world** (built offline 2026-10-12, not applied): The Singing Hollow, `cave_singing_hollow` (K2), a repeatable ultra-rare chamber spawn at level 50 behind gym6_cleared | cave kit, `data/caves.json` | the song cave; its inherited DP spawn is not yet removed |
| 649 | Genesect | mythical | **dungeon**: nowhere authored | warped_lab, bands 5, 6 | an ancient thing rebuilt in a lab; the DP's fossil revive also exists (unverified reachable) |
| 716 | Xerneas | legendary | **dungeon**: nowhere authored | patriarch, band 6 | Yveltal's pair, the life-tree; restricted |
| 717 | Yveltal | legendary | planned (designed, not built): D18: the Patriarch's boss, band-6 catch (designed) | patriarch (boss) |  |
| 718 | Zygarde | legendary | **dungeon**: nowhere authored | night_shift, band 6 | dripstone caves; restricted |
| 719 | Diancie | mythical | **dungeon**: nowhere authored | night_shift, bands 4, 5, 6 | the gem at the back of the mine |
| 720 | Hoopa | mythical | placed: the Hoopa cradle (hoopa_cradle.json) | stays |  |
| 721 | Volcanion | mythical | placed: the Night Shift's prize, bands 4-6 (data/dungeons.json, built) | stays (night_shift) |  |
| 772 | Type: Null | legendary | placed: mythical starter (mythical_starters.json) | stays |  |
| 773 | Silvally | legendary | placed: starter line (Type: Null) | stays |  |
| 785 | Tapu Koko | legendary | **world** (proposal): nowhere authored | Sunset Isle west (proposal); fallback temple_calendar bands 5-6 |  |
| 786 | Tapu Lele | legendary | **world** (proposal): nowhere authored | Sunset Isle east (proposal); fallback temple_calendar bands 5-6 |  |
| 787 | Tapu Bulu | legendary | **world** (proposal): nowhere authored | Jungle Isle (proposal); fallback temple_calendar bands 5-6 |  |
| 788 | Tapu Fini | legendary | **dungeon**: nowhere authored | temple_calendar, bands 5, 6 | D18's lake pick for the Temple Calendar |
| 789 | Cosmog | legendary | placed: mythical starter | stays |  |
| 790 | Cosmoem | legendary | placed: starter line (Cosmog) | stays |  |
| 791 | Solgaleo | legendary | placed: starter line (Cosmog) | stays |  |
| 792 | Lunala | legendary | placed: starter line (Cosmog) | stays |  |
| 793 | Nihilego (ATM subset) | UB | **dungeon**: nowhere authored | cistern, bands 4, 5, 6 | poison in the reservoir; the cistern's boss |
| 794 | Buzzwole (ATM subset) | UB | **dungeon**: nowhere authored | temple_calendar, bands 5, 6 | the calendar's pair |
| 795 | Pheromosa (ATM subset) | UB | **dungeon**: nowhere authored | temple_calendar, bands 5, 6 | the calendar's pair |
| 796 | Xurkitree (ATM subset) | UB | **dungeon**: nowhere authored | night_shift, bands 4, 5, 6 | the lit wiring; the Night Shift's boss |
| 797 | Celesteela | UB | **dungeon**: nowhere authored | patriarch, bands 4, 5, 6 | grew up through the roots; renders today |
| 798 | Kartana | UB | **dungeon**: nowhere authored | patriarch, bands 4, 5, 6 | cuts the roots; renders today |
| 799 | Guzzlord (ATM subset) | UB | **dungeon**: nowhere authored | street, bands 4, 5, 6 | it ate the rest of the street; its boss |
| 800 | Necrozma | legendary | placed: the dawn and dusk towers (adopted) | stays |  |
| 801 | Magearna (ATM subset) | mythical | **dungeon**: nowhere authored | street, bands 4, 5, 6 | a machine an old city made |
| 802 | Marshadow | mythical | **dungeon**: nowhere authored | soul_ossuary, bands 5, 6 | the shadow among the bones |
| 803 | Poipole | UB | placed: mythical starter; the two towers (spawns.json placement_sites) | stays |  |
| 804 | Naganadel | UB | placed: starter line (Poipole) | stays |  |
| 805 | Stakataka (ATM subset) | UB | **dungeon**: nowhere authored | crucible, band 6 | a stone wall in the basalt; moved from the Tower pair |
| 806 | Blacephalon (ATM subset) | UB | **dungeon**: nowhere authored | soul_ossuary, bands 5, 6 | fire and ghost; moved from the Tower pair |
| 807 | Zeraora (ATM subset) | mythical | **dungeon**: nowhere authored | street, bands 4, 5, 6 | a city's thunderclap |
| 808 | Meltan | mythical | placed: mythical starter | stays |  |
| 809 | Melmetal | mythical | placed: starter line (Meltan) | stays |  |
| 888 | Zacian | legendary | **dungeon**: nowhere authored | patriarch, band 6 | the misty wood of heroes; restricted |
| 889 | Zamazenta | legendary | **dungeon**: nowhere authored | patriarch, band 6 | the misty wood of heroes; restricted |
| 890 | Eternatus | legendary | OUT (owner): OUT by the owner until a Galar Particle supply exists | owner's call: starfall band 6, owner's call |  |
| 891 | Kubfu | legendary | placed: mythical starter | stays |  |
| 892 | Urshifu | legendary | placed: starter line (Kubfu) | stays |  |
| 893 | Zarude | mythical | placed: the Overgrown Temple's prize, bands 4-6 (data/dungeons.json, built) | stays (jungle) |  |
| 894 | Regieleki | legendary | **dungeon**: nowhere authored | flooded_ruin, bands 4, 5, 6 | Regidrago's pair, the same sealed chamber |
| 895 | Regidrago | legendary | placed: the Drowned Reliquary's prize, bands 4-6 (data/dungeons.json, built) | stays (flooded_ruin) |  |
| 896 | Glastrier | legendary | placed: crown spire (adopted, hidden) | stays |  |
| 897 | Spectrier | legendary | placed: crown cemetery, once per player (spectrier_cap.json) | stays |  |
| 898 | Calyrex | legendary | placed: crown cemetery (adopted) | stays |  |
| 905 | Enamorus | legendary | **world** (proposal): nowhere authored | Tri Peaks saddle after the three (proposal); fallback dragonspiral band 6 |  |
| 984 | Great Tusk (ATM subset) | paradox | **dungeon**: nowhere authored | zero_dig, bands 4, 5, 6 | arid paradox |
| 985 | Scream Tail (ATM subset) | paradox | **dungeon**: nowhere authored | temple_calendar, bands 5, 6 | an ancient paradox through the calendar; floral |
| 986 | Brute Bonnet (ATM subset) | paradox | **dungeon**: nowhere authored | temple_calendar, bands 5, 6 | an ancient paradox; jungle |
| 987 | Flutter Mane (ATM subset) | paradox | placed: starter line (Misdreavus -> Mismagius -> Flutter Mane, STATE 157) | stays |  |
| 988 | Slither Wing (ATM subset) | paradox | **dungeon**: nowhere authored | moth_cathedral, bands 5, 6 | Volcarona's ancient paradox; crimson forest |
| 989 | Sandy Shocks (ATM subset) | paradox | **dungeon**: nowhere authored | zero_dig, bands 4, 5, 6 | arid paradox |
| 990 | Iron Treads (ATM subset) | paradox | **dungeon**: nowhere authored | zero_dig, bands 4, 5, 6 | arid paradox, Great Tusk's double |
| 991 | Iron Bundle (ATM subset) | paradox | **dungeon**: nowhere authored | cistern, bands 4, 5, 6 | ice/water: the cold reservoir |
| 992 | Iron Hands | paradox | **dungeon**: nowhere authored | zero_dig, bands 4, 5, 6 | desert paradox; renders today (Planeta RP) |
| 993 | Iron Jugulis | paradox | **dungeon**: nowhere authored | warped_lab, bands 5, 6 | a future paradox; renders today (Planeta RP) |
| 994 | Iron Moth (ATM subset) | paradox | **dungeon**: nowhere authored | moth_cathedral, bands 5, 6 | Volcarona's future paradox |
| 995 | Iron Thorns (ATM subset) | paradox | **dungeon**: nowhere authored | zero_dig, bands 4, 5, 6 | a future paradox |
| 1001 | Wo-Chien | legendary | placed: Nether shrine, stays where it generates (adopted_legendary_sites.json catalogue) | stays |  |
| 1002 | Chien-Pao | legendary | placed: Nether shrine, stays where it generates | stays |  |
| 1003 | Ting-Lu | legendary | placed: Nether shrine, stays where it generates | stays |  |
| 1004 | Chi-Yu | legendary | placed: Nether shrine, stays where it generates | stays |  |
| 1005 | Roaring Moon (ATM subset) | paradox | **dungeon**: nowhere authored | soul_ossuary, bands 5, 6 | dragon/dark ancient paradox |
| 1006 | Iron Valiant (ATM subset) | paradox | **dungeon**: nowhere authored | warped_lab, bands 5, 6 | a future paradox |
| 1007 | Koraidon | legendary | **dungeon**: nowhere authored | zero_dig, band 6 | the past; restricted; Q14 open |
| 1008 | Miraidon | legendary | **world** (built offline 2026-10-12, not applied): The Relay Fault, `cave_relay_fault` (K3), a post-Champion area boss kept by a keeper, level 70, behind champion_cleared | cave kit, `data/caves.json` | the future; restricted; Q14 answered 2026-10-12 |
| 1009 | Walking Wake | paradox | **dungeon**: nowhere authored | cistern, bands 4, 5, 6 | D18's lake pick for the Cistern; renders today (jar) |
| 1010 | Iron Leaves | paradox | **dungeon**: nowhere authored | field_of_swords, bands 4, 5, 6 | Virizion's paradox; renders today (jar) |
| 1014 | Okidogi | legendary | **dungeon**: nowhere authored | jungle, bands 4, 5, 6 | one of the Loyal Three |
| 1015 | Munkidori | legendary | **dungeon**: nowhere authored | jungle, bands 4, 5, 6 | one of the Loyal Three; inherited jungle spawn |
| 1016 | Fezandipiti | legendary | **dungeon**: nowhere authored | jungle, bands 4, 5, 6 | one of the Loyal Three |
| 1017 | Ogerpon | legendary | **dungeon**: nowhere authored | jungle, bands 5, 6 | the masked one, after the Three |
| 1020 | Gouging Fire (ATM subset) | paradox | **dungeon**: nowhere authored | crucible, band 6 | its inherited spawn is the basalt deltas |
| 1021 | Raging Bolt (ATM subset) | paradox | **dungeon**: nowhere authored | ash_bell, bands 5, 6 | Raikou's ancient paradox |
| 1022 | Iron Boulder | paradox | **dungeon**: nowhere authored | field_of_swords, bands 4, 5, 6 | Terrakion's paradox; renders today (Planeta RP) |
| 1023 | Iron Crown (ATM subset) | paradox | **dungeon**: nowhere authored | field_of_swords, bands 4, 5, 6 | Cobalion's paradox |
| 1024 | Terapagos | legendary | **dungeon**: nowhere authored | night_shift, band 6 | a crystal cavern; restricted |
| 1025 | Pecharunt (ATM subset) | mythical | **dungeon**: nowhere authored | soul_ossuary, bands 5, 6 | poison and ghost |

## 9. Not verified

- Every placement is a proposal; none is built, placed or seen in game. "Placed" means a record or decision in `data/`
  (or a starter line), not that the encounter has been seen to work.
- That Mewtwo's DP fossil revive and Genesect's are reachable with our item routes (relayed).
- That a level-50 legendary at band 4 is a fair prize: balance is `trainer-balance-designer`'s; levels follow the built
  rule (the band's lower cap).
- Every "renders today" and "ATM subset" call is a file check (the unhomed note's method and the subset manifest), not
  seen in game.
- Pokemon lore used for theme (the Swords' paradox doubles, the Loyal Three, the Tapus' islands) is recalled, not read;
  it is flavour, and no rule here rests on it.

## 9. The nine homeless paradoxes, re-homed (2026-10-12)

The Zero Dig is cut and the Temple Calendar and the Last Cistern were never built, so nine paradoxes had a roster home
that cannot be entered. Each moved into the legendary pool of a BUILT dungeon by theme
(`data/dungeon_prize_roster.json`, read by `tools/dungeon_prize.pool_at` through each habitat's `prize.roster`). The three
unbuilt dungeons' pools are now `{}`; one home each. The table is the whole change, with the band range each keeps.

| Paradox | From | To | Bands | Why | Model gate |
|---|---|---|---|---|---|
| Iron Treads | zero_dig | night_shift | 4-6 | a steel/ground machine is a mine's find | atm_subset |
| Great Tusk | zero_dig | field_of_swords | 4-6 | ground/fighting, the open hills | atm_subset |
| Sandy Shocks | zero_dig | ash_bell | 5-6 | electric/ground waste beside Raikou and Raging Bolt | atm_subset |
| Iron Hands | zero_dig | crucible | 6 | a forge-hammer brute; the only non-gated species of that pool | none |
| Iron Thorns | zero_dig | warped_lab | 5-6 | a future paradox beside the lab's other two | atm_subset |
| Scream Tail | temple_calendar | jungle | 4-6 | floral ancient paradox in the flowering jungle | atm_subset |
| Brute Bonnet | temple_calendar | patriarch | 4-6 | ancient grass/dark, the great tree's root hollows | atm_subset |
| Iron Bundle | cistern | dragonspiral | 6 | ice/water future paradox in an ice spire | atm_subset |
| Walking Wake | cistern | flooded_ruin | 4-6 | the drowned reliquary's water | none |

No pool doubles (largest growth: the Crucible 2 -> 3 at its one band). Every pool keeps at least one species that is not
model-gated at each band it has, except the pools that were already all-gated before this change (the Street's bands 4-5,
which this change does not touch). The Crucible's band 6 was all-gated (Stakataka, Gouging Fire) and now offers Iron Hands
until the AllTheMons subset is delivered. Not verified in game: file validity and the pool tests only.

### Heatran and Yveltal stay planned

Both are listed as D18 boss catches (`boss_legendary` in the roster), but a rooms dungeon has no legendary boss stage: the
boss is a chain of NPC trainer stages (`data/dungeons.json` `boss.teams`), and the only legendary mechanism in
`tools/dungeon_fights.py` is the prize habitat (`anchors["legendary"]`). The Crucible and Patriarch records say so in their
`does_not_cover`. Heatran's room is `data/heatran_boss.json` (designed, not built); Yveltal needs the wild band-6 last stage
and the sealed cocoon (E-P6, E-P7). The prize form (a pool entry) is the roster's own stated alternative; it is the owner's
call, not taken here.
