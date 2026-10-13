# Handover: session 44e927, 2026-10-13 morning (far past the context line, at the owner's request)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch
`build/2026-10-13-weather-trio` in worktree `.claude/worktrees/night-shift-engine-gym-9b76f2`, local only, NO PR yet.
It stacks on #136 (`build/2026-10-12-sanctuaries`, head d685aedfda153fea6eb69dd606ac6c3a12e629db), which stacks on
#135 (`build/2026-10-12-overnight`, head fca0a767d97be3c642c3eeca4aa4858959dac028). `git fetch --prune` and re-read
both heads before quoting them (the owner merges mid-session). Per the owner's rule (memory: one-big-pr-per-batch),
hand this over as ONE integration branch onto main, one draft PR.

## 2. Where it stopped
Merged on the branch tonight, none of it installed or seen in game:
- Rayquaza's sky (R14R), Kyogre's cave (R18KC), the six seas' and the Nether's balance pass, the seas' second rares.
- Hank and Lena: world-scoped quest fields in `tools/compile_dialogue.py` (175 of 175 compile), seats (R17N, R18CH),
  the crushed house (R16CH, `tools/crushed_house.py`).
- The dungeon draw: 20 region rips, the 13 trail rips retired by R16DR (`rips/retire`; 12 patches' ground assumed grass:
  check in game or from an OFFLINE snapshot), rip_the_rift kept though gated. Re-apply R16DR with nobody in a run.
- Economy v2 B1/B3/B4/B5 (bank 15 kinds, Master Ball barter 1 ingot + 5 scrap, five held items barter, Oak's card,
  economy_audit 0 problems, contract C28). Contracts + economy suites: 185 passed, 2 xfail (C3, C14).
- R9F no longer places Oak, the Route 4 packer or Maren a second time (`npc_placed_by`).
- Independent audits: `tools/kyogre_rayquaza_audit.py` (47 pass, 1 strict xfail: the cage, section 3);
  the draw's audit (`tools/dungeon_draw_audit.py`, merged): every draw check passes, 13 of 13 generator mutations caught;
  ONE siting defect (strict xfail): `rip_the_rift` stands inside Rift zone z2 (badge 8), so it is no find below band 5
  and `tools/dungeon_rips.py check` never reads zones. Owner's call: move it out of z2, or accept badge-gated rips
  (like the Nether's) and teach the check and the audit that rule. Notes: two trail rips lack `region`; rip_the_wedge
  and rip_southern_coast sit in far_south's keep_out_box.
- Economy v2 DESIGN only: `docs/mechanics/ECONOMY_V2.md` (E1-E12 await the owner).
- Mod update audit: `docs/research/COBBLEVERSE_COMPATIBILITY.md` "Update audit, 2026-10-13" (22 UPDATE, 14
  UPDATE-CAREFUL, 10 HOLD); nothing downloaded: each file needs the owner's yes.

Known red tests: `test_coldwater_station_audit::test_built_pack_passes_every_check` (built-pack stub rule owed a
rewrite, recorded by the Kyogre builder); four ash_bell `lure` cases in `test_dungeon_audit` and one vault-budget text
case in `test_dungeon_kit3` (both red at 6249332e, before the draw). The dungeon suites' full run did NOT complete: `test_dungeon_audit.py` (2,135 per-site cases) ran past 50 minutes at 3%
with 16 early failures unidentified; the other dungeon and rip suites were re-run in the background (`.scratch/d2.txt`). Contracts: 76 pass, C3 and C14 xfail.

Staging: last installed from prepare 238/238 at bff8baf (2026-10-12), build packs stripped, 12G. Next cycle: snapshot
to D:, prepare, stop, hold the bank file, install, boot 24G watchdog off, `reapply.py run` (new steps include R14R,
R18KC, R16CH, R18CH, R16DR re-apply, R9F), stop, watchdog 60000, `strip`, boot 12G, read back
(`npc_seats.py verify`, `presence_audit --only extra`, the per-place verify commands). A fresh session should do it.

## 3. Waiting on the owner
- Economy E1-E12 (`ECONOMY_V2.md` section 6). The owner's 64 cobble = $100 is ~8x the spine (estimate).
- Mod updates: DOWNLOADED (the owner: "download any updates that we can") 40 files to
  `C:/Users/wnd/Documents/cobblers-local/mod-updates-2026-10-13/` (MANIFEST.json; each size and SHA-512 matched
  Modrinth's record). Not installed, not boot-tested. Excluded: the Cobblemon 1.8.2 lockstep set (capturexp has no
  1.8.2 build: owner's call to drop capturexp or wait), HOLD rows, alphas. Next: snapshot, staging boot test.
- (was) Which mod updates to download (per file; Cobblemon 1.8.2 moves in lockstep with rctapi 0.16.2, capturexp has no
  1.8.2 build, CobbleDollars Beta-6.1 renames the bank file, tm_megadrain is gone).
- Kyogre's cage: a player who logs out on the dais can be sealed in barrier. The audit's two properties contradict at
  Kyogre's own spot. Recommended: a rejoin eject (leave_game stat) plus the audit excluding the sleeper's own cells.
- DECIDED 2026-10-13: the 13 trail rips go; every region gets a rip; badge-gated rips stay (rip_the_rift); Nether
  dungeons draw from overworld rips (no Nether rips); Kyogre's rejoiners are moved out (BUILT, merged 7bbd4d48). Agents building the rest and
  economy B1/B3/B5 were running at hand-over. Economy E3 (allowance) and E7 (13 held TMs + 17 memories) still open.
- Dungeon gates built as the roster's "proposed": gym6 (Field of Swords), champion (Crucible, Dragonspiral).
- Bands 5-6 are too hard (typical win 0-54% / 0-35%; band 4 is 52-77%): a per-dungeon retune by
  trainer-balance-designer, on the owner's go.
- Nether rips: unsited (no heightmap; needs the NS1 oracle world). Whether the Nether is a Nuzlocke zone (declared
  not-zones pending).
- The crushed house lot (x1512-1520 z5254-5262) is the builder's choice; the two other damaged homes are not built.
- Older: sealed-chamber markers; Hoarfrost Hollow's mouth block (6722, 100, 1348); Scar Tarn water wards.

## 4. Do not rediscover
- A record a generator splices (route4_events.py -> rewards.json) is edited in the generator, never by hand: the
  splice test compares bytes.
- `tests/test_system_contracts.py` takes 8-10 minutes alone; run it in the background, never inside a 10-minute
  foreground call together with other suites.
- `python tools/spawn_tiers_audit.py --pack <scratch>` after `compile_spawns.py --out <scratch>` tests the real tiers
  without touching build/.
- Structural merges of data/world_probes.json and data/system_contracts.json (load the three stages, take each
  side's own records, keep indent 2) worked four times tonight.

## 5. Cost
`python tools/session_cost.py`: this session ran far past the hand-over line at the owner's request.
