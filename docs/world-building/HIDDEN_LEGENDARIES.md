# Hidden legendaries: catalogue templates placed where you stumble on them

The owner, 2026-10-03: *"Place more of the Cobbleverse catalogue in their own shrines, and OBSCURE them. I do not
want a row of landmarks - I want places you stumble on ... Use /place template, not /clone. Re-open the eight that
were left where they generate ... Each one: what gates it, what a player gets, and how anyone would ever find it.
Spread them so finding one is an event."*

Authored data: `data/adopted_legendary_sites.json` (the measurement and the reasoning) and `data/placements.json`
(the one position, a `kind: donor` record that reapply R9 pastes with `place template` through
`tools/place_donor.py`). Rules: `tools/hidden_sites.py check`. Nothing here was placed, booted or clicked.

## The rule a hidden site is held to

`python tools/hidden_sites.py check` (every site with `"hidden": true`), all off `tools/ground.py` (rounded) and the
authored data, never a world:

| Rule | Number | From |
|---|---|---|
| clearance | no authored x/z within **96** of the footprint edge | every dict with numeric x/z and every `[x, z]` / `[x, y, z]` list in `data/*.json` and `data/*/*.json` (29,071 points; routes, rivers and region outlines included on purpose) |
| keep-out | outside x3450..4250, z4700..5450; **300** from (3556, 6112), (4530, 5850), (3708, 5716) | the brief: the Mega farm and the new southern places |
| portals | **120** from every portal, footprint edge | `data/portals.json` `rules.min_from_legendary_mouth` |
| spread | **800** centre to centre from every other legendary site | every adopted site and every `data/legendaries.json` encounter with a coordinate |
| dry | every column above sea level y62 | `data/world.json` |

`tools/hidden_sites.py` also measures `sightings`: how many route vertices within 1,200 blocks see the template's
top over bare terrain (trees not modelled, so it over-counts). A hidden site should be seen from none.

## The site

| | The Crown Spire |
|---|---|
| Template | `cobbleverse:crown_spire` (41x38x49), `adopted_crown_spire` / `legendary_crown_spire` |
| Command | `place template cobbleverse:crown_spire 5348 130 484 none none`, then `data remove block 5363 131 493 storageWrapper.contents.inventory.Items[{id:"lumymon:calyrex_crown"}]` |
| Where | **Northgate Isle**, its eastern highland (cell A6, `northgate_east`, sparse taiga), 99 blocks from the elder spruce `elder_northgate_east_1` (5472, 432) |
| Ground | 1,957 of 2,009 columns already at y130: 12 blocks cut, 40 filled. Top occupied layer y167, 408 under y575 |
| Obscurity | An island with no reason to visit: no town, route, ferry stop or trainer. The nearest route vertex is **1,489** blocks away, so 0 route vertices see it. Its only other content is three elder spruces |
| Gate | **Surf** to cross (Misty, after `gym2_cleared`; the island is 150-500 blocks off the north coast). Then **the level cap**: Glastrier spawns at 50-59 or 70; every 50-59 roll is catchable from `gym8_cleared` (cap 60), the 70 roll only after `champion_cleared` |
| What a player gets | **Glastrier**, from the one `iceroot_carrot_crop` (ripe), thrown onto the trigger ring. Probably **once for the server** (see owner call 2). Barrels: TM Freezy Frost, 17 ice Tera Shards, 12 relic coins, 2 Azure Balls and an Ice Heal, a diamond axe. A second Calyrex statue, waiting for the archivist's crown |
| How it is found | A **rumour after gym 8** from the Shrew Station **archivist** (`data/research_station.json` npc `archivist`, who already holds the crown errand), proposed line: *"There's a spire of old ice on the spruce isle north of the downs. Go and look behind the big tree."* Then the elder spruce itself: whoever crosses to see the giant tree finds the spire behind it. **Not authored**: the dialogue belongs to the station's session |
| Spread | Azelf's grotto 1,671; the Crown Cemetery 1,936; Regice 2,129; the Dawn tower 2,142 |
| Lost by pasting | the Ice Calyrex radar and `/locate`; one spawn entry, `cobblemon:0037_vulpix` via the structure |

**Read from the template** (`COBBLEVERSE-DP-v31.zip` `crown_spire.nbt`, client profile, zipfile + `tools/nbt.py`,
nothing copied): it is a **Glastrier** site (trigger x3 at template [24, 2, 36..38], anchor [16, 6, 38], one
`iceroot_carrot_crop` age 7 at [13, 4, 30] among eight vanilla carrots) that **also** carries a Calyrex statue
([23, 21, 24]) and, in the barrel at [15, 1, 9], **the only `lumymon:calyrex_crown` in the game**. That corrects two
records: `data/structures.json` lists only the trigger, and refused group 4 refused the spire as a second Calyrex
site. The crown is removed after the paste (`data_remove`, new in `tools/place_donor.py`) so the archivist's
`champion_cleared` gate stays the only road to a level-70 Calyrex.

## Why there is only one more: the loaded catalogue is used up

`data/structures.json` has 20 LEGENDARY structures. After this, every one is adopted or has a reason that is not
taste:

| Template | Legendary | Status |
|---|---|---|
| mew, crown_cemetery, zapdos, articuno, dawn_tower, dusk_tower, moltres | Mew, Spectrier/Calyrex, Zapdos, Articuno, Necrozma x2, Moltres | adopted before today |
| **crown_spire** | **Glastrier** | **adopted today, hidden** |
| lake_acuity/valor/verity | Uxie, Azelf, Mesprit | ours already, in `data/legendaries.json` |
| stark_mountain | Heatran | 120x90x137 and two Sinnoh RCT trainers |
| giratina_island, distortion_portal, turnback_cave | Giratina | jigsaws; see below |
| four Ruinous shrines, eternatus_cocoon | Chi-Yu, Wo-Chien, Ting-Lu, Chien-Pao, Eternatus | the eight, below |

Beyond the catalogue, **three templates the loaded jars ship and `place template` could reach today**, each read
2026-10-03 and each blocked by more than a site:

| Template | Size | What it is | Blocked by |
|---|---|---|---|
| `lumymon:newmoon_island` | 101x58x100 | Darkrai's shrine and anchor; loot: a Lunar Wing, 16 enchanted books, TM Night Slash, 6 psychic Tera Shards, Moon/Dusk Balls, three gilded chests | Darkrai's item `nightmare_weaver` is made only by a recipe in the **disabled** Sinnoh pack, so the shrine is dead. It is a **floating island** for LumyMon's own Nightmare dimension (`nightmare_void`): its bottom layer is 28% air, so pasted onto ground it digs 2,804 columns of holes, onto sea it opens dry pits. Not in `data/structures.json`, so the record's tests reject it |
| `lumymon:temple_of_sinnoh` | 35x38x103 | Arceus (18 `arceus_pedestal`, one plate each, Arceus 90-100), Origin Dialga and Palkia statues, 52 ghost barriers | ships two RCT spawners for **Hisuian** trainers `hisui_damon`, `hisui_perula` (they exist in the loaded RCT pack, so they would spawn), the plates' source was not checked, and it is not in `data/structures.json` |
| `legendarymonuments:giratina_island/main/222` | 42x43x38 | the island's centre piece: `giratina_altar`, an anchor, 15,349 distortion cobblestone | the Red Chain drops only from `team_galactic_cyrus` (not in our campaign) or a **disabled** Sinnoh recipe; Giratina is 85-99. The template id is not the structure id the record keys on |

And the **disabled Johto, Hoenn and Sinnoh packs** hold 52 more templates (Lugia, Ho-Oh, Celebi, the Regis,
Latias/Latios, Kyogre, Groudon, Rayquaza, Jirachi, Deoxys, Dialga, Palkia, Cresselia, Darkrai, Shaymin...;
`docs/world-building/STRUCTURE_INVENTORY.md`). `place template` cannot reach a template in a disabled pack.

## The eight that were left where they generate, re-opened one by one

| Template | Verdict | Why |
|---|---|---|
| `cobbleverse:dawn_tower` | **MOVED** (2026-10-02), north Pine Isle (7480, 99, 316) | already hidden by these rules: 0 route sightings, nearest route 3,175 |
| `cobbleverse:dusk_tower` | **MOVED** (2026-10-02), Sunset Isle's western heights (1156, 146, 7216) | 0 route sightings, nearest route 1,966 |
| `cobbleverse:legendary/moltres` | **MOVED** (2026-10-02), the Craters (6252, 168, 5344) | a landmark, not hidden: seen from 1,961 of 1,967 route vertices within 1,200, and 431 from Groudon's chamber. It is the owner's birds' trio with Blaine, so it stays; owner call 4 |
| `legendarymonuments:eternatus_cocoon` | **STAYS OUT** | the owner, 2026-10-02: until a Galar Particle supply is authored (500 needed, the template carries 45, the ore never generates in our export) |
| `legendarymonuments:firescourge_shrine` (Chi-Yu) | **STAYS in the Nether** | its stakes are a Nether worldgen feature; a pasted shrine would have none near it, and the Nether copies would still generate, so a paste adds a second shrine rather than moving one |
| `legendarymonuments:grasswither_shrine` (Wo-Chien) | **STAYS** | same |
| `legendarymonuments:groundblight_shrine` (Ting-Lu) | **STAYS** | same |
| `legendarymonuments:icerend_shrine` (Chien-Pao) | **STAYS** | same. INFERRED, not tested: progress is per player in a server-side file, so the shrine's position may not matter, and an overworld shrine fed by Nether stakes could work. That is an experiment, not a placement |

## The owner's calls (not settled here)

1. **The crown.** By default the spire's crown is removed, keeping `data/research_station.json`'s
   `champion_cleared` crown errand the only source. The alternative: delete the `data_remove` entry and let the
   spire's barrel BE the crown, which makes the archivist's sixteen-carrot trade redundant and hands a level-70
   Calyrex to any finder at any cap.
2. **One Glastrier, and an early finder can waste it.** Surf reaches the island from gym 2; a carrot thrown before
   the cap reaches the roll wastes the server's one Glastrier (if the trigger consumes it, which is not known).
   Options: accept it (the rumour comes after gym 8), or remove the crop at paste and hand iceroot carrots out at
   `gym8_cleared` like the feathers. If the trigger does NOT consume the carrot, Glastrier is a farm, and needs a
   twin of `cobblers_spectrier_cap`.
3. **More hidden sites need one of:** the Sinnoh pack enabled (Darkrai's and Giratina's items, and its templates),
   a test change that lets a record name a template that is not a registered structure (Newmoon Island, the
   Temple, the Giratina piece), or authored items for dead altars. Proposed homes when allowed: Newmoon Island
   floating over the **Fungal Isle** (x0..983, z5208..6247: nothing authored on it but spawns, 699 off the
   mainland); the Giratina piece in a dead end of the Rift; the Temple only with its two spawners emptied.
4. **Moltres, the Crown Cemetery and Zapdos are seen from the roads** (route sightings 1,961, 2,102 and 387). The
   owner placed all three on purpose; under today's brief they are landmarks. Re-siting them is a choice.
5. **Pocket rooms and caves.** A dive portal's room is 7 to 13 blocks wide in `cobblers:pocket`, and the record
   measures ground on the overworld heightmap; no catalogue template fits a room, and a heightmap cannot describe an
   overhang or a cave back. Those homes need a different record (a room kind, or a carved cavern spec).

## Independent audit checklist (for another agent)

Do not reuse `tools/hidden_sites.py` or `tools/adopted_sites.py` for the expectation; derive it.

1. Read `crown_spire.nbt` yourself (client profile, read only) and confirm: size 41x38x49; the barrel at
   [15, 1, 9] holds `lumymon:calyrex_crown`; trigger, anchor, statue and iceroot crop positions as recorded.
2. `round(ground(x, z))` over x5348..5388, z484..532 by your own loop: min 129, max 131, 1,957 columns at 130,
   cut 12 and fill 40 at y130, and y130 the unique cheapest seat.
3. Recompute the nearest authored coordinate with your own JSON walk over every `data/*.json` and `data/*/*.json`
   (skipping only `adopted_crown_spire` and `legendary_crown_spire`): it should be (5472, 432), 98.8 from the
   footprint edge. Then check whether any key-shape the walk does not catch carries a coordinate inside 96.
4. Edge distance to every portal in `data/portals.json` (nearest 1,593) and centre distance to every adopted site
   and legendary chamber (nearest 1,671).
5. Mutate the GENERATOR, not the record: change `data_removals()` to drop the rotation, place the record at
   rotation `180`, and confirm a test of yours catches the wrong world position.
6. Confirm `place_donor.commands()` for `legendary_crown_spire` emits the `data remove` after `place template`
   and before `forceload remove`, and that a mirrored record with `data_remove` fails closed.
7. In game, on staging only: after R9, the barrel at (5363, 131, 493) holds ice and no crown; the crop at
   (5361, 134, 514) is ripe; a thrown iceroot carrot spawns Glastrier at (5364, 136, 522); and whether the carrot
   is consumed.
