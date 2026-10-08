# Dynamax and Gigantamax as dungeon encounters (Cobblemon 1.8.0)

Researched 2026-10-08 for the owner's question: can a dungeon have Dynamax or Gigantamax Pokemon?
Research only; nothing was built and nothing was run in Minecraft.

**Sources read.** The installed jars in the offline server snapshot
`C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/` (102 entries), opened
read-only with Python `zipfile` and `javap -c -p`: `Cobblemon-fabric-1.8.0+1.21.1.jar`,
`mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar` (MSD), `rctapi-fabric-1.21.1-0.16.1-beta.jar`,
`rctmod-fabric-1.21.1-0.19.0-beta.jar`. The snapshot's `config/` and `datapacks/`
(`COBBLEVERSE-DP-v31.zip`, `COBBLEVERSE-Loot-DP-v11.zip`, `COBBLEVERSE-RCT-DP-v20.zip`). The
brief's path `cobblers/COBBLEVERSE/datapacks/` does not exist; the snapshot copy was used.
Bytecode citations are `Class.method` plus the javap offset, because a class has no line numbers to cite.

## The answer

**Partly.** Real Dynamax and Gigantamax exist in this pack: Mega Showdown 1.0.2 implements them.
Cobblemon 1.8.0 supplies the data side (Dynamax Level, the G-Max Factor, the `dynamax_form`
feature) and MSD patches the battle engine so that Dynamax can be used in Cobblemon's battles.

| Question | Answer | Status |
|---|---|---|
| Does the pack support it? | **Yes, through Mega Showdown 1.0.2.** Stock Cobblemon's battle engine allows Dynamax only in gen 8. Cobblemon battles are gen 9, and MSD patches that check. Cobblemon Raid Dens is **not installed**: only its datapack files are present. | VERIFIED from the code; never run |
| Can a **wild** Pokemon Dynamax? | **No.** Wild battles use Cobblemon's own battle AIs, and neither of them ever asks for a gimmick. | VERIFIED from the code |
| Can an **NPC's** Pokemon Dynamax? | **Yes, if it is an RCT trainer.** RCT's AI Dynamaxes a team member whose trainer JSON says `"gimmicks": {"dynamax": true, "gmax": true}`. Cobbleverse already ships one: Cyrus's Corviknight. | VERIFIED from the code and data; never run |
| A real mechanic or a fake? | **Real for an RCT trainer's Pokemon:** HP times (1.5 + 0.05 x Dynamax Level), Max Moves, 3 turns, once per battle. **Faked for a wild one:** we can copy the look (size, clouds, the Gmax model) but not the battle state. | as above |
| What does a player need? | A Dynamax Band (or an Omni Ring) in a hand or an Accessories slot, **and** a Power Spot block within 32 blocks, because `dynamaxAnywhere` is false. | VERIFIED from the code |
| Would a player have it? | **No.** The band needs a Wishing Star, which comes only from a structure we have not placed. The Power Spot also needs a Max Mushroom, which only worldgen produces. Nothing in our economy or rewards grants any of them. | VERIFIED (grep of `data/`) |

So a dungeon **can** hold a real Dynamax boss, but only as an RCT trainer battle. A **wild**
Dynamax boss, such as the Entei room's spawned boss, can only be faked, and the fake can borrow
MSD's own visuals.

## 1. Which jar implements it, and is Raid Dens there?

- **VERIFIED.** MSD 1.0.2 carries the whole feature. It has the items `dynamax_band`,
  `dynamax_candy`, `max_mushroom`, Max Soup and Max Honey (`com/.../item/custom/dynamax/*`), the
  `power_spot` and `wishing_star_crystal` blocks, Gmax models for 33 species
  (`assets/cobblemon/bedrock/pokemon/models/*/..._gmax.geo.json`), a Dynamax effect, the
  `DynamaxStartCallback` and `DynamaxEndCallback` events, and a patched Showdown battle engine
  (`assets/mega_showdown/showdown/*.js`).
- **VERIFIED: Cobblemon Raid Dens is not installed.** No jar in the snapshot's `mods/` has "raid"
  in its name. The mod was removed for the 1.8 target (`modpack/manifest/overlay.json:528-531`;
  `docs/research/COBBLEVERSE_COMPATIBILITY.md:53,281`: `NoSuchMethodError` for the removed
  `GraalShowdownService.getContext()`). Its data is still present, though:
  - `COBBLEVERSE-DP-v31.zip` carries 277 `data/cobblemonraiddens/` files, among them 246 raid
    bosses. `raid/boss/charizard_gmax.json`, for example, sets `"raid_feature": "DYNAMAX"` and
    `dynamax_form=gmax`.
  - `COBBLEVERSE-Loot-DP-v11.zip` carries the seven `cobblemonraiddens:loot_table/raid/tier/*`
    tables.
  - `config/cobblemonraiddens/*.json5` is left over in the snapshot.

  The staging log's unknown `cobblemonraiddens:*` registry keys are what this predicts. That log
  line is *relayed* from the brief: I did not read the log. **None of this is a Dynamax source.**
- **VERIFIED: stock Cobblemon's Showdown cannot Dynamax in a Cobblemon battle.** Cobblemon's
  bundled `node_modules/pokemon-showdown/sim/side.js:127-128` has
  `canDynamaxNow() { if (this.battle.gen !== 8) return false; ...`. MSD's replacement
  `assets/mega_showdown/showdown/side.js:119-127` changes that to `gen !== 9`, and it also
  refuses a side whose active Pokemon has Terastallized. `utils/ShowdownPatcher.class` holds the
  strings `/assets/mega_showdown/showdown/side.js` and `showdown/sim`, so the patch is copied in at
  runtime. *Whether the running server's `showdown/sim/side.js` is the patched copy was not checked*:
  that folder is not in the snapshot.
- **VERIFIED: once the patch is in, Showdown offers Dynamax to every side, not only to players.**
  MSD `pokemon.js:711-720` `getDynamaxRequest` refuses only for these reasons:
  - the side cannot Dynamax now;
  - the Pokemon is a Mega, a Primal, Ultra, holding a Z-crystal or Terastallized;
  - the Pokemon can Mega Evolve (Rayquaza excepted);
  - the species has `cannotDynamax`.

  Other facts from the patched engine:
  - Dynamax HP: `conditions.js:776`, `ratio = 1.5 + pokemon.dynamaxLevel * 0.05`.
  - It ends after 3 turns: `battle.js:1259`, `volatiles["dynamax"]?.turns === 3`.
  - Once per side per battle: `battle.js:2301-2305`, `side.dynamaxUsed = true`.

## 2. Wild versus NPC versus player: who decides to Dynamax

Showdown offers the option. **The actor's AI or player has to choose it**, by sending a move with
the gimmick id `dynamax`.

- **Players: gated twice, by key item.**
  1. Cobblemon's own `ShowdownActionRequest.sanitize` (offsets 15-90) returns at once unless the
     actor is a player. For a player, offsets 232-280 block each gimmick unless the player holds
     the matching Cobblemon key item. For Dynamax that is `cobblemon:dynamax_band`.
  2. MSD's `ShowdownActionRequestMixin.afterSanitize` blocks `Gimmick.DYNAMAX` and clears
     `maxMoves` for a player without that key item.

  MSD's `GimmickTurnCheck.check(ServerPlayer)` grants or removes the key item. It grants it only
  when **(a Power Spot is within `powerSpotRange`, or `dynamaxAnywhere`)** (offsets 11-27) **and**
  `hasGimmick(DYNAMAX)` holds (offsets 48-69). `hasGimmick` needs config `dynamax` true, plus an
  Omni Ring or an item tagged `mega_showdown:dynamax_band`.
  `AccessoriesUtils.checkTagInAccessories` looks at the main hand, the off hand, and every
  Accessories slot. **VERIFIED.**
- **Wild Pokemon: never.** Cobblemon's `StrongBattleAI` and `RandomBattleAI` build a
  `MoveActionResponse` at seven sites:
  - `StrongBattleAI` offsets 1363, 5678, 72 and 253;
  - `RandomBattleAI` offsets 423, 519 and 702.

  Every site uses the default-argument constructor with mask 6 or 4. Bit 4 means the third
  argument, `gimmickID`, is left at its default of null. So the AIs Cobblemon gives wild Pokemon
  never choose a gimmick, whatever Showdown offers. **VERIFIED from the code.** It also means a
  Cobblemon-native NPC (an `NPCEntity` with a party) never Dynamaxes, because it uses the same AIs.
  *Which of the two AIs a wild battle uses was not traced; neither one can Dynamax.*
- **RCT trainers: yes, opted in per Pokemon.**
  1. `rctapi` `models/Gimmicks` is the record `(String tera, boolean dynamax, boolean gmax)`.
     `models/PokemonModel` has a field `gimmicks`. The data example is Cobbleverse's
     `COBBLEVERSE-RCT-DP-v20.zip` `data/rctmod/trainers/team_galactic_cyrus.json:164-168`:
     `"gimmicks": {"dynamax": true, "gmax": true}` on Corviknight, with `"battleFormat": "GEN_9_DOUBLES"` at line 204.
  2. `PokemonModelConverter` offsets 786-792 call `Pokemon.setGmaxFactor(gimmicks.gmax())`.
  3. `RCTBattleAI` offsets 154-241 set the moveset's `canDynamax` true only when all of these hold:
     - `mega_showdown` is loaded;
     - the Pokemon's `gimmicks.dynamax` is true;
     - the actor has not yet used Dynamax;
     - the Pokemon is not Mega or Tera;
     - no Mega, Ultra Burst or Z-Move is available.
  4. `ResponseBuilder` offsets 183-220 build a 3-argument `MoveActionResponse` that carries the
     gimmick id.

  **VERIFIED from the code; never run.** No path here reads MSD's `dynamax`, Power Spot or band
  settings for an NPC. Those are checked only in `GimmickTurnCheck`, which takes a
  `ServerPlayer`. A scan of every MSD class's reads of `MegaShowdownConfig.dynamax` found only
  `GimmickTurnCheck.hasGimmick` and `DynamaxLevelHandler.update`.
- **What happens on screen, for any owner.** When Showdown reports Dynamax,
  `CobbleEvents.dynamaxStarted` (offsets 0-197) does the following:
  - grants advancements; `grantAdvancement` is null-safe, so a Pokemon with no owner is fine;
  - for a Gigantamax, applies `dynamax_form=gmax`, which brings the Gmax model;
  - adds the aspect `msd:dmax` and sets the persistent flag `is_max`;
  - calls `MaxGimmick.startGradualScaling(pokemon, dynamaxScaleFactor)`.

  `MaxGimmick` stores `orignal_size` and animates **`Pokemon.setScaleModifier`** up to the
  factor, which is 4.0 in `server/config/mods/mega_showdown/config.json:13`. It also calls
  `GlowHandler.applyDynamaxGlow`. On the client, `PokemonRendererMixin.render` draws the
  `DynamaxCloudsLayer` when the aspects contain `msd:dmax`. `dynamaxEnded` reverses all of it.
  **VERIFIED from the code.**

## 3. Can a datapack set it?

| What | How | Status |
|---|---|---|
| A trainer Pokemon Dynamaxes in battle | `"gimmicks": {"dynamax": true}` on an RCT team member; add `"gmax": true` for the Gigantamax form | VERIFIED (code and the Cyrus file); not run |
| Our generator would carry it | `tools/route_trainers.py:394` copies `rct["team"]` from `data/trainers.json` verbatim, and all 90 of our `rct` records use `"ai": {"type": "rct"}`. `gym_trainers.py` was not checked | VERIFIED for `route_trainers.py` |
| G-Max Factor and Dynamax Level on any Pokemon | Cobblemon 1.8.0 `PokemonProperties$Companion` parses `dmax_level` / `dmax` and `gmax_factor` / `gmax`. `BattleRegistry` packs `G` and the level into the Showdown team. `maxDynamaxLevel` is 10 (snapshot `config/cobblemon/main.json:81`). An RCT `PokemonModel` has **no** Dynamax Level field | VERIFIED |
| The Gmax look out of battle | Cobblemon 1.8.0 `data/cobblemon/species_features/dynamax_form.json` is a choice `gmax` or `eternamax`, `isAspect: true`, assigned to 33 species (`species_feature_assignments/dynamax_form.json`). Each has a `"Gmax"` form with `"aspects": ["gmax"]`. The models come from MSD | VERIFIED (data). Whether a wild spawned with `dynamax_form=gmax` battles without trouble: NOT VERIFIED; the same open question as the wild Mega |
| A wild Pokemon in the Dynamax state | **No datapack route.** Dynamax is a Showdown volatile that begins only when an actor chooses the gimmick | VERIFIED (section 2) |

## 4. What a player needs, and whether they would get it

- **Recipes (VERIFIED, MSD jar).**
  - `recipe/dynamax_band.json`: pink apricorns, iron, a **Wishing Star**, blue apricorns.
  - `recipe/power_spot.json`: redstone, a **Max Mushroom**, a **Wishing Star**, stone.
- **Sources (VERIFIED in our data).**
  - A Wishing Star comes only from `mega_showdown:wishing_star_crystal`, inside the
    `mega_showdown:wishing_weald` template. `data/structures.json:6791-6838` gives that template's
    disposition as "hand-place", and it is placed nowhere.
  - A Max Mushroom is a worldgen feature only (`docs/world-building/WORLDGEN_FEATURES.md:63-65`),
    and a pre-exported world grows none.
  - `grep` of `data/`, `server/` and `modpack/config` for `dynamax_band`, `wishing_star`,
    `power_spot`, `max_mushroom`, `dynamax_candy`, `max_soup` and `max_honey` finds only that one
    structure line. **No market, reward or loot of ours gives any of them.**
- **Config (VERIFIED, `server/config/mods/mega_showdown/config.json:10-13`):** `dynamax: true`,
  `powerSpotRange: 32`, `dynamaxAnywhere: false`, `dynamaxScaleFactor: 4.0`.
- **The open decision.** `docs/mechanics/ITEM_ROUTES.md:177,310` (Q6) and
  `docs/research/OBTAINABILITY_MODS.md:59,125` recommend `dynamax: false`. **A finding for that
  decision:** on the code read, `dynamax: false` removes Dynamax for **players only**. The RCT path
  never reads it, so "only bosses can Dynamax" is a possible configuration. *ASSUMED; it needs a
  staging test.* Also, every Dynamaxed Pokemon, the player's included, grows by
  `dynamaxScaleFactor` through `ScaleModifier`. Collision boxes scale with `ScaleModifier`
  (measured, `data/sizes.json:10`). A Charizard's hitbox height of 2.65 (MSD species file) times
  4 is about 10.6 blocks, so a Dynamax arena needs that much headroom.

## 5. The nearest things, and what each costs

**A. A real Dynamax boss as an RCT trainer battle.** This uses the actual mechanic. Give one team
member `"gimmicks": {"dynamax": true, "gmax": true}` on a Gmax-capable species, plus level, IVs, EVs
and a held item for strength. It Dynamaxes once, on the AI's chosen turn, for 3 turns, with HP
times 1.5 to 2.0. The visual is MSD's (4x size, glow, clouds, the Gmax model).

The costs:
- The boss is a trainer: a human NPC appears, and the Pokemon is not catchable.
- It is one player's battle at a time.
- Unknowns for an experiment: whether an RCT trainer entity can be hidden or styled as "the
  dungeon"; that the AI really does Dynamax in a GEN_9_SINGLES battle; that MSD's Showdown patch is
  live on the server.

The proof is a main-session staging check: one trainer edit, then one battle. That is less than a
narrow follow-up (about 2.6M). A dungeon boss built end to end is a builder unit, about 3.4-4.6M.

**B. A faked wild "Dynamax" boss on the proven wild-Mega and scaled-Pokemon patterns.** Spawn it the
way the Mega farms' keeper does (`data/gulch_mine.json:3158`, `macro spawn_at`, uncatchable,
leashed; Mega forms by aspect at line 3164). The Entei boss's spawned property string is the other
proven example (`data/entei_boss.json:18-19`, which has no scale today). Then add:
- **Size:** `scale_modifier=` up to 4.0, which is the field MSD itself animates. It is proven: the
  Ursaluna at 2.0 (`data/ursaluna_cave.json:68-69`, `docs/STATE.md:310`) and the size outliers
  (`data/sizes.json`, `docs/STATE.md:119`). Mind the headroom.
- **The Gmax model:** `dynamax_form=gmax` on one of the 33 species. NOT VERIFIED in battle.
- **The red clouds:** Cobblemon's `aspect=` property (`AspectPropertyType`, key `aspect`) set to
  `msd:dmax`, which is the aspect MSD's client renderer keys on. NOT VERIFIED that a forced aspect
  survives the battle start and the save.
- **The glow:** a Glowing effect.
- **"Dynamax HP":** this cannot be had. Stand-ins are level, `min_perfect_ivs`, HP EVs, and a held
  Leftovers or Sitrus.

It reads as Dynamaxed and is not: there are no Max Moves, no doubled HP, and no 3-turn end. The cost
is a narrow follow-up on an existing keeper, about 2.6M, on top of the place's own build.

**C. Letting players Dynamax.** This needs a Wishing Star and a Max Mushroom source, or a granted
band and Power Spot (or `dynamaxAnywhere: true`), and it needs the owner's Q6 decision first. It is
an economy and reward change, not this question's.

## Not verified

- Nothing above was run in Minecraft.
- That the server's extracted `showdown/sim/side.js` is MSD's patched copy.
- That RCT's AI actually picks Dynamax in play.
- That `dynamax: false` leaves the NPC path alone.
- Whether a Pokemon that enters battle already in the Gmax form, or with a forced `msd:dmax`
  aspect, battles without trouble.
- How Cobblemon chooses between its two AIs for a wild battle.
- The 2026-10-05 snapshot is assumed to match the running server's mods.
