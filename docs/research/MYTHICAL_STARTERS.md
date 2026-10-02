# Mythical starters: Cosmog, Kubfu, Type: Null, Poipole, Meltan

**Asked by:** the owner, 2026-10-02 ("Starter candidates decided in principle ... Report before changing anything").
**Answered for:** Cobblemon 1.8.0+1.21.1 (jar `Cobblemon-fabric-1.8.0+1.21.1.jar`, found by `tools/battle_sim.py`
`find_jar()`), Mega Showdown `1.0.2+1.8+1.21.1` (the overlay's build, `modpack/manifest/overlay.json:215`, read from a
local client copy), COBBLEVERSE datapack `COBBLEVERSE-DP-v31.zip` and `COBBLEVERSE-Loot-DP-v11.zip` (the local
Cobbleverse copy; the server takes a patched DP-v31, `tools/install_check.py:28`). Source code at GitLab tag `1.8.0`
(`https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/<path>`, written
`src:<path>` below; read through a fetch-and-summarise step, identifiers and code asked for verbatim).
**Nothing was built, changed or run in Minecraft.** No server, world or runtime was touched.

Labels: **VERIFIED** (jar entry, pack entry, source, or repo `path:line`), **MEASURED** (a scratch run of the repo's
own `tools/battle_sim.py` harness, offline, this session; the repo was not changed), **ASSUMED** (with the experiment
that would settle it), **RELAYED** (a figure from the brief, checked or not as stated).

Prior work this builds on, not repeated: `docs/research/STARTER_OPTIONS.md` and
`docs/research/notes/starter-stat-mechanics.md` (the "dormant form" mechanism, verified in source for one mythical,
Mew) and its costing in `docs/mechanics/STARTER_DESIGN_COMPARISON.md:81-93` (about 3 sessions for one mythical).

---

## 1. Short answer

1. **The premise "all five evolve natively from a weak base" is wrong in three places.**
   - **Meltan does not evolve in Cobblemon 1.8.0 at all.** The jar's `meltan.json` has `"evolutions": []` and
     `melmetal.json` has no `preEvolution`. What evolves it on our server is a **COBBLEVERSE** addition, not Cobblemon:
     `level_up`, holding `minecraft:anvil`, **level 70**. Our caps stop at 60, so **Meltan can never evolve** in the
     campaign as the pack stands.
   - **Type: Null (534) and Poipole (420) are not weak bases.** 534 is a fully evolved starter's total: Charizard is
     534 (`docs/research/notes/starter-stat-mechanics.md` §4).
   - **Cosmog cannot fight.** Cosmog's whole learnset is Splash and Teleport, with no TM entries; Cosmoem adds only
     Cosmic Power. Natively it evolves at 43 and 53, so a Cosmog starter would deal no damage until leg 6.
2. **The relayed figures are right:** Cosmog 43 / Cosmoem 53, Cosmog 200, Solgaleo 680, Type: Null 534, Silvally 570.
   Cosmoem's 53 also needs day (Solgaleo) or night (Lunala).
3. **Poipole already knows Dragon Pulse at level 1** in 1.8.0, and Cobblemon lets a player swap in any level-up move at
   or below the current level. So a starter Poipole can evolve the moment the player chooses.
4. **Kubfu's towers do not exist here.** The branch depends on an item: use a Scroll of Darkness or a Scroll of Waters
   on it. No structure gates it.
5. **A learnset CAN be edited from a datapack**, three ways, all VERIFIED in source and none ever loaded by us:
   - a full species file at the jar's own path;
   - `species_additions` with a `moves` key, which **replaces** the whole list;
   - a form's own `moves`. This one has live precedent in the pack: Cobbleverse's mega forms and Mega Showdown's
     cosplay Pikachu forms.
6. **An evolution method can be REPLACED only by a full species file, or per Pokémon by a form.** It cannot be removed
   with `species_additions`, because `evolutions` there **appends**. For Meltan, the Cobbleverse addition re-appends
   its level-70 rule on top of any species file, so the addition file has to be shadowed too.
7. **Gym 3 is not where a normal starter reaches its second stage.** All 27 configured starters reach their middle
   stage at levels 14 to 18, which is leg 1, before gym 1. They reach their final stage at 30 to 36: one at 30, three
   at 32, three at 34, three at 35, seventeen at 36. That is legs 3 to 5. MEASURED from the jar.
8. **Equalising stats does not equalise strength.** The measured spread with every line normalised to the median
   starter BST at each cap is 10 to 32 wins of 35. With native stats and the fixes below it is about 12 to 26, against
   today's 9 to 27. Movepool and typing dominate at these caps. Only **Cosmog** is out of reach without new stats: it
   scores 3 to 8 of 35, and 5 to 8 even with a borrowed learnset.
9. **Recommendation:** option **c, a hybrid.**
   - Replace the native evolution methods species-wide with **level 31 and level 46**. Each is one level above a leg's
     cap, so it arrives with badges 3 and 6 without a flag.
   - Fix Poipole's learnset so Dragon Pulse is learnt at 31.
   - Give **only the Cosmog line** new stats and a learnset.
   - Do not build five weak-form lines. Details and costs are in §8.
10. **Stress tests:** 108 is not divisible by 5, so `build_profiles` raises, and the "exactly 27" checks fail.
    - The arithmetic fix is small: 115 = 25/20/20/20/15/15, which keeps every archetype divisible by 5.
    - The real cost is the starter model. The simulators read species only from the jar and drop properties, so they
      would score a Splash-only Cosmog and a Meltan that never evolves.

---

## 2. The five lines in Cobblemon 1.8.0's own data (VERIFIED, jar entries `data/cobblemon/species/<gen>/<name>.json`)

| Species | Types | HP/Atk/Def/SpA/SpD/Spe | BST | Evolution (variant, requirements) | Base friendship | Catch rate | Labels |
|---|---|---|---|---|---|---|---|
| Cosmog | Psychic | 43/29/31/29/31/37 | **200** | `level_up` → Cosmoem, `level` **43** | 0 | 3 | legendary, restricted |
| Cosmoem | Psychic | 43/29/131/29/131/37 | 400 | `level_up` → Solgaleo: `level` **53** + `time_range` day; → Lunala: `level` 53 + `time_range` night | 0 | 3 | legendary, restricted |
| Solgaleo | Psychic/Steel | 137/137/107/113/89/97 | **680** | none | 0 | 3 | legendary, restricted |
| Lunala | Psychic/Ghost | 137/113/89/137/107/97 | 680 | none | 0 | 3 | legendary, restricted |
| Type: Null | Normal | 95/95/95/95/95/59 | **534** | `level_up` → Silvally, `friendship` **160** | 0 | 3 | legendary |
| Silvally | Normal (17 memory forms) | 95×6 | **570** | none | 0 | 3 | legendary |
| Kubfu | Fighting | 60/90/60/53/50/72 | 385 | `item_interact` → Urshifu `wushu_style=single_strike` with `cobblemon:scroll_of_darkness`; → `rapid_strike` with `cobblemon:scroll_of_waters`; `requirements: []` | 50 | 3 | legendary |
| Urshifu | Fighting/Dark (Rapid: Fighting/Water) | 100/130/100/63/60/97 | 550 | none | 50 | 3 | legendary |
| Poipole | Poison | 67/73/67/73/67/73 | 420 | `level_up` → Naganadel, `has_move` **dragonpulse** (drops a Shed Shell) | 0 | 45 | ultra_beast |
| Naganadel | Poison/Dragon | 73/73/73/127/73/121 | 540 | none | 0 | 45 | ultra_beast |
| Meltan | Steel | 46/65/65/55/35/34 | 300 | **none in the jar** | 0 | 3 | mythical |
| Melmetal | Steel | 135/143/143/80/65/34 | 600 | none; `preEvolution` absent | 0 | 3 | mythical |

**Learnsets that decide the design (VERIFIED, same files):**
- Cosmog: `1:splash`, `1:teleport`, and no TM, tutor or egg entries. Cosmoem: `1:cosmicpower`, `1:teleport`,
  `1:splash`, `tm:cosmicpower`. **Neither has a damaging move.**
- Poipole: `1:dragonpulse` among five level-1 moves, plus `tm:dragonpulse` and `tutor:dragonpulse`.
- Meltan: Thundershock and Harden at 1, Tail Whip 8, Headbutt 16, Thunder Wave 24, Acid Armor 32, Flash Cannon 40.
- Kubfu: a normal 4-level ladder up to Focus Punch at 52. Type: Null: Tackle up to Double-Edge at 55.

**Implemented and rendering.**
- VERIFIED: only Poipole and Naganadel are `implemented: true` in the bare jar, and they are the only ones with models
  in it (`assets/cobblemon/bedrock/pokemon/models/0803_poipole/`, `0804_naganadel/`).
- VERIFIED: the rest are switched on by additions that set `implemented: true`. Mega Showdown 1.0.2+1.8 ships
  additions for cosmog, cosmoem, solgaleo, lunala, typenull, silvally, urshifu, meltan and melmetal in
  `data/cobblemon/species_additions/`, and full species files for kubfu and melmetal. COBBLEVERSE-DP-v31 adds cosmog, cosmoem, solgaleo, lunala, kubfu, meltan,
  naganadel and urshifu.
- VERIFIED: model resolvers for the other ten exist in the Mega Showdown 1.8 jar (`assets/cobblemon/bedrock/pokemon/resolvers/`).
- ASSUMED: they render in our client, not as the substitute doll. Experiment X6.

**Wild and raid copies exist** (VERIFIED, COBBLEVERSE-DP-v31 `data/cobblemon/spawn_pool_world/`, all `ultra-rare`):

| Species | Level | Where |
|---|---|---|
| Cosmog | 28–42 | the End |
| Cosmoem | 44–52 | the End |
| Solgaleo, Lunala | 70 | — |
| Poipole | 40 | End towers |
| Naganadel | 48–62 | — |
| Meltan | 38–52 | near iron blocks, and beaches |
| Kubfu | 30–50 | cherry groves |
| Urshifu | 60–80 | — |

- VERIFIED: raids exist for Kubfu, Urshifu, Meltan, Melmetal, Solgaleo, Lunala and Naganadel
  (`data/cobblemonraiddens/raid/`).
- NOT CHECKED: whether our spawn suppression lets any of them spawn in our world. No file in `data/` names them except
  two notes that avoid iron blocks because of Meltan (`data/deep_city.json:32`, `data/relic_underground.json:114`).
- This matters for one reason: **a species-wide override changes these copies too.**

---

## 3. The four specific questions

### 3a. Type: Null's friendship threshold, and how friendship is gained here

**The threshold is 160** (VERIFIED, `typenull.json` evolution requirement `{"variant": "friendship", "amount": 160}`).
Its base friendship is 0, and the server cap is 255 (`modpack/config/cobblemon/main.json:4`, `maxPokemonFriendship`).

How Cobblemon 1.8.0 raises friendship (VERIFIED, source):

| Source | Amount | Where |
|---|---|---|
| Level-up from experience | +3 while friendship ≤ 99, +2 at ≤ 199, then 0 | `src:api/pokemon/friendship/FriendshipMutationCalculator.kt` `SWORD_AND_SHIELD_LEVEL_UP`, applied once per level gained in `Pokemon.addExperienceWithPlayer` |
| Time out of the ball | +1 every 120 s while sent out or on the shoulder, **only while friendship < 160** | `src:api/storage/party/PlayerPartyStore.kt` `onSecondPassed` |
| EV-lowering berries (Pomeg, Kelpsy, Qualot, Hondew, Grepa, Tamato) | +10 below 100, +5 below 200, else +1 | jar `data/cobblemon/mechanics/berries.json` `friendshipRaiseAmount`; tag `data/cobblemon/tags/item/berries/friendship.json` |
| Soothe Bell held | ×1.5 on every gain | `src:Cobblemon.kt` `FRIENDSHIP_UPDATED` handler, tag `held/is_friendship_booster` = `cobblemon:soothe_bell`; crafted from iron and wool (jar `data/cobblemon/recipe/soothe_bell.json`) |
| Cobble Cuisine foods (in the pack, `modpack/manifest/overlay.json:675`) | bean 1, Poképuff 6, malasada 12 | `base-pack/cobbleverse/config/cobblecuisine.json:17-19` (Cobbleverse's values; ours not checked) |

**What that means:**
- **Levelling alone** (from 0): 34 levels to pass 99, then 29 more at +2, so **63 levels**. A level-5 starter would
  reach 160 at about level 68, which is past every cap.
- **Time alone** reaches **exactly 160**, because the passive gain stops there: 160 × 120 s, about **5 h 20 min sent
  out**. It is less with the levels already gained.
- **Berries:** 10 to reach 100, then 12 more, so **22 berries**. With a Soothe Bell, 7 to reach 105, then 7 more.

Friendship is therefore **not a progression gate.** It is a chore the player can finish at level 5. To make Type: Null
evolve at a set moment, its method must be replaced (§5).

### 3b. What substitutes for Meltan's candy threshold

**Cobblemon substitutes nothing.**
- VERIFIED: Meltan has no evolution in the 1.8.0 jar.
- VERIFIED, the live substitute: COBBLEVERSE-DP-v31 `data/cobblemon/species_additions/meltan.json` appends
  `meltan_melmetal`: `level_up`, `held_item` `minecraft:anvil`, `level` `minLevel` **70**. That pack ships to the
  server (`tools/install_check.py:28`).
- **Under caps of 20 to 60, a Meltan never reaches 70.** It would need a postgame cap above 69.
- VERIFIED, and not live: a Cobbleverse "credits only" pack (`z DO NOT ENABLE z [ATM x MSD - Credits Only].zip`)
  carries a different rule, `properties` `meltan meltan_iron=400` with a `meltan_iron` species feature. The pack is
  marked not to enable.

### 3c. Kubfu's Tower of Darkness and Tower of Waters

**There are no towers. The branch depends on an item.**
- VERIFIED: `kubfu.json` evolves by `item_interact` with `requiredContext` `cobblemon:scroll_of_darkness` (to Single
  Strike) or `cobblemon:scroll_of_waters` (to Rapid Strike), with no requirements. The scrolls are jar items
  (`assets/cobblemon/models/item/scroll_of_*.json`, tag `evolution_items`).
- VERIFIED: Mega Showdown 1.8 ships its own `data/cobblemon/species/generation8/kubfu.json` at the same path. It has
  the same evolutions with `consumeHeldItem: true`. Which of the two mod copies wins is not known; it is load order.
- VERIFIED: no tower structure or `tower_of` entry exists in the jar, in Mega Showdown, or in any Cobbleverse datapack
  scanned.

**Where scrolls come from in the live packs** (VERIFIED):
- archaeology loot in desert pyramids (Darkness) and warm ocean ruins (Waters), in COBBLEVERSE-Loot-DP-v11;
- the Urshifu raid boss loot table;
- no crafting recipe. The only scroll recipes are in the not-enabled credits pack. TMCraft's Wicked Blow recipe
  *consumes* a Scroll of Darkness.

ASSUMED: a pre-exported WorldPainter world has no generated desert pyramids or ocean ruins inside its border
(`CLAUDE.md`, "World-critical"). If so, the scrolls must be handed out.

### 3d. Poipole and Dragon Pulse today

- VERIFIED: Dragon Pulse is `1:dragonpulse`.
- VERIFIED, `src:pokemon/Pokemon.kt` `allAccessibleMoves`: the summary-screen swap accepts any move in
  `form.moves.getLevelUpMovesUpTo(level) + benchedMoves + form.moves.evolutionMoves`, and
  `src:net/serverhandling/storage/BenchMoveHandler.kt` rejects anything else. So Dragon Pulse can be slotted in at
  level 5.
- VERIFIED, `src:pokemon/requirements/MoveSetRequirement.kt`: `has_move` checks `pokemon.moveSet.getMoves()`, the
  active moves.
- VERIFIED, `PlayerPartyStore.onSecondPassed`: passive evolutions are attempted **every second** for party Pokémon.
- So a starter Poipole is offered Naganadel within seconds of the player choosing to do it. The learnset edit in §4 is
  mandatory for the owner's plan, not optional.

---

## 4. The learnset question

### 4a. Can a species' learnset be edited from a datapack?

**Yes, by three routes (VERIFIED in source; none loaded or run by us):**

| Route | Scope | Evidence | Precedent |
|---|---|---|---|
| A full species file at the jar's path, e.g. `data/cobblemon/species/generation7/poipole.json` | every Poipole | `src:api/data/JsonDataRegistry.kt` keys by namespace + file name (notes §1); a higher pack's file at the same path wins | **Mega Showdown 1.8 does exactly this** for `generation8/kubfu.json` and `generation7b/melmetal.json` (VERIFIED, jar entries) |
| `species_additions` with a `moves` key | every Poipole | `src:pokemon/SpeciesAdditions.kt`: every mutable `Species` property is admissible. It makes private setters accessible (`isAccessible = true`). `forms` and `evolutions` append; **everything else, `moves` included, replaces**. `src:pokemon/Species.kt`: `var moves = Learnset() private set` | none found: no species-level `moves` addition in the pack |
| A form's own `moves`, the form chosen by an aspect | one Pokémon | `FormData.moves` falls back to the species only when unset (notes §2); `allAccessibleMoves` reads `form.moves` | **live in the pack**: COBBLEVERSE-DP-v31's mega forms (`dialga`, `groudon`, `lugia`, `mewtwo`, `palkia` additions) and Mega Showdown's cosplay Pikachu forms carry their own `moves` (VERIFIED, entry contents) |

"Nobody has tested a learnset edit" stands. Experiment **X1** settles it.

**Two traps (VERIFIED from the data):**
1. **A replacement is the whole list.** Every `tm:`, `tutor:`, `egg:` and level entry to be kept must be written
   again. Leaving `tm:dragonpulse` in would presumably let a Dragon Pulse TM evolve Poipole early.
   - VERIFIED: Cobblemon 1.8's native TM classes `api/tms/TMMoveManager` and `item/interactive/TechnicalMachineItem`
     reference `allAccessibleMoves` (class references).
   - **ASSUMED:** they, and TMCraft (also in the pack), decide compatibility from the `tm:` entries. That code was not
     read. X1 checks it.
2. **A copied species file is Cobblemon's data.** VERIFIED: the 1.8.0 source carries the Mozilla Public License 2.0
   header (`src:api/pokemon/friendship/FriendshipMutationCalculator.kt`). ASSUMED: the bundled JSON is under the same
   licence.
   - CLAUDE.md commits only MIT-style sources, so a modified copy must not be committed.
   - The committable form is a **patch spec in `data/`** plus a generator that reads the jar and writes the full file
     into `build/`. This is the "anything in build/ is reproducible from data/ and tools/" rule.
   - `species_additions` and form files are our own text and can be committed.

### 4b. What level lands "around gym 3"?

**Caps (RELAYED from STATE `docs/STATE.md:549,552`; checked against the harness).**
- `battle_sim.level_caps` plus the gym aces in `data/trainers.json` give caps 20/25/30/35/40/45/50/55 for gyms 1 to 8
  (MEASURED this session).
- rctmod stops experience **at** the cap, and the cap rises only when the next required trainer changes
  (`docs/research/notes/level-cap-catch-block.md:3-4,109-113`, rctmod v0.19.0-beta source).

So there are two exact choices for each point:

| Level | When the player can reach it | Meaning |
|---|---|---|
| **30** | at the leg-3 cap, before gym 3 | evolves *for* the gym 3 fight |
| **31** | only after badge 3 (the cap becomes 35) | evolves *as the reward* for badge 3, gated by the cap itself, no flag |
| 45 / **46** | the same at gym 6 | |

**Recommendation: 31 and 46.** They are the only levels that tie the moment to the badge with no flag and no
advancement requirement, which is what the owner asked for ("gates itself without a flag").

Two conditions on that:
- **ASSUMED:** Rare Candy also respects the RCT cap. If it does not, a player can skip the gate with candies.
  Experiment X3.
- The cap holds only while the next required trainer is the gym leader. A route trainer of a higher level in the
  series would move it (rctmod `LevelUtils.levelCap`, the minimum over next trainers).

If a hard guarantee is wanted anyway, add an `advancement` requirement on `cobblers:flag/gym3_cleared`. The
`advancement` variant is VERIFIED in 1.8.0 (notes §3a), and the passive check runs every second, so it fires as soon as
the badge lands.

**For Poipole:** put Dragon Pulse at `31:dragonpulse` and drop `tm:dragonpulse` and `tutor:dragonpulse`. The native
`has_move` evolution then gates itself. One caveat, VERIFIED in source: on level-up a new move is added only if the
moveset has a free slot. Otherwise the player has to swap it in from the summary. That is a UI step, not a gate, so
Dragon Pulse "learnt at 31" means "available at 31". X1 records what the player sees.

**"Something similar for Meltan":** no move gate exists to edit, because Meltan has no evolution in Cobblemon (§3b).
- Meltan needs an evolution written for it. That is a replacement (§5), not a learnset change.
- The simplest replacement is a plain `level` 31 or 46 requirement, as for the others.
- A `has_move` gate on a move moved to 31 (for example Flash Cannon, natively 40) would work the same way as Poipole's,
  but it adds a step for no gain.

### 4c. If learnset edits did not work: the alternatives

All of these exist in 1.8.0 or in the pack. None replaces the edit for Poipole, because the level-1 entry is the
problem.
- **A TM:** Cobblemon native or TMCraft. It does not remove the level-1 Dragon Pulse.
- **An item or quest gate:** an `item_interact` evolution needing an item the player is given. That is a replacement,
  §5.
- **A command from a function** at the badge: `pokemonedit <slot> <properties>`, or MoLang `q.pokemon.force_evolve`
  on `advancement_earned` (notes §3b).

If learnset edits fail X1, **the evolution replacement in §5 makes them unnecessary.** Replace Poipole's `has_move`
with a `level` 31 requirement, and Dragon Pulse can stay at level 1.

---

## 5. Question 1: identical evolution points

### 5a. Can an evolution method be overridden at all?

| Route | Can it REMOVE the native method? | Scope | Evidence |
|---|---|---|---|
| `species_additions` `evolutions` | **No.** It appends, so the native method stays alongside ours. | species | `SpeciesAdditions.reload`: `appendKeywordsCollection = listOf("forms", "evolutions")` (notes §1; re-read this session) |
| Full species file at the jar path | **Yes** | species | as §4a. Two catches follow. |
| A form with its own `evolutions`, chosen by an aspect | **Yes, for that Pokémon only** | instance | `Pokemon.evolutions = form.evolutions`. `FormData.evolutions` is the form's own and does not fall back. The standard form is built with `_evolutions = species.evolutions` (`src:pokemon/Species.kt` `standardForm`). VERIFIED in source, never loaded. |

**Two catches with the full-file route:**
1. **Additions apply on top of the file.** COBBLEVERSE-DP-v31's Meltan addition would re-append its level-70 / anvil
   rule onto our Meltan file.
   - The fix: also ship `data/cobblemon/species_additions/meltan.json`. Same namespace and name means same id, so ours
     replaces Cobbleverse's when our pack sits above DP-v31 (`JsonDataRegistry` keying, notes §1).
   - It keeps its `implemented`, `behaviour` and drop fields and leaves out `evolutions`.
   - ASSUMED: our pack's order above DP-v31. That depends on how the datapack reaches the server (`global_packs.toml`
     force-loads `datapacks/`). X2.
2. **Two mod copies of Kubfu.** Cobblemon and Mega Showdown both ship `species/generation8/kubfu.json`. ASSUMED: a
   world or global datapack sits above all mod data, so ours beats both. X2.

### 5b. What it takes, species by species (route: full file, emitted to `build/` from a patch spec)

| Species | Native | Replacement | Note |
|---|---|---|---|
| Cosmog | `level` 43 | `level` 31 | plus new stats and moves (§6) |
| Cosmoem | `level` 53 + `time_range` day / night | `level` 46 + the same day / night branch | keeps the Solgaleo / Lunala choice |
| Kubfu | `item_interact` scroll, no requirement | `item_interact` scroll **+ `level` 31** (`requirements` is a list on `item_interact`, VERIFIED in the JSON shape) | the scrolls must be handed out (a reward or Oak); their natural sources likely do not exist in our world (§3c) |
| Type: Null | `friendship` 160 | `level` 31 | Silvally's type then needs a memory (Mega Showdown's 17 memory items, VERIFIED present; their source not checked) or stays Normal |
| Poipole | `has_move` dragonpulse | keep the method; learnset edit puts Dragon Pulse at 31 (§4b) | or replace with `level` 31 if X1 fails |
| Meltan | none (Cobbleverse: anvil + 70) | `level_up` `level` 31 → Melmetal, **and** shadow the Cobbleverse addition | Melmetal gets no `preEvolution` unless its file is also written (cosmetic: Pokédex link) |

- **Optional by default.** VERIFIED: `LevelUpEvolution` defaults to `optional = true` (notes §3a), so each evolution
  is *offered*, and the player can decline or delay it. ASSUMED: the same holds for a level rule on `item_interact`.
- **Files:** five species files plus one shadowed addition, all emitted to `build/`, plus one patch spec in `data/`.
  Solgaleo, Lunala, Silvally, Urshifu, Naganadel and Melmetal are untouched.

### 5c. Two evolution points on a two-stage line

**Only Cosmog has two evolutions.** Kubfu, Type: Null, Poipole and Meltan evolve once. So "identical evolution
points" can mean only one of these:
- **(i)** the two-stage lines use one of the two points and the other point does nothing for them; or
- **(ii)** the other point is a **stat step without a species change**, a same-species form change, which exists
  only on the form route (§6a).

**MEASURED**, native stats, wins of 35 leader Pokémon:

| Line | Evolves at 31 | Evolves at 46 |
|---|---|---|
| Kubfu | 22 | 14 |
| Type: Null | 26 | 21 |
| Poipole | 20 | 14 |
| Meltan | 12 | **2** |

The 46 point starves the weak lines. **For two-stage lines, use 31.** The 46 point is real only for Cosmoem →
Solgaleo / Lunala, unless the form route is taken.

### 5d. Are gym 3 and gym 6 the right points?

**MEASURED:**
- Every configured starter reaches its middle stage at 14 to 18, which is leg 1 under cap 20, before gym 1.
- It reaches its final stage at 30 (Totodile), 32 (three), 34 (three), 35 (three) or 36 (seventeen): legs 3 to 5.
- The median configured starter's BST at each gym's cap is 405, 405, 409 and 411 for gyms 1 to 4, then 530 from
  gym 5.

So:
- **Gym 3 is not "where a normal starter hits its second stage".** That happens before gym 1. Gym 3 to gym 5 is where
  a normal starter hits its **third**.
- A **31** point lands one leg *after* the earliest normal final stage (Totodile, 30), and about one leg *before*
  the typical one (36, needing cap 40).
- **46 is deliberately late.** The final form arrives for gyms 7, 8 and Victory Road. That matches the owner's "does
  not carry the midgame", and it means a mythical sits one stage behind a normal starter on legs 5 and 6.

**Verdict:**
- **Gym 3, as 31, is the right first point** for every line.
- **Gym 6, as 46, is right only as a design choice for Cosmog's final stage.** For the four two-stage lines it costs
  too much (Meltan 2 of 35).
- If the owner wants the mythicals to track a normal starter instead, the matching points are about 16 and about 36.

---

## 6. Question 2: scaling the five to similar strength

### 6a. What each option is

- **a. Weak-form hack ×5.** Each line gets aspect-selected forms with normalised `baseStats` and curated `moves`. Each
  form carries the aspect onward through its own evolutions.
- **b. Accept the spread.** Native stats; only the evolution replacements in §5 and Poipole's learnset.
- **c. Hybrid (recommended).** Option b, plus **species-level** stats and learnsets for the Cosmog line only (Cosmog
  and Cosmoem), through `species_additions` `baseStats` and `moves`, both admissible keys (VERIFIED). Meltan
  optionally gets a better learnset.

### 6b. What each buys (MEASURED)

Scratch harness: `tools/battle_sim.py`'s own `Mon`, `duel` and `build_leader`. IVs 15, EVs 0, level-up moves only, no
switching, caps 20 to 55, eight leaders and 35 Pokémon. The repo was unchanged. "Normalised" = each line's **final**
form's stat distribution and level-up learnset, scaled to the median configured starter's BST at that cap: a stand-in
for curated forms.

| Line | Native, as shipped | b: 31 (Cosmog 31/46) | b: 30 (Cosmog 30/45) | a: normalised, every gym | a: normalised, stepping at 3 and 6 |
|---|---|---|---|---|---|
| Cosmog | **3** (no damage until Solgaleo at gym 8) | **3** | 8 | 18 | 16 |
| Kubfu | 9 without a scroll; 25 with one from the start | 22 | 24 | 19 | 18 |
| Type: Null | 16 never evolved; 33 as Silvally at once | 26 | 29 | **32** | **31** |
| Poipole | 23 (evolves at once, §3d) | 20 | 23 | 20 | 17 |
| Meltan | **2** (never evolves) | 12 | 14 | 10 | 9 |
| *the 27 configured starters* | *9 to 27, median 17* | | | | |

**Other measurements:**
- Cosmog and Cosmoem **given Solgaleo's whole level-up list** but their own stats score 5 (31/46) and 8 (30/45). So
  Cosmog needs *stats*, not only moves.
- Meltan given Melmetal's list scores the same 12, so its weakness is Melmetal's own (Speed 34, a thin level-up list).

**What the table says:**
- **Normalising stats does not close the spread**: 10 to 32 normalised, against 3 to 26 under b. Type: Null / Silvally
  stays on top and Meltan / Melmetal at the bottom, because movepool and typing dominate at these caps. This agrees
  with STARTER_OPTIONS.md §5, measured for single mythicals.
- **The one line that stats do fix is Cosmog**, from 3 to between 16 and 18. That is the case for option c.

**Limits:**
- The harness sees no TMs, held items, abilities or switching.
- Silvally is simulated as Normal (no memory). Urshifu is Single Strike.
- These are lower bounds on spread, not predictions of play.

### 6c. Costs, against each other

|  | a. Weak forms ×5 | b. Accept spread | c. Hybrid (recommended) |
|---|---|---|---|
| Data | species_additions **forms** on about 12 species: Cosmog, Cosmoem, Solgaleo, Lunala, Kubfu, Urshifu (two styles), Type: Null, Silvally, Poipole, Naganadel, Meltan, Melmetal. Each form carries baseStats, moves and evolutions whose result keeps the aspect. | patch spec for 5 species + 1 shadowed addition; Poipole learnset | b + `species_additions` for Cosmog and Cosmoem (`baseStats`, `moves`), committed as our own text |
| Hidden multiplier | **Silvally's 17 memory forms and Urshifu's two styles are themselves aspect-selected forms.** `Species.getForm` takes the **last** form whose aspects all match (notes §2), so an appended stage form hides them. Each stage needs one form per memory (17) and per style (2), or the type and style are lost. | none | none |
| Unverified mechanism | E1–E5 from the notes, plus **an aspect carried across a species change** (Cosmog → Cosmoem keeps `forcedAspects` on the same object: VERIFIED by source reading, never run) | X1, X2, X3 | X1, X2, X3 + a `baseStats` addition loads (notes §1 "NOT RUN") |
| Tools | `battle_sim.py` must learn forms, aspects and our additions; `config_starters()` already drops properties (`tools/battle_sim.py:991`) | `battle_sim.py` must read the patched species (from `build/` or the spec) and handle `has_move` and `item_interact` + level in `evolve()` (`:277-303` follows only a single `level` requirement) | as b, plus reading two additions |
| Tests | stress rewrite (§7) + an independent audit of every stage's BST against the jar-derived starter curve | stress rewrite (§7) + an audit that each replaced evolution is reachable under the caps (expectation from `data/trainers.json` aces, not from the patch) | as b + the Cosmog BST audit |
| Effort (ASSUMED, scaled from the one-mythical figure of about 3 sessions, `STARTER_DESIGN_COMPARISON.md:93`) | **about 5–7 sessions**: experiments 1; forms and generator 2 (Silvally / Urshifu fan-out); tools 1; balance 1–2 | **about 2 sessions**: experiments 1, build + tools + tests 1 | **about 2–2.5 sessions** |
| Balance outcome (MEASURED above) | 9–32: does not narrow the spread | 3–26: Cosmog unplayable | about 12–26 with Cosmog rebased, inside today's 9–27 band |
| Side effects | instance-only: wild and raid copies untouched | species-wide: wild Kubfu, Meltan and Cosmog, and raids, get the new evolution levels (§2) | as b, plus wild Cosmog gets the new stats (End-only, ultra-rare) |

**Recommendation: c.**
- It fixes the only line that cannot play, at species level, in two committed files.
- It does not build twelve-plus forms whose measured payoff is nil.
- The form route stays available for one line if X-tests show a species-wide change hurts something (for example, if
  the owner later wants a second stat step at gym 6 for the two-stage lines).

---

## 7. What five starters do to the stress tests

**What breaks (VERIFIED):**
- `tools/battle_stress.py:329-331` raises unless `len(config_starters()) == 27`.
- `:91-93` raises unless `SAMPLE_SIZE % len(starters) == 0`, and 108 % 5 = 3.
- `tests/test_battle_stress.py:82-83` asserts 27 starters with exactly 4 profiles each.
- `:148` monkeypatches 27 synthetic starters.
- The report text hard-codes "All 27 ... exactly four times" (`tools/battle_stress.py:393`).
- No other test or tool depends on the count: `config_starters` is read only by `battle_sim.py` and `battle_stress.py`
  (grep this session).

**The arithmetic fix:**
- 105 (21 each) or 110 (22) divide by 5.
- The archetype counts (`tools/battle_stress.py:31-38`: 24/18/18/18/15/15) must re-total.
- **115 = 25/20/20/20/15/15** keeps every archetype divisible by 5, so each starter can appear equally *within* every
  archetype. Today's round-robin `starters[i % n]` (`:101`) does not guarantee that even at 27.
- It is about 6% more simulation than 108.

**The real cost is the starter model, not the count:**
- The simulators read species only from the jar and keep the first word of each starter entry.
- Without teaching them the patched data, the stress test would field:
  - a Cosmog with Splash;
  - a Poipole that is Naganadel from level 5;
  - a Meltan that never evolves;
  - a Kubfu that never evolves (scrolls are "stones");
  - a Type: Null that never evolves (friendship is not modelled).
- That would be a measurement of the wrong Pokémon, which is worse than a red test.

**Whether 27 still means anything:** the other session is placing the 27 normal starters as wild spawns. Once that
lands they are catches in the availability data, not starters, and "27 starters × 4" is a stale model, not merely a
broken assertion. The starter dimension becomes the five, and each needs equal representation.

**Rewrite cost:**
- `tools/battle_stress.py`: the sample size, the archetype counts, the count check derived from config, and the
  report text.
- `tests/test_battle_stress.py`: lines 69–83 and 148.
- `tools/battle_sim.py`: patched species and evolutions, as §6c.
- One full stress run in the integration session.
- The same work is needed under a, b or c. Option a adds form and aspect support on top.

---

## 8. Recommendation per decision

| Decision | Recommendation | Why |
|---|---|---|
| Evolution points | **Level 31 and level 46**, each one above a leg cap, so badges 3 and 6 gate them without a flag | the only flagless badge gate (§4b); contingent on X3 (Rare Candy and the cap) |
| Two-stage lines | **Evolve at 31.** The 46 point applies to Cosmoem → Solgaleo / Lunala. | 46 starves Meltan (2 of 35) and Poipole and Kubfu (14) (§5c) |
| Override mechanism | **Full species files emitted to `build/` from a committed patch spec**, plus shadowing Cobbleverse's Meltan addition | additions cannot remove a method (§5a); MPL-2.0 copies must not be committed (§4a) |
| Poipole | learnset patch: Dragon Pulse at 31; remove `tm:` and `tutor:dragonpulse` | the native `has_move` then gates itself (§4b) |
| Kubfu | keep the scroll branch, add `level` 31; hand both scrolls out (reward or Oak) | the scrolls' natural sources are likely absent in our world (§3c) |
| Scaling | **Option c**: native stats for four lines; species-level `baseStats` + `moves` for Cosmog and Cosmoem | stats fix only Cosmog; form ×5 costs about 5–7 sessions for no measured narrowing (§6) |
| Stress tests | 115 profiles = 25/20/20/20/15/15; teach `battle_sim` the patched species before trusting any number | §7 |

---

## 9. Experiments needed before building (designed, not run; none in `EXPERIMENT_BACKLOG.md` yet)

All need staging with the server lock. X1 to X3 and X6 fit one staging session.

**X1. Learnset replace.**
- **Steps:**
  1. Add a `species_additions` `poipole.json` whose `moves` puts Dragon Pulse at 31 and has no `tm:` or `tutor:` entry.
  2. Boot, and grep for `Caught exception applying addition`.
  3. `pokegive poipole level=5`.
- **Pass:**
  - The summary swap does not offer Dragon Pulse at level 5 and does offer it at 31.
  - The evolution prompt appears within seconds of Dragon Pulse entering the moveset.
  - A Dragon Pulse TM (native and TMCraft) is refused before 31.
- **Fail:** Dragon Pulse is still selectable at 5, or the addition errors.

**X2. Evolution replace and pack order.**
- **Steps:** load the generated `cosmog`, `cosmoem`, `kubfu`, `typenull` and `meltan` species files, plus the shadowed
  Meltan addition.
- **Pass:**
  - A level-30 Meltan has no evolution and a level-31 one is offered Melmetal.
  - There is no anvil / level-70 rule.
  - Kubfu's level rule wins over Mega Showdown's `kubfu.json`.
  - Cosmoem branches by day and night at 46.

**X3. The cap as the gate.**
- **Steps:**
  1. Take a capped level-30 Pokémon on leg 3.
  2. Battle for experience and use a Rare Candy.
  3. Then clear gym 3.
- **Pass:** it stays at 30 until badge 3, then reaches 31 and is offered the evolution.
- **Fail:** the candy passes the cap. Then add the `advancement` requirement.

**X4. Cosmog stats.**
- **Steps:** load a `baseStats` + `moves` `species_additions` file for Cosmog.
- **Pass:**
  - The summary and battle damage show the new bases.
  - A client with no datapack shows the same (notes E4).

**X5. Starter entries.**
- **Steps:** five entries in `starters.json`, for example `"cosmog level=5"`.
- **Pass:** each appears on the starter screen and is created as written. Also count the tabs (the open EXP-029).

**X6. Rendering.** Each of the 12 species renders on a client with Mega Showdown 1.0.2+1.8, with no substitute doll.

**Only if option a is chosen:** E1–E5 from `docs/research/notes/starter-stat-mechanics.md`, plus:
- an aspect carried across a species change (Cosmog → Cosmoem → Solgaleo keeps its form);
- Silvally with a memory and Urshifu Rapid Strike under a stage form.

---

## 10. What was not checked

- Whether our spawn suppression lets the wild copies in §2 spawn.
- How Mega Showdown's memory items are obtained.
- Whether mints and Bottle Caps change any of this. They do not change base stats.
- How TMCraft decides compatibility.
- The order of our datapack against COBBLEVERSE-DP-v31 and against mod data on the live server.
- Every effort figure in §6c, which is ASSUMED, scaled from the earlier one-mythical estimate.
