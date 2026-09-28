# EXP-045: A player Mega Evolves with a Mega Bracelet

**Objective:** prove that a player in this pack can Mega Evolve a Pokemon in battle. Nobody ever has: EXP-000 still
lists the player Mega check as not tested, and the southern Rift's mega town, mine and stone economy all assume it
works. The owner, 2026-09-27: "PROVE THE MEGA BRACELET FIRST. Nobody has ever Mega Evolved in this pack, and
everything downstream assumes it works." This is proof M-1 in `docs/world-building/SOUTHERN_RIFT_MEGA.md` section 10.

**Versions:** Minecraft 1.21.1 Fabric, Cobblemon 1.8.0, Mega Showdown 1.0.2
(`mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar`), the Accessories mod; staging `cobblers-dryrun11`.

## What the jar says (read 2026-09-27)

- The bracelet is `mega_showdown:mega_bracelet` (six colours and the May bracelet and Mega Ring besides); its lang
  tooltip: "It contains a Key Stone that allows Pokemon holding a Mega Stone...".
- It is worn in the Accessories mod's `mega_slot`: `data/accessories/tags/item/mega_slot.json` lists
  `#mega_showdown:mega_bracelet` and `#mega_showdown:omni_ring`.
- The stones used here: `mega_showdown:lucarionite` (Lucario) and `mega_showdown:charizardite_x` (Charizard); each
  has a mega definition under `data/mega_showdown/mega_showdown/mega/`. Lucario and Charizard are not on the
  broken-texture list (STATE, client model faults).

## Implementation

A staging-only proof pack, `pack/` here, installed as `cobblers_proof_mega` in the staging world's own datapacks folder
(never the global one):
- `cobblers_proof:mega/kit` (run as the player): survival, a teleport to the Hometown Center (1440, 120, 5248), the
  bracelet, both stones, a level-50 Lucario and Charizard (`pokegive`).
- `cobblers_proof:mega/opponent`: a level-35 wild Blissey at (1462, 119, 5226), tanky and gentle, so the battle lasts
  and cannot black the player out.

## Test (the owner)

1. `/function cobblers_proof:mega/kit`
2. Open the Accessories screen and put the Mega Bracelet in its slot.
3. Send out Lucario; sneak and use the Lucarionite on it so it holds it (Cobblemon's held-item interaction).
4. `/function cobblers_proof:mega/opponent`, walk to the Blissey, battle it.
5. In the battle, look for the Mega option on Lucario's turn and use it. Record: whether the option shows, whether
   Lucario becomes Mega Lucario (model and stats), whether it reverts after the battle.
6. Repeat with Charizard and Charizardite X. Then once with the bracelet held in the hand instead of the slot, to
   record which the mod requires.

## Results

- 2026-09-27: the kit installed and loads with no error; the opponent function spawns the Blissey where stated
  (checked over RCON, then removed).
- **2026-09-27, the owner in game on staging (`cobblers-dryrun11`; Minecraft 1.21.1 Fabric, Cobblemon 1.8.0, Mega
  Showdown 1.0.2, Accessories): PASS.** The kit gave the items and both Pokemon (`pokegive` from a function run as the
  player works). With the bracelet worn in its Accessories slot before the battle, the move screen shows a
  "Mega Evolve!" option (a button under the moves, beside the back button); Charizard holding Charizardite X Mega
  Evolved, and reverted after the battle (the owner: "it works, it reverts after battle"). With the bracelet held in the
  hand the option does not show ("not there if mega ring in hand"), and equipping it mid-battle does not bring it
  ("not there if mega ring equipped mid battle"). Screenshots in the session; not logged.

## Decision

The Mega Bracelet works for a player in this pack, worn in the Accessories slot and equipped before the battle. The
southern Rift's mega site stands on a working mechanic (SOUTHERN_RIFT_MEGA.md proof M-1). Sabrina's reward (decision 7)
must reach the player as a bracelet with a clear line to wear it before battles.

## Limits

- Lucario and Lucarionite were not recorded Mega Evolving (the owner's Lucario screen was the in-hand case); Charizard X
  is the one seen.
- Only a wild battle was used; a trainer battle is EXP-000's own check and is still open.
