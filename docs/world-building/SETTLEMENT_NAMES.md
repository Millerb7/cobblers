# Settlement names

**Status:** proposed 2026-09-27 by Claude, with the owner's instruction to make the call. The owner, Codex, or
both may change any of them. The names are written into `data/towns.json` `display_name`, each with a
`display_name_why`. Until now every settlement showed its working name.

## Where a name shows

- **One list feeds both.** `tools/signposts.py` `place_names()` returns a settlement's `display_name` from
  `data/towns.json` when set. Otherwise it falls back to the working name in `data/signposts.json` `names`.
  The route signposts and `tools/location_titles.py` both read this list, so a name lands on both at once.
- **Signposts** stand only at route-leg ends (the hometown, the eight gym towns and the League), at sub-region
  changes and at the Route 1 mansion junction. A sign line holds 15 characters, and a longer name wraps.
- **Location titles** cover the 26 settlements below plus the Route 1 mansion and old mine. Those two are not in
  `data/towns.json` and keep their `data/signposts.json` names, "the old manor" and "the old mine". The 4 landmark
  trees get no title and no sign. Their names are set so the file has no null left.
- **Nothing reaches a world until a re-apply.** The signs are placed by `cobblers:signs/place` and the titles by
  the `cobblers_titles` pack, both rebuilt under `build/`.

## How they were chosen

- **Native towns get native names.** The leaders are natives of this region (`docs/story/ARC.md`: Giovanni "is a
  native leader"), so no gym town takes a Kanto name.
- **Pallet Town is the exception.** It is the one town that came from elsewhere, and the premise fixes its name.
- **Each gym town's name carries the leader's type and the town's civic role** in the story and its plan's
  reading (`data/placements.json`).
- **Names already in the story are kept:** Sunset West, Northlight, Viltri Light, Relic Island, the Scar, the
  Displaced City, Merian Hut, Frostpeak Shrine, and Pacifidlog, which the owner reused from Hoenn on purpose.
- **Mainline Pokemon town names are avoided** except Pallet Town and Pacifidlog.
- **Names fit their signs.** A sign line holds 15 characters and a sign 4 lines. A sub-region transition sign
  reads route, sub-region, "to" and the name, so a signed name must fit "to <name>" in 15 characters there.
  The regenerated signs were checked for any text lost at the 4-line limit: none is. Before this pass 2 were,
  both "to Pokemon League" on Victory Road. The names over 15 characters (The Displaced City, Frostpeak Shrine,
  The Cherry Elder) carry no sign.
- **Where a name can keep old geography, it does** (`SQ-G2-02`: "names preserve older geography after the land
  itself changes").

## The names

"Codex" marks a name the story owner should confirm: it adds a claim to the fiction or changes the tone. A name
without the mark is the story's own name, or is purely descriptive.

| id | Working name | Display name | Why | Confirm |
| --- | --- | --- | --- | --- |
| `hometown` | Hometown | **Pallet Town** | The premise fixes it (`ARC.md`: "Pallet Town is established by the premise"). The one Kanto name, so it reads as the town that does not belong | |
| `gym1_town` | Gym 1 town (Brock) | **Stoneford** | Brock's builders on the Viltri Plateau. A stone crossing named for a river that no longer runs, like the plateau's river-worn stonework (`SQ-G1-01`). Rock | **Codex**: it puts a lost river at the town |
| `gym2_town` | Gym 2 town (Misty) | **Viltri Quay** | Misty's lake town, where boats tie up, rescue crews sort what the lake brings, and Compact families come ashore (ARC Settlement 3, `SQ-G2-01`). Water. Not "Viltri Landing", which overflows two transition signs | Codex |
| `gym3_town` | Gym 3 town (Ltsurge) | **Highwire** | One walk along the lip of a drop, under the signal array's line up the shoulder. Electric, and a town on a tightrope | **Codex**: the lightest in tone |
| `gym4_town` | Gym 4 town (Erika) | **Greenhollow** | Built round a green, not a square, in Peak Pond Hollow, and home to native and Compact families alike (`SQ-G4-02`). Grass | Codex |
| `gym5_town` | Gym 5 town (Koga) | **Fenhide** | Beside a fen; the gym is found along a boardwalk through the reeds. A hide is a trackers' blind, and Koga's trackers watch the wet ground (`SQ-G5-01`). Poison and stealth | Codex |
| `gym6_town` | Gym 6 town (Sabrina) | **Tilpey Cross** | The central hub with the region's only true square at a crossing, where observations "become one pattern" (ARC Settlement 7). The largest town on Lake Tilpey | Codex |
| `gym7_town` | Gym 7 town (Blaine) | **Cinderlee** | Houses on the lee of a mound, sheltered from the cone, round an ash-black square. Fire | Codex |
| `gym8_town` | Gym 8 town (Giovanni) | **Holdfast** | Giovanni holds it as the gate to Victory Road and has kept his gym shut while defending the south (ARC Settlement 9). Ground | Codex |
| `league` | Pokemon League | **The League** | The institution, named plainly; no town stands there. "Pokemon League" loses "League" on the two Victory Road transition signs, and "Pokémon" cannot go on a sign (see "Found in passing") | Codex |
| `sunset_west` | Sunset West | **Sunset West** | The story's name. The town now stands on the mainland across the strait, so the name says where its boats go | **Codex**: the sub-region "Sunset West" is the isle, not the town |
| `northlight` | Northlight | **Northlight** | The story's name for the research town | |
| `mining_town` | Mining Town (East Cones) | **Fossick** | To fossick is to dig and sift for ore, stones and fossils: the mine, smelter and fossil lab (`SQ-MINE-01`, `SQ-MINE-02`) | **Codex**: an uncommon word |
| `displaced_city` | The Displaced City | **The Displaced City** | The story's name. It is the outsiders' name; the residents' own is unwritten. No sign, so only its title shows it | **Codex**: handoff question 13 |
| `tea_town` | Tea town | **Steepside** | Tea steeps, and the tea rows step down the steep slope below the tea house (`SQ-TEA-01`) | Codex |
| `sea_town` | Pacifidlog | **Pacifidlog** | The owner reused it from Hoenn on purpose ("add the sea town from hoenn"). `data/sea_town.json` D3 kept it as a working name | **Owner** |
| `merian_hut` | Merian hut | **Merian Hut** | The story's name: the hut at the head of the Merian cirque, kept by Merian (`MIDGAME_EVENT_BANK.md`) | |
| `gorge_hamlet` | Gorge hamlet | **Bridgekeep** | The bridge-keepers' hamlet over the Tilpey outflow gorge (`SQ-GORGE-01`, `SQ-GORGE-02`, `SQ-G6-02`) | Codex |
| `tableland_stop` | Tableland stop | **Redbrow** | The lookout stands on the brow of the red tableland (`SQ-TABLE-01`) | |
| `rift_rim_stop` | Rift rim post | **Rimwatch** | The rangers' post on the Rift's rim, the traditional stop before Victory Road (`SQ-RIM-01`) | |
| `relic_island` | Relic Island | **Relic Island** | The story's name | |
| `the_scar` | The Scar | **The Scar** | The story's name. What stands there is an open question (`docs/story/handoffs/DISPLACED_CITY_AND_SCAR.md`) | |
| `viltri_light` | Viltri Light | **Viltri Light** | The story's name for the lighthouse | |
| `rift_dig_camp` | Rift dig camp | **West Spur Dig** | A dig, not a town, at the dead end of the west spur. The League archivist's "West Spur Record" (`SQ-LEAGUE-01`) | |
| `frostpeak_shrine` | Frostpeak shrine | **Frostpeak Shrine** | The story's name, capitalised. 16 characters, but no sign points to it | |
| `jungle_ruins` | Jungle Isle ruins | **Sunken Court** | Half-sunk walls along a causeway ending in a ruined court. It does not give away the ring symbols `SQ-JUNGLE-01` reveals | Codex |
| `great_oak_pallet` | The Great Oak | **The Great Oak** | Landmark tree; no title or sign | |
| `sentinel_spruce_tarn` | The Sentinel | **The Sentinel** | The owner's name for it (`SQ-G4-03`); no title or sign | |
| `patriarch_wedge` | The Patriarch | **The Patriarch** | Landmark tree; no title or sign | |
| `cherry_elder_shrew` | The Cherry Elder | **The Cherry Elder** | Landmark tree; no title or sign | |

## Judgement calls

- **Pallet Town, not Pallet.** The premise names it (ARC). The signs said "Pallet" from the fallback.
  `tests/test_location_titles.py` checked the fallback against the hometown, which now has a display name, so the
  check moved to the Route 1 mansion. That settlement still has no display name, and the assertion is unchanged
  in strength.
- **Pacifidlog is kept** although it is marked "working name". The owner asked for "the sea town from hoenn", and
  the instruction for this pass named it as a deliberate reuse. It is still for the owner to confirm.
- **Sunset West is kept** although the town left the Sunset West sub-region, because the story uses it.
  Alternatives, if Codex wants the town named for where it is: "Strait Quay", "Sunset Landing".
- **The Displaced City is kept** because the story uses it, though no resident would call their home that.
- **The League, not Pokemon League.** It fits both Victory Road transition signs, which had lost "League" under
  the working name, and it needs no accent (see below). Misty's town is **Viltri Quay** for the same reason:
  "Viltri Landing" was the first choice and lost "Landing" on the Routes 2 and 3 transition signs.
- **The landmark trees are named too,** with their existing names, so no `display_name` is null.
- **The Route 1 mansion and old mine are not renamed.** They are not in `data/towns.json`, and HANDOVER item 20
  leaves the choice between a towns record and a `data/signposts.json` name open.

## Found in passing

`tools/signposts.py` `sign_nbt` writes each sign line with `json.dumps` (ASCII escapes) inside a single-quoted
SNBT string. Minecraft 1.21.1's SNBT reader accepts only `\'` and `\\` as escapes in a quoted string, so a name
with any non-ASCII character (Pokémon, a curly apostrophe) would make that sign's `setblock` fail. This is
inferred from the tool's code and not tested in game. Every name above is ASCII, which avoids it. The tool
belongs to the test author.

## Not verified

No name has been seen on a sign or a title in game. The rebuilt `cobblers_signs` and `cobblers_titles` are
under `build/` in this worktree only; nothing is installed.
