# Where the Nether dungeons' rips stand: siting research (RESEARCH ONLY, nothing built)

Written 2026-10-10 by unit NETHER-THEMES. The five nether themes (`data/dungeon_themes.json`: `nether_wastes`,
`crimson_forest`, `warped_forest`, `soul_sand_valley`, `basalt_deltas`) are built and tested; the dungeons themselves are
authored later. This note answers: how is this world's Nether generated, do the five biomes exist and where, and how can
a rip be placed in each without breaking "ground comes from the heightmap, never from a world". Labels: **READ** = read in
a jar, a file or a README this session, with the source; **ASSUMED** = vanilla behaviour recalled and not checked here;
**UNKNOWN** = becomes an experiment.

## 0. Premises checked

| Premise (from the brief) | Finding |
|---|---|
| "the world's seed: `data/world.json`" | **Wrong.** `data/world.json` has `"seed": null`. The seed lives in a `level.dat`. `tools/structure_candidates.py` reads it from one at run time "and never writes it out". `docs/STATE.md` disagrees with itself: its "World facts" section says the live seed is "deliberately uncommitted, identified only by SHA-256 48202407...", while its first section prints the staging world's seed in plain text ("carried from a disposable copy of `cobblers-10240.pre-rescale`'s `level.dat`"). Those are the same seed. This note does not repeat the number; someone should decide which STATE line is true. |
| "a datapack may generate the Nether" | **No datapack or mod config touches it.** READ: every datapack zip and folder of the 2026-10-05 server snapshot holds one Nether file (a loot table, `COBBLEVERSE-Loot-DP-v11.zip` `chests/nether_bridge.json`) and no dimension, noise-settings or biome override. `base-pack/cobbleverse/config/biome_replacer.properties` lists only Terralith ids; `nethermap.toml` sets map creation height 40 for `minecraft:the_nether`. So the Nether is **vanilla 1.21.1 generation from the world seed**, plus mod features and structures (section 2). |
| "a nether has no heightmap in this repo" | True, and it has no routes or sub-regions either (`docs/mechanics/NETHER_ENCOUNTERS.md` section 1, "Two rings"). |
| "the five biomes exist" | **They are vanilla's five, but where each lies is a function of the seed, unmeasured.** The live world has never generated a Nether chunk (`docs/world-building/DIMENSIONS_AND_BORDERS.md` section 3). |

## 1. How the Nether is generated here (READ from the 1.21.1 jar)

- `dimension_type/the_nether.json`: `min_y` 0, `height` 256, `logical_height` 128, `coordinate_scale` 8, `ultrawarm` true,
  `has_ceiling` true, fixed time 18000. (Our pocket dimension is **not** ultrawarm, `tools/portals.py:415`, so the
  one-deep water in the nether themes' "flooded" looks is legal inside a dungeon.)
- `worldgen/noise_settings/nether.json`: `noise.height` 128, `min_y` 0, `sea_level` 32 with lava as the default fluid,
  default block netherrack, a bedrock floor at y0-4 and a bedrock roof at `below_top` 5..0 (y123-127). Nothing generates above
  y127: **y128-255 is empty air inside the build limit** (the "Nether roof").
- Biomes: `worldgen/multi_noise_biome_source_parameter_list/nether.json` is just `{"preset": "minecraft:nether"}`: the
  five biomes are points in a six-parameter climate space and the climate noises are seeded by the world seed. READ: that is
  all the jar says. ASSUMED: the points are the usual ones and `depth` varies with y, so the biome of a column is **not
  constant with height** (a site's biome must be asked at its own x, y, z).
- Border: the world border is shared in block coordinates (`DIMENSIONS_AND_BORDERS.md` section 2): the Nether is
  x/z -1024..9215. A portal from the landmass (overworld 0..8191) lands in Nether 0..1023: the **Near Nether**
  (-128..1152, `NETHER_ENCOUNTERS.md` section 1). That is the part players reach by portal; the rest is walking or flying.
- Structures there (READ): vanilla `nether_complexes` (fortress and bastion, spacing 27, separation 4), `ruined_portals`
  (40/15), `nether_fossils` (2/1); Repurposed Structures 7.5.21 adds nether sets for ancient cities (400/250), cities (100/50),
  outposts (65/25), villages (53/27), temples (33/16), ruins (36/3), pyramids (45/23), monuments (320/140), shipwrecks
  (21/11), strongholds (135/60) and mineshafts (spacing 1, frequency 0.00275). The pack's `repurposed_structures.json` has no
  structure switches, so all are on. `cobblers_dimension_overrides` zeroes Blaine and Moltres in the Nether and keeps the
  Ruinous shrines (`data/dimension_overrides.json`). **Disagreement:** EXP-058's README says PASSED (run 2026-10-08, ungraded);
  `docs/STATE.md` still says "BUILT, NOT PROVEN (2026-10-10)". Reconcile before anyone relies on either.
- Mods that matter to siting: `netherportalfix` (changes portal linking in some way not read), `nethermap` (maps in the Nether).

## 2. Where the five biomes are: what the repo has, and what it lacks

- **No biome lookup tool exists.** `tools/structure_candidates.py` reproduces `random_spread` placement from the seed
  (EXP-058 matched it against `locate` for Blaine, Moltres and the League), but biome checks are outside it ("which become
  starts is decided by biome and terrain, which this does not model"). `tools/spawn_biomes.py` lists biome *names* from
  jars, not positions.
- The vanilla server itself is the exact biome oracle: a **throwaway world on the live seed with the server's mod set**,
  the method of EXP-058 (worlds `exp058_control*`, the offline snapshot `server-snapshot-2026-10-05`). `locate biome` is
  documented vanilla (`execute in minecraft:the_nether run locate biome minecraft:crimson_forest`, the same shape as EXP-058's
  `locate structure` lines). Whether `locate biome` leaves chunks or structure starts behind is **UNKNOWN**; EXP-058 found
  that `locate structure` in the Nether saves starts "that the pack cannot remove", so **the live Nether must never be asked,
  and the oracle world must be a different world folder.**
- Writing a Python biome-noise port (cubiomes-style) is possible but is new machinery and a new correctness proof; the
  server already answers exactly. Not recommended unless the throwaway-world route proves unworkable.

## 3. Options for a rip in each biome without reading a world to decide

All five rips are Nether doors into the pocket dimension; **nothing about the dungeon depends on where the door stands**.
Engine fact: `tools/dungeon.py` builds rips only in the overworld (5 literal `minecraft:overworld` sites: the exit `tp`
at 1139 and 1141, the particles at 1546 and 1548, the placement at 1602, plus the rip's click entity chain). Any option needs
`rip.dimension` and those sites changed, and a reapply step like `R16DR` that forceloads the pad's chunks in the Nether.
Entry to the Nether is gated at `gym8_cleared` (`NETHER_ENCOUNTERS.md` G1; EXP-063 NOT_EXECUTED), so these dungeons run at
bands 5 and 6 in practice.

| | A. One hub, five rips | B. Blind pads at `locate biome` coordinates | C. Oracle-planned pads | D. Portal-linked chambers | E. The Nether roof (y128+) |
|---|---|---|---|---|---|
| Idea | A built station at one fixed Nether spot; a rip per dungeon, signed | A sealed pad built at the coordinates `locate biome` returns, at a fixed y, terrain unseen | As B, but the site and y are chosen from an oracle world's terrain (no lava in or beside the pad, an existing cavern), and the choice committed as data | A sealed chamber at the exact landing point of an overworld portal (overworld x,z = 8 x Nether), lit portal frame inside | Pads on the empty air above the bedrock roof, over each biome |
| Door in the biome | **No** | Yes | Yes | Yes, if the landing point is | **Unknown**: the biome at y200 need not be the surface biome |
| Terrain-blind | Yes (one site, can be vetted by hand once) | **Yes, and unsafe**: a pad carved into rock beside lava inflows, or overlapped by a Repurposed Structures piece | No, by design | Needs a vetted site as C | **Yes and safe** (nothing generates there) |
| Reachable | By portal, by construction | Only by the player's own means | Only by the player's own means (plus a compass, below) | By portal | Players cross the roof routinely; the roof route is the standard bypass |
| Follows the ground rule | Yes (no terrain decided) | Yes (nothing read) | **Needs a judgement call** (section 4) | Needs the same | Yes |
| New machinery | A pad builder; no oracle | A pad builder; the oracle's `locate` only | A pad builder, an oracle run and a planner tool in `tools/` | As A, plus 5 overworld portals and linking behaviour (`netherportalfix` unread) | A pad builder |
| Survives a re-export | Yes: data re-applied; the Nether regenerates from the same seed (ASSUMED identical) | Same | Same, plus the plan must be re-derived if the mod set changes | Same | Same |

**Recommendation: C**, staged so that B's data is step one and A is the fallback.

1. **Oracle run (experiment NS1).** A disposable world on the live seed (read from an offline snapshot's `level.dat` at run
   time and never written out, as `structure_candidates.py` and `reexport.py` do), the server's mods and global datapacks, and
   **no `cobblers_*` world-local pack**. For each biome, `locate biome` from several origins inside the Near Nether; record
   x, z and the distances. Pin the result to the seed's SHA-256 and the mod set's hash, as `data/world.json` pins the heightmap.
2. **Plan.** `tools/nether_plan.py` (to write) reads that oracle world's saved regions only, and for each biome picks the site
   in the Near Nether with an existing open cavern of at least the pad's volume, no lava within 3 blocks of it, no structure
   start overlapping it, and the biome confirmed at the pad's own x, y, z. Output `data/nether_rips.json`
   (`biome`, `x`, `y`, `z`, `pad box`, seed sha, mod-set hash) and `derived/nether_plan/`.
3. **Pad.** A 21 x 21 plate of the theme's hull with the rip frame (`rip_lines`, the same two posts and lintel), a clear 9-high
   volume, a one-block parapet, the theme's light. A reapply step carves and builds it by `fill`, forceloading the chunks, then
   releasing them. Navigation: a lodestone beside the rip and a compass whose `minecraft:lodestone_tracker` component targets it
   (ASSUMED vanilla 1.21.1 component form, not read here; verify in EXP-NS2) given by the Nether's first quest or trader.
4. **Verify (read only).** After the step, `tools/presence_audit.py`-style probes read the **staging** world's pad (never the
   live world) for the frame, the hull and the clear volume. This read confirms what was built; it does not decide a position.

**What flips it:** if NS1 shows a biome with no patch inside the Near Nether, or every candidate in a biome has lava or a
structure on it, use A for that biome's rip (a station at the first safe vetted spot, biome named on its sign). If the owner
does not need the door to stand in the biome, A is the cheapest of all and C buys nothing.

## 4. The ground rule, applied to the Nether

`CLAUDE.md`: a tool that decides where something goes takes its ground from `tools/ground.py` or measured plan data, "never
from a world", because a world holds whatever was built into it last and a tool that reads its own output builds on top of
itself. The Nether's heightmap equivalent is **the pure generator's output for the seed**. An oracle world that has never had a
`cobblers_*` pack or a command run in it holds none of our output, so the rule's reason does not apply; its letter says "a
world", so **this is a judgement call for the owner**. To keep it honest:
- the planner refuses an oracle world whose `level.dat` lists any `file/cobblers_*` data pack or whose
  `data/` holds a `command_storage_cobblers*` file (a test, as `tests/test_ground_rule.py` does for placement tools);
- the plan's inputs are the seed's hash and the mod set's hash, so it is reproducible from `data/` and the oracle;
- the live world is never read, enumerated or asked (`locate` included), and the staging world is read only in step 4.

## 5. Ordering constraints (READ)

1. `cobblers_dimension_overrides` must be installed before **any** Nether chunk of the live world is generated, `locate`
   included (EXP-058, "Finding for the live world"). The pad step generates Nether chunks, so it comes after.
2. The nether gate (EXP-063) should be proven before pads exist, or a player without the eighth badge can reach a rip.
3. The pocket dungeons need no Nether terrain, so they can be authored and played from the overworld test rips first.

## 6. Experiments this opens (none run)

- **NS1** the oracle run above: biome patches in the Near Nether for the live seed, and whether `locate biome` creates chunks
  or structure starts (count region files before and after).
- **NS2** a lodestone compass given by command points at a Nether lodestone and spins nowhere else; and a pad built by `fill`
  in a freshly generated Nether area holds against adjacent lava for 10 minutes of game time.
- **NS3** the engine change: a rip with `dimension: minecraft:the_nether` places, clicks, returns the player to the Nether
  pad (not the overworld) and shows its particles.

## 7. Not verified here

The biome parameter points, how `depth` varies with y, `locate biome`'s side effects, portal linking under `netherportalfix`,
the lodestone component form, whether a regenerated Nether is identical after a re-export, and every behaviour in a running
Minecraft. Nothing was run on a server, and no world was read.
