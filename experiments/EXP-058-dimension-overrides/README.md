# EXP-058: Do the structure_set overrides stop gym, League and legendary copies generating in the Nether and the End?

**Status: PASSED (run 2026-10-08 by the main session, not the builder; not yet graded by a reviewer).** Written 2026-10-10 by the builder of `tools/dimension_overrides.py`. Run and graded by
someone else (CLAUDE.md principle 16).

Number: EXP-057 was the next free number in this checkout; the brief named EXP-058, which keeps clear of a
concurrent unit that may take 057.

## Objective

The live world has never generated a Nether or End chunk (`docs/world-building/DIMENSIONS_AND_BORDERS.md`
section 3). When anyone enters, worldgen places Blaine-gym copies (a `kanto_blaine` trainer spawner in each) and
Moltres altars in the Nether, and League copies and Necrozma towers in the End. `cobblers_dimension_overrides`
overrides seven upstream structure_sets with `"frequency": 0.0` (`data/dimension_overrides.json`). This experiment
answers three questions on a throwaway world:

1. Does Minecraft 1.21.1, with this pack set, accept the override (no registry or parse error at boot)?
2. Does each suppressed structure stop generating in its dimension?
3. Is everything else untouched, the kept Ruinous shrines in particular?

"Yes" unblocks installing the pack beside the live world before anyone goes through a portal, and closes the
`docs/STATE.md` line "Generated gym copies".

## Where it runs

- **A throwaway, freshly generated world.** A worldgen question needs a plain generated world, not an export:
  never the staging world and never `cobblers-10240`. Use a disposable server folder with this server's mods,
  `config/` and global `datapacks/` (the offline snapshot
  `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05` has all three) and a NEW `level-name`.
- The live-server safety gate (CLAUDE.md) applies before any boot: port 25565 and the shared lock. Start the server
  detached and check the PROCESS, not just RCON. Never accept the EULA for the owner.
- Use the **same `level-seed`** for both worlds, so the control run's positions can be checked in the test run.

## Build

```
python tools/dimension_overrides.py build
python tools/dimension_overrides.py audit --roots <throwaway>/mods <throwaway>/datapacks
```

The audit must print `0 problems` and list 14 dangerous structures before anything boots.

## Run A: the positive control (no override)

1. Fresh world `exp058_control`, no `cobblers_dimension_overrides` anywhere. Boot it, wait for `Done`.
2. Over RCON, one at a time:

```
execute in minecraft:the_nether run locate structure cobbleverse:blaine
execute in minecraft:the_nether run locate structure cobbleverse:legendary/moltres
execute in minecraft:the_nether run locate structure legendarymonuments:stark_mountain
execute in minecraft:the_nether run locate structure legendarymonuments:firescourge_shrine
execute in minecraft:the_end run locate structure cobbleverse:kanto_league
execute in minecraft:the_end run locate structure cobbleverse:dawn_tower
execute in minecraft:the_end run locate structure cobbleverse:dusk_tower
execute in minecraft:the_end run locate structure legendarymonuments:eternatus_cocoon
```

3. Record each answer. Expected: a position for blaine, moltres, firescourge_shrine, kanto_league and the two towers.
   Eternatus may be too far for /locate's search (spacing 280 chunks). Stark Mountain is expected **not found** in
   both runs: its biome tag ships only in the disabled Sinnoh extra, so it cannot generate here at all. Its line is
   a check of that inference, not a control.
4. Forceload two of the found positions and save, so the region files hold real starts:

```
execute in minecraft:the_nether run forceload add <blaine x> <blaine z>
execute in minecraft:the_end run forceload add <league x> <league z>
save-all flush
```

   Stop the server, then audit from the region files (the world is disposable, so reading it is allowed):

```
python tools/dimension_audit.py --world <throwaway>/exp058_control --dimension the_nether --min-x <bx-64> --min-z <bz-64> --max-x <bx+63> --max-z <bz+63> --out derived/exp058/control_nether.json
python tools/dimension_audit.py --world <throwaway>/exp058_control --dimension the_end --min-x <lx-64> --min-z <lz-64> --max-x <lx+63> --max-z <lz+63> --out derived/exp058/control_end.json
```

## Run B: the override

1. **The SAME world as run A** (same seed by construction), stopped after run A. Only now copy
   `build/datapacks/cobblers_dimension_overrides` into its `datapacks/` folder. (Corrected 2026-10-10 by the
   independent audit 9f1c8f5: a pack present before a world's first boot is probably ordered BELOW the global
   COBBLEVERSE-DP; a pack first seen by an existing world is added at the top of its order, which is the case the
   staging and live worlds are in.)
2. Boot. Then:

```
datapack list enabled
```

   `file/cobblers_dimension_overrides` must be listed, and listed after the COBBLEVERSE datapack (the list runs
   lowest to highest priority). Record the order exactly as printed.
3. The same eight `locate` commands as run A.
4. Forceload the SAME two positions run A found, `save-all flush`, stop, and run the same two `dimension_audit.py`
   commands against `exp058_override`.
5. `grep -iE "cobblers_dimension_overrides|structure_set|Unbound|Failed to (load|parse)|registry" logs/latest.log`

## Success criteria

- Run B boots to `Done` with no registry, parse or datapack error naming the pack or any structure_set (step 5).
- `datapack list enabled` shows the pack above the COBBLEVERSE datapack.
- Run B: blaine, moltres, kanto_league, dawn_tower, dusk_tower and eternatus_cocoon each answer
  `Could not find a structure of type "<id>" nearby`, where run A found the first five.
- Run B: firescourge_shrine is still found (the kept Ruinous set is untouched).
- Run B's region-file audits show no `cobbleverse:blaine` start in the Nether chunks and no
  `cobbleverse:kanto_league` start in the End chunks where run A's show one.

## If it fails

- **Rejected at boot (frequency 0.0 out of range, or any registry error):** switch to the fallback in
  `data/dimension_overrides.json` `mechanism.fallback_if_rejected` (an empty biome tag, Terralith's precedent) and
  re-run. Do not install anything beside the live world meanwhile.
- **Loads but the pack sits below the COBBLEVERSE datapack:** the world-local choice is wrong for this server; record
  the order and take it to the owner before moving the pack to the global folder.
- **Loads, but a structure is still found:** record which; the set may be duplicated at another path (re-run the
  audit) or overridden by a later pack.

## Results (2026-10-08, main session)

Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, the server's full mod set and global datapacks
(COBBLEVERSE-DP-v31, -RCT-DP-v20, -Loot-DP-v11, No Hunger, No Ender Dragon), `cobblers-server` booted at 16G with
`--universe C:/Users/wnd/Documents/cobblers-staging`. Worlds `exp058_control` and `exp058_control2`, seed
-7807808745076202749, both disposable. Raw replies: the session scratchpad `exp058_*.txt`; audits `derived/exp058/`.

**The design above was not enough, and was changed while running.** `locate` in run B returned run A's positions
unchanged, because run A's own `locate` had already created those chunks at STRUCTURE_STARTS: the starts were saved
before the pack existed, and the pack cannot remove them. Forceloading the same positions in run B (step 4) would
likewise read run A's saved starts. So the proof used FRESH positions: a second control world on the same seed
(`exp058_control2`, no pack) located each structure from (6000, 64, 6000), and the same four chunks were then
forceloaded in both worlds. (Candidate positions were also reproduced independently from the seed with vanilla's
random_spread formula: Blaine chunk (-38, 57), Moltres (43, 10), League (-96, 50), all three matching run A.)

| Check | Without the pack | With the pack |
|---|---|---|
| boot | Done | Done; `Found new data pack file/cobblers_dimension_overrides, loading it automatically`; no error names the pack or a structure_set (the raid-den loot errors are the mod's own, in both runs) |
| pack order (`datapack list enabled`, 113 packs) | - | `file/cobblers_dimension_overrides (world)` at 112, after `COBBLEVERSE-DP-v31.zip (Global)` at 54: highest priority |
| locate from (6000, 6000): blaine | 555 blocks | 8,339 (only run A's saved start) |
| moltres | 1,173 | 7,894 (only run A's saved start) |
| kanto_league (End) | 2,720 | 9,155 (only run A's saved start) |
| firescourge_shrine (kept) | 781 | 781 |
| region files, Nether (6112, 6544) | 1 start `cobbleverse:blaine` | 0 starts |
| Nether (4944, 5488) | 1 start `cobbleverse:legendary/moltres` | 0 starts |
| End (5936, 8720) | 1 start `cobbleverse:kanto_league` | 0 starts |
| Nether (5552, 5360) | firescourge_shrine, ruins_nether, outpost_nether_brick | the same three |
| stark_mountain | not found (run A) | not found |

Each audited box: 64 chunks saved, 25 full.

**Verdict: the override works on 1.21.1 with this pack set. It stops Blaine, Moltres and League starts in fresh
chunks and leaves the kept shrines and other mods' Nether structures alone.** Dawn tower, dusk tower and Eternatus
were checked with run B's `locate` only, not region files (same mechanism, same pack file).

**Finding for the live world:** a `locate` (or any structure check that reaches STRUCTURE_STARTS) in the Nether or
the End **before** the pack is installed saves a start that the pack cannot remove. Install the pack before anyone
enters either dimension or runs `locate` there.
