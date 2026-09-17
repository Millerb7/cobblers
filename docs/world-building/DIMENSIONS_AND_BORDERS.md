# Borders, trim, and the Nether and End

**Status: the overworld border is applied in the re-exported world `cobblers-10240`
(`REEXPORT.md`).** The trim became unnecessary: the export is a full overwrite with nothing
outside the canvas. Nether and End pregen and audit are still procedures only.

**Decisions on record (2026-09-13):**
- **Overworld border:** 10240 × 10240, centred so the 8192 landmass has 1024 blocks of
  ocean on every side.
- **Nether and End:** stay real, vanilla-generated dimensions. Their structures are not
  relocated. The "everything hand-placed" rule applies to the overworld region only.
- **Timing:** borders, trim and pregen wait for the canonical terrain re-export. This
  document writes the procedures and the tools; nothing is applied to `erosion-land-8k`.

**Tools** (all read-only unless `--apply`; tests in `tests/`):

| Tool | What it answers |
| --- | --- |
| `tools/region_trim.py` | Which saved chunks and structure starts lie outside a rectangle. With `--apply --backup-dir`, removes them |
| `tools/dimension_audit.py` | After pregen: how much of the border area is fully generated, how much spilled outside, which structures started, and which required ones are missing |
| `tools/structure_candidates.py` | Before pregen: the candidate chunks a random-spread structure set can start in inside a border, from the world seed. An upper bound, since biome checks decide the rest |

**`structure_candidates.py` is verified against the live world.** The server generated 49
random-spread structure starts outside the export. The tool predicts every one of those
chunks exactly (49 of 49), including both Brock gyms (spacing 40) and the mega sites.
Mineshafts (spacing 1) are trivial matches. The seed is read from `level.dat` at run time
and is never written anywhere.

## 1. How the world border works in 1.21.1

- **One border is shared by all dimensions.** Minecraft Java has a single world border. The
  wiki's history for 14w19a says "The border in the Nether is now the same size as that of
  the Overworld". The border became dimension-specific only in 1.21.9 (25w36a), and the
  campaign is pinned to 1.21.1.
- **So a 10240 border centred on (4096, 4096) applies in every dimension.** The Nether and
  the End each span −1024…9215 in their own coordinates.
- **Not verified in game:** that the centre is also unscaled in the Nether. Check it on a
  disposable world:
  ```
  worldborder center 4096 4096
  worldborder set 10240
  execute in minecraft:the_nether run worldborder get
  execute in minecraft:the_end run worldborder get
  ```
  Then teleport to x=9200 and x=9230 in the Nether and see which side of the wall you are on.

## 2. Proposed sizes

### Overworld: 10240, centre (4096, 4096)

- **Border edges:** x and z from −1024 to 9215 inclusive.
- **Nothing outside to trim in the current save.** A dry run of `region_trim.py` against
  `erosion-land-8k` found all 307 region files and 268,045 saved chunks inside the border.
- **The margin is already dirty, though.** The server generated 5,901 chunks in the margin
  (outside 0–8191), holding 62 structure starts, including both Brock gyms at blocks
  (−376, 120) and (8520, 7976). A 10240 trim cannot remove them because they are inside the
  border. **They disappear only when the re-export writes the margin as WorldPainter
  chunks,** which is the plan.

### Nether and End: the shared border, not a smaller one

Candidate starts inside each option, counted with `structure_candidates.py` for the
PROGRESSION and LEGENDARY sets:

| Nether option | Blaine's gym (spacing 25) | Moltres (151) | Ruin shrines, 4 share one set (80) | Enforcement in 1.21.1 |
| --- | ---: | ---: | ---: | --- |
| **Shared border, −1024…9215** | 643 | **16** | **67** | vanilla, nothing added |
| 6144 centred on (512, 512) | 225 | 9 | 25 | needs a per-dimension mechanism |
| 4096 centred on (512, 512) | 108 | 1 | 9 | needs a per-dimension mechanism |
| 2048 centred on (512, 512) | 25 | 1 | 1 | needs a per-dimension mechanism |

(512, 512) is the overworld landmass centre divided by 8. Candidates on the End's outer
islands only (1024+ blocks from 0,0):

| End option | Kanto League (120) | Dawn tower (200) | Dusk tower (200) | Eternatus (280) | Enforcement |
| --- | ---: | ---: | ---: | ---: | --- |
| **Shared border, −1024…9215** | **26** | **8** | **9** | **4** | vanilla |
| 10240 centred on 0,0 | 29 | 8 | 9 | 8 | per-dimension |
| 8192 centred on 0,0 | 16 | 6 | 9 | 3 | per-dimension |
| 4096 centred on 0,0 | 3 | 0 | 1 | 0 | per-dimension |

**Candidates are attempts, not structures.** Each becomes a start only if its biome
matches: crimson forest for Blaine, nether wastes for Moltres, one of four Nether biomes
for the shrines, end highlands (plus midlands for Eternatus) for the End sets. The audit
after pregen gives the real answer.

**Recommendation: use the shared border for both dimensions.**
- **It needs no extra mechanism** and is finite and auditable at 104.9 km² per dimension.
- **Everything is likely present.** It holds 16 Moltres attempts and 67 shrine attempts, so
  all five Nether legendaries are very likely to generate. It holds 4 Eternatus attempts;
  smaller Ends drop Eternatus and the towers to zero or one.
- **A smaller Nether would need a datapack tick function** that teleports players back
  inside a soft limit, or a server-side border mod. Both add machinery the campaign does not
  otherwise need. Chunks near a soft limit still generate at view distance, and the audit
  reports that as spill.

**What the shared Nether costs:**
- **Many copies of Blaine's gym.** Blaine's set places an attempt every 400 blocks, so a
  10240 Nether could hold dozens to a hundred or more copies, depending on crimson-forest
  cover. The audit counts them. Every copy has the same RCT spawner, and the Kanto series
  still enforces the order (Blaine needs Sabrina). The copies are redundant, not broken.
- **Most of the Nether links nowhere on the landmass.** The overworld landmass corresponds
  to Nether x and z of 0…1024 (the margin to −128…1152). A portal built deeper in the Nether
  exits at an overworld position the border clamps to its edge, in the Outer Deep. This is
  expected from vanilla's portal clamp and not verified. It is survivable (portals over
  water get an obsidian platform), and it fits "the edge of the world". If it is unwanted,
  the soft-limit function above is the fix.
- **Pregen volume.** The border area is 409,600 chunks per dimension. The overworld export
  is 1.3 GB for 268,045 chunks; measure Nether and End storage on the first pregen.

## 3. Procedures

All of these run after the canonical re-export, on that world, with the server stopped
unless a step says otherwise. Back up first: copy the whole world folder, not only region
files.

### 3.1 Overworld trim (a safety check after the re-export)

1. Dry run. On a clean 10240 export, expect 0 chunks outside:
   ```
   python tools/region_trim.py --world <world> --min-x -1024 --min-z -1024 --max-x 9215 --max-z 9215 --out derived/trim/overworld_postexport.json
   ```
2. If anything is outside, apply with the backup folder outside the world:
   ```
   python tools/region_trim.py --world <world> --min-x -1024 --min-z -1024 --max-x 9215 --max-z 9215 --apply --backup-dir <backup>/trim-overworld
   ```
3. Distant Horizons keeps its own LOD database (`data/DistantHorizons.sqlite` in the world
   root, `DIM-1/data/` and `DIM1/data/`). Delete it after any trim or re-export so LODs of
   removed terrain do not persist. Whether DH server-side generation respects the world
   border is **not verified**. Check its config before letting it generate again.

### 3.2 Set the border

On the first boot of the re-exported world, from the console or RCON:
```
worldborder center 4096 4096
worldborder set 10240
worldborder get
execute in minecraft:the_nether run worldborder get
execute in minecraft:the_end run worldborder get
```
The border is stored in `level.dat` (`BorderCenterX/Z`, `BorderSize`).
`structure_inventory.py --world` reports `BorderSize`. Record the observed output in the
procedure run log.

### 3.3 Before pregen: candidates

```
python tools/structure_candidates.py --server-dir ../cobblers-server --level-dat <world>/level.dat --dimension nether --min-x -1024 --min-z -1024 --max-x 9215 --max-z 9215 --classes PROGRESSION,LEGENDARY --out derived/audit/nether_candidates.json
python tools/structure_candidates.py ... --dimension end ... --out derived/audit/end_candidates.json
```
If the re-export changed the seed, these numbers change. Re-run them rather than reusing
the tables above.

### 3.4 Pregen the Nether and the End inside the border

The overworld needs no pregen, because the export writes every chunk. The Nether and the
End generate normally, so they are pregenerated once to make them finite and auditable.

**Two ways to do it (a decision for you):**

| Method | Dependency | Notes |
| --- | --- | --- |
| **Chunky** (Fabric, server-only) | adds a mod for the pregen only; it is not world-critical and can be removed afterwards | radius and shape per dimension; resumable; standard tool. Not yet in the pack, so adding it follows the dependency rule |
| Vanilla `forceload` in batches over RCON | none | force-loading generates chunks to full. A script walks the area in batches under the per-command chunk limit, waits, and removes the tickets. Much slower, and entirely under our control |

**Steps with either method:**
1. Stop DH generation for the duration.
2. Pregen `minecraft:the_nether` and `minecraft:the_end` over −1024…9215.
3. `save-all flush`, then stop the server.

### 3.5 Audit what generated

```
python tools/dimension_audit.py --world <world> --dimension the_nether --min-x -1024 --min-z -1024 --max-x 9215 --max-z 9215 --require-classes PROGRESSION,LEGENDARY --fail-on-missing --fail-on-incomplete --out derived/audit/nether.json
python tools/dimension_audit.py --world <world> --dimension the_end   ... --out derived/audit/end.json
```

**Pass means:**
- `coverage_full` is 1.0.
- `required_missing` is empty: Blaine, Moltres, the four shrines, the League, both Necrozma
  towers and Eternatus are each present at least once.
- `chunks_saved_outside` is small, meaning view-distance spill only.

**Then record the result** in a short section here: counts per structure (including how
many Blaine copies), and the positions of the League and each legendary. Guidance
(section 4) is authored from those positions.

**If a required structure is missing,** do not relocate it (that is the decision on
record). The options are:
- enlarge the dimension's pregen and border, which in 1.21.1 means the shared border;
- accept its absence;
- or bring it back as a decision for you.

**What exists today:** the live world has never generated a Nether or End chunk. `DIM-1`
and `DIM1` contain only `data/` (the DH database and raid data), with no `region/` folder.

## 4. How the Nether and End fit the overworld critical path

> **Changed 2026-09-14 (your decision): Blaine is an overworld gym at the Craters, not the
> Nether.** Towns are hand-built from now on, so a structure generating for free in a
> dimension is no longer a reason to put a gym there. Placements are in `data/towns.json`
> and [`TOWNS.md`](TOWNS.md). The table below is updated; section 4.1 says what the Nether
> needs instead. The League follows the same logic and is **proposed** in the overworld,
> which is not yet decided (4.2).

**The Kanto series order** comes from RCT `requiredDefeats` in the loaded trainer files.
Each gym's generation biome comes from its structure. No structure generates in the
overworld, because every overworld chunk is written by the export, so every overworld gym is
hand-placed.

| Step | Leader | Structure generates in | Where it goes | First needed |
| --- | --- | --- | --- | --- |
| 1 | Brock | plains | overworld, hand-placed: Viltri Plateau | start |
| 2 | Misty | lukewarm_ocean | overworld, hand-placed: Lake Viltri north shore | early |
| 3 | Lt. Surge | savanna_plateau | overworld, hand-placed: Tri Peaks shelf below Mt Vessu (1688, 1410) | |
| 4 | Erika | flower_forest | overworld, hand-placed: Peak Pond Hollow | |
| 5 | Koga | swamp | overworld, hand-placed: Glacier Foot Fields | |
| 6 | Sabrina | dark_forest | overworld, hand-placed: Tilpey North Shore | |
| **7** | **Blaine** | crimson_forest (Nether copies to be disabled, 4.1) | **overworld, hand-placed: the Craters** | after crossing the major river |
| 8 | Giovanni | `#has_structure/ancient_city` (deep dark) | overworld, hand-placed: South Strand | |
| 9–13 | Lorelei, Bruno, Agatha, Lance, Champion Blue | end_highlands | **proposed: overworld, hand-placed at the Rift's head (4.2)**; today's plan: End, outer islands | end of Victory Road |

### 4.1 What the Nether needs now that Blaine has left it

**Nothing on the critical path needs the Nether.** It becomes optional. Four things follow:

1. **Disable Blaine's generated copies.** Cobbleverse's `cobbleverse:blaine` structure set
   (COBBLEVERSE-DP-v31, spacing 25, separation 10, crimson forest) would place dozens of copies
   in a 10240 Nether. Each carries the `kanto_blaine` RCT spawner and a healer. RCT still
   requires Sabrina first, but after badge 6 a player could beat Blaine in any Nether copy and
   skip the Craters.
   - **The fix** is an overlay datapack override, applied before anyone enters the Nether or
     it is pregenerated. It overrides either the structure set or the structure's biome
     list.
   - **Not verified:** which override form 1.21.1 accepts without a worldgen error. That is an
     experiment. The exact file path inside the zip has to be read from it, not assumed.
2. **Give it a reason to visit, or accept that it has none.** The Nether still holds Moltres
   and the four Ruin shrines (16 and 67 attempts in the shared border), fortresses and blaze
   rods, and Nether materials.
   - **Recommended:** keep it as optional exploration opened by obsidian, which fits
     mid-game.
   - **If the End portal room asks for eyes of ender,** blaze powder keeps one real reason to
     go.
3. **Change the audit's required list.** `dimension_audit.py --require-classes` must stop
   requiring `cobbleverse:blaine`, or the Nether audit fails by design once the copies are
   disabled.
4. **Change the guidance plan.** No gym waystone or marker in the Nether; markers there only
   for legendaries, if any.

The shared-border recommendation (section 2) and the portal-clamp note are unchanged.

### 4.2 The League: in the overworld (decided 2026-09-14)

**Decided (yours, 2026-09-14):**
- **The League** is an overworld town at the head of the Rift.
- **The End's League copies** (`cobbleverse:kanto_league`) are disabled.
- **End access is post-game.**

The consequences below now apply. The override that disables the copies is the same
unverified experiment as Blaine's (4.1).

The same reasoning moves the League.
- **The generated structure** is `cobbleverse:kanto_league` (end_highlands; 111 × 159 × 120,
  so large), and the End's 26 candidates are only attempts.
- **A hand-placed League** at the head of the Rift puts Victory Road on the overworld critical
  path. `data/towns.json` has a 196-block square site.

**If you accept it:**
- the End's `kanto_league` copies need the same override as Blaine's;
- the End portal room moves from after Giovanni to post-game;
- the End becomes post-game: the Necrozma towers, Eternatus, and the Rayquaza question.

**If you keep the League in the End,** the overworld site becomes the Victory Road terminus
and the portal room.

### When a player first has to go

- **Nether:** after badge 6. They need obsidian, so a diamond pickaxe or lava casting, which
  fits mid-to-late game. Nothing stops an earlier trip, but RCT will not let Blaine be
  battled before Sabrina.
- **End:** after badge 8.

### Is the critical path coherent? Yes, with two authored pieces and two risks

**1. End access has to be authored.**
- **No stronghold can exist in the world.** Stronghold rings start 1280 blocks from 0,0.
  Every ring position inside the border lands on a chunk the export writes, and a written
  chunk never generates a structure. Every position outside the border is unreachable. The 62 starts the server made in the current margin include
  no stronghold.
- **Eyes of ender therefore have nothing to find.** Predicted, not verified.
- **The fix is a hand-built portal room** on the overworld critical path after Giovanni. It
  can use real end portal frames the player fills, or a pre-lit portal.
- **This reuses the Nether requirement naturally.** Eyes need blaze powder, so if the room
  asks for eyes, the gym-7 Nether trip (fortresses generate normally) supplies the rods.
  Nether before End stays true without a lock.

**2. Guidance to Blaine and the League.**

*Superseded 2026-09-13.* Navigation is waystone-only, with map markers
(`NAVIGATION.md`). Locator items are removed everywhere, including these dimensions. The
gyms generate from the carried seed, so their positions are fixed:
- record them once from the audit candidates;
- give each a waystone and a marker in the dimension it is in.

The generator already takes a `dimension` per waystone.

**3. Risk: the outer islands need a gateway.**
- **The League is at least 1024 blocks out.** Every candidate lies on the outer islands.
- **A gateway should appear.** Cobbleverse's `cobbleversenoenderdragon` datapack sets the
  dragon's health to 0 every tick, so the dragon dies on arrival. The dragon's death should
  create the first end gateway and the exit portal. Not verified.
- **Without a gateway, players must bridge about 1000 blocks.** Verify this on the first
  End boot.

**4. Risks to sequencing:**
- **Moltres and the four Ruin shrines** are reachable from the first Nether trip at gym 7,
  before the League. Whether their altars need anything later is not verified (LumyMon is
  closed source). If they should wait, gate them with the encounter items, not the
  structures.
- **Necrozma's towers and Eternatus** open with End access at the League, and Mew is
  champion-gated in its own template. That is coherent.
- **A shiny level-100 Rayquaza.** The loaded function `cobbleverse:spawn_rayquaza`, which
  `end_dimension` schedules, spawns one at End 0,70,0, the arrival platform. A player
  reaching the End for the League meets it. Decide whether to keep, gate or remove it
  (datapack override) before the End is opened.
- **Giovanni's gym** is keyed to the deep-dark biome tag. It is overworld and hand-placed,
  so no locator finds it. It needs authored guidance, like every overworld gym.

## 5. What is decided, and what is still yours

| Question | State |
| --- | --- |
| Overworld border 10240, centre 4096,4096 | decided |
| Nether and End borders | proposed: the shared border (−1024…9215), no extra mechanism |
| Pregen method: Chunky, or a forceload script | **your call** |
| Border and pregen timing | decided: after the re-export |
| End access | **decided 2026-09-14: post-game.** The authored portal room (eyes or pre-lit) opens after the Champion, not after Giovanni |
| End League copies (`cobbleverse:kanto_league`) | **decided 2026-09-14: disabled** (override form still an experiment) |
| Blaine's gym | **decided 2026-09-14: overworld, the Craters**; Nether copies to be disabled (4.1) |
| The League | **decided 2026-09-14: overworld, at the Rift's head** (4.2); End copies to be disabled, End access post-game |
| Rayquaza at the End spawn | **your call** |
| Soft limit for deep-Nether portals | not proposed unless the clamp proves a problem |
