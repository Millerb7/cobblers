# Gym matchup sufficiency audit

> ## Review, 2026-09-23: read this first
>
> This audit was written against **the inherited Cobbleverse RCT v20 leaders** and **a route-only reading of
> availability**. Both of those inputs have since changed, and the audit's per-gym verdicts do not survive
> unaltered. Nothing below has been deleted; this section says what still holds.
>
> **What changed under it.**
>
> 1. `data/trainers.json` now carries **our own authored rosters**, seven of eight, sitting exactly on the route
>    ceilings the audit recommended. The inherited teams it audited were 5 to 15 levels higher: it judged Blaine
>    at 57-60 where ours is 47-50, and Giovanni at 68-70 where ours does not exist yet. Most of its "thin"
>    verdicts were driven by that gap, and recommendation 2 has already been applied to the rosters.
> 2. `docs/story/AVAILABILITY.md` is regenerated from **every compiled pool**, not the curated route compilation
>    alone. Sub-region and waterway pools are in it now. The species counts before each gym roughly double:
>    19 / 24 / 44 / 74 / 91 / 110 / 146 / 184.
>
> **The conclusion that does not survive: Gym 3 is not thin.**
>
> The audit set aside the Wooper population as "the existing pond-shore Wooper ... should not carry the entire
> fairness contract until its one-per-player delivery is proven". That is not what it is. The compiled
> `mt_clay_outflow` waterway pool carries **Wooper across 100 boxes at bucket `common`, weight 23.98, levels
> 24-30**, with Quagsire uncommon and Clodsire rare spawning directly beside it, 57 blocks off the Route 3
> corridor at its closest. It is ambient and repeatable, not an event, and there is no Wooper event in
> `data/events.json`. Wooper is the single most common thing on that river.
>
> So Surge has **three** Ground families before the gym, not one: Bunnelby to Diggersby on Route 3, and
> Wooper to Quagsire and Clodsire on the waterway. All three are Electric-immune. Against our authored Surge,
> `tools/battle_sim.py` finds 5 catchable species that beat the whole gym one on one and 9 that beat Raichu.
>
> **Therefore the Route 2 quarry Geodude does not earn its place as a balance fix.** It was recommended to
> create "a second common family" for a gap that has two already. The audit's other argument for it -- that a
> quarry needs rock-dwelling fauna and extends the miner scene -- is a world-building argument and should be
> decided on those grounds alone, or the quarry should be cut.
>
> **Neither addition was ever implemented, so there is nothing to cut.** Checked 2026-09-23 against the
> encounter data: **Geodude, Graveler and Golem appear nowhere** in `data/spawns.json` -- no entry, no
> sub-region, no habitat. The quarry population was never built.
>
> Wimpod does exist, in two places: `long_isle_south` (25-45, uncommon, weight 6) and `south_strand` (50-52,
> common, weight 9), with Golisopod beside it in both. But both arrived in `a767d1e` *Compile encounter rosters
> into Cobblemon spawn data*, which **predates** this audit's own first commit `b80cdce` on the same day. They
> are original roster content on a rocky shoreline -- mareanie, clauncher, pincurchin, crabrawler -- that the
> audit then pointed at as an existing thing to extend. Cutting it would delete coherent content that was never
> added for a phantom problem.
>
> **South Strand Wimpod likewise.** It was recommended for Gym 8, which has no roster in `data/trainers.json`
> (`status: held`, empty team), so nothing about it can be certified. Gym 8's availability is now 184 species
> with 12 Ground families. Cut it or defer it until the rewritten Giovanni exists.
>
> **Item by item, of the coordinated fix package:**
>
> | # | Item | Verdict |
> |---|---|---|
> | 1 | Keep the Kanto order and the ceilings 20/25/30/35/40/45/50/55 | **Survives.** The simulation shows a clean monotone difficulty curve on those ceilings. |
> | 2 | Retune leaders to the ceilings; set the cap offset to zero | **Half done.** The authored rosters sit on the ceilings. `rctmod-server.toml` still has `relativeLevelCap = 5`, so the runtime half is open. |
> | 3 | Route 2 quarry Geodude | **Does not survive as a balance fix.** See above. |
> | 4 | Build and prove the Route 1 mansion Ghost habitat | **Survives, and is more urgent than it was.** Ghost is absent from authored availability until Gym 7, and **every** habitat pool is inert because `data/habitat_blocks.json` places no blocks at all. |
> | 5 | Make the Displaced City cavern accessible before Sabrina | **Survives**, on the same evidence. |
> | 6 | South Strand Wimpod | **Does not survive.** See above. |
> | 7 | Preserve the species sets for Erika, Koga and Blaine | **Survives, strengthened.** 24, 22 and 36 catchable families can hit those three aces super-effectively. |
> | 8 | Redesign Giovanni at level 55, Mewtwo out of the gym | **Untestable here** and superseded: there is no roster to redesign, and the owner is rewriting the fights. |
>
> **One correction that cuts the other way.** The audit's "availability is sufficient, the only gap is levels"
> for Blaine is now an understatement. `tilpey_waters` sits **one block** off the Route 7 corridor carrying
> Arrokuda and Basculin at L39-48; Barraskewda beats all six of Blaine's team one on one. With the corrected
> pools the best six available win Blaine losing nobody, where the route-only reading had them losing.
>
> **What none of this touches.** The audit's evidence boundary still stands: no encounter pool, Habitat Block,
> RCT battle or level-cap behaviour has been proven in the target runtime, and `data/habitat_blocks.json` places
> no blocks, so items 4 and 5 are unbuilt rather than merely unproven. Separately, the pack's own inherited
> pools are live in unauthored caves and off-route wilderness, which no version of this audit has accounted for.


**Status:** coordinated design audit complete. No encounter pool, species
placement, leader roster, level cap, move, item, reward, or runtime config was
changed.

## Recommendation

Keep the fixed Kanto leader order and the current route progression curve. The
geography already puts sensible answer ecosystems before each leader. Retune
the inherited leaders to the route ceilings, set the eventual enforced cap to
the next leader's ace rather than ace plus five, and make only the small number
of place-driven availability changes listed below.

Difficulty should come from complete teams, coverage, switching, resources,
and battle format. A ten-to-fifteen-level deficit followed by permission to
grind five levels above the boss works against the campaign's team-building
goal.

## Evidence boundary

This audit compares `data/routes.json`, `data/spawns.json`, the authored Habitat
rosters, the inherited Cobbleverse RCT v20 Kanto trainer files, the target RCT
0.19 cap calculation, and Cobblemon 1.8 species data. Natural level-up moves
are counted; unplanned TMs, move-reminder access, held items, hidden abilities,
and evolution items are not.

The route bands, compiled encounter pools, Habitat Blocks, RCT battles, and
level-cap behavior have not been proven in the target runtime. The conclusions
below are design findings, not functional-test results.

## The level problem affects the whole campaign

RCT 0.19 calculates the cap from the strongest Pokemon on the next required
trainer plus `relativeLevelCap`. The inherited config sets that offset to five.
The resulting curve does not match the authored route bands.

| Gym | Leader | Route ceiling | Inherited ace | Current inferred RCT cap | Gap from route to ace |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | Brock | 20 | 20 | 25 | 0 |
| 2 | Misty | 25 | 25 | 30 | 0 |
| 3 | Lt. Surge | 30 | 35 | 40 | 5 |
| 4 | Erika | 35 | 40 | 45 | 5 |
| 5 | Koga | 40 | 50 | 55 | 10 |
| 6 | Sabrina | 45 | 55 | 60 | 10 |
| 7 | Blaine | 50 | 60 | 65 | 10 |
| 8 | Giovanni | 55 | 70 | 75 | 15 |

The recommended leader ceilings are therefore `20/25/30/35/40/45/50/55`,
with `relativeLevelCap = 0` after EXP-003 proves the behavior. Preserve the
leaders' species identities and tactical roles while scaling individual team
members into the ranges below.

| Gym | Recommended team range | Recommended ace |
| ---: | ---: | ---: |
| 3 | 27–30 | 30 |
| 4 | 33–35 | 35 |
| 5 | 38–40 | 40 |
| 6 | 42–45 | 45 |
| 7 | 47–50 | 50 |
| 8 | 52–55 | 55 |

Keeping the inherited levels instead would require route ceilings of roughly
`20/25/35/40/50/55/60/70`. That creates uneven ten-level chapters, requires a
large rewrite of wild levels and evolution gates, and rewards grinding more
than scouting. It is the weaker option.

## Gym 3 — Lt. Surge

**Verdict:** thin. One dependable plan exists at level 30; a second is possible
but brittle. The inherited level gap makes both worse.

The inherited team is Boltund 32, Magnezone 33, Electabuzz 34, and Raichu 35,
with two Full Restores. Magnezone has Sturdy and a Focus Sash. Strong Jaw
Boltund carries Fire Fang, Ice Fang, Psychic Fangs, and Thunder Fang, so it
deliberately punishes simple Grass, Ground, and Fighting answers.

**Plan 1 — Diggersby core.** Common level 21–23 Bunnelby can evolve immediately
and naturally use Bulldoze or Dig. Diggersby covers Raichu, Electabuzz, and
Magnezone; Hariyama and Drampa provide Fake Out, Fighting pressure, Glare, and
switching support against Boltund. Huge Power is not required.

**Plan 2 — resistance and chip.** Skiddo has Synthesis, Seed Bomb, and
Bulldoze; Hariyama supplies Fake Out and Force Palm; Lycanroc supplies Rock
Tomb and Accelerock. This can cover the team, but Boltund can trade favorably
into every component. At the level-30 ceiling it is too fragile to count as a
second dependable answer.

**Coordinated fix:** scale Surge to levels 27–30 and add a localized Geodude
population to a visible Route 2 quarry or rock cut tied to the existing miner
scene. Geodude belongs in that place independently of Surge, learns Bulldoze
at 12, evolves at 25, and creates a second common family without consuming a
Route 3 ambient slot. The existing pond-shore Wooper remains a worthwhile
event, but it should not carry the entire fairness contract until its
one-per-player delivery is proven.

Do not add Diglett, Mudbray, or Sandshrew solely to manufacture another
counter. Each would require a new Route 3 niche or displace an existing species
while solving a problem the quarry can solve more naturally.

## Gym 4 — Erika

**Verdict:** availability is sufficient; the only identified gap is levels.

The inherited team is Bellossom 38, Roserade 39, Victreebel 39, and Vileplume
40, with two Focus Sashes, a Weakness Policy, and three Full Restores.

**Plan 1 — Flying offense.** Scyther has Wing Attack, Noctowl has Air Slash,
and Swablu can become Altaria at 35. Flying remains super-effective against all
four members despite the Poison secondary typing.

**Plan 2 — Ice offense.** Bergmite has Avalanche and Ice Fang, Cryogonal has
Aurora Beam, and Smoochum has Ice Punch and can become Jynx at 30. This plan is
independent of the Flying roster and requires no unplanned TM or item.

**Resolution:** scale Erika to levels 33–35. Add no species. The alpine and
glacial Route 4 geography already earns the Ice roster, while the preceding
woods and mountain slopes earn the Flying roster.

## Gym 5 — Koga

**Verdict:** two coherent compositions exist at level 40. The inherited
level-49–50 team, three Full Restores, and two Focus Sashes prevent a fairness
claim at the current route ceiling.

The inherited team is Crobat 49, Drapion 49, Toxtricity 49, Weezing 50, and
Venomoth 50. Crobat and Levitate Weezing invalidate a Ground sweep; Drapion is
immune to Psychic. This is a team-composition check rather than a single-type
check.

**Plan 1 — split offense.** Ampharos uses Thunder Wave, Power Gem, and
Discharge against Crobat and Venomoth; Jynx uses Psychic and Lovely Kiss
against Weezing and Venomoth; Diggersby uses Ground damage against Drapion and
4x damage against Toxtricity, with Quick Attack to finish a Focus Sash.

**Plan 2 — defensive immunity core.** Levitate Bronzong covers Crobat,
Weezing, and Venomoth with Extrasensory, Hypnosis, and Heavy Slam. Quagsire or
Diggersby covers Drapion and Toxtricity. Lycanroc supplies Accelerock to finish
Sash targets. The Wooper learn-then-evolve Earthquake sequence still needs a
runtime check, so Diggersby is the safe fallback.

**Resolution:** scale Koga to levels 38–40 and tune the recovery/Sash package
in the final roster pass. Add no species. Slowpoke at Peak Pond or Mudbray on
the downs would fit their locations, but neither is needed to make the existing
ecology sufficient once the level contract is corrected.

## Gym 6 — Sabrina

**Verdict:** one ambient strategy exists at level 45 and one strong authored
strategy exists only on paper. The inherited ten-level gap and unplaced
habitats keep the matchup thin.

The inherited team is Galarian Rapidash 52, Mr. Mime 53, Hatterene 54, and
Alakazam 55, with three Full Restores. Three members are Psychic/Fairy;
Hatterene carries Mystical Fire, Alakazam carries Drain Punch, and Rapidash
carries Megahorn and High Horsepower. Rapidash's declared Synchronize ability
is not legal in the target Cobblemon data and needs correction.

**Plan 1 — ambient Dark/Steel core.** Skuntank has Sucker Punch and Night
Slash; Levitate Bronzong has Heavy Slam and resists Rapidash's entire inherited
set; Scyther, Masquerain, Heracross, and Toxtricity provide Bug or Poison
redundancy. Bronzor's ultra-rare weight and required Levitate ability make this
a prepared plan rather than broad baseline access.

**Plan 2 — haunted-mansion Ghost core.** The already-authored Route 1 mansion
roster includes Shuppet, Duskull, and Sableye. Banette, Dusclops, and Sableye
have natural Ghost offense and priority options by level 45. The species earn
their place because it is a haunted mansion, not because Sabrina exists.

**Coordinated fix:** scale Sabrina to levels 42–45, correct Rapidash's ability,
and make the existing mansion a clearly discoverable, repeatable multiplayer
Habitat before it is counted as guaranteed availability. The already-authored
Displaced City cavern is a second thematically valid source of Sableye,
Mimikyu, Greavard, Steel, and other strange urban-cavern encounters if it is
accessible before the gym. Add no new species to Marsh Creek solely to answer
Sabrina.

## Gym 7 — Blaine

**Verdict:** availability is sufficient; the only identified gap is levels.

The inherited team is Torkoal 57, Magcargo 58, Arcanine 59, Magmortar 60,
Typhlosion 60, and Charizard 60, with four Full Restores. Arcanine and
Magmortar carry Electric coverage, while Charizard carries Solar Beam.
Torkoal has White Smoke rather than Drought, so Solar Beam remains a two-turn
move.

**Plan 1 — marsh core.** Barboach naturally gains Aqua Tail, Muddy Water, and
Earthquake before becoming Whiscash. Lycanroc supplies Rock Slide against
Charizard when Solar Beam pressures Water/Ground members.

**Plan 2 — fast Water offense.** Floatzel has Liquidation, Crawdaunt has Razor
Shell, and Golduck has Hydro Pump. Electric coverage checks individual
attackers without invalidating the whole composition. High-level wild Psyduck
should not be required until generated movesets or move-reminder behavior are
proven.

**Resolution:** scale Blaine to levels 47–50. Add no species. The sequence from
Marsh Creek through Lake Tilpey's three shores naturally earns multiple Water
and Water/Ground families before the crater gym.

## Gym 8 — Giovanni

**Verdict:** the inherited battle is not a Ground-type sufficiency test. It is
a mixed level-68–70 doubles boss, and no level-55 composition can be certified
against it as written.

The inherited team is Persian 68, Rhyperior 69, Tyranitar 69, Nidoking 69,
Nidoqueen 69, and Mewtwo 70, with four Full Restores. Only Rhyperior and the
Nido pair are Ground-type. Tyranitar, Persian, and Mewtwo require Fighting,
Bug, Dark, or Ghost answers. Tyranitar's declared Sand Veil is illegal in the
target species data; Dragon Fang and both Power Herbs have no matching move;
several EV spreads do not support their movesets.

**Plan 1 — Tailwind split offense.** Swanna provides Tailwind; Seismitoad and
Gogoat cover Rhyperior and the Nido pair; Hariyama covers Tyranitar and
Persian; Drapion and Cacturne pressure Mewtwo. The inherited Rock leads both
carry Thunder Fang, and level-70 Mewtwo outspeeds and covers the Dark finishers,
so this is not dependable at level 55.

**Plan 2 — direct offense and double priority.** Golduck and Lurantis cover the
Ground members; Machoke and Heracross cover Tyranitar and Persian; Skuntank and
Thievul can double-target Mewtwo with Sucker Punch. The fifteen-level deficit
still makes the Mewtwo line unreliable and leaves no robust second source of
doubles speed control.

**Coordinated fix:** scale the gym to levels 52–55, repair invalid abilities,
items, and EVs, and redesign it as a Ground-centered doubles fight. Move Mewtwo
to a separate story or postgame boss rather than distorting the entire surface
availability plan around one legendary on a nominal Ground team. Preserve
Persian as Giovanni's signature if desired, but the remaining roster should
express Ground and sand doubles clearly enough that scouting produces a real
plan.

Select the already-authored Wimpod family for South Strand's Route 8 pool,
replacing one redundant Fire-family slot such as Sizzlipede while retaining
Centiskorch. Wimpod/Golisopod independently belongs on the rocky coast and
adds First Impression and Water offense to a late-game doubles toolkit. This
is a route-selection correction, not a species invented for Giovanni.
Plateau West's already-authored Vullaby also fits as a Rift-edge scavenger and
can be considered in the same final 20-species selection pass, but it is not
required for sufficiency.

## One coordinated fix package

No part of this package has been implemented. Apply it as one design decision,
then regenerate availability and run EXP-002/EXP-003 before treating it as
settled.

1. Keep the Kanto order and the route ceilings `20/25/30/35/40/45/50/55`.
2. Retune leader teams to those ceilings and set the proven runtime cap offset
   to zero.
3. Add one localized Route 2 quarry/rock-cut Geodude population.
4. Build, signpost, and runtime-prove the already-authored Route 1 haunted
   mansion Habitat; keep it repeatable or per-player for multiplayer.
5. Make the already-authored Displaced City cavern accessible before Sabrina
   if it is intended as an answer library, and prove its Habitat behavior.
6. Add Wimpod to the existing South Strand selection by replacing a redundant
   family rather than expanding every route pool.
7. Preserve the current species sets for Erika, Koga, and Blaine.
8. Redesign Giovanni's final roster as a level-55 Ground-centered doubles
   battle and move Mewtwo out of the gym.

| Change | Earns its place independently because | Gyms helped |
| --- | --- | --- |
| Route 2 quarry Geodude | A quarry or rock cut needs rock-dwelling fauna and extends the existing miner story | 3, with later utility against 5 and 7 |
| Route 1 mansion Ghost habitat | Ghosts belong to the authored haunted-mansion quest | 6 and 8 |
| Displaced City cavern habitat | Artificial, object-like, Ghost, and Steel species belong in a displaced urban cavern | 5, 6, and 8 |
| South Strand Wimpod | A rocky coast supports an armored shoreline scavenger | 8, with broader doubles utility |

Rejected as unnecessary in this package: a Surge-only Diglett pocket, Koga-only
Slowpoke or Mudbray placement, Sabrina-only Marsh Creek Skorupi, and an arid
Sandshrew pocket. These species can still be added later if their places become
valuable content on their own.

## Is the problem the region or the Kanto order?

It is mostly not the order. The region sequence already lines up with the fixed
leaders:

| Leader | Geography already encountered | Natural answer ecosystem |
| --- | --- | --- |
| Brock | coast, river, plateau | Water and Grass |
| Misty | meadow and lake | Electric and Grass |
| Surge | foothill woods, clay mountain, quarry/miner site, pond | Ground, Grass resistance, Fighting support |
| Erika | alpine and glacial route after woods | Ice and Flying |
| Koga | crags, downs, old-growth pond, glacier foot | Psychic, Ground, Rock, Steel |
| Sabrina | marsh, earlier haunted mansion, displaced urban cavern | Bug, Dark, Ghost, Steel, Poison |
| Blaine | marsh and three lake shores before craters | Water, Ground, Rock |
| Giovanni | scorched plateau, Rift foot, coast, authored Rift Depths | Water, Grass, Fighting, Bug, Dark, Ghost, doubles control |

The recurring thinness comes from four data/design choices:

1. inherited leader levels drift upward faster than the authored route curve;
2. inherited teams stack anti-counter coverage and recovery without a matching
   player item/TM plan;
3. the availability report counts selected ambient route entries but omits
   several authored place-specific habitats;
4. the final 20-species route selections are manual and can omit species that
   already belong to a sub-region.

There is mild order pressure before Sabrina because the immediately preceding
marsh is not an obvious Ghost biome. The mansion and Displaced City cavern
solve that through place-based ecology without changing the order or terrain.
No region redesign is warranted from this audit.

## Still unverified

- EXP-002: RCT AI, switching, invalid-data fallback, items, consumables,
  doubles lead order, multiplayer battles, and rewards.
- EXP-003: per-player cap enforcement through battles, experience, candy,
  reconnects, and restarts; `relativeLevelCap = 0` is a recommendation until
  proven.
- Compiled coordinate-box pools and bounded default suppression in a live
  route corridor.
- Habitat replacement, boundaries, multiplayer availability, and reconnect
  behavior for the mansion, Displaced City cavern, and Rift Depths.
- Final player access to TMs, move reminders, evolution items, held items, and
  consumables.
