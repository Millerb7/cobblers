# Route 5's events: the Bellwether

Gap 6 of `docs/world-building/WORLD_SWEEP_2026-10-09.md` ("Routes 5, 6 and 8: no events"), Route 5 first. Routes 1-3 have
ten events (`tools/route_events.py`, R12); the sweep counted 11,559 walked blocks of Routes 4-8 with none (relayed, not
re-measured here). This is Route 5's chain: four event sites and one find, on the same scene, dialogue, quest and cache
mechanisms Routes 1-3 use. **Built offline; nothing has run in a server.**

## Mechanism rung (CLAUDE.md principle 6)

Datapack functions (block placement), the existing scene runtime (`data/scenes.json` -> `tools/scenes_pack.py`: props,
per-player actors, NPCs), Cobblemon-native dialogue compiled from `data/dialogue.json` by `tools/compile_dialogue.py`, and
ADR-002 caches (`data/rewards.json` -> `tools/rewards_pack.py`). Nothing above "datapack" is used; no mod, script or
companion. The previous rungs suffice because every part is something Routes 1-3 already run: the chain is new content on
proven mechanisms, and the only new code is the site builder (`tools/route5_events.py`), a block-command generator that
imports `route_events.Site` and changes nothing in it.

## What was measured (all on `tools/ground.py`, the canonical heightmap; no world read)

Route 5 is `route_05_erika_to_koga`: 892 dense cells, 1,051 walked blocks (matches `data/routes.json`), ground y110-117,
steepest grade 7.07 degrees, band 4 (cap 40). It leaves Erika's town (4309, 1555), runs south down a valley's west flank
(spruce and heath, `taiga_dense`) past four trainers (seats at walked 289, 448, 622, 734) and out onto the exposed fields
at the Glacial Tear's foot (`plains`) to Koga's town (4646, 2446). The ground east of the road rises to y127 at the Downs
Crag (4530, 1951); west of it falls to a hollow. Its compiled wild table is pastoral (Mareep, Flaaffy, Ampharos, Wooloo,
Lechonk, Furret, Sentret, Hatenna, Teddiursa, Emolga, Starly and the like): shepherds' country. Nothing else of ours
stands within 150 blocks of the road between walked 60 and 840 except the four trainers, the Crag's portal and the
Route 5 shrine niche (4509, 2303, walked 848).

| Event | Scene id | Walked | Site (x, z) | Ground | Road to site | Nearest trainer seat |
| --- | --- | ---: | --- | --- | --- | ---: |
| 1. The empty fold | `route5_empty_fold` | ~140 | fold x4402-4416 z1656-1667, Nan at (4399, 1664) | y110-113 | 16 to Nan | 151 |
| 2. The bell cairns (+ the tin) | `route5_cairn_bells` | ~347 | cairns (4424, 1884) (4432, 1876) (4434, 1889), tin (4430, 1883) | y114-121 | 48-59 to a bell, 52 to the tin | 77 |
| 3. The lee hut | `route5_lee_hut` | ~563 | hut x4397-4405 z2071-2077, Gorse at (4401, 2074) | y114-117 | 35 to Gorse | 65 |
| 4. The winter fold (payoff) | `route5_winter_fold` | ~885 | byre x4566-4576 z2288-2292, pen x4579-4585, Jory at (4571, 2295) | y113-115 | 42 to Jory | 155 |

Distances are from the dense path (`data/route_paths.json`); "nearest seat" is centre of the built bounding box to
`data/late_route_trainers.json`, and `tests/test_route5_events.py` also requires every scene AREA to hold no seat and to
stand at least 40 blocks from one (`tools/late_route_trainers.py` refuses a seat inside any scene area). The route's own
trainers sit at 289/448/622/734, so the events interleave with the fights: event, fight, event, fight, event, fight, fight,
payoff.

## The chain

One quest, `evt_route5_bellwether`, four scenes, eleven conversations, thirteen fields. A shepherd's bellwether, Tolly the
Flaaffy, has slipped his strap and gone south ahead of the flock. Each event stands alone and any order works; what a
player did earlier changes what a later person says and one reward.

1. **The empty fold** (walked ~140). A drystone fold east of the road, its gate swung open, nineteen ewes (a per-player
   Mareep actor stands in the gap) refusing to cross, an empty strap hook on the gate post. Nan Tarrow tells the story, where
   Tolly would go ("by the cairns first"), and what his bell sounds like: cracked, flat, a pebble in a tin. No reward.
2. **The bell cairns** (walked ~347). Forty paces east, up the rise: a signpost on the shoulder, a trail, three cairns each
   with a hung bell (prop, click to ring). West is bright, south is round, north is flat: the north cairn carries Tolly's
   blue strap and prints heading south-east. Ringing it sets `strap`. In the lee between the cairns, a barrel: the find
   (`r5_shepherds_tin`: 2 Sitrus Berries, 1 Lum Berry), earned by standing in it whether or not the bells were rung.
3. **The lee hut** (walked ~563). Old Gorse watches the Glacial Tear from a stone hut with a slab roof; a chalked weather
   board on its wall; a commons box ("take one parcel, leave the rest"). He says why the winter fold is where it is, and
   that a Flaaffy went by. The player picks the salve (3 Full Heals) or the oil (2 Super Potions); the other is never offered.
4. **The winter fold** (walked ~885, the payoff). In the open fields at the glacier's foot, behind a windbreak wall: a
   turf-roofed byre, a fence pen with a flat stone, a tally post. Tolly (a per-player Flaaffy actor) stands on the stone.
   Jory Tarrow, Nan's brother, pays: 2 Great Balls and 2 Sitrus Berries to anyone who found Tolly; plus a Magnet to a player
   who rang the flat bell and so brought the strap.

What differs from Routes 1-3: nothing mechanical, but the shape. Routes 1-3 are single-stop vignettes; this is a flock's
road laid along the whole leg, with one decision (the commons box), one off-path walk (the cairns) and one conditional
reward (the strap). No two of the four events are the same activity: listen and be told (1), ring bells and choose the
wrong ones first (2), choose a parcel (3), find a Pokemon and be paid (4).

## State model

Quest fields live in Cobblemon player data via the dialogue compiler (EXP-022), per player. The fields:

- Booleans: `met_nan`, `strap`, `met_gorse`, `commons_taken`, `found_tolly`, `met_jory`, `reward_claimed`, `completed`.
- Enum `commons` (`none` / `salve` / `oil`): which parcel was chosen; it is what lets a failed delivery be retried.
- Enum cursors: `nan_cursor`, `gorse_cursor`, `jory_cursor` (one per NPC conversation) and `prop_cursor` (every prop and
  actor conversation, which enter on an explicit node and never restore).

Where a rule bites:

- **Late join, different order, skipping events.** No event requires another. Jory's reward is chosen by two fields read at
  the moment he pays: `found_tolly` (the player met Tolly) and `strap`. A player who rings the flat bell after being paid
  stays with the plain reward (the claim is spent), so the Magnet is earned by doing the cairns BEFORE the fold, which
  `tests/test_route5_events.py` asserts across all 24 orders.
- **Disconnect mid-conversation.** Cursors persist after each node (the compiler's `after_each_node`); a reward line that
  fails to deliver keeps its cursor and the claim stays unwritten, so the next talk retries it. Gorse's entry rules put a
  player who chose but was not paid back on the parcel line, not on a menu with no way back.
- **Death / blackout.** Nothing here is gated on being alive or on a position; the blackout system's rules are
  untouched. A player who dies at the fold gets nothing taken and nothing repeated.
- **Two players.** The NPCs and props are shared entities that open the CLICKER's own conversation; the actors (Mareep,
  Flaaffy) are per-player copies side by side, clicking another player's says so. The two-player grant is the same
  unproven ADR-002 / `grant_reward_once` mechanism the rest of the game uses, not a new risk.
- **An export.** The block functions rebuild at R12R5 and the props, NPCs and actors are re-placed by R17 from
  `data/scenes.json`; the cache's barrel is rebuilt by R12R5 and its advancement is carried with the player
  (`tools/carry_players.py`), as Route 1's are.

## Economy

Rewards are items only (no CobbleDollars: `income_basis` is trainers, and wild battles pay nothing). Priced from
`data/markets.json` counter prices (Full Heal $300, Super Potion $400, Great Ball $350, Magnet $800):

| Source | Contents | Counter value |
| --- | --- | ---: |
| The tin (find) | 2 Sitrus Berry, 1 Lum Berry | not on a counter |
| Gorse, the salve | 3 Full Heal | 900 |
| Gorse, the oil | 2 Super Potion | 800 |
| Jory, plain | 2 Great Ball, 2 Sitrus Berry | 700 |
| Jory, with the strap | 2 Great Ball, 2 Sitrus Berry, 1 Magnet | 1,500 |

A player who does everything gets 2,400 at counter prices (the salve and the strap reward), 11.2% of leg 5's trainer income
of 21,433 (`income_basis.leg_by_badge["5"]`); a player who takes the least gets 1,500, 7.0%. For scale, Route 1's fern-glade cache
alone (2 Great Balls, 2 Oran Berries) is $700 at the same prices, 17% of leg 1's 4,033; this chain is lower. None of the five item ids is on the Bank's buy list (`data/bank.json buys`), so nothing converts
to money. Every item id is looked up at its jar path (`assets/cobblemon/models/item/<id>.json` in
`Cobblemon-fabric-1.8.0+1.21.1.jar`, read with `zipfile`), and the test reads the jar when the snapshot is on the machine.

## Registration (the shared files this touches)

- `tools/route5_events.py`: the generator. Imports `route_events.Site`, `sign()`, `wall_sign()`, `scene_patch()`,
  `apply_scene_patch()`, `verify_world()`; subclasses `Site` to read `data/elder_trees.json` for clearing protection
  instead of `derived/`. **`tools/route_events.py` is not edited.**
- `tools/reapply.py`: three insertions. `SERVER_PACKS` gains `cobblers_route5_events` (after `cobblers_bridges`); the
  prepare job `route5_events` (after `route_trainers`); the step `R12R5` (after `R12`, before R17).
- `data/scenes.json` (4 scenes, before `route1_gastly_family`), `data/quests.json` (1 quest, before `evt_prospector_claim`),
  `data/dialogue.json` (11 conversations, before `dlg_prospector_claim`), `data/progression.json` (13 fields, before
  `quest.route_01_trainer_01.defeated`), `data/rewards.json` (1 cache, before `r3_world_tree_roots`),
  `data/world_probes.json` (key `route5_events`, after `zapdos_tower`). Insertions are mid-file so they do not collide
  with another unit that appends.
- `--write-scenes` rewrites only the four scene records and the cache record, as text, so a re-run touches nothing else.

## Verified and not verified

Verified offline (this session): the generator runs clean (`python tools/route5_events.py` exits 0: no drift, nothing on
the road); `python tools/validate_data.py` 0 errors; `python tools/validate.py` 0 errors (including the ground rule);
`tools/id_authorship.py` 0 faults; `tools/compile_dialogue.py --all` compiles all eleven; `tools/scenes_pack.py` builds
the four scenes; `tools/late_route_trainers.py` still agrees with its seats; the model player in
`tests/test_route5_events.py` walks the authored dialogue in all 24 orders; `tests/test_route_events.py` (Routes 1-3) is
unchanged at 88 passed.

**Not verified: that any of it works in a running server.** In particular ASSUMED: that the `tripwire_hook`, wall banner,
fence arms and `moss_block` render as intended and stay attached (each is a vanilla block, set by `setblock`, with no
physics update expected); that a prop box over a hanging lantern is clickable; that the Mareep and Flaaffy actors place
from their markers (the scene runtime's actors are proven for Swablu, Wooper and others on Routes 1-3, not for these
species); that `grant_reward_once` from a line page works for these four rewards (the same mechanism as the Swablu
quest, which is itself not yet run for two players); that the barrel's advancement fires for the cache.

In-game check, once staged (R12R5, then R17): stand at (4399, 112, 1664) and click the hook; at (4433, 121, 1876) ring
the north bell and confirm the strap line; walk to (4430, 121, 1883) for the tin; at (4401, 117, 2074) talk to Gorse,
take the salve, and confirm a second visit offers no parcel; at (4571, 114, 2295) talk to Jory before and after clicking
the Flaaffy on its stone at (4582, 115, 2290). `python tools/presence_audit.py --only extra` runs the 14 probes under
`route5_events`.
