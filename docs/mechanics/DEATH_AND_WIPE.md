# Death, wipe, recovery and water depth

**Status:** approved design direction; no runtime handler, recovery claim,
checkpoint hook or water-depth rule in this document is implemented or
runtime-proven.

This is the single specification for blackout, recoverable losses and deep
water. It supersedes earlier death-only wording in this file.

## Rules that must survive implementation

1. A Minecraft player knockout and a full-party Cobblemon loss use the same
   blackout pipeline.
2. The player returns to the last Pokemon Center they successfully used or the
   last town waystone they successfully travelled through.
3. The player's ordinary inventory is kept. The blackout handler removes only
   the bounded eligible items described below.
4. Every blackout loses 10% of current CobbleDollars, whether the cause was a
   Pokemon, trainer, fall, lava, drowning or another environment hazard.
5. **Items are lost only when a Pokemon or trainer defeated the player. The
   Pokemon or trainer that won holds the recovery claim. Environmental death
   never loses items.** Drowning, falling, lava, the void, suffocation, commands,
   PvP and damage with no confidently identified Pokemon or trainer cost money
   and a checkpoint return only.
6. TMs, permanent move unlocks and Minecraft tools are never eligible. Balls,
   medicine, consumable battle supplies and evolution stones may be eligible.
7. Recoverable items never decay. Recovery requires the victor to be defeated
   or caught. The saved claim, rather than an entity held-item slot, is the
   authority.
8. Shorelines, rivers and shallow water remain ordinary water. The harsh air
   rule begins only at actual depth.
9. With no qualifying mount Pokemon, a player has vanilla air. When it is gone,
   each drowning pulse deals half the player's maximum health; two pulses knock
   out a player who entered them at full health.
10. An unlocked Surf ability plus a qualifying Pokemon in the active party gives
    bonus air. An unlocked Dive ability plus a qualifying Pokemon gives unlimited
    air.

If cause attribution is uncertain, the system must choose the environmental
outcome: money and teleport, with no item removal. It must never guess a holder.

## Terms and attribution

- **Blackout:** the common transaction caused by Minecraft player death or a
  full-party Cobblemon battle loss.
- **Battle defeat:** an explicit Cobblemon loss callback with a stable opposing
  wild Pokemon or trainer identity.
- **Pokemon knockout:** a Minecraft death whose direct damage source is a
  specific Cobblemon Pokemon entity.
- **Environmental death:** every death without a confidently identified Pokemon
  or trainer victor, including environmental damage shortly after combat.
- **Recovery claim:** the persistent owner-and-victor record containing the
  removed item stacks.
- **Guardian:** the exact wild Pokemon bound to a recovery claim.

Do not use a “recently attacked” timeout to turn later drowning, lava or fall
damage into a Pokemon defeat. Only the explicit battle result or the direct
lethal Pokemon source can create an item claim. A single incident ID deduplicates
a battle-loss callback and a player-death callback from the same defeat.

## Blackout transaction

The server performs one idempotent transaction:

1. Record an incident ID, cause, player UUID, dimension, safe defeat coordinate,
   current checkpoint and, when present, the wild Pokemon UUID or stable trainer
   ID.
2. Read the CobbleDollars balance and calculate 10%, rounded up, with a minimum
   loss of 1 when the balance is above zero.
3. If and only if the cause has a Pokemon or trainer victor, select recoverable
   items from one complete inventory snapshot and prepare a claim.
4. Persist the incident and any claim before debiting money or removing items.
5. Debit money and remove the selected items atomically on the server thread.
6. Bind the claim to the wild guardian or trainer. Environmental incidents skip
   this step and have no claim.
7. Teleport the player to their checkpoint, clear combat pursuit and grant short
   arrival protection.
8. In standard play, heal the party as a Pokemon Center blackout would. Formal
   Nuzlocke handling is different below.
9. Deliver the player-facing result after the destination loads.

If persistence fails, abort before charging anything. If teleporting fails after
commit, reconnect recovery completes the teleport without charging again.

## Checkpoints

Each player stores one `last_safe_checkpoint` with a stable place ID, dimension,
coordinates, facing, source type and update time.

- A Pokemon Center becomes the checkpoint only after a successful healer use.
- A town waystone becomes the checkpoint only after successful travel through
  that waystone. Discovery and proximity are insufficient.
- Route midpoint waystones are not safe checkpoints unless later promoted by an
  explicit campaign decision.
- A player with no record returns to the Pallet/Hometown campaign spawn.
- Before use, validate the checkpoint against the current placement manifest. A
  moved or removed checkpoint falls back to Pallet rather than an obsolete
  coordinate.

The Center and Waystones hooks are not yet proven in this pack.

## Money and eligible items

Money loss is permanent and never enters a recovery claim. The initial value is
**10% of current CobbleDollars, rounded up**, minimum 1 above a zero balance and
with no cap. Keep the percentage configurable for playtesting.

Item selection is calculated by category across the entire carried inventory,
not per stack, so splitting stacks does not reduce the loss.

| Category | Initial amount placed in the claim | Included | Excluded |
| --- | --- | --- | --- |
| Ordinary Poke Balls | 15% of carried quantity, rounded up, maximum 10 | Purchasable and craftable balls | Master Ball, Ancient Origin Ball, unique and story balls |
| Medicine | 15%, rounded up, maximum 6 | Healing, status cures, Ether-like supplies and revives | Key and story medicine |
| Battle and evolution consumables | One random eligible item, 35% chance when any are carried | Evolution stones and consumable battle items | Permanent unlocks and quest items |

Never select:

- TMs or other permanent move unlocks;
- Minecraft tools, weapons, armour, buckets or navigation equipment;
- badges, trophies, key items, books, maps, Pokedexes or quest objects;
- equipped accessories;
- a Pokemon's held item;
- backpacks or other storage containers themselves.

Eligible supplies inside a protected backpack still count. Otherwise a backpack
is free wipe insurance. Nested inventories are a required proof before release.
Evolution stones are eligible only because claims do not expire and cannot be
stolen; if either guarantee fails, evolution stones must be removed from the
loss pool.

An environmental death does not run item selection at all. It does not create an
empty claim, a satchel or a later recovery objective.

## Recovery claims

The authoritative record contains:

- claim ID and transaction state;
- owner UUID and display name;
- victor kind and stable victor identity;
- defeat dimension, exact point and ground-safe guardian point;
- all removed stacks, including item components;
- for a wild guardian, its UUID, serialized Pokemon snapshot and original held
  item;
- for a trainer, its stable campaign trainer ID;
- resolution state, resolver UUID and timestamps;
- source world/export generation for re-export rematerialization.

Claims persist indefinitely. Repeated wipes may create multiple claims. Losing
again to the same unresolved guardian appends newly selected items to that
owner's existing claim after a new money charge; it never duplicates old items.

### Wild Pokemon victor

The exact victor is tagged with the claim ID and exempted from normal despawn. In
a multi-Pokemon battle, use the surviving opponent that landed the final faint;
if the event cannot prove that, use the surviving active opponent. If neither is
known, create no item claim.

The guardian remains near the defeat site and visibly presents the most
recognizable claimed item, preferring an evolution item over medicine and
medicine over a Ball. This is a non-droppable display mirror, not the stored
item. Preserve and restore the Pokemon's natural held item.

Defeating or catching the guardian resolves the claim atomically: lock the
claim, strip the display item and tag, deliver all stacks to the owner, mark the
claim resolved, then finish normal defeat or capture consequences. Overflow
becomes an owner-only package at the owner's feet or checkpoint.

If the entity despawns, unloads incorrectly or is absent after restart, the
claim remains and recreates exactly one guardian from its snapshot when the
area next loads. Duplicate entities with the same claim ID are removed. A catch
must strip the display item before the Pokemon enters storage so it cannot be
duplicated.

### Trainer victor

A trainer loss binds the claim to that trainer's stable campaign ID. No ground
satchel is created. The trainer must remain available for a recovery rematch even
if its ordinary battle is one-time or on cooldown. Beating that trainer resolves
only the viewing player's claims bound to it; a shared NPC must never expose one
player's inventory to another.

The trainer may show a generic owner-only cue that it is holding supplies. The
claim ledger remains authoritative because one shared trainer can hold separate
claims for several players and cannot represent them safely in one physical
item slot.

### Persistence, restart and re-export

Chunk unload, server restart and player logout do not age or delete a claim.
Store claims in campaign recovery data keyed by player UUID, mirror active IDs in
player-persistent data, and include the recovery store in the explicit re-export
carry manifest. The carry step must hash-check every claim file. On first boot of
the rebuilt world, validate coordinates and recreate guardians when their chunks
load; trainer claims rebind by stable trainer ID.

If terrain moved, search vertically and within a small bounded radius for safe
ground. If no valid guardian site or trainer exists, fail safe by returning the
items directly to their owner and logging the broken claim. Do not turn them into
environmental ground drops; that would violate the holder rule and risk loss.

## Multiplayer policy

Default to **rescue without theft**:

- another player may defeat or catch a wild recovery guardian;
- the Pokemon goes to that player if the capture is otherwise legal;
- every cached item goes to the claim owner, never the helper;
- an offline owner receives the items once on next login;
- helpers cannot inspect another player's cache;
- trainer claims remain per player even though the trainer entity is shared.

This keeps the useful co-op story—“I found the Pokemon that wiped you”—without
turning a private campaign into theft or allowing accidental capture to delete a
friend's Thunder Stone. If the owner wants the literal rematch, friends can leave
the guardian alone. Owner-only resolution may be offered as a server policy, but
helper theft must not be the default.

Authored one-time Pokemon and capture locks take precedence. A helper may return
the items without receiving an encounter that is normally non-catchable.

## Player-facing messages

Messages are short and explicit. Item-loss text appears only after an attributed
Pokemon or trainer defeat.

| Moment | Required information | Recommended copy |
| --- | --- | --- |
| Any blackout | Destination and money loss | `You blacked out and returned to <checkpoint>. Lost ₽<amount>.` |
| Environmental death | Explicitly confirm the scoping rule | `No items were lost. Nothing defeated you.` |
| Pokemon or trainer defeat with a claim | Holder, items and recovery action | `<victor> took <summary>. Defeat or catch it to recover everything.` |
| Attributed defeat with no eligible items | Confirm no hidden claim | `<victor> defeated you, but you had no eligible supplies to lose.` |
| Claim resolved by owner | Full return | `You recovered <summary> from <victor>.` |
| Claim resolved by helper | Both players understand ownership | Owner: `<helper> recovered your supplies from <victor>.` Helper: `Recovered supplies for <owner>.` |
| Air at 20% | First warning | `Your air is running low. Surface now or rely on a trained water mount.` |
| Air reaches zero | Harsh rule before damage | `You are out of air. Drowning here is lethal.` |
| First drowning pulse | One-pulse warning from full health | `One more drowning hit will knock you out.` |
| Surf or Dive interaction lacks unlock | Progress refusal | `You have not learned how to travel safely at this depth.` |
| Ability unlocked but no qualifying party Pokemon | Party refusal | `No Pokemon in your party can support you at this depth.` |

Ordinary open water is not blocked. A new player may swim toward a visible deep
reward and discover the risk. Refusal messages apply to marked Surf/Dive
interactions and destinations that require controlled descent, not an invisible
wall around every lake.

## Water and depth

### What is gated

This system gates **depth**, not access to water. Wading, shorelines, rivers,
surface swimming and shallow lake shelves use ordinary Minecraft behavior. Deep
lake floors, trenches and authored submerged sites create the risk.

The initial depth boundary is the player's eyes at least **five contiguous water
blocks below the local water surface**. Above that boundary, use vanilla air and
damage. This number is a tuning value and must be checked at Lake Viltri, a river,
the visible Dratini site and an ocean trench before it becomes final. A local
water-column measurement is preferable to a global Y threshold because the
region's lakes sit at different elevations.

### Ability model

Depth access has two requirements:

1. the per-player Surf or Dive training has been unlocked; and
2. a Pokemon with the corresponding verified water-mount capability is in the
   player's active party.

The Pokemon does not need to be visibly mounted while the player swims. “Mount
gated” means the party supplies a capable partner; it is not a level check and
not merely knowledge of a move named Surf or Dive. Dive includes Surf's benefit.
The exact capability source must be proven from the installed mount system; do
not infer a species list from mainline Pokemon games.

| State at depth | Air behavior | Drowning behavior |
| --- | --- | --- |
| No qualifying partner | Vanilla 300-tick air supply | After air reaches zero, each normal drowning pulse removes 50% of maximum health, bypassing armour; two pulses knock out a full-health player |
| Surf unlocked and Surf-capable partner in party | Hold vanilla air full for 900 bonus ticks, then allow the normal 300 ticks: about 60 seconds total | Same 50%-maximum-health pulse after the full allowance expires |
| Dive unlocked and Dive-capable partner in party | Keep air full while submerged | No drowning damage while qualification remains valid |

The 900-tick Surf bonus is an initial tuning value. It should permit work at a
lake bottom while preserving route choice and the danger of trenches. Dive is
the point where air stops constraining exploration.

Each 50% pulse is based on maximum health, not five fixed hearts. From less than
half health, the first pulse can knock the player out. The rule must be
server-authoritative and must not be weakened by armour. Whether Resistance or
other effects should mitigate it is an open implementation proof; the intended
result is two pulses from full health.

### Entering, swapping and leaving depth

- Re-evaluate ability and party qualification promptly while submerged. Prefer a
  party-change event plus a low-frequency safety check over a full party scan
  every tick.
- Surf bonus time belongs to one continuous submersion and does not reset when
  the player swaps Pokemon, crosses the deep boundary or relogs underwater. It
  resets only after the player's eyes remain in breathable air long enough for
  vanilla air to refill.
- Removing the qualifying Pokemon underwater starts a five-second warning grace,
  then downgrades to the best remaining state. It does not grant a fresh Surf
  timer.
- Logging out underwater stores the current exposure timer. Login rechecks the
  party before restoring the benefit.
- Death at depth follows the environmental rule unless a Pokemon or trainer was
  the explicit victor: money and checkpoint teleport, no item claim.

### Where Surf and Dive come from

**Surf:** Misty grants the player's Surf training after `gym2_cleared` at Lake
Viltri, as part of the lake-rescue chapter. It becomes useful immediately in the
first major lake and on previously seen deep shelves. It provides time to work
underwater without making trenches safe. The benefit activates only with a
verified Surf-capable partner in the active party.

**Dive:** after `gym6_cleared`, Sabrina directs the player to a glacial survey
diver on Lake Tilpey's north shore. The diver teaches the technique because the
player now understands the linked water, glacier and Rift evidence and is being
sent toward places where submerged investigation matters. Dive provides
unlimited air with a verified Dive-capable partner.

This timing changes the whole map:

- before Gym 2, visible deep rewards are warnings and future hooks;
- after Gym 2, lake bottoms become workable for a limited time;
- after Gym 6, air no longer protects any deep-water content from the player;
- late underwater set pieces such as the Lugia trench still need their own story
  gates if Dive alone must not open them.

Surf and Dive are traversal training, not TMs and not items that can be lost.

## Nuzlocke compatibility

A formal Nuzlocke distinguishes player death from Pokemon death:

- A Pokemon faint in battle is that Pokemon's Nuzlocke death. It does not create
  a blackout or recovery claim unless the whole party loses or the player is
  also knocked out.
- A full-party battle loss retires every fainted party member, then applies the
  same money loss and recoverable claim. The checkpoint return must not revive
  those Pokemon. The player withdraws legal reserves; with none, the run ends
  under that ruleset.
- Drowning, falling, lava and other environmental player deaths are **player
  deaths, not Pokemon deaths**. They lose money and return the player, but do not
  retire party members and never lose items.
- Riding or being supported by a Pokemon when the player drowns does not turn the
  event into a Pokemon faint unless Cobblemon separately reports that Pokemon as
  fainted.

The item system does not make a Nuzlocke inherently unplayable because claimed
items are recoverable indefinitely and cannot be stolen. It does compound the
cost of a full-party wipe, which is already the harshest Nuzlocke outcome. Start
with the same recoverable-loss rules so the campaign has one understandable
economy; add a reduced-loss Nuzlocke profile only if playtests show the rematch
loop prevents rebuilding a legal reserve team. Never solve that by reviving
fainted Pokemon or by making claims expire.

The installed Cobblemon configuration wakes fainted Pokemon after 300 seconds at
20% health, so a formal Nuzlocke still needs a separate retirement mechanism.
Self-imposed runs must retire Pokemon before that timer completes.

## Existing runtime behavior and implementation boundary

- Cobblemon 1.8 exposes battle faint/victory events, Pokemon persistent data,
  held-item access, entity save/load events and despawner interfaces. These are
  useful extension points, not proof of this design.
- A saved Pokemon appears to carry held-item data through normal serialization,
  but natural spawns can still be removed under spawn pressure. A held item on
  the entity is therefore presentation only.
- Cobbleverse ships Lenient Death 1.2.5, which can preserve key items and tools
  and manage ordinary drops. It does not handle Cobblemon party wipes,
  CobbleDollars, victor-bound claims or re-export persistence.
- Vanilla `keepInventory` cannot implement selective recovery. The companion
  handler must snapshot the inventory, suppress ordinary drops and remove only
  selected stacks after claim persistence succeeds.

The combined event attribution, atomic money and inventory transaction,
persistent claim ledger, guardian reconstruction, trainer binding, per-player
air state and party capability checks justify one small server-side companion
module unless an existing addon proves the entire state machine. Commands and
datapacks alone are not a safe escrow system.

## Design risks that must not be hidden

- A literal held item on a wild Pokemon is not durable enough to be the player's
  property. The claim ledger must be authoritative even though the fiction says
  the victor holds the items.
- A trainer is one shared entity while losses are per player. Any global trainer
  inventory or visible owner name would leak state; trainer presentation and
  recovery must be viewer-specific or generic.
- “Mount gated” and “in the party” are not the same as “currently riding.” This
  specification chooses unlocked training plus a capable active-party Pokemon.
  If the installed mount system cannot expose Surf and Dive capability, Claude
  must stop and return that finding instead of guessing species.
- Half maximum health per drowning pulse can feel instantaneous under lag or a
  missed warning. The severity is intentional, but it is acceptable only if the
  shallow/deep boundary, client warning and server pulse timing are proven
  together.
- Dive at Gym 6 removes air as a gate everywhere. Any underwater place intended
  for later progression needs an independent story gate; hiding it behind depth
  after Gym 6 will not work.
- Evolution stones are unusually scarce in the pregenerated world. Keeping them
  eligible is defensible only because recovery is indefinite and theft-free.
  Any implementation that can permanently lose a claim must exclude them.

## Open technical questions for Claude

These must be answered in disposable-world experiments before implementation is
called complete:

1. Which exact Cobblemon callbacks distinguish a full-party loss, a direct wild
   Pokemon knockout and a trainer loss, and do they provide stable victor IDs?
2. Can CobbleDollars balance read and percentage deduction be committed in the
   same server-thread transaction as claim persistence and inventory removal?
3. Can Center healer use and successful town-waystone travel update the correct
   player's checkpoint without false updates from proximity?
4. Can a wild guardian be excluded from Cobblemon's despawner and reconstructed
   exactly once after chunk unload, restart and a forced removal?
5. Does a Pokemon's real held item survive chunk unload and restart, and can the
   visual recovery item be stripped before capture without duplicating or
   deleting the natural held item?
6. Can a shared trainer expose and resolve owner-specific claims, including a
   recovery rematch that bypasses ordinary one-time or cooldown rules?
7. Can air supply be changed per player while keeping the client bubble display
   accurate, or should Surf use a separate server timer with explicit UI?
8. Can party contents and verified mount capabilities be read on party-change
   events and at a safe polling rate? What API identifies Surf-capable and
   Dive-capable mounts in this installed pack?
9. What happens when a player swaps the qualifying Pokemon, changes dimension,
   disconnects or dies while the water timer is active?
10. Can the server apply a 50%-of-maximum-health drowning pulse that bypasses
    armour consistently, and how do Resistance, regeneration and lag affect the
    promised two-pulse result?
11. Does five blocks below the local surface correctly separate shallow water
    from depth across rivers, Lake Viltri, Lake Tilpey, the ocean and trenches?
12. Can helper defeat and helper capture resolve a wild claim exactly once and
    deliver only to an online or offline owner?
13. Does the re-export carry step preserve claims and water exposure state, and
    can it rebind every guardian and trainer claim without touching the live
    world during preparation?
14. Can nested modded inventories be scanned and modified atomically without
    losing item components or creating a backpack-based exemption?
15. How will a formal Nuzlocke suppress Cobblemon's five-minute passive revival?

## Required functional proof

A disposable-world test must demonstrate:

1. Battle loss and Minecraft death from one incident charge once.
2. Wild and trainer defeats create claims; drowning, fall and lava deaths never
   remove an item even when they occur immediately after combat.
3. Protected items remain, eligible items enter a claim, and nested containers
   cannot evade the policy.
4. The exact wild guardian survives or reconstructs after unload, restart and
   forced despawn without duplication.
5. Trainer rematch returns the correct player's items and exposes no other
   player's claim.
6. Owner defeat/capture and helper defeat/capture each resolve once, with offline
   owner delivery and no helper theft.
7. Re-export carry rematerializes unresolved claims at valid locations.
8. A river and shoreline remain vanilla; a deep unassisted player gets vanilla
   air and the two-pulse drowning rule.
9. Surf supplies the configured finite bonus and Dive supplies unlimited air.
10. Party swapping and relogging cannot reset the timer or retain a benefit
    without a qualifying Pokemon.
11. Standard blackout heals the party; Nuzlocke blackout does not revive or
    unretire any Pokemon.
12. Every warning and result message is sent only to the affected player and
    names the correct checkpoint, charge, holder and recovery outcome.

Until those pass, this document is an implementation specification, not a claim
that the campaign mechanic works.

## Evidence carried forward

- Repository runtime and world facts: `docs/STATE.md`.
- Cobblemon configuration: `modpack/config/cobblemon/main.json` and the reference
  pack's matching `base-pack/cobbleverse/config/cobblemon/main.json`.
- Lenient Death policy: `base-pack/cobbleverse/config/lenientdeath.json5` and
  [Lenient Death source](https://github.com/JackFred2/LenientDeath).
- Installed Cobblemon 1.8.0 jar: battle events, Pokemon persistent data,
  held-item access, entity save/load events and despawner interfaces.
- Installed CobbleDollars 2.0.0 Beta 5.1 jar: balance getter/setter and
  synchronous remove path.
- Cobblemon persistence caveats:
  [save-to-world issue](https://gitlab.com/cable-mc/cobblemon/-/issues/269) and
  [forced-despawn issue](https://gitlab.com/cable-mc/cobblemon/-/issues/1686).
