# Dialogue review, part 2: `data/dialogue.json` conversations 114-174

Scope: the last 61 conversations (`dlg_ursaluna_den_watcher` to `dlg_compact_cp14_loyalist_2`). Part 1 (0-113) and
the text outside `dialogue.json` are other reviewers'. Every edit is in place, one line each; no id, node, option,
condition, action or placeholder changed, and every rewritten line is shorter than or the same length as the one it
replaced.

**Generators.** I checked every conversation id and every changed sentence against `tools/*.py` and `data/*.json`.
None of the 23 changed lines (22 distinct; one line appears in two conversations) is written by a generator: the tools that name these ids (`finale_audit.py`,
`frostpeak_keep_quest_audit.py`, `hoopa_cradle.py`, `pokemon_farm.py`, `relic_underground.py`, `apricorn_farm.py`,
`route5_events.py`) either read the conversation or mention it in a docstring, and none carries the text. So nothing
had to be re-spliced.

## Changed lines

### dlg_ursaluna_den_watcher
- `She sleeps, I watch, Highwire gets its quiet. Wake her and you'd best be ready.` -> `She sleeps and I watch. Wake her and you'd best be ready.` (tidy tricolon)

### dlg_lopunny_superfan
- `You did that. You loved something until it turned into itself. Here. ...` -> `You did that. Here. ...` (an aphorism that explains the moment; Ellis talks in short bursts)

### dlg_sunset_watch_keeper
- `... before the dark takes them home. Not before. Not after. Sit on the benches. ...` -> `... before the dark takes them home. Sit on the benches. ...` (rhythmic drama; the line already says "only then" and gives the minute and a half)

### dlg_main_finale_oren
- `I kept telling myself control made the exchanges moral. Better measurements. Smaller losses. One more family carried out.` -> `I kept telling myself careful work made the exchanges right. Smaller losses, one more family carried out.` (fragment triplet, abstract vocabulary)
- `Elara has the shaft interlock. Make her look at what remains when the miracle is removed.` -> `Elara has the shaft interlock. Go down and show her the board is dark.` (abstract, portentous; the new line is concrete and points down to her door)

### dlg_main_finale_elara
- `That certainty became an excuse to leave the other names blank.` -> `I never once asked for the other names.` (a confession explained rather than made)
- `Release it. Then we begin the work that cannot be solved by exchanging somebody else's home.` -> `Release it. Then we find people homes the slow way, without taking anyone else's.` (inflated, abstract)
- `The cradle is empty. Now the work starts that nobody can exchange their way out of.` -> `The cradle is empty. Now the slow work starts.` (same)

### dlg_main_relic_hall_release
- `Release it. Then we begin the work ...` -> as Elara's above (the same line, said by the binder)
- `The machine is quiet; the binding is not.` -> `The machine is quiet. The binding is not.` (semicolon in speech)

### dlg_station_director
- `... Not both: the choice is the point.` -> `... Not both. You choose.` ("X is the point" formula)

### dlg_station_field_officer
- `Brandt, field officer. I count clouds, time storms, and lose arguments with the weather mast.` -> `Brandt, field officer. I count clouds and time storms.` (triplet with a bolted-on twist)
- `... She calls it caution. I call it paperwork.` -> `... Caution, she calls it.` ("she calls it X, I call it Y" template quip)

### dlg_station_archivist
- `The cases are empty because the honest exhibit is the label. ...` -> `The labels are all we have, so the cases stay empty. ...` (writerly aphorism)
- `... whoever wears it could hold what comes. Neither is true yet.` -> `... whoever wears it could hold what comes.` (restates the "Not yet" that opens the line)

### dlg_half_house
- `I set her place every night. Cup on the table, chair pulled out. It's a small thing. It's the thing I can do.` -> `I set her place every night. Cup on the table, chair pulled out.` (explains the emotion; the image carries it)

### dlg_surveyor_line
- `... I'll start a new line from here, with a stone that knows less and a compass that knows more.` -> `... I'll start a new line from here, off the new compass.` (neat antithesis)

### dlg_agnes_carving
- `... The daft, soft, lovely man.` -> `... The daft old thing.` (tricolon)
- `You have it. I know what the tree says now, and that's enough to keep.` -> `You have it. I've got what the tree says now. That'll do me.` (tidy closing note; now in her voice)

### dlg_long_count
- `Perrin Hale. I count. Don't smile; somebody has to, ...` -> `... Don't smile. Somebody has to, ...` (semicolon in speech)

### dlg_pokemon_farm_farmer
- `Shut the gates behind you; the Wooloo think ...` -> `Shut the gates behind you. The Wooloo think ...` (semicolon in speech)

### dlg_wardenhold_maren
- `You beat it? ...It'll be back. Things like that come back. But now it knows we have friends.` -> `You beat it? ...It'll be back. Things like that come back.` (uplifting closer bolted on)

### dlg_wardenhold_sef
- `Sit. The fire's the only honest thing down here.` -> `Sit. The fire's the only warm thing down here.` (portentous; "honest" did no work)

## Reviewed and left unchanged

dlg_old_orchard_keeper, dlg_dune_ruin_salvager, dlg_fossil_dig_foreman, dlg_drovers_hollow_drover,
dlg_main_finale_nia, dlg_main_finale_brann, dlg_main_relic_hq_guard, dlg_main_relic_hq_guard_inside,
dlg_station_shrine_keeper, dlg_r5_nan, dlg_r5_hook, dlg_r5_ewe, dlg_r5_bell_west, dlg_r5_bell_south,
dlg_r5_bell_north, dlg_r5_board, dlg_r5_gorse, dlg_r5_tally, dlg_r5_tolly, dlg_r5_jory, dlg_prospector_claim,
dlg_gate_watcher, dlg_stubborn_tree, dlg_pips_gym, dlg_hide_and_seek, dlg_hide_and_seek_den, dlg_hunters_hide,
dlg_apricorn_farmer, dlg_wardenhold_pell, dlg_compact_cp04_courier_1, dlg_compact_cp04_courier_2,
dlg_compact_cp04_courier_3, dlg_compact_cp04_varga, dlg_compact_cp12_tomas_rill, dlg_compact_cp12_oren_pell,
dlg_compact_cp12_aster, dlg_compact_cp12_guard_1, dlg_compact_cp12_guard_2, dlg_compact_cp12_guard_3,
dlg_compact_cp12_commander, dlg_compact_cp14_nia_calder, dlg_compact_cp14_aster, dlg_compact_cp14_watch_sergeant,
dlg_compact_cp14_loyalist_1, dlg_compact_cp14_loyalist_2.

Most of this range already reads like people: the route 5 shepherds, Pip, the hide-and-seek twins, Hesketh and his
tree, the drover, the prospector. The Compact's NPCs speak without contractions on purpose (it is their voice across
CP-04, CP-12 and CP-14), so their formality was left alone.

## Wanted to change, did not

- **`data/finale_trainers.json` `finale_elara_venn` `player_win`** repeats two of the Elara lines changed above
  ("That certainty became an excuse to leave the other names blank. ... we begin the work that cannot be solved by
  exchanging somebody else's home."). It is outside `dialogue.json`, so it is the third reviewer's; it now
  disagrees with her dialogue and should get the same rewrite.
- **`dlg_main_relic_hq_guard` node 2** ("The surveyor's word opens this door, not the Director's tower. ...") is
  hard to parse, but it carries the route to Nia's packet and the clinic's direction; untangling it needs the
  finale's gating confirmed, which is outside a text review.
- **`dlg_station_director`**'s lock-and-key metaphor runs across three lines (an accident or a lock; the key without
  breaking the door; a key to a door painted on the wall). Each line is fine alone; together it is laid on thick.
  Cutting one changes her character, which is the owner's call.
- **`dlg_compact_cp12_*` and the finale** share one register: every Compact member, from guard to Director, speaks in
  the same measured, contraction-free sentences. It is consistent, but it means a guard and the Director sound
  alike. A voice pass per character, not line edits, would fix that.
