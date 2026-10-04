# The far south: five places in the emptiest southern cells

Built 2026-10-04 against `docs/world-building/SOUTH_DENSITY.md`. Data `data/far_south.json` (hand-authored), caches
in `data/rewards.json`, generator `tools/far_south.py` -> `build/datapacks/cobblers_far_south` (world-local: its keeper
spawns Pokemon), re-apply steps **R9FS** (blocks, after R9NR and before R9E) and **R18FS** (after R18NR; empty while
all three residents are gated). Builder's tests: `tests/test_far_south.py`. **Not audited, not applied, not seen in
game.**

Every part is the southern and northern residents' machinery, called rather than copied: their block pieces
(structure on a levelled floor, top-block surface, blocks on their own column's ground, ring), their record checks and
`tools/resident_encounters.py`'s keeper (dormant until the trigger, leashed, respawned on a 36,000-tick clock, never
spawned in sight, left alone once the blackout makes it a guardian). No NPCs. Ground is `tools/ground.py`'s.

| Place | Cell, sub-region | Centre (ground) | What a player finds |
| --- | --- | --- | --- |
| **Kraal Number Three** | F3, Arrow Creeks savanna | (2808, 5760), y107 | A ring wall of field stone 22 across, a gate between lantern posts, a trough, the last bale and an acacia split by lightning. **Greymane**, a Zebstrika, L57, holds it (trigger 12, leash 20). |
| **the Four Chimneys** | F6, Plateau South (badlands eroded) | (5176, 5968), y158 | Four banded terracotta hoodoos under red sandstone caprocks, a dry wash, a survey cairn that says FOUR and a sign beside it that says FIVE. **The Fifth Chimney**, a Crustle, L56 (trigger 9, leash 16). Cache `far_south_hoodoo_tin` at the tall chimney's foot: Smooth Rock, 2 Dusk Balls. |
| **the Glass Garden** | G6, South-East Dunes | (5976, 6544), y122 | Rays of lightning-fused glass in the dune top and seven glass spires, the tallest five high; a glass-cutter's sandstone shade with a grindstone and a lantern. Cache `far_south_glass_cutters_box` in its floor: Thunder Stone, Soft Sand. |
| **the Watcher's Ring** | G7, South-East Dunes | (7056, 6200), y149 | Eight sandstone standing stones with glyph heads round a smooth floor, a caravan sign: DO NOT STEP BETWEEN THE STONES. **The Old Watcher**, a Sigilyph, L58: the trigger (8) is the stones' radius, so obeying the sign means never meeting it (leash 14). |
| **the Lady's Folly** | H3, Sunset East meadow | (2904, 7632), y93 | A raised round floor with eight pale columns (two broken, one gone at the step), lanterns on two, empty flower pots round a pedestal: HER GARDEN. the bees kept it after her. Cache `far_south_folly_cellar` under a floor stone: Leaf Stone, Miracle Seed. No Pokemon: Sunset Isle's one heart is the Old Orchard's. |

The three residents are tier 8 and gated after gym 7 (a presence gate, as Ash's); their levels sit over the cap before
gym 8 (55) and within tier 8's ceiling of 60, so the level-cap refusal is the catch gate. That the cap after the eighth
badge is 60 is RELAYED from `data/encounter_design.json` rules.hearts.next_cap, not measured. Every species is on its
sub-region's list in `docs/story/ENCOUNTERS.md`, and every species and item id was checked against
`Cobblemon-fabric-1.8.0+1.21.1.jar` on 2026-10-04.

## The caches' `items_hook`

Each cache record in `data/far_south.json` carries `items_hook` (`open`, the reward id, what fits the place). The
obtainability sweep (`docs/STATE.md`: every Cobblemon item obtainable without crafting) may add an item with no natural
source to that reward's `contents` in `data/rewards.json`, if it fits; nothing else needs to change.

## The builder's guards (fail the build; not an audit)

Rows F-H only; 96 from every x/z any other data file authors and every route corridor box; outside towns (+96), Rift
zone boxes, and a keep-out box over the Rift's southern arms and the Mega field ([3244, 3460, 4923, 5707]); centre,
anchors and caches 128 from every route path; leash clear of activated Habitat Blocks; level within the tier ceiling;
no spawn-condition block; the recorded anchors, cache containers and bboxes equal to what the heightmap gives.
Measured by `--report`: every site's nearest authored point is 202-371 blocks away; the nearest route path 585-1,547.

## Owed

- **The independent audit** (`tools/far_south_audit.py`, another agent), to `data/far_south.json` audit_checklist; then
  its prepare job after `far_south` in `tools/reapply.py`, and these sites in `tests/test_resident_siting.py`'s set.
- **In game**: that the five builds land on their ground at the coordinates above, that each cache grants once, that
  each resident appears after gym 7 and wakes at its trigger. None of it has been run.
- **Findability**: all five are 585+ blocks from a route, by design (the emptiness is between the roads). Nothing points
  to them yet; a signpost or a rumour line is a separate decision.
