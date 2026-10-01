# Giovanni battle format

## Current decision

Use **singles** for the authored Normal and Challenge rosters. RCT doubles remains unproven, so it cannot hold the eighth gym open or force untested targeting and multiplayer behavior into the campaign.

Giovanni is gym 8, the final gym before Victory Road. His singles fight still differs from the previous seven: Hippowdon establishes sand, Persian interrupts tempo, Mudsdale anchors physical offense, Nidoqueen supplies special pressure, Krookodile checks passive setup, and Rhyperior advertises a Rock Polish turn. The player solves a sequence of partner-like roles instead of six unrelated Ground attackers.

Normal and Challenge use six members at levels 52–55. Challenge keeps the same species and level cap, then adds Smooth Rock, Persian's Taunt, one Rindo Berry on the ace, and sharper AI. Mewtwo is absent.

## Doubles remains optional research

A later doubles redesign is allowed only after all of these pass in the installed RCT/Cobblemon runtime:

1. `GEN_9_DOUBLES` loads and resolves a complete fight.
2. Lead order, legal target selection, spread damage, switching, and AI target choice behave predictably.
3. Route 8 contains at least two real doubles lessons before the leader.
4. A second connected player cannot join, hijack, duplicate, or corrupt the initiating player's battle.
5. Win/loss callbacks set only the initiating player's badge and dialogue state.

Until then, route trainers and Giovanni must not claim to teach or use doubles.

## Answer contract

The fight must support at least two independent structures from pre-Giovanni availability:

- Split Water/Grass offense: Golduck, Floatzel, or Clawitzer with Cacturne, Lurantis, or Gogoat.
- Ground immunity plus Fighting and priority: Swanna or Kilowattrel with Hariyama, Heracross, Golisopod, or Cacturne.

The complete roster and mode deltas live in `TRAINER_RULES.json` and `TRAINER_MODE_DESIGN.md`.
