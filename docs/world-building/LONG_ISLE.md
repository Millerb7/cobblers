# The Long Isle: a desert island, a jungle island and a sea town

**Status: design proposal, 2026-09-25. Nothing here is built, sited in data, or decided.**
Answers EXP-035 row 30. The owner's note:
*"the long isle feels pointless as a biome/region. need to have a design for it. im thinking maybe make the long isle a
desert and jungle island and have the jungle island become a town on the sea. specifically pacifidlog from hoenn
expanded and transported here. it should be big on fishing and boating/surfing (pokemon surfing maybe real surfing too)"*.

The labels used below: **VERIFIED** means read in this repository's data, tools or experiment records (the source is
cited). **ESTIMATE** means derived from the region polygons, which are simplified to 24 blocks, and not measured on the
heightmap. **NOT VERIFIED** means nobody has checked it in game or in a jar.

## 1. What the island is today

| | North | Middle | South | Whole island |
|---|---|---|---|---|
| Sub-region | `long_isle_north` | `long_isle_middle` | `long_isle_south` | `long_isle` |
| Area km² | 0.644 | 0.836 | 1.082 | 2.559 |
| Bounds x / z | 7568-8159 / 4432-5815 | 7304-8191 / 5576-6919 | 6832-8135 / 6856-8023 | 6832-8191 / 4432-8015 |
| Ground median / p90 / max | y90 / 107 / 124 | y119 / 144 / 148 | y119 / 144 / 149 | y106 / 142 / 149 |
| Slope p90, flat under 5° | 19.2°, 22% | 24.2°, 17% | 22.5°, 22% | 22.6°, 20% |
| Paint preset | `taiga_sparse` | `forest` | `sparse_jungle` | |
| Roster (`data/spawns.json`) | Deerling, Zigzagoon, Nickit, Rookidee, Skwovet and their lines | Deerling, Nincada, Seedot, Applin and their lines | Chatot, Deerling, Fomantis, Bounsweet, Squawkabilly, Wimpod | band 25-45, `signature_overlay_keep_defaults` |

VERIFIED from `data/regions.json` and `data/spawns.json`. The island covers cells E8, F8, G8 and H8, and its
south-west arm reaches H7.

- **Why it feels pointless.** It holds no settlement, no event and no find. No route reaches it: the nearest leg is
  913 blocks from the north end (`route_07_sabrina_to_blaine`) and 1,585 blocks from the south end
  (`route_08_blaine_to_giovanni`, `docs/story/AVAILABILITY.md:829-833`). Its three rosters are generic woodland, and
  `docs/world-building/ROSTER_AUDIT.md:32` flags Deerling in the jungle as the wrong country. Its three biomes repeat
  Northgate and the Jungle Isle.
- **Its neighbours are already desert.** The East Coast Dunes and the South-East Dunes (`eastern_dunes`, preset
  `desert`) face it across a strait on the west. The Mining Town (6633, 5716) is the nearest settlement, about
  700 blocks west of the strait.
- **The Long Sound (ESTIMATE).** The strait on the west side runs north to south:
  - about 180-300 blocks wide at z5200-5600, where the dunes' coast is at x7344-7392 and the island's at x7568-7664;
  - about 120-150 blocks wide at z6100-6500, its narrowest point, near (7300-7400, 6500);
  - then it opens south-west into a bay about 300-430 blocks across, between the South-East Dunes' coast (7280, 6504)
    to (6856, 6856) and the south isle's north-west shore (7296, 6856) to (7008, 7304).

  The middle and south sub-regions meet the west coast at (7304, 6856), at the head of that bay.
- **The sea there.** The planned marine region is the Southern Shallows, which is warm and planned with reefs
  (`OCEAN.md` §3). OCEAN.md predates the rescale and says so. No seabed pass and no coral exist. The water depth in
  the bay is NOT measured.

## 2. Its role in the game

- **Slot:** an optional detour between badge 6 and badge 8. It is not a leg. The land approach crosses the Tilpey
  outflow gorge, the barrier between badges 6 and 7 (`data/towns.json` gym7_town). It then runs through the East Coast
  Dunes or from the Mining Town, which Route 8 leaves at 905 blocks off the path. It is the east's counterpart to Sunset
  West, the western harbour, which is post-game in content (`SETTLEMENTS.md`).
- **Level band, proposed 44-50 on land and in the sea.** With `relativeLevelCap` 0 and gym aces of
  20/25/30/35/40/45/50/55 (`data/trainers.json` `generation_contract`), a player holding 6 badges is capped at 50,
  Blaine's ace. Route 7's pools run 41-46 and Route 8's 47-52 (`data/spawns.json` `level_band`). The current flat
  25-45 was a placeholder with no `basis_route`.
- **The risk that decides the band: the sea is open from the start.** A boat bypasses the gorge. A player who sails
  here at badge 3 meets 44-50 wild Pokémon, catches one, and falls into the level-cap trap (STATE "What is open";
  EXP-035 row 13). So the band, and whether the island is reachable early, are one decision with the trap's fix (§9 D5).
- **Pacing.** The owner found the first three gyms too quick (EXP-035 row 16). Fishing and boating are slow, repeatable
  play off the critical path, and this is the first place in the game built around them.

## 3. The split: a desert island and a jungle island

**Recommended line: the existing cover boundary between the middle and the south.** It is 928 blocks long, runs from
(7304, 6856) on the west coast to about (8128, 6920) on the east, and both sides have a median of y119.

| Island | Ground | Area | Character |
|---|---|---|---|
| **Desert island** (the north and middle sub-regions) | y66-148; low dunes in the north (median y90), sandstone uplands in the middle (the "rocky middle" in `SCULPT.md`) | 1.48 km² | Desert paint on both. The middle's rocky coast reads as sandstone cliffs. A dry continuation of the dunes across the Sound |
| **Jungle island** (the south sub-region) | y71-149, hilly | 1.08 km² | `jungle` paint in place of `sparse_jungle`, thicker, as the owner asked for the Jungle Isle (row 29). Hosts the sea town on its north-west shore |

The alternative puts the line at the north/middle boundary (about 848 blocks long). The desert island would then be
only the low north (0.64 km²), with a jungle three times its size. That is an owner decision (D2).

**Does it need a terrain change?**
- **The biome split does not change the heightmap.** It is paint:
  - `paint.preset` changes on the three sub-regions in `data/regions.json`;
  - `data/foliage.json` changes three forest types: the "Coastal spruce", "Mossy broadleaf" and "Jungle edge" entries
    for the Long Isle (`FOLIAGE.md:103-106`);
  - `tools/paint_maps.py` and `tools/worldpainter/paint.js` apply it.

  Paint reaches a world only through a WorldPainter re-export. The other route is a block pass that runs after the
  export, as the Rift's skin does (`/fillbiome` plus replacing the surface, `tools/rift_skin.py`). That is heavier, but
  it does not depend on the export.
- **Making them literally two islands does change the heightmap.** A channel cut along the seam would be about
  830-930 blocks long through ground at a median of y119 (ESTIMATE). It would be a new brush in the style of
  `data/sculpt.json`, or a small tool like `tools/rift_heightmap.py`, written into the **canonical heightmap**. That
  means a new sha256 in `data/world.json` and a re-export. After it, `cell_stats.py --write-cells`,
  `visibility_claims.py`, `measure_towns.py` and the region measurements are re-run. It lands in the world only with
  the next export. A beach coast (adding `long_isle` to `sculpt.json` `coast.soft_regions`) and a desert lagoon basin
  would also be heightmap changes. Deepening the Sound, if §4's slice finds it too shallow, is one too.
- **Recommendation:** start with paint only (option A). The town and the fishing do not need the channel, because the
  rafts float on water that already exists. Decide the channel (option B) before the island is built on, because every
  later build on it would be re-seated on the new ground.

## 4. The sea town ("Pacifidlog", working name)

**Site (ESTIMATE):** in the Sound's bay, off the jungle island's north-west shore. The centre is about (7120, 6880):
about 240 blocks from the dunes' coast, 170 from the jungle shore to the east, and 300 from the Mining Town's side of the
water. The rafts reach from the jungle shore out into open water, at the point where the desert and jungle islands meet.
The tool measures the water depth and width before anything is sited (§7).

**Deck level:** the logs replace the top water layer at y62 (`data/world.json` `water_level` 62), so players walk at
y63. That the export's top water block is y62 is NOT VERIFIED. The plan tool takes the level from data, and the verify
step reads the world only to check it.

**Access:** by water only, which is Pacifidlog's defining trait. A jetty on the South-East Dunes' coast at about
(7150, 6620) has a bell, a boat rack and a signpost; the town is about 260 blocks across the water. No causeway, unless
the owner decides otherwise (D4).

| District | What it is | Holds |
|---|---|---|
| **Old Rafts** (the Pacifidlog core) | 12-16 log rafts, 11×11 to 17×17, linked by log bridges 3 wide over a loose grid of about 140×140 | Centre and Mart on the two largest rafts (about 21×21); a hut on each raft; the waystone; a bell raft as the town square |
| **Fishers' Row** | a pier 5 wide and about 120 long, out to the Sound's deepest water | a fishing station every 8 blocks (seat, barrel, lantern), 12 or more stations; the Fishing Guild hall at its root (rod master, catch board, smokehouse) |
| **Boatwright's Yard** | on the jungle shore | a slipway, a boat shed, a hull in frame, a boat rack, bamboo rafts; a boatwright trader (boats sold, so they are obtainable without crafting) |
| **Stilt Quarter** | 8-12 houses on mangrove-log stilts in the shallows along the jungle shore | mangrove roots, hammocks, the inn (with beds, for respawn) |
| **Current Gate** | a floating breakwater and lookout at the bay's south-west mouth, facing the open sea | the surf spot (§5); the swimmer's hut; the deep fishing water |
| **Mainland jetty** | the outpost on the desert shore | the boat rack, a signpost to the Mining Town |

- **Services:** a Centre and a Mart. The Mart has a clerk with `data/traders.json` stock `mart`, as in the 13 placed
  Marts. A fishing-supply trader and the boatwright are proposed; their stock is D6.
- **Lighting:** lanterns on posts and on raft floors, never light blocks (STATE "Places are lit as towns").
- **Palette:**
  - vanilla jungle, mangrove and bamboo wood (planks, mosaic, logs, stripped logs, mangrove roots), lanterns, chains
    and barrels. None of these appears in `data/spawn_blocks.json`;
  - furniture from Handcrafted, CobbleFurnies and Cozy Home; rope and hanging pots from Beautify; hammocks from
    Comforts. All are world-critical mods in the manifest.

  Exact mod block ids are to be read from the jars before a palette is authored.
- **Blocks that decide spawns:** water, sand, seagrass, kelp, lily pads and coral are in `data/spawn_blocks.json`. The
  town's water is the point, so it needs one deliberate `data/spawn_block_policy.json` entry, like gym2_town's. Hay is
  a spawn block, so the roofs are not thatched with it.

## 5. Boats, riding and "surfing"

| Way onto the water | Status |
|---|---|
| Vanilla boats, chest boats, bamboo rafts | Vanilla. They are entities: a boat left somewhere is gone from the rack. A keeper function would top each rack up when fewer than N boats are inside its box, following the pattern of the Celebi keeper (`tools/sapling_celebi.py`). NOT VERIFIED |
| Riding a water Pokémon ("Pokémon surfing") | **NOT VERIFIED.** VERIFIED only that land and air riding work on this stack: Mudsdale and Charizard (`docs/research/COBBLEVERSE_COMPATIBILITY.md:5, 221`). `tools/patch_cobbleverse_riding.py` migrates COBBLEVERSE-DP-v31's riding seats for 1.8: 51 native-locator mounts, with 182 offsets kept. Which of the 233 are water mounts, and how they behave on water, has not been read or tried. ASSUMED that Cobblemon's riding includes swimming mounts. The breath and descent question is OCEAN.md's proposed EXP-015 |
| "Real surfing" | No surfboard or wave mod is in the stack. Adding one is a new dependency (principles 5 and 9) and is not proposed. The closest vanilla feel is a current lane: a stepped raceway of flowing water at the Current Gate that carries boats and swimmers. NOT VERIFIED that it reads as surfing |

## 6. Fishing and encounters

**The rod rule (STATE "What is decided"):** First Cast gives the Poké Rod, and better rods are found at other waters.
The Long Isle offers three distinct waters, each with one rod find:

| Water | Where | Character | Rod find (proposed) |
|---|---|---|---|
| **Under the rafts** | the Old Rafts and Fishers' Row | sheltered, shallow and mid-depth | the Guild's rod master, a per-player dialogue grant (`grant_reward_once`) |
| **The Current Gate** | the bay mouth, facing the open sea | deep, moving water | a barrel at the lookout, a per-player advancement find (ADR-002, `data/rewards.json`) |
| **The desert lagoon** | a brackish pool in the desert's low north (optional; a basin is a heightmap change) | still, shallow | a barrel in the lagoon hut |

**Which rods:** blocked. What a rod's ball changes when fishing is not researched (STATE "Early fishing balance"). The
rod item ids (for example `lure_rod`, `net_rod`, `dive_rod`) are ASSUMED and must be read from the Cobblemon 1.8.0 jar.
Bait is not researched either.

**How fishing spawns would be authored:**
- as `data/spawns.json` entries with `spawnable_position: "fishing"` inside coordinate boxes over each water.
  `tools/compile_spawns.py` passes the position type through (`position_type`, line 71), and `tools/position_types.py`
  confirms `fishing` is an upstream position type;
- no fishing entry exists anywhere in the data today;
- NOT VERIFIED that Cobblemon honours box conditions on fishing spawns;
- Habitat Blocks carry an `affectsFishing` flag in source (`docs/research/notes/habitat-blocks-underground.md:136`),
  but fishing replacement is untested (EXP-021).

**Encounter intent.** The tables belong to `trainer-balance-designer`. These are candidates, and every one listed here
has no authored home today (`docs/story/ENCOUNTER_GAPS.md:7-15`):

| Place | Candidates |
|---|---|
| Sound: surface and submerged | Tentacool line, Mantyke/Mantine (shelf, `minY 48`), Finneon line, Frillish line |
| Sound: fishing under the rafts | Magikarp, Remoraid/Octillery, Horsea/Seadra, Luvdisc, Qwilfish |
| Current Gate: deep water and fishing | Wailmer line, Carvanha/Sharpedo, Chinchou/Lanturn (night), Skrelp line, rare Lapras, Relicanth (dark water, `maxY 48`) |
| Reef, only if coral is placed (coral decides spawns) | Corsola, Luvdisc, Bruxish (`warm_ocean` only), Pyukumuku on the beach |
| Desert island | Sandygast/Palossand on the beaches, Zangoose and Seviper (Hoenn's rival pair), Yamask, Castform (a Hoenn weather nod) |
| Desert lagoon (fishing) | Barboach line, Feebas ultra-rare (weigh it against Milotic as Victory Road's prize) |
| Jungle island | keep Chatot, Fomantis, Bounsweet, Squawkabilly and Wimpod; drop Deerling; add Dewpider/Araquanid, Grubbin line |

- **Trainers:** Swimmers and Fishers along the Sound, and Sailors at the jetty. They are `trainer-balance-designer`'s
  to write.
- **Spawn policy:** the island is `signature_overlay_keep_defaults` today, so Cobbleverse's own ocean pools stay live
  beside ours. A curated fishing town probably wants `exclusive_curated` over the Sound. That costs suppression boxes
  (grid 16, heap) and is D8.

## 7. How it is built in this repository

The ground comes from the heightmap: the seabed under a raft is `tools/ground.py` `round(h)`, and the deck is
`water_level`. The rule is in CLAUDE.md, "Ground comes from the heightmap".

| Piece | Where | Notes |
|---|---|---|
| Island paint | `data/regions.json` presets, `data/foliage.json` | applied at re-export (§3) |
| Settlement record | `data/towns.json` (new id, working name, `display_name` null until named); `tools/measure_towns.py` rewrites the measurements | `built_ground` over water, as for Relic Island |
| Town layout | **new** `data/sea_town.json` (rafts, bridges, piers, stilts, racks, stations, lantern posts) | a template has no position; the layout is placement data |
| Generator | **new** `tools/sea_town.py`: `plan` / `build` / `verify` | `plan` refuses a raft over water shallower than N, over land, or overlapping. `build` emits mcfunctions through `tools/function_limits.py` (chunks held, fills split). `verify` reads the world only to check the result |
| Re-apply | a new `tools/reapply.py` step | `prepare` fails closed on a pack with no step |
| Centre and Mart | `kits/structures/campaign/f4/services/towns/*` (MIT, CobblemonCityTowns), re-materialed in jungle or bamboo wood by `tools/rematerial.py` and `data/rematerial.json`, as for `sunset_center`; placed via `data/placements.json` | committable |
| Huts, stilts, guild, boat shed | written by `tools/sea_town.py` (licence `generated`, a `kits/PROVENANCE.json` record) | committable |
| Clerk and traders | `data/traders.json`, `tools/traders.py` | |
| Rewards | `data/rewards.json`, `tools/rewards_pack.py`, `data/dialogue.json` | per player |
| Titles, signposts, waystone | `tools/location_titles.py` (settlements automatic), `data/signposts.json`, `data/progression.json` | |

**Donor search:**
- No Pacifidlog-like structure exists in the 254 records of `data/structures.json`, in `kits/`, or in
  `kits/structures/manifests/pokemon-town-donors.json`.
- The only "Pacifidlog" string in the installed packs is a Waystones name-generator word
  (`base-pack/cobbleverse/config/waystones-common.toml:185`).
- CobblemonCityTowns 1.0 (MIT) is recorded here only by its Pallet set and four Centre/Mart pairs. Whether its archive
  holds a Hoenn sea town is NOT checked; look before generating from scratch.
- Repurposed Structures' ocean-village houses are placed by id and never committed, as in gym2_town
  (`data/placements.json:5033-5041`).
- Finding: `base-pack/inventory/licenses_pdf_entries.json:177-186` pairs Repurposed Structures with "MIT" and
  ResourcefulLib's URL, and ResourcefulLib with "LGPL-3.0-only" and Repurposed Structures' URL. The two entries look
  crossed. Keep Repurposed Structures local-only until the dependency-auditor settles it.

## 8. Phased plan

| Phase | Work | World |
|---|---|---|
| **0: decide and measure** | The owner answers §9. A read-only measurement on the canonical heightmap gives the Sound's width and depth profile, the seam's heights and, for option B, the channel's volume. Research: rod ids and what a ball does from the jar; water-mount species from the patched pack | none |
| **1: prototype slice** | Old Rafts core only: 5 rafts (Centre, Mart, 3 huts), bridges, a 40-block pier with 4 stations, the mainland jetty and boat rack, one fishing box of 3-4 species over the pier, lanterns. Two experiments: fishing in a box (does it spawn only there, at its band?) and surf (ride 3 candidate water mounts across the Sound: speed, breath, dismount, a wild battle while mounted). Success: every deck block at plan y, no leak or flow, the verify clean, the owner fishes and boats across; with a second account, two players at once | staging only |
| **2: the islands** | Repaint (desert/jungle) at the next re-export, or a block pass. Rosters rewritten by `trainer-balance-designer`; Deerling dropped | re-export |
| **3: the full town** | Fishers' Row and the Guild, the Stilt Quarter, Boatwright's Yard, the Current Gate, the three rod finds, trainers | staging, then live |
| **4: optional** | the channel (option B), the desert lagoon, a coral reef, a dive wreck | heightmap and re-export |

Principle 20 applies: nothing beyond phase 1 before the deck, the fishing boxes and the boats are proven.

**Hook, out of scope:** OCEAN.md's Maelstrom Trench (a proposal, unbuilt, in the border margin) curves past the jungle
island's east coast at about (8200, 7400). A town of fishers and divers is its natural base.

## 9. Owner decisions

1. **D1: two islands or one?** Paint only, one island with two faces (option A, no heightmap change); or cut a channel
   and re-export (option B).
2. **D2: where the desert ends.** North and middle desert (recommended, 1.48 km² against 1.08); or north only.
3. **D3: name.** "Pacifidlog" outright, or an original name with Pacifidlog as the inspiration.
4. **D4: access and fast travel.** Water only (recommended) or a log causeway. The waystone: discovery, a badge flag,
   or none (the jetty is the way in).
5. **D5: level band and early arrival.** 44-50 as the badge-6-to-8 detour. Accept that a boat can bring a player early,
   or tie it to the level-cap trap's fix (a warning on catch, or capped spawns).
6. **D6: rods and shops.** Which rods live here (after the research), and whether each is a find, a quest reward or
   stock. Does the fishing trader sell balls beyond the Mart's three?
7. **D7: "real surfing".** Accept water-mount riding, boats and a current lane without a new mod (recommended).
8. **D8: spawn policy.** Curate the Sound exclusively (a cost in suppression boxes), or overlay on Cobbleverse's ocean
   pools.
9. **D9: coral.** Place a reef (the Corsola line; coral is a spawn block) or not.
10. **D10: timing.** Land the paint with the pending live re-export (another staging rehearsal), or wait for a later one.
11. **D11: the rafts' protection.** Survival, where a friend can break a deck and re-apply restores it; or adventure
    mode inside the town, as in the mansion.
