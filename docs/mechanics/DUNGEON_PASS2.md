# Dungeons, pass 2: the owner's notes after the first walk (2026-10-10)

Pass 1 (merged on `build/2026-10-09-dungeon-playtest`, staged 2026-10-09): the room kit (`tools/dungeon_rooms.py`,
`dungeon_kinds.py`, `dungeon_grid.py`, `data/dungeon_themes.json`, `docs/mechanics/DUNGEON_ROOMS.md`), fights
(`tools/dungeon_fights.py`), puzzles and vaults (`tools/dungeon_puzzles.py`), the clock (`tools/dungeon_clock.py`), three
dungeons in `data/dungeons.json` (night_shift 21 rooms, jungle 26, flooded_ruin 26), the independent audit
(`tools/dungeon_independent_audit.py`, 0 findings at `1f747ce`).

## The owner's notes (playing pass 1 on staging, 2026-10-10)
1. "Feels way too linear, always moving in a straight line; I should be going to different elevations, turning, etc."
2. "It feels arbitrarily long right now. A lot of the sequences are good, we just need more life in each room."
3. "Aim for a 40 minute completion length assuming a player grabs loot or Pokemon, so at 1.25x or so."
4. "The parkour should include longer and challenging jumps and not be a straight path."
5. "Puzzles should have less explanation; they are good though."
6. "Xaero's map should be off" (read as: inside the dungeons; confirm if everywhere).
7. "Really emphasize making rooms different shapes, not all boxes."
8. Chose replayability ideas **1, 2, 3 and 6** (below). Approved about 27M (20M + 6-8M).

## What changes
- **Shape (7).** The kit stops being boxes. A room has an OUTLINE: circle/oval, L and T halls, curving galleries,
  noise-carved caverns (alcoves, rock pillars, uneven floor), split levels with a chasm, rooms round a central feature.
  The theme sets the default mix: mine = rough cavern plus a few timbered chambers; jungle = organic clearings and
  root hollows plus the stepped temple court; ruin = round chambers, colonnades, broken half-flooded halls. The walk
  check, the pit plug, lighting and the independent audit all work on the real outline.
- **Elevation and turns (1).** Doors at different heights and on different sides; the route bends in z and doubles
  back; stacked rooms (balconies, drops into the room below, climbs back up); look-backs onto earlier rooms. The slot
  strip is 2,048 x 64 (`engine.slots`): use the width, and the y range, not only x.
- **Life (2).** Fewer connectors and fewer rooms, each richer: ambient Pokemon living in it (not fights, the sweep's keep
  tag), set dressing that tells what happened, sound and particles, light changes, something to notice per room.
- **Length (3).** Retarget each dungeon so `tools/dungeon_clock.py`'s required time is about 32 minutes at band 1 and the
  clock about 40 (x1.25). Jungle and ruin shrink most; the clock formula stays the arbiter. The test dungeons' own
  lockout (`lockout_of`) can then return to D17's hour.
- **Parkour (4).** Gaps up to 4 flat / 3 with a rise of 1 (the grid's jump limits), height changes, corners, a split
  route, checkpoints between sections; never a fall into the void (catch floors, as now).
- **Puzzles (5).** Strip the on-screen explanation to a short hint or nothing (`tools/dungeon_puzzles.py` messages).
- **Xaero (6).** Research first (the mod version in our pack, its documented server-side/dimension disable), then
  implement for `cobblers:pocket`; never assert a mechanism without the jar or a cited source.

## Replayability chosen (8)
- **1 Choices:** forks (fast-and-dangerous vs safe-and-long), optional side rooms, unlockable shortcuts back toward the
  entry. The walk check and the audit must hold for every branch.
- **2 Secrets:** hidden passages (a cracked wall the rift pick may break, a gap seen from a balcony), a lore note or a
  relic piece per secret, a set collected across runs (a scoreboard or advancement per piece).
- **3 Layout per slot:** each dungeon's 4 slots carry different variants (room order within rules, alternate rooms,
  mirrored or re-rolled shapes); entry gives a variant different from the player's last (DUNGEONS.md 13.1).
- **6 One set piece per dungeon:** mine = the floor collapsing behind you; ruin = water rising in a chamber; jungle =
  lights dying room by room (or the canopy closing). Function-driven, reset with the slot, audited for traps.

## Units (estimate, not measured; one wave then integration)
| Unit | Agent | Est. |
|---|---|---|
| KIT2: outlines, elevation, turns, multi-level, branches/forks, secrets' geometry, variants per slot | minecraft-systems-dev (opus: geometry that can trap) | 5M |
| PARKOUR2 + SETPIECES: parkour rework; the three set pieces | minecraft-systems-dev | 4M |
| LIFE: ambient Pokemon, dressing, sound/light per theme; puzzle text cut | datapack-content-dev | 3M |
| XAERO: research and the disable | cobblemon-researcher then main session | 0.6M |
| Re-author x3 (after KIT2): each dungeon to ~32 min required, shapes, forks, secrets, 4 variants | datapack-content-dev (opus) | 3 x 3M |
| AUDIT2: extend the independent audit to outlines, branches, variants, set pieces | test-author (opus) | 3M |
| Integration: merges, suites, prepare (~50 min), install, apply, playtest | main session (FRESH) | 2M |
| **Total** | | **about 27M** |

Order: KIT2, PARKOUR2+SETPIECES, LIFE and XAERO in parallel (KIT2 defines the interface the others read: they code to
the record contract it publishes first); then the three authors on KIT2's merge; then AUDIT2; then integration.

## State at the hand-off (2026-10-10)
- Branch `build/2026-10-09-dungeon-playtest`, head `1f747ce` (local commits not pushed since `d77fd0d`).
- Staging RUNNING for the owner (12G, watchdog 60000, terminal tab "staging server"), lock released. Installed from
  prepare `0d014a7` plus the shell-entities chain fix copied by hand (`1f747ce`): **a full prepare is owed** so build/ and
  the install match the tree.
- The owner is a band-1 playtester (`cobblers.dg_playtest`, `dg.ptband` 1) with sigils.
- Open owner calls: Giratina fight-only or catchable once; Wardenhold's beacon-room Froslass.

## Pass 3 (the owner, 2026-10-10, playing pass 2 on staging; approved about 16M)
- **The owner:** "The pathing and structure feels non-linear now and is great, I found 2 relics, but I see no diverging
  paths ... it didn't seem like I could go a different direction ... the optional paths didn't feel immense. And the
  parkour room should be longer, or just have more of them."
- **Read of pass 2:** the Night Shift's fork leaves the ore cavern by two near-identical doors on one wall and rejoins
  one room later; the side room is a single vault. Nothing signals a choice.
- **Plan:** (1) a CROSSROADS room kind with sightlines down each way and distinct-looking exits (lit gantry vs dark
  signed tunnel), 3-way splits, at least 2 forks per dungeon; (2) OPTIONAL WINGS of 2-4 rooms each with its own
  challenge and payoff (mini-boss, relic, richer vault or ore pile, maybe the legendary), never counted in the required
  ~32 minutes; (3) two parkour rooms per dungeon: a longer main one (5-6 sections) and a harder one guarding a wing;
  (4) re-author the three dungeons. Starts after GREED (value-weighted clock) and RESOURCES2 (band-scaled ore piles,
  mega stones, netherite) merge, so the records are not edited by two units at once.
- **Other owner decisions this day:** Froslass stays; Zarude and Regidrago stay optional; living-room Pokemon are
  catchable and every catch counts as a resource; every valuable mined anywhere (wall ore too) counts; points ~ 20 coal
  or 1 diamond = 1 point, 2 points = +0.1x clock; resource rooms are band-scaled piles. Open: Giratina fight-only or
  catchable once.
- **Server:** the owner is testing; do not stop staging without asking.
- **Playtest, pass 2 (the owner, 2026-10-10):** the Night Shift finished with about 15 minutes of the clock to spare,
  flying over the maze in creative, mining a few ores, with a level-100 Urshifu against band 1 (the playtest switch).
  The owner: "seems good". Not a timing measurement of a normal run (no maze walk, one-shot fights, little greed).
