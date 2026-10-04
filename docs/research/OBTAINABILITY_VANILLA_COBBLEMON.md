# Obtainability sweep: vanilla 1.21.1, Cobblemon 1.8.0 and the Cobbleverse datapack

**Status: research, 2026-10-04. Nothing in the game was changed and nothing was seen in game.** The owner's
brief: list what is unobtainable in a pre-generated world, what it silently breaks, what we depend on, and how
each gets in. This document covers vanilla Minecraft 1.21.1, Cobblemon 1.8.0 and `COBBLEVERSE-DP-v31.zip`.
The other mods (Mega Showdown, TMCraft, LumyMon, CobbleDollars, backpacks, cuisine, Only Bottle Caps, ...) are
another agent's share; where one of their items blocks something here, this document names it and stops.

**Legend.** VERIFIED = read this session from a jar, a datapack or `data/`. ASSUMED = reasoned, not read or not
run. Nothing here is VERIFIED in a running game.

## 0. The premise, checked first

Four things in the brief, or in `docs/STATE.md`, disagree with the repository. They change the answer, so they
come before the table.

1. **"No ores spawn" is only half true.** WorldPainter's Resources layer was applied everywhere at export, and
   it places **vanilla** ores: coal, iron, copper, gold, redstone, lapis, diamond, emerald
   (`docs/world-building/REEXPORT.md:714`, `:839`). That is ASSUMED still true of the live world
   (`docs/mechanics/STONE_ECONOMY.md:389` says the same). What generates nowhere is every **modded** ore and
   crystal: evolution stones, Cobblemon's type-gem clusters, tumblestones, LumyMon relics. Vanilla iron and
   diamond are not the problem.
2. **The real hole is mobs, and it is bigger than STATE says.** STATE line 177 says MobsBeGone removes "every
   vanilla hostile". VERIFIED from `base-pack/cobbleverse/config/mobsbegone-blacklist.json`: it removes **81
   entities, including every passive animal.** Cow, sheep, chicken, pig, rabbit, bee, squid, horse, goat, fox,
   turtle, frog, armadillo, sniffer and iron golem are all on it. Only the villager, the wandering trader and the
   ender dragon are left. So **no vanilla mob drop exists at all**: no leather, wool, feathers, eggs, string,
   bones, gunpowder, ender pearls, blaze rods, ghast tears, slime, honeycomb, scutes or prismarine from a
   vanilla mob. Cobbleverse makes up for it in two ways. Pokemon `drops` cover most of these items, and
   CobbleDollars' `defaultShop` (`base-pack/cobbleverse/config/cobbledollars/default_shop.json`) sells bone, egg,
   ender pearl, feather, gunpowder, ink sac, leather, rabbit hide and slime ball. **Our merchants run filtered,
   authored shops**, so that second fix reaches no player. Whether a merchant with an empty shop falls back to
   `defaultShop` is NOT VERIFIED (STATE line 210).
3. **The Nether and the End generate normally** (`docs/world-building/WORLDGEN_FEATURES.md:6-8`). Their
   structures and chests are real. **The End cannot be reached**: there are no strongholds, so there is no
   portal frame. The Nether can be reached if a player builds a portal. That is ASSUMED possible: buckets are
   craftable, and obsidian comes from a water-and-lava cast or from diamonds. Nothing in `docs/vision`,
   `docs/mechanics` or `docs/decisions` says whether the Nether is part of the game. **It is the largest single
   hinge in this sweep** (section 3, row 5).
4. **STATE is stale on Shrew Station.** STATE line 208 says the feathers are "still issuing OFF".
   `data/research_station.json` has `economy.issuing: true` since `f6b2bb9` ("feathers issuing"), and
   `tests/test_research_station.py:115` was retargeted away from pinning it false. The Kubfu scroll errand
   (`edac917`) is live data too. STATE needs reconciling by its owner. This document does not edit it.

## 1. Method

The method is a reachability closure over everything the server loads. VERIFIED inputs:

- **Archives.** The vanilla 1.21.1 client jar
  (`%APPDATA%/ModrinthApp/meta/versions/1.21.1-0.19.5/1.21.1-0.19.5.jar`). Every mod jar in the Modrinth
  profile `Fabric 1.21.10`, which carries `Cobblemon-fabric-1.8.0+1.21.1.jar` and the server's mod set (the
  manifest's runtime folder `experiments/EXP-000-*/runtime/` does not exist in any checkout). The six datapacks
  `COBBLEVERSE-DP-v31`, `-Loot-DP-v11`, `-RCT-DP-v20`, `PokeCenterPCs-DP`, `No Hunger` and `No Ender Dragon`.
  From these: **11,875 recipes, 900 item tags, 8,273 loot tables, 1,025 species, 446 species additions, 154
  berry mutations and 335 native TM definitions**, with later archives overriding earlier ones at the same id.
- **Routes that exist in our world, by tier.** The table cites the earliest tier that reaches an item:

| Tier | Adds | Basis |
|---|---|---|
| **A** | Terrain and foliage (grass, dirt, stone, deepslate, gravel, sand, clay, 8 woods); Resources-layer ores, gated on pickaxe tier; lava; every **renewable** shop: the Mart clerks' three lines, the Exchange's ten stones, the 26 traders' BCA templates (only the `regional` ones, minus the withheld categories and herbs), and all 43 stalls and 14 counters in `data/markets.json`; the `data/mines.json` evolution-stone faces; crafting, smelting, stonecutting, smithing, Cobblemon campfire-pot and brewing recipes (each with its station); block loot; growth (saplings, crops, apricorn seeds, mint seeds, berry mutations, bone meal on grass, the cobblestone and obsidian casts); vanilla and Cobblemon fishing loot | ores and terrain ASSUMED (REEXPORT); the shops VERIFIED in data and NOT RUN in game |
| **B** | Drops of wild Pokemon that can spawn (non-legendary species in Cobblemon's and Cobbleverse's `spawn_pool_world` plus `data/spawns.json`), and **evolution-event drops** (Shelmet evolving with Karrablast in the party gives a Shell Helmet) | drops VERIFIED in species JSON. That a default-pool species spawns somewhere in our biomes is ASSUMED. Species we author are marked * below |
| **C** | The Nether: its blocks, plus fortress, bastion and ruined-portal chests (vanilla and Cobblemon injections). **The chests are finite** | ASSUMED reachable |
| **D** | The wandering trader. It is not on the blacklist, and its trades are hard-coded vanilla, read from vanilla knowledge rather than a file | ASSUMED it spawns (gamerule unread). It costs emeralds |
| **E** | One-off rewards: `data/rewards.json` caches, `data/quests.json`, the leaders' first-win items (`progression.json`) | VERIFIED in data. **Not renewable** |
| **F** | Unverified or random: the loot of natural rctmod trainers (`rctmod:generic/*`, spawning with a trainer card per `rctmod-server.toml`), Cobblemon alpha rewards, Shrew Station's economy | ASSUMED that ambient RCT trainers spawn and drop loot. The alpha trigger was not found in the jar |

**Pasture Loot is installed** (`pastureLoot-1.0.5`, config `base-pack/cobbleverse/config/PastureLoot.json`): a
pastured Pokemon has a 15% chance a minute to drop from its own drop table, with 34 items blacklisted, mostly
meat and wool. **So every tier-B item becomes a renewable farm once a player owns one of the species.** That is
the most important softening in this document. It is ASSUMED to work as configured.

**Counts.** These leave out model, cosmetic and technical ids, so they count real items. Of 832 Cobblemon items:
238 at A, 161 at B, 94 at C, 1 at D, 6 at E, 166 at F only, and **166 never**. Most of the 166 are worldgen
blocks with no item purpose: gem buds and clusters, ore blocks, saccharine wood, and seasoning variants of
food. Of 1,629 vanilla-namespace items: 707 at A, 95 at B, 106 at C, 30 at D, 31 at F, and 660 never. That 660
is mostly model frames, trims and interaction-only blocks the model cannot see (section 5). About 60 of them
matter, and they are in the table.

## 2. What it silently breaks: the top five

1. **Type gems: TMs of both kinds are almost entirely unreachable.** 294 of Cobblemon 1.8's 335 native TM
   recipes need at least one type gem. So do **all 483** of the TMCraft recipes that the **Cobbleverse
   datapack itself** ships, where `normal_gem` alone is in 116. Gems come only from gem clusters, which are
   worldgen. The only other sources are finite Nether bastion chests (C) and unverified trainer or alpha loot (F).
   No stall, counter or Pokemon drop gives one. This makes a crafted TM economy impossible.
2. **Fossils: the Resurrection Machine is dead.** 14 of 15 fossil items have no source but natural trainer loot
   (F). The 15th is one Old Amber in one reward cache (E). The Fossil Analyzer needs amethyst (B), and the
   Restoration Tank needs a Revive (B). Wild fossil Pokemon exist only as ultra-rare spawns in `#cobblemon:is_lush`
   (VERIFIED in the pools). Whether our world has a lush-caves biome is NOT VERIFIED. Our roster authors only
   Aerodactyl and Bastiodon.
3. **Mints: natures cannot be changed.** All 33 mint items have no source but F: 6 leaves, 6 seed types and 21
   mints. Mint plants are worldgen-only. The six Power items also need a white mint leaf.
4. **The brewing stand is unreachable.** It needs a blaze rod, and no Pokemon drops one. That leaves 6
   Cobblemon outputs with no other recipe: **PP Up, PP Max, Max Ether, Max Elixir, Ability Capsule and Throat
   Spray**. The six vitamins and Max Potion and Full Restore are also brewing-only, but the counters sell them.
5. **Quartz and the Link Cable belong to the Nether.** The Link Cable needs quartz and an ender pearl, which
   only Pokemon drop. Quartz has no Pokemon drop. Without the Nether, the 30 trade evolutions (18 of them in our
   roster) need a real player-to-player trade, and the Shelmet-to-Accelgor-to-Shell-Helmet-to-Escavalier chain
   needs one too. Player trades work in a co-op group (ASSUMED), so this costs solo players the most.

**Evolution items (60 checked): 36 at A, 16 at B, 5 at C, 2 at E (Kubfu's scrolls), 1 at F.** Not one is fully
unreachable now that evolution-event drops are counted. **Evolution stones: all ten are at A** through the
`data/mines.json` faces and the Exchange. This document does not reopen that work (STONE_ECONOMY.md).

## 3. The prioritised table

Priority runs P0 to P3. **P0** means a system or progression chain is dead without the item. **P1** means a
player-facing feature is dead or depends on one-off or RNG loot. **P2** means one evolution, or one
convenience, is lost. **P3** is cosmetic.

| # | P | Item(s) | What needs it | Why unreachable | Best route today | Proposed route | Cost and consequence |
|---|---|---|---|---|---|---|---|
| 1 | P0 | **18 type gems** (`cobblemon:*_gem`) | 294/335 native TM recipes; all 483 of the DP's TMCraft recipes; Metal Coat recipe (steel gem) | Gem clusters and the deepslate crystal core are worldgen (`worldgen/placed_feature/type_gems.json`) | C: bastion chests (finite). F: `rctmod:generic/uncommon/battle`, `cobblemon:alpha/types/*` | **A gem counter at the Mining Town Exchange or the Cinderlee core shed**, gated by badge, priced per gem as a TM's cost. Or a hand-placed gem grotto (gem blocks and a crystal core) as a cache. Whether the core regrows buds is NOT VERIFIED | Data plus pricing. **An owner decision**: it sets the price of every TM in the game. Cutting it means TMs exist only as rewards |
| 2 | P0 | **14 fossils** (helix, dome, old amber is E, root, claw, skull, armor, cover, plume, jaw, sail, 4 fossilized) | The Resurrection Machine; every fossil family not caught wild | Fossil sites are worldgen suspicious blocks (`cobblemon:fossils/*` tables VERIFIED) | F only | **Fossil faces in the `mines.json` pattern**: placed `suspicious_gravel` and `suspicious_sand` naming `cobblemon:fossils/rare/<fossil>` (archaeology itself works with placed blocks: ASSUMED). The Mining Town and the relic underground fit. Or an archivist errand at Shrew Station | A generator change (mines.py already restores faces). Or cut, and name the consequence: no fossil Pokemon except what spawns wild in lush caves |
| 3 | P0 | **Mint leaves and seeds** (6 colours), hence **21 mints** and the **6 Power items** | Natures; Power items for EV training and breeding | Mint plants are worldgen-only (`WORLDGEN_FEATURES.md:43`) | F only | **Sell mint *seeds*** at a herbalist (Stoneford, Greenhollow and Tilpey have one). Seeds are renewable: plant, grow, harvest leaves, craft mints. One counter line per colour, gated | Data: six counter lines. The owner chooses the gate (natures are a power rung) |
| 4 | P1 | **Brewing stand** (blaze rod) | PP Up, PP Max, Max Ether, Max Elixir, Ability Capsule, Throat Spray (brewing-only); vanilla potions (No Hunger makes food moot, not potions) | Blazes are blacklisted, and no Pokemon drops a blaze rod (VERIFIED) | F only | A **brewing stand on a counter** (the Fenhide apothecary and Tilpey physic garden themes fit), or blaze rods as a Craters line | Data: one line. Otherwise PP Up and PP Max are cut, and the bastion's finite Ability Capsules are all there is |
| 5 | P1 | **The Nether as a whole**: quartz, glowstone, nether wart, magma, ancient debris, bastion chests | Link Cable, teacups, redstone lamp (Upgrade), magma (Magmarizer recipe), netherite; also the finite chest loot: gems, Exp Candies, Rare Candy, Ability Capsule and Patch, Destiny Knot, Power items | Not a supply gap: **a design decision nobody has made** | C (ASSUMED portal-buildable) | **Decide whether the Nether is in the game.** If yes, nothing to build. If no, quartz and glowstone need counter lines, and the bastion-only items (row 7) are cut | A decision. The Ruinous four "stay Nether-generated" (STATE line 204) implies yes |
| 6 | P1 | **Link Cable** | Solo trade evolutions (30 species; ours: Boldore, Dusclops, Feebas, Graveler, Haunter, Karrablast, Machoke, Magmar, Onix, Phantump, Poliwhirl, Porygon, Pumpkaboo, Rhydon, Scyther, Seadra, Shelmet, Slowpoke); Shelmet to Accelgor | Recipe needs quartz (Nether) and an ender pearl (Pokemon drops only; rostered droppers: Spoink*, Grumpig*, Gallade*, Metagross*, Gothita*, Sigilyph*, Rabsca*) | C | Follows row 5. Or one Link Cable line on a late counter | Without it, a co-op trade still works (ASSUMED). A solo player loses 18 rostered evolutions |
| 7 | P1 | **Exp Candies (5), Rare Candy, Ability Capsule and Patch, Destiny Knot, PP Up and Max** | Levelling against the cap; abilities; Cobbreeding IV inheritance (Destiny Knot) | No recipe: Destiny Knot needs a ghast tear, the candies have none. Bastion chests only (finite), plus F | C (finite) | **Cut deliberately** for the candies (the level cap makes them a bypass; see EXP-049's open Rare Candy question). Put the **Destiny Knot** on a breeder's counter if breeding matters | A decision. Cutting is free and coherent with the cap |
| 8 | P1 | **Amethyst shard** | Blank TM, TM Machine (tinted glass), Fossil Analyzer, Exp. Share, Sachet | Geodes are worldgen. A placed `amethyst_cluster` (town dressing) is one-time | B: Sableye*, Glimmet*, Glimmora*; renewable through Pasture Loot | Leave it, since a pastured Sableye farms it. Or a core-shed line | Free if Pasture Loot works (ASSUMED). The first shard waits on a Sableye or Glimmet win |
| 9 | P2 | **Dubious Disc** | Porygon2 to Porygon-Z | Recipe needs **sculk** (deep-dark worldgen, unreachable). The only other source is a Porygon-Z drop (25%): circular unless Porygon-Z spawns wild (default pools, ASSUMED) | B (circular) | A reward cache, or a late counter line | Data: one line. Otherwise Porygon-Z is cut (Porygon* is rostered) |
| 10 | P2 | **Upgrade** | Porygon to Porygon2 | Recipe: redstone lamp (glowstone: Nether) plus blank TM (amethyst). Drop: Porygon2 25% (circular) | C via the recipe | Follows row 5 | None if the Nether is in |
| 11 | P2 | **Sachet** | Spritzee to Aromatisse | Recipe needs **pink petals** (cherry-grove flora; worldgen only, no trader) plus amethyst | C (Nether fortress chest, finite) | One cache, or sell pink petals at the Greenhollow seed cart (it already sells cherry saplings, but **bone meal on a cherry sapling does not make petals**) | Spritzee is not in our roster: low |
| 12 | P2 | **Masterpiece Teacup**; **Chipped Pot** | Artisan Poltchageist* to Sinistcha; Antique Sinistea* to Polteageist | Masterpiece: no recipe from obtainable inputs (it needs itself plus quartz); ruins loot is worldgen. Chipped: same shape | Masterpiece F; Chipped C (fortress chest) | One cache each, if the owner wants the rare forms | The common forms are reachable: the Unremarkable Teacup at C, the Cracked Pot at A |
| 13 | P2 | **Kubfu's scrolls** | Kubfu to Urshifu | Archaeology loot (desert pyramid, warm ocean ruin) is worldgen | E: one of the two, once, at gym 5 (`data/rewards.json` `station_director`, `one_of`) | As designed. The other form needs a second scroll | Decided (STATE line 322). Named here only because it is one-off |
| 14 | P2 | **Rostered evolution items reachable only as Pokemon drops (B)** | Metal Coat (Onix*, Scyther*), Protector (Rhydon*), Razor Claw and Fang (Sneasel*, Gligar*), Reaper Cloth (Dusclops*), Magmarizer (Magmar*), Black Augurite (Scyther*), Peat Block (Ursaring*), Auspicious and Malicious Armor (Charcadet*), the three apples (Applin*), Oval Stone | Recipes need other dead inputs (Metal Coat: steel gem and honeycomb; Protector: armadillo scute; Magmarizer: magma, a Nether block) | B at 2.5-10% per KO, then a Pasture Loot farm. Every family listed has a dropper in `data/spawns.json` (VERIFIED), except the Oval Stone's Happiny line: Chansey* drops it | Nothing needed. Optionally, Protector, Metal Coat and Razor Claw on gym 5-6 counters to cut the grind | Free. The cost is grind, not breakage |
| 15 | P2 | **Wind charge, breeze rod, mace, cobweb** | 4 native TMs and 23 TMCraft recipes (wind charge); 6 TMCraft (mace); 6 TMCraft (cobweb) | Breezes and trial chambers are gone; cobwebs come from mineshafts and spiders | Never | Cut, named: those TMs need another route (row 1) | Folded into the TM decision |
| 16 | P2 | **Gunpowder** | TNT, fireworks; some TMs | Creepers are blacklisted; only Voltorb and Electrode drop it, and neither is in our roster (default pools only) | B (ASSUMED) | Cut, or put Voltorb on a route | Low |
| 17 | P3 | **The End**: elytra, shulker shells and boxes, end stone, chorus, dragon's breath | Flight; storage | No stronghold, so no portal | Never (the shulker shell is F) | Cut. Waystones and mounts cover travel | Decided by geography. Named |
| 18 | P3 | **Sculk, sponge, coral (block items only from the trader), sniffer plants, pitcher, torchflower, pink petals, bee nest, frogspawn, spore blossom, powder snow** | Decoration; the Dubious Disc (sculk) | Worldgen or blacklisted mobs | Never, or D (coral blocks, sugar cane, moss, red sand, dripstone) | Cut | Cosmetic |
| 19 | P3 | **Hearty grains**, **saccharine tree** (wood set) | Cooking; decoration. Applin apples come from Applin drops instead | Worldgen plants | Never | Cut | Cosmetic |
| 20 | P3 | **Cherish Ball** | Event Pokemon | Never obtainable in Cobblemon by design | Never | None | None |
| 21 | P3 | **Bottle caps** | Hyper Training | Not in vanilla or Cobblemon. Only Bottle Caps is the other agent's: its recipes are F, and the Holdfast counter sells `bottle_cap_gold` | A for gold (counter) | Other agent | n/a |

**Evolutions that cannot fire for a reason other than an item** (VERIFIED in species JSON; the world's biomes
were not checked):

- **Vivillon's Modern pattern** needs `structureCondition: #minecraft:village`. No village exists, so it never
  fires. **18 of Spewpa's other 22 evolutions carry `structureAnticondition: #minecraft:village`**, which always
  passes.
- **35 other evolution entries are biome-conditioned**, counting forms: the Hisuian, Alolan and Galarian
  branches of Bergmite, Cubone, Dartrix, Dewott, Exeggcute, Goomy, Koffing, Mime Jr., Petilil, Pikachu, Quilava
  and Rufflet; Goodra; Runerigus; and Grotle's tree-form Torterra evolutions, which also need a held sapling.
  The mangrove propagule is reachable by bone-mealing mangrove leaves. Whether each condition's biome tag holds
  any biome we painted is the next check. It needs the painted biome list, which was not read.

## 4. What we depend on: status

| System | Status | Note |
|---|---|---|
| Healing Machine, PC, Pasture, Monitor, Display Case, Pokedex, campfire pots | **A** (craftable) | Crafted from iron, gold, redstone, glass and copper: Resources-layer ores (ASSUMED) or stall lines |
| Fossil Analyzer, Restoration Tank, TM Machine, Blank TM | **B** | Amethyst (Sableye* or Glimmet* drops) and a Revive (revival herb from Petilil*, Sewaddle* or Leavanny* drops) |
| Poke Balls | **29 of 48 at A** (apricorns grow from the mulch trader's seeds; the Marts and counters sell the rest); the **15 Ancient balls at C** (Nether chests; tumblestones are worldgen); Beast Ball F; Cherish never | Hisui-style balls are effectively cut unless sold |
| Held items | 126: **30 A, 65 B, 31 C**, none never | The C group (Destiny Knot, Power items and others) is finite bastion loot (row 7) |
| Medicine | 21: **11 A, 4 B, 6 C** | Max Ether, Max Elixir and Superb Remedy need the brewing stand (row 4) |
| Berries | 70: **all reachable**. 9 are sold, and **mutations reach Sitrus, Leppa and Lum at A**; 25 more come only as Pokemon drops and their mutations | Mutation pairs from Cobblemon's `berries/*.json` (154) |
| Evolution stones | **A**: `data/mines.json` faces and the Exchange | STONE_ECONOMY.md |
| Kubfu scrolls | **E**, one of two, once | Row 13 |
| Key Stone, Mega stones, Z-Ring, Dynamax Band, LumyMon feathers and crown | not this share | The Mega Bracelet is on the Fenhide counter (`data/markets.json`) |
| Quest inputs (`data/quests.json` conditions and offerings) | **All A**: bucket, compass, glass bottle, paper, water potion, water bucket, berries | No quest asks for an unreachable item |

## 5. What the model does not see

These are ASSUMED gaps, and they bias only toward false "never" results:

- Block interactions: stripping logs, concrete powder plus water, copper oxidation, shears on a pumpkin, bone
  meal on dripleaf and mushrooms.
- Cobblemon cooking with seasonings: ponigiri variants, Poke Puffs, Poke Cake.
- Tool tiers below the pickaxe, Fortune and Silk Touch.
- Spawn conditions beyond the species list: biome, structure, sky light and the lush caves.

A "never" in the vanilla count is therefore often an interaction. Every row in section 3 was checked by hand
against its recipes and loot tables (`recipe ... missing:` lists), so the table does not carry that bias.

## 6. What was built

**Nothing.** Every gap that matters is an item that **cannot be gathered**. `data/markets.json`
`stalls_basis.budget` says a stall line must be "something a player can also gather or craft... a convenience
bought with spare money, never a gate". So adding gems, mint seeds, fossils, a brewing stand or a Link Cable to
a stall would break the stalls' own contract. Each one is a **counter** line (gated, priced, counted by the
budget curve) or a cache, and that makes it a pricing and progression decision for the owner, not an obvious
fix. The decisions, in order of what breaks without them:

1. Is the Nether in the game? (row 5)
2. Price the gems, or cut crafted TMs (row 1).
3. Fossil faces or a fossil cut (row 2).
4. Mint seeds on a gated counter (row 3).
5. A brewing stand on a counter (row 4).
6. Cut the candies (row 7).

The closure scripts lived in a scratch directory and are not committed. To reproduce, re-read the archives
listed in section 1 and close over the tiers in its table.
