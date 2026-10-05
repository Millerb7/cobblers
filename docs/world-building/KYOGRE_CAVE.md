# The Kyogre cave behind Coldwater's sealed arch, and the weather trio

**Status:** PROPOSED design (content-architect, 2026-10-05). Nothing here is built. Section 6 is no longer a
recommendation: the owner committed the trio the same evening (below). Every Cobblemon or addon behaviour this design
relies on is either cited as VERIFIED or listed in section 8 as an experiment that comes first (principle 15).

**The owner, 2026-10-05:**
- "for the kyogre research, make them looking at a dive portal underwater, that will later tp the player to a kyogre
  cave" (`data/coldwater_station.json:8`).
- "The Kyogre cave needs a design tonight ... people will care about it" (`docs/PLAYTEST_2026-10-05.md:95`).
- On the trio: "groudon should be deep in a volcano below some lava or something a player wouldn't be able to get to
  easily and rayquaza probably on a sky island from a relic portal like kyogre" (relayed by the coordinator; not yet
  recorded in a repo file, so it should go into `docs/STATE.md` "What is decided" when this lands).
- Standing rulings respected here: **Shrew Station stays with Latios and Latias** (not moved or repurposed); **Megas stay
  uncatchable for now**, so no wild Mega and no wild Primal appears anywhere in this design.

**Documents this supersedes or that now disagree:**
- `docs/world-building/STRUCTURE_DECISIONS.md:176`: Groudon "framed as the mountain's sleeper, not half of a weather
  duel".
- `STRUCTURE_DECISIONS.md:182`: "the trio collapses without all three".
- `STRUCTURE_DECISIONS.md:209` and `docs/world-building/DIMENSIONS_AND_BORDERS.md:342`: Rayquaza at the End spawn is an
  open call; section 6 gives it a recommended default.
- `docs/mechanics/WATER_MAP.md:239, 310` already carry the Kyogre supersession note.
- `data/legendaries.json:503`: Groudon's gate is "PROPOSED, NOT DECIDED"; section 6 proposes changing its geometry.

Reconciling those lines is a follow-up edit for whoever lands this design. This document does not edit them.

---

## 0. The design in one paragraph

Coldwater's three researchers turn the sealed arch from a curiosity into a quest. In four beats it opens for a diver
with eight badges. The arch crosses into a **shared, co-op cave in the pocket dimension** (`cobblers:pocket`), built as
one descent of about 180 blocks:
- a flooded vertical shaft (the Sounding);
- three dark galleries whose lamps must be lit;
- a flooded hall drained by a tide wheel;
- a 128-block trench;
- the Basin, where Kyogre sleeps in a pool.

**Kyogre is level 60, once per player and keyed on the catch.** The Basin always holds a sleeper. Any qualified player
who has not caught one can wake it; a catch records that player and the keeper lays a new sleeper down. Rewards are
per-player claim pedestals. They become instanced chests if the owner adds that mod. The catcher's pedestal holds the
Blue Orb, if research confirms Mega Showdown has one. Rain falls on the overworld while Kyogre is awake.

Groudon is reworked as a lava-lidded vent under the Craters. Rayquaza waits on a sky island behind a sealed relic sky
arch, after the Champion, for a player who has met both.

---

## 1. The fiction

### What Coldwater has found (already built as dialogue)

- **The arch.** Old stone, a sheet of dark glass, and lamps "lit before any of us were born", 9 blocks down under a red
  buoy (`data/coldwater_station.json:281`). Calder: "It isn't locked the way a door is locked. It's waiting"
  (`:291`).
- **The cold ring.** The sea freezes over the arch in a ring and nowhere else, and "Water that cold should sink. This
  rises" (Rask, `:315`).
- **The legend.** "The sea was made, not found ... This is the only coast where the story has a door" (`:320`).
- **The stillness.** The boatman swears the water goes still over the arch (Moss, `:344`).
- **The sealed message.** "Something beyond it is very large, and asleep" (`:75`).

### Why it matters to the region

Proposed. The story line is Codex's (`docs/story/ARC.md`); these are hooks, not final text.
- The region is a place assembled by forced exchanges (ARC Act III, "The cost of repetition", `ARC.md:407`). The Rift is
  "accumulated damage rather than a natural landmark" (`ARC.md:448`).
- **Hook:** the exchanges have been tearing at the ground and the sea for years, and two sleepers under this region
  feel it.
- The Craters climax at gym 7 sets `crater_operation_stopped` (`ARC.md:48`). It is the moment the mountain's sleeper
  turned over. The sea's sleeper answered: the cold ring froze twice in a week, both times on days the Craters shook.
- This gives the station a reason to care about the Craters and points both legendaries at each other. It does not
  supply any fact the critical path needs (ARC narrative rule 7, `ARC.md:69-70`).
- Kyogre does not replace Lugia, who stays the post-game apex of the open sea (`data/legendaries.json:533-596`,
  blocked). Kyogre is the region's own sea sleeper, found through a station, not a trench.

### How the player is drawn in: the quest `coldwater_kyogre`

Fields are `quest.coldwater_kyogre.<field>` (STATE "Quest namespaces"). Flags are progression flags declared in
`data/progression.json` and granted as `cobblers:flag/<id>` advancements. A dialogue can test a flag
(`tools/compile_dialogue.py:28-31`), run a pack function as the player (`:36-37`) and give a reward once (`:22`).

| Stage | Who | Condition | Beat | Sets |
|---|---|---|---|---|
| 0 Lead | all three | none (the station is reached by the Northlight packet, $400, `gym5_cleared`, `coldwater_station.json:361`) | Exists today. | cursors only |
| 1 Sounding | Rask | the `cobblers.dive` tag (`data/portals.json:32-34`), read through a `player_tag` condition (`compile_dialogue.py:32-35`) | "Take a reading for me. Put your hand on the sheet and tell me what it does." The arch's existing `portal/touch` already refuses non-divers. A diver's touch now grants flag `kyogre_arch_sounded` and prints "The sheet is cold enough to burn. Under your hand, something turns over in its sleep." Back at Rask: Dive Balls, given once. | `kyogre_arch_sounded` |
| 2 Two sleepers | Moss, then Calder | `kyogre_arch_sounded` and flag `crater_operation_stopped` | Moss has laid a third bearing on the theodolite: the Craters. Calder ties the two ring freezes to the crater tremors and names Groudon as the other sleeper. This is the trio's first cue (section 6). | quest field `two_sleepers=1` |
| 3 The key | Calder | `two_sleepers` and flag `gym8_cleared` | "The lamps on the arch were lit once. I think it opens for someone who has shown the sea they can keep up with it." Her dialogue runs `cobblers:kyogre_cave/attune` as the player. It telegraphs the fight (vision: "Bosses telegraph their strategy", `docs/vision/GAME_VISION.md:178`): "It brings the rain with it. Bring something that doesn't mind getting wet." | flag `kyogre_arch_open` |
| 4 After | Calder, Rask | flag `kyogre_caught` (or `kyogre_met` without a catch) | Epilogue. Rask: the ring didn't freeze this winter. Moss: "The theodolite keeps wanting to point up." This is the Rayquaza lead. | cursors |

The arch's destination function opens for a clicking player who has all three of: the dive tag (checked by `touch`
already), `gym8_cleared`, and `kyogre_arch_open`. Otherwise it keeps today's sealed message. The gate is per player, so
a friend who has not done the beats cannot follow through. Open question 3 asks whether that is wanted.

---

## 2. When: the gate, the level, and why not after the League

**Recommended: `gym8_cleared` plus Dive plus `kyogre_arch_open`, Kyogre at level 60.**

- **The owner's cap decision.** "After gym 8 the cap stays at 60 ... a player with eight badges can collect and
  prepare" (`docs/mechanics/LEAGUE_LEVEL_CAP.md:3-5`).
  - The legendary rule is that each legendary sits at the cap band of its gate's badge
    (`data/legendaries.json:52, 85-95`).
  - At 8 badges the bound is 60 (`legendaries.json:46`). A Pokemon strictly over the thrower's cap breaks free from
    every ball (`:35`).
  - So level 60 is the highest catchable level at this gate, and it is Groudon's and Regigigas's level too
    (`:492, :443`). Kyogre and Groudon as a pair at the same gate and level is the trio's shape (section 6).
- **Why not post-game.** A post-game gate (`champion_cleared`, level 70-75, cap 100, `legendaries.json:97`) would be
  catchable and would mirror Lugia (`:537`). But:
  - it would leave the eight-badge "collect and prepare" window with Groudon and nothing from the sea;
  - Rayquaza is the better post-game capstone (section 6).
  - The cost of the earlier gate: a level-60 Drizzle Kyogre is a strong Elite Four tool. That is the same trade
    already accepted for Groudon and Regigigas. Open question 2.
- **Wild levels in the cave.**
  - Most wild Pokemon sit at 50-58, under the cap.
  - The three alphas sit at 58-62, a few above the cap. That fits the owner's rule that above-cap Pokemon are welcome at
    a place's focal points, "in balance" (`docs/STATE.md:134`).
  - Alphas are a native PokemonProperties key (`docs/mechanics/ENCOUNTER_DESIGN.md:306-315`).
  - The species and exact numbers are trainer-balance-designer's (section 3, "Dangers").

---

## 3. The place

### Pocket dimension, not carved in place (ADR-004)

ADR-004 carves in place what the fiction says is "right there". It uses the pocket dimension for spaces "bigger than
their entrance, or instanced per player", which "**are** elsewhere" (`docs/decisions/ADR-004-pocket-spaces.md:29-34`).
The pocket dimension is the right home here, for five reasons:

1. **The fiction is a crossing.** The owner said "tp the player to a kyogre cave" (`coldwater_station.json:8`). The arch
   is a sheet of glass that "won't open", not a tunnel mouth. Every dive arch in the game already crosses into
   `cobblers:pocket` (`data/portals.json:4-5`), so the loading screen belongs to the story (`ADR-004:32-34`).
2. **It is far bigger than its entrance.** The cave is about 260 by 300 blocks and 180 tall. The arch is a 5 by 5 apron
   on a sea floor 9 deep (`coldwater_station.json:63`).
3. **Carving it in place costs more and protects less.** The site is inside the `coldwater_crossing` ferry lane, which
   the sea packs keep clear (`coldwater_station.json:64`).
   - A carved cave would need a spawn-free zone, and that zone is a 2-D column. It would silence the sea above
     (`legendaries.json:99`).
   - It would need re-carving after every re-export.
   - It would share the sea floor with `sea_life` and `sea_floor`.
   - The pocket is untouched by re-exports; its contents are rebuilt by the re-application, exactly
     (`tools/portals.py:31-32`).
4. **The dimension is proven on this stack.**
   - It registers, loads and holds entities (EXP-047, `tools/portals.py:17-18, 24-34`).
   - Our per-tick systems reach it, the blackout system and the water ladder among them (`tools/portals.py:30`).
5. **A second dimension buys nothing.** A dedicated `cobblers:abyss` dimension (a dark `dimension_type`, an ocean
   biome) would add a boot-time registration and a fresh experiment. The cave is roofed, so `has_skylight: true` and
   `fixed_time` (`data/portals.json:69-70`) do not light it.

**What a player notices when crossing** (`ADR-004:57-63`):
- a short loading screen;
- the coordinate jump;
- sent-out Pokemon recalled.

All three are accepted.

**Where in the pocket.** The cave must stay outside the portals pack's rescue box.
- That box is every room centre plus or minus `rescue_margin` (512), from `min_y` up to `floor_y - 2`
  (`tools/portals.py:438-441`; `data/portals.json:57-59`).
- Today the rooms sit at x 0..640 and z 0 (dive) or 256 (sky) (`data/portals.json:50-56`, `tools/portals.py:206`). So
  the box ends at about z 768.
- The Basin floor is at y30, inside that box's y range. A cave inside the box would be "rescued" mid-dive.
- **Place the cave's origin at (0, 2048) in `cobblers:pocket`.** It gets its own rescue sweep, and an audit proves the
  two boxes are disjoint (section 7).

### The route from the arch: sizes in blocks

All interiors sit inside a solid envelope with at least 4 blocks of shell, using the legendary chambers' fill-then-carve
pattern (`data/legendaries.json:18-19`, `tools/legendaries.py:20-24`). In the pocket the outside is void, so the shell
is what makes the cave a cave.

| # | Room | Size (x by z by height) | Floor y | What it does |
|---|---|---|---|---|
| A | **The Antechamber** | 13 x 9 x 7, dry | 200 | Arrival. The return click stands here. Like every portal's way back it is never gated (`tools/portals.py:524`). One sea lantern and a carved plaque. |
| B | **The Sounding** | 7 x 7 shaft, water from y196 to y120 (77 deep) | 120 | The descent. Three dry alcoves, 3 x 3 x 3, at y175, y150 and y125. Sea lanterns at long intervals; it is dark between them. |
| C | **The Gallery hub** | 15 x 15 x 8, flooded | 112 | Three galleries leave it. The way on, the Tide Gate's door, is visible and shut. |
| C1 | North gallery | 64 long, 5 wide, 6 high, flooded | 112 | Winding and dark. Glowing wild Pokemon are the only light. Ends in a lamp shrine (7 x 7 x 6, air pocket). |
| C2 | East gallery, **the Race** | 72 long, 5 x 6, a current | 112 to 103 | Flowing water, stepped down one block every 8. A swimmer is pushed back; Dive's swim boost is meant to beat it (experiment E3). Ends in a lamp shrine. |
| C3 | South gallery | 48 long, 5 x 6, flooded | 112 | A dead-end side room with the Diver's Cache pedestal and a lamp shrine. |
| D | **The Tide Gate** | 21 x 21 x 14, flooded to the roof | 98 | The tide wheel drains it once the three lamps are lit. Draining reveals a stair in the floor to the Trench. |
| E | **The Trench** | 128 long, 13 to 19 wide, rim y96, floor y36, 20 of dark roof above the rim | 36 | The scale reveal. From the Tide Gate's floor a player looks 60 blocks down to faint sea lanterns in the water at the bottom (6 deep). A 3-wide ledge path descends both walls at no steeper than 1 in 3. Two of the three alphas hold the ledges. |
| F | **The Basin** | dome 45 x 45, floor y30, roof y66 (36 high) | 30 | Kyogre's chamber. A central pool, 21 x 21 and 10 deep, holds the sleeper. A dry ledge ring at least 6 wide surrounds it. On the west lip: the shrine click, a second return click, and the catcher's pedestal. The third alpha patrols the pool's mouth. |

Totals:
- **Descent:** about 170 blocks of vertical.
- **Footprint:** about 260 x 300 including the trench's run.
- **Shell volume:** roughly 0.6 million blocks, split by `tools/function_limits.py` (32,768 per fill).

**Palette:** the dive set already in `data/portals.json:76-85` (prismarine bricks, dark prismarine, sea lanterns),
deepslate for the trench walls, and nothing that is a spawn condition unless the owner's 2026-10-05 flip is applied
deliberately (`PLAYTEST_2026-10-05.md:87-89`).

### Puzzles, from mechanics we already have

Puzzles are **clicks and fills, not redstone**. The repository's audits replay blocks, not signals; a redstone puzzle
cannot be checked offline (`data/gym_interiors.json:1467`). Every click is the proven interaction-plus-advancement
pattern (`tools/portals.py:19-22`).

1. **The Sounding: the air and fatigue test.** It is not a lock; it is the first lesson.
   - The water ladder holds air full only while the Dive training **and** a Dive-capable party member hold
     (`data/blackout.json:144-146`; seen in game: Dive held air flat for over two minutes, `docs/STATE.md:107`).
   - The arch's gate reads only the tag (`portals.json:32`). A tagged player without a Dive partner therefore drowns on
     the way down, unless they use the alcoves.
   - Putting this test at the top means the lesson costs one swim back up, not a trip to the bottom.
2. **The Three Lamps (light).**
   - Each lamp shrine has a click that sets its lamp, a sea lantern on a dark prismarine plinth.
   - The galleries are dark. Calder's "lamps that were lit before any of us were born" is the clue.
   - With all three lit, the tide wheel in D answers. Until then it prints "The wheel will not turn in the dark."
3. **The Tide Wheel (water level).**
   - One click `fill`s D's water to air, in slices, over a few seconds.
   - This is the shape of Erika's drain, "the drain is the puzzle and the drain is water"
     (`data/gym_interiors.json:1978`). It is done by commands, not live fluid physics, so it is exact and auditable.

**Shared state, and how it resets.** The lamps and the drained hall are world state, so a party solves them once,
together. It is co-op by design (vision 7).
- They reset only when **no player is anywhere in the cave's box**.
- They never re-close around a player. This is the lesson of REVIEW 87: Azelf's gate opened only while a qualified
  player stood in the approach box and shut a player inside the chamber (`docs/REVIEW_2026-10-02.md:99`).
- The Basin's barrier is the only thing that closes while players are present (section 4). It encloses only the
  sleeper's cell in the pool, never a walkable or swimmable cell a player can occupy. The audit proves it (section 7).

### Dangers

- **No natural spawning.** The pocket's biome is `minecraft:the_void`, whose spawn list is empty. Whether a Cobblemon
  pool can still match it is NOT VERIFIED (`data/portals.json:62`), so experiment E1 comes first. The design does not
  rely on natural spawning.
- **The wild Pokemon are set pieces**, summoned by a **macro** `spawnpokemonat`. A macro works from a function at a
  fresh boot; a plain line does not (EXP-046, `experiments/EXP-046-working-pokemon/README.md:23`). Each is claimed
  (`PersistenceRequired`) in the same function, because an unclaimed Pokemon despawns within a minute (`:24`).
- They are re-armed when a player enters an empty cave, so a revisit has something in it (`STATE.md:134`, "it adds to
  revisiting").
- **Proposed roster** (trainer-balance-designer sets the species, levels and counts):

  | Where | What |
  |---|---|
  | Sounding | Tentacool line, Chinchou/Lanturn |
  | Galleries | Lanturn, Huntail/Gorebyss, Lumineon, Relicanth |
  | Trench | Sharpedo, Wailord |
  | Alphas (3) | Gyarados and Kingdra on the trench ledges, Dhelmise at the Basin mouth |

  - None appears as a Mega (the owner's ruling).
- **Hazards** are the water rules that already exist:
  - surface fatigue in any water (`STATE.md:112`);
  - the Race's current;
  - the dark.

  Nothing new is invented.

---

## 4. The encounter

### Per player, once, keyed on the catch (recommended)

The owner's catalogue rulings point both ways:
- **Necrozma is server-wide**: "whoever gets there first gets it" (`data/adopted_legendary_sites.json:894`). But there
  is one Necrozma per tower, so the race has several prizes.
- **Spectrier is once per player, permanently** (`:895`).

Kyogre is a single cave, the one sea legendary a player can actually reach, and the owner expects "people will care".
- A server-wide Kyogre turns the best-built dungeon in the campaign into a one-player prize.
- The vision asks each dungeon to say which rewards are per player (`GAME_VISION.md:138-139`).
- **So: per player, once, keyed on the catch.** Open question 1.

**The mechanism.** It is the legendary chambers' entity handling (`tools/legendaries.py:58-62, 376-427`) with
Spectrier's lesson: record the outcome, not the trigger (`adopted_legendary_sites.json:229-233`).

- **The sleeper.**
  - A keeper keeps exactly one Kyogre in the pool, dormant (`Unbattleable`, `NoAI`, `PoseType SLEEP`, ...,
    `legendaries.py:58-59`).
  - A barrier cell surrounds it, because a sword can kill a Cobblemon entity that is "invulnerable" (EXP-023,
    `legendaries.py:14-17`).
  - If the sleeper is missing, the keeper summons one by macro (EXP-046). So the keeper does not depend on an RCON
    step, unlike R14L's legendaries (`legendaries.py:11-13`).
- **The wake.** A click on the shrine runs `kyogre_cave/wake` as the player. In order:
  1. It refuses a player holding `cobblers:legendary/kyogre/caught` ("It does not stir for you again").
  2. It refuses while another wake is live: "The water is already moving." One awake Kyogre at a time; the second player
     waits.
  3. Otherwise it removes the barrier cell, sets the awake NBT (`legendaries.py:62`), tags the waker, grants
     `cobblers:legendary/kyogre/met` (the existing per-player pattern, `legendaries.py:423-427`) and starts the rain
     (below).
- **A catch.** It grants `cobblers:legendary/kyogre/caught` and flag `kyogre_caught` **to whoever caught it**, which is
  not necessarily the waker. The keeper then lays a new sleeper down after the Basin has had no battle for 30 s.
  - If friend B catches the Kyogre friend A woke, B's one Kyogre is spent and A can wake the next. Each player still
    gets exactly one.
  - Detection is the open point (experiment E2):
    - **First choice:** a Cobblemon capture callback under `data/cobblemon/callbacks/` (`.claude/rules/datapacks.md`).
      The blackout system already resolves claims on a capture in game (`STATE.md:103, 110`).
    - **Fallback:** the proven party read (`compile_dialogue.py:32-35`, EXP-042) tags a player with a Kyogre in the
      party.
- **A flee.** Running is not a loss (`STATE.md:103`). The Kyogre stays awake while its waker is in the Basin. When the
  waker leaves, or after 5 minutes with no battle, it goes back to sleep: dormant NBT and the barrier cell. The cell
  closes only when no player is inside the cell's box.
- **A loss.** A full-party loss is a blackout: 20% charge, return to the checkpoint (`STATE.md:103`). Whether the return
  works from the pocket dimension is experiment E4.
  - **The Kyogre is exempt from item claims.** Otherwise the wild victor becomes a guardian holding the player's items
    (`STATE.md:110`), and the keeper's re-sleep would fight the guardian's leash.
  - The exemption is a change to `cobblers_blackout`. It gets a contract entry and a test in
    `data/system_contracts.json` (`.claude/rules/testing.md`, "Cross-system contracts").
  - A player who loses can come back and wake it again.
- **A kill.** If the Kyogre dies outside battle (`legendaries.json:625`), the keeper re-summons it. No catch was
  recorded, so nothing is lost.
- **Weak points, accepted** (as Spectrier's were, `adopted_legendary_sites.json:234-236`):
  - A player who already holds `caught` could throw a ball at a friend's woken Kyogre and take a second one. A capture
    callback cannot cancel a capture.
  - The shared Basin shows a sleeping Kyogre even to a player who has caught theirs. Hook for Codex: the "cost of
    repetition" theme (`ARC.md:407`) can carry it ("the sea remembers its shape").

**Catch rules.**
- Level 60, at the gate's bound (section 2). `tools/legendaries_audit.py rct_caps` checks it (`LEAGUE_LEVEL_CAP.md:9`).
- No forced ball and no Master Ball ban.
- Size: Cobblemon's intrinsic size roll is widened to 0.6-1.4 (`STATE.md:114`). Whether a `spawnpokemonat` legendary
  takes it, and the Kyogre hitbox at 1.4, are unmeasured (E5). The pool and dome are sized with margin for 1.4.

### Weather

- **In battle:** Kyogre's Drizzle is its standard ability. ASSUMED, not checked in the 1.8.0 species file; E5 confirms.
- **In the world:** the wake runs `execute in minecraft:overworld run weather rain 12000` (10 minutes). On the station's
  deck and across the region it rains while someone fights Kyogre. It is server-wide flavour for a group of friends and
  harmless. Open question 4.
- Whether rain renders in the pocket dimension itself is unknown (E7). The Basin is roofed, so this matters only for
  Rayquaza's island.

### Primal Kyogre and the Blue Orb

- What is known:
  - Mega Showdown's description says "Adds primal's" (`base-pack/inventory/mod_inventory.json:7359`; a description, so
    ASSUMED).
  - The Red Orb exists in Mega Showdown 1.0.2 and has no source anywhere, so Primal Groudon is dead
    (`docs/research/OBTAINABILITY_MODS.md:61`).
  - The research recommends handing a form-change item with its species (`:135`).
- **The Blue Orb is recorded nowhere in `docs/research/`.** Its item id, whether Mega Showdown 1.0.2 ships it, how
  Primal Reversion triggers (held at battle start?), and whether a config switch governs it are questions for
  `cobblemon-researcher` (E6). This design names no id.
- **Design, subject to E6:**
  - The wild Kyogre is never Primal (the Megas ruling).
  - The Basin's catcher's pedestal gives the Blue Orb once, to a player holding `kyogre/caught`.
  - Groudon's Red Orb follows the same rule (section 6).
  - If E6 finds no working Primal, the pedestal holds something else and the species record says "Primal cut", as
    `OBTAINABILITY_MODS.md:135` asks.

---

## 5. Rewards and repeat visits

- **Per player.** Chests are shared and first-come (`data/portals.json:129`); the owner wants every chest per player
  through an instanced-chest mod (`PLAYTEST_2026-10-05.md:15`).
  - No mod is chosen. Adding one is a dependency decision (principle 9) for `dependency-auditor`.
  - Until then, every reward is a **claim pedestal**: the portals' `vault` pattern, "a pedestal that grants its reward
    ONCE PER PLAYER" (`data/portals.json:136`, `tools/portals.py:504-508`). An interaction click and a per-player
    advancement, no container.
  - Each reward record carries `container: "pedestal" | "instanced_chest"`, so the swap is a data edit once a mod exists.
  - A chest is also a Gimmighoul spawn condition (`portals.json:113`), which is moot in the void biome.
- **The pedestals** (contents are trainer-balance-designer's; the ids below must come from the checked set in
  `data/rewards.json`):
  - **The Diver's Cache** (C3, open to anyone who reaches it): Dive Balls (`cobblemon:dive_ball` is a real id,
    `data/blackout.json:86`) and a Water Stone.
  - **The Lamps' gift** (D, after the third lamp): one held item suited to a rain team. Which one is the balance
    designer's.
  - **The Catcher's pedestal** (F, requires `kyogre/caught`): the Blue Orb (subject to E6).
- **Free Poke Balls are fine.** "Economy: don't limit the player" (`PLAYTEST_2026-10-05.md:93`).
- **On a revisit:**
  - the set-piece wild Pokemon and alphas re-arm when a player enters an empty cave, and all are catchable;
  - the lamps and the Tide Gate reset, so a newcomer's party does the puzzles;
  - the sleeper stays for the next friend;
  - the station's stage-4 lines change.

  The arch becomes the way to the region's deep-water species.

---

## 6. The weather trio (COMMITTED by the owner, 2026-10-05): companion outlines

These are outlines, not designs. Each needs its own document before a builder starts.

### The tie, and the order

- **Order: Kyogre and Groudon in either order after gym 8, then Rayquaza after the Champion, for a player who has met
  both.**
  - The two sleepers stir because the forced exchanges shook the region, the crater operation woke the mountain
    (`ARC.md:48`), and the sea answered (section 1).
  - The sky does not settle them until the ground stops moving. Rayquaza's arch answers only after the Rift crisis is
    resolved and the League is won (`ARC.md:50`: the League requires `rift_crisis_resolved`), and only for someone the
    other two have seen.
  - That is the main-series shape (Rayquaza calms the pair) told through our region's cause.
- **Cues:**
  - Coldwater's stage 2 names Groudon.
  - Fossick or Cinderlee carries the mirror line: the mountain warms when the sea's ring freezes.
  - Moss's stage 4 points up.
- **Gate pattern.** `requires_met` already expresses "met both" for Regigigas (`data/legendaries.json:453-459`).
- **Availability.** All three are once per player, keyed on the catch (section 4). The mechanism should become an option
  in `tools/legendaries.py`, not three copies. Groudon is still a shared world entity today: "the first catch takes the
  encounter for the whole server" (`legendaries.json:624`).

### Groudon: deep in a volcano, beneath lava

- **Site: the Craters.** It is the only volcano: `volcanic_cones: craters` (`data/landmarks.json:17`). Mt Clay is in the
  northern range (`:16`) and is not volcanic.
  - Groudon is already sited at the **eastern cone's bowl**, plug at (6672, 5508), ground y108, as a `sealed_chamber`
    with a 40-block drop and a 21 x 21 x 11 chamber, 211 blocks from Fossick (`legendaries.json:489-531`). The bowl is
    the one cone with an actual crater (`landmarks.json:4658`).
  - The landmark record's y127 bowl floor is stale; the heightmap says y108 (`legendaries.json:510`).
  - **Keep the site; change the shape. Carve in place:** "deep in a volcano" is right there (ADR-004).
  - The **great cone** ((6454, 5078), top y304, no crater, `landmarks.json:4658-4663`) is the alternative if the owner
    wants more depth. It is better kept for Rayquaza's arch (below).
- **Shape.**
  - The bowl floor becomes a **lava lid**: a lava pool over a vertical vent about 30 deep.
  - Below it, a descent roughly twice today's 40, to a larger chamber sized for Groudon (E5 measures it).
  - This needs a new chamber kind in `tools/legendaries.py`, e.g. `lava_vent`. Today's `sealed_chamber` has a dry
    ladder and a plug that "never closes again" (`legendaries.py:30-31`).
- **Getting past the lava**, with what exists:
  - **(a) Fire Resistance.** A vanilla potion. Its ingredients come from the Nether, which the owner has now confirmed
    exists (`PLAYTEST_2026-10-05.md:85-86`). It lets a prepared player swim the vent.
  - **(b) The cooling puzzle.** Three sluices in Fossick's deep workings each turn a stretch of the vent's lava to
    basalt steps by `fill`. It is the Tide Wheel's mirror, with the same shared state and the same reset only when
    nobody is in the box.
  - **(c) Mounts.** No riding note in `docs/research/` covers lava. Charizard and Mudsdale riding are verified
    (`docs/research/COBBLEVERSE_COMPATIBILITY.md:5`). A flyer could cross a lava *lake*, which is why the lava must lid a
    vertical vent rather than cover a lake. Whether any Cobblemon mount swims lava is a researcher question, not an
    assumption.
- **Gate, level, reward.**
  - `gym8_cleared` plus the Fossick quest beat, level 60 (unchanged).
  - The Red Orb at the catcher's pedestal, subject to E6.
  - Wild Fire-type set pieces at 50-58.

### Rayquaza: a sky island behind a relic arch

- **The arch.** A **sealed sky arch**, a seventh, built outside `data/portals.json` for the same reason as Coldwater's.
  `portals.py load()` refuses a gate whose count is not a multiple of six with one vault in each six, the owner's 1-in-6
  rule (`coldwater_station.json:55`).
  - It uses the sky palette: a ruined relic doorway with no sheet (`data/portals.json:86-95, 114`).
  - It is opened by the sky tag `cobblers.sky` (granted at `gym4_cleared`, `portals.json:37-44`) **and**
    `champion_cleared` **and** met Kyogre **and** met Groudon.
  - Before that, it is clickable and gives a sealed line, as Coldwater's arch does today.
- **Site.** A high summit east of x4000 (`portals.json:9-10`). The proposed candidate is the Craters' **great cone
  summit** (y304, close to the terrain cap of y310, `STATE.md:136`): the sky over the mountain whose sleeper the player
  has already met. A builder measures it with `tools/ground.py` and the portals' clearances before it is final. Moltres's
  tower is also on the Craters (`STATE.md:132`).
- **The island.** It is in `cobblers:pocket`, really elsewhere (ADR-004), at its own origin (0, 4096), outside both
  other rescue boxes.
  - About 64 x 48, its top at y200, with a broken pillar 40 high.
  - The climb is inside the pillar and roofed, so a flying mount does not skip it.
  - Rayquaza waits at the open top.
  - A fall off the island is caught by the island's own rescue sweep, on the portals' 20-tick shape
    (`tools/portals.py:449-459`), before the bedrock plane at y0 kills the player.
- **Level.** 70 is proposed. After the Champion the cap is 100 (`legendaries.json:97`). Lugia's 75 is the sea apex.
- **The End spawn.** Cobbleverse's loaded function spawns a **shiny level-100 Rayquaza** at the End arrival platform
  (`DIMENSIONS_AND_BORDERS.md:323-326`), and End access is post-game (`:338`). With Rayquaza committed to the sky
  island, recommend overriding that function empty at its own path (`.claude/rules/datapacks.md`, "Upstream is
  read-only"). Open question 5.

---

## 7. Build plan

Each step is one unit. Build work goes only to an agent with a shell (CLAUDE.md, cost rules).

| # | Step | Agent | Notes |
|---|---|---|---|
| 1 | Experiments E1-E8 (section 8), the cheap ones first; E6 is research only | `cobblemon-researcher` (E6, E5's hitbox source), `minecraft-systems-dev` (runs), `qa-reviewer` (verdicts) | Nothing below starts before E1, E2 and E4 have results. |
| 2 | `data/kyogre_cave.json`: rooms as boxes in pocket coordinates, the shell, the palette, the lamps/wheel/shrine/return/pedestal clicks, the set-piece roster slots, the reset box, the rescue box, the gate flags, the reward records with `container` | `world-content-dev` (geometry), `trainer-balance-designer` (roster, levels, rewards) | Generators translate and do not decide (`.claude/rules/datapacks.md`). |
| 3 | Kyogre's record in `data/legendaries.json`: kind `pocket_basin` (new), `status`, gate, level 60, `availability: "per_player_catch"` | `trainer-balance-designer` + `datapack-content-dev` | The gate and level are checked by `legendaries_audit` `rct_caps`. |
| 4 | Flags `kyogre_arch_sounded`, `kyogre_arch_open`, `kyogre_caught` in `data/progression.json`; quest `coldwater_kyogre` fields and cursors; stages 1-4 in `data/dialogue.json` | `minecraft-systems-dev` (flags), Codex or the dialogue writer (words) | |
| 5 | `tools/kyogre_cave.py` writes `build/datapacks/cobblers_kyogre_cave`. It covers the shell and carve, run `execute in cobblers:pocket` with its own forceloads (the `portals/place` shape, `tools/portals.py:471-477`); clicks and advancements; lamps, wheel and reset; the keeper, wake, sleep and catch; the set-piece re-arm (macro); the rescue sweep; the overworld rain. It REUSES `legendaries.py` (envelope, DORMANT/AWAKE, met), `portals.py` (`summon`, `click_advancement`, the enter/leave shape) and `function_limits` by calling them, not copying them, as `coldwater_station.py` does (`tools/coldwater_station.py:13-20`). | `datapack-content-dev` | It must not redefine `cobblers:pocket`; the portals pack owns it. That is a contract. |
| 6 | The arch's hook: `cobblers:coldwater_station/portal/touch` grants `kyogre_arch_sounded` to a diver; `portal/destination` becomes the enter shape (gate check, return score, `execute in cobblers:pocket run tp`). The arch stays in `coldwater_station.json`: keep the lane guard (`:64`) and do not touch the 1-in-6 rule (`what_remains` 3). | `datapack-content-dev` | **This deliberately breaks the Coldwater audit's rule** that `portal/destination` holds no tp, no `execute in`, no scoreboard (`coldwater_station.json:376`). The auditor rewrites that check in the same change. |
| 7 | `tools/legendaries.py` gains the `availability` option and the `lava_vent` kind; Groudon moves to it; the sky arch and island tool for Rayquaza | `datapack-content-dev` | Separate units, after Kyogre is proven. |
| 8 | `tools/reapply.py`: step **R18KC** after R16P and R18CW. Install the pack world-local, run `kyogre_cave/build`, let the keeper summon. Add the pack to prepare's coverage. | integration (main session) | Prepare and install are never delegated. |
| 9 | `blackout` exemption for `cobblers_leg_*` from item claims, plus a contract and test | `minecraft-systems-dev`, then `test-author` | `tests/test_system_contracts.py` must pass. |
| 10 | Docs: STATE "What is decided" (trio committed, per-player legendaries); STRUCTURE_DECISIONS 176/182/209; DIMENSIONS_AND_BORDERS 342 | content-architect / main session | |

### Audits an independent auditor must write (`test-author`)

`tools/kyogre_cave_audit.py` reads only `data/kyogre_cave.json`, `data/portals.json`, `data/coldwater_station.json`,
`data/legendaries.json`, `data/progression.json` and the emitted function text. It must not import `kyogre_cave.py`,
`legendaries.py` or `portals.py`; it replays the functions into a voxel model, as `portals_audit` does
(`tools/portals.py:48-50`).

1. **The seal.** Every carved cell has at least 4 blocks of shell in all six directions, so no carved cell opens to
   the void anywhere.
2. **Reachability by state.** A flood fill over walkable and swimmable cells, run for each puzzle state:
   - with the lamps unlit, the Trench is unreachable;
   - with all three lamps lit and the wheel turned, the Basin ledge is reachable from A;
   - **in every state, every reachable cell reaches a return click.** This is REVIEW 87 as a proof.
3. **No trap.** Every command that writes a blocking block while the cave can be occupied either:
   - targets only the sleeper cell, whose box no walkable or swimmable cell intersects; or
   - runs under the "no player in the cave box" guard.
4. **Disjoint rescue boxes.** The cave's rescue box is disjoint from the portals pack's (recomputed from
   `portals.json` rooms and `rescue_margin`) and from the island's. Every cave cell is inside its own box.
5. **The gate.** Every line that tps into the cave carries all three predicates. Every wake line carries
   `caught=false`. Every catcher's pedestal requires `caught`.
6. **Levels.** Kyogre's level is at or under the 8-badge band. Recompute it with `rct_caps` read independently from
   `data/trainers.json` and the RCT config.
7. **Water.** Every macro spawn targets a water or ledge cell of its room. The Sounding's three alcoves are dry. The
   drained Tide Gate holds no water source a flood could restore.
8. **Mutate the generator, not the record.** Each of these must fail with the data untouched:
   - +1 on the shell margin in the builder;
   - the reset guard's box shrunk by 1;
   - the barrier fill grown by 1 into the ledge;
   - the wake's `caught` predicate dropped.
9. Plus the existing suites: `portals_audit`, `coldwater_station_audit` (with the destination rule rewritten),
   `legendaries_audit`, `id_authorship`, `test_system_contracts`.

### In-game test list (staging, after R18KC; never the live world)

1. A non-diver clicks the arch and gets the dive refusal. A diver without the flags gets the sealed line. A diver
   touching it gets `kyogre_arch_sounded` (stage 1).
2. Stages 2-4 of the dialogue, each with and without its condition.
3. Crossing in and out; the return click from A and from F; `tp` by the rescue sweep from the trench floor area if the
   player is pushed out of the shell.
4. Descending the Sounding with a Dive partner (air held) and without one (the alcoves save them).
5. The Race against and with Dive.
6. The three lamps, the wheel, and the reset only after everyone leaves (two accounts: one stays inside while the other
   leaves).
7. Waking, a battle, a catch: `caught` granted to the catcher and a new sleeper within 30 s. A friend's wake refused
   while one is live. A flee leads to re-sleep. A full-party loss leads to a blackout, no item claim, and a wake again
   after return.
8. Rain on the overworld during the wake.
9. Each pedestal once per player.
10. Set pieces re-arm after an empty cave.
11. Probes present out of probes total, reported as such ("A success report is not the work", CLAUDE.md).

---

## 8. Unverified: the experiments to run first

| # | Question | Why it blocks | Cheapest proof |
|---|---|---|---|
| E1 | Does any Cobblemon spawn pool match `minecraft:the_void` in `cobblers:pocket`? Would a Habitat Block work there? | Set pieces assume nothing else spawns (`portals.json:62`). | One player standing in a built pocket room for 10 minutes, then place a Habitat Block. |
| E2 | Can a capture callback (or the party read) attribute a tagged wild legendary's capture to the capturing player, in the pocket? | Per-player Kyogre rests on it. | A tagged wild Magikarp summoned by macro in a pocket room, caught by a second account. |
| E3 | Can a Dive-boosted swimmer beat a stepped flowing-water current, and an unboosted one not? | The Race. | A 40-block channel on a disposable world. |
| E4 | Do a Cobblemon battle, the blackout return and the water ladder all work inside `cobblers:pocket`? | Every fight in the cave. | One wild battle lost on purpose in a pocket room. |
| E5 | Kyogre's (and Groudon's, Rayquaza's) hitbox at sizes 1.0 and 1.4; whether `spawnpokemonat` applies the size roll; whether a NoAI Kyogre in a pool can be battled by click after the awake NBT; whether Drizzle is its ability in the 1.8.0 species file. | Room sizes and the wake. | Read the species files (researcher), then one spawn. |
| E6 | Mega Showdown 1.0.2: the Blue Orb's and Red Orb's item ids, how Primal Reversion triggers, any config switch, and whether it works on Cobblemon 1.8.0. | The catcher's reward. | `cobblemon-researcher`: the jar, then one battle. |
| E7 | Does `weather rain` reach or render in `cobblers:pocket`? | Only Rayquaza's open-air island. | One command, one look. |
| E8 | A ball thrown by a second player at a woken legendary: is it allowed, and does attribution hold? | Section 4's weak point. | Folded into E2. |

---

## 9. Open questions for the owner (each with a recommended default)

1. **Kyogre per player or one for the server?** *Default: per player, once, keyed on the catch.* Necrozma's
   first-come rule had several towers behind it; this is one cave.
2. **Gate and level.** *Default: `gym8_cleared` plus Dive plus the station's quest, level 60.* The alternative is
   post-game at about 70 (champion cap 100).
3. **Should a qualified player be able to bring a friend who has not done the station's beats?** *Default: no.* The gate
   is per player, and the beats are four short conversations.
4. **Overworld rain while Kyogre is awake?** *Default: yes, 10 minutes, server-wide.*
5. **The Cobbleverse shiny level-100 Rayquaza at the End spawn.** *Default: remove it by override,* now that Rayquaza
   has a home.
6. **Rayquaza's gate and level.** *Default: `champion_cleared` plus met Kyogre plus met Groudon, level 70, its arch on
   the Craters' great cone summit.*
7. **Groudon's lava.** *Default: keep the eastern bowl, lid a vent with lava, and allow both routes: the Fire Resistance
   potion and the Fossick cooling puzzle.* The alternative is stripping Fire Resistance as Water Breathing was
   stripped (`data/blackout.json:148`).
8. **Instanced chests.** *Default: per-player claim pedestals now, and choose an instanced-chest mod separately* (a
   dependency review). Every reward record is already switchable.
