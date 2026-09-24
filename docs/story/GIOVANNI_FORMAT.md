# Giovanni Battle Format

## Recommendation

Use **doubles** for Giovanni, pending one RCT/Cobblemon runtime proof. Keep his
roster `held` until that proof passes.

Giovanni is gym 8, the last gym before the Victory Road cave gauntlet. A
doubles fight gives that capstone a different skill test from the seven earlier
single battles: lead pairing, partner protection, spread pressure, speed
control, and deciding which opposing slot matters. The availability curve is
wide enough by then to support those choices; it contains every type, multiple
Ground-resistant cores, Tailwind users, Fake Out, priority, Water and Grass
offense, and twelve Ground families.

Singles is technically safer but weaker as a conclusion. It would make the
eighth gym another version of the format the player has already solved seven
times. Multiplayer alone is not an argument for doubles—the battle must still
have one authoritative initiating player and predictable spectators—but the
campaign's team-building goal is.

## Conditions before the roster is written

1. Convert at least two Route 8 trainers to doubles so the format is taught
   before Giovanni. The current Rift Surveyor says it previews doubles while
   still using singles; that is not instruction.
2. Prove `GEN_9_DOUBLES` loads through the installed RCT version.
3. Prove lead order, legal target selection, spread-move damage, switching, and
   AI target choice.
4. Prove a second connected player cannot join, hijack, duplicate, or corrupt
   the initiating player's battle.
5. Prove win/loss callbacks set only the initiating player's badge and dialogue
   state.

## Roster contract after proof

- Six members, levels 52–55, Ground-centred rather than Ground-only.
- One lead pair establishes the battle's rule within the first turn.
- One partner-protection or speed-control line must be visible and answerable.
- Persian may remain Giovanni's signature partner, but Mewtwo does not belong
  in the gym.
- Player answers must come from the pre-Giovanni availability table, with at
  least two independent structures supported:
  - Tailwind plus split Water/Grass offense.
  - Fake Out/priority plus a Ground-resistant or Ground-immune defensive core.

If the runtime proof fails, use singles and preserve the same partner-combo
ideas as sequential pivots. Do not fake doubles in prose around a singles
battle.

## Current blocker

`gym_08_giovanni` remains `held` in `TRAINER_RULES.json` and
`data/trainers.json`. The design direction is settled enough to run the proof;
the roster is blocked by unverified doubles behavior, not by a missing design
argument.
