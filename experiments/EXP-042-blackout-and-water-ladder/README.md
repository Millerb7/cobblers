# EXP-042: Blackout, recovery claims and the water ladder, in game

**Objective:** prove `cobblers_blackout` (tools/blackout_pack.py, data/blackout.json, data/water_mounts.json) against
`docs/mechanics/DEATH_AND_WIPE.md`'s required functional proof. It is built on EXP-038 to EXP-041 and ADR-005's
datapack-and-MoLang route; no companion mod.

Versions: Minecraft 1.21.1 Fabric, Cobblemon 1.8.0, CobbleDollars 2.0.0 Beta 5.1, staging world `cobblers-dryrun11`,
with the pack installed world-local.

## Implementation (one datapack)

| Part | Mechanism |
|---|---|
| Death | vanilla `deathCount`; charged the tick it happens, then returned on the first living tick |
| Full-party battle loss | `data/cobblers/callbacks/battle_victory/blackout.molang`: each player loser runs `battle_loss_wild`, `battle_loss_npc` or `battle_loss_other` with the victor's UUID |
| One incident | a second blackout report within 200 ticks is dropped |
| Money | `cobbledollars query` into a score; `ceil(balance * 10 / 100)` removed by macro |
| Checkpoint: Center | vanilla `any_block_use` on `cobblemon:healing_machine` inside a Center's 48-block box; the saved point is where the player stood; also their spawnpoint |
| Checkpoint: waystone | a jump of at least 48 blocks in 5 ticks that lands within 4 blocks of a town waystone |
| Fallback | a checkpoint the data no longer has, or a saved point no longer at it, sends the player to Hometown `(1461, 118, 5306)` |
| Return | teleport, `healpokemon`, Resistance V for 5 s, the result message |
| Claim | wild victor only; quotas across the whole inventory (balls 15% max 10, medicine 15% max 6, a 35% chance of one battle or evolution item); written to `storage cobblers:recovery claims` before anything is taken |
| Guardian | vanilla `PersistenceRequired`, tag `cobblers.guardian`, a guardian number (score `bo.g`, tag `cobblers.g<N>`) |
| Maintenance, every 100 ticks | a guardian more than 24 blocks from its site is walked back; a duplicate is removed; one absent while its site is loaded, on two passes in a row, is rebuilt from the ledger |
| Resolution | the guardian beaten (`battle_victory`) or caught (`pokemon_captured`) resolves every open claim it holds; the stacks drop at the owner's feet as owner-only, non-despawning items, now or at next login |
| Water | eyes 5+ blocks under water is depth. With no support: vanilla air, then a drown hit of half maximum health every 20 ticks. Surf training plus a capable party member: 900 ticks of water breathing per submersion. Dive: unlimited. The party is read once a second by `callbacks/player_tick_pre/water_mounts.molang` |

## Results so far (staging, 2026-09-26, no player online; run over RCON)

1. **The pack loads.** No function fails to load. Cobblemon's callback count went from 7 to 10: our three callbacks
   register in our namespace. `keepInventory` became `true`. All `bo.*` objectives exist.
2. **Rebuild from the ledger, from the tick loop: PASS.** A penned level-12 Rattata holding a gold ingot was bound to
   a synthetic claim, then killed.
   - Maintenance pass 1 marked it missing.
   - Pass 2 rebuilt exactly one guardian: the same Pokemon UUID, species and held item, `PersistenceRequired: 1b` and
     guardian number 9001.
   - It stayed one across 4 more passes.

   `spawnpokemonat` works inside functions, including from the tick loop. That contradicts the STATE line that said it
   did nothing inside a function (see "Findings").
3. **Leash: PASS.** Teleported 30 blocks off its site, the guardian was walked back to the site within one pass.
4. **Duplicate: PASS.** With two entities holding the same guardian number, one pass left one.
5. **Resolution: PASS on the second run.**
   - The first run exposed an ordering bug: the guardian was released before the claim resolved, and a guardian with
     no number left the claim open with the guardian unprotected.
   - Fixed: `defeated` refuses a guardian with no number, resolves first, and releases after.
   - Rerun: the claim moved to `deliver` with the resolver recorded, and the guardian lost its tag, number and
     persistence. A pass later, nothing was rebuilt for the settled claim.
6. **Not yet run: everything that needs a player.** That is the charge, the checkpoints, a real battle loss, capture,
   delivery, and the whole water ladder.

## In-game test (the owner; staging)

Setup, done over RCON before each part:
- test items: 20 Poke Balls, 10 Potions, a Fire Stone;
- a known balance;
- the Surf or Dive training tag.

1. **Drowning with no mount.** At Shrew Lake `(2873, 107, 3988)`, 46 deep, swim straight down.
   - Expect the air-low warning, then out of air, then one hit to half health and "One more drowning hit...", then a
     knockout on the second.
   - Then: the return to the checkpoint, "Lost $X" (10% rounded up), "No items were lost.", every item still carried.
   - Your position is logged every half-second to measure how fast a player sinks and swims.
2. **Center checkpoint.** Use a healing machine; expect "Checkpoint: ...". Drown again; you return there.
3. **Surf.** Grant Surf and have a Surf-capable Pokemon (Lapras) in the party. Dive at Shrew: air stays full for about
   45 s, then vanilla air, then the harsh rule.
4. **Dive.** Grant Dive and have a Dive-capable Pokemon (Wailmer) in the party: air never drops at the bottom.
5. **Swap.** Underwater, move the capable Pokemon to the PC: expect the warning and, 5 s later, vanilla air (not a
   fresh Surf timer).
6. **Wild battle loss.** Lose a full party to a strong wild Pokemon.
   - Expect "<Pokemon> took 3 Poke Ball(s), 2 medicine..." (and perhaps the Fire Stone), the charge once, and the
     return.
   - Expect the victor to stay at the site across a relog.
7. **Recovery.** Go back and beat it, then catch it, in two runs. Every stack drops at your feet, only you can pick
   it up, and you get "You recovered your supplies." Nothing is left guarding.

## Findings

- `docs/STATE.md` said `spawnpokemonat` "does nothing inside a function" (2026-09-25). On 2026-09-26 it spawned from a
  function run over RCON and from the tick loop. The context of the earlier failure is not recorded.
- `summon cobblemon:pokemon` is refused even with a full `Pokemon` compound, both from the console and through a
  function macro. The rebuild therefore uses a placeholder from `spawnpokemonat` with the snapshot written over it.
  That preserves the Pokemon UUID, level and held item (checked with `data get`); whether the client renders the new
  species correctly is not seen yet.
- `/checkspawn` evaluates the whole spawning zone around the player (CheckSpawnsCommand source), not only the player's
  block.

## Limits (known and recorded)

- **Trainer claims:** an NPC loss takes no items yet. They bind to the route trainers, which are not built.
- **Nested inventories:** backpacks, bundles and shulker boxes are not scanned. The spec requires this proof before
  release.
- **No display item** on the guardian (the spec's visible cue); nothing is duplicated by a catch as a result.
- **A Pokemon knockout outside battle** (Fight or Flight) is environmental: no item claim. Vanilla does not name the
  attacker to a function (EXP-039).
- **Vanilla air items** (Respiration, turtle shell, Water Breathing potions) still work. `docs/world-building/OCEAN.md`
  and the spec disagree about them.
- **Nuzlocke handling** is not built.
