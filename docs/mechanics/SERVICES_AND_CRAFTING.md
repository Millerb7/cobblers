# Paid services against craftable items, and the Challenge voucher

The owner, after the 2026-10-10 overnight (`docs/STATE.md` "Owner decisions after the 2026-10-10 overnight" (4)):
"A player should be pushed toward crafting them. [...] Either the services cost enough that crafting is worth it, or
the services are the answer and the craftables are flavour. Pick one and price both to match."

**Picked: crafting, and training by battle, is the route. A service is the convenience, and it costs more than the
play it saves.** EV service $2,000 -> **$17,200** a Pokemon; IV service $1,000 -> **$17,200** a stat ($103,200 for
all six). The raise stays $500. The shelf's vitamins, mochi and power items keep their prices. Data:
`data/training_services.json` `price_rule`; `tools/training_services.py audit` refuses any other price.

Marks: MEASURED = read or computed here from a file named beside it; RELAYED = from a document, not re-measured;
ASSUMED = nobody has measured it.

## 1. What the craftables actually are (MEASURED from the jars)

Recipes read with Python `zipfile` from the offline snapshot
`C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/` (the brief named the live server's `mods/`;
reading that tree needs the coordination lock under CLAUDE.md's live-server gate, and the brief forbids the lock, so
the snapshot's copies were used: `Cobblemon-fabric-1.8.0+1.21.1.jar`, `Only Bottle Caps-1.5.0-fabric.jar`,
`pastureLoot-1.0.5+1.21.1.jar`, the versions `modpack/manifest/` names).

| Result | Recipe | Station |
|---|---|---|
| `medicinal_brew` | water bottle + `medicinal_leek` | brewing stand, or campfire pot (shapeless) |
| `pp_up` | `medicinal_brew` + `vivichoke` | brewing stand |
| each vitamin (`hp_up` ... `carbos`) | `pp_up` + its EV berry (pomeg, kelpsy, qualot, hondew, grepa, tamato) | brewing stand |
| each mochi (+4), x3 | `hearty_grains` + `honey_bottle` + its EV berry | campfire pot |
| `fresh_start_mochi`, x3 | `hearty_grains` + `honey_bottle` + `enigma_berry` | campfire pot |
| each power item | 2 mint leaves of its colour + 4 concrete + 2 diamonds | crafting table |
| EV feathers (+1), x3 | 3 feathers + 1 mint leaf | crafting table |
| hyper-training candy (+1 IV) | 4 EV berries + 4 honeycomb + `exp_candy_l` (x3 from `exp_candy_xl`) | campfire pot |
| `exp_candy_xs` | `sculk` + `honeycomb`; L = 54 XS | campfire pot |
| `obc:bottle_cap_<stat>` | 8 mint leaves of the stat's colour around any bottle cap | crafting table |
| `obc:bottle_cap_gold` | the six stat caps | crafting table |

Sources: silver caps are 3% of vanilla fishing treasure and 5% of Poke Rod treasure, gold 0
(`obc-common.toml`, MEASURED, the snapshot's copy equals the base's apart from a `breedingBuff = false` line). Mint
plants are worldgen only (RELAYED, `OBTAINABILITY_VANILLA_COBBLEMON.md:92`). Blaze rods have no source, so no
brewing stand can be crafted; stands are placed as scenery (`data/plaza_centres.json`, `research_station.json`,
`gym_interiors.json`, MEASURED by grep) and blaze powder is a Pokemon drop (RELAYED, `OBTAINABILITY_MODS.md:42`).
Whether a placed stand is usable is NOT CHECKED. A candy costs 54 sculk and 58 honeycomb: not a real route.

## 2. Measured prices of the same results

One Pokemon, two stats to 252 and 4 in a third:

| Route | Dollars | Effort |
|---|---:|---|
| EV service, old | 2,000 | none |
| battle, two power items bought at the Mart | 3,000 | ~64 fights at a ground (252 / 8 per stat, RELAYED EV_IV_TRAINING 4.2) |
| battle, power items crafted | 4 diamonds = 480 at bank value, plus concrete and 4 mint leaves | the same fights, plus the craft |
| vitamins brewed | two EV berries, 2 x 300 once (the tree regrows: ASSUMED) | 52 vitamins = 18 batches of three, one leek, one vivichoke and one berry a batch (ASSUMED vanilla: one ingredient serves three bottles) |
| mochi cooked, honey bought | 43 honey bottles x 200 = 8,600 | 43 pot crafts |
| shelf mochi (Mart tier 3, 800 each) | 127 x 800 = 101,600 | none |
| shelf vitamins (Northlight, 3,500 each) | 52 x 3,500 + one mochi = 182,800 | none |

**The finding behind the owner's doubt:** the old $2,000 cost less than the bought inputs of two of the crafted routes
(power items $3,000, honey $8,600), and at leg 8's fight hour ($68,505 / 4 = $17,126, MEASURED income /
`effort_model.max_leg_hours`) it was **seven minutes** of fighting. Nobody crafts against that.

IVs: the gold cap is **not sold** (Holdfast's line is `superseded_stock`, decision `arena_trophies_not_sold`,
2026-10-09, MEASURED: `data/markets.json` counters[8]); it comes from arena prizes, a quest and a cache.
`EV_IV_TRAINING.md` 1.2 still says Holdfast sells it at 6,000: stale. So the old IV service ($1,000 a stat) was the
only dollar route to a perfect IV, at 3.5 minutes of leg-8 fighting a stat.

## 3. The rule

A service's price is the **smallest multiple of $100 strictly above `hours_saved` x the fight hour of leg 8**. The fight
hour is the repo's own exchange rate between an hour of play and money: R5 already prices gathering at parity with it
(`data/bank.json` `effort_model.rules`). So a player who crafts for the hour instead of paying earns at least what an
hour of fighting would have paid, which is what "crafting is worth it" means, in this economy's own unit.

- **Why leg 8:** a flat price has to hold where money is most plentiful. Leg 8 has the largest fight hour of the eight
  badge legs ($17,126; Victory Road's is $12,335). At every earlier leg the service costs more hours of fighting, so the
  push to craft is strongest where crafting is cheapest. A badge-scaled price would fit each leg exactly but needs a
  price per badge in the dialogue and the charge; not built.
- **hours_saved is ASSUMED: 1 for an EV spread, 1 for an IV stat.** EV: about 64 wild fights or 18 brewing batches.
  IV: a silver cap at vanilla's treasure share is about 0.7 h with Luck of the Sea III and Lure III, about 3.5 h with a
  plain rod (ASSUMED vanilla rates on the MEASURED 3%), plus eight mint leaves; one hour is the low, enchanted figure.
  An EXP timing replaces both. The prices move with them and with the income model: the audit refuses a stale price.
- **Mutation-checked:** an EV price of $2,000 fails; a leg-8 income of 68,400 gives 17,100 and the price stays 17,200
  (strictly above); 68,800 gives 17,300 and both prices fail.

**Resulting order, every result:** craft or battle (cheap in dollars, costs play) < service (one late fight hour per
result) < the shelf bought in bulk (101,600+ a spread). The shelf items are top-ups: a vitamin is $350 an EV and a
mochi $200 against the service's $34, so a few points are bought off the shelf and a whole spread never is.

**Deliberate exceptions.**
- **Power items stay $1,500.** At any leg the bought item is cheaper than crafting it (two diamonds are about an hour
  of deep mining, RELAYED `ECONOMY_OVERHAUL.md` 3.3). It is the ticket to the battle route, the one EV route with no
  Minecraft, and a Challenge player needs it (section 5). Pricing it up would push that player to the service.
- **The raise stays $500** (the owner's figure). It competes with the free training grounds, not with a craftable: Exp.
  Candies are cut by design. Whether $500 holds when leg 8 pays $68,505 is owner question 7 (`ECONOMY_OVERHAUL.md` 10).

**What it costs a player.** A Normal player at badge 8 has earned $217,315 and the critical-path ask is $146,700
(`python tools/markets.py report`, MEASURED): $70,615 of slack. Six EV services are $103,200: more than the slack, so
servicing the whole team by badge 8 means skipping lines or crafting. After Victory Road and the League (+$224,392,
MEASURED) it is affordable: a real late sink, as `ECONOMY_OVERHAUL.md` 1.3 intended for the services.

`ECONOMY_OVERHAUL.md` section 5's table and section 4.2's Challenge cash flow carry the old prices; this supersedes
them on price.

## 4. Ranch ore (owner decision 3)

`modpack/config/PastureLoot.json` is the base file plus `coal`, `raw_copper`, `raw_iron`, `iron_ingot`, `iron_nugget`,
`redstone`, `diamond`, `emerald` in `item_blacklist`. Key names and matching read from the jar: `Config` carries
`item_blacklist`, and `PokemonPastureBlockEntityMixin` tests each drop's `Identifier.toString()` with `List.contains`.
The seven bought ores were measured as ranch drops (`tools/bank.py ranch_drops` over the snapshot); the nugget is there
because nine craft into a bought ingot. `tools/bank.py` now judges the bank against our overlay, and the eight
`OPEN: ranch_ore` exceptions, `copper_ingot` and `emerald_block` left `afk_rule`. Ore stays bankable at its flat price.
With the snapshot's old blacklist the same check names exactly the seven ores; with ours, none.

## 5. The Challenge voucher (owner decision 2)

Data: `data/challenge_mode.json` `voucher`, the file Challenge mode already uses (`ECONOMY_OVERHAUL.md` U6 had proposed a
separate `data/challenge_voucher.json`). `python tools/challenge_voucher.py --write | --check`.

**Total $23,748 = Oak cash $4,000 + kits $10,748 + power kit $9,000.**
- Oak cash: the largest $100 multiple strictly below the cheapest income-gate line ($4,100, MEASURED), so the voucher
  alone buys no gated TM before badge 1.
- Kits: the quantities are `ECONOMY_OVERHAUL.md` 1.4's (RELAYED, no barter line carries them yet), valued at
  `data/bank.json` prices (MEASURED, unchanged): 864, 920, 1,048, 1,048, 1,288, 1,860, 1,860, 1,860 (League). N148's
  $14,750 re-measures to $14,748.
- **What the services decision obliges:** the six power items ($9,000, Mart prices). With the EV service dear, a
  Challenge player (no Minecraft, by the owner's design) trains EVs by battle with a power item held. Raises are not
  added: Challenge income less the critical-path ask (stretch included), six raises a leg and two extra blackouts a
  leg (ASSUMED, $1,200) stays positive at every badge ($290 at badge 1, $3,244 at 2, $4,419 at 3, then rising). The IV
  service and vitamins are optional: no boss carries EVs or IVs (`"evs"` 0 times in `data/trainers.json`).

**Schedule (front-loaded; each gym grant in inverse proportion to the Challenge income of the leg it opens; gym 8's
opens Victory Road and the League):**

| Grant | Value | Paid as |
|---|---:|---|
| Oak's mode choice | 4,000 | cash |
| gym 1 cleared | 7,298 | kits for legs 2-7 in materials + $270 |
| gym 2 cleared | 4,000 | kits for leg 8 and the League + $280 |
| gym 3 | 2,600 | cash |
| gym 4 | 2,300 | cash |
| gym 5 | 1,400 | cash |
| gym 6 | 1,050 | cash |
| gym 7 | 800 | cash |
| gym 8 | 300 | cash |

The old back-loaded schedule was 4,000, 864, 920, 1,048, 1,048, 1,288, 1,860, 1,860, 1,860.

**Delivery is materials first**, whole kits, because cash cannot buy a material back (rule B1) and the late grants are
smaller than the late kits. The tool fails if a kit would arrive after the gym it answers. **Consequence for the owner:**
netherite scrap and the late kits' diamonds reach a Challenge player at gyms 1-2. That is the choice he asked for (spend
early on power, or hold), but it also hands Nether-tier materials over at badge 1. A player who buys all six power items
at badge 2 and every stretch line runs $1,486 short at badge 2 unless he sells materials; one or two power items fit.

## 6. Not verified, and what would prove it

- Nothing here was run in game. Valid JSON and clean audits are the most this asserts.
- EXP timing: one EV spread by battle and by brewing, one silver cap by fishing, in staging; replaces `hours_saved`.
- EXP-061 step 9: a pastured Steelix stops dropping raw iron under the overlay.
- EXP-062 (the services, S1-S5) is unchanged and still blocks placing the keepers.
- Owner questions: the scrap-at-badge-1 consequence; the raise at $500 (Q7); a badge-scaled service price instead of
  the leg-8 anchor.
