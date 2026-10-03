# EXP-053: the Ursaluna's wake - does a sleeping bear become a boss fight?

Status: **built 2026-10-02, not run.** For the integrating session, on staging, under the coordination lock.

## Objective

The owner, 2026-10-02, after walking the den on staging: *"i dont like the invisible blocks around the
ursuluna"*. Offered three options, they chose **"Wake it as a boss fight"**: no wall; the bear wakes and fights
when you get close. This experiment proves that the built wake (`data/ursaluna_cave.json` `ursaluna.wake`,
`tools/ursaluna_cave.py`) does that, and settles the parts nothing in this repository has proven. The same day the
owner set the boss rules: *"Den boss: returns after it is beaten, no badge to wake it, catchable only late. A boss
that stays dead is an event; one that returns is a place."* (`ursaluna.returns`, `ursaluna.catch`); this run proves
those too.

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
| A macro `spawnpokemonat` line spawns at a fresh boot, from a keeper | proven | EXP-046 (and a killed worker put back by its keeper through the macro) |
| `battle_fainted` and `pokemon_captured` callbacks hand a beaten / caught wild Pokemon's UUID to a function, matched against `recovery/pid`'s text | proven | EXP-042 session 5 (a guardian beaten, and one caught, resolved by UUID); `tools/blackout_pack.py` |
| Several `cobblers_*.molang` files in one callback folder all run | **jar + staging** | Cobblemon ships three in `pokemon_captured/`; ours sits beside `cobblers_recovery.molang` and `cobblers_level_cap.molang` |
| `battle_fainted` sees THIS bear (a NoAI, scale-2 Pokemon woken by NBT merge) as `actor.is_wild` | **unproven** | the guardians were ordinary wild spawns |
| `poke_ball_capture_calculated` + `set_shakes(0)` makes a ball break free | **unproven** | built and loaded for the level cap (`docs/STATE.md` 'The level-cap trap'), never thrown |
| `q.pokemon.has_tag(...)` reads the target entity's tag | **jar only** | `PokemonEntity` adds `EntityMoLangFunctions` (which has `has_tag`) to its struct |
| A caught bear, sent out, carries no `cobblers_ursaluna` tag and no `NoAI` | **jar only** | entity tags live on the entity, not the Pokemon; `NoAIProperty`'s Pokemon-side setter does nothing. If it DID carry the tag, `keep` could kill the player's Pokemon as a duplicate |
| A caught bear keeps its 2.0 scale | **unproven** | `ScaleModifier` is saved with the Pokemon |

## Success criteria

1. No barrier anywhere in the hall; a player walks from the mouth to the bear.
2. Standing at (1471, 163, 1381) (24.0 blocks from the bear's spot) or nearer wakes it within 2 s; standing at
   (1473, 163, 1383) (26.9) does not.
3. After the wake: `Unbattleable 0b`, the message *"The Ursaluna stirs, and rises to face you."* and a growl;
   `#awake cobblers.ursaluna` is 1; sending out a Pokemon at the bear starts a battle.
4. The bear is level 30 and not teleported home during the battle (the keeper stands down).
5. **The return** (the owner, 2026-10-02: "returns after it is beaten"). Knock it out: at once
   `#gone cobblers.ursaluna` = the game time and `#why` = 1 (the callback saw it; 3 means only the absence did).
   With the player still within 48 of the spot, nothing comes back however long they wait. Walk out past 48 (the
   mouth is 71 away) and come back after the cooldown: one sleeping bear on its spot, level 30, `#awake` 0, `#gone`
   -1. For the run, shorten the wait with `scoreboard players set #cool cobblers.ursaluna 600` (30 s; `load` puts
   72000 back on the next restart or `/reload`). Repeat with a catch (`#why` 2) and a sword kill (`#why` 3, two
   keeper passes after it dies).
6. **The catch** (the owner: "catchable only late"). Asleep: any ball breaks free and wakes it. Awake: a player
   without `cobblers:flag/gym6_cleared` sees the ball break free (a Master Ball too) and the red line; a player with
   it (`advancement grant @s only cobblers:flag/gym6_cleared` on staging) can catch it.
7. **Fled**: wake it, start a battle, run; walk out past 48: within 2 s it lies down again on its spot (`#awake` 0,
   `Unbattleable` 1b).
8. Teddiursa: within a minute of a player arriving, 1 to 4 Teddiursa within 20 of (1514, 158, 1424), levels 20-28.

## Implementation

`tools/ursaluna_cave.py` (pack `cobblers_ursaluna_cave`): `keeper` -> `near` (returns at once while awake) ->
`keep`, `wake_check` (`execute positioned 1454.5 163 1364.5 as @a[distance=..24,gamemode=!spectator,limit=1,
sort=nearest] run function cobblers:ursaluna_cave/wake`) -> `wake` (merge `{Unbattleable:0b,RecalculatePose:1b,
HideLabel:0b,Silent:0b}`, set `#awake` 1, tellraw, playsound, and a red line to a waker without six badges).
`dress` resets `#awake` to 0, clears the return clock and stores the bear's Pokemon UUID (`storage cobblers:ursaluna
bear.pid`). The boss rules: `keeper` -> `track` wherever (1454, 163, 1364) is loaded (a tagged bear resets the
absence count; absent two loaded passes running, it is gone; `vanished` if no callback said so; after `#cool` ticks
and with nobody within 48, `respawn` -> `spawn_at` (macro) -> `dress_new`); callbacks `battle_fainted` and
`pokemon_captured` -> `gone` (why 1, 2) by UUID; `poke_ball_capture_calculated` -> `catch_check` as the thrower.
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
- `scoreboard players get #awake cobblers.ursaluna` -> 0; `... #gone ...` -> -1; `... #cool ...` -> 72000.
- `data get storage cobblers:ursaluna bear.pid` -> a UUID string; it must equal the bear's own
  (`data get entity @e[tag=cobblers_ursaluna,limit=1] Pokemon.UUID`, the four ints as Java's UUID text). If it does
  not, no callback will ever match and the return falls back to absence (`#why` 3): record it.
- After a catch: send the caught Ursaluna out next to the den spot and read `data get entity <it> Tags` and `NoAI`:
  neither `cobblers_ursaluna` nor `NoAI:1b` may be there.
- `data get block 1514 158 1424` -> `SpawningStyle "cobblemon:activated"`, `PoolId "cobblers:ursaluna_den_outskirts"`,
  `MaxSpawns 4`, `SpawnRange 16`, `MimicId "minecraft:grass_block"`; or `python tools/habitat_blocks.py verify --rcon`.
  Look at the neighbours (1513, 158, 1424) and (1515, 158, 1424): if they are not grass, change `mimic`.

Then in game: criteria 2 to 6 in order. Also throw a Poke Ball at the SLEEPING bear from the hall's threshold
(about (1476, 163, 1386), 31 blocks) and record what happens.

## Results

Not run.

## Limitations

One bear at a time for the whole server: after a knockout, a catch or a kill it is gone for the cooldown (an hour of
server time) for everyone. A sleeping bear can be hit with arrows from outside the wake radius (Cobblemon ignores
`Invulnerable`, EXP-023); that counts as a kill and it returns. A bear that lies down after a fled fight keeps the
health the fight left (no command heals a wild Pokemon here). The return needs the den spot loaded with nobody
within 48; a player who teleports straight into the den never sees it return until they leave.
Offline, `tests/test_ursaluna_cave.py` runs the return, the catch gate and the UUID text on `tests/gulch_sim.py`'s
command model; that is a model, not this run.

## Decision

Pending the run.

## Follow-up

If `Unbattleable 0b` does not take effect on a live entity, the Celebi's wake fails the same way: record it in
`docs/mechanics/CELEBI_WAKE.md` too.
