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
| Stoneford (gym1) | 48 (12/7/9/20) | a masons' and rescue town; Rock types at work, and stone pretending to be something else | **The herbalist's new tree**; The Rhyhorn across the west lane; Waiting their turn at the kiln; Bath day at the animal pen; Three stones too many; The armorer's keys; Sitting for the sculptor; The temple's new statue |
| Viltri Quay (gym2) | 47 (11/6/10/20) | the lake's rescue port; freshwater Pokemon working boats, piers and nets | **Right of way**; Tenants of the rescue boat; The dam behind the library; Gone fishing; The lifeguard's chair; The Psyduck have the vegetable bed; The rain butt's tenant; Ugliest catch of the year |
| Highwire (gym3) | 43 (11/5/9/18) | the storm-relay town; all Electric types plus mountain birds | **Warming hands at the pylon**; The web on the corner; Not for sale; Knock knock; Practice behind the Mart; Waiting to be charged; The weathervane |
| Sunset West | 47 (12/6/9/20) | fishermen at the river mouth; sea species only | **Beached**; Waiting for scraps; The rock pool at low tide; Nobody wants them back; The bird on the forge; Applying for the job; Do not touch the fossil |
| Northlight | 47 (11/5/11/20) | the snowy research village; Ice types and night-sky Pokemon | **The sledging hill**; Out of the wind; Stuck to the lamp post; The observatory's night shift; Under the sled rack; The fire that will not catch; First in line for the ice; Waiting for the lights; Third snowman from the left |
| Steepside (tea_town) | 47 (11/5/11/20) | the tea terraces; Grass and Bug types, plus tea ghosts | **Tea for eight**; The queen holds court; Blown in; There were five yesterday; The smokehouse's second brew; Asleep in the leaf bins; Ripe by Sunday |
| The Displaced City | 42 (11/3/10/18) | a town rebuilt in a cavern; cave, ghost and fungus Pokemon | **Does anyone know this face**; The fairy ring; The king of the heap; The gate count; Standoff in the alley; Hung up the chimney; Two at the butcher's door; The best bed in the cavern |
| Bridgekeep (gorge_hamlet) | 15 (4/2/3/6) | a walled courtyard in the dunes; desert Pokemon | **The toll pits**; Shade for the elder; Somebody's sandcastle; Nobody planted it |
| Viltri Light | 6 (2/0/1/3) | a lighthouse over a dead estuary | **Waiting for the river**; The night watch |
| Merian Hut | 6 (2/0/1/3) | a cirque hut with a woodshed and a stable | **Who took the washing**; The cellar nobody asked for |

**More situations (2026-10-06, the owner: "towns want more happening").** Each town gained two to four hand-written
situations (fewer for the hamlet and the two outposts), listed after the originals above. The composition caps
situations at 0.43 of a town (0.35 + 0.08), so a full town holds at most 20 situation Pokemon: the new ones are small
(one to three Pokemon, often one with props: four chimney pots, a door queue in four towns, a garden), and some older
groups gave up a member (Lillipup, Ducklett, Krabby, Poliwag, Mareep, Voltorb, Cubchoo, Spheal, Combee, Exeggcute,
Yamask, Morelull, Trubbish, Duskull, Trapinch). The two outposts converted rather than added: Viltri Light's keeper's
Noctowl is now a situation on a mooring post, Merian Hut's step Bunnelby now digs a cellar by the woodshed. Highwire
stays at 43 because its middle is at the in-view limit (20 within 24 blocks); its vane went to the Pokemon Center's
ridge, since the Mart top already has the Pikipek. Checked: `ambient_idle.py build` against the orchestrator's built
packs (every town placed) and `ambient_composition_audit.py` (data 15 PASS, placement 4 PASS). Bombirdier, Frigibax
and Greavard were tried first and are in the ATM client-model subset; Cramorant, Froslass and Poochyena replaced them.
Nothing has been seen in game.

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
