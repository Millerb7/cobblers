# Route 1 Hut — The Thirsty Stranger

- **Event ID:** `EVT-ROUTE1-THIRSTY-STRANGER`
- **Kind:** Comedic character encounter and item trade
- **Route anchor:** Pallet (1462, 5293) to Brock’s town (1743, 3628)
- **Progression:** Optional; no story flag

## Premise

A man in a small roadside hut looks unmistakably like a 1990s West Coast
rapper. He wears a bandana, speaks with total confidence, and refuses to admit
he is Tupac. He is also extremely thirsty and too proud to ask for water
directly.

This is an easter egg, not a major Worldshift reveal. The scene never confirms
how he arrived or turns a real person into campaign lore.

## Location

Place the hut entrance at `(1509, 4469)`, route distance 1039.4 and route ground
`y122.6`. Keep the footprint east of the road around `(1521, 4461)`, no larger
than 9×7 blocks. This moves the scene away from Celebi's sapling at
`(1380, 4628)` while preserving a visible roadside stop.

## Visual direction

- Bandana and simple travel clothes.
- Small table, empty cup, chest, bedroll, and no functioning water source.
- A music-related object may decorate the room, but avoid real album art,
  logos, or copied lyrics.
- Working NPC name: **The Stranger**. Do not label him Tupac in UI text.

## Before water

1. `T001` — Before you ask: no.
2. `T002` — No what? Exactly.
3. `T003` — I am just a traveler with a familiar face.
4. `T004` — People see the bandana and lose all judgment.
5. `T005` — All eyes on me. Constant problem.
6. `T006` — You got any supplies?
7. `T007` — Something clear. Cool. Life-supporting.
8. `T008` — Not that I need water.
9. `T009` — I could stop being thirsty whenever I want.
10. `T010` — I am choosing not to.
11. `T011` — Builds character.
12. `T012` — Also headaches.
13. `T013` — Things change when you have not had a drink all day.
14. `T014` — Keep your head up. Mine is pounding.
15. `T015` — Again: I am not asking for water.
16. `T016` — I am creating an opportunity for generosity.
17. `T017` — Different thing.
18. `T018` — And I am not Tupac.
19. `T019` — Never heard of him.
20. `T020` — Water first. Questions never.

## Accepted offerings

Accept one of the following after item IDs are verified:

- Cobblemon or pack **Fresh Water / Pokémon water bottle** item;
- `minecraft:water_bucket`, consuming the water and returning the empty
  bucket;
- another campaign-approved drink only if it is added deliberately to the
  acceptance list.

Do not accept arbitrary potions, milk, lava, or rain as substitutes. Special
one-line rejections are welcome, but the player should understand the valid
items from the empty cup and dialogue.

## Bucket response

- `TB01` — A whole bucket.
- `TB02` — I asked for water, not municipal infrastructure.
- `TB03` — Still counts.
- `TB04` — Here. Take your bucket back.

## Bottle response

- `TF01` — That is exactly what I was not asking for.
- `TF02` — Hand it over.
- `TF03` — Finally.

## After water

1. `TA01` — All right. You helped me. I respect that.
2. `TA02` — You want the truth?
3. `TA03` — Fine. People used to call me Pac.
4. `TA04` — That is all you are getting.
5. `TA05` — Tell nobody where this hut is.
6. `TA06` — Especially anybody carrying a camera.
7. `TA07` — I have had enough eyes on me.
8. `TA08` — Take these. Payment for the water and the silence.
9. `TA09` — If anyone asks, you met a handsome beekeeper.
10. `TA10` — I do not own bees. That helps the story.

## Reward bundle

- **Black Glasses** held item candidate, subject to item-ID and balance check.
- One Minecraft music disc chosen from assets already allowed in the pack.
- A small bundle of ordinary capture supplies appropriate before Brock.
- Empty bucket returned when that option was used.

The rewards should be useful and funny, not strong enough to make the event
mandatory.

## Repeat dialogue

- **Before completion:** One of `T006`, `T009`, `T015`, or `T020`.
- **After completion:** “Handsome beekeeper. Remember the story.”
- **Holding another water item afterward:** “Prepared now, huh? Growth.”

## Multiplayer behavior

- Water delivery and rewards should be tracked per player.
- The stranger remains in the hut after another player completes the event.
- A water bucket must always return an empty bucket to the same player.
- The shared chest is decoration and must not permit reward duplication.

## Implementation gaps

1. NPC skin or model that evokes the joke without copied promotional art.
2. Verified IDs for the water-bottle alternatives, Black Glasses, music disc,
   and capture supplies.
3. Conditional dialogue based on held or submitted items.
4. Per-player completion and duplicate-safe rewards.
