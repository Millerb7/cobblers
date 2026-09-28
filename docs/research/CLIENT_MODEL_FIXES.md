# Client model fixes: resource packs vs Cobblemon 1.8 models

**Status (2026-09-26):**
- **Crash class:** `cobblers-model-fixes.zip` (the 2026-09-14 build, seven forms) is installed on the authoring
  client. Not yet confirmed in game.
- **Substitute doll and mis-assembled forms:** `tools/client_model_fix.py` now detects both, and
  `build --server-pack` builds `cobblers-client-AllTheMons-subset.zip` for delivery through `server.properties`
  ([ADR-006](../decisions/ADR-006-server-delivered-client-pack.md)). **Built, not installed, not hosted, not seen
  in game.** A scan with the pack simulated on top leaves nothing uncovered but nine forms (below).
- **Licence: blocked on the owner.** The ATMxMSD RP we hold ships licence v3.2, which requires written permission
  to upload copies (see "Licence").
- **2026-09-28, the owner's route:** the author's own Modrinth v4.0, referenced by hash. File-level scan: it gives
  all 43 dolls a model, and the reload break of 3.6.1 is gone. Nothing seen in game yet. See "ATM x MSD v4.0 from
  Modrinth, 2026-09-28".

## Incident log

| Date | What happened | Evidence | Action |
| --- | --- | --- | --- |
| 2026-09-14 | Screen went black while flying the painted `cobblers-10240`. The server logged the player as "Disconnected" | Client crash report `crash-2026-09-14_07.51.45-client.txt`: `java.util.NoSuchElementException: Can't find part persian` in `PersianAlolanModel.<init>`, while rendering a wild Persian at 3076, 114, 4837. Not related to the terrain or the paint | Scanned the enabled pack stack; built and installed `cobblers-model-fixes.zip` |
| 2026-09-26 | Staging playtest: some wild Pokémon are the green substitute doll ("??? Lv.N"), Vullaby and Oranguru among them; Talonflame and Pidgeot are mis-assembled | [`COBBLEVERSE_COMPATIBILITY.md`](COBBLEVERSE_COMPATIBILITY.md), "Client model audit, 2026-09-26" | Added the `missing` and `uv_mismatch` rules; built `cobblers-client-AllTheMons-subset.zip`; not yet delivered |

## How the scan rebuilds the stack

- **Layers**, lowest first, from `options.txt` `resourcePacks`: every mod jar under `fabric`, built-in mod packs
  (`modid:name` → `resourcepacks/name/` in that jar), then `file/` packs. `--with-pack ZIP` adds a zip above all of
  them, which is where Minecraft puts a server resource pack.
- **Ids are keyed by file name** (VERIFIED, Cobblemon 1.8.0 bytecode, `VaryingModelRepository`; audit of
  2026-09-26): models as `ns:name.geo`, posers as `ns:name`, animation groups as `name` without a namespace. The
  lexicographically last path of a name wins, and the highest pack wins a path. A pack file at a different path
  with the same name therefore replaces Cobblemon's (CobbleMotion's `posers/talonflame.json`).
- **Variations:** the last variation whose aspects fit and that sets the field wins
  (`VaryingRenderableResolver.getVariationValue`).
- **Two stacks per scan:** "flagged" is the stack *without* our packs; "uncovered" is the effective stack, with our
  packs where `options.txt` enables them plus any `--with-pack`. A fault is covered only when it is gone from the
  effective stack.

## Rule 1, crash: a built-in poser missing a part

**How Cobblemon 1.8 poses a model:** either with a built-in Kotlin poser
(`…/blockbench/pokemon/genN/<Form>Model`) or with a JSON poser
(`bedrock/pokemon/posers/<form>.json`).

**Read from Cobblemon-fabric-1.8.0+1.21.1 bytecode (`VaryingModelRepository`):**
- `registerPosers` calls `registerInBuiltPosers` first, then `registerJsonPosers`, and stores
  both with `Map.put`, so **a JSON poser for the same form replaces the built-in one**.
- `loadJsonPoser` resolves `rootBone` through the model's children map and **falls back** when
  that bone is missing. JSON posers do not crash on renamed bones.
- **Built-in posers look parts up by name** (`ModelPart.getChild`), which throws when the part
  is missing.

COBBLEVERSE RP ships models made for Cobblemon 1.7. For Alolan Persian its root bone is
`persian_alolan`, while 1.8's built-in poser asks for `persian`.

**A form is flagged when all of these hold:**
1. a resource pack supplies the model that wins its id;
2. no JSON poser for it exists anywhere in the stack (jar or packs), so the built-in poser is used;
3. the pack's model lacks a non-locator part that Cobblemon's own model has.

**Limits:** it is conservative (a missing part is flagged even if the built-in poser never looks it up), and the
built-in-poser check matches class names, which is approximate (`GimmighoulChestModel` is matched both as
`gimmighoul_chest` and `gimmighoulchest`).

**Flagged on 2026-09-14 and again on 2026-09-26 (unchanged):**

| Form | Pack | Missing parts | Fix |
| --- | --- | --- | --- |
| persian_alolan | COBBLEVERSE RP | root `persian` (confirmed crash) | Cobblemon's model restored |
| granbull | COBBLEVERSE RP | item_hat, left_pupil, right_pupil | Cobblemon's model restored |
| ironleaves | COBBLEVERSE RP | leg_back_left, leg_back_right | Cobblemon's model restored |
| stoutland | COBBLEVERSE RP | seat_1_locator | Cobblemon's model restored |
| tangrowth | COBBLEVERSE RP | eye_left, eyelid_left, eye_right, eyelid_right | Cobblemon's model restored |
| vileplume | COBBLEVERSE RP | head_locators, arms, legs | Cobblemon's model restored |
| yanmega | COBBLEVERSE RP | eyes | Cobblemon's model restored |

For all seven the packs override only the model file, so restoring Cobblemon's keeps model, texture and animation
consistent. **The trade:** these seven show Cobblemon's models instead of COBBLEVERSE RP's.

**Checked and deliberately not patched:** exeggutor_alolan, silcoon, typhlosion_hisuian,
zoroark_hisuian, samurott_hisuian and dartrix_hisui_bias also have root-bone mismatches, but a
JSON poser covers each of them. JSON posers fall back instead of crashing.

## Rule 2, missing: a spawnable species with no client model

**Mechanism (VERIFIED, audit of 2026-09-26):** when a species has no resolver, or its resolver throws for a
missing model, poser or texture, `getPoser` returns the `substitute` resolver, the green doll. Nothing is logged.
"???" above it is only the unscanned-Pokédex name (`displayNameForUnknownPokemon: false`).

**Spawnable:** a species in `data/spawns.json` (any `pokemon` field, or `species` of a top-level entry), or a
species in a `spawn_pool_world` file of the instance's mod jars or `datapacks/` (and `datapacks/extra/`) whose final
`implemented` (jar species, then `species_additions`) is true.

**Flagged:** no resolver; or the variation for no aspects names a model or texture the stack lacks, or a poser that
is neither a JSON poser nor built in; or no variation applies without aspects at all.

**Flagged on 2026-09-26: 43 species.**
- **40 with no resolver**, the audit's list: arctibax, blacephalon, bombirdier, brutebonnet, buzzwole, charjabug,
  fluttermane, frigibax, gougingfire, greattusk, greavard, grubbin, gulpin, guzzlord, houndstone, ironbundle,
  ironcrown, ironmoth, ironthorns, irontreads, ironvaliant, jirachi, manaphy, mandibuzz, nihilego, oranguru,
  passimian, pecharunt, pheromosa, phione, ragingbolt, roaringmoon, sandyshocks, screamtail, slitherwing, stakataka,
  swalot, vikavolt, vullaby, xurkitree.
- **3 more the audit missed: baxcalibur, magearna, zeraora.** Their only resolver is ZAMegas' `7_<species>_mega.json`,
  whose variations all need the `mega` aspect, so an ordinary one is a doll too. All three spawn from
  `COBBLEVERSE-DP-v31.zip`. ATMxMSD has their base sets.

## Rule 3, uv_mismatch: a model its texture was not drawn for

**Measure (from the audit's `score.py`):** normalise each cube's UV rectangle by the model's `texture_width` and
`texture_height`, then take the share of the effective model's rectangles that also appear in the model the texture
was drawn for.
- **"Drawn for"** = the model of that id in the texture's own pack, else the model that wins the id at that pack's
  level of the stack.
- Only forms whose model and texture come from different layers are measured.
- **Flagged:** under half of the rectangles match, or the texture's aspect ratio differs from the model's UV space.

**Why the cut is 50%, not 20%:** the measure is bimodal. On 2026-09-26, 797 of 864 split forms match 95% or more
and 59 under 20%. Between them sit only onix 79%, porygon2 71%, victreebel (mega) 88%, and Hisuian Samurott at
20.4%, which the audit counts as broken (Class A). The cut sits in the empty gap between 21% and 70%. The 50–95%
and 20–50% bands are listed in every scan, so a form drifting into the gap is seen.

**Limit:** "drawn for" assumes a pack drew against whatever sat below it. It is wrong for a pack drawn against an
older Cobblemon: E19 Cobblemon Minimap Icons' Arbok snake-pattern textures (128×64) were drawn for the 1.7.3 model,
yet measure against 1.8's.

**Flagged on 2026-09-26: 33 forms** (63 with shiny variants).
- The audit's **16 Class A forms**: COBBLEVERSE RP's 1.7.3 model wearing Cobblemon 1.8's redrawn texture. appletun,
  arbok, archaludon, cofagrigus, crobat, garganacl, goodra, goodra (hisuian), nidoking, pidgeot, primarina,
  samurott (hisuian), skarmory, talonflame, turtonator, tyranitar.
- **Arbok's 8 snake patterns:** E19's resolver replaces Cobblemon's at the same path and sets 1.7-layout textures.
- **7 megas:** a Mega Showdown texture on COBBLEVERSE RP's mega model, all at 0%. aggron, altaria, gengar, manectric,
  sceptile, slowbro, swampert.
- **Class B, female beautifly and dustox:** 1.8's female model (64×128 and 128×64 UV) with COBBLEVERSE RP's
  128×128 texture. Flagged by aspect ratio.

## The fixes the tool builds

**Cobblemon's own files, from the local jar** (`build`, and part of `--server-pack`):
- **crash:** Cobblemon's model at every path a pack uses for that id.
- **uv_mismatch whose texture is Cobblemon's own** (the 16 Class A forms):
  - Cobblemon's model at every pack path for that id.
  - Where a pack's JSON poser shadows Cobblemon's JSON poser, Cobblemon's poser at the pack's path, and Cobblemon's
    animation groups at the pack's paths. This covers CobbleMotion's goodra, goodra_hisuian, nidoking, primarina,
    talonflame and tyranitar.
  - **Hisuian Samurott keeps CobbleMotion's poser and animations.** Cobblemon poses it with a built-in poser
    (`SamurottHisuianModel`), and a JSON poser of the same name replaces a built-in one; no file can restore a
    built-in poser. CobbleMotion's animations touch 56 bones, and 51 of them exist in 1.8's model.
  - **Arbok also gets Cobblemon's resolver** at E19's path. Without it, the restored 1.8 model would wear E19's
    128×64 pattern textures. The tool finds such cases by simulating its own fixes and rescanning.
- **The trade:** these forms show Cobblemon 1.8's look instead of COBBLEVERSE RP's, CobbleMotion's or E19's.

**Not fixed, by decision:**
- the 7 megas: their texture is Mega Showdown's, not Cobblemon's, so no Cobblemon file restores them;
- female beautifly and dustox: the empty-resolver trick the audit proposed is unverified.

## The server pack

`python tools/client_model_fix.py build --server-pack --instance DIR` writes
`build/client/cobblers-client-AllTheMons-subset.zip` and its sha1 to `….zip.sha1`. The build is deterministic
(fixed entry dates, sorted entries), so an unchanged input gives an unchanged sha1.

**Contents:**
- Cobblemon's own files, as above.
- **The ATMxMSD subset**, derived rather than listed:
  - `ATMxMSD RP.zip` is simulated at its Cobbleverse position, just above `cobblemon:regionbiasforms`, per
    `base-pack/cobbleverse/config/resourcepackoverrides.json`.
  - For every species the `missing` rule flags, the derivation takes the ATMxMSD files it needs: resolvers, the
    models and posers they name, their textures and layer textures, and the animation groups their posers use.
  - The build fails if a needed id is unresolved, collides with an id already in the stack, or a species is absent
    from ATMxMSD.
- `pack.mcmeta`: `pack_format` 34, a description naming AllTheMons and Cobblemon, and a `credits` object.
- `CREDITS.md`: AllTheMons' contributors and other credited people, parsed from the pack's own `readme.md`.
- `LICENSE-AllTheMons.md` (the pack's licence) and `cobblers-client-pack.json` (what was covered, and each file's
  source).

**The path list** is committed as `modpack/manifest/client-pack-atm-subset.json`: paths only, with the source zip's
sha256. A build whose derived list differs stops, until it is rerun with `--record-paths`.

**Reproducing the audit:** `donor_subset(instance, layer_textures=False, no_resolver_only=True)` gives exactly the
audit's 223 paths for its 40 species. The full derivation gives **265 paths for 43 species**:
- the 223;
- 19 emissive and glow layer textures for 16 of the 40 species, which the audit left out, and which their resolvers
  reference;
- 23 files for baxcalibur, magearna and zeraora.

**Two of the 265 are left to COBBLEVERSE RP:** the screamtail and ironcrown models, which COBBLEVERSE RP also ships
at the same path and which win in Cobbleverse's own order. The audit found them 100% UV-compatible with ATMxMSD's
textures. The zip therefore holds 263 ATMxMSD files.

**Built 2026-09-26** from Cobblemon-fabric-1.8.0+1.21.1 and ATMxMSD RP 3.6.1 (sha256 `6d48b792…`):
- 1,468,971 bytes, sha1 `dfdd4f8118a66ff854d23a1e5c2f7651ff042e97`;
- 36 Cobblemon files, 263 ATMxMSD files.

A rebuild after any pack or Cobblemon change gives a new sha1; `server.properties` must follow it.

## Scan results, 2026-09-26

**Instance:** Modrinth profile "Fabric 1.21.10", Cobblemon 1.8.0, 182 layers, 1,017 spawnable species.

| | crash | missing | uv_mismatch (forms incl. shiny) |
| --- | --- | --- | --- |
| Flagged (no packs of ours) | 7 | 43 | 63 |
| Uncovered: installed `cobblers-model-fixes.zip` only | 0 | 43 | 63 |
| Uncovered: plus the server pack, simulated on top | 0 | 0 | 16 |

**Still uncovered with the server pack:** the 7 megas and female beautifly and dustox, each with its shiny, which
makes 16 form keys. Split forms at 95% or more rose from 797 to 833.

**Not verified:**
- Everything in game. The scan is a file-level reconstruction of the stack. It matches the client's own
  `latest.log` counts for the installed stack: 1,583 model registrations ("Loaded 1583 models") and 1,284 animation
  groups. No form above has been seen rendering.
- Whether the Resource Pack Overrides mod reorders packs at launch, for the local `install`. A server pack is outside
  that mod's list.

## Licence

**The disagreement:**
- ADR-006 relies on `base-pack/cobbleverse/licenses/AllTheMons x Mega Showdown - License.txt`, which is licence
  v3.1. Its §1.3 allows non-monetized redistribution of a modified copy whose title includes "AllTheMons".
- **The ATMxMSD RP.zip we hold is not under v3.1.** It is version 3.6.1, identical by sha256 to Cobbleverse's, and
  its own `LICENSE` is **v3.2**. Its §1.3 opens: "Only with explicit written permission can the User … upload copies
  of the Software", modified or unmodified.
- Its §4 dates v3.1 to releases between 2025-12-07 and 2026-03-30.

**Consequence:**
- Hosting the zip at a URL for `server.properties` is an upload of a modified copy. Under v3.2 that needs written
  permission from the author (Lvnatic), whatever the audience.
- The pack is built locally only, and must not be uploaded until the owner decides.
- ADR-006's licence paragraph needs revisiting (content-architect).

## ATM x MSD v4.0 from Modrinth, 2026-09-28

**The route (the owner's choice, 2026-09-28):** the pack references the author's own Modrinth file by hash, so we
host nothing. This section records what that file is, what it covers on our stack, and what would change to adopt
it. Nothing in `modpack/` was changed.

### The file (VERIFIED, Modrinth API, fetched 2026-09-28)

Sources: `https://api.modrinth.com/v2/project/odZZdRCE` and `…/project/odZZdRCE/version`.

| Field | Value |
| --- | --- |
| Project | "AllTheMons x Mega Showdown", slug `allthemons-x-mega-showdown-legacy`, id `odZZdRCE`, `project_type` `mod`, `client_side` optional, `server_side` required, source `https://gitlab.com/lvnatic/allthemons-x-mega-showdown` |
| Version | `v4.0`, "AllTheMons x Mega Showdown [4.0]", id **`2JPClXSG`**, release, listed, published 2026-09-08T15:53:52Z |
| File | `ATM x MSD [v4.0].zip`, primary, **8,115,647 bytes** |
| sha1 | `05d411776564ec96934a3e5b7ed8aca8e3df780a` |
| sha512 | `96e4b45e57c5183ff59cbe2d7ad2b743b4384ac393f4ed9c6a02e636af3b7c1f24d8fdcd99ac8a8769c1712f917ada936f7a92a0d91df47b3b0ddf498632f682` |
| URL | `https://cdn.modrinth.com/data/odZZdRCE/versions/2JPClXSG/ATM%20x%20MSD%20%5Bv4.0%5D.zip` |
| Game versions / loaders | `1.21.1` / `datapack`, `minecraft` (not `fabric`) |
| Dependencies | none declared. The project page says "This requires Mega Showdown". We run `mega_showdown-fabric-1.0.2+1.8+1.21.1` |
| Licence (Modrinth field) | `LicenseRef-AllTheMons-License-v3.2`, linked to the author's Google document |

The download was checked against both hashes. It was saved to a session scratch folder outside the repository and
never committed. The zip is a combined data and resource pack: 1,263 `assets/`, 474 `data/`, `pack.mcmeta`
`pack_format` 48 with `supported_formats` 34–48, so 1.21.1 (34) accepts it. As a client resource pack its `data/` is
ignored.

### Licence: what it says about a modpack referencing the file

- **VERIFIED:** the `LICENSE` inside v4.0 is **ALLTHEMONS LICENSE v3.2**, byte-identical (apart from line endings) to
  the one in our 3.6.1. §1.3 still reads "Only with explicit written permission can the User … upload copies of the
  Software".
- **VERIFIED: the licence says nothing about referencing, linking or launcher auto-download.** Its "Public
  Distribution" definition lists launchers among the ways of *making the Software available*, but that definition
  is about providing a copy. §1.3 restricts *uploading copies*.
- **Our reading (ASSUMED, not legal advice):** a `.mrpack` entry lists the file by its `cdn.modrinth.com` URL and
  hashes, and each player's launcher downloads the author's own upload from Modrinth. No copy is uploaded by us, so
  §1.3's permission is not triggered. Two things support this reading:
  - the project page asks people to read the licence "before starting a server or modpack containing the addon",
    so it expects modpacks;
  - Cobbleverse 1.7.42 already does this. Its manifest lists the Modrinth file `VhwUZj8K` (3.6.1) by hash as
    `z DO NOT ENABLE z [ATM x MSD - Credits Only].zip` (`modpack/manifest/base-cobbleverse-1.7.42.json`).
- **The consequence the reading does not excuse:** the Cobbleverse repack `ATMxMSD RP.zip` has no Modrinth source
  (`"source": {"type": "unresolved"}` in the base manifest). A `.mrpack` could carry it only in `overrides/`, which
  is an upload of a copy. An adopting pack must therefore **drop** `ATMxMSD RP.zip`, not merely leave it disabled.
- §1.2's rule that the name be listed visibly applies to commercial use. Crediting "AllTheMons x Mega Showdown (Lvnatic
  and contributors)" in the pack's info costs nothing and is recommended.

### What v4.0 covers (file-level scan)

**Instance and tools:** the Modrinth profile "Fabric 1.21.10" (Cobblemon 1.8.0, Mega Showdown 1.0.2, ZAMegas 1.7.7,
182 layers, 1,017 spawnable species). The scans used `tools/client_model_fix.py scan --with-pack`, which puts a zip
on top. A scratch script used the tool's own `Stack` and `faults` to put v4.0 at other positions, because the tool's
`insert=` looks for the zip only in the instance's `resourcepacks/`. "Baseline" means the stack without our packs.

| Position of v4.0 | crash | missing | uv_mismatch (form keys) | New faults | Species whose look changes vs baseline |
| --- | --- | --- | --- | --- | --- |
| Baseline (no v4.0) | 7 | 43 | 63 | | |
| **Cobbleverse's slot**, after `cobblemon:regionbiasforms` | 7 | **0** | 63 | **ironhands** (+ shiny) | 71 |
| After `file/PlanetaCobblemon RP.zip` | 7 | **0** | 61 | none | 71, and 9 Eeveelution posers |
| Top (as a server pack) | 7 | **0** | 61 | none | 102 |
| Our 3.6.1 at Cobbleverse's slot (control) | 7 | 0 | 65 | greninja cosmetic, ursaluna bloodmoon | |

- **Dolls: 43 of 43 covered at every position, the 11 in our tables among them** (Vullaby, Mandibuzz, Oranguru,
  Passimian, Gulpin, Swalot, Charjabug, Grubbin, Vikavolt, Greavard, Bombirdier).
  - For those 43 species, v4.0's resolvers declare exactly the aspect sets 3.6.1's did (compared file by file).
    3.6.1 is what COBBLEVERSE-DP's species data was built against.
  - Baxcalibur, Magearna and Zeraora keep ZAMegas' mega models for the `mega` aspect.
- **The 16 mis-textured forms: v4.0 fixes 1 of 16, Appletun.** It ships Appletun's poser and texture, which fit
  COBBLEVERSE RP's model. The other 15 are COBBLEVERSE RP's 1.7.3 models over Cobblemon 1.8's textures, and v4.0
  does not touch them. The 7 Mega Showdown megas, the E19 Arbok patterns and female Beautifly and Dustox also stay
  mis-textured.
- **The 7 crash forms: v4.0 neither fixes nor adds any.** Cobblemon's own files still fix them.

**What v4.0 breaks or overrides at Cobbleverse's slot:**
- **Iron Hands: a new mis-texture.** v4.0 ships its model at `bedrock/pokemon/models/`, PlanetaCobblemon RP ships
  it at `bedrock/models/`, and the lexicographically later path wins whatever the pack order. The model is
  therefore v4.0's while the texture is still PlanetaCobblemon's: 0% UV match, 128×128 UV space on a 256×256
  texture.
  - Placing v4.0 just above PlanetaCobblemon RP removes the fault.
  - The cost: v4.0's CobbleMotion posers then replace EeveelutionsReimagined's for eevee and its eight
    evolutions.
- **Mega Floette (Eternal Flower):** `flower-eternal`+`mega` resolves to v4.0's non-mega
  `atm_remodels:floette_eternalflower.geo` instead of Mega Showdown's `floette_eternal_mega.geo`. It is the only mega,
  Gigantamax or primal form whose model changes. Mega Mewtwo X and Y keep Mega Showdown's `mewtwo_x`/`mewtwo_y`.
- **The 71 species whose model, poser or texture changes.** All are consistent (no UV fault apart from Iron Hands).
  They are Cobbleverse 1.7's look, and v4.0's changelog lists them as deliberate. They fall into five groups:
  - **27 ATM remodels replace Cobblemon 1.8's model:** carkol, coalossal, delcatty, dipplin, druddigon, flapple,
    frosmoth, garbodor, glameow, grumpig, hydrapple, mew, mewtwo (base), purugly, regigigas, runerigus, sawk,
    seviper, skuntank, slurpuff, spoink, stunky, swirlix, throh, togedemaru, trubbish, zangoose. 12 of them spawn
    in `data/spawns.json`.
  - **9 replace Mega Showdown's:** cosmoem, cosmog, darkrai, deoxys (normal and attack forme), entei, floette
    (eternal), heatran, ursaluna (bloodmoon), victini.
  - **18 take v4.0's CobbleMotion posers over Cobblemon's:** arboliva, azumarill, azurill, cramorant, dolliv,
    espurr, fraxure, hawlucha, heracross, kingdra, leavanny, liepard, marill, meowstic, purrloin, smoliv, snorunt,
    weezing.
  - **3 replace LackingMons RP:** pawmi, pawmo, pawmot.
  - **Iron Hands**, the one above.
- **At the top position**, v4.0 would also override posers from EeveelutionsReimagined, TDmon and MissingMons,
  21 CobbleMotion RP textures, and COBBLEVERSE RP's appletun model. That is 102 species in all. Not recommended.

**With Cobblemon's own fix files as well:**
- `build --out` wrote a scratch copy of the Cobblemon-only fixes: 36 files, the 7 crash forms and the Class A forms.
- Simulated with v4.0 above PlanetaCobblemon, **everything is covered except the 7 megas and female Beautifly and
  Dustox (16 form keys, the same residue as the server pack) plus Appletun.**
- **Appletun is re-broken by the fix pack.** The fix pack was derived from a stack without v4.0, so it restores
  Cobblemon 1.8's Appletun model under v4.0's texture.
- The fix pack must therefore be rebuilt from an instance that has v4.0 enabled. It would then leave Appletun to
  v4.0.

### The reload break

- **What it was (VERIFIED):** `experiments/EXP-000-cobblemon-1.8-compat/results.md`, run 1 (2026-09-10): "`ATMxMSD
  RP.zip` requested missing Cobblemon 1.8 model `cobblemon:mewtwo_mega_x.geo`", and the resource reload failed. The
  3.6.1 resolvers `0150_mewtwo/1_mewtwo_mega_x.json` and `2_mewtwo_mega_y.json` name `mewtwo_mega_x/y` models,
  posers and textures. Mega Showdown 1.0.2 names them `mewtwo_x`/`mewtwo_y`.
- **Control:** a reference check reproduces the fault on 3.6.1. It walks every variation of every resolver for each
  species the pack touches and requires each named model, poser and texture to exist in the stack. It found the
  Mega Mewtwo X and Y `MODEL_MISSING`/`POSER_MISSING`, plus `POSER_MISSING cobblemon:ashgreninja`.
- **v4.0: gone (file-level).** No file in v4.0 mentions `mewtwo_mega`, `mega_x`, `mega_y` or `ashgreninja`. Its only
  Mewtwo resolver (`atm_remodels/…/0150_mewtwo/1_mewtwo_base.json`) sets the base, shiny and alpha-eyes variations.
- **Across v4.0's 108 species, at Cobbleverse's slot, no model, poser or animation group is missing.** Two apparent
  gaps are not v4.0's:
  - the fossil textures `genesect_fetus.png` and `mewtwo_fetus.png` are in the zip; the scanner indexes only
    `textures/pokemon/`, so they look missing;
  - Floette's `flower-expansion-*` textures are missing from E19's own resolver, and are absent with or without
    v4.0.
- **Two poser files are not strict JSON.** Whether Cobblemon 1.8's reader accepts them is NOT VERIFIED:
  - `0986_brutebonnet/brutebonnet.json` writes `[0., 0.1, 0]`. The same bytes shipped in 3.6.1, which Cobbleverse
    ran on Cobblemon 1.7.3.
  - `0022_fearow/fearow.json`, line 72, has a raw tab inside a string. CobbleMotion RP's `posers/fearow.json` wins
    the `fearow` id anyway, by path order.

### What adoption would change (not done; the modpack's owners decide)

1. **`modpack/manifest/overlay.json`, `replace[]`:** one entry with
   `"file": "z DO NOT ENABLE z [ATM x MSD - Credits Only].zip"`, the base's Modrinth 3.6.1 file. It would set
   `to_version` `v4.0`, `to_file` `ATM x MSD [v4.0].zip`, the `modrinth` block above (`project_id` `odZZdRCE`,
   `version_id` `2JPClXSG`, URL, size, `dependencies: []`), `sha1`, `sha512`, and `verification` "verified via
   Modrinth API 2026-09-28".
   - Fill it by hand. `pack_manifest.py resolve-overlay` asks Modrinth for `loaders=["fabric"]` and would mark this
     project unverified.
2. **`overlay.json`, `remove[]`:** `"file": "ATMxMSD RP.zip"`, Cobbleverse's unresolvable 3.6.1 repack, for the
   licence reason above.
3. **Pack order, in all three files that carry it:**
   - `modpack/config/resourcepackoverrides.json` `default_packs`;
   - `modpack/config/defaultoptions/options.txt` `resourcePacks`;
   - `modpack/config/defaultoptions-common.toml` `defaultResourcePacks`.

   Insert `"file/ATM x MSD [v4.0].zip"` either:
   - **after `"file/PlanetaCobblemon RP.zip"`:** no new fault; Eeveelution posers change; or
   - **after `"cobblemon:regionbiasforms"`:** Cobbleverse's slot; Iron Hands is mis-textured.

   Add a `pack_overrides` title and credit for it. The `"file/ATMxMSD RP.zip"` override then has no file, which is
   harmless.
4. **`modpack/config/README.md`:** its paragraph on why ATMxMSD is disabled.
5. **Nothing on the server.** COBBLEVERSE-DP already implements the species. v4.0's `data/` must not go into the
   world's datapacks: it carries 155 `species_additions`, 151 spawn-pool files and reworked spawn weights.
6. **Then:**
   - rebuild the Cobblemon-only fix pack from an instance with v4.0 enabled, for Appletun;
   - drop the AllTheMons subset from ADR-006's server pack.

### NOT VERIFIED (needs the running client)

- That v4.0 loads without a reload failure on the real stack. Look in `latest.log` for resolver, poser or JSON
  errors, especially brutebonnet and fearow.
- That the 11 table species render, animate and show their shiny and emissive layers. The first ones to look at:
  Vullaby, Greavard in the Route 1 mansion, Vikavolt (emissive), Bombirdier.
- Iron Hands at whichever position is chosen; Eeveelution animations if v4.0 goes above PlanetaCobblemon.
- Mega Mewtwo X and Y and a ZAMegas mega (Zeraora); Mega Floette.
- Whether the Resource Pack Overrides mod honours the new order on a fresh install from the `.mrpack`.
- Whether a Modrinth-launcher install puts the file in `resourcepacks/`. The `.mrpack` `path` field decides that;
  no `.mrpack` builder exists in `tools/` yet.

## Commands

Run with the game closed, after any change to the modpack, the resource packs or Cobblemon.

```bash
python tools/client_model_fix.py scan --instance "C:/Users/wnd/AppData/Roaming/ModrinthApp/profiles/Fabric 1.21.10"
```

```bash
python tools/client_model_fix.py scan --instance "C:/Users/wnd/AppData/Roaming/ModrinthApp/profiles/Fabric 1.21.10" --with-pack build/client/cobblers-client-AllTheMons-subset.zip
```

```bash
python tools/client_model_fix.py build --server-pack --instance "C:/Users/wnd/AppData/Roaming/ModrinthApp/profiles/Fabric 1.21.10"
```

- **Exit 0:** nothing uncovered on the effective stack. **Exit 1:** something is uncovered; the JSON lists it.
  `--full` prints every flagged record with its paths and packs.
- **Local test without a server:** `install --zip build/client/cobblers-client-AllTheMons-subset.zip` copies a zip
  into the instance's `resourcepacks/` and puts it at the top of `options.txt`, keeping a backup
  (`options.txt.pre-cobblers-model-fixes`).
- **After a rebuild,** add a row to the incident log and update `server.properties`' `resource-pack-sha1`.
- **Crash of the same kind:** a client crash report with `Can't find part <name>` in a `…Model.<init>` is rule 1. Run
  the scan.

## To test in game

1. Enable the server pack locally (`install`) or through a test server's `server.properties`.
2. Spawn each of these in a singleplayer test world:
   - vullaby, oranguru, greavard, baxcalibur and zeraora, which should no longer be dolls;
   - a jirachi or vikavolt, whose emissive layer should now glow;
   - pidgeot, talonflame and an arbok with a snake pattern, which should now look right;
   - a Hisuian Samurott, whose animation is the part at risk.
3. Confirm Alolan Persian still renders.
4. Record the result in `experiments/`.
