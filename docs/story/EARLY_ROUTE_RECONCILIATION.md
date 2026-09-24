# Early Route Event Reconciliation

**Scope:** Routes 1–3 only. This audit compares `SIDEQUESTS.md`,
`SIDE_EVENTS.md`, and `events/EARLY_GAME_EVENT_BANK.md` with current route,
town, placement, encounter, and story data.

`SIDEQUESTS.md` contains settlement quests rather than route events. Its Pallet,
Brock, Misty, and Surge entries remain outside this route pass; none is counted
as a Route 1–3 event.

## Current constraints

- Route 1 is 1,978 blocks and already contains the maze forest, the mansion,
  the sleeping Celebi sapling, and the thirsty stranger. Its named River of
  Shrews vale is dry in the built terrain and cannot carry a fishing lesson.
- Route 2 is 944 blocks and introduces Lake Viltri; its short length cannot
  support five side scenes plus three trainers without feeling staged.
- Route 3 is 2,120 blocks and already contains the Wooper pond, the Nosepass
  sign clearing, the signal-array sightline, and the climb to Surge's shelf.
- Optional events write only `quest.*` state and never set a gym, faction,
  Rift, or mainline reveal flag.
- Route 1 may show unexplained displacement, but deliberate steering remains
  Surge's mainline reveal. The Nosepass event can show a pulse and a direction;
  it cannot explain who caused either.
- Celebi is visible and inert at `(1380, 4628)`. No early event hints at its
  wake item or advances its later quest.
- The Gastly escort is per player. Each player has their own escort ownership,
  checkpoint, and reward state; none of that state is shared across a party.

## Event audit

| Event | Decision | Current treatment |
| --- | --- | --- |
| `EVT-ROUTE1-GASTLY-FAMILY` | **EDIT** | Use the authored mansion at `(1630, 5034)`. Remove the pulse/ring explanation and shared-party state. Each player leads their own Gastly through five checkpoints. |
| `EVT-ROUTE1-THIRSTY-STRANGER` | **KEEP** | The proven quest remains a joke with no Worldshift explanation. Move its hut away from Celebi to the exact site in the build handoff. |
| `EVT-ROUTE1-CATERPIE-CROSSING` | **CUT** | Route 1 already has three major discoveries and four trainers; Caterpie is not in the current Route 1 pool, and an optional scene must not appear to block the main road. |
| `EVT-ROUTE1-RATTATA-PICNIC` | **KEEP** | Rattata is in the current Route 1 pool. The small scene gives the road ordinary life without adding lore. |
| `EVT-ROUTE1-FIRST-CAST` | **ADD** | A signed spur to the real coast west of Pallet gives the shoreline a purpose and introduces fishing with a basic rod. It is optional and does not imply Relic Island lore. |
| `EVT-ROUTE1-BUG-NET` | **CUT** | It repeats the Bug lesson taught by the Meadow Apiarist and adds a non-roster Metapod actor beside an already crowded forest section. |
| `EVT-ROUTE1-SENTRET-WATCH` | **CUT** | Sentret is not in the current route pool, and the dropped-item beat does not add enough to justify another actor cluster near Celebi and the hut. |
| `EVT-ROUTE2-ROLLAWAY-GEODUDE` | **EDIT** | Keep as the handoff from Brock's stone country. The cart stops safely on the upper grade, well before the lake; the event no longer implies a 400-block uncontrolled roll to the shore. |
| `EVT-ROUTE2-BONSLY-MILESTONE` | **CUT** | Pleasant texture, but the 944-block route needs space for the lake reveal and three trainers. |
| `EVT-ROUTE2-BELLSPROUT-GAUGE` | **CUT** | Bellsprout is not in the current Route 2 pool and the scene competes with the first Lake Viltri stop. |
| `EVT-ROUTE2-NINCADA-ROAD` | **CUT** | Nincada is not in the current Route 2 pool; the road-maintenance beat is less specific to this place than the lake event. |
| `EVT-ROUTE2-MUDBRAY-BOOT` | **CUT** | Mudbray is not in the current Route 2 pool and the joke does not establish Lake Viltri. |
| `EVT-ROUTE2-VILTRI-SOUNDING` | **EDIT** | Keep the existing event-bank concept and make it the player's first real lake activity, using ambient Lotad, Lombre, and Corphish rather than another generic road mishap. |
| `EVT-VILTRI-NORTH-BANK` | **ADD** | A north-bank platform 184 blocks off Route 2 and 267 blocks from Route 3's origin is a shared optional destination with one trainer and one Lure Ball reward. |
| `EVT-ROUTE3-CREEK-WOOPER` | **EDIT** | Keep at `(2204, 1580)`, about 32 blocks from the relocated signs. It is encountered on the outward trip and never becomes a return quest from Surge. |
| `EVT-ROUTE3-NOSEPASS-SIGNS` | **EDIT** | Keep at `(2186, 1606)`. The array receives a visible pulse; the player observes directional interference but does not learn deliberate steering before Surge. |
| `EVT-ROUTE3-SPOINK-PEARL` | **CUT** | Spoink is not in the current Route 3 pool and the generic camper clearing adds little to the mountain leg. |
| `EVT-ROUTE3-SWABLU-NEST` | **KEEP** | Swablu is in the current route pool. The cut-bank nest makes the transition from forest to mountain readable. |
| `EVT-ROUTE3-MAREEP-SHELTER` | **CUT** | Mareep is not in the current Route 3 pool and storm/electric teaching is already carried by the Signal Watcher and Surge's array. |
| `EVT-ROUTE3-SABLEYE-REFLECTORS` | **CUT** | Sableye is not in the current pool and a rare controlled actor is unnecessary for a reflector repair scene. |

The retired concepts stay recoverable in Git history. They are removed from
the canonical event lists so later builders do not treat them as pending work.

## What each leg was missing

### Route 1

The leg lacked a clear first trainer lesson and gave its real shoreline no
purpose. `route_01_trainer_01` introduces eye-contact battles, then later
trainers teach switching and the Water/Grass answers to Brock. First Cast is
the owner-approved exception to the route's otherwise full event density: a
signed coast spur and basic rod, rather than another critical-path scene. The
former River Angler is now a Vale Naturalist because the River of Shrews was
never cut into the terrain.

### Route 2

The leg lacked enough reason to use **Lake Viltri's shore**.
`EVT-ROUTE2-VILTRI-SOUNDING` adds a shore survey at route distance 636. The
player reads three water-depth marks, follows the safe shelf indicated by
Lotad, and resets a floating gauge that Corphish pulled loose. The North Bank
adds a separate optional spur and trainer shared with Route 3. Both are place
activities rather than disguised gym-counter delivery.

### Route 3

The leg lacked a deliberate combat lesson connecting mountain travel to Surge.
Beyond the shared Lake Viltri north bank at its opening, it does not need
another side scene. The Groundkeeper, Signal Watcher, and Vessu Ranger teach
Ground immunity, Electric resistance, paralysis, and priority before the
shelf. Wooper, Nosepass, and Swablu provide the leg's three dedicated physical
events.

## Density after reconciliation

| Leg | Length | Side events | Trainers | Protected discovery |
| --- | ---: | ---: | ---: | --- |
| Route 1 | 1,978 | 4 | 4 | Celebi sapling and optional coast spur |
| Route 2 | 944 | 3 | 4, including 1 optional | First Lake Viltri view and shared north bank |
| Route 3 | 2,120 | 3, plus the shared north bank | 5 | Surge array and shelf reveal |

The shelf lip remains empty. It is an arrival view, not an event pad.
