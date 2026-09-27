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
| `test_compile_spawns_sky.py` | which compiled spawn conditions require `canSeeSky` (land and surface do; submerged and seafloor must not), per entry and over the whole compiled output. |
| `test_water_mounts.py` | `data/water_mounts.json`: Surf and Dive lists disjoint, bare lowercase ids, each a Cobblemon 1.8.0 species (skips without the jar). |
| `test_themed_saplings_tool.py` | `tools/themed_saplings.py`: the build places each tree at its pin and never re-picks; nests bottom-up; `records --write` keeps a placed status only where the position is unchanged. |
| `test_no_eula.py` | no tracked (or untracked-but-not-ignored) text file accepts the Minecraft EULA, and no `eula.txt` is tracked. |

`conftest.py` provides `repo_root`, `tracked_files` (git-known plus untracked
non-ignored files, so new work is checked before it is committed) and `python`.

These tests do not touch Modrinth and do not need any jars. Regenerating the
manifest (`tools/pack_manifest.py generate`) is a separate, deliberate step.
