# The dungeon draw: progression decides, the rip does not

Status: **DESIGN ONLY, for the owner (2026-10-11).** Nothing in the rip or draw logic changes until the owner approves
this. The owner's rule (STATE, "Dungeons, the owner 2026-10-11"): dungeons are NOT tied to biomes, any rip may open
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
