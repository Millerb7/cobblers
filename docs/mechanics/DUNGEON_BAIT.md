# Dungeon bait: the lure table

Status: DESIGN (trainer-balance-designer, 2026-10-12). Data: `data/dungeon_extras.json` `bait_room`. The engine
change that reads `tier` and rolls shiny and alpha is a separate unit (a builder working in parallel); nothing here
is seen in game.

## 1. The owner's brief (2026-10-12)

"The mon you attract should have a chance to be a shiny alpha, so it's a unique reward, not just a standard mon.
The pool should widen: map each type of berry to a mon, and the rarity of the berry equates to the rarity of the
mon." Decided: shiny and alpha are **two separate rolls**; a berry's tier is **how hard it is to get in this
campaign**, measured from our data; the lure stays at the band's **lower** level cap (20, 30, 40, 50, 60, and 100
at band 6, `data/dungeons.json` engine bands), so an alpha's reward is its look and size, not difficulty.

## 2. Tiers

Independent rolls: P(both) = shiny x alpha. The world's shiny rate is 1/2048 (`modpack/config/cobblemon/main.json:64`).

| Tier | Shiny | Alpha | Both | Baits | What puts a berry here |
|---|---|---|---|---|---|
| common | 1% (~20x world) | 5% | 0.05% | 8 | dropped by 18-27 spawned species; Oran and Pecha also in caches; poke bait |
| uncommon | 2% | 8% | 0.16% | 32 | dropped by fewer species (flavour berries 11-15; resist berries 11-25 plus alpha type rewards and vault loot); EV berries bought ($300, 2 badges); Sitrus and Lum from caches only; poke snack |
| rare | 4% | 12% | 0.48% | 17 | mutation only: no dropper, shop, cache or quest anywhere in `data/` |
| very_rare | 8% (~160x world) | 20% | 1.6% | 14 | the pinch and battle berries, mutation only; Custap is four steps deep |

Why these numbers: one bait a run (`tools/dungeon_extras.py`: one bait room a dungeon, one lure a run), so a common
shiny is about one in a hundred lures, a jackpot; a very-rare shiny about one in twelve, a fair return on a berry
farm that took many sessions. Alpha is three to five times as likely as shiny at every tier, so most players see
alphas and few see shinies.

"Live droppers" were counted by hand from `docs/research/notes/drops-1.8.0.json` `items.<berry>.droppers`, entries
whose last field (`live`) is true. That note is a research note ("do not generate content from this file"); the
counts set the tier boundaries and are not read by any tool. Rawst's Litleo entry rolls 0 and is not counted.

## 3. Sources

| Berries | Source in this campaign | Evidence |
|---|---|---|
| Oran, Pecha | drops (19, 27 live species) and caches: Oran r1_fern_glade, r4_packer, sea_life_beached_wreck; Pecha r1_west_hollow, r4_strayed_load | drops note; `data/rewards.json` |
| Cheri, Chesto, Rawst, Aspear, Persim | drops (25, 18, 25, 26, 25 live species) | drops note |
| Razz, Bluk, Nanab, Pinap, Wepear | drops only (14, 11, 11, 15, 15 live species) | drops note |
| the 18 type-resist berries | drops (11-25 live species each); a wild alpha's type reward, 25% of a 50% roll (`drops-1.8.0.json` `alpha_rewards`); dungeon vault tables in `data/dungeons.json` (all 18 appear) | drops note; `data/dungeon_greed.json` resist_berries |
| Pomeg, Kelpsy, Qualot, Hondew, Grepa, Tamato | sold at $300 from 2 badges | `data/traders.json:628-633` |
| Sitrus | no dropper; five caches (r3_world_tree_roots, r4_gate, r4_strayed_load, r5_shepherds_tin, survey_benchmark_store) | `data/rewards.json` |
| Lum | no dropper; one cache (r5_shepherds_tin) | `data/rewards.json:336` |
| Leppa and 16 cultivars | mutation only | absence in data/; OBTAINABILITY_VANILLA_COBBLEMON.md:156 (relayed: "70, all reachable", 154 mutation pairs) |
| Mago, Magost, Watmel, Custap | mutation steps 1-4: Pecha x Persim, x Nanab, x Tanga, x Chilan | `docs/research/DROPS_AUDIT.md:432`, read in the jar |
| 13 other pinch/battle berries | mutation only, chain not read | absence in data/ |
| Poke snack, poke bait | not in `data/`; ASSUMED crafted (1.8.0 recipes not read) | grep of `data/` |

No berry grows wild in this world (`docs/research/notes/reward-item-inventory.md:265`). A berry is what you plant
(`mint-seeds.md:110`, VERIFIED), so every berry is renewable once a player holds one: the tier prices the FIRST one.

## 4. The table

Stage per band follows the prize roster's rule (a stage offered when its natural evolution is at most 10 levels
above the band's lower cap); item, stone and friendship evolutions from band 3-4. Index = `dg.bait` (load-bearing:
the first six keep their places; see the data's `why`).

| # | Bait | Tier | Line (bands 1 to 6) | Link |
|---|---|---|---|---|
| 1 | oran | common | marill x2, azumarill x4 | blue, round (was Snorlax at 5-6: Munchlax is a prize) |
| 2 | pecha | common | clefairy x3, clefable x3 | pink, sweet (was Snubbull to Clefable, two lines) |
| 3 | razz | uncommon | ponyta x2, rapidash x4 | red (was Arcanine at 5-6: now Occa's) |
| 4 | sitrus | uncommon | chansey x3, blissey x3 | healing (unchanged) |
| 5 | poke snack | uncommon | eevee x6 | unchanged |
| 6 | poke bait | common | scyther x3, scizor x3 | unchanged |
| 7 | cheri | common | capsakid x2, scovillain x4 | spicy pepper |
| 8 | chesto | common | hoothoot, noctowl x5 | wakefulness |
| 9 | rawst | common | vulpix x2, ninetales x4 | burn |
| 10 | aspear | common | swinub, piloswine x2, mamoswine x3 | ice |
| 11 | persim | common | psyduck x2, golduck x4 | confusion |
| 12 | bluk | uncommon | murkrow x3, honchkrow x3 | blue-black; Honchkrow drops it |
| 13 | nanab | uncommon | aipom, ambipom x5 | banana; Aipom drops it |
| 14 | pinap | uncommon | exeggcute x2, exeggutor x4 | tropical |
| 15 | wepear | uncommon | bellsprout, weepinbell x2, victreebel x3 | the name |
| 16-33 | resist berries | uncommon | a line OF the type the berry resists: occa growlithe/arcanine; passho poliwag/poliwrath; wacan mareep/ampharos; rindo oddish/vileplume; yache sneasel/weavile; chople machop/machamp; kebia skorupi/drapion; shuca sandile/krookodile; coba swablu/altaria; payapa abra/alakazam; tanga venipede/scolipede; charti rhyhorn/rhyperior; kasib gastly/gengar; haban trapinch/flygon; colbur houndour/houndoom; babiri magnemite/magnezone; chilan teddiursa/ursaluna; roseli flabebe/florges | the type |
| 34-39 | EV berries | uncommon | pomeg skwovet/greedent (a berry hoarder); kelpsy sewaddle/leavanny (leaf wrap); qualot aron/aggron (defence); hondew lotad/ludicolo (dew); grepa clobbopus/grapploct (the name); tamato slowpoke/slowbro (speed down) | the stat |
| 40 | lum | uncommon | hatenna, hattrem x2, hatterene x3 | cures, heals |
| 41-57 | cultivars | rare | leppa togepi/togekiss; mago tinkatink/tinkaton; magost ralts/gardevoir; watmel stufful/bewear; figy charcadet/armarouge; wiki applin/flapple; aguav noibat/noivern; iapapa zorua/zoroark; cornn rookidee/corviknight; rabuta sinistea/polteageist (bitter tea); nomel toxel/toxtricity (sour); spelon pawniard/bisharp, kingambit at 6; pamtre duraludon/archaludon; durin ferroseed/ferrothorn (spiky); belue shinx/luxray; hopo rufflet/braviary; touga dunsparce/dudunsparce | colour, flavour, name |
| 58-71 | pinch/battle | very_rare | traditional starters' lines, base / middle / final x4: liechi treecko; ganlon piplup; salac chimchar; petaya bulbasaur; apicot mudkip; lansat charmander; starf fennekin; micle sobble; custap rowlet; enigma froakie; jaboca chespin; rowap litten; kee popplio; maranga sprigatito | Natural Gift type where one fits (ASSUMED, memory) |

Excluded on purpose: every family in `data/dungeon_prize_roster.json` rare pools (which is every pseudo-legendary
line, so the top tier uses the traditional starters, which the brief allows); the eight starters (Cosmog, Kubfu,
Type: Null, Poipole, Meltan, Larvesta, Smeargle, Misdreavus line); fossils (their own room); the ATMxMSD-only
species (`modpack/manifest/client-pack-atm-subset.json`); and pure swimmers (Horsea, Feebas, Lapras, Wailmer,
Shellder, Skrelp), because the lure walks a dry living room. Every species id was found as a species key in
`drops-1.8.0.json` (all 180 used), except Hydrapple, which is not there and is not used.

## 5. The greed clock (proposal, no code changed)

Today a lure catch is weighed by the room it is caught in, as any catch: `data/dungeon_greed.json` `catches`,
ambient 100/100/150/150/200/200 cp by band (1 point = 100 cp; rate = min(30, 10 + floor(cp/200)), so 200 cp is
+0.1x). The habitat's rare prize is 800 cp, its legendary 2000.

**Recommendation: a shiny or alpha lure should weigh more**, because the clock prices what a player takes and a
shiny alpha is the rarest non-legendary thing a run can hand over. Proposed, for the lured Pokemon only:

| Catch | cp | Reason |
|---|---|---|
| plain lure | the room's ambient value | unchanged |
| alpha | 2x ambient (200-400) | bigger, still an ordinary catch at the lower cap |
| shiny | 800 | the habitat's rare prize: a collector's prize |
| shiny alpha | 1000 | under the legendary's 2000; never ends a run alone |

A player who does not want the clock cost can leave it: declining is free. **Not buildable as the hook stands:**
`tools/dungeon_greed.py` reads only the room kind at the `pokemon_captured` callback ("the caught entity is already
gone"). Weighing a shiny or alpha needs the callback to read the caught Pokemon's shiny flag and aspects, or the
lure's keeper to mark its catch; neither is verified (open question 3).

## 6. Open questions

1. **Mutation depth (decides 30 tiers).** Read Cobblemon 1.8.0's `berries/*.json` mutation pairs: confirm every
   rare and very-rare berry is reachable and how deep. If a pinch berry is one step from two drops it belongs in
   rare; if a cultivar is unreachable it must leave the table.
2. **Ids not confirmed in the 1.8.0 jar** (in the 1.7.42 REI index only): apicot, belue, cornn, durin, enigma,
   figy, ganlon, iapapa, jaboca, kee, lansat, liechi, maranga, micle, nomel, pamtre, petaya, rabuta, rowap,
   salac, spelon, starf, touga, wiki. `tools/dungeon_extras.py` `problems()` checks each id against the jar.
   Touga's flavour is unknown to us, so its line (Dunsparce) has no link.
3. **Can the capture hook see shiny and alpha?** (section 5).
4. **Native alpha in 1.8.0:** does it change stats or IVs as well as scale? If so "look and size, not difficulty"
   needs the spawn to override it. And a wild alpha fainted in battle drops alpha rewards (`drops-1.8.0.json`
   `alpha_rewards`): defeating rather than catching an alpha lure pays candy. One lure a run keeps it small.
5. **Alpha size in a room 8 high:** the largest finals here (Dudunsparce, Ursaluna, Mamoswine, Rhyperior,
   Archaludon, Aggron) may clip at alpha scale.
6. **Poke snack and poke bait sources** are ASSUMED crafted; if neither can be made, they are dead entries.
7. **Band 6 lures spawn at 100** (the band's only cap).

Multiplayer: `dg.bait` is the player's own score and runs are solo (`members_max` 1), so each player rolls their
own lure; nothing is shared or claimed once per server.
