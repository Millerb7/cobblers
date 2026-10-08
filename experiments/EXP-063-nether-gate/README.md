# EXP-063: does the Nether's badge-8 gate send back every player without the eighth badge, and trap nobody?

**Status: NOT_EXECUTED.** Designed 2026-10-08 with the pack it tests (`tools/nether_gate.py`, `data/nether_gate.json`,
`cobblers_nether_gate`, world-local, no reapply step). Nothing has been run on a server. The builder wrote this
procedure and the builder's own tests (`tests/test_nether_gate.py`, contracts C19 and C20). **The builder does not
grade it**: another agent or the main session runs it and reviews the results. It is experiment N5 of
`docs/mechanics/NETHER_ENCOUNTERS.md` section 6.

## Objective

`NETHER_ENCOUNTERS.md` G1, approved by the owner: a player arriving in `minecraft:the_nether` without
`cobblers:flag/gym8_cleared` is sent back to the overworld. **Yes** means every route into the Nether is turned back
for a player without the badge, a player with it is never touched, nobody is left in the Nether or in a loop they
cannot leave, and the Entei's `cobblers:pocket` rooms are unaffected.

## What it relies on, and what is ASSUMED

| Claim | Status |
|---|---|
| `minecraft:changed_dimension` with `conditions.to` fires on a portal, a `/tp` and a mod teleport | **ASSUMED** (vanilla, not in `docs/research/`). Cases 1, 4, 5 |
| `execute in minecraft:the_nether as @a[x=..,dx=..]` selects only players in the Nether | **INFERRED** from EXP-047 result 4 (the reverse was measured: an unpositioned selector reaches across dimensions). Cases 9, 10 |
| A cross-dimension `tp` of a player who is riding stops the riding; the pack dismounts first anyway | **ASSUMED**. Case 3 |
| What Cobblemon does with a sent-out mount left behind in the Nether | **NOT KNOWN**. Case 3 reads it |
| A respawn at a Nether respawn anchor and a login inside the Nether raise no `changed_dimension` | **ASSUMED**; the sweep covers them either way. Cases 7, 8 |

## Success criteria

Coordinates: the pallet landing is **(1461.5, 118, 5306.5)** in the overworld (`data/blackout.json` pallet; ground
y117 measured with `tools/ground.py` on 2026-10-08). A checkpoint landing is the player's `bo.cpx`, `bo.cpy`, `bo.cpz`
plus 0.5 on x and z.

- **G-a.** A survival player without the flag who enters the Nether is back in the overworld within 1 tick when the
  trigger fires, or within 20 ticks (1 s) by the sweep. They are at their checkpoint, or at the pallet if they have no
  valid one. They see "The heat turns you back. Eight badges first." and "You are back at <place>."
- **G-b.** `ng.b` for that player goes up by exactly 1 per bounce. Their `bo.cp`, `bo.cpx`, `bo.cpy`, `bo.cpz`, their
  spawnpoint, items, money and party are unchanged.
- **G-c.** A player holding `cobblers:flag/gym8_cleared` is never moved and sees no line.
- **G-d.** No player is ever left in the Nether without the flag for more than 20 ticks, and none lands inside a
  portal.
- **G-e.** A player in `cobblers:pocket` is never moved by this pack.
- **G-f.** The boot log has no error naming `cobblers:nether_gate/*`. `datapack list enabled` names
  `file/cobblers_nether_gate` and `file/cobblers_blackout`.

## Dependencies

- Staging only, under the coordination lock (CLAUDE.md "Live server safety"). Never the live world.
- Packs: `cobblers_nether_gate` and `cobblers_blackout` (the checkpoint functions it calls, contract C20). For case 10
  also `cobblers_entei_boss` and `cobblers_portals` (EXP-059's setup).
- Two accounts for cases 6 and 10b (`docs/STATE.md`, the second-account note). Every other case needs one.
- An operator at the console for grants (`advancement grant <p> only cobblers:flag/gym8_cleared`) and teleports.

## Procedure

Before each case: the test player is in survival, in the overworld, without the flag (`advancement revoke <p> only
cobblers:flag/gym8_cleared`). Read `scoreboard players get <p> ng.b` before and after.

1. **Portal, the trigger alone.** Stop the backstop: `schedule clear cobblers:nether_gate/keeper`. Light a portal
   anywhere and walk through. Pass: back in the overworld at once (G-a), which proves the trigger fired, because
   the sweep is off. Walk through again: bounced again, so the advancement revoked itself. Restart the backstop:
   `function cobblers:nether_gate/load`.
2. **No checkpoint.** A player who has never used a healer or waystone (`scoreboard players reset <p> bo.cp`), then
   the portal. Pass: lands at the pallet, and the line names Hometown.
3. **A rider.** Mount a rideable Pokemon (Mudsdale or Charizard, the two verified rides). Ride into the portal; if
   vanilla does not take a mounted player through, use `execute in minecraft:the_nether run tp <p> 0 80 0` while
   mounted. Pass: the player lands dismounted at their checkpoint. **Record**: where the Pokemon is (`execute in
   minecraft:the_nether run data get entity @e[type=cobblemon:pokemon,limit=1,sort=nearest] Pos`), whether the
   party screen shows it recalled, and whether it can be sent out again. A Pokemon lost from the party is a FAIL.
4. **An operator's /tp.** `execute in minecraft:the_nether run tp <p> 0 80 0`. Pass: G-a.
5. **Waystones.** Grant the flag to a helper, who places a waystone in the Nether. Revoke nothing from the helper.
   The test player warps to it from an overworld waystone. Pass: G-a for the test player; the helper stays.
6. **Two together** (two accounts). Grant the flag to A only. A and B step into one portal within a second of each
   other. Pass: A stays in the Nether with no line (G-c); B is bounced (G-a).
7. **A login inside the Nether.** `datapack disable "file/cobblers_nether_gate"`. Walk into the Nether, log out.
   `datapack enable "file/cobblers_nether_gate"`, then log in. Pass: back in the overworld within 1 s of joining.
8. **A respawn anchor.** With the pack disabled, charge and set a respawn anchor in the Nether. Enable the pack. Back
   in the overworld, `kill <p>` and respawn. Pass: within 1 s of respawning, the player is in the overworld. **Record**
   whether the blackout's own arrival (`blackout/arrive`) or this gate moved them first, and that they were moved
   once to a safe place either way.
9. **Operators.** In the Nether, `gamemode creative <p>` and `gamemode spectator <p>` for 5 s each: not moved. Then
   `gamemode adventure <p>`: bounced.
10. **The Entei's pocket** (EXP-059's setup).
    - (a) A player with `champion_cleared` AND `gym8_cleared` eats an Ember Sigil in the Nether. They are in their
      slot in `cobblers:pocket`, and stay there for 10 s (G-e). They leave by the arch, are back on their Nether
      block, and stay (G-c).
    - (b) The same with `gym8_cleared` revoked before they leave by the arch. Pass: they land on their Nether block
      and are then bounced to their checkpoint within 1 s. `#s1 eb.own` reads 0 within 1 s (the slot is freed).
11. **A portal inside a structure.** Build a portal inside a house, or in a cave under a town. Go through. Pass: the
    landing is the checkpoint, nowhere near the portal. Then build a portal **on** the checkpoint spot (inside the
    Center, where the player stood to heal) and go through it. **Record** what happens. The player lands in the portal
    block. Expected: they are carried back into the Nether after vanilla's portal delay and bounced again, until they
    step out. This is a loop the player can walk out of, not a trap. A player who cannot step out is a FAIL.
12. **Cost.** With nobody in the Nether, `tick query` for 60 s with the pack enabled, then disabled. Pass: the
    difference is inside the measurement's noise. The pack's stated cost is 3 command lines per 20 ticks, about
    0.15-0.57 us a tick (`docs/mechanics/TOWN_TICK_BUDGET.md` section 1b's calibration, an upper bound).

## Results

Not run.
