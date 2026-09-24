# Routes 1-3 and the Gastly mansion: as built

The build of Codex's reconciled early game (`docs/story/EARLY_ROUTE_BUILD_HANDOFF.md`,
`docs/story/EARLY_ROUTE_RECONCILIATION.md`): the Gastly mansion's interior and escort, ten events, thirteen trainers,
and four finds off the path. Built on staging (`cobblers-dryrun9`) only; nothing is in the live world.

## The pieces

| Piece | Source | Tool | Re-apply step |
| --- | --- | --- | --- |
| The mansion, furnished | `tools/route1_mansion.py` (earthwork in `data/placements.json`) | `place_town.py` | R8 |
| The ghost pool's Habitat Block | `data/habitat_blocks.json` `route1_mansion_ward` | `habitat_blocks.py` | R9E |
| Event sites, trainers' shoulders, the mast, the caches' barrels | `tools/route_events.py` | itself | R12 |
| Scenes: props, per-player actors, zones, effects, NPCs | `data/scenes.json` | `scenes_pack.py` | R17 (props, NPCs) and its own tick |
| Conversations | `data/dialogue.json`, `data/quests.json`, `data/progression.json` | `compile_dialogue.py --all` | installed before boot |
| Trainers | `data/trainers.json` (Codex's), `data/route_trainers.json` (seats) | `route_trainers.py` | R17 (`summon_persistent`) |
| Finds | `data/rewards.json` (`r1_*`, `r3_*`) | `rewards_pack.py` | advancements |

`route_events.py` writes each scene's positions into `data/scenes.json` and each trainer's seat into
`data/route_trainers.json` (`--write-scenes`); without the flag it fails when they disagree with the build, and when
anything it builds stands within a block of the walked line (`build/routes/paths.json`), so the scene and the build
cannot drift apart and no scene narrows the road.

## The scene runtime

A scene is everything a quest needs in the world besides its dialogue (`tools/scenes_pack.py` has the whole account):

- **Props** are shared interaction boxes (a cup, a sign, a candle stand); a click opens that prop's conversation for
  the player who clicked, so every player works from their own state on the same prop.
- **Actors** are Pokemon each player owns: spawned uncatchable and without AI, marked Unbattleable and Invulnerable,
  standing where the owner's saved fields say. Once a second, every player inside a scene's area runs its beat:
  `runmolang` reads their quest fields and moves or spawns their actors; an actor nobody refreshed vanishes. This is
  the checkpoint: an actor's place is a function of saved state, so leaving, a disconnect or a restart cannot lose it.
  Another player's actors are visible to everyone (vanilla has no per-player entities); clicking one that is not
  yours says so and opens nothing.
- **Zones** run quest transitions for a player standing in them; **effects** are particles sent to one player only,
  a push-back out of a box, a sequence of lights.

Ownership is a scoreboard number per player (`cobblers_pid`), copied onto their actors. It is identity, not quest
state: every mutable field stays in the Cobblemon player data the dialogue compiler writes (EXP-022).

## The Gastly mansion

**The house.** An abandoned house, not labelled rooms: the foyer's stopped clock, dust-sheeted chairs and portraits,
and a hiding place behind the grand stair; the dining table still laid (Handcrafted plates and cups, a blue cup at
the head); the library's shelves half emptied, with a servants' stair up its east wall; bedrooms with their beds and
mirrors; the ballroom's barred doors bent apart, a cold hearth, and an inlaid path across the floor through three
cracked ward marks; leaf litter under the broken windows, pale moss where the damp got in. Pale hanging moss stands
in for cobweb, which is a spawn condition.

**The ghosts.** The pool `route_1_ghost_mansion` (Gastly, Misdreavus, Shuppet, Duskull, Litwick; levels 6-15) was
authored and compiled but never placed. It is now one Habitat Block, the house's old ward, cracked in the landing
floor, applying what the Rift taught:

- **replacement:** a natural ReplaceSpawns block, which replaces the ambient pool inside its range (EXP-021);
- **range:** 18 from between the storeys reaches every standable floor of the house as a sphere or a column (the
  farthest interior corner is 15.9 away), whichever EXP-033 finds the shape to be;
- **seams:** one block, not a lattice, so no seam inside the house falls back to the forest's pool; the edge falls
  inside the forest clearing (radius 22), so the ghosts keep to the house and its grounds and nothing reaches Route 1.

**The escort** (`evt_route1_gastly_family`, scene `route1_gastly_family`). Five rooms, five conditions, one
checkpoint field (`foyer|stairs|service|library|landing|family`):

1. Foyer: Pip hides behind the stair. Accept, then choose the one clear way (the portrait's hint: the runner's worn
   middle). Wrong ways scare Pip back; nothing resets.
2. Dining room: walk through to the service corridor without the blue cup (a zone). Take it and Pip will not follow;
   put it back and it will.
3. Library: Pip hums three notes; follow the aisle whose call matches. Pip waits at the servants' stair.
4. Bedroom hall: the Litwick light the candle stands in an order (particles only this player sees); touch the
   candles in that order. A wrong one puts the lit ones out.
5. Ballroom: restore the three ward marks in the inlay's order, from the hearth. The barrier (a curtain and a
   push-back, this player's only) drops, Gengar comes out, and the three reunite. Pip gives the Spell Tag; the family
   moves to the north-west bedroom; the loose board where Pip hid holds three Dusk Balls.

Per-player throughout; the checkpoint restores on return. Fields beyond the handoff's five: the rooms' own
(`cup_taken`, `lamp_1`, `lamp_2`, `ward_1`, `ward_2`), `cache_claimed`, and one cursor per speaker plus a shared
`prop_cursor` for the props' one-page conversations.

**Not built, and why.** The optional tea battle in the dining room and "defeat the strongest wild ghost" instead of
the wards: there is no per-player way to know that one particular wild Pokemon was beaten. The non-family Gastly
encounter outside waits on Route 1 balance, as the design says.

## The events

| Event | Where it stands | Deviation from the handoff |
| --- | --- | --- |
| Mansion junction | a signed post where the spur leaves Route 1 | none |
| Rattata picnic | a glade west of the road at (1449, 4826), basket (1450, 4828) | the listed basket is on the walked line: 4 west. The forest has a new glade there (`maze_forest.py` CLEARINGS) |
| Thirsty stranger | the 9 x 7 hut at (1521, 4461), door to the road | a new glade round it; the proven conversation unchanged |
| First Cast | a 5 x 9 jetty at x1049-1057, z5347-5351, deck y64; a signed footpath from Pallet's west side | the sea here is flats about a block deep for 30 blocks; fishing works, vanilla's open-water treasure check probably does not, which matters to the Bottle Cap measurement |
| Rollaway Geodude | miner west of the road at (1752, 3528), rut, sack, boulder, the cart against a birch at (1770, 3517) | both listed points are on the walked line: the scene is on its shoulders |
| Viltri sounding | keeper at (1773, 3010); platform x1725-1733 at the waterline; staffs 5, 6 and 7 deep | **the listed station is 11 above Lake Viltri and 48 from its water.** The keeper keeps the view there and a stepped path goes down the bank to the platform |
| Viltri north bank | platform x1601-1607, z3060-3068, over the water; net rack, beached skiff, tackle box; a 261-cell ring trail from the sounding platform | none |
| Nosepass signs | three signs on the north shoulder at x2182-2190, z1601-1602; the keeper's lean-to; the 40-block clearing and the 60 x 16 strip toward the mast, vegetation only, clear of the elder | the listed signs are on the walked line: north shoulder. **The mast was not built**; it is now (12 blocks, at its anchor). **The pulse cannot be seen on the mast**: it is 441 blocks away, past any client's render distance, so the flash is sent to the player 64 blocks along the line to the mast top, with a sound and Nosepass turning to face it |
| Creek Wooper | the pond shore at (2182, 1630), 24 south of the signs, in their clearing | **(2204, 1580) is a vertex of the pond's annotation outline, 8 above the water and 54 from it.** The water's nearest shore to the signs is used, which is the one stop the design wants |
| Swablu nest | the cut bank on the north shoulder at (2014, 1601); the guide's bench at (1980, 1600) | the nest point is on the walked line: north shoulder. The bench moved east of the route's turn |

Every event is optional and per player; conversations persist their cursors; rewards are once per player through
the proven claim path (EXP-022). Quantities are provisional until the early economy review. The Wooper encounter is
claimed at the moment it is offered: the claim and the spawn are one dialogue action, so relogging cannot repeat it.

**Not built, and why.** In the Wooper scene, crossing the wrong patch resetting the crate: there is no per-player way
to see which ground a player walked on short of a zone per patch, so the three approaches are choices at their heads.

## The trainers

Thirteen, as Radical Cobblemon Trainers data from Codex's records: each team, its AI, its three lines (pre-battle;
the player won, which is also every later talk; the player lost), no item, never spawning naturally, beaten once per
player. Each wears one of rctmod's own trainer skins, which every client has. The Trail Novice battles on sight: the
eye-contact lesson. Each is placed once with `rctmod trainer summon_persistent`.

The handoff's `quest.<trainer>.defeated` is written only by rctmod's `defeat_count` advancement, which fires for the
winning side of a finished battle and never on a loss or a forfeit (EXP-027); the North Bank Angler's also sets
`quest.evt_viltri_north_bank.trainer_defeated`, and the Lure Ball comes through the quest (the tackle box), never
the trainer's bag.

Seats (`data/route_trainers.json`): eleven listed points are on the walked line and stand three blocks onto the
flatter shoulder; the apiarist stands in the apiary glade west of the road; the angler on the north bank platform;
the Vessu Ranger at the Swablu bench; the Signal Watcher on the route by the Nosepass shelter, as listed.

## What each leg still needed

- **Route 1** had its events and trainers, and hidden squeeze paths in the maze that ended in empty glades. Each
  glade now holds a find (`r1_fern_glade`: two Great Balls and Oran Berries; `r1_west_hollow`: two Potions and a
  Pecha Berry; `r1_north_ring`: a Revive, the last before Brock).
- **Route 2** is short and now full: the cart, the sounding, the north bank and its trail, four trainers. Nothing
  added.
- **Route 3** ran 1,400 blocks of forest with only trainers before the Nosepass stop, under the world tree's crown.
  Its roots, 95 blocks off the road, hold a find (`r3_world_tree_roots`: a Big Root and two Sitrus Berries).

## Applying it, and what staging taught (2026-09-24)

Order in a re-export: R6 (forest) and R8 (the mansion, with the towns) come first; R9E sets the ward stone's data
and a restart activates it; R12 runs `route_events/00_clear` and then each site; R17 places props, NPCs and
trainers after the restart that followed install. Every site's vegetation clear runs before any site builds, and a
clear skips anything another tool planted: the Route 1 maze forest, every town's ground and the built elders and
grove giants. Each of those rules is there because staging broke without it:

- a site that cleared after building took its own spruce posts, and the north bank's trail took the sounding
  platform's post (`replace #minecraft:logs` does not know whose log it is);
- the Geodude clear took the log walls of Brock's library, which stands at the site's edge;
- the stranger's short trail cut five planned maze trunks, and the picnic's first hollow log stood on one (both
  moved; `route_events.py` now refuses a block on a planned trunk).

Two runtime facts for anyone repeating this on staging:

- **Re-running R8 alone resets the ward stone** to Cobblemon's default data (a same-state `setblock` still replaces
  the block entity). R9E must follow any R8, then a restart.
- **A second `/reload` on one boot exhausts the 10 GB heap** with this pack stack (the Rift skin alone is 1.6 million
  commands of functions): it happened twice. `reapply.py run --no-reload` runs straight after a boot instead.
