# Heaven's Arena in the Windward Deep: the geometry and what it costs the city

**Status: proposal, 2026-10-01. Nothing here is a decision the owner has taken.** The owner's request:
"The pit holds 196 buildings and nine stair towers. I want a HEAVEN'S ARENA tower in it — tiers climbing
upward, champions at the top, a player challenges them for their place. Endless fights, real money. Tell
me what the tower costs the existing city: what comes out, what stays, whether they coexist or one
replaces the other."

This document answers the cost and the shape only. **It does not design the fights.** Whether `rctmod`
can hold an endless ladder, repeatable battles, generated teams and per-player "who holds tier 7" is
being researched in parallel; every place where the geometry depends on that answer is marked
**[fight-system]**.

Written without a shell: `tools/deep_city.py` was **not run**. Every figure below is either read from a
file (cited by `path:line`) or arithmetic on a circle, and section 7 lists what only a run can settle.

Sources: `data/deep_city.json`, `tools/deep_city.py`, `data/rift_deep.json`, `tools/rift_deep.py`,
`data/rift_regions.json`, `data/vr_caves.json`, `docs/world-building/DEEP_CITY.md`, `docs/STATE.md:191`,
`docs/world-building/BUILD_PALETTE.md`, `docs/world-building/VICTORY_ROAD_FIGHTS.md`.

---

## 1. What is in the pit now

### 1.1 The ground the city stands on

| Fact | Value | Source |
| --- | --- | --- |
| Region `the_deep` | bbox x3421-3786, z3015-3429; 114,180 columns | `data/rift_regions.json:76` |
| Centre (measured centroid, **not** the region seed) | (3603, 3222) | `DEEP_CITY.md:35`; computed by `rift_deep.model()` (`tools/rift_deep.py:189,208`) |
| Rings | 5 treads at y66 / y49 / y32 / y15 / y0, each 36 wide, step 17 | `data/rift_deep.json:15-20` |
| Rift floor / pit lip | y83 (17 above ring 0) | `data/rift_deep.json:20`, `DEEP_CITY.md:36` |
| Sheer sector | 55 degrees either side of the line to `entrance_to_e4`: ring 0, then one unbroken 66 face to the floor | `data/rift_deep.json:22-27`, `tools/rift_deep.py:199-204` |
| Victory Road's mouth | (3560, 1, 3064) | `data/vr_caves.json:86-91` |
| Mouth tunnel kept clear | x3555-3565, y0-9, z2974-3066 | `data/deep_city.json:212`, `tools/deep_city.py:719` |
| Mouth plaza kept clear | x3528-3592, y1-41, z3064-3124 | `data/deep_city.json:213`, `tools/deep_city.py:720` |
| Reserved volumes (sealed) | Hoopa's cradle, the cradle passage, the HQ basement, the secure shaft — all between x3317 and x3445 | `data/deep_city.json:205-210` |

Derived, **not measured**: 114,180 columns is an equivalent radius of about **191**; the floor begins where
a column is 4 x 36 = **144 or more** from the pit's edge (`tools/rift_deep.py:198`), so the non-sheer floor
is an irregular disc of equivalent radius about **47** (about 93 across). `DEEP_CITY.md:99` independently
calls the core "est. 60 across". The sheer sector adds **25,518 columns** of bare floor under the 66 face
(`data/deep_city.json:26`).

### 1.2 The 196 buildings, district by district

STATE's counts (`docs/STATE.md:191`) are arithmetically consistent and I accept them: Rimside 69, the
Works 38, the Quarter 29, Relay Row 20, the Core 8, the Stacks 27, HQ 5 sections = **196**; the spire and
the HQ tower are counted separately.

| District | Ring / level | Buildings | Id form | Where it sits |
| --- | --- | ---: | --- | --- |
| Rimside | ring 0, y66 | 69 | `lot_<x>_66_<z>` | full circuit on the rim street |
| The Works | ring 1, y49 | 38 | `lot_<x>_49_<z>` | — |
| The Quarter | ring 2, y32 | 29 | `lot_<x>_32_<z>` | — |
| Relay Row | ring 3, y15 | 20 | `lot_<x>_15_<z>` | — |
| **The Core** | floor, y0, non-sheer | **8** | `lot_<x>_0_<z>`, `district == "core"` | against the feet of ring 3's riser |
| The Stacks | floor, y0, **sheer** | 27 | `lot_<x>_0_<z>`, `district == "stacks"` | against the 66 north face |
| The Compact's HQ | one section per ring + floor | 5 | `hq_66`, `hq_49`, `hq_32`, `hq_15`, `hq_0` | the west bearing window 244-266 (floor 205-262) |
| HQ tower | over (3427, 3308), 11-square, top **y132** | 1 | inside `hq_66` | `data/deep_city.json:183` |
| The Core spire | radius 8 (17 across), top **y100**, decks every 16 from y15, beacon at y98 | 1 | — | the non-sheer floor column furthest from every riser |

**Lot ids are coordinate-derived and cannot be listed without running the generator.** `tools/deep_city.py:1164`
builds them as `"lot_%d_%d_%d" % (seed x, tread y, seed z)` and `:1088` builds HQ sections as `"hq_%d" % tread y`.
The ids of the eight Core buildings are therefore exactly the entries of `plan.json`'s `lots` list
(written at `tools/deep_city.py:1519`) with `level == 0` and `district == "core"`. That predicate is the
answer; the eight literal strings are a shell command away and are in section 7.

### 1.3 The stair towers

`tools/deep_city.py:754-776` builds **one stair tower per lift pair**, then `:778` builds the Sink Gate as
one more. `tools/rift_deep.py:221` sets `per = max(2, banks // (len(treads) - 1))` = `max(2, 10 // 4)` =
**2 per boundary** across **4 boundaries** = **at most 8 lift pairs**. So the pit should hold **8 + 1 = 9**
stair towers, which is the owner's number.

### 1.4 How the city's buildings work

- A lot is a cell of columns round a seed sown at exactly 7 from a riser foot, trimmed to its own depth
  (11, 13, 15 or 16) and dropped if fewer than **40** columns survive (`data/deep_city.json:97-104`,
  `tools/deep_city.py:1116-1160`).
- The buildable zone is `dist < 16` from a riser foot (`zone_depth`). **Everything more than 16 from a
  riser is unbuildable by construction** — which is precisely where the spire stands.
- Frontage 16, storey 5, so three floors in a 17 riser; roofs are flush with the street above and are that
  street's outer terrace.
- The lots are seeded **last**: `claimed` already holds the plaza, the tower footprints, the service
  buildings, the spire and the bridge decks when `lot_zone` is computed (`tools/deep_city.py:1065-1069`).

**That last point is the single most important fact in this document.** Anything added to `claimed` before
line 1064 does not *conflict* with a building — it quietly prevents one from existing, and a lot squeezed
under 40 columns is dropped with no error. **The cost of a bigger tower is paid silently in the lot count.**

---

## 2. Where a tower could physically go

### Site A — the spire's site, the spire grown (recommended)

The spire already occupies the one place in the pit that costs nothing: the non-sheer floor column with the
greatest distance from any riser, at least `radius + 12` = 20 from every floor lift, with a
`2 x radius + 3` = 19-square clear of everything already claimed (`tools/deep_city.py:886-901`). That site
is outside the lot zone (`dist < 16`) by definition, and the generator fails closed with
`CityError("no room for the spire on the Core's floor")` if it cannot find one.

| | |
| --- | --- |
| Footprint | the spire's computed centre (`plan.json` `spire.centre`; **not measured here**), radius **16** → 33 across |
| y range | y0 (lobby floor) to **y128** (crown), 45 proud of the lip at y83 |
| Buildings displaced | **0**, if the drum stays inside the free inner disc (equivalent radius about 30, est.) |
| Stair towers displaced | **0** — the siting rule already holds 20 clear of every floor lift |
| What is lost | the Core spire **as currently generated** (radius 8, y100, 6 decks, the beacon). It is generated, not hand-authored, so it is regenerated rather than destroyed |
| Keep-clear | the mouth plaza is 100+ blocks north of the centre; every reserved box is west of x3445 — clear |

Risk: going from radius 8 to 16 widens the required clear square from 19 to **35**. If the floor cannot
offer that, the generator raises `CityError` — a loud failure, not a silent one. The silent failure mode is
the drum reaching `dist < 16` and suppressing Core lots; the builder must diff the per-district lot counts.

### Site B — the Core replaced

A drum 60-80 across on the floor, sitting on the Core's street.

| | |
| --- | --- |
| Footprint | the non-sheer floor, 60-80 across, centred near (3603, 3222) |
| y range | y0 to y128 |
| Buildings displaced | **the 8 Core buildings** — the `plan.json` lots with `level == 0` and `district == "core"` — plus **the spire**, which stands inside that footprint, and at 80 across very likely **`hq_0`**, the HQ's floor section |
| Stair towers displaced | the ring-3/floor lift tower if the drum reaches the west (`data/deep_city.json:182` says that tower and the spire's west bridge already take most of the west floor) |
| What is lost | 8 buildings, possibly 9, and `hq_lower_hall` — "the likeliest stage for the confrontation" (`data/deep_city.json:194`) |

This is the obvious middle and it is **big enough**. It costs 8 buildings and, at the larger radius, the
finale's stage. It also puts a commercial fight tower on the plaza a player crosses to leave for the Elite
Four, so the last thing the Deep says before the League is "pay to fight" rather than "this is the way out".

### Site C — the north face, in the Stacks

A tower against the 66-block sheer face, rising out of the 25,518 columns of bare floor, roof flush with the
north promenade.

| | |
| --- | --- |
| Footprint | 40 x 40 or wider against the face, somewhere in x3528-3680, z3064-3140 |
| y range | y0 to y128 (y0-y66 inside the face's shadow) |
| Buildings displaced | **4 to 8** of the 27 Stacks buildings for a 40-square; **up to all 27** (`lot_<x>_0_<z>`, `district == "stacks"`) if it takes the face |
| Stair towers displaced | none — there are no lifts on the sheer side (`data/rift_deep.json:62`) |
| What is lost | the families' tower blocks (story: the refugees' homes), the promenade's terrace over them, and clearance: the mouth plaza (x3528-3592, y1-41, z3064-3124) and Victory Road's tunnel are right there |

Visually the strongest — a tower growing out of a 66-block cliff — and the worst neighbour. It evicts
refugees to build a fight club and it crowds the finale's exit.

### Site D — the HQ tower grown (runner-up, listed for honesty)

`hq_tower` already reaches **y132** (`data/deep_city.json:183,195`), is 11 across, and has "no way in
built". Growing it costs **0 buildings and 0 towers**. It costs the HQ: the tower's storeys are reserved and
sealed for Codex's story, and it makes the Compact's headquarters and a paid fight ladder the same building.
That is either very good story or a collision with `hq_director_office`, `hq_anchor_control` and the
confrontation. It is Codex's volume, not this document's to spend.

---

## 3. Coexist or replace: the recommendation

**Recommended: they coexist, and the arena IS the spire grown (Site A).**

The defence, in the terms the owner asked for:

1. **It costs zero buildings and zero stair towers.** No other site in the pit can say that. The spire's
   site is the only large footprint the city's own rules leave empty, because the lot zone stops 16 from a
   riser and the spire is sited at the maximum.
2. **What is lost is a generated shell, not authored judgement.** The spire is emitted by
   `tools/deep_city.py:883-964`; its centre, decks and beacon are recomputed every run. Nothing about it is
   hand-authored in the sense of `data/vr_trainers.json`.
3. **The story already supports it, and it is not a theme park.** The Deep is a summit town displaced
   underground, "a city fuelled by the Rift" (`DEEP_CITY.md:26`), run by a Compact that needs money and
   legitimacy and is explicitly "not evil". The spire is already the city's single shared structure, the
   light column every street is built around. A ladder inside it reads as *the Compact selling the one thing
   it has* — the Rift's power, as spectacle — to people who arrive at the last town before the League with
   full pockets. The prize money is the city's income. The refugees in the Quarter get the trade it brings.
   That is a reason for the tower to exist in this city specifically, which is the test a fight tower has to
   pass here.
4. **The lighting language survives intact.** L5 (the light column) becomes the arena's spine; L6 (the one
   beacon) becomes its crown; the violet-cyan-warm grammar of `data/deep_city.json:61-87` is unchanged. A
   drum of glass over a column of light that you climb by winning is the same object the design already has.
5. **The HQ stays the dominant building.** Crown at y128, under the HQ tower's y132. `data/deep_city.json:186`
   calls the HQ "the dominant building"; keeping the arena 4 below preserves that without argument. The
   owner may of course want the arena to overtop it — that is open question 4.

**What the city keeps:** all 196 buildings, all 9 stair towers, all 8 lift pairs, the Centre and Mart, the
mouth plaza, the HQ and its tower, every reserved volume, the relic area, and the existing y15 bridge.

**What comes out:** the Core spire as generated — one structure, 17 across, top y100, 6 decks, 1 beacon.

Runners-up, one line each:
- **Site B, the Core replaced:** a better lobby and a worse neighbour; 8 buildings, probably the spire too,
  and at the larger radius `hq_lower_hall`, the confrontation's stage.
- **Site C, the north face:** the best picture in the pit, paid for with up to 27 refugee homes and the
  clearance round Victory Road's exit.
- **Site D, the HQ tower:** free in buildings, expensive in story, and Codex's volume to spend.

**The pit can hold both.** The honest "it belongs somewhere else" answer is only forced if the owner wants
a ground-level hall 60+ across with a real lobby and tiered seating, which Site A's drum cannot give.

---

## 4. The tiers as a shape

Geometry only. Nothing below asserts anything about how a fight is run.

### 4.1 The ladder

The pit's own vertical grammar is 15 then 17: streets at y0, 15, 32, 49, 66 and the lip at y83. Continue it
upward and the tiers land on it exactly:

| Tier | Floor y | Clear to the next floor | What is at that height in the city |
| ---: | ---: | ---: | --- |
| lobby | 0 | 15 | the Core's plaza, the floor street |
| 1 | 15 | 17 | Relay Row — **the existing bridge already lands here** (`data/deep_city.json:175`) |
| 2 | 32 | 17 | the Quarter |
| 3 | 49 | 17 | the Works |
| 4 | 66 | 17 | Rimside, the rim street |
| 5 | 83 | 17 | **the Rift floor / the lip** — the tower leaves the pit here |
| 6 | 100 | 17 | the spire's current top |
| 7 | 117 | 11 to the crown | open air, 34 over the lip |
| crown | 128 | — | the beacon; 4 under the HQ tower's y132 |

**Seven tiers plus a lobby.** 17 of clear per tier gives roughly 14 of interior headroom after a floor and a
ceiling course. Tier 5 at y83 is the one that matters dramatically: it is level with the Rift floor, so it is
where a climber first sees out of the pit, and the only tier that can have an outside terrace at ground level.

**Champions sit on tier 7 (y117).** If the ladder needs more than one champion, tier 6 and tier 7 are the
pair. The crown at y128 is the beacon and the view, not a battle floor.

**[fight-system]** If the ladder needs more than seven rungs, **add them horizontally, not vertically**: two
or three stands on one tier floor, not a halved storey. Halving the storey to 8-9 breaks the alignment with
every street and leaves a battle floor with 6 of headroom, and no document in `docs/research/` records how
much clear space a Cobblemon battle actually needs.

### 4.2 The drum

Radius **16** (33 across) at the spire's computed centre.

- The central **7 x 7** stays the light core and the spiral stair, exactly as `build_tower()` already builds
  it for the spire with `exits` onto every deck (`tools/deep_city.py:950-953`). That function is the
  precedent; this is a parameter change, not a new mechanism.
- Each tier floor is therefore an **annulus**, r=4 to r=15: **11 wide** all round, about 60-90 of circumference.
  That is a ring, which is the shape the name wants, and it keeps the light column unbroken.
- The crown at y128 is a single hall 33 across — no core above the top tier, so the climb ends in a room
  rather than a corridor.

The alternative shape, for the record: radius 13 with the stair moved into a 7 x 7 bay in the shell, giving a
clear hall 25 across per tier. It is a better battle floor and it breaks the light column into eight stubs.
**Recommend the ring.**

### 4.3 How a player goes up

**Reuse everything; add nothing below y66.**

- The city is already the lift. Nine stair towers and eight lift pairs carry a player from the lip to any
  street, and the **existing y15 bridge** (3 wide, `data/deep_city.json:177`) is the city's door into tier 1
  from Relay Row — the Compact's civic floor, which is where you would register.
- Inside the tower, the spiral stair round the light core runs y0 to y117 with a door onto every tier.
- **A second bridge at y32 to the Quarter is feasible but long.** The bridge walk in
  `tools/deep_city.py:970-1008` strides outward until it meets a column whose tread equals the bridge's y,
  capped at 140. From the centre, y15 lands on ring 3 at about 30-45; y32 lands on ring 2 at about 70-110;
  **y49 and y66 are 110 to 150+ and the y66 span is exactly the "long glass span" the owner already declined**
  (`data/deep_city.json:21`, decision 3). So: keep y15, offer y32, do not propose y49 or y66.
- **[fight-system]** `lumymon:elevator` has a per-player `requiredAdvancement` read from the bytecode
  (`data/rift_deep.json:55-61`), so "you may ride straight to the highest tier you hold" is available as a
  mechanism the moment the fight system can grant an advancement per tier. **Riding a lift at all is NOT
  PROVEN** (`data/rift_deep.json:58`), so the stair is the real way up and the lift is a convenience.

### 4.4 Materials

No new palette. Everything the arena needs is already in `data/deep_city.json:34-59` and already checked
against `data/spawn_blocks.json`: `deep_stone` (polished deepslate) for floors, `panel_black` for the shell's
solid courses, `glass_dark` and `glass_conduit` for the drum, `rib_teal` (waxed oxidized copper) for the ribs,
`grate` for the gantries, `tread`/`tread_edge` for the decks, `rail` (light blue pane) at every drop,
`sea_lantern` and `violet` for the light. Providers are all in `BUILD_PALETTE.md` (Moar Concrete, Rechiseled,
Legendary Monuments).

**Three hard rules carried over:** no water anywhere (a spawn condition for 84 species,
`DEEP_CITY.md:217`); no iron blocks (Meltan), so the beacon base stays gold; no `minecraft:light` blocks. A
tower of gold and glass also sharpens owner decision 5, adventure mode inside the city.

---

## 5. What the tower costs, in one table

| | Site A (recommended) | Site B, the Core | Site C, the face | Site D, the HQ tower |
| --- | --- | --- | --- | --- |
| Buildings lost | **0** | 8, likely 9 | 4-8, up to 27 | 0 |
| Ids | — | `lot_*_0_*` where `district == "core"`; plus `hq_0` | `lot_*_0_*` where `district == "stacks"` | — |
| Stair towers lost | 0 | 0-1 | 0 | 0 |
| Other structures lost | the spire (generated) | the spire, `hq_lower_hall`'s stage | the north promenade's terrace | `hq_tower`'s reserved storeys |
| Keep-clear risk | none | low | **high** (mouth plaza, VR tunnel) | none |
| Story cost | the light column becomes a fight tower | the finale's stage and the exit plaza's meaning | the refugees' homes | the Compact's HQ runs the ladder |
| New mechanism needed | none | a lobby and a plaza rebuild | the face rebuilt | a way into a sealed tower |

---

## 6. Where the shape depends on the fight system

1. **Tier count.** Seven is what the pit's 17-step grammar supports between the floor and the HQ's height.
   More rungs must come from more stands per tier.
2. **Per-tier battle floor.** The annulus is 11 wide; whether that is enough is unanswered, because the clear
   space and headroom a Cobblemon or `rctmod` battle needs is not recorded as VERIFIED in `docs/research/`.
3. **Per-player tier state.** The geometry is one shared tower. If "who holds tier 7" has to be per player
   and visible, that is either a per-player actor (the scene runtime's pattern, `DEEP_CITY.md:160`) or it is
   not expressible in blocks at all.
4. **Stands.** Each tier needs a seat with `yaw`, `faces`, `eye_contact` and `sight_distance`, on Victory
   Road's pattern (`docs/world-building/VICTORY_ROAD_FIGHTS.md:53-75`). The geometry reserves the cell; the
   values are the fight system's.
5. **Money.** The pack's economy is CobbleDollars (`CLAUDE.md`, base-pack systems). Nothing about prizes is
   designed here.
6. **The ladder's level band.** The Deep's cap is 60 and Victory Road beyond is 58-64 (`DEEP_CITY.md:22-23`).
   An endless ladder in the last town before the League is a pacing decision for
   `trainer-balance-designer`.

---

## 7. What I could not measure

I have no shell, so `tools/deep_city.py` was not run and no generated plan was read. These are questions,
not answers:

1. **Every literal id.** The eight Core ids and the 27 Stacks ids are in `plan.json`'s `lots`
   (`tools/deep_city.py:1519`), selected by `level == 0` and `district == "core"` / `"stacks"`.
2. **The spire's centre `(scx, scz)`** and therefore the arena's exact position.
3. **The free radius at that centre** — whether radius 16 passes `free(cx-17, cz-17, cx+17, cz+17)`. If it
   does not, the generator raises `CityError("no room for the spire on the Core's floor")`.
4. **Whether a wider drum silently suppresses Core lots.** The builder must diff per-district lot counts
   before and after; the lot pass runs after `claimed |= spire_cols` and drops any lot under 40 columns with
   no error.
5. **The real tower count.** 9 is derived from `per = max(2, 10 // 4)` = 2 per boundary over 4 boundaries,
   plus the Sink Gate. A boundary that failed to place both pairs would make it 8.
6. **Each bridge's length** at y15 and y32, and whether a y32 landing exists within the 140 cap.
7. **Light levels.** `data/deep_city.json:85` says the light figures are modelled by Manhattan distance with
   no occlusion and are "NOT a measurement".
8. **Lift riding**, still NOT PROVEN.

## 8. Disagreements found between the documents and the data

Reported as findings, not smoothed over.

**Findings 1-5 were FIXED on 2026-10-01 (owner decision D3), each by establishing which side the code or
the data supported and changing only the wrong side. The entries below are kept as the record of what was
wrong and are no longer live:** 1 — nine confirmed and `docs/STATE.md` and `RIFT_STATUS.md` corrected,
from a run's own counts ("stair towers round lift banks 8", "the Sink Gate 1"); 2 — `data/rift_deep.json`
`lifts.banks` is now 8, with a `banks_how_it_is_read` note, and the same 8 pairs are placed before and
after; 3 — `DEEP_CITY.md` now carries the measured 196 beside the 130 estimate; 4 — its status header now
says applied to `staging-2026-10-01` and records that the dryrun worlds are deleted; 5 — `FACTION.md` now
puts the cradle at (3357, 3306) and records (3297, 2603) as retired and already propagated.

1. **The stair-tower count.** `docs/STATE.md:191` reads "8 stair towers round the lift banks and the Sink
   Gate"; the owner says nine. `tools/deep_city.py:754-776` builds one tower per lift pair and `:778` builds
   the Sink Gate as an additional one, and `tools/rift_deep.py:221` yields 8 pairs. **Nine is the number the
   code implies**; STATE's sentence reads as eight in total. Unsettled without a run.
2. **`data/rift_deep.json:51` says `"banks": 10`, and 10 is unreachable.**
   `per = max(2, banks // (len(treads) - 1))` = `max(2, 10 // 4)` = 2, times 4 boundaries = 8. The spec's 10
   is dead: 12 would also give 8, and 16 would be needed for 10. `DEEP_CITY.md:38` says "2 banks per ring
   boundary = 8 pairs" and matches the code; the data file does not match either.
3. **`DEEP_CITY.md:94-96` estimates "about 130 buildings plus the spire and the HQ"; the build made 196**
   (191 district lots + 5 HQ sections). The doc is 66 low, about 34%. It labels the figure "est." and was
   never updated after the build.
4. **`DEEP_CITY.md:3-5` says the city is generated "into `build/` only: not run on staging, not seen in
   game".** `docs/STATE.md:191` says R9DC ran on `cobblers-dryrun11` on 2026-09-27, 99 functions, 300 of 300
   sampled blocks present. The design doc's status header is stale.
5. **The cradle's location is still contradicted.** `docs/story/FACTION.md` puts it under the League plateau
   at (3297, 2603); `data/rift_regions.json` and `DEEP_CITY.md` put it under the relic area at (3357, 3306).
   Already recorded at `data/deep_city.json:29` and still open. It does not touch the arena.
6. **A trap, not a contradiction:** `DEEP_CITY.md:35` gives the Deep's centre as "measured (3603, 3222)"
   while `data/rift_regions.json:77` gives `the_deep.seed` as (3600, 3150). They are different quantities.
   Any arena siting must use `rift_deep.model()["centre"]`, never the seed.

---

## 9. Open questions for the owner, to answer one by one

1. **Site:** A (the spire grown, 0 buildings lost), B (the Core, 8-9 lost), C (the north face, up to 27
   lost), D (the HQ tower, 0 lost and Codex's volume), or "not in the pit"?
2. **Does the arena replace the spire's meaning, or carry it?** Recommended: carry it — the light column is
   the spine, the beacon is the crown, so the city's lighting language is unchanged.
3. **Seven tiers at 17 apart on the pit's own grammar, or more rungs with several stands per tier?**
4. **Does the arena top the HQ?** Recommended no: crown at y128, 4 under the HQ tower's y132, so "the
   dominant building" stays the Compact's.
5. **The drum: a ring (radius 16, an 11-wide annulus round the light core) or a hall (radius 13, the stair
   in the shell, a clear 25-across floor and a broken light column)?** Recommended: the ring.
6. **A second bridge at y32 to the Quarter, yes or no?** y49 and y66 are the long spans already declined.
7. **Whose tower is it?** Recommended: the Compact's, as the city's income — which makes it the same
   institution as the HQ without being the same building.
8. **Does the ladder stay open after the Champion?** Geometry is indifferent; it decides whether the arena is
   a pre-League stop or the Deep's permanent reason to exist.
9. **Adventure mode inside the city** (DEEP_CITY.md decision 5, still open) — a tower of gold and glass makes
   it sharper.
10. **Does `plan.json`'s lot count change when the drum grows?** Not a taste question: the builder must
    report the per-district diff, and if the Core drops below 8 the owner is paying a cost nobody chose.
