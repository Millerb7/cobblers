# EXP-051: Do our NPCs render as people once their classes name a model?

**Status:** fix built and audited offline 2026-10-02 (`tools/compile_dialogue.py`, `tools/npc_model_audit.py`,
`tests/test_npc_model_audit.py`); not yet seen in game.

## Question

The owner, in staging, of the den keeper Hollis: "hollis is buried and a subsitute dolll". Hollis's column measures
fine (stone at y162 = heightmap ground, a snow layer at y163, air above), so the "buried" look is the small green
substitute doll under a full-height name tag. Does every NPC this repository ships render as a person after the fix?

## Why they were dolls (read from the Cobblemon 1.8.0 jar's bytecode, `Cobblemon-fabric-1.8.0+1.21.1.jar`)

1. `util/adapters/NPCClassAdapter` reads an optional `"resourceIdentifier"` string from the class JSON (namespace
   defaults to `cobblemon`, `ResourceLocationExtensionsKt.asIdentifierDefaultingNamespace$default`).
2. `api/npc/NPCClass`'s constructor sets `resourceIdentifier = cobblemon:dummy`; `api/npc/NPCClasses`, on reload,
   replaces any whose path is `"dummy"` with **the class id**.
3. `entity/npc/NPCEntity` syncs `RESOURCE_IDENTIFIER = forcedResourceIdentifier ?: npc.resourceIdentifier`, in
   `setNpc` and again in `readAdditionalSaveData` (NBT `ForcedResourceIdentifier`, absent on ours).
4. `client/render/npc/NPCRenderer` calls `VaryingModelRepository.getPoser(entity.resourceIdentifier, state)` and
   `getTexture(...)`; an unknown name falls to the resolver of `cobblemon:substitute`.

Our 40 classes carried no `resourceIdentifier`, so each asked the client for a variation named after itself
(`cobblers:npc_ursaluna_den_watcher`), and none exists. Cobblemon's own `sacchi` and `standard` classes are just as
bare and render because variations named `cobblemon:sacchi` and `cobblemon:standard` ship in the jar.

## The fix

Every class `tools/compile_dialogue.py` emits now carries `"resourceIdentifier": "cobblemon:standard"`
(`NPC_RESOURCE`). The ferries (`tools/ferries.py`) and the Frostpeak camp (`tools/frostpeak_camp.py`) compile their
NPCs through `compile_dialogue.compile_conversation`, so the one line covers all three packs: 30 + 7 + 3 = 40 classes.
With no aspects, `cobblemon:standard` resolves (variations `standard/0_standard_base.json`, order 0) to model
`cobblemon:trainer.geo`, texture `cobblemon:textures/npcs/standard/trainer.png`, poser `cobblemon:standard`: Cobblemon's
generic trainer. Every one of our NPCs gets the same look; distinct looks would need our own textures (not cheap).

**Server-side only.** The variation, model, texture and poser are in the Cobblemon jar every client already has, so
nothing new reaches players and no one re-downloads anything. `cobblemon-additions-4.1.6` ships its own
`npcs/posers/standard.json` and `trainer_generic.animation.json`; both are byte-for-byte JSON-equal to Cobblemon's
(checked 2026-10-02). Client resource packs were not available offline to check (see below).

**Existing NPCs need no respawn.** The class is re-applied to an entity on every NBT load (rule 3), so after the
datapacks are installed and the server restarted (NPC classes load at boot), each NPC picks up the model when its
chunk loads. A `/reload` alone does not refresh an entity already in a loaded chunk.

## The check

`python tools/npc_model_audit.py` (default: every pack in `build/datapacks`) applies rules 1-2 to each class, resolves
the name as `VaryingRenderableResolver` does with no aspects, and requires the model, poser and texture to exist in the
jar (plus any `--with` jar or pack zip). It also re-reads the four classes above and fails if their bytecode stops
carrying the rule. Measured 2026-10-02: on the integrating session's pre-fix `build/datapacks`, **40 classes, 40
problems** ("no client variation is named cobblers:..."); on this branch's build, **40 classes, 0 problems**.
`tests/test_npc_model_audit.py` mutates the generator (NPC_RESOURCE to an unknown name; the field stripped from
`compile_conversation`) and each mutation fails every class.

## Probe (for the integrating session)

After `cobblers_dialogue`, `cobblers_ferries` and `cobblers_frostpeak_camp` are rebuilt, installed and the server
restarted, look at each NPC. **Pass:** a full-size person (Cobblemon's generic trainer model, the same for all) standing at
the spot, name tag at head height. **Fail:** the small green doll, or no entity. The list is the placement functions
`tools/reapply.py` uses, printed 2026-10-02 (the Frostpeak camp's three may move with the summit work).

Start with Hollis, then one of each source; the rest only if those pass.

| Source | NPC class (`cobblers:`) | x y z |
|---|---|---|
| ursaluna_cave | `npc_ursaluna_den_watcher` (Hollis) | 1512 163 1411 |
| frostpeak_camp | `npc_frostpeak_camp_halvard` | 714 114 692 |
| frostpeak_camp | `npc_frostpeak_camp_krell` | 708 114 692 |
| frostpeak_camp | `npc_frostpeak_camp_ostrow` | 698 113 707 |
| ferries | `npc_ferry_first_cast` | 1061 63 5352 |
| ferries | `npc_ferry_relic_landing` | 1113 63 5534 |
| ferries | `npc_ferry_sunset_quay` | 2634 64 6521 |
| ferries | `npc_ferry_sunset_south_pier` | 2697 64 6590 |
| ferries | `npc_ferry_sunset_isle_landing` | 2572 63 6899 |
| ferries | `npc_ferry_northeast_landing` | 6605 63 2306 |
| ferries | `npc_ferry_northlight_landing` | 6878 63 1955 |
| npc_seats | `npc_main_pallet_oak` | 1493 118 5317 |
| npc_seats | `npc_main_pallet_maren` | 1472 117 5321 |
| npc_seats | `npc_main_pallet_mina` | 1454 118 5287 |
| npc_seats | `npc_main_misty_relief_clerk` | 1601 108 2801 |
| npc_seats | `npc_main_surge_signal_clerk` | 1685 175 1413 |
| npc_seats | `npc_main_brock_witness` | 1832 142 3661 |
| npc_seats | `npc_main_erika_survey_archivist` | 4309 111 1551 |
| npc_seats | `npc_main_koga_marsh_tracker` | 4643 118 2449 |
| npc_seats | `npc_main_sabrina_pattern` | 6191 95 3394 |
| npc_seats | `npc_main_blaine_crater_analyst` | 6071 108 4992 |
| npc_seats | `npc_main_giovanni_watch` | 3643 114 6497 |
| npc_seats | `npc_main_league_steward` | 3647 89 2490 |
| npc_seats | `npc_main_rift_surveyor` | 3552 112 5334 |
| npc_seats | `npc_stone_tip_displaced_city_mason` | 3323 47 1752 |
| npc_seats | `npc_stone_tip_gorge_hamlet_elder` | 6813 114 4370 |
| npc_seats | `npc_stone_tip_mining_town_foreman` | 6638 138 5708 |
| npc_seats | `npc_stone_tip_northlight_field_hand` | 7247 117 1568 |
| npc_seats | `npc_stone_tip_tea_town_picker` | 2630 115 3583 |
| npc_seats | `npc_stone_tip_the_scar_scavenger` | 2098 281 938 |
| npc_seats | `npc_stone_tip_viltri_light_keeper` | 555 71 4514 |
| scenes | `npc_route1_picnicker` | 1448 123 4831 |
| scenes | `npc_route1_thirsty_stranger` | 1521 123 4461 |
| scenes | `npc_route1_first_cast_fisher` | 1052 65 5349 |
| scenes | `npc_route2_miner` | 1752 139 3528 |
| scenes | `npc_route2_shore_keeper` | 1773 113 3010 |
| scenes | `npc_route3_trail_keeper` | 2195 126 1599 |
| scenes | `npc_route3_courier` | 2190 121 1624 |
| scenes | `npc_route3_guide` | 2016 133 1598 |
| R9F rewards | `npc_vr_abandoned_cut_digger` | 3638 55 2643 |

There is no console-side substitute: the entity NBT stores the class (`NPCClass`), not the synced resource
identifier, so the render is the test.

## ASSUMED, to be checked here

- No client resource pack in the Cobbleverse stack shadows `bedrock/npcs/variations/standard/`, `trainer.geo`,
  `textures/npcs/standard/trainer.png` or the `standard` poser with something broken (not available offline).
- The hitbox and name-tag height are unchanged (`"hitbox": "player"` was already set).

## Result

Not run.

## Decision

Pending the probe.

## Follow-up

- Distinct looks per character would need our own textures on `trainer.geo` or `steve.geo`, shipped in the client
  pack (ADR-006) with a variation file per name; the audit already checks `--with` packs.
