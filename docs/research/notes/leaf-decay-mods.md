# Stopping leaf decay on a Fabric 1.21.1 server

Question (2026-10-20): is there a maintained, server-side-only Fabric mod for
Minecraft 1.21.1 that stops leaf decay, so clients need nothing? Answered for
Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.2.

## Verdict

**No Fabric 1.21.1 mod that stops leaf decay exists on Modrinth.** The only mod
that does what is asked is NeoForge/Forge only. Every Fabric leaf mod found
speeds decay up or changes which leaves/logs count as connected. Ranked
options at the bottom.

## VERIFIED

Method: Modrinth API (`/v2/search` with queries `leaf decay`, `leaves`,
`decay`, `persistent leaves`, `prevent leaf decay`, `random tick`, filters
fabric / server_side) and `/v2/project/<id>`, run 2026-10-20. Search hits
for `doLeafDecay`, `gamerule leaf`, `no leaf decay`+1.21.1 filter, `leaf decay
stopper`, `keep leaves`, `block tick blacklist` returned zero Modrinth hits.

### Local manifest

- No leaf/tree/foliage mod is present in `modpack/manifest/overlay.json` or
  `modpack/manifest/base-cobbleverse-1.7.42.json` (case-insensitive grep for
  `leaf|leaves|foliage|tree`: only a path string matched). So no existing
  mod there is a known second author of leaf decay. Lithium
  0.15.4+mc1.21.1 (`base-cobbleverse-1.7.42.json:2464`), FerriteCore 7.0.3,
  ModernFix 5.25.1 are present; whether any mixes `LeavesBlock` was NOT
  checked (jars not opened). See ASSUMED.

### The only mod that stops decay: Leaf Decay Stopper (not usable)

- CurseForge slug `leafdecaystopper`, author CrabMods, source
  https://github.com/CrabMods/leaf_decay_stopper, licence GPL-3.0.
- Loaders: Forge 1.20.1 and **NeoForge 1.21.1 only**. Files (CurseForge
  files page): `Leaf Decay Stopper 1.21.1-1.0.1` NeoForge 2026-10-18,
  `leaf_decay_stopper-1.0.0.jar` NeoForge 1.21.1 2025-12-16, plus two Forge
  1.20.1 files. GitHub branches: `forge-1.20.1-47.3.11`, `neoforge-1.21.1`,
  `gallery`, `forge-1.20.1-47.3.0`. No Fabric branch, no Modrinth project.
- 19,620 CurseForge downloads. Server-only on multiplayer (per README).
- How it works (README): `/setleavesdecay <dimension> true|false`, op level 2,
  saved to config; "protection covers vanilla's leaf random-tick path", other
  blocks keep ticking. A third-party write-up describes it as a Mixin on
  `LeavesBlock.randomTick` (seen via search snippet only, not the source).
- Sources: https://www.curseforge.com/minecraft/mc-mods/leafdecaystopper ,
  https://www.curseforge.com/minecraft/mc-mods/leafdecaystopper/files ,
  https://github.com/CrabMods/leaf_decay_stopper

### Fabric 1.21.1 leaf mods (none stops decay)

| Mod | Modrinth id / slug | Client / server | Licence | Last update (project) | Downloads | What it does |
|---|---|---|---|---|---|---|
| Leaves Us In Peace | `IIpWIe1o` leaves-us-in-peace | unsupported / required | CC0-1.0 | 2026-09-18 | 133,694 | Faster decay, mixed leaf/log matching. No off switch. |
| Quick Leaf Decay | `3Puj7Mln` quickleafdecay | unsupported / required | CC0-1.0 | 2026-09-16 | 80,079 | Fork of the above; faster decay. No off switch described. |
| Leaves Be Gone | `AVq17PqV` leaves-be-gone | unsupported / required | MPL-2.0 | 2026-09-26 | 13.4M | Decay after a tree is cut; timing/rules configurable; page does not say decay can be disabled. |
| Cancel Block Update | `nQM9AEMV` cancel-block-update | optional / required | MPL-2.0 | 2025-07-05 | 2,511 | GLOBAL: cancels block updates, scheduled ticks and **random ticks** via gamerules. Not block-specific, so would stop crops. Rejected. |
| Leaf Decay Instant | `qI4oJZOt` | unsupported / required | MIT | 2026-07-13 | 2,567 | Versions 26.1+ only. Has `enabled`, `blacklistedLeaves`, `disabledDimensions` options, but those switch off the MOD (vanilla decay returns). Not 1.21.1. |

- Leaves Us In Peace 1.21.1 build: `1.6.2+MC1.21-1.21.1`, published
  2025-04-30, game versions 1.21 and 1.21.1, Fabric + Quilt, 251,749 bytes.
  Required dependency `P7dR8mSH` (Fabric API per ASSUMED id mapping; not
  looked up); optional `9s6osm5g`, `tbAZnTrE`, `mOgUt4GM`. Changelog: replaced
  "Ignore persistent leaves" with "Persistent leaves behavior" (IGNORE, NORMAL,
  MATCH_ALL); backported larger decay-delay limits.
  https://api.modrinth.com/v2/project/IIpWIe1o/version
- Its `fabric.mod.json` (GitLab branch `1.21`, the branch whose last commit
  2025-04-29 matches that release) declares `"environment": "*"` (not
  `server`) even though Modrinth marks it client-unsupported; it has a
  client-side config source set and Mod Menu entrypoint. Mixins
  (`leaves_us_in_peace.mixins.json`): `ChunkSerializerMixin`,
  `LeavesBlockMixin`, `ServerWorldMixin`, `WorldChunkMixin`,
  `accessor.DirectionAccessor`.
  https://gitlab.com/supersaiyansubtlety/leaves_us_in_peace/-/raw/1.21/src/main/resources/fabric.mod.json
- Its `LeavesBlockMixin` (summary from fetch tool, source not quoted): adds a
  decay tick scheduler, redirects `getOptionalDistanceFromLog`, wraps leaf
  matching by persistent setting, injects into `randomTick`. This is a speed
  and matching change; no code path found that suppresses decay.
- Quick Leaf Decay: https://github.com/wb1016/QuickLeafDecay , releases cover
  1.21 and 1.21.1 (Modrinth `/v2/project/3Puj7Mln`), fork of Leaves Us In Peace.
- Leaves Us In Peace's "Decay delay maximum" default is 60 and the range
  limit was NOT found; a huge delay as a decay "stop" is untested (see
  experiments).

### Vanilla method names (Yarn 1.21.1 javadoc)

`net.minecraft.block.LeavesBlock` declares `randomTick`, `shouldDecay`,
`scheduledTick`, `hasRandomTicks`, public static `getOptionalDistanceFromLog`,
private static `updateDistanceFromLogs`/`getDistanceFromLog`. Descriptions are
empty on the page.
https://maven.fabricmc.net/docs/yarn-1.21.1+build.3/net/minecraft/block/LeavesBlock.html

## ASSUMED (each with why)

- Vanilla 1.21.1 decay rule: decays when not `persistent` and
  `distance == 7`, checked in `randomTick`. Why assumed: matches the owner's
  stated behaviour and common knowledge; the method bodies were not read here.
- A ~20-line own Fabric mod would stop decay: `@Inject(HEAD, cancellable)` on
  `LeavesBlock.shouldDecay` returning `false` (it feeds `randomTick` and
  `hasRandomTicks`). Why assumed: method existence verified, bodies and call
  sites in 1.21.1 not read. It would need an experiment. It is server-side
  only (no registries, no networking) so clients need nothing. Per CLAUDE.md
  principle 6 a custom mod is the last resort.
- Lithium/FerriteCore/ModernFix do not mix into `LeavesBlock` decay. Why
  assumed: jars not opened; Lithium's optimisation list was not checked.
- An offline palette rewrite of the region files (every leaf blockstate
  `persistent=false` to `true`, chunk sections' palettes only, block data
  untouched) would take minutes for the 256 region files of an 8192x8192 map,
  not hours of fills. Why assumed: standard Anvil layout from memory, not
  tested; duplicate palette entries after the rewrite (an existing
  `persistent=true` twin of a `false` entry) could be a problem and must be
  tried on a snapshot, never the live world.
- Datapack-only hack (adding leaves to `#minecraft:logs` so every leaf sees a
  "log" neighbour) is not recommended: it would change planks recipes and
  other `logs` users, and stored `distance=7` states are not recomputed
  until a neighbour update.

## Ranking and recommendation

1. **Offline world edit on a snapshot** (palette rewrite via a script in
   `tools/`, applied to a staged copy, then promoted). Permanent, no runtime
   mod, no conflict surface. Newly planted/natural trees from new chunks
   would still decay, but a pre-built map inside its border generates none.
   Leaves later regrown by saplings are vanilla and not persistent.
2. **Own tiny server-side Fabric mod** mixing `LeavesBlock.shouldDecay`
   (also covers saplings-grown trees). Needs a proof (EXP) first.
3. Leaves Us In Peace / Quick Leaf Decay: does NOT meet the requirement.
   Only usable if a very large decay-delay maximum were accepted, untested.
4. Not usable: Leaf Decay Stopper (NeoForge/Forge only, GPL-3.0; Sinytra
   Connector would be needed and is not in our stack), Cancel Block Update
   (global, stops crops).

## Unknown / experiment candidates

- Does `LeavesBlock.shouldDecay` returning false (own mixin) stop decay of
  `persistent=false, distance=7` leaves already stored in chunks, without
  other side effects?
- Does Leaves Us In Peace accept an enormous `Decay delay maximum`, and does
  decay then effectively never happen within a session?
- Does an offline palette rewrite load cleanly (duplicate palette entries)?
- Do Lithium 0.15.4 / ModernFix 5.25.1 mixin into `LeavesBlock`?
- Were the Fabric branches of Leaf Decay Stopper requested upstream? Its
  issue tracker was not checked.

(Not edited, per brief: `CAPABILITY_MATRIX.md` and `EXPERIMENT_BACKLOG.md`; the
orchestrator should add the capability row and the experiments above.)
