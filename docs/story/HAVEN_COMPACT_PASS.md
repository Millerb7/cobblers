# The Haven Compact pass: more story points, more battles

**Status:** design proposal (unit COMPACT-STORY, 2026-10-11), for the owner and the builders. It writes no story
text: the lines are Codex's (`CAMPAIGN_OUTLINE.md:4-5`), and where a point needs a line this document says what the
line must do. Teams are themes and level bands; `trainer-balance-designer` sets the exact teams.

**The owner (2026-10-11):** "I want to make sure we have enough inclusion of the evil faction through the world, so we
need to add more story points for them that a player would go through. Especially some fun new battles to add to the
game."

**Numbers.** Measured ones say how they were measured. Leader aces 20/25/30/35/40/45/50/55 and leg lengths are
**relayed** from `CAMPAIGN_OUTLINE.md:13-15` (which relays `docs/STATE.md:327` and `docs/HANDOVER_CODEX.md:31-38`).
Teller seats are relayed from `CAMPAIGN_OUTLINE.md` chapters 2-8. No new coordinate is proposed here: every point is
anchored to an existing `data/` id, and the seat inside it is `world-content-dev`'s to measure on `tools/ground.py`.

## 0. Premises checked

| Premise | What the files say |
|---|---|
| The faction is the Haven Compact | **True.** `ARC.md:74-82`, `FACTION.md:1-23`, `data/rift_regions.json:245-253`. |
| It is "the evil faction" | **Not as the owner has defined it.** `data/rift_regions.json:253`: "the Haven Compact, which already exists and is **not evil** (owner, 2026-09-22). Do not invent a new one." `CAMPAIGN_OUTLINE.md:220` (relaying the owner): "Its people are heroes to themselves." `ARC.md` rules 3-5 (`:62-66`): the player understands the rescue purpose *before* opposing it, displaced families stay visible, and the moral line is crossed at the Craters, not earlier. **This pass designs to those rules.** Before the Craters, Compact battles come from secrecy, guarding families, or disagreement. After the Craters, the loyalists who carry on are the opponents. Question O1 asks the owner to confirm this. |
| There are Compact battles in the world | **Only after badge 8.** The HQ tower has seven fights (`data/hq_trainers.json`: six "Compact" names plus Relay Technician Sorrel) and the finale has two (Brann and Elara, `data/finale_trainers.json`). `data/route_trainers.json` (13 seats on Routes 1-3) and `data/late_route_trainers.json` (28 seats on Routes 4-8) have no Compact trainer (a grep for compact/haven/faction across both finds nothing). |

## 1. Where the Compact appears today

### On the critical path

| Window | Place | What exists | File and id |
|---|---|---|---|
| Pallet, gym 1 | `hometown`, `gym1_town` | Nothing, by design (`FACTION.md:204-205`) | none |
| gym 1-2 | `gym2_town` Viltri Quay, relief clerk (1601, 108, 2801) | The Compact is **named** for the first time, by a clerk (misty_003, misty_005). No member of the Compact is present | `data/dialogue.json:2461,2475` `dlg_main_misty_relief_clerk`. Required fact `data/quests.json:727`. The `misty_refugee_ledger` prop is unbuilt (`quests.json:1188-1193`) |
| gym 2-3 | `gym3_town` Highwire, signal clerk (1685, 175, 1413) | The clerk **does not name the Compact** (no match in `dlg_main_surge_signal_clerk`, `dialogue.json:2508-2664`). ARC's first obstruction, the record-recovery team (`ARC.md:328-331`), is **MISSING** (`CAMPAIGN_OUTLINE.md:88-90`) | `dlg_main_surge_signal_clerk` |
| gym 3-4 | `gym4_town` Greenhollow, archivist (4309, 111, 1551) | One mention in the archivist's lines. The town's name record says it "houses both native and Compact families" (`data/towns.json:745`), but no NPC carries this. Nia and Tomas are absent | `dialogue.json:2802` `dlg_main_erika_survey_archivist` |
| gym 4-5 | `gym5_town` Fenhide, tracker (4643, 118, 2449) | Hoopa is named on a control plate. **The Compact is not named** (no match in `dialogue.json:2835-2997`). Oren's traces are written only | `dlg_main_koga_marsh_tracker` |
| gym 5-6 | `gym6_town` Tilpey Cross, Sabrina witness (6191, 95, 3394) | One mention. Elara's representative and the waiting families are not built | `dialogue.json:3119` `dlg_main_sabrina_pattern` |
| gym 6-7 | `gym7_town` Cinderlee, crater analyst (6071, 108, 4992) | **The moral line is reported, not played.** `crater_operation_stopped` is set by the stand-in line `blaine_008` | `dialogue.json:3267` `dlg_main_blaine_crater_analyst`; `quests.json:773` |
| gym 7-8 | `gym8_town` Holdfast, watch officer (3643, 114, 6497) | One mention. Nia and the public split are not built | `dialogue.json:3457` `dlg_main_giovanni_watch`; `quests.json:783` |
| post-8 | Rift surveyor (3552, 112, 5334) | Two mentions; the rest of the path is direction-giving | `dialogue.json:3680,3729` `dlg_main_rift_surveyor` |
| post-8 | The Deep, the HQ, the cradle | The whole finale: HQ guards, Nia at the clinic, Brann (talks, then fights), Oren, Elara (talks, then fights), the binder's release; seven tower fights at levels 55-59 | `dialogue.json:12112-13509` (`dlg_main_finale_*`, `dlg_main_relic_*`); `data/hq_trainers.json`; `data/finale_trainers.json`; `data/hq_tower.json` |
| League | Steward | One mention | `dialogue.json:3785` |

### Off the path

- **Post Fourteen and Ash** (`data/southern_residents.json:124-130`, centre (7856, 4704), Long Isle, gated on
  `gym7_cleared`): an abandoned Compact field post with an anchor stump and a Houndoom left behind. There is no
  battle.
- **The Deep's city** (`data/deep_city.json`): a Compact city of rescued families. Its counter is story-gated and
  unbuilt (`data/markets.json:1121`).
- **Written, not built:** `SQ-G4-02` (a native family and a Compact family share a cooking pot), `SQ-G5-01` (anchor
  tracks), `SQ-G8-02` (names on the boats) (`SIDEQUESTS.md:135-260`); `EVT-G6-ASTER-LANTERN` and the Erika and Koga
  echoes in `events/MIDGAME_EVENT_BANK.md:135-610`; the Southern Rift's "Compact survey posts"
  (`world-building/SOUTHERN_RIFT.md:190`, build status not checked here).

### The gaps

- **No Compact battle before badge 8.** Across all eight route legs (16,601 blocks, the sum of the relayed leg
  lengths) and all eight gym towns, the player fights no one from the Compact.
- **No Compact character before the Deep.** Nia, Tomas, Oren, Brann, Elara and the Asters each have four or more
  written appearances (`FACTION.md:200-213`). None is built before the finale. The player first hears Elara named by
  Nia, in the Deep (`CAMPAIGN_OUTLINE.md:243`, X5).
- **Stretches with no Compact presence of any kind:** Route 1 and gym 1 (by design); **Route 2, Route 3, gym 3,
  Route 4 (3,453 blocks, the longest leg), Route 5, gym 5, Route 6, Route 7 and Route 8**; and Victory Road's southern
  approach, which has no trainers by design (`SOUTHERN_RIFT.md:186`). Gyms 2, 4, 6, 7 and 8 have one clerk's
  sentence each.
- **The required beats that ARC writes and nothing carries:** Highwire's records obstruction (`ARC.md:328-331`), the
  Craters climax (`ARC.md:521-526`, Codex C1), and Holdfast's public split (`FACTION.md:212`).

### Two findings for whoever owns the files

1. **`data/quests.json:1135-1143` is stale.** It says Brann is an "rctmod trainer, battles on sight" at the cradle
   (3363, 13, 3300). `data/finale_trainers.json:5` says he is ONE Cobblemon NPC in the HQ tower who talks and fights
   through `npc_battle`, and that his cradle seat is superseded. Elara's record (`quests.json:1147`) has the same
   fault. `quests.json` is story data that Codex corrects upstream (`FACTION.md:83`).
2. **`ARC.md:116-129` still carries the retired cradle coordinate (3297, 2603)**, which `FACTION.md:77-86`
   corrected. This is already known as X2 (`CAMPAIGN_OUTLINE.md:240`). It is repeated here because a builder working
   from ARC alone would seat a point on it.

## 2. The mechanisms (what each battle would run on)

Every point uses one of these. All of them sit on rungs 1-2 (Cobblemon native, and rctmod, a compatible addon) plus
datapack and functions. **No point needs a custom mod.**

| Id | Mechanism | Existing tool and pattern | Proven? | Fits |
|---|---|---|---|---|
| **M1** | rctmod seated trainer: `summon_persistent`, one win counted per player through the defeat advancement | `tools/route_trainers.py` (record and seat together, as in `data/hq_trainers.json`), placed by `tools/reapply.py` R17 | **VERIFIED in game** for route trainers and gyms (`docs/research/notes/rct-arena-capabilities.md:61-63`; EXP-027) | Route crews that can stand there at every stage. **Limits:** one shared entity, visible from day one to everyone. The hold-off cooldown refuses an unbeaten co-op partner while a beaten one is near (`route_trainers.py:656-667`). rctmod's level-cap refusal covers it for free |
| **M2** | A Cobblemon NPC that **talks, then fights**: dialogue entry rules gate the node on the player's own stage, and an `npc_battle` response starts `q.npc.start_battle` against the player who is talking | `tools/compile_dialogue.py:39-45, 274-290, 511-533`; teams-only file like `data/finale_trainers.json`; result read by a `battle_victory` callback (as `tools/hq_tower.py`); NPC placed over RCON (as `data/hq_tower.json` npcs) | `start_battle` **PASS in game** (arena probe, `arena-per-player-opponents.md:360`). The `npc_battle` dialogue route is "NOT yet run in game" (`compile_dialogue.py:43`). **Singles only:** the compiler refuses any other format (`:278`). Each fight needs an `over_cap_node` | Named characters and fights gated on story stage. **The default for this pass** |
| **M3** | A Cobblemon NPC **spawned per player** in front of them, battle started by command, result from the callback | `tools/arena_runtime.py:17-22, 70-74` (spawn with `spawnnpcat`, start, read the callback, sweep) | Spawn, start, win, loss, re-roll and removal **PASS in game, one player** (`arena-per-player-opponents.md:354-371`). Two players at once: not run. **Triggering a spawn from a story zone is new** | Squads that should exist only for the player at that stage (a raid, a gauntlet). Unproven as a story trigger: experiment X2 |
| **M4** | Wild Pokémon a player owns, placed by a scene: "distressed by the exchange", fought as ordinary wild battles | `data/scenes.json` actors and functions (`tools/scenes_pack.py`); macro `spawnpokemonat` (`.claude/rules/datapacks.md`, EXP-046) | Macro spawn VERIFIED (EXP-046). Scene actors **partial** (EXP-034 is "in progress", `experiments/EXP-034-scene-runtime/README.md:133-140`) | Fights to defend a camp or a family |
| M5 | The dungeon engine: clock, gauntlet rooms, stands | `data/dungeons.json`, `tools/dungeon.py` | **Not run on a server** (EXP-084 NOT_EXECUTED, `dungeons.json:4`) | Not for the main story. A later optional Compact anchor dungeon at most (O9) |

**Doubles and multi battles are unproven everywhere.** rctmod documents `battleFormat` DOUBLES and MULTI
(`rct-arena-capabilities.md:96`), and `start_battle` accepts `'doubles'` in source (`arena-per-player-opponents.md:134`,
not run). Neither has been run in game (`GIOVANNI_FORMAT.md:5`, `docs/STATE.md:347`). Every "double battle" below is
therefore written with a **fallback of two singles, back to back, with no heal between them**. The doubles version is
built only if experiment X3 passes.

**A "battle on a moving ferry" does not exist to build.** The ferry is a fade and a teleport (`tools/ferries.py:2-21`).
CP-10 puts its fight at the dock instead.

**Gating rule for every point:** entry rules read `quest.main_worldshift_reveal.stage` with `progression_in` (the
pattern of `dialogue.json:2362-2397`), so the badge carry (`CAMPAIGN_OUTLINE.md:22`) opens each point to a player who
skipped a teller. **No point gates a badge** unless the owner says so (O3). Every point is its own optional
`evt_compact_<slug>` quest, shaped like `evt_viltri_north_bank` (`quests.json:4398-4472`): its fields are declared in
`data/progression.json`, and a win sets `quest.<evt>.<trainer>_defeated`. Two points are proposed as main-quest beats
(CP-04, CP-12). Each is marked.

**The common threads** (so the faction reads as people, not a sequence of grunts):
- **The Asters** appear at CP-01, CP-06, CP-12 and CP-14. These are exactly FACTION.md's four places (`:172-173`):
  Lake Viltri, Peak Pond, the Craters and Giovanni's town.
- **Lieutenant Varga is the scaling rematch.** She already exists as the HQ's last tower fight (`hq_trainers.json`
  `hq_tower_trainer_07`, Drapion, Excadrill, Gigalith and Crobat at 58-59; her line at `:642` is "Say to her what you
  said to my team"). She meets the player four times before the HQ: CP-04, CP-07, CP-11 and CP-13. **Her team is the
  same four lines each time, evolving and growing,** so by the tower the player knows every member. rctmod and
  Cobblemon teams are static (`rct-arena-capabilities.md:39-40, 96-97`), so each appearance is its own trainer id:
  `compact_varga_1` to `_4`.
- **Compact teams carry species the region does not have wild.** This is the visible sign that they came from
  elsewhere. `ENCOUNTER_GAPS.md:5-15` lists 570 species with no authored home. The balance designer draws from that
  list, excluding legendaries and anything reserved. Varga's lines already fit: Excadrill is on it (`:11`).

## 3. The new story points

Each point lists: where (an existing id), when (the badge window), what happens, the ARC or FACTION beat it serves,
how it is triggered, and the battle. "Band" is the planned level range, held under the next leader's ace (relayed
curve). The order runs along the critical path.

### CP-01 The Courier's Spar: `route_02_brock_to_misty`, the last stretch before Lake Viltri

- **When:** after `gym1_cleared`, at stage `brock_account_heard` or later.
- **What:** A Compact relief cart has thrown a wheel on the road to the lake. It carries medicine and household
  bundles, and the Asters (Mila, Dev and Jo) walk beside it. The courier is cheerful, tired and proud of the run. **This
  is the player's first sight of the Compact as people.** Nothing about their method is said.
- **Serves:** ARC Settlement 3, the sympathy beat (`ARC.md:268-298`); rule 3; FACTION "The sympathy beat"
  (`:215-225`); the Asters at Lake Viltri.
- **Battle:** **a friendly spar.** The courier offers a practice match "to see what this world's Pokémon are like".
  2 Pokémon, band 20-23. Theme: hardy haulers from somewhere else, drawn from the homeless-species list. The win gives a
  small medicine gift. A loss has no sting beyond the normal blackout (O6).
- **Mechanism:** M2. A Cobblemon NPC and a seat in `data/npc_seats.json`. The cart and the bundles are props
  (`data/scenes.json`). Quest `evt_compact_courier_spar`.
- **Size:** S.

### CP-02 Landing Night: `gym2_town` Viltri Quay, the shore

- **When:** at stage `brock_account_heard` (before Misty) and after.
- **What:** Nia Calder's field clinic, Tomas Rill with his survey cases, crews unloading boats. This puts in person
  what the relief clerk only reports (Codex C3). Maren helps unload (`ARC.md:107`). Tomas says he recognises Pallet as
  "a large, clean transfer" without admitting the Compact caused it.
- **Serves:** ARC Settlement 3; FACTION `gym2_town` (`:206`); rule 3.
- **Battle: none, deliberately.** The sympathy beat stays a place where nobody fights. (The fight nearby is CP-01.)
- **Mechanism:** M2 NPCs with conversations only, plus scene props. Quest `evt_compact_landing`.
- **Size:** S.

### CP-03 The Relay on the Climb: `route_03_misty_to_surge`, Foothill Woods to Mt Clay

- **When:** after `gym2_cleared`.
- **What:** Two Compact technicians tend a small relay mast beside the trail: an end rod on tinted glass, the Deep's
  light language (`SOUTHERN_RIFT.md:190`). They will not say what it relays and ask the player to keep off the
  equipment. **This is the first secret**, not yet an obstruction.
- **Serves:** ARC Settlement 4 setup. It is an echo, never the source: Surge's town still supplies "steered"
  (`ARC.md:323-327`).
- **Battle:** **"Keep off the mast", a double battle against the two technicians.** Band 25-28, Electric and Steel
  gadgets. **Fallback (until X3): two singles back to back, no heal.**
- **Mechanism:** M1. These technicians can stand there at every stage, so a seated rctmod pair (`route_trainers.py`,
  eye contact on the first) works. A seat file shaped like `data/hq_trainers.json`. Quest `evt_compact_relay`.
- **Size:** S.

### CP-04 The Records Run: `gym3_town` Highwire, Surge's records office and the array path

- **When:** at stage `misty_reveal_complete` (after badge 2, before Surge).
- **What:** A record-recovery team is carrying Surge's pulse logs out of town. The player catches them in a run
  through three rooms or streets. Each courier holds part of the file, and the player beats each one to recover it.
  When the team is exposed it withdraws without harming anyone (`ARC.md:328-331`). Its leader is **Varga, here a
  sergeant**. She meets the player for the first time and leaves angry.
- **Serves:** ARC Settlement 4, the first direct obstruction. Today it is MISSING (`CAMPAIGN_OUTLINE.md:88-90`).
  FACTION `gym3_town` (`:207`).
- **Battle:** **a grunt gauntlet: three couriers back to back with no heal, then Varga.** The fun gimmick: the
  raiders came prepared for an Electric town. Couriers 1-3 each lead with a Ground type, so a player who brought only
  Electric types to beat Surge has to think. Couriers: 2 Pokémon each, band 26-28. **Varga (`compact_varga_1`):**
  Skorupi, Drilbur, Roggenrola and Zubat, 3-4 of them at 27-29.
- **Mechanism:** **M3 if X2 passes** (the squad exists only for a player at this stage, which a raid needs).
  **Fallback M2:** four Cobblemon NPCs, each fight gated on the previous one's defeated field (the HQ tower's chain).
  Recovering the file sets `quest.evt_compact_records_run.records_recovered`. Proposed as a **main-quest beat** if the
  owner wants ARC's order, "Surge's battle comes after the player secures the critical evidence" (O3).
- **Size:** M.

### CP-05 Survey of an Empty Cirque: `merian_hut`, Merian Hut (2813, 1102), on `route_04_surge_to_erika`

- **When:** after `gym3_cleared`. It sits about four tenths of the way along the longest leg (`towns.json:1689`).
- **What:** Tomas's destination team has staked the Merian cirque as "unoccupied volume". The hut's keeper says
  herders summer here, and children were born here. A native ranger and the Compact surveyor have laid incompatible
  maps (`MIDGAME_EVENT_BANK.md:135`). **The player chooses whom to fight.** Siding with the ranger means fighting the
  surveyor so the stakes come up. Siding with Tomas means fighting the ranger so the survey can finish. Both routes
  end with the same fact: the survey missed people. Only the tone differs.
- **Serves:** ARC Settlement 5 setup ("every transfer exchanges occupied volume", `ARC.md:389-393`). FACTION Tomas
  ("trusts better maps more than speeches", `:144-153`).
- **Battle:** **a choice of opponent.** Surveyor: 3 Pokémon, band 31-33, Psychic and Steel instruments (sensing
  Pokémon). Ranger: 3, band 31-33, Rock and Ice mountain natives. The choice is a quest field (`sided_with`) that a
  later line can read (CP-12).
- **Mechanism:** M2. Two NPCs, and one choice in a conversation that sets the field. Each opponent's `npc_battle` is
  offered only on its side. Quest `evt_compact_cirque_survey`.
- **Size:** M.

### CP-06 The Pause Vote: `gym4_town` Greenhollow, the green

- **When:** at stage `surge_reveal_complete` and after.
- **What:** The Compact's internal divide, held in public. Nia argues for a pause until a destination can be proved
  empty. A guard sergeant from Brann's crews argues that waiting abandons the living. The Asters are among the families
  housed here. Erika makes the player deal with both sides as residents (`ARC.md:375`).
- **Serves:** ARC Settlement 5 (the internal divide); FACTION `gym4_town` (`:208`); the Asters at Peak Pond.
- **Battle:** **the sergeant tests the player.** He wants to know whether the stranger asking questions is a threat to
  the families. 3 Pokémon, band 32-34: a small version of Brann's Steel and Fighting wall, foreshadowing the finale
  (`finale_trainers.json:11`). The win earns his grudging respect, not a defeat of the Compact.
- **Mechanism:** M2. Quest `evt_compact_pause_vote`.
- **Size:** S.

### CP-07 The Anchor Pull: `route_05_erika_to_koga`, the wet ground toward `glacial_tear`

- **When:** after `gym4_cleared`.
- **What:** A salvage crew is winching an abandoned field anchor out of the marsh before Koga's trackers can see it.
  The anchor's destination marks have drifted (`quests.json:1213-1217`, the plate Koga's tracker reads). **Oren
  Pell's field notebook is in the crew's crate:** he admits Hoopa's condition is worsening (`FACTION.md:120-123`).
  Varga commands the crew.
- **Serves:** ARC Settlement 6 ("each forced use makes the next less stable", `ARC.md:428-430`); FACTION
  `gym5_town` (Oren's traces); `SQ-G5-01`. An echo: Koga's town remains the source.
- **Battle:** **a raid on a camp: two crew, then Varga, before the anchor is lifted.** Phase 1 is untimed: three fights
  in a row, no heal, and the notebook is the prize. **The timed version** (the winch finishes in N minutes and the
  anchor is gone) is built only if X4 passes. Crew: 2-3 Pokémon each, band 36-38. **`compact_varga_2`:** Skorupi,
  Excadrill, Boldore, Golbat and one more, band 37-39.
- **Mechanism:** M1 for the two crew (they can stand by the crane at any stage). Varga is M2 (her fight reads the
  stage). Quest `evt_compact_anchor_pull`.
- **Size:** M (L with the timer).

### CP-08 Shadows in the Reeds: `gym5_town` Fenhide and `marshy_marsh`

- **When:** at stage `erika_reveal_complete` and after.
- **What:** Koga's trackers and the player hunt a Compact scout cell hidden in the marsh: three scouts in reed blinds.
  Each scout found has been watching the town's movements.
- **Serves:** ARC Settlement 6 ("Koga tracks covert movement", `ARC.md:152`, `:423-426`).
- **Battle:** **hide and seek, then a fight per scout found.** Three scouts, 2 Pokémon each, band 37-39. Theme:
  ambush and stealth (Dark and Poison, illusion users if the species allow). Finding all three gives Koga's tracker
  gear.
- **Mechanism:** the existing hide-and-seek pattern (`evt_hide_and_seek`, `quests.json:8896`;
  `dlg_hide_and_seek`, `dialogue.json:17095`) plus M2 per scout. Quest `evt_compact_reed_scouts`.
- **Size:** M.

### CP-09 The Waiting Camp: `route_06_koga_to_sabrina`, Marsh Creek to the north shore

- **When:** after `gym5_cleared`.
- **What:** A large camp of families from a source world is waiting for the next transfer, the "largest remaining
  community" made visible (`ARC.md:473-476`). Exchange effects have frightened the local Pokémon (`ARC.md:425`), and
  some wander into the camp at dusk.
- **Serves:** ARC Settlement 7 (the strongest moral case); FACTION `gym6_town` (the waiting families); rule 4.
- **Battle:** **defend the families.** Three distressed wild Pokémon come at the camp's edge. The player fights them
  as wild battles while the camp's guards hold the line. Band 41-43, species native to `marsh_creek`. Afterwards the
  camp's guard thanks the player. A Compact family the player helped will be at the Craters (CP-12).
- **Mechanism:** M4. Scene actors the player owns, placed by a `data/scenes.json` zone at dusk. Partly proven (EXP-034).
  Quest `evt_compact_waiting_camp`.
- **Size:** M.

### CP-10 The Requisitioned Boat: `gym6_town` Tilpey Cross, the lake dock (`data/ferries.json` `tilpey_sabrina_dock`)

- **When:** at stage `sabrina_reveal_complete` (after badge 6).
- **What:** Loyalists are loading equipment onto the lake boats bound south toward the Craters. They tell the
  boatman his boat is needed for a rescue. He cannot refuse them and does not want to.
- **Serves:** ARC Settlement 7's last fact: "the faction is preparing that transfer at a major energy source"
  (`ARC.md:492`).
- **Battle:** **a boarding officer at the gangplank.** 3 Pokémon, band 44-46, Water and Flying, with crew who know
  boats. Winning frees the boat for the day. **The ferry is never blocked.** It is the gate for players without a
  water mount (`ferries.py:5-6`), so the officer stands beside it, not in its way.
- **Mechanism:** M2, at the dock. The ferryman's own dialogue is generated by `tools/ferries.py` and is not touched.
  Quest `evt_compact_requisition`.
- **Size:** S.

### CP-11 The Bridge Checkpoint: `route_07_sabrina_to_blaine`, the outflow bridge at (6632, 3904)

- **When:** after `gym6_cleared`.
- **What:** Brann's guards hold the only crossing south (`ARC.md:483-484`) to keep locals away from the Craters.
  Brann is seen but not fought: he watches from the far end and lets the result stand. Varga leads the checkpoint. The
  Bridgekeep keepers (`gorge_hamlet`, `SQ-G6-02`) are angry about it.
- **Serves:** the escalation before the line. This is open force for the first time, but no occupied target has been
  chosen yet (rule 5).
- **Battle:** **Varga's pair, a double battle.** `compact_varga_3` together with a guard, Varga's team at 45-48:
  Drapion has evolved now, alongside Excadrill and Boldore. **Fallback: the guard, then Varga, as singles with no heal
  between.**
- **Mechanism:** M2. **This is the only crossing**, so whether the fight is unavoidable is the owner's call (O2). The
  recommendation is that the guards step aside after one attempt, win or lose, so a player is never stuck.
  Quest `evt_compact_bridge`.
- **Size:** M.

### CP-12 The Crater Activation: `gym7_town` Cinderlee and the `craters` rim

- **When:** at stage `sabrina_reveal_complete` (after badge 6, before Blaine).
- **What:** The moral line, played rather than reported (Codex C1, X6). It happens in this order:
  1. Tomas confirms the target is occupied. If the player sided with the ranger at CP-05, he says so.
  2. Oren hands over the calibration record.
  3. Elara is seen giving the order. **This is the player's first sight of the villain** (O5).
  4. The player shuts three anchors. Each is guarded, and each shutdown is a clicked prop after its guard falls.
  5. A Field Commander fights at the console.
  The Asters are among the families who were waiting for this transfer, so stopping it leaves them stranded
  (`ARC.md:521-526`).
- **Serves:** ARC Settlement 8 and FACTION "The point where the method becomes indefensible" (`:227-237`). **It sets
  `crater_operation_stopped`, replacing the stand-in setter at `blaine_008`** (`quests.json:773`).
- **Battle:** **shut down the activation: three anchor guards (any order), then the Field Commander.** Guards: 3
  Pokémon each, band 47-49. Fire-proofed crews (Water and Ground) who can work on the crater. **Commander:** 5 Pokémon,
  band 48-50, built around the machine (Steel and Psychic, Elara's own theme, `finale_trainers.json:11`, in a lesser
  version).
- **Mechanism:** **M3 if X2 passes** (the activation exists for the player at this stage, and a player past it must
  not see it again). **Fallback M2.** The anchors are `data/scenes.json` props. The Commander's win runs the
  transition that sets `crater_operation_stopped`. Proposed as a **main-quest beat** (O3).
- **Size:** L.

### CP-13 The Rearguard: `tableland_stop` Redbrow (4876, 5729), on `route_08_blaine_to_giovanni`

- **When:** after `gym7_cleared`.
- **What:** Loyalists are retreating west toward the Rift. A small group of dissenters, led by a Nia-aligned medic,
  is trying to slip away with stores and records. Varga's rearguard means to stop them. **Rule 4:** the dissenters are
  families and medics, not soldiers.
- **Serves:** ARC Settlement 9 setup ("withdrawing toward the Rift's southern approach", `ARC.md:529-531`); the start
  of the public split.
- **Battle:** **`compact_varga_4`, a rematch that scales.** 5 Pokémon, band 51-53: Drapion, Excadrill, Boldore,
  Crobat and one new member. This is the last time before the tower, where she has the final four at 58-59. Winning
  lets the dissenters go. They reappear at Holdfast (CP-14) and in the Deep.
- **Mechanism:** M2. Quest `evt_compact_rearguard`.
- **Size:** S.

### CP-14 The Split Goes Public: `gym8_town` Holdfast, the southern watch

- **When:** at stage `blaine_reveal_complete` and after.
- **What:** Nia speaks for the dissenters in public (`FACTION.md:212`). The Asters are here (`:172`). A loyalist
  detail arrives to take back the dissenters' route packet, the `giovanni_dissenter_route_packet` evidence
  (`quests.json:1236-1241`). Giovanni's watch and the player stand with the dissenters.
- **Serves:** ARC Settlement 9 (the break goes public); FACTION `gym8_town`; Codex C3 "Nia at Holdfast".
- **Battle:** **defend the watch: the player and a watch officer against two loyalists, a multi battle.** Band 51-54.
  **Fallback: two singles, no heal between, with the watch officer's line between them.** Winning keeps the packet,
  which the Rift surveyor's lines already assume.
- **Mechanism:** M2 (the multi battle needs X3). Quest `evt_compact_split`.
- **Size:** M.

### The coverage this gives

Every leg and gym town from Route 2 to Holdfast gets one or two Compact points. Route 4, the longest leg, gets CP-05
at its 0.42 mark. That makes **11 new battle points** (CP-02 has no fight; CP-09's fights are wild). By the badge
windows: 1-2 (CP-01, CP-02), 2-3 (CP-03, CP-04), 3-4 (CP-05, CP-06), 4-5 (CP-07, CP-08), 5-6 (CP-09), 6-7 (CP-10,
CP-11, CP-12), 7-8 (CP-13, CP-14). The only stretch left out is Victory Road's approach (O9).

**New trainer records (planned):** CP-01 1, CP-03 2, CP-04 4, CP-05 2, CP-06 1, CP-07 3, CP-08 3, CP-10 1, CP-11 2,
CP-12 4, CP-13 1, CP-14 2. That is **26 trainers, 4 of them Varga**. CP-09 adds 3 wild actors. Every new id must pass
`python tools/id_authorship.py` against `data/trainers.json` before it merges (CLAUDE.md "A clean merge is not a clean
union").

## 4. Build order

Sizes: **S** is about one builder for half a session, **M** one session, **L** more than one. Builders work in
isolation worktrees. Integration (prepare, the full suite, staging) stays in the main session.

**Wave 0: settle the unknowns first. These run in parallel and gate nothing in wave 1 except where noted.**

| Step | Agent | What | Size |
|---|---|---|---|
| X1 | main session (staging) | **`npc_battle` in game:** talk to Brann in the HQ (`hq_tower.json` storey hq_s1), start his fight, win, and check that `brann_defeated` is set; then lose once and check the over-cap line. Every M2 point rests on this | S |
| X2 | `minecraft-systems-dev`, then the main session | **A story squad spawned per player:** a `scenes.json` zone, gated on stage, runs the arena's `spawnnpcat` → `start_battle` → `battle_victory` chain, and the next leg spawns on a win. Two accounts, one at the stage and one not. Gates M3 for CP-04 and CP-12 | M |
| X3 | `cobblemon-researcher` (source read), then the main session | **Doubles and multi:** `start_battle(q.player, 'doubles')` on a Cobblemon NPC with two Pokémon; rctmod `GEN_9_DOUBLES`; a two-player multi. Gates the doubles versions of CP-03, CP-11 and CP-14 | M |
| X4 | `minecraft-systems-dev` | **A story timer:** a per-player scoreboard countdown with a bossbar that ends a raid (the dungeon engine's clock, `dungeons.json:46-57`, has not been run). Gates CP-07's timed version only | S |

**Wave 1: content, in parallel. Each row is one builder unit.**

| Unit | Agent | Points | Size |
|---|---|---|---|
| W1-text | Codex (story text owner) | Lines for CP-01 to CP-14, given what each line must do (section 3) | M |
| W1-teams | `trainer-balance-designer` | 26 teams in the bands above, the Varga ladder (4 + the existing tower record), the homeless-species signature | M |
| W1-seats | `world-content-dev` | Seats and props measured on `tools/ground.py` for every point: the cart, the mast, the anchor, the camp, the three crater anchors, the reed blinds. Data only | M |
| W1-early | `datapack-content-dev` | CP-01, CP-02, CP-03: quest records, progression fields, conversations, the M1 seat file and the M2 teams file (shaped like `hq_trainers.json` and `finale_trainers.json`) | M |
| W1-mid | `datapack-content-dev` | CP-05, CP-06, CP-08, CP-10, CP-13: the M2 points | M |
| W1-raids | `minecraft-systems-dev` (after X2) | CP-04, CP-07, CP-12: the gauntlets, the anchor props, the setter for `crater_operation_stopped` | L |
| W1-camp | `minecraft-systems-dev` | CP-09: the scene actors and the dusk zone | M |
| W1-tests | `test-author` | See the list below | M |
| W1-coop | `datapack-content-dev` (after X3) | CP-11 and CP-14 in doubles and multi | S |

**What W1-tests should check** (a different agent from the builders, `.claude/rules/testing.md`):
- No Compact battle opens before `brock_account_heard`.
- No point gates a badge.
- Every `npc_battle` has an `over_cap_node`.
- Every team's top level is under the next leader's ace.
- Varga's four ids rise in level, and her last is under the tower's 58.
- Each id has exactly one author (`id_authorship`).

**Priority if not all are built:** CP-04, CP-12 and CP-14 first. They carry ARC's three missing required beats. Then
CP-01 and CP-06, which make the Asters and the divide visible. Then the rest.

## 5. Questions for the owner

1. **O1. "Evil faction".** By your 2026-09-22 rule the Compact is not evil. Do you confirm that the fights before the
   Craters come from secrecy, guarding families and disagreement, and that only the loyalists after the line are open
   opponents? Or do you want them harder-edged earlier? That would mean changing `ARC.md` rules 3 and 5.
2. **O2. Unavoidable fights on the critical path.** May a Compact battle stand on the only crossing (CP-11, the
   outflow bridge) or in the way through Highwire (CP-04)? The recommendation is that the guards step aside after one
   attempt, so no player is ever stuck.
3. **O3. Main-quest beats.** Should CP-04 (the records) come before Surge, as ARC orders it? Should CP-12 become the
   setter of `crater_operation_stopped`, replacing the stand-in line `blaine_008`? Both stay optional unless you say so.
4. **O4. Varga as the recurring rival.** Reusing the HQ's existing lieutenant gives her tower line a history. Is that
   wanted, or should the rival be a new character and Varga stay as she is?
5. **O5. Elara before the Deep.** Today the player never sees her until the HQ. Should she appear in person at the
   Craters (CP-12), or only as a voice or an order on the console?
6. **O6. Losing a Compact fight.** A loss runs the normal blackout to the player's checkpoint (the arena probe's loss
   sent its player home, `arena-per-player-opponents.md:365`). Keep that, or give story fights a softer loss where the
   crew withdraws anyway?
7. **O7. The species signature.** Should Compact teams use species the region has no wild home for
   (`ENCOUNTER_GAPS.md`)? The player would then meet some species only in Compact hands.
8. **O8. Doubles and multi.** Are they worth an experiment now (X3)? Co-op multi battles, two of you against two
   loyalists, suit a group of friends, but they are unproven.
9. **O9. Victory Road's approach** has "no trainers" by design (`SOUTHERN_RIFT.md:186`). Keep it that way, or add one
   loyalist patrol? Also: is there an optional Compact anchor dungeon on the dungeon engine, later?
10. **O10. Who writes the lines:** Codex, or stand-ins marked `placeholder` (as in the finale) so builders are not
    blocked?
