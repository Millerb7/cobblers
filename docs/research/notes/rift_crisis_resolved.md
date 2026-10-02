# rift_crisis_resolved: its setter, and what still invokes nothing

2026-10-02, minecraft-systems-dev, on `build/2026-10-02-consolidation` (from dcb9f67).

## Was there a setter?

No. Measured, not relayed:

- `grep rift_crisis_resolved` over `data/`, `tools/`, `tests/` at dcb9f67: no flag in
  `data/progression.json` (`flags[]` held nine, all `set_by.kind: trainer_defeat`), no dialogue node
  invoking `unlock_league_after_rift_resolution` (`data/quests.json`, whose `external_trigger_contract`
  said so), no tool emitting a grant.
- `git log --all -S rift_crisis_resolved` after `git fetch --prune`: no commit on any ref adds a setter.
- **The finale IS written, on an unmerged local branch.** `docs/story/NPCS_AND_RIFT_FINALE.md`
  (commit `9cbfd213`, "Author all route trainers and Rift finale handoff") exists only on the LOCAL branch
  `codex/trainer-modes` (`git branch -a --contains 9cbfd213` lists nothing else; it is not an ancestor of
  HEAD and is on no remote). Its Scene 5 is the setter's beat. STATE's "no setter on any remote branch" was
  true and missed this.

## The beat (decided by Codex, not by this unit)

`NPCS_AND_RIFT_FINALE.md` "Scene 5 - Hoopa's cradle": actor `actor_finale_hoopa`, restrained Hoopa, at the
cradle centre **(3357, 12, 3306)** (reserved box `[3317,-12,3266,3397,72,3346]`, `data/deep_city.json`);
reads `stage == cradle_open`; player choice **"Release Hoopa."**; writes `rift_crisis_resolved = true`,
`stage = rift_released`, League cursor `league_001`. Those last two writes are exactly the existing
transition `unlock_league_after_rift_resolution`'s effects, so that transition is the setter. ARC.md
("The final story confrontation ... sets `rift_crisis_resolved`") and FACTION.md ("Releasing Hoopa sets
`rift_crisis_resolved`") agree on the moment; ARC left the mechanism to "the progression schema pass".

No battle sets it (no Elara/Brann trainer exists in `data/trainers.json`; Codex: "No capture occurs here"),
so the RCT `defeat_count` mechanism the gym flags use cannot be the setter.

## What was built (the setter, not the beat)

Mechanism, copied from existing usage, nothing new invented:

- the flag is an advancement `cobblers:flag/rift_crisis_resolved` with a `minecraft:impossible` criterion,
  as `tools/progression_pack.py` already emits for `trigger` flags;
- new `set_by.kind: quest_transition` emits `function cobblers:flag/<id>/grant` =
  `advancement grant @s only cobblers:flag/<id>` (the command `progression_pack` already uses in its tick);
  no `/trigger` is exposed, so typing cannot set the finale;
- the transition's FIRST effect is `{"kind": "function", "function": "cobblers:flag/rift_crisis_resolved/grant"}`,
  the same construct as `relic_hq_admit` -> `cobblers:relic_underground/hq_admit`
  (`tools/compile_dialogue.py` runs it `execute as <uuid> at @s`).
- `league.unlocked_by` = `[gym8_cleared, rift_crisis_resolved]` (`data/rift_zones.json`
  `zones.z5.needs_progression.change_node`). The chapter ledger is read only by `validate_data`; the
  in-game League gate (RCT's chain) is unchanged.

## What is NOT built, and why

The invoker. `set_by.invoked_by` is `null` with `invoked_by_owed`. A Hoopa actor needs a
`data/scenes.json` scene, and an NPC-less conversation with no scene is a `validate_data` error; the scene
needs markers in a chamber that is not carved (`data/relic_underground.json`: the passage "carves to its
doorstep and no further"). Seating it in rock would be speculative. So **nobody can hold the flag yet**,
`tools/rift_zones.py report` now owes "the invoker" instead of "the setter", and z5 stays held.

## State model

Per player, like every flag: an advancement on the player's record. Late joiner, different order: each
player releases Hoopa for themselves. Death: no effect. Disconnect mid-dialogue: the transition runs inside
one Molang action (grant, then stage, then `save_data`); a grant without the stage write leaves the player
re-offered the choice, and a re-grant is a no-op that does not rerun the reward.

## Owner calls

1. **Merge or port `codex/trainer-modes`'s `NPCS_AND_RIFT_FINALE.md`.** It is the only authored finale and
   lives on one local branch.
2. **Stage gate.** Codex gates the release on `cradle_open` after four intermediate stages (Nia, Brann,
   Oren, Elara). Today the transition reads `rift_crisis_pending`. Keep it (finale = one beat) or add
   Scenes 1-4 first (cost per Codex: M+M+L+M).
3. **Multiplayer.** Codex asks for "one release ... advance every eligible player once". Built: per player.
   A shared release is world-scoped state the dialogue compiler refuses.
4. **The invoker**: carve the cradle (`data/deep_city.json` reserved box), then a scene with
   `actor_finale_hoopa` and the Scene 5 conversation; set `invoked_by`. Hoopa's model is unverified on the
   client (`data/relic_underground.json`).

## Apply

Pack `cobblers_progression` (`tools/reapply.py` prepare job `progression_pack`; the pack is "self-driving",
no world step) must be rebuilt and installed to carry the grant function and advancement. No dialogue pack change takes effect (nothing invokes the transition).
`cobblers_rift_zones` stays EXCLUDED.

## Tests

`tests/test_rift_crisis_resolved.py` (11): declared once with the quest_transition setter; exactly one
transition in data calls the grant, as its first effect, before the stage moves; no other data record
calls it or raw-grants the advancement; the generator emits the grant with exactly one command; the
advancement is `impossible`-only with no trigger/tick grant; only quest_transition flags get a grant; the
compiled transition holds the call before `rift_released`; `invoked_by` equals the conversations that
invoke the transition (none); `plan()` rejects a malformed setter. Mutating the generator's grant to `@a`
fails the suite.
