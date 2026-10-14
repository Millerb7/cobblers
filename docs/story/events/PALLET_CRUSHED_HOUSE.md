# Pallet Crushed House — The Hundred Complaints

- **Event ID:** `EVT-PALLET-CRUSHED-HOUSE`
- **Kind:** Character rescue and long-form joke
- **Region anchor:** `hometown`, Pallet Town centre (1462, 5293)
- **Progression:** Optional; available from the start; no required flag

## Purpose

This event makes the Worldshift personal before the larger plot explains it.
One Pallet house was crushed by debris and compression during the exchange. A
husband woke outside with no memory of getting there. His wife is still inside.
They were fighting when the town moved, so his panic comes out as a ridiculous
stream of complaints.

The expressions **“chud wife”** and **“being a fungus”** are deliberate inside
jokes. They should sound like this couple’s established nonsense vocabulary,
not general regional slang.

## Characters

- **Hank:** worried, stubborn, talks when frightened, insults domestic details
  while revealing that he notices and values everything Lena does.
- **Lena:** alive, bruised, trapped behind a stable pocket of debris, entirely
  capable of insulting Hank back. She heard much of his speech through the
  wall.

Names are working names and need stable NPC IDs later.

## Physical scene

- Place the damaged house inside the measured Pallet footprint
  (x 1397–1528, z 5228–5359).
- Hank stands outside a visibly blocked entrance.
- Lena waits in a protected interior pocket reachable by a short side opening,
  crawlspace, or debris-clearing interaction.
- The house must look repairable enough that finding Lena alive is credible.
- Do not place the NPCs or house until the town layout assigns exact blocks.

## Interaction flow

1. Talking to Hank starts the hundred-line monologue.
2. Each interaction advances exactly one short line. Leaving preserves the
   player’s current line.
3. After line 100, the objective changes to **Check the crushed house**.
4. The player reaches Lena and confirms she is alive.
5. Lena exits or relocates to a safe exterior marker.
6. Lena gives the reward and both NPCs switch to short repeatable banter.

The long sequence is the joke. It must never block leaving Pallet or any main
progression.

## Hank’s 100 lines

1. `H001` — My wife is in there.
2. `H002` — I woke up outside. Just outside. No idea how.
3. `H003` — One second, kitchen. Next second, grass in my mouth.
4. `H004` — And my chud wife is still inside.
5. `H005` — Lena! If you hear me, yell something rude!
6. `H006` — Nothing. That is actually unusual.
7. `H007` — She normally has something ready.
8. `H008` — We were fighting when it happened.
9. `H009` — Not a serious fight.
10. `H010` — Well. It had become serious to her.
11. `H011` — It started with a spoon.
12. `H012` — A completely normal spoon.
13. `H013` — I put it in the wrong drawer.
14. `H014` — Apparently we have a correct spoon drawer.
15. `H015` — She was being a total fungus about it.
16. `H016` — Very fungal behavior.
17. `H017` — The chud heard me say that.
18. `H018` — She always hears me say that.
19. `H019` — My chud wife loves rules nobody voted on.
20. `H020` — Forks left. Spoons right. I get tires sometimes...
21. `H021` — Then she brought up the boots.
22. `H022` — The boots were by the door.
23. `H023` — "Doors are where boots go." chud ahhhh shit yk twin.
24. `H024` — The chud says boots go under the bench.
25. `H025` — The bench is also by the door.
26. `H026` — We agree geographically.
27. `H027` — Philosophically, we are enemies.
28. `H028` — Then the windows flashed purple.
29. `H029` — I thought the chud had finally become psychic.
30. `H030` — She said, “Hank, that is not me.”
31. `H031` — Very calm for a fungus. Suspiciously calm.
32. `H032` — The floor pulled sideways.
33. `H033` — Not down. Sideways.
34. `H034` — Floors should pick one direction.
35. `H035` — The cupboard opened.
36. `H036` — Every correct spoon became airborne.
37. `H037` — I was struck by her entire argument.
38. `H038` — Three spoons. Maybe four.
39. `H039` — She laughed.
40. `H040` — During a disaster, the chud laughed at me. Crazy work.
41. `H041` — That is my chud, though.
42. `H042` — She finds the exact wrong moment delightful.
43. `H043` — I tried to grab the table.
44. `H044` — The table left first.
45. `H045` — If you find it, the left leg wobbles.
46. `H046` — Do not let that chud pretend it does not.
47. `H047` — She has denied that wobble for six years.
48. `H048` — We put folded paper under it.
49. `H049` — Her idea.
50. `H050` — Good idea, honestly.
51. `H051` — Then the roof made a sound like thunder eating gravel.
52. `H052` — I called her name.
53. `H053` — The chud called me a turnip.
54. `H054` — That means she was scared.
55. `H055` — Usually that fungus says “moldy turnip.”
56. `H056` — Plain turnip is serious.
57. `H057` — I remember reaching for her.
58. `H058` — I remember the green necklace my chud always wears.
59. `H059` — Then I remember dirt.
60. `H060` — Wet dirt. New dirt.
61. `H061` — The sky looked wrong.
62. `H062` — The hills looked worse.
63. `H063` — Our chimney landed over there.
64. `H064` — The neighbor’s fence landed over here.
65. `H065` — The neighbor has not stopped mentioning it.
66. `H066` — Fair, I suppose.
67. `H067` — I dug at the front door.
68. `H068` — The frame shifted when I touched it.
69. `H069` — I stopped. I am irritating, not stupid.
70. `H070` — My chud would dispute both parts.
71. `H071` — She knows houses better than I do.
72. `H072` — She fixed the pantry shelf herself.
73. `H073` — I offered help.
74. `H074` — The fungus asked me to stand farther away.
75. `H075` — It has held for four years.
76. `H076` — The shelf, I mean.
77. `H077` — I hope the room around it held too.
78. `H078` — The chud keeps tea behind the blue tin.
79. `H079` — Emergency money under the flour.
80. `H080` — Spare key inside the ugly planter.
81. `H081` — The fungus says the planter is rustic.
82. `H082` — It is shaped like a screaming Bellsprout.
83. `H083` — I bought it for her.
84. `H084` — That is not the point.
85. `H085` — The point is my chud cannot be gone.
86. `H086` — We still have not settled the spoon question.
87. `H087` — And I called her a fungus. Which she was being.
88. `H088` — Quietly. Mostly quietly.
89. `H089` — The chud called me worse.
90. `H090` — Better, too. She is creative.
91. `H091` — I should have grabbed my chud instead of the table.
92. `H092` — I knew the table was unreliable.
93. `H093` — I knew she was right there.
94. `H094` — I keep thinking she yelled after I landed.
95. `H095` — Or maybe that was somebody else.
96. `H096` — I cannot move the front wall safely.
97. `H097` — There may be a gap around the side.
98. `H098` — You look less likely to collapse it than I am.
99. `H099` — If the chud insults you, that means she is fine.
100. `H100` — Please check on my chud wife.

## Objective text

**Check the crushed house for Lena.**

Hank heard the roof collapse during the Worldshift. Look for a safe opening
rather than breaking the front wall.

## Lena’s discovery dialogue

1. `L001` — Hello? If that is Hank, the spoon drawer is still wrong.
2. `L002` — Oh. You are not Hank.
3. `L003` — Good. You look useful.
4. `L004` — The beam missed me. The cupboard did not.
5. `L005` — I am bruised, trapped, and extremely alive.
6. `L006` — Did he make you listen to the whole hundred?
7. `L007` — Of course he did.
8. `L008` — That man panics in paragraphs.
9. `L009` — He called me his chud wife, did he not?
10. `L010` — Tell him this fungus heard everything.
11. `L011` — Help me past this beam, then take this.
12. `L012` — You earned it long before you opened the door.

## Reward

**Pallet Locket** — a Miracle Seed worn on a simple chain.

- Mechanical base: Miracle Seed, subject to item-ID verification.
- Display name: `Pallet Locket`.
- Lore: `A green seed Lena wore for luck. It survived the Worldshift.`
- Purpose: useful for an early Grass-type answer to Brock while also feeling
  like personal Pallet jewelry.
- Lena explains that this is her spare charm; she keeps the matching one.

Optional bonus cosmetic: **Patient Listener**, granted for reaching line 100
without leaving the conversation more than once. Do not attach useful power to
the bonus.

## Post-event banter

- **Hank:** She is alive. She is furious. Beautiful day.
- **Lena:** He told a stranger about the spoon drawer.
- **Hank:** It is a historic dispute now.
- **Lena:** Put one spoon wrong and I will bury you in the new dirt.
- **Hank:** See? Completely recovered.

## Multiplayer and reset notes

- Dialogue position should be per player so one friend cannot consume another’s
  hundred-line joke.
- The rescued-house state is shared. Once Lena is found, later players receive
  a short recap and can still claim the reward once per player if desired.
- If the server restarts during the rescue, Lena remains in the last safe state;
  the house never resets on top of a player.
- The event must not require block breaking unless the exact protected-block
  and reset behavior is proven.

## Implementation gaps

1. Exact house, Hank, Lena, safe-opening, and post-rescue coordinates.
2. Final ruined-house structure and protected debris interaction.
3. NPC dialogue and state mechanism capable of preserving 100 per-player lines.
4. Verified Miracle Seed item ID and custom-name/item-lore syntax for 1.21.1.
5. Once-per-player reward behavior on a shared server.

## Built (2026-10-13, unit PALLET-HANK-LENA)

What exists, what it rests on, and what has not run. Nothing here has been seen in a running Minecraft.

**Scoping.** The house's state is a score, not player data: `quest.evt_pallet_crushed_house.house_state` is the fake
player `#evt_pallet_crushed_house.house_state` in the objective `cobblers_world`, `0` = `blocked`, `1` =
`lena_relocated` (an unset score reads as `blocked`). A score was chosen over command storage because the dialogue
already reads world facts as a tag set by `execute ... run tag` and read with `q.player.has_tag` (flags, held items),
and one command is one main-thread step, so the compare-and-set needs no lock. The stage, the dialogue cursor and the
reward claim stay in each player's `q.player.data()`. The mechanism is `tools/compile_dialogue.py`, the "world" paragraph
of its docstring: `progression_equals` on a world field, `set_progression`, `compare_and_set_progression` and
`relocate_actor`. A world field named anywhere else is refused, so it can never be read from a key nobody writes.

**Flows (played in a simulator of the compiled Molang, `tests/molang_dialogue_sim.py`, 30 tests in
`tests/test_crushed_house.py`, one of which needs a prepared build/ and skipped here).**
- Player 1: the hundred lines in order, the objective, Lena's twelve, then at `l012`'s acknowledge: the score goes to 1,
  Lena is tagged at the interior marker and teleported to the exterior one, the Miracle Seed is given, the claim and the
  stage are written. Leaving mid-way keeps the line; each player's cursor is their own.
- Player 2 after: Hank says the one recap line (the monologue is skipped, stage `shared_rescue_recap`), Lena's recap
  line pays the seed once and sets stage `complete`; both then give the short banter. A player who walks straight to
  Lena after the rescue is paid too. A player mid-monologue when another finishes gets the recap on the next click.
- Two players finishing at once: both are paid once, she moves once, one NPC stands at the exterior marker.
- Design choice where this document was silent: **every player is paid once, whether or not they found her**. The
  event doc allows it ("can still claim the reward once per player if desired") and the quest record already encoded it.
- Two small repairs to the authored dialogue, both in `data/dialogue.json`: Lena's "not yet" line and Hank's objective
  line no longer write their own id into the cursor the two conversations share (a player who tried Lena mid-monologue
  would otherwise have had Hank answer with a page he does not have), and Hank now repeats the objective to a player
  who is mid-way through Lena's lines (he used to close in silence).

**Reward.** `cobblemon:miracle_seed` x1, delivered **plain**. The item id is verified (`data/rewards.json` cites the
jar). The "Pallet Locket" name and the lore are NOT delivered: the `give` would carry them as `custom_name` and `lore`
item components, whose quotes must survive a Molang single-quoted string, and nothing in the repository has run one in
game. `data/quests.json` `reward_pallet_locket.contents_note` records it; implementation gap 4 stays open for the name.

**Where they stand** (all `round(heightmap)` from `tools/ground.py`, feet = ground + 1, all 117 / 118):

| | x, y, z | yaw | note |
|---|---|---|---|
| Hank | 1509, 118, 5258 | -90 (east) | 3 blocks west of the blocked front door (1512, 5258) |
| Lena, in the house | 1516, 118, 5258 | 0 (south) | the 9 by 9 lot's centre, facing the side opening (1516, 5262) |
| Lena, after | 1508, 118, 5262 | -166 | 4.1 blocks from Hank, facing him |

The lot is x 1512..1520, z 5254..5262: all 81 columns y117. It sits on the east edge of the town, 46 or more blocks
from every walked route line. `data/crushed_house.json` is the plan; `data/npc_seats.json` holds the stands (Hank a
seat, the two Lena stands `markers`, Lena a `relocating_seats` record).

**The apply.** Hank is an ordinary seat: step **R17N** seats him. Lena is step **R18CH** (after R17N): the `npc` action
gets a fifth element, a selector `{objective, holder, value, at, yaw}`; it reads the score over RCON and seats her at the
interior marker while it is 0 and at the exterior marker while it is 1, and a Lena found at the interior marker when
the score says 1 is teleported, never doubled (no `spawnnpcat` is issued). It is idempotent. `tools/npc_seats.py check`
holds the markers to a seat's rules and `verify` probes her at the stand the score selects.

**The house (2026-10-13, unit PALLET-CRUSHED-HOUSE-BUILD): written, applied by a step, never seen in a running Minecraft.**
Rung of the mechanism ladder: datapack functions plus a re-apply step (principle 6, "functions/commands"); the cheaper
rungs cannot place blocks, and the repository's own pattern (`tools/lopunny_house.py`, `tools/sanctuaries.py`) already
does. Nothing is a mod or a script.
- **Generator** `tools/crushed_house.py` from `data/crushed_house.json` `structure` -> pack `cobblers_crushed_house`
  (`build/datapacks/`), two functions: `cobblers:crushed_house/build` (270 commands, 412 non-air blocks) and
  `cobblers:crushed_house/restore` (34 commands). Ground from `tools/ground.py` (rounded); the floor is `F` = the highest
  ground under the lot (117), so the walls start at y118. No world is read. The pack has no runtime data, so
  `tools/pack_roles.py` classes it `build` (measured on the built pack) and `reapply.py strip` takes it out of the heap.
- **Step R16CH**, in `tools/reapply.py` immediately after R16D (the shrines) and before R16E, so it is after R7 (hometown),
  R13, R16 (lights), R16B (dressing) and before R17N (Hank) and R18CH (Lena): `forceload add 1507 5249 1523 5266`, wait 3,
  `function cobblers:crushed_house/build`, `forceload remove`. The prepare job is `crushed_house:build`; the pack is in
  `SERVER_PACKS`, not `WORLD_LOCAL`.
- **Look.** A 9 by 9 cottage in the town's own vocabulary (white plaster over red brick, oak, a brick gable): the west half
  keeps its roof and gable, the north slope stops at x1516, the east half is open to the sky and its rubble mounds to 5
  high; the east wall is broken to 1-3 blocks; a fallen oak (trunk along z at x1518, root plate at z5250, tip at z5261,
  no crown: `oak_leaves` is a spawn condition) lies across the broken north wall and the rubble; the front (west) door is
  a dropped lintel, a jammed beam and a pile at x1510-1511 (Hank stands at x1509, clear); a wall panel leans off the
  south wall west of the opening.
- **The pocket and the opening.** Lena's 3 by 3 room (x1515..1517, z5257..5259, y118-119, a lantern on a barrel in its
  corner) sits in a sealed block of rubble under a plank ceiling at y120 and an oak beam; a one-wide crawl (x1516,
  z5260..5262, y118-119) joins it to the south wall's cell **(1516, 118..119, 5262)**, the safe opening, lintel y120. The
  approach is from the south (1516, 5263-5264); the leaning panel is the only mark. Nothing needs breaking.
- **Conflict with the lot, said plainly.** None with the event doc's intent. One thing it did not say: the roof is open to
  the sky on the east, so a player can climb the rubble onto the shell and walk the attic under the west roof. The pocket
  stays sealed (below), but "no way in except the opening" means "no way to Lena", not "no way onto the ruin".
- **Probes** `data/world_probes.json` place `crushed_house`, 21: the planks under the pocket, the NW post, the west gable's
  ridge course and ridge brick, the opening (feet, head, lintel), the crawl (feet, head), Lena's cell (feet, head), the
  pocket's beam and lantern, the front doorway (feet, head: NOT air), the dropped lintel, the fallen oak, and Hank's and
  Lena's after stands (air, feet and head). `python tools/crushed_house.py probes --write` regenerates them; `build` refuses a
  drifted set. Run by `tools/presence_audit.py` (extra); not run against any world.
- **Proved offline** (`tests/test_crushed_house_build.py`, 24 tests): the BUILT function is parsed back over heightmap ground
  and a 0.6 by 1.8 player is walked through it: Lena's cell is reachable from (1516, 5264) through the opening; with the
  opening shut it is not reachable by any route (roof, window, shell); the doorway is not enterable; the three stands are
  clear, standable and connected; nothing is written under the ground but the floor; every block is declared and none is in
  `data/spawn_blocks.json`; the restore returns the box to heightmap ground; each tamper case changes the generator's code
  (opening walled up, door carved open, a hole over the pocket, Hank buried) and is caught.
- **Restore** `cobblers:crushed_house/restore`: air above each column's ground over the build's clear box (x1507..1523,
  z5249..5266, up to y140), the floor columns back to `grass_block`, guarded (a player in the box stops it). By hand over
  RCON only; **no step runs it**, so its id is named in the build function's header comment to satisfy `unreferenced()`.
  The surface block `grass_block` is an ASSUMPTION (the ground rule forbids reading the world). To change the design:
  restore, then build: the build rewrites the house volume completely but leaves a stale apron cell of an older design.

**Not done, and why.**
- **Not seen in a running Minecraft, nor applied to any world.** That each command lands, the house reads as a crushed
  repairable house from the street, the clear step leaves the town's own trees alone, stairs, panes and fences take the
  intended shapes, and the lantern lights the crawl (block light above 0 keeps monsters out; not measured) are unproven.
  The ARC's other two damaged homes are not built; `data/quests.json` `pallet_edge_damage_cluster` still reads
  `required_but_unbuilt` for the cluster and was left as it is.
- **Not swept** against placement footprints of other layers (only point records in `data/*.json` were swept); the
  clear step removes logs, leaves and plants in the box (x1507..1523, z5249..5266) and nothing else.
- **Not run in game (the dialogue side):** that Minecraft accepts each emitted command; that Cobblemon keeps Lena's dialogue open when its
  NPC is teleported out from under it on the last line (if it closes, the player has still been paid and the cursor is
  on `post_lena_1`); that the `@e` selector finds her in the loaded chunk.
- Not swept against other layers' claims on the lot's columns (ambient sites, signposts, habitat blocks, the light plan).
- The optional Patient Listener cosmetic is not implemented.
