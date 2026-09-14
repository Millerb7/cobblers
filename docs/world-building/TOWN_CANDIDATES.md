# Town candidates: buildability, Kanto order, gym 1 counters

**Status: assessment only (2026-09-14). No town is placed.**
- **Candidates:** the eleven green boxes on `land_8k_16_eroded_annotated.png`. One is labelled
  Pallet Town.
- **Sites:** measured with `tools/find_sites.py`, which finds the largest square inside the box
  under a slope limit. Ground above y199 is excluded, because clipped summits read as flat.
- **Travel:** a terrain-weighted route cost between box centres. On 8-block cells a step costs
  its length × (1 + 0.25 × climb); slopes over 35° cost ×4; sea and painted lakes cost ×2.5,
  as a boat.

## 1. Buildability

| Box | Centre | Sub-region | Area km² | Ground y (median) | Flat ≤5° | Below sea | Best square ≤5° | Best ≤8° | Verdict |
| --- | --- | --- | ---: | --- | ---: | ---: | --- | --- | --- |
| **A Pallet Town** | 1377, 5401 | Pallet Meadows | 0.08 | 56–118 (102) | 23% | 2% | 69² at y113–117 | 91² | **Tight.** Small and sloped (mean 10°). A village fits on the upper bench at (1434, 5286), not across the box |
| B | 1495, 7428 | Sunset West (island) | 0.54 | 85–147 (122) | 71% | 0% | 235² at y111–119 | 396² | **Best site on the map.** Needs a sea crossing |
| C | 3885, 6652 | South Strand | 0.49 | 14–118 (71) | 20% | **43%** | 124² at y109–115 | 179² | **Partial.** Half the box is sea; the town fits on the ridge at (3647, 6497) |
| D | 1818, 3409 | Viltri Plateau | 0.48 | 108–142 (129) | 81% | 0% | 162² at y130–133 | 315² | **Good**, the largest mainland site |
| E | 2875, 2475 | Foothill Woods | 0.20 | 101–123 (108) | 74% | 0% | 157² at y105–109 | 232² | **Good** |
| F | 2070, 1074 | Mt Vessu | 0.16 | 174–200 (200) | 68% | 0% | none below y199 | 36² at y183–186 | **Only on the clipped y200 summit plateau** (~0.1 km², flat because it is cut off). Buildable, but artificial, at the top of the terrain band |
| G | 4614, 951 | (sea) | 0.23 | 19–102 (49) | 9% | **65%** | none | none | **Not buildable.** The box sits mostly in the sea off the north coast |
| H | 7253, 1475 | South Pine Isle (island) | 0.24 | 83–125 (113) | 69% | 0% | 131² at y114–119 | 231² | **Good.** Needs a sea crossing |
| I | 4823, 2554 | Glacier Foot Fields | 0.20 | 115–139 (127) | 80% | 0% | 110² at y134–137 | 211² | **Good** |
| J | 5905, 3563 | Tilpey North Shore | 0.21 | 52–105 (88) | 37% | 8% | 112² at y93–95 | 131² | **Moderate.** The painted lake (y77) takes its lower edge. Build on the terrace at (6167, 3479) |
| K | 5980, 5035 | Craters North-West Rim | 0.11 | 99–123 (109) | 71% | 0% | 152² at y105–111 | 200² | **Good** |

**Summary:**
- **Buildable:** B, D, E, H, I, K.
- **Usable with care:** A, C, J.
- **Only on a clipped summit:** F.
- **Unusable:** G.

## 2. Can the boxes carry Brock → Misty → Surge → Erika → Koga → Sabrina → Blaine → Giovanni?

### Geography alone

**The shortest eight-gym route from Pallet is a clockwise loop:**

**A** → D → E → F → G → I → J → K → C (route cost 18,249)

**Shape of the route:**
- It runs north up the west, east along the north, and down the east.
- It finishes on the south coast about 3,300 cost units from Pallet.
- The next-best orders are that loop reversed, or with F and E swapped.
- **The two islands (B, H) never enter the shortest routes.** They are natural optional or
  post-game towns.

Nearest-neighbour costs along the loop:

| Leg | Cost |
| --- | ---: |
| Pallet → D | 2,289 |
| D → E | 1,589 |
| E → F | 1,976 |
| F → G | 3,149 |
| G → I | 1,963 |
| I → J | 1,689 |
| J → K | 2,437 |
| K → C | 3,153 |

### Laid against Kanto

| Order | Leader (type) | Loop box | Fit |
| ---: | --- | --- | --- |
| 1 | Brock (Rock) | **D** Viltri Plateau | **Good.** The first town north of Pallet, on an upland plateau under the massif, as Pewter sits north of Pallet |
| 2 | Misty (Water) | **E** Foothill Woods | **Poor.** No water within ~1,100 blocks; the nearest are Lake Viltri, the pond west of Mt Clay and Shrew Lake |
| 3 | Lt. Surge (Electric) | **F** Mt Vessu summit | **Plausible** (an exposed peak), but the site is the clipped y200 plateau |
| 4 | Erika (Grass) | **G** north coast | **Fails:** the box is in the sea |
| 5 | Koga (Poison) | **I** Glacier Foot Fields | **Good.** On the edge of the Marsh Country, a short walk from Marshy Marsh |
| 6 | Sabrina (Psychic) | **J** Tilpey North Shore | **Good.** The central hub where the glacier meets the lake, as Saffron is Kanto's centre |
| 7 | Blaine (Fire) | **K** the Craters | **Very good** |
| 8 | Giovanni (Ground) | **C** south coast | **Good.** Beside the Rift's foot and the badlands, and a short walk from Pallet, as Viridian's gym sits next to Pallet and opens last |

**The second half of the loop matches Kanto closely; the first half does not.** Neither the
geography nor the chain has to give wholesale. Two boxes need to move:
1. **G moves inland** onto the Northern Downs, around (4700, 1500) by the Peak Pond Hollow
   forest, for Erika. It is still on the loop between F and I.
2. **Misty needs water at the second stop.** Either:
   - move E ~500 blocks west to the shore of Lake Viltri, which keeps the order D → E′ → F; or
   - shift the head of the route to run D → Shrew Lake (a new box, ~1,100 east of D) → E → F.
     That lengthens the first leg but gives Misty a real lake.

**With those changes, the Kanto chain holds as Cobbleverse ships it.**
- Blaine is at the Craters and Giovanni is back near Pallet for the finale, with the Rift (a
  Victory Road candidate) next to C.
- If the boxes stay where they are, the other lever is the chain itself. `requiredDefeats` is
  datapack JSON the campaign overrides anyway (`NAVIGATION.md` §5).
- **The chain is the costlier thing to bend.** The leaders' teams follow the Kanto level curve
  (Brock is levels 16–20), so reordering means retuning teams.

**Conflict to decide:**
- [`DIMENSIONS_AND_BORDERS.md`](DIMENSIONS_AND_BORDERS.md) places gym 7 (Blaine) in the Nether.
- Box K suggests an overworld Blaine at the Craters.
- Both cannot be true; the Craters fit better on the route.

## 3. Gym 1 is Rock: can the routes near D offer a counter?

**Brock's team** (`COBBLEVERSE-RCT-DP-v20`, `kanto_brock`):

| Pokémon | Level | Type | Notes |
| --- | ---: | --- | --- |
| Geodude | 16 | Rock/Ground | Sturdy; Rock Tomb, Rock Throw, Bulldoze, Protect |
| Bonsly | 16 | Rock | Rock Head, Focus Sash |
| Cranidos | 18 | Rock | Mold Breaker; Take Down, Rock Tomb, Rock Smash |
| Onix | 20 | Rock/Ground | Sturdy, Rocky Helmet; Rock Slide, Bulldoze |

**What the team demands:**
- **Water and Grass hit Geodude and Onix 4×.** Fighting, Ground and Steel hit all four 2×.
- **Sturdy and the Focus Sash** mean a one-hit plan fails; multi-hit moves or chip damage
  matter.
- **Onix's Rocky Helmet** punishes contact moves.

**The routes from Pallet to D** are Pallet Meadows, West Shore, the Viltri Plateau, Lake Viltri
Hollow, the River of Shrews Vale and Shrew Lake Shores. They are painted plains, sunflower
plains, forest, old-growth birch forest, flower forest and cherry grove, with painted lakes at
Lake Viltri and Shrew Lake.

**Early counters the pack's spawn pools already place in those biomes.** The count is species
that are super-effective against Rock, can spawn at level 20 or below, and are not tied to a
structure:

| Type | Species | Examples (lowest level) |
| --- | ---: | --- |
| Water | 56 | Lotad 1, Wooper 1, Tympole 1, Magikarp 1, Feebas 1, Surskit 2, Chewtle 3, Barboach 4 (many are fishing or water spawns: the painted lakes provide the water) |
| Grass | 39 | Seedot 1, Hoppip 1, Sunkern 1, Fomantis 1, Gossifleur 1, Budew 3, Cottonee 3, Petilil 3, Cherubi 4, Shroomish 5 |
| Fighting | 17 | Makuhita 1, Tyrogue 1, Machop 6, Mankey 6, Timburr 6, Crabrawler 9; Riolu 4 (rare) |
| Ground | 18 | Wooper 1, Diglett 2, Nincada 2, Barboach 4, Drilbur 8, Rhyhorn 10 |
| Steel | 8 | Bronzor 5, Aron 8, Magnemite 8 |

**Verdict: yes, plausibly and in depth.**
- **Water and Grass**, the 4× answers to Geodude and Onix, are the deepest pools.
- **A curated route needs only a few of them.** Recommended picks: one fishable Water species at
  Lake Viltri, one Grass species on the Viltri Plateau, and one Fighting species with multi-hit
  or chip options for Sturdy.

**Not verified in game.**
- These are spawn-file entries, and many carry time or sky-light conditions.
- The curated encounter lists, still empty, will decide what actually spawns.
