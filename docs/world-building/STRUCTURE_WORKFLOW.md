# Structure placement and editing workflow

## Tool decision

Use vanilla `/place template`, `/place structure`, structure blocks, and the
installed Huge Structure Blocks mod for the first prototype pass. Huge Structure
Blocks raises structure-block dimensions and offsets to 512 blocks and jigsaw
depth/distance to 512; runtime use of those extended limits still needs a client
test. WorldEdit would materially improve palette replacement, selections, undo,
and schematic handling during sustained regional construction. Axiom would add a
strong visual editor, but neither tool is installed and this task does not add one.

Adopt WorldEdit only in a later development-tool experiment that checks loader
compatibility, server/client scope, export format, and whether builders actually
prefer it. Keep vanilla NBT as the canonical artifact whenever it preserves all
required block entities.

## A. Exact reuse

1. Confirm the ID in `structure-dependencies.json` and ensure its source component
   is active in the same runtime.
2. Create or reset a disposable Creative build world.
3. Load enough surrounding chunks. Large jigsaw structures needed a 15×15 forced
   chunk square in the headless proof.
4. For raw NBT use:

   ```mcfunction
   /place template <namespace:path> <x> <y> <z> <rotation> <mirror> 1.0 <seed>
   ```

   Verified transform values include `none`, `clockwise_90`, `180`, and mirrors
   `none`, `front_back`, `left_right`.
5. For a registered worldgen structure use:

   ```mcfunction
   /place structure <namespace:path> <x> <y> <z>
   ```

   This route applies the structure's jigsaw, biome, terrain, projection, and
   processor behavior. It does not expose a direct rotation/mirror argument.
6. Inspect terrain seams, jigsaw joins, functional blocks, entities, loot, and
   orientation in a client. Run `save-all flush`, restart, and inspect again.
7. Connect roads and terrain only after the structure passes.

## B. Regionalized reuse

1. Place the upstream template in a disposable build world.
2. Record the source catalog ID, license, dimensions, block entities, entities,
   jigsaws, processors, and required components.
3. Duplicate it into a separately named `campaign:<path>` working copy only when
   the upstream license permits derivative files.
4. Change exterior palette, roof, foundation, landscaping, signage and local
   furniture. Preserve PCs, healers, shops, Waystones and jigsaw connectors unless
   the variant explicitly replaces their function.
5. Remove embedded upstream trainers, progression triggers and loot when campaign
   systems own those behaviors.
6. Save/export the result under `kits/structures/campaign/`, add a
   `campaign_structures` manifest entry with `based_on`, `asset`, and
   `required_components`, then run validation.
7. Place, rotate, mirror, restart, and visually inspect the exported campaign copy.

## C. Extracting a worldgen structure

1. Prefer the shipped raw NBT and template-pool pieces. Worldgen output may include
   random pieces, processor substitutions, terrain adaptation and entities that no
   single template contains.
2. If the assembled result is needed, locate or `/place structure` it in a fresh
   survey world with the original biome/dimension and a recorded seed.
3. Mark an exact bounding box and inventory all entities and functional block
   entities before export.
4. Use a structure block/Huge Structure Blocks when the selection fits. Split a
   larger build into named pieces with stable anchors rather than one opaque file.
5. Preserve jigsaw blocks only if the campaign copy will remain modular. Otherwise
   replace connectors after assembly and save the finished geometry.
6. Record processors whose output has already been baked into the copy. Never
   assume `/place template` reproduces a registered structure's terrain checks.
7. Do not extract non-redistributable Cobbleverse/Lumyverse content into Git.

## Placement proof (2026-09-09)

Runtime: Minecraft 1.21.1, Fabric 0.19.5, Cobblemon 1.8.0, 101-server-jar
overlay, disposable flat world `structure-proof`.

| Structure | Placement | Rotation | Mirror | Blocks complete | Entities complete | Functional elements | Editable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `cobblemon:village_plains/village_plains_pokecenter` | PASS via `/place template` | PASS (90° command accepted) | PASS (`front_back` accepted) | UNKNOWN pending visual inspection | N/A/UNKNOWN | UNKNOWN; PC/healer not operated | YES |
| `bca:default/one_off/small_battlepad` | PASS via `/place template` | PASS (90°) | PASS (`left_right`) | UNKNOWN pending visual inspection | UNKNOWN | N/A | YES |
| `bca:default/one_off/structure_pokemart` | PASS via `/place template` | PASS (90°) | NOT APPLICABLE in run | UNKNOWN pending visual inspection | UNKNOWN | UNKNOWN; shop behavior not exercised | YES |
| `cobbleverse:brock` | PASS via `/place template` | PASS (`180`) | NOT APPLICABLE in run | UNKNOWN pending visual inspection | UNKNOWN | UNKNOWN; embedded trainers not exercised | WITH CARE |
| `legendarymonuments:firescourge_shrine` | PASS via raw `/place template` | PASS (90°) | PASS (`front_back`) | UNKNOWN pending visual inspection | UNKNOWN | UNKNOWN | WITH CARE |
| BCA small villages (`default_small`, `fighting_small`) | PASS via `/place structure` | internal jigsaw only | internal jigsaw only | PARTIAL | UNKNOWN | PARTIAL; missing-pool warnings | component pieces only |

The same world saved, stopped cleanly, restarted to `Done (1.315s)`, and stopped
cleanly again. This proves persistence did not prevent reload; it does not prove
that every placed block/entity survived correctly. The registered Firescourge
placement resolved but rejected the flat test site in its terrain validator, while
direct raw-template placement passed. This demonstrates why registered and raw
placement must be tested separately.

## WorldPainter boundary

```text
regional plan (Inkarnate or equivalent)
  -> WorldPainter: landmass, elevation, mountains, rivers, coasts, biome masks, broad forests
  -> Minecraft editing: roads, town pads, terrain seams, detailed vegetation, structure placement
  -> upstream structure library: Centers, Marts, village pieces, route landmarks
  -> campaign assets: Gym interiors, villain bases, dungeons, labs and story landmarks
```

Keep WorldPainter sources and masks under `source/`, which lives outside this repository (see `data/notes/source_tree.md`). Do not bake trainers,
PC state, loot, puzzle state, progression, or automatically generated settlements
into the terrain source. Generate terrain first, then place reviewed structures in
Minecraft so their state and dependencies remain inspectable.

## Readiness

**READY TO BUILD STRUCTURE PROTOTYPES.** Vanilla template placement and transforms
have functional headless evidence. The minimum blocker for permanent campaign
construction is the unfinished world-critical dependency freeze plus client visual
and functional inspection of the chosen prototype.
