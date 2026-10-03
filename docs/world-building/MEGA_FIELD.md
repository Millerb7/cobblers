# The Mega field: the south-west Rift basin as one hostile Mega farm

**Status: step 1 of 4 (the area) written 2026-10-03; not built, not in any world.**

The owner, 2026-10-03, on a minimap screenshot of the Rift: *"everywhere in the red inside the rift should be the mega
area, not just spawn one randomly in the world. the idea is an aggressive and hostile resource farm as discussed in
some chat a while ago. you would go in and fight high level megas that in theory should require more than one mon to
kill and get a reward to spend in the big town next to this area in the rift."*

The screenshot itself was not seen by the session that wrote this; it was relayed as a description (two connected
lobes of Rift floor, a large western lobe and a narrower inner arm running south between two dark ravines; the cursor
at X 3967 Z 5037; the big town to the north-east across a pale line). **Everything below is measured from data and
the canonical heightmap, and the owner confirms the area on the picture.**

## 1. The area

![the Mega field](MEGA_FIELD.png)

`MEGA_FIELD.png` (`python tools/mega_field.py map --out docs/world-building/MEGA_FIELD.png`): the heightmap, the field
in red, the gulch zone in blue, the Cutters' square in cyan, Victory Road's walked line in white, the owner's cursor and
his two section-13 coordinates in yellow, the seven 2026-10-01 dens in orange.

| What | Value | Source |
| --- | --- | --- |
| Polygon | `data/gulch_mine.json` `mega_field.polygon`, 216 vertices, **473,215 columns**, bbox x 3541-4355, z 4377-5401 | `python tools/mega_field.py trace` |
| Rule | the Rift sculpt's lip ring (`derived/rift_sculpt/plan.json` `ring`), outset 3 along the rim like the gulch zone, from the gulch zone's south-west end (ring 3430, (4195, 4929)) away from the gulch round the inner arm and the south-west basin, up the west wall to ring 6902 (4120, 4379), straight across the stem (319.7 blocks) to the gulch zone's north-east end (ring 2574, (4351, 4600)), and back along the gulch zone's own closing line | `mega_field.trace` |
| Overlap with the gulch zone | 0 columns: the two share the gulch's closing edge | measured |
| The owner's cursor (3967, 5037) | inside; ground y117 | `tools/ground.py` |
| SOUTHERN_RIFT_MEGA.md:650's two sites (4090, 116, 5289), (3738, 87, 5164) | both inside; ground y116 and y87 | `tools/ground.py` |
| The town north-east of it | the Cutters' Gulch: square (4278-4338, 4818-4878), the Cutters' workshop at (4288-4312, 4896-4911), inside the gulch zone | `gulch_mine.json` `town` |
| The owner's traced region here | `hidden_rift_cavern` (`data/rift_regions.json`, 118,802 columns, bbox 3658-4125, 4574-5079) lies inside the field's western lobe | `rift_deep.region_mask` |

**Match with the description.** The basin south-west of the gulch is exactly two connected lobes: the large western
lobe (x 3550-4000) and an inner arm (x 4030-4170, z 5050-5370) running south between two tongues of high ground. The
Cutters' Gulch lies north-east of the cursor, across the gulch's closing line. The "pale line running NW-SE" is not
identified from data (candidates: the gulch's rim, Victory Road's path); this does not change the area.

**What the owner must confirm on the picture.** (a) Where the field stops up the stem: the cut at the narrowest
crossing from the gulch line's north-east end (z about 4380-4600) is this tool's choice; the map did not show it.
(b) The field includes the Rift floor under **Victory Road's walked line** (white): see section 2's findings.
