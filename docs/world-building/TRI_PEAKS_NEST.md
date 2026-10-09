# The Broken Crown: the Tri Peaks' open-summit nest

The world sweep's gap 2 (`docs/world-building/WORLD_SWEEP_2026-10-09.md` section 7): A2 had no site, and band 3 had
nothing at its own level ahead of the player. This is a creature **in the open**, on a summit, seen before it can be
reached. The Ursaluna den is the Tri Peaks' cave; this is its summit.

| | |
|---|---|
| Creature | **Crownbreaker**, a Tyranitar, level 35 (`cobblemon:tyranitar`) |
| Where | the south peak's bare dome, anchor **(1478, 254, 1062)** (ground y253), sub-region `the_tri_peaks`, tier 3 |
| Data | `data/tri_peaks_nest.json` (the residents' schema, `cobblers.resident-encounters/1`) |
| Generator | `tools/tri_peaks_nest.py` -> `build/datapacks/cobblers_tri_peaks_nest`; calls `tools/resident_encounters.py` for the keeper and the dressing |
| Step | **R9TP** (blocks only), between R9FS and R9JT, before R9E; the pack is world-local |
| Probes | `data/world_probes.json` key `tri_peaks_nest` (16 block probes) |
| Tests | `tests/test_tri_peaks_nest.py`, written by the builder; the independent audit is owed to another agent |

## The place

A dome of rounded stone (y250 to y253 across the bench), scoured bare (radius 7) so the creature stands on stone
and not snow. Round it, six black rock **teeth** 7 to 12 blocks tall (blackstone, deepslate, basalt, with andesite and
tuff), tallest at the back (north-west, 12) and lowest at the front (south-west, 7). The south is open: the seventh
tooth is broken, its stump 3 high at (+3, +9), and its rubble pours down a **scree spur** 112 blocks long, widening
from 11 to 25 columns, with seven heaps along it. Everything is the plain stone family, none of it a spawn-condition
block (`data/spawn_blocks.json`), none of it concrete. It faces Highwire: yaw -31 degrees, down the slope.

## Why this creature, why here

Tyranitar is a big upright dark-and-stone figure whose own silhouette is the skyline; the Cobblemon 1.8.0 species box is
2 x 3.16 (read from the jar). The Tri Peaks' summit heart is birds and Duraludon, so nothing up there is a rock giant,
and Tyranitar is the species whose story is that it takes mountains apart: the broken tooth and its fall of stone are
that story told in blocks, with no sign and no NPC. Rejected (what the other nests of tonight are is relayed from the brief, not read): Aerodactyl and Braviary (a perched bird on a high rock is
the sea-stack rookery's shape, built tonight), Golem (`data/northern_residents.json` already has one, a boulder on the
glacier fields), Avalugg and Mamoswine (ice giants: Whiteback is a resident, and A1 and the Merian cirque get ice
buildings tonight), Rhyperior (the fair swap, see below), Steelix (Attack 85 makes meeting it early a delay, not a
mistake).

**Balance flag for the owner.** Tyranitar is a 600-BST pseudo-legendary and this one is catchable at level 35 with the
third badge. No moves, ability, nature or IVs are written; the species learnset decides. If that is too much, the swap
is two fields in the record (the species and the message): Rhyperior at 535.

## The meeting

- **Early is a mistake.** L35 is over the cap 30 a player carries before beating gym 3 (`data/trainers.json`
  `gym_ace_levels[2]`) and its band is 20-28. The level-cap refusal (`data/level_cap.json`) breaks every ball free
  until the third badge gives the cap 35 (`gym_ace_levels[3]`), the tier-3 ceiling. No advancement, no flag: the gate is
  the same one that holds Old Jaw.
- **Seen from below.** No presence gate, so a band-2 player sees the crown from town and cannot yet take what lives in
  it. Measured on the heightmap: the tallest tooth's tip (1474, 263, 1053) is in line of sight of Highwire's centre,
  416 blocks away, clear of the ground between by 2.3 blocks (a margin, not a wide one), and from Route 3 for its last
  115 path points, from (1721, 1524), 532 blocks out.
- **The way up is a walk.** From Highwire's gate a path with no step over one block between adjacent columns exists: 437
  blocks and 110 of climb to the crown; 314 blocks (46 climb) to the scree's toe at (1476, 1186), then 126 blocks (64
  climb) up inside the scree itself. The creature faces the whole climb.
- **Waking.** Dormant (no AI, on its spot, facing its yaw) until a non-spectator player is within 30 blocks; then awake
  under its own AI and the global Fight or Flight config, leashed to 40 blocks, and put back to sleep once nobody is
  within 56. It returns 72,000 ticks (one hour of server time, the den's cooldown) after it faints, is caught or is
  killed, with a player near and none within 48. A resident that beats a player becomes the blackout's guardian and the
  keeper never touches it again (`data/resident_encounters.json` `build.blackout_decision`).

## Mechanism, by CLAUDE.md principle 6

Cobblemon native (the species, the spawn command), configuration (the level cap, already in place), datapack and
functions (the residents' keeper, called, not copied). No scripting layer, companion or mod. **No entity step:** the
ungated resident is brought in by the keeper the first time a player is within 96 blocks of the crown (none within
48). R18R's RCON summon was not copied, because a step that force-loads and then summons is the shape N155 found racing
a chunk's saved entities (`tools/chunk_look.py`); with no such step there is nothing to race. The cost: the creature
does not exist until someone is within 96 blocks, so it is seen as a figure only on the scree's upper two thirds.

## Spawns

None added. The climb crosses only `the_tri_peaks`' tier-3 land table and its summit heart (`minY` 195: the crown and
the spur down to about z1155, measured), so most of the walk stays catchable. No Habitat Block: the Ursaluna den needs one for its cubs;
nothing here has young.

## Collisions checked

Nearest route path point 406 blocks (the rule is 128); nearest activated Habitat Block `ursaluna_den_outskirts_ward`
363 blocks (the rule is its spawn range 16 plus the leash 40); no x/z authored in any other `data/*.json` within 60
blocks of the dressed box (the one hit, a rejected town-site option at (1480, 1170) in `data/towns.json`, is excluded
by name in the test). Surge's signal array (1928, 1248) is 487 blocks away.

## NOT verified

Nothing here has run on a server or a client. Not verified: the dress function's 5,757 commands on a live world; that
the teeth read from Highwire in play (vanilla view distance is 10 chunks, the town is 416 blocks off; Distant Horizons
is installed and would carry them only once the dressed chunks are saved and its LODs refresh); the entity render
distance claim (vanilla rule from memory); that the keeper brings it in at 96 blocks and that it wakes, leashes and
settles as designed on this ground (the residents' keeper is applied to staging, this instance is not); how Fight or
Flight treats an awake Tyranitar; the actual surface blocks of the dome and the spur (the heightmap has heights, not
materials, so snow over the scree is possible and the clears take one block of it); that the stone teeth do not trap
the awake creature (its leash is 40, the breach is 11 columns clear).

## To run

`python tools/tri_peaks_nest.py --report`, then `python tools/reapply.py prepare` and `--only R9TP` (staging, under the
coordination lock); `python tools/presence_audit.py --only extra`; then walk it: from Highwire's gate to the scree toe,
up the spur to within 30 blocks, and check the wake, the leash, the catch refusal before and the catch after gym 3.
