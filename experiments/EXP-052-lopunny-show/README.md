# EXP-052: can Ellis Hopgood see the player's Lopunny, and do his Buneary stay in the cellar?

Status: **built 2026-10-02, not run.** For the integrating session, on staging, under the coordination lock.

## Objective

The owner, 2026-10-02: *"add a house at 6950 1360 that is a man who has a dungeon of buneary, hes obsessed with
lopunny and wants one of his own"*. The house (`data/lopunny_house.json`, `tools/lopunny_house.py`) gives him a
cellar of Buneary and a quest: raise a Buneary into a Lopunny and show her to him. Two parts of that rest on
pieces each proven alone and never together; this run proves the combination.

## What is proven, and what this run must prove

| Part | Status | Evidence |
|---|---|---|
| A `player_tick_pre` callback under `data/cobblemon/callbacks/` fires; one under our own namespace never does | proven | EXP-042 (the water ladder) |
| That callback reads `q.player.party.pokemon`, a species through a `t.` variable, and runs a command naming `q.player.username` | proven | EXP-042 runs 1-2: the owner's Lapras read as mount level 1 |
| A dialogue option's `isVisible` and action read `q.player.has_tag(...)` | proven | EXP-022; every held-item condition (`tools/compile_dialogue.py`) |
| `grant_reward_once` gives the contents once per player | proven | the Thirsty Stranger and the Abandoned Cut |
| A second `player_tick_pre` callback beside the water ladder's also fires | **unproven** | Cobblemon loads every file in the folder (EXP-042 saw the load count rise) but only one of ours has run |
| `tag <name> add/remove` from that callback reaches the player the dialogue then reads | **unproven** | the chain end to end |
| An activated Habitat Block in a sealed room fills the room and nothing outside it | **unproven** | the spawner's box is `spawn_range` round the block (`docs/research/notes/habitat-nest-perching.md` 4); never run underground |
| Buneary do not leave the room with the trapdoor closed | **unproven** | nothing tethers a wild spawn (same note); only the walls and the trapdoor |

## Success criteria

1. Before R9E: `(6950, 112, 1360)` is `minecraft:stone_bricks`; after R9E and the restart it is the Habitat Block,
   `MimicId "minecraft:stone_bricks"`, `PoolId "cobblers:lopunny_superfan_cellar"`, `SpawningStyle "cobblemon:activated"`.
2. The house floor is y117 at `(6950, 117, 1360)`; the trapdoor at `(6946, 117, 1356)`; the ladder `(6946, 113..116, 1356)`.
3. With a player in the cellar, within a minute 1 to 12 Buneary stand in the room (x6946..6954, y113..115,
   z1356..1364), levels 33-43; after five minutes with the trapdoor shut, **0** Pokemon in the house
   (x6945..6955, y118..122, z1355..1365) and none spawned on the snow round it.
4. A player with a Lopunny in the party carries the tag `cobblers_lopunny_in_party` within 1 s
   (`tag <name> list`); with the Lopunny put in the PC, the tag is gone within 1 s. A player without one never has it.
5. Ellis Hopgood stands at `(6948, 118, 1362)` and renders as Cobblemon's trainer. Talking: the intro, then the
   hub "Well? Is she with you?" with three options; with the tag, a fourth, "Show him your Lopunny.". Choosing it
   runs s001-s004 and gives **one** Soothe Bell; talking again gives the repeat line and no second bell.
6. Two players: each has their own cursor and their own bell; one's Lopunny does not show the option to the other.

## Implementation

- `tools/lopunny_house.py build` -> `build/datapacks/cobblers_lopunny_house`: `cobblers:lopunny_house/build`
  (the house, the cellar, the yard and the statue) and
  `data/cobblemon/callbacks/player_tick_pre/cobblers_lopunny_house.molang` (the party check).
- The Habitat Block: `data/habitat_blocks.json` `lopunny_superfan_cellar_ward`, placed by R9E. The pool:
  `data/spawns.json` habitat `lopunny_superfan_cellar`.
- Hopgood: `data/dialogue.json` `dlg_lopunny_superfan`, `data/quests.json` `evt_lopunny_superfan`, placed by R9F
  from `data/rewards.json` `lopunny_superfan`.
- `tools/lopunny_house_audit.py` checks all of it offline.

## Test instructions

1. Install `cobblers_lopunny_house` with `cobblers_dialogue` and `cobblers_habitats` (world-local or server
   datapacks), restart.
2. Run the house step (`tools/lopunny_house.py` `placement_steps()`), BEFORE R9E; probe 1's first half and 2. Then
   R9E, the restart, R9F; probe 1's second half.
3. Stand in the cellar a minute; count (criterion 3). Close the trapdoor, wait five minutes, count the house.
4. Get a Lopunny into a test player's party (catch one on the isle, `surface.south_pine_isle.lopunny` 38-43, or an
   operator's give command - which command is NOT verified here); `tag <name> list`; deposit it; list again.
5. Talk to Hopgood without and with the Lopunny (criterion 5), then a second player (criterion 6).
6. Read the server log for Molang errors from `cobblers_lopunny_house.molang` after the reload.

## Results

Not run.

## Limitations

Offline, the audit proves the blocks, the box geometry, the order of writes and the chain's text, not behaviour.
The Soothe Bell's effect is not claimed anywhere.

## Decision

Pending the run.

## Follow-up

If criterion 4 fails, the quest still runs to its hub and nothing is lost; the alternative is a quest field written by
the callback through `q.player.data()`, which is less proven than the tag.
