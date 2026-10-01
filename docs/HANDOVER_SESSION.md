# Handover — the Rift's research is done, the builds are a fresh session's

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 0. Why this session stopped before building

**It hit the owner's own hand-over threshold.** `python tools/session_cost.py` at the stop: 186 turns,
**context 370k, every turn costing 37k to send**, weighted 5.5M — of which the four subagents were only
1.6M and this session's own thread was 3.9M. CLAUDE.md: "Over 300k: hand over", because "a long session is
the single most expensive thing we do". Continuing the builds at 370k a turn would have bought less than a
cold session buys at 70k. That is the finding, not an excuse: the research phase and the build phase are
different jobs and the boundary is here.

**The builds cannot be delegated either, and that is the night's structural finding.** Three of the five
Rift units (the Slip, the relic site, the Mega dens) need `derived/` and the canonical heightmap. Verified
this session: an agent's isolation worktree receives **no `derived/`** (`agent-*/derived/` holds only the
tracked `README.md`) and there is no `.worktreeinclude` at all. So every heightmap-dependent build is
main-session work by construction. Plan the next session as one build job, not as a fan-out.

## 1. The branch and the PRs

- Working branch **`build/2026-10-01-rift-economy`**, cut from `fix/2026-10-01-vr-trainer-ownership`.
  Re-read its head: `git rev-parse HEAD`. One commit of substance: `485e364`.
- **[PR #102](https://github.com/Millerb7/cobblers/pull/102) is OPEN, draft, base `main`, and FROZEN** —
  it carries the trainer-ownership work and was reported to the owner. Push nothing to
  `fix/2026-10-01-vr-trainer-ownership`. Check a branch's PR state **before** a push, not after:
  `gh pr list --head $(git branch --show-current)`. This session's predecessor got that order wrong.
- `origin/main` is `a271532` and does **not** yet have #102's suite fix. Anything that runs the suite on
  main will still report `no tests ran`.
- No PR opened for `build/2026-10-01-rift-economy` yet.

## 2. Part 1 — the Rift, unit by unit

| Unit | State | Next step |
|---|---|---|
| 1. Heaven's Arena | **Designed, costed, not built** | Build the geometry; hold the fights behind A1 |
| 2. Relic site underground | Not started; existing design contradicts the owner | Re-design section 5, then carve |
| 3. Mining town / Deep barrier | **Designed already — "the Slip"** | Build it as blocks, not as a sculpt |
| 4. Mega farm in the open | **AUTHORED AND PARKED; audit clean** | Rewrite its test surface (chip `task_1cb2b2d7`) |
| 5. The four withheld zone walls | **ANSWERED: stay withheld** | Nothing. Do not reopen |

### Unit 5 is closed, with proof
`rift_crisis_resolved` still has **no setter on any branch**. `data/quests.json` on `origin/main` says it
itself, verbatim: *"Invoke only after the authoritative rift_crisis_resolved setter commits successfully;
no current dialogue node invokes this trigger"*, and *"rift_crisis_resolved is approved in ARC.md but
absent from the progression ledger"*. Checked across every remote branch including
`codex/mainline-reveal-pallet-brock`. The walls stay withheld; the finale's quest stage is Codex's.

### Unit 1 — the answer the owner asked for
`docs/world-building/HEAVENS_ARENA.md` (385 lines). **They coexist: the arena is the Core spire grown
upward. 0 of 196 buildings and 0 stair towers lost**, because lots seed only within 16 blocks of a riser
foot and the spire already stands on the one large footprint that rule leaves empty. 7 tiers on the pit's
own 15-then-17 grammar, crown y128 (4 under the HQ tower, so the HQ stays dominant), the existing y15
bridge from Relay Row is tier 1's door, and the 9 stair towers plus 8 lift pairs are the lift. Runners-up
costed: the Core (8 buildings plus the confrontation's stage), the north face (up to 27 Stacks lots).

**Two things the builder must not miss.**
- **Lots are seeded AFTER the spire claims its columns, and a lot under 40 columns is dropped with no
  error** (`tools/deep_city.py:960,1064`). A wider drum therefore costs buildings *silently*. Diff
  per-district lot counts before and after, every time.
- Use `rift_deep.model()["centre"]`, not DEEP_CITY.md's `(3603,3222)` and not `the_deep.seed`
  `(3600,3150)`; they disagree.

### Unit 1's fights are BLOCKED on one experiment, deliberately
`docs/research/notes/rct-arena-capabilities.md` (368 lines). An endless ladder needs **nothing we lack**:
repeatable fights are the default (`maxTrainerDefeats` negative = infinity), CobbleDollars pays every win
automatically ($732, then $600 on a rematch), and `requiredDefeats` is a 2-D list (OR within, AND across)
that expresses "beat tier N before N+1" **per player** natively. rctmod cannot generate a team, hold a
per-player champion, or keep per-mob state; a per-player tier holder rides the MoLang quest fields
`tools/route_trainers.py` already writes.

- **A1, the blocker: does `requiredDefeats` gate a trainer with `series: []`?** UNPROVEN. Principle 20
  says prove it before building the ladder. The exact commands are in the file's section 7.
- **The cap trap:** a player's level cap is derived from the next required trainer **in their series**, so
  the arena must use `series: []` or it hijacks every cap in the game. This is the kind of cross-system
  consequence that has bitten before — read the consumers before wiring it.
- Geometry and fights are separable. Build the tower; leave the ladder until A1 answers.

### Unit 3 — the Slip, and why NOT to sculpt it
The owner's own design already exists: `docs/world-building/DEEP_CITY.md` section 6, **"The barrier
(recommended): the Slip"** — a landslide ridge across the spur floor at about **x3290–3310** (trace it from
the two region masks, which overlap there), 24–30 above the floor, sheer on the camp side, with a one-way
down-lift on the relic side and an up-lift gated on a flag. `data/rift_mines.json`'s `keep_clear` box
`relic_area_and_the_slip` (`rect [3280, 3150, 3440, 3440]`) already reserves the ground for it.

**The document says to sculpt it into `data/rift_sculpt.json`. Do not, without the owner awake.**
`tools/rift_heightmap.py --apply` **rewrites the canonical heightmap and `data/world.json`**, which
re-pins the sha256 every measured artifact in the repo is keyed to and needs a full world re-export. That
is the one irreversible act available here and it is not a thing to do unsupervised. The reversible route
is a **block-built rockslide**, and there is a proven precedent to copy: the gulch's rockslide wall
(`tools/gulch_mine.py`, `data/gulch_mine.json` `gate.band` — `top`, `core`, `spread_out`, `spread_in`,
`batter`, `jag`, `min_rise`), raised to the crag tops after the owner's gate test found a y122 rockfall
read as passable. It re-applies and can be undone.

### Unit 4 — the cheapest thing left, and it is nearly free
**`tools/gulch_mine.py` already implements `farms[]` end to end** — the zone check and turn-back, the
per-tier level, the respawn clock, the drop roll and the shared keeper (macro `megas/spawn_at`, per
EXP-046). **`data/gulch_mine.json` has no `farms` key at all.** Its own `megas.why` references
`farms[].dens` and `farm_tiers` describes "four outer dens" that do not exist. So the open-air Mega farm
is *unbuilt, with its tool already written*. The unit is data authoring.

The schema the tool reads (extracted from the code, not guessed):
- a farm: `id`, `name`, `tier`, `approach` `[x0,y0,z0,x1,y1,z1]`, `zone` `{polygon, turn_back:[x,y,z,yaw]}`, `dens`
- a den: `id`, `species`, `aspect`, `anchor` `[x,y,z]`, `leash`, optional `level` / `tier` /
  `drop_percent` / `respawn_ticks` (the tier supplies the rest from `farm_tiers`)

**The one obstacle, and the wrong way to clear it.** `tools/gulch_mine_audit.py:242,407` checks coordinates
against `spec["grid"]` (`x 4228–4500, z 4640–4970`) and these sites are far outside it. **Widening `grid`
would weaken the block-write guard** that keeps this build inside its box — a threshold widened to make
data pass is not a threshold (CLAUDE.md). Dens write **no blocks** (keeper and zone functions only), so the
right change is a *separate declared box* for den anchors and turn-back points, leaving `grid` tight.

**The 12 measured sites** (off the canonical heightmap, never a world; inside the arm polygons, pad slope
< 10°, 24+ clear of every `keep_clear` box, 260+ apart). `derived/` is gitignored, so they are written out
here rather than lost:

| Arm | x | z | ground | pad slope |
|---|---|---|---|---|
| west | 3944 | 3904 | 146.0 | 9.1 |
| west | 4080 | 4168 | 148.0 | 8.3 |
| west | 4104 | 4728 | 84.6 | 8.4 |
| west | 4200 | 5056 | 118.1 | 7.0 |
| west | 4248 | 5328 | 127.7 | 9.0 |
| west | 3984 | 5392 | 122.4 | 6.6 |
| east | 4344 | 3904 | 87.7 | 3.2 |
| east | 4264 | 4312 | 87.1 | 6.2 |
| east | 4528 | 4416 | 121.7 | 3.2 |
| east | 4576 | 4680 | 121.2 | 8.3 |
| east | 4608 | 4944 | 132.3 | 5.5 |
| east | 4488 | 5216 | 144.0 | 6.8 |

Notes for whoever picks: **the sightline metric saturated at its own 136-block ceiling for all twelve**, so
it proves each has a long clear approach and did NOT rank them — spacing and arm coverage chose them. The
scan script is `scratchpad/site_megas.py` (disposable; re-run it rather than trusting this table if the
heightmap moves). Drop the four under y100 if the intent is the arms' open uplands rather than the Rift
basin floor. The east arm holds the gulch, its road and the Cutters; the **west arm has nothing in it**,
which is the obvious home for the "deeper" tier.
**A design caution:** a turn-back zone around an open-air den fights the owner's own brief ("a player
should see them before they reach them"). Keep each zone tight to the den's pad so a Mega is *seen, not
reached* — the cordon language the Deep already uses — or let the level band (60 / 67 against a cap of 50)
be the gate and give the open farms no zone at all. That is an owner decision; `farm_tiers` is ASSUMED
throughout and nothing in it has been timed.

### Unit 2 — not started, and the existing design now contradicts the owner
The owner wants the relic site **much deeper, reachable only upward from the Compact HQ, with the zone
check turning players back rather than glass or barriers.** `DEEP_CITY.md` section 5 currently has the
opposite: a **surface** platform on the Deep's west lip (x3285–3429, z3229–3384, y86–100) with six ring
arches, inside "a Compact cordon (a fence of tinted glass and iron bars)" — the exact glass-and-barrier
answer the owner has now rejected — plus the cradle already deep at **floor y12, (3357, 3306)**, reached
from "HQ ring-0 front at x3427 → a secure shaft down to the basement at y0 → the 70-block passage west".
So the shaft-from-the-HQ half is already designed and matches the owner; the **surface shrine is the part
that must go down**, and the cordon must become a zone check. Re-write section 5 before carving anything.
`tools/cavern_plan.py` is the named precedent for the rock shell.

### Unit 4, done as far as it can go in one session
Seven dens are authored in `data/notes/mega_farms_proposal.json`, ready to paste into
`data/gulch_mine.json` as its `farms`, `farms_why` and `farms_grid` keys. With them in place
`gulch_mine.py build` emits all seven and `gulch_mine_audit.py` is CLEAN. **They are parked because
switching them on turns 15 tests red** — 12 in the gulch suites, 3 contracts (C12 once, C14 twice) — and
**not one red is a fault in the data.** The gulch suite was written to assert the raw-stone drop roll is
dormant (`test_the_drop_roll_is_inert_without_a_farm_den`) and `tests/gulch_sim.py` has no NBT storage
model, which the roll is built on. The rewrite is chip **`task_1cb2b2d7`** and must be a **main session**
(the contracts test imports the generator in-process, so it needs the heightmap and `derived/`) run by a
**different hand** from the data's author.

Do not dodge it by zeroing `drop_percent`: the roll is keyed on a den existing, not on its rate, and the
drops are the farms' half of the material chain the owner said to keep.

**The general lesson, which bears on units 1, 2 and 3 equally:** every build here activates a
verification surface, and that surface needs a different author with heightmap access. So **plan one
build unit per session**, with its test rewrite as the session after.

## 3. Part 3 — the economy

- **3d is ANSWERED** — `docs/mechanics/MARKET_GATING.md` (257 lines). **Stock can be gated per player, and
  not on the merchant.** The casino's score reaches a *total*, not a stock list; per-player **dialogue
  option visibility** does (`tools/compile_dialogue.py` `isVisible` from `visible_when`, plus a
  `cobblers:flag/<id>` advancement probe per player). The recommendation is the **ferry's already-proven
  checked-payment sequence** (`cobbledollars query` → refuse if short → `remove` → re-read and verify →
  deliver), rung 5 + rung 7, no scripting and no new mod. It **corrects the brief**: what stalled was not
  missing per-player machinery but that trader stock is baked into the `summon` line at build time
  (`tools/traders.py:163-201,248-275`), so a category withheld from one player is withheld from everyone.
  Costs: the trade GUI is lost at gated counters, a new counter needs a restart rather than `/reload`, and
  **nothing stops player A buying for player B** — gating controls purchase, not possession.
  **Unknown:** whether two players can hold an open dialogue with the same NPC at once (EXP-022's
  two-player test is still unrun, blocked on a second account).
- **3a is ANSWERED** — `docs/research/PROGRESSION_UNLOCKABLES.md`. The backpack is **Sophisticated
  Backpacks** (`sophisticatedbackpacks` 1.21.1-3.23.4.3.106), in OUR overlay, on both sides. Six tiers
  (27 / 45 / **81** / 96 / 108 / 120 slots) plus **56 upgrade items**, including a six-rung stack ladder
  and portable crafting/anvil/smithing/stonecutter — the most on-brief items in the pack. Obtained by
  **crafting and nothing else** (verified: chest loot off, mob drop 0.0, loot tables empty), so nothing
  hands a tier out behind our back. Gateable **EASY** by datapack recipe suppression.
  **Three findings that bear on the ladder's shape:**
  1. **Cobbleverse has already flattened its own curve.** Iron is buffed from the mod's 54 slots / 2
     upgrades to **81 / 7**, so gold, diamond and netherite add about 12 slots and one upgrade slot each.
     Four of the six rungs have almost nothing left to give — a ladder built on tiers alone would feel
     flat, and the 56 upgrades are the better currency.
  2. **A suppressed recipe reads as a mystery, not a goal**: the tier stays registered and givable but
     shows no recipe in REI with no explanation. The better lever is selling tiers in CobbleDollars'
     `default_shop.json`, a plain per-item price list.
  3. **No mod in the pack exposes a per-player gate. The only per-player mechanism is possession of an
     item.** This is the same wall `MARKET_GATING.md` hit from the other side, and together they are the
     answer to Part 3: per-player dialogue visibility decides *who may buy*, and the item in the pack
     decides *what they then have*.
  **THE HIGHEST-VALUE OPEN QUESTION, and 3b waits on it:** is CobbleDollars' `defaultShop` **global or
  per-merchant**? It decides whether a mining town can sell what a mining town would, or whether every
  town sells one list. Answer that before designing the ladder.
  **Caveat that could collapse the ratings:** the jars are **not on this machine at all**
  (`base-pack/cobbleverse/mods/` does not exist; `modpack/mods/` holds a README). No recipe file was read.
  Every item id is verified from the pack's own REI index
  (`config/roughlyenoughitems/collapsible.json5`) at Cobbleverse **1.7.42**, and **13 mods are
  version-replaced for 1.8**, so ids need re-checking. Datapack recipe suppression itself is **ASSUMED
  and untested in this pack — if it fails, every "EASY" rating drops to NONE.**
  Other EASY levers: CobbleDollars (the market itself), TMCraft (six blank grades, no config at all),
  Waystones (**world-critical**; `defaultVisibility="ACTIVATION"` already makes travel the unlock, plus a
  `warpRequirements` cost language), CobbleverseBadges (40 plain badge items, the cheapest rung token),
  Comforts (**world-critical**; sleeping bags are what make "no house" literal).
  **Not available:** the raid dens' seven tiers — **our overlay removes the mod** (1.8 world-load crash).
  **Already running a parallel progression, to be reconciled rather than layered on:** our own
  `modpack/config/rctmod-server.toml` sets `initialLevelCap=20`, `initialSeries="kanto"`,
  `freeroamRequiresCompletedSeries=true`, `spawningRequiresTrainerCard=true`; and Lumymon's
  `remotePcEnabled=true` gives remote Pokemon storage from day one, which undercuts storage as a reward.
- **3b and 3c (the ladder, and the backpack as the spine) were NOT started.** 3a is now in hand, so they
  are the next session's first economy job — after the `defaultShop` question above.

## 4. What waits on the owner

1. **Which tenth Victory Road trainer stands at the exit ravine** — main's League Examiner (4 Pokemon)
   or our Gate Warden (3), kept in `data/vr_trainers.json`'s `superseded_roster`. Also 38 superseded
   seat-file dialogue sets: the roster's lines are what a player hears.
2. **Giovanni.** One stale field: `data/gym_trainers.json`'s `held: true`, whose reason quotes an empty
   team that no longer exists. `data/trainers.json` has him authored, six Pokemon at 52–55 (top = his
   contract's 55), singles, `blocked_by: None`. Clearing it makes eight leaders' teams reach a player
   instead of seven. Not done: it changes what a player fights.
3. **The arena's 10 numbered questions** at the end of `HEAVENS_ARENA.md`.
4. **Unit 4's zone question** above: seen-not-reached, or no zone and let the level band gate it.
5. **Whether the Slip may be sculpted** (irreversible, needs a re-export) or must stay a block build.

## 5. The review list — refusals and judgement calls this session

- **`cobblemon-researcher` has no Bash at all.** Verbatim: *"No such tool available: Bash. Bash is disabled
  for this session, in subagents as well as here."* It stopped that line correctly and did the work with
  Read/Grep/WebFetch, so **every bytecode claim in `rct-arena-capabilities.md` is a quotation of an
  earlier read recorded in the repo, not fresh jar evidence** — the jars are absent from agent worktrees
  too. Brief that agent type without jar work.
- **THREE agents were refused a compound Bash command** (a heredoc twice, a `for` loop once) and then used the `Write` tool for the same
  in-worktree path. The refusal's own text says *"Split it into plain, separate commands"*, so both read it
  as a complaint about command shape rather than a denial. **Strictly, CLAUDE.md's rule is "a different
  tool reaching the same outcome" and that is what happened — twice.** The owner should decide whether the
  guard's suggested remediation counts as an exception, because it will keep happening.
- **A heightmap rewrite was declined on the session's own judgement** (unit 3 above). Reversible route
  taken instead; the owner can overrule.
- Seven doc/data/code disagreements were found and recorded rather than silently patched. **Owner
  decision D3 (2026-10-01) was "fix all seven", and six are now FIXED** — each by reading the code or the
  data first to establish which side was right, and changing only the wrong side:
  1. **Stair towers: 9, not 8. FIXED.** A run's own counts are "stair towers round lift banks 8" and "the
     Sink Gate 1" (`python tools/deep_city.py build --source-root <root>`), and `rift_deep.lift_sites()`
     returns 8 pairs, 2 at each of the 4 boundaries. The code and the owner were right; `docs/STATE.md`
     and `docs/world-building/RIFT_STATUS.md` now say nine.
  2. **`data/rift_deep.json` `lifts.banks`: 10 → 8. FIXED in the data only.** The formula
     `per = max(2, banks // (len(treads) - 1))` reads the field as a TOTAL across the four boundaries, so
     only multiples of 4 above the floor of 2 are expressible and 10 could never mean 10. 8 is what the
     pit holds and what DEEP_CITY.md says, so the value was corrected instead of the formula (no code
     change, `tools/rift_deep.py` untouched); a `banks_how_it_is_read` note records why. `lift_sites()`
     places the same 8 pairs before and after.
  3. **"about 130 buildings" → the measured 196. FIXED.** DEEP_CITY.md now carries the run's per-district
     counts (Rimside 69, the Works 38, the Quarter 29, Relay Row 20, the Core 8, the Stacks 27, HQ 5) and
     keeps the 130 above them labelled as the circle arithmetic it was.
  4. **DEEP_CITY.md's "not run on staging" header. FIXED.** It is applied to `staging-2026-10-01` (one of
     the 38 of 38 steps). The header says so, keeps "not in the live world" and "never seen by a player",
     and records that `cobblers-dryrun9`, `dryrun11` and `dryrun12` are DELETED, so the 2026-09-27 result
     cannot be re-checked.
  5. **The cradle coordinate. FIXED in `docs/story/FACTION.md`:** (3357, 3306) under the relic area, per
     `data/rift_regions.json` and STATE's settled answer, with a note retiring (3297, 2603) — outside the
     Rift, heightmap y118 against the League footprint's 86-99 — and naming the propagation it already
     caused (`npc_main_league_steward`, Codex's to fix upstream).
  6. **`GYM_INTERIORS.md`'s trainer-cooldown rule. FIXED.** `route_trainers.cycle_lines()` writes the
     cooldown when **any** nearby player has beaten the trainer (the `unless entity @a[…,tag=!<tag>]`
     clause went on 2026-09-29), so the doc's "every nearby player" and its first consequence were
     inverted: the beaten player is protected and the unbeaten partner must start the fight by hand. The
     section now states the live rule, the change, and the routing constraint that is lifted with it.
  **The seventh, `data/gulch_mine.json`'s `megas.why` / missing `farms` key, was another agent's in the
  same wave and is not covered by this entry.** `docs/world-building/HEAVENS_ARENA.md` section 8, where
  findings 1-5 were recorded, now marks them fixed and keeps the entries as the record.
- `tests/test_id_authorship.py` has three uncovered cases queued as chip `task_77d572d3`.

## 6. Nothing is in the world, and nothing was applied

**No `prepare`, no install, no apply, no staging boot, no server start.** The server was down at the start
(no listener on 25565, no Java process) and is down now. `python tools/install_check.py --server-dir
C:/Users/wnd/Documents/github/cobblers-server` ran clean at session start: **0 problems (packs and
configs)**. `python tools/validate.py`: 1,238 files, 0 errors, 0 warnings.

**The coordination lock is FREE** — taken at the start for `install_check`, released at the end.

## 7. What this session cost, per unit

`python tools/session_cost.py`, weighted (context × turns, cache reads at a tenth) — never the harness's
per-agent figure, which is final context and about 20× low:

| Unit | Agent | Weighted |
|---|---|---|
| 1. Heaven's Arena, cost to the city | `content-architect` | 0.52M |
| 1. RCT arena capability | `cobblemon-researcher` | 0.43M |
| 3d. Market gating | `minecraft-systems-dev` | 0.30M |
| 3a. Mod unlockables audit | `dependency-auditor` | 0.46M |
| **Agents together** | | **1.7M** |
| **This session's own thread** | | **4.0M** |
| **Total** | | **5.7M** |

The ratio is the lesson, and it is the same one as 2026-09-28: **the four agents that answered four
questions cost 1.6M between them; the single thread that briefed them and read the files cost 3.9M.** The
owner's instinct that parallel agents beat one long thread is right, and the way to act on it is to keep
the orchestrating session short — hand over at the phase boundary rather than carrying the research
phase's context into the build phase.
