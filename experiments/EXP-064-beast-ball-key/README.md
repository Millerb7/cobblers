# EXP-064: is the Beast Ball the only ball that catches a dungeon boss, and is nothing else lost?

**Status: NOT_EXECUTED.** Designed 2026-10-08 with the pack it tests (`tools/key_ball.py`, `data/key_ball.json`,
`cobblers_key_ball`, world-local, self-driving, no reapply step) and the tag the Entei boss now carries
(`tools/entei_boss.py` `slot/s<k>/bind`). Nothing has been run on a server. The builder wrote this procedure and the
builder's own tests (`tests/test_key_ball.py`). **The builder does not grade it**: another agent or the main session
runs it and reviews the results. Staging only, never the live world.

## Objective

The owner's decisions of 2026-10-08 (`data/key_ball.json` `decision`): at a Pokemon tagged `cobblers.key_boss` the
Beast Ball's catch rate is x5, and every other ball, the Master Ball included, breaks free, is handed back and says the
refusal line. Everywhere else, balls behave as Cobblemon ships them. **Yes** means every case below passes.

## What it relies on, and what is ASSUMED

| Claim | Status | Case |
|---|---|---|
| Both callbacks fire from `data/cobblemon/callbacks/<event>/cobblers_key_ball.molang` with the context the jar names (`pokemon_entity`, `poke_ball_entity`, `catch_rate`; `pokemon`, `poke_ball`, `thrower`) | VERIFIED in bytecode (research note section 3), NOT RUN | 1, 2 |
| `ball_type` compares to `'cobblemon:beast_ball'` as a string; `has_tag` reads an entity tag | ASSUMED (names VERIFIED, argument shapes not) | 1, 2, 3 |
| `set_shakes(0)` makes the ball break free and a battle continues | NOT RUN (the level cap's identical path is also unproven) | 2 |
| `give @s <ball_type> 1` gives the ball; Cobblemon's ball items share their ball ids | ASSUMED | 3 |
| A creative throw consumes no ball (`ItemStack.consume`), so no refund there | read from bytecode, NOT RUN | 3 |
| `fabric:load_conditions` with `fabric:not` / `fabric:true` drops the jar's recipe and its unlock advancement | VERIFIED in the Fabric API 0.116.14 jar, NOT RUN | 6 |

## Setup

1. A staging server with `cobblers_key_ball`, `cobblers_entei_boss`, `cobblers_levelcap` and `cobblers_blackout`
   installed world-local (`tools/reapply.py install`, run by the main session). Check `/datapack list` shows all four.
2. A test player P, survival, with one of each ball in `data/blackout.json` `claims.balls`, plus a Master Ball, a
   Cherish Ball, a Park Ball, an Ancient Origin Ball and ten Beast Balls. A second player Q, creative.
3. A **stand-in boss**: `/pokespawn snorlax level=50` (catch rate 25, so a Beast Ball lands often enough to see), then
   `/tag @e[type=cobblemon:pokemon,limit=1,sort=nearest] add cobblers.key_boss`. Respawn and re-tag between cases.
4. A **normal Pokemon**: the same `pokespawn`, untagged.

## Cases

1. **Every ball type at a tagged boss.** In battle with the stand-in at about half HP, throw each ball once.
   *Pass:* every ball but the Beast Ball shows zero shakes and breaks free, the battle goes on, and P's inventory
   holds the same count of that ball as before the throw. Beast Balls: over ten throws, at least one catches (x5 on
   rate 25 at half HP is about 90% a throw). Repeat three of them (Ultra, Quick, Dusk) out of battle.
2. **The Master Ball refused and returned.** One Master Ball at a tagged boss, in battle and out. *Pass:* it breaks
   free, P still holds exactly one Master Ball, and there is no Master Ball item entity on the ground near the boss
   (`/execute as P at @s run data get entity @e[type=item,distance=..8,limit=1]` finds none).
3. **The refund is exact.** P throws a Master Ball with a full inventory: *pass* the ball drops at P's feet, one only.
   Q (creative) throws a Master Ball at a tagged boss: *pass* it breaks free and Q gains no ball.
4. **The message.** On every refusal above, P sees, in grey italic: *"The ball closes on nothing and rolls back to you.
   Whatever could hold a thing this old, it is not this. Even a Master Ball will not close on it."* once per throw. A
   Beast Ball that fails shows Cobblemon's own "broke free" and no line of ours.
5. **A Beast Ball on a normal Pokemon is x1.** Ten Beast Balls and ten Poke Balls at the untagged stand-in at full HP,
   in battle. *Pass:* no line of ours, each failed ball consumed, and the two catch counts within noise of each other
   (the jar's LabelModifier: x1 on a non-Ultra-Beast). Any ball at an untagged Pokemon is never refunded.
6. **The recipe gone.** On server start, the log carries no recipe parse error for `cobblemon:beast_ball`;
   `/recipe give P cobblemon:beast_ball` reports no such recipe (or gives nothing); the recipe book has no Beast Ball;
   4 gold ingots, 4 echo shards and a diamond in the jar's pattern make nothing. Other ball recipes still craft (an Ultra
   Ball from its recipe).
7. **Blackout keeps Beast Balls.** P carries 10 Beast Balls and 20 Ultra Balls and loses to a wild Pokemon (blackout
   EXP-042 procedure). *Pass:* the claim takes Ultra Balls and no Beast Ball; P still has 10.
8. **The level cap still refuses an over-cap boss.** P whose RCT level cap is below 50 (read it first with
   `rctmod player get level_cap P`) throws a Beast Ball at
   the tagged L50 stand-in, in battle. *Pass:* the level cap's "Your team isn't strong enough yet" line, the ball
   breaks free and is consumed (not refunded: data/key_ball.json does_not_cover), and no catch. A Master Ball at the
   same target: both refusal lines may show, the ball is refunded once, no catch.
9. **The Entei boss carries the tag, and the claim still waits.** With `cobblers_entei_boss` and a Champion-cleared P,
   enter a run: `/data get entity @e[type=cobblemon:entei,limit=1] Tags` lists `cobblers.key_boss` beside `cobblers.eb`.
   Throw a Master Ball (refused, returned, the line), then faint the Entei: *pass* "Entei sinks back into the ash ring.
   It will be waiting when you return." The next run spawns a catchable Entei again; a Beast Ball catch grants
   `cobblers:entei_boss/caught`.
10. **Untagged legendaries are untouched.** A `pokespawn` Entei (untagged): a Master Ball catches it.

## Record

For each case: what was thrown, in or out of battle, shakes seen, the chat lines, P's ball counts before and after.
Write results to `experiments/EXP-064-beast-ball-key/results.md`.
