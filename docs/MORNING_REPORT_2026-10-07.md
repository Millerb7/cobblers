# Morning report, 2026-10-07 (overnight brief #2)

Branch `build/2026-10-06-next` (local `wave1-2026-10-06`), head in `docs/HANDOVER_SESSION.md`. Staging world
`C:/Users/wnd/Documents/cobblers-staging/staging-2026-10-01`, snapshot before tonight's apply at
`cobblers-staging/snapshot-2026-10-07-before-apply` (10,420 files, 3.56 GB, byte-identical count). The full review
list is `docs/OVERNIGHT_REVIEW_2026-10-06.md` (N60-N94 are tonight's).

## Two things in the brief that are not so

- **"Hoopa now spawns after the Rift release."** The Hoopa you saw was the display Hoopa I spawned by hand at your
  request (uncatchable, which is why you could battle but not catch it). The real one is tonight's
  `cobblers_hoopa_cradle`: a level-60 Hoopa per player at (3357, 13, 3306), only the owner's ball holds. It is
  installed and self-driving, but **nobody has yet released the binder with it installed**, so it has not been
  seen to spawn.
- **"The fossil site is in."** It was not applied when you wrote that. It is now: see below.

## What is IN THE WORLD (staging), read back from the world

RESULTS_TABLE

## What was built tonight, by item

| # | Item | Built | Where it lives | Applied |
|---|---|---|---|---|
| 1 | Gym trainers inside the gyms | 21 juniors (gyms 1-4: 2, gyms 5-7: 3, gym 8: 4), type-themed, below the leader's ace, Normal and Challenge identities. Every seat proved must-pass and softlock-free against each gym's real geometry by the builder and by an independent audit (`tools/gym_trainers_audit.py`, 3 generator mutants red). The audit moved two seats: gym 7's Flue Keeper walled the only way to the leader; gym 3's was passable by half a cell | `data/gym_junior_trainers.json`, `docs/world-building/GYM_TRAINERS.md` | R17 |
| 2 | Unplaced legendaries | Giratina's Distortion shrine **sunk** in the Glacial Tear (4374, 66, 2862), altar (4397, 78, 2882); Darkrai's Newmoon Island **floating** over the Fungal Isle (24, 141, 5582), shrine (73, 187, 5615). Each gated by `champion_cleared` on its one-source item cache (Red Chain, Nightmare Weaver); found by eye (follow the Tear's river upstream; a black island in the western sky from Zapdos's tower). Hoopa catchable at the cradle (above). The Ruinous four **stay in the Nether** (their stakes are Nether worldgen; an overworld paste has none); Moltres had already moved | `docs/world-building/LEGENDARY_SWEEP.md` | donors placed tonight; Hoopa installed |
| 3 | Levelling without grinding | A training ground per gym town: one activated Habitat Block 70-130 blocks out, off the routes, keeping up to six high-EXP Pokemon at cap-3 to cap-1 of the cap you hold arriving. rctmod clamps EXP at the cap, so it reaches the next cap and never passes it | `data/training_grounds.json` (independent audit: 147 PASS) | R9E + R9TG |
| 4 | Minecraft grind earns Cobblemon things | CobbleDollars **cannot barter** (an offer is item, price, stock; read from the jar), so the shape is "sell the material to the Bank, buy the reward at a counter". The Nether tier in the Bank; exchange lines at Fossick and Northlight (netherite to a Master Ball is ~1.26 of leg 6's income). Independent audit: 0 arbitrage over 122 bank prices, 479 offers and 11,003 recipes | `docs/mechanics/MATERIAL_EXCHANGE.md`, `data/bank.json`, `tools/economy_audit.py` | bank at install; counters R17M |
| 5 | Hand-written situations | 119 situations across 20 settlements, each with a title and a story; composition audit PASS; five roof perches made legal (N89) | `data/ambient_towns/*.json` | R16C |
| 6 | Oak's intro and Challenge mode | Oak's lab as a scene (the five starters shown as uncatchable actors); `allowStarterOnJoin` false; Challenge offered by Oak in Codex's words, never "easy" or "hard": second spawners for every gym leader, the E4 and the Champion (independent audit: 56 checks, 0 problems after moving Misty's and Bruno's) | `data/scenes.json` oak_lab, `data/challenge_mode.json` | install + R17 |
| 7 | Nuzlocke zones, location titles | 72 zones (6 in Victory Road), each titled on entry | `data/nuzlocke_zones.json`, `cobblers_titles` | install |
| 8 | Discussed but unfinished | The Marts now scale with the gyms (tiered shelves); the ledger of everything else open | `docs/UNFINISHED_SWEEP_2026-10-06.md` | R17M |
| + | After gym 8: where to go | The Earth Badge pointed you back at the League; it now points at the Rift surveyor, with the direction told in the world | `docs/world-building/POST_GYM8_DIRECTION.md` | install + R17N |
| + | Elite Four rejection | **Proved offline** from the rctmod jar: every rctmod trainer refuses an over-cap player whatever spawned it, and the League's five are rctmod trainers (unlike the HQ fights, N57). One 5-minute in-game check remains (below) | `docs/UNFINISHED_SWEEP_2026-10-06.md` section 3 | n/a |
| + | The "11 items" | No document says 11; the list that reproduces it is 11 rows. **Four block something**: type gems (crafted TMs), Mewtwo's DNA grant (dead without the catalyst), Silvally/Primal Groudon/Hoopa Unbound items, and Porygon-Z's and Aromatisse's items | same file, section 4 | n/a |
| + | Earlier asks | Merchants as villagers with the shop UI only (Steves gone); the fossil dig at (4183, 5623); Victory Road's rosters at one starter final per zone; Elara re-seated | | R17M, R9FD + R17N, install, R18HQ |

## Waiting on you

Decisions (each is in the review list):

- **N8** a badgeless player can reach the finale.
- **N39 / N54** stone gating, and the per-player badge gates the merchant conversion dropped (a town's shelf can be
  bought before its gym).
- **N64** the base bank pays for AFK-farmable food (melon, kelp, crops, fishing loot, stew, cookies); keep or cut.
- **N74** Exp. Share, a catchable Audino/Blissey, candies.
- **N77** two leaders standing in every gym (Normal and Challenge spawners).
- **N71** the Windward Sea as one Nuzlocke zone or three; the creek as its own zone.
- **N82 (P1)** Misty's island floats ~20 blocks up; on foot the only way in is the well scaffolding.
- **N83** Giratina's cache is sealed under the dome's glass (break it, or open a way in).
- **N89** Stoneford holds 51 Pokemon against the cap of 48: which three go.
- **N67 / N93** Sunset West and Pacifidlog sell tier-7 shelves and are reachable at 0 and 6 badges.
- The 11 items: which of the four blockers to open (Mewtwo's catalyst is one reward edit).
- Kyogre Q1 and Q8; the summit loot; Waystone locations; the two rumour lines for Giratina and Darkrai.

In-game checks (staging, with coordinates):

- **Elite Four refusal**: a party member at 61 at Lorelei's room (expect the over-cap line, no battle), then 60.
- **Hoopa**: release the binder (HQ ring 0), stand at (3357, 13, 3306): your own Hoopa, level 60, only your ball holds.
- **Gym juniors**: walk gym 7 (6179, 120, 4991) and gym 3 (1732, 175, 1424); 12 juniors are passed beside or
  behind them (facing warnings, N87): does rctmod start the battle anyway?
- **Training grounds**: stand near gym 1's (1833, 139, 3618): Pokemon at 17-19 (cap 20).
- **Oak's lab** with a fresh account: the scene, the offer, Challenge mode's wording.
- **The exchange**: sell netherite at the Bank, buy at Fossick's and Northlight's counters.
- **Giratina** (4397, 78, 2882) and **Darkrai** (73, 187, 5615) with `champion_cleared`.

PROCESS_NOTES
