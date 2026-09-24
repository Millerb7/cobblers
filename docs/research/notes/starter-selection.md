# What starter is a player on this pack actually offered?

**Answered for:** Cobblemon 1.8.0 (target) and Cobblemon 1.7.3 (what the base
pack ships). Both were checked; on this point they agree.

**Date:** 2026-09-23.

**How the evidence was gathered.** `Bash` was disabled for this session, so the
jars could not be unzipped or run through `javap`. Two techniques were used
instead:

1. **ZIP directory grep.** A jar stores entry *names* uncompressed in the local
   file headers and the central directory, so `rg` on the raw jar enumerates
   the entry list reliably (entry *contents* are DEFLATE-compressed and are not
   greppable). This proves presence/absence of resource paths, not code.
2. **Official versioned source**, `https://gitlab.com/cable-mc/cobblemon`, at
   refs `1.8.0` and `1.7.3`, fetched as raw files.

Code quoted below came through a fetch-and-render step, so treat the exact
whitespace as approximate; the identifiers, control flow and defaults are the
load-bearing part and were requested verbatim.

---

## Short answer

`useConfigStarters: false` does **not** disable `starters.json` on this pack.
With no datapack supplying a `starters` registry — and none does — Cobblemon
falls back to the config file's list regardless of that flag. The players are
offered **all 13 categories / 41 entries / 36 distinct species** in
`base-pack/cobbleverse/config/cobblemon/starters.json`, every one at
**level 5**, not the 9 species of the Kanto/Johto/Hoenn trios.

---

## 1. What `useConfigStarters: false` actually does

**VERIFIED.** The flag is read in exactly one place: `StarterDataLoader.reload`,
which merges datapack-loaded starter categories with the config list.

Source: `common/src/main/kotlin/com/cobblemon/mod/common/data/StarterDataLoader.kt`
at ref `1.8.0`
(`https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/data/StarterDataLoader.kt`):

```kotlin
object StarterDataLoader : JsonDataRegistry<StarterCategory>
// resourcePath "starters", id cobblemonResource("starters")

override fun reload(data: Map<ResourceLocation, StarterCategory>) {
    categories.clear()

    // If enabled, start with default built-in starters
    if (Cobblemon.starterConfig.useConfigStarters) {
        categories += Cobblemon.starterConfig.starters
    }

    val loadedCategories = data.mapNotNull { ... }   // validation: name non-blank, pokemon non-empty

    // Default: If datapack exist then only use those, otherwise fall back to built-in starters
    if (loadedCategories.isNotEmpty() && !Cobblemon.starterConfig.useConfigStarters) {
        categories.clear()
        categories += loadedCategories
    } else {
        // Merge: Replace matching entries in-place (case-insensitive by name), otherwise append
        ...
    }

    observable.emit(this)
}
```

So the flag means **"when a datapack supplies starters, should the config list
be kept?"**:

| `useConfigStarters` | datapack `starters` present | resulting `StarterDataLoader.categories` |
|---|---|---|
| `false` | yes | datapack categories **only** — config file ignored |
| `false` | no | **empty** |
| `true` | yes | config list, then datapack categories merged in (same name replaces, new name appends) |
| `true` | no | config list |

**VERIFIED.** It is *not* "ignore this file and use a built-in list", and it is
*not* "ignore starters entirely". The name is misleading: on a pack with no
starter datapack the flag is a no-op, because of the fallback in the next
section.

**VERIFIED.** `useConfigStarters = false` is Cobblemon's own default, not a
Cobbleverse decision. From
`common/src/main/kotlin/com/cobblemon/mod/common/config/starter/StarterConfig.kt`
at ref `1.8.0`:

```kotlin
@CobblemonConfigField(Category.Starter, lang = "use_config_starters", SERVER)
var useConfigStarters = false
```

## 2. Is there a built-in list, and what gets used when `categories` is empty?

**VERIFIED — the decisive line.** `CobblemonStarterHandler.getStarterList`
falls back to the config list whenever the datapack-derived list is empty:

Source: `common/src/main/kotlin/com/cobblemon/mod/common/starter/CobbledStarterHandler.kt`
(note the file name is `CobbledStarterHandler.kt`; the class inside is
`CobblemonStarterHandler`) at ref `1.8.0`:

```kotlin
override fun getStarterList(player: ServerPlayer): List<StarterCategory> {
    val fromPacks = StarterDataLoader.getAllCategories().toList()
    return fromPacks.ifEmpty { Cobblemon.starterConfig.starters }
}
```

**VERIFIED.** The identical function exists at ref `1.7.3`
(`https://gitlab.com/cable-mc/cobblemon/-/raw/1.7.3/common/src/main/kotlin/com/cobblemon/mod/common/starter/CobbledStarterHandler.kt`),
so the behaviour is the same on the currently shipped 1.7.3 and on the 1.8.0
target.

`Cobblemon.starterConfig` is the deserialized config object, i.e. the contents
of `config/cobblemon/starters.json`, not the hardcoded defaults — the hardcoded
`StarterConfig` values only apply to a missing file or a missing field.
`base-pack/cobbleverse/config/cobblemon/main.json:31` has
`"exportStarterConfig": true`, which is consistent with the file being written
back out by the mod and therefore live.

**VERIFIED — Cobblemon ships no built-in `starters` datapack.** Neither jar
contains a `data/cobblemon/starters/` entry:

- `Cobblemon-fabric-1.8.0+1.21.1.jar`: the `data/cobblemon/*/` directory entries
  are `action_effects, advancement, arts_and_crafts, bag_items, behaviours,
  berries, callbacks, cosmetic_items, dex_entries, dexes, dialogues, fossils,
  global_species_features, habitat_pools, held_items, hourglass_dusts,
  loot_table, marks, mechanics, molang, moonlight, moveset_builders,
  natural_materials, npc_presets, npcs, painting_variant, pokemon_interactions,
  pokerods, recipe, ride_settings, seasonings, spawn_bait_effects,
  spawn_detail_presets, spawn_pool_world, spawn_rules, spawning, species,
  species_feature_assignments, species_features, structure, tags, tms,
  trim_pattern, unlockable_pc_box_wallpapers, worldgen, rs_pieces_spawn_counts,
  rs_pool_additions`. No `starters`. Every jar entry whose path contains
  `starter` is either a GUI texture under
  `assets/cobblemon/textures/gui/starterselection/` or a `.class` file.
- Confirmed against the repository too: the GitLab tree API for
  `common/src/main/resources/data/cobblemon` at ref `1.8.0` lists no `starters`
  directory.

So the "built-in list" is literally the hardcoded `StarterConfig.starters`
default (11 categories, all at `level=10`, including a `Special` category with
`randomStarter = true` holding Pikachu and Eevee) — but **on this pack it is
never reached**, because `config/cobblemon/starters.json` exists and overrides
the whole field.

## 3. Does anything else in the installed set override it?

**VERIFIED.** No mod in the 1.8 experiment server mod set ships a `starters`
datapack directory. `rg "/starters"` across
`experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods/` (all jars,
matching on the uncompressed ZIP entry names) returned **0 occurrences across 0
files**.

**VERIFIED.** No Cobbleverse datapack supplies starters. `rg` for any path
containing `starter` across
`C:\Users\wnd\Documents\github\cobblers\COBBLEVERSE\datapacks\` — which holds
`COBBLEVERSE-DP-v31.zip`, `COBBLEVERSE-Loot-DP-v11.zip`,
`COBBLEVERSE-RCT-DP-v20.zip`, `COBBLEVERSE - No Ender Dragon.zip`,
`COBBLEVERSE - No Hunger.zip`, `PokeCenterPCs-DP.zip`, and
`extra/{Hoenn,Johto,Sinnoh,Terralith}-DP.zip` — returned no matches, and a
targeted `starters/` grep of `COBBLEVERSE-DP-v31.zip` specifically returned no
matches.

**VERIFIED.** The Cobbleverse instance has no `globalpacks/`, `openloader/` or
`kubejs/` data directory that could inject one.

**VERIFIED.** The only Cobbleverse config files mentioning "starter" at all are
`base-pack/cobbleverse/config/cobblemon/starters.json` and
`base-pack/cobbleverse/config/cobblemon/main.json:31`
(`exportStarterConfig`). The other four hits
(`sophisticatedcore-common.toml`, `roughlyenoughitems/collapsible.json5`,
`resourcepackoverrides.json`, `defaultoptions-common.toml`) are unrelated uses
of the word.

**NOT CHECKED — live-server gate.** `C:\Users\wnd\Documents\github\cobblers-server\datapacks`
was deliberately **not** enumerated. `CLAUDE.md` requires a process/port check
and the external coordination lock before any access to the `cobblers-server`
runtime, and with `Bash` disabled neither could be performed. The
`COBBLEVERSE\datapacks` folder above is the same upstream set by filename, but
**it is not proof of what is in the server's folder** — a server-only datapack
could still add a `starters` registry and silently replace the whole list
(because `useConfigStarters: false` makes a datapack list *replace* rather than
merge). See experiment candidate EXP-029 below.

**ASSUMED — a mod could swap the handler.** `Cobblemon.starterHandler` is a
public `var` (`var starterHandler: StarterHandler = CobblemonStarterHandler()`
in `Cobblemon.kt`, ref `1.8.0`), so any mod may replace the whole handler and
with it `getStarterList`. This is only an assumption of *possibility*: class
constant pools are compressed inside the jars and could not be searched without
a shell, so no installed mod was cleared or implicated. Candidates worth
decompiling if the in-game list disagrees with this note: `cobblemon-additions`,
`CobbleverseBadges`, `timcore`, `LumyMon`, `rctmod`.

## 4. The list the players are actually offered

**VERIFIED (by source-reading, not by observation)** — the contents of
`base-pack/cobbleverse/config/cobblemon/starters.json`, 13 categories,
41 entries, 36 distinct species, all `level=5`:

| Category (`displayName`) | Entries |
|---|---|
| Kanto | Charmander, Squirtle, Bulbasaur |
| Johto | Cyndaquil, Totodile, Chikorita |
| Hoenn | Torchic, Mudkip, Treecko |
| Sinnoh | Chimchar, Piplup, Turtwig |
| Unova | Tepig, Oshawott, Snivy |
| Kalos | Fennekin, Froakie, Chespin |
| Alola | Litten, Popplio, Rowlet |
| Galar | Scorbunny, Sobble, Grookey |
| Hisui | Cyndaquil, Oshawott, Rowlet (all `region_bias=hisui`, `pokeball=ancient_poke_ball`) |
| Paldea | Fuecoco, Quaxly, Sprigatito |
| Pallet | Pikachu (`moves=thundershock`), Eevee, Pichu (`region_bias=alola`) |
| Lumya | Bagon, Azurill (`gender=female`), Budew (`gender=female`) — all `pokeball=great_ball` |
| Cosplay | Pikachu ×5 (`cosplay=belle/libre/phd/pop_star/rock_star`) |

Line references: `base-pack/cobbleverse/config/cobblemon/starters.json:5-125`.

**Campaign consequence.** The battle simulation run this session covered only
the 9 species of the first three categories. The real offer is four times
wider, and includes Bagon (→ Salamence), Eevee (→ nine evolutions), Piplup,
Rowlet and the Hisui variants. Any balance conclusion drawn from the 9-species
set is an undercount of what a player can bring to gym 1.

**ASSUMED — ordering.** None of the config categories carries an `order` field,
and `StarterCategory.order` defaults to `0` (`StarterCategory.kt`, ref `1.8.0`).
The hardcoded defaults use `order = -110 … -100`. What the UI does with 13
categories that all sort equal was not determined; `StarterSelectionScreen.kt`
shows no `sortedBy` of its own, so insertion order is the likely result, but the
sort may live in the `CategoryList` widget which was not read.

## 5. Is the starter gated, re-rollable, refusable?

**VERIFIED — `allowStarterOnJoin` sets the initial lock.** From
`common/src/main/kotlin/com/cobblemon/mod/common/api/storage/player/adapter/PlayerDataJsonBackend.kt`
at ref `1.8.0`:

```kotlin
override val defaultData = { forPlayer: UUID -> GeneralPlayerData(
    uuid = forPlayer,
    starterPrompted = false,
    starterLocked = !Cobblemon.starterConfig.allowStarterOnJoin,
    starterSelected =  false,
    ...
)}
```

With `allowStarterOnJoin: true` (this pack), a new player's `starterLocked` is
`false`, so they may choose immediately on first join.

**VERIFIED — `promptStarterOnceOnly` only controls the nag, not the right.**
From `GeneralPlayerData.toClientData()`, ref `1.8.0`:

```kotlin
if(Cobblemon.starterConfig.promptStarterOnceOnly) !starterPrompted else true
```

That boolean becomes `ClientPlayerData.promptStarter`. With
`promptStarterOnceOnly: true`, once the player has been prompted once
(`starterPrompted` is set in `requestStarterChoice`), the client stops offering
the prompt. The player is **not** barred from choosing — `starterSelected` is
still false, so they can still open the screen. `CobblemonClient` has a separate
`checkedStarterScreen` flag described in-source as "If true then we won't bother
them anymore about choosing a starter even if it's a thing they can do", which
is the same idea client-side.

**VERIFIED — exactly one starter, no re-roll.** `requestStarterChoice` and
`chooseStarter` both hard-fail on `starterSelected`
(`lang("ui.starter.alreadyselected").red()`) and on `starterLocked`
(`lang("ui.starter.cannotchoose").red()`), and `chooseStarter` sets
`playerData.starterSelected = true` inside the `STARTER_CHOSEN` event callback.
There is no code path that clears `starterSelected`.

**VERIFIED — the op command cannot re-roll either.**
`OpenStarterScreenCommand` (literal `openstarterscreen`, permission
`CobblemonPermissions.OPEN_STARTER_SCREEN`) checks whether the player has
already chosen and denies if so; it *unlocks* a locked player, marks them
prompted, saves and sends the list. So an operator can un-gate someone who was
locked, but cannot give a second starter through it.

**VERIFIED — refusing is possible and sticky-free.** Nothing forces the choice;
`handleJoin` is an empty body in `CobblemonStarterHandler` in 1.8.0. A player
who declines simply keeps `starterSelected = false` and can request the screen
later (the client will not re-prompt unaided, given `promptStarterOnceOnly:
true`).

**VERIFIED — a random option exists in the protocol.** `chooseStarter` treats
`index == category.pokemon.size` as "random" and then picks
`getStarterList(player).flatMap { it.pokemon }.random()` — i.e. random across
**every** category, not within the chosen one.

**UNKNOWN — whether the UI ever offers that random slot on this pack.**
`StarterCategory.randomStarter` defaults to `false` and no Cobbleverse category
sets it; `randomStarter` does not appear in `StarterSelectionScreen.kt`, so the
widget that honours it was not located. The hardcoded default `Special` category
is the only one in Cobblemon's own defaults that sets it, and that category is
not in this pack's config.

**VERIFIED — shiny starters are a gamerule.** `chooseStarter` checks
`player.level().gameRules.getBoolean(CobblemonGameRules.SHINY_STARTERS)`. Its
value on our server was not read.

---

## What would have to be observed in a running game

A config read is not proof of behaviour. To be certain:

1. Join a fresh player on the actual server and screenshot the starter screen.
   Count the category tabs. **13 tabs including Pallet, Lumya and Cosplay
   confirms this note; 3 tabs would mean something is filtering the list and
   this note is wrong.**
2. Check the starter's level on capture (expect 5, not 10). Level 10 would mean
   the hardcoded defaults are in play and `starters.json` is not being read.
3. `/openstarterscreen <player>` on a player who has already chosen — expect the
   red "already selected" message.
4. Grep `logs/latest.log` for `Replaced starter category` / `Appended starter
   category` on boot. **Either message means a datapack *is* supplying starters
   and the fallback path is not what is running.** Silence on both is consistent
   with this note.
5. Confirm no category tab offers a "?" / random slot.
6. Read the `cobblemonShinyStarters` gamerule value.

## Experiment candidates

Added to `docs/research/EXPERIMENT_BACKLOG.md` as **EXP-029 Live starter offer**.

Open specifically:

- The server's own `datapacks/` folder was never inspected (live-server gate,
  no shell). If it contains a `data/<ns>/starters/*.json`, that list *replaces*
  everything in this note, because `useConfigStarters: false` makes a datapack
  list exclusive.
- Whether any installed mod replaces `Cobblemon.starterHandler`. Needs a
  decompile pass with a shell available.
- The sort order and the random-slot question in section 4/5.
