# EXP-001: Can F4 Route 1 feel deliberately authored?

> **Superseded.** The source files this record refers to under `world/source/`
> were deleted when the prototype coordinate data was discarded. Both prototype
> landscapes are gone; paths below are historical. Surviving design intent is in
> `data/notes/legacy_events.md`, and the structure library lives in `kits/structures/`.

**Status: READY FOR F4 CLIENT PLAYTEST. Curated encounter proof remains pending.**

## Objective

Prove that one 1,000-block F4 planning hex can feel like a real Pokémon place:
a recognizable Pallet Town on a broad southern coast, a readable northbound
route, useful side paths, and optional discoveries that reward exploration.

## Success criteria

- A separate F4 save exists; launching it cannot silently open EXP-009.
- The mainland, coast, ocean, islands, woods and northeastern upland read as one
  continuous landscape rather than a flat test platform.
- Pallet Town includes donor-built houses, Oak's Lab, a Pokémon Center, a Poké
  Mart and a town sign without enabling donor natural world generation.
- The fish hut, abandoned house, broken boat and Relic Island are real,
  inspectable locations rather than marker blocks.
- Every placed structure resolves, persists through save/restart and works on
  the complete Cobbleverse-style server overlay.
- The route eventually contains an authored roster of roughly 10–20 Pokémon.

## Dependencies

- The EXP-000 100-jar Cobblemon 1.8 server overlay and matching client provide
  the shared executable runtime. EXP-001 owns its own selected save.
- Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0 and WorldPainter
  2.27.1.
- CobblemonCityTowns 1.0 is the MIT Pallet donor library. Selected templates
  are copied into `cobblers:`; the donor structure sets and natural generation
  are not installed.

## Implementation

- `world/source/exp-001/f4-region.json` defines the 1,000×1,000 F4 layout.
- `tools/generate_exp001_f4.py` creates the terrain masks, preview, hashes and
  `cobblers:exp_001/f4/setup` placement function.
- `world/source/worldpainter/build-exp-001.js` exports a separate Minecraft
  world into this experiment's ignored `runtime/` directory.
- The deterministic terrain has a sheltered southern bay, organic beach,
  northern woods, northeastern rocky upland and three offshore islands.
- The setup function lays three routes and places nine Pallet/service buildings,
  the fish hut, abandoned house, broken boat and Relic Island. It resolves donor
  jigsaws and removes donor loot-table references that were not copied.
- `server/scripts/install-exp001-world.ps1` installs the export as
  `exp001-f4-pallet-prototype` into the proven server runtime and selects it in
  `server.properties`. It does not touch `eula.txt` or EXP-009.
- `server/scripts/run-exp001-server.ps1` starts only that selected profile.

The tested local save is:

```text
experiments/EXP-000-cobblemon-1.8-compat/runtime/server/
└── exp001-f4-pallet-prototype/
```

The server binaries remain under EXP-000 because they are the shared verified
mod runtime. The world name and launch guard make the active experiment clear.

## Rebuild and install

From the repository root:

```powershell
python tools/generate_exp001_f4.py
New-Item -ItemType Directory -Force experiments/EXP-001-curated-route/runtime/export
& 'C:\Program Files\WorldPainter\wpscript.exe' world/source/worldpainter/build-exp-001.js 100 export
& server/scripts/install-exp001-world.ps1 -Replace
```

Run the placement function once on a fresh export:

```text
function cobblers:exp_001/f4/setup
save-all flush
```

The currently installed local save already contains the placement. Do not run
the setup function again unless deliberately resetting/rebuilding the prototype.

## Launch and inspect

Start the dedicated F4 profile:

```powershell
& server/scripts/run-exp001-server.ps1
```

Wait for `Done (...)`, then join **Multiplayer → `localhost`**. Do not open the
old Modrinth single-player Survival World.

| Place | Teleport command | Purpose |
| --- | --- | --- |
| Pallet spawn | `/tp @s 555 84 390` | Town and route junction |
| Oak's Lab | `/tp @s 610 86 305` | Canonical donor lab |
| Pokémon Center | `/tp @s 690 92 330` | Town service building |
| Poké Mart | `/tp @s 700 92 410` | Town service building |
| Abandoned fish hut | `/tp @s 170 90 515` | Western coast and dock |
| Abandoned house | `/tp @s 835 104 175` | Northeastern upland side path |
| Relic Island | `/tp @s 420 88 675` | Optional worldshift house and cache |
| Broken boat | `/tp @s 790 82 785` | Southeastern island landmark |
| North route exit | `/tp @s 620 95 30` | Route-scale endpoint |

## Runtime results

- **Generation/export:** deterministic 1,000×1,000 masks were generated at one
  block per pixel. WorldPainter produced a 272,097-byte editable `.world` file
  and a usable 22,606,414-byte Anvil save containing `level.dat`, `region/` and
  `entities/`.
- **Clean export boot:** the selected `exp001-f4-pallet-prototype` save reached
  `Done (1.959s)` on the 100-jar overlay (mod-set hash `62BEABD9398A`). Capture:
  `runs/20260910-175034/`.
- **Placement:** `cobblers:exp_001/f4/setup` executed successfully. Server-side
  checks passed for Oak's Lab, five Pallet houses, Pallet sign, Pokémon Center,
  Poké Mart, fish hut, abandoned house, Relic Island and broken boat.
- **Relic cache:** the chest at `(419,68,677)` contains one Relic Coin Pouch,
  three Poké Balls and one map.
- **Persistence:** `save-all flush` completed, the server stopped cleanly, and a
  fresh-log restart reached `Done (1.721s)`. Capture:
  `runs/20260910-180033/`. A later guarded-profile launch reached
  `Done (2.178s)`; post-restart checks found the Pokémon Center marker at
  `(690,81,340)`, the Poké Mart marker at `(722,78,425)`, and the unchanged
  Relic Island cache at `(419,68,677)`, followed by another clean save and stop.
- **Harness correction:** the boot script previously allowed a stale `Done` line
  to mask an early launcher failure. It now preserves and clears `latest.log`
  before starting Java; the results above were recorded after that correction.
- **Client visual review:** pending. Terrain silhouette, town composition,
  interiors, shoreline sightline and walking density still need in-game review.

## Superseded result

The first Relic Island proof was placed into the old EXP-009 save at Y=62 even
though that coordinate's terrain surface was near Y=84. It proved that the NBT,
loot and persistence worked, but it did not produce the planned F4 hex and could
be buried in terrain. That placement is superseded by this separate coastal
world and is not evidence of visual quality.

## Limitations and follow-up

- The prototype establishes geography and donor-built locations. It is not the
  production campaign save.
- The final Pichu reward waits for EXP-006/EXP-007 multiplayer-safe encounter
  and claim-state proofs; the current cache is a placeholder.
- Curated Cobblemon spawn data and the ten-minute observed roster test remain
  the final EXP-001 mechanic proof.
- Client feedback should drive terrain/town revisions before these coordinates
  become campaign canon.

## Decision

Use a shared, verified mod runtime with separately named experiment worlds. The
F4 world is ready for the user's visual and route-scale playtest; EXP-009 remains
available and unchanged under its own save name.
