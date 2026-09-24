# ADR-003: Where evolution stones come from

- **Status:** Proposed
- **Date:** 2026-09-23
- **Evidence:**
  - `docs/mechanics/EVOLUTION_STONES.md` (the full design, its arithmetic and its unknowns)
  - `docs/mechanics/SPAWN_PHILOSOPHY.md:258-424` ("The rosters carry families this world cannot
    finish": the 20 stone-gated families, measured on `data/spawns.json`)
  - `docs/world-building/WORLDGEN_FEATURES.md:5-9, 25, 99-113, 115-171` (why no feature runs; the
    Underground Pockets and scatter-pass alternatives)
  - `experiments/EXP-017-ore-pockets-and-object-load/README.md:85-88, 147-168` (the ore features'
    own replace rules and host rocks; measured Underground Pockets settings)
  - `base-pack/cobbleverse/config/roughlyenoughitems/collapsible.json5:139-161` (the 23 ore block ids)
  - `data/spawn_blocks.json:1577-1585, 1857-1865, 2027-2035, 2881-2889` (vanilla ore summons the
    Rock and Steel lines through `neededNearbyBlocks`)
  - `tools/validate_data.py:2583-2637` (a spawn-condition block in placed content must be whitelisted)
  - `tools/reapply.py:155-172, 267-311` (the fail-closed step requirement and the step list)
  - `docs/decisions/ADR-002-reward-delivery-mechanism.md` (the per-player reward spine this reuses)
  - Owner-supplied, from a jar read in another session and **not yet filed in `docs/research/`:**
    all 66 evolution-stone recipes take ore, deepslate ore, or the stone's own compressed block.

## Context

Twenty of the families in the placed rosters cannot be completed in this world, and ten more wait
on another item (`SPAWN_PHILOSOPHY.md:316-353`, VERIFIED by count on `data/spawns.json`). The
cause is not balance: a WorldPainter export writes every chunk as already generated, so none of
Cobblemon 1.8.0's 42 evolution-stone ore features runs (`WORLDGEN_FEATURES.md:5-9, 25`). The only
stone ore left in the game is `nether_fire_stone_ore`, and Fire Stone is the single stone with no
consumer in the rosters at all.

`SPAWN_PHILOSOPHY.md:387-391` named the question that decides whether this is a blocker or a
note — what the stones' recipes take as input — and left it UNKNOWN. The owner has since read the
jar: **all 66 recipes take ore, deepslate ore, or a compressed block of the stone. None takes
ordinary materials.** So the answer is "blocker", and with structure chests absent, raid dens
removed and zero trainers placed (`SPAWN_PHILOSOPHY.md:392-400`), there is today no path to any
of the ten stones except the Nether's fire stone, which nothing needs.

This must be decided now because it is upstream of three things already in flight: reward content
(ADR-002 explicitly sequences itself against this, `ADR-002:189-195`), the early-route
availability work the owner opened on 2026-09-23 (`docs/STATE.md`), and the next export — one of
the candidate mechanisms only ships with a re-export and the live re-export is already queued.

## Decision

**Proposed. Put the ore in the rock, at seven authored sites, in face volumes that a generated
function resets on a timer.** Four parts:

1. **Ore blocks, native, at authored positions.** `cobblemon:<stone>_stone_ore` and its deepslate
   and special-host variants placed inside authored face boxes. Breaking one uses Cobblemon's own
   loot table and crafting uses Cobblemon's own recipes: we supply position, not behaviour. Under
   `CLAUDE.md` principle 6 the ore is **rung 1 (Cobblemon native)** and the placement and reset
   are **rung 7 (functions and commands)** — the proven shape in this repository
   (`tools/rift_deep.py`, `tools/habitat_blocks.py`). No scripting layer, no server companion, no
   custom mod, and no new dependency of any kind.
2. **The face is shared and resets; a per-player floor covers the rest.** A block is world state
   and there is no per-player block view without a mod, so "ore in the rock" and "per-player" are
   mutually exclusive. The face is shared, resets on a ten-minute cycle, and refuses to reset
   while a player stands in it. Each site *additionally* grants one stone of its type, once, per
   player, on first arrival, by exactly the mechanism ADR-002 proposes — so a player who arrives
   second is never empty-handed. If ADR-002's two-player proof fails, the floor is dropped and
   the faces are unaffected.
3. **Ten stones across seven sites, not ten towns.** Water at Viltri Light, Leaf and Shiny at the
   tea town, Sun at the Scar, Moon at the Displaced City, Ice at Northlight, Dusk and Dawn at the
   gorge hamlet, Thunder and Fire at the Mining Town, which anchors the system as the only place
   that works stone as an industry and the clearing house where the rest are traded on. Assignment
   follows reachability first (twelve of the twenty families are served before gym 5), then the
   host rock Cobblemon itself implies (EXP-017 A1: sun stone alone replaces terracotta, moon stone
   alone has a dripstone feature), then the identity the place already has. The reasoning, the
   rejected alternatives and the measured distances are in `EVOLUTION_STONES.md` §3.
4. **Everything is a record, re-applied.** `data/mines.json` (`cobblers.mines/1`) generated by
   `tools/mines.py` into `cobblers_mines`, run by a new `tools/reapply.py` step (R17, after the
   donors and the cavern). Anything placed by hand is erased by the next export, and `prepare`
   now fails closed on a pack no step runs (`tools/reapply.py:155-163`) — which is the only
   reason the five missing Rift steps were ever found.

Blast radius: **no world-critical surface.** No block, biome, structure or worldgen feature is
added to the map's foundations; the faces are small authored volumes inside places that already
exist. Reversing this costs seven cuts and a pack, not the map. Multiplayer: the face is shared by
design and the contention it creates is bounded by demand (a party of four completionists needs
sixteen Water Stones *in total*, `EVOLUTION_STONES.md` §6.1); the guard against a reset firing on
an occupied box is mandatory, not optional.

## Alternatives considered

- **(a) The Underground Pockets pass at the next export.** The strongest alternative, and the
  only one already proven: EXP-017 measured settings that land within about ±30% of Cobblemon's
  own stone densities, two layers split at y0, painted per biome
  (`EXP-017/README.md:147-168`). It restores the ore economy world-wide with **zero runtime cost
  and no reset at all**. Rejected as the primary for three reasons. It puts the supply in
  unauthored caves, where VERIFIED the pack's own underground pools are live and Gengar bands run
  to 36-50 (`docs/STATE.md`, "What actually spawns underground in the Rift is the pack's"), so
  finding a stone means meeting somebody else's encounter design. It gives no place an identity —
  the owner's premise is that towns grew around working the stones, and pockets are the opposite
  of a town. And it ships only with an export: the live re-export is blocked on seven items
  (`docs/STATE.md`, "What still blocks the live re-export") and this would add an eighth. **Kept
  as a compatible later addition, not a competitor:** a very low background density in deep caves
  would be fiction-consistent, and could be added at any future export without touching the faces.
  If the owner would rather have supply than places, this is the cheaper decision and it is
  already measured.
- **(b) The specified scatter pass, `tools/scatter.py`.** `WORLDGEN_FEATURES.md:115-171` specifies
  it and VERIFIED it does not exist (`SPAWN_PHILOSOPHY.md:288-297`). Its stated blocker — needing
  an NBT writer — is obsolete now that every block pass is generated mcfunction. But it is a
  general-purpose tool for flora, fossils and mints as much as ore, it is a much larger build than
  a twenty-face pack, and its output is the same "ore in random caves" as (a). Not rejected as a
  project: it should be judged on apricorns and berries, which have no alternative, rather than on
  stones, which do.
- **(c) Caches and hidden items (ADR-002's spine alone).** Per-player, once-only, multiplayer-safe
  by construction, and it cannot express a repeatable source at all (`ADR-002:196-198`). A stone
  economy delivered entirely by one-shot advancements makes each stone a unique quest item, which
  is a different game from the one the owner asked for and is worse fiction. Kept as the floor
  (decision item 2), which is its correct size.
- **(d) Trader stock, and rctmod trainer reward tables.** The highest rung available where a
  trainer already stands (`ADR-002:82-87`), and VERIFIED the stones' loot tables are mostly
  trainer rewards and structure chests (`SPAWN_PHILOSOPHY.md:392-400`). But VERIFIED 0 trainers
  are placed, the trader stock policy withholds whole categories, and badge-gated stock has not
  landed (`docs/STATE.md`). This is the *convenience* layer for stones a player did not travel
  for, and it depends on systems that do not exist yet. It cannot be the source.
- **(e) One town per stone.** The owner's first instinct and their own doubt. Rejected: ten mine
  towns would consume every non-gym place including rest stops and unserviced outposts, overwrite
  identities `SETTLEMENTS.md` gave deliberately (harbour, observatory, tea), flatten the map into
  a commodity grid, and cost ten builds and ten reset loops for a system worth about two hours of
  play. Cobblemon's own data disagrees with even distribution: three stones have a special host
  rock and want particular geology.
- **(f) Per-player instanced faces.** N copies of each face assigned per player. Rejected for the
  reasons ADR-002 already rejected the same shape for caches (`ADR-002:132-133`): the player count
  is not fixed, a late joiner has no instance, and a player still sees another player's rock.
- **(g) Do nothing; accept twenty un-completable families.** The honest fallback, and it is not
  absurd — nothing on the critical path needs a stone, and `data/spawns.json` already carries
  these rows at `weight: 0` with a stated reason. Rejected because the rosters were authored on
  the assumption that catching a base stage leads somewhere (`data/spawns.json:32-49`
  `evolution_policy`), and because a difficult campaign that removes twenty team options removes
  answers its own gyms were balanced against.

## Consequences

- **Easier:** twenty families stop being dead rows; the stones become a reason to walk to seven
  places that currently reward nothing; reward design stops waiting on this question, and
  ADR-002's "entangled with GAP 1" sequencing note (`ADR-002:189-195`) resolves in favour of caches
  holding things other than stones.
- **Harder:** a new data file, a new tool, a new re-apply step and a new validator, all of which
  must exist before a single face is built; and the ore filler that supplies the flavour spawns
  forces a deliberate `data/spawn_block_policy.json` whitelist entry per site
  (`tools/validate_data.py:2583-2637`) — the system catching a real decision, not a nuisance.
- **A new file needs an owner.** `data/mines.json` belongs with `datapack-content-dev` on the
  `docs/STATE.md` ownership table, beside the future `data/events.json`; its validator belongs to
  `test-author`. Add the row when the file is created.
- **Nothing may be authored beyond one proof face** until the runtime items in
  `EVOLUTION_STONES.md` §7 pass — above all what a stone ore actually drops and at what pickaxe
  tier, which decides both the arithmetic and whether an early site is playable at all. Principle
  20, and the cheapest moment to be wrong is now.
- **Revisit when:** the recipe and drop reads land (they may make the rate arithmetic wrong in
  either direction); eeveelutions enter the rosters, or stones acquire a second sink such as
  trade, at which point demand stops being tiny and the reset becomes a real rate limiter; a
  future export makes the Underground Pockets pass free to add as a background layer; or the
  badge-gated trader stock lands and "the rest are traded on" becomes mechanism instead of
  fiction.
