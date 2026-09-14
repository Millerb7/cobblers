# Client model fixes: resource packs vs Cobblemon 1.8 posers

**Status: patch installed on the authoring client 2026-09-14.** Not yet confirmed in game:
the next session should see an Alolan Persian render without a crash.

## Incident log

| Date | What happened | Evidence | Action |
| --- | --- | --- | --- |
| 2026-09-14 | Screen went black while flying the painted `cobblers-10240`. The server logged the player as "Disconnected" | Client crash report `crash-2026-09-14_07.51.45-client.txt`: `java.util.NoSuchElementException: Can't find part persian` in `PersianAlolanModel.<init>`, while rendering a wild Persian at 3076, 114, 4837. Not related to the terrain or the paint | Scanned the enabled pack stack; built and installed `cobblers-model-fixes.zip` |

## Cause

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

**Models are keyed by file name**, and the highest-priority pack that ships the file wins.
COBBLEVERSE RP ships models made for Cobblemon 1.7. For Alolan Persian its root bone is
`persian_alolan`, while 1.8's built-in poser asks for `persian`.

## Rule used by the scan

**A form is flagged when all of these hold:**
1. a resource pack supplies its `.geo.json`;
2. no JSON poser for it exists anywhere in the stack (jar or packs), so the built-in poser is used;
3. the pack's model lacks a non-locator part that Cobblemon's own model has.

**Two limits on the rule:**
- It is conservative: a missing part is flagged even if the built-in poser happens not to look it
  up.
- The built-in-poser check matches class names, which is approximate.

## Flagged on 2026-09-14

**Stack:** Cobblemon 1.8.0 client with the Modrinth profile "Fabric 1.21.10" pack order;
327 geometry ids overridden by packs.

| Form | Pack | Missing parts | Fix |
| --- | --- | --- | --- |
| persian_alolan | COBBLEVERSE RP | root `persian` (confirmed crash) | Cobblemon's model restored |
| granbull | COBBLEVERSE RP | item_hat, left_pupil, right_pupil | Cobblemon's model restored |
| ironleaves | COBBLEVERSE RP | leg_back_left, leg_back_right | Cobblemon's model restored |
| stoutland | COBBLEVERSE RP | seat_1_locator | Cobblemon's model restored |
| tangrowth | COBBLEVERSE RP | eye_left, eyelid_left, eye_right, eyelid_right | Cobblemon's model restored |
| vileplume | COBBLEVERSE RP | head_locators, arms, legs | Cobblemon's model restored |
| yanmega | COBBLEVERSE RP | eyes | Cobblemon's model restored |

**What the fix changes:**
- For all seven, the packs override only the model file; textures and animations already come
  from Cobblemon. Restoring Cobblemon's model keeps model, texture and animation consistent.
- **The trade:** these seven show Cobblemon's models instead of COBBLEVERSE RP's.

**Checked and deliberately not patched:** exeggutor_alolan, silcoon, typhlosion_hisuian,
zoroark_hisuian, samurott_hisuian and dartrix_hisui_bias also have root-bone mismatches, but a
JSON poser covers each of them (Cobblemon's own, COBBLEVERSE RP's or CobbleMotion RP's). JSON
posers fall back instead of crashing. Replacing those models could break CobbleMotion's
animations.

## Patch

**File:** `cobblers-model-fixes.zip`, built by `tools/client_model_fix.py build` from the
local Cobblemon jar.
- It contains only Cobblemon's own `.geo.json` files at the paths the packs use, plus
  `cobblers-model-fixes.json` recording what was flagged.
- It is never committed: it holds Cobblemon assets.

**Installed on 2026-09-14:**
- the pack copied to `…/profiles/Fabric 1.21.10/resourcepacks/`;
- `file/cobblers-model-fixes.zip` appended as the last (highest-priority) entry of
  `options.txt` `resourcePacks`;
- backup: `options.txt.pre-cobblers-model-fixes`.

**Not verified:** whether the Resource Pack Overrides mod reorders packs at launch.
COBBLEVERSE RP has `"default_position": "TOP"` in `config/resourcepackoverrides.json`. If the
fix pack is not above COBBLEVERSE RP in the in-game pack screen, move it up.

## Recheck after every update

**Run this after any change to the modpack, the resource packs or Cobblemon, with the game
closed:**

```bash
python tools/client_model_fix.py scan --instance "C:/Users/wnd/AppData/Roaming/ModrinthApp/profiles/Fabric 1.21.10"
```

**Reading the result:**
- **Exit 0:** every flagged form is covered by the installed fix pack, and it is on top.
- **Exit 1:** something is uncovered. Rebuild and reinstall:

```bash
python tools/client_model_fix.py build --instance "C:/Users/wnd/AppData/Roaming/ModrinthApp/profiles/Fabric 1.21.10"
```

```bash
python tools/client_model_fix.py install --instance "C:/Users/wnd/AppData/Roaming/ModrinthApp/profiles/Fabric 1.21.10"
```

**Then add a row to the incident log above,** including anything newly flagged or no longer
flagged. When a pack update fixes its models, the scan stops flagging them and the rebuilt fix
pack shrinks.

**Crash of the same kind:** a client crash report with `Can't find part <name>` in a
`…Model.<init>` is this problem. Run the scan.
