# Cobbleverse → Cobblemon 1.8 compatibility

## Decision snapshot

**EXP-000 is not complete, and the repository is not ready for EXP-001.** The isolated dedicated server reaches Minecraft's `Done` state after the scoped runtime exclusions and Cobbleverse riding-seat migration. The assembled client connects, and Mudsdale and Charizard riding are verified; most gameplay smoke tests remain unverified.

The current target is Minecraft 1.21.1, Fabric Loader 0.19.5, Java 21, and Cobblemon 1.8.0. The effective dedicated-server set has 100 jars: 88 unchanged base jars and 12 replacements. Better Pokédex Scanner and Raid Dens are removed; PlayerXP and Krypton are excluded from the server only; the disabled legacy Particular jar is omitted, while Particular Reforged remains.

## Evidence standard

- **Verified fact:** read from local `fabric.mod.json`, a recorded cryptographic hash, the Modrinth version API, Fabric Meta, or an executed command captured in EXP-000.
- **Supported upstream:** a 1.8-targeted release exists. This proves metadata intent, not successful behavior in this pack.
- **Needs boot test:** metadata permits the target, but the loader has not resolved the assembled set.
- **Needs functional test:** loading would still not prove that the addon behaves correctly.
- **Unknown:** no 1.8 release statement or runtime result was found. Unknown components are preserved for testing unless they are proven blockers.

## Verified baseline and assembled target

| Item | Reference | Target | Evidence |
| --- | --- | --- | --- |
| Cobbleverse | 1.7.42 | upstream reference remains unchanged | local manifest and hash inventory |
| Minecraft | 1.21.1 | 1.21.1 | Cobblemon metadata and Fabric installer |
| Fabric Loader | ≥0.18.4 required | 0.19.5 stable | Fabric Meta queried 2026-09-08 |
| Fabric installer | — | 1.1.2 stable | Fabric Meta queried 2026-09-08 |
| Java | 21 | Temurin 21.0.9 | executed `java -version` |
| Cobblemon | 1.7.3+1.21.1 | 1.8.0+1.21.1 | local metadata and Modrinth version `YgmyyFcs` |
| Server jars | 104 baseline jars | 100 effective jars | `pack_manifest.py verify` and boot capture `20260910-124927` |
| Client jars | base client set | 135 effective jars | `pack_manifest.py plan` and assembled client launch |
| Config files | 223 base files | 224 assembled files | isolated runtime inventory |
| Datapacks | 10 zip files | 10 assembled zip files | isolated runtime inventory |

The immutable base verification found 104 matching server-side jars, zero missing, and zero hash mismatches. The 34 extras were exactly the 33 enabled client-only jars plus the disabled legacy Particular jar. The final target verification found all 100 planned server jars with zero missing, mismatched, extra, or unverified files. With Krypton provisionally excluded server-side and the riding-seat migration applied, that set reached `Done (1.276s)` with mod-set hash `62BEABD9398A`.

## Required compatibility overlay

| Component | Base | Target | Action | Why |
| --- | --- | --- | --- | --- |
| cobblemon | 1.7.3+1.21.1 | 1.8.0 | UPDATE | Target Cobblemon version for the campaign (1.8.0 Fabric, published 2026-09-06). Requires Fabric API (P7dR8mSH). |
| tmcraft | 1.4.18+1.7.3 | 1.4.19+1.8.0 | UPDATE | fabric.mod.json hard-pins cobblemon 1.7.3+1.21.1; 1.4.19+1.8.0 build exists (2026-09-06). |
| capture_xp | 1.7.3-fabric-1.3.0 | 1.8.0-fabric-1.3.0 | UPDATE | fabric.mod.json hard-pins cobblemon 1.7.3+1.21.1; 1.8.0 build exists (2026-09-08). Also requires Tim Core (lVP9aUaY). |
| tim_core | 1.7.3-fabric-1.32.0 | 1.8.0-fabric-1.32.0 | UPDATE | fabric.mod.json hard-pins cobblemon 1.7.3+1.21.1; 1.8.0 build exists (2026-09-08). Library for Capture XP. |
| rctmod | 0.18.1-beta | 0.19.0-beta | UPDATE | Radical Cobblemon Trainers 0.19.0-beta (2026-09-07) raises the minimum Cobblemon to 1.8. Loads on 1.8 only with this update. |
| rctapi | 0.15.2-beta | 0.16.0-beta | UPDATE | Paired RCT API release published 2026-09-06 alongside rctmod 0.19.0-beta; assumed required by rctmod 0.19.0 (verify at boot: rctmod's fabric.mod.json rctapi constraint). |
| mega_showdown | 1.8.4+1.7.3+1.21.1 | 1.0.2+1.8+1.21.1-release | UPDATE | Mega Showdown 1.0.2 for Cobblemon 1.8 (2026-09-08). Note the version scheme reset (1.8.4 -> 1.0.2); its required dependencies are present in the base pack. |
| cobbreeding | 2.2.2 | 2.3.0 | UPDATE | Release 2.3.0 explicitly updates Cobbreeding for Cobblemon 1.8. |
| obc | 1.3.0 | 1.5.0-fabric | UPDATE | Release 1.5.0-fabric explicitly targets Cobblemon 1.8 and is not backward-compatible. |
| playerxp | 1.0.9+1.21.1 | 1.1.1+1.21.1 | CLIENT OPTIONAL; SERVER EXCLUDE | No newer 1.21.1 release exists. Version 1.1.1 and current upstream source register client-only `ItemTooltipCallback` from the common `ModInitializer`, crashing a dedicated server during entrypoint initialization. Preserve in the client provisionally; connection safety and usefulness remain unverified. |
| cobblenav | 2.3.3 | 2.4.1 | UPDATE | CobbleNav 2.4.x explicitly updates for Cobblemon 1.8. |
| zamega | 1.7.3 | 1.7.7+1.8 | UPDATE | The base jar requires Mega Showdown's 1.7-era version range; release 1.7.7+1.8 targets the reset Mega Showdown 1.0.x line. |
| fightorflight | 0.10.9 | 0.11.0 | UPDATE | Maintained Reborn release reports normal operation on Cobblemon 1.8; preserve provisionally and verify aggression, fleeing, battle start, and XP behavior. |
| better_pokedex_scanner | better-pokedex-scanner-1.0.0.jar | — | REMOVE | Depends on cobblemon >=1.7.3 <1.8.0 and has no 1.8 build (single release 1.0.0, 2026-04-15). Client-side QoL; safe to drop. |
| particular | particular-1.1.2+1.21.jar.disabled | — | REMOVE | Already .disabled in the base pack; duplicate mod id with Particular Reforged 1.5.5 (particular-1.21.1-Fabric-1.5.5.jar). Drop the file entirely. |
| cobblemonraiddens | 0.11.3+1.21.1 | — | REMOVE | Runtime datapack reload fails with `NoSuchMethodError: GraalShowdownService.getContext()`. Published 0.11.7 and current upstream source retain the same removed API call. This also removes den blocks and structures before campaign world construction. |
| COBBLEVERSE-DP-v31 | 1.7 offset-based riding seats | generated runtime copy with 1.8 named locators | PATCH AT ASSEMBLY | The pack has 233 riding additions. For 51 native Cobblemon 1.8 mounts, old seats override the current model locators and leave the rendered rider detached. `tools/patch_cobbleverse_riding.py` copies the local licensed ZIP and replaces only those seats from the target Cobblemon JAR. It preserves custom riding stats and 182 Cobbleverse-only mounts. Mudsdale and Charizard pass in the client. |

All replacement downloads are pinned by URL, Modrinth version ID, SHA-1, and SHA-512 in `modpack/manifest/overlay.json`. The six replacements added by current research are Cobbreeding, Only Bottle Caps, PlayerXP, CobbleNav, ZAMegas, and Fight or Flight Reborn. ZAMegas is mandatory: the base jar requires the old Mega Showdown version line, while Mega Showdown resets to 1.0.x for Cobblemon 1.8.

**Client resource packs vs Cobblemon 1.8 models (2026-09-14): client crash, patched.**
- **Cause:** COBBLEVERSE RP ships Pokémon models built for Cobblemon 1.7. Where Cobblemon 1.8 poses a form with a built-in poser, a renamed or missing bone crashes the client on first render.
- **Seen:** Alolan Persian, `NoSuchElementException: Can't find part persian`.
- **Fix:** seven forms are flagged, and `cobblers-model-fixes.zip` restores Cobblemon's own models for them. The pack is built and installed with `tools/client_model_fix.py`.
- **Recheck** after every modpack, resource pack or Cobblemon update. The log and procedure are in [`CLIENT_MODEL_FIXES.md`](CLIENT_MODEL_FIXES.md).

## Client model audit, 2026-09-26: placeholder and mis-assembled Pokémon

**Report (owner, staging playtest, Cobblemon 1.8.0 client):**
- Some wild Pokémon render as Cobblemon's green substitute doll with "??? Lv.N" above them, including Vullaby and Oranguru.
- Others are mis-assembled, including Talonflame and Pidgeot.

**Instance audited:** the Modrinth profile `%APPDATA%/ModrinthApp/profiles/Fabric 1.21.10`. It is the only local client with `Cobblemon-fabric-1.8.0+1.21.1.jar`. Its `logs/latest.log` (2026-09-26) shows the campaign's habitat-pool ids, so it is the staging client.

The folder at `C:\Users\wnd\Documents\github\cobblers\COBBLEVERSE` is not this client. It still has Cobblemon 1.7.3 and has no `options.txt` or logs. It was used only as the 1.7.3 reference jar.

**Method:** read-only Python `zipfile` over the jars, the resource packs, `options.txt` and `config/`, plus `javap` over classes extracted from the Cobblemon 1.8.0 jar. Nothing was executed and nothing in the client was changed.

**How the stack was rebuilt:**
- Layers come from the `options.txt` `resourcePacks` order: mod jars under `fabric`, built-in mod packs, then the `file/` packs.
- Asset ids are resolved the way `VaryingModelRepository` resolves them.
- The rebuild reproduces the client's own load counts exactly: 1,583 model registrations and 1,284 animation groups (`latest.log`: "Loaded 1583 models", "Loaded 13919 animations from 1284 animation groups").

### VERIFIED: mechanism (Cobblemon 1.8.0 bytecode)

- **Substitute fallback:** `VaryingModelRepository.getPoser` looks up the species' resolver in `variations`. If there is none, or the resolver throws `IllegalStateException` (no matching variation, or a missing poser, model or texture), it returns the resolver named by the `fallback` field, whose constant is `substitute`. That is the green doll.
- **Last match wins:** `VaryingRenderableResolver.getVariationValue` walks the variation list from the end and takes the last variation that `fits` the aspects and has the field set.
- **Models and posers are keyed by file name:** the id is the file name without its extension (`FilesKt.getNameWithoutExtension`), stored with `Map.put`.
- **Animation groups are keyed by file name without a namespace:** the id is `substringAfterLast('/')` minus `.animation.json`, stored with `Map.put`.
- **Consequence of file-name keys:** a pack file at a *different* path with the same file name replaces Cobblemon's.
  - Example: CobbleMotion's `posers/talonflame.json` replaces 1.8's `posers/0663_talonflame/talonflame.json`.
  - Pack priority applies only when the paths are identical.
- **"???" is not an error:** `PokemonRenderer` reads `displayNameForUnknownPokemon`, which is `false` in the client's `config/cobblemon/main.json`. The lang tooltip reads "Whether to display the name above a Pokémon if it has not been scanned with the Pokédex yet." Any unscanned species shows "???".

### VERIFIED: cause 1, substitute doll (40 species with no client resolver)

**Log:** there is no model, poser or resolver error. The substitute fallback is silent.

**Why the 40 species have no assets:**
- Cobblemon 1.8.0 ships species data for all 40 species but no client assets (no resolver, model, poser or texture). For example, `data/cobblemon/species/generation5/vullaby.json` is present and nothing under `assets/cobblemon/bedrock/pokemon/**/vullaby*` is.
- `COBBLEVERSE-DP-v31.zip` (`data/cobblemon/species_additions/*.json`, `implemented: true`) enables all 40 and gives them spawn pools.
- Among resource packs, only `ATMxMSD RP.zip` supplies their resolvers, models, posers, animations and textures.

**Why that pack is off:**
- `ATMxMSD RP.zip` is not in the client's `resourcePacks`.
- It was removed on purpose by our overlay `modpack/config/resourcepackoverrides.json`, which is identical to the client's `config/resourcepackoverrides.json` apart from whitespace.
- Base Cobbleverse lists it at line 33 of `base-pack/cobbleverse/config/resourcepackoverrides.json`.
- The reason for removing it (see the ATMxMSD row below): its Mega Mewtwo resolver broke the first 1.8 resource reload.
- The side effect was not recorded: those 40 species lost their only client assets.

**Every species in the server data now has a client resolver except these 40, and all 40 are spawnable:**
arctibax, blacephalon, bombirdier, brutebonnet, buzzwole, charjabug, fluttermane, frigibax, gougingfire, greattusk, greavard, grubbin, gulpin, guzzlord, houndstone, ironbundle, ironcrown, ironmoth, ironthorns, irontreads, ironvaliant, jirachi, manaphy, mandibuzz, nihilego, oranguru, passimian, pecharunt, pheromosa, phione, ragingbolt, roaringmoon, sandyshocks, screamtail, slitherwing, stakataka, swalot, vikavolt, vullaby, xurkitree.

**Eleven of them are in the campaign's own encounter tables (`data/spawns.json`):**

| Species | Where |
| --- | --- |
| vullaby | plateau_west; the elder_wedge_south_1 habitat; three desert saplings |
| mandibuzz | plateau_west |
| oranguru, passimian | jungle_east |
| gulpin, swalot | marshy_marsh |
| charjabug, grubbin, vikavolt | long_isle_south |
| greavard | the Route 1 ghost mansion; the Displaced City cavern |
| bombirdier | the elder_marshy_marsh_2 habitat |

**Re-enabling `ATMxMSD RP.zip` as a whole is not the fix.** Simulated at its Cobbleverse position, it would:
- add the 40 species;
- take over 89 species that Cobblemon 1.8 already covers. For those it replaces 1.8's resolvers, and for most also the models, posers and textures, with 1.7-era files. Examples: lucario, growlithe, arcanine, the legendary birds, mewtwo.
- break two resolvers again:
  - mewtwo: `MODEL_MISSING cobblemon:mewtwo_mega_x.geo` and `…mega_y.geo`, plus `POSER_MISSING`;
  - greninja: `POSER_MISSING cobblemon:ashgreninja`.

**A subset pack is clean.** The 40 species need 223 files from ATMxMSD, and none of their ids collide with the current stack. The only exceptions are the `screamtail` and `ironcrown` model paths, which COBBLEVERSE RP also ships; its models there match ATMxMSD's texture layout 100%.

### VERIFIED: cause 2, mis-assembled models (file-level; visuals verified only for Talonflame and Pidgeot)

**What goes wrong:** a pack model is combined with a texture drawn for a different model. The texture test compares normalized cube UV rectangles between models: the result is bimodal, 296 pack models at 95% or more and 35 below 20%.

**Class A, 1.8 remodel regression.** COBBLEVERSE RP overrides the model at the same path. Its UV layout matches Cobblemon 1.7.3's model 100%. Cobblemon 1.8 remodelled the species (0–20% of 1.7.3's UV rectangles kept) and redrew the texture, so the old model now wears the new texture.

| Form | Evidence |
| --- | --- |
| **pidgeot** | pack UV = 1.7.3; 1.8 texture 256×256 (1.7.3: 128×128); 28 animated bones absent from the pack model |
| **talonflame** | pack UV = 1.7.3; 1.8 texture 128×128 (1.7.3: 128×64); poser and animations are CobbleMotion's (`posers/talonflame.json`, `animations/talonflame/…`), shadowing 1.8's by file name |
| arbok | 1.8 texture 128×128 vs 1.7.3 128×64 |
| crobat, cofagrigus, skarmory, tyranitar | UV 0–1% of the 1.8 texture's model |
| garganacl, goodra, primarina | 1.8 textures widened to 256×128 |
| nidoking | 1.8 texture 256×256 (1.7.3: 128×128) |
| goodra (hisuian), samurott (hisuian) | UV 0% and 20% of the 1.8 texture's model |
| turtonator | 1.8 texture 256×256 (1.7.3: 256×128) |
| appletun, archaludon | species new to Cobblemon 1.8's models; COBBLEVERSE RP's model shares 0% of the 1.8 texture's UV |

**CobbleMotion also shadows the 1.8 poser and animation group** for talonflame, goodra, goodra (hisuian), nidoking, primarina, samurott (hisuian) and tyranitar.

**Class B, female forms (beautifly, dustox).** COBBLEVERSE RP replaces the whole species set: resolver, model, poser, animations and texture. Cobblemon 1.8 adds a separate `resolvers/…/1_<species>_female.json` that sets only `model: <species>_female.geo`, a model new in 1.8. Females therefore get the 1.8 model with COBBLEVERSE RP's texture and poser: texture 128×128 on a 64×128 or 128×64 UV space, and 11 of 13 or 6 of 7 animated bones absent.

**Special forms with the same defect:** pidgeot (mega), skarmory (mega) and appletun (gmax) inherit the Class A model. Mega and gmax cases where the Mega Showdown texture or poser does not fit a COBBLEVERSE RP model: altaria, manectric, slowbro, sceptile, blaziken, clefable and gengar (mega).

**The 2026-09-14 check could not catch this.** `tools/client_model_fix.py scan` exits 0 on this instance. Its rule only covers the crash class (a built-in poser missing a part), not texture/UV or JSON-poser mismatches.

### Weaker file evidence (NEEDS FUNCTIONAL TEST; visible effect not verified)

**Animation mismatch.** The effective animations animate at least 5 bones (and at least 20% of those animated) that are absent from the effective model, beyond the 1.8-only baseline of the same form.
- Expected effect (ASSUMED): stiff or unanimated parts, not broken textures.

| Species | Source of the mismatched poser/model |
| --- | --- |
| eevee, jolteon, leafeon, vaporeon | EeveelutionsReimagined posers |
| gliscor, sceptile, typhlosion | CobbleMotion |
| aggron, lairon | HydroReanimodel |
| sudowoodo | OJsAnimations |
| probopass | COBBLEVERSE RP model |

**Missing root bone.** The JSON poser's `rootBone` is absent from the model, and a JSON poser falls back rather than crashing (see `CLIENT_MODEL_FIXES.md`).
- Affected: muk (alolan), typhlosion (hisuian), samurott (hisuian), dartrix and dewott (region-bias-hisui), hakamoo, jangmoo, scrafty, mr. mime (galarian), mr. rime.

### Recommended fix (client only; the server is not involved)

**Why only the client:** resolvers, models, posers, animations and textures are client assets. The server's only role is that it spawns these species, which is correct.

**Two ways to hide the problem on the server, not recommended:** suppress the 40 species, or drop `implemented: true` from `COBBLEVERSE-DP-v31`. Either removes campaign encounters.

**Every player's client needs the same fix.**

1. **Do not re-enable `ATMxMSD RP.zip`.**
   - Build a local-only subset pack from the installed zip, for example `cobblers-missing-mons.zip`, holding only the 223 files for the 40 species above.
   - Enable it just below COBBLEVERSE RP, which is Cobbleverse's intended relative order for screamtail and ironcrown.
   - It is never committed, because it holds ATMxMSD assets.
2. **Extend `cobblers-model-fixes.zip`, which stays at the top of the list:**
   - Class A: Cobblemon 1.8's own `.geo.json` at COBBLEVERSE RP's model path, for all 16 forms.
   - The seven CobbleMotion-shadowed forms: also Cobblemon 1.8's poser JSON at CobbleMotion's poser path (e.g. `posers/talonflame.json`) and 1.8's animation file at CobbleMotion's animation path (e.g. `animations/talonflame/talonflame.animation.json`). Restoring only the model would leave CobbleMotion's old-bone animations on the new model.
   - Class B: shadow `resolvers/0267_beautifly/1_beautifly_female.json` and `resolvers/0269_dustox/1_dustox_female.json` with a resolver that has an empty `variations` list. Females then use COBBLEVERSE RP's unisex set.
     - The alternative is to restore Cobblemon's full beautifly and dustox sets.
     - ASSUMED: a resolver with no variations is accepted. Test it.
   - **The trade:** these forms show Cobblemon 1.8's look instead of COBBLEVERSE RP's or CobbleMotion's.
3. **Build both packs with a tool, not by hand.** `tools/client_model_fix.py` needs two more rules:
   - spawnable species with no client resolver;
   - a model whose UV layout does not match the model its texture was drawn for.
   Rebuild and rescan after every pack or Cobblemon update. The prototype audit scripts are not in the repository.
4. **Verify in game, then record the incident** in `CLIENT_MODEL_FIXES.md`.
   - Restart the client and spawn vullaby, oranguru, pidgeot and talonflame in a singleplayer test world.
   - Spot-check the weaker-evidence forms before deciding whether to patch them.
5. **Once proven, ship it to all players.** The modpack overlay should carry the build step. `modpack/config/README.md` should also state what disabling ATMxMSD costs.

### Not verified

- The rendered result of any fix, and every form except Talonflame and Pidgeot (reported by the owner).
- Minecraft's `listResources` ordering.
  - ASSUMED: sorted by id. It decides which of two same-named files at different paths wins.
  - The client's registration counts match this model exactly, but the ordering itself was not read from Minecraft's code.
- Resolver ordering when two resolver files share an `order` (ASSUMED: stable in listing order).
- That ATMxMSD's 1.7-era JSON posers for the 40 species animate correctly under 1.8 (NEEDS FUNCTIONAL TEST).
- That the staging server loads the same `COBBLEVERSE-DP-v31` as the client's `datapacks/` folder. The server directory was not read.
- Whether Resource Pack Overrides reorders packs at launch. `options.txt` already has the fix pack on top.

## Preserved systems requiring functional tests

The retained functional scope contains 26 Cobblemon-integrating addons and libraries after removing Raid Dens. PlayerXP is client-optional and needs a client connection test before it can be kept safely. Server boot cannot validate PlayerXP, Catch Indicator, Catch Rate Display, or LumyREI. High-risk server checks include RCT trainer lifecycle and multiplayer behavior, Mega Showdown plus ZAMegas, CobbleNav, Cobbreeding, CobbleDollars, Capture XP, TMCraft, and world-critical CobbleFurnies/LumyMon/Legendary Monuments/Cobblemon Additions.

No standalone quest system was found. Cobbleverse progression behavior comes from RCT series and level-cap configuration, datapack advancements/functions, and badge items. Global Packs force-loads `config/cobbleverse`, `datapacks/`, and optional `datapacks/extra/`; these are part of the compatibility surface.

## Complete mod matrix

This matrix covers all 138 jar records, including the disabled legacy Particular jar. `GAMEPLAY-CRITICAL / LIBRARY` means the jar is infrastructure required by another gameplay or world component.

| Component | Type | Current Version | Minecraft Version | Loader | Cobblemon Dependency | 1.8 Status | Action | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Advancement Plaques | OPTIONAL/CLIENT-QOL | 1.6.8 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only advancement toast visuals. Needs Iceberg. CC BY-NC-ND. |
| BadOptimizations | OPTIONAL/CLIENT-QOL | 2.4.1 | >=1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only perf. |
| BetterF1 | OPTIONAL/CLIENT-QOL | 1.1 | ~1.21 | Fabric | — | NEEDS BOOT TEST | CLIENT ONLY | ODD: jar named +1.21.7 but depends minecraft ~1.21 (any 1.21.x). Built against a newer MC; client mixin may not apply cleanly on 1.21.1. No source/contact in metadata. |
| BetterF3 | OPTIONAL/CLIENT-QOL | 11.0.3 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only debug HUD. |
| Better Third Person | OPTIONAL/CLIENT-QOL | 1.9.0 | ~1.21 | Fabric | — | LIKELY WORKING | CLIENT OPTIONAL | Client-only camera. Disabling it did not change the EXP-009 riding failure, so it is not the observed cause. ARR. |
| Carved Wood | WORLD-CRITICAL | 1.9.7-B | >=1.21 <1.22 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 325 blockstates of decorative wood blocks; if used in the handcrafted map it must stay. Bundles cardinal-components. Contact points at fabric-example-mod template (no real source URL). |
| CobbleDollars | GAMEPLAY-CRITICAL | 2.0.0+Beta-5.1+1.21.1 | >=1.21.1 | Fabric | >=1.6.0+1.21.1 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Currency + merchant NPCs (villager template pools). cobblemon >=1.6.0+1.21.1 (no upper bound). 55 classes reference Cobblemon API. ARR. |
| CobbleFurnies | WORLD-CRITICAL | 1.2 | ~1.21.1 | Fabric | >=1.7.1 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | 372 blockstates of Pokemon-themed furniture (labs, Pokecenters). Hard-required by LegendaryMonuments. cobblemon >=1.7.1, athena >=4.0.2, architectury >=13.0.8. 8 classes touch Cobblemon API. |
| Cobblemon | GAMEPLAY-CRITICAL | 1.7.3+1.21.1 | 1.21.1 | Fabric | — | NEEDS BOOT TEST | UPDATE → 1.8.0 | Core mod 1.7.3+1.21.1. Target per task premise is 1.8.x. Bundles fabric-language-kotlin nested. Requires fabricloader >=0.17.2, fabric-api >=0.116.6+1.21.1, Java 21. |
| COBBLEVERSE Badges | GAMEPLAY-CRITICAL | 1.3 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Gym badges/trophies items (Kanto-Sinnoh) - progression items. No cobblemon dependency declared, 0 API refs (pure items). Pack-specific Lumyverse mod, CC BY-NC-ND 4.0 (no-derivatives; distribution outside the pack is license-sensitive). Once given to players they persist in inventories. |
| Cobbreeding | GAMEPLAY-CRITICAL | 2.2.2 | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | UPDATE → 2.3.0 | Breeding via pasture. cobblemon >=1.7.0 (no upper bound). Overrides cobblemon pasture blockstate. architectury 13.x, cloth-config >=15. 40 API refs - high coupling. |
| Controlling | OPTIONAL/CLIENT-QOL | 19.0.5 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only keybind search. Needs Searchables. |
| Debugify | OPTIONAL/CLIENT-QOL | 1.21.1+1.0 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Vanilla bug fixes; env=* (has server-side fixes). |
| Euphoria Patcher | OPTIONAL/CLIENT-QOL | 1.9.3-r5.8.1-fabric | >=1.14.0 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; patches Complementary shaders (shaderpacks/ComplementaryUnbound_r5.8.1). |
| Forge Config API Port | GAMEPLAY-CRITICAL / LIBRARY | 21.1.6 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: sophisticatedcore (>=21.1.3), rctmod (>=21.1.1), particular (Reforged). |
| Iceberg | GAMEPLAY-CRITICAL / LIBRARY | 1.3.2 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: advancementplaques. CC BY-NC-ND. |
| ImmediatelyFast | OPTIONAL/CLIENT-QOL | 1.6.11+1.21.1 | >=1.21 <=1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only render perf. minecraft >=1.21 <=1.21.1. |
| Iron Chests | GAMEPLAY-CRITICAL | 2.0.4 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Storage blocks players keep items in (10 blockstates). Bundles libgui. |
| Legendary Monuments | WORLD-CRITICAL | Cobbleverse | ~1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Worldgen structures + 48 blockstates (shrines, Giratina island, etc.) for legendary encounters. version='Cobbleverse' = pack-custom build; no public source (template contact). Hard-depends cobblefurnies * and cobblemon >=1.7.0. 6 API refs. |
| Cozy Home | WORLD-CRITICAL | 1.1.20 | ~1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 278 blockstates furniture. Template contact (no real source). |
| LumyMon | WORLD-CRITICAL | 0.6.6 | ~1.21.1 | Fabric | >=1.7.1 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Pack-specific Lumyverse mod: worldgen + structures + 64 blockstates + custom mechanics (17 API refs). cobblemon >=1.7.1 (no upper). Bundles fabric-permissions-api. CC BY-NC-ND 4.0 - license-sensitive to carry forward. Also GAMEPLAY-relevant. |
| LumyREI | OPTIONAL/CLIENT-QOL | 1.1.3 | ~1.21.1 | Fabric | >=1.7.1 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Client-only REI recipe integration (cooking pot/brewing/stark forge). cobblemon >=1.7.1. GPL-3.0. |
| MobsBeGone | GAMEPLAY-CRITICAL | 0.0.7 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Server-side entity spawn blacklist; config/mobsbegone-blacklist.json lists most vanilla mobs (allay..giant..) - defines the campaign's mob roster. Keep mod + config together. ARR/Custom, modpack permission on file. |
| MoreCobblemonTweaks | OPTIONAL/CLIENT-QOL | 1.3.3 | ~1.21 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Cobblemon client QoL (PC multiselect, egg lore). cobblemon >=1.7.0, architectury >=13.0.8. 30 API refs (UI-level coupling - likely to break on UI changes). GPL-3.0. |
| Mouse Tweaks | OPTIONAL/CLIENT-QOL | 2.26 | ~1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only. |
| No Chat Restrictions | OPTIONAL/CLIENT-QOL | Fabric-MC1.21.11-v1.0.0 | >=1.21 <=1.21.11 | Fabric | — | NEEDS BOOT TEST | PRESERVE FOR BOOT | ODD: built for MC 1.21.11 (depends >=1.21 <=1.21.11 so it will load on 1.21.1). Mixins were compiled against 1.21.11 - verify they apply. Purpose: removes chat signing restrictions. |
| Only Bottle Caps | GAMEPLAY-CRITICAL | 1.3.0 | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | UPDATE → 1.5.0-fabric | Bottle cap items (IV training). cobblemon >=1.7.0. No fabricloader dep declared. Bundles supermartijn642configlib. |
| Ping Wheel | OPTIONAL/CLIENT-QOL | 1.12.2 | >=1.21 <=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Location pings; needs server side too (env=*). |
| Platform | GAMEPLAY-CRITICAL / LIBRARY | 1.3.3 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: vanillabackport (>=1.3.3). Contains worldgen helper classes. |
| Resource Pack Overrides | OPTIONAL/CLIENT-QOL | 21.1.0 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; forces pack resource packs active (config/resourcepackoverrides.json). |
| Roughly Enough Items | OPTIONAL/CLIENT-QOL | 16.0.799 | ~1.21- | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Recipe viewer. env=* (server side for recipe sync). Bundles error_notifier. |
| Safe Pastures | GAMEPLAY-CRITICAL | 1.1.1+1.21.1 | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Pasture protection. cobblemon >=1.7.0. 1 API ref (low coupling). |
| ScalableLux | OPTIONAL/CLIENT-QOL | 0.1.0.1+fabric.d0d58ab | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Light engine rewrite (provides starlight). Server+client perf. |
| Searchables | GAMEPLAY-CRITICAL / LIBRARY | 1.0.2 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Needed by: controlling. Client-only. |
| StackDeobfuscator | DEVELOPMENT-ONLY | 1.4.3+08e71cc | >=1.14-alpha.18.49.a | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Deobfuscates stack traces in logs; useful while debugging the 1.8 migration, not needed by players. |
| VanillaBackport | WORLD-CRITICAL | 1.1.7.10 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Backports newer vanilla content: 72 blockstates + worldgen/biomes/structures (terrablender entrypoint). Anything built with these blocks persists. Needs Platform. ARR. Bundles mixinsquared. |
| Accessories | GAMEPLAY-CRITICAL / LIBRARY | 1.1.0-beta.53+1.21.1 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: mega_showdown (>=beta.52), zamega, accessories_compat_layer. Needs owo. Beta build. |
| Accessories Compatibility Layer | GAMEPLAY-CRITICAL / LIBRARY | 0.1.12 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Bridges Trinkets/Curios APIs onto Accessories (provides tclayer/cclayer). Needed only if any mod uses Trinkets API; nothing in this pack hard-depends on trinkets. |
| AdvancementDisable | OPTIONAL/CLIENT-QOL | 1.0.0 | 1.21.x | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Disables mod advancements. Check config/advancementdisable.toml. |
| Architectury | GAMEPLAY-CRITICAL / LIBRARY | 13.0.8 | ~1.21- | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: cobblefurnies, cobbreeding, more_cobblemon_tweaks, fightorflight, mega_showdown, rctapi, zamega, brb. Version 13.0.8 is exactly the minimum several mods require. |
| Athena | GAMEPLAY-CRITICAL / LIBRARY | 4.0.6 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: cobblefurnies (>=4.0.2). Client entrypoint only. |
| Balm | GAMEPLAY-CRITICAL / LIBRARY | 21.0.63 | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: waystones, defaultoptions, forgivingvoid, netherportalfix. Bundles kuma_api. |
| Beautify | WORLD-CRITICAL | 2.0.0+1.21.1 | ~1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 57 decorative blockstates (blinds, trellis, frames). Needs cloth-config. |
| Better Pokédex Scanner | OPTIONAL/CLIENT-QOL | 1.0.0 | 1.21.1 | Fabric | >=1.7.3 <1.8.0 | INCOMPATIBLE | REMOVE | HARD BLOCKER: depends cobblemon ">=1.7.3 <1.8.0" - loader will refuse to start with Cobblemon 1.8.x until a new build exists. Also needs fabric-language-kotlin >=1.13.6. Small QoL (aspect detection in scanner) - candidate for REMOVE if no 1.8 build. |
| Better Beds | OPTIONAL/CLIENT-QOL | 1.4.0 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only bed renderer. |
| Biome Replacer | WORLD-CRITICAL | 2.1-hippo | >=1.19.4 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Replaces biomes at generation (config/biome_replacer.properties). Changing/removing it changes terrain of newly generated chunks - must be frozen for the map. minecraft >=1.19.4 <1.21.2. |
| Better Recipe Book | OPTIONAL/CLIENT-QOL | 1.10.0-rc5+1.21 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only recipe book tweaks. Needs architectury >=11. |
| Concurrent Chunk Management Engine | OPTIONAL/CLIENT-QOL | 0.4.0-alpha.0.23+1.21.1 | ["=1.21.1", "=1.21"] | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Chunk perf (alpha). 28 nested jars. Requires fabricloader >=0.18.3. Touches worldgen threading - verify chunk output identical before generating the map. |
| Cobblemon Capture XP | GAMEPLAY-CRITICAL | 1.7.3-fabric-1.3.0 | 1.21.1 | Fabric | 1.7.3+1.21.1 | NEEDS FUNCTIONAL TEST | UPDATE → 1.8.0-fabric-1.3.0 | HARD BLOCKER: depends cobblemon "1.7.3+1.21.1" (exact pin; Fabric treats a bare version as equality) and tim_core >=1.7.3-fabric-1.31.0. Will not load with 1.8.x without a new build. |
| Catch Indicator | OPTIONAL/CLIENT-QOL | 1.7.0 | 1.21.1 | Fabric | — | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Client-only Pokedex status indicator. Does NOT declare a cobblemon dependency but 13 classes reference com.cobblemon API (incl. Alphas/SizeVariation compat) - silent runtime breakage risk. ARR + permission. |
| Cobblemon Catch Rate Display | OPTIONAL/CLIENT-QOL | 2.8.22 | >=1.21 <1.22 | Fabric | >=1.6.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Client-only catch-rate HUD. cobblemon >=1.6.0, breaks <1.6.0. 19 API refs. |
| Cloth Config v15 | GAMEPLAY-CRITICAL / LIBRARY | 15.0.140 | >=1.21- | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: cobbreeding, fightorflight, beautify, moreculling, musicnotification, nethermap, paginatedadvancements, soundsbegone, toms_storage, brb, betterf3 (several also bundle it nested). |
| CobbleCuisine | GAMEPLAY-CRITICAL | 2.0.1 | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Food/snack items + bean crop block. cobblemon >=1.7.0. 22 API refs. Jar name says '1.7.rc1' (built for Cobblemon 1.7). |
| Cobblemon Additions | WORLD-CRITICAL | 4.1.6 | ~1.21.1 | Fabric | — | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Pokemon-themed villages/structures (datapack-turned-mod), spawn pools. No cobblemon dependency declared but ships assets/cobblemon + spawn_pool data and 2 API refs. Worldgen: villages will be in the map. CC0. |
| Cobblemon Battle Extras | OPTIONAL/CLIENT-QOL | 1.13.45 | ~1.21.1 | Fabric | >=1.6 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Battle UI/QoL + controller support. cobblemon >=1.6. 74 API refs (battle UI coupling - high break risk). Breaks cobblemon-ui-tweaks/cobblestats/move_inspector. ARR, permission on file. |
| Cobblemon Battle Positions | GAMEPLAY-CRITICAL | 1.1.2 | ~1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Arena marker blocks (5 blockstates) placed in world for NPC/PVP battle positions - blocks persist in map. cobblemon >=1.7.0, rctapi >=0.14.0. Jar says 1.1.3, metadata version 1.1.2. |
| Cobblemon Raid Dens | WORLD-CRITICAL / GAMEPLAY-CRITICAL | 0.11.3+1.21.1 | 1.21.1 | Fabric | >=1.7.0 | INCOMPATIBLE | REMOVE | Fatal on Cobblemon 1.8 during datapack reload: `NoSuchMethodError` for removed `GraalShowdownService.getContext()`. Latest published 0.11.7 and current source retain the call. Removing before map construction avoids orphaned den blocks and structures. |
| Cobblenav | GAMEPLAY-CRITICAL | 2.3.3 | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | UPDATE → 2.4.1 | PokeNav item (spawn info/trainer contacts). cobblemon >=1.7.0. 191 API refs (very high coupling). MPL-2.0. |
| Comforts | WORLD-CRITICAL | 9.0.5+1.21.1 | ~1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Sleeping bags/hammocks - placeable blocks (34 blockstates). Bundles spectrelib + cardinal-components. |
| Configurable | GAMEPLAY-CRITICAL / LIBRARY | 3.5.2 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: neruina (~3.5.2). |
| Continuity | OPTIONAL/CLIENT-QOL | 3.0.0+1.21 | >=1.21 <=1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only connected textures. |
| Custom Splash Screen | OPTIONAL/CLIENT-QOL | 2.2.0 | — | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; no minecraft dep declared. Needs midnightlib. |
| Default Options | OPTIONAL/CLIENT-QOL | 21.1.7 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Ships default keybinds/options (config/defaultoptions). Needs balm. ARR. |
| Entity Model Features | OPTIONAL/CLIENT-QOL | 3.2.4 | * | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only CEM support; minecraft '*'. Needs ETF >=7.1. Used by Fresh Animations resource pack. |
| Entity Texture Features | OPTIONAL/CLIENT-QOL | 7.1 | * | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; minecraft '*'. |
| EntityCulling | OPTIONAL/CLIENT-QOL | 1.10.5 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Client perf (env=* but client entrypoint only). tr7zw protective license. |
| Fabric API | GAMEPLAY-CRITICAL / LIBRARY | 0.116.14+1.21.1 | >=1.21- <1.21.2- | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Fabric API 0.116.14+1.21.1 (49 modules). Cobblemon 1.7.3 requires >=0.116.6. |
| Fabric Language Kotlin | GAMEPLAY-CRITICAL / LIBRARY | 1.13.13+kotlin.2.4.10 | — | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Kotlin 2.4.10. Needed by: cobblemon (also nests its own copy), catchrate-display, better_pokedex_scanner (>=1.13.6+kotlin.2.2.20), fzzy_config, particle_core, zoomify (>=1.13.8), cobblemon-additions. |
| FancyMenu | OPTIONAL/CLIENT-QOL | 3.9.8 | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Custom menus (config/fancymenu). env=* but cosmetic. Needs konkrete, melody. DSMSL license. |
| FerriteCore | OPTIONAL/CLIENT-QOL | 7.0.3 | >=1.21.1 <1.22 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Memory perf, server+client. |
| Cobblemon Fight or Flight Fabric | GAMEPLAY-CRITICAL | 0.10.9 | 1.21.1 | Fabric | >=1.7.2 | NEEDS FUNCTIONAL TEST | UPDATE → 0.11.0 | Wild Pokemon attack/flee behaviour. cobblemon >=1.7.2, architectury, cloth-config. 83 API refs (high coupling). |
| Forgiving Void | OPTIONAL/CLIENT-QOL | 21.1.7 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Void fall teleport rule. Needs balm. ARR. |
| Fusion | GAMEPLAY-CRITICAL / LIBRARY | 1.2.12 | >=1.21 <1.22 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: rechiseled (>=1.2.12). Connected-texture lib. ARR. |
| Fzzy Config | GAMEPLAY-CRITICAL / LIBRARY | 0.7.6+1.21 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: particle_core (>=0.7.5). Requires fabric-language-kotlin. |
| GeckoLib 4 | GAMEPLAY-CRITICAL / LIBRARY | 4.9.2 | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: cobblemonraiddens (>=4.7.0), pokeblocks (>=4.7.3). fabricloader >=0.17. |
| Global Data- & Resourcepacks | GAMEPLAY-CRITICAL | 21.0.6 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | PACK INFRASTRUCTURE: config/global_packs.toml force-loads datapacks/ (required), datapacks/extra/ (optional: Hoenn/Johto/Sinnoh region DPs + Terralith-DP) and config/cobbleverse as a required resourcepack. Without it the COBBLEVERSE-DP-v31 / Loot / RCT datapacks are not applied. ARR. Metadata description is the template placeholder. |
| Handcrafted | WORLD-CRITICAL | 4.0.3 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 268 blockstates furniture. Needs resourcefullib >=3.0.0. Terrarium license. |
| Highlight | OPTIONAL/CLIENT-QOL | 3.0.0 | >=1.20.5 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Block selection outline shapes. Bundles resourcefullib. |
| Huge Structure Blocks | DEVELOPMENT-ONLY | 1.1.6 | >=1.21 <=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Bigger structure blocks - map-building tool. Keep while building the map; if huge structure blocks are left in the world, removing the mod would delete them (verify before removal). |
| Infinite Music | OPTIONAL/CLIENT-QOL | 0.4.6 | — | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; no minecraft dep declared. |
| Interactic | OPTIONAL/CLIENT-QOL | 0.2.3+1.21 | >=1.20.3 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Item throw/pickup animations (env=*). Needs owo. Bundles owo-sentinel. |
| Iris | OPTIONAL/CLIENT-QOL | 1.8.14-beta.1+mc1.21.1 | ["1.21.1"] | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only shaders; requires sodium 0.8.x. Beta build. |
| Konkrete | GAMEPLAY-CRITICAL / LIBRARY | 1.9.9 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: fancymenu (>=1.9.4). |
| Krypton | OPTIONAL/CLIENT-QOL | 0.2.8 | >=1.21 | Fabric | — | NEEDS FUNCTIONAL TEST (SERVER) | CLIENT OPTIONAL; PROVISIONAL SERVER EXCLUDE | Removing it server-side restored authoritative mount/player position synchronization, but the rider still rendered detached until the Cobbleverse datapack seats were migrated. Keep the tested server exclusion for now; isolate it again after broader mount sampling before declaring Krypton incompatible. Client Krypton was restored and is present in the successful test. |
| Lenient Death | OPTIONAL/CLIENT-QOL | 1.2.5+1.21.1 | >=1.20.5 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Server-side death-item rules (config/lenientdeath.json5) - a gameplay rule, not Cobblemon-coupled. Bundles jackfredlib + fabric-permissions-api. |
| LibJF | GAMEPLAY-CRITICAL / LIBRARY | 3.17.5 | * | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: respackopts (libjf-base/config-core-v2/data-manipulation). 12 nested modules. |
| Lithium | OPTIONAL/CLIENT-QOL | 0.15.4+mc1.21.1 | ["1.21", "1.21.1"] | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Server+client perf. |
| Cobblemon:Mega Showdown | GAMEPLAY-CRITICAL | 1.8.4+1.7.3+1.21.1 | ~1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | UPDATE → 1.0.2+1.8+1.21.1-release | Mega Evolution/Z-moves/Tera/Dynamax + 34 blockstates (keystone ore, meteorite - world-persistent) + worldgen + 28 species files. cobblemon >=1.7.0, accessories >=beta.52, architectury. 163 API refs. NOTE: '1.8.4' is MSD's own version, NOT Cobblemon 1.8. Jar name pins '+1.7.3'. Custom MSD license. |
| Melody | GAMEPLAY-CRITICAL / LIBRARY | 1.0.10 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: fancymenu (>=1.0.6). Audio lib. |
| MidnightLib | GAMEPLAY-CRITICAL / LIBRARY | 1.7.5 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: repurposed_structures (>=1.5.7), customsplashscreen (also nested there). |
| Moar Concrete | WORLD-CRITICAL | 1.3.1 | ~1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 178 concrete-variant blockstates. Template contact. |
| ModernFix | OPTIONAL/CLIENT-QOL | 5.25.1+mc1.21.1 | >=1.16.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Perf, server+client. |
| Mod Menu | OPTIONAL/CLIENT-QOL | 11.0.4 | >=1.21-beta.2 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only. |
| More Culling | OPTIONAL/CLIENT-QOL | 1.0.8 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; sodium >=0.6.7 required by breaks rule. Needs cloth-config. |
| MusicNotification | OPTIONAL/CLIENT-QOL | 3.0.0 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; no fabricloader dep declared. |
| Neruina | OPTIONAL/CLIENT-QOL | 3.3.3 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Ticking-entity crash guard (server+client). Needs configurable ~3.5.2. Bundles github-api (auto-report). |
| Better Nether Map | OPTIONAL/CLIENT-QOL | 4.0.0-1.21.1 | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Maps in nether. Needs cloth-config2. |
| NetherPortalFix | OPTIONAL/CLIENT-QOL | 21.1.3 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Server-side portal linking. Needs balm. ARR. |
| NotEnoughAnimations | OPTIONAL/CLIENT-QOL | 1.12.4 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT OPTIONAL | Client animations (env=*, client entrypoint). Disabling it did not change the EXP-009 riding failure, so it is not the observed cause. tr7zw protective license. |
| Not Enough Crashes | OPTIONAL/CLIENT-QOL | 4.4.9+1.21.1 | >=1.17 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Crash handling. Sodium breaks <4.4.8 (ok at 4.4.9). |
| oωo | GAMEPLAY-CRITICAL / LIBRARY | 0.12.15.4+1.21 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: accessories (>=0.12.15.1), accessories_compat_layer (>=0.12.15.4), interactic (>=0.11.3), particular 1.1.2 (disabled). |
| Packet Fixer | OPTIONAL/CLIENT-QOL | 3.3.1 | >=1.20.5 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Raises packet/NBT size limits - useful for large Cobblemon PC/NBT payloads on servers. minecraft >=1.20.5, fabricloader '*'. |
| Paginated Advancements | OPTIONAL/CLIENT-QOL | 2.5.1 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only advancement screen. Needs cloth-config. |
| Particle Core | OPTIONAL/CLIENT-QOL | 0.3.3+1.21 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only particle perf. Needs fzzy_config, kotlin. |
| Particle Rain | OPTIONAL/CLIENT-QOL | 4.0.0-beta.10 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only weather particles (beta). |
| Particular | OPTIONAL/CLIENT-QOL | 1.1.2+1.21 | ~1.21 | Fabric | — | REMOVE | REMOVE | Disabled in the reference pack. DISABLED duplicate: original 'Particular' 1.1.2 (client-only, needs owo-lib ^0.12.10). Same mod id 'particular' as the enabled Particular Reforged 1.5.5 - enabling both would be a duplicate-mod load failure. Delete or keep disabled. |
| Particular Reforged | OPTIONAL/CLIENT-QOL | 1.5.5 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Particular Reforged (multiloader fork) - ambience particles. Needs forgeconfigapiport. env=* (server presence needed?) - verify; recommends iris. |
| PastureLoot | GAMEPLAY-CRITICAL | 1.0.5+1.21.1 | 1.21.1 | Fabric | >=1.7.1+1.21.1 | NEEDS FUNCTIONAL TEST | PRESERVE; TEST | Pasture loot drops (config/PastureLoot.json). cobblemon >=1.7.1+1.21.1. 1 API ref. Empty description; ARR. |
| PlayerXP | OPTIONAL/CLIENT-QOL | 1.1.1+1.21.1 | 1.21.1 | Fabric | >=1.6.0 | INCOMPATIBLE ON SERVER / NEEDS CLIENT TEST | CLIENT OPTIONAL; SERVER EXCLUDE | The common entrypoint loads Fabric's client-only `ItemTooltipCallback` and crashes a dedicated server. No newer release or source fix exists as of 2026-09-09. Client retention is provisional. |
| Pokeblocks | WORLD-CRITICAL | 1.4.0-1.21.1 | ~1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 314 blockstates (Pokemon figurines, baskets, etc.) - decorative blocks in the map. No cobblemon dependency; needs geckolib >=4.7.3. CC-BY-NC-4.0. |
| Radical Cobblemon Trainers API | GAMEPLAY-CRITICAL / LIBRARY | 0.15.2-beta | ~1.21.1 | Fabric | >=1.7 | NEEDS FUNCTIONAL TEST | UPDATE → 0.16.0-beta | Radical Cobblemon Trainers API - trainer/battle API. Needed by: rctmod (>=0.15.0-beta), cobblemonbattlepositions (>=0.14.0); suggested by raiddens. cobblemon >=1.7 (no upper). 56 API refs. Gameplay-critical library. |
| Radical Cobblemon Trainers | GAMEPLAY-CRITICAL | 0.18.1-beta | 1.21.1 | Fabric | >=1.7.0 | NEEDS FUNCTIONAL TEST | UPDATE → 0.19.0-beta | 1500+ trainers spawning (Radical Red/Unbound/BDSP) + 3 blockstates. cobblemon >=1.7.0, rctapi, forgeconfigapiport >=21.1.1. Pack ships COBBLEVERSE-RCT-DP-v20 datapack + RCTmod RP for it. Bundles jgrapht. |
| Rechiseled | WORLD-CRITICAL | 1.2.4 | >=1.21 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | 3628 blockstates of decorative block variants - by far the largest block set; any use in the map makes it mandatory. Needs supermartijn642corelib >=1.1.20 <1.2.0, configlib, fusion. ARR + modpack permission. |
| Reese's Sodium Options | OPTIONAL/CLIENT-QOL | 2.2.3+mc1.21.1 | 1.21.1 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; sodium >=0.8.12 (exactly the shipped version). |
| Repurposed Structures | WORLD-CRITICAL | 7.5.21+1.21.1-fabric | >=1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Worldgen: extra structure variants. Removing changes future chunk generation. Needs midnightlib >=1.5.7. |
| Resourceful Lib | GAMEPLAY-CRITICAL / LIBRARY | 3.0.12 | >=1.20.5 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: handcrafted (>=3.0.0), highlight (also nested there). |
| Resource Pack Options | OPTIONAL/CLIENT-QOL | 4.14.0+1.21.1.4 | * | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Resource pack option menus (.rpo files in resourcepacks/). Needs libjf. Conflicts with quilt_loader/connectormod. |
| Sodium | OPTIONAL/CLIENT-QOL | 0.8.12+mc1.21.1 | ["1.21", "1.21.1"] | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only renderer. Provides 'indium'. Large breaks list (iris <1.8.13, moreculling <1.0.8, notenoughcrashes <4.4.8, iceberg <1.2.7 - all satisfied). |
| Sophisticated Backpacks | GAMEPLAY-CRITICAL | 1.21.1-3.23.4.3.106 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Backpacks holding player items. Needs sophisticatedcore >=1.2.9.15 <1.22. GPL-3 unofficial Fabric port. |
| Sophisticated Core | GAMEPLAY-CRITICAL / LIBRARY | 1.21.1-1.2.9.21.168 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: sophisticatedbackpacks, sophisticatedstorage. Needs forgeconfigapiport >=21.1.3, team_reborn_energy (nested). Breaks jei <19.21. 12 nested porting_lib jars. |
| Sophisticated Storage | GAMEPLAY-CRITICAL | 1.21.1-1.3.7.9.139 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Storage blocks with player items (49 blockstates). Needs sophisticatedcore. |
| Sound Physics Remastered | OPTIONAL/CLIENT-QOL | 1.21.1-1.5.1 | ["1.21", "1.21.1"] | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Audio (env=*, client effect). Breaks voicechat <2.3.0. |
| SoundsBeGone | OPTIONAL/CLIENT-QOL | 1.5.2 | >=1.21 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only sound muting. Bundles posthog analytics lib (privacy note). |
| SuperMartijn642's Config Lib | GAMEPLAY-CRITICAL / LIBRARY | 1.1.8 | >=1.21 <1.22 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: rechiseled (>=1.1.6), obc (>=1.1.8; also nested there). ARR. |
| SuperMartijn642's Core Lib | GAMEPLAY-CRITICAL / LIBRARY | 1.1.21 | >=1.21 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: rechiseled (>=1.1.20 <1.2.0). minecraft >=1.21 <1.21.2. ARR. |
| Tim Core | GAMEPLAY-CRITICAL / LIBRARY | 1.7.3-fabric-1.32.0 | 1.21.1 | Fabric | 1.7.3+1.21.1 | NEEDS FUNCTIONAL TEST | UPDATE → 1.8.0-fabric-1.32.0 | HARD BLOCKER: depends cobblemon "1.7.3+1.21.1" (exact pin). Needed by: capture_xp. 106 API refs. Both Tim mods must be rebuilt for 1.8 or removed together. |
| TM Craft | GAMEPLAY-CRITICAL | 1.4.18+1.7.3 | 1.21.1 | Fabric | 1.7.3+1.21.1 | NEEDS FUNCTIONAL TEST | UPDATE → 1.4.19+1.8.0 | HARD BLOCKER: depends cobblemon "1.7.3+1.21.1" (exact pin). TMs with crafting recipes + move tutor / breeder table blocks (world-persistent). 31 API refs. GPL-3.0. |
| Tom's Simple Storage Mod | GAMEPLAY-CRITICAL | 2.3.0 | >=1.21 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Storage network blocks holding items (16 blockstates). minecraft >=1.21 <1.21.2. Bundles cardinal-components + cloth-config. |
| ToolTip Fix | OPTIONAL/CLIENT-QOL | 1.1.1-1.20 | — | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only; jar says 1.20 but declares no minecraft dep (loads anywhere). Tiny mixin - low risk. |
| Trinkets | GAMEPLAY-CRITICAL / LIBRARY | 3.10.0 | >1.18 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Nothing in the pack hard-depends on trinkets (only recommended by accessories_compat_layer). Candidate for removal unless a resource/data pack or server plugin uses Trinkets slots. minecraft '>1.18' (very loose). |
| VillagerConfig | OPTIONAL/CLIENT-QOL | 4.5.4 | — | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Villager trade customization (config/VillagerConfig/villagerconfig.json5). If the pack defines custom trades there, becomes gameplay-relevant. No minecraft dep declared. Bundles fiber. |
| Waystones | WORLD-CRITICAL | 21.1.37 | >=1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Waystone blocks (45 blockstates) + worldgen placement; player-activated waystones are world state. Needs balm. fabricloader >=0.17.3. ARR. |
| Xaero's Minimap | OPTIONAL/CLIENT-QOL | 26.4.2 | 1.21.1 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Minimap (env=*, has server entrypoint; safe on server). Bundles xaerolib. Breaks xaeroworldmap <1.44.0 (ok). |
| Xaero's World Map | OPTIONAL/CLIENT-QOL | 1.44.2 | >1.20.6 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | World map. minecraft >1.20.6 <1.21.2. Breaks xaerominimap <26.4.0 (ok). |
| YetAnotherConfigLib | GAMEPLAY-CRITICAL / LIBRARY | 3.8.2+1.21.1-fabric | ~1.21 <1.21.2 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Needed by: zoomify (>=3.6.6); recommended by debugify. fabricloader >=0.17.0. |
| zamega | GAMEPLAY-CRITICAL | 1.7.3 | ~1.21.1 | Fabric | >=1.7 | NEEDS FUNCTIONAL TEST | UPDATE → 1.7.7+1.8 | Legends Z-A megas: pure data (species_additions, spawn pools, cobblemon assets) - 0 API refs, but hard-depends mega_showdown >=1.6.2+1.7+1.21.1, cobblemon >=1.7, accessories, architectury. Follows MSD's fate. Jar version '1.7.3' = Cobblemon target. |
| Fast Noise | OPTIONAL/CLIENT-QOL | 1.0.13+1.21 | ~1.21 | Fabric | — | LIKELY WORKING | PRESERVE FOR BOOT | Worldgen noise optimization - if it changes noise output the map's future chunks differ; verify determinism vs vanilla before generating. Requires fabricloader >=0.18.4 (highest floor in pack). Breaks moonrise/noisium. |
| Zoomify | OPTIONAL/CLIENT-QOL | 2.15.2+1.21.1 | ~1.21 <1.21.2 | Fabric | — | LIKELY WORKING | CLIENT ONLY | Client-only zoom. Needs YACL, kotlin >=1.13.8. fabricloader >=0.18.0. |

## Non-mod pack components

| Component | Type | Current Version | Minecraft Version | Loader | Cobblemon Dependency | 1.8 Status | Action | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| datapacks/COBBLEVERSE - No Ender Dragon.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/COBBLEVERSE - No Hunger.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/COBBLEVERSE-DP-v31.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | Cobblemon 1.7 riding data | NEEDS COMPATIBILITY PATCH | PRESERVE SOURCE; PATCH RUNTIME RIDING SEATS | Contains 233 offset-based riding additions. Generate a runtime copy with native 1.8 named locators for 51 mounts; retain 182 Cobbleverse-only offsets. Mudsdale and Charizard verified. |
| datapacks/COBBLEVERSE-Loot-DP-v11.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/COBBLEVERSE-RCT-DP-v20.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/PokeCenterPCs-DP.zip | WORLD-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/extra/COBBLEVERSE-Hoenn-DP.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/extra/COBBLEVERSE-Johto-DP.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/extra/COBBLEVERSE-Sinnoh-DP.zip | GAMEPLAY-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| datapacks/extra/Terralith-DP.zip | WORLD-CRITICAL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; FRESH-WORLD TEST | datapack |
| resourcepacks/ATMxMSD RP.zip | OPTIONAL / CLIENT-QOL | 3.6.1 in base 1.7.42 | 1.21.1 | Fabric | Cobblemon model resolvers; Mega Showdown assets | INCOMPATIBLE (3.6.1); UPDATE AVAILABLE (v4.0, NEEDS BOOT TEST) | PRESERVE INSTALLED; DISABLE BY DEFAULT | First 1.8 client launch failed its resource reload because the pack resolves Mega Mewtwo X as `cobblemon:mewtwo_mega_x.geo`; Mega Showdown 1.0.2 for Cobblemon 1.8 provides `cobblemon:mewtwo_x.geo`. The fallback reload reached the title/welcome screen but left the custom splash visible. Retest a newer or patched pack separately. 2026-09-26: it is also the only client source of assets for 40 spawnable species (vullaby, oranguru, …), which render as the substitute doll while it is disabled. A subset pack of those species' files is recommended instead of re-enabling it; see the client model audit above. 2026-09-28: the author's Modrinth v4.0 (`odZZdRCE` version `2JPClXSG`, `ATM x MSD [v4.0].zip`, sha1 `05d41177…`) no longer names `mewtwo_mega_x/y` or `ashgreninja`, and on a file-level scan gives all 43 doll species a model (fixes 1 of the 16 mis-textured forms, Appletun). Same licence v3.2. Not booted. See `CLIENT_MODEL_FIXES.md`, "ATM x MSD v4.0 from Modrinth, 2026-09-28". |
| resourcepacks/COBBLEVERSE RCTmod RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/COBBLEVERSE RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/COBBLEVERSE Soundtrack.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Canon PC Wallpapers.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/CavsCobbleMons RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Classic Grass.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/CobbleMotion RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Cobblemon Interface Modded.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Cobblemon Interface.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Comforts Modernized.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/E19 Cobblemon Minimap Icons.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/EeveelutionsReimagined RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Emissive Cobblemon Ores.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Fresh Animations.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Fresh Icons.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Fresh Moves.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/FullyHisuianStarters RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/GlitchDex RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/HydroReanimodel RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/JigglyRadio.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/LackingMons RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Low Fire.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/MissingMons RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/MundialMons RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/MysticMons RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/OJsAnimations RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Original Pokemon Battle Music.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/PlanetaCobblemon RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/PokeDiscs.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/PokeRods3D.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/Pokemans RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/TDmon RP.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [ATM x MSD - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [CavsCobbleMons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [CobbleMotion - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [E19 Minimap Icons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [GlitchDex - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [Hydro Reanimodel - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [LackingMons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [MissingMons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [MundialMons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [MysticMons - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [PlanetaCobblemon - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [Pokemans - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [TDmon - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| resourcepacks/z DO NOT ENABLE z [Terralith - Credits Only].zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | NEEDS FUNCTIONAL TEST | PRESERVE; CLIENT TEST | resourcepack |
| shaderpacks/ComplementaryUnbound_r5.8.1.zip | OPTIONAL / CLIENT-QOL | base 1.7.42 asset | 1.21.1 | Fabric | data/resource compatibility | LIKELY WORKING | CLIENT ONLY | shaderpack |

## Boot and smoke-test status

The isolated runtime contains the pinned Fabric launcher, all 100 target server jars, base configuration, overlay configuration, and all 10 datapacks, with `COBBLEVERSE-DP-v31.zip` generated as a patched runtime copy. The effective client plan contains 135 jars, 47 resource packs, 10 datapacks, and one shader pack. The assembled client launches and connects; Mudsdale and Charizard riding pass, while broader gameplay smoke tests remain pending.

The first real complete-overlay launch failed in PlayerXP's common entrypoint. The next launch failed in Raid Dens during datapack reload. After applying the scoped exclusions, the server reached `Done`. Client riding then exposed stale 1.7 offset seats in the main Cobbleverse datapack. Capture `20260910-124927` reached `Done (1.276s)` with the generated seat migration, and the user verified Mudsdale and Charizard riding. The retained upstream datapacks still emit nonfatal errors for orphaned Raid Dens loot tables; these were recorded without expanding the boot-fix scope. Server startup and those two mounts are verified for this exact set; other gameplay components remain unverified until their functional checks pass.

## Update audit, 2026-10-13: newer releases for Cobblemon 1.8.x on Minecraft 1.21.1 Fabric

**Question.** Which mods in the server and client stack have a newer release that is ready for Cobblemon 1.8.x? Report only: nothing was downloaded; the owner approves each file.

**Method.** The 102 jars in `cobblers-server/mods` were read with Python `zipfile` (`fabric.mod.json`) and hashed (SHA-512). The hashes were posted to the Modrinth API (`POST /v2/version_files` for the installed version, `POST /v2/version_files/update` with `loaders=["fabric"]`, `game_versions=["1.21.1"]` for the newest). Changelogs and dependency lists come from those version records. Client-only mods were looked up the same way from the SHA-512 values in `modpack/manifest/base-cobbleverse-1.7.42.json` (33 client-only jars; the owner's actual client folder was not inspected). The "latest" is the newest by date and may be a beta or alpha; the type is shown. Declared dependency ranges for the *new* jars were not read, because that needs the jar; where a pin is stated below it is from the installed jar, a changelog, or the mod's source tag, and says which.

**Result (server, 102 jars).** 56 CURRENT (55 are already the newest Modrinth version for 1.21.1 Fabric, plus `cobblemon-battle-positions`, not on Modrinth, undetermined), 22 UPDATE, 14 UPDATE-CAREFUL, 10 HOLD. **Client-only (33 jars):** 20 CURRENT, 11 UPDATE, 2 HOLD. Cobblemon itself: **1.8.2 (2026-10-11)** is the newest; 1.8.1 (2026-09-12) is in between. The server runs 1.8.0.

### Blockers and the lockstep set

1. **Cobblemon 1.8.2 is a set, not a single jar.** Four installed jars pin Cobblemon exactly: `tim_core` and `tmcraft` (`1.8.0+1.21.1`) and `capture_xp` (`1.8.0+1.21.1`); `rctapi` 0.16.2 and Cobbreeding 2.4.1 state they need 1.8.2 (Cobbreeding: "does not work with the previous versions of Cobblemon"). Move together: Cobblemon 1.8.2, tim_core 1.8.2-1.34.0, tmcraft 1.4.19+1.8.2, rctapi 0.16.2-beta, Cobbreeding 2.4.1, Mega Showdown 1.3.0 hotfix, Zamega 1.8.2+1.8.2.
2. **`capturexp` has no 1.8.2 build.** Newest is 1.8.1-fabric-1.3.0, whose source tag sets `cobblemon_version=1.8.1+1.21.1` (an exact pin, by the same template as the installed 1.8.0 jar). It will stop the loader on 1.8.2. Smallest change: remove it from the server (and client) for the 1.8.2 move, or wait for a 1.8.2 build. The alternative is staying on 1.8.0 for everything, or moving to the 1.8.1 set (tmcraft `1.4.19+1.8.1`, tim_core `1.8.1-fabric-1.33.2`, Mega Showdown `1.2.0+1.8.1`, Zamega `1.8.1+1.8`, capturexp 1.8.1 all exist; Cobbreeding's 1.8.1 pairing was not checked). Which to choose is the owner's.
3. **rctapi/rctmod.** rctapi 0.16.2-beta is required on Cobblemon 1.8.2 (it fixes crashes from changed items, e.g. Iron Ball). rctmod 0.19.2-beta is not required (0.19.0 needs rctapi `>=0.16.0-beta`) and changes presentation: trainer messages become speech bubbles by default (0.19.1, #407) and trainer loot tables gain Cobblemon TMs (#406). HOLD it unless we want both.
4. **CobbleDollars Beta-6.1 breaks our config path.** `bank.json` becomes `default_bank.json` with a new serialization; `tools/bank.py` writes `modpack/config/cobbledollars/bank.json`. HOLD.
5. **Authored data touching 1.8.2.** Cobblemon 1.8.2 "Removed Mega Drain as a TM" and adds species (Eternatus, Snover line, Grubbin line, ...), changing spawn pools and evolution handling. `data/tm_gate.json`, `data/markets.json`, `data/progression.json`, `data/challenge_mode.json` and `data/trainers.json` reference `megadrain` (`tmcraft:tm_megadrain` at `data/tm_gate.json:124`). Not verified whether tmcraft 1.4.19+1.8.2 still ships that item.

### UPDATE-CAREFUL (staging boot and a snapshot first)

| Installed jar | Installed | Latest for 1.21.1 Fabric | Published | File (size) | URL | Class and evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Carved Wood-fabric-1.21.1-1.9.7-B.jar | 1.9.7-B-Fabric-1.21.1 | 1.9.8-B-Fabric-1.21.1 | 2026-09-09 release | Carved Wood-fabric-1.21.1-1.9.8-B.jar (2,897,856 B) | https://cdn.modrinth.com/data/WuwijfrW/versions/LdlaVUmN/Carved%20Wood-fabric-1.21.1-1.9.8-B.jar | **UPDATE-CAREFUL.** World-critical. 1.9.8-B changelog "Hot Fix (Please update to this version)"; 1.9.8 (beta) "Fixed some bugs with Every Compat". No block change stated. |
| Cobblemon-fabric-1.8.0+1.21.1.jar | 1.8.0 | 1.8.2 | 2026-10-11 release | Cobblemon-fabric-1.8.2+1.21.1.jar (139,317,851 B) | https://cdn.modrinth.com/data/MdwFAVRL/versions/GJ2a1b8O/Cobblemon-fabric-1.8.2%2B1.21.1.jar | **UPDATE-CAREFUL.** Core. Release notes 1.8.1 and 1.8.2 list fixes, new species/items and datapack/Molang additions; no breaking change stated. 1.8.2 removes Mega Drain as a (Cobblemon) TM and adds a `negate` evolution requirement. Lockstep anchor: tim_core, tmcraft, rctapi, Cobbreeding, MSD and Zamega need 1.8.2; capturexp cannot load on it (see blockers). |
| Cobbreeding-fabric-2.3.0.jar | 2.3.0 | 2.4.1 | 2026-10-12 release | Cobbreeding-fabric-2.4.1.jar (477,771 B) | https://cdn.modrinth.com/data/ItmVb4zY/versions/QEX1BKMf/Cobbreeding-fabric-2.4.1.jar | **UPDATE-CAREFUL.** Changelog: "Compatibility with 1.8.2 / This version does not work with the previous versions of Cobblemon". Required with Cobblemon 1.8.2 (2.3.1 and 2.4.0 sit in between; not read). |
| beautify-2.0.0+1.21.1.jar | 2.0.0+1.21.1 | 3.0.0+1.21.1 | 2026-10-06 release | beautify-3.0.0+1.21.1.jar (905,029 B) | https://cdn.modrinth.com/data/DhSSvaxs/versions/tY6FTt9y/beautify-3.0.0%2B1.21.1.jar | **UPDATE-CAREFUL.** World-critical. 3.0.0: picture frames can be placed at 8 angles (placement behaviour of an existing block; 12 authored references to `beautify:dark_oak_picture_frame`), botanist-house jigsaws retargeted (village worldgen). No removal stated. |
| fusion-1.2.12-fabric-mc1.21.jar | 1.2.12-fabric-mc1.21 | 1.3.16-fabric-mc1.21 | 2026-10-05 release | fusion-1.3.16-fabric-mc1.21.jar (913,396 B) | https://cdn.modrinth.com/data/p19vrgc2/versions/LQSMRNBf/fusion-1.3.16-fabric-mc1.21.jar | **UPDATE-CAREFUL.** Connected-texture library used by Rechiseled and resource packs; 1.2.12 to 1.3.16 spans many releases, changelog shows rendering fixes. Update with Rechiseled and check connected textures in game. |
| mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar | 1.0.2+1.8+1.21.1-release | 1.3.0+1.8.2+1.21.1-hotfix | 2026-10-12 release | mega_showdown-fabric-1.3.0+1.8.2+1.21.1-hotfix.jar (20,041,092 B) | https://cdn.modrinth.com/data/SszvX85I/versions/EAunp9Kz/mega_showdown-fabric-1.3.0%2B1.8.2%2B1.21.1-hotfix.jar | **UPDATE-CAREFUL.** Version `1.3.0+1.8.2`; changelog "1.8.2 compact", hotfix "Crash fix fabric". The jump from 1.0.2 covers 1.1.0 (new megas, models, Dex Entry Additions files), 1.2.0 (for 1.8.1) and 1.3.0: content additions, so mega authoring and spawn overlays need a recheck. Its declared Cobblemon range was not read (needs jar metadata). |
| pokeblocks-1.4.0-1.21.1.jar | 1.4.0-1.21.1 | 1.5.0-1.21.1 | 2026-04-03 release | pokeblocks-1.5.0-1.21.1.jar (1,775,159 B) | https://cdn.modrinth.com/data/hnOfcjSq/versions/qlp66lU8/pokeblocks-1.5.0-1.21.1.jar | **UPDATE-CAREFUL.** World-critical. 1.5.0 adds Dolls and three Poke-Block blocks, plus a loot-table injection fix; additive, no removal stated. Requires GeckoLib (installed 4.9.2 ok). |
| rctapi-fabric-1.21.1-0.16.1-beta.jar | 0.16.1-beta | 0.16.2-beta | 2026-10-12 beta | rctapi-fabric-1.21.1-0.16.2-beta.jar (267,864 B) | https://cdn.modrinth.com/data/CBfM2yw7/versions/DoQNDXAU/rctapi-fabric-1.21.1-0.16.2-beta.jar | **UPDATE-CAREFUL.** Changelog: "Bump min required version of Cobblemon to `1.8.2`"; "Crashes related to changes in some items in Cobblemon `1.8.2` (e.g. Iron Ball)". The double-faint softlock fix (#132) is in 0.16.1 and 0.16.2 is later in the same line; that it still holds is not verified. Required with Cobblemon 1.8.2. Still `-beta`. |
| rechiseled-1.2.4-fabric-mc1.21.jar | 1.2.4-fabric-mc1.21 | 1.2.6-fabric-mc1.21 | 2026-09-13 release | rechiseled-1.2.6-fabric-mc1.21.jar (11,951,835 B) | https://cdn.modrinth.com/data/B0g2vT6l/versions/7411ZFAs/rechiseled-1.2.6-fabric-mc1.21.jar | **UPDATE-CAREFUL.** World-critical. 1.2.5 "Fixed non-connecting blocks also connecting", 1.2.6 translations and a JEI crash fix. No block id change stated. Pair with supermartijn642corelib 1.1.25 and Fusion 1.3.16. |
| repurposed_structures-7.5.21+1.21.1-fabric.jar | 7.5.21+1.21.1-fabric | 7.5.22+1.21.1-fabric | 2026-08-20 release | repurposed_structures-7.5.22+1.21.1-fabric.jar (8,203,618 B) | https://cdn.modrinth.com/data/muf0XoRe/versions/JRMMCb1O/repurposed_structures-7.5.22%2B1.21.1-fabric.jar | **UPDATE-CAREFUL.** World-critical (worldgen). 7.5.22 "Config Datapack Updated": overworld land structures now exclude ocean-tagged biomes; needs Fabric API >=0.116.14 (met). New chunks only. Depends on midnightlib. |
| timcore-fabric-1.8.0-1.32.0.jar | 1.8.0-fabric-1.32.0 | 1.8.2-fabric-1.34.0 | 2026-10-11 release | timcore-fabric-1.8.2-1.34.0.jar (307,475 B) | https://cdn.modrinth.com/data/lVP9aUaY/versions/dtgPWpFE/timcore-fabric-1.8.2-1.34.0.jar | **UPDATE-CAREFUL.** Installed jar pins `cobblemon` = `1.8.0+1.21.1` exactly; changelog of 1.8.2-fabric-1.34.0: "Bumped to Cobblemon 1.8.2". Required with Cobblemon 1.8.2. |
| tmcraft-1.4.19+1.8.0.jar | 1.4.19+1.8.0 | 1.4.19+1.8.2 | 2026-10-11 release | tmcraft-1.4.19+1.8.2.jar (6,505,639 B) | https://cdn.modrinth.com/data/HU6mkUZs/versions/cIXTptDr/tmcraft-1.4.19%2B1.8.2.jar | **UPDATE-CAREFUL.** Installed jar pins `cobblemon` = `1.8.0+1.21.1` exactly; changelog "Updated for Cobblemon 1.8.2". Required with Cobblemon 1.8.2. Authored data references `tmcraft:tm_megadrain` (data/tm_gate.json:124 and four other data files); Cobblemon 1.8.2 removed Mega Drain as a TM; whether tmcraft keeps that item is not verified. |
| waystones-fabric-1.21.1-21.1.37.jar | 21.1.37+fabric-1.21.1 | 21.1.46+fabric-1.21.1 | 2026-09-25 release | waystones-fabric-1.21.1-21.1.46.jar (1,248,666 B) | https://cdn.modrinth.com/data/LOpKHB2A/versions/nSAwjAk4/waystones-fabric-1.21.1-21.1.46.jar | **UPDATE-CAREFUL.** World-critical. Changes 21.1.38-46: fixes (crashes, visibility, scrolls), new `/waystones cooldown` commands, `allowedVisibilities` deprecated for `allowEveryoneToManageGlobalWaystones`, new worldgen tags (empty), `enableDurability` option; no block removal stated. 18 authored references to `waystones:waystone`. Back up the Waystones config; test warp and scroll items. |
| zamega-fabric-1.7.7+1.8.jar | 1.7.7+1.8 | 1.8.2+1.8.2 | 2026-10-13 release | zamega-fabric-1.8.2+1.8.2.jar (896,936 B) | https://cdn.modrinth.com/data/2V1Y86sc/versions/CBalGwUD/zamega-fabric-1.8.2%2B1.8.2.jar | **UPDATE-CAREFUL.** Version `1.8.2+1.8.2`; Modrinth deps list Cobblemon, Mega Showdown, owo-lib, accessories, architectury. Move with Mega Showdown. Published 2026-10-13, one day old. |

### UPDATE (low risk; bundle into the same boot test)

| Installed jar | Installed | Latest for 1.21.1 Fabric | Published | File (size) | URL | Class and evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Axiom-6.0.5-for-MC1.21.1.jar | 6.0.5 | 6.1.3 | 2026-09-25 release | Axiom-6.1.3-for-MC1.21.1.jar (47,177,991 B) | https://cdn.modrinth.com/data/N6n5dqoA/versions/vHcXJQqi/Axiom-6.1.3-for-MC1.21.1.jar | **UPDATE.** Editor tool; "bug fixes and improvements". |
| Debugify-1.21.1+1.0.jar | 1.21.1+1.0 | 1.21.1+1.1 | 2026-09-28 release | Debugify-1.21.1+1.1.jar (289,699 B) | https://cdn.modrinth.com/data/QwxR6Gcd/versions/pyIdu3f1/Debugify-1.21.1%2B1.1.jar | **UPDATE.** Debugify: "gameplay fixes not being correctly disabled in multiplayer". |
| DistantHorizons-3.2.0-b-1.21.1-fabric-neoforge.jar | 3.2.0-b-1.21.1 | 3.3.3-1.21.1 | 2026-09-29 release | DistantHorizons-3.3.3-1.21.1-fabric-neoforge.jar (28,289,212 B) | https://cdn.modrinth.com/data/uCdwusMi/versions/9w34y8ai/DistantHorizons-3.3.3-1.21.1-fabric-neoforge.jar | **UPDATE.** Distant Horizons 3.3.3: config version 4 to 5 "will clear your config" (re-apply our DH settings). Pinned `exact` in overlay.json. |
| MobsBeGone-0.0.7.jar | 0.0.7 | 0.0.9 | 2026-08-03 release | MobsBeGone-0.0.9.jar (10,563 B) | https://cdn.modrinth.com/data/hXvXSxxg/versions/ZGbHcluC/MobsBeGone-0.0.9.jar | **UPDATE.** Changelog: "Fixed compatibility with Cobblemon Combee beehive behaviour". |
| MoreCobblemonTweaks-fabric-1.3.3.jar | 1.3.3-fabric | 1.3.5-fabric | 2026-09-15 release | MoreCobblemonTweaks-fabric-1.3.5.jar (138,045 B) | https://cdn.modrinth.com/data/5KWlJ2HC/versions/j4HsonDT/MoreCobblemonTweaks-fabric-1.3.5.jar | **UPDATE.** Changelog 1.3.5: "Fixed minimum egg iv indicator always showing"; declared Cobblemon range unchanged (`>=1.7.0`). |
| NoChatRestrictions-Fabric-MC1.21.11-v1.0.0.jar | Fabric-MC1.21.11-v1.0.0 | Fabric-MC1.21.11-v1.0.3 | 2026-09-30 release | NoChatRestrictions-Fabric-MC1.21.11-v1.0.3.jar (10,182 B) | https://cdn.modrinth.com/data/z440MEwJ/versions/J95EIHAC/NoChatRestrictions-Fabric-MC1.21.11-v1.0.3.jar | **UPDATE.** 10 KB. Installed jar is the MC1.21.11 build; Modrinth lists 1.21.1 among its game versions. Changelog: Forge/NeoForge/IGAS fixes only. |
| SafePastures-1.1.1+1.21.1.jar | 1.1.1+1.21.1 | 1.1.2+1.21.1 | 2026-09-13 release | SafePastures(Fabric)-1.1.2+1.21.1.jar (16,517 B) | https://cdn.modrinth.com/data/qpe01spE/versions/gHHJ8bPf/SafePastures%28Fabric%29-1.1.2%2B1.21.1.jar | **UPDATE.** Changelog: "Updated to Cobblemon v1.8.0 and newer". |
| architectury-13.0.8-fabric.jar | 13.0.8+fabric | 13.0.11+fabric | 2026-07-23 release | architectury-13.0.11-fabric.jar (600,921 B) | https://cdn.modrinth.com/data/lhGA9TYQ/versions/Pzc2FP5K/architectury-13.0.11-fabric.jar | **UPDATE.** Library patch 13.0.8 to 13.0.11; changelog is a commit link only. |
| balm-fabric-1.21.1-21.0.63.jar | 21.0.63+fabric-1.21.1 | 21.0.66+fabric-1.21.1 | 2026-09-25 release | balm-fabric-1.21.1-21.0.66.jar (805,265 B) | https://cdn.modrinth.com/data/MBAkmtvl/versions/EghJxg4h/balm-fabric-1.21.1-21.0.66.jar | **UPDATE.** Fixes a memory leak in BlockEntityOnLoadCallback; Waystones depends on Balm. |
| defaultoptions-fabric-1.21.1-21.1.7.jar | 21.1.7+fabric-1.21.1 | 21.1.8+fabric-1.21.1 | 2026-07-24 release | defaultoptions-fabric-1.21.1-21.1.8.jar (107,949 B) | https://cdn.modrinth.com/data/WEg59z5b/versions/54JaBQkk/defaultoptions-fabric-1.21.1-21.1.8.jar | **UPDATE.** Fix for `extra` folder options not applied on Fabric. |
| entityculling-fabric-1.10.5-mc1.21.1.jar | 1.10.5 | 1.11.3 | 2026-10-08 release | entityculling-fabric-1.11.3-mc1.21.1.jar (1,519,243 B) | https://cdn.modrinth.com/data/NNAgCjsB/versions/yllJFBpU/entityculling-fabric-1.11.3-mc1.21.1.jar | **UPDATE.** Culling fixes; client-side effect. |
| fabric-api-0.116.14+1.21.1.jar | 0.116.14+1.21.1 | 0.116.17+1.21.1 | 2026-09-01 release | fabric-api-0.116.17+1.21.1.jar (2,452,735 B) | https://cdn.modrinth.com/data/P7dR8mSH/versions/Mys3P7lK/fabric-api-0.116.17%2B1.21.1.jar | **UPDATE.** 0.116.14 to 0.116.17: version bump plus a revert of "Hud Render Events Backport"; Repurposed Structures needs >=0.116.14. |
| fancymenu_fabric_3.9.8_MC_1.21.1.jar | 3.9.8-1.21.1-fabric | 3.9.14-1.21.1-fabric | 2026-09-28 release | fancymenu_fabric_3.9.14_MC_1.21.1.jar (26,277,804 B) | https://cdn.modrinth.com/data/Wq5SjeWM/versions/iGLyAyEZ/fancymenu_fabric_3.9.14_MC_1.21.1.jar | **UPDATE.** Client UI mod; changelog is a link only. |
| fzzy_config-0.7.6+1.21.jar | 0.7.6+1.21 | 0.7.7+1.21 | 2026-09-15 release | fzzy_config-0.7.7+1.21.jar (2,387,721 B) | https://cdn.modrinth.com/data/hYykXjDp/versions/zFccjYag/fzzy_config-0.7.7%2B1.21.jar | **UPDATE.** Config library 0.7.6 to 0.7.7. |
| geckolib-fabric-1.21.1-4.9.2.jar | 4.9.2 | 4.9.3 | 2026-09-16 release | geckolib-fabric-1.21.1-4.9.3.jar (664,463 B) | https://cdn.modrinth.com/data/8BmcQJ2H/versions/tmxM7U4W/geckolib-fabric-1.21.1-4.9.3.jar | **UPDATE.** GeckoLib 4.9.3: molang fixes and a crash-on-load fix. Pokeblocks depends on it. |
| midnightlib-1.7.5-fabric+1.21.1.jar | 1.7.5+1.21.1-fabric | 1.9.3+1.21.1-fabric | 2026-05-02 release | midnightlib-fabric-1.9.3+1.21.1.jar (58,781 B) | https://cdn.modrinth.com/data/codAaoxh/versions/as2ZKoB1/midnightlib-fabric-1.9.3%2B1.21.1.jar | **UPDATE.** MidnightLib 1.7.5 to 1.9.3 (formatting and NPE fixes). Repurposed Structures depends on it. |
| notenoughanimations-fabric-1.12.4-mc1.21.1.jar | 1.12.4 | 1.12.6 | 2026-09-19 release | notenoughanimations-fabric-1.12.6-mc1.21.1.jar (1,873,853 B) | https://cdn.modrinth.com/data/MPCX6s5C/versions/P5COwDnM/notenoughanimations-fabric-1.12.6-mc1.21.1.jar | **UPDATE.** Client animation mod; crawl crash hotfix. |
| particular-1.21.1-Fabric-1.5.5.jar | 1.5.5 | 1.5.7 | 2026-08-16 release | particular-1.21.1-Fabric-1.5.7.jar (285,956 B) | https://cdn.modrinth.com/data/pYFUU6cq/versions/7HcxmnFS/particular-1.21.1-Fabric-1.5.7.jar | **UPDATE.** Particular Reforged 1.5.5 to 1.5.7: fixes (cave dust biome list, boat splashes). |
| supermartijn642corelib-1.1.21-fabric-mc1.21.jar | 1.1.21-fabric-mc1.21 | 1.1.25-fabric-mc1.21 | 2026-10-06 release | supermartijn642corelib-1.1.25-fabric-mc1.21.jar (622,551 B) | https://cdn.modrinth.com/data/rOUBggPv/versions/ImY2F2fz/supermartijn642corelib-1.1.25-fabric-mc1.21.jar | **UPDATE.** Library 1.1.21 to 1.1.25; update with Rechiseled, which depends on it. |
| toms_storage_fabric-1.21-2.3.0.jar | 1.21-2.3.0-fabric | 1.21-2.4.2-fabric | 2026-08-30 release | toms_storage_fabric-1.21-2.4.2.jar (1,971,384 B) | https://cdn.modrinth.com/data/XZNI4Cpy/versions/nhRuPk5W/toms_storage_fabric-1.21-2.4.2.jar | **UPDATE.** Tom's Storage 2.3.0 to 2.4.2: Filing Cabinet fix, recipe advancements, a duplication fix. |
| xaerominimap-fabric-1.21.1-26.4.2.jar | fabric-1.21.1-26.4.2 | fabric-1.21.1-26.6.0 | 2026-10-05 release | xaerominimap-fabric-1.21.1-26.6.0.jar (2,234,556 B) | https://cdn.modrinth.com/data/1bokaNcj/versions/W4dcLcUs/xaerominimap-fabric-1.21.1-26.6.0.jar | **UPDATE.** Client-side; changelog is a link only. |
| xaeroworldmap-fabric-1.21.1-1.44.2.jar | fabric-1.21.1-1.44.2 | fabric-1.21.1-1.47.0 | 2026-10-05 release | xaeroworldmap-fabric-1.21.1-1.47.0.jar (1,456,162 B) | https://cdn.modrinth.com/data/NcUtCpym/versions/XIR7GzC3/xaeroworldmap-fabric-1.21.1-1.47.0.jar | **UPDATE.** Client-side; changelog is a link only. |

### HOLD

| Installed jar | Installed | Latest for 1.21.1 Fabric | Published | File (size) | URL | Class and evidence |
| --- | --- | --- | --- | --- | --- | --- |
| CobbleDollars-fabric-2.0.0+Beta-5.1+1.21.1.jar | 2.0.0+Beta-5.1 | 2.0.0+Beta-6.1 | 2026-07-22 beta | CobbleDollars-fabric-2.0.0+Beta-6.1+1.21.1.jar (500,815 B) | https://cdn.modrinth.com/data/s7N7AsqL/versions/NQdxKsW7/CobbleDollars-fabric-2.0.0%2BBeta-6.1%2B1.21.1.jar | **HOLD.** Only betas exist. Beta-6 changelog: "new Shop/Bank serialization format", `bank.json` renamed `default_bank.json`, merchant shops stored on entities may be affected, back up first. Our economy pipeline writes `modpack/config/cobbledollars/bank.json` (`tools/bank.py`, `tools/economy_audit.py`) and the live server has that file: tools would need rework first. |
| LegendaryMonuments-Cobbleverse.jar | LM-Cobbleverse | 8.2-Keep-Fighting | 2026-10-05 release | legendarymonuments-fabric-1.21.1-8.2-Keep-Fighting.jar (16,931,202 B) | https://cdn.modrinth.com/data/m6RyHSbV/versions/dcZ53MPy/legendarymonuments-fabric-1.21.1-8.2-Keep-Fighting.jar | **HOLD.** World-critical. Installed `LM-Cobbleverse` is the Cobbleverse-specific build (declared Cobblemon `>=1.7.0`, published 2026-02-02). 8.2 is the mainline: requires Lithostitched and Chipped (neither installed); 8.0 removed the Cherry Plains biome, 8.0.2 switched Terrablender to Lithostitched for biome generation; 8.2 notes "Compatible with 1.8.1 Cobblemon". Our sanctuaries reference its blocks (`legendarymonuments:*_shrine`, `distortion_stone`, ...). Changes worldgen and possibly block ids; nothing in it is needed. |
| ScalableLux-0.1.0.1+fabric.d0d58ab-all.jar | 0.1.0.1+fabric.d0d58ab | 0.3.0-alpha.0.7+1.21.1 | 2026-08-16 alpha | ScalableLux-fabric-0.3.0-alpha.0.7-all.jar (196,331 B) | https://cdn.modrinth.com/data/Ps1zyz6x/versions/AodeMVa6/ScalableLux-fabric-0.3.0-alpha.0.7-all.jar | **HOLD.** 0.3.0-alpha.0.7 is an alpha (auto-uploaded CI build). Lighting engine; do not move to an alpha. |
| biomereplacer-2.1-hippo-fabric.jar | 2.1-hippo-fabric | 3.1-hippo-fabric | 2026-06-18 beta | biomereplacer-3.1-hippo-fabric.jar (147,722 B) | https://cdn.modrinth.com/data/DAXbR0Wj/versions/yWEYAFRu/biomereplacer-3.1-hippo-fabric.jar | **HOLD.** World-critical. 3.1-hippo is a beta (the latest release is 2.1-hippo, the installed one); changes are 26.1 corruption fixes, dimension-id parsing and a crash fix with Adventure Platform + Terrablender. Nothing we need. |
| capturexp-fabric-1.8.0-1.3.0.jar | 1.8.0-fabric-1.3.0 | 1.8.1-fabric-1.3.0 | 2026-09-13 release | capturexp-fabric-1.8.1-1.3.0.jar (23,382 B) | https://cdn.modrinth.com/data/LBl4Qguc/versions/FOUiJc3h/capturexp-fabric-1.8.1-1.3.0.jar | **HOLD.** BLOCKER for Cobblemon 1.8.2. Latest is 1.8.1-fabric-1.3.0 ("Port to 1.8.1"). Source tag v1.8.1-1.3.0 `gradle.properties` has `cobblemon_version=1.8.1+1.21.1`, and the mod template writes it into `depends.cobblemon`, as the installed 1.8.0 jar shows (`1.8.0+1.21.1`): an exact pin, so it loads on Cobblemon 1.8.1 only. Read from raw.githubusercontent.com, not from the jar. |
| cobblemon-additions-4.1.6.jar | 4.1.6 | 4.3.0 | 2026-03-19 release | cobblemon-additions-4.3.0.jar (3,198,962 B) | https://cdn.modrinth.com/data/W2pr9jyL/versions/NVitD9gY/cobblemon-additions-4.3.0.jar | **HOLD.** World-critical. 4.1.6 to 4.3.0 spans 4.2.x and 4.3.0, published 2026-03-19, "Requires Cobblemon 1.7.3+1.21.1": predates 1.8, no 1.8 statement. Ice village overhaul (structures moved to a `structures/` subdirectory, jigsaw layout changed) and a new Fairy village: worldgen for new chunks only. No authored data references `cobblemon_additions:`. Requires CobbleDollars. |
| fabric-language-kotlin-1.13.13+kotlin.2.4.10.jar | 1.13.13+kotlin.2.4.10 | 1.14.2+kotlin.2.4.21 | 2026-10-09 release | fabric-language-kotlin-1.14.2+kotlin.2.4.21.jar (8,142,878 B) | https://cdn.modrinth.com/data/Ha28R6CL/versions/SKW1BTL3/fabric-language-kotlin-1.14.2%2Bkotlin.2.4.21.jar | **HOLD.** Runtime language adapter for Cobblemon and every Kotlin mod. 1.14.2 ships Kotlin 2.4.21; the changelog is version bumps only. No stated benefit; test only with the whole set. |
| owo-lib-0.12.15.4+1.21.jar | 0.12.15.4+1.21 | 0.13.0-alpha.15+1.21 | 2026-04-29 alpha | owo-lib-0.13.0-alpha.15+1.21.jar (1,963,544 B) | https://cdn.modrinth.com/data/ccKDOlHs/versions/m3XmDd8j/owo-lib-0.13.0-alpha.15%2B1.21.jar | **HOLD.** 0.13.0-alpha.15 is an alpha ("largely untested braid-ui-1.21 branch", "not entirely equivalent in features"); Mega Showdown and Interactic depend on owo-lib. |
| rctmod-fabric-1.21.1-0.19.0-beta.jar | 0.19.0-beta | 0.19.2-beta | 2026-09-22 beta | rctmod-fabric-1.21.1-0.19.2-beta.jar (6,807,725 B) | https://cdn.modrinth.com/data/lRwTUnD7/versions/rgfBfnW9/rctmod-fabric-1.21.1-0.19.2-beta.jar | **HOLD.** Optional. 0.19.1 shows trainer messages as speech bubbles by default (new server options `showMessageAsSpeechBubble`, `showMessagesInChat`) and adds Cobblemon TMs to trainer loot tables (#406); 0.19.2 fixes bubble crashes. Both change what players see and receive from our authored trainers. 0.19.0 already requires rctapi >=0.16.0-beta, so it runs on rctapi 0.16.2. Only betas exist. |
| zfastnoise-1.0.13+1.21.jar | 1.0.13+1.21 | 1.0.14+1.21 | 2026-08-09 release | zfastnoise-1.0.14+1.21.jar (36,201 B) | https://cdn.modrinth.com/data/OnlVIpq5/versions/73DMCY3S/zfastnoise-1.0.14%2B1.21.jar | **HOLD.** 1.0.14 adds a new required dependency, ZConfig (Modrinth project `4qmvXRB9`), not installed. Principle 9: no new dependency for a patch. |

### Client-only mods (from `base-cobbleverse-1.7.42.json`)

| Installed jar | Installed | Latest for 1.21.1 Fabric | Published | File (size) | URL | Class and evidence |
| --- | --- | --- | --- | --- | --- | --- |
| EuphoriaPatcher-1.9.3-r5.8.1-fabric.jar | 1.9.3-r5.8.1-fabric | 1.10.5-r5.9.3-fabric | 2026-09-15 release | EuphoriaPatcher-1.10.5-r5.9.3-fabric.jar (4,602,936 B) | https://cdn.modrinth.com/data/4H6sumDB/versions/YYczPGkW/EuphoriaPatcher-1.10.5-r5.9.3-fabric.jar | **HOLD.** Tracks a Complementary Shaders release (changelog: "Updated to Complementary Shaders r5.9.2"); the pack ships `ComplementaryUnbound_r5.8.1.zip`. Move the shader and the patcher together or not at all. |
| ImmediatelyFast-Fabric-1.6.11+1.21.1.jar | 1.6.11+1.21.1-fabric | 1.6.14+1.21.1-fabric | 2026-09-13 release | ImmediatelyFast-Fabric-1.6.14+1.21.1.jar (340,166 B) | https://cdn.modrinth.com/data/5ZwdcRci/versions/7XKnsIC8/ImmediatelyFast-Fabric-1.6.14%2B1.21.1.jar | **UPDATE.** Patch release 1.6.11 to 1.6.14; client rendering. |
| catchindicator-fabric-1.7.0.jar | 1.7.0 | 3.0 | 2026-09-07 release | catchindicator-fabric-3.0.jar (335,369 B) | https://cdn.modrinth.com/data/tpTcu2PM/versions/qPETaVwo/catchindicator-fabric-3.0.jar | **UPDATE.** 3.0 "Now requires Cobblemon 1.8.0 or newer": uses 1.8 native Alpha title, native XS-XL size categories and Pokedex states. Installed 1.7.0 targets Cobblemon 1.7; this is the 1.8 build. |
| catchrate-display-fabric-2.8.22.jar | 2.8.22+fabric | 2.12.3+fabric | 2026-09-20 release | catchrate-display-fabric-2.12.3.jar (293,930 B) | https://cdn.modrinth.com/data/vADO40xp/versions/rh5xmGEe/catchrate-display-fabric-2.12.3.jar | **UPDATE.** 2.12.3: Timer, Beast, Moon and Love Ball rates "calculate correctly on Cobblemon 1.8.1+, while staying accurate for 1.8.0 and earlier"; needs Fabric Language Kotlin (installed). Installed 2.8.22 declares Cobblemon `>=1.6.0`. |
| entity_model_features-3.2.4-1.21-fabric.jar | 3.2.4-fabric-1.21 | 3.3.11-fabric-1.21 | 2026-10-05 release | entity_model_features-3.3.11-1.21-fabric.jar (652,846 B) | https://cdn.modrinth.com/data/4I1XuqiY/versions/VeoAKvQ0/entity_model_features-3.3.11-1.21-fabric.jar | **UPDATE.** 3.2.4 to 3.3.11; fixes. Needs ETF-family dependency (project BVzZfTc1). |
| entity_texture_features_1.21-fabric-7.1.jar | 7.1-fabric-1.21 | 7.2.5-fabric-1.21 | 2026-10-04 release | entity_texture_features-7.2.5-1.21-fabric.jar (799,948 B) | https://cdn.modrinth.com/data/BVzZfTc1/versions/OVZ7HJXt/entity_texture_features-7.2.5-1.21-fabric.jar | **UPDATE.** 7.1 to 7.2.5; allocation performance fix. |
| modmenu-11.0.4.jar | 11.0.4 | 11.0.5 | 2026-09-24 release | modmenu-11.0.5.jar (975,846 B) | https://cdn.modrinth.com/data/mOgUt4GM/versions/6lgOkclV/modmenu-11.0.5.jar | **UPDATE.** 11.0.4 to 11.0.5. |
| moreculling-fabric-1.21.1-1.0.8.jar | 1.0.8 | 1.0.10 | 2026-09-07 release | moreculling-fabric-1.21.1-1.0.10.jar (332,266 B) | https://cdn.modrinth.com/data/51shyZVL/versions/wUYbHzXF/moreculling-fabric-1.21.1-1.0.10.jar | **UPDATE.** 1.0.8 to 1.0.10. |
| musicnotification-fabric-3.0.0+mc1.21.1.jar | 3.0.0 | 3.4.0-alpha.1 | 2026-10-03 alpha | musicnotification-fabric-3.4.0-alpha.1+mc1.21.1.jar (209,145 B) | https://cdn.modrinth.com/data/A4YQgwzz/versions/LTCin2Wc/musicnotification-fabric-3.4.0-alpha.1%2Bmc1.21.1.jar | **HOLD.** Newer is 3.4.0-alpha.1 (alpha). |
| particlerain-4.0.0-beta.10+1.21.1-fabric.jar | v4-beta.10+1.21.1-fabric | v4.0.2+1.21.1-fabric | 2026-10-10 release | particlerain-4.0.2+1.21.1-fabric.jar (626,772 B) | https://cdn.modrinth.com/data/nrikgvxm/versions/jquizTC2/particlerain-4.0.2%2B1.21.1-fabric.jar | **UPDATE.** 4.0.0-beta.10 to 4.0.2 (release); crash and flicker fixes. |
| reeses-sodium-options-fabric-2.2.3+mc1.21.1.jar | mc1.21.1-2.2.3+fabric | mc1.21.1-2.2.4+fabric | 2026-09-16 release | reeses-sodium-options-fabric-2.2.4+mc1.21.1.jar (257,229 B) | https://cdn.modrinth.com/data/Bh37bMuy/versions/XtuPOKUN/reeses-sodium-options-fabric-2.2.4%2Bmc1.21.1.jar | **UPDATE.** 2.2.3 to 2.2.4; pairs with Sodium 0.8.13. |
| sodium-fabric-0.8.12+mc1.21.1.jar | mc1.21.1-0.8.12-fabric | mc1.21.1-0.8.13-fabric | 2026-08-28 release | sodium-fabric-0.8.13+mc1.21.1.jar (1,574,609 B) | https://cdn.modrinth.com/data/AANobbMI/versions/SMxNOGZ6/sodium-fabric-0.8.13%2Bmc1.21.1.jar | **UPDATE.** 0.8.12 to 0.8.13; crash-log message fix. |
| soundsbegone-fabric-1.5.2+mc1.21.jar | 1.5.2+fabric-1.21 | 1.6.0+fabric-1.21 | 2026-09-19 release | soundsbegone-fabric-1.6.0+mc1.21.jar (6,151,886 B) | https://cdn.modrinth.com/data/FOIvwGKz/versions/HJwHCWgs/soundsbegone-fabric-1.6.0%2Bmc1.21.jar | **UPDATE.** 1.5.2 to 1.6.0; changelog not read. |

Also: PlayerXP 1.1.2+1.21.1 exists (installed 1.0.9, excluded from the server after it crashed in its common entrypoint); not tested, HOLD. Krypton 0.2.8 is current but excluded from the server.

CURRENT client-only: AdvancementPlaques-1.21.1-fabric-1.6.8.jar, BadOptimizations-2.4.1-1.21.1.jar, BetterF1-Fabric-1.1+1.21.7.jar, BetterF3-11.0.3-Fabric-1.21.1.jar, BetterThirdPerson-Fabric-1.21-1.9.0.jar, Controlling-fabric-1.21.1-19.0.5.jar, LumyREI-1.1.3.jar, MouseTweaks-fabric-mc1.21-2.26.jar, ResourcePackOverrides-v21.1.0-1.21.1-Fabric.jar, Searchables-fabric-1.21.1-1.0.2.jar, betterbeds-fabric-1.4.0.jar, brb-1.10.0-rc5+1.21.jar, continuity-3.0.0+1.21.jar, customsplashscreen-2.2.0.jar, infinite-music-0.4.6.jar, iris-fabric-1.8.14-beta.1+mc1.21.1.jar, paginatedadvancements-2.5.1.jar, particle_core-0.3.3+1.21.jar, tooltipfix-1.1.1-1.20.jar, zoomify-2.15.2+1.21.1.jar.

### CURRENT on the server (newest Modrinth version for 1.21.1 Fabric)

CobbleFurnies-fabric-1.2.jar, CobbleverseBadges-1.3.jar, ForgeConfigAPIPort-v21.1.6-1.21.1-Fabric.jar, Iceberg-1.21.1-fabric-1.3.2.jar, IronChests-2.0.4.jar, Luckys-Cozyhome-Refurnished-1.1.20.jar, LumyMon-0.6.6.jar, Only Bottle Caps-1.5.0-fabric.jar, Ping-Wheel-1.12.2-fabric-1.21.1.jar, Platform-fabric-1.21.1-1.3.3.jar, RoughlyEnoughItems-16.0.799-fabric.jar, StackDeobfuscatorFabric-1.4.3+08e71cc.jar, VanillaBackport-fabric-1.21.1-1.1.7.10.jar, accessories-fabric-1.1.0-beta.53+1.21.1.jar, accessories_compat_layer-fabric-0.1.12+1.21.1.jar, advancementdisable-fabric-1.0.1+1.21.jar, athena-fabric-1.21.1-4.0.6.jar, cloth-config-15.0.140-fabric.jar, cobblecuisine-2.0.1-1.7.rc1.jar, cobblemon-battle-extras-fabric-1.13.45.jar, cobblenav-fabric-2.4.1.jar, comforts-fabric-9.0.5+1.21.1.jar, configurable-3.5.2+1.21.1-fabric.jar, ferritecore-7.0.3-fabric.jar, fightorflight-fabric-0.11.0.jar, forgivingvoid-fabric-1.21.1-21.1.7.jar, globalpacks-fabric-1.21.1-21.0.6.jar, handcrafted-fabric-1.21.1-4.0.3.jar, highlight-fabric-1.21-3.0.0.jar, huge-structure-blocks-fabric-1.1.6.jar, interactic-0.2.3+1.21.jar, konkrete_fabric_1.9.9_MC_1.21.jar, lenientdeath-1.2.5+1.21.1.jar, libjf-3.17.5.jar, lithium-fabric-0.15.4+mc1.21.1.jar, melody_fabric_1.0.10_MC_1.21.jar, moar-concrete-1.3.1.jar, modernfix-fabric-5.25.1+mc1.21.1.jar, neruina-3.3.3+1.21.1-fabric.jar, nethermap-4.0.0-1.21.1.jar, netherportalfix-fabric-1.21.1-21.1.3.jar, notenoughcrashes-fabric-4.4.9+1.21.1.jar, packetfixer-3.3.1-1.20.5-1.21.X-merged.jar, pastureLoot-1.0.5+1.21.1.jar, resourcefullib-fabric-1.21-3.0.12.jar, respackopts-4.14.0+1.21.1.4.jar, sophisticatedbackpacks-1.21.1-3.23.4.3.106.jar, sophisticatedcore-1.21.1-1.2.9.21.168.jar, sophisticatedstorage-1.21.1-1.3.7.9.139.jar, sound-physics-remastered-fabric-1.21.1-1.5.1.jar, supermartijn642configlib-1.1.8-fabric-mc1.21.jar, trinkets-3.10.0.jar, villagerconfig-fabric-4.5.4+1.21.1.jar, worldedit-mod-7.3.8.jar, yet_another_config_lib_v3-3.8.2+1.21.1-fabric.jar.

World-critical members of this list: CobbleFurnies 1.2, Comforts 9.0.5, Handcrafted 4.0.3, Luckys Cozy Home Refurnished 1.1.20, LumyMon 0.6.6, Moar Concrete 1.3.1, VanillaBackport 1.1.7.10. Cobblemon-coupled members and what they declare about 1.8: Cobblenav 2.4.1 (`>=1.8.0`), Only Bottle Caps 1.5.0 (`>=1.8.0`, "not backwards compatible"), Fight or Flight 0.11.0 (`>=1.7.2`; author: "designed for Cobblemon 1.7, but it seems to work normally on Cobblemon 1.8"), Cobblemon Battle Extras 1.13.45 (`>=1.6`, published 2026-04-22, before 1.8), CobbleFurnies (`>=1.7.1`), LumyMon (`>=1.7.1`), CobbleCuisine 2.0.1-1.7-rc1 (`>=1.7.0`, 2025-11-26, alpha, before 1.8), PastureLoot (`>=1.7.1+1.21.1`), CobbleverseBadges 1.3 (no Cobblemon pin). None of these has a newer release, so "CURRENT" here means no update exists, not that 1.8 or 1.8.2 behaviour is proven.

### Not determined

- `cobblemon-battle-positions` (jar 1.1.3, metadata 1.1.2, MIT, `rctapi >=0.14.0`): not on Modrinth by hash or search; the GitHub URL in its metadata (`github.com/ramen/cobblemon-battle-positions`) returned "Not Found" from the GitHub API. CurseForge was not queried (no API access here).
- Declared `cobblemon` ranges of every proposed new jar (needs the jar; the owner has not approved any download). The 1.8.2 claims above rest on changelogs, version strings and the installed jars' pins.
- Whether any other `>=1.8` addon breaks on Cobblemon 1.8.2 item changes (rctapi did); an API-coupling check of Cobblenav, Battle Extras, Fight or Flight, OBC, Cobbreeding against 1.8.2 needs a boot.
- Block-id stability of the world-critical updates beyond what changelogs state; the changelogs list no removals, which is not proof.
- Cobblemon 1.8.2 effect on our authored spawn tables, TM gating and trainer teams: all unverified until a staging boot and a functional test.
- CurseForge-only releases of any mod listed.

**Sources.** Modrinth API, queried 2026-10-13: `POST https://api.modrinth.com/v2/version_files` and `/version_files/update` (installed and newest by SHA-512); `GET /v2/project/<id>/version?loaders=["fabric"]&game_versions=["1.21.1"]` for Cobblemon (`MdwFAVRL`), rctmod (`lRwTUnD7`), rctapi (`CBfM2yw7`), Mega Showdown (`SszvX85I`), LegendaryMonuments (`m6RyHSbV`), cobblemon-additions (`W2pr9jyL`), Waystones (`LOpKHB2A`), CobbleDollars (`s7N7AsqL`), capturexp (`LBl4Qguc`), tim_core (`lVP9aUaY`), tmcraft (`HU6mkUZs`), Cobbreeding (`ItmVb4zY`), Zamega (`2V1Y86sc`). capturexp pin: `raw.githubusercontent.com/timinc-cobble/cobblemon-capture-xp/v1.8.1-1.3.0/gradle.properties` and `v1.8.0-1.3.0/gradle.properties`. Installed-jar metadata: `fabric.mod.json` of the jars in `cobblers-server/mods`.

## Sources

- Local evidence: `base-pack/inventory/mod_inventory.json`, `base-pack/inventory/pack_hashes.csv`, `modpack/manifest/base-cobbleverse-1.7.42.json`, and `modpack/manifest/overlay.json`.
- [Fabric Meta loader API](https://meta.fabricmc.net/v2/versions/loader/1.21.1) and [installer API](https://meta.fabricmc.net/v2/versions/installer).
- Modrinth version records are linked by stable version ID in `overlay.json`; examples include [Cobblemon 1.8.0](https://api.modrinth.com/v2/version/YgmyyFcs), [RCT 0.19.0-beta](https://api.modrinth.com/v2/version/jdUENp3C), and [Mega Showdown 1.0.2](https://api.modrinth.com/v2/version/TACsHsKC).
- PlayerXP evidence: [Modrinth 1.21.1 releases](https://api.modrinth.com/v2/project/cobblemon-playerxp/version?loaders=%5B%22fabric%22%5D&game_versions=%5B%221.21.1%22%5D) and [current common entrypoint source](https://github.com/chudders1231/PlayerXP/blob/1.21.1/fabric/src/main/java/chadlymasterson/playerxp/PlayerXp.java).
- Raid Dens evidence: [Modrinth releases](https://api.modrinth.com/v2/project/cobblemonraiddens/version?loaders=%5B%22fabric%22%5D&game_versions=%5B%221.21.1%22%5D) and [current reload-listener source](https://github.com/necro50n3/cobblemon-raiddens/blob/master/fabric/src/main/java/com/necro/raid/dens/fabric/events/reloader/StatusEffectsReloadListener.java).
- Riding evidence: [Cobblemon riding setup](https://wiki.cobblemon.com/index.php/Tutorials/Riding_Setup), [Cobblemon species additions](https://wiki.cobblemon.com/index.php/Species_Additions), and [Cobblemon 1.8.0 changelog](https://modrinth.com/mod/cobblemon/version/YgmyyFcs).
