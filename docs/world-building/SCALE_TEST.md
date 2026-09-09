# EXP-009 scale and travel test

## Measured routes

Distances come from the deterministic waypoints in `region.json`; they are path
polyline lengths, not straight-line guesses. Regeneration records the values in
`generation-summary.json`.

| Route | Approximate distance |
| --- | ---: |
| Town center → D5 center | 1,362.0 blocks |
| Town center → D4 medium event | 470.5 blocks |
| Opposite sides of D4 | 1,207.9 blocks |
| D4 berry grove → E5 cavern | 2,035.4 blocks |

## Runtime ride evidence

Cobblemon 1.8 stores per-species ride ranges in its jar. `Mudsdale` is a useful
basic land control (LAND SPEED `30-40`, ACCELERATION `50-70`) and `Rapidash` a
faster comparison (LAND SPEED `45-75`, ACCELERATION `30-60`). The shared
`cobblemon:land/horse` profile calculates motion from those stats; the values are
not blocks per second, so this document does not turn them into invented times.
Flying remains a qualitative late-game sightline and bypass test.

| Mode | What to observe |
| --- | --- |
| On foot | Route remains readable; medium event feels discoverable but separate from town. |
| Basic land mount (Mudsdale) | One cell crossing still contains decisions, concealment and at least one stop. |
| Fast land mount (Rapidash) | The 1,250-block cell does not collapse into a trivial sprint; turns and ridge approaches remain legible. |
| Flying mount | Ridge and forest still organize the map from above without exposing every event at once. |

## Exact manual playtest

1. Generate and export the world as described in `world/source/README.md`.
2. Put the exported save in the existing disposable server runtime, set
   `level-name` to the exported folder name, and run the complete-overlay boot.
3. Apply `world/source/exp-009/place-town.mcfunction`, save, restart, then join
   with the matching client.
4. Run `/gamemode creative`, `/gamerule doDaylightCycle false`, `/time set day`,
   and `/tp @s 520 110 560`; descend to the town surface.
5. Inspect the Center, Mart, six support placements, plaza/well, landmark and
   road departure. Check foundations, doors, functional blocks and palette.
6. Walk town → D4 medium event → D5 center using the route coordinates in the
   generation summary. Record elapsed time and whether foliage/ridge conceal the
   other reserved events.
7. Run `/pokespawn mudsdale level=50`, capture it in Creative, mount it, and
   repeat. Then use `/pokespawn rapidash level=50` and repeat. If the runtime's
   command parser rejects that property syntax, run `/pokespawn mudsdale` and
   `/pokespawn rapidash`; do not change world data to work around it.
8. Test one rideable flying Pokémon available in the client and inspect whether
   the ridge, forest depth and river remain readable from above.
9. Classify the scale as **too condensed**, **promising**, or **too empty**, and
   include measured travel times plus screenshots in the EXP-009 results.

The final choice among 1,000, 1,250 and 1,500 blocks per cell waits for this test.

## WorldEdit

**RECOMMEND INSTALL as a development-only experiment.** Large selections, road
grading, palette replacement, undo and repeated schematic/template placement
would materially shorten post-export finishing. Keep vanilla structure NBT and
the terrain source as canonical artifacts, and do not put WorldEdit on the player
pack or make the live campaign depend on it. Axiom remains optional.
