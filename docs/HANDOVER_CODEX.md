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
9. **The roster audit tooling behind `docs/world-building/ROSTER_AUDIT.md`.** Not in `tools/`: it was written and run
   in a scratch session on 2026-09-17, and its counts (35 unreachable sub-regions, 23 wrong-country, 28 needs-water,
   42 milder mismatches, 45 weak-identity rosters) are in the report. It decides where a species belongs by resolving
   Cobblemon's biome tags across every jar the server loads and reading the species' dry-land entries only. Two
   mistakes were found and fixed while writing it — vanilla `#minecraft:` tags were not resolving at all, which
   flagged 380 entries instead of 117; and counting a species' fishing entries made Krabby look like it lived in every
   biome. Both suggest the remaining counts deserve a check. The two findings it produced are committed
   (`tools/subregion_boxes.py`, `tools/position_types.py`), the report's judgements are not.
10. **`tools/subregion_boxes.py` and `build_subregions` in `tools/compile_spawns.py`.** Check the polygon rasterising
   and rectangle merge (cell-centre membership, so neighbouring sub-regions cannot both claim a cell), the exclusion
   of route corridor cells, and whether a 32-block grid is the right trade between boundary slop and 14,366 entries.
   No pytest suite yet.
11. **`tools/position_types.py`.** Check the rule: fishing entries dropped, any dry-land entry keeps `grounded`,
   otherwise the most-used water position. 32 species have no upstream spawn data at all and keep `grounded` by
   default — Starly, Staravia, Bidoof and Piplup among them, the last two because Cobblemon 1.8 only spawns them from
   fishing. No pytest suite yet.
12. **`tests/test_ground_rule.py` and `tools/ground.py`.** Written by the session that converted the eight
   placement tools. Check the detector's reach: it catches `world_heights` imports and `X.extract()`/`X.capture()`
   calls, so a world read by another route (opening region files directly, a new reader module) would pass. Check
   that `VERIFY_ONLY` functions really only verify, and that `round` rather than `floor` holds away from the 40
   sampled windows.
13. **`tools/traders.py`, `tests/test_traders.py` and the `traders` check.** One session wrote the function, its
   tests and the verifier. Check the de-duplication cannot kill the only trader (it kills only where a `new` one
   stands), that the stray sweep (same type and exact name within 48 blocks) cannot catch an unrelated entity, and
   that 40 ticks is a safe load wait on a busier server than the idle disposable one it was measured on.
14. **`town_audit.plan_audit`, the unloaded-write rule and `ensure_loaded` in `tools/function_limits.py`,
   `rewrite_template(dry=True)` in `tools/place_town.py`, and `tests/test_silent_commands.py`.** One session wrote
   them. Check that `TEMPLATE_REACH` (32 blocks) covers every template the generators place (a giant tree or a gym
   may be larger), that the 95% standing threshold cannot pass a building missing its roof, and that the passable
   set used for "a block standing on the road" is not hiding anything.
15. **`tools/build_audit.py` and `tests/test_build_audit.py`; `split_fills` in `tools/function_limits.py`; the
   interim trader stock policy in `tools/traders.py`.** One session wrote them. Check that replaying a function
   (last write wins, `replace` honoured only against blocks the replay wrote) cannot pass a build that differs,
   that the cavern's mid-height open test cannot be fooled by a tree, and that the stock policy's category names
   match what the templates spell (`Pok\u00e9balls` has an accent).
16. **Batch 1 placement: `tools/rematerial.py`, the check-and-retry donor functions in `tools/place_donor.py`, the
   exact plaza paving in `tools/place_town.py`, the stray-paving and decay rules in `tools/town_audit.py`, and the
   spawn-policy entries of 2026-09-21.** One session wrote them and placed the towns. Check the house-choice rule in
   the placements' `chosen_because` against the renders, that the grass/dirt/path equivalences cannot hide a missing
   building, and the two scoped whitelist entries (the League's wool, red sand and lily pads; Sabrina's sunflower,
   cobweb and monitor), which the owner may veto.

## Handover, 2026-09-21 (Claude, the placement and re-export sessions)

For Codex to pick up. Claude has not edited any of the files named here.

17. **Sunset West moved.** It is no longer on the Sunset isle, which has no bay or inlet anywhere: it is now a harbour
    at a river mouth on the strait's mainland shore, centre **(2660, 6490)**, sub-region `south_strand` of
    `southern_coast` (`data/towns.json`, whose `why_here` records the search). The story documents still place it at
    **(1716, 7298)** on the isle: `docs/story/ARC.md` line 671, `docs/story/SIDEQUESTS.md` lines 291-305 and 651-652
    (the rubbing to carry to it), `docs/story/SIDE_EVENTS.md` line 335. `docs/story/ENCOUNTERS.md` lines 49 and 147
    describe the `sunset_west` **sub-region**, which is still the isle and is unchanged; the town simply is not in it
    any more. The isle stays in view across the strait as the place the port's boats go.
18. **The jungle ruins' cache needs a reward.** `jungle_ruins` is built (six vanilla ruin pieces half sunk on the
    jungle island, `data/placements.json`), and its brief promises a cache. No container or reward exists: choose
    what it holds and where, as event data.
19. **Review debt: every tool and test written or changed this week by Claude in the same session as its tests or its
    use.** None has had an independent reviewer. In priority order, by what a mistake would cost:

    *First, the live re-export path.* These run against the live world when the owner starts the re-export.
    - `tools/reapply.py` (the driver: step order, checkpoints, stale-file handling, the restore pack's removal).
    - `tools/function_limits.py` (`ensure_loaded`, `releases_mid_run`, `split_fills`, the unloaded-write rule) and
      `tests/test_silent_commands.py`. A mistake here silently drops blocks.
    - `tools/place_town.py` (seating on levelled pads, `rewrite_template` with `dry` and `materials`, the verify's
      corner rule, chunk wait, batching and `finally`) with `tests/test_place_town.py`, `tests/test_verify_floor.py`,
      `tests/test_house_materials.py`.
    - `tools/town_plan.py` (`clear_above`: 3 blocks of headroom and trees cleared over every street; `level_lots`,
      `avoid_water`, plan footprints, refusal reasons).
    - `tools/place_donor.py` (check-and-retry, `jigsaw_commands`, loot clearing) with `tests/test_donor_jigsaws.py`.
    - `tools/cavern_plan.py` (the seal now turns gravel and sand to stone; `town_mask` keeps trees off the town).
    - `tools/ground.py` (`for_settlement`: cavern floor, islet) with `tests/test_ground_rule.py` and
      `tests/test_ground_overrides.py`.
    - `tools/maze_forest.py`, `tools/world_tree.py`, `tools/tree_grove.py`, `tools/elder_trees.py`, `tools/islet.py`.
    - `tools/signposts.py` with `tests/test_signposts.py`; `tools/route1_mansion.py`; `tools/traders.py` with
      `tests/test_traders.py`; `tools/reexport.py`.

    *Second, the audits the live run is judged by.* A blind spot here passes a bad build.
    - `tools/town_audit.py`: the stray-paving control ring and its "not checkable" case, the earthwork exemption for
      road cells, donors' grade layer, exact template-written positions.
    - `tools/build_audit.py` (`built_over`, which leaves out what a later town rebuilds) with
      `tests/test_build_audit.py`.
    - `tools/signposts.py verify` and the floor verify in `tools/place_town.py` (above).

    *Third, spawn data* (not installed in the live world yet): `tools/compile_spawns.py` (spawn-free zones, whole-cell
    exclusion), `tools/suppress_inherited_spawns.py`, `tools/subregion_boxes.py`, `tools/spawn_blocks.py`,
    `tools/habitat_blocks.py`, `tools/position_types.py`, `tools/size_outliers.py`, with
    `tests/test_compile_spawns.py`, `tests/test_spawn_free_zones.py`, `tests/test_spawn_blocks_validator.py`,
    `tests/test_habitat_blocks.py`. Check that the eight gym zones cover each gym as placed.

    *Fourth, validation and measurement:* `tools/validate_data.py` (town, earthwork, trader, visibility checks),
    `tools/measure_towns.py`, `tools/visibility_claims.py`, `tools/nosepass_sightline.py`, `tools/town_templates.py`,
    `tools/rematerial.py`, `tools/runtime_guard.py`, `tools/restore_ground.py` (disposable worlds only), with
    `tests/test_town_measures.py`, `tests/test_visibility_claims.py`, `tests/test_runtime_guard.py`,
    `tests/test_template_provenance.py`.

    *Last:* `tools/compile_dialogue.py` (with its test), `tools/kit.py`, `tools/close_route_gaps.py`,
    `tools/build_routes.py`, `tools/press_pads.py`, `tools/rescale.py`, `tools/waterways.py`,
    `tools/tree_town_sites.py`, `tools/place_vendors.py`.

    **Not in the repository:** most placement records in `data/placements.json` (the batch 1-3 houses, donors and
    earthworks, Sunset West, the Displaced City's terraces) were written by session scratch scripts. The records are
    the source of truth and carry their reasons (`chosen_because`), but the scripts that chose them are not committed,
    so the choice rule can only be reviewed from the records.

    *Added 2026-09-21 (lighting and titles session), live re-export path:* `tools/light_plan.py` (the voxel light
    model, its scope rules, `connected_air`, the world `check`) with `tests/test_light_plan.py`; the after-donor split
    in `tools/place_town.py` and step R16 in `tools/reapply.py`; `tools/cavern_farms.py`; `tools/location_titles.py`
    and `signposts.place_names` with `tests/test_location_titles.py`.
20. **Every settlement needs a display name.** The route signposts and the location titles (`tools/location_titles.py`)
    both read `signposts.place_names()`: a settlement's `display_name` in `data/towns.json` once set, until then its
    working name in `data/signposts.json` `names` ("Brock's town", "Tea town", "the old manor"). All 29
    `data/towns.json` entries have `display_name: null`: the 25 settlements, and the 4 landmark trees, which get no title.
    The Route 1 mansion (`route1_mansion`), a settlement in `data/placements.json` but not in `data/towns.json`,
    needs one too. Set `display_name` in `data/towns.json` (and add `route1_mansion` there, or give it a name in
    `data/signposts.json`); then `python tools/signposts.py function` and `python tools/location_titles.py` pick it
    up, and a re-export places the new signs. Names over 15 characters wrap across sign lines.

21. **Re-review the fail-closed fixes before the live run.** Your review of the re-export path found four fail-open
    defects; the owner has held the live run until they are fixed, rehearsed and re-reviewed. Your written report was
    not in the repository or your worktree, so the fixtures were rebuilt from the owner's summary of it; check they
    are the cases you broke. Each commit's tests fail against the tools before it (shown in each commit message).
    - The lock: `tools/runtime_guard.py` `require_lock` (the lock file's `owner:` must equal `COBBLERS_LOCK_OWNER`),
      `tools/reapply.py` `main` and `install`; `tests/test_reapply_lock.py`, `tests/test_runtime_guard.py`.
    - Empty output: `tools/build_audit.py` (forest from `derived/sites/route1_forest.json`, world tree `top_y`, islet,
      cavern box and shell); `tests/test_audits_fail_closed.py`.
    - Not checkable: `tools/town_audit.py` `stray_paving_writes` (the heuristic is gone; our functions' paving writes
      against the plan's cells), `expected_building_ids`, `main`; `tools/reapply.py` `audit`; `tools/place_town.py`
      `lay` (planned streets on the plan's cells, which the new check caught overrunning in 17 of 24 places);
      `tests/test_town_audit_fail_closed.py`.
    - The ground rule: `tools/ground_rule.py` (call graph over every tool, `WORLD_READS` declared in each of the 17
      tools that read a world, a `validate.py` check); `tests/test_ground_rule.py`.
    - The sweep: `tools/light_plan.py check` (expected from the model, `BUILT_SHARE`, `dark_by_design`, shared
      `passable`), `signposts.py verify`, `traders.py verify`, `habitat_blocks.py verify`, `place_town.py verify`
      (`unverified`); `tests/test_verifies_fail_closed.py`.
    - What run 3 then found and fixed: R15 after R9; `town_audit.expected_buildings` earthworks by final state; the
      light model's foundations. EXP-026 run 3 has the numbers.

## What Codex can resume

- Everything in `docs/story/` and the world-building documents above, now.
- `data/spawns.json` rosters, `route_species_selection` and `spawn_suppression.json` (datapack-content-dev), now.
- The rest of `data/` once PR #17 merges.
