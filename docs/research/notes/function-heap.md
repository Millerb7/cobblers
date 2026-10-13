# The function heap: one-shot packs stay parsed

Status: tooling built and tested offline (2026-10-12); the saving is an ESTIMATE until re-measured on staging.

## The measurement (relayed, not re-measured here)

Measured by the orchestrator on staging, 2026-10-12, with `jcmd <pid> GC.run` then `GC.heap_info` and a class
histogram:

- idle live heap 12.4 GB with nobody online;
- ~7-8 GB of it Brigadier's parsed commands: `StringRange` 0.92 GB, `ParsedCommandNode` 0.76 GB, `ParsedArgument`
  0.51 GB, `CommandContext` 0.39 GB, `LinkedHashMap` entries 1.1 GB, coordinate/blockstate argument classes ~1.2 GB;
- `class_8858$class_8861` (a parsed function line) has 6,491,795 instances against 6,563,647 installed function lines:
  every line of every loaded function stays parsed for as long as its pack is loaded.

So the lines of a pack nothing calls at play time cost heap for nothing once the re-apply has run them.

## The classification (`tools/pack_roles.py`)

Run on the built packs of the night-shift checkout's 2026-10-12 prepare (read only), with `cobblers_dungeons` taken
from this branch's generator so the split is counted. Lines are non-blank, non-comment function lines.

| | packs | lines | share |
|---|---|---|---|
| all installed packs | 122 | 6,490,311 | 100% |
| `build` (strippable) | 55 | 5,787,543 | 89.2% |
| `runtime` | 67 | 702,768 | 10.8% |

The line total differs from the relayed 6,563,647 because comments and blank lines are not counted here, and the
packs are one prepare, not the staging install.

Largest `build` packs: `cobblers_rift` 2,080,825; `cobblers_dungeons_build` 894,253 (the split, below);
`cobblers_sea_floor` 861,237; `cobblers_lake_life` 345,401; `cobblers_deep` 316,172; `cobblers_vr_caves` 225,139;
`cobblers_sea_life` 146,254; `cobblers_worldtree` 118,336; `cobblers_lakebed_repair` 115,903; `cobblers_towns`
96,272; `cobblers_deep_city` 90,632; `cobblers_sea_drift` 84,351; `cobblers_cavern` 79,987; `cobblers_route1` 61,834;
`cobblers_reapply` 51,576; then 40 smaller (`build/pack_roles.json` lists all).

Largest `runtime` packs, with the lines a runtime root reaches: `cobblers_dungeons` 189,892 (188,900);
`cobblers_gulch_mine` 171,840 (11,562); `cobblers_rift_biome` 97,622 (0: runtime for its worldgen biome);
`cobblers_rift_mines` 91,558 (25); `cobblers_relic_underground` 37,133 (31); `cobblers_mines` 12,661 (6,275);
`cobblers_caves` 11,973 (197); every other runtime pack is under 8,000.

Every pack the orchestrator's rough pass called hook-less is `build` here: no cross-pack call reaches any of them.
`cobblers_direct_trades`, listed world-local because "the barterer trades", is `build`: its barterers are summoned
villagers whose trades need no function.

Expected saving: 5,787,543 of 6,490,311 parsed lines (89.2%). If the parsed-command heap (~7-8 GB) scales with
lines, roughly 6-7 GB. An ESTIMATE until re-measured (procedure step 5).

The rules, all fail-closed: a pack is `build` only if no function of it is reachable from a runtime root (tick/load
tags; any function named by runtime data -- advancements, Cobblemon callbacks, dialogues, NPCs -- or by the repo's
configs; any function named inside a string or NBT, such as a command block or a click event, even in a build
function; any function a structure template names), across packs, through `function`, `execute ... run function`,
`execute if function`, `schedule function`, macro `$function a:b/$(c)` (every id the pattern matches) and function
tags; it carries no runtime data of any kind (an unknown kind counts as runtime); none of its block tags or templates
is named by runtime; and no file of it overrides another pack's at the same path (index.txt and merging tags
excepted). An unresolvable call (`function $(f)`, `run $(cmd)`, a callback that builds a name from a variable) reaches
every function: in this build there were none.

`python tools/pack_roles.py --why <function or prefix/>` prints the chain from a runtime root, e.g. the dungeon's room
resets are runtime: `rip_ab` advancement -> `door/ab` -> `door/go_ab` -> `slot/s13/reserve` -> `slot/s13/reset` ->
`room/.../s13/reset`.

## The dungeon split

`tools/dungeon.py` writes its one-shot placement -- `place`, `place/s<g>`, `shells/build`, `shells/s<g>/**`,
`rips/place`, `rips/blocks_<d>` -- into `build/datapacks/cobblers_dungeons_build` (`tools/pack_split.py`) under the
SAME function ids, so R16DG and R16DR, their tests and audits are unchanged. The look-then-act chains
(`shells/entities`, `rips/entities`) stay in the runtime pack. The split refuses, before moving anything, if any
command or data file left in the runtime pack names a moved function (macro and string-built prefixes included).

Not split, measured (build share = lines no runtime root reaches): `cobblers_gulch_mine` 160,278 of 171,840 (93.3%:
its surface, shell, earth and air passes), `cobblers_rift_mines` 91,533 of 91,558 (99.97%), `cobblers_relic_underground`
37,102 of 37,133 (99.9%: `carve/*` and `undo`); together 288,913 lines, 4.5% of the total. All are over 50%, but seven prepare audits read their
function files from the pack folder by name (`gulch_mine_audit`, `mega_field_audit`, `rift_mines_audit`,
`relic_underground_audit`, `deep_walk_audit`, `hq_tower_audit`, `finale_audit`), so splitting them is a follow-up
that must change those readers and be proven by a prepare. `cobblers_rift_biome` is runtime only because it carries
the Rift's biome (worldgen); its ~98k lines of biome painting are a split candidate on the same terms.

## The operator procedure

1. `python tools/reapply.py prepare ...` (the last job, `pack_roles`, writes `build/pack_roles.json`).
2. Server stopped: `python tools/reapply.py install --server-dir <server> --world-dir <world>` (every pack).
3. Boot at 24G; `python tools/reapply.py run --server-dir <server> ...`; stop the server.
4. Server stopped: `python tools/reapply.py strip --server-dir <server> --world-dir <world>`. It refuses while
   port 25565 answers or a java process runs, refuses a pack not installed as built, MOVES each build pack to
   `<server>/../cobblers-server-retired/stripped_<time>/{global,world}/<pack>` and records it in
   `build/install_record.json`. `install_check` then accepts those packs as absent by design and still fails on any
   missing runtime pack.
5. Boot at the play heap. `jcmd <pid> GC.run`, then `jcmd <pid> GC.heap_info`, and a class histogram: compare the
   live heap and the parsed-line instance count with the figures above.
6. Before the next apply: `reapply.py install` puts every pack back (`run` refuses a step whose call closure needs a
   stripped pack, and names it).

## Not verified

- The heap saving: an estimate from line counts, assuming heap scales with parsed lines. Re-measure (step 5).
- That a world-folder pack removed while stopped and later put back is re-enabled on the next boot, and that the
  global folder's loader does the same. Vanilla drops a missing pack from the enabled list and enables a newly seen
  one; the global folder's mod is not checked here. Step 6 then `install_check` and the world probes prove it.
- Functions an operator runs by hand over RCON (cleanups, probes) are not roots; a stripped pack holds none that the
  repo names, but a hand call into one answers "Unknown function" until `install`.
