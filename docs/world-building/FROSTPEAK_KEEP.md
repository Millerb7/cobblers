# Wardenhold: the snow-covered keep on Frostpeak Strand

> **Status 2026-10-09: built in the repository, applied to no world, seen in no game.** The owner asked for "a
> SNOW-COVERED CASTLE at Frostpeak Strand, visible from Highwire. Measure the sightline before siting it ... It should
> read as a landmark from Highwire first and a place second, so the silhouette matters more than the interior. Propose
> what it is and why it is there." The name, the story and the two Pokemon are **proposals for the owner to accept or
> change**. Files: `data/frostpeak_keep.json`, `tools/frostpeak_keep.py` (generator, step, probes),
> `tools/frostpeak_keep_audit.py` (independent audit), `tools/frostpeak_keep_siting.py` (the measurement below),
> `tests/test_frostpeak_keep.py`.

## 1. The sightline, measured first

**Method** (`tools/frostpeak_keep_siting.py`, from the canonical heightmap rounded as `tools/ground.py` does, never a world).
Minecraft is flat, so a point is seen from an eye when the straight segment clears the top surface (`round(h) + 1`) of every
ground column between them. Terrain only: no trees, fog or castle self-occlusion. A site is evaluated with the ground under
its base rectangle raised to the courtyard floor, as the build does.

**Observers** (eye 1.62 above the feet): ten street points on Highwire's shelf (`data/towns.json` gym3_town footprint
x1660-1715, z1382-1437, ground y174: the belvedere at the array path's lip (1700, 1382) and a 3 x 3 grid x1664/1688/1712,
z1386/1410/1434), and three points on the Relay Works' roofline (`data/placements.json` gym3_gym_building: y173, 17 high,
roof surface y190; a viewing height, not a walkway).

**Distant Horizons.** `modpack/config/DistantHorizons.toml` line 774, `lodChunkRenderDistanceRadius = 256` = 4,096 blocks
(DH's own comment calls it "a best effort number"; `docs/world-building/SIGHTLINES.md` quotes the same). The chosen site is
759-815 blocks from the streets, so the distance is not the limit. **What an 11-block-wide spire looks like as an LOD at 800 blocks
is NOT measured.**

**The terrain does block it.** From the belvedere to the Strand, the limiting column is the ridge at (1606, 925), ground top
y161, 467 blocks out: the line from the eye (y176.6) clears it by passing 0.033 of a block lower per block, which puts the
lowest visible point at the Strand's lip at y151 (courtyard floor y127 + 24). `python tools/frostpeak_keep_siting.py
coverage 32` over the Strand's 337 land cells (ground over y70): **no cell shows a point 20 blocks above its ground; 5%
(18 cells) show one 40 above; 25% (85 cells) one 70 above.** The six easiest cells are all on the southern lip
(z608-640): (1540,640) needs +21, (1508,640) +26, (1572,640) +28.

**Where.** `scan` over every 4-block centre whose base rectangle lies wholly inside frostpeak_strand's polygon (198
candidates) is a plateau of 0.28-0.29 street fraction between x1544-1572, z628-636; the site is the one in it with the best
worst street (0.19) and a roofline mean of 0.28:

| Site | Centre | Courtyard | Base in the Strand | Streets (mean / best) | Roofline (mean / best) |
|---|---|---|---|---|---|
| **A the southern lip (Wardenhold)** | (1548, 636) | y127 | yes | **0.28 / 0.37** | **0.28 / 0.48** |
| B east shoulder of the lip | (1590, 624) | y122 | no (crosses the boundary) | 0.25 / 0.38 | 0.02 / 0.07 |
| C west end of the lip | (1340, 628) | y112 | yes | 0.00 / 0.00 | 0.00 / 0.00 |
| D mid Strand | (1330, 330) | y95 | yes | 0.00 / 0.00 | 0.00 / 0.01 |
| E the Strand's heart (`encounter_design.json`) | (1296, 208) | y111 | yes | 0.00 / 0.00 | 0.16 / 0.22 |
| F the north-west Strand | (1300, 120) | y100 | yes | 0.00 / 0.00 | 0.27 / 0.34 |
| G the east arm | (2300, 470) | y110 | yes | 0.00 / 0.00 | 0.00 / 0.00 |
| H the far east arm | (2700, 560) | y101 | yes | 0.00 / 0.00 | 0.00 / 0.00 |

"Fraction" is the share of the silhouette (1-block bins across the line of sight, every solid block above the courtyard
floor) with a clear segment to the eye. The silhouette is mostly wide and low, so 0.28 is the share of the whole outline,
not of its height. By feature, from the streets (blocks visible above the lowest visible height at the feature's column;
negative is hidden by that much), at the chosen site:

| Feature (ry above the courtyard) | Belvedere | Street centre (1688, 1410) | Worst street (1712, 1386) | Roofline (1740, 1410) |
|---|---|---|---|---|
| Spire finial (ry 71) | +47 | +43 | +32 | +44 |
| Beacon chamber floor (ry 46) | +23 | +19 | +8 | +20 |
| Keep turret tip (ry 46) | +22 | +20 | +7 | +11 |
| Corner tower cone tip (ry 40) | +18 | +16 | 0 | -7 |
| Keep roof (ry 30) | +6 | +2 | -9 | +3 |
| South curtain wall top (ry 13) | -13 | -15 | -12 | -14 |

So from Highwire's shelf a player sees the **spire from about ry 25 up (its upper two thirds: the open beacon arcade, the
snow cone, the finial), the four keep turrets' cones and the corner towers' cone tips**, and nothing of the wall, which is
hidden by 12-20 blocks. The audit (`K7`) holds that: the finial from all ten street points and two of three roofline points,
the arcade from at least nine of ten, and at least 30 blocks of the spire's axis from the belvedere. **Reciprocal (`K8`):**
from the beacon arcade the belvedere and at least eight street points see back, so a player standing in the chamber sees
Highwire's shelf, 759 blocks south by east (bearing 170 degrees).

**Reachable on foot.** A 1-block-step walk (water excluded) from the array path's lip to the postern lane's far end exists:
weighted cost 819 for 749 straight-line blocks. The audit's own player model (`K9`) walks from the north approach and the
south hill to the courtyard, the hall, the archive, the loft, the roof pocket and the beacon floor.

**Not inside another place.** The base rectangle (x1520-1576, z612-660) lies wholly inside frostpeak_strand's polygon
(`data/regions.json`, edge columns checked every block). The nearest x/z any other `data/*.json` authors is 305 blocks away
(`sculpt.json` (1860, 770)); the nearest `data/routes.json` spawn-corridor box, counted as a filled rectangle, is 682 blocks
(route_04_surge_to_erika r04_b0037 [1664, 1336, 1711, 1343]); the generator refuses a site within 100 of either
(`tools/southern_residents.py` `authored_points` and `corridor_check`, the same reading `northern_residents` uses). The
Frostpeak research camp is at (713, 691) and the Ursaluna's den at (1504, 162, 1414): neither is near.

## 2. What it is, and why it is there (a proposal)

**Wardenhold is the northern end of the old Signal Wardens' line.** Before anyone strung wire, a chain of fire-keeps carried
warnings from the Strand over the Tri Peaks: ice-fall, storm, a party lost on the snow. Wardenhold's spire was built to be
seen from the shelf where Highwire now stands, and Highwire stands there because that is where the line ended: the town is
placed where it can see the keep, and the keep where it can be seen. Surge's relay (`docs/story/ARC.md` Settlement 4, the
array on the Vessu shoulder) is the wire that replaced the fire. The Wardens withdrew south, the fire went out, and the snow
kept the rest. It fits what the map already says about the north: the pilgrims' way and cairns on Frostpeak's summit
(`data/frostpeak_summit.json`), a tower "nobody alive remembers being built" (the camp's Dr. Halvard) and a cold country
people once crossed on purpose.

*Why a keep rather than an observatory or an ice queen's folly:* the measurement says only one thing on the Strand can be
seen, and it has to be tall and stand on the lip; a fire-keep is the one building whose purpose IS being seen, so the siting
needs no excuse. *What it commits the story to:* nothing named. The log never names a person or a town; "the shelf" is
Highwire; "the col" is the Tri Peaks pass. If the owner prefers another history the signs (`data/frostpeak_keep.json log`)
are the only text.

**Silhouette first** (all heights ry, above the courtyard floor; `data/frostpeak_keep.json dims`):

- the **spire**, 11 wide, rises from the keep roof (ry 31) to the beacon chamber (floor ry 46, open arcade ry 48-51 behind
  iron bars) under a snow-block cone (ry 56-68) and a finial (ry 69-71): **y198**, the tallest thing for 800 blocks. The
  arcade is the dark band the eye finds under the white cone; the body is deepslate and stone brick so it reads against sky;
- the **keep**, 19 x 19, battlements to ry 32, with four solid corner **turrets** under cones to ry 46;
- four **corner towers** (9 wide, walls to ry 26, cones to ry 40) on a 49 x 41 **curtain wall** (ry 10 walk, merloned to ry 12);
- a **gatehouse** of two towers astride a five-wide arch in the north wall (portcullis raised), and a three-wide
  **postern** in the south wall, where a walker from Highwire arrives (a gravel lane and a flight of stairs up to the hill);
- a **plinth**: the courtyard is the highest ground under the base rectangle, so the keep never cuts into the hill; the
  lower (north) ground is filled with rock and battered out at 45 degrees to meet the hill (a crag 22 blocks high on the
  north side) with the gate ramp, stairs down the batter on the axis.

**Snow and ice.** Every cone is `snow_block` with `blue_ice` trim; 800 `packed_ice` blocks are plastered on west faces,
their share rising with height (0.2 to 0.7): the repository's one west wind (`data/frostpeak_summit.json wind`). Snow layers
(1-5, deeper on a wall's lee side) cover the exposed masonry. Walls are `deepslate_bricks`, `stone_bricks` and their cracked
forms, `tuff_bricks`; the rock is `cobbled_deepslate`, `stone`, `tuff`, `andesite`. Vanilla 1.21.1 only; no concrete, no wool,
no bell or lightning rod (none is written; the audit holds it against `data/spawn_blocks.json`, `K4`).

**Dark by design.** No lantern, no light: a ruin, like the summit. (Open question for the owner: one lit lamp in the arcade
would make it a night beacon from Highwire, but DH's LOD lighting at 800 blocks is unmeasured, and a lit window in an
abandoned keep says the fire is back.)

## 3. The interior: a modest place

- **The cold hall** (ground floor): a long spruce table and benches, a cold hearth (an unlit campfire).
- **The archive** (ry 11-19): bookshelves and an empty lectern under four wall signs, **the Wardens' line log**: what the
  line was, how it answered ("Col to shelf: one fire. They answer in kind."), "Line first. Wood is dear."
- **The loft** (ry 21-29): a lookout's bench at the south slit and two signs (a bearing "South by east: the shelf." and
  "Count the fire. Two is well. None: ride to the col.").
- **The beacon chamber** (ry 47-54): a dead basin (an empty cauldron) and the last entry: **"LAST ENTRY / Fire out. Snow in
  the glass. Someone stays."** The thing to find is the log, and what stayed:
- **The Pokemon that belong** (two activated Habitat Blocks, `data/habitat_blocks.json`, status `planned`): the **household**
  in the hall (`frostpeak_keep_hall_ward`, up to 4 of Snorunt 28-38 common, Snom, Sneasel, the Strand's own band 28-38); and
  **the last watch** in the beacon chamber (`frostpeak_keep_beacon_ward`, ONE Froslass at level 40-44, above the Strand's
  28-38 and under tier 5's next cap 45), at the head of a 25-block ladder climb. A nest in the Ursaluna den's sense: a
  creature, a place that suits it, strong enough that meeting it early is a mistake, while the courtyard, the climb and every
  other room stay catchable. A Froslass is a snow-woman: the Wardens' log ends with someone staying.

## 4. Mechanism order (CLAUDE.md principle 6)

The building is **functions/commands** (a generated datapack function, like the summit, the Khan and the orchard): there is
no Cobblemon-native or addon structure for a castle, a plain datapack structure template would be a hand-built donor with a
licence to carry, and the repository's generators already place hand-designed buildings with an independent audit. The
Pokemon are **Cobblemon native** (Habitat Blocks, the spawn system `data/spawns.json` / `tools/compile_spawns.py`, never
`data merge` on a placed block). No custom mod, no scripting, no companion. Re-apply step **R9FK**, immediately before **R9E**
(the Habitat Blocks sit in floor cells this pack writes), pack `cobblers_frostpeak_keep`, prepare jobs `frostpeak_keep:build`
and `frostpeak_keep_audit`.

## 5. State model

Static world data only: the build and two Habitat Blocks. No scoreboard, storage, advancement or per-player state, nothing
gated, no quest. Multiplayer: the keep and the household are shared and persistent; the Froslass refills only when she is
caught or gone, one at a time, so a second player arriving after the first catches her finds the chamber empty until the
block refills it (the Habitat Block's own refill, as the Ursaluna den's Teddiursa). A player who dies on the climb respawns by
the blackout system as anywhere; nothing is lost. A re-export erases the build and the blocks, so R9FK and the Habitat step
re-place them (EXP-021).

## 6. Verified, not verified, assumed

- **Run:** the generator (24,995 commands, one function, `function_limits` clean), the independent audit (27 checks clean), the
  siting tool, `tests/test_frostpeak_keep.py` (25 pass, 1 skipped for `reapply.steps()`), the Habitat, spawn and encounter
  tests named in the commit.
- **Not run:** anything in a server or client; `tools/reapply.py steps()`, `uncovered()` and `unreferenced()` (they need
  `prepare`); `tools/nuzlocke_zones.py` (it needs `derived/cavern`): the two new unplaced pools were added to
  `data/nuzlocke_zones.json` `not_zones` by hand in the generator's own wording and count; `tools/availability.py` was not
  regenerated.
- **Assumed:** terrain-only sightline (the Strand's krummholz and any Highwire building are ignored); that signs with
  `'"text"'` messages are the 1.21.1 form (the repository's own `southern_residents.sign` writes them so); that a floating
  ghost spawns on a `grounded` pool in a roofed chamber; that a Pokemon will not leave the chamber (no ladder-climbing); how the
  keep reads as a Distant Horizons LOD.
- **Collisions:** none found. The base rectangle is 305+ blocks from every authored x/z and 682 from every route corridor.
  Highwire's own streets are untouched; the keep is on the far side of the Tri Peaks.
