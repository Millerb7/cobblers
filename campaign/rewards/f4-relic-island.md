# F4 Relic Island reward

## Recommended final reward

- **Reward:** one level 5–7 Pichu per player, plus a weathered-cap lore item.
- **Availability:** immediately reachable; fully optional.
- **Claim:** once per player, independent of shared world progression.
- **Reason:** memorable and useful without invalidating early team building.
- **Dependencies:** EXP-006 static encounter proof and EXP-007 per-player state.

Do not implement the Pichu as an ordinary low-weight spawn. If per-player static
encounters cannot be made reliable, use the badge-delayed Light Ball alternative.

## Prototype cache

Until those systems are proven, the placement function fills a barrel from
`cobblers:chests/f4_relic_island_placeholder` with a Relic Coin Pouch, three
Poké Balls, and an empty map. This cache only proves placement and loot-table
resolution. It is repeatable when the prototype is rebuilt and is not the final
campaign reward.
