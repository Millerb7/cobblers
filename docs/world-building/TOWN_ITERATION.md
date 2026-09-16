# Iterating on town layouts destructively (2026-09-15)

**Verdict: B, copy out and copy back, with a bounded box. Not A.** The instinct that A is strictly better for
surface towns is wrong, and it is wrong for a reason that has nothing to do with surfaces: **a region file is 512 ×
512 and a town is 119–217, so restoring region files reverts 3.3 to 4.6 times more ground than the town occupies**,
including whatever else you have built in that square. B's seam risk, the thing that made A look safe, is an
artefact of the one copy that was ever done — and that copy was cross-world.

Measured round trip on a test town: **70,750 blocks destroyed, 0 differing after the restore, across all
201,326,592 block cells of both region files.** The restore took **0.16 s**.

| | A: restore region files | B: copy out, copy back |
| --- | --- | --- |
| Unit | the whole 512 × 512 .mca | a chunk-aligned box you choose |
| Ground reverted, hometown | 262,144 blocks | 73,984 |
| Ground reverted, gym 1 | 524,288 | 123,904 |
| Also reverted | the elder tree, the outpost, the routed leg in that square | nothing you did not name |
| Seam risk | none | **none, when the source is a copy of the current world** |
| Server must be stopped | **yes** | yes, for the write |
| Snapshot cost | 14.2 MB, 0.02 s (2 files) | the same 14.2 MB |
| Restore cost | 0.02 s (file copy) | 0.16 s (256 chunks) |

Both cost the same. A is not cheaper; it is only coarser.

## 1. The seam was cross-world. Confirmed.

`REEXPORT.md` records it as: *"outside the rectangle, the two exports differ by 457 blocks in the 8-block strips
around it. About 170 are leaves or logs of a few trees."* Read again, that sentence is not measuring a seam a copy
produced. It is measuring **how far apart two different exports were** in the strips around the hometown box —
the sculpt export (heightmap `19abdd39…`) and the relief export (`217d411c…`). The hometown was never actually
copied across that gap; it was re-placed with the seating placer.

Both retired worlds are still on disk, so this was re-measured rather than argued.

**The control, which settles it.** The sculpt export before the town went in
(`2026-09-15-pre-sculpt/sculpted-export-before-transplant`) against the same export after the town was copied into
it (`2026-09-15-pre-relief/cobblers-10240`), in the 8-block ring outside the rectangle, full column y−64..319:

| | Cells |
| --- | ---: |
| Compared | 3,833,856 |
| Differing | **468** |
| …of which `minecraft:grass` → `minecraft:short_grass` | 466 |
| …of which lava → water | 2 |
| **Tree blocks differing** | **0** |
| Ground-height columns differing | **0 of 9,984** |

The 466 are the server's DataVersion upgrade of the pre-1.20.3 block name on chunk load, already known and
harmless. **A chunk copy between two copies of the same world produces no seam at all.**

**The cross-world case, same ring, same method** — sculpt export against the relief export:

| | Cells |
| --- | ---: |
| Differing | **239,949** (6.3% of the ring) |
| Columns with at least one difference | 9,970 of 9,984 |
| **Tree blocks differing** | **178** |
| Ground-height columns differing | 0 of 9,984 |

178 is the "about 170" in the record. Where they are is the whole story — six clusters, every one of them hard
against the box edge:

| Cluster | Where | Side | Present only in |
| ---: | --- | --- | --- |
| 76 | x1368–1372, z5343–5347, y109–116 | west of x1376 | the relief export |
| 38 | x1568–1570, z5108–5112, y111–116 | east of x1567 | the relief export |
| 26 | x1374–1375, z5222–5226, y120–124 | west of x1376 | the sculpt export |
| 23 | x1368–1369, z5099–5103, y124–127 | west of x1376 | the sculpt export |
| 9 | x1575, z5064–5066, y119–121 | east of x1567 | the sculpt export |
| 6 | x1389–1391, z5398–5399, y105–107 | south of z5391 | the sculpt export |

Six oaks, a birch and a dark oak that stand in one export and not the other, within 8 blocks of the boundary.
Copy the box across and you keep the inside from one world and the outside from the other, and those trees are cut
in half. That is the seam.

**One correction to the hypothesis.** The terrain did *not* differ: ground height is identical in all 9,984 ring
columns, because the relief pass did not reach Pallet Meadows. What differed is everything WorldPainter rolls per
export — the foliage objects at the surface and, far more of it, the substrate and ore field underground. That
239,949 is almost entirely stone↔dirt, gravel↔stone, deepslate↔ore, down to y−63, symmetric in both directions.

**So the real finding is worse than the record, and it makes B safer, not riskier: two WorldPainter exports of the
same heightmap are not the same world below ground.** Cross-world chunk copying will always seam. Copying between
two copies of one world cannot.

## 2. What A actually costs

A region file is 512 × 512 blocks and 6.9–8.4 MB. Every town's footprint is much smaller than one, so a restore
always reverts a large collar of ground you did not ask about.

| Town | Footprint | B's box (+64, chunk-aligned) | Region files | A reverts | A / B |
| --- | ---: | ---: | --- | ---: | ---: |
| hometown | 132 × 132 = 17,424 | 73,984 (289 chunks) | `r.2.10` | 262,144 | **3.5 ×** |
| gym1_town (Viltri Plateau) | 217 × 217 = 47,089 | 123,904 (484 chunks) | `r.3.6`, `r.3.7` | 524,288 | **4.2 ×** |
| gym2_town (Lake Viltri Hollow) | 119 × 119 = 14,161 | 69,632 (272 chunks) | `r.3.5` | 262,144 | **3.8 ×** |
| league | 196 × 196 | 112,896 (441 chunks) | `r.6.4`, `r.6.5` | 524,288 | 4.6 × |
| displaced_city | 132 × 132 | 78,336 (306 chunks) | `r.5.3` | 262,144 | 3.3 × |
| sunset_west | 408 × 408 | 304,640 (1,190 chunks) | `r.2.13`, `r.2.14`, `r.3.13`, `r.3.14` | 1,048,576 | 3.4 × |

The "region files" column is what the *footprint* alone touches. Restoring the footprint **plus a margin** often
costs another file: the hometown's box + 64 runs to x1599, which is inside `r.3.10`, so an honest A restore of the
hometown is two files and 524,288 blocks — a **7.1 ×** revert.

**What else lives in those same files**, outside the town's own box + 64:

| Town | Collateral a restore also reverts |
| --- | --- |
| hometown | the **relic_island** outpost (1072–1111, 5512–5551); 160 blocks of the hometown → gym 1 leg, of which only 128 are inside B's box |
| gym1_town | the **viltri_plateau elder tree** at (1730, 3960) — one of the 48 in `derived/sites/elder_trees.json`; 1,074 blocks of routed leg (hometown → gym 1 and gym 1 → gym 2) against 398 inside B's box |
| gym2_town | the **lake_viltri_hollow elder tree** at (1824, 3056); 590 blocks of routed leg against 303 inside B's box |

The legs are still planned polylines, not built roads, and the landmark trees happen to sit outside these
particular squares. That is luck, not design, and it will not hold: `great_oak_pallet` is in `r.3.10`, one file
east of the hometown's, and the first hometown restore that needs a 64-block margin already spills into it.

**The general shape of A's cost:** you cannot restore a town without also restoring everything within up to 511
blocks of it that happens to share the square. You will not always remember what that is. B makes you name the box.

### Does A need the server stopped? Yes.

Three separate reasons, in order of how quickly they bite.

1. **The OS will not stop you.** Probed on the running server: `region/r.4.9.mca`, `region/r.5.9.mca`,
   `r.0.0.mca` and `level.dat` all opened for write from a second process while the server held them. There is no
   guard rail. Only `session.lock` is range-locked, and that only stops a second *server*: a second boot attempt
   during this work died with `java.io.IOException: The process cannot access the file because another process has
   locked a portion of the file` at `SessionLock.create`.
2. **The server writes over you.** Chunks live in memory. `save-all flush` rewrote `r.5.9.mca` from 7,024,640 to
   7,127,661 bytes during this test. Anything loaded — forceloaded, or within a player's view distance — is
   rewritten from the cache on the next autosave, on unload, and on shutdown. Your restore lasts until then.
3. **The sector table goes stale, and that is the one that corrupts.** A .mca is a sector-allocated container with
   an 8 KiB header of chunk offsets and lengths, which the server holds in memory along with a free-sector map.
   Replace the file underneath it and the two disagree; the next chunk write lands on sectors the server believes
   are free and which now hold other chunks. *Not verified:* the corruption path was reasoned from the format, not
   demonstrated — the destructive test was not run against the live world with a player on it.

The same three apply to B's copy-back. **Reading** region files while the server runs is fine and was done
repeatedly here.

## 3. B's bounding rule

> **Copy back the authored footprint plus 64 blocks, expanded outward to the chunk grid. Never whole region
> files. Snapshot and restore `region/`, `entities/` and `poi/` together.**

**Why 64.** The margin has to cover the largest thing that can be placed with its anchor inside the footprint and
its blocks outside it. The list, measured from the templates:

| What | Reach from its anchor | Source |
| --- | ---: | --- |
| **world tree** (`world_oak_a`) | **59 blocks** | template 117 × 202 × 117, trunk 21 × 21 at offset (49, 48) → trunk centre 59 from the far edge. `crown_radius: 46` is the cluster *ring* radius; the hung leaf balls add another 14 |
| elder tree | 20 | 41 × 84 × 41, `crown_radius` 19, `limb_reach` 17 |
| giant tree | 14 | `crown_radius` 14 |
| landmark trees (Great Oak, kapok, patriarch, cherry elder) | 21 | foliage library, max `crown_radius` 23.3 in a 42 × 57 × 41 box |
| largest building | 23 | `structure_pokemart` 23 × 12 × 22, and placements are corner-anchored (`anchor_mode: corner`), so the whole box extends from the anchor |
| light from a source at the edge | 15 | light 15 falling 1 a block |

59 is the binding number and 64 is the next multiple of 16 above it, so the margin is exactly 4 chunks and a
chunk-aligned footprint stays chunk-aligned. **Note the trap:** `crown_radius: 46` in `world_oak_a.json` is not
the reach. The reach is 59. A 48-block margin would clip the new world tree.

**Why chunk-aligned, and why that is not negotiable.** The Anvil region file stores one deflate-compressed NBT
record per chunk column, 16 × 16 × 384. There is no smaller unit. `tools/transplant_chunks.py` copies the
compressed record and its timestamp verbatim, which is why lighting, heightmaps and block entities travel with it
intact. Splitting a chunk would mean decompressing it, splicing packed block-state arrays (4–12 bits a cell, per
16³ section, each with its own palette), then re-deriving the heightmaps and the stored light for the result. The
alignment is the file format's, not a convenience.

**Expand outward, never inward.** `(min >> 4) * 16` and `(max >> 4) * 16 + 15`. Rounding inward would leave a
strip of your build behind.

### Two sharp edges in `transplant_chunks.py`

- **A chunk missing from the source is deleted in the destination.** The tool's rule is "the source has no chunk
  here (e.g. no entities): leave none". That is right for a fresh export and wrong for a restore from a partial
  snapshot. Running it with a box the snapshot does not cover reported `missing_in_source: 484` and would have
  deleted 484 destination chunks had they existed. **Snapshot every region file your box touches, or the restore
  is a deletion.**
- **`entities/` and `poi/` count.** The hometown's `r.2.10` carries 0.2 MB of entities and 0.1 MB of poi. The
  2,048-chunk restore in this test reported `missing_in_source: 2048` for both, because those files did not exist
  for the test area. Restore a real town with a region-only snapshot and every mob, item frame, armour stand and
  village POI in the box is wiped.

## 4. The round trip, proved

Test area: **x2592–2719, z4896–5023**, a 128 × 128 stand-in footprint in unnamed forest. Nearest authored thing is
**734 blocks** away (the Great Oak outpost); both region files, `r.4.9` and `r.5.9`, contain no town, no elder
tree, no landmark and **0 routed leg points**. Before the test: 256 chunks, 25,165,824 cells, **0 man-made
blocks**, 1,367 tree blocks.

| Step | What ran | Result |
| --- | --- | --- |
| Snapshot | server stopped; `region/`, `entities/`, `poi/` for `r.4.9`, `r.5.9` | 2 files, 14.2 MB, **0.02 s** (no entity or poi file existed) |
| Destroy | `fill` ×2 glass at y200–207 (65,536), `fill` air through terrain at 2640–2655 / y95–114 / 4940–4955 (4,096), `save-all flush` | 69,632 blocks changed by command |
| Measure the damage | both whole region files, 2,048 chunks, 201,326,592 cells | **70,750** differing: 70,247 inside the footprint, **503 in the margin**, **0 outside the restore box** |
| Restore | `transplant_chunks.py --blocks 2528 4832 2783 5087` | 256 chunks, **0.16 s** |
| Verify | the same 2,048-chunk, 201,326,592-cell comparison | **0 differing. Everywhere.** |

**The 503 is the finding, not the 70,247.** Those are blocks in the margin, outside the footprint, that changed
without anything being built there: `minecraft:grass` → `minecraft:short_grass`, the server's own DataVersion
upgrade, applied to every chunk it loaded — and it loaded a halo beyond the 64 chunks that were forceloaded.
**Touching a town changes its neighbours.** The halo stayed inside 64 blocks, which is one more reason the margin
is 64 and not 16.

**A corollary that undercuts A's headline claim.** "Restoring puts back identical bytes" is true of the file and
false of the world. Bringing the live world back to pristine afterwards — 65,536 glass removed, then 542
run-length `fill` commands rebuilding all 5,120 carved cells from the snapshot — left **862 blocks still
different from the snapshot**: 852 `grass` → `short_grass` and 10 fluid cells (lava → obsidian, lava → water,
water → stone) where loading the chunks let fluids tick. None of it is damage and none of it is recoverable by
building; it is what a chunk does when a server looks at it. Your snapshot stops being byte-equal to the live
world the moment anyone flies over the town.

## 5. Commands

Set the box from the footprint in `data/towns.json`, add 64, round outward to the chunk grid, and list the region
files it touches. **The server must be stopped for the restore.**

```powershell
# --- snapshot, before a session --------------------------------------------
$world = "C:\Users\wnd\Documents\github\cobblers-server\cobblers-10240"
$snap  = "C:\Users\wnd\Documents\github\cobblers-server-retired\town-snapshots\gym1-2026-09-15"
$regions = @("r.3.6.mca","r.3.7.mca")          # every file the box+64 touches
foreach ($d in @("region","entities","poi")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $snap $d) | Out-Null
  foreach ($r in $regions) {
    $src = Join-Path $world "$d\$r"
    if (Test-Path $src) { Copy-Item $src (Join-Path $snap "$d\$r") -Force }
  }
}
```

```bash
# --- restore, after a session you want to throw away (server STOPPED) -------
python tools/transplant_chunks.py \
  --from "C:/Users/wnd/Documents/github/cobblers-server-retired/town-snapshots/gym1-2026-09-15" \
  --to   "C:/Users/wnd/Documents/github/cobblers-server/cobblers-10240" \
  --blocks 1568 3456 1919 3807          # gym1_town footprint + 64, chunk-aligned
```

Add `--dry-run` first and read `missing_in_source`. **If it is not 0 for `region`, stop:** your snapshot does not
cover the box and the run would delete chunks.

### Measured timings

| | Measured |
| --- | ---: |
| Snapshot, one town (2 region files, 14.2 MB) | **0.02 s** |
| Snapshot, whole world `region/` (484 files, 2.28 GB) | **2.4 s** |
| Restore, 256 chunks (hometown-sized box) | **0.16 s** |
| Restore, 2,048 chunks (two whole region files) | **0.15 s** |
| `save-all flush` on an idle world | < 1 s |
| **Server stop**, 0 players, idle (`stop` over RCON to the last log line) | **~2 s** |
| **Server boot**, JVM start to "Done" (`Dedicated server took N seconds to load`) | **34.1 s median** over the 24 boots recorded in `logs/` — 25.2 s best, 118.9 s worst, 40.4 s most recent |

The file work is free. **The entire cost of a throw-away session is one stop and one boot: about 36 seconds**, and
that is the same for A and for B. Choose on what gets reverted, not on speed.

Verification of a restore (the block-for-block comparison used above) runs at about **7.4 s per two region
files**, 2,048 chunks. Cheap enough to run every time.

## 6. No town needs a WorldPainter export

**No.** The pipeline puts the boundary explicitly, in
[`STRUCTURE_WORKFLOW.md`](STRUCTURE_WORKFLOW.md#worldpainter-boundary):

```text
-> WorldPainter: landmass, elevation, mountains, rivers, coasts, biome masks, broad forests
-> Minecraft editing: roads, town pads, terrain seams, detailed vegetation, structure placement
```

and the rule under it: *"Generate terrain first, then place reviewed structures in Minecraft."*
[`TOWNS.md`](TOWNS.md) says layout, streets and buildings *"are authored in Axiom; the footprint is only the flat
square that fits."*

The record agrees. Every re-export in [`REEXPORT.md`](REEXPORT.md) was driven by a heightmap or a paint change —
the ocean mapping, the river cuts, the tarn, the Crater biome tags, the foliage pass, the sculpt, the hillside
relief, the river head, the creek. Not one by a build. And [`BUILT.md`](BUILT.md) records the cavern, the Foothill
Woods grove, the 48 elders and **the gym 1 and gym 2 town prep — streets, plazas and a gym lot flattened to
y141 — all built with commands on the exported creek world.** Even the ground-shaping under a town is done in
game.

**The one direction it runs.** A re-export for *terrain* reasons will wipe a built town, which is why
`transplant_chunks.py` exists at all and why `TOWNS.md` records the hometown rectangle as protected from
sculpting. That is the cross-world copy diagnosed in §1 — and it is the one case where the seam is real, because
the two worlds genuinely are different exports. **Re-placing from templates, as the creek export did, avoids it
entirely; copying across does not.**

## What this leaves undone

- **The corruption path in §2.3 is reasoned, not demonstrated.** Replacing a region file under a running server
  was not tested against the live world, because a player was online.
- **`entities/` and `poi/` were not exercised.** The test area had neither file when it was snapshotted, so the
  restore proved only `region/`. A real town restore must be re-proved with all three.
- **Nothing was tested in game.** The round trip was verified by reading region files, not by flying the site.
- **Lighting across the box edge was not measured.** Chunk records carry their own light, so the restored box is
  self-consistent, but a chunk just outside the box can hold light from a source you removed. 64 blocks is four
  times the propagation distance, so it should not reach, and that was not checked.

## What this session did to the server

- **Stopped the server once** (22:17:58, 0 players, clean, ~2 s) to take the snapshot. **It was restarted from
  outside this session at 22:19:05** — parent process already gone, and no start script exists in the server
  folder, so most likely by hand. A second boot attempted at 22:20:51 therefore failed on `session.lock` and was
  killed; it never opened the world. **Assume the server can come back under you and check before writing to
  region files.**
- **Edited and fully reverted** x2592–2719, z4896–5023: verified back to the snapshot except the 862 blocks in
  §4, all of them the server's own chunk-load effects.
- **Left behind:** `entities/r.5.9.mca` with 3 chunk records (mobs that spawned in the forceloaded chunks) and two
  empty `poi` files. Forceloads removed; `forceload query` is clear.
- **The snapshot is kept** at `cobblers-server-retired/town-iteration-test/snapshot/` (14.2 MB). Delete it when
  you are satisfied.
