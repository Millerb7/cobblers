# Larvesta as an a-lite starter (research, 2026-10-08)

**Research only. Nothing is built and no data changed.** Read with Python zipfile from the 1.8.0 jar in the offline
snapshot (`cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar`, "the jar"), the
snapshot's `datapacks/`, and `COBBLEVERSE/datapacks|resourcepacks`. Fights are `tools/mythical_starters.py`'s own
`measure()` (battle_sim's duel), run from a scratch script that adds candidate lines to a copy of the record and
writes nothing in the repo. No world, no server.

**A premise to correct first.** The repo's set is five lines, not seven (`data/mythical_starters.json` `lines`,
`modpack/config/cobblemon/starters.json:10-14`); Larvesta would be the sixth here. And **Kubfu is not two-stage in the
set**: it walks Kubfu-Starter (5) -> Kubfu-Starter-Grown (30) -> Urshifu (45), `data/mythical_starters.json:241-321`.
Every line in the set has both points. Natively Kubfu is two-stage; in our set nothing is.

## 1. Can it be done, and is it the same work?

**Yes, and it is the same work, not new work.** VERIFIED in the record: the first step is already a same-species
form change on four of the five lines -- Kubfu `"kubfu unaspect=cobblers_starter_1 aspect=cobblers_starter_2"`
(`data/mythical_starters.json:260`), Type: Null (`:375`), Poipole (`:472`), Meltan (`:580`). Only Cosmog's first step
changes species (`:140`, to Cosmoem). Weak Larvesta -> Larvesta at 30 is exactly the Kubfu step. The generator needs
no code change for it: `tools/mythical_starters.py` groups a line's stages by species into one
`species_additions` file with two forms (`files()`, `:305-318`), and `check()` already expects a same-species stage 2.

**The one constraint: "Larvesta proper" at 30 must still be OUR form, not native Larvesta.**
- VERIFIED: native Larvesta evolves to Volcarona at **level 59** (jar `species/generation5/larvesta.json:194-206`,
  `minLevel` 59, with `learnableMoves: [quiverdance]` and a Shed Shell drop). 59 is above every gym cap (aces end
  at 55; the cap is 60 only after gym 8, `docs/STATE.md` "League level cap").
- RELAYED (`tools/mythical_starters.py:11-13`, from `NATIVE_STARTERS_1_8_0.md` 4a, src `FormData.kt:210-211`): a
  form's own `evolutions` never fall back to the species list. So if stage 2 dropped every aspect, it would be
  native Larvesta and evolve at 59. It must carry `cobblers_starter_2` with its own Volcarona-at-45 evolution, as
  Kubfu's stage 2 does.
- RELAYED (`tools/mythical_starters.py:17-20`): `species_additions` `evolutions` APPEND, so a species-wide level-45
  evolution cannot replace the 59 one, and would also reach wild Larvesta, which we spawn at 38-53
  (`data/spawns.json` `surface.east_cones.larvesta`, `surface.great_crater.larvesta`, `surface.south_east_dunes.larvesta`).

**A decision conflict, not a mechanism one.** The decided curve is 330 / 430 / native (`NATIVE_STARTERS_COST.md:60`),
and the audit pins it: `BST = {1: 330, 2: 430}` (`tools/mythical_starters_audit.py:62`). Native Larvesta is **360**.
A stage 2 with Larvesta's own stats fails the audit and, measured below, falls out of the band. A stage 2 at 430 in
Larvesta's shape is stronger than any wild Larvesta (101 Atk vs 85).

Unproven links are the same as the other lines' (EXP-049, still NOT RUN: `experiments/EXP-049-native-starter-evolution/README.md:3`).
Larvesta adds none.

## 2. The numbers (VERIFIED, the jar)

| | Larvesta | Volcarona |
|---|---|---|
| file | `species/generation5/larvesta.json` | `species/generation5/volcarona.json` |
| `implemented` | true (`:2`) | true (`:2`) |
| types | Bug / Fire | Bug / Fire |
| abilities (`:17`) | Flame Body, hidden Swarm | Flame Body, hidden Swarm |
| baseStats (`:24`) | 55 / 85 / 55 / 50 / 55 / 60 = **360** | 85 / 60 / 65 / 135 / 105 / 100 = **550** |
| evolution | `level_up` -> volcarona, `minLevel` **59**, no other requirement (`:194-206`) | none (`:276`); `preEvolution` larvesta (`:275`) |
| exp group / catch rate | slow / 45 | slow / 15 |

Level-up: Larvesta Ember, String Shot, Absorb 1, Flame Charge 6, Struggle Bug 12, Flame Wheel 18, Bug Bite 24,
Screech 30, Leech Life 36, Bug Buzz 42. Volcarona has Quiver Dance and Fiery Dance at 1, Heat Wave 48, Hurricane 62.

**COBBLEVERSE does not override either species.** `COBBLEVERSE-DP-v31.zip` (snapshot and `COBBLEVERSE/datapacks`)
carries only `spawn_pool_world/0636_larvesta.json` and `0637_volcarona.json`; no `species_additions` file in any
scanned datapack or mod targets them. Unlike four of the five, **both are on in the bare jar**: no addon dependency.
The 59 is the surprise here, the way Meltan's anvil was: a plain Larvesta starter would not evolve until after gym 8.

Comparison BSTs, VERIFIED in the jar: Urshifu 550, Silvally 570, Solgaleo and Lunala 680, Naganadel 540, Melmetal 600.

## 3. Models (VERIFIED, the jar)

Both modelled in the Cobblemon jar itself: `assets/cobblemon/bedrock/pokemon/models/0636_larvesta/larvesta.geo.json`,
`.../0637_volcarona/volcarona.geo.json`, with posers, animations, textures (normal, shiny, alpha) and resolvers
`resolvers/0636_larvesta/0_larvesta_base.json`, `resolvers/0637_volcarona/0_volcarona_base.json`. The base variation
has `"aspects": []`, so it matches a Pokemon carrying `cobblers_starter_1/2`. No installed resource pack replaces them
(the only other hits are minimap icons in `E19 Cobblemon Minimap Icons.zip`, and dex entries in the uninstalled
"z DO NOT ENABLE z [Hydro Reanimodel]"). ASSUMED, not seen: that the client renders the aspected forms with that
model (the same unrun assumption as the other five).

## 4. The two versions, costed

**A. Three points (weak form 5, grown form 30, Volcarona 45).** The existing pattern; no generator code changes.
Files: `data/mythical_starters.json` (one line, with an authored movepool and `potent_at`);
`modpack/config/cobblemon/starters.json` (one entry); `tools/mythical_starters_audit.py` `LINES` (`:67-73`, plus its
"five" wording) and `tests/test_mythical_starters_audit.py` (`FIVE`, `:270`); `data/scenes.json` Oak's lab (a sixth
stand, `:27-38`) with `tools/oak_starter_audit.py` (P4 "five_entries", `:699`) and `tests/test_oak_lab_scene.py`;
the player guide re-generated (`tools/player_guide_starters.py`, `docs/player/starters.html`). **About 2.6M for the
builder (a narrow follow-up) plus about 3M for the independent audit/test update: about 5.6M**, plus a balance pass on
the movepool (no runnable check; unmeasured).

**B. Two-stage (Larvesta 5, Volcarona 45).** Still needs an aspected form: a plain Larvesta evolves at 59, and a
species-wide 45 also hits wild ones. And the tools reject a one-step line: `check()` requires stages exactly 1 and 2
(`tools/mythical_starters.py:154-156`), stage 2 stronger than stage 1 (`:187-188`), a stage-1 result carrying
`aspect=cobblers_starter_2` (`:245-246`); `measure()` assumes two stages (`:377-378`); the audit requires 330/430
and `2 x lines` forms (`mythical_starters_audit.py:62`, `:437-439`); the guide states tiers 1 and 2 are one total
for every line (`player_guide_starters.py:11-12`, `:364`). So B is everything in A **plus** schema changes in the
generator, the audit and the guide: **about 4M for a builder plus 3M for the audit: about 7M.** **B costs more than A,
not less**, and breaks the identical points the set was built on.

## 5. Power (MEASURED, battle_sim; 1v1, IVs 15, no items, damaging moves only)

Wins of leader Pokemon at each gym's cap (20/25/30/35/40/45/50/55), with the stage a player has there, pool = Larvesta's
native level-up moves to 42:

| line | g1 | g2 | g3 | g4 | g5 | g6 | g7 | g8 | before 45 (of 19) | from 45 (of 16) | total /35 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Cosmog | 0 | 1 | 0 | 2 | 2 | 5 | 5 | 5 | 5 | 15 | 20 |
| Kubfu | 2 | 2 | 2 | 0 | 1 | 4 | 2 | 6 | 7 | 12 | 19 |
| Poipole | 0 | 2 | 1 | 4 | 1 | 4 | 4 | 2 | 8 | 10 | 18 |
| Meltan | 1 | 1 | 1 | 1 | 3 | 5 | 2 | 2 | 7 | 9 | 16 |
| Type: Null | 0 | 1 | 1 | 0 | 2 | 3 | 2 | 6 | 4 | 11 | 15 |
| **Larvesta A, 330 / 430 (Larvesta shape)** | 0 | 1 | 2 | 3 | 0 | 5 | 1 | 3 | 6 | 9 | **15** |
| Larvesta A, 330 / native 360 | 0 | 1 | 0 | 2 | 0 | 5 | 1 | 3 | 3 | 9 | 12 |
| Larvesta A, 330 / 430 (Volcarona shape) | 0 | 1 | 0 | 1 | 0 | 5 | 1 | 3 | 2 | 9 | 11 |
| Larvesta B, native 360 to 45 | 0 | 1 | 0 | 2 | 0 | 5 | 1 | 3 | 3 | 9 | 12 |

- **Only A at 330/430 in Larvesta's shape is in the band** (15-20): tied last with Type: Null. Native 360 at stage 2,
  and version B, sit at 12, below it.
- Volcarona from 45 scores 9 of 16, tied last with Meltan: Sabrina 5/5, but Blaine (Fire) 1/5 and Giovanni 3/6.
- Bug/Fire is 4x weak to Rock: every Larvesta form is 0/3 at Brock, and 0/5 at Koga.
- Its peak (A-430) is gym 4, Erika, already Poipole's peak (`data/mythical_starters.json:426-429`), and gym 6,
  already Cosmog's ground.
- **Simulator defect found:** `battle_sim.choose_moveset` ranks by power, STAB and accuracy and ignores the
  physical/special split (`tools/battle_sim.py:315-336`), so it gave a 135-SpA Volcarona Flare Blitz and Thrash.
  Re-run with a fixed Fiery Dance / Bug Buzz / Gust / Flame Charge set it still scores 9 of 16 (g6 5, g7 1, g8 3).
  The total does not move, but the report from that path should not be trusted for special attackers.
- **NOT simulated, and the real risk: Quiver Dance.** The duel has no set-up moves and no abilities. Volcarona gets
  Quiver Dance on evolving (`larvesta.json` `learnableMoves`) and at level 1. One boost to SpA, SpD and Speed per
  turn is the reason Volcarona is a famous sweeper. REASONED, not measured: in real play the final is very likely
  above this table's 9. The early stages are not.

## Recommendation

**Take version A, with stage 2 at 430 in Larvesta's shape.** The weak->real step is not awkward. It is the step four
of our five lines already use, and the generator takes it unchanged. Version B is the awkward one: it needs a form
anyway, costs more, and is weaker. Before building, the owner decides: (1) stage 2 is a 430 form, not native
Larvesta's 360 (360 fails the audit and the band); (2) whether a starter 4x weak to Brock's gym is acceptable; it is
the band's floor before 45, and its peak gyms overlap Poipole's and Cosmog's; (3) whether Quiver Dance is allowed,
since it is what the simulator cannot see.
