# Mine crews

The owner, 2026-10-22: "for the economy we are diving back into the same mistake adding trainers people may never see... i like th emines idea thats good add trainers there". So the trainers go where players go to mine, and none on routes. Twelve in each of the three long mine networks (`MINE_NETWORKS.md`): miners, a foreman and a Shift Boss at the deepest stope. **Planned, generated and checked offline. Nothing applied to any world; nothing seen in game.**

| network | band | crew | Shift Boss (deepest stope) | expected purse, once per player |
|---|---|---|---|---|
| mn_ridgeback, The Ridgeback Workings (near gym4_town) | 27 to 34 | 10 miners, foreman Hale Corbin (level 5 stope) | Maren Tull, level 7, five at 33-34 | about 30,500 |
| mn_gorge, The Hollow Seam (Bridgekeep, between gyms 6 and 7) | 41 to 48 | 10 miners, foreman Ada Pellam (level 5 stope) | Ilsa Draycott, level 7, five at 47-48 | about 57,900 |
| mn_craters, The Old Craters Drift (Fossick) | 45 to 52 | 10 miners, foreman Hale Voss (level 5 stope) | Maren Kell, level 8, five at 50-52 | about 70,400 |

## Chain

`data/mine_crews.json` (authored: slots, teams, lines) -> `tools/mine_crews.py write` -> `data/mine_crew_trainers.json` (record and seat together, the shape of `data/compact_route_trainers.json`) and the 36 `quest.<id>.defeated` fields in `data/progression.json` -> `tools/route_trainers.py` (rctmod trainer, mob, dialog, defeat advancement, Challenge copy, cycle) and `tools/reapply.py` R17 (summon, through `route_trainers.placements()`; **no new step**, R9MN carves the mines earlier in the same run).

## How a seat is chosen

A slot names a level and either a **walk distance from the adit** along the main line or the **stope** of that level. `tools/mine_crews.py` picks from the networks' own geometry (`tools/mine_networks.py` Layout and Model, grown on the canonical heightmap, never on a world):

- main line: a cell of an adit or main run whose 7 x 7 neighbourhood holds no air outside the run's three-wide band (a straight tube: no junction, incline, shaft or stope mouth within three blocks), at least six cells from either end of the run, on a **side lane** (the rail and its bed take the middle one), nearest the slot's walk distance. It faces toward the adit, the way a player comes in, with eye contact and sight 7.
- stope: a free cell with all eight neighbours open, five clear cells toward the entry, nearest the slot's depth and lateral offset, sight 10.
- 20 blocks or more between any two seats.

## How it is checked

`python tools/mine_crews.py check` replays the BUILT functions (`build/datapacks/cobblers_mine_networks`, through `tools/mine_networks_audit.py read_pack` and `replay`) and imports none of the generator's geometry: air at the feet and head, a floor that was not carved, no rail under the seat, five open cells ahead, two walkable cells left across the way (a 3-wide drift keeps its other two), eye contact, quest field declared, band, Challenge rule, and, when the Cobblemon 1.8 jar is on the machine, every species' type and every move against its learnset. `tests/test_mine_crews.py` runs it on a fresh build and mutates the GENERATOR (the lane, the yaw) to prove it bites.

**A fault found while building this:** `tools/mine_nets_world.py` and the audit treat every x/z any `data/*.json` carries as an authored place the networks keep 32 blocks from. The seat file is such a file, so once it existed each network avoided its own crew and regrew a different layout (the main-line cells disappeared). `mine_crew_trainers.json` is now in both `SKIP_FILES`, like `mine_networks.json`.

## Not covered

- The world: whether a seat's cells are air in the running game, whether a natural cave, a donor structure or a mod block shares the cell, whether rctmod summons and pins a trainer underground.
- No first-win prize. The design's Shift Boss prize (`docs/mechanics/ECONOMY_V3.md` B4, 4 diamonds or a tier TM) needs the once-per-player give B2 describes, which does not exist; the Boss pays money only.
- **The economy model.** CobbleDollars pays 0.28125 * S^2 a win (S the losing team's level sum), which is what `python tools/mine_crews.py purses` prints. These 36 are not in `tools/income_model.py`'s legs, so `data/markets.json` `income_basis` and the economy audit do not count them. Measured against that basis, Ridgeback's 30,500 is about 1.9 times the whole badge-3-to-4 leg (34,991 - 18,576 = 16,415), the Hollow Seam's 57,900 is about 1.3 times the badge-6-to-7 leg (44,198) and the Craters' 70,400 about the badge-7-to-8 leg (68,505). Trim team sizes in `data/mine_crews.json` if that is too much; the owner decides.
- The crews are eye-contact fights on the main line: a player walking to the deepest level meets all of them once.
