# Victory Road's ten fights, and the League's five

Written 2026-09-30, from `docs/world-building/RIFT_STATUS.md` items 2 and 3 of BUILDABLE NOW.
Two things were authored but unplaced: ten marked stands in Victory Road with nine teams, and
five League teams with nowhere to stand. This is where they go and why.

Data: `data/vr_trainers.json`, `data/league_trainers.json`.
Generator: `tools/route_trainers.py` (extended, not replaced).
Pack: `build/datapacks/cobblers_trainers` — the one that generator already emits. A sibling pack
was not made: these are the same kind of record, read by the same mod, pinned by the same cycle
function, and `tools/reapply.py` R17 already places whatever `route_trainers.placements()`
returns.

## A. The climb

The mouth is (3560, 1, 3064), where the Windward Deep's north face meets its floor. The exit is
(3656, 89, 2486), a ravine onto the League's apron, entered from its foot at (3656, 64, 2566).
88 blocks of climb; 713 cells of walked route between them.

### Where the seats come from

Not from a world, and not invented. `tools/vr_caves.py` `place_fights()` already carves ten
blackstone stands into the cave and records them in its own plan (`derived/vr_caves/plan.json`,
key `stands`). Those ten blocks are the physical furniture of the fight; the seats here are the
air above them. This also settles the disagreement `docs/STATE.md` records — "Full `--check`
fails on Victory Road's pins ... whose ten fights stand where `tools/vr_caves.py` places them
along its walked route, not at those pins" — in favour of the cave model. Any pin that disagrees
is the thing that is wrong.

### The spacing rule: by progress, not by distance

`place_fights()` spaces the ten at **even route index**, not even distance:

```
idx = lo + (hi - lo) * (m + 0.5) / 10,   lo = 4% and hi = 94% of the 713-cell route
```

then steps to the nearest cell along the route that is standable, outside the rest station's box,
and at least `min_apart` (40) from every stand already placed.

The result is even in progress and uneven in blocks, which is the point. Ten fights over an
88-block climb is a pacing problem: a braided cave's shortest path doubles back on itself, so
even spacing in blocks would bunch fights wherever the route folds and leave the long straight
galleries empty. Spacing by progress puts one fight every ninth of the way up however the route
wanders.

The rest station at (3606, 23, 2835) is not the halfway mark. `place_fights()` refuses any stand
within 3 blocks of its box (x3606-3620, z2835-2849), and the route crosses it at about 44% of the
climb, between stands 4 and 5. Five and five is an accident of the route, not a design.

### The ten

| # | id | seat | yaw | progress | gap | climb | what makes it unavoidable |
|---|---|---|---|---|---|---|---|
| 1 | `route_09_trainer_01` | 3563, 2, 3009 | 3 | 0.084 | 55.1 | +1 | 55 blocks inside the mouth, the one way in from below; the drowned low caverns funnel every climber onto it |
| 2 | `route_09_trainer_02` | 3597, 8, 2985 | 55 | 0.174 | 42.0 | +6 | on the route, in the first long gallery out of the drowned band; the lit ring fills the gallery's width |
| 3 | `route_09_trainer_03` | 3604, 17, 2928 | 7 | 0.264 | 58.1 | +9 | on the route, on the lit lip between the Slagworks' lava pools, which the route threads |
| 4 | `route_09_trainer_04` | 3620, 19, 2880 | 18 | 0.353 | 50.6 | +2 | on the route, where the gallery narrows out of the Slagworks' core cavern |
| 5 | `route_09_trainer_05` | 3616, 25, 2822 | -4 | 0.443 | 58.4 | +6 | on the route, at the trench step just above the rest station |
| 6 | `route_09_trainer_06` | 3607, 31, 2766 | -9 | 0.534 | 57.0 | +6 | on the route, on the Bloom's moss shelf, the only dry footing across it |
| 7 | `route_09_trainer_07` | 3621, 42, 2716 | 16 | 0.624 | 53.1 | +11 | on the route, in the Raw Tear's approach gallery, which carries no branch |
| 8 | `route_09_trainer_08` | 3642, 48, 2673 | 26 | 0.714 | 48.2 | +6 | on the route, inside the Abandoned Cut, between the rail line and the spoil heap |
| 9 | `route_09_trainer_09` | 3641, 55, 2614 | -1 | 0.804 | 59.4 | +7 | on the route, in the Cut's upper hall where it turns for the exit ravine |
| 10 | `route_09_trainer_10` | 3655, 65, 2564 | 16 | 0.893 | 52.9 | +10 | **geometry**: 2.4 blocks from the exit ravine's foot (3656, 64, 2566), inside the 11-wide shaft `data/vr_caves.json` names as the only opening onto the League's apron |

`gap` is blocks from the previous stand (from the mouth, for stand 1): 42.0 to 59.4, never even,
always at least `min_apart`. `yaw` faces each trainer back down the climb, at the player coming
up. Every one carries `forceBattleOnSight` at 7 blocks — one more than the 6-block lit ring
`place_fights()` burns into the floor around each stand, so a player who can see the lit floor is
already in the fight.

**Not verified.** `data/vr_caves.json`'s guarantees say in terms: *"There is no path."* The
network is braided on purpose (`tunnels.loops` 0.28) and only reachability is proven. Stands 1
and 10 are unavoidable by geometry; the middle eight are unavoidable only in the sense that they
stand on the shortest way through and catch anyone who comes within 7 blocks. A determined player
may be able to skirt one through a loop gallery, and the sight check is known to pass through
walls, which is why the radius is small rather than large. **Walking the climb and counting how
many of the ten actually force a battle is what EXP-033 has to answer.** Nothing here has been
seen in game.

### The tenth team: the Gate Warden

The tenth stand was carved and never staffed — `data/vr_caves.json` says `count: 10` and ends
"Marked and unstaffed", and `data/trainers.json` holds nine. The Gate Warden is what that stand
is for: the one fight in the cave that cannot be walked around, standing in the exit shaft so the
climb ends in a battle instead of a staircase.

```
klang     57   geargrind, chargebeam, shiftgear
toxapex   58   poisonjab, toxicspikes, recover
heracross 59   brickbreak, megahorn, rockblast
```

Species and movesets come from the pool the nine already use; `maxItemUses: 0` as every Victory
Road trainer has.

**The band, and why the cap data did not settle it.** `data/progression.json` carries no level
cap to read. Its own notes say: *"Level caps are computed by RCT per player from the active series
(initialLevelCap 20, relativeLevelCap 0 in `modpack/config/rctmod-server.toml` since 2026-09-24,
Cobbleverse ships 5), so chapters carry no level_cap here."* There is no Victory Road cap in the
data at all. So the band is the one the nine imply: they climb 51 to 58 by one or two a fight,
and the Elite Four open at 57-60 behind a level-60 ace. **57-59** continues the nine's own step
and stops one level under Lorelei's ace — the hardest fight in the cave, and still easier than
the first room above it. (`docs/world-building/RIFT_STATUS.md` notes in passing that "the level
cap in Victory Road moved from 65 to 60"; 57-59 sits under 60 either way.)

The record lives in `data/vr_trainers.json`, not in `data/trainers.json`, because that file is
generated by `docs/story/generate_trainers.py` from `docs/story/TRAINER_RULES.json` and must not
be hand-edited. `data/mansion_guardians.json` is the precedent for a record that lives beside its
seat. When `TRAINER_RULES.json` is next edited the Gate Warden should migrate there and the
`generation_contract` count rise from 50 to 51.

## B. The League

The five have no authored coordinates, on purpose.

`data/structures.json` (`cobbleverse:kanto_league`, read from COBBLEVERSE-DP-v31.zip) and
`docs/world-building/STRUCTURE_INVENTORY.md` both record that the 111x159x120 template already
carries **five `rctmod:trainer_spawner` blocks** locked to `kanto_league_lorelei`,
`kanto_league_bruno`, `kanto_league_agatha`, `kanto_league_lance` and `kanto_champion_blue`. The
campaign is already bound to those upstream ids rather than to ours: `data/progression.json`'s
`champion_cleared` flag is set by defeating `kanto_champion_blue`, exactly as `gym1_cleared` is
set by `kanto_brock`.

So our five authored teams reach a player by **overriding the upstream ids' team and dialogue at
the upstream path** (`.claude/rules/datapacks.md`), which is what `upstream_neutralised` already
does for the same trainers' loot tables. Seating five new trainers at hand-chosen coordinates
would need the template's interior geometry, which is not in this repo — it is placed by resource
id from the installed pack and never copied in — and would leave upstream's own five spawners
standing in the rooms beside them.

| our record | overrides | order | members | levels | ace |
|---|---|---|---|---|---|
| `elite_01_lorelei` | `kanto_league_lorelei` | 1 (Ice) | 6 | 57-60 | lapras 60 |
| `elite_02_bruno` | `kanto_league_bruno` | 2 (Fighting) | 6 | 57-60 | hitmonlee 60 |
| `elite_03_agatha` | `kanto_league_agatha` | 3 (Ghost) | 6 | 57-60 | gengar 60 |
| `elite_04_lance` | `kanto_league_lance` | 4 (Dragon) | 6 | 57-60 | dragonite 60 |
| `champion_blue` | `kanto_champion_blue` | 5 (Mixed) | 6 | 58-62 | blastoise 62 |

**Measured from** `data/placements.json` `league_building`: `cobbleverse:kanto_league` at
(3754, 88, 2375), `clockwise_90`, corner anchor, size 111x159x120, so the building occupies
x3635-3754, z2375-2485 with its floor at y88 and its entrance facing south. The `league`
settlement puts Victory Road's arrival at (3656, 2486), three blocks from the door. Every seat
lies inside that box. No world save was read.

**What enforces the order.** The template, not us.
`docs/world-building/STRUCTURE_INVENTORY.md`: *"The league is one 111x159x120 template with five
trainer spawners (Lorelei, Bruno, Agatha, Lance, Blue). A LumyMon elevator in it requires the
advancement `cobbleverse:trainer/kanto/defeat_elite_lance`."* `data/structures.json` carries that
same advancement as the structure's one `required_advancement`. The Champion's floor cannot be
reached until Lance is beaten, and the four rooms run in order ahead of it. Because only the team
and the lines are overridden, every door, gate and spawner stays upstream's, so the order we
inherit is the order Cobbleverse built.

**Not verified.** What gates rooms 1 to 4 from one another inside the template has not been read
out of the template here — only the elevator's advancement has, and from a repo record rather
than from the blocks. The template's geometry is not in this repo. An in-game walk of the League
is the only thing that settles it, including what a beaten room's door does for a second player
at a different point in the order.

**Deliberately not emitted** for these five: the rctmod mob file (upstream's spawner owns how each
is spawned, and a `spawnWeightFactor: 0` override could break it), a loot table (the Champion's is
already emptied by `upstream_neutralised`; the four elites' upstream tables are another unit's
call), an advancement (`champion_cleared` already fires through `tools/progression_pack.py`), and
any entry in `placements()` — there is no seat for `reapply` to summon at.

## What this unit could not do, and what has to happen next

### 1. Ten quest fields must be declared (blocking)

`tools/route_trainers.py` refuses to emit a trainer whose fields are not declared in
`data/progression.json` `quest_fields`, and none of the ten are. `data/progression.json` belonged
to another unit on the night this was written, so it was read and not written. **`prepare`'s
`route_trainers` job fails closed until these ten entries are added** — the tool now names all
ten in one run instead of stopping at the first:

```json
{"id": "quest.route_09_trainer_01.defeated", "quest_id": "route_09_trainer_01", "field": "defeated", "type": "boolean", "scope": "player", "initial": false},
{"id": "quest.route_09_trainer_02.defeated", "quest_id": "route_09_trainer_02", "field": "defeated", "type": "boolean", "scope": "player", "initial": false},
{"id": "quest.route_09_trainer_03.defeated", "quest_id": "route_09_trainer_03", "field": "defeated", "type": "boolean", "scope": "player", "initial": false},
{"id": "quest.route_09_trainer_04.defeated", "quest_id": "route_09_trainer_04", "field": "defeated", "type": "boolean", "scope": "player", "initial": false},
{"id": "quest.route_09_trainer_05.defeated", "quest_id": "route_09_trainer_05", "field": "defeated", "type": "boolean", "scope": "player", "initial": false},
{"id": "quest.route_09_trainer_06.defeated", "quest_id": "route_09_trainer_06", "field": "defeated", "type": "boolean", "scope": "player", "initial": false},
{"id": "quest.route_09_trainer_07.defeated", "quest_id": "route_09_trainer_07", "field": "defeated", "type": "boolean", "scope": "player", "initial": false},
{"id": "quest.route_09_trainer_08.defeated", "quest_id": "route_09_trainer_08", "field": "defeated", "type": "boolean", "scope": "player", "initial": false},
{"id": "quest.route_09_trainer_09.defeated", "quest_id": "route_09_trainer_09", "field": "defeated", "type": "boolean", "scope": "player", "initial": false},
{"id": "quest.route_09_trainer_10.defeated", "quest_id": "route_09_trainer_10", "field": "defeated", "type": "boolean", "scope": "player", "initial": false}
```

### 2. `reapply.py` needs no new step

`R17` already places `[("trainer", t) for t in route_trainers.placements()]`, and the ten
Victory Road seats are now in that list; the League's five are deliberately not. Ordering is
already right: the caves are `R9C`, long before `R17`. `tools/reapply.py` was not touched by this
unit, but one line there is now stale — **`R17`'s label reads "scene props, scene NPCs and the
route trainers" and should read "... and the placed trainers (Routes 1-3, the mansion, Victory
Road's ten)"**, because its contents changed under it. That is the whole of the reapply change.

### 3. Unclaimed findings, for whoever owns them

- **No generator writes any gym leader's team.** `data/progression.json` binds `gym1_cleared` to
  `kanto_brock` and so on, and `tools/route_trainers.py` was until now the only tool writing
  `data/rctmod/trainers/*`, and it wrote only Routes 1-3. So our eight authored gym leader teams
  may not be in the game at all; upstream's are. The League five are fixed here by the same
  mechanism, and the gyms are the identical job.
- **The dialogue ids go nowhere.** `data/trainers.json` gives every Victory Road and League
  trainer `dlg_*` ids, and `data/dialogue.json` contains none of them (checked 2026-09-30); the
  `generation_contract` calls them "campaign metadata; RCT sidecars require a future compiler".
  The text for these fifteen is authored in the seat files instead, and the generator now falls
  back to it. When that compiler exists, the fallback is the thing to remove.
- **The trainer texture set is narrow.** Only 18 `rctmod:textures/trainers/single/*.png` names
  appear anywhere in this repo, and the ten seats reuse from that verified set rather than
  guessing at names in the jar. A wider audit of rctmod's textures would let Victory Road's ten
  stop borrowing Route 1's faces.
