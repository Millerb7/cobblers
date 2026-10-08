# Drop-rate consumers: what else was computed against the wrong figures, and the TM sweep re-run

**Status: AUDIT ONLY (2026-10-08, escalated unit: the economy's arbitrage, CLAUDE.md escalation rule 1).** No data,
config, world or server was changed. Inputs, read only: this commit's `data/`, `tools/`, `tests/` and `docs/`; the
offline snapshot `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05` (`mods/*.jar` with their nested
jars, `datapacks/*.zip` and folder packs, `extra/` excluded); and the vanilla 1.21.1 jar under
`%APPDATA%/ModrinthApp/meta/versions/1.21.1-0.19.5/`. Labels follow `.claude/rules/research.md`. Scratch scripts
produced every figure here; they are not committed, as the 2026-10-05 sweep's were not.

The fact everything below is measured against is `docs/research/DROPS_AUDIT.md` 2.1 and 2.6: a drop table's `amount`
is a number of passes and each pass takes the first entry that rolls, so the file's percentage is not the per-defeat
rate; Pasture Loot keeps ONE entry of each roll, uniformly, and a blacklisted pick drops nothing.

---

## 1. The rate table was re-derived first

An independent implementation of the two models (not `tools/economy_audit.py expected_picks`, not the audit's
scripts) recomputed `per_defeat` and the Pasture Loot `ranch_per_hour` from the entries as written, for every table
of up to seven entries in `docs/research/notes/drops-1.8.0.json`. **Largest disagreement over all of them: 0.0001.**
Spot checks (per wild death; per pastured Pokemon an hour, blacklist ignored where it says so):

| Species (N) | Entry as written | Per wild death | Ranch per hour |
|---|---|---:|---:|
| Thievul (6) | emerald 5% | 0.2262 (file says 5%) | 0.955 unblacklisted (0.106 a proc), 0 as configured |
| Sableye (6) | diamond 5%, emerald 5% | 0.217, 0.208 | 0.813, 0.778 unblacklisted |
| Steelix (7) | raw iron 100% 2-4 | 3.0 | 18.16 unblacklisted |
| Onix (6) | hard stone 2.5% | 0.1189 | 0.502 |
| Flareon / Jolteon (2) | fire / thunder stone 25% | 0.4375 | 3.741 |
| Gimmighoul, Gholdengo (48) | relic coin 100% 24-48 | 36.0 | 324 (single entry: whole roll and one entry agree) |
| Archaludon (1) | iron ingot 50% 1-32 | 8.25 | 74.25 unblacklisted (single entry) |
| **Litleo (1)** | rotten flesh 100%, **blaze powder 5%** | **blaze powder 0.0** | 0 |

The JSON is safe to rely on. **One correction to DROPS_AUDIT itself:** its 4.4 row "Blaze powder ... 16 live; Litleo
at North Shore Downs, uncommon" (`DROPS_AUDIT.md:307`) names a dropper whose upstream rate is zero (amount 1 and a 100%
entry first; the JSON's own `per_defeat` is 0.0). 15 live droppers have a non-zero rate. Litleo drops blaze powder
only once `cobblers_drop_fixes` (`data/drop_fixes.json`, world-local, "built, not observed in game") is installed.
The JSON predates that pack: it has the 13 upstream tables the fixes replace (Helioptile and Heliolisk Sun Stone,
Pancham, Pangoro, Litleo, the Blipbug line, Gulpin, Swalot, Delcatty, Spritzee, Deoxys), so a consumer of the JSON
sees the unfixed rates.

---

## 2. Every consumer, and its verdict

"Nominal" = the file's percentage taken as the rate. "Whole roll" = Pasture Loot assumed to pay the whole `getDrops`
result. "Presence" = the check asks only whether some entry names the item, which no rate error can touch.

| # | File:line | Figure as written | Model used | Corrected figure | Consequence |
|---|---|---|---|---|---|
| 1 | `data/bank.json:286` (`decisions_pending ranch_ore`) | Steelix "9 drops an hour x 3 raw iron x $8 = $216 an hour"; Sableye "0.45 diamonds ($54) and 0.45 emeralds ($180) an hour" | whole roll; **and nominal 5% for Sableye** | Steelix 18.16 raw iron an hour = **$145** (1.5x high); Sableye **0.81 diamonds ($98) and 0.78 emeralds ($311)** an hour: the nominal 5% **understated** it 1.7-1.8x, more than the whole roll overstated it | **None now:** resolved by blacklisting all eight ore ids (`modpack/config/PastureLoot.json`). The decision text understated the emerald ranch it closed |
| 2 | `data/bank.json:49` (relic coin, `base_removed`) | "If Pasture Loot pays a whole roll (ASSUMED) ... 9 x 36 x $50, $16,000 an hour" | whole roll | **$16,200, and VERIFIED, not ASSUMED:** a single-entry table, so one entry and the whole roll agree | None (relic coins left the bank). The ASSUMED label is the stale part |
| 3 | `data/bank.json:89` (`afk_rule.ranch.why`) | "15% chance a minute to drop from its own species drop table ... (ASSUMED)" | presence | Right in effect: 0.15/1200 a tick is 9 procs an hour, VERIFIED from the mixin (DROPS_AUDIT 2.6). The text still says ASSUMED | None. The rule (any non-blacklisted entry is a ranch drop) holds under the one-entry model |
| 4 | `data/bank.json:99` (`not_decided_here`) | meats "dormant: their animals are on the mobsbegone blacklist and their items on Pasture Loot's" | presence (wrong premise, not a rate) | 61 live chicken droppers etc. (DROPS_AUDIT 8.2, *relayed*); wild deaths have no blacklist | Already DROPS_AUDIT's finding: meat is live income from leg 1 |
| 5 | `tools/bank.py:391-425` (`ranch_drops`) and the ranch check | which bought items a ranch makes | presence | Right. It also counts zero-rate entries (Litleo's blaze powder) and both a base table and the addition that replaces it: over-inclusive, which fails safe. It reads `mods/` and global `datapacks/` only, so a world-local `cobblers_drop_fixes` id is invisible to it (none of those ids is bought today) | None |
| 6 | `tools/economy_audit.py:1386-1419` (`ranch_money_report`), `:1409` | money an hour per pastured Pokemon = expected picks of the entry in one roll x mean quantity x 9 | **whole roll** (the pass model itself, `expected_picks` `:1340-1383`, is right) | One entry per proc: Thievul emerald **0.106 a proc, not 0.226** (2.1x high). Exact for single-entry tables | **Report only, and dormant:** it reports `afk_rule.exceptions`, which today holds only `chorus_fruit`, not a drop. If an exception for a multi-entry drop returns, it will over-report about 2x (fails safe, but a wrong number) |
| 7 | `tests/test_economy_audit.py:933-943` | pins "ranch money minecraft:emerald at $400: best thievul, 0.226 a drop" | whole roll | 0.106 a proc: $382 an hour per pastured Thievul under the base blacklist, not $814 | The test pins the wrong figure as correct; it would fail a fix of item 6. Flag for `test-author` |
| 8 | `tools/economy_audit.py` (no line: absent) | no check of wild-death drops | none | Thievul emerald **$90.48 a wild death** (0.2262 x $400) from tier 4; Sableye $109 | Gap DROPS_AUDIT 8.3 named; still open. Nothing fails on the emerald |
| 9 | `tools/income_model.py:37-41`, `:239` (`excluded`) | "wild battles: they pay nothing" | none (uses no drop figure) | CobbleDollars pay nothing for wild battles (true), but **drops reach money through the bank**: emerald and meat (DROPS_AUDIT 8.1) | Not a wrong figure, an omission: `cumulative_by_badge`, and so every income-gated price, leaves out banked drops. At 25 Thievul KOs an hour (ASSUMED rate) that is ~$2,260 an hour from tier 4, against a leg-4 fight hour of $4,104 (`leg_by_badge` 16,415 / 4) |
| 10 | `data/produce_buyer.json:57` (`ranch` crate) | 16 ranch goods a crate, scheduled allowance | count-capped, no rate | Right: the cap bounds it whatever the rate | None (meat is still not in a crate: DROPS_AUDIT 8.2, an owner call) |
| 11 | Mining caves and farms: `tools/mining_caves.py`, `mining_caves_audit.py`, `mining_works.py`, `cavern_farms.py`, `data/mines.json`, `data/apricorn_farm.json`, `data/pokemon_farm.json:22`, `data/bank.json effort_model` | ore and fruit an hour | block loot and ASSUMED hours; no species drop figure (grep: none) | Unaffected. `pokemon_farm.json:22` (leather and beef "need a death") is presence and right | None |
| 12 | `docs/OVERNIGHT_REVIEW_2026-10-06.md:154` (N145) | "a pasture of 16 makes ~$13,030/h in emeralds (Thievul) or ~$10,692/h in iron (Archaludon)"; relic coins ~$16k/h | whole roll | Thievul **~$6,110/h** (16 x 0.955 x $400; 2.1x high). Archaludon $10,692 and relic coins $16,200 stand (single entry) | None now: emerald and iron ingot are blacklisted, relic coins left the bank. The headline ranch figure was double |
| 13 | `docs/OVERNIGHT_REVIEW_2026-10-06.md:167` (N158) | iron helmet and sword missing from the blacklist | presence | Right | None |
| 14 | `docs/mechanics/ECONOMY_OVERHAUL.md:181` | "farm Megas, 15% a drop" | our own roll (`cobblers_gulch_drops.molang`, `gm.pct`), not a species table | Right: one roll per Mega, as authored | None |
| 15 | `docs/mechanics/ECONOMY_OVERHAUL.md:197-215` (2.2, the AFK rule) | "every drop a Pasture Loot ranch makes" | presence | Right | None. Its premise "ore, gems ... each needs a player at the pick" (`:197`) is now wrong for gems: they come from alpha battles (DROPS_AUDIT 2.4); the bank buys no gem, so no price moves |
| 16 | `docs/mechanics/STONE_ECONOMY.md:331`, `:336` | no Fire Stone line; Eevee absent | presence (stale) | Eevee, Growlithe, Kanto Vulpix live (DROPS_AUDIT 4.2, *relayed*). Every Eeveelution ranch is **3.74 stones an hour**: a single-entry table, so this figure is exact under either Pasture model | The stone scarcity the document designs is not there after one Eevee (DROPS_AUDIT 9 Q3) |
| 17 | `docs/mechanics/SERVICES_AND_CRAFTING.md:104-111` (ranch ore) | the seven ores were measured as ranch drops | presence | Right | None |
| 18 | `docs/mechanics/MINECRAFT_PLAY_LOOPS.md:118`, `:195`, `:239`, `:300` | Pasture "15% a minute ... ASSUMED"; "the 9 drop rows" the Bank buys; "any drop the Bank buys is AFK money" | presence, stale | Pasture VERIFIED (one entry). The bank buys no drop row now (`data/bank.json buys_removed`, 2026-10-10) and none of its 13 bought ores is a ranch drop | Stale text; no number to correct |
| 19 | `docs/mechanics/MINECRAFT_PLAY_LOOPS.md:92` | "294 of 335 native TM recipes need" a gem, gems from "Mines gem clusters (if any are authored)" | presence | Gems come from alpha battles (2.4); see section 3 | The proposed gem seams (`:183-186`, `:269`) are no longer the only gem route |
| 20 | `docs/research/OBTAINABILITY_VANILLA_COBBLEMON.md:126` (row 14) | evolution items "B at 2.5-10% per KO" | **nominal** | 5-41% per KO (Metal Coat 13.6%, Razor Fang 9.4%, Reaper Cloth 24.9%, Dragon Scale 41%; DROPS_AUDIT 4.1, *relayed*, consistent with the JSON) | Verdict ("nothing needed") stands on the rate, falls on rarity: the Electirizer and the Charcadet armours are 0.0019 and 0.0004 per spawn (DROPS_AUDIT 6.2) |
| 21 | `docs/research/OBTAINABILITY_VANILLA_COBBLEMON.md:121-122` (rows 9, 10) | Porygon-Z Dubious Disc 25%, Porygon2 Upgrade 25% | nominal | **25% is right:** single-pass, single-entry tables (amount 1) | None |
| 22 | `docs/research/OBTAINABILITY_VANILLA_COBBLEMON.md:65`, `:67-70`, `:82-85` | alpha trigger "not found"; Pasture ASSUMED; "a crafted TM economy impossible" | presence | Alpha callback exists (DROPS_AUDIT 2.4); Pasture VERIFIED; **603 TMs craftable** (section 3) | The crafted-TM verdict is reversed |
| 23 | `docs/research/OBTAINABILITY_SWEEP_2026-10-05.md:39` (tier B) | "drops of species `data/spawns.json` names ... Pasture Loot farms them" | presence; no rate, no rarity | Right as presence; it counted zero-rate and broken-id entries as routes (DROPS_AUDIT 2.7) | Below for the TM rows |
| 24 | `OBTAINABILITY_SWEEP_2026-10-05.md:119`, `:148` (P0 gems, "none of the 3,596 TM recipes is craftable") | gems NC/F | presence, with alpha rewards at F | **0 of 802 TMs is craftable without alpha gems (reproduced); 603 are with them** | P0 is closed by battle; its proposed route ("sell finished TMs ... or sell gems per gym type") lost its premise. Its "3,596" counted recipes the server does not load (section 3.1) |
| 25 | `OBTAINABILITY_SWEEP_2026-10-05.md:155` (P1 candies) | "cut the candies deliberately" | presence | Alpha battle KOs pay Exp. Candies at every tier, Rare Candy from L66 (DROPS_AUDIT 2.4, *relayed*) | Not cut: an owner call (DROPS_AUDIT 9 Q4) |
| 26 | `docs/mechanics/ITEM_ROUTES.md:80-84` (2.1), `:362-363` | "none of 3,596 TM recipes is craftable"; "nothing in our world drops" ghost and dragon gems | relayed from 24 | 603 TMs craftable; the **Griseous Orb is craftable** (ghost gem from tier 6, dragon gem from tier 2, section 3.4) | Route A's case ("all 23 pool TMs attainable") now has a free competitor; the Griseous Orb no longer waits on the Core cache |
| 27 | `docs/mechanics/DUNGEONS.md:262-265` | gems "are the spine" because "nothing in our world drops them"; "no power bypass, because the counters' TMCraft blanks still gate the grade by gym (`PROGRESSION_LADDER.md:177-182`)" | relayed | **Both premises fail:** alpha hearts drop gems from leg 1, and **no counter sells a blank** (`data/markets.json`: no `blank` item, grep 0) **and every blank disc is craftable** without a shop (3.2) | The dungeon's gem reward is not exclusive, and nothing gates a TM's grade |
| 28 | `tools/player_guide_drops.py:29-45`, `tools/drop_fixes.py` (intent check) | per-defeat chances | the exact pass model | Right (both enumerate `getDrops`) | None |
| 29 | `data/spawns.json` `held_items[].percentage` (142 lines) | a held item's chance | a different mechanism (rolled at spawn, dropped first on a wild death) | Not a drop-table percentage; unaffected | None |

**In short:** no price or verdict that is live today rests on a wrong drop figure. Every rate-dependent number that
was wrong (items 1, 2, 6, 7, 12) priced an AFK route that a later decision already closed (the ore blacklist, the
bank's removals), and the errors ran both ways: the whole-roll assumption doubled Thievul's ranch, while the nominal
5% understated Sableye's 1.8x. The verdicts that do change are not rate errors but **source** errors: the gem and
candy routes nobody found (items 15, 19, 22, 24-27), and the drop income the income model leaves out (item 9).

---

## 3. The TM sweep, re-run with alpha gems

### 3.1 Method and what it reproduces

A reachability fixpoint over every recipe the server loads (9,692 recipe files: vanilla, 102 jars and their nested
jars, the global datapacks; a datapack overrides a jar at the same path; `fabric:load_conditions` on an absent mod
drop the recipe). Seeds, the 2026-10-05 sweep's tiers: **A** vanilla block drops (generous, as that sweep's; minus
worldgen-only items and, because the overworld is a pre-exported WorldPainter world with no vanilla structures, minus
sponge and bell), vanilla fishing loot, our counter and stall lines (`data/markets.json`, held lines and TMs
excluded); **B** every registered item with a live dropper of non-zero rate (214, from the JSON); **N** Nether blocks;
**modded worldgen** (Cobblemon ores, gem clusters, fossils) off except the Nether's fire stone ore; a modded plant's
loot once its seed or produce is reached; Cobblemon berry mutations (`berries/*.json`); stations (furnace kinds,
stonecutter, smithing table, brewing stand, a campfire pot of any colour) must themselves be reached. The **alpha
rewards** (48 items: 18 gems, Exp. Candies, EV candies, Rare Candy, resist berries; DROPS_AUDIT 2.4 tables) are the
added tier.

| | Without alpha | With alpha |
|---|---:|---:|
| Items reached | 2,401 | 3,677 |
| TMCraft TMs craftable (802 distinct `tmcraft:tm_*`, 805 native recipes, every one naming a gem) | **0** | **603** (75%) |
| ... counting three interactions the model cannot see (a lava bucket, an enchanted book from an enchanting table, a written book) | 0 | **614** |

**The baseline reproduces the 2026-10-05 sweep's "none craftable"**, so the difference is the alpha tier alone. Held
items of our spawns (26) add nothing. Each of the 802 also converts 1:1 to a `cobblemon:technical_machine` (929
`to_cobblemon_tm_*` recipes). The loaded TM-producing recipes are **1,734** (TMCraft jar 1,251 after the Cobbleverse
pack's 483 same-path overrides, plus those 483), not the sweep's 3,596: TMCraft's `simpletms` conversions carry a load
condition on a mod we do not run, and an overridden recipe is one recipe.

### 3.2 The blank discs need no shop

Read from `tmcraft-1.4.19+1.8.0.jar` `data/tmcraft/recipe/`: `copper_blank_disc` is one copper ingot, shapeless.
Iron, gold, diamond and emerald discs are smithing upgrades (template + previous disc + iron ingot / gold ingot /
diamond / emerald; netherite from diamond + netherite ingot). The `move_upgrade_smithing_template` is 7 gold ingots
+ cobbled deepslate + **one blaze powder** (a B drop) the first time, then 7 gold + deepslate + a template **gives 2**:
self-sustaining. At the bank's prices (`tools/bank.py prices`: copper ingot $3, iron ingot $9, raw gold $20, diamond
$120, emerald $400, netherite ingot $900), the cash a player forgoes per disc is **copper $3, iron $152, gold $312,
diamond $572, emerald $852, netherite $1,612** (a template at 7 x $20).

### 3.3 The income-gated shelf (`data/markets.json` `price_policies.income_gate`)

The gate's criterion: a line with `gate_badge` B is priced strictly above `cumulative_by_badge[B]`, so it is
affordable no earlier than leg B+1. A craft is available at the tier of its gem (tier N = the leg to gym N, holding
N-1 badges, as `income_gate.gate_badges.sachet` defines it). Gem tiers are the earliest live **alpha** entry of the
type (computed from the JSON's live places and the species' types read from the Cobblemon jar).

| TM (badge, price) | Recipe | Craft cash | Gem: earliest alpha | Verdict |
|---|---|---:|---|---|
| Rock Tomb, Rock Slide (b1, $4,100) | gold disc + rock gem + obsidian / gravel | $312 | tier 3, Graveler L25 Mt Clay (common) | craftable; after the gate, at 1/13 the price |
| Headbutt (b1, $4,100) | gold disc + normal gem + Rocky Helmet (drop, $3,000 line, or crafted) | $312 | tier 1, Bibarel L15 (uncommon) | **before the gate** |
| Bide (b1, $4,100) | gold disc + normal gem + turtle helmet + 2 X Attack (campfire pot; Liechi by mutation) | $312 | tier 1 | before the gate; a long chain |
| Bubble Beam, Scald (b2, $8,700) | gold disc + water gem + magma block (Nether) / blaze powder | $312 | tier 1, Bibarel L15 (uncommon) | **before the gate** |
| Water Pulse (b2) | gold disc + water gem + **bell** | | | **blocked**: no villages in the pre-exported overworld; only our placed bells (finite) |
| Thunder (b3, $18,600) | diamond disc + electric gem + Thunder Stone ($2,100 at Steepside, Pikachu, or a Jolteon ranch) | $572-2,672 | tier 1, Minun L11 (uncommon) | **before the gate** |
| Thunderbolt (b3, $18,600) | diamond disc + electric gem + Electirizer (0.0019 per spawn; ranches at 1.41 an hour from a caught Electivire) | $572 | tier 1 | craftable once an Electivire is caught |
| Shock Wave (b3, $18,600) | gold disc + electric gem + X Accuracy (Micle by mutation) | $312 | tier 1 | before the gate; a long chain |
| Mega Drain, Giga Drain (b4, held) | iron / gold disc + grass gem + **sponge** | | | **blocked**: no monuments, elder guardians off |
| Toxic (b5, $56,500, held) | emerald disc + poison gem + Black Sludge | $852 | tier 1, Oddish L9 (uncommon) | craftable from leg 1 |
| Poison Jab, Poison Fang, Poison Gas (b5, $56,500, held) | gold / gold / iron disc + poison gem + Black Belt / Razor Fang and Poison Barb / Smoke Ball | $152-312 | tier 1 | craftable from leg 1 |
| Psywave, Calm Mind (b6, $90,200, held) | gold / emerald disc + psychic gem + repeater / target | $312-852 | tier 3, Lunatone L25 Mt Vessu (common) | craftable from leg 3 |
| Skill Swap (b6, $90,200, held) | emerald disc + psychic gem + enchanted book + Link Cable ($2,160 exchange) | ~$3,000 | tier 3 | craftable (enchanting table) |
| Overheat (b7, $134,400, held) | netherite disc + fire gem + 2 lava buckets (Nether) | $1,612 | tier 1, Growlithe L10 (uncommon) | craftable |
| Fire Blast (b7, held) | diamond disc + fire gem + **TNT** | | | **blocked**: gunpowder has no live dropper |
| **Earthquake (b8, $202,900, held)** | diamond disc + ground gem + crying obsidian (Nether ruined portals) | **$572** | **tier 1**, Diggersby L20 Viltri Plateau (uncommon) | craftable from the first Nether trip: **0.3% of its price** |
| Fissure (b8, held) | netherite disc + ground gem + **netherite shovel** | | | **blocked**: the netherite upgrade template is bastion loot (NC) |

**18 of the 23 shelf TMs are craftable, and every one of them breaks the income gate's price:** the craft's cash
($152-$1,612, Skill Swap ~$3,000) is below leg 1's whole income ($4,033), against prices of $4,100-$202,900. By gem
timing, 16 of the 18 are craftable before their shelf line is affordable; only the two rock TMs (rock gems from tier
3, the line from leg 2) come after it, and they still cost 1/13 of the price. Other inputs can delay a craft (a Nether
trip, a rare Electirizer). One alpha battle KO pays 1.125 gems
below level 51 (all of its type if mono-typed), so **one alpha KO is about one TM**. The live lines today are the ten
at Fossick (b1-b3); the thirteen b4-b8 lines are `held` (ball_floor), so the gate they would enforce is already
bypassable before they open. The first-win TMs (`data/progression.json` `one_of`) lose their exclusivity the same
way.

### 3.4 Gem sources by type (earliest live alpha; tier = leg)

bug 1 (Metapod L7, Pallet Meadows, common); electric 1 (Minun L11, uncommon); fairy 1 (Fidough L6, uncommon); fire 1
(Growlithe L10, uncommon); flying 1 (Butterfree L10, common); grass and poison 1 (Oddish L9, uncommon); ground 1
(Diggersby L20, uncommon); normal and water 1 (Bibarel L15, uncommon); dragon 2 (Dragonair L30, uncommon); dark 3
(Morgrem L32); fighting 3 (Breloom L26); psychic 3 (Lunatone L25, common); rock 3 (Graveler L25, common); steel 3
(Duraludon L24, common); ice 4 (Jynx L30, common); ghost 6 (Drifblim L38, common). Every type has an alpha; the
earliest are often uncommon at a 0.26-0.46% share of their scope (an upper bound, DROPS_AUDIT 1), and the commonest
(13-16% of a scope) are later (DROPS_AUDIT 2.4, *relayed*). Whether a leg-1 team beats an L20-25 alpha under the leg's
level cap is not measured.

### 3.5 What still blocks the other 199

The commonest missing inputs: wind charge (23 TMs), TNT (12), bell (11), cobweb (10), nether star (9), end rod (7),
goat horn, end crystal, ghast tear and mace (6 each), sponge and sculk shrieker (5). They are End, trial-chamber,
structure or blacklisted-mob items, which alpha gems do not touch.

### 3.6 Limits of the model

It errs as the 2026-10-05 sweep's did: generous on vanilla (every non-crafted block's drop counts), blind to block
interactions (lava and powder snow buckets, enchanting, writing; the "614" row adds three), and it does not check
that a rostered species spawns in its painted biome. Crying obsidian, magma and lava are taken from the Nether, which
the sweep counts as renewable. **Not verified in game:** that an alpha KO in our world pays gems as tabled
(DROPS_AUDIT X5), and that a crafted TMCraft TM teaches. Recipe types the model does not parse (348 CobbleFurnies
`furni_crafting`, Sophisticated Storage's tier upgrades) were skipped; none makes a TM or a TM input.

---

## 4. For the owner

1. **Crafted TMs are live the day alphas pay gems.** Either accept them (the shelf then sells convenience, and its
   income-gate prices are a ceiling nobody pays), or cut the route at data level: override the alpha type tables
   (`cobblemon:alpha/types/<type>_rewards_tier1|2`) to drop the gem (DROPS_AUDIT 9 Q5), or empty the TMCraft
   recipes at their paths (needs a recipe kind in `tools/progression_pack.py upstream_neutralised`, which today
   cannot empty a recipe). Whichever is chosen, `DUNGEONS.md` 262-265's case for gems as the dungeon's spine needs
   rewriting, since its blank-disc gate does not exist.
2. **The income model omits banked drops** (item 9). If emerald stays both a Thievul drop and a $400 bank line, the
   income gate under-counts from tier 4.
3. **For `test-author`:** `ranch_money_report` should pick one entry per proc (item 6) and the pinned 0.226 (item 7)
   should become 0.106; the wild-death check of DROPS_AUDIT 8.3 is still unwritten (item 8).
