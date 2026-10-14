# Dialogue review, part 1: `data/dialogue.json` conversations 0-113

Scope: `conversations[0]` (`dlg_route1_thirsty_stranger`) through `conversations[113]` (`dlg_stone_tip_mining_town`),
player-facing `text` only. 114 conversations, 875 text strings read. 38 lines changed in 23 conversations.
Branch `review/dialogue-part1`.

Generated conversations were changed at their source table, then re-spliced:
`dlg_compact_*` from `data/compact_routes.json` (`python tools/compact_routes.py write`), `dlg_fisher_*` from
`data/fishermen.json` (`python tools/fishermen.py write`). `dlg_route4_*` come from `data/route4_events.json`; nothing
there needed changing. Every other conversation in this range is hand-authored in `dialogue.json` and was edited in place.

## Changed lines

### dlg_main_pallet_oak
- `Trust the ground before the map. Bring back an account from someone who was outside Pallet.`
  -> `Find someone who was outside Pallet when it happened, and bring me what they saw.`
  Drops the aphorism. Keeps the instruction.

### dlg_main_pallet_maren
- `Find someone who watched Pallet arrive. We need a witness who did not wake up inside the mystery.`
  -> `Find someone who watched Pallet arrive. Someone who was outside it, not asleep in it like us.`
  "Inside the mystery" is inflated. Now plain.

### dlg_main_brock_witness
- `Compare Pallet's maps with the ground before we speak. Professor Oak and Maren in Pallet hold the first half of this account. Or earn the Boulder Badge from me, and I will tell you anyway.`
  -> `Talk to Professor Oak and Maren in Pallet first. They have the first half of this. Or earn the Boulder Badge from me, and I will tell you anyway.`
  Brochure voice ("hold the first half of this account"). The gate and both ways past it are kept.
- `That makes Pallet one event in a larger pattern. It does not tell me who caused it.`
  -> `So Pallet is not the only one. The rock does not say who did it.`
  Abstract summary. Now in Brock's voice (rock).
- `The sample proves two grounds were joined. The missing settlement proves what the join cost.`
  -> `Two grounds joined with nothing between them. And a settlement gone to make room.`
  Parallel "X proves... Y proves..." aphorism. The recap keeps both facts.

### dlg_main_misty_relief_clerk
- `The Haven Compact brought them out of worlds that were already collapsing. Whatever else is true, those rescues saved lives.`
  -> `The Haven Compact pulled them out of worlds that were already falling apart. Say what you like about the Compact, these people are alive.`
  "Whatever else is true" is a stock hedge.
- `That resemblance does not prove the Compact moved Pallet, and it does not tell us what vanished from either destination.`
  -> `That does not mean the Compact moved Pallet. And it says nothing about what disappeared at either end.`
  Doubled "does not prove / does not tell us" construction.
- `The rescues were real. So is the unanswered question of what each rescue displaced.`
  -> `The rescues were real. What each one pushed out, nobody has asked yet.`
  Tidy closer ("So is the unanswered question").

### dlg_main_surge_signal_clerk
- `The record cannot tell us whether that system was used as a weapon, a rescue beacon, or both.`
  -> `Weapon or rescue line? Could be both. The record does not say.`
  "Beacon", plus an essay sentence. Now a clipped technician voice.
- `The next source lies east of the massif, toward Peak Pond Hollow. Its signal is older and buried under altered ground.`
  -> `Next source is east of the massif, toward Peak Pond Hollow. Older signal, buried under altered ground.`
  Same voice. The direction and place are kept.

### dlg_main_erika_survey_archivist
- `The ledger proves the cost exists. It does not prove that anyone can measure every life at a destination.`
  -> `The ledger shows the cost is real. Whether anyone can count every life at a destination, it cannot say.`
  "Proves / does not prove" parallelism.

### dlg_main_koga_marsh_tracker
- `These marks are not random failures. Every forced exchange makes the next boundary wider and less exact.`
  -> `These are not accidents. Every forced exchange leaves the next edge wider and sloppier.`
  Report voice. Now a tracker's.
- `The Rift may not be a natural scar. It may be damage accumulated from every forced use.`
  -> `I do not think the Rift is natural. I think it is every forced use, piled up.`
  Hedged and abstract. Now a person's opinion.
- `Sabrina's town has the glacier, lake, signal, and memory reports. She can compare what no single tracker can see.`
  -> `Sabrina's town has the glacier, lake, signal, and memory reports. She can lay them side by side. I see one marsh.`
  "What no single tracker can see" is inflated. Same length.

### dlg_main_sabrina_pattern
- `That is why their argument cannot be dismissed as simple cruelty, and why their method cannot be accepted as harmless.`
  -> `So I cannot call them cruel. And I cannot call what they do harmless.`
  Balanced essay sentence that spells out the moral.

### dlg_main_blaine_crater_analyst
- `The Craters can power the Compact's next mass exchange. The energy source is not the discovery that stopped us.`
  -> `The Craters can power the Compact's next mass exchange. That is not what stopped us cold.`
  Stiff "not the discovery that" construction.
- `Stopping the crater operation prevents this activation. It does not make the waiting refugees safe.`
  -> `Shutting down the crater stops this activation. The refugees are still waiting, and still not safe.`
  "Prevents X. It does not Y" parallelism.

### dlg_main_giovanni_watch
- `His challenge is the region's last test before the Rift road: whether you can carry a decision whose cost cannot be hidden.`
  -> `His gym is the last test before the Rift road. He will not make it easy.`
  Tells the player what the fight means. The fact (last test before the Rift road) is kept.

### dlg_main_rift_surveyor
- `If it stops, the refugees do not receive a miracle. That cost remains even if the method is indefensible.`
  -> `Stop it, and the refugees are still stranded. That does not make the method right.`
  Abstract moralising.
- `The world will not reset when this ends. Pallet, the missing settlement, and every stranded refugee will still be here.`
  -> `Nothing resets when this ends. Pallet, the missing settlement and the refugees will all still be here.`
  Slightly inflated. Trimmed. All three facts are kept.

### dlg_main_league_steward
- `The rescued families remain people who need homes. The dissenters remain responsible for the rescues and the displacements they enabled.`
  -> `The rescued families still need homes. The dissenters still answer for the rescues, and for what the rescues displaced.`
  Bureaucratic "remain people who".
- `No one here will promise a safe reversal before one exists. Repair begins with consent, evidence, and care for everyone stranded by the exchanges.`
  -> `Nobody here will promise to undo it until someone knows how. Until then, we look after the people it stranded.`
  Triplet ("consent, evidence, and care") and a mission-statement voice.
- `Opening the League is not another crisis. It is the region recognizing what you carried across it.`
  -> `The League opening is not another emergency. This one is for you.`
  "Not X. It is Y" pattern, and it tells the player how to feel.
- `The trainers ahead will test the team that crossed the continent. The champion's record will mark the end of this campaign and the start of the repair.`
  -> `The trainers ahead will test the team that crossed the continent with you. Beat the Champion and this part is over. The repair goes on after.`
  Ceremonial "will mark the end... and the start of..." parallelism.
- `The crisis is over. The League is open, and the work after victory will still be waiting.`
  -> `The crisis is over and the League is open. The rest of the work will keep.`
  The uplifting closer is trimmed.

### dlg_route1_gastly_pip
- `Then it curls up against Haunter and does not look back at you once. That is how you know it's fine.`
  -> `Then it curls up against Haunter and does not look back at you once.`
  Explained the emotion. The image already carries it.

### dlg_route1_first_cast
- `Patience is a route skill. Nobody believes that until they try it.`
  -> `Waiting is a skill. Nobody believes that until they try it.`
  "Route skill" is brochure vocabulary.

### dlg_route2_viltri_sounding
- `Same lake, three depths. That is why one path never tells you the whole shore.`
  -> `Same lake, three different answers. Now you know why I look at the banks.`
  Explained the lesson. Now it calls back to the keeper's own opening line.

### dlg_fisher_glacial_tear (source `data/fishermen.json` `hello_2`)
- `The current doesn't care what you're after. You learn to cast across it, not into it.`
  -> `You cast across the current here, not into it.`
  Aphorism. All five fishers shared the same wise-old-fisher cadence.

### dlg_fisher_peak_pond (source `data/fishermen.json` `done`)
- `Still the same pond. Still the same me.` -> `Same pond as yesterday.`
  Parallelism for its own sake.

### dlg_fisher_northlight_shore (source `data/fishermen.json` `hello_2`)
- `The sea keeps no timetable, but it keeps a mood. I fish between the boats.`
  -> `The sea has no timetable. I fish between the boats.`
  "Keeps no X, but keeps a Y" literary flourish.

### dlg_compact_courier_ansel (source `data/compact_routes.json`)
- `Good. That is what I wanted to see: a world that fights fair. The lake office will hear the cart is a day late.`
  -> `Good. So this world fights fair. The lake office can live with the cart being a day late.`
  "That is what I wanted to see" is a stock line.

### dlg_compact_mila_aster (source `data/compact_routes.json`)
- `Whatever you hear about the Compact on this road, I hope you remember the cart.`
  -> `You will hear things about the Compact on this road. Remember the cart.`
  "Whatever you hear... I hope you remember" is a stock appeal.

### dlg_compact_nia_pause (source `data/compact_routes.json`)
- `A pause is not abandonment. It is the first time we would ask who is on the other side before we carry someone through.`
  -> `Pausing abandons nobody. For once we would ask who is on the other side before we carry someone through.`
  "X is not Y. It is Z" pattern.

### dlg_compact_dev_aster (source `data/compact_routes.json`)
- `Mila says Nia is right. I say the sergeant is right. The honest answer is both, and we have a boy who needs a roof either way.`
  -> `Mila says Nia is right. I say the sergeant is. Either way, we have a boy who needs a roof.`
  "The honest answer is both" is a tidy synthesis.
- `Whatever you decide you are for, remember that there is a child asking when we are going home.`
  -> `Our boy keeps asking when we are going home. I do not have an answer for him.`
  Told the player how to feel. Now it is the father's own problem.

### dlg_compact_camp_warden (source `data/compact_routes.json`)
- `They are waiting for a transfer that has not been scheduled. Nobody here will tell you it is wrong, because they have nowhere else to put the hope.`
  -> `They are waiting for a transfer nobody has scheduled. Nobody here says so out loud. It is all they have.`
  "Nowhere else to put the hope" explains the emotion.
- `... My guards hold the line; there are not enough of them.` -> `... My guards hold the line. There are not enough of them.`
  Semicolon in speech.

## Reviewed and left unchanged

These read like people already: concrete, uneven, each with a voice.

- Hand-authored: `dlg_route1_thirsty_stranger`, `dlg_pallet_crushed_house_hank` (the owner's own humour; deliberately
  left alone), `dlg_pallet_crushed_house_lena`, `dlg_main_pallet_lab_starter`, `dlg_main_pallet_mina`,
  `dlg_vr_abandoned_cut`, `dlg_route1_gastly_haunter`, `_gengar`, `_portrait`, `_cup`, `_aisle_west`, `_aisle_middle`,
  `_aisle_east`, `_candle_a`-`_d`, `_candle_n`, `_ward_a`-`_c`, `_board`, `dlg_route1_rattata_picnic`,
  `dlg_route1_picnic_hollow_log`, `_bush`, `_crate`, `_stump`, `_rattata`, `dlg_route1_first_cast_rack`,
  `dlg_route2_rollaway_geodude`, `dlg_route2_geodude_rut`, `_sack`, `_boulder`, `_brake`, `dlg_route2_geodude`,
  `dlg_route2_staff_shallow`, `_middle`, `_deep`, `dlg_route2_gauge`, `dlg_route2_claw_post`, `dlg_route2_corphish`,
  `dlg_route2_lotad`, `dlg_viltri_north_bank`, `dlg_route3_nosepass_signs`, `dlg_route3_sign_a`-`_c`,
  `dlg_route3_nosepass`, `dlg_route3_creek_wooper`, `dlg_route3_approach_feeding`, `_mud`, `_stones`,
  `dlg_route3_crate`, `dlg_route3_wooper`, `dlg_route3_swablu_nest`, `dlg_route3_fiber_1`-`_3`, `dlg_route3_nest`,
  `dlg_route3_swablu`, and all seven `dlg_stone_tip_*`.
- From `data/route4_events.json`: all ten `dlg_route4_*` (Hallam, the thaw gate keeper and Biscuit are the strongest
  writing in this range).
- From `data/fishermen.json`: `dlg_fisher_viltri`, `dlg_fisher_sunset_harbour`.
- From `data/compact_routes.json`: `dlg_compact_nia_landing`, `_tomas_landing`, `_ranger_halloran`, `_surveyor_marn`,
  `_sergeant_dorrin`, `_varga_2`, `_camp_mother`, `_boarding_hask`, `_bridge_guard`, `_varga_3`, `_varga_4`,
  `_dissenter_medic`.
- The other lines of the conversations listed under "Changed lines" were reviewed and kept.

## Wanted to change, could not

- **Oak's rules pages** (`dlg_main_pallet_oak` `oak_mode_001`-`oak_mode_005` and the two confirm prompts). These are
  the most brochure-like lines in the range: "the League rules your journey will follow"; "Their combinations are
  tighter, their held items matter, and a prepared answer may need help from the rest of your party" (a triplet);
  "This changes what each battle asks of you, not how far you may train". `tools/challenge_mode_audit.py` check `T`
  (`check_text`, line 1202) requires these nodes to equal the lines quoted in `docs/story/CHALLENGE_GYM_DESIGN.md`
  ("Oak's world-wide choice"), changed only by the substitutions in `DECLARED_REWRITES`. Rewriting them means editing
  that design doc as well, which is outside this unit's writes. Suggested text, if the owner wants it:
  - 001 `Before I send you out, I need to write down which League rules you will battle under.`
  - 002 `Under Standard rules, Gym Leaders bring focused teams with a clear plan. Held items help, but not every Pokémon carries one.`
  - 003 `Under Full-Team rules, every Gym Leader brings six that cover for each other, and their held items matter. Expect to need more than one counter.`
  - 004 `The level limits are the same either way. Only the battles change.`
  - 005 `This is for you alone, and once I write it down it stays. Which rules?` (this one is itself a declared rewrite
    target, so `DECLARED_REWRITES` would need to change with it)
  - The audit's `BANNED` word list (easy/hard/difficult...) must still hold for any new text.
