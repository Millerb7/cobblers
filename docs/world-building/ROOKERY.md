# Gull Rock: the rookery off the north-east coast (cell C7)

Gap 9 of `WORLD_SWEEP_2026-10-09.md` section 7, built 2026-10-09. Record `data/rookery.json`, generator
`tools/rookery.py`, steps R9RK and R18RK, pack `cobblers_rookery`, tests `tests/test_rookery.py`. Not applied to any
world, not run in game, no independent audit yet (`audit_checklist` in the record). Every number below is measured on
the canonical heightmap by `python tools/rookery.py report` unless it names another source.

## What it is

A grey stack 20 blocks out of the sea (crown plate y82, sea y62, bed y55-57), white with guano down its landward faces,
three hay-thatched nest ledges, six dome-shaped tidal rocks on a ring of radius 34 round it, and a colony of sea-birds
on the water and the rocks. On the crown, in a half-ring of her own nest, sleeps the **Gullmother**, a **level 55
Dragonite**. Centre **(6940, 2650)**, 101 blocks east of the beach (last dry column x6839), 1,055 from any route path,
442 from the Northlight ferry's line, 122 from the nearest authored x/z in any other data file (a false hit, kept as a
clearance). Everything written is under the sea: 1,437 columns, 15,051 blocks, 3,231 commands, none on a dry column.

## Two premises of the brief that the heightmap does not support

- **"Seen from the cliffs first": there are no cliffs.** The coast of C7 is a beach on a shelf: ground y62 at the
  waterline, the moor climbing y66 (x6800), y83 (x6720), y98 (x6680), y109 (x6520); the sea 0-1 deep for 35 blocks off the
  sand and 7 or more only 100 blocks out. What the coast has instead is a long slope, so the stack is seen from **above**:
  the Gullmother's head (crown + 4) is in terrain line of sight from x6480 (ground y111), **460 blocks inland** (where the
  scan stops), with two gaps of a few columns near x6522 and x6562 (`tools/rookery.py report`, along z2650; trees and
  the paint are not in the heightmap).
- **"Sea stack or tidal rocks off the coast": none exists.** The only land beyond the beach in the window x6144-7679,
  z1792-3327 is the Pine Isles across the ferry strait. The stack and the six rocks are **authored** out of the seabed
  (a heightfield, deterministic, no randomness), every column checked wet by `tools/water_mask.py` AND by the heightmap
  alone (the test), and none touches land: a stack joined to the sand would be a path, and this is a swim.

## Why a Dragonite, and why these birds

Weighed against the brief's own list:

| Option | Why not |
|---|---|
| Pelipper/Wingull colony | Wingull and Pelipper already fill four water tables (west shore, north-west coast, Tilpey, south strand). They are the **colony**, not the great one. |
| Lapras pod | Lapras is Frostpeak Strand's find and Driftmouth's rare; it is a Surf mount, so a pod would hand out the sea. |
| Corsola reef / Cursola | A coral reef in a cold strait; Cursola is the Brass Petrel's. |
| Skarmory roost | A loner of the crater plateau (tier 8 tables), not a colony's centre. |
| Kingdra | A deep-trench creature; nothing about a rookery. |
| **Dragonite** | The jar's own dex text: *"a kindhearted Pokemon that leads lost and foundering ships in a storm to the safety of land"* (`cobblemon.species.dragonite.desc`, Cobblemon 1.8.0). A ferry strait that cannot be crossed unaided (the packet's 418-block swim is gated) is exactly where she would be. She is Dragon/Flying, 3.2 high, and **55 is the lowest level a wild Dragonite can honestly be**: Dragonair evolves at `minLevel 55` (jar). |

The colony (levels 36-44, up to 3 alive per rock, six rocks): **Pelipper** (anchor), **Swanna** (both on the water's
surface), **Altaria** (her cloud-dragon kin), **Kilowattrel** (the storm bird), **Delibird**, and **Mantyke** (rare, the
ray that skims the wave tops, found nowhere else on this coast). All are final stages or have no level evolution inside
the band (Wingull and Wattrel evolve at 25, Ducklett and Swablu at 35: jar), so there is no Wingull at level 40. Dratini is
not in it: it already stands in two water tables.

## How a player meets it

1. **From the moor's high edge** the stack stands out of the sea with gulls wheeling round it. Early players see it and the
   Gullmother is not behind a gate: she is **ungated** (no `appears_after`), asleep and visible from the first day.
2. **Band 5 (cap 45):** the colony is all catchable (top level 44), at the sandbar and from the rocks. The nearest rock is a
   25-block swim from where deep water (2+) starts at x6875; the stack's foot is 55 blocks from that point (the unaided
   limit is about 75, STATE "Surface exhaustion"), and a rock is land: it recovers fatigue. With Surf the whole nest is open. The
   six rocks stand 34 from her, outside her trigger (12) and her settle radius (32).
3. **She wakes** when a player is within 12 of her (the stack's base is about 10 in radius, so touching the rock does it),
   by the residents' keeper, and sleeps again when nobody is within 32.
4. **Early is a mistake:** level 55 against caps of 45 and 50 at five and six badges. She can be fought on day one.
5. **The gate to catch her is the level cap, with no new machinery** (`data/level_cap.json`): a Pokemon over the thrower's
   cap breaks free from any ball, a Master Ball included; the cap is 55 at seven badges, so she holds from `gym7_cleared`.

## Mechanism order (CLAUDE.md principle 6)

Cobblemon native: Habitat Blocks for the colony and `spawnpokemonat` for the resident. Datapack and functions: the rock
(one `build` function) and the residents' keeper (`tools/resident_encounters.py` `resident_files()`, called as the northern
and far-south residents call it). Configuration: the level cap as the catch gate. Nothing new in code: no mod, no
scripting layer, no companion. The rungs above it do not suffice because nothing native builds a stack in the sea or keeps
one named Pokemon on a crown (the Ursaluna den, Greymane and the other residents are the same finding).

## State model

- **The rock** is world blocks: a re-export erases it, R9RK puts it back (before R9E, which sets the six Habitat Blocks in
  its rock).
- **The Gullmother** is one entity per server (tags `cobblers.res`, `cobblers.res.gullmother`, `cobblers.res_dormant`),
  and her clock is `#gullmother.gone` / `#gullmother.abs` on objective `cobblers.rkres`, in the world's scoreboard.
  When she is beaten, caught or killed she returns after **144,000 ticks (two hours of server time)**, never in front of a
  player (nobody within 48) and only with someone within 96.
- **Per player:** nothing is stored. The only per-player fact is the level cap the capture hook reads (RCT's own).
- **Late joiner / different order:** no flag, no sequence; anyone can meet her at any time, and whoever arrives
  with seven badges catches her. A friend who missed her finds her again within a session or two.
- **Dies or disconnects mid-fight:** a wild battle ends; she leashes to 16 blocks and settles asleep when everyone has gone
  (32). A player she beats becomes that claim's blackout guardian (the residents' decision): from then on the keeper only
  counts her and never touches her.

## Not verified (principle 18)

Nothing ran in a server. Assumed: that **activated Habitat Blocks spawn over water and rock** as designed (Driftmouth Isle's
are the same unverified shape); that the water birds with a `surface` position appear on the sea between the rocks; that a
**NoAI Dragonite on a 42-block crown plate** wakes, fights and settles as the other residents' do (EXP-053 is the same
question for the Ursaluna); that the **level-cap hook refuses** a throw (STATE "The level-cap trap" says no throw has been
seen); that the guano reads white at distance. The stack's silhouette was checked on ASCII slices only. Whether the spawned
Dragonite's four moves are sensible at level 55 is the Cobblemon default, unchecked.

## Collisions

- **Surf.** Dragonite is in `data/water_mounts.json` surf: a caught Gullmother lets a seven-badge player cross the
  Northlight strait unaided. That is late (the packet's gate is the ferry's) and arguably the reward, but it is a system
  consequence; the owner may prefer a different great one.
- **Pseudo-legendary supply.** One per two hours of server time, the same cooldown rule as every resident but longer.
- `tests/test_spawn_habitat_audit.py::test_prepare_runs_the_audit_right_after_the_spawns_compile` fails at baseline (a
  `training_grounds_audit` job sits between): not this unit's.
