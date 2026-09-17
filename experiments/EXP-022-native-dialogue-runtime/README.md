# EXP-022: Campaign dialogue on Cobblemon's native dialogue runtime

## Objective
The campaign's conversations and quests exist as data (`data/dialogue.json`, `data/quests.json`, `data/progression.json`)
but had never run. This experiment compiles one of them, the Route 1 thirsty stranger (44 nodes, 5 per-player quest
fields), into Cobblemon 1.8's own dialogue format and tests what the design depends on:
- the conversation runs start to finish;
- held-item branches fire for a water bucket and a water bottle, and refuse other items;
- the offered item is consumed and its empty container returned;
- the reward is granted once per player;
- a player who disconnects mid-conversation resumes at the right node;
- two players can stand at different points of the same conversation.

## Success criteria
- Quest fields and the cursor are persisted per player and read back from disk while the player is offline.
- On reconnecting, the conversation opens on the node that was on screen when the player left.
- The inventory changes are exactly the authored ones: one item taken, one empty container and the reward contents given,
  once each, proven from the server log.
- Replaying the reward node with the reward already claimed gives nothing.

## Dependencies
Cobblemon 1.8.0+1.21.1 on Fabric 1.21.1 (Java 21.0.9), the full COBBLEVERSE server stack. Disposable world
`cobblers-runtime-proof/spawnproof`, seeded from the offline snapshot `2026-09-17-pre-grass`; the live world is never
touched. One operator account, in survival for the item tests.

## Implementation

### Runtime facts, each probed before the compiler relied on it (2026-09-17)

| Question | Probe | Result |
| --- | --- | --- |
| Where can per-player state live? | `runmolang` writing `q.player.data()` then `save_data()`, and reading `<world>/playermolangdata/<uuid>.dat` | Persisted as NBT. Strings (`'tb01'`) and numbers both read back; an unset key reads 0 |
| Can a reopened dialogue start at a stored page? | a dialogue whose `initializationAction` is `q.dialogue.set_page('p3')`, opened with `/opendialogue` | Opens on `p3`; `q.player.active_dialogue.current_page.id` reads `p3` over RCON |
| Who runs `run_command`? | Bytecode: `PlayerMoLangFunctions.run_command` uses the player's command source; `GeneralMoLangFunctions.run_command` (`q.run_command`) uses the server's | `q.run_command('execute as ' + q.player.uuid + ' …')` works for any player; the player version would need operator status |
| Does a command take effect before the next Molang statement? | Under `/runmolang`: tag set by `q.run_command`, then `q.player.has_tag` → **0** (a command inside a command is queued). In a dialogue action (`probe_sync`, clicked in game) → **1**, three times | Inside dialogue actions commands run immediately. The `/runmolang` result does not apply |
| Can Molang tell a water bottle from other potions? | `q.player.main_held_item.is_of('minecraft:potion')` | **No**: 1 for the water bottle and 1 for Swiftness |
| Strict item check | `execute if items entity @s weapon.mainhand minecraft:potion[potion_contents={potion:"minecraft:water"}]`, run from a dialogue action | Water bottle 1; Swiftness 0; water bucket (own predicate) 1 |
| A Fresh Water item? | Item-model and lang search of every mod jar | None in the pack; the vanilla water bottle is the only bottled water |
| NPC classes | `data/cobblers/npcs/*.json` with `"interaction": {"type": "dialogue", "dialogue": …}`; `spawnnpcat` | **NPC classes load only at server start** (a new class is unknown after `/reload`), and a function naming one fails to parse at load. After a restart the class spawns |

### The compiler
`tools/compile_dialogue.py dlg_route1_thirsty_stranger [--place X Y Z]` writes `build/datapacks/cobblers_dialogue`:
- **Dialogue** (`data/cobblers/dialogues/<id>.json`):
  - One page per node.
  - `initializationAction` evaluates the authored entry rules and calls `set_page`.
  - A line's input persists the cursor as the next node, then shows it.
  - A choice's options carry `isVisible` from `visible_when`, and actions from the quest transitions.
- **NPC class** (`data/cobblers/npcs/<npc>.json`): invulnerable and immovable, and its interaction opens that dialogue.
- **Placement** (`placement.txt`): the `spawnnpcat` command. It is not a function, because of the NPC class load order.

Each quest field `quest.<quest>.<field>` becomes the player-data key `cobblers__quest__<quest>__<field>`. Anything the
compiler does not recognise stops compilation.

Data added for the proof: the verified water-bottle offering and its authored `TF01`-`TF03` response
(`docs/story/events/ROUTE1_THIRSTY_STRANGER.md`), and verified reward item ids (`cobblemon:black_glasses`,
`minecraft:music_disc_cat`, `cobblemon:poke_ball`). The quantities and the disc are provisional.

Test position: the stranger at (1402, 125, 4794), inside Route 1 box `r01_b0080`, on dry level ground read from the
disposable world's region files. This is not the hut decision.

## Test instructions
1. Compile into `<world>/datapacks/cobblers_dialogue`, restart the server (NPC classes load at start), run the `placement.txt` command.
2. Read state with the player offline from `playermolangdata/<uuid>.dat`; with the player online, use `runmolang` for the open page.
3. **Disconnect/restore:** empty hand, talk, click to about line 7, quit to title with a line on screen, read the saved cursor,
   reconnect, talk.
4. **Bucket:** hold the water bucket, reach `offer_water`, hand it over, finish. Check the log for the slot replacement and each `Gave`.
5. **Reward once:** with `reward_claimed` 1, rewind the cursor to `ta08` over `runmolang`, talk and acknowledge. There must be no `Gave` line.
6. **Bottle:** with `water_delivered` 0 and `reward_claimed` 1, set the cursor to `offer_water`, hold the water bottle, hand it over, finish.

## Results
Run 2026-09-17, compiler as committed. Log excerpts are from the server console.

**Bugs found by the first in-game runs, fixed before the recorded runs:**
1. `give <uuid> …` is refused ("Only players may be affected by this command, but the provided selector includes
   entities"). No item was given, **and `reward_claimed` was set anyway**, so the reward was lost for good. Fixed on
   two counts: gives now run as `execute as <uuid> run give @s …`, and the claim is written only if no give failed. On
   failure, the cursor stays on the reward line so the next talk retries.
2. The first give of a session stores into the `cobblers_tx` objective. The objective did not exist yet, and
   `store success score` into a missing objective fails silently, so a returned glass bottle was lost. Every give now
   creates the objective first. For the recorded bucket run the objective was deleted beforehand, so the recorded run
   exercises exactly this case.

**Recorded runs:**

| Test | Evidence | Result |
| --- | --- | --- |
| Disconnect mid-conversation | Quit on "Something clear. Cool. Life-supporting." Saved state with the player offline: `started 1, dialogue_cursor "t007"`. Reconnected 12:10:57; the conversation opened on that line | **pass** |
| Bucket consumed, empty returned | `12:11:18 Replaced a slot … with [Air]`, `Created new objective [cobblers_tx]`, `Gave 1 [Bucket]`; state `water_delivered 1`, cursor `ta01` | **pass** |
| Conversation completes, reward | `12:11:21 Gave 1 [Black Glasses]`, `Gave 1 [Music Disc]`, `Gave 5 [Poké Ball]`; state `completed 1, reward_claimed 1, cursor repeat_beekeeper` | **pass** |
| Reward once | Cursor rewound to `ta08` with `reward_claimed 1`; the player acknowledged it and finished (12:15). No `Gave` line; inventory unchanged; `completed 1` again | **pass** |
| Bottle consumed, glass bottle returned | `12:16:30 Replaced a slot … with [Air]`, `Gave 1 [Glass Bottle]`, no reward gives; inventory shows `glass_bottle 1` and the Swiftness potion kept | **pass** |
| Held-item visibility | The bucket and bottle options appeared when that item was held (the player took each) | **pass** |
| Swiftness refused inside the dialogue | Not observed: the player held the water bottle when the recorded bottle run opened. Only the probe covers it (the predicate rejects Swiftness) | **not run in dialogue** |
| Two players at different points | Needs a second account | **not run** |

## Limitations
- **Single player so far.** Per-player isolation is by construction (per-uuid data files, `execute as <uuid>`, per-player
  tags) and is not yet observed.
- **The failure path is unexercised.** Neither the retry-on-failed-give branch nor an invalid item id has been tested.
- **Take-then-return is not atomic.** Consuming the item and giving its container happen in one server tick with no
  rollback. A server crash inside that tick is not tested.
- **Operators see chat noise.** Each held-item check echoes to operators' chat ("Added tag …"). Non-operators do not
  see admin broadcasts; this was not checked with a non-operator.
- **Rewinds were done by command.** The recorded reward-once and bottle runs started from a cursor set over
  `runmolang`, not from a fresh conversation. A fresh full run with the fixed compiler, taking the bottle branch, was done
  earlier: `12:08:07` consumed, rewards `12:08:14`. That run lost the glass bottle to bug 2.
- **One conversation.** The crushed-house conversations use world-scoped fields and actions the compiler refuses.

## Decision
**Adopt the native runtime for per-player quest dialogue:**
- conversations are compiled from campaign data by `tools/compile_dialogue.py`;
- state lives in Cobblemon player data;
- specific-item checks use the vanilla item predicate run as the server;
- every give reports success, and a claim depends on it.

No KubeJS, scripting layer or custom mod is needed for this event.

## Follow-up
- **Two-player run:** player A mid-conversation, player B at the offer; each disconnects and resumes independently; a
  reward for one does not mark the other.
- **Swiftness refusal in dialogue:** hold Swiftness at the offer; only "I do not have water." may appear.
- **Retry path:** a deliberately invalid reward id in a disposable build; the cursor must stay on `ta08` and nothing may be claimed.
- **World-scoped fields** (crushed house) need a design for shared state before the compiler accepts them.
