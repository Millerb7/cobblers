# Structure placement: decisions after Step 1

**Status: for review. Steps 2 and 3 wait for approval.**

This follows `STRUCTURE_INVENTORY.md` (Step 1). It records the decisions made on 2026-09-13
and what the experiments showed. It then proposes the scatter distribution and the
legendaries to author. Companion documents:

| Document | Covers |
| --- | --- |
| `DIMENSIONS_AND_BORDERS.md` | borders, trim, Nether and End pregen and audit, progression |
| `OCEAN.md` | depth, marine regions, seabed pass, underwater content |
| `WORLDGEN_FEATURES.md` | ores, apricorns, berries, fossils, and the scatter script |
| `TOWNS_AND_VILLAGES.md` | what replacing villages costs |

## 1. Nether and End stay vanilla

**Removed from the relocation list.** These generate where the game puts them, in their own
dimensions:

| Structure | Class | Dimension |
| --- | --- | --- |
| `cobbleverse:blaine` | PROGRESSION | Nether |
| `cobbleverse:kanto_league` | PROGRESSION | End |
| `cobbleverse:legendary/moltres` | LEGENDARY | Nether |
| `legendarymonuments:firescourge_shrine`, `grasswither_shrine`, `groundblight_shrine`, `icerend_shrine` | LEGENDARY | Nether |
| `legendarymonuments:eternatus_cocoon` | LEGENDARY | End |
| `cobbleverse:dawn_tower`, `cobbleverse:dusk_tower` | LEGENDARY | End |

**How `data/structures.json` records it:**
- Every Nether and End structure now has the disposition "keep: vanilla-generated in its own
  dimension; audit after pregen within that dimension's border".
- Giratina's island keeps the disposition "generates in the Distortion World dimension".
- The hand-place-everything rule applies to the overworld region only.

**What this buys:**
- Nether and End structures carry real structure data. Their structure-gated spawns and
  locators keep working there: bastions and fortresses for the Charcadet line, End cities
  for the Gothita line, the towers for Poipole.

## 2. The six experiments (EXP-013)

Run headless on a disposable copy of the world. The live world was not booted or edited,
and `server.properties` was restored byte-for-byte.

| Exp | Question | Result |
| --- | --- | --- |
| **A** | Does any placement method write structure data? | **No.** `/place structure`, `/place jigsaw` and `/place template` all left `starts` and `References` empty. `/locate` and `location_check` ignored every placed build, while natural controls passed |
| **B** | Does `/place structure` land right on painted terrain? | **No, for jigsaw structures.** Village houses were buried 31–54 blocks and Brock's gym 20 blocks under the surface. `/place jigsaw` dropped the houses. Igloo and templates landed correctly. The desert pyramid refused to place, cause unknown |
| **C** | Do template command blocks run? | **Not on placement.** Brock's chain runs only when its pressure plate is pressed and `enable-command-block=true`. Any entity can press the plate |
| D | Do Cobblemon structure-gated spawns fire at a pasted site? | **Not run: needs a player.** Predicted to fail, because the chunks have no starts |
| E | Do pasted RCT trainer spawners spawn? | **Block data survives** (`TrainerIds` intact). Spawning needs a player |
| **F** | Does the Cobbleverse gym map find a pasted gym? | **No.** 6 maps, none pointed at a hand-placed gym |

**The approach is settled by A:**
- **Paste with `/place template` or objects at an explicit Y.**
- **Never paste with `/place structure` or `/place jigsaw` on painted terrain.**
- **Replace every system keyed to structure data in the overworld:**

| System | Replacement |
| --- | --- |
| Structure-gated spawns | Habitat Blocks, or datapack overrides with non-structure conditions |
| Gym maps, cartographer maps, radars | removed; flag-driven waystones and Xaero markers (`NAVIGATION.md`) |
| `location_check` advancements | position or scoreboard triggers |

**D and E need one player for about 15 minutes** on the disposable world
`exp013-structures`, which is still in the server folder. They confirm a prediction and a
source reading; they do not change the approach. The test steps are in
`experiments/EXP-013-hand-placed-structures/README.md`.

### Species that only spawn with a structure

Weight above 0, presets resolved. Whether each one survives:

| Species | Needs | Where that structure is now | Survives? |
| --- | --- | --- | --- |
| Charcadet, Armarouge, Ceruledge | bastion, fortress or ruined portal | Nether: vanilla; overworld ruined portals: pasted | **yes, in the Nether** |
| Gothita, Gothorita, Gothitelle | mansion or End city | End cities: vanilla; mansions: pasted | **yes, in the End** |
| Poipole | Dawn or Dusk tower | End: vanilla | **yes** |
| Gimmighoul | `#cobblemon:ruin` | overworld ruins, pasted | **no, needs replacement** |
| Tinkatink, Tinkatuff, Tinkaton | `#cobblemon:ruin` | overworld ruins, pasted | **no, needs replacement** |
| Sinistea, Polteageist | village or mansion | pasted | **no, needs replacement** |
| Poltchageist, Sinistcha | village | pasted | **no, needs replacement** |
| Galarian Articuno, Zapdos, Moltres | `cobbleverse:dyna_tree` | disabled pack | no structure anywhere |
| Raikou, Entei, Suicune | `cobbleverse:burned_tower` | disabled pack | no structure anywhere |

**Eight species need a spawn replacement** before the overworld feels complete. They are
the ruin line and the tea line.

## 3. Scatter: 150 placements

**Scope:**
- **Counted:** SCATTER structures only, hand-placed from tool-produced candidates in Step 3.
- **Not counted:** PROGRESSION, LEGENDARY and NAMED sites, and features. Trees, ores,
  berries and fossils are distributions (`WORLDGEN_FEATURES.md`).
- **Start low.** Adding later is easy; thinning a built map is not.

**Priorities:**
- **Economy and spawn points first.** Habitats, mega sites, and ruins (which feed
  Gimmighoul) carry value. Flavour families get a token presence.
- **Per region, the share follows land area** (about 2.5 per km²). The Rift is cut back
  because it is an anomaly with its own content, and Strand Flats is lifted to a minimum
  of 3.
- **The ocean gets about a quarter.** It is 56% of the world by area, but underwater
  content is sparser and deliberately hard to find.

### By family

| Family | Land | Sea | Total | Why this many |
| --- | ---: | ---: | ---: | --- |
| Cobblemon habitats: surface | 28 | 6 | 34 | spawn points that work pasted; about 2 per land region; icebergs 2, reefs 3 and the deep sea spire at sea |
| Cobblemon habitats: underground | 10 | | 10 | spawn points for the underground biome plan (dripstone, lush, deep dark) |
| Cobblemon ruins: arches, pillars, crypts, Gimmighoul towers | 24 | | 24 | relic coins and gilded chests (Gimmighoul economy); Tinkatink and Gimmighoul spawns once replaced |
| Mega Showdown mega sites | 12 | | 12 | every raw mega stone comes from these; 12 is a deliberate scarcity, and authored rewards supply the rest |
| Mineshafts, vanilla and RS by biome | 14 | | 14 | underground exploration with a regional look (mesa, icy, jungle, dark forest, stone) |
| Ruined portals | 8 | 2 | 10 | loot and Nether foreshadowing before gym 7 |
| Pyramids and temples, vanilla and RS | 8 | 1 | 9 | loot dungeons in their biomes; the RS ocean pyramid in the Outer Deep |
| Trail ruins | 5 | | 5 | archaeology |
| Igloos | 3 | | 3 | Northern Isles and Glacier Valley |
| Witch huts | 2 | | 2 | swamp edges |
| Fishing boats | 2 | 4 | 6 | coast and sea-lane loot |
| Shipwrecks (sunk 5, beached 2) | | 7 | 7 | `OCEAN.md` tiers 0–1 |
| Ocean ruins (cold 3, warm 5) | | 8 | 8 | slope content by temperature |
| Buried treasure (3 without a heart of the sea, 2 with) | | 5 | 5 | hearts only in tier-2 sites; each one is a conduit |
| Submerged forge ruins | | 1 | 1 | Windward Deep basin |
| **Total** | **116** | **34** | **150** | |

**NAMED ocean sites are outside the 150:** the three shipwreck coves, the monument and the
trench set piece.

### By land region

| Region | Area km² | Placements |
| --- | ---: | ---: |
| Lakeshore Vale | 5.82 | 15 |
| Northern Range | 5.15 | 13 |
| Southern Isles | 4.71 | 13 |
| Eastern Downs | 3.58 | 10 |
| Ember Highlands | 3.46 | 9 |
| Glacier Valley | 3.03 | 8 |
| Leeward Plateau | 2.89 | 7 |
| Windward Coast | 2.85 | 7 |
| Northern Isles | 2.72 | 7 |
| Rim Uplands | 2.60 | 7 |
| Stillwater Basin | 2.57 | 6 |
| Jungle Isle | 2.51 | 6 |
| The Rift | 3.77 | 5 |
| Strand Flats | 0.77 | 3 |
| **Land total** | 46.4 | **116** |

Step 3 assigns families to regions by the biomes each accepts (`data/structures.json`,
`plan_regions_with_a_valid_biome`). It enforces spacing per class in the validator.

## 4. Legendaries from the disabled packs: take six

The disabled Johto, Hoenn and Sinnoh packs name these legendaries without a loaded
structure:
- **Johto:** Lugia, Ho-Oh, Celebi.
- **Hoenn:** Regirock, Regice, Registeel, Latias, Latios, Kyogre, Groudon, Rayquaza,
  Jirachi, Deoxys.
- **Sinnoh:** Dialga, Palkia, Regigigas, Cresselia, Phione, Manaphy, Darkrai, Shaymin,
  Regieleki, Regidrago.

**That is 23 species.** `STRUCTURE_INVENTORY.md`'s summary row says 24; its species table
lists 23. The difference is still to be reconciled.

**Recommendation: author six, as four encounters.** Build each properly: an authored site,
concealment, and a trigger that does not depend on structure data. Do not import the
donor templates.

| Pick | Where | Why this one |
| --- | --- | --- |
| **Lugia** | the Maelstrom Trench, the Outer Deep (`OCEAN.md`) | The ocean is 56% of the world and needs an apex reward. Lugia is the one sea legendary that stands alone, where Kyogre wants Groudon and Rayquaza. It turns depth gating and the three-cove key search into a destination |
| **Regirock, Regice, Registeel** | Ember Highlands (badlands), Glacier Valley (ice), the Rift (the anomalous steel chamber) | This is the classic systematic-search puzzle for a co-op group. Each golem uses a region identity that already exists. The three share one authored key mechanic, so it is one system, not three builds |
| **Regigigas** | beneath the glacier, in or beside the Displaced City (Step 2) | This is the concealment model you named: a sealed site signposted from afar, opened only by bringing the three golems. It gives the Displaced City a reason to exist below the ice |
| **Groudon** | the Mining Town's deep workings under the volcanic cone (Step 2) | The region plan already has a volcanic cone and a mine. Groudon rewards going deeper than the fossil levels, and depth gates it through heat, lava and darkness. Without Kyogre it is framed as the mountain's sleeper, not half of a weather duel |

**Not picked, and why:**

| Species | Reason |
| --- | --- |
| Kyogre, Rayquaza | the trio collapses without all three. Rayquaza already has a loaded function that spawns it in the End |
| Ho-Oh, Celebi | good, but they duplicate roles: Moltres covers the fire bird, and the Stillwater cherry basin is better left to its own story |
| Dialga, Palkia | the strongest runners-up for the Rift, but they pull the campaign into a time-and-space plot. Giratina, with the loaded Distortion World, already occupies that lane |
| Latias, Latios, Jirachi, Deoxys, Cresselia, Darkrai, Shaymin, Phione, Manaphy, Regieleki, Regidrago | roaming, event or mythical mechanics that need their own systems; better as later additions |

**Whether a player can meet each one** depends on how its trigger works without structure
data. That is part of Step 3, and it is the first thing each authored site has to prove in
game.

## 5. What Steps 2 and 3 now inherit

- **Placement method:**
  - templates and objects at an explicit Y;
  - no structure data;
  - every structure-keyed system replaced (section 2).
- **Nether and End:** vanilla, audited after pregen. Only their entrances are authored: the
  End portal room after Giovanni (`DIMENSIONS_AND_BORDERS.md`).
- **The ocean:** five marine regions, the seabed pass, 34 scatter placements, the NAMED
  coves and monument, and the trench (`OCEAN.md`).
- **Features before scatter:** apricorn trees, stone and type ores, berries, mints and
  fossils (`WORLDGEN_FEATURES.md`).
- **Towns:** Habitat Blocks for town Pokémon, placed villagers, authored trades
  (`TOWNS_AND_VILLAGES.md`).

**Still waiting on you:**
1. Approval of Step 1 as amended.
2. The pregen method: Chunky or a forceload script.
3. Rayquaza at the End spawn: keep, gate or remove.
4. Rolled or authored villager trades.
5. The six legendary picks.
6. One player session for EXP-013 D and E.

## Legendary structures: candidates, not on Route 1 (2026-09-17)

Cobbleverse ships each legendary encounter as a structure with a LumyMon summon block: the block consumes an
activation item, checks a summon anchor nearby and spawns the Pokémon at level 70-90. The gate is therefore the item,
not the place. Two suit a forest:

| Structure | Template | Size | Summon block and item | Notes |
| --- | --- | ---: | --- | --- |
| Mew's shrine | `cobbleverse:mythical/mew` (installed) | 37 x 25 x 39 | `lumymon:mew_shrine`, Origin Fossil (craftable, `lumymon:recipe/origin_fossil`) | its command blocks also gate on Cobbleverse's own "defeat champion" advancement, which our progression does not grant. Carries a Z-crystal, TMs and ancient balls |
| Crown Cemetery (Calyrex) | `cobbleverse:crown_cemetery` (installed) | 45 x 24 x 47 | `lumymon:calyrex_statue`, Calyrex Crown | old-growth pine country; brushable gravel loot (TMs, vitamins, rare items) |

The Johto pack also ships `cobbleverse:celebi_shrine` (Ilex shrine, `lumymon:ilex_shrine` plus a GS Ball), but that pack
is not enabled and it would duplicate the Celebi planned for the Route 1 sapling.

**Not on Route 1.** The maze forest's openings are the sapling clearing (r20), the mansion clearing (r22), three
glades (r10-11) and three secret glades (r8-9); its dead ends are 3 blocks wide. Either structure needs roughly a
30-block clearing, which is a hole in a maze whose whole point is enclosure, and their loot is late-game on a first
route. Both stay as candidates for a place with room: see the region rosters for where a shrine would fit.
