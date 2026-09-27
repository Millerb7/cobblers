# tests/

Fast, network-free checks on the repository's data and tooling. Run from the
repo root:

```
python -m pytest tests -q
```

| Test file | What it guards |
|-----------|----------------|
| `test_validate_runs.py` | `tools/validate.py` exits 0 on the repo and still lists its extension-point checks. |
| `test_manifest_consistency.py` | every hash in `base-pack/inventory/pack_hashes.csv` is in the base manifest; overlay `replace` / `remove` / `server_exclude` / `needs_functional_test` reference only mod ids that exist in the base (or in `add`); `server_exclude` equals the set of client-only mods; verified replacements carry a version id, URL and sha512; `plan --side server` leaks no client mod and contains Cobblemon 1.8.0. |
| `test_blackout_pack.py` | the generated `cobblers_blackout` pack: checkpoint ids cover every Center and town waystone and are never renumbered; validate, the charge, the dedupe, the Surf/Dive timers and the drowning hit, run on a small scoreboard simulator; claim categories and scan slots; claim-before-take and resolve-before-release order; macros, objectives, callbacks under `data/cobblemon/`; the Respiration override and the Dive swim modifiers. |
| `test_surface_exhaustion.py` | `tools/open_water.py` (lakes are not sea, band thresholds, rectangles cover the mask; Lake Tilpey and the far west margin on the real heightmap, which skips without it) and the pack's `surface/*`: every world row present and equal to the bands; land, riding and the shallows recover; the deep doubles, a partner halves; the ride flag does not carry between players; collapse reuses `water/pulse`, first hit as collapse is reached then one every `pulse_ticks` of time in any band; the tick runs every `sample_ticks`. |
| `test_system_contracts.py` | the cross-system contracts registered in `data/system_contracts.json`, each run with the systems together as generated: Dive unlimited and Surf's whole bonus at depth with swim fatigue running (a player model over the blackout pack's tick and the water-mounts MoLang; strict xfail today), the ferry's gates re-walked on the heightmap (slow, skips without it), no world pack placing a spawn condition its place is not whitelisted for, a claim surviving a simulated re-export, every gate's ward out of reach, the gate's flag granted by the progression pack; and the registry itself (tests exist and are registered, a consumer other than the owner, citations still quote their lines, failing contracts recorded and marked strict). |
| `test_carry_recovery_ledger.py` | `tools/carry_players.py` with the claim ledger: the ledger file is the pack's ledger namespace and is carried byte for byte; the shared `cobblers` storage never is; a world without scores is refused; the badge check is still reached. |
| `test_compile_spawns_sky.py` | which compiled spawn conditions require `canSeeSky` (land and surface do; submerged and seafloor must not), per entry and over the whole compiled output. |
| `test_water_mounts.py` | `data/water_mounts.json`: Surf and Dive lists disjoint, bare lowercase ids, each a Cobblemon 1.8.0 species (skips without the jar). |
| `test_themed_saplings_tool.py` | `tools/themed_saplings.py`: the build places each tree at its pin and never re-picks; nests bottom-up; `records --write` keeps a placed status only where the position is unchanged. |
| `test_no_eula.py` | no tracked (or untracked-but-not-ignored) text file accepts the Minecraft EULA, and no `eula.txt` is tracked. |

`conftest.py` provides `repo_root`, `tracked_files` (git-known plus untracked
non-ignored files, so new work is checked before it is committed) and `python`.

These tests do not touch Modrinth and do not need any jars. Regenerating the
manifest (`tools/pack_manifest.py generate`) is a separate, deliberate step.
