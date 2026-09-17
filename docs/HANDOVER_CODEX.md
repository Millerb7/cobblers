# Handover to Codex: the regenerated canonical data (2026-09-16, final)

Codex stood down from `data/` while the canonical data was regenerated. This is the final state on branch
`data/post-rescale-regeneration` (PR #17), after Route 1 was pinned through the built forest and Surge's town moved to
a pressed shelf. It supersedes the intermediate version of this file. Nothing in `docs/story/` was edited.

Numbers come from `data/routes.json`, `data/towns.json` and `data/landmarks.json`. Where prose allows, quote a route id
rather than copying a distance.

## What changed underneath the story

### Geometry

- **Canonical heightmap** `5b963567`: the rescaled terrain with three pads pressed (the Scar at y280, the Frostpeak
  shrine at y310, Surge's shelf at y174). Not in the live world until the next re-export.
- **Surge's town (`gym3_town`)** is on a shelf cut into the Tri Peaks - Mt Vessu south flank: **centre (1688, 1410),
  y174**, sub-region `the_tri_peaks` (region `tri_peaks`). Above the treeline, open to the prevailing wind, Mt Vessu's
  summit in view from town. It is no longer at (1847, 1262) on Mt Vessu's shoulder, and it never settled at the
  intermediate foothill site (2347, 1956). The Scar (624 blocks away) is not visible from town.
- **Surge's signal array** is a new landmark, `surge_signal_array`: (1928, 1248), y284, on a Mt Vessu shoulder 290
  blocks above the town. Status `planned`. The maintenance climb from town is about 510 blocks with 127 of ascent and
  steep steps, so it needs authored stairs or terracing.
- **Route 1** is pinned through the built maze forest's main path and passes River of Shrews vale.
- **Leg 4** takes a waypoint west of the Merian cirque at (2640, 1180).
- **0 polygon holes** on every route; every compiled pool reaches every species in its authored list.

### Leg lengths and climbs

| Leg | Route id | Was (2026-09-15) | Now | Climb | Steepest | Steps >35° |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 Pallet→Brock | `route_01_pallet_to_brock` | 1,792 | **1,978** | 37 | 9.6° | 0 |
| 2 Brock→Misty | `route_02_brock_to_misty` | 946 | 944 | 3 | 15.7° | 0 |
| 3 Misty→Surge | `route_03_misty_to_surge` | 1,989 | **2,120** | **81** | 23.5° | 0 |
| 4 Surge→Erika | `route_04_surge_to_erika` | 2,907 | **3,453** | 55 | 24.2° | 0 |
| 5 Erika→Koga | `route_05_erika_to_koga` | 1,038 | 1,051 | 13 | 7.1° | 0 |
| 6 Koga→Sabrina | `route_06_koga_to_sabrina` | 1,944 | 1,944 | 22 | 12.9° | 0 |
| 7 Sabrina→Blaine | `route_07_sabrina_to_blaine` | 2,053 | 2,061 | 49 | 27.8° | 0 |
| 8 Blaine→Giovanni | `route_08_blaine_to_giovanni` | 3,049 | 3,050 | 68 | 13.3° | 0 |
| Victory Road | `victory_road` | 5,157 | **5,248** | 62 | 17.3° | 0 |

- **Leg 3 is a real ascent again:** Lake Viltri Hollow → Foothill Woods → Mt Clay → Mt Vessu → the Tri Peaks shelf. The
  mountain segment and its species are back.
- **Leg 4:** the Tri Peaks → Mt Vessu → Mt Clay → Merian Cirque → the Crags → Upper Trough → Peak Pond Hollow; no water
  crossing.

### Beats keyed to Surge

- **The climb** (`EARLY_GAME_EVENT_BANK` "Misty-to-Surge climb", 6 events): holds. About 81 blocks of climb, the last
  stretch above the treeline.
- **`EVT-ROUTE3-NOSEPASS-SIGNS`:** the Nosepass turns toward **Surge's signal array**, not the summit. The signs belong
  at the one stretch of leg 3 where the array's 12-block mast is visible over the forest canopy: **1,464-1,505 blocks
  along the leg (69-71%), (2203, 1609) to (2163, 1606), y124**, below Mt Clay. Suggested sign site **(2203, 1609)**,
  since moved to **(2186, 1606)** to keep a built elder outside the clearing (`data/landmarks.json` sign_site).
  The keeper's shelter and signs need a 40-block clearing there, and the line north-west to the array must stay free of
  the tallest Foothill Woods trees: the margin over the canopy is 0.4-4 blocks. Recorded in
  `landmarks.json` `surge_signal_array.site.nosepass_view.canopy_clear`. Its reward ("a marked shelter location on the
  remaining route to Surge") still works: about 615 blocks of route remain.
- **The summit reveal:** Mt Vessu's summit comes into view only on the last 72 blocks of leg 3, as the path crests onto
  the shelf. That is an arrival moment. **Do not attach a quest beat to it.**
- **`EVT-G3-KITE-LINE` (wind puzzle):** holds. The shelf is above the treeline and faces the prevailing wind.
- **Mountain species segment** (`ENCOUNTER_GAPS.md` line 30): holds. Leg 3 crosses `mt_clay`, `mt_vessu` and
  `the_tri_peaks`, and Route 3's pool compiles all 20 of its authored species, including the Mt Vessu ones.
- **Surge's side quest** (`SIDEQUESTS.md` 105-116): the Scar is not visible from town (accepted). The map marker to it
  still works as a trip.

### Settlement distances that changed

Off-path distances are now measured by the validator on `data/routes.json` rather than read from records, and every
record was refreshed: the Scar 437, Frostpeak shrine 1,440, sentinel spruce tarn 390, cherry elder 531, weeping elder
861, the Patriarch 247 (landmark trees may be 200 or more off the path), Displaced City 287, Merian hut 120.
Rest stops: Merian hut 120 off leg 4 at fraction 0.421; gorge hamlet 283 off leg 7 at 0.598; tableland stop 238 off
leg 8 at 0.525; rift rim post 386 off Victory Road at 0.628.

### Spawn pools

Compiled pools are generated, not committed: `tools/compile_spawns.py` writes `build/datapacks/cobblers_spawns/`
(1,408 boxes, 7,066 route entries). `data/cobblemon/` no longer exists. Per-route species lists are authored in
`data/spawns.json` `route_species_selection`, and the compiler reproduces them exactly (no route has an unreached
species).

## Documents to revise (Codex owns these)

1. **`docs/story/ARC.md`**
   - Distance references, with their new values: line 32 and 127 and 578 (Victory Road 5,157 → 5,248), 214 (Route 1
     1,792 → 1,978), 256 (946 → 944), 280 and 299 (1,989 → 2,120), 343 (2,907 → 3,453, and leg 4's new sub-region
     order), 396 (1,038 → 1,051), 439 (1,944, unchanged), 485 (2,053 → 2,061), 532 (3,049 → 3,050).
   - Line 43 and 298: Surge's centre (1847, 190, 1262) → **(1688, 174, 1410)**, in `the_tri_peaks` / `tri_peaks`.
     Line 301's distances to `tri_peaks` and `mt_vessu` no longer apply.
   - Line 294's title "Surge on Mt Vessu": the town is on the Tri Peaks flank facing Mt Vessu; the signal array (line
     147's "storm-facing equipment on Mt Vessu") is on Mt Vessu, 290 blocks above the town.
   - Line 644: the Scar's y is 280, not 200.
2. **`docs/story/SIDE_EVENTS.md`** line 123 and **`docs/story/SIDEQUESTS.md`** line 110: Surge's town coordinates.
3. **`docs/story/events/EARLY_GAME_ENCOUNTERS.md`** 330-360 and 442: place the Nosepass signs at (2203, 1609) and aim
   them at `surge_signal_array`. Do not stage anything at the shelf lip.
4. **`docs/story/events/MIDGAME_EVENT_BANK.md`** line 51 (leg 4: 3,453 and its order) and line 242 (leg 5: 1,051).
   Line 425 (leg 6, 1,944) is still correct.
5. **`docs/story/AVAILABILITY.md`**: chapter 1's Route 1 / `river_of_shrews_vale` rows (Surskit, Buizel, Bidoof, Pawmi,
   Deerling) stand. The route_03 rows for `mt_clay` and `mt_vessu` stand too: Route 3 reaches them again. Check level
   bands if the per-sub-region order along Route 3 matters to them (it now ends in `the_tri_peaks`).
6. **`docs/story/ENCOUNTERS.md`** lines 3 and 32: pools are in `build/datapacks/cobblers_spawns/`, generated by
   `tools/compile_spawns.py`.
7. **`docs/story/ENCOUNTER_GAPS.md`** lines 59-66: the listed polygon holes are closed.
8. **`docs/world-building/TOWNS.md` 62-108 and `SETTLEMENTS.md` 45-161**: still on pre-sculpt numbers (1,780, 908, 1,643,
   2,640, 1,027, 1,946, 2,021, 3,055, 4,953); use the tables above.

## Independent review requested (Codex)

Claude wrote each of these together with its own tests in one session, so none has had an independent reviewer.
Spot-check the code and the tests against real data, and report disagreements rather than editing the checks:

1. **`tools/validate_data.py` town checks:** `measure_nearest_leg` and `_nearest_leg_problems` (called from
   `check_towns`), and `measure_town_ground` with `check_town_ground` (the `town-ground` check, including
   `built_ground` for `tools/islet.py`). Tests: `tests/test_town_measures.py`.
2. **`tools/measure_towns.py`**, which writes the same measurements back into `data/towns.json`. Check that `--write`
   changes only derived numbers, never positions, footprints or prose.
3. **`tools/nosepass_sightline.py`**, the Route 3 sign-site margins (terrain, the canopy_clear model, the planned
   paint canopy). It has no pytest suite; its only check so far is that it reproduced the exploratory run (82 points,
   no difference).
4. **`tools/visibility_claims.py` and the `visibility` check in `tools/validate_data.py`**, which measure every
   visibility claim in `data/visibility.json`. Check the observer and target semantics against what each stating record
   actually claims, the fragility rule, and the citation rule. Tests: `tests/test_visibility_claims.py`.
5. **`measure_nearest_settlement`** (in `check_towns` and `measure_towns.py`) and the foliage check's handling of a
   demoted tree (`landmark: false`).
6. **`tools/suppress_inherited_spawns.py`** (EXP-012): per-path precedence (mods, then global, then world packs), the
   singular-to-plural anticondition move, and `merge_boxes` snapping outward on a coarser grid without losing a box.
7. **`tools/habitat_blocks.py` and the `habitat-blocks` check** (EXP-021): the overlap rule, the region-file reader
   (blockstate index order and block-entity match), and the RCON parser. Tests: `tests/test_habitat_blocks.py`,
   written in the same session.
8. **`tools/compile_dialogue.py`** (EXP-022): entry-rule order, the cursor/`set_page` flow, the give success guard
   and the refusal of unsupported constructs. Tests: `tests/test_compile_dialogue.py`, written in the same session.

## What Codex can resume

- Everything in `docs/story/` and the world-building documents above, now.
- `data/spawns.json` rosters, `route_species_selection` and `spawn_suppression.json` (datapack-content-dev), now.
- The rest of `data/` once PR #17 merges.
