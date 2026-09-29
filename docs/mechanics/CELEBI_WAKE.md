# The wake of the sleeping Celebi

Status: **designed and emitted 2026-09-29, not run in game.** The item and the badge gate are proposals and
need the owner. Everything else here is built by `tools/sapling_celebi.py` and `tools/legendaries.py` from
`data/sapling_celebi.json` and `data/legendaries.json`.

The Celebi has been asleep on a branch of Route 1's world-tree sapling at `(1383.5, 144, 4630.5)` since
2026-09-25 (`EXP-023`, reapply step `R14C`, pack `cobblers_celebi`). It is inert, walled in barrier blocks,
and until this design it could not be woken, and if it had been woken it could not have been caught. Three
separate faults had to be closed for "catch the Celebi" to be a thing a player can do at all.

---

## 1. What wakes it

**Chosen: a state check on the keeper's own 40-tick loop.** A player who

- has cleared gym 8 (`cobblers:flag/gym8_cleared`, a per-player advancement written by
  `tools/progression_pack.py`), and
- stands within 16 blocks of the Celebi, and
- is holding the wake item in the main hand (`nbt={SelectedItem:{id:"minecraft:clock"}}`)

wakes it. The check is `cobblers:celebi/wake_check`, one command line, run from `cobblers:celebi/near`,
which already runs every 40 ticks while any player is within 48 blocks of the sapling. It hands off to
`cobblers:legendary/celebi_wake/open`, which owns the badge gate and does the opening.

### Why not the cheaper rungs (principle 6)

| Rung | Candidate | Why it does not suffice |
|---|---|---|
| Cobblemon native | `pokemon_interactions` datapack interaction on a held item | **Tested and failed** (EXP-023 B). The `owner_held_item` requirement is an `OwnerQueryRequirement`: it tests the *owner's* held item, and a wild Pokemon has no owner. The script never ran, for the right item or the wrong one. |
| Compatible addon | — | No addon in `base-pack/inventory/` offers a world interaction hook. Adding one for a single encounter is principle 9. |
| Cobbleverse dependency | — | Same. |
| Configuration | — | Nothing here is configurable; there is no key that says "wake this entity". |
| Datapack (advancement) | `minecraft:item_used_on_block` on the branch, with an item predicate and the flag | EXP-023's candidate, and it is **unsound twice over.** (a) An advancement fires once per player for ever and its criteria cannot test another advancement, so a player who tries the item before gym 8 burns it and can never wake it. `/advancement revoke` could re-arm it, but that needs a tick-driven revoker — i.e. the loop below, plus an advancement. (b) **The branch block cannot be used on at all**: the barrier shell fills every cell around it and caps the Celebi's own column, so no face of the branch log is reachable, and it is 19 blocks up a tree. An advancement that can never fire is not a trigger. |
| **Functions/commands** | **a state check on an existing loop** | **Chosen.** It cannot be burned (it is a state, not an event), it needs no reachable block, it re-arms itself after a re-export, and it costs one command line per 40 ticks *inside a loop that already runs* — `docs/mechanics/TOWN_TICK_BUDGET.md` is counting the idle floor, and this adds nothing to it while no player is at the sapling. |
| Scripting layer / companion / mod | — | Not reached. The rung above works. |

### The item

`minecraft:clock`, **PROPOSED, not decided** (`data/sapling_celebi.json` `wake.item`). Celebi is the Time
Travel Pokemon; a clock is vanilla, so no dependency; and using a clock on a block does nothing else, so it
carries no other meaning. Nothing in the campaign names a wake item today, and
`docs/story/EARLY_ROUTE_BUILD_HANDOFF.md` forbids a Route 1 NPC naming one, so **whatever item is chosen has
to be taught somewhere after gym 8** — that is story work the arc owner has not done. Changing it is one
field.

`SelectedItem` is the main-hand stack in vanilla player data (Player.dat format, minecraft.wiki); an offhand
item does not match, which is intended. This selector form is **documented vanilla but has no precedent in
this repo** and is on the in-game checklist below. The alternative, if it misbehaves, is a predicate file
with `minecraft:entity_properties` / `equipment.mainhand.items`, at the cost of one more file.

### The gate

`gym8_cleared`, unchanged from `data/legendaries.json`, and still marked the file author's proposal rather
than the owner's decision. Nothing about the mechanism depends on which flag it is: the gate is a selector
predicate in `wake_check` and an `execute unless entity @s[advancements={…}] run return 0` inside `open`.
`open` is the authority; `wake_check` repeats the flag only so that an ungated player holding a clock does
not call a function that would refuse.

---

## 2. How the shell opens

`cobblers:legendary/celebi_wake/open`, run **as the waking player**, in order:

1. refuse unless the player is past the gate;
2. refuse if it is already awake (so a second qualified player does not repeat the message and the sound);
3. grant that player `cobblers:legendary/celebi_wake/met`;
4. `fill 1382 143 4629 1384 146 4631 minecraft:air replace minecraft:barrier` — the shell, and only the
   shell: `replace minecraft:barrier` cannot touch the branch log or the leaves;
5. `data merge` the awake flags onto the Celebi: `Unbattleable:0b`, `RecalculatePose:1b`, `HideLabel:0b`,
   `Silent:0b`. `PoseType` is **not** set to another value: EXP-023 proved only `"SLEEP"`, and principle 7
   forbids guessing the rest of the enum. `NoAI` and `NoGravity` stay on, so it holds its branch instead of
   flying off;
6. set the awake score (section 4);
7. tell everyone within 48 blocks, and play `minecraft:block.beacon.activate`.

Chunk loading: the waking player is within 16 blocks of the fill, so the chunks are inside their own
simulation distance. No force-load is needed and none is taken.

---

## 3. Why it could not be caught, and what changed

Two independent blocks, both fatal on their own.

### 3.1 Level 70 against the level cap

`data/level_cap.json` (the owner, 2026-09-28) refuses a capture **strictly above the thrower's RCT level
cap**, a Master Ball included, in battle and out (`cobblers_levelcap`, `tools/levelcap_pack.py`: a
`poke_ball_capture_calculated` MoLang callback sets the shakes to 0).

**Where the caps actually live.** Not in a table. `data/legendaries.json` carried an invented
`level_caps.by_badges` (3:40 … 8:70, champion:80) that matched nothing. RCT computes the cap per player:

> `max(initialLevelCap, min over the player's next trainers of that trainer's team's highest level + relativeLevelCap)`
> — `LevelUtils` at rctmod `v0.19.0-beta`, quoted in `docs/research/notes/level-cap-catch-block.md`

with `initialLevelCap = 20` and `relativeLevelCap = 0` (`modpack/config/rctmod-server.toml`). So the cap
comes from **the campaign's own RCT series data**, and our gyms and Elite Four are not in that data yet
(only the 13 Route 1-3 trainers and the 5 mansion Channelers are, `docs/STATE.md`). The authored ladder
gives an **upper bound**: after *n* badges the next set contains gym *n+1*, whose top level is
`data/trainers.json` `generation_contract.gym_ace_levels` = 20 25 30 35 40 45 50 55, and after 8 badges it
contains the Elite Four at 60. The cap is the *minimum* over that set, so it is at most the bound and lower
while any weaker required trainer of the tier is undefeated.

Celebi at 70 was above every bound the campaign can produce, including the champion's own team (62). **It is
now 55**: the gym 8 ace level, i.e. the cap tier a player was already on while Giovanni was the next
trainer. Since the gate is `gym8_cleared`, every player who can wake it has passed that tier, and the bound
after 8 badges is 60, so there are five levels of margin. The level lives in `data/sapling_celebi.json`
(the spawn command uses it) and is mirrored in `data/legendaries.json`; a test fails if they disagree.

**The cap system is not weakened, and it does not learn about legendaries.** Instead the wake *reads* the
cap and says so: `cobblers:celebi/cap_advice` runs `rctmod player get level_cap @s` and, if the answer is
1..54, tells that player plainly that a Celebi this strong will break free. A cap that reads 0 (RCT still
loading) says nothing, matching `data/level_cap.json`. The line is a **macro** (`$… $(x)`) for the reason
`tools/levelcap_pack.py` gives: a mod's command written plainly in a function may be parsed at server start
before it is usable (EXP-046). This matters because the real cap is still unverified — if it turns out below
55, the player is told why instead of watching Master Balls bounce.

**Eight of the ten legendaries are still above the bound** (`data/legendaries.json`
`level_caps.above_the_bound`): azelf 47>45, uxie 59>55, regirock 41>40, regice 53>50, registeel 59>55,
regigigas 65>60, groudon 65>60, lugia 75>unknown. They are **not fixed here**: re-levelling is a balance
decision and it changes six emitted packs. Only Celebi, the record this session owned, was brought under the
bound. Each record's `cap_at_gate` still carries the invented table's number, which is why
`tools/legendaries_audit.py` passes them.

### 3.2 `uncatchable`, which no wake can undo

The Celebi was spawned `uncatchable`. That is a Cobblemon **spawn property stored in the Pokemon's own
data** (EXP-023); `EmptyPokeBallEntity.onHitEntity` checks it before anything else and drops the ball.
**No verified command or NBT path clears it on an entity already in the world**, so a Celebi spawned
uncatchable would still refuse every ball after the wake — the encounter would be a wall no matter what the
wake did. Guessing at the NBT key would be principle 7.

So `uncatchable` is **off the spawn** (`data/sapling_celebi.json` `spawn_properties` is now `["no_ai"]`, and
`tools/sapling_celebi.py` refuses to build if it comes back). While it sleeps it is protected by blocks and
by a flag that *is* reversible:

- the **barrier shell** stops a thrown ball exactly as it stops a sword and an arrow — every straight line
  from outside to the hitbox crosses a barrier or the branch log (`shell_why`);
- **`Unbattleable: 1b`** means no battle can start, so there is no in-battle capture either.

**This is the one substitution that has not been proved in game.** EXP-023 proved that `uncatchable` refuses
a ball and that the shell stops a sword; that the shell also stops a *ball* is geometry plus vanilla
projectile collision, and it is first on the checklist below.

---

## 4. The keeper, and why it had to learn the woken state

`cobblers:celebi/keep` ran every 40 ticks while a player was within 48 blocks and, unconditionally:

```
execute store result score #n cobblers.celebi if entity @e[tag=cobblers_celebi]
execute if score #n cobblers.celebi matches 2.. run kill @e[tag=cobblers_celebi,limit=1,sort=random]
execute as @e[tag=cobblers_celebi] positioned … unless entity @s[distance=..0.5] run tp @s … 200.0 0
```

**Correction to `docs/NIGHT_REVIEW.md`:** it does **not** re-merge the dormant NBT. The generated function
has only a count, a kill and a teleport; the `data merge` lives in `celebi/dress`, which only the
re-application calls. (`tools/legendaries.py`'s keeper for the other six *does* re-merge, and only while the
chamber is shut — the same rule, arrived at separately.)

**What it was protecting against**, which is why it is not simply deleted:

1. **a second Celebi.** The re-application's spawn is guarded twice (`unless entity @e[tag=…]` and `unless
   entity @e[type=cobblemon:pokemon,distance=..3]`), but a load race, a chunk that had not ticked in, or a
   hand-run step could still leave two on one branch. The keeper removes one.
2. **displacement.** `NoAI` + `NoGravity` hold it still against its own movement, not against the world:
   a piston, a boat, an explosion, a Cobblemon knockback, or a hand-run `tp` would leave a legendary hanging
   somewhere in the canopy for ever, and it cannot be re-summoned (Cobblemon's spawn command does nothing
   from a plainly parsed function). The keeper puts it back.

Both reasons are about a **sleeping** Celebi. Once it wakes, the teleport is exactly wrong: it snaps the
Celebi back to `1383.5 144 4630.5` every two seconds, through the battle the wake exists to give, and the
random `kill` is no longer safe either. So the keeper **stands down** rather than being deleted:

```
celebi/near:   execute if score #awake cobblers.celebi matches 1 run return 0
               function cobblers:celebi/keep
               function cobblers:celebi/wake_check
```

**Where the awake state lives.** A score, `#awake` on this pack's existing objective `cobblers.celebi` —
no new objective, and no whole-entity scan every 40 ticks (which an entity tag would have cost).

- `cobblers:legendary/celebi_wake/open` sets it to 1.
- **`cobblers:celebi/dress` sets it back to 0**, and dress runs in exactly one place: the re-application,
  on a freshly summoned, untagged Celebi. So the flag cannot outlive the entity it describes.
- `celebi/load` deliberately does **not** reset it: a server restart must not put a woken Celebi back to
  sleep. `scoreboard objectives add` keeps existing scores.

---

## 5. State, and what happens to other players

The wake is **world state, not per player** — the barriers are blocks and the Celebi is an entity, and
`data/legendaries.json` already records that the chambers are shared. Concretely:

| Case | What happens |
|---|---|
| A second player is present at the wake | They see the message and hear the sound (48 blocks). They do **not** get `met`; that is granted to the waking player only. |
| A player joins after the wake | They find an awake Celebi with the shell gone. Anyone can battle or catch it: the gate applies to *waking*, not to *catching*. The level cap still applies per thrower. |
| A player who has not cleared gym 8 | Cannot wake it, and while it sleeps cannot battle it (`Unbattleable`), reach it (shell) or catch it. |
| The first catch | Takes the Celebi for the server. Per-player legendaries would need the scene runtime's per-player actors (EXP-034); nothing here changes that. |
| It is killed after the wake | It is gone until the next re-application. Cobblemon ignores `Invulnerable` (EXP-023) and the shell is the only protection, which the wake removes by design. |
| A player disconnects mid-wake | Nothing is held open: the wake is one function call, not a sequence with state. |
| Players in a different order | The gate is a per-player advancement, so order between players does not matter; the first qualified one to hold the item at the sapling wakes it for all. |
| A restart | The score survives (it is a scoreboard), the shell survives (blocks), the Celebi survives (`PersistenceRequired`). Nothing re-sleeps. |
| A re-export | The world and the Celebi are new: no score, no entity. `R14C` walls, summons and dresses a dormant one, and `dress` sets the flag back to 0. The wake can be earned again by the same ritual, and `met` is already granted so nothing double-counts. |
| A re-application **without** a re-export, while it is awake and alive | `celebi/shell` returns early (`if score #awake matches 1 if entity @e[tag=…]`), the spawn is skipped (a tagged Celebi exists), `dress_new` finds nothing untagged. It stays free. |
| A re-application after it was caught or killed | The score says awake but no entity carries the tag, so the shell **is** rebuilt, the spawn runs, and `dress` resets the flag. The new one is dormant behind barriers, as it should be. |

---

## 6. The re-application

`R14C` is **unchanged**: force-load, `celebi/shell`, the RCON `spawnpokemonat`, `celebi/dress_new`,
release, then the `("check", "celebi")`. The only difference in what it sends is `level=55` and the loss of
`uncatchable`, both read from `data/sapling_celebi.json`. The new functions (`near`, `wake_check`, `wake`,
`cap_advice`) are driven by the pack's own load tag and schedule, not by a step.

`cobblers_celebi` calls `cobblers:legendary/celebi_wake/open`, which lives in `cobblers_legendaries`. Both
are world-local server packs installed together by `tools/reapply.py` (`SERVER_PACKS` and `WORLD_LOCAL`), so
the reference always resolves; a test asserts both memberships so that removing one pack cannot silently
break the other.

---

## 7. What is verified, and what needs a running server

Verified offline, by the generators and `tests/test_celebi_wake.py`:

- the level is 55 in both files and under the after-8-badges bound of 60, computed here from
  `data/trainers.json` rather than from either file being checked;
- `uncatchable` is not in the spawn properties and the generator refuses to build if it returns;
- the keeper stands down on the awake score before `keep` runs, and `open` sets that score in the same
  function that removes the shell;
- `dress` resets it, `load` does not;
- the shell's re-wall guard covers both re-application cases;
- the wake selector carries the gate, the radius and the item, and `open` carries the gate independently;
- every function the pack calls exists, in this pack or in `cobblers_legendaries`;
- no function carries Cobblemon's spawn command; the rctmod line is a macro.

**Not verified. Needs a server** (`boot-test`, then an entry in `experiments/`):

1. **A Poke Ball thrown at the sleeping Celebi bounces off the barrier shell.** This replaces
   `uncatchable`; if it does not hold, the dormant Celebi is catchable early and the design needs a
   different dormant protection.
2. `@a[nbt={SelectedItem:{id:"minecraft:clock"}}]` matches a player holding a clock, and the wake fires
   within 40 ticks.
3. `open` runs from the other pack without a load error, and the fill removes the shell.
4. The woken Celebi can be battled (`Unbattleable:0b` takes effect on a live entity) and caught at 55 with
   a real cap at or above 55.
5. The keeper no longer teleports it: walk it away from the branch after the wake and confirm it stays.
6. `rctmod player get level_cap @s` returns a usable number from a macro line in our function, and the
   advisory only appears when the cap is genuinely below 55.
7. Whether `RecalculatePose:1b` alone visibly wakes the sleeping pose, or whether the model stays asleep.
