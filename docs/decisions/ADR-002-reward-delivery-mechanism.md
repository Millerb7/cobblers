# ADR-002: How a reward reaches a player

- **Status:** Proposed
- **Date:** 2026-09-23
- **Evidence:**
  - `docs/research/notes/reward-item-inventory.md` section 6 (the absence, itemised)
  - `data/quests.json:296-311, 335-362, 374-381` (`grant_reward_once`, its `verification`
    convention, and `"shared_chest": "decoration_only"`)
  - EXP-022 (per-player dialogue, reward-once, disconnect restore — single player only)
  - EXP-027 (advancement-backed badge flags on `cobblers-dryrun4`; player carry rehearsed)
  - `tools/carry_players.py:9-24, 65-75` (what survives a re-export, per player)
  - `tools/progression_pack.py:2-17, 190-197` (advancement + reward-function generator)
  - `tools/habitat_blocks.py:99-106`, `tools/traders.py:233` (the proven
    `setblock`/`data merge`/`summon`-with-SNBT re-application shape)
  - `tools/reapply.py:267-311` (the step list a placed thing must appear in)

## Context

**There is no chest, cache or loot mechanism in this repository.** That is not a gap in
Victory Road; it is a gap under every reward, cache and hidden item the campaign will ever
place. Verified, on 2026-09-23:

- `data/placements.json` has no reward record. Its `kind` vocabulary is exactly
  `town_centre`, `service`, `lab`, `house`, `gym`, `league`, `civic`, `landmark`, `donor`,
  `earthwork`.
- `data/events.json` does not exist. `docs/STATE.md` lists it as "Future `data/events.json`";
  the only material is the retired `data/notes/legacy_events.md:33`, which sketches an
  `e4-cache` "hidden stash rather than a fight" and implements nothing.
- `kits/` contains no loot table and no chest prefab. The only "chest" in `kits/` is prose in
  `kits/structures/prefabs/README.md`.
- **The only loot code in `tools/` deletes loot.** `tools/place_donor.py:115-128` emits
  `data remove block <x> <y> <z> LootTable` for every container in a donor template when the
  record sets `clear_loot`; `tools/place_town.py` does the same for houses;
  `tools/progression_pack.py:233-235` writes `{"pools": []}` over upstream loot tables named
  in `data/progression.json` `upstream_neutralised`. The campaign's entire relationship with
  loot so far is suppression.
- The one reward path that exists is per-player and runs inside a conversation:
  `grant_reward_once` with a `claim_field` and an `idempotency_key`
  (`data/quests.json:296-304`), compiled by `tools/compile_dialogue.py:132-152`, proven
  single-player in EXP-022.

Three constraints decide this, and they are not negotiable:

1. **Co-op multiplayer.** A small group plays this world together. A mechanism whose answer
   to "two players arrive" is "the first one takes it" is a mechanism that will be used once
   and resented.
2. **Per-player fairness is already the ruling.** `data/quests.json:374-381` states
   `"state": "per_player"`, `"reward_target": "triggering_player"`, and
   `"shared_chest": "decoration_only"`. A shared container holding anything that matters
   contradicts a decision this project has already taken.
3. **A re-export erases anything hand-placed.** Region, entity and POI files are replaced
   (`tools/carry_players.py:31-34`). Anything placed in the world must therefore be a record
   in `data/` re-applied by a `tools/reapply.py` step — and since 2026-09-23 `reapply.py
   prepare` fails closed on a generated pack that no step runs, so it cannot be forgotten
   quietly. **What does survive a re-export is per-player state:** `carry_players.py:65-75`
   carries `playerdata`, `advancements`, `stats`, `cobblemonplayerdata`, `pokedex`, `pokemon`,
   `cobbledollars` and `rctmod_player` as *required* categories, rehearsed in EXP-027. This
   asymmetry — world state is disposable, player state is durable — is the single most
   important fact in this decision and it points away from containers.

## Decision

**Proposed. Use per-player grants keyed to a vanilla advancement as the spine, and treat
containers as scenery.** Concretely, four mechanisms with a stated division of labour:

1. **Anything that matters — one-time, per-player, valuable (a TM, an Ability Patch, a
   Gold Bottle Cap, an evolution stone, a Z-crystal):** a vanilla advancement whose criterion
   is reaching an authored place, with `"rewards": {"function": "cobblers:reward/<id>"}`
   running as the earning player. Per-player and once-only by construction; the
   `advancements/<uuid>.json` that records it is already a required carry category. This is a
   **new record kind plus a branch in an existing generator**, not a new system:
   `tools/progression_pack.py` already emits `advancement/flag/<id>.json` together with
   `function/flag/<id>/granted` that runs as the player (`progression_pack.py:2-17, 190-197`),
   and that exact pattern was proven for the badge flags on `cobblers-dryrun4` (EXP-027).
2. **The physical cache is scenery.** A chest, barrel, gilded chest or cairn placed by the
   ordinary `setblock` path with its loot table stripped (`clear_loot`, the existing
   `place_donor.py:115-128` treatment), so opening it shows flavour and never the reward.
3. **Flavour contents may be literal.** Where a container's contents genuinely do not matter
   — cooked food in a camp, a fisherman's barrel — `setblock` plus `data merge block` with a
   literal `Items` payload, the shape `tools/habitat_blocks.py:99-106` and
   `tools/traders.py:233` already prove and audit.
4. **Where a trainer already stands, the trainer is the dispenser.** Victory Road has ten
   marked, unstaffed trainer stands (`docs/STATE.md`, "The Rift overhaul"); rctmod already
   hands rewards to the winning player per player, from its own reward loot tables
   (`docs/world-building/WORLDGEN_FEATURES.md:52-53` names `rctmod:generic/*/nature`). That
   is the highest rung available — an installed addon's own mechanism — and it costs nothing
   to use where a fight already belongs.

Under `CLAUDE.md` principle 6 this sits at **datapack** (rung 5) for (1), **functions and
commands** (rung 7) for (2) and (3), and **compatible addon** (rung 2) for (4). No scripting
layer, no server companion, no custom mod. Nothing here is world-critical: no blocks, biomes,
structures or worldgen are added, so a later reversal costs the caches, not the map.

Data model, sketched and **not implemented**: a new `data/rewards.json`, schema
`cobblers.rewards/1`, one record per cache with `id`, `kind`
(`cache` | `hidden_item` | `trainer_reward` | `npc_grant`), the trigger box or position, the
sub-region it belongs to, an optional `container` (block id, rotation, `clear_loot`), the
`advancement` id it grants, `contents` as a list of `{item, count, verification}` reusing
`data/quests.json`'s convention that an item id is proved by naming the jar path of its model
and lang key (`data/quests.json:345-361`), `presentation` (`show_toast`, `announce_to_chat`),
and the `reapply` step that puts the scenery back. Validation to be specified with
`test-author`: every item carries a `verification` string; every position is on measured
ground inside the border; no two records share an advancement id; every record with a
container is named by a `reapply.py` step or excluded with a reason.

## Alternatives considered

- **(a) A block `LootTable` written by a re-applied function.** Rejected as the spine.
  `setblock <pos> minecraft:chest` plus `data merge block <pos> {LootTable:"cobblers:..."}`
  is cheap and the table itself is a reviewable datapack file. But vanilla rolls a container's
  loot table **once**, on first open, writes the result into `Items` and clears the tag: the
  reward is both **shared** (whoever opens it first has it) and **random**, which is the worst
  pair for "one named TM per region". **ASSUMED, not verified in this pack:** that 1.21.1 has
  no per-player container re-roll. The reward inventory flagged the same question
  (`reward-item-inventory.md` section 6, mechanism 2) and it stays open — but even if a
  re-roll existed, randomness still fights the design. Kept only as a possible future way to
  stock a *shop* or a *restockable* barrel, where randomness is wanted.
- **(b) `setblock` plus `data merge block` with literal contents.** Kept, but demoted to
  scenery and flavour (decision item 3). It is the best-proven shape in the repository and it
  audits cleanly against a stopped world copy, but a chest is shared world state: the first
  player empties it, which `data/quests.json:379` has already ruled out for anything that
  matters. Two further costs: 1.21.1 item stacks in NBT use the data-component format, which
  **is not verified** anywhere in this repo; and the contents are erased by a re-export, so
  every restock is a re-apply.
- **(c) Extending `grant_reward_once` to fire at a world marker.** Kept for rewards that are
  part of a conversation, not adopted as the spine. It is per-player, idempotent, and its
  claim field lives in Cobblemon player data, which is carried across a re-export. Its cost is
  the trigger: today it fires only inside a Cobblemon dialogue, so it needs an NPC standing at
  the cache — a different fiction from a hidden stash, and one more placed entity needing its
  own re-apply step (the traders' R14 is the precedent). It also inherits an open gap: the
  two-player dialogue run is unproven (`docs/STATE.md`, "Dialogue delivery").
- **(d) One container instanced per player.** Rejected. N chests per cache, a player count
  that is not fixed, and no answer for a player who joins later.
- **(e) Do nothing; all rewards come from NPCs and trainers.** Rejected as insufficient, but
  it is the honest fallback if the advancement trigger fails its proof. It cannot express a
  hidden item, which is a stated part of the world's texture.

**A boundary this decision does not cross.** An advancement cannot write a Cobblemon quest
field, and Cobblemon dialogue cannot read an advancement — `docs/STATE.md` already records
that "advancement-backed gym flags cannot gate dialogue". So a cache granted by advancement is
invisible to the dialogue system. That is acceptable for a stash in a cave and unacceptable
for a cache an NPC must later refer to; those go through (c).

## What must be proven in a running game before this is trusted

None of the following has been run. The first three are one two-player session and should be
scheduled together with the badge-flag two-player proof that already blocks play
(`docs/STATE.md`, "Badge flags").

1. **The trigger fires.** A `minecraft:location` advancement with an authored position range
   is granted to a player standing in the box on a dedicated server, within an acceptable
   delay, and is **not** granted to a player who has not been there. The trigger type is a
   design choice, not yet a fact: `minecraft:location`, `minecraft:item_used_on_block` on the
   container, and a `tick`-driven `execute as @a[...]` are all candidates and none is verified.
2. **The reward function runs as the earning player and its `give` is checked.** Reuse the
   discipline `tools/compile_dialogue.py:145-152` already established: store the give's
   success into a scoreboard objective that is created first, and leave a tag on failure,
   because a full inventory eats a `give` silently. An unverified give is a lost reward.
3. **Two players, independently, once each.** Player A triggers and receives; player B is
   unaffected until B triggers; neither can trigger twice; nothing a player does grants
   another player's advancement.
4. **It survives the re-export.** `advancements/<uuid>.json` is a required carry category
   (`tools/carry_players.py:65-68`) and the carry was rehearsed on `cobblers-dryrun4`
   (EXP-027) — but for badge flags, not for a reward advancement. Re-run the same check with a
   cache advancement set, then confirm the reward is not granted a second time in the new
   world.
5. **Presentation.** `show_toast` and `announce_to_chat` produce the intended reveal (a hidden
   stash that announces itself in chat to everyone is not hidden).
6. **The scenery behaves.** A container whose `LootTable` was removed by the `clear_loot` path
   opens empty and stays empty, and is not re-stocked by any upstream reload.

Until items 1 to 3 pass, **no reward content is authored beyond one proof cache.** That is
principle 20 applied to this decision specifically: the campaign has 254 catalogued structures
and zero placed rewards, and the cheapest moment to be wrong about the mechanism is now.

## Consequences

- **Easier:** rewards stop being blocked on an unanswered question; the mechanism reuses a
  generator, a re-apply discipline and a carry step that all already exist and have all been
  run at least once; multiplayer correctness is a property of the mechanism rather than
  something each cache must get right.
- **Harder:** a reward becomes two artefacts — a record in `data/rewards.json` and a scenery
  placement with a `reapply.py` step — instead of "put a chest there". Placing a cache by hand
  in game will not survive and must be refused by tooling, not by memory.
- **A new file needs an owner.** `data/rewards.json` is campaign content data; on the
  `docs/STATE.md` ownership table it belongs with `datapack-content-dev`, alongside the future
  `data/events.json`, and its validator belongs to `test-author`. That row must be added when
  the file is created, not after.
- **Entangled with GAP 1.** What is worth putting in a cache depends on what the world
  otherwise supplies, and today it supplies very little: no evolution-stone ore generates
  anywhere (`docs/mechanics/SPAWN_PHILOSOPHY.md`, "The rosters carry families this world
  cannot finish"), no berries, mints, apricorns or fossils, and the trader stock policy
  withholds whole categories (`data/traders.json:227-245`). If the scatter pass lands first,
  most of the reward list stops being reward-worthy. **Sequence these two decisions
  deliberately.**
- **Revisit when:** the two-player proof runs; a native Cobblemon per-player container is
  shown to exist; or the campaign wants a *repeatable* reward, which an advancement cannot
  express at all.
