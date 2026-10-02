# Gating a town market's stock per player

Research with a recommendation. Nothing is built; `data/` and the packs are untouched.
Labels follow `.claude/rules/research.md`: **VERIFIED** = seen in a file at the cited line, in a jar,
or in a recorded in-game run here. **ASSUMED** = inferred and not run.

The question (the owner, 2026-10-01): "The trader work stalled on shared merchants with no per-player
gating, and the casino research found score-based currency works per player. Say whether market stock
can be gated the same way, or whether these have to be quest rewards."

The design it serves: a player advances materially by buying better gear in town markets, so the
market in town 3 must offer something a two-badge player cannot buy and a five-badge player can,
**at the same counter, at the same moment**.

## The verdict

**Yes — per player, without a new mod, and not as a quest reward.** But not on the merchant.

- **No entity-based shop can do it.** A villager's `Offers` and a CobbleMerchant's
  `CobbleMerchantShop` are one list on one entity; every player who right-clicks it sees the same
  list. VERIFIED by the shape our own generator reads and writes (`tools/traders.py:155-201`, the
  `Offers`/`Price` compound) and by the CobbleDollars class reading
  (`docs/research/CASINO.md:203`: "every player sees the same offers").
- **The per-player part is not the stock, it is the SHOP WINDOW.** Replace the merchant's trade GUI
  with a Cobblemon dialogue counter. A dialogue option carries `isVisible`, a per-player MoLang
  expression, so the option for the thing a player has not earned is **not on that player's screen**
  while it is on the screen of the player next to them. VERIFIED: `tools/compile_dialogue.py:294-297`
  emits `isVisible` from an authored `visible_when`; EXP-022 recorded held-item-conditional options
  appearing and being taken in game (`experiments/EXP-022-native-dialogue-runtime/README.md:47,88`).
- **The gate is the badge flag we already have.** One flag is one advancement, `cobblers:flag/<id>`
  (`tools/progression_pack.py:4,209-239`), and the dialogue compiler already probes an advancement
  per player inside an action and reads it back as a tag
  (`tools/compile_dialogue.py:27-30` — `execute as <uuid> if entity @s[advancements={...=true}] run
  tag @s add <tag>`, then `q.player.has_tag`). First used by the ferry, 2026-09-27.
- **The money is already proven per player.** `cobbledollars query @s` into a score, refuse if short,
  `$cobbledollars remove @s $(amount)` by macro, re-read and refuse unless the balance fell by exactly
  the price. VERIFIED in game: EXP-040 (read), EXP-042 run 1 (charge, $725 to $652); generated today
  by `tools/ferries.py:220-239,272`.
- **The casino's mechanism reaches a scoreboard total, NOT a merchant's stock.** This is the
  distinction the owner suspected and it holds. A score is per player (`docs/research/CASINO.md:58-65`)
  and so is a CobbleDollars balance (`:37-51`), so *paying* has always been per player — our 14 Mart
  clerks already charge each player their own money. What the score cannot do is change what an entity
  offers. CASINO.md states it outright at line 20: "**The wall the owner describes is per-player
  *stock*, not per-player *payment*.**" Score-based currency is not the answer to stock; **per-player
  dialogue visibility** is, and the score is how it gets paid for.

**Not quest rewards.** Keystone one-offs stay rewards (ADR-002), but the design wants a *market*: the
same item buyable later, by anyone who qualifies, for money. A reward is once and free; a gated shelf
is repeatable and costs. Both exist and they are different jobs.

## 1. What actually stalled

**The blocker is not that per-player gating is impossible. It is that stock in `data/traders.json` is
decided once, at pack-generation time, server-wide, and is baked into the summon command's NBT.**

`tools/traders.py:163-201` (`apply_stock_policy`) filters the template's `CobbleMerchantShop` while
the re-application function is being *written*; `:248-275` bakes the filtered compound into the
`summon` line. So the stock a trader carries is a property of the generated function, not of the
player standing there — and changing it needs a regenerate, a `/reload` and a re-summon that kills
and replaces the entity (`:244-262`, `DEDUPE_WAIT`). The one lever in the data is a single global
policy, and it says so in its own status field:

- `tools/traders.py:166-167` — "**Until the badge-gated stock is designed**, a trader sells only what
  the policy in `data/traders.json` leaves".
- `data/traders.json` `stock_policy.status` — "**interim, 2026-09-21: until the badge-gated stock plan
  (Codex) replaces it**", `mode: "regional_only"`.
- `data/traders.json` `stock_policy.mart.status` — "basic stock in every town from the start;
  **badge-gated stock comes later**".
- `docs/STATE.md:23` — "**Badge-gated stock is still to come**; that a `NoAI` trader trades is not
  tested in game."

The interim policy is a blunt instrument: whole categories withheld from everyone
(`Pokéballs`, `Combat`, `Treatments`, `Remedies`, `Boosts`) because they cannot be withheld from
*some*. `tools/traders.py:519-522` even fails closed if a record's declared stock disagrees with what
the policy leaves, which is good discipline and also proof that stock is a build-time constant.

**Correcting the summary in one place:** "shared merchants with no per-player gating" is right about
the merchant and wrong about the repository. The per-player machinery the market needs is already
built and partly proven — flags, dialogue visibility, the checked charge, per-player quest fields —
it has simply never been pointed at a shop. 26 trader records and a verified in-game presence check
(`traders.py verify --rcon`, 24 of 24, STATE.md:23) exist; the gating layer is the missing piece, not
the trader layer.

## 2. Where the per-player state lives, precisely

| Store | Per player | Readable by | Survives re-export | Evidence |
|---|---|---|---|---|
| `cobblers:flag/<id>` advancement (badges) | yes | selector `@s[advancements={...}]`; a dialogue probe | yes, `advancements` is a required carry | `tools/progression_pack.py:209-239`; `tools/carry_players.py:65-75`; EXP-027 |
| `quest.<q>.<f>` MoLang field | yes, `<world>/playermolangdata/<uuid>.dat` | `q.player.data()`; not a selector | ASSUMED — **not** among `carry_players.py`'s named categories; check before relying on it | `tools/compile_dialogue.py:12-14`; EXP-022 |
| Scoreboard score | yes | selectors, `execute store` | only if `scoreboard.dat` is carried, and it is **optional** | `tools/carry_players.py:81`; `docs/research/CASINO.md:58,68` |
| CobbleDollars balance | yes | `cobbledollars query @s` | yes, required category | `tools/carry_players.py:73`; EXP-040 |
| `CobbleMerchantShop` on an entity | **no** | everyone, identically | no: world entity, re-applied by R14 | `tools/traders.py:155-201`; `docs/research/CASINO.md:203` |

Two of these are a flag and the rest are quantities. **Stock gating wants a flag**, which is why the
badge advancement is the right key and a score is not.

## 3. The real options

| # | Option | Per player? | What the player sees | Build cost | Maintenance | Rung (principle 6) |
|---|---|---|---|---|---|---|
| 1 | **Vanilla villager, trades rebuilt** | **No.** `Offers.Recipes` is one list on one entity; no vanilla field makes a recipe conditional on who clicked | the same list as everyone | low | low | 7 — and it does not answer the question |
| 2 | **CobbleDollars CobbleMerchant** (what we ship today) | **No** for stock; **yes** for payment | one list, each paying from their own balance | already built | already built | 2 |
| 3 | **NBT swapped per nearby player** (`data merge entity` in a tick loop keyed on who stands at the counter) | **No** with two players, by construction: one entity, one state | correct stock alone; the wrong player's stock, or a flicker, with a second player at the counter | medium | high: a tick loop per counter and a race nobody can win | 7 |
| 4 | **One merchant entity per player** | partly | their own stall | high: a summon per player per town (26 counters x N players); nothing prevents player B clicking player A's merchant; `NoAI` copies must still pass the R14 dedupe | high | 7 |
| 5 | **A merchant summoned per interaction** (press a button, a stocked merchant appears for 100 ticks) | partly | a merchant that appears and must then be right-clicked a second time to open | high; a GUI cannot be forced open; two clicks per purchase; stray entities after a crash | high | 7 |
| 6 | **Loot table rolled against the player** (`loot give @s loot <table>`, entity predicate) | **yes** — a vanilla entity predicate takes `type_specific: {type: "minecraft:player", advancements: {...}}` (documented vanilla; **used nowhere in this repo**: grep for `type_specific` returns nothing) | a random handful, not a shelf | medium | medium | 5 |
| 7 | **A dialogue counter: gated options, paid in CobbleDollars** | **yes** | a menu of exactly what *they* may buy, with prices, and a refusal when short | medium, and mostly **already written** | low: one more conversation compiled by an existing tool | 5+7 |
| 8 | **A function shop on a sign, button or interaction block**, paid from a score | **yes** (`any_block_use` is per player, VERIFIED in game by the healing-machine checkpoint, `tools/blackout_pack.py:146`) | a block to press and chat text; no list, no prices on screen | medium | medium: an advancement per shelf; a block per item does not scale to a shop | 5+7 |
| 9 | **Not a shop: the item is a quest or badge reward, the market is dressing** | yes, by construction (ADR-002) | a gift, once | low | low | 5 |

Option 6 deserves its own line of honesty: a loot table **can** read the buyer's advancements, so it
is a genuine per-player mechanism and the only one that gates *contents* rather than *offers*. It
suits a restock crate, a daily bundle or a bargain bin. It does not suit a market where the player
chooses, because a loot roll chooses for them.

Option 9 is not wrong, it is a different product. ADR-002 already rules that anything one-time and
valuable arrives as an advancement reward, and that is the right home for a storyline backpack
upgrade. It cannot be the whole market: a market the player cannot spend money in makes CobbleDollars
pointless, and the design says the backpack gets better **because it is bought**.

## 4. Recommendation

**Option 7: the market counter is a Cobblemon dialogue NPC with badge-gated options, paid through the
ferry's checked CobbleDollars sequence. Rung 5 (datapack) plus rung 7 (functions), with rung 2 for the
money. No scripting layer, no companion process, no custom mod.**

Why it is defensible rather than merely attractive: **every part of it already runs in this
repository, and one existing tool already does the whole job for a different noun.**
`tools/ferries.py` builds, per dock, a compiled dialogue whose options are visible only to a player
who meets its flag gates, each option running a function that reads the balance, refuses if short,
charges by macro, verifies the balance fell by exactly the fare, and only then delivers
(`tools/ferries.py:10-21,220-239`). A market counter is that function with `tp` replaced by
`execute as <uuid> run give @s <item>` — the give shape EXP-022 proved in game, including the two bugs
it cost us (`give <uuid>` is refused for a non-player selector; a `store success` into a missing
objective fails silently, so the objective is created first: EXP-022 Results, bugs 1-2). The gating
and the charging are not new work. The new work is a `data/` schema for shelves, a branch in a
generator, and a conversation.

What it costs and what it breaks:

- **The trade GUI goes away at a gated counter.** The player gets a dialogue menu, not Minecraft's
  merchant screen: no drag-and-drop, no stack arithmetic, quantities are whatever the option says.
  This is a real downgrade in feel and the owner should see it before it spreads.
- **Two kinds of counter in one town.** Keep the CobbleMerchant for ungated basics (the 14 Mart clerks
  already work and already charge per player; do not rebuild them) and add a dialogue counter for
  gated goods. A Mart gets a clerk *and* a quartermaster. That is a content decision, not a
  limitation.
- **`stock_policy` stops being a gate and becomes a floor.** Once gated goods have a home, the interim
  blanket withholding (`Pokéballs`, `Combat`, `Treatments`, `Remedies`, `Boosts`) can be revisited
  item by item — which is the thing it was always waiting for.
- **Nothing stops player A buying for player B.** Gating controls the *purchase*, never *possession*;
  a bought item can be dropped, traded or chested. In a four-friend co-op this is probably a feature,
  but the design must not pretend otherwise: per-player stock is a pacing tool, not an enforcement.
- **NPC classes load only at server start** (EXP-022; `tools/compile_dialogue.py:6-8`). A new counter
  needs a restart, not a `/reload`, and its placement is an RCON `spawnnpcat` step in
  `tools/reapply.py` (the existing "npc" action, R17F) — not a function, because a function naming an
  unknown class fails to parse at load.

### Principle 12: two players at one counter

Plainly, and separating what is known from what is not:

- **Each player's screen is their own.** A dialogue is opened per player and its pages carry
  per-player `isVisible` expressions, so A sees five options and B sees two. ASSUMED for two
  *simultaneous* players: EXP-022's "two players at different points of one conversation" is recorded
  **not run** — it needs a second account (`EXP-022 README`, Limitations; `docs/STATE.md:248`).
- **The purchase is serialised and cannot interleave.** One function runs to completion on the server
  thread; no other player's function runs inside it (VERIFIED reasoning, EXP-040 README:20-27, held in
  EXP-042). Two simultaneous buys are two charges against two balances, in order.
- **There is no shared stock to race for.** A shelf is a gated option, not an inventory count. Nobody
  can be sold out from under. If the design ever wants scarcity, that is shared world state and a
  different design (ADR-002's reasoning on shared containers applies).
- **Dialogue cursor state must stay out of it.** The ferry's menu deliberately holds no quest state —
  "no cursor, no field" (`tools/ferries.py:14-15`) — so a second player cannot be affected by the
  first's position in the conversation. **A market counter must copy that: a shop menu is stateless.**
- **The open question is the entity, not the state:** whether two players can hold an open dialogue
  with the same NPC at once, or whether the second is refused. That is the first thing the experiment
  must answer, and it is the only part of this recommendation with a plausible failure mode.

If that fails, the fallback is option 8 (one `any_block_use` button per shelf, per player by
construction, a worse interface) — not a custom mod. **No mechanism has been shown to fail yet, so no
custom mod can be claimed.**

## 5. What must be proven in a running game

**An experiment (number to be assigned from `docs/research/EXPERIMENT_BACKLOG.md`): a badge-gated
market counter.** On staging or the disposable world, under the coordination lock, never the live
world.

Success criteria:

1. A counter NPC opens a shop menu; an option gated on a flag the player **lacks** is absent from
   their menu, and one they hold is present.
2. Buying charges exactly the price, and the balance falls by exactly that amount.
3. Buying with too little money takes **nothing** and says so.
4. The item arrives once, and a `store success` on the give proves it (EXP-022 bug 2).
5. Two players, one counter, at once: each sees their own options, each pays their own money, neither
   purchase affects the other. **Blocked on a second account** (`docs/STATE.md:248`) — if it stays
   blocked, criterion 5 is tested by granting and revoking a flag on one account between opens, and
   the two-player result is recorded as not run.
6. After a server restart the gated option is still correctly visible (the flag is a carried
   advancement; the NPC class reloads at start).

The commands, in order (`<srv>` = the staging server dir, `<world>` = its world; the lock at
`C:\Users\wnd\Documents\github\.cobblers-server-agent.lock` is acquired first and the process/port
check is the first server action):

```
# 1. author a throwaway shop conversation in data/dialogue.json, then compile it alone
python tools/compile_dialogue.py dlg_market_proof --out <world>/datapacks/cobblers_market_proof --place <x> <y> <z>
python tools/validate_data.py

# 2. restart the server detached (NPC classes load only at start; run_in_background, then check the PROCESS),
#    then place the counter with the command compile_dialogue wrote:
cat <world>/datapacks/cobblers_market_proof/placement.txt    # run that spawnnpcat over RCON

# 3. the gate, both ways, as the operator account
advancement revoke <player> only cobblers:flag/gym3_cleared
#   -> talk: the gated option must be ABSENT
advancement grant  <player> only cobblers:flag/gym3_cleared
#   -> talk: the gated option must be PRESENT

# 4. the money, read before and after each purchase
cobbledollars query <player>
#   -> buy; then
cobbledollars query <player>
cobbledollars set <player> 10
#   -> buy a 2,000 item: nothing given, nothing taken, a refusal message

# 5. the state, read off disk with the player offline
#    <world>/advancements/<uuid>.json                the flag
#    <world>/cobbledollarsplayerdata/<uuid>.json     the balance
python tools/progression_pack.py --report <stopped world copy>

# 6. afterwards, the existing presence check still passes
python tools/traders.py verify --rcon <srv>
```

What the experiment does **not** need: `prepare`, the full suite, the live world, or any change to
`data/traders.json`. The proof is one conversation and one NPC.

## Open research questions (do not guess these)

1. **Can two players hold an open dialogue with one Cobblemon NPC simultaneously?** UNKNOWN. Decides
   whether option 7 or option 8 is the shape.
2. **Is `playermolangdata` carried across a re-export?** It is not among `carry_players.py`'s named
   categories (`:65-81`). A stateless shop menu does not care; anything that remembers a purchase
   does.
3. **Does CobbleDollars re-read `CobbleMerchantShop` from NBT at interaction time, or cache it?**
   UNKNOWN; it matters only if option 3 is ever revisited, so it is not worth a jar read today.
4. **Is there any per-player field in CobbleDollars' shop configs?** None in the four files
   (`base-pack/cobbleverse/config/cobbledollars/{common,client,bank,default_shop}.json`, read
   2026-10-01): `defaultShop` is a flat server-wide category list and `bank` a flat sell-back list.
   VERIFIED absent from the configs; ASSUMED absent from the mod, on CASINO.md:203's class reading.
   `modpack/config/cobbledollars/` does not exist, so nothing of ours overrides them yet.
5. **Does a `NoAI` trader trade at all?** Still untested in game (`docs/STATE.md:23`). It gates the
   clerks we already ship, independently of anything here.
