# Morning report, 2026-09-29

Written through the night as things landed. `docs/NIGHT_REVIEW.md` holds every decision taken without you and why.

## What landed

### Phase 1 — experiments and measurements

- **EXP-047, the pocket dimension: it works.** A custom dimension registers, loads with no new error, is writable
  and holds entities. Three results that shape the portal design:
  - **Our per-tick systems reach it for free.** A selector with no positional constraint is not dimension-scoped
    here — a kill run `in minecraft:overworld` destroyed an entity in the pocket dimension. So the blackout tick,
    the water ladder, the trainer cycle and the progression checks all apply to a player there with no change. And
    anything positional (a habitat block's range, a trainer seat) is confined for free. The flip side: a global
    selector also reaches *into* it, so anything meant to be overworld-only needs an explicit dimension predicate.
  - **Its contents do not survive a re-export.** The blocks live at `<world>/dimensions/`, inside the world folder,
    and a re-export makes a new one while only players are carried. **Your hypothesis is disproved as things stand
    — but the refinement is better than the negative:** a pocket dimension is the *only* part of the world that
    could be carried verbatim by a folder copy, because nothing regenerates it. Extending `reapply.py carry` to copy
    `dimensions/` would make it true, and it is a small change.
  - Spawning, habitat-pool resolution and the callbacks **need a player** and are recorded untested, not assumed.
- **The villager is measured: ~20 us a tick** (swept 0-64 in the empty pocket dimension, nobody online). So ~220
  villagers reach 10% of a tick and a 40-50 villager town costs ~2%. Villagers are not the constraint. **`T`, the
  rctmod trainer, is still unmeasured** — it cannot be plain-`summon`ed, and the sweep stopped rather than report a
  number from an empty pen.
- **`/tick query` prints to 0.1 ms**, confirmed, so every single-entity figure is multiply-and-divide.
- **The water ladder: 35 command lines a tick down to 7** on the dry path, with the two `effect clear` commands off
  it entirely. Contracts C1 and C2 green, 337 tests green. Vanilla air on land now runs from a
  `minecraft:effects_changed` advancement, and the wet path still clears unconditionally so the rule cannot break in
  water. **The land clear is unverified in game** — that is the one behaviour this could regress.

### Phase 2 — content

- **The trainer rematch fault is fixed (interim)** and the strict xfail that pinned it is gone, removed because the
  fix made it pass and `XPASS(strict)` forced the cleanup. `test_trainer_cycle.py:175`, which asserted the buggy
  clause as correct, is rewritten with a guard against its return.
- **Legendaries: six chambers built, four blocked by name.** Audit 376 checks, 0 failures, proved fail-closed on six
  tampered inputs. See the review list — five gates are a proposal, not your decision, and there are two new Celebi
  faults.
- **Stone faces re-sited into their towns**, rebuilt, audit CLEAN (22 faces, 13,953 cells). One face had to be
  re-anchored after the repaint put trees over it.

### Phase 3 — the export

- **`cobblers-dryrun12` is built**, `seed_match: true`, and the **margin relief ran for the first time** (7,056
  tiles) — the seamounts and the carried-off map edge have never existed in a world before tonight.
- **The water shape is applied**: 19,027,615 columns changed, the new heightmap is canonical, and the old sha is
  kept in `previous_sha256`, so it is reversible.
- Its dependents were re-measured until `validate_data` read **0 errors**: Pacifidlog folded onto its new site,
  regions, cells and town grounds re-measured, the paint regenerated, the visibility claims re-measured.
- **Prepare's whole-build gate passed**: 4,468 function files, 0 problems, 26 places, 32 pack donors, 35 steps,
  every function pack covered.
- **Install is clean**: every pack and config the repo builds is installed and current.
- **The re-application ran 35 steps with 0 problems** (238 s), the world was audited on a stopped copy, and the
  **Distant Horizons pregen completed over the whole border**.
- **The region question closed itself exactly as predicted.** 454 files after the export; after the pregen, 477, and
  **all 400 border regions are present, 0 missing**. The empty far-north ocean strip was indeed the pregen's to fill.
- The watchdog was turned off for the run as the runbook requires and **has been restored to `max-tick-time=60000`**
  (backup at `server.properties.watchdog-backup`).

**Region count, explained rather than waved through.** 454 files where the old world has 491 and the runbook names
484. Inside the border 390 of 400 are present; the 10 absent are the far-north sea strip beyond the authored
landmass, empty ocean WorldPainter had nothing to write for, and the pregen is the step that fills them. The 37 the
old world has extra are spill from having been played.

**Three things the export broke, all caught by fail-closed audits and fixed rather than bypassed:** the drowned
Pacifidlog docks and the Sound ferry (retired per the plan STATE already recorded), a stone face under the new
canopy (re-anchored), and the Route 2 shrine (moved clear of both the new shore and the new trees). A fourth, the
now-orphaned ferry charge macro, was caught by prepare's own orphan gate.

## The world audit

Every settlement clean except two, and one of those is expected:

- **`jungle_ruins`** — 469 causeway cells with water on the road, the great hall 59.8% standing. **That is the sea.**
  The ruins stood on the Jungle Isle your 2026-09-27 decision removed. Not a build fault; it surfaces exactly where
  it should, and it stays until the ruins are re-sited or removed.
- **The Displaced City cavern shell has 12 voids** (`shell_columns: 60992, shell_voids: {"in the walls, air": 12}`)
  where the last export measured **0**. They are described as in the walls rather than reaching the surface, so they
  may be isolated pockets rather than a way in — the audit cannot tell, and neither can I from outside. I did not
  re-run the seal: it had already run once in this world and would write identical blocks. Worth a look before the
  city is played.

## Where the work is

**PR [#95](https://github.com/Millerb7/cobblers/pull/95)**, branch `night/2026-09-29-water-export`, 39 commits.

**A mistake to know about:** those commits were first pushed to `docs/gym-q1-interiors` **after PR #93 on that branch
had already merged** — the exact failure the repo's rules warn about, and the second time I have done it. They are on
a clean branch now and nothing is lost, but merging #93 brought none of this.

## What was cut, and why

See `docs/NIGHT_REVIEW.md`. In short: the Viltri Ravine (held by you, never in the audited design), `build_routes`
(audit C2 proves no road changed), the employed-villager sweep, `T`, both two-player measurements (second account),
and everything player-gated in EXP-047.

## Cost per agent (context x turns, `tools/session_cost.py`)

| agent | turns | weighted |
|---|---|---|
| Legendary placements and gates | 114 | 3.21M |
| Stone faces survey and redesign | 134 | 3.14M |
| Gym interiors data and gym 1 | 104 | 2.49M |
| Design eight gym interiors | 39 | 1.11M |
| Town tick-cost inventory and plan | 69 | 0.90M |
| Water ladder early exit | 49 | 0.64M |
| Failing test for the rematch fault | 21 | 0.23M |
| **agents together** | | **11.7M** |
| **this session** | 464 | **23.2M** |

The main session is the expensive one, as always — 435k of context per turn on average, and 728k by the end. Seven
agents did the parallel work for half what the session itself cost.

## The state of the server right now

`cobblers-dryrun12` is **booted and running**, saved, pregenerated, with the coordination lock still held by this
session. Log in and fly whenever you like — but read the carry note first, because you will arrive as a new player.

## Where to fly, most important first

The world is `cobblers-dryrun12` (universe `cobblers-runtime-proof/dryrun12`). **Read the carry note in
`NIGHT_REVIEW.md` before you log in** — your character did not come across, so you will arrive fresh.

**1. The water, everywhere. This is what the night was for.** Every coast, lake bed and river was re-cut:
19,027,615 columns. Fly the shore anywhere and it should read as a shore rather than a cliff into flat blue. The
lakes have wadeable margins now (Viltri 19%, Shrew 11%, Arrow 13%, Marshy Marsh 25%, Tilpey 13%).

**2. The map edge and the seamounts — these have never existed.** The margin relief ran for the first time
(7,056 tiles), so beyond the landmass there are now seamounts and a carried-off edge instead of a blank wall.
Five summits to look for: `(-600, 2200)`, `(-500, 6000)`, `(4200, -700)`, `(9000, 1800)`, `(1500, 8900)`.

**3. The Jungle Isle is gone and Pacifidlog has moved.** The isle is a bank 4-9 deep; the town is at its new
square **(5160, 7380)** with a mainland jetty on the plateau's south beach. **The jungle ruins are drowned** at
y55-61 and need re-siting — review item 1.

**4. The six legendary chambers.** Mesprit under Arrow Lake, mouth **(2790, 4606)**; Azelf under Marshy Marsh,
mouth **(5158, 2166)**; Regirock **(4800, 5200)**; Regice **(3900, 2050)**; Regigigas **(3560, 1760)**; Groudon
**(6672, 5508)**. Each is sealed until its gate opens, so you are looking at the portal and the ground, not the
chamber.

**5. Gym 1's interior — the first gym that is a place rather than a room.** Brock's gym at Pallet's plateau town;
the works are carved beneath, shell `(1812, 140, 3667)`-`(1838, 156, 3690)`, and the way down is a scaffolding
column at **(1817, 3685)** standing where the healing machine used to be. Three fights and one climb.

**6. The stone faces, now in their towns** (they were 121-205 blocks out; they are 30-64 now, the Scar 110-119):
tea town **(2667, 3633)**, Mining Town **(6627, 5755)**, gorge hamlet **(6860, 4347)**, Northlight
**(7289, 1601)**, Viltri Light **(558, 4565)**, the Scar **(2007, 988)**, Displaced City **(3334, 1850)**.

**7. No gym has a healing machine any more.** All eight, replaced with cut stone of the town's palette. Check one
reads as furniture rather than a gap.

**8. The six wayside shrines**, one moved tonight: Brock's cairn (1609, 3767), **Misty's lantern stone now at
(1699, 2873)**, the fork below Surge's (1699, 1501), Koga's niche (4509, 2303), the Tableland altar (4765, 5622),
the Merian cairn (2820, 1212).
