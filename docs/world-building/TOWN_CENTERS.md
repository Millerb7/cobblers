# Town centres: what stands on the plaza

**Status: proposal, 2026-09-25, for the owner to react to.** Nothing here is built, authored as data, or
tested. It answers the playtest note of 2026-09-25: *"begin to craft an idea for town centers since as of
now its just big rectangles with nothing on them."*

**What is on a plaza today** (`derived/towns/<town>_plan.json` `plaza`, `data/placements.json`):
- the paving;
- flush lamps every 27 blocks from the rect's corner (`tools/town_plan.py`, `LIGHT_REACH` 14);
- the waystone;
- in Brock's and Misty's towns only, a row of market traders one block over the paving (`data/traders.json`).

The hometown has no plaza. Its centre is the CobbleTowns Pallet sign at the crossroads (placement
`hometown_sign`, kind `town_centre`, 13×13, `verified` 2026-09-16).

## 1. What a town centre is for

A player arrives on the plaza, by waystone or by road, before anything else. The centre has six jobs:

| Job | What it means on the ground |
| --- | --- |
| Orientation | From the arrival point you can see where the Centre door, the Mart door, the gym and the road out are, and the board names them. |
| Arrival | Waystone travel lands you here, so the stone keeps a clear pad and nothing stands in the way of walking off it. |
| The leader's presence | The gym's type is announced on the square, even where the gym itself is out of sight (Koga, Blaine). |
| Meeting | Friends wait for each other here: seats, shade and something to look at, out of the walking lines. |
| NPCs | Marked spots for the gym guide, quest-givers and the traders, so later actors have a home that does not block anything. |
| Identity | One piece you remember the town by, built from the town's own materials. |

### The elements (reusable)

| Code | Element | Footprint | Rule |
| --- | --- | --- | --- |
| **W** | Waystone arrival pad | stone + 3×3 pad on its facing side | Already placed. Nothing within 2 blocks, and the pad stays open. |
| **N** | Notice board | 3×1, 2–3 high | Beside the pad, facing it. Carries the town name, the roads out with their compass direction (read from `data/signposts.json`), the Centre and Mart arrows, and the gym line ("Leader Brock: Rock"). |
| **C** | Centrepiece | S 5×5 · M 7×7 · L 9×9 to 11×11 | One per town, tied to its identity (section 2). It must never hide what the plan's `reading` promises can be seen from the square. |
| **E** | Gym emblem plinth | 3×3, 2 high, with a sign | Stands at the mouth of the street toward the gym. Shows the badge's shape in blocks and the leader's name. |
| **t** | Stall | 3×2: counter plus awning | Only where a trader stands. The trader stays behind the counter, and the counter faces the paving. |
| **b** | Bench pair | 3×1 each | Along the edges, facing the centrepiece or a view. Never in a door apron. |
| **p / Y** | Planter / tree pit | 1×3 / 3×3 | For shade and softness. Leaves must be placed `[persistent=true]`, or leaves set by command decay (vanilla behaviour). |
| **x** | NPC spot | 1×1, recorded, empty | Reserved for later actors (`data/scenes.json`, dialogue NPCs). |
| **V** | Rail / viewpoint | 1 wide | Only on plazas that end at a drop (Surge, the Rift rim post, the Tableland stop). |

### Arrangement rules (any rectangle)

1. **Keep-clear mask first.** The generator computes it from the plan and refuses any piece that lands on
   it:
   - the waystone and its pad (2 blocks round the stone);
   - every street mouth, at its width plus 2, projected 6 blocks into the plaza;
   - a door apron 5 wide by 4 deep in front of every Centre, Mart or gym door that opens onto the plaza;
   - every flush lamp cell and the cell above it;
   - every trader position and the cell in front of it.
2. **Desire lines stay walkable.** A 3-wide straight corridor joins every pair of mouth, door apron and
   pad. Pieces go in the bays these lines leave. Where two streets cross the plaza (Sabrina, Giovanni),
   the crossing itself stays flat: its centrepiece is flush in the paving or stands in a corner bay.
3. **Zones by distance from the edge.**
   - **Edge band** (outer 3 blocks): benches, boards, stalls, planters, all 2 high or less.
   - **Field**: walking.
   - **Core**: the centrepiece, with a 3-block walk ring round it.
4. **Size classes by the short side.**

   | Short side | Class | What it gets |
   | --- | --- | --- |
   | under 20 | small | No core piece: an edge piece plus N and b. |
   | 20–35 | medium | C at S or M, E, N, 2–4 b, 1–2 Y. |
   | over 35 | large | C at L, plus planted quarters and shade. |
5. **Coverage cap.** Furniture covers at most 15% of the plaza's cells, and at least 70% stays open
   paving.
6. **Height.** Nothing in the edge band is taller than 2 blocks, except lamps and trees. The centrepiece
   may rise only where no promised sightline crosses it:
   - Brock's gym on the knoll;
   - Sabrina's axis;
   - Blaine's causeway;
   - Giovanni's gate.
7. **Spawn-neutral by default.** The blocks below are spawn conditions in `data/spawn_block_policy.json`
   (listed in `data/spawn_blocks.json`). A template that contains one fails validation unless the policy
   whitelists it for that scope. Each is a deliberate owner call per town, never a default:
   - water, flowers, leaves, a bell, a lightning rod, rails;
   - iron, amethyst, magma, lava;
   - vanilla concrete (use `moarconcrete:<colour>_concrete_texture`, as the donors already do).
8. **Light.** Lanterns on posts or on the piece itself, never `minecraft:light`. Lights are re-planned
   after the centre stands (section 3).

## 2. Per-town concepts

Sizes are inclusive block counts, from `derived/towns/*_plan.json`.

**Palette method.** Every palette names only vanilla 1.21.1 ids and the two mod-id families the repository
already uses (`moarconcrete:*_concrete_texture` and `rechiseled:*`). Mod furniture (Handcrafted benches,
Beautify lamps and trellis, Pokéblocks figurines, CobbleFurnies) is named by family only. Take its exact
ids from the jar in Axiom when the kit is authored; `tools/kit.py index` checks the namespaces. **Not
verified:** that Pokéblocks ships a figurine of any particular Pokemon.

**Sketches:** north is up. One character is about 3–4 blocks. Positions are rough; the generator places
exactly.

Legend:
- `L` lamp;
- `W` waystone;
- `N` notice board;
- `E` emblem plinth;
- `C`/`c` centrepiece;
- `t` stall;
- `b` bench;
- `Y` tree pit;
- `x` NPC spot;
- `:` desire line;
- `>` a door or a mouth.

| Town | Plaza | Centrepiece | Emblem (badge) | Palette (vanilla unless noted) |
| --- | --- | --- | --- | --- |
| Hometown | none (crossroads, sign at 1456,5287) | Keep the Pallet sign. Add a "first step" stone at the Route 1 mouth. | none | oak, white fences, grass path, flowers (garden scope) |
| Brock | 41×41 y138 stone_bricks | **Onix run**: a low segmented stone serpent (humps no more than 3 high) curling across the SE quarter. Its head points up the gym lane to the knoll. | Boulder (grey octagon) at the gym_lane mouth | stone, polished_andesite, cobblestone, tuff, calcite, dripstone_block, stripped_birch_log benches, birch tree pits, `rechiseled:` stone variants |
| Misty | 33×33 y107 prismarine_bricks | **Starmie fountain**: a five-pointed basin with a centre jet. Needs `minecraft:water` whitelisted for the plaza (today only gym2 houses). | Cascade (blue drop) at the promenade_link mouth | prismarine, dark_prismarine, sea_lantern, smooth_quartz, `moarconcrete:light_blue_concrete_texture` |
| Surge | 33×15 y174 exposed_copper | **Relay pylon and sighting post**: a copper lattice mast at the east end, and a brass pointer on a plinth aimed at the array (1928,1248) and Vessu's summit. Benches along the west rail face the drop. | Thunder (gold star) at the wall lane | waxed_* copper (cut, grate, bulb), polished_deepslate, iron_bars, chain, end_rod. The mast is crowned with end_rod, not lightning_rod (a spawn condition). |
| Erika | 53×61 y110 moss_block (a green) | **Formal garden**: four hedged parterres, a central pergola with seats and shade, and one cherry tree. It relies on the garden scope the policy already grants to flowers and leaves. | Rainbow (flower) at the gym's garden gate, north | moss_carpet, azalea, leaves `[persistent=true]`, flowers, dark_oak or bamboo pergola, mossy_stone_bricks walks |
| Koga | 33×25 y117 mossy_cobblestone | **The dry well**: a roofed well in mud brick with a mangrove roof ("the fen water is not for drinking"), plus three stone lanterns on the west edge that line up on the boardwalk's start. A hint, not a signpost. | Soul (pink heart) turned toward the fen | mud_bricks, packed_mud, mangrove_planks/roots/log, bamboo, purple_terracotta, verdant_froglight |
| Sabrina | 33×33 y94 polished_diorite | **Flush mosaic**: the crossing stays flat, with a concentric "eye" laid into the paving. Four low quartz plinths stand in the corner bays. **Option:** floating quartz stones as `block_display` entities, which needs a proof. | Marsh (gold rings) at the axis's north mouth | smooth_quartz, quartz_bricks, quartz_pillar, purpur_block, calcite, amethyst_block (whitelisted in the overworld), end_rod |
| Blaine | 29×29 y107 polished_basalt | **Ember brazier**: a raised blackstone basin with campfires, south of the causeway line, so the view east to the gym stays open. Plus a quiz board (Blaine's riddles, flavour only). | Volcano (flame) at the causeway mouth | polished_blackstone(_bricks), gilded_blackstone, smooth_basalt, campfire (raised: it burns feet), stripped_crimson_stem, `moarconcrete:orange_concrete_texture`. **No** magma or lava. |
| Giovanni | 31×23 y112 terracotta | **Gate of Eight**: eight standing stones in an arc off the diagonal foot street, each in its gym town's stone, the eighth beside the gym. This is Victory Road's badge check, built as flavour. | Earth, on the eighth stone | terracotta (brown/orange/red), coarse_dirt, rooted_dirt, packed_mud, dripstone_block, plus one sample block from each earlier town |
| League | 29×16 + 17×16 forecourts y88 polished_tuff; waystone 3634,2494 | **Torch walk**: two pairs of tall braziers or pillars on the terraces, framing the ramp cut (x3651–3661), and a name monument on the west terrace. | the League's crest (to design) | polished_tuff, tuff_bricks, chiseled_tuff, gold_block trim, campfire or lantern tops |

### Sketches

```
BROCK 41x41 (1 ch ~4)   north_avenue ^            MISTY 33x33 (1 ch ~3)  north_avenue ^
 west_lane <  L t t t t t t L . . .               L . t t t t t . . L .
              . . . N W : . . . . .   < Mart     . . . N W : . . . . .   (Centre NW,
 Centre door> b . . . : . . . . . .              . b . . . : . . . b .    Mart NE,
              : : : : : : : . Y . .              . . . c c c c . . . .    both off
              . Y . . . . . . . . .   west_street> : : c c c c : : : .    the rect)
              . . . . . . . . c c .              . . . c c c c . . . .
              L . . . . . L c c . E > gym_lane   . Y . . : . . . . Y .
              . . b . . . c c . . .              L . . . : . . L . . .
 approach_sw >. . . . . . . . . . .              . b . . : . . . : : < shore_approach
                                                 . . . E : . . . . . .
                                                  promenade_link v (gym, south)
```
Brock: the trader row at z3603 crosses the north_avenue mouth. The trader at (1756,139,3603) stands on
the avenue's centreline, three blocks in front of the waystone. Misty: the trader at (1619,108,2799)
stands diagonally against the waystone (1620,2800), inside the avenue mouth. Both break rule 1. The fix
is to shift each row one bay sideways (a `data/traders.json` edit for its owner, not made here).

```
SURGE 33x15 (1 ch ~3)                    ERIKA 53x61 (1 ch ~5)   gym (door S) v
drop  W . . b . . b . . . c > Centre     . . . . . E . . . . .
 (V)  . . . . . . . . . c c : wall_lane  . p p Y . : . Y p p .
 rail . b . . . x . . . . N . to gym     . p p . . : . . p p .
      . . . . . . . . . . . .    W(off)> : : : : : C : : : : :
      lip_walk ^ (from the S)             . p p . . : . . p p .
      view NE -> summit, array            . p p Y . : . Y p p .
                                         . . . . . : . . . . .
                                              Mart (door N) ^
```
Erika: the ring road is outside the green. The waystone is off the plaza, at its west corner (4276,1554).

```
KOGA 33x25 (1 ch ~3)                     SABRINA 33x33 (1 ch ~3)  gym on axis ^
post_road  . . . . . W N . . . .          . c . . . E . . . c .
(W edge    L x . . . . . . L . .          . . W N . : . . . . .
 all open) Y . . . . c c . . b .          . . . . . : . . . . .
 fen, gym  . . . . . c c . . b .  cross > : : : : :(m): : : : : < cross
 WSW  ->   Y . . . . . . . . t t          . . . . . : . . . . .
           . . . . . . . . . t t          . c . . . : . . . c .
                                                     Route 7 v
```
Koga's stalls are future: the market yard waits for the badge-gated stock. `(m)` is the flush mosaic.

```
BLAINE 29x29 (1 ch ~3)                   GIOVANNI 31x23 (1 ch ~3)
  W N . . . . . . . .                     to League < W . . . . . . . . .
  road : : : : : : : : E > causeway (gym) gym (NW) ^ : N . . . . . . . .
  . . . . . . . . . .                     . . : . . . . . . . .
  . b . . C C C . . .                     s . . : . . . . . . s
  . b . . C C C . . .                     . s . . : : : : : : < foot_street
  . . . . . . . . . .                     . . s . s . s . s . .
  mound (lee), houses S/W                 (s = standing stone; arc of 8)
```

```
HOMETOWN (no rect)                        LEAGUE apron
        route_north ^ (Route 1)           [ W  b  T  N ][ramp x3651-3661][ T  b ]
   Centre  >  :  <  Mart                  [ west 29x16 T ]    open       [east 17x16]
 houses < : [Pallet sign 13x13]            T = brazier pair, facing the ramp mouth
            W at NE corner of the sign
            :  . . . > lab_lane (z5318, Oak's lab east)
```
Hometown: hold everything past a bench pair and the "first step" stone until the Pallet relocation is
decided (`docs/STATE.md`, open).

### Major towns and rest stops (one line each)

| Place | Plaza | Idea |
| --- | --- | --- |
| Sunset West | 25×29 y64 polished_granite | A hull on trestles (an upturned boat in oak), net racks, and a tide-and-charter board. |
| Northlight | 41×31 y116 polished_deepslate | A weather mast (fences and chain; not a daylight_detector, which is a spawn condition), an aurora canopy of light-blue glass, and benches of packed or blue ice. |
| Mining Town | 41×24 y137 cobblestone | A headframe winding wheel (dark oak, chain), a static ore cart built of blocks (no rails), and sample plinths of raw_iron, raw_copper and raw_gold blocks (not ore). |
| Displaced City | 16×16 y46 | Small class. The summit cairn (`displaced_cairn`) is already the centre; add a ring of benches and an altitude plaque that is wrong by a mountain. |
| Tea town | 29×27 y114 mossy_stone_bricks | A tea pavilion with low tables, a cherry tree pit and stone lanterns, and a giant teacup sculpture for Poltchageist (in `moarconcrete:lime_concrete_texture`). |
| Gorge hamlet | 31×29 y113 cut_sandstone | The well its plan's `reading` already promises. **No well placement exists** (checked in `data/placements.json`). |
| Tableland, Rift rim, Merian | 27×21, 27×9, 69×7 | Small class: a board, benches facing the view, and the rail already built at the rim post. |

## 3. How it is built here

**Data** (`data/placements.json`, owned by world-content-dev). Each settlement's `plan` gains a
`centre` block. Positions are **offsets from the plaza rect's minimum corner**, so a replanned plaza
carries its centre, or the generator refuses:

```json
"centre": {"class": "large", "coverage_max": 0.15,
  "pieces": [{"id": "gym1_onix", "role": "centrepiece", "prefab": "cobblers:kits/props/plaza_gym1/onix_a",
              "at": [26, 22], "facing": "east"},
             {"id": "gym1_board", "role": "notice", "kind": "generated_board", "at": [16, 7], "facing": "south"}],
  "npc_spots": [{"id": "gym1_guide", "at": [37, 30], "for": "gym guide (unwritten)"}],
  "spawn_scope": "plaza_centres"}
```

**Kits** (`kits/structures/prefabs/props/`):

| Source | Pieces | Licence / commit |
| --- | --- | --- |
| Hand-built in Axiom, imported by `tools/kit.py import --kind props --set plaza_<town>` | the signature centrepieces | `original`. Needs a new `kits/PROVENANCE.json` record for `prefabs/props/**`. |
| Generated by the generator itself (as `tools/route_events.py` writes signs) | benches, board, planter, tree pit, emblem plinth base, stall awning, lamp post | `generated`. The sign text is written with the existing `signposts.py` / `route_events.py` sign helpers. |
| Placed by resource id, never committed | Repurposed Structures meeting points (`villages/{birch,oak,badlands}/houses/meeting_point_*`, local copies under `kits/structures/incoming/`); cobblemon-additions `bca:default/paths/path_well_cross_road` (licence conflicting, so place only); vanilla `minecraft:village/*/town_centers/*` wells | Installed packs. Bells and water inside them need the spawn policy. |
| Committed MIT | the CobbleTowns Pallet `town_centers/sign` (already the hometown's centre) | MIT, recorded |

**Generator: `tools/plaza_centre.py`** (new; standalone CLI).
- **Reads:**
  - the plan's `centre`;
  - `derived/towns/<town>_plan.json` (plaza rect and `y`, lamp cells, street polylines for the mouths);
  - the anchors' door cells (the entrance rule `tools/place_town.py` already applies);
  - the waystone;
  - `data/traders.json` (read only).
- **Ground** is the plan's plaza `y`, which `town_plan.py` took from `tools/ground.py`. It never reads a
  world (`tests/test_ground_rule.py` must cover the new tool).
- **Fails closed** on any of:
  - a piece on the keep-clear mask;
  - a piece outside the rect;
  - coverage over the cap;
  - a missing prefab;
  - an unloaded namespace;
  - a spawn-condition block outside its whitelisted scope.
- **Emits:**
  - `build/datapacks/cobblers_centres` (`cobblers:centres/<town>`, through `tools/function_limits.py`);
  - `derived/towns/<town>_centre.json`, the model of every block it writes.

**Re-application.** A new step **R13 "plaza centres"** in `tools/reapply.py`:
- **After R9F.** Donors are placed whole with air margins and erase what stands in them (Sabrina's store
  erased a signpost once).
- **Before R16.** The lights must be planned with the centre standing.

`prepare` already fails closed on a pack with no step. **Not edited here:** another session holds
`tools/reapply.py`.

**Checks** (written by test-author, not by the implementer):
- `tools/town_audit.py` must read the centre model. Its `blocked_above` road check would otherwise report
  every piece as "a block standing on the road".
- `tools/light_plan.py` must model the centre's blocks, so no lantern is planned inside a piece and the
  shaded cells are counted.
- A verify pass compares the world with the model (reading a world to *check* is allowed).

## 4. First prototype and the owner's decisions

**Prototype: Brock's town (gym1).**
- It is the first gym square players see and the largest empty one (41×41).
- It is already laid out on the disposable world and on staging, with traders on it. That tests the stall
  row and the keep-clear mask against real positions.
- Its palette is plain vanilla stone, and it needs no spawn-policy exception beyond birch leaves in tree
  pits (garden scope).
- Scope: one hand-built centrepiece (the Onix run), the generated pieces, R13, the audit and light
  updates. Then fly it in game before any second town.

**For the owner to decide:**
1. **Direction.** Should each town get a signature centrepiece (this proposal), or stay calm and civic
   (benches, trees, a board) with identity in materials only?
2. **Spawn draw on plazas.** Allow water (Misty), a bell, flowers and leaves on plazas (a new policy scope
   `plaza_centres`), or keep every plaza spawn-neutral?
3. **The traders' rows in Brock's and Misty's towns** stand in the avenue mouth, against the waystone.
   Move them one bay over? That is a `data/traders.json` change.
4. **Who builds the signature pieces?** You in Axiom, imported by `kit.py`, or authored as generated block
   lists (like the Northlight observatory earthwork)?
5. **Sabrina's floating stones** (`block_display` entities). They are entities, re-applied like scene
   props, and not proven. Try them or drop them?
6. **A "hall of names" plaque** by each emblem, gaining each player's name on their first win. It needs an
   experiment: a sign written per player from the win advancement is unproven. Keep it as an idea or drop
   it?
7. **Hometown.** Wait for the Pallet relocation decision?

## Findings made while writing this (not fixed here)

- **Traders.** Brock's and Misty's trader rows break the arrival clearances, as described under the
  sketches.
- **Surge's copper.** His plaza is paved `minecraft:exposed_copper`. In vanilla, unwaxed copper oxidises
  under random ticks, so the square will drift to weathered and oxidized, and `town_audit` expects
  `exposed_copper`. Not observed here. The waxed variant, `waxed_exposed_copper`, would hold.
- **The gorge hamlet's well.** Its `reading` promises "a well in the middle"; no placement builds one.
