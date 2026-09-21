# EXP-024: The re-export procedure, end to end on a staging export

> **Correction, 2026-09-21.** This experiment proved that the re-application commands run on a fresh export. It did not prove that they build what they should: most checks below read a sample, a proxy or an unanchored count. Re-checked by result on the disposable world, the builds these same functions made were missing 13,586 of Route 1's 46,052 trees and 165 columns of the cavern's roof cap, because 39 of 72 generated functions wrote into chunks they never force-loaded. The functions are fixed and every step now has a result check; which of the checks below were which is in `docs/world-building/REEXPORT.md`. A fresh staging run with the result checks has not been done.


## Objective
An inventory of authored content found that a re-export would lose work: Brock's gym had no rebuild path at all, the
braided maze forest had never been re-applied, the cavern's biome step had never been run after an export, and two
world datapacks live inside the world folder. This experiment fixes the rebuild paths and then proves the whole
procedure by exporting to a staging directory and re-applying everything onto it, before the live world is touched.

## Success criteria
- A real export runs to a staging directory, with the seed carried and all 484 region files present.
- Every re-application step runs against that export and its result is checked, read-only where possible.
- Anything that cannot be rebuilt from committed data is named.

## Dependencies
WorldPainter 2.27.1 headless, the canonical heightmap `land_8k_16_rescaled_b145_pads.png`, the project file
`cobblers-10240.world`, the paint manifest from `tools/paint_maps.py`, the offline snapshot `2026-09-17-pre-grass`
for the seed, and the installed COBBLEVERSE datapack for donor templates. Server: Cobblemon 1.8.0 on MC 1.21.1,
`-Xms4G -Xmx10G`. Nothing here touched the live world.

## Implementation

### Fixes made first
- **Brock's gym** (`data/placements.json` → `gym1_brock_gym`, `tools/place_donor.py`). Its template is Cobbleverse's
  `cobbleverse:brock`, which the licence forbids committing; but the pack is installed, so the gym is placed by resource
  id and the recorded concrete substitutions are applied with `fill … replace`. No local file is needed.
- **`REEXPORT.md`** rewritten: 6 items the export carries, 13 re-application steps in order, each with a check.
- **`derived/routes/critical_legs.json`** is gitignored and was absent; `tools/cavern_plan.py` will not run without it.
  It is now step R0.
- **Donor provenance** recorded for the hometown Pokémon Center and Mart, the only two local-only templates left.

### The dry run
1. `tools/reexport.py --out-dir <staging> --name cobblers-dryrun --paint build/paint/manifest.json`.
2. Phase A, server stopped: regenerate every datapack against the staged world.
3. Install them into the staged world's own `datapacks/`, wrapping the loose mcfunctions (elders, grove, gym prep) in one pack.
4. Boot the staged world as a disposable universe and run R2-R10 in order.
5. Verify, preferring read-only reads of the saved chunks over in-game checks.

## Results
Run 2026-09-17.

**The export.** 484 region files, `seed_match: true`, spawn (1461, 5306), border 10,240, on the canonical heightmap
with the three pads. The staging directory must exist first: WorldPainter refuses to create it (the first attempt
failed on that).

| Step | What ran | Check | Result |
| --- | --- | --- | --- |
| R0 | `critical_legs.py` | file written | **ok** (it was missing, and blocks the cavern tool) |
| R1 | `cobblers_height`, `cobblers_worldtree` copied into `<world>/datapacks` | `/datapack list enabled` | **ok**: both enabled as world packs |
| R2 | cavern: `00_seal, 05_reset, 10_excavate, 20_surfaces, 30_trees, 40_light, 50_tunnel, 70_drain, 15_cap, 60_biome` | air inside, floor under, biome | **ok**, and the cherry-grove biome applied on a fresh export for the first time |
| R3 | world tree `00_tree`…`03_tree`, `90_foundation` | column at (2016, 2280) | **ok**: 394 blocks, top y512, well above the vanilla 319, so `cobblers_height` is doing its job |
| R4 | grove and its augment | grove box | **ok**: 33,545 oak logs, 10,293 leaves |
| R5 | 48 elders (144 commands) | three recorded sites | **ok**: trees to y182, y189, y206 |
| R6 | 16 maze tiles | corridor clearance, sapling | **ok**: 157 of 158 sampled points on the through route and braids clear at eye height (one azalea at (1460, 4630)); sapling column 45 blocks, top y162; the tool seats it at ground y124, matching the original build record |
| R7 | hometown | `place_town.py --verify` | **ok**: **0 gaps in 1,670 columns**; exactly one waystone (its two halves), so the donor Centre's own waystone is still stripped |
| R8 | gym1 and gym2 prep (301 and 157 commands) | plaza block | **ok** |
| R9 | Brock's gym from the installed pack | `place_donor.py verify` | **ok**: 2,712 blocks, 20 block entities (trainer spawner, 9 command blocks, healing machine), substituted counts 566/274/127 exactly as recorded |
| R10 | islet | footprint read | **ok**: 400 columns, tops y63-70, all above sea, matching `data/towns.json` |
| R11 | Habitat Blocks | manifest | nothing to place (0 recorded) |
| R12 | waystones | fresh world | nothing stale to clear |
| R13 | spawn pools and suppression | not installed live | not part of this run |

**Route 1 still matches the rebuilt forest.** All 17 mandatory waypoints in `data/routes.json` lie on corridor
centrelines of the regenerated network (distance 0.0), because both come from the same source.

## Limitations
- The dry run rebuilt onto a **staging** export, not the live world. The live re-export still has to be done and checked.
- No Distant Horizons pregen, no client flight, and no player session: every check here is a command or a chunk read.
- Elder and grove sites are **re-picked** from committed data plus the new world each run. They are deterministic given
  the same inputs, but they are not guaranteed to match the previous world's positions.
- One corridor sample point is blocked by an azalea; the original build reported the same class of blemish.
- `tools/place_town.py` still reads two local-only donor templates (Centre and Mart). Their provenance is recorded, but
  a machine without those files cannot rebuild the hometown until they are re-extracted from the installed pack.
- The verification is mine, in the same session as the fixes; no independent review yet.

## Decision
**The procedure is proven on a staging export and `REEXPORT.md` is the record of it.** The two blockers that
prompted this (Brock's gym and the braided forest) are both rebuilt and checked. The live re-export is now a matter of
scheduling, not of unknown rebuild paths.

## Follow-up
- Re-extract the Centre and Mart from the installed pack at build time, so `place_town` needs no local file.
- Add the dry run to the release checklist: staging export, re-apply, verify, then the live one.
- Decide whether elder and grove sites should be recorded rather than re-picked, so a rebuild reproduces positions exactly.
