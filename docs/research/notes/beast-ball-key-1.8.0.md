# Beast Balls as the key to dungeon bosses (Cobblemon 1.8.0)

**Question (the owner, 2026-10-08).** Make the Beast Ball the only ball that catches a dungeon boss: every other
ball fails, the Master Ball included, so the ball is a key and its price is the gate on dungeon rewards. Can it be
done, what is the real Beast Ball rate, what should it be, what does the player see, what does it cost, and what
happens to a player who clears a dungeon without one?

**Sources.** Bytecode read with `javap -c -l` from the snapshot jars in
`C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/`: `Cobblemon-fabric-1.8.0+1.21.1.jar` (class
names below are in `com/cobblemon/mod/common/`), `mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar`,
`cobblecuisine-2.0.1-1.7.rc1.jar`, `cobblemon-additions-4.1.6.jar`; the snapshot's `datapacks/`. "Line N" is the
Kotlin source line from the class's LineNumberTable; "bytes N" is the bytecode offset. The earlier note
`docs/research/notes/level-cap-catch-block.md` (from GitLab source at ref 1.8.0) reached the same hooks, and this
reading agrees with it. **Nothing here was run in game.**

## Answers in brief

| Question | Answer | Label |
|---|---|---|
| Can a boss refuse every ball but one? | **Yes, with a datapack**, through two MoLang callbacks. No mod is needed. The `uncatchable` hook cannot do it: it refuses all balls or none | VERIFIED in bytecode; NOT RUN |
| Beast Ball's real rate in 1.8.0 | **×5 on a Pokémon labelled `ultra_beast`, ×1 on everything else** (a Poké Ball). The jar's own tooltip says "0.1× otherwise", **and that is false** | VERIFIED |
| Can we change it? | Not the ball itself: there is no `poke_balls` data folder and no config key. **The catch rate can be changed per throw** from a MoLang callback, which does the same job for our bosses | VERIFIED |
| Recommended rate | **×5 on a tagged boss** (Cobblemon's own Ultra Beast value). About 4 throws on a sleeping boss at 1 HP and 19 at full HP | computed from the jar formula |
| Failure message | Cobblemon's own text is only "The Entei broke free!", and only in battle. **Our callback sends its own line** and can hand the ball back | VERIFIED hooks; text is a proposal |
| Is a failed throw consumed? | **Yes.** A ball that breaks free is discarded with no item drop. A ball refused at the hit (`uncatchable`) is dropped back. Our callback can refund a refused ball with `give` | VERIFIED |
| Price, gate, seller | **$5,000 each at the Cinderlee counter** (gym 7's town). A counter cannot gate a line by badge, so the location is the gate. Optionally, Blaine's first-win reward hands out one | proposal |
| Effect on the Master Ball | It still catches everything except tagged bosses. Its $27,000 price and the ball floor stand, because a $5,000 line leaves the floor at $26,600 | VERIFIED against `tools/bank.py` |
| Clearing without a Beast Ball | **The claim already waits.** Entei is catchable on every run until the player has caught one, so a cleared but uncaught run loses nothing permanently | VERIFIED in the generator; NOT RUN |

## 1. The Beast Ball as shipped

- **Registry.** `api/pokeball/PokeBalls.class` `<clinit>` bytes 1009-1054, source line 281:
  `beast_ball` = `LabelModifier(5.0f, true, "ultra_beast")`. Ultra Ball is `MultiplierModifier(2.0f)` (bytes 269-280),
  Great Ball `MultiplierModifier(1.5f)`, Master Ball `GuaranteedModifier()` (bytes 303-313). VERIFIED.
- **`LabelModifier`** (`api/pokeball/catching/modifiers/LabelModifier.class`): `value()` returns the multiplier (5.0);
  `behavior()` returns `MULTIPLY`; `isValid()` with `matching = true` is `pokemon.hasLabels("ultra_beast")`.
  VERIFIED.
- **What happens on a non-Ultra-Beast.** `CobblemonCaptureCalculator.processCapture` bytes 223-245 (line 73):
  `ballBonus = if (isValid) modifier.value() else 1.0`. A Beast Ball on Entei is **×1, exactly a Poké Ball**. VERIFIED.
- **The tooltip is wrong.** `assets/cobblemon/lang/en_us.json:586` reads `"5× on Ultra Beasts, 0.1× otherwise"`.
  The code never applies 0.1. Entei's labels are `gen2, legendary` and Heatran's `gen4, legendary`, with catch rate
  3 for both (`data/cobblemon/species/generation2/entei.json`, `generation4/heatran.json`). Neither the COBBLEVERSE
  datapack's `species_additions/entei.json` nor Mega Showdown's sets a catch rate. VERIFIED.
- **Not data-driven.** The jar has no `data/cobblemon/poke_balls/` folder (its `data/cobblemon/` folders were
  listed). `CobblemonConfig` has `captureCalculator` (ours is `"cobblemon"`, `modpack/config/cobblemon/main.json:70`)
  and no per-ball key. Switching the global calculator would change every catch in the game; it is not the lever.
  VERIFIED.

## 2. The capture formula (`pokeball/catching/calculators/CobblemonCaptureCalculator.class`, `processCapture`, lines 55-98)

VERIFIED from bytecode:

1. **Guaranteed ball** (Master): returns success before any maths (bytes 35-58, lines 57-58). It does **not** fire
   the catch-rate event, but it **does** reach the capture-calculated event (section 3).
2. `inBattle = 1.0` if the target has a battle id, **0.5 if it does not** (bytes 59-75, line 62).
3. `catchRate = getCatchRate(form.catchRate)`, which posts `POKEMON_CATCH_RATE` and returns the event's (mutable)
   rate (`api/pokeball/catching/calculators/CaptureCalculator.class` default method, lines 49-56).
4. Status: sleep/frozen ×2.5, paralysis/burn/poison/toxic ×1.5 (bytes 129-188, lines 65-68).
5. Low level: below level 13, `max((36 - 2L)/10, 1)` (line 70).
6. `a = ballMutator((3·maxHP − 2·HP) · catchRate · inBattle, ballBonus) / (3·maxHP) · status · lowLevel`
   (bytes 247-330, lines 75-77). Nothing caps `a`.
7. **Level penalty, in battle only**: if the thrower's highest active battler is below the target's level,
   `a ×= max(0.1, min(1, 1 − (target − thrower) / (maxLevel / 2)))`. **That division is integer division**
   (bytes 383-402, `isub ... idiv ... idiv ... i2f`), so with `maxPokemonLevel` 100 the factor is 1.0 for a gap of
   0-49 levels and 0.1 for a gap of 50 or more. That is a step, not a slope. Against an L100 boss it bites only if
   the active Pokémon is L50 or lower.
8. Critical capture (`CriticalCaptureProvider` default): chance `round(a · d / 6) / 256`, where d is 0 at ≤30
   caught, 0.5 at ≤150, 1 at ≤300, 1.5 at ≤450, 2 at ≤600 and 2.5 above. A critical needs one shake roll, not four.
9. Shake probability `b = round(65536 / (255/a)^0.1875)`. Four rolls of `nextInt(65537) < b`; all four must pass
   (bytes 436-542, lines 87-95).

`PokedexStatusCaptureInfluencer` only shortens the animation of a success on a species already owned. It never
turns a failure into a catch.

## 3. Refusing every ball but one

### What exists today

- **`uncatchable`** (`pokemon/properties/UncatchableProperty.class`, a flag property). `EmptyPokeBallEntity.onHitEntity`
  checks `UncatchableProperty.isCatchable` (bytes 149-199, lines 212-214) before anything that knows the ball type.
  On refusal it sends `cobblemon.capture.cannot_be_caught` ("This Pokémon cannot be captured.", `en_us.json:2783`)
  and `drop()`s the ball. This is **all or nothing**. The Entei boss's farm mode uses it (`data/entei_boss.json:17`,
  props.farm). VERIFIED in game on 1.8.0 (EXP-023).
- **Species `catchRate`** is per species and applies to every ball, so it cannot single out one ball.
- **Labels**: the jar's ×5 keys on the `ultra_beast` species label. Labelling Entei would apply to every Entei,
  including a shrine or raid one, and would not refuse the other balls anyway. Rejected.

### The mechanism (datapack only, no mod)

Cobblemon 1.8.0 fires MoLang callbacks from `data/cobblemon/callbacks/<event>/*.molang`
(`CobblemonCallbacks.class` `reload`; `events/CallbackHandler.class` `setup`). Three catch events are wired. All
VERIFIED:

| Callback (folder) | `CallbackHandler` line | Context / functions | Can it refuse? |
|---|---|---|---|
| `thrown_pokeball_hit` | 41 | `pokeball`, `pokemon`. **The Cancelable is not passed** (`run$default` with the 4th argument defaulted), and `CobblemonCallbacks.run` lines 104-107 removes `q.cancel` when it is null | **No.** Only Kotlin can cancel it, which Mega Showdown does for Zygarde cores (`CobbleEvents.class`, aspect `core-percent`) |
| `pokemon_catch_rate_calculated` | 62 | `thrower`, `poke_ball_entity`, `pokemon_entity`, `catch_rate`; `set_catch_rate(r)` | It can **set the rate**. It is never fired for a Master Ball |
| `poke_ball_capture_calculated` | 63 | `thrower`, `pokemon`, `poke_ball`, `is_successful_capture`, `is_critical_capture`; `set_shakes(n, successful?)` (successful defaults to `n == 4`, critical forced false), `set_critical_capture(n)` (forces success) | **Yes, after every ball's maths, the Master Ball's included** |

- `EmptyPokeBallEntity.beginCapture` (lines 497-535) calls `processCapture`, posts `POKE_BALL_CAPTURE_CALCULATED`
  (lines 499-501) and drives the shakes from `event.captureResult` (line 501). The shake task tests
  `captureResult.isSuccessfulCapture` and otherwise calls `breakFree()`. VERIFIED.
- The ball's MoLang struct (`EmptyPokeBallEntity` constructor and `struct$lambda$0..3`) has `capture_state`,
  **`ball_type`** (`PokeBall.getName().toString()`, e.g. `cobblemon:beast_ball`), `aspects` and `thrower`. VERIFIED.
- The Pokémon struct carries `has_tag` (`api/molang/function/EntityMoLangFunctions.class`) and `has_aspect`
  (`PokemonEntityMoLangFunctions.class`). The player struct carries `tell`, `run_command`, `uuid`, `is_player` and
  `has_advancement` (`PlayerMoLangFunctions.class`). VERIFIED as names; the argument shapes are ASSUMED.

**Design:** tag every catch-mode dungeon boss at bind (the Entei bind already adds `cobblers.eb`,
`tools/entei_boss.py:570-580`; add one shared tag, for example `cobblers.key_boss`). Then two files:

```
# data/cobblemon/callbacks/pokemon_catch_rate_calculated/cobblers_key_ball.molang   (sketch, NOT RUN)
q.pokemon_entity.has_tag('cobblers.key_boss') ? {
  q.poke_ball_entity.ball_type == 'cobblemon:beast_ball' ? { q.set_catch_rate(q.catch_rate * 5); };
};

# data/cobblemon/callbacks/poke_ball_capture_calculated/cobblers_key_ball.molang    (sketch, NOT RUN)
t.pk = q.pokemon; t.th = q.thrower;
t.pk.has_tag('cobblers.key_boss') ? {
  q.poke_ball.ball_type != 'cobblemon:beast_ball' ? {
    q.set_shakes(0);
    t.th.is_player ? {
      q.run_command('give ' + t.th.uuid + ' ' + q.poke_ball.ball_type);
      q.run_command('execute as ' + t.th.uuid + ' at @s run function cobblers:key_ball/refused');
    };
  };
};
```

Rules the build must keep:

- **Never force a success.** Only raise the rate and refuse. Other `poke_ball_capture_calculated` scripts already
  exist: the level cap (`tools/levelcap_pack.py:155`), the Hoopa cradle (`tools/hoopa_cradle.py:264-279`) and Ursaluna
  (`tools/ursaluna_cave.py:352`). Every one of them only refuses. Because a refusal from any script wins whatever the
  order, the scripts need no ordering. A `set_critical_capture` here would make the order matter.
- **Key on the tag, not the species.** That is the world-shaped predicate. Say in the tool what it does NOT cover:
  an untagged Entei (a shrine, a raid) behaves normally.
- The farm-mode boss stays `uncatchable`. Its refusal happens at the hit, before these scripts, and returns the
  ball with Cobblemon's own message.

Whether these run as read is the same open question the level-cap pack carries (`docs/STATE.md`: "installed in
staging, not run in game"): `set_shakes(0)` has never been thrown at.

## 4. What the player sees, and the ball

- **A ball that breaks free is consumed.** `breakFree()` (lines 395-441) discards the ball entity
  (`breakFree$lambda$4`: `discard()`) and never spawns the item. VERIFIED. Without a refund, a refused Master Ball
  is $27,000 gone.
- **A ball refused at the hit is returned.** `drop()` (lines 283-287) discards the entity and, unless the thrower is
  in creative mode, spawns the ball item where it hit. Players see this for `not_wild`, `uncatchable`, `in_battle`,
  `not_single`, `not_your_turn`, `busy`, `you_in_battle` and a cancelled hit. VERIFIED.
- **Cobblemon's own text on a refusal through `set_shakes(0)`:** in battle, `cobblemon.capture.broke_free`, "The
  %1$s broke free!" (`en_us.json:2774`, sent by `battles/BattleCaptureAction.class`); out of battle, nothing but the
  animation. **That is the silent failure the owner wants to avoid**, so the callback sends a line of its own.
- **Recommended:** refund the exact ball (`give <uuid> <ball_type>`) and say something that reads as "this needs
  something else" without naming it:
  - any refused ball: *"The ball closes on nothing and rolls back to you. Whatever could hold a thing this old, it
    is not this."*
  - a Master Ball, so the player does not think it broke: *"Even a Master Ball will not close on it."*
  - optional breadcrumb (owner's call: pure discovery or a pointer): *"...People in the crater town speak of balls
    made for things that do not belong."*
  - a Beast Ball that fails: Cobblemon's "broke free" is honest here; add nothing, or *"It almost held."*
- **The client tooltip** says "0.1× otherwise". It is wrong in the jar and would be wrong again here. It can be
  overridden with a lang entry, `item.cobblemon.beast_ball.tooltip`, in our client resource pack (`modpack/`, which
  players install). ASSUMED: we do not yet ship a lang override, so the path is untested.

## 5. The number

Catch rate 3, level 100 (`data/entei_boss.json:17`), in battle, the thrower's active Pokémon within 49 levels,
no critical (a critical at d = 1 adds 0.1-1.6 points). Per-throw chance, with expected throws (1/p) in brackets.
×1 is the Beast Ball as shipped and ×2 is what an Ultra Ball would do:

| Boss state | ×1 | ×2 | ×3 | ×4 | **×5** | ×6 | ×8 | ×10 |
|---|---|---|---|---|---|---|---|---|
| full HP | 1.6% (64) | 2.6% (38) | 3.6% (28) | 4.4% (23) | **5.2% (19)** | 6.0% (17) | 7.5% (13) | 8.8% (11) |
| half HP | 2.6% (38) | 4.4% (23) | 6.0% (17) | 7.5% (13) | **8.8% (11)** | 10.1% (10) | 12.5% (8) | 14.8% (7) |
| 1 HP | 3.6% (28) | 6.0% (17) | 8.1% (12) | 10.1% (10) | **11.9% (8)** | 13.7% (7) | 17.0% (6) | 20.1% (5) |
| 1 HP, paralysed/burned/poisoned | 4.8% (21) | 8.1% (12) | 11.0% (9) | 13.7% (7) | **16.2% (6)** | 18.5% (5) | 23.0% (4) | 27.2% (4) |
| 1 HP, asleep/frozen | 7.1% (14) | 11.9% (8) | 16.2% (6) | 20.1% (5) | **23.7% (4)** | 27.2% (4) | 33.7% (3) | 39.9% (3) |

For reference, an Ultra Ball on an ordinary catch-rate-45 Pokémon in battle catches 20% at full HP, 46% at 1 HP
and 91% at 1 HP asleep. A throw out of battle halves `a`: ×5 at 1 HP asleep falls to 14%.

**Two readings of "better than Ultra on a normal Pokémon".**

- **(A), recommended:** the boss multiplier should beat the Ultra Ball's ×2. ×5 does, and it is "nowhere near a
  guarantee": even played perfectly it is 24% a throw, so 5 balls catch 74% of the time and 10 balls 93%. With only
  paralysis, 5 balls catch 59% and 10 catch 83%. At 1 HP with no status, 5 catch 47% and 10 catch 72%.
- **(B):** the Beast Ball should beat an Ultra Ball on ordinary Pokémon. That costs one more line (`set_catch_rate`
  ×2.5 on untagged targets). It turns the key into the best ball below the Master, and at $5,000 nobody would throw
  it at a normal Pokémon anyway. Recommended against. Today it is a Poké Ball on everything untagged.

**Why ×5:** it is Cobblemon's own Ultra Beast figure, so the story ("a ball made for things that do not belong
here") and the number agree. Weakening matters a lot (19 throws at full HP against 4 asleep at 1 HP), which rewards
the fight. Mind Entei's Sitrus Berry: it heals 25% below half HP (`props.catch`), so reaching 1 HP takes one more
hit.

## 6. Price, gate and seller

**Income** (`python tools/income_model.py --json`, measured from the trainer files, not run in game): by badge 7
$134,330 and badge 8 $202,835. Through the League $427,228 for a Normal player and $572,051 for a Challenge one.
The ladder's target leaves about 30% unspent (`target_ratio` 0.7). The Challenge voucher totals $23,748
(`data/challenge_mode.json` voucher.computed). Challenge players get more trainer income and no mining, so a
dollar price is fair to both modes.

**Recommended: $5,000 a ball, sold one at a time.** The expected spend per catch at ×5:

| Boss state | throws | at $4,000 | **at $5,000** | at $7,500 |
|---|---:|---:|---:|---:|
| 1 HP asleep | 4.2 | $17k | **$21k** | $32k |
| 1 HP paralysed | 6.2 | $25k | **$31k** | $46k |
| 1 HP | 8.4 | $34k | **$42k** | $63k |
| full HP | 19.1 | $76k | **$95k** | $143k |

So a boss played well costs about one Master Ball ($27,000), and played lazily three or four. Each throw is 6¼
Ultra Balls ($800 each), and leg 8's whole income ($68,505) buys 13. That is expensive enough to think about every
throw.

**Where, and the gate.** No counter line can be badge-gated any more. Decision `counters_are_merchants`
(`data/markets.json` decisions, the owner 2026-10-06) made every counter a CobbleDollars merchant that "shows one
list to every player", so all 53 old gates sit in `gate_dropped`. **The brief's premise of badge-gated counters is
out of date.** The gate is therefore the location:

- **Sell it at the Cinderlee counter** (`gym7_town`, critical path, badge 7, `data/markets.json:279`). A player can
  buy there on arrival with 6 badges, which is "around gym 7". Buying early is harmless: until the first boss it is
  a Poké Ball. The counter's theme ("a town on a volcano sells heat") and its keeper's greeting need a word for the
  new line. The alternative is the Northlight station (off-path, badge 6; "the station's research" fits), but money
  lines there sit beside the netherite exchange.
- **Not an exchange line.** An exchange line of kind `ball` must cost more than the dearest non-exchange shelf line
  (`tools/bank.py:553-558`), which today is $26,600, so it could not be cheap.
- **Not a Mart tier.** The Mart sells only what its shopkeeper template already prices (`data/traders.json`
  stock_policy.mart.tiers_why), and the template sells no Beast Ball (no `beast_ball` in the snapshot's shop data).
- **Optional per-player gate:** Blaine's first-win reward (`data/progression.json`) gives one Beast Ball. That is
  the only real gym-7 gate available, and it introduces the item.

**The ball floor holds.** `exchange_floors` (`tools/bank.py:489-511`) takes the floor as the highest unit price of
any non-exchange counter or stall line: $26,600 (Holdfast's diamond backpack, measured). The Master Ball is the
Northlight exchange line, 30 netherite × $900 = $27,000 (`data/markets.json:394`), and must stay above that floor.
A $5,000 Beast Ball leaves the floor where it is. A Beast Ball at $26,600 or more would breach it. Do not price it
there.

## 7. What it does to the ball economy and the Master Ball

- The Master Ball still guarantees every catch except a tagged boss, and except anything over the level cap, which
  it already could not catch (`data/level_cap.json`). Its line, its barter (`data/direct_trades.json` `master_ball`,
  a netherite block plus 21 ingots) and the floor are unchanged. Its stated purpose, "a Master Ball removes the
  catch check" (`direct_trades.json:113`), stops being true for dungeon bosses only. No player is affected, because
  the Entei boss has never run in any world (`data/entei_boss.json` status).
- **Leaks that would bypass the price, to close or accept:**
  1. **Crafting recipe, live:** `data/cobblemon/recipe/beast_ball.json` makes **8 Beast Balls** from 4 gold ingots,
     4 echo shards and a `#cobblemon:tier_4_poke_ball_materials`. Echo shards come only from Ancient City chests. The
     world has no Ancient City placed (`data/structures.json:6844` says "hand-place"; there is no entry in
     `data/placements.json`). Closed today by geography. Override the recipe if an Ancient City is ever placed.
  2. `cobblemon-additions` chest loot: `bca:item_groups/normal_balls` has `beast_ball` at weight 3, reached via
     `bca:support_tables/poke_balls`. Whether any BCA chest exists in our world is not checked.
  3. COBBLEVERSE loot datapack: `minecraft:chests/end_city_treasure` (no End here) and COBBLEVERSE-RCT
     `rctmod:loot_table/generic/legendary/pokeballs`. Nothing in `data/` references the latter. Not checked: whether
     Cobbleverse's own roaming trainers drop from it.
- **Blackout:** `data/blackout.json` claims take 40% of a player's balls, up to 30, on a wild loss, and
  `cobblemon:beast_ball` is in that list (line 86). The Master Ball is exempt ("unique or story balls, never lost",
  `balls_basis`). At $5,000 a Beast Ball is a key: **add it to the exemptions.** The Entei itself already makes no
  claim (`loss`: exempt tag).
- CobbleCuisine's catch-boost food multiplies the same event rate (`PkmCatchRateEvent.class`), so it stacks with ×5.
  That is acceptable; note it in the balance.

## 8. Clearing a dungeon without a Beast Ball: the waiting claim

**It already waits** (VERIFIED in `tools/entei_boss.py`; NOT RUN, EXP-059 is NOT_EXECUTED):

- The claim is keyed on the **catch**, not the clear (`data/entei_boss.json:22` catch.rule). At each run's appear
  step, `slot/s<k>/appear` (`tools/entei_boss.py:554-569`) spawns `props.catch` (mode 1) unless the owner holds
  `cobblers:entei_boss/caught`, and `props.farm` (mode 2, uncatchable) once they do.
- A catch-mode Entei that faints in battle settles the run with no drop and the line *"Entei sinks back into the ash
  ring. It will be waiting when you return."* (`settle`, `:581-591`; `data/entei_boss.json:169`).
- Only `pokemon_captured`, in the owner's slot, grants the flag (`caught`, `:592-600`). The relog case is
  `relog_caught` (`:601-610`, review N142). N157's two open defects, another player's ball landing within one
  20-tick keeper pass, are unchanged by this design.

So a player who clears without a Beast Ball **does not lose the catch**. They come back, pay the sigil (2
netherite) and the 24,000-tick lockout again, fight again, and throw. The flag "cleared, not yet caught" the owner
asked for is simply "has no `caught` advancement", which exists today.

Proposed additions:

1. **The key-ball refusal sits beside the existing catch rule.** The new tag goes on catch-mode Entei only (mode 1),
   and the Beast Ball callbacks key on it. The present `why_no_ball_check` (`data/entei_boss.json:25`) stays true:
   that ball check was about other *players*, and this one is about the *ball*.
2. A **hint at the faint**: *"It will be waiting when you return. Bring something that can hold it."*
3. Owner's choice, **not recommended by default: warn at the sigil** when a catch-mode entrant carries no Beast Ball
   (`execute if items entity @s container.* cobblemon:beast_ball`, vanilla 1.21). The warning would not refuse: it
   would spare a wasted sigil, but it gives the discovery away.
4. Do **not** add a re-fight-free claim, such as spawning the boss already weakened for a returning player. The
   catch needs a battle anyway: out of battle the rate halves, and weakening is the whole skill in the table above.

Cross-system check: the boss is level 100 and the cap after the Champion is 100 (`data/arena_fights.json`
postgame). The level-cap pack refuses only targets strictly over the cap, so Entei is catchable. **Any future boss
placed before the Champion must be at or under the cap at its gate.** Otherwise the cap refuses even a Beast Ball,
and its "Your team isn't strong enough yet" would read like a broken key.

## 9. Cost (the repo's measured terms)

| Unit | What | Cost |
|---|---|---|
| Build | the shared tag at the Entei bind; two callbacks plus `cobblers:key_ball/refused`, generated from a small data record (or folded into `tools/entei_boss.py`); the Cinderlee line (`markets.py prices --write`, markets and bank audits); the `beast_ball` exemption in `data/blackout.json`; the lang override; tests | **narrow follow-up, ~2.6M** (an end-to-end builder, if the owner also wants Blaine's reward and the entry warning: 3.4-4.6M) |
| Independent audit | Can a non-Beast ball ever catch a tagged boss? Can a refund duplicate a ball? Can a scripting error lock a player out of the catch? It can trap a player, so CLAUDE.md escalation rule 1 says run it on **opus** | **~3M** |
| In-game proof | main session, staging (never live): a tagged catch-rate-255 Pokémon refuses a Master Ball (refunded, message shown) in and out of battle and the battle continues; a Beast Ball catches it; a tagged catch-rate-3 Pokémon over about 20 Beast Balls lands near the table's rate; the farm boss still says "cannot be captured" | the owner's or the main session's |

Total about 5.6M, or 6.4-7.6M at the larger scope, plus the proof.

## 10. Open questions for the owner

1. Which bosses are "dungeon bosses"? Today only the Entei boss (gated at `champion_cleared`). Heatran would follow
   it. Are the shrine legendaries, Hoopa, Ursaluna or the Gulch Megas in or out? "From around gym 7" suggests the
   owner expects a boss before the Champion, and none exists.
2. Reading (A) or (B) of "better than Ultra on a normal Pokémon" (section 5).
3. Pure discovery, or a breadcrumb to the crater town, in the refusal line.
4. Refund a refused ball (recommended), or let it break as a lesson. A lost Master Ball costs $27,000.
5. Cinderlee (gym 7, critical path) or Northlight (badge 6, off path) as the seller; a Blaine first-win Beast Ball,
   yes or no.
6. A sigil warning for empty-handed entrants (section 8, item 3).

## Not verified (experiment candidates)

- The whole chain in game: both callbacks fire; `ball_type` compares as a string; `set_catch_rate` takes a number;
  `set_shakes(0)` breaks free and a battle continues afterwards; `give <uuid> <id>` refunds. The level-cap pack's
  identical `set_shakes(0)` path is also unproven.
- `!=` and nested `?{}` in Cobblemon's MoLang dialect. The repo's existing scripts use only `==` and nesting, so
  prefer that form.
- Whether a BCA chest or a Cobbleverse trainer can drop a Beast Ball in our world.
- The lang override reaching clients.
