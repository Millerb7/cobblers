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

Dungeon suites on 806feb88 (after the economy sim fix): 988 run, 987 passed; the one failure (kit3's published-budget
text) fixed in 154b30e4. Draw audit 87/87; independent audit + guide + pack split 57/57; contracts + economy 185 passed.
NOT re-run: `test_dungeon_audit.py`'s 2,135 per-site cases (over 50 minutes; four ash_bell lure cases were red before).
Known red tests: `test_coldwater_station_audit::test_built_pack_passes_every_check` (built-pack stub rule owed a
rewrite, recorded by the Kyogre builder); four ash_bell `lure` cases in `test_dungeon_audit` (red at 6249332e, before the draw). The dungeon suites' full run did NOT complete: `test_dungeon_audit.py` (2,135 per-site cases) ran past 50 minutes at 3%
with 16 early failures unidentified; the other dungeon and rip suites were re-run in the background (`.scratch/d2.txt`). Contracts: 76 pass, C3 and C14 xfail.

Staging: last installed from prepare 238/238 at bff8baf (2026-10-12), build packs stripped, 12G. Next cycle: snapshot
to D:, prepare, stop, hold the bank file, install, boot 24G watchdog off, `reapply.py run` (new steps include R14R,
R18KC, R16CH, R18CH, R16DR re-apply, R9F), stop, watchdog 60000, `strip`, boot 12G, read back
(`npc_seats.py verify`, `presence_audit --only extra`, the per-place verify commands). A fresh session should do it.

## 3. The owner's instructions for the next sessions (2026-10-13, all DECIDED; do them, do not re-ask)
Run them as separate sessions (CLAUDE.md "one session per job"); job A touches the server, B and C fan out.

**A. Mods: move to Cobblemon 1.8.2 and update every other pack and mod** ("update to 1.8.2 and see if we need
these changes and to use them. also update any other pack or mod").
- 40 non-lockstep updates are already downloaded and verified: `C:/Users/wnd/Documents/cobblers-local/mod-updates-2026-10-13/`
  (MANIFEST.json). The lockstep set is NOT downloaded: Cobblemon 1.8.2, tim_core 1.8.2-1.34.0, tmcraft 1.4.19+1.8.2,
  rctapi 0.16.2-beta, Cobbreeding 2.4.1, Mega Showdown 1.3.0 hotfix, Zamega 1.8.2+1.8.2 (URLs and sizes in
  `docs/research/COBBLEVERSE_COMPATIBILITY.md` "Update audit, 2026-10-13"; re-query Modrinth first: capturexp may have
  a 1.8.2 build by now; if not, it must come out, since it pins 1.8.1 exactly). "Any other pack or mod" includes the HOLD
  rows: CobbleDollars Beta-6.1 renames `bank.json` to `default_bank.json` (tools/bank.py writes the old path), rctmod
  0.19.2 changes trainer messages to speech bubbles, fabric-language-kotlin, LegendaryMonuments, biomereplacer and
  cobblemon-additions are world-critical (CLAUDE.md principle 10/11: read each changelog against our use before taking
  it), owo-lib and ScalableLux are alpha. Cobblemon 1.8.2 removes TM Mega Drain: `data/tm_gate.json:124`,
  `data/markets.json`, `data/progression.json`, `data/challenge_mode.json`, `data/trainers.json` reference it.
- Then the client pack (modpack/manifest) and the friends' zip follow the server. Snapshot, staging boot test
  (boot-test skill), read the log, then the full install cycle with tonight's build.

**B. Economy v2 finish** (ECONOMY_V2.md section 7):
- B2 Trading Post with NO cap (farming allowed), at the market town squares and ports such as Pacifidlog.
- The 13 held TMs made available; crafting is acceptable (a recipe per TM, or a barter).
- The 17 Silvally memories from the Station Director (`npc_station_director`, `dlg_station_director`, Urshifu's NPC).
- Recompute the Challenge voucher (`tools/challenge_voucher.py --write`) and report its old and new figures
  (oak_cash $4,000, total $23,748 before). Then B4's audit extended to the Trading Post (A4), by a different agent.

**C. Challenge mode: every challenge fight should be "a good bit different" from Normal.** Go through the Challenge
roster (`data/challenge_mode.json`, the trainers it overrides) and make tweaks: trainer-balance-designer (Opus, no
shell: data only) for the design, then a shell builder for any generator change, then an independent check.

**D. Rips must SPAWN, not stand** (the owner, 2026-10-14: "i thought we were placing possible spawn locations and then
randomly having them appear all over?"). What was built is 20 permanent rips (`data/dungeon_rips.json`): a misreading of
"find spawn locations". Not installed, so nothing to undo in the world. Build: a pool of candidate sites (several per
region, `tools/dungeon_rips.py` siting rules; the 20 join the pool); a runtime scheduler (scoreboard timer) that opens a
few rips at random candidates, keeps each open for a while, then closes it and restores the ground (the open = frame +
themed patch and close = `restore` logic exist; today they run once from R16DR, and `rip_close_lines` still fails
closed because `rip.under` is not recorded); forceload while writing; the rip functions become RUNTIME pack content
(not stripped: a heap cost, measure it). Proposed defaults, NOT yet confirmed by the owner: 3-5 open at once, about an
hour of play each or closed once entered, anywhere (gated regions included), a chat line naming the region. The draw
itself (band, least-recent, sigil) is unchanged; its audit must follow.

Also decided tonight, already recorded: the Master Ball's cheap barter is fine; dungeon bands 5-6 difficulty is
accepted (no retune); the 12 retired rip patches' ground is grass; Kyogre's rejoin eject built; the 13 trail rips
retired; gated rips allowed; no Nether rips.

Still open (older, the owner has not answered): the proposed dungeon gates (gym6 Field of Swords; champion Crucible,
Dragonspiral); whether the Nether is a Nuzlocke zone; the crushed-house lot and the two other damaged homes;
sealed-chamber markers; Hoarfrost Hollow's mouth block (6722, 100, 1348); Scar Tarn water wards.

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
