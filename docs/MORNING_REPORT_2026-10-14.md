# Morning report: launch, 2026-10-15

## Is it up?
**The new live world is UP at the 12G play heap** (idle heap after GC 5.57 GB; install_check 0; NPC seats 46/46;
Compact NPCs 16/16), built, applied and verified by the apply's own checks. The whitelist is on and carries the old
server's two names, so those two can join as soon as there is a network route. Before adding more players, read the
audit below: it is not clean, and the call is yours. Network: `docs/launch/HOSTING.md` (a playit.gg tunnel is the
recommended route); friends install `docs/launch/CLIENT_PACK.md`; each new friend needs `whitelist add <name>`.

- Old live world: RETIRED, untouched: `cobblers-server-retired/2026-10-15-pre-reexport/cobblers-10240`, plus a sha256-verified
  snapshot `D:\cobblers-snapshots\live-cobblers-10240-2026-10-15` (731 files). Rollback: `docs/launch/ROLLBACK.md`.
- New world: a fresh WorldPainter export (484 regions, seed matched), your one player carried (every file sha256-equal),
  every one of the 126 apply steps run at 24G, the real bank installed, Cobblemon 1.8.2 and every approved mod, Lootr.
- The apply's own checkpoints: every town's floor gaps 0; 26 traders, 0 problems; the sea town 4,278 cells, 0 failed.
- Copy of the applied world: `D:\cobblers-snapshots\live-2026-10-15-after-apply` (33,604 files, verified).

## The offline audit: NOT CLEAN (your call before launch)
`reapply.py audit` on the applied copy (`derived/reapply/audit_20261015_135900.json`). Build audit, signposts and sea
town pass. What fails, and my reading of it (NOT verified in game):
- **Town audits, all eight gym towns and Merian Hut:** each gym town expects its ORIGINAL gym building template (0% in
  place) — the gym overhaul demolishes it and builds the authored gym, so the audit's plan is older than the gyms;
  "blocks standing on the road" are barrels, lecterns, hay and fences that town dressing and the market stalls place on
  the plazas after the town step. Light templates partly missing in gym2/6/8 towns (near the demolished buildings).
- **Light check (not a gate):** spawnable cells at block light 0: gym5 town 375, mining town 176, league 23, Northlight
  14, sea town 14, gym7 town 10, mansion 1. Hostile mobs can spawn there at night.
- **The Deep's city:** 2 of 1,064 blocks differ (black concrete texture at y0).
- **Rift rim and Sunset West trails:** 32 and 29 cells not paved as planned.
I believe the town and gym items are the audit lagging the gym overhaul, not a broken world, but I did not prove each one.

## Read back from the live world (12G, after the strip)
- install_check 0 problems; NPC seats 46/46; Compact NPCs 16/16; idle heap after GC 5.57 GB.
- **presence_audit: 973 of 1,062 probes present, 89 not.** Mega dens 31 (the probes report the den dressing PRESENT
  and count it as a miss: most likely they expect the retired open-air dens' dressing gone, which the fresh full run
  re-placed; cosmetic, needs a look), dens 29 (Mega dens short of members: the known staging issue, 17 there), the
  Night Shift's slots 1-4 (12, also on staging: unexplained), Fungal Isle stumps 3, gulch coves 3, residents 4,
  sanctuary 1, relic/relic_underground/Sunset plinth/Hoarfrost/Kyogre clicks/Long Count Grotle 1 each (known or
  entity-loading). Full list: run `python tools/presence_audit.py --server-dir <server> --out <file>`.

## Calls you made last night (recorded, not re-asked)
- Eight Challenge leaders with a new ace: fine. The 77 route/junior Challenge fights: not redesigned tonight.
- No cap on the Trading Post (about $3,800 an hour per pasture): fine. Kitchen and pharmacy goods SELL (built: 40 goods).
- The Trading Post's one-page 14-option dialogue: fine. Fossick and Northlight squares: built, with posts.
- Oak's rules pages rewritten; the battle guide's raw balance notes hidden; no wild Larvesta (Gible takes the South East
  Dunes' rare); voucher re-measured: unchanged at $23,748 (its grant is still not built).
- Hosting from this PC; a tunnel (playit.gg) recommended: `docs/launch/HOSTING.md`.

## Done before you went to bed
- #137 and #138 merged to main (f4268bcb). Launch work on `build/2026-10-14-launch`.
- Job D (rips that open and close at random): 80 candidates, the scheduler, the independent audit (15 generator
  mutations caught); its pause-survives-reload defect fixed; its pool-change-while-open defect recorded (close every
  rip, `function cobblers:rips/close_all`, before installing a pack that changes the candidate list).
- The server's mods swapped to the Cobblemon 1.8.2 set (101 jars); the old set kept in
  `cobblers-server-retired/mods-1.8.0-20261014`. A throwaway boot reached "Done" in 6.9 s.
- 1.8.2 fallout fixed as prepare found it: the bank file (CobbleDollars Beta-6.1 reads `default_bank.json`, a bare list
  with string prices: the real bank goes in that way), the install's hard-coded 1.8.0 jar name, Zamega's stones moved
  into Mega Showdown (three Z-A stones have no recipe; the Cutters still trade them), Tom's Storage's storage terminal
  (no longer locked with the crafting terminal), Showdown data zipped inside the 1.8.2 jar, the Tera-only Stellar type,
  the rip pool's siting notes read as places, and two rips re-sited clear of Fungal Isle's build.

## Overnight log
(each step below with its result)
- prepare stopped at coldwater_station_audit: the audit predated Kyogre's cave (R18KC) and the dialogue compiler's probes; fixed (0 problems, its known red test green)
- prepare stopped at nuzlocke_zones: stale after the Larvesta/Gible spawn change; regenerated (three zones' counts)
- prepare stopped at spawn_tiers_audit: the Great Crater had one rare without Larvesta; Carkol added as its second rare (Rolycoly's line, unused elsewhere); 92 areas pass
- prepare stopped at legendary_sweep_audit: rip_fungal_isle_3 was 20 blocks from the Newmoon Island legendary site; removed, Fungal Isle keeps 3 rip sites (no spot clears everything); rip_fungal_isle and _2 were moved earlier for Fungal Isle's own build
- prepare stopped at ambient_idle: the new Northlight square and Redbrow post collided with idle Pokemon scenes and the field hand's spot; the field hand moved mid-edge, two scenes allowed on the walkway, Redbrow's post re-sited (4833, 162, 5691)
- prepare's whole-build check: the 40 kitchen/pharmacy single-good sell functions were called by nothing (no menu line); sell/all now names them as operator entry points
- **PREPARE COMPLETE: all 242 jobs** on head b0547586 (full run, 2746 s; every function pack covered; 58 packs)
- staging install: every pack and config installed and current; the REAL bank (economy v2, 15 kinds) is the server's default_bank.json; 4 mod configs recorded (Cobbreeding's new alphaChances 0.05 accepted: a bred egg can hatch an alpha 5% of the time, your call)
- staging apply stopped at R16GA (gym arenas) twice: three probe points sat on cells the arenas fill differently (a buoy, a bubble column, the new roof); probes moved, each read true in the world; prepare re-run
- staging APPLY COMPLETE: all 24 changed/new steps, 0 problems (two runs; R16GA's probes fixed between); stripped (58 packs, 89.2% of function lines); booted 12G: idle heap after GC **5.56 GB**; install_check 0; npc_seats 46/46; Compact NPCs 16/16
- Distant Horizons v5 dropped enableServerGeneration; maxGenerationRequestDistance 0 keeps the server from generating past the border (overlay updated)
- staging presence audit: **1012 of 1062** probes present; 50 not: 31 known (dens 17, residents 4, gulch 3, Copperway Khan 2, relic gravel 1, Hoarfrost snow 1, etc.), 3 gym probes stale (regenerated), Sunset plinth is the Habitat Block (correct, probe dated), and 12 Night Shift slot cells + 3 Fungal Isle stumps + Kyogre clicks 4/11 + Long Count Grotle unexplained on staging: the live export rebuilds them from scratch and its read-back decides
- live world snapshot (server stopped): D:\cobblers-snapshots\live-cobblers-10240-2026-10-15, 731 files, 2.37 GB, 0 differ by sha256
- Lootr added (ADR-007): the jar in the server mods (102) and the manifest; the sea town's two boat barrels by `lootr custom-chest`
- **Lootr verified on staging (1.8.2)**: boot clean; the sea town's two boat barrels run from its function became lootr:lootr_barrel (customSize 27: EXP-056 C2 PASS); a portal cache chest with a loot table converted to lootr:lootr_chest on chunk load, loot table kept. Two-player opening NOT run (launch night is the test)
- live: retired the live world to cobblers-server-retired/2026-10-15-pre-reexport (rename, nothing deleted); exported 484 regions, seed_match true; carried 1 player (every file sha256-equal; the old world had no scoreboard.dat: it never ran our packs, so carry_players now carries it when present); install refused by a read guard matching the name cobblers-10240 (it also blocked the runbook's own export): the guards now refuse by place (the live server folder and the retired copies); prepare re-run
- **live apply stopped at R17M** (step 89 of 126): the shops were right, but CobbleDollars Beta-6 migrates each merchant with an EMPTY inline bank (nothing could be sold) and our verify read the old key. Fixed: every merchant gets the default bank after its summon, the markets pack sets cobbledollars:default to our bank, the verifies read CobbleDollars.Shop (294 merchant tests pass, market audit 0)
- **live APPLY COMPLETE**: all 126 steps (88, then 38 from R17M after the merchant bank fix); final verify: every town's floor gaps 0, traders 26/0 problems, sea town 4278 tested 0 failed (its one miss was the Lootr barrel the verify did not yet expect; fixed)
