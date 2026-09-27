# STATE sweep, 2026-09-27

Every factual line of `docs/STATE.md` checked against the repository at `476c4e5` (branch `water/surface-exhaustion`,
the top of the 2026-09-26/27 stack), on branch `docs/state-sweep`. Repository only: `data/`, `tools/`, `docs/`,
`experiments/`, `tests/` and `git log`. No server, RCON or world was touched.

How counts were taken: Python over `data/*.json`; `tools/compile_spawns.py --out <scratch>` (a fresh compile, not
written to `build/`); `tools/compile_dialogue.py --all --out <scratch>`; `tools/paint_maps.py --out build/paint` then
`tools/visibility_claims.py --out <scratch>` (no `--write`); `docs/story/generate_trainers.py --check-early` and
`--check`; `tools/validate.py`; `tools/validate_data.py`.

Not in this base, so STATE does not describe them: PR #61 (`fix/underwater-canseesky`, `ad48221`, "Underwater
spawns no longer need to see the sky") and PR #62 (tests). When #61 merges, the lake line's "deep spawns may need
sky visibility, which the compiler forces" needs revisiting.

## Lines changed

| # | Section, line | Before | After | Evidence |
|---|---|---|---|---|
| 1 | World facts, habitat `data merge` | Two bullets run together on one line ("...offline player file.- **Cobblemon's spawn command...") | Split into two bullets | Formatting fault in the file |
| 2 | Built, Towns | 24 of 29 planned places laid out | 25 of 30 | `data/towns.json` has 30 entries (`sea_town` added); `data/placements.json` has plans for 24 of them plus Pacifidlog, built on staging (`2f1f79b`: "Built on staging, verify 10,332 of 10,332") |
| 3 | Built, Towns | Surge's town and the Scar "built only on the staging export `cobblers-dryrun3`" and, later in the same line, Surge's town "also built on the disposable world" | Surge's town, the Scar and Pacifidlog stand on staging (now `cobblers-dryrun11`); of the three the disposable world carries only Surge's town, on restored ground | Contradiction inside the line; EXP-026 run 5 re-applied all places on `cobblers-dryrun11` |
| 4 | Built, Towns | Every placed Mart (13: ...) | 14, with Pacifidlog | `data/traders.json`: 14 records with stock `mart`, one at `sea_town` |
| 5 | Built, Towns | `traders.py verify --rcon` finds all 24 traders | same, noted as a run before Pacifidlog, whose clerk was verified on its own | 25 trader records now; `2f1f79b` "clerk verified" |
| 6 | Built, Towns | The 5 landmark trees need no plan | The 4 landmark-tree outposts in `data/towns.json` need no plan | 30 entries - 25 laid out - Frostpeak = 4 (`great_oak_pallet`, `sentinel_spruce_tarn`, `patriarch_wedge`, `cherry_elder_shrew`); the fifth painted giant, the Weeping Elder, is not a town record |
| 7 | Built, Gyms | all 8 on the staging export `cobblers-dryrun3` | all 8 on staging | Staging is `cobblers-dryrun11` (EXP-026 run 5, EXP-042) |
| 8 | Built, Routes | event chains on staging (`cobblers-dryrun9`); 1,408 spawn boxes in `data/routes.json` | on `cobblers-dryrun11`, re-applied by EXP-026 run 5; 1,359 boxes | Sum of `spawn_scope.box_count` over the 9 routes = 1,359 (changed by `4cce6ff`, the maze-forest sub-region); run 5: 2,237 of 2,237 route-event blocks |
| 9 | Built, Regions | 62 sub-regions; 26 titled settlements | 63; 28 | `data/regions.json` `subregions` = 63 (`route1_maze_forest`); `tools/location_titles.py` `settlements()` on current data returns 28 (Pacifidlog and the old mine added) |
| 10 | Built, Terrain landmarks | 27 tracked: 22 built, 4 partial, 1 planned | 28: 22, 4, 2 planned (`river_of_shrews`, `surge_signal_array`) | `data/landmarks.json` |
| 11 | Built, Death and wipe | EXP-042 runs 1-2 only: second hit "not yet rerun"; not run: Center checkpoint, Dive | Three sessions: the charge ($59 of $586 as well), the Center checkpoint works, the second hit kills, Dive holds air 2+ min, Dive counts against the Surf bonus, swim 5 blocks/s, Dive boost about 10 blocks/s ("its good"); not run: waystone checkpoint, mid-dive swap, wild loss, recovery, delivery | `1b9bbc1`; `experiments/EXP-042-blackout-and-water-ladder/README.md` "Session 3" |
| 12 | Built, new bullet | (EXP-043 absent) | Surface exhaustion: zones, rates, loads clean on staging, not run in game, no written brief | `476c4e5`; `experiments/EXP-043-surface-exhaustion/README.md`; `tools/open_water.py`; `data/blackout.json` `surface` |
| 13 | Built, Encounter data | 62 of 62; 9 route files (1,408 boxes, 7,066 entries), 62 sub-region files (2,033 boxes, 14,488 entries over 43.0 million blocks), 1 waterway, 9 Habitat pool files; "Until 2026-09-17 ..." history | 63 of 63; 9 route files (1,359 boxes, 7,164), 63 sub-region files (2,027 boxes, 17,416), 1 waterway, 3 marine, 87 Habitat pool files, 25,646 details in 76 spawn files; history removed | Fresh `compile_spawns.py` run (2026-09-27): "1359 route boxes, 7164 route entries, 63 sub-regions, 2027 sub-region boxes, 17416 sub-region entries", 87 files under `habitat_pools/`. The 43.0 million blocks figure was dropped: it belonged to the old box set and the tool does not print it |
| 14 | Built, Encounter data | "What spawns there has not been observed yet (EXP-035)" | The owner's observations so far are the lake and sea findings; the route-by-route observation is not done | Contradicted by the same file's lake and western-sea items, both from the owner in game |
| 15 | Built, Size variance | "**`cobblers_sizes` is not installed on staging** (not in `SERVER_PACKS`)" | Built at `prepare`, installed world-local (`WORLD_LOCAL`), on staging since the 2026-09-26 install; no outlier seen there | `tools/reapply.py` lines 75 and 110-111; `5989f1c`, `1d8c016` (install_check 0 problems on `cobblers-dryrun11`); contradicted STATE's own "Packs too" item |
| 16 | Built, Quest data | the Digger stands on staging (`cobblers-dryrun9`) | `cobblers-dryrun11` | EXP-026 run 5 re-ran R9F |
| 17 | Built, Tooling | 104 Python tools, 90 pytest modules, 26 experiment directories | 113, 97, 33 | `tools/*.py`, `tests/**/test_*.py`, `experiments/EXP-*` |
| 18 | Built, Tooling | (the fail-closed `prepare` lived in a history item under What is open) | One sentence of state: `prepare` fails closed; EXCLUDED names the self-driving and event-driven packs; a rehearsal proves only the steps that exist | `tools/reapply.py` `EXCLUDED` and the check at l.284-288 |
| 19 | Built, Stale inventory | sightline docs stale if the canopy is not `ce7da822…` | the current data paints `f1ac39d4…`, so they are stale | `tools/paint_maps.py --out build/paint`, sha256 `f1ac39d41ae2…` |
| 20 | Built, Re-export readiness | run-4 fixes "checked offline ..., not yet on a rebuilt world" | "All are fixed." | The same line, and EXP-026 run 5: "Run 4's fixes all held on a rebuilt world" |
| 21 | Decided, Legendary side content | bespoke: Regis/Regigigas/Groudon/Lugia and Celebi | adds the lake trio (below) | The owner's 2026-09-26 lake-trio decision in the same section and `docs/mechanics/WATER_MAP.md` section 3 (grottos with air chambers) |
| 22 | Decided, Vanilla air | "the in-game check is EXP-042" | seen working on staging (session 3: Water Breathing stripped; Respiration inert after a restart) | EXP-042 session 3 |
| 23 | Decided, new bullet | (the rim post's move recorded only as a closed option list under What is open) | Rift rim post moved to (3814, 3791), the owner, 2026-09-23; 50 of 272 over terrain | `051c348`; `data/towns.json` `rift_rim_stop.centre`; `data/visibility.json` `rift_rim_stop_from_its_leg_terrain` |
| 24 | Decided, Habitat Blocks | sapling nests "described under 'What is built'"; blocks placed by `setblock` + `data merge` | "What is open"; natural blocks by setblock + merge, activated by two setblocks | Where the sapling items actually are; `tools/habitat_blocks.py` l.10-20, and STATE's own World facts rule |
| 25 | Open, Water map | "Its ten open decisions are listed at the end" | Ten listed; four decided or settled (lake trio placement, Lugia, vanilla air, Shrew floor); six wait on the owner, plus shared-or-per-player for the trio | `WATER_MAP.md` section 6 |
| 26 | Open, Death and wipe | owner's run of drowning, Center checkpoint, Surf, Dive, swap, wild loss, recovery; "vanilla air items (OCEAN.md and the spec disagree)" | the rest of EXP-042 and EXP-043's first run; boats past the shallows added; OCEAN.md's tiers still rely on the removed items | EXP-042 session 3; EXP-043 "Open"; `docs/world-building/OCEAN.md` l.240-242 |
| 27 | Open, Blackout | "whiting out does not send a player to a Poké Center ... Not researched." | removed (closed) | `cobblers_blackout` returns to the last Center; seen in game, EXP-042 session 3 |
| 28 | Open, Visibility vs canopy | canopy `e84d8665…`; trial moved 8 claims by 1-8 points | canopy `f1ac39d4…`; trial (2026-09-27, not written) moves 8 claims by 1-6; the gorge hamlet 0 of 129 still | `visibility_claims.py --out <scratch>`; `validate_data.py --only visibility`: 1 error |
| 29 | Open, lakes | "... 24,780 details across 73 files" | sentence ends at the sub-region count | Superseded by the western-sea item (25,646 across 76), confirmed by the fresh compile |
| 30 | Open, client models | "`cobblers_kits` is installed by hand and has no install step; a fresh `kit.py pack` lacks `brock.nbt`, which the installed copy has" | `cobblers_kits` built at `prepare`, installed at `install`; the local-only `brock.nbt` is placed by nothing (gym 1 is `cobbleverse:brock`) | `tools/reapply.py` l.254; `5989f1c`; `data/placements.json` `gym1_brock_gym` |
| 31 | Open, sapling birds | "210 activated Habitat Blocks in `data/habitat_blocks.json`" | "210 of the 252 activated" | `data/habitat_blocks.json`: 252 activated, 81 natural |
| 32 | Open, Trainer regeneration | `generate_trainers.py --check-early` (12 trainers) | `docs/story/generate_trainers.py`, 13 trainers | Run: "ok: 13 route 1-3 trainers"; `--check` still fails on Victory Road's pin as the line says |
| 33 | Open, Live re-export | "Run 4's fixes still need a fifth fresh staging rehearsal" | The fifth ran (EXP-026 run 5); no readiness verdict is recorded after it; the live run waits on one | EXP-026 "Run 5"; its "Decision" section ends at run 4 |
| 34 | Open, display names | all 29 entries | all 30 | `data/towns.json`: 30 entries, every `display_name` null |
| 35 | Open, Rift overhaul | a full description of the 2026-09-23 Victory Road gauntlet (666 blocks, five caverns, 10 stands ...) and the precinct's move history | Victory Road is the cave network (its own item); the gauntlet spine is retired; fightorflight's thresholds kept as the rule; "the precinct moved with it" | `data/victory_road.json` status "RETIRED 2026-09-23"; STATE's own Victory Road item |
| 36 | Open, "The sculpt left cells.json and visibility.json behind" (20 lines, the rim post's options) | the only validator error is the rim post; options to choose | removed; the owner's choice is now a Decided bullet (row 23) | `051c348` moved the post; `data/visibility.json` now measures 50 of 272; `validate_data.py` cell-terrain: "no drift" |
| 37 | Open, Rift underground | "which is what Victory Road and every unbuilt Rift cavity are, and the bounded-suppression override pack is not installed on the staging server"; "corrected 2026-09-23"; "An earlier report in this session ..." | outside Victory Road's tiles; the seams between tiles; the suppression on staging leaves them by policy; history removed | Suppression installed on staging (Encounter data line; install sweep); Victory Road tiled with 80 Habitat Blocks |
| 38 | Open, Starters | "EXP-029 counts the tabs on a fresh join" | EXP-029 is a backlog candidate with no experiment folder | `docs/research/EXPERIMENT_BACKLOG.md`; no `experiments/EXP-029-*` |
| 39 | Open, relativeLevelCap | "the runtime disagrees with them"; "which replaces the old hand copy"; "`rctmod-server.toml` sets 5" | "which the runtime now matches"; history dropped; "Cobbleverse's `rctmod-server.toml` sets 5" | `modpack/config/rctmod-server.toml` l.153 `relativeLevelCap = 0`, base pack l.150 `= 5`; the line's own "the server runs 0" |
| 40 | Open, "The re-export was reported as rehearsed end to end, twice..." | a history paragraph | removed; its state is row 18 | `tools/reapply.py` |
| 41 | Open, evolution stones | 168 rows (84 + 84), 60 species; "0 trainers placed" | 182 rows (91 entries, 77 subregions, 11 habitats, 3 marine), 63 species in `entries`; the family breakdown marked as counted at 60 species; the campaign's only stones are one each of Water, Fire, Leaf, Sun, Shiny in Victory Road's finds | Python count over `data/spawns.json`; `data/rewards.json` l.44-170; 18 trainers stand on staging, so "0 trainers placed" was false |
| 42 | Open, Rewards | "Victory Road's five finds, and nowhere else"; "four caches and one NPC grant"; "Everywhere else there is still no reward content; the only loot code outside this deletes loot" | eleven records: VR's five and six caches off Routes 1 and 3; the leaders' first-win items are the other reward content | `data/rewards.json` (11 records); `tools/progression_pack.py` `first_win` |
| 43 | Blocked, live re-export list | item 2 "relativeLevelCap ... Cleared."; "Cleared on 2026-09-23: ..." paragraph; "listed 2026-09-23" | cleared item and paragraph removed; new item 3: no readiness verdict after run 5 | History; EXP-026 Decision |
| 44 | Blocked, Pads | "the live re-export, which is ready to run" | "the live re-export" | Contradicted "Re-export readiness: not ready" and EXP-026 |
| 45 | File ownership | "Future `data/events.json`, `data/trainers.json`, `data/gyms.json`" | `data/trainers.json` has its own row (same owner, generated by `docs/story/generate_trainers.py`); the Future row keeps events and gyms | `data/trainers.json` exists, `generator: docs/story/generate_trainers.py` |

`git diff --numstat`: 48 lines added, 70 removed in `docs/STATE.md` (long lines; 45 corrections above).

## Lines that could not be verified from the repository

They depend on a world, a server, a client or an owner statement not filed in the repo. Left as they are.

- World facts: the live `level.dat` spawn, 484 region files and border; the runtime versions and "Done (2.659s)";
  the habitat `data merge` finding and Neruina's player key; rctmod's rematch behaviour (bytecode read and owner
  reports); the spawn command inside a function.
- What is built:
  - the disposable world's contents (towns, gyms, 484 pregenerated regions);
  - every staging audit figure (light at 0, floor gaps, 159,470 template blocks, cavern shell 60,992 columns,
    254 lantern posts, 136 plants);
  - the 77,750 foliage objects: `data/world.json` records them for the 2026-09-15 paint; whether the current
    WorldPainter project (with the marsh and jungle overlays exported on staging) still holds that number is not
    in the repo;
  - scenes "41 props, 8 NPCs and 18 trainers are placed (R17)": a staging count; `data/scenes.json` lists 40 props
    and 11 actors by a plain count, which need not match what R17 places;
  - the thirsty stranger's 44 nodes;
  - "load last of 87 packs"; suppression at 926 boxes and 3,841 MB (needs the server's mod set);
    `data/spawn_suppression.json` itself still says `critical_route_boxes.box_count` 1,408;
  - "every function the re-application installs passes";
  - the retired snapshots' boots.
- What is decided: the MobsBeGone summon test; fightorflight's values (read from the base pack, not re-read).
- What is open:
  - the TM and money figures from Brock on staging; the level-cap trap; pacing;
  - "the owner's client runs rctapi 0.16.1" (client, not in the repo);
  - whether the pendant duration and `starters.json` have taken effect (staging restarted in EXP-042 session 3,
    but the order against the config copy is not recorded);
  - "Not seen in game, not installed" for the western sea: the install that reported 0 problems (`1d8c016`)
    descends from the western-sea commit (`c98adc4`), so staging probably carries the marine files, but no record
    says so;
  - "route corridors over four lakes still have no fish";
  - the sapling-bird counts measured on staging; the Pacifidlog verify count;
  - "the Rift overhaul ... waiting on the owner's flight": the owner flew Victory Road's spine, but no record says
    whether the Rift as a whole was flown;
  - the street-light percentages; the snapshot sizes;
  - the starter spread (29 to 14) and the battle-sim results: not re-run.
- What is blocked: EXP-000's boot evidence is in the repo, the rest is runtime.

## Found in passing, outside STATE (not changed)

- `experiments/README.md` index: EXP-000 still reads "procedure written, not yet run" although its README records
  boots and a client connection; EXP-038 to EXP-043 are missing from the table; EXP-026's row stops at run 2.
- `experiments/EXP-042-.../README.md`: its "Still to run" list and its Limits ("Vanilla air items ... still work")
  predate session 3.
- EXP-026's "Decision" section has no entry after run 5.
- `data/placements.json` `sea_town.status` says "not built on staging"; the commit that added it says built and
  verified.
- `data/rewards.json` `status` says "four finds off Routes 1 and 3"; it holds six.
- `docs/world-building/OCEAN.md` depth tiers still rely on Respiration, a turtle shell, Water Breathing and conduits.
- EXP-043 cites `docs/mechanics/WATER_PROPOSAL.md`, which is not in this base (it may be on `design/water-proposal`).
- `tools/location_titles.py` needs `derived/cavern/plan.json` (the Displaced City's vertical box), so it fails in a
  checkout where `derived/` has not been regenerated.
- The file-ownership table has no row for `data/blackout.json`, `water_mounts.json`, `traders.json`,
  `rewards.json`, `scenes.json`, `sea_town.json`, `themed_saplings.json`, `elder_trees.json` and the Rift and
  Victory Road files. No owner was invented for them.
- In an isolated worktree, `tools/validate.py` reports 2 errors and `tools/validate_data.py` 263, all missing
  gitignored local-only templates (`kits/structures/campaign/f4/services/*.nbt`, `kits/structures/incoming/...`).
  `python tools/validate.py --only template_provenance` is clean. With the canopy regenerated, the only data error
  is the stale canopy (1).
