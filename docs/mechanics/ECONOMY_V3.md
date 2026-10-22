# Economy v3: price what the path pays

Status: DESIGN, 2026-10-22 (trainer-balance-designer). Nothing here is built or run. Written at HEAD `ef3dca11`
(read from the worktree's branch ref). The one data edit is a `proposal_v3` block in `data/training_services.json`;
no live field changed.

The owner, 2026-10-21: "the iv/ev system costing 17k feels bad early game ... so far no one is doing optional fights
just the gym trainers and leaders. which is what i expected and emphasized, so idk why the economy was balanced around
a different play style"; "players spent about 3 hours running through the first 2 gyms tonight, and i was the only
one to make it to gym 3" (about six players); on rebasing vs cutting: "a mix of both, maybe we just need more content
for battle areas"; service prices: RISES WITH BADGES; Challenge: "just give him money i dont care".

## 0. Premises checked

| Premise (relayed in the brief) | Verdict | Evidence |
|---|---|---|
| `income_basis.counts_trainers` counts Route N's trainers (optional included), the mansion's five, gym N's juniors and leader | TRUE | `data/markets.json:25` |
| `cumulative_by_badge` {1: 4033, 2: 8608, 3: 18576 ... 8: 202835} | TRUE | `data/markets.json:26`; re-summed by hand for leg 1 (0.28125 x 14,339 = 4,033) |
| The service price is above hours_saved x the leg-8 fight hour (~$17,126) | TRUE: 68,505 / 4 = 17,126 -> $17,200 | `data/training_services.json:21-23, 54, 126` |
| SERVICES_AND_CRAFTING says a badge-scaled price is "not built" | TRUE | `docs/mechanics/SERVICES_AND_CRAFTING.md:76-77` |
| "the iv/ev system costing 17k" | **PARTLY WRONG, and worse than it reads.** EV is $17,200 a Pokemon from badge 2. IV is $17,200 **a stat** ($103,200 for six) and is gated at **badge 8**: no player can buy any IV before the eighth badge | `data/training_services.json:54-56, 126-130` |
| Only one shop sells TMs: 10 lines at the mining town | TRUE. Fossick's ten (Brock's 4 at $4,100, Misty's 3 at $8,700, Surge's 3 at $18,600), off the path. The other 13 leader TMs are `held_stock` at Northlight ($35,000-$202,900), sold by nobody | `data/markets.json:355-365, 411-423` |
| Challenge pays cash per badge | TRUE (built, not installed) | `data/challenge_mode.json:147, 175-185` |

## 1. What is wrong

1. **The income model counts fights players skip.** `income_basis` is "Route N's trainers (optional ones included) ...
   each beaten once" (`data/markets.json:25`). Before the League, only 26 gym juniors, 10 Victory Road trainers, the 5 mansion guardians
   and 1 route trainer have eye contact (`"eye_contact": true` in `data/gym_junior_trainers.json`,
   `data/vr_trainers.json`, `data/mansion_guardians.json`; `data/route_trainers.json:23` is the only route one). Every
   other route trainer can be walked past, and the owner reports nobody fights them. What the path pays is 48-62% of
   the model at every badge (section 2).
2. **Every price that reads `cumulative_by_badge` is therefore pitched at a player who does not exist.** The TM
   income gate prices a TM above *everything the road pays by its badge* (`data/markets.json:75`): Thunderbolt
   $18,600 against $10,610 a path player has earned by badge 3. The curve's convenience band (0.65-0.70 of income,
   `data/markets.json:88-91`) prices shelves for the road's income.
3. **The fight allowance exceeds what the path pays.** The curve assumes $2,500 a leg of Mart, blackout and ferries
   (`data/markets.json:58-61`). A path player earns $1,932 in leg 1 and $2,468 in leg 2.
4. **The services are priced for the richest leg and gated late.** `anchor_badge: 8` (`data/training_services.json:22-23`)
   makes EV $17,200 at every badge and IV $17,200 a stat from badge 8 only. A path player first holds $17,200 between
   badges 3 ($10,610) and 4 ($19,229): exactly the owner's "gym 3-4 for a single mon". A team is six times that.
5. **Challenge players cannot buy TMs.** They do not craft (the owner's design, `data/challenge_mode.json:163`), and the
   only TM shop sells ten leader TMs from gyms 1-3 at one off-path counter (`data/markets.json:355-365`). The cash
   voucher gives money with nothing to spend it on for coverage.
6. **The tempo assumption is four hours a leg** (`data/bank.json:262`, ASSUMED). The owner's evening (relayed, one
   session, six players) is three hours for two gyms, about 1.5 h a leg, and slower for everyone but the owner.
7. **An unbounded repeatable income already exists and nobody has used it.** A placed trainer is never refused a
   rematch (`docs/STATE.md:92`) and "rematch money is unchanged" (`docs/STATE.md:301`): a beaten leader re-fought pays
   its battleVictory again (Misty about $1,378 a win). Not measured; this design does not depend on it (build unit V3-9).
8. **Stale input:** the curve's `produce_allowance` (`data/markets.json:63-66`) still counts a Produce Buyer allowance
   that E3 removed (`data/produce_buyer.json:6, 10`).

## 2. What the path pays

**Method.** For each leg, `income_basis.level_sums` (`data/markets.json:42-43`) lists every counted battle's level sum
in `tools/income_model.py` `legs()` order: route trainers by walked distance, then (leg 1) the mansion's five, then the
gym's juniors by trainer order, then the leader (`tools/income_model.py:152-157`). Junior counts are 3, 2, 3, 3, 3, 4, 4,
4 (`data/gym_junior_trainers.json:4`, confirmed by the 26 records). So the last 1 + juniors entries of each list are the
gym; I added Route 1's eye-contact trainer (sum 7). Expected credit per win is 0.28125 x S^2
(`data/markets.json:20`). Wild battles pay nothing (`modpack/config/cobbledollars/common.json:3`). First-win rewards
pay no money: badges, one TM, and for Giovanni a Master Ball (`data/progression.json:5114-5218`). Pick-ups: drops left
the bank (`data/bank.json:204-236`) except meat at $10 raw; I allow **$100 a leg, ASSUMED**, which changes no
conclusion and is not in the tables.

| Leg (to badge) | Gym path S (juniors; leader) | Path leg | Path cumulative | Road cumulative | Path / road | Path hour at 1.5 h a leg |
|---|---|---|---|---|---|---|
| 1 | 33, 35, 37; 56 (+ route 7) | 1,932 | 1,932 | 4,033 | 0.48 | 1,288 |
| 2 | 43, 45; 70 | 2,468 | 4,400 | 8,608 | 0.51 | 1,645 |
| 3 | 53, 55, 57; 114 | 6,210 | 10,610 | 18,576 | 0.57 | 4,140 |
| 4 | 63, 65, 65; 135 | 8,619 | 19,229 | 34,991 | 0.55 | 5,746 |
| 5 | 73, 75, 77; 195 | 15,443 | 34,672 | 56,424 | 0.61 | 10,295 |
| 6 | 83, 85, 87, 87; 217 | 21,471 | 56,143 | 90,132 | 0.62 | 14,314 |
| 7 | 93, 95, 97, 97; 242 | 26,735 | 82,878 | 134,330 | 0.62 | 17,823 |
| 8 | 103, 105, 105, 107; 319 | 41,026 | 123,904 | 202,835 | 0.61 | 27,351 |
| VR (holding 8) | ten, all eye contact | 49,341 | 173,245 | | | |

The 1.5 h column is the owner's one evening (legs 1-2, RELAYED); later legs are unmeasured and may be slower.
Challenge, same method on `level_sums.challenge`: path legs 6,085 / 8,328 / 14,194 / 19,597 / 26,789 / 38,870 /
48,244 / 58,363, cumulative 6,085 / 14,413 / 28,607 / 48,204 / 74,993 / 113,863 / 162,107 / 220,470 (0.65-0.70 of
Challenge's road), plus Oak's $4,000 and the voucher.

## 3. The fix

### 3.1 Two incomes, each for its job

Add `income_basis.path` (Normal and Challenge, the table above) beside the road figures; **change no road figure**.
- **Path** (the floor: what everyone has) prices what a player is meant to afford: services and TM shops.
- **Road** (the ceiling: the most a thorough player has) stays where it is a guard against buying too early or
  earning too fast: the bank's parity rule (`data/bank.json:267`), `early_reach_pricing` (`data/traders.json:587`),
  the Sachet and memory income gates.
Additive keeps every pinned road number (`tests/test_markets_audit.py:257-258`) and every consumer in section 5 that
only needs a ceiling. Whether the convenience curve moves to path is owner question Q4: land the battle content
(section 4) first, because it moves the path figure.

### 3.2 Training services: priced by tier, rising with badges

Rule (data: `data/training_services.json` `proposal_v3`): price = smallest multiple of $100 at or above
fraction x the path income of the leg the player is playing. Fractions: raise 0.05, EV spread 0.15, IV 0.025 a stat.
Tier t = badges held for the raise; for EV and IV t = max(badges held, the slot's level band), so a high Pokemon
traded to a low-badge friend is priced high (the co-op arbitrage a badge-only price opens).

| Tier (badges held) | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| Raise to cap (was $500) | 100 | 200 | 400 | 500 | 800 | 1,100 | 1,400 | 2,100 | 2,500 |
| EV spread (was $17,200, badge 2+) | closed | 400 | 1,000 | 1,300 | 2,400 | 3,300 | 4,100 | 6,200 | 7,500 |
| IV a stat (was $17,200, badge 8 only) | closed | 100 | 200 | 300 | 400 | 600 | 700 | 1,100 | 1,300 |
| IV all six | | 600 | 1,200 | 1,800 | 2,400 | 3,600 | 4,200 | 6,600 | 7,800 |
| **One Pokemon (EV + six IVs)** | | **1,000** | **2,200** | **3,100** | **4,800** | 6,900 | 8,300 | 12,800 | 15,300 |

Gates: EV and IV open at `gym1_cleared` (were gym 2 and gym 8). Raise unchanged (`max_cap` 62).

**Cash walk, a Normal path player, no optional fights** (Mart $800 a leg in legs 1-3 and $1,200 in 4-5, ASSUMED;
one TM a leg from leg 3 at 3.3's prices; packages: one at tier 1, one at tier 2, two at tier 3, two at tier 4):

| Leg | Start | + path | - Mart | - packages | - TM | End |
|---|---|---|---|---|---|---|
| 1 | 0 | 1,932 | 800 | | | 1,132 |
| 2 | 1,132 | 2,468 | 800 | 1,000 | | 1,800 |
| 3 | 1,800 | 6,210 | 800 | 2,200 | 2,200 | 2,810 |
| 4 | 2,810 | 8,619 | 1,200 | 6,200 | 3,100 | 929 |
| 5 | 929 | 15,443 | 1,200 | 9,600 | 5,500 | 72 |

One Pokemon by gym 2, a full team by badge 5 with nothing left over: real and reachable, as asked. Every unit of
section 4 content is slack on top. Purchases inside a leg need the leg's earlier fights first; the walk is per leg.
At today's prices the same plan is $103,200 of EV alone and no IVs before badge 8.

**What this supersedes, said plainly.** The owner's decision (4) after the 2026-10-10 overnight ("a service is the
convenience that costs more than the play it saves", `data/training_services.json:20`) is reversed for these three
services. EV power was always free by battle (training grounds, $1,500 power items), so the service sells time, not
power: a spread is about +36% on the non-flat part of each trained stat at every level ((EV/4) / (2B + IV) for a base
80 stat), and a diligent player already had it. Still true: the shelf (vitamins $3,500, mochi $800, `data/markets.json:388-393`,
`data/traders.json:640-645`) costs far more per spread than the service. Bosses carry no EVs
(`data/challenge_mode.json:163`); whether that should change is Q3.

### 3.3 TM shops for both modes

A merchant cannot gate per player (`docs/mechanics/MARKET_GATING.md:19-23`), so the gate is where the shelf stands plus
its price, as the Marts already do (`data/traders.json:582`).

- **Where:** tier t sells in gym (t+1)'s town, where a path player arrives holding t badges: tier 1 Viltri (gym 2's
  town), 2 Highwire, 3 Greenhollow, 4 Fenhide, 5 Tilpey Cross, 6 Cinderlee, 7 and 8 Holdfast. As lines on each
  town's existing counter (one category per counter, `data/markets.json:7`), strand `power`, off the curve.
- **Price (new `price_rule: "tm_tier"`):** the smallest multiple of $100 at or above 0.35 x the path leg played at
  that tier, floored at the bank value of the TM's crafting inputs plus $100 so crafting stays the cheap route
  (the floor is unmeasured: unit V3-3 computes it).

| Tier | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| A TM | 900 | 2,200 | 3,100 | 5,500 | 7,600 | 9,400 | 14,400 | 17,300 |
| was (income gate, road) | 4,100 | 8,700 | 18,600 | 35,000 held | 56,500 held | 90,200 held | 134,400 held | 202,900 held |

- **Stock:** the previous leader's whole first-win pool (the 23 leader lines, released from `held_stock`, Fossick's
  ten repriced in place) plus 3-6 answers to the next leader whose resolved `tools/tm_gate.py` badge is <= t. The
  line's `gate_badge` must equal that resolved badge: `tools/tm_gate.py:297-302` reads every shelf line's
  `gate_badge`, and the shelf wins over the power rule, so a wrong one moves a crafting gate. Candidates (power badge
  from `docs/mechanics/TM_POWER_GATE.json`; learnsets unchecked):
  - tier 1 vs Misty: Brock's four, Absorb (1);
  - tier 2 vs Surge: Misty's three, Dig (2), Charge Beam (2), Ember (2), Confusion (2), Metal Claw (2);
  - tier 3 vs Erika: Surge's three, Flame Charge, Aerial Ace, Wing Attack, Icy Wind, Bug Bite, Acid Spray (all 3);
  - tier 4 vs Koga: Erika's two, Psybeam, Bulldoze, Fire Fang, Bite (all 4);
  - tier 5 vs Sabrina: Koga's four, Crunch, Dark Pulse, Shadow Ball, X-Scissor (all 5);
  - tier 6 vs Blaine: Sabrina's three, Surf, Liquidation, Earth Power (6), Power Gem (5);
  - tier 7 vs Giovanni: Blaine's two, Ice Beam, Energy Ball (6);
  - tier 8 vs the League: Giovanni's pool (Fissure, Earthquake).
- **Early reach:** a walker who arrives ahead of the badges sees later tiers. A Normal path player can afford about
  one tier ahead; a Challenge player (6,085 by badge 1 plus Oak's 4,000) could buy tier-4 TMs holding one badge.
  Accepted under the owner's existing "a player who reaches a town early buys its shelf early" (`data/traders.json:582`);
  the TM power bands (`data/tm_gate.json:28-32`) bound what that buys. Q2 if not acceptable.
- **Co-op:** TMs are single use (`consumeMoveItemOnUse` true, `docs/HANDOVER_SESSION.md:39`), so giving one away is
  one use. Stock is unlimited (an Offer with no Stock, `data/bank.json:284`): never one per server.

### 3.4 Challenge cash: keep the schedule, change its reason

Keep `data/challenge_mode.json` `voucher.computed.schedule` as built (Oak 4,000; gyms 7,298 / 4,000 / 2,600 / 2,300 /
1,400 / 1,050 / 800 / 300; total $23,748). Reasons:
1. One live player was already paid gym 1 under it (`data/challenge_mode.json:147`); changing it splits Challenge
   players into two classes.
2. At 3.3's prices Challenge's own extra fight income buys the answer kits. Premium (Challenge path minus Normal path)
   by leg: 4,153 / 5,860 / 7,984 / 10,978 / 11,346 / 17,399 / 21,509 / 17,337 (+8,812 on Victory Road). A two-TM
   answer kit for the next leader: 1,800 / 4,400 / 6,200 / 11,000 / 15,200 / 18,800 / 28,800 / 34,600 (League).
   Carried forward, the premium covers every kit through gym 7 and falls $15,422 short by the League; the gyms'
   $19,748 covers that, and the rest pays about one tier-3/4 service package.
3. Front-loading stays the owner's shape (decision (2), `data/challenge_mode.json:148`).

What changes: the derivation. The material kits and the $9,000 power kit (`data/challenge_mode.json:152-163`) stop
being the basis (grants are cash; the EV service is now cheaper than the power kit). Freeze the schedule as the owner's
hand figure, and have `tools/challenge_voucher.py --check` assert the new invariant instead: at every gym arrival,
cumulative Challenge path income + Oak + grants >= cumulative answer-kit cost. Decouple Oak's bar ("below the
cheapest income_gate line", `data/challenge_mode.json:169`): with TMs off the income gate it would read the Sachet
($8,640) and silently double Oak's grant.

### 3.5 Mining: the income a player chooses

Today's typical hours (`data/bank.json:190-202`): early (opens leg 1) coal 60 x $4 + copper 40 x $2 + iron 30 x $8 +
lapis 15 x $4 = **$620**; deep (leg 3) adds gold 10 x $20, redstone 25 x $2, diamond 4 x $120 = **$1,350**; Nether
(badge 8) **$2,120**. Against the path hour (section 2) that is about half of fighting in legs 1-2 and a third in leg 3:
a real alternative for a player who likes it, never the plan. In v3 terms an early hour is 60% of a tier-1 package;
a deep hour is 43% of a tier-3 package or 44% of a tier-3 TM.

Tonight's tunnels raise ore exposed per hour, and `rate_per_hour` is ASSUMED everywhere. So: **time one hour in the
new tunnels first** (V3-8), then reprice inside parity. Parity is measured against the road (the ceiling), which leaves
headroom: early may rise to $1,008 an hour (4,033 / 4), deep to $2,492 (9,967 / 4). If timing finds rates at or below
today's, raise **iron 8 -> 10, coal 4 -> 5, raw gold 20 -> 30** (early $740, deep $1,570). **Do not touch the diamond
or the netherite ingot:** every exchange line is count x that price (`data/bank.json:285`), so they would move the
Metal Coat and the Master Ball lines with them. Mining is Normal-mode income; Challenge's design assumes none.

Also already in the game and unknown to most: a brewed vitamin sells for $2,500 (`data/bank.json:64-69`). That is the
largest farm income for a Normal player who gardens; the player guide should say so (V3-7).

## 4. More content for battle areas

Each pays CobbleDollars by battleVictory (0.28125 x S^2) unless said. "Normal" figures are per player.

| # | Proposal | Where | Reward | Repeatable | Build size | Who |
|---|---|---|---|---|---|---|
| B1 | **Gatekeepers**: move each route's strongest optional trainer onto a chokepoint of the walked line with eye contact | Routes 1-8, existing records | its existing purse: +648 / 1,116 / 1,711 / 2,592 / 3,101 / 4,465 / 5,592 / 6,845 by leg (S 48, 63, 78, 96, 105, 126, 141, 156), +17-45% on the path leg | no | small: re-seat 8, prove 8 sightlines | world-content-dev (seats), datapack-content-dev |
| B2 | **First-win prizes on optional trainers**: the two strongest optional trainers per route carry a named prize given once per player (a tier TM from 3.3, a type-boost held item, a Bottle Cap from route 6 on), said in their intro line | Routes 1-8 | purse + the item | no | small-medium: a give on the per-player defeat tag `tools/route_trainers.py` already mirrors (`docs/STATE.md:93`) | trainer-balance-designer (prize table), datapack-content-dev |
| B3 | **Sparring partners**: two one-Pokemon trainers per training ground, rematchable on a 5-minute trainer cooldown; species picked for EV yield so sparring is the paid EV route | beside each of the 8 grounds (keepers already seated, `data/training_services.json` `keepers`) | partner level 12 / 14 / 22 / 25 / 34 / 40 / 45 / 55 at tiers 0-7: $40 / 55 / 136 / 176 / 325 / 450 / 570 / 851 a win; at most 24 wins an hour between the two, about 0.75 of the path hour | yes | medium: 16 records, 8 seats, a long `battleCooldownTicks` (ASSUMED per trainer) | trainer-balance-designer (teams), datapack-content-dev, world-content-dev |
| B4 | **Mine crews**: miners and hikers at tunnel junctions in tonight's tunnels (about one per 150-200 blocks), eye contact, and a Shift Boss per mine with a once-per-player prize (4 diamonds or a tier TM) | the new ore tunnels | crew purses at the tier the mine opens; fighting and mining in one trip | no (crews); ore renews | medium: needs the tunnel geometry from tonight's agents | world-content-dev, trainer-balance-designer |
| B5 | **Ambient trainers, measured then tuned**: rctmod's natural spawns are on with Oak's card (`modpack/config/rctmod-server.toml:6, 87`) and are unmodelled (`docs/mechanics/ECONOMY_V2.md:346`, U4/E12). Time an hour with the card on Routes 1-2, then tune spawn chance and interval | everywhere a card-holder walks | upstream teams at the player's level | yes, uncapped | small: configuration (rung 4) and one timed hour | minecraft-systems-dev (measure), owner (in game) |
| B6 | **Early arena bands**: extend `data/arena_fights.json` (DRAFT, post-badge-8 only) down to caps 25-45 with the arena's own purse | Heaven's Arena when it is built | the arena purse, taken from the battleVictory and paid capped | yes, capped | large: waits on the arena's per-player mechanism | content-architect, then builders |

B1 is the largest lever for the least work and is what "players really dont have to do many fights" asks for, but it
changes pacing: one gatekeeper a route, not two (Q1). B3 is the only repeatable that is cheap to build; its cooldown is
per trainer, so six players share 24 wins an hour, and its pay-per-hour rests on ASSUMED fight lengths: measure before
raising it. Grinding XP stays useless under the caps; grinding money is bounded by the cooldown.

## 5. Every consumer of `income_basis`, and what pins today's numbers

Additive design (3.1): road consumers keep working unchanged. Consumers found by grep for `income_basis` and
`cumulative_by_badge` / `leg_by_badge`:

| Consumer | Reads | Change needed |
|---|---|---|
| `tools/income_model.py` | writes the block | emit `path` (rows are already tagged route/mansion/junior/leader, `:152-157`; add eye contact) |
| `tools/training_services.py:439-447` | `leg_by_badge[anchor]` for the price rule | the tier rule from `proposal_v3`; per-tier dialogue options and charge |
| `tools/markets.py:548-589, 1028-1053, 1764` | income gate, curve | new `tm_tier` rule on `path`; income gate stays for Sachet and memory |
| `tools/markets_audit.py:227-244` | re-sums road from level sums | also re-sum `path` |
| `tools/town_squares_audit.py:87-95, 1177-1187, 1246-1320` | power lines must carry a known price rule | accept `tm_tier` |
| `tools/tm_gate.py:297-302` | every shelf line's `gate_badge` | none, if new lines carry the resolved badge (3.3) |
| `tools/challenge_voucher.py:25, 94-95` | Challenge legs; Oak's bar from the cheapest income-gate line | frozen schedule plus the kit invariant (3.4) |
| `tools/player_guide_tms.py:188, 259`; `tools/player_guide_items.py:15, 308, 353-356` | cumulative for the guide | show path and the tier tables |
| `tools/economy_sim.py:9, 163, 975` | level sums | add a path-player profile |
| `tools/bank.py:485-528`; `tools/economy_audit.py:35, 106, 925-1086, 2591-2593`; `tools/traders.py:226-277, 665` | road as a ceiling | none |
| `tools/apricorn_farm_audit.py:1371`; `tools/new_places_land_audit.py:1084`; `data/route4_events.json`, `data/stage_loot.json` | road, to size rewards | none (rewards look generous to a path player: fine) |

Tests that pin today's numbers and must change with the build: `tests/test_services_voucher_audit.py:86-109` ($17,200
from the leg-8 hour), `:156-202` (no craft route dearer than the service: **fails by design** under v3, rewrite as
the shelf ordering only), `:222` (Oak's bar), `:269-316` ($23,748 and the voucher's shape: keep the totals, change the
derivation); `tests/test_markets_audit.py`, `tests/test_town_squares_audit.py`, `tests/test_material_exchange.py`,
`tests/test_player_guide_items.py`, `tests/test_economy_sim.py`, `tests/test_economy_audit.py`,
`tests/test_town_traders_build.py`, `tests/test_route5_events.py` read the block and are re-run. Unchanged by design:
`tests/test_markets_audit.py:257-258` (4,033 and 14,339).

## 6. Build list for the morning

| Unit | What | Who | Size |
|---|---|---|---|
| V3-0 | `income_model.py` emits `income_basis.path` (Normal, Challenge, VR); `markets_audit` re-sums it; must reproduce section 2 | datapack-content-dev; audit by test-author | small |
| V3-1 | Services: tier rule from `proposal_v3` into the live fields, per-tier dialogue options, tier read (badge probe + slot level) and charge; gates gym 1; rewrite the price-rule tests | minecraft-systems-dev (functions); tests by test-author | medium |
| V3-2 | Staging proof of V3-1: buy EV and IV at tiers 1 and 3, a traded high-level slot at tier 1, a short balance | owner + main session (EXP-062 S1-S5 first) | in game |
| V3-3 | TM shops: `tm_tier` rule, lines at seven counters, release the 13 held lines, reprice Fossick's ten, crafting-input floor, `gate_badge` from `tm_gate` resolved | datapack-content-dev; stock lists checked by trainer-balance-designer | medium |
| V3-4 | Challenge voucher: freeze schedule, kit invariant, decouple Oak's bar; tests | datapack-content-dev; test-author | small |
| V3-5 | B1 gatekeepers (one a route) | world-content-dev, datapack-content-dev | small |
| V3-6 | B3 sparring partners, then B2 first-win prizes | trainer-balance-designer (teams, prizes), datapack-content-dev, world-content-dev | medium each |
| V3-7 | Player guide: path income, tier tables, vitamins sell for $2,500 | datapack-content-dev | small |
| V3-8 | Time an hour in tonight's tunnels and an hour with ambient trainers (B5); then bank prices per 3.5 | owner in game; main session records | in game |
| V3-9 | Measure and decide the leader rematch payout (section 1 item 7) | main session, staging | small |
| later | B4 mine crews (after the tunnels land); B6 arena bands; whether the curve moves to `path` (Q4) | as listed | |

## 7. Questions for the owner

- **Q1.** Gatekeepers: one per route (recommended), two, or none?
- **Q2.** A walker who reaches a later town buys its TMs early (Challenge players can afford about three tiers ahead).
  Accept, as for the Marts, or hold tiers 5-8 behind the counter of the gym town itself only?
- **Q3.** With EVs and IVs now cheap for players, should leaders and the Elite Four carry EV spreads?
- **Q4.** Move the convenience curve to the path income after B1 and B3 land, or leave shelves priced for the road?
- **Q5.** The raise falls from $500 to $100-500 for badges 0-3 and rises after. Keep your flat $500 until badge 3?

## Assumptions and research status

- Payout 0.28125 x S^2 a win: `data/markets.json:20`, the jar's formula VERIFIED, the uniform draw ASSUMED; never read
  back in game against our rosters (`data/markets.json:22-23`).
- 1.5 h a leg: RELAYED from the owner's one evening; later legs unmeasured.
- Mart $800-1,200 a leg; $100 a leg of pick-ups; 15-24 sparring wins an hour: ASSUMED.
- Per-player dialogue option visibility and the charge macro: VERIFIED (`docs/mechanics/MARKET_GATING.md:24-37`).
  Combining a badge probe with a slot-level read in one service: not run.
- `battleCooldownTicks` as a per-trainer cooldown after any battle: ASSUMED (upstream mob field,
  `data/challenge_mode.json:35`), an experiment.
- EVs awarded in NPC trainer battles (B3 as an EV route): ASSUMED, an experiment.
- TM learnsets for every candidate in 3.3: not checked.
- Crafting-input bank value per TM (3.3's floor): not measured.
