# The dive and sky portals, and the pocket dimension

**Status (2026-09-29).** Designed, generated and audited offline. **Nothing here has been seen in a
running game.** The dimension registers only at a server boot, and every click, every crossing and every
reward is unrun. `data/portals.json`, `tools/portals.py`, `tools/portals_audit.py`,
`tests/test_portals.py`, and `tools/reapply.py` step **R16P** plus the two `prepare` jobs
`portals:build` and `portals_audit`.

---

## 1. What this is

Twelve portals. Each is a small arch — a 5 by 5 apron, two jambs, a 3 by 3 sheet of tinted glass, a
lintel and two lamps — with an invisible click box one block in front of it. Clicking it, when the
player's gate is open, puts them in a room built inside `cobblers:pocket`. Each room has the same arch
back, and clicking that returns them to the apron they left from.

- **Six dive portals** stand on the floors of six bodies of water, 13 to 51 blocks down. They gate on
  the **existing** `cobblers.dive` tag, which `cobblers:water/grant_dive` grants (`tools/blackout_pack.py`,
  "the survey diver's training"). This pack reads that tag and **never grants, revokes or touches it**;
  `tools/portals_audit.py` fails the build if it ever does.
- **Six sky portals** stand on summits, all east of x4000. They gate on a **new** `cobblers.sky` tag,
  granted by `cobblers:portals/grant_sky` on exactly the same pattern: a tag on the player, put there by
  a function, never revoked.

**The owner's content rule, verbatim: "1 in 6 meaningful, the rest a chest or nothing."** So each six
has exactly one `vault` and five small rooms: three `cache` (a chest) and two `cell` (nothing but the
room, a light and the way back). `tools/portals.py` refuses to build if that count is ever wrong, and
the audit checks it again from the data.

---

## 2. The rung, and why nothing cheaper does it

`CLAUDE.md` principle 6, in order:

| Rung | Why it does not suffice |
|---|---|
| Cobblemon native | Cobblemon has no portal, no pocket space and no dimension feature. 1.8 adds `party_pools`, `party_compositions`, `moveset_builders` and the Habitat Block; none of them moves a player. |
| A compatible addon / a Cobbleverse dependency | No mod in the pack ships a portal to a custom dimension (`base-pack/inventory/`). Waystones move a player but only between its own placed waystones, in the overworld. |
| Configuration | There is no config key for a dimension or a portal in any of them. |
| **Datapack** | **Used.** A `dimension` and a `dimension_type` are plain datapack files. **EXP-047** proved on this exact stack that one registers, loads with no new error line, is writable, and holds entities. |
| **Functions and commands** | **Used.** Vanilla has no datapack-definable portal *block*, so the crossing itself has to be a command. It is a right-click on a `minecraft:interaction` entity, read by a `minecraft:player_interacted_with_entity` advancement whose reward runs the crossing and then revokes itself so it can fire again — the pattern `tools/scenes_pack.py` already uses for every clickable prop (EXP-034). |
| A scripting layer, a companion process, a custom mod | Not reached, and not needed. |

ADR-004 had already chosen the pocket dimension for spaces that must be elsewhere; EXP-047 closed the
question of whether one works here at all.

---

## 3. What EXP-047 settled, and what this design does about each of its results

| EXP-047 | What is built on it |
|---|---|
| A custom dimension registers and loads, no new error | The `dimension`/`dimension_type` pair is shipped in `cobblers_portals`. It registers **only at a server boot**, not on `/reload`: a first install must restart the server before step R16P will do anything. |
| We can `forceload` and `setblock` in it | Every room is built by a function that force-loads its own chunks. The functions are called by `cobblers:portals/place`, whose one line is `execute in cobblers:pocket run function cobblers:portals/pocket/build`. `execute in` carries the dimension into the called function, so every command inside — the forceloads included — acts in the pocket. That also keeps `tools/function_limits.py` honest: it sees a plain `forceload add` before every plain `fill`, which is exactly what happens. |
| Entities live there | The return box and the vault's claim box are `minecraft:interaction` entities summoned by the room functions. |
| **A selector with no positional constraint is NOT dimension-scoped** (`kill` run `in minecraft:overworld` destroyed an entity in the pocket) | Every selector that must stay in one dimension carries a position. The rescue sweep is `execute in cobblers:pocket as @a[x=…,dx=…,…]`. The two kills in the place functions are deliberately global, because a stale copy of *that* portal's box is to be removed wherever it is. |
| Our per-tick systems reach the pocket for free | Good: blackout, the water ladder and the level cap all still apply to a player inside a room. It also means anything meant to be overworld-only needs a dimension predicate — this pack adds none. |
| **Contents do not survive a re-export** (they live inside the world folder) | Step **R16P** rebuilds every room on every run. The rooms are flat, deterministic and small (169 to 2,501 blocks each), so rebuilding is exact and cheap. Nothing here relies on `reapply.py carry` learning to copy `dimensions/`. |
| The crossing is a right-click, so the player is already dismounted | ADR-004's recall-on-crossing has nothing to recall, and the water-fatigue collision cannot arise. **If a portal is ever changed to trigger by walking into it, this reopens.** |

---

## 4. Where they are

Ground for every one of them comes from `tools/ground.py` (the canonical heightmap, rounded). No world
was read to decide a position. The apron sits at the highest of its 25 columns; a lower column is
filled up to it.

### The six dive portals

| id | at | apron y | water level | depth | room | body |
|---|---|---|---|---|---|---|
| `dive_viltri_floor` | 1652, 2996 | 75 | 103 | 28 | cache | Lake Viltri |
| `dive_shrew_pit` | 2856, 3960 | 56 | 106 | 50 | cell | Shrew Lake |
| `dive_tarn_bottom` | 3388, 916 | 105 | 127 | 22 | cache | Ravine Head Tarn |
| `dive_peak_pond_floor` | 4068, 1480 | 87 | 105 | 18 | cell | Peak Pond |
| `dive_watering_hole_floor` | 2958, 5235 | 82 | 95 | 13 | cache | Watering Hole |
| **`dive_tilpey_gate`** | 6076, 4296 | 50 | 77 | 27 | **vault** | Lake Tilpey |

The Watering Hole lies under the Rift's block pass. `cobblers_rift` skins every column the sculpt
moved, and that covers almost the whole basin; the one patch it never touches is the original lake bed
(x2938-2979, z5229-5243), which was already at y82, below the cut, so the sculpt left it alone. The arch
stands in the middle of that patch. A first siting at (2964, 5268) sat inside distortion tile 46 82, and
because R16P runs after R1 the portal would have silently overwritten 85 of the skin's fills;
`tools/portals_audit.py` caught it. Any future move inside this body must stay in that patch.

Lake Tilpey is the meaningful one because the **Dive school stands on its north shore**
(`docs/mechanics/WATER_MAP.md` allocation 12): it is the first water a newly trained diver goes into, so
the payoff is where the training is.

Three bodies were deliberately left alone: **Arrow Lake** (Mesprit's grotto), **Marshy Marsh** (Azelf's)
and the **Mt Clay pond** (`docs/STATE.md`: "players are not sent back to this pond"). The rule
`min_from_legendary_mouth` (120) fails the build if a portal is ever moved onto a sited legendary.

A dive portal is visible long before it can be opened. That is deliberate and it is the established
pattern here: `WATER_BUILD_PLAN` 4.2 shows the lake trio's grottos to everyone and has them answer only
to a badge.

### The six sky portals

| id | at | apron y | room | where |
|---|---|---|---|---|
| `sky_downs_crag` | 4530, 1951 | 127 | cache | between Erika's town (gym 4) and gym 5 |
| `sky_marsh_horn` | 5450, 2661 | 140 | cell | east of gym 5, towards gym 6 |
| `sky_gorge_shoulder` | 6630, 4667 | 124 | cache | above the gorge hamlet, between gyms 6 and 7 |
| **`sky_tableland_head`** | 5601, 5632 | 195 | **vault** | the highest eastern summit outside the Rift and the Craters |
| `sky_assay_tor` | 7007, 5834 | 157 | cache | above the Mining Town |
| `sky_far_reach` | 7613, 7498 | 149 | cell | the far south-east, past the sea town |

### The x4000 check, in full

The owner's rule: *a sky portal west of about x4000 would sit unusable while the player walks past it
for three gyms.* **No sky site landed west of x4000.** The westernmost is `sky_downs_crag` at
**x4530**, 530 east of the line, and it is the first one the gate opens for. `data/portals.json`
carries the rule, `tools/portals.py` refuses to build a sky portal west of it, `tools/portals_audit.py`
checks it again, and `tests/test_portals.py::test_every_sky_portal_is_east_of_the_owners_line` fails if
one ever appears.

**What the rule cost, for the owner to look at.** The five best high places on the map are all west of
the line and none of them carries a portal:

| Summit | Where | Nearest town |
|---|---|---|
| y310, (736, 288) | the Frostpeak massif | frostpeak_shrine, 37 |
| y305, (3360, 2720) | the League's shoulder | league, 362 |
| y300, (1888, 736) | Mt Vessu | the_scar, 96 |
| **y288, (3744, 5408)** | **the ridge north of gym 8's town** | **gym8_town, 1029** |
| y287, (1888, 1376) | above gym 3's town | gym3_town, 173 |

The fourth is the one worth a decision. It is at **x3744, 256 west of the line**, but a player reaches
it *after gym 7*, not before gym 4, so the reason the line exists does not apply to it. It was **not
built**, because the rule as written is a line on x and the brief said to stop at it. If the owner wants
it, it is a one-line addition to `data/portals.json` plus a `sky_min_x` exception with its reason.

---

## 5. The rooms

All twelve rooms live in one dimension, `cobblers:pocket`, on a grid: room *i* of a gate is centred at
`x = i * 128`, `z = 0` for dive and `z = 256` for sky, with its floor at **y96**. They are laid out
128 apart so each owns its own chunks.

- **`cell`** (nothing): interior 7 by 7, 5 high.
- **`cache`** (a chest): the same, with one chest against the back wall carrying its own loot table.
- **`vault`** (the meaningful one): interior 13 by 13, 9 high, with a pedestal.

A **dive** room is a sealed shell of prismarine with four sea lanterns in the ceiling — the audit walks
every boundary cell and fails on a single hole. A **sky** room is an open platform of stone brick under
the dimension's own sky, with a parapet two courses high (you cannot jump a two-block wall) and a
lantern on each corner.

The generator is `minecraft:flat`: biome `minecraft:the_void`, one layer of bedrock at y0, no features,
no lakes, no structure overrides. `the_void`'s mob spawn list is empty, so nothing vanilla spawns
anywhere in the dimension without being asked. The `dimension_type` has `monster_spawn_light_level: 0`,
`has_raids: false`, `bed_works: false` and `respawn_anchor_works: false`, so **no player can set a spawn
point in there**.

---

## 6. State: where it lives, and what happens when a game goes wrong

| State | Where | Lifetime |
|---|---|---|
| `cobblers.dive` | a player tag | the player's own file; **not ours** (`tools/blackout_pack.py`) |
| `cobblers.sky` | a player tag | the player's own file; granted once by `cobblers:portals/grant_sky` |
| which portal a player last crossed | scoreboard `cobblers.portal`, per player | the scoreboard file; survives death, logout and a re-export |
| the arches | blocks in the overworld | erased by a re-export, rebuilt by R16P |
| the rooms | blocks inside `<world>/dimensions/cobblers/pocket/` | **lost on every re-export**, rebuilt by R16P |
| a `cache`'s chest | one chest, one loot table | refilled whenever R16P rebuilds the room |
| a `vault`'s claim | the advancement `cobblers:portals/claim/<id>`, never revoked | per player, for ever |

**Nothing per-player is stored as a coordinate.** The way back is a constant per portal — each room
returns to its own arch — so a return needs no memory of where the player came from.

### The multiplayer and edge cases (principle 12)

- **A player joins late.** The sky sweep (`cobblers:portals/gate`, every 100 ticks) tags anybody who
  holds `cobblers:flag/gym4_cleared` and lacks `cobblers.sky`. So the grant is **retroactive** — a
  player who cleared gym 4 before this pack existed is tagged on the next sweep — and it reaches a late
  joiner the moment they clear gym 4 themselves. Nothing has to be run by hand for an existing save.
- **Players in different orders.** Every gate is per player and every room is shared space. Two players
  can be in the same room, or in different rooms, at once; the rooms are 128 apart so nothing collides.
- **A player disconnects inside a room.** They log back in inside it and walk out through the return
  arch. Nothing was held in the session.
- **A player logs in inside the pocket after a re-export**, when the room no longer exists: they are
  below y95 with nothing under them, so `cobblers:portals/tick` catches them within a second and puts
  them back at the arch they last used (`cobblers.portal`). A player who has never crossed a portal and
  is somehow in there is put out on dry land at `sky_downs_crag`.
- **A player leaves a sky room** (the one way out is a hop from the arch's lintel onto the parapet):
  they fall 96 blocks to the bedrock plane. The rescue runs **every 20 ticks** precisely so it catches
  them on the way down; a fall that far kills, and a death in there would drag in the blackout
  machinery for no reason. *This is reasoning, not a measurement — it is on the list below.*
- **A player dies in a room** (they should not be able to, but): no bed and no respawn anchor works
  there, so they respawn in the overworld like anyone else.
- **A `cache`'s chest is first-come.** One chest, one loot table: the first player to open it takes it.
  That is why the **meaningful** room's reward is not a chest but a pedestal whose advancement is never
  revoked — clicking it grants `cobblers:portals/<id>` **once per player**, so a party of four all get
  it, and a second click does nothing.

---

## 7. What is proven, what is only written

**Verified offline, here:**

- `python tools/portals.py build` emits the pack: 57 functions, 12 world arches, 12 rooms, the
  dimension pair, 26 advancements and 8 loot tables.
- `python tools/portals_audit.py` — **CLEAN**. It never imports the generator: it replays the written
  functions into a voxel model and holds it against its own reading of the heightmap, the lake levels
  and outlines, the town footprints, the placements, the sited legendary mouths, `data/spawn_blocks.json`
  and every other built pack.
- `python tools/function_limits.py build/datapacks/cobblers_portals` — 57 files, 0 with problems.
- `python -m pytest tests/test_portals.py` — 32 passed, including nine deliberate corruptions of the
  pack that the audit must reject.
- `tools/reapply.py`'s two fail-closed checks: the pack is covered by a step (`uncovered`) and every
  function it ships is run or referenced (`unreferenced`).
- `python tools/validate_data.py` — 0 errors. `tests/test_ground_rule.py` — 10 passed (no new tool
  reads a world to decide).

**Not verified. Every one of these needs a player in a running game:**

1. **The dimension loads inside our real pack set.** EXP-047 proved a throwaway dimension loads; this
   one ships in `cobblers_portals` alongside 40 other packs, and it has never booted.
2. **A click crosses.** The advancement-plus-interaction pattern is proven for dialogue (EXP-034), never
   for a teleport.
3. **The gate holds.** A player without `cobblers.sky` must get the message and stay put.
4. **The sky tag is granted.** The `@a[advancements={cobblers:flag/gym4_cleared=true}]` sweep has never
   run.
5. **The rescue beats the fall.** Reasoned, not measured. If a 20-tick sweep is not fast enough, the
   answer is a lower room floor or a water cushion, not a longer period.
6. **The vault's pedestal is clickable.** Its box is 1.6 wide and sits on a lit pedestal; whether a
   player's aim hits the interaction rather than the block under it is unknown.
7. **Nothing spawns in `minecraft:the_void`.** Vanilla's spawn list for it is empty; whether a Cobblemon
   pool can match it is untested, and EXP-047 left that question open for want of a player.
8. **A dive arch reads as a door under water**, and the return into water at the same spot is not
   unpleasant with the fatigue clock running.

These belong in one experiment (dive and sky portals, first crossing) after the next staging boot.

---

## 8. What is left for somebody else

- **The stories.** Every portal carries `"story": "for Codex"` and the generator refuses any other
  value. What these places are, why an arch stands under Lake Viltri, and what the two empty rooms
  are for, is Codex's.
- **The rewards.** `data/portals.json` `loot.tables` uses only item ids that already appear in
  `data/rewards.json`, so nothing is invented, but **what** each portal gives is the
  `trainer-balance-designer`'s decision, not this design's.
- **The western y288 ridge** north of gym 8's town (section 4), which needs the owner.
