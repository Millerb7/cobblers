# Gym stress-test judgment

This review interprets the reproducible 108-team run in
[`BATTLE_STRESS.md`](BATTLE_STRESS.md). It does not change a roster. The sample
uses 27 starters four times each, paired Normal/Challenge parties, six player
archetypes, encounter-rarity weighting, route-only profiles, uneven levelling,
and one-catch-per-area Nuzlocke-shaped profiles.

The primary percentage is deliberately harsh: the player enters with a realistic
party order and never switches. `Cap reorder` asks whether one of 36 stable
pre-battle orders wins after every straggler reaches the cap. It is a sensitivity,
not proof of winnability, because it still cannot switch during battle.

## Judgment

| Gym | Normal | Challenge | Why |
| --- | --- | --- | --- |
| 1 Brock | **Trivial** | **Punishing but fair** | Normal wins 94.4% with 1.33 faints. Challenge wins 22.2%, but 95.4% win after levelling and sampled reordering; the team composition is usually capable. |
| 2 Misty | **Fair** | **Unwinnable** | Normal wins 82.4% and prepared teams win 94.9%. Challenge wins 1.9%; only 29.6% win at cap after sampled reordering and 44 teams still have no answer in the simplified model. |
| 3 Surge | **Punishing but fair, low confidence** | **Unwinnable** | Normal wins 35.2%; the Ground lesson is legible, but only 64.8% win at cap after reordering. Challenge wins 2.8%, and just 18.5% clear after cap/reorder. |
| 4 Erika | **Fair** | **Unwinnable risk** | Normal prepared teams win 79.5%. Challenge wins 9.3% and only 52.8% clear at cap/reorder before Chlorophyll and the full sun engine are represented. |
| 5 Koga | **Punishing but fair, low confidence** | **Unwinnable risk** | Normal starts at 24.1% but reaches 81.5% at cap/reorder. Challenge reaches only 43.5%, and the simulator omits several mechanics that make Koga stronger. |
| 6 Sabrina | **Punishing but fair, provisional** | **Unwinnable risk, unresolved** | Normal rises from 29.6% to 89.8% with levels and order. Challenge reaches 60.2%, but Trick Room—the fight's engine—is a no-op in the simulator. |
| 7 Blaine | **Unwinnable** | **Unwinnable** | Normal wins 2.8% and only 21.3% clear at cap/reorder. Challenge records zero first-order wins and 5.6% at cap/reorder. The simplified simulation is already a wall. |
| 8 Giovanni | **Punishing but fair, low confidence** | **Unwinnable risk** | Normal rises from 22.2% to 79.6% with levels/order. Challenge reaches 57.4%, loses five members on an average win, and leaves most ordinary teams without a stable line. |

`Unwinnable` here means a meaningful share of these realistic parties cannot find
a win even after being levelled and reordered inside the simplified model. It is
not a claim that no human can win. Intelligent switching, TMs, held items and EVs
can rescue teams; leader switching and currently inert leader mechanics can make
the same fights worse.

## What loses

- **Wrong levels dominate Challenge Brock.** Forty-three of its 84 losses become
  wins when the same six reach the cap in the same order. The roster is harsh, but
  it is not composition-locked.
- **Composition dominates Challenge Misty and Surge.** Their cap/reorder rates are
  29.6% and 18.5%; the failure is not mostly four underlevelled stragglers.
- **Ordering dominates Sabrina.** Normal rises from 29.6% to 75.9% before levels
  change. That is exactly the kind of result no-switch simulation handles poorly.
- **Blaine is the red alarm.** Seventy-two Normal losses and 73 Challenge losses
  become possible only after stripping the authored engine, while almost no intact
  roster clears even at cap. His result is too lopsided to dismiss as sample noise.
- **Bad luck accounts for zero recorded losses because the engine has no random
  battle outcomes.** Accuracy is averaged into damage; critical hits, damage rolls,
  flinches and secondary effects are absent. Zero is a limitation, not a finding.

Type-blind teams win at least once in every Normal gym except Blaine. Challenge
type-blind teams win 6/18 at Brock, 1/18 at Misty, 2/18 at Surge, 2/18 at Erika,
3/18 at Koga, 4/18 at Sabrina, 0/18 at Blaine and 2/18 at Giovanni.

The Nuzlocke-shaped result is worse. Normal Brock is the only fight with clean
wins (6/15). Every later Normal or Challenge win costs at least one permanent
death, and Challenge Misty, Surge, Koga and Blaine wipe all 15 sampled teams. The
profiles are independent gym snapshots, so a campaign that carries deaths forward
would be worse than this report.

## How much the missing mechanics matter

| Gym | Dependence | Missing pieces that can reverse a result |
| --- | --- | --- |
| Brock | Medium | Protect is inert; Berry Juice, White Herb and Weakness Policy are not implemented; Body Press uses Attack instead of Defense; leader switching can preserve Lileep against Water. |
| Misty | High | Swift Swim, Hydration/Rest, Analytic, Damp Rock, Mystic Water, Fake Out and Icy Wind speed drops are absent or incomplete; rain-aware switching matters. |
| Surge | High | The policy generally ignores Thunder Wave and Light Screen while damage exists; Static, Strong Jaw, Iron Fist, Expert Belt, Encore and Volt Switch behavior are absent. |
| Erika | High | Chlorophyll, sun-boosted Growth, Weather Ball, Heat Rock and Regenerator switching are central to the design and missing or incomplete. |
| Koga | Very high | Pain Split, Toxic/Venoshock sequencing, Punk Rock, Throat Spray, poison secondary effects, Neutralizing Gas and leader switching are absent. |
| Sabrina | Very high | Trick Room is a no-op; Magic Bounce, Regenerator, Harvest and Hypnosis accuracy/state interactions are incomplete. The numeric verdict cannot validate the intended engine. |
| Blaine | Very high | Solar Power, Flame Body/Lava Plume burns, Stealth Rock, Eruption's HP scaling, Heat Rock duration, White Herb and leader switching are absent or incomplete. Most omissions strengthen Blaine. |
| Giovanni | Very high | Fake Out flinch, U-turn switching, Technician, Stamina, Sheer Force + Life Orb, Moxie, sand's Rock special-defense boost, Heavy Slam and multi-hit Double Hit are absent. |

The simulator also fixes both sides at IV 15/EV 0, gives players level-up moves and
no held items, and has never been compared with Cobblemon's embedded Showdown at
these levels. Player TMs and sensible held items bias real results upward. Most
unmodelled leader engines bias them downward. The direction is therefore not safe
to reduce to one correction factor.

## Recommended changes, not applied

1. **Keep Challenge Brock for the first playtest.** Its first attempt is severe,
   but almost every sampled composition can win after levelling and ordering.
2. **Keep Normal Misty and Erika.** They best match the intended split: prepared
   teams usually win and ordinary teams still pay a cost.
3. **Raise Normal Brock modestly.** Preserve three members, but make one middle
   member demand a second answer so a random team does not win 94.4% for one faint.
4. **Give Challenge Misty one pressure release.** Remove Damp Rock first so rain
   can be survived rather than lasting through the whole six. If runtime testing
   still walls teams, remove one anti-Grass coverage move rather than a member.
5. **Give Challenge Surge a Ground line.** Replace Vikavolt's Energy Ball first;
   Levitate can stay as the lesson, but the Ground/Water answers should not be
   punished by the same member that invalidates Ground.
6. **Shorten Challenge Erika's sun.** Remove Heat Rock before touching species.
   Five turns preserves the engine and gives weather management an endpoint.
7. **Remove one anti-Ground layer from Challenge Koga.** The smallest candidate is
   Drapion's Shuca Berry; keep the mixed Poison identities and let a prepared Ground
   closer perform its job.
8. **Do not tune Sabrina from this simulator.** Prove Trick Room and RCT support-move
   selection in game first. If the real fight is still a wall, remove one of the two
   Focus Sashes rather than dismantling Trick Room.
9. **Reduce Blaine before play.** Remove Heat Rock in both modes and rerun. If Normal
   remains below a 50% cap/reorder result, remove either Stealth Rock or one coverage
   move. Challenge should keep six, but not eight-turn sun plus hazards plus six
   complete coverage sets.
10. **Open one Grass line through Challenge Giovanni.** Remove Nidoqueen's Ice Beam
    or Rhyperior's Rindo Berry, then prove sand duration and switching before making
    a second change.

The next trustworthy step is not another larger Monte Carlo sample. It is one
logged in-game battle per mode for Misty, Sabrina and Blaine, using a losing sampled
party and the authored answer line. Those three distinguish composition wall,
unmodelled engine and formula drift.
