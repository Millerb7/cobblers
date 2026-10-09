# Route 4's middle: the thaw road

Gap #1 of `docs/world-building/WORLD_SWEEP_2026-10-09.md`: Route 4 is 3,453 walked blocks with six trainers and
nothing else, and the event pattern of Routes 1-3 stopped at Route 3. This is four events and one find along walked
1085-2263 (cells B3-B4, band 3, cap 35), built by `tools/route4_events.py` from the hand-authored design
`data/route4_events.json`. **Written in a worktree, offline: nothing here has run in a world.**

## The chain, west to east

| # | Site | Where (measured on `tools/ground.py`) | What the player does | Different from Routes 1-3 because |
|---|---|---|---|---|
| 1 | Headwall camp | (2500, 1278), y162, 18 blocks off the walked line at walked 1089 | Reads the rockfall scar and the snapped lead, then answers Hallam's riddle (three answers, one right). She pays 4 Oran Berries. | The first deduction with a wrong answer; mountain, not meadow |
| 2 | Steam hollow | (3110, 1500), y107, 39 off the line at walked 1903 | Reads prints, a warm pool in a ring of moss, a pink petal; follows the prints east (they cross the road) | No person: the place is the clue; green in a white floor |
| find | Strayed load | (3262, 1450), y115, 104 off the line | A barrel under a red pennant at the east wall's foot: 2 Sitrus, 2 Pecha (advancement cache, ADR-002) | Seen from the road, never signed |
| 3 | The old summit road | trail from the walked-2100 cell (3252, 1622) to the gate, 264 blocks, six numbered milestones 5 to 0 | Walks it. A zone at each stone sets the player's own HUD line ("four stones to the top"). The 0 stone says THE SUMMIT IS BELOW. ASK AT THE GATE. | A walk, not a puzzle: the count is the event; no prop but the last stone |
| 4 | The thaw gate | the Displaced City's gate (3033, 1714); the tunnel mouth (3035, 1700), 235 blocks from the line | Oriel, a resident, and Biscuit the Gogoat (a per-player actor) in a drift of petals running from the mouth into the snow. Never-Melt Ice, a cherry sapling, 3 Sitrus. | Payoff: warm wind and `cherry_leaves` particles out of a hill, and the city's stair lit below |

**Ties to the Displaced City.** The leg passes *over* the city: the walked line's nearest cell to the city's centre column
(3366, 1755) is (3356, 1765), **14.1 blocks away** at walked 2287, 57 blocks over the summit square (ground y103, the square y46).
Nothing on the surface said so. The road's stones lead the other way, to the gate the cavern plan already authored.
**Disagreement found:** `docs/STATE.md` ("Leg 4 waypoint ... the Displaced City stays at least 250 ... off the critical
path") and `data/towns.json` (`distance_from_critical_path_blocks` 287) predate the current `data/route_paths.json`; the city
is 235 blocks from the line at its *entrance* and 14 at its *middle*. Both statements stay true of the gate; neither of the
city.

## Mechanism (principle 6)

Rung 5, datapack, throughout; nothing above it. Blocks: a function pack, `build/datapacks/cobblers_route4_events`, one
function per site, re-applied by **R12R4** (after R12). People: scenes (props, a per-player actor, zones, effects, NPCs) in
`data/scenes.json`, run by `cobblers_scenes` and placed by R17 *without a list of ours* (R17 reads every scene). One quest,
`evt_route4_thaw_road`, because `tools/validate_data.py` lets a quest read only its own fields; the finale reads the earlier
events' flags to change who greets the player. Rewards: `grant_reward_once` for the two NPCs, an advancement cache for the find.
Why not less: Routes 1-3 are the same mechanism; there is no rung below that does a per-player riddle, a per-player HUD line and
a per-player mule. Why not more: no script, no companion, no mod was needed.

## State model (multiplayer, principle 12)

Everything is per player (Cobblemon player data via the dialogue compiler), and **no event reads another's flags to unlock
itself**: a player who reaches the gate first gets the gate; one who never reads a stone loses nothing; the finale's reward does
not depend on the earlier events, only its first line does (four greetings). The Gogoat's place is a function of the owner's
`gate_done`, so a restart, a death or a disconnect loses nothing (the scene runtime's checkpoint). The two NPC grants are keyed
`<quest>:<reward>:{player_uuid}` with their own claim fields; the find is once per player by advancement.

## Economy

No new money source: cash 0 per hour. Items only: 4 Oran, 2 Sitrus + 2 Pecha, 1 Never-Melt Ice, 1 cherry sapling, 3 Sitrus (13
items, one held item); none is in the Bank's buy list (`data/bank.json` `buys`, 13 lines of minerals), so `data/markets.json`
`income_basis` (trainer income only) is untouched. No Exp. Candy, IV candy, Rare Candy, Lucky Egg, stone, TM or Bottle Cap
(`tests/test_route4_events.py` fails on them). Never-Melt Ice is one a wild pool already holds at 5% (`data/spawns.json`), so it is
not a gate item. Biscuit is level 34 against the band's 35, an actor that cannot be caught.

## Not done / assumed

- **ASSUMED, not seen:** the pool does not freeze and the moss does not snow over, because eight invisible `minecraft:light` blocks (five at the pool, three on the gate's belt)
  keep block light at 10+ (the vanilla snow/ice rule); the milestones read well; the NPC models are the shared `cobblemon:standard`.
- **ASSUMED:** the tunnel mouth is at (3035, 1700) by the formula `tools/cavern_plan.py` uses (`derived/cavern/plan.json` is not in a
  worktree); nothing is written within 3.5 blocks of it, and the belt starts 4 blocks south of it. The cavern pack's open cut runs
  north-east of the mouth; nothing here does.
- The Merian ice fishing lodge (being built tonight) was not read: every block is 400+ blocks from the hut, `tests/test_route4_events.py`
  keeps it above 150.
- Flower species (Combee, Cutiefly, Comfey) may spawn near the petals and cherry leaves where a pool carries them
  (`data/spawn_blocks.json`); that is Cobblers' pools' call, declared in `route4_events.SPAWN_OK`.
- The hoofprints are coarse dirt and will snow over; the red pennant and the props carry the clue.
- Not in STATE.md yet (the owner's session reconciles it).
