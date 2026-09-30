# For Codex: FACTION.md puts Hoopa's cradle outside the Rift

Raised 2026-09-30 by the Claude session that built the zone system. **`docs/story/FACTION.md` is
Codex's and has not been edited.**

FACTION.md sites Hoopa's cradle at **(3297, 2603)**. Measured against `data/regions.json`'s
`the_rift` polygons, that point is **outside the Rift extent** — 626 blocks north of the relic area,
on ground y118, which is rim height rather than floor. The build follows `data/rift_regions.json`
instead and puts the cradle **under the relic area**.

The owner settled it on 2026-09-30: **the cradle is at (3357, 3306)**, which is where
`data/rift_zones.json` now places it. Two further reasons that position is load-bearing:

- It sits in **Z2**, and only because the throat wall was moved to the excavation site's east edge.
  At the line `docs/mechanics/RIFT_ZONES.md` originally drew, the cradle fell in **Z1**, which opens
  at 2 badges — and that breaks RIFT_ZONES.md §2a, which is explicit that the cradle is late content.
- (3297, 2603) being outside the Rift means no zone can gate it at all.

**What Codex may want to change**, in its own file and its own time: FACTION.md's coordinate, and any
prose that reads the cradle's position against the rim rather than the relic area. Nothing in the
build depends on FACTION.md's number, so there is no rush and no breakage either way — but the two
documents disagree, and this note exists so the disagreement is recorded rather than discovered
twice.
