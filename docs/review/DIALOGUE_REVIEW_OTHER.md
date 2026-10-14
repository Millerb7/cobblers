# Dialogue review: player text outside data/dialogue.json

Branch `review/dialogue-other`, from `4955bcdd`. The rubric is the brief's ("AI slop"). Each changed line was edited
at its source and regenerated through that source's own generator. No id, key, placeholder or game fact changed.

## Trainer battle lines

### docs/story/TRAINER_RULES.json -> data/trainers.json (`generate_trainers.py --write-active`)

The worst area. Routes 1-3 and Victory Road spoke in a coach's lecture voice: "That is the lesson", aphorisms
("One counter is a plan. Two counters are a team."), abstractions ("lost tempo", "the seam between weather and
coverage"). **All ten Victory Road trainers lost with the same line**, "Return when your plan has a second line."

Route 1
- p0 pre: `First battle? Mine too. If our eyes meet on the road, we battle—ready?` -> `First battle? Mine too. Our eyes met, so that's the rule. Ready?` (em-dash; keeps the sight-line rule)
- p0 win: `Sand Attack bought me a turn, but it could not fix a bad matchup.` -> `I threw sand in your eyes and you still won?` (lecture)
- p0 loss: `Quick Attack closes a fight before nerves can.` -> `Quick Attack! Over before you could even get nervous.` (aphorism)
- p1 pre: `The Combee followed the flowers; Surskit followed the water. I learned to pack answers for both.` -> `Combee came with the flowers. Surskit came with the puddles. Bugs are everywhere round here.` (semicolon, parallelism)
- p1 win: `You switched instead of forcing one partner through everything. That is the lesson.` -> `You kept switching. Annoying. Smart, but annoying.` (explains the lesson)
- p1 loss: `Bug teams look gentle until you let them control the field.` -> `Not so gentle now, are they?` (lecture)
- p2 win: `You changed targets before Quick Attack could pin you down. Brock will not wait either.` -> `Quick Attack didn't rattle you. Good. Brock won't wait for you either.`
- p2 loss: `Fast Water types turn a dry path into their own ground.` -> `Lost to Water types in a dry valley. Think about that one.` (aphorism)
- p3 pre: `Brock survives the obvious first hit. Bring a second answer for what comes after.` -> `Brock's rocks take the first hit and keep coming. What have you got after that?`
- p3 win: `That is a team ready for stone: pressure from more than one direction.` -> `Yeah, you're ready for Brock.` (brochure)
- p3 loss: `One counter is a plan. Two counters are a team.` -> `One counter won't get you past Brock. Bring two.` (tidy parallelism)

Route 2
- trainer_01 pre: `Corphish does not need a long plan. It denies yours and takes the opening.` -> `Got a plan? My Corphish doesn't care.`
- trainer_01 win: `You attacked before Taunt stole your setup. Good.` -> `You hit me before Taunt landed. Fair enough.`
- trainer_02 win: `You broke the cycle before Charm, confusion, and Moonlight piled up.` -> `Charm, confusion, Moonlight, and you still got through. Rude.`
- trainer_02 loss: `A weak attack matters when the other side controls every turn.` -> `Told you they don't hit hard. They didn't need to.` (lecture)
- shore_trainer_01 win: `Krabby pushes hard and Shellder closes up. You changed the kind of pressure instead of repeating it.` -> `Krabby hits hard, Shellder shuts tight, and you got round both. Huh.` (explains)
- shore_trainer_01 loss: `The bank rewards a long walk, but it still expects the right answer.` -> `Long walk out here to lose. Bad luck.`
- trainer_03 win: `Electric pressure handles open water. Flying or Bug pressure handles what grows in it.` -> `Electric for the water, Flying or Bug for what grows in it. You'll do fine against Misty.` (parallelism; hint kept)
- trainer_03 loss: `Misty's lake will not give you one clean weakness to chase.` -> `Misty won't give you one weakness to hit. Neither did I.`

Route 3
- p0: pre `On a climb, controlling the footing matters more than moving first.` -> `On a climb, footing beats speed. You'll see.`; win `You punished Howl before Rock Tomb could keep you slow.` -> `You hit me while I was Howling. Should've thrown Rock Tomb first.`; loss `One speed drop was enough to decide the slope.` -> `One Rock Tomb and you were stuck on the slope.`
- p1: pre `The grove punishes teams built around one resistance. Show me your second switch.` -> `Built your whole team around one resistance? The grove eats teams like that.`; win `You saw the partner behind the first matchup.` -> `You saw my second one coming. Most don't.`; loss `One safe switch led straight into the other threat.` -> `Safe switch, straight into my other one.`
- p2: pre `Burrows and roots both carry current into the earth. That is how you face Surge.` -> `Burrows and roots. Current goes into the earth and stops there. That's how you beat Surge.`; win `You found the opening before Ground and Grass could settle in.` -> `You got in before my Ground and Grass could dig in.`; loss `Bunnelby can grow into your clean Ground answer. Skiddo is the fallback when Ground gets disrupted.` -> `Catch a Bunnelby, it grows into a real Ground answer. Skiddo too, if Ground gets shut down.` (hint kept, said plainly)
- p3 (its `lesson` says the dialogue names Ground, Grass and priority; it still does): pre `That mast keeps changing the way everything moves. Let us see how your team handles lost tempo.` -> `That mast messes with everyone's speed. Let's see how you cope.`; win `Good. Do not race Surge—use Ground, Grass, or priority to take the turn back.` -> `Good. Don't race Surge. Ground, Grass or priority gets you the turn back.` (em-dash); loss `Paralysis makes speed unreliable. Bring an immunity or a way to act first anyway.` -> `Paralysed, so speed means nothing. Bring something immune, or something that moves first.`
- p4: pre `The mountain's safest teams redirect electricity instead of trying to endure it.` -> `Up here you don't tank Electric. You send it somewhere it can't hurt.`; win `You brought immunity, resistance, and pressure. That is enough to challenge the shelf.` -> `Something immune, something that resists, and you hit back. Go take the shelf.`; loss `The pond behind you offers Wooper. Bunnelby stays on the critical path. Use one of them.` -> `There's Wooper in the pond behind you and Bunnelby on the path. Catch one.` (hint kept)

Victory Road (teams checked: Drapion/Toxapex poison, Weezing Will-O-Wisp + Mudsdale, Gigalith Stealth Rock, Aggron Stealth Rock + Crobat)
- 01: pre `The cave takes speed before it takes strength. Keep something quick in reserve.` -> `This cave slows you down before it beats you up. Hope you kept something quick.`; win `You kept a second pace. That is the lesson.` -> `You had something fast left over. Fine.`; loss -> `Too slow. Go back up and get faster.`
- 02: pre `A bad condition becomes a worse hit down here. Do not let the clock start.` -> `Get poisoned down here and every hit after it gets worse. Don't let me start.`; win `You broke the clock before it owned the fight.` -> `You ended it before the poison could add up.`; loss -> `Every turn you sat there poisoned was mine.`
- 03: loss -> `Too hot for you. Go and cool off.` (pre and win kept)
- 04: pre `One mark ruins muscle. The next target asks whether you brought another kind of force.` -> `One burn and your big hitters are done. Then Mudsdale. Got anything that isn't muscle?`; win `changed tools` -> `switched tools`; loss -> `All muscle, and I burned it.`
- 05: pre `Rest is over. Sand changes what survives the next hit.` -> `Break's over. Once the sand's up, my side takes hits yours can't.`; loss -> `The sand was chipping you from the first turn.` (win kept)
- 06: pre `Speed means something different for the next few turns. Survive the room, then move.` -> `For the next few turns, slow goes first. Live through the room, then move.`; loss -> `All that speed, and my room made it worthless.` (win kept)
- 07: pre `Rain makes both halves of my team faster at their jobs. Split them apart.` -> `In the rain both of mine do their jobs faster. Try and split them up.`; win `You found the seam between weather and coverage.` -> `You got between the rain and the coverage. Nice.`; loss -> `Still raining. Go and dry off.`
- 08: pre `The cut punishes every careless change. Choose what stays in before you move.` -> `Switch carelessly in this cut and the rocks bill you. Pick who stays in.`; win `You paid for no change you did not need.` -> `Not one switch you didn't need. Good.`; loss -> `Every switch cost you. Should have counted.`
- 09: pre `I stop your plan, then begin mine. Show me you brought a second plan.` -> `I stop your plan, then I run mine. Got a backup?`; win `That answer was ready before mine started.` -> `You had that ready before I'd even started. Annoying.`; loss -> `First plan stopped, no second one. Done.`
- 10: loss -> `Fail. Come back with a better six.` (pre and win kept: already in character)

Reviewed and left: all 26 gym junior lines (in character, concrete), the 13 bosses' `modes.challenge` blocks (they carry no
spoken line: `open_line` is a species list; their dialogue is `dlg_*` ids in data/dialogue.json). `strategy`, `lesson`,
`ace_math_change`, `line_obviousness`: `tools/player_guide_battles.py` and `tools/challenge_guide.py` DO quote them to
players, labelled by field name, as battle notes. They are terse technical notes, not prose, and rewriting ~4,000 words of
balance analysis risks game facts; left. The owner may decide otherwise.

### tools/late_route_trainers.py VOICE -> data/late_route_trainers.json (`--write`; seats unchanged)
- route_04_trainer_01 pre: `Snowline starts here. One Pokemon, one lesson: Ice chips through what Erika grows.` -> `Snowline starts here. Just the one Pokemon, and its Ice chews through anything Erika grows.` (lesson voice)
- route_04_trainer_02 loss: `One answer for two angles is no answer. Try again.` -> `One answer, two problems. Try again.` (aphorism)
- route_04_trainer_03 win: `That is the lesson, and you had it already. Mind the embers.` -> `You knew that already. Mind the embers.`
- route_05_trainer_02 win: `You closed it before I could heal through. That is the trick.` -> `You finished it before I could heal. Annoying.`
- route_06_trainer_02 loss: `A resistance is a wall, not a bluff. Bring a key.` -> `Resisted is resisted. Bring something else.` (aphorism)
- route_08_trainer_05 loss: `Narrow beats nothing. Widen it.` -> `Too narrow. Widen your team.`
- route_08_trainer_07 loss: `A balanced three stopped you. Prepare; do not hurry.` -> `Three, no gimmick, and you still lost. Don't rush him.` (semicolon in speech)

The other 77 late-route lines are terse and in character; left.

### data/finale_trainers.json (hand)
- finale_elara_venn player_win: `That certainty became an excuse to leave the other names blank. There is no operation left to finish. Release it, and we begin the work that cannot be solved by exchanging somebody else's home.` -> `I never once asked for the other names. There is no operation left to finish. Release it. Then we find people homes the slow way, without taking anyone else's.` (matches review/dialogue-part2's rewrite of dlg_main_finale_elara, da458909)
- Note: both finale records' `dialogue_text` sits under `superseded_seat`; no tool I found reads it live. Brann's three and Elara's pre/loss reviewed and left.

Reviewed and left: data/league_trainers.json (5), data/mansion_guardians.json (5; the ghosts' ellipses are possession,
not drama), data/arena_trainers.json (7), data/hq_trainers.json (7), data/compact_routes.json actors (7), the
rctmod cooldown lines in tools/route_trainers.py, data/trainer_refusals.json.

## Markets: data/markets.json (hand)
- counters.greenhollow: `...can buy the feeding fittings, malasadas and puffs your partners will love you for, and a Miracle Seed.` -> `...can buy the feeding fittings, malasadas, puffs and a Miracle Seed.` (brochure)
- counters.northlight_station: `Station supply. Hammocks for anyone; supplements for trainers; and the station's specimen exchange: netherite from the deep Nether pays for what our research turns up. A Master Ball, the held items and the capsule are bartered for metal, never money: ask the Exchange in the Mart.` -> `Station supply. Hammocks for anyone, supplements for trainers. What our research turns up goes for netherite from the deep Nether, never money: a Master Ball, the held items and the capsule. Ask the Exchange in the Mart.` (semicolons, brochure)
- stalls.tilpey_market_kitchen: `Everyone passes through Tilpey; everyone eats.` -> `Everyone passes through Tilpey, and everyone eats.` (semicolon)
- stalls.rimwatch_rangers_kit: `Glass for the far wall, a compass for when the fog comes up, a lamp for the night watch.` -> `Rangers' kit. Glass, compass, lamp. The fog comes up off the far wall fast.` (the third stall with the same "X for Y" triplet; northlight_field_kit and highwire_relay_spares keep theirs)

Reviewed and left: the other 52 greetings. The superseded purchase messages are not live.

## Trading Post: data/produce_buyer.json (hand)
- greeting: `Trading Post. I pay the posted price for what you dig, cut, grow and catch, as much as you bring: no limit. Sell one crate at a time, or have me take everything I buy. Found items (held items and evolution items) I buy by the piece, but only when you sell everything.` -> `Trading Post. Posted price for anything you dig, cut, grow or catch, and no limit on how much. Sell a crate at a time, or I take everything I buy. Found items (held items and evolution items) go by the piece, but only when you sell everything.` (recited mechanics; every rule kept)
- messages.short_note: `One take came up short of what was counted; you were paid for what was taken.` -> `One take came up short of the count. You were paid for what was actually taken.` (semicolon)

## Quests: data/quests.json
- The five fisher objectives (generated by tools/fishermen.py, fixed in its template and re-spliced with `write`; only
  the quests text changed): `has a Ultra Rod` -> `has an Ultra Rod` (article chosen by the rod name).
- Reviewed and left: the other ~110 objective texts. Plain and specific. The main_worldshift_reveal objectives
  ("Verify that the Craters operation targets an occupied destination...") read like a report, but they are concrete;
  `physical_evidence.description` is a design spec, not shown to players.

## Rewards: data/rewards.json
Reviewed all 55 `message` fields; none changed. They name where and what, concretely ("Wedged under the barrel, wrapped
in oilcloth and dry: a Water Stone, and five Net Balls."). A few flourishes are in-world and short.

## Signs, books, system messages (reviewed, left)
- data/signposts.json names and notices; data/research_station.json signs; reveal_evidence, sea_town, apricorn_farm signs: terse, sign-like.
- Rift Guide book (tools/dungeon_guide.py sections()): reads like a manual, as it should. Its figures are read from data.
- `messages` blocks in blackout, dungeons (247), dungeon_extras, dungeon_extras2, dungeon_puzzles, dungeon_themes,
  ferries, kyogre_cave, rayquaza_sky, training_services, mythical_starters: short, functional or atmospheric in a
  plain way. One awkward line left for the owner: rayquaza_sky `hush`, "Rayquaza will not answer while one the sea and
  the mountain have not seen stands on the crown." (hard to parse; making it plain would name Kyogre and Groudon, which
  the current text avoids on purpose).
- tellraw strings hard-coded in tools, sampled: kyogre_cave.py ("You have found Kyogre."), legendaries.py ("The Celebi
  opens its eyes."), arena_runtime.py ("Heaven's Arena - %s - click to challenge"), dungeon_guide.py ("The rift hands
  you a guide. Read it from your pack."). Most tellraw text comes from the data `messages` blocks above; nothing worth
  fixing found.
- No rctmod language files are authored in data/ or modpack/.

## Not reviewed (owned by dialogue.json, or spliced into it)
Thirty-odd tools splice conversations into data/dialogue.json from their own data files (fishermen, ferries,
coldwater_station, frostpeak_camp, northern/southern_residents, training_services greeting, compact_routes, hq_tower,
research_station, produce_buyer's quest half...). I did not edit those sources: re-running their `write` would change
data/dialogue.json under the other two reviewers. The reverse also holds: **an edit in data/dialogue.json to a spliced
record is reverted by the next `write` of its tool, or fails that tool's check.** Each spliced line has to be changed
in its source file.
