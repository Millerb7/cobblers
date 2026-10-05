# Town Pokemon by composition: town author A's ten towns

The owner's brief (2026-10-05, `data/ambient.json` `composition`) said the town Pokemon "read as paste". These ten
files replace that roster with Pokemon arranged on purpose: working Pokemon, pets, placed Pokemon and situations, in
`data/ambient_towns/<settlement>.json`. The other ten towns are town author B's.

**How they were checked (2026-10-05):**

- `tools/ambient_idle.py compose` on the orchestrator branch: all ten compose with every rule held.
- The data layer of `tools/ambient_composition_audit.py`: 14 checks pass. One fails, `scope_files`, and only
  because the other author's ten files are not in this worktree.
- A cross-read of both authors' files. No species is in more than 2 towns. The highest roster overlap between two
  towns is 0.17. No two situations share a title or the same species and props.
- Nothing has been tested in game.

**Where positions come from:** `derived/towns/<s>_plan.json`, `<s>_placement.json`,
`derived/plaza_centres/<s>.json`, and `tools/ground.py` (rounded) through `tools/ambient.py`'s Site. The Displaced
City uses its own cavern floor (`for_settlement`). Every `y` is the feet y.

**Species rule:** each species appears in only one of these ten towns, 242 species in all. None is a client doll.

| Town | Total (work / pets / placed / situations) | Character | Situations (unique one first) |
|---|---|---|---|
| Stoneford (gym1) | 44 (12/7/8/17) | a masons' and rescue town; Rock types at work, and stone pretending to be something else | **The herbalist's new tree**; The Rhyhorn across the west lane; Waiting their turn at the kiln; Bath day at the animal pen; Three stones too many |
| Viltri Quay (gym2) | 44 (11/6/9/18) | the lake's rescue port; freshwater Pokemon working boats, piers and nets | **Right of way**; Tenants of the rescue boat; The dam behind the library; Gone fishing; The lifeguard's chair |
| Highwire (gym3) | 42 (11/5/9/17) | the storm-relay town; all Electric types plus mountain birds | **Warming hands at the pylon**; The web on the corner; Not for sale; Knock knock; Practice behind the Mart |
| Sunset West | 44 (12/6/9/17) | fishermen at the river mouth; sea species only | **Beached**; Waiting for scraps; The rock pool at low tide; Nobody wants them back |
| Northlight | 42 (11/5/9/17) | the snowy research village; Ice types and night-sky Pokemon | **The sledging hill**; Out of the wind; Stuck to the lamp post; The observatory's night shift; Under the sled rack |
| Steepside (tea_town) | 42 (11/5/9/17) | the tea terraces; Grass and Bug types, plus tea ghosts | **Tea for eight**; The queen holds court; Blown in; There were five yesterday |
| The Displaced City | 42 (11/3/10/18) | a town rebuilt in a cavern; cave, ghost and fungus Pokemon | **Does anyone know this face**; The fairy ring; The king of the heap; The gate count; Standoff in the alley |
| Bridgekeep (gorge_hamlet) | 14 (4/2/3/5) | a walled courtyard in the dunes; desert Pokemon | **The toll pits**; Shade for the elder |
| Viltri Light | 6 (2/1/1/2) | a lighthouse over a dead estuary | **Waiting for the river** |
| Merian Hut | 6 (2/0/2/2) | a cirque hut with a woodshed and a stable | **Who took the washing** |

## What could not be sited, and why

- **Pets in the Displaced City (3) and Merian Hut (0).** These towns have only one NPC that the apply places (the
  Displaced City's mason) or none at all (Merian Hut). Sunset West has no seated NPC, so all its pets belong to the
  market keepers.
- **No worker stands on a square that was cut below the heightmap** (Viltri Quay, Sunset West, Northlight). Site's
  `y` there is the uncut ground, so the worker would float a block above the paving. This is a fault in
  `tools/ambient.py` Site, not in the data.
- **Nothing is placed on the gyms, the field station, the observatory or the lighthouse.** None of them is a
  placement building. Where a Pokemon was wanted there, it has a measured `at` (the Highwire Helioptile, the Viltri
  Light Clobbopus). The same goes for two templates with no free porch (Stoneford's Nacli, Sunset West's Clamperl).
- **Sleeping.** Only the generator's eight day-sleepers can be posed asleep. Galvantula is the only sleeper here.
  The Geodude and Tentacool were changed to `still`.
- **Workers are well over `rules.per_town`.** That rule allows 2 carriers and 4 stationary workers per town; the 30%
  working share needs 11 or 12 in a gym town. The generator now checks the composition share instead.
- **Kept worker ids.** `brock_stone_carrier`, `surge_magnemite_lamp`, `tea_oddish_picker` and
  `northlight_log_carrier` keep their ids. Northlight's carrier is now a Beartic, because the Timburr went to Viltri
  Quay. Stoneford's bench Machop is now a Sawk, with a new id.
