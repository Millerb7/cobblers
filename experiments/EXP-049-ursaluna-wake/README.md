# EXP-049: the Ursaluna's wake - does a sleeping bear become a boss fight?

Status: **built 2026-10-02, not run.** For the integrating session, on staging, under the coordination lock.

## Objective

The owner, 2026-10-02, after walking the den on staging: *"i dont like the invisible blocks around the
ursuluna"*. Offered three options, they chose **"Wake it as a boss fight"**: no wall; the bear wakes and fights
when you get close. This experiment proves that the built wake (`data/ursaluna_cave.json` `ursaluna.wake`,
`tools/ursaluna_cave.py`) does that, and settles the parts nothing in this repository has proven.

The mechanism is the sleeping Celebi's (`docs/mechanics/CELEBI_WAKE.md`), whose own wake has **also never run
in game** (its section 7). So this run answers several of the Celebi's open questions too.

## What is proven, and what this run must prove

| Part | Status | Evidence |
|---|---|---|
| Dormant flags (`Unbattleable 1b`, `NoAI`, `NoGravity`, `PoseType "SLEEP"`, `RecalculatePose 0b`, `HideLabel`, `PersistenceRequired`) hold on a live entity across a restart | proven | EXP-023 |
| A plainly parsed function cannot run `spawnpokemonat`; a macro line can run a mod command | proven | EXP-023 / staging 2026-09-25; EXP-046 |
| A Poke Ball's out-of-battle catch does not consult `Unbattleable` | **bytecode only** | `EmptyPokeBallEntity` (Cobblemon 1.8.0 jar) calls `UncatchableProperty.isCatchable`, `PokemonEntity.isBusy` and `getBattleId`; no `Unbattleable` read. So a ball can catch the bear asleep, as any wild Pokemon can be caught without a battle; the level cap (`data/level_cap.json`) still applies |
| `Unbattleable 0b` merged onto a LIVE entity lets a battle start | **unproven** | EXP-023 proved only that 1b blocks one |
| A wild Pokemon with `NoAI 1b` can be battled | **unproven** | the woken Celebi and legendaries keep NoAI on too (`tools/legendaries.py` AWAKE) |
| `RecalculatePose 1b` visibly ends the sleep pose | **unproven** | CELEBI_WAKE.md 7, item 7 |
| The bear starts the battle itself | **not built** | Cobblemon 1.8.0 ships no command that starts a wild battle (the jar's command classes); the player sends out a Pokemon at it |

## Success criteria

1. No barrier anywhere in the hall; a player walks from the mouth to the bear.
2. Standing at (1471, 163, 1381) (24.0 blocks from the bear's spot) or nearer wakes it within 2 s; standing at
   (1473, 163, 1383) (26.9) does not.
3. After the wake: `Unbattleable 0b`, the message *"The Ursaluna stirs, and rises to face you."* and a growl;
   `#awake cobblers.ursaluna` is 1; sending out a Pokemon at the bear starts a battle.
4. The bear is level 30 and not teleported home during the battle (the keeper stands down).
5. Knock it out: no bear, `#awake` stays 1, nothing re-sleeps. Re-run `R18U`: a fresh sleeping bear, `#awake` 0.
6. Teddiursa: within a minute of a player arriving, 1 to 4 Teddiursa within 20 of (1514, 158, 1424), levels 20-28.

## Implementation

`tools/ursaluna_cave.py` (pack `cobblers_ursaluna_cave`): `keeper` -> `near` (returns at once while awake) ->
`keep`, `wake_check` (`execute positioned 1454.5 163 1364.5 as @a[distance=..24,gamemode=!spectator,limit=1,
sort=nearest] run function cobblers:ursaluna_cave/wake`) -> `wake` (merge `{Unbattleable:0b,RecalculatePose:1b,
HideLabel:0b,Silent:0b}`, set `#awake` 1, tellraw, playsound, `cap_advice`). `dress` resets `#awake` to 0.
Teddiursa: `ursaluna_den_outskirts_ward` in `data/habitat_blocks.json`, now activated (max 4, 2 per activation,
range 16, TICK, cancel -1, mimic grass).

## Test instructions

Apply (staging only): build `cobblers_ursaluna_cave` and `cobblers_habitats`; install them; `kill
@e[tag=cobblers_ursaluna]` (the bear standing there was summoned at level 35 and the summon guard would keep it);
run `R18U` (its carve writes air over the whole hall, which removes the old barrier band) and `R9E`, then restart
so the activated block initialises.

Probes, before any player goes in:

- `execute if block 1458 163 1369 minecraft:air`, and the same at (1459, 163, 1369), (1454, 163, 1375),
  (1465, 163, 1364): all pass (the old barrier band at s 63-64).
- `data get entity @e[tag=cobblers_ursaluna,limit=1] Unbattleable` -> 1b; `... PoseType` -> "SLEEP";
  `... Pokemon.Level` -> 30.
- `scoreboard players get #awake cobblers.ursaluna` -> 0.
- `data get block 1514 158 1424` -> `SpawningStyle "cobblemon:activated"`, `PoolId "cobblers:ursaluna_den_outskirts"`,
  `MaxSpawns 4`, `SpawnRange 16`, `MimicId "minecraft:grass_block"`; or `python tools/habitat_blocks.py verify --rcon`.
  Look at the neighbours (1513, 158, 1424) and (1515, 158, 1424): if they are not grass, change `mimic`.

Then in game: criteria 2 to 6 in order. Also throw a Poke Ball at the SLEEPING bear from the hall's threshold
(about (1476, 163, 1386), 31 blocks) and record what happens.

## Results

Not run.

## Limitations

One bear for the whole server, like the Celebi: a knockout or a catch removes it until the next re-application.
A sleeping bear can be hit with arrows from outside the wake radius (Cobblemon ignores `Invulnerable`, EXP-023).

## Decision

Pending the run.

## Follow-up

If `Unbattleable 0b` does not take effect on a live entity, the Celebi's wake fails the same way: record it in
`docs/mechanics/CELEBI_WAKE.md` too.
