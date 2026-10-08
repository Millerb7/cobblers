# Unhomed legendaries, mythicals, Ultra Beasts and paradoxes (Cobblemon 1.8.0, our stack)

**Research only, 2026-10-08. Nothing is built, placed, booted or spawned.** Answers the owner's dungeon brief: "use
legendaries and mythicals we have no home for. A lake area where a player with Dive swims to something at the bottom;
make it OBVIOUS something is down there." Already decided and not reopened here: paradoxes are dungeon content
(`docs/STATE.md:152`); Entei is a dungeon boss and Heatran follows (`data/entei_boss.json`, `docs/mechanics/DUNGEONS.md`
section 3); overworld legendaries with a home stay where they are.

Companions: `docs/research/notes/legendary-species-1.8.0.md`, `ultra-beasts-1.8.0.md`, `paradox-pokemon-1.8.0.md`
(their findings re-checked here, corrections below), `docs/mechanics/NETHER_DUNGEON_SCOPE.md` section 7 (the candidate
table this one replaces), `data/adopted_legendary_sites.json` `catalogue_2026_10_06`.

## Method (what was read, and how)

- **Archives, READ ONLY, Python `zipfile`** (scratch scripts in the worktree's gitignored `tmp/unhomed/`, not
  committed):
  - every jar in `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/` (the offline server
    snapshot) and every zip in its `datapacks/` (COBBLEVERSE-DP-v31 among them);
  - every zip in `C:/Users/wnd/Documents/github/cobblers/COBBLEVERSE/resourcepacks/`. The live server directory was
    not opened.
- **The species set** = every `data/cobblemon/species/*/*.json` in `Cobblemon-fabric-1.8.0+1.21.1.jar` whose `labels`
  include `legendary`, `mythical`, `ultra_beast` or `paradox`: **125 species** (71 legendary, 23 mythical, 20 paradox,
  11 Ultra Beasts; Koraidon and Miraidon are labelled `legendary, restricted`, not `paradox`). Type, base-stat total
  and `catchRate` are from those files. VERIFIED.
- **Implemented** = the jar's own file has `implemented: true`, or any jar or datapack zip carries a
  `species_additions` (or full species) file for it with `implemented: true`. **All 125 are implemented somewhere.**
  Who implements matters: "DP" means the species exists only while COBBLEVERSE-DP-v31 is enabled; "MSD" means Mega
  Showdown 1.0.2 must stay. VERIFIED.
- **"Model today"** = a resolver (`assets/*/bedrock/pokemon/resolvers/` or the old `bedrock/species/` path) whose
  aspect-free variation names a `.geo.json` model, a poser (a JSON poser, or the jar's compiled
  `client/render/models/blockbench/pokemon/**/<Name>Model.class`) and a texture that all exist in **what players get**:
  the mod jars plus the 32 file packs our overlay enables (`modpack/config/resourcepackoverrides.json` `default_packs`).
  `ATMxMSD RP.zip` is not in that list, so a species whose only model is there is **"usable if AllTheMons ships"**
  (ADR-006, Proposed; the subset manifest `modpack/manifest/client-pack-atm-subset.json` lists all 28 of them, grep
  2026-10-08). A file check, **not seen in game**; that players' resource-pack files equal this local copy is ASSUMED.
- **Level.** **The Cobblemon jar gives no level for any of the 125**: it ships 1,544 `spawn_pool_world` files and
  none is for one of these species (VERIFIED). The level shown is the **base pack's** inherited
  COBBLEVERSE-DP spawn (`data/cobblemon/spawn_pool_world/`). "Label only (weight 0)" is one of the DP's 42 zero-weight
  "where it is found" labels and can never spawn (`docs/research/notes/cobbleverse-legendary-structures.md` section 1).
  "Structure-gated" (Raikou, Entei, Suicune: `cobbleverse:burned_tower`; Poipole: the two towers; the Galarian birds:
  `dyna_tree`) never passes in our exported chunks, which carry no structure starts (EXP-013, relayed). "End" is a
  dimension with no door in our world (relayed, `legendary-catalogue-reopened.md` section 5). The rest are live
  wherever the bounded suppression does not reach (`data/spawn_suppression.json` `retain_defaults`: off-route
  wilderness, unauthored caves, the Nether), and the live world has no suppression at all (STATE, relayed): an
  ultra-rare, above-cap wild legendary is possible today wherever its biome is painted.
- **Homes** = a grep of every `data/*.json` plus `docs/mechanics/{LEGENDARIES,DUNGEONS,NETHER_DUNGEON_SCOPE}.md` for
  each species' id and display name, then each hit read in context. The brief's named files are among them
  (`legendaries.json`, `adopted_legendary_sites.json` incl. `sweep_sites` and `catalogue_2026_10_06`, `structures.json`,
  `spawns.json`, `entei_boss.json`, `dimension_overrides.json`, `hoopa_cradle.json`, the Rift files,
  `mythical_starters.json`, `rewards.json`). A mention that is a list (the water-mount riding list, drop fixes, the
  key ball's "never tagged" list) is not a home. **LegendaryMonuments and LumyMon altars**: the strings of both jars
  were scanned; species with many hits are exactly the altar species the catalogue already accounts for
  (Gen 1-4 legendaries, Necrozma, the Crown trio, Eternatus, Regieleki, Regidrago, the Ruinous four); every other
  species appears once (a list). Which altar templates are loaded and where they went is
  `adopted_legendary_sites.json` `catalogue_2026_10_06`, relayed, not re-read.

## The answer

| Group | Count |
|---|---|
| **A. Usable and unhomed** | **53** (Eternatus among them, but OUT by the owner) |
| B. Usable but homed (adopted, authored, planned, decided, or a starter line) | 44 |
| C. Unusable today: no model in what players get; **all 28 "usable if AllTheMons ships"** | 28 |

**Every one of the 28 in C has its only model in `ATMxMSD RP.zip`**, so one delivery decision (ADR-006 subset, or
the owner's ATM v4.0 hash route, STATE "Client models") moves all 28 into A. Group C holds the best water theme in the
catalogue (Manaphy and Phione) and seven of the eleven Ultra Beasts.

## Corrections to the companion notes and documents (the disagreements are findings)

1. **`ultra-beasts-1.8.0.md` says the ATMxMSD pack is "in the client pack"** and concludes that the Ultra Beasts "can
   be dungeon bosses with no new dependency". ATMxMSD is in the *built, undelivered* subset manifest; our overlay's
   `default_packs` does not enable it (`modpack/config/resourcepackoverrides.json`, the `ATMxMSD RP.zip` key appears
   only in `pack_overrides`). **Today only four of the eleven render: Poipole and Naganadel (jar), Kartana
   (MissingMons RP) and Celesteela (PlanetaCobblemon RP).** The other seven are dolls. That note also says it read the
   live server's `mods/`; this one did not.
2. **`legendary-species-1.8.0.md:76-78`** lists every Ultra Beast but Poipole, Naganadel and Kartana as a doll:
   **Celesteela renders** (PlanetaCobblemon RP, `bedrock/species/` path, as the paradox note found for Iron Hands,
   Jugulis and Boulder). It also groups "the Ruinous four" as implemented and modelled through MSD or Cobblemon:
   **Chi-Yu is implemented only by the DP and modelled only by CavsCobbleMons RP**; Ting-Lu has MSD and Cavs.
3. **`NETHER_DUNGEON_SCOPE.md:191`** assumes that Cresselia, Shaymin, Dialga, Palkia, Regieleki, Regidrago, Deoxys
   and Jirachi "ship in Cobblemon itself". **Only Regieleki and Regidrago do.** Dialga, Palkia, Deoxys and Shaymin are
   implemented by MSD (and the DP); **Cresselia only by the DP** (model: CavsCobbleMons RP); **Jirachi only by the DP,
   with no model** (group C).
4. Re-confirmed, not new: Walking Wake and Iron Leaves render from the jar (their posers are compiled classes, which a
   JSON-only check misses); Magearna and Zeraora have a base resolver only in ATMxMSD.

## The inventory

Columns: **Kind** leg / myth / UB / paradox. **Implemented by**: jar = the Cobblemon jar's own file, MSD, DP.
**Model today**: the source(s) a player's client draws it from. **Home**: from the repository (Method). **Dungeon fit**:
this unit's suggestion, one line, for the owner's encounter kinds (water/Dive, boss, hidden reward, parkour-guarded
shrine); nothing in that column is decided.

### A. Usable and unhomed: 53

| Species | Kind | Type | BST | Catch | Implemented by | Model today | Inherited DP spawn (level, bucket, where) | Home | Dungeon fit |
|---|---|---|---|---|---|---|---|---|---|
| Ho-Oh | leg | fire/flying | 680 | 3 | DP, MSD, jar | jar | label only (weight 0) 60-70 | none (bell_tower not loaded); Nether scope: rotation slot | Parkour-guarded shrine (a burnt tower climb to the roof) or Nether rotation boss |
| Raikou | leg | electric | 580 | 3 | DP, MSD | MSD | 60 ultra-rare, structure-gated | none (burned_tower is Johto, disabled); Nether scope: rotation slot | Boss: an Entei-pattern room, storm-themed (Entei's sibling) |
| Suicune | leg | water | 580 | 3 | DP, MSD | MSD | 60 ultra-rare, structure-gated | none; Nether scope: rotation slot | **Dive lake**: the purifier at the bottom of the clearest lake; or an Entei-pattern boss |
| Deoxys | myth | psychic | 600 | 3 | DP, MSD | MSD | label only (weight 0) 75-80 | none (Hoenn meteorite not loaded) | Hidden reward in a meteor crater; formes (MSD) suit a boss |
| Arceus | myth | normal | 720 | 3 | DP, MSD | MSD | label only (weight 0) 70 | none (temple_of_sinnoh unplaced: 18 plates, no source); Nether scope: capstone, not a boss | Capstone: plates as dungeon drops open its temple (NETHER_DUNGEON_SCOPE section 9) |
| Cresselia | leg | psychic | 580 | 3 | DP | Cavs RP | label only (weight 0) 40-65 | none (fullmoon_island not loaded) | Hidden reward on a crescent isle at full moon; pairs with Darkrai (homed) |
| Dialga | leg | steel/dragon | 680 | 3 | DP, MSD | MSD, Pokemans RP | label only (weight 0) 70 | none (spear_pillar not loaded) | Boss of The Temple Calendar (dungeon 5: "inside the day it measures") |
| Palkia | leg | water/dragon | 680 | 3 | DP, MSD | MSD, Pokemans RP | label only (weight 0) 70 | none (spear_pillar not loaded) | **Dive lake** (a space pearl under the water) or boss of The Street That Ends at Nothing |
| Shaymin | myth | grass | 600 | 45 | DP, MSD | MSD, MissingMons RP | label only (weight 0) 50-55 | none (flower_paradise not loaded) | Hidden reward in a flower meadow; catch 45, gentle |
| Cobalion | leg | steel/fighting | 580 | 3 | DP, MSD | MSD | 50-70 ultra-rare, windswept_forest | none | Swords of Justice: one of three guarded shrines (cave) |
| Genesect | myth | bug/steel | 600 | 3 | MSD | MSD | 48-68 ultra-rare, is_dripstone | none by us; inherited DP fossil revive (dome fossil + dubious disc + nether star) | Boss in a lab; mind the inherited fossil route (two authors) |
| Keldeo | myth | water/fighting | 580 | 3 | DP, MSD | MSD | 60 ultra-rare, sakura_grove; 80 ultra-rare, sakura_grove | none | **Dive lake**: a sword in a spring, the prize after the three Swords |
| Kyurem | leg | dragon/ice | 660 | 3 | DP, MSD | MSD | 66-78 ultra-rare, ice_spikes | none (Coldwater Station first pick, superseded by Kyogre) | Boss: a frozen cavern (dragon/ice) |
| Landorus | leg | ground/flying | 600 | 3 | MSD | MSD | 50-60 ultra-rare, is_badlands | none | Forces of Nature: the third, after both |
| Meloetta | myth | normal/psychic | 600 | 3 | MSD | MSD | 50-55 rare, sunflower_plains | none | Hidden reward behind a music puzzle |
| Reshiram | leg | dragon/fire | 680 | 3 | DP, MSD | MSD | 70-84 ultra-rare, is_mountain | none | Boss: twin-room dungeon with Zekrom (ideal and truth) |
| Terrakion | leg | rock/fighting | 580 | 3 | DP, MSD | MSD | 50-70 ultra-rare, is_savanna | none | Swords of Justice: guarded shrine (cliff) |
| Thundurus | leg | electric/flying | 580 | 3 | MSD | MSD | 50-60 ultra-rare, is_mountain | none | Forces of Nature: parkour storm shrine |
| Tornadus | leg | flying | 580 | 3 | MSD | MSD | 50-60 ultra-rare, is_ocean | none | Forces of Nature: parkour sky shrine (ocean-surface DP spawn) |
| Victini | myth | psychic/fire | 600 | 3 | DP, MSD | MSD | 50 ultra-rare, crimson_forest | none | Hidden reward: a small mythical in a ruined keep |
| Virizion | leg | grass/fighting | 580 | 3 | DP, MSD | MSD | 50-70 ultra-rare, is_forest | none | Swords of Justice: guarded shrine (forest) |
| Zekrom | leg | dragon/electric | 680 | 3 | DP, MSD | MSD | 70-84 ultra-rare, is_mountain | none | Boss: twin of Reshiram |
| Diancie | myth | rock/fairy | 600 | 3 | DP, MSD | MSD | 45-68 ultra-rare, lush_caves | none | Hidden reward at the back of a gem mine (The Night Shift's top band) |
| Volcanion | myth | fire/water | 600 | 3 | DP, MSD | MSD | 70 ultra-rare, is_mountain | none | **Dive lake**: a boiling crater lake (fire/water, steam) |
| Xerneas | leg | fairy | 680 | 45 | DP, jar | Hydro RP, jar | 65-75 ultra-rare, is_floral | none | Boss or reward of Under the Patriarch (a great tree); catch 45 |
| Yveltal | leg | dark/flying | 680 | 45 | DP, MSD | MSD | 65-75 ultra-rare, is_spooky | none | Boss of Under the Patriarch (dark forest); catch 45 |
| Zygarde | leg | dragon/ground | 600 | 3 | DP, MSD | Hydro RP, MSD | 1-10 ultra-rare, dripstone_caves | none | Collection reward: cells as dungeon drops (MSD has `zygarde_cell`) |
| Celesteela | UB | steel/flying | 570 | 45 | DP | Planeta RP | 65-80 ultra-rare, End | none | UB boss caught only with the Beast Ball (the key ball's own lore) |
| Kartana | UB | grass/steel | 570 | 45 | DP | MissingMons RP | 55-70 ultra-rare, cherry_grove | none | UB boss (Beast Ball) |
| Marshadow | myth | fighting/ghost | 600 | 3 | MSD | MSD | 45-68 ultra-rare, is_deep_dark | none | Boss of a lamp-lit dark dungeon (The Night Shift) |
| Tapu Bulu | leg | grass/fairy | 570 | 3 | MSD | MSD | 50-70 ultra-rare, is_river | none | Island guardian shrine |
| Tapu Fini | leg | water/fairy | 570 | 3 | MSD | MSD | 50-70 ultra-rare, is_river | none | **Dive lake**: guardian under a misted island lake |
| Tapu Koko | leg | electric/fairy | 570 | 3 | MSD | MSD | 50-70 ultra-rare, is_savanna | none | Island guardian shrine (SIDE_ISLANDS story reason) |
| Tapu Lele | leg | psychic/fairy | 570 | 3 | MSD | MSD | 50-70 ultra-rare, is_floral | none | Island guardian shrine |
| Eternatus | leg | poison/dragon | 690 | 255 | DP, MSD | MSD | label only (weight 0) 70-90 | OUT by the owner until a Galar Particle supply exists (cocoon in the End) | Out (owner); a dungeon could become the particle supply |
| Regidrago | leg | dragon | 580 | 3 | jar | jar | label only (weight 0) 70-80 | none (split_decision_temple not loaded) | Sealed chamber: extends the Regi set |
| Regieleki | leg | electric | 580 | 3 | jar | jar | label only (weight 0) 70-80 | none (split_decision_temple not loaded) | Sealed chamber: extends the authored Regi set (legendaries.json archetype) |
| Zacian | leg | fairy | 660 | 10 | DP, MSD | MSD | 65-80 ultra-rare, dark_forest | none | Twin shrine with Zamazenta; catch 10 |
| Zamazenta | leg | fighting | 660 | 10 | DP, MSD | MSD | 65-80 ultra-rare, dark_forest | none | Twin shrine with Zacian; catch 10 |
| Zarude | myth | dark/grass | 600 | 3 | jar | jar | 70 ultra-rare, jungle | none | Boss of The Temple Calendar (jungle temples) |
| Enamorus | leg | fairy/flying | 580 | 3 | MSD | MSD | 50 ultra-rare, is_mountain | none | Parkour sky shrine (fourth Force of Nature) |
| Fezandipiti | leg | poison/fairy | 555 | 3 | DP, MSD | MSD | 70-75 ultra-rare, is_peak | none | Loyal Three gauntlet |
| Iron Boulder | paradox | rock/psychic | 590 | 10 | DP | Planeta RP | 45-60 ultra-rare, dark_forest | none | Paradox threat or prize (Under the Patriarch, dark forest) |
| Iron Hands | paradox | fighting/electric | 570 | 50 | DP | Planeta RP | 45-60 rare, desert | none | Paradox threat or prize |
| Iron Jugulis | paradox | dark/flying | 570 | 30 | DP | Planeta RP | 70-75 rare, is_mountain | none | Paradox threat or prize |
| Iron Leaves | paradox | grass/psychic | 590 | 5 | jar | jar | 50-75 ultra-rare, is_forest | none | Paradox forest threat or prize |
| Koraidon | leg | fighting/dragon | 670 | 3 | DP, MSD | MSD | 40 ultra-rare, beach | none; DUNGEONS.md Q14 open | Paradox-band dungeon prize; owner Q14 |
| Miraidon | leg | electric/dragon | 670 | 3 | DP, MSD | MSD | 40 ultra-rare, beach | none; DUNGEONS.md Q14 open | Paradox-band dungeon prize; owner Q14 |
| Munkidori | leg | poison/psychic | 555 | 3 | DP, MSD | MSD | 70-75 ultra-rare, is_jungle | none | Loyal Three gauntlet |
| Ogerpon | leg | grass | 550 | 5 | MSD | MSD | 50-75 ultra-rare, is_lush | none | Hidden reward after the Loyal Three (masks) |
| Okidogi | leg | poison/fighting | 555 | 3 | DP, MSD | MSD | 70-75 ultra-rare, is_savanna | none | Loyal Three gauntlet: a trio of thugs, then Ogerpon |
| Terapagos | leg | normal | 450 | 255 | DP, MSD | MSD | 55-75 ultra-rare, is_cave | none | Boss in a crystal cavern; catch 255 |
| Walking Wake | paradox | water/dragon | 590 | 5 | jar | jar | 60-75 ultra-rare, is_mountain | none | **Dive lake** paradox (the ancient Suicune); paradoxes are dungeon content |

### B. Usable but homed: 44

| Species | Kind | Type | Catch | Model today | Home |
|---|---|---|---|---|---|
| Articuno | leg | ice/flying | 3 | jar | adopted tower on the Frostpeak summit (adopted_legendary_sites `adopted_articuno_shrine`) |
| Mew | myth | psychic | 45 | jar | adopted temple (`adopted_mew_temple`, Champion door, Origin Fossil) |
| Mewtwo | leg | psychic | 3 | jar | DP fossil revive (ancient_dna + cloning_catalyst); "Mewtwo stays on the fossil route" (entei_boss.json decision) |
| Moltres | leg | fire/flying | 3 | jar | adopted tower in the Craters (`adopted_moltres_tower`); Nether copies stay |
| Zapdos | leg | electric/flying | 3 | jar | adopted tower, Fungal Isle east coast (`adopted_zapdos_tower`) |
| Celebi | myth | psychic/grass | 45 | MissingMons RP | Route 1 sapling (sapling_celebi.json) + `celebi_wake` (legendaries.json) |
| Entei | leg | fire | 3 | MSD | dungeon boss, built (entei_boss.json) |
| Lugia | leg | psychic/flying | 3 | jar | legendaries.json (blocked: no seabed) |
| Groudon | leg | ground | 3 | MSD | legendaries.json, the Craters |
| Kyogre | leg | water | 3 | MSD | planned): KYOGRE_CAVE.md dive cave behind a sea-floor arch, Coldwater Station lead |
| Latias | leg | dragon/psychic | 3 | MSD, jar | Shrew Station Eon shrine (research_station.json) |
| Latios | leg | dragon/psychic | 3 | MSD, jar | Shrew Station Eon shrine |
| Rayquaza | leg | dragon/flying | 3 | MSD, jar | planned): KYOGRE_CAVE.md sky island behind a relic arch |
| Regice | leg | ice | 3 | jar | legendaries.json sealed chamber |
| Regirock | leg | rock | 3 | jar | legendaries.json sealed chamber |
| Registeel | leg | steel | 3 | jar | legendaries.json (blocked: the Rift plan) |
| Azelf | leg | psychic | 3 | MSD | legendaries.json lake grotto (Marshy Marsh) |
| Darkrai | myth | dark | 3 | MSD | Newmoon Island over the Fungal Isle (`sweep_newmoon_island`) |
| Giratina | leg | ghost/dragon | 3 | Hydro RP, MSD | sweep shrine, Glacial Tear (`sweep_giratina_shrine`) |
| Heatran | leg | fire/steel | 3 | MSD | decided): dungeon boss after Entei (DUNGEONS.md row 7, designed) |
| Mesprit | leg | psychic | 3 | MSD | legendaries.json lake grotto (Arrow Lake) |
| Regigigas | leg | normal | 3 | jar | legendaries.json, beside the Displaced City |
| Uxie | leg | psychic | 3 | MSD | legendaries.json lake grotto (Lake Tilpey) |
| Hoopa | myth | psychic/ghost | 3 | MSD | the Hoopa cradle (hoopa_cradle.json) |
| Cosmoem | leg | psychic | 3 | MSD | starter line (Cosmog) |
| Cosmog | leg | psychic | 3 | MSD | mythical starter (mythical_starters.json) |
| Lunala | leg | psychic/ghost | 3 | MSD | starter line (Cosmog) |
| Naganadel | UB | poison/dragon | 45 | jar | starter line (Poipole) |
| Necrozma | leg | psychic | 3 | Hydro RP, MSD | dawn and dusk towers (adopted, one per server) |
| Poipole | UB | poison | 45 | jar | mythical starter + placement sites at the two towers (spawns.json) |
| Silvally | leg | normal | 3 | MSD | starter line (Type: Null) |
| Solgaleo | leg | psychic/steel | 3 | MSD | starter line (Cosmog) |
| Type: Null | leg | normal | 3 | MSD | mythical starter (also a DP fossil revive) |
| Melmetal | myth | steel | 3 | MSD | starter line (Meltan) |
| Meltan | myth | steel | 3 | MSD | mythical starter |
| Calyrex | leg | psychic/grass | 3 | MSD | crown cemetery (adopted) |
| Glastrier | leg | ice | 3 | MSD | crown spire (adopted, hidden) |
| Kubfu | leg | fighting | 3 | MSD, Pokemans RP | mythical starter |
| Spectrier | leg | ghost | 3 | MSD | crown cemetery, once per player (spectrier_cap.json) |
| Urshifu | leg | fighting/dark | 3 | MSD, Pokemans RP | starter line (Kubfu) |
| Chien-Pao | leg | dark/ice | 6 | MSD | Nether shrine |
| Chi-Yu | leg | dark/fire | 6 | Cavs RP | Nether shrine (stakes), stays where it generates |
| Ting-Lu | leg | dark/ground | 6 | Cavs RP, MSD | Nether shrine |
| Wo-Chien | leg | dark/grass | 6 | MSD | Nether shrine |

### C. Unusable today (no model in what players get): 28

| Species | Kind | Type | BST | Catch | Implemented by | Model today | Inherited DP spawn (level, bucket, where) | Home | Dungeon fit |
|---|---|---|---|---|---|---|---|---|---|
| Jirachi | myth | steel/psychic | 600 | 3 | DP | none (ATMxMSD only: usable if AllTheMons ships) | label only (weight 0) 75-80 | none | Hidden reward (a wish) |
| Manaphy | myth | water | 600 | 3 | DP | none (ATMxMSD only: usable if AllTheMons ships) | label only (weight 0) 50 | none; a postgame charter to an appearing island is proposed, unsited (ferries.json) | **Dive** sea temple, best water theme of all |
| Phione | myth | water | 480 | 30 | DP | none (ATMxMSD only: usable if AllTheMons ships) | label only (weight 0) 50 | none; same proposed charter as Manaphy | **Dive**, with Manaphy |
| Blacephalon | UB | fire/ghost | 570 | 30 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 55-62 ultra-rare, is_spooky | none | UB boss (Beast Ball) |
| Buzzwole | UB | bug/fighting | 570 | 45 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 60-70 ultra-rare, is_jungle | none | UB boss (Beast Ball) |
| Guzzlord | UB | dark/dragon | 570 | 45 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 70-75 ultra-rare, End | none | UB boss (Beast Ball) |
| Magearna | myth | steel/fairy | 600 | 3 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 50-70 ultra-rare, is_taiga; 70-85 ultra-rare, is_taiga | none | Reward in a sealed vault |
| Nihilego | UB | rock/poison | 570 | 45 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 60-78 ultra-rare, is_ocean | none | **Dive**: an ultra wormhole on the sea floor (DP spawns it submerged) |
| Pheromosa | UB | bug/fighting | 570 | 45 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 55-65 ultra-rare, blooming_valley; 55-65 ultra-rare, End | none | UB boss (Beast Ball) |
| Stakataka | UB | rock/steel | 570 | 30 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 60-72 ultra-rare, deep_dark | none | UB boss (Beast Ball) |
| Xurkitree | UB | electric | 570 | 45 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 58-72 ultra-rare, End | none | UB boss (Beast Ball) |
| Zeraora | myth | electric | 600 | 3 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 45-85 ultra-rare, is_badlands; 45-85 ultra-rare, is_forest | none | Boss (electric) |
| Brute Bonnet | paradox | grass/dark | 570 | 50 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 45-60 rare, is_jungle | none | Paradox dungeon threat or prize |
| Flutter Mane | paradox | ghost/fairy | 570 | 30 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 45-60 rare, is_spooky | none | Paradox dungeon threat or prize |
| Gouging Fire | paradox | fire/dragon | 590 | 10 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 70-75 ultra-rare, basalt_deltas | none | Paradox dungeon threat or prize |
| Great Tusk | paradox | ground/fighting | 570 | 30 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 40-65 rare, is_arid | none | Paradox dungeon threat or prize |
| Iron Bundle | paradox | ice/water | 570 | 50 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 50-70 rare, is_freezing | none | Paradox; a **Dive** candidate (ice/water) |
| Iron Crown | paradox | steel/psychic | 590 | 10 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 50-75 ultra-rare, is_lush | none | Paradox dungeon threat or prize |
| Iron Moth | paradox | fire/poison | 570 | 30 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 40-65 rare, is_hills | none | Paradox dungeon threat or prize |
| Iron Thorns | paradox | rock/electric | 570 | 30 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 40-65 rare, is_mountain | none | Paradox dungeon threat or prize |
| Iron Treads | paradox | ground/steel | 570 | 30 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 50-70 rare, is_arid | none | Paradox dungeon threat or prize |
| Iron Valiant | paradox | fairy/fighting | 590 | 10 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 55-70 rare, is_plains | none | Paradox dungeon threat or prize |
| Pecharunt | myth | poison/ghost | 600 | 3 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 60-80 ultra-rare, is_spooky | none | Boss (poison/ghost) |
| Raging Bolt | paradox | electric/dragon | 590 | 10 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 60-75 ultra-rare, is_arid | none | Paradox dungeon threat or prize |
| Roaring Moon | paradox | dragon/dark | 590 | 10 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 55-70 rare, is_mountain | none | Paradox dungeon threat or prize |
| Sandy Shocks | paradox | electric/ground | 570 | 30 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 60-70 rare, is_arid | none | Paradox dungeon threat or prize |
| Scream Tail | paradox | fairy/psychic | 570 | 50 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 40-65 rare, is_floral | none | Paradox dungeon threat or prize |
| Slither Wing | paradox | bug/fighting | 570 | 30 | DP | none (ATMxMSD only: usable if AllTheMons ships) | 47-62 ultra-rare, is_jungle; 66-76 rare, crimson_forest | none | Paradox dungeon threat or prize |

## Shortlist: the best fits by theme (all usable today, all unhomed)

Chosen for theme first, then for what is already built to carry them. Every one is catch rate 3 unless stated, so a
dungeon catch leans on the Beast Ball key (x5 on a tagged dungeon boss, `data/key_ball.json`, NOT RUN) and on the
level cap (a catch above the thrower's cap is blocked, `docs/mechanics/LEAGUE_LEVEL_CAP.md`, relayed).

**The Dive lake (the owner's case)**

1. **Suicune** (water, MSD). The purifier of water: the obvious "something at the bottom of the clearest lake". The
   owner named the beasts; the Nether scope offers it as a rotation boss instead, so pick one home, not both.
2. **Tapu Fini** (water/fairy, MSD). A guardian under a misted lake; its own mist is the "something is down there".
3. **Keldeo** (water/fighting, MSD). A sword in a spring; the natural prize after a Swords of Justice set (item 10).
4. **Volcanion** (fire/water, MSD). A boiling crater lake: steam and a hot, lit bed read as "something lives here".
5. **Palkia** (water/dragon, MSD; also Pokemans RP). Space folded under water; equally strong as a boss (item 7).
6. **Walking Wake** (water/dragon paradox, jar model, catch 5). The paradox Suicune: fits "paradoxes are dungeon
   content" and a lake run in one go.

Not Dive candidates today: **Kyogre** is homed (planned dive cave, `docs/world-building/KYOGRE_CAVE.md`), **Lugia**
is homed (blocked on a seabed), the **lake trio** are homed in lake grottos already. **Manaphy, Phione** (best water
theme of all), **Nihilego** (the DP already spawns it submerged in ocean) and **Iron Bundle** are group C: they wait on
AllTheMons.

**Bosses**

7. **Raikou** (electric, MSD). Entei's sibling room: the cheapest boss on the list (the Entei engine, a storm dressing).
8. **Ho-Oh** (fire/flying, jar model). A burnt-tower climb to the roof (parkour-guarded) or a Nether rotation slot.
9. **Dialga** (steel/dragon, MSD). The Temple Calendar's boss: "the run is inside the day it measures" (DUNGEONS.md
   dungeon 5). Palkia is its pair for The Street That Ends at Nothing (dungeon 2, a city out of place).
10. **Yveltal** (dark/flying, MSD, catch 45) or **Xerneas** (fairy, jar model, catch 45) for Under the Patriarch
    (dungeon 3, the great dark oak). Zarude (dark/grass, jar model) is the jungle-temple alternative.
11. **Marshadow** (fighting/ghost, MSD). The thing in the lit lower level of The Night Shift (dungeon 1); a late band
    only (its DP level is 45-68).
12. **Celesteela, Kartana** (UB, catch 45). Ultra Beasts as the bosses the Beast Ball is named for; the only two
    non-starter UBs that render today.

**Hidden reward and parkour-guarded shrine**

13. **Regieleki, Regidrago** (jar models). Two more `sealed_chamber`s beside the authored Regi set
    (`data/legendaries.json`): the archetype, gate and audit exist; their own temple is not loaded.
14. **Cobalion, Terrakion, Virizion** then **Keldeo**: three guarded shrines and a prize, the Swords of Justice; or the
    Forces of Nature (**Tornadus, Thundurus, Landorus**, plus Enamorus) as parkour sky shrines.
15. **Diancie** (rock/fairy) at the back of a gem mine, **Shaymin** (grass, catch 45) in a flower meadow, or
    **Cresselia** (psychic, Cavs RP) on a crescent isle at full moon: small finds, not fights.

Left out on purpose: **Arceus** (a capstone: its temple's 18 plates as dungeon drops, NETHER_DUNGEON_SCOPE section 9,
not a boss); **Eternatus** (OUT by the owner until a Galar Particle supply exists; a dungeon drop could become that
supply); **Koraidon, Miraidon** (owner's Q14 in DUNGEONS.md); **Genesect** (the DP already revives it from a fossil:
a dungeon home would be a second author); **Mewtwo** (homed on the fossil route).

## "Make it OBVIOUS something is down there": what already exists (design notes, not tested)

- **The lake grotto archetype is built and audited** (`tools/legendaries.py` `lake_grotto`,
  `docs/mechanics/LEGENDARIES.md` section 2): a mouth in the bed, a stone-sleeved shaft, a passage of at most 20, a
  pool and a dry air chamber (a battle outlasts Surf's air, about 61 s at depth, relayed from `WATER_MAP.md`). The
  mouth needs a `keep` zone in `data/water_shape.json`, or the water export rewrites the bed (Uxie's block).
- **Dive is a party capability, not an item**: a species whose riding behaviour is `submarine`
  (`data/water_mounts.json` `dive`: Blastoise, Cloyster, Dhelmise, Dondozo, Kingler, Relicanth, Seaking, Toxapex,
  Wailmer, Wailord; in-game riding not checked).
- Ways to make the bottom read from the surface, all vanilla behaviour from general knowledge, **ASSUMED, not tested
  here**: lit lanterns on the bed (the repo's rule is lanterns, never light blocks); an upward **bubble column** from
  soul sand over the mouth, visible from the shore; a sea-floor ring that glows; and a **conduit**, which also gives
  water breathing nearby, so it would remove the air-chamber problem and the Dive tension with it: an owner's call.
- The legendary's own NBT can be dressed dormant and visible (`PoseType: SLEEP`, `NoAI`, `PersistenceRequired`, proven
  across a restart, EXP-023/EXP-046, relayed): a sleeping Suicune seen through clear water is the strongest "something
  is down there" and needs nothing new.

## Not verified

- Every "model today" cell: a file check across the jars and the 32 enabled packs; not seen in game, and pack order
  (a higher pack replacing a resolver) was not simulated.
- That COBBLEVERSE-DP-v31 is enabled in staging (relayed); the 36 species implemented only by the DP need it
  (every species in group C, plus Celebi, Cresselia, Chi-Yu, Kartana, Celesteela, Iron Hands, Iron Jugulis and Iron
  Boulder).
- That the inherited live spawns actually occur in our world (biome painting not sampled per species).
- Whether any of these battles normally in Showdown with its ability (Beast Boost, Protosynthesis and the rest).
- The altar strings scan reads names, not behaviour; which altar each species uses is the catalogue's, relayed.
