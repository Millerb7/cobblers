# Dungeon 2: The Street That Ends at Nothing

**Status: DESIGN ONLY (content-architect, 2026-10-09).** Nothing here is built, placed, generated or run. **The
owner, 2026-10-09: build nothing past the Night Shift until the owner has played it.** This document makes dungeon 2 of
the six-dungeon list (`docs/mechanics/DUNGEONS.md:897`) ready to hand to builders when that changes.

It builds on `DUNGEONS.md` throughout and does not reopen its decisions (D1-D22, `DUNGEONS.md:30-60`). The engine
it designs to is the built core: `tools/dungeon.py`, `data/dungeons.json` (schema `cobblers.dungeons/2`) and
`experiments/EXP-084-dungeon-engine-core/README.md`, which is NOT_EXECUTED.

Labels are `DUNGEONS.md`'s (`:23-26`):
- **VERIFIED**: read in source, a jar read recorded in `docs/research/`, or a run, with the citation.
- **ASSUMED**: inferred, not checked.
- ***relayed***: taken from another document and not re-measured here. **No coordinate or ground height in this
  document was measured by this unit**, which has no shell.
- ***read***: this unit read the value at the cited line on 2026-10-09.
- ***planning***: a value chosen so the arithmetic can be done; XT1 replaces it.

---

## 0. Question and premises

**Question.** Design dungeon 2, the Scar's dungeon with Palkia as its lake legendary, to the Night Shift's level of
detail (`DUNGEONS.md` section 11). It must differ from the Night Shift and from dungeon 3. It must say where it needs
more than the engine core provides.

**Premises checked:**

| # | Premise | Finding |
|---|---|---|
| P1 | The Scar is the rip home (`DUNGEONS.md:897`) | **Right, with a blocker. The Scar is not in the live world.** Its pad and ruins exist in the canonical heightmap and on staging only. "Surge's town, the Scar and the Frostpeak shrine wait for the live re-export" (`docs/STATE.md:381`, *read*; also `:344`). **The rip cannot reach the live game before that re-export.** Staging can carry it. |
| P2 | "First reachable about gym 2-3" (`DUNGEONS.md:897`) | **Probably gym 3.** The handoff says the Scar is reachable from Route 4 "after Surge (gym 3)", 437 blocks off the leg (`docs/story/handoffs/DISPLACED_CITY_AND_SCAR.md:124`, *relayed*). After Surge the cap is 35, which is band 2 (`DUNGEONS.md:608`). The two documents disagree by one gym. Neither gates it in data. |
| P3 | "The road's end" exists to put a rip at | **Partly.** The avenue runs north and "stops at the cliff edge, in the air", but that end is **not built**. Whether a cliff exists there is "a heightmap question" (`data/ruins.json:770-771`, *read*). The rip is designed (section 3) so that it works whether or not there is a drop. |
| P4 | The engine has one clock per band | **True, and it is a gap for dungeon 2.** `engine.bands[].clock_s` is one table for every dungeon (`data/dungeons.json:73-81`, *read*). V3 makes each clock a function of its own spine (`DUNGEONS.md:1084`), so the clock moves under each dungeon (section 8, E-S1). |
| P5 | The engine's segment kinds | **Partly built.** The core builds `entry_room`, `drift`, `boss_arena` and `exit_room`, and requires exactly one each of entry room, boss arena and exit room (`tools/dungeon.py:345-350`, *read*). `DUNGEONS.md:929` calls the end rooms `rip_room`, so the two names disagree. `stand`, `seam`, `den`, `lake` and `parkour` are step 6 and not built (`data/dungeons.json:4`, *read*). Every floor is at `floor_y` and every segment is roofed with its wall block (`tools/dungeon.py:198-208`, `:520-524`, *read*). |

---

## 1. Theme, and why it is here

**The fiction.** A summit city was exchanged whole into the cavern under the Glacial Tear. The Scar is the footprint
it left: 33 roofless ruins on a pad pressed flat at y280, with an avenue that runs north to an edge and stops
(`DISPLACED_CITY_AND_SCAR.md:73-101`, *relayed*). The rift is **the street the exchange folded**. A piece of the city
was caught between the two places and never arrived at either. Its street repeats, its square is drowned, and its
road breaks off into nothing. The pocket's fixed noon (`data/portals.json:69-70`, `fixed_time` 6000 and
`has_skylight` true, *read*) means this street still has the sun the Displaced City lost.

The story belongs to Codex: what the folded street *means* (echo, remnant, or the city's missing piece) is
`DISPLACED_CITY_AND_SCAR.md` Q1 and Q3, still open. This design commits to geometry, not to an answer.

**Palkia** (water/dragon, catch rate 3, MSD; *relayed*, `docs/research/notes/unhomed-legendaries-1.8.0.md:106`)
is the master of space, under the drowned square. The owner approved the pick (D18, `DUNGEONS.md:815`).

**How it differs from the Night Shift:**

| | The Night Shift | The Street |
|---|---|---|
| Space | enclosed drifts, timber, lanterns, dark rock | **open streets under a fixed noon sky**, houses on both sides |
| Signature mechanic | none new: every leg is a `DUNGEONS.md` 3 kind | **the fold**: a street block that repeats until you knock at the lit house |
| The lake | a vertical shaft seen from a gantry | **a drowned lane under the street**, seen through broken paving and swum along |
| Parkour | trestles and cages in a cave hall | **the road breaking off into the void**, open on every side |
| The den | the Electirizer den, electric, in a side room | **the Belfry**, a tower above the street, steel/psychic |
| Families | fighting, rock, ground (`DUNGEONS.md:923`) | ghost, steel, psychic: the Displaced City's urban roster |

**How it differs from dungeon 3** (`DUNGEON_3_PATRIARCH.md`): the Street is level, open and lit by daylight. Its
puzzle is attention (which house), and its greed is ore. The Patriarch descends into the dark, its way back is a
climb, and its greed is healing.

---

## 2. Gate and band coverage

- **`gate_flag: null`**, as `DUNGEONS.md:897` proposes. The geography gates it: the Scar is first reached after Surge
  (P2).
- **Bands 1-6 are all authored.** The engine refuses a dungeon without an ace for every band
  (`tools/dungeon.py:419-420`, *read*), and the band is read from the cap at the rip (`DUNGEONS.md` 5.1).
- **The expected first entry is band 2** (cap 35 after gym 3). Band 1 exists for a player who reaches the Scar with
  one badge, which no gate prevents.
- **Band 6 is the Palkia catch** (D8: catches only after the Champion).
- **Sigils are per band, not per dungeon** (`DUNGEONS.md:709-713`). The Street takes the same ladder. The free first
  entry is the Night Shift's alone, and is still Q20 OPEN (`DUNGEONS.md:1310-1313`).

---

## 3. The rip home and its evidence

**Where.** The ruined avenue's north end, where the paving stops. The avenue runs north across the pad and stops "at
the cliff edge, in the air". It is paved to z803 (`data/ruins.json:770-771`, *relayed*). The last building before the
end is the temple ruin on the west side of the avenue (`data/ruins.json:758`, *relayed*). The rip stands across the
avenue's line where the street runs out, with its opening facing **south down the avenue**. A player walks the whole
ruined city to reach it. The street ends at the rip: whether there is a drop behind it or only a slope, the rip is the
"nothing" the street ends at.

**The coordinates are RELAYED, and their ground is NOT measured by this unit:**
- the Scar's centre is (2110, 950), ground_y 280.3, and its footprint is x1960-2260, z800-1100
  (`data/towns.json:2070-2082`, *relayed*). Town records are checked against the canonical heightmap by
  `tools/validate_data.py` and rewritten only by `tools/measure_towns.py` (`docs/STATE.md:197`, *relayed*), so the
  record is likely right. This unit did not run it;
- the avenue's x is **not read**. The towers bracket it at x2057-2063 (west) and x2172-2178 (east)
  (`data/ruins.json:765`, *relayed*).

**What `world-content-dev` must measure, on `tools/ground.py` (never a world), before the rip enters `data/`:**
1. the avenue's centre x and its north paving line from `data/ruins.json`'s own plan, read from the record and not
   from a staging world;
2. `round(ground(x, z))` across the candidate rip cell, a frame 5 wide (`tools/dungeon.py:422-423`), and the
   outside point 3 to 5 blocks south of it on the avenue. Both must be on the pad's flat. The pad is pressed flat
   within 150 of the centre and feathered over 140 (`DISPLACED_CITY_AND_SCAR.md:73-74`, *relayed*), so the north end
   at z~803 is 147 from the centre and **may already be on the feather**. Measure it;
3. **the drop question** (`data/ruins.json:771`): ground from z803 north to z760, sampled per column. If a cliff
   exists, the outside point must sit back from the edge so that the exit's teleport can never land a player over
   it. Leave at least the rip's own depth plus 3;
4. **clearance from the ruins**, taken from `data/ruins.json` (the temple, the lots, `scar_foundations` and the
   towers) and the ruin kits' extents, not from a world. Our ruins are what stands there. Nothing else does, because
   the pad is pre-exported inside the border. The kits are named in the record;
5. **sight.** V1 found that the rip's particles cannot be seen from 64-128 blocks (`data/dungeons.json:41`, *read*).
   The avenue is a straight 290-block sightline (`DISPLACED_CITY_AND_SCAR.md:81-82`, *relayed*), so the **plume**
   (`rips[].plume`) is likely needed here. The Scar is dark by design (`data/ruins.json:775`, *read*), so at night
   the rip is the only light on the mountain. That is the look to show the owner.

**The palette** is `world-content-dev`'s: the Scar's own cracked and mossy stone brick and the city's spruce, torn
open. It uses no nether or end portal block (`tools/dungeon.py:424-426`) and **no concrete** (contract C4).

---

## 4. The spine, segment by segment (x increases from the entry)

| # | Segment | Kind | Spine blocks | Contents |
|---|---|---|---|---|
| 0 | The Last Stop | `entry_room` | 16 | arrival; the back rip; the board (`DUNGEONS.md` 2.4, plus the fold line, section 5.1); the threshold |
| 1 | The Avenue | `drift`, **open sky** | 220 | 9 wide, ruined house fronts both sides, lantern posts every 8; straight |
| 2 | The Lamplighter's stand | `stand` | 24 | a small square at a well; timber gate |
| 3 | The First Fold | **`fold`** | 96 | two identical street blocks of 48, each ending in a dog-leg; 4 house doors per copy, one lit per run |
| 4 | The Cross Street | `drift`, open sky | 200 | turns twice in z inside the strip |
| 5 | The Locksmith's stand | `stand` | 24 | a gatehouse arch |
| 6 | The Cut | `seam` | 30 | where the exchange sheared the street: the paving stops at a raw face of Mt Vessu's rock with its ores; 24 seam blocks; the ladder board |
| 6a | The Belfry | `den`, off-spine, **up** | 0 (a stair of 20 up, off the Cut) | the nest (section 6.3) |
| 7 | The Second Fold | `fold` | 96 | as 3, a different street |
| 8 | The Drowned Square | `drift` (a plaza, 33 wide) | 36 | the old square half under water; the empty plinth at its centre; the lane's mouth in its south-east corner |
| 8a | The Drowned Lane | `lake`, **shape `lane`**, beneath 9 | 0 (off-spine, under the next segment) | section 6.4 |
| 9 | The Lower Street | `drift`, open sky | 200 | cracked paving with glass breaks in it, through which the lane and Palkia's glow show below |
| 10 | The Road That Ends | `parkour`, open | 160 | 4 sections of 40: slabs of road hanging in the void; catch band 6 below; barrier ceiling 3-4 above the route |
| 11 | The Far Kerb | `drift`, open sky | 150 | the street resumes as if nothing happened |
| 12 | The Surveyor's stand | `stand` | 24 | a survey office's steps |
| 13 | The Third Fold | `fold` | 96 | the last fold, a narrower street: its doors are closer, so a lap is shorter but the windows are harder to read at a sprint |
| 14 | The Gate Road | `drift` | 100 | roofed again, rising 6 to the gate |
| 15 | The Warden's Square | `boss_arena` | 33 | 31 x 33 x 14, open sky; the Warden's three stages |
| 16 | The Street's End | `exit_room` | 16 | the far rip, standing where the street stops |
| | **Total** | | **1,521** | **1,361 walking** (each fold walked once through both copies) + **160 parkour**, inside a 2,048 strip |

Every size is a proposal that the builder settles against the validator (as `DUNGEONS.md:946-947`). The spine length is
the walked path, never x. Segments 1, 4, 9, 11 and 15 are **open-sky**. Their ceiling is a barrier layer at the
segment's height, so daylight reaches the street and nothing can be climbed out (section 7, E-S3).

**The board** adds three lines to `DUNGEONS.md` 2.4's:
- "The street folds. Knock at the lit house to go on."
- "No Pokemon in the folds."
- "The square's south lane runs under the street."

---

## 5. What is new

### 5.1 The fold (the Street's signature)

**What the player sees.** A street block with four house doors. At its end is a dog-leg corner. Round the corner the
same street begins again: the same doors, the same broken lantern, the same cart. One house in each fold has a
**lit window**. Knocking at its door (clicking it) gets the line "Someone was waiting for you." and a bell-like
sound. The street "lets go": round the next corner, the street is a new one. Knocking at a dark door gets "Nobody
lives here any more." and costs only the seconds it took.

**Mechanism** (vanilla `tp` and interactions, at the functions/commands rung; nothing new from Cobblemon):
1. A `fold` segment is **two block-identical copies**, A and A', each of length L (48, *planning*). Each copy ends in
   a dog-leg, so no line of sight inside a copy reaches past its own end. Both copies are emitted by one function
   from one description, so they cannot drift apart.
2. **The fold line** is a box at A' 's first blocks, past A's dog-leg. While the slot's fold k is **closed**, the
   keeper moves any member in that box back by L with `execute as <member> at @s run tp @s ~-L ~ ~`. Rotation is
   unchanged because no rotation is given (vanilla `tp` behaviour, ASSUMED until **FX1**). The player is now at
   the same point of A, seeing the same street.
3. **The key.** At reset (`DUNGEONS.md:120-124`, the slot's mutables) a `random value 1..4` picks the lit house in
   each fold. The window's light block (a lantern behind glass) is set in **both copies**, and the other three are
   left dark. Each door carries an interaction. A click at the lit door opens fold k for the slot (`#s<g> dg.f<k>`
   = 1). Solo first, so per slot is per player. In co-op one knock opens it for every member.
4. **Westbound is never folded.** The box only catches a player crossing eastward into A'. A player turning back
   walks A westward and never meets the line. A player can never be east of the line with the fold closed, because
   the fold never re-closes during a run. So the softlock rule (`DUNGEONS.md:113-115`) holds by construction, and V18
   checks it.
5. **The fold boxes are no-deploy and dismount boxes**, using the parkour's sweep (`DUNGEONS.md` 3.4, already built
   as `no_deploy`, `data/dungeons.json:129-134`). A sent-out Pokemon or a mount left 48 blocks behind by a teleport
   is the problem the sweep already solves. Riding elsewhere stays allowed (Q8).
6. **The clock** counts a fold as its walked length (A + A'), plus 15 s to read the doors (*planning*). A player who
   loops pays roughly 12 s a lap at the planning pace. The Cut sits between the first and second folds, so **a lap
   costs more clock after greed**: at x2 a lap is 24 s of clock.

**Why this rung.** No lower rung makes a street repeat: no addon or native mechanism does, and a datapack loop is a
`tp`. A street that physically re-arranges itself (fills at run time) was rejected: it is a reset of thousands of
blocks per fold per run, against I2's measured 2.64 s stall for one strip (`data/dungeons.json:28`, *read*).

**What it costs if FX1 fails** (a visible jump or a lost sprint): the fold still works as a loop, only less
seamless. If it is unplayable, the fallback is a **closed fold**: the dog-leg holds a gate that opens on the knock, a
plain door puzzle. The fallback is cheaper and loses the "the street repeats" moment.

### 5.2 The open sky

The street segments are roofed with **barrier**, not stone. The pocket has skylight and a fixed noon
(`data/portals.json:69-70`, *read*), so these streets are lit by day. What the pocket's sky looks like above a
barrier ceiling is ASSUMED: the void biome, fixed time and the visible bedrock plane at y0
(`data/portals.json:63-68`, *read*) have never been looked at from inside a slot. **Probe OS1.** The parkour (10)
especially must not show the bedrock plane 95 blocks below. Its pit gets a dark floor 30 below the route, under the
catch band (`DUNGEONS.md` 3.5), so "nothing" reads as nothing.

Lighting still follows V8 (`DUNGEONS.md:1089`): no walkable cell at block light 0, which matters for the roofed
segments 0, 14 and 16. The lantern posts carry the Displaced City's rule, "a town that lost its sun lights itself"
(`DISPLACED_CITY_AND_SCAR.md:44-45`, *relayed*). Here they are dressing under a sun that stayed.

---

## 6. The legs

### 6.1 Stands (families, not teams; rosters are `trainer-balance-designer`'s)

The Displaced City's urban roster is the source (`DISPLACED_CITY_AND_SCAR.md:29`, *relayed*: Magnemite, Klink, Rotom,
Porygon, Trubbish, Gothita, Espurr, Klefki, Greavard, Mimikyu). Each stand keeps `DUNGEONS.md` 3.1's mechanism and
5.3's member counts (2/3/3/4/5/6 by band).

| Stand | Character | Families | By band |
|---|---|---|---|
| 2 | **The Lamplighter**, who still lights posts for nobody | Litwick line, Magnemite line, Rotom | bands 1-2 the base forms; Lampent and Magneton from band 3; Chandelure and Magnezone from band 5 |
| 5 | **The Locksmith**, keys to every door in a city that has none | Klefki, Klink line, Honedge line | Klinklang and Doublade from band 4; Aegislash at band 6 |
| 12 | **The Surveyor**, measuring a street that will not hold still | Espurr line, Gothita line, Porygon line | psychic and space: Meowstic and Gothitelle from band 4; Porygon2 from band 5. Porygon-Z only at band 6, if the owner accepts the Dubious Disc being a counter item (`data/markets.json:396`, *read*) |

### 6.2 The boss: the Warden of the Last Street (NPC chain, fight-only)

`DUNGEONS.md:815` names "the city's last warden (NPC)".
- **Ace: the Golett line.** Golett at bands 1-2, Golurk from band 3. A golem built to guard a city's people fits a
  warden whose city left without him.
- **Escort from band 4** (`escort_from_band`, `data/dungeons.json:212`): the Greavard line, Houndstone from band 5,
  from the urban roster.
- Three stages at band lower cap -2, -1 and 0 (`data/dungeons.json:207-209`, *read*), as the engine builds. No catch
  at any band: section 8's table gives this dungeon no boss catch, and NPC Pokemon refuse balls
  (`DUNGEON_PLACEMENT.md:44`, *relayed*).
- Stage cue: "He gets up again." works as written. The Warden's could be "The street will not let him fall."
  (`trainer-balance-designer` to tone).

### 6.3 The nest: the Belfry (optional; `DUNGEONS.md` 3.6)

**A creature, and a place that suits it.** The Scar's fallen tower stands whole in the fold. Its bells are gone, and
**Bronzor and Bronzong hang where the bells were**. Bronzor at bands 1-2, Bronzong from band 3: steel/psychic bulk
that punishes a party built for the Night Shift. A stair of 20 up from the Cut leads to a belfry room of four.
- **Levels:** `DUNGEONS.md:481` *stands* at cap-2 to cap-1, uncatchable, never alpha, carrying the exempt tag. **OPEN
  (S-Q3):** the owner's standard of 2026-10-09 is "strong enough that meeting it early is a mistake". The design
  would put the **head** of the four at cap+2, and the rest at 3.6's levels. It is optional and costs clock, so being
  over the cap is a choice, not a wall.
- **Drops:** the species' own tables (`DUNGEONS.md` 3.6). **Not read.** `trainer-balance-designer` reads the Bronzor
  line's drop table from the 1.8.0 jar. If it pays nothing worth about 6 minutes of clock, the fallback nest is the
  **Honedge line in the gatehouse armoury**.
- **No bell blocks.** `minecraft:bell` is a spawn-condition block (`data/spawn_blocks.json:1229`, *read*). The empty
  bell frames are the dressing.

### 6.4 The legendary leg: Palkia under the drowned lane

**Shape: horizontal, not a shaft.** The Night Shift's sump is a vertical drop seen from a gantry (`DUNGEONS.md:937`).
The Street's lake is **a street under the street**:
- The Drowned Square (8) is flooded across its south half. From its south-east corner the paving runs down under the
  water as a ramp, into **the Drowned Lane**: 3 wide and 4 high, sloping from 0 to 16 deep over 50 blocks, and
  running east *beneath* the Lower Street (9).
- **The cache** sits in a doorway along the lane, **30 swim-blocks from the nearest air** (the path length, *planning*:
  the same reach as the Night Shift's 30 deep, from Surf's about 61 s of air at 5 blocks a second,
  `DUNGEONS.md:490-493`, *relayed*).
- **At the lane's end, behind the membrane, Palkia rests** on a pale floor, asleep and glowing (3.7's dressing). The
  Lower Street's glass breaks look straight down onto it, so a player walking segment 9 sees it below their feet. That
  is the "obvious".
- **The membrane is 3.7's, unchanged:** closed at bands 1-5 ("It does not stir for you yet."), and at band 6 open only
  to a Dive-qualified member.

**How it is caught (band 6 only):**
- spawned by macro `spawnpokemonat` at **level 100**, which is **at the band-6 cap of 100**. The cap blocks a catch
  only when the target is strictly above it (`DUNGEON_PLACEMENT.md:43`, *relayed*);
- tagged `cobblers.key_boss` and listed in `data/key_ball.json` `bosses` (today Entei only, `data/key_ball.json:29-32`,
  *read*), so **only a Beast Ball catches it, at x5**. Every other ball is refused and handed back
  (`data/key_ball.json:5`, `:13-16`, *read*);
- carries `claims.exempt_tag` and is bound and leashed (3.7);
- catch once per player, by the `pokemon_captured` advancement. After that the lane holds only the cache for them.

Palkia's catch rate is 3 (*relayed*, note row 106), the same as Entei's. The note's throw count therefore applies:
about 4 asleep at 1 HP, 19 at full (`DUNGEON_PLACEMENT.md:45`, *relayed*). **Mega Showdown is world-critical for this
leg** (`DUNGEONS.md:808-810`).

**The battle is underwater** (L2, `DUNGEONS.md:1250`). The fallback is a dry chamber behind the membrane, the
`lake_grotto` archetype (`DUNGEONS.md:520-522`).

---

## 7. The seam and greed: the Cut

**The Cut is the sheared mountain.** The paving stops at a raw face of rock. The exchange cut the street off Mt Vessu
and left the mountain's veins showing. There are 24 seam blocks in a face of 9 x 4, the rift pick, and markers
(`DUNGEONS.md` 3.3, *stands*). It uses the **same ladder** (D13), the same per-run caps and the same economy entry.

| Bands | Ores (re-weighted to copper: a city of wire) |
|---|---|
| 1-2 | copper (the majority), iron, coal |
| 3-4 | add gold, lapis |
| 5-6 | add diamond |

- **V16 holds** (`DUNGEONS.md:1096`): band 2 has no gold (Gilt), bands 3-4 no diamond (Glint, Deepstone), and no band
  has netherite. The band-1 Soot Sigil (3 iron, 3 coal) can be mined only past the free tier of 4.
- **Redstone is left out**, unlike the Night Shift's 3-4 (`DUNGEONS.md:873`): `minecraft:redstone_ore` is a
  spawn-condition block (`data/spawn_blocks.json:2881`, *read*). The pocket's void biome spawns nothing, which is
  untested (`data/portals.json:62`, *read*), so the Street avoids the question.
- **The rift pick's `can_break` becomes per dungeon and band** (section 8, E-S4). Today it is one engine-wide list
  (`data/dungeons.json:120-128`, *read*).

### 7.1 The clock, worked (minutes; every pace *planning*, `DUNGEONS.md` 4.1)

Walk 1,361 / 4.0 = 5.67. The folds' reading: 3 x 0.25 = 0.75. Parkour 160 / 1.5 = 1.78, plus 2 falls at 35 s =
2.95. Seam and cues 1.0. **Fixed part 10.37.** Stand and boss times are `DUNGEONS.md` 4.2's.

| Band | 3 stands | Boss | Fixed | **Required** | **Clock = ceil(x 1.25)** | Slack |
|---|---|---|---|---|---|---|
| 1 | 6.0 | 6.0 | 10.37 | 22.37 | **28** | 5.6 |
| 2 | 7.5 | 6.5 | 10.37 | 24.37 | **31** | 6.6 |
| 3 | 7.5 | 7.0 | 10.37 | 24.87 | **32** | 7.1 |
| 4 | 9.0 | 7.5 | 10.37 | 26.87 | **34** | 7.1 |
| 5 | 10.5 | 8.0 | 10.37 | 28.87 | **37** | 8.1 |
| 6 | 12.0 | 9.0 | 10.37 | 31.37 | **40** | 8.6 |

The lockout of 72,000 ticks (60 min) is above the longest clock (40), so V12 holds.

### 7.2 Greed, worked (band 2, clock 31: the expected first band)

Reaching the Cut and digging its free tier: 610 blocks (2.54), two stands (5.0), one fold read (0.25), cues (0.3) and
the dig (0.5) come to **8.6 minutes**, leaving **22.4** on the clock. After the Cut: 751 blocks (3.13), the parkour
(2.95), one stand (2.5), the boss (6.5), two fold reads (0.5) and cues (0.2) come to **15.8 minutes of real time**.

| Taken | Speed | Clock the rest needs | Outcome |
|---|---|---|---|
| 0-4 | x1 | 15.8 | 6.6 to spare |
| 5-9 | x1.25 | 19.7 | **2.7 to spare** |
| 10-14 | x1.5 | 23.7 | **1.3 short.** Sprinting the 751 blocks saves 0.9 real minutes (1.3 of clock), so it ends at about 0, with **no fold lap allowed** |
| 15-19 | x2 | 31.6 | cannot finish. Turn back: 610 blocks at sprint is 1.8 real minutes, 3.6 of clock |
| 20-24 | x3 | 47.3 | cannot finish. Turn back: 5.4 of clock |

The same shape as the Night Shift's (`DUNGEONS.md:587`): **5 affordable, 10 a gamble, 15 or more take it and run.**
The Street's own twist is that **the two folds after the Cut are where a greedy player loses**. One missed lit window
at x1.5 is the run.

At band 6 (slack 8.6) Palkia (about 6) and greed past x1.25 exclude each other, as Volcanion and greed do.

---

## 8. What the engine needs (E-S, new work; each named against the built core)

| # | Need | Why | Where today |
|---|---|---|---|
| E-S1 | **The clock per dungeon per band** (`dungeons[].clock_s_by_band`), keeping `engine.bands` for the caps | V3 computes a clock from each spine; one table cannot serve two spines | `data/dungeons.json:73-81` |
| E-S2 | **The `fold` kind**: twin copies from one description; fold-line box; per-slot fold state in the reset; door interactions; `random value` lit-house pick; no-deploy and dismount in the box | 5.1 | not built |
| E-S3 | **A per-segment ceiling** (`ceiling: "wall"` or `"barrier"`) and per-segment palettes | the open sky (5.2); the shell roofs every segment with the wall block | `tools/dungeon.py:522` |
| E-S4 | **`can_break` per dungeon and band**, from the seam table | the Cut's ores differ from the Night Shift's | `data/dungeons.json:125` |
| E-S5 | **The `lake` kind's `shape: "lane"`**: a horizontal swim under a later segment, its cache placed by swim distance | 6.4; V7 checks depth, not swim length | step 6 (not built) |
| E-S6 | **Board lines from the record**: the fold line, optional legs | the board's "Optional legs: none in this spine." is a literal | `tools/dungeon.py:575` |
| E-S7 | **Per-dungeon `parkour_recross_s`** | the return margin's constant is engine-wide | `data/dungeons.json:64-69` |

**Do not reorder `dungeons[]`.** Slots are numbered across every dungeon in list order (`tools/dungeon.py:185-195`,
*read*). Putting the Street before the Night Shift would move every built Night Shift shell. Append it.

The Street also needs everything the Night Shift's step 6 and 7 build: stands, seam, den, lake, parkour, per-segment
floor height, and the shell from segment kinds (`DUNGEONS.md:1184-1185`). It is not buildable before them.

---

## 9. Validation added (for `test-author`, not the builder)

| # | Check | Independent how |
|---|---|---|
| V17 | **Fold copies are block-identical** over the copy's whole volume, A against A' shifted by L, and no line of sight from the fold line reaches past its copy's dog-leg | read from the shell's generated fills, not from the fold description. Mutation, in the generator only: change one block in A' 's emission; V17 must fail |
| V18 | **Fold softlock:** with every fold closed, open, or open behind and closed ahead, the back rip is reachable from every walkable cell, and the far rip is reachable once every fold is open; the fold box catches only eastward entry (its box is wholly inside A') | BFS over the shell with the fold boxes as one-way edges |
| V3' | V3's path length counts each fold once through both copies, plus its read allowance | the shell |
| V7' | The lane's cache is at most 30 swim-blocks from air (path length through water) | the shell's water blocks |
| V19 | Every `barrier` ceiling is continuous over its segment and 3-4 above the parkour route; no open-sky segment leaves a gap a player can leave through | the shell |
| V8' | V8's light rule for roofed segments; open segments get skylight credit only if OS1 confirms it reaches the floor | `tools/light_plan.py` plus OS1 |

---

## 10. Rewards by band (`DUNGEONS.md` 9, *stands*; `trainer-balance-designer` sets items and weights)

| Leg | Paid how | Bands |
|---|---|---|
| Each stand | escrow: the band's area gems (1 / 1 / 2 / 2 / 3 / 3) plus a minor battle item | 1-6 |
| The Cut | real drops, the table in 7, capped per run (3.3) | 1-6 |
| The Belfry | real drops, the species' own (6.3) | 1-6 |
| The lane's cache | escrow: one progression item from the band's list | 2-5 (band 1 reaches it only at risk) |
| The Warden | escrow: the band's progression bundle (`DUNGEONS.md:856-860`) plus a battle-item roll | 1-6 |
| Palkia | the catch | 6 |
| First clear | advancement plus escrow | **band 5: one Rare Candy** (decided for every home, `DUNGEONS.md:864-866`). Band 2 (the first expected): **proposed** "something from the city that survived", for example a Soothe Bell, the belfry's one bell that did not fall. Others are `trainer-balance-designer`'s |

The candidate held items soothe_bell, shell_bell, amulet_coin and exp_share appear in no line of `data/markets.json`,
`data/traders.json` or `data/bank.json` (Grep, 2026-10-09). Whether each id exists in the 1.8.0 jar is **not read**.
The generator's fail-closed list (`DUNGEONS.md:849-851`) decides.

---

## 11. Multiplayer (`DUNGEONS.md` 6, *stands*)

- **Folds open per slot**, so in co-op one knock opens a fold for every member and a partner cannot be trapped in a
  lap.
- **Greed, the clock and Palkia are per member.** Co-op Palkia uses the cradle's ball check (`DUNGEONS.md:523-525`).
- Solo first (D16). Co-op waits on XD8.

---

## 12. Unknowns, as probes (run before the Street's engine work; the main session runs them)

| Id | Probe | Settles |
|---|---|---|
| **FX1** | In a test slot, a keeper relative `tp @s ~-48 ~ ~` on a player crossing a box, walking and sprinting: is the jump visible? Are rotation, sprint and momentum kept? Ten laps; then mounted (expect the dismount first); then with a sent-out Pokemon (expect the sweep) | 5.1 (fallback: the closed fold) |
| **OS1** | A slot segment with a barrier ceiling: what the sky looks like at the pocket's fixed noon, the skylight at the floor, and whether the y0 bedrock plane is visible from 95 above | 5.2, V8' |
| L2 | A wild battle underwater, with Dive (`DUNGEONS.md:1250`), already listed | 6.4 |
| XT1 | Fight timings (`DUNGEONS.md:1255`), already listed; add one timed lap of a fold | 7.1 |
| C1, P1, SG1, LO1, B3 | The core's owner halves (EXP-084, NOT_EXECUTED) | everything |

---

## 13. Build steps and cost (all ESTIMATES on `DUNGEONS.md:1166-1172`'s rates, not measurements)

**Prerequisites, none of which is this design's:** the owner has played the Night Shift (2026-10-09); the Night
Shift's steps 6-7 are built (legs, shell from kinds, per-segment floor height); **the live re-export carries the
Scar** (P1).

| # | Step | Agent | Estimate |
|---|---|---|---|
| 1 | FX1 and OS1 probe pack (beside any other new probes) | `minecraft-systems-dev`, narrow | 1.5-2.6M |
| 2 | Run them | main session + the owner | 1M |
| 3 | Rosters, the Warden's stages, the nest, escrow tables, first clears; the clocks re-derived from XT1 | `trainer-balance-designer` (opus) | 1.5M |
| 4 | The spine in data, palettes, the rip cell measured (section 3, items 1-5) | `world-content-dev` (data only) | 2M |
| 5 | E-S1 to E-S7 | `minecraft-systems-dev` | 2.6M (a new leg mechanic, `DUNGEONS.md:1204`) |
| 6 | Independent audit: V17-V19, V3', V7', V8'; mutate the generator | `test-author`, opus (escalation 1: the fold can trap a player) | 1.5-2M |
| 7 | Integration, staging run, the owner's look | main session | 1M |
| | **Total** | | **about 11-13M** (the base 7M of `DUNGEONS.md:1203`, plus the fold, plus the probes) |

---

## 14. Questions for the owner (OPEN; numbered S-Q)

1. **S-Q1. The fold: a seamless loop opened by knocking at the lit house?** *Recommend yes.* It is the Street's one new
   mechanic, legible ("rewards noticing, not searching"), and it costs clock only. The fallback is a plain door.
2. **S-Q2. Open sky over the street, at the pocket's fixed noon?** *Recommend yes*, if OS1 shows it reads well.
3. **S-Q3. The nest's head at cap+2** (the rest at 3.6's levels)? *Recommend yes*, under the 2026-10-09 standard.
4. **S-Q4. The rip waits for the live re-export that carries the Scar.** Staging can show it first. *No
   recommendation needed; noted so it is not a surprise.*
5. **S-Q5. What the folded street is** (an echo, a remnant, the city's missing piece) is the story's, still open in
   `DISPLACED_CITY_AND_SCAR.md` Q1 and Q3. The geometry here commits to none of them. *Codex's call*, through
   `docs/HANDOVER_CODEX.md`.
