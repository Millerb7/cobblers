# Long mine networks (eastern half)

The owner, 2026-10-21: "with no caves people wont be incentivized to mine at all ... really really large and long mines every so
often in the world ... a few hunderd block caves wont be enough for 10 people". Three abandoned-mine networks, each 4,400 to 4,700
blocks of drift on 7 or 8 levels, all east of x4160. **Planned, generated and audited offline. Nothing applied to any world; nothing seen in game.**

| id | name | adit(s) | nearest town | levels (floor y) | drift | stopes / inclines / shafts |
|---|---|---|---|---|---|---|
| mn_craters | The Old Craters Drift | (6616, 5456) west | mining_town, 260 | 8: 101 down to -11 | 4,507 | 8 / 9 / 7 |
| mn_gorge | The Hollow Seam | (6888, 3856) and (7000, 3836) north | gorge_hamlet, 516 | 7: 70 down to -26 | 4,642 | 7 / 8 / 6 |
| mn_ridgeback | The Ridgeback Workings | (4908, 1192) south | gym4_town, 700 | 7: 69 down to -27 | 4,447 | 7 / 8 / 6 |

Pictures: `MINE_NETWORKS_EAST.png` (where they are), `MINE_NETWORKS_CRATERS.png`, `_GORGE.png`, `_RIDGEBACK.png` (drifts coloured by level).

## Chain

`data/mine_networks.json` -> `tools/mine_networks.py build` -> `build/datapacks/cobblers_mine_networks` (one function per 128-block tile,
`index.txt`) -> `tools/mine_networks_audit.py` (reads the BUILT functions) -> `tools/reapply.py` step `R9MN`.
`python tools/mine_networks.py site x0 z0 x1 z1` lists adit candidates; `tools/mine_networks_map.py` draws the pictures.

## What a network is

A timbered adit (spruce sets, hanging lantern) into a hillside, a main haulage drift 3 wide and 4 tall with timber sets every 5 blocks, a
cobblestone bed, rails and a lantern every third set; crosscuts through the main and long side drifts 3 wide and 3 tall (sets every 8);
stopes 6 tall with 2x2 pillars left, sized for six players; stair inclines (16 blocks down) and ladder shafts between levels 16 apart; dead ends.
Vanilla ore in the exposed walls and roof as veins running back into the rock (coal, copper, iron, redstone, lapis, gold, diamond: the
minerals the bank buys), richer on deeper levels and farther from the adit, deepslate variants below y0. Every number is in the data
(`ores.table` holds the odds). Everything is a hash of `seed` and the network id.

## Rules, and where each is enforced

Ground only from `tools/ground.py` (rounded heightmap). At least 8 blocks of ground over every written cell except the adit's first
`exempt` cells (28-33 at most, authored per adit). No carved cell within 12 blocks of the sea, a lake basin, a river corridor or a waterway.
32 blocks from every authored x/z, box and short polyline in `data/*.json`. 2-thick shell: every function carves, replaces `water` and
`lava` with stone round every carved box, carves again. Tile functions pass `function_limits.check_lines`. The spawn policy has an entry
scoped to `mine_networks` for rail and coal, iron, redstone and diamond ore (`data/spawn_block_policy.json`).

## Crews

Twelve trainers work each network (miners, a foreman, a Shift Boss at the deepest stope): `MINE_CREWS.md`, `data/mine_crews.json`, `tools/mine_crews.py`. `data/mine_crew_trainers.json` is skipped by this generator's and the audit's authored-place scan (`SKIP_FILES`), or the layout would avoid its own crew.

## Not checked

Water, lava, caves or structures that no data file carries (the shell covers fluid within 2 blocks of a carved box only); that the rock is
rock; routed legs and painted water (`derived/routes`, `build/paint`, generated, absent in a fresh checkout); behaviour in game. Needs: apply
to a disposable snapshot world, walk one network end to end, and see whether the coal, iron, redstone and diamond ore and the rails draw
spawns along thousands of blocks. The ore counts (about 3,800 to 3,950 blocks a network) are a first setting, not a balance decision.
