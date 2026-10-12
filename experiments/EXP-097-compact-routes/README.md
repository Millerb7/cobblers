# EXP-097: Do the Haven Compact's route and town points (CP-01, 02, 03, 05, 06, 07, 08, 09, 10, 11, 13) run in game?

**Status: STUB, NOT RUN (2026-10-11).** Built offline by unit CP-ROUTES: `tools/compact_routes.py`,
`data/compact_routes.json` (the table), `data/compact_route_trainers.json` (seven seated fighters),
`data/compact_route_npc_teams.json` (nine NPC fighters' teams), the records it splices into `data/dialogue.json`,
`data/quests.json`, `data/progression.json` and `data/npc_seats.json`, and the pack `cobblers_compact_routes`.
Sibling of EXP-091 (CP-CORE's CP-04, CP-12, CP-14); the number is provisional, renumber on merge. Grade with
`qa-reviewer`, not the builder.

## Objective

Part A proves what is BUILT: 17 Cobblemon NPCs (R17N places them) and 7 rctmod seated trainers (R17), of which nine NPCs
talk and then fight through `npc_battle` singles, the win written by the `cobblers_compact_routes` battle_victory callback.

Part B is the stub for what was NOT built, each the design's unproven form (`docs/story/HAVEN_COMPACT_PASS.md`):

- **CP-09's defence of the Waiting Camp**: three distressed wild Pokemon at dusk, fought as wild battles while the
  guards hold the line (band 41-43). Needs a story-zone-triggered per-player wild spawn (M4): scene actors are
  "in progress" (EXP-034) and a keeper that spawns per player has only the Entei/den precedent. Only the camp's two
  conversations exist.
- **Doubles** (CP-03's technicians, CP-11's guard and Varga): built as two singles back to back (X3 unrun).
- **CP-07's timer** (the winch finishes in N minutes): not built (X4 unrun).
- **CP-08's hide-and-seek**: the scouts are seated and found by walking the rim; the finding game is not built.

## Success criteria (Part A)

1. After R17 and R17N and the restart that loads `cobblers_dialogue`: each of the 17 NPCs stands at its seat in
   `data/npc_seats.json` facing its yaw (`python tools/npc_seats.py verify`), and each of the 7 seated trainers at its
   seat (`data/compact_route_trainers.json`).
2. A player at `brock_account_heard` talks to Courier Ansel Kerr (CP-01): the intro, the choice, "A practice match" starts
   a 2-Pokemon battle; a win sets `quest.evt_compact_courier_spar.compact_courier_ansel_defeated` for THAT player only
   (a second account's field stays false); the next talk shows the after lines; a loss leaves the choice on the next talk.
3. A player over the level cap (a party member above `rctmod player get level_cap`) is shown the `*_over_cap` line and no battle.
4. A player BEFORE a point's stage gets the `_before` line and no choice (try `pallet_complete` against CP-01).
5. CP-03: Voss fights on sight within 6 blocks, Iwen does not; each win sets `quest.<id>.defeated`; a beaten player near
   the pair is not dragged back (the hold-off, `tools/route_trainers.py`).
6. CP-05: talking to the ranger and choosing his side sets `sided_with` to `ranger` and moves his cursor; the surveyor
   then offers the fight, the ranger does not; the mirror holds for the surveyor.
7. CP-07: Varga refuses until both salvage hands are beaten; CP-11: Varga refuses until the guard is beaten.
8. CP-13: the medic's lines change after Varga's win.
9. Nobody stands on the road: walk Route 2, 3, 5, 6, 7, 8 and the cirque path end to end; no actor blocks the walked line.

## Not covered

Two players fighting one NPC at once (unrun); whether `npc_battle` through the dialogue works at all (the shared
precondition, X1: EXP-091 step 1 settles it for both units); seat dryness (painted water is not in the heightmap; the
finder only requires ground above y64, y79 at the dock); that the rctmod level cap refuses an over-cap player at a
seated trainer (it does for route trainers, EXP-027).

## Decision / Follow-up

Open. Merge with CP-CORE's tool (`tools/compact_points.py`) is the orchestrator's call; this one needs seated rctmod
fighters and an enum side choice its state DSL does not express.
