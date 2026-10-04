# NPC skins: why our characters look like Steve, and what each system supports

**Question (the owner, 2026-10-03):** "look into making the characters not Steve default skin if we can."
**Answered for:** Cobblemon 1.8.0+1.21.1 (tag `1.8.0` on GitLab, and the jar
`experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods/Cobblemon-fabric-1.8.0+1.21.1.jar`); rctmod
0.19.0-beta source (tag `v0.19.0-beta`) with the 0.18.1 jar as the local asset check
(`C:/Users/wnd/Documents/github/cobblers/COBBLEVERSE/mods/rctmod-fabric-1.21.1-0.18.1-beta.jar`; the server runs 0.19.0,
`modpack/manifest/overlay.json:138-149`); the Cobbleverse client resource packs in
`C:/Users/wnd/Documents/github/cobblers/COBBLEVERSE/resourcepacks/`.

**How it was read.** Jar and zip entry NAMES were grepped (they are stored uncompressed); file CONTENTS inside a jar are
deflated and could not be read without a shell, so every content quote below comes from the GitLab source at the
matching tag, fetched through a summarising web fetch. The quoted JSON and Kotlin lines are short and were returned as
code, but treat any single quote as "source, via fetch" rather than byte-checked. Two PNGs were viewed as images.

## 1. Who renders as what today

| Character | System | What the client is asked for | What it looks like |
|---|---|---|---|
| Settlement, quest, ferry, market, camp NPCs (`tools/compile_dialogue.py` and everything that compiles through `compile_conversation`) | Cobblemon NPC class | `"resourceIdentifier": "cobblemon:standard"` (`tools/compile_dialogue.py:67`, `:381`) | **Steve.** See 1a |
| Heaven's Arena opponents (19 classes, `tools/arena_runtime.py:251-258`) | Cobblemon NPC class | no `resourceIdentifier`, so the class id `cobblers:<class>` (EXP-051 rule) | **the green substitute doll**, by the rule; not seen in game by this research |
| Route, VR, late-route, mansion, arena rctmod trainers (63 `skin` values in `data/*.json`) | rctmod | the trainer id, looked up client-side; our `textureResource` is ignored (1c) | **one shared default skin** for every trainer whose id is ours; contents of that skin not seen (1c) |
| Gym leaders, E4, Champion (upstream ids `kanto_*`) | rctmod | upstream id | their own Cobbleverse textures (`COBBLEVERSE RCTmod RP.zip` has `kanto_brock.png`, `kanto_misty.png`, ...) |
| Rift guards | vanilla armour stands (`tools/rift_zones.py:2025-2027`) | none | a bare armour stand, not Steve |

### 1a. Why the settlement NPCs are Steve -- VERIFIED

- `cobblemon:standard` with no aspects resolves to `assets/cobblemon/bedrock/npcs/variations/standard/0_standard_base.json`
  (order 0): model `cobblemon:trainer.geo`, texture `cobblemon:textures/npcs/standard/trainer.png`, poser
  `cobblemon:standard`. Source: `.../-/raw/1.8.0/common/src/main/resources/assets/cobblemon/bedrock/npcs/variations/standard/0_standard_base.json`.
- **`trainer.png` IS a Steve skin**: viewed as an image (1.3 KB, tag 1.8.0): brown hair, teal shirt, blue-purple
  trousers, Steve's layout. So EXP-051's fix (doll to "Cobblemon's generic trainer") turned every NPC into Steve. Nothing
  is broken; it is simply the only generic look Cobblemon ships.
- Cobblemon 1.8.0 ships exactly three NPC textures (jar entries): `textures/npcs/default.png`,
  `textures/npcs/sacchi/sacchi.png`, `textures/npcs/standard/trainer.png`; four models: `alex.geo`, `steve.geo`,
  `sacchi.geo`, `trainer.geo`; four variation files: `npc.json` (same trainer/Steve look), `sacchi/0_sacchi.json`,
  `standard/0_standard_base.json`, `standard/50_standard_player.json`. **There are no per-role textures to choose
  from in Cobblemon itself.**
- The `standard` class's `variation` block (`dirt`: clean..filthy; `net`: green 10 / blue 5 / red 1) and names
  Red/Green/Blue/Yellow (`data/cobblemon/npcs/standard.json` @1.8.0) give aspects, but the only shipped variation with a
  non-empty aspect list in `0_standard_base.json` is `hasty` (poser only). Dirt and net aspects change nothing visible
  with the shipped assets (ASSUMED: no other variation file reacts to them; none is in the jar's entry list).
- No Cobbleverse resource pack ships a `bedrock/npcs/` or `textures/npcs/` file (grep of entry names in every zip under
  `COBBLEVERSE/resourcepacks/`, no match), so nothing shadows this.

### 1b. The arena classes -- VERIFIED rule, ASSUMED outcome

`npc_class()` at `tools/arena_runtime.py:254-258` emits no `resourceIdentifier`. By the rule EXP-051 read from the jar
(`experiments/EXP-051-npc-models/README.md:14-21`) the client is asked for a variation named after the class and falls
back to `cobblemon:substitute`. `tools/npc_model_audit.py` would report each one. Whether the owner saw dolls at the
arena is not recorded; the render is the test.

### 1c. rctmod: our authored `skin` is dead data -- VERIFIED in source

- `TrainerMobData.java` @v0.19.0-beta: `@JsonExclude private RLWrapper textureResource;` -- the JSON key our
  generators write (`tools/route_trainers.py:336`, tested at `tests/test_route_trainers.py:73`,
  `tests/test_mansion_guardians.py:234`) is **excluded from deserialisation**. The constructor default is
  `rctmod:textures/trainers/default.png` (`PATH_DEFAULT = "trainers/default"`).
- `onLoad` sets the texture from `dpm.findResource(trainerId, "textures")`, and `DataPackManager` registers that
  context as `new DataLocator(PackType.CLIENT_RESOURCES, ".png")`. `findResource` tries
  `rctmod:textures/trainers/single/<trainerId>.png`, then the longest group `textures/trainers/groups/<g>.png` where
  `trainerId.equals(g) || trainerId.startsWith(g + "_")`, then the default.
- Our ids (`route_01_trainer_01`, ...) match no single texture in the 0.18.1 jar or in `COBBLEVERSE RCTmod RP.zip`,
  and neither ships any `groups/` texture. So every seated trainer of ours gets `trainers/default.png`.
- That default is overridden on our clients: `COBBLEVERSE RCTmod RP.zip` ("Improved Skins for Trainers") ships its own
  `assets/rctmod/textures/trainers/default.png`, and it is in the default pack list (`modpack/config/resourcepackoverrides.json:49`, `:58-61`).
  rctmod's own default (fetched, 6.2 KB) is a capped trainer in blue, not Steve. **Cobbleverse's replacement was not
  viewable (zip contents compressed): UNKNOWN whether it is Steve.**
- All 18 distinct `skin` files we name do exist in the 0.18.1 jar (`assets/rctmod/textures/trainers/single/...`,
  e.g. `worker_braden_0460.png`, `hiker_nob_00b7.png`, the five channelers). ASSUMED present in 0.19.0 too.
- rctmod docs: textures "are structured the same as player skins"; a trainer without one "will use the default
  texture"; textures live in a resource pack (https://srcmc.gitlab.io/rct/docs/latest/configuration/resource_pack/textures/).

## 2. What each system supports for a look

### Cobblemon NPC, server-only: player textures -- VERIFIED in source @1.8.0

- `NPCPlayerTexture(texture: ByteArray, model: NPCPlayerModelType)`, model `DEFAULT | SLIM | NONE`
  (`entity/npc/NPCPlayerTexture.kt`). The PNG bytes live on the entity, are synced as entity data
  (`NPC_PLAYER_TEXTURE`, `NPCPlayerTextureSerializer`) and saved in entity NBT (`DataKeys.NPC_PLAYER_TEXTURE`, with
  model and byte-array sub-keys; exact key strings not read). **The client needs no file: the server sends the skin.**
- `NPCEntity.loadTextureFromGameProfileName(username)`: server `profileRepository.findProfilesByNames` then
  `sessionService.fetchProfile` / `getTextures`, `textures.skin!!`, model from the skin metadata, then
  `loadTexture(URI(url), model)`, which reads the URL's bytes, adds aspect `model-default` or `model-slim`, and calls
  `updateAspects()`. So: Mojang lookup by **username**; needs outbound network from the server; an account with no
  custom skin hits `skin!!` (ASSUMED to fail that lookup).
- With aspect `model-default`/`model-slim` on a `cobblemon:standard` NPC, `standard/50_standard_player.json` (order 50)
  wins: model `cobblemon:steve.geo` / `cobblemon:alex.geo`, texture `"variable"` (the synced bytes). Our settlement
  classes already name `cobblemon:standard`, so they need nothing else.
- Three ways in:
  1. Command `/applyplayertexture <player>` (`command/ApplyPlayerTextureCommand.kt`): source must be a player
     (`playerOrException`) and it targets `player.traceFirstEntityCollision(NPCEntity)` -- the NPC the op is looking
     at. Permission `CobblemonPermissions.APPLY_PLAYER_TEXTURE` (op level 2 per https://www.poketools.com/cobblemon-command/applyplayertexture, unversioned: ASSUMED).
  2. Molang `set_player_texture(username)` / `unset_player_texture()` in `api/molang/function/NPCMoLangFunctions.kt`;
     also `set_resource_identifier(id)`, `unset_resource_identifier()`, `add_aspect`, `remove_aspect`, `has_aspect`.
     No function in that file takes a URL.
  3. Behaviour `data/cobblemon/behaviours/npc/player_textured.json`: declares config variable `player_texture`
     (TEXT, default `""`, category appearance); `onAdd`: if not blank, `q.entity.set_player_texture(...)` and
     `q.entity.set_resource_identifier('cobblemon:standard')`; if blank, `unset_resource_identifier()` and
     `unset_player_texture()`. `onRemove` unsets both. This is what the `/npcedit` GUI exposes.
- A class's own `config` is appended after its behaviours: `NPCBrain.configure` builds
  `autoNPCBehaviours + npcClass.behaviours + AddVariablesConfig(npcClass.config)` (`entity/npc/NPCBrain.kt` @1.8.0),
  and `initializeScripting` fills each registered variable not yet in `config` with its default
  (`entity/MoLangScriptingEntity.kt`). Whether a class-level `player_texture` default is in place before the
  behaviour's `onAdd` runs was **not** established: see experiment 4.
- `runmolang <molang> [player] [npc]` binds `q.npc` (`docs/research/notes/arena-per-player-opponents.md:131`) and is
  in use in game (`tools/arena_runtime.py:590-591`). ASSUMED that `q.npc` carries the `NPCMoLangFunctions` map
  (`start_battle` is not in that file, so `q.npc` aggregates more than one map).

### Cobblemon NPC, client pack: our own variations -- format VERIFIED from shipped files, cross-mod use ASSUMED

A variation file is a client asset under `assets/<ns>/bedrock/npcs/variations/` with
`{"name", "order", "variations": [{"aspects", "poser", "model", "texture", "layers"}]}` (all four shipped files).
A file such as `assets/cobblers/bedrock/npcs/variations/hiker.json` naming `cobblers:hiker`, model
`cobblemon:steve.geo`, poser `cobblemon:standard`, texture `rctmod:textures/trainers/single/hiker_nob_00b7.png`, with the
class's `resourceIdentifier` set to `cobblers:hiker`, would give a role look from art every client already has (rctmod
is a client mod in our pack). ASSUMED: that the variation loader reads other namespaces (the Pokemon one does) and that
a player-skin-layout rctmod texture maps onto `steve.geo` (designed for player skins). It needs a client resource pack;
nothing is copied, so no art licence question arises.

### rctmod trainer, client pack only -- VERIFIED

The only lever is a client resource asset at `assets/rctmod/textures/trainers/single/<our trainer id>.png` or
`.../groups/<prefix>.png`. That means copying an rctmod (or Cobbleverse) PNG under a new name into a pack we ship:
redistribution of their art; licence not checked here. A group per prefix (`route_01.png`, ...) keeps it to a
handful of files.

## 3. Options, ranked (cheapest durable first)

1. **Server-only Mojang skins on the settlement NPCs, via `runmolang` after each spawn.** In each placement function,
   after `spawnnpcat`, `runmolang "q.npc.set_player_texture('<username>');" @s <that npc>` (or, if experiment 4 shows it
   works, the `player_textured` behaviour plus a class `config` default). Cost: data and generator change, datapack
   reinstall and restart (classes load at boot, EXP-051 line 41-43), a re-apply of the placement functions; **no client
   change**. Needs: outbound HTTPS from the server at spawn, and a chosen username per role whose current skin fits
   (the bytes are a snapshot, so a later skin change does not follow). Owner decision: whose accounts -- not players'
   names in tracked docs (`.claude/rules/security.md`); an owner-controlled account per look is cleanest.
2. **Hand-applied `/applyplayertexture` by an op** looking at each NPC. Zero code, minutes per town, persists in NBT --
   but lost whenever a re-apply kills and re-summons the NPC, and useless for the arena's per-fight spawns. Best as the
   proof (section 4), not the route.
3. **Client pack of role variations on rctmod art** (2, "client pack"). Best result (1,600 role-named outfits: hiker,
   worker, scientist, fisherman, channeler, ...), offline, deterministic, works for per-fight arena spawns. Cost: a
   new authored resource pack folder (JSON only) every player must install and enable, a class field per NPC, restart.
   Waits on ADR-006's client-pack route.
4. **rctmod textures by id** for our 63 route trainers: client pack with copied PNGs, licence check first. Separate
   from the settlement question; the `skin`/`textureResource` fields should be either wired this way or recorded as
   inert.

Not routes: Cobblemon's `standard` aspects (no shipped art), `sacchi` (one named character), `set_resource_identifier`
to a Pokemon id (renders a Pokemon), NBT-injected texture bytes in `/summon` (key strings unread; kilobyte lines).

**Recommended:** prove the render path with option 2 on one NPC; if it shows a skin, take option 1 for settlement and
quest NPCs and add `"resourceIdentifier": "cobblemon:standard"` to the arena classes in the same pass (fixes the doll;
their per-fight spawns get a skin only through the `runmolang` line in `venue/<v>/spawn`, at one Mojang lookup per fight
-- ASSUMED acceptable, rate limits unchecked). Option 3 is the upgrade if the owner wants role outfits rather than
borrowed player skins.

## 4. In-game proof (staging, op)

1. Stand at Hollis (1512 163 1411), look at him, `/applyplayertexture <a username with a custom skin>`. **Pass:** the
   NPC changes from Steve to that skin within a second, same height and name tag. **Fail:** no change, an error, or the
   substitute doll.
2. Walk away until the chunk unloads, return (or restart). **Pass:** the skin is still there (NBT round trip).
3. On a second NPC: `/runmolang "q.npc.set_player_texture('<username>');" @s @e[type=cobblemon:npc,sort=nearest,limit=1]`.
   **Pass:** same result as step 1, from a command a function can carry.
4. Disposable probe class with `"ai": [{"type": "apply_behaviours", "presets": ["cobblemon:npc/player_textured"]}]`
   and `"config": [{"variableName": "player_texture", "type": "TEXT", "defaultValue": "<username>"}]`, restart,
   `spawnnpcat`. **Pass:** spawns already skinned (then the data-only route works); **fail:** Steve (onAdd ran before
   the class default; use step 3's form).
5. Look at one seated route trainer (e.g. route 1's first) and one gym leader, and write down whether the route one is
   Steve: that settles what Cobbleverse's `default.png` is.

## Unknown

- Cobbleverse RCTmod RP's `default.png` (what all our route trainers wear).
- Whether `q.npc` under `runmolang` exposes `set_player_texture` (step 3).
- Behaviour `onAdd` versus class `config` ordering (step 4); the behaviour id `cobblemon:npc/player_textured` is
  ASSUMED from the path, as `cobblemon:battler` is for `behaviours/battler.json`.
- Whether the server has outbound access to Mojang's profile and texture hosts, and `online-mode` (not read: live
  server).
- The rctmod and Cobbleverse art licences, if option 4 is taken.
