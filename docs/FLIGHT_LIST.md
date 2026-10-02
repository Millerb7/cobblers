# Flight list

**Most important first, with coordinates and what to look at.** Written 2026-10-01.

> **Read this before flying anything.** After the staging deletion, **almost everything below has never
> been seen in a world by anyone** — it exists as authored data and generated packs only
> (`docs/STATE.md`'s opening banner). So the ordering is not "what is most interesting"; it is **what has
> the most riding on an unverified assumption**. The first three items can each invalidate a whole
> subsystem in one glance.
>
> Fly the staging world, never `cobblers-10240`.

## 1. Hoopa — one glance, and the Deep's relic area depends on it

**`/pokespawn hoopa`, anywhere flat. Then look at it.**

Measured tonight in a running game: the species **exists** in Cobblemon 1.8.0 and spawns as
`cobblemon:hoopa`. What RCON cannot tell us is whether it **renders** — a client model is a client fact.
Community sources (ASSUMED) say Hoopa has no model yet and appears as a placeholder.

`docs/world-building/DEEP_CITY.md`'s entire relic area — the cradle, the containment deck, the anchor
pylons, the finale's release — is built on a player seeing Hoopa. **If it is a placeholder, unit 2's
premise is wrong and the relic area needs re-thinking before it is built.** No Prison Bottle item or
form-change mechanism was found in any Cobblemon source, so also try `/pokespawn hoopa unbound` and see
whether the aspect does anything.

## 2. Does any seated trainer actually fight you?

**Victory Road's ten, in order up the climb:**

| # | Seat | # | Seat |
|---|---|---|---|
| 1 | (3563, 2, 3009) | 6 | (3607, 31, 2766) |
| 2 | (3597, 8, 2985) | 7 | (3621, 42, 2716) |
| 3 | (3604, 17, 2928) | 8 | (3642, 48, 2673) |
| 4 | (3620, 19, 2880) | 9 | (3641, 55, 2614) |
| 5 | (3616, 25, 2822) | 10 | (3655, 65, 2564) |

Stand 1 is 55 blocks inside the mouth; stand 10 is 2.4 blocks from the exit ravine's foot. **What to
look for:** does each one stand on its block (not in it, not floating); does the one with eye contact
start a battle on sight and at roughly its stated distance; and **does the tenth greet you as the League
Examiner or the Gate Warden** — that is decision B1 and the answer is whichever name appears.

Then **Brock**: fight him, win, and talk to him again. *Does he refuse a rematch?* Long-standing and
still unproven — installed is not working.

## 3. The five gym interiors, and Sabrina's and Giovanni's

All seven were written and audited clean on 2026-09-30 and **none has been seen in a world**.

| Gym | Building | Lot | Level |
|---|---|---|---|
| 1 | The Stoneworks Hall | x1806–1845, z3656–3703 | y141 |
| 3 | The Relay Works (cut into a hillside) | x1722–1752, z1388–1432 | y174 |
| 4 | The Great Glasshouse (flattest lot) | x4288–4332, z1470–1512 | y110 |
| 5 | The Reed House (most confined lot) | x4574–4606, z2463–2495 | y116 |
| 6 | **The Hall of Lenses** (Sabrina) | x6180–6212, z3302–3334 | y97 |
| 7 | The Assay House | x6154–6186, z4980–5010 | y106 |
| 8 | **The Gate of the South** (Giovanni) | x3556–3588, z6400–6432 | y112 |

**Gym 6 is the one to look at hardest.** Its build gate — *not built until EXP-034 has run* — was
answered on the grounds that the Hall of Lenses carries **no per-player state**, and **EXP-034 is still
unrun**. So the reasoning, not the experiment, is what let it through. If the Hall turns out to need
per-player state in play, that gate was answered wrongly.

Also check, at each: the donor shell is **gone** (`tools/gym_demolish.py`, step R16F) and the new
building stands in its place; the leader's spawner moved into the new building; and **Misty's gym 2 is a
carved interior nothing may touch** — confirm it was not touched.

## 4. The Mega dens in the open — brand new, never seen

Seven dens, four `outer` (level 60) and three `deeper` (67). **The owner's own test is in the brief:
"a player should see them before they reach them."** So approach each from a distance and ask whether you
see the Mega *before* you arrive.

| Tier | Den | Anchor | Species |
|---|---|---|---|
| outer | east arm shoulder | (4528, 123, 4416) | Aggron |
| outer | east arm bench | (4576, 122, 4680) | Pinsir |
| outer | east arm head | (4608, 133, 4944) | Manectric |
| outer | east arm tail | (4488, 145, 5216) | Houndoom |
| deeper | west arm crest | (3944, 147, 3904) | Abomasnow |
| deeper | west arm shelf | (4080, 149, 4168) | Tyranitar |
| deeper | west arm tail | (4248, 129, 5328) | Garchomp |

**Three things to judge.** (a) Does the Mega **render** at all — every one of these species' Mega client
model is NOT VERIFIED, the same caveat `data/gulch_mine.json` already carries for Excadrill. (b) Walk
into the 41-block pad: **you should be turned back, facing the den**, which is decision B4 — tell me
whether "seen, not reached" feels right or merely annoying in open country. (c) The sightline measurement
that chose these sites **saturated at its 136-block ceiling for all twelve candidates**, so it proved
each has a long clear approach but did *not* rank them. Your eye is the real ranking.

## 4b. The new railing on Victory Road's brink — does it read, without crowding the reveal?

**Stand at (3565, 114, 5294)**, then walk the approach down toward the lip crossing at (3557, 113, 5306)
and on to the trailhead at **(3548, 114, 5322)**, where the gatehouse now stands.

The route passes **1-2 blocks from an 18-block drop** — ground falls y111 to y93 in a single block — and
37 railing columns now mark it: a pier of the skin's own rock on the same band hash, one course of
cobbled deepslate wall, a lantern every fifth column.

**Three things only your eye can settle.** (a) Does it read as a barrier, or as scenery you would walk
through? (b) **One course was chosen deliberately** so the wall's collision cannot be stepped over while
its top stays below eye level and the Rift is still revealed from the descent — is that right, or does it
crowd the reveal? (c) **Two isolated end posts** stand where the brink turns, at (3555, 5304) and
(3572, 5283); the coverage count proves they are not holes, but they may still *look* like a mistake.

While you are there: the **gatehouse moved here** from 318 blocks inside the basin. Does a gate on flat
open ground at the trailhead read as a gate at all, or does it need the rock around it? And **do not try
to walk out of it** — all six gatehouse walkways are impassable on foot (decision B12, being fixed now),
so leaving on foot is expected to fail until that lands.

## 5. The portals — do they read as relics?

Six dive and six sky, applied and re-skinned on the deleted world, so unseen as they now stand.

| Dive | | Sky | |
|---|---|---|---|
| Viltri floor | (1652, 2996) | Downs crag | (4530, 1951) |
| Shrew pit | (2856, 3960) | Marsh horn | (5450, 2661) |
| Tarn bottom | (3388, 916) | Gorge shoulder | (6630, 4667) |
| Peak Pond floor | (4068, 1480) | Tableland head | (5601, 5632) |
| Watering hole floor | (2958, 5235) | Assay tor | (7007, 5834) |
| Tilpey gate | (6076, 4296) | Far reach | (7613, 7498) |

**The specific worry:** the dive arches **lost their lights** in the 2026-09-30 re-skin (sea lantern →
dark prismarine). Do they still read as *made* things underwater, or as rubble? That is the question
behind "do they read as relics".

## 6. The rest, in order of how much rests on it

- **The Deep's city**, 196 buildings and 9 stair towers in the pit — and **where the Heaven's Arena tower
  would stand** (the Core spire, crown y128 against the HQ's y132). Judge whether a fight tower belongs
  in a displaced summit town at all.
- **The Rift dig camp** (`rift_dig_camp`): Forge Row's 9 rock houses, 2 quarries, a worked face, 3
  drifts, 11 ore piles, 303 powered rails, 9 carts. And look east across the floor toward the relic area
  — that flat span is why unit 3 was cancelled: **182–211 columns wide, nothing above y110.**
- **The wayside shrines**: Brock's Route 1 cairn (1609, 3767), Misty's lantern stone (1699, 2873),
  Surge's fork niche (1699, 1501), Koga's Route 5 niche (4509, 2303).
- **The evolution-stone faces**: 22 at seven places. Flight finding 2 is still open — some read as *too
  far from their towns*, the Mining Town's at 150–210 blocks out reading as unconnected.
- **Sunset west's south pier** (2701, 6639) and the ferry docks.
- **The sleeping Celebi** on the Route 1 sapling — walled in barrier blocks, inert, the wake undesigned.
- **Pallet / Hometown**: the sign (1456, 5287), Oak's Lab (1487, 5309), the Centre (1432, 5238), the Mart
  (1467, 5239). **Oak's stand marker is the one of thirteen that could not be authored** — his anchor is
  indoors and the heightmap under a building is terrain, not floor. Tell me where he should stand.

## 7. What a flight cannot settle

- **Whether the Rift's shape is the one we want.** The heightmap holds a sculpt computed with a normals
  bug that was later fixed; re-applying would move ~10,867 columns (decision A1). Flying it tells you
  whether you *like* what is there, which is useful — but it is not the same question.
- **Two-player behaviour** anywhere: gated counters, NPC dialogue, the Hall of Lenses. Blocked on a
  second account (C4).
