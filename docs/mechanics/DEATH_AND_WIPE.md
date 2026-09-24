# Death, blackout and recovery

**Status:** proposed design; nothing in this document is implemented or runtime-proven.

## Decision

Use one wipe pipeline for both Minecraft death and a full-party Cobblemon loss.
The player returns to the last Pokemon Center they healed at or town waystone
they travelled through, keeps protected infrastructure, permanently loses 10%
of their CobbleDollars, and temporarily loses a bounded selection of ordinary
consumables.

The consumables belong to a persistent **recovery claim** at the defeat site.
When a wild Pokemon caused the wipe, that exact Pokemon becomes the claim's
guardian and appears to carry the most notable lost item. Beating or catching
the guardian returns the full claim. The entity is presentation and encounter;
the saved claim is the authority. If the entity disappears, the claim recreates
it rather than deleting the player's property.

Recovery claims do not expire. A player may return when prepared. The permanent
money loss supplies the unavoidable cost; deleting the recoverable items on a
timer would turn an intended rematch into an offline-time penalty.

## Why this recovery model

| Model | Feel | Reliability | Decision |
| --- | --- | --- | --- |
| Natural victor literally owns every lost item | Best story when it works | One held-item slot; natural despawn, capture and re-export can destroy or duplicate the loss | Do not use as authority |
| Item entities on the ground | Familiar corpse run | Generic, time-limited, vulnerable to lava, other players and re-export | Fallback presentation only |
| Timed recovery claim | Urgent | Punishes logout and can force an unwinnable immediate rematch | Reject |
| Permanent claim with a bound guardian | The victor still has the player's things and creates a rematch | Survives restart, disappearance and re-export when the claim is carried | **Use** |

For a small private server, indefinite records are cheap and unresolved claims
are useful stories. Guardians only need to exist while their area is loaded.
There is no arbitrary three-claim cap. Repeated wipes can therefore leave more
than one unresolved recovery encounter.

## Trigger and blackout flow

Two events enter the same idempotent transaction:

1. **Player knockout:** a Minecraft player death caused by a wild Pokemon,
   terrain, environment or another supported hazard.
2. **Party wipe:** the player loses a Cobblemon battle with no conscious party
   member. Cobblemon does not kill or teleport the player for this on its own.

The handler records a wipe ID before changing money or inventory. If a physical
knockout and battle-loss callback arrive for the same incident, the second sees
the completed ID and cannot charge the player twice.

The transaction is:

1. Capture the cause, dimension, safe defeat coordinate, battle and opposing
   Pokemon UUIDs, and the player's current checkpoint.
2. Calculate the money charge and recovery items from one inventory snapshot.
3. Persist the recovery claim before removing anything.
4. Debit the money and remove the selected items on the server thread.
5. Commit the claim and bind its guardian or fallback satchel.
6. Return the player to the checkpoint, clear combat pursuit, and give short
   arrival protection.
7. In standard play, heal the party as a Pokemon Center blackout would.

If claim persistence fails, the transaction aborts before charging the player.
If teleporting fails after the charge commits, reconnect recovery completes the
return rather than charging again.

## Checkpoints

Each player stores one `last_safe_checkpoint` with a stable place ID,
dimension, coordinates, facing, source type and update time.

- A Pokemon Center becomes the checkpoint only after a successful healer use.
- A town waystone becomes the checkpoint after successful travel through that
  waystone. Discovering or merely walking near it is insufficient.
- Route midpoint waystones are excluded unless the later navigation decision
  explicitly promotes them to safe checkpoints.
- A new player with no record falls back to the Pallet/Hometown campaign spawn.
- A checkpoint is validated against the current place manifest before use. A
  moved or removed checkpoint falls back to Pallet rather than an obsolete
  coordinate.

The Center and Waystones hooks are not yet proven in this pack.

## Cost

### Money

Lose **10% of current CobbleDollars, rounded up**, with a minimum loss of 1 when
the balance is above zero and no cap. Money is the permanent part of the wipe;
it is not included in the recovery claim.

CobbleDollars 2.0.0 Beta 5.1 exposes balance reads and writes and its own remove
command performs a synchronous read/subtract/write. A percentage still needs a
server-side transaction that reads the balance and writes the calculated result
in one tick; the stock command accepts an amount, not a percentage.

### Recoverable consumables

Selection is calculated across each category, not per stack, so splitting a
stack does not reduce the loss.

| Category | Amount placed in claim | Included | Excluded |
| --- | --- | --- | --- |
| Ordinary Poke Balls | 15% of carried quantity, rounded up, maximum 10 | purchasable and craftable balls | Master Ball, Ancient Origin Ball, unique/story balls |
| Medicine | 15%, rounded up, maximum 6 | healing, status cure, Ether-like and revive consumables | key/story medicine |
| Battle and evolution consumables | one random eligible item, 35% chance when any are carried | evolution stones and consumable battle items | permanent unlocks and quest items |

Never select:

- TMs or other permanent move unlocks;
- Minecraft tools, weapons, armour, buckets or navigation equipment;
- badges, trophies, key items, books, maps, Pokedexes or quest objects;
- equipped accessories;
- a Pokemon's held item;
- backpacks or other storage containers themselves.

Eligible supplies inside a protected backpack must still count. Otherwise a
backpack becomes free wipe insurance. Nested modded inventories are therefore a
required proof, not an optional refinement. Until that scan is reliable, the
system is not ready for production.

The percentages are initial tuning values. They should be data/config values so
a playtest can change severity without changing the transaction code.

## Recovery claim

The authoritative record contains:

- claim ID and transaction state;
- owner UUID and display name;
- defeat dimension, exact point and ground-safe recovery point;
- cause (`wild_battle`, `wild_attack`, `trainer_battle`, `environment` or
  `other`);
- all removed item stacks, including components;
- guardian Pokemon UUID plus a serialized Pokemon snapshot when applicable;
- original natural held item, if any;
- resolution state, resolver UUID and timestamps;
- source world/export generation so a re-export can rematerialize it once.

### Wild defeat

The exact wild victor is tagged with the claim ID and exempted from normal
despawn. In a multi-Pokemon wild battle, use the surviving opponent that landed
the final faint; if that cannot be determined, use the surviving active
opponent. The guardian remains at or patrols a small radius around the defeat
site.

The guardian presents the most recognizable claimed item, preferring an
evolution item over medicine and medicine over a Ball. That presentation is a
non-droppable mirror of the claim, not the sole copy. Its original natural held
item is recorded and restored when the claim ends. A label or recovery particle
must identify it without revealing the entire cache from across the map.

Winning a battle against it or catching it resolves the claim atomically:

1. lock the claim;
2. remove the presentation item/tag;
3. grant all stored stacks to the owner, putting overflow in an owner-only
   recovery package at their feet or checkpoint;
4. mark the claim resolved;
5. only then complete the normal defeat/capture consequences.

If the original entity is absent when its chunk loads, recreate it from the
snapshot with the same claim ID. Duplicate guardians are removed by claim ID.

### No wild victor

Trainer losses and environmental deaths create a visible lost satchel at the
nearest safe ground to the defeat point. The satchel is still backed by the
claim record. Touching it resolves the claim; the physical marker may be rebuilt
after restart or re-export. PvP never transfers recovery ownership to the other
player.

### Repeated defeat

Losing to a recovery guardian creates a second charge and appends the newly
selected consumables to that guardian's existing unresolved claim. It does not
duplicate the first claim or reset its contents. Losing elsewhere creates a
separate claim.

## Multiplayer

Default to **rescue without theft**:

- any trusted server player may defeat or catch a recovery guardian;
- the Pokemon goes to the catcher if the normal capture is legal;
- the cached items always return to the claim owner;
- if the owner is offline, the claim becomes `resolved_pending_delivery` and
  pays out when that owner next joins;
- a helper cannot inspect or withdraw another player's cache.

This keeps the good emergent moment—“I found and caught the Ursaluna that wiped
you”—without allowing a friend to take the Thunder Stone. It also avoids adding
party membership infrastructure that this campaign deliberately does not have.

An optional server policy could make only the owner able to resolve a guardian,
or make the resolver take the goods. The latter is a theft/PvP rule and should
never be the campaign default.

Authored one-time Pokemon may already have capture ownership rules. Those rules
win: a helper may defeat the guardian and return the items without receiving a
normally non-catchable encounter.

## What the installed systems already do

### Cobblemon 1.8

- A Pokemon faint is Pokemon state, not Minecraft player death. The current
  config gives fainted Pokemon a 300-second faint timer and wakes them at 20%
  health. A full party loss does not provide this blackout system.
- The jar exposes battle faint/victory events, Pokemon entity save/load events,
  a persistent-data compound, held-item access and an entity despawner. Those
  are sufficient extension points for a companion implementation.
- Pokemon properties can describe a held item and the API can set one. No stock
  command was verified that safely targets the exact existing wild victor and
  replaces its Cobblemon held item. Direct vanilla `/data` edits are not an
  acceptable persistence contract.
- A saved Pokemon carries its held-item data through normal entity
  serialization, so chunk unload/restart should preserve it when the entity is
  saved. This is **not runtime-proven here**.
- `savePokemonToWorld: true` does not make a natural spawn safe escrow. Cobblemon
  has its own age/distance despawner, and upstream reports show wild Pokemon can
  still be removed under spawn pressure. A no-despawn guardian plus a recovery
  record both need proof.

### Lenient Death

Cobbleverse already ships Lenient Death 1.2.5. Its current config preserves
listed key items, can preserve tools by type, can split stacks probabilistically,
marks dropped items, extends their lifetime, reports death coordinates and keeps
inventory snapshots. It is useful policy and a safety net for Minecraft deaths.
It does not handle a Cobblemon party wipe, CobbleDollars, bind drops to a Pokemon,
or make those drops survive a world re-export.

Vanilla `keepInventory` and Lenient Death must not be treated as the design. If
`keepInventory` keeps everything, there are no selected vanilla drops to become
a recovery claim; if it is false, ordinary death handling can drop items before
the claim owns them. The implementation must snapshot and remove the selected
items itself and suppress their ordinary drop path. The current runtime value of
`keepInventory` has not been read from the live world and remains unverified.

## Re-export

World entities do not survive this project's re-export. A guardian-only design
therefore loses claims even if restart persistence works.

Store claims in campaign recovery data keyed by player UUID, mirror the active
claim IDs in player-persistent data, and add the recovery store to the explicit
re-export carry manifest. The carry step must hash-check every claim file. On the
new world's first boot, claims validate their coordinates and recreate guardians
or satchels when the relevant chunk next loads.

If terrain changed so the saved point is unsafe, search vertically and within a
small radius for safe ground. If none exists, retain the claim and route it to an
owner-only recovery clerk at the saved checkpoint. This fallback prevents loss;
it is not the normal recovery loop.

## Nuzlocke compatibility

The item-and-money recovery loop can coexist with a Nuzlocke, but the current
Cobblemon faint rules cannot enforce one. Fainted Pokemon automatically wake
after 300 seconds at 20% health.

Use two policy profiles if a formal Nuzlocke mode is added later:

- **Standard campaign:** checkpoint return heals the whole party.
- **Nuzlocke:** the same money and recovery claim apply, but the wipe handler
  never revives fainted Pokemon. A separate death/retirement system must mark or
  box them and suppress passive awakening. A total wipe returns the player with
  no restored team so they must withdraw legal reserves.

Self-imposed Nuzlocke rules can use the standard system only if players retire
Pokemon manually before the five-minute awakening. The recovery design does not
make Nuzlocke mandatory and does not count a captured recovery guardian as the
owner's route encounter unless that ruleset says it does.

## Ursaluna cave example

1. Ursaluna knocks out the player in the Tri Peaks cave.
2. The player loses 10% of their balance, eight ordinary Balls, three medicines
   and—on the utility roll—a Thunder Stone.
3. They wake at the last used town waystone with their pickaxe, TMs and all other
   infrastructure.
4. Ursaluna remains bound to that cave and visibly presents the Thunder Stone.
5. The player may rebuild their team and return days later. Beating or catching
   Ursaluna returns every cached item. A friend may resolve it, but the items go
   back to the wiped player.
6. If the world is re-exported first, the claim recreates Ursaluna in the rebuilt
   cave rather than deleting the cache.

## Implementation boundary and required proofs

Configuration and Lenient Death cover only part of this. The combined battle
hook, atomic currency/inventory transaction, persistent claim, bound guardian,
multiplayer ownership and re-export rematerialization justify a small server-side
companion module unless an existing addon is found that provides the same state
machine. Datapack commands alone are not a reliable implementation.

Before production, a disposable-world experiment must prove:

1. Minecraft death and full-party loss each invoke exactly one wipe transaction.
2. Center and town-waystone use update only the correct player's checkpoint.
3. A fixed-percentage CobbleDollars debit and item removal are atomic across
   disconnect/restart and cannot double-charge.
4. Every protected category stays; Balls, medicine and an evolution stone enter
   the claim; stack splitting and nested backpacks cannot evade it.
5. The exact victor survives chunk unload and restart, and forced natural
   despawn causes one reconstruction without duplication.
6. Owner defeat, owner capture, helper defeat and helper capture each resolve
   once; the helper never receives the owner's items.
7. An offline owner receives a helper-resolved claim once on next login.
8. Multiple unresolved claims and a repeated loss to the same guardian neither
   overwrite nor duplicate items.
9. Re-export carry preserves claims and rematerializes their guardians at safe
   coordinates.
10. Inventory overflow, a full party, server crash between transaction phases,
    authored capture locks and the Nuzlocke policy all fail safely.

Until those pass, the design is approved only as a direction, not a working
campaign mechanic.

## Evidence read for this design

- Repository runtime and re-export facts: `docs/STATE.md`.
- Cobblemon config: `modpack/config/cobblemon/main.json` and the reference pack's
  matching `base-pack/cobbleverse/config/cobblemon/main.json`.
- Lenient Death policy: `base-pack/cobbleverse/config/lenientdeath.json5` and
  [Lenient Death source](https://github.com/JackFred2/LenientDeath).
- Installed Cobblemon 1.8.0 jar: battle events, Pokemon persistent data,
  held-item access, entity save/load events and despawner interfaces.
- Installed CobbleDollars 2.0.0 Beta 5.1 jar: balance getter/setter and
  read/subtract/write remove path.
- Cobblemon upstream persistence caveat:
  [save-to-world issue](https://gitlab.com/cable-mc/cobblemon/-/issues/269) and
  [forced-despawn issue](https://gitlab.com/cable-mc/cobblemon/-/issues/1686).
