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
| Full-party battle loss | `data/cobblemon/callbacks/battle_victory/cobblers_blackout.molang`: each player loser runs `battle_loss_wild`, `battle_loss_npc` or `battle_loss_other` with the victor's UUID |
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
| Water | eyes 5+ blocks under water is depth. With no support: vanilla air, then a drown hit of half maximum health every 20 ticks. Surf training plus a capable party member: 900 ticks of water breathing per submersion. Dive: unlimited. The party is read once a second by `data/cobblemon/callbacks/player_tick_pre/cobblers_water_mounts.molang` |

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
6. **The callbacks did not run at first: FIXED.** Files under `data/cobblers/callbacks/<event>/` register (the count
   rose) but never fire. A tracer at the top of the script counted 0. Moved beside Cobblemon's own files as
   `data/cobblemon/callbacks/<event>/cobblers_*.molang`, the same tracer counted every tick. This corrects EXP-038's
   assumption that a custom namespace works. The files are additions (`cobblers_` names), not overrides.

## Results in game (the owner, staging, 2026-09-26)

Party: Marshtomp, Finneon, Dubwool, Swablu, Phantump, Voltorb, then a level-40 Lapras in place of one. Balance
$725. Logged over RCON every half-second.

**Run 1: drowning with no mount, Shrew Lake. Mostly PASS; one fix.**
- The party read gave mount level 0 (no water mount), which is correct.
- At depth, the air-low warning fired at air 60.
- At air 0, the first hit took **20 → 10**, exactly half.
- **FAIL:** natural regeneration healed the player to 11, the second hit left 2 and a third killed. The spec wants two
  hits from full health.
  - Fixed: a hit landing at or below half health plus `pulse_regen_margin` (2) is lethal.
  - Not rerun yet.
- Death: charged **$73** (10% of 725, rounded up), balance **$652**, once.
- The return: respawned at Hometown `(1461, 118, 5306)` with no checkpoint saved, spawnpoint set there. The owner
  reported the respawn.
- Passive sinking, not swimming: 0.55 blocks per second.

**Run 2: Surf, Shrew Lake. PASS.**
- With the Surf training and the Lapras in the party, the party read gave mount level **1** and qualification **1**.
- The owner reached the floor at **y56**, 50 blocks below the surface at y106.
- The Surf timer used its whole **900 ticks** (45 s) with air held full.
- After it, vanilla air was draining (216 of 300 when read).
- The owner: "it works". The Lapras did not know the move Surf, and it does not have to: capability is the species'
  riding data (spec: "not merely knowledge of a move").
- The owner logged off before drowning, so the second-hit fix is still unrun.

**Not registered: the Center checkpoint.** The checkpoint stayed at 0. The owner is unsure whether they used the
healing machine, so this is not a result either way; rerun it.

**Session 3 (the owner, staging, 2026-09-26). PASS except as noted.**
- **Center checkpoint:** "Checkpoint: the Hometown Pokemon Center" on the action bar when the owner used the healing
  machine (checkpoint id 1). The later drowning returned them inside the Center at (1438, 120, 5248).
- **Vanilla air removed:** one yellow message. The Water Breathing potion's effect was stripped. Air drained at the
  vanilla rate, 300 to 0 in about 14.5 s, with the Respiration III helmet given for the test (worn, per the owner).
  The Respiration override needed a restart: enchantments are registry data, which `/reload` does not refresh.
- **Lethal second hit:** 20 → 10 at air 0, regenerated to 11, then the second hit killed. Fix confirmed.
- **Charge:** $59, 10% of 586 rounded up, once.
- **Dive:** Wailmer in the party, Dive training: mount level 2, qualification 2.
  - Air held flat for over two minutes at the floor (248 of 300: the oxygen bonus holds air, it does not refill it).
  - The Surf timer counted up under Dive, reaching 900, so a swap cannot hand out a fresh Surf bonus. Fix made this
    session.
- **Swim speed, no boost (survival):**
  - down 47 blocks in 9.4 s, about 5.0 blocks per second;
  - up 50 blocks in 10.1 s, about 4.9 blocks per second;
  - peaks 6-7.

  **The map's assumed 5 blocks per second holds.**
- **Dive swim boost (the owner's request):**
  - Water movement efficiency 0.5 alone felt like nothing: the owner said "it feels slow". It is Depth Strider's
    attribute, which mostly helps walking in water.
  - Adding +50% movement speed in water: about **10 blocks per second** sustained over 2 s (diagonal).
  - The owner: "its good".
- **Not run: the mid-dive swap.** The owner declined.
- The owner switched to creative now and then. Those samples (mode 1) are excluded from every speed figure.

Still to run (after session 3):
- the town waystone checkpoint;
- the mid-dive swap (the owner declined it);
- a wild battle loss, recovery by defeat and by capture, and delivery, including to an offline owner and through a
  helper;
- a trainer loss (money and the return only; no claim).

Fixed after session 3, from independent tests (tests/blackout-and-water):
- a Center checkpoint saved at the edge of its area;
- the charge overflowing for huge balances;
- an aborted claim left open in the ledger;
- the Surf bonus one tick short.

The claim ledger also moved to its own storage, `cobblers_recovery:ledger`, so a re-export carries it (and never
carries the re-apply's progress). The guardian rebuild was re-run on the new ledger: PASS (one guardian, the same
Pokemon and item).

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
