# The authored legendary encounters

**Status: designed and generated, nothing built in any world.** 2026-09-29.
Data `data/legendaries.json`, generator `tools/legendaries.py`, audit
`tools/legendaries_audit.py`, re-application step `R14L`. Six chambers are
emitted and four encounters are blocked with a named reason.

This note covers only the **authored** encounters. Every other legendary is
Tier B and stays what `docs/story/FUTURE_SIDE_CONTENT.md` decided: paste a
compatible structure into a fitting biome, gate it by badge count, no bespoke
work.

---

## 1. What is here, and what stops each blocked one

| Encounter | Where | Gate | State |
|---|---|---|---|
| **Mesprit** | Arrow Lake, mouth at (2790, 4606), bed y55 | `gym3_cleared` | **emitted** |
| **Azelf** | Marshy Marsh, mouth at (5158, 2166), bed y63 | `gym5_cleared` | **emitted** |
| **Uxie** | Lake Tilpey, under the Weeping Elder island's apron | `gym7_cleared` | **blocked: the water export** |
| **Regirock** | The Scorched Plateau, portal (4800, 5200), y144 | `gym4_cleared` *(proposed)* | **emitted** |
| **Regice** | The Glacial Tear's Upper Trough, portal (3900, 2050), y101 | `gym6_cleared` *(proposed)* | **emitted** |
| **Registeel** | The Rift's anomalous chamber | `gym7_cleared` *(proposed)* | **blocked: the Rift plan** |
| **Regigigas** | Beside the Displaced City, portal (3560, 1760), y126 | `gym8_cleared` *(proposed)* **and the three golems met** | **emitted** |
| **Groudon** | The Craters' eastern bowl, portal (6672, 5508), y108 | `gym8_cleared` *(proposed)* | **emitted** |
| **Lugia** | The Maelstrom Trench | Dive **and** `champion_cleared` | **blocked: no seabed** |
| **Celebi's wake** | The Route 1 sapling | `gym8_cleared` *(proposed)* | **gate built, trigger open** |

The trio's gates (3, 5, 7 badges) and Lugia's are the owner's, from
`docs/mechanics/WATER_MAP.md`. **Every gate marked *proposed* is this design's
guess**: no document fixes a badge for the four bespoke encounters, and the
owner has not seen these.

### Why each blocked one is blocked

- **Uxie.** `data/water_shape.json` gives Arrow Lake a keep zone
  (`mesprit_grotto_floor`, radius 12) and Marshy Marsh one (`azelf_pit`,
  core_depth 20) expressly so those two mouths survive the pending water export.
  Lake Tilpey's `keep` list is **empty**: its whole bed is rewritten — a shelf
  14-44 wide off every shore and island, a 10-deep drop-off over 6 blocks, then
  a basin floor remapped by `floor_gamma`. Uxie's mouth belongs under the
  island's apron, which is exactly what changes, and the new bed Y there cannot
  be computed without `derived/water_shape`. **The fix is one line in
  `data/water_shape.json`:** give `lake_tilpey` a keep zone
  `{"id": "uxie_grotto_floor", "radius": 12, "around": <the resolved mouth>}`,
  as Arrow Lake has. Then the record becomes `sited` with nothing else changed.
- **Registeel.** The Rift's authored voids — `rift_deep`, `vr_caves`,
  `rift_mines`, `rift_league_tunnel`, `deep_city` — are seeds and rules in
  `data/`, not boxes. Their extents live in `derived/` and `build/`, which an
  isolated worktree does not have and must not regenerate. A chamber carved
  blind inside the Rift could intersect Victory Road or the Deep's terraces and
  nobody would find out until somebody walked into it.
- **Lugia.** The trench is a proposal with no seabed pass and no build
  (`WATER_MAP.md`: "no seabed pass, no build"); `data/regions.json` holds only a
  `trench_axis`. There is no seabed today to put a mouth in, and the water
  export rewrites that ground anyway.
- **Celebi's wake.** Below, section 5.

---

## 2. The chamber: solid first, then the void

Every chamber is **parametric**, not a noise model. A stone envelope is filled
**solid first** and extends `shell_margin` (4) beyond every carved block in all
six directions; the void is then cut out of it. So `WATER_BUILD_PLAN.md` 4.5's
audit 1 — "at least 4 blocks of rock round every void, no void connecting to
the water but the passage" — holds **by construction** and is proved by
arithmetic instead of by a dilation over a world.

    lake_grotto      mouth in the lake bed
                     -> flooded shaft (its own stone sleeve down from the bed)
                     -> flooded passage, 3 wide, no more than 20 blocks
                     -> a pool cut 4 deep into the chamber floor
                     -> the air chamber, dry above the pool's surface
                     -> a barrier partition
                     -> the alcove the legendary stands in

    sealed_chamber   a stone plug at the surface portal
                     -> a dry ladder shaft
                     -> a short adit
                     -> the chamber, the legendary at its far end

The **sleeve** is the second half of the seal: the shaft's own stone collar,
filled from the envelope's roof up to the *lowest* ground over its own 11 by 11
footprint, so it never raises the lake bed. That is the Displaced City tunnel's
precedent — "its seal turns gravel and sand to stone". The hole in the bed is
therefore stone-rimmed, and the audit bounds its unsleeved lip at 3 blocks.

**The air chamber.** A legendary battle outlasts Surf's air (`WATER_MAP.md`
section 0: about 61 s at depth), so the player swims the passage, surfaces in
the pool and fights on dry ground. An air pocket at depth is stable in
Minecraft — water does not rise into air — but that is still assumption P1 in
`WATER_BUILD_PLAN.md` and has not been seen in game.

**Lanterns, never light blocks** (`docs/STATE.md`, "Places are lit as towns"):
nine hanging lanterns under each chamber roof.

---

## 3. The gate

Two things had to be true at once: a legendary must be **unreachable** before
its badge, and **visible** to everyone from the first time they pass the place
(`WATER_BUILD_PLAN.md` 4.2: "the trio are shown to every player whatever their
badges"). So the gate is **blocks**, not entity state:

- a **grotto's mouth is always open**. A player at 2 badges can swim Arrow
  Lake's passage and stand in Mesprit's chamber, and see it through a wall of
  barriers they cannot pass. The partition opens while a player carrying
  `cobblers:flag/gym3_cleared` stands in the outer chamber and closes when none
  does.
- a **sealed chamber's plug is rock** until a qualified player stands on the
  portal. It then opens **and never closes again**, so nobody is ever sealed in.

The gate is one advancement predicate and it appears on **every line that can
open a chamber**:

    execute if entity @a[<the outer chamber>,advancements={cobblers:flag/gym3_cleared=true}] \
      unless score #mesprit cobblers.leg matches 1 run function cobblers:legendary/mesprit/open

The audit parses that out of the generated function and fails on any line that
opens a chamber without the full predicate (`WATER_BUILD_PLAN.md` 4.5 audit 4).
Regigigas's predicate additionally names all three golems' `met` advancements.

**Why blocks and not the entity.** `Unbattleable` would stop a battle but not a
thrown Poké Ball and not a sword: Cobblemon ignores `Invulnerable`, and a sword
killed the sleeping Celebi in three hits (EXP-023). A barrier stops a hit, an
arrow and a thrown ball, which is why the Celebi is walled in one, and it is why
these chambers are too.

**The driver is cheap on purpose.** `docs/mechanics/TOWN_TICK_BUDGET.md` is
counting the server's idle floor, so nothing here runs per tick. One scheduled
function every 20 ticks carries **one** `execute positioned ... if entity
@a[distance=..R]` line per emitted chamber — six lines a second, server-wide —
and nothing else runs until somebody is near. That is the Celebi keeper's shape.

**Per-player state** is an advancement, `cobblers:legendary/<id>/met`, granted
by the gate to the qualifying player. Advancements are per player, persisted,
and carried across a re-export by `reapply.py carry`. Each one is declared in
`data/progression.json` `quest_fields` as `quest.legendary_<id>.met`, with its
carrier named: the advancement, **not** Cobblemon player data, because the gate
is an mcfunction and a function cannot read `q.player.data()`.

---

## 4. Placement: RCON, never a pack

A legendary is an **entity**, so a re-export erases it, and `spawnpokemonat`
inside a datapack function spawns nothing until a `/reload` (EXP-046 question
1). Every one is therefore summoned over RCON by `reapply.py` **R14L**, exactly
as the Celebi is by R14C: force-load, carve, summon if none is tagged there,
dress, shut the gate, release.

Dressed dormant with the flags EXP-023 proved kept across a restart —
`Unbattleable`, `NoAI`, `NoGravity`, `PoseType: "SLEEP"`, `RecalculatePose 0b`,
`HideLabel`, `PersistenceRequired`, `Silent` — and `PersistenceRequired` is what
stops the despawner taking it (EXP-046 question 2). Waking sets
`Unbattleable 0b` and `RecalculatePose 1b` and lets Cobblemon choose the pose:
`PoseType` is **not** set to any other value, because only `"SLEEP"` is proven
and principle 7 forbids guessing the rest of the enum.

The keeper — dedupe, and put it back on its pedestal — runs **only while the
chamber is shut**, so it can never drag a Pokémon out of a battle in progress.

---

## 5. The Celebi's wake: what was settled and what was not

The brief was to establish from the repo whether an advancement trigger can
carry the wake. Two things were established, and they point opposite ways.

**It can, in principle.** `minecraft:item_used_on_block` is a real vanilla
advancement trigger, and this repo already proves the shape: `ADR-002` and
`tools/rewards_pack.py` use a `minecraft:location` advancement as a per-player,
once-only carrier that runs a function as the earning player, and it works.

**It cannot, as EXP-023 proposed it.** An advancement fires **once per player,
for ever**, and an advancement's criteria **cannot test another advancement**.
So an advancement whose criterion is only "used item X on block Y" is *burned*
by a player who tries the right item before the gate is open — and that player
can never wake the Celebi again. This is a real fault, not a detail. Closing it
needs either a criterion this repo has not used, or a tick-driven check like
this pack's own gate, and neither can be settled offline.

**A second fault, found while building the gate.** `cobblers_celebi`'s keeper
(`tools/sapling_celebi.py` `celebi/keep`) re-merges the dormant NBT onto the
Celebi **every 40 ticks while a player is within 48 blocks**. A wake that only
flips the entity's flags would be undone within two seconds. The keeper has to
learn the woken state before the wake is built.

**Which item** is also undecided, and no document names one.

So: the **gate is built and the trigger is not**. `cobblers_legendaries` ships
`cobblers:legendary/celebi_wake/open`, which checks the badge flag, grants the
`met` advancement, fills the barrier shell (read from
`tools/sapling_celebi.py`'s own `shell_box`, so the two can never drift) with
air and wakes the entity. **Nothing calls it.** The badge check lives *inside*
that function rather than in a caller, so whichever trigger is chosen later
inherits the gate instead of having to remember it. `legendary/tick` names it in
a comment so `reapply.py`'s `uncovered()` check sees that nothing driving it is
a decision rather than a pack function silently lost.

---

## 6. The audit

`tools/legendaries_audit.py` is offline and fail-closed in five ways:

1. **An audit that finds nothing to check fails.** No sited encounter, no carve
   function, no tested write or no tested gate line is an error. (Audits passing
   on empty output were one of the four fail-open defects Codex found in the
   re-export path.)
2. **Nothing is taken from the artifact being checked.** The geometry is
   recomputed from `data/legendaries.json` and `tools/ground.py`; the generated
   functions are then read as *text* and every `fill` and `setblock` in them is
   tested against that independent geometry.
3. **"Not checkable" is a failure.** A keep zone, gate flag or quest field that
   cannot be resolved fails; it is never skipped.
4. A record that is not `sited` must have **no** functions in the pack, and one
   that is must have all of them.
5. The gate is **parsed**, not assumed.

It also checks the roof clearance against the lowest heightmap ground over the
envelope's own footprint, the sleeve's flatness, the four-block margin on every
void face, the walkable battle area and headroom, the passage length, that the
flooded passage meets the pool below its surface and the air chamber sits above
it, every fill against Minecraft's 32,768-block limit, the spawn-free zone's
grid and coverage, and — for each grotto — that its declared keep zone really
exists in `data/water_shape.json` and really covers the sleeve, measured on the
heightmap.

**376 checks, 0 failures**, and proved to fail on six tampered inputs: a gate
stripped out of a `near` line, a write moved outside the shell, an empty pack,
no pack at all, every encounter blocked, and a level above the catch cap.

---

## 7. What is not settled

1. **Shared or per player.** An entity's NBT is world state, so a qualified
   player who opens a grotto opens it for everyone in the chamber, and the first
   catch takes the encounter for the whole server. `WATER_MAP.md` decision 1
   leaves this open for the trio and `ENCOUNTERS.md:397` for Lugia. The build is
   **shared**; per player would need the scene runtime's per-player actors
   (EXP-034, which waits on a second account).
2. **A woken legendary can be killed.** Once a gate opens, the legendary is as
   killable as any placed Pokémon. The re-application restores it, but within a
   session it is gone and the keeper cannot summon it back.
3. **Every level rests on an unread number.** `data/level_cap.json` (the owner,
   2026-09-28) blocks a catch outright above the thrower's RCT cap — a Master
   Ball included. The per-badge caps come from the Cobbleverse RCT series data
   and **have not been read out**; `data/legendaries.json` `level_caps` is a
   placeholder, marked provisional, for `trainer-balance-designer`. A legendary
   authored above its gate's cap is a wall, not a reward. **Celebi is level 70
   today and above every provisional cap**, so as it stands it cannot be caught
   at all: whether the wake lowers it, or Celebi is a battle and not a catch, is
   a balance decision nobody has taken.
4. **The badge gates of the four bespoke encounters** are this design's
   proposals.
5. **Azelf's mouth is a stated deviation.** `WATER_BUILD_PLAN.md` 3.3 puts it
   "under the root tangle" of the drowned trees; the roots stand on the export's
   new shelf humps, which do not exist and are not a kept surface. The mouth is
   on the kept pit floor at the anchor instead, and the boardwalk down the pit
   wall is the lake-sites pack's dressing that will meet it.
6. **The spawn-free zones are declared, not merged.** Each sited encounter
   carries one in `data/legendaries.json`; they are **not** written into
   `data/spawn_suppression.json`, which was in flight in another session.
   Whoever merges them must accept that a spawn-free zone is a 2-D column, so a
   grotto's zone also silences about 40 by 40 blocks of the lake surface above
   it.
7. **Nothing here has run.** No chamber has been carved in any world, no gate
   has been opened, and no legendary has been summoned. A generated datapack is
   not proof that a feature works.
