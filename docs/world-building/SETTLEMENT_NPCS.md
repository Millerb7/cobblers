# Settlement NPCs: what they actually are

Measured from the files on 2026-09-30, at `3bf300b`. The job was "establish what
the 32 settlement NPCs are" before anyone places them. **There are not 32, and
there is no file that ever said there were.**

> **Update 2026-10-02: seated in data.** `data/npc_seats.json` now seats 20 of these NPCs (the 13 `npc_main_*` and
> the 7 stone-tip speakers, which this document did not count), and re-apply step R17N places them. Hank and Lena
> stay unseated: the compiler refuses their conversations. Sections 2 and 5 below describe the state before that.
> Two corrections to section 2: of the eight markers that were authored, **seven stand on the walked route line**
> (`data/route_paths.json` distance 0) and one inside the Pallet sign, so the seats move them off the road and say
> why; and Erika's took the heightmap's y111 on a plaza paved at y110. No seat has been placed in a world yet.

## 1. The number

`32` appears nowhere in the repository in connection with NPCs. The only
occurrence was `docs/HANDOVER_SESSION.md`'s own line recording it as the owner's
figure, which the handover already marked unverified. The closest real number is
**34**, and it counts gate guards, not NPCs — see section 4.

What the data actually holds:

| Set | Count | Authored? | Placed? |
|---|---:|---|---|
| Mainline-reveal actors (`npc_main_*`) | **13** | yes, with dialogue | **no** |
| Pallet crushed-house NPCs (Hank, Lena) | **2** | yes, with dialogue | **no** |
| Gate guards | **34 positions** | **no character authored at all** | no |
| Sea town's rod master, fishing trader, boatwright | 3 | proposed only (`LONG_ISLE.md`) | no |
| Trader clerks (`data/traders.json`) | 26 | yes | **yes**, on staging |
| Cutters (gulch workshop) | 3 | yes | **yes**, on staging |
| Ferrymen | 4 | yes | **yes**, on staging |
| Rift guards + posts | 4 + 2 | Codex's, unwritten | seats exist, armour-stand placeholders |

So the unplaced, conversation-bearing settlement NPCs number **15**, not 32. The
much larger unplaced set is the 34 gate guards, for which no character exists.

**How this was counted.** `data/dialogue.json` holds 74 conversations and **24**
distinct `npc_id` values. Of the 74, **50 carry no `npc_id` at all** — they are
Routes 1–3 props and Pokémon (candles, wards, aisles, signs, crates, gauges, and
Rattata, Geodude, Corphish, Lotad, Wooper, Swablu, Nosepass), already built on
staging. Of the 24 named NPCs, 9 are route or cave NPCs (`npc_route1_*`,
`npc_route2_*`, `npc_route3_*`, `npc_vr_abandoned_cut_digger`), leaving the 15
settlement residents below. `data/scenes.json`'s 10 actors are all route Pokémon
and add nobody.

## 2. The 15, and what each still needs

All 13 `npc_main_*` belong to one per-player quest, `main_worldshift_reveal`
(10 ordered beats, `docs/story/ARC.md`). Their placement state lives in that
quest's own `actors` array.

| NPC | Anchor | `recorded_position_xz` | Ground (canonical heightmap) | Town footprint y |
|---|---|---|---:|---|
| `npc_main_pallet_oak` | `hometown_oaks_lab` | (1487, 5309) | 117 | 109.3–118.1 |
| `npc_main_pallet_mina` | `hometown_sign` | (1456, 5287) | 117 | 109.3–118.1 |
| `npc_main_pallet_maren` | `hometown.lab_lane` | **none** | — | — |
| `npc_main_brock_witness` | built Brock gym prefab | **none** | — | — |
| `npc_main_misty_relief_clerk` | `gym2_town` | (1605, 2801) | 107 | 105.2–109.0 |
| `npc_main_surge_signal_clerk` | `gym3_town` | (1688, 1410) | 174 | 174.4 |
| `npc_main_erika_survey_archivist` | `gym4_town` | (4309, 1555) | 111 | 106.9–112.0 |
| `npc_main_koga_marsh_tracker` | `gym5_town` | (4646, 2446) | 117 | 114.5–123.1 |
| `npc_main_sabrina_pattern` | `gym6_town` | (6196, 3398) | 94 | 93.4–98.0 |
| `npc_main_blaine_crater_analyst` | `gym7_town` | (6074, 4995) | 107 | 105.4–110.5 |
| `npc_main_giovanni_watch` | `gym8_town` | (3647, 6497) | 113 | 108.5–115.0 |
| `npc_main_rift_surveyor` | `victory_road_entry` | **none** | — | — |
| `npc_main_league_steward` | `league` | (3297, 2603) | 118 | **86.3–98.9** ← defect, §3 |

Plus, at Pallet, `npc_pallet_crushed_house_hank` (105 dialogue nodes) and
`npc_pallet_crushed_house_lena` (16 nodes, `scope: mixed`). Lena is the one the
compiler **refuses**: her conversation uses world-scoped fields, and
`compile_dialogue.py --all` compiles 72 of 74 for exactly this reason. House
completion is shared world state while cursors and rewards are per player, and
Lena relocates after rescue — so she needs a marker chosen from the authoritative
world field on load, never inferred from her current position.

**The blocker is not coordinates. It is standing blocks.** Of the 13 actors,
10 have a recorded position and **0 have a `stand_marker`** — the quest's own
blocker says it: *"Every later town actor needs a verified safe standing marker
after its town exists; proposed town centres are not placement coordinates."*
Nine of the ten recorded positions check out, which is the good news: each falls
inside its own settlement's footprint box and sits on heightmap ground within
~2 blocks of that footprint's recorded `ground_y` range. They are plausible
anchors awaiting a verified block, not positions to redo.

Nothing places any of them: `npc_main_*` is referenced only by
`data/dialogue.json` and `data/quests.json`. No tool, pack or re-apply step
reads it.

## 3. Defect: the League steward stands 433 blocks from the League

`npc_main_league_steward`'s `recorded_position_xz` is **(3297, 2603)**. That is
wrong on three independent checks:

1. **Containment.** The League's footprint is x3635–3754, z2375–2485. (3297, 2603)
   is outside it, and inside **no** settlement footprint in `data/towns.json`.
2. **Distance.** 433 blocks from the League's centre (3694, 2430).
3. **Ground.** The canonical heightmap reads **y118** there, against the League
   footprint's 86.3–98.9 — 19 to 32 blocks above the League's own ground.

The second and third checks use different data from the first, so this is not one
assumption failing twice.

**(3297, 2603) is the retired `FACTION.md` cradle coordinate.** `docs/STATE.md`
already records that `docs/story/FACTION.md` "still puts the cradle under the
League plateau at (3297, 2603)" while the build follows `data/rift_regions.json`,
and the Rift-zones unit settled that the cradle goes to **(3357, 3306)**, because
(3297, 2603) is outside the Rift. The steward's position looks copied from that
same stale line. The quest's own blocker list still carries it too: *"The
containment cradle beneath the League plateau has no Y, entrance, footprint,
structure ID, or build."*

**This is Codex's to correct, not ours.** `data/quests.json` is
`datapack-content-dev`'s file and the coordinate is story data from `ARC.md`. Do
not silently move it to the League lot from this side — that would hide the fact
that one retired coordinate propagated into a second file. The right fix is a
League-lot position authored upstream, and the cradle reference dropped.

## 4. The 34 gate guards: positions exist, characters do not

`docs/world-building/TOWN_CHARACTER.md` section "Gates: where the guards would
stand (not built)" lists **33 table rows carrying 34 positions** — Sunset West
has two ways in (coast on foot at (2790, 6625) y63, and the sea at (2616, 6482)
y66). Counted programmatically from the tables, and this matches the 34 that
`docs/STATE.md` already records. 18 are critical-path gates (both ends of every
town on the path, plus the League's one way in from Victory Road); 16 are the one
way into each other place.

The brief was **"THE GATES ARE GUARDS"**: a town's way in is marked by the people
who keep it, not by a structure. **No guard is built and none is authored.** The
proposed reading is that each town's guards come from its trade, as its dressing
does — a mason at Brock's, rescue-boat crew at Misty's, a lineman at Surge's, a
gardener at Erika's, a tracker at Koga's, a record-keeper at Sabrina's, a
researcher at Blaine's, a garrison soldier at Giovanni's — but names, voices and
lines are unwritten, and they are Codex's.

Two constraints any answer must keep, already recorded there: a guard stands
**beside** the road and never on it, so the walked line and the street stay open;
and **guards gate nothing** — the critical path stays at ten gates and a guard
may greet, warn or point, but not stop a player except where a flag already gates
the way.

## 5. What it would take to place them

In dependency order, cheapest first:

1. **Three missing positions** — `pallet_maren`, `brock_witness`,
   `rift_surveyor`. Two are blocked by things above them: Pallet relocation is
   still open, so every Pallet anchor is a staging anchor, and `brock_witness`'s
   anchor is "built Brock gym prefab", which now means the authored Stoneworks
   Hall rather than the donor shell.
2. **Thirteen `stand_marker`s**, verified against the world the town actually
   stands in, not against the plan. The probe pattern that worked for the route
   trainers applies: nominate in advance the seats most likely to be wrong, then
   check those over RCON.
3. **The League steward's position**, upstream (§3).
4. **Twelve evidence objects**, which are the real bulk of the work: 4
   `required_object_unbuilt`, 2 `required_but_unbuilt`, 1
   `required_object_not_built`, 1 `required_object_and_staging_unbuilt`, 1
   `array_planned_record_object_unbuilt`, 1 `required_evidence_carrier_unbuilt`,
   and 2 recorded-but-unverified. Misty needs a relief ledger and belongings
   display, Surge the planned signal array and a comparison record, Erika a
   survey ledger, Koga an abandoned anchor/control-plate display, Sabrina a
   convergence-record table, Blaine an occupied-destination model, Giovanni a
   dissenter evidence carrier.
5. **The 34 gate guards**, which need characters from Codex before anything can
   be seated.

Two blockers sit outside all of it and are not ours: the dialogue compiler cannot
read advancement-backed gym flags, so a beat cannot gate on `gymN_cleared`; and
`crater_operation_stopped` and `rift_crisis_resolved` are approved in `ARC.md` but
absent from the progression ledger with no setter.

## 6. Status of every claim here

**Verified from files at `3bf300b`:** every count in §1 and §2; the three checks
in §3; the 34 positions in §4; the evidence-object statuses in §5. The ground
figures come from `tools/ground.py` on the canonical heightmap, rounded, as the
ground rule requires — no world save was read.

**Not verified:** nothing in this document has been seen in a running game. No
NPC is placed in any world, staging included, so none of these positions has been
stood on. Whether each of the nine good anchors has a safe standing block is
exactly the open question, and only a world can answer it.
