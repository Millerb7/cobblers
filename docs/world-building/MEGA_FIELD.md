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

## 2. The earlier design, and what was built instead

**The design the owner refers to is `docs/world-building/SOUTHERN_RIFT_MEGA.md` section 13 (2026-09-27).** It agrees
with his message on every point it covers:

- Hostile Megas as the resource: *"a player will fight the mega mons I have roaming for resources, that they will then
  use to buy mega stones"* (`SOUTHERN_RIFT_MEGA.md:645-646`); the site has *"hostile roaming Megas"* (`:7`, section 6).
- A late-game farm, not free stones: *"I don't want mega stones being free, I want this to be a sort of late game
  farm"*; the currency is the raw `mega_showdown:mega_stone`, a finished stone is never dropped (`:647-649`).
- **Where: *"the southern Rift's two western zones, around (4090, 116, 5289) and (3738, 87, 5164) (the owner's
  coordinates). They look as if a world broke there and something powerful moved in: caves, Mega dens, broken houses
  half sunk, debris"*** (`:650-652`). Both points are inside the field of section 1: its inner arm and its western lobe.
- Levels: outer *"about 60 (the owner: 'if cap after gym 5 is 50 … lvl 60 or so, so it takes a team')"*, 15% a defeat;
  deeper 65-70, 25-35% (ASSUMED) (`:653-658`).
- Spent where: the raw stone buys a keyed stone at the Cutters in the gulch town, 2 raw stones plus a diamond
  (`:664-667`; `data/gulch_mine.json` `cutters.offer.raw_count` 2).
- Hostility: *"The owner wants Megas to attack on sight unless the player is 20 or more levels above them"*; Fight or
  Flight's `always_aggro_aspects` was set to the Mega aspects on staging; the 20-level exemption is not a config key
  (M-3b); whether an always-aggressive aspect overrides `light_dependent_unprovoked_attack` is open (M-3) (`:671-683`).
- **Held:** *"Both sites lie in the south-west arm, inside Victory Road's zone Z2, which RIFT_ZONES gates at 8 badges.
  Section 13 puts the farms after gym 6. The owner decides between carving a gym-6 zone out of Z2 and waiting for 8
  badges"* (`:706-709`; `RIFT_STATUS.md:264-268`, `:479-481`). No answer is recorded anywhere in `docs/`.

**What was built instead (2026-10-01).** Research commit `485e364` measured *"12 open-ground den sites across both
southern arms ... inside the arm polygons"*: `data/regions.json`'s `rift_south_west_arm` and `rift_south_east_arm`
subregions, 0.54 and 0.61 km2 of painted cover that take in the plateau round the basin. Seven were placed (`70dcd65`,
unparked `5198d14`; `gulch_mine.json` `farms`, `farms_why`), B4 dropped their zones (`cbcff87`;
`docs/DECISION_QUEUE.md:24`), and R9MD dressed them as lairs (`data/mega_dens.json`, `MEGA_DENS.md`). **None of the
seven is in the field, or in the basin at all** (measured against the polygon and `derived/rift_sculpt/basin.npy`): all
stand on high ground at y121-148, 163 to 1,133 blocks from the nearest owner coordinate (Garchomp, (4248, 5328), is the
163). That is the "spawn one randomly in the world" the owner objects to. The misreading was the name "south-west arm":
`RIFT_ZONES.md:21-45` uses it for the BASIN arm Victory Road runs up; the den search used the subregion of that name.

**What the new design supersedes.** The seven `farms` and their `farms_why` (`farms_grid` stays as the dens' bound),
and the seven `data/mega_dens.json` lairs that dress them. Kept unchanged: the gulch's zone and gate, the Cutters, the
drop roll, the two Cutting Floor Megas, `drops`, the keeper. B4 ("no zone on the open dens") is not contradicted: the
field declares no zone of its own (section 4).

**Two findings the owner must see.**

1. **The field is inside Z2 (8 badges) today.** `data/rift_zones.json` `zones.z2.boxes` cover 370,182 of the field's
   473,215 columns (measured); the rest is the floor south of the owner's traced `hidden_rift_cavern`. Unless Z2 is
   cut, the field is an 8-badge farm (level cap 60, `docs/mechanics/LEAGUE_LEVEL_CAP.md` section 2), not the gym-6
   one section 13 wrote. This is the 2026-09-27 held question, unchanged.
2. **Victory Road walks through the field.** `data/route_paths.json` `victory_road` crosses the lip at the south-west
   tip and runs north-east across the western lobe and up the stem (white line). Aggressive Megas beside the critical
   path change Victory Road. Section 4 keeps every den off the walked line; whether the owner wants that is his call.
