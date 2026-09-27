# The water proposal: rivers, lakes, dive sites, the ferry, fishing and docks

**Status:** proposal, 2026-09-27, for the owner. Nothing here is built by this document. It sits on top of
`WATER_MAP.md`, whose allocation of one role per body of water stands; this document adds the travel, fishing, docks
and the remaining sites around it, and defines the two sites that existed nowhere in the repository: **the Relic
Island reef** (section 3.2) and **the appearing island** (section 3.3).

**Tags.** Every mechanic claim carries one:
- **[V: source]** VERIFIED, with where it was seen or read.
- **[M]** measured for this proposal on the canonical heightmap (`0d9b5f1e…`, `tools/ground.py`), read-only: land is
  ground at y62 or above, distance from land on a 4-block raster (octagonal, within about 8% of true distance),
  crossings as straight lines between the named points. An estimate, repeatable with the script described in the
  appendix.
- **[A]** ASSUMED: not tested, not read from a jar or a file.

Stages: **S0** before Brock, **SN** after gym N, **L** the League, **P** postgame. Caps 20/25/30/35/40/45/50/55.

---

## The one-page summary

| Topic | The proposal in one line |
|---|---|
| **Rivers** | Three water roads (Viltri's Path to the sea at S2; the Lakes' River from Shrew Lake to Sunset West; the major river to Tilpey and the east coast), one barrier (the major river and Tilpey's outflow gorge, crossed by the one required bridge), the rest scenery and fishing. No new bridges on routes |
| **Lakes** | `WATER_MAP.md`'s allocation stands: lakes are Surf content, the trio sits in air-chambered grottos at S3, S5 and S7. Added: a dock and a fishing box for each lake that has a role, and a free launch across Tilpey from S6 |
| **Dive sites** | Eight, all S6 or later by construction: the Tilpey practice floor, **the Relic Island reef's sunken Pallet fragment**, the forge ruin, Lugia's three coves, the trench, and **the appearing island's sea temple**. Three open Surf wrecks keep the sea in play between S1 and S6 |
| **The ferry** | Ferrymen at docks, a dialogue, a fare in CobbleDollars, a fade and a teleport. Built from parts already proven one by one; no moving boats. Five lines and a postgame charter from Sunset West |
| **Boats** | Recommended: boats are for shallows, lakes, rivers and the Sound. Past 96 blocks from land a boat is swamped and its rider swims (then surface exhaustion applies). The open sea is for water Pokemon and the ferry |
| **Fishing** | Six rods at six waters (First Cast's Poke Rod, then Misty's lake, Peak Pond, Pacifidlog's Guild, the Relic reef, the Watering Hole), each water fishing at its own stage's levels. Which rod is "better" waits on research into what a rod's ball or enchantment does |
| **Docks** | 19 in all: 8 already built or planned (First Cast, the two Viltri platforms, Misty's two piers, Sunset West's waterfront, Pacifidlog's jetty and its waterfront), 11 new small ones (the Relic landing, the Sunset isle landing, three at Tilpey, the north-east landing and the Northlight landing, the Peak Pond jetty, the Watering Hole stage, the Lakes' River head, the appearing island's landing) |
| **Ocean bands** | One distance-from-land field decides four things at once: levels, surface exhaustion, where boats may go, and which content sits where |
| **Measured surprise** | Relic Island, Fungal Isle and the Long Isle at the Sound's narrows are all **inside the shallows** (never more than 80 blocks from land). Every other island crossing but the Pine Isles has 60-90 blocks of open water: 12-18 seconds of swimming. With a one-minute exhaustion budget the ferry is comfort and safety, not the only way over (section 4.1) |

**By stage, where the water is:**

- **S0: the Pallet coast.** First Cast's jetty and the Poke Rod; the shallows; Relic Island by the free row from First
  Cast or a short swim (84 blocks of water, all shallows), and the reef's sunlit edge seen from its shore; Viltri
  Light along the coast. The Sunset strait and Sound ferries run from the start, for anyone who walks that far.
- **S1: the first ride.** The first water Pokemon (Gyarados at 20, a rare Relicanth). The Windward Sea's open water and
  its sunlit fishing-boat wreck.
- **S2: Misty.** Surf training at Lake Viltri; the floor survey; the Shrew pit; the Viltri's Path water road to the
  sea; the second rod; the windward slope wreck.
- **S3: Mesprit** under Arrow Lake.
- **S4: Erika's Peak Pond:** fishing, the third rod; the tarn's story.
- **S5: Azelf** under Marshy Marsh. The Northlight packet from the north-east coast starts running (Northlight's content is
  postgame, not locked).
- **S6: Dive** at Tilpey. The Tilpey launch; the Relic reef's sunken fragment; the forge ruin; the key coves; the
  Sound and Pacifidlog as the S6-S8 detour, with the Guild's rod and the Sound wreck.
- **S7: Uxie** under Tilpey. The Watering Hole's rod.
- **S8:** the Lakes' River to Sunset West is open all game; nothing new is needed here.
- **L:** Milotic's Drowned Gallery (built).
- **P:** Lugia in the trench; the appearing island (Manaphy, Phione); Sunset West's charters; Northlight's research.

---

## 1. Rivers

The rivers are graded and cut into the canonical heightmap [V: `docs/world-building/RIVERS.md`, `data/rivers.json`].
Only one route crosses water: Route 7, over Lake Tilpey's outflow at (6632, 3904) [V: `data/routes.json`
`barriers`, `data/towns.json` gym7_town `water_crossings`]. Rivers are shallows: never more than 9 deep and never far
from a bank, so surface exhaustion never applies on them [A: it measures distance from land].

| River | Size [V: RIVERS.md] | Role | Travel by water | Crossings |
|---|---|---|---|---|
| **Major river** (Glacial Tear to Tilpey) | 2,618 blocks: a 5-6 wide creek, then 18-28 wide and 7-9 deep, 6-8 below its floodplain | **Barrier** where it is big; scenery upstream | A water road downstream from the lower trough into Tilpey (S5-S7), for a mount or a boat | Route 4 passes its head as a creek (no crossing recorded). No bridge added |
| **Tilpey outflow gorge** | 352 blocks, 22-32 wide, 9 deep, a confined gravel gorge | **Barrier** between S6 and S7 | Out of Tilpey to the east coast: a scenic run, not a road | **The one required bridge**, at (6632, 3904), on Route 7. **Not built** (no placement or tool names it). The gorge hamlet's bridge-keepers keep it (`SQ-G6-02`, `SQ-GORGE-01`) |
| **Viltri's Path** | 1,711 blocks, 4-10 wide, 1.4-2.9 deep, gravel to sand to clay | **Water road**, the first: Misty's lake to the north-west coast | Downstream by boat or mount from S2 (`SQ-G2-02`), then south along the coast (all shallows) to Viltri Light and Pallet: the first water loop | None needed: shallow and narrow |
| **The Lakes' River** (proposed name for the Shrew Lake, Arrow Lake and Watering Hole outflows as one course) | 231 + 361 + 1,312 blocks; 8-11 wide, 2.7-3.2 deep | **Water road**: from the cherry vale down to Sunset West's harbour | Downstream by boat from Shrew Lake through Arrow Lake and the Watering Hole to the sea at Sunset West, about 1,900 blocks. Open all game; passes over Mesprit's lake | Sunset West's footbridge at the mouth (planned earthwork `sunset_footbridge`) |
| **Marsh outflow** | 395 blocks, 6-10 wide | Scenery; ends on the north-east coast at (5662, 1598) | Short: the marsh to the north-east coast | None |
| **Peak Pond outflow** | 545 blocks | Fishing creek near Erika's town | None worth taking | None |
| **Tarn outflow, Tilpey inflow creek, Mt Clay creek** | 401, 484, 1,261 blocks; narrow and steep | Scenery | None | None |
| **River of Shrews** | Not cut: a canal candidate, 89% clay | None: leave it uncut | — | — |
| **The four dry rivers** (Viltri ravine, Peak Pond creek, Marsh-to-Tilpey, Arrow's south-east branch) | Dry ravines | **Story evidence** (`SQ-G1-01`, `SQ-G4-01`, `SQ-G6-01`, `SQ-G8-01`) | None | None |

**How boats use rivers.** A river is a stair of one-block steps where it meets a lake or falls [V: RIVERS.md "one block
below the lake"]. A boat can ride down a step but not up one [A: vanilla]. So each water road is one-way for a boat
(downstream) and two-way for a ridden Pokemon only if a dolphin-style mount leaps the steps [A: not tested]. A boat rack
at each road's head (section 6) is what makes the trip repeatable.

**Where the water roads go.** Two of them end at the sea in shallows, so a boat can carry on along the coast:
Viltri's Path to Viltri Light and Pallet; the Lakes' River to Sunset West, then east along the south strand. Neither
needs the ferry.

---

## 2. Lakes

`WATER_MAP.md` section 3 is the allocation, and it stands. This adds the dock and the fishing to each lake.

| Lake | Role (WATER_MAP) | Stage | Dock (section 6) | Fishing box and band (section 5) |
|---|---|---|---|---|
| **Lake Viltri** (y103, 27 deep) | The Surf school: training, the sounding, the floor survey | S1-S2 | Misty's two piers (planned); the sounding and north-bank platforms (built on staging) | Goldeen, Poliwag, Magikarp, rare Chinchou at 16-22; **rod 2** |
| **Shrew Lake** (46-50 deep) | The dragon's pit: deep Dratini, the lost surveyor's case | S2 | **The Lakes' River head**: a boat rack and a small stage on the south shore, at the outflow | Magikarp, Goldeen, Barboach at 10-22. Dratini stays a deep swim find, not a rod catch |
| **Arrow Lake** (41 deep) | Mesprit's grotto | S3 | None: the lake stays wild so the grotto is found, not signposted | None: the Lakes' River passes through; its roster is the swim roster |
| **Mt Clay pond** | The Wooper stop (decided) | S2 | None | None |
| **Ravine Head Tarn** | Story evidence | S4 | None | None |
| **Peak Pond** (18 deep) | Erika's pond: fishing water | S4 | **A fishing jetty** on the town side, 129 blocks from Erika's town | Basculin, Whiscash, Goldeen, Gyarados at 30-32; **rod 3** |
| **Marshy Marsh** (38 deep) | Azelf's grotto | S5 | None: a tracker's hide on the shore at most (Koga's story) | None |
| **Lake Tilpey** (25 deep) | Uxie's grotto; the Dive school on the north shore | S6-S7 | **Three**: Sabrina's town dock (the survey diver and the launch), the Weeping Elder island landing, a south-shore landing | Arrokuda, Basculin, Seaking, Gyarados at 39-48 |
| **Watering Hole** (9 deep) | Fishing water, a rod find | S7-S8 | **A fishing stage** with a boat rack (the Lakes' River passes it) | Barboach line, Goldeen, rare Feebas (see decision 10); **rod 6** |
| **Drowned Gallery** | Milotic (built) | L | None | None |

**Surface exhaustion on lakes.** Recommended: it does not apply to lakes (decision 3). Lakes are the owner's Surf
content, their floors are the point, and Tilpey is the only lake wide enough to leave the shallows band at all [A: not
measured here, lakes count as land in this proposal's mask].

**The Tilpey launch.** Sabrina's town already has a ferry in its side events (`EVT-G6-SLOWPOKE-FERRY`) and a ferrier
who sends the player to the bridge-keepers (`SQ-G6-02`). Proposed: a free launch from Sabrina's town dock to the
Weeping Elder island and on to a south-shore landing, from `gym6_cleared`. It is a scene, not a shortcut past a gate:
the gorge bridge is still the road, and a player can swim Tilpey anyway.

**The trio's grottos** (decided in WATER_MAP; detail for the build): the mouth on the lake floor, a flooded passage no
longer than about 20 blocks, then an air chamber for the battle. From Arrow's surface that is about 8 s down, 4 s
through and the rest of Surf's 45 s held air spare [V: 5 blocks per second, EXP-042 session 3]. A lake floor never needs
Dive.

---

## 3. Dive sites and the sea's Surf sites

Dive arrives at gym 6, so every Dive site is S6 or later by construction [V: DEATH_AND_WIPE.md "Where Surf and Dive
come from"; the ladder is built, `cobblers_blackout`]. Dive gives unlimited air and about 10 blocks per second
[V: EXP-042 session 3, "air held flat for over two minutes"; the owner's swim boost]. The owner's rule: lakes are Surf
content; the sea's long or enclosed places are Dive content.

### 3.1 All of them, by stage

| # | Site | Where | Stage | What it holds | Gate |
|---|---|---|---|---|---|
| W1 | **The fishing-boat wreck** (Surf, open) | Windward Sea, open water, sunlit | S1-S2 | A cache; the first thing worth riding out to | A mount to reach; one breath to search [V: `OCEAN.md` section 5] |
| W2 | **The slope wreck** (Surf, open) | Windward Sea, the slope at y28-40 | S2 | A shipwreck template as found, a cache; Dhelmise's rare entry nearby | Surf (20-35 deep) |
| W3 | **The Sound wreck** (Surf, open) | The Sound's deep hole, 32-39 deep at about (7120, 6880) [V: `data/sea_town.json` why_here] | S6-S8 | An open hull the Guild lost; Pacifidlog's divers' story; a cache | Surf |
| D1 | **Tilpey's practice floor** | Lake Tilpey, 25 deep | S6 | The survey diver's lesson and a practice cache | Dive training (the lesson itself) |
| D2 | **The Relic Island reef: the sunken Pallet fragment** | Relic Island (1092, 5532), seabed y35 | S6 | The reef cache, a second Pallet letter, the Corsola home (the reef itself is open) | Dive, for the rooms (section 3.2) |
| D3 | **The forge ruin** | Windward Sea, the deep band (site not chosen) [V: `STRUCTURE_DECISIONS.md` submerged forge ruins, 1] | S6 | Cobblemon's submerged forge ruins template, a cache; the only Strength room if Strength exists | Dive |
| D4 | **The lush cove** (Lugia key 1) | Frostwater Shelf | S6+ | Key 1 | Dive |
| D5 | **The submerged cove** (Lugia key 2) | Eastern Reach | S6+ | Key 2 | Dive |
| D6 | **The magma cove** (Lugia key 3) | Outer Deep: the deep band, so a mount to reach | S6+ | Key 3 | Dive |
| D7 | **The Maelstrom Trench** | South-east margin [V: `data/regions.json` `trench_axis`] | P | Lugia | Dive, three keys and `champion_cleared` (decided) |
| D8 | **The appearing island's sea temple** | South of the Sunset isle (section 3.3) | P | Manaphy once, Phione repeatable | Dive, `champion_cleared`, and the island's night |

**Parked, not proposed:** the ocean monument. It is not a template (it would have to be captured in tiles), and its
guardians could not exist: Cobbleverse's MobsBeGone blacklists `minecraft:guardian`, `minecraft:elder_guardian` and
`minecraft:drowned` [V: `base-pack/cobbleverse/config/mobsbegone-blacklist.json`]. It would be empty architecture.

**The keys can be found from S6** (WATER_MAP's Lugia section), so the search starts before the League while the
trench opens only after it.

### 3.2 The Relic Island reef (proposal)

Relic Island is the F4 fragment: a Pallet starter home on an islet torn off in the exchange [V: `SETTLEMENTS.md`,
`data/towns.json`], built by `tools/islet.py` over a seabed at y35, 27 deep [V: `data/towns.json` ground note]. The
reef makes the start area's water pay off three times, at S0, S2 and S6.

| Layer | Depth | Stage | What |
|---|---|---|---|
| **The sunlit edge** | y50-60, 2-12 deep, on the islet's south and west apron | S0 | Coral, coral fans, sea pickles and seagrass, seen through the water from the islet: the hook. Corsola and Luvdisc at the Pallet coast's levels |
| **The drop-off** | the reef wall from y50 down to the seabed at y35 | S2 | Surf-depth: a dead-coral patch (Galarian Corsola), a fishing mark off the islet |
| **The sunken fragment** | the seabed, y35-45 | S6 | The rest of the torn-off piece of Pallet: a Pallet house and its cellar on its side on the seabed, rooms joined by a collapsed stair. Enclosed, so Dive. It holds **the reef cache** (ADR-002 find; candidate contents: the reef's rod, section 5, a Mystic Water, Dive Balls) and **a second letter** that pairs with `SQ-RELIC-02`'s note |

- **Why here.** `SQ-HOME-02` says the exchange "sheared off fragments rather than moving one perfect rectangle"; the
  islet is one, and the seabed piece is the rest. It gives Relic Island a reason to come back to at S6, near home.
- **The water is shallows.** The islet's centre is 88 blocks from land and the swim from First Cast never passes 80
  [M]. No exhaustion, no mount needed to get there.
- **Coral decides spawns.** Corsola needs coral blocks or corals nearby, Cursola dead coral [V: `OCEAN.md` section 4,
  read from the spawn files]. Whether the spawn also needs a warm-ocean biome is not known [A]; `/fillbiome` over the
  reef box is the fallback, the Rift skin's pattern [V: `tools/rift_skin.py`].
- **The levels are the coast's, not Dive's.** Everything that spawns on the reef is at the Pallet coast's band. Only
  the fragment's cache is S6 content. That keeps a gym-6 reward out of a start-area roster.
- **Build notes.** Coral is placed by a block pass (no seabed pass exists) and lives only touching water [A: vanilla].
  A house template placed underwater writes its air as air pockets, so the fragment needs a variant whose air is water
  [A: `tools/rematerial.py` has not been asked to map air]. The islet is not re-run (decided, `docs/STATE.md`).
- **Not the mythical site.** WATER_MAP decided the start area is not also Manaphy's.

### 3.3 The appearing island: Manaphy and Phione (proposal)

- **What.** A small island that rises from the outer sea on **full-moon nights** and is gone by morning, with a
  flooded sea temple beneath it. Hoenn's Mirage Island is the model: a place that is only sometimes there.
- **Where.** About **(1600, 8400)**, south of the Sunset isle, 372 blocks from the nearest land [M], so in the deep
  band: a swimmer cannot reach it and a rider or the charter can. It is in the border margin (z above 8191), inside the
  playable border (to z9215) [V: `docs/STATE.md` world facts]. The margin's seabed is the y10 plain the export writes
  there [A: `OCEAN.md` section 2 says so; not measured]. Measure it before siting.
- **When.** Postgame: the temple is Dive content and the encounter needs `champion_cleared`.
- **What it holds.** An islet of sand and palms with a ring of standing stones and a pool; a stair down into the
  **sea temple**, flooded, Dive only, whose inner hall holds air for the battle. **Manaphy once per player**, an
  authored encounter; **Phione repeatable**, spawning round the island's pool while it is up.
- **How it appears.** Shared world state, carved in place, as ADR-004 allows [V: ADR-004, accepted]. A function
  places the island template at dusk on a full-moon night and removes it at dawn. `place template` at an explicit Y
  lands correctly [V: EXP-013]. The moon phase is readable from the day count [A: vanilla, `time query day` modulo
  8]. The removal waits while any player is inside the island's box, the guard the stone mines proposed
  [V: ADR-003 proposes it; not built]. A schedule re-armed from a `load` tag surviving a restart is unverified [V: STATE,
  stone mines, "NOT VERIFIED"].
- **How Manaphy is met.** A function spawns it for the player whose flag allows it, when they enter the temple hall.
  `spawnpokemonat` works from a function [V: EXP-042 findings]. The authored encounter itself is EXP-006, unrun.
  Phione from a Habitat Block that goes in and out with the island, placed by the two-setblock recipe
  [V: `docs/STATE.md`, "Never switch a placed Habitat Block's style with `data merge`"].
- **How players find out.** Sunset West's harbour talks about it (the boat builders' charting run, `SQ-SUNSET-01`),
  and the postgame charter sails there on a full-moon night.
- **Blockers.** Both species have no client model today: they are among the 40 that lost their only assets with ATMxMSD
  RP, whose licence blocks hosting the fix [V: `docs/STATE.md`, "Client models"]. Distant Horizons may show a stale
  island (or none) from a distance, because its LODs are pregenerated [A: `docs/STATE.md` notes DH as a leak for
  far-overworld chambers; not tested with a block swap].

---

## 4. The ferry

### 4.1 Why a ferry, with the numbers

Surface exhaustion is being built (EXP-043, another agent): swimming in open water (96-256 blocks from land) builds
fatigue, a warning, then Slowness, then the harsh drown pulses after about a minute; the deep band (256+) twice as fast;
shallows (0-96) are free; riding a Pokemon clears it; land and shallows recover it [A: the design as briefed; not yet
built]. A sprint-swim is 5 blocks per second [V: EXP-042 session 3].

What each island crossing costs a swimmer [M]:

| Crossing | Length | Farthest from land | Open water (96-256) | Deep (256+) | Swim time in open water |
|---|---:|---:|---:|---:|---|
| First Cast jetty to Relic Island | 173 | 80 | 0 | 0 | none: all shallows |
| First Cast jetty to Fungal Isle | 231 | 80 | 0 | 0 | none |
| The Sound's narrows, dunes to the Long Isle (z6100, 6300, 6500) | 111-152 | 40-52 | 0 | 0 | none |
| Pacifidlog's jetty landing to the town square | 253 | 112 | 60 | 0 | about 12 s |
| Eastern dunes to the Jungle Isle, shortest | 326 | 128 | 64 | 0 | about 13 s |
| Sunset West's south pier to the Sunset isle | 307 | 132 | 73 | 0 | about 15 s |
| Marsh country to Northgate Isle, shortest | 335 | 136 | 89 | 0 | about 18 s |
| Marsh country to the Pine Isles (Northlight), shortest | 459 | 204 | 226 | 0 | about 45 s |
| Sunset West to the Jungle Isle (a charter) | 1,820 | 360 | 565 | 301 | not swimmable |

**What this means:** with about a minute of open water before the pulses, every island but the Pine Isles can be
swum by a player who knows where the narrows are, with a warning on the way. So the ferry is not a wall. It is:
- the **safe, easy** way for a player without a water Pokemon (the first ones come around gym 1-2 [V: `data/spawns.json`
  `marine_zones.windward_sea.access`, itself ASSUMED from the rosters]);
- the **only** easy way to the Pine Isles and on the postgame charters;
- the **story**: every dock is a place with a person.

If the owner wants islands to need a ferry or a mount, exhaustion has to bite faster (for example Slowness after 10 s
and pulses after 20-30 s of open water), and the near islands stay free because they are shallows. That is decision 2.

### 4.2 How it works in this pack

| Option | How | Status |
|---|---|---|
| **A. A ferryman, a dialogue, a fare, a teleport** (recommended) | A Cobblemon NPC at the dock opens a compiled conversation; each destination is a choice; the choice runs a scene function as the player that checks the fare, charges it, fades the screen, plays a boat sound and teleports the player to the far dock's landing | **Buildable now from proven parts** (below). Nothing new in the compiler |
| **B. A fare in CobbleDollars** (part of A) | `execute store result score @s <obj> run cobbledollars query @s`; if the score is at least the fare, `cobbledollars remove @s <fare>`, then travel; otherwise a refusal line | The read is verified [V: EXP-040], and a function charged a balance in game [V: EXP-042 run 1, $725 to $652]. A fixed fare needs no macro |
| **C. A moving boat** | Teleporting a boat and its riders along a lane every tick | **Not recommended.** Client jitter, riders falling off, chunk loading over 300-1,800 blocks, and several players on one boat [A]. Nothing in the repo does it |
| **D. Waystones** | Sunset West and Pacifidlog have discovery waystones [V: `data/towns.json`] | Already the return trip once a player has been there. The ferry is for the first crossing and for places with no waystone (Relic Island, the Sunset isle, the appearing island) |

**What each part of option A rests on:**
- the dialogue compiler and per-player state, proven single-player [V: EXP-022; `tools/compile_dialogue.py`];
- `scene_function`, a dialogue effect that runs a scene's named command list as the player [V: `tools/compile_dialogue.py`
  effect kinds; `tools/scenes_pack.py` `functions`]. The scene pack loads and its NPCs are placed, but **nobody has
  clicked a scene NPC yet** [V: STATE "Quest data", EXP-034 unrun];
- NPCs placed over RCON after a restart, because NPC classes load only at boot [V: `tools/scenes_pack.py`, R9F];
- a function teleporting a player [V: EXP-042, the blackout return];
- a badge gate in the function itself, `@s[advancements={cobblers:flag/gymN_cleared=true}]`, because gym flags cannot
  gate dialogue directly [V: STATE "Mainline reveal runtime"; the selector test is vanilla, A];
- dismounting first (`ride @s dismount`) so no boat or Pokemon is dragged along [A: vanilla].

**Multiplayer.** Per player: each player talks, pays and travels alone; nobody is moved by someone else's choice.
Two players at once is unproven for dialogue [V: STATE "Dialogue delivery", blocked on a second account].

**Data.** A new `data/ferries.json` (docks, landing points and facing, lines, fares, gates), generated into scene
NPCs and functions, and re-applied by a `tools/reapply.py` step (`prepare` fails closed on a pack no step runs
[V: STATE]).

### 4.3 The lines

| Line | From, to | Fare | Opens | Why |
|---|---|---|---|---|
| **The Relic row** | First Cast jetty to the Relic landing and back | Free | After First Cast | `SQ-HOME-02`'s roof across the water; the fisher who gave the rod rows you over. All shallows, so it is kindness, not a gate |
| **The Sunset strait** | Sunset West's south pier to the Sunset isle landing | $100 each way | Always | The harbour's purpose [V: `data/towns.json` sunset_west `for`]. 73 blocks of open water [M] swamp a boat (decision 1) |
| **The Sound ferry** | Pacifidlog's mainland jetty to the town | $150 each way | Always | "Water only" is the town's defining trait [V: `data/sea_town.json` D4]. The boats in the rack stay too: the Sound is sheltered water (decision 1) |
| **The Tilpey launch** | Sabrina's town dock to the Weeping Elder island to the south-shore landing | Free | `gym6_cleared` | `EVT-G6-SLOWPOKE-FERRY`, `SQ-G6-02` |
| **The Northlight packet** | The north-east landing to the Northlight landing | $400 each way | `gym5_cleared` | The only island whose crossing is really long (226 blocks of open water) [M]. Northlight's content is postgame, not locked [V: ARC.md] |
| **Sunset charters** (postgame) | Sunset West to the Jungle Isle ruins, the appearing island (full-moon nights), the trench's marker, Relic Island | $600 each | `champion_cleared` and `SQ-SUNSET-01` | "Chartered travel from the harbour" is `SQ-SUNSET-01`'s reward; `SQ-SUNSET-02` and `SQ-JUNGLE-02` sail to the ruins |

**Fares** are proposals, for the owner. For scale: Brock's first win paid $732 and a rematch $600 [V: STATE
"Cobbleverse gym rewards"]; a blackout takes 10% [V: EXP-042]. A fare should hurt less than dying on the swim.

**Sunset West is a hub, not a destination.** It moved to the mainland on 2026-09-21, at the Lakes' River mouth,
reachable on foot along the south coast [V: `data/towns.json` sunset_west `why_here`]. Its ferry goes to the Sunset
isle across the strait. (Its waystone record still says "an island": stale, see "Findings".)

### 4.4 Boats

Vanilla boats, chest boats and bamboo rafts are in the world already: barrels of six at Pacifidlog's jetty and yard
[V: `data/sea_town.json`], a beached skiff at Lake Viltri [V: `EARLY_ROUTES.md`], and crafting is allowed
[V: STATE "Every Cobblemon item is obtainable without crafting"]. A boat runs at about 8 blocks per second on open water
[A: vanilla], so on the same fatigue clock as a swimmer a boat would cross every strait in this region well inside a
minute. The rule for boats therefore cannot be the fatigue clock alone. Options (decision 1):

| Option | Rule | Consequence |
|---|---|---|
| A | Boats go anywhere | Every island and the far sea are open from S0 by boat. The ferry is a convenience; the level-cap trap is wide open (the Long Isle at 44-50, `LONG_ISLE.md` D5) |
| B | Boats share the swimmer's fatigue clock | In practice the same as A here: no island strait takes a boat a minute |
| **C (recommended)** | **Boats are shallows craft.** Past 96 blocks from land a boat is swamped: its rider is dismounted with a line ("Too rough for a rowboat past the shallows") and swims, and surface exhaustion takes over. **Sheltered water** is an authored exception: the Sound's bay and any harbour basin count as shallows | Boats keep the coasts, lakes, rivers and the Sound. The open sea is for water Pokemon and the ferry. One rule a player can see |
| D | No boats on the sea at all | Breaks Pacifidlog's boat culture and Sunset West's slipway. Rejected |

Option C needs the exhaustion system's distance field and a check on each boat with a player in it
(`execute on passengers`, `ride ... dismount`) [A: vanilla commands, not run here]. The Sound's crossing leaves the
shallows for 60 blocks [M], which is why it needs the sheltered-water box.

---

## 5. Fishing

**Decided:** First Cast gives one Poke Rod per player (`cobblemon:poke_rod`) and better rods are placed at other
waters as each one's natural source [V: STATE "What is decided"]. **Not researched:** what a rod's ball changes when
fishing [V: STATE "Early fishing balance"], whether Cobblemon's rods honour vanilla Lure and Luck of the Sea, and what
bait does [A]. So the ladder below names waters and stages, and the rod at each rung is chosen after that research.

**No fishing spawn exists anywhere in the data today** [V: `data/spawns.json` has no `fishing` entry].
`tools/compile_spawns.py` passes the position type through and `fishing` is an upstream position type
[V: `LONG_ISLE.md` section 6], but whether Cobblemon honours a coordinate box on a fishing spawn is unverified [A], and
Habitat Block fishing replacement is untested [V: EXP-021].

### 5.1 The rod ladder

| Rung | Water and stage | How it is given | If balls matter | If enchantments matter |
|---|---|---|---|---|
| 1 | **Route 1 coast, First Cast** (S0) | The fisher's gift (decided; the jetty is built on staging) | Poke Rod | plain |
| 2 | **Lake Viltri** (S2) | Misty's lake crew, after `SQ-G2-01` ("water-travel supplies") | Great or Lure Rod | Lure I |
| 3 | **Peak Pond** (S4) | Erika's pond fisher at the new jetty | Ultra or Nest Rod | Lure II |
| 4 | **Pacifidlog, the Guild** (S6-S8) | The rod master, per player (`LONG_ISLE.md` section 6) | Lure or Net Rod | Luck of the Sea I |
| 5 | **The Relic reef cache** (S6) | The sunken fragment's cache (section 3.2) | Dive Rod | Luck of the Sea II |
| 6 | **The Watering Hole** (S7-S8) | A find at the fishing stage (WATER_MAP #17) | Quick or Luxury Rod | Lure III, Luck of the Sea III |

Rod item ids other than `poke_rod` are ASSUMED (`LONG_ISLE.md` says the same). Any rod can also be made at a
smithing table from a Poke Rod template, a rod and the matching ball [V: STATE, Cobblemon 1.8.0 jar]; the template is
fishing treasure, so crafting stays a second route.

### 5.2 Fishing spots

Each water fishes at **its own stage's levels**, never the sea band's: fishing reaches over-cap catches that the
route pools avoid [V: STATE "The level-cap trap"].

| Spot | Stage | Candidates (for `trainer-balance-designer`) | Ties to |
|---|---|---|---|
| First Cast jetty, Route 1 coast | S0 | Magikarp, Tentacool, Krabby, Shellder, Horsea at 7-12 | First Cast; the Southern Shallows have no roster yet (WATER_MAP decision 9) |
| Relic Island, off the reef | S0-S2 | Luvdisc, Corsola, Staryu, Remoraid at the coast band | The reef (section 3.2) |
| Lake Viltri, Misty's piers | S2 | Goldeen, Poliwag, Magikarp, rare Chinchou at 16-22 | The lake roster [V: WATER_MAP inventory] |
| Viltri's Path mouth | S2 | Goldeen, Poliwag, Wooper | The water road's end |
| Peak Pond jetty | S4 | Basculin, Whiscash, Goldeen, rare Gyarados at 30-32 | The pond roster [V: WATER_MAP] |
| Tilpey, Sabrina's dock | S6 | Arrokuda, Seaking, Basculin at 39-46 | The lake roster [V: WATER_MAP] |
| Pacifidlog: under the rafts, Fishers' Row, the Current Gate | S6-S8 | `LONG_ISLE.md` section 6's three lists at 44-50 | Fishers' Row's 17 stations are built on staging [V: STATE] |
| Watering Hole stage | S7-S8 | Barboach line, Goldeen, rare Feebas (decision 10) | The arrow_creeks roster |
| Sunset West quay and south pier | any; best postgame | Harbour catches; the charter's deep-sea fishing at the postgame band | `SQ-SUNSET-01` |

---

## 6. Docks

| # | Dock | Where | Status | Serves |
|---|---|---|---|---|
| 1 | **First Cast jetty** | x1049-1057, z5347-5351, deck y64 | Built on staging [V: `EARLY_ROUTES.md`] | The Poke Rod; S0 fishing; the Relic row |
| 2 | **Viltri sounding platform** | x1725-1733 at the waterline | Built on staging [V: `EARLY_ROUTES.md`] | The sounding; the Surf school |
| 3 | **Viltri north-bank platform** | x1601-1607, z3060-3068, with a beached skiff | Built on staging [V: `EARLY_ROUTES.md`] | The floor survey; a boat |
| 4-5 | **Misty's two piers** | x1560-1567 and x1648-1655, z2862-2904 | Planned anchors, Axiom composition, no prep [V: `data/placements.json` gym2_town] | Rod 2; fishing; the lake's boats |
| 6 | **Sunset West: quay, west pier, south pier, slipway** | x2578-2703, z6519-6640 | Planned earthworks [V: `data/placements.json`] | The strait ferry; the charters; fishing; boat-building |
| 7 | **Pacifidlog: mainland jetty and landing** | (7092-7172, 6704-6718) | Built on staging [V: STATE, `data/sea_town.json`] | The Sound ferry; the boat rack |
| 8 | **Pacifidlog: Fishers' Row, the yard's wharf, the Current Gate, the stilt landings** | the Sound | Built on staging [V: STATE] | Fishing, boats, the Guild's rod |
| 9 | **The Relic landing** (new) | the islet's north shore, facing First Cast | Proposed | The Relic row |
| 10 | **The Sunset isle landing** (new) | the isle's north shore, about (2570, 6918) [M: nearest isle land to the south pier] | Proposed | The strait ferry |
| 11-13 | **Tilpey: Sabrina's town dock, the Weeping Elder landing, the south-shore landing** (new) | north shore at Sabrina's town; the island; the south shore | Proposed | The launch; the survey diver (the Dive school); Tilpey fishing |
| 14 | **The north-east landing** (new) | the north-east coast facing the Pine Isles. The shortest gap is from about (6586, 2294) to (6886, 1946) [M]; the marsh outflow's own mouth at (5662, 1598) is 871 blocks out, 205 of them deep [M], so the landing belongs on the short gap | Proposed | The Northlight packet |
| 15 | **The Northlight landing** (new) | South Pine Isle, the shore nearest the mainland | Proposed | The Northlight packet |
| 16 | **Peak Pond jetty** (new) | the pond's town side | Proposed | Rod 3; fishing |
| 17 | **The Watering Hole stage** (new) | the pond's shore, with a boat rack | Proposed | Rod 6; fishing; a stop on the Lakes' River |
| 18 | **The Lakes' River head** (new) | Shrew Lake's south shore, at the outflow | Proposed | A boat rack for the water road |
| 19 | **The appearing island's landing** (new, part of its template) | (1600, 8400) | Proposed, postgame | The charter |

That is 19 docks: 8 built or planned (Sunset West's four structures and Pacifidlog's waterfront counted as one each),
11 new. Each new
one is small: a jetty of the First Cast size, a post, a lantern, a sign, and a boat rack only where a water road starts.
Boat racks need a keeper function to stay full [V: `LONG_ISLE.md` section 5 proposes it; NOT VERIFIED there].

---

## 7. What the ocean bands are for, beyond spawn levels

The bands exist as data only in the Windward Sea today: shallows 0-96 blocks from land at 16-20, open water 96-256 at
20-25, the deep beyond 256 at 25-30 [V: `data/spawns.json` `marine_zones`]. Surface exhaustion uses the same three
distances [A: as briefed]. So **one distance-from-land field decides four things**:

| Band | Levels | Surface exhaustion | Boats (option C) | Content that belongs there |
|---|---|---|---|---|
| **Shallows** (0-96) | The nearest leg's band | Free; recovers fatigue | Allowed | S0 content: First Cast, Relic Island and its reef, Fungal Isle, the coasts as roads, the Sound's narrows |
| **Open water** (96-256) | +5 | Builds | Swamped (except sheltered water) | Mount or ferry content: the straits, the sunlit wrecks, the ferry lanes |
| **The deep** (256+) | +10 | Builds twice as fast | Swamped | Far content: the forge ruin, the magma cove, Lapras and Wailord, the appearing island, the trench |

Two consequences for the build:
- **Every sea needs a band map, not just the Windward Sea.** The Southern Shallows (Pallet, Relic Island, Sunset
  West) have no roster (WATER_MAP decision 9); nor do the Eastern Reach, the Frostwater Shelf or the Sound.
- **Ferry lanes stay in shallows where they can** (the Relic row, the coast roads) and cross open water only where an
  island makes them.

---

## 8. Balance check by stage

| Stage | On the water | Under it (air) | New water content | Rods | Over-cap risk |
|---|---|---|---|---|---|
| S0 | Swim the shallows; the Relic row | Vanilla, then two lethal hits [V] | First Cast, Relic Island, the reef's edge, Viltri Light | 1 | Sunset strait and Sound ferries run from the start; the Sunset isle's placeholder band is 25-45 [V: `SAPLING_BIRDS.md`] |
| S1 | First water Pokemon; the open water | Vanilla | The fishing-boat wreck | 1 | The Windward Sea's deep band at 25-30 is over the cap until Misty [V: STATE] |
| S2 | Viltri's Path road | **Surf** [V: EXP-042 run 2] | Viltri survey, the Shrew pit, the slope wreck | 2 | Shrew's rare Dratini (the owner reviews) |
| S3 | — | Surf | **Mesprit** | 2 | — |
| S4 | — | Surf | Peak Pond, the tarn | 3 | — |
| S5 | The Northlight packet | Surf | **Azelf** | 3 | Northlight's rosters, if early arrival is allowed |
| S6 | The Tilpey launch | **Dive** [V: EXP-042 session 3] | Tilpey practice, the Relic fragment, the forge ruin, the coves, Pacifidlog and the Sound wreck | 4, 5 | The Long Isle at 44-50 is the intended detour |
| S7 | — | Dive | **Uxie**, the Watering Hole | 6 | — |
| S8 | — | Dive | — | — | — |
| L | — | Dive | Milotic (built) | — | — |
| P | Charters | Dive | **Lugia**, **the appearing island**, Northlight's stories | — | Postgame bands |

- **Every stage from S0 to S7 has something in the water** except S8, which is fine: Giovanni's leg is a land leg and
  the League is next.
- **The middle is wet.** The three Surf wrecks, the Viltri survey, the Shrew pit and two of the trio fill S1-S5; Dive
  content is still back-loaded, as WATER_MAP says it must be.
- **Nothing stacks gates.** No site has a shrine with Dive or Strength; the trench's keys are its puzzle, and the
  appearing island's night is its schedule, not a second lock.
- **The one real balance risk is early arrival**: ferries and boats that run from S0 reach islands whose rosters are
  over the cap. That is the level-cap trap's fix, not the ferry's (STATE "The level-cap trap"; `LONG_ISLE.md` D5).
  Decision 6 gives the fallback: gate the Sound ferry at `gym6_cleared`.

---

## 9. Blocked by

| Waits | On | Where it stands |
|---|---|---|
| The boat rule, sheltered water, the ferry's purpose | **Surface exhaustion** | Being built (EXP-043) by another agent |
| Every ferry line | `data/ferries.json` and its generator; a re-apply step | Not written. The parts are proven one by one (section 4.2); a scene NPC has never been clicked (EXP-034); two players unproven (EXP-022) |
| Surf and Dive in the story | Misty's grant and the survey diver's event calling `cobblers:water/grant_surf` and `grant_dive` | The functions are built [V: `tools/blackout_pack.py`]; the events are not written |
| Any "a mount" claim | A ridden submarine mount keeping its rider's air | Untested (EXP-038 step 2). If it does, it bypasses the ladder |
| Deep lake and sea spawns | Draft PR #61; the owner's observation | Not seen in game |
| Every fishing spot | Fishing entries in `data/spawns.json`; whether box conditions hold on fishing | None exist |
| The rod ladder | Research: rod ids, what the ball does, enchantments, bait | Route to `cobblemon-researcher` |
| The reef, the wrecks, the coves, the forge ruin | A seabed or block pass, coral placement, captured coves, a flooded house variant | No tool exists [V: WATER_MAP section 5] |
| Rosters for the Pallet coast, the reef, the Sound, the other seas | Marine zones beyond the Windward Sea | Only `windward_sea` exists |
| The trio, Lugia, Manaphy | An authored encounter | EXP-006, planned |
| Manaphy and Phione | Client models | Blocked on the ATMxMSD licence |
| The appearing island | The swap function, its occupancy guard, a restart-safe schedule | Nothing built; ADR-003 proposes the guard |
| Caches and rod finds | ADR-002 rewards | Proven only as static files for Victory Road's five finds |
| The Route 7 gorge crossing | The bridge | Not built; required on the critical path |
| Swimmers, Fishers, Sailors | Trainer work | Paused (STATE "Custom leaders") |
| Early arrival at 44-50 islands | The level-cap trap's fix | Open (STATE) |

---

## 10. Open decisions for the owner

1. **Boats beyond the shallows.** Options A-D in section 4.4. *Recommend C:* boats are shallows craft, swamped past 96
   blocks from land, with the Sound and harbour basins authored as sheltered water.
2. **How hard the open sea is.** With a one-minute budget, every island but the Pine Isles is swimmable in 12-18
   seconds of open water (section 4.1). *Recommend:* keep it: the near islands are shallows and should be free, the
   straits a risky swim, the ferry the easy way. If islands must need a mount or a ferry, Slowness at 10 s and pulses
   at 20-30 s of open water would do it.
3. **Surface exhaustion on lakes.** *Recommend:* sea only. Lakes are Surf content.
4. **The ferry's mechanism.** *Recommend:* option A, a ferryman, a dialogue, a fare, a fade and a teleport; no moving
   boats.
5. **Fares.** *Recommend:* the Relic row and the Tilpey launch free; the strait $100 and the Sound $150 each way; the
   Northlight packet $400; postgame charters $600. All live in `data/ferries.json` for tuning.
6. **Ferry gates.** *Recommend:* none on the Relic row, the strait or the Sound (the level-cap fix covers early
   arrival); `gym6_cleared` on the Tilpey launch; `gym5_cleared` on the Northlight packet; `champion_cleared` and
   `SQ-SUNSET-01` on the charters. Fallback if the trap fix is late: gate the Sound ferry at `gym6_cleared`.
7. **Does riding a water Pokemon on the surface need the Surf training?** *Recommend:* no. Surf and Dive are depth
   training [V: DEATH_AND_WIPE.md "This system gates depth, not access to water"]; riding is Cobblemon's own.
8. **The appearing island.** A full-moon island at about (1600, 8400), shared world state, Manaphy once per player,
   Phione repeatable, postgame. *Recommend:* yes; build nothing until the client models and EXP-006 land.
9. **The Relic reef.** The three layers of section 3.2, with the sunken Pallet fragment as the Dive interior.
   *Recommend:* yes.
10. **Feebas.** At the Watering Hole (S7-S8, a rod catch) or not at all, weighed against Milotic as Victory Road's prize.
    *Recommend:* not at all; Milotic stays the prize.
11. **The Surf wrecks.** Three open wrecks (the fishing boat, the slope, the Sound) to keep the sea in play before Dive.
    *Recommend:* yes.
12. **New docks.** Eleven small ones (section 6). *Recommend:* the Relic landing, the Sunset isle landing and the Tilpey
    three first; the Northlight pair with Northlight's content.
13. **Names.** "The Lakes' River" and "the appearing island" are working names. For Codex, with the trio's arc line
    (WATER_MAP decision 1).

## Findings made while writing this (not changed here)

- `data/towns.json` sunset_west's waystone `reason` still says "an island: the waystone is what a sea crossing earns";
  the town has been on the mainland since 2026-09-21. `docs/world-building/SETTLEMENTS.md`'s table still gives the old
  centre (1716, 7298) and "on the largest island". The story docs' stale coordinates are already handed to Codex
  (`docs/HANDOVER_CODEX.md` item 17).
- `data/towns.json` says Sunset West's river is "three-block"; the Watering Hole outflow, whose mouth at (2582, 6494)
  is inside the town's footprint, is graded 10-11 wide [V: RIVERS.md]. One of the two is wrong; not checked in a world.
- `docs/world-building/LONG_ISLE.md` section 5 still says water riding is unread; EXP-038 has since read it (45 surface,
  10 underwater species).

## Appendix: how the crossings were measured

A read-only script (not committed): `tools/ground.py`'s heightmap, rounded; land = y62 or above; the 8,192-square map
reduced to 4-block cells by maximum; the sea padded 512 blocks round the map; distance from land by alternating 4- and
8-connected dilation; each crossing sampled every 4 blocks on a straight line, and the nearest island shore found
inside that island's region polygon. Built ground (Relic's islet, Pacifidlog's decks) is not land in it, and lakes
are. Rerun it before a dock is sited.
