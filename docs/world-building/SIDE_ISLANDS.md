# Side islands: story reasons, a gym move, and the ones left to explore

**Status: design proposal, 2026-10-07 (Wave A unit A10). Nothing here is built, and no data has been changed.**
The ask came from the owner on 2026-10-07 (`docs/STATE.md` "What is decided", the owner's answers to the morning
report, item 14): *side islands: give some a story reason or move a gym there; some stay exploration only.* It goes
back to the 2026-10-05 play test (`docs/PLAYTEST_2026-10-05.md` note 3): *"Make the player visit side islands (or
similar) so the game is not a straight gym-to-gym path"*. It is tracked as U48 in `docs/UNFINISHED_SWEEP_2026-10-06.md`.

**Where the numbers come from.** I had no shell for this unit. Every box, centre, band and distance below is read
from a data record, and the record is named. None was measured on the heightmap. A distance marked "straight line"
is my own arithmetic between two `data/towns.json` centres. It is not a path length. One count is mine: the grep
count of `gym[1-8]_cleared` in section 3, run over `data/`, `tools/` and `tests/`.

## 0. Premises that are wrong or stale

Each of these changes the design below, and none has been fixed here (this unit writes one file).

| # | The premise | What the data says |
|---|---|---|
| F1 | Pacifidlog is on the Long Isle | `data/towns.json` `sea_town` still says `region: long_isle`, with centre (7210, 6960). `data/sea_town.json` `site.centre` is **(5160, 7380)**, on the drowned Jungle Isle bank. The town record is stale; this is U68, already known |
| F2 | A player without a water mount reaches Pacifidlog by ferry | **Nobody can.** The Sound ferry is `retired`. Its replacement, `pacifidlog_ferry`, cannot run: its south jetty stood 7 blocks under the sea and was removed, and its other stop, `pacifidlog_square`, is retired (`data/ferry_docks.json` `not_sited`, `pacifidlog_south_jetty`). Today the town is reachable only by riding something. That breaks the owner's rule "the ferry IS the gate" in the closed direction |
| F3 | Sunset West is an island town | It moved to the mainland shore of the strait on 2026-09-21 (`data/towns.json` `sunset_west`, centre (2660, 6490)). It is the harbour for the isle, not part of it |
| F4 | The charters are a way to the outer islands | All four charters need `quest.sq_sunset_01.completed`, and **nothing grants it** (`data/ferries.json`, `blocked_by` on each charter). The Jungle Isle charter is also retired. Every charter is shut |
| F5 | Misty's gym is an island | It is the Cobbleverse `misty` template, standing on Lake Viltri in Viltri Quay (`data/placements.json` `gym2_misty_gym`, corner (1594, 107, 2859)). Its floating-island shape is the template's own (review N82). There is no `data/gym_buildings/gym2.json`: gym 2 is the only gym without an authored building. **The owner has parked Misty** (`docs/HANDOVER_SESSION.md` 2c: "Parked by the owner: Mega carry, team tuning, Misty, doubles") |
| F6 | The Jungle Isle is gone | It is under the sea (STATE line 297), but `data/regions.json` `jungle_isle`, `data/spawns.json` subregions `jungle_west` and `jungle_east` (band 43-53) and `data/towns.json` `jungle_ruins` ("Sunken Court", `proposed`) still describe it |
| F7 | Records about the isles are current | Four are stale. `data/regions.json` `long_isle` `character` still says "taiga in the north grading to jungle". `data/ferry_docks.json` `sunset_isle_landing` says "nothing else on the isle is built yet", but the Dusk tower and the Old Orchard stand there (STATE lines 38, 51). `docs/story/SIDEQUESTS.md` SQ-SUNSET-01 and SQ-SUNSET-02 still use the old Sunset West site (1716, 7298) and the drowned ruins (5160, 7463). `docs/world-building/LONG_ISLE.md` says the band is 44-50, while `data/spawns.json` gives `long_isle_north` and `long_isle_middle` `level_band` 38-48 and `long_isle_south` 43-53. Those may be roster levels against band edges, but they do not agree as written |

## 1. Inventory

Sources for each column:
- **Box:** `data/regions.json` `measured.bounds`, or a site record where named.
- **Band:** `data/spawns.json` subregion `level_band`.
- **Reach:** `data/ferries.json`, plus the swim table in `docs/mechanics/WATER_BUILD_PLAN.md` 11.1.

The reach column assumes the rules as built:
- Swim fatigue knocks out an unaided swimmer after about 18 s of deep water, and a trained swimmer goes about twice as far.
- Riding anything recovers fatigue.
- Boats are tipped 48 blocks or more from land.
- The first water mount (Gyarados at 20) arrives around gym 1-2 (STATE "Surface exhaustion", line 280).

| Island | Box / centre | Band | What stands on it now | How a player reaches it, and when |
|---|---|---|---|---|
| **Relic Island** | dry core (1082-1101, 5522-5541); built islet, crown y70 (`data/towns.json` `relic_island`) | (none) | The Ash House: a displaced Pallet home, F4 (`docs/world-building/events/F4_RELIC_ISLAND_ASH_HOUSE.md`); lights; the reef | The **Relic row** from First Cast is free and ungated. The swim from Pallet's beach arrives exhausted, with no hit. Reachable at **S0** |
| **Fungal Isle** | (0-983, 5216-6247); 0.782 km² | 18-28 (tier 3, basis `route_03_misty_to_surge`) | **Zapdos's tower** on the east shelf, altar (895, 69, 5583). Its altar needs a `thunder_feather` that nothing hands out; Zapdos rolls 50-60, and there is no gate (`data/adopted_legendary_sites.json` `adopted_zapdos_tower`) | No ferry. Unaided swimmers are knocked out (198-234 block crossings). A **trained** swimmer arrives exhausted with no hit, so after Misty's Surf training (S2), or by mount |
| **Newmoon Island** | floating, corner (24, 5582) y141, 101x58x100, over Fungal North (`sweep_newmoon_island`) | (none) | **Darkrai**, hidden; the Nightmare Weaver is earned at `champion_cleared`; loot open to anyone who flies up | Flying only. It can be seen from the top of Zapdos's tower |
| **Driftmouth Isle** | centre (336, 1798), radius 28, built (`data/sea_drift.json` `island`) | water Habitat Blocks (Chinchou to Dratini and Lapras) | Driftmouth Light, the keeper's hall, four sea stacks | The **Seaward Drift**: a 1.1 km straight rail road from Foothill Gate (1461, 1795), which is on Route 3 (Misty to Surge). Reachable from **leg 3** on foot |
| **Northgate Isle** | (4728-6071, 0-1007); 0.898 km² | 33-43 (tier 6) | **Crown Spire** (Glastrier, hidden) at (5348, 130, 484); Northgate's old growth (the Grookey line) | **No dock and no line.** It is 304 blocks from marsh country, which knocks out even a trained swimmer (WATER_BUILD_PLAN 11.1). Mount only |
| **North Pine Isle** | part of the Pine Isles (6416-8079, 0-2055); 1.938 km² for both | 33-43 (tier 6) | **Dawn tower** (Necrozma Dawn Wings, level 80) at (7480, 99, 316). Its summit wakes only for a Champion | From South Pine Isle (the two isles are one region in two pieces), or by mount |
| **South Pine Isle** | as above | 33-43 (tier 6) | **Northlight**, a major town at (7265, 1556), 231-block square: the aurora observatory and ice field station. It has Mart, houses, a Timburr worker and the **Ice stone** face (STATE lines 242, 243, 339). SQ-NORTH-01 and SQ-NORTH-02 are written; Rowlet's find is in the heart | **Northlight packet**, $400 each way, gated on `gym5_cleared`, from the north-east landing (6605, 2301). **Coldwater launch**, $400, `gym5_cleared`, from (6075, 1833) (Coldwater Station is authored, not applied). Reachable from **leg 6** |
| **The Long Isle** | (6832-8191, 4432-8015); 2.559 km² | north and middle 38-48 (tier 7, basis `route_07_sabrina_to_blaine`); south 43-53 (tier 8) | Repainted as desert in the north and middle and jungle in the south. In the south: the **Mew temple** (corner (7604, 7082), y142; the door opens for the Champion), four relocated elders with their nests, and the **lost temples** (`data/jungle_temples.json`: authored, not audited, not applied) | Walkable in practice. The Sound narrows: 61 blocks at z6024 (`data/ferries.json` `long_isle_narrows`), and at z6100 an unaided swimmer is "slowed, no hit". The **bridge is decided** (LONG_ISLE D4) but not designed. Reachable from **S0**, which is the D5 early-arrival problem |
| **Sunset Isle** | (816-3551, 6664-8015); 2.559 km² | west 28-38 (tier 5); east 43-53 (tier 8) | **Dusk tower** (Necrozma Dusk Mane, level 80, Champion) at (1156, 146, 7216); the **Old Orchard** at (2768, 7076), with the Orchard Sleeper (a level 60 Slaking) and the giant palm | The **Sunset strait ferry**, $100, **no gate**, from Sunset West's south pier. The strait (255 blocks) knocks out every swimmer. Reachable from **S0** for $100 |
| **Pacifidlog** (the drowned Jungle Isle bank) | sea town at (5160, 7380) (`data/sea_town.json`); the old island box was (4384-5935, 6880-7983) | jungle residue 43-53 (F6) | The rafts, the Stilt Quarter, Fishers' Row, the Current Gate. A **town on the water**, mostly decks | **Mount only today** (F2) |
| Weeping Elder islet | in Lake Tilpey | Tilpey | The demoted Weeping Elder and its glade (STATE line 183) | The **Tilpey launch** (free, `gym6_cleared`). Its three docks are built, but the line is not emitted: `tools/ferries.py` cannot walk a lake at y77 |
| Skerries | `windward_skerries` (0-760, 2600-5200) and `north_west_skerries` (300-1000, 1400-2600) (`data/water_shape.json`) | (none) | Rocks and sea stacks for Wingull, and rest points | Swim or boat; texture rather than places |

Not islands of this map, so out of scope here:
- the appearing island (Manaphy): outside the heightmap and unsited;
- Lugia's trench marker: unsited;
- Rayquaza's sky island: in the `cobblers:pocket` dimension (`docs/world-building/KYOGRE_CAVE.md`).

## 2. The call for each island

The design rule I applied: **the owner asked for "some", so one island goes on the critical path. A few more get a
story reason the campaign points at, and the rest stay places to find.** Every island already holds a legendary
site or a town, so exploration-only does not mean empty. It means nothing tells the player to go there.

| Island | Call | Why |
|---|---|---|
| **South Pine Isle (Northlight)** | **STORY, REQUIRED, on leg 6** (P1) | Everything already lines up:<br>- Its band (33-43) is leg 6's.<br>- Its two boats open at `gym5_cleared`, the badge a player holds when leg 6 begins.<br>- It is a built town with a written quest (SQ-NORTH-01: "some instability travels through the sky and water before it is visible as a ring").<br>- That quest is the Rift story told from the sky, and the next leader, Sabrina, runs a town that "records what the Rift does to memory and perception" (`data/gym_buildings/gym6.json` `reading`). One research question links the two towns.<br>Of all the islands, this one needs the least new building to make it required |
| **The Long Isle** | **STORY, signposted on leg 7** (P2); required only if the owner says so (Q4) | Its desert band is leg 7's, and the owner decided to build a bridge to it. The bridge needs a reason to exist, and Bridgekeep's written quest (SQ-GORGE-02, "The Keeper Who Hates Bridges") is a ready voice for it. The lost temples are where the drowned ruins' quests were meant to move (LONG_ISLE 11.4) |
| **Sunset Isle** | **STORY, late (after gym 8)** (P3) | SQ-SUNSET-01, "A Boat for the Outer Sea", is the quest every charter already waits on (F4). Making the isle the setting of that quest unshuts four lines with one grant. The Dusk tower and the Orchard Sleeper (level 60) are late content. Gym 8's town is the nearest gym, 987 blocks off (`data/towns.json` `sunset_west` `nearest_settlement`) |
| **Fungal Isle** | **EXPLORATION early; STORY on a late return** (P4) | At S2 it is the first island a Surf-trained swimmer can reach. That is a reward in itself and needs no text. Its story reason is Zapdos: the altar waits on a thunder feather, and Zapdos rolls 50-60, so the feather belongs at gym 7 or 8, beside Moltres's (Q5) |
| **Relic Island** | **STORY, as it is** | It already has its event (F4 Ash House), its free row and SQ-HOME-02. Nothing to add |
| **Pacifidlog** | **STORY (a town), blocked** (P5) | The town is built and has a voice. What it lacks is a way in without a mount (F2). Repair the ferry; do not give it a new reason |
| **Northgate Isle** | **EXPLORATION ONLY** | It holds a hidden legendary (Crown Spire) whose design is "not on any path" (`hidden: true`). It has no dock, and mount-only access is the point. Giving it a story reason would undo a deliberate hiding |
| **North Pine Isle** | **EXPLORATION ONLY** | The Dawn tower is post-Champion. A Northlight visit (P1) will bring players within sight of it, and that is the right amount of pointing |
| **Driftmouth Isle** | **EXPLORATION ONLY** | It is the far end of an authored ride, with its own lighthouse, mine and water spawns. It is already a destination off leg 3, and the drift is the story |
| **Newmoon Island** | **EXPLORATION ONLY** | It is hidden and found by eye from Zapdos's tower. That chain of discovery is better than any line of dialogue |
| Weeping Elder islet, skerries | **EXPLORATION ONLY** | Too small to carry content. The Tilpey launch stays blocked on the tooling (a per-crossing water level) |

### 2.1 The gym move: the candidates, and my recommendation

**Rule first: a move must keep the gym's number.** Badge flags, chapters, Mart tiers, residents, level caps and the
gates of every system are keyed by ordinal. I counted 555 occurrences of `gym[1-8]_cleared` across 78 files in
`data/`, `tools/` and `tests/` (grep count, this unit). `data/progression.json` sets each flag on its leader's rctmod
defeat, and chapter N is unlocked by `gym{N-1}_cleared`. Moving a leader to a different place in the order is a
renumbering, and it is out of scope. Moving a leader to a different town at the same number keeps every flag's
meaning.

| Candidate | Thematic fit | Fit to the island's band and reach | What would be lost | Verdict |
|---|---|---|---|---|
| **Sabrina (gym 6) to Northlight** | Good: the observatory sees what is coming | **Exact:** band 33-43, ace 45, boats open at `gym5_cleared` | **The Hall of Lenses** (`data/gym_buildings/gym6.json`), which was written for Tilpey Cross's white axis and highest ground. Tilpey Cross is a town built round Sabrina: memory stones, Abra and Natu at the spire (STATE line 243), SQ-G6-01/02, EVT-G6-SLOWPOKE-FERRY. The Tilpey launch is gated on Sabrina's badge because it is her town's boat | **The best of the three, and still not recommended**: see P1-alt |
| Blaine (gym 7) to the Long Isle | Canon: Cinnabar is an island | Exact: band 38-48, ace 50, reachable on foot | **The Assay House** (`gym7.json`), built round the crater's vent, and Cinderlee's whole reading as a research town on the rim. The Long Isle has no town to host a gym, so it needs a new town, a new gym and the bridge. It is the largest build of the three | Rejected |
| Misty (gym 2) to a sea island (Pacifidlog, Driftmouth) | Good on water | **Bad.** Gym 2 comes before the first mount, so the critical path would cross the sea at S1 on a ferry. Pacifidlog is at the far south-east and leg 2 is in the north-west. Driftmouth is 28 blocks in radius | Viltri Quay's reason to exist ("the town's reason to be here is the lake", `gym2_misty_gym` `chosen_because`). Cheapest building cost, since there is no authored gym 2 building | Rejected; **the owner has parked Misty** (F5) |

**Recommendation: do not relocate a gym. Use P1-alt, "the leader's work is on the island".** It gets the forced
island visit the play test asked for, keeps the Hall of Lenses and Tilpey Cross whole, and adds one trainer and one
requirement instead of a gym. If the owner still wants a gym to stand on an island, Sabrina to Northlight is the one
to cost, and its costs are listed in full under P1-move.

## 3. What each proposal needs

The layers are: data (authored records), generator (a tool that emits a pack from that data), and new mechanism (a
behaviour that nothing in the repository does yet). A place's coordinates come from its own plan and are seated by
its tool; **this document proposes no new coordinate.**

Codex is the dialogue author: `data/ferries.json` `messages.voice` marks its lines "PLACEHOLDERS for Codex's
voice".

### P1-alt (recommended): Northlight before Sabrina

**The story.** Tilpey Cross studies what the Rift does to perception, and Northlight sees the weather arrive early.
Sabrina has lent Northlight one of her students to read the aurora against the rings. She will not take a challenger
who has not seen the sky do it.
- The player crosses to Northlight, takes the synchronised reading (SQ-NORTH-01, promoted from a sidequest to a main
  step) and beats the student.
- The student is a trainer of the observatory, not a gym junior.
- Sabrina's door is open to everyone. Her battle refuses only a player who has not beaten the student.

**Mechanism.** rctmod's own `requiredDefeats` does the check. Read from rctmod's source in
`docs/research/RCT_PER_PLAYER_MODE.md` line 95, eligibility includes "missing `requiredDefeats` (filtered to required
ids that are of the player's current series) empty". It is per player, so it holds in co-op: a friend who skipped the
island is refused alone. This is principle 6, rung 2, with no new mechanism.
- **Not seen in game.**
- I have not checked whether any of our trainer files already sets `requiredDefeats`.
- What a refused player sees from rctmod is not known. A gym aide's flag-keyed line should tell them, so the refusal
  is never silent.

**What it needs, by layer:**
- **Data:**
  - `data/trainers.json`: one record for the student, with its team from `trainer-balance-designer`, under Sabrina's
    ace of 45. It needs a `modes.challenge` twin, because the requirement is filtered by series and a Challenge
    player is in `cobblers_challenge`.
  - Sabrina's normal and challenge records each gain the requirement.
  - The A1 swap (one spawner, `TrainerIds` swapped to `_challenge`) must carry the requirement into both ids.
  - `data/progression.json`: one flag, `northlight_reading_taken`, set by `trainer_defeat` as the gym flags are, so
    dialogue can read it.
  - `data/placements.json`: the student's seat inside Northlight's plan, seated by the town and NPC seating tools
    from the plan.
  - `data/dialogue.json`: the pointer at Fenhide after Koga, Sabrina's aide, and the student.
  - `data/quests.json`: SQ-NORTH-01 as a main step.
- **Generator:** none new. `tools/challenge_mode.py` and the trainer emitters already write rctmod files. The
  emitters must pass the requirement through; whether they do today is not checked.
- **Check:** `gym_trainers_audit`, or a sibling audit, owes one rule: every leader requirement names a trainer that
  is seated, in both series. That is the "our list is not the world" lesson.
- **In game:** the Northlight packet itself. No click, charge or teleport of any ferry line has run on this world's
  build (`data/ferries.json` `not_proven`), although the owner rode two lines on an earlier world.
- **Cost the owner should see:**
  - Two crossings at $400 each, on the critical path. Whether leg 6 income covers that is an economy question
    (A3/economy audit). A player with a mount pays nothing.
  - The walk, as straight lines: Fenhide to the Coldwater jetty 1,555 and the jetty to Tilpey Cross 1,570, against
    Fenhide to Tilpey Cross at 1,819.
- **Codex writes:** the student, the aide, Sabrina's refusal and acceptance lines, the Fenhide pointer, and the
  quest text.

### P1-move (costed, not recommended): Sabrina's gym to Northlight

What changes, item by item:

**The authored building:**
- `data/gym_buildings/gym6.json` is bound to Tilpey Cross's lot (6180, 3302)-(6212, 3334), at level 97.
- A Northlight gym needs a new building record and a lot in Northlight's plan. STATE line 339 says every lot is
  taken, so a gym lot means giving up houses.
- Staging must demolish the hall and rebuild it on the island.

**Routes:**
- `route_06_koga_to_sabrina` and `route_07_sabrina_to_blaine` in `data/routes.json` end at `gym6_town`, and both
  would cross 388-437 blocks of sea.
- Straight lines: Fenhide to Northlight 2,766 against 1,819 today; Northlight to Cinderlee 3,639 against 1,602.
- Every route trainer, signpost, route event and `nearest_leg` along those legs moves (`tools/measure_towns.py`
  rewrites the last).

**The level curve and leg order:** unchanged. Sabrina stays gym 6 with an ace of 45.

**Waystones:** Northlight's waystone changes from discovery to a gym-town waystone (`tests/test_gym_waystones.py`).
Tilpey Cross keeps a discovery waystone.

**The ferry:** the packet becomes a critical-path line, so $800 is paid by every player without a mount. If either
dock fails, the campaign stops.

**Challenge spawners:** the single swapped spawner from A1 moves, and so does `tools/challenge_mode.py`
`spawner_files`. Any donor spawner left at Tilpey (the `cobbleverse:sabrina` shell is cleared by gym6.json's own
clearing parts) must be swept for.

**Badge flags:** `gym6_cleared` keeps its meaning. What breaks is the geography keyed to it: the Tilpey launch
("belongs to EVT-G6-SLOWPOKE-FERRY", Sabrina's town), the Mart tiers and the residents near Tilpey.

**Juniors:** A2's three or more juniors are re-seated.

**What it gains over P1-alt:** a gym on an island, and Northlight as a town the critical path passes through. That
is all P1-alt does not already give, and it costs a gym, two legs and a town's identity.

### P2: the Long Isle and its bridge (story, signposted on leg 7)

**Data:**
- The bridge: a large span, which needs its own design (LONG_ISLE D4) in `data/bridges.json`.
- A gatehouse on `gym6_cleared` at the mainland end, using the Rift mine ward's pattern (LONG_ISLE D4).
- The lost temples as the home of the drowned ruins' quests: SQ-SUNSET-02 and the jungle quest re-sited from
  (5160, 7463), so a separate `docs/story/` edit, plus `data/quests.json`.
- Bridgekeep's SQ-GORGE-02 as the bridge's voice.
- A pointer from Cinderlee or Tilpey Cross.

**Generator:** `tools/bridges.py` builds a 43-block span only. A landmark bridge with piers and a boat channel is new
generator work for a builder with a shell.

**The truth about the gate:** a gatehouse stops walkers only. The narrows (61 blocks at z6024, slowed with no hit at
z6100) stay swimmable from S0, so **gating the bridge does not gate the island.** D5's level-cap answer is still
needed.

**Open:** `data/jungle_temples.json` owes its independent audit before anything is pointed at it.

**Codex writes:** the keeper, the temple quests, the pointer.

### P3: Sunset Isle and the boat (story, after gym 8)

**Data:**
- Author SQ-SUNSET-01 with steps on the isle: the boatbuilders' survey to the Old Orchard and the foot of the Dusk
  tower, and the optional Relic leg it already names.
- A grant of `quest.sq_sunset_01.completed`, through the existing dialogue compiler and flags (EXP-022).
- This opens the Relic, trench and appearing-island charters with no change to `data/ferries.json`, since the field
  is already declared.
- Re-site the quest's coordinates in `docs/story/SIDEQUESTS.md` (F7).

**Generator:** none new.

**The alternative,** already offered by `data/ferries.json` `blocked_by`: drop the quest gate from the charters (one
line each) and leave the isle exploration-only (Q6).

**Early arrival:** the strait ferry is $100 and ungated, so an S0 player can land beside the 43-53 east and a level 60
Slaking. The level cap protects catches. Whether to gate the ferry is Q10.

**Codex writes:** the boatbuilders, the survey lines, the charter ferryman's new greeting.

### P4: Fungal Isle's return (Zapdos)

**Data:** a `thunder_feather` handout. Moltres's feather comes from Shrew Station at `gym8_cleared`
(`adopted_moltres_tower` `gate`). The Zapdos record names Shrew Station's storm log or the Frostpeak camp as
candidates and leaves the choice to the owner. The rolls run 50-60, so the badge decides how many rolls are
catchable (Q5).

**Generator:** the research station's or Frostpeak's existing reward emitters. Their hand-out mechanism is not
checked here.

**New mechanism:** none, but the altar itself is unproven. Whether an altar with no anchor answers is EXP-048's open
step 2.

**Codex writes:** the feather's line, and a rumour pointing west from Pallet.

### P5: Pacifidlog's way in (repair)

**Data:**
- Re-site `sea_town_mainland_jetty` (`data/placements.json`) to the real shore. Measured for whoever does it: "along
  x5160 the water ends about z6574 (ground y62) with land at z6562 (y63)" (`data/ferry_docks.json`).
- Re-declare a square stop at the re-sited town in `data/ferries.json`.
- Correct `data/towns.json` `sea_town` (U68).

**Generator:** `tools/ferries.py` and `tools/ferry_docks.py`, as they stand. This is wave B's U79, the ferry
migration, and contracts C3 and C14.

**Codex writes:** the ferryman.

### Housekeeping the calls depend on (not designs)

These need to be retired or corrected so that no island story reads drowned or stale records:
- The Jungle Isle records (F6).
- The `long_isle` `character` line and the Sunset landing's `landward` line (F7).

## 4. Questions for the owner

1. **Required or pointed at?** Should the Northlight step be **required** for Sabrina (rctmod refuses her battle
   until the student is beaten), or only signposted?
2. **A gym on an island, or the leader's work on an island?** I recommend P1-alt: no gym moves. If you want a gym to
   physically stand on an island, is it Sabrina to Northlight with the costs in P1-move, or another leader at the
   same number?
3. **The packet on the critical path:** P1 makes two $400 crossings near-mandatory for a player without a mount.
   Keep it, make the first crossing free, or lower the fare?
4. **The Long Isle:** keep it pointed at (P2), or also require something there for Blaine? And do you accept a
   bridge gatehouse on `gym6_cleared`, knowing the narrows stay swimmable?
5. **The thunder feather:** who hands it out, and at which badge? `gym8_cleared` matches Moltres and makes every
   50-60 roll catchable.
6. **SQ-SUNSET-01:** should it become the Sunset Isle's story and open the charters (P3), or should the quest gate
   come off the charters and the isle stay exploration-only?
7. **Pacifidlog:** it is reachable only by mount today. Repair the ferry now, ahead of the rest of wave B's U79?
8. **The drowned records:** retire the Jungle Isle region, its two subregions and the Sunken Court record now (F6)?
9. **Northgate:** should it stay mount-only, with no dock, as the hidden Crown Spire's home?
10. **Sunset early arrival:** should the $100 strait ferry stay ungated at S0, given the 43-53 east and the level 60
    Slaking?
11. **Misty:** confirm she stays parked and out of this work (F5).
