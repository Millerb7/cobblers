# NPC appearance on Cobblemon 1.8.2: a "Brock" look for `cobblers:npc_main_brock_witness`

**Question (2026-10-15):** can a datapack NPC (`cobblemon:npc`) be given a specific appearance, here Brock, with the least
client-side work?
**Answered for:** Cobblemon 1.8.2+1.21.1 Fabric. Builds on `docs/research/notes/npc-skins.md` (answered for 1.8.0).

**How it was read (and what was NOT).** This session had no shell, so the process/port check and the shared lock that
CLAUDE.md requires before touching `cobblers-server` could not be done. The live server folder (and so the 1.8.2 jar) was
therefore **not read**. Every Cobblemon quote is from the GitLab source at tag `1.8.2`
(`https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.2/common/src/main/...`) fetched through a summarising web fetch: short
lines are as returned, but treat each as "source via fetch", not byte-checked against the jar. The RP entry name was
grepped from the local zip (entry names are stored uncompressed).

## Answers

### 1. Server-side player skin: YES, by Mojang USERNAME, not by URL

VERIFIED (1.8.2 source):

- NPC class JSON has **no** skin/texture field. `NPCClass` fields are: `resourceIdentifier`, `names`, `aspects`, `hitbox`,
  `modelScale`, `battleConfiguration`, `interaction`, `canDespawn`, `variations` (JSON key `variation`/`variations`), `config`,
  `variables`, `party`, `skill`, `autoHealParty`, `randomizePartyOrder`, `battleTheme`, `behaviours` (JSON keys `behaviours`,
  `behaviors`, `ai`), `isMovable`, `isInvulnerable`, `isLeashable`, `allowProjectileHits`, `hideNameTag` (`api/npc/NPCClass.kt`,
  `util/adapters/NPCClassAdapter.kt`); class JSON also reads `presets` (`NPCPresets.getPreset`).
- Command: `/applyplayertexture <player>` (`StringArgumentType.word()`), literal `applyplayertexture`, permission
  `CobblemonPermissions.APPLY_PLAYER_TEXTURE`; the source must be a player and the target is the NPC they are looking at;
  no NPC in line of sight prints `commandLang("npcedit.non_npc")` (`command/ApplyPlayerTextureCommand.kt`). Op level 2 per
  https://www.poketools.com/cobblemon-command/applyplayertexture (unversioned: ASSUMED for 1.8.2).
- Molang (NPC functions): `q.npc.set_player_texture('<username>')` (returns without reloading if it equals the stored
  `player_texture_username`), `unset_player_texture()`, `set_resource_identifier('<ns:id>')`, `unset_resource_identifier()`,
  `add_aspect(...)`, `remove_aspect(...)`, `aspects()` (`api/molang/function/NPCMoLangFunctions.kt`). **No function takes a URL.**
- Underneath: `NPCEntity.loadTextureFromGameProfileName(username)` does a server-side Mojang profile lookup, takes
  `textures.skin!!`, model from skin metadata (`default`/`slim`), then `loadTexture(URI, model)` which reads the URL's bytes
  (`uri.toURL().openStream().readBytes()`), adds aspect `model-default` or `model-slim` and syncs
  `NPC_PLAYER_TEXTURE`. `loadTexture(URI, ...)` is a Kotlin method with no command or Molang entry point, so "texture URL" is NOT
  settable from data. The skin is a **byte snapshot** stored on the entity.
- Rendering: `standard/50_standard_player.json` (order 50), name `cobblemon:standard`: aspect `model-default` -> model
  `cobblemon:steve.geo`, `model-slim` -> `cobblemon:alex.geo`, texture `"variable"`, poser `cobblemon:standard`
  (`assets/cobblemon/bedrock/npcs/variations/standard/50_standard_player.json`). Our classes already name
  `cobblemon:standard`, so nothing else changes on the client. `VariableModelTextureSupplier` falls back to
  `cobblemon:textures/npcs/default.png` when the variable is unset.
- Behaviour `data/cobblemon/behaviours/npc/player_textured.json` exists at 1.8.2: config variable `player_texture` (TEXT,
  default empty, category appearance); `onAdd` sets the player texture and resource identifier `cobblemon:standard` when the
  variable is non-blank, else unsets both; `onRemove` unsets both. (Summarised by the fetch; exact text not quoted.)
- NBT on a spawned entity (`DataKeys.kt`, `NPCEntity.saveWithoutId` / `load`):
  - `NPCPlayerTexture` compound with `Model` (string, enum name `DEFAULT`/`SLIM`/`NONE`) and `Texture` (byte array of PNG
    bytes); written only when model is not `NONE`.
  - `ForcedResourceIdentifier` (string, parsed with `ResourceLocation.parse`).
  - `AppliedAspects` (list of strings; `load` calls `updateAspects()` then `remakeBrain()`).
  - `VariationAspects`.

ASSUMED (not seen working):

- Setting skin on an already-spawned NPC with `data merge entity <sel> {NPCPlayerTexture:{Model:"DEFAULT",Texture:[B;...]},
  AppliedAspects:["model-default"]}`: NBT key names and types are verified above, but whether `data merge` on a loaded
  `cobblemon:npc` re-runs `load` (and so syncs and updates aspects) is untested. The `load` excerpt shown did not set the
  `model-default` aspect, so `AppliedAspects` must be set too or the render falls to `trainer.geo`. A PNG is 1-6 KB, i.e.
  about 4-25 KB of SNBT per line.
- In a class JSON: `"ai": [{"type": "apply_behaviours", "presets": ["cobblemon:npc/player_textured"]}]` plus
  `"config": [{"variableName": "player_texture", "type": "TEXT", "defaultValue": "<username>"}]`. The `ai`, `config` keys and
  the behaviour file are verified; the `apply_behaviours` entry shape and the preset id are inferred from the path (as in
  `npc-skins.md` section 4 step 4) and whether the class default is in place before `onAdd` runs is unknown.
- A Mojang account named like the look exists. Brock's look is not a Mojang account we know; the lookup needs a real
  username with a custom skin and outbound HTTPS from the server at spawn.

### 2. Client resource-pack route

VERIFIED:

- NPC variations are **client assets** read from `assets/<any namespace>/bedrock/npcs/variations/*.json`
  (`VaryingModelRepository`: directory `bedrock/npcs/variations`, `listResources` with no namespace filter; files grouped by
  their `name`, merged, sorted by `order`). Shape (all shipped files, e.g. `50_standard_player.json`):
  `{"name","order","variations":[{"aspects","poser","model","texture","layers"}]}`. A variation applies when all its
  `aspects` are in the entity's aspects. An unknown `name` falls back to `cobblemon:substitute` (green doll).
- A static `texture` is a `ResourceLocation` returned as-is (`StaticModelTextureSupplier`; `NPCRenderer` puts the resolved
  location in the render context without branching on namespace). So a variation CAN name a texture from another namespace.
- The class selects it with `"resourceIdentifier": "cobblers:brock"` (NPCClassAdapter reads it; default `cobblemon:dummy`,
  replaced by the class id on reload).
- The Brock trainer texture is **present** in the Cobbleverse RCTmod RP:
  `assets/rctmod/textures/trainers/single/kanto_brock.png`, entry in
  `C:/Users/wnd/Documents/github/cobblers/COBBLEVERSE/resourcepacks/COBBLEVERSE RCTmod RP.zip` (grep of entry names,
  2026-10-15; twice, local + central directory). Texture location: `rctmod:textures/trainers/single/kanto_brock.png`.
- A minimal pack file would be `assets/cobblers/bedrock/npcs/variations/brock.json`:
  `{"name":"cobblers:brock","order":0,"variations":[{"aspects":[],"poser":"cobblemon:standard","model":"cobblemon:steve.geo","texture":"rctmod:textures/trainers/single/kanto_brock.png","layers":[]}]}`
  (format from shipped files; the specific values are ours, untested).

ASSUMED:

- That the rctmod texture is player-skin layout and wide (not slim) so `steve.geo` maps it correctly. rctmod docs say textures
  are "structured the same as player skins" (https://srcmc.gitlab.io/rct/docs/latest/configuration/resource_pack/textures/,
  unversioned). The PNG was not viewed (zip contents are deflated, no shell).
- That the texture string accepts a non-`cobblemon` namespace in the JSON adapter (`ModelTextureSupplierAdapter`, not read).
- That the RP is enabled on every client (`modpack/config/resourcepackoverrides.json` lists it per `npc-skins.md`), so no
  art needs to be copied; only the one JSON.

### 3. Which route needs no new file on players' clients

- **Server-side player texture (route 1)**: nothing on the client. The server syncs the PNG bytes and the `model-default`
  variation is in the Cobblemon jar already (VERIFIED). Cost: it needs a PNG source.
- **Route 2** needs one small JSON in a client resource pack (a new file to ship), but no art.
- No route makes Brock look like Brock with zero client files AND zero art transfer except a Mojang account with that skin
  (ASSUMED to exist; owner decision).
- Injecting `kanto_brock.png` bytes via NBT is a zero-client-file route, but the PNG would come from the no-redistribution
  Cobbleverse RP and CLAUDE.md allows only MIT-style sources in git; it could only live in a gitignored local file.

## Recommendation

Route 2 (variation JSON + `"resourceIdentifier": "cobblers:brock"`) is the least work that gives the actual Brock art, if a
client pack carrying one JSON is acceptable. If not, route 1 with an owner-controlled Mojang account carrying the wanted
skin: `/applyplayertexture <account>` while looking at the NPC for the proof; in a function, `runmolang
"q.npc.set_player_texture('<account>');" ...` after `spawnnpcat` (command form from `tools/arena_runtime.py:590-591`).

## Experiment candidates (not added to the backlog by this note)

1. Hand-check on `npc_main_brock_witness`: `/applyplayertexture <a custom-skin account>`. Pass: skin appears; persists after unload.
2. `data merge entity` with `NPCPlayerTexture` + `AppliedAspects:["model-default"]` using a tiny PNG. Pass: renders; fail:
   Steve, then try `/runmolang`.
3. One variation JSON as in section 2 in a local resource pack plus the class `resourceIdentifier`. Pass: Brock art on
   `steve.geo`; check arms (wide vs slim) and that the unknown-name fallback is not hit.
4. Class-level `player_textured` behaviour with `config` default (open from `npc-skins.md`).
