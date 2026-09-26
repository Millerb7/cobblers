# EXP-039: Which events identify a full-party loss, a wild knockout and a trainer loss, with a stable victor?

**Spec question** (`docs/mechanics/DEATH_AND_WIPE.md`, open technical question 1): which exact Cobblemon callbacks
distinguish a full-party loss, a direct wild Pokemon knockout and a trainer loss, and do they give stable victor IDs?
Rule 5 requires this: only an identified Pokemon or trainer victor may create an item claim.

Versions: Cobblemon 1.8.0, rctmod (Radical Cobblemon Trainers) as installed, Minecraft 1.21.1 Fabric.

## Findings so far (VERIFIED from the jar)

- **Events.** `CobblemonEvents` exposes `BATTLE_VICTORY`, `BATTLE_FAINTED`, `BATTLE_FLED`, `POKEMON_FAINTED`,
  `BATTLE_STARTED_PRE/POST` and others. A datapack reaches them through MoLang callbacks under
  `data/<ns>/callbacks/<event>/`.
- **What a battle callback can see.** Cobblemon's own `callbacks/battle_victory/npc_battle_end_scripts.molang`
  iterates `c.scriptable_losers` and `c.player_winners`:
  - a loser `is_npc` or `is_pokemon`;
  - the winner exposes `.player`;
  - battle functions give `battle_id`, `battle_type`, `is_pvw` / `is_pvn` / `is_pvp` and `get_actor`;
  - actors give `is_wild`, `is_npc` and `is_player`.

  So a **full-party loss to a wild Pokemon or to an NPC** is visible as a `battle_victory` whose losers include the
  player, with the winning actor's identity available.
- **Stable victor IDs** (ASSUMED until the test): a wild winner's entity UUID and `pokemon.uuid`; an NPC winner's
  entity UUID. RCT trainers must be checked: whether their battles run through Cobblemon's NPC actor, and whether
  RCT's own trainer id is reachable.
- **Direct wild knockout** (a Minecraft death with a Pokemon as the damage source, since Fight or Flight makes wild
  Pokemon attack players). Vanilla's `entity_killed_player` advancement trigger can test the killer's type
  (`cobblemon:pokemon`) and run a function as the player. **Which** Pokemon entity it was is not passed to the
  function. That is ASSUMED and is the crux for the item claim: without the killer's UUID, rule 5's safe default
  applies (environmental outcome, no item claim).

## Test (in game, a player online, disposable or staging world)

1. Lose a full party to a wild Pokemon. A logging callback in `battle_victory` and `battle_fainted` records the actor
   kinds and UUIDs.
2. The same against an RCT trainer and a Cobblemon NPC.
3. Be killed by a Fight-or-Flight wild attack. Check that `entity_killed_player` fires, and whether any path (an
   advancement, a `PLAYER` death event through MoLang, or a scoreboard) yields the killer's UUID.
4. Fall or drown right after a battle. Confirm nothing attributes it.

## Result

Static only; not run.
