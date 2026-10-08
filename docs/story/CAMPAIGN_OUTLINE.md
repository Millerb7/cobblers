# Campaign outline: the chapters, the world's story, and Challenge mode

**Status: design (unit A9, 2026-10-07), for the owner to read before wave B.** This document outlines the story and
lists its gaps. It writes no story text. The lines belong to Codex (`docs/HANDOVER_CODEX.md`), and where this outline
says a scene is missing it describes what the scene must do, not what anyone says in it.

**How to read the status words.**
- **BUILT** means it is in `data/`, a generator emits it, and `docs/STATE.md` says it is applied to staging. **Nobody
  has talked to any of the mainline in game** (`docs/STATE.md:360`). So BUILT never means "seen working".
- **WRITTEN** means the story documents describe it, but no NPC, dialogue or object carries it.
- **MISSING** means no document or file covers it.

**Numbers.** Each number is either *measured* (how is given) or *relayed* (the source is given). Leg lengths are
relayed from `docs/HANDOVER_CODEX.md:31-38` (2026-09-16). Leader ace levels are relayed from `docs/STATE.md:327`
(curve 20/25/30/35/40/45/50/55). Town names and centres were read from `data/towns.json`.

## 0. Premises checked

| Premise in the brief | What the files say |
|---|---|
| The mainline is ten ordered beats in one per-player quest | **True.** `data/quests.json:705-795` has ten beats from `pallet` to `league`. Beat 10 now holds the whole finale: six more stages (`deep_handoff_received`, `hq_crossed`, `anchor_shutdown`, `cradle_open`, `rift_released`, `league_recognized`; `docs/world-building/RIFT_FINALE_CHAIN.md:16-39`). The quest's `dialogue_ids` (`quests.json:684-704`) list 19 conversations. `dialogue.json` has 21 `dlg_main_*` conversations (counted with grep). The two not listed are `dlg_main_pallet_lab_starter` and `dlg_main_relic_hall_release`, the binder who sets `rift_crisis_resolved`. |
| "Challenge mode skips most of the story" | **No mechanism in the repo does this.** Challenge is Full-Team trainer rules, chosen at Oak, and nothing else (`docs/mechanics/OAK_AND_CHALLENGE.md:32-60`). What actually makes the story skippable is the **badge carry**, which works the same in **both modes**. Each badge lifts the player's reveal stage (`data/progression.json:84-90` and the same block for every gym), and each teller's locked line accepts "the badge OR the previous teller's account" (review N8). So the story can already be skipped up to the HQ door, in both modes. Section 3 sets out the two readings of the owner's sentence (O1). |
| `crater_operation_stopped` has no setter | **True.** The id appears only in documents and as `missing_story_flag` in `quests.json:772` (searched with grep). Nothing grants it. The Kyogre design depends on it (`docs/world-building/KYOGRE_CAVE.md:88`). |
| A badgeless player can walk the tellers to the finale's door | **True as written** (N8, `docs/OVERNIGHT_REVIEW_2026-10-06.md:15`). Unit A3 is building the gate in parallel, and this outline assumes nothing about its shape. One fact matters here: the cradle itself is already badge-gated. The relic knock box needs all eight gym flags (`RIFT_FINALE_CHAIN.md:33`). The gap is the HQ, Nia, and the two fights before that point. |
| The villain is original; Giovanni is gym 8 and a civil defender | **True** (`docs/STATE.md:167`; `ARC.md:138-142,155-156`). The villain is Director Elara Venn of the Haven Compact (`FACTION.md:33-39`). |

---

## 1. The campaign, chapter by chapter

The critical path is ten places: `hometown` -> `gym1_town` ... `gym8_town` -> `league` (`ARC.md:13-17`). Each
chapter below names the teller who carries its beat. A teller is a Cobblemon NPC at a seat in `data/npc_seats.json`,
with an evidence display beside them (one prop and one sign, `data/reveal_evidence.json`).

### Chapter 0: Pallet and Oak

- **Where:** Pallet Town, `hometown`, centre (1462, 5293). The player spawns at (1461, 118, 5306) and Oak stands at
  (1493, 118, 5317) (`OAK_AND_CHALLENGE.md:15`).
- **What the player learns:** Pallet survived, but in the wrong geography, with localized damage at its edge
  (`quests.json:709`). By design the town explains nothing; the premise is the mismatch the player sees (`ARC.md:58-59`).
- **Who carries it:** Oak, then Mina at the crossroads sign (1454, 118, 5287), then back to Oak, then Maren on the
  lab lane (1472, 117, 5321) (`npc_seats.json:191-251`).
- **Built:**
  - The lab scene: a hint in the hotbar, the five starters on display, Oak's greeting, Cobblemon's chooser opened by
    Oak, and the mode choice in Oak's words (`OAK_AND_CHALLENGE.md:11-60`). Its first in-game test is the owner's next
    join (`docs/HANDOVER_SESSION.md:50-53`).
  - The four conversations and the crushed-house side event (`evt_pallet_crushed_house`).
- **Written only:**
  - The exchange seam at the north exit, which needs a reserved corridor 32 x 12 (relayed,
    `MAINLINE_REVEAL_IMPLEMENTATION.md:28-35`). `reveal_evidence.json:5` treats the seam as terrain that already
    exists. Whether the join actually reads as abrupt has not been checked.
  - Maren's "coastal lead" toward Relic Island (`ARC.md:105`).
- **Missing:** a waypoint to gym 1. `data/progression.json:3458` says "Gym 1's is Oak's to offer at the start (not
  built)". Today the only cues are Oak's remembered directions and the Route 1 signposts.

### Chapter 1: Stoneford (Brock), ace 20

- **Where:** `gym1_town`, centre (1743, 3628), on the Viltri Plateau. Route 1 is 1,978 blocks (relayed) and is pinned
  through the maze forest.
- **What the player learns:** Pallet replaced an occupied native settlement (`quests.json:718`).
- **Who carries it:** Brock himself, as a witness NPC on the forecourt at (1832, 142, 3661). The leader Brock is a
  separate entity on the gallery spawner at (1832, 155, 3696) (`npc_seats.json:253-268`). The display is the
  **BOUNDARY CORE** (tuff under coarse dirt).
- **Built:** the witness, the display, and the juniors (2 per gym today; the owner wants 3 or more, unit A2).
- **Written only:** the public competence test before Brock will speak (`ARC.md:225-228`). Today the badge or Pallet's
  account unlocks him.
- **Note for the owner:** handover item 2b-7, "the Brock OUTSIDE gym 1 is not explained", is very probably this
  witness Brock. The seat puts him 35 blocks south of the spawner and outside the hall, by design (measured:
  3696 - 3661 on z). That is a hypothesis. To check it, click him and see whether `dlg_main_brock_witness` opens.

### Chapter 2: Viltri Quay (Misty), ace 25

- **Where:** `gym2_town`, centre (1605, 2801). Route 2 is 944 blocks (relayed).
- **What the player learns:** the Haven Compact rescues people from collapsing worlds, and Pallet carries the same
  exchange signature (`quests.json:727`). This is the **sympathy beat** (`ARC.md:298`).
- **Who carries it:** a relief clerk at (1601, 108, 2801). The display is the RELIEF LEDGER barrel.
- **Written only:** first contact with the Compact in person. Field crews, the medic Nia Calder, the surveyor Tomas
  Rill and the Aster family should all be here (`FACTION.md:206,215-225`). **None of them is built here.** The player
  hears about rescues from a clerk and meets no one who was rescued.

### Chapter 3: Highwire (Surge), ace 30

- **Where:** `gym3_town`, a shelf at (1688, 1410) at y174. Route 3 is 2,120 blocks and climbs 81 (relayed). The signal
  array stands at (1928, 284, 1248).
- **What the player learns:** exchange pulses carry corrections, so someone triggers and steers them
  (`quests.json:736`).
- **Who carries it:** a signal clerk at (1685, 175, 1413). The display is the SIGNAL RECORD mast.
- **Written only:**
  - The **first direct obstruction**: a Compact team tries to take Surge's records and withdraws when exposed
    (`ARC.md:328-331`). No event, trainer or NPC exists for it.
  - Maren's second signal trace (`ARC.md:108`).
- **Optional:** the Scar at (2110, 950), the summit the city was taken from. It is BUILT as ruins: 33 houses and four
  towers (`HANDOVER_CODEX.md:330-349`). Its story is still Codex's question (C6).

### Chapter 4: Greenhollow (Erika), ace 35

- **Where:** `gym4_town`, centre (4309, 1555). Route 4 is 3,453 blocks (relayed), the longest gym leg.
- **What the player learns:** every transfer exchanges occupied volume, and an earlier settled summit was exchanged
  too (`quests.json:745`). The dry channel runs uphill from (3786, 1182) to (3376, 921) (`ARC.md:376-380`).
- **Who carries it:** a survey archivist at (4309, 111, 1551). The display is the SURVEY LEDGER lectern.
- **Written only:**
  - The Compact's internal divide in person, with Nia and Tomas (`FACTION.md:208`).
  - Erika walking the player to the channel (`ARC.md:375-376`).
- **Optional:** the Displaced City at (2969, 1710). The summit's streets were exchanged into a cavern (`SIDEQUESTS.md:368-378`).

### Chapter 5: Fenhide (Koga), ace 40

- **Where:** `gym5_town`, centre (4646, 2446). Route 5 is 1,051 blocks (relayed).
- **What the player learns:** repeated forced use destabilises Hoopa and widens the damage. Hoopa is named here for the
  first time, on a recovered control plate (`quests.json:754`; `dialogue.json:2858`).
- **Who carries it:** a marsh tracker at (4643, 118, 2449). The display is the RECOVERED ANCHOR lodestone.
- **Written only:** the engineer Oren Pell's traces (`FACTION.md:209`).
- **Missing:** anything pointing to the Mega field after Koga (U47, `docs/UNFINISHED_SWEEP_2026-10-06.md:165`).

### Chapter 6: Tilpey Cross (Sabrina), ace 45

- **Where:** `gym6_town`, centre (6196, 3398). Route 6 is 1,944 blocks (relayed).
- **What the player learns:** Hoopa is being compelled, and a mass rescue is imminent (`quests.json:763`). This is the
  Compact's strongest moral case (`ARC.md:473-480`).
- **Who carries it:** Sabrina herself, as the witness to Hoopa's fragments, at (6191, 95, 3394). The display is the
  CONVERGENCE cartography table. Her battle lines are not ours.
- **Written only:** Elara's representative and the waiting families (`FACTION.md:210`).

### Chapter 7: Cinderlee (Blaine), ace 50

- **Where:** `gym7_town`, centre (6074, 4995), on the Crater rim. Route 7 is 2,061 blocks (relayed) and crosses the
  outflow bridge at (6632, 3904).
- **What the player learns:** the Compact's leadership knowingly chose an occupied destination and proceeded anyway
  (`quests.json:773`). **This is the moral line** (`ARC.md:516-519`; `FACTION.md:227-237`).
- **Who carries it:** a crater analyst at (6071, 108, 4992). The display is the DESTINATION lectern.
- **Missing: the climax itself.** The player is supposed to stop the crater activation with Blaine, Elara, Oren,
  Tomas, Brann and the refugees present (`ARC.md:521-526`). Instead the analyst *reports* that it was stopped
  (`dialogue.json:3186-3193`), and line `blaine_008` (`dialogue.json:3200`) says out loud that "shutting down the
  operation needs its own authoritative record". That line is a design note spoken in game. With no event,
  `crater_operation_stopped` has no setter (U58), and the Kyogre "two sleepers" beat waits on that flag.

### Chapter 8: Holdfast (Giovanni), ace 55

- **Where:** `gym8_town`, centre (3647, 6497). Route 8 is 3,050 blocks (relayed).
- **What the player learns:** the final forced exchange will go through the Rift, and Compact dissenters will help
  stop it (`quests.json:782`).
- **Who carries it:** the southern watch officer at (3643, 114, 6497). The display is the ROUTE PACKET barrel.
- **Built:**
  - The way onward. The Earth Badge offers a waypoint to the **Rift surveyor** at (3552, 112, 5334), with a hint
    naming the trailhead about 1,000 blocks north (`POST_GYM8_DIRECTION.md:18`).
  - The watch repeats that direction to any Earth Badge holder who comes back.
- **Written only:** the Compact's split going public, with Nia as the dissenters' voice (`FACTION.md:212`).
- **Unknown:** Giovanni speaks Cobbleverse's battle lines, not ours (`POST_GYM8_DIRECTION.md:18`). Nobody has checked
  whether those lines cast him as Team Rocket's boss, which would contradict "civil defender" (U3).

### Chapter 9: the Rift crisis (Victory Road's south half, the Deep, the HQ, the cradle)

- **Where:** from the surveyor, up the Rift floor to the Deep (`docs/world-building/DEEP_CITY.md:25-36`), then into
  the Compact's HQ tower and down to Hoopa's cradle at (3357, 12, 3306).
- **Level:** the cap is 60 (relayed, `DEEP_CITY.md:28`). The HQ and arena fights ignore the cap (U54).
- **What the player learns:** a Compact city of rescued families exists, Elara has ordered the last cycle, and the
  machine can be shut down. Releasing Hoopa ends forced use (`quests.json:792`).
- **Who carries it, in order:** the surveyor, then the HQ guard (3444, 67, 3283), then Nia at the clinic
  (3536, 33, 3344), then Elara at the tower door, then a fight with Brann (3431, 74, 3305), then Oren at anchor control
  (3433, 128, 3307), then a fight with Elara, then the stair, the passage and the cradle, then the binder's
  "Release Hoopa." at (3363, 13, 3312) (`RIFT_FINALE_CHAIN.md:22-36`).
- **Built and audited offline:**
  - The whole finale chain.
  - Seven HQ tower trainers (counted in `data/hq_trainers.json`).
  - Sign and notice cues: a notice at (3748, 84, 3423) and the Victory Road wall sign at (3566, 2, 3064)
    (`POST_GYM8_DIRECTION.md:24-25`).
- **Placeholders:** 8 of the lines are Claude-written stand-ins for Codex (`"placeholder"` keys counted in
  `dialogue.json`).
- **Not built:**
  - A Hoopa actor. One Hoopa per player at the release, which the owner decided on (`docs/STATE.md:136`).
  - Codex's "one release advances every eligible player". Today each player releases Hoopa for themselves
    (`RIFT_FINALE_CHAIN.md:132-133`).

### Chapter 10: the League

- **Where:** The League, centre (3694, 2430), footprint x3635-3754 z2375-2485 (`towns.json:1122-1148`). Victory Road's
  caves climb to it from the Deep's floor. The precinct gate G5 opens on `rift_crisis_resolved`.
- **What the player learns:** nothing new. This chapter is recognition: the world stays changed, and repair is the
  postgame (`ARC.md:631-634`; steward `dialogue.json:3663-3716`).
- **Who carries it:** the League steward on the west forecourt at (3647, 89, 2490) (`npc_seats.json:271-286`). Then
  the Elite Four (Lorelei, Bruno, Agatha, Lance) and the Champion Blue. Aces are 60/62 (relayed,
  `OAK_AND_CHALLENGE.md:129`).
- **Open:**
  - The League stands inside z4, the 120-species apex zone (U71).
  - The Champion's floor depends on an upstream advancement firing for our override (`POST_GYM8_DIRECTION.md:23`).
- **Missing:** who Blue is in this story (C9).

### Chapter 11: the postgame

- **Built and gated on `champion_cleared`:**
  - Lugia (with Dive).
  - The Necrozma towers.
  - Mew's door (very probably; not seen).
  - Split-Bark.
- **Decided, not built:** Rayquaza (`docs/STATE.md:134-136,213`).
- **Written only:**
  - Maren's record of missing communities (`ARC.md:114`).
  - The Compact as a source of rescue, restitution and contact quests (`FACTION.md:241-249`).
  - "The start of the repair" promised by the steward (`dialogue.json:3701`).
  - The End as postgame (`ARC.md:601`).
- **Missing:** any postgame quest, and any change the release makes to the **shared** world.

---

## 2. The world's story, as the documents tell it

**The worldshift.** Some worlds are collapsing. The Haven Compact formed as mutual aid between their communities, and
it learned to bridge failing worlds through Hoopa's rings (`FACTION.md:9-45`). Its method needs four parts: a survey,
a destination that looks empty, field anchors, and Hoopa forced to open and steer the rings. The two places
*exchange*; nothing is added (`FACTION.md:49-63`). Pallet is the Compact's largest apparent success. The town arrived
here from Kanto almost intact, and the occupied native settlement that stood here vanished (`FACTION.md:65-67`;
`ARC.md:230-233`). An older city-scale exchange had already emptied a summit: the Scar's city now stands in a cavern,
the Displaced City (`ARC.md:382-387`; `SIDEQUESTS.md:377-378`). The eight gym leaders are natives. Only Pallet
remembers Kanto (`ARC.md:133-136`).

**The Rift.** It is accumulated damage, not a natural landmark (`ARC.md:448`). Each forced use makes the next one less
stable and its effects wider (`ARC.md:428-430`). The Deep is a city of rescued families, fuelled by the Rift
(`DEEP_CITY.md:30-32`). Under it, beneath the relic area, Hoopa is held in a cradle (`FACTION.md:71-75`).

**The Compact and the villain.** The Compact is not evil. Its people are heroes to themselves (the owner, relayed in
`HANDOVER_CODEX.md:310-311`).
- Director Elara Venn lost her own town to a delayed evacuation. She treats delay as abandonment, and at the Craters
  she crosses the line knowingly (`FACTION.md:33-39,104-116`).
- Captain Brann Saye commands the guards, and stands down once the operation is over.
- Oren Pell, the engineer, gives Blaine the calibration record.
- Tomas Rill, the surveyor, verifies that the target is occupied.
- Nia Calder, the medic, leads the dissenters (`FACTION.md:118-177`).
- Giovanni has no secret tie to them (`ARC.md:141-142`).

**The ending.** Forced exchanges stop and Hoopa is freed. Nothing snaps back: Pallet stays, the native settlement
stays lost, and refugees still need homes (`ARC.md:625-629`). The last image is Oak's wrong map, with a new one begun
beside it (`ARC.md:650-652`). The rival Maren wants a consented reconnection with Kanto, not a reversal
(`ARC.md:86-101`).

### Contradictions between documents (listed, not resolved)

| # | Subject | One document | Another |
|---|---|---|---|
| X1 | Where the League is | `ARC.md:50,595` and `SIDE_EVENTS.md:310`: (3297, 118, 2603), in Foothill Woods | `towns.json:1132-1144`: centre (3694, 2430), footprint x3635-3754 z2375-2485. Two earlier lots are on record too: `HANDOVER_CODEX.md:271` and `:304` |
| X2 | Where Hoopa's cradle is | `ARC.md:118-129`: "beneath the League plateau". `quests.json:1269`: "(3297, 2603)", status `required_but_unbuilt` | `FACTION.md:71-75`: (3357, 3306) y12. `RIFT_FINALE_CHAIN.md:12`: carved since 2026-10-03. `FACTION.md:254-256` still says "not built" |
| X3 | The steward's position | `quests.json:1125-1127`: (3297, 2603), 433 blocks from the League (left alone deliberately for Codex) | `npc_seats.json:274-278`: (3647, 89, 2490) |
| X4 | What Victory Road is | `ARC.md:34-35,599,606`: "the Rift itself", about 5,200 blocks; Victory Road "reaches the containment level" (`:123`) | `routes.json:16080`: 4,363 walked blocks (read). `HANDOVER_CODEX.md:305`: a tunnel from the Deep to the League, "the only way to the Elite Four". `POST_GYM8_DIRECTION.md:21`: it can be bypassed on the surface (an open owner decision). The cradle is reached through the HQ, not through Victory Road |
| X5 | Who tells the mid-game | `ARC.md` and `FACTION.md:200-213`: leaders and named Compact members, in scenes, at each gym | Built: a clerk, archivist, tracker or analyst at each of gyms 2-5, 7 and 8. The named Compact appears **only in the Deep**; Elara's name is first spoken by Nia (`dialogue.json:11111`). `STATE.md:166` defers those arcs |
| X6 | The Craters | `ARC.md:521-526`, `FACTION.md:211,237`: the player stops the activation | `dialogue.json:3186-3200`: the analyst reports it; no event, no setter |
| X7 | A Hoopa on screen | `RIFT_FINALE_CHAIN.md:95-102`: Cobblemon 1.8.0 has no Hoopa model, so no actor was built | `STATE.md:218`: Mega Showdown 1.0.2 ships Hoopa's models, and a display Hoopa was shown to the owner on 2026-10-06. `STATE.md:136`: Hoopa is to be catchable |
| X8 | Is Hoopa caught or freed? | `ARC.md:67-68,619-620`: Hoopa is released, neither mastermind nor monster | The owner, 2026-10-06: "make it catchable for sure". Not a document conflict but a story one, for Codex (C2) |
| X9 | When Sunset West and Northlight open | `ARC.md:671-672`: postgame | `towns.json:1206-1209`: Sunset West moved to (2660, 6490), 970 blocks off the path. `STATE.md:137` item 4 treats it as early-reachable. `KYOGRE_CAVE.md:86`: the Northlight packet opens at `gym5_cleared` |
| X10 | The jungle ruins | `ARC.md:673`: evidence that anomalies predate the Compact | `STATE.md:326`: retired. Yet `towns.json:2350-2365` still carries the record as `proposed`, at ground y61.0, below sea level (sea level y62 is relayed from CLAUDE.md) |
| X11 | Celebi | `FUTURE_SIDE_CONTENT.md:9`: Celebi "belongs to the mainline arc" | `ARC.md` never mentions Celebi. `legendaries.json:609-615`: the gate is a proposal and the wake item is untaught |
| X12 | The Scar | `ARC.md:349-351,666`: an empty footprint and a road ending at nothing | Built as ruins (`HANDOVER_CODEX.md:336-349`) |
| X13 | `ARC.md`'s own data notes | `ARC.md:19-30`: display names null, no `trainers.json`, no flags | `towns.json` has every display name. Trainers and both progression flags exist (`rift_crisis_resolved` has a setter) |
| X14 | The vision's navigation | `GAME_VISION.md:24-29`: waystones only; defeating a gym unlocks its waystone | The badge gate is off (`STATE.md:147`), and every badge offers a Xaero waypoint (`progression.json:3457-3461`) |
| X15 | The guard's admit line | `dialogue.json:12038`: "Your clearance came down from the surveyor" | A player carried by Nia's badge rule never met the surveyor (`RIFT_FINALE_CHAIN.md:18-20`) |
| X16 | "The Director" | Elara Venn, the Compact's Director | Imogen Vale, the research station's Director (`dialogue.json:12420`, and her locked lines `:12967,13180,13396`) |

---

## 3. Challenge mode

**What exists.** Challenge (Full-Team) is chosen once at Oak, after the starter. It changes the trainers' teams and
nothing else: the same caps, the same places, the same story (`OAK_AND_CHALLENGE.md:32-60`). **No content is skipped
or added for a Challenge player.**

**What any player can already skip, in either mode, because of the badge carry:**
- Mina, Maren, Oak's send-off.
- All eight gym-town tellers and their displays.
- The Rift surveyor (Nia's badge rule covers him, `RIFT_FINALE_CHAIN.md:18-20`).
- The League steward (G5 checks the flag, not the steward).

**What no player can skip:**
- Oak's offer, because it opens the starter chooser and the mode choice.
- The finale's chain of conversations: the guard, Nia, Elara at the door, Brann (talk and fight), Oren, Elara (fight),
  and the binder. That is **seven required interactions with six NPCs** (counted from `RIFT_FINALE_CHAIN.md:22-36`).
  The finale is the only place the story is compulsory.

**What a player who skips the story must still be told, so they are never lost.** These cues come from systems, not
from the story, and they do not depend on mode:

| Moment | The cue today | Status |
|---|---|---|
| Pallet to gym 1 | Oak's directions (part of the story) and the Route 1 signposts | **Gap:** no waypoint (`progression.json:3458`). A player who clicks through Oak gets nothing else |
| Each badge to the next gym | A Xaero waypoint offered in chat (`offers_marker`) | Built; not proven in game (EXP-020 part F, `STATE.md:361`) |
| After Koga | Nothing points to the Mega field | **Gap** (U47) |
| Gym 6 to gym 7 | The bridge at (6632, 3904) is on the route | Signposts only |
| Earth Badge to the Rift | A waypoint to the surveyor, with the trailhead hint | Built (`POST_GYM8_DIRECTION.md:18`) |
| Rift floor to the HQ | The notice at (3748, 84, 3423), z5's one-time turn-back hint, and the guard's turned-away line naming the surveyor or Nia | Built |
| Inside the HQ | Each NPC names the next stop (`tests/test_finale_wayfinding.py`) | Built |
| Release to the League | A waypoint plus a hint naming both ways up, the binder's `release_way`, and the wall sign at the caves' mouth | Built |
| Gates a player meets | Rift guards G1 (2 badges), G2 (8 badges), G3 (60 species), G4 (120 species), G5 (the flag) (`HANDOVER_CODEX.md:285-287`); the level-cap refusal; Dive gates | The zones' refusals print why. **The guards are armour-stand placeholders with no character** (`npc_seats.json:6`; Codex item 23) |

**My recommendation, pending O1.** Keep one story in both modes; do not add a mode-specific path. The badge carry
already makes the story optional up to the finale, and every extra mode branch is more surface to test across 13
bosses that are not yet proven to swap (E7). Two things are worth doing either way:
1. Close the two direction gaps: gym 1's waypoint from Oak, and U47.
2. Have Codex shorten the finale's required lines. The chain stays, but each required NPC gets a one-line path for a
   player who wants to get on.

---

## 4. Gaps and questions

### For Codex (story text and story decisions)

- **C1.** The Craters climax (X6). Write the scene in which the player stops the activation, so it can set
  `crater_operation_stopped`. Then replace `blaine_008`, which reads as a design note spoken in game.
- **C2.** Hoopa after the release (X8). If it can be caught at the cradle (the owner's decision), what does catching it
  mean, given that the story says it was freed?
- **C3.** Each mid-game beat is a clerk talking to the player (X5). Decide which of these get a person or a scene:
  - Nia, Tomas and the Asters at Viltri Quay;
  - the record team at Highwire;
  - the divide at Greenhollow;
  - Elara's representative at Tilpey Cross;
  - Nia at Holdfast.

  The player never meets the villain before the Deep.
- **C4.** Maren after Pallet: nine appearances are written (`ARC.md:103-114`) and none is built. Is Maren ever a
  battle? The vision asks for rivals (`GAME_VISION.md:43`).
- **C5.** Correct `quests.json` upstream: the steward (X3), the cradle evidence record (X2), and the two missing
  conversation ids.
- **C6.** The Scar's ruins and the Displaced City. Was the city exchanged *within* this world, and if so, what went to
  the summit in its place? (`docs/story/handoffs/DISPLACED_CITY_AND_SCAR.md` lists 14 questions.)
- **C7.** The eight placeholder lines, and the guard's "clearance from the surveyor" (X15).
- **C8.** The two Directors (X16).
- **C9.** Who the Champion Blue is, given that Pallet remembers Kanto (`TRAINER_RULES.json:3867-3870`).
- **C10.** Story hooks for the legendaries the arc is silent on: Celebi (X11), the lake trio (`STATE.md:154`), and the
  two sleepers. Also whether the five starters, all from elsewhere (Cosmog, Kubfu, Type: Null, Poipole, Meltan), have
  a reason to be at Oak's.
- **C11.** The postgame "repair": Maren's record and the Compact's restitution quests.
- **C12.** Characters for the Rift guards (G1-G5) and the 34 town gate guards (Codex items 23 and 28).

### For the owner

- **O1.** What does "mostly skipped in Challenge mode" mean? Either (a) a Challenge player is *allowed* to skip it, which
  is already true in both modes, or (b) Challenge should actively *show* less story. Reading (b) means a mode branch in
  the dialogue and is not recommended (section 3).
- **O2.** May the finale's required conversations be shortened, or turned into fights and actions, for players who
  skip the story?
- **O3.** Should the first release change the **shared** world for every player (the Deep's lights, the anchors, the
  Rift), or does each player release Hoopa alone, as built?
- **O4.** Is Victory Road the only way up, or may players bypass it on the surface (X4; `POST_GYM8_DIRECTION.md:21`)?
- **O5.** The League inside z4 (U71): move the zone, or move the lot?
- **O6.** When do Sunset West and Northlight open: early or postgame (X9)?
- **O7.** Should the jungle ruins record be retired from `towns.json` too (X10)?
- **O8.** Is the Brock outside gym 1 the witness? (Chapter 1. Click him in game.)

### Unknowns (experiment candidates)

- **U1.** Do the gym-town tellers, the displays and the finale behave in game? (STATE:360. Nobody has talked to them.)
- **U2.** Does the Xaero waypoint offer arrive and get accepted on a badge (EXP-020 part F)?
- **U3.** What do Cobbleverse's Giovanni battle lines say? Read the upstream dialog keys, or fight him once.
- **U4.** Does the Pallet seam read as an abrupt join from Mina's seat? (One screenshot.)
