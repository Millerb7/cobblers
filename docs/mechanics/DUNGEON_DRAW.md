# The dungeon draw: progression decides, the rip does not

Status: **APPROVED by the owner 2026-10-13 ("ok yeah finish dungeon work, find spawn locations and do everything else
planned for them"), taking the recommended answer to D1-D5; BUILT 2026-10-13, NOT RUN IN GAME. Sections 1-4 are the design
as approved (section 1 describes the engine before the build); section 5 is what was built, measured, and what is deferred.**
The owner's rule (STATE, "Dungeons, the owner 2026-10-11"): dungeons are NOT tied to biomes, any rip may open
onto any dungeon, and PROGRESSION gates which dungeons are drawn, their rosters, levels and prizes.

## 1. What the engine does today (read from the code, 2026-10-11)

- **A rip is one dungeon.** Every record in `data/dungeons.json` carries its own `rip` (frame, click, outside), and
  `tools/dungeon.py` writes one `door_click` per dungeon. Thirteen dungeons, thirteen test rips on the old mine's trail
  (x1350-1677, z~4118).
- **The band is already progression.** At the click the band is frozen from the player's RCT level cap: the first
  `engine.bands` entry whose highest cap is at or above it (band 1 caps 20/25, 2: 30/35, 3: 40/45, 4: 50/55,
  5: 60/62, 6: 100). The playtest tag `cobblers.dg_playtest` with `dg.ptband` overrides this on staging only.
- **The sigil is the price, not the decider.** `engine.sigils.accept` is `own_or_higher`: the entrant's own band's
  sigil, else the lowest higher one. A lower band's sigil is refused.
- **Slots are per player.** `engine.slots.per_dungeon` is 4 and `members_max` is 1, so every entrant gets their own
  instance with their own frozen band and clock. The data carries a member index, so co-op is a switch.
- **The lockout is per dungeon per player**: one hour of uptime from the threshold.
- **Gates exist only as proposals.** Every built record has `gate_flag` null (test dungeons). The roster
  (`data/dungeon_prize_roster.json`) proposes `first_band` and a gate for each.

## 2. The proposal

### 2.1 What decides the band: progression (recommended)

Keep the band from the RCT level cap, as built. The sigil stays the price of entry at that band (a crafted cost per
band, netherite only from badge 8). It never chooses the band. A sigil-decided band would let a player buy an early
band-5 run with a lent sigil. It would also make "a dungeon with band 4-5 prizes is never drawn early" depend on an
item rather than on the player's progress.

### 2.2 Which dungeons each band can draw

A dungeon is in the draw at band B when its `first_band` is B or lower (and its gate flag, if any, is held). From the
roster's `first_band` as it stands today (the Zero Dig cut; the Cistern and Temple Calendar are not built):

| Band (caps) | Drawn from | Count |
|---|---|---|
| 1-3 (20-45) | Night Shift, Jungle, Flooded Ruin, the Street, the Patriarch | 5 |
| 4 (50-55) | the above + Field of Swords | 6 |
| 5 (60-62) | the above + Ash Bell, Moth Cathedral, Warped Lab, Soul Ossuary, Starfall | 11 |
| 6 (Champion) | the above + Crucible, Dragonspiral | 13 |

Every dungeon a band draws has a roster for that band, because the engine builds every dungeon at all six bands.
Early dungeons scale up: a band-5 player can still draw the Night Shift, at band 5, with its band-5 pools. A late
dungeon is never drawn early. Its first band is its floor. No early pool is invented for it.

**The gap this shows:** bands 1-3 draw from five dungeons, and the Jungle and the Flooded Ruin are test builds that
still have to be judged in play. If the owner wants more early variety, it comes from lowering a late dungeon's floor
and giving it a real early roster. That is authoring, so it waits on the owner's play.

### 2.3 The draw at a rip

At the click, after the existing checks (gate, lockout, not in a run, no elytra, party within the cap) and before
the sigil:

1. Compute the band, as today.
2. The candidates are the dungeons eligible at that band, minus any the player is locked out of, minus any with no
   free slot.
3. **Pick the candidate the player has least recently entered; break ties at random** (`random value` into a score).
   Recommended over a pure random draw, so a player sees the whole band before a repeat. It never gives the same
   dungeon twice in a row while another is free.
4. Show the drawn dungeon's name in the refusal-style line before the threshold. The player can still back out for
   the full refund (the back rip, as built), but **the back-out does not re-roll**. The next click at any rip draws
   again, but the backed-out dungeon counts as entered. A free re-roll would make the draw a menu.

The draw needs a per-player "last entered" stamp per dungeon. One score per dungeon (13 objectives) is enough, read
from the uptime counter the lockout already uses.

### 2.4 Rotation per band

There is no separate global rotation. Each player's least-recent pick rotates them through their band. The pool
rotation already built inside a dungeon (PRIZE-POOLS: boss crews, trainer pool teams, rare and legendary pools) stays
as it is. Keep the two levels apart: the draw picks the place, and the dungeon's own pools pick what is in it.

### 2.5 Two players at one rip

Each player who clicks gets their own draw, their own band and their own slot, as today. Two friends at one rip can
land in different dungeons at different bands. That is honest solo play, and it is what the engine supports. **When
co-op is switched on** (members_max 2), the proposal is a party draw: the band is that of the party's HIGHER-capped
member, both must hold the gate, both must be outside their lockouts, and one draw covers the party. That is a later
unit, and EXP-034's second account is needed to test it.

### 2.6 Where rips go

Rips stop belonging to dungeons, so they move out of the dungeon records into a list of their own (proposed
`data/dungeon_rips.json`: frame, click, outside, ground source; no dungeon id). Siting rules:

- On ground from `tools/ground.py`, dry, off the critical path's corridor, and 30 or more blocks from any `data/`
  coordinate (the test rips' own rule).
- Roughly one per region or major landmark, so a rip is a find, not a queue. The Nether's rips are included. They
  can only be reached after badge 8, so in practice they draw band 5 or higher.
- No rip inside a spawn-free town precinct. Rips are wild places.
- The 13 test rips on the old mine's trail stay until the owner has played. After that, each one becomes either a
  general rip or nothing.

## 3. What changes in the code when approved (not started)

- `data/dungeons.json`: `rip` leaves each record for `data/dungeon_rips.json`. Each record takes `first_band` and a
  `gate_flag` from the roster, which settles the roster's prose `rip`/`theme` overlap in `data/id_authorship.json`.
- `tools/dungeon.py`: one `door_click` per RIP. The draw function (candidates, least-recent, tie-break) runs before
  the sigil. It works by score arithmetic and function macros, with one chain per click and nothing in the keeper.
- The independent audit gains the draw: every band has at least one candidate, no dungeon is drawn below its first
  band, a full dungeon falls through to the next candidate, and a locked-out one is skipped.
- R16DR moves to rips-from-the-list. The test rips' `restore` data carries over for the removal.

Rough size: one builder unit on the engine plus one independent audit unit, about 4M each by the measured builder
cost. To run only after the owner has played three dungeons and approved this.

## 4. Questions for the owner

1. **D1. Band by progression, sigil as price.** Confirm (recommended), or should a higher sigil let a player enter a
   higher band than their cap?
2. **D2. Least-recent with a random tie-break, no re-roll.** Or a pure random draw, or a free re-roll?
3. **D3. The early pool is five dungeons** (two of them test builds). Is that enough for bands 1-3, or should a late
   dungeon get a real early roster after you have played?
4. **D4. Co-op later as a party draw at the higher cap.** Or the lower cap, which is safer for the weaker player?
5. **D5. Rip density.** About one per region (21 regions), or fewer and rarer?

## 5. Built (2026-10-13, by the DRAW builder; NOT RUN IN GAME)

The owner took the recommended answer to D1-D5. Rung: datapack and functions (CLAUDE.md principle 6); every lower rung was
exhausted by the existing engine, which is already a function pack. No mod, script layer or companion.

**Files.** `data/dungeon_rips.json` (new: the rips, places and no dungeon id), `tools/dungeon_rips.py` (new: the siting
rules, `find`, `record`, `check`, `probes`), `tools/dungeon.py` (the rip leaves the dungeon record; `door/rip_<name>` per
rip; `draw`, `draw/open`; `dg.rip`, `dg.ptdun`, `dg.dr_<short>`; `m/out` leads to the rip the run was entered by; R16DR places
the rips from the list), `data/dungeons.json` (`first_band` and `gate_flag` per record from the roster; `engine.draw`),
`data/id_authorship.json` (the roster/record `rip` overlap entry removed: the record no longer carries a rip; the `theme`
entry stays, two forms of one thing), `data/world_probes.json` (`dungeon_rips`, 90 probes, generated), the independent audit's
rip block and `tools/poi_heatmap.py` (read the new file), the players' guide (`tools/player_guide_dungeons.py`, regenerated).

**The draw** (docs/mechanics sections 2.2-2.4 as built): the band from the RCT cap (`m/band`); a dungeon is a candidate when
its `first_band` is at or under the band, its `gate_flag` is held, it is not locked out and it has a free slot; the
candidate the player drew least recently wins (never drawn is oldest), a random number breaks a tie, and the drawn
dungeon's own door runs unchanged, so its checks and then the sigil still come last and a refusal takes nothing. The stamp
(`dg.dr_<short>`) is taken at the go: a refused click is not a draw, a back-out is (no re-roll). When nothing is fully open
(all locked out or full) the same rule runs over band and gate alone, so the drawn dungeon's own door refuses with its
lockout or busy message. Scoreboard arithmetic only: no macro (the tie-break is `random value 0..2^30-1` taken mod the count,
so there is no storage to write), one chain per click, nothing in the keeper.

**Gates** (roster `gate`, as `cobblers:flag/<id>`, the advancements `tools/progression_pack.py` emits): ash_bell,
soul_ossuary, moth_cathedral, warped_lab, starfall `gym8_cleared`; field_of_swords `gym6_cleared`; crucible, dragonspiral
`champion_cleared`. The roster's gym6 and champion gates are marked "proposed" there; they are built as written, change the
record's `gate_flag` to change them. First bands: 1 for night_shift, jungle, flooded_ruin, street, patriarch; 4
field_of_swords; 5 ash_bell, soul_ossuary, moth_cathedral, warped_lab, starfall; 6 crucible, dragonspiral.

**Staging playtest.** The playtest tag now also bypasses a gate, and `dg.ptdun <1..13>` names the dungeon the tag's holder is
drawn (the draw would otherwise make a single dungeon unreachable on demand). Never set for a player.

**Deferred.**
- **D3** (nothing to defer, one finding): every band 1-3 has five candidates (night_shift, jungle, flooded_ruin, street,
  patriarch), each with rare pools at bands 1-3 in the roster. Only the Night Shift is not a `test` build.
- **D4, the party draw (section 2.5).** Section 2.5 asks for nothing now: each clicker draws alone from their own cap, lockouts
  and stamps, which is what is built. The party draw (the higher cap's band, both gates, both outside their lockouts, one draw
  covering the party) waits for `members_max` 2 and EXP-034's second account.
- **Nether rips (D5 "the Nether included").** NOT sited. The Nether has no heightmap and its biomes are the seed's, so a
  site cannot come from `tools/ground.py`; the engine places rips in the overworld only (`docs/research/notes/nether-rip-siting.md`
  sections 1-3: it needs the oracle world NS1 and a `dimension` on the rip). The Nether dungeons are drawn from overworld rips
  at band 5 and above, behind `gym8_cleared`.
- **`rip.under`** (the original surface under each scorched patch) is not recorded for any rip, so `rip_close_lines` still
  fails closed; nothing closes a rip yet.
- **Jungle Isle** has no rip: every column of its region is at or under y61 against sea level y62 (the water shape removed the
  isle). Pallet Fields and Shrew Lakes hold the 13 test rips on the old mine's trail and got no second one.

**Rips.** 31 in all: the 13 test rips (kind `test_trail`) at the positions the owner played, kept with their themed ground
(`rip_trail_<short>`; their tags, `rips/blocks_<short>` functions and probes are the ones the world already has), and 18 new
region rips (`kind` `region`, `rip_<region>`), one in each of the 18 other regions with dry ground. Each region rip stands
on a flat 9 x 7 window (`round(ground)` the same over all 63 columns), dry (sea and every lake basin), 30 or more blocks
from every coordinate in `data/` (the nearest is 150 or more away), 60 or more from the road, outside every spawn-free zone
and town footprint, inside its region, 300 or more from the other region rips. Checked by `python tools/dungeon_rips.py check`
and `tests/test_dungeon_rips.py`; the numbers are in each record's `ground` and `siting`.

**Tests run on the build (simulator and static only; the builder's, not the independent audit of the draw).**
`tests/test_dungeon_draw.py` 16 passed and `tests/test_dungeon_rips.py` 13 passed (new); `tests/test_dungeon.py` 26 of 26 (in three runs, the last two re-running what each fix touched)
(the `reapply_steps` count now reads the rips); the per-dungeon files `test_dungeon_{ash_bell,crucible,dragonspiral,
field_of_swords,flooded_ruin,jungle,moth_cathedral,patriarch,soul_ossuary,starfall,street,warped_lab}.py` plus
`test_dungeon_guide.py`, `test_rip_pack.py`, `test_player_guide_dungeons.py`, `test_id_authorship.py` all pass (the per-dungeon
rip tests now read the dungeon's test rip from `data/dungeon_rips.json`; their gate assertions are the roster's);
`tests/test_dungeon_independent_audit.py` 42 passed; `tests/test_dungeon_audit.py` 56 passed with the 2,135 per-spawn-site
parametrisations deselected, of which four ash_bell `lure` cases fail on the commit before this work too (6249332e: the bait
rework's tier lines no longer match the test's regex); `tests/test_dungeon_kit3.py` 41 passed and one failing, also before this
work (a vault budget figure in DUNGEON_ROOMS.md); `tests/test_system_contracts.py -k dungeon` 7 passed; `tests/test_pack_split.py` (the R16DR placement stays build-only) passed, and the first 920 of the other 17 dungeon test files' 995 cases passed bar the kit3 one above (that run was stopped in `test_dungeon_resources.py`; `vault_one_of` and `setpieces` were partly run). Not run: the rest of
`tests/test_dungeon_audit.py`, `test_dungeon_rooms.py`, `test_dungeon_sim.py` (thousands of cases, hours).

**To prove on staging (not run; an experiment for whoever grades it).** After `prepare`, `install` and R16DR/R16DG: (1)
`python tools/presence_audit.py --only extra` reads the `dungeon_rips` place (90 probes) and `dungeon_night_shift` present, so
all 31 rips stand; (2) a player with a sigil clicks `rip_the_rift` at band 1: a dungeon of the five opens, the chat names it,
`scoreboard players get <player> dg.rip` is 21 and the back rip leaves at the Rift's point, not the old mine's; (3) five
back-outs in a row at band 1 show five different dungeons; (4) a player holding `cobblers:flag/gym8_cleared` at a band-5
cap sees the Nether dungeons enter the draw and one without it does not; (5) `tag <player> add cobblers.dg_playtest`,
`scoreboard players set <player> dg.ptdun 12` draws the Street; (6) the first click of a fresh player after a restart
(`random value` in a function parsed at boot, which the simulator models and a server may not). Reading `/tick query` around
the first click gives the chain's cost.

**Band 5-6 tuning (measured with `tools/dungeon_sim.py` and `tools/dungeon_clock.py`, 2026-10-13).** No clock was changed, because
none is short. Authored clocks against the clock the sim re-derives from its own fight pace (ratio, authored over implied):
band 5, 1.76 to 2.14 (crucible lowest); band 6, 1.77 to 2.12 (crucible lowest). Against the planning pace
(`tools/dungeon_clock.py`) the slack above the required walk, fights and fixed costs is 641 to 779 s at band 5 and 671 to 809 s
at band 6. The nine bank vaults cost 50 to 52 s of it at both bands (the vault room is a 14 to 16 s side trip, the keypad 36 s,
and the clue rooms are on the main route), 6 to 8 per cent of the slack, so the code is findable in the time. What the sim
does show is difficulty: the typical-team win rate at band 5 runs from 0 to 54 per cent (the two caps of a band, lowest to highest cell) and at band 6
from 0 to 35, eight of the thirteen dungeons at 2 or under at band 6 (the Night Shift, Ash Bell, Moth Cathedral, Dragonspiral,
Field of Swords and the Street at 0), with the held items, switching and status play it cannot model left out. For comparison band 4 runs 52 to 77 at the lower cap (the 60-90 target
of BOSS2). That is a team and level question for the balance designer, not a clock one, and nothing was edited for it. One
measured sensitivity, so the next pass need not repeat it: with every stand and gauntlet trainer at band 5 dropped four more
levels (cap-6 to cap-3 instead of cap-2 to cap-1; the sim run with `engine.stands.low_offset` 6, `high_offset` 3 patched in
memory, no file edited) the typical win at the lower cap goes from a mean of 16 per cent over the thirteen dungeons to 27,
and nine of the thirteen are still under 35. A global level drop does not reach the target; the fix is per dungeon (the
named fights in `derived/dungeon_sim/report.md`, which `python tools/dungeon_sim.py --advise` lists).
