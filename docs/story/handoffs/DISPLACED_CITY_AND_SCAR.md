# Handoff to Codex: the Displaced City and the Scar, as built

**From:** Claude, 2026-09-27, branch `content/codex-handoff-names`. **For:** Codex, which owns `docs/story/`.
**Status:** open. Claude has not edited `ARC.md`, `SIDEQUESTS.md`, `SIDE_EVENTS.md`, `ENCOUNTERS.md` or any
other story file. This expands `docs/HANDOVER_CODEX.md` item 27.

The owner: "the story docs describe something other than what is built. Write up what changed for Codex." This
file lists what the story says, what stands in the build, every difference, and the questions only the story can
answer. The build is on the staging exports only. Neither place is in the live world.

## 1. What the story says

| Source | Claim |
| --- | --- |
| `ARC.md:347-352` | The Scar at (2110, 280, 950) is optional. A player who climbs there sees "the empty summit footprint and a road ending at nothing", and can infer a second town-scale exchange before the critical path confirms it. |
| `ARC.md:382-387`, `:402`, `:687` | Erika's survey records show that a **settled summit** west of the hollow was exchanged before Pallet. The Scar and the Displaced City show where the city went and how its people live now. |
| `ARC.md:389-390` | "A transfer exchanges occupied volume rather than adding new land." |
| `ARC.md:666-667` | `the_scar` "shows the summit footprint of the displaced city". `displaced_city` (2969, 123, 1710) "gives the deepest human account of a complete town exchange". |
| `SIDEQUESTS.md:107-117` (`SQ-G3-01`, Surge) | The player climbs from (1688, 1410) about 620 blocks and 100 up, inspects "the bare footprint and ended road", and copies "the orientation of the remaining foundations". Reveal: "A settlement once stood on Mt Vessu and vanished as a whole." |
| `SIDEQUESTS.md:174-182` (`SQ-G5-02`, Koga) | From `glacial_tear` (4380, 2640) to the city's surface entrance (2969, 1710). Reveal: the vanished summit city "survives beneath the glacier". |
| `SIDEQUESTS.md:368-378` (`SQ-CITY-01`) | A city surveyor at the surface entrance asks why the underground streets "drain toward a sky that is no longer above them". The player compares the street orientation with the Scar. Reveal: "the complete summit plan was exchanged into it." |
| `SIDEQUESTS.md:380-389` (`SQ-CITY-02`) | Gardeners at (2969, 1710) argue whether the **false sky** should imitate the lost seasons. |
| `SIDEQUESTS.md:431-438` (`SQ-MERIAN-02`) | The Merian keeper keeps a bunk for a traveller who stopped arriving after the city exchange. |
| `SIDEQUESTS.md:541-550` (`SQ-SCAR-01`) | At the Scar, "surviving foundations line up with streets" of the city below. Reveal: "The Scar and Displaced City are the two sides of one exchange." |
| `SIDEQUESTS.md:552-561` (`SQ-SCAR-02`) | A former resident at the Scar cannot decide whether a memorial claims the summit or says goodbye. The player helps choose "a temporary marker that does not alter terrain permanently". |
| `SIDEQUESTS.md:709-710` | The city quests need the cavern, a safe entrance and the street plan at the surface anchor (2969, 1710). |
| `SIDE_EVENTS.md:351-358` | `EVT-CITY-CHERRIM`: Cherrim under a **false-sky panel** whose lighting schedule slips. `EVT-CITY-BANETTE`: a Banette carries an object from a family that lived on the summit. |
| `SIDE_EVENTS.md:399-403` | `EVT-SCAR-CARBINK`: Carbink light the surviving foundations at dusk and reveal one missing street line. |
| `ENCOUNTERS.md:335`, `:354` | The cavern: 200 by 200 at y32-72 "under the Glacial Tear"; an urban roster (Magnemite, Klink, Rotom, Porygon, Trubbish, Gothita, Espurr, Klefki, Greavard, Mimikyu and others). |

The story's picture: **the Scar is bare**, with foundations and a dead-end road, because the city **left whole**.
The cavern holds the same street plan under an **artificial sky**.

## 2. What is built or planned

### The Displaced City (staging; `data/placements.json` `displaced_city`, `tools/cavern_plan.py`, `docs/STATE.md` "Displaced City cavern")

- **The cavern** is at x3250-3449, z1650-1849. Its floor is not flat: it is **the summit itself**, a rounded
  mountain top with two benches and a crown. The floor bottoms at y21, and the summit square is on the true top at
  y46. The roof is bare rock 24 blocks under the real ground: y72 under the creek, median y79, up to about y107. It
  is **not lit**. "From the floor there is nothing up there to see. That is the point." (`tools/cavern_plan.py`
  docstring.) The biome is filled as `minecraft:cherry_grove`.
- **Light:** 254 lantern posts along the old road, the ring streets, the square and the slopes; 6 light strings
  hung between trees; sea lanterns in the paving plan. There are no light blocks. STATE records no position in the
  cavern at block light 0. The owner, 2026-09-21: "a town that lost its sun lights itself."
- **The town** was drafted without the owner's review. From the tunnel arrival at the north-west corner, the
  **old summit road** climbs the ridge. Two **ring streets** run round the mountain on the two benches. **42
  houses** stand on levelled terraces and face outward over the dark. Lanes run on the south and east. A stair of
  eight or nine steps climbs to the **summit square** (the plan says nine, STATE and `AUDIT_TOUR.md` say eight),
  where the **cairn** stands (`displaced_cairn`: mossy cobblestone, a chiselled stone brick and a lantern at
  (3328, 47-51, 1757)) with the waystone at (3334, 1762).
- **Houses:** giant-taiga village houses (Repurposed Structures). The first 24 are in the donor's own spruce and
  cobble. The 18 repeats are re-materialed in cherry or dark oak (`data/rematerial.json`).
- **No Centre or Mart**, by decision: "a summit town displaced underground is people living where they were never
  meant to, not a waystation". The owner has not confirmed this (STATE, "Displaced City services").
- **Fields:** six small, struggling, tended plots on the slopes (carrot, potato, beetroot) at block light 8-12.
  Also 17 cherry trees in the margins (41 before the town's keep-clear buffer).
- **The way in:** a gate "of the summit town's stone" (`displaced_gate`) at x3029-3037 z1713-1715. It stands at the
  east edge of the surface square whose centre (2969, 1710) is the story's anchor. From a meltwater mouth there, a
  wandering dug tunnel runs down to the arrival at (3264, 1662). A **rock shell** seals every void within 24 blocks
  of the chamber: the city has no back door.
- **Hidden on purpose:** no signpost points to it (`data/signposts.json` `no_sign`). Its waystone is a discovery
  waystone. The surface site is 287 blocks off the Surge-to-Erika leg (`route_04`, 57% along), so it is reachable
  **after Surge**, and no gate stands in data.
- **Not built:** NPCs, dialogue, quests or events of any kind (`data/quests.json` and `data/dialogue.json` do not
  name the place); a Habitat Block (the authored `displaced_city_cavern` pool exists in `data/spawns.json`, but no
  block is in `data/habitat_blocks.json`, so what spawns there is not verified); Regigigas' sealed chamber
  ("beside the city", `data/towns.json`; no record, no site); the proposed Moon Stone faces
  (`docs/mechanics/EVOLUTION_STONES.md:112`, proposed only).

### The Scar (staging; `data/placements.json` `the_scar`, `data/ruins.json`, `tools/ruins.py`, commits `016f9ea` and `3fdce45`)

- **The ground:** a disc pressed flat at y280 by `tools/press_pads.py`, flat within 150 blocks of (2110, 950) and
  feathered over 140. It is **20 blocks under Mt Vessu's y300 summit**, whose anchor is (2154, 682), about 270
  blocks north. The plan calls it "a disc pressed out of Mt Vessu's shoulder".
- **The owner chose ruins, 2026-09-25** (EXP-035 row 28: "a big city as seen by the layout"). Offered ruined,
  living or unchanged, the owner picked a ruined city (the recommended option). Reading the result, the owner
  said: "the ruins are better than bare foundations: the buildings came down when the town went under, and these
  are what stayed. But that is a story change."
- **The layout is a grid:** a straight north-south avenue 7 wide (z806 to z1098), an east-west cross road, and a
  north and a south road, in cracked and mossy stone brick. An old square of 33 by 33 stands where the avenue and
  cross road meet. Across the whole city this is about 210 blocks east-west by 290 north-south.
- **33 ruined houses:** one per lot and one beside the avenue's north end. Each is a seeded ruined copy of a
  Displaced City house design, and the data names its **twin** below (`data/ruins.json` `twin`). They are in the
  **original spruce and cobble** even where the cavern's copy is cherry or dark oak: "the house as it was before
  it went down".
- **Roofs all gone,** so the houses stand 2 to 7 blocks high. They decay by distance from the old square: standing
  to the eaves near it, then shells, then sills, then stumps "at the rim, where the wind has had the longest".
  There is snow, moss and a few vines. There are no lights, doors, beds, chests or glass: "everything that was the
  people's went with them".
- **Four towers carry the height:** A stands to y302 with a broken crown, B lies fallen in three lengths, C stands
  roofless to y296, and D is a stump. **The cavern has no towers.**
- **Two broken terrace walls** stand at z925 and z975. One course of stone brick outlines each of the 32 lots
  (`scar_foundations`).
- **An empty cairn plinth** stands on the old square: a 5-by-5 ring round an empty 3-by-3, the size of the
  cavern's cairn. "A player who has seen both can set one on the other."
- **The avenue's end over the drop** is designed but **not built**. Whether a cliff exists there at all is an open
  heightmap question (`data/ruins.json` `avenue_end`).
- **Dark by design**, with no waystone, no NPC, no trail from Surge's town in `data/placements.json`, no Carbink
  (in `data/spawns.json` Carbink is only in the Mining Town's fossil levels), and no Sun Stone faces yet
  (proposed, `EVOLUTION_STONES.md:111`).
- **Not seen in game.** 0 floor gaps is the only check recorded.

## 3. Every difference

| # | Topic | Story | Built or planned | Kind |
| ---: | --- | --- | --- | --- |
| 1 | What stands at the Scar | An empty footprint: bare foundations and a road that ends at nothing (`ARC.md:350`, `SQ-G3-01`) | A ruined city: 33 roofless houses, 4 towers (one fallen), broken terrace walls, an empty cairn plinth, a grid of broken roads | **Owner's change; the story must follow or push back** |
| 2 | How the city left | "Vanished as a whole" (`SQ-G3-01` reveal); a complete exchange | The houses stayed behind as ruins, and the same designs stand whole below. The owner's reading: "the buildings came down when the town went under, and these are what stayed" | Contradiction; needs a story reason (Q1) |
| 3 | The exchange rule | A transfer exchanges occupied volume (`ARC.md:389`) | The Scar shows no sign of what came back up in place of the city: it is a flat mountain-rock pad, and the cavern it swapped with was solid rock | Story-internal gap the build exposes (Q3) |
| 4 | Street orientation | The Scar's foundations line up with the cavern's streets (`SQ-SCAR-01`, `SQ-CITY-01`); `data/ruins.json` `decided` repeats the claim | They do not. The Scar is a straight grid on a flat disc (avenue north-south, roads east-west). The cavern has a diagonal old road climbing a ridge north-west to south-east and two ring streets round a domed summit. No comparison a player can make will match | **Built contradicts both story and data text** (Q4) |
| 5 | Size | One city, two sides | The Scar's city is about 210 by 290 blocks, and the cavern is 200 by 200 with its town about 160 across. Scar: 32 lots of 11 by 11, 33 houses. Cavern: 42 houses on 10-by-10 lots | Difference to explain or accept (Q4) |
| 6 | Summit or shoulder | "Summit footprint", "settled summit", "Summit Memorial" | A pad 20 blocks under the y300 summit, on the shoulder about 270 blocks south. Before the rescale it was the clipped summit plateau (`data/towns.json`) | Wording or fiction (Q6) |
| 7 | The ground shape | A summit city moved whole | The cavern's floor **is a mountain top** (benches and crown, y21 to y46). The Scar is flat. A flat cut is right for a summit that left, but then the Scar's houses stand on ground the city's houses never stood on | Needs a story reading (Q1, Q4) |
| 8 | Towers | None mentioned | Four at the Scar, none in the cavern | New element (Q2) |
| 9 | The cairn | None mentioned | A cairn on the cavern's summit square, and an empty plinth of its size at the Scar | New element; confirm or replace (Q7) |
| 10 | Materials | None mentioned | The Scar is in spruce and cobble; 18 of the cavern's 42 houses are cherry or dark oak. `data/ruins.json` reads this as "the house as it was before it went down", which implies residents rebuilt in the cavern's cherry wood | Claude-invented implication; confirm (Q5) |
| 11 | Decay pattern | None | Best preserved at the old square, worst at the rim "where the wind has had the longest": weathering over time, with no mark of the event | Implies an age for the ruins (Q8) |
| 12 | The cavern's sky | A **false sky**: panels with a lighting schedule (`SQ-CITY-02`, `EVT-CITY-CHERRIM`); `data/towns.json` still recommends "a glowing false sky" | **No false sky.** The roof is bare unlit rock, deliberately invisible. Light is lanterns on posts and strings. There are no panels and nothing on a schedule | **Build contradicts two story items** (Q9) |
| 13 | Where city scenes happen | Every city NPC and event is anchored at (2969, 1710), the surface site | The city is about 400 blocks east and 80 down: square (3321-3336, 1750-1765) at y46, city centre (3366, 1755). The gate is at (3029-3037, 1713-1715) and the tunnel arrival at (3264, 1662) | Coordinates to move (Q10) |
| 14 | Surface entrance | "The surface entrance (2969, 1710)" | A gate and a meltwater mouth at the east edge of that square, then a dug tunnel of a few hundred blocks. No NPC stands at the surface | Coordinates |
| 15 | Cavern depth | y32-72 (`ENCOUNTERS.md:335`) | Floor y21-48 (summit y46), roof y72-107, median y79 | Numbers |
| 16 | "Under the Glacial Tear" | Beneath the glacier; `SQ-G5-02` starts at `glacial_tear` (4380, 2640) | Under the Upper Trough sub-region of the Glacial Tear region, 97 blocks from the trough at the surface site; (4380, 2640) is about 1,720 blocks away | Route text |
| 17 | When a player can reach it | Handed out by Koga (`SQ-G5-02`, after gym 5); must never gate anything | Reachable from Route 4 **after Surge** (gym 3), 287 blocks off the leg. The Scar is reachable at the same point, 437 off the same leg. Nothing gates either | Timing (Q11) |
| 18 | Services | "Gives the deepest human account", with a surveyor and gardeners | No Centre or Mart, by an unconfirmed decision. No NPCs, dialogue or quests in data | Owner call pending; Codex writes the people |
| 19 | Encounters | Urban roster under a signature floor tag (`ENCOUNTERS.md:354`) | The pool exists; no Habitat Block is placed, and the biome is `cherry_grove`. What spawns is not verified | Build gap (not Codex's) |
| 20 | Fields | Gardeners argue over plant light (`SQ-CITY-02`) | Six small lantern-lit crop plots, "small, struggling, clearly tended" (the owner) | Fits; a place for the gardeners |
| 21 | Carbink at the Scar | `EVT-SCAR-CARBINK`: Carbink light the foundations at dusk | No Carbink spawn at the Scar. The Scar is dark by design, which suits a light show at dusk | Build gap if the event stays |
| 22 | The ended road | The survey's road "ends in open air" (`SQ-G3-01`) | The avenue stops at the pad's north edge. The run out over the drop is designed but not built, and whether there is a drop is unmeasured | Partly built |
| 23 | Regigigas | Not in the story briefs | `data/towns.json` has Regigigas "sealed beside" the city. No site or record | Not built |
| 24 | Stones | Not in the story | Proposed: Sun Stone at the Scar ("a summit scraped flat and open to the sky") and Moon Stone in the city. They must not sit under ruins | Proposal (item 27) |

## 4. Questions only Codex can answer

1. **Why do ruined copies of the cavern's houses stand at the Scar?** The owner reads it as "the buildings came
   down when the town went under, and these are what stayed". That fits the owner's picture but not "vanished as a
   whole". Candidate readings, none chosen by Claude:
   - **An imperfect exchange left an echo:** a second, broken copy of every house. This makes the Scar evidence
     that exchanges are unstable, which is Koga's fact (`ARC.md:688`), so it would pull that fact earlier.
   - **The exchange took the summit core and left the outer city:** the houses are the lower town, which fell
     empty once its people had gone below. The two places would then be two halves of one city, not two copies.
     The data's `twin` rule would become "same builders, same designs".
   - **The people came back up and rebuilt, then left again.** This adds a chapter to the city's history.
2. **What were the towers,** and why did none go below? The owner wanted "a few fallen towers or tall ruins" for
   height. If the story has no towers, say what they should be (watchtowers, a signal mast older than Surge's,
   granaries), or ask for them to be removed before anything else is built on them.
3. **What did the Scar receive in exchange?** By `ARC.md:389` an exchange swaps occupied volume. The cavern's
   volume was solid rock under the trough, so the Scar should hold that rock, not an empty flat or a ruined city.
   Is the flat pad the top of that rock plug, or does the rule bend for this, the oldest exchange?
4. **Must the streets line up?** `SQ-SCAR-01` and `SQ-CITY-01` turn on matching orientation, and the build does
   not match (difference 4). Choose one:
   - the puzzle compares something else (the house designs, which do match one for one, or the cairn and plinth);
   - Claude re-draws the Scar's streets as the cavern's ring-and-ridge plan projected onto the flat pad (a world
     change, to be requested);
   - the mismatch is itself the clue (for example, the summit was re-laid when it arrived).
5. **The two woods:** do the cavern's cherry and dark-oak houses mean the residents rebuilt with cavern timber?
   If not, Claude can put all 42 cavern houses back in spruce and cobble, or make the Scar match.
6. **Summit or shoulder:** the Scar is 20 blocks under Mt Vessu's summit. Should the story say "the shoulder
   where the city stood"? Or was the city's own peak the part that went, leaving Vessu's higher summit beside it?
7. **The plinth:** the empty cairn footprint assumes the cairn went down with the city and stands on the cavern's
   square. Confirm or replace. `SQ-SCAR-02`'s memorial ("a temporary marker that does not alter terrain
   permanently") now has an obvious place: the empty plinth. Say whether it goes there.
8. **How long ago?** Weathering from the rim inward reads as decades. `EVOLUTION_STONES.md` places the stones'
   first appearance "a generation ago, contemporary with the earlier city-scale exchange". `SQ-MERIAN-02` and
   `SQ-SCAR-02` have people alive who remember it. Name the interval so the ruins, the Merian keeper and the
   returning resident agree.
9. **The false sky is not built.** Either rewrite `SQ-CITY-02` and `EVT-CITY-CHERRIM` for a city lit by its own
   lanterns under a roof nobody can see, or ask for a false sky (a world change, contrary to the owner's
   2026-09-21 lighting call). The farms and the lantern posts are there to build on.
10. **Anchors:** move the city's surveyor, gardeners, Banette and Cherrim scenes into the cavern: the square at y46,
    the fields on the slopes, the arrival at (3264, 1662). Keep only the gate (3029-3037, 1713-1715) at the
    surface.
11. **Order of discovery:** both places can be found after Surge, off the same leg (the Scar at 27% along, the
    city at 57%). A player can see the ruins, then the living city, before Erika states the earlier exchange.
    Is that the intended order? `ARC.md:350` expects the Scar to prompt an inference before Erika. The ruins
    now prompt "disaster" before "exchange".
12. **What should a player conclude from seeing both?** The same houses stand whole underground and broken on the
    mountain. Does that change `SQ-SCAR-01`'s reveal ("two sides of one exchange") or the reveal ladder
    (`ARC.md:679-693`)? At which stage may a player understand it?
13. **The city's own name.** "The Displaced City" is what outsiders call it. The residents must have had a name for
    their summit town. If so, it belongs on the Scar's plinth or survey sheet and could replace the working name
    (see `docs/world-building/SETTLEMENT_NAMES.md`, which keeps "The Displaced City" for now).
14. **Is the look right?** The ruins read low because the roofs are gone, and four towers carry the height. If a
    city should still show its roofs, or no towers stood there, say so before more is built on it.

## 5. Stale Claude-side records (not Codex's to fix; listed so they are not read as story)

- `data/towns.json` `the_scar.for` still says "a bare scraped-flat table ... with foundations and a road that
  ends at nothing". `displaced_city.for` and `underground.ceiling` still describe "a glowing false sky".
- `data/placements.json` `the_scar.status` says the 33 houses are "designed, not built" and that the ruin transform
  "does not exist yet". `data/ruins.json` `status`, `tools/ruins.py` and STATE say they are built on staging.
- `docs/world-building/AUDIT_TOUR.md:132`: "Foundations only, one course, on the 32 lots".
- `docs/world-building/SETTLEMENTS.md:107-118` and `:189`: the false-sky spec and "foundations and a road that
  ends at nothing".
- `docs/world-building/BUILD_PREP.md` "Displaced City cavern": the superseded plan (floor y33-53, flat y72
  ceiling, 800 light blocks, sea lanterns behind stained glass).
- `tools/cavern_plan.py` docstring: "the wild floor is left at block light 0". STATE and the light plan say no
  cavern position is at 0.
- `data/ruins.json` `decided`: "its foundations line up with the cavern city's streets" (difference 4).

## 6. Not verified

Neither place has been seen in game in its current form. The Scar's ruins and the cavern town exist on staging
exports only. What spawns in the cavern, whether the Scar's avenue ends at a drop, and every in-game impression
above are unverified. All positions come from `data/` records, not from reading a world.
