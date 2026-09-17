# Gym matchup sufficiency audit

**Status:** design assessment only. No encounter pool, species placement, level cap,
trainer roster, move, item, or reward changed in this pass.

## Evidence boundary

This audit compares the current critical-path availability tables with the
inherited Cobbleverse RCT v20 Kanto trainer files and Cobblemon 1.8 species
data. The route bands are expected party bands, not proven hard caps. RCT's
configured cap appears to be the strongest Pokémon on the next required
trainer plus five, but EXP-003 has not proven that sequence at runtime. There
is no accepted TM, move-reminder, held-item, or evolution-item schedule, and
the inherited teams have not been accepted as the campaign's final teams.
These findings identify design pressure; they do not settle roster or spawn
changes.

## Gym 3: what is actually available

Surge's inherited team is Boltund 32, Magnezone 33, Electabuzz 34, and Raichu
35, with two Full Restores. Magnezone has Sturdy and a Focus Sash. Boltund has
Strong Jaw with Fire Fang, Ice Fang, Psychic Fangs, and Thunder Fang.

The expected Route 3 party band ends at 30. The inferred RCT cap would be 40,
but that cap behavior is unproven and is substantially looser than the route
design.

| Answer | What the player really has | Limitation |
| --- | --- | --- |
| Bunnelby → Diggersby | Bunnelby appears commonly at levels 21–23; it is eligible to evolve immediately. Bunnelby learns Bulldoze at 21 and Dig at 24; Diggersby learns Bulldoze at 23 and Dig at 28. | Bunnelby itself is Normal, so the player must evolve it. Huge Power is hidden and cannot be assumed. Boltund's Ice Fang directly checks Diggersby. |
| Pond-shore Wooper | Wooper is Water/Ground, learns Mud Shot at 8, and evolves to Quagsire at 20. The authored shore event gives one controlled encounter. | The event's encounter level is unset and its one-per-player encounter mechanism is unproven. Optional discovery is not the same as dependable ambient access. |
| Grass and neutral offense | Skiddo, Fomantis, and Gossifleur resist Electric. Machop and Makuhita can pressure Magnezone with Fighting damage. | These pieces do not form a second demonstrated plan across all four opponents. Boltund carries Fire and Ice coverage. Lotad and Lombre are neutral to Electric because their Water weakness and Grass resistance cancel. |

A Ground type is not mathematically mandatory. A sufficiently trained neutral
team can win, especially if the inherited RCT cap really permits level 40.
Under the authored 20–30 route band, however, no second coherent non-Ground
strategy has been demonstrated. If the inherited Surge team remains, the
campaign needs a second dependable plan; that plan does not necessarily have
to be another Ground species.

## Cost of a second pre-Surge Ground family

Route 3 already emits the design maximum of 20 ambient species. Any ambient
addition requires replacing one of those species or revising the 10–20 target,
then regenerating the availability table and compiled pools. No option below
has been selected.

| Candidate | Place that fits for its own reasons | Cost and drawback |
| --- | --- | --- |
| Wooper | The pond shore beside the Nosepass signs. The event already exists because Wooper live and feed there. | No ambient slot change. To count as dependable, the controlled encounter needs a level, clear signposting, one-per-player runtime proof, and reconnect/duplicate protection. |
| Geodude | A small Route 2 quarry, rock cut, or authored cave tied to the existing miner scene. Rock/Ground Geodude fits this place directly, learns Bulldoze at 12, and evolves at 25. | No Route 3 slot change if tightly localized. The miner's current Geodude returns home, so this requires a separate encounter; generated moves and controlled delivery need proof. Broad Lake Viltri spawning would be a poor fit. |
| Diglett | A loose-soil or talus pocket on lower Mt Clay, preferably a visibly excavated bank rather than generic alpine ground. | Cleanest new ambient mechanic: Ground typing, Bulldoze at 16, evolution at 26. It needs a new ecological pocket and consumes or displaces one Route 3 slot. |
| Mudbray | A worked clay track, pack-animal rest, or human-used lower slope. | Strong natural moves—Bulldoze at 12 and High Horsepower at 28—but its native grassland/badlands identity is weak in the existing forest-and-alpine route unless the place is deliberately human-shaped. |
| Phanpy | A lower talus or haul-road pocket. | It evolves at 25, but Phanpy lacks natural Ground offense before evolution; automatic access to Donphan's level-1 Ground moves has not been tested. Its savanna/badlands identity is also a weak fit. |
| Larvitar | Mt Vessu. It already belongs there for its own mountain ecology. | It is intentionally authored-only and pseudo-legendary. Making it a dependable common answer would cheapen that placement; leaving it rare does not solve availability. |
| Sandshrew | No current Route 3 place fits regular Sandshrew without adding an arid pocket. | Mechanically clean—Bulldoze at 18, evolution at 22—but the terrain addition would exist mainly to solve Surge. |
| Nincada | Foothill Woods. | It loses Ground typing when it evolves at 20, and its native Y 32–62 forest condition conflicts with the foothills around Y115. It is not a stable answer. |

## Is this isolated to Surge?

No. The original table measured whether a weakness type appears before a gym.
It did not test evolution gates, learned moves, held items, coverage, complete
team composition, or battle format.

| Gym | Practical finding against the inherited team |
| --- | --- |
| Brock | Sound. Several Water and Grass families have natural offense at the expected band. |
| Misty | Sound. Electric and Grass plans are both available; coverage checks Grass without removing the Electric plan. |
| Surge | Thin. Evolved Bunnelby is the only dependable common Ground family, and no independent second strategy is established. |
| Erika | Availability is sound, but the expected route maximum is 35 against a level-40 ace. Flying and Ice plans remain independent despite Poison typing and coverage. |
| Koga | Structurally thin at the documented band. Crobat and Levitate Weezing block a Ground sweep, while Drapion blocks Psychic. Jynx plus Diggersby is the one clearly complete level-40 plan. |
| Sabrina | Thin. Stunky→Stuntank is the only dependable common Dark family; evolution gates and anti-counter coverage make the nominal Bug pool much weaker than the table implies. |
| Blaine | Redundant answers exist. Several Water/Ground families bypass the Electric coverage, although the expected route maximum is 50 against level 60. |
| Giovanni | The current availability verdict is invalid. Only half the inherited doubles roster is Ground-type, and Water/Grass availability does not answer Persian, Tyranitar, or Mewtwo. |

Gyms 3, 5, 6, and 8 therefore need a real team-building audit. Gyms 4 and 7
have adequate species breadth but unresolved level-band mismatches. The gap
between route bands and inherited leader maxima grows from five levels at
Gyms 3–4 to ten at Gyms 5–7 and fifteen at Gym 8, so no final fairness claim
is possible until level-cap behavior and final trainer rosters are settled.

## Decision still owed

No species should be added from this report alone. The next design decision is
whether the campaign keeps the inherited Surge roster and coverage at the
authored Route 3 band. If it does, the viable directions are to prove and
guarantee the pond-shore Wooper, add an ecologically justified ambient family,
or establish a non-Ground strategy through roster/move/item design. The same
sufficiency method should then be applied to Gyms 5, 6, and 8 before their
encounter pools are treated as settled.
