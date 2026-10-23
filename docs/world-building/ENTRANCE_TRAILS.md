# Trails, signs and guides to the caves and mines

Status: **built and audited offline on 2026-10-23; nothing is applied to any world, nothing seen in game.**

The owner, 2026-10-22: "i think if its near a town, add a path to it" and "an npc to give a waypoint to a mine would be cool."
The six places (`data/cave_systems.json`: the Old Seams, the Hollow Reach, the Frostpeak Deeps; `data/mine_networks.json`: the Old
Craters Drift, the Hollow Seam, the Ridgeback Workings) have entrances 80 to 700 blocks from a town, with nothing to find them by.

## What was made

`data/entrance_trails.json` is the table; `tools/entrance_trails.py` builds `cobblers_entrance_trails` (the trails, one function
each, run by reapply step R16T) and `cobblers_entrance_guides` (the waypoint offers, kept at play time because a dialogue calls
them); `tools/entrance_trails_audit.py` reads the written functions back and recomputes every property by its own code.

| trail | from | to | walk | lanterns | sign (front / back) |
|---|---|---|---|---|---|
| `trail_old_seams` | Pallet's cross street, east end (1522, 5292) | `seams_oak_s` (1806, 5302) | 279 | 11 | Old Seams, cave 280 blocks / Pallet Town |
| `trail_hollow_reach_steepside` | Steepside's terrace road, north end (2600, 3486) | `reach_tea_n` (2486, 3410) | 136 | 5 | Hollow Reach, cave 140 blocks / Steepside |
| `trail_hollow_reach_stoneford` | Stoneford's north avenue, north end (1756, 3520) | `reach_brock` (1930, 3490) | 180 | 7 | Hollow Reach, cave 180 blocks / Stoneford |
| `trail_craters` | Fossick's bowl walk, north end (6636, 5612) | `mn_craters_a1` (6616, 5456) | 161 | 6 | Craters Drift, mine 160 blocks / Fossick |
| `trail_gorge` | Route 7 at (6608, 3855), north of the river bridge | `mn_gorge_a1` (6888, 3856) | 284 | 11 | Hollow Seam, mine 290 blocks / Route 7 |
| `trail_ridgeback` | Greenhollow's east lane (4392, 1554) | `mn_ridgeback_a1` (4908, 1192) | 686 | 28 | Ridgeback Workings, mine 690 blocks / Greenhollow |

Walks are the audit's shortest path along the written centre line (Dijkstra over 8-connected centre cells); the sign says the
nearest ten. A trail is a 3-wide ribbon on the heightmap's ground (`dirt_path` centre, `gravel` and `coarse_dirt` flanks),
vegetation cleared four blocks up, a spruce-fence post with a lantern on it every 24 blocks beside it, and a two-faced sign near
its start, in the format `tools/signposts.py` writes (front faces the traveller leaving the start).

**Two choices the owner may want to change.**

- *The Hollow Seam's trail starts on Route 7, not in Bridgekeep.* The adits stand north of the gorge's river and Bridgekeep
  south of it; no open line joins them without a bridge, and the trail bridges nothing (it refuses a line that must cross water).
  Route 7 is 246 blocks from the first adit (`data/route_paths.json`, at (6645, 3895), which is on the river bridge), so the trail
  forks off the last dry route cell north of the bridge and the sign stands at the fork. Bridgekeep's guide still offers the waypoint.
- *The Frostpeak Deeps has a guide and no trail.* Its four mouths stand 81 to 85 blocks from the Frostpeak shrine, a summit site,
  and 1,244 blocks or more from the nearest town (Highwire): past the 800 blocks a trail is laid for. Highwire's guide offers the
  southern mouth (`peak_s`). A trail from the Frostpeak survey camp (688, 688), 190 blocks from `peak_s`, was not tried.

Each system gets one trail to one entrance (two for the Hollow Reach, one from each of its towns). The other entrances have no
trail: the Old Seams has two more, the Hollow Reach four, the Hollow Seam one. No junction sign was added on a route for the
entrances that stand 100 to 200 blocks off one (`reach_r2`, `reach_r2n`, `seams_mansion`).

## The guides

One resident of the nearest town per system. Talking to them: a line of flavour, then a choice "Mark it on my map." that runs
`cobblers:guides/<guide id>` as the player, which prints one chat line with a Xaero's share (`xaero-waypoint:<name>:<initials>:x:y:z:
<colour>:false:0:Internal-overworld-waypoints`, the form of the "Next gym" offer, `tools/progression_pack.py xaero_share`) to the
entrance's surface. The player clicks it to add the waypoint. Repeatable: the conversation offers the mark again.

| guide | town | goes to | seat | skin |
|---|---|---|---|---|
| Wren Tolliver, an old seam-finder | Pallet | `seams_oak_s` | (1514, 119, 5296), heightmap ground | `hiker_alan_00b9` |
| Corwin Hale, a surveyor of the Reach | Stoneford | `reach_brock` | (1744, 139, 3604), plaza | `scientist_beau_0154` |
| Hjalmar Skarn, a mountain guide | Highwire | `peak_s` | (1664, 175, 1388), plaza | `hiker_nob_00b7` |
| Pell Dacey, an assayer of the Drift | Fossick | `mn_craters_a1` | (6602, 138, 5690), plaza | `scientist_connor_0150` |
| Marit Doyle, a bridge-keeper | Bridgekeep | `mn_gorge_a1` | (6803, 114, 4363), plaza | `fisherman_andrew_00e9` |
| Dorsey Quill, an ore carter | Greenhollow | `mn_ridgeback_a1` | (4332, 111, 1538), plaza | `hiker_brice_00ba` |

Wired through the existing mechanism, by id: `data/dialogue.json` (six `dlg_entrance_guide_*`), `data/quests.json` (quest
`ambient_entrance_guides`, six `mark_*` transitions, each running the guide function and setting the cursor), `data/progression.json`
(six cursor fields), `data/npc_seats.json` (six seats, placed by R17N), `data/npc_looks.json` (six looks). The skins are file
names the trainer records already use, chosen from their names and the role without seeing the textures, and none is another
NPC look's skin.

## The player site

`docs/player/region-map.html` gains a "Caves and mines" layer (orange dots, one per entrance, labelled by system) and a section with
each place's entrances (x, z, ground y), depth, how to find it and the surface wild levels at its entrances
(`tools/entrance_sites.py`; `tools/player_guide_map.py`). It names no guide (the story files are not public,
`tests/test_player_site_leaks.py`) and lists no underground spawns.

## Verified / not verified

Verified offline (2026-10-23): the audit passes on the built pack (the walk, the ground, water, buildings, lanterns, signs, blocks,
function limits); `tests/test_entrance_trails.py` mutates the generator's functions and the audit catches each; the six
conversations compile; `tools/npc_seats.py check` is clean for the new seats; `tests/test_entrance_guides.py`.

**Not verified:** anything in a running game. The audit's check against other built packs' writes did not run here (a fresh
worktree has none); the planner kept clear of every point, box and short line in `data/*.json` and the placements' origins, and
the audit used the placements' recorded size, else 24 blocks from the corner, but trees, ponds and rock the world holds and no
file carries are cleared or crossed without a check. Whether the signs read well, the lanterns light the way, the clicks work and
the NPCs stand where the seat rules say are the first things to see: `python tools/reapply.py` R16T and R17N, then
`python tools/npc_seats.py verify` and a walk from each start.
