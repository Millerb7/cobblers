# Drops: progression to the dungeons, materials stay, and what an alpha pays instead

**Status: DESIGN AND RESEARCH ONLY (2026-10-08, escalated unit: design with no runnable check).** Nothing is built.
No data, config, world or server was changed. Inputs were read only: `Cobblemon-fabric-1.8.0+1.21.1.jar`,
`rctmod-fabric-1.21.1-0.19.0-beta.jar` and `tmcraft-1.4.19+1.8.0.jar` in the offline snapshot
`C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/` (Python `zipfile`, `javap -c`), and this
commit's `data/`, `modpack/config/` and `docs/`.

It answers the owner's direction of 2026-10-08: *"EXP CANDIES AND THE OTHER PROGRESSION ITEMS MOVE TO DUNGEONS ...
Progression items become dungeon rewards. Materials stay as drops."* It also covers item 4 of the owner's eight
(alpha candies against the cap) and item 6 (the Electirizer and the armours as a dungeon den).

Labels: **VERIFIED** means read from a jar, a config or our data at the cited place. **ASSUMED** means not read.
*relayed* marks a figure taken from another document and not re-measured here. **REASONED** marks a design
argument. Bytecode is cited as `Class.method` with `javap` offsets.

---

## 0. The answer in short

1. **No live species drop table carries a progression item, apart from the Lucky Egg.** Every Exp. Candy, every
   Rare Candy and all six IV candies that a wild Pokemon gives come from **one source**: the alpha callback's four
   tier loot tables (section 1, VERIFIED over the 219 items with a live dropper in `docs/research/notes/drops-1.8.0.json`).
   So "move progression to dungeons" comes down to switching off those four tables and deciding about the Lucky Egg.
   Everything else that drops is material, equipment or an evolution key, and stays where it is.
2. **The cap stops a candy from levelling past the cap, but it does not stop the leak** (section 2, VERIFIED in
   bytecode, not run in game). rctmod clamps each EXP gain to what the Pokemon still needs to reach the cap. A candy
   used at the cap adds 0 and is **not used up**. So candies cannot overshoot, but they **stockpile**, and at every
   new cap they are spent at once. Alpha level matching makes the tier depend on the party, not on where the alpha
   stands. **From cap 50 on, every alpha anywhere pays tier 4**: about 57,000 EXP per KO, more than the whole 50 to 55
   step of a medium-fast Pokemon (41,375).
3. **Recommendation for alphas (option C):** keep the gems and make them the alpha's whole reward. Override the four
   `alpha_rewards_tier*` loot tables at their own path with empty pools, which is data and the upstream override that
   CLAUDE.md sanctions. Add an **additive** `cobblers_` callback that rolls the alpha's type tables more often as the
   alpha's level rises, and rolls the **secondary** type too. Gems per KO go from 1.125 (L<31) to 2.25, 3.75 and
   5.625 by tier (section 3). Gems are bought by no bank, no Produce Buyer and no counter (VERIFIED), so none of it is
   income. The jar's callback is not overridden, as `.claude/rules/datapacks.md:75-78` requires.
4. **The jar's callback probably never pays a dual-type alpha its second type** (REASONED from the script text: the
   length test reads the one-entry list it has just built, `pokemon_alpha_drops.molang:22-25`). If so, flying gems
   come from 1 of our 288 alphas, not 37. Option C pays the second type whichever way experiment X5 comes out.
5. **The dungeons take the progression items per band** (section 4): Exp. Candies sized to about half a cap step for
   one Pokemon, IV candies from band 4, Rare Candy at bands 5 and 6. The Lucky Egg goes to a first clear if the owner
   moves it.
6. **The den, as a fourth, optional leg kind** (section 5):
   - **Night Shift (dungeon 1):** the powerhouse, with Electabuzz and Electivire, for the Electirizer. Expected 0.97
     a run at band 3 and above, and at least one in 68% of runs.
   - **The Last Cistern (dungeon 4):** Armarouge and Ceruledge, for the two armours. Expected 0.355 of each a run.
   - Each den also gives a guaranteed copy at that band's first clear, so every player can evolve once.

---

## 1. The classification

### 1.1 What the owner's line means here

The line is *"anything that advances a player rather than feeding a recipe"*. Read strictly, an item is
**PROGRESSION** when using it directly raises a Pokemon's level, EXP, IVs, EVs, ability or nature. It is
**MATERIAL** when its main use is as an input: a craft, a brew, a cooking pot, a TM recipe, a berry mutation or a
trade. Two groups sit between those, and this document **keeps both as drops**, for the reasons given:

- **Equipment:** held battle items. They are not consumed, there is one per party slot, and they never touch the
  levelling design. 42 of the 59 can also be crafted, and 52 of them feed at least one recipe (VERIFIED, the JSON's
  `recipe_result_count` and `recipe_ingredient_count`).
- **Evolution keys:** an evolution still waits on its level and the cap (the spawn tables' evolution policy). ADR-003
  owns the stones, and our counters already sell eleven of these keys (`data/markets.json:349-408`, VERIFIED).

### 1.2 The 219 items with a live dropper (VERIFIED: `drops-1.8.0.json`, `droppers[*][4]` true)

| Class | Count | Members | Verdict |
|---|---:|---|---|
| Vanilla material | 93 | ores, meats, mob materials, wood, plants, `relic_coin` (Gimmighoul) and the rest; full list from the JSON | **MATERIAL, stays** |
| Berries and battle consumables | 32 | 29 Cobblemon berries (resist, status and mutation inputs), `berry_juice`, `revival_herb` | **MATERIAL, stays.** Berries are mutation, cooking and brewing inputs |
| Held equipment | 59 | type boosters (`charcoal_stick`, `mystic_water`, ...), `life_orb`, `leftovers`, `expert_belt`, `focus_band`, `eviolite`, `everstone`, the seeds, the orbs, `light_ball`, `medicinal_leek` and others | **EQUIPMENT, stays** (1.1) |
| Evolution keys | 29 | the stones dropped live, `kings_rock`, `metal_coat`, `razor_claw` and `razor_fang`, `reaper_cloth`, `protector`, `magmarizer`, **`electirizer`**, `dragon_scale`, `prism_scale`, the deep-sea pair, `oval_stone`, `black_augurite`, `peat_block`, the three apples, `metal_alloy`, **the two armours**, the two saplings | **KEY, stays.** The Electirizer and the armours also get a den (section 5) |
| Broken ids (drop nothing) | 5 | `cobblemon:apple`, `minecraft:kebia_berry`, `minecraft:oran_berry`, `minecraft:razz_berry`, `minecraft:sun_stone` (`DROPS_AUDIT.md` 2.7) | not an item; out of scope |
| **Arguable progression** | **1** | **`lucky_egg`** (Blissey 0.25, Chansey 0.10, Togepi 0.073 per KO) | see 1.4 |

Counts total 219.

**No vitamin, EV feather, mint, bottle cap, PP Up, Exp. Candy, Rare Candy, Ability Capsule or Ability Patch has a
live dropper** (VERIFIED). Thirty-seven ids are dropped only by species we do not spawn (`droppers[*][4]` false
throughout). Among them, the **Rare Candy, Ability Capsule and Ability Patch come from Virizion and Okidogi alone**.
That is latent: if either species is ever placed, or caught and pastured (Pasture Loot rolls owned Pokemon:
`DROPS_AUDIT.md` 2.6), Virizion ranches 1.56 Ability Capsules an hour (VERIFIED, `ranch_per_hour`). Add both to the
Pasture Loot blacklist on the day either becomes obtainable.

### 1.3 The alpha callback's items (VERIFIED: the jar's `data/cobblemon/loot_table/alpha/**`)

| Item | Tables | Class |
|---|---|---|
| `exp_candy_xs`, `_s`, `_m`, `_l`, `_xl` | tiers 1-4 | **PROGRESSION, move** |
| `rare_candy` | tier 4 (weight 10 of 90 per roll) | **PROGRESSION, move** |
| `health_candy`, `mighty_candy`, `tough_candy`, `smart_candy`, `courage_candy`, `quick_candy` | tiers 3-4 | **PROGRESSION, move.** These are **IV** candies: *"Raises the Pokemon's effective HP IV stat by 1"* (`assets/cobblemon/lang/en_us.json`, `item.cobblemon.health_candy.tooltip_1`). `DROPS_AUDIT.md:157-158` calls them "EV candies", which is a disagreement (section 7) |
| the 18 `<type>_gem` | `alpha/types/<type>_rewards_tier1/2`, 75% | **MATERIAL, stays.** One gem goes into a TM recipe: `tmcraft:tm_absorb` is a copper blank disc, a grass gem and a sponge (VERIFIED, `tmcraft-1.4.19+1.8.0.jar!data/tmcraft/recipe/tm_absorb.json`) |
| the 18 resist berries | the same tables, 25% | **MATERIAL, stays** |

That makes **12 progression ids**, all from the alpha tier tables. The type tables hold **36 material ids**.

### 1.4 The arguable ones, with a recommendation each

| Item | Why it is arguable | Recommendation |
|---|---|---|
| **Exp. Candies** | Progression, but also an input: the hyper-training candy is 4 EV berries, 4 honeycomb and an `exp_candy_l` in the campfire pot (`SERVICES_AND_CRAFTING.md:32`, *relayed*) | **Progression.** The recipe's output is progression too, so the dungeon supplying the L candy keeps the craft route alive as a dungeon-fed route |
| **IV candies** | They are the output of that crafting route (`SERVICES_AND_CRAFTING.md:32`) | **Progression.** Dungeon reward |
| **Lucky Egg** | A held item, not consumed, that raises battle EXP. Its EXP still goes through the clamp (section 2). It is drop-only (`DROPS_AUDIT.md` 4.5) and ranchable at 2.25 an hour from a pastured Blissey (VERIFIED) | **Progression by the owner's line.** Make it a Night Shift band-1 first-clear prize and strip it from Blissey, Chansey and Togepi with `species_additions` at their paths, the rung `DROPS_AUDIT.md` 2.7 already names. **The owner's call:** it is bounded (one per slot) and cannot overshoot the cap, so leaving the drop is defensible |
| **Evolution keys** | They complete a line, which advances a player | **Key, stays** (1.1). The Electirizer and the armours are a supply fix, not a reclassification (section 5) |
| **Held battle items** | They raise battle power directly | **Equipment, stays.** The levelling design does not bound them, and nothing in the owner's line is about them. `DUNGEONS.md:267-275` already uses them as dungeon rewards as well |
| **Dragon's breath** | A material, but the gating input of the Ability Capsule by brewing (`DROPS_AUDIT.md:305`, *relayed*); a pastured Dragonair makes 6.8 an hour | **Material, stays** by the owner's line. Flag for the owner: it is the one drop whose recipe output is progression and whose ranch is fast. A Pasture Loot blacklist entry is data |
| **Feathers, honeycomb** | Inputs to EV feathers (with a mint leaf) and the IV candy | **Material, stays.** The gating input is elsewhere (mint leaves, `exp_candy_l`) |
| **Type gems** | A TM teaches a move | **Material, stays** (the owner keeps them). The graded TMCraft blanks sold by gym stay the gate (`PROGRESSION_LADDER.md:177-183`) |

**Outside the owner's line, flagged and not changed:** our counters **sell** progression items: the six vitamins
and the Ability Capsule (`data/markets.json:388-394`, VERIFIED). The direction covers drop tables.
Whether the counters' priced progression stays is a separate question (section 8, Q4).

---

## 2. Does the level cap stop alpha candies?

### 2.1 What the callback gives, to whom, when (VERIFIED, `pokemon_alpha_drops.molang`, cited by line)

- **When:** the event `cobblemon:battle_fainted`, for an actor that `is_wild` and a Pokemon that `is_alpha`
  (`:1-3`). The callback runs on a faint **in battle** only. A catch is not a faint, so it pays nothing.
- **What:** one loot table chosen by the alpha's level at the faint (`:7-17`): tier 1, then tier 2 at 31, tier 3 at
  51 and tier 4 at 66. On top of that come two independent 1-in-2 rolls of `alpha/types/<type>_rewards_tier<1|2>`,
  with the type tier at 51 (`:21-37`).
- **To whom:** nobody in particular. `spawn_loot_table_items` drops item entities at the alpha's position (`:19`,
  `:32`, `:36`), and whoever picks them up has them.
- **The tier follows the party, not the place.** A wild alpha is re-levelled to the nearest player's highest party
  level plus 4, 8, 12, 16 or 20 (`ENCOUNTER_DESIGN.md:344-361`, *relayed* from the jar's
  `AlphaLevelMatchingSensor`, owner-kept 2026-10-05). The caps are 20, 25, 30, 35, 40, 45, 50, 55 and 60 by tier
  (VERIFIED, the `eligibility_reason` strings in `data/spawns.json`). A party at its cap therefore meets these alphas:

| Player's cap | Alpha level (party + step) | Reward tier | Type tier |
|---|---|---|---|
| 20 | 24 | 1 | 1 |
| 25 / 30 / 35 | 33 / 38 / 47 | 2 | 1 |
| 40 / 45 | 52 / 57 | 3 | 2 |
| 50 / 55 / 60 / 100 | 66 / 71 / 76 / 100 | **4** | 2 |

Expected yield per KO, computed from the tables (VERIFIED weights; uniform inclusive counts; candy EXP 100, 800,
3,000, 10,000 and 30,000 from `LEVEL_CATCHUP.md:31`, *relayed*):

| Tier | EXP in candies | Rare Candy | IV candies |
|---|---:|---:|---:|
| 1 | 844 | 0 | 0 |
| 2 | 6,192 | 0 | 0 |
| 3 | 16,200 | 0 | 1.06 |
| 4 | **56,944** | 0.28 | **2.70** |

For scale, a medium-fast Pokemon (n³) needs 7,625 EXP from 20 to 25, 27,125 from 40 to 45 and **41,375 from 50 to
55**. One tier-4 alpha KO more than fills one Pokemon's whole cap step. Six of them fill a party's.

### 2.2 How rctmod's cap treats a candy (VERIFIED in bytecode; NOT run in game)

| Step | Where | What it does |
|---|---|---|
| Candy use | `CandyItem.applyToPokemon` 174-194 | builds a `CandyExperienceSource` and calls `Pokemon.addExperienceWithPlayer` with the candy's yield |
| EXP event | `Pokemon.addExperience` 62-131 | emits `CobblemonEvents.EXPERIENCE_GAINED_EVENT_PRE` before applying |
| The clamp | rctmod `ModServer.onExperienceGained` 0-104 (subscribed at `registerEventHandlers` 132-143) | if `allowOverLeveling` is false, and the Pokemon has an owner: `maxExp = getExperienceToLevel(levelCap)`; if `maxExp < experience`, an action-bar warning; then `setExperience(min(experience, maxExp))` |
| At or over the cap | `Pokemon.getExperienceToLevel` 0-27 | returns **0** when the cap is at or below the current level |
| Candy consumed? | `CandyItem.applyToPokemon` 202-216 | `stack.consume(1)` only when `getExperienceAdded() > 0`; otherwise the use fails (`method_22431`) |
| Config | `modpack/config/rctmod-server.toml:167` | `allowOverLeveling = false` |

So:

- **At the cap**, a candy (Rare Candy included) adds 0, is refused, and stays in the inventory.
- **Below the cap**, a candy is consumed and adds only up to the cap. The overflow is lost.
- **Nothing overshoots**, and this agrees with `LEVEL_CATCHUP.md:25-31` (VERIFIED there from source).
  `DROPS_AUDIT.md:531-533` ("not known", X3 at `:551`) is superseded by it.
- **What the cap does not stop is speed and stockpiling.** Kept candies are spent the moment a badge raises the cap,
  which turns a cap step from a stretch of play into a menu action. That is the owner's "uncapped EXP source", and it
  is real even with the clamp.
- The handler's priority constant was not re-read here; that it subscribes at `Priority.HIGHEST`, before
  cobblecuisine's multiplier, is *relayed* (`LEVEL_CATCHUP.md:39`).
- **Not run in game:** X3 stays owed as the in-game confirmation.

---

## 3. Alphas: worth finding, and not an EXP source

### 3.1 The constraints

- Keep the gems: they close the type-gem gap (`DROPS_AUDIT.md:303`).
- **Nothing an alpha drops may be bank income.** The bank buys 41 ids (VERIFIED, `tools/bank.py prices()` at this
  commit): ores, meats, foods, PP Max, four LumyMon feathers, elytra, emerald, diamond, netherite. The Produce Buyer
  buys 39 more in capped crates (VERIFIED, `data/produce_buyer.json`): berries, apricorns, mob materials,
  gunpowder, nether wart. **No type gem and no resist berry is in either list, or at any counter** (VERIFIED: no
  `_gem` in `data/markets.json`, `data/traders.json`, `data/bank.json` or `data/produce_buyer.json`).
- An alpha is a hard fight: it is re-levelled above the party and it retaliates (`ENCOUNTER_DESIGN.md:337-338`,
  *relayed*). It is also almost never catchable: once re-levelled over the cap, the catch block makes it break free
  (`data/level_cap.json` decision, VERIFIED). **The drop is the whole reward**, so it has to grow with the fight.

### 3.2 How a callback or loot table can be replaced (VERIFIED in bytecode)

- **Callbacks.** `CobblemonCallbacks` is a `SERVER_DATA` registry (static init 28: `class_3264.field_14190`). Its
  `reload` calls `ResourceManager.listResources("callbacks", <.molang filter>)` (47-51; filter `lambda$reload$0`,
  `".molang"`). That returns `Map<Identifier, Resource>`, **one resource per id**, so a datapack file at the jar's own
  id replaces it. The event key is the **parent folder name** in the **file's own namespace** (regex
  `.*/([^/]+)/[^/]+$`, then `Identifier.of(namespace, group)`, 246-300). Every file in a folder runs, sorted by path
  (`$reload$lambda$2$$inlined$sortBy$1`).
  - **So replacement is possible, and an addition beside it also works.** Which pack wins at equal id is vanilla pack
    order: ASSUMED standard, not observed for callbacks.
  - **Repository rule:** never override Cobblemon's own callback files; add `cobblers_*.molang` beside them
    (`.claude/rules/datapacks.md:75-78`, EXP-042). The recommendation below obeys it.
- **Loot tables.** The callback names `cobblemon:alpha/alpha_rewards_tier1..4` by id (`:7-16`). These are ordinary
  loot tables (`data/cobblemon/loot_table/alpha/*.json`, VERIFIED in the jar), so a file at the same path replaces
  them. That is the upstream override CLAUDE.md's layer model sanctions ("overridden ... from a file our generators
  emit at the same namespace path"). It is the same class of change as our rctmod leader overrides
  (`docs/STATE.md:95`).

### 3.3 The dual-type finding (REASONED; to be confirmed by X5)

Line 22 sets `t.types[0]`. Line 24 then tests `q.length(t.types) == 1`, the list it has just built with one entry,
not `t.pokemon_types`. If MoLang's `q.length` counts that one entry, the test is always true, line 25 copies the
primary type into slot 1, and **a dual-type alpha rolls its primary type twice and never its secondary**.
`DROPS_AUDIT.md:161-162` ("dual-type: half each") assumed the intended behaviour.

Our 288 alpha entries with weight above 0 (VERIFIED, `data/spawns.json`; types from the jar's species files) cover
all 18 types **by primary type alone**, so the gap stays closed either way. The thin types under the bug, though, are:

| Type | Primary-type alphas | Any-type alphas |
|---|---:|---:|
| flying | 1 (Corvisquire, L24) | 37 |
| fighting | 4 | 8 |
| fairy | 5 | 11 |
| psychic | 5 | 16 |

### 3.4 Three options

| | **A. Gems only** | **C. Gems are the alpha's reward (recommended)** | **D. The alpha rolls its own table twice** |
|---|---|---|---|
| What | empty the four tier tables; nothing added | empty the four tier tables, and add `cobblers_alpha_spoils.molang`, which rolls the type tables more with level and rolls the secondary type | at the faint, give the alpha the `drops_reroll` aspect, so its entity death rolls its species table twice (`DROPS_AUDIT.md` 2.3) |
| Gems per KO (L<31 / 31-50 / 51-65 / 66+) | 1.125 / 1.125 / 1.875 / 1.875 | **1.125 / 2.25 / 3.75 / 5.625** | 1.125 / 1.125 / 1.875 / 1.875, plus a second species roll |
| Dual types | primary only, if 3.3 holds | **both types** | as A |
| Mechanism | 4 loot tables (data) | 4 loot tables and 1 additive callback (data, rung "datapack") | an additive callback that sets a forced aspect: **whether MoLang can do that is unverified** (X4) |
| Bank income | none | none | **yes.** Thievul and Archaludon are among our 203 alpha species: a second roll adds $90.50 (emerald) and $74 (iron) per KO, and 36 more alpha species carry a bought item (VERIFIED, the JSON against `prices()`) |
| Feel | a hard high-level fight pays what a level-20 one pays | the reward grows with the fight, and each type's alphas are where that type's gems come from | thematic (an alpha Onix gives more Hard Stone) but uneven, and pays nothing for 12 table-less species |
| Verdict | the fallback, if C's callback fails its proof | **recommended** | rejected while emerald is bought (`DROPS_AUDIT.md` 9 Q1) |

**Variant B (not recommended): fill the tier tables with a type-blind material bundle instead of emptying them.** A
loot table cannot see the alpha's type. And of the materials with no drop route (`DROPS_AUDIT.md:314-317`), each
useful one fails a filter:

| Material | Fails because |
|---|---|
| gunpowder, nether wart | the Produce Buyer buys them |
| quartz | the bank buys it |
| sculk | it is the Exp. Candy XS recipe (`SERVICES_AND_CRAFTING.md:33`) |
| blaze rod | it is a brewing stand, a priced unlock (`ITEM_ROUTES.md:56`) |
| mint leaves | they are the EV/IV and nature gate |
| the four stones | ADR-003 owns them |
| wither skull, nether star | they are boss and beacon gates |

What is left (cobweb, ghast tear, breeze rod, pink petals) does not make an alpha worth finding.

### 3.5 Option C as data (a sketch; not built, not run)

**Files:**

1. `data/cobblemon/loot_table/alpha/alpha_rewards_tier{1,2,3,4}.json`: each `{"type": "minecraft:chest",
   "pools": []}`. The jar's callback still runs and still makes its two type rolls, but the tier table now spawns
   nothing. **This is a safe floor on its own:** if file 2 never loads, the game is at option A, with no candies and
   no double gems.
2. `data/cobblemon/callbacks/battle_fainted/cobblers_alpha_spoils.molang`, written only in the forms the jar's own
   script uses (ternaries, `math.random_integer`, `q.length`, string concatenation, `spawn_loot_table_items`):

```
c.pokemon.actor.is_wild ? {
  t.pokemon = c.pokemon.pokemon;
  t.pokemon.is_alpha ? {
    t.e = t.pokemon.entity;
    t.world = t.e.world;
    t.pt = t.pokemon.types;
    t.second = (q.length(t.pt) > 1) ? t.pt[1] : t.pt[0];
    t.tier = (t.pokemon.level >= 51) ? 2 : 1;
    t.base = 'cobblemon:alpha/types/';
    (t.pokemon.level >= 31) ? {
      t.world.spawn_loot_table_items(t.base + t.second + '_rewards_tier' + t.tier, t.e.x, t.e.y, t.e.z);
    };
    (t.pokemon.level >= 66) ? {
      t.world.spawn_loot_table_items(t.base + t.pt[0] + '_rewards_tier' + t.tier, t.e.x, t.e.y, t.e.z);
    };
  };
};
```

**Yield.** Our extra rolls are certain, where the jar's are 1 in 2. Each type-table roll yields 0.75 x the mean
count: 1.125 gems at type tier 1 and 1.875 at tier 2.

| Alpha level | Jar's 2 rolls at 50% | Ours | Gems per KO |
|---|---:|---:|---:|
| under 31 | 1.125 | 0 | 1.125, unchanged at leg 1 |
| 31-50 | 1.125 | 1 roll, secondary | 2.25 |
| 51-65 | 1.875 | 1 roll, secondary | 3.75 |
| 66+ | 1.875 | 2 rolls, secondary and primary | 5.625 |

**The knob is the number of rolls per band.** It is `trainer-balance-designer`'s, and the owner's if they want
fewer.

**Economy (REASONED).**

- A gem is one TM's ingredient. The graded TMCraft blank, sold by gym at 500 to 2,800 (`PROGRESSION_LADDER.md:177-183`,
  VERIFIED), stays the gate, so more gems mean more choice of moves, never earlier grades.
- No gem or resist berry is bought anywhere (3.1).
- The callback fires only on a battle faint, so it multiplies effort, never AFK: Pasture Loot ignores alpha rewards
  (`DROPS_AUDIT.md:194-195`).
- **What it costs the dungeons:** gems were their "spine" because "nothing in our world drops them"
  (`DUNGEONS.md:262-265`), which is already stale. Under this design **the dungeons' exclusive is progression**
  (section 4), which is a stronger reason to run one.

**What a player sees.** An alpha is a hard fight that pays the best battle EXP in the area (clamped, the designed
route), its own species drop, a 10% Tera Shard (`DROPS_AUDIT.md` 2.5) and a pile of its types' gems that grows with
the game. Hunting a flying alpha for flying gems becomes a reason to go somewhere.

**Validator (for `test-author`, not written here):**

- the four tier tables are empty;
- no file in our packs other than a dungeon reward table names a progression id from 1.3;
- `cobblers_alpha_spoils.molang` exists and no file overrides `pokemon_alpha_drops.molang`;
- **the mutation that proves it:** add `exp_candy_xs` back to the tier-1 override and the check must fail.

---

## 4. The progression items in the dungeons (changes listed for `DUNGEONS.md` and `DUNGEON_PLACEMENT.md`; not made)

Candies are type-neutral, so they scale **by band** (`DUNGEONS.md:291-298`), not by home. Sizing rule (REASONED):
**one run's candies are about half a cap step for one medium-fast Pokemon at that band.** A run then helps one
Pokemon catch up, and never levels a party.

| Band (cap at entry) | Cap step (EXP, n³) | Candies per run | EXP | IV candies | Rare Candy |
|---|---:|---|---:|---|---|
| 1 (20, 25) | 7,625-11,375 | 1 M + 2 S | 4,600 | none | none |
| 2 (30, 35) | 15,875-21,125 | 3 M | 9,000 | none | none |
| 3 (40, 45) | 27,125-33,875 | 1 L + 2 M | 16,000 | none | none |
| 4 (50, 55) | 41,375-49,625 | 2 L + 1 M | 23,000 | 1-2 of one random stat | none |
| 5 (60, 62) | 49,625 (55 to 60) | 1 XL | 30,000 | 2-3 | 1 |
| 6 (100) | 784,000 (60 to 100) | 2 XL | 60,000 | 3-4 | 1-2 |

The exact bundles are `trainer-balance-designer`'s.

**Against today's alpha, for scale:** a band-4 run is about 40% of one tier-4 alpha KO. That is the point of the move.

**Changes to `docs/mechanics/DUNGEONS.md`:**

- **D1. Section 4 rule (`:250-256`):** add "a progression item (1.3's twelve ids, and the Lucky Egg if Q1 moves it)
  is a dungeon reward and appears in no other generated table". The generator and the validator fail closed on one
  anywhere else: the alpha tables, `data/rewards.json`, `data/markets.json`, `data/traders.json` and the arena.
- **D2. Section 4 table (`:267-275`):** add a "progression, every home, by band" sub-table (the table above).
- **D3. Section 4 "Why gems are the spine" (`:262-265`):** stale. Alphas drop gems in every type
  (`DROPS_AUDIT.md` 2.4), and more under option C. Restate it as "gems are the dungeons' volume and progression is
  their exclusive".
- **D4. Section 4 "Scaling of rewards" (`:277-281`), first clears:**
  - Night Shift band 1: the Lucky Egg (if moved).
  - Night Shift band 3: one Electirizer.
  - Last Cistern band 4: one Auspicious and one Malicious Armor.
  - The band-5 first clear of any home: one Rare Candy.
- **D5. Section 2.3 (`:170-193`):** a fourth leg kind, **the den** (section 5). It is **optional**: the boss door
  still opens on the two required legs, so the run stays inside the 25-31 minutes of `:162-168`.
- **D6. Section 6 replay (`:321-337`):** item 3 becomes "gems and progression never stop being wanted".
- **D7. Section 7.1 schema (`:347`):** per band, `progression` (a list of `{item, count}`). Per dungeon, an optional
  `den` (`{species_by_band, count, uncatchable: true}`).
- **D8. Section 7.2 validation:**
  - D1's check;
  - every den species has a drop entry for its declared item;
  - no den Pokemon is an alpha;
  - the den's per-run expected yield is computed from the species file with `DROPS_AUDIT.md` 2.1's roll model,
    never stated by hand.
- **D9. Section 8:** add Q1-Q5 of this document.

**Changes to `docs/mechanics/DUNGEON_PLACEMENT.md`:**

- **P1. C4 (`:166-171`):** "Bands 1-5 reward items only" holds; candies and IV candies are items. Add that a band's
  progression bundle is sized by D2's rule.
- **P2. Section 3 (`:127-138`):** the window (band 5, cap 60) gets candies up to 60 only, because the clamp holds.
  This adds no Elite Four exposure beyond what the free training grounds already allow (REASONED).
- **P3. "Key bosses are never alphas" (`:135-136`):** extend it to every dungeon Pokemon. A den alpha would pay alpha
  gems, re-level above the band and break the cap's catch block.

---

## 5. The den: the Electirizer and the armours

**Why a den.** At the best place today, the Electirizer drops 0.0019 times per spawn and the armours 0.0004 times
(`DROPS_AUDIT.md:260-261`, *relayed*; 6.2). Our counters sell eleven evolution keys but none of these three
(VERIFIED, `data/markets.json:349-408`). The rates below are the exact per-KO figures from the species tables
(VERIFIED, `drops-1.8.0.json`, `per_defeat`, 2.1's model).

**The leg (REASONED).**

- One room off the hub holds four wild Pokemon, spawned at the band's level (cap-2 to cap-1, the arena rule) when the
  slot is built, and KO'd in battle.
- They are **`uncatchable`** (the Entei farm-mode pattern, `data/entei_boss.json:22-26`) and **never alpha**.
- Drops are the **species' native tables** at entity death (`DROPS_AUDIT.md` 2.2). No generated loot is involved.
  They land on the entity in a per-player slot.
- About 5-6 minutes (ASSUMED: four wild battles; no fight has been timed).

**Night Shift (dungeon 1) powerhouse: the Electirizer.**

- *Why here.* The mine's "lamps down there are still lit" (`DUNGEONS.md:225`). Electabuzz is caught at Arrow Creeks,
  levels 43-53 (VERIFIED, `data/spawns.json`), so the item matters from band 3 on, and the Night Shift is open at
  every band.
- *Why Elekid at bands 1-2.* It is not catchable in the den, and an Electirizer that early has no Electabuzz to use
  it on.

| Band | Den | Electirizer expected per run | P(at least one) |
|---|---|---:|---:|
| 1-2 | 4 Elekid (0.0494 each) | 0.198 | 0.183 |
| 3 | 3 Electabuzz (0.1426), 1 Electivire (0.3439) | 0.772 | 0.586 |
| 4-6 | 2 Electabuzz, 2 Electivire | 0.973 | 0.684 |

- *Side drops.* Redstone is bought at $2: 1.0 a KO from Electabuzz and 1.5 from Electivire, so about 5 a run, about
  $10. Declare it to `tools/economy_audit.py` as the seam's ores are, on the lockout clock (`DUNGEONS.md:184-186`).
  Cheri berries are not bought.
- *Guarantee.* The band-3 first clear gives one Electirizer (D4).

**The Last Cistern (dungeon 4): the two armours.**

- *Why here.* It opens at about gym 7 on the plateau (`DUNGEONS.md:228`). Charcadet is caught at Plateau East, levels
  48-53, rare (VERIFIED, `data/spawns.json`). So the den opens at the band where the evolution becomes possible.
- *Theme.* The dead town's two sentries: the blessed knight and the cursed blade.
- *Charcadet itself* drops no armour (VERIFIED: charcoal, charcoal stick, rawst berry).

| Band | Den | Each armour, expected per run | P(at least one of a given armour) | P(both) |
|---|---|---:|---:|---:|
| 4-6 | 2 Armarouge (Auspicious 0.1775), 2 Ceruledge (Malicious 0.1775) | 0.355 | 0.324 | 0.105 |

- *Side drops.* Charcoal is not bought.
- *Guarantee.* The band-4 first clear gives one of each armour (D4), so every player can evolve one Charcadet either
  way. The den is the repeatable source after that, about three runs per further armour.
- *Alternative home, the owner's choice:* **the Temple Calendar** (sun and moon: Armarouge by day, Ceruledge by night,
  the reading in `DROPS_AUDIT.md:407`). It opens later, at `gym8_cleared` (`DUNGEON_PLACEMENT.md:133-134`), a band
  after Charcadet is catchable.

**If `drops_reroll` can be set on a spawn (X4):** den Pokemon carrying it would double every rate above, raising the
armour odds to 0.542 a run. Do not count on it until X4 runs.

---

## 6. Experiments owed (none run)

- **X3** (`DROPS_AUDIT.md` 10): an Exp. Candy and a Rare Candy used at the cap are refused and kept; one below the
  cap is consumed and stops at the cap.
- **X5** (`DROPS_AUDIT.md` 10), extended: KO a **dual-type** alpha, for example Butterfree (bug/flying), ten times,
  and record the gem types. That settles 3.3. Then, with option C's pack, the tier tables spawn nothing and the gem
  counts match 3.5's table.
- **X6. Callback load count:** with `cobblers_alpha_spoils.molang` added, the log's callback count rises by one and
  the jar's file still loads. Cobblemon logs the count at `CobblemonCallbacks.reload` 1011-1025.
- **X4** (`DROPS_AUDIT.md` 10): only for the den's optional doubling.

---

## 7. Disagreements found (for whoever owns each document)

| Document | Says | Actually |
|---|---|---|
| `docs/research/DROPS_AUDIT.md:157-158` | "the six EV candies" | IV candies (lang tooltips, 1.3) |
| `docs/research/DROPS_AUDIT.md:161-162` | "dual-type: half each" | the script tests the list it just built; probably primary only (3.3, REASONED, X5) |
| `docs/research/DROPS_AUDIT.md:164-175`, "first at tiers 1-4" | reward tier read from the authored level | the level fought follows the party (`ENCOUNTER_DESIGN.md:344-361`), so from cap 50 every alpha pays tier 4 (2.1) |
| `docs/research/DROPS_AUDIT.md:531-533` (Q4), `:551` (X3) | not known whether the cap stops candies | clamped, and not consumed at the cap (2.2; agrees with `LEVEL_CATCHUP.md:25-31`) |
| `docs/mechanics/DUNGEONS.md:263` | "nothing in our world drops them" (gems) | alphas drop them in every type |
| `docs/mechanics/ITEM_ROUTES.md:179` (row 5) | Exp. Candies and Rare Candy as counter lines from gym 4 | superseded by the owner's 2026-10-08 direction: dungeon rewards |

---

## 8. Open questions for the owner, each with a recommendation

1. **Q1. The Lucky Egg:** move it (a first clear, stripped from three tables) or leave the drop? *Recommend move it*,
   by the line. It is the owner's call because it cannot overshoot the cap.
2. **Q2. Option C's roll counts** (2.25 / 3.75 / 5.625 gems by tier): keep them, or cap tier 4 at 3.75? *Recommend
   keep them.* The blank is the gate.
3. **Q3. The armour den's home:** the Last Cistern (it opens when Charcadet is catchable) or the Temple Calendar (sun
   and moon, a band later)? *Recommend the Last Cistern.*
4. **Q4. The counters' priced progression** (vitamins, the Ability Capsule, `data/markets.json:388-394`): outside
   this direction. Stay? *Recommend it stays.* It is priced, the direction is about free drops, and
   `SERVICES_AND_CRAFTING.md` builds on it.
5. **Q5. Dragon's breath** (the Ability Capsule's brewing input, ranchable at 6.8 an hour): add it to the Pasture Loot
   blacklist? *Recommend yes.* It is the one material whose fast ranch prints a progression item.
