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
