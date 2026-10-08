# Morning report, 2026-10-06 (overnight build)

Branch `build/2026-10-06-next` (pushed; stacked on draft PR Millerb7/cobblers#119, which is frozen). Staging only;
the live world was never touched. Snapshot before: `cobblers-staging/snapshot-2026-10-06-before-overnight`.

## In the world (staging-2026-10-01), read back after a restart

Prepare complete (175 jobs, head 541a7d8), install_check 0 problems, then R9DW, R9AF, R9PF, R9E, R13, R16C, R16H,
R17F, R17M, R17NE, R18AF, R18CW and a restart. Staging is DOWN: the detached boot (java pid 50764, 05:55) was killed when the tool's background task hit its 2-hour limit; its log ends at 06:21 with no shutdown line (review N53). The apply's own save-all and the world's autosaves precede it; whatever changed after the last autosave is lost. The coordination lock is released.

| What | Where | Read back |
|---|---|---|
| **Ambient Pokemon by composition**: 20 towns hand-authored (working / pets / placed on roofs, gutters, windows / unique situations), mining towns >= 50% working | every gym town, Sunset West, Northlight, Fossick, Steepside, Pacifidlog, the Displaced City, Viltri Light, Bridgekeep, Redbrow, Rimwatch, the West Spur Dig, Merian Hut | `ambient.py verify`: 194 working, 0 problems; `ambient_idle.py verify`: 498 idle in 22 places, 2 problems (Arrow Creeks Farm's Combee, known) |
| **The Brass Petrel**, a wreck half-buried in the south-east dunes' beach, bow in the dune, stern on the flats | hull x6483-6493 z6752-6791 (deck y70); way in at the broken stern (6487-6489, 66-68, 6791); sea chest (6491, 71, 6789); dead reef x6466-6510 z6794-6838; anchor chain to (6494, 63, 6827); two beach Habitat Blocks (6488, 62, 6762) and (6488, 62, 6818) | the chest barrel read from the world; the independent audit 0 problems over 14 checks |
| Castellan, a Palossand "sandcastle" at the tide line | (6448, 63, 6826) | appears only for a player with gym7_cleared (not summoned by a step) |
| **The beats' evidence displays** (a prop and a sign beside each gym-town teller) | Brock (1831, 142, 3663), Misty (1602, 108, 2799), Surge (1686, 175, 1415), Erika (4311, 111, 1552), Koga (4641, 118, 2448), Sabrina (6188, 95, 3394), Blaine (6069, 108, 4993), Giovanni (3644, 114, 6495) | 8 of 8 signs read back |
| **New town squares and stalls** | Bridgekeep (6806, 114, 4377), Redbrow (4846, 162, 5682), Rimwatch (3759, 140, 3952), Merian Hut (2831, 108, 1037), West Spur Dig (3109, 90, 3300) | R13 and R17M ran with 0 problems; not probed block by block |
| **Bird towers' feathers removed** (no free legendaries) | Articuno (682, 311, 379), Zapdos (895, 68, 5582), Moltres (6266, 168, 5361) | all three barrels read empty of feathers after the restart |
| The play test's deferred apply | Hollin's Apricorn Farm (2068, 5570); Arrow Creeks Farm (3149, 5714); Coldwater Station (6030-6070, 1828-1868); the docks and ferrymen; the bank buy list | steps ran, 0 problems (R18AF, R18CW, R16H, R17F); install_check 0 |

Installed (packs), behaviour not seen in game: Old Knot stands still (its wake keeps NoAI); every lake grotto
stays open while a player is in its chamber (Azelf); Dr. Vale's "come back with the Soul Badge" line and hub
re-entry; waystones without the badge gate; route variety (each crossed table keeps 3 species: Pallet's stretch 12%
Caterpie, was 100% of Route 1's pool there); wild held items (2-5%, 51 species); Route 1 Hoppip and Seedot (the
Grass/Water answer to Brock: 28.6% of Route 1 land spawns); the nesting-birds hint at Northlight and Steepside;
evolution stones at Steepside (2,100, ungated); the Ability Capsule at Northlight (gym 6, 10,000, a proposal price);
a Z-Ring with the Raw Tear cache; the finale's two wayfinding lines.

Presence audit: 254 of 316 probes present. Of the 62 absent, 9 are the known stale probes and **53 are Mega-field
dens holding 2-3 Megas each (review N50, P1, not caused tonight, not chased).**

## Findings that changed the plan

- **The story was already wired** (N12): all 13 tellers are seated and the chain Oak -> League compiles and runs
  (60 chain tests); what was missing was the evidence displays (built) and anyone talking to them.
- **The finale was already built** (finale builder): cradle carved, the setter invoked; two wayfinding lines added.
- **There is no "stone shard"** anywhere in the mod set (N21): the gate was the ore; Steepside now sells all ten.
- **TMs are dead in this world** (N22): none of 3,596 TM recipes is craftable from renewable inputs.

## Defects recorded, not chased

`docs/OVERNIGHT_REVIEW_2026-10-06.md` (N1-N52), each with where and who found it.

## Waiting on you

1. N8: a badgeless player can talk to all ten tellers and reach the finale's door (the tellers accept "the badge OR
   the previous teller's account"). Lock it to badges?
2. N39: evolution stones at Steepside ungated (design 5.4, your "don't limit the player") vs the squares audit's
   power rule. Gate at gym 2 or keep open?
3. N35/N26: the Displaced City's market is HELD (two stalls, "OWNER TO CONFIRM": does the city trade?).
4. N23: the obtainability proposals (a TM counter, mint seeds, a brewing-stand line, fossil faces, Z/Dynamax config,
   Giovanni's Ancient DNA, plain bottle caps) and the Ability Capsule's price.
5. Route species lists grew (20 -> up to 35) so every area a route crosses keeps three of its own: accept or veto.
6. Challenge mode (docs/research/RCT_PER_PLAYER_MODE.md): both leaders standing in each gym, each refusing the other
   mode's players: acceptable?
7. N6: keep the loot in the bird towers' summit barrels?
8. Locations for the second Viltri Quay waystone and the research-station waystones.
9. Kyogre questions 1 (per player) and 8 (chests) kept their defaults.
10. In game: walk the West Spur Dig's stall from the finds shed (N37); a held item on ~40 wild Geodude; a Steepside
    stone purchase; the evidence signs and the wreck.
