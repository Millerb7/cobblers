# Critical path walk, part 1: joining to the town of gym 5

**Asked by:** the owner, 2026-10-04 ("Walk the whole game ... not an audit of what is built, a walk of what a player
hits"). **Part 2** (gym 5 to the Champion) is a separate walk.

**How this was walked.** On the data and generators at `5a03188`, in the order a player meets them: the join screen,
Pallet, Route 1, Stoneford (gym 1), Route 2, Viltri Quay (gym 2), Route 3, Highwire (gym 3), Route 4, Greenhollow
(gym 4), Route 5, arrival at Fenhide (gym 5). No server, world or staging was touched; nothing was run but reads of
`data/`, `docs/`, `tools/` and one read of the Cobblemon 1.8.0 jar's species files (Python `zipfile`). **Nothing below
is seen in game unless it says so.** Where a fact is only provable in game, the coordinate to check is given.

Labels: **BLOCKER** a player cannot continue; **STALL** continues, but confused or with nothing to do; **GAP**
something promised is missing; **OK** works as far as data and recorded tests show.

## 1. Leg by leg

Caps are rctmod's (`modpack/config/rctmod-server.toml:144,153,159`: `initialLevelCap 20`, `relativeLevelCap 0`,
`initialSeries "kanto"`), so the cap is the next leader's ace: 20, then 25/30/35/40 (`docs/mechanics/LEAGUE_LEVEL_CAP.md`
section 2, verified in rctmod source, not observed moving in game). Wild bands are `data/encounter_design.json`
`rules.tiers`. Catches are `docs/story/AVAILABILITY.md` (generated 2026-10-02 17:58 from the compiled pools, after the
encounter rebuild).

| Leg | Path | Trainers | Gym | Badge / cap | Catches vs curve | Next town reacts? |
|---|---|---|---|---|---|---|
| **0. Join, Pallet** (spawn 1461, 118, 5306) | Starter screen on join; Oak in his lab (1493, 118, 5317) | none | -- | cap 20 | -- | Oak -> Mina (1454, 118, 5287) -> Oak -> Maren (1472, 117, 5321): a story ladder, OK as data |
| **1. Route 1** Pallet -> Stoneford, 1,978 walked | No road (0 of 9 legs built, STATE "Routes"); a 220-block dirt stretch out of Pallet (`placements.json` hometown plan), the maze forest's main path (R6), then the vale and the Viltri Plateau; transition signs only at 244, 1,236, 1,461 and 1,465 blocks (the longest unsigned stretch about 990). **No gym-1 marker**: "Gym 1's is Oak's to offer at the start (not built)" (`data/progression.json:2958`) | 4 seated, L7 -> L15-17 (`data/route_trainers.json`), the mansion's 5 Channelers off the spur (junction sign at 1466, 5036) | -- | -- | tier 1, L4-14: 31 species; grass 10, water 10 against Brock's Rock; fighting/ground only by evolving. Matches the curve | -- |
| **Gym 1, Brock** Stoneworks Hall, lot x1806-1845 z3656-3703, door (1826, 142, 3667) | 9-step climb to the gallery (`data/gym_buildings/gym1.json` `route`) | **none in the hall** (`gym1.json:331` `"trainers": []`) | Our team, override PROVEN in game 2026-09-30 (`docs/FLIGHT_FINDINGS_2026-09-29.md` F11). Emitted now: geodude 18, bonsly 18, onix 20 (3) | `gym1_cleared` proven (EXP-027); badge + badge box + one TM once (`progression.json` `first_win_rewards`, not observed); cap -> 25 | -- | Witness Brock (1832, 142, 3661) outside on the forecourt; the Stoneford counter (1776, 139, 3608) opens items at `gym1_cleared` |
| **2. Route 2** Stoneford -> Viltri Quay, 944 | Descent to Lake Viltri; one sign mid-leg (500) | 4, L18 -> L20-22 | -- | -- | tier 2, L13-19: 46 species (+15); grass 12, electric 5 against Water. Matches | -- |
| **Gym 2, Misty** donor gym (1594, 2859), the carved cistern under it | Shaft (1620, 133, 2867) down 38 to the cistern, race, three mouths, gallery, back up | **2 seats, no rosters** (`gym_interiors.json` gym2 `trainers`: seat/yaw only; no record in `data/trainers.json`) | Ours; spawner (1605, 132, 2874), **ungated, same hall as the shaft** (`gym_interiors.json:1144` `"gate": null`) | cap -> 30 | -- | Relief clerk (1601, 108, 2801) gated on `brock_account_heard` (story), not the badge |
| **3. Route 3** Viltri Quay -> Highwire, 2,120 | Foothill Woods, then the Tri Peaks grade (81 climb, max 23.5 deg); signs at 367, 1,654, 1,691, 1,776, 1,782, 1,786, 1,790 | 5, L21 -> L25-27; **route_03_trainer_05 inside a signpost** (1980, 134, 1602) | -- | -- | tier 3, L19-28: 87 species (+41); ground 5 against Electric. Matches | -- |
| **Gym 3, Lt. Surge** Relay Works, x1722-1752 z1388-1432 | 8 steps, stair (1733, 175, 1426) to the cable ladder | **none** (`gym3.json:316`) | Ours, spawner (1747, 190, 1414) | cap -> 35. **Mythical starters' stage 2 at L30** lands on this leg | -- | Signal clerk (1685, 175, 1413), story-gated |
| **4. Route 4** Highwire -> Greenhollow, **3,453** (longest leg) | Back east over Mt Vessu/Mt Clay, the Merian cirque, the Crags, the Upper Trough, Peak Pond Hollow; signs at 328, 437, 1,048, 1,845, 2,114, 2,891 (gaps to ~800) | 6, L26 -> L31-33 | -- | -- | tier 4, L23-33: 133 species (+46); **first fire (6)**, ice 10, flying 19, poison 8 against Grass. Matches | Merian hut's Centre (2806, 1014) is 208 off the line, **no junction sign** |
| **Gym 4, Erika** Great Glasshouse, x4288-4332 z1470-1512 | 7 steps, door (4310, 111, 1511) | **none** (`gym4.json:261`) | Ours, spawner (4308, 110, 1480) | cap -> 40 | -- | Survey archivist (4309, 111, 1551), story-gated |
| **5. Route 5** Greenhollow -> Fenhide, 1,051 | Flat (max 7 deg); signs at 867, 873, 994; Koga's shrine niche (4509, 2303) | 4, L32 -> L34-36 | -- | -- | tier 5, L28-38: 164 species (+31); ground 14, psychic 8 against Poison. Matches | Fenhide: marsh tracker (4643, 118, 2449) story-gated; Mart (4721, 121, 2476); waystone (4668, 2422) locked until `gym5_cleared` |

**No leg needs water, a bridge or a gate.** Legs 1-5 have no recorded water crossing (`data/routes.json`
`water_crossings` empty), and no Rift zone box touches a route 1-5 point (checked against `data/rift_zones.json`
boxes and `data/route_paths.json`).

## 2. Every stop, stuck or nothing point

Ranked within each class. Coordinates are x, y, z.

### Blockers

1. **BLOCKER (risk, unproven): the starter.** `modpack/config/cobblemon/starters.json` offers one tab, "Cobblers",
   with Cosmog, Kubfu, Type: Null, Poipole and Meltan at L5 `aspect=cobblers_starter_1`. Their usable movesets exist
   only in our forms (`build/datapacks/cobblers_mythical_starters`, world-local). The config is server-wide and the
   pack world-local (REVIEW 25), and EXP-049 has not run (`data/mythical_starters.json` `status`). **Read from the
   Cobblemon 1.8.0 jar this session:** vanilla Cosmog knows `1:splash, 1:teleport` and nothing else, so a Cosmog pick
   on any world where the form does not apply **cannot damage anything**: no win, no money, no Poke Ball, and every
   eye-contact trainer is a forced loss. Vanilla Poipole knows Dragon Pulse at level 1 (`poipole.json`), the trigger
   for its native evolution. Only Poipole is `implemented: true` in the bare jar; the other four rely on Mega Showdown
   or COBBLEVERSE additions and their models are ASSUMED to render (`docs/research/MYTHICAL_STARTERS.md` lines 104-111,
   experiment X6). **In game:** a fresh account on staging, pick Cosmog, open its moves; pick Poipole, check it is
   still Poipole after a minute at L5.
2. **"The three extra starters" (UNRESOLVED; cannot be answered from the repo).** Config and data both offer exactly
   five. Under `useConfigStarters: false` a datapack `starters` category would *replace* the list, not add to it
   (`docs/research/notes/starter-selection.md` section 1), so "five plus three" is not a reachable state from our
   files. Candidates, cheapest check first: (a) the server's *installed* `config/cobblemon/starters.json` differs from
   `modpack/config/cobblemon/starters.json` (compare under the lock); (b) a loaded mod jar or Cobbleverse zip ships
   `data/*/starters/` (the audit checks only our build packs, `tools/mythical_starters_audit.py:31`); (c) the owner
   means three of the five (for instance Type: Null, Poipole and Meltan) render as placeholders, which is X6. Ask the
   owner for a screenshot of the screen.
3. **BLOCKER for co-op, unproven:** a second player's flags, reveal cursors and trainer hold-offs. "A second player's
   flags untouched ... must be proven before anyone else plays" (STATE "Badge flags"); the reveal "remains single-player
   proven only" (`data/quests.json` `main_worldshift_reveal.generation_blockers`); the trainer cooldown is shared entity
   NBT, so an unbeaten partner must start each fight by hand (STATE "Our hold-off"). Needs the second account (C4).
4. **BLOCKER risk at every gym: no interior has been walked.** All five halls on this segment are "file-valid only"
   (`gym1.json` `status`); the independent movement model passes them, but the first player is the first test. Walk:
   Brock (1826, 142, 3667) to the gallery (1829, 156, 3697); Surge (1733, 175, 1426) to (1748, 191, 1410); Erika
   (4310, 111, 1511) to (4300, 119, 1485); Misty's shaft (1620, 133, 2867).

### Stalls

5. **No Poke Ball and no money at the start.** Nothing gives a ball: Oak's dialogue has no item (`dlg_main_pallet_oak`),
   no starter kit exists, and no reward record holds a Poke Ball (`grep -c poke_ball data/rewards.json` = 0). The first
   one costs 200 at Pallet's Mart clerk (1482, 119, 5243; `data/traders.json:561`). The starting balance (U-8) and the
   wild-battle rate (EXP-C) are unmeasured (`docs/research/INCOME_MEASUREMENT.md:224,268`). The first certain income is
   the Trail Novice (1465, 120, 5019), 285 blocks out; after him the nearest ball is back in Pallet or 1,700 blocks on.
   Pallet's only counter, the Packmaker (1470, 118, 5266: backpack 300, sleeping bag 250), is unaffordable at $0. The
   hidden-glade caches on Route 1 (2 Great Balls, `data/rewards.json` `r1_fern_glade`) are off the main path.
   **In game:** `cobbledollars query` on a new player; beat one wild Pokemon; query again.
6. **No way to Stoneford is marked.** Oak's gym-1 waypoint is not built (`data/progression.json:2958`); the road is not
   built; between the forest sign (244) and the vale sign (1,236) there are about 990 blocks with no sign, and 513
   more from the plateau sign to Stoneford. Oak's own lines point at "Viridian ... keep the
   coast on your left" (story misdirection, by design) and the correction needs Mina and Maren found first. A player who
   skips them has only signposts and location titles. From gym 2 on, the next gym is offered as a Xaero share on the
   flag (EXP-020 F5, unproven).
7. **Two Brocks.** `npc_main_brock_witness` *is* Brock (speaker `brock`), standing outside on the forecourt
   (1832, 142, 3661), while the leader stands inside on the gallery. The witness says "Show the local trainers you can
   handle the road ahead, then face me" (`data/dialogue.json` `brock_009`) in a hall with no trainers, and "If you earn
   the badge, go to Misty's lake town" (`brock_010`, line 1900) whether or not you have it. In staging the leader still
   stands one block up on his spawner: the fix (281c0c9) is in data and **not applied** (HANDOVER section 0 item 3).
8. **The gyms have nothing in them but the leader.** Gyms 1, 3, 4 and 5 have `"trainers": []`; Misty's two seats
   (Rescue Swimmer (1609, 88, 2874), Lifeguard (1604, 99, 2874)) have no rosters anywhere. **Misty's cistern is
   optional:** her spawner (1605, 132, 2874) is in the hall the shaft opens from, ungated, so the whole interior can
   be walked past.
9. **Route 4 is 3,453 blocks with one Centre, unsigned.** Merian hut's Centre (2806, 1014) is 208 blocks off the line
   at 42% of the leg; `data/signposts.json:48` `junctions` lists only the mansion spur. No Mart between Highwire and
   Greenhollow. The Displaced City (287 off) is hidden on purpose.
10. **83 Pidgey on Route 1.** The world-tree sapling at (1375, 135, 4625) is **14 blocks** from the walked line and
    held 83 wild Pidgey within 60 in staging (REVIEW 61, `data/habitat_blocks.json` `route1_sapling_*`), round a
    Celebi walled in barrier blocks (1383, 143, 4630).
11. **Misty's canal and the swim rule.** The race (1604-1620, 86-89, 2872-2876) is swum, and the true mouth is a
    6-block underwater climb to (1602, 98, 2874). `data/blackout.json:161-170`: every swim builds fatigue; deep water
    (3 blocks) at 4 a tick warns at 5 s and hits from 15 s. A player trying both dead-end sumps first can be hit
    inside a gym. **In game:** try the two wrong mouths, then the right one, and watch the fatigue.
12. **Trainers standing in blocks.** `route_03_trainer_05` inside a signpost at (1980, 134, 1602), 4 blocks from the
    line (REVIEW 62, the owner's call); `route_01_trainer_01` (1465, 120, 5019), the first fight of the game, has a
    "solid" block at its feet (probably a flower; not looked at).
13. **The over-cap refusal is silent.** rctmod refuses every trainer battle while a party member is strictly over the
    cap, "without saying why" (STATE "level-cap trap"). In co-op a friend's traded Pokemon does this. The catch block
    (`data/level_cap.json`) is installed in staging and not run in game.

### Gaps

14. **No town knows you won.** Every reveal NPC opens on `{"kind": "always"}` and its story cursor (`data/dialogue.json`
    e.g. lines 1814, 1929): Viltri's clerk wants "Brock's account", not Brock's badge. The quest still says "The
    dialogue compiler cannot read advancement-backed gym flags" (`data/quests.json:1885`), **which is stale**:
    `{"kind": "flag"}` conditions exist since 2026-09-27 (`tools/compile_dialogue.py:27-30`, first used by the ferry).
    The only things that react to a badge are the counters (`data/markets.json`) and the waystones.
15. **The leaders speak Cobbleverse's lines**: our dialogue for them is deliberately not emitted
    (`data/gym_trainers.json` `not_emitted`).
16. **Pallet's crushed house has nobody in it**: Hank and Lena are unseated because `compile_dialogue.py` refuses their
    world-scoped field (`data/npc_seats.json` `not_seated`).
17. **The trainer card** (500, Pallet's Mart only; `data/traders.json:571`) is out of reach at the start, and
    `spawningRequiresTrainerCard = true` (`rctmod-server.toml:87`) withholds natural RCT trainers until it is bought.
    Seated trainers and leaders are unaffected.
18. **Decisions still open on this segment**: the Pallet relocation and Route 1's middle feature (STATE "What is open"),
    the hometown and midpoint waystones (`progression.json` `open_questions`), Challenge mode (only Normal teams are
    emitted).
19. **Rematches pay.** The leader hold-off (`leader_cycle_lines`, keyed on `gymN_cleared`) is not seen in game, and
    CobbleDollars pays every rematch win (STATE "Cobbleverse gym rewards").

### Records that disagree with the repository

- STATE "The leaders' teams are ours" still says the override rests "on one unverified assumption"; F11 proved it in
  game on 2026-09-30.
- STATE "Starters" says the config offers 27 starters and the mythicals are "NOT built"; since `50321948`
  (2026-10-03) the config offers five and the forms pack is built.
- `data/gym_trainers.json` says Brock and Misty have 4 members; `data/trainers.json` emits 3 for each.
- `data/gym_buildings/gym1.json` route step 7 still ends at y157, Brock's height before 281c0c9.
- `data/late_route_trainers.json` `status` "placed in no world yet" against STATE's 63 of 63 seated.
- `docs/story/AVAILABILITY.md` "Habitat pools" says no blocks are placed, and its own table lists placed blocks.

## 3. In-game checks, in walking order

| # | Where | What settles it |
|---|---|---|
| 1 | join a fresh account | what the screen shows (item 2); Cosmog's moves, Poipole after a minute (item 1) |
| 2 | Pallet, any spot | `cobbledollars query` before and after one wild win (item 5) |
| 3 | Oak (1493, 118, 5317) | the owner's "professor in the wrong place" (REVIEW 62): the data was judged correct |
| 4 | Route 1, (1468, 5116) | stand still: do the route pool's species appear (REVIEW 53-54 saw a source outside our pools at Frostpeak) |
| 5 | (1375, 135, 4625) | the Pidgey count after R9E's next run |
| 6 | Brock's hall (1826, 142, 3667) | the climb, the leader's height, a rematch refused after the win |
| 7 | Misty's shaft (1620, 133, 2867) | the swim and fatigue; then the Xaero share for gym 3 after the win |
| 8 | (1980, 134, 1602) | the Vessu Ranger in the sign |
| 9 | Surge (1733, 175, 1426), Erika (4310, 111, 1511) | each climb to the leader |
| 10 | Fenhide waystone (4668, 2422) | refuses activation before `gym5_cleared` |
