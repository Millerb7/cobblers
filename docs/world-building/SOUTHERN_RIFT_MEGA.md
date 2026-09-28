# The southern Rift's mega site: the mega town, the great mine and its Megas

**Status: decided 2026-09-27 (section 11); the prototype slice of section 10 is generated offline on the branch
`world/gulch-prototype` (section 12): not installed, not in any world, not seen in game.** It answers the owner's request of
2026-09-27: the mega stone mine was built in the wrong place (the dig camp's west spur); it belongs in the gulch of
`SOUTHERN_RIFT.md`. The dig camp keeps a small seam, found early and not usable yet. The southern site has three
parts: a mega town, a large mine and hostile roaming Megas, joined by a material chain.

Labels: **VERIFIED** means a file, a line, a jar read or an in-game result, cited. **ASSUMED** means design judgement
or a fact not read here. Coordinates come from data files or from the canonical heightmap (`tools/ground.py`,
heightmap `0d9b5f1e…`, read 2026-09-27), never from a world.

## 0. What was read

| Source | What it gave |
| --- | --- |
| `docs/world-building/SOUTHERN_RIFT.md` (all) and what it cites: `data/rift_regions.json`, `data/rift_sculpt.json`, `docs/mechanics/RIFT_ZONES.md` | the existing gulch design, the zones and entrances |
| `data/rift_mines.json`, `tools/rift_mines.py` (docstring), `tools/rift_mines_audit.py` (docstring), `tests/test_rift_mines*.py` | what stands in the west spur |
| `docs/mechanics/STONE_ECONOMY.md`, `docs/decisions/ADR-003-evolution-stone-supply.md` (amended), `docs/mechanics/EVOLUTION_STONES.md` | the evolution-stone system and its restoring faces |
| `data/spawns.json`, `modpack/config/cobblemon/starters.json` | which species can be had here |
| `data/sapling_celebi.json` | the "found early, not usable yet" pattern |
| `docs/research/CASINO.md` | the score-currency idea (the token question) |
| `data/progression.json` | the badge flags and the leaders' first-win rewards |
| `experiments/EXP-036-wild-mega/README.md`, `docs/research/notes/wild-mega-pokemon.md` | the wild-Mega proof and its research |
| `server/config/mods/mega_showdown/config.json`, `server/config/mods/fightorflight.json5` | the values the server runs, recorded in the repo (`python tools/server_config_record.py check` reported 0 disagreements on 2026-09-26, `docs/STATE.md:149`); the server's own `config/` was not opened |
| **Mega Showdown jar** `mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar`, SHA-1 `50b2012b5207706fd93d42dfad73f94aa294c7a2` (the hash `modpack/manifest/overlay.json:259` pins) | recipes, loot tables, tags, structures, worldgen, Mega definitions |
| **ZAMegas jar** `zamega-fabric-1.7.7+1.8.jar`, SHA-1 `01ee9cf94c7af2c6a772f08d5db6f1a8efa4ff18` (`overlay.json:478`) | 11 more Mega stones |

Both jars were read with Python's `zipfile` from a client profile copy (`%APPDATA%\ModrinthApp\profiles\Fabric
1.21.10\mods\`), whose hashes match the pins; the server's `mods/` folder was only listed. No server, world or live
save was touched.

**The review-list note about the mine placement was not found** as a separate note. The placement is recorded in
`docs/STATE.md:128` ("The owner's request moves the mine from SOUTHERN_RIFT.md's gulch to the spur") and in
`SOUTHERN_RIFT.md:10-14` ("Moved, 2026-09-27"). Both now describe the move this document proposes to reverse.

---

## 1. What SOUTHERN_RIFT.md already specifies

It is a design proposal of 2026-09-25, nothing built (`SOUTHERN_RIFT.md:3`). For the gulch it specifies:

- **The place.** The owner's own map names the region `mega_stone_mine_the_gulch`: bbox x4039-4454 z4513-4958,
  ground y83-110, median y89, seed (4330, 4800) (`data/rift_regions.json:205-222`). It is the south-east branch,
  "about 290 long below the split, floor about 80 wide, 27-32 deep", "the crystal garden: Distortion trees and crystal
  outcrops" (`SOUTHERN_RIFT.md:100-101`). The sculpt already carries a guarded entrance for it: `gulch_mouth`, a canyon
  near (4240, 4740), gap 44, 7 wide, guard "Gulch lookout", "A canyon mouth into the mega stone mine"
  (`data/rift_sculpt.json:56-58`).
- **A town, "Gulch Junction"** (working name), recommended at the junction where Victory Road passes from the arm into
  the stem, (4076, 4653) to the split about (4180, 4745), with the mine opening from its back street
  (`SOUTHERN_RIFT.md:67-96`): the Gate (Centre, Mart, notice wall), the Crystal Yard (sorting sheds, crystal behind
  glass), Rock Row (bunkhouses cut into the wall, no timber), the Dissenters' camp, the Mine Gate, and a rail-less Haul
  Road north to the Deep. No flat site was searched.
- **The mine** (`SOUTHERN_RIFT.md:98-165`): the Crystal Garden on the surface (Distortion trees, outcrops, a megaroid
  holding `keystone_ore` if the Key Stone goes here); underground, a cave network on `tools/vr_caves.py`'s model falling
  40-60 below the floor: the Adit Hall, the Galleries with `mega_stone_crystal` faces on ADR-003's reset pattern, 5-6
  dead-end Mega Chambers each with one Enraged Mega, and the Heart. Three guardian modes per chamber (`wild_mega`,
  `trainer_echo`, `outlier`). Raw stones from the faces; the Key Stone from `keystone_ore`; a clerk or reward as the
  no-crafting source.
- **The gate:** recommended Z2 (8 badges) through the town, with G3's tip entrance leading only to the surface garden
  (Z3, 60 species) (`SOUTHERN_RIFT.md:162-165`).
- **Findings still standing** (`SOUTHERN_RIFT.md:54-65`): `gulch_mouth` lies on Victory Road's (Z2) side of the
  branch-mouth line; Z2 has four sculpted entrances and one guard; Z3's gate (about the fifth gym) and its roster
  (54-56) disagree.
- **Eight owner decisions** (`SOUTHERN_RIFT.md:216-225`), among them the town's site, the mine's gate, the guardian
  mode, where the Key Stone lives, and the Heart as postgame.

What it does **not** specify, and this document adds: what the town does with the material, the chain from ore to
stone, which stones matter, the effort, a reset that is not finite, roaming (not chamber-bound) Megas, and the cost of
moving the mine back.

## 2. Record correction: a wild Mega works

The owner tested a wild Mega in game on staging and it worked (2026-09-27, reported by the owner; not logged). With
EXP-036 (staging, 2026-09-25: a spawned Mega Charizard X kept form `megax` and Tough Claws, the battle started and it
stayed Mega), the wild Mega itself is settled. What is still unproven in play: a thrown ball refused, the state after the
battle, the enrage by Fight or Flight's config, and a Mega spawned by a function rather than typed over RCON.

Corrected in this commit, minimally: `docs/STATE.md`, `SOUTHERN_RIFT.md`, `EXP-036`, `EXP-035` row 22,
`docs/research/EXPERIMENT_BACKLOG.md`, `docs/research/notes/wild-mega-pokemon.md` and `data/rift_mines.json`.

---

## 3. The site

### 3.1 The gulch, measured

| Part | Where | Ground (canonical heightmap) |
| --- | --- | --- |
| The gulch floor on the tip side of the branch-mouth line (4373, 4691)-(4196, 4927) | x4150-4470, z4600-4980 | 19,513 columns at or under y92; min y88, median y89 |
| Flattest town square inside it | 61 x 61 centred (4308, 4848) | y88-91 (range 3) |
| Next best | 91 x 91 centred (4331, 4859) | y88-99 (range 11) |
| The east plateau above the mine | x4380-4640, z4690-4960 | y120-146; median y126 |
| The junction (SOUTHERN_RIFT's town window, Z2) | 121 x 121 centred about (4100, 4655) | y83-85 (range 2); a 181 at (4129, 4651) spans y83-93 |
| Split / gulch_mouth / tip (G3) | (4180, 4745) / (4240, 4740) / (4390, 4894) | y90 / y88 / y91 |

Every point above and every proposed hall below lies in sub-region `rift_south_east_arm` (point-in-polygon on
`data/regions.json`). The town site is 164 blocks from the split, which Victory Road's players pass.

### 3.2 The sketch

```
                        north: the stem -> Victory Road (Z2, 8 badges)
                                  ^
      junction (4076,4653)  ------+------ split (4180,4745)
                                    \  zone line (re-traced, see 3.3)
          gulch_mouth canyon ~(4240,4740), guard: Gulch lookout (6 badges)
                                      \
                        THE MEGA TOWN (4308,4848) y88, floor 61x61 + rock-cut quarters in the walls
                          |  the Cutters' adit, south-east
                          v
   floor y88-90 ~~~~~~~~~ Crystal Garden (surface) ~~~~~~~~~ megaroid crater ~~~ tip (4390,4894)
   ----------------------------------------------------------------------------------------------
   y62-80   Tally Hall (4350,4905)  lit, company works, no Megas
   y40-80   Cutting Floor (4420,4860) ==== Slag Gallery (4480,4780) ==== Echo (4560,4830, under the plateau)
   y35-75                 Glass Nave (4500,4910) ======== Hot Workings (4590,4920, under the plateau)
   y15-45                              The Heart (4530,4870)
```

Cover over each hall's roof, from the heightmap: Tally Hall 9, Cutting Floor 13, Glass Nave 15, Slag Gallery 18, the
Heart 45, Echo 47, Hot Workings 51 (the repo's minimum is 4, `data/rift_mines.json` `cover_min`). All positions are a
proposal for a builder to model; none is carved or checked against a world.

### 3.3 The gate (a change to RIFT_ZONES)

**Recommended: the gulch becomes its own zone, opened by `gym6_cleared`, entered by the `gulch_mouth` canyon.**

- Z3 today is "60 species caught" with G3 at the tip (`RIFT_ZONES.md:46`). The tip has no sculpted descent; the
  `gulch_mouth` canyon is the sculpt's own guarded entrance and is already named for the mine. Move G3 there and gate it
  on the sixth badge, the badge whose leader gives the Key Stone (section 7.4). The owner earlier asked for the deeper
  mine "around badge five or six" (`data/rift_mines.json:73-77`).
- **Re-trace the branch-mouth line** so the canyon's foot and the town fall inside the gulch zone (today the canyon
  lies on the Z2 side, `SOUTHERN_RIFT.md:55-58`). Anyone in Z2 without eight badges is turned back by the zone check
  (`RIFT_ZONES.md:120-140`), so a six-badge player cannot walk up the stem to Victory Road. An eight-badge player holds
  the sixth badge, so Victory Road's players walk into the gulch freely: the town serves them too, 164 blocks off their
  road.
- The collectors' caught-count gate then has no pocket; move it to Z4 only, or drop the 60-species number (decision 3).
- **Alternative:** SOUTHERN_RIFT's Z2 gate (8 badges) with the town at the junction. It keeps the mine endgame, but the
  Key Stone (gym 6) would then wait two gyms for its first stone.

---

## 4. Part a: the mega town

**Working name: the Cutters' Gulch** (names are the owner's and Codex's, `HANDOVER_CODEX.md` item 26).

**Who lives there and what they do.** A lapidaries' town: people who cut the raw stone the gulch gives up into keyed
stones, each shaped to one kind of Pokemon. They are not the Compact and not miners by trade; the company digs, the
cutters work. Their fiction sits inside the stone economy's rules (`STONE_ECONOMY.md` §2: no site delivers a required
fact, miners have no theory, "recently" means a generation): the cutters can make a stone fit a Pokemon, and they
cannot say why it works. SOUTHERN_RIFT's Dissenters' camp stays (Nia's tents, the clinic); the Compact's haul road
leaves north with crystal for the Deep, which is the town's quiet quarrel.

| Quarter | What | Residents (dialogue is Codex's) |
| --- | --- | --- |
| **The Gate** | Centre, Mart, notice wall, the signpost to the split | Centre and Mart clerks (the `data/traders.json` `mart` stock) |
| **The Cutting Hall** | the town's heart: long benches, Mega Showdown `pedestal` blocks showing finished stones, a window onto the Crystal Garden | **the Cutters**: three bench masters whose trades turn raw stone into keyed stones (section 7) |
| **The Assay Counter** | weighs raw stone; the company's tally | the Assayer, who explains the rate and never buys raw stone |
| **Rock Row** | bunkhouses and a canteen cut into the east wall, over the floor | miners, the company foreman |
| **The Dissenters' camp** | tents, the field clinic | Nia and the dissenters (story beat) |
| **The Adit Head** | headframe, the Cutters' adit into the mine, the tally board | the adit keeper (a sign, or an NPC who warns about the Megas) |

**What it looks like.** A rock town, as the owner asked of the Craters: no timber. Masonry of Mega Showdown's own
meteorid set (`mega_meteorid_brick`, `polished_mega_meteorid_block`, `chiseled_mega_meteorid_brick`: craftable
building blocks, `data/mega_showdown/recipe/mega_meteorid_brick.json`, `polished_mega_meteorid_block.json`),
deepslate and tuff, copper trim; `dormant_crystal` in the Cutting Hall's windows (placed on staging in the Rift skin,
`DEEP_CITY.md:119`). The floor town stands on the 61-square at (4308, 4848); Rock Row and the Cutting Hall's back are
cut into the east wall, which climbs to y120-128 within 60 blocks. Lit as towns are (lanterns on posts, never light
blocks, `docs/STATE.md:97`); the mine below is not.

**Same system as the seven stone places, or its own? Its own, on the same machinery.**

- **Own:** the mega town makes no evolution stone and is not an eighth stone place. The seven places and their lag
  table (`STONE_ECONOMY.md` §3) stay as they are.
- **Shared machinery:** the restoring faces (`STONE_ECONOMY.md` §5.3, restore on approach, filtered `fill`, mandatory
  occupancy guard), the per-player floor through ADR-002's advancement spine (§4), the re-apply pattern, and the
  Exchange's rule that **a sold good is never bought back** (§8: otherwise a face prints money). One tick driver can run
  both sets of faces.
- **One trap to keep out:** Mega Showdown's `mega_meteorid_<stone>_ore` blocks drop Cobblemon evolution stones
  (VERIFIED, `data/mega_showdown/loot_table/blocks/mega_meteorid_*_ore.json`; `STONE_ECONOMY.md:30`), and the
  `mega_site` template's processor list turns 1 stone block in 11 into each of them
  (`data/mega_showdown/worldgen/processor_list/mega_site.json`). The mine's palette uses only the plain, radiated,
  polished and brick meteorid blocks, and the `mega_site` template is never placed with its processors. Otherwise the
  gulch becomes an unplanned eighth evolution-stone site.

---

## 5. Part b: the large mine

**A mine that opens into spaces.** Seven caverns at real scale, joined by wide drifts (8-12 wide, 6-10 high) that are
themselves loops and arches, not tubes. Modelled on Victory Road's cave network (`tools/vr_caves.py`: ragged caverns
merged into halls, cover at least 4, every face sealed, fluids bounded, a walk-out search from the entrance reaching
every floor cell with no traps; `docs/STATE.md:213`), which is built and matched on staging. Ground from
`tools/ground.py` only.

| Hall | Centre | Size (proposed) | Floor to roof | Role | Megas (section 6) |
| --- | --- | --- | --- | --- | --- |
| Tally Hall | (4350, 4905) | about 60 across | y62-80 | the company's works, lit, the floor's arrival point | none (a safe room) |
| Cutting Floor | (4420, 4860) | about 80 | y45-75 | benched walls, 2 faces | Steelix, Excadrill |
| Slag Gallery | (4480, 4780) | about 70 | y40-72 | spoil terraces, 2 faces | Camerupt, Houndoom |
| Glass Nave | (4500, 4910) | about 80, the tallest | y35-75 | dormant-crystal glints in the roof, 2 faces | Glimmora, Absol |
| Echo | (4560, 4830) | about 70 | y30-75 | a dark vault under the plateau, 2 faces | Golurk, Banette |
| Hot Workings | (4590, 4920) | about 60 | y40-75 | a lower bench, 2 faces | Scrafty, Sableye |
| The Heart | (4530, 4870) | about 50 | y15-45 | the deepest; 2 faces, the richest | Metagross (the Heart's Mega) |

That is 14 faces. For scale: Victory Road's network is 40 caverns and 65,661 floor cells (`docs/STATE.md:213`); this
mine is roughly a third of that, ASSUMED until modelled.

**The seal.** Its shell writes rock round every cavern, as the Displaced City's and the spur mine's do, so no natural
void opens into it. Under the gulch floor the roofs keep at least 9 of cover. The mine does not come west of x4300 and
so stays away from Victory Road's surface corridor and the unbuilt `hidden_rift_cavern` region (x3658-4125).

**Spawns in the caverns.** Sub-region pools reach underground (`docs/STATE.md:206`), so ambient spawns here would be
`rift_south_east_arm`'s roster unless Habitat Block tiles replace them (Victory Road's pattern, ranges of at most 28,
never overlapping, active after a restart; `docs/STATE.md:103`). The Megas are not spawns (section 6). No block in the
palette is named by a spawn condition: `mega_stone_crystal`, `dormant_crystal` and `keystone_ore` are not
(`SOUTHERN_RIFT.md:184-185`); no rails (`data/rift_mines.json` uses powered rails for that reason), no coal or iron
ore.

---

## 6. Part c: the hostile roaming Megas

### 6.1 How many and which

**Ten roaming Megas, two per worked hall, and one in the Heart: 11 alive at most.** Every species is a Mega whose line
can be caught here (section 7.3), chosen for rock, dark and ghost, and kept off the client's broken Mega models:
Mega Aggron, Gengar, Altaria, Manectric, Sceptile, Slowbro and Swampert wear the wrong texture on the client
(`docs/research/CLIENT_MODEL_FIXES.md:127-128`), and Mega Pidgeot and Skarmory share a model defect
(`docs/research/COBBLEVERSE_COMPATIBILITY.md:154`), so none of those is used.

| Hall | Mega | Stone (jar) | Its line here (`data/spawns.json`, lowest band) |
| --- | --- | --- | --- |
| Cutting Floor | Steelix | `steelixite` | Onix, Mining Town fossil levels 42-50 |
| Cutting Floor | Excadrill | `excadrite` | Drilbur, fossil levels 42-50 |
| Slag Gallery | Camerupt | `cameruptite` | Numel, the Great Crater 44-52 |
| Slag Gallery | Houndoom | `houndoominite` | Houndour, plateau east 47-54 |
| Glass Nave | Glimmora | `glimmoranite` | Glimmet, fossil levels 42-50; Glimmora in `rift_south_west_arm` 53-55 |
| Glass Nave | Absol | `absolite` (and ZAMegas' `absolitez`) | Absol, the Tri Peaks 24-35 |
| Echo | Golurk | `golurkite` | Golett in the gulch's own roster (`rift_south_east_arm` 54-56) |
| Echo | Banette | `banettite` | Shuppet, the Route 1 mansion 6-15 |
| Hot Workings | Scrafty | `scraftinite` | Scraggy, `rift_south_west_arm` 53-55 |
| Hot Workings | Sableye | `sablenite` | Sableye, the Route 1 mansion 6-15 |
| The Heart | Metagross | `metagrossite` | Metagross, Victory Road's Abandoned Cut core 60-64 |

Glimmora, Golurk, Scrafty and Excadrill are Legends Z-A Megas added by Mega Showdown
(`data/cobblemon/species_feature_assignments/za_mega_evolution.json` in its jar); whether their Mega models render on
the client is NOT VERIFIED (run `tools/client_model_fix.py scan` on each chosen form before building). Alternatives for
the Heart: Mega Garchomp (Victory Road's Slagworks prize) or Mega Charizard X, the form EXP-036 fought.

**Levels (ASSUMED, trainer-balance-designer's):** with the gulch opened at six badges, the cap is 50 (gym 7's ace,
cap offset 0, `docs/STATE.md:208`); the roaming Megas at 52-56 and the Heart at 58. A wild Pokemon above the cap is
allowed, and these cannot be caught, so the level-cap trap (`docs/STATE.md:120`) does not arise. The
`rift_south_east_arm` roster (54-56, Victory Road's band) needs re-banding for a six-badge zone; SOUTHERN_RIFT's
finding 3 already says so.

### 6.2 How they appear, move and come back

Every part below exists in this repository; the combination does not.

| Mechanism | How | Status |
| --- | --- | --- |
| **Spawned by a function, not a pool** | a keeper function runs `spawnpokemonat <anchor> <species> mega_evolution=<mega\|mega_x\|mega_y> uncatchable level=<L>` and tags what it spawned | `spawnpokemonat` from a function works (EXP-042; `docs/STATE.md:15`), and the blackout pack rebuilds its guardians that way (`tools/blackout_pack.py:649`). The Mega string works over RCON (EXP-036). **From a function, with the Mega string: needs a run** |
| **Count per hall** | the keeper spawns only while a hall holds fewer than its quota of tagged Megas, and only at an anchor with no player within 24 | a selector count; ASSUMED, plain vanilla |
| **Roaming** | Cobblemon's own wander AI (no `NoAI`), inside the hall | native behaviour |
| **The leash** | a tagged Mega farther than its hall's radius (30-40) from its anchor is walked back by `tp`, every 2 s while a player is near | the recovery guardians' leash (`tools/blackout_pack.py:639`, `data/blackout.json:105`, 24 blocks), which works on staging (`docs/STATE.md:31`) |
| **Aggression** | Fight or Flight: add `mega`, `mega_x`, `mega_y`, `mega_z` to `always_aggro_aspects` (today `["alpha"]`, `server/config/mods/fightorflight.json5:98-100`); unprovoked attack needs darkness and level 25 or more (`:5`, `:7`, `:17`), so the Megas' halls carry no light source | matched by aspect in FoF's source (`docs/research/notes/wild-mega-pokemon.md`, section 3). Only the Megas we spawn are wild Megas, and a player's own Mega is excluded (`!isPlayerOwned()`). **Not run: needs the config line and a test** |
| **Battle on contact** | `force_wild_battle_on_pokemon_hurt: true` (`fightorflight.json5:227`): when a Mega and a player's sent-out Pokemon trade a hit, a battle starts. A Mega hitting the player only hurts (`force_wild_battle_on_player_hurt: false`, `:231`) | config VERIFIED; behaviour ASSUMED |
| **Uncatchable** | the `uncatchable` property | carried on the entity (EXP-036); a ball refused in play **not yet seen** |
| **After a win** | the Mega faints and is gone; the keeper replaces it later | normal battle end; ASSUMED |

**Guard, or drawn by the material? They guard it, and they come back with it.** Each hall's Megas are leashed round
its faces. When a face restores (section 7.6), its hall's missing Megas are spawned at the face's far anchor. So a fresh
face comes with its guardian, and an emptied hall stays quiet until its faces return: the crystal "calls" the Mega in
the fiction (`SOUTHERN_RIFT.md:139-140`, the crystal forces Mega Evolution on what lives near it), and the rhythm ties
danger to reward. "Drawn to a player who is mining" would need a Pokemon to walk to a chosen block, and no command sets
a Cobblemon walk target (ASSUMED; none is known here); a `tp` to the face would read as a jump cut. Not recommended.

### 6.3 Risks to settle

- **A sword kills a Pokemon entity** (EXP-023). A killed Mega is simply replaced by the keeper later.
- **The blackout's guardians.** A wild battle loss is a blackout, and the victor becomes a leashed claim guardian
  (`docs/STATE.md:31`). A Mega that beats a player would then carry two leashes. Either the blackout skips tagged Megas
  (the items are then recovered from the hall's next Mega, or lost), or the Mega's own leash yields while it guards a
  claim. Decision 9.
- **Multiplayer.** Megas are shared entities. One in battle with one player is out of the fight for the others; a
  party clears a hall faster, and the faces are what bound the take.
- **Re-export.** Nothing built in game survives an export, entities included (`docs/world-building/REEXPORT.md:5-6`); the keeper spawns them again on the next
  approach, so no RCON step is needed.

---

## 7. The material chain

### 7.1 What Mega Showdown requires (read from the jar)

| Fact | Jar path | Status |
| --- | --- | --- |
| **81 Mega Stones in Mega Showdown 1.0.2, every one craftable.** Each recipe is a shaped craft of exactly one raw `mega_showdown:mega_stone`, one diamond and three more items: a species item and a pair of iron ingots (the classic stones: Gengarite = Spell Tag, raw stone, 2 iron, diamond) or of a themed item (the Z-A stones: Chandelurite = Ghost Gem, 2 lanterns, raw stone, diamond) | `data/mega_showdown/recipe/<stone>.json` (81 files, each `minecraft:crafting_shaped`) | VERIFIED. The earlier count of 83 (`WORLDGEN_FEATURES.md:59`) is 81 stones plus two directory entries in `mega_showdown/showdown/held_items/` |
| Each stone's species and form | `data/mega_showdown/mega_showdown/mega/<stone>.json` (81), e.g. `gengarite.json`: Gengar, `mega_evolution=mega` | VERIFIED |
| **ZAMegas adds 11 more**, crafted the same way from one raw stone (Absolite Z, Garchompite Z, Golisopite, Baxcalibrite, Darkranite, Heatranite, Lucarionite Z, Magearnite, Tatsugirinite, Zeraorite, Zygardite) | `zamega` jar `data/zamega/recipe/*.json`, `data/zamega/mega_showdown/mega/*.json` | VERIFIED |
| **Raw `mega_stone` comes only from the `mega_stone_crystal` block**: one per block, no Fortune bonus (the table has no bonus function), the block itself with Silk Touch, nothing if destroyed by an explosion | `data/mega_showdown/loot_table/blocks/mega_stone_crystal.json` | VERIFIED |
| **The Key Stone comes only from `keystone_ore`**, one per block, same shape | `data/mega_showdown/loot_table/blocks/keystone_ore.json` | VERIFIED |
| **Both blocks need a diamond pickaxe** (as do `dormant_crystal`, `keystone_block`, `wishing_star_crystal`) | `data/minecraft/tags/block/needs_diamond_tool.json` | VERIFIED. SOUTHERN_RIFT's "tool tier NOT VERIFIED" (`:150-151`) is answered |
| **No loot table in the jar holds a finished Mega Stone, a raw stone or a Key Stone.** The archaeological site gives sun stones, raw ores and Zygarde cells, its rare table sparkling stones; the observatory's chests and brushable sand give candies, gems, fossils, a Dawn and a Fire Stone | `data/mega_showdown/loot_table/archaeological_site/*.json`, `chests/observatory_*.json`, `archaeology/*.json`, `sets/any_showdown_held_item.json` | VERIFIED |
| In an ordinary world, **one `mega_site` holds one crystal** (13 x 14 x 13: 856 meteorid, 25 radiated, 1 crystal) and **one `megaroid` holds one Key Stone ore**; they generate underground (y-19..5 and y-32..-20) every ~32 and ~38 chunks at half frequency. None generates in a WorldPainter export | `data/mega_showdown/structure/mega_site.nbt`, `megaroid.nbt`; `worldgen/structure/*.json`, `worldgen/structure_set/*.json` | VERIFIED (read); the export's absence is `WORLDGEN_FEATURES.md:5-9` |
| **The Mega Bracelet** = Key Stone + 2 white apricorns + diamond + 5 iron (`IDI/AKA/III`); 16 other wearables (coloured bracelets, Mega Ring, cuffs, charms) also take a Key Stone; the tag `mega_showdown:mega_bracelet` lists all 17 | `recipe/mega_bracelet.json`, `tags/item/mega_bracelet.json` | VERIFIED |
| Mega Evolution outside battle and more than one Mega per battle are on (`outSideMega: true`, `multipleMegas: true`) | `server/config/mods/mega_showdown/config.json` | values VERIFIED; their exact meaning ASSUMED |
| The "find a raw mega stone" and "find a Key Stone" advancements fire on picking the item up (`minecraft:inventory_changed`), so they work at a placed site | `data/mega_showdown/advancement/mega_showdown/mega/find_raw_megastone.json`, `find_keystone.json` | VERIFIED. `WORLDGEN_FEATURES.md:73-75` said Mega Showdown's find advancements will not fire at pasted sites; that holds only for their parent's structure check |

**So: craftable, and findable only as raw material.** Every stone is crafted from the one raw material, and the raw
material is found only as crystal. The token idea is therefore not needed: the raw stone is the material, and it is
already an item Mega Showdown understands. A score-based token (`docs/research/CASINO.md`) stays the fallback for one
case only: if the owner wants the town to be the *only* place a stone is made (decision 5, option B).

**The practical wall is the species item, not the raw stone.** Most recipes need a held item: Spell Tag, Choice Specs,
Focus Sash, Life Orb, Eviolite, Muscle Band, Metal Coat and so on. Whether this world has any natural source for most of
them is EXP-031's open question (`docs/research/EXPERIMENT_BACKLOG.md`). The Cutters remove that wall (7.2).

### 7.2 One material or one per stone?

**One.** Mega Showdown has exactly one raw material for all 92 stones; what makes a stone Gengarite is the species item
in the recipe, not the ore. One ore per stone would need 60 custom items, which no mod here provides (principle 5 and
6). The mine yields raw mega stone and nothing else.

**How it is worked in the town: the Cutters.** Three bench masters in the Cutting Hall, each a villager placed the way
`tools/traders.py` places the Mart clerks, but with plain vanilla trade offers: **4 raw mega stones + 1 diamond -> one
keyed stone**, unlimited uses, one offer per stone. Three benches split the 60 stones of section 7.3 by generation so no
list is unreadably long. No species item is asked for: that is the Cutters' craft, and it is what makes the town the
place stones are made. Nothing is bought back.

- **Crafting stays allowed** (the owner, 2026-09-24, `docs/STATE.md:76`), but at the same rate: our pack overrides the
  92 recipes at their own paths (`data/mega_showdown/recipe/<stone>.json`, `data/zamega/recipe/<stone>.json`) so a
  crafted stone takes **4 raw stones**, the species item, iron and a diamond. Crafting is then the path for a player
  who holds the species item; the Cutters are the path for everyone else, and the natural source the no-crafting rule
  asks for.
- ASSUMED, and the Cutters' own proof: that a placed villager with `Offers` trades as written, never restocks down, and
  cannot be traded to zero. `STONE_ECONOMY.md` §8 already names this as its fallback and marks it unproven.

### 7.3 Which stones matter here

A stone matters when some line that ends in its Mega can be caught in `data/spawns.json` at a weight above zero (any
roster: routes, sub-regions, habitats, the sea), or is on the starter screen
(`modpack/config/cobblemon/starters.json`). Counted 2026-09-27; family links are mainline knowledge (ASSUMED).

**Wild lines: 46 species, 50 stones.** Abomasite (Snover), Absolite and Absolite Z (Absol), Aggronite (Aron),
Altarianite (Swablu), Ampharosite (Mareep), Audinite, Banettite (Shuppet), Barbaracite (Binacle), Beedrillite (Weedle),
Cameruptite (Numel), Chandelurite (Litwick), Charizardite X and Y (Charmander, the Great Crater 44-52),
Crabominite (Crabrawler), Dragoninite (Dratini), Drampanite, Excadrite (Drilbur), Feraligite (Totodile),
Froslassite and Glalitite (Snorunt), Galladite and Gardevoirite (Ralts), Garchompite and Garchompite Z (Garchomp,
Victory Road 60-64), Gengarite (Gastly), Glimmoranite (Glimmet), Golisopite (Wimpod, Long Isle south 44-50),
Golurkite (Golett), Gyaradosite (Magikarp), Hawluchanite, Heracronite, Houndoominite (Houndour), Lopunnite (Buneary),
Malamarite (Inkay), Medichamite (Meditite), Meowsticite (Espurr), Metagrossite (Metagross, Victory Road 60-64),
Pidgeotite (Pidgey), Pyroarite (Litleo), Raichunite X and Y (Pichu), Sablenite, Scizorite (Scyther), Scraftinite
(Scraggy), Sharpedonite (Carvanha), Skarmorite, Staraptite (Starly), Starminite (Staryu), Steelixite (Onix).

**Starter lines only: 10 species, 10 stones** (one per player who picks that starter): Venusaurite, Blastoisinite,
Meganiumite, Sceptilite, Blazikenite, Swampertite, Chesnaughtite, Delphoxite, Greninjite, Emboarite.

**Left out, 32 stones for Pokemon nobody can catch here:** Aerodactylite, Alakazite, Chimechite, Clefablite, Diancite,
Dragalgite, Eelektrossite, Falinksite, Floettite, Kangaskhanite, Latiasite, Latiosite, Lucarionite, Manectite,
Mawilite, Mewtwonite X and Y, Pinsirite, Salamencite, Scolipite, Scovillainite, Slowbronite, Tyranitarite,
Victreebelite; from ZAMegas Baxcalibrite, Darkranite, Heatranite, Lucarionite Z, Magearnite, Tatsugirinite, Zeraorite,
Zygardite. The Cutters offer none of them. Their recipes can stay; nobody holds the Pokemon.

**Sixty stones in all.** Nine of the Megas need a second item to reach the evolving form, so they lean on the stone
economy too: Starmie (Water Stone), Raichu (Thunder), Froslass and Gallade (Dawn), Chandelure (Dusk), Crabominable
(Ice), and the trade evolutions Gengar, Scizor and Steelix (`docs/STATE.md:210` lists Link Cable among the items
the rosters need).

### 7.4 The Key Stone

**VERIFIED: nothing places one.** No `keystone_ore` or Key Stone is written by any tool or data file; the only
mentions are the structure catalogue (`data/structures.json:6681`) and inventory tools. The Mega Bracelet also needs
white apricorns, which do not grow in this world (`WORLDGEN_FEATURES.md:57-78`: "Apricorn trees are the highest-priority
feature").

**Recommended: Sabrina gives a Mega Bracelet on her first win.** Sabrina "studies the Rift's effects on memory,
perception, and Pokémon" (`docs/story/ARC.md:153`), and her town already stands round Mega Showdown's observatory
(`TOWN_CHARACTER.md:46`). The mechanism exists: each leader's badge flag gives that leader's items once, per player
(`data/progression.json:1539-1540`, `first_win_rewards`); Sabrina's entry (`:1632`) gets
`mega_showdown:mega_bracelet` beside her badge. A finished bracelet, not a bare Key Stone, because the bracelet's
apricorns have no source and the no-crafting rule wants the item itself. Her dialogue points south: the gulch opens on
the same flag (3.3).

- **A second source, for a lost bracelet or another colour:** the megaroid crater in the Crystal Garden
  (`SOUTHERN_RIFT.md:103-106`), its single `keystone_ore` as a restoring face with a long period (a day, ASSUMED). One
  Key Stone per restore, shared, diamond pickaxe.
- **VERIFIED in game, 2026-09-27 (proof M-1, EXP-045, the owner on staging):** a player Mega Evolves in battle with the
  bracelet WORN in its Accessories slot (the "Mega Evolve!" option shows on the Pokemon's move screen; Charizard with
  Charizardite X). It reverts after the battle. Held in the hand, the option does not show; equipped mid-battle, it does
  not show either: the bracelet must be worn before the battle starts. So Sabrina's reward must reach the player as a
  wearable they are told to equip.

### 7.5 How much mining, and how long for one stone

The unit is the **crystal face**: a pocket in a hall wall, about 7 x 5 x 7 (245 blocks) of radiated meteorid, meteorid
and deepslate, holding **3 crystals (2-4)**: one showing on the surface, the rest in small hidden vugs.

| Quantity | Value | Basis |
| --- | --- | --- |
| Blocks mined per face to find its crystals | about 165 | two hidden crystals at random in 245 blocks are both found after two thirds of the box, on average (ASSUMED model) |
| Blocks mined per raw stone | about 55 | 165 / 3 |
| Raw stones per keyed stone | **4** | the Cutters' rate, and the overridden recipe |
| Blocks mined per keyed stone | about 220 | 4 x 55 |
| Seconds per block | about 1 with movement | deepslate breaks in 0.6 s with an unenchanted diamond pickaxe (vanilla hardness 3, ASSUMED to hold for meteorid, whose hardness is in code and was not read) |
| **Minutes per keyed stone** | about **12** at the rock: 4 digging, 5 fighting the face's Mega (one per 1.3 faces, about 4 min each), 3 walking between faces | ASSUMED; to be timed in the prototype |
| **The first stone** | about **25 minutes** from the town: the walk down, the first hall's two Megas, two faces, back to the Cutters | ASSUMED |
| Server-wide ceiling | 14 faces x 3 = 42 raw per restore cycle; at a 30-minute period, 84 raw an hour, **21 keyed stones an hour** for everyone | arithmetic |
| A party of four | about 5 stones an hour each while the faces are fresh | arithmetic |

**Demand, for comparison (ASSUMED):** a player running two or three Megas needs 2-3 stones; a collector of every
local Mega needs up to 60. So a normal player spends about an hour in the mine for their set, which is "a real
undertaking, not a chest", and a collector spends a long campaign there.

**The floor, per player.** On first reaching the Tally Hall, each player is handed **4 raw stones**, enough for one
keyed stone (ADR-002's advancement spine, the same "floor" as the stone economy's, `STONE_ECONOMY.md` §4, kind
`arrival` in `data/rewards.json`). It covers the diamond-pickaxe gap as the stone economy's floor covers the iron one.
Droppable if the two-player advancement proof fails.

### 7.6 The reset: not 40 finite crystals

The spur build places **40 `mega_stone_crystal`, finite** (`docs/STATE.md:128`; 14 in six faces, 4 in each of five
chambers, 6 in the Heart, `data/rift_mines.json`). With one raw stone per crystal that is 40 raw stones for the whole
server forever, or ten keyed stones at the rate above.

**The southern site uses restoring faces on approach**, the pattern already chosen for the evolution stones
(`STONE_ECONOMY.md` §5.3; ADR-003 as amended), specialised:

- A driver on the pack's tick tag, every 100 ticks: if no player is inside the mine's approach box, stop (one
  selector).
- For each face: when its period has passed (**30 minutes**, faces in a hall offset by 15), both corners are loaded
  (`execute if loaded`), no player and no Pokemon stands in the box, restore it: a `fill` filtered to a
  `#cobblers:face_resettable` tag (so a player's chest survives), then one of 8 variants' guarded `setblock`s for the
  crystals, one always on the surface. Then spawn that hall's missing Megas (6.2).
- At most about 12 commands and 245 block writes per restore; nothing runs while nobody is near.

| Option | Verdict |
| --- | --- |
| **Faces restored on approach** | **recommended**: shared, bounded, costs nothing idle, shares the stone economy's driver and proofs (P-2 to P-4) |
| Regrowing veins on a timer | rejected: `fill` fails on unloaded chunks, so a fixed timer mostly fails silently (`STONE_ECONOMY.md:226-230`) |
| Per-player instanced claims | rejected: player count not fixed, a late joiner has none, everyone still sees everyone's rock (`STONE_ECONOMY.md` §4, option B) |
| A quarry face that refills | the same as the recommended option, with one large face instead of 14; loses the halls' spread |
| A per-player allowance (a score, like the casino's coins) | fallback only: a vending machine, not mining (option E) |

---

## 8. The dig camp's seam: found early, not usable yet

**Keep, reshaped as the Celebi pattern** (`data/sapling_celebi.json`: seen from the clearing, inert, walled so it
cannot be harmed, its wake designed later):

- **What stays:** the seam cut with its meteorid band and dormant-crystal glints, and the prospect drift
  (`drift_c`, "the seam followed west into the hill ... open to anyone", `data/rift_mines.json:935`), plus Forge Row,
  the quarries, the worked face, drifts A and B, the ore piles and the carts.
- **The tease:** **one** `mega_stone_crystal` in the seam's face at the prospect drift's end, visible and out of reach:
  behind the company's grille, inside the Mining Fatigue ward the gate already uses (`data/rift_mines.json:1523-1525`).
  The ward is an effect given to players, so it can be **per player**: it lifts for a player holding `gym6_cleared`.
  From then on that crystal is theirs to take, as one small face restoring on approach (a day, ASSUMED). A raw stone in
  hand before the Key Stone does nothing, which is the point.
- **What goes:** the company gate and its zone check, the gated galleries, the six gated faces, the five chambers and
  the Heart, and 39 of the 40 crystals. The Megas never existed there (guardians were data only).

**Does the dig camp still have a reason to exist without the mine? Yes, and the reasons were there first:**
archaeology over Registeel's steel chamber (`data/towns.json`, `TOWN_CHARACTER.md:63`); Mega Showdown's two
archaeological sites, whose rare table is the only source of the sparkling stones that make the Z-Ring
(`data/mega_showdown/loot_table/archaeological_site/archaeological_site_rare.json`; `reward-item-inventory.md:390-396`);
Forge Row as the early crafting street the owner asked for (EXP-035 row 19); the Rift's first zone (Z1, 2 badges, G1);
the Slip barrier towards the relic area (`DEEP_CITY.md` §6); and now the seam, the first sight of the material the south
works. `STONE_ECONOMY.md` §7 already wants it to "dig up the past", not work stone.

---

## 9. What moving the mine costs

Every file or system that touches the west-spur mine, found by search (`rift_mines`, `R9M`, `mega_stone_crystal`, "mega
stone mine") on 2026-09-27:

| File or system | What it holds | Change |
| --- | --- | --- |
| `data/rift_mines.json` | the town, the seam, the gate, the gated galleries, faces, chambers, the Heart, `flag` = `gym5_cleared`, the ward | delete the gated features and the gate; keep town and seam; one crystal; the ward keyed on `gym6_cleared` |
| `tools/rift_mines.py` | builds the gate, the zone advancement (`zone_boxes`, `:833-860`, `:936-968`), crystals | the zone check and gate go; the ward's flag and a one-crystal face remain. Data-driven, so mostly data |
| `tools/rift_mines_audit.py` | fails closed when there is "no gated cell" (`:31`); checks gate, cover, zone | **breaks** once nothing is gated: its gated checks must go or become optional (test-author's) |
| `tests/test_rift_mines.py`, `tests/test_rift_mines_review.py` | 29 tests, many on the gate, zone and chambers | rewritten with the audit (test-author's) |
| `tools/reapply.py` | R9M step, world-local and excluded lists (`:88-90`, `:123`, `:237-267`, `:694-700`) | R9M stays for the camp. **Conflict:** `STONE_ECONOMY.md` §5.5 and ADR-003 reserve R9M for `cobblers_mines`; the spur build took the name first. The southern site needs its own step (R9S proposed) and the evolution-stone faces a new name |
| **The staging world** (`cobblers-dryrun11`) | the gated section is carved there, and its pack's gate and zone advancements are installed | the carve stays until the next export or a refill pass; reinstalling the pared pack removes the old advancements |
| **Zone checks** | the spur's own pocket zone check (`rift_mines/zone`); RIFT_ZONES Z3 at 60 species | the spur check goes; RIFT_ZONES Z3 becomes the gulch zone at 6 badges, the branch-mouth line re-traced (3.3) |
| **Routes** (`data/routes.json`) | no reference to the spur mine (VERIFIED by search) | none. The town is 164 off Victory Road's split: a town record and `tools/measure_towns.py` give its `nearest_leg` |
| **Signposts** (`data/signposts.json`) | the dig camp's name only (`:30`); nothing points to the mine | none removed; new signposts at the split and at the canyon foot for the mega town |
| `docs/mechanics/STONE_ECONOMY.md` | §7: "The Rift dig camp stays archaeology ... The camp opens after gym 8" (`:417-422`; RIFT_ZONES opens Z1 at 2 badges, a disagreement already); R9M | a paragraph: the mega town is its own system on the same machinery (section 4); the meteorid-ore trap; the step name |
| `docs/decisions/ADR-003-evolution-stone-supply.md` | amendment 3, R9M (`:103`) | the step name, if the owner keeps R9M for the camp |
| `docs/world-building/SOUTHERN_RIFT.md` | "Moved, 2026-09-27" (`:10-14`) | reversed: the gulch mine is the real one |
| `docs/world-building/DEEP_CITY.md` | §6 decision 9, "where the Key Stone lives" (`:258`) | answered by 7.4 |
| `docs/world-building/REEXPORT.md` | R9M's description (`:99`) | follows the pack |
| `docs/STATE.md` | `:128` (the spur mine built on staging) | reconciled when the change is built |
| `data/progression.json` | Sabrina's first-win items (`:1632`) | add the bracelet |
| `modpack/config/fightorflight.json5` (does not exist yet) | — | new overlay with `always_aggro_aspects` += the Mega aspects; `server_config_record.py` then records it |
| `experiments/EXP-035-first-playtest/README.md` | rows 19 and 22 | point at this document |

**The largest real cost is the audit and its tests**, which were built around the gated section; the rest is data and
documents. Nothing was placed in the live world.

---

## 10. Proofs before building (principle 20)

| # | Proof | Passes when |
| --- | --- | --- |
| M-1 | A player Mega Evolves in battle with a bracelet from a reward | the bracelet works held or worn; which one is recorded. EXP-000's open Mega check |
| M-2 | A Mega spawned from a function, tagged, leashed, replaced | a function spawns `steelix mega_evolution=mega uncatchable level=54`; it roams, is walked back past its radius, and is replaced after it faints |
| M-3 | The enrage | with the FoF line set, the Mega attacks unprovoked in a dark hall and not in the lit Tally Hall; a player's own Mega does not |
| M-4 | Uncatchable in play | a thrown ball is refused and the Mega keeps its form after the battle |
| M-5 | A crystal face | a diamond pickaxe gets one raw stone per crystal, an iron one nothing; the face restores on approach with the stone economy's P-2 to P-4 |
| M-6 | The Cutter | 4 raw + 1 diamond gives the stone, unlimited; nothing is bought |
| M-7 | Client models | each chosen Mega renders (`tools/client_model_fix.py scan`) |

Then a prototype slice: the canyon, the town's 61-square, the adit, the Tally Hall and the Cutting Floor with its two
faces and two Megas. The owner plays it; then the rest.

---

## 11. Decisions for the owner

**Decided by the owner, 2026-09-27: all twelve at the recommendations below**, with three notes:
- "PROVE THE MEGA BRACELET FIRST. Nobody has ever Mega Evolved in this pack, and everything downstream assumes it
  works." Proof M-1 comes before anything that depends on it.
- "the Cutters dropping the species-item requirement is right. 60 specific held items obtainable here was never
  realistic."
- "the gulch at badge 6 is fine."
The build starts with section 10's prototype slice, which the owner plays before the rest.

1. **Reverse the move: the gulch mine is the real one, the spur keeps only the seam and the camp.** Recommended.
2. **The dig camp's seam:** one crystal behind the company grille, warded per player until `gym6_cleared`, then a
   small daily face. Recommended. Alternative: a view only, never minable.
3. **The gulch's gate:** its own zone at 6 badges through the `gulch_mouth` canyon, with the branch-mouth line
   re-traced and the 60-species gate moved to Z4 or dropped. Recommended. Alternative: SOUTHERN_RIFT's Z2 (8 badges)
   with the town at the junction.
4. **The town's site:** the gulch floor at (4308, 4848) with quarters cut into the east wall (recommended), or the
   junction's flat 121-square at about (4100, 4655) on Victory Road.
5. **How stones are made:** (A) the Cutters at 4 raw + 1 diamond, and crafting kept but raised to 4 raw by overriding
   the 92 recipes (recommended); (B) the Cutters only, recipes disabled, which breaks "crafting stays allowed"; (C)
   Mega Showdown's 1 raw per stone left as it is, with fewer crystals per face.
6. **The rate:** 4 raw per stone, 3 crystals per face, 14 faces, a 30-minute restore. Recommended as the prototype's
   starting numbers, to be timed in play.
7. **The Key Stone:** Sabrina gives a Mega Bracelet on her first win (recommended), with the megaroid's restoring
   `keystone_ore` as a second source. Alternative: a bare Key Stone from Sabrina, crafted once apricorns exist.
8. **The Megas:** ten roaming, two per worked hall, plus the Heart's Metagross, at 52-56 and 58; the species in 6.1.
   Recommended. Alternatives for the Heart: Mega Garchomp or Mega Charizard X.
9. **A Mega that blacks a player out:** the blackout skips tagged Megas (recommended: the mine's danger is the Megas,
   not a lost item), or the Mega keeps the claim as any wild victor does.
10. **The Heart:** part of the mine at six badges (recommended), or postgame behind `champion_cleared`.
11. **Which stones the Cutters offer:** the 60 whose Pokemon can be had here (recommended), or all 92.
12. **The step name:** R9M stays the dig camp's, the southern site takes R9S and the evolution-stone faces take a new
    letter (recommended); or rename the camp's step and give R9M back to `cobblers_mines` as ADR-003 wrote it.

**Not verified anywhere in this document:** that the bracelet works for a player; a Mega spawned from a function; the
enrage; a ball refused; the hardness of meteorid blocks; every time in 7.5; villager trades as the Cutters; the Z-A
Megas' client models; the family links in 7.3. The halls' volume, cover and seal are now modelled and audited offline
(section 12), not measured in a world.

---

## 12. What was built: the prototype slice (2026-09-27, offline)

Generated on the branch `world/gulch-prototype` from `data/gulch_mine.json` by `tools/gulch_mine.py`, audited by
`tools/gulch_mine_audit.py` (clean), re-applied by `tools/reapply.py` step **R9S** (decision 12). Ground from
`tools/ground.py` only. **Not installed, not in any world, not seen in game.** Pack `cobblers_gulch_mine`, world-local
(it drives itself): 50 block functions, 78,850 commands, 239,444 cells written.

| Part | Where | Built |
| --- | --- | --- |
| **The gate** | the sculpt's `gulch_mouth` gap, ring index 2680 +-44 (derived/rift_sculpt/plan.json), lip at (4360, 4706) | a rockfall along the lip across all 89 gap points (3,793 blocks, 4-6 wide, 7 over each point's ground), the plug in its middle (flat top y122) with the company grille at x4362 z4705-4707 y116-118; knock alcove x4363-4365, exit box x4353-4354, arrival (4349.5, 111, 4706.5) facing down the road, turn-back (4370.5, 119, 4706.5); the ward (Mining Fatigue IV) over x4350-4372 y103-129 z4692-4720, margin 7 |
| **The road** | (4392, 4706) y126 to (4285, 4790) y88 | a graded 5-wide road through the gate down to the floor: the sculpt's ramp is stepped by its own rounding into ridges up to 10 blocks apart (x4300-4340), unwalkable without it |
| **The zone** | the gulch inside the lip ring from (4351, 4600) round the south-east branch to (4195, 4929), closed by the re-traced branch-mouth line | 366 boxes, 79,749 columns, y-64 to 575, opened by `cobblers:flag/gym6_cleared` (decision 3). The rim edge runs 3 outside the lip, the gap edge 2 inside it. The split is about 100 blocks outside the line, Victory Road's corridor about 190 |
| **The square** | 61 x 61 at (4308, 4848), y88 | paved (deepslate brick border, tuff bands, polished deepslate field), a meteorid plinth with a dormant crystal behind glass, ten lamp posts |
| **The quarters** | a yard x4276-4340 z4880-4911 cut to y88 into the slope south of the square | the Cutters' workshop (25 x 16, counter of polished meteorid, benches), a bunkhouse, the assay counter, the adit's portal in the face at z4912 |
| **The Cutters** | behind the counter at (4293 / 4300 / 4307, 89, 4903) | three mason villagers, NoAI, invulnerable, 20 offers each: 4 `mega_showdown:mega_stone` + 1 diamond -> the stone, `maxUses` 2147483647, no experience, no price drift; the 60 stones of 7.3, split by generation; none of the 32 |
| **The Tally Hall** | centre (4365, 4925), about 57 across, floor y64-67, roof y80 | 26,690 cells of air, lit (lanterns hung every 7), four basalt pillars; four raw stones once per player on arrival (an advancement) |
| **The Cutting Floor** | centre (4430, 4850), about 77 across, floor y45 (bowl to y54), roof y75 | 79,487 cells of air, unlit, 6% meteorid in its walls |
| **The faces** | A: x4477-4483 z4847-4853 y53-57 (east alcove); B: x4427-4433 z4797-4803 y53-57 (north alcove) | 7 x 5 x 7 of meteorid, 3 crystals each (one on the front, two hidden), 8 variants; restored on approach every 36,000 ticks, B offset 18,000 |
| **The Megas** | Steelix at (4446, 47, 4852), Excadrill at (4428, 47, 4834) | spawned by the keeper `uncatchable` at levels 54 and 53, tagged `cobblers.gm.<id>`, PersistenceRequired, leashed at 24 every 2 s while a player is near, owed again when a face of the hall restores while one is gone |

Tunnels: the Cutters' adit (y89 to y67, 5 x 5, lit every 8), the drift from the Tally Hall to the Cutting Floor (y66 to
y52, unlit), two short alcoves to the faces. 111,331 cells carved in all; a shell of 65,218 rock cells round
everything carved and round the face boxes; least rock over the shell: Tally Hall 13, Cutting Floor 16 (minimum 4).

**Where the build departs from sections 3-7, and why:**
- The Tally Hall moved from (4350, 4905) to (4365, 4925): at the proposed point the adit from the town would have had to
  start over the hall's own roof. The Cutting Floor moved from (4420, 4860) to (4430, 4850), to keep 30 blocks of rock
  between the two halls.
- The quarters are cut into the **south** slope (y89 to y97-100 within 30 blocks), not the east wall: on the heightmap
  the east wall climbs to only y92-100 within 60 blocks of the square (section 4 says y120-128).
- The gulch_mouth "canyon" is a broad ramp across an 89-point gap in the rim, not a 7-wide canyon: the gate is a
  rockfall across the whole gap with the grille in its middle, and a road graded through it.
- The zone's closing line is new: (4351, 4600) to (4195, 4929), not the old branch-mouth line (4373, 4691)-(4196, 4927).
- Only the Cutters, the square and three houses of section 4's town are built; no Centre, Mart, Assayer, Dissenters'
  camp or signposts yet.

**Also changed for the slice:** the spur is cut back (decisions 1-2; `data/rift_mines.json`): the camp keeps its seam
and one crystal behind the company grille at the end of drift C, warded per player until `gym6_cleared`, restored on
approach once a day; the spur's gated galleries, chambers and Heart are retired, with a staging-only refill
(`cobblers_rift_mines_refill`, 14,627 cells). The 92 stone recipes are raised to 4 raw stones by `tools/mega_recipes.py`
from the server's own jar into `build/` (never committed). The blackout makes no item claim for a victor tagged
`cobblers.gm` (decision 9, `data/blackout.json` `claims.exempt_tag`). The Fight or Flight line is proposed in
`data/gulch_mine.json` `megas.aggression_proposal`; the owner approved it and it was applied on staging (section 13).

**What `tools/gulch_mine_audit.py` checks** (independent of the generator's model: its own rasterising of the data, the
heightmap, the sculpt's gap, Victory Road's corridor and caves, `data/spawn_blocks.json`): cover over every hall
column; nothing carved within a block of the surface outside the adit's portal; no build column within Victory Road's
corridor (half its width + 24) or its caves' extent, nor near a settlement; the rockfall under every ring point of the
sculpt's gap and a crag beyond each end; every write inside the grid and the plan's columns; no stray air, the carved
space sealed by written rock; no spawn-condition block, fluid or meteorid ore; the zone boxes full height, every write
inside them but the rockfall, the road and the gate's lamps, the knock and turn-back outside, the arrival and exit
inside, and every basin column walked from the square (77,994) inside; the knock and zone functions gated on the flag,
the ward holding the plug with its margin; a walk on the replayed world from the arrival to the square, both halls,
both faces, both anchors and the three counters, and no walk from the turn-back point to the arrival; each face written
whole with its crystals, each variant one filtered fill and guarded setblocks, each check guarded; each Mega's spawn
line uncatchable with its aspect at a floor cell, its leash; every Cutter offer; function limits.

**Proofs still open (section 10):** M-1 the bracelet (the owner's first), M-2 a Mega spawned, tagged, leashed and
replaced from a function, M-3 the enrage (needs the config line), M-4 a ball refused, M-5 the faces (diamond pickaxe,
the restore with P-2 to P-4, the filter's `replace #tag`), M-6 the Cutters' trades (the offer format is read from the
vanilla 1.21.1 jar; the trade itself is not run), M-7 the Megas' client models (Excadrill is a Z-A Mega). None has run.

**Install on staging** (the main session; the server stopped, the coordination lock held): `reapply.py prepare`
(it builds and audits everything above, and needs `--server-dir` for the recipes' jar) and `install` (puts
`cobblers_gulch_mine`, `cobblers_mega_recipes` and the pared `cobblers_rift_mines` in the world's own datapacks);
boot; `reapply.py run --only R9M` then `--only R9S`; then, staging only, copy `build/datapacks/cobblers_rift_mines_refill`
into the world's datapacks, `/reload`, run its functions in the order of its `index.txt`, and remove it again.

## 13. The owner's redesign (2026-09-27, after the gate test)

The owner played the gate on staging: it opens with the sixth badge. Then the design changed. These decisions supersede
sections 4 to 7 where they disagree (and section 12 where it describes the faces' restore, the owed Megas, the floor
and the 4-stone price). What is built from it is in 13.1.

**The gate goes higher.** The zone check already turns back a player without the badge at any height (the zone boxes
are full height, section 12), so a flier cannot get in. But the rockfall plug stops at y122, below the gap's walls, and
reads as passable. It is raised to fill the gulch mouth to the crag tops as a rockslide wall.

**The town fills the whole cove**, in sections of workers, miners and extractors: a workers' quarter; a miners' camp
(headframes, winches, spoil heaps); an extraction works (ore piles, sluices, crushers); the Cutters' workshop at its
heart. The layout follows the cove's shape and grows by accretion, not a grid (the same rule as the dig camp below).

**Megas are the source of the currency, not mining.** The owner: "a player will fight the mega mons I have roaming for
resources, that they will then use to buy mega stones".
- The currency is the raw `mega_showdown:mega_stone`. The owner declined free stones ("I don't want mega stones being
  free, I want this to be a sort of late game farm"). A finished stone is never dropped, and the arrival floor of 4 raw
  stones (section 7.5) is dropped.
- **Where:** the southern Rift's two western zones, around **(4090, 116, 5289)** and **(3738, 87, 5164)** (the owner's
  coordinates). They look as if a world broke there and something powerful moved in: caves, Mega dens, broken houses
  half sunk, debris.
- **Levels and drops:**

  | Tier | Level | Drop chance per defeat |
  | --- | --- | --- |
  | Outer | about 60 (the owner: "if cap after gym 5 is 50 … lvl 60 or so, so it takes a team") | 15% |
  | Deeper | 65-70, harder evolved lines | higher, 25-35% (ASSUMED; the owner said "more frequently") |

  The drop falls at the victor's feet, owner-only. The mechanism is the `battle_fainted` and kill paths the recovery
  claims already use (`tools/blackout_pack.py`), for Megas carrying the farm's tag. Megas stay uncatchable, respawn in
  their dens on a timer, and make no blackout item claim (decision 9). The respawn timer is the farm's rate limit, so no
  repeatable action may reset it (the lesson recorded with the swim-fatigue fix).
- **The price.** The owner: "a player should take an hour to get a mega mon ish". A team fight with a level-60 Mega plus
  finding the next is about 5 minutes (ASSUMED; to be timed), so about 12 wins an hour, and 1.8 raw stones at 15%. The
  keyed-stone recipe therefore takes **2 raw stones** (it is 4 today, `tools/mega_recipes.py`). The deeper tier pays
  faster, at a higher risk. Both numbers are data, and are re-set once a real fight is timed.
- **The crystal faces are unmineable scenery.** They keep their look; the ward holds them permanently and the restore
  cycle is retired.

**Hostility.** The owner wants Megas to attack on sight unless the player is 20 or more levels above them.
- **Applied on staging, 2026-09-27:** Fight or Flight's `always_aggro_aspects` became
  `["alpha", "mega", "mega_x", "mega_y", "mega_z"]` in the server's `config/fightorflight.json5` (recorded in
  `server/config/mods/`).
  - The config folder is the server's, shared by the staging and live worlds. The live world has no wild Megas, and the
    mod exempts a player's own, so the change has no effect there.
- **Not a config setting: the 20-level exemption.** Fight or Flight 0.11.0's config (read in full on the server) has no
  key relative to the player's level; aggression is a property of the wild Pokemon alone. Nobody can be 20 levels
  above a level-60 Mega before the cap passes 80, so the rule matters only after the League. It is recorded as proof
  M-3b; the route would be the datapack reading the party's top level (the water ladder already reads the party).
- **Open (M-3):** `light_dependent_unprovoked_attack` is `true` server-wide, so unprovoked attacks may happen only in
  the dark. Whether an always-aggressive aspect overrides the light rule is not known. The zones are outdoors, and the
  in-game proof decides it.

**The West Spur Dig (the north Rift dig camp) is reshaped too.** The owner, on the map of the camp: it "should also
conform to the shape of the pocket it is in, the quarry should be large and a little deep taking half of the area
probably, with the strip mines and stuff on top. have the camp seem chaotic in its planning not just a pasted town with
perfect lines in a grid pattern." Today it is a straight forge row, three rectangular yards and a small stepped pit
(`tools/rift_mines.py`, `data/rift_mines.json`).

### 13.1 What was built from section 13 (2026-09-28, offline)

Generated by `tools/gulch_mine.py` from `data/gulch_mine.json`, audited by `tools/gulch_mine_audit.py` (clean). **Not
installed, not in any world, not seen in game.**

| Part | Built |
| --- | --- |
| **The Megas' spawn (a bug fix)** | Every Mega now spawns through one macro line, `megas/spawn_at` = `$spawnpokemonat $(x) $(y) $(z) $(species) $(aspect) uncatchable level=$(level)`. `spawn_<den>` calls it with inline arguments and then claims the new Pokemon in the same function. The plain line it replaces spawned nothing after a plain restart until a `/reload` (EXP-046). The audit fails on any plain `spawnpokemonat` line anywhere in the pack |
| **The gate** | A rockslide wall across all 89 points of the gap, rising to the crag tops. Its crest runs straight from y194 (j -44) to y186 (j +44): at each end, the rim's highest ground within 16 outward of the first ring point beyond the gap, measured on the heightmap. It has a steep inner face and a talus onto the plateau that drops 3 per block beyond a 2-block core, out to 8. About 71,000 blocks. The plug (\|j\| <= 6) is flat-topped at y190. The grille stands in its face at the end of a 7-wide slot through the outer talus, with the road and the knock alcove in the slot. The ward is now x4350-4377, y106-197, z4689-4720 (margin 7 over the plug). The audit measures the crag tops itself: the wall must stand within its jag of them and reach the crest line at every ring point |
| **The respawn clock** | Each den's Mega (so far the Cutting Floor's Steelix and Excadrill) respawns `respawn_ticks` after it was first seen gone. It must be absent on two passes in a row, and it comes back only when nobody is within 24 of its anchor. The mine's two wait 15 minutes. Load sets a clock only when it has never been set. Only the keeper starts a clock, and only a spawn, or a Mega seen in the den, clears it. The audit rejects any other line that writes the clock. Tests cover a restart and leaving and re-entering the approach box, and contract C14 now sweeps this clock in place of the faces' restore |
| **The drop roll: machinery only** | Built into the keeper, and inert until a farm den exists in the data (the farms are held, see below). When a farm Mega is claimed, the keeper stores its Pokemon UUID as text on its den (the method of `tools/blackout_pack.py` recovery/pid). A `battle_fainted` callback (`data/cobblemon/callbacks/battle_fainted/cobblers_gulch_drops.molang`) looks the fainted Pokemon up by that UUID and rolls the den's `gm.pct` for the first player in the battle. For a kill outside a battle, an attacker watch (recovery/watch's pattern) notes the last player to hurt the Mega. If that hit came after the Mega was last seen alive, the keeper's first sight of it gone rolls for that player. There is one roll per Mega: a roll spends its UUID. A win drops one raw `mega_showdown:mega_stone` at the victor's feet with `Owner` set to the victor, so only they can pick it up (vanilla 1.21.1 ItemEntity). This build creates no blackout item claim for a Mega (decision 9). Data: `drops`, `farm_tiers` (outer: level 60, 15%, 10 min; deeper: level 67, 30%, 15 min), `megas.farm_tag` |
| **The price** | A keyed stone costs 2 raw stones plus a diamond at the Cutters (`cutters.offer.raw_count`). `tools/mega_recipes.py` reads the same number, so crafting takes 2 as well. The arrival floor (4 free raw stones at the Tally Hall) is removed |
| **The cove town** | 69 buildings across the gulch floor, laid out by accretion (`python tools/gulch_mine.py layout`, deterministic from `cove.seed`; the result is pasted into `data/gulch_mine.json` `cove.buildings`, which `build` reads). Each section starts at its seeds and adds one building at a time beside one already placed, across a 2-4 alley, at a random offset and turn. A building is kept only on cove floor: inside the zone by 3, ground at or under y96, clear of the square, the yard, the road, the portal and the gate. A house's ground may span at most 3, an open work's at most 5. **Heart:** 4 lapidaries by the square. **Workers' quarter** (west of the square and the road's foot): a canteen, 2 washhouses and 15 dwellings. **Miners' camp** (the sunken east floor): 4 headframes (basalt legs 15-19 high, copper girts, a sheave of iron bars, chains to a capped collar), 4 winch houses, 6 spoil heaps, 3 tool sheds and 7 bunkhouses. **Extraction works** (the south-east floor by the adit's end): 3 crushers (stamp pistons, grindstones), 3 sorting sheds, 4 dry sluices on trestles (no fluid; a water cauldron at each head) and 10 ore piles (raw iron, raw copper, coal blocks) with 3 spoil heaps. There are also 34 lamp posts. Every house has steps down from its door. No timber: basalt, deepslate, tuff, stone and copper. **Found on the heightmap:** the east of the cove is a sunken floor (y88-89) inside a rim that stands at y97-102 and drops about 14 blocks at once, so no walker could enter it or leave it. A level cutting, 5 wide at y88 (`cove.paths` `crater_cutting`), runs from the square's east edge through the rim onto that floor. **The Cutters' workshop is unchanged.** The narrow floor north of the gate is left empty: nothing reaches it on foot from the town. Both the model's walk and the audit's walk (on the replayed pack) reach every house doorway from the gate's arrival. The audit also checks each building against the zone, the ways, the square, the ground limits and the alley |
| **The faces** | Scenery: each face is built once (the old variant 0) and never rewritten. The restore, its variants, its period and its block tag are gone. Every tick, any survival or adventure player within 7 of a face's box gets Mining Fatigue IV. Contract C6 now counts the faces as a built ward and checks their reach |

**Held:** the Mega farms (item 2). Both sites lie in the south-west arm, inside Victory Road's zone Z2, which RIFT_ZONES
gates at 8 badges. Section 13 puts the farms after gym 6. The owner decides between carving a gym-6 zone out of Z2 and
waiting for 8 badges. Once the farms are placed, the keeper, the respawn clock and the drop roll above take their dens
as they are.

**Proofs this adds (none run):** a plain restart followed by a Mega spawning through the macro (M-2 as amended); a
roll after a battle win, and after a sword kill; an owner-only item refused to another player; the faces' ward holding
in game (replaces M-5's restore).
