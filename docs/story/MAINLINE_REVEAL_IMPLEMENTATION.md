# Mainline reveal implementation

## What the Pallet and Brock proof strained

- **Gym flags are not readable by the dialogue compiler.** `gym1_cleared` and the later defeat advancements can be documented as required gates and world changes, but native dialogue currently reads only player-scoped `quest_fields`. The source therefore carries a per-player reveal stage while gym flags remain the authoritative badge, chapter, and waystone ledger. Exact post-gym hand-offs require a separate advancement-to-dialogue-field proof.
- **Physical inspection is not a supported condition.** The compiler has item and quest-field predicates, but no coordinate, proximity, block-interaction, or evidence-inspection predicate. Pallet advances through Mina's account at the boundary rather than proving that the player looked at the road seam. Later evidence is authored as a visible object or terrain site and remains non-gating until that mechanism is proven.
- **Separate beat quests could not share an ordered state.** The validator correctly rejects one quest claiming another quest's fields. Pallet and Brock were therefore combined into one `main_worldshift_reveal` quest. The remaining beats extend that one ladder instead of creating a parallel state system.
- **Shared world mutation is outside the proven path.** The compiler rejects world-scoped fields and emits no generic shared-world mutation. Dialogue records what each player knows; structures, actors, route openings, waystones, the crater shutdown, and Hoopa's release remain separately owned world/progression work.
- **NPC placement is not compiled.** The compiler can emit an NPC class and a manual placement command, but the story data cannot select a safe standing block. Every actor needs a verified marker after the relevant town exists.
- **The first Brock entry rule hid its repeat node.** Completing Brock changed the reveal stage, so a stage-gated entry rule redirected every later interaction to the locked line even though the cursor held `brock_repeat`. Brock and all later beats now use one always-read-the-cursor entry rule, start on an explicit locked node, and are unlocked by the prior transition.
- **Runtime evidence remains narrow.** EXP-022 proved the mechanism with one conversation and one player. Compilation proves structure and cursor emission, not these actors, locations, multiplayer behavior, or the advancement hand-offs.

## Gym 1 world-build request

Apply this only after the next re-export and after Pallet's final position is settled. Record every accepted marker or structure in `data/placements.json`; do not edit the live save as source.

### Actor markers

| Actor | Required site | Clear space | Facing and reach | Dialogue dependency | Failure if moved |
| --- | --- | --- | --- | --- | --- |
| Professor Oak | Inside the verified Oak's Lab placement anchored at `(1487, 5309)` | One stable standing block with a `3×3` clear floor area and three blocks of headroom | Face the normal player approach; remain within ordinary interaction distance of the lab's starter/work area | Oak gives the remembered Route 1 directions, then admits the map no longer matches the land | An outdoor or edge placement makes Oak look like he has already inspected the mismatch and weakens the ordinary send-off |
| Mina | At the verified Pallet sign anchored at `(1456, 5287)` | A `5×5` turnout beside the path, including a safe `3×3×3` NPC volume | Face the north exit and the visible exchange seam; keep both in the player's forward view | Mina points out the road ending, missing shoulder/drainage, and abrupt soil join | If she cannot see the seam, her instructions describe evidence somewhere else and the only available inspection cue fails |
| Maren | Beside, not on, the verified lab lane from `(1461, 5318)` to `(1486, 5318)` | A `5×5` waiting area with a safe `3×3×3` NPC volume and at least a two-block path clearance | Face players travelling between Oak's Lab and the north exit | Maren compares the shared wrong map and leaves on the coastal lead | Blocking the lane makes the scene a bottleneck; placing Maren at the boundary collapses Mina's separate evidence role |
| Brock | In the public-facing lobby of the built Brock prefab anchored at `(1838, 140, 3690)`, rotation `180` | A `5×5` dialogue bay with a safe `3×3×3` NPC volume | Place within eight blocks and clear sight of the geology display, while leaving trainer/battle circulation open | Brock points to the joined geology while giving the native eyewitness account | A hidden back-room placement disconnects his public account from its evidence; a battle-floor placement mixes this story dialogue with deferred leader battle dialogue |

Exact Y values and `spawnnpcat` coordinates must be measured from the exported blocks. Structure anchors and terrain estimates are not safe NPC markers.

### Pallet exchange boundary

- Build one readable seam at the north exit, aligned with Mina and the eventual Route 1 departure.
- Reserve a corridor at least `32` blocks long and `12` blocks wide. At least `24` continuous blocks of the join must be visible from Mina without entering a building.
- The Pallet side uses the settled town road/packed soil. The outside uses the native trail and field palette. Meet them abruptly: no graded shoulder, drainage ditch, blended verge, or old wear crossing the join.
- Keep the seam walkable and keep the critical path open by at least three blocks.
- Record a single inspection marker on the seam for a future proximity proof, even though the current dialogue cannot gate on it.
- If the join is blended, hidden behind landscaping, or placed away from the north exit, Mina's lines about an impossible clean join become false and Pallet's first reveal loses its physical evidence.

### Localized damaged-house cluster

- Place exactly three damaged homes on one edge of Pallet, close enough to read as one exchange-boundary accident rather than town-wide destruction.
- Keep the cluster inside an approximate `40×32` block envelope. Use house footprints between `9×9` and `13×15`, separated by three to seven blocks of debris/path space.
- Show three distinct effects: one compressed downward, one sheared at the seam, and one partially buried or struck by displaced native material. Preserve recognizable Pallet construction in every shell.
- One shell may later carry Hank and Lena, but the mainline evidence must remain understandable without starting that optional quest.
- Do not block Oak's Lab, spawn, the waystone, or the three-block northbound path.
- If the damage is spread around town, the approved “mostly intact with localized edge damage” fact fails. If all three houses are generic ruins, the exchange boundary reads as age or attack rather than sudden displacement.

### Brock geology display

- Build a fixed `7×3×2` display in Brock's lobby, within eight blocks of his marker.
- Present two `2×2` sample faces side by side: native Viltri Plateau stone/shale and Pallet soil/road material, with a one-block vertical join and no sediment or weathering layer between them.
- Add two short labels and one heading identifying the sample as taken from the Pallet boundary. Use the final local palette; the story contract is the abrupt contact, not a specific decorative block.
- Keep the faces exposed so the player can stand within four blocks and compare them while Brock speaks.
- If the samples are separated, unlabeled, or displayed far from Brock, his claim that the materials meet directly becomes testimony instead of inspectable evidence.

## Acceptance evidence for Claude

- Record final XYZ and facing for Oak, Mina, Maren, and Brock.
- Record the boundary seam bounds, its inspection marker, and a screenshot from Mina's marker showing both materials.
- Record each damaged-house bounding box and one screenshot showing the cluster remains localized.
- Record the geology display bounding box and a screenshot from Brock's marker.
- Confirm every NPC has a stable floor, three blocks of headroom, no door/pressure-plate collision, and an unobstructed interaction approach.
- Recompile the four conversations with the final placement commands, then test the Pallet-to-Brock sequence with a fresh player.

