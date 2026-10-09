# Dungeon 3: Under the Patriarch

**Status: DESIGN ONLY (content-architect, 2026-10-09).** Nothing here is built, placed, generated or run. **The
owner, 2026-10-09: build nothing past the Night Shift until the owner has played it.** This document makes dungeon 3 of
the six-dungeon list (`docs/mechanics/DUNGEONS.md:898`) ready to hand to builders when that changes.

It builds on `DUNGEONS.md` and does not reopen D1-D22 (`DUNGEONS.md:30-60`). Its sibling is
`docs/mechanics/DUNGEON_2_STREET.md`, and the two share engine needs (section 8). The engine it designs to is the built
core: `tools/dungeon.py`, `data/dungeons.json` and EXP-084, which is NOT_EXECUTED.

Labels are as `DUNGEONS.md:23-26`:
- **VERIFIED**: read in source, a jar read recorded in `docs/research/`, or a run, with the citation.
- **ASSUMED**: inferred, not checked.
- ***relayed***: taken from another document and not re-measured here. **No coordinate or ground height here was
  measured by this unit**, which has no shell.
- ***read***: read at the cited line on 2026-10-09.
- ***planning***: chosen for the arithmetic; XT1 replaces it.

---

## 0. Question and premises

**Question.** Design dungeon 3 at the Patriarch's foot, with Suicune in the lake and Yveltal as the boss, to the
Night Shift's level of detail. It must be unlike the Night Shift and unlike the Street, and must say what the engine
lacks.

| # | Premise | Finding |
|---|---|---|
| P1 | The Patriarch's foot at (4272, 3600) (`DUNGEONS.md:898`) | **The record exists:** `patriarch_wedge`, "an enormous flat-crowned dark oak on the crest of the Wedge, standing over the Rift". Centre (4272, 3600), ground_y 146.7 (`data/towns.json:2570-2585`, *relayed*). It is a landmark tree, and landmark trees are placed by the foliage paint (the Sentinel's record says so,
`data/towns.json:2566`, *read*; the Patriarch's own placement record is not read here). Its ground is **not measured by this unit.** |
| P2 | "Yveltal as the boss" | **Read as the approved table puts it:** "Yveltal's chain, catch at band 6" (`DUNGEONS.md:816`, D18). Pre-League bosses are fight-only NPCs (D8), and an NPC's Pokemon refuses every ball (`DUNGEON_PLACEMENT.md:44`, *relayed*). So Yveltal is **the band-6 last stage**, a wild key boss after an NPC chain. Bands 1-5 see it sealed and never fight it (section 6.2). This is an interpretation, and P-Q3 asks the owner. |
| P3 | Two catchable legendaries in one dungeon | **New to the design.** The Night Shift has one (Volcanion). Here Suicune (the lake, optional) and Yveltal (the boss, required at band 6) are both band-6 catches. The clock (section 7) is sized so that **Suicune, or a heal, fits in a band-6 run, rarely both**. |
| P4 | The engine can lay a spine that goes down | **No.** Every segment's floor is `floor_y` (`tools/dungeon.py:198-208`, *read*), the presence box starts at `floor_y - 1` (`:240`), and the return margin is linear in x (`data/dungeons.json:64-69`, *read*; `DUNGEONS.md:182-184`). The Night Shift's own spec already needs floor changes ("stairs down 20", `DUNGEONS.md:933`). The Patriarch needs a 48-block descent and a climb back (section 8). |
| P5 | Paradox threats at band 5 in "the late homes, Patriarch included" (`DUNGEON_PLACEMENT.md:145`) | **OPEN.** The paradox rule is unrecorded in `DUNGEONS.md` (`DUNGEON_PLACEMENT.md:20-22`). No paradox is designed in here. Section 6.2 marks the slot one would fill. |

---

## 1. Theme, and why it is here

**The fiction.** The Patriarch is the dark oak whose crown breaks the skyline over the Rift (`data/towns.json:2579-2580`,
*relayed*). In the rift, **the tree grew around something asleep.** Its taproot goes down into a clear pool, and the
roots drink from it. Something in the heart of the root mass has been feeding the tree for a very long time, and
everything near it is dying slowly. Suicune purifies the pool; Yveltal is the sleeper. In this place they are the
two halves of one rule: **the pool gives, the tree takes.** Yveltal's canonical rest as a cocoon in a tree is the
reason for the pick (`unhomed-legendaries-1.8.0.md:124`, `:263`, *relayed*: "Boss of Under the Patriarch (dark
forest); catch 45"). The story is Codex's. This design commits to the geometry and the trade.

**How it differs:**

| | The Night Shift | The Street | **Under the Patriarch** |
|---|---|---|---|
| Direction | level, a line along x | level, folded | **down: a 48-block descent; the way back is a climb** |
| Light | lanterns in the dark | open noon sky | **dim: glow lichen, shroomlight in the roots, the pool's light; never block light 0** |
| Greed | ore (the seam) | ore (the Cut) | **healing: the spring. Every drink costs a rung** |
| The lake | a shaft below a gantry | a lane under the street | **the pool at the foot of the descent, seen for the whole way down** |
| Boss | an NPC chain | an NPC chain | **an NPC chain whose band-6 last stage is a wild Yveltal (a key boss)** |
| Families | fighting, rock, ground | ghost, steel, psychic | **dark, grass, fungus, ghost** |

---

## 2. Gate and band coverage

- **`gate_flag: null`**, as `DUNGEONS.md:898` proposes. It is first reached at about gym 6-7 (*relayed*, there): the
  climb out of the Rift to the Wedge is the gate.
- **The expected first entry is band 4** (cap 50 or 55). Bands 1-3 are authored, because the engine requires an ace
  per band (`tools/dungeon.py:419-420`, *read*) and nothing stops an early climber. Expect them rarely.
- **Band 5** is the League window: NPC chain, no catch, and the paradox slot (P5) OPEN.
- **Band 6** has two catches: Suicune (optional) and Yveltal (the boss).
- **Sigils** are per band (`DUNGEONS.md:709-713`), unchanged.

---

## 3. The rip home and its evidence

**Where.** At the trunk's foot, between two roots, on the side of the glade the player arrives from: the climb up out
of the Rift. The rip reads as **the roots torn open**. The frame posts are root-wrapped dark oak, and the opening is
the dark beneath the tree. The palette is `world-content-dev`'s, with no portal block and no concrete.

**The coordinates are RELAYED and not measured here:**
- centre (4272, 3600), ground_y 146.7;
- the glade footprint x4242-4302, z3570-3630, ground 142.8-148.0, slope mean 3.6 and max 7.5
  (`data/towns.json:2583-2602`, *relayed*);
- the Rift landmark 54 blocks away (`data/towns.json:2609-2610`, *read*).

Town records are held to the canonical heightmap by `tools/validate_data.py` (`docs/STATE.md:197`, *relayed*). This
unit did not run it.

**What `world-content-dev` must measure (on `tools/ground.py` and our own records; never a world):**
1. **The tree's footprint from its records**, not from a world: its `data/foliage.json` landmark record and its kit's
   NBT extent (trunk, roots and the glade radius, `data/towns.json:2603`). The rip and its outside point must clear
   the tree's blocks, **and anything else our lists place there**: elder nests (`docs/STATE.md:102` mentions nests on
   elders), any Habitat Block in `data/habitat_blocks.json`, and any signpost. CLAUDE.md "Our list is not the world":
   say in the record what the check does not cover.
2. `round(ground(x, z))` over the 5-wide frame and an outside point 3-5 blocks out from the trunk, inside the glade,
   on slope at most 1 per block (the glade's max is 7.5 degrees, *relayed*, so a level cell exists but must be found).
3. **The Rift sculpt.** The sculpt writes the world, not the canonical heightmap, and `derived/rift_sculpt/` cannot be
   rebuilt today (CLAUDE.md, "So what actually cannot be delegated"). The tree is 54 blocks from the Rift landmark.
   If any column of the rip cell or outside point is in the sculpt's footprint, `tools/ground.py` does not describe
   the world there. **Choose a cell the sculpt's plan data does not touch**, checked against that plan, not a world.
4. **That the Patriarch is in the live world.** STATE counts "5 painted giants ... 4 landmark trees" (`docs/STATE.md:102`,
   *relayed*). Confirm this tree is one of them in the live world, not only in staging.
5. **Sight.** The rip need only read from inside the glade, 61 across, which is within the particles' 48-block range
   (`data/dungeons.json:40`, *read*). The plume is optional here, unlike at the Scar.

---

## 4. The spine, segment by segment (x increases from the entry; the floor falls in segment 5)

| # | Segment | Kind | Spine blocks (walked) | x footprint | Contents |
|---|---|---|---|---|---|
| 0 | The Root Door | `entry_room` | 16 | 16 | arrival at `floor_y` (96); the back rip; the board; the threshold |
| 1 | The Crown Roots | `drift` | 240 | 240 | 3-5 wide, winding in z; bark, rooted dirt and dark oak; glow lichen |
| 2 | The Forager's stand | `stand` | 24 | 24 | a fungus-lit hollow |
| 3 | The Hollow Way | `drift` | 220 | 220 | through dead heartwood; the first glimpses of the pool's light ahead |
| 4 | The Crowkeeper's stand | `stand` | 24 | 24 | a roost under a root arch |
| 5 | **The Taproot** | **`descent`** | 260 | 33 | a vertical bore 33 across; a 3-wide spiral ledge on its wall drops 48 in about three turns; inner rail 2 high (root, barrier-backed); the pool fills the bore's foot |
| 5a | The Clear Pool | `lake`, **shape `well`**, at 5's foot | 0 | (inside 5) | section 6.4 |
| 6 | The Pool Spring | **`spring`** | 12 | 12 | at the pool's rim, `floor_y - 48`; the first spring; the ladder board |
| 6a | The Absol Hollow | `den`, off-spine | 0 | 0 | the nest (6.3) |
| 7 | The Root Bridges | `parkour` | 160 | 160 | 4 sections of 40 over the dark under the tree: hanging root tangles, level overall, rises at most 1; catch band 6 below; a root ceiling 3-4 above |
| 8 | The Deep Galleries | `drift` | 260 | 260 | wide, low, roots like pillars |
| 9 | The Pruner's stand | `stand` | 24 | 24 | among cut root ends |
| 10 | The Heartwood | `drift` | 200 | 200 | the roots thicken; everything is dying; Murkrow perched (dressing only) |
| 11 | The Heart Spring | `spring` | 12 | 12 | the second spring, at the Heart's door |
| 12 | The Heart | `boss_arena` | 35 | 35 | 31 x 35 x 16; the cocoon at the far third (6.2) |
| 13 | The Root Gate | `exit_room` | 16 | 16 | the far rip |
| | **Total** | | **1,343 walked + 160 parkour** | **1,276** | inside a 2,048 strip; floors at y96 (0-5 top) and y48 (5 foot to 13) |

**The descent is the Patriarch's shape.** Everything after segment 5 lies 48 below the entry, so **turning back
means climbing the Taproot**. The return margin knows this (section 5.3). The board adds:
- "The way back is up: the Taproot is a climb."
- "Every drink from a spring tightens the rift. The Heart's spring is still once the fight begins."
- "No Pokemon past the cracked roots" (the parkour, `DUNGEONS.md` 3.4).

**Rejected: the jump.** With an open inner edge, a player could drop 48 into the pool and skip the descent. Falling
into water does no damage (vanilla, ASSUMED), but a short step off would land on the ledge a turn below. That is a
fall death, which the parkour rule (`DUNGEONS.md:473-475`) forbids elsewhere. The rail closes it, and V20 proves it.

---

## 5. What is new

### 5.1 The spring: greed by healing (the Patriarch's signature)

**What the player sees.** At the pool's rim, and again at the Heart's door, a root basin brims with the pool's clear
water. A click: "The water is clean. The rift tightens." The party is healed, the bar steps up a rung, and the sound
of 3.3's threshold plays. The board beside each basin shows the ladder with **one drink = one rung**.

**Mechanism** (Cobblemon native command plus vanilla interactions; the functions rung):
1. An **interaction** at each basin, using the arch click pattern that `door_click` uses (EXP-034, `DUNGEONS.md:656`).
2. The click checks, in order: a member of this slot; `q.player.in_battle` at 0; at the Heart Spring only, the
   member's boss chain not begun (`dg.stage` 0, `tools/dungeon.py:89`, *read*). A refusal prints "The spring is
   still."
3. Then **`healpokemon @s`**, the command the blackout already uses for its party heal (`tools/blackout_pack.py:307`,
   *read*; in game it heals on arrival, `docs/research/DUNGEON_DEATH.md:43`, *relayed*). Whether it restores PP and
   status as well as HP is ASSUMED until **SP1**.
4. Then **five takes** into the greed ladder through the built entry point `cobblers:dungeons/greed/take`
   (`data/dungeons.json:245`, *read*). That is one rung of D13's ladder (5 / 10 / 15 / 20). D13 is not changed: the
   heal is priced in its units.
5. **No `cobblemon:healing_machine` block anywhere in a shell.** Using one fires the blackout's checkpoint
   advancement (`tools/blackout_pack.py:16-17`, `:159-162`, *read*: `any_block_use` on
   `cobblemon:healing_machine`), which would make a point inside a slot the player's respawn checkpoint. That is a
   **cross-system collision**, and it gets a contract (section 9).

**Why heals, not ore.** The Night Shift and the Street sell time for loot. The Patriarch sells time for survival:
the same ladder, a different question. **Where** you drink matters as much as how often, because a rung costs the
real time left after it (7.2). It is also the run where `DUNGEONS.md` Q5 ("healing in a run: none provided",
`:1282-1284`, OPEN) is answered by a price instead of a ban. P-Q1 asks the owner.

**No ore seam, and no rift pick.** Nothing in the Patriarch is mined, so the pick is not given (E-P5) and the run stays
in adventure mode. The economy gets no supply from this dungeon. V16's self-funding rule holds vacuously. If the owner
wants ore in every run (P-Q2), the fallback is a **root seam** of 12 blocks in the Deep Galleries, with the Night
Shift's 9.3 table and the same ladder: heals and ore then share one count.

### 5.2 The descent

- **Kind `descent`**: a vertical bore with a spiral ledge, whose walked length (about 260, *planning*: three turns at
  a radius of about 13.5) is packed into a 33-block x footprint. It drops 48 at about 1 in 5.4, by stairs and slabs.
- **Walkable both ways.** Every step rises at most 1, with 3 of headroom. The inner rail is 2 high.
- **The pool from above.** The ledge looks down onto the pool the whole way, so Suicune, asleep and glowing on the
  bed, is in view for about a minute and a quarter of walking. That is the Patriarch's "obvious".
- **Paces** (*planning*, for XT1 to replace): down at 3.5 blocks a second, up at 2.5.

### 5.3 The return margin with a climb

The built margin is `back_s = (x - x_back) x 10 / 56` plus a constant (`data/dungeons.json:64-69`, *read*). In the
Patriarch, x is not distance and the way back climbs. **Replace it with a per-segment table**, computed by the
generator from the shell: for each segment, the seconds from its east door to the back rip at sprint on the level
and at climb pace on rises. The keeper then needs only `back_s = table[segment] + (x_end - x) x 10 / 56` within the
segment. The Night Shift and the Street use the same table, with their parkour constant folded in. V21 holds it to
the built shell.

---

## 6. The legs

### 6.1 Stands (families, not teams; rosters are `trainer-balance-designer`'s; member counts `DUNGEONS.md` 5.3)

| Stand | Character | Families | By band |
|---|---|---|---|
| 2 | **The Forager**, who eats what grows on the dying | Foongus line, Morelull line, Paras line | evolved from band 3 (Amoonguss, Shiinotic, Parasect) |
| 4 | **The Crowkeeper**, who feeds the birds that wait | Murkrow line, Vullaby line | Honchkrow and Mandibuzz from band 4 |
| 9 | **The Pruner**, who cuts the roots back and loses | Seedot line, Phantump line | Shiftry and Trevenant from band 4 |

### 6.2 The boss: the Rootkeeper's chain, and Yveltal

**Bands 1-5: an NPC chain, fight-only (D8).**
- The Rootkeeper's **ace is the Deino line**: Deino at bands 1-2, Zweilous at 3-4, Hydreigon at 5-6. It is the hunger
  the sleeper draws.
- **Escort from band 4: Spiritomb**, a keystone bound into a root.
- Three stages at the band's lower cap -2, -1 and 0 (`data/dungeons.json:207-209`, *read*).
- **The paradox slot (P5, OPEN):** if the owner adopts the paradox rule, the band-5 escort is the place for it. Iron
  Jugulis (dark/flying, the future Hydreigon) fits the chain. Its model is DP-only (*relayed*,
  `unhomed-legendaries-1.8.0.md:305-307`). It waits on the rule.
- **The cocoon is visible at every band**, at the Heart's far third behind a root lattice: Yveltal, dressed asleep and
  bound like the lake legendaries (`PoseType: SLEEP`, `NoAI`, `PersistenceRequired`, glowing; 3.7's dressing). It is
  `uncatchable` and carries the exempt tag. When stage 3 falls at bands 1-5, the line is "It does not stir for you
  yet."

**Band 6: stages 1 and 2 are the NPC; stage 3 is Yveltal, wild.**
1. When stage 2 falls, the keeper plays the cue ("The roots let go."), removes the sleeping display, and spawns a live
   Yveltal by macro `spawnpokemonat` at **level 100**. That is **at the band-6 cap of 100**: the cap refuses only a
   target strictly above it (`DUNGEON_PLACEMENT.md:43`, *relayed*).
2. In the same function it is bound, leashed, tagged `cobblers.key_boss` and listed in `data/key_ball.json`
   `bosses`, so **only a Beast Ball catches it, at x5**, and every other ball is refused and handed back
   (`data/key_ball.json:5`, `:13-16`, *read*). It also gets `claims.exempt_tag` (`DUNGEONS.md:232-234`).
3. **The stage ends on its faint or its capture.** Either opens the exit gate and sets the boss escrow. This is
   Entei's catch-or-defeat pattern (`tools/entei_boss.py`, *relayed*; EXP-059 NOT_EXECUTED), new to the chain:
   probe **YV1**.
4. **Catch once per player** (the `pokemon_captured` advancement). In later band-6 runs, stage 3 is **farm-mode
   Yveltal**: uncatchable and still key-tagged, as Entei's farm mode is (`data/key_ball.json:31`, *read*). The fight
   still stands between the player and the exit.
5. A flee leaves Yveltal standing, leashed, and the player re-engages it. The engine's idle restart
   (`data/dungeons.json:43-44`, *read*) is for NPC stages and does not apply to a wild one.

Yveltal's catch rate is 45 (*relayed*, note row 124), against Entei's and Suicune's 3, so it takes far fewer throws.
The throw count is the research note's formula's to give, not this design's. **Mega Showdown is world-critical** for
Yveltal and Suicune (`DUNGEONS.md:808-810`).

### 6.3 The nest: the Absol Hollow (optional)

**A creature, and a place that suits it.** Absol come where disaster is coming. A hollow off the Pool Spring holds a
pack of four, watching the Heart. They are uncatchable, never alpha, carry the exempt tag, and are spawned on entry
(`DUNGEONS.md` 3.6, *stands*). Their drops are the species' own, **not read**: `trainer-balance-designer` reads the
1.8.0 table. The fallback nest is the Zorua line ("the ones that wear the dead's faces").

**Levels: P-Q5**, the same question as the Street's S-Q3: the head at cap+2 under the owner's 2026-10-09 nest standard,
the rest at 3.6's cap-2 to cap-1.

### 6.4 The legendary leg: Suicune in the Clear Pool

- **Shape: a well under a descent.** The pool fills the Taproot's foot: 27 across inside the ledge, 24 deep
  (*planning*). It is the clearest water in the run, with no particles but a slow bubble column over the bed (3.7's
  dressing, L1).
- **The cache** is on a root shelf at **20 deep** (within the 30 Surf reach, `DUNGEONS.md:490-493`, *relayed*).
- **Suicune rests on the bed under the membrane**: a barrier dome over a hollow in the roots, dressed with particles.
  Bands 1-5: always closed ("It does not stir for you yet."). Band 6: open only to a Dive-qualified member (3.7,
  unchanged).
- **Band-6 catch:** level 100, at the cap; a key boss (Beast Ball only, x5); exempt tag; bound; catch once per
  player. All as 3.7. Catch rate 3 (*relayed*, note row 101).
- **The battle is underwater** (L2). The fallback is a dry hollow behind the membrane (`lake_grotto`,
  `DUNGEONS.md:520-522`).
- **Climbing out:** every point of the pool's surface reaches the Pool Spring's rim without a rise above 1. Without it
  the pool is a pit (V20).

---

## 7. The clock and greed

### 7.1 The clock (minutes; paces *planning*, `DUNGEONS.md` 4.1 plus 5.2's descent)

- **Walk:** 1,083 level blocks / 4.0 = 4.51, plus the Taproot's 260 / 3.5 = 1.24, so **5.75**.
- **Parkour:** 160 / 1.5 = 1.78, plus 2 falls at 35 s, so **2.95**.
- **Cues:** 0.5. There is no dig, so no free tier.
- **Fixed part: 9.20.**
- **The band-6 boss** is 9.0 plus 3.0 for stage 3's Yveltal and its throws (*planning*), so 12.0.

| Band | 3 stands | Boss | Fixed | **Required** | **Clock = ceil(x 1.25)** | Slack |
|---|---|---|---|---|---|---|
| 1 | 6.0 | 6.0 | 9.20 | 21.20 | **27** | 5.8 |
| 2 | 7.5 | 6.5 | 9.20 | 23.20 | **29** | 5.8 |
| 3 | 7.5 | 7.0 | 9.20 | 23.70 | **30** | 6.3 |
| 4 | 9.0 | 7.5 | 9.20 | 25.70 | **33** | 7.3 |
| 5 | 10.5 | 8.0 | 9.20 | 27.70 | **35** | 7.3 |
| 6 | 12.0 | 12.0 | 9.20 | 33.20 | **42** | 8.8 |

The lockout (60 minutes) exceeds the longest clock (42), so V12 holds. Band 2's 23.20 x 1.25 is exactly 29.0.

### 7.2 Greed by healing, worked (band 4, clock 33: the expected first band)

At the Pool Spring a player has walked 524 level blocks (2.18) and the Taproot (1.24), fought two stands (6.0) and
spent 0.3 on cues: **9.72 minutes**, leaving **23.28** on the clock. From the Pool Spring to the end is **15.98 real
minutes**: 559 blocks (2.33), the parkour (2.95), one stand (3.0), the boss (7.5) and cues (0.2). From the Heart Spring
to the end is **7.86**: 63 blocks (0.26), the boss (7.5) and cues (0.1).

A rung bought at the Pool Spring is paid on 15.98 minutes; at the Heart Spring, on 7.86.

| Drinks (Pool, Heart) | Speed after each | Clock the rest needs | Outcome |
|---|---|---|---|
| 0, 0 | x1 | 15.98 | 7.3 to spare |
| 0, 1 | x1 to the Heart, then x1.25 | 8.12 + 9.83 = 17.95 | **5.3 to spare**: the cheap heal |
| 1, 0 | x1.25 from the pool | 19.98 | **3.3 to spare** |
| 1, 1 | x1.25, then x1.5 | 10.15 + 11.79 = 21.94 | **1.3 to spare** |
| 0, 2 | x1, then x1.5 | 8.12 + 11.79 = 19.91 | **3.4 to spare**: two drinks, both late |
| 2, 0 | x1.5 from the pool | 23.97 | 0.7 short; sprinting the 559 blocks saves 1.0 of clock, so it ends with about 0.3 and no fall to spare |
| 1, 2 or 0, 3 | x2 at the Heart | 25.87 / 23.84 | **cannot finish**: the boss cannot be sprinted |

So **one drink is cheap, two are affordable if late, and three are the run.** A player who heals at the pool because
the crows hurt them pays twice what a player who waits for the Heart pays. A player turning back after a drink climbs
the Taproot: about 3.3 real minutes from the Pool Spring (524 blocks at sprint and 260 at climb pace).

**At band 6** (slack 8.8), Suicune (about 6, `DUNGEONS.md:526-527`) leaves about 2.8. A single late heal costs about
12.36 x 0.25 = 3.1, so it does not fit with Suicune. **The pool or the spring, rarely both.** That is the place's
trade, purification or survival, and the board says it.

---

## 8. What the engine needs (E-P; with the Street's E-S where shared)

| # | Need | Why | Where today |
|---|---|---|---|
| E-P1 | **Per-segment floor height** (`floor_dy`) and the **`descent` kind** (a spiral packing its walked length into a small x footprint) | 4, 5.2. The Night Shift's real spine also needs floor changes (`DUNGEONS.md:933`, `:941`) | all floors at `floor_y`: `tools/dungeon.py:198-208` |
| E-P2 | **A shell below `floor_y`**: the presence box, the height check and the strip clear generalised to each segment's floor | the run lives at y48 and the pool's bed at about y24 | `tools/dungeon.py:240`, `:324`; `data/dungeons.json:27-29` |
| E-P3 | **The return margin as a per-segment table** with a climb pace | 5.3 | `data/dungeons.json:64-69` |
| E-P4 | **The `spring` kind**: interaction, refusals, `healpokemon @s`, five takes, cue | 5.1 | not built |
| E-P5 | **No rift pick where a dungeon has no seam** (an empty `can_break` gives none); adventure stays | 5.1 | the pick is engine-wide: `data/dungeons.json:120-128` |
| E-P6 | **A `wild` boss stage**: band-scoped (band 6 stage 3); spawn, bind, key tag and exempt tag in one function; faint or capture ends the stage; catch-once; farm mode after | 6.2 | `boss_classes` builds NPC stages only: `tools/dungeon.py:483-502` |
| E-P7 | **A sealed display legendary** at every band (the cocoon), shared with 3.7's lake dressing | 6.2 | step 6 (the lake), not built |
| E-S1 | **The clock per dungeon** (the Street's) | 7.1 | `data/dungeons.json:73-81` |
| E-S6 | **Board lines from the record** (the Street's) | 4 | `tools/dungeon.py:575` |

**Append the Patriarch after the Street in `dungeons[]`.** Slots are numbered across dungeons in list order
(`tools/dungeon.py:185-195`, *read*), so inserting it earlier would move every built shell.

It also needs all of the Night Shift's steps 6-7: stands, den, lake, parkour, and the shell from kinds
(`DUNGEONS.md:1184-1185`).

---

## 9. Validation and contracts (for `test-author`, not the builder)

| # | Check | Independent how |
|---|---|---|
| V20 | **Descent and pool:** every spiral step rises at most 1 in both directions with 3 of headroom; the inner rail is 2 high and continuous (no fall from the ledge to anything below); every pool surface cell reaches the rim with no rise above 1; the cache is at most 30 deep | BFS over the generated shell. Mutation, in the generator only: drop one rail block; V20 must fail |
| V21 | **The return table** equals the BFS back-path time over the shell at sprint on the level and climb pace on rises, for every segment | the shell, not the spine list. Mutation: lengthen the spiral in the generator; V21 must fail |
| V22 | **Springs:** each refuses in battle and while its member's chain is begun (Heart only); each adds exactly 5 to `dg.greed`; **no shell contains `cobblemon:healing_machine`**; the heal runs only for a member of that slot | the generated functions and the shell's blocks |
| V23 | **Wild stage:** only at band 6, stage 3; level at most the band's lowest cap (100); the key tag and the exempt tag in the same function as the spawn; Yveltal and Suicune are both in `data/key_ball.json` `bosses`; each has its own catch-once advancement; the farm mode is uncatchable | the generated functions and `data/key_ball.json`, not `tools/dungeon.py`'s own list |
| V3' | V3 with the descent's walked length and paces | the shell |

**New contract** in `data/system_contracts.json`: **"a dungeon heal never sets a blackout checkpoint"**. The owner is
the dungeons; the consumer is the blackout's checkpoints (`tools/blackout_pack.py:16-17`, `:159-162`). V22 enforces
it, and a `test_contract_*` test is written with it (`.claude/rules/testing.md`, cross-system contracts).

---

## 10. Rewards by band (`DUNGEONS.md` 9, *stands*; items and weights are `trainer-balance-designer`'s)

| Leg | Paid how | Bands |
|---|---|---|
| Each stand | escrow: area gems (1 / 1 / 2 / 2 / 3 / 3) plus a minor battle item | 1-6 |
| The springs | **nothing**: a heal is its own reward | 1-6 |
| The Absol Hollow | real drops, the species' own | 1-6 |
| The pool's cache | escrow: one progression item from the band's list | 2-5 (band 1 only at risk) |
| The Rootkeeper | escrow: the band's progression bundle (`DUNGEONS.md:856-860`) plus a battle-item roll | 1-6 |
| Suicune, Yveltal | the catches, once each per player | 6 |
| First clear | advancement plus escrow | **band 5: one Rare Candy** (decided for every home, `DUNGEONS.md:864-866`). Band 4 (the first expected): **proposed** "something the roots kept". Candidates in no line of `data/markets.json`, `data/traders.json` or `data/bank.json` (Grep, 2026-10-09): black_glasses, spell_tag, cleanse_tag, dragon_fang. Whether each id exists in the 1.8.0 jar is not read; the fail-closed list decides (`DUNGEONS.md:849-851`) |

**No ore seam means a smaller material payout** than the Night Shift's at the same band. The escrow and the bundle are
unchanged. That is the cost of the heals and is P-Q2.

---

## 11. Multiplayer (`DUNGEONS.md` 6, *stands*)

- **Springs are per member.** Each drink moves only the drinker's clock (D16), and the refusals read the drinker.
- **Yveltal and Suicune: one per member who has not caught each**, each tagged with its member, with the cradle's
  ball check (`DUNGEONS.md:523-525`, `:638-639`).
- **The Heart's gate opens when every member present has finished their own stage 3**, whether by faint or catch
  (`DUNGEONS.md:629-632`).
- Solo first (D16). Co-op waits on XD8.

---

## 12. Unknowns, as probes

| Id | Probe | Settles |
|---|---|---|
| **SP1** | `healpokemon @s` from an interaction click in adventure mode, in `cobblers:pocket`: HP, PP and status restored? Refused mid-battle by our check? Confirm no blackout checkpoint moves | 5.1 |
| **YV1** | A chain whose stage 3 is a wild key boss: an NPC stage-2 victory spawns it (macro) and binds it; a faint ends the stage; a Beast Ball capture ends the stage; a Great Ball is refused and returned; catch-once and farm mode on the next run | 6.2 |
| **DS1** | Time a 48-block spiral down and up, walking and sprinting (an XT1 addition) | 5.2, 5.3, 7 |
| L1, L2 | Seen from above through clear water, and a battle underwater (`DUNGEONS.md:1249-1250`) | 6.4 |
| C1, P1, SG1, LO1, B3 | The core's owner halves (EXP-084, NOT_EXECUTED) | everything |

---

## 13. Build steps and cost (ESTIMATES on `DUNGEONS.md:1166-1172`'s rates; nothing here is measured)

**Prerequisites:** the owner has played the Night Shift; the Night Shift's steps 6-7 are built; the Street's E-S1
(the per-dungeon clock) exists, or this unit builds it.

| # | Step | Agent | Estimate |
|---|---|---|---|
| 1 | SP1, YV1 and DS1 probes | `minecraft-systems-dev`, narrow | 2.6M |
| 2 | Run them | main session + the owner | 1M |
| 3 | Rosters, the chain, Yveltal's stage and farm mode, the nest, escrow, first clears; clocks from XT1 and DS1 | `trainer-balance-designer` (opus) | 2M |
| 4 | Spine data, palettes, the rip cell measured (section 3, items 1-5) | `world-content-dev` (data only) | 2M |
| 5 | E-P1 to E-P7 | `minecraft-systems-dev` | 4M (two new mechanics and a new stage type) |
| 6 | Independent audit: V20-V23, V3'; mutate the generator | `test-author`, opus (escalation 1: the descent can trap, the wild stage gates the exit) | 2-3M |
| 7 | Integration, staging run at bands 4 and 6, the owner's look | main session | 1M |
| | **Total** | | **about 14-16M**, against the 7M base of `DUNGEONS.md:1203`: the descent and the wild stage are engine work the Street does not pay for |

---

## 14. Questions for the owner (OPEN; numbered P-Q)

1. **P-Q1. Healing as greed:** two springs; each drink heals the party and costs one rung of the ladder; the Heart's
   spring is still once the fight begins. *Recommend yes.* It answers Q5 for this dungeon by a price rather than a
   ban.
2. **P-Q2. No ore seam in the Patriarch** (heals instead)? *Recommend yes.* The fallback is a 12-block root seam that
   shares the count.
3. **P-Q3. Yveltal as the band-6 third stage of the Rootkeeper's chain**, wild and Beast Ball only, catch once, then
   farm mode; seen sealed at bands 1-5? *Recommend yes.* This reads D18's "Yveltal's chain, catch at band 6".
4. **P-Q4. The paradox slot:** Iron Jugulis as the band-5 escort, if the paradox rule is adopted
   (`DUNGEON_PLACEMENT.md` C1, OPEN). *No recommendation until the rule is decided.*
5. **P-Q5. The nest's head at cap+2**, as the Street's S-Q3. *Recommend yes.*
