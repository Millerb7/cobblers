# EXP-012: Bounded default-spawn suppression on route corridors

## Objective
Route corridors get an exclusive, authored encounter pool; the rest of the map keeps Cobbleverse's default
spawning. That needs the default (inherited) pools switched off inside the 1,408 route boxes in
`data/routes.json` and left alone everywhere else. This experiment asks, in order:
1. whether installing the curated route pools already makes them exclusive;
2. whether a native, bounded exclusion exists;
3. whether it holds at the scale of every inherited spawn file against every box.

## Success criteria
- **Baseline:** the share of curated species inside a corridor with only the route pools installed, and an
  outside sample for comparison.
- **Mechanism:** one inherited file overridden at its resource path loses its entries inside the listed boxes
  and keeps them outside, with `/checkspawn` A/B at a fixed spot.
- **Scale:** a pack overriding every inherited file loads, and its cost in pack size, boot time, reload time,
  heap and tick time is measured.
- **Result:** the inside-corridor sample goes from its baseline to effectively 100% curated.

## Dependencies
Cobblemon 1.8.0+1.21.1 on Fabric 1.21.1, the full COBBLEVERSE server stack (`COBBLEVERSE-DP-v31.zip` as a global
datapack; `mega_showdown`, `cobblemon-additions`, `zamega`), the compiled route pools from
`tools/compile_spawns.py` installed as the world datapack `cobblers_spawns`. Disposable world
`cobblers-runtime-proof/spawnproof`, seeded from the offline snapshot `2026-09-17-pre-grass`; the live world is
never touched. One player (an operator account). Server run with `-Xms4G -Xmx10G`, Java 21.0.9.

**Sample site:** inside box `r01_b0080` (x1360-1527, z4792-4815, Route 1, Pallet meadows roster
Pidgey 24 / Rattata 24 / Mareep 12 / Wooloo 12, levels 5-8), player at (1443, 125, 4803). **Outside site:**
(1731, 4803), 200 blocks east of any box.

## Implementation

### 1. Baseline: route pools installed, nothing suppressed
An 8-minute sample at each site: a helper over RCON kills wild Pokémon within 64 blocks, then polls every 10 s and
records each new entity's species, level and position. The positions are classified against the route boxes and
each box's compiled roster.

### 2. Probe pack (`cobblers_probe`, world datapack)
Five inherited files copied to the same resource path and modified. Each variant tests one thing:

| Variant | File (source) | Change | Tests |
| --- | --- | --- | --- |
| V1 | `herds/0504_patrat_herd.json` (jar) | `"anticonditions"`: all 1,408 route boxes on its one entry (133 KB) | many boxes on one detail; the scale of one entry |
| V2 | `herds/0161_sentret_herd.json` (jar) | `"anticonditions"`: the 5 boxes nearest the site, not including `r01_b0084` | the plural key; boundedness |
| V3 | `herds/0659_bunnelby_herd.json` (jar) | `"anticondition"`: the single object for box `r01_b0080` | the singular key as the jar itself uses it |
| V4 | `herds/0263_zigzagoon_herd.json` (jar only) | `"enabled": false` | disabling a jar file by path |
| V5 | `0161_sentret.json` (jar, overridden by COBBLEVERSE-DP) | `"enabled": false` | precedence over the global Cobbleverse pack |

Box condition shape: `{"minX": min_x, "maxX": max_x, "minZ": min_z, "maxZ": max_z}`, with no Y bound.

### 3. Full override pack
`tools/suppress_inherited_spawns.py` reads every `data/<ns>/spawn_pool_world/**.json` the server loads, from mod
jars (including nested packs), global datapacks and world datapacks. For each resource path it takes the
highest-priority file, skipping our own `cobblers_*` packs. It re-emits that file with every spawn detail given
one coordinate anticondition per route box. Any existing anticondition is kept, and a singular one moves into the
list. `--boxes merged` re-cuts the same union into fewer rectangles on the boxes' shared 8-block grid. The output
is `build/`, gitignored, and never committed: it is upstream spawn data re-emitted.

## Test instructions
1. **Baseline:** install `cobblers_spawns` only. Run `observe_spawns.py sample <label> 8` at the inside site, then
   at the outside site. Classify the rows with the compiled rosters.
2. **Probe:**
   - Write the V1-V5 files into a world datapack and enable it (`datapack enable "file/cobblers_probe"`).
   - Run `/checkspawn common` in game at (1429, 122, 4794) inside `r01_b0080` with the probe off, then on.
   - With it on, run the same at (1446, 4856) inside `r01_b0084`, which only V1 lists.
3. **Scale:**
   - `python tools/suppress_inherited_spawns.py --server <server> --world <disposable world> [--boxes merged]`.
   - Boot the world without the pack, and again with the pack copied into `datapacks/cobblers_suppress`. Time
     process start to `Done`, then after 20 s run `jcmd <pid> GC.run` and `GC.heap_info` for the live heap.
   - Time `reload` over RCON (with a trailing command so the timing covers the server thread) with the pack
     enabled and disabled.
4. **Result:**
   - With the pack enabled and the player at the inside site, run `/checkspawn common` and repeat the 8-minute sample.
   - Poll `/tick query` every 5 s for the 8 minutes.
   - Disable the pack and poll 8 more minutes at the same spot.

## Results
Run 2026-09-17.

### 1. Installing the curated pools does not suppress anything

| Site | Spawns in 8 min | Curated | Default |
| --- | --- | --- | --- |
| Inside `r01_b0080` | 96 | 52 (54%): Rattata 21, Pidgey 14, Mareep 9, Wooloo 6, plus Wingull 1 and Krabby 1 from an adjacent box's roster | 44 across 30 species, levels up to 38 (Linoone 38, Skitty 33, Dugtrio 32, Drilbur 31, Voltorb 29) in a 5-8 zone |
| Outside (1731, 4803) | 97 | none | 97: Caterpie 24, Blipbug 16, Hoppip 12, Ledian 9, Metapod 5, … |

`/checkspawn common` inside, before suppression: Rattata 6.15%, Pidgey 3.51%, Wooloo 2.89%, Mareep 2.09%,
under the default herds at 8.79% each. The route pool is added to the default pool, not substituted for it.

### 2. The probe: the plural key is a bounded exclusion

- **`"anticondition": [array]` breaks the reload.** The log shows "Not a JSON Object", and one bad file aborts
  the whole `/reload` ("Reload failed; keeping old data"). The singular key takes one object only.
- **`"anticonditions": [list]` parses.** V1 carries 1,408 boxes on one entry and loads.
- **`/checkspawn common` at (1429, 122, 4794), inside `r01_b0080`:**

  | Entry | Probe off | Probe on |
  | --- | --- | --- |
  | bunnelby-herd (V3) | 4.03% | absent |
  | patrat-herd (V1) | 4.03% | absent |
  | sentret-herd (V2) | 4.03% | absent |
  | zigzagoon-herd (V4) | 2.01% | absent |
  | Sentret (V5) | 0.6% | absent |

- **Boundedness, probe on, at (1446, 4856) inside `r01_b0084`:**
  - bunnelby-herd 4.37% and sentret-herd 4.37% are back: V3 and V2 do not list that box.
  - patrat-herd is absent: V1 lists every box.
  - zigzagoon-herd and Sentret are absent: V4 and V5 are global.

  Each exclusion applies exactly to the boxes it lists.
- **`"enabled": false` at the same path disables a file,** whether it exists only in the jar (V4) or is also
  provided by the global COBBLEVERSE-DP (V5). A world datapack wins over both.

### 3. Scale: every inherited file against every box

| Measure | Value |
| --- | --- |
| Inherited source files read | 2,590 (the Cobblemon jar 1,544, COBBLEVERSE-DP 1,024, mega_showdown 19, cobblemon-additions 2, zamega 1) |
| Resource paths overridden | 1,729 (860 are provided by more than one source; the highest priority is used) |
| Spawn details carrying the exclusion | 5,195 |
| Boxes per detail | 1,408 raw; `--boxes merged` gives 1,293 with identical coverage, so merging does not help |
| Pack size | 368.3 MB of compact JSON raw (338.5 MB merged) |
| Boot, process start to `Done` | 33.4 s without the pack, **41.5 s** with it (+8 s); `Done` reported with 43-44 ERROR lines both ways, all pre-existing |
| Live heap after full GC | 2,569 MB without, **4,076 MB** with (+1.5 GB) |
| `/reload` | 5.3-5.7 s without, **14.0-14.6 s** with (+8.5 s; the first reload after boot took 25.5 s) |
| Tick time at the corridor, player present, 96 polls of `/tick query` each | median 4.0 ms both ways; p95 median 4.5 ms with, 4.3 ms without; p99 median 26.3 ms with, 23.6 ms without (periodic spikes present both ways; one poll during the disabling reload excluded) |

The pack loads with no failure, and the spawn tick shows no measurable cost.

### 4. The corridor with the pack on

`/checkspawn common` at the inside site: **Pidgey 33.33%, Rattata 33.33%, Mareep 16.67%, Wooloo 16.67%**, which is
the authored 24/24/12/12 and nothing else. `/checkspawn` in a second bucket: "Nothing can spawn here right now"
(the roster has no entries there).

The 8-minute sample, same site and radius:

| | Before | With the pack |
| --- | --- | --- |
| Spawns | 96 | 124 |
| Curated roster | 52 (54%) | **121 (97.6%)**: Pidgey 47, Rattata 24, Mareep 20, Wooloo 19, and Staryu 3, Krabby 2, Wingull 2 from the adjacent coast box's roster, all in band except one Pidgey |
| Not curated or out of band | 44, up to level 38 | 3: Glameow L6, 5.8 blocks inside a box edge; Krabby L10, 1.5-2.5 inside an edge of a box whose roster lacks Krabby; Pidgey L23, 2.5 inside an edge |

Positions are sampled up to 10 s after spawning, and all three residuals were within 6 blocks of a box edge.
That fits a default spawn just outside a box that wandered in before the poll. No residual was found deeper
inside a box.

### 5. Coarser exclusion boxes

The boxes now decide only where the default pool is excluded, so an exclusion slightly wider than the corridor
costs little. `--boxes merged --grid N` snaps the union outward to an N-block grid (a cell is excluded if any
route box touches it), then merges. Each measured on a fresh boot of the same world, live heap after a full GC:

| Grid | Boxes | Overshoot past a box edge | Excluded area | Pack | Boot to `Done` | Live heap | Heap cost over no pack | `/reload` (second run) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no pack | | | | | 33.4 s | 2,569 MB | | 5.3-5.7 s |
| 8 (raw) | 1,408 | 0 | 2.75 km² | 368 MB | 41.5 s | 4,076 MB | +1,507 MB | 14.6 s |
| 16 | 637 | under 8 blocks | 2.97 km² (+8%) | 168 MB | 38.6 s, 34.5 s | 3,263 MB, 3,254 MB | **+690 MB** | 10.6 s |
| 32 | 321 | under 24 blocks | 3.37 km² (+23%) | 86 MB | 36.5 s | 2,910 MB | +341 MB | 7.0 s |

Heap cost falls in step with the box count. **Grid 16 is adopted:** it removes 54% of the heap cost for at most 8 blocks of
overshoot. Grid 32 removes 77%, but overshoots by up to 24 blocks. The coarser packs were not re-sampled for spawns:
their exclusion covers every raw box, and the mechanism is unchanged.

**The overshoot strip is dead ground:** it is outside the curated boxes, so neither the default pool nor the
route pool spawns there. At grid 16 that is a strip under 8 blocks wide along a corridor's outer edge. If it ever
matters, compile the route pools on the same grid.

## Limitations
- One corridor site, one player, 8 minutes per condition, at day and night. Other routes, water, caves under a
  corridor (the boxes have no Y bound, so caves beneath are also suppressed) and fishing are not sampled.
- Anticonditions test the spawn position. A Pokémon that spawns outside a box and walks in is not prevented;
  the edge residual above is that effect.
- **The pack is regenerated, not maintained.** Any change to the mod list, the Cobbleverse datapack version or
  the route boxes needs a rerun. A new inherited file the generator has not seen is not suppressed.
- Heap and boot deltas were measured on this machine with this pack size. A client joining the server receives
  no spawn data, so client cost is not expected, but it was not measured.
- Tick cost with several players spread over many corridors is not measured.
- The pack re-emits upstream data, so it is local build output and can never be committed or shipped in a
  public repo.

## Decision
**Adopt bounded exclusion; do not switch default spawning off globally.**
- Every inherited spawn file is overridden at its path with the route boxes as `anticonditions` (plural key),
  generated by `tools/suppress_inherited_spawns.py` into `build/`.
- Cobbleverse's wild spawn design stays live everywhere outside the route corridors; the corridors get only
  their authored pools. The campaign does not author the whole map's wilderness.
- **Box set:** the union snapped to a 16-block grid (637 boxes; `--boxes merged --grid 16`, the generator's default).
  Costs accepted: a 168 MB generated pack, about +3 s boot, +690 MB heap, +5 s per `/reload`, and dead strips
  under 8 blocks wide at corridor edges.
- `"enabled": false` at the same path is proven, and is kept for removing a whole inherited file where that
  is wanted. It is not the corridor mechanism.

## Follow-up
- Wire the pack into the server build, so it is regenerated whenever mods, the Cobbleverse datapack or
  `data/routes.json` change, with a check that every loaded inherited path is covered.
- An independent test author reviews `tools/suppress_inherited_spawns.py` (box merging, precedence, the
  singular-to-plural move); it was written and run in the same session as this experiment.
- Sample a second corridor on water, and one with caves beneath, before any cave content is authored under a route.
- Habitat Blocks for place identity inside or beside corridors: see EXP-021.
