# What the repo builds that nothing installs (2026-09-26)

Asked after two things were found by accident: the compiled spawn tables were not on the running server, and five
committed config overlay files (among them `starters.json`) had never been copied to it. Configs are now covered by
`tools/server_config_record.py check` (0 disagreements, re-run for this sweep). This note is everything else.

## How it was checked

Read-only. Nothing was installed, run over RCON, or edited outside this file.

- **Datapacks.** Every pack under `build/datapacks/` and `modpack/datapacks/` in this worktree was hashed file by file
  (sha256) against:
  - the server's global folder `cobblers-server/datapacks/`, which Global Packs force-loads for every world the server
    runs (`config/global_packs.toml`: `required = ["datapacks/"]`, `optional = ["datapacks/extra/"]`);
  - the staging world's own folder `cobblers-dryrun11/datapacks/`.
- **Enabled packs.** Read from the staging `level.dat` `DataPacks` only: 89 enabled, 6 disabled. The seed was not read.
- **Coverage.** Each pack was checked against `tools/reapply.py` (`SERVER_PACKS`, `WORLD_LOCAL`, `SPAWN_PACKS`,
  `WORLD_PACKS`, `EXCLUDED`, `prepare()`, `install()`, `steps()`).
- **Regenerated to scratch to test staleness:** `spawn_tag_pack.py`, `size_outliers.py`.
- **Mods.** `python tools/pack_manifest.py verify <dir> --side server|client`, against the server's `mods/` and the
  client instance's `mods/`.
- **Resource packs.** The client's `resourcepacks/`, `options.txt` `resourcePacks` and `config/`, compared with
  `modpack/config/`.
- **Not read:** the live world `cobblers-10240` or anything in it, including its datapacks folder. Everything below
  about the live world is therefore **unknown** unless the repo records it.

**Corrected after the sweep: the server was running staging, not the live world.** The sweep read
`level-name=cobblers-10240` in `server.properties` as the running world. The process listening on 25565 was started by
the staging driver with `--universe C:\Users\wnd\Documents\github\cobblers-runtime-proof\dryrun11 --world
cobblers-dryrun11`, and those arguments override `level-name` (checked from the process command line, 2026-09-26).
The established connection was the owner's client on staging. `server.properties` names the live world because the
live server boots from the same folder without those arguments.

Verdicts: **installed**, **stale** (installed, but older than what the repo now builds), **never installed**, **not
enabled**, **no install step** (present, but only by hand; nothing in the repo puts it there), **unknown**.

## Findings

| Item | Kind | What the repo has | What runs | Verdict | Evidence |
|---|---|---|---|---|---|
| `cobblers_reapply` | datapack (global) | `prepare` assembles it from `build/town_prep`, `build/elders`, `build/themed_saplings`, `build/grove` and `build/islet` | Server copy is byte-identical to the build: 31 files, 01:44. **But that build predates its sources.** It has no `reapply/themed_saplings.mcfunction`, although step R5B runs `cobblers:reapply/themed_saplings` (`reapply.py:583`). Its `elders.mcfunction` has 591 lines; `build/elders/elders.mcfunction` has 645 (02:09, after `data/elder_trees.json` 02:08) | **stale** | A `run` from R5B stops there with an unknown function. R5 would lay the pre-02:09 elders. `prepare` has not run since 01:44. How the 14 themed saplings reached staging is not recorded. `prep_grove_city.mcfunction` (09-21) is a leftover with no settlement |
| `cobblers_kits` | datapack (global) | `tools/kit.py pack` writes 56 files from `kits/structures/prefabs` | Server has 57 files, newest 13:33, copied by hand. `prepare` does not build it and `install` does not copy it: `reapply.py` never mentions kits | installed; **no install step** | Every elder (R5, 24 templates), themed sapling (R5B, 21 templates) and the maze forest's sapling (R6) is placed from `cobblers:kits/...`. `build_audit.py` checks only cavern, forest, world_tree and islet (`CHECKS`, l.476), so a server without the pack places no elders or themed saplings, and no audit notices |
| `kits/gyms/kanto/brock.nbt` | structure | Gitignored local-only source; absent from this worktree (only `brock.json`) | Installed in the server's `cobblers_kits`. **No function places it:** gym 1 is `cobbleverse:brock` (`data/placements.json:4590`, `place_gym1_brock_gym_go.mcfunction`) | installed, **unused** | The concrete-fixed Brock (`STRUCTURE_INVENTORY.md:631`) is never in the world. `data/towns.json:2688` still names it as built on gym 1's lot |
| `cobblers_sizes` | datapack | Built 09-20: 9 files, identical to a fresh `size_outliers.py` run from `data/sizes.json` | Absent from the server, staging and `level.dat`. Not in `SERVER_PACKS`. It sits in `EXCLUDED` as "self-driving" (l.84), which exempts it from a step but not from install. `prepare` never runs `size_outliers.py` | **never installed; no install step** | The 1-in-200 notable-size individuals exist on no world since the disposable one. `data/sizes.json` status says so; STATE l.31 agrees |
| `cobblers_habitats` | datapack (global) | 333 activated Habitat Blocks from `data/habitat_blocks.json` (13:33) | Server copy (13:06) differs in `place.mcfunction`, but only in line order: the sorted files are identical, and the 333 positions equal the 333 records | installed | STATE l.82 still says "82 recorded" |
| Habitat pools without a block | spawn data | 8 of 87 `data/spawns.json` habitats compile to pools that no block uses: `displaced_city_cavern`, `glacial_tear_deep_valley`, `great_crater_bowls`, `marshy_marsh_basin`, `mining_town_fossil_levels`, `northgate_old_growth_grove`, `rift_depths`, `tree_town_canopy` | Compiled into `cobblers_spawns`. Nothing places a block for them | **no install step** | `placement_status: pending_or_authored_world_asset` on all 8; they are not in `habitat_blocks.json` |
| `cobblers_spawns` | datapack (staging world) | `compile_spawns.py` at `prepare` | Staging copy identical to the build (168 files, 13:06). `data/spawns.json` (14:38) and `tools/compile_spawns.py` carry uncommitted edits made after that compile | installed (staging); **stale** against the working tree | Live world: unknown (not readable); STATE l.30 says 0 |
| `cobblers_suppress` | datapack (staging world) | `suppress_inherited_spawns.py` at `install` | Staging identical (1,731 files, 13:07). The tool has uncommitted edits | installed (staging) | Live world: unknown; STATE says not installed |
| `cobblers_scenes`, `_trainers`, `_route_events`, `_celebi`, `_rift_storm` | datapacks (`WORLD_LOCAL`) | `prepare` and `install` | All five identical in the staging world, enabled as `file/...` | installed (staging) | Live world: unknown. By design, none is in the global folder |
| `cobblers_height`, `cobblers_worldtree` | datapacks (`WORLD_PACKS`) | `modpack/datapacks/cobblers_height`; `world_tree.py` | Identical in the staging world, enabled | installed (staging) | Live world: unknown |
| Global `SERVER_PACKS`: cavern, deep, dialogue, donor, league_tunnel, progression, rewards, rift, rift_biome, route1, signs, titles, towns, vendors, vr_caves | datapacks (global) | `prepare` / `install` | All byte-identical to the build and enabled on staging. The global folder is loaded by the live world too | installed | `cobblers_progression` (load and tick tags, 10 advancements, 22 loot tables), `cobblers_titles` (98 advancements) and `cobblers_rewards` (10 advancements) run on their own in any world the server loads |
| `cobblers_progression` in STATE | record | STATE l.90: "The pack is not installed on the server between staging runs" | It is in the global folder, identical to the build | STATE is wrong | See above |
| `cobblers_vr_backfill`, `cobblers_vr_clear` | datapacks (global) | `EXCLUDED` calls both "staging only" | Both installed globally, byte-identical to the build, enabled on staging, and loaded by the live world as well. Nothing runs them | installed (wrong scope) | The same hazard for which `install()` deletes `cobblers_restore` (l.307-311). Inert unless called |
| `cobblers_restore`, `_rift_fracture`, `_victory_road`, `_vr_regions` | datapacks | Built; disposable-only or retired | Absent everywhere | never installed (intended) | `EXCLUDED` reasons |
| `cobblers_spawn_tags` | datapack (global) | `tools/spawn_tag_pack.py` from `data/regions.json`; no copy in `build/` | Server copy (09-14) is byte-identical to a fresh regeneration, 3 of 3 files, and enabled on staging | installed; **no install step in reapply** | Installed only by the manual `--install` (`REEXPORT.md:520`). It gives the Craters `#cobblemon:is_volcanic` and `#cobblemon:is_thermal` |
| `cobblers_campaign` | datapack (global) | No generator in the repo | Server only, 14 files (09-10/09-15): EXP-001 functions, a placeholder loot table, 9 structures byte-identical to `cobblers_towns`' copies, and `f4/services/pokecenter.nbt`. No function places a template from it (every `cobblers:f4/...` reference resolves in `cobblers_towns`) | installed; **not built from the repo** | Legacy, enabled on staging, loaded by the live world |
| `cobblers_build` | datapack (global) | No generator in the repo | Server only, 10 files (09-15): 7 grove and 2 town-prep functions, superseded by `cobblers_reapply` | installed; **not built from the repo** | Legacy, enabled on staging |
| `COBBLEVERSE-DP-v31.zip` (riding patch) | datapack (global) | `tools/patch_cobbleverse_riding.py` (`modpack/datapacks/README.md`) | Server zip sha256 `91b2f6d6…` against upstream `24344c64…` (`base-pack/inventory/pack_hashes.csv`), 09-10. Neither `assemble-server.ps1` nor `reapply.py` runs the patch | installed; **no install step** | Not re-verified against a fresh patch run |
| `datapacks/extra`: Terralith, Hoenn, Johto, Sinnoh DPs | upstream datapacks | CLAUDE.md lists "the Terralith datapack, and the region datapacks in … extra" as world-critical | Global Packs `optional`; all four are in the staging `level.dat` **Disabled** list. `tools/spawn_biomes.py:10` says "the server does not load it" | **not enabled** | No decision record found for leaving them off |
| Server mods | mods | Manifest plan, `--side server` | 100 of 100 present and hash-matched. Extra and not listed: `Axiom-6.0.5`, `worldedit-mod-7.3.8`. No client-only jar on the server | installed | `pack_manifest.py verify`: 100 ok, 0 missing, 2 extra |
| Client mods: `rctapi` | mod (both sides) | Overlay pins `rctapi 0.16.1-beta`, the double-KO softlock fix (STATE l.13) | Client has `rctapi-fabric-1.21.1-0.16.0-beta.jar`; 0.16.1 is missing. Also extra: Axiom, DBTools | **stale** (client) | `verify --side client`: 134 ok, 1 missing, 3 extra. Whether the client's version matters for a server battle is not verified |
| `resourcepackoverrides.json`, `defaultoptions/options.txt` | client config | ATMxMSD RP removed from the default packs | The client's copies equal the repo's by JSON and by key; only line endings differ. The client's `options.txt` pack list matches the repo, plus `file/cobblers-model-fixes.zip` at the top | installed | This choice is the cause of the 40-species substitute doll (STATE l.143) |
| Client model fix: ATMxMSD subset and 1.8 models for 16 forms | client resource pack | Proposed (STATE l.146, `COBBLEVERSE_COMPATIBILITY.md` "Client model audit") | Not built | **never built** | 11 of the 40 are in our spawn tables, Greavard in the Route 1 mansion among them |
| `cobblers-model-fixes.zip` | client resource pack | `tools/client_model_fix.py build/install`, per client, never committed | On this client, 09-14, 7 forms; enabled last | installed (this client only) | Nothing gives it to another player's client |
| `cobblers_rift_ctm` | client resource pack | `tools/ctm_pack.py` → `build/resourcepacks/cobblers_rift_ctm` (09-22): connected-texture variants for the Rift's rock | Not in the client's `resourcepacks/` or `options.txt` | **never installed** | `RIFT_FRACTURE.md:415-419`: shipping it needs an ADR (MPL-2.0 art). None exists. The owner's complaint that the walls read as a grid stands in game |
| Overlay configs on the server | config | `modpack/config/**` | `server_config_record.py check`: 0 disagreements. `rctmod-server.toml` on the server has `relativeLevelCap = 0` | installed | STATE l.187 ("the server still runs 5") and blocker 2 (l.202) are out of date. The client's `cobblemon/main.json` and `starters.json` differ, but the server decides both |
| Trainers | data → rctmod pack | `data/trainers.json`: 63 records | `cobblers_trainers` carries 13 of them (Routes 1-3) plus 5 mansion guardians (`mansion_guardians.json`). 36 route trainers are `placement.status: proposed`, and the 12 authored bosses and Giovanni's held slot are in no pack. Leaders fight with Cobbleverse's `COBBLEVERSE-RCT-DP-v20` rosters | **no install step** (paused by the owner, STATE l.95) | Pack `trainers/` has 18 files |
| Dialogue NPCs | data → NPCs | 24 conversations carry an `npc_id` | 9 are placed (R9F: the Digger; R17: 8 scene NPCs). No step places the other 15: the 13 mainline-reveal NPCs and the two crushed-house NPCs, whose conversations the compiler refuses | **no install step** | Known blocker (STATE l.215) |
| Rewards | data → pack | `data/rewards.json`: Victory Road's 5 finds | `cobblers_rewards` is global and identical | installed | No other reward content exists |
| Signposts | data → pack | `data/signposts.json` | `cobblers_signs/place` holds 50 sign placements; installed globally; run by R15 | installed | |
| Traders | data → pack | 25 records, 4 withdrawn | 21 summons across 14 `vendors_*_place` functions: 7 regional traders and 14 Marts. Run by R14 | installed | `status: planned` on all 25 means "not in the campaign world" (the field definition), which is true of the live world |
| Placements and towns | data → packs | 375 placements (365 `planned`, 10 `verified`) and 26 planned places | `prepare` refuses to continue unless every place has an R8 step and each of the 32 donors an R9 step | installed (staging only) | The statuses describe the live world |
| Landmarks | data | 22 built, 4 partial, 2 planned (`river_of_shrews`, `surge_signal_array`) | No generator places a landmark record | no install step (design) | |
| STATE on themed saplings | record | STATE l.142: "The trees' placement function is `cobblers:reapply/themed_saplings` (R5B)" | That function is in neither the built nor the installed `cobblers_reapply` | STATE is wrong until `prepare` re-runs | See the first row |

## What matters to gameplay first

1. **The next re-apply run stops at R5B, and its elders are old.** `cobblers_reapply` was last assembled at 01:44. It
   has no themed-saplings function and carries a 591-line elders function where the build has 645. Re-running
   `prepare` (then `install`) fixes both. Until then, the STATE line naming R5B is wrong.
2. **Elders and themed saplings depend on a pack nothing installs, and nothing audits them.** Everything in
   `cobblers_kits` is on the server only because it was copied by hand (the last copy was at 13:33). Neither `prepare`
   nor `install` builds or copies it. A server assembled from the repo would place 52 elders and 14 saplings from
   missing templates, and `build_audit` would still report clean.
3. **The size-outlier layer has never been on any world since the disposable one.** `cobblers_sizes` is built and
   current, but `SERVER_PACKS` leaves it out and nothing else installs it.
4. **Client visuals:**
   - the model-fix subset is not built, so 11 spawnable species render as the substitute doll (Greavard in the
     mansion among them);
   - the Rift's connected-texture pack is built but never installed, pending an ADR that does not exist;
   - `cobblers-model-fixes.zip` exists only on this client.
5. **The client runs rctapi 0.16.0, not the pinned 0.16.1.** Whether that matters for the double-KO softlock is not
   verified. The battle runs on the server, which has 0.16.1.
6. **Built content with no placement:**
   - 8 compiled habitat pools have no block;
   - 36 route trainers and every custom leader, Elite Four member and the Champion are in no pack (paused);
   - 15 NPC conversations have no NPC (blocked).
7. **Manual-only installs that happen to be present:**
   - `cobblers_spawn_tags` (current);
   - the riding-patched `COBBLEVERSE-DP-v31.zip`.

   A server rebuilt from the repo would lose both silently.
8. **Hygiene in the global folder, which the live world loads:**
   - legacy `cobblers_campaign` and `cobblers_build`, not built from anything in the repo;
   - the staging-only `cobblers_vr_backfill` and `cobblers_vr_clear`;
   - the unused concrete-fixed `brock.nbt`.

   The Terralith and region datapacks in `extra/` are disabled, with no recorded decision.
9. **STATE lines to correct:**
   - `cobblers_progression` is installed (l.90);
   - `relativeLevelCap` is 0 on the server (l.187, l.202);
   - 333 Habitat Blocks are recorded, not 82 (l.82);
   - R5B's function does not exist yet (l.142).
